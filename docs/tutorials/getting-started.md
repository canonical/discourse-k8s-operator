# Getting started

In this tutorial, we'll walk you through the process of deploying the Discourse charm, relating it to the nginx-ingress-integrator charm, the postgresql-k8s charm and the redis-k8s charm, and inspecting the kubernetes resources created.

## Requirements

You will need:

* A laptop or desktop running Ubuntu (or you can use a VM).
* [Juju and Microk8s](https://juju.is/docs/olm/microk8s) installed. We’ll also want to make sure the ingress add-on is enabled, which we can do by running `microk8s enable ingress`.

## Deploy this charm

Discourse requires connections to PostgreSQL and Redis, so those will be deployed too and related to the Discourse charm. For more information, see the [Charm Architecture](https://charmhub.io/discourse-k8s/docs/charm-architecture).

All the above charms will the deployed in a new model named `discourse`:

```
# Add the model
juju add-model discourse

# Deploy the charms
juju deploy redis-k8s
juju deploy postgresql-k8s --channel latest/stable
juju deploy discourse-k8s

# Relate redis-k8s and postgresql-k8s to discourse-k8s
juju relate redis-k8s discourse-k8s
# For postgresql-k8s the "db" interface needs to be specified as the charm provides more than one
juju relate discourse-k8s postgresql-k8s:db

```

By running `juju status --relations` the current state of the deployment can be queried, with all the charms eventually reaching `Active`state:
```
Model      Controller          Cloud/Region        Version  SLA          Timestamp
discourse  microk8s-localhost  microk8s/localhost  2.9.37   unsupported  10:35:00+01:00

App             Version                       Status  Scale  Charm           Channel  Rev  Address        Exposed  Message
discourse-k8s                                 active      1  discourse-k8s   edge      13  10.152.183.34  no       
postgresql-k8s  res:postgresql-image@8a72e11  active      1  postgresql-k8s  stable    20                 no       Pod configured
redis-k8s       ubuntu/redis@691f315          active      1  redis-k8s       stable     7                 no       

Unit               Workload  Agent  Address      Ports     Message
discourse-k8s/0*   active    idle   10.1.180.82            
postgresql-k8s/0*  active    idle   10.1.180.81  5432/TCP  Pod configured
redis-k8s/0*       active    idle   10.1.180.78  6379/TCP  

Relation provider    Requirer             Interface  Type     Message
postgresql-k8s:db    discourse-k8s:db     pgsql      regular  
postgresql-k8s:peer  postgresql-k8s:peer  peer       peer     
redis-k8s:redis      discourse-k8s:redis  redis      regular  

```

Run `kubectl get pods -n discourse` to see the pods that are being created by the charms:
```
NAME                             READY   STATUS    RESTARTS   AGE
modeloperator-7879f68947-s4q59   1/1     Running   0          10m
postgresql-k8s-operator-0        1/1     Running   0          10m
redis-k8s-operator-0             1/1     Running   0          10m
redis-k8s-0                      1/1     Running   0          10m
postgresql-k8s-0                 1/1     Running   0          10m
discourse-k8s-0                  2/2     Running   0          9m

```

In order to expose the charm, the Nginx Ingress Integrator is to be deployed alongside Discourse to provide ingress capabilities

```
juju deploy nginx-ingress-integrator
# If your cluster has RBAC enabled you'll be prompted to run the following:
juju trust nginx-ingress-integrator --scope=cluster

juju relate discourse-k8s nginx-ingress-integrator
```

Discourse will be deployed with `discourse-k8s` as default hostname. In order to reach it, modify your `/etc/hosts` file so that it points to `127.0.0.1`

`echo 127.0.0.1 discourse-k8s >> /etc/hosts`

After that, visit `http://discourse-k8s` to reach Discourse.

This charm allows you to add a admin user by executing the corresponding action. Instead of interacting with the Discourse UI just run `juju run-action discourse-k8s/0 add-admin-user email=email@example.com password=somepwd --wait` and it will be registered and validated.
