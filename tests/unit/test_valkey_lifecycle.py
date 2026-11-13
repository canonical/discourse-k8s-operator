# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse K8s operator charm cache relation lifecycle unit tests.

These tests start from a running discourse and drive it through the relation
and secret events that Juju emits, without relying on another pebble ready.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from ops import pebble, testing
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charm import CONTAINER_NAME, SERVICE_NAME, DiscourseCharm
from constants import SETUP_COMPLETED_FLAG_FILE

REQUEST_ID = "a2b7f513afa07883"
SALT = "Uh39g15ZlrWSwJtk"
VALKEY_USERNAME = "relation-1-abc123"
VALKEY_PASSWORD = "supersecretpass"  # nosec B105
ROTATED_PASSWORD = "rotatedpass"  # nosec B105
SECRET_LABEL = f"valkey.{{relation_id}}.{REQUEST_ID}.user.secret"


def _valkey_remote_data(
    endpoints: str | None = "valkey-primary:6379", user_secret: testing.Secret | None = None
) -> dict[str, str]:
    """Build the valkey application databag answering the discourse request.

    Args:
        endpoints: endpoints advertised by valkey, omitted if None.
        user_secret: secret holding the valkey credentials, omitted if None.

    Returns:
        The valkey application databag.
    """
    request = {"resource": "*", "salt": SALT, "request-id": REQUEST_ID}
    response = dict(request)
    if endpoints is not None:
        response["endpoints"] = endpoints
    if user_secret is not None:
        response["secret-user"] = user_secret.id
    return {
        "version": "v1",
        "requests": json.dumps([response]),
        "data": json.dumps({REQUEST_ID: request}),
    }


def _valkey_relation(**kwargs) -> testing.Relation:
    """Build a valkey relation where discourse already sent its request.

    Args:
        kwargs: arguments of _valkey_remote_data.

    Returns:
        The valkey relation.
    """
    return testing.Relation(
        endpoint="valkey",
        interface="valkey_client",
        remote_app_name="valkey",
        local_app_data={
            "version": "v1",
            "requests": json.dumps([{"resource": "*", "salt": SALT, "request-id": REQUEST_ID}]),
        },
        remote_app_data=_valkey_remote_data(**kwargs),
    )


def _user_secret(
    relation: testing.Relation, password: str = VALKEY_PASSWORD, **kwargs
) -> testing.Secret:
    """Build the valkey user secret as seen by discourse.

    Args:
        relation: the valkey relation sharing the secret.
        password: the valkey password.
        kwargs: other secret arguments.

    Returns:
        The valkey user secret.
    """
    return testing.Secret(
        tracked_content={"username": VALKEY_USERNAME, "password": password},
        label=SECRET_LABEL.format(relation_id=relation.id),
        **kwargs,
    )


def _with_remote_data(
    state: testing.State, relation: testing.Relation, **kwargs
) -> tuple[testing.State, testing.Relation]:
    """Update the valkey application databag of a relation in a state.

    Args:
        state: the state to update.
        relation: the valkey relation to update.
        kwargs: arguments of _valkey_remote_data.

    Returns:
        The updated state and relation.
    """
    current = state.get_relation(relation.id)
    updated = dataclasses.replace(current, remote_app_data=_valkey_remote_data(**kwargs))
    relations = [r for r in state.relations if r.id != relation.id] + [updated]
    return dataclasses.replace(state, relations=relations), updated


def _environment(state: testing.State) -> dict:
    return state.get_container(CONTAINER_NAME).plan.services[SERVICE_NAME].environment


def _service_status(state: testing.State) -> pebble.ServiceStatus:
    return state.get_container(CONTAINER_NAME).service_statuses[SERVICE_NAME]


@pytest.fixture(name="container")
def container_fixture(discourse_container, tmp_path: Path):
    """Discourse container keeping the setup flag between events."""
    mount = testing.Mount(location=str(Path(SETUP_COMPLETED_FLAG_FILE).parent), source=tmp_path)
    return dataclasses.replace(discourse_container, mounts={"run": mount})


