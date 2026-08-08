# Repository guidance

P2pKit is a Kotlin Multiplatform local-network P2P library for Android API 24+,
JVM 17/Desktop, and iOS. Authenticated protocol v2 is the fail-closed default.
The latest published release is `0.7.0-rc2`; `main` develops
`0.7.0-rc3-SNAPSHOT`.

## Repository map

- `library/p2p-core` — API, protocol, security, sessions, durable transfer.
- `library/p2p-transport-lan` — JmDNS/Bonjour and TCP implementations.
- `library/p2p-network-provisioning-*` — optional platform sidecars.
- `samples/` — Android, JVM CLI, Desktop UI, KMP, iOS, and diagnostics apps.
- `docs/` — current public/maintainer docs; `docs/archive/` is historical only.
- `scripts/` — release, security, publication, consumer, and repository gates.

Physical paths are mapped in `settings.gradle.kts`; do not change Gradle project
names or Maven artifact IDs merely to reorganize files.

## Core commands

```bash
scripts/tests/check-repository-layout.sh
scripts/tests/check-osv-lockfile-coverage.sh
scripts/tests/check-markdown-links.sh
scripts/check-release-metadata.sh
./gradlew check --console=plain
git diff --check
```

The complete macOS gate is `scripts/run-release-gate.sh`. Focused tasks retain
their original project names, for example `:p2p-core:jvmTest`,
`:p2p-transport-lan:iosSimulatorArm64Test`,
`:p2p-network-provisioning-android:testAndroidHostTest`, and
`:iosApp:runIosSimulator`.

## Compatibility and security constraints

- Published tags, coordinates, artifacts, API baselines, and release history
  are immutable. Never move `v0.7.0-rc1` or `v0.7.0-rc2`.
- Do not change the published `0.7.0-rc2` API or wire protocol during cleanup.
- Keep JVM, Android, and Apple transport/protocol behavior aligned.
- Never downgrade after authenticated-v2 failure or weaken identity checks.
- Surface typed failures and preserve cancellation. Do not weaken assertions,
  extend timeouts to hide failures, or skip required gates.
- Samples' detailed diagnostics are test-only and must not expose secrets,
  payload contents, credentials, keys, or personal device identifiers.
- Use exact, bounded tests for lifecycle, concurrency, retry, cleanup, and
  durable transfer changes.

## Apple configuration

The maintained XcodeGen project is `samples/iosApp/project.yml`. Its
`NSLocalNetworkUsageDescription`, secure `_p2pkit2._tcp` Bonjour declaration,
and XCFramework provenance phase are load-bearing. The generated `.xcodeproj`
is ignored and must not become a source of truth.

## Current documents

- `docs/architecture/specification.md` — maintained API/protocol contract.
- `docs/security/model.md` — threat model and limitations.
- `docs/testing/local.md` — automated checks.
- `docs/testing/external-validation.md` — physical/external test execution.
- `docs/releasing/checklist.md` — release process.
- `docs/releases/0.7.0-rc2.md` — immutable publication evidence.

The six external areas in `docs/testing/validation-status.md` remain pending;
do not promote them from compilation or simulator results.

If present in a local workspace, `.review-2026-07/`,
`DEFERRED_ITEMS_REGISTER_2026-07.md`,
`P2PKIT_FULL_CODE_REVIEW_2026-07-17.md`, and
`P2PKIT_REMEDIATION_HANDOFF_2026-07-22.md` are user-owned/protected and must not
be read, modified, staged, or committed.
