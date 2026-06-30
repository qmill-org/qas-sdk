import subprocess

import pytest
import requests

from examples import api_walkthrough
from examples import sdk_and_api_walkthrough as walkthrough


def _mock_response(payload: object, status_code: int = 200) -> object:
    class _Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                msg = f"HTTP {self.status_code}"
                raise requests.HTTPError(msg)
            return None

        def json(self) -> object:
            return payload

    return _Response(status_code)


def test_api_walkthrough_poll_refreshes_token_after_401(monkeypatch: object) -> None:
    """Polling should recover from token expiry by refreshing auth and retrying once."""
    monkeypatch.setenv("QAS_BASE_URL", "https://example.test")
    monkeypatch.setenv("QAS_WAIT_FOR_COMPLETION", "true")
    monkeypatch.setattr(api_walkthrough, "POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(api_walkthrough, "POLL_TIMEOUT_SECONDS", 30)

    token_calls: list[str] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        _ = (args, kwargs)
        token = f"token-{len(token_calls) + 1}"
        token_calls.append(token)
        return subprocess.CompletedProcess(
            args=["qas", "auth", "token"],
            returncode=0,
            stdout=f"{token}\n",
            stderr="",
        )

    monkeypatch.setattr(api_walkthrough.subprocess, "run", fake_run)

    responses = [
        _mock_response({"job_id": "job-123", "status": "SUBMITTED"}),
        _mock_response({"detail": "Unauthorized"}, status_code=401),
        _mock_response({"job_id": "job-123", "status": "COMPLETED", "result": "ok"}),
    ]
    request_calls: list[dict[str, object]] = []

    def fake_request(
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
        **kwargs: object,
    ) -> object:
        request_calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        return responses.pop(0)

    monkeypatch.setattr(api_walkthrough.requests, "request", fake_request)

    exit_code = api_walkthrough.main()

    assert exit_code == 0
    assert len(request_calls) == 3
    assert request_calls[1]["method"] == "GET"
    assert request_calls[2]["method"] == "GET"
    assert (
        request_calls[1]["headers"]["Authorization"] != request_calls[2]["headers"]["Authorization"]
    )
    assert len(token_calls) == 3


def test_walkthrough_main_handles_api_call(monkeypatch: object) -> None:
    """Test the walkthrough uses SDK-managed auth for direct API calls."""
    expected_token = "cli-session-token"

    monkeypatch.setenv("QAS_BASE_URL", "https://example.test")
    for var in [
        "QAS_NUM_GPUS",
        "QAS_ITERATION_MINUTES",
        "QAS_GATE_SET",
        "QAS_HPC_MODE",
    ]:
        monkeypatch.delenv(var, raising=False)

    created_clients = []

    class DummyClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_clients.append({"args": args, "kwargs": kwargs})

        def submit_compression(
            self, circuit: object, **compression_kwargs: object
        ) -> dict[str, str]:
            _ = (circuit, compression_kwargs)
            return {"job_id": "job-123"}

        def wait_for_job(
            self, job_id: object, poll_interval: object = 5, timeout: object = 600
        ) -> dict[str, object]:
            _ = (poll_interval, timeout)
            return {
                "job_id": job_id,
                "status": "COMPLETED",
                "original_gate_count": 42,
                "compressed_gate_count": 21,
            }

        def get_compression_job(self, job_id: object) -> dict[str, object]:
            return {
                "job_id": job_id,
                "status": "RUNNING",
            }

    monkeypatch.setattr(walkthrough, "QASClient", DummyClient)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        _ = (args, kwargs)
        return subprocess.CompletedProcess(
            args=["qas", "auth", "token"],
            returncode=0,
            stdout=f"{expected_token}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    requests_calls = []

    def fake_get(url: object, *, headers: object, timeout: object) -> object:
        requests_calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _mock_response({"status": "COMPLETED", "result": "ok"})

    monkeypatch.setattr(walkthrough.requests, "get", fake_get)

    exit_code = walkthrough.main()

    assert exit_code == 0
    assert created_clients, "QASClient should be instantiated"
    assert requests_calls, "Direct API call should be executed"
    assert requests_calls[0]["headers"]["Authorization"] == f"Bearer {expected_token}"


def test_walkthrough_raises_without_credentials(monkeypatch: object) -> None:
    """Test that walkthrough fails when SDK cannot load auth context."""
    for var in ["QAS_CLIENT_ID", "QAS_CLIENT_SECRET"]:
        monkeypatch.delenv(var, raising=False)

    class FailingClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            _ = (args, kwargs)
            msg = "No authentication credentials available"
            raise RuntimeError(msg)

    monkeypatch.setattr(walkthrough, "QASClient", FailingClient)

    with pytest.raises(RuntimeError):
        walkthrough.main()
