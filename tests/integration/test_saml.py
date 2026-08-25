#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging
import time
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, urlunsplit

import jubilant
import pytest
import requests
import urllib3.exceptions

from . import types

logger = logging.getLogger(__name__)


def _set_session_cookie_from_response(
    session: requests.Session, response: requests.Response
) -> None:
    """Persist response cookies in manual Cookie header for host-mapped test traffic."""
    cookie_header = response.headers.get("set-cookie")
    if not cookie_header:
        return
    parsed_cookie = SimpleCookie()
    parsed_cookie.load(cookie_header)
    existing_cookie_header = session.headers.get("Cookie", "")
    merged_cookie = SimpleCookie()
    if existing_cookie_header:
        merged_cookie.load(existing_cookie_header)
    for name, morsel in parsed_cookie.items():
        merged_cookie[name] = morsel.value
    session.headers["Cookie"] = "; ".join(
        f"{name}={morsel.value}" for name, morsel in merged_cookie.items()
    )


@pytest.mark.abort_on_fail
def test_saml_login(  # pylint: disable=too-many-locals
    juju: jubilant.Juju,
    app: types.App,
    discourse_address: str,
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

    try:
        task = juju.run(app.name + "/0", "create-user", {"email": email})
        assert "user" in task.results
    except Exception as error:
        assert "already exists" in str(error)

    host = app.name
    parsed_address = urlsplit(discourse_address)
    session = requests.session()
    session.headers.update(
        {
            "Host": host,
            "X-Forwarded-Proto": "https",
            "Origin": f"https://{host}",
            "Referer": f"https://{host}/",
        }
    )

    response = None
    last_error = None
    for _ in range(90):
        try:
            response = session.get(
                f"{discourse_address}/auth/saml/metadata",
                timeout=10,
                verify=False,
            )
            if response.ok:
                break
        except requests.RequestException as error:
            last_error = error
        time.sleep(2)
    assert response is not None, (
        f"Failed to reach {discourse_address}/auth/saml/metadata: {last_error}"
    )
    assert response.ok, response.text
    saml_helper.register_service_provider(name=host, metadata=response.text)

    preference_page = session.get(
        f"{discourse_address}/u/{username}/preferences/account",
        timeout=requests_timeout,
        verify=False,
    )
    assert preference_page.status_code == 404

    session.get(discourse_address, timeout=requests_timeout, verify=False)
    redirect_response = None
    for _ in range(30):
        response = session.get(
            f"{discourse_address}/session/csrf",
            headers={"Accept": "application/json"},
            timeout=requests_timeout,
            verify=False,
        )
        _set_session_cookie_from_response(session, response)
        csrf_token = response.json()["csrf"]
        redirect_response = session.post(
            f"{discourse_address}/auth/saml",
            headers={
                "X-CSRF-Token": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
            },
            data={"authenticity_token": csrf_token},
            timeout=requests_timeout,
            allow_redirects=False,
            verify=False,
        )
        _set_session_cookie_from_response(session, redirect_response)
        if redirect_response.status_code == 302:
            break
        time.sleep(2)
    assert redirect_response is not None
    assert redirect_response.status_code == 302, redirect_response.text
    redirect_url = redirect_response.headers["Location"]
    saml_response = saml_helper.redirect_sso_login(
        redirect_url, username=username, password=password
    )
    assert host in saml_response.url
    callback_url = urlsplit(saml_response.url)
    callback_endpoint = urlunsplit(
        (
            parsed_address.scheme,
            parsed_address.netloc,
            callback_url.path,
            callback_url.query,
            callback_url.fragment,
        )
    )
    first_callback_response = session.post(
        callback_endpoint,
        data={"SAMLResponse": saml_response.data["SAMLResponse"], "SameSite": "1"},
        verify=False,
        timeout=requests_timeout,
        allow_redirects=False,
    )
    _set_session_cookie_from_response(session, first_callback_response)
    second_callback_response = session.post(
        callback_endpoint,
        data=saml_response.data,
        verify=False,
        timeout=requests_timeout,
        allow_redirects=False,
    )
    _set_session_cookie_from_response(session, second_callback_response)

    preference_page = session.get(
        f"{discourse_address}/u/{username}/preferences/account",
        timeout=requests_timeout,
        verify=False,
    )
    assert preference_page.status_code == 200
