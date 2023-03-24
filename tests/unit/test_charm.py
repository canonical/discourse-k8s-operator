# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Discourse charm."""

# pylint: disable=protected-access
# Protected access check is disabled in tests as we're injecting test data

import contextlib
import typing
import unittest
from unittest.mock import MagicMock, patch

import ops.model
import ops.pebble
from ops.charm import ActionEvent
from ops.model import ActiveStatus, BlockedStatus, Container, WaitingStatus
from ops.testing import Harness

from tests.unit._patched_charm import DISCOURSE_PATH, DiscourseCharm, pgsql_patch

BLOCKED_STATUS = BlockedStatus.name  # type: ignore


class TestDiscourseK8sCharm(unittest.TestCase):
    """Unit tests for Discourse charm."""

    def setUp(self):
        pgsql_patch.start()
        self.harness = Harness(DiscourseCharm)
        self.addCleanup(self.harness.cleanup)

    def tearDown(self):
        pgsql_patch.stop()

    @contextlib.contextmanager
    def _patch_exec(self, fail: bool = False) -> typing.Generator[unittest.mock.Mock, None, None]:
        """Patch the ops.model.Container.exec method.

        When fail argument is true, the execution will fail.

        Yields:
            Mock for the exec method.
        """
        exec_process_mock = unittest.mock.MagicMock()
        if not fail:
            exec_process_mock.wait_output = unittest.mock.MagicMock(return_value=("", ""))
        else:
            exec_process_mock.wait_output = unittest.mock.Mock()
            exec_process_mock.wait_output.side_effect = ops.pebble.ExecError([], 1, "", "")
        exec_function_mock = unittest.mock.MagicMock(return_value=exec_process_mock)
        with unittest.mock.patch.multiple(ops.model.Container, exec=exec_function_mock):
            yield exec_function_mock

    def test_relations_not_ready(self):
        """
        arrange: given a deployed discourse charm
        act: when pebble ready event is triggered
        assert: it will wait for the db relation.
        """
        self.harness.begin_with_initial_hooks()
        self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            WaitingStatus("Waiting for database relation"),
        )

    def test_db_relation_not_ready(self):
        """
        arrange: given a deployed discourse charm with the redis relation stablished
        act: when pebble ready event is triggered
        assert: it will wait for the db relation.
        """
        self.harness.begin_with_initial_hooks()
        self._add_redis_relation()
        self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            WaitingStatus("Waiting for database relation"),
        )

    def test_redis_relation_not_ready(self):
        """
        arrange: given a deployed discourse charm with the redis db stablished
        act: when pebble ready event is triggered
        assert: it will wait for the redis relation.
        """
        self.harness.begin_with_initial_hooks()
        self._add_postgres_relation()
        self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            WaitingStatus("Waiting for redis relation"),
        )

    def test_config_changed_when_no_saml_target(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when force_saml_login configuration is True and there's no saml_target_url
        assert: it will get to blocked status waiting for the latter.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.update_config({"force_saml_login": True, "saml_target_url": ""})
        with self._patch_exec():
            self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("force_saml_login can not be true without a saml_target_url"),
        )

    def test_config_changed_when_saml_sync_groups_and_no_url_invalid(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when saml_sync_groups configuration is provided and there's no saml_target_url
        assert: it will get to blocked status waiting for the latter.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.update_config({"saml_sync_groups": "group1", "saml_target_url": ""})
        with self._patch_exec():
            self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("'saml_sync_groups' cannot be specified without a 'saml_target_url'"),
        )

    def test_config_changed_when_saml_target_url_and_force_https_disabled(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when saml_target_url configuration is provided and force_https is False
        assert: it will get to blocked status waiting for the latter.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.update_config({"saml_target_url": "group1", "force_https": False})
        with self._patch_exec():
            self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus(
                "'saml_target_url' cannot be specified without 'force_https' being true"
            ),
        )

    def test_config_changed_when_no_cors(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when cors_origin configuration is empty
        assert: it will get to blocked status waiting for it.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.update_config({"cors_origin": ""})
        with self._patch_exec():
            self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("Required configuration missing: cors_origin"),
        )

    def test_config_changed_when_throttle_mode_invalid(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when throttle_level configuration is invalid
        assert: it will get to blocked status waiting for a valid value to be provided.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.update_config({"throttle_level": "Scream"})
        self.harness.container_pebble_ready("discourse")

        self.assertEqual(self.harness.model.unit.status.name, BLOCKED_STATUS)
        self.assertTrue("none permissive strict" in self.harness.model.unit.status.message)

    def test_config_changed_when_s3_and_no_bucket_invalid(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when s3_enabled configuration is True and there's no s3_bucket
        assert: it will get to blocked status waiting for the latter.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.update_config(
            {
                "s3_access_key_id": "3|33+",
                "s3_enabled": True,
                "s3_endpoint": "s3.endpoint",
                "s3_region": "the-infinite-and-beyond",
                "s3_secret_access_key": "s|kI0ure_k3Y",
            }
        )
        self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("'s3_enabled' requires 's3_bucket'"),
        )

    @patch.object(Container, "exec")
    def test_config_changed_when_valid_no_s3_backup_nor_cdn(self, mock_exec):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when a valid configuration is provided
        assert: the appropriate configuration values are passed to the pod and the unit
            reaches Active status.
        """
        self.harness.begin_with_initial_hooks()
        self.harness.disable_hooks()
        self.harness.set_leader(True)
        self._add_database_relations()
        self.harness.update_config(
            {
                "s3_access_key_id": "3|33+",
                "s3_bucket": "who-s-a-good-bucket?",
                "s3_enabled": True,
                "s3_endpoint": "s3.endpoint",
                "s3_region": "the-infinite-and-beyond",
                "s3_secret_access_key": "s|kI0ure_k3Y",
            }
        )
        self.harness.container_pebble_ready("discourse")
        self.harness.framework.reemit()

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        mock_exec.assert_any_call(
            [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "s3:upload_assets"],
            environment=updated_plan_env,
            working_dir=DISCOURSE_PATH,
            user="discourse",
        )
        self.assertNotIn("DISCOURSE_BACKUP_LOCATION", updated_plan_env)
        self.assertEqual("*", updated_plan_env["DISCOURSE_CORS_ORIGIN"])
        self.assertEqual("dbhost", updated_plan_env["DISCOURSE_DB_HOST"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_DB_NAME"])
        self.assertEqual("somepasswd", updated_plan_env["DISCOURSE_DB_PASSWORD"])
        self.assertEqual("someuser", updated_plan_env["DISCOURSE_DB_USERNAME"])
        self.assertTrue(updated_plan_env["DISCOURSE_ENABLE_CORS"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_HOSTNAME"])
        self.assertEqual("redis-host", updated_plan_env["DISCOURSE_REDIS_HOST"])
        self.assertEqual("1010", updated_plan_env["DISCOURSE_REDIS_PORT"])
        self.assertTrue(updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"])
        self.assertEqual("3|33+", updated_plan_env["DISCOURSE_S3_ACCESS_KEY_ID"])
        self.assertNotIn("DISCOURSE_S3_BACKUP_BUCKET", updated_plan_env)
        self.assertNotIn("DISCOURSE_S3_CDN_URL", updated_plan_env)
        self.assertEqual("who-s-a-good-bucket?", updated_plan_env["DISCOURSE_S3_BUCKET"])
        self.assertEqual("s3.endpoint", updated_plan_env["DISCOURSE_S3_ENDPOINT"])
        self.assertEqual("the-infinite-and-beyond", updated_plan_env["DISCOURSE_S3_REGION"])
        self.assertEqual("s|kI0ure_k3Y", updated_plan_env["DISCOURSE_S3_SECRET_ACCESS_KEY"])
        self.assertTrue(updated_plan_env["DISCOURSE_USE_S3"])
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        self.assertEqual(
            "discourse-k8s", self.harness.charm.ingress.config_dict["service-hostname"]
        )

    def test_config_changed_when_valid_no_fingerprint(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when a valid configuration is provided
        assert: the appropriate configuration values are passed to the pod and the unit
            reaches Active status.
        """
        self.harness.begin_with_initial_hooks()
        self.harness.disable_hooks()
        self._add_database_relations()
        with self._patch_exec():
            self.harness.update_config(
                {
                    "force_saml_login": True,
                    "saml_target_url": "https://login.sample.com/+saml",
                    "saml_sync_groups": "group1",
                    "s3_enabled": False,
                    "force_https": True,
                }
            )
            self.harness.container_pebble_ready("discourse")
            self.harness.framework.reemit()

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        self.assertEqual("*", updated_plan_env["DISCOURSE_CORS_ORIGIN"])
        self.assertEqual("dbhost", updated_plan_env["DISCOURSE_DB_HOST"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_DB_NAME"])
        self.assertEqual("somepasswd", updated_plan_env["DISCOURSE_DB_PASSWORD"])
        self.assertEqual("someuser", updated_plan_env["DISCOURSE_DB_USERNAME"])
        self.assertTrue(updated_plan_env["DISCOURSE_ENABLE_CORS"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_HOSTNAME"])
        self.assertEqual("redis-host", updated_plan_env["DISCOURSE_REDIS_HOST"])
        self.assertEqual("1010", updated_plan_env["DISCOURSE_REDIS_PORT"])
        self.assertNotIn("DISCOURSE_SAML_CERT_FINGERPRINT", updated_plan_env)
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_FULL_SCREEN_LOGIN"])
        self.assertEqual(
            "https://login.sample.com/+saml", updated_plan_env["DISCOURSE_SAML_TARGET_URL"]
        )
        self.assertEqual("false", updated_plan_env["DISCOURSE_SAML_GROUPS_FULLSYNC"])
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS"])
        self.assertEqual("group1", updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS_LIST"])
        self.assertTrue(updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_AUTHENTICATION"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_OPENSSL_VERIFY_MODE"])
        self.assertNotIn("DISCOURSE_USE_S3", updated_plan_env)
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        self.assertEqual(
            "discourse-k8s", self.harness.charm.ingress.config_dict["service-hostname"]
        )

    def test_config_changed_when_valid(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when a valid configuration is provided
        assert: the appropriate configuration values are passed to the pod and the unit
            reaches Active status.
        """
        self.harness.begin_with_initial_hooks()
        self.harness.disable_hooks()
        self._add_database_relations()
        with self._patch_exec():
            self.harness.update_config(
                {
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
            self.harness.container_pebble_ready("discourse")
            self.harness.framework.reemit()

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        self.assertEqual("s3", updated_plan_env["DISCOURSE_BACKUP_LOCATION"])
        self.assertEqual("*", updated_plan_env["DISCOURSE_CORS_ORIGIN"])
        self.assertEqual("dbhost", updated_plan_env["DISCOURSE_DB_HOST"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_DB_NAME"])
        self.assertEqual("somepasswd", updated_plan_env["DISCOURSE_DB_PASSWORD"])
        self.assertEqual("someuser", updated_plan_env["DISCOURSE_DB_USERNAME"])
        self.assertEqual("user@foo.internal", updated_plan_env["DISCOURSE_DEVELOPER_EMAILS"])
        self.assertTrue(updated_plan_env["DISCOURSE_ENABLE_CORS"])
        self.assertEqual("discourse.local", updated_plan_env["DISCOURSE_HOSTNAME"])
        self.assertEqual("redis-host", updated_plan_env["DISCOURSE_REDIS_HOST"])
        self.assertEqual("1010", updated_plan_env["DISCOURSE_REDIS_PORT"])
        self.assertIsNotNone(updated_plan_env["DISCOURSE_SAML_CERT_FINGERPRINT"])
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_FULL_SCREEN_LOGIN"])
        self.assertEqual(
            "https://login.ubuntu.com/+saml", updated_plan_env["DISCOURSE_SAML_TARGET_URL"]
        )
        self.assertEqual("false", updated_plan_env["DISCOURSE_SAML_GROUPS_FULLSYNC"])
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS"])
        self.assertEqual("group1", updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS_LIST"])
        self.assertTrue(updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"])
        self.assertEqual("3|33+", updated_plan_env["DISCOURSE_S3_ACCESS_KEY_ID"])
        self.assertEqual("back-bucket", updated_plan_env["DISCOURSE_S3_BACKUP_BUCKET"])
        self.assertEqual("s3.cdn", updated_plan_env["DISCOURSE_S3_CDN_URL"])
        self.assertEqual("who-s-a-good-bucket?", updated_plan_env["DISCOURSE_S3_BUCKET"])
        self.assertEqual("s3.endpoint", updated_plan_env["DISCOURSE_S3_ENDPOINT"])
        self.assertEqual("the-infinite-and-beyond", updated_plan_env["DISCOURSE_S3_REGION"])
        self.assertEqual("s|kI0ure_k3Y", updated_plan_env["DISCOURSE_S3_SECRET_ACCESS_KEY"])
        self.assertEqual("smtp.internal", updated_plan_env["DISCOURSE_SMTP_ADDRESS"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_AUTHENTICATION"])
        self.assertEqual("foo.internal", updated_plan_env["DISCOURSE_SMTP_DOMAIN"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_OPENSSL_VERIFY_MODE"])
        self.assertEqual("OBV10USLYF4K3", updated_plan_env["DISCOURSE_SMTP_PASSWORD"])
        self.assertEqual("587", updated_plan_env["DISCOURSE_SMTP_PORT"])
        self.assertEqual("apikey", updated_plan_env["DISCOURSE_SMTP_USER_NAME"])
        self.assertTrue(updated_plan_env["DISCOURSE_USE_S3"])
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_db_relation(self):
        """
        arrange: given a deployed discourse charm
        act: when the database relation is added
        assert: the appropriate database name is set.
        """
        self.harness.begin()
        self._add_database_relations()
        self.harness.set_leader(True)
        # testing harness not re-emits deferred events, manually trigger that
        self.harness.framework.reemit()

        db_relation_data = self.harness.get_relation_data(
            self.db_relation_id, self.harness.charm.app.name
        )

        self.assertEqual(
            db_relation_data.get("database"),
            "discourse",
            "database name should be set after relation joined",
        )

    @patch.object(Container, "exec")
    def test_add_admin_user(self, mock_exec):
        """
        arrange: an email and a password
        act: when the _on_add_admin_user_action mtehod is executed
        assert: the underlying rake command to add the user is executed
            with the appropriate parameters.
        """
        self.harness.begin()
        self.harness.disable_hooks()
        self._add_database_relations()

        charm: DiscourseCharm = typing.cast(DiscourseCharm, self.harness.charm)
        self.harness.container_pebble_ready("discourse")

        email = "sample@email.com"
        password = "somepassword"  # nosec
        event = MagicMock(spec=ActionEvent)
        event.params = {
            "email": email,
            "password": password,
        }
        charm._on_add_admin_user_action(event)

        mock_exec.assert_any_call(
            [
                f"{DISCOURSE_PATH}/bin/bundle",
                "exec",
                "rake",
                "admin:create",
            ],
            user="discourse",
            working_dir=DISCOURSE_PATH,
            environment=charm._create_discourse_environment_settings(),
            stdin=f"{email}\n{password}\n{password}\nY\n",
            timeout=60,
        )

    @patch.object(Container, "exec")
    def test_anonymize_user(self, mock_exec):
        """
        arrange: set up discourse
        act: execute the _on_anonymize_user_action method
        assert: the underlying rake command to anonymize the user is executed
            with the appropriate parameters.
        """
        self.harness.begin()
        self.harness.disable_hooks()
        self._add_database_relations()

        charm: DiscourseCharm = typing.cast(DiscourseCharm, self.harness.charm)
        self.harness.container_pebble_ready("discourse")

        username = "someusername"
        event = MagicMock(spec=ActionEvent)
        event.params = {"username": username}
        charm._on_anonymize_user_action(event)

        mock_exec.assert_any_call(
            [
                "bash",
                "-c",
                f"./bin/bundle exec rake users:anonymize[{username}]",
            ],
            user="discourse",
            working_dir=DISCOURSE_PATH,
            environment=charm._create_discourse_environment_settings(),
        )

    def test_install_when_leader(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: trigger the install event on a leader unit
        assert: migrations are executed and assets are precompiled.
        """
        self.harness.begin_with_initial_hooks()
        self.harness.set_leader(True)
        self._add_database_relations()
        with self._patch_exec() as mock_exec:
            self.harness.container_pebble_ready("discourse")
            self.harness.charm.on.install.emit()
            self.harness.framework.reemit()

            updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
            updated_plan_env = updated_plan["services"]["discourse"]["environment"]
            mock_exec.assert_any_call(
                [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "--trace", "db:migrate"],
                environment=updated_plan_env,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )
            mock_exec.assert_any_call(
                [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "assets:precompile"],
                environment=updated_plan_env,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )
            mock_exec.assert_any_call(
                [f"{DISCOURSE_PATH}/bin/rails", "runner", "puts Discourse::VERSION::STRING"],
                environment=updated_plan_env,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )

    def test_install_when_not_leader(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: trigger the install event on a leader unit
        assert: migrations are executed and assets are precompiled.
        """
        self.harness.begin_with_initial_hooks()
        self.harness.set_leader(False)
        self._add_database_relations()
        with self._patch_exec() as mock_exec:
            self.harness.container_pebble_ready("discourse")
            self.harness.charm.on.install.emit()
            self.harness.framework.reemit()

            updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
            updated_plan_env = updated_plan["services"]["discourse"]["environment"]
            mock_exec.assert_any_call(
                [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "assets:precompile"],
                environment=updated_plan_env,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )
            mock_exec.assert_any_call(
                [f"{DISCOURSE_PATH}/bin/rails", "runner", "puts Discourse::VERSION::STRING"],
                environment=updated_plan_env,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )

    def _add_postgres_relation(self):
        "Add postgresql relation and relation data to the charm."
        self.harness.charm._stored.db_name = "discourse-k8s"
        self.harness.charm._stored.db_user = "someuser"
        self.harness.charm._stored.db_password = "somepasswd"  # nosec
        self.harness.charm._stored.db_host = "dbhost"
        # get a relation ID for the test outside of __init__ (note pylint disable)
        self.db_relation_id = (  # pylint: disable=attribute-defined-outside-init
            self.harness.add_relation("db", "postgresql")
        )
        self.harness.add_relation_unit(self.db_relation_id, "postgresql/0")

    def _add_redis_relation(self):
        "Add redis relation and relation data to the charm."
        redis_relation_id = self.harness.add_relation("redis", "redis")
        self.harness.add_relation_unit(redis_relation_id, "redis/0")
        self.harness.charm._stored.redis_relation = {
            redis_relation_id: {"hostname": "redis-host", "port": 1010}
        }

    def _add_database_relations(self):
        "Add postgresql and redis relations and relation data to the charm."
        self._add_postgres_relation()
        self._add_redis_relation()
