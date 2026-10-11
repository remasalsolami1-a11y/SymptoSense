"""Tiny TTL cache for expensive public read-only snapshots (row counts, file
scans). Public pages used to recompute them on every view."""
import copy
import functools
import threading
import time


def cached(fn, ttl=300):
    lock = threading.Lock()
    box = {"at": 0.0, "val": None}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        now = time.time()
        if box["val"] is not None and now - box["at"] < ttl and not args and not kwargs:
            return copy.deepcopy(box["val"])
        val = fn(*args, **kwargs)
        if not args and not kwargs:
            with lock:
                box["at"], box["val"] = now, copy.deepcopy(val)
        return val
    return wrapper
