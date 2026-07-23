#!/usr/bin/env bash
set -euo pipefail

: "${CLOUDFLARE_API_TOKEN:?Set CLOUDFLARE_API_TOKEN in the environment.}"
: "${CLOUDFLARE_ACCOUNT_ID:?Set CLOUDFLARE_ACCOUNT_ID in the environment.}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHOWCASE="$ROOT/showcase"
DEPLOY_LOG="$(mktemp -t look-twice-cloudflare.XXXXXX)"
trap 'rm -f "$DEPLOY_LOG"' EXIT

cd "$SHOWCASE"
npm run build
./node_modules/.bin/wrangler deploy \
  --config dist/server/wrangler.json | tee "$DEPLOY_LOG"

PUBLIC_URL="$(
  grep -Eo 'https://[A-Za-z0-9.-]+\\.workers\\.dev' "$DEPLOY_LOG" | tail -1
)"
if [[ -z "$PUBLIC_URL" ]]; then
  echo "Deployment completed but no workers.dev URL was found in Wrangler output." >&2
  exit 1
fi

cd "$ROOT"
python3 scripts/finalize_public_release.py \
  --docker-verified \
  --browser-verified \
  --public-url "$PUBLIC_URL"
