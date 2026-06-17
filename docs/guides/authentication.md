# Authentication

This guide explains public authentication options for the QAS SDK and API.

## Overview

QAS uses Keycloak-issued OAuth2/OIDC access tokens (`Bearer` tokens).

## External SDK/API authentication

External users should authenticate with the QAS CLI device-code flow.

Canonical public path: run `qas auth login` once, then use SDK/scripts normally.

Required values for SDK/API usage:

```bash
export QAS_BASE_URL=https://qas.qmill.com
qas auth login
```

### How to authenticate for SDK usage

Use the supported public method:

1. Run device-code login:

```bash
qas auth login
```

2. Verify local session status:

```bash
qas auth status
```

The SDK automatically loads the persisted CLI session and refreshes tokens when possible.

If you receive `401 Unauthorized: Invalid audience`, validate that the token includes `quantum-app` in `aud`.

## Troubleshooting

### 401 responses on API calls

Check that the client sends `Authorization: Bearer <access token>`.

### Token expired during SDK/API usage

Symptoms:

- API returns `401 Unauthorized` after previously working requests.
- Notebook/script starts failing without code changes.

Resolution:

- Refresh your CLI session:

```bash
qas auth login
```

- Re-run the command or restart the notebook kernel.

## Related documentation

- [API Reference](../api/compression-api.md)
