#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging
import socket
import unittest.mock

import jubilant
import pytest
import requests
import urllib3.exceptions

from . import types

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_saml_login(  # pylint: disable=too-many-locals
    juju: jubilant.Juju,
    app: types.App,
    requests_timeout: int,
    setup_saml_config,
):
    """
    arrange: after discourse charm has been deployed, with all required relation established.
    act: add an admin user and enable force-https mode.
    assert: user can login discourse using SAML Authentication.
    """
    saml_helper = setup_saml_config
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # discourse need a long password and a valid email
    # username can't be "discourse" or it will be renamed
    username = "ubuntu"
    email = "ubuntu@canonical.com"
    password = "test-discourse-k8s-password"  # nosecue
    saml_helper.register_user(username=username, email=email, password=password)

    task = juju.run(app.name + "/0", "create-user", {"email": email})
    assert "user" in task.results

    host = app.name
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(*args):
        if args[0] == host:
            return original_getaddrinfo("127.0.0.1", *args[1:])
        return original_getaddrinfo(*args)

    with unittest.mock.patch.multiple(socket, getaddrinfo=patched_getaddrinfo):
        session = requests.session()

        response = session.get(
            f"https://{host}/auth/saml/metadata",
            verify=False,
            timeout=10,
        )
        saml_helper.register_service_provider(name=host, metadata=response.text)

        preference_page = session.get(
            f"https://{host}/u/{username}/preferences/account",
            verify=False,
            timeout=requests_timeout,
        )
        assert preference_page.status_code == 404

        session.get(f"https://{host}", verify=False)
        response = session.get(
            f"https://{host}/session/csrf",
            verify=False,
            headers={"Accept": "application/json"},
            timeout=requests_timeout,
        )
        csrf_token = response.json()["csrf"]
        redirect_response = session.post(
            f"https://{host}/auth/saml",
            data={"authenticity_token": csrf_token},
            verify=False,
            timeout=requests_timeout,
            allow_redirects=False,
        )
        assert redirect_response.status_code == 302
        redirect_url = redirect_response.headers["Location"]
        saml_response = saml_helper.redirect_sso_login(
            redirect_url, username=username, password=password
        )
        assert f"https://{host}" in saml_response.url
        session.post(
            saml_response.url,
            verify=False,
            data={"SAMLResponse": saml_response.data["SAMLResponse"], "SameSite": "1"},
        )
        session.post(saml_response.url, verify=False, data=saml_response.data)

        preference_page = session.get(
            f"https://{host}/u/{username}/preferences/account",
            verify=False,
            timeout=requests_timeout,
        )
        assert preference_page.status_code == 200
