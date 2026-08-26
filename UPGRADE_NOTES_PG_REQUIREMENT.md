# Discourse v2026.7.1 Upgrade: PostgreSQL 15 Requirement

## Decision: PostgreSQL 15+ Required

This upgrade supports **PostgreSQL 15 and later only**. PG14 is not supported.

### Rationale

- **Discourse official requirement:** Discourse v2026+ explicitly requires PostgreSQL 15+ (see README.md)
- **Upstream alignment:** We align with official Discourse requirements rather than maintaining local compatibility layers
- **Sustainability:** Patching around unsupported versions creates technical debt for every future upgrade
- **Fresh deployments:** Discourse v2026 uses PG15-only syntax (NULLS NOT DISTINCT) that fails on fresh PG14 deployments

### Migration Path for Existing PG14 Deployments

1. **Planning phase:** Notify teams of PG14→PG15 migration requirement
2. **Pre-upgrade:** Backup PG14 database
3. **Migration:** Follow PostgreSQL official upgrade guide (typically 2-4 hours)
4. **Charm deployment:** Deploy new charm version with v2026.7.1 (30 min)
5. **Validation:** Verify Discourse starts and SAML auth works

### Timeline

- **Deadline:** Before October 2026 (end of v2026.1 support lifecycle)
- **Recommendation:** Complete PG14→PG15 migrations by September 2026

### Why Not Patch for PG14 Support?

We evaluated local compatibility patches (version-aware index recreation), but decided against:

1. **Upstream doesn't support PG14** — we'd be maintaining unsupported territory
2. **Fragile solution** — only addresses one specific feature; if Discourse v2026.8+ adds other PG15-only features, we patch again
3. **Maintenance burden** — every version bump requires re-validation
4. **Better alternatives exist** — PG15 migration is straightforward and planned

This decision aligns with best practices: migrate to supported versions rather than patch around upstream requirements.

### Documentation

See session files for:
- PATCH-DECISION-AND-PG-REQUIREMENT.md — Full analysis
- PATCH-LIFECYCLE-AND-MAINTENANCE.md — Future patch governance

---

**Version:** v2026.7.1 Upgrade  
**Date:** 2026-08-26
