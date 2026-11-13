# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse K8s operator charm valkey relation unit tests."""

import json

import pytest
from ops import testing
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charm import CONTAINER_NAME, SERVICE_NAME, DiscourseCharm
from valkey_relation import InvalidValkeyRelationDataError, _parse_endpoint

VALKEY_USERNAME = "relation-1-abc123"
VALKEY_PASSWORD = "supersecretpass"  # nosec B105


def _valkey_relation(
    endpoints: str | None = "valkey-primary:6379", secrets: dict[str, testing.Secret] | None = None
) -> testing.Relation:
    """Build a valkey relation answering the discourse request.

    Args:
        endpoints: endpoints advertised by valkey, no response is sent if None.
        secrets: secrets referenced by the response, keyed by secret group.

    Returns:
        The valkey relation.
    """
    remote_app_data = {}
    if endpoints is not None:
        response = {
            "resource": "*",
            "request-id": "a2b7f513afa07883",
            "salt": "Uh39g15ZlrWSwJtk",
            "endpoints": endpoints,
        }
        for group, secret in (secrets or {}).items():
            response[f"secret-{group}"] = secret.id
        remote_app_data = {"version": "v1", "requests": json.dumps([response])}
    return testing.Relation(
        endpoint="valkey",
        interface="valkey_client",
        remote_app_name="valkey",
        remote_app_data=remote_app_data,
    )


@pytest.fixture(name="valkey_user_secret")
def valkey_user_secret_fixture():
    """Valkey user secret fixture."""
    yield testing.Secret(
        tracked_content={"username": VALKEY_USERNAME, "password": VALKEY_PASSWORD}
    )


def _run_pebble_ready(state_in: testing.State) -> testing.State:
    ctx = testing.Context(DiscourseCharm)
    container = state_in.get_container(CONTAINER_NAME)
    return ctx.run(ctx.on.pebble_ready(container), state_in)


def _environment(state_out: testing.State) -> dict:
    return state_out.get_container(CONTAINER_NAME).plan.services[SERVICE_NAME].environment


@pytest.mark.parametrize(
    "endpoints, expected_host, expected_port",
    [
        pytest.param("valkey-primary:6379", "valkey-primary", "6379", id="host and port"),
        pytest.param("valkey://10.1.88.132:6380", "10.1.88.132", "6380", id="with scheme"),
        pytest.param("valkey-0:6379,valkey-1:6379", "valkey-0", "6379", id="first endpoint"),
    ],
)
def test_valkey_relation_configures_redis_env(
    base_state, postgresql_relation, valkey_user_secret, endpoints, expected_host, expected_port
):
    """
    arrange: relate discourse to valkey, which provides endpoints and credentials.
    act: run pebble ready.
    assert: the charm is active and discourse uses valkey through the redis settings.
    """
    valkey_relation = _valkey_relation(endpoints, {"user": valkey_user_secret})
    state_in = testing.State(
        **{**base_state, "relations": [postgresql_relation, valkey_relation]},
        secrets=[valkey_user_secret],
    )

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == ActiveStatus()
    environment = _environment(state_out)
    assert environment["DISCOURSE_REDIS_HOST"] == expected_host
    assert environment["DISCOURSE_REDIS_PORT"] == expected_port
    assert environment["DISCOURSE_REDIS_USERNAME"] == VALKEY_USERNAME
    assert environment["DISCOURSE_REDIS_PASSWORD"] == VALKEY_PASSWORD


@pytest.mark.parametrize(
    "share_secret, secret_in_state",
    [
        pytest.param(False, False, id="no user secret"),
        pytest.param(True, False, id="user secret not accessible"),
    ],
)
def test_valkey_relation_without_credentials(
    base_state, postgresql_relation, valkey_user_secret, share_secret, secret_in_state
):
    """
    arrange: relate discourse to valkey, which provides endpoints but no readable credentials.
    act: run pebble ready.
    assert: the charm waits for the valkey relation to be ready.
    """
    secrets = {"user": valkey_user_secret} if share_secret else None
    state_in = testing.State(
        **{**base_state, "relations": [postgresql_relation, _valkey_relation(secrets=secrets)]},
        secrets=[valkey_user_secret] if secret_in_state else [],
    )

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == WaitingStatus("Waiting for valkey relation to initialize")


def test_redis_relation_sets_empty_credentials(base_state):
    """
    arrange: relate discourse to redis only.
    act: run pebble ready.
    assert: the redis settings come from redis and the credentials are empty.
    """
    state_out = _run_pebble_ready(testing.State(**base_state))

    assert state_out.unit_status == ActiveStatus()
    environment = _environment(state_out)
    assert environment["DISCOURSE_REDIS_HOST"] == "redis-host"
    assert environment["DISCOURSE_REDIS_PORT"] == "1010"
    assert environment["DISCOURSE_REDIS_USERNAME"] == ""
    assert environment["DISCOURSE_REDIS_PASSWORD"] == ""


