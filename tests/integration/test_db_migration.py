#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging

import pytest
from botocore.config import Config
from ops.model import WaitingStatus
from pytest_operator.plugin import Model, OpsTest

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_db_migration(model: Model, ops_test: OpsTest, pytestconfig: Config, run_action):
    """
    arrange: preload postgres with a testing db that is created in Discourse v3.2.0
    act: deploy and integrate with Discourse v3.3.0 (latest)
    assert: discourse is active/idle

    Discourse must be active idle, it might create migration errors related to
    not being able to delete some columns because of triggers. This is fixed
    with a patch but this patch only works for Discourse v3.2.0 and we might
    need to create a new patch for the new version of Discourse.
    """
    postgres_app = await model.deploy(
        "postgresql-k8s",
        channel="14/stable",
        series="jammy",
        revision=300,
        trust=True,
        config={"profile": "testing"},
    )
    async with ops_test.fast_forward():
        await model.wait_for_idle(apps=[postgres_app.name], status="active")
    await postgres_app.set_config(
        {
            "plugin_hstore_enable": "true",
            "plugin_pg_trgm_enable": "true",
        }
    )
    await model.wait_for_idle(apps=[postgres_app.name], status="active")
    db_pass = await run_action(postgres_app.name, "get-password", username="operator")
    db_pass = db_pass["password"]
    return_code, _, scp_err = await ops_test.juju(
        "scp",
        "--container",
        "postgresql",
        "./testing_database/testing_database.sql",
        f"{postgres_app.units[0].name}:.",
    )

    assert return_code == 0, scp_err

    return_code, _, ssh_err = await ops_test.juju(
        "ssh",
        "--container",
        "postgresql",
        postgres_app.units[0].name,
        "createdb -h localhost -U operator --password discourse",
        stdin=str.encode(f"{db_pass}\n"),
    )
    assert return_code == 0, ssh_err

    return_code, _, ssh_err = await ops_test.juju(
        "ssh",
        "--container",
        "postgresql",
        postgres_app.units[0].name,
        "pg_restore -h localhost -U operator\
              --password -d discourse\
                  --no-owner --clean --if-exists ./testing_database.sql",
        stdin=str.encode(f"{db_pass}\n"),
    )
    assert return_code == 0, ssh_err

    # ensure we are using the Discourse v3.2.0 database
    # Discourse v3.2.0 uses the git commit hash:
    # f9502188a646cdb286ae6572ad6198c711ecdea8
    return_code, latest_git_version, _ = await ops_test.juju(
        "ssh",
        "--container",
        "postgresql",
        postgres_app.units[0].name,
        "psql -h localhost -U operator\
              --password -d discourse\
                  -c 'SELECT git_version FROM schema_migration_details LIMIT 1;'",
        stdin=str.encode(f"{db_pass}\n"),
    )
    assert (
        "f9502188a646cdb286ae6572ad6198c711ecdea8" in latest_git_version
    ), "Discourse v3.2.0 git version does not match with the database version"

    redis_app = await model.deploy("redis-k8s", series="jammy", channel="latest/edge")
    await model.wait_for_idle(apps=[redis_app.name], status="active")

    charm = await ops_test.build_charm(".")
    await model.deploy("nginx-ingress-integrator", series="focal", trust=True)
    app_name = "discourse-k8s"
    discourse_application = await model.deploy(
        charm,
        resources={"discourse-image": pytestconfig.getoption("--discourse-image")},
        application_name=app_name,
        series="focal",
    )
    await model.wait_for_idle(apps=[app_name], status="waiting")
    unit = discourse_application.units[0]
    assert unit.workload_status == WaitingStatus.name  # type: ignore
    await model.add_relation(app_name, "postgresql-k8s:database")
    await model.add_relation(app_name, "redis-k8s")
    await model.add_relation(app_name, "nginx-ingress-integrator")
    await model.wait_for_idle(apps=[app_name], status="active", raise_on_error=True)
    await model.wait_for_idle(apps=[app_name], status="active", raise_on_error=True)
