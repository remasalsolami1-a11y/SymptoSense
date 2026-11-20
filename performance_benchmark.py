"""Measured database connection-pooling benchmark for the Admin dashboard.

The benchmark intentionally isolates connection acquisition overhead using
``SELECT 1``. Results are persisted in the active application database so the
latest measured Before/After evidence survives application restarts and can be
shown in the Admin dashboard without rerunning load on every page view.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import statistics
import threading
import time
from datetime import datetime, timezone

import db

_BENCH_LOCK = threading.Lock()


class BenchmarkUnavailable(RuntimeError):
    """Raised when connection pooling cannot be benchmarked on this backend."""


class BenchmarkBusy(RuntimeError):
    """Raised when another benchmark is already running in this process."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _percentile95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * 0.95)))
    return ordered[index]


def _summary(samples: list[float]) -> dict:
    if not samples:
        return {"n": 0, "total_ms": 0.0, "mean_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    return {
        "n": len(samples),
        "total_ms": round(sum(samples) * 1000, 3),
        "mean_ms": round(statistics.mean(samples) * 1000, 3),
        "median_ms": round(statistics.median(samples) * 1000, 3),
        "p95_ms": round(_percentile95(samples) * 1000, 3),
        "min_ms": round(min(samples) * 1000, 3),
        "max_ms": round(max(samples) * 1000, 3),
    }


def init_schema() -> None:
    conn = db._conn()
    cur = conn.cursor()
    try:
        if db.USE_POSTGRES:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS ss_performance_benchmarks (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    benchmark_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )
        else:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS ss_performance_benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    benchmark_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def save_result(result: dict) -> dict:
    init_schema()
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    conn = db._conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"INSERT INTO ss_performance_benchmarks (created_at,benchmark_type,payload) VALUES ({db.PH},{db.PH},{db.PH})",
            (str(result.get("measured_at") or _utc_now()), str(result.get("benchmark_type") or "connection_pooling"), payload),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return result


def latest_result() -> dict | None:
    try:
        # Read-only lookup: if no benchmark has ever been saved, the table may
        # not exist yet. In that case simply return None; POST/CLI benchmark
        # execution owns schema creation.
        conn = db._conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT payload FROM ss_performance_benchmarks ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
        finally:
            cur.close()
            conn.close()
        if not row:
            return None
        data = json.loads(row[0])
        return data if isinstance(data, dict) else None
    except Exception:
        # The Admin page should remain usable when no benchmark exists yet or
        # during a transient database incident.
        return None


def _raw_connect_once(database_url: str) -> float:
    import psycopg2

    started = time.perf_counter()
    conn = psycopg2.connect(
        database_url,
        connect_timeout=max(3, min(30, int(os.environ.get("POSTGRES_CONNECT_TIMEOUT_SECONDS", "10") or 10))),
        application_name="symptosense-benchmark-before",
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        cur.close()
        conn.close()
    return time.perf_counter() - started


def _pooled_once() -> float:
    started = time.perf_counter()
    conn = db._conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        cur.close()
        conn.close()
    return time.perf_counter() - started


def _concurrent_wall(fn, workers: int, per_worker: int) -> float:
    def worker(_):
        for _ in range(per_worker):
            fn()

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(worker, range(workers)))
    return time.perf_counter() - started


def run_connection_pooling_benchmark(
    *,
    sequential_requests: int = 25,
    concurrent_workers: int = 6,
    requests_per_worker: int = 3,
    benchmark_type: str = "admin_quick",
    persist: bool = True,
) -> dict:
    """Run a bounded real Before/After benchmark against the active Postgres DB.

    BEFORE opens a new psycopg2 connection for every query. AFTER borrows a
    connection through the application's current ``db._conn()`` pool. The SQL
    workload is identical on both sides (``SELECT 1``).
    """
    if not db.USE_POSTGRES or not str(getattr(db, "DATABASE_URL", "") or "").strip():
        raise BenchmarkUnavailable("postgres_required")

    sequential_requests = max(10, min(1000, int(sequential_requests)))
    pool_max = db._bounded_env_int("POSTGRES_POOL_MAX", 10, 1, 50)
    concurrent_workers = max(2, min(20, pool_max, int(concurrent_workers)))
    requests_per_worker = max(1, min(50, int(requests_per_worker)))
    database_url = db.DATABASE_URL

    if not _BENCH_LOCK.acquire(blocking=False):
        raise BenchmarkBusy("benchmark_already_running")
    try:
        # Warm each path once so first-use import/pool/DNS effects do not
        # dominate the measured samples.
        _raw_connect_once(database_url)
        _pooled_once()

        before_samples = [_raw_connect_once(database_url) for _ in range(sequential_requests)]
        after_samples = [_pooled_once() for _ in range(sequential_requests)]
        before = _summary(before_samples)
        after = _summary(after_samples)

        before_mean = before["mean_ms"]
        after_mean = after["mean_ms"]
        speedup = (before_mean / after_mean) if after_mean > 0 else None
        improvement = ((before_mean - after_mean) / before_mean * 100.0) if before_mean > 0 else None
        saved_ms = before_mean - after_mean

        before_wall = _concurrent_wall(lambda: _raw_connect_once(database_url), concurrent_workers, requests_per_worker)
        after_wall = _concurrent_wall(_pooled_once, concurrent_workers, requests_per_worker)
        concurrent_speedup = (before_wall / after_wall) if after_wall > 0 else None

        result = {
            "benchmark_type": benchmark_type,
            "measured_at": _utc_now(),
            "database_backend": "PostgreSQL",
            "workload": "SELECT 1",
            "methodology": "Same query and database; only connection acquisition strategy changes.",
            "before_strategy": "new psycopg2.connect() per operation",
            "after_strategy": "shared ThreadedConnectionPool via db._conn()",
            "sequential_requests": sequential_requests,
            "before": before,
            "after": after,
            "speedup_x": round(speedup, 3) if speedup is not None else None,
            "improvement_pct": round(improvement, 2) if improvement is not None else None,
            "saved_ms_per_operation": round(saved_ms, 3),
            "concurrent": {
                "workers": concurrent_workers,
                "requests_per_worker": requests_per_worker,
                "total_requests": concurrent_workers * requests_per_worker,
                "before_wall_ms": round(before_wall * 1000, 3),
                "after_wall_ms": round(after_wall * 1000, 3),
                "speedup_x": round(concurrent_speedup, 3) if concurrent_speedup is not None else None,
            },
            "scope_note": "Measures connection-acquisition overhead only, not full page or end-to-end route latency.",
        }
        return save_result(result) if persist else result
    finally:
        _BENCH_LOCK.release()
