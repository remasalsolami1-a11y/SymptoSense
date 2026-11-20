"""Real, reproducible Before/After benchmark for db.py connection pooling.

Run directly:
    python3 bench_connection_pooling.py

Requires a reachable PostgreSQL instance via DATABASE_URL. The measured result
is also persisted to ``ss_performance_benchmarks`` so the Admin dashboard can
show the exact latest Before/After numbers.
"""
import os

import db
import performance_benchmark

N_REQUESTS = max(10, min(1000, int(os.environ.get("BENCH_REQUESTS", "300"))))
CONCURRENT_USERS = max(2, min(20, int(os.environ.get("BENCH_CONCURRENT_USERS", "20"))))
REQUESTS_PER_USER = max(1, min(50, int(os.environ.get("BENCH_REQUESTS_PER_USER", "10"))))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def _fmt(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def main():
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is required for the PostgreSQL pooling benchmark.")

    db.DATABASE_URL = DATABASE_URL
    db.USE_POSTGRES = True
    db.PH = "%s"
    db._pg_pool = None

    print(f"Benchmarking {N_REQUESTS} sequential SELECT 1 operations against PostgreSQL...")
    result = performance_benchmark.run_connection_pooling_benchmark(
        sequential_requests=N_REQUESTS,
        concurrent_workers=CONCURRENT_USERS,
        requests_per_worker=REQUESTS_PER_USER,
        benchmark_type="full_cli",
        persist=True,
    )

    before, after, concurrent = result["before"], result["after"], result["concurrent"]
    print(f"\nBEFORE — {result['before_strategy']} (n={before['n']})")
    print(f"  total wall time   : {before['total_ms']:8.1f} ms")
    print(f"  mean per operation: {before['mean_ms']:8.2f} ms")
    print(f"  median            : {before['median_ms']:8.2f} ms")
    print(f"  p95               : {before['p95_ms']:8.2f} ms")

    print(f"\nAFTER — {result['after_strategy']} (n={after['n']})")
    print(f"  total wall time   : {after['total_ms']:8.1f} ms")
    print(f"  mean per operation: {after['mean_ms']:8.2f} ms")
    print(f"  median            : {after['median_ms']:8.2f} ms")
    print(f"  p95               : {after['p95_ms']:8.2f} ms")

    print(f"\n=> {_fmt(result['speedup_x'], 1)}x faster mean connection/query time")
    print(f"=> {_fmt(result['improvement_pct'])}% lower measured mean latency")
    print(f"=> {_fmt(result['saved_ms_per_operation'])} ms saved per database operation on average")
    print(
        f"\nConcurrent: {concurrent['workers']} users x {concurrent['requests_per_worker']} requests "
        f"({concurrent['total_requests']} total)"
    )
    print(f"  BEFORE wall time: {concurrent['before_wall_ms']:.1f} ms")
    print(f"  AFTER  wall time: {concurrent['after_wall_ms']:.1f} ms")
    print(f"  Speedup          : {_fmt(concurrent['speedup_x'], 1)}x")
    print("\nSaved to the database for Admin Dashboard → Database Performance.")
    print("Scope: connection-acquisition overhead only; not full page/end-to-end latency.")


if __name__ == "__main__":
    main()
