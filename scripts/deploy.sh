#!/usr/bin/env bash
# Publish site/ to GitHub Pages. Runs the full test suite first and refuses to
# deploy a failing build.
set -euo pipefail
cd "$(dirname "$0")/.."


if ! curl -sf -o /dev/null http://localhost:8231/index.html; then
  echo "starting local server on :8231"
  nohup python3 -m http.server 8231 --directory site >/tmp/dvserver.log 2>&1 </dev/null &
  sleep 2
fi

# One runner for all three browser suites: it puts a settle between them, which
# is what stops a chained run failing on the tail of the previous suite's
# browsers rather than on anything real.
echo "── browser suites ──────────────────────────────────────"
bash tests/verify_all.sh


echo "── publishing ──────────────────────────────────────────"
git add -A
git diff --cached --quiet || git commit -q -m "${1:-Update site}"
git push -q origin main
# An empty split expands to `git push origin :gh-pages`, which DELETES the branch
# and takes the site down. That has happened once. Refuse to push nothing.
SHA="$(git subtree split --prefix site main | tail -1)"
if [ -z "${SHA}" ] || ! git cat-file -e "${SHA}^{commit}" 2>/dev/null; then
  echo "deploy aborted: subtree split produced no commit" >&2; exit 1
fi
COUNT="$(git ls-tree -r --name-only "${SHA}" | wc -l | tr -d ' ')"
if [ "${COUNT}" -lt 100 ]; then
  echo "deploy aborted: split tree holds only ${COUNT} files" >&2; exit 1
fi
git push -q origin "${SHA}:refs/heads/gh-pages" --force
echo "pushed ${COUNT} files"
echo "pushed. waiting for Pages…"
for _ in $(seq 1 40); do
  s=$(gh api repos/AHoff2026/data-visualization/pages --jq .status 2>/dev/null || echo "?")
  [ "$s" = "built" ] && break
  sleep 15
done
code=$(curl -s -o /dev/null -w "%{http_code}" https://ahoff2026.github.io/data-visualization/)
echo "live: https://ahoff2026.github.io/data-visualization/  (HTTP $code)"
