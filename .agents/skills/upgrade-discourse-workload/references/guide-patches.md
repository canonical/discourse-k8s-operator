# Guide: Patches

Detailed background on each patch applied to the Discourse source in the rock,
and how to update each one for a new Discourse version.

**All four patches must be checked on every upgrade — do not assume any one is
fine without verifying.** Use `check_patch_applicability.sh` first; only clone
Discourse manually for patches that fail.

**Clone workspace rule:** clone Discourse only into a unique temporary
directory outside this repository, preferably via `mktemp -d` under `$TMPDIR`
or `/tmp`. Never clone into `discourse_rock/`, the repo root, or a shared
directory reused by multiple sub-agents. Clean up the temp workspace once the
patch task is finished.

| # | Patch | Target file | Typically needs update? |
|---|---|---|---|
| 1 | `db_migrations.patch` | `db/post_migrate/<TIMESTAMP>_<name>.rb` | Almost always (minor/major bumps) |
| 2 | `lp1903695.patch` | `lib/middleware/anonymous_cache.rb` | Only if context lines shifted |
| 3 | `discourse-charm.patch` | `lib/tasks/discourse-charm.rake` | Rarely |
| 4 | `sigterm.patch` | `config/unicorn.conf.rb` | Only if index hash changed |

---

## Overview

The `apply-patches` part in `rockcraft.yaml` applies four git patches to the
Discourse source tree before assets are compiled and the rock is primed.

```yaml
  apply-patches:
    override-stage: |
      git -C srv/discourse/app apply patches/db_migrations.patch
      git -C srv/discourse/app apply patches/lp1903695.patch
      git -C srv/discourse/app apply patches/discourse-charm.patch
      git -C srv/discourse/app apply patches/sigterm.patch
```

Run the applicability check before attempting manual regeneration:
```bash
bash .agents/skills/upgrade-discourse-workload/scripts/check_patch_applicability.sh <NEW_TAG>
```

---

## 1. `db_migrations.patch`

**File targeted:** `db/post_migrate/<TIMESTAMP>_<migration_name>.rb`

**Purpose:**  
Injects `DROP TRIGGER` SQL into the earliest new `post_migrate` file in the
target Discourse version. When upgrading from an older version, certain triggers
(e.g. `invites_user_id_readonly`) block later column-drop migrations. By
injecting the DROP statements into the first new migration, we guarantee they
run before any column-drop can fail.

**What the patch does:**
```diff
+    execute <<~SQL
+      DROP TRIGGER IF EXISTS invites_user_id_readonly ON invites;
+      DROP TRIGGER IF EXISTS invites_redeemed_at_readonly ON invites;
+      DROP TRIGGER IF EXISTS user_api_keys_scopes_readonly ON user_api_keys;
+    SQL
```
This block is inserted inside `def up` of the target migration file.

**When to update:** Almost always on minor/major bumps — whenever there are new
`post_migrate` files in the target version that didn't exist in the previous one.

**How to update:**

1. Find the earliest new target file:
   ```bash
   bash .agents/skills/upgrade-discourse-workload/scripts/find_db_migration_target.sh <NEW_TAG> <OLD_TAG>
   ```

2. Fetch its content:
   ```bash
   gh api "repos/discourse/discourse/contents/db/post_migrate/<FILENAME>.rb?ref=<NEW_TAG>" \
     --jq '.content' | base64 -d
   ```

3. Create a valid `git diff` that inserts the DROP TRIGGER block inside `def up`:
   ```diff
   diff --git a/db/post_migrate/<FILENAME>.rb b/db/post_migrate/<FILENAME>.rb
   index <OLD_HASH>..<NEW_HASH> 100644
   --- a/db/post_migrate/<FILENAME>.rb
   +++ b/db/post_migrate/<FILENAME>.rb
   @@ -N,M +N,M+5 @@ class <ClassName> < ActiveRecord::Migration[X.Y]
      def up
   +    execute <<~SQL
   +      DROP TRIGGER IF EXISTS invites_user_id_readonly ON invites;
   +      DROP TRIGGER IF EXISTS invites_redeemed_at_readonly ON invites;
   +      DROP TRIGGER IF EXISTS user_api_keys_scopes_readonly ON user_api_keys;
   +    SQL
        <original first line of def up>
   ```

4. Save to `discourse_rock/patches/db_migrations.patch`.

5. **Update the `prime` list** in the `apply-patches` part of `rockcraft.yaml`:
   ```yaml
     apply-patches:
       ...
       prime:
         - srv/discourse/app/db/post_migrate/<NEW_FILENAME>.rb   # ← update this
         - srv/discourse/app/lib/middleware/anonymous_cache.rb
         - srv/discourse/app/lib/tasks/discourse-charm.rake
         - srv/discourse/app/config/unicorn.conf.rb
         - srv/discourse/app/config/environments/production.rb
   ```

---

## 2. `lp1903695.patch`

**File targeted:** `lib/middleware/anonymous_cache.rb`

**Purpose:**  
Fixes a crash in the anonymous cache middleware when a request body's IO object
does not respond to `.size`. Adds a `.respond_to?(:size)` guard before calling
`.size` on `env[Rack::RACK_INPUT]`.

