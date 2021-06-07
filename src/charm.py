#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import ops.lib
from charms.redis_k8s.v0.redis import (
    RedisRelationCharmEvents,
    RedisRequires,
)
from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.pebble import ConnectionError
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from charms.nginx_ingress_integrator.v0.ingress import IngressRequires


logger = logging.getLogger(__name__)


pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

THROTTLE_LEVELS = {
    "none": {'DISCOURSE_MAX_REQS_PER_IP_MODE': 'none', 'DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE': 'false'},
    "permissive": {
        'DISCOURSE_MAX_REQS_PER_IP_MODE': 'warn+block',
        'DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE': 1000,
        'DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS': 100,
        'DISCOURSE_MAX_USER_API_REQS_PER_MINUTE': 400,
        'DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS': 400,
        'DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE': 'false',
    },
    "strict": {
        'DISCOURSE_MAX_REQS_PER_IP_MODE': 'block',
        'DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE': 200,
        'DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS': 50,
        'DISCOURSE_MAX_USER_API_REQS_PER_MINUTE': 100,
        'DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS': 200,
        'DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE': 'false',
    },
}


def create_discourse_environment_settings(config):
    """Create the pod environment config from the juju config."""

    pod_config = {
        'DISCOURSE_DB_USERNAME': config['db_user'],
        'DISCOURSE_DB_PASSWORD': config['db_password'],
        'DISCOURSE_DB_HOST': config['db_host'],
        'DISCOURSE_DB_NAME': config['db_name'],
        'DISCOURSE_DEVELOPER_EMAILS': config['developer_emails'],
        'DISCOURSE_SERVE_STATIC_ASSETS': "true",
        'DISCOURSE_HOSTNAME': config['external_hostname'],
        'DISCOURSE_SMTP_DOMAIN': config['smtp_domain'],
        'DISCOURSE_SMTP_ADDRESS': config['smtp_address'],
        'DISCOURSE_SMTP_PORT': config['smtp_port'],
        'DISCOURSE_SMTP_AUTHENTICATION': config['smtp_authentication'],
        'DISCOURSE_SMTP_OPENSSL_VERIFY_MODE': config['smtp_openssl_verify_mode'],
        'DISCOURSE_SMTP_USER_NAME': config['smtp_username'],
        'DISCOURSE_SMTP_PASSWORD': config['smtp_password'],
        'DISCOURSE_REDIS_HOST': config['redis_host'],
        'DISCOURSE_REDIS_PORT': config['redis_port'],
        'DISCOURSE_ENABLE_CORS': config['enable_cors'],
        'DISCOURSE_CORS_ORIGIN': config['cors_origin'],
        'DISCOURSE_REFRESH_MAXMIND_DB_DURING_PRECOMPILE_DAYS': "0",
    }

    saml_config = get_saml_config(config)
    for key in saml_config:
        pod_config[key] = saml_config[key]

    # We only get valid throttle levels here, otherwise it would be caught
    # by `check_for_config_problems`, so we can be sure this won't raise a
    # KeyError.
    for key in THROTTLE_LEVELS[config['throttle_level']]:
        pod_config[key] = THROTTLE_LEVELS[config['throttle_level']][key]

    return pod_config


def get_saml_config(config):
    saml_fingerprints = {
        'https://login.ubuntu.com/+saml': '32:15:20:9F:A4:3C:8E:3E:8E:47:72:62:9A:86:8D:0E:E6:CF:45:D5'
    }
    saml_config = {}

    if config.get('saml_target_url'):
        saml_config['DISCOURSE_SAML_TARGET_URL'] = config['saml_target_url']
        saml_config['DISCOURSE_SAML_FULL_SCREEN_LOGIN'] = "true" if config['force_saml_login'] else "false"
        fingerprint = saml_fingerprints.get(config['saml_target_url'])
        if fingerprint:
            saml_config['DISCOURSE_SAML_CERT_FINGERPRINT'] = fingerprint

    return saml_config


