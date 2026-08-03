# Stabilization & Release Checklist (RC gating)

**Status:** active gate for the authenticated-v2 `0.7.0-rc1` release candidate.
Existing `0.6.x` artifacts are immutable.
**Owner:** maintainer. **Updated:** 2026-07-28.

This document is the gate between "the audit branch is green in CI" and "we tag
an RC and publish artifacts." It has three parts:

- **Part A — Device smoke matrix:** the cross-platform manual validation the
  automated suites *cannot* cover (real radios, real Bonjour removal, real
  hotspot provisioning).
- **Part B — Publishing & signing:** how the wiring works and the exact steps
  for a local dry-run vs. a signed release.
- **Part C — Known caveats & RC checklist:** what is deferred, what is flaky,
  and the final sign-off boxes.

> Automated coverage today includes complete affected JVM, Android-host, and
> Apple-simulator gates for the remediation batches: `:p2p-core:jvmTest`,
> `:p2p-transport-lan:jvmTest`, the provisioning host suites, and
> `iosSimulatorArm64Test`, plus warning-free `check`, ABI, Dokka, SBOM,
> publication-shape, consumer, and XCFramework-provenance checks. These local
> gates still cannot prove two physical devices, cellular/Wi-Fi interface
> selection, AWDL, or LocalOnlyHotspot; hence Part A.
>
> The underlying loopback coverage remains: `:p2p-core:jvmTest`, `:p2p-transport-lan:jvmTest`
> (real TCP + mDNS loopback in one JVM: text, 200 KB binary, SHA-256-verified
> 5 MiB file), `:p2p-network-provisioning-android:testAndroidHostTest`,
> `:p2p-network-provisioning-desktop:test` (manual-IP loopback), and
> `:p2p-transport-lan:iosSimulatorArm64Test` (Bonjour + `nw_connection_t`).

---

## Part A — Device smoke matrix

Run each row on real hardware before the RC tag. Recipes live in
`INTERNAL_TESTING.md` (§A–§K); this matrix is the *minimum* pass set. Mark
PASS/FAIL/▢ and link logs.

Build the harnesses first:

```bash
./gradlew :p2p-sample-desktop:installDist          # JVM CLI
./gradlew :p2p-sample-desktop-ui:run               # Compose Desktop UI
./gradlew :p2p-sample-android:assembleDebug        # APK
./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance   # then build iosApp in Xcode
```

