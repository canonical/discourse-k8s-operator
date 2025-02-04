# How to configure SAML

To configure Discourse's SAML integration you'll have to set the following configuration options with the appropriate values for your SAML server by running `juju config [charm_name] [configuration]=[value]`.

If you wish to force the login to go through SAML, enable `force_saml_login`.
The groups to be synced from the provider can be defined in `saml_sync_groups` as a comma-separated list of values.
In order to implement the relation, Discourse has to be related with the [saml-integrator](https://charmhub.io/saml-integrator):
```
juju deploy saml-integrator --channel=edge
# Set the SAML integrator configs
juju config saml-integrator metadata_url=https://login.staging.ubuntu.com/saml/metadata
juju config saml-integrator entity_id=https://login.staging.ubuntu.com
juju integrate discourse-k8s saml-integrator
```

For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).