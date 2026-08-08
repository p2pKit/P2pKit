# P2pKit remediation continuation handoff

Prepared: 2026-07-22

Repository: `/Users/abdelrahman/Projects/P2pKit`

Branch: `remediation/full-register-2026-07`

Committed HEAD when this handoff was created: `c09c8c787c62808df47109276b11725385c6a0be`

This document is the standalone continuation record for a new agent/chat. It describes what is complete, what is only implemented locally, the exact in-progress worktree, verification already performed, known blockers, and the dependency-ordered next work. It does not replace the authoritative mutable tracker:

- `P2PKIT_REMEDIATION_TRACKER_2026-07.md`

## 1. Goal and working rules

The unchanged goal is to resolve all 150 findings and all 54 explicit test gaps from the P2pKit full-code review, implement every locally actionable fix, add deterministic regression coverage, verify affected platforms, create logical commits, push authorized commits, and continue until no dependency-ready unblocked work remains.

Use subsystem batches rather than one finding per cycle. The preferred order is security/identity, core lifecycle/sessions, protocol, transfer, LAN, provisioning, samples, then build/release. For each batch:

1. Record a concise plan and finding/test-gap mapping in the tracker.
2. Implement the smallest complete architectural correction.
3. Add deterministic success, failure, cancellation, timeout, concurrency, cleanup, and boundary tests as applicable.
4. Use focused compilation/tests during implementation.
5. Run the complete affected-module/platform checkpoint when the batch is complete.
6. Review `git diff`, equivalent platform implementations, and `git diff --check`.
7. Create a focused human-readable commit and rerun the required committed-state checks.
8. Push only to an explicitly authorized remote.

Do not weaken assertions, permit multiple terminal outcomes, inflate timeouts to hide races, swallow `CancellationException`, silently ignore cleanup errors, or replace required production/platform behavior with mocks. Existing unrelated baseline failures may be recorded without blocking a valid independent batch.

Never claim production readiness until all findings/gaps are resolved, the repeated complete gate is green, and the required cryptographic audit, real-device, two-machine, hostile-network, and release-service validation is complete.

## 2. Protected user-owned files

The following untracked files/directories predate or are outside this remediation workflow. Do not read, modify, delete, stage, or commit them:

- `.review-2026-07/`
- `DEFERRED_ITEMS_REGISTER_2026-07.md`
- `P2PKIT_FULL_CODE_REVIEW_2026-07-17.md`

The mutable tracker and this handoff document are allowed remediation documents.

## 3. Source-control and push state

The working branch is `remediation/full-register-2026-07`. Commit `b79c9ba` and its SEC-01 tracker update were pushed successfully earlier. Later local commits are not pushed because of `SCM-PUSH-01`.

The configured origin is `https://github.com/Apdelrahman1911/P2pKit.git`, but the server reports that the repository moved to `https://github.com/p2pKit/P2pKit.git`. A later push was not authorized after this ownership/destination change became visible. Do not change the remote or retry pushing without an explicit owner reply.

Recommended authorization reply:

`Approve SCM-PUSH-01 canonical https://github.com/p2pKit/P2pKit.git`

Alternative:

`Approve SCM-PUSH-01 current https://github.com/Apdelrahman1911/P2pKit.git`

Until approval, keep making focused local commits, record `push blocked at SCM-PUSH-01`, and leave affected rows `Implemented` rather than `Verified` where the tracker definition requires a successful push.

## 4. Repository state at handoff

Committed HEAD is `c09c8c7` (`docs(remediation): record LAN-NET-SCHEMA-01 evidence`). The current LAN liveness/routing batch is implemented in the worktree but is not yet fully checkpointed, documented in the tracker, or committed.

Modified tracked files:

- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt`
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/Internal.kt`
- `p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/DiscoveryReemitContractTest.kt`
- `p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDataTransport.kt`
- `p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDiscoveryTransport.kt`
- `p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDsl.kt`
- `p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDataTransport.kt`
- `p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDiscoveryTransport.kt`
- `p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt`
- `p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/AnnounceCacheReconcileTest.kt`
- `p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosLanRecoveryTest.kt`
- `p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/JmdnsLifecycleCoordinator.kt`
- `p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt`
- `p2p-transport-lan/src/commonTest/kotlin/dev/p2pkit/transport/lan/PeerRecordValidationTest.kt`
- `p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDataTransport.kt`
- `p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryTransport.kt`
- `p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/HostSelectorTest.kt`
- `p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsLifecycleCoordinatorTest.kt`
- `p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryHeartbeatTest.kt`
- `p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h`

New source/test files:

- `p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanNetworkState.kt`
- `p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JvmLanCandidateFallbackTest.kt`

This handoff file is also new. Do not stage the three protected untracked entries listed above.

## 5. Completed and committed remediation history

The commits after the review baseline `6a05ccd` are, in order:

| Batch | Code commit(s) | Documentation commit(s) | Result |
| --- | --- | --- | --- |
| SEC-01 secure protocol v2 | `b79c9ba` | `42458f9` | Authenticated/encrypted v2 and protected identities implemented; pushed; external assurance remains |
| BUILD-02 analysis | — | `079de28` | Central publication path blocked pending owner/service decision |
| BUILD-01 public ABI metadata | `8f15d75` | `c12e91d` | Correct API dependency scopes and isolated published-consumer gate verified |
| CORE-01 lifecycle generation | `a4e0bb0` | `b8bf5a8` | Terminal lifecycle commits serialized and verified |
| ID-STORE-01 legacy identity | `ee69d09` | `48c33d7` | Collision-safe, concurrent, atomic persistence verified |
| CORE-SESSION-01 | `68934be`, `82a9b41` | `7ee1dfb` (shared) | Connect/session ownership and terminal-state races verified |
| PARSE-01 | `aa3ac0c`, `6171588` | `7ee1dfb` (shared) | Parser complexity, framing, structure, diagnostics, and canonical text verified |
| XFER-01 | `68c579f` | `8288df5` | Transfer ownership/timeouts/concurrency/bounds verified; separate API/wire decisions remain |
| PEER-CTRL-01 | `ee2cae5` | `981d771` | Aggregation, duplicate direction, control-plane backpressure, monotonic keepalive implemented; push blocked |
| CORE-LIFE-02 | `60aecf6` | `ab6f0db` | Discovery rollback, bounded cleanup, inbound recollection implemented; one data-transport API decision remains |
| LAN-CONN-01 | `b21ed84` | `36ad189`, `e5711a7` | Connection admission/cancellation/read/write/listener ownership implemented |
| LAN-JMDNS-02 | `83db1ab` | `3d3dd57` | Transactional JmDNS registration/restoration/cleanup and retry generation implemented |
| LAN-APPLE-03 | `703182a` | `d96ed56` | Apple browser/listener/cache recovery and cleanup implemented |
| LAN-NET-SCHEMA-01 | `2895ff1`, `09af6b5` | `c09c8c7` | TXT/schema/service ownership and diagnostic hardening implemented |

At committed HEAD the tracker reports 83 `Planned`, 27 `Implemented`, 29 `Verified`, and 11 `Blocked`. Those counts intentionally do not yet include the active uncommitted LAN batch and must be recalculated when its tracker update is made.

## 6. Major completed architecture

### 6.1 SEC-01: secure protocol v2 and identity

`b79c9ba` replaces the unusable post-parser security hook with a security-owned raw stream and authenticated protocol v2. The complete frozen contract is in `P2PKIT_REMEDIATION_TRACKER_2026-07.md` under `SEC-01 implementation contract freeze — Frozen 2026-07-17`; do not alter it without a new owner decision.

Key guarantees:

