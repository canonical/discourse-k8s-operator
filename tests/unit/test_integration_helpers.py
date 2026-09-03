#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Unit tests for integration helper behavior."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_pg_restore_utils_module():
    module_path = Path(__file__).resolve().parents[1] / "integration" / "pg_restore_utils.py"
    spec = spec_from_file_location("pg_restore_utils", module_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pg_restore_retryable_on_connection_refused() -> None:
    """pg_restore connection-refused failures should be retried."""
    module = _load_pg_restore_utils_module()
    stderr = (
        'pg_restore: error: connection to server at "localhost" (::1), port 5432 failed: '
        "Connection refused"
    )
    assert module.is_retryable_pg_restore_error(stderr)


def test_pg_restore_not_retryable_on_unrelated_error() -> None:
    """Non-transient pg_restore errors should not be retried."""
    module = _load_pg_restore_utils_module()
    stderr = 'pg_restore: error: relation "users" does not exist'
    assert not module.is_retryable_pg_restore_error(stderr)
