# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Help Specific logic
# Contains macros and the self-documenting help target.
# ==============================================================================

# --- Color & Message Macros ---
NO_COLOR=\033[0m
CYAN_COLOR=\033[0;36m
YELLOW_COLOR=\033[0;93m
RED_COLOR=\033[0;91m

msg = @printf '$(CYAN_COLOR)$(1)$(NO_COLOR)\n'
warnmsg = @printf '$(YELLOW_COLOR)Warning: $(1)$(NO_COLOR)\n'
errmsg = @printf '$(RED_COLOR)Error: $(1)$(NO_COLOR)\n' && exit 1


##@ Helpers
.PHONY: help

help: ## Prints all available, documented targets.
	$(call msg,Available targets:)
	@awk ' \
		/^##@/ { \
			sub(/^##@ /, ""); \
			printf "\n  \033[1m%s\033[0m\n", $$0; \
		} \
		/^[a-zA-Z0-9_-]+:.*?##/ { \
			match($$0, /## .*/); \
			comment = substr($$0, RSTART + 3); \
			split($$0, target, ":"); \
			if (target[1] ~ /^[a-zA-Z0-9_-]+$$/ && target[1] != ".PHONY") { \
				printf "    make %-20s $(YELLOW_COLOR)# %s$(NO_COLOR)\n", target[1], comment; \
			} \
		}' $(MAKEFILE_LIST)
