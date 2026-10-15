#!/usr/bin/env bash
# Runs every non-browser test file in its own process with its own SQLite file (tests share module-level state, so
# files are isolated from each other), in parallel. Exit code is non-zero if any file fails.
# Browser files (Chromium) and the PostgreSQL file are run by their own CI jobs, where they may not be skipped.
# The number of passed / failed / skipped tests is printed, and the run fails when more tests were skipped than
# SKIP_BUDGET (default 1: the single documented skip in conftest.SKIP_REASONS) or when failures/errors exist.
# Usage: tools/ci_run_tests.sh [parallelism]
set -u
cd "$(dirname "$0")/.."
JOBS="${1:-4}"
OUT="$(mktemp -d)"
export PYTHONPATH="$PWD/tools/offline_tests${PYTHONPATH:+:$PYTHONPATH}"
export WEB_SECRET="ci-secret-that-is-longer-than-thirty-two-characters"
export SESSION_COOKIE_SECURE=0 SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER=1
run_one() {
  f="$1"; b="$(basename "$f" .py)"
  DB_PATH="$OUT/$b.db" python -m pytest -q -p no:cacheprovider --tb=short -rs --junitxml="$OUT/$b.xml" "$f" > "$OUT/$b.txt" 2>&1
  echo $? > "$OUT/$b.rc"
}
export -f run_one; export OUT
ls test_*.py | grep -v -E '^test_e2e_|_browser\.py$|^test_postgres_|^test_interaction_bridge_data_actions' | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
fail=0
for rc in "$OUT"/*.rc; do
  b="$(basename "$rc" .rc)"
  # 0 = passed, 5 = no tests collected (skipped module); anything else is a failure
  if [ "$(cat "$rc")" != "0" ] && [ "$(cat "$rc")" != "5" ]; then echo "::error::FAILED $b"; tail -25 "$OUT/$b.txt"; fail=1; fi
done
echo "files: $(ls "$OUT"/*.rc | wc -l)"
python tools/ci_check_skips.py "$OUT" --budget "${SKIP_BUDGET:-1}" --min-tests 2000 || fail=1
exit $fail