- Secure v2 uses only `Noise_XX_25519_ChaChaPoly_SHA256`, suite ID `0x01`.
- Exact 16-byte `P2KS` v2 preface and transcript-bound AppId; no negotiation or fallback.
- The transport dialer is initiator; accepted connection is responder.
- The security pump is the sole `RawConnection.read()` collector for the connection lifetime.
- HELLO, frame headers, controls, messages, and file data are encrypted and use inner major 2.
- Record encryption uses bounded 16 KiB plaintext segments, ordered implicit nonces, serialized writes, and terminal failure on tamper/replay/reorder/truncation/exhaustion.
- `SecurityMode.NoneForMvp` remains only as explicitly selected deprecated whole-kit legacy v1. Secure and legacy LAN use distinct service namespaces. No automatic downgrade exists.
- Identity is per-AppId exportable X25519. Peer IDs and full fingerprints use domain-separated SHA-256 and canonical lowercase unpadded Base32.
- Unknown identities are rejected by default. Supported authorization is configured full fingerprint/trusted store, manual full fingerprint, or explicitly enabled `AcceptAnyAuthenticatedSameApp`.
- Secure manual IP requires the expected full fingerprint. Discovery identifiers remain untrusted routing hints until key possession is proven.
- Reconnect retains the authenticated fingerprint and cannot change identity when routing changes.
- Secure migration creates a new key-derived identity and never overwrites/deletes the legacy UUID. Explicit rollback resumes the untouched legacy UUID and v1 behavior; re-enabling secure mode returns to the stored v2 identity.
- Android wraps the strict 104-byte identity record with a non-exportable Android Keystore AES-256-GCM key and stores ciphertext in no-backup storage.
- iOS stores the identity in a device-only, non-synchronizable Keychain item with a strict nonsecret marker.
- JVM requires an injected `JvmSecureIdentityStore`; core has no silently plaintext secure default.
- Corruption, missing wrapping key, inconsistent marker/blob, CSPRNG failure, or storage failure fails closed. No automatic identity rotation or legacy fallback occurs.
- Key loss recovery requires explicit destructive reset and creates a new PeerId requiring re-pinning.

Local common/JVM/Apple cryptographic vectors, secure-session integration, raw confidentiality, tamper/replay/version/downgrade, authorization, migration, key-store state matrices, manual pinning, and single-reader tests passed. SEC-01 remains externally gated by professional cryptographic design/code audit, physical API-24/mobile interoperability, hostile-network validation, and the final complete gate.

### 6.2 Core lifecycle, sessions, identity, parser, and transfer

Implemented/verified behavior includes:

- Lifecycle generation prevents advertising, discovery, observer startup, connect, or session publication after terminal `stop()`.
- Pending connects, raw connections, sessions, registration, and remote terminal jobs have explicit transactional ownership and cleanup.
- Session registration lookup uses safe published state, shutdown drains terminal entries, and current unsatisfied path state is applied to newly registered sessions.
- Legacy PeerId persistence uses collision-safe AppId hashing, concurrent durable winner selection, JVM atomic move/fsync, Android `AtomicFile`, iOS locked hash-bucket migration, and stable instance memoization.
- Frame parsing validates the fixed header early, enforces packet-specific limits, avoids quadratic tail copying, isolates hostile diagnostics, and validates strict UTF-8/canonical wire text.
- Application delivery is separated from protocol controls with count/byte bounds; overflow terminalizes explicitly.
- File acceptance, idle/overall deadlines, sink serialization, terminal progress, source/sink release, chunk arithmetic, transfer-ID uniqueness, timeout authority, and platform snapshot checks were corrected.

Still intentionally separate are file durability acknowledgement/digest (`FILE-04/13`), retained offers (`FILE-05/06` receiver side), typed transfer errors (`FILE-11`), and metadata wire semantics (`PROTO-08`).

### 6.3 LAN lifecycle and schema batches

Committed LAN work now provides:

- Bounded Apple inbound queue and deterministic overflow/drain cancellation.
- Cancellation-safe JVM/Android/Apple outbound connect ownership.
- Raw-read cancellation that closes native I/O, ordinary write failure terminalization, and Apple queued-writer close recheck.
- Fatal listener depublishing/rebind and terminal port/reference clearing.
- Transactional JmDNS service/listener creation, restoration, cancellation compensation, retained cleanup ownership, per-target retry budgets, and synchronized debounce replacement.
- Apple listener/browser host-intent separation, cancellable readiness, self-recovery, terminal depublishing, cache-prune/rediscovery serialization, and validated TXT-less removal handling.
- Central bounded LAN TXT schema, exact service-instance ownership, Unicode/control sanitization, Apple opt-in history, and Android default-off routine diagnostics.

