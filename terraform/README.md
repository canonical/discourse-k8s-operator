# Discourse K8s Terraform Module

This is a Terraform module for deploying the [discourse-k8s](https://charmhub.io/discourse-k8s) charm on a Kubernetes Juju model.

## Usage

```hcl
module "discourse_k8s" {
  source     = "git::https://github.com/canonical/discourse-k8s-operator//terraform"
  model_uuid = juju_model.my_model.uuid
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | ~> 1.12 |
| juju | ~> 1.0 |

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| app\_name | Name of the application in the Juju model. | `string` | `"discourse-k8s"` |
| channel | The channel to use when deploying a charm. | `string` | `"latest/stable"` |
| config | Application config. | `map(string)` | `{}` |
| constraints | Juju constraints to apply for this application. | `string` | `""` |
| model\_uuid | Reference to a `juju_model` uuid. | `string` | `""` |
| revision | Revision number of the charm. | `number` | `null` |
| units | Number of units to deploy. | `number` | `1` |

## Outputs

| Name | Description |
|------|-------------|
| app\_name | Name of the deployed application. |
| requires | Map of requires endpoints. |
| provides | Map of provides endpoints. |
| endpoints | Map of all endpoints. |

## Relations

### Requires

- `redis` – Redis interface
- `database` – PostgreSQL client interface
- `nginx-route` – Nginx route interface
- `logging` – Loki push API interface
- `oauth` – OAuth interface
- `saml` – SAML interface

### Provides

- `metrics-endpoint` – Prometheus scrape interface
- `grafana-dashboard` – Grafana dashboard interface
