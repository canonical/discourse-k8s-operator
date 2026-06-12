#!/usr/bin/env bash
# check_discourse_requirements.sh
#
# Fetches Discourse's runtime requirements (Ruby, Node.js, pnpm/bundler versions)
# for a given tag by reading key files directly from GitHub without cloning.
#
# Usage:
#   bash check_discourse_requirements.sh <discourse-tag>
#
# Example:
#   bash check_discourse_requirements.sh v2026.1.4
#   bash check_discourse_requirements.sh 2026.1.4-latest
#
# Output:
#   Prints required versions and compares with discourse_rock/rockcraft.yaml
#   if run from within the discourse-k8s-operator repo.

set -euo pipefail

TAG="${1:-}"
REPO="discourse/discourse"

if [[ -z "$TAG" ]]; then
  echo "Usage: $0 <discourse-tag>" >&2
  exit 1
fi

# Normalize tag: add 'v' prefix only for semver-style tags (not calendar versioning)
if [[ "$TAG" =~ ^[0-9]{4}\. ]]; then
  GIT_REF="$TAG"
else
  GIT_REF="${TAG#v}"   # strip leading v for raw ref lookups
  GIT_REF="v${GIT_REF}"
fi

echo "=== Discourse Requirements for tag: ${TAG} ==="
echo ""

fetch_raw() {
  local path="$1"
  gh api "repos/${REPO}/contents/${path}?ref=${TAG}" --jq '.content' 2>/dev/null \
    | base64 -d 2>/dev/null || true
}

fetch_raw_url() {
  local path="$1"
  curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TAG}/${path}" 2>/dev/null || true
}

echo "--- Ruby version ---"
RUBY_VERSION=$(fetch_raw_url ".ruby-version" | tr -d '[:space:]')
if [[ -n "$RUBY_VERSION" ]]; then
  echo "  Required Ruby: ${RUBY_VERSION}"
else
  # Fall back to searching Gemfile
  GEMFILE=$(fetch_raw_url "Gemfile" | grep -E "^ruby " | head -1 || true)
  echo "  From Gemfile: ${GEMFILE:-NOT FOUND}"
fi

echo ""
echo "--- Node.js version ---"
NODE_VERSION=$(fetch_raw_url ".node-version" | tr -d '[:space:]')
if [[ -z "$NODE_VERSION" ]]; then
  NODE_VERSION=$(fetch_raw_url ".nvmrc" | tr -d '[:space:]')
fi
if [[ -z "$NODE_VERSION" ]]; then
  # Try reading from discourse's package.json engines field
  PKG=$(fetch_raw_url "package.json")
  NODE_VERSION=$(echo "$PKG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('engines',{}).get('node','NOT FOUND'))" 2>/dev/null || echo "NOT FOUND")
fi
echo "  Required Node.js: ${NODE_VERSION}"

echo ""
echo "--- pnpm version ---"
PNPM_VERSION=""
# Check package.json for packageManager field
PKG=$(fetch_raw_url "package.json")
PNPM_VERSION=$(echo "$PKG" | python3 -c "
import sys, json, re
try:
    d = json.load(sys.stdin)
    pm = d.get('packageManager','')
    if pm.startswith('pnpm@'):
        print(pm.split('@')[1].split('+')[0])
    elif pm.startswith('pnpm'):
        print(pm)
except:
    pass
" 2>/dev/null || true)
if [[ -z "$PNPM_VERSION" ]]; then
  PNPM_VERSION=$(fetch_raw_url ".pnpmfile.cjs" | head -5 || true)
  PNPM_VERSION="NOT FOUND in package.json (check manually)"
fi
echo "  Required pnpm: ${PNPM_VERSION}"

echo ""
echo "--- Bundler version ---"
GEMFILE_LOCK_BUNDLER=$(fetch_raw_url "Gemfile.lock" | grep -A1 "^BUNDLED WITH" | tail -1 | tr -d '[:space:]' || true)
echo "  Bundler (from Gemfile.lock): ${GEMFILE_LOCK_BUNDLER:-NOT FOUND}"

echo ""
echo "=== Current rockcraft.yaml values (if in repo root) ==="
ROCKCRAFT="discourse_rock/rockcraft.yaml"
if [[ -f "$ROCKCRAFT" ]]; then
  echo ""
  grep -E "(NODE_VERSION|RUBY_VERSION|PNPM_VERSION|RUBY_INSTALL_VERSION|bundler)" "$ROCKCRAFT" | sed 's/^/  /'
else
  echo "  (rockcraft.yaml not found - run from discourse-k8s-operator repo root)"
fi

echo ""
echo "=== Plugin compatibility check ==="
echo "  Run check_plugin_commits.sh $TAG to get compatible plugin commits."
