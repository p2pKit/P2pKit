# Stabilization & Release Checklist (RC gating)

**Status:** active worklist for cutting the first release-candidate tag off
`audit/exhaustive-review-2026-06` (current `VERSION_NAME=0.6.0`).
**Owner:** maintainer. **Updated:** 2026-06-13.

This document is the gate between "the audit branch is green in CI" and "we tag
an RC and publish artifacts." It has three parts:

- **Part A — Device smoke matrix:** the cross-platform manual validation the
  automated suites *cannot* cover (real radios, real Bonjour removal, real
  hotspot provisioning).
- **Part B — Publishing & signing:** how the wiring works and the exact steps
  for a local dry-run vs. a signed release.
- **Part C — Known caveats & RC checklist:** what is deferred, what is flaky,
  and the final sign-off boxes.

> Automated coverage today: `:p2p-core:jvmTest`, `:p2p-transport-lan:jvmTest`
> (real TCP + mDNS loopback in one JVM: text, 200 KB binary, SHA-256-verified
> 5 MiB file), `:p2p-network-provisioning-android:testAndroidHostTest`,
> `:p2p-network-provisioning-desktop:test` (manual-IP loopback), and
> `:p2p-transport-lan:iosSimulatorArm64Test` (Bonjour + `nw_connection_t`).
> None of these exercise two physical devices, cellular/Wi-Fi interface
> selection, or LocalOnlyHotspot — hence Part A.

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
./gradlew :p2p-transport-lan:assembleP2pKitSharedXCFramework   # then build iosApp in Xcode
```

| # | Scenario | Devices | What it proves | Status |
|---|----------|---------|----------------|--------|
| A1 | Discover + connect + text round-trip | Android ↔ JVM | mDNS Found + HELLO handshake + DATA framing cross-platform | ▢ |
| A2 | Discover + connect + text round-trip | iOS ↔ JVM | Network.framework ↔ JmDNS wire-compat | ▢ |
| A3 | Discover + connect + text round-trip | iOS ↔ Android | both non-JVM stacks interop | ▢ |
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
- The desktop sidecar publishes `-sources.jar` + `-javadoc.jar` (Central
  requires both); KMP modules get theirs automatically.
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

```bash
./gradlew publishToMavenLocal
ls ~/.m2/repository/dev/p2pkit/*/0.6.0/      # jars, -sources, -javadoc, .pom, .module
```

Verified output for the two new sidecars: `*.jar`, `*-sources.jar`,
`*-javadoc.jar`, `*.module`, `*.pom`; POM carries group/artifact/version +
license + scm; `sign*Publication` reported `SKIPPED`.

### Signed release (CI / Central)

```bash
ORG_GRADLE_PROJECT_signingInMemoryKey="$(cat secret.asc)" \
ORG_GRADLE_PROJECT_signingInMemoryKeyPassword="$PASSPHRASE" \
  ./gradlew publishToMavenLocal      # confirm .asc signatures now appear
```

> **Remaining release-infra step (NOT yet wired):** the publishing block has no
> remote `repositories { maven { … } }` target, so artifacts can be produced
> and signed but not yet *uploaded* to Maven Central. Before the public release
> (not required for an internal RC tag), add a Central Portal / Sonatype
> repository + credentials — e.g. the `com.vanniktech.maven.publish` or
> `nmcp` plugin — and a `publish` (not just `publishToMavenLocal`) smoke run.

---

## Part C — Known caveats & RC checklist

### C1 — Still-deferred items (out of RC scope, tracked for later)

These are documented in `AUDIT_REPORT_2026-06.md`; none block an RC but should
be on the post-RC / encryption-milestone radar:

- **Inbound HELLO peerId is not verified** (`SessionManager`, `TODO(encryption-milestone)`).
  Trusted-LAN only under `SecurityMode.NoneForMvp`; the real fix is the
  encryption handshake. The reject-own-peerId guard is in place.
- **`SessionManager` handshake-phase exceptions** can still escape `connect()`
  as non-`P2pError` (only transport-connect is wrapped). Cheap follow-up: wrap
  the handshake path too.
- **iOS `include_peer_to_peer` asymmetry** (browser vs. listener/connection) —
  AWDL peers may be undialable; needs device testing (A2/A3) to confirm fix
  direction.
- **Interface selection** (`AndroidLanDiscoveryTransport`, `JvmLanDiscoveryTransport`)
  can bind a cellular/loopback NIC; JVM has no network-rotation rebind. Validate
  on multi-interface hardware (A7).
- **`IosNetworkPathObserver` counts cellular as Satisfied**, diverging from the
  cellular-prohibited data transport — can drive reconnect storms.
- **Test gaps:** no `HandshakeTest` (outgoing peerId anti-spoof) / `KeepAliveTest`
  (positive PING/PONG path).
- **~remaining doc-drift minors** — mechanical, low risk.

### C2 — Known-flaky automated tests (pre-existing, not regressions)

`:p2p-transport-lan:iosSimulatorArm64Test` →
`IosLanLifecycleTest.peerLostEventFiresWhenPeerStops` and
`advertiseStopRestartProducesObservablePeerChurn` **fail on the macOS
simulator** (verified failing on the pre-audit baseline too, with 30 s
timeouts). Root cause: the simulator's NWBrowser does not reliably deliver
*removed* results (peer-Lost / churn); the **Found**, handshake, 5 MiB file
transfer + cancel, and reconnect-exhaustion tests in the same suite pass.
**Action:** validate the Lost path on real devices via **A4** — do not mask
these by widening the (already 30 s) timeouts or `@Ignore`. Re-evaluate after
A4 passes on hardware.

### C3 — RC sign-off checklist

- [ ] All four host/JVM suites green (3× under parallel load): `core:jvmTest`,
      `transport-lan:jvmTest`, provisioning `-android`/`-desktop`.
- [ ] JVM, Android, and iOS-simulator targets all **compile**.
- [ ] `iosSimulatorArm64Test` green **except** the two C2 churn tests.
- [ ] Part A device smoke matrix: A1–A8, A10–A12 PASS; A9 PASS or explicitly
      waived for the RC.
- [ ] `./gradlew publishToMavenLocal` produces jars + sources + javadoc + pom
      for all four modules; `sign*` SKIPPED without a key.
- [ ] One signed `publishToMavenLocal` run with a test key produces `.asc`
      signatures.
- [ ] Release notes state the trust model honestly: identity/encryption is
      `NoneForMvp` (trusted-LAN only) — C1 first bullet.
- [ ] Tag `v0.6.0-rc1` (or chosen RC id) and capture the device-matrix logs.