def test_valkey_and_redis_relations_block(base_state, valkey_user_secret):
    """
    arrange: relate discourse to both redis and valkey.
    act: run pebble ready.
    assert: the charm is blocked.
    """
    base_state["relations"].append(_valkey_relation(secrets={"user": valkey_user_secret}))
    state_in = testing.State(**base_state, secrets=[valkey_user_secret])

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == BlockedStatus(
        "Both redis and valkey relations exist, remove one of them"
    )


def test_no_redis_nor_valkey_relation_waits(base_state, postgresql_relation):
    """
    arrange: relate discourse to the database only.
    act: run pebble ready.
    assert: the charm waits for a redis or valkey relation.
    """
    state_in = testing.State(**{**base_state, "relations": [postgresql_relation]})

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == WaitingStatus("Waiting for redis or valkey relation")


def test_valkey_relation_without_response_waits(base_state, postgresql_relation):
    """
    arrange: relate discourse to valkey, which has not answered the request yet.
    act: run pebble ready.
    assert: the charm waits for the valkey relation.
    """
    state_in = testing.State(
        **{**base_state, "relations": [postgresql_relation, _valkey_relation(endpoints=None)]}
    )

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == WaitingStatus("Waiting for valkey relation to initialize")


def test_valkey_relation_with_tls_blocks(base_state, postgresql_relation, valkey_user_secret):
    """
    arrange: relate discourse to valkey with TLS enabled.
    act: run pebble ready.
    assert: the charm is blocked as TLS is not supported.
    """
    tls_secret = testing.Secret(tracked_content={"tls": "true", "tls-ca": "ca"})
    valkey_relation = _valkey_relation(secrets={"user": valkey_user_secret, "tls": tls_secret})
    state_in = testing.State(
        **{**base_state, "relations": [postgresql_relation, valkey_relation]},
        secrets=[valkey_user_secret, tls_secret],
    )

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == BlockedStatus("TLS is not supported for valkey")


def test_valkey_relation_with_invalid_endpoint_blocks(base_state, postgresql_relation):
    """
    arrange: relate discourse to valkey advertising a malformed endpoint.
    act: run pebble ready.
    assert: the charm is blocked.
    """
    valkey_relation = _valkey_relation(endpoints="valkey-primary")
    state_in = testing.State(**{**base_state, "relations": [postgresql_relation, valkey_relation]})

    state_out = _run_pebble_ready(state_in)

    assert state_out.unit_status == BlockedStatus("Invalid valkey endpoint: valkey-primary")


def test_valkey_relation_broken_waits(base_state, postgresql_relation, valkey_user_secret):
    """
    arrange: relate discourse to valkey only.
    act: break the valkey relation.
    assert: the charm waits for a redis or valkey relation.
    """
    ctx = testing.Context(DiscourseCharm)
    valkey_relation = _valkey_relation(secrets={"user": valkey_user_secret})
    state_in = testing.State(
        **{**base_state, "relations": [postgresql_relation, valkey_relation]},
        secrets=[valkey_user_secret],
    )

    state_out = ctx.run(ctx.on.relation_broken(valkey_relation), state_in)

    assert state_out.unit_status == WaitingStatus("Waiting for redis or valkey relation")


def test_valkey_request_is_sent(base_state, postgresql_relation):
    """
    arrange: relate discourse to valkey as the leader unit.
    act: run the relation created event.
    assert: discourse requests a valkey resource.
    """
    ctx = testing.Context(DiscourseCharm)
    valkey_relation = _valkey_relation(endpoints=None)
    state_in = testing.State(**{**base_state, "relations": [postgresql_relation, valkey_relation]})

    state_out = ctx.run(ctx.on.relation_created(valkey_relation), state_in)

    relation_out = state_out.get_relation(valkey_relation.id)
    requests = json.loads(relation_out.local_app_data["requests"])
    assert len(requests) == 1
    assert requests[0]["resource"] == "*"


@pytest.mark.parametrize("endpoint", ["valkey-primary", "valkey-primary:port", ":6379"])
def test_parse_invalid_endpoint(endpoint):
    """
    arrange: given a malformed valkey endpoint.
    act: parse the endpoint.
    assert: an InvalidValkeyRelationDataError is raised.
    """
    with pytest.raises(InvalidValkeyRelationDataError):
        _parse_endpoint(endpoint)
