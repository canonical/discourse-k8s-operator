---
myst:
  html_meta:
    "description lang=en": "Learn how to deploy, configure and operate the Discourse charm using Juju."
---

<!-- vale Canonical.007-Headings-sentence-case = NO -->
<!-- "Operator" is part of the name -->

# Discourse Operator

<!-- vale Canonical.007-Headings-sentence-case = YES -->

A {ref}`Juju <juju:juju>` {ref}`charm <juju:charm>` deploying and managing Discourse on Kubernetes.

Discourse is an open-source software application used to create customer-friendly and community-friendly discussion platforms, 
forums, and mailing lists. It's designed to work as a discussion platform for various topics and is widely used by numerous 
organizations and individuals to build communities, provide customer support, and facilitate conversations. The platform is 
built with a focus on simplicity, user-friendliness, and responsiveness, making it accessible from both desktops and mobile 
devices. Discourse provides various moderation and administration tools, enabling community managers to maintain a healthy and 
constructive environment.

This charm simplifies operations of Discourse on Kubernetes, such as scaling the number of instances, integration 
with SSO, access to S3 for redundant file storage and more. It allows for deployment on many different Kubernetes 
platforms, from [MicroK8s](https://canonical.com/microk8s) or [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud 
Kubernetes offerings.

## In this documentation

| | |
|--|--|
|  {ref}`Tutorials <tutorial>`</br>  Get started - a hands-on introduction to using the Charmed Discourse operator for new users </br> |  {ref}`How-to guides <how_to_index>` </br> Step-by-step guides covering key operations and common tasks | 
| {ref}`Reference <reference_index>` </br> Technical information - specifications, APIs, architecture | {ref}`Explanation <explanation_index>` </br> Concepts - discussion and clarification of key topics  |

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions, and constructive feedback on our documentation. See {ref}`how_to_contribute` for more information.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/discourse-k8s-operator/issues).

## Project and community

The Discourse Operator is a member of the Ubuntu family. It's an open source
project that warmly welcomes community projects, contributions, suggestions,
fixes and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- {ref}`Contribute <how_to_contribute>`

```{toctree}
:hidden:
Tutorial <tutorial>
how-to/index
reference/index
explanation/index
changelog
```