**Background:**  
Named after Launchpad bug [LP#1903695](https://bugs.launchpad.net/bugs/1903695).
Without this fix, certain load balancer health checks or malformed requests
crash Discourse with a `NoMethodError`.

**Patch structure:**
```diff
--- a/lib/middleware/anonymous_cache.rb
+++ b/lib/middleware/anonymous_cache.rb
@@ -NNN,7 +NNN,7 @@
       if PAYLOAD_INVALID_REQUEST_METHODS.include?(env[Rack::REQUEST_METHOD]) &&
-           env[Rack::RACK_INPUT].size > 0
+           env[Rack::RACK_INPUT].respond_to?(:size) && env[Rack::RACK_INPUT].size > 0
```

**How to update:**  
This patch usually only needs the `@@ -NNN,7 @@` line numbers updated when the
surrounding code shifts. The actual change (`.respond_to?(:size) &&`) is
unlikely to change.

1. Find the new line number:
   ```bash
   gh api "repos/discourse/discourse/contents/lib/middleware/anonymous_cache.rb?ref=<NEW_TAG>" \
     --jq '.content' | base64 -d | grep -n "RACK_INPUT.size"
   ```

2. Update the `@@ -NNN,7 +NNN,7 @@` hunk header in `lp1903695.patch`.

3. The surrounding context lines must match exactly. If the context has also
   changed, update those lines too.

---

## 3. `discourse-charm.patch`

**File targeted:** `lib/tasks/discourse-charm.rake` (NEW FILE)

**Purpose:**  
Adds custom Rake tasks that the charm operator uses:
- `users:exists` — checks if a user with a given email exists
- `users:activate` — activates a user's email token

**Background:**  
The charm's `create-user` and related actions invoke these tasks via
`bundle exec rake users:activate`. Without this patch, these tasks don't exist
in Discourse's task system.

**How to update:**  
This patch creates a new file, so it almost never needs updating between
versions. It should apply cleanly unless Discourse changes the rake task
loading mechanism.

If the rake syntax ever needs to change (e.g., Rails API update), update
the task body in `discourse-charm.patch`.

**Patch format warning:**  
- Because this patch creates a new file, it **must** use `--- /dev/null` (not
  `--- a/lib/tasks/discourse-charm.rake`).
- When regenerating it, always use
  `git add lib/tasks/discourse-charm.rake && git diff --cached` rather than
  plain `git diff`, so Git emits the correct new-file patch format.
- A malformed new-file patch may still pass a plain `git apply --check`, but
  will fail during the actual rock build inside the LXC container. The
  applicability checker now flags this as `⚠️  MALFORMED FORMAT`.

---

## 4. `sigterm.patch`

**File targeted:** `config/unicorn.conf.rb`

**Purpose:**  
Intercepts SIGTERM signals in the Unicorn master and worker processes to enable
graceful shutdown. Without this:
- Kubernetes sends SIGTERM to the container
- Unicorn interprets SIGTERM as a fast shutdown (not graceful)
- In-flight requests are dropped

The patch makes the master process wait 15 seconds after receiving SIGTERM,
then send SIGQUIT (graceful shutdown) to itself.

**Patch structure:**
```diff
diff --git a/config/unicorn.conf.rb b/config/unicorn.conf.rb
index <OLD_HASH>..<NEW_HASH> 100644
--- a/config/unicorn.conf.rb
+++ b/config/unicorn.conf.rb
@@ -62,6 +62,15 @@ check_client_connection false
 initialized = false
 before_fork do |server, worker|
+  Signal.trap 'TERM' do
+    ...
```

**How to update:**  
The `index <OLD>..<NEW>` line must match the actual git blob hashes for the file
in the new Discourse version. If the patch fails only because of the index hash:

1. Get the blob SHA of `config/unicorn.conf.rb` at the new tag:
   ```bash
   gh api "repos/discourse/discourse/contents/config/unicorn.conf.rb?ref=<NEW_TAG>" \
     --jq '.sha'
   ```
   This is the OLD hash (state before patching).

2. Clone discourse, apply the patch manually, then get the resulting blob SHA.

3. Update `index <old>..<new>` in `sigterm.patch`.

The actual `Signal.trap` blocks should not need changing.

---

## Generating a patch from scratch

If `regenerate_patch.sh` is unavailable or you need full control:

1. Clone discourse at the new tag:
   ```bash
   WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/upgrade-discourse-workload.XXXXXX")"
   git -c advice.detachedHead=false clone --depth 1 --branch <NEW_TAG> \
     https://github.com/discourse/discourse.git "$WORKDIR/discourse"
   cd "$WORKDIR/discourse"
   ```

2. Edit the target file to apply the desired change.

3. Generate the patch:
   ```bash
   git diff > "$WORKDIR/<patch-name>.patch"
   ```

4. Review, then copy to `discourse_rock/patches/<patch-name>.patch`.

5. Clean up when done:
   ```bash
   rm -rf "$WORKDIR"
   ```

Or use the interactive helper:
```bash
bash .agents/skills/upgrade-discourse-workload/scripts/regenerate_patch.sh <NEW_TAG> <patch-name>
```
