#!/bin/sh
set -eu
: "${REPO_URL:?REPO_URL must be set}"
: "${WEBHOOK_SECRET:?WEBHOOK_SECRET must be set}"

# Build once at startup so a fresh server serves the site before the first push.
/app/build.sh || echo "initial build failed; the previous release (if any) keeps serving" >&2

exec webhook -hooks /app/hooks.json -template -port 9000 -urlprefix hooks
