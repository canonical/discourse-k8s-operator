# Discourse Charm

## Overview

This charm deploys the Discourse discussion forum. Discourse is the 100% open
source discussion platform built for the next decade of the Internet. Use it
as a mailing list, discussion forum, long-form chat room, and more!

This is a k8s workload charm and can only be deployed to to a Juju k8s
cloud, attached to a controller using `juju add-k8s`.

## Usage

To get started with a test environment, first deploy Redis in an IaaS model:

    juju deploy cs:~redis-charmers/redis  # Note the deployed IP as ${REDIS_IP}

Now deploy the Discourse and PostgreSQL charms within a Juju Kubernetes model
as follows:

    juju deploy cs:~postgresql-charmers/postgresql-k8s postgresql
    juju deploy cs:~discourse-charmers/discourse-k8s discourse \
      --config redis_host=${REDIS_IP} \
      --config developer_emails="user@foo.internal" \
      --config external_hostname="foo.internal" \
      --config smtp_address="127.0.0.1" \
      --config smtp_domain="foo.internal"
    juju add-relation discourse postgresql:db-admin
    juju expose discourse

### Static content and uploads

Discourse supports post uploads. When using this charm you need to make 
use of the S3 storage option built in to discourse for file uploads.

You do this by accessing the Files option in the discourse settings
web admin panel. Enter your S3 options here and check the 'enable s3 
uploads' option. This will push any uploads made into the S3 system and
will serve them from there as well, eliminating the need for any persistent
local storage.

### Developing

Notes for deploying a test setup locally using MicroK8s:

    sudo snap install juju --classic
    sudo snap install juju-wait --classic
    sudo snap install microk8s --classic
    sudo snap alias microk8s.kubectl kubectl
    sudo snap install charmcraft
    git clone https://git.launchpad.net/charm-k8s-discourse
    cd charm-k8s-discourse
    make discourse.charm

    microk8s.reset  # Warning! Clean slate!
    microk8s.enable dns dashboard registry storage
    microk8s.status --wait-ready
    microk8s.config | juju add-k8s myk8s --client

    # Build your Discourse image
    make build-image
    docker push localhost:32000/discourse

    juju bootstrap myk8s
    juju add-model discourse-test
    juju deploy ./discourse.charm --config discourse_image=localhost:32000/discourse:latest discourse
    juju wait
    juju status

The charm will not function without a database, so you will need to
deploy `cs:postgresql` somewhere. You will also need a Redis application
to connect to, such as `cs:~redis-charmers/redis`.

If PostgreSQL is deployed in the same model you plan to use for
Discourse, simply use `juju relate discourse postgresql:db-admin`.  (This
deployment style is recommended for testing purposes only.)

Cross-model relations are also supported.  Create a suitable model on
a different cloud, for example, LXD or OpenStack.

    juju switch database
    juju deploy cs:postgresql
    juju deploy cs:~redis-charmers/redis # Use the IP address for the `redis_host` config option to discourse
    juju offer postgresql:db-admin

In most k8s deployments, traffic to external services from worker pods
will be SNATed by some part of the infrastructure.  You will need to
know what the source addresses or address range is for the next step.

    juju switch discourse-test
    juju find-offers  # note down offer URL; example used below:
    juju relate discourse admin/database.postgresql --via 10.9.8.0/24

(In the case of PostgreSQL, `--via` is needed so that the charm can
configure `pga_hba.conf` to let the k8s pods connect to the database.)

## Testing

Just run `make test`.
