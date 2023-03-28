# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Module for test customizations."""


def pytest_addoption(parser):
    """Adds parser switches."""
    parser.addoption("--discourse-image", action="store")
    parser.addoption("--localstack-address", action="store")
    parser.addoption("--saml-email", action="store")
    parser.addoption("--saml-password", action="store")
