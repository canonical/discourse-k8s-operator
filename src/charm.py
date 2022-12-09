#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Discourse on kubernetes."""
import logging
from collections import namedtuple
from typing import Any, Dict, List, Optional

import ops.lib
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.nginx_ingress_integrator.v0.ingress import IngressRequires
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from ops.charm import ActionEvent, CharmBase, HookEvent
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import ExecError

logger = logging.getLogger(__name__)
pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

S3Info = namedtuple("S3Info", ["enabled", "region", "bucket", "endpoint"])

DATABASE_NAME = "discourse"
DISCOURSE_PATH = "/srv/discourse/app"
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
LOG_PATHS = [
    "/srv/discourse/app/log/production.log",
    "/srv/discourse/app/log/unicorn.stderr.log",
    "/srv/discourse/app/log/unicorn.stdout.log",
]
PROMETHEUS_PORT = 9394
REQUIRED_S3_SETTINGS = ["s3_access_key_id", "s3_bucket", "s3_region", "s3_secret_access_key"]
SCRIPT_PATH = "/srv/scripts"
SERVICE_NAME = "discourse"
SERVICE_PORT = 3000


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
        self.framework.observe(self.on.add_admin_user_action, self._on_add_admin_user_action)

        self.redis = RedisRequires(self, self._stored)
        self.framework.observe(self.on.redis_relation_updated, self._config_changed)

        self._metrics_endpoint = MetricsEndpointProvider(
            self, jobs=[{"static_configs": [{"targets": [f"*:{PROMETHEUS_PORT}"]}]}]
        )
        self._logging = LogProxyConsumer(
            self, relation_name="logging", log_files=LOG_PATHS, container_name="discourse"
        )
        self._grafana_dashboards = GrafanaDashboardProvider(self)

    def _make_ingress_config(self) -> Dict[str, Any]:
        """Create minimal ingress configuration.

        Returns:
            Minimal ingress configuration with hostname, service name and service port.
        """
        ingress_config = {
            "service-hostname": self._get_external_hostname(),
            "service-name": self.app.name,
            "service-port": SERVICE_PORT,
            "session-cookie-max-age": 3600,
        }
        return ingress_config

    def _get_external_hostname(self) -> str:
        """Extract and return hostname from site_url or default to [application name].

        Returns:
            The site hostname defined as part of the site_url configuration or a default value.
        """
        return (
            self.config["external_hostname"] if self.config["external_hostname"] else self.app.name
        )

    def _is_config_valid(self) -> bool:
        """Check that the provided config is valid.

        Returns:
            If config is valid.
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
            errors.extend(
                f"'s3_enabled' requires '{s3_config}'"
                for s3_config in REQUIRED_S3_SETTINGS
                if not self.config[s3_config]
            )

        if errors:
            self.model.unit.status = BlockedStatus(", ".join(errors))
        return not errors

    def _get_saml_config(self) -> Dict[str, Any]:
        """Get SAML configuration.

        Returns:
            Dictionary with the SAML configuration settings..
        """
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

        Returns:
            List of required fields that are either not present or empty.
        """
        needed_fields = ["cors_origin"]
        return [field for field in needed_fields if not self.config.get(field)]

    def _get_s3_env(self) -> Dict[str, Any]:
        """Get the list of S3-related environment variables from charm's configuration.

        Returns:
            Dictionary with all the S3 environment settings.
        """
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

    def _create_discourse_environment_settings(self) -> Dict[str, Any]:
        """Create a layer config based on our current configuration.

        Returns:
            Dictionary with all the environment settings.
        """
        # Get redis connection information from the relation.
        redis_hostname = None
        redis_port = 6379
        # This is the current recommended way of accessing the relation data.
        for redis_unit in self._stored.redis_relation:  # type: ignore
            redis_hostname = self._stored.redis_relation[redis_unit].get("hostname")  # type: ignore
            redis_port = self._stored.redis_relation[redis_unit].get("port")  # type: ignore
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
        pod_config.update(self._get_saml_config())

        if self.config.get("s3_enabled"):
            pod_config.update(self._get_s3_env())

        # We only get valid throttle levels here, otherwise it would be caught
        # by `check_for_config_problems`.
        if THROTTLE_LEVELS.get(self.config["throttle_level"]):
            # self.config return an Any type
            pod_config.update(THROTTLE_LEVELS.get(self.config["throttle_level"]))  # type: ignore

        return pod_config

    def _create_layer_config(self) -> Dict[str, Any]:
        """Create a layer config based on our current configuration.

        Returns:
            Dictionary with the pebble configuration.
        """
        logger.info("Generating Layer config")
        layer_config = {
            "summary": "Discourse layer",
            "description": "Discourse layer",
            "services": {
                "discourse": {
                    "override": "replace",
                    "summary": "Discourse web application",
                    "command": f"sh -c '{SCRIPT_PATH}/app_launch.sh'",
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
        """Determine if the setup script is to be run based on the current plan and the new S3 settings.

        Args:
            current_plan: Dictionary containing the current plan.
            s3info: S3Info object containing the S3 configuration options.

        Returns:
            If no services are planned yet (first run) or S3 settings have changed.
        """
        # Properly type checks would require defining a complex TypedMap for the pebble plan
        return not current_plan.services or (  # type: ignore
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
        """Check if the needed database relations are established.

        Returns:
            If the needed relations have been established.
        """
        # mypy fails do detect this stored value can be False
        if not self._stored.db_name:  # type: ignore
            self.model.unit.status = WaitingStatus("Waiting for database relation")
            return False
        # mypy fails do detect this stored value can be False
        if not self._stored.redis_relation:  # type: ignore
            self.model.unit.status = WaitingStatus("Waiting for redis relation")
            return False
        return True

    def _config_changed(self, event: HookEvent) -> None:
        """Configure pod using pebble and layer generated from config.

        Args:
            event: Event triggering the handler.
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
            script = f"{SCRIPT_PATH}/pod_setup.sh"
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
                logger.error("%s stderr: %s", script, e.stderr)
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

    def _on_add_admin_user_action(self, event: ActionEvent) -> None:
        """Add a new admin user to Discourse.

        Args:
            event: Event triggering the add_admin_user action.
        """
        email = event.params["email"]
        password = event.params["password"]
        container = self.unit.get_container("discourse")
        if container.can_connect():
            process = container.exec(
                [
                    "bash",
                    "-c",
                    f"./bin/bundle exec rake admin:create <<< $'{email}\n{password}\n{password}\nY'",
                ],
                user="discourse",
                working_dir=DISCOURSE_PATH,
                environment=self._create_discourse_environment_settings(),
            )
            try:
                process.wait_output()
            except ExecError as ex:
                event.fail(
                    f"Failed to create user with email {email}: {ex.stderr.decode('utf-8')}"  # type: ignore
                )
            event.set_results({"user": f"{email}"})


if __name__ == "__main__":  # pragma: no cover
    main(DiscourseCharm, use_juju_for_storage=True)
