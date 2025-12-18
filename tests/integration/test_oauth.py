#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse OAuth integration tests."""

import json
import logging
import textwrap

import jubilant
import pytest

from . import types

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_oauth_integration(app: types.App, juju: jubilant.Juju):
    """
    arrange: deploy AnyCharm.
    act: integrate Discourse with AnyCharm.
    assert: Discourse is active.
    """
    any_app_name = "any-oauth"
    any_charm_src_overwrite = {
        "any_charm.py": textwrap.dedent(
            """\
        from any_charm_base import AnyCharmBase
        from ops.model import ActiveStatus
        import json
        import logging

        logger = logging.getLogger(__name__)

        class AnyCharm(AnyCharmBase):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.framework.observe(self.on["oauth"].relation_changed, self._on_relation_changed)

            def _on_relation_changed(self, event):
                if event.relation.app:
                    data = event.relation.data[event.relation.app]
                    logger.info(f"Received relation data: {data}")
                    with open("/tmp/relation_data.json", "w") as f:
                        f.write(json.dumps(dict(data)))

                relation_data = {
                    "issuer_url": "https://example.com",
                    "authorization_endpoint": "https://example.com/auth",
                    "token_endpoint": "https://example.com/token",
                    "introspection_endpoint": "https://example.com/introspect",
                    "userinfo_endpoint": "https://example.com/userinfo",
                    "jwks_endpoint": "https://example.com/jwks",
                    "scope": "openid email",
                    "client_id": "some-client-id",
                    "client_secret": "supersecret",
                }
                event.relation.data[self.app].update(relation_data)
                self.unit.status = ActiveStatus()
        """
        ),
    }

    juju.deploy(
        "any-charm",
        application_name=any_app_name,
        channel="beta",
        config={"src-overwrite": json.dumps(any_charm_src_overwrite), "python-packages": "ops"},
    )

    juju.config(app.name, {"force_https": True, "external_hostname": "test.discourse.com"})

    juju.integrate(app.name, any_app_name)

    juju.wait(lambda status: jubilant.all_active(status, app.name, any_app_name))
