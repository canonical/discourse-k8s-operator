# Discourse Operator
A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying and managing Discourse on Kubernetes.

Discourse is an open-source software application used to create customer-friendly and community-friendly discussion platforms, 
forums, and mailing lists. It's designed to work as a discussion platform for various topics and is widely used by numerous 
organizations and individuals to build communities, provide customer support, and facilitate conversations. The platform is 
built with a focus on simplicity, user-friendliness, and responsiveness, making it accessible from both desktops and mobile 
devices. Discourse provides various moderation and administration tools, enabling community managers to maintain a healthy and 
constructive environment.

This charm simplifies operations of Discourse on Kubernetes, such as scaling the number of instances, integration 
with SSO, access to S3 for redundant file storage and more. It allows for deployment on many different Kubernetes 
platforms, from [MicroK8s](https://microk8s.io) or [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud 
Kubernetes offerings.

## In this documentation

| | |
|--|--|
|  [Tutorials](/t/discourse-k8s-docs-getting-started/12157)</br>  Get started - a hands-on introduction to using the Charmed Discourse operator for new users </br> |  [How-to guides](/t/discourse-k8s-docs-how-to-configure-the-container/12141) </br> Step-by-step guides covering key operations and common tasks |
| [Reference](/t/discourse-k8s-docs-integrations/12155) </br> Technical information - specifications, APIs, architecture | [Explanation](/t/discourse-k8s-docs-charm-architecture/12139) </br> Concepts - discussion and clarification of key topics  |

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/discourse-documentation-overview/3773) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/discourse-k8s-operator/issues).

## Project and community

The Discourse Operator is a member of the Ubuntu family. It's an open source
project that warmly welcomes community projects, contributions, suggestions,
fixes and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](https://charmhub.io/discourse-k8s/docs/how-to-contribute)

# Contents

1. [Tutorial](tutorial.md)
1. [How To](how-to)
  1. [Access the Rails console](how-to/access--the-rails-console.md)
  1. [Backup and restore](how-to/backup-and-restore.md)
  1. [Configure the container](how-to/configure-container.md)
  1. [Configure the hostname](how-to/configure-hostname.md)
  1. [Configure S3](how-to/configure-s3.md)
  1. [Configure SAML](how-to/configure-saml.md)
  1. [Configure SMTP](how-to/configure-smtp.md)
  1. [Contribute](how-to/contribute.md)
  1. [Upgrade](how-to/upgrade.md)
1. [Reference](reference)
  1. [Actions](reference/actions.md)
  1. [Configurations](reference/configurations.md)
  1. [External Access](reference/external-access.md)
  1. [Integrations](reference/integrations.md)
  1. [Plugins](reference/plugins.md)
1. [Explanation](explanation)
  1. [Charm architecture](explanation/charm-architecture.md)
1. [Changelog](changelog.md)