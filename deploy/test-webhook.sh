#!/bin/sh
# Send a correctly signed GitHub-style push event, like GitHub does.
#   ./test-webhook.sh                                  # local stack (uses local.env)
#   ./test-webhook.sh https://kandepet.com "$SECRET"   # production
set -eu
URL="${1:-http://localhost:8080}"
SECRET="${2:-local-webhook-secret}"
BRANCH="${3:-main}"
BODY="{\"ref\":\"refs/heads/$BRANCH\"}"
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}')
curl -sS -X POST "$URL/_deploy" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -d "$BODY"
