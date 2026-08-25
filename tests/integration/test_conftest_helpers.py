# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit-like tests for lightweight helper logic in integration conftest."""

from pathlib import Path

from . import conftest


def test_resolve_kubectl_command_falls_back_to_microk8s(monkeypatch) -> None:
    """Fallback to microk8s kubectl wrapper when kubectl is not on PATH."""
    monkeypatch.setattr(
        conftest.shutil,
        "which",
        lambda command: None if command == "kubectl" else "/usr/bin/microk8s",
    )

    assert conftest._resolve_kubectl_command() == ["microk8s", "kubectl"]


def test_resolve_saml_kube_config_prefers_existing_kubeconfig_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Use the first existing path from KUBECONFIG."""
    first = tmp_path / "missing-kubeconfig"
    second = tmp_path / "valid-kubeconfig"
    second.write_text("apiVersion: v1\nclusters: []\ncontexts: []\nusers: []\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", f"{first}:{second}")

    assert conftest._resolve_saml_kube_config() == str(second)


def test_resolve_saml_kube_config_falls_back_to_candidate_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Fall back to known candidate paths when KUBECONFIG is unset."""
    candidate = tmp_path / "candidate-kubeconfig"
    candidate.write_text(
        "apiVersion: v1\nclusters: []\ncontexts: []\nusers: []\n", encoding="utf-8"
    )
    monkeypatch.delenv("KUBECONFIG", raising=False)
    monkeypatch.setattr(conftest, "SAML_KUBECONFIG_CANDIDATES", (str(candidate),))

    assert conftest._resolve_saml_kube_config() == str(candidate)
