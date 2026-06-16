#!/usr/bin/env bash
# regenerate_patch.sh
#
# Helps regenerate a specific patch file for a new Discourse version.
# Clones discourse at the target tag into a unique temporary workspace outside
# the repository, applies all patches except the one being regenerated, then
# guides the user through creating the new patch.
#
# Usage:
#   bash regenerate_patch.sh <discourse-tag> <patch-name>
#
# Example:
#   bash regenerate_patch.sh v2026.1.4 lp1903695
#   bash regenerate_patch.sh v2026.1.4 db_migrations
#   bash regenerate_patch.sh v2026.1.4 sigterm
#   bash regenerate_patch.sh v2026.1.4 discourse-charm
#
# The script will:
#   1. Clone discourse at the tag
#   2. Show the current patch content
#   3. Show the current state of the target file(s)
#   4. Output the exact git diff command to run after manual editing

set -euo pipefail

TAG="${1:-}"
PATCH_NAME="${2:-}"
PATCHES_DIR="${3:-discourse_rock/patches}"

if [[ -z "$TAG" || -z "$PATCH_NAME" ]]; then
  echo "Usage: $0 <discourse-tag> <patch-name> [patches-dir]" >&2
  echo ""
  echo "Available patches (run from repo root):"
  ls discourse_rock/patches/*.patch 2>/dev/null | xargs -I{} basename {} .patch || true
  exit 1
fi

# Normalize patch name (strip .patch if provided)
PATCH_NAME="${PATCH_NAME%.patch}"
PATCH_FILE="${PATCHES_DIR}/${PATCH_NAME}.patch"

if [[ ! -f "$PATCH_FILE" ]]; then
  echo "ERROR: Patch file not found: ${PATCH_FILE}" >&2
  exit 1
fi

TMP_ROOT="${TMPDIR:-/tmp}"
TMPDIR_BASE=$(mktemp -d "${TMP_ROOT%/}/upgrade-discourse-workload.XXXXXX")
CLONE_DIR="${TMPDIR_BASE}/discourse"
PATCH_OUTPUT="${TMPDIR_BASE}/${PATCH_NAME}_new.patch"
trap 'rm -rf "$TMPDIR_BASE"' EXIT

echo "=== Patch Regeneration: ${PATCH_NAME}.patch for Discourse ${TAG} ==="
echo ""
echo "Temporary workspace: ${TMPDIR_BASE}"
echo ""

echo "--- Current patch content ---"
cat "$PATCH_FILE"
echo ""

echo "Cloning Discourse at ${TAG}..."
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "${TAG}" https://github.com/discourse/discourse.git "$CLONE_DIR"
echo "Clone complete."
echo ""

cd "$CLONE_DIR"
git config user.email "ci@example.com"
git config user.name "CI"

# Extract target files from patch
TARGET_FILES=$(grep -oP "(?<=--- a/).*" "$OLDPWD/$PATCH_FILE" || grep -oP "(?<=\+\+\+ b/).*" "$OLDPWD/$PATCH_FILE" || true)

echo "--- Target file(s) in patch ---"
echo "$TARGET_FILES" | sed 's/^/  /'
echo ""

# Show current content of target files
for FILE in $TARGET_FILES; do
  if [[ -f "$FILE" ]]; then
    echo "--- Current content of ${FILE} (showing relevant lines) ---"
    # Show first 50 lines for context
    head -80 "$FILE" | cat
    echo "..."
    echo ""
  else
    echo "WARNING: File ${FILE} does not exist in Discourse ${TAG}" >&2
  fi
done

# Try applying the patch and see what fails
echo "--- Attempting to apply ${PATCH_NAME}.patch ---"
if git apply --check "$OLDPWD/$PATCH_FILE" 2>&1; then
  echo "✅ Patch applies cleanly!"
  echo ""
  echo "The patch content is correct. You may only need to update the index hash."
  echo ""
  echo "To update the patch header (index hash), apply then capture:"
  echo "  git apply '$OLDPWD/$PATCH_FILE'"

  # Apply the patch and show the resulting diff
  git apply "$OLDPWD/$PATCH_FILE" 2>/dev/null
  echo ""
  echo "--- Regenerated patch (copy this to ${PATCH_FILE}) ---"
  git diff HEAD | cat
else
  echo "❌ Patch does not apply cleanly. Manual regeneration needed."
  echo ""
  echo "=== Manual regeneration steps ==="
  echo ""
  echo "1. The clone is at: ${CLONE_DIR}"
  echo "   (This is a unique temp workspace outside the repo; it will be deleted when this script exits)"
  echo ""
  echo "2. Open the target file(s) and apply the same change manually:"
  for FILE in $TARGET_FILES; do
    echo "   - ${CLONE_DIR}/${FILE}"
  done
  echo ""
  echo "3. After editing, run in ${CLONE_DIR}:"
  echo "   git diff > '${PATCH_OUTPUT}'"
  echo ""
  echo "4. Review ${PATCH_OUTPUT} and copy to ${PATCHES_DIR}/${PATCH_NAME}.patch"
  echo ""
  echo "=== What the patch does (from the diff) ==="
  grep "^+" "$OLDPWD/$PATCH_FILE" | grep -v "^+++" | head -20 | sed 's/^+/  + /'
  echo ""
  echo "⚠️  This script is keeping the clone alive. Open a new terminal to edit the files."
  echo "Press ENTER when done (or Ctrl+C to abort without saving)..."
  read -r

  if git diff --quiet; then
    echo "No changes detected. Exiting without updating patch." >&2
    exit 1
  fi

  NEW_PATCH=$(git diff HEAD)
  echo ""
  echo "--- New patch content ---"
  echo "$NEW_PATCH"
  echo ""
  echo "Save this to ${PATCHES_DIR}/${PATCH_NAME}.patch? [y/N]"
  read -r CONFIRM
  if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    cd "$OLDPWD"
    echo "$NEW_PATCH" > "${PATCHES_DIR}/${PATCH_NAME}.patch"
    echo "✅ Saved to ${PATCHES_DIR}/${PATCH_NAME}.patch"
  fi
fi
