"""
QAS Platform Python SDK

A Python client library for interacting with the QAS Circuit Compression API.

Example usage:
    import os
    from qas_sdk import QASClient

    client = QASClient(
        base_url="https://qas.qmill.com",
        keycloak_client_id=os.environ["QAS_CLIENT_ID"],
        client_secret=os.environ["QAS_CLIENT_SECRET"],
        token_audience=os.getenv("QAS_TOKEN_AUDIENCE"),
        scope=os.getenv("QAS_TOKEN_SCOPE"),
    )

    # Submit a circuit for compression
    job = client.submit_compression("OPENQASM 2.0;...")
    print(f"Job ID: {job['job_id']}")

    # Wait for completion
    result = client.wait_for_job(job['job_id'])
    print(f"Compressed circuit: {result['result']}")

    # Submit circuit for quantum execution
    execution_job = client.submit_circuit(
        circuit=circuit,
        device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
        shots=1000
    )

    # Get job results and status
    results = client.get_job_results(execution_job['job_id'])
    status = client.get_job_status(execution_job['job_id'])
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .auth import (
    AuthStorageError,
    default_realm_for_base_url,
    is_state_match,
    load_auth_state,
    save_auth_state,
)

PUBLIC_COMPRESSION_API_PREFIX = "/api/public/v1/circuit-compression"
INTERNAL_COMPRESSION_API_PREFIX = "/api/v1/circuit-compression"


class QASAuthError(Exception):
    """Authentication error"""


class QASAPIError(Exception):
    """API request error"""


TOKEN_EXPIRY_BUFFER = 30
UTC_TZ = timezone(timedelta(0))


@dataclass(frozen=True)
class CompressionJobOptions:
    """Optional parameters for compression job submissions."""

    num_gpus: int | None = None
    iteration_time_minutes: int | None = None
    gate_set: str | None = None
    goal: str | None = None
    hpc_mode: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.num_gpus is not None:
            payload["num_gpus"] = self.num_gpus
        if self.iteration_time_minutes is not None:
            payload["iteration_time_minutes"] = self.iteration_time_minutes
        if self.gate_set is not None:
            payload["gate_set"] = self.gate_set
        if self.goal is not None:
            payload["goal"] = self.goal
        if self.hpc_mode is not None:
            payload["hpc_mode"] = self.hpc_mode
        return payload


class QASClient:
    """
    QAS Platform API Client

    Handles authentication and provides methods for circuit compression
    and quantum device operations.
    """

    def __init__(
        self,
        base_url: str = "https://qas.qmill.com",
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_provider: Callable[[], str] | None = None,
        *,
        keycloak_realm: str | None = None,
        keycloak_client_id: str | None = None,
        client_secret: str | None = None,
        token_audience: str | None = None,
        scope: str | None = None,
        compression_api_prefix: str = PUBLIC_COMPRESSION_API_PREFIX,
        auto_authenticate: bool = True,
    ) -> None:
        """
        Initialize QAS client

        Args:
            base_url: Base URL of QAS platform
            access_token: Pre-obtained access token.
            refresh_token: Keycloak refresh token paired with *access_token*. When
                provided, the SDK exchanges it automatically for a new access/refresh
                token pair whenever the access token expires, so long sessions work
                without any manual intervention.
            token_provider: Zero-argument callable that returns a fresh access token
                string. Called automatically whenever a token refresh is needed.
                Takes precedence over *refresh_token* when both are supplied.
                Useful for custom auth integrations (e.g. reading a rotating secret
                from a vault or re-prompting the user).
            keycloak_realm: Keycloak realm name (defaults based on base_url)
            keycloak_client_id: Keycloak client ID (defaults based on base_url)
        """
        self.base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_provider = token_provider
        self._token_expiry = None
        self.client_secret = client_secret
        self.token_audience = token_audience
        self.scope = scope
        self.compression_api_prefix = compression_api_prefix.rstrip("/")
        self._auth_flow: str | None = None
        self._persist_external_tokens = False
        self._keycloak_client_id_explicit = keycloak_client_id is not None

        # Auto-detect realm and client_id based on environment if not provided
        self.keycloak_realm = keycloak_realm or default_realm_for_base_url(self.base_url)

        if keycloak_client_id is None:
            self.keycloak_client_id = "qas-cli"
        else:
            self.keycloak_client_id = keycloak_client_id

        # Track externally provided tokens
        if access_token:
            self._auth_flow = "external"

        # Authenticate if credentials provided and caller permits auto auth
        has_client_credentials = bool(self.client_secret and self.keycloak_client_id)
        if auto_authenticate and not access_token:
            if has_client_credentials:
                self.authenticate()
            else:
                self._load_stored_auth_tokens()

    def authenticate(self) -> None:
        """Authenticate using the configured credential flow."""

        if self.client_secret:
            self._authenticate_client_credentials()
            return

        msg = (
            "No authentication credentials available. Provide client_secret for machine-to-machine "
            "authentication, or run `qas auth login` first."
        )
        raise QASAuthError(msg)

    def _load_stored_auth_tokens(self) -> None:
        try:
            state = load_auth_state()
        except AuthStorageError:
            return
        if not state:
            return

        # If client ID was not explicitly configured, adopt the stored one for
        # the matching base_url+realm so CLI logins via alternate client IDs
        # (for example qas-cli) are usable by default SDK flows.
        if self._keycloak_client_id_explicit:
            if not is_state_match(
                state,
                base_url=self.base_url,
                keycloak_realm=self.keycloak_realm,
                keycloak_client_id=self.keycloak_client_id,
            ):
                return
        else:
            if (
                state.get("base_url") != self.base_url
                or state.get("keycloak_realm") != self.keycloak_realm
            ):
                return
            stored_client_id = state.get("keycloak_client_id")
            if isinstance(stored_client_id, str) and stored_client_id:
                self.keycloak_client_id = stored_client_id

        access_token = state.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return

        self._access_token = access_token
        refresh_token = state.get("refresh_token")
        self._refresh_token = refresh_token if isinstance(refresh_token, str) else None
        expires_at = state.get("access_token_expires_at")
        if isinstance(expires_at, str):
            normalized = expires_at.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC_TZ)
                self._token_expiry = parsed.astimezone(UTC_TZ)
            except ValueError:
                self._token_expiry = None
        self._auth_flow = "external"
        self._persist_external_tokens = True

    def _persist_external_auth_tokens(self) -> None:
        if not self._persist_external_tokens or not self._access_token:
            return

        expires_at = self._token_expiry.isoformat() if self._token_expiry else None
        state = {
            "base_url": self.base_url,
            "keycloak_realm": self.keycloak_realm,
            "keycloak_client_id": self.keycloak_client_id,
            "scope": self.scope,
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "access_token_expires_at": expires_at,
            "saved_at": datetime.now(UTC_TZ).isoformat(),
        }
        try:
            save_auth_state(state)
        except AuthStorageError:
            # Persistence is best-effort; request flow should still succeed.
            return

    def _token_endpoint(self) -> str:
        return f"{self.base_url}/auth/realms/{self.keycloak_realm}/protocol/openid-connect/token"

    def _execute_token_request(self, data: dict[str, str], context: str) -> dict:
        try:
            response = requests.post(self._token_endpoint(), data=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            msg = f"{context}: {exc}"
            raise QASAuthError(msg) from exc

        try:
            return response.json()
        except ValueError as exc:
            msg = f"{context}: Invalid token response"
            raise QASAuthError(msg) from exc

    def _hydrate_tokens(self, token_data: dict, auth_flow: str) -> None:
        self._access_token = token_data.get("access_token")
        if not self._access_token:
            msg = "Token response missing access_token"
            raise QASAuthError(msg)

        self._refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > 0:
            buffer_seconds = min(TOKEN_EXPIRY_BUFFER, int(expires_in))
            self._token_expiry = datetime.now(UTC_TZ) + timedelta(
                seconds=int(expires_in) - buffer_seconds
            )
        else:
            self._token_expiry = None

        self._auth_flow = auth_flow

    def _authenticate_client_credentials(self) -> None:
        if not self.keycloak_client_id or not self.client_secret:
            msg = "Client credentials authentication requires keycloak_client_id and client_secret"
            raise QASAuthError(msg)

        data = {
            "grant_type": "client_credentials",
            "client_id": self.keycloak_client_id,
            "client_secret": self.client_secret,
        }

        if self.token_audience:
            data["audience"] = self.token_audience

        if self.scope:
            data["scope"] = self.scope

        token_data = self._execute_token_request(
            data, "Authentication failed using client credentials"
        )
        self._hydrate_tokens(token_data, auth_flow="client_credentials")

    def refresh_access_token(self) -> None:
        """
        Refresh access token using refresh token

        Raises:
            QASAuthError: If token refresh fails
        """
        if self._auth_flow == "client_credentials":
            # Client credential tokens typically cannot be refreshed; request a new one.
            self._authenticate_client_credentials()
            return

        if self._auth_flow == "external":
            if self._token_provider is not None:
                self._access_token = self._token_provider()
                # Expiry unknown for provider-supplied tokens; clear so we
                # don't loop on an immediate re-check.
                self._token_expiry = None
                return

            if self._refresh_token:
                data = {
                    "grant_type": "refresh_token",
                    "client_id": self.keycloak_client_id,
                    "refresh_token": self._refresh_token,
                }
                token_data = self._execute_token_request(data, "Token refresh failed")
                # Preserve "external" flow label; _hydrate_tokens stores the new
                # refresh token returned by Keycloak so the chain continues.
                self._hydrate_tokens(token_data, auth_flow="external")
                self._persist_external_auth_tokens()
                return

            msg = (
                "Access token has expired and cannot be refreshed automatically. "
                "Provide a refresh_token or token_provider when constructing QASClient, "
                "or obtain a new access token and create a fresh client instance."
            )
            raise QASAuthError(msg)

        self.authenticate()

    def _ensure_token_valid(self) -> None:
        """Ensure access token is valid, refresh if needed"""
        if not self._access_token:
            msg = "No access token. Call authenticate() first."
            raise QASAuthError(msg)

        if self._token_expiry and datetime.now(UTC_TZ) >= self._token_expiry:
            self.refresh_access_token()

    def _get_headers(self) -> dict[str, str]:
        """Get headers with authentication"""
        self._ensure_token_valid()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs: object) -> dict:
        """
        Make authenticated API request

        Args:
            method: HTTP method
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Response JSON data

        Raises:
            QASAPIError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            response = e.response
            if response is not None and response.status_code == 401:
                # Token expired, try to refresh and retry once
                self.refresh_access_token()
                headers = self._get_headers()
                response = requests.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()
            detail = None
            if response is not None:
                try:
                    payload = response.json()
                    detail = payload.get("detail") or payload.get("message")
                except ValueError:
                    detail = response.text.strip() if response.text else None
            error_message = f"API request failed: {e!s}"
            if detail:
                error_message = f"API request failed: {detail}"
                if isinstance(detail, str) and "term" in detail.lower():
                    error_message = (
                        f"{error_message}. Please accept the Terms & Conditions and retry."
                    )
            raise QASAPIError(error_message) from e

        except requests.exceptions.RequestException as e:
            msg = f"API request failed: {e!s}"
            raise QASAPIError(msg) from e

    # Circuit Compression Methods

    def _compression_endpoint(self, suffix: str) -> str:
        if not suffix.startswith("/"):
            suffix = f"/{suffix}"
        return f"{self.compression_api_prefix}{suffix}"

    def submit_compression(
        self,
        circuit: str,
        *,
        num_gpus: int | None = None,
        iteration_time_minutes: int | None = None,
        gate_set: str | None = None,
        goal: str | None = None,
        hpc_mode: str | None = None,
        options: CompressionJobOptions | None = None,
    ) -> dict:
        """
        Submit circuit for compression on the configured HPC backend.

        Args:
            circuit: OpenQASM 2.0 circuit code
            num_gpus: Optional number of GPUs to request for real backends
            iteration_time_minutes: Optional iteration time budget in minutes
            gate_set: Optional logical gate set slug (for example "IBM-Eagle")
            goal: Optional compression objective (for example "depth" or "twoqubit")
            hpc_mode: Optional HPC mode override (for example "demo")
            options: Optional CompressionJobOptions bundle; individual kwargs override it

        Returns:
            Job information including job_id and status

        Example:
            >>> circuit = '''OPENQASM 2.0;
            ... include "qelib1.inc";
            ... qreg q[3];
            ... creg c[3];
            ... h q[0];
            ... cx q[0], q[1];
            ... measure q -> c;'''
            >>> job = client.submit_compression(circuit, num_gpus=2)
            >>> print(job['job_id'])
        """
        data: dict[str, Any] = {"circuit": circuit}

        if options is not None:
            data.update(options.to_payload())

        if num_gpus is not None:
            data["num_gpus"] = num_gpus
        if iteration_time_minutes is not None:
            data["iteration_time_minutes"] = iteration_time_minutes
        if gate_set is not None:
            data["gate_set"] = gate_set
        if goal is not None:
            data["goal"] = goal
        if hpc_mode is not None:
            data["hpc_mode"] = hpc_mode

        return self._request("POST", self._compression_endpoint("/jobs"), json=data)

    def get_compression_job(self, job_id: str) -> dict:
        """
        Get compression job status and results

        Args:
            job_id: Job ID from submit_compression

        Returns:
            Job information including status, result, logs

        Example:
            >>> job_info = client.get_compression_job("550e8400-e29b-41d4-a716-446655440000")
            >>> print(job_info['status'])
            'COMPLETED'
        """
        return self._request("GET", self._compression_endpoint(f"/jobs/{job_id}"))

    def stop_compression_job(self, job_id: str) -> dict:
        """
        Stop a running compression job while preserving any partial results.

        Args:
            job_id: Job ID from submit_compression

        Returns:
            Job information reflecting the stop request

        Example:
            >>> job_info = client.stop_compression_job("550e8400-e29b-41d4-a716-446655440000")
            >>> print(job_info["status"])
            'STOPPED'
        """
        stop_endpoint = self._compression_endpoint(f"/jobs/{job_id}/stop")
        try:
            return self._request("POST", stop_endpoint)
        except QASAPIError as exc:
            # Keep compatibility with older API deployments that only exposed DELETE /jobs/{id}.
            error_text = str(exc).lower()
            if (
                "not found" in error_text
                or "method not allowed" in error_text
                or "404" in error_text
                or "405" in error_text
            ):
                return self._request("DELETE", self._compression_endpoint(f"/jobs/{job_id}"))
            raise

    def cancel_compression_job(self, job_id: str) -> dict:
        """
        Backward-compatible alias for stop_compression_job.
        """
        return self.stop_compression_job(job_id)

    def list_compression_jobs(self, limit: int = 50) -> list[dict]:
        """
        List all compression jobs for current user

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of job information dictionaries

        Example:
            >>> jobs = client.list_compression_jobs(limit=10)
            >>> for job in jobs:
            ...     print(f"{job['id']}: {job['status']}")
        """
        response = self._request("GET", self._compression_endpoint(f"/jobs?limit={limit}"))
        return response.get("jobs", [])

    def get_hpc_mode(self) -> dict:
        """
        Get the current HPC mode and available modes.

        Returns:
            Dictionary including current mode details and available modes.

        Example:
            >>> mode_info = client.get_hpc_mode()
            >>> print(mode_info["mode"])
        """
        return self._request("GET", self._compression_endpoint("/hpc-mode"))

    def list_hpc_modes(self) -> list[dict]:
        """
        List available HPC modes for compression.

        Returns:
            List of available mode dictionaries.

        Example:
            >>> modes = client.list_hpc_modes()
            >>> print(modes[0]["mode"])
        """
        response = self.get_hpc_mode()
        return response.get("available_modes", [])

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: int = 5,
        timeout: int | None = None,
        callback: Callable[[dict], None] | None = None,
    ) -> dict:
        """
        Wait for compression job to complete

        Args:
            job_id: Job ID to wait for
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait (None = no timeout)
            callback: Optional function to call with job status on each poll

        Returns:
            Final job information with results

        Raises:
            TimeoutError: If timeout is reached
            QASAPIError: If job fails

        Example:
            >>> def progress(job):
            ...     print(f"Status: {job['status']}")
            >>> result = client.wait_for_job(job_id, callback=progress)
            >>> print(result['result'])
        """
        start_time = time.time()

        while True:
            job = self.get_compression_job(job_id)

            if callback:
                callback(job)

            status = job.get("status")

            if status == "COMPLETED":
                return job
            if status == "FAILED":
                error = job.get("error", "Unknown error")
                msg = f"Job failed: {error}"
                raise QASAPIError(msg)
            if status in {"CANCELLED", "STOPPED"}:
                return job

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                msg = f"Job {job_id} did not complete within {timeout} seconds"
                raise TimeoutError(msg)

            time.sleep(poll_interval)

    # Quantum Device Methods

    def list_devices(self) -> list[dict]:
        """
        List available AWS Braket quantum devices

        Returns:
            List of device information dictionaries

        Example:
            >>> devices = client.list_devices()
            >>> for device in devices:
            ...     print(f"{device['name']}: {device['status']}")
        """
        response = self._request("GET", "/api/devices")
        return response.get("devices", [])

    def submit_circuit(
        self,
        circuit: str,
        device_arn: str,
        shots: int = 1000,
        device_region: str | None = None,
    ) -> dict:
        """
        Submit circuit for execution on quantum device

        Args:
            circuit: OpenQASM 2.0 circuit code
            device_arn: AWS Braket device ARN
            shots: Number of shots to execute
            device_region: AWS region (extracted from ARN if not provided)

        Returns:
            Job information

        Example:
            >>> job = client.submit_circuit(
            ...     circuit=my_circuit,
            ...     device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            ...     shots=1000
            ... )
        """
        data = {
            "openqasm": circuit,
            "device_arn": device_arn,
            "shots": shots,
        }
        if device_region:
            data["device_region"] = device_region

        return self._request("POST", "/api/submit", json=data)

    def get_job_results(self, job_id: str) -> dict:
        """
        Get results from quantum circuit execution

        Args:
            job_id: AWS Braket job ID (ARN)

        Returns:
            Job results including counts and metadata

        Example:
            >>> results = client.get_job_results(job_arn)
            >>> print(results['counts'])
            {'000': 450, '111': 550}
        """
        return self._request("GET", f"/api/result/{job_id}")

    def get_job_status(self, job_id: str) -> dict:
        """
        Get status of quantum circuit execution

        Args:
            job_id: AWS Braket job ID (ARN)

        Returns:
            Job status information

        Example:
            >>> status = client.get_job_status(job_arn)
            >>> print(status['status'])
            'COMPLETED'
        """
        return self._request("GET", f"/api/status/{job_id}")


