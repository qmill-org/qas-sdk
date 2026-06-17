# Changelog

All notable changes to the QAS SDK will be documented in this file.

## [Unreleased]

### Changed

- **BREAKING**: Removed username/password (password grant) authentication from `QASClient`.
- Added `qas auth` CLI (`login`, `status`, `token`, `logout`) with device-code login.
- `QASClient` now auto-loads persisted CLI auth state when instantiated without explicit credentials.
- Updated public examples and README to use CLI-first authentication flows.

## [0.1.4] - 2026-03-27

### Added

- Initial public release of the QAS SDK.

### Notes

- Earlier internal milestones are intentionally omitted from this public changelog baseline.
