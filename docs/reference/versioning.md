# Versioning

## Discourse Charm Versioning Strategy

The Discourse charm has transitioned from semantic versioning to calendar-based versioning to align with the upstream Discourse project's new versioning strategy.

### Historical versioning (semantic versioning)

**Last Release:** [Revision 227](https://github.com/canonical/discourse-k8s-operator/releases/tag/rev227) - Version 3.5.3

The Discourse charm previously followed semantic versioning (SemVer) format `MAJOR.MINOR.PATCH`, with the final release using this format being version 3.5.3 published as revision 227.

### Current versioning (calendar-based)

**New Format:** `YYYY.MM.PATCH-BRANCH`

Starting with releases after revision 227, the Discourse charm follows the new calendar-based versioning strategy adopted by the upstream Discourse project. This format includes:

- **YYYY**: Year (e.g., 2025)
- **MM**: Month (e.g., 12 for December)
- **PATCH**: Patch version for the month
- **BRANCH**: Branch identifier (e.g., `latest`, `beta`)

**Example:** `2025.12.0-latest`

The Discourse charm will track the `-latest` branch of the upstream Discourse releases, providing the most current stable version within each monthly release cycle.

## Reference

For more information about the new versioning strategy, see the [RFC: A new versioning strategy for Discourse](https://meta.discourse.org/t/rfc-a-new-versioning-strategy-for-discourse/383536).
