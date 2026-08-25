#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import json
import logging
import time

import jubilant
import pytest

from .conftest import JUJU_WAIT_TIMEOUT
from .conftest import POSTGRESQL_BASE, POSTGRESQL_CHANNEL

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_db_migration(
    juju: jubilant.Juju,
    charm_file: str,
    charm_resource_images: dict[str, dict[str, str]],
    charm_base: str,
):
    """
    arrange: preload postgres with a testing db that was created in Discourse v3.3.0
    act: deploy and integrate with the current Discourse version (latest)
    assert: discourse is active/idle

    Discourse must be active idle; migrations can fail if triggers prevent column
    changes. This is addressed with db_migrations.patch which must be regenerated
    for each Discourse version upgrade.
    """
    pg_app_name = "postgresql-k8s"
    juju.deploy(
        pg_app_name,
        channel=POSTGRESQL_CHANNEL,
        base=POSTGRESQL_BASE,
        trust=True,
        config={"profile": "testing"},
    )
    juju.wait(
        lambda status: pg_app_name in status.apps and status.apps[pg_app_name].is_active,
        timeout=JUJU_WAIT_TIMEOUT,
    )
    juju.config(
        pg_app_name,
        {
            "plugin-hstore-enable": True,
            "plugin-pg-trgm-enable": True,
            "plugin-vector-enable": True,
        },
    )
    juju.wait(
        lambda status: pg_app_name in status.apps and status.apps[pg_app_name].is_active,
        timeout=JUJU_WAIT_TIMEOUT,
    )
    app_secret_id = None
    for _ in range(30):
        secrets = json.loads(juju.cli("secrets", "--format", "json"))
        app_secret_id = next(
            (
                secret_id
                for secret_id, metadata in secrets.items()
                if metadata.get("owner") == pg_app_name
                and metadata.get("label", "").startswith("database-peers.")
            ),
            None,
        )
        if app_secret_id:
            break
        time.sleep(2)

    assert app_secret_id, "PostgreSQL app secret with operator password not found"

    secret_data = json.loads(
        juju.cli("show-secret", "--reveal", "--format", "json", app_secret_id)
    )
    db_pass = secret_data[app_secret_id]["content"]["Data"]["operator-password"]
    juju.cli(
        "scp",
        "--container",
        "postgresql",
        "./testing_database/testing_database.sql",
        pg_app_name + "/0:.",
    )

    for _ in range(30):
        try:
            juju.cli(
                "ssh",
                "--container",
                "postgresql",
                pg_app_name + "/0",
                "createdb -h localhost -U operator --password discourse",
                stdin=db_pass + "\n",
            )
            break
        except jubilant.CLIError as error:
            if "Connection refused" not in error.stderr:
                raise
            time.sleep(2)
    else:
        raise AssertionError("PostgreSQL did not accept TCP connections before migration import")

    for _ in range(5):
        try:
            juju.cli(
                "ssh",
                "--container",
                "postgresql",
                pg_app_name + "/0",
                "pg_restore -h localhost -U operator \
                      --password -d discourse \
                      --no-comments --no-owner --no-privileges --clean --if-exists ./testing_database.sql",
                stdin=db_pass + "\n",
            )
            break
        except jubilant.CLIError as error:
            if (
                "terminating connection due to administrator command" not in error.stderr
                and "no connection to the server" not in error.stderr
            ):
                raise
            time.sleep(15)
    else:
        raise AssertionError(
            "PostgreSQL did not stay available long enough to restore fixture database"
        )

    juju.cli(
        "ssh",
        "--container",
        "postgresql",
        pg_app_name + "/0",
        "psql -h localhost -U operator --password -d discourse \
              -c 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO PUBLIC; \
                  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO PUBLIC; \
                  GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO PUBLIC;'",
        stdin=db_pass + "\n",
    )

    # ensure we are using the Discourse v3.3.0 database
    # Discourse v3.3.0 uses the git commit hash:
    # 5bbdc8a813caf55ab3147ac65b5ffafb5e0aab90
    latest_git_version = juju.cli(
        "ssh",
        "--container",
        "postgresql",
        pg_app_name + "/0",
        "psql -h localhost -U operator \
              --password -d discourse \
              -c 'SELECT git_version FROM schema_migration_details LIMIT 1;'",
        stdin=db_pass + "\n",
    )
    assert "5bbdc8a813caf55ab3147ac65b5ffafb5e0aab90" in latest_git_version, (
        "Discourse v3.3.0 git version does not match with the database version"
    )

    juju.deploy("redis-k8s", base="ubuntu@22.04", channel="latest/edge")
    juju.wait(
        lambda status: "redis-k8s" in status.apps and status.apps["redis-k8s"].is_active,
        timeout=JUJU_WAIT_TIMEOUT,
    )

    juju.deploy("nginx-ingress-integrator", base="ubuntu@22.04", trust=True)

    discourse_app_name = "discourse-k8s"
    juju.deploy(
        charm=charm_file,
        app=discourse_app_name,
        resources=charm_resource_images[discourse_app_name],
        base=charm_base,
    )
    juju.wait(
        lambda status: discourse_app_name in status.apps
        and status.apps[discourse_app_name].is_waiting,
        timeout=JUJU_WAIT_TIMEOUT,
    )

    juju.integrate(discourse_app_name, pg_app_name + ":database")

    db_relation_user = None
    db_relation_password = None
    for _ in range(30):
        show_unit = json.loads(
            juju.cli("show-unit", "--format", "json", discourse_app_name + "/0")
        )
        relation_info = show_unit[discourse_app_name + "/0"]["relation-info"]
        database_relation = next(
            (relation for relation in relation_info if relation["endpoint"] == "database"),
            None,
        )
        secret_uri = (
            database_relation["application-data"].get("secret-user") if database_relation else None
        )
        if not secret_uri:
            time.sleep(2)
            continue
        secret_id = secret_uri.rsplit("/", 1)[-1]
        db_credentials = json.loads(
            juju.cli("show-secret", "--reveal", "--format", "json", secret_id)
        )
        db_relation_user = db_credentials[secret_id]["content"]["Data"]["username"]
        db_relation_password = db_credentials[secret_id]["content"]["Data"]["password"]
        if db_relation_user and db_relation_password:
            break
        time.sleep(2)
    assert db_relation_user, "Discourse database relation user not found"
    assert db_relation_password, "Discourse database relation password not found"

    db_effective_user = juju.cli(
        "ssh",
        "--container",
        "postgresql",
        pg_app_name + "/0",
        f"psql -h localhost -U {db_relation_user} --password -d discourse "
        "-tAc 'SELECT current_user;'",
        stdin=db_relation_password + "\n",
    ).strip()
    assert db_effective_user, "Discourse database effective role not found"

    juju.cli(
        "ssh",
        "--container",
        "postgresql",
        pg_app_name + "/0",
        "psql -h localhost -U operator --password -d discourse -v ON_ERROR_STOP=1 "  # nosec B608
        f'-c "DO \\$\\$ DECLARE r RECORD; '
        f"owner_role TEXT := '{db_effective_user}'; "
        f"BEGIN "
        f"EXECUTE format('ALTER SCHEMA public OWNER TO %I', owner_role); "
        f"FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP "
        f"EXECUTE format('ALTER TABLE public.%I OWNER TO %I', r.tablename, owner_role); "
        f"END LOOP; "
        f"FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public' LOOP "
        f"EXECUTE format('ALTER SEQUENCE public.%I OWNER TO %I', r.sequence_name, owner_role); "
        f"END LOOP; "
        f"END \\$\\$; "
        f'ALTER DATABASE discourse OWNER TO {db_effective_user};"',
        stdin=db_pass + "\n",
    )

    juju.integrate(discourse_app_name, "redis-k8s")
    juju.integrate(discourse_app_name, "nginx-ingress-integrator")
    juju.wait(
        lambda status: discourse_app_name in status.apps
        and status.apps[discourse_app_name].is_active,
        error=lambda status: discourse_app_name in status.apps
        and status.apps[discourse_app_name].is_error,
        timeout=JUJU_WAIT_TIMEOUT,
    )
