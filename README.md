[![CharmHub Badge](https://charmhub.io/discourse-k8s/badge.svg)](https://charmhub.io/discourse-k8s)
[![Publish to edge](https://github.com/canonical/discourse-k8s-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/discourse-k8s-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/discourse-k8s-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/discourse-k8s-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)
<!-- vale Canonical.007-Headings-sentence-case = NO -->
<!-- "Operator" is part of the name -->
# Discourse Operator
<!-- vale Canonical.007-Headings-sentence-case = YES -->
A Juju charm deploying and managing Discourse on Kubernetes. Discourse is the
100% open source discussion platform. Use it as a mailing list, discussion
forum or long-form chat room.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling and more.
For Charmed Discourse, this includes:
  - Scaling
  - Integration with SSO
  - Integration with S3 for redundant file storage

It allows for deployment on
many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to
[Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes
offerings.

For information about how to deploy, integrate and manage this charm,
see the Official [Discourse Operator Documentation](https://charmhub.io/discourse-k8s/docs).

## Get started

You can follow the tutorial [here](https://charmhub.io/discourse-k8s/docs/tutorial).

### Basic operations

The following actions are available for this charm:
  - `anonymize-user`: anonymize a user
  - `create-user`: create a new user
  - `promote-user`: promote a user to admin

You can check out the [full list of actions here](https://charmhub.io/discourse-k8s/actions).

## Integrations

This charm can be integrated with other Juju charms and services:

  - [Redis](https://charmhub.io/redis-k8s): Redis is an open source (BSD licensed), in-memory data structure store, used as a database, cache and message broker.
  - [Saml](https://charmhub.io/saml-integrator): SAML is an open standard used for authentication.
  - [PostgreSQL](https://charmhub.io/postgresql-k8s): PostgreSQL is a powerful, open source object-relational database system.

For a full list of integrations, see the [Charmhub documentation](https://charmhub.io/discourse-k8s/integrations).

## Learn more
* [Read more](https://charmhub.io/discourse-k8s) <!--Link to the charm's official documentation-->
* [Developer documentation](https://docs.discourse.org/) <!--Link to any developer documentation-->
* [Official webpage](https://www.discourse.org/index) <!--(Optional) Link to official webpage/blog/marketing content-->
* [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com) <!--(Optional) Link to a page or section about troubleshooting/FAQ-->

## Project and community
* [Issues](https://github.com/canonical/discourse-k8s-operator/issues) <!--Link to GitHub issues (if applicable)-->
* [Contributing](https://charmhub.io/discourse-k8s/docs/how-to-contribute) <!--Link to any contribution guides-->
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com) <!--Link to contact info (if applicable), e.g. Matrix channel-->
