# P2pKit — Audit Remediation Report (2026-07-03)

Remediation of the 21 findings from the max-effort review of the
`audit/exhaustive-review-2026-06` hardening branch, plus three follow-ups
(E:370, C:54, B:317). Fixes are grouped by root cause across 8 commits on this
branch. Every finding was re-verified against the current tree before fixing.

## Result

- **19 findings fixed**, **1 false positive** (#21), **1 deferred** (B:317).
- Two extras also fixed: **E:370** (streamer-cancel race) and **C:54** (permission-enum ambiguity, resolved as a side effect of #9).
- **No public app-API change** (`P2pKit-Spec.md` surface untouched). One internal transport-SPI addition (`PeerOrigin`/`InternalPeer.origin`) — not app-facing.

## Gate status (all green except 2 pre-existing documented flakes)

| Gate | Result |
|---|---|
| `:p2p-core:jvmTest` | PASS |
| `:p2p-core:allTests` (JVM + iOS-native) | PASS — 149 tests, 0 failures on iosSimulatorArm64 |
| `:p2p-transport-lan:jvmTest` | PASS (incl. new fd-leak loopback test asserting `socket.isClosed`) |
| `:p2p-network-provisioning-android:testAndroidHostTest` | PASS |
| `:p2p-network-provisioning-desktop:test` | PASS |
| `:p2p-core:assemble` + `:p2p-transport-lan:assemble` | PASS (JVM + Android + iosArm64/iosX64/iosSimulatorArm64 + framework links) |
| `:p2p-transport-lan:iosSimulatorArm64Test` | 29 tests, **only** the 2 known-flaky churn tests fail (C2) |

The 2 iOS failures (`IosLanLifecycleTest.peerLostEventFiresWhenPeerStops`, `advertiseStopRestartProducesObservablePeerChurn`) are the pre-existing simulator flakes documented in `docs/STABILIZATION_AND_RELEASE.md` C2 (the simulator's `NWBrowser` does not deliver `result_removed` in steady state). They were **not** masked (no `@Ignore`, timeouts unchanged). The #8 fix targets the browser-recreation ghost-peer case (orthogonal to this limitation); the steady-state Lost path needs real-hardware validation (smoke row A4).

## Finding → fix → test → commit

| # | Finding | Status | Fix | Test | Commit |
|---|---------|--------|-----|------|--------|
| 1 | Reassembler dup-chunk accounting bypass | Fixed | Reject duplicate/out-of-range `chunkIndex`; accounting now unconditional | `ReassemblerTest.duplicateChunkIndexThrowsAndDoesNotReplaceStoredBytes`, `outOfRangeChunkIndex…` | `6de50db` |
| 11 | Single-frame 4 MiB cap bypass | Fixed | `MAX_PAYLOAD_BYTES` check on the `totalChunks==1` fast path | `ReassemblerTest.singleFrameOverMaxPayloadBytes…` | `6de50db` |
| 12 | Pending count cap → ~1 GiB aggregate | Fixed | New `MAX_TOTAL_PENDING_BYTES` aggregate budget; `removePending` keeps it exact | `ReassemblerTest.aggregatePendingBytesAcrossMessagesIsCapped` | `6de50db` |
| 14 | Age-based evictStale drops slow msgs | Fixed | Evict on `lastSeenMillis` (inactivity), not first-seen | `ReassemblerTest.slowButSteadyPartialIsNotEvictedAndCompletes`, `idlePartialIsEvicted…` | `6de50db` |
| 3 | Disk-full IOException tears down session | Fixed | `onFileDone` catches `Throwable` scoped to the transfer (mirrors `onFileData`) | `FileTransferErrorIsolationTest.sinkFlushFailureOnFinishFailsOnlyThatTransfer` | `7854ca7` |
| 16 | onFileOffer insert-after-closeAll TOCTOU | Fixed | Re-check `closed` under the lock before insert/emit | `FileTransferFlowTest.offerProcessedWhileDispatcherClosedIsDropped…` | `7854ca7` |
| E:370 | onFileAccept streamer-cancel race | Fixed | `CoroutineStart.LAZY` streamer registered before start | `FileTransferFlowTest.acceptThenImmediateCancelNeverStreamsOrSendsFileDone` | `7854ca7` |
| — | Dispatcher best-effort sends swallow CE | Fixed | try/catch rethrows `CancellationException` | (covered by above) | `7854ca7` |
| 2 | Manual-IP identity/session mismatch | Fixed | Explicit `PeerOrigin`; outgoing keeps dialed identity (no HELLO adoption) | `ManualPeerIdentityTest.manualConnectKeepsDialedSyntheticIdentity…`, `…IsIdempotentAndDoesNotChurn…` | `012e49e` |
| 13 | Manual-peer anti-spoof string-prefix | Fixed | Provenance flag, not `"manual-"` prefix | `ManualPeerIdentityTest.discoveredPeerWithManualLookingIdIsStillRejected…` | `012e49e` |
| 5 | Android rebind/JmDNS flap bricks transport | Fixed | Advertise/discovery INTENT flags decoupled from handles; bounded create-failure retry | Compile + code review + manual (Wi-Fi flap on device) | `25e501c` |
| 7 | JVM discovery refresh swallows CE | Fixed | Add-before-remove listener; rethrow `CancellationException` | Compile + code review; `JvmLanLoopbackTest` unaffected | `25e501c` |
| 8 | iOS ghost peers / announceCache | Fixed | Browser-generation reconcile; departed peers pruned + `emitLost` | `AnnounceCacheReconcileTest` (7 cases, pure helper) | `25e501c` |
| 15 | iOS stale browser callback missing guard | Fixed | `if (browser === b)` on browse-results handler | Compile (behavior covered by reconcile) | `25e501c` |
| 9 | Permission gate regression | Fixed | Core LAN reports no runtime perms; non-fatal startup warn for undeclared install-time perms | `PermissionGateTest` (4 cases incl. the exact regression pair) | `881fb31` |
| C:54 | ChangeWifiState enum ↔ two OS perms | Fixed | Core no longer maps the enum (side effect of #9) — single meaning restored | grep-verified single mapping | `881fb31` |
| 19 | SessionStore invariant hides failures | Fixed | `strictInvariants` (throws in tests, warns in prod) | `SessionStoreInvariantTest` (enforce + no-false-positive) | `e91e094` |
| 4 | JVM/Android write-timeout watchdog | Fixed | Watchdog on connection-owned `Dispatchers.Default` scope + `AtomicInteger` race | `CloseSemanticsTest` (wedged write → close returns) | `f4dd3a9` |
| 6 | JVM/Android socket fd leak on EOF | Fixed | `closeSocketOnce` CAS on every terminal path incl. read-loop EOF | `JvmLanLoopbackTest.remoteDisconnectClosesLocalSocketFd` (`socket.isClosed`) | `f4dd3a9` |
| 17 | stop() NonCancellable/startMutex hang | Fixed | Bounded `startMutex` + lock-less teardown; `ensureStarted` re-checks `stopped` | `KitLifecycleTest.stopCompletesWhenATransportStartHangs` | `f4dd3a9` |
| 18 | iOS write-path send deadline gap | Fixed | `withTimeout(30s)` around the send await (parity with JVM/Android) | `IosRawConnectionTest` + manual (wedged live peer) | `f4dd3a9` |
| 20a | iOS ensureParameters RMW double-create | Fixed | `AtomicReference` compareAndSet | Compile + review | `f4dd3a9` |
| 20b | iOS inbound wrap→trySend leak | Fixed | `raw.cancelNow()` when `trySend` fails | Compile + review | `f4dd3a9` |
| 20c | iOS logConnectionPath nw_path_t leak | Verified non-leaking — no change | Evidence: SDK header `NW_RETURNS_RETAINED` → K/N imports it as a GC-managed `NSObject?`; K/N auto-releases OS_OBJECT copies (no manual release API exists) | n/a | — |
| 10 | BUILD_COMMIT.txt / XCFramework stamp | Fixed | Check passes on stamp≠HEAD iff no framework sources changed since the stamp | Manual recipe in `docs/STABILIZATION_AND_RELEASE.md` (shell not unit-testable) | `adca586` |
| 21 | sendFile source-ownership reversed | **False positive** | `P2pSession.kt:75` KDoc already states "kit takes ownership … closes it automatically … callers must not close it" — matches behavior | existing file-transfer tests | — |

## Deliberately deferred (with reason + risk)

- **B:317 — Android `refresh()` `list(type, 200 ms)` snapshot.** Latency, not correctness: a cold JmDNS cache may miss a peer in one refresh cycle, extending reconnect by ~one 3 s cadence. Left as-is to avoid re-introducing the 6 s lock-stall the 200 ms bound was chosen to prevent. **Risk: low** (self-corrects next cycle).
- **The 2 iOS simulator churn tests.** Fail due to the simulator's `NWBrowser` not delivering `result_removed`; require real-device validation (smoke A4). The #8 fix does not (and cannot) change this simulator limitation. **Risk: low** (steady-state Lost on real radios is a separate, hardware-only verification the repo already tracks).
- **`registerManualPeer` per-call id minting (pre-existing, outside the 21).** Repeated `createManualPeer(host,port)` still mints a fresh id with no `(host,port)` dedup — noted by the original audit as deferred; unchanged here. **Risk: low** (multiple manual peers to one host is an uncommon app pattern).

## API / compatibility notes

- **No app-facing API change.** `PeerOrigin` + `InternalPeer.origin` are additions to the transport SPI (`InternalPeer` is already `public` only because transports live in separate Gradle modules — documented "app code should not use this"); the locked `P2pKit-Spec.md` surface is untouched.
- **Permission behavior change (intended, compatibility-restoring):** core LAN no longer throws `PermissionMissing` from `startAdvertising`/`startDiscovery`; undeclared manifest perms now surface as a startup warning. Apps that declared the documented perms are unaffected.
- **NsdManager not reintroduced; PP2K wire format / Bonjour type / TXT keys unchanged; JVM↔Android RawConnection behavior kept identical.**

## No unrelated behavior changed

The remediation diff is confined to the 27 source/test/doc files listed above (verified via `git status`). Not part of this work and left untouched: `CLAUDE.md` (from the earlier `/init`, uncommitted) and an untracked `P2PKIT_GAP_ANALYSIS_2026-07.md` (present before this task; origin unknown, not created by the remediation).
