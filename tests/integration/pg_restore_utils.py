# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Utilities for retry behavior in migration fixture restore."""


def is_retryable_pg_restore_error(stderr: str) -> bool:
    """Return True when pg_restore failed due to transient DB availability errors."""
    retryable_fragments = (
        "terminating connection due to administrator command",
        "no connection to the server",
        "Connection refused",
    )
    return any(fragment in stderr for fragment in retryable_fragments)
