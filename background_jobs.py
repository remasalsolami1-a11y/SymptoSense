"""Optional background-job abstraction.

Production can use Redis/RQ via REDIS_URL. Development and deployments without
Redis use a bounded in-process executor so the core web app remains functional.
Only named, allow-listed jobs can be queued.
"""
from __future__ import annotations
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import db

def _local_worker_count() -> int:
    try:
        value = int(str(os.environ.get("LOCAL_JOB_WORKERS", "2") or "2").strip())
    except (TypeError, ValueError, OverflowError):
        value = 2
    return max(1, min(value, 4))


_EXECUTOR = ThreadPoolExecutor(max_workers=_local_worker_count(), thread_name_prefix="symptosense-job")
_LOCK = threading.Lock()
_ALLOWED = {"source_monitor", "backup", "retention_cleanup"}


def _now(): return datetime.now(timezone.utc).isoformat()


def init_schema():
    db.init_db(); conn=db._conn()
    try:
        c=conn.cursor(); serial="SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""CREATE TABLE IF NOT EXISTS background_jobs (
            id {serial}, job_id TEXT UNIQUE NOT NULL, job_name TEXT NOT NULL,
            backend TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
            started_at TEXT, finished_at TEXT, result_json TEXT, error_code TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status, created_at)")
        conn.commit()
    finally: conn.close()


def _record(job_id, job_name, backend, status, *, started_at=None, finished_at=None, result=None, error_code=None):
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); payload=json.dumps(result, ensure_ascii=False, default=str)[:20000] if result is not None else None
        if db.USE_POSTGRES:
            c.execute("""INSERT INTO background_jobs(job_id,job_name,backend,status,created_at,started_at,finished_at,result_json,error_code)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(job_id) DO UPDATE SET status=EXCLUDED.status,started_at=COALESCE(EXCLUDED.started_at,background_jobs.started_at),finished_at=COALESCE(EXCLUDED.finished_at,background_jobs.finished_at),result_json=EXCLUDED.result_json,error_code=EXCLUDED.error_code""",
                (job_id,job_name,backend,status,_now(),started_at,finished_at,payload,error_code))
        else:
            c.execute("""INSERT INTO background_jobs(job_id,job_name,backend,status,created_at,started_at,finished_at,result_json,error_code)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,started_at=COALESCE(excluded.started_at,background_jobs.started_at),finished_at=COALESCE(excluded.finished_at,background_jobs.finished_at),result_json=excluded.result_json,error_code=excluded.error_code""",
                (job_id,job_name,backend,status,_now(),started_at,finished_at,payload,error_code))
        conn.commit()
    finally: conn.close()


def run_named_job(job_name: str, payload: dict | None = None):
    payload = dict(payload or {})
    if job_name not in _ALLOWED: raise ValueError("job_not_allowed")
    if job_name == "source_monitor":
        import source_monitor
        try:
            limit = int(payload.get("limit") or 100)
            timeout = float(payload.get("timeout") or 5.0)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid_job_parameters")
        if not 1 <= limit <= 500 or not 1.0 <= timeout <= 10.0:
            raise ValueError("invalid_job_parameters")
        return source_monitor.run_monitor(limit=limit, timeout=timeout)
    if job_name == "backup":
        import backup_restore
        return backup_restore.create_backup()
    if job_name == "retention_cleanup":
        import data_retention
        return data_retention.run_cleanup()
    raise ValueError("job_not_allowed")


def _run_tracked(job_id: str, job_name: str, payload: dict, backend: str):
    """Execute an allow-listed job and persist its lifecycle for any backend."""
    _record(job_id, job_name, backend, "running", started_at=_now())
    try:
        result = run_named_job(job_name, payload)
        _record(job_id, job_name, backend, "finished", finished_at=_now(), result=result)
        return result
    except Exception as exc:
        _record(job_id, job_name, backend, "failed", finished_at=_now(), error_code=type(exc).__name__)
        raise


def _local_runner(job_id, job_name, payload):
    try:
        return _run_tracked(job_id, job_name, payload, "local")
    except Exception:
        # The web request has already returned a job id. Keep the failure in the
        # status table rather than crashing the executor thread noisily.
        return None


def _rq_runner(job_id, job_name, payload):
    """RQ entry point; keeps the application status table in sync with RQ."""
    return _run_tracked(job_id, job_name, payload, "rq")


def backend_status() -> dict:
    mode = str(os.environ.get("BACKGROUND_JOBS_BACKEND", "local") or "local").strip().lower()
    if mode not in {"local", "rq"}:
        mode = "local"
    if mode != "rq":
        return {"backend":"local","available":True,"configured":"local"}

    redis_url=os.environ.get("REDIS_URL","").strip()
    if not redis_url:
        return {"backend":"rq","available":False,"fallback":"local","reason":"redis_not_configured"}
    try:
        import redis
        from rq import Queue
        conn=redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2)
        conn.ping(); Queue("symptosense", connection=conn)
        # Worker presence cannot be proven reliably from the web process.  RQ is
        # therefore selected only through BACKGROUND_JOBS_BACKEND=rq, which is
        # documented alongside the dedicated rq_worker.py service.
        return {"backend":"rq","available":True,"configured":"rq"}
    except Exception:
        return {"backend":"rq","available":False,"fallback":"local","reason":"redis_unavailable"}


def enqueue(job_name: str, payload: dict | None = None) -> dict:
    if job_name not in _ALLOWED: raise ValueError("job_not_allowed")
    payload=dict(payload or {}); job_id="job_"+uuid.uuid4().hex
    state=backend_status(); backend=state["backend"] if state.get("available") else "local"
    _record(job_id,job_name,backend,"queued")
    if backend=="rq":
        try:
            import redis
            from rq import Queue
            conn=redis.from_url(os.environ["REDIS_URL"], socket_timeout=2, socket_connect_timeout=2)
            q=Queue("symptosense",connection=conn,default_timeout=300)
            q.enqueue(_rq_runner,job_id,job_name,payload,job_id=job_id,job_timeout=300,result_ttl=3600,failure_ttl=86400)
        except Exception:
            # Do not leave a permanently queued row when Redis/RQ disappears
            # between the health check and the actual enqueue operation.
            _record(job_id, job_name, "rq", "failed", finished_at=_now(), error_code="enqueue_failed")
            raise RuntimeError("background_backend_unavailable")
    else:
        _EXECUTOR.submit(_local_runner,job_id,job_name,payload)
    return {"job_id":job_id,"job_name":job_name,"backend":backend,"status":"queued"}


def get(job_id: str) -> dict | None:
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT job_id,job_name,backend,status,created_at,started_at,finished_at,result_json,error_code FROM background_jobs WHERE job_id={db.PH}",(str(job_id),)); r=c.fetchone()
        if not r: return None
        out=dict(zip(["job_id","job_name","backend","status","created_at","started_at","finished_at","result","error_code"],r))
        try: out["result"]=json.loads(out["result"]) if out["result"] else None
        except Exception: out["result"]=None
        return out
    finally: conn.close()
