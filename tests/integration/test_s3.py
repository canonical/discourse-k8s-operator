#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest

from minio import Minio

from ops.model import Application
from pytest_operator.plugin import OpsTest


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
