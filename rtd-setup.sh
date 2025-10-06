#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
TEMPLATE_REPO="https://github.com/canonical/sphinx-docs-starter-pack.git"
TMP_DIR=$(mktemp -d)

# Markers for the gitignore block
GITIGNORE_START_MARKER="# BEGIN VALE WORKFLOW IGNORE"
GITIGNORE_END_MARKER="# END VALE WORKFLOW IGNORE"

# --- Helper Functions for User-Friendly Output ---
info() { echo -e "\033[34mINFO\033[0m: $1"; }
ask() { echo -e "\033[33mACTION\033[0m: $1"; }
success() { echo -e "\033[32mSUCCESS\033[0m: $1"; }
errmsg() { echo -e "\033[31mERROR\033[0m: $1"; }

# --- Main Script ---

# 0. Pre-flight check for Git branch
info "Checking Git branch..."
# First, check if we are in a git repository.
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    errmsg "This script must be run from within a Git repository."
    exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "main" ]; then
    errmsg "This script should not be run on the 'main' branch."
    echo "Please create and check out a new branch before running (e.g., 'git checkout -b setup-rtd-project')."
    exit 1
fi
success "Running on branch '$CURRENT_BRANCH'. Proceeding..."

# 1. Clone the template
info "Cloning Vale workflow template from $TEMPLATE_REPO..."
git clone --depth 1 "$TEMPLATE_REPO" "$TMP_DIR" &>/dev/null

# 2. Copy over the core, non-conflicting files
# TESTED, WORKING
info "Copying Sphinx files and GitHub workflow..."
#mkdir -p .github/workflows
#mkdir -p docs/.sphinx
#rm "$TMP_DIR"/.github/workflows/test-starter-pack.yml
#cp "$TMP_DIR"/.github/workflows/* .github/workflows/
#cp "$TMP_DIR"/.readthedocs.yaml .
#cp -r "$TMP_DIR"/docs/.sphinx/* docs/.sphinx/
#cp "$TMP_DIR"/docs/.gitignore docs/
#cp "$TMP_DIR"/docs/Makefile docs/
#cp "$TMP_DIR"/docs/conf.py docs/
#cp "$TMP_DIR"/docs/requirements.txt docs/

# 3. Handle custom wordlist migration
# TESTED, WORKING
#if [ -f ".custom_wordlist.txt" ]; then
#  ask "Found '.custom_wordlist.txt'. Do you want to add it to the RTD project? (y/n)"
#  read -r response
#  if [[ "$response" =~ ^[Yy]$ ]]; then
#    info "Migrating words from .custom_wordlist.txt..."
#    cat ".custom_wordlist.txt" >> "docs/.custom_wordlist.txt"
#    ask "Wordlist migrated. Would you like to remove the old '.custom_wordlist.txt' file? (y/n)"
#    read -r del_response
#    if [[ "$del_response" =~ ^[Yy]$ ]]; then
#        rm ".custom_wordlist.txt"
#        info "Removed .custom_wordlist.txt."
#    fi
#  fi
#fi

# Conditionally copy accept.txt
#if [ -f ".vale/styles/config/vocabularies/local/accept.txt" ]; then
#    ask "Local 'accept.txt' found. Do you want to add it to the RTD project? (y/n)"
#    read -r response
#    if [[ "$response" =~ ^[Yy]$ ]]; then
#      info "Migrating words from local accept.txt..."
#      cat ".vale/styles/config/vocabularies/local/accept.txt" >> "docs/.custom_wordlist.txt"
#      info "Wordlist migrated."
#    fi
#fi

# If no custom wordlist in the project, then create blank one
#if [ ! -f ".custom_wordlist.txt" ] || [ ! -f ".vale/styles/config/vocabularies/local/accept.txt" ]; then
#    info "No local wordlist found. Creating a blank one..."
#    touch docs/.custom_wordlist.txt
#fi

# 4. Update conf.py for links/names
#info "Updating conf.py to use team-specific links..."
# TESTED, WORKING
#DISCOURSE_OG_LINK='discourse.ubuntu.com'
#DISCOURSE_NEW_LINK='discourse.charmhub.io'
#sed -i "s/$DISCOURSE_OG_LINK/$DISCOURSE_NEW_LINK/g" "docs/conf.py"
#MM_OG_LINK='https:\/\/chat.canonical.com\/canonical\/channels\/documentation'
#MM_NEW_LINK=''
#sed -i "s/$MM_OG_LINK/$MM_NEW_LINK/g" "docs/conf.py"
#MATRIX_OG_LINK='https:\/\/matrix.to\/#\/#documentation:ubuntu.com'
#MATRIX_NEW_LINK='https:\/\/matrix.to\/#\/#charmhub-charmdev:ubuntu.com'
#sed -i "s/$MATRIX_OG_LINK/$MATRIX_NEW_LINK/g" "docs/conf.py"

# todo: look into getting user input to replace project, project_page, github_url, html_theme_options
# NOT TESTED
#ask "Update project-specific variables in conf.py? (y/n)"
#read -r response
#if [[ "$response" =~ ^[Yy]$ ]]; then
#  ask "Enter name of project (e.g. 'WordPress charm'): "
#  read -r response
#  info "Updating variable 'project'..."
#  #PROJECT_OG='project = "Documentation starter pack"'
#  #PROJECT_NEW='project = "$response"'
#  #sed -i "s/$MM_OG_LINK/$MM_NEW_LINK/g" "docs/conf.py"
#  info "'project' updated."
#fi

# 5. Add Mermaid extension to project

# 6. Add index.md files in all subdirectories
# TESTED, NOT WORKING COMPLETELY
# Issue: extra whitespace in toctree that causes errors in the build
#info "Checking for index.md files in all subdirectories..."
# 6a. Get a list of all subdirectories
#subdirectories=$(find "docs/" -type d -mindepth 1)
# 6b. Check whether index.md file already exists
# 6b-1. If file exists, then skip
# 6b-2. If no file, then create one 
#for subdir in $subdirectories; do
#    if [ ! -f "$subdir/index.md" ]; then
#      info "No index.md file found in $subdir. Create one? (y/n)"
#      read -r response
#      if [[ "$response" =~ ^[Yy]$ ]]; then
#        info "Creating index.md in $subdir..."
#        files=$(ls -p "$subdir")
#        touch "$subdir/index.md"
#        text="# $subdir
#
#        \`\`\`{toctree}
#        $files
#        \`\`\`"
#        echo "$text" > "$subdir/index.md"
#      fi
#    fi
#done

# 7. refactor index.md overview page Contents -> toctree

# 6. Final cleanup and instructions
info "Cleaning up temporary files..."
rm -rf "$TMP_DIR"

#success "Vale workflow has been bootstrapped!"
#echo "Please review the changes and run 'git add .' to commit them."