#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging
import re
import socket
import unittest.mock
from typing import Dict

import pytest
import requests
import urllib3.exceptions
from boto3 import client
from botocore.config import Config
from ops.model import ActiveStatus, Application
from pytest_operator.plugin import Model
from saml_test_helper import SamlK8sTestHelper  # pylint: disable=import-error

from charm import PROMETHEUS_PORT

from . import types

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
async def test_prom_exporter_is_up(app: Application):
    """
    arrange: given charm in its initial state
    act: when the metrics endpoint is scraped
    assert: the response is 200 (HTTP OK)
    """
    # Application actually does have units
    discourse_unit = app.units[0]  # type: ignore
    assert discourse_unit
    cmd = f"/usr/bin/curl -m 30 http://localhost:{PROMETHEUS_PORT}/metrics"
    action = await discourse_unit.run(cmd, timeout=60)
    await action.wait()
    code = action.results.get("return-code")
    stdout = action.results.get("stdout")
    stderr = action.results.get("stderr")
    assert code == 0, f"{cmd} failed ({code}): {stderr or stdout}"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_setup_discourse(
    app_config: Dict[str, str],
    requests_timeout: float,
    discourse_address: str,
):
    """Check discourse servers the registration page."""

    session = requests.session()
    logger.info("Getting registration page")
    # Send request to bootstrap page and set Host header to app_name (which the application
    # expects)
    response = session.get(
        f"{discourse_address}/finish-installation/register",
        headers={"Host": f"{app_config['external_hostname']}"},
        timeout=requests_timeout,
        allow_redirects=True,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_s3_conf(app: Application, localstack_address: str, model: Model):
    """Check that the bootstrap page is reachable
    with the charm configured with an S3 target
    Assume that the charm has already been built and is running.
    This test requires a localstack deployed
    """

    s3_conf: Dict = generate_s3_config(localstack_address)

    logger.info("Updating discourse hosts")

    # Discourse S3 client uses subdomain bucket routing,
    # I need to inject subdomain in the DNS (not needed if everything runs localhost)
    # Application actually does have units
    action = await app.units[0].run(  # type: ignore
        f'echo "{s3_conf["ip_address"]}  {s3_conf["bucket"]}.s3.{s3_conf["domain"]}" >> /etc/hosts'
    )
    await action.wait()
    assert action.results.get("return-code") == 0, "Can't inject S3 IP in Discourse hosts"

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
    await model.wait_for_idle(status="active")

    logger.info("Discourse config updated, checking bucket content")

    # Configuration for boto client
    s3_client_config = Config(
        region_name=s3_conf["region"],
        s3={
            "addressing_style": "virtual",
        },
    )

    # Configure the boto client
    s3_client = client(
        "s3",
        s3_conf["region"],
        aws_access_key_id=s3_conf["credentials"]["access-key"],
        aws_secret_access_key=s3_conf["credentials"]["secret-key"],
        endpoint_url=f"http://{localstack_address}:4566",
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
    await model.wait_for_idle(status="active")


def generate_s3_config(localstack_address: str) -> Dict:
    """Generate an S3 config for localstack based test."""
    return {
        # Localstack doesn't require any specific value there, any random string will work
        "credentials": {"access-key": "my-lovely-key", "secret-key": "this-is-very-secret"},
        # Localstack enforce to use this domain and it resolves to localhost
        "domain": "localhost.localstack.cloud",
        "bucket": "tests",
        "region": "us-east-1",
        "ip_address": localstack_address,
        "endpoint": "http://s3.localhost.localstack.cloud:4566",
    }


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.requires_secrets
@pytest.mark.usefixtures("setup_saml_config")
async def test_saml_login(  # pylint: disable=too-many-locals,too-many-arguments
    app: Application,
    requests_timeout: int,
    run_action,
    model: Model,
    saml_email: str,
    saml_password: str,
):
    """
    arrange: after discourse charm has been deployed, with all required relation established.
    act: add an admin user and enable force-https mode.
    assert: user can login discourse using SAML Authentication.
    """
    saml_helper = SamlK8sTestHelper.deploy_saml_idp(model.name)
    saml_app: Application = await model.deploy(
        "saml-integrator",
        channel="latest/edge",
        series="jammy",
        trust=True,
    )
    await model.wait_for_idle()
    saml_helper.prepare_pod(model.name, f"{saml_app.name}-0")
    saml_helper.prepare_pod(model.name, f"{app.name}-0")
    await model.wait_for_idle()
    await saml_app.set_config(  # type: ignore[attr-defined]
        {
            "entity_id": f"https://{saml_helper.SAML_HOST}/metadata",
            "metadata_url": f"https://{saml_helper.SAML_HOST}/metadata",
        }
    )
    await model.add_relation(app.name, "saml-integrator")
    await model.wait_for_idle()
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    action_result = await run_action(
        app.name, "add-admin-user", email=saml_email, password=saml_password
    )
    assert "user" in action_result

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
        username = saml_email.split("@")[0]
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
            headers={"Accept": "application/json"},
            timeout=requests_timeout,
        )
        csrf_token = response.json()["csrf"]
        redirect_response = session.post(
            f"https://{host}/auth/saml",
            data={"authenticity_token": csrf_token},
            timeout=requests_timeout,
            allow_redirects=False,
        )
        assert redirect_response.status_code == 302
        redirect_url = redirect_response.headers["Location"]
        saml_response = saml_helper.redirect_sso_login(redirect_url)
        assert f"https://{host}" in saml_response.url

        preference_page = session.get(
            f"https://{host}/u/{username}/preferences/account",
            verify=False,
            timeout=requests_timeout,
        )
        assert preference_page.status_code == 200


@pytest.mark.asyncio
async def test_create_category(
    discourse_address: str,
    admin_credentials: types.Credentials,
    admin_api_key: str,
):
    """
    arrange: Given discourse application and an admin user
    act: if an admin user creates a category
    assert: a category should be created normally.
    """
    category_info = {"name": "test", "color": "FFFFFF"}
    res = requests.post(
        f"{discourse_address}/categories.json",
        headers={
            "Api-Key": admin_api_key,
            "Api-Username": admin_credentials.username,
        },
        json=category_info,
        timeout=60,
    )
    category_id = res.json()["category"]["id"]
    category = requests.get(f"{discourse_address}/c/{category_id}/show.json", timeout=60).json()[
        "category"
    ]

    assert category["name"] == category_info["name"]
    assert category["color"] == category_info["color"]


@pytest.mark.asyncio
async def test_serve_compiled_assets(
    discourse_address: str,
):
    """
    arrange: Given discourse application
    act: when accessing a page that does not exist
    assert: a compiled asset should be served.
    """
    res = requests.get(f"{discourse_address}/404", timeout=60)
    not_found_page = str(res.content)

    asset_matches = re.search(
        r"(onpopstate-handler).+.js", not_found_page
    )  # a non-compiled asset will be named onpopstate-handler.js
    assert asset_matches, "Compiled asset not found."


@pytest.mark.asyncio
async def test_relations(
    app: Application,
    discourse_address: str,
    model: Model,
    requests_timeout: int,
):
    """
    arrange: Given discourse application
    act: when removing some of its relations
    assert: it should have the correct status
    """

    def test_discourse_srv_status_ok():
        response = requests.get(f"{discourse_address}/srv/status", timeout=requests_timeout)
        assert response.status_code == 200

    # The charm should be active when starting this test
    await model.wait_for_idle(status="active")
    test_discourse_srv_status_ok()

    # Removing the relation to postgresql should disable the charm
    await model.applications[app.name].remove_relation("database", "postgresql-k8s:database")
    await model.wait_for_idle(apps=[app.name], status="waiting")
    with pytest.raises(requests.ConnectionError):
        test_discourse_srv_status_ok()

    await model.add_relation(app.name, "postgresql-k8s:database")
    await model.wait_for_idle(status="active")
    test_discourse_srv_status_ok()

    # Removing the relation to redis should disable the charm
    await model.applications[app.name].remove_relation("redis", "redis-k8s")
    await model.wait_for_idle(apps=[app.name], status="waiting")
    with pytest.raises(requests.ConnectionError):
        test_discourse_srv_status_ok()

    await model.add_relation(app.name, "redis-k8s")
    await model.wait_for_idle(status="active")
    test_discourse_srv_status_ok()

    # Removing the relation to ingress should keep the charm active
    await model.applications[app.name].remove_relation("nginx-route", "nginx-ingress-integrator")
    await model.wait_for_idle(status="active")
    test_discourse_srv_status_ok()

    await model.add_relation(app.name, "nginx-ingress-integrator")
    await model.wait_for_idle(status="active")
    test_discourse_srv_status_ok()
