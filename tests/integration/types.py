# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Useful types for integration tests."""

from typing import NamedTuple


class Credentials(NamedTuple):
    """Credentials to login to an application.

    Attrs:
        email: The contact information to use to login.
        username: The identification to use to login.
        password: The secret to use to login.
    """

    email: str
    username: str
    password: str
