"""RQ worker entrypoint. Run only when REDIS_URL is configured."""
import os

if __name__ == "__main__":
    if not os.environ.get("REDIS_URL"):
        raise SystemExit("REDIS_URL is required for the dedicated background worker")
    import redis
    from rq import Worker, Queue
    conn=redis.from_url(os.environ["REDIS_URL"])
    worker=Worker([Queue("symptosense",connection=conn)],connection=conn)
    worker.work(with_scheduler=False)
