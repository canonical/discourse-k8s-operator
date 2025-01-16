#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging

import pytest
import requests
from juju.action import Action
from juju.application import Application
from juju.unit import Unit

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_create_user(
    app: Application,
):
    """
    arrange: A discourse application
    act: Create a user
    assert: User is created, and re-creating the same user should fail
    """

    await app.model.wait_for_idle(status="active")
    discourse_unit: Unit = app.units[0]

    email = "test-user@test.internal"

    action: Action = await discourse_unit.run_action("create-user", email=email)
    await action.wait()
    assert action.results["user"] == email

    # Re-creating the same user should fail, as the user already exists
    break_action: Action = await discourse_unit.run_action("create-user", email=email)
    await break_action.wait()
    assert break_action.status == "failed"


@pytest.mark.asyncio
async def test_promote_user(
    app: Application,
    discourse_address: str,
):
    """
    arrange: A discourse application
    act: Promote a user to admin
    assert: User cannot access the admin API before being promoted
    """

    with requests.session() as session:

        def get_api_key(csrf_token: str) -> bool:
            response = session.post(
                f"{discourse_address}/admin/api/keys",
                headers={
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                },
                json={"key": {"description": "admin-api-key", "username": None}},
            )
            if response.json().get("key") is None:
                return False
            return True

        response = session.get(
            f"{discourse_address}/session/csrf", headers={"Accept": "application/json"}, timeout=60
        )
        # pylint doesn't see the "ok" member
        assert response.ok, response.text  # pylint: disable=no-member
        data = response.json()
        assert data["csrf"], data
        csrf = data["csrf"]

        email = "test-promote-user@test.internal"
        discourse_unit: Unit = app.units[0]
        create_action: Action = await discourse_unit.run_action("create-user", email=email)
        await create_action.wait()
        assert create_action.results["user"] == email

        response = session.post(
            f"{discourse_address}/session",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            data={
                "login": email,
                "password": create_action.results["password"],
                "second_factor_method": "1",
                "timezone": "Asia/Hong_Kong",
            },
        )

        assert response.ok, response.text  # pylint: disable=no-member
        assert "error" not in response.json()

        assert not get_api_key(csrf), "This should fail as the user is not promoted"

        promote_action: Action = await discourse_unit.run_action("promote-user", email=email)
        await promote_action.wait()

        assert get_api_key(csrf), "This should succeed as the user is promoted"
