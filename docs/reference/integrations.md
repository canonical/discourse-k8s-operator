# Integrations

### db

_Interface_: pgsql

_Supported charms_: [postgresql-k8s](https://charmhub.io/postgresql-k8s),
[postgresql](https://charmhub.io/postgresql)

Database integration is a required relation for the Discourse charm to supply
structured data storage for Discourse.

Database integrate command: 
```
juju integrate discourse-k8s postgresql-k8s
```

### grafana-dashboard

_Interface_: grafana-dashboard

_Supported charms_: [grafana-k8s](https://charmhub.io/grafana-k8s)

Grafana-dashboard relation enables quick dashboard access already tailored to
fit the needs of operators to monitor the charm. The template for the Grafana
dashboard for Discourse charm can be found at `/src/grafana_dashboards/discourse.json`.
In Grafana UI, it can be found as “Discourse Operator” under the General section of the dashboard browser
(`/dashboards`). Modifications to the dashboard can be made but will not be
persisted upon restart/redeployment of the charm.

Grafana-Prometheus integrate command:
```
juju integrate grafana-k8s:grafana-source prometheus-k8s:grafana-source
```
Grafana-dashboard integrate command:
```
juju integrate discourse-k8s grafana-dashboard`
```

### ingress

_Interface_: ingress

_Supported charms_: [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator),
[traefik](https://charmhub.io/traefik-k8s)

Ingress manages external http/https access to services in a kubernetes cluster.
Note that the kubernetes cluster must already have an nginx ingress controller
already deployed. Documentation to enable ingress in MicroK8s can be found in
[Addon: Ingress](https://microk8s.io/docs/addon-ingress).

Ingress integrate command: 
```
juju integrate discourse-k8s nginx-ingress-integrator
```

### metrics-endpoint

_Interface_: [prometheus_scrape](https://charmhub.io/interfaces/prometheus_scrape-v0)

_Supported charms_: [prometheus-k8s](https://charmhub.io/prometheus-k8s)

Metrics-endpoint relation allows scraping the `/metrics` endpoint provided by Discourse.
The metrics are exposed in the [open metrics format](https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#data-model) and will only be scraped by Prometheus once the
relation becomes active. For more information about the metrics exposed, refer to ["How to monitor Discourse metrics using Prometheus"](https://meta.discourse.org/t/discourse-prometheus/72666).

Metrics-endpoint integrate command: 
```
juju integrate discourse-k8s prometheus-k8s
```

### redis

_Interface_: redis  

_Supported charms_: [redis-k8s](https://charmhub.io/redis-k8s)

Discourse uses Redis to run background tasks (with Sidekiq) and keep the application fast and responsive. It enables real-time updates on the pages and helps in managing data efficiently. Redis also helps Discourse in balancing loads by managing rate limits, making it a crucial part of its system.

Redis integrate commands: 
```
juju integrate discourse-k8s redis-k8s
```