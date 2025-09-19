# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Common Makefile - Generic logic, managed centrally.
# ==============================================================================

# --- Includes ---
# Include all the modular workflow files.
include $(MAKE_DIR)/help.mk
include $(MAKE_DIR)/rock.mk
include $(MAKE_DIR)/charm.mk
include $(MAKE_DIR)/juju.mk
include $(MAKE_DIR)/tox.mk
include $(MAKE_DIR)/docs.mk

# Default target when 'make' is called without arguments.
all: help

.PHONY: all build publish deploy clean test lint unit integration docs

##@ General
build: build-rock build-charm         		## Build all artifacts (ROCK and Charm).
publish: publish-rock                 		## Publish all artifacts.
deploy: deploy-charm                  		## Deploy the charm for local testing.
clean: clean-rock clean-charm clean-docs    ## Clean up all build artifacts.
test: tox-unit								## Run unit tests.
lint: tox-lint docs-check					## Run all linters and documentation checks.	
unit: tox-unit                    			## Run unit tests.
integration: tox-integration          		## Deploy the charm, then run integration tests.