def create_layer_config(config):
    """Create a layer config based on our current configuration.

    - uses create_discourse_environment_settings to genreate the environment we need.
    """
    logger.info("Generating Layer config")
    layer_config = {
        "summary": "Discourse layer",
        "description": "Discourse layer",
        "services": {
            "discourse": {
                "override": "replace",
                "summary": "Discourse web application",
                "command": "sh -c '/srv/scripts/pod_start >>/srv/discourse/discourse.log 2&>1'",
                "startup": "enabled",
                "environment": create_discourse_environment_settings(config),
            }
        },
    }
    return layer_config


def check_for_config_problems(config, stored):
    """Check if there are issues with the juju config.

    - Primarily looks for missing config options using check_for_missing_config_fields()

    - Returns a list of errors if any were found.
    """
    errors = []
    missing_fields = check_for_missing_config_fields(config, stored)

    if missing_fields:
        errors.append('Required configuration missing: {}'.format(" ".join(missing_fields)))

    if not THROTTLE_LEVELS.get(config['throttle_level']):
        errors.append('throttle_level must be one of: ' + ' '.join(THROTTLE_LEVELS.keys()))

    if config['force_saml_login'] and config['saml_target_url'] == '':
        errors.append('force_saml_login can not be true without a saml_target_url')

    return errors


def check_for_missing_config_fields(config, stored):
    """Check for missing fields in juju config.

    - Returns a list of required fields that are either not present
      or are empty.
    """
    missing_fields = []

    needed_fields = [
        'db_name',
        'smtp_address',
        'cors_origin',
        'developer_emails',
        'smtp_domain',
        'external_hostname',
    ]
    # See if Redis connection information has been provided via a relation.
    redis_hostname = None
    for redis_unit in stored.redis_relation:
        redis_hostname = stored.redis_relation[redis_unit]["hostname"]
    if not redis_hostname:
        needed_fields.append("redis_host")
    for key in needed_fields:
        if not config.get(key):
            missing_fields.append(key)

    return sorted(missing_fields)


