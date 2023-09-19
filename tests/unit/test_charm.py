# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Discourse charm."""

# pylint: disable=protected-access
# Protected access check is disabled in tests as we're injecting test data

import secrets
import typing
from unittest.mock import MagicMock

import ops
import pytest
from ops.charm import ActionEvent
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charm import DISCOURSE_PATH, DiscourseCharm
from tests.unit import helpers

DATABASE_NAME = "discourse"


@pytest.mark.parametrize(
    "with_postgres, with_redis, with_ingress, status",
    [
        (False, False, False, WaitingStatus("Waiting for database relation")),
        (False, True, False, WaitingStatus("Waiting for database relation")),
        (True, False, False, WaitingStatus("Waiting for redis relation")),
        (True, True, False, ActiveStatus("")),
        (False, False, True, WaitingStatus("Waiting for database relation")),
        (False, True, True, WaitingStatus("Waiting for database relation")),
        (True, False, True, WaitingStatus("Waiting for redis relation")),
        (True, True, True, ActiveStatus("")),
    ],
    ids=[
        "No relation",
        "Only redis",
        "Only postgres",
        "Postgres+redis",
        "Only ingress",
        "Redis+ingress",
        "Postgres+ingress",
        "All relations",
    ],
)
def test_relations(with_postgres, with_redis, with_ingress, status):
    """
    arrange: given a deployed discourse charm
    act: when pebble ready event is triggered
    assert: it will have the correct status depending on the relations
    """
    harness = helpers.start_harness(
        with_postgres=with_postgres, with_redis=with_redis, with_ingress=with_ingress
    )
    assert harness.model.unit.status == status


def test_ingress_relation_not_ready():
    """
    arrange: given a deployed discourse charm with the ingress established
    act: when pebble ready event is triggered
    assert: it will wait for the ingress relation.
    """
    harness = helpers.start_harness(with_postgres=False, with_redis=False, with_ingress=True)
    assert harness.model.unit.status == WaitingStatus("Waiting for database relation")


def test_config_changed_when_no_saml_target():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when force_saml_login configuration is True and there's no saml_target_url
    assert: it will get to blocked status waiting for the latter.
    """
    harness = helpers.start_harness(with_config={"force_saml_login": True, "saml_target_url": ""})
    assert harness.model.unit.status == BlockedStatus(
        "force_saml_login can not be true without a saml_target_url"
    )


def test_config_changed_when_saml_sync_groups_and_no_url_invalid():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when saml_sync_groups configuration is provided and there's no saml_target_url
    assert: it will get to blocked status waiting for the latter.
    """
    harness = helpers.start_harness(
        with_config={"saml_sync_groups": "group1", "saml_target_url": ""}
    )
    assert harness.model.unit.status == BlockedStatus(
        "'saml_sync_groups' cannot be specified without a 'saml_target_url'"
    )


def test_config_changed_when_saml_target_url_and_force_https_disabled():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when saml_target_url configuration is provided and force_https is False
    assert: it will get to blocked status waiting for the latter.
    """
    harness = helpers.start_harness(
        with_config={"saml_target_url": "group1", "force_https": False}
    )
    assert harness.model.unit.status == BlockedStatus(
        "'saml_target_url' cannot be specified without 'force_https' being true"
    )


def test_config_changed_when_no_cors():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when cors_origin configuration is empty
    assert: it will get to blocked status waiting for it.
    """
    harness = helpers.start_harness(with_config={"cors_origin": ""})
    assert (
        harness.charm._database.get_relation_data() is not None
    ), "database name should be set after relation joined"
    assert (
        harness.charm._database.get_relation_data().get("POSTGRES_DB") == "discourse"
    ), "database name should be set after relation joined"


def test_config_changed_when_throttle_mode_invalid():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when throttle_level configuration is invalid
    assert: it will get to blocked status waiting for a valid value to be provided.
    """
    harness = helpers.start_harness(with_config={"throttle_level": "Scream"})
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert "none permissive strict" in harness.model.unit.status.message


def test_config_changed_when_s3_and_no_bucket_invalid():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when s3_enabled configuration is True and there's no s3_bucket
    assert: it will get to blocked status waiting for the latter.
    """
    harness = helpers.start_harness(
        with_config={
            "s3_access_key_id": "3|33+",
            "s3_enabled": True,
            "s3_endpoint": "s3.endpoint",
            "s3_region": "the-infinite-and-beyond",
            "s3_secret_access_key": "s|kI0ure_k3Y",
        }
    )
    assert harness.model.unit.status == BlockedStatus("'s3_enabled' requires 's3_bucket'")


