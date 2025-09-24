# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Project: Discourse K8s Operator
# This file contains ONLY project-specific configuration.
# ==============================================================================

# Names for this specific charm and its artifacts
CHARM_NAME 			:= discourse-k8s
ROCK_NAME 			:= discourse
OCI_RESOURCE_NAME 	:= discourse-image

ROCK_DIR 			?= discourse_rock

# ==============================================================================
# Makefile common logic
# ==============================================================================

MAKE_DIR := make
include $(MAKE_DIR)/common.mk
