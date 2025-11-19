# Deploy the Discourse charm for the first time

In this tutorial, we'll go through each step of the process to get a basic Discourse deployment.

## What you'll need

> Tip: You can get a working setup by using a Multipass VM as outlined in the
[Set up your test environment](https://documentation.ubuntu.com/juju/3.6/howto/manage-your-deployment/#set-up-your-deployment-local-testing-and-development) guide.
When using a Multipass VM, make sure to replace `127.0.0.1` IP addresses with the
VM IP in steps that assume you're running locally. To get the IP address of the
Multipass instance run ```multipass info my-juju-vm```.

You will need a working station, e.g., a laptop, with AMD64 architecture. Your working station
should have at least 4 CPUs, 8 GB of RAM, and 50 GB of disk space.

This tutorial requires the following software to be installed on your working station:

- Juju 3
- MicroK8s 1.28

For more information about how to install Juju, see [Get started with Juju](https://documentation.ubuntu.com/juju/3.6/tutorial/).

MicroK8s must have an NGINX ingress controller enabled. Complete this requirement by running:

```
microk8s enable ingress
```

For more details, see [Add-on: Ingress](https://microk8s.io/docs/addon-ingress).

Finally, Juju must be bootstrapped to a MicroK8s controller. You can achieve this by running: 

```
juju bootstrap microk8s tutorial-controller
```

## What you'll do

1. Deploy the Discourse charm
2. Integrate with `nginx-ingress-integrator`, `postgresql-k8s` and `redis-k8s` charms
3. Inspect the Kubernetes resources created
4. Create an admin user and log in
5. Clean up the environment

### Shell into the Multipass VM
> NOTE: If you're working locally, you don't need to do this step.

To be able to work inside the Multipass VM first you need to log in with the following command:
```
multipass shell my-juju-vm
```

### Add a Juju model for the tutorial

To easily clean up the resources and separate your workload from the contents of this tutorial, set up a new Juju model named `discourse-tutorial`:

```
juju add-model discourse-tutorial
```

### Deploy the charms

Discourse requires connections to PostgreSQL and Redis. For more information, see the [Charm Integrations](https://charmhub.io/discourse-k8s/docs/reference-integrations).

> NOTE: Discourse requires PostgreSQL extensions to be available in the relation.

Deploy the charms:
```
juju deploy redis-k8s --channel latest/edge
juju deploy postgresql-k8s --channel 14/stable --trust
juju deploy discourse-k8s
```

Enable the required PostgreSQL extensions:
```
juju config postgresql-k8s plugin_hstore_enable=True plugin_pg_trgm_enable=True
```

### Integrate with the Redis k8s charm and the PostgreSQL k8s charm

Integrate `redis-k8s` and `postgresql-k8s` to `discourse-k8s`:
```
juju integrate redis-k8s discourse-k8s
juju integrate discourse-k8s postgresql-k8s
```

By running `juju status --relations` the current state of the deployment can be queried:
```
Model               Controller  Cloud/Region        Version  SLA          Timestamp
discourse-tutorial  microk8s    microk8s/localhost  3.5.4    unsupported  14:07:18+03:00

App             Version  Status  Scale  Charm           Channel        Rev  Address         Exposed  Message
discourse-k8s   3.3.0    active      1  discourse-k8s   latest/stable  173  10.152.183.231  no
postgresql-k8s  14.12    active      1  postgresql-k8s  14/stable      381  10.152.183.143  no
redis-k8s       7.2.5    active      1  redis-k8s       latest/edge     36  10.152.183.188  no

Unit               Workload  Agent  Address      Ports  Message
discourse-k8s/0*   active    idle   10.1.32.182
postgresql-k8s/0*  active    idle   10.1.32.184         Primary
redis-k8s/0*       active    idle   10.1.32.181

Integration provider           Requirer                       Interface          Type     Message
discourse-k8s:restart          discourse-k8s:restart          rolling_op         peer
postgresql-k8s:database        discourse-k8s:database         postgresql_client  regular
postgresql-k8s:database-peers  postgresql-k8s:database-peers  postgresql_peers   peer
postgresql-k8s:restart         postgresql-k8s:restart         rolling_op         peer
postgresql-k8s:upgrade         postgresql-k8s:upgrade         upgrade            peer
redis-k8s:redis                discourse-k8s:redis            redis              regular
redis-k8s:redis-peers          redis-k8s:redis-peers          redis-peers        peer
```
The deployment finishes when all the charms show `Active` states.

Run `kubectl get pods -n discourse-tutorial` to see the pods that are being created by the charms:
```
NAME                             READY   STATUS    RESTARTS   AGE
modeloperator-c584f6f9f-qf9gr    1/1     Running   0          5m30s
redis-k8s-0                      3/3     Running   0          5m22s
discourse-k8s-0                  2/2     Running   0          5m1s
postgresql-k8s-0                 2/2     Running   0          5m9s
```

### Provide ingress capabilities

In order to expose the charm, the Nginx Ingress Integrator needs to be deployed and integrated with Discourse:

```
juju deploy nginx-ingress-integrator
```
To check if RBAC is enabled run the following command:
```
microk8s status | grep rbac
```
If it is enabled, then the output should be like the following:
```
rbac                 # (core) Role-Based Access Control for authorisation
```
If the output is empty then RBAC is not enabled.

If your cluster has RBAC enabled, you'll be prompted to run the following command:
```
juju trust nginx-ingress-integrator --scope=cluster
```
Then you need to integrate the charm with Nginx Ingress Integrator:
```
juju integrate discourse-k8s nginx-ingress-integrator
```

### Validate workload is reachable

To validate that you can successfully reach the deployed workload, run the following command:
```
curl http://discourse-k8s --resolve discourse-k8s:80:127.0.0.1
```

### Create an admin user and log in

To create an admin user, use the `create-user` action:
```
juju run discourse-k8s/0 create-user admin=true email=email@example.com
```
The command will return the password of the created user. Discourse will be deployed with `discourse-k8s` as default hostname.

If you are following the tutorial in your local machine, modify your `/etc/hosts` file so that it points to `127.0.0.1`:

```
echo "127.0.0.1 discourse-k8s" | sudo tee -a /etc/hosts
```

After that, visit `http://discourse-k8s` to reach Discourse, using the credentials returned from the `create-user` action to login.

### Clean up the environment

Congratulations! You have successfully finished the Discourse tutorial. You can now remove the
model environment that you've created using the following command:

```
juju destroy-model discourse-tutorial --destroy-storage
```
If you used Multipass, to remove the Multipass instance you created for this tutorial, use the following command.
```
multipass delete --purge my-juju-vm
```
Finally, remove the `127.0.0.1 discourse-k8s` line from the `/etc/hosts` file.

## Next steps

You achieved a basic deployment of the Discourse charm. If you want to go further in your deployment
or learn more about the charm, check out these pages:

- Perform basic operations with your deployment like
  [configuring S3](https://charmhub.io/discourse-k8s/docs/how-to-configure-s3)
  or [SMTP](https://charmhub.io/discourse-k8s/docs/how-to-configure-smtp).
- Make your deployment more secure by [configuring SAML](https://charmhub.io/discourse-k8s/docs/how-to-configure-saml),
  and learn more about the charm's security in
  [Security overview](https://charmhub.io/discourse-k8s/docs/explanation-security).
- Learn more about the available [relation endpoints](https://charmhub.io/discourse-k8s/docs/reference-integrations)
  for the Discourse charm.

