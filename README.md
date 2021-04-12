# Discourse Operator

A juju charm deploying and managing Discourse on Kubernetes, configurable to
use a PostgreSQL backend.

## Overview

Supported features include SAML authentication, scaling to multiple pods and the
storage of files and images in S3. This charm also offers seamless Discourse
version upgrades, initiated by switching to an image with a newer version of
Discourse than the one currently deployed.

## Usage

For details on using Kubernetes with Juju [see here](https://juju.is/docs/kubernetes), and for
details on using Juju with MicroK8s for easy local testing [see here](https://juju.is/docs/microk8s-cloud).

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

Once the deployment is completed and the "discourse" workload state in `juju
status` has changed to "active" you can visit http://{$discourse_ip}:3000 in a
browser and log in to your Discourse instance.

For further details, [see here](https://charmhub.io/discourse-charmers-discourse-k8s/docs).
