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
info "Cloning $TEMPLATE_REPO..."
git clone --depth 1 "$TEMPLATE_REPO" "$TMP_DIR" &>/dev/null

# 2. Copy over the core, non-conflicting files
# TESTED, WORKING
#info "Copying Sphinx files and GitHub workflow..."
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

# 5. optional user input to replace project, project_page, github_url, html_theme_options
# TESTED, WORKING
#ask "Update project-specific variables in conf.py? (y/n)"
#read -r response
#if [[ "$response" =~ ^[Yy]$ ]]; then
#  read -p "Enter name of project (e.g. 'WordPress charm'): " project_name
#  info "Updating variable 'project'..."
#  PROJECT_OG='project = "Documentation starter pack"'
#  PROJECT_NEW='project = "'$project_name'"'
#  sed -i "s/$PROJECT_OG/$PROJECT_NEW/g" "docs/conf.py"
#  success "'project' updated."

#  read -p "Enter name of product_page (e.g. 'charmhub.io/wordpress-k8s'): " product_page
#  info "Updating variable 'product_page'..."
#  PRODUCT_PAGE_OG='"product_page": "documentation.ubuntu.com",'
#  PRODUCT_PAGE_NEW='"product_page": "'$product_page'",'
#  sed -i "s=$PRODUCT_PAGE_OG=$PRODUCT_PAGE_NEW=g" "docs/conf.py"
#  success "'product_page' updated."

#  read -p "Enter name of github_url (e.g. 'https://github.com/canonical/wordpress-k8s-operator'): " github_url
#  info "Updating variable 'github_url'..."
#  GITHUB_URL_OG='"github_url": "https://github.com/canonical/sphinx-docs-starter-pack",'
#  GITHUB_URL_NEW='"github_url": "'$github_url'",'
#  sed -i "s=$GITHUB_URL_OG=$GITHUB_URL_NEW=g" "docs/conf.py"
#  info "Enabling edit button and updating 'source_edit_link'..."
#  HTML_THEME_OPTION_OG='# html_theme_options = {'
#  HTML_THEME_OPTION_NEW='html_theme_options = {'
#  sed -i "s/$HTML_THEME_OPTION_OG/$HTML_THEME_OPTION_NEW/g" "docs/conf.py"
#  SOURCE_EDIT_LINK_OG="# 'source_edit_link': 'https://github.com/canonical/sphinx-docs-starter-pack',"
#  SOURCE_EDIT_LINK_NEW='"source_edit_link": "'$github_url'",'
#  sed -i "s=$SOURCE_EDIT_LINK_OG=$SOURCE_EDIT_LINK_NEW=g" "docs/conf.py"
#  CLOSING_BRACKET_OG='# }'
#  CLOSING_BRACKET_NEW='}'
#  sed -i "s=$CLOSING_BRACKET_OG=$CLOSING_BRACKET_NEW=g" "docs/conf.py"
#  success "'github_url' and 'source_edit_link' updated."
#fi

# 6. Add Mermaid extension to project
# TESTED, WORKING
#info "Adding Mermaid extension to project..."
#echo -e "sphinxcontrib-mermaid" >> "docs/requirements.txt"
#sed -i '/extensions = \[/a \    "sphinxcontrib.mermaid",' "docs/conf.py"
#success "Added Mermaid extension to conf.py and requirements.txt"

# 7. Add index.md files in all subdirectories
# TESTED, WORKING
#info "Checking for index.md files in all subdirectories..."
# 7a. Get a list of all subdirectories
#subdirectories=$(find "docs/" -mindepth 1 -type d)
# 7b. Check whether index.md file already exists
# 7b-1. If file exists, then skip
# 7b-2. If no file, then create one 
# 7c. Add metadescriptions to these files (fill in the details later)
#for subdir in $subdirectories; do
#    if [ ! -f "$subdir/index.md" ]; then
#      info "No index.md file found in $subdir. Create one? (y/n)"
#      read -r response
#      if [[ "$response" =~ ^[Yy]$ ]]; then
#        info "Creating index.md in $subdir..."
#        files=$(ls -p "$subdir")
#        touch "$subdir/index.md"
#text="---
#myst:
#  html_meta:
#    \"description lang=en\": \"TBD\"
#---
#
#($subdir\_index)=
#
#Description TBD
#
#\`\`\`{toctree}
#$files
#\`\`\`"
#        echo "$text" > "$subdir/index.md"
#        success "Created index.md file in $subdir. Remember to fill in the meta-description!!"
#      else
#        success "Checked for index.md file in $subdir. Remember to create this file later!!"
#      fi
#    fi
#done

# 8. refactor index.md overview page Contents -> toctree


# 9. RTD cookie banner
# 10. Add target headers to all files??
# 11. Add intersphinx mapping for Juju docs into conf.py

# 10. Final cleanup and instructions
info "Cleaning up temporary files..."
rm -rf "$TMP_DIR"

#success "RTD project has been set up!"
#echo "Please review the changes with 'make run' and run 'git add .' to commit them."