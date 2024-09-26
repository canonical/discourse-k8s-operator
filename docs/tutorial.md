# Deploy the Discourse charm for the first time

## What you'll do

- Deploy the Discourse charm
- Integrate with nginx-ingress-integrator, postgresql-k8s and redis-k8s charms
- Inspect the Kubernetes resources created

In this tutorial, we'll go through each step of the process to get a basic Discourse deployment.

## Requirements

* A laptop or desktop running Ubuntu (or you can use a VM).
* Juju and [Microk8s](https://juju.is/docs/olm/microk8s) installed. We’ll also want to make sure the ingress add-on is enabled, which we can do by running `microk8s enable ingress`.

## Steps

### Set up environment

To easily clean up the resources and separate your workload from the contents of this tutorial, set up a new Juju model named `discourse`:

```
juju add-model discourse
```

### Deploy the charms

Discourse requires connections to PostgreSQL and Redis. For more information, see the [Charm Architecture](https://charmhub.io/discourse-k8s/docs/charm-architecture).

> NOTE: Discourse requires PostgreSQL extensions to be available in the relation.

Deploy the charms:
```
juju deploy redis-k8s --channel latest/edge
juju deploy postgresql-k8s --channel 14/stable --trust
juju deploy discourse-k8s
```

Enable the required PostgreSQL extensions:
```
juju config postgresql-k8s plugin_hstore_enable=True
juju config postgresql-k8s plugin_pg_trgm_enable=True
```

### Integrate the charms

Integrate `redis-k8s` and `postgresql-k8s` to `discourse-k8s`:
```
juju integrate redis-k8s discourse-k8s
juju integrate discourse-k8s postgresql-k8s
```

By running `juju status --relations` the current state of the deployment can be queried:
```
Model      Controller  Cloud/Region        Version  SLA          Timestamp
discourse  microk8s    microk8s/localhost  3.1.7    unsupported  12:48:02+02:00

App             Version  Status  Scale  Charm           Channel      Rev  Address         Exposed  Message
discourse-k8s   3.2.0    active      1  discourse-k8s   stable        95  10.152.183.175  no       
postgresql-k8s  14.10    active      1  postgresql-k8s  14/stable    193  10.152.183.59   no       
redis-k8s       7.0.4    active      1  redis-k8s       latest/edge   27  10.152.183.46   no       

Unit               Workload  Agent  Address      Ports  Message
discourse-k8s/0*   active    idle   10.1.44.214         
postgresql-k8s/0*  active    idle   10.1.44.219         
redis-k8s/0*       active    idle   10.1.44.227         

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

Run `kubectl get pods -n discourse` to see the pods that are being created by the charms:
```
NAME                             READY   STATUS    RESTARTS   AGE
modeloperator-64c58d675d-csj47   1/1     Running   0          5m30s
redis-k8s-0                      3/3     Running   0          5m22s
discourse-k8s-0                  2/2     Running   0          5m1s
postgresql-k8s-0                 2/2     Running   0          5m9s
```

### Provide ingress capabilities 

In order to expose the charm, the Nginx Ingress Integrator needs to be deployed and integrated with Discourse:

```
juju deploy nginx-ingress-integrator
# If your cluster has RBAC enabled you'll be prompted to run the following:
juju trust nginx-ingress-integrator --scope=cluster

juju integrate discourse-k8s nginx-ingress-integrator
```

### Create an admin user and log in

To create an admin user, use the `create-user` action:
```
juju run discourse-k8s/0 create-user admin=true email=email@example.com
```
The command will return the password of the created user. Discourse will be deployed with `discourse-k8s` as default hostname. In order to reach it, modify your `/etc/hosts` file so that it points to `127.0.0.1`:

```
echo 127.0.0.1 discourse-k8s >> /etc/hosts
```

After that, visit `http://discourse-k8s` to reach Discourse, using the credentials returned from the `create-user` action to login.

### Clean up the environment 

Congratulations! You have successfully finished the Discourse tutorial. You can now remove the 
model environment that you've created using the following command:

```
juju destroy-model discourse --destroy-storage
```