# Guide: Troubleshooting

Failure modes and fixes for the build and test pipeline.

---

## Rock build failures

| Symptom | Cause | Fix |
|---|---|---|
| `bin/bundle install` error | Ruby or bundler version mismatch | Revisit §2 — update `RUBY_VERSION` / bundler pin |
| `patch failed: ... :0` or `corrupt patch` | Malformed new-file patch (wrong header format) | See "Patch format" below |
| Patch applies cleanly in check but fails in rock | Context conflict with a prior patch | Revisit §4 — check patch ordering in `rockcraft.yaml` |
| `PermissionError` on `.venv/lib64` or similar | Broken SSHFS symlink in repo root | Use `git archive` charm build path (§5c) |

---

## Patch format (new-file patches)

`discourse-charm.patch` creates a new file. New-file patches require a specific format that
`git apply --check` may accept locally but the rock build's LXC container will reject.

**Required headers:**
```diff
diff --git a/lib/tasks/discourse-charm.rake b/lib/tasks/discourse-charm.rake
new file mode 100644
--- /dev/null
+++ b/lib/tasks/discourse-charm.rake
```

**To regenerate correctly:**
```bash
# Stage the new file first, then diff the index — NOT `git diff` on an untracked file
git add lib/tasks/discourse-charm.rake
git diff --cached > discourse_rock/patches/discourse-charm.patch
```

---

## Integration test failures

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'app-name'` in wait lambda | App not yet registered in status | Guard: `app_name in status.apps and status.apps[app_name].is_active` |
| `TimeoutError: wait timed out after Xs` | Missing explicit timeout | All `juju.wait()` calls in `test_db_migration.py` must have `timeout=JUJU_WAIT_TIMEOUT` |
| `base "ubuntu@22.04" is not supported` | Stale pre-built `.charm` used | Build charm fresh via `git archive` (§5c) |
| `TLS handshake timeout` to k8s API | MicroK8s under load from stale models | Destroy leftover jubilant-* temp models: `juju models` then `juju destroy-model <name> --no-prompt --force` |
| `test_s3_conf` fails | Requires MicroCeph/radosgw (CI-only) | Expected locally — skip |
| `test_db_migration` "git_version does not match" | Testing database is outdated | Regenerate per §6 |

---

## Charm packing failures

| Symptom | Cause | Fix |
|---|---|---|
| `PermissionError: filename: /root/project/.../lib64` | Broken symlink in repo root pulled into LXD container | Use `git archive` to build from a clean `/tmp` copy (§5c) |
| `Ubuntu 22.04 builds cannot be performed on this Ubuntu 24.04 system` | `--destructive-mode` on wrong host OS | Use managed mode (default); fix the broken symlink issue instead |

---

## Registry push failures

The MicroK8s local registry runs HTTP, not HTTPS. Always include `--dest-tls-verify=false`:

```bash
sudo rockcraft.skopeo --insecure-policy copy \
  --dest-tls-verify=false \
  oci-archive:discourse_rock/discourse_*.rock \
  docker://localhost:32000/discourse:<NEW_TAG>
```
