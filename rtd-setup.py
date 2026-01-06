#!/usr/bin/env python3
"""
Script to set up a Read The Docs (RTD) Sphinx documentation project for a Canonical charm repository.

This script clones a template repository and configures it for the specific project, handling
migration of existing documentation files, adding Mermaid diagram support, cookie banners, and
creating proper index files with MyST Markdown metadata.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import yaml
from pathlib import Path

# Configuration
TEMPLATE_REPO = "https://github.com/canonical/sphinx-docs-starter-pack.git"
RTD_COOKIE_REPO = "https://github.com/canonical/RTD-cookie-banner-integration.git"


def check_git_branch():
    """Check if running in a git repository and not on main branch."""
    print("INFO: Checking Git branch...")
    
    # Check if in a git repository
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError:
        print("ERROR: This script must be run from within a Git repository.")
        sys.exit(1)
    
    # Check current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True
    )
    current_branch = result.stdout.strip()
    
    if current_branch == "main":
        print("ERROR: This script should not be run on the 'main' branch.")
        print("Please create and check out a new branch before running (e.g., 'git checkout -b setup-rtd-project').")
        sys.exit(1)
    
    print(f"SUCCESS: Running on branch '{current_branch}'. Proceeding...")


def clone_template(tmp_dir: Path):
    """Clone the sphinx-docs-starter-pack template."""
    print(f"INFO: Cloning {TEMPLATE_REPO}...")
    subprocess.run(
        ["git", "clone", "--depth", "1", TEMPLATE_REPO, str(tmp_dir)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def copy_sphinx_files(tmp_dir: Path):
    """Copy core Sphinx and RTD files from template."""
    print("INFO: Copying Sphinx and RTD files...")
    
    docs_sphinx = Path("docs/.sphinx")
    docs_sphinx.mkdir(parents=True, exist_ok=True)
    
    # Copy files from template
    github_workflows = Path(".github/workflows")
    github_workflows.mkdir(parents=True, exist_ok=True)
    shutil.copy(tmp_dir / ".github/workflows/cla-check.yml", github_workflows)
    shutil.copy(tmp_dir / ".readthedocs.yaml", ".")
    
    # Copy docs/.sphinx/* contents
    src_sphinx = tmp_dir / "docs/.sphinx"
    for item in src_sphinx.iterdir():
        if item.is_file():
            shutil.copy(item, docs_sphinx)
        elif item.is_dir():
            shutil.copytree(item, docs_sphinx / item.name, dirs_exist_ok=True)
    
    # Copy other docs files
    shutil.copy(tmp_dir / "docs/.gitignore", "docs/")
    shutil.copy(tmp_dir / "docs/Makefile", "docs/")
    shutil.copy(tmp_dir / "docs/conf.py", "docs/")
    shutil.copy(tmp_dir / "docs/requirements.txt", "docs/")


def setup_github_workflows():
    """Check for and create RTD-specific GitHub workflows if needed."""
    print("INFO: Checking for the RTD-specific workflows...")
    
    workflow_file = Path(".github/workflows/docs_rtd.yaml")
    if workflow_file.exists():
        print("SUCCESS: Found the workflow! No need to do anything!")
    else:
        print("INFO: Did not find the RTD-specific workflows. Copying from operator-workflows...")
        workflow_file.parent.mkdir(parents=True, exist_ok=True)
        
        workflow_content = """name: RTD workflows

on:
  pull_request:

jobs:
  rtd-docs-checks:
    uses: canonical/operator-workflows/.github/workflows/docs_rtd.yaml@main
    secrets: inherit
