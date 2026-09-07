#!/usr/bin/env bash
# Re-download every source behind every dataset and compare, value for value.
# One command so the whole claim can be re-checked rather than trusted.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
run() {
  echo "── $1 ──────────────────────────────────────────"
  if ! python3 "tests/$2" 2>&1 | tail -"${3:-6}"; then fail=1; fi
}
run "OECD, 51 datasets"        audit_fidelity.py 60
run "Eurostat, 23 tables"      audit_fidelity_estat.py 4
run "ICTWSS"                   audit_fidelity_ictwss.py 3
run "ILOSTAT strikes"          audit_fidelity_ilo.py 6
run "Our World in Data"        audit_fidelity_owid.py 3
run "WID bulk files"           audit_fidelity_wid.py 3
run "BLS, 3 datasets"          audit_fidelity_bls.py 5
run "EPI"                      audit_fidelity_epi.py 2
run "Online Labour Index"      audit_fidelity_oli.py 2
echo
[ "$fail" = 0 ] && echo "source verification complete" || echo "a check failed"
exit "$fail"
