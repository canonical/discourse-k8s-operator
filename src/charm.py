#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Discourse on kubernetes."""
import logging
from collections import namedtuple
from typing import Dict, List, Optional

import ops.lib
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.nginx_ingress_integrator.v0.ingress import IngressRequires
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from ops.charm import CharmBase, HookEvent
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import ExecError

logger = logging.getLogger(__name__)
pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

S3Info = namedtuple("S3Info", ["enabled", "region", "bucket", "endpoint"])

DATABASE_NAME = "discourse"
THROTTLE_LEVELS = {
    "none": {
        "DISCOURSE_MAX_REQS_PER_IP_MODE": "none",
        "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
    },
    "permissive": {
        "DISCOURSE_MAX_REQS_PER_IP_MODE": "warn+block",
        "DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE": 1000,
        "DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS": 100,
        "DISCOURSE_MAX_USER_API_REQS_PER_MINUTE": 400,
        "DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS": 400,
        "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
    },
    "strict": {
        "DISCOURSE_MAX_REQS_PER_IP_MODE": "block",
        "DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE": 200,
        "DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS": 50,
        "DISCOURSE_MAX_USER_API_REQS_PER_MINUTE": 100,
        "DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS": 200,
        "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
    },
}
LOG_PATH = "/srv/discourse/app/log/production.log"
REQUIRED_S3_SETTINGS = ["s3_access_key_id", "s3_bucket", "s3_region", "s3_secret_access_key"]

SERVICE_NAME = "discourse"
SERVICE_PORT = 3000

SCRIPT_PATH = "/srv/scripts"


