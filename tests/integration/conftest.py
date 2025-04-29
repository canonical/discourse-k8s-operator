# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests fixtures."""

import logging
import pathlib
import secrets
import subprocess  # nosec B404
from collections.abc import Generator
from typing import Any, Dict, cast

import jubilant
import pytest
import requests
import yaml
from saml_test_helper import SamlK8sTestHelper  # pylint: disable=import-error

from . import types

logger = logging.getLogger(__name__)

ENABLED_PLUGINS = [
    "solved",
    "saml",
    "calendar",
    "data_explorer",
    "discourse_gamification",
    "chat_integration",
]


@pytest.fixture(scope="session")
def metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(pathlib.Path("./metadata.yaml").read_text(encoding="UTF-8"))


@pytest.fixture(scope="session")
def app_config():
    """Provides app config."""
    yield {
        "developer_emails": "noreply@canonical.com",
        "external_hostname": "discourse-k8s",
        "smtp_address": "test.local",
        "smtp_domain": "test.local",
        "s3_install_cors_rule": "false",
    }


@pytest.fixture(scope="session")
def localstack_address(pytestconfig: pytest.Config):
    """Provides localstack IP address to be used in the integration test"""
    yield pytestconfig.getoption("--localstack-address")


@pytest.fixture(scope="session")
def saml_email(pytestconfig: pytest.Config):
    """SAML login email address test argument for SAML integration tests"""
    email = pytestconfig.getoption("--saml-email")
    if not email:
        raise ValueError("--saml-email argument is required for selected test cases")
    return email


@pytest.fixture(scope="session")
def saml_password(pytestconfig: pytest.Config):
    """SAML login password test argument for SAML integration tests"""
    password = pytestconfig.getoption("--saml-password")
    if not password:
        raise ValueError("--saml-password argument is required for selected test cases")
    return password


@pytest.fixture(scope="session")
def requests_timeout():
    """Provides a global default timeout for HTTP requests"""
    yield 15


@pytest.fixture(scope="module", name="discourse_address")
def discourse_address_fixture(app: types.App, juju: jubilant.Juju):
    """Get discourse web address."""
    status = juju.status()
    unit_ip = status.apps[app.name].units[app.name + "/0"].address
    return f"http://{unit_ip}:3000"


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """Pytest fixture that wraps :meth:`jubilant.with_model`."""

    def show_debug_log(juju: jubilant.Juju):
        if request.session.testsfailed:
            log = juju.debug_log(limit=1000)
            print(log, end="")

    use_existing = request.config.getoption("--use-existing", default=False)
    if use_existing:
        juju = jubilant.Juju()
        yield juju
        show_debug_log(juju)
        return

    model = request.config.getoption("--model")
    if model:
        juju = jubilant.Juju(model=model)
        yield juju
        show_debug_log(juju)
        return

    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = 10 * 60
        yield juju
        show_debug_log(juju)
        return


@pytest.fixture(scope="session")
def charm_file(metadata: Dict[str, Any], pytestconfig: pytest.Config):
    """Pytest fixture that packs the charm and returns the filename, or --charm-file if set."""
    charm_file = pytestconfig.getoption("--charm-file")
    if charm_file:
        yield charm_file
        return

    try:
        subprocess.run(
            ["charmcraft", "pack"], check=True, capture_output=True, text=True
        )  # nosec B603, B607
    except subprocess.CalledProcessError as exc:
        raise OSError(f"Error packing charm: {exc}; Stderr:\n{exc.stderr}") from None

    app_name = metadata["name"]
    charm_path = pathlib.Path(__file__).parent.parent.parent
    charms = [p.absolute() for p in charm_path.glob(f"{app_name}_*.charm")]
    assert charms, f"{app_name} .charm file not found"
    assert len(charms) == 1, f"{app_name} has more than one .charm file, unsure which to use"
    yield str(charms[0])


