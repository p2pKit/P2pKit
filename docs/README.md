# P2pKit documentation

This directory separates current user and maintainer guidance from historical
remediation records. Start with the repository [README](../README.md).

Current source and latest published versions are listed in the
[repository README](../README.md); canonical version properties live in
[`gradle.properties`](../gradle.properties). Publication does not complete
the remaining runtime and independent validation scopes.

## Use and design

- [Architecture overview](architecture/overview.md)
- [Current high-level API and protocol contract](architecture/specification.md)
- [Operational limits and configuration](reference/limits.md)
- [Security model](security/model.md)
- [Compatibility policy](compatibility.md)
- [Versioning policy](versioning.md)
- [Migration from 0.6.x](guides/migrating-to-0.7.md)
- [Error handling and recovery](guides/error-handling.md)
- [Custom transport providers](guides/custom-transports.md)
- [Samples](guides/samples.md)
- [Optional organization-LAN RPC](rpc/README.md) — published optional library; runtime limitations remain

## Test and release

- [Historical Mac handoff](testing/mac-handoff.md) — preserved September audit checkpoint
- [Local testing](testing/local.md)
- [Validation status](testing/validation-status.md)
- [Real-world and independent validation handbook](validation/README.md)
- [Cross-platform validation test catalog](validation/test-catalog.md)
- [Validation evidence schema](validation/evidence-schema.md)
- [Release checklist](releasing/checklist.md)
- [Maven Central procedure](releasing/maven-central.md)
- [`0.8.0-rc6` release evidence](releases/0.8.0-rc6.md)
- [`0.8.0-rc5` release evidence](releases/0.8.0-rc5.md)
- [`0.8.0-rc2` release evidence](releases/0.8.0-rc2.md)
- [`0.7.0-rc3` release evidence](releases/0.7.0-rc3.md)
- [`0.7.0-rc2` release evidence](releases/0.7.0-rc2.md)

Historical audits, remediation trackers, superseded runbooks, and old evidence
are indexed under [`archive/`](archive/README.md). An archived status is not a
current product claim.

Dated branch and GitHub tracker decisions are indexed under
[`maintenance/`](maintenance/README.md).
