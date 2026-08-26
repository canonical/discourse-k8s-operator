# Create the testing database

Current baseline fixture:

- Discourse workload: `v2026.1.7`
- PostgreSQL channel: `14/stable`
- Expected git_version in `schema_migration_details`: `b6af77c0382ac61817e825e4e285217327772b54`

## 1) Deploy the baseline stack

Deploy Discourse `v2026.1.7` with PostgreSQL 14 and wait until all units are active.
Use the same charm configuration used by integration tests (external hostname, smtp placeholders, etc.).

## 2) Export the database dump from PostgreSQL

Get the PostgreSQL operator password (for example via Juju secret data), then:

```bash
juju ssh --model <model> --container postgresql postgresql-k8s/0 \
  "pg_dump -Fc -h localhost -U operator -d discourse > /tmp/testing_database.sql"
```

Copy the dump into this repository:

```bash
juju scp --model <model> --container postgresql \
  postgresql-k8s/0:/tmp/testing_database.sql \
  ./testing_database/testing_database.sql
```

## 3) Capture and update expected git_version

Query the baseline git hash:

```bash
juju ssh --model <model> --container postgresql postgresql-k8s/0 \
  "psql -h localhost -U operator --password -d discourse \
  -tAc \"SELECT git_version FROM schema_migration_details ORDER BY id DESC LIMIT 1;\""
```

Update `tests/integration/test_db_migration.py` to assert the new hash.

## Final notes

- Keep this fixture aligned with the "from" version for migration testing.
- Regenerate the dump whenever the supported baseline series changes.
