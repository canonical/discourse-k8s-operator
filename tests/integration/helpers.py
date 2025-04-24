# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Various helper functions for use in integration tests."""

import jubilant


def all_units_idle(status: jubilant.Status, *apps: str) -> bool:
    """Report whether all unit agents in *status* (or given *apps*) are in "idle" status."""
    if not apps:
        apps = tuple(status.apps.keys())

    for app in apps:
        app_info = status.apps.get(app)
        if app_info is None:
            return False
        for unit_info in app_info.units.values():
            if unit_info.juju_status.current != "idle":
                return False
    return True
