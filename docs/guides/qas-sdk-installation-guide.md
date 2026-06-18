# QAS client library installation

This guide explains how to install and use the QAS SDK.

## Prerequisites

- Python 3.10+.
- QAS user account.
- QAS CLI installed (for device-code login).

If you do not yet have QAS access, register at:

- https://qmill.com/en/qas-registration

## Install the client library

### Install from PyPI (recommended)

```bash
pip install qas-sdk
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

If automatic browser launch is not supported in your environment, run:

```bash
qas auth login --no-browser
```

Optional: verify current session state:

```bash
qas auth status
```

## Optional: running in qBraid Lab

If you opened this repository through qBraid Explore, install dependencies in
your Lab environment and run the same authentication steps above:

```bash
pip install qas-sdk
qas auth login --base-url https://qas.qmill.com
```

In headless/minimal environments, use:

```bash
qas auth login --base-url https://qas.qmill.com --no-browser
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
- [SDK method reference](sdk-method-reference.md)
- [Compression API](../api/compression-api.md)
