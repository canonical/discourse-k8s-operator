#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging

import jubilant
import pytest
import requests

from . import types

logger = logging.getLogger(__name__)


def test_create_user(juju: jubilant.Juju, app: types.App):
    """
    arrange: A discourse application
    act: Create a user
    assert: User is created, and re-creating the same user should fail
    """
    juju.wait(jubilant.all_active)

    email = "test-user@test.internal"

    task = juju.run(app.name + "/0", "create-user", {"email": email})
    assert task.results["user"] == email

    # Re-creating the same user should fail, as the user already exists
    with pytest.raises(jubilant.TaskError) as excinfo:
        juju.run(app.name + "/0", "create-user", {"email": email})
    assert excinfo.value.task.status == "failed"


def test_promote_user(juju: jubilant.Juju, app: types.App, discourse_address: str):
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

        assert response.ok, response.text
        data = response.json()
        assert data["csrf"], data
        csrf = data["csrf"]

        email = "test-promote-user@test.internal"
        task = juju.run(app.name + "/0", "create-user", {"email": email})
        assert task.results["user"] == email

        response = session.post(
            f"{discourse_address}/session",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            data={
                "login": email,
                "password": task.results["password"],
                "second_factor_method": "1",
                "timezone": "Asia/Hong_Kong",
            },
        )

        assert response.ok, response.text
        assert "error" not in response.json()

        assert not get_api_key(csrf), "This should fail as the user is not promoted"

        juju.run(app.name + "/0", "promote-user", {"email": email})
        assert get_api_key(csrf), "This should succeed as the user is promoted"
