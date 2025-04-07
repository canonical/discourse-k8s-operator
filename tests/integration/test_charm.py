#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging
import re
from typing import Dict

import jubilant
import pytest
import requests
from boto3 import client
from botocore.config import Config

from charm import PROMETHEUS_PORT

from . import types

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_active(app: types.App, juju: jubilant.Juju):
    """Check that the charm is active.
    Assume that the charm has already been built and is running.
    """
    status = juju.status()
    assert status.apps[app.name].units[app.name + "/0"].is_active


@pytest.mark.abort_on_fail
def test_prom_exporter_is_up(app: types.App, juju: jubilant.Juju):
    """
    arrange: given charm in its initial state
    act: when the metrics endpoint is scraped
    assert: the response is 200 (HTTP OK)
    """
    status = juju.status()
    assert app.name + "/0" in status.apps[app.name].units
    cmd = f"/usr/bin/curl -m 30 http://localhost:{PROMETHEUS_PORT}/metrics"
    juju.exec(cmd, unit=app.name + "/0", wait=60)


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("app")
def test_setup_discourse(
    app_config: Dict[str, str],
    requests_timeout: float,
    discourse_address: str,
):
    """Check discourse servers the registration page."""
    session = requests.session()
    logger.info("Getting registration page")
    # Send request to bootstrap page and set Host header to app name (which the application
    # expects)
    response = session.get(
        f"{discourse_address}/finish-installation/register",
        headers={"Host": f"{app_config['external_hostname']}"},
        timeout=requests_timeout,
        allow_redirects=True,
    )

    assert response.status_code == 200


@pytest.mark.abort_on_fail
def test_s3_conf(app: types.App, juju: jubilant.Juju, localstack_address: str | None):
    """Check that the bootstrap page is reachable
    with the charm configured with an S3 target
    Assume that the charm has already been built and is running.
    This test requires a localstack deployed
    """
    if not localstack_address:
        pytest.skip("requires --localstack-address argument")
        return

    s3_conf: Dict = generate_s3_config(localstack_address)

    logger.info("Updating discourse hosts")

    # Discourse S3 client uses subdomain bucket routing,
    # I need to inject subdomain in the DNS (not needed if everything runs localhost)
    juju.exec(
        f'echo "{s3_conf["ip_address"]}  {s3_conf["bucket"]}.s3.{s3_conf["domain"]}" >> /etc/hosts',
        unit=app.name + "/0",
    )

    logger.info("Injected bucket subdomain in hosts, configuring settings for discourse")
    juju.config(
        app.name,
        {
            "s3_enabled": True,
            # The final URL is computed by discourse, we need to pass the main URL
            "s3_endpoint": s3_conf["endpoint"],
            "s3_bucket": s3_conf["bucket"],
            "s3_secret_access_key": s3_conf["credentials"]["secret-key"],
            "s3_access_key_id": s3_conf["credentials"]["access-key"],
            # Default localstack region
            "s3_region": s3_conf["region"],
        },
    )
    juju.wait(jubilant.all_active)

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
    juju.config(
        app.name,
        {
            "s3_enabled": False,
            # The final URL is computed by discourse, we need to pass the main URL
            "s3_endpoint": "",
            "s3_bucket": "",
            "s3_secret_access_key": "",
            "s3_access_key_id": "",
            # Default localstack region
            "s3_region": "",
        },
    )
    juju.wait(jubilant.all_active)


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


@pytest.mark.usefixtures("app")
def test_create_category(
    discourse_address: str,
    admin_credentials: types.Credentials,
    admin_api_key: str,
):
    """
    arrange: A discourse application and an admin user
    act: If an admin user creates a category
    assert: A category should be created normally.
    """
    category_info = {"name": "test", "color": "FFFFFF"}
    response = requests.post(
        f"{discourse_address}/categories.json",
        headers={
            "Api-Key": admin_api_key,
            "Api-Username": admin_credentials.username,
        },
        json=category_info,
        timeout=60,
    )
    category_id = response.json()["category"]["id"]
    category = requests.get(f"{discourse_address}/c/{category_id}/show.json", timeout=60).json()[
        "category"
    ]

    assert category["name"] == category_info["name"]
    assert category["color"] == category_info["color"]


@pytest.mark.usefixtures("app")
def test_serve_compiled_assets(discourse_address: str):
    """
    arrange: A discourse application
    act: Access a page that does not exist
    assert: A compiled asset should be served.
    """
    response = requests.get(f"{discourse_address}/404", timeout=60)
    not_found_page = str(response.content)

    asset_matches = re.search(
        r"(onpopstate-handler).+.js", not_found_page
    )  # a non-compiled asset will be named onpopstate-handler.js
    assert asset_matches, "Compiled asset not found."


def test_relations(
    app: types.App,
    juju: jubilant.Juju,
    discourse_address: str,
    requests_timeout: int,
):
    """
    arrange: A discourse application
    act: Remove some of its relations
    assert: It should have the correct status
    """

    def test_discourse_srv_status_ok():
        response = requests.get(f"{discourse_address}/srv/status", timeout=requests_timeout)
        assert response.status_code == 200

    # The charm should be active when starting this test
    juju.wait(jubilant.all_active)
    test_discourse_srv_status_ok()

    # Removing the relation to postgresql should disable the charm
    juju.remove_relation(app.name, "postgresql-k8s:database")
    juju.wait(lambda status: status.apps[app.name].is_waiting)
    with pytest.raises(requests.ConnectionError):
        test_discourse_srv_status_ok()

    juju.integrate(app.name, "postgresql-k8s:database")
    juju.wait(jubilant.all_active)
    test_discourse_srv_status_ok()

    # Removing the relation to redis should disable the charm
    juju.remove_relation(app.name, "redis-k8s")
    juju.wait(lambda status: status.apps[app.name].is_waiting)
    with pytest.raises(requests.ConnectionError):
        test_discourse_srv_status_ok()

    juju.integrate(app.name, "redis-k8s")
    juju.wait(jubilant.all_active)
    test_discourse_srv_status_ok()

    # Removing the relation to ingress should keep the charm active
    juju.remove_relation(app.name, "nginx-ingress-integrator")
    juju.wait(lambda status: status.apps[app.name].is_active)
    test_discourse_srv_status_ok()

    juju.integrate(app.name, "nginx-ingress-integrator")
    juju.wait(jubilant.all_active)
    test_discourse_srv_status_ok()
