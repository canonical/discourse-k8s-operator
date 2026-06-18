# Guide: Testing Database and Trivy

Deep dive on two integration concerns: refreshing the `testing_database.sql`
used in migration tests, and keeping `.trivyignore` up to date after a trivy
CVE scan.

---

## Part 1: Testing database

### What it is

`testing_database/testing_database.sql` is a PostgreSQL dump of a Discourse
database at a known old version. The integration test `test_db_migration.py`
loads this dump and then runs Discourse migrations against it to verify that
the upgrade path works end-to-end.

### When to update

Only needed when doing a **large version jump** (multiple months/versions) where
the existing dump is too old to be a realistic migration source, or when the
migration test fails with a "git_version does not match" assertion.

### Updating the test database

Follow the procedure in `testing_database/creating-the-testing-database.md`.
The dump represents the version being migrated **FROM** (the old version).

### Updating the integration test

After regenerating the dump, update `tests/integration/test_db_migration.py`:

1. Update the docstring to name the version being migrated from
2. Update the `git_version` assertion to match the old version's commit hash:
   ```python
   assert "<OLD_VERSION_GIT_HASH>" in latest_git_version, (
       "Discourse <OLD_VERSION> git version does not match with the database version"
   )
   ```
   The hash comes from querying `schema_migration_details` on the old database:
   ```sql
   SELECT git_version FROM schema_migration_details LIMIT 1;
   ```

---

## Part 2: Trivy security scan

After the rock is built, the CI runs `trivy` to scan for CVEs. New Discourse
versions sometimes introduce new CVEs in their dependencies that have no fix yet.

If the build fails due to a trivy CVE, add it to `.trivyignore` with a comment:
```
# <package> — <reason no fix is available>
CVE-2025-XXXXX
```

Keep the `.trivyignore` tidy: when a CVE is fixed in a later Discourse version,
remove its entry.
