#!/usr/bin/env bash
set -euo pipefail

# pull-preserve.sh
# Safely fetch and reset to origin/<branch> while preserving specific local files.
# Usage: ./scripts/pull-preserve.sh [branch]

BRANCH="${1:-main}"
FILES=("server/db.json" "server/server.log")

TMPDIR="$(mktemp -d /tmp/pull-preserve.XXXXXX)"
trap 'rm -rf "${TMPDIR}"' EXIT

echo "[pull-preserve] Saving files to ${TMPDIR}"
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    cp -- "$f" "${TMPDIR}/$(basename "$f").bak"
  else
    # create empty placeholder so restore step is safe
    : > "${TMPDIR}/$(basename "$f").bak"
  fi
done

echo "[pull-preserve] Fetching origin and resetting to origin/${BRANCH}"
git fetch origin
git reset --hard "origin/${BRANCH}"

echo "[pull-preserve] Restoring preserved files"
for f in "${FILES[@]}"; do
  cp -- "${TMPDIR}/$(basename "$f").bak" "$f"
done

echo "[pull-preserve] Done. Your preserved files have been restored."
