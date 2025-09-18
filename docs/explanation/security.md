# Security

This document explains the possible security risks in the Discourse charm and best practices to avoid them. It revolves around the practices from the charm side. Refer to the [official Discourse documentation](https://meta.discourse.org/c/documentation/10?tl=en) for upstream practices. 

## Outdated software

Outdated software components, such as plugins or the upstream workload, can introduce exploitable security vulnerabilities.

### Best practices

- Regularly [update the charm](../how-to/upgrade.md) revision to include latest charm components. Updates include the security fixes from the dependencies and the workloads as the charm dependencies are regularly updated.
- Regularly update Juju to latest version to include security fixes.
- Deploy observability, like the Canonical Observability Stack, to detect any unusual behaviors.


## Loss of data

The Discourse database or the media files can be lost or corrupted for various reasons. 

### Best practices

- Use S3 for uploads and regular backups. See [how to configure S3 section](../how-to/configure-s3.md).
- Use a dedicated Charmed PostgreSQL and regularly back up the database through the charm's [backup action](https://canonical-charmed-postgresql.readthedocs-hosted.com/14/how-to/back-up-and-restore/create-a-backup/).

<!-- vale Canonical.007-Headings-sentence-case = NO -->
<!-- DOS is an acronym -->
## Denial-of-service (DOS) attacks
<!-- vale Canonical.007-Headings-sentence-case = YES-->

Malicious attackers can overwhelm the Discourse traffic with DOS attacks, making the application unresponsive to legitimate users.

### Best practices

- Deploy an ingress that can limit the number of requests per users. For example, [NGINX Ingress Integrator](https://charmhub.io/nginx-ingress-integrator) charm supports limiting the requests per second through [`limit-rps`](https://charmhub.io/nginx-ingress-integrator/configurations#limit-rps) configuration and features an allow list through [`limit-whitelist`](https://charmhub.io/nginx-ingress-integrator/configurations#limit-whitelist) configuration. 
- Set the throttle level directly from Discourse charm through the [`throttle-level`](https://charmhub.io/discourse-k8s/configurations#throttle_level) configuration by setting it to `permissive` or `strict`.

## Unencrypted traffic

If Discourse serves HTTP, the traffic between Discourse and the clients will be unencrypted, risking eavesdropping and tampering.

### Best practices

- Always enable HTTPS by setting the [`force_https`](https://charmhub.io/discourse-k8s/configurations#force_https) configuration option to `True`.
- Integrate the Discourse charm with an ingress that provides TLS, such as [NGINX Ingress Integrator](https://charmhub.io/nginx-ingress-integrator).
- Force SMTP encryption by setting [`smtp_force_tls`](https://charmhub.io/discourse-k8s/configurations#smtp_force_tls) to `True`.

<!-- vale Canonical.007-Headings-sentence-case = NO -->
<!-- CORS is an acronym -->
## Cross-origin requests (CORS)
<!-- vale Canonical.007-Headings-sentence-case = YES-->

Discourse can be configured to enable or disable CORS through the [`enable_cors`](https://charmhub.io/discourse-k8s/configurations#enable_cors) configuration option. If enabled unnecessarily or [`cors_origin`](https://charmhub.io/discourse-k8s/configurations#cors_origin) is configured too broadly, a malicious attacker can interact with Discourse on behalf of legitimate users.

### Best practices

- Only set `enable_cors` if you require Single Sign-On (SSO) or another trusted cross-domain integration.
- Only allow trusted origins by configuring the [`cors_origin`](https://charmhub.io/discourse-k8s/configurations#cors_origin) and [`augment_cors_origin`](https://charmhub.io/discourse-k8s/configurations#augment_cors_origin) options. Do not set `cors_origin` to `*` as this allows all origins.