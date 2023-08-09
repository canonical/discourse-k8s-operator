#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Discourse on kubernetes."""
import logging
import os.path
import typing
from collections import defaultdict, namedtuple

import ops
import ops.lib
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
)
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from ops.charm import ActionEvent, CharmBase, HookEvent, RelationBrokenEvent
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import ExecError, ExecProcess, Plan

from database import DatabaseHandler

logger = logging.getLogger(__name__)
pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

S3Info = namedtuple("S3Info", ["enabled", "region", "bucket", "endpoint"])

DATABASE_NAME = "discourse"
DISCOURSE_PATH = "/srv/discourse/app"
THROTTLE_LEVELS: typing.Dict = defaultdict(dict)
THROTTLE_LEVELS["none"] = {
    "DISCOURSE_MAX_REQS_PER_IP_MODE": "none",
    "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
}
THROTTLE_LEVELS["permissive"] = {
    "DISCOURSE_MAX_REQS_PER_IP_MODE": "warn+block",
    "DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE": "1000",
    "DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS": "100",
    "DISCOURSE_MAX_USER_API_REQS_PER_MINUTE": "400",
    "DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS": "400",
    "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
}
THROTTLE_LEVELS["strict"] = {
    "DISCOURSE_MAX_REQS_PER_IP_MODE": "block",
    "DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE": "200",
    "DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS": "50",
    "DISCOURSE_MAX_USER_API_REQS_PER_MINUTE": "100",
    "DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS": "200",
    "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
}
LOG_PATHS = [
    f"{DISCOURSE_PATH}/log/production.log",
    f"{DISCOURSE_PATH}/log/unicorn.stderr.log",
    f"{DISCOURSE_PATH}/log/unicorn.stdout.log",
]
PROMETHEUS_PORT = 9394
REQUIRED_S3_SETTINGS = ["s3_access_key_id", "s3_bucket", "s3_region", "s3_secret_access_key"]
SCRIPT_PATH = "/srv/scripts"
SERVICE_NAME = "discourse"
SERVICE_PORT = 3000
SETUP_COMPLETED_FLAG_FILE = "/run/discourse-k8s-operator/setup_completed"
DATABASE_RELATION_NAME = "database"


class DiscourseCharm(CharmBase):
    """Charm for Discourse on kubernetes."""

    on = RedisRelationCharmEvents()
    _stored = StoredState()

    def __init__(self, *args):
        """Initialize defaults and event handlers."""
        super().__init__(*args)

        self._database = DatabaseHandler(self, DATABASE_RELATION_NAME)

        self.framework.observe(
            self._database.database.on.database_created, self._on_database_created
        )
        self.framework.observe(
            self._database.database.on.endpoints_changed, self._on_database_endpoints_changed
        )
        self.framework.observe(
            self.on[DATABASE_RELATION_NAME].relation_broken,
            self._on_database_relation_broken,
        )

        self._stored.set_default(
            redis_relation={},
        )
        self._require_nginx_route()
        self.framework.observe(self.on.install, self._set_up_discourse)
        self.framework.observe(self.on.upgrade_charm, self._set_up_discourse)
        self.framework.observe(self.on.discourse_pebble_ready, self._config_changed)
        self.framework.observe(self.on.config_changed, self._config_changed)

        self.framework.observe(self.on.add_admin_user_action, self._on_add_admin_user_action)
        self.framework.observe(self.on.anonymize_user_action, self._on_anonymize_user_action)

        self.redis = RedisRequires(self, self._stored)
        self.framework.observe(self.on.redis_relation_updated, self._redis_relation_changed)

        self._metrics_endpoint = MetricsEndpointProvider(
            self, jobs=[{"static_configs": [{"targets": [f"*:{PROMETHEUS_PORT}"]}]}]
        )
        self._logging = LogProxyConsumer(
            self, relation_name="logging", log_files=LOG_PATHS, container_name="discourse"
        )
        self._grafana_dashboards = GrafanaDashboardProvider(self)

    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        if self._are_db_relations_ready():
            self._reload_configuration()

    def _on_database_endpoints_changed(self, _: DatabaseEndpointsChangedEvent) -> None:
        """Handle endpoints change.

        Args:
            event: Event triggering the endpoints changed handler.
        """
        if self._are_db_relations_ready():
            self._reload_configuration()

    def _on_database_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Handle broken relation.

        Args:
            event: Event triggering the broken relation handler.
        """
        self._reload_configuration()

    def _require_nginx_route(self) -> None:
        """Create minimal ingress configuration."""
        require_nginx_route(
            charm=self,
            service_hostname=self._get_external_hostname(),
            service_name=self.app.name,
            service_port=SERVICE_PORT,
            session_cookie_max_age=3600,
        )

    def _get_external_hostname(self) -> str:
        """Extract and return hostname from site_url or default to [application name].

        Returns:
            The site hostname defined as part of the site_url configuration or a default value.
        """
        return (
            self.config["external_hostname"] if self.config["external_hostname"] else self.app.name
        )

    def _is_setup_completed(self) -> bool:
        """Check if the _set_up_discourse process has finished.

        Returns:
            True if the _set_up_discourse process has finished.
        """
        container = self.unit.get_container(SERVICE_NAME)
        return container.can_connect() and container.exists(SETUP_COMPLETED_FLAG_FILE)

    def _set_setup_completed(self) -> None:
        """Mark the _set_up_discourse process as completed."""
        container = self.unit.get_container(SERVICE_NAME)
        container.push(SETUP_COMPLETED_FLAG_FILE, "", make_dirs=True)

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

        if self.config["saml_target_url"] and not self.config["force_https"]:
            errors.append("'saml_target_url' cannot be specified without 'force_https' being true")

        if self.config.get("s3_enabled"):
            errors.extend(
                f"'s3_enabled' requires '{s3_config}'"
                for s3_config in REQUIRED_S3_SETTINGS
                if not self.config[s3_config]
            )

        if errors:
            self.model.unit.status = BlockedStatus(", ".join(errors))
        return not errors

    def _get_saml_config(self) -> typing.Dict[str, typing.Any]:
        """Get SAML configuration.

        Returns:
            Dictionary with the SAML configuration settings..
        """
        ubuntu_one_fingerprint = "32:15:20:9F:A4:3C:8E:3E:8E:47:72:62:9A:86:8D:0E:E6:CF:45:D5"
        ubuntu_one_staging_fingerprint = (
            "D2:B4:86:49:1B:AC:29:F6:A4:C8:CF:0D:3A:8F:AD:86:36:0A:77:C0"
        )
        saml_fingerprints = {
            "https://login.ubuntu.com/+saml": ubuntu_one_fingerprint,
            "https://login.staging.ubuntu.com/+saml": ubuntu_one_staging_fingerprint,
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

    def _get_missing_config_fields(self) -> typing.List[str]:
        """Check for missing fields in juju config.

        Returns:
            List of required fields that are either not present or empty.
        """
        needed_fields = ["cors_origin"]
        return [field for field in needed_fields if not self.config.get(field)]

    def _get_s3_env(self) -> typing.Dict[str, typing.Any]:
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

    def _get_redis_relation_data(self) -> typing.Tuple[str, int]:
        """Get the hostname and port from the redis relation data.

        Returns:
            Tuple with the hostname and port of the related redis
        """
        # This is the current recommended way of accessing the relation data.
        for redis_unit in self._stored.redis_relation:  # type: ignore
            # mypy fails to see that this is indexable
            redis_unit_data = self._stored.redis_relation[redis_unit]  # type: ignore
            redis_hostname = str(redis_unit_data.get("hostname", "") or "")
            redis_port = int(redis_unit_data.get("port", 0) or 0)
            logger.debug(
                "Got redis connection details from relation of %s:%s", redis_hostname, redis_port
            )
        return (redis_hostname, redis_port)

    def _create_discourse_environment_settings(self) -> typing.Dict[str, str]:
        """Create a layer config based on our current configuration.

        Returns:
            Dictionary with all the environment settings.
        """
        database_relation_data = self._database.get_relation_data()
        redis_relation_data = self._get_redis_relation_data()

        pod_config = {
            # Since pebble exec command doesn't copy the container env (envVars set in Dockerfile),
            # I need to take the required envVars for the application to work properly
            "CONTAINER_APP_NAME": "discourse",
            "CONTAINER_APP_ROOT": "/srv/discourse",
            "CONTAINER_APP_USERNAME": "discourse",
            "DISCOURSE_CORS_ORIGIN": self.config["cors_origin"],
            "DISCOURSE_DB_HOST": database_relation_data["POSTGRES_HOST"],
            "DISCOURSE_DB_NAME": database_relation_data["POSTGRES_DB"],
            "DISCOURSE_DB_PASSWORD": database_relation_data["POSTGRES_PASSWORD"],
            "DISCOURSE_DB_USERNAME": database_relation_data["POSTGRES_USER"],
            "DISCOURSE_DEVELOPER_EMAILS": self.config["developer_emails"],
            "DISCOURSE_ENABLE_CORS": str(self.config["enable_cors"]).lower(),
            "DISCOURSE_HOSTNAME": self._get_external_hostname(),
            "DISCOURSE_REDIS_HOST": redis_relation_data[0],
            "DISCOURSE_REDIS_PORT": str(redis_relation_data[1]),
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
        # self.config return an Any type
        pod_config.update(THROTTLE_LEVELS.get(self.config["throttle_level"]))  # type: ignore

        return pod_config

    def _create_layer_config(self) -> ops.pebble.LayerDict:
        """Create a layer config based on our current configuration.

        Returns:
            Dictionary with the pebble configuration.
        """
        logger.info("Generating Layer config")
        layer_config = {
            "summary": "Discourse layer",
            "description": "Discourse layer",
            "services": {
                SERVICE_NAME: {
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
        return typing.cast(ops.pebble.LayerDict, layer_config)

    def _should_run_s3_migration(
        self, current_plan: Plan, s3info: typing.Optional[S3Info]
    ) -> bool:
        """Determine if the S3 migration is to be run.

        Args:
            current_plan: Dictionary containing the current plan.
            s3info: S3Info object containing the S3 configuration options.

        Returns:
            If no services are planned yet (first run) or S3 settings have changed.
        """
        result = self.config.get("s3_enabled") and (
            not current_plan.services
            or (
                s3info
                and (
                    s3info.enabled != self.config.get("s3_enabled")
                    or s3info.region != self.config.get("s3_region")
                    or s3info.bucket != self.config.get("s3_bucket")
                    or s3info.endpoint != self.config.get("s3_endpoint")
                )
            )
        )
        return bool(result)

    def _are_db_relations_ready(self) -> bool:
        """Check if the needed database relations are established.

        Returns:
            If the needed relations have been established.
        """
        if not self._database.is_relation_ready():
            self.model.unit.status = WaitingStatus("Waiting for database relation")
            return False
        # mypy fails do detect this stored value can be False
        if not self._stored.redis_relation:  # type: ignore
            self.model.unit.status = WaitingStatus("Waiting for redis relation")
            return False
        if not all(self._get_redis_relation_data()):
            self.model.unit.status = WaitingStatus("Waiting for redis relation to initialize")
            return False
        return True

    def _set_up_discourse(self, event: HookEvent) -> None:
        """Run Discourse migrations and recompile assets.

        Args:
            event: Event triggering the handler.
        """
        container = self.unit.get_container(SERVICE_NAME)
        if not self._are_db_relations_ready() or not container.can_connect():
            event.defer()
            return
        env_settings = self._create_discourse_environment_settings()
        try:
            if self.model.unit.is_leader():
                self.model.unit.status = MaintenanceStatus("Executing migrations")
                migration_process: ExecProcess = container.exec(
                    [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "--trace", "db:migrate"],
                    environment=env_settings,
                    working_dir=DISCOURSE_PATH,
                    user="discourse",
                )
                migration_process.wait_output()
            self.model.unit.status = MaintenanceStatus("Compiling assets")
            precompile_process: ExecProcess = container.exec(
                [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "assets:precompile"],
                environment=env_settings,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )
            precompile_process.wait_output()
            self._set_setup_completed()
            get_version_process = container.exec(
                [f"{DISCOURSE_PATH}/bin/rails", "runner", "puts Discourse::VERSION::STRING"],
                environment=env_settings,
                working_dir=DISCOURSE_PATH,
                user="discourse",
            )
            version, _ = get_version_process.wait_output()
            self.unit.set_workload_version(version)
        except ExecError as cmd_err:
            logger.exception("Setting up discourse failed with code %d.", cmd_err.exit_code)
            raise

    def _config_changed(self, event: HookEvent) -> None:
        """Configure pod using pebble and layer generated from config.

        Args:
            event: Event triggering the handler.
        """
        container = self.unit.get_container(SERVICE_NAME)
        if not self._are_db_relations_ready() or not container.can_connect():
            event.defer()
            return
        if not self._is_config_valid():
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
        env_settings = self._create_discourse_environment_settings()
        try:
            if self.model.unit.is_leader() and self._should_run_s3_migration(
                current_plan, previous_s3_info
            ):
                self.model.unit.status = MaintenanceStatus("Running S3 migration")
                process = container.exec(
                    [f"{DISCOURSE_PATH}/bin/bundle", "exec", "rake", "s3:upload_assets"],
                    environment=env_settings,
                    working_dir=DISCOURSE_PATH,
                    user="discourse",
                )
                process.wait_output()
        except ExecError as cmd_err:
            logger.exception("S3 migration failed with code %d.", cmd_err.exit_code)
            raise

        self._reload_configuration()
        if container.can_connect():
            self._config_force_https()
            self.model.unit.status = ActiveStatus()

    def _reload_configuration(self) -> None:
        # mypy has some trouble with dynamic attributes
        if not self._is_setup_completed():
            logger.info("Defer starting the discourse server until discourse setup completed")
            return
        container = self.unit.get_container(SERVICE_NAME)
        if self._is_config_valid() and container.can_connect():
            layer_config = self._create_layer_config()
            container.add_layer(SERVICE_NAME, layer_config, combine=True)
            container.pebble.replan_services()

    def _redis_relation_changed(self, _: HookEvent) -> None:
        if self._are_db_relations_ready():
            self._reload_configuration()

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
                    os.path.join(DISCOURSE_PATH, "bin/bundle"),
                    "exec",
                    "rake",
                    "admin:create",
                ],
                stdin=f"{email}\n{password}\n{password}\nY\n",
                user="discourse",
                working_dir=DISCOURSE_PATH,
                environment=self._create_discourse_environment_settings(),
                timeout=60,
            )
            try:
                process.wait_output()
                event.set_results({"user": f"{email}"})
            except ExecError as ex:
                event.fail(
                    # Parameter validation errors are printed to stdout
                    f"Failed to create user with email {email}: {ex.stdout}"  # type: ignore
                )
        else:
            event.fail("Container is not ready")

    def _config_force_https(self) -> None:
        """Config Discourse to force_https option based on charm configuration."""
        container = self.unit.get_container("discourse")
        force_bool = str(self.config["force_https"]).lower()
        process = container.exec(
            [
                os.path.join(DISCOURSE_PATH, "bin/rails"),
                "runner",
                f"SiteSetting.force_https={force_bool}",
            ],
            user="discourse",
            working_dir=DISCOURSE_PATH,
            environment=self._create_discourse_environment_settings(),
        )
        process.wait_output()

    def _on_anonymize_user_action(self, event: ActionEvent) -> None:
        """Anonymize data from a user.

        Args:
            event: Event triggering the anonymize_user action.
        """
        username = event.params["username"]
        container = self.unit.get_container("discourse")
        if container.can_connect():
            process = container.exec(
                [
                    "bash",
                    "-c",
                    f"./bin/bundle exec rake users:anonymize[{username}]",
                ],
                user="discourse",
                working_dir=DISCOURSE_PATH,
                environment=self._create_discourse_environment_settings(),
            )
            try:
                process.wait_output()
                event.set_results({"user": f"{username}"})
            except ExecError as ex:
                event.fail(
                    # Parameter validation errors are printed to stdout
                    # Ignore mypy warning when formatting stdout
                    f"Failed to anonymize user with username {username}:{ex.stdout}"  # type: ignore
                )


if __name__ == "__main__":  # pragma: no cover
    main(DiscourseCharm, use_juju_for_storage=True)
