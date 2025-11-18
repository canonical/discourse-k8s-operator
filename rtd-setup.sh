#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -xe

# --- Configuration ---
TEMPLATE_REPO="https://github.com/canonical/sphinx-docs-starter-pack.git"
TMP_DIR=$(mktemp -d)

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
info "Copying Sphinx and RTD files..."
mkdir -p docs/.sphinx
cp "$TMP_DIR"/.github/workflows/cla-check.yml .github/workflows/
cp "$TMP_DIR"/.readthedocs.yaml .
cp -r "$TMP_DIR"/docs/.sphinx/* docs/.sphinx/
cp "$TMP_DIR"/docs/.gitignore docs/
cp "$TMP_DIR"/docs/Makefile docs/
cp "$TMP_DIR"/docs/conf.py docs/
cp "$TMP_DIR"/docs/requirements.txt docs/

# 3. GitHub workflows
info "Checking for the RTD-specific workflows..."
if [ -f ".github/workflows/docs_rtd.yaml" ]; then
  success "Found the workflow! No need to do anything!"
else
  info "Did not find the RTD-specific workflows. Copying from operator-workflows..."
  mkdir -p .github/workflows
  text='name: RTD workflows

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  rtd-docs-checks:
    uses: canonical/operator-workflows/.github/workflows/docs_rtd.yaml@main
    secrets: inherit
'
  echo "$text" > ".github/workflows/docs_rtd.yaml"
  success "Created the workflow!"
fi

# 4. Handle custom wordlist migration
if [ -f ".custom_wordlist.txt" ]; then
  info "Found '.custom_wordlist.txt'. Adding to the RTD project..."
  cat ".custom_wordlist.txt" >> "docs/.custom_wordlist.txt"
  ask "Wordlist migrated. Would you like to remove the old '.custom_wordlist.txt' file? (y/n)"
  read -r del_response
  if [[ "$del_response" =~ ^[Yy]$ ]]; then
      rm ".custom_wordlist.txt"
      info "Removed .custom_wordlist.txt."
  fi
fi

# Conditionally copy accept.txt
if [ -f ".vale/styles/config/vocabularies/local/accept.txt" ]; then
    info "Local 'accept.txt' found. Migrating to the RTD project..."
    cat ".vale/styles/config/vocabularies/local/accept.txt" >> "docs/.custom_wordlist.txt"
    success "Wordlist migrated."
fi

# If no custom wordlist in the project, then create blank one
if [ -f ".custom_wordlist.txt" ] && [ -f ".vale/styles/config/vocabularies/local/accept.txt" ]; then
    info "No local wordlist found. Creating a blank one..."
    touch docs/.custom_wordlist.txt
fi

# 5. Update conf.py for links/names
info "Updating conf.py to use team-specific links..."
DISCOURSE_OG_LINK='discourse.ubuntu.com'
DISCOURSE_NEW_LINK='discourse.charmhub.io'
sed -i "s/$DISCOURSE_OG_LINK/$DISCOURSE_NEW_LINK/g" "docs/conf.py"
MM_OG_LINK='https:\/\/chat.canonical.com\/canonical\/channels\/documentation'
MM_NEW_LINK=''
sed -i "s/$MM_OG_LINK/$MM_NEW_LINK/g" "docs/conf.py"
MATRIX_OG_LINK='https://matrix.to/#/#documentation:ubuntu.com'
MATRIX_NEW_LINK='https://matrix.to/#/#charmhub-charmdev:ubuntu.com'
sed -i "s|$MATRIX_OG_LINK|$MATRIX_NEW_LINK|g" "docs/conf.py"
sed -i "/intersphinx\_mapping = {/a \    'juju': \(\"https:\/\/documentation.ubuntu.com\/juju\/3.6\/\", None\)," "docs/conf.py"

# 6. optional user input to replace project, project_page, github_url, html_theme_options
ask "Update project-specific variables in conf.py? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
  read -rp "Enter name of project (e.g. 'WordPress charm'): " project_name
  info "Updating variable 'project'..."
  PROJECT_OG='project = "Documentation starter pack"'
  PROJECT_NEW='project = "'$project_name'"'
  sed -i "s/$PROJECT_OG/$PROJECT_NEW/g" "docs/conf.py"
  success "'project' updated."

  read -rp "Enter name of product_page (e.g. 'charmhub.io/wordpress-k8s'): " product_page
  info "Updating variable 'product_page'..."
  PRODUCT_PAGE_OG='"product_page": "documentation.ubuntu.com",'
  PRODUCT_PAGE_NEW='"product_page": "'$product_page'",'
  sed -i "s=$PRODUCT_PAGE_OG=$PRODUCT_PAGE_NEW=g" "docs/conf.py"
  success "'product_page' updated."

  read -rp "Enter name of github_url (e.g. 'https://github.com/canonical/wordpress-k8s-operator'): " github_url
  info "Updating variable 'github_url'..."
  GITHUB_URL_OG='"github_url": "https://github.com/canonical/sphinx-docs-starter-pack",'
  GITHUB_URL_NEW='"github_url": "'$github_url'",'
  sed -i "s|$GITHUB_URL_OG|$GITHUB_URL_NEW|g" "docs/conf.py"
  info "Enabling edit button and updating 'source_edit_link'..."
  HTML_THEME_OPTION_OG='# html_theme_options = {'
  HTML_THEME_OPTION_NEW='html_theme_options = {'
  sed -i "s/$HTML_THEME_OPTION_OG/$HTML_THEME_OPTION_NEW/g" "docs/conf.py"
  SOURCE_EDIT_LINK_OG="# 'source_edit_link': 'https://github.com/canonical/sphinx-docs-starter-pack',"
  SOURCE_EDIT_LINK_NEW='"source_edit_link": "'$github_url'",'
  sed -i "s=$SOURCE_EDIT_LINK_OG=$SOURCE_EDIT_LINK_NEW=g" "docs/conf.py"
  CLOSING_BRACKET_OG='# }'
  CLOSING_BRACKET_NEW='}'
  sed -i "s=$CLOSING_BRACKET_OG=$CLOSING_BRACKET_NEW=g" "docs/conf.py"
  success "'github_url' and 'source_edit_link' updated."
fi

# 7. Add Mermaid extension to project
info "Adding Mermaid extension to project..."
echo -e "sphinxcontrib-mermaid" >> "docs/requirements.txt"
sed -i '/extensions = \[/a \    "sphinxcontrib.mermaid",' "docs/conf.py"
success "Added Mermaid extension to conf.py and requirements.txt"

# 8. Add initial index.md files in all subdirectories
info "Checking for index.md files in all subdirectories..."
# 8a. Get a list of all subdirectories
# 8b. Check whether index.md file already exists. Create if it doesn't exist.
# 8c. Add metadescriptions to these files (fill in the details later)
dirs=$(find "docs/" -mindepth 1 -type d -not -path "docs/.sphinx" -not -path "docs/.sphinx/*")
printf "%s\n" "$dirs" | while read -r subdir; do
    if [ ! -f "$subdir/index.md" ]; then
      info "No index.md file found in $subdir. Creating one..."

      files=$(ls -p "$subdir")
      stripped_subdir_file=$(echo "$subdir" | cut -c 6-)
      # replace '/' and ' ' and '-' with '_'
      replaced_file="${stripped_subdir_file//[-\/\ ]/_}"
      # create the target
      target="($replaced_file)="

      touch "$subdir/index.md"
text="---
myst:
  html_meta:
    \"description lang=en\": \"TBD\"
---

$target

# $subdir

Description TBD

\`\`\`{toctree}
:maxdepth: 1
$files
\`\`\`"
        echo "$text" > "$subdir/index.md"
        success "Created index.md file in $subdir!"
    fi
done

# 9. refactor index.md overview page 
# 9a. Add metadata description to front
metadata_text='---
myst:
  html_meta:
    "description lang=en": "TBD"
---'
echo -e "$metadata_text" | cat - docs/index.md > temp && mv temp docs/index.md
# 9b. Contents -> toctree
info "Updating the Contents section of the home page..."
contents_line_num=$(awk '/# Contents/{print NR; exit}' docs/index.md)
sed -i "$contents_line_num,$ d" "docs/index.md"
subdirectories=$(find docs/*/index.md)
stripped_subdir=$(echo "$subdirectories" | cut -c 6-)
other_files=$(find docs/*.md -not -wholename 'docs/index.md')
stripped_other_files=$(echo "$other_files" | cut -c 6-)
index_toctree="\`\`\`{toctree}
:hidden:
$stripped_subdir
$stripped_other_files
\`\`\`"
echo "$index_toctree" >> "docs/index.md"
success "Contents section of the home page has been refactored!"

# 10. RTD cookie banner
# 10a. Create directories in project
info "Setting up the analytics banner..."
mkdir -p docs/_static docs/_templates
mkdir -p docs/_static/js
# 10b. Clone the cookie banner repo and copy the files
RTD_COOKIE_REPO="https://github.com/canonical/RTD-cookie-banner-integration.git"
info "Cloning $RTD_COOKIE_REPO..."
mkdir tmp
git clone --depth 1 "$RTD_COOKIE_REPO" tmp
info "Copying files from $RTD_COOKIE_REPO..."
cp tmp/bundle.js docs/_static/js/
cp tmp/cookie-banner.css docs/_static
cp tmp/header.html docs/_templates
cp tmp/footer.html docs/_templates
# 10c. uncomment html_static_path and templates_path in conf.py
info "Updating conf.py to detect the cookie banner..."
HTML_STATIC_OG_LINE='#html_static_path'
HTML_STATIC_NEW_LINE='html_static_path'
sed -i "s/$HTML_STATIC_OG_LINE/$HTML_STATIC_NEW_LINE/g" "docs/conf.py"
TEMPLATES_OG_LINE='#templates_path'
TEMPLATES_NEW_LINE='templates_path'
sed -i "s/$TEMPLATES_OG_LINE/$TEMPLATES_NEW_LINE/g" "docs/conf.py"
# 10d. uncomment and fill html_css_files and html_js_files in conf.py
HTML_CSS_OG_LINE="# html_css_files = \[\]"
HTML_CSS_NEW_LINE="html_css_files = \['cookie-banner.css'\]"
sed -i "s/$HTML_CSS_OG_LINE/$HTML_CSS_NEW_LINE/g" "docs/conf.py"
HTML_JS_OG_LINE="# html_js_files = \[\]"
HTML_JS_NEW_LINE="html_js_files = \['js\/bundle.js'\]"
sed -i "s/$HTML_JS_OG_LINE/$HTML_JS_NEW_LINE/g" "docs/conf.py"
success "RTD banner set up!"

# 11. Add target headers to all files
info "Adding reference targets to all files..."
# 11a. Get list of all the MD files in the project
# 11b. Create the targets in the correct form
docfiles=$(find docs/*.md docs/*/*.md -not -wholename "docs/*/index.md" -not -wholename "docs/index.md")
printf "%s\n" "$docfiles" | while read -r file; do
    # strip docs from the name, strip .md from the end 
    stripped_docs_dir_file=$(echo "$file" | cut -c 6-)
    stripped_filename_file="${stripped_docs_dir_file:0:${#stripped_docs_dir_file}-3}"
    # replace '/' and ' ' and '-' with '_'
    replaced_file="${stripped_filename_file//[-\/\ ]/_}"
    # create the target
    target="($replaced_file)=\n"
    # then add the target to the front of all files
    echo -e "$target" | cat - "$file" > temp && mv temp "$file"
done
success "Added targets to all files!"

# 12. Final cleanup and instructions
info "Cleaning up temporary files..."
rm -rf "$TMP_DIR"
rm -rf tmp

success "RTD project has been set up!"
info "Please review the changes with 'make run' and run 'git add .' to commit them."
info "Here's a list of other things you should do before opening a PR:"
info " [ ] Update Charmhub links to use new targets"
info " [ ] Update the landing pages' titles, descriptions, and SEO metadescriptions"
info " [ ] Replace Charmhub links to other projects with RTD intersphinx links (if applicable)"
info " [ ] Update Mermaid diagrams and admonition blocks"

