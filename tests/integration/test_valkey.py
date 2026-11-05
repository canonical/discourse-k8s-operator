# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse integration tests for the valkey relation."""

import logging
import subprocess  # nosec B404
from contextlib import suppress
from typing import Dict

import jubilant
import pytest
import requests
import yaml

from . import types

logger = logging.getLogger(__name__)

VALKEY_APP_NAME = "valkey"
VALKEY_CHANNEL = "9/stable"
VALKEY_MAJOR_VERSION = "9"
VALKEY_ENDPOINT = f"{VALKEY_APP_NAME}:valkey-client"
REDIS_APP_NAME = "redis-k8s"
JUJU_WAIT_TIMEOUT = 30 * 60
PEBBLE = "PEBBLE_SOCKET=/charm/containers/discourse/pebble.socket pebble"


def _discourse_environment(juju: jubilant.Juju, app: types.App) -> Dict[str, str]:
    """Get the environment of the discourse pebble service."""
    task = juju.exec(f"{PEBBLE} plan", unit=f"{app.name}/0")
    plan = yaml.safe_load(task.stdout)
    return plan["services"]["discourse"]["environment"]


def _rails_runner(juju: jubilant.Juju, app: types.App, code: str) -> str:
    """Run ruby code in discourse with rails runner and return its output."""
    command = (
        f"{PEBBLE} exec --user=_daemon_ --context=discourse -w=/srv/discourse/app -- "
        f"/srv/discourse/app/bin/rails runner '{code}'"
    )
    task = juju.exec(command, unit=f"{app.name}/0", wait=10 * 60)
    return task.stdout.strip()


def _redis_ping(juju: jubilant.Juju, app: types.App) -> str:
    """Ping redis from discourse using the configured redis settings."""
    return _rails_runner(juju, app, "puts Discourse.redis.ping")


def _valkey_server_version(juju: jubilant.Juju, app: types.App) -> str:
    """Get the valkey server version as seen by discourse."""
    return _rails_runner(
        juju, app, 'puts Discourse.redis.without_namespace.info["valkey_version"]'
    )


@pytest.mark.abort_on_fail
def test_valkey_relation(
    app: types.App,
    juju: jubilant.Juju,
    app_config: Dict[str, str],
    discourse_address: str,
    requests_timeout: int,
):
    """
    arrange: a discourse application related to redis, and a valkey application.
    act: replace the redis relation with a valkey relation, then restore redis.
    assert: discourse is active and uses valkey with its credentials, then redis again.
    """

    def home_page_ok() -> bool:
        try:
            response = requests.get(
                f"{discourse_address}/",
                headers={
                    "Host": app_config["external_hostname"],
                    "X-Forwarded-Proto": "https",
                },
                timeout=requests_timeout,
            )
        except requests.RequestException:
            return False
        return response.status_code == 200

    def discourse_active_and_serving(status: jubilant.Status) -> bool:
        return status.apps[app.name].is_active and home_page_ok()

    if VALKEY_APP_NAME not in juju.status().apps:
        juju.deploy(VALKEY_APP_NAME, channel=VALKEY_CHANNEL, trust=True)
    juju.wait(
        lambda status: jubilant.all_active(status, VALKEY_APP_NAME), timeout=JUJU_WAIT_TIMEOUT
    )
    valkey_status = juju.status().apps[VALKEY_APP_NAME]
    assert valkey_status.charm_channel == VALKEY_CHANNEL

    juju.integrate(f"{app.name}:valkey", VALKEY_ENDPOINT)
    juju.wait(lambda status: status.apps[app.name].is_blocked, timeout=JUJU_WAIT_TIMEOUT)

    juju.remove_relation(app.name, REDIS_APP_NAME)
    juju.wait(discourse_active_and_serving, timeout=JUJU_WAIT_TIMEOUT)

    environment = _discourse_environment(juju, app)
    redis_address = juju.status().apps[REDIS_APP_NAME].units[f"{REDIS_APP_NAME}/0"].address
    assert environment["DISCOURSE_REDIS_HOST"] not in ("", redis_address)
    assert environment["DISCOURSE_REDIS_USERNAME"]
    assert environment["DISCOURSE_REDIS_PASSWORD"]
    assert _redis_ping(juju, app) == "PONG"
    valkey_version = _valkey_server_version(juju, app)
    assert valkey_version.split(".")[0] == VALKEY_MAJOR_VERSION
    assert valkey_version == valkey_status.version

    juju.integrate(app.name, REDIS_APP_NAME)
    juju.wait(lambda status: status.apps[app.name].is_blocked, timeout=JUJU_WAIT_TIMEOUT)

    juju.remove_relation(f"{app.name}:valkey", VALKEY_ENDPOINT)
    juju.wait(discourse_active_and_serving, timeout=JUJU_WAIT_TIMEOUT)

    environment = _discourse_environment(juju, app)
    assert environment["DISCOURSE_REDIS_USERNAME"] == ""
    assert environment["DISCOURSE_REDIS_PASSWORD"] == ""
    assert _redis_ping(juju, app) == "PONG"

    with suppress(subprocess.CalledProcessError):
        juju.remove_application(VALKEY_APP_NAME, destroy_storage=True, force=True)
