# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for the discourse valkey integration tests."""

from collections.abc import Callable
from typing import Dict

import jubilant
import requests
import yaml

from . import types
from .conftest import JUJU_WAIT_TIMEOUT, PEBBLE

VALKEY_APP_NAME = "valkey"
# Discourse needs TIME in Lua scripts, which client users can only run since
# https://github.com/canonical/valkey-operator/pull/214 (not yet in 9/stable).
VALKEY_CHANNEL = "9/edge"
VALKEY_MAJOR_VERSION = "9"
VALKEY_ENDPOINT = f"{VALKEY_APP_NAME}:valkey-client"
REDIS_APP_NAME = "redis-k8s"


def deploy_valkey(juju: jubilant.Juju) -> None:
    """Deploy valkey if needed and wait for it to be active."""
    if VALKEY_APP_NAME not in juju.status().apps:
        juju.deploy(VALKEY_APP_NAME, channel=VALKEY_CHANNEL, trust=True)
    juju.wait(
        lambda status: jubilant.all_active(status, VALKEY_APP_NAME), timeout=JUJU_WAIT_TIMEOUT
    )


def all_units(status: jubilant.Status, app_name: str, workload_status: str) -> bool:
    """Check that all units of an application have a workload status.

    The rolling restart library may set the application status explicitly, so the
    application status does not always reflect the status of its units.
    """
    units = status.apps[app_name].units
    return bool(units) and all(
        unit.workload_status.current == workload_status for unit in units.values()
    )


def switch_to_valkey(
    juju: jubilant.Juju, app: types.App, ready: Callable[[jubilant.Status], bool]
) -> None:
    """Replace the redis relation of discourse with a valkey relation.

    Args:
        juju: the juju client.
        app: the discourse application, related to redis.
        ready: condition to wait for once the redis relation is removed.
    """
    juju.integrate(f"{app.name}:valkey", VALKEY_ENDPOINT)
    juju.wait(lambda status: all_units(status, app.name, "blocked"), timeout=JUJU_WAIT_TIMEOUT)
    juju.remove_relation(app.name, REDIS_APP_NAME)
    juju.wait(ready, timeout=JUJU_WAIT_TIMEOUT)


def discourse_environment(juju: jubilant.Juju, unit: str) -> Dict[str, str]:
    """Get the environment of the discourse pebble service of a unit."""
    task = juju.exec(f"{PEBBLE} plan", unit=unit)
    plan = yaml.safe_load(task.stdout)
    return plan["services"]["discourse"]["environment"]


def discourse_service_status(juju: jubilant.Juju, unit: str) -> str:
    """Get the status of the discourse pebble service of a unit."""
    task = juju.exec(f"{PEBBLE} services discourse", unit=unit)
    return task.stdout.splitlines()[1].split()[2]


def rails_runner(juju: jubilant.Juju, unit: str, code: str) -> str:
    """Run ruby code in discourse with rails runner and return its output."""
    command = (
        f"{PEBBLE} exec --user=_daemon_ --context=discourse -w=/srv/discourse/app -- "
        f"/srv/discourse/app/bin/rails runner '{code}'"
    )
    task = juju.exec(command, unit=unit, wait=10 * 60)
    return task.stdout.strip()


def redis_ping(juju: jubilant.Juju, unit: str) -> str:
    """Ping redis from discourse using the configured redis settings."""
    return rails_runner(juju, unit, "puts Discourse.redis.ping")


def valkey_server_version(juju: jubilant.Juju, unit: str) -> str:
    """Get the valkey server version as seen by discourse."""
    return rails_runner(
        juju, unit, 'puts Discourse.redis.without_namespace.info["valkey_version"]'
    )


def home_page_ok(address: str, hostname: str, timeout: int) -> bool:
    """Check that the discourse server running at an address serves its home page.

    Anonymous pages go through the redis backed anonymous cache, so this also checks
    that the running server, and not only a new process, can use redis.
    """
    try:
        response = requests.get(
            f"{address}/",
            headers={"Host": hostname, "X-Forwarded-Proto": "https"},
            timeout=timeout,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200


def status_ok(address: str, timeout: int) -> bool:
    """Check that the discourse server running at an address answers its status endpoint."""
    try:
        response = requests.get(
            f"{address}/srv/status",
            headers={"X-Forwarded-Proto": "https"},
            timeout=timeout,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200
