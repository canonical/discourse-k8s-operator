# External access required by the Charm

Depending on the configuration of the charm, the next external accesses are needed:
 - Access to PostgreSQL instance.
 - Access to S3.
 - Access to github to download Promtail if logging interface is configured.

If the option "external system avatars enabled" is enabled in the admin, access
to `https://avatars.discourse.org` is necessary.

Besides that, other services, like link previews and installing themes from a git repository
may need access to external sites to work, so allowing internet access to the Discourse instance is
recommended.
