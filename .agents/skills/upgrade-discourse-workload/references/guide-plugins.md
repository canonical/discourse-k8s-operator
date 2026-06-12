# Guide: Plugin Source Commits

Deep dive on verifying and updating the `source-commit` values for each plugin
part in `discourse_rock/rockcraft.yaml`.

---

## The `.discourse-compatibility` mechanism

Discourse plugins can declare which commit to use for each Discourse version via
a `.discourse-compatibility` file at the root of their repository. This is the
**authoritative** source for plugin compatibility.

Reference: https://meta.discourse.org/t/156971

### File format

The modern format uses `<` prefixed entries sorted descending (newest first):

```
< 2026.2.0-latest: abc123def456   # use this commit if Discourse < 2026.2.0-latest
< 3.6.0.beta1-dev: 09382316a5b9   # use this commit if Discourse < 3.6.0.beta1-dev
< 3.5.0.beta1-dev: d972e13829c4   # ...and so on
```

The legacy format (no `<`) lists entries descending, using the smallest key
that is >= the target Discourse version.

### Resolution algorithm

For the modern `<` format: scan top to bottom, use the first entry where
`discourse_version < key_version`. If no entry matches, use HEAD.

For the legacy format: find the smallest key that is >= `discourse_version`.

### Running the check

```bash
bash .agents/skills/upgrade-discourse-workload/scripts/check_plugin_commits.sh <NEW_TAG>
```

The script fetches `.discourse-compatibility` for each plugin, resolves the
correct commit, and compares it against the current `source-commit` in
`rockcraft.yaml`. It prints the resolution method for each plugin so the
decision is transparent.

---

## Plugin inventory

| Part name | GitHub repo | Has `.discourse-compatibility` |
|---|---|---|
| `discourse-markdown-note` | `canonical-web-and-design/discourse-markdown-note` | ❌ No |
| `discourse-mermaid-theme-component` | `discourse/discourse-mermaid-theme-component` | ✅ Yes |
| `discourse-saml` | `discourse/discourse-saml` | ✅ Yes |
| `discourse-prometheus` | `discourse/discourse-prometheus` | ✅ Yes |
| `discourse-signatures` | `discourse/discourse-signatures` | ✅ Yes |

### discourse-markdown-note (no compatibility file)

This plugin is maintained by the Canonical Web & Design team. It has no
`.discourse-compatibility` file. The script falls back to the latest commit on
the default branch and emits a `⚠️ FALLBACK` warning.

**Manual verification:** Check the plugin's README or commit history for any
notes about Discourse version compatibility. When in doubt, use the latest
commit and verify the rock builds and tests pass.

---

## Plugin additions and removals

Between major Discourse versions, official plugins are sometimes **merged into
Discourse core** or **deprecated**. Check the
[Discourse release notes](https://github.com/discourse/discourse/releases) and
[blog](https://blog.discourse.org) when doing a major version bump.

### If a plugin is merged into core

1. Remove its `part` block from `rockcraft.yaml`
2. Remove its `bin/bundle install --gemfile=...` line from the `setup` part
3. Remove it from the `after:` list in the `setup` part
4. Verify the rock still builds and its features work

### If a new plugin should be added

1. Add a new `part` block following the pattern of existing plugins:
   ```yaml
     discourse-my-plugin:
       plugin: dump
       after: [discourse, bundler-config]
       source: https://github.com/discourse/discourse-my-plugin.git
       source-commit: <COMMIT>
       source-depth: 1
       organize:
         "*": srv/discourse/app/plugins/discourse-my-plugin/
   ```
2. If the plugin has its own `Gemfile`, add to `setup`:
   ```yaml
       bin/bundle install --gemfile="plugins/discourse-my-plugin/Gemfile"
   ```
3. Add it to the `after:` list in the `setup` part

---

## Updating source-commit manually

If the script is unavailable or you need to verify a specific commit:

1. Go to `https://github.com/<owner>/<plugin>`
2. Check `.discourse-compatibility` at the repo root
3. Apply the resolution algorithm above for your target Discourse version
4. Copy the full 40-character commit SHA into `rockcraft.yaml`