| # | Scenario | Devices | What it proves | Status |
|---|----------|---------|----------------|--------|
| A1 | Discover + pinned connect + text round-trip | Android ↔ JVM | secure namespace + Noise XX + authorization + encrypted HELLO/DATA cross-platform | ▢ |
| A2 | Discover + pinned connect + text round-trip | iOS ↔ JVM | Network.framework ↔ JmDNS secure-v2 wire compatibility | ▢ |
| A3 | Discover + pinned connect + text round-trip | iOS ↔ Android | both non-JVM secure stacks interoperate | ▢ |
| A4 | **Peer Lost** on remote stop (all pairs) | each pair | removal/`PeerEvent.Lost` delivery on real radios (the path the simulator suite can't reliably exercise — see C2) | ▢ |
| A5 | File transfer (≥5 MiB), SHA-256 verify both directions | each pair | FILE_* frames, chunking, reassembly, backpressure | ▢ |
| A6 | File transfer **cancel** mid-stream, session survives | iOS ↔ Android | per-transfer cancel ≠ session teardown | ▢ |
| A7 | Wi-Fi flap during a live session → auto-reconnect | Android ↔ JVM | reconnect re-resolves endpoint; iOS listener rebind | ▢ |
| A8 | App backgrounded/foregrounded mid-session (mobile) | iOS, Android | foreground-rebind + keep-alive survive suspension | ▢ |
| A9 | LocalOnlyHotspot **host** + Wi-Fi **join**, then A1 over the hotspot | 2× Android | `NetworkProvisioningManager` host/join lifecycle (never device-verified) | ▢ |
| A10 | Manual-IP fallback (mDNS blocked / different subnets) | JVM ↔ Android | `createManualPeer` + connect; manual peers are session-scoped | ▢ |
| A11 | Permission gating on a fresh install (no LAN perms granted) | Android 13+ & ≤12 | `P2pKit.permissions.missingPermissions()` reports correctly (new functional manager) | ▢ |
| A12 | Kill one side hard (no clean CLOSE) → other side surfaces terminal state, no hang | each pair | wedged-writer / keep-alive timeout + new socket-write watchdog | ▢ |

A12 specifically validates the new `JvmRawConnection` write-timeout watchdog
(`WRITE_TIMEOUT_MILLIS`) — pull the Ethernet/Wi-Fi on the receiver mid-send and
confirm the sender fails the connection instead of blocking forever.

---

## Part B — Publishing & signing

### What is wired (as of this branch)

- `maven-publish` on **all four** library modules: `:p2p-core`,
  `:p2p-transport-lan`, `:p2p-network-provisioning-android`,
  `:p2p-network-provisioning-desktop`. (The two provisioning sidecars were
  previously unpublishable — fixed in the audit.)
- Coordinates `dev.p2pkit:<module>:<VERSION_NAME>` from `gradle.properties`
  via the root `allprojects` block.
- Per-module POM metadata (name, description, license Apache-2.0, url, scm,
  developer) — Maven-Central-shaped.
- All four modules publish `-sources.jar` + `-javadoc.jar`. KMP publications
  use strict Dokka HTML output (`failOnWarning=true`) packaged as readable
  javadoc archives; the desktop sidecar (plain Kotlin/JVM) uses the same
  generated documentation contract.
- The release gate pins the Gradle wrapper and plugin inputs, verifies dependency
  metadata, writes dependency locks, emits a CycloneDX 1.6 SBOM containing only
  release components, and validates Kotlin ABI baselines. CI runs the same
  warning-free checks, documentation, ABI, SBOM, publication, and consumer
  gates with pinned GitHub Actions revisions.
- **Signing wired centrally** in the root `build.gradle.kts` for every module
  applying `maven-publish`, plus a `publish → sign` task dependency so the
  release path has no "uses output without declaring dependency" error.

### Signing is conditional (this is intentional)

Signing is **required only when a PGP key is supplied**. With no key:
`Sign*Publication` tasks are **SKIPPED**, so `publishToMavenLocal` and ordinary
dev/CI builds need no secrets and never fail on signing.

Supply the key via Gradle properties or env (`ORG_GRADLE_PROJECT_…`):

| Property | Env var | Value |
|----------|---------|-------|
| `signingInMemoryKey` | `ORG_GRADLE_PROJECT_signingInMemoryKey` | ASCII-armored PGP **secret** key |
| `signingInMemoryKeyPassword` | `ORG_GRADLE_PROJECT_signingInMemoryKeyPassword` | key passphrase |

### Local dry-run (no keys, validated on this branch)

The executable gate (coverage row P1-29) publishes to a throwaway repo —
never `~/.m2` — and asserts the full Central artifact set (main artifact +
`-sources.jar` + `-javadoc.jar` + `.pom` + `.module`) for every publication
of the four library modules:

```bash
scripts/check-publish-artifacts.sh           # run on macOS for the iOS klib rows
```

Manual unsigned shape equivalent:

```bash
./gradlew publishToMavenLocal \
  -Dmaven.repo.local=/absolute/path/to/isolated-p2pkit-repository
ls /absolute/path/to/isolated-p2pkit-repository/dev/p2pkit/*/0.7.0-rc1/
```

The checker validates every JVM, Android, and Apple publication (15 on macOS):
readable main/sources/Dokka archives, `.module`, and complete Central-shaped
POM metadata. With no key, `sign*Publication` reports `SKIPPED`.

### Signed Central Portal bundle (local only)

```bash
ORG_GRADLE_PROJECT_signingInMemoryKeyBase64="$BASE64_SECRET_KEY" \
ORG_GRADLE_PROJECT_signingInMemoryKeyPassword="$PASSPHRASE" \
MAVEN_SIGNING_KEY_FINGERPRINT="$FULL_PUBLIC_FINGERPRINT" \
  scripts/build-central-portal-bundle.sh \
    build/central/p2pkit-0.7.0-rc1-central-bundle.zip
```

The script publishes into an isolated temporary repository, re-runs the
artifact-shape checks, requires a PGP `.asc` signature for every deployed file,
generates Central-required MD5/SHA-1 plus SHA-256/SHA-512 checksums, and archives
the Maven repository layout. It refuses to overwrite an existing output and
**never uploads**.

This bundle-upload approach follows the
[Central Portal bundle format](https://central.sonatype.org/publish/publish-portal-upload/)
and [component requirements](https://central.sonatype.org/publish/requirements/)
without introducing a third-party Gradle publishing plugin.

The tag-only `Publish Maven Central` workflow repeats the full gate without
secrets. Its publishing job then waits on the protected `maven-central`
environment, builds the signed bundle, and uploads it exactly once with Central
Portal `AUTOMATIC` publishing. Status and public-repository reads are bounded;
an ambiguous upload is never retried. After `PUBLISHED`, every remote file is
compared with the reviewed bundle and isolated JVM/Android/KMP/iOS consumers
compile using only Maven Central.

> **REL-REMOTE-01 / BUILD-02 remains an external gate until executed:** the
> verified namespace, Portal token, protected GitHub environment, public key
> fingerprint, tag push, approval, Portal `PUBLISHED` state, and remote consumer
> evidence are all required. Repository code alone does not claim that
> `0.7.0-rc1` is remotely available.

### XCFramework provenance guard (manual verification)

`iosApp/scripts/check-xcframework.sh` gates every Xcode build on the declared
XCFramework provenance outputs: `BUILD_COMMIT.txt`,
`BUILD_SOURCE_STATE.txt`, and `BUILD_INPUTS_SHA256.txt`. The assembly task
tracks the exact commit, relevant tracked/untracked source state, and all
framework-shaping source/config files. The verification task refuses invalid
git identity or stale/missing sidecars before Xcode links either slice.
After touching the script or provenance block, verify all three behaviors:

1. **Unchanged commit/source → deterministic UP-TO-DATE build.** Run twice:

   ```bash
   sh ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance
   sh ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance
   sh iosApp/scripts/check-xcframework.sh
   # → "✅ XCFramework is fresh: <short> (matches HEAD, source state: clean|dirty)"
   ```

2. **Tracked or untracked framework input → rebuild and new fingerprint.**
   Edit or add a fixture under either module's `src/` tree and rerun the
   verification task. It must execute, record `dirty`, and change the SHA-256
   fingerprint. Restore the fixture and rerun before committing.

3. **Deleted sidecar → declared-output recovery.** Move one sidecar aside,
   rerun verification, and confirm Gradle executes the declared provenance
   writer and recreates the exact sidecar while the framework assembly itself
   may remain UP-TO-DATE:

   ```bash
   STAMP=p2p-transport-lan/build/XCFrameworks/release/BUILD_COMMIT.txt
   cp "$STAMP" /tmp/BUILD_COMMIT.txt.bak
   rm "$STAMP"
   sh ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance
   cmp "$STAMP" /tmp/BUILD_COMMIT.txt.bak
   ```

---

## Part C — Known caveats & RC checklist

### C1 — Still-deferred items (out of RC scope, tracked for later)

These are documented in `AUDIT_REPORT_2026-06.md`; none block an RC but should
be on the post-RC / encryption-milestone radar:

- Secure-v2 now authenticates/encrypts by default; `SecurityMode.NoneForMvp` is
  retained only as an explicit deprecated legacy mode with separate service
  namespaces and no automatic downgrade. Secure-v2 audit and physical
  interoperability evidence remain release gates.
- **iOS AWDL and interface selection** are implemented locally (peer-to-peer
  parameters, address-fingerprint rebind, Android selected-network routing,
  JVM rotation detection, bounded multi-address candidates), but require A1–A8
  physical-device and hostile-network evidence.

**Resolved during stabilization** (closed on this branch, no longer deferred):

- ✅ **Handshake-phase exceptions** now wrap into a typed `P2pError`
  (`SessionManager.runHandshake`).
- ✅ **`IosNetworkPathObserver` cellular-only** paths now report `Unsatisfied`,
  mirroring the cellular-prohibited data transport (no more reconnect storms
  during Wi-Fi gaps).
- ✅ **Test gaps** filled: `HandshakeIdentityTest` (outgoing peerId anti-spoof:
  match / mismatch / self-collision) and `KeepAliveTest` (PONG responder +
  positive stays-connected path).
- ✅ **Mechanical doc-drift** swept (stale NsdManager current-state references,
  the `gradle.properties` publishing comment).

### C2 — Simulator and physical-radio boundary

`:p2p-transport-lan:iosSimulatorArm64Test` currently passes every executed
test in the affected suite; one manual diagnostic remains intentionally skipped.
Simulator execution cannot prove physical Bonjour removal, AWDL, DHCP/address
rotation, or abrupt hostile-network departure. **Action:** validate those
paths on real devices via A1–A8 and the LAN diagnostic protocol, preserving
exact assertions and bounded timeouts.

### C3 — RC sign-off checklist

- [ ] All four host/JVM suites green (3× under parallel load): `core:jvmTest`,
      `transport-lan:jvmTest`, provisioning `-android`/`-desktop`.
- [ ] JVM, Android, and iOS-simulator targets all **compile**.
- [ ] `iosSimulatorArm64Test` green for all executed tests; complete the manual
      diagnostic and physical-radio evidence in A1–A8.
- [ ] Part A device smoke matrix: A1–A8, A10–A12 PASS; A9 PASS or explicitly
      waived for the RC.
- [ ] `scripts/check-publish-artifacts.sh` PASSes on macOS (full Central
      artifact set — main artifact + sources + javadoc + pom + module — for
      every publication of all four modules); `sign*` SKIPPED without a key.
- [ ] `scripts/build-central-portal-bundle.sh` with the release key PASSes,
      every deployed file has a signature/checksum, and the recorded archive
      SHA-256 matches the reviewed upload.
- [ ] Release notes state the trust model honestly: secure-v2 is the default
      authenticated/encrypted mode; deprecated `NoneForMvp` is explicit legacy
      only, with cryptographic audit and physical interoperability still open.
- [x] **Decision box — `P2pMessage.metadata`: SUPERSEDED AND IMPLEMENTED.**
      The 2026-07-04 legacy-v1 decision remains true for explicit legacy
      sessions. On 2026-07-22 the owner approved `PARSE-META-01`: authenticated
      secure peers negotiate a canonical metadata envelope in encrypted HELLO;
      non-empty metadata never silently downgrades. See C4 and spec §9.4.
- [x] **Decision box — `P2pPermission.ChangeWifiState` disambiguation (C:54;
      decision #4a): DECIDED, deferral recorded, 2026-07-04.** The A09
      re-verification confirmed the enum member has a single Android mapping
      today — the provisioning sidecar's `CHANGE_WIFI_STATE`; core stopped
      mapping it to `CHANGE_WIFI_MULTICAST_STATE` in the AUDIT-2026-06
      permission-gate fix — so the C:54 deferral is assessed sound and no
      enum rework is warranted. Revisit only if a second platform mapping
      for the member appears.
- [ ] Tag `v0.7.0-rc1` only after the preceding gates and
      capture the device-matrix, bundle, and Portal-validation evidence.

### C4 — Negotiated secure metadata envelope (implemented from PARSE-META-01)

Explicit legacy protocol v1 remains metadata-free. The owner approved the
authenticated, negotiated secure-v2 envelope on 2026-07-22.

- **Negotiation:** encrypted HELLO features include
  `app-message-envelope-v1`; capability intersection is immutable for one
  connection epoch.
- **Envelope:** canonical commonMain binary encoding authenticates type, frame
  id, monotonic per-direction sequence, sender, recipient, sorted metadata,
  content length, content digest, and content through the secure record AEAD.
- **Compatibility:** empty-metadata raw DATA remains readable when a secure
  peer lacks the feature; non-empty metadata fails typed. Legacy v1 bytes are
  unchanged. Invalid envelopes fail the session closed.
- **Bounds/tests:** entry/key/value/aggregate bounds, canonical ordering,
  identity mismatch, digest tamper, id reuse, sequence replay, feature
  downgrade, and end-to-end metadata round-trip are deterministic tests.
