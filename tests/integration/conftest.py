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
from saml_test_helper import SamlK8sTestHelper  # pylint: disable=import-error

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
    # pylint: disable=too-many-locals
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
    async with ops_test.fast_forward():
        await model.wait_for_idle(apps=[postgres_app.name], status="active")

    # Revision 28 is being used due to https://github.com/canonical/redis-k8s-operator/issues/87.
    redis_app = await model.deploy("redis-k8s", series="jammy", channel="latest/edge", revision=28)
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
    await model.wait_for_idle(status="active")

    # Enable plugins calling rake site_settings:import in one of the units.
    inline_yaml = "\n".join(f"{plugin}_enabled: true" for plugin in ENABLED_PLUGINS)
    discourse_rake_command = "/srv/discourse/app/bin/bundle exec rake site_settings:import "
    pebble_exec = (
        "PEBBLE_SOCKET=/charm/containers/discourse/pebble.socket "
        "pebble exec --user=_daemon_ --context=discourse -w=/srv/discourse/app"
    )
    full_command = (
        "/bin/bash -c "
        f"'set -euo pipefail; echo \"{inline_yaml}\" | {pebble_exec} -- {discourse_rake_command}'"
    )
    logger.info("Enable plugins command: %s", full_command)
    action = await unit.run(full_command)
    await action.wait()
    logger.info(action.results)
    assert action.results["return-code"] == 0, "Enable plugins failed"

    yield application


@pytest_asyncio.fixture(scope="module")
async def setup_saml_config(app: Application, model: Model):
    """Set SAML related charm config to enable SAML authentication."""
    discourse_app = model.applications[app.name]
    original_config: dict = await discourse_app.get_config()
    original_config = {k: v["value"] for k, v in original_config.items()}
    await discourse_app.set_config({"force_https": "true"})

    saml_helper = SamlK8sTestHelper.deploy_saml_idp(model.name)
    saml_app: Application = await model.deploy(
        "saml-integrator",
        channel="latest/edge",
        series="jammy",
        trust=True,
    )
    await model.wait_for_idle()
    saml_helper.prepare_pod(model.name, f"{saml_app.name}-0")
    saml_helper.prepare_pod(model.name, f"{app.name}-0")
    await model.wait_for_idle()
    await saml_app.set_config(  # type: ignore[attr-defined]
        {
            "entity_id": saml_helper.entity_id,
            "metadata_url": saml_helper.metadata_url,
        }
    )
    await model.add_relation(app.name, "saml-integrator")
    await model.wait_for_idle()

    yield saml_helper


@pytest_asyncio.fixture(scope="module", name="admin_credentials")
async def admin_credentials_fixture(app: Application) -> types.Credentials:
    """Admin user credentials."""
    email = f"admin-user{secrets.randbits(32)}@test.internal"
    discourse_unit: Unit = app.units[0]
    action: Action = await discourse_unit.run_action("create-user", email=email, admin=True)
    await action.wait()
    password = action.results["password"]
    admin_credentials = types.Credentials(
        email=email, username=email.split("@", maxsplit=1)[0], password=password
    )
    return admin_credentials


@pytest_asyncio.fixture(scope="module", name="admin_api_key")
async def admin_api_key_fixture(
    admin_credentials: types.Credentials, discourse_address: str
) -> str:
    """Admin user API key"""
    with requests.session() as session:
        # Get CSRF token
        response = session.get(
            f"{discourse_address}/session/csrf", headers={"Accept": "application/json"}
        )
        # pylint doesn't see the "ok" member
        assert response.ok, response.text  # pylint: disable=no-member
        data = response.json()
        assert data["csrf"], data
        csrf = data["csrf"]
        # Create session & login
        response = session.post(
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
        assert response.ok, response.text  # pylint: disable=no-member
        assert "error" not in response.json()
        # Create global key
        response = session.post(
            f"{discourse_address}/admin/api/keys",
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            json={"key": {"description": "admin-api-key", "username": None}},
        )
        # pylint doesn't see the "ok" member
        assert response.ok, response.text  # pylint: disable=no-member

    data = response.json()
    assert data["key"]["key"], data
    return data["key"]["key"]