@pytest.fixture(name="ctx")
def ctx_fixture():
    """Charm context."""
    return testing.Context(DiscourseCharm)


def _state(container, relations, secrets=()) -> testing.State:
    return testing.State(
        leader=True, containers={container}, relations=relations, secrets=list(secrets)
    )


def _start(ctx: testing.Context, state: testing.State) -> testing.State:
    """Run pebble ready so that discourse is set up and running."""
    state_out = ctx.run(ctx.on.pebble_ready(state.get_container(CONTAINER_NAME)), state)
    assert state_out.unit_status == ActiveStatus()
    assert _service_status(state_out) == pebble.ServiceStatus.ACTIVE
    return state_out


@pytest.mark.parametrize(
    "first, second",
    [
        pytest.param("endpoints", "credentials", id="endpoints first"),
        pytest.param("credentials", "endpoints", id="credentials first"),
    ],
)
def test_valkey_data_arriving_in_any_order_activates(
    ctx, container, postgresql_relation, first, second
):
    """
    arrange: discourse related to the database and to valkey, without a valkey response.
    act: valkey sends its endpoints and credentials in two separate relation changes.
    assert: discourse waits after the first change and runs with valkey after the second,
        without another pebble ready.
    """
    valkey_relation = _valkey_relation(endpoints=None)
    secret = _user_secret(valkey_relation)
    state = _state(container, [postgresql_relation, valkey_relation], [secret])
    data = {"endpoints": "valkey-primary:6379", "credentials": secret}

    def response(*parts):
        return {
            "endpoints": data["endpoints"] if "endpoints" in parts else None,
            "user_secret": data["credentials"] if "credentials" in parts else None,
        }

    state, relation = _with_remote_data(state, valkey_relation, **response(first))
    state = ctx.run(ctx.on.relation_changed(relation, remote_unit=0), state)
    assert state.unit_status == WaitingStatus("Waiting for valkey relation to initialize")

    state, relation = _with_remote_data(state, valkey_relation, **response(first, second))
    state = ctx.run(ctx.on.relation_changed(relation, remote_unit=0), state)

    assert state.unit_status == ActiveStatus()
    assert _service_status(state) == pebble.ServiceStatus.ACTIVE
    environment = _environment(state)
    assert environment["DISCOURSE_REDIS_HOST"] == "valkey-primary"
    assert environment["DISCOURSE_REDIS_USERNAME"] == VALKEY_USERNAME
    assert environment["DISCOURSE_REDIS_PASSWORD"] == VALKEY_PASSWORD


def test_valkey_endpoint_change_applies_new_endpoint(ctx, container, postgresql_relation):
    """
    arrange: discourse running with valkey.
    act: valkey advertises a new endpoint.
    assert: discourse is reconfigured with the new endpoint.
    """
    valkey_relation = _valkey_relation()
    secret = _user_secret(valkey_relation)
    state, valkey_relation = _with_remote_data(
        _state(container, [postgresql_relation, valkey_relation], [secret]),
        valkey_relation,
        user_secret=secret,
    )
    state = _start(ctx, state)

    state, relation = _with_remote_data(
        state, valkey_relation, endpoints="valkey-new:6380", user_secret=secret
    )
    state = ctx.run(ctx.on.relation_changed(relation, remote_unit=0), state)

    assert state.unit_status == ActiveStatus()
    environment = _environment(state)
    assert environment["DISCOURSE_REDIS_HOST"] == "valkey-new"
    assert environment["DISCOURSE_REDIS_PORT"] == "6380"


