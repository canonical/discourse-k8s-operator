---
name: upgrade-discourse-workload
description: >
  Guides the full upgrade of the Discourse workload version in the discourse-k8s-operator charm.
  Handles rockcraft.yaml source-tag bumps, Node.js/Ruby/pnpm/bundler version checks, plugin
  source-commit updates, patch regeneration (db_migrations, lp1903695, sigterm, discourse-charm),
  testing-database refresh, and integration test updates. Includes diagnostic scripts for checking
  requirements, patch applicability, and plugin compatibility automatically.
  WHEN: upgrade discourse version, bump discourse workload, update discourse tag, new discourse
  release, discourse version bump, update rockcraft.yaml discourse, upgrade discourse charm,
  update source-tag, discourse patch update, update discourse plugins, discourse rock upgrade,
  discourse rock build, update discourse bundler, update discourse ruby, update discourse node.
license: Apache-2.0
metadata:
  author: canonical
  version: "1.0.0"
  summary: Automates and guides the Discourse workload version upgrade process in the discourse-k8s-operator charm.
  tags:
    - discourse
    - charm
    - rockcraft
    - upgrade
---

# Upgrade Discourse Workload

## Overview

Upgrades the Discourse workload version used in the `discourse-k8s-operator` charm.
This involves updating `discourse_rock/rockcraft.yaml` and regenerating or adjusting
several dependent artefacts: Node/Ruby version pins, plugin commits, and four source
patches applied to Discourse before the rock is built.

**All scripts must be run from the `discourse-k8s-operator` repo root unless stated otherwise.**  
**All scripts require `gh` CLI (authenticated) and `git`.**

The SKILL directory is `.agents/skills/upgrade-discourse-workload/` in the repo root.
Referred to as `<skill-dir>` in the examples below.

---

## Entry Point

When asked to upgrade the Discourse workload, first identify:
- `NEW_TAG` — the target Discourse version (e.g. `v2026.1.4` or `2026.03.0-latest`)
- `OLD_TAG` — the current `source-tag` in `discourse_rock/rockcraft.yaml`

Then use the Workflow Decision Tree below to determine scope, and work through
the applicable sections in order. Run scripts as directed — do not manually
replicate what they compute.

---

## Workflow Decision Tree

Determine what kind of upgrade this is:

1. **Patch bump (same YYYY.MM, e.g. v2026.1.3 → v2026.1.4)?**  
   → Likely only needs: source-tag update + patch line-number fixes  
   → Run scripts, apply fixes for anything flagged, done.

2. **Minor/major bump (new month or year, e.g. v2026.1.x → v2026.2.x)?**  
   → Likely needs: all of the above + new db_migrations target + Node/Ruby check  
   → Work through §1–§5 top to bottom.

3. **Large version jump (multiple months)?**  
   → May also need: testing database refresh, plugin removals/additions  
   → Work through §1–§6; pay extra attention to §3 (plugin changes) and §6 (testing DB).

---

## §1 — Update `source-tag`

Edit `discourse_rock/rockcraft.yaml`:

```yaml
  discourse:
    source-tag: <NEW_TAG>   # change this line
```

Commit nothing yet — run all checks first.

---

## §2 — Runtime requirements

Run:
```bash
bash <skill-dir>/scripts/check_discourse_requirements.sh <NEW_TAG>
```

Update `rockcraft.yaml` if the script reports mismatches for `NODE_VERSION`,
`RUBY_VERSION`, `PNPM_VERSION`, or the bundler version in the `setup` part.

Load `references/guide-core-versions.md` for details on where each version is
declared in the Discourse repo and the exact fields to change in `rockcraft.yaml`.

---

## §3 — Plugin commits

Run:
```bash
bash <skill-dir>/scripts/check_plugin_commits.sh <NEW_TAG>
```

For each plugin flagged with 🔄, update `source-commit` in `rockcraft.yaml`.
Plugins with ⚠️ FALLBACK have no `.discourse-compatibility` file — verify
compatibility manually before accepting the HEAD commit.

Load `references/guide-plugins.md` for the `.discourse-compatibility` resolution
algorithm, the full plugin inventory, and instructions on handling plugin
additions or removals.

---

## §4 — Patches

Run:
```bash
bash <skill-dir>/scripts/check_patch_applicability.sh <NEW_TAG>
```

For patches that ❌ fail, load `references/guide-patches.md` to understand what
the patch does and how to regenerate it. Use the interactive helper:
```bash
bash <skill-dir>/scripts/regenerate_patch.sh <NEW_TAG> <patch-name>
```

> **After updating any patch**, check whether that patch's target file is listed
> in the `prime` list under `apply-patches` in `rockcraft.yaml` and update the
> filename if it changed. This is mandatory — an outdated `prime` entry causes
> the rock to bundle the wrong file.

---

## §5 — Build and validate

```bash
# Build the rock (20-40 min)
cd discourse_rock && rockcraft pack --verbosity brief

# Load into local registry (MicroK8s)
sudo rockcraft.skopeo --insecure-policy copy \
  oci-archive:discourse_*.rock \
  docker-daemon:localhost:32000/discourse:test

# Run unit tests
tox -e unit

# Run integration tests
make integration
```

If the rock build fails, inspect the error and cross-reference with §2 (versions)
or §4 (patches). A failed `bin/bundle install` usually means a Ruby or bundler
version mismatch.

---

## §6 — Testing database (major upgrades only)

If the migration test fails with a "git_version does not match" assertion,
the testing database needs regenerating from the version being migrated FROM.

Load `references/guide-db-migration.md` for the regeneration procedure, the
assertion to update in `test_db_migration.py`, and when to update `.trivyignore`
after a trivy scan failure.

---

## Completion checklist

Before raising a PR, verify all applicable items:

- [ ] `source-tag` updated in `rockcraft.yaml`
- [ ] `NODE_VERSION`, `RUBY_VERSION`, `PNPM_VERSION`, bundler version updated if needed
- [ ] All plugin `source-commit` values updated
- [ ] `db_migrations.patch` targets the correct file for the new version
- [ ] `lp1903695.patch`, `sigterm.patch`, `discourse-charm.patch` apply cleanly
- [ ] `apply-patches` `prime` list updated with the new migration filename
- [ ] `.trivyignore` updated if the trivy scan reported new CVEs
- [ ] Unit and integration tests pass

---

## References

| File | Load when |
|---|---|
| `references/guide-core-versions.md` | Node/Ruby/pnpm/bundler version details |
| `references/guide-plugins.md` | `.discourse-compatibility` mechanism, plugin inventory, additions/removals |
| `references/guide-patches.md` | Background on each patch, how to regenerate |
| `references/guide-db-migration.md` | Testing database refresh, trivy CVE handling |

### Scripts
| Script | Purpose |
|---|---|
| `scripts/check_discourse_requirements.sh <TAG>` | Node/Ruby/pnpm/bundler version check |
| `scripts/check_plugin_commits.sh <TAG>` | Resolve correct plugin commits via `.discourse-compatibility` |
| `scripts/check_patch_applicability.sh <TAG>` | Test all patches against new Discourse |
| `scripts/find_db_migration_target.sh <NEW_TAG> <OLD_TAG>` | Find `db_migrations.patch` target file |
| `scripts/regenerate_patch.sh <TAG> <patch-name>` | Interactive patch regeneration |
