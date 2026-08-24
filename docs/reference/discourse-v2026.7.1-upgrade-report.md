# Discourse v2026.7.1 upgrade report

## Summary

Upgrade work from `v2026.1` to `v2026.7.1` is mostly complete in the charm and rock, but full integration validation is currently blocked by a PostgreSQL/pgvector prerequisite not yet available in published stable charm channels.

## Confirmed breaking changes

### 1) Unicorn -> Pitchfork runtime switch

- Upstream no longer ships `config/unicorn.conf.rb` or `bin/unicorn`.
- `v2026.7.1` expects Pitchfork (`config/pitchfork.conf.rb`, `bin/pitchfork`).
- Impact: charm startup fails with code 127 if Unicorn paths are kept.
- Mitigation implemented:
  - Updated launcher to use Pitchfork.
  - Retargeted SIGTERM patch to Pitchfork config.

### 2) Higher Node.js engine floor

- New JS dependencies require Node `>=22.18.0`.
- Previous build value (`22.13.1`) fails pnpm install with `ERR_PNPM_UNSUPPORTED_ENGINE`.
- Mitigation implemented:
  - Updated rock build Node version to `22.18.0`.

### 3) pgvector `halfvec` requirement during migrations

- During `db:migrate`, PostgreSQL fails on `public.halfvec` type.
- Root cause: published `postgresql-k8s` channels currently package pgvector `0.6.0`, which does not provide `halfvec`.
- Verified evidence from `default-workspace` probes:
  - `14/stable` (`ubuntu@22.04`) -> pgvector `0.6.0`
  - `14/edge` (`ubuntu@22.04`) -> pgvector `0.6.0`
  - `16/stable` (`ubuntu@24.04`) -> pgvector `0.6.0`
  - `16/edge` (`ubuntu@24.04`) -> pgvector `0.6.0`
- This means changing to another currently published channel (stable or edge) does not resolve the `halfvec` migration failure today.

## Temporary compatibility patch (kept with explicit exit criteria)

A temporary rock patch (`discourse_rock/patches/pgvector_halfvec_compat.patch`) is kept to unblock upgrade validation while the PostgreSQL charm channels still ship pgvector `0.6.0`.

Patch behavior and safety constraints:

- Scope is limited to three `db/structure.sql` table definitions for AI embeddings.
- It only replaces `public.halfvec` with `public.vector` in schema load.
- It does not alter charm logic, relation handling, or non-AI Discourse paths.
- In this charm, `plugins/discourse-ai` is excluded from the image prime set, which limits runtime exposure to AI query paths that rely on `halfvec` operators.

This keeps the workaround narrow, auditable, and isolated to migration bootstrap.

## Required prerequisite to complete upgrade safely

Before fully supporting `v2026.7.1` without workaround, we need an available `postgresql-k8s` channel suitable for this charm deployment matrix that provides a pgvector version supporting `halfvec`. At current publication state, there is no channel meeting that requirement.

## Upstream references checked

- PostgreSQL charm config exposes pgvector as an optional extension (`plugin-vector-enable`), but does not itself define pgvector version policy:
  - https://github.com/canonical/postgresql-k8s-operator/blob/main/config.yaml
- Charmed PostgreSQL snap includes distro package `postgresql-16-pgvector` in stage packages (version inherited from package archives/PPAs):
  - https://github.com/canonical/charmed-postgresql-snap/blob/2a73a00cab904c170fc8ea027ddce18a814b9d7b/snap/snapcraft.yaml
- Historical enablement PRs:
  - https://github.com/canonical/charmed-postgresql-snap/pull/30
  - https://github.com/canonical/postgresql-k8s-operator/pull/361
- pgvector upstream introduced `halfvec` in `0.7.0`:
  - https://raw.githubusercontent.com/pgvector/pgvector/master/CHANGELOG.md
- Discourse `v2026.7.1` schema/migrations use `halfvec`:
  - https://raw.githubusercontent.com/discourse/discourse/v2026.7.1/plugins/discourse-ai/db/migrate/20241230153300_new_embeddings_tables.rb
  - https://raw.githubusercontent.com/discourse/discourse/v2026.7.1/db/structure.sql
- Ubuntu Noble package reference currently shows `postgresql-16-pgvector (0.6.0-1)`:
  - https://packages.ubuntu.com/noble/postgresql-16-pgvector

No active public issue/PR was found in Canonical PostgreSQL charm/snap repos specifically tracking a pgvector version bump beyond `0.6.0` at the time of this validation.

## Revert plan (day pgvector supports halfvec)

When a supported PostgreSQL charm channel reports pgvector `>= 0.7.0`:

1. Remove `discourse_rock/patches/pgvector_halfvec_compat.patch`.
2. Remove its `apply_patch_once` line from `discourse_rock/rockcraft.yaml`.
3. Remove `srv/discourse/app/db/structure.sql` from `apply-patches.prime`.
4. Rebuild rock and re-run integration + migration tests.

## Validation status

- Completed:
  - patch applicability checks for existing charm patches,
  - unit tests,
  - charm packaging,
  - rock build (with updated Node and runtime changes).
- Blocked:
  - full integration and migration pass for `v2026.7.1` due to missing `halfvec` support in currently available PostgreSQL charm channels.
