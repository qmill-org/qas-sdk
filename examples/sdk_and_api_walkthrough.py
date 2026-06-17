#!/usr/bin/env python3
"""SDK and Direct API walkthrough for external QMill Circuit Compression users.

This script performs the following steps:
1. Loads credentials from a `qas auth login` session.
2. Instantiates the QMill Circuit Compression SDK client and submits a sample compression job.
3. Waits for completion and displays the compressed circuit.
4. Calls the REST API directly with the same SDK-managed bearer token to fetch the job payload.

Run from the repository root after installing the SDK (see README in this directory).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import requests

from qas_sdk import CompressionJobOptions, QASClient


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive parsing
        msg = f"Environment variable {name} must be an integer"
        raise RuntimeError(msg) from exc


def _print_json(title: str, payload: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cli_token() -> str:
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
        msg = "Empty token received from CLI."
        raise RuntimeError(msg)
    return token


def main() -> int:
    base_url = os.getenv("QAS_BASE_URL", "https://qas.qmill.com").rstrip("/")

    print(f"Connecting to QAS at {base_url}")

    client = QASClient(base_url=base_url)
    print("Authenticated with SDK using local CLI session state.")

    mod5_4_circuit = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
x q[4];
rz(pi/2) q[4];
sx q[4];
rz(pi/2) q[4];
cx q[3],q[4];
rz(-pi/4) q[4];
cx q[0],q[4];
rz(pi/4) q[4];
cx q[3],q[4];
rz(-pi/4) q[4];
cx q[0],q[4];
cx q[0],q[3];
rz(-pi/4) q[3];
cx q[0],q[3];
rz(pi/4) q[0];
rz(pi/4) q[3];
rz(pi/4) q[4];
cx q[3],q[4];
rz(-pi/4) q[4];
cx q[2],q[4];
rz(pi/4) q[4];
cx q[3],q[4];
rz(-pi/4) q[4];
cx q[2],q[4];
cx q[2],q[3];
rz(-pi/4) q[3];
cx q[2],q[3];
rz(pi/4) q[2];
rz(pi/4) q[3];
rz(pi/4) q[4];
rz(pi/2) q[4];
sx q[4];
rz(pi/2) q[4];
cx q[3],q[4];
rz(pi/2) q[4];
sx q[4];
rz(pi/2) q[4];
cx q[2],q[4];
rz(-pi/4) q[4];
cx q[1],q[4];
rz(pi/4) q[4];
cx q[2],q[4];
rz(-pi/4) q[4];
cx q[1],q[4];
cx q[1],q[2];
rz(-pi/4) q[2];
cx q[1],q[2];
rz(pi/4) q[1];
rz(pi/4) q[2];
rz(pi/4) q[4];
rz(pi/2) q[4];
sx q[4];
rz(pi/2) q[4];
cx q[2],q[4];
rz(pi/2) q[4];
sx q[4];
rz(pi/2) q[4];
cx q[1],q[4];
rz(-pi/4) q[4];
cx q[0],q[4];
rz(pi/4) q[4];
cx q[1],q[4];
rz(-pi/4) q[4];
cx q[0],q[4];
cx q[0],q[1];
rz(-pi/4) q[1];
cx q[0],q[1];
rz(pi/4) q[0];
rz(pi/4) q[1];
rz(pi/4) q[4];
rz(pi/2) q[4];
sx q[4];
rz(pi/2) q[4];
cx q[1],q[4];
cx q[0],q[4];"""

    compression_kwargs: dict[str, Any] = {}

    num_gpus = _optional_int("QAS_NUM_GPUS")
    if num_gpus is not None:
        compression_kwargs["num_gpus"] = num_gpus

    options = CompressionJobOptions(
        iteration_time_minutes=_optional_int("QAS_ITERATION_MINUTES"),
        gate_set=os.getenv("QAS_GATE_SET"),
        hpc_mode=os.getenv("QAS_HPC_MODE"),
    )
    if options.to_payload():
        compression_kwargs["options"] = options

    if compression_kwargs:
        print("Submitting compression job via SDK with overrides...")
    else:
        print("Submitting compression job via SDK...")

    job = client.submit_compression(mod5_4_circuit, **compression_kwargs)
    job_id = job["job_id"]
    print(f"Job submitted with ID: {job_id}")

    result = client.wait_for_job(job_id, poll_interval=5, timeout=600)
    print("Compression completed via SDK.")
    _print_json("SDK Result", result)

    print("\nRequesting job payload directly via REST API...")
    auth_header = f"Bearer {_cli_token()}"
    job_url = f"{base_url}/api/public/v1/circuit-compression/jobs/{job_id}"
    response = requests.get(
        job_url,
        headers={
            "Authorization": auth_header,
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    api_payload = response.json()
    _print_json("Direct API Result", api_payload)

    print("\nWorkflow complete. SDK and direct API responses should align on status/result fields.")
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