"""
        workflow_file.write_text(workflow_content)
        print("SUCCESS: Created the workflow!")


def migrate_custom_wordlist():
    """Handle custom wordlist migration."""
    custom_wordlist = Path(".custom_wordlist.txt")
    accept_txt = Path(".vale/styles/config/vocabularies/local/accept.txt")
    dest_wordlist = Path("docs/.custom_wordlist.txt")
    
    # Migrate .custom_wordlist.txt
    if custom_wordlist.exists():
        print("INFO: Found '.custom_wordlist.txt'. Adding to the RTD project...")
        content = custom_wordlist.read_text()
        with dest_wordlist.open("a") as f:
            f.write(content)
        
        response = input("ACTION: Wordlist migrated. Would you like to remove the old '.custom_wordlist.txt' file? (y/n) ")
        if re.match(r'^[Yy]$', response):
            custom_wordlist.unlink()
            print("INFO: Removed .custom_wordlist.txt.")
    
    # Migrate accept.txt
    if accept_txt.exists():
        print("INFO: Local 'accept.txt' found. Migrating to the RTD project...")
        content = accept_txt.read_text()
        with dest_wordlist.open("a") as f:
            f.write(content)
        print("SUCCESS: Wordlist migrated.")
    
    # Create blank wordlist if none exists
    if not custom_wordlist.exists() and not accept_txt.exists():
        print("INFO: No local wordlist found. Creating a blank one...")
        dest_wordlist.touch()


def update_conf_py_links():
    """Update conf.py to use team-specific links."""
    print("INFO: Updating conf.py to use team-specific links...")
    
    conf_py = Path("docs/conf.py")
    content = conf_py.read_text()
    
    # Replace Discourse link
    content = content.replace("discourse.ubuntu.com", "discourse.charmhub.io")
    
    # Remove Mattermost link
    content = content.replace("https://chat.canonical.com/canonical/channels/documentation", "")
    
    # Update Matrix link
    content = content.replace(
        "https://matrix.to/#/#documentation:ubuntu.com",
        "https://matrix.to/#/#charmhub-charmdev:ubuntu.com"
    )
    
    # Add Juju to intersphinx_mapping
    content = re.sub(
        r'(intersphinx_mapping = \{)',
        r'\1\n    "juju": ("https://documentation.ubuntu.com/juju/3.6/", None),',
        content
    )
    
    conf_py.write_text(content)


def update_linkcheck_ignore():
    """Add Matrix URL to linkcheck_ignore in conf.py."""
    print("INFO: Adding Matrix URL to linkcheck_ignore...")
    
    conf_py = Path("docs/conf.py")
    content = conf_py.read_text()
    
    # Add Matrix URL to linkcheck_ignore at the beginning of the list
    content = re.sub(
        r'(linkcheck_ignore = \[)',
        r'\1\n    "https://matrix.to/#/#charmhub-charmdev:ubuntu.com",',
        content
    )
    
    conf_py.write_text(content)
    print("SUCCESS: Matrix URL added to linkcheck_ignore.")


def get_charm_metadata():
    """
    Extract charm metadata from charmcraft.yaml or metadata.yaml.
    
    Returns dict with 'name' and 'source' keys, or None values if not found.
    Checks charmcraft.yaml first, then falls back to metadata.yaml.
    """
    metadata = {"name": None, "source": None}
    
    charmcraft_file = Path("charmcraft.yaml")
    metadata_file = Path("metadata.yaml")
    
    # Check charmcraft.yaml first
    if charmcraft_file.exists():
        try:
            with charmcraft_file.open("r") as f:
                charmcraft_data = yaml.safe_load(f)
            
            # Extract name
            if "name" in charmcraft_data:
                metadata["name"] = charmcraft_data["name"]
            
            # Extract source from links.source or source
            if "links" in charmcraft_data and "source" in charmcraft_data["links"]:
                metadata["source"] = charmcraft_data["links"]["source"]
            elif "source" in charmcraft_data:
                metadata["source"] = charmcraft_data["source"]
                
        except yaml.YAMLError as e:
            print(f"WARNING: Could not parse charmcraft.yaml: {e}")
        except Exception as e:
            print(f"WARNING: Error reading charmcraft.yaml: {e}")
    else:
        print("WARNING: charmcraft.yaml not found in project root")
    
    # Fall back to metadata.yaml for missing keys
    if metadata_file.exists():
        try:
            with metadata_file.open("r") as f:
                metadata_data = yaml.safe_load(f)
            
            # Extract name if not already found
            if metadata["name"] is None and "name" in metadata_data:
                metadata["name"] = metadata_data["name"]
            
            # Extract source if not already found
            if metadata["source"] is None and "source" in metadata_data:
                metadata["source"] = metadata_data["source"]
                
        except yaml.YAMLError as e:
            print(f"WARNING: Could not parse metadata.yaml: {e}")
        except Exception as e:
            print(f"WARNING: Error reading metadata.yaml: {e}")
    else:
        print("WARNING: metadata.yaml not found in project root")
    
    # Report what was found or missing
    if metadata["name"] is None:
        print("WARNING: 'name' key not found in charmcraft.yaml or metadata.yaml")
    if metadata["source"] is None:
        print("WARNING: 'source' key not found in charmcraft.yaml or metadata.yaml")
    
    return metadata


def validate_github_url(url):
    """
    Validate that a URL looks like a valid GitHub URL.
    
    Returns True if valid, False otherwise.
    """
    if not url:
        return False
    
    if "github.com" not in url:
        print(f"WARNING: URL does not appear to be a GitHub URL: {url}")
        return False
    
    # Basic pattern matching for GitHub URLs
    github_pattern = r'https?://github\.com/[\w\-]+/[\w\-]+'
    if not re.match(github_pattern, url):
        print(f"WARNING: URL does not match expected GitHub URL pattern: {url}")
        return False
    
    return True


def update_project_variables():
    """Optionally update project-specific variables in conf.py."""
    
    conf_py = Path("docs/conf.py")
    content = conf_py.read_text()
    
    # Get metadata from YAML files
    metadata = get_charm_metadata()
    
    # Update project name (still requires user input)
    project_name = input("Enter name of project (e.g. 'WordPress charm'): ")
    print("INFO: Updating variable 'project'...")
    content = content.replace(
        'project = "Documentation starter pack"',
        f'project = "{project_name}"'
    )
    print("SUCCESS: 'project' updated.")
    
    # Auto-detect and update product_page
    if metadata["name"]:
        product_page = f"charmhub.io/{metadata['name']}"
        print(f"INFO: Auto-detected product_page: {product_page}")
        print("INFO: Updating variable 'product_page'...")
        content = content.replace(
            '"product_page": "documentation.ubuntu.com",',
            f'"product_page": "{product_page}",'
        )
        print("SUCCESS: 'product_page' updated.")
    else:
        print("WARNING: Skipping 'product_page' update - could not auto-detect charm name")
    
    # Auto-detect and update github_url and source_edit_link
    if metadata["source"]:
        github_url = metadata["source"]
        if validate_github_url(github_url):
            print(f"INFO: Auto-detected github_url: {github_url}")
            print("INFO: Updating variable 'github_url'...")
            content = content.replace(
                '"github_url": "https://github.com/canonical/sphinx-docs-starter-pack",',
                f'"github_url": "{github_url}",'
            )
            
            # Enable edit button and update source_edit_link
            print("INFO: Enabling edit button and updating 'source_edit_link'...")
            content = content.replace("# html_theme_options = {", "html_theme_options = {")
            content = content.replace(
                "# 'source_edit_link': 'https://github.com/canonical/sphinx-docs-starter-pack',",
                f'"source_edit_link": "{github_url}",'
            )
            content = content.replace("# }", "}")
            print("SUCCESS: 'github_url' and 'source_edit_link' updated.")
        else:
            print("WARNING: Skipping 'github_url' and 'source_edit_link' updates - URL validation failed")
    else:
        print("WARNING: Skipping 'github_url' and 'source_edit_link' updates - could not auto-detect source URL")
    
    conf_py.write_text(content)


def add_mermaid_extension():
    """Add Mermaid extension to project and update mermaid blocks to MyST syntax."""
    print("INFO: Adding Mermaid extension to project...")
    
    # Add to requirements.txt
    requirements = Path("docs/requirements.txt")
    with requirements.open("a") as f:
        f.write("sphinxcontrib-mermaid\n")
    
    # Add to conf.py extensions
    conf_py = Path("docs/conf.py")
    content = conf_py.read_text()
    content = re.sub(
        r'(extensions = \[)',
        r'\1\n    "sphinxcontrib.mermaid",',
        content
    )
    conf_py.write_text(content)
    
    print("SUCCESS: Added Mermaid extension to conf.py and requirements.txt")
    
    # Update mermaid blocks in markdown files
    print("INFO: Searching for mermaid blocks in markdown files...")
    
    docs_dir = Path("docs")
    sphinx_dir = docs_dir / ".sphinx"
    build_dir = docs_dir / "_build"
    
    # Find all .md files recursively, excluding .sphinx and _build
    md_files = []
    for md_file in docs_dir.rglob("*.md"):
        # Skip files in .sphinx or _build directories
        if str(md_file).startswith(str(sphinx_dir)) or str(md_file).startswith(str(build_dir)):
            continue
        md_files.append(md_file)
    
    # Track modified files
    modified_files = []
    
    # Process each markdown file
    for md_file in md_files:
        content = md_file.read_text()
        original_content = content
        
        # Replace ```mermaid (with or without trailing space) with ```{mermaid}
        # Use re.sub to replace both patterns
        content = re.sub(r'```mermaid\s*\n', '```{mermaid}\n', content)
        
        # Check if file was modified
        if content != original_content:
            md_file.write_text(content)
            modified_files.append(str(md_file))
    
    # Report results
    if modified_files:
        print("SUCCESS: Updated mermaid blocks in the following files:")
        for file_path in modified_files:
            print(f"  - {file_path}")
    else:
        print("INFO: No mermaid blocks were found or updated.")


def create_subdirectory_index_files():
    """Add initial index.md files in all subdirectories."""
    print("INFO: Checking for index.md files in all subdirectories...")
    
    docs_dir = Path("docs")
    sphinx_dir = docs_dir / ".sphinx"
    
    # Find all subdirectories (excluding .sphinx)
    subdirs = [d for d in docs_dir.rglob("*") if d.is_dir() and not str(d).startswith(str(sphinx_dir))]
    
    for subdir in subdirs:
        index_file = subdir / "index.md"
        if not index_file.exists():
            print(f"INFO: No index.md file found in {subdir}. Creating one...")
            
            # Get list of files in subdirectory
            files = [f.name for f in subdir.iterdir() if f.is_file()]
            files_list = "\n".join(files)
            
            # Create target from directory name
            stripped_subdir = str(subdir).replace("docs/", "")
            replaced = stripped_subdir.replace("/", "_").replace(" ", "_").replace("-", "_")
            target = f"({replaced})="
            
            # Create index.md content
            index_content = f"""---
