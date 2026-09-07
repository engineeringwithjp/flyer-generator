#!/usr/bin/env bash
# Tag a checkpoint you can roll back to.
#
#   ./scripts/release.sh v0.2.0 "Connector decision engine"
#
# Every phase of this project is tagged, so `git checkout <tag>` returns the
# repository to a known-good state. See docs/VERSIONING.md.
set -euo pipefail

TAG="${1:-}"
MESSAGE="${2:-}"

if [ -z "$TAG" ]; then
  echo "usage: $0 <tag> [message]" >&2
  echo >&2
  echo "existing tags:" >&2
  git tag --sort=-creatordate | head -20 >&2
  exit 1
fi

if ! [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$ ]]; then
  echo "Tag must look like v1.2.3 or v1.2.3-rc1" >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is dirty. Commit or stash first." >&2
  git status --short >&2
  exit 1
fi

echo "Running checks before tagging..."
./scripts/dev.sh check

git tag -a "$TAG" -m "${MESSAGE:-Release $TAG}"
echo
echo "Tagged $TAG. Push it with:"
echo "    git push origin $TAG"
echo
echo "Roll back to it later with:"
echo "    git checkout $TAG"
