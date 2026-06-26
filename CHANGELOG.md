# Changelog

All notable changes to the QAS SDK will be documented in this file.

## [Unreleased]

### Changed

- **BREAKING**: Removed username/password (password grant) authentication from `QASClient`.
- Added `qas auth` CLI (`login`, `status`, `token`, `logout`) with device-code login.
- `QASClient` now auto-loads persisted CLI auth state when instantiated without explicit credentials.
- Updated public examples and README to use CLI-first authentication flows.
- `QASClient.submit_compression()` now supports optional `goal` parameter (`depth`, `twoqubit`, `total`).
- `CompressionJobOptions` now supports optional `goal`.
- `QASClient.stop_compression_job()` now prefers `POST /jobs/{job_id}/stop` and falls back to legacy `DELETE /jobs/{job_id}` for older deployments.

## [0.1.4] - 2026-03-27

### Added

- Initial public release of the QAS SDK.

### Notes

- Earlier internal milestones are intentionally omitted from this public changelog baseline.
