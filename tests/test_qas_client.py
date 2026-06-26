"""
Unit tests for QAS SDK

Tests the core functionality of the QASClient class including:
- Initialization
- Error handling
- Method signatures
- Basic functionality
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from qas_sdk import CompressionJobOptions, QASAPIError, QASAuthError, QASClient

UTC_TZ = timezone(timedelta(0))


class TestQASClient:
    """Test suite for QASClient class"""

    def test_init_with_client_credentials(self) -> None:
        """Client credentials trigger authentication on init."""
        with patch.object(QASClient, "authenticate") as mock_auth:
            client = QASClient(
                base_url="https://test.example.com",
                keycloak_client_id="qas_sdk",
                client_secret="secret",
            )

            assert client.client_secret == "secret"
            assert client.keycloak_client_id == "qas_sdk"
            mock_auth.assert_called_once()

    def test_init_with_token(self) -> None:
        """Test client initialization with access token"""
        client = QASClient(base_url="https://test.example.com", access_token="test_token")

        assert client._access_token == "test_token"
        assert client._auth_flow == "external"

    def test_authenticate_no_credentials(self) -> None:
        """Test authentication without credentials"""
        client = QASClient(base_url="https://test.example.com", auto_authenticate=False)

        with pytest.raises(QASAuthError, match="No authentication credentials available"):
            client.authenticate()

    def test_authenticate_uses_client_credentials(self) -> None:
        """Client credentials flow should be preferred when available."""
        client = QASClient(
            base_url="https://test.example.com",
            keycloak_client_id="sdk",
            client_secret="secret",
            auto_authenticate=False,
        )

        with patch.object(client, "_authenticate_client_credentials") as mock_client:
            client.authenticate()

        mock_client.assert_called_once()

    def test_init_loads_matching_stored_tokens(self) -> None:
        """Stored CLI auth should auto-hydrate token auth when context matches."""
        stored = {
            "base_url": "https://test.example.com",
            "keycloak_realm": "quantum-platform",
            "keycloak_client_id": "quantum-app",
            "access_token": "stored_access",
            "refresh_token": "stored_refresh",
            "access_token_expires_at": "2030-01-01T00:00:00+00:00",
        }

        with patch("qas_sdk.client.load_auth_state", return_value=stored):
            client = QASClient(base_url="https://test.example.com")

        assert client._access_token == "stored_access"
        assert client._refresh_token == "stored_refresh"
        assert client._auth_flow == "external"

    def test_init_ignores_non_matching_stored_tokens(self) -> None:
        """Stored auth should be ignored when base URL does not match the client."""
        stored = {
            "base_url": "https://other.example.com",
            "keycloak_realm": "quantum-platform",
            "keycloak_client_id": "quantum-app",
            "access_token": "stored_access",
        }

        with patch("qas_sdk.client.load_auth_state", return_value=stored):
            client = QASClient(base_url="https://test.example.com")

        assert client._access_token is None

    def test_refresh_access_token_client_credentials(self) -> None:
        """Refreshing client-credential tokens requests a new token."""
        client = QASClient(
            base_url="https://test.example.com",
            keycloak_client_id="sdk",
            client_secret="secret",
            auto_authenticate=False,
        )
        client._auth_flow = "client_credentials"

        with patch.object(client, "_authenticate_client_credentials") as mock_client:
            client.refresh_access_token()

        mock_client.assert_called_once()

    def test_refresh_access_token_external_token_no_refresh(self) -> None:
        """Clear error when external token expires and no refresh mechanism is set."""
        client = QASClient(
            base_url="https://test.example.com",
            access_token="token",
        )

        with pytest.raises(QASAuthError, match="cannot be refreshed automatically"):
            client.refresh_access_token()

    def test_refresh_access_token_external_uses_refresh_token(self) -> None:
        """refresh_token parameter lets the SDK silently renew an external access token."""
        client = QASClient(
            base_url="https://test.example.com",
            access_token="old_token",
            refresh_token="rt_initial",
        )

        new_token_data = {
            "access_token": "new_access_token",
            "refresh_token": "rt_rotated",
            "expires_in": 900,
        }

        with (
            patch.object(client, "_execute_token_request", return_value=new_token_data),
            patch.object(client, "_persist_external_auth_tokens") as mock_persist,
        ):
            client.refresh_access_token()

        assert client._access_token == "new_access_token"
        assert client._refresh_token == "rt_rotated"
        assert client._auth_flow == "external"
        mock_persist.assert_called_once()

    def test_refresh_access_token_external_uses_token_provider(self) -> None:
        """token_provider callback is called to obtain a fresh token."""
        call_count = [0]

        def my_provider() -> str:
            call_count[0] += 1
            return "provider_token"

        client = QASClient(
            base_url="https://test.example.com",
            access_token="old_token",
            token_provider=my_provider,
        )

        client.refresh_access_token()

        assert client._access_token == "provider_token"
        assert call_count[0] == 1

    def test_token_provider_takes_precedence_over_refresh_token(self) -> None:
        """When both token_provider and refresh_token are supplied, provider wins."""
        provider_called = [False]

        def my_provider() -> str:
            provider_called[0] = True
            return "provider_token"

        client = QASClient(
            base_url="https://test.example.com",
            access_token="old_token",
            refresh_token="rt",
            token_provider=my_provider,
        )

        with patch.object(client, "_execute_token_request") as mock_req:
            client.refresh_access_token()

        assert provider_called[0] is True
        mock_req.assert_not_called()

    def test_wait_for_job_timeout(self) -> None:
        """Test wait_for_job timeout"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        # Mock get_compression_job to always return RUNNING
        with patch.object(client, "get_compression_job") as mock_get:
            mock_get.return_value = {"status": "RUNNING"}

            with pytest.raises(TimeoutError, match="did not complete within"):
                client.wait_for_job("test-job", poll_interval=1, timeout=1)

    def test_wait_for_job_failure(self) -> None:
        """Test wait_for_job when job fails"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        # Mock get_compression_job to return FAILED
        with patch.object(client, "get_compression_job") as mock_get:
            mock_get.return_value = {
                "status": "FAILED",
                "error": "Compression algorithm failed",
            }

            with pytest.raises(QASAPIError, match="Job failed"):
                client.wait_for_job("test-job")

    def test_wait_for_job_success(self) -> None:
        """Test wait_for_job successful completion"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        final_result = {
            "status": "COMPLETED",
            "result": "compressed_circuit",
            "compression_ratio": 0.7,
        }

        # Mock get_compression_job to return COMPLETED
        with patch.object(client, "get_compression_job") as mock_get:
            mock_get.return_value = final_result

            result = client.wait_for_job("test-job")
            assert result == final_result

    def test_callback_function(self) -> None:
        """Test wait_for_job with callback"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        callback_calls = []

        def test_callback(job_info: object) -> None:
            callback_calls.append(job_info["status"])

        final_result = {"status": "COMPLETED", "result": "done"}

        with patch.object(client, "get_compression_job") as mock_get:
            mock_get.return_value = final_result

            client.wait_for_job("test-job", callback=test_callback)

            assert "COMPLETED" in callback_calls

    def test_base_url_stripping(self) -> None:
        """Test that trailing slashes are stripped from base_url"""
        client = QASClient(base_url="https://test.example.com/", access_token="token")
        assert client.base_url == "https://test.example.com"

    def test_headers_generation(self) -> None:
        """Test that headers are generated correctly"""
        client = QASClient(base_url="https://test.example.com", access_token="test_token")

        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"

    def test_token_expiry_check(self) -> None:
        """Test token expiry validation"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        # Set expired token
        client._token_expiry = datetime.now(UTC_TZ) - timedelta(seconds=1)

        with patch.object(client, "refresh_access_token") as mock_refresh:
            client._ensure_token_valid()
            mock_refresh.assert_called_once()

    def test_no_token_error(self) -> None:
        """Test error when no token is available"""
        client = QASClient(base_url="https://test.example.com")

        with pytest.raises(QASAuthError, match="No access token"):
            client._ensure_token_valid()


