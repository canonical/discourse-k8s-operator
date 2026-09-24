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
forums, and mailing lists.
This charm simplifies operations of Discourse on Kubernetes, such as scaling the number of instances, integration 
with SSO, access to S3 for redundant file storage and more. It allows for deployment on many different Kubernetes 
platforms, from [MicroK8s](https://canonical.com/microk8s) or [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud 
Kubernetes offerings.
This charm makes operating Discourse straightforward for DevOps and SRE teams who want to run community forums or support platforms on Kubernetes through Juju's clean interface.

## In this documentation

```{list-table}
   :header-rows: 1
   :widths: 15 30

* - 
  - 
* - **Get started**
  - {ref}`Deploy the Discourse charm <tutorial>`
* - **Deployment**
  - {ref}`Configure the hostname <how_to_configure_hostname>` | {ref}`Configure the container <how_to_configure_container>` | {ref}`Configure S3 <how_to_configure_s3>` | {ref}`Configure SMTP <how_to_configure_smtp>` | {ref}`Configure SAML <how_to_configure_saml>`
* - **Operations**
  - {ref}`Access the Rails console <how_to_access_the_rails_console>` | {ref}`Back up and restore <how_to_backup_and_restore>` | {ref}`Upgrade <how_to_upgrade>`
* - **Integrations**
  - {ref}`Integrations <reference_integrations>` | {ref}`External access <reference_external_access>`
* - **Design**
  - {ref}`Charm architecture <reference_charm_architecture>` | {ref}`Versioning <reference_versioning>`
* - **Security**
  - {ref}`Overview <explanation_security>`
```

## How this documentation is organized

This documentation uses the
[Diátaxis documentation structure](https://diataxis.fr/).

* The {ref}`Tutorial <tutorial>` takes you step-by-step through your first deployment of the Discourse charm.
* The {ref}`How-to guides <how_to_index>` cover practical tasks for configuring, integrating, and maintaining your Discourse deployment.
* {ref}`Reference <reference_index>` provides technical details on actions, configurations, plugins, integrations, and charm architecture.
* {ref}`Explanation <explanation_index>` includes context and overviews on key topics such as security.

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions, and constructive feedback on our documentation. See {ref}`how_to_contribute` for more information.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/discourse-k8s-operator/issues).

## Project and community

The Discourse Operator is a member of the Ubuntu family. It's an open-source
project that warmly welcomes community projects, contributions, suggestions,
fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [File a bug](https://github.com/canonical/discourse-k8s-operator/issues)
- Get support through the [Discourse forum](https://discourse.charmhub.io/)
- Join our [online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- {ref}`Contribute <how_to_contribute>`

Thinking about using the Discourse Operator for your next project?
[Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!

```{toctree}
:hidden:
Tutorial <tutorial>
how-to/index
reference/index
explanation/index
changelog
```
