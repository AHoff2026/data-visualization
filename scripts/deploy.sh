#!/usr/bin/env bash
# Publish site/ to GitHub Pages. Runs the full test suite first and refuses to
# deploy a failing build.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "── unit tests ──────────────────────────────────────────"
node tests/verify_units.mjs

if ! curl -sf -o /dev/null http://localhost:8231/index.html; then
  echo "starting local server on :8231"
  nohup python3 -m http.server 8231 --directory site >/tmp/dvserver.log 2>&1 </dev/null &
  sleep 2
fi

echo "── site tests (WebKit) ─────────────────────────────────"
node tests/verify_site.mjs

if [ "${DEEP:-0}" = "1" ]; then
  echo "── deep UI tests ─────────────────────────────────────"
  node tests/verify_deep.mjs
fi

echo "── publishing ──────────────────────────────────────────"
git add -A
git diff --cached --quiet || git commit -q -m "${1:-Update site}"
git push -q origin main
git push -q origin "$(git subtree split --prefix site main)":refs/heads/gh-pages --force
echo "pushed. waiting for Pages…"
for _ in $(seq 1 40); do
  s=$(gh api repos/AHoff2026/data-visualization/pages --jq .status 2>/dev/null || echo "?")
  [ "$s" = "built" ] && break
  sleep 15
done
code=$(curl -s -o /dev/null -w "%{http_code}" https://ahoff2026.github.io/data-visualization/)
echo "live: https://ahoff2026.github.io/data-visualization/  (HTTP $code)"
