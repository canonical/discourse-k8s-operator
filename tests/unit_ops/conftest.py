# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discourse K8s operator charm fixtures."""

import pytest
from ops import testing

from charm import CONTAINER_NAME, DATABASE_NAME


@pytest.fixture(name="base_state")
def base_state_fixture(discourse_config, discourse_container, postgresql_relation, redis_relation):
    input_state = {
        "leader": True,
        "config": discourse_config,
        "containers": {discourse_container},
        "relations": [postgresql_relation, redis_relation],
    }
    yield input_state


@pytest.fixture(name="discourse_config")
def discourse_config_fixture():
    yield {}


@pytest.fixture(name="discourse_container")
def discourse_container_fixture():
    """Discourse container fixture."""
    yield testing.Container(
        name=CONTAINER_NAME,
        can_connect=True,
        execs=[
            testing.Exec(
                command_prefix=[
                    "/srv/discourse/app/bin/bundle",
                    "exec",
                    "rake",
                    "--trace",
                    "db:migrate",
                ],
                return_code=0,
                stdout="Migration successful\n",
                stderr="",
            ),
            testing.Exec(
                command_prefix=["/srv/discourse/app/bin/rails", "runner"],
                return_code=0,
                stdout="successful\n",
                stderr="",
            ),
        ],
    )  # type: ignore[call-arg]


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
        remote_units_data=relation_data,
        remote_app_data={"leader-host": "redis-host"},
    )
