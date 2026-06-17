#!/usr/bin/env python3
"""Golden-path external example for the QAS compression API.

Flow:
1) Submit a compression job
2) Poll job status until terminal
3) Print and optionally persist the full final payload
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

import requests

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
DEFAULT_BASE_URL = "https://qas.qmill.com"


def _resolve_token(args: argparse.Namespace) -> str:
    _ = args
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


def _parse_dynamic_value(raw: str) -> object:
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null":
        return None

    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _load_submit_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.request_json:
        with pathlib.Path(args.request_json).open(encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    else:
        if args.circuit_file:
            with pathlib.Path(args.circuit_file).open(encoding="utf-8") as file_obj:
                circuit = file_obj.read()
        elif args.circuit:
            circuit = args.circuit
        else:
            msg = "Provide --request-json, or provide --circuit-file/--circuit."
            raise RuntimeError(msg)

        payload = {"circuit": circuit}

        if args.num_gpus is not None:
            payload["num_gpus"] = args.num_gpus
        if args.iteration_time_minutes is not None:
            payload["iteration_time_minutes"] = args.iteration_time_minutes
        if args.gate_set:
            payload["gate_set"] = args.gate_set
        if args.hpc_mode:
            payload["hpc_mode"] = args.hpc_mode

    for item in args.set:
        if "=" not in item:
            msg = f"Invalid --set value '{item}'. Expected key=value."
            raise RuntimeError(msg)
        key, value = item.split("=", 1)
        payload[key] = _parse_dynamic_value(value)

    if "circuit" not in payload:
        msg = "Submit payload must include the 'circuit' field."
        raise RuntimeError(msg)

    return payload


def _print_json(title: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _request_with_retry(
    method: str,
    url: str,
    headers: dict[str, str],
    *,
    timeout: int,
    json_payload: dict[str, Any] | None = None,
    retries: int,
) -> requests.Response:
    attempt = 0
    while True:
        attempt += 1
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json_payload,
            timeout=timeout,
        )

        if response.status_code not in {429, 500, 502, 503, 504}:
            return response

        if attempt > retries:
            return response

        sleep_seconds = min(30.0, 1.5**attempt)
        print(
            f"Retryable status {response.status_code} from {url}; "
            f"retrying in {sleep_seconds:.1f}s (attempt {attempt}/{retries})"
        )
        time.sleep(sleep_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit and poll a QAS compression job (golden path)."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)

    parser.add_argument("--request-json", help="Full submit payload JSON file")
    parser.add_argument("--circuit-file", help="Path to OpenQASM file")
    parser.add_argument("--circuit", help="Inline OpenQASM string")

    parser.add_argument("--num-gpus", type=int)
    parser.add_argument("--iteration-time-minutes", type=int)
    parser.add_argument("--gate-set")
    parser.add_argument("--hpc-mode")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        help="Override or add submit field key=value; can be repeated",
    )

    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--max-poll-interval", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--http-timeout", type=int, default=30)
    parser.add_argument("--retry-count", type=int, default=5)
    parser.add_argument("--output-json", help="Write final job payload to file")

    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    try:
        token = _resolve_token(args)
        payload = _load_submit_payload(args)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    submit_url = f"{base_url}/api/public/v1/circuit-compression/jobs"
    print(f"Submitting compression job to {submit_url}")
    _print_json("Submit Request", payload)

    submit_response = _request_with_retry(
        "POST",
        submit_url,
        headers,
        timeout=args.http_timeout,
        json_payload=payload,
        retries=args.retry_count,
    )

    if submit_response.status_code >= 400:
        print(
            f"Submit failed with HTTP {submit_response.status_code}:\n{submit_response.text}",
            file=sys.stderr,
        )
        return 1

    submit_payload = submit_response.json()
    _print_json("Submit Response", submit_payload)

    job_id = submit_payload.get("job_id") or submit_payload.get("id")
    if not job_id:
        print("Submit response did not contain job_id.", file=sys.stderr)
        return 1

    poll_url = f"{base_url}/api/public/v1/circuit-compression/jobs/{job_id}"
    print(f"\nPolling {poll_url}")

    started = time.monotonic()
    interval = max(1.0, args.poll_interval)
    last_status = None

    while True:
        elapsed = time.monotonic() - started
        if elapsed > args.timeout_seconds:
            print(
                f"Timed out after {args.timeout_seconds}s waiting for terminal status.",
                file=sys.stderr,
            )
            return 3

        poll_response = _request_with_retry(
            "GET",
            poll_url,
            headers,
            timeout=args.http_timeout,
            retries=args.retry_count,
        )

        if poll_response.status_code >= 400:
            print(
                f"Polling failed with HTTP {poll_response.status_code}:\n{poll_response.text}",
                file=sys.stderr,
            )
            time.sleep(interval)
            interval = min(args.max_poll_interval, interval * 1.3)
            continue

        job_payload = poll_response.json()
        status = str(job_payload.get("status", "UNKNOWN")).upper()

        if status != last_status:
            print(f"Status changed: {last_status or 'N/A'} -> {status}")
            last_status = status

        if status in TERMINAL_STATUSES:
            _print_json("Final Job Payload", job_payload)
            if args.output_json:
                with pathlib.Path(args.output_json).open("w", encoding="utf-8") as file_obj:
                    json.dump(job_payload, file_obj, indent=2, ensure_ascii=False)
                print(f"Saved final payload to {args.output_json}")
            if status == "COMPLETED":
                return 0
            return 4

        time.sleep(interval)
        interval = min(args.max_poll_interval, interval * 1.15)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("Interrupted by user.")
        raise SystemExit(130) from exc
