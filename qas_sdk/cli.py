"""Command line interface for QAS SDK authentication flows."""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser

import requests

from .auth import (
    clear_auth_state,
    default_auth_file,
    default_realm_for_base_url,
    device_endpoint,
    hydrate_token_state,
    is_token_expired,
    load_auth_state,
    refresh_with_refresh_token,
    save_auth_state,
    token_endpoint,
)


def _add_auth_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    auth = subparsers.add_parser("auth", help="Authentication helpers")
    auth_subparsers = auth.add_subparsers(dest="auth_command")

    login = auth_subparsers.add_parser("login", help="Login via device code flow")
    login.add_argument("--base-url", default="https://qas.qmill.com")
    login.add_argument("--realm", default=None)
    login.add_argument("--client-id", default="quantum-app")
    login.add_argument("--scope", default="openid profile offline_access")
    login.add_argument("--no-browser", action="store_true")

    auth_subparsers.add_parser("status", help="Show current auth state")
    auth_subparsers.add_parser("logout", help="Clear persisted auth state")

    token = auth_subparsers.add_parser("token", help="Print a valid access token")
    token.add_argument("--refresh", action="store_true", help="Force refresh before printing")


def _device_login(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    realm = args.realm or default_realm_for_base_url(base_url)
    client_id = args.client_id
    scope = args.scope

    try:
        response = requests.post(
            device_endpoint(base_url, realm),
            data={"client_id": client_id, "scope": scope},
            timeout=20,
        )
        response.raise_for_status()
        device_data = response.json()
    except requests.exceptions.RequestException as exc:
        print(f"Device login initialization failed: {exc}", file=sys.stderr)
        return 1

    user_code = device_data.get("user_code")
    verification_uri = device_data.get("verification_uri")
    verification_uri_complete = device_data.get("verification_uri_complete")
    device_code = device_data.get("device_code")
    interval = int(device_data.get("interval", 5))
    expires_in = int(device_data.get("expires_in", 600))

    if not user_code or not verification_uri or not device_code:
        print("Device login endpoint returned incomplete payload", file=sys.stderr)
        return 1

    print("Open the following URL and complete sign-in:")
    print(f"  {verification_uri}")
    print(f"Code: {user_code}")
    if verification_uri_complete:
        print(f"Direct link: {verification_uri_complete}")

    if not args.no_browser and verification_uri_complete:
        webbrowser.open(verification_uri_complete)

    deadline = time.time() + expires_in
    login_succeeded = False
    while time.time() < deadline:
        try:
            token_response = requests.post(
                token_endpoint(base_url, realm),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": client_id,
                    "device_code": device_code,
                },
                timeout=20,
            )
            if token_response.status_code != 200:
                error_payload = token_response.json()
                error_code = error_payload.get("error")
                if error_code == "authorization_pending":
                    time.sleep(interval)
                    continue
                if error_code == "slow_down":
                    interval += 2
                    time.sleep(interval)
                    continue
                if error_code in {"access_denied", "expired_token"}:
                    error_message = error_code
                else:
                    error_message = str(error_payload)
                print(f"Login failed: {error_message}", file=sys.stderr)
                return 1

            token_data = token_response.json()
            state = hydrate_token_state(
                base_url=base_url,
                keycloak_realm=realm,
                keycloak_client_id=client_id,
                token_data=token_data,
                scope=scope,
            )
            save_auth_state(state)
            print(f"Login successful. Credentials stored at {default_auth_file()}")
            login_succeeded = True
            break
        except requests.exceptions.RequestException as exc:
            print(f"Login polling error: {exc}", file=sys.stderr)
            return 1

    if login_succeeded:
        return 0

    print("Login timed out before authorization was completed.", file=sys.stderr)
    return 1


def _auth_status() -> int:
    state = load_auth_state()
    if not state:
        print("Not logged in. Run: qas auth login")
        return 1

    expires = state.get("access_token_expires_at") or "unknown"
    expired = is_token_expired(state)
    print("Auth status:")
    print(f"  base_url: {state.get('base_url')}")
    print(f"  realm: {state.get('keycloak_realm')}")
    print(f"  client_id: {state.get('keycloak_client_id')}")
    print(f"  expires_at: {expires}")
    print(f"  expired: {'yes' if expired else 'no'}")
    print(f"  refresh_token: {'present' if state.get('refresh_token') else 'missing'}")
    print(f"  auth_file: {default_auth_file()}")
    return 0


def _auth_logout() -> int:
    clear_auth_state()
    print(f"Removed stored credentials at {default_auth_file()}")
    return 0


def _auth_token(*, force_refresh: bool) -> int:
    state = load_auth_state()
    if not state:
        print("Not logged in. Run: qas auth login", file=sys.stderr)
        return 1

    needs_refresh = force_refresh or is_token_expired(state)
    if needs_refresh:
        refresh_token = state.get("refresh_token")
        if not refresh_token:
            print("Stored session has no refresh token. Run: qas auth login", file=sys.stderr)
            return 1
        try:
            token_data = refresh_with_refresh_token(
                base_url=state["base_url"],
                keycloak_realm=state["keycloak_realm"],
                keycloak_client_id=state["keycloak_client_id"],
                refresh_token=refresh_token,
                scope=state.get("scope"),
            )
            state = hydrate_token_state(
                base_url=state["base_url"],
                keycloak_realm=state["keycloak_realm"],
                keycloak_client_id=state["keycloak_client_id"],
                token_data=token_data,
                scope=state.get("scope"),
            )
            save_auth_state(state)
        except requests.exceptions.RequestException as exc:
            print(f"Token refresh failed: {exc}", file=sys.stderr)
            return 1

    token = state.get("access_token")
    if not token:
        print("Stored session has no access token. Run: qas auth login", file=sys.stderr)
        return 1

    print(token)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qas", description="QAS SDK helper CLI")
    subparsers = parser.add_subparsers(dest="command")
    _add_auth_parsers(subparsers)

    args = parser.parse_args(argv)

    if args.command != "auth":
        parser.print_help()
        return 1

    if args.auth_command == "login":
        return _device_login(args)
    if args.auth_command == "status":
        return _auth_status()
    if args.auth_command == "logout":
        return _auth_logout()
    if args.auth_command == "token":
        return _auth_token(force_refresh=args.refresh)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
