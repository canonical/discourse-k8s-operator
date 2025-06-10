# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse K8s operator charm fixtures."""

import pytest
from ops import testing

from charm import CONTAINER_NAME, DATABASE_NAME, DISCOURSE_PATH, SERVICE_NAME



@pytest.fixture(name="discourse_container")
def discourse_container_fixture():
    """Discourse container fixture."""
    yield testing.Container(name=CONTAINER_NAME, can_connect=True)  # type: ignore[call-arg]


@pytest.fixture(name="postgresql_relation")
def postgresql_relation_fixture():
    """Postgresql relation fixture."""
    relation_data = {
        "database": DATABASE_NAME,
        "endpoints": "dbhost:5432,dbhost-2:5432",
        "password": "somepasswd",  # nosec
        "username": "someuser",
    }
    yield testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_data=relation_data,
    )

@pytest.fixture(name="redis_relation")
def redis_relation_fixture():
    """Redis relation fixture."""
    relation_data = {
        0: {
            "hostname": "redis-host",
            "port": "1010",
        },
    }
    yield testing.Relation(
        endpoint="redis",
        interface="redis",
        remote_app_name="redis",
        remote_units_data=relation_data,  ## FIXME: the port is not propagated to self.redis.relation_data
        remote_app_data={"leader-host": "redis-host"}, # relation_app_data

    )