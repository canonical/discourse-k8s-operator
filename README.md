[![CharmHub Badge](https://charmhub.io/discourse-k8s/badge.svg)](https://charmhub.io/discourse-k8s)
[![Publish to edge](https://github.com/canonical/discourse-k8s-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/discourse-k8s-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/discourse-k8s-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/discourse-k8s-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# Discourse Operator

A juju charm deploying and managing Discourse on Kubernetes. Discourse is the
100% open source discussion platform. Use it as a mailing list, discussion
forum or long-form chat room.

This charm simplifies initial deployment and "day N" operations of Discourse
on Kubernetes, such as scaling the number of instances, integration with SSO,
access to S3 for redundant file storage and more. It allows for deployment on
many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) or
[Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes
offerings.

As such, the charm makes it easy for those looking to take control of their own
discussion platform whilst keeping operations simple, and gives them the
freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating Discourse simple and
straightforward through Juju's clean interface. It will allow easy deployment
into multiple environments for testing of changes, and supports scaling out for
enterprise deployments.

## Project and community

The Discourse Operator is a member of the Ubuntu family. It's an open source
project that warmly welcomes community projects, contributions, suggestions,
fixes and constructive feedback.
* [Code of conduct](https://ubuntu.com/community/code-of-conduct)
* [Get support](https://discourse.charmhub.io/)
* [Join our online chat](https://chat.charmhub.io/charmhub/channels/charm-dev)
* [Contribute](https://charmhub.io/discourse-k8s/docs/how-to-contribute)
* [Get started](https://charmhub.io/discourse-k8s/docs/getting-started)

Thinking about using the Discourse Operator for your next project? [Get in touch](https://chat.charmhub.io/charmhub/channels/charm-dev)!

---

For further details,
[see the charm's detailed documentation](https://charmhub.io/discourse-k8s/docs).
