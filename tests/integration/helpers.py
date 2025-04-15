"""Various helper functions for use in integration tests."""

from collections.abc import Iterable

import jubilant


def all_units_idle(status: jubilant.Status, apps: Iterable[str] | None = None) -> bool:
    """Report whether all unit agents in *status* (or given *apps*) are in "idle" status."""
    if apps is None:
        apps = status.apps.keys()

    for app in apps:
        app_info = status.apps.get(app)
        if app_info is None:
            return False
        for unit_info in app_info.units.values():
            if unit_info.juju_status.current != "idle":
                return False
    return True
