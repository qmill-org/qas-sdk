# Changelog

All notable changes to the QAS SDK will be documented in this file.

## [Unreleased]

## [0.1.6] - 2026-06-30

### Fixed

- Corrected `qas_sdk.__version__` to report `0.1.6` to match the published package version.
- Updated release workflow ordering to publish to PyPI before generating `SHA256SUMS.txt`, preventing non-distribution files from being uploaded to PyPI.

## [0.1.5] - 2026-06-30

### Changed

- Aligned SDK and examples with QAS 1.6 compression updates.
- Added optional `goal` support to `QASClient.submit_compression()` and `CompressionJobOptions`.
- Updated compression docs/examples to current mode and gate-set guidance.
- Aligned Python example scripts to submit-first flow by default for non-demo modes, with optional wait controls.
- Improved API walkthrough auth resilience by refreshing CLI token and retrying once on `401`.
- Changed auth defaults to use `qas-cli` as the default client ID in CLI and SDK fallback auth loading.
- Changed CLI default login scope to `openid` (use `--scope "openid offline_access"` for offline sessions).

## [0.1.4] - 2026-06-18

### Added

- Initial public release of the QAS SDK.

### Notes

- Earlier internal milestones are intentionally omitted from this public changelog baseline.
