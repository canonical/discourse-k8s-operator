# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""OAuth integration for Discourse."""

import logging
import typing

from charms.hydra.v0.oauth import (
    ClientConfig,
    ClientConfigError,
    OauthProviderConfig,
    OAuthRequirer,
)
from ops.charm import RelationBrokenEvent, RelationChangedEvent
from ops.framework import Object
from ops.model import BlockedStatus

from constants import OAUTH_RELATION_NAME, OAUTH_SCOPE

logger = logging.getLogger(__name__)


class DiscourseOAuth(Object):
    """OAuth integration for Discourse."""

    def __init__(
        self,
        charm,
        external_hostname_callback: typing.Callable[[], str],
        setup_and_activate_callback: typing.Callable[[], None],
    ):
        """Initialize OAuth integration.

        Args:
            charm: The charm object.
            external_hostname_callback: Callback to get the external hostname.
            setup_and_activate_callback: Callback to setup and activate Discourse.
        """
        super().__init__(charm, OAUTH_RELATION_NAME)
        self.charm = charm
        self._external_hostname_callback = external_hostname_callback
        self._setup_and_activate_callback = setup_and_activate_callback
        self._oauth = OAuthRequirer(self.charm, relation_name=OAUTH_RELATION_NAME)
        self.client_config: ClientConfig | None = None
        self._generate_client_config()

        self.framework.observe(
            self.charm.on[OAUTH_RELATION_NAME].relation_changed, self._on_oauth_relation_changed
        )
        self.framework.observe(
            self.charm.on[OAUTH_RELATION_NAME].relation_joined, self._on_oauth_relation_changed
        )
        self.framework.observe(
            self.charm.on[OAUTH_RELATION_NAME].relation_created, self._on_oauth_relation_changed
        )
        self.framework.observe(
            self.charm.on[OAUTH_RELATION_NAME].relation_broken, self._on_oauth_relation_broken
        )

    def _on_oauth_relation_changed(self, _: RelationChangedEvent) -> None:
        """Handle oauth relation changed event."""
        self._generate_client_config()
        if not self.client_config:
            return
        try:
            self.client_config.validate()
        except ClientConfigError as e:
            # Block charm
            self.charm.unit.status = BlockedStatus(f"Invalid OAuth client config: {e}")
            logger.error("Invalid OAuth client config: %s", e)
            return
        self._oauth.update_client_config(self.client_config)
        self._setup_and_activate_callback()

    def _on_oauth_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Handle the breaking of the oauth relation."""
        self._generate_client_config()
        self._setup_and_activate_callback()

    def _generate_client_config(self) -> None:
        """Generate OAuth client configuration."""
        if self.charm.model.get_relation(OAUTH_RELATION_NAME):
            self.client_config = ClientConfig(
                redirect_uri=f"https://{self._external_hostname_callback()}/auth/oidc/callback",
                scope=OAUTH_SCOPE,
                grant_types=["authorization_code"],
                token_endpoint_auth_method="client_secret_basic",
            )
        else:
            self.client_config = None

    def get_oidc_env(self) -> typing.Dict[str, typing.Any]:
        """
        Get the list of OIDC-related environment variables from the OAuth relation.

        Returns:
            Dictionary with all the OIDC environment settings.
        """
        if self.client_config is None:
            return {}
        provider_info: OauthProviderConfig | None = self._oauth.get_provider_info()
        if not provider_info:
            return {}
        try:
            self.client_config.validate()
        except ClientConfigError as e:
            # Block charm
            self.charm.unit.status = BlockedStatus(f"Invalid OAuth client config: {e}")
            logger.error("Invalid OAuth client config: %s", e)
            return {}
        oidc_env = {
            "DISCOURSE_OPENID_CONNECT_ENABLED": "true",
            "DISCOURSE_OPENID_CONNECT_DISCOVERY_DOCUMENT": f"{provider_info.issuer_url}"
            "/.well-known/openid-configuration",
            "DISCOURSE_OPENID_CONNECT_CLIENT_ID": provider_info.client_id,
            "DISCOURSE_OPENID_CONNECT_CLIENT_SECRET": provider_info.client_secret,
            "DISCOURSE_OPENID_CONNECT_AUTHORIZE_SCOPE": OAUTH_SCOPE,
            "DISCOURSE_OPENID_CONNECT_MATCH_BY_EMAIL": "true",
        }
        return oidc_env
