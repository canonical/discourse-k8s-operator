#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import ssl
from typing import Dict, Optional
from urllib.parse import urlencode
from urllib3.poolmanager import PoolManager

import juju.action
import pytest
import requests
from bs4 import BeautifulSoup
from ops.model import ActiveStatus, Application
from pytest_operator.plugin import OpsTest
from requests.adapters import HTTPAdapter, Retry

from charm import (
    DISCOURSE_PATH,
    PROMETHEUS_PORT,
    SERVICE_NAME,
    SERVICE_PORT,
)
from tests.integration.helpers import (
    DBInfo,
    get_db_info,
    get_discourse_email_token,
    get_unit_address,
)

logger = logging.getLogger(__name__)
csrf_token = ""

class Ssl3HttpAdapter(HTTPAdapter):
    """ "Transport adapter" that allows us to use SSLv3."""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_version=ssl.PROTOCOL_SSLv2
        )


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
    discourse_unit = app.units[0]  # type: ignore
    cmd = f"curl http://localhost:{PROMETHEUS_PORT}/metrics"
    action = await discourse_unit.run(cmd)
    result = await action.wait()
    code = result.results.get("return-code")
    stdout = result.results.get("stdout")
    stderr = result.results.get("stderr")
    assert code == 0, f"{cmd} failed ({code}): {stderr or stdout}"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_setup_discourse(
    ops_test: OpsTest,
    app: Application,
    app_config: Dict[str, str],
    requests_timeout: float,
    service_ip: str,
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
        headers={"Host": f"{app_config['external_hostname']}:3000"},
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
        "Host": f"{app_config['external_hostname']}:3000",
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
        headers={"Host": f"{app_config['external_hostname']}:3000"},
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
            "Host": f"{app_config['external_hostname']}:3000",
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
            "Host": f"{app_config['external_hostname']}:3000",
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
            "Host": f"{app_config['external_hostname']}:3000",
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


# @pytest.mark.asyncio
# @pytest.mark.abort_on_fail
# async def test_s3_conf(ops_test: OpsTest, app: Application, s3_url: str):
#     """Check that the bootstrap page is reachable
#     with the charm configured with an S3 target
#     Assume that the charm has already been built and is running.
#     This test requires a localstack deployed
#     """

#     # Localstack doesn't require any specific value there, any random string will work
#     config_s3_bucket = {"access-key": "my-lovely-key", "secret-key": "this-is-very-secret"}

#     # Localstack enforce to use this domain and it resolves to localhost
#     s3_domain = "localhost.localstack.cloud"
#     s3_bucket = "tests"
#     s3_region = "us-east-1"

#     # Parse URL to get the IP address and the port, and compose the required variables
#     parsed_s3_url = urlparse(s3_url)
#     s3_ip_address = parsed_s3_url.hostname
#     s3_endpoint = f"{parsed_s3_url.scheme}://{s3_domain}"
#     if parsed_s3_url:
#         s3_endpoint = f"{s3_endpoint}:{parsed_s3_url.port}"

#     logger.info("Updating discourse hosts")

#     # Discourse S3 client uses subdomain bucket routing,
#     # I need to inject subdomain in the DNS (not needed if everything runs localhost)
#     # Application actually does have units
#     action = await app.units[0].run(  # type: ignore
#         f'echo "{s3_ip_address}  {s3_bucket}.{s3_domain}" >> /etc/hosts'
#     )
#     result = await action.wait()
#     assert result.results.get("return-code") == 0, "Can't inject S3 IP in Discourse hosts"

#     logger.info("Injected bucket subdomain in hosts, configuring settings for discourse")

#     # Application does actually have attribute set_config
#     await app.set_config(  # type: ignore
#         {
#             "s3_enabled": "true",
#             # The final URL is computed by discourse, we need to pass the main URL
#             "s3_endpoint": s3_endpoint,
#             "s3_bucket": s3_bucket,
#             "s3_secret_access_key": config_s3_bucket["secret-key"],
#             "s3_access_key_id": config_s3_bucket["access-key"],
#             # Default localstack region
#             "s3_region": s3_region,
#         }
#     )
#     assert ops_test.model
#     await ops_test.model.wait_for_idle(status="active")

#     logger.info("Discourse config updated, checking bucket content")

#     # Configuration for boto client
#     s3_client_config = Config(
#         region_name=s3_region,
#         s3={
#             "addressing_style": "virtual",
#         },
#     )

#     # Trick to use when localstack is deployed on another location than locally
#     if s3_ip_address != "127.0.0.1":
#         proxy_definition = {
#             "http": s3_url,
#         }
#         s3_client_config = s3_client_config.merge(
#             Config(
#                 proxies=proxy_definition,
#             )
#         )

#     # Configure the boto client
#     s3_client = client(
#         "s3",
#         s3_region,
#         aws_access_key_id=config_s3_bucket["access-key"],
#         aws_secret_access_key=config_s3_bucket["secret-key"],
#         endpoint_url=s3_endpoint,
#         use_ssl=False,
#         config=s3_client_config,
#     )

#     # Check the bucket has been created
#     response = s3_client.list_buckets()
#     bucket_list = [*map(lambda a: a["Name"], response["Buckets"])]

#     assert s3_bucket in bucket_list

#     # Check content has been uploaded in the bucket
#     response = s3_client.list_objects(Bucket=s3_bucket)
#     object_count = sum(1 for _ in response["Contents"])

#     assert object_count > 0


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_saml_auth(
    ops_test: OpsTest,
    app_config: Dict[str, str],
    app: Application,
    requests_timeout: float,
    ingress_ip: str,
):
    discourse_address = await get_unit_address(ops_test, app.name)
    discourse_url = f"http://{discourse_address}:{SERVICE_PORT}"
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0'
    response_adm = session.get(
        f"{discourse_url}/session/csrf",
        headers={
            "Host": f"{app_config['external_hostname']}:3000",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=requests_timeout,
    )
    action: juju.action.Action = await app.units[0].run_action("force-https")
    await action.wait()
    assert action.status == "completed"
    
    parsed_auth = response_adm.json()
    # Get the form info
    assert parsed_auth.get("csrf")
    authenticity_token = parsed_auth.get("csrf")  # type: ignore
    response = session.get(
        f"https://{ingress_ip}:443/auth/saml/metadata",
        headers={"Host": f"{app_config['external_hostname']}:3000"},
        timeout=5,
        verify=False,
    )
    assert "https" in response.text
    assert app_config['external_hostname'] in response.text
    logger.info(response.text)
    assert response.status_code == 200
    form_fields = {
        "authenticity_token": authenticity_token,
    }
    logger.info(session.cookies)
    response2 = session.post(
        f"https://{ingress_ip}:443/auth/saml",
        headers={
            "Host": f"{app_config['external_hostname']}:3000",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urlencode(form_fields),
        timeout=5,
        verify=False,
        allow_redirects=False
    )
    logger.info(response2.headers)
    # Replies with a redirect
    assert response2.status_code == 302
    logger.info(response2.history)
    logger.info(session.cookies)

    session.cookies.set("_cookies_accepted", "all")
    session.cookies.set("_ga", "GA1.2.453452525.1674827903")
    session.cookies.set("C", "1")
    session.cookies.set("csrftoken", "zsvAd1rsrBvQGgoYmZuBsmBTnuLN55SyYhhXn7rTkMrUQ26PMD5juYkxTPrxtOTQ")
    session.cookies.set("sessionid", "4jhwke0pl1fkv1hwrr18xxzuhh3cczh5")

    response3 = session.get(
        response2.headers['Location'],
        headers={
            "Host": f"{app_config['external_hostname']}:3000",
            "Content-Type": "text/html; charset=utf-8",
        },
        timeout=5,
        verify=False,
        allow_redirects=False
    )
    logger.info(response3.headers)
    logger.info(response3.history)
    logger.info(session.cookies)
    # Replies with a redirect
    assert response3.status_code == 301

    form_fields = {
        "email": "franco.forneron@canonical.com",
        "password": "I'm changing this for obvious reasons",
        "next": "/saml/process"
    }

    form_headers = {
        "Host": f"{app_config['external_hostname']}:3000",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    logger.info("Submitting authentication form")

    response = session.post(
        "https://login.staging.ubuntu.com/+login",
        headers=form_headers,
        data=urlencode(form_fields),
        allow_redirects=False,
        timeout=requests_timeout,
    )

    assert response.status_code == 301
