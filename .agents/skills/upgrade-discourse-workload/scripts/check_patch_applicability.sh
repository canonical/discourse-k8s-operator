#!/usr/bin/env bash
# check_patch_applicability.sh
#
# Clones Discourse at a specific tag (shallow) into a unique temporary
# workspace outside the repository, attempts to apply each patch from
# discourse_rock/patches/, and reports which ones need updating.
#
# Usage:
#   bash check_patch_applicability.sh <discourse-tag> [patches-dir]
#
# Example:
#   bash check_patch_applicability.sh v2026.1.4
#   bash check_patch_applicability.sh v2026.1.4 discourse_rock/patches
#
# Requirements: git, curl
# Must be run from the discourse-k8s-operator repo root (or provide patches-dir).

set -euo pipefail

TAG="${1:-}"
# Default: look for patches relative to cwd (expected to be repo root)
PATCHES_DIR="${2:-discourse_rock/patches}"

if [[ -z "$TAG" ]]; then
  echo "Usage: $0 <discourse-tag> [patches-dir]" >&2
  exit 1
fi

if [[ ! -d "$PATCHES_DIR" ]]; then
  echo "ERROR: patches directory not found: $PATCHES_DIR" >&2
  echo "  Run from the discourse-k8s-operator repo root, or pass the path as second argument." >&2
  exit 1
fi

TMP_ROOT="${TMPDIR:-/tmp}"
TMPDIR_BASE=$(mktemp -d "${TMP_ROOT%/}/upgrade-discourse-workload.XXXXXX")
CLONE_DIR="${TMPDIR_BASE}/discourse"
trap 'rm -rf "$TMPDIR_BASE"' EXIT

echo "=== Patch Applicability Check for Discourse ${TAG} ==="
echo ""
echo "Temporary workspace: ${TMPDIR_BASE}"
echo "Cloning discourse at ${TAG} (shallow)..."
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "${TAG}" https://github.com/discourse/discourse.git "$CLONE_DIR" 2>&1 \
  || { echo "ERROR: Failed to clone discourse at tag ${TAG}" >&2; exit 1; }
echo "Clone complete."
echo ""

# Initialise a bare git repo so 'git apply' works
cd "$CLONE_DIR"
git config user.email "ci@example.com"
git config user.name "CI"

PASS=()
FAIL=()
NEED_LINE_UPDATE=()

check_new_file_patch_format() {
  local patch_file="$1"

  if ! grep -Eq '^@@ -0,0 \+[0-9]+,[0-9]+ @@' "$patch_file"; then
    return 0
  fi

  if ! grep -Eq '^diff --git a/.+ b/.+' "$patch_file"; then
    echo "missing diff --git header"
    return 1
  fi

  if ! grep -Fxq -- '--- /dev/null' "$patch_file"; then
    echo "missing --- /dev/null header"
    return 1
  fi
}

for PATCH_FILE in "${OLDPWD}/${PATCHES_DIR}"/*.patch; do
  PATCH_NAME=$(basename "$PATCH_FILE")
  echo -n "  Applying ${PATCH_NAME} ... "

  MALFORMED_REASON=""
  if ! MALFORMED_REASON=$(check_new_file_patch_format "$PATCH_FILE"); then
    echo "❌ MALFORMED NEW-FILE FORMAT (${MALFORMED_REASON}) — rock build will fail"
    FAIL+=("$PATCH_NAME")
    continue
  fi

  # Try applying (check-only, no actual change)
  if git apply --check "$PATCH_FILE" 2>/dev/null; then
    echo "✅ APPLIES CLEANLY"
    PASS+=("$PATCH_NAME")
    # Also apply so subsequent patches work correctly
    git apply "$PATCH_FILE" 2>/dev/null || true
  else
    # Try with --ignore-whitespace
    if git apply --check --ignore-whitespace "$PATCH_FILE" 2>/dev/null; then
      echo "⚠️  APPLIES WITH --ignore-whitespace (whitespace changes only)"
      NEED_LINE_UPDATE+=("$PATCH_NAME")
      git apply --ignore-whitespace "$PATCH_FILE" 2>/dev/null || true
    else
      # Try with fuzz
      if git apply --check --3way "$PATCH_FILE" 2>/dev/null; then
        echo "⚠️  APPLIES WITH --3way (conflicts may exist)"
        NEED_LINE_UPDATE+=("$PATCH_NAME")
      else
        echo "❌ FAILS"
        FAIL+=("$PATCH_NAME")
        # Show what went wrong
        echo "    Details:"
        git apply --check "$PATCH_FILE" 2>&1 | sed 's/^/      /' || true
        echo ""
      fi
    fi
  fi
done

echo ""
echo "=== Summary ==="
echo ""
if [[ ${#PASS[@]} -gt 0 ]]; then
  echo "✅ Patches that apply cleanly (${#PASS[@]}):"
  for p in "${PASS[@]}"; do echo "   - $p"; done
fi
if [[ ${#NEED_LINE_UPDATE[@]} -gt 0 ]]; then
  echo ""
  echo "⚠️  Patches needing minor updates (${#NEED_LINE_UPDATE[@]}):"
  for p in "${NEED_LINE_UPDATE[@]}"; do echo "   - $p"; done
  echo "   → Usually line-number offsets in the patch header. Update with regenerate_patch.sh."
fi
if [[ ${#FAIL[@]} -gt 0 ]]; then
  echo ""
  echo "❌ Patches that FAIL (${#FAIL[@]}) — require manual regeneration:"
  for p in "${FAIL[@]}"; do echo "   - $p"; done
  echo ""
  echo "   For each failing patch:"
  echo "   1. Read the patch to understand what change it makes"
  echo "   2. Find the same lines in the new Discourse source"
  echo "   3. Run: bash scripts/regenerate_patch.sh ${TAG} <patch-name>"
  echo "   NOTE: For discourse-charm.patch (creates a new file), regenerate with:"
  echo "         git add <file> && git diff --cached > new.patch  (NOT git diff)"
fi

echo ""
echo "=== Next step ==="
if [[ ${#FAIL[@]} -gt 0 ]]; then
  echo "  ❌ Manual patch regeneration required. See references/guide-patches.md."
  exit 2
elif [[ ${#NEED_LINE_UPDATE[@]} -gt 0 ]]; then
  echo "  ⚠️  Line-offset updates needed. Run regenerate_patch.sh for each flagged patch."
  exit 1
else
  echo "  ✅ All patches apply cleanly! No patch updates needed."
  exit 0
fi
