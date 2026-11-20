#!/usr/bin/env python3
"""Live link check for every reference added in V251 (run manually or from a scheduled CI job; needs internet).

    python tools/check_sources.py [--workers 8]
Exit code 1 when any URL does not answer 200/3xx.  Some publishers (Mayo, Cleveland) rate-limit bots: a 403/429
is reported as WARN, not FAIL.
"""
import argparse
import concurrent.futures
import sys
import urllib.request

import trusted_sources_v251 as t


def urls():
    out = set()
    for rows in list(t.DISEASE_SOURCES.values()) + list(t.SEARCH_SOURCES.values()):
        out.update(r[3] for r in rows)
    for v in t.BLOOD_SOURCES.values():
        out.update(r[3] for r in v.values())
    return sorted(out)


def check(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SymptoSense-link-check/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return url, r.status
    except urllib.error.HTTPError as e:
        return url, e.code
    except Exception as e:  # noqa: BLE001
        return url, str(e)[:60]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    fails = 0
    with concurrent.futures.ThreadPoolExecutor(a.workers) as ex:
        for url, status in ex.map(check, urls()):
            if status in (200, 301, 302, 303, 307, 308):
                continue
            level = "WARN" if status in (403, 429) else "FAIL"
            fails += level == "FAIL"
            print(level, status, url)
    print("done;", fails, "failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