## 7. Active uncommitted LAN liveness/routing batch

### 7.1 Scope

The active batch covers the locally actionable parts of `LAN-13`, `LAN-14`, `LAN-16`, `LAN-17`, `LAN-18`, and related `LAN-T07/LAN-T08`. It builds on the committed lifecycle/schema work.

### 7.2 Implemented worktree behavior

Discovery lifetime:

- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/Internal.kt` adds additive `DiscoveryLifetime`, `TransportHint.withDiscoveryLifetime()`, and `InternalPeer.discoveryLifetime()` using reserved hint metadata. This preserves the `InternalPeer` data-class constructor ABI.
- `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt` no longer applies the core 15-second timer to transport-managed contributions. Exact source `Lost` or transport shutdown owns expiration.
- `DiscoveryReemitContractTest.kt` covers ordinary event-based timeout and transport-managed lifetime followed by exact `Lost`.

Native liveness:

- `JmdnsLifecycleCoordinator.kt` no longer owns a cached-peer heartbeat job/configuration.
- JVM and Android discovery transports no longer re-emit cached peers as proof of liveness.
- Apple cache reconciliation now only removes stale browser generations and emits `Lost`; it does not synthesize `Updated` events.
- LAN-discovered peers are tagged `TransportManaged`, making native JmDNS/NWBrowser TTL/removal authoritative.
- JmDNS removal ownership permits a current listener to consume removal for an admission owned by its deactivated predecessor, while still preventing stale listeners from withdrawing newer ownership.

Rebind correctness:

- `JmdnsLifecycleCoordinator.kt` supports a forced same-network rebind that survives callback coalescing through `pendingForcedRebind`.
- Initial `boundDefaultNetwork` comes from `observedDefaultNetwork()` rather than a second `currentNetwork()` query.
- `JmdnsLifecycleCoordinatorTest.kt` proves forced same-network address rotation is not lost.

Multi-address routing:

- `Lan.kt` adds bounded `LanEndpoint`, `InternalPeer.lanEndpoints()`, and `lanTransportHints()`.
- At most eight dial candidates are retained. Multiple candidates get a 1.5-second per-candidate attempt within one 5-second global monotonic budget; a single candidate retains the existing 5-second budget.
- JVM/Android host selection deduplicates candidates, prefers IPv4 then IPv6, preserves stable order within a family, rejects loopback/wildcard/unscoped IPv6 link-local candidates, and when local prefixes are known admits only same-subnet candidates.
- JVM/Android data transports try candidates in order, close every failed/cancelled socket, preserve `CancellationException`, and aggregate endpoint failures.
- `JvmLanCandidateFallbackTest.kt` proves the failed first socket is closed and the second candidate succeeds.
- `HostSelectorTest.kt` covers off-subnet rejection, same-subnet ordering, deduplication, and the candidate cap.

JVM rotation:

- `JvmLanDiscoveryTransport.kt` polls a real nonloopback, nonvirtual, non-point-to-point interface/address fingerprint every second and asks the coordinator to rebind when the concrete set changes.
- The watcher is stopped with transport lifecycle.
- Current limitation: JmDNS still creates one default-interface handle unless the existing test bind override is used. This batch detects/rebinds rotation but does not create one simultaneous JmDNS handle per interface.

Android selected-network routing:

- New `AndroidLanNetworkState.kt` is shared by discovery and data through `AndroidLanDsl.kt`.
- Discovery selects a real Wi-Fi/Ethernet `Network`, never cellular, selects IPv4 then IPv6 bind addresses, and publishes the selected `Network`.
- Outbound TCP uses `selectedNetwork.socketFactory.createSocket()`. Ordinary socket fallback remains only for hotspot/manual cases where no Android `Network` exists.
- The first primary LAN callback is skipped only when it is genuinely the already-bound network.
- `onLinkPropertiesChanged` requests a forced same-Network rebind for DHCP/address rotation.
- A briefly introduced deprecated `allNetworks` use was removed; no new Android deprecation warning remains.

Apple routing/AWDL:

- `IosLanDataTransport.kt` enables peer-to-peer on shared listener/dial Network.framework parameters while retaining the cellular prohibition.
- A test seam verifies `nw_parameters_get_include_peer_to_peer()` is true.
- Apple path monitoring includes a native interface-address fingerprint so same-interface address changes trigger rebind even when interface-type flags do not change.
- `p2pkit_nw.h` obtains an order-independent hash of UP, nonloopback IPv4/IPv6 interface addresses with `getifaddrs`.
- `IosLanRecoveryTest.kt` covers peer-to-peer parameters and address-change rebind decisions.

### 7.3 Focused verification already completed

The following focused command passed after the ABI-preserving lifetime representation and JmDNS ownership correction:

```text
./gradlew :p2p-core:jvmTest \
  --tests dev.p2pkit.core.internal.DiscoveryReemitContractTest \
  --tests dev.p2pkit.core.internal.PeerRegistryTest \
  :p2p-transport-lan:jvmTest \
  --tests dev.p2pkit.transport.lan.HostSelectorTest \
  --tests dev.p2pkit.transport.lan.JvmLanCandidateFallbackTest \
  --tests dev.p2pkit.transport.lan.JmdnsLifecycleCoordinatorTest \
  --tests dev.p2pkit.transport.lan.PeerRecordValidationTest \
  --tests dev.p2pkit.transport.lan.JvmDiscoveryRecordValidationTest \
  :p2p-transport-lan:iosSimulatorArm64Test \
  --tests dev.p2pkit.transport.lan.AnnounceCacheReconcileTest \
  --tests dev.p2pkit.transport.lan.IosLanRecoveryTest \
  --tests dev.p2pkit.transport.lan.PeerRecordValidationTest \
  :p2p-transport-lan:compileAndroidMain --stacktrace