def test_valkey_credential_rotation_applies_new_password(ctx, container, postgresql_relation):
    """
    arrange: discourse running with valkey.
    act: valkey publishes a new revision of the user secret.
    assert: discourse is reconfigured with the new password.
    """
    valkey_relation = _valkey_relation()
    secret = _user_secret(valkey_relation)
    state, valkey_relation = _with_remote_data(
        _state(container, [postgresql_relation, valkey_relation], [secret]),
        valkey_relation,
        user_secret=secret,
    )
    state = _start(ctx, state)

    rotated = dataclasses.replace(
        secret, latest_content={"username": VALKEY_USERNAME, "password": ROTATED_PASSWORD}
    )
    state = dataclasses.replace(state, secrets=[rotated])
    state = ctx.run(ctx.on.secret_changed(rotated), state)

    assert state.unit_status == ActiveStatus()
    assert _environment(state)["DISCOURSE_REDIS_PASSWORD"] == ROTATED_PASSWORD


def test_valkey_removed_stops_and_new_relation_starts(ctx, container, postgresql_relation):
    """
    arrange: discourse running with valkey only.
    act: remove the valkey relation, then relate valkey again.
    assert: discourse stops when valkey is removed and starts again once the new relation
        is ready, without another pebble ready.
    """
    valkey_relation = _valkey_relation()
    secret = _user_secret(valkey_relation)
    state, valkey_relation = _with_remote_data(
        _state(container, [postgresql_relation, valkey_relation], [secret]),
        valkey_relation,
        user_secret=secret,
    )
    state = _start(ctx, state)

    state = ctx.run(ctx.on.relation_broken(valkey_relation), state)
    assert state.unit_status == WaitingStatus("Waiting for redis or valkey relation")
    assert _service_status(state) == pebble.ServiceStatus.INACTIVE

    new_relation = _valkey_relation(endpoints=None)
    new_secret = _user_secret(new_relation)
    state = dataclasses.replace(
        state,
        relations=[r for r in state.relations if r.id != valkey_relation.id] + [new_relation],
        secrets=[new_secret],
    )
    state, new_relation = _with_remote_data(state, new_relation, user_secret=new_secret)
    state = ctx.run(ctx.on.relation_changed(new_relation, remote_unit=0), state)

    assert state.unit_status == ActiveStatus()
    assert _service_status(state) == pebble.ServiceStatus.ACTIVE


@pytest.mark.parametrize(
    "endpoints, expected_status",
    [
        pytest.param(
            "valkey-primary",
            BlockedStatus("Invalid valkey endpoint: valkey-primary"),
            id="invalid endpoint",
        ),
        pytest.param(
            "", WaitingStatus("Waiting for valkey relation to initialize"), id="no endpoint"
        ),
    ],
)
def test_valkey_unusable_stops_running_service(
    ctx, container, postgresql_relation, endpoints, expected_status
):
    """
    arrange: discourse running with valkey.
    act: valkey advertises unusable endpoints.
    assert: discourse is stopped instead of running with outdated settings.
    """
    valkey_relation = _valkey_relation()
    secret = _user_secret(valkey_relation)
    state, valkey_relation = _with_remote_data(
        _state(container, [postgresql_relation, valkey_relation], [secret]),
        valkey_relation,
        user_secret=secret,
    )
    state = _start(ctx, state)

    state, relation = _with_remote_data(
        state, valkey_relation, endpoints=endpoints, user_secret=secret
    )
    state = ctx.run(ctx.on.relation_changed(relation, remote_unit=0), state)

    assert state.unit_status == expected_status
    assert _service_status(state) == pebble.ServiceStatus.INACTIVE


def test_redis_change_applies_new_host(ctx, container, postgresql_relation, redis_relation):
    """
    arrange: discourse running with redis.
    act: redis advertises a new host.
    assert: discourse is reconfigured with the new host.
    """
    state = _start(ctx, _state(container, [postgresql_relation, redis_relation]))

    relation = dataclasses.replace(
        state.get_relation(redis_relation.id),
        remote_app_data={"leader-host": "redis-new"},
        remote_units_data={0: {"hostname": "redis-new", "port": "1010"}},
    )
    state = dataclasses.replace(
        state, relations=[r for r in state.relations if r.id != relation.id] + [relation]
    )
    state = ctx.run(ctx.on.relation_changed(relation, remote_unit=0), state)

    assert _environment(state)["DISCOURSE_REDIS_HOST"] == "redis-new"
