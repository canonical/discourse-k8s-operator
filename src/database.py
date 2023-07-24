# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the DatabaseObserver class to handle database relation and state."""

import typing

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops.charm import CharmBase
from ops.framework import Object

DATABASE_NAME = "discourse"


class DatabaseObserver(Object):
    """The Database relation observer."""

    _RELATION_NAME = "database"

    def __init__(self, charm: CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "database-observer")
        self._charm = charm
        self.database = DatabaseRequires(
            self._charm,
            relation_name=self._RELATION_NAME,
            database_name=DATABASE_NAME,
        )

    def get_relation_data(self) -> typing.Optional[typing.Dict]:
        """Get database data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        if self.model.get_relation(self._RELATION_NAME) is None:
            return None

        relation_id = self.database.relations[0].id
        relation_data = self.database.fetch_relation_data()[relation_id]

        endpoint = relation_data.get("endpoints", ":")

        return {
            "POSTGRES_USER": relation_data.get("username"),
            "POSTGRES_PASSWORD": relation_data.get("password"),
            "POSTGRES_HOST": endpoint.split(":")[0],
            "POSTGRES_PORT": endpoint.split(":")[1],
            "POSTGRES_DB": relation_data.get("database"),
        }
