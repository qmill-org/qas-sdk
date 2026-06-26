# QAS 1.6 Compatibility Plan for qas-sdk 0.1.4 -> 0.1.5

## Goal

Prepare QAS 1.6 so qas-sdk 0.1.4 remains functional, then add 0.1.5 support for new compression parameters without introducing breaking behavior.

## Baseline SDK 0.1.4 Compression Contract

`QASClient.submit_compression()` currently sends:

- required: `circuit`
- optional: `num_gpus`, `iteration_time_minutes`, `gate_set`, `hpc_mode`

Rules in SDK:

- Optional fields are omitted from payload when not provided.
- API defaults are relied on for omitted optional fields.
- Unknown response fields are tolerated by the SDK (dict passthrough).
- `wait_for_job()` expects terminal statuses including `COMPLETED`, `FAILED`, `CANCELLED` and also accepts `STOPPED`.

## Workstream 1: Verify QAS 1.6 does not break SDK 0.1.4

Check QAS develop branch for these non-breaking guarantees:

1. Endpoint compatibility
- Keep `POST /api/public/v1/circuit-compression/jobs`.
- Keep `GET /api/public/v1/circuit-compression/jobs/{job_id}`.
- Keep `GET /api/public/v1/circuit-compression/jobs`.

2. Request compatibility
- Existing fields remain accepted with same names and types:
  - `circuit` (string)
  - `num_gpus` (integer)
  - `iteration_time_minutes` (integer)
  - `gate_set` (string)
  - `hpc_mode` (string)
- Existing defaults remain stable when fields are omitted.

3. Response compatibility
- Keep `job_id` and `status` in submit response.
- Keep `status` values recognizable by SDK polling logic.
- Keep `result` and `error` semantics unchanged for terminal states.

4. Error compatibility
- Validation changes should still return clear 4xx messages.
- Avoid changing successful behavior into hard 400/422 for previously valid 0.1.4 payloads.

## Current Findings From QAS `develop` (2026-06-26)

### Compression API request/response compatibility

1. Public compression endpoints used by SDK 0.1.4 are still present.
2. Existing request fields remain optional and accepted:
- `num_gpus` defaults to `1` and is range-limited.
- `iteration_time_minutes` defaults to `60` and is range-limited.
- `gate_set` and `hpc_mode` remain optional.
3. A new optional `goal` field exists in the API request model.
4. Public job payload shape used by SDK polling remains compatible (`job_id`, `status`, `result`, `error`).

### Gate-set behavior risk (important)

Observed path in `develop`:

1. API normalization accepts legacy labels/codes (`IBM-Eagle`, `IBM`, `IonQ`, etc.) and maps to internal compression codes.
2. Default runtime mode is now `*_v2_0` family.
3. v2.0 wrapper scripts only accept code-style gate sets (`CX_RX_RZ`, `CZ_RX_RZ`, `RXX_RX_RZ`, `RZZ_RX_RZ`).
4. Unsupported gate-set values at wrapper level fall back to `CX_RX_RZ` with a warning.

Impact:

- SDK 0.1.4 requests usually still succeed, but legacy gate-set intent may be silently remapped under v2.0 defaults.
- This is a behavior drift risk, not a hard API-break risk.

### HPC mode / wrapper versioning behavior

1. QAS mode catalog includes both v1.6 and v2.0 modes.
2. Wrapper scripts are versioned and tied to mode-specific asset roots.
3. If caller sets `hpc_mode=lumi_v1_6` or `aws_v1_6`, legacy wrapper + asset path is still used.
4. If caller omits `hpc_mode`, runtime default may route to v2.0 wrappers.

Impact:

- Existing SDK 0.1.4 can preserve old behavior by explicitly setting `hpc_mode` to v1.6 modes.
- Omitted `hpc_mode` may now execute through v2.0 behavior.

## Workstream 2: QAS-side changes to preserve 0.1.4 behavior

If new parameters are introduced, QAS should:

1. Make all new request fields optional.
2. Apply safe server defaults when omitted.
3. Preserve old default values where feasible.
4. Avoid changing meaning of existing fields.
5. If constraints tighten, provide backward-compatible fallback path for old payloads.

Recommended QAS-side hardening before 1.6 release:

1. Keep legacy gate-set values deterministic in v2.0 path (no silent fallback without surfaced response metadata).
2. Return effective resolved gate set and mode in submit/job payloads to make remapping visible.
3. Keep v1.6 modes available for clients that need legacy behavior during transition.
4. Keep both stop endpoints available during SDK 0.1.x (`DELETE /jobs/{job_id}` and `POST /jobs/{job_id}/stop`).

## Workstream 3: qas-sdk 0.1.5 support for new parameters

Proposed SDK changes:

1. Add new optional fields to `CompressionJobOptions`.
2. Add matching keyword args to `submit_compression()`.
3. Keep old kwargs behavior unchanged.
4. Keep precedence rule: explicit kwargs override options dataclass values.
5. Update docs/examples with new fields and default behavior notes.

## Recommended Versioning Decision

- Use `0.1.5` if changes are additive and non-breaking.
- Use `0.2.0` only if SDK behavior or API contract changes in a breaking way.

## Test Matrix (must pass)

1. SDK 0.1.4 against QAS 1.6
- Submit with only `circuit`.
- Submit with each existing optional field.
- Poll until completion and verify terminal payload fields.

2. SDK 0.1.5 against QAS 1.6
- Submit old payloads (backward compatibility).
- Submit with new optional fields.
- Verify new fields are honored and old flows unchanged.

3. Negative tests
- Invalid type/value for each new field returns clear validation errors.
- Unknown/legacy mode and gate set behavior is documented and predictable.

## Gate Set + Mode Compatibility Test Cases (Release Blocking)

Run these against QAS `develop` before QAS 1.6 release tag.

1. Baseline submit compatibility
- Payload: `circuit` only.
- Expect: success and stable submit response shape.

2. Legacy gate set with explicit v1.6 mode
- Payload: `gate_set=IBM-Eagle`, `hpc_mode=lumi_v1_6`.
- Expect: success and effective gate set aligns with legacy flow.

3. Legacy gate set with default mode (no hpc_mode)
- Payload: `gate_set=IBM-Eagle`, no `hpc_mode`.
- Expect: success; verify whether effective gate set is remapped to v2.0 code and record it.

4. v2.0 code-style gate set with explicit v2.0 mode
- Payload: `gate_set=CX_RX_RZ`, `hpc_mode=lumi_v2_0`.
- Expect: success with no fallback.

5. Invalid gate set handling
- Payload: `gate_set=UNKNOWN_GATE_SET`.
- Expect: clear 4xx validation error at API layer (not silent wrapper fallback).

6. Wrapper compatibility by mode
- Repeat cases 2-4 for AWS modes (`aws_v1_6`, `aws_v2_0`).
- Verify wrapper selected matches requested mode family.

7. Stop endpoint compatibility
- Trigger stop via SDK 0.1.4 path (`DELETE /jobs/{id}`) and public stop path (`POST /jobs/{id}/stop`).
- Expect: both remain functional for transition period.

## Release Gate Criteria

QAS 1.6 can ship with SDK 0.1.4 support only if:

1. All baseline 0.1.4 compatibility tests pass.
2. No required request fields were added.
3. Existing defaults and status semantics remain compatible.

SDK 0.1.5 can ship if:

1. Additive parameter support is tested.
2. Backward compatibility with 0.1.4 payloads is confirmed.
3. Changelog and API docs are updated.
