# A2-API — S1 public API surface review

Reviewer: A2-API. Scope: 31 files (public API of `:p2p-core` + `P2pKitAndroid.kt`).
Branch `audit/exhaustive-review-2026-06`, HEAD `870bf10`.
Reference reading performed: `P2pKit-Spec.md` (v0.6, 1440 lines), `REMEDIATION_2026-07.md`, `CLAUDE.md`, and the implementations behind every contract claim: `P2pKitImpl.kt`, `P2pSessionImpl.kt`, `SessionManager.kt`, `SessionStore.kt`, `PeerRegistry.kt`, `FileTransferDispatcher.kt`, `OutgoingFileTransferImpl.kt`, `IncomingFileSession.kt`, `TransportManager.kt`, `Handshake.kt`, `DefaultP2pProtocol.kt`, `Chunker.kt`, `Reassembler.kt`, `Frame.kt` (MessageId), `NoOpNetworkPathObserver.kt` + the three `defaultNetworkPathObserver` actuals, `PeerIdStorageFactory.android.kt`, `PermissionManagerFactory.android.kt`, plus transport write paths (`JvmRawConnection.kt`, `IosRawConnection.kt`) and sample call sites (`p2p-sample-desktop`, `p2p-sample-android`, `sample-kmp-shared`, `p2p-sample-desktop-ui`).

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| Config.kt | 83 | findings: API-16 | KeepAliveTest, ReconnectPolicyTest, CloseSemanticsTest (semantics); constructors used across suites | no test asserts the `require` validation messages / IAE behavior |
| Errors.kt | 61 | findings: API-2 (taxonomy claim), API-16 | typed errors asserted in HandshakeTest, SessionFlowTest, TransportManagerTest | no test asserts `send()` failure surfaces as `P2pError` |
| ExperimentalP2pApi.kt | 20 | clean | n/a (annotation) | none |
| Identity.kt | 41 | findings: API-17 | HandshakeTest, InMemoryPeerIdStorageTest, LocalIdentityTest | blank id/appId arriving from network parse paths untested (transport-side) |
| NetworkPath.kt | 94 | clean — every behavioral claim verified (P2pKitImpl.kt:301-312, 469; SessionManager.kt:764-779) | NetworkPathRecoveryTest | observer shared across two kits (stop closes, next kit restarts) untested |
| NetworkProvisioningError.kt | 31 | clean — spec §20.3 match incl. `platformException` naming note | provisioning sidecar tests | none |
| P2pKit.kt | 195 | findings: API-5, API-6 | KitLifecycleTest, PermissionGateTest, LocalIdentityTest, loopback integration | TransportStartFailed propagation from lazy start via `connect()` untested |
| P2pLogger.kt | 24 | clean | used ubiquitously | none |
| P2pMessage.kt | 44 | findings: API-1 | ChunkerTest, ReassemblerTest, SessionFlowTest (payload round-trips only) | metadata round-trip (would fail today — see API-1) |
| P2pSession.kt | 94 | findings: API-2, API-3, API-4 | SessionFlowTest, CloseSemanticsTest, KeepAliveTest | exception-type assertion for mid-send connection loss |
| Peer.kt | 48 | improvements: API-21 | PeerRegistryTest | none |
| States.kt | 46 | findings: API-9, API-10 | KitLifecycleTest (kit states), SessionFlowTest (session states) | no test enumerates the observable session-state set |
| dsl/Builders.kt | 226 | findings: API-7; improvements: API-11, API-12 | exercised by every test constructing a kit; no dedicated builder test | repeated-DSL-block semantics and required-field errors untested |
| permission/NoOpP2pPermissionManager.kt | 16 | findings: API-13 | PermissionGateTest | none |
| permission/P2pPermissionManager.kt | 35 | clean — KDoc verified true post-#9 (gate remains for custom/sidecar managers, P2pKitImpl.kt:497-500); C:54 assessed sound [CATALOGUED] | PermissionGateTest (4 cases) | none |
| provisioning/ManualPeerRegistrar.kt | 43 | findings: API-18 | ManualPeerIdentityTest | IAE on bad host/port unasserted |
| provisioning/NetworkProvisioningFactory.kt | 69 | clean — `lanTcpPort` live-provider claim verified (P2pKitImpl.kt:199-210); improvements: API-22 | sidecar tests (desktop/android) | none |
| provisioning/NetworkProvisioningTypes.kt | 152 | findings: API-18 (createManualPeer inherits undocumented IAE); shape = spec §20 exactly | sidecar tests | none |
| provisioning/UnsupportedNetworkProvisioningManager.kt | 47 | findings: API-8 | none direct | stub return-value test absent |
| security/SecurityManager.kt | 41 | improvements: API-11 — interface invoked (SessionManager.kt:379) but not injectable | HandshakeIdentityTest (indirect) | none |
| transfer/FileTransferConfig.kt | 35 | findings: API-16 (undocumented IAE); defaults = spec §7.6 exactly | FileTransferFlowTest | validation-boundary tests (chunk 0 / 4MiB+1) |
| transfer/FileTransferState.kt | 51 | findings: API-19 | FileTransferFlowTest, FileTransferErrorIsolationTest | timeout state pair (sender Cancelled vs receiver Rejected) unasserted |
| transfer/P2pFileOffer.kt | 52 | findings: API-19, API-20 | FileTransferFlowTest | accept-after-timeout ISE assertion |
| transfer/P2pFileTransfer.kt | 51 | dup-only: FIL-1/FIL-2 (see §2b); "32-char hex id" verified (Frame.kt:87-105), monotonic bytes verified, cancel-when-terminal no-op verified | FileTransferFlowTest, StreamingFileReceiver/SenderTest | zero-byte-file end-to-end |
| transport/DataTransport.kt | 54 | improvements: API-15 | JvmLanLoopbackTest, iOS loopback (implementations) | double-close idempotency not asserted as a contract |
| transport/DiscoveryTransport.kt | 44 | clean — refresh() contract matches SessionManager.kt:469-498 + P2pKitImpl.kt:169-183; V0.4 marker retained | SessionReconnectRotationTest, loopback suites | none |
| transport/HasLocalTcpEndpoint.kt | 27 | clean — AUDIT-2026-06 marker + iOS-rebind caveat consistent with ProvisioningContext docs | iOS lifecycle tests | none |
| transport/Internal.kt | 72 | findings: API-14 | ManualPeerIdentityTest, PeerRegistryTest | none |
| transport/RawConnection.kt | 29 | improvements: API-15 | loopback + FakeRawConnection-based suites | none |
| transport/TransportFactory.kt | 38 | clean — "build once during construction" verified (P2pKitImpl.kt:139-142) | every integration test | none |
| androidMain/.../android/P2pKitAndroid.kt | 33 | clean — applicationContext-only retention verified; warn-at-construction claim verified (PeerIdStorageFactory.android.kt:9-16, PermissionManagerFactory.android.kt:34-39); @Volatile holder; no API-level-gated calls | none (no instrumented tests, per repo policy) | manual recipe only (INTERNAL_TESTING.md) |

