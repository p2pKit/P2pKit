# Changelog

This file records release-facing behavior. Historical internal milestone tags
and audit implementation details remain in the repository's stabilization
documents.

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

See [`docs/MIGRATING_TO_0.7.md`](docs/MIGRATING_TO_0.7.md) before upgrading.

## 0.6.x

Legacy LAN protocol v1 line. Artifacts from this line are immutable.