def test_config_changed_when_valid_no_s3_backup_nor_cdn():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when a valid configuration is provided
    assert: the appropriate configuration values are passed to the pod and the unit
        reaches Active status.
    """
    harness = helpers.start_harness()

    # We catch the exec call that we expect to register it and make sure that the
    # args passed to it are correct.
    expected_exec_call_was_made = False

    def bundle_handler(args: ops.testing.ExecArgs) -> None:
        nonlocal expected_exec_call_was_made
        expected_exec_call_was_made = True
        if (
            args.environment != harness._charm._create_discourse_environment_settings()
            or args.working_dir != DISCOURSE_PATH
            or args.user != "_daemon_"
        ):
            raise ValueError("Exec rake s3:upload_assets wasn't made with the correct args.")

    harness.handle_exec(
        "discourse",
        [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "s3:upload_assets"],
        handler=bundle_handler,
    )

    harness.set_leader(True)
    harness.update_config(
        {
            "s3_access_key_id": "3|33+",
            "s3_bucket": "who-s-a-good-bucket?",
            "s3_enabled": True,
            "s3_endpoint": "s3.endpoint",
            "s3_region": "the-infinite-and-beyond",
            "s3_secret_access_key": "s|kI0ure_k3Y",
        }
    )
    harness.container_pebble_ready("discourse")
    harness.framework.reemit()

    assert harness._charm
    assert expected_exec_call_was_made

    updated_plan = harness.get_container_pebble_plan("discourse").to_dict()
    updated_plan_env = updated_plan["services"]["discourse"]["environment"]
    assert "DISCOURSE_BACKUP_LOCATION" not in updated_plan_env
    assert "*" == updated_plan_env["DISCOURSE_CORS_ORIGIN"]
    assert "dbhost" == updated_plan_env["DISCOURSE_DB_HOST"]
    assert DATABASE_NAME == updated_plan_env["DISCOURSE_DB_NAME"]
    assert "somepasswd" == updated_plan_env["DISCOURSE_DB_PASSWORD"]
    assert "someuser" == updated_plan_env["DISCOURSE_DB_USERNAME"]
    assert updated_plan_env["DISCOURSE_ENABLE_CORS"]
    assert "discourse-k8s" == updated_plan_env["DISCOURSE_HOSTNAME"]
    assert "redis-host" == updated_plan_env["DISCOURSE_REDIS_HOST"]
    assert "1010" == updated_plan_env["DISCOURSE_REDIS_PORT"]
    assert updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"]
    assert "3|33+" == updated_plan_env["DISCOURSE_S3_ACCESS_KEY_ID"]
    assert "DISCOURSE_S3_BACKUP_BUCKET" not in updated_plan_env
    assert "DISCOURSE_S3_CDN_URL" not in updated_plan_env
    assert "who-s-a-good-bucket?" == updated_plan_env["DISCOURSE_S3_BUCKET"]
    assert "s3.endpoint" == updated_plan_env["DISCOURSE_S3_ENDPOINT"]
    assert "the-infinite-and-beyond" == updated_plan_env["DISCOURSE_S3_REGION"]
    assert "s|kI0ure_k3Y" == updated_plan_env["DISCOURSE_S3_SECRET_ACCESS_KEY"]
    assert updated_plan_env["DISCOURSE_USE_S3"]
    assert isinstance(harness.model.unit.status, ActiveStatus)


def test_config_changed_when_valid_no_fingerprint():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when a valid configuration is provided
    assert: the appropriate configuration values are passed to the pod and the unit
        reaches Active status.
    """
    with helpers.patch_exec():
        harness = helpers.start_harness(
            with_config={
                "force_saml_login": True,
                "saml_target_url": "https://login.sample.com/+saml",
                "saml_sync_groups": "group1",
                "s3_enabled": False,
                "force_https": True,
            }
        )

        updated_plan = harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        assert "*" == updated_plan_env["DISCOURSE_CORS_ORIGIN"]
        assert "dbhost" == updated_plan_env["DISCOURSE_DB_HOST"]
        assert DATABASE_NAME == updated_plan_env["DISCOURSE_DB_NAME"]
        assert "somepasswd" == updated_plan_env["DISCOURSE_DB_PASSWORD"]
        assert "someuser" == updated_plan_env["DISCOURSE_DB_USERNAME"]
        assert updated_plan_env["DISCOURSE_ENABLE_CORS"]
        assert "discourse-k8s" == updated_plan_env["DISCOURSE_HOSTNAME"]
        assert "redis-host" == updated_plan_env["DISCOURSE_REDIS_HOST"]
        assert "1010" == updated_plan_env["DISCOURSE_REDIS_PORT"]
        assert "DISCOURSE_SAML_CERT_FINGERPRINT" not in updated_plan_env
        assert "true" == updated_plan_env["DISCOURSE_SAML_FULL_SCREEN_LOGIN"]
        assert "https://login.sample.com/+saml" == updated_plan_env["DISCOURSE_SAML_TARGET_URL"]
        assert "false" == updated_plan_env["DISCOURSE_SAML_GROUPS_FULLSYNC"]
        assert "true" == updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS"]
        assert "group1" == updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS_LIST"]
        assert updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"]
        assert "none" == updated_plan_env["DISCOURSE_SMTP_AUTHENTICATION"]
        assert "none" == updated_plan_env["DISCOURSE_SMTP_OPENSSL_VERIFY_MODE"]
        assert "DISCOURSE_USE_S3" not in updated_plan_env
        assert isinstance(harness.model.unit.status, ActiveStatus)


