#!/usr/bin/env bash
# find_db_migration_target.sh
#
# Finds the appropriate post_migrate file to target for db_migrations.patch
# in a new Discourse version. The db_migrations.patch must target the EARLIEST
# (lowest timestamp) post_migrate file present in the new version that is NOT
# in the previous version — so the SQL trigger drops run before any column drops.
#
# If no new migration exists, it reports which is the best existing candidate.
#
# Usage:
#   bash find_db_migration_target.sh <new-tag> [old-tag]
#
# Example:
#   bash find_db_migration_target.sh v2026.1.4 v2025.12.0-latest
#
# Output:
#   Prints the recommended migration file name and the current db_migrations.patch target.

set -euo pipefail

NEW_TAG="${1:-}"
OLD_TAG="${2:-}"

if [[ -z "$NEW_TAG" ]]; then
  echo "Usage: $0 <new-discourse-tag> [old-discourse-tag]" >&2
  exit 1
fi

TMPDIR_BASE=$(mktemp -d)
trap 'rm -rf "$TMPDIR_BASE"' EXIT

echo "=== DB Migration Target Finder ==="
echo "  New Discourse tag: ${NEW_TAG}"
[[ -n "$OLD_TAG" ]] && echo "  Old Discourse tag: ${OLD_TAG}"
echo ""

echo "Fetching post_migrate file list for ${NEW_TAG}..."
NEW_MIGRATIONS=$(gh api "repos/discourse/discourse/git/trees/${NEW_TAG}?recursive=1" \
  --jq '.tree[] | select(.path | startswith("db/post_migrate/")) | .path' 2>/dev/null \
  | sort)

if [[ -z "$NEW_MIGRATIONS" ]]; then
  echo "ERROR: Could not fetch migration list for ${NEW_TAG}. Check the tag is correct." >&2
  exit 1
fi

if [[ -n "$OLD_TAG" ]]; then
  echo "Fetching post_migrate file list for ${OLD_TAG}..."
  OLD_MIGRATIONS=$(gh api "repos/discourse/discourse/git/trees/${OLD_TAG}?recursive=1" \
    --jq '.tree[] | select(.path | startswith("db/post_migrate/")) | .path' 2>/dev/null \
    | sort)

  echo ""
  echo "--- New migrations added in ${NEW_TAG} (not in ${OLD_TAG}) ---"
  NEW_ONLY=$(comm -23 <(echo "$NEW_MIGRATIONS") <(echo "$OLD_MIGRATIONS") || true)
  if [[ -n "$NEW_ONLY" ]]; then
    while IFS= read -r line; do echo "  $line"; done <<< "$NEW_ONLY"
    FIRST_NEW=$(echo "$NEW_ONLY" | head -1)
    echo ""
    echo "  ➜ Earliest new migration: ${FIRST_NEW}"
  else
    echo "  (No new post_migrate files added)"
    FIRST_NEW=""
  fi
else
  echo ""
  FIRST_NEW=""
fi

echo ""
echo "--- All post_migrate files in ${NEW_TAG} (last 10) ---"
echo "$NEW_MIGRATIONS" | tail -10 | sed 's/^/  /'
LATEST_EXISTING=$(echo "$NEW_MIGRATIONS" | tail -1)
echo ""
echo "  ➜ Latest overall migration: ${LATEST_EXISTING}"

echo ""
echo "=== Current db_migrations.patch target ==="
PATCHES_DIR="discourse_rock/patches/db_migrations.patch"
if [[ -f "$PATCHES_DIR" ]]; then
  CURRENT_TARGET=$(grep -oP "(?<=db/post_migrate/)[a-z0-9_]+" "$PATCHES_DIR" | head -1 || true)
  echo "  Current target file: db/post_migrate/${CURRENT_TARGET}.rb"
else
  echo "  (discourse_rock/patches/db_migrations.patch not found - run from repo root)"
fi

echo ""
echo "=== Recommendation ==="
if [[ -n "$FIRST_NEW" ]]; then
  FNAME=$(basename "$FIRST_NEW")
  echo "  Use the EARLIEST new migration as target: ${FNAME}"
  echo ""
  echo "  The patch adds DROP TRIGGER statements before the existing migration UP method."
  echo "  Steps:"
  echo "  1. Fetch the file: gh api repos/discourse/discourse/contents/${FIRST_NEW}?ref=${NEW_TAG} --jq '.content' | base64 -d"
  echo "  2. Generate a patch with the DROP TRIGGER SQL added in the def up method"
  echo "  3. Update discourse_rock/patches/db_migrations.patch"
  echo "  4. Update the 'prime' list in apply-patches section of rockcraft.yaml"
elif [[ -n "$LATEST_EXISTING" ]]; then
  FNAME=$(basename "$LATEST_EXISTING")
  echo "  No new migrations found. Re-target to latest migration: ${FNAME}"
  echo "  (Or check if the existing patch target still exists in ${NEW_TAG})"
fi
