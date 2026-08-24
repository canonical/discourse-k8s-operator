# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests fixtures."""

import logging
import os
import pathlib
import socket
import subprocess
import time
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
    "saml",
    "calendar",
    "data_explorer",
    "discourse_gamification",
    "chat_integration",
]

# Timeout for juju wait operations in seconds
JUJU_WAIT_TIMEOUT = 1200
POSTGRESQL_CHANNEL = "16/stable"
POSTGRESQL_BASE = "ubuntu@24.04"


def _cleanup_saml_integration(juju: jubilant.Juju, app_name: str) -> None:
    """Remove stale SAML relation/app from shared models to keep tests idempotent."""
    status = juju.status()
    if "saml-integrator" not in status.apps:
        return

    try:
        juju.remove_relation(app_name, "saml-integrator")
    except subprocess.CalledProcessError:
        pass

    juju.wait(jubilant.all_agents_idle, timeout=JUJU_WAIT_TIMEOUT)
    juju.cli("remove-application", "saml-integrator", "--force", "--no-wait", "--no-prompt")
    try:
        juju.wait(lambda current_status: "saml-integrator" not in current_status.apps, timeout=120)
    except TimeoutError:
        logger.warning("saml-integrator removal did not complete before cleanup timeout")


def _cleanup_saml_test_idp_pod(model_name: str) -> None:
    """Ensure the helper-managed SAML IdP pod does not persist across runs."""
    subprocess.run(
        ["kubectl", "--namespace", model_name, "delete", "pod", "saml-test-idp", "--ignore-not-found"],
        check=True,
    )


@pytest.fixture(scope="module")
def charm_base() -> str:
    """The base to deploy the charm on"""
    base = os.environ.get("JUJU_DEPLOY_BASE")
    if not base:
        # Returning the default base to stay consistent with current behavior
        return "ubuntu@22.04"
    return base


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


def _host_ip() -> str | None:
    """Return the host's primary outbound IP, reachable from microk8s pods."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


@pytest.fixture(scope="session")
def s3_address(pytestconfig: pytest.Config):
    """Provides the S3 service IP address to be used in integration tests.

    Defaults to the host's primary IP so microk8s pods can reach radosgw
    on the runner without needing --s3-address to be passed explicitly.
    """
    yield pytestconfig.getoption("--s3-address") or _host_ip()


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

    model = request.config.getoption("--model")
    use_existing = request.config.getoption("--use-existing", default=False)
    if use_existing:
        juju = jubilant.Juju(model=model) if model else jubilant.Juju()
        yield juju
        show_debug_log(juju)
        return

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
def charm_file(charm_paths, metadata: Dict[str, Any]):
    """Pytest fixture that returns the charm file path via opcli's charm_paths."""
    app_name = metadata["name"]
    return str(charm_paths[app_name].path)


