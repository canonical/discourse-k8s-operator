# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests fixtures."""

import asyncio
import logging
import secrets
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, cast

import pytest_asyncio
import requests
import yaml
from juju.action import Action
from juju.application import Application
from juju.client._definitions import ApplicationStatus, FullStatus, UnitStatus
from juju.unit import Unit
from ops.model import WaitingStatus
from pytest import Config, fixture
from pytest_operator.plugin import Model, OpsTest

from . import types

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
def localstack_address(pytestconfig: Config):
    """Provides localstack IP address to be used in the integration test"""
    address = pytestconfig.getoption("--localstack-address")
    if not address:
        raise ValueError("--localstack-address argument is required for selected test cases")
    yield address


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


@pytest_asyncio.fixture(scope="module", name="discourse_address")
async def discourse_address_fixture(model: Model, app: Application):
    """Get discourse web address."""
    status: FullStatus = await model.get_status()
    app_status = cast(ApplicationStatus, status.applications[app.name])
    unit_status = cast(UnitStatus, app_status.units[f"{app.name}/0"])
    unit_ip = cast(str, unit_status.address)
    return f"http://{unit_ip}:3000"


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
        ops_test.juju(
            "deploy",
            "postgresql-k8s",
            "--channel",
            "latest/stable",
            "--trust"
            check=True
        ),
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
    await model.wait_for_idle(status="active", raise_on_error=False)

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


@pytest_asyncio.fixture(scope="module", name="admin_credentials")
async def admin_credentials_fixture(app: Application) -> types.Credentials:
    """Admin user credentials."""
    email = "admin-user@test.internal"
    password = secrets.token_urlsafe(16)
    discourse_unit: Unit = app.units[0]
    action: Action = await discourse_unit.run_action(
        "add-admin-user", email=email, password=password
    )
    await action.wait()
    return types.Credentials(
        email=email, username=email.split("@", maxsplit=1)[0], password=password
    )


@pytest_asyncio.fixture(scope="module", name="admin_api_key")
async def admin_api_key_fixture(
    admin_credentials: types.Credentials, discourse_address: str
) -> str:
    """Admin user API key"""
    with requests.session() as sess:
        # Get CSRF token
        res = sess.get(f"{discourse_address}/session/csrf", headers={"Accept": "application/json"})
        csrf = res.json()["csrf"]
        # Create session & login
        res = sess.post(
            f"{discourse_address}/session",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            data={
                "login": admin_credentials.email,
                "password": admin_credentials.password,
                "second_factor_method": "1",
                "timezone": "Asia/Hong_Kong",
            },
        )
        # Create global key
        res = sess.post(
            f"{discourse_address}/admin/api/keys",
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            json={"key": {"description": "admin-api-key", "username": None}},
        )

    return res.json()["key"]["key"]
