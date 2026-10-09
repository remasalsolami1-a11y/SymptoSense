#!/usr/bin/env bash
# Runs every non-browser test file in its own process with its own SQLite file (tests share module-level state, so
# files are isolated from each other), in parallel. Exit code is non-zero if any file fails.
# Usage: tools/ci_run_tests.sh [parallelism]
set -u
cd "$(dirname "$0")/.."
JOBS="${1:-4}"
OUT="$(mktemp -d)"
export WEB_SECRET="ci-secret-that-is-longer-than-thirty-two-characters"
export SESSION_COOKIE_SECURE=0 SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER=1
run_one() {
  f="$1"; b="$(basename "$f" .py)"
  DB_PATH="$OUT/$b.db" python -m pytest -q -p no:cacheprovider --tb=short "$f" > "$OUT/$b.txt" 2>&1
  echo $? > "$OUT/$b.rc"
}
export -f run_one; export OUT
ls test_*.py | grep -v '^test_e2e_' | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
fail=0
for rc in "$OUT"/*.rc; do
  b="$(basename "$rc" .rc)"
  # 0 = passed, 5 = no tests collected (skipped module); anything else is a failure
  if [ "$(cat "$rc")" != "0" ] && [ "$(cat "$rc")" != "5" ]; then echo "::error::FAILED $b"; tail -25 "$OUT/$b.txt"; fail=1; fi
done
echo "files: $(ls "$OUT"/*.rc | wc -l)  passed tests: $(cat "$OUT"/*.txt | grep -o '[0-9]* passed' | awk '{s+=$1} END{print s+0}')"
exit $fail
