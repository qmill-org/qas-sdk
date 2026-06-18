"""Tests for SDK auth-state helpers and CLI auth commands."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from qas_sdk import cli
from qas_sdk.auth import load_auth_state, save_auth_state

UTC_TZ = timezone(timedelta(0))


def _write_state(path: Path, **overrides: object) -> None:
    state: dict[str, object] = {
        "base_url": "https://qas.qmill.com",
        "keycloak_realm": "quantum-platform",
        "keycloak_client_id": "quantum-app",
        "scope": "openid profile offline_access",
        "access_token": "old_access",
        "refresh_token": "refresh_1",
        "access_token_expires_at": (datetime.now(UTC_TZ) - timedelta(minutes=5)).isoformat(),
        "saved_at": datetime.now(UTC_TZ).isoformat(),
    }
    state.update(overrides)
    save_auth_state(state, auth_file=path)


def test_auth_state_roundtrip(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"

    payload = {
        "base_url": "https://qas.qmill.com",
        "keycloak_realm": "quantum-platform",
        "keycloak_client_id": "quantum-app",
        "access_token": "token-1",
        "refresh_token": "refresh-1",
        "access_token_expires_at": "2030-01-01T00:00:00+00:00",
    }
    save_auth_state(payload, auth_file=auth_file)

    loaded = load_auth_state(auth_file=auth_file)
    assert loaded is not None
    assert loaded["access_token"] == "token-1"
    assert loaded["refresh_token"] == "refresh-1"


def test_cli_status_not_logged_in(tmp_path: Path, monkeypatch: object, capsys: object) -> None:
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("QAS_AUTH_FILE", str(auth_file))

    exit_code = cli.main(["auth", "status"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Not logged in" in captured.out


def test_cli_token_refreshes_expired_state(
    tmp_path: Path, monkeypatch: object, capsys: object
) -> None:
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("QAS_AUTH_FILE", str(auth_file))
    _write_state(auth_file)

    def fake_refresh_with_refresh_token(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {
            "access_token": "new_access",
            "refresh_token": "refresh_2",
            "expires_in": 900,
        }

    monkeypatch.setattr(cli, "refresh_with_refresh_token", fake_refresh_with_refresh_token)

    exit_code = cli.main(["auth", "token"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "new_access"

    saved = load_auth_state(auth_file=auth_file)
    assert saved is not None
    assert saved["access_token"] == "new_access"
    assert saved["refresh_token"] == "refresh_2"
