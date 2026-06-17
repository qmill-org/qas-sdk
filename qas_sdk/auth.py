"""Authentication helpers shared by the QAS SDK and CLI."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

TOKEN_EXPIRY_BUFFER = 30
UTC_TZ = timezone(timedelta(0))
AUTH_FILE_ENV = "QAS_AUTH_FILE"


class AuthStorageError(Exception):
    """Raised when persisted auth state cannot be read or written."""


def default_realm_for_base_url(base_url: str) -> str:
    """Return the default Keycloak realm for the provided QAS base URL."""
    return "quantum-platform-dev" if "qas-dev" in base_url else "quantum-platform"


def default_auth_file() -> Path:
    raw = os.getenv(AUTH_FILE_ENV, "~/.config/qas/auth.json")
    path = Path(raw).expanduser()
    if path.is_dir():
        return path / "auth.json"
    return path


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ)


def _format_iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC_TZ).isoformat()


def load_auth_state(auth_file: Path | None = None) -> dict[str, Any] | None:
    path = auth_file or default_auth_file()
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Unable to read auth state at {path}: {exc}"
        raise AuthStorageError(msg) from exc

    if not isinstance(payload, dict):
        msg = f"Auth state file at {path} is not a JSON object"
        raise AuthStorageError(msg)

    return payload


def save_auth_state(state: dict[str, Any], auth_file: Path | None = None) -> None:
    path = auth_file or default_auth_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        path.chmod(0o600)
    except OSError as exc:
        msg = f"Unable to persist auth state at {path}: {exc}"
        raise AuthStorageError(msg) from exc


def clear_auth_state(auth_file: Path | None = None) -> None:
    path = auth_file or default_auth_file()
    if path.exists():
        path.unlink()


def token_endpoint(base_url: str, keycloak_realm: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/auth/realms/{keycloak_realm}/protocol/openid-connect/token"


def device_endpoint(base_url: str, keycloak_realm: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/auth/realms/{keycloak_realm}/protocol/openid-connect/auth/device"


def hydrate_token_state(
    *,
    base_url: str,
    keycloak_realm: str,
    keycloak_client_id: str,
    token_data: dict[str, Any],
    scope: str | None = None,
) -> dict[str, Any]:
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        msg = "Token response missing access_token"
        raise ValueError(msg)

    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    expires_at = None
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        buffer_seconds = min(TOKEN_EXPIRY_BUFFER, int(expires_in))
        expires_at = datetime.now(UTC_TZ) + timedelta(seconds=int(expires_in) - buffer_seconds)

    return {
        "base_url": base_url.rstrip("/"),
        "keycloak_realm": keycloak_realm,
        "keycloak_client_id": keycloak_client_id,
        "scope": scope,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_token_expires_at": _format_iso_datetime(expires_at),
        "saved_at": _format_iso_datetime(datetime.now(UTC_TZ)),
    }


def is_state_match(
    state: dict[str, Any],
    *,
    base_url: str,
    keycloak_realm: str,
    keycloak_client_id: str,
) -> bool:
    return (
        state.get("base_url") == base_url.rstrip("/")
        and state.get("keycloak_realm") == keycloak_realm
        and state.get("keycloak_client_id") == keycloak_client_id
    )


def is_token_expired(state: dict[str, Any]) -> bool:
    expires_at = _parse_iso_datetime(state.get("access_token_expires_at"))
    if expires_at is None:
        return False
    return datetime.now(UTC_TZ) >= expires_at


def refresh_with_refresh_token(  # noqa: PLR0913
    *,
    base_url: str,
    keycloak_realm: str,
    keycloak_client_id: str,
    refresh_token: str,
    scope: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "client_id": keycloak_client_id,
        "refresh_token": refresh_token,
    }
    if scope:
        data["scope"] = scope

    response = requests.post(token_endpoint(base_url, keycloak_realm), data=data, timeout=timeout)
    response.raise_for_status()
    return response.json()