# Convenience functions for common workflows


def compress_and_wait(
    client: QASClient,
    circuit: str,
    poll_interval: int = 10,
    *,
    verbose: bool = True,
    **submit_kwargs: object,
) -> dict:
    """
    Submit circuit compression and wait for result

    Args:
        client: QASClient instance
        circuit: OpenQASM circuit to compress
        poll_interval: Seconds between status checks
        verbose: Print progress messages
        **submit_kwargs: Additional submit_compression keyword arguments

    Returns:
        Job result with compressed circuit
    """
    if verbose:
        print("Submitting circuit for compression...")

    job = client.submit_compression(circuit, **submit_kwargs)
    job_id = job["job_id"]

    if verbose:
        print(f"Job submitted: {job_id}")
        print("Waiting for compression to complete (this may take several hours)...")

    def progress_callback(job_info: object) -> None:
        if verbose:
            status = job_info.get("status")
            print(f"Status: {status}")
            if job_info.get("logs"):
                print("Latest logs:")
                print(job_info["logs"][-500:])  # Last 500 chars

    result = client.wait_for_job(job_id, poll_interval=poll_interval, callback=progress_callback)

    if verbose:
        print("Compression complete!")
        print(f"Compressed circuit:\n{result['result']}")

    return result


if __name__ == "__main__":
    # Example usage
    import sys

    # Create client
    try:
        client = QASClient(base_url="https://qas.qmill.com")
    except QASAuthError:
        print("Run `qas auth login --base-url https://qas.qmill.com` first.")
        sys.exit(1)

    # Example circuit
    circuit = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;"""

    # Submit and wait
    result = compress_and_wait(client, circuit, verbose=True)
