# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.


def pytest_addoption(parser):
    parser.addoption("--discourse-image", action="store")
    parser.addoption("--s3-url", action="store")
    parser.addoption("--saml-email", action="store")
    parser.addoption("--saml-password", action="store")
