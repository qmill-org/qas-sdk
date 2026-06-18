#!/usr/bin/env python3
"""SDK-only walkthrough for external QMill Circuit Compression users.

This script demonstrates the SDK flow only:
1. Load credentials from a `qas auth login` session.
2. Submit a compression job with optional overrides.
3. Wait for completion and print the final payload fields.

Run from the repository root after installing the SDK.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from qas_sdk.client import CompressionJobOptions, QASClient

DEFAULT_GATE_SET = "IBM-Eagle"


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive parsing
        msg = f"Environment variable {name} must be an integer"
        raise RuntimeError(msg) from exc


def _normalized_gate_set_from_env() -> str | None:
    raw = os.getenv("QAS_GATE_SET")
    if raw is None:
        return None
    value = raw.strip()
    return value if value else DEFAULT_GATE_SET


def _print_json(title: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, sort_keys=True))


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
        gate_set=_normalized_gate_set_from_env(),
        hpc_mode=os.getenv("QAS_HPC_MODE"),
    )
    if options.to_payload():
        compression_kwargs["options"] = options

    if compression_kwargs:
        print("Submitting compression job via SDK with overrides...")
    else:
        print("Submitting compression job via SDK...")

    submit_payload = {
        "circuit": "mod5_4",
        "overrides": {
            "num_gpus": compression_kwargs.get("num_gpus"),
            "options": options.to_payload() if options.to_payload() else None,
        },
    }
    _print_json("SDK Submit Parameters", submit_payload)

    job = client.submit_compression(mod5_4_circuit, **compression_kwargs)
    job_id = job["job_id"]
    print(f"Job submitted with ID: {job_id}")

    result = client.wait_for_job(job_id, poll_interval=5, timeout=600)
    _print_json("SDK Final Payload", result)

    print("\nWorkflow complete.")
    print("Status:", result.get("status"))
    print("Compressed circuit:", result.get("result"))
    print("Credits charged:", result.get("credits_charged"))
    print("Remaining credits:", result.get("remaining_credits"))
    print("Transpiled circuit (optional):", result.get("transpiled_circuit"))
    print("Compressed metrics (optional):", result.get("compressed_metrics"))
    print("Transpiled metrics (optional):", result.get("transpiled_metrics"))

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
