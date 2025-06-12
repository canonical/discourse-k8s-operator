# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""helpers for the unit tests."""

import contextlib
import typing
import unittest.mock

from ops.model import Container
from ops.testing import Harness

from charm import DiscourseCharm

DATABASE_NAME = "discourse"


def start_harness(  # pylint: disable=too-many-arguments
    *,
    saml_fields: tuple = (False, ""),
    with_postgres: bool = True,
    with_redis: bool = True,
    with_ingress: bool = False,
    with_config: typing.Optional[typing.Dict[str, typing.Any]] = None,
    run_initial_hooks=True,
):
    """Start a harness discourse charm.

    This is also a workaround for the fact that Harness
    doesn't reinitialize the charm as expected.
    Ref: https://github.com/canonical/operator/issues/736

    Args:
        - with_postgres: should a postgres relation be added
        - with_redis: should a redis relation be added
        - with_ingress: should a ingress relation be added
        - with_config: apply some configuration to the charm

    Returns: a ready to use harness instance
    """
    harness = Harness(DiscourseCharm)
    if run_initial_hooks:
        harness.begin_with_initial_hooks()
    else:
        harness.begin()

    # We catch all exec calls to the container by default
    harness.handle_exec("discourse", [], result=0)

    if with_postgres:
        add_postgres_relation(harness)

    if with_redis:
        add_redis_relation(harness)

    if with_ingress:
        _add_ingress_relation(harness)

    if saml_fields[0]:
        _add_saml_relation(harness, saml_fields[1])

    if with_config is not None:
        harness.update_config(with_config)

    return harness


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


def add_postgres_relation(harness):
    """Add postgresql relation and relation data to the charm.

    Args:
        - A harness instance

    Returns: the same harness instance with an added relation
    """

    relation_data = {
        "database": DATABASE_NAME,
        "endpoints": "dbhost:5432,dbhost-2:5432",
        "password": "somepasswd",  # nosec
        "username": "someuser",
    }

    harness.db_relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(harness.db_relation_id, "postgresql/0")
    harness.update_relation_data(
        harness.db_relation_id,
        "postgresql",
        relation_data,
    )


def add_redis_relation(harness, relation_data=None, app_data=None):
    """Add redis relation and relation data to the charm.

    Args:
        - A harness instance

    Returns: the same harness instance with an added relation
    """
    redis_relation_id = harness.add_relation(
        "redis",
        "redis",
        app_data={"leader-host": "redis-host"} if app_data is None else app_data,
    )
    harness.add_relation_unit(redis_relation_id, "redis/0")
    harness.update_relation_data(
        redis_relation_id,
        "redis/0",
        {"hostname": "redis-host", "port": "1010"} if relation_data is None else relation_data,
    )


def _add_ingress_relation(harness):
    """Add ingress relation and relation data to the charm.

    Args:
        - A harness instance

    Returns: the same harness instance with an added relation
    """
    nginx_route_relation_id = harness.add_relation("nginx-route", "ingress")
    harness.add_relation_unit(nginx_route_relation_id, "ingress/0")


def _add_saml_relation(harness, saml_target):
    """Add ingress relation and relation data to the charm.

    Args:
        - A harness instance

    Returns: the same harness instance with an added relation
    """
    harness.set_leader(True)
    saml_relation_id = harness.add_relation("saml", "saml-integrator")
    harness.add_relation_unit(saml_relation_id, "saml-integrator/0")
    harness.disable_hooks()
    binding = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    harness.update_relation_data(
        relation_id=saml_relation_id,
        app_or_unit="saml-integrator",
        key_values={
            "entity_id": saml_target,
            "metadata_url": f"{saml_target}/saml/metadata",
            "x509certs": "test",
            "single_sign_on_service_redirect_url": f"{saml_target}/+saml",
            "single_sign_on_service_redirect_binding": binding,
        },
    )
    harness.enable_hooks()
