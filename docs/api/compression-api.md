# QMill Circuit Compression API

<!-- markdownlint-disable MD060 -->

## Overview

This reference documents the public QMill Circuit Compression API for circuit compression jobs.

## Base URL

```text
https://qas.qmill.com
```

## Authentication

All endpoints in this document require a Bearer access token.

Preferred for user workflows: authenticate once with the SDK CLI and reuse the local session.

```bash
qas auth login --base-url https://qas.qmill.com
qas auth token
```

## Golden path

1. Submit a compression job with `POST /api/public/v1/circuit-compression/jobs`.
2. Poll `GET /api/public/v1/circuit-compression/jobs/{job_id}` until status is terminal.
3. Persist the final job payload returned by the API.

Terminal statuses are `COMPLETED`, `FAILED`, and `CANCELLED`.

Note: user-initiated stop requests are represented as `COMPLETED` in the public
status field. In those cases, `result` may be empty if no compressed output was
available when the stop was processed.

## Endpoints

### Submit compression job

Endpoint: `POST /api/public/v1/circuit-compression/jobs`

Headers:

- `Authorization: Bearer <token>`
- `Content-Type: application/json`

Request fields:

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `circuit` | `string` | Yes | - | OpenQASM source string to compress. |
| `num_gpus` | `integer` | No | `1` | Number of GPUs requested for compression. |
| `iteration_time_minutes` | `integer` | No | `60` | Requested iteration time budget, in minutes. |
| `gate_set` | `string` | No | backend default | Optional gate set identifier passed to the backend. |
| `hpc_mode` | `string` | No | platform runtime mode | Optional HPC mode override for job submission. |

Current `hpc_mode` options:

- `demo`
- `lumi_v1_6`
- `lumi_v1_6_parallel`
- `aws_v1_6`
- `aws_v1_6_parallel`

Additional legacy mode values currently accepted by the backend:

- `lumi_v1_0`
- `lumi_v1_5`
- `aws_v1_0`
- `aws_v1_5`

Current `gate_set` options by mode:

- For `demo`, `lumi_v1_6`, `lumi_v1_6_parallel`, `aws_v1_6`, and `aws_v1_6_parallel`:
  `IBM-Eagle`, `IQM`, `Rigetti`, `IonQ`, `IonQ Forte`, `Quantinuum`
- For legacy `lumi_v1_0` and `aws_v1_0`:
  `IBM-Eagle`, `Rigetti`, `IonQ`

Current constraints:

- `num_gpus`:
  - Default is `1`.
  - Public API enforces a maximum value of `4`.
  - In `demo` mode, effective GPU count is forced to `0`.
  - In real HPC modes, values greater than `1` are used only when
    the account has multi-GPU entitlement; otherwise, the API
    returns `403`.
  - In practice, free-tier accounts should submit with `num_gpus = 1`.
    For widest compatibility, use non-parallel real modes (`lumi_v1_6`
    or `aws_v1_6`) unless your account has explicit multi-GPU entitlement.
- `iteration_time_minutes`:
  - Default is `60`.
  - Public API enforces a maximum value of `360` (6 hours).
  - The value is passed through to backend submission
    and used in credit estimation.

Plan and entitlement behavior (production backend):

- Multi-GPU entitlement is required when `num_gpus > 1` in real HPC modes.
- Entitlement is granted when either:
  - billing tier is monthly paid, or
  - PAYG credits are available.
- If entitlement is missing, submit returns `403` with an entitlement message.
- Parallel mode slugs (`lumi_v1_6_parallel`, `aws_v1_6_parallel`) are real,
  billable modes; for free-tier onboarding, prefer single-GPU non-parallel modes.

Example request:

```json
{
  "circuit": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0], q[1];\ncx q[1], q[2];\nmeasure q -> c;",
  "num_gpus": 1,
  "iteration_time_minutes": 45,
  "gate_set": "IBM-Eagle",
  "hpc_mode": "lumi_v1_6"
}
```

Example response (`200 OK`):

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUBMITTED",
  "message": "Job submitted to LUMI successfully. Slurm Job ID: 12345678",
  "credit_estimate": 43,
  "remaining_credits": 255
}
```

Error responses:

- `400`: Invalid OpenQASM, invalid payload values, or unsupported circuit size
- `401`: Missing or invalid token
- `402`: Insufficient credits
- `403`: Entitlement restriction (for example multi-GPU not allowed)
- `500`: Backend submission failed

### Credit usage and charging

Compression credit estimate is calculated server-side from circuit complexity and
requested runtime parameters. In production, the estimate uses:

- base component
- qubit component
- gate component
- GPU component (scales with effective GPU count)
- iteration component (scales in blocks of iteration minutes)
- minimum per-job floor

Charging lifecycle:

- On submit (`POST /jobs`), `credit_estimate` is returned and reservation/capacity checks apply.
- On terminal success (`COMPLETED`, and backend-internal stopped completions),
  final charge is settled and returned as `credits_charged` in job payload.
- On terminal failure/cancel (`FAILED`/`CANCELLED`), reserved credits are released
  and no completion charge is applied.
- `remaining_credits` reflects available balance after reservation/settlement state.

Example curl:

```bash
curl -X POST https://qas.qmill.com/api/public/v1/circuit-compression/jobs \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "circuit": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0], q[1];\ncx q[1], q[2];\nmeasure q -> c;",
    "num_gpus": 1,
    "iteration_time_minutes": 45
  }'