## 2. Findings — bugs

### API-1 — `P2pMessage.metadata` is accepted by the API but silently dropped on the wire
- Severity: High | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pMessage.kt:15-24 (API shape + "optional string metadata" KDoc), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Chunker.kt:29-31 (send side), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Reassembler.kt:182-184 (receive side)
- Category: bug
- Root cause: The PP2K frame format (spec §13.2: 36-byte header + payload) has no metadata slot and the protocol layer never serializes the field. `Chunker.chunk` encodes only `message.value` / `message.bytes`; `Reassembler.decodePayload` reconstructs with the default `emptyMap()`.
- Evidence:
  ```kotlin
  // Chunker.kt:29-31 — metadata never read
  val (bytes, isText) = when (message) {
      is P2pMessage.Text -> message.value.encodeToByteArray() to true
      is P2pMessage.Binary -> message.bytes to false
  }
  // Reassembler.kt:182-184 — receiver always gets emptyMap()
  private fun decodePayload(bytes: ByteArray, isText: Boolean): P2pMessage =
      if (isText) P2pMessage.Text(bytes.decodeToString())
      else P2pMessage.Binary(bytes)
  ```
  Grep over `p2p-core/src/commonMain` shows zero reads of `P2pMessage.metadata` outside P2pMessage.kt itself (only `TransportHint.metadata` matches elsewhere). Neither the KDoc nor spec §9.4 carries a non-transmission caveat.
- Runtime impact: Any app attaching metadata to `Text`/`Binary` loses it silently; receivers always observe `emptyMap()`. Also breaks sender-vs-receiver message `equals()`. | Platforms: all | User-visible: yes
- Failure class: data loss (silent)
- Proposed fix (do NOT implement): (a) encode metadata into the DATA payload behind a new flag bit (length-prefixed map before the body), mirrored across jvmMain/androidMain/appleMain and gated on `pv`; or (b) interim doc fix in KDoc + spec §9.4 stating metadata is not transmitted in v0.6 (weak — the field then serves no purpose). Decide before RC locks the wire.
- Required tests: commonTest round-trip asserting `sent.metadata == received.metadata` for Text and Binary (fails today); loopback variant.

### API-2 — `P2pSession.send()` leaks raw platform exceptions instead of the documented `P2pError.ConnectionFailed`
- Severity: High | Confidence: Confirmed (JVM and iOS write paths read; Android mirrors JVM per the lockstep rule)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt:45-54 (contract), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Errors.kt:6-13 (taxonomy claim), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:235-242 (no wrap), p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:116-137, p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt:190, 200, 208, 253, 353
- Category: bug
- Root cause: `send()` guards only the pre-write state check with `ConnectionFailed`; the actual `protocol.sendMessage → connection.write` is unwrapped. A connection dying between the state check and the write (or mid-multi-chunk write) surfaces the transport's raw exception to app code. Every neighboring caller-facing path *does* wrap (SessionManager.kt:174-180 and 396-406 for connect/handshake; FileTransferDispatcher.kt:162-168 for `sendFile`, 220-224 for `accept`) — `send()` is the one gap.
- Evidence:
  ```kotlin
  // P2pSessionImpl.kt:235-242
  override suspend fun send(message: P2pMessage) {
      if (_state.value != ConnectionState.Connected) {
          throw P2pError.ConnectionFailed("Session $id is ${_state.value}; cannot send")
      }
      sendMutex.withLock {
          protocol.sendMessage(connection, message)   // raw IOException / ISE escapes
      }
  }
  ```
  JvmRawConnection.write rethrows `IOException` (line 128) and throws `IOException("socket write timed out …")` (122-125, 135-137). IosRawConnection throws `IllegalStateException("connection closed")` (190, 208) and `NetworkException : RuntimeException` (253, 353). P2pSession.send KDoc: "Throws P2pError.ConnectionFailed if the connection has dropped." Errors.kt: "All operational failures (connect, send, handshake, transport, file transfer) are subtypes of P2pError … IllegalStateException … reserved for API misuse."
