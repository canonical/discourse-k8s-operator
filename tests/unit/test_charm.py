#!/usr/bin/env python3

# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, patch

from ops.model import ActiveStatus, BlockedStatus, Container, WaitingStatus
from ops.testing import Harness

from tests.unit._patched_charm import SCRIPT_PATH, DiscourseCharm, pgsql_patch


class MockExecProcess(object):
    wait_output: MagicMock = MagicMock(return_value=("", None))


class TestDiscourseK8sCharm(unittest.TestCase):
    def setUp(self):
        pgsql_patch.start()
        self.harness = Harness(DiscourseCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.harness.set_leader(True)

    def tearDown(self):
        pgsql_patch.stop()

    def test_db_relation_not_ready(self):
        """
        arrange: given a deployed discourse charm
        act: when pebble ready event is triggered
        assert: it will wait for the db relation.
        """
        self.harness.container_pebble_ready("discourse")

        self.assertEqual(
            self.harness.model.unit.status,
            WaitingStatus("Waiting for database relation"),
        )

    def test_redis_relation_not_ready(self):
        """
        arrange: given a deployed discourse charm
        act: when pebble ready event is triggered
        assert: it will wait for the db relation.
        """
        self.add_postgres_relation()
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
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")

        self.harness.update_config(
            {
                "developer_emails": "user@foo.internal",
                "force_saml_login": True,
                "smtp_address": "smtp.internal",
                "smtp_domain": "foo.internal",
            }
        )

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
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")

        self.harness.update_config(
            {
                "developer_emails": "user@foo.internal",
                "saml_sync_groups": "group1",
                "smtp_address": "smtp.internal",
                "smtp_domain": "foo.internal",
            }
        )

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("'saml_sync_groups' cannot be specified without a 'saml_target_url'"),
        )

    def test_config_changed_when_no_cors(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when cors_origin configuration is empty
        assert: it will get to blocked status waiting for it.
        """
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")

        self.harness.update_config(
            {
                "cors_origin": "",
                "developer_emails": "user@foo.internal",
                "smtp_address": "smtp.internal",
                "smtp_domain": "foo.internal",
            }
        )

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
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")

        self.harness.update_config(
            {
                "developer_emails": "user@foo.internal",
                "throttle_level": "Scream",
                "smtp_address": "smtp.internal",
                "smtp_domain": "foo.internal",
            }
        )

        self.assertEqual(
            self.harness.model.unit.status.name,
            BlockedStatus.name,
        )
        self.assertTrue("none permissive strict" in self.harness.model.unit.status.message)

    def test_config_changed_when_s3_and_no_bucket_invalid(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when s3_enabled configuration is True and there's no s3_bucket
        assert: it will get to blocked status waiting for the latter.
        """
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")

        self.harness.update_config(
            {
                "developer_emails": "user@foo.internal",
                "smtp_address": "smtp.internal",
                "smtp_domain": "foo.internal",
                "s3_access_key_id": "3|33+",
                "s3_enabled": True,
                "s3_endpoint": "s3.endpoint",
                "s3_region": "the-infinite-and-beyond",
                "s3_secret_access_key": "s|kI0ure_k3Y",
            }
        )

        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("'s3_enabled' requires 's3_bucket'"),
        )

    def test_config_changed_when_valid_no_s3_backup_nor_cdn(self):
        """
        arrange: given a deployed discourse charm with all the required relations
        act: when a valid configuration is provided
        assert: the appropriate configuration values are passed to the pod and the unit
        reaches Active status.
        """
        self.add_database_relations()
        with patch.object(Container, "exec", return_value=MockExecProcess()) as exec_mock:
            self.harness.container_pebble_ready("discourse")

            self.harness.update_config(
                {
                    "developer_emails": "user@foo.internal",
                    "enable_cors": True,
                    "smtp_address": "smtp.internal",
                    "smtp_domain": "foo.internal",
                    "s3_access_key_id": "3|33+",
                    "s3_bucket": "who-s-a-good-bucket?",
                    "s3_enabled": True,
                    "s3_endpoint": "s3.endpoint",
                    "s3_region": "the-infinite-and-beyond",
                    "s3_secret_access_key": "s|kI0ure_k3Y",
                }
            )

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        exec_mock.assert_any_call(
            [f"{SCRIPT_PATH}/pod_setup.sh"],
            environment=updated_plan_env,
            working_dir="/srv/discourse/app",
        )
        self.assertNotIn("DISCOURSE_BACKUP_LOCATION", updated_plan_env)
        self.assertEqual("*", updated_plan_env["DISCOURSE_CORS_ORIGIN"])
        self.assertEqual("dbhost", updated_plan_env["DISCOURSE_DB_HOST"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_DB_NAME"])
        self.assertEqual("somepasswd", updated_plan_env["DISCOURSE_DB_PASSWORD"])
        self.assertEqual("someuser", updated_plan_env["DISCOURSE_DB_USERNAME"])
        self.assertEqual("user@foo.internal", updated_plan_env["DISCOURSE_DEVELOPER_EMAILS"])
        self.assertTrue(updated_plan_env["DISCOURSE_ENABLE_CORS"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_HOSTNAME"])
        self.assertEqual("redis-host", updated_plan_env["DISCOURSE_REDIS_HOST"])
        self.assertEqual(1010, updated_plan_env["DISCOURSE_REDIS_PORT"])
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
        self.add_database_relations()
        with patch.object(Container, "exec", return_value=MockExecProcess()) as exec_mock:
            self.harness.container_pebble_ready("discourse")

            self.harness.update_config(
                {
                    "developer_emails": "user@foo.internal",
                    "enable_cors": True,
                    "force_saml_login": True,
                    "saml_target_url": "https://login.sample.com/+saml",
                    "saml_sync_groups": "group1",
                    "smtp_address": "smtp.internal",
                    "smtp_domain": "foo.internal",
                    "smtp_password": "OBV10USLYF4K3",
                    "smtp_username": "apikey",
                    "s3_enabled": False,
                }
            )

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        exec_mock.assert_any_call(
            [f"{SCRIPT_PATH}/pod_setup.sh"],
            environment=updated_plan_env,
            working_dir="/srv/discourse/app",
        )
        self.assertEqual("*", updated_plan_env["DISCOURSE_CORS_ORIGIN"])
        self.assertEqual("dbhost", updated_plan_env["DISCOURSE_DB_HOST"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_DB_NAME"])
        self.assertEqual("somepasswd", updated_plan_env["DISCOURSE_DB_PASSWORD"])
        self.assertEqual("someuser", updated_plan_env["DISCOURSE_DB_USERNAME"])
        self.assertEqual("user@foo.internal", updated_plan_env["DISCOURSE_DEVELOPER_EMAILS"])
        self.assertTrue(updated_plan_env["DISCOURSE_ENABLE_CORS"])
        self.assertEqual("discourse-k8s", updated_plan_env["DISCOURSE_HOSTNAME"])
        self.assertEqual("redis-host", updated_plan_env["DISCOURSE_REDIS_HOST"])
        self.assertEqual(1010, updated_plan_env["DISCOURSE_REDIS_PORT"])
        self.assertNotIn("DISCOURSE_SAML_CERT_FINGERPRINT", updated_plan_env)
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_FULL_SCREEN_LOGIN"])
        self.assertEqual(
            "https://login.sample.com/+saml", updated_plan_env["DISCOURSE_SAML_TARGET_URL"]
        )
        self.assertEqual("false", updated_plan_env["DISCOURSE_SAML_GROUPS_FULLSYNC"])
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS"])
        self.assertEqual("group1", updated_plan_env["DISCOURSE_SAML_SYNC_GROUPS_LIST"])
        self.assertTrue(updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"])
        self.assertEqual("smtp.internal", updated_plan_env["DISCOURSE_SMTP_ADDRESS"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_AUTHENTICATION"])
        self.assertEqual("foo.internal", updated_plan_env["DISCOURSE_SMTP_DOMAIN"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_OPENSSL_VERIFY_MODE"])
        self.assertEqual("OBV10USLYF4K3", updated_plan_env["DISCOURSE_SMTP_PASSWORD"])
        self.assertEqual("587", updated_plan_env["DISCOURSE_SMTP_PORT"])
        self.assertEqual("apikey", updated_plan_env["DISCOURSE_SMTP_USER_NAME"])
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
        self.add_database_relations()
        with patch.object(Container, "exec", return_value=MockExecProcess()) as exec_mock:
            self.harness.container_pebble_ready("discourse")

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
                }
            )

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]
        exec_mock.assert_any_call(
            [f"{SCRIPT_PATH}/pod_setup.sh"],
            environment=updated_plan_env,
            working_dir="/srv/discourse/app",
        )
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
        self.assertEqual(1010, updated_plan_env["DISCOURSE_REDIS_PORT"])
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
        self.assertEqual(
            "discourse.local", self.harness.charm.ingress.config_dict["service-hostname"]
        )

    def test_db_relation(self):
        """
        arrange: given a deployed discourse charm
        act: when the database relation is added
        assert: the appropriate database name is set.
        """
        self.add_database_relations()
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

    def add_postgres_relation(self):
        "Adds postgresql relation and relation data to the charm."
        self.harness.charm._stored.db_name = "discourse-k8s"
        self.harness.charm._stored.db_user = "someuser"
        self.harness.charm._stored.db_password = "somepasswd"  # nosec
        self.harness.charm._stored.db_host = "dbhost"
        self.db_relation_id = self.harness.add_relation("db", "postgresql")
        self.harness.add_relation_unit(self.db_relation_id, "postgresql/0")

    def add_database_relations(self):
        "Adds postgresql and redis relations and relation data to the charm."
        self.add_postgres_relation()

        redis_relation_id = self.harness.add_relation("redis", "redis")
        self.harness.add_relation_unit(redis_relation_id, "redis/0")
        self.harness.charm._stored.redis_relation = {
            redis_relation_id: {"hostname": "redis-host", "port": 1010}
        }
