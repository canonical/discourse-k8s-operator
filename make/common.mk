# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Common Makefile - Generic logic, managed centrally.
# ==============================================================================

# Default the charm's version from Git if not set in the root Makefile.
CHARM_VERSION ?= $(shell git describe --tags --always --dirty)

# Default target
all: help

# Include all logical modules
include $(MAKE_DIR)/help.mk
include $(MAKE_DIR)/rock.mk
include $(MAKE_DIR)/charm.mk
include $(MAKE_DIR)/juju.mk
include $(MAKE_DIR)/docs.mk

##@ General
.PHONY: all help build test publish deploy clean

build: build-rock build-charm         ## Build all artifacts (ROCK and Charm).
test: lint unit                       ## Run all static analysis and unit tests.
publish: publish-rock                 ## Publish all artifacts.
deploy: deploy-charm                  ## Deploy the charm for local testing.
clean: clean-rock clean-charm         ## Clean up build artifacts.

##@ Testing
lint:                                 ## Run linters.
	tox -e lint
