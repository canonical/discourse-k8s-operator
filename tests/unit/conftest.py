# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""pytest fixtures for the unit test."""

import contextlib
import typing
import unittest.mock

import ops
import pytest
from ops.model import BlockedStatus, Container
from ops.testing import Harness

from tests.unit import helpers
from tests.unit._patched_charm import DiscourseCharm, pgsql_patch

BLOCKED_STATUS = BlockedStatus.name  # type: ignore

DATABASE_NAME = "discourse"


@pytest.fixture(name="start_harness", autouse=True)
def start_harness_fixture():  # -> typing.Generator[Harness, None, None]:
    """Ops testing framework harness fixture."""

    def start_harness(
        *,
        with_postgres: bool = True,
        with_redis: bool = True,
        with_ingress: bool = False,
        with_config: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ):
        """Start a harness discourse charm.

        This is also a workaround for the fact that Harness
        doesn't reinitialize the charm as expected.
        Ref: https://github.com/canonical/operator/issues/736

        Args:
            - with_postgres: should a postgres relation be added
            - with_redis: should a redis relation be added
        """
        harness = Harness(DiscourseCharm)
        harness.disable_hooks()
        # Protected access is needed to instantiate harness
        # pylint: disable=protected-access
        harness._framework = ops.framework.Framework(
            # pylint: disable=protected-access
            harness._storage,
            harness._charm_dir,
            harness._meta,
            harness._model,
        )
        if with_postgres:
            _add_postgres_relation(harness)
        harness.enable_hooks()
        harness.begin_with_initial_hooks()
        if with_redis:
            _add_redis_relation(harness)
            with helpers.patch_exec():
                harness.framework.reemit()
        if with_ingress:
            _add_ingress_relation(harness)

        with helpers.patch_exec(), _patch_setup_completed():
            charm: DiscourseCharm = typing.cast(DiscourseCharm, harness.charm)
            charm._set_setup_completed()

        pgsql_patch.start()

        if with_config is not None:
            harness.update_config(with_config)
            with helpers.patch_exec():
                harness.container_pebble_ready("discourse")

        return harness

    return start_harness


@contextlib.contextmanager
def _patch_setup_completed():
    """Patch filesystem calls in the _is_setup_completed and _set_setup_completed functions."""
    setup_completed = False

    def exists(*_args, **_kwargs):
        return setup_completed

    def push(*_args, **_kwargs):
        nonlocal setup_completed
        setup_completed = True

    with unittest.mock.patch.multiple(Container, exists=exists, push=push):
        yield


def _add_postgres_relation(harness):
    "Add postgresql relation and relation data to the charm."

    relation_data = {
        "database": DATABASE_NAME,
        "endpoints": "dbhost:5432,dbhost-2:5432",
        "password": "somepasswd",  # nosec
        "username": "someuser",
    }

    # get a relation ID for the test outside of __init__ (note pylint disable)
    harness.db_relation_id = (  # pylint: disable=attribute-defined-outside-init
        harness.add_relation("database", "postgresql")
    )
    harness.add_relation_unit(harness.db_relation_id, "postgresql/0")
    harness.update_relation_data(
        harness.db_relation_id,
        "postgresql",
        relation_data,
    )


def _add_redis_relation(harness):
    "Add redis relation and relation data to the charm."
    redis_relation_id = harness.add_relation("redis", "redis")
    harness.add_relation_unit(redis_relation_id, "redis/0")
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._stored.redis_relation = {
        redis_relation_id: {"hostname": "redis-host", "port": 1010}
    }


def _add_ingress_relation(harness):
    "Add ingress relation and relation data to the charm."
    nginx_route_relation_id = harness.add_relation("nginx-route", "ingress")
    harness.add_relation_unit(nginx_route_relation_id, "ingress/0")