- Runtime impact: A peer dropping mid-send — the most common LAN failure — throws `java.io.IOException` (JVM/Android) or `IllegalStateException` (iOS, inverting Errors.kt's misuse-only promise for ISE) out of `send()`. Apps matching `catch (e: P2pError)` per the docs miss it; on iOS the `@Throws` bridge hands Swift an unexpected error kind. | Platforms: all, with divergent leak types per platform | User-visible: yes
- Failure class: crash (unhandled exception class) / wrong error semantics
- Proposed fix (do NOT implement): in `P2pSessionImpl.send`, catch non-`CancellationException`, non-`P2pError` throwables and rethrow `P2pError.ConnectionFailed(msg, cause)` — the exact pattern already used at SessionManager.kt:396-406. No API change.
- Required tests: commonTest with FakeRawConnection whose `write` throws a plain exception mid-send, asserting `P2pError.ConnectionFailed` reaches the caller (single- and multi-chunk sends).

### API-3 — `P2pSession.incoming` KDoc claims the flow "completes" after close; a `SharedFlow` never completes
- Severity: Medium | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt:29-33, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:131-136, 430-432
- Category: bug (doc contract)
- Root cause: `incoming` is `MutableSharedFlow(...).asSharedFlow()`; no completion mechanism exists. `transitionToTerminal` only cancels the emitter (`epochJob?.cancel()`); collectors suspend forever after close. Notably, CODEBASE_REVIEW_MAP_2026-07.md:44-45 itself states the S1 contract as "flows never complete" — the KDoc contradicts the codebase's own architectural description.
- Evidence:
  ```
  // P2pSession.kt:31-33
  * `close()` transitions the session to `Closed` … After [close], the underlying
  * connection is released and [incoming] completes.
  ```
  `private val _incoming = MutableSharedFlow<P2pMessage>(replay = 0, extraBufferCapacity = 64, onBufferOverflow = SUSPEND)` (P2pSessionImpl.kt:131-135).
- Runtime impact: App code awaiting completion (`toList()`, sequential code after `collect`, `onCompletion`-based cleanup) hangs and leaks one coroutine per closed session. Applies transitively to `incomingFiles` ("same semantics as [incoming]", P2pSession.kt:57-60). | Platforms: all | User-visible: yes (app-side hang/leak when following the doc)
- Failure class: hang / leak (induced in app code)
- Proposed fix (do NOT implement): correct the KDoc — "the flow never completes; observe [state] for terminal transitions and cancel collectors." Do not change the flow type (behavioral API change, unwarranted).
- Required tests: doc-only; the no-emissions-after-terminal invariant is already structurally guaranteed (epoch cancel).

### API-4 — Spec §7.3 still says "the caller closes [source]" — direct contradiction of the shipped `sendFile` ownership contract
- Severity: Low | Confidence: Confirmed. Related to but distinct from FIL-1 — this is the spec-side text that remediation #21 (which validated KDoc-vs-behavior only) did not touch.
- File(s): P2pKit-Spec.md:290-293 (§7.3: "The caller closes [source] after the returned transfer reaches a terminal state."), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt:75-77 ("The kit takes ownership of [source] and closes it automatically … callers must not close it themselves.")
- Category: bug (spec/doc contradiction on the locked contract)
- Root cause: v0.2.2 spec text never amended when kit-side ownership shipped (FileTransferDispatcher.kt:137-144 owns the close).
- Evidence: quoted above; behavior follows the KDoc, not the spec.
- Runtime impact: A developer following the spec double-closes (usually benign) or holds conflicting expectations; exactly the ambiguity a locked spec exists to prevent. | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: amend spec §7.3 to kit-takes-ownership wording (the spec header authorizes in-place amendment); resolve consistently with FIL-1's outcome.
- Required tests: n/a (FIL-1 owns the behavioral test).

### API-5 — `connect()` KDoc omits `TransportStartFailed` (and post-stop `IllegalStateException`) that spec and impl both deliver
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pKit.kt:157-169, P2pKit-Spec.md:228-236 (§7.2 lists TransportStartFailed for connect), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:384-385 (connect → ensureStarted), 250-296 (throws TransportStartFailed / ISE)
- Category: bug (doc)
- Root cause: the interface KDoc lists only `NoTransportAvailable` and `ConnectionFailed`, but `connect()` lazily starts the kit and therefore also throws `P2pError.TransportStartFailed` (bind failure) and `IllegalStateException` (after `stop()`).
- Evidence: `@throws P2pError.NoTransportAvailable … @throws P2pError.ConnectionFailed` (P2pKit.kt:165-166) vs `override suspend fun connect(peer: Peer): P2pSession { ensureStarted() … }`.
- Runtime impact: callers using the documented-optional lazy-start path don't know to handle TransportStartFailed at connect(). | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: add both `@throws` clauses.
- Required tests: unit asserting `connect()` on a kit whose transport start fails throws TransportStartFailed.

### API-6 — Terminal-`stop()` contract: `stop()` has no interface KDoc, and `stopAdvertising`/`stopDiscovery` silently succeed after `stop()` despite "any lifecycle call after stop() throws IllegalStateException"
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pKit.kt:180-181 (bare `stop()`), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/States.kt:15-17, P2pKit-Spec.md:244-249, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:351-355, 378-382 (no `stopped` check), 428 (second `stop()` returns silently)
- Category: bug (doc)
- Root cause: the API's strongest lifecycle claim lives only in States.kt/spec, and it overreaches — only `start`/`startAdvertising`/`startDiscovery`/`connect` pass `ensureStarted()`'s ISE gate; `stopAdvertising()`/`stopDiscovery()` (and repeat `stop()`) return normally on a stopped kit.
- Evidence: `override suspend fun stopAdvertising() { for (transport in discoveryTransports) { runCatching { transport.stopAdvertising() } } }` — no stopped check.
- Runtime impact: none harmful (silent no-op is arguably correct); docs mislead, and `stop()`'s terminality is invisible in IDE quick-doc at the call site. | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: copy terminal-semantics KDoc onto `stop()`; narrow States.kt/spec wording to "any call that would start work".
- Required tests: assert stopAdvertising-after-stop is a silent no-op (locks in intended semantics).

### API-7 — Re-entering `networkProvisioning { }` silently drops a previously registered factory
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt:110-114, 218-222
- Category: bug
- Root cause: every other repeatable DSL block seeds its sub-builder from accumulated state (`KeepAliveConfigBuilder(keepAlive)`, `LifecycleConfigBuilder(reconnectPolicy, …)`, `SecurityConfigBuilder(securityMode)`, `FileTransferConfigBuilder(fileTransfer)`), so repeated blocks are additive. `NetworkProvisioningConfigBuilder(initial)` seeds only the three booleans; `factory` restarts at `null` and line 113 unconditionally overwrites the outer field.
- Evidence:
  ```kotlin
  public fun networkProvisioning(block: NetworkProvisioningConfigBuilder.() -> Unit) {
      val b = NetworkProvisioningConfigBuilder(networkProvisioning).apply(block)
      networkProvisioning = b.toConfig()
      networkProvisioningFactory = b.factory   // null unless re-registered in THIS block
  }
  …
  internal var factory: NetworkProvisioningFactory? = null   // never seeded from previous block
  ```
- Runtime impact: `networkProvisioning { android(ctx) }` followed later by `networkProvisioning { enableWifiJoin = true }` (config helpers composing blocks) yields the Unsupported stub with no diagnostic. | Platforms: all | User-visible: yes, narrow trigger
- Failure class: none (silent feature loss)
- Proposed fix: seed the sub-builder's `factory` from the outer `networkProvisioningFactory`.
- Required tests: builder test with two blocks, factory in the first, asserting the kit's provisioning manager is not `UnsupportedNetworkProvisioningManager`.

### API-8 — Unsupported provisioning stub still reports "planned for v0.2 and not implemented in v0.1" in v0.6
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/UnsupportedNetworkProvisioningManager.kt:44-46
- Category: bug (misleading diagnostics)
- Root cause: `const val NOT_IN_V01 = "Network provisioning is planned for v0.2 and not implemented in v0.1."` is what apps see from `LocalNetworkResult.Unsupported`/`JoinNetworkResult.Unsupported` and the `createManualPeer` UnsupportedOperationException whenever they merely forgot to register a factory — provisioning shipped in v0.2.1.
- Evidence: quoted above; returned at lines 28-29, 35-36, thrown at 41-42.
- Runtime impact: developers chase a nonexistent version gap instead of adding `networkProvisioning { jvm()/android(ctx) }`. | Platforms: all | User-visible: yes
- Failure class: none (diagnostics)
- Proposed fix: reword to "no provisioning factory registered — register one via networkProvisioning { … } (platform sidecar modules), or provisioning is unavailable on this platform".
- Required tests: trivial string/type assertions on the stub.

### API-9 — `P2pState.Failed` KDoc ("carries the error that aborted startup … next lifecycle call retries through Starting") is incomplete for post-start failures
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/States.kt:10-13, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:338, 344-347, 364, 371-374
- Category: bug (doc)
- Root cause: `startAdvertising`/`startDiscovery` failures *after* a successful start also set `P2pState.Failed` (wrapping into `ConnectionFailed`, not a startup error), and the next successful call clears `Failed → Running` directly (ensureStarted's success fast-path skips `Starting`).
- Evidence: `if (_state.value is P2pState.Failed) _state.value = P2pState.Running` (P2pKitImpl.kt:338, comment cites the AUDIT-2026-06 unlatch fix).
- Runtime impact: host UIs keying on "Failed = startup failed; recovery passes Starting" mis-render the advertise-failure case. | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: extend the States.kt KDoc with the post-start Failed entry paths and the direct Failed→Running recovery.
- Required tests: assert Failed→Running (no intervening Starting) after failed-then-successful startAdvertising on a started kit.

### API-10 — `ConnectionState.Connecting`/`Handshaking`/`Idle` are never observable on `P2pSession.state`, but only `Closing` is documented as never-emitted
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/States.kt:31-35, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt:29-33, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:128, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:223-277
- Category: bug (doc)
- Root cause: sessions are constructed only after the handshake with `MutableStateFlow(ConnectionState.Connected)`; the dial/handshake window is `SessionStore.pending`, not a session object. The app-observable set on `P2pSession.state` is exactly {Connected, Reconnecting, Closed, Failed}. States.kt presents "`Connecting → Handshaking → Connected` is the happy path" and singles out only `Closing`. (`Idle`/`Connecting` etc. are legitimately used by `RawConnection.state` internally — a different, SPI-facing flow.)
- Evidence: `private val _state = MutableStateFlow(ConnectionState.Connected)` (P2pSessionImpl.kt:128).
- Runtime impact: apps rendering a "connecting…" UI state keyed to `ConnectionState.Connecting` never see it. | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: States.kt KDoc: enumerate the four observable session states; note the remaining constants currently appear only on transport-internal `RawConnection.state`. Keep the constants (SPI use + evolution headroom).
- Required tests: integration assertion collecting the state set over a connect→close cycle.

### API-13 — `NoOpP2pPermissionManager` KDoc says to plug a custom manager in "once that knob exists" — the knob exists
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/permission/NoOpP2pPermissionManager.kt:8-10, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt:73-81 (public `permissionManager` knob, fully documented)
- Category: bug (stale doc)
- Root cause / Evidence: "should plug their own implementation in via the builder once that knob exists; for v0.1 this no-op is sufficient" — predates `P2pKitBuilder.permissionManager`.
- Runtime impact: doc only. | Platforms: all | User-visible: no
- Failure class: none | Proposed fix: reference `P2pKitBuilder.permissionManager`. | Required tests: n/a.
- **C:54 assessment [CATALOGUED]:** resolved soundly on this branch as a #9 side effect. Grep confirms core no longer maps `P2pPermission.ChangeWifiState` at all (the only Android mapping left is the provisioning sidecar's `ChangeWifiState -> Manifest.permission.CHANGE_WIFI_STATE`, AndroidP2pPermissionManager.kt:67; core's `CHANGE_WIFI_MULTICAST_STATE` handling moved to the non-fatal manifest warn, PermissionManagerFactory.android.kt:54-68). The single-meaning state removes the ambiguity; deferring the new enum constant is correct — adding `ChangeWifiMulticastState` now would be speculative API with no consumer. Also verified the permission gate itself survives #9 for sidecar/custom managers (`ensurePermissions`, P2pKitImpl.kt:497-500), so P2pPermissionManager.kt:11-14's "startAdvertising/startDiscovery throw PermissionMissing" and spec §15.2 remain true.

### API-14 — Spec §9.3 `InternalPeer` shape is stale: missing `origin: PeerOrigin`
- Severity: Low | Confidence: Confirmed
- File(s): P2pKit-Spec.md:562-566 (§9.3), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/Internal.kt:17-40
- Category: bug (doc drift on a living contract)
- Root cause: commit `012e49e` added `PeerOrigin`/`InternalPeer.origin`; §9.3 — which explicitly documents this public-for-SPI type — was not amended, though the spec header requires in-place amendment of locked shapes.
- Evidence: spec shows `InternalPeer(publicPeer, transportHints)`; code adds `val origin: PeerOrigin = PeerOrigin.Discovered`.
- Runtime impact: future transport authors reading the spec miss the provenance field SessionManager's manual-peer exemption keys off. | Platforms: all | User-visible: no
- Failure class: none (doc) | Proposed fix: amend §9.3. | Required tests: n/a.

### API-16 — Config types and `sendFile` throw undocumented `IllegalArgumentException` on invalid values (and the `timeout > interval` constraint is itself undocumented)
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt:15-18 (`require(timeoutMillis > pingIntervalMillis)`), 54-57, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt:28-34, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:105 (`require(sizeBytes >= 0)` behind `P2pSession.sendFile`), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Errors.kt:10-13 (taxonomy names only ISE/UOE)
- Category: bug (doc completeness; the validation itself is good)
- Root cause: `require(...)` throws IAE out of `P2pKit.create` and `sendFile`; Errors.kt's non-P2pError taxonomy omits IAE, and the KeepAlive relationship constraint (stricter than the spec, which shows no validation) is stated only in the exception message.
- Evidence: `P2pKit.create { keepAlive { pingIntervalMillis = 10_000; timeoutMillis = 5_000 } }` throws undocumented IAE; `session.sendFile(name, -1, …)` likewise.
- Runtime impact: doc-level; first-run construction crashes are self-explanatory but off-taxonomy. | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: add IAE to the Errors.kt taxonomy note; document the `timeoutMillis > pingIntervalMillis` requirement and `sizeBytes >= 0` in their KDocs.
- Required tests: validation boundary tests for the three config types and negative sizeBytes.

### API-17 — Blank-value `require` on `PeerId`/`AppId` is a throw-hazard for network-supplied strings the KDoc doesn't flag
- Severity: Low | Confidence: Confirmed as a contract gap; the risky call sites are transport-side (outside this scope) and flagged for those reviewers
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt:12-31
- Category: bug (defensive gap at the API boundary)
- Root cause: `PeerId("")`/`AppId("")` throw IAE, and these types are constructed from network-controlled input (HELLO peerId; mDNS TXT `pid`/`app`) inside transport parse paths. HELLO is safe (`runCatching { HelloPayload.decode(...) }`, DefaultP2pProtocol.kt:154-157); the discovery TXT parse paths on the three platforms must each guard, and nothing in the type's contract warns implementers.
- Evidence: `init { require(value.isNotBlank()) { "PeerId must not be blank" } }`.
- Runtime impact: worst case, a malformed advertisement throws inside a discovery event flow — platform-dependent. | Platforms: all (exposure depends on transport code) | User-visible: potential
- Failure class: resource-limit (narrow) / none if all call sites guard
- Proposed fix: KDoc note on both value classes ("constructor throws on blank — network parsers must pre-validate"), or an internal `orNull` factory for parser use.
- Required tests: transport-side malformed-TXT tests (blank `pid`/`app`) asserting the advertiser is skipped without killing discovery.

### API-18 — `registerManualPeer` / `createManualPeer` throw undocumented `IllegalArgumentException` on bad host/port
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/ManualPeerRegistrar.kt:26-42 (no throws doc), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/NetworkProvisioningTypes.kt:40-42 (createManualPeer, ditto), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:115-116
- Category: bug (doc)
- Root cause: `require(host.isNotBlank())` / `require(port in 1..65_535)` added (correctly) in PeerRegistry; the public KDocs don't declare the throw. Manual-IP is precisely the user-typed-input flow, so the IAE path is the expected path for typos.
- Evidence: quoted above.
- Runtime impact: uncaught IAE from a user-input flow in apps that followed the docs. | Platforms: all | User-visible: yes (narrow)
- Failure class: crash (app-side, narrow)
- Proposed fix: `@throws IllegalArgumentException` on both KDocs.
- Required tests: IAE assertions for blank host / port 0 / port 70000.

### API-19 — Offer-timeout terminal state is asymmetric and mislabeled: receiver shows `Rejected("timeout")`, sender shows `Cancelled("offer not accepted within …ms")`, while `Cancelled`'s KDoc claims timeouts land in `Cancelled`
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferState.kt:34 ("Either side cancelled mid-transfer, or the offer auto-rejected on timeout"), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/P2pFileOffer.kt:12-14 and P2pSession.kt:62-64 ("auto-rejected with reason \"timeout\""), p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:590-613 (sender timer → `Cancelled("offer not accepted within ${…}ms")`), 615-635 (receiver timer → `Rejected("timeout")` + FILE_REJECT "timeout")
- Category: bug (doc)
- Root cause: both sides run independent `offerTimeoutMillis` timers. The receiver's produces `Rejected("timeout")`; the sender's produces `Cancelled(...)` with a different reason string, and because both default to 30 s the sender's local timer usually beats the receiver's FILE_REJECT by the network RTT — so the sender effectively never observes `Rejected("timeout")`. Each KDoc describes one side without saying which: `Cancelled` claims timeout membership (sender-side reality), the offer docs promise reason "timeout" (receiver-side reality).
- Evidence: quoted line refs above.
- Runtime impact: sender-side apps distinguishing "peer declined" from "peer ignored" via `Rejected("timeout")` misclassify timeouts; reason strings differ across sides for one logical event. | Platforms: all | User-visible: yes (state-labeling only; transfer outcome correct)
- Failure class: none (semantics/diagnostics)
- Proposed fix: document per-side outcomes on `Cancelled`/`Rejected` and in P2pFileOffer/P2pSession (or align the sender's local-timeout state to `Rejected("timeout")` — behavioral change, needs a decision).
- Required tests: FileTransferFlowTest case asserting the sender/receiver terminal-state pair on an unanswered offer.

### API-20 — `P2pFileOffer.accept` KDoc documents only `IllegalStateException`; it also throws `P2pError.ConnectionFailed`
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/P2pFileOffer.kt:33-43, p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:214-225
- Category: bug (doc)
- Root cause: when the FILE_ACCEPT write fails, `acceptOffer` (correctly) wraps into `P2pError.ConnectionFailed("FILE_ACCEPT write failed: …")`, marks the transfer Failed, and rethrows; the KDoc lists only the already-answered ISE case.
- Evidence: `val err = if (e is P2pError) e else P2pError.ConnectionFailed("FILE_ACCEPT write failed: ${e.message}") … throw err` (FileTransferDispatcher.kt:221-224).
- Runtime impact: doc-level; ConnectionFailed is the right type — it just isn't declared. | Platforms: all | User-visible: doc-level
- Failure class: none (doc)
- Proposed fix: add `@throws P2pError.ConnectionFailed` to `accept`.
- Required tests: accept-with-dead-connection assertion (typed error + transfer Failed).

## 2b. Likely duplicates of already-confirmed findings (one-liners)

- [LIKELY-DUP FIL-1] P2pSession.kt:75-77 / P2pFileTransfer.kt:14-18 ownership text ("resources are released" at terminal) is undermined by the source-close watcher (FileTransferDispatcher.kt:141-144) living on the session scope that `close()`/`kit.stop()` cancels → source leak; the spec-side contradiction is reported separately as API-4.
- [LIKELY-DUP SES-1] Spec §16.3 "session emits Failed immediately [then] enters Reconnecting" contradicts the implementation (Connected → Reconnecting directly, P2pSessionImpl.kt:644-664); my scope files (Config.kt:29-52, NetworkPath.kt:41-49) describe the *implemented* semantics correctly — the defect is spec-side.
- [LIKELY-DUP DSC-1] DiscoveryTransport.kt/Internal.kt present `PeerEvent.Updated` as a normal cross-platform event; only iOS emits it — parity divergence owned by the discovery section.
- [LIKELY-DUP FIL-2] Sender-side source read failure sends no FILE_CANCEL (receiver hangs) — dispatcher-side; noted because P2pFileTransfer.kt:43-46 "both sides transition to Cancelled" reads as if failure signalling were symmetric.

## 2c. Findings — improvements

### API-11 — `securityMode` and `appKilledPolicy` are accepted by the DSL but provably inert; `SecurityManager` is public yet not injectable
- Category: improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:66-67 (`@Suppress("unused") private val appKilledPolicy / securityMode`), 96 (`private val security: SecurityManager = NoOpSecurityManager()` hardcoded), dsl/Builders.kt:105-108, 193-194, security/SecurityManager.kt
- Evidence: both fields are marked `@Suppress("unused")`; the DSL `security { mode = … }` value is threaded to the constructor and never read; `SecurityManager`/`SecureConnection` are public (spec §18: "the extension point"), but no builder knob exists to supply an implementation — the extension point is currently unreachable from app code. Each sealed type has exactly one variant today, so no behavioral lie exists — this is future-proofing surface carried as dead weight.
- Suggested action: either wire `securityMode` through to manager selection when a second mode ships (and note in KDoc that `security { }` is currently a forward-compat no-op), or drop the `@Suppress` in favor of a comment explaining the plan. No API change needed now.

### API-12 — `deviceName` is unvalidated at build time (blank or oversized names fail later, opaquely)
- Category: improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt:40-41, 125-127
- Evidence: `build()` only null-checks `deviceName`; `""` (or a multi-hundred-byte name) passes and flows into TXT records (`name` key, URL-encoded — DNS TXT strings cap at 255 bytes) and HELLO. `AppId` gets `isNotBlank` validation via its value class; `deviceName` gets none.
- Suggested action: `require(deviceName.isNotBlank())` and a documented length bound (e.g. ≤ 63 bytes URL-encoded) at build(), failing fast with a clear message instead of a platform-dependent advertise failure.

### API-15 — SPI contracts omit obligations core relies on: close idempotency and connect/startAdvertising error handling
- Category: improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/DataTransport.kt:53 (`close()` undocumented), transport/RawConnection.kt:28, transport/DiscoveryTransport.kt:18-21; relied on at p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:288-295 ("transport close() is idempotent for the ones stop() already closed" — the stop-hang fallback can close transports twice) and 481-488
- Evidence: the stop-hang fix's lock-less fallback explicitly depends on idempotent `DataTransport.close()`, and `P2pSessionImpl.transitionToTerminal`/rearm depend on idempotent `RawConnection.close()` — obligations stated nowhere in the SPI KDocs (the shipped implementations satisfy them via CAS guards, but a third-party transport author has no way to know). Similarly `connect()`/`startAdvertising()` KDocs don't say what implementations may throw (core wraps everything — worth stating so SPI authors don't invent their own wrapping).
- Suggested action: add "must be idempotent; may be called concurrently with/after other calls" to both `close()` KDocs, and "may throw anything; the kit wraps into typed P2pError" to `connect`/`startAdvertising`/`startDiscovery`.

### API-21 — Doc nits: unresolved/misleading KDoc references
- Category: improvement | Confidence: Confirmed
- File(s)/Evidence:
  - Peer.kt:8 — `the peers [StateFlow]` has no import/qualifier → unresolved Dokka link.
  - P2pKit.kt:62 — public KDoc links `dev.p2pkit.core.internal.PeerIdStorage` (internal type; unresolvable for consumers).
  - NetworkPath.kt:40, 66-68 — commonMain KDoc references `[AndroidNetworkPathObserver]` (androidMain-only class; unresolvable from common docs).
  - NetworkProvisioningTypes.kt:128-129 — "Carries host/port — the only public type that does so" ignores the public SPI `TransportHint` (Internal.kt:48-53); qualify as "only app-facing type".
- Suggested action: qualify or drop the links; one Dokka run would surface all of these.

### API-22 — `ProvisioningContext` exposes the experimental `ManualPeerRegistrar` via `@OptIn` instead of propagating `@ExperimentalP2pApi`
- Category: improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/NetworkProvisioningFactory.kt:51-59
- Evidence: `@OptIn(ExperimentalP2pApi::class) public class ProvisioningContext(… public val manualPeerRegistrar: ManualPeerRegistrar …)` — `@OptIn` silences the "experimental type in stable signature" diagnostic rather than propagating it, so holding a `ManualPeerRegistrar` obtained from the context carries no opt-in signal (calling its members still warns, so the leak is partial). Kotlin's guidance is to propagate the marker on API that exposes experimental types.
- Suggested action: annotate the property (or the class) `@ExperimentalP2pApi` instead of `@OptIn`; sidecar modules already opt in.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| `send()` on a failing connection surfaces `P2pError.ConnectionFailed`, never raw IOException/ISE | API-2 — the documented typed-error contract for the hottest API call | p2p-core commonTest (SessionFlowTest or new SendErrorContractTest, FakeRawConnection with throwing `write`) | unit | P1 |
| `P2pMessage.metadata` round-trips sender→receiver | API-1 — silent data loss; test documents/locks whichever fix is chosen | p2p-core commonTest protocol (Chunker/Reassembler round-trip) | unit | P1 |
| Builder/config validation: IAE for bad keepAlive/reconnect/fileTransfer values, missing appId/deviceName/transport errors, repeated-DSL-block semantics incl. factory persistence (API-7) | DSL is every consumer's entry point; zero dedicated tests today | p2p-core commonTest (new P2pKitBuilderTest) | unit | P2 |
| Sender/receiver terminal-state pair for an unanswered file offer (Cancelled vs Rejected("timeout")) | API-19 — cross-side semantics currently unpinned | FileTransferFlowTest | unit | P2 |
| `accept()` after timeout/answer throws ISE; `accept()` on dead connection throws ConnectionFailed and fails the transfer | API-20 + P2pFileOffer contract | FileTransferFlowTest | unit | P2 |
| Zero-byte file transfer completes on both sides (no Sending emission, Completed reached) | Boundary of the progress contract (guards at OutgoingFileTransferImpl.kt:54, IncomingFileSession.kt:69 are untested) | FileTransferFlowTest | unit | P2 |
| `connect()` surfaces TransportStartFailed when lazy start fails | API-5 / spec §7.2 | KitLifecycleTest | unit | P2 |
| Post-stop semantics: start/connect throw ISE; stopAdvertising/stopDiscovery no-op | API-6 — pins the intended terminal contract | KitLifecycleTest | unit | P3 |
| Kit `Failed → Running` recovery path without `Starting` after post-start advertise failure | API-9 | KitLifecycleTest | unit | P3 |
| Observable session-state set over connect→close is exactly {Connected, Closed} (+Reconnecting/Failed in failure runs) | API-10 — prevents accidental future emission of half-supported states | SessionFlowTest | unit | P3 |

## 4. Section summary

**What S1 owns:** the locked app-facing contract (kit, session, messages, files, errors, states, DSL) plus the public-but-documented-internal transport/provisioning SPI and the Android context holder.

**Overall health:** structurally strong. Shape conformance against `P2pKit-Spec.md` is near-exact (every §7/§9/§15/§18/§20 type present with matching signatures; TransportManager, handshake errors, permission gate, path-observer defaults, `lanTcpPort` provider, manual-peer dedup all verified against their implementations). The 2026-07 remediation fixes hold up in the API layer (permission gate correctly narrowed, not removed; PeerOrigin provenance clean; C:54 genuinely resolved). The defects are concentrated in **contract truthfulness**, not shape: two High findings where the wire/impl can't deliver what the API sells (metadata, typed send errors), and a cluster of doc/spec drift that will confuse RC adopters.

**Top 3 risks:**
1. **API-1** — `P2pMessage.metadata` silently dropped; must be resolved (wire encoding or explicit de-scoping) *before* the RC locks the frame format.
2. **API-2** — `send()` leaking raw, per-platform-divergent exception types breaks the "all operational failures are P2pError" pillar exactly where apps are most likely to hit it.
3. **Doc/spec drift cluster** (API-3/4/5/6/9/10/14 + spec-side SES-1) — individually Low, collectively they erode the spec's authority as the locked contract at the moment external consumers start reading it.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy for S1:** accurate overall (file inventory, "public-but-documented-internal" SPI framing, "no dedicated contract tests", Medium-risk/spec-drift hazard — all confirmed; the spec-drift warning proved prescient). Two nits: (a) the map's own contract summary "flows never complete" (line 44-45) is contradicted by P2pSession.kt's KDoc — the map is right, the KDoc is wrong (API-3); (b) "Depends on: nothing internal" is not literally true — `dsl/Builders.kt` imports `internal.PeerIdStorage`/`internal.newP2pKit` (Builders.kt:12-13) and P2pKit.kt's companion delegates to the internal impl; immaterial for review sequencing.

## Out-of-scope observations

- p2p-transport-lan/src/appleMain/.../IosRawConnection.kt:190, 208, 353 — connection-drop surfaces as `IllegalStateException`/`NetworkException` where JVM/Android throw `IOException` for the same condition; platform parity gap independent of (and masked by) the API-2 wrapping fix.
- p2p-core/src/commonMain/.../internal/FileTransferDispatcher.kt:378 — inbound offers are emitted via `scope.launch { _incomingOffers.emit(...) }`; two offers in quick succession may reach `incomingFiles` out of arrival order (separate unordered launches). Cosmetic today; belongs to the file-transfer section.
- p2p-core/src/commonMain/.../internal/FileTransferDispatcher.kt:226-227 — stale comment: "For zero-byte files we may transition to Sending(1.0) on the first FILE_DONE; that's handled in onFileDone" — onFileDone contains no such handling (it sets Completed directly); harmless but misleading.
- p2p-core/src/commonMain/.../internal/PeerRegistry.kt:162-164 — `evictLoop` swallows non-cancellation throwables with an empty catch and a "No logger here by design" comment even though a `logger` could be threaded in; a chronically failing eviction pass would be invisible. Belongs to S4.
