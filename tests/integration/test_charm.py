#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from typing import Dict, Optional
from urllib.parse import urlencode, urlparse

import pytest
import requests
from boto3 import client
from botocore.config import Config
from bs4 import BeautifulSoup
from ops.model import ActiveStatus, Application
from pytest_operator.plugin import OpsTest
from requests.adapters import HTTPAdapter, Retry

from charm import PROMETHEUS_PORT, SERVICE_NAME, SERVICE_PORT
from tests.integration.helpers import (
    DBInfo,
    get_db_info,
    get_discourse_email_token,
    get_unit_address,
)

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_active(app: Application):
    """Check that the charm is active.
    Assume that the charm has already been built and is running.
    """
    # Application actually does have units
    # Mypy has difficulty with ActiveStatus
    assert app.units[0].workload_status == ActiveStatus.name  # type: ignore


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_discourse_up(ops_test: OpsTest, app: Application, requests_timeout: float):
    """Check that the bootstrap page is reachable.
    Assume that the charm has already been built and is running.
    """

    address = await get_unit_address(ops_test, app.name)
    # Send request to bootstrap page and set Host header to app_name (which the application
    # expects)
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1)
    session.mount("http://", HTTPAdapter(max_retries=retries))
    response = session.get(
        f"http://{address}:{SERVICE_PORT}/finish-installation/register",
        timeout=requests_timeout,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_prom_exporter_is_up(app: Application):
    """
    arrange: given charm in its initial state
    act: when the metrics endpoint is scraped
    assert: the response is 200 (HTTP OK)
    """
    # Application actually does have units
    indico_unit = app.units[0]  # type: ignore
    cmd = f"curl http://localhost:{PROMETHEUS_PORT}/metrics"
    action = await indico_unit.run(cmd)
    result = await action.wait()
    code = result.results.get("return-code")
    stdout = result.results.get("stdout")
    stderr = result.results.get("stderr")
    assert code == 0, f"{cmd} failed ({code}): {stderr or stdout}"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_setup_discourse(
    ops_test: OpsTest, app: Application, app_config: Dict[str, str], requests_timeout: float
):
    """Check discourse if working properly by registrating an Admin and generates an API
    Note that the API is later used to manipulate Discourse
    """

    discourse_address = await get_unit_address(ops_test, app.name)
    discourse_url = f"http://{discourse_address}:{SERVICE_PORT}"
    session = requests.session()

    logger.info("Getting registration page")

    # Send request to bootstrap page and set Host header to app_name (which the application
    # expects)
    response = session.get(
        f"{discourse_url}/finish-installation/register",
        headers={"Host": f"{app_config['external_hostname']}"},
        timeout=requests_timeout,
    )

    assert response.status_code == 200

    # Parse output and send registration form
    parsed_registration: BeautifulSoup = BeautifulSoup(response.content, features="html.parser")

    # Get the form info
    assert parsed_registration.body
    utf8 = parsed_registration.body.find("input", attrs={"name": "utf8"}).get("value")  # type: ignore
    authenticity_token = parsed_registration.body.find("input", attrs={"name": "authenticity_token"}).get("value")  # type: ignore
    form_fields = {
        "utf8": utf8,
        "authenticity_token": authenticity_token,
        "username": "admin",
        "email": app_config["developer_emails"],
        "password": "MyLovelySecurePassword2022!",
    }

    form_headers = {
        "Host": f"{app_config['external_hostname']}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    logger.info("Submitting registration form")

    response = session.post(
        f"{discourse_url}/finish-installation/register",
        headers=form_headers,
        data=urlencode(form_fields),
        allow_redirects=False,
        timeout=requests_timeout,
    )

    # Replies with a redirect
    assert response.status_code == 302

    # Fecth the email token from DB
    postgresql_info: Optional[DBInfo] = await get_db_info(app, SERVICE_NAME)
    assert postgresql_info is not None
    email_token = await get_discourse_email_token(postgresql_info, app_config["developer_emails"])
    assert email_token is not None

    # Confirm email with token
    session.cookies.clear()

    logger.info("Getting account activation page")

    response = session.get(
        f"{discourse_url}/u/activate-account/{email_token}",
        headers={"Host": f"{app_config['external_hostname']}"},
        timeout=requests_timeout,
    )

    assert response.status_code == 200

    # Parse the response to get the authenticity_token
    parsed_validation: BeautifulSoup = BeautifulSoup(response.content, features="html.parser")

    logger.info("Getting challenge for account activation form")

    # There's a challenge to get through an Ajax request to submit the activation
    response = session.get(
        f"{discourse_url}/session/hp",
        headers={
            "Host": f"{app_config['external_hostname']}",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=requests_timeout,
    )

    assert response.status_code == 200
    parsed_challenge = response.json()

    assert parsed_validation.body
    authenticity_token = parsed_validation.body.find("input", attrs={"name": "authenticity_token"}).get("value")  # type: ignore
    form_fields = {
        "_method": "put",
        "authenticity_token": authenticity_token,
        "password_confirmation": parsed_challenge["value"],
        # The challenge string is reversed see
        # https://github.com/discourse/discourse/blob/main/app/assets/javascripts/discourse/scripts/activate-account.js
        "challenge": parsed_challenge["challenge"][::-1],
    }

    logger.info("Submitting account validation form")

    # Submit the activation of the account
    response = session.post(
        f"{discourse_url}/u/activate-account/{email_token}",
        headers=form_headers,
        data=urlencode(form_fields),
        allow_redirects=False,
        timeout=requests_timeout,
    )

    assert response.status_code == 302

    logger.info("Getting admin page")

    # Load Admin page
    response = session.get(
        f"{discourse_url}/admin/",
        headers={
            "Host": f"{app_config['external_hostname']}",
            # Without the user-agent, the server answer doesn't contain csrf
            "User-Agent": "AppleWebKit/537.36",
        },
        timeout=requests_timeout,
    )

    # Extract the CSRF token
    parsed_admin: BeautifulSoup = BeautifulSoup(response.content, features="html.parser")
    assert parsed_admin.head
    csrf_token = parsed_admin.head.find("meta", attrs={"name": "csrf-token"}).get("content")  # type: ignore

    logger.info("Getting admin API key")

    # Finally create an API Key, which will be used on the next integration tests
    api_key_payload = {"key": {"description": "Key to The Batmobile", "username": "admin"}}

    response = session.post(
        f"{discourse_url}/admin/api/keys",
        headers={
            "Host": f"{app_config['external_hostname']}",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": csrf_token,  # type: ignore
            "Content-Type": "application/json",
        },
        data=json.dumps(api_key_payload),
        timeout=requests_timeout,
    )

    assert response.status_code == 200

    parsed_key = response.json()
    logger.info("Admin API Key: %s", {parsed_key["key"]["key"]})
