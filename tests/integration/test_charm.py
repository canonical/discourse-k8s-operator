#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
import requests

from charm import SERVICE_PORT
from minio import Minio
from ops.model import ActiveStatus, Application
from pytest_operator.plugin import OpsTest


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_active(app: Application):
    """Check that the charm is active.
    Assume that the charm has already been built and is running.
    """
    assert app.units[0].workload_status == ActiveStatus.name


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_discourse_up(ops_test: OpsTest, app: Application):
    """Check that the bootstrap page is reachable.
    Assume that the charm has already been built and is running.
    """

    # TODO: Simplify should be available from ops_test.model.unit
    status = await ops_test.model.get_status()
    unit = list(status.applications[app.name].units)[0]
    address = status["applications"][app.name]["units"][unit]["address"]
    # Send request to bootstrap page and set Host header to app_name (which the application
    # expects)
    response = requests.get(
        f"http://{address}:{SERVICE_PORT}/finish-installation/register", headers={"Host": f"{app.name}.local"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_s3_conf(ops_test: OpsTest, app: Application):
    """Check that the bootstrap page is reachable
    with the charm configured with an S3 target
    Assume that the charm has already been built and is running.
    """

    config = {
        "access-key": "my-lovely-key",
        "secret-key": "this-is-very-secret"
    }

    minio = await ops_test.model.deploy("minio", config=config)
    await ops_test.model.wait_for_idle(status="active")

    minio_address = minio.units[0].public_address

    # Create a bucket
    minio_client = Minio(minio_address, access_key=config["access-key"], secret_key=config["secret-key"])
    minio_client.make_bucket("integration_tests")

    app.units[0].set_config({
        "s3_enabled": True,
        "s3_endpoint": f"{minio_address}:9000",
        "s3_bucket": "integration_tests",
        "s3_secret_access_key": "this-is-very-secret",
        "s3_access_key_id": "my-lovely-key",
    })

    objects = minio_client.list_objects("integration_tests")
    assert objects is not None