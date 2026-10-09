"""Dedicated RQ worker for V48 background jobs.

Deploy this as a separate worker service only when
BACKGROUND_JOBS_BACKEND=rq and REDIS_URL are configured.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    redis_url = str(os.environ.get("REDIS_URL", "") or "").strip()
    if not redis_url:
        print("REDIS_URL is required for the RQ worker", file=sys.stderr)
        return 2
    try:
        import redis
        from rq import Queue, Worker
    except ImportError:
        print("redis and rq packages are required", file=sys.stderr)
        return 2

    connection = redis.from_url(
        redis_url,
        socket_timeout=5,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    connection.ping()
    queue = Queue("symptosense", connection=connection, default_timeout=300)
    worker = Worker([queue], connection=connection)
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
