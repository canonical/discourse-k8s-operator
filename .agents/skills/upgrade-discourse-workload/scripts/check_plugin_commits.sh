#!/usr/bin/env bash
# check_plugin_commits.sh
#
# For each plugin in discourse_rock/rockcraft.yaml, determines the correct
# source-commit to use for the target Discourse version.
#
# Uses the official .discourse-compatibility file mechanism when available:
#   https://meta.discourse.org/t/156971
#
# File format:
#   < VERSION: COMMIT  (newer format) — use COMMIT if Discourse < VERSION
#   VERSION: COMMIT    (legacy format) — use COMMIT if Discourse >= VERSION
#
# Falls back to "latest commit on default branch" with a warning when the
# plugin has no .discourse-compatibility file.
#
# Usage:
#   bash check_plugin_commits.sh <discourse-tag> [rockcraft-yaml]
#
# Example:
#   bash check_plugin_commits.sh v2026.1.4
#   bash check_plugin_commits.sh v2026.1.4 discourse_rock/rockcraft.yaml
#
# Requirements: gh CLI (authenticated), python3

set -euo pipefail

TAG="${1:-}"
ROCKCRAFT="${2:-discourse_rock/rockcraft.yaml}"

if [[ -z "$TAG" ]]; then
  echo "Usage: $0 <discourse-tag> [rockcraft-yaml]" >&2
  exit 1
fi

if [[ ! -f "$ROCKCRAFT" ]]; then
  echo "ERROR: $ROCKCRAFT not found. Run from the discourse-k8s-operator repo root." >&2
  exit 1
fi

echo "=== Plugin Commit Checker for Discourse ${TAG} ==="
echo ""

# Python helper: resolve correct commit from .discourse-compatibility content
# Usage: resolve_compat <discourse_version> <compat_file_content>
# Prints the commit hash or "HEAD" if no entry matches
RESOLVE_COMPAT_PY='
import sys
import re

def parse_version(v):
    """
    Parse version string into a comparable tuple.
    Handles calendar (2026.1.4, 2026.2.0-latest) and semver (3.6.0.beta1-dev).
    Calendar versions (major >= 100) always sort higher than semver (major < 100).
    Pre-release/channel suffixes are stripped for numeric comparison.
    """
    v = v.strip().lstrip("v<").strip()
    # Extract only leading numeric components separated by "."
    parts = re.split(r"[.\-]", v)
    nums = []
    for p in parts:
        if re.match(r"^\d+$", p):
            nums.append(int(p))
        else:
            break  # stop at first non-numeric part (beta, dev, latest, etc.)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

discourse_ver = parse_version(sys.argv[1])
compat_content = sys.stdin.read()

# Parse entries: each line is either "< VERSION: COMMIT" or "VERSION: COMMIT"
entries = []
for line in compat_content.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    m = re.match(r"^(<\s*)?([^:]+):\s*([a-f0-9]{7,40}|[^\s]+)\s*$", line)
    if not m:
        continue
    lt_prefix = bool(m.group(1))
    key_ver = parse_version(m.group(2))
    commit = m.group(3).strip()
    entries.append((lt_prefix, key_ver, m.group(2).strip(), commit))

if not entries:
    print("HEAD")
    sys.exit(0)

# Determine format: if any entry has "<" prefix, use new format; else legacy
has_lt = any(e[0] for e in entries)

if has_lt:
    # New format: "< VERSION: COMMIT" — file sorted descending (newer first)
    # Find FIRST entry where discourse_ver < key_ver
    for lt_prefix, key_ver, key_str, commit in entries:
        if lt_prefix and discourse_ver < key_ver:
            print(commit)
            sys.exit(0)
    # No match → discourse is newer than all entries → use HEAD
    print("HEAD")
else:
    # Legacy format: "VERSION: COMMIT" — file sorted descending
    # Find the SMALLEST key_ver that is >= discourse_ver (i.e., last match scanning top-down)
    # Equivalent: scan from bottom to top and take last entry where key_ver >= discourse_ver
    best = None
    for lt_prefix, key_ver, key_str, commit in reversed(entries):
        if key_ver >= discourse_ver:
            best = commit
    if best:
        print(best)
    else:
        print("HEAD")
