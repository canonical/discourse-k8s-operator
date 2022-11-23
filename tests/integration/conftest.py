# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
from pathlib import Path
from typing import Dict

import pytest_asyncio
import yaml
from ops.model import WaitingStatus
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


@fixture(scope="module")
def app_config():
    """Provides app config."""
    yield {
        "developer_emails": "noreply@canonical.com",
        "external_hostname": "test.local:3000",
        "smtp_address": "test.local",
        "smtp_domain": "test.local",
        "s3_install_cors_rule": "false",
    }


@fixture(scope="module")
def s3_url(pytestconfig: Config):
    """Provides S3 IP address to inject to discourse hosts"""
    yield pytestconfig.getoption("--s3-url") if pytestconfig.getoption(
        "--s3-url"
    ) else "http://127.0.0.1:4566"


@fixture(scope="module")
def requests_timeout():
    """Provides a global default timeout for HTTP requests"""
    yield 15


@pytest_asyncio.fixture(scope="module")
async def app(ops_test: OpsTest, app_name: str, app_config: Dict[str, str], pytestconfig: Config):
    """Discourse charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    # Deploy relations to speed up overall execution
    await asyncio.gather(
        ops_test.model.deploy("postgresql-k8s", series="focal"),
        ops_test.model.deploy("redis-k8s", series="focal"),
    )

    charm = await ops_test.build_charm(".")
    resources = {
        "discourse-image": pytestconfig.getoption("--discourse-image"),
    }

    application = await ops_test.model.deploy(
        charm, resources=resources, application_name=app_name, config=app_config, series="focal"
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
