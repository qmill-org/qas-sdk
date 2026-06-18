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
| `stop_compression_job(job_id)` | Stop/cancel an active job | Acknowledgement payload |
| `cancel_compression_job(job_id)` | Alias for stop method | Acknowledgement payload |
| `get_hpc_mode()` | Current mode and available modes | Mode payload |
| `list_hpc_modes()` | Available mode list only | `list[dict]` |

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
    gate_set="IBM-Eagle",
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
- `stop_compression_job` maps to the public stop/cancel behavior and may return
  `COMPLETED` status in public API semantics.
