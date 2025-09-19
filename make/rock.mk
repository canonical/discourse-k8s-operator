# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# ROCK Workflow - Generic logic, managed centrally.
# ==============================================================================

ROCK_DIR 			?= rock
DOCKER_REGISTRY 	?= localhost:32000

HAS_YQ := $(shell command -v yq)

ifneq ($(HAS_YQ),)
    ROCK_VERSION_BASE := $(shell yq '.version // "1.0"' $(ROCK_DIR)/rockcraft.yaml)
else
    @$(call errmsg,"yq not found, cannot determine rock base. Filename may be incorrect.")
endif

ROCK_PLATFORM ?= amd64

# The OCI image tag is DYNAMIC, including the hash for cache-busting.
ROCK_CONTENT_HASH 	:= $(shell find $(ROCK_DIR) -type f -not -name '*.rock' -print0 | sort -z | xargs -0 cat | sha1sum | cut -c1-7)
ROCK_IMAGE_TAG 		?= $(ROCK_VERSION_BASE)-$(ROCK_CONTENT_HASH)
ROCK_STATIC_ARTIFACT := $(ROCK_NAME)_$(ROCK_VERSION_BASE)_$(ROCK_PLATFORM).rock
ROCK_DYNAMIC_ARTIFACT := $(ROCK_NAME)_$(ROCK_IMAGE_TAG)_$(ROCK_PLATFORM).rock
ROCK_IMAGE 			:= $(DOCKER_REGISTRY)/$(ROCK_NAME):$(ROCK_IMAGE_TAG)

ROCKCRAFT_PACK_CMD 	:= rockcraft pack
SKOPEO_ARGS 		?= --insecure-policy copy --dest-tls-verify=false
SKOPEO_COPY_CMD 	:= skopeo $(SKOPEO_ARGS)

##@ ROCK
.PHONY: build-rock publish-rock clean-rock

build-rock: $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) ## Build the ROCK OCI image.

$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT):
	@$(call msg,"--> Building ROCK artifact: $(ROCK_DYNAMIC_ARTIFACT)...")
	@cd $(ROCK_DIR) && $(ROCKCRAFT_PACK_CMD)
	@mv $(ROCK_DIR)/$(ROCK_STATIC_ARTIFACT) $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT)

publish-rock: $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) check-microk8s-registry ## Push the ROCK OCI image to the registry, if not already present.
	@$(call msg,"--> Publishing ROCK: $(ROCK_IMAGE)")
	@{ \
		if skopeo --insecure-policy inspect --tls-verify=false docker://$(ROCK_IMAGE) >/dev/null 2>&1; then \
			$(call warnmsg, Image $(ROCK_IMAGE) already exists in registry, skipping upload); \
			exit 0; \
		fi; \
		$(SKOPEO_COPY_CMD) oci-archive:$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) docker://$(ROCK_IMAGE); \
	}

publish-rock-force: $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) check-microk8s-registry ## Force push the ROCK OCI image to the registry.
	@$(call msg,"--> Force Publishing ROCK: $(ROCK_IMAGE)")
	microk8s ctr images rm $(ROCK_IMAGE) || true
	$(SKOPEO_COPY_CMD) oci-archive:$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) docker://$(ROCK_IMAGE)

clean-rock: ## Remove ROCK artifacts.
	@$(call msg,"--> Cleaning ROCK artifacts...")
	@rm -f $(ROCK_DIR)/*.rock
