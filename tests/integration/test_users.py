#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Discourse integration tests."""

import logging
import time

import jubilant
import pytest
import requests

from . import types
from .conftest import JUJU_WAIT_TIMEOUT

logger = logging.getLogger(__name__)


def test_create_user(juju: jubilant.Juju, app: types.App):
    """
    arrange: A discourse application
    act: Create a user
    assert: User is created, and re-creating the same user should fail
    """
    juju.wait(jubilant.all_active, timeout=JUJU_WAIT_TIMEOUT)

    email = f"test-user-{int(time.time())}@test.internal"

    task = juju.run(app.name + "/0", "create-user", {"email": email})
    assert task.results["user"] == email

    # Re-creating the same user should fail, as the user already exists
    with pytest.raises(jubilant.TaskError) as excinfo:
        juju.run(app.name + "/0", "create-user", {"email": email})
    assert excinfo.value.task.status == "failed"


def test_promote_user(
    juju: jubilant.Juju,
    app: types.App,
    discourse_address: str,
    app_config: dict[str, str],
):
    """
    arrange: A discourse application
    act: Promote a user to admin
    assert: User cannot access the admin API before being promoted
    """
    with requests.session() as session:
        base_headers = {"Host": app_config["external_hostname"], "X-Forwarded-Proto": "https"}
        session.headers.update(base_headers)

        def get_api_key_response(
            http_session: requests.Session, csrf_token: str
        ) -> requests.Response:
            http_session.headers.update(base_headers)
            response = http_session.post(
                f"{discourse_address}/admin/api/keys",
                headers={
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                },
                json={"key": {"description": "admin-api-key", "username": None}},
            )
            return response

        def login(http_session: requests.Session, email: str, password: str) -> str:
            http_session.headers.update(base_headers)
            csrf_response = http_session.get(
                f"{discourse_address}/session/csrf",
                headers={"Accept": "application/json"},
                timeout=60,
            )

            assert csrf_response.ok, csrf_response.text
            data = csrf_response.json()
            assert data["csrf"], data
            csrf = data["csrf"]

            login_response = http_session.post(
                f"{discourse_address}/session",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-CSRF-Token": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                },
                data={
                    "login": email,
                    "password": password,
                    "second_factor_method": "1",
                    "timezone": "Asia/Hong_Kong",
                },
            )
            assert login_response.ok, login_response.text
            assert "error" not in login_response.json()

            refreshed_csrf = http_session.get(
                f"{discourse_address}/session/csrf",
                headers={"Accept": "application/json"},
                timeout=60,
            )
            assert refreshed_csrf.ok, refreshed_csrf.text
            refreshed_data = refreshed_csrf.json()
            assert refreshed_data["csrf"], refreshed_data
            return refreshed_data["csrf"]

        email = f"test-promote-user-{int(time.time())}@test.internal"
        task = juju.run(app.name + "/0", "create-user", {"email": email})
        assert task.results["user"] == email

        csrf = login(session, email, task.results["password"])

        unpromoted_response = get_api_key_response(session, csrf)
        assert unpromoted_response.ok is False, unpromoted_response.text

        promote_task = juju.run(app.name + "/0", "promote-user", {"email": email})
        assert promote_task.results["user"] == email

        with requests.session() as promoted_session:
            promoted_csrf = login(promoted_session, email, task.results["password"])
            promoted_response = get_api_key_response(promoted_session, promoted_csrf)

        assert promoted_response.ok, promoted_response.text
        assert promoted_response.json().get("key"), promoted_response.text
