Upgrades are done just by running the `juju refresh` subcommand. Juju, Kubernetes, and Discourse then work together to ensure that one pod is upgraded to the new version and makes any database schema changes before the rest of the pods are upgraded in their turn.

## Upgrading from pod-spec to sidecar
It is recommended to take a database backup before starting an upgrade from pod-spec to the sidecar version of the discourse-k8s charm.

When upgrading from the pod-spec charm some downtime is to be expected. The existing Deployment will be deleted and a new StatefulSet will be created from scratch. Hence, the charm will be unresponsive while the discourse image resource is downloaded from the Charmhub registry and the first unit is spun up.

The [Nginx Ingress Integrator charm](https://charmhub.io/nginx-ingress-integrator) should now be deployed alongside the Discourse charm and related and configured appropriately to provision the ingress resources as they are not provided by sidecar charms. You can do this as follows:
```
# After upgrading to the sidecar version
juju deploy nginx-ingress-integrator
juju relate nginx-ingress-integrator discourse-k8s
# If you require TLS (per below):
juju config nginx-ingress-integrator tls-secret-name=YOUR_TLS_SECRET_NAME
# If your cluster has RBAC:
juju trust nginx-ingress-integrator --scope cluster
```

Because the pod-spec charm doesn't [store state](https://discourse.charmhub.io/t/keeping-state-in-juju-controllers-in-operator-framework/3303) in the Juju controller, during the upgrade the charm stored state will be lost, so the database relations will have to be recreated in order to exchange the connection details again. This can be done by running:
```
juju remove-relation redis-k8s:redis discourse-k8s:redis
juju remove-relation  postgresql-k8s:db-admin discourse-k8s:db

juju relate redis-k8s:redis discourse-k8s:redis
juju relate postgresql-k8s:db-admin discourse-k8s:db
```

Note also that the following configuration options have been dropped, so manual intervention to prepare for the upgrade might be needed.
* `db_name`: Customizing the name of the database Discourse connects to is not supported anymore. The database will have to be renamed to `discourse`, in order for the charm to be able to connect to it.
* `redis_host`: Using a Redis instance not provided by a charm is not supported anymore. Redis should now be deployed as a charm and related to Discourse. The charm will automatically retrieve all the settings needed to connect to it from the relation. You can do this as follows:
```
juju deploy redis-k8s
juju relate discourse-k8s redis-k8s
```
* `tls_secret_name`: Providing the TLS secret via the charm configuration is not supported anymore. The secret must be provided now using the [Nginx Ingress Integrator charm](https://charmhub.io/nginx-ingress-integrator) using the `tls-secret-name` option. See above for an example.

Given that the image is now packed and released as a charm resource, the following configuration options have been dropped too:
* `discourse_image`
* `image_user`
* `image_pass`

You can use a different image than the one deployed by default with the charm using the [attach-resource](https://juju.is/docs/olm/juju-attach-resource) juju command.
