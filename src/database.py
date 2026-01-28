# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the DatabaseObserver class to handle database relation and state."""

import typing

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops.charm import CharmBase
from ops.framework import Object

DATABASE_NAME = "discourse"


class DatabaseHandler(Object):
    """The Database relation observer."""

    def __init__(self, charm: CharmBase, relation_name):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            relation_name: The name of the database relation.
        """
        super().__init__(charm, "database-observer")
        self._charm = charm
        self.relation_name = relation_name
        self.database = DatabaseRequires(
            self._charm,
            relation_name=self.relation_name,
            database_name=DATABASE_NAME,
        )

    def get_relation_data(self) -> typing.Dict[str, str]:
        """Get database data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
            Returns default if the relation data is not correctly initialized.
        """
        default = {
            "POSTGRES_USER": "",
            "POSTGRES_PASSWORD": "",  # nosec B105
            "POSTGRES_HOST": "",
            "POSTGRES_PORT": "",
            "POSTGRES_DB": "",
        }

        if self.model.get_relation(self.relation_name) is None:
            return default

        relation_id = self.database.relations[0].id
        relation_data = self.database.fetch_relation_data()[relation_id]

        endpoints = relation_data.get("endpoints", "").split(",")
        if len(endpoints) < 1:
            return default

        primary_endpoint = endpoints[0].split(":")
        if len(primary_endpoint) < 2:
            return default

        data = {
            "POSTGRES_USER": relation_data.get("username"),
            "POSTGRES_PASSWORD": relation_data.get("password"),
            "POSTGRES_HOST": primary_endpoint[0],
            "POSTGRES_PORT": primary_endpoint[1],
            "POSTGRES_DB": relation_data.get("database"),
        }

        if None in (
            data["POSTGRES_USER"],
            data["POSTGRES_PASSWORD"],
            data["POSTGRES_DB"],
        ):
            return default

        return data

    def is_relation_ready(self) -> bool:
        """Check if the relation is ready.

        Returns:
            bool: returns True if the relation is ready.
        """
        return self.get_relation_data()["POSTGRES_HOST"] != ""
