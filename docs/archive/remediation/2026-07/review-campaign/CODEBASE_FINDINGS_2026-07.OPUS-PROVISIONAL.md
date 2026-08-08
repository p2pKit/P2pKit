# CODEBASE_FINDINGS_2026-07 — consolidated review register

Consolidation of all **18** review reports in `.review-2026-07/reports/`
(A01–A16, plus the two A14 cross-cutting dimensions). Branch
`audit/exhaustive-review-2026-06`, HEAD `870bf10`. Wording is neutral
defensive-QA throughout (BRIEF rule 7): robustness gaps are described as
input-validation, resource-limit / bounded-usage enforcement,
connection-admission control, and crash-prevention concerns.

## Totals (after cross-report dedupe)

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 16 |
| Medium | 47 |
| Low | 89 |
| Improvement | 97 |
| **Total canonical rows** | **250** |

Raw finding-IDs across the 18 reports: **263**. Cross-report dedupe collapsed
**13 duplicate IDs into 10 canonical rows** (see *Duplicates collapsed*), giving
250 canonical rows. For navigability, 3 of the 13 folded IDs (PRM-12, SEC-I1,
SEC-I2) are also left in their tiers as one-line **pointer rows** to their
canonical destination; these are marked "(folded into …)" and are excluded from
the counts above (so the Low/Improvement tables physically contain 90/99 rows =
89/97 canonical + 1/2 pointer rows).

### Verification of Critical + High (17 findings)

Every Critical and High finding's cited `file:line` was opened in the current
tree and the described condition checked directly.

| Verdict | Count |
|---|---|
| Confirmed | 17 |
| Refuted | 0 |
| Needs-runtime | 0 |

All 17 code/build/doc conditions hold as described. Several carry a residual
*runtime-severity* uncertainty (e.g. the exact host-crash escalation) noted per
ID in *Verification notes*; in every case the underlying defect condition is
present in source, so the status is Confirmed rather than Needs-runtime.

Owning-section legend: S1 public API · S2 kit wiring/platform · S3 session ·
S4 identity/registry · S5 discovery · S6 wire protocol · S7 data transports/raw
connections · S8 file transfer · S9 permissions · S10 provisioning · S11 samples
· S12 iOS/Xcode build · S13 build/Gradle/publishing · S14 docs · S15 test
fixtures. Cross-cutting reviewers (robustness/resilience/perf) attach to the
owning section.

---

## Critical

| ID | Section | File(s):line | Title (short) | Category | Status |
|---|---|---|---|---|---|
| RBS-1 | S5 | IosLanDiscoveryTransport.kt:634,:675; JvmLanDiscoveryTransport.kt:171,:134; AndroidLanDiscoveryTransport.kt:567,:524 | Discovered peer-id from mDNS TXT reaches `PeerId()` unguarded; blank/whitespace value throws in the discovery callback (iOS: process termination; JVM/Android: untyped discovery-thread failure) on malformed discovery input | bug | Confirmed |

---

## High

