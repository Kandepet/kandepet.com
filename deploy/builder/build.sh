#!/bin/bash
# Pull the repo and build the Hugo site into a new release directory, then
# atomically point /srv/site/current at it. A failed build leaves the
# previous release serving.
set -euo pipefail

REPO=/srv/repo
SITE=/srv/site
BRANCH="${GIT_BRANCH:-main}"
KEEP="${KEEP_RELEASES:-5}"

log() { echo "[build $(date -u +%FT%TZ)] $*"; }

# Serialize builds: a push during a build waits, then builds the newest commit.
exec 9>/tmp/build.lock
flock 9

if [ ! -d "$REPO/.git" ]; then
  log "cloning $REPO_URL ($BRANCH)"
  git clone --quiet --depth 1 --branch "$BRANCH" --recurse-submodules --shallow-submodules "$REPO_URL" "$REPO"
else
  git -C "$REPO" fetch --quiet --depth 1 origin "$BRANCH"
  git -C "$REPO" reset --quiet --hard FETCH_HEAD
  git -C "$REPO" clean --quiet -ffdx
  git -C "$REPO" submodule --quiet sync --recursive
  git -C "$REPO" submodule --quiet update --init --recursive --depth 1
fi

rev="$(git -C "$REPO" rev-parse --short HEAD)"
release="$(date -u +%Y%m%d-%H%M%S)-$rev"
mkdir -p "$SITE/releases"

log "building $rev"
hugo --source "$REPO/site" --destination "$SITE/releases/$release" \
     --environment "${HUGO_ENV:-production}" --minify --cleanDestinationDir --logLevel warn

ln -sfn "releases/$release" "$SITE/.current.tmp"
mv -Tf "$SITE/.current.tmp" "$SITE/current"
log "live: $release"

# Keep the newest $KEEP releases for rollback.
ls -1dt "$SITE"/releases/*/ | tail -n +"$((KEEP + 1))" | xargs -r rm -rf --
