# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Documentation specific logic
# ==============================================================================

##@ Documentation
.PHONY: docs-check docs-clean vale-sync vale lychee vale-clean


# Vale settings
VALE_DIR 			?= .vale
PRAECEPTA_CONFIG 	?= .vale.ini
DOCS_FILES 			?= docs/ README.md CONTRIBUTING.md

HAS_VALE			:= $(shell command -v vale;)
HAS_LYCHEE			:= $(shell command -v lychee;)

# ==============================================================================
# Docs Targets
# ==============================================================================

docs-check: vale lychee ## Run all documentation checks (vale and lychee).

docs-clean: vale-clean ## Clean documentation-related artifacts.

# ==============================================================================
# Dependency Check Targets
# ==============================================================================

.PHONY: .check-vale
.check-vale:
ifndef HAS_VALE
	$(call errmsg,'vale' is not installed. Please install it first) \
	exit 1;
endif

.PHONY: .check-lychee
.check-lychee:
ifndef HAS_LYCHEE
	$(call errmsg,'lychee' is not installed. Please install it first) \
	exit 1;
endif


# ==============================================================================
# Main Vale Targets
# ==============================================================================

vale-sync: ## Download and install external Vale configuration sources
	$(call msg,--- Syncing Vale styles... ---)
	@vale sync

vale: .check-vale vale-sync ## Run Vale checks on docs
	$(call msg,--- Running Vale checks on "$(DOCS_FILES)"... ---)
	@vale --config=$(PRAECEPTA_CONFIG) $(DOCS_FILES)

# ==============================================================================
# Main Lychee Targets
# ==============================================================================

lychee: .check-lychee ## Run Lychee checks on docs
	$(call msg,--- Running lychee checks on "$(LYCHEE_DOCS_FILES)"... ---)
	@lychee $(DOCS_FILES)

# ==============================================================================
# Helper Targets
# ==============================================================================

vale-clean: ## Clean documentation-related artifacts.
	$(call msg,--- Cleaning downloaded packages and ignored files from "$(VALE_DIR)"... ---)
	@git clean -dfX $(VALE_DIR)
