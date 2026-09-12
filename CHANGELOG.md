# Changelog

This file records release-facing behavior. Historical internal milestone tags,
audits, trackers, and implementation evidence remain under `docs/archive/`.

## Unreleased

`main` is the unreleased post-RC3 development line, including the consolidated
audit work. The `0.7.0-SNAPSHOT` label does not authorize shipping the changes
reserved below for **0.8.0+** in a 0.7 release without a new explicit owner decision.
The six real-world, independent-interoperability, and professional-audit areas
remain pending; no stable-release readiness claim is implied.

### Audit-origin Android provisioning address snapshots — reserved for 0.8.0+

- #282: Android manual connection information and hosted-network snapshots now
  share one IO-dispatched all-interface scanner. Usable IPv4 is retained and
  portable non-link-local unicast IPv6 candidates are included, so dual-stack
  consumers can see additional addresses and IPv6-only snapshots need not be
  empty. Sender-local IPv6 zones and deprecated site-local IPv6 are excluded.
  A snapshot is not proof of peer reachability: LAN-only route admission and
  fingerprint-pinned authentication are unchanged. Physical IPv6/OEM
  qualification remains pending.
- This integrated but unreleased behavior expansion is **not approved for a 0.7 release** and
  is not part of published RC3. Honor the 0.8.0+ target or obtain an explicit
  owner release decision; no version/tag/publication authorization is implied.

### Audit-origin discovery tightening — reserved for 0.8.0+

- #229: JVM/Android decode original DNS-SD TXT bytes rather than JmDNS's
  normalized property map. Malformed UTF-8 in a consumed field rejects the
  complete record, including earlier duplicate values; empty/boolean values
  stay empty and trailing NULs reach the existing semantic rejection checks.
  Unknown fields remain ignored, and correctly encoded Unicode (including
  literal U+FFFD) remains valid. Valid peers, security profiles and the wire
  format are unchanged. JVM/Android invalid re-resolutions still withdraw their
  old route.
- #356: Apple reads the original bounded TXT bytes for both native dictionary
  and buffer records. Unknown NUL-containing keys cannot supply or overwrite
  canonical fields, and valid fields after those keys remain readable.
  Failed access, truncated framing and malformed consumed values reject the
  whole record. Absent records and valid Unicode/empty/duplicate-value behavior
  stay compatible. This decoder change does not change discovery cache lifecycle.
- #332 (Apple follow-up): a non-admissible current-browser re-resolution now
  withdraws that native service's prior cache, endpoint and relay ownership.
  Invalid TXT cannot select another peer for removal; retired callbacks cannot
  delete replacement ownership. Repeated rejection is idempotent and valid
  recovery publishes a fresh Found lifecycle. Existing dial/session ownership,
  manual endpoints and independent advertising remain unaffected.
- This integrated audit-origin change is unreleased, **not** part of published RC3 and
  **not approved for a 0.7 release**. The current snapshot version label does
  not override #229's 0.8.0+ requirement. A release must honor that target or
  obtain an explicit owner decision before changing it; no version/tag or
  publication authorization is implied here.

### Audit-origin receive-backlog accounting — reserved for 0.8.0+

- #145: receive admission no longer creates UTF-8 arrays just to measure text
  or metadata. The unchanged 64-message/8 MiB caps now use an approximate
  retention-policy charge: 512 bytes/message, two bytes/text UTF-16 code unit
  (or actual binary payload length), and 256 bytes/metadata pair plus two
  bytes/key and value code unit. Recorded ownership is released on delivery,
  failed-send rollback and terminal drain; defensive binary copies remain.
- This tightens admission, not the wire format or public ABI. A legal 4 MiB
  ASCII message alone exceeds the budget by 512 bytes and fails the receiving
  session. See [operational limits](docs/reference/limits.md). The estimate is
  not an exact platform or whole-session heap bound. This integrated but unreleased change is
  **not approved for a 0.7 release**; honor the 0.8.0+ target or obtain a new
  explicit owner decision. No version/tag/publication is authorized here.

## 0.7.0-rc3 — release candidate (2026-08-09)

This candidate preserves the RC2 public API and secure-v2 wire format while
incorporating the post-RC2 dependency, LAN recovery, sample-diagnostics, and
repository-hardening work. It is intended to be the exact artifact set used
for the remaining real-world and independent validation campaigns.
It was published from immutable tag `v0.7.0-rc3` under the verified
`io.github.apdelrahman1911` Maven Central namespace.

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