```

Result: `BUILD SUCCESSFUL` in 43 seconds.

After the initial/default binding correction, this command also passed:

```text
./gradlew :p2p-transport-lan:jvmTest \
  --tests dev.p2pkit.transport.lan.JmdnsLifecycleCoordinatorTest \
  --tests dev.p2pkit.transport.lan.HostSelectorTest \
  --tests dev.p2pkit.transport.lan.JvmLanCandidateFallbackTest \
  :p2p-transport-lan:iosSimulatorArm64Test \
  --tests dev.p2pkit.transport.lan.IosLanRecoveryTest \
  :p2p-transport-lan:compileAndroidMain --stacktrace
```

Result: `BUILD SUCCESSFUL` in 15 seconds.

Production JVM, Android, and Apple compilation has passed during the batch. Existing core test opt-in warnings and the registered JmDNS `getInterface()` deprecation remain baseline items under BUILD-14. The new Android warning was removed.

### 7.4 Work required before committing this batch

1. Run `git diff --check`.
2. Review the complete diff and equivalent JVM/Android/Apple implementations.
3. Update stale selector KDoc that still describes a single selected host rather than an ordered bounded candidate list.
4. Decide whether to keep the historical `JvmLanDiscoveryHeartbeatTest.kt` filename/class after its behavior changed to native ownership/goodbye. Renaming is optional; do not spend risk merely for aesthetics.
5. Run the complete affected checkpoint, not only focused tests:
   - `./gradlew :p2p-core:jvmTest`
   - `./gradlew :p2p-core:iosSimulatorArm64Test`
   - `./gradlew :p2p-transport-lan:jvmTest`
   - `./gradlew :p2p-transport-lan:iosSimulatorArm64Test`
   - `./gradlew :p2p-transport-lan:compileAndroidMain :p2p-transport-lan:compileKotlinIosArm64 :p2p-transport-lan:compileKotlinIosX64 :p2p-transport-lan:compileKotlinIosSimulatorArm64`
6. Ensure the rewritten long-lived native ownership/goodbye test in `JvmLanDiscoveryHeartbeatTest.kt` runs; the complete JVM suite should include it.
7. Repeat the high-risk coordinator/rotation/candidate focused tests from the unchanged worktree.
8. Update tracker rows and execution log with exact commands/results. Recommended status:
   - `LAN-13`: Implemented locally; Android/JVM/Apple device/network rotation evidence still prevents full verification.
   - `LAN-14`: Implemented locally; real native TTL/abrupt-departure evidence remains external.
   - `LAN-16`: local schema, service ownership, subnet affinity, and alternate candidates implemented; authenticated identity is already SEC-01; hostile-network hardware proof remains.
   - `LAN-17`: Implemented; real AWDL interoperability remains device-blocked.
   - `LAN-18`: local candidate preservation/fallback implemented; real Android selected-network/device proof remains.
   - `LAN-T07/LAN-T08`: record exact completed local conjuncts and retain physical/hostile-network portions as blocked.
9. Commit only the listed batch files plus the tracker update. Suggested message:

   `fix(lan): make native liveness and routes authoritative (LAN-13/14/16/17/18)`

10. Review `git show --check --stat --oneline HEAD` and rerun the focused committed-state command.
11. Do not push until `SCM-PUSH-01` is approved.

## 8. Known owner-decision blockers

These blockers do not prevent independent batches. Do not implement their dependent contracts by assumption.

| Decision ID | Findings/gaps | Recommended decision and exact reply |
| --- | --- | --- |
| `SCM-PUSH-01` | All unpushed local commits | Authorize canonical remote: `Approve SCM-PUSH-01 canonical https://github.com/p2pKit/P2pKit.git` |
| `DATA-TRANSPORT-LIFECYCLE-API-01` | Remaining `CORE-11/CORE-T09` data-start rollback | Add restartable `suspend stop()` to `DataTransport`, reserve `close()` for terminal disposal: `Approve DATA-TRANSPORT-LIFECYCLE-API-01 restartable stop` |
| `PROVISIONING-CLOSE-API-01` | `CORE-24`, final provisioning disposal | Required idempotent suspending manager `close()`: `Approve PROVISIONING-CLOSE-API-01 required close` |
| `PEER-STATE-API-01` | `CORE-15` | Add advertising/discovery feature state flows and reserve global state for core: `Approve PEER-STATE-API-01 feature states` |
| `IMMUTABLE-MODEL-API-01` | Remaining `CORE-17` | Snapshot-backed public values with ABI consumer tests: `Approve IMMUTABLE-MODEL-API-01 snapshot values` |
| `TRANSPORT-FACTORY-API-01` | `CORE-27`, duplicate-kind part of `CORE-28` | Declared pre-build capabilities and nullable data transport: `Approve TRANSPORT-FACTORY-API-01 declared capabilities` |
| `PARSE-META-01` | `PROTO-08` | Versioned authenticated secure-v2 message envelope: `Approve PARSE-META-01 envelope` |
| `XFER-OFFER-API-01` | `FILE-05`, receiver side of `FILE-06`, `PT-T12/T13` | Add authoritative `StateFlow<List<P2pFileOffer>> pendingFileOffers` and deprecate lossy event flow: `Approve XFER-OFFER-API-01 pendingFileOffers` |
| `XFER-ERROR-API-01` | `FILE-11` | Add typed transfer-I/O and transfer-protocol errors with causes: `Approve XFER-ERROR-API-01 typed errors` |
| `XFER-PROTO-01` | `FILE-04/13`, `PT-T16/T18` | Receiver durability acknowledgement plus optional digest is a secure-v2 wire decision; prepare the full decision package before implementation |
| `REL-REMOTE-01` | `BUILD-02`, `ENV-07` | Recommended first-party Portal API Maven bundle with `USER_MANAGED`; reply format is in the tracker |

