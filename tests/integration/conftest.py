# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests fixtures."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

import pytest_asyncio
import yaml
from ops.model import Application, WaitingStatus
from pytest import Config, fixture
from pytest_operator.plugin import Model, OpsTest

logger = logging.getLogger(__name__)


@fixture(scope="module", name="metadata")
def fixture_metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(Path("./metadata.yaml").read_text(encoding="UTF-8"))


@fixture(scope="module", name="app_name")
def fixture_app_name(metadata):
    """Provides app name from the metadata."""
    yield metadata["name"]


@fixture(scope="module", name="app_config")
def fixture_app_config():
    """Provides app config."""
    yield {
        "developer_emails": "noreply@canonical.com",
        "external_hostname": "discourse-k8s",
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
def saml_email(pytestconfig: Config):
    """SAML login email address test argument for SAML integration tests"""
    email = pytestconfig.getoption("--saml-email")
    if not email:
        raise ValueError("--saml-email argument is required for selected test cases")
    return email


@fixture(scope="module")
def saml_password(pytestconfig: Config):
    """SAML login password test argument for SAML integration tests"""
    password = pytestconfig.getoption("--saml-password")
    if not password:
        raise ValueError("--saml-password argument is required for selected test cases")
    return password


@fixture(scope="module")
def requests_timeout():
    """Provides a global default timeout for HTTP requests"""
    yield 15


@fixture(scope="module", name="model")
def model_fixture(ops_test: OpsTest) -> Model:
    """Juju model API client."""
    assert ops_test.model
    return ops_test.model


@fixture(scope="module")
def run_action(model: Model) -> Callable[..., Awaitable[Any]]:
    """Create an async function to run action and return results."""

    async def _run_action(application_name: str, action_name: str, **params):
        """Run a specified action.

        Args:
            application_name: Name the application is deployed with.
            action_name: Name of the action to be executed.
            params: Dictionary with action parameters.

        Returns:
            The results of the executed action
        """
        application = model.applications[application_name]
        action = await application.units[0].run_action(action_name, **params)
        await action.wait()
        return action.results

    return _run_action


@pytest_asyncio.fixture(scope="module", name="app")
async def app_fixture(
    ops_test: OpsTest,
    app_name: str,
    app_config: Dict[str, str],
    pytestconfig: Config,
    model: Model,
):
    """Discourse charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    # Deploy relations to speed up overall execution
    await asyncio.gather(
        model.deploy("postgresql-k8s", series="focal"),
        model.deploy("redis-k8s", series="focal"),
        model.deploy("nginx-ingress-integrator", series="focal", trust=True),
    )

    charm = await ops_test.build_charm(".")
    resources = {
        "discourse-image": pytestconfig.getoption("--discourse-image"),
    }

    application = await model.deploy(
        charm, resources=resources, application_name=app_name, config=app_config, series="focal"
    )
    await model.wait_for_idle()

    # Add required relations
    unit = model.applications[app_name].units[0]
    assert unit.workload_status == WaitingStatus.name  # type: ignore
    await asyncio.gather(
        model.add_relation(app_name, "postgresql-k8s:db-admin"),
        model.add_relation(app_name, "redis-k8s"),
        model.add_relation(app_name, "nginx-ingress-integrator"),
    )
    await model.wait_for_idle(status="active")

    yield application


@pytest_asyncio.fixture(scope="module")
async def setup_saml_config(app: Application, model: Model):
    """Set SAML related charm config to enable SAML authentication."""
    discourse_app = model.applications[app.name]
    original_config: dict = await discourse_app.get_config()
    original_config = {k: v["value"] for k, v in original_config.items()}
    await discourse_app.set_config(
        {"saml_target_url": "https://login.staging.ubuntu.com/+saml", "force_https": "true"}
    )
    yield
    await discourse_app.set_config(
        {
            "saml_target_url": original_config["saml_target_url"],
            "force_https": str(original_config["force_https"]).lower(),
        }
    )