@pytest.fixture(scope="module", name="app")
def app_fixture(
    juju: jubilant.Juju,
    metadata: Dict[str, Any],
    app_config: Dict[str, str],
    pytestconfig: pytest.Config,
    charm_file: str,
):
    # pylint: disable=too-many-locals
    """Discourse charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    app_name = metadata["name"]

    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing:
        yield types.App(app_name)
        return

    juju.deploy(
        "postgresql-k8s",
        channel="14/stable",
        base="ubuntu@22.04",
        revision=300,
        trust=True,
        config={"profile": "testing"},
    )
    juju.deploy("redis-k8s", base="ubuntu@22.04", channel="latest/edge")
    juju.wait(
        lambda status: jubilant.all_active(status, "postgresql-k8s", "redis-k8s"),
        timeout=20 * 60,
    )

    juju.deploy("nginx-ingress-integrator", base="ubuntu@20.04", trust=True)

    resources = {
        "discourse-image": pytestconfig.getoption("--discourse-image"),
    }

    juju.deploy(
        charm=charm_file,
        app=app_name,
        resources=resources,
        config=app_config,
        base="ubuntu@20.04",
    )

    juju.wait(lambda status: jubilant.all_waiting(status, app_name))

    # configure postgres
    juju.config(
        "postgresql-k8s",
        {
            "plugin_hstore_enable": "true",
            "plugin_pg_trgm_enable": "true",
        },
    )
    juju.wait(lambda status: jubilant.all_active(status, "postgresql-k8s"))

    # Add required relations
    status = juju.status()
    assert status.apps[app_name].units[app_name + "/0"].is_waiting
    juju.integrate(app_name, "postgresql-k8s:database")
    juju.integrate(app_name, "redis-k8s")
    juju.integrate(app_name, "nginx-ingress-integrator")
    juju.wait(jubilant.all_active)

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
    task = juju.exec(full_command, unit=app_name + "/0")
    logger.info(task.results)

    yield types.App(app_name)


@pytest.fixture(scope="module")
def setup_saml_config(juju: jubilant.Juju, app: types.App):
    """Set SAML related charm config to enable SAML authentication."""
    juju.config(app.name, {"force_https": True})

    saml_helper = SamlK8sTestHelper.deploy_saml_idp(juju.model)
    juju.deploy(
        "saml-integrator",
        channel="latest/edge",
        base="ubuntu@22.04",
        trust=True,
    )

    juju.wait(jubilant.all_agents_idle)
    saml_helper.prepare_pod(juju.model, "saml-integrator-0")
    saml_helper.prepare_pod(juju.model, f"{app.name}-0")
    juju.wait(jubilant.all_agents_idle)
    juju.config(
        "saml-integrator",
        {
            "entity_id": saml_helper.entity_id,
            "metadata_url": saml_helper.metadata_url,
        },
    )
    juju.integrate(app.name, "saml-integrator")
    juju.wait(jubilant.all_agents_idle)

    yield saml_helper


@pytest.fixture(scope="module", name="admin_credentials")
def admin_credentials_fixture(juju: jubilant.Juju, app: types.App) -> types.Credentials:
    """Admin user credentials."""
    email = f"admin-user{secrets.randbits(32)}@test.internal"
    task = juju.run(f"{app.name}/0", "create-user", {"email": email, "admin": True})
    password = task.results["password"]
    admin_credentials = types.Credentials(
        email=email, username=email.split("@", maxsplit=1)[0], password=password
    )
    return admin_credentials


@pytest.fixture(scope="module", name="admin_api_key")
def admin_api_key_fixture(admin_credentials: types.Credentials, discourse_address: str) -> str:
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


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Pytest hook wrapper to set the test's rep_* attribute for abort_on_fail."""
    _ = call  # unused argument
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture(autouse=True)
def abort_on_fail(request: pytest.FixtureRequest):
    """Fixture which aborts other tests in module after first fails."""
    abort_on_fail = request.node.get_closest_marker("abort_on_fail")
    if abort_on_fail and getattr(request.module, "__aborted__", False):
        pytest.xfail("abort_on_fail")

    _ = yield

    if abort_on_fail and request.node.rep_call.failed:
        request.module.__aborted__ = True
