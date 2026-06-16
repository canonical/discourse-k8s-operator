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

Delegate to a sub-agent with this context: `NEW_TAG`, the current
`discourse_rock/rockcraft.yaml` content, and `references/guide-core-versions.md`.

The sub-agent should:
1. Run `bash <skill-dir>/scripts/check_discourse_requirements.sh <NEW_TAG>`
2. Compare the output against the current values in `rockcraft.yaml`
3. Return the exact field-value pairs that need updating (e.g. `PNPM_VERSION: 10.28.0`)

The main agent applies those changes to `rockcraft.yaml`.

---

## §3 — Plugin commits

Delegate to a sub-agent with this context: `NEW_TAG`, the current
`discourse_rock/rockcraft.yaml` content, and `references/guide-plugins.md`.

The sub-agent should:
1. Run `bash <skill-dir>/scripts/check_plugin_commits.sh <NEW_TAG>`
2. For each plugin flagged with 🔄, record the resolved commit
3. For each plugin flagged with ⚠️ FALLBACK (no `.discourse-compatibility` file),
   verify the returned HEAD commit is safe to use and note the manual check
4. Return the complete map of plugin name → new `source-commit` value

The main agent applies those changes to `rockcraft.yaml` and records any
FALLBACK plugins that need a manual compatibility note in the PR description.

---

## §4 — Patches

There are **exactly four patches** that must all be verified and updated as needed:

| # | Patch file | Target file |
|---|---|---|
| 1 | `db_migrations.patch` | `db/post_migrate/<TIMESTAMP>_<name>.rb` |
| 2 | `lp1903695.patch` | `lib/middleware/anonymous_cache.rb` |
| 3 | `discourse-charm.patch` | `lib/tasks/discourse-charm.rake` |
| 4 | `sigterm.patch` | `config/unicorn.conf.rb` |

Do not assume any patch is fine without checking. All four must be confirmed.

**Step 1 — Run the applicability check against a shallow clone of Discourse:**
```bash
bash <skill-dir>/scripts/check_patch_applicability.sh <NEW_TAG>
```

This clones Discourse at `<NEW_TAG>` into a **unique temporary workspace**
outside the repository (via `mktemp -d` under `$TMPDIR` or `/tmp`) and applies
all four patches in sequence, reporting ✅/❌ per patch. Never clone into
`discourse_rock/`, the repo root, or any shared working directory. No rock
build is needed at this stage.

**Step 2 — Fix any failing patches.**

For each ❌ patch, delegate the regeneration work to a sub-agent with this
context: the patch name, `NEW_TAG`, `OLD_TAG`, the current patch content from
`discourse_rock/patches/`, and the relevant section of `references/guide-patches.md`.
The sub-agent should create its **own** unique temporary workspace outside the
repo, clone Discourse at `NEW_TAG`, apply the change, produce the new patch
diff, return it, and clean up that temp workspace before finishing. Do not let
multiple sub-agents share a clone directory. Apply the returned diff to the
patch file.

**Step 3 — Re-run the applicability check** to confirm all four patches now ✅.

**Step 4 — Update the `prime` list.**  
After any patch change, verify the patch's target file is listed under
`apply-patches > prime` in `rockcraft.yaml` and update the filename if it
changed. An outdated entry causes the rock to bundle the wrong file.

Do not proceed to §5 until `check_patch_applicability.sh` reports ✅ for all
four patches.

---

## §5 — Build and validate

Only start this section once `check_patch_applicability.sh` confirms all four
patches apply cleanly (§4 Step 3). The rock build is slow (20–40 min) and noisy
— do not use it as the primary way to validate patches.

Delegate the full build and test sequence to a sub-agent:

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

The sub-agent should report only failures back. If the rock build fails:
- `bin/bundle install` error → Ruby or bundler version mismatch (revisit §2)
- patch-related error → patch applied cleanly in isolation but conflicts with
  another; revisit §4 and check patch ordering in `rockcraft.yaml`

---

## §6 — Testing database (major upgrades only)

If the migration test fails with a "git_version does not match" assertion,
the testing database needs regenerating from the version being migrated FROM.

Delegate to a sub-agent with this context: `OLD_TAG`, the current
`testing_database/creating-the-testing-database.md`, `references/guide-db-migration.md`,
and the current `tests/integration/test_db_migration.py`.

The sub-agent should:
1. Follow the procedure in `testing_database/creating-the-testing-database.md`
   to regenerate `testing_database/testing_database.sql` from `OLD_TAG`
2. Extract the `git_version` hash from the new dump
3. Return the updated `testing_database.sql` and the exact assertion line
   to update in `test_db_migration.py`

The main agent applies those changes and checks whether `.trivyignore` needs
updating (see `references/guide-db-migration.md` Part 2).

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