def test_config_changed_when_valid():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: when a valid configuration is provided
    assert: the appropriate configuration values are passed to the pod and the unit
        reaches Active status.
    """
    with helpers.patch_exec():
        harness = helpers.start_harness(
            with_config={
                "developer_emails": "user@foo.internal",
                "enable_cors": True,
                "external_hostname": "discourse.local",
                "force_saml_login": True,
                "saml_target_url": "https://login.ubuntu.com/+saml",
                "saml_sync_groups": "group1",
                "smtp_address": "smtp.internal",
                "smtp_domain": "foo.internal",
                "smtp_password": "OBV10USLYF4K3",
                "smtp_username": "apikey",
                "s3_access_key_id": "3|33+",
                "s3_backup_bucket": "back-bucket",
                "s3_bucket": "who-s-a-good-bucket?",
                "s3_cdn_url": "s3.cdn",
                "s3_enabled": True,
                "s3_endpoint": "s3.endpoint",
                "s3_region": "the-infinite-and-beyond",
                "s3_secret_access_key": "s|kI0ure_k3Y",
                "force_https": True,
            }
        )

        updated_plan = harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        assert "s3" == updated_plan_env["DISCOURSE_BACKUP_LOCATION"]
        assert "*" == updated_plan_env["DISCOURSE_CORS_ORIGIN"]
        assert "dbhost" == updated_plan_env["DISCOURSE_DB_HOST"]
        assert DATABASE_NAME == updated_plan_env["DISCOURSE_DB_NAME"]
        assert "somepasswd" == updated_plan_env["DISCOURSE_DB_PASSWORD"]
        assert "someuser" == updated_plan_env["DISCOURSE_DB_USERNAME"]
        assert "user@foo.internal" == updated_plan_env["DISCOURSE_DEVELOPER_EMAILS"]
        assert updated_plan_env["DISCOURSE_ENABLE_CORS"]
        assert "discourse.local" == updated_plan_env["DISCOURSE_HOSTNAME"]
        assert "redis-host" == updated_plan_env["DISCOURSE_REDIS_HOST"]
        assert "1010" == updated_plan_env["DISCOURSE_REDIS_PORT"]
        assert updated_plan_env["DISCOURSE_SAML_CERT_FINGERPRINT"] is not None
        assert "true" == updated_plan_env["DISCOURSE_SAML_FULL_SCREEN_LOGIN"]
        assert "https://login.ubuntu.com/+saml" == updated_plan_env["DISCOURSE_SAML_TARGET_URL"]
        assert "false" == updated_plan_env["DISCOURSE_SAML_GROUPS_FULLSYNC"]
        assert "true" == updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS"]
        assert "group1" == updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS_LIST"]
        assert updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"]
        assert "3|33+" == updated_plan_env["DISCOURSE_S3_ACCESS_KEY_ID"]
        assert "back-bucket" == updated_plan_env["DISCOURSE_S3_BACKUP_BUCKET"]
        assert "s3.cdn" == updated_plan_env["DISCOURSE_S3_CDN_URL"]
        assert "who-s-a-good-bucket?" == updated_plan_env["DISCOURSE_S3_BUCKET"]
        assert "s3.endpoint" == updated_plan_env["DISCOURSE_S3_ENDPOINT"]
        assert "the-infinite-and-beyond" == updated_plan_env["DISCOURSE_S3_REGION"]
        assert "s|kI0ure_k3Y" == updated_plan_env["DISCOURSE_S3_SECRET_ACCESS_KEY"]
        assert "smtp.internal" == updated_plan_env["DISCOURSE_SMTP_ADDRESS"]
        assert "none" == updated_plan_env["DISCOURSE_SMTP_AUTHENTICATION"]
        assert "foo.internal" == updated_plan_env["DISCOURSE_SMTP_DOMAIN"]
        assert "none" == updated_plan_env["DISCOURSE_SMTP_OPENSSL_VERIFY_MODE"]
        assert "OBV10USLYF4K3" == updated_plan_env["DISCOURSE_SMTP_PASSWORD"]
        assert "587" == updated_plan_env["DISCOURSE_SMTP_PORT"]
        assert "apikey" == updated_plan_env["DISCOURSE_SMTP_USER_NAME"]
        assert updated_plan_env["DISCOURSE_USE_S3"]
        assert isinstance(harness.model.unit.status, ActiveStatus)


def test_db_relation():
    """
    arrange: given a deployed discourse charm
    act: when the database relation is added
    assert: the appropriate database name is set.
    """
    harness = helpers.start_harness()
    harness.set_leader(True)

    db_relation_data = harness.get_relation_data(
        # This attribute was defined in the helpers
        harness.db_relation_id,  # pylint: disable=no-member
        "postgresql",
    )

    assert (
        db_relation_data.get("database") == "discourse"
    ), "database name should be set after relation joined"
    assert (
        harness.charm._database.get_relation_data().get("POSTGRES_DB") == "discourse"
    ), "database name should be set after relation joined"


def test_add_admin_user():
    """
    arrange: an email and a password
    act: when the _on_add_admin_user_action mtehod is executed
    assert: the underlying rake command to add the user is executed
        with the appropriate parameters.
    """
    harness = helpers.start_harness()

    # We catch the exec call that we expect to register it and make sure that the
    # args passed to it are correct.
    expected_exec_call_was_made = False

    def bundle_handler(args: ops.testing.ExecArgs) -> None:
        nonlocal expected_exec_call_was_made
        expected_exec_call_was_made = True
        if (
            args.environment != harness._charm._create_discourse_environment_settings()
            or args.working_dir != DISCOURSE_PATH
            or args.user != "_daemon_"
            or args.stdin != f"{email}\n{password}\n{password}\nY\n"
            or args.timeout != 60
        ):
            raise ValueError(f"{args.command} wasn't made with the correct args.")

    harness.handle_exec(
        "discourse",
        [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "admin:create"],
        handler=bundle_handler,
    )

    charm: DiscourseCharm = typing.cast(DiscourseCharm, harness.charm)

    email = "sample@email.com"
    password = "somepassword"  # nosec
    event = MagicMock(spec=ActionEvent)
    event.params = {
        "email": email,
        "password": password,
    }
    charm._on_add_admin_user_action(event)


def test_anonymize_user():
    """
    arrange: set up discourse
    act: execute the _on_anonymize_user_action method
    assert: the underlying rake command to anonymize the user is executed
        with the appropriate parameters.
    """
    harness = helpers.start_harness()
    username = "someusername"

    # We catch the exec call that we expect to register it and make sure that the
    # args passed to it are correct.
    expected_exec_call_was_made = False

    def bundle_handler(args: ops.testing.ExecArgs) -> None:
        nonlocal expected_exec_call_was_made
        expected_exec_call_was_made = True
        if (
            args.environment != harness._charm._create_discourse_environment_settings()
            or args.working_dir != DISCOURSE_PATH
            or args.user != "_daemon_"
        ):
            raise ValueError(f"{args.command} wasn't made with the correct args.")

    harness.handle_exec(
        "discourse",
        ["bash", "-c", f"./bin/bundle exec rake users:anonymize[{username}]"],
        handler=bundle_handler,
    )
    charm: DiscourseCharm = typing.cast(DiscourseCharm, harness.charm)
    event = MagicMock(spec=ActionEvent)
    event.params = {"username": username}
    charm._on_anonymize_user_action(event)


def test_install_when_leader():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: trigger the install event on a leader unit
    assert: migrations are executed and assets are precompiled.
    """
    harness = helpers.start_harness()

    # exec calls that we want to monitor
    exec_calls = [
        [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "--trace", "db:migrate"],
        [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "assets:precompile"],
        [f"{DISCOURSE_PATH}/bin/rails", "runner", "puts Discourse::VERSION::STRING"],
    ]

    # construct the dict to store if those calls were executed
    expected_exec_call_was_made = {" ".join(call): False for call in exec_calls}

    # We catch the exec calls that we expect to register
    # it and make sure that the args passed to it are correct.
    def exec_handler(args: ops.testing.ExecArgs) -> None:
        nonlocal expected_exec_call_was_made

        # set the call as executed
        expected_exec_call_was_made[" ".join(args.command)] = True

        if (
            args.environment != harness._charm._create_discourse_environment_settings()
            or args.working_dir != DISCOURSE_PATH
            or args.user != "_daemon_"
        ):
            raise ValueError(f"{args.command} wasn't made with the correct args.")

    for call in exec_calls:
        harness.handle_exec("discourse", call, handler=exec_handler)

    harness.set_leader(True)
    harness.container_pebble_ready("discourse")
    harness.charm.on.install.emit()
    harness.framework.reemit()

    assert all(expected_exec_call_was_made.values())


