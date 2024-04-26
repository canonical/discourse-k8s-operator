# External access required by the Charm

Depending on the configuration of the charm, the next external accesses are needed:
 - Access to the PostgreSQL database (mandatory).
 - Access to the S3 server is S3 is configured in the charm.
 - Access to http://github.com to download Promtail if the logging interface is used in the charm.

If the option "external system avatars enabled" is enabled in the admin, access
to https://avatars.discourse.org is necessary.

Besides that, other services, like link previews and installing themes from a git repository
may need access to external sites to work, so allowing internet access to the Discourse instance is
recommended.
