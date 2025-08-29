# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Charm Workflow - Generic logic, managed centrally.
# ==============================================================================

CHARM_VERSION 			?= $(shell git describe --tags --always --dirty)
CHARM_PLATFORM 			?= amd64
# The index of the base in charmcraft.yaml to build
CHARM_BASE_INDEX 		?= 0

CHARM_STATIC_ARTIFACT 	:= $(CHARM_NAME)_$(CHARM_PLATFORM).charm

CHARMCRAFT_PACK_CMD 	:= charmcraft pack --base-index=$(CHARM_BASE_INDEX)
HAS_YQ := $(shell command -v yq)

ifneq ($(HAS_YQ),)
    # Read the specified 'run-on' base from charmcraft.yaml to correctly predict the filename.
    CHARM_BASE_NAME 	:= $(shell yq ".bases[$(CHARM_BASE_INDEX)].run-on[0].name" charmcraft.yaml)
    CHARM_BASE_CHANNEL 	:= $(shell yq ".bases[$(CHARM_BASE_INDEX)].run-on[0].channel" charmcraft.yaml)
    CHARM_BASE_STRING 	:= $(CHARM_BASE_NAME)-$(CHARM_BASE_CHANNEL)
	JUJU_DEPLOY_BASE 	:= $(shell echo $(CHARM_BASE_STRING) | sed 's/-/@/')
else
    $(call errmsg,"yq not found, cannot determine charm base. Filename may be incorrect.")
endif

CHARM_STATIC_ARTIFACT 	:= $(CHARM_NAME)_$(CHARM_BASE_STRING)_$(CHARM_PLATFORM).charm
CHARM_DYNAMIC_ARTIFACT 	:= $(CHARM_NAME)_$(CHARM_VERSION)_$(CHARM_BASE_STRING)_$(CHARM_PLATFORM).charm

##@ Charm
.PHONY: build-charm deploy-charm clean-charm	

build-charm: $(CHARM_DYNAMIC_ARTIFACT) ## Build the charm if it's out of date.

$(CHARM_DYNAMIC_ARTIFACT):
	$(call msg,"--> Building Charm artifact: $(CHARM_DYNAMIC_ARTIFACT)...")
	@echo "$(CHARM_VERSION)" > version
	@$(CHARMCRAFT_PACK_CMD)
	@rm -f version
	@mv $(CHARM_STATIC_ARTIFACT) $(CHARM_DYNAMIC_ARTIFACT)

deploy-charm: $(CHARM_DYNAMIC_ARTIFACT) publish-rock setup-juju-model ## Build & publish artifacts, then deploy.
	$(call msg,"--> Deploying Charm: $(CHARM_NAME) with ROCK resource: $(ROCK_IMAGE)")
	@juju deploy -m $(JUJU_MODEL_NAME) ./$(CHARM_DYNAMIC_ARTIFACT) --resource $(OCI_RESOURCE_NAME)=$(ROCK_IMAGE)

clean-charm: ## Remove charm artifacts.
	$(call msg,"--> Cleaning charm artifacts...")
	@rm -f *.charm $(CHARM_OVERRIDE_FILE)
