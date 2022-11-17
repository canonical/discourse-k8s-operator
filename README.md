# Discourse Operator

A juju charm deploying and managing Discourse on Kubernetes. Discourse is the
100% open source discussion platform. Use it as a mailing list, discussion
forum or long-form chat room.

This charm simplifies initial deployment and "day N" operations of Discourse
on Kubernetes, such as scaling the number of instances, integration with SSO,
access to S3 for redundant file storage and more. It allows for deployment on
many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to
[Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes
offerings.

As such, the charm makes it easy for those looking to take control of their own
discussion platform whilst keeping operations simple, and gives them the
freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating Discourse simple and
straightforward through Juju's clean interface. It will allow easy deployment
into multiple environments for testing of changes, and supports scaling out for
enterprise deployments.

## Deployment options overview

For overall concepts related to using Juju
[see the Juju overview page](https://juju.is/). For easy local testing we
recommend
[this how to on using MicroK8s with Juju](https://juju.is/docs/olm/microk8s).
Because this charm requires an ingress controller, you'll also need to enable
the `ingress` add-on by running `microk8s enable ingress`.

## How to deploy this charm (quick guide)

To deploy the charm and relate it to
[the PostgreSQL K8s charm](https://charmhub.io/postgresql-k8s) and
[the Redis K8s charm](https://charmhub.io/redis-k8s) within a Juju Kubernetes model:

    juju deploy postgresql-k8s
    juju deploy redis-k8s
    juju deploy discourse-k8s
    juju relate discourse-k8s postgresql-k8s:db-admin
    juju relate discourse-k8s redis-k8s

The charm also supports the `ingress` relation, which can be used with
[nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator/).

    juju deploy nginx-ingress-integrator
    juju relate discourse-k8s nginx-ingress-integrator

Once the deployment is completed and the "discourse-k8s" workload state in
`juju status` has changed to "active" you can add `discourse-k8s` to
`/etc/hosts` with the IP address of your Kubernetes cluster's ingress
(127.0.0.1 if you're using MicroK8s) and visit `http://discourse-k8s` in a
browser and log in to your Discourse instance.

## Project and community

The Discourse Operator is a member of the Ubuntu family. It's an open source
project that warmly welcomes community projects, contributions, suggestions,
fixes and constructive feedback.
* [Code of conduct](https://ubuntu.com/community/code-of-conduct)
* [Get support](https://discourse.charmhub.io/)
* [Join our online chat](https://chat.charmhub.io/charmhub/channels/charm-dev)
* [Contribute](https://charmhub.io/discourse-k8s/docs/contributing)
* [Roadmap](https://charmhub.io/discourse-k8s/docs/roadmap)
Thinking about using the Discourse Operator for your next project? [Get in touch](https://chat.charmhub.io/charmhub/channels/charm-dev)!

---

For further details,
[see the charm's detailed documentation](https://charmhub.io/discourse-k8s/docs).
