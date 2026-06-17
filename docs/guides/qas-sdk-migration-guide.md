# QAS client library migration guide

This guide explains changes in the QAS client library and how to update your integration.

## Summary of changes

The client library now uses the `/api/public/v1/circuit-compression` endpoints. Older versions used
legacy paths that no longer return results.

## Update the client library

```bash
pip install --upgrade git+https://github.com/qmill-org/qas-sdk.git
```

## Verify the version

```python
import qas_sdk

print(qas_sdk.__version__)
```

## Update API calls

If your code uses the client library, you don't need changes. The client library routes requests
to the current endpoints.

If you call the API directly, use these endpoints:

- `POST /api/public/v1/circuit-compression/jobs`
- `GET /api/public/v1/circuit-compression/jobs/{job_id}`

## Related documentation

- [QAS client library installation](qas-sdk-installation-guide.md)