'

# Parse plugin repos from rockcraft.yaml
PLUGINS=$(python3 - "$ROCKCRAFT" <<'PYEOF'
import sys, re

with open(sys.argv[1]) as f:
    content = f.read()

plugin_pattern = re.compile(
    r"^  (discourse-[a-zA-Z0-9-]+):\n.*?source: (https://github\.com/[^\n]+\.git)\n.*?source-commit: ([a-f0-9]+)",
    re.MULTILINE | re.DOTALL,
)

for m in plugin_pattern.finditer(content):
    name = m.group(1)
    url = m.group(2).rstrip("/")
    current = m.group(3)
    repo = url.replace("https://github.com/", "").replace(".git", "")
    print(f"{name}\t{repo}\t{current}")
PYEOF
)

if [[ -z "$PLUGINS" ]]; then
  echo "No plugins with source-commit found in ${ROCKCRAFT}." >&2
  exit 1
fi

echo "--- Checking plugins ---"
echo ""

UPDATES_NEEDED=()
WARNINGS=()

while IFS=$'\t' read -r PLUGIN_NAME REPO CURRENT_COMMIT; do
  echo -n "  ${PLUGIN_NAME} (${REPO}) ... "

  # Try fetching .discourse-compatibility from the plugin repo
  COMPAT_CONTENT=$(curl -fsL "https://raw.githubusercontent.com/${REPO}/main/.discourse-compatibility" 2>/dev/null || true)

  if [[ -n "$COMPAT_CONTENT" ]]; then
    METHOD="via .discourse-compatibility"
    TARGET_COMMIT=$(echo "$COMPAT_CONTENT" | python3 -c "$RESOLVE_COMPAT_PY" "${TAG}" 2>/dev/null || echo "HEAD")

    if [[ "$TARGET_COMMIT" == "HEAD" ]]; then
      # No pinned entry — use latest commit on default branch
      TARGET_COMMIT=$(gh api "repos/${REPO}/commits?per_page=1" --jq '.[0].sha' 2>/dev/null || true)
      METHOD="via .discourse-compatibility (no pin for ${TAG} → HEAD)"
    fi
  else
    # No .discourse-compatibility file — fallback to latest commit with warning
    METHOD="⚠️  FALLBACK (no .discourse-compatibility file)"
    TARGET_COMMIT=$(gh api "repos/${REPO}/commits?per_page=1" --jq '.[0].sha' 2>/dev/null || true)
    WARNINGS+=("${PLUGIN_NAME}: no .discourse-compatibility — used latest commit; verify manually")
  fi

  if [[ -z "$TARGET_COMMIT" ]]; then
    echo "❓ could not determine target commit"
    WARNINGS+=("${PLUGIN_NAME}: API call failed, could not fetch commits")
    continue
  fi

  if [[ "$TARGET_COMMIT" == "$CURRENT_COMMIT"* ]] || [[ "$CURRENT_COMMIT" == "$TARGET_COMMIT"* ]]; then
    echo "✅ up to date (${CURRENT_COMMIT:0:12})  [${METHOD}]"
  else
    echo "🔄 UPDATE AVAILABLE  [${METHOD}]"
    echo "    Current: ${CURRENT_COMMIT}"
    echo "    Target:  ${TARGET_COMMIT}"
    UPDATES_NEEDED+=("${PLUGIN_NAME}: ${CURRENT_COMMIT} → ${TARGET_COMMIT}")
  fi
done <<< "$PLUGINS"

echo ""
echo "=== Summary ==="

if [[ ${#UPDATES_NEEDED[@]} -eq 0 ]]; then
  echo "  ✅ All plugins are at the correct commit for Discourse ${TAG}"
else
  echo "  🔄 ${#UPDATES_NEEDED[@]} plugin(s) need updating:"
  for u in "${UPDATES_NEEDED[@]}"; do
    echo "     - $u"
  done
  echo ""
  echo "  Update source-commit for each plugin in ${ROCKCRAFT}"
fi

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
  echo ""
  echo "  ⚠️  Warnings (manual verification needed):"
  for w in "${WARNINGS[@]}"; do
    echo "     - $w"
  done
fi

