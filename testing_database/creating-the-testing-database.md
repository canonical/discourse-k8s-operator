# Create the testing database

Current baseline fixture:

- Discourse workload: `v2026.1.7`
- PostgreSQL channel: `14/stable`
- Expected git_version in `schema_migration_details`: `b6af77c0382ac61817e825e4e285217327772b54`

## 1) Deploy the baseline stack

Create a new Juju model or use an existing one with space for a clean deployment:

```bash
juju add-model testing-db-baseline || juju switch testing-db-baseline
```

Deploy PostgreSQL 14 and wait for it to be ready:

```bash
juju deploy postgresql-k8s --channel 14/stable --wait
```

Deploy the Discourse charm at v2026.1.7 with appropriate configuration:

```bash
# Build/obtain the v2026.1.7 charm file
juju deploy ./discourse-k8s.charm discourse-k8s \
  --config developer_emails="noreply@canonical.com" \
  --config external_hostname="discourse-k8s" \
  --config smtp_address="test.local" \
  --config smtp_domain="test.local" \
  --config s3_install_cors_rule="false" \
  --wait

# Relate to PostgreSQL
juju relate discourse-k8s:postgresql-client postgresql-k8s:database
```

Wait until all units reach active/idle state:

```bash
juju wait-for unit -m testing-db-baseline --timeout=10m
```

Verify the deployment is healthy by checking unit status and logs if needed.

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
