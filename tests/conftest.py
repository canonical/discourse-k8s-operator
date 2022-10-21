# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.


def pytest_addoption(parser):
    parser.addoption("--discourse-image", action="store")
    parser.addoption("--s3-ip-address", action="store")
