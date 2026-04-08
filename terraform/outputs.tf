# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.discourse_k8s.name
}

output "requires" {
  description = "Map of requires endpoints."
  value = {
    redis       = "redis"
    database    = "database"
    nginx_route = "nginx-route"
    logging     = "logging"
    oauth       = "oauth"
    saml        = "saml"
  }
}

output "provides" {
  description = "Map of provides endpoints."
  value = {
    metrics_endpoint  = "metrics-endpoint"
    grafana_dashboard = "grafana-dashboard"
  }
}

output "endpoints" {
  description = "Map of all endpoints."
  value = {
    metrics_endpoint  = "metrics-endpoint"
    grafana_dashboard = "grafana-dashboard"
    redis             = "redis"
    database          = "database"
    nginx_route       = "nginx-route"
    logging           = "logging"
    oauth             = "oauth"
    saml              = "saml"
  }
}