def test_install_when_not_leader():
    """
    arrange: given a deployed discourse charm with all the required relations
    act: trigger the install event on a leader unit
    assert: migrations are executed and assets are precompiled.
    """
    harness = helpers.start_harness()

    # exec calls that we want to monitor
    exec_calls = [
        [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "assets:precompile"],
        [f"{DISCOURSE_PATH}/bin/rails", "runner", "puts Discourse::VERSION::STRING"],
    ]

    # construct the dict to store if those calls were executed
    expected_exec_call_was_made = {" ".join(call): False for call in exec_calls}

    # We catch the exec calls that we expect to register
    # it and make sure that the args passed to it are correct.
    def exec_handler(args: ops.testing.ExecArgs) -> None:
        nonlocal expected_exec_call_was_made

        # set the call as executed
        expected_exec_call_was_made[" ".join(args.command)] = True

        if (
            args.environment != harness._charm._create_discourse_environment_settings()
            or args.working_dir != DISCOURSE_PATH
            or args.user != "_daemon_"
        ):
            raise ValueError(f"{args.command} wasn't made with the correct args.")

    for call in exec_calls:
        harness.handle_exec("discourse", call, handler=exec_handler)

    harness.set_leader(False)
    harness.container_pebble_ready("discourse")
    harness.charm.on.install.emit()
    harness.framework.reemit()


