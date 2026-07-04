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
- All four modules publish `-sources.jar` + `-javadoc.jar` (Central requires
  both). The KMP plugin does **not** attach a javadoc jar automatically
  (verified 2026-07, finding BLD-2 — an earlier revision of this doc claimed
  otherwise): the root `build.gradle.kts` attaches an empty Kotlin-style
  javadoc jar to every KMP publication; the desktop sidecar (plain
  Kotlin/JVM) uses `withJavadocJar()`.
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

Manual equivalent:

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

### XCFramework provenance guard (manual verification)

`iosApp/scripts/check-xcframework.sh` gates every Xcode build on the
`BUILD_COMMIT.txt` stamp. The stamp is only written when the assemble task
actually executes, so after a commit that touches no framework source
(docs/Swift/project.yml) the task is UP-TO-DATE and the stamp legitimately
lags HEAD — the script accepts that case by diffing the stamped commit
against HEAD over the framework-relevant paths (both modules' `src/`, their
`build.gradle.kts`, `gradle/libs.versions.toml`). After touching the script
or the provenance block, verify all three behaviors:

1. **Docs-only commit → UP-TO-DATE assemble, check still passes.** Commit a
   docs-only change, then:

   ```bash
   sh ./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework   # UP-TO-DATE, stamp unchanged
   sh iosApp/scripts/check-xcframework.sh
   # → "✅ XCFramework stamped at <short>; no framework sources changed through HEAD — OK"
   ```

2. **Kotlin edit → rebuild, re-stamp, pass.** Edit any file under
   `p2p-transport-lan/src` or `p2p-core/src`, commit, and re-run the two
   commands above — the assemble task executes (not UP-TO-DATE), re-stamps,
   and the check prints `✅ XCFramework is fresh: <short> (matches HEAD)`.

3. **Stale stamp + real source diff → hard fail.** Forge a stamp older than
   the last source-touching commit (the script's embedded assemble run is
   UP-TO-DATE, so it won't overwrite the forgery) and confirm the guard
   refuses, then restore:

   ```bash
   STAMP=p2p-transport-lan/build/XCFrameworks/release/BUILD_COMMIT.txt
   cp "$STAMP" /tmp/BUILD_COMMIT.txt.bak
   git rev-parse "$(git log -1 --format=%H -- p2p-transport-lan/src p2p-core/src)^" > "$STAMP"
   sh iosApp/scripts/check-xcframework.sh   # → "error: XCFramework identity mismatch", exit 1
   cp /tmp/BUILD_COMMIT.txt.bak "$STAMP"
   ```

---

## Part C — Known caveats & RC checklist

### C1 — Still-deferred items (out of RC scope, tracked for later)

These are documented in `AUDIT_REPORT_2026-06.md`; none block an RC but should
be on the post-RC / encryption-milestone radar:

- **Inbound HELLO peerId is not verified** (`SessionManager`, `TODO(encryption-milestone)`).
  Trusted-LAN only under `SecurityMode.NoneForMvp`; the real fix is the
  encryption handshake. The reject-own-peerId guard is in place.
- **iOS `include_peer_to_peer` asymmetry** (browser vs. listener/connection) —
  AWDL peers may be undialable; needs device testing (A2/A3) to confirm fix
  direction.
- **Interface selection** (`AndroidLanDiscoveryTransport`, `JvmLanDiscoveryTransport`)
  can bind a cellular/loopback NIC; JVM has no network-rotation rebind. Validate
  on multi-interface hardware (A7).

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
- [ ] `scripts/check-publish-artifacts.sh` PASSes on macOS (full Central
      artifact set — main artifact + sources + javadoc + pom + module — for
      every publication of all four modules); `sign*` SKIPPED without a key.
- [ ] One signed `publishToMavenLocal` run with a test key produces `.asc`
      signatures.
- [ ] Release notes state the trust model honestly: identity/encryption is
      `NoneForMvp` (trusted-LAN only) — C1 first bullet.
- [x] **Decision box — `P2pMessage.metadata` (decision #3): DECIDED, option
      (c), 2026-07-04.** Metadata is documented as **not transmitted in
      protocol v1** (`P2pMessage` KDoc + spec §9.4), the receive side is
      pinned empty by `MessageMetadataContractTest` (P1-06), and real
      transmission is scheduled as the post-RC `metadata-wire` milestone
      (C4). The RC must not tag with this line undecided (DOCA-14).
- [x] **Decision box — `P2pPermission.ChangeWifiState` disambiguation (C:54;
      decision #4a): DECIDED, deferral recorded, 2026-07-04.** The A09
      re-verification confirmed the enum member has a single Android mapping
      today — the provisioning sidecar's `CHANGE_WIFI_STATE`; core stopped
      mapping it to `CHANGE_WIFI_MULTICAST_STATE` in the AUDIT-2026-06
      permission-gate fix — so the C:54 deferral is assessed sound and no
      enum rework is warranted. Revisit only if a second platform mapping
      for the member appears.
- [ ] Tag `v0.6.0-rc1` (or chosen RC id) and capture the device-matrix logs.

### C4 — Post-RC milestone: `metadata-wire` (from decision #3, recorded 2026-07-04)

Owner-approved follow-up to decision #3 option (c): protocol v1 does not
transmit `P2pMessage.metadata` (see the C3 decision box). The owner wants
metadata transmission to land **soon after the RC line** — this section is
the durable record of that milestone.

- **What:** serialize `metadata` in a DATA-payload **envelope**. The PP2K
  magic, version byte, 36-byte header, frame types, and `ProtocolConstants`
  limits stay untouched; only the DATA payload encoding gains an envelope
  (metadata + payload). The codec lives in commonMain, so all three
  platforms share one implementation — no per-platform mirroring needed.
- **Where:** `p2p-core` `protocol/` — encode in `Chunker.chunk` (today it
  reads only `value`/`bytes`), decode in `Reassembler.decodePayload` (today
  it reconstructs with the `emptyMap()` default); update `P2pMessage` KDoc,
  spec §9.4, and **consciously flip the P1-06 pin** in
  `MessageMetadataContractTest` from asserted-empty to round-trip equality
  in the same commit.
- **Prerequisites (must be decided before any bytes change):**
  1. **Cross-version interop stance** — a metadata-capable sender to a v1
     receiver (and the reverse) must have defined behavior: candidate
     mechanisms are a HELLO-negotiated capability, a reserved DATA flag bit,
     or a protocol version bump. Pick one and document the compatibility
     matrix; a v1 receiver must never misparse an envelope as payload bytes.
  2. **Bounds and input validation on receive** — metadata key/value/count
     limits sized against the 4 MiB message cap and the reassembly caps, so
     malformed or excessive metadata from a peer is rejected as a typed,
     bounded failure rather than growing memory or throwing untyped.
  3. **Protocol version consideration** — decide whether this is v1.1
     (envelope negotiated in-band, version byte unchanged) or v2 (version
     byte bump); the wire-parity rule (identical across jvmMain/androidMain/
     appleMain) applies to whichever is chosen.
- **Not before:** the v0.6 RC tag — this work is scoped post-RC by decision
  #3(c); the RC ships the documented local-only contract above.
