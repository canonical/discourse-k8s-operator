# Guide: Core Version Requirements

Deep dive on checking and updating the Node.js, Ruby, pnpm, and Bundler version
pins in `discourse_rock/rockcraft.yaml` when upgrading Discourse.

---

## Overview

Discourse bundles its own JavaScript toolchain and has Ruby version requirements.
These are pinned explicitly in the `tooling` and `setup` parts of `rockcraft.yaml`
and must be kept in sync with what the target Discourse version requires.

---

## Running the check

```bash
bash .agents/skills/upgrade-discourse-workload/scripts/check_discourse_requirements.sh <NEW_TAG>
```

The script fetches the requirements directly from the Discourse repo at the target
tag and prints them alongside the current values in `rockcraft.yaml`.

---

## What to check and where Discourse declares it

| Requirement | Discourse source file | rockcraft.yaml field |
|---|---|---|
| Ruby version | `.ruby-version` or `Gemfile` (`ruby "~> X.Y"`) | `RUBY_VERSION` |
| Node.js version | `.node-version`, `.nvmrc`, or `package.json` `engines.node` | `NODE_VERSION` |
| pnpm version | `package.json` `packageManager` field (`pnpm@X.Y.Z`) | `PNPM_VERSION` |
| Bundler version | `Gemfile.lock` `BUNDLED WITH` section | `gem install -n "bin" bundler -v X.Y.Z` in `setup` part |

---

## Node.js

Node.js is downloaded directly from `nodejs.org` at rock build time — it is **not**
installed from Ubuntu packages. Always pin to a specific LTS release that satisfies
the Discourse constraint.

- Check `.node-version` or `package.json` `engines.node` for the minimum required version.
- Prefer the latest LTS release that satisfies the constraint (e.g. if `>= 20`, use `22.x LTS`).
- Verify the release exists at `https://nodejs.org/dist/v<VERSION>/`.

In `rockcraft.yaml`:
```yaml
    build-environment:
      - NODE_VERSION: "22.12.0"   # ← update this
```

---

## Ruby

Ruby is installed at build time via `ruby-install`. The version must exactly match
Discourse's `.ruby-version` file.

- Discourse publishes `.ruby-version` at the repo root.
- `RUBY_INSTALL_VERSION` is the version of the `ruby-install` tool itself — only
  update this if the tool has a new release that fixes a build issue.

In `rockcraft.yaml`:
```yaml
    build-environment:
      - RUBY_INSTALL_VERSION: "0.10.1"   # tool version, rarely changes
      - RUBY_VERSION: "3.3.8"            # ← update to match .ruby-version
```

---

## pnpm

Discourse replaced Yarn with pnpm. The required pnpm version is declared in
`package.json` under `packageManager`:

```json
{
  "packageManager": "pnpm@10.28.0+sha512...."
}
```

Extract just the version number (strip the `+sha...` suffix).

In `rockcraft.yaml`:
```yaml
    build-environment:
      - PNPM_VERSION: "9.15.0"   # ← update to match packageManager
```

---

## Bundler

Bundler version is declared at the bottom of `Gemfile.lock` under `BUNDLED WITH`:

```
BUNDLED WITH
   2.6.4
```

This controls which bundler version is installed in the `setup` part:

```yaml
  setup:
    override-prime: |
      cd srv/discourse/app
      gem install -n "bin" bundler -v 2.6.4   # ← update version here
```

> Bundler is also installed transitively via the `bundler-config` part. If the
> `bin/bundle install` step fails during rock build, a bundler version mismatch
> is the most likely cause.
