# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse integration tests for the valkey relation.

The tests run in order and share the deployment: discourse moves from redis to
valkey, survives valkey pod replacements, and finally moves back to redis.
"""

import json
import logging
import subprocess  # nosec B404
from collections.abc import Callable
from contextlib import suppress
from typing import Dict

import jubilant
import pytest

from . import types
from .conftest import JUJU_WAIT_TIMEOUT, _resolve_kubectl_command
from .valkey_helpers import (
    REDIS_APP_NAME,
    VALKEY_APP_NAME,
    VALKEY_CHANNEL,
    VALKEY_ENDPOINT,
    VALKEY_MAJOR_VERSION,
    all_units,
    deploy_valkey,
    discourse_environment,
    discourse_service_status,
    home_page_ok,
    redis_ping,
    status_ok,
    switch_to_valkey,
    valkey_server_version,
)

logger = logging.getLogger(__name__)

# Time for discourse to use valkey again once a valkey pod is deleted.
RECOVERY_TIMEOUT = 10 * 60
VALKEY_NUM_UNITS = 3


@pytest.fixture(scope="module", name="active_and_serving")
def active_and_serving_fixture(
    app: types.App, app_config: Dict[str, str], discourse_address: str, requests_timeout: int
) -> Callable[[jubilant.Status], bool]:
    """Condition for all discourse units to be active and discourse to serve its home page."""

    def active_and_serving(status: jubilant.Status) -> bool:
        return all_units(status, app.name, "active") and home_page_ok(
            discourse_address, app_config["external_hostname"], requests_timeout
        )

    return active_and_serving


def _kubectl(juju: jubilant.Juju, *args: str) -> str:
    """Run kubectl in the namespace of the model and return its output."""
    assert juju.model, "the model must be known to find its namespace"
    namespace = juju.model.split(":")[-1]
    return subprocess.run(  # nosec B603
        [*_resolve_kubectl_command(), "-n", namespace, *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _pod(juju: jubilant.Juju, name: str) -> Dict:
    """Get a pod of the model namespace."""
    return json.loads(_kubectl(juju, "get", "pod", name, "-o", "json"))


def _valkey_primary_pod(juju: jubilant.Juju) -> str:
    """Get the name of the valkey primary pod."""
    selector = f"application-name={VALKEY_APP_NAME},role=primary"
    pods = json.loads(_kubectl(juju, "get", "pods", "-l", selector, "-o", "json"))["items"]
    assert len(pods) == 1, f"expected a single valkey primary pod, found {len(pods)}"
    return pods[0]["metadata"]["name"]


def _valkey_leader_pod(juju: jubilant.Juju) -> str:
    """Get the name of the pod running the valkey juju leader."""
    units = juju.status().apps[VALKEY_APP_NAME].units
    leader = next(name for name, unit in units.items() if unit.leader)
    return leader.replace("/", "-")


def _delete_pod_and_check_recovery(
    juju: jubilant.Juju,
    app: types.App,
    pod: str,
    active_and_serving: Callable[[jubilant.Status], bool],
) -> None:
    """Delete a valkey pod and check that discourse uses valkey again in time."""
    num_units = len(juju.status().apps[VALKEY_APP_NAME].units)
    uid = _pod(juju, pod)["metadata"]["uid"]
    logger.info("Deleting valkey pod %s", pod)
    _kubectl(juju, "delete", "pod", pod, "--wait=true")

    def pod_replaced() -> bool:
        with suppress(subprocess.CalledProcessError):
            new_pod = _pod(juju, pod)
            return (
                new_pod["metadata"]["uid"] != uid and new_pod["status"].get("phase") == "Running"
            )
        return False

    def recovered(status: jubilant.Status) -> bool:
        return (
            pod_replaced()
            and len(status.apps[VALKEY_APP_NAME].units) == num_units
            and jubilant.all_active(status, VALKEY_APP_NAME)
            and active_and_serving(status)
        )

    juju.wait(recovered, timeout=RECOVERY_TIMEOUT, delay=5)
    assert redis_ping(juju, f"{app.name}/0") == "PONG"


@pytest.mark.abort_on_fail
def test_valkey_relation(
    app: types.App,
    juju: jubilant.Juju,
    active_and_serving: Callable[[jubilant.Status], bool],
):
    """
    arrange: a discourse application related to redis, and a valkey application.
    act: replace the redis relation with a valkey relation.
    assert: discourse uses valkey with its credentials.
    """
    unit = f"{app.name}/0"
    deploy_valkey(juju)
    valkey_status = juju.status().apps[VALKEY_APP_NAME]
    assert valkey_status.charm_channel == VALKEY_CHANNEL

    switch_to_valkey(juju, app, active_and_serving)

    environment = discourse_environment(juju, unit)
    redis_address = juju.status().apps[REDIS_APP_NAME].units[f"{REDIS_APP_NAME}/0"].address
    assert environment["DISCOURSE_REDIS_HOST"] not in ("", redis_address)
    assert environment["DISCOURSE_REDIS_USERNAME"]
    assert environment["DISCOURSE_REDIS_PASSWORD"]
    assert redis_ping(juju, unit) == "PONG"
    valkey_version = valkey_server_version(juju, unit)
    assert valkey_version.split(".")[0] == VALKEY_MAJOR_VERSION
    assert valkey_version == valkey_status.version


@pytest.mark.abort_on_fail
def test_valkey_removed_and_related_again(
    app: types.App,
    juju: jubilant.Juju,
    discourse_address: str,
    requests_timeout: int,
    active_and_serving: Callable[[jubilant.Status], bool],
):
    """
    arrange: discourse related to valkey only.
    act: remove the valkey relation, then relate valkey again.
    assert: discourse is stopped while it has no cache, and recovers when valkey is
        related again.
    """
    unit = f"{app.name}/0"
    juju.remove_relation(f"{app.name}:valkey", VALKEY_ENDPOINT)
    juju.wait(
        lambda status: not status.apps[app.name].relations.get("valkey")
        and status.apps[app.name].units[unit].workload_status.message
        == "Waiting for redis or valkey relation",
        timeout=JUJU_WAIT_TIMEOUT,
    )
    assert discourse_service_status(juju, unit) == "inactive"
    assert not status_ok(discourse_address, requests_timeout)

    juju.integrate(f"{app.name}:valkey", VALKEY_ENDPOINT)
    juju.wait(active_and_serving, timeout=JUJU_WAIT_TIMEOUT)
    assert discourse_service_status(juju, unit) == "active"
    assert redis_ping(juju, unit) == "PONG"


@pytest.mark.abort_on_fail
def test_single_valkey_pod_replaced(
    app: types.App,
    juju: jubilant.Juju,
    active_and_serving: Callable[[jubilant.Status], bool],
):
    """
    arrange: discourse related to a single unit valkey.
    act: delete the valkey pod, which is the primary and hosts the juju leader.
    assert: discourse uses valkey again within the recovery timeout.
    """
    pod = _valkey_primary_pod(juju)
    assert pod == _valkey_leader_pod(juju)

    _delete_pod_and_check_recovery(juju, app, pod, active_and_serving)


@pytest.mark.abort_on_fail
def test_valkey_primary_replaced(
    app: types.App,
    juju: jubilant.Juju,
    active_and_serving: Callable[[jubilant.Status], bool],
):
    """
    arrange: discourse related to a valkey cluster.
    act: delete the valkey primary pod, then the pod hosting the valkey juju leader.
    assert: discourse uses the new valkey primary within the recovery timeout each time.
    """
    juju.add_unit(VALKEY_APP_NAME, num_units=VALKEY_NUM_UNITS - 1)
    juju.wait(
        lambda status: len(status.apps[VALKEY_APP_NAME].units) == VALKEY_NUM_UNITS
        and jubilant.all_active(status, VALKEY_APP_NAME),
        timeout=JUJU_WAIT_TIMEOUT,
    )

    _delete_pod_and_check_recovery(juju, app, _valkey_primary_pod(juju), active_and_serving)
    _delete_pod_and_check_recovery(juju, app, _valkey_leader_pod(juju), active_and_serving)


@pytest.mark.abort_on_fail
def test_redis_restored(
    app: types.App,
    juju: jubilant.Juju,
    active_and_serving: Callable[[jubilant.Status], bool],
):
    """
    arrange: discourse related to valkey only.
    act: relate redis, then remove the valkey relation.
    assert: discourse is blocked while both are related, then uses redis without
        credentials.
    """
    unit = f"{app.name}/0"
    juju.integrate(app.name, REDIS_APP_NAME)
    juju.wait(lambda status: all_units(status, app.name, "blocked"), timeout=JUJU_WAIT_TIMEOUT)

    juju.remove_relation(f"{app.name}:valkey", VALKEY_ENDPOINT)
    juju.wait(active_and_serving, timeout=JUJU_WAIT_TIMEOUT)

    environment = discourse_environment(juju, unit)
    assert environment["DISCOURSE_REDIS_USERNAME"] == ""
    assert environment["DISCOURSE_REDIS_PASSWORD"] == ""
    assert redis_ping(juju, unit) == "PONG"
