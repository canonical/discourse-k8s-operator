# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Juju Environment Workflow - Generic logic, managed centrally.
# ==============================================================================

# --- Default Variable Definitions ---
# These can be overridden in the root Makefile or from the command line.
JUJU_MODEL_NAME ?= charm-dev
JUJU_LOGGING_CONFIG ?= "<root>=INFO;unit=DEBUG"

# --- Targets ---

##@ Juju
setup-model: ## Create and configure the Juju model for development.
	$(call msg,"--> Setting up Juju model: $(JUJU_MODEL_NAME)...")
	@juju models | grep -q "^$(JUJU_MODEL_NAME) " || juju add-model $(JUJU_MODEL_NAME)
	@juju model-config -m $(JUJU_MODEL_NAME) logging-config=$(JUJU_LOGGING_CONFIG)
