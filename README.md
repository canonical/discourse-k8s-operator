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

To deploy into a Juju K8s model:

    juju deploy postgresql-k8s
    juju deploy redis-k8s
    juju deploy discourse-k8s
    juju relate discourse-k8s postgresql-k8s:db-admin
    juju relate discourse-k8s redis-k8s

Once the deployment is completed and the "discourse" workload state in `juju
status` has changed to "active" you can visit http://{$discourse_ip}:3000 in a
browser and log in to your Discourse instance.

For further details, [see here](https://charmhub.io/discourse-charmers-discourse-k8s/docs).
