# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
import pytest_asyncio
import yaml

from ops.model import WaitingStatus
from pathlib import Path
from pytest import Config, fixture
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@fixture(scope="module")
def metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture(scope="module")
def app_name(metadata):
    """Provides app name from the metadata."""
    yield metadata["name"]


@pytest_asyncio.fixture(scope="module")
async def app(ops_test: OpsTest, app_name: str, pytestconfig: Config):
    """Discourse charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    # Deploy relations to speed up overall execution
    await asyncio.gather(
        ops_test.model.deploy("postgresql-k8s"),
        ops_test.model.deploy("redis-k8s"),
    )

    charm = await ops_test.build_charm(".")
    resources = {
        "discourse-image": pytestconfig.getoption("--discourse-image"),
    }
    config = {
        "developer_emails": "noreply@canonical.com",
        "external_hostname": "test.local",
        "smtp_domain": "test.local"
    }
    application = await ops_test.model.deploy(
        charm, resources=resources, application_name=app_name, config=config
    )
    await ops_test.model.wait_for_idle()

    # Add required relations
    assert ops_test.model.applications[app_name].units[0].workload_status == WaitingStatus.name
    await asyncio.gather(
        ops_test.model.add_relation(app_name, "postgresql-k8s:db-admin"),
        ops_test.model.add_relation(app_name, "redis-k8s"),
    )
    await ops_test.model.wait_for_idle(status="active")

    yield application