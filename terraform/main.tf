# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "discourse_k8s" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "discourse-k8s"
    channel  = var.channel
    revision = var.revision
  }

  config      = var.config
  constraints = var.constraints
  units       = var.units
}
