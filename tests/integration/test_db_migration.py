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
    arrange: preload postgres with a mock db that is created in Discource v3.2.0
    act: deploy and integrate with discourse v3.3.0
    assert: discourse must be active idle, previously it was creating migration
    errors related to not being able to delete some columns because of triggers
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
    # configure postgres
    await postgres_app.set_config(
        {
            "plugin_hstore_enable": "true",
            "plugin_pg_trgm_enable": "true",
        }
    )
    await model.wait_for_idle(apps=[postgres_app.name], status="active")
    db_pass = await run_action(postgres_app.name, "get-password", username="operator")
    db_pass = db_pass["password"]
    return_code, _, _ = await ops_test.juju(
        "scp",
        "--container",
        "postgresql",
        "./mock_db",
        f"{postgres_app.units[0].name}:.",
    )
    assert return_code == 0

    return_code, _, _ = await ops_test.juju(
        "ssh",
        "--container",
        "postgresql",
        postgres_app.units[0].name,
        "createdb -h localhost -U operator --password discourse",
        stdin=str.encode(f"{db_pass}\n"),
    )
    assert return_code == 0

    return_code, _, _ = await ops_test.juju(
        "ssh",
        "--container",
        "postgresql",
        postgres_app.units[0].name,
        "pg_restore -h localhost -U operator\
              --password -d discourse\
                  --no-owner --clean --if-exists ./mock_db",
        stdin=str.encode(f"{db_pass}\n"),
    )
    assert return_code == 0
    redis_app = await model.deploy("redis-k8s", series="jammy", channel="latest/edge")
    await model.wait_for_idle(apps=[redis_app.name], status="active")

    resources = {"discourse-image": pytestconfig.getoption("--discourse-image")}
    charm = await ops_test.build_charm(".")
    await model.deploy("nginx-ingress-integrator", series="focal", trust=True)
    app_name = "discourse-k8s"
    discourse_application = await model.deploy(
        charm,
        resources=resources,
        application_name=app_name,
        series="focal",
    )
    await model.wait_for_idle(apps=[app_name], status="waiting")
    # Add required relations
    unit = discourse_application.units[0]
    assert unit.workload_status == WaitingStatus.name  # type: ignore
    await model.add_relation(app_name, "postgresql-k8s:database")
    await model.add_relation(app_name, "redis-k8s")
    await model.add_relation(app_name, "nginx-ingress-integrator")
    await model.wait_for_idle(apps=[app_name], status="active", raise_on_error=True)
    await model.wait_for_idle(apps=[app_name], status="active", raise_on_error=True)
