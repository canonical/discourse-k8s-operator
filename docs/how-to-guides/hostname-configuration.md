This charm exposes the `external_hostname` configuration option to specify the external hostname of the application.

To expose the application it is recommended to set that configuration option and deploy and relate the [Nginx Ingress Integrator Operator](https://charmhub.io/nginx-ingress-integrator), that will be automatically configured with the values provided by the charm.

Assuming discourse is already up and running as `discourse-k8s`, you'll need to run the following commands:
```
# Configure the external hostname
juju config discourse-k8s external_hostname=discourse.local
# Deploy and relate the Nginx Ingress Integrator charm
juju deploy nginx-ingress-integrator
juju trust nginx-ingress-integrator --scope cluster # if RBAC is enabled
juju relate nginx-ingress-integrator discourse-k8s
```

For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).
