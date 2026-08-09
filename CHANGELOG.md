# Changelog

This file records release-facing behavior. Historical internal milestone tags,
audits, trackers, and implementation evidence remain under `docs/archive/`.

## 0.7.0-rc3 — release candidate (2026-08-09)

This candidate preserves the RC2 public API and secure-v2 wire format while
incorporating the post-RC2 dependency, LAN recovery, sample-diagnostics, and
repository-hardening work. It is intended to be the exact artifact set used
for the remaining real-world and independent validation campaigns.

### LAN reliability

- Selects and owns routable JVM/Android LAN bindings deterministically,
  including Android selected-network socket routing, bounded JmDNS creation,
  serialized rebind cleanup, and metadata-free service removal.
- Hardens Apple browser-generation endpoint ownership, listener/browser path
  recovery, foreground coalescing, peer-to-peer/cellular policy symmetry, and
  terminal write-ready cleanup.
- Adds deterministic lifecycle, callback-race, removal, path-rotation,
  cancellation, and recovery regression coverage without treating simulator
  or host checks as physical-device evidence.

### Toolchain and distribution

- Updates to Kotlin 2.4.10 while retaining and inspecting the iOS 14 library
  deployment floor across every XCFramework slice.
- Updates Kotlin serialization, AndroidX/Compose, and Desktop Compose with
  locked dependency graphs, verification metadata, canonical serialization
  vectors, ABI checks, and cross-host Desktop packaging coverage.
- Keeps the verified `io.github.apdelrahman1911` namespace, signed Central
  bundle shape, provenance, SBOM, isolated-consumer, and immutable-tag gates.
- Rebuilds release signatures with daemon and build-cache reuse disabled so a
  prior disposable key or maintainer key rotation cannot contribute stale
  signatures to a Central bundle.

### Validation status

Android and Apple physical-device validation, two-machine hostile-network
testing, CLI fault injection/headful Desktop observation, independent
secure-v2 interoperability, and professional cryptographic audit remain
pending. Publishing this release candidate does not mark any of those areas
complete or claim production readiness.

## 0.7.0-rc2 — release candidate (2026-08-06)

This candidate preserves the `0.7.0-rc1` API, protocol, and implementation and
corrects only its unpublished Maven release identity. All artifacts now use
the owner-verified Central Portal namespace `io.github.apdelrahman1911`. The
`v0.7.0-rc1` tag remains immutable and was not published after Central rejected
the former unowned namespace during validation.

Published to Maven Central under `io.github.apdelrahman1911`. Android and Apple
physical-device validation, two-machine hostile-network testing, CLI
fault injection/headful Desktop observation, independent secure-v2
interoperability, and professional cryptographic audit remain explicitly
pending external evidence.

## 0.7.0-rc1 — release candidate (2026-08-04)

Remote Maven Central publication is not asserted by this source state.

### Security

- Authenticated protocol v2 is the default:
  `Noise_XX_25519_ChaChaPoly_SHA256` with persistent X25519 identities.
- Default authorization is fail-closed
  `PeerAuthorizationPolicy.RejectUnknown`.
- Added typed fingerprints, AppId-bound pairing QR text, exact per-connect
  pins, global pinned authorization, and an explicit-risk same-AppId admission
  policy.
- Authenticated messages and file-transfer control/content are protected by
  the secure record layer. Failed authentication never downgrades to plaintext.
- Secure and deprecated plaintext peers use separate discovery namespaces:
  `_p2pkit2._tcp`/protocol 2 and `_p2pkit._tcp`/protocol 1.
- Android secure identity uses Keystore-wrapped no-backup storage after
  `P2pKitAndroid.initialize`; iOS uses a device-only Keychain item. JVM hosts
  must provide a protected `JvmSecureIdentityStore`.

### Reliability and API behavior

- Retained independent advertising/discovery feature states and explicit
  transport capabilities.
- Hardened startup rollback, cancellation, reconnect, stop, file-transfer
  durability, parsing bounds, queue bounds, and session bookkeeping.
- Authenticated peers negotiate an application-message metadata envelope and
  durable SHA-256 file commit protocol.
- Public collection-valued models now expose immutable snapshots.
- Public API additions preserve the existing entry points; deprecated
  plaintext and legacy file APIs remain for an explicit migration period.

### Distribution

- Versioned as new `0.7.0-rc1` artifacts; existing `0.6.x` artifacts must not be
  overwritten.
- All four library modules produce Central-shaped POMs, sources, Dokka
  documentation, Gradle metadata, ABI baselines, dependency locks, and SBOM
  evidence.
- A credential-gated script builds a signed/checksummed Central Portal bundle
  without performing a remote upload.

See [`docs/guides/migrating-to-0.7.md`](docs/guides/migrating-to-0.7.md) before upgrading.

## 0.6.x

Legacy LAN protocol v1 line. Artifacts from this line are immutable.