class TestSDKMethods:
    """Test SDK method signatures and basic behavior"""

    def test_compression_methods_exist(self) -> None:
        """Test that compression methods exist with correct signatures"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        # Check methods exist
        assert hasattr(client, "submit_compression")
        assert hasattr(client, "get_compression_job")
        assert hasattr(client, "list_compression_jobs")
        assert hasattr(client, "wait_for_job")

    def test_quantum_methods_exist(self) -> None:
        """Test that quantum device methods exist with correct signatures"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        # Check methods exist
        assert hasattr(client, "list_devices")
        assert hasattr(client, "submit_circuit")
        assert hasattr(client, "get_job_results")

    def test_auth_methods_exist(self) -> None:
        """Test that authentication methods exist"""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        assert hasattr(client, "authenticate")
        assert hasattr(client, "refresh_access_token")

    def test_submit_compression_with_kwargs(self) -> None:
        """submit_compression should forward optional fields when provided."""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        with patch.object(client, "_request") as mock_request:
            mock_request.return_value = {"job_id": "abc", "status": "SUBMITTED"}
            client.submit_compression(
                "OPENQASM 2.0;",
                num_gpus=2,
                iteration_time_minutes=90,
                gate_set="IBM-Eagle",
                goal="twoqubit",
                hpc_mode="demo",
            )

        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert args[1] == "/api/public/v1/circuit-compression/jobs"
        assert kwargs["json"] == {
            "circuit": "OPENQASM 2.0;",
            "num_gpus": 2,
            "iteration_time_minutes": 90,
            "gate_set": "IBM-Eagle",
            "goal": "twoqubit",
            "hpc_mode": "demo",
        }

    def test_submit_compression_options_dataclass(self) -> None:
        """CompressionJobOptions should populate defaults and allow overrides."""
        client = QASClient(base_url="https://test.example.com", access_token="token")
        options = CompressionJobOptions(
            num_gpus=4,
            iteration_time_minutes=30,
            gate_set="IonQ",
            goal="depth",
            hpc_mode="aws_v1_5",
        )

        with patch.object(client, "_request") as mock_request:
            mock_request.return_value = {"job_id": "xyz", "status": "SUBMITTED"}
            client.submit_compression(
                "OPENQASM 2.0;",
                options=options,
                num_gpus=1,
                goal="total",
            )

        _, kwargs = mock_request.call_args
        payload = kwargs["json"]
        assert payload["circuit"] == "OPENQASM 2.0;"
        # explicit kwargs should override dataclass values
        assert payload["num_gpus"] == 1
        assert payload["iteration_time_minutes"] == 30
        assert payload["gate_set"] == "IonQ"
        assert payload["goal"] == "total"
        assert payload["hpc_mode"] == "aws_v1_5"

    def test_stop_compression_prefers_post_stop_endpoint(self) -> None:
        """stop_compression_job should use POST /jobs/{id}/stop on modern API deployments."""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        with patch.object(client, "_request") as mock_request:
            mock_request.return_value = {"status": "COMPLETED"}
            client.stop_compression_job("job-123")

        mock_request.assert_called_once_with(
            "POST",
            "/api/public/v1/circuit-compression/jobs/job-123/stop",
        )

    def test_stop_compression_falls_back_to_delete_for_legacy_api(self) -> None:
        """stop_compression_job should fall back to DELETE /jobs/{id} for legacy API routes."""
        client = QASClient(base_url="https://test.example.com", access_token="token")

        with patch.object(client, "_request") as mock_request:
            mock_request.side_effect = [
                QASAPIError("API request failed: Not Found"),
                {"status": "COMPLETED"},
            ]
            result = client.stop_compression_job("job-legacy")

        assert result == {"status": "COMPLETED"}
        assert mock_request.call_count == 2
        first_call = mock_request.call_args_list[0].args
        second_call = mock_request.call_args_list[1].args
        assert first_call == (
            "POST",
            "/api/public/v1/circuit-compression/jobs/job-legacy/stop",
        )
        assert second_call == (
            "DELETE",
            "/api/public/v1/circuit-compression/jobs/job-legacy",
        )


if __name__ == "__main__":
    pytest.main([__file__])