class DiscourseCharm(CharmBase):
    on = RedisRelationCharmEvents()
    stored = StoredState()

    def __init__(self, *args):
        """Initialization.

        - Primarily sets up defaults and event handlers.

        """
        super().__init__(*args)

        self.stored.set_default(
            db_name=None,
            db_user=None,
            db_password=None,
            db_host=None,
            has_db_relation=False,
            has_db_credentials=False,
            redis_relation={},
        )
        self.service_name = "discourse"
        self.ingress = IngressRequires(self, self._ingress_config())
        self.framework.observe(self.on.leader_elected, self.config_changed)
        self.framework.observe(self.on.config_changed, self.config_changed)
        self.framework.observe(self.on.upgrade_charm, self.config_changed)

        self.db = pgsql.PostgreSQLClient(self, 'db')
        self.framework.observe(self.db.on.database_relation_joined, self.on_database_relation_joined)
        self.framework.observe(self.db.on.master_changed, self.on_database_changed)

        self.redis = RedisRequires(self, self.stored)
        self.framework.observe(self.on.redis_relation_updated, self.config_changed)

    def _ingress_config(self):
        """Return a dict of our ingress config."""
        ingress_config = {
            "service-hostname": self.config['external_hostname'],
            "service-name": self.app.name,
            "service-port": 3000,
            "session-cookie-max-age": 3600,
        }
        if self.config["tls_secret_name"]:
            ingress_config["tls-secret-name"] = self.config["tls_secret_name"]
        if self.config["max_body_size"]:
            ingress_config["max-body-size"] = self.config["max_body_size"]
        return ingress_config

    def check_config_is_valid(self, config):
        """Check that the provided config is valid.

        - Returns True if config is valid, False otherwise.

        - Sets model status as appropriate.
        """
        valid_config = True
        errors = check_for_config_problems(config, self.stored)

        # Set status if we have a bad config.
        if errors:
            self.model.unit.status = BlockedStatus(", ".join(errors))
            valid_config = False
        else:
            self.model.unit.status = MaintenanceStatus("Configuration passed validation")

        return valid_config

    def check_db_is_valid(self, state):
        if not state.has_db_relation:
            self.model.unit.status = BlockedStatus("db relation is required")
            return False
        if not state.has_db_credentials:
            self.model.unit.status = WaitingStatus("db relation is setting up")
            return False
        self.model.unit.status = MaintenanceStatus("db relation is ready")
        return True

    def config_changed(self, event=None):
        """Configure service.

        - Verifies config is valid

        - Configures pod using pebble and layer generated from config.
        """

        # Set our status while we get configured.
        self.model.unit.status = MaintenanceStatus('Configuring service')

        # Get redis connection information from config but allow overriding
        # via a relation.
        redis_hostname = self.config["redis_host"]
        redis_port = 6379
        for redis_unit in self.stored.redis_relation:
            redis_hostname = self.stored.redis_relation[redis_unit]["hostname"]
            redis_port = self.stored.redis_relation[redis_unit]["port"]
            logger.debug("Got redis connection details from relation of %s:%s", redis_hostname, redis_port)

        if not self.check_db_is_valid(self.stored):
            self.model.unit.status = MaintenanceStatus('Invalid database configuration')
            return

        # Merge our config and state into a single dict and set
        # defaults here, because the helpers avoid dealing with
        # the framework.
        config = dict(self.model.config)
        config["db_name"] = self.stored.db_name
        config["db_user"] = self.stored.db_user
        config["db_password"] = self.stored.db_password
        config["db_host"] = self.stored.db_host
        config["redis_host"] = redis_hostname
        config["redis_port"] = redis_port

        # Get our layer config.

        try:
            if self.check_config_is_valid(config):
                layer_config = create_layer_config(config)
                live_config = self.container().get_plan().to_dict().get("services", {})
                logger.debug("___LIVE CONFIG___")
                logger.debug(live_config)
                logger.debug("___LAYER CONFIG___")
                logger.debug(layer_config["services"])
                if live_config != layer_config["services"]:
                    logger.debug("Updating config")
                    self.container().add_layer(self.service_name, layer_config, combine=True)
                    self.restart_service()
                    self.ingress.update_config(self._ingress_config())

                self.model.unit.status = ActiveStatus()
        except ConnectionError:
            logger.info("Unable to connect to Pebble, deferring event")
            event.defer()
            return

    def on_database_relation_joined(self, event):
        """Event handler for a newly joined database relation.

        - Sets the event.database field on the database joined event.

        - Required because setting the database name is only possible
          from inside the event handler per https://github.com/canonical/ops-lib-pgsql/issues/2
        """
        self.stored.has_db_relation = True
        # Ensure event.database is always set to a non-empty string. PostgreSQL
        # can infer this if it's in the same model as Discourse, but not if
        # we're using cross-model relations.
        db_name = self.model.config["db_name"] or self.framework.model.app.name
        # Per https://github.com/canonical/ops-lib-pgsql/issues/2,
        # changing the setting in the config will not take effect,
        # unless the relation is dropped and recreated.
        if self.model.unit.is_leader():
            event.database = db_name
        elif event.database != db_name:
            # Leader has not yet set requirements. Defer, in case this unit
            # becomes leader and needs to perform that operation.
            event.defer()
            return

    def on_database_changed(self, event):
        """Event handler for database relation change.

        - Sets our database parameters based on what was provided
          in the relation event.
        """
        if event.master is None:
            self.stored.db_name = None
            self.stored.db_user = None
            self.stored.db_password = None
            self.stored.db_host = None
            self.stored.has_db_credentials = False
            self.model.unit.status = WaitingStatus("waiting for db relation")
            return

        self.stored.db_name = event.master.dbname
        self.stored.db_user = event.master.user
        self.stored.db_password = event.master.password
        self.stored.db_host = event.master.host
        self.stored.has_db_credentials = True

        self.config_changed(event)

    def container(self):
        return self.unit.get_container(self.service_name)

    def stop_service(self):
        self.container().stop(self.service_name)

    def restart_service(self):
        if self.container().get_service(self.service_name).is_running():
            logger.debug("Stopping service")
            self.stop_service()
        logger.debug("Starting service")
        self.container().start(self.service_name)


if __name__ == '__main__':  # pragma: no cover
    main(
        DiscourseCharm,
        use_juju_for_storage=True,  # https://github.com/canonical/operator/issues/506
    )
