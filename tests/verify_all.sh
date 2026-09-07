#!/usr/bin/env bash
# Run the three browser suites with room between them.
#
# Chaining them back to back once produced 49 spurious failures: each suite exits
# before the next starts, but WebKit's helper processes take a moment to actually
# go away, and the next suite starts under the tail of the previous one. A short
# settle between suites removes that, and each suite is run in its own process so
# a crash in one cannot take the others with it.
set -uo pipefail
cd "$(dirname "$0")/.."

settle() {
  for _ in $(seq 1 20); do
    n=$(pgrep -f "ms-playwright.*[Ww]eb[Kk]it" 2>/dev/null | wc -l | tr -d ' ')
    [ "${n:-0}" -eq 0 ] && return 0
    sleep 1
  done
}

fail=0
for suite in verify_site verify_units verify_deep; do
  echo "── ${suite} ───────────────────────────────────────────"
  settle
  node "tests/${suite}.mjs" || fail=1
done
settle
echo
[ "$fail" = 0 ] && echo "all browser suites pass" || echo "a suite failed"
exit "$fail"
