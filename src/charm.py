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

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus


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


def create_discourse_pod_config(config):
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

        saml_sync_groups = [x.strip() for x in config['saml_sync_groups'].split(',') if x.strip()]
        if saml_sync_groups:
            # Per https://github.com/discourse/discourse-saml setting this to `true`
            # "should the assigned groups be completely synced including adding AND
            # removing groups based on the IDP".
            saml_config['DISCOURSE_SAML_GROUPS_FULLSYNC'] = "false"
            saml_config['DISCOURSE_SAML_SYNC_GROUPS'] = "true"
            saml_config['DISCOURSE_SAML_SYNC_GROUPS_LIST'] = "|".join(saml_sync_groups)

    return saml_config


def create_ingress_config(app_name, config):
    """Create the ingress config form the juju config."""
    annotations = {}
    ingressResource = {
        "name": app_name + "-ingress",
        "spec": {
            "rules": [
                {
                    "host": config['external_hostname'],
                    "http": {"paths": [{"path": "/", "backend": {"serviceName": app_name, "servicePort": 3000}}]},
                }
            ]
        },
    }
    tls_secret_name = config.get('tls_secret_name')
    if tls_secret_name:
        ingressResource['spec']['tls'] = [{'hosts': [config['external_hostname']], 'secretName': tls_secret_name}]
    else:
        annotations['nginx.ingress.kubernetes.io/ssl-redirect'] = 'false'

    annotations['nginx.ingress.kubernetes.io/proxy-body-size'] = "{}m".format(config.get('max_body_size'))

    # Set affinity because discourse breaks uploads into multiple
    # requests and we need all of them to go to the same worker pod.
    annotations['nginx.ingress.kubernetes.io/affinity'] = 'cookie'
    annotations['nginx.ingress.kubernetes.io/affinity-mode'] = 'balanced'
    annotations['nginx.ingress.kubernetes.io/session-cookie-change-on-failure'] = 'true'
    annotations['nginx.ingress.kubernetes.io/session-cookie-max-age'] = '3600'
    annotations['nginx.ingress.kubernetes.io/session-cookie-name'] = 'DISCOURSE_AFFINITY'
    annotations['nginx.ingress.kubernetes.io/session-cookie-samesite'] = 'Lax'

    ingressResource['annotations'] = annotations

    return ingressResource


def get_pod_spec(app_name, config):
    """Get the entire pod spec using the juju config.

    - uses create_discourse_pod_config() to generate pod envConfig.

    - uses create_ingress_config() to generate pod ingressResources.

    """
    pod_spec = {
        "version": 3,
        "containers": [
            {
                "name": app_name,
                "imageDetails": {"imagePath": config['discourse_image']},
                "imagePullPolicy": "IfNotPresent",
                "ports": [{"containerPort": 3000, "protocol": "TCP"}],
                "envConfig": create_discourse_pod_config(config),
                "kubernetes": {
                    "readinessProbe": {
                        "httpGet": {
                            "path": "/srv/status",
                            "port": 3000,
                        }
                    }
                },
            }
        ],
        "kubernetesResources": {"ingressResources": [create_ingress_config(app_name, config)]},
    }
    # This handles when we are trying to get an image from a private
    # registry.
    if config['image_user'] and config['image_pass']:
        pod_spec['containers'][0]['imageDetails']['username'] = config['image_user']
        pod_spec['containers'][0]['imageDetails']['password'] = config['image_pass']

    return pod_spec


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

    if config['force_saml_login'] and not config['saml_target_url']:
        errors.append("'force_saml_login' cannot be true without a 'saml_target_url'")

    if config['saml_sync_groups'] and not config['saml_target_url']:
        errors.append("'saml_sync_groups' cannot be specified without a 'saml_target_url'")

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
        'discourse_image',
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
        self.framework.observe(self.on.leader_elected, self.configure_pod)
        self.framework.observe(self.on.config_changed, self.configure_pod)
        self.framework.observe(self.on.upgrade_charm, self.configure_pod)

        self.db = pgsql.PostgreSQLClient(self, 'db')
        self.framework.observe(self.db.on.database_relation_joined, self.on_database_relation_joined)
        self.framework.observe(self.db.on.master_changed, self.on_database_changed)

        self.redis = RedisRequires(self, self.stored)
        self.framework.observe(self.on.redis_relation_updated, self.configure_pod)

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

    def configure_pod(self, event=None):
        """Configure pod.

        - Verifies config is valid and unit is leader.

        - Configures pod using pod_spec generated from config.
        """
        # Get redis connection information from config but allow overriding
        # via a relation.
        redis_hostname = self.config["redis_host"]
        redis_port = 6379
        for redis_unit in self.stored.redis_relation:
            redis_hostname = self.stored.redis_relation[redis_unit]["hostname"]
            redis_port = self.stored.redis_relation[redis_unit]["port"]
            logging.debug("Got redis connection details from relation of %s:%s", redis_hostname, redis_port)

        # Set our status while we get configured.
        self.model.unit.status = MaintenanceStatus('Configuring pod')

        # Leader must set the pod spec.
        if self.model.unit.is_leader():
            if not self.check_db_is_valid(self.stored):
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
            # Get our spec definition.
            if self.check_config_is_valid(config):
                # Get pod spec using our app name and config
                pod_spec = get_pod_spec(self.framework.model.app.name, config)
                # Set our pod spec.
                self.model.pod.set_spec(pod_spec)
                self.model.unit.status = ActiveStatus()
        else:
            self.model.unit.status = ActiveStatus()

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

        self.configure_pod()


if __name__ == '__main__':  # pragma: no cover
    main(DiscourseCharm)
