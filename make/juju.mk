# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Juju Environment Workflow - Generic logic, managed centrally.
# ==============================================================================

# --- Default Variable Definitions ---
# These can be overridden in the root Makefile or from the command line.
JUJU_MODEL_NAME ?= charm-dev
JUJU_LOGGING_CONFIG ?= "<root>=INFO;unit=DEBUG"

##@ Juju
.PHONY: setup-juju-model check-microk8s-registry

setup-juju-model: ## Create and configure the Juju model for development.
	$(call msg,"--> Setting up Juju model: $(JUJU_MODEL_NAME)...")
	@juju models | grep -q "^$(JUJU_MODEL_NAME) " || juju add-model $(JUJU_MODEL_NAME)
	@juju model-config -m $(JUJU_MODEL_NAME) logging-config=$(JUJU_LOGGING_CONFIG)

check-microk8s-registry: ## Check if the MicroK8s registry addon is enabled.
	@command -v microk8s >/dev/null || \
		( $(call errmsg, "microk8s command not found. Is MicroK8s installed and in your PATH?") )
	@microk8s status --wait-ready | grep "registry: enabled" > /dev/null || \
		( $(call errmsg, "MicroK8s registry is not enabled. Please run 'microk8s enable registry'.") )