| ID | Section | File(s):line | Title (short) | Category | Status |
|---|---|---|---|---|---|
| ARCH-1 | S2 | P2pKitImpl.kt:266-281, :301 | `ensureStarted` bind loop swallows `CancellationException` and latches `P2pState.Failed` on caller cancellation | bug | Confirmed |
| ARCH-2 | S2 | P2pKitImpl.kt:435-472 (:463 boundary), :469-471; AndroidNetworkPathObserver.kt:69-118; IosNetworkPathObserver.kt:71-109 | `stop()` observer-close tail runs outside `NonCancellable` and unbounded → hang on a contended observer mutex / observer leak on caller cancellation | bug | Confirmed |
| API-1 | S1 | P2pMessage.kt:15-24; Chunker.kt:29-31; Reassembler.kt:182-184 | `P2pMessage.metadata` accepted by the API but never serialized on the wire; receiver always reconstructs empty (silent data loss) | bug | Confirmed |
| API-2 (+SES-2) | S1/S3 | P2pSession.kt:45-54; P2pSessionImpl.kt:235-242; JvmRawConnection.kt:116-137; IosRawConnection.kt:190-353 | `send()` leaks raw, per-platform-divergent transport exceptions instead of the documented typed `P2pError.ConnectionFailed` | bug | Confirmed |
| SES-1 (+CON-7) | S3 | P2pSessionImpl.kt:222-233, :548-561, :603-614, :638-696; SessionManager.kt:300-313 | Terminal-outcome race on remote connection loss: `observeRawState`→`onConnectionLost` vs channel-end→`markCleanlyClosed` race the connection lock — reconnect nondeterministically skipped; clean close nondeterministically retried | bug | Confirmed |
| DSC-1 | S5 | JvmLanDiscoveryTransport.kt:123-188; AndroidLanDiscoveryTransport.kt:514-584; PeerRegistry.kt:95-106 | JVM/Android discovered peers evicted from `kit.peers` at 15 s with no re-announce heartbeat (only iOS has one) → steady-state peer loss | bug | Confirmed |
| CON-1 | S7 | JvmRawConnection.kt:178-189, :149-176; AndroidRawConnection.kt:177-188, :149-175 | JVM/Android `close()` and read-loop skip fd release when the calling coroutine is cancelled (`withContext` throws before the release runs) | bug | Confirmed |
| CON-3 | S7 | JvmLanDataTransport.kt:140-147; AndroidLanDataTransport.kt:130-137; P2pKitImpl.kt:78-79 | Accept-loop failure fails the callbackFlow → uncaught in the CEH-less kit scope (Android host-app crash; JVM permanent inbound deafness) | bug | Confirmed |
| FIL-1 | S8 | FileTransferDispatcher.kt:141-144; P2pSessionImpl.kt:291-301 | `sendFile` source-close watcher is a child of `sessionJob`; `close()`/`kit.stop()` cancels it before it closes the source → RawSource/fd leak, violating the "kit owns the source" contract | bug | Confirmed |
| FIL-2 | S8 | FileTransferDispatcher.kt:582-587 | Sender-side source read failure on a healthy connection sends no FILE_CANCEL → accepted incoming transfer never terminalizes (receiver hangs) | bug | Confirmed |
| SEC-1 | S3 | SessionManager.kt:146-152, :198-215, :290-313 | No admission control on inbound connection setup: non-blocking fan-out → unbounded concurrent pre-handshake handshakes and unbounded total sessions (bounded memory/fd/coroutine usage not enforced) | bug | Confirmed |
| TST-1 (+SES-10) | S15 | FakeRawConnection.kt:37-63 | `FakeRawConnection` models remote-initiated termination unlike any shipped transport → the real clean-close-vs-reconnect behavior (SES-1) is structurally untestable in commonTest | bug | Confirmed |
| TST-9 (+SES-8) | S15/S3 | SessionManager.kt:109; P2pKitImpl.kt:153-184; SessionStore.kt:47 | `strictInvariants` (#19 safety net) is inert in every kit-level suite — only `SessionStoreInvariantTest` constructs a strict store; behavioral flows run warn-mode with a NoOp logger | bug | Confirmed |
| BLD-2 | S13 | p2p-core/build.gradle.kts:118-143; p2p-transport-lan/build.gradle.kts:139-164; p2p-network-provisioning-android/build.gradle.kts:34-62 | Maven-Central javadoc-jar wired on only 1 of 4 publishable modules; the release doc claims the KMP modules "get theirs automatically" — the RC sign-off item can't pass as written | bug | Confirmed |
| IOSB-3 | S12 | scripts/run-ios-app.sh:47-50 | `run-ios-app.sh` installs the first `p2pkit-sample.app` found anywhere in global DerivedData (`-print -quit`) — can silently run a stale bundle, defeating the provenance gate | bug | Confirmed |
| DOCB-1 | S14 | AUDIT_REPORT_2026-06.md:60-86 | The "Deferred (39)" list is heavily stale (≥10 of 16 bullets since implemented on this branch) while CLAUDE.md routes every agent to it — risk of re-fixing/reverting shipped work | bug | Confirmed |

---

## Medium

| ID | Section | File(s):line | Title (short) | Category | Status |
|---|---|---|---|---|---|
| ARCH-3 | S2 | P2pKitImpl.kt:313-316, :341-348, :365-375 | Terminal `Stopped` state can be overwritten: post-`stop()` observer-start resume latches `Running`; advertise/discovery catch-blocks write `Failed` unguarded | bug | Confirmed |
| ARCH-4 | S2 | P2pKitImpl.kt:78-79; PeerRegistry.kt:72-78 | Kit scope has no `CoroutineExceptionHandler`; an uncaught throw in any internal/SPI collector reaches the platform handler (Android host-app crash) | bug | Confirmed |
| API-3 | S1 | P2pSession.kt:29-33; P2pSessionImpl.kt:131-136 | `incoming` KDoc claims the flow "completes" after close; a `SharedFlow` never completes → app code awaiting completion hangs/leaks | bug | Reported |
| SES-3 | S3 | SessionManager.kt:300-313; P2pSessionImpl.kt:420-435 | Reader coroutine (on the kit scope) parks forever in `eventChannel.send` when a session terminates with a full 256-slot channel → coroutine + buffered-payload leak | bug | Confirmed |
| SES-4 | S3 | SessionStore.kt:129-172; SessionManager.kt:715-722 | Arbitration rejects a live redial while a stale-but-undetected-dead session holds the peer slot → reconnect lockout up to the keep-alive timeout | bug | Reported |
| DSC-2 | S5 | AndroidLanDiscoveryTransport.kt (44 `Log.*` sites) | Android discovery transport logs unconditionally, violating the documented default-off trace contract (JVM/iOS are gated); logcat metadata exposure | bug | Reported |
| DSC-3 | S5 | AndroidLanDiscoveryTransport.kt:886-923, :426-428; JvmLanDiscoveryTransport.kt:290-293 | Cancellation during `JmDNS.create` leaks a running JmDNS instance (multicast socket + threads) that nothing can close | bug | Reported |
| DSC-4 | S5 | AndroidLanDiscoveryTransport.kt:931-955 | Android rebind: failure to re-register/re-listen on the fresh handle is dropped with no retry → discovery/advertising stays dead until the next network change | bug | Reported |
| DSC-5 | S5 | AndroidLanDiscoveryTransport.kt:229-230, :270-271, :835-844 | `start*` writes `boundNetwork`/`boundDefaultNetwork` without a bind, letting a pending rebind be wrongly skipped as "no change" | bug | Reported |
| DSC-6 | S5 | IosLanDiscoveryTransport.kt:353-367, :395-398 | iOS `onAfterListenerRebind` recreates the browser from a stale flag without re-checking `discoveryStartedByHost` → resurrects browsing against a concurrent `stopDiscovery` | bug | Reported |
| DSC-7 | S5 | JvmLanDiscoveryTransport.kt:240-243; AndroidLanDiscoveryTransport.kt:369-372 | `refresh()` cancellation on the remove-old-listener hop leaks the old listener permanently (duplicate event stream), accumulating across reconnect cycles | bug | Reported |
| CON-2 | S7 | JvmLanDataTransport.kt:99-121; AndroidLanDataTransport.kt:93-115; IosLanDataTransport.kt:482-490 | Cancelled dial leaks the freshly-connected socket (`withContext` discards its result on caller cancellation) | bug | Reported |
| CON-4 | S7 | IosLanDataTransport.kt:304-333, :501-511; JvmLanDataTransport.kt:60-81; P2pKitImpl.kt:284-296 | `stop()` racing a slow `start()` orphans bound resources; both safety nets defeated (`start()` lacks the post-bind `closed` re-check; `close()` early-returns on the flag) | bug | Reported |
| CON-5 | S7 | IosRawConnection.kt:264-280, :194-204; IosLanDataTransport.kt:486-490 | iOS `catch (TimeoutCancellationException)` intercepts an app-level outer timeout, tearing down a healthy connection and swallowing/retyping the cancellation | bug | Reported |
| CON-6 | S7 | JvmRawConnection.kt:116-128; AndroidRawConnection.kt:116-128; IosRawConnection.kt:240-254 | Write-error parity divergence: JVM/Android leave socket open & state Connected on a non-timeout write failure (detection deferred a ping interval); exception types diverge across platforms | bug | Reported |
| CON-8 | S7 | IosLanDataTransport.kt:394-411 | iOS listener failure after ready is silent: no rebind, no error to core, listener not cancelled → inbound-deaf transport still reports started | bug | Reported |
| PRO-1 | S6 | HelloPayload.kt:36-57; Builders.kt:41,127 | HELLO wire caps enforced only on decode; an over-limit local `deviceName`/`appId` fails every handshake with a generic timeout (no local fail-fast) | bug | Reported |
| FIL-3 | S8 | FileTransferDispatcher.kt:318-343, :91-95, :208-209 | No post-accept inactivity timeout; stalled accepted transfers permanently consume the pending-offer budget (bounded-usage / admission gap) | bug | Reported |
| FIL-4 | S8 | FileTransferDispatcher.kt:381-405, :552-588 | Duplicate FILE_ACCEPT launches a second concurrent streamer over the same source (state regression, interleaved chunks, orphaned job, over-count) | bug | Reported |
| FIL-5 | S8 | FileTransferDispatcher.kt:421-459, :255-265, :541-547; StreamingFileReceiver.kt:30-33 | Receiver sink data race: `acceptDataChunk` (outside lock) vs `abort()` on cancel/teardown → concurrent write+flush on one buffered `Sink` (contained corruption) | bug | Reported |
| FIL-6 | S8 | FileTransferDispatcher.kt:109-134 | `sendFile` lacks the closed re-check under lock that the #16 fix added to `onFileOffer` (TOCTOU); worst case a handle that never terminalizes + source leak | bug | Reported |
| FIL-8 | S8 | P2pFileOffer.kt:24-25; P2pFileTransfer.kt:28-29; FileOfferPayload.kt:37-52 | Remote-controlled `offer.name` documented only as "Suggested file name" — no sanitization warning; consuming apps that use it as a filesystem path inherit a path-traversal write primitive | bug | Reported |
| FIL-11 | S15/S8 | FileTransferFlowTest.kt:231-233, :519-523 | `assertSubscriberSeesNoOffer` is a no-op probe: the oversize-auto-reject test asserts nothing about its headline "not surfaced to the app" invariant | bug | Confirmed |
| PRM-1 | S9/S10 | P2pKitImpl.kt:321,358,497-500; PermissionManagerFactory.android.kt:82-88; AndroidP2pPermissionManager.kt:37-47 | Kit-wide permission gate re-creates LAN over-gating for apps that wire the sidecar's manager as the docs recommend (provisioning-only perms block plain advertise/discovery) | bug | Reported |
| PRM-4 | S10 | WifiManagerWrapperImpl.kt:78-90, :141-199, :195-198 | Cancellation racing the OS callback (`if (cont.isActive) resume` pattern) can leak the hotspot reservation and, on join, leave the whole process bound to a dead network | bug | Reported |
| PRM-5 | S10 | AndroidNetworkProvisioningManager.kt:366-391; NetworkProvisioningError.kt:25-26 | `SecurityException` mapping produces actionably-wrong error types (location toggle ≠ missing permission; join blamed on wrong perm; original cause dropped) | bug | Reported |
| PRM-6 | S10 | JvmNetworkProvisioningManager.kt:137-159 | JVM manager lacks the per-NIC `SocketException` guard the Android twin has; `getManualConnectionInfo()` can throw a raw `SocketException` out of the public API | bug | Reported |
| IOSB-1 | S12 | scripts/run-ios-app.sh:58-67 | UDID-resolution failure path is dead code under `set -e` (grep exit 1 aborts before the FATAL-hint guard runs) | bug | Confirmed |
| IOSB-2 | S12 | scripts/run-ios-app.sh:59 | `SIM_NAME` interpolated into an ERE unescaped — every parenthesized stock device name fails UDID resolution | bug | Confirmed |
| BLD-1 | S13 | p2p-core/build.gradle.kts:15-19, :42, :62-63, :71-75 | BuildInfo `BUILD_TIME` defeats its own "only write when changed" guard: every build rewrites the file → incremental/cache miss + non-reproducible artifacts | bug | Reported |
| TST-3 | S15 | FakeDataTransport.kt:26, :55-64; SessionManager.kt:146-152 | `FakeDataTransport` incoming flow can never terminate with a cause → accept-loop-death handling (CON-3) is untestable and untested against the shipped failure shape | bug | Reported |
| TST-10 | S15/S3 | ReconnectPolicyTest.kt:247, :283; NetworkPathRecoveryTest.kt:227 | Negative assertions bounded by 150 ms windows shorter than the 1 s retry delay they negate — can't catch a 1 s-late retry | bug | Reported |
| TST-11 | S15/S3 | SessionFlowTest.kt:222-231 | The only remote-CLOSE-frame test accepts `Closed || Failed`, leaving the spec's clean-close distinction unpinned (masks either SES-1 resolution) | bug | Reported |
| SEC-2 (+PERF-8,RBS-3) | S4 | PeerRegistry.kt:79-93, :95-106; IosLanDiscoveryTransport.kt:176,:635 | `PeerRegistry.tracked` (and the iOS `announceCache`/endpoint maps) are uncapped; O(n) republish per event → growth/CPU under a high volume of mDNS events; idle 1 Hz eviction tick allocates unconditionally | bug | Confirmed |
| DOCA-2 | S14 | README.md:44,219,229-233,249 | README describes shipped network provisioning in the future tense (self-contradictory with the shipped sidecar modules) | bug | Reported |
| DOCA-3 (+PRM-12,DOCA-10) | S14 | README.md:52,63,329-330; CLAUDE.md; P2pKit-Spec.md:99,1316; INTERNAL_TESTING.md:194; WORKSPACE_SYNC_DASHBOARD.md:202 | Docs assert iOS `networkProvisioning` is/"will remain" permanently `Unsupported`, contradicting the shipped `iosManualIp()` manual-IP manager (only hotspot/join are Unsupported) | bug | Reported |
| DOCA-8 (+PRO-3) | S14/S6 | P2pKit-Spec.md:838; ProtocolConstants.kt:51-60 | Spec §13.4 receive-path caps omit the new 16 MiB `MAX_TOTAL_PENDING_BYTES` session-closing cap — a spec-conforming interop sender can be closed below what §13.4 promises is tolerated | bug | Confirmed |
| DOCA-13 | S14 | INTERNAL_TESTING.md:50,202,347,366-371,438,444 | Test counts stale and iOS "all 20 green" expectation contradicts the two documented known-flaky churn failures → pressures a runner into masking or blocking a healthy build | bug | Reported |
| DOCA-14 | S14 | docs/STABILIZATION_AND_RELEASE.md:204-218, :5 | RC gate sign-off checklist omits campaign-known open RC decisions (metadata wire-drop; smoke-binary freshness); header date stale | bug | Reported |
| DOCA-16 (+SES-9) | S14/S3 | P2pKit-Spec.md:669; States.kt:31-46; P2pSessionImpl.kt:319,:662 | Spec §10 documents `Connected → Closing → Closed`, but `ConnectionState.Closing` is never assigned; spec-following code that awaits `Closing` hangs; dead guards in code | bug | Reported |
| DOCA-21 | S14 | docs/ios-sample-app/project.yml:1-10,:28-29; ContentView.swift:1-4; P2pKitSampleApp.swift:1-2; Info.plist | Deprecated iOS template: 4 of 6 files carry no deprecation marker, and project.yml's own usage steps regenerate-wipe the load-bearing local-network Info.plist keys | bug | Reported |
| DOCB-2 | S14 | AUDIT_REPORT_2026-06.md:25 | AUDIT_REPORT C1 fix description now states the opposite of shipped behavior (manual peers "adopt the remote's HELLO identity" — reversed by `012e49e`) | bug | Confirmed |
| DOCB-4 | S14 | PROBLEMS_P2PKIT.md:105,156-161,317-323,324-330,391-397,882 | PROBLEMS_P2PKIT.md presents since-fixed HIGH findings as open; its line-882 "everything untagged is still open" rule no longer holds | bug | Reported |
| DOCB-5 | S14 | PROBLEMS_P2PKIT.md:212-217,163-168,205-210,191-196 | PROBLEMS_P2PKIT.md carries fix texts that, applied today, re-introduce known criticals (C1 manual-peer, C7 file-transfer-after-reconnect, spec-breaking lifecycle) | bug | Reported |
| DOCB-6 | S14 | docs/hardware-validation-checklist.md:269 | Test 5 points the operator at a non-existent iOS incoming directory (`p2pkit-incoming` is the Android path; iOS uses `Documents/P2pKitInbox/`) → the leak-detection step inspects an empty folder | bug | Reported |
| DOCB-8 | S14 | docs/v0.4-cumulative-validation-runbook.md:359,367-370,470,692,794 | Reconnect-handler log signatures the runbook greps for no longer exist in code; two aggregate PASS criteria can never be satisfied → false FAIL on a correct device run | bug | Reported |
| SMP-1 | S11 | p2p-sample-desktop-ui/.../Main.kt:672-683, :810-813 | desktop-ui incoming file destination is not uniquified (CLI/Android fix not mirrored): same-named offers overwrite / concurrent same-named offers interleave-corrupt | bug | Reported |

---

## Low

| ID | Section | File(s):line | Title (short) | Category | Status |
|---|---|---|---|---|---|
| ARCH-5 | S2 | P2pKitImpl.kt:265-282 vs :284-296 | Bind-loop failure path skips the close-if-stopped cleanup, leaking a re-bound transport on a stopped kit (multi-transport only) | bug | Reported |
| ARCH-6 | S2 | AndroidNetworkPathObserver.kt:113-118; IosNetworkPathObserver.kt:105-109; NetworkPath.kt:79 | Bundled path observers never reset `status` to `Unknown` on `close()`, breaking the documented cold-read contract for reused/shared observers | bug | Reported |
| ARCH-7 | S2 | NativeBuildLog.kt:7-13 vs NativeBuildLog.jvm.kt:23-25 | `nativeBuildInfoLog` common contract promises the identity line "ALWAYS appears" but the JVM actual is deliberately empty (doc mismatch) | bug | Reported |
| ARCH-8 | S2/S14 | P2pKit-Spec.md:506-516 vs TransportManager.kt:26-30 | Spec §8.3 embeds a stale `TransportManager` snippet (`maxByOrNull`) that differs from the shipped deterministic tie-break | bug | Reported |
| ARCH-9 | S2 | KitLifecycleTest.kt:47-51,70-76,82-87,111-115 | Kit-level common tests persist real peer-id state on the host machine (no `peerIdStorage` override) | bug | Reported |
| ARCH-10 | S2 | P2pKitImpl.kt:543; P2pKit.kt:190; Builders.kt:131 | [CATALOGUED B:201] Blocking disk I/O at kit construction (`loadOrGenerate()` on the caller's thread) — ANR risk on the Android main thread | bug | Reported |
| API-4 | S1/S14 | P2pKit-Spec.md:290-293; P2pSession.kt:75-77 | Spec §7.3 still says "the caller closes source" — contradicts the shipped kit-takes-ownership `sendFile` contract | bug | Reported |
| API-5 | S1 | P2pKit.kt:157-169; P2pKitImpl.kt:384-385,250-296 | `connect()` KDoc omits `TransportStartFailed` and post-stop `IllegalStateException` that lazy-start delivers | bug | Reported |
| API-6 | S1 | P2pKit.kt:180-181; States.kt:15-17; P2pKitImpl.kt:351-355,378-382,428 | `stop()` has no interface KDoc; `stopAdvertising`/`stopDiscovery` silently succeed after `stop()` despite the "any call after stop() throws ISE" claim | bug | Reported |
| API-7 | S1 | Builders.kt:110-114, :218-222 | Re-entering `networkProvisioning { }` silently drops a previously registered factory (sub-builder not seeded) | bug | Reported |
| API-8 | S1 | UnsupportedNetworkProvisioningManager.kt:44-46 | Unsupported provisioning stub still reports "planned for v0.2 and not implemented in v0.1" in v0.6 (misleading diagnostics) | bug | Reported |
| API-9 | S1 | States.kt:10-13; P2pKitImpl.kt:338,344-347,364,371-374 | `P2pState.Failed` KDoc incomplete for post-start advertise/discovery failures and the direct `Failed→Running` recovery | bug | Reported |
| API-10 | S1 | States.kt:31-35; P2pSessionImpl.kt:128; SessionManager.kt:223-277 | `Connecting`/`Handshaking`/`Idle` are never observable on `P2pSession.state`, but only `Closing` is documented as never-emitted | bug | Reported |
| API-13 | S1 | NoOpP2pPermissionManager.kt:8-10; Builders.kt:73-81 | KDoc says to plug a custom manager "once that knob exists" — the `permissionManager` knob already exists | bug | Reported |
| API-14 | S1/S14 | P2pKit-Spec.md:562-566; Internal.kt:17-40 | Spec §9.3 `InternalPeer` shape stale: missing `origin: PeerOrigin` added in `012e49e` | bug | Reported |
| API-16 | S1 | Config.kt:15-18,54-57; FileTransferConfig.kt:28-34; FileTransferDispatcher.kt:105; Errors.kt:10-13 | Config types and `sendFile` throw undocumented `IllegalArgumentException`; the `timeout > interval` constraint is itself undocumented | bug | Reported |
| API-17 | S1 | Identity.kt:12-31 | Blank-value `require` on `PeerId`/`AppId` is a throw hazard for network-supplied strings the KDoc doesn't flag (call sites are RBS-1) | bug | Confirmed |
| API-18 | S1 | ManualPeerRegistrar.kt:26-42; NetworkProvisioningTypes.kt:40-42; PeerRegistry.kt:115-116 | `registerManualPeer`/`createManualPeer` throw undocumented `IllegalArgumentException` on bad host/port (the user-typed-input flow) | bug | Reported |
| API-19 | S1 | FileTransferState.kt:34; P2pFileOffer.kt:12-14; FileTransferDispatcher.kt:590-635 | Offer-timeout terminal state is asymmetric/mislabeled: receiver `Rejected("timeout")` vs sender `Cancelled(...)`; KDoc claims timeouts land in `Cancelled` | bug | Reported |
| API-20 | S1 | P2pFileOffer.kt:33-43; FileTransferDispatcher.kt:214-225 | `P2pFileOffer.accept` KDoc documents only `IllegalStateException`; it also throws `P2pError.ConnectionFailed` | bug | Reported |
| SES-5 | S3 | SessionManager.kt:174-180 | `performConnect` wraps `CancellationException` into `P2pError.ConnectionFailed` (no CE-first arm; also drops the cause) | bug | Reported |
| SES-6 | S3 | SessionManager.kt:544-583; P2pSessionImpl.kt:317-353 | Cancellation window in the reconnect loop (post-handshake, pre-`rearmWith`) leaks the freshly-dialed connection + reader | bug | Reported |
| SES-7 | S3 | P2pSessionImpl.kt:125-126,384-390; SessionManager.kt:732-737 | `sessionJob` never completes for sessions ending via failure paths → unbounded Job accumulation under the kit scope | bug | Reported |
| SES-11 | S3 | Handshake.kt:47-54; JvmRawConnection.kt:206 | Handshake worst-case duration is bounded by the 30 s write watchdog, not the 10 s handshake timeout (≈40 s per attempt vs a wedged listener) | bug | Reported |
| IDN-1 | S4 | PeerRegistry.kt:79-88; Internal.kt:35-40 | Registry event path enforces no provenance invariants: Found/Updated can demote/overwrite a Manual entry, Lost can remove one, event `origin` trusted verbatim | bug | Reported |
| IDN-2 | S4 | PeerRegistry.kt:126-149 | `registerManualPeer` dedupe is check-then-act: concurrent same-endpoint registrations mint duplicate permanent (eviction-exempt) entries | bug | Reported |
| IDN-3 | S4 | PeerRegistry.kt:90-93 | `publishPeers` read-then-assign race can publish a stale peers list over a newer one (self-heals within one eviction poll) | bug | Reported |
| IDN-4 | S4 | FilePeerIdStorage.kt (jvm:68-77, android:30-42); NSUserDefaultsPeerIdStorage.kt:39-43; Identity.kt:27-31 | No storage backend validates loaded peer-id content beyond non-blank; a corrupt-but-nonblank value becomes the advertised identity; JVM KDoc overclaims "unparseable → overwritten" | bug | Reported |
| IDN-5 | S4/S14 | REMEDIATION_2026-07.md:63; CODEBASE_REVIEW_MAP_2026-07.md:132-134; PeerRegistry.kt:117-131 | "registerManualPeer has no host:port dedupe — deferred" is stale: dedupe has existed since `b9f6311`; the dedupe itself is untested | bug | Reported |
| IDN-6 | S4 | androidMain/FilePeerIdStorage.kt:9-13,:20; jvmMain/FilePeerIdStorage.kt:35 | Android storage header still claims "same-semantics copy … will converge" — following it would migrate every Android install's identity path (foot-gun) | bug | Reported |
| DSC-8 | S5 | IosLanDiscoveryTransport.kt:259-278, :650, :673-680 | iOS announce-loop prune races the browse callback: a peer re-confirmed between the reconcile CAS and `emitLostById` is wrongly emitted Lost | bug | Reported |
| DSC-9 | S5 | IosLanDiscoveryTransport.kt:537-539, :650, :478 | iOS browse callbacks stamp entries with the current volatile `browserGeneration`, not the delivering browser's generation (TOCTOU; self-heals one generation) | bug | Reported |
| DSC-10 | S5 | AndroidLanDiscoveryTransport.kt:791-798, :766-767 | `pendingRebindJob` mutated from ConnectivityManager callback threads with no synchronization (mixed-discipline data race) | bug | Reported |
| DSC-11 | S5 | JvmLanDiscoveryTransport.kt:129-135; AndroidLanDiscoveryTransport.kt:519-525; IosLanDiscoveryTransport.kt:656-664 | `serviceRemoved`/`emitLost` emit `PeerEvent.Lost` with no appId filter, so any same-type advertiser can remove arbitrary pids (incl. manual entries) from the registry | bug | Reported |
| DSC-12 | S5 | IosBonjour.kt:44-58,:84-90; Builders.kt:127 | TXT edge-case parity divergences: empty value decodes `"true"` (JmDNS) vs `""` (iOS); oversized values silently dropped; no deviceName length validation | bug | Reported |
| DSC-13 | S5 | AndroidLanDiscoveryTransport.kt:218-237,:590-598; JvmLanDiscoveryTransport.kt:63-97 | Failed `start*` leaves the multicast lock held and the JmDNS handle open with both intent flags false until `kit.stop()` | bug | Reported |
| CON-9 | S7 | IosLanDataTransport.kt:185; JvmLanDataTransport.kt:132,156-160; AndroidLanDataTransport.kt:122,143-147 | Inbound-queue parity: iOS `Channel.UNLIMITED` vs JVM/Android bounded(64)+drop-close → unbounded fd/memory on iOS under a stalled collector | bug | Reported |
| CON-10 | S7 | AndroidRawConnection.kt:67,100-183; AndroidLanDataTransport.kt:71-164 | Android connection-lifecycle trace is unconditional `Log.d` (peer IPs/ports), contradicting the documented default-off trace (JVM/iOS gated) — related to DSC-2 | bug | Reported |
| CON-11 | S7 | IosLanDataTransport.kt:281,:662-672,:606-607,:633-639 | iOS `pendingRebindJob` data race: `scheduleRebind` runs unsynchronized from three threads (double rebind / missed cancel) | bug | Reported |
| CON-12 | S7 | IosLanDataTransport.kt:501-511; JvmLanDataTransport.kt:173-180 | iOS `close()` leaves `listener` non-null and `_tcpPort` set (stale endpoint reported via `lanTcpPort` after stop); JVM/Android leave `_tcpPort` stale | bug | Reported |
| CON-13 | S7 | IosLanDataTransport.kt:382-387 | iOS inbound connection arriving after `closed` is ignored without cancelling it (brief leak until K/N GC) | bug | Reported |
| PRO-2 | S6 | P2pProtocol.kt:18-45; P2pSessionImpl.kt:527-529; P2pKit-Spec.md §13.5 | Spec §13.5 promises a DATA-with-NEEDS_ACK triggers an ACK, but no code can ever send an ACK (decode-only; latent interop) | bug | Reported |
| PRO-4 (+SEC-I2) | S6 | HelloPayload.kt:44-56 | `HelloPayload.decode` bounds neither `platform` nor individual `supportedTransports` strings (frame-cap-bounded; defensive-symmetry gap) | bug | Reported |
| PRO-5 | S6 | HelloPayload.kt:11-13; P2pKit-Spec.md:831,1013; Handshake.kt:69-75 | Version-check docs claim "major component" semantics; implementation is exact-match on a single Int | bug | Reported |
| PRO-6 | S6 | FrameCodec.kt:72,75-78,110; Frame.kt:27 | Frame-header `version` byte is never validated on receive, and unlike the reserved byte this stance is undocumented and untested (forward-compat) | bug | Reported |
| PRO-7 | S6 | DefaultP2pProtocol.kt:124-139; Reassembler.kt:87-96,163-170 | `evictStale()` runs before the batch that could refresh a partial; late chunks then resurrect an uncompletable "zombie" pending → silent message loss (narrow edge) | bug | Reported |
| FIL-7 | S8 | FileTransferDispatcher.kt:361-378 | Offer emit happens outside the closed re-check lock: a ghost offer can surface after `closeAll` (accept then throws ISE) | bug | Reported |
| FIL-9 | S8 | FileTransferAndroid.kt:23-27,31-35,71-74; FileTransferJvm.kt:20-25 | Platform wrapper defects: Android KDoc directs to a `sendFile(File)` overload that doesn't exist on Android; negative-SIZE and error-typing gaps in both wrappers | bug | Reported |
| FIL-10 | S8 | OutgoingFileTransferImpl.kt:19-48; IncomingFileSession.kt:23-24; StreamingFileReceiver.kt:10,88-89; FileTransferDispatcher.kt:226-228 | Stale/contradictory concurrency- and ownership-doc comments across the transfer internals (name the wrong load-bearing mechanism) | bug | Reported |
| PRM-7 | S10 | AndroidNetworkProvisioningManager.kt:355-364,249-271,155-159 | System-initiated teardown paths orphan their watcher coroutines and (hotspot) skip closing the fired handle (bounded leak, asymmetric cleanup) | bug | Reported |
| PRM-8 | S10 | AndroidNetworkProvisioningManager.kt:127-129,397-404; WifiManagerWrapperImpl.kt:202-205 | Hotspot-start timeout is reported as reason `STOPPED_BEFORE_START`, masking the hang it actually is (misleading diagnostics) | bug | Reported |
| PRM-9 | S10 | AndroidNetworkProvisioningManager.kt:152-165,314-332,117-121 | `startLocalNetwork` can return `Failed` while state says `LocalNetworkRunning` and the reservation keeps running (narrow no-creds/no-info trigger) | bug | Reported |
| PRM-10 | S10 | AndroidNetworkProvisioningManager.kt:64-65,88-100,155-159 | Provisioning entry points still "work" after `kit.stop()` but against a dead scope: a hotspot started post-stop has no system-stop watcher and is never auto-released | bug | Reported |
| PRM-11 | S10 | WifiManagerWrapperImpl.kt:32-39 vs :63-70 | KDoc still carries the "targetSdk 26..28: ACCESS_COARSE_LOCATION" row the audit fix deleted as never-implemented (doc mismatch) | bug | Reported |
| PRM-12 | — | (folded into DOCA-3) | iOS provisioning "permanently Unsupported" wording vs shipped `iosManualIp()` — see collapsed row DOCA-3 | bug | Confirmed |
| PRM-13 | S10 | IosManualNetworkProvisioningManager.kt:43-49,86-93 | iOS `getManualConnectionInfo` returns empty `hostAddresses` on a false premise ("no synchronous non-loopback enumeration" — `getifaddrs` is available) | bug | Reported |
| IOSB-4 | S12 | iosApp/scripts/check-xcframework.sh:83-89 | Unresolvable-stamp branch hard-fails with a suggested fix (re-run the assemble task) that is a no-op exactly when the stale stamp persists (UP-TO-DATE) | bug | Reported |
| IOSB-5 | S12 | iosApp/scripts/check-xcframework.sh:76-79 | Freshness pathspec omits build-config inputs that also shape the XCFramework (gradle.properties, root/settings build scripts, wrapper) | bug | Reported |
| IOSB-6 | S12 | iosApp/scripts/README.md:10-44 | README stale twice: obsolete manual Run-Script setup (double-wires the phase) and a pre-adca586 behavior description | bug | Reported |
| IOSB-9 | S12 | iosApp/Info.plist; iosApp/project.yml:22-24 | `iosApp/Info.plist` is generated xcodegen output tracked in git with no generated-file marker — direct edits are silently reverted on the next regen | bug | Reported |
| IOSB-11 | S11/S12 | iosApp/ContentView.swift:995-997,1006-1008; P2pSession.kt:75-77 | Sample closes the `sendFile` source on the terminal path, violating the "callers must not close it" contract; its comment documents the wrong ownership | bug | Reported |
| BLD-3 | S13 | .gitignore:25; docs/audit-evidence/*.log; docs/LAN_DIAGNOSTICS_PROTOCOL.md | `.gitignore` ignores `*.log` globally while the documented practice tracks evidence logs under `docs/audit-evidence/` (new captures silently dropped) | bug | Reported |
| TST-2 | S15 | FakeRawConnection.kt:37-40 | Fake write-failure exception type (`ClosedSendChannelException`) matches no platform pair; blinds the exact test the API-2 fix will need | bug | Reported |
| TST-4 | S15 | FakeDiscoveryTransport.kt:18-30 | `FakeDiscoveryTransport` buffer semantics diverge from all three production transports (SUSPEND(64) vs DROP_OLDEST(256)); KDoc overclaims parity | bug | Reported |
| DOCA-1 | S14 | CLAUDE.md (working tree vs HEAD) | CLAUDE.md is uncommitted while the committed (HEAD) version carries a now-false "publishing not yet wired" claim and lacks the RC pointers | bug | Reported |
| DOCA-4 | S14 | README.md:381 | README test counts stale (134/17/20 vs actual 161/18/29) | bug | Reported |
| DOCA-5 | S14 | README.md:55,391,403 | README claims the iOS sample provides a "Network entitlement"; none exists or is needed (only the two Info.plist keys) | bug | Reported |
| DOCA-6 | S14 | README.md:256 | README architecture diagram lists "ACK" as an implemented protocol feature; ACK is decode-only and never sent (relates to PRO-2) | bug | Reported |
| DOCA-7 | S14 | README.md:405 | README "Status" changelog ends at early v0.6; the entire 2026-06 audit/hardening line is absent | bug | Reported |
| DOCA-9 | S14 | P2pKit-Spec.md:532 vs :954-960 | Spec §9.1 PeerId persistence backends (DataStore/SharedPreferences) contradict §16.2 and the code (file-based on JVM/Android; NSUserDefaults on iOS) | bug | Reported |
| DOCA-11 | S14 | P2pKit-Spec.md:233-235 | Spec §7.2 documents `connect(peer)` as throwing `PermissionMissing`; `connect()` has no permission gate (§15.2 is the correct rule) | bug | Reported |
| DOCA-12 | S14 | P2pKit-Spec.md:670,935,718,608,835,5 | Spec prose nits: dangling "retention" reference, §16.1 mechanism fiction, manual-peer eviction exemption undocumented, MB/MiB, stale "Last updated" | bug | Reported |
| DOCA-15 | S14 | P2pKit-Spec.md:584-608 | Spec never states that `P2pMessage.metadata` is not transmitted (contract-doc side of API-1) | bug | Reported |
| DOCA-17 | S14 | docs/production-readiness.md:140-147,71-74 | production-readiness.md §8 still describes shipped PeerId persistence as a future "v0.4" item; §4 names a nonexistent `pathSatisfiedSignal` | bug | Reported |
| DOCA-18 | S14 | docs/LAN_DIAGNOSTICS_PROTOCOL.md:123,27-28 | Wrong expected subnet for LocalOnlyHotspot (192.168.49.x vs 43.x); unescaped pipes break the capture-command table | bug | Reported |
| DOCA-19 | S14 | REMEDIATION_2026-07.md:73 | Scope claim "confined to the 27 source/test/doc files listed above" — no list exists and the count is 33 | bug | Reported |
| DOCB-3 | S14 | AUDIT_REPORT_2026-06.md:3,102,96; PROBLEMS_P2PKIT.md:14,1170-1189 | AUDIT_REPORT header/footer stale ("two commits on top of main"; "one commit, 33 files" review instruction; a since-repaired PROBLEMS characterization) | bug | Reported |
| DOCB-7 | S14 | docs/hardware-validation-checklist.md:231,296-298,326-334,207,235 | Invariant/crash framing and stage plumbing stale (S1-era verdict flow; names a non-fireable invariant; post-#19 soft invariants not reflected) | bug | Reported |
| DOCB-9 | S14 | docs/v0.4-cumulative-validation-runbook.md:145-146,160,956 | STOP-condition mechanics stale post-`e91e094`: SessionStore invariant violations no longer raise ISE in the field; "revert f84a218" is dead advice | bug | Reported |
| DOCB-10 | S14 | docs/v0.4-cumulative-validation-runbook.md:278,103-104,293,367,672,692,719 | Minor signature/parameter drift: browser-cancel suffix, maxAttempts=5 examples vs sample preset 10/1500, JmDNS.create-failure now retried | bug | Reported |
| DOCB-11 | S14 | docs/audit-real-device-checklist.md:1,50-54,147 | Gates an obsolete tag (v0.3-internal) with no superseded banner; A.4's payload spec contradicts its own steps | bug | Reported |
| RBS-2 | S3/S6 | P2pSessionImpl.kt:536; DefaultP2pProtocol.kt:155,174; IosLanDiscoveryTransport.kt:600,653 | Remote-controlled strings reach SDK log lines unsanitized (core `logger.warn` + transport trace) — CR/LF/control-char injection into an app logger sink | bug | Reported |
| PERF-9 (+PRO-10,SEC-I1) | S6 | FrameReader.kt:37-79; JvmRawConnection.kt:154 | `FrameReader` buffering is quadratic against legal-but-non-conforming framing (large frame in tiny segments / many tiny frames) — peer-controlled CPU cost, memory stays bounded | bug | Reported |
| SMP-2 | S11 | p2p-sample-desktop/.../Main.kt:476 | CLI `close` command evicts sessions by key without the identity check its own replacement-safety rule requires (harness state desync) | bug | Reported |
| SMP-3 | S11 | p2p-sample-desktop/.../Main.kt:161-168,303-358,394,426-688 | CLI swallows `CancellationException` around suspend SDK calls (CE-safe helper applied to the other two samples, not the CLI) | bug | Reported |
| SMP-4 | S11 | p2p-sample-desktop/.../Main.kt:519-703; P2pKitViewModel.kt:716-760 | Per-transfer StateFlow collectors never terminate (CLI + Android) → coroutine pile-up over long runs | bug | Reported |
| SMP-5 | S11 | p2p-sample-desktop/.../Main.kt:175-194 | CLI has no SIGINT/shutdown hook: Ctrl-C skips `p2p.stop()`, leaving the mDNS advertisement to go stale with no goodbye (ghost peer) | bug | Reported |
| SMP-6 | S11 | p2p-sample-desktop-ui/.../Main.kt:373,675-869; P2pKitViewModel.kt:387,674-1049 | Remote-controlled strings printed unsanitized to terminal-bound streams (desktop-ui stderr, Android logcat) — CLI-only terminal-escape fix not mirrored | bug | Reported |
| SMP-7 | S11 | p2p-sample-desktop-ui/.../Main.kt:1611-1615,1636-1644 | desktop-ui renders unbounded remote-supplied reject/cancel reasons (Android's `.take(200)`/`maxLines` bound not mirrored) → UI jank | bug | Reported |
| SMP-8 | S11 | KmpConsumerLoopbackTest.kt:100-109; Demo.kt:31-32 | KmpConsumerLoopbackTest subscribes to `session.incoming` only after the session is emitted — scheduling race can drop the greeting (latent flake) | bug | Reported |

---

## Improvement

| ID | Section | File(s):line | Title (short) | Category | Status |
|---|---|---|---|---|---|
| ARCH-11 | S2 | P2pKitImpl.kt:452-455 | `stop()` bounds mutex-acquisition and teardown together, cancelling a healthy-but-slow locked teardown and re-running it lock-lessly | improvement | Reported |
| ARCH-12 | S2 | P2pKitImpl.kt:428 | Second concurrent `stop()` returns before teardown completes (no join semantics) | improvement | Reported |
| ARCH-13 | S2 | AndroidNetworkPathObserver.kt:98-104 | Make the `NET_CAPABILITY_INTERNET`-default reliance explicit (a future "add capabilities" edit would break the hotspot story) | improvement | Reported |
| ARCH-14 | S2 | P2pKitImpl.kt:115-118 vs :351-415 | Post-stop `stopAdvertising`/`stopDiscovery`/`notifyAppBackgrounded` silently no-op, contradicting the "every entry point rejects further calls" comment | improvement | Reported |
| ARCH-15 | S2 | TransportManagerTest.kt | Tie-break determinism (priority → ordinal → registration order) is unasserted | improvement | Reported |
| ARCH-16 | S2 | IosNetworkPathObserver.kt:78-99 | No path-transition logging where iOS path flaps are under active hardware investigation | improvement | Reported |
| API-11 | S1 | P2pKitImpl.kt:66-67,96; Builders.kt:105-108; SecurityManager.kt | `securityMode`/`appKilledPolicy` accepted by the DSL but provably inert; `SecurityManager` is public yet not injectable | improvement | Reported |
| API-12 | S1 | Builders.kt:40-41,125-127 | `deviceName` unvalidated at build time (blank/oversized names fail later, opaquely) | improvement | Reported |
| API-15 | S1 | DataTransport.kt:53; RawConnection.kt:28; DiscoveryTransport.kt:18-21 | SPI contracts omit obligations core relies on: `close()` idempotency, `connect`/`startAdvertising` error handling | improvement | Reported |
| API-21 | S1 | Peer.kt:8; P2pKit.kt:62; NetworkPath.kt:40; NetworkProvisioningTypes.kt:128-129 | Doc nits: unresolved/misleading KDoc references (Dokka links to internal/androidMain types) | improvement | Reported |
| API-22 | S1 | NetworkProvisioningFactory.kt:51-59 | `ProvisioningContext` exposes experimental `ManualPeerRegistrar` via `@OptIn` instead of propagating `@ExperimentalP2pApi` | improvement | Reported |
| SES-12 | S3 | SessionManager.kt:694-699 | `Rejected` log line mislabels `existingState` (prints the newcomer's state, not the incumbent's) | improvement | Reported |
| SES-13 | S3 | SessionManager.kt:739-744 | `closeAllSessions` is sequential; stop latency scales with wedged sessions (≈2 s × N) | improvement | Reported |
| SES-14 | S3 | SessionManager.kt:713,721,742; P2pSessionImpl.kt:519-521 | Tail-position `runCatching` around suspending close/send swallows `CancellationException` (letter-of-invariant) | improvement | Reported |
| SES-15 | S3 | SessionManager.kt:233 | Session id collisions possible within one clock millisecond (add a monotonic counter) | improvement | Reported |
| SES-16 | S3 | Handshake.kt:52-70; SessionManager.kt:348,357 | Handshake reject paths can stall on the best-effort `sendError` (unbounded write; subsumed by SES-11 if fixed) | improvement | Reported |
| SES-17 | S3/S15 | SessionFlowTest.kt:198-230 | SessionFlowTest weaknesses: single-frame payloads make interleaving impossible; `Closed||Failed` tolerance (both catalogued) | improvement | Reported |
| SES-18 | S3/S15 | KeepAliveTest.kt | KeepAliveTest gaps (rearm PONG-deadline reset, PING-send-failure, wedged-mutex pre-send check) + real-time cadence | improvement | Reported |
| SES-19 | S3/S15 | SimultaneousOpenTest.kt:96-126 | SimultaneousOpenTest asserts only session count, not the arbitration contract (tie-break direction, survivor health, arrival orders) | improvement | Reported |
| IDN-7 | S4 | ManualPeerRegistrar.kt:24-43; PeerRegistry.kt:126-131 | No unregister/expiry path for manual peers; dedupe-hit silently ignores a new deviceName ([API-CHANGE] for `unregisterManualPeer`) | improvement | Reported |
| IDN-8 | S4 | SessionManager.kt:344-352; P2pKit.kt:171-172; PeerRegistry.kt:61 | Manual-peer handshake silently exempt from the mismatch check: log the remote's real HELLO id; `lastSeen` KDoc wrong for manual peers | improvement | Reported |
| IDN-9 | S4 | PeerRegistry.kt:158-164; InMemoryPeerIdStorage.kt:18-26 | evictLoop swallows Throwable with no logger (convention breach); `InMemoryPeerIdStorage` uses a plain `var` | improvement | Reported |
| DSC-I1 | S5 | JvmLanDiag.kt; IosLanDebug.kt:58-63; IosLanDiscoveryTransport.kt:600 | Diag "zero allocation when disabled" is false at call sites; iOS builds+retains trace lines with no subscribers | improvement | Reported |
| DSC-I2 | S5 | IosLanDiscoveryTransport.kt:251-280 | iOS announce loop has no per-tick try/catch; an unexpected throw silently kills re-announcing (15 s evaporation returns) | improvement | Reported |
| DSC-I3 | S5 | AndroidLanDiscoveryTransport.kt:900-925 | Rebind retry budget resets only on success/watcher-stop; after exhaustion each new network episode gets one un-retried attempt | improvement | Reported |
| DSC-I4 | S5 | JvmLanDiscoveryTransport.kt:361; AndroidLanDiscoveryTransport.kt:381 | `JMDNS_LIST_SNAPSHOT_TIMEOUT_MS` constant drift (named on JVM, inlined `200L` on Android) | improvement | Reported |
| DSC-I5 | S5 | JvmLanDiscoveryTransport.kt:248-254; AndroidLanDiscoveryTransport.kt:385-400 | refresh() re-queries every cached `_p2pkit._tcp` service regardless of appId (multicast noise on shared-type networks) | improvement | Reported |
| DSC-I6 | S5 | IosEndpointRegistry.kt; IosLanDiscoveryTransport.kt:283-298 | `stopDiscovery` leaves all endpoint-registry entries behind (bounded but untidy) | improvement | Reported |
| DSC-I7 | S5/S6 | all three advertisers (TXT `pv`) | Advertised `TXT_PROTOCOL_VERSION` is never read back — read it as an early filter or document as reserved | improvement | Reported |
| DSC-I8 | S5/S12 | IosSwiftHelpers.kt:33-50 | `peersSnapshot`/`sessionsSnapshot`/`stateName` are public/exported/used by the iOS sample but absent from `P2pKit-Spec.md` | improvement | Reported |
| DSC-I9 | S15 | IosLanLifecycleTest.kt:46-47 | Test appId uses second-resolution timestamp; two instances in the same second share it (zombie-advert bleed) | improvement | Reported |
| DSC-I10 | S5 | Lan.kt:16 | `LanServiceRegistration` documents `tcpPort != 0` precondition but neither JVM nor Android asserts it before `ServiceInfo.create` | improvement | Reported |
| CON-14 | S7 | JvmRawConnection.kt:206; AndroidRawConnection.kt:205 | Write watchdog is untestable (hardcoded 30 s constant) and untested at the transport level (REMEDIATION's cited test uses the fake) | improvement | Reported |
| CON-15 | S7 | IosLanDataTransport.kt:413-416 | `buildListener` blocks the calling thread up to 5 s (`dispatch_semaphore_wait`) inside a suspend path | improvement | Reported |
| CON-16 | S7 | IosLanDebug.kt:58-63; IosRawConnection.kt:219 | `IosLanDebug.log` builds strings and emits per event with no master gate; one line per `write()` on the hot path | improvement | Reported |
| CON-17 | S15 | IosLanLoopbackTest.kt:43-44 | iOS loopback test `unique` id has 1-second resolution (stale-advert bleed) | improvement | Reported |
| CON-18 | S7 | JvmLanDataTransport.kt:88-93; IosLanDataTransport.kt:446-455 | Dial uses only the first LAN hint; no multi-address fallback (adjacent to catalogued issue #2) | improvement | Reported |
| CON-19 | S15 | IosRawConnectionTest.kt:58,73 | IosRawConnectionTest asserts exact exception message strings (couples the test to a diagnostic string) | improvement | Reported |
| PRO-8 | S6 | FrameReader.kt:48-66 | FrameReader trusts `payload_len` before checking magic (waits up to 8 MiB before rejecting bad magic) | improvement | Reported |
| PRO-9 | S6 | Chunker.kt:53; FrameCodec.kt:31-48 | No sender-side symmetry guards: Chunker can exceed `MAX_TOTAL_CHUNKS`, `encode` can exceed `MAX_FRAME_PAYLOAD_BYTES` (latent-config hazard) | improvement | Reported |
| PRO-11 | S6 | Lan.kt:52-53; ProtocolConstants.kt:13 | `LanConstants.PROTOCOL_VERSION` is a comment-enforced duplicate of `ProtocolConstants.VERSION` with no parity assertion | improvement | Reported |
| PRO-12 | S6 | FrameReader.kt:17-18,74; P2pKit-Spec.md §13.2; DefaultP2pProtocol.kt:216-219 | Doc/diagnostic nits: KDoc param-as-property, "UUID" vs 16 random bytes, reason-truncation UTF-8 split, unthrottled skip-warn | improvement | Reported |
| FIL-12 | S8 | P2pSessionImpl.kt:518-522,543; FileTransferDispatcher.kt:434 | Inbound FILE_DATA sink writes run inline in `routeEvents` (head-of-line blocking of PONG replies) — a slow sink can delay our keep-alive | improvement | Reported |
| FIL-13 | S8 | FileTransferDispatcher.kt:388-390 | `onFileAccept` mutates `entry.timer` outside the dispatcher lock (benign today; breaks the uniform lock-discipline invariant) | improvement | Reported |
| FIL-14 | S8 | FileTransferDispatcher.kt:113; SessionManager.kt:232-244; Frame.kt:98-100 | TransferId from a seedable-but-default `Random.Default`; no cross-map duplicate check in `sendFile` (cheap hardening) | improvement | Reported |
| FIL-15 | S15 | FileTransferFlowTest.kt:326-352 | `cancelMidStreamPropagatesToReceiver` tolerates two receiver outcomes but hard-asserts the sender side (latent flake) | improvement | Reported |
| PRM-2 | S9 | PermissionManagerFactory.android.kt:18-20 vs :54-58 | Construction-time manifest warn checks 2 of the 4 install-time permissions its own header lists | improvement | Reported |
| PRM-3 | S9 | PermissionGateTest.kt:47-136 | PermissionGateTest does not pin the full gate contract (connect() un-gated; permission-ordering; Android manager manual-only) | improvement | Reported |
| PRM-14 | S10 | IosManualNetworkProvisioningManager.kt:82-99 | Implement iOS `hostAddresses` via `getifaddrs` (companion to PRM-13) for iOS→X manual-IP parity | improvement | Reported |
| PRM-15 | S10 | JvmNetworkProvisioningManager.kt:148-155; AndroidNetworkProvisioningManager.kt:419; WifiManagerWrapperImpl.kt:299 | Address-collection semantics drift across the three managers (IPv6 inclusion, failure→NoNetwork vs Unknown, joined-state SSID) | improvement | Reported |
| PRM-16 | S10 | AndroidNetworkProvisioningManager.kt:190-196; NetworkProvisioningTypes.kt:24-43 | Join-rejection message says "already in progress" when the state is already joined; no way to leave a joined network ([API-CHANGE] for `leaveNetwork`) | improvement | Reported |
| PRM-17 | S10/S15 | AndroidNetworkProvisioningManagerTest.kt:417-446,172-324 | Host test fidelity: fakes model pre-audit `replay=0` flow semantics; `…AndClearsHandle` tests assert neither the close nor the state | improvement | Reported |
| PRM-18 | S10/S15 | ManualIpLoopbackTest.kt:85-114,47-65 | Dead 127.* loopback branch; one-directional "round-trip"; process-global `user.home` mutation | improvement | Reported |
| PRM-19 | S10/S15 | JvmNetworkProvisioningManagerTest.kt:82-100 | Conditional assertion silently passes on a NIC-less host; poll loop and timeout knobs untested | improvement | Reported |
| PRM-20 | S10 | AndroidNetworkProvisioningManager.kt:293-302; AndroidDsl.kt:33-37; AndroidProvisioningFactory.kt:15; AndroidManifest.xml | Sidecar KDoc/manifest nits: misplaced `close()` doc, unresolved links, NEARBY device-API note, install-time-perm library declaration | improvement | Reported |
| IOSB-7 | S12 | p2pkit_nw.h:25-97 | Make ownership explicit — annotate the create helper `NW_RETURNS_RETAINED`; fail compilation if built without ARC | improvement | Reported |
| IOSB-8 | S12 | p2pkit_nw.def:6-7 | `-framework Network` in compilerOpts is link-only; the `-I` is cwd-relative (prefer `includeDirs(project.file(...))`) | improvement | Reported |
| IOSB-10 | S12 | iosApp/build.gradle.kts:9-27 | Undocumented environment assumptions; the nested Gradle-in-Gradle chain deserves a comment + xcodegen/JDK probe | improvement | Reported |
| IOSB-12 | S12 | iosApp/ContentView.swift:1489-1523 | `FileHandleRawSink` swallows disk-write failures: a truncated file still reports "Completed" (deliberate sample tradeoff — surface it) | improvement | Reported |
| BLD-4 | S13 | p2p-core/build.gradle.kts:27-38; p2p-transport-lan/build.gradle.kts:116-126 | Validate git subprocess output in both provenance writers (stderr-merge could pollute BUILD_COMMIT / BuildInfo) | improvement | Reported |
| BLD-5 | S13 | settings.gradle.kts:1-21; gradle/gradle-daemon-jvm.properties | `jvmToolchain(17)` has no auto-provisioning while the daemon JVM (21) auto-downloads (fresh-machine DX asymmetry) | improvement | Reported |
| BLD-6 | S13 | gradle/wrapper/gradle-wrapper.properties:1-7 | No `distributionSha256Sum` pin (supply-chain hardening for a public release) | improvement | Reported |
| BLD-7 | S13 | all four publishable modules | [CATALOGUED] `explicitApi()` not enabled on any published module despite a locked public API | improvement | Reported |
| BLD-8 | S13 | p2p-sample-desktop/build.gradle.kts:13-15 | `standardInput = System.in` on the run task is configuration-cache-incompatible (latent; CC not enabled) | improvement | Reported |
| BLD-9 | S13 | p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.def:6 | cinterop def uses a cwd-relative include path (duplicate of IOSB-8, build-side) | improvement | Reported |
| BLD-10 | S13 | settings.gradle.kts; provisioning-desktop build; .gitignore; .editorconfig; sample-android build; libs.versions.toml | Hygiene batch: content-filter, redundant testImpl, dead ignore rules, unwired ktlint knobs, sample versionName, ~18-month-old androidx pins | improvement | Reported |
| TST-5 | S15 | FakeRawConnection.kt:37-40; CloseSemanticsTest.kt:117-143 | No reusable write-fault injection (blocked/slow/transient-fail) in the shared fixture | improvement | Reported |
| TST-6 | S15 | FakeDataTransport.kt | FakeDataTransport models neither the `start()` contract nor close-visibility | improvement | Reported |
| TST-7 | S15 | FakeRawConnection.kt:35; FakeDataTransport.kt:35-36 | Unsynchronized mutable state in fixtures read/written across dispatcher threads (latent race, benign today) | improvement | Reported |
| TST-8 | S15 | SessionReconnectRotationTest.kt:148 | Address-rotation coverage drives re-resolution only via `PeerEvent.Updated`, which no shipped JVM/Android transport emits; fake `refresh()` has no side effects | improvement | Reported |
| TST-12 | S15 | (repo-wide) | Zero virtual-time usage: every async suite is `runBlocking` + wall clock; `kotlinx-coroutines-test` declared-but-unused in 5 modules (flake debt) | improvement | Reported |
| TST-13 | S15 | (repo-wide) | NoOp-logger blind spots: warn-only diagnostics (ZOMBIE, stuck-Reconnecting, store soft invariants) asserted nowhere; no shared RecordingLogger | improvement | Reported |
| TST-14 | S15 | FakeDiscoveryTransport.kt; PeerRegistryTest.kt:39; KitLifecycleTest.kt | Fixture duplication drift: three discovery/transport fakes with three different event-flow configs | improvement | Reported |
| TST-15 | S15/S3 | SimultaneousOpenTest.kt:113-121 | Accepts a `Reconnecting` survivor as "live"; a regression closing the wrong physical connection would pass | improvement | Reported |
| TST-16 | S15 | JvmLanLoopbackTest.kt:60-64; KmpConsumerLoopbackTest.kt:58-61 | Integration layer is environment-conditional (`Assume.assumeTrue`) and mutates global JVM state; no CI gate asserts loopback tests actually ran | improvement | Reported |
| DOCA-20 | S14 | P2PKIT_GAP_ANALYSIS_2026-07.md (untracked) | Informational: identify/keep/commit the untracked strategy doc (§4.3 overstated; P7 `@Ignore` wording collides with the standing rule; line refs pre-remediation) | improvement (informational) | Reported |
| DOCA-I1 | S14 | README.md:15-24,356-361 | README teaser snippet is non-compiling (top-level suspend calls); CLI arg list omits the `trace=` switch | improvement | Reported |
| DOCA-I2 | S14 | docs/STABILIZATION_AND_RELEASE.md:55 | Part A row A11 wording predates the #9 permission-model change | improvement | Reported |
| DOCA-I3 | S14 | docs/STABILIZATION_AND_RELEASE.md:34-41 | Part A smoke preamble should require an on-device build-identity (stamp) check | improvement | Reported |
| DOCA-I4 | S14 | P2pKit-Spec.md:1399 | Spec §24 item 8 instructs the README to "mark provisioning as v0.2" (reintroduces the DOCA-2 staleness) | improvement | Reported |
| DOCB-I1 | S14 | README.md; P2pKit-Spec.md; LICENSE | README/Spec have no License section despite shipping Apache-2.0 POMs | improvement | Reported |
| DOCB-I2 | S14 | docs/audit-evidence/README.md:61-74 | The TXT-dump proof has no captured artifact behind it (save it next capture) | improvement | Reported |
| DOCB-I3 | S14 | docs/hardware-validation-checklist.md:34,53,285 | Android capture filter (`adb logcat -s p2pkit:V`) drops all SDK transport-trace tags | improvement | Reported |
| SEC-I1 | — | (folded into PERF-9) | FrameReader O(n²) is peer-input-controlled, not merely an app-chunk-size note — see collapsed row PERF-9 | improvement | Reported |
| SEC-I2 | — | (folded into PRO-4) | HELLO `platform`/per-transport strings not length-validated — see collapsed row PRO-4 | improvement | Reported |
| PERF-1 | S7 | JvmRawConnection.kt:151-176; FrameReader.kt:37-79; FrameCodec.kt:109 | Receive path: 5-copy chain, 8 KiB read buffer, per-read dispatcher hops (JVM/Android; iOS shares the copy chain) | improvement | Reported |
| PERF-2 | S6/S8 | Chunker.kt:53-66; DefaultP2pProtocol.kt:22-27; StreamingFileSender.kt:40 | Send path: full-message materialization in Chunker + one encode copy per frame (2× transient memory on large sends) | improvement | Reported |
| PERF-3 | S7 | JvmRawConnection.kt:96-107,144; AndroidRawConnection.kt:96-107,144 | One watchdog coroutine launched and cancelled per `write()` (JVM+Android) — avoidable scheduler churn | improvement | Reported |
| PERF-4 | S5/S7 | IosLanDebug.kt:58-63; JvmLanDiag.kt:58-69; AndroidLanDiscoveryTransport.kt (ungated Log.d) | Diagnostic-trace string work performed when tracing is disabled; iOS has no master gate at all | improvement | Reported |
| PERF-5 | S3 | P2pSessionImpl.kt:499-515; SessionStore.kt:207-213 | Zombie-detection lookup runs per inbound message even when its only output (a warn) is discarded by the default NoOp logger | improvement | Reported |
| PERF-6 | S3 | P2pSessionImpl.kt:235-242,518-522; DefaultP2pProtocol.kt:22-27 | `sendMutex` held across all chunks of a message; control frames (PONG/PING) queue behind large sends (file path already per-chunk) | improvement | Reported |
| PERF-7 | S3/S5 | SessionManager.kt:498,609-654; P2pKitImpl.kt:169-183 | Reconnect discovery refresh is per-session with no cross-session coalescing; cost multiplies at K reconnecting sessions | improvement | Reported |
| PERF-10 | S7 | IosLanDataTransport.kt:394-416,277-278; P2pKitImpl.kt:79 | iOS listener (re)build blocks a `Dispatchers.Default` worker up to 5 s; the kit's entire core runs on Default | improvement | Reported |
| SMP-9 | S11 | ui/Main.kt:289-315; P2pKitViewModel.kt:270-315 | `start()` has no failure guard; a throwing `P2pKit.create` wedges the UI in "Starting…" forever | improvement | Reported |
| SMP-10 | S11 | ui/Main.kt:927-933,1346-1350 | desktop-ui `pickFile()` shows a modal AWT `FileDialog` from the Compose UI thread | improvement | Reported |
| SMP-11 | S11 | MainActivity.kt; P2pKitViewModel.kt:71-72 | Android harness has no keep-alive against cached-app freezing during manual tests | improvement | Reported |
| SMP-12 | S11 | MainActivity.kt:867-871,1090-1094 | MainActivity re-derives the OS permission string from device SDK only (would diverge if targetSdk ≤32) | improvement | Reported |
| SMP-13 | S11 | p2p-sample-desktop/.../Main.kt:559 | CLI `printInfo` calls a suspend provisioning API unguarded inside the REPL (a throw skips `p2p.stop()` teardown) | improvement | Reported |
| SMP-14 | S11 | KmpConsumerLoopbackTest.kt:124-127 | `finally` stops kits without guarding the first `stop()` (a throw leaks the second kit into later suites) | improvement | Reported |

---

## Verification notes (Critical + High)

Each cited primary `file:line` was opened in the current tree (HEAD `870bf10`)
and the condition checked directly. All 17 Confirmed; 0 Refuted; 0 Needs-runtime.

- **RBS-1 — Confirmed.** `PeerId(pid)` at IosLanDiscoveryTransport.kt:634 (Found) and :675 (`emitLostById`, guarded only by the self-check at :674 — no appId gate, no blank guard); JvmLanDiscoveryTransport.kt:134 `PeerEvent.Lost(PeerId(pid))` in `serviceRemoved` with only the self-check at :132 (`serviceResolved` alone filters appId at :142); `PeerId` throws on blank (Identity.kt:29). Residual: exact JVM/Android JmDNS-thread disposition of the throw is runtime-dependent, but the unguarded-throw condition holds in source.
- **ARCH-1 — Confirmed.** P2pKitImpl.kt:266 `runCatching { transport.start() }` catches all throwables incl. CE; :280 `if (!stopped) _state.value = P2pState.Failed(failed)`; :281 `throw failed` — no CE-first arm. Secondary CE-swallow at :301 confirmed. Residual: the Android host-crash escalation is standard kotlinx behavior, not separately reproduced.
- **ARCH-2 — Confirmed.** `withContext(NonCancellable)` closes at :463; `runCatching { pathObserver.close() }` (:469), `internalJob.cancel()` (:470), `_state.value = P2pState.Stopped` (:471) run outside it, on the caller's cancellable context, unbounded.
- **API-1 — Confirmed.** Chunker.kt:29-31 reads only `message.value`/`message.bytes`; Reassembler.kt:182-184 `decodePayload` reconstructs Text/Binary with the default (empty) metadata. No `.metadata` serialization anywhere in the protocol layer.
- **API-2 (+SES-2) — Confirmed.** P2pSessionImpl.kt:239-241: `sendMutex.withLock { protocol.sendMessage(connection, message) }` with no exception mapping; only the pre-write state check throws `ConnectionFailed`.
- **SES-1 (+CON-7) — Confirmed.** `observeRawState` (:226-227) calls `onConnectionLost` on Closed/Failed when `_state == Connected`; routeEvents channel-end (:552) calls `markCleanlyClosed()`; both gated on `Connected` under the connection lock → scheduler race. routeEvents catch(Throwable)→`onConnectionLost` at :557-559 also present.
- **DSC-1 — Confirmed.** `evictStalePeers` (PeerRegistry.kt:101-102) drops non-manual peers past `staleTimeoutMillis`; the JVM listener emits only Found/Lost (no `Updated` re-announce). Residual: the "JmDNS never re-fires on renewal" premise rests on the reviewer's JmDNS-3.6.3 source reading; the P2pKit-side no-heartbeat + 15 s-eviction condition is confirmed in source.
- **CON-1 — Confirmed.** JvmRawConnection.kt:185-188: `withContext(Dispatchers.IO) { closeSocketOnce() }` then `connScope.cancel()` — an already-cancelled caller throws CE at `withContext` entry, skipping both; the read-loop release at :173 sits after the `while` and is skipped on collector cancellation.
- **CON-3 — Confirmed.** JvmLanDataTransport.kt:145 `if (!closed) close(e)` fails the callbackFlow; the collector is `.launchIn(scope)` on the CEH-less kit scope (P2pKitImpl.kt:78-79).
- **FIL-1 — Confirmed.** FileTransferDispatcher.kt:141-144 `scope.launch { handle.state.first { it.isTerminal() }; runCatching { source.close() } }` — no `finally`; the watcher is a child of `sessionJob` (P2pSessionImpl.kt:126), which `close()` cancels via `sessionJob.cancelAndJoin()` (:291-301) after `markFailed` schedules the resume. (Matches the report's own orchestrator re-verification.)
- **FIL-2 — Confirmed.** FileTransferDispatcher.kt:582-587 catch(Throwable): `markFailed` + `outgoing.remove` + `logger.warn`, no `sendFileCancel`; contrast the receiver→sender path at :449-461 which does notify. Receiver's offer timer is cancelled at accept and never re-armed → non-terminal indefinitely on a healthy connection.
- **SEC-1 — Confirmed.** SessionManager.kt:146-152: `incomingConnections().onEach { handleIncoming(it) }.launchIn(scope)`; `handleIncoming` is a non-blocking `scope.launch`. No `Semaphore`/session cap anywhere (grep). The bounded accept queue drains at O(1), providing no back-pressure onto the fan-out.
- **TST-1 (+SES-10) — Confirmed.** FakeRawConnection.kt:58-63 `breakWith` closes the receive channel *with* a cause (read flow throws), whereas all three shipped `read()` implementations complete the flow *normally* on error/EOF and flip state to Closed — the fixture exercises a production-unreachable branch and cannot model peer-initiated close. Rated High by A12 (fixture reviewer); A03's SES-10 rated the same defect Medium.
- **TST-9 (+SES-8) — Confirmed.** `strictInvariants = true` appears only in SessionStoreInvariantTest.kt:46,78 (a directly-built store with a forced violation); SessionManager.kt:109 defaults `false` and nothing in P2pKitImpl (or anywhere) overrides it, so kit-level suites run warn-mode with a NoOp logger. Rated High by A12; A03's SES-8 rated it Medium.
- **BLD-2 — Confirmed.** p2p-core/build.gradle.kts:118-143 enriches the POM but wires no `withJavadocJar()`; only p2p-network-provisioning-desktop/build.gradle.kts:12-15 has `java { withSourcesJar(); withJavadocJar() }`. The two other KMP modules likewise lack it. Residual: whether KGP 2.3.x auto-attaches a javadoc jar would be settled by a `publishToMavenLocal` listing — but no wiring exists in the build files.
- **IOSB-3 — Confirmed.** scripts/run-ios-app.sh:47-50 `find "$DERIVED_DATA_BASE" -name 'p2pkit-sample.app' -path '*Debug-iphonesimulator*' -print -quit` searches all of DerivedData and returns the first hit in arbitrary order; the xcodebuild invocation pins no `-derivedDataPath`.
- **DOCB-1 — Confirmed.** AUDIT_REPORT_2026-06.md:60-86 still lists as "deferred" items independently confirmed fixed elsewhere in this campaign: the permissionManager knob (:66 → exists, A02/A09), manual-peer dedupe (:67 → `b9f6311`, IDN-5), handshake wrap (:68 → `a08500a`), write watchdog (:69 → confirmed A06), iOS `error()` init (:72), cellular-path observer (:75), project.yml plist keys (:80 → A10), BUILD_COMMIT stamp (:82 → `adca586`), maven-publish on 4 modules (:83 → A11), HandshakeTest/KeepAliveTest (:86 → exist). CLAUDE.md routes agents to this list.

## Duplicates collapsed

13 duplicate finding-IDs were folded into 10 canonical rows (the canonical row
lists all contributing IDs):

1. **SES-1 (canonical) ← CON-7** — the terminal-outcome clean-close-vs-reconnect race; S3 owns, S7 flagged the transport-behavior root enabler.
2. **API-2 (canonical) ← SES-2** — `send()` leaking raw platform exceptions (same code, P2pSessionImpl.kt:235-242); rated High by A02, Medium by A03.
3. **TST-1 (canonical) ← SES-10** — the `FakeRawConnection.breakWith` fidelity defect; rated High by A12, Medium by A03.
4. **TST-9 (canonical) ← SES-8** — `strictInvariants` inert in kit-level suites; rated High by A12, Medium by A03.
5. **DOCA-8 (canonical) ← PRO-3** — Spec §13.4 omits the 16 MiB aggregate cap (doc reviewer S14 + protocol reviewer S6).
6. **PRO-4 (canonical) ← SEC-I2** — HELLO `platform`/per-transport strings not length-validated (S6 finding + resilience escalation).
7. **PERF-9 (canonical) ← PRO-10, SEC-I1** — `FrameReader` O(n²) copy amplification: perf note (PRO-10), peer-input escalation (SEC-I1), and the Low-severity CPU-robustness bug (PERF-9) are one defect.
8. **SEC-2 (canonical) ← PERF-8, RBS-3** — uncapped `PeerRegistry.tracked` + O(n) republish, its per-tick allocation cost (PERF-8), and the parallel unbounded iOS transport maps (RBS-3).
9. **DOCA-16 (canonical) ← SES-9** — `ConnectionState.Closing` never entered while spec §10 documents it as a transition (spec + code/States.kt).
10. **DOCA-3 (canonical) ← PRM-12, DOCA-10** — "iOS provisioning permanently Unsupported" wording vs shipped `iosManualIp()`, spanning CLAUDE.md (PRM-12), README (DOCA-3), Spec §5.1/§21.3 (DOCA-10), plus INTERNAL_TESTING and WORKSPACE_SYNC_DASHBOARD instances.

**Related but NOT collapsed (distinct code/layer; cross-referenced instead):**
DSC-2 ↔ CON-10 (Android unconditional logging — discovery transport vs raw
connection, different files); SEC-1 ↔ CON-3 ↔ CON-9 (admission gap vs its
EMFILE-crash symptom vs the iOS unbounded accept queue); RBS-2 ↔ SMP-6 (SDK-core
log sanitization vs sample terminal sanitization); API-1 ↔ DOCA-15 (metadata:
code vs spec); PRO-2 ↔ DOCA-6 (ACK: spec/impl vs README); FIL-1 ↔ API-4 ↔
IOSB-11 (source-ownership: SDK leak vs spec text vs sample double-close);
IDN-5 ↔ DOCB-1 (the stale manual-peer-dedupe deferral is one item within
DOCB-1's broader stale-list finding).

## Open decisions

Carried forward from the reviewers for orchestrator/maintainer decision:

**RC-gate decisions (release-blocking to resolve, per DOCA-14).**
- **`P2pMessage.metadata` wire semantics (API-1 / DOCA-14 / DOCA-15).** The public field is silently dropped on the wire. Decide before the RC locks the frame format: (a) encode it behind a new flag bit mirrored across all three platforms, or (b) explicitly de-scope it in KDoc + spec §9.4. Either way pin the receive-side contract with a test.
- **Smoke-binary freshness (DOCA-14 / IOSB-3 / DOCA-I3).** Add an on-device build-identity (stamp==HEAD) check to the Part A smoke preamble; the iOS run-script stale-install defect can otherwise let smoke rows exercise a stale binary.

**Findings flagged `[API-CHANGE]` (a clean fix needs public-surface change; each has a no-API-change alternative noted in its source report).**
- API-1 (metadata wire encoding — the wire/API decision above).
- API-11 (make `SecurityManager` injectable / wire `securityMode` — or document it as forward-compat no-op).
- SES-9/DOCA-16 (actually emit `ConnectionState.Closing` — the no-change alternative is the spec/doc fix).
- IDN-7 (`unregisterManualPeer` — no-change alt: document the manual-peer lifetime + refresh the display name on dedupe-hit).
- PRM-1 (per-operation permission sets `missingPermissions(operation)` — no-change alt: change the docs to recommend the sample's standalone-manager pattern).
- PRM-16 (`leaveNetwork()` — no-change alt: reword the join-rejection message).
- FIL-9 (Android `sendFile(File)` overload / shared `jvmAndroid` source set — no-change alt: fix the KDoc recipe).
- FIL-8 (normalize/reject `offer.name` separators in `FileOfferPayload.decode` is a cross-version-interop behavior change — no-change alt: document the field as peer-controlled).

**Deferred C:54 public-enum question — assessed sound, keep deferred.**
Both A02 (API-13 C:54 assessment) and A09 verified that after remediation #9,
`ChangeWifiState` has exactly one Android mapping (`CHANGE_WIFI_STATE`) and no
code maps it to `CHANGE_WIFI_MULTICAST_STATE`; the single meaning removes the
ambiguity, so deferring a new `ChangeWifiMulticastState` enum constant (which
would be speculative API with no consumer) is correct. No action beyond
recording the decision.

**[CATALOGUED] deferrals reviewers argued should be reconsidered for the RC.**
- **API-2/SES-2** — A03 assessed the original "minor" deferral of the typed-error breach as unsound for an RC: it is app-facing, platform-divergent, and a one-catch-block fix. (Now consolidated as a High row.)
- **BLD-1** — [CATALOGUED PROBLEMS:356] BuildInfo `BUILD_TIME` non-reproducibility; A11 argues the RC lens (signed, reproducible artifacts) raises its relevance above the "open, deferred" tag.
- **ARCH-10** — [CATALOGUED B:201] blocking disk I/O at kit construction; A01 flags for an explicit decision (document "construct off the main thread" and/or lazy file I/O) rather than continued silent drift.
- **BLD-7** — [CATALOGUED PROBLEMS:363] `explicitApi()` off on all published modules; A11 notes the generated BuildInfo already writes explicit `public`, signalling intent never enforced against a locked API.

**Sound deferrals reviewers explicitly affirmed (no reconsideration; recorded for the orchestrator).**
- Inbound HELLO peerId unverified until the encryption milestone (`TODO(encryption-milestone)`, SessionManager.kt:360) — A14-sec/SEC-A1 and A04 both affirm the deferral is sound under `SecurityMode.NoneForMvp`; the own-peerId reflection guard at :356 is the correct MVP-level check.
- The 2 iOS-simulator churn tests are known-flaky and validated on real hardware (smoke A4); no masking proposed.
- Android `refresh()` 200 ms JmDNS `list()` snapshot (B:317) latency trade-off; PERF-7's K×-multiplication concern is orthogonal.
- Interface selection / iOS AWDL asymmetry (issues #2/#3) await real-hardware diagnosis.

**Doc-of-record corrections needed (so future agents stop trusting stale status).**
- IDN-5 / DOCB-1 / DOCA-19 / DOCB-2/3/4/5: AUDIT_REPORT_2026-06.md's deferred list, PROBLEMS_P2PKIT.md's open/closed statuses and fix texts, and REMEDIATION_2026-07.md:63's manual-peer-dedupe line are stale; CLAUDE.md routes agents to them. Several PROBLEMS fix prescriptions, applied verbatim today, re-introduce known criticals (DOCB-5). Reviewers recommend dated banners + per-line annotations rather than trusting these as live.
- DOCA-20: the untracked `P2PKIT_GAP_ANALYSIS_2026-07.md` is one `git clean` from loss; keep + commit with a status banner after correcting §4.3 and rewording its P7 `@Ignore` suggestion (which collides with the standing no-masking rule).