class DiscourseCharm(CharmBase):
    """Charm for Discourse on kubernetes."""

    on = RedisRelationCharmEvents()
    _stored = StoredState()

    def __init__(self, *args):
        """Initialize defaults and event handlers."""
        super().__init__(*args)

        self._stored.set_default(
            db_name=None,
            db_user=None,
            db_password=None,
            db_host=None,
            redis_relation={},
        )
        self.ingress = IngressRequires(self, self._make_ingress_config())
        self.framework.observe(self.on.discourse_pebble_ready, self._config_changed)
        self.framework.observe(self.on.config_changed, self._config_changed)

        self.db = pgsql.PostgreSQLClient(self, "db")
        self.framework.observe(
            self.db.on.database_relation_joined, self._on_database_relation_joined
        )
        self.framework.observe(self.db.on.master_changed, self._on_database_changed)

        self.redis = RedisRequires(self, self._stored)
        self.framework.observe(self.on.redis_relation_updated, self._config_changed)

        self._metrics_endpoint = MetricsEndpointProvider(
            self, jobs=[{"static_configs": [{"targets": ["*:9394"]}]}]
        )
        self._logging = LogProxyConsumer(
            self, relation_name="logging", log_files=[LOG_PATH], container_name="discourse"
        )
        self._grafana_dashboards = GrafanaDashboardProvider(self)

    def _make_ingress_config(self) -> Dict:
        """Return a dict of our ingress config."""
        ingress_config = {
            "service-hostname": self._get_external_hostname(),
            "service-name": self.app.name,
            "service-port": SERVICE_PORT,
            "session-cookie-max-age": 3600,
        }
        return ingress_config

    def _get_external_hostname(self) -> str:
        """Return external_hostname if exists or the default value."""
        return (
            self.config["external_hostname"] if self.config["external_hostname"] else self.app.name
        )

    def _is_config_valid(self) -> bool:
        """Check that the provided config is valid.

        - Returns True if config is valid, False otherwise.

        - Sets model status as appropriate.
        """
        errors = []
        missing_fields = self._get_missing_config_fields()

        if missing_fields:
            errors.append(f"Required configuration missing: {','.join(missing_fields)}")

        if self.config["throttle_level"] not in THROTTLE_LEVELS:
            errors.append(f"throttle_level must be one of: {' '.join(THROTTLE_LEVELS.keys())}")

        if self.config["force_saml_login"] and not self.config["saml_target_url"]:
            errors.append("force_saml_login can not be true without a saml_target_url")

        if self.config["saml_sync_groups"] and not self.config["saml_target_url"]:
            errors.append("'saml_sync_groups' cannot be specified without a 'saml_target_url'")

        if self.config.get("s3_enabled"):
            [
                errors.append(f"'s3_enabled' requires '{s3_config}'")
                for s3_config in REQUIRED_S3_SETTINGS
                if not self.config[s3_config]
            ]

        if errors:
            self.model.unit.status = BlockedStatus(", ".join(errors))

        return not errors

    def _get_saml_config(self) -> Dict:
        saml_fingerprints = {
            "https://login.ubuntu.com/+saml": "32:15:20:9F:A4:3C:8E:3E:8E:47:72:62:9A:86:8D:0E:E6:CF:45:D5"
        }
        saml_config = {}

        if self.config.get("saml_target_url"):
            saml_config["DISCOURSE_SAML_TARGET_URL"] = self.config["saml_target_url"]
            saml_config["DISCOURSE_SAML_FULL_SCREEN_LOGIN"] = (
                "true" if self.config["force_saml_login"] else "false"
            )
            fingerprint = saml_fingerprints.get(self.config["saml_target_url"])
            if fingerprint:
                saml_config["DISCOURSE_SAML_CERT_FINGERPRINT"] = fingerprint

        saml_sync_groups = [
            x.strip() for x in self.config["saml_sync_groups"].split(",") if x.strip()
        ]
        if saml_sync_groups:
            # Per https://github.com/discourse/discourse-saml setting this to `true`
            # means the assigned groups will be completely synced including adding
            # AND removing groups based on the SAML provider.
            saml_config["DISCOURSE_SAML_GROUPS_FULLSYNC"] = "false"
            saml_config["DISCOURSE_SAML_SYNC_GROUPS"] = "true"
            saml_config["DISCOURSE_SAML_SYNC_GROUPS_LIST"] = "|".join(saml_sync_groups)

        return saml_config

    def _get_missing_config_fields(self) -> List[str]:
        """Check for missing fields in juju config.

        - Returns a list of required fields that are either not present
        or are empty.
        """
        needed_fields = [
            "cors_origin",
            "developer_emails",
            "smtp_address",
            "smtp_domain",
        ]
        return [field for field in needed_fields if not self.config.get(field)]

    def _get_s3_env(self) -> Dict:
        """Get the list of S3-related environment variables from charm's configuration."""
        s3_env = {
            "DISCOURSE_S3_ACCESS_KEY_ID": self.config["s3_access_key_id"],
            "DISCOURSE_S3_BUCKET": self.config["s3_bucket"],
            "DISCOURSE_S3_ENDPOINT": self.config.get("s3_endpoint", "s3.amazonaws.com"),
            "DISCOURSE_S3_REGION": self.config["s3_region"],
            "DISCOURSE_S3_SECRET_ACCESS_KEY": self.config["s3_secret_access_key"],
            "DISCOURSE_S3_INSTALL_CORS_RULE": str(
                self.config.get("s3_install_cors_rule", True)
            ).lower(),
            "DISCOURSE_USE_S3": "true",
        }
        if self.config.get("s3_backup_bucket"):
            s3_env["DISCOURSE_BACKUP_LOCATION"] = "s3"
            s3_env["DISCOURSE_S3_BACKUP_BUCKET"] = self.config["s3_backup_bucket"]
        if self.config.get("s3_cdn_url"):
            s3_env["DISCOURSE_S3_CDN_URL"] = self.config["s3_cdn_url"]

        return s3_env

    def _create_discourse_environment_settings(self) -> Dict:
        """Create the pod environment config from the existing config."""
        # Get redis connection information from the relation.
        redis_hostname = None
        redis_port = 6379
        for redis_unit in self._stored.redis_relation:
            redis_hostname = self._stored.redis_relation[redis_unit]["hostname"]
            redis_port = self._stored.redis_relation[redis_unit]["port"]
            logger.debug(
                "Got redis connection details from relation of %s:%s", redis_hostname, redis_port
            )

        pod_config = {
            # Since pebble exec command doesn't copy the container env (envVars set in Dockerfile),
            # I need to take the required envVars for the application to work properly
            "CONTAINER_APP_NAME": "discourse",
            "CONTAINER_APP_ROOT": "/srv/discourse",
            "CONTAINER_APP_USERNAME": "discourse",
            "DISCOURSE_CORS_ORIGIN": self.config["cors_origin"],
            "DISCOURSE_DB_HOST": self._stored.db_host,
            "DISCOURSE_DB_NAME": self._stored.db_name,
            "DISCOURSE_DB_PASSWORD": self._stored.db_password,
            "DISCOURSE_DB_USERNAME": self._stored.db_user,
            "DISCOURSE_DEVELOPER_EMAILS": self.config["developer_emails"],
            "DISCOURSE_ENABLE_CORS": str(self.config["enable_cors"]).lower(),
            "DISCOURSE_HOSTNAME": self._get_external_hostname(),
            "DISCOURSE_REDIS_HOST": redis_hostname,
            "DISCOURSE_REDIS_PORT": redis_port,
            "DISCOURSE_REFRESH_MAXMIND_DB_DURING_PRECOMPILE_DAYS": "0",
            "DISCOURSE_SERVE_STATIC_ASSETS": "true",
            "DISCOURSE_SMTP_ADDRESS": self.config["smtp_address"],
            "DISCOURSE_SMTP_AUTHENTICATION": self.config["smtp_authentication"],
            "DISCOURSE_SMTP_DOMAIN": self.config["smtp_domain"],
            "DISCOURSE_SMTP_OPENSSL_VERIFY_MODE": self.config["smtp_openssl_verify_mode"],
            "DISCOURSE_SMTP_PASSWORD": self.config["smtp_password"],
            "DISCOURSE_SMTP_PORT": str(self.config["smtp_port"]),
            "DISCOURSE_SMTP_USER_NAME": self.config["smtp_username"],
            "GEM_HOME": "/srv/discourse/.gem",
            "RAILS_ENV": "production",
        }

        saml_config = self._get_saml_config()
        for key in saml_config:
            pod_config[key] = saml_config[key]

        if self.config.get("s3_enabled"):
            pod_config.update(self._get_s3_env())

        # We only get valid throttle levels here, otherwise it would be caught
        # by `check_for_config_problems`, so we can be sure this won"t raise a
        # KeyError.
        for key in THROTTLE_LEVELS[self.config["throttle_level"]]:
            pod_config[key] = THROTTLE_LEVELS[self.config["throttle_level"]][key]

        return pod_config

    def _create_layer_config(self) -> Dict:
        """Create a layer config based on our current configuration.

        - uses create_discourse_environment_settings to generate the environment we need.
        """
        logger.info("Generating Layer config")
        layer_config = {
            "summary": "Discourse layer",
            "description": "Discourse layer",
            "services": {
                "discourse": {
                    "override": "replace",
                    "summary": "Discourse web application",
                    "command": f"sh -c '{SCRIPT_PATH}/app_launch >> {LOG_PATH} 2&>1'",
                    "startup": "enabled",
                    "environment": self._create_discourse_environment_settings(),
                }
            },
            "checks": {
                "discourse-check": {
                    "override": "replace",
                    "http": {"url": f"http://localhost:{SERVICE_PORT}"},
                },
            },
        }
        return layer_config

    def _should_run_setup(self, current_plan: Dict, s3info: Optional[S3Info]) -> bool:
        # Return true if no services are planned yet (first run)
        return not current_plan.services or (
            # Or S3 is enabled and one S3 parameter has changed
            self.config.get("s3_enabled")
            and s3info
            and (
                s3info.enabled != self.config.get("s3_enabled")
                or s3info.region != self.config.get("s3_region")
                or s3info.bucket != self.config.get("s3_bucket")
                or s3info.endpoint != self.config.get("s3_endpoint")
            )
        )

    def _are_db_relations_ready(self) -> bool:
        if not self._stored.db_name:
            self.model.unit.status = WaitingStatus("Waiting for database relation")
            return False
        if not self._stored.redis_relation:
            self.model.unit.status = WaitingStatus("Waiting for redis relation")
            return False
        return True

    def _config_changed(self, event: HookEvent) -> None:
        """Configure service.

        - Verifies config is valid

        - Configures pod using pebble and layer generated from config.
        """
        self.model.unit.status = MaintenanceStatus("Configuring service")
        if not self._are_db_relations_ready():
            event.defer()
            return

        container = self.unit.get_container(SERVICE_NAME)
        if not self._are_db_relations_ready() or not container.can_connect():
            event.defer()
            return

        # Get previous plan and extract env vars values to check is some S3 params has changed
        current_plan = container.get_plan()

        # Covers when there are no plan
        previous_s3_info = None
        if current_plan.services and current_plan.services["discourse"]:
            current_env = current_plan.services["discourse"].environment
            previous_s3_info = S3Info(
                current_env["DISCOURSE_USE_S3"] if "DISCOURSE_USE_S3" in current_env else "",
                current_env["DISCOURSE_S3_REGION"] if "DISCOURSE_S3_REGION" in current_env else "",
                current_env["DISCOURSE_S3_BUCKET"] if "DISCOURSE_S3_BUCKET" in current_env else "",
                current_env["DISCOURSE_S3_ENDPOINT"]
                if "DISCOURSE_S3_ENDPOINT" in current_env
                else "",
            )

        # First execute the setup script in 2 conditions:
        # - First run (when no services are planned in pebble)
        # - Change in important S3 parameter (comparing value with envVars in pebble plan)
        if (
            self._is_config_valid()
            and self.model.unit.is_leader()
            and self._should_run_setup(current_plan, previous_s3_info)
        ):
            self.model.unit.status = MaintenanceStatus("Compiling assets")
            script = f"{SCRIPT_PATH}/pod_setup"
            process = container.exec(
                [script],
                environment=self._create_discourse_environment_settings(),
                working_dir="/srv/discourse/app",
            )
            try:
                stdout, _ = process.wait_output()
                logger.debug("%s stdout: %s", script, stdout)
            except ExecError as e:
                logger.error("%s command exited with code %d. Stderr:", script, e.exit_code)
                for line in e.stderr.splitlines():
                    logger.error("    %s", line)
                logger.error("%s stdout: %s", script, e.stdout)
                raise

        # Then start the service
        if self._is_config_valid():
            layer_config = self._create_layer_config()
            container.add_layer(SERVICE_NAME, layer_config, combine=True)
            container.pebble.replan_services()
            self.ingress.update_config(self._make_ingress_config())
            self.model.unit.status = ActiveStatus()

    # pgsql.DatabaseRelationJoinedEvent is actually defined
    def _on_database_relation_joined(
        self, event: pgsql.DatabaseRelationJoinedEvent  # type: ignore
    ) -> None:
        """Handle db-relation-joined.

        Args:
            event: Event triggering the database relation joined handler.
        """
        if self.model.unit.is_leader():
            event.database = DATABASE_NAME
            event.extensions = ["hstore:public", "pg_trgm:public"]
        elif event.database != DATABASE_NAME:
            # Leader has not yet set requirements. Defer, in case this unit
            # becomes leader and needs to perform that operation.
            event.defer()
            return

    # pgsql.DatabaseChangedEvent is actually defined
    def _on_database_changed(self, event: pgsql.DatabaseChangedEvent) -> None:  # type: ignore
        """Handle changes in the primary database unit.

        Args:
            event: Event triggering the database master changed handler.
        """
        if event.master is None:
            self._stored.db_name = None
            self._stored.db_user = None
            self._stored.db_password = None
            self._stored.db_host = None
        else:
            self._stored.db_name = event.master.dbname
            self._stored.db_user = event.master.user
            self._stored.db_password = event.master.password
            self._stored.db_host = event.master.host

        self._config_changed(event)


if __name__ == "__main__":  # pragma: no cover
    main(DiscourseCharm, use_juju_for_storage=True)