```

### Get compression job details

Endpoint: `GET /api/public/v1/circuit-compression/jobs/{job_id}`

Headers:

- `Authorization: Bearer <token>`

Response fields:

| Field | Type | Description |
| --- | --- | --- |
| `job_id` | `string` | Compression job identifier. |
| `status` | `string` | Current status (`SUBMITTED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`). |
| `created_at` | `string \| null` | Job creation timestamp (`ISO 8601`, UTC). |
| `completed_at` | `string \| null` | Job completion timestamp (`ISO 8601`, UTC). |
| `result` | `string \| null` | Compressed OpenQASM circuit when available. |
| `error` | `string \| null` | Error message for failed jobs. |
| `credits_charged` | `integer \| null` | Credits charged after completion. |
| `remaining_credits` | `integer \| null` | Remaining credits at response time. |

Example response (`200 OK`):

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "created_at": "2026-03-18T10:30:00Z",
  "completed_at": "2026-03-18T10:42:07Z",
  "result": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0], q[2];\nmeasure q -> c;",
  "error": null,
  "credits_charged": 41,
  "remaining_credits": 214
}
```

Error responses:

- `401`: Missing or invalid token
- `403`: Job does not belong to authenticated user
- `404`: Job not found

Example curl:

```bash
curl -X GET https://qas.qmill.com/api/public/v1/circuit-compression/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### List user compression jobs

Endpoint: `GET /api/public/v1/circuit-compression/jobs`

Headers:

- `Authorization: Bearer <token>`

Query parameters:

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `limit` | `integer` | No | `50` | Maximum number of jobs returned. |

Example response (`200 OK`):

```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-03-18T10:30:00Z",
      "status": "COMPLETED",
      "completed_at": "2026-03-18T10:42:07Z",
      "result": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\n...",
      "error": null,
      "credits_charged": 41,
      "remaining_credits": 214
    }
  ]
}
```

### Stop or cancel a compression job

Preferred endpoint: `POST /api/public/v1/circuit-compression/jobs/{job_id}/stop`

Headers:

- `Authorization: Bearer <token>`

Behavior:

- Intended for jobs in `SUBMITTED` or `RUNNING` state.
- Use this when current compression quality is already good enough and you do not
  want to spend more iteration time/credits.
- Returns acknowledgement payload with status and backend job id when available.
- Stop attempts to preserve the best currently available output from the active
  run instead of continuing optimization iterations.
- For public responses, stopped jobs are surfaced as `COMPLETED`.
- If no partial/final result exists at stop time, `result` in subsequent
  `GET /jobs/{job_id}` responses can be `null`.

Recommended follow-up:

- After stop acknowledgement, call `GET /api/public/v1/circuit-compression/jobs/{job_id}`
  to fetch the latest available result payload.

Example stop request:

```bash
curl -X POST https://qas.qmill.com/api/public/v1/circuit-compression/jobs/550e8400-e29b-41d4-a716-446655440000/stop \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Example response (`200 OK`):

```json
{
  "message": "Stop request sent for job 550e8400-e29b-41d4-a716-446655440000",
  "lumi_job_id": "12345678",
  "status": "COMPLETED"
}
```

Error responses:

- `400`: Job is not in a stoppable state, or backend identifier is missing
- `401`: Missing or invalid token
- `403`: Job does not belong to authenticated user
- `404`: Job not found
- `429`: Rate limit exceeded
- `500`: Backend stop operation failed

### Polling and retries

- Poll every 5 seconds for `SUBMITTED` and `RUNNING` jobs.
- Increase polling interval progressively for long-running jobs.
- Treat `429` and `5xx` as retryable failures.
- Persist the full final payload when status becomes terminal.

### External example

Use the golden-path script in `examples/compression_golden_path.py`.

Default behavior is submit-first (no polling), which is recommended for long-running real HPC jobs.

```bash
python examples/compression_golden_path.py \
  --base-url https://qas.qmill.com \
  --circuit-file ./examples/example.qasm \
  --gate-set IBM-Eagle \
  --output-json ./submit-job.json
```

To block and wait for terminal status in the same run, add `--wait`:

```bash
python examples/compression_golden_path.py \
  --base-url https://qas.qmill.com \
  --circuit-file ./examples/example.qasm \
  --gate-set IBM-Eagle \
  --wait \
  --poll-interval 5 \
  --timeout-seconds 7200 \
  --output-json ./final-job.json
```

## Support

- GitHub Issues: <https://github.com/qmill-org/qas-sdk>
- email: <support@qmill.com>

<!-- markdownlint-enable MD060 -->
