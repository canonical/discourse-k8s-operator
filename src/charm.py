#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
    ModelError,
    WaitingStatus,
)

from oci_image import OCIImageResource, ResourceError


class DiscourseCharm(CharmBase):
    state = StoredState()

    def __init__(self, framework, key):
        super().__init__(framework, key)

        self.state.set_default(is_started=False)
        # get our discourse_image from juju
        # ie: juju deploy . --resource discourse_image=discourse-canonical:1.0.0 )
        self.discourse_image = OCIImageResource(self, 'discourse_image')
        self.framework.observe(self.on.leader_elected, self.configure_pod)
        self.framework.observe(self.on.config_changed, self.configure_pod)
        self.framework.observe(self.on.upgrade_charm, self.configure_pod)

    def verify_leadership(self):
        if not self.model.unit.is_leader():
            raise LeadershipError()

    def configure_pod(self, event):

        # Verify we are leader - throws exception if we are not
        # Revisit this, because it's not what we actually want - prevents scaling
        self.verify_leadership()

        # Get the image details for our discourse image - this will
        # obtain all the details needed to access our docker registry / etc.
        discourse_image_details = self.discourse_image.fetch()

        # set our status while we get configured
        self.model.unit.status = MaintenanceStatus('Configuring pod')

        # get our config
        config = self.framework.model.config

        # set our spec per our config
        # revise this to create the spec in two pieces, 
        # the leader should have a initContainer section,
        # non-leaders should not.
        self.model.pod.set_spec({
            'containers': [{
                'name': self.framework.model.app.name,
                'imageDetails': discourse_image_details,
                'imagePullPolicy': 'Never',
                'ports': [{
                    'containerPort': int(config['service_port']),
                    'protocol': 'TCP',
                }],
                'config': {
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
                },
            }],
            'initContainers': [{
                'name': '%s-init1'%(self.framework.model.app.name),
                'imageDetails': discourse_image_details,
                'imagePullPolicy': 'Never',
                'config': {
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
                    # the magic 'only migrate, then exit'
                    'DISCOURSE_MIGRATE_ONLY': 'true',
                },
            }],

        })
        self.state.is_started = True
        self.model.unit.status = ActiveStatus()

    def on_new_client(self, event):
        if not self.state.is_started:
            return event.defer()

        event.client.serve(hosts=[event.client.ingress_address],
                           port=self.model.config['http_port'])

class LeadershipError(ModelError):
    def __init__(self):
        super().__init__('not leader')
        self.status = WaitingStatus('Deferring to leader unit to configure pod')


if __name__ == '__main__':
    main(DiscourseCharm)
