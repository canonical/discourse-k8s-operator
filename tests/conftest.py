# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Module for test customizations."""


def pytest_addoption(parser):
    """Adds parser switches."""
    parser.addoption("--discourse-image", action="store")
    parser.addoption("--localstack-address", action="store")
    parser.addoption("--saml-email", action="store")
    parser.addoption("--saml-password", action="store")
    parser.addoption("--charm-file", action="store", default=None)
    parser.addoption(
        "--use-existing",
        action="store_true",
        default=False,
        help="This will skip deployment of the charms. Useful for local testing.",
    )
