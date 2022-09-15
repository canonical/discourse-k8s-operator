#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest

from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness

from tests.unit._patched_charm import DiscourseCharm, pgsql_patch


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
        self.harness.container_pebble_ready("discourse")
        self.assertEqual(
            self.harness.model.unit.status,
            WaitingStatus("Waiting for database relation"),
        )

    def test_config_changed_when_no_saml_target(self):
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")
        self.harness.update_config(
            {
                "external_hostname": "discourse.local",
                "force_saml_login": True,
            }
        )
        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("force_saml_login can not be true without a saml_target_url"),
        )

    def test_config_changed_when_no_cors(self):
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")
        self.harness.update_config(
            {
                "cors_origin": "",
                "external_hostname": "discourse.local",
            }
        )
        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("Required configuration missing: cors_origin"),
        )

    def test_config_changed_when_throttle_mode_invalid(self):
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")
        self.harness.update_config(
            {
                "external_hostname": "discourse.local",
                "throttle_level": "Scream",
            }
        )
        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("throttle_level must be one of: none permissive strict"),
        )

    def test_config_changed_when_valid(self):
        self.add_database_relations()
        self.harness.container_pebble_ready("discourse")
        self.harness.update_config(
            {
                "enable_cors": True,
                "external_hostname": "discourse.local",
                "force_saml_login": True,
                "saml_target_url": "https://login.ubuntu.com/+saml",
                "smtp_password": "OBV10USLYF4K3",
                "smtp_username": "apikey",
                "tls_secret_name": "somesecret",
            }
        )

        updated_plan = self.harness.get_container_pebble_plan("discourse").to_dict()
        print(updated_plan)
        updated_plan_env = updated_plan["services"]["discourse"]["environment"]

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
        self.assertEqual(
            "32:15:20:9F:A4:3C:8E:3E:8E:47:72:62:9A:86:8D:0E:E6:CF:45:D5",
            updated_plan_env["DISCOURSE_SAML_CERT_FINGERPRINT"],
        )
        self.assertEqual("true", updated_plan_env["DISCOURSE_SAML_FULL_SCREEN_LOGIN"])
        self.assertEqual("https://login.ubuntu.com/+saml", updated_plan_env["DISCOURSE_SAML_TARGET_URL"])
        self.assertTrue(updated_plan_env["DISCOURSE_SERVE_STATIC_ASSETS"])
        self.assertEqual("127.0.0.1", updated_plan_env["DISCOURSE_SMTP_ADDRESS"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_AUTHENTICATION"])
        self.assertEqual("foo.internal", updated_plan_env["DISCOURSE_SMTP_DOMAIN"])
        self.assertEqual("none", updated_plan_env["DISCOURSE_SMTP_OPENSSL_VERIFY_MODE"])
        self.assertEqual("OBV10USLYF4K3", updated_plan_env["DISCOURSE_SMTP_PASSWORD"])
        self.assertEqual(587, updated_plan_env["DISCOURSE_SMTP_PORT"])
        self.assertEqual("apikey", updated_plan_env["DISCOURSE_SMTP_USER_NAME"])

        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

        self.assertEqual("discourse.local", self.harness.charm.ingress.config_dict["service-hostname"])
        self.assertEqual("somesecret", self.harness.charm.ingress.config_dict["tls-secret-name"])
        self.assertEqual(20, self.harness.charm.ingress.config_dict["max-body-size"])

    def test_db_relation(self):
        self.add_database_relations()
        self.harness.set_leader(True)
        # testing harness not re-emits deferred events, manually trigger that
        self.harness.framework.reemit()
        db_relation_data = self.harness.get_relation_data(self.db_relation_id, self.harness.charm.app.name)
        self.assertEqual(
            db_relation_data.get("database"),
            "discourse-k8s",
            "database name should be set after relation joined",
        )

    def add_database_relations(self):
        self.harness.charm._stored.db_name = "discourse-k8s"
        self.harness.charm._stored.db_user = "someuser"
        self.harness.charm._stored.db_password = "somepasswd"
        self.harness.charm._stored.db_host = "dbhost"
        self.db_relation_id = self.harness.add_relation("db", self.harness.charm.app.name)
        self.harness.add_relation_unit(self.db_relation_id, "postgresql/0")

        redis_relation_id = self.harness.add_relation("redis", self.harness.charm.app.name)
        self.harness.add_relation_unit(redis_relation_id, "redis/0")
        self.harness.charm._stored.redis_relation = {redis_relation_id: {"hostname": "redis-host", "port": 1010}}
