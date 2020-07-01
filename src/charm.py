#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    ModelError,
    WaitingStatus,
)


class DiscourseCharm(CharmBase):
    state = StoredState()

    def __init__(self, framework, key):
        super().__init__(framework, key)

        self.state.set_default(is_started=False)
        self.framework.observe(self.on.leader_elected, self.configure_pod)
        self.framework.observe(self.on.config_changed, self.configure_pod)
        self.framework.observe(self.on.upgrade_charm, self.configure_pod)

    def get_pod_spec(self):

        # get our config
        config = self.framework.model.config

        pod_spec = {
            "version": 2,
            "containers": [{
                "name": self.framework.model.app.name,
                "imageDetails": {"imagePath": config['discourse_image']},
                "imagePullPolicy": "IfNotPresent",
                "ports": [{
                    "containerPort": 3000,
                    "protocol": "TCP",
                }],
                "config": self.create_discourse_pod_config(config),
            }],
            "kubernetesResources": {
                "ingressResources": [
                    self.create_ingress_config(config)
                ]
            },
            "service": {
                "scalePolicy": "serial"
            }
        }

        # this handles when we are trying to get an image from a private
        # registry.  Details are here:
        # https://kubernetes.io/docs/concepts/containers/images/#specifying-imagepullsecrets-on-a-pod
        if config['registry_secrets_name']:
            pod_spec['containers'][0].set("imagePullSecrets", config['registry_secrets_name'])

        return pod_spec

    def create_discourse_pod_config(self, config):
        pod_config = {
            'DISCOURSE_POSTGRES_USERNAME': config['db_user'],
            'DISCOURSE_POSTGRES_PASSWORD': config['db_password'],
            'DISCOURSE_POSTGRES_HOST': config['db_host'],
            'DISCOURSE_POSTGRES_NAME': config['db_name'],
            'DISCOURSE_DEVELOPER_EMAILS': config['developer_emails'],
            'DISCOURSE_HOSTNAME': config['external_hostname'],
            'DISCOURSE_SMTP_DOMAIN': config['smtp_domain'],
            'DISCOURSE_SMTP_ADDRESS': config['smtp_address'],
            'DISCOURSE_SMTP_PORT': config['smtp_port'],
            'DISCOURSE_SMTP_AUTHENTICATION': config['smtp_authentication'],
            'DISCOURSE_SMTP_OPENSSL_VERIFY_MODE': config['smtp_openssl_verify_mode'],
            'DISCOURSE_SMTP_USER_NAME': config['smtp_username'],
            'DISCOURSE_SMTP_PASSWORD': config['smtp_password'],
            'DISCOURSE_ENABLE_LOCAL_REDIS': config['enable_local_redis'],
            'DISCOURSE_REDIS_HOST': config['redis_host'],
            'DISCOURSE_SERVE_STATIC_ASSETS': config['serve_static_assets'],
        }
        return pod_config

    def create_ingress_config(self, config):
        ingressResource = {
            "name": self.framework.model.app.name + "-ingress",
            "spec": {
                "rules": [
                    {
                        "host": config['external_hostname'],
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "backend": {
                                        "serviceName": self.framework.model.app.name,
                                        "servicePort": 3000
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }

        return ingressResource

    def check_config_is_valid(self):
        config = self.framework.model.config
        valid_config = True
        errors = []
        missing_fields = []

        needed_fields = ['db_user', 'db_password', 'db_host', 'db_name', 'smtp_address',
                         'redis_host']
        for key in needed_fields:
            if len(config[key]) == 0:
                missing_fields.append(key)

        if len(missing_fields):
            valid_config = False
            errors.append('Required configuration missing: {}'.format(" ".join(missing_fields)))

        if config['redis_host'] == '127.0.0.1' and config['enable_local_redis'] != "true":
            valid_config = False
            errors.append('redis_host set to 127.0.0.1, but enable_local_redis is disabled')

        # set status if we have a bad config
        if errors:
            self.model.unit.status = BlockedStatus(", ".join(errors))
        else:
            self.model.unit.status = MaintenanceStatus("Configuration passed validation")

        return valid_config

    def configure_pod(self, event):

        # set our status while we get configured
        self.model.unit.status = MaintenanceStatus('Configuring pod')

        # leader must set the pod spec
        if self.model.unit.is_leader():
            # get our spec definition
            if self.check_config_is_valid():
                pod_spec = self.get_pod_spec()
                # set our pod spec
                self.model.pod.set_spec(pod_spec)
                self.state.is_started = True
                self.model.unit.status = ActiveStatus()

    def on_new_client(self, event):
        if not self.state.is_started:
            return event.defer()

        event.client.serve(hosts=[event.client.ingress_address],
                           port=self.model.config['http_port'])


if __name__ == '__main__':
    main(DiscourseCharm)
