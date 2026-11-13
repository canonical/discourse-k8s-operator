# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide a wrapper around the valkey_client interface."""

import dataclasses
import logging

import ops
from dpcharmlibs.interfaces import (
    RequirerCommonModel,
    ResourceRequirerEventHandler,
    ValkeyResponseModel,
)
from pydantic import ValidationError

from constants import VALKEY_RELATION_NAME

logger = logging.getLogger(__name__)


class ValkeyRelationNotReadyError(Exception):
    """Raised when the Valkey relation data is not available yet."""


class InvalidValkeyRelationDataError(Exception):
    """Raised when the Valkey relation data is invalid or unsupported."""


@dataclasses.dataclass(frozen=True)
class ValkeyConnection:
    """Valkey connection details.

    Attributes:
        host: Valkey primary hostname.
        port: Valkey primary port.
        username: Valkey username.
        password: Valkey password.
    """

    host: str
    port: int
    username: str
    password: str = dataclasses.field(repr=False)


def _parse_endpoint(endpoints: str) -> tuple[str, int]:
    """Extract the host and port of the first Valkey endpoint.

    Args:
        endpoints: comma-separated endpoints, optionally prefixed with a scheme.

    Returns:
        The host and port of the first endpoint.

    Raises:
        InvalidValkeyRelationDataError: if the endpoint is malformed.
    """
    endpoint = endpoints.split(",")[0].strip()
    endpoint = endpoint.split("://", 1)[-1].rsplit("@", 1)[-1].rstrip("/")
    host, separator, port = endpoint.rpartition(":")
    host = host.strip("[]")
    if not separator or not host:
        raise InvalidValkeyRelationDataError(f"Invalid valkey endpoint: {endpoint}")
    try:
        return host, int(port)
    except ValueError as exc:
        raise InvalidValkeyRelationDataError(f"Invalid valkey endpoint: {endpoint}") from exc


class ValkeyRequirer:
    """Wrapper around ResourceRequirerEventHandler for Valkey."""

    def __init__(self, charm: ops.CharmBase, relation_name: str = VALKEY_RELATION_NAME) -> None:
        """Initialize the Valkey requirer.

        Args:
            charm: The charm instance.
            relation_name: The name of the relation.
        """
        self.relation_name = relation_name
        self.valkey_interface = ResourceRequirerEventHandler(
            charm,
            relation_name,
            [RequirerCommonModel(resource="*")],
            response_model=ValkeyResponseModel,
        )

    @property
    def is_related(self) -> bool:
        """Whether a Valkey relation exists."""
        return bool(self.valkey_interface.relations)

    def get_connection(self) -> ValkeyConnection:
        """Get the Valkey connection details from the relation.

        Returns:
            The Valkey connection details.

        Raises:
            ValkeyRelationNotReadyError: if the relation data is not available yet.
            InvalidValkeyRelationDataError: if the relation data is invalid or unsupported.
        """
        relations = self.valkey_interface.relations
        if not relations:
            raise ValkeyRelationNotReadyError("No valkey relation")
        relation = relations[0]
        if relation.app is None:
            raise ValkeyRelationNotReadyError("Valkey application not available yet")
        try:
            model = self.valkey_interface.interface.build_model(
                relation.id, component=relation.app
            )
        except ValidationError as exc:
            logger.error("Invalid valkey relation data: %s", exc)
            raise InvalidValkeyRelationDataError("Invalid valkey relation data") from exc
        except ops.SecretNotFoundError as exc:
            raise ValkeyRelationNotReadyError("Valkey credentials not available yet") from exc

        if not model.requests:
            raise ValkeyRelationNotReadyError("Valkey has not answered the request yet")
        response = model.requests[0]
        if response.tls:
            raise InvalidValkeyRelationDataError("TLS is not supported for valkey")
        if not response.endpoints:
            raise ValkeyRelationNotReadyError("Valkey endpoints not available yet")

        host, port = _parse_endpoint(response.endpoints)
        if not response.secret_user or response.username is None or response.password is None:
            raise ValkeyRelationNotReadyError("Valkey credentials not available yet")
        return ValkeyConnection(
            host=host,
            port=port,
            username=response.username,
            password=response.password,
        )
