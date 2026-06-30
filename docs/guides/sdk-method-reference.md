# SDK method reference

This page summarizes the main `QASClient` methods used for public circuit
compression workflows.

For REST contract details (payload fields, error codes, and endpoint behavior),
see [Compression API](../api/compression-api.md).

## Compression methods

| Method | Purpose | Returns |
| --- | --- | --- |
| `submit_compression(circuit, ..., options=None)` | Submit compression job | Job payload with `job_id`, `status`, and estimate fields |
| `get_compression_job(job_id)` | Fetch one job state/results | Job payload |
| `list_compression_jobs(limit=50)` | List user jobs | `list[dict]` job summaries |
| `wait_for_job(job_id, poll_interval=5, timeout=None, callback=None)` | Poll until terminal status | Final job payload |
| `stop_compression_job(job_id)` | Stop an active job and keep best available current output | Acknowledgement payload |
| `cancel_compression_job(job_id)` | Alias for stop method | Acknowledgement payload |
| `get_hpc_mode()` | Current mode and available modes | Mode payload |
| `list_hpc_modes()` | Available mode list only | `list[dict]` |

## Stopping early with best-so-far results

Use `stop_compression_job(job_id)` when:

- the current output quality already meets your target, or
- you want to stop further iteration time and credit usage.

Typical pattern:

1. Submit job.
2. Track status/logs.
3. Stop when quality is sufficient.
4. Fetch the latest job payload and read `result`.

```python
job = client.submit_compression(circuit_text, options=options)
job_id = job["job_id"]

# ... some monitoring/checking period ...
client.stop_compression_job(job_id)

latest = client.get_compression_job(job_id)
best_result = latest.get("result")
```

Note: in public API semantics, stopped jobs are surfaced as `COMPLETED`.

## Compression options object

`CompressionJobOptions` can be passed as `options=` to
`submit_compression(...)`:

- `num_gpus`
- `iteration_time_minutes`
- `gate_set`
- `hpc_mode`

Any explicit keyword arguments passed directly to `submit_compression` override
the same field from `options`.

## Typical usage

```python
from qas_sdk import CompressionJobOptions, QASClient

client = QASClient(base_url="https://qas.qmill.com")

options = CompressionJobOptions(
    num_gpus=1,
    iteration_time_minutes=45,
  gate_set="CX_RX_RZ",
)

job = client.submit_compression(circuit_text, options=options)
job_id = job["job_id"]

# For long jobs, submit now and check later:
latest = client.get_compression_job(job_id)

# For synchronous scripts:
final = client.wait_for_job(job_id, poll_interval=5, timeout=7200)
```

## Notes

- For public users, long-running real HPC jobs are usually best handled as
  submit-first workflows.
- Use `wait_for_job` when you explicitly want a blocking script.
- `stop_compression_job` is useful to accept current best results without waiting
  for further optimization iterations.
