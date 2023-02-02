#!/usr/bin/env python3
"""Helper functions for Discourse charm tests."""
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Helper functions for Discourse charm tests."""

import itertools
from collections import namedtuple
from typing import Optional

import psycopg2
import yaml
from ops.model import Application
from pytest_operator.plugin import OpsTest

DBInfo = namedtuple("DBInfo", ["host", "schema", "username", "password"])


async def get_unit_address(ops_test: OpsTest, app_name: str) -> str:
    """Get unit IP address.
    Args:
        ops_test: The ops test framework instance
        app_name: The name of the app
    Returns:
        IP address of the first unit
    """
    assert ops_test.model
    status = await ops_test.model.get_status()
    unit = list(status.applications[app_name].units)[0]
    return status["applications"][app_name]["units"][unit]["address"]


async def get_db_info(app: Application, app_name: str = "operator") -> Optional[DBInfo]:
    """Retrieve a user password from the application pebble plan."""

    cmd = f"PEBBLE_SOCKET=/charm/containers/{app_name}/pebble.socket /charm/bin/pebble plan"
    # Application actually does have units
    unit = app.units[0]  # type: ignore

    action = await unit.run(cmd)
    result = await action.wait()

    if result.results.get("return-code") != 0:
        return None

    stdout = result.results.get("stdout")
    parsed_plan = yaml.safe_load(stdout)
    parsed_env = parsed_plan["services"][app_name]["environment"]

    return DBInfo(
        parsed_env["DISCOURSE_DB_HOST"],
        parsed_env["DISCOURSE_DB_NAME"],
        parsed_env["DISCOURSE_DB_USERNAME"],
        parsed_env["DISCOURSE_DB_PASSWORD"],
    )


async def get_discourse_email_token(db_info: DBInfo, email: str):
    """Look for token related to an email address in Discourse DB
    Args:
        db_info: The DBInfo object containing host, schema, username and password
        email: The email address
    Return:
        The token associated to this email address$
    """
    sql_output = await execute_query_on_unit(
        db_info, f"SELECT \"token\" FROM email_tokens WHERE email = '{email}'"  # nosec
    )

    return sql_output[0] if sql_output else None


async def execute_query_on_unit(db_info: DBInfo, query: str) -> list:
    """Execute given PostgreSQL query on a unit.
    Args:
        db_info: The DBInfo object containing host, schema, username and password
        query: Query to execute.
    Returns:
        The result of the query.
    """
    with psycopg2.connect(
        f"dbname='{db_info.schema}' user='{db_info.username}' host='{db_info.host}'"
        f"password='{db_info.password}' connect_timeout=10"
    ) as connection, connection.cursor() as cursor:
        cursor.execute(query)
        output = list(itertools.chain(*cursor.fetchall()))
    return output
