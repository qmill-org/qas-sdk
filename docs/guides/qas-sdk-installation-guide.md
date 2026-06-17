# QAS client library installation

This guide explains how to install and use the QAS SDK.

## Prerequisites

- Python 3.10+.
- QAS user account.
- QAS CLI installed (for device-code login).

## Install the client library

### Install from PyPI (recommended)

```bash
pip install qas-sdk
```

### Install from a wheel (fallback)

```bash
wget https://github.com/qmill-org/qas-sdk/releases/download/v0.1.4/qas_sdk-0.1.4-py3-none-any.whl
pip install qas_sdk-0.1.4-py3-none-any.whl
```

### Install from the repository

```bash
pip install git+https://github.com/qmill-org/qas-sdk.git
```

## Configure credentials

Authenticate with the CLI device-code flow. For details, see
[Authentication](authentication.md#how-to-authenticate-for-sdk-usage).

```bash
qas auth login
```

Optional: verify current session state:

```bash
qas auth status
```

## Quick start

```python
import os
from qas_sdk import QASClient

client = QASClient(
    base_url=os.getenv("QAS_BASE_URL", "https://qas.qmill.com"),
)

circuit = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;"""

job = client.submit_compression(circuit)
result = client.wait_for_job(job["job_id"])
print(result["result"])
```

## Development setup

Use editable mode when working inside the repository:

```bash
pip install -e .
```

## Related documentation

- [Authentication](authentication.md)
