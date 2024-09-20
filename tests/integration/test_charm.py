#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import pytest
import requests
from boto3 import client
from botocore.config import Config
from juju.application import Application
from ops.model import ActiveStatus, WaitingStatus
from pytest_operator.plugin import Model, OpsTest

from charm import DISCOURSE_PATH, PROMETHEUS_PORT

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
async def test_db_migration(model: Model, ops_test: OpsTest, run_action):

    postgres_app = await model.deploy(
        "postgresql-k8s",
        channel="14/stable",
        series="jammy",
        trust=True,
        config={"profile": "testing"},
    )
    async with ops_test.fast_forward():
        await model.wait_for_idle(apps=[postgres_app.name], status="active")

    redis_app = await model.deploy("redis-k8s", series="jammy", channel="latest/edge")
    await model.wait_for_idle(apps=[redis_app.name], status="active")

    await model.deploy("nginx-ingress-integrator", series="focal", trust=True)
    app_name = "discourse-k8s"
    discourse_app = await model.deploy(
        app_name,
        channel="latest/edge",
        revision=162,
        series="focal",
        resources={"discourse-image": "152"},
    )
    await model.wait_for_idle(apps=[app_name], status="waiting")

    logger.info("Deployed discourse ")
    # configure postgres
    await postgres_app.set_config(
        {
            "plugin_hstore_enable": "true",
            "plugin_pg_trgm_enable": "true",
        }
    )
    logger.info("Configured postgresql")
    await model.wait_for_idle(apps=[postgres_app.name], status="active")

    logger.info("Checking discourse status")
    # Add required relations
    unit = model.applications[app_name].units[0]
    assert unit.workload_status == WaitingStatus.name  # type: ignore
    logger.info("Adding relations")
    await model.add_relation(app_name, "postgresql-k8s:database")
    await model.add_relation(app_name, "redis-k8s")
    await model.add_relation(app_name, "nginx-ingress-integrator")
    logger.info("Added relations")
    await model.wait_for_idle(apps=[app_name], status="active")
    # import pdb; pdb.set_trace()
    logger.info("Create mock database")

    # Create mock database
    # Get the api key first
    return_code, api_key, _ = await ops_test.juju(
        "ssh",
        "--container",
        "discourse",
        unit.name,
        f"pebble exec --user=_daemon_ --context=discourse -w={DISCOURSE_PATH} -- {DISCOURSE_PATH}/bin/bundle exec rake api_key:create_master['api key description']",
    )
    api_key = api_key.strip()
    # create admin user
    user_1_pass = await run_action(app_name, "create-user", email="email@example.com", admin=True)
    logger.info("email password: %s", user_1_pass)
    logger.info("api_key: %s",api_key )
    return_code, invite_output, _ = await ops_test.juju(
        "ssh",
        "--container",
        "discourse",
        unit.name,
        f"pebble exec --user=_daemon_ --context=discourse -w={DISCOURSE_PATH} -- {DISCOURSE_PATH}/bin/bundle exec rake admin:invite['email2@example.com']",
    )
    logger.info("invite output: %s", invite_output)

    # import pdb; pdb.set_trace()
    # await run_action(app_name, "create-user", email="email2@example.com", admin=True)
    # create regular user
    header = {"Api-Key": api_key, "Api-Username": "email", "Host": "discourse-k8s"}
    # user_json = {
    #     "name": "email2",
    #     "email": "email2@example.com",
    #     "password": "Strong.Password",
    #     "username": "email2",
    #     "active": False,
    #     "approved": False,
    # }
    # user_result = requests.post("http://127.0.0.1/users.json", json=user_json, headers=header)
    # logger.warning(user_result.text)
    # user_id = json.loads(user_result.text)["user_id"]
    # new_res = requests.put(f"http://127.0.0.1/admin/users/{user_id}/activate.json", json={"id": user_id}, headers=header)
    # logger.info("new_res : %s",new_res.text )
    # import pdb; pdb.set_trace()
    # create a topic
    example_topic = {
        "title": "test topic for integration tests",
        "category": 4,
        "category_id": 4,
        "raw": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "id": 12,
    }
    # header["Api-Username"] = "email2"
    post_res = requests.post("http://127.0.0.1/posts.json", json=example_topic, headers=header)
    post_json = json.loads(post_res.text)
    logger.info(post_json)
    # import pdb; pdb.set_trace()
    reply_obj = {
        "raw": "https://github.com/canonical/discourse-k8s-operator/pull/287",
        "topic_id": post_json["topic_id"],
    }
    post_res = requests.post("http://127.0.0.1/posts.json", json=reply_obj, headers=header)
    # import pdb ;pdb.set_trace()
    header["Api-Username"] = "email2"
    reply_obj = {
        "raw": """"

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eu vehicula eros. Aliquam id velit ac libero rutrum vulputate. Fusce at vehicula justo. Cras vulputate aliquet nisi in viverra. Nullam vitae libero tincidunt, feugiat mi ac, condimentum lacus. Nulla quam nisi, sodales quis tempor eu, blandit at justo. Proin semper finibus accumsan. Aliquam non nunc at dolor dapibus luctus id a leo.

Fusce mollis, augue quis pharetra porttitor, ante felis euismod ante, at dignissim enim felis ac sem. Praesent at purus faucibus, tincidunt arcu eget, dapibus lectus. Etiam scelerisque pulvinar enim ut blandit. Morbi sed nibh et nisi convallis fermentum. Nullam nec ultricies arcu, et imperdiet sapien. Aliquam mauris ipsum, blandit id semper in, tincidunt sed quam. Fusce sollicitudin sollicitudin elit et condimentum. Duis tempus ligula arcu, eu fringilla eros placerat sit amet. Donec tempus enim et finibus rutrum. Vestibulum ac erat ac dolor maximus accumsan. Nulla aliquam diam non felis feugiat dictum.

Cras hendrerit odio arcu, nec ultrices lectus tincidunt in. Nam gravida viverra mi eu accumsan. Sed luctus tellus posuere mi venenatis, ac elementum purus porttitor. Ut vel massa dui. Duis auctor sapien in aliquet ultricies. Maecenas quis nibh id metus porta tempor. Sed imperdiet erat massa, non consectetur velit aliquam a. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla vestibulum tortor leo, vel congue ex ullamcorper venenatis. Donec ipsum ex, ultrices sed congue et, ornare non purus. Nulla ornare eget metus in suscipit. Lorem ipsum dolor sit amet, consectetur adipiscing elit.

Class aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos himenaeos. Donec aliquet ornare est, eu posuere ligula. Nunc at viverra turpis. Maecenas sed volutpat augue, ut mollis nunc. Nam quis felis ac enim blandit aliquet. Duis facilisis enim id erat vehicula, nec tempor est blandit. Quisque eu nulla non nibh consequat porta.

Aliquam in elementum tortor. Sed purus magna, vulputate eu lacus sit amet, dapibus gravida enim. Maecenas at orci vel erat accumsan feugiat sit amet non ante. Aliquam imperdiet, augue sed volutpat efficitur, massa arcu tempus sapien, eget iaculis ipsum lorem at mauris. Fusce ligula risus, condimentum quis odio ut, maximus viverra mi. Maecenas eget lectus porttitor dui commodo ultricies. Mauris aliquam, turpis ut facilisis mattis, orci felis aliquam erat, eget posuere nisl metus sed orci. Vivamus tellus dolor, sodales dapibus urna vitae, venenatis rutrum erat. Cras efficitur tempor tortor, non dictum dui facilisis eu. Morbi nec turpis eu neque aliquet bibendum id at erat. Nullam lacinia maximus consectetur. Fusce finibus arcu eu luctus auctor. Aenean porttitor in turpis dignissim auctor. Proin finibus non justo in efficitur.
""",
        "topic_id": post_json["topic_id"],
    }
    post_res = requests.post("http://127.0.0.1/posts.json", json=reply_obj, headers=header)

    resources = {"discourse-image": "localhost:32000/discourse-rock:1.1"}
    charm_path = await ops_test.build_charm(".")
    await discourse_app.refresh(path=charm_path, resources=resources)
    # import pdb; pdb.set_trace()
    assert True, "TODO"


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
async def test_create_category(
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


@pytest.mark.asyncio
async def test_serve_compiled_assets(
    discourse_address: str,
):
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


@pytest.mark.asyncio
async def test_relations(
    app: Application,
    discourse_address: str,
    model: Model,
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
    await model.wait_for_idle(apps=[app.name], status="active")
    test_discourse_srv_status_ok()

    await model.add_relation(app.name, "nginx-ingress-integrator")
    await model.wait_for_idle(status="active")
    test_discourse_srv_status_ok()


@pytest.mark.skip(reason="Frequent timeouts")
async def test_upgrade(
    app: Application,
    model: Model,
    pytestconfig: Config,
    ops_test: OpsTest,
):
    """
    arrange: A discourse application with three units
    act: Refresh the application (upgrade)
    assert: The application upgrades and over all the upgrade, the application replies
      correctly through the ingress.
    """

    await app.scale(3)
    await model.wait_for_idle(status="active")

    resources = {
        "discourse-image": pytestconfig.getoption("--discourse-image"),
    }

    if charm_file := pytestconfig.getoption("--charm-file"):
        charm_path: str | Path | None = f"./{charm_file}"
    else:
        charm_path = await ops_test.build_charm(".")

    host = app.name

    def check_alive():
        response = requests.get("http://127.0.0.1/srv/status", headers={"Host": host}, timeout=2)
        logger.info("check_alive response: %s", response.content)
        assert response.status_code == 200

    check_alive()
    await app.refresh(path=charm_path, resources=resources)

    def upgrade_finished(idle_seconds=15):
        """Check that the upgrade finishes correctly (active)

        This function checks continuously during the upgrade (in every iteration
        every 0.5 seconds) that Discourse is replying correctly to the /srv/status endpoint.

        The upgrade is considered done when the units have been idle for
        `idle_seconds` and all the units workloads and the app are active.
        """
        idle_start = None

        def _upgrade_finished():
            nonlocal idle_start
            check_alive()

            idle_period = timedelta(seconds=idle_seconds)
            is_idle = all(unit.agent_status == "idle" for unit in app.units)

            now = datetime.now()

            if not is_idle:
                idle_start = None
                return False

            if not idle_start:
                idle_start = now
                return False

            if now - idle_start < idle_period:
                # Not idle for long enough
                return False

            is_active = app.status == "active" and all(
                unit.workload_status == "active" for unit in app.units
            )
            if is_active:
                return True

            return False

        return _upgrade_finished

    await model.block_until(upgrade_finished(), timeout=10 * 60)
    check_alive()
