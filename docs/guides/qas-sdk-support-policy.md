# QAS SDK support policy

This page defines support, compatibility, and lifecycle commitments for the QAS SDK.

## Scope

This policy applies to officially released QAS SDK versions distributed by QMill.

## Supported versions

- Supported: latest major version and latest two minor versions.
- Security fixes: latest major version, unless otherwise agreed in writing.
- Unsupported versions may continue to run, but QMill does not guarantee behavior.

## Compatibility commitments

QAS SDK uses semantic versioning.

- Patch releases: bug fixes only, no intentional breaking API changes.
- Minor releases: backward-compatible features and improvements.
- Major releases: breaking changes may occur with migration guidance.

## Deprecation policy

- Deprecated features are announced in release notes.
- Minimum deprecation window is 90 days before removal.
- Removal occurs in major releases, except for security-critical cases.

## Security handling

- Security contact: `support@qmill.com`
- Acknowledgement target: 2 business days.
- Critical remediation target: 7 calendar days.
- Security advisories are published for customer-impacting vulnerabilities.

## Support channels and response targets

- Support channel: `support@qmill.com`
- Response targets:
  - Severity 1: 4 business hours
  - Severity 2: 1 business day
  - Severity 3: 3 business days
  - Severity 4: best effort

Support hours follow the service agreement defined for your organization.

## Supported usage

- Installation and authentication troubleshooting.
- SDK defects and regressions.
- Documented workflows and examples.
- Supported Python runtime versions listed in SDK release notes.

## Unsupported usage

- Modified SDK source in customer forks.
- Undocumented internal API endpoints.
- End-of-life Python runtimes.
- Customer infrastructure issues unrelated to SDK behavior.

## Customer responsibilities

- Pin SDK versions in production.
- Test upgrades in non-production before rollout.
- Protect and rotate credentials.
- Provide reproducible issue reports with SDK version, request context, and logs.

## Release communication

Each release includes:

- Version and release date.
- CHANGELOG summary.
- Breaking-change notice, if applicable.
- Security notes, if applicable.

## Policy review

- Owner: QMill SDK maintainers.
- Review cadence: quarterly.