External resource blockers:

- `ENV-01`: physical Android and Apple device tests.
- `ENV-02`: two-machine and controlled hostile-network validation.
- `ENV-04`: iOS X64 execution needs a compatible x86_64 Apple host/runtime.
- `ENV-07`: real Central upload needs namespace access, signing identity, Portal credentials, and explicit release authorization.
- SEC-01 needs professional cryptographic audit and physical interoperability before production-security claims.

## 9. Dependency-ordered work after the active LAN batch

Follow the authoritative table in the tracker, but the practical next sequence is:

1. Finish, document, checkpoint, and commit the current LAN liveness/routing batch.
2. Implement decision-independent Android path/permission work: `CORE-22/25/26` and `CORE-T12`.
3. Implement independent Android provisioning internals (`PROV-A01/02/03/04/05/06/07/08/09/10/11`) while keeping the final disposal contract blocked on `PROVISIONING-CLOSE-API-01`. Real callback/device proof remains external.
4. Complete desktop provisioning `PROV-D01..05` and `PS-T03`.
5. Implement high sample safety work first: explicit file consent/quota/free-space, iOS sink error propagation and atomic exclusive naming, Android byte-bounded histories, partial-file cleanup, and structured transfer ownership.
6. Complete the remaining sample lifecycle, CLI parsing/targeting, IPv6, permissions/lint, cleanup, and UI-history work.
7. Resolve local reproducibility/provenance and repository-gate work: `BUILD-03/07/08/09/10/11/12/14/15`, then wrapper/publication/supply-chain `BUILD-04/05/06/13` where no external service is required.
8. Apply owner-approved API/protocol decisions in dependency order. Do not pre-empt them.
9. Run the final repository audit, repeated full build/test/lint/publication/XCFramework/sample/security gates, and external validations. Only then close FINAL-01.

