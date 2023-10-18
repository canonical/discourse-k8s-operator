# How to configure the hostname

### Prerequisites

Deploy and relate [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator) charm.

```
juju deploy nginx-ingress-integrator
juju trust nginx-ingress-integrator --scope cluster # if RBAC is enabled
juju relate discourse-k8s nginx-ingress-integrator
```

### Configure hostname

This charm exposes the `external_hostname` configuration option to specify the external hostname of the application.

To configure a different hostname for Discourse, you can configure the ingress hostname through the
discourse-k8s configuration.

```
juju config discourse-k8s external_hostname=<desired-hostname>
```

The output of `juju status` should look similar to the following:

```
Model           Controller  Cloud/Region        Version  SLA          Timestamp
tutorial        mk8s        microk8s/localhost  2.9.44   unsupported  18:19:34-04:00

App                       Version  Status  Scale  Charm                     Channel        Rev  Address         Exposed  Message
discourse-k8s             2.8.14   active      1  discourse-k8s                             41  <discourse-ip>  no
nginx-ingress-integrator  25.3.0   active      1  nginx-ingress-integrator  latest/stable   81  <ingress-ip>    no       Ingress IP(s): 127.0.0.1, Service IP(s): <ingress-svc-ip>
postgresql-k8s            14.9     active      1  postgresql-k8s            14/edge        145  <postgres-ip>   no       Primary
redis-k8s                 7.0.4    active      1  redis-k8s                 latest/edge     26  <redis-ip>      no

Unit                         Workload  Agent  Address           Ports   Message
discourse-k8s/0*             active    idle   <discourse-ip>
nginx-ingress-integrator/0*  active    idle   <ingress-ip>              Ingress IP(s): 127.0.0.1, Service IP(s): <ingress-svc-ip>
postgresql-k8s/0*            active    idle   <postgres-ip>             Primary
redis-k8s/0*                 active    idle   <redis-ip>    
```

Note the Service IP(s): next to nginx-ingress-integrator charm’s Status output.

Test the ingress by sending a GET request to the service with `Host` headers.

```
curl -H "Host: <desired-hostname>" http://<ingress-svc-ip>
```