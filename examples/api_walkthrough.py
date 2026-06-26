#!/usr/bin/env python3
"""Plain REST API walkthrough for QMill circuit compression jobs.

This script demonstrates how to submit a compression job and retrieve the
results using raw HTTP requests. It authenticates by retrieving a bearer token
from the `qas auth token` CLI command.

Run from the repository root after installing dependencies (``pip install requests``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

import requests

POLL_INTERVAL_SECONDS = int(os.getenv("QAS_POLL_INTERVAL", "5"))
POLL_TIMEOUT_SECONDS = int(os.getenv("QAS_POLL_TIMEOUT", "300"))
DEFAULT_GATE_SET = "CX_RX_RZ"


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        msg = f"Environment variable {name} must be an integer"
        raise RuntimeError(msg) from exc


def _normalized_gate_set_from_env() -> str | None:
    raw = os.getenv("QAS_GATE_SET")
    if raw is None:
        return DEFAULT_GATE_SET
    value = raw.strip()
    return value if value else DEFAULT_GATE_SET


def _obtain_bearer_token() -> str:
    try:
        result = subprocess.run(
            ["qas", "auth", "token"],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        msg = "Unable to retrieve token from CLI. Run `qas auth login` first."
        raise RuntimeError(msg) from exc

    token = result.stdout.strip()
    if not token:
        msg = "Empty token received from CLI. Run `qas auth login` again."
        raise RuntimeError(msg)
    return token


def _auth_headers(base_headers: dict[str, str]) -> dict[str, str]:
    headers = dict(base_headers)
    headers["Authorization"] = f"Bearer {_obtain_bearer_token()}"
    return headers


def _request_with_fresh_auth(
    method: str,
    url: str,
    *,
    base_headers: dict[str, str],
    timeout: int,
    **kwargs: Any,
) -> requests.Response:
    response = requests.request(
        method,
        url,
        headers=_auth_headers(base_headers),
        timeout=timeout,
        **kwargs,
    )
    if response.status_code == 401:
        # Refresh via `qas auth token` and retry once for expired short-lived tokens.
        response = requests.request(
            method,
            url,
            headers=_auth_headers(base_headers),
            timeout=timeout,
            **kwargs,
        )
    return response


def _build_job_payload(circuit: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"circuit": circuit}

    num_gpus = _optional_int("QAS_NUM_GPUS")
    if num_gpus is not None:
        payload["num_gpus"] = num_gpus

    iteration_minutes = _optional_int("QAS_ITERATION_MINUTES")
    if iteration_minutes is not None:
        payload["iteration_time_minutes"] = iteration_minutes

    gate_set = _normalized_gate_set_from_env()
    if gate_set:
        payload["gate_set"] = gate_set

    hpc_mode = os.getenv("QAS_HPC_MODE")
    if hpc_mode:
        payload["hpc_mode"] = hpc_mode

    return payload


def _print_json(title: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _poll_job(base_url: str, job_id: str, base_headers: dict[str, str]) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    job_url = f"{base_url}/api/public/v1/circuit-compression/jobs/{job_id}"

    while True:
        response = _request_with_fresh_auth(
            "GET",
            job_url,
            base_headers=base_headers,
            timeout=30,
        )
        response.raise_for_status()
        job_payload = response.json()

        status = job_payload.get("status")
        if status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return job_payload

        if time.monotonic() > deadline:
            msg = f"Job {job_id} did not complete within {POLL_TIMEOUT_SECONDS} seconds"
            raise TimeoutError(msg)

        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> int:
    base_url = os.getenv("QAS_BASE_URL", "https://qas.qmill.com").rstrip("/")
    print(f"Connecting to QAS at {base_url}")

    base_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    mod5_4_circuit = (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        "qreg q[5];\n"
        "x q[4];\n"
        "rz(pi/2) q[4];\n"
        "sx q[4];\n"
        "rz(pi/2) q[4];\n"
        "cx q[3],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[0],q[4];\n"
        "rz(pi/4) q[4];\n"
        "cx q[3],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[0],q[4];\n"
        "cx q[0],q[3];\n"
        "rz(-pi/4) q[3];\n"
        "cx q[0],q[3];\n"
        "rz(pi/4) q[0];\n"
        "rz(pi/4) q[3];\n"
        "rz(pi/4) q[4];\n"
        "cx q[3],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[2],q[4];\n"
        "rz(pi/4) q[4];\n"
        "cx q[3],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[2],q[4];\n"
        "cx q[2],q[3];\n"
        "rz(-pi/4) q[3];\n"
        "cx q[2],q[3];\n"
        "rz(pi/4) q[2];\n"
        "rz(pi/4) q[3];\n"
        "rz(pi/4) q[4];\n"
        "rz(pi/2) q[4];\n"
        "sx q[4];\n"
        "rz(pi/2) q[4];\n"
        "cx q[3],q[4];\n"
        "rz(pi/2) q[4];\n"
        "sx q[4];\n"
        "rz(pi/2) q[4];\n"
        "cx q[2],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[1],q[4];\n"
        "rz(pi/4) q[4];\n"
        "cx q[2],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[1],q[4];\n"
        "cx q[1],q[2];\n"
        "rz(-pi/4) q[2];\n"
        "cx q[1],q[2];\n"
        "rz(pi/4) q[1];\n"
        "rz(pi/4) q[2];\n"
        "rz(pi/4) q[4];\n"
        "rz(pi/2) q[4];\n"
        "sx q[4];\n"
        "rz(pi/2) q[4];\n"
        "cx q[2],q[4];\n"
        "rz(pi/2) q[4];\n"
        "sx q[4];\n"
        "rz(pi/2) q[4];\n"
        "cx q[1],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[0],q[4];\n"
        "rz(pi/4) q[4];\n"
        "cx q[1],q[4];\n"
        "rz(-pi/4) q[4];\n"
        "cx q[0],q[4];\n"
        "cx q[0],q[1];\n"
        "rz(-pi/4) q[1];\n"
        "cx q[0],q[1];\n"
        "rz(pi/4) q[0];\n"
        "rz(pi/4) q[1];\n"
        "rz(pi/4) q[4];\n"
        "rz(pi/2) q[4];\n"
        "sx q[4];\n"
        "rz(pi/2) q[4];\n"
        "cx q[1],q[4];\n"
        "cx q[0],q[4];"
    )

    job_payload = _build_job_payload(mod5_4_circuit)
    _print_json("Submitting Compression Job", job_payload)

    submission = _request_with_fresh_auth(
        "POST",
        f"{base_url}/api/public/v1/circuit-compression/jobs",
        base_headers=base_headers,
        json=job_payload,
        timeout=30,
    )
    submission.raise_for_status()
    job_info = submission.json()
    job_id = job_info["job_id"]
    _print_json("Submission Response", job_info)

    print(f"Polling job {job_id} every {POLL_INTERVAL_SECONDS}s...")
    result_payload = _poll_job(base_url, job_id, base_headers)
    _print_json("Final Job Payload", result_payload)

    print("\nAPI workflow complete. Job status:", result_payload.get("status"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)