myst:
  html_meta:
    "description lang=en": "TBD"
---

{target}

# {subdir}

Description TBD

```{{toctree}}
:maxdepth: 1
{files_list}
```"""
            
            index_file.write_text(index_content)
            print(f"SUCCESS: Created index.md file in {subdir}!")


def refactor_main_index():
    """Refactor index.md overview page."""
    print("INFO: Updating the Contents section of the home page...")
    
    index_file = Path("docs/index.md")
    content = index_file.read_text()
    
    # Add metadata description to front
    metadata_text = """---
myst:
  html_meta:
    "description lang=en": "TBD"
---
"""
    
    # Find Contents section and remove everything after it
    lines = content.split("\n")
    contents_line_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "# Contents":
            contents_line_idx = idx
            break
    
    if contents_line_idx is not None:
        # Keep everything before Contents
        content_before = "\n".join(lines[:contents_line_idx])
    else:
        content_before = content
    
    # Find subdirectory index files
    subdirs = sorted(Path("docs").glob("*/index.md"))
    stripped_subdirs = "\n".join([str(s).replace("docs/", "") for s in subdirs])
    
    # Find other .md files
    other_files = [f for f in Path("docs").glob("*.md") if f.name != "index.md"]
    stripped_other = "\n".join([str(f).replace("docs/", "") for f in other_files])
    
    # Create new toctree
    index_toctree = f"""```{{toctree}}
:hidden:
{stripped_subdirs}
{stripped_other}
```"""
    
    # Combine everything
    new_content = metadata_text + content_before + "\n\n" + index_toctree + "\n"
    index_file.write_text(new_content)
    
    print("SUCCESS: Contents section of the home page has been refactored!")


def setup_rtd_cookie_banner(tmp_dir: Path):
    """Set up RTD cookie banner."""
    print("INFO: Setting up the analytics banner...")
    
    # Create directories
    static_dir = Path("docs/_static")
    static_js_dir = static_dir / "js"
    templates_dir = Path("docs/_templates")
    
    static_dir.mkdir(parents=True, exist_ok=True)
    static_js_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    # Clone cookie banner repo
    print(f"INFO: Cloning {RTD_COOKIE_REPO}...")
    cookie_tmp = tmp_dir / "cookie_banner"
    subprocess.run(
        ["git", "clone", "--depth", "1", RTD_COOKIE_REPO, str(cookie_tmp)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Copy files
    print(f"INFO: Copying files from {RTD_COOKIE_REPO}...")
    shutil.copy(cookie_tmp / "bundle.js", static_js_dir)
    shutil.copy(cookie_tmp / "cookie-banner.css", static_dir)
    shutil.copy(cookie_tmp / "header.html", templates_dir)
    shutil.copy(cookie_tmp / "footer.html", templates_dir)
    
    # Update conf.py
    print("INFO: Updating conf.py to detect the cookie banner...")
    conf_py = Path("docs/conf.py")
    content = conf_py.read_text()
    
    # Uncomment html_static_path and templates_path
    content = content.replace("#html_static_path", "html_static_path")
    content = content.replace("#templates_path", "templates_path")
    
    # Set html_css_files and html_js_files
    content = content.replace(
        "# html_css_files = []",
        "html_css_files = ['cookie-banner.css']"
    )
    content = content.replace(
        "# html_js_files = []",
        "html_js_files = ['js/bundle.js']"
    )
    
    conf_py.write_text(content)
    print("SUCCESS: RTD banner set up!")


def add_reference_targets():
    """Add target headers to all markdown files."""
    print("INFO: Adding reference targets to all files...")
    
    docs_dir = Path("docs")
    
    # Find all .md files except index files
    md_files = []
    for pattern in ["*.md", "*/*.md"]:
        md_files.extend(docs_dir.glob(pattern))
    
    # Exclude index files
    md_files = [
        f for f in md_files 
        if f.name != "index.md" and not str(f).endswith("/index.md")
    ]
    
    for file in md_files:
        # Create target from filename
        stripped = str(file).replace("docs/", "").replace(".md", "")
        replaced = stripped.replace("/", "_").replace(" ", "_").replace("-", "_")
        target = f"({replaced})=\n"
        
        # Prepend target to file
        original_content = file.read_text()
        new_content = target + original_content
        file.write_text(new_content)
    
    print("SUCCESS: Added targets to all files!")


def print_final_instructions():
    """Print final cleanup and instructions."""
    print("SUCCESS: RTD project has been set up!")
    print("INFO: Please review the changes with 'make run' and run 'git add .' to commit them.")
    print("INFO: Here's a list of other things you should do before opening a PR:")
    print("INFO:  [ ] Update Charmhub links to use new targets")
    print("INFO:  [ ] Update the landing pages' titles, descriptions, and SEO metadescriptions")
    print("INFO:  [ ] Replace Charmhub links to other projects with RTD intersphinx links (if applicable)")
    print("INFO:  [ ] Update Mermaid diagrams and admonition blocks")


def main():
    """Main workflow for setting up RTD project."""
    # Step 0: Git branch check
    check_git_branch()
    
    # Use temporary directory with automatic cleanup
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Step 1: Clone template
        clone_template(tmp_path)
        
        # Step 2: Copy Sphinx files
        copy_sphinx_files(tmp_path)
        
        # Step 3: GitHub workflows
        setup_github_workflows()
        
        # Step 4: Custom wordlist migration
        migrate_custom_wordlist()
        
        # Step 5: Update conf.py links
        update_conf_py_links()
        
        # Step 6: Update linkcheck_ignore
        update_linkcheck_ignore()
        
        # Step 7: Optional project variables
        update_project_variables()
        
        # Step 8: Add Mermaid extension
        add_mermaid_extension()
        
        # Step 9: Create subdirectory index files
        create_subdirectory_index_files()
        
        # Step 10: Refactor main index
        refactor_main_index()
        
        # Step 11: RTD cookie banner
        setup_rtd_cookie_banner(tmp_path)
        
        # Step 12: Add reference targets
        add_reference_targets()
    
    # Step 13: Final instructions
    print("INFO: Cleaning up temporary files...")
    print_final_instructions()


if __name__ == "__main__":
    main()
