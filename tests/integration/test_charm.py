#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import json
import logging
import re
import socket
import unittest.mock
from typing import Dict, Optional
from urllib.parse import urlencode, urlparse

import pytest
import requests
import urllib3.exceptions
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
    logger.info("Submitting registration form")

    response = session.post(
        f"{discourse_url}/finish-installation/register",
        headers={
            "Host": f"{app_config['external_hostname']}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urlencode(
            {
                "utf8": parsed_registration.body.find(
                    "input", attrs={"name": "utf8"}  # type: ignore
                ).get("value"),
                "authenticity_token": parsed_registration.body.find(
                    "input", attrs={"name": "authenticity_token"}  # type: ignore
                ).get("value"),
                "username": "admin",
                "email": app_config["developer_emails"],
                "password": "MyLovelySecurePassword2022!",
            }
        ),
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

    assert parsed_validation.body
    form_fields = {
        "_method": "put",
        "authenticity_token": parsed_validation.body.find(
            "input", attrs={"name": "authenticity_token"}  # type: ignore
        ).get("value"),
        "password_confirmation": response.json()["value"],
        # The challenge string is reversed see
        # https://github.com/discourse/discourse/blob/main/app/assets/javascripts/discourse/scripts/activate-account.js
        "challenge": response.json()["challenge"][::-1],
    }

    logger.info("Submitting account validation form")

    # Submit the activation of the account
    response = session.post(
        f"{discourse_url}/u/activate-account/{email_token}",
        headers={
            "Host": f"{app_config['external_hostname']}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
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
    csrf_token = parsed_admin.head.find("meta", attrs={"name": "csrf-token"}).get(  # type: ignore
        "content"
    )

    logger.info("Getting admin API key")

    # Finally create an API Key, which will be used on the next integration tests
    response = session.post(
        f"{discourse_url}/admin/api/keys",
        headers={
            "Host": f"{app_config['external_hostname']}",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": csrf_token,  # type: ignore
            "Content-Type": "application/json",
        },
        data=json.dumps({"key": {"description": "Key to The Batmobile", "username": "admin"}}),
        timeout=requests_timeout,
    )

    assert response.status_code == 200

    logger.info("Admin API Key: %s", {response.json()["key"]["key"]})


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_s3_conf(ops_test: OpsTest, app: Application, s3_url: str):
    """Check that the bootstrap page is reachable
    with the charm configured with an S3 target
    Assume that the charm has already been built and is running.
    This test requires a localstack deployed
    """

    s3_conf: Dict = generate_s3_config(s3_url)

    logger.info("Updating discourse hosts")

    # Discourse S3 client uses subdomain bucket routing,
    # I need to inject subdomain in the DNS (not needed if everything runs localhost)
    # Application actually does have units
    action = await app.units[0].run(  # type: ignore
        f'echo "{s3_conf["ip_address"]}  {s3_conf["bucket"]}.{s3_conf["domain"]}" >> /etc/hosts'
    )
    result = await action.wait()
    assert result.results.get("return-code") == 0, "Can't inject S3 IP in Discourse hosts"

    logger.info("Injected bucket subdomain in hosts, configuring settings for discourse")

    # Application does actually have attribute set_config
    await app.set_config(  # type: ignore
        {
            "s3_enabled": "true",
            # The final URL is computed by discourse, we need to pass the main URL
            "s3_endpoint": s3_conf["endpoint"],
            "s3_bucket": s3_conf["bucket"],
            "s3_secret_access_key": s3_conf["credentials"]["secret-key"],
            "s3_access_key_id": s3_conf["credentials"]["access-key"],
            # Default localstack region
            "s3_region": s3_conf["region"],
        }
    )
    assert ops_test.model
    await ops_test.model.wait_for_idle(status="active")

    logger.info("Discourse config updated, checking bucket content")

    # Configuration for boto client
    s3_client_config = Config(
        region_name=s3_conf["region"],
        s3={
            "addressing_style": "virtual",
        },
    )

    # Trick to use when localstack is deployed on another location than locally
    if s3_conf["ip_address"] != "127.0.0.1":
        proxy_definition = {
            "http": s3_url,
        }
        s3_client_config = s3_client_config.merge(
            Config(
                proxies=proxy_definition,
            )
        )

    # Configure the boto client
    s3_client = client(
        "s3",
        s3_conf["region"],
        aws_access_key_id=s3_conf["credentials"]["access-key"],
        aws_secret_access_key=s3_conf["credentials"]["secret-key"],
        endpoint_url=s3_conf["endpoint"],
        use_ssl=False,
        config=s3_client_config,
    )

    # Check the bucket has been created
    response = s3_client.list_buckets()
    bucket_list = [*map(lambda a: a["Name"], response["Buckets"])]

    assert s3_conf["bucket"] in bucket_list

    # Check content has been uploaded in the bucket
    response = s3_client.list_objects(Bucket=s3_conf["bucket"])
    object_count = sum(1 for _ in response["Contents"])

    assert object_count > 0

    # Cleanup
    await app.set_config(  # type: ignore
        {
            "s3_enabled": "false",
            # The final URL is computed by discourse, we need to pass the main URL
            "s3_endpoint": "",
            "s3_bucket": "",
            "s3_secret_access_key": "",
            "s3_access_key_id": "",
            # Default localstack region
            "s3_region": "",
        }
    )
    assert ops_test.model
    await ops_test.model.wait_for_idle(status="active")


def generate_s3_config(s3_url: str) -> Dict:
    """Generate an S3 config for localstack based test."""
    s3_config: Dict = {
        # Localstack doesn't require any specific value there, any random string will work
        "credentials": {"access-key": "my-lovely-key", "secret-key": "this-is-very-secret"},
        # Localstack enforce to use this domain and it resolves to localhost
        "domain": "localhost.localstack.cloud",
        "bucket": "tests",
        "region": "us-east-1",
    }

    # Parse URL to get the IP address and the port, and compose the required variables
    parsed_s3_url = urlparse(s3_url)
    s3_ip_address = parsed_s3_url.hostname
    s3_endpoint = f"{parsed_s3_url.scheme}://{s3_config['domain']}"
    if parsed_s3_url:
        s3_endpoint = f"{s3_endpoint}:{parsed_s3_url.port}"
    s3_config["ip_address"] = s3_ip_address
    s3_config["endpoint"] = s3_endpoint
    return s3_config


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.requires_secrets
@pytest.mark.usefixtures("setup_saml_config")
async def test_saml_login(  # pylint: disable=too-many-locals
    ops_test: OpsTest,
    app: Application,
    pytestconfig: pytest.Config,
    requests_timeout: int,
    run_action,
):
    """
    arrange: after discourse charm has been deployed, with all required relation established.
    act: add an admin user and enable force-https mode.
    assert: user can login discourse using SAML Authentication.
    """
    assert ops_test.model
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    email = pytestconfig.getoption("--saml-email")
    password = pytestconfig.getoption("--saml-password")
    if not (email and password):
        raise RuntimeError(
            "--saml-email and --saml-password arguments are required for running test_saml_login"
        )
    action_result = await run_action(app.name, "add-admin-user", email=email, password=password)
    assert "user" in action_result

    await ops_test.model.wait_for_idle(status="active")

    username = email.split("@")[0]
    host = app.name
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(*args):
        if args[0] == host:
            return original_getaddrinfo("127.0.0.1", *args[1:])
        return original_getaddrinfo(*args)

    with unittest.mock.patch.multiple(socket, getaddrinfo=patched_getaddrinfo):
        session = requests.session()
        preference_page = session.get(
            f"https://{host}/u/{username}/preferences/account",
            verify=False,
            timeout=requests_timeout,
        )
        assert preference_page.status_code == 404

        session.get(f"https://{host}", verify=False)
        response = session.get(
            f"https://{host}/session/csrf",
            headers={"Accept": "application/json"},
            timeout=requests_timeout,
        )
        csrf_token = response.json()["csrf"]
        login_page = session.post(
            f"https://{host}/auth/saml",
            data={"authenticity_token": csrf_token},
            timeout=requests_timeout,
        )
        csrf_token = re.findall(
            "<input type='hidden' name='csrfmiddlewaretoken' value='([^']+)' />", login_page.text
        )[0]
        saml_callback = session.post(
            "https://login.staging.ubuntu.com/+login",
            data={
                "csrfmiddlewaretoken": csrf_token,
                "email": email,
                "user-intentions": "login",
                "password": password,
                "next": "/saml/process",
                "continue": "",
                "openid.usernamesecret": "",
            },
            headers={"Referer": login_page.url},
            timeout=requests_timeout,
        )
        saml_response = re.findall(
            '<input type="hidden" name="SAMLResponse" value="([^"]+)" />', saml_callback.text
        )[0]
        session.post(
            f"https://{host}/auth/saml/callback",
            data={
                "RelayState": "None",
                "SAMLResponse": saml_response,
                "openid.usernamesecret": "",
            },
            verify=False,
            timeout=requests_timeout,
        )
        session.post(
            f"https://{host}/auth/saml/callback",
            data={"SAMLResponse": saml_response, "SameSite": "1"},
            verify=False,
            timeout=requests_timeout,
        )

        preference_page = session.get(
            f"https://{host}/u/{username}/preferences/account",
            verify=False,
            timeout=requests_timeout,
        )
        assert preference_page.status_code == 200
