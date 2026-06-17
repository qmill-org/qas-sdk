# QAS SDK

Python client library for the QAS Circuit Compression API.

## Installation

### From PyPI (Recommended)

```bash
pip install qas-sdk
```

### From Wheel (Fallback)

```bash
wget https://github.com/qmill-org/qas-sdk/releases/download/v0.1.4/qas_sdk-0.1.4-py3-none-any.whl
pip install qas_sdk-0.1.4-py3-none-any.whl
```

### From Git

```bash
pip install git+https://github.com/qmill-org/qas-sdk.git
```

### For Development

```bash
pip install -e .
```

## Quick Start

```python
from qas_sdk import QASClient

# Recommended: login once with CLI, then construct client without tokens.
#   qas auth login --base-url https://qas.qmill.com
client = QASClient(
    base_url="https://qas.qmill.com",
)

# Submit circuit for compression
circuit = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
measure q -> c;"""

job = client.submit_compression(circuit)
print(f"Job ID: {job['job_id']}")

# Wait for completion
result = client.wait_for_job(job["job_id"])
print(f"Compressed circuit: {result['result']}")
```

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
