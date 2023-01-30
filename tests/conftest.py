"""Module for test customizations."""
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.


def pytest_addoption(parser):
    """Adds parser switches."""
    parser.addoption("--discourse-image", action="store")
    parser.addoption("--s3-url", action="store")
