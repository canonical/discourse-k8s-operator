# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse K8s operator charm unit tests."""

import pytest
from ops import testing
from ops.model import ActiveStatus, BlockedStatus

from charm import (
    CONTAINER_NAME,
    INVALID_CORS_MESSAGE,
    OAUTH_RELATION_NAME,
    SERVICE_NAME,
    DiscourseCharm,
)


@pytest.mark.parametrize(
    "config, expected_origin, expected_status",
    [
        pytest.param(
            {
                "cors_origin": "*",
                "augment_cors_origin": True,
                "external_hostname": "example.com",
                "force_https": True,
                "s3_cdn_url": "https://cdn.test",
            },
            "*",
            ActiveStatus(),
            id="Wildcard disables augmentation",
        ),
        pytest.param(
            {
                "cors_origin": "",
                "augment_cors_origin": False,
                "external_hostname": "example.com",
                "force_https": True,
                "s3_cdn_url": "https://cdn.test",
            },
            "*",
            BlockedStatus(INVALID_CORS_MESSAGE),
            id="Raise error when invalid CORS config",
        ),
        pytest.param(
            {
                "cors_origin": "",
                "augment_cors_origin": True,
                "external_hostname": "example.com",
                "force_https": True,
                "s3_cdn_url": "",
            },
            "https://example.com",
            ActiveStatus(),
            id="Augment only with external_hostname (HTTPS)",
        ),
        pytest.param(
            {
                "cors_origin": "",
                "augment_cors_origin": True,
                "external_hostname": "",
                "force_https": True,
                "s3_cdn_url": "",
            },
            "https://discourse-k8s",
            ActiveStatus(),
            id="Augment with external_hostname not explicitly defined",
        ),
        pytest.param(
            {
                "cors_origin": "",
                "augment_cors_origin": True,
                "external_hostname": "example.com",
                "force_https": False,
                "s3_cdn_url": "https://cdn.test",
            },
            "http://example.com,https://cdn.test",
            ActiveStatus(),
            id="Augment with both external_hostname (HTTP) and s3_cdn_url",
        ),
        pytest.param(
            {
                "cors_origin": "https://custom.origin",
                "augment_cors_origin": False,
                "external_hostname": "example.com",
                "force_https": True,
                "s3_cdn_url": "https://cdn.test",
            },
            "https://custom.origin",
            ActiveStatus(),
            id="User-defined cors_origin, no augmentation",
        ),
        pytest.param(
            {
                "cors_origin": "https://custom.origin",
                "augment_cors_origin": True,
                "external_hostname": "example.com",
                "force_https": True,
                "s3_cdn_url": "https://cdn.test",
            },
            "https://cdn.test,https://custom.origin,https://example.com",
            ActiveStatus(),
            id="User-defined cors_origin with augmentation enabled",
        ),
        pytest.param(
            {
                "cors_origin": "https://foo.com, https://bar.com",
                "augment_cors_origin": True,
                "external_hostname": "example.com",
                "force_https": False,
                "s3_cdn_url": "https://cdn.test",
            },
            "http://example.com,https://bar.com,https://cdn.test,https://foo.com",
            ActiveStatus(),
            id="Multiple user-defined cors_origins with augmentation",
        ),
        pytest.param(
            {
                "cors_origin": " https://foo.com , https://foo.com ",
                "augment_cors_origin": True,
                "external_hostname": "foo.com",
                "force_https": True,
                "s3_cdn_url": "https://foo.com",
            },
            "https://foo.com",
            ActiveStatus(),
            id="Duplicated origins across cors_origin and augmentation",
        ),
    ],
)
def test_get_cors_origin_behavior(config, expected_origin, expected_status, base_state):
    """
    arrange: deploy charm with CORS-related config
    act: configure charm with varying CORS inputs
    assert: DISCOURSE_CORS_ORIGIN matches expected result
    """
    ctx = testing.Context(DiscourseCharm)

    base_state["config"] = config

    state_in = testing.State(**base_state)
    container = state_in.get_container(CONTAINER_NAME)

    state_out = ctx.run(ctx.on.pebble_ready(container), state_in)
    plan_out = state_out.get_container(container.name).plan

    assert state_out.unit_status == expected_status
    if expected_status == ActiveStatus():  # plan is empty when in BlockedStatus
        assert (
            plan_out.services[SERVICE_NAME].environment["DISCOURSE_CORS_ORIGIN"] == expected_origin
        )


@pytest.mark.parametrize(
    "config, expected_status",
    [
        pytest.param(
            {"external_hostname": "discourse.example.com", "force_https": True},
            ActiveStatus(),
            id="Valid config",
        ),
        pytest.param(
            {"external_hostname": "discourse.example.com", "force_https": False},
            BlockedStatus(
                "An oauth relation cannot be established without 'force_https' being true"
            ),
            id="Missing force_https",
        ),
        pytest.param(
            {"force_https": True},
            BlockedStatus("Invalid OAuth client config, check the logs for more info."),
            id="external_hostname not set",
        ),
    ],
)
def test_oauth_integration(base_state, config, expected_status):
    """
    arrange: deploy charm and add oauth relation with provider data.
    act: trigger pebble ready or relation changed.
    assert: charm configures OIDC environment variables in the container.
    """
    ctx = testing.Context(DiscourseCharm)

    # Define the relation
    oauth_relation = testing.Relation(
        endpoint=OAUTH_RELATION_NAME,
        interface="oauth",
        remote_app_data={
            "issuer_url": "https://auth.example.com",
            "authorization_endpoint": "https://auth.example.com/auth",
            "token_endpoint": "https://auth.example.com/token",
            "introspection_endpoint": "https://auth.example.com/introspect",
            "userinfo_endpoint": "https://auth.example.com/userinfo",
            "jwks_endpoint": "https://auth.example.com/jwks",
            "scope": "openid email",
            "client_id": "my-client-id",
            "client_secret": "my-super-secret",
        },
    )

    base_state["relations"].append(oauth_relation)
    base_state["config"] = config

    state_in = testing.State(**base_state)

    # Run the charm
    state_out = ctx.run(ctx.on.relation_joined(oauth_relation), state_in)

    assert state_out.unit_status == expected_status
    if expected_status == ActiveStatus():
        # Check if OIDC env vars are set in the plan
        plan = state_out.get_container(CONTAINER_NAME).plan
        env = plan.services[SERVICE_NAME].environment

        assert env["DISCOURSE_OPENID_CONNECT_ENABLED"] == "true"
        assert (
            env["DISCOURSE_OPENID_CONNECT_DISCOVERY_DOCUMENT"]
            == "https://auth.example.com/.well-known/openid-configuration"
        )
        assert env["DISCOURSE_OPENID_CONNECT_CLIENT_ID"] == "my-client-id"
        assert env["DISCOURSE_OPENID_CONNECT_CLIENT_SECRET"] == "my-super-secret"
        assert env["DISCOURSE_OPENID_CONNECT_AUTHORIZE_SCOPE"] == "openid email"

        # Also check if the charm sent its client config
        relation = next(r for r in state_out.relations if r.id == oauth_relation.id)
        assert (
            relation.local_app_data["redirect_uri"]
            == "https://discourse.example.com/auth/oidc/callback"
        )
        assert relation.local_app_data["scope"] == "openid email"
        assert relation.local_app_data["grant_types"] == '["authorization_code"]'
        assert relation.local_app_data["token_endpoint_auth_method"] == "client_secret_basic"
