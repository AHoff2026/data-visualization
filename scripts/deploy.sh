#!/usr/bin/env bash
# Publish site/ to the gh-pages branch.
#
# The guard below is not decorative. `git push origin "${SHA}:gh-pages"` with an
# empty SHA expands to `git push origin :gh-pages`, which DELETES the branch and
# takes the whole site down. That happened once. An empty split must abort.
set -euo pipefail
cd "$(dirname "$0")/.."

SHA="$(git subtree split --prefix site main | tail -1)"
if [ -z "${SHA}" ] || ! git cat-file -e "${SHA}^{commit}" 2>/dev/null; then
  echo "deploy aborted: subtree split produced no commit" >&2
  exit 1
fi
COUNT="$(git ls-tree -r --name-only "${SHA}" | wc -l | tr -d ' ')"
if [ "${COUNT}" -lt 100 ]; then
  echo "deploy aborted: split tree holds only ${COUNT} files, expected hundreds" >&2
  exit 1
fi
git push -q origin "${SHA}:refs/heads/gh-pages" --force
git push -q origin main
echo "deployed ${SHA} (${COUNT} files)"
