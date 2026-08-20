#!/usr/bin/env bash
#
# Local mirror of .github/workflows/smoke-test.yml — build the site, serve it,
# and crawl every internal link looking for 404s.
#
# Run it directly, or let the pre-push hook run it for you:
#
#   ./scripts/smoke-test.sh
#
# Env:
#   SMOKE_PORT   port to serve the built site on (default 4322, kept off the
#                dev server's 4321 so a running `npm run dev` isn't crawled
#                by mistake and the ports don't collide)
#   SKIP_BUILD=1 crawl the existing dist/ instead of rebuilding

set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${SMOKE_PORT:-4322}"
BASE="http://localhost:${PORT}"
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if lsof -i ":${PORT}" -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "smoke: port ${PORT} is already in use — set SMOKE_PORT to a free port" >&2
  exit 1
fi

if [ "${SKIP_BUILD:-}" = "1" ]; then
  echo "smoke: SKIP_BUILD=1, crawling the existing dist/"
  [ -d dist ] || { echo "smoke: no dist/ to crawl" >&2; exit 1; }
else
  echo "smoke: building site"
  npm run build
fi

echo "smoke: serving dist/ on ${BASE}"
./node_modules/.bin/astro preview --port "$PORT" >/dev/null 2>&1 &
SERVER_PID=$!

npx --yes wait-on "$BASE" --timeout 60000

echo "smoke: crawling for broken links"
npx --yes linkinator "$BASE" \
  --recurse \
  --skip "^(?!${BASE})"
