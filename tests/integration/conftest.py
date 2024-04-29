# Copyright 2024 Canonical Ltd.
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

ENABLED_PLUGINS = [
    "solved",
    "saml",
    "calendar",
    "data_explorer",
    "discourse_gamification",
]


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
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing:
        yield model.applications[app_name]
        return

    postgres_app = await model.deploy(
        "postgresql-k8s",
        channel="14/edge",
        series="jammy",
        trust=True,
        config={"profile": "testing"},
    )
    await model.wait_for_idle(apps=[postgres_app.name], status="active")

    redis_app = await model.deploy("redis-k8s", series="jammy", channel="latest/edge")
    await model.wait_for_idle(apps=[redis_app.name], status="active")

    await model.deploy("nginx-ingress-integrator", series="focal", trust=True)

    resources = {
        "discourse-image": pytestconfig.getoption("--discourse-image"),
    }

    if charm := pytestconfig.getoption("--charm-file"):
        application = await model.deploy(
            f"./{charm}",
            resources=resources,
            application_name=app_name,
            config=app_config,
            series="focal",
        )
    else:
        charm = await ops_test.build_charm(".")
        application = await model.deploy(
            charm,
            resources=resources,
            application_name=app_name,
            config=app_config,
            series="focal",
        )

    await model.wait_for_idle(apps=[application.name], status="waiting")

    # configure postgres
    await postgres_app.set_config(
        {
            "plugin_hstore_enable": "true",
            "plugin_pg_trgm_enable": "true",
        }
    )
    await model.wait_for_idle(apps=[postgres_app.name], status="active")

    # Add required relations
    unit = model.applications[app_name].units[0]
    assert unit.workload_status == WaitingStatus.name  # type: ignore
    await asyncio.gather(
        model.add_relation(app_name, "postgresql-k8s:database"),
        model.add_relation(app_name, "redis-k8s"),
        model.add_relation(app_name, "nginx-ingress-integrator"),
    )
    await model.wait_for_idle(apps=[application.name], status="active", raise_on_error=False)
    # Doing multiple exec calls here to avoid complicated and error-prone bash one-liners
    # This won't be too costly in terms of performance since we only enable a few plugins
    # and this is only a temporary solution which will be replaced with an enable_plugins
    # action in the future
    for plugin in ENABLED_PLUGINS:
        enable_plugins_command = (
            "pebble exec --user=_daemon_ --context=discourse -w=/srv/discourse/app -ti -- /bin/bash -c "
            f""""echo '{plugin}_enabled: true' | """
            '''/srv/discourse/app/bin/bundle exec rake site_settings:import -"'''
        )
        logger.info("enabling plugin: %s", plugin)
        logger.info("running command: %s", enable_plugins_command)
        return_code, stdout, stderr = await ops_test.juju(
            "ssh", "--container", "discourse", unit.name, f"'''{enable_plugins_command}'''"
        )
        logger.info("command stdout: %s", stdout)
        assert (
            return_code == 0 and f"{plugin}_enabled: true" in stdout
        ), f"Enabling plugins failed, stderr: {stderr}"

    yield application


@pytest_asyncio.fixture(scope="module")
async def setup_saml_config(app: Application, model: Model):
    """Set SAML related charm config to enable SAML authentication."""
    discourse_app = model.applications[app.name]
    original_config: dict = await discourse_app.get_config()
    original_config = {k: v["value"] for k, v in original_config.items()}
    await discourse_app.set_config({"force_https": "true"})
    yield
    await discourse_app.set_config(
        {
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
    admin_credentials = types.Credentials(
        email=email, username=email.split("@", maxsplit=1)[0], password=password
    )
    return admin_credentials


@pytest_asyncio.fixture(scope="module", name="admin_api_key")
async def admin_api_key_fixture(
    admin_credentials: types.Credentials, discourse_address: str
) -> str:
    """Admin user API key"""
    with requests.session() as sess:
        # Get CSRF token
        res = sess.get(f"{discourse_address}/session/csrf", headers={"Accept": "application/json"})
        # pylint doesn't see the "ok" member
        assert res.status_code == requests.codes.ok, res.text  # pylint: disable=no-member
        data = res.json()
        assert data["csrf"], data
        csrf = data["csrf"]
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
        # pylint doesn't see the "ok" member
        assert res.status_code == requests.codes.ok, res.text  # pylint: disable=no-member
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
        # pylint doesn't see the "ok" member
        assert res.status_code == requests.codes.ok, res.text  # pylint: disable=no-member

    data = res.json()
    assert data["key"]["key"], data
    return data["key"]["key"]
