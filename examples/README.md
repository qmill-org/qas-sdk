# External QMill Circuit Compression API examples

These examples show how to use QMill Circuit Compression with direct HTTP calls and with the Python SDK. They assume
you have a QAS user account authenticated with the `qas auth login` CLI flow, plus network access to the target QAS
environment.

## Prerequisites

- Python 3.10+
- `git`
- QAS base URL (`https://qas.qmill.com`)
- QAS CLI login session (`qas auth login`)

## Install the SDK

Install from PyPI:

```bash
pip install qas-sdk
```

Or install from source:

```bash
# Clone the repository and enter it
$ git clone https://github.com/qmill-org/qas-sdk.git
$ cd qas-sdk

# Install SDK in editable mode with development extras
$ pip install -e .[dev]

# Install Jupyter for notebook runs (optional)
$ pip install jupyter
```

> **Tip:** You can also install straight from Git using a single command:
>
> ```bash
> pip install "git+https://github.com/qmill-org/qas-sdk.git"
> ```

## Configure Environment Variables

Create a `.env` file or export the following before running the examples:

```bash
cp examples/.env.example .env
```

```bash
export QAS_BASE_URL=https://qas.qmill.com
# Optional compression overrides (forwarded via SDK)
# Free-plan guidance: keep GPU at 1 and prefer non-parallel real modes.
# export QAS_NUM_GPUS=1
# export QAS_ITERATION_MINUTES=45
# export QAS_GATE_SET="CX_RX_RZ"
# export QAS_HPC_MODE="demo"
```

Plan-aware default recommendation:

- If your account is on free plan, use `num_gpus=1`.
- Prefer non-parallel real modes (`lumi_v2_0` or `aws_v2_0`) unless your
  account explicitly supports multi-GPU compression.

Mode and wait guidance:

| Goal | Recommended mode | Recommended golden-path behavior |
| --- | --- | --- |
| Fast local/API check | `demo` | submit + `--wait` |
| Real compression on HPC | omit `QAS_HPC_MODE` (platform default) or set `lumi_v2_0`/`aws_v2_0` | submit only (default), poll later |
| End-to-end synchronous run | real mode or `demo` | submit + `--wait` |

## Available Examples

- `compression_golden_path.py` - recommended pilot-customer flow that submits a job first,
  with optional polling to terminal status via `--wait`.
- `sdk_walkthrough.py` - SDK-only Python script; submit-first by default for non-demo modes, optional wait.
- `sdk_walkthrough.ipynb` - notebook version of the SDK-only flow for interactive exploration.
- `sdk_and_api_walkthrough.py` — end-to-end Python script using both the SDK and raw REST calls (submit-first by default for non-demo modes).
- `sdk_and_api_walkthrough.ipynb` — notebook variant with the same flow and rich output.
- `api_walkthrough.py` — REST-only Python script for submitting compression jobs
  without the SDK (submit-first by default for non-demo modes).
- `api_walkthrough.ipynb` — notebook version of the REST-only flow for interactive exploration.

All examples authenticate via the local CLI session (`qas auth login`) and submit a compression job.

- SDK-only flows: `sdk_walkthrough.py`, `sdk_walkthrough.ipynb`
- API-only flows: `compression_golden_path.py`, `api_walkthrough.py`, `api_walkthrough.ipynb`
- Mixed SDK+API parity flows: `sdk_and_api_walkthrough.py`, `sdk_and_api_walkthrough.ipynb` (optional, useful for verification/migration)

## Golden-path script (recommended)

Run from the repository root:

```bash
python examples/compression_golden_path.py \
  --base-url https://qas.qmill.com \
  --circuit-file ./examples/example.qasm \
  --gate-set CX_RX_RZ
```

If `--gate-set` is omitted, the script defaults to `CX_RX_RZ`.

By default, golden-path runs in submit-first mode and does not poll.

Authentication is loaded from your local `qas auth login` session.

Optional compression overrides:

```bash
python examples/compression_golden_path.py \
  --base-url https://qas.qmill.com \
  --circuit-file ./examples/example.qasm \
  --num-gpus 1 \
  --iteration-time-minutes 45 \
  --gate-set CX_RX_RZ \
  --hpc-mode lumi_v2_0
```

For free-plan accounts, keep `--num-gpus 1` and avoid parallel mode slugs.

To wait for completion in the same run, add `--wait`:

```bash
python examples/compression_golden_path.py \
  --base-url https://qas.qmill.com \
  --circuit-file ./examples/example.qasm \
  --gate-set CX_RX_RZ \
  --wait \
  --poll-interval 5 \
  --timeout-seconds 7200 \
  --output-json ./final-job.json
```

Pass additional request fields with repeatable `--set key=value` flags.

## Running the Python Script

```bash
cd examples
python sdk_walkthrough.py
```

### Running the SDK+API Script

```bash
cd examples
python sdk_and_api_walkthrough.py
```

The script prints SDK/API status snapshots by default, and can wait for completion when requested.

### Running the API-Only Script

```bash
cd examples
python api_walkthrough.py
```

Ensure `qas auth login --base-url https://qas.qmill.com` has completed successfully.

By default this script submits first and prints a status snapshot for non-demo
modes. To block until terminal status in the same run, set:

```bash
export QAS_WAIT_FOR_COMPLETION=true
```

## Running the Notebook

```bash
$ jupyter notebook examples/sdk_and_api_walkthrough.ipynb
# or for the SDK-only notebook
$ jupyter notebook examples/sdk_walkthrough.ipynb
# or for the REST-only notebook
$ jupyter notebook examples/api_walkthrough.ipynb
```

If you prefer uv, equivalent commands with `uv run` also work.

Follow the instructions in the first cell of the chosen notebook to confirm your environment
variables and run each cell in order.

## Troubleshooting

- **Authentication errors:** Confirm your user account is active in QAS, then re-run
  `qas auth login --base-url <your_qas_url>`.
- **Connection errors:** Ensure your environment can reach the QAS base URL and that any required VPN is connected.
- **HTTP 403/404:** Verify that the job ID exists and that your user account has permission to read it.

For additional details, consult the SDK README in the repository root or contact QMill support.