@pytest.mark.parametrize(
    "relation_data, should_be_ready",
    [
        (
            {
                "database": DATABASE_NAME,
                "endpoints": "dbhost:5432,dbhost-2:5432",
                "password": secrets.token_hex(16),
                "username": "someuser",
            },
            True,
        ),
        (
            {
                "database": DATABASE_NAME,
                "endpoints": "foo",
                "password": secrets.token_hex(16),
                "username": "someuser",
            },
            False,
        ),
        (
            {
                "database": DATABASE_NAME,
                "endpoints": "dbhost:5432,dbhost-2:5432",
                "password": "",
                "username": "someuser",
            },
            False,
        ),
    ],
)
def test_postgres_relation_data(relation_data, should_be_ready):
    """
    arrange: given a deployed discourse charm and some relation data
    act: add the postgresql relation to the charm
    assert: the charm should wait for some correct relation data
    """
    harness = helpers.start_harness(with_postgres=False, with_redis=False)
    db_relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(db_relation_id, "postgresql/0")
    harness.update_relation_data(
        db_relation_id,
        "postgresql",
        relation_data,
    )
    if should_be_ready:
        assert harness.model.unit.status == WaitingStatus("Waiting for redis relation")
    else:
        assert harness.model.unit.status == WaitingStatus("Waiting for database relation")


@pytest.mark.parametrize(
    "relation_data, should_be_ready",
    [
        (
            {"hostname": "redis-host", "port": 1010},
            True,
        ),
        (
            {"hostname": "redis-host", "port": 0},
            False,
        ),
        (
            {"hostname": "", "port": 1010},
            False,
        ),
        (
            {"hostname": "redis-host", "port": None},
            False,
        ),
        (
            {"hostname": None, "port": None},
            False,
        ),
        (
            {},
            False,
        ),
        (
            {"port": 6379},
            False,
        ),
        (
            {"hostname": "redis-port"},
            False,
        ),
    ],
)
def test_redis_relation_data(relation_data, should_be_ready):
    """
    arrange: given a deployed discourse charm and some relation data
    act: add the redis relation to the charm
    assert: the charm should wait for some correct relation data
    """
    harness = helpers.start_harness(with_postgres=True, with_redis=False)
    redis_relation_id = harness.add_relation("redis", "redis")
    harness.add_relation_unit(redis_relation_id, "redis/0")
    harness.charm._stored.redis_relation = {redis_relation_id: relation_data}
    assert should_be_ready == harness.charm._are_db_relations_ready()
