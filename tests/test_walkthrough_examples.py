import subprocess

import pytest

from examples import sdk_and_api_walkthrough as walkthrough


def _mock_response(payload: object) -> object:
    class _Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return payload

    return _Response()


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
