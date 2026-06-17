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

**Run all scripts from the repo root. Scripts require `gh` (authenticated) and `git`.**

Skill dir: `.agents/skills/upgrade-discourse-workload/` (`<skill-dir>` below).

---

## Entry Point

Identify `NEW_TAG` and `OLD_TAG` (current `source-tag` in `discourse_rock/rockcraft.yaml`).

Work through §1–§5 in order. For large version jumps (multiple months), also run §6.

Run all scripts regardless of bump size — do not pre-judge scope.

---

## §1 — Update `source-tag`

Edit `discourse_rock/rockcraft.yaml`:

```yaml
  discourse:
    source-tag: <NEW_TAG>
```

---

## §2 — Runtime requirements

Sub-agent: provide `NEW_TAG`, current `rockcraft.yaml`, `references/guide-core-versions.md`.

1. Run `bash <skill-dir>/scripts/check_discourse_requirements.sh <NEW_TAG>`
2. Return field-value pairs that differ from current `rockcraft.yaml`

Apply the returned changes.

---

## §3 — Plugin commits

Sub-agent: provide `NEW_TAG`, current `rockcraft.yaml`, `references/guide-plugins.md`.

1. Run `bash <skill-dir>/scripts/check_plugin_commits.sh <NEW_TAG>`
2. Return plugin name → new `source-commit` map; flag any ⚠️ FALLBACK plugins

Apply the returned changes. Note FALLBACK plugins in the PR description.

---

## §4 — Patches

Four patches, all must be verified:

| # | Patch | Target |
|---|---|---|
| 1 | `db_migrations.patch` | `db/post_migrate/<TIMESTAMP>_<name>.rb` |
| 2 | `lp1903695.patch` | `lib/middleware/anonymous_cache.rb` |
| 3 | `discourse-charm.patch` | `lib/tasks/discourse-charm.rake` |
| 4 | `sigterm.patch` | `config/unicorn.conf.rb` |

**Step 1:** `bash <skill-dir>/scripts/check_patch_applicability.sh <NEW_TAG>`

**Step 2:** For each ❌, delegate regeneration to a sub-agent:
- Provide: patch name, `NEW_TAG`, `OLD_TAG`, current patch content, relevant section of `references/guide-patches.md`
- Sub-agent must: work in a unique `/tmp` dir, clone Discourse at `NEW_TAG`, produce the new patch, clean up, return it
- Apply the returned patch

**Step 3:** Re-run the check — all four must be ✅ before proceeding.

**Step 4:** Update `apply-patches > prime` in `rockcraft.yaml` if any target filename changed.

---

## §5 — Build and validate

**Mandatory. Do not skip or defer to CI.**

Delegate to a sub-agent with `NEW_TAG` and the repo path.

### 5a — Rock
```bash
cd discourse_rock && rockcraft pack --verbosity brief
```

### 5b — Push to registry
```bash
sudo rockcraft.skopeo --insecure-policy copy \
  --dest-tls-verify=false \
  oci-archive:discourse_rock/discourse_*.rock \
  docker://localhost:32000/discourse:<NEW_TAG>
```

### 5c — Charm
```bash
CHARM_BUILD=$(mktemp -d /tmp/charm-build.XXXXXX)
git archive HEAD | tar -x -C "$CHARM_BUILD"
cd "$CHARM_BUILD" && charmcraft pack
CHARM_FILE="$(ls "$CHARM_BUILD"/*.charm | head -1)"
```

### 5d — Unit tests
```bash
PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/discourse-venv \
  uv run --group unit pytest tests/unit -v
```

### 5e — Integration tests

Juju with MicroK8s is available (`concierge-microk8s` controller, `testing` model).

Refresh the `testing` model, then run main tests with `--use-existing`:
```bash
juju refresh discourse-k8s --model testing \
  --path="$CHARM_FILE" \
  --resource discourse-image=localhost:32000/discourse:<NEW_TAG>

# Wait for active, then:
PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/discourse-venv \
  uv run --group integration pytest \
    tests/integration/test_charm.py \
    tests/integration/test_users.py \
    tests/integration/test_saml.py \
    -v --model testing --use-existing \
    --charm-file "$CHARM_FILE" \
    --discourse-image localhost:32000/discourse:<NEW_TAG>
```

DB migration test (fresh temp model):
```bash
PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/discourse-venv \
  uv run --group integration pytest \
    tests/integration/test_db_migration.py -v \
    --charm-file "$CHARM_FILE" \
    --discourse-image localhost:32000/discourse:<NEW_TAG>
```

### 5f — Shellcheck
If any `.sh` files under `.agents/skills/` were modified:
```bash
shellcheck -f gcc .agents/skills/upgrade-discourse-workload/scripts/*.sh
```

For build and test failure modes, see `references/guide-troubleshooting.md`.

---

## §6 — Testing database (major upgrades only)

Triggered when `test_db_migration` fails with "git_version does not match".

Sub-agent: provide `OLD_TAG`, `testing_database/creating-the-testing-database.md`,
`references/guide-db-migration.md`, `tests/integration/test_db_migration.py`.

1. Regenerate `testing_database/testing_database.sql` from `OLD_TAG`
2. Return the updated SQL and the updated assertion line for `test_db_migration.py`

Apply the changes and check `.trivyignore` per `references/guide-db-migration.md`.

---

## Completion checklist

- [ ] `source-tag` updated in `rockcraft.yaml`
- [ ] `NODE_VERSION`, `RUBY_VERSION`, `PNPM_VERSION`, bundler version updated if needed
- [ ] All plugin `source-commit` values updated
- [ ] `db_migrations.patch` targets the correct file for the new version
- [ ] All four patches apply ✅
- [ ] `apply-patches > prime` list updated
- [ ] `.trivyignore` updated if trivy reported new CVEs
- [ ] All `juju.wait()` calls in `test_db_migration.py` have `timeout=JUJU_WAIT_TIMEOUT` and `app_name in status.apps` guard
- [ ] `shellcheck` passes on all modified `.sh` files
- [ ] Unit and integration tests pass (including `test_db_migration`)

---

## References

| File | Load when |
|---|---|
| `references/guide-core-versions.md` | Node/Ruby/pnpm/bundler version details |
| `references/guide-plugins.md` | Plugin compatibility, inventory, additions/removals |
| `references/guide-patches.md` | Per-patch background and regeneration procedure |
| `references/guide-db-migration.md` | Testing database refresh, trivy CVE handling |
| `references/guide-troubleshooting.md` | Build/test failure modes and fixes |

### Scripts

| Script | Purpose |
|---|---|
| `scripts/check_discourse_requirements.sh <TAG>` | Node/Ruby/pnpm/bundler version check |
| `scripts/check_plugin_commits.sh <TAG>` | Resolve plugin commits via `.discourse-compatibility` |
| `scripts/check_patch_applicability.sh <TAG>` | Test all patches against new Discourse |
| `scripts/find_db_migration_target.sh <NEW_TAG> <OLD_TAG>` | Find `db_migrations.patch` target |
| `scripts/regenerate_patch.sh <TAG> <patch-name>` | Interactive patch regeneration |

