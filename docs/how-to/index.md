---
myst:
  html_meta:
    "description lang=en": "How-to guides for operating the Discourse charm, including basic operations, upgrades, and deployments."
---

(how_to_index)=

# How-to guides

Manage the operational lifecycle of your Discourse deployment, from
initial provisioning and configurations to ongoing maintenance and
contribution workflows.

## Initial setup

A working Discourse deployment begins with establishing an initial set of
configurations to match your use case and needs.

* [Configure the hostname]
* [Configure the container]

## Basic operations

Your base deployment might involve additional configurations
and operations related to external services for storage, email
delivery, or authentication.

* [Access the Rails Console]
* [Configure S3]
* [Configure SMTP]
* [Configure SAML]

## Maintenance and development

As your deployment ages, preserving data integrity across
upgrades requires a reliable backup and restore strategy.
You may even have feedback or ideas for future features to
the charm; contributors working on the charm itself should familiarize
themselves with the development workflow.

* [Backup and restore]
* [Upgrade]
* [Contribute]

<!--Links-->

[Access the Rails Console]: access--the-rails-console.md
[Backup and restore]: backup-and-restore.md
[Configure the container]: configure-container.md
[Configure the hostname]: configure-hostname.md
[Configure S3]: configure-s3.md
[Configure SAML]: configure-saml.md
[Configure SMTP]: configure-smtp.md
[Upgrade]: upgrade.md
[Contribute]: contribute.rst

```{toctree}
:hidden:
:maxdepth: 1
Configure hostname <configure-hostname>
Configure container <configure-container>
Access the Rails console <access--the-rails-console>
Configure S3 <configure-s3>
Configure SMTP <configure-smtp>
Configure SAML <configure-saml>
Back up and restore <backup-and-restore>
Upgrade <upgrade>
Contribute <contribute>
```