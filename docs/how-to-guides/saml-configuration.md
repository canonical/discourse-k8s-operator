To configure Discourse's SAML integration you'll have to set the following configuration options with the appropriate values for your SAML server by running `juju config [charm_name] [configuration]=[value]`.

The SAML URL needs to be scpecified in `saml_target_url`. If you wish to force the login to go through SAML, enable `force_saml_login`.
The groups to be synced from the provider can be defined in `saml_sync_groups` as a comma-separated list of values.

For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).
