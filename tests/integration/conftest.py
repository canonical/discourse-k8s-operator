# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
import re
from pathlib import Path
from typing import Dict

import pytest_asyncio
import yaml
from ops.model import ActiveStatus, Application, WaitingStatus
from pytest import Config, fixture
from pytest_operator.plugin import OpsTest
from typing import Any, Awaitable, Callable, List

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
        "external_hostname": "test.local",
        "smtp_address": "test.local",
        "smtp_domain": "test.local",
        "s3_install_cors_rule": "false",
    }


@fixture(scope="module")
def run_action(ops_test: OpsTest) -> Callable[[str, str], Awaitable[Any]]:
    """Create a async function to run action and return results."""

    async def _run_action(application_name: str, action_name: str, **params):
        """Run a specified action.

        Args:
            application_name: Name the application is deployed with.
            action_name: Name of the action to be executed.
            params: Dictionary with action parameters.

        Returns:
            The results of the executed action
        """
        application = ops_test.model.applications[application_name]
        action = await application.units[0].run_action(action_name, **params)
        await action.wait()
        return action.results

    return _run_action


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
async def nginx_integrator_app(ops_test: OpsTest):
    """Deploy nginx-ingress-integrator charm."""
    nginx_integrator_app_name = "nginx-ingress-integrator"
    nginx_integrator_app = await ops_test.model.deploy(nginx_integrator_app_name, trust=True)
    await ops_test.model.wait_for_idle()
    assert (
        ops_test.model.applications[nginx_integrator_app_name].units[0].workload_status
        == ActiveStatus.name
    )
    yield nginx_integrator_app


@pytest_asyncio.fixture(scope="module")
async def ip_address_list(ops_test: OpsTest, app: Application, nginx_integrator_app: Application):
    """Get unit IP address from workload message.

    Example: Ingress IP(s): 127.0.0.1, Service IP(s): 10.152.183.84
    """
    # Reduce the update_status frequency until the cluster is deployed
    async with ops_test.fast_forward():
        await ops_test.model.block_until(
            lambda: "Ingress IP(s)" in nginx_integrator_app.units[0].workload_status_message,
            timeout=100,
        )
    nginx_integrator_unit = nginx_integrator_app.units[0]
    status_message = nginx_integrator_unit.workload_status_message
    ip_regex = r"[0-9]+(?:\.[0-9]+){3}"
    ip_address_list = re.findall(ip_regex, status_message)
    assert ip_address_list, f"could not find IP address in status message: {status_message}"
    yield ip_address_list


@pytest_asyncio.fixture(scope="module")
async def ingress_ip(ip_address_list: List):
    """First match is the ingress IP."""
    yield ip_address_list[0]


@pytest_asyncio.fixture(scope="module")
async def service_ip(ip_address_list: List):
    """Last match is the service IP."""
    yield ip_address_list[-1]


@pytest_asyncio.fixture(scope="module")
async def app(
    ops_test: OpsTest,
    app_name: str,
    app_config: Dict[str, str],
    pytestconfig: Config,
    nginx_integrator_app: Application,
):
    """Discourse charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    assert ops_test.model
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
    assert ops_test.model.applications[app_name].units[0].workload_status == WaitingStatus.name  # type: ignore
    await asyncio.gather(
        ops_test.model.add_relation(app_name, "postgresql-k8s:db-admin"),
        ops_test.model.add_relation(app_name, "redis-k8s"),
        ops_test.model.add_relation(nginx_integrator_app.name, f"{app_name}:ingress"),
    )
    await ops_test.model.wait_for_idle(status="active")

    yield application
