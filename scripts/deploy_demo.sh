#!/usr/bin/env bash
# Publish the read-only demo (real recorded cases) to GitHub Pages: the gh-pages branch.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run python scripts/export_demo.py
(cd dashboard && VITE_DEMO=1 npx vite build --base=/complaint-replay/ --outDir dist-demo --emptyOutDir)
rm -rf dashboard/public/demo

out="$(mktemp -d)"
cp -r dashboard/dist-demo/. "$out"
touch "$out/.nojekyll"
cd "$out"
git init -q -b gh-pages
git add -A
git commit -qm "Deploy recorded demo"
git push -qf https://github.com/yashasviyadav30/complaint-replay.git gh-pages
echo "pushed to gh-pages"