@pytest.fixture(scope="module", name="app")
def app_fixture(
    juju: jubilant.Juju,
    metadata: Dict[str, Any],
    app_config: Dict[str, str],
    pytestconfig: pytest.Config,
    charm_file: str,
    charm_resource_images: dict[str, dict[str, str]],
    charm_base: str,
):  # pylint: disable=too-many-positional-arguments, too-many-arguments
    """Discourse charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    app_name = metadata["name"]
    charm_resources = charm_resource_images[app_name]

    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing:
        _cleanup_saml_integration(juju, app_name)
        status = juju.status()
        if any(app_state.is_error for app_state in status.apps.values()):
            juju.cli("resolved", "--all")

        juju.config(
            app_name,
            {
                "force_https": True,
                "s3_enabled": False,
                "s3_endpoint": "",
                "s3_bucket": "",
                "s3_secret_access_key": "",  # nosec B105
                "s3_access_key_id": "",
                "s3_region": "",
            },
        )
        juju.cli("resolved", "--all")

        def required_apps_ready(status: jubilant.Status) -> bool:
            if not status.apps[app_name].is_active:
                return False
            if not jubilant.all_active(status, "redis-k8s", "nginx-ingress-integrator"):
                return False
            return any(
                name.startswith("postgresql") and app.is_active for name, app in status.apps.items()
            )

        juju.wait(required_apps_ready, timeout=JUJU_WAIT_TIMEOUT)
        yield types.App(app_name)
        return

    juju.deploy(
        "postgresql-k8s",
        channel=POSTGRESQL_CHANNEL,
        base=POSTGRESQL_BASE,
        trust=True,
        config={"profile": "testing"},
    )
    juju.deploy("redis-k8s", base="ubuntu@22.04", channel="latest/edge")
    juju.wait(
        lambda status: jubilant.all_active(status, "postgresql-k8s", "redis-k8s"),
        timeout=20 * 60,
    )

    juju.deploy("nginx-ingress-integrator", base="ubuntu@22.04", trust=True)

    juju.deploy(
        charm=charm_file,
        app=app_name,
        resources=charm_resources,
        config=app_config,
        base=charm_base,
    )

    juju.wait(lambda status: jubilant.all_waiting(status, app_name))

    # configure postgres
    juju.config(
        "postgresql-k8s",
        {
            "plugin-hstore-enable": True,
            "plugin-pg-trgm-enable": True,
            "plugin-vector-enable": True,
        },
    )
    juju.wait(lambda status: jubilant.all_active(status, "postgresql-k8s"))

    # Add required relations
    juju.integrate(app_name, "postgresql-k8s:database")
    juju.integrate(app_name, "redis-k8s")
    juju.integrate(app_name, "nginx-ingress-integrator")
    juju.wait(jubilant.all_active, timeout=JUJU_WAIT_TIMEOUT)

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
    _cleanup_saml_integration(juju, app.name)
    _cleanup_saml_test_idp_pod(juju.model)
    juju.config(app.name, {"force_https": True})

    saml_helper = SamlK8sTestHelper.deploy_saml_idp(juju.model)
    juju.deploy(
        "saml-integrator",
        channel="latest/edge",
        base="ubuntu@22.04",
        trust=True,
    )

    juju.wait(jubilant.all_agents_idle, timeout=JUJU_WAIT_TIMEOUT)
    saml_helper.prepare_pod(juju.model, "saml-integrator-0")
    saml_helper.prepare_pod(juju.model, f"{app.name}-0")
    juju.wait(jubilant.all_agents_idle, timeout=JUJU_WAIT_TIMEOUT)
    juju.config(
        "saml-integrator",
        {
            "entity_id": saml_helper.entity_id,
            "metadata_url": saml_helper.metadata_url,
        },
    )
    juju.integrate(app.name, "saml-integrator")
    juju.wait(jubilant.all_agents_idle, timeout=JUJU_WAIT_TIMEOUT)

    yield saml_helper

    try:
        juju.remove_relation(app.name, "saml-integrator")
    except subprocess.CalledProcessError:
        pass
    juju.wait(jubilant.all_agents_idle, timeout=JUJU_WAIT_TIMEOUT)
    try:
        juju.cli("remove-application", "saml-integrator", "--force", "--no-wait", "--no-prompt")
    except subprocess.CalledProcessError:
        pass
    try:
        juju.wait(lambda status: "saml-integrator" not in status.apps, timeout=120)
    except TimeoutError:
        logger.warning("saml-integrator removal did not complete before teardown timeout")
    _cleanup_saml_test_idp_pod(juju.model)
    juju.config(app.name, {"force_https": True})


@pytest.fixture(scope="module", name="admin_credentials")
def admin_credentials_fixture(juju: jubilant.Juju, app: types.App) -> types.Credentials:
    """Admin user credentials."""
    username = f"sys{int(time.time())}"
    email = f"{username}@test.internal"
    task = juju.run(f"{app.name}/0", "create-user", {"email": email, "admin": True})
    password = task.results["password"]
    admin_credentials = types.Credentials(
        email=email, username=username, password=password
    )
    return admin_credentials


@pytest.fixture(scope="module", name="admin_api_key")
def admin_api_key_fixture(
    admin_credentials: types.Credentials, discourse_address: str, app_config: Dict[str, str]
) -> str:
    """Admin user API key"""
    with requests.session() as session:
        session.headers.update(
            {
                "Host": app_config["external_hostname"],
                "X-Forwarded-Proto": "https",
            }
        )
        csrf_response = None
        for _ in range(30):
            try:
                csrf_response = session.get(
                    f"{discourse_address}/session/csrf",
                    headers={"Accept": "application/json"},
                    timeout=10,
                )
                if csrf_response.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(2)
        assert csrf_response is not None

        # Get CSRF token
        response = csrf_response

        assert response.ok, response.text
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

        assert response.ok, response.text
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

        assert response.ok, response.text

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