## 10. Baseline failures and warnings that must stay visible

The original baseline included:

- Android sample lint: one `CoarseFineLocation` error and three warnings.
- Forced core JVM transfer test: sender could report `Completed` where exact `Cancelled` was required. Most ownership races were fixed in XFER-01, but receiver durability acknowledgement remains `FILE-04`.
- Core iOS reconnect rotation timeout.
- Two Apple LAN lifecycle timeouts and one ignored manual diagnostic. The two lifecycle defects were repaired in LAN-APPLE-03 and complete Apple suites later passed with only the manual diagnostic ignored.
- Experimental-coroutines test opt-in warnings, JmDNS multicast deprecation, and Android nullable text warnings under BUILD-14.

Do not call a changed batch green if it introduces another failure or warning. Do not make an independent valid batch wait on a precisely unchanged baseline owned elsewhere.

## 11. Verification and tooling notes

- Prefer `rg`/`rg --files` for source searches.
- Use `apply_patch` for source/document edits.
- Gradle commands may require the approved escalated `./gradlew` execution prefix in the environment.
- Reuse Gradle build caches and valid prior results. Do not rerun the full repository gate after each small edit.
- At batch completion, run the complete affected modules and every affected target, then repeat the highest-risk focused tests from committed state.
- Android physical instrumentation, real AWDL, hostile-network, and remote release evidence cannot be replaced with JVM fakes.
- When staging, use explicit paths. Never use a broad command that could include protected untracked files.
- Before committing, run `git status --short`, `git diff --check`, review `git diff --stat`, review the complete diff, then stage only the focused paths.

## 12. First actions for the next agent/chat

1. Read this handoff and `P2PKIT_REMEDIATION_TRACKER_2026-07.md`; do not read or modify the protected review/deferred files.
2. Confirm:

   ```text
   git branch --show-current
   git rev-parse HEAD
   git status --short
   ```

   Expected branch is `remediation/full-register-2026-07`, committed HEAD is `c09c8c7`, and the active LAN files listed in section 4 are modified/new.
3. Inspect the active LAN diff without discarding or overwriting it.
4. Complete section 7.4 in order.
5. Update the master tracker concisely with exact test counts/results and the active batch commit.
6. Commit the LAN batch locally, perform committed-state verification, and record the push blocker.
7. Continue directly to the next dependency-ready unblocked batch. Collect unresolved decisions rather than interrupting while independent work remains.

## 13. Completion definition

A finding is not complete merely because code exists or one test passed. Under the current tracker convention:

- `Implemented`: the root fix and required local tests exist, but an acceptance gate, external evidence, push, or final dependent work remains.
- `Verified`: the complete acceptance criteria passed from the focused committed state, the diff was reviewed, required target checks passed, and the authorized commit was pushed.
- `Blocked`: a concrete owner decision, credential, service, physical device, or external validation is required, and all independent local work has been preserved/documented.

The repository remains an experimental remediation branch, not a production-certified release. Security, transfer durability, real-platform behavior, publication, and final release claims remain bounded by the still-open rows and external-validation register.
