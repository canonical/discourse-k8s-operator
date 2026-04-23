# How-to guides

Manage the operational lifecycle of your Discourse deployment, from initial provisioning and service configuration through to ongoing maintenance and contribution workflows.

## Initial setup

A working Discourse deployment begins with establishing the charm's external identity and tuning the container runtime to match your infrastructure's resource profile.

* [Configure the hostname]
* [Configure the container]

## Basic operations

Day-to-day administration may involve direct database interaction through the Rails console, and depending on your infrastructure requirements, connecting external services for object storage, email delivery, or federated authentication.

* [Access the Rails Console]
* [Configure S3]
* [Configure SMTP]
* [Configure SAML]

## Maintenance and development

Preserving data integrity across upgrades requires a reliable backup and restore strategy. Contributors working on the charm itself should also familiarize themselves with the development workflow.

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
[Contribute]: contribute.md