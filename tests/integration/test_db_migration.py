#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging

import jubilant
import pytest

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_db_migration(juju: jubilant.Juju, pytestconfig: pytest.Config, charm_file: str):
    """
    arrange: preload postgres with a testing db that is created in Discourse v3.2.0
    act: deploy and integrate with Discourse v3.3.0 (latest)
    assert: discourse is active/idle

    Discourse must be active idle, it might create migration errors related to
    not being able to delete some columns because of triggers. This is fixed
    with a patch but this patch only works for Discourse v3.2.0 and we might
    need to create a new patch for the new version of Discourse.
    """
    pg_app_name = "postgresql-k8s"
    juju.deploy(
        pg_app_name,
        channel="14/stable",
        base="ubuntu@22.04",
        revision=300,
        trust=True,
        config={"profile": "testing"},
    )
    juju.wait(lambda status: status.apps[pg_app_name].is_active, timeout=20 * 60)
    juju.config(
        pg_app_name,
        {
            "plugin_hstore_enable": "true",
            "plugin_pg_trgm_enable": "true",
        },
    )
    juju.wait(lambda status: status.apps[pg_app_name].is_active)
    task = juju.run(pg_app_name + "/0", "get-password", {"username": "operator"})
    db_pass = task.results["password"]
    juju.cli(
        "scp",
        "--container",
        "postgresql",
        "./testing_database/testing_database.sql",
        pg_app_name + "/0:.",
    )

    juju.cli(
        "ssh",
        "--container",
        "postgresql",
        pg_app_name + "/0",
        "createdb -h localhost -U operator --password discourse",
        stdin=db_pass + "\n",
    )

    juju.cli(
        "ssh",
        "--container",
        "postgresql",
        pg_app_name + "/0",
        "pg_restore -h localhost -U operator \
              --password -d discourse \
              --no-owner --clean --if-exists ./testing_database.sql",
        stdin=db_pass + "\n",
    )

    # ensure we are using the Discourse v3.2.0 database
    # Discourse v3.2.0 uses the git commit hash:
    # f9502188a646cdb286ae6572ad6198c711ecdea8
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
    assert (
        "f9502188a646cdb286ae6572ad6198c711ecdea8" in latest_git_version
    ), "Discourse v3.2.0 git version does not match with the database version"

    juju.deploy("redis-k8s", base="ubuntu@22.04", channel="latest/edge")
    juju.wait(lambda status: status.apps["redis-k8s"].is_active)

    juju.deploy("nginx-ingress-integrator", base="ubuntu@20.04", trust=True)

    discourse_app_name = "discourse-k8s"
    juju.deploy(
        charm=charm_file,
        app=discourse_app_name,
        resources={"discourse-image": pytestconfig.getoption("--discourse-image")},
        base="ubuntu@20.04",
    )
    juju.wait(lambda status: status.apps[discourse_app_name].is_waiting)

    juju.integrate(discourse_app_name, pg_app_name + ":database")
    juju.integrate(discourse_app_name, "redis-k8s")
    juju.integrate(discourse_app_name, "nginx-ingress-integrator")
    juju.wait(
        lambda status: status.apps[discourse_app_name].is_active,
        error=lambda status: status.apps[discourse_app_name].is_error,
    )
