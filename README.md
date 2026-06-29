# QAS SDK

Python client library for the QAS Circuit Compression API.

This repository is intended for any developer using QAS, whether locally,
in notebooks, or in hosted environments such as qBraid Lab.

## Get Access to QAS

To use the SDK against a QAS environment, you need QAS access.

If you do not yet have access, register here:

- https://qmill.com/en/qas-registration

## Installation

### From PyPI (Recommended)

```bash
pip install qas-sdk
```

### From Git

```bash
pip install git+https://github.com/qmill-org/qas-sdk.git
```

### For Development

```bash
pip install -e .
```

## Development in Dev Containers

This repository supports VS Code Dev Containers so development can follow the
same container-first workflow used in QAS.

1. Open the repository in VS Code.
2. Run "Dev Containers: Reopen in Container".
3. Wait for `.devcontainer/setup.sh` to finish.

The setup installs development dependencies and pre-commit hooks inside the
container. You do not need to create a local virtual environment when working
inside the dev container.

## Launch on qBraid Lab (Optional)

[<img src="https://qbraid-static.s3.amazonaws.com/logos/Launch_on_qBraid_white.png" width="150">](https://account.qbraid.com/explore/projects/qmill-qas-circuit-compression)

If this repository is launched from qBraid Explore, it is cloned into your Lab
workspace, and the QMill QAS SDK environment will be installed automatically. From there:

1. Open Terminal, and activate the QMill QAS environment:

```bash
qbraid envs activate "QMill QAS SDK"
```

2. Authenticate:

```bash
qas auth login --base-url https://qas.qmill.com
```

For headless/minimal environments, use:

```bash
qas auth login --base-url https://qas.qmill.com --no-browser
```

> [!NOTE]
> To use the `qas-sdk` within Jupyter Notebooks, set your kernel to `Python 3 [QMill]`.

## Quick Start

```python
from qas_sdk import CompressionJobOptions, QASClient

# Preferred auth flow: login once with CLI, then construct client without tokens.
#   qas auth login --base-url https://qas.qmill.com
client = QASClient(
    base_url="https://qas.qmill.com",
)

# Submit a small demo-mode compression job
circuit = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
x q[0];
x q[0];
h q[1];
h q[1];
cx q[0],q[2];
cx q[0],q[2];
rz(pi/4) q[3];
rz(-pi/4) q[3];"""

job = client.submit_compression(
    circuit,
    options=CompressionJobOptions(
        hpc_mode="demo",
        gate_set="IBM-Eagle",
    ),
)
print(f"Job ID: {job['job_id']}")

# Wait for completion (demo mode is suitable for blocking quick starts)
result = client.wait_for_job(job["job_id"])
print(f"Compressed circuit: {result['result']}")
```

In `demo` mode, the backend still requires and validates your `circuit` payload
(valid OpenQASM, minimum qubit constraints), but the returned compression output
is mock/demo output rather than a real HPC optimization result.

For real HPC runs, prefer submit-first workflows and fetch status/results later.
See `examples/compression_golden_path.py` for that pattern.

## Features

- ✅ Device-code CLI login (`qas auth login`) for user-scoped workflows
- ✅ Automatic refresh-token based session renewal in SDK
- ✅ Circuit compression on LUMI supercomputer or AWS ParallelCluster
- ✅ Configurable compression parameters (GPUs, iteration time, gate sets, HPC mode)
- ✅ Progress monitoring with custom callbacks and live status polling
- ✅ Comprehensive error handling
- ✅ Type hints for IDE support

## Documentation

Full documentation available at:

- [Installation Guide](docs/guides/qas-sdk-installation-guide.md)
- [SDK Method Reference](docs/guides/sdk-method-reference.md)
- [Examples](examples/README.md)
- [API Documentation](docs/api/compression-api.md)

## Requirements

- Python 3.10+
- Access to QAS Platform instance

## Authentication

### Recommended: Device-code CLI login

Login once and persist your session locally:

```bash
qas auth login --base-url https://qas.qmill.com
```

If you are on a headless/minimal Linux environment (no desktop browser integration), use:

```bash
qas auth login --base-url https://qas.qmill.com --no-browser
```

Then create a client without passing tokens:

```python
from qas_sdk import QASClient

client = QASClient(
    base_url="https://qas.qmill.com",
)
```

The SDK loads the stored session automatically and refreshes expired access tokens with the
stored refresh token.

Useful CLI commands:

```bash
qas auth status
qas auth token
qas auth logout
```

## License

MIT License - see LICENSE file for details.
