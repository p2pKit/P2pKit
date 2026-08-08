# A15-PERF — Cross-cutting performance & efficiency review (runtime hot paths)

Scope: protocol hot path (`p2p-core/.../protocol/`), session/registry hot path
(`p2p-core/.../internal/`), and the three platform transport hot paths in
`p2p-transport-lan`. Lens: allocations, copies, latency, lock hold times,
dispatcher usage, timer cadences, log-work-when-disabled, per-event complexity.
All paths relative to repo root. Findings attach to the owning tracker
sections (column "Owner"). I own no tracker rows.

Baseline for arithmetic used throughout: default chunk = 64 KiB
(`ProtocolConstants.DEFAULT_CHUNK_SIZE`, `FileTransferConfig.chunkSizeBytes`);
a 5 MiB file ≈ 80 FILE_DATA chunks; a 4 MiB message = 64 DATA chunks; JVM/Android
socket read buffer = 8 KiB (`JvmRawConnection.BUFFER_SIZE`); iOS receive
request = 64 KiB (`RECEIVE_MAX_LENGTH`); keep-alive default PING every 10 s
(`KeepAliveConfig`); registry eviction poll 1 s; iOS re-announce 5 s; reconnect
periodic refresh ~3 s ± 0.4 s per reconnecting session.

## 1. Per-file verdicts

| File | Lines | Verdict | Owner section | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|---|
| p2p-core/.../protocol/FrameCodec.kt | 126 | improvements: PERF-1, PERF-2 | S6 | FrameCodecTest | No allocation/copy-count characterization; correctness well covered |
| p2p-core/.../protocol/Frame.kt | 112 | improvements: PERF-1 (minor: `fromCode` linear scan) | S6 | FrameCodecTest (indirect) | none needed beyond PERF-1 note |
| p2p-core/.../protocol/FrameReader.kt | 86 | findings: PERF-9; improvements: PERF-1 | S6 | FrameReaderTest | No test for pathological feed patterns (large frame in small feeds; many frames per feed) |
| p2p-core/.../protocol/FrameTrace.kt | 38 | clean (exemplary: inline lambda, zero cost when disabled) | S6 | sample usage only | none |
| p2p-core/.../protocol/Chunker.kt | 75 | improvements: PERF-2 | S6 | ChunkerTest | No test pinning single-frame zero-copy behavior (payload identity) |
| p2p-core/.../protocol/Reassembler.kt | 185 | clean (new remediation code reviewed fresh; efficiency is fine — see notes) | S6 | ReassemblerTest (incl. new cap/eviction tests) | none for efficiency |
| p2p-core/.../protocol/ProtocolConstants.kt | 64 | clean | S6 | indirectly by all protocol tests | none |
| p2p-core/.../protocol/DefaultP2pProtocol.kt | 219 | improvements: PERF-2, PERF-6 (send loop is the mutex-hold body) | S6 | DefaultP2pProtocolTest, FileTransferProtocolTest | No test that PING/PONG latency is bounded while a large send is in flight |
| p2p-core/.../protocol/StreamingFileSender.kt | 55 | improvements: PERF-2 (one fresh 64 KiB array per chunk; no read-ahead) | S8 | StreamingFileSenderTest | none for efficiency |
| p2p-core/.../protocol/StreamingFileReceiver.kt | 94 | clean (single sink copy per chunk; memory statement in KDoc is accurate) | S8 | StreamingFileReceiverTest | none |
| p2p-core/.../protocol/HelloPayload.kt | 59 | clean (JSON en/decode is handshake-only, not hot) | S6 | HelloPayloadTest | none |
| p2p-core/.../protocol/FileOfferPayload.kt | 54 | clean | S6/S8 | FileOfferPayloadTest | none |
| p2p-core/.../protocol/P2pProtocol.kt | 46 | clean (interface) | S6 | n/a | none |
| p2p-core/.../protocol/ProtocolEvent.kt | 36 | clean (FileData hands over the Frame without copy — good) | S6 | n/a | none |
| p2p-core/.../internal/P2pSessionImpl.kt | 717 | improvements: PERF-5, PERF-6 | S3 | SessionFlowTest, KeepAliveTest, CloseSemanticsTest, ReconnectPolicyTest | No combination test: keep-alive/PONG responsiveness during a concurrent multi-chunk send |
| p2p-core/.../internal/SessionManager.kt | 789 | improvements: PERF-7 | S3 | SessionFlowTest, SimultaneousOpenTest, SessionReconnectRotationTest, NetworkPathRecoveryTest | No test of refresh cadence with K>1 concurrently-reconnecting sessions |
| p2p-core/.../internal/SessionStore.kt | 333 | improvements: PERF-5 (registrationOf is the per-message body) | S3 | SessionStoreInvariantTest, SimultaneousOpenTest | none beyond PERF-5 |
| p2p-core/.../internal/PeerRegistry.kt | 187 | improvements: PERF-8 [CATALOGUED ext.] | S4 | PeerRegistryTest | No test that heartbeat-only Updated events do not re-emit `peers` (behavior exists, untested) |
| p2p-core/.../internal/FileTransferDispatcher.kt | 645 | clean for efficiency (per-chunk mutex acquisition is the right pattern; one lock lookup + one StateFlow update per chunk) | S8 | FileTransferFlowTest, FileTransferErrorIsolationTest | none for efficiency |
| p2p-core/.../internal/TransportManager.kt | 33 | clean (sort of a 1-element list per connect; negligible) | S7 | TransportManagerTest | none |
| p2p-core/.../internal/Handshake.kt | 89 | clean (read for call-site verification) | S3 | HandshakeTest, HandshakeIdentityTest | none |
| p2p-core/.../internal/OutgoingFileTransferImpl.kt | 79 | clean (CAS progress update; one small `Sending` alloc per chunk — negligible) | S8 | FileTransferFlowTest | none |
| p2p-core/.../internal/IncomingFileSession.kt | 86 | clean (same as above) | S8 | FileTransferFlowTest | none |
| p2p-core/.../internal/P2pKitImpl.kt (wiring sections read) | ~130 of 400+ | improvements: PERF-7 (refresh fan-out wiring) | S2 | KitLifecycleTest | covered by PERF-7 gap |
| p2p-transport-lan/src/jvmMain/.../JvmRawConnection.kt | 208 | improvements: PERF-1, PERF-3, PERF-4 | S7 | JvmLanLoopbackTest (functional, incl. 5 MiB SHA-256 file) | Loopback test asserts correctness only; no throughput/allocation guardrail |
| p2p-transport-lan/src/jvmMain/.../JvmLanDataTransport.kt | 181 | clean for efficiency (dial-path log strings eager but dial-rate only) | S7 | JvmLanLoopbackTest | none |
| p2p-transport-lan/src/jvmMain/.../JvmLanDiscoveryTransport.kt | 361 | improvements: PERF-7, PERF-4 (minor) | S5 | JvmLanLoopbackTest, HostSelectorTest | No test of refresh() cost/behavior under repeated 3 s cadence |
| p2p-transport-lan/src/jvmMain/.../JvmLanDiag.kt | 100 | improvements: PERF-4 (gate is inside the callee; args evaluated at call sites) | S5/S7 | none | none (diagnostics) |
| p2p-transport-lan/src/androidMain/.../AndroidRawConnection.kt | 207 | improvements: PERF-1, PERF-3, PERF-4 | S7 | none (no instrumented tests — known) | Manual-only coverage (INTERNAL_TESTING.md); parity with JVM pinned by review only |
| p2p-transport-lan/src/androidMain/.../AndroidLanDataTransport.kt | 173 | clean for efficiency | S7 | none (manual) | same as above |
| p2p-transport-lan/src/androidMain/.../AndroidLanDiscoveryTransport.kt | 1031 | improvements: PERF-7, PERF-4 (ungated `Log.d` on discovery/refresh cadence) | S5 | none (manual) | No host-side test of rebind/refresh cadence cost |
| p2p-transport-lan/src/androidMain/.../AndroidLanDiag.kt | 80 | improvements: PERF-4 | S5/S7 | none | none |
| p2p-transport-lan/src/appleMain/.../IosRawConnection.kt | 383 | improvements: PERF-1 (iOS variant), PERF-4 (worst platform: per-write log with no gate) | S7 | IosRawConnectionTest, IosLanLoopbackTest | No perf characterization; functional only |
| p2p-transport-lan/src/appleMain/.../IosLanDataTransport.kt | 766 | improvements: PERF-10, PERF-4 | S7 | IosLanLifecycleTest, IosLanLoopbackTest | No test that rebind does not stall other Default-dispatcher work |
| p2p-transport-lan/src/appleMain/.../IosLanDiscoveryTransport.kt | 783 | improvements: PERF-8 [CATALOGUED ext.], PERF-7, PERF-4 | S5 | AnnounceCacheReconcileTest, IosLanLifecycleTest | Announce-loop cost at N peers untested (pure fn is tested; loop cadence is not) |
| p2p-transport-lan/src/appleMain/.../IosLanDebug.kt | 75 | improvements: PERF-4 (no master gate; only the println mirror is gated) | S5/S7 | none | none |
| p2p-transport-lan/src/appleMain/.../IosBonjour.kt | 97 | clean (TXT round-trip per browse event only) | S5 | IosBonjourTest | none |
| p2p-transport-lan/src/appleMain/.../IosEndpointRegistry.kt | 42 | clean (copy-on-write map; peer-count scale) | S5 | via loopback tests | none |
| Reference files read for call-site verification: P2pLogger.kt, P2pMessage.kt, FileTransferConfig.kt, RawConnection.kt, Config.kt | — | clean (context only) | — | — | — |

## Data-path copy-count summary

"Copy" = a user-space byte-array copy of the payload bytes (kernel↔user
transfers not counted). Single-frame = message ≤ 64 KiB.

**send(message) → socket**

| Platform | Single-frame message | Multi-chunk message (per byte) | Where |
|---|---|---|---|
| JVM / Android | **1** (encode) — Chunker passes the caller's array by reference (`Chunker.kt:39-50`) | **2** — chunk slice (`Chunker.kt:64`) + encode header+payload (`FrameCodec.kt:46`) | then `OutputStream.write` direct |
| iOS | **2** (encode + dispatch_data) | **3** — chunk slice + encode + `dispatch_data_create` copy (`IosRawConnection.kt` KDoc "copies by default", :234-260) | |

Text messages add one copy (`encodeToByteArray`). `sendFile` per chunk: source
read allocates a fresh payload array (`StreamingFileSender.kt:40`) + encode
(+ dispatch_data on iOS) → 2 copies JVM/Android, 3 iOS.

**socket → incoming flow / file sink** (per delivered 64 KiB chunk)

| Platform | Copies | Where |
|---|---|---|
| JVM / Android | **5** (+ append amplification ≈ ×4.5) | per-read `buffer.copyOfRange` (`JvmRawConnection.kt:166`) → FrameReader append into fresh combined array (`FrameReader.kt:40-43`) → `frameBytes` slice (`FrameReader.kt:68`) → payload slice (`FrameCodec.kt:109`) → Reassembler combine (`Reassembler.kt:155`) or file-sink segment copy (`StreamingFileReceiver.kt:62`). With 8 KiB reads a 64 KiB frame takes ~8 feeds, and each feed re-copies the whole partial frame: ~288 KiB of extra memcpy per 64 KiB frame. |
| iOS | **5** (append amplification ≈ ×1–2) | `readBytes` from dispatch buffer (`IosRawConnection.kt:294`) → same FrameReader/decode/reassemble chain; 64 KiB receives roughly align with frame size, so far fewer feeds per frame. |

Net effect on JVM/Android: ≈ 8–9× total memcpy amplification and roughly
0.5 MB of short-lived garbage per 64 KiB delivered (~40 MB transient
allocations per 5 MiB file). Correct, and LAN throughput is still achieved in
the loopback test — but it is measurable CPU + GC pressure, most relevant on
Android.

## 2. Findings

### PERF-1 — Receive path: 5-copy chain, 8 KiB read buffer, and per-read dispatcher hops (JVM/Android; iOS shares the copy chain)
- Severity: Improvement | Confidence: Confirmed (code arithmetic; see copy table above)
- File(s): p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt:151-176, :192; androidMain/.../AndroidRawConnection.kt:149-175, :191; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameReader.kt:37-79; FrameCodec.kt:109; Frame.kt:72
- Category: improvement
- Root cause: every stage of the inbound pipeline materializes its own array:
  per-read `copyOfRange`, append-into-new-buffer, whole-frame slice, payload
  slice, reassembly/sink copy. The JVM/Android read buffer (8 KiB) is 1/8 of
  the frame size, so each 64 KiB frame is fed in ~8 pieces and the growing
  partial frame is re-copied on every feed. Each read also does its own
  `withContext(Dispatchers.IO)` round trip (2 dispatcher hops per 8 KiB → ~1280
  hops per 5 MiB file).
- Evidence:
  ```kotlin
  // JvmRawConnection.kt:151,154,166
  val buffer = ByteArray(BUFFER_SIZE)            // 8 * 1024
  withContext(Dispatchers.IO) { input.read(buffer) }
  emit(buffer.copyOfRange(0, n))                 // fresh array per read
  // FrameReader.kt:40-43 — whole-buffer copy on every feed
  val combined = ByteArray(buffer.size + bytes.size)
  buffer.copyInto(combined, 0); bytes.copyInto(combined, buffer.size)
  // FrameReader.kt:68 + FrameCodec.kt:109 — two more slices per frame
  val frameBytes = buffer.copyOfRange(0, frameSize)
  val payload = bytes.copyOfRange(ProtocolConstants.HEADER_SIZE, frameEnd)
  ```
  Minor per-frame allocations ride along: `PacketType.fromCode` iterates
  `entries` with `firstOrNull` per frame (Frame.kt:72), `MessageId` slice per
  frame (FrameCodec.kt:80), `mutableListOf<Frame>()` per feed (FrameReader.kt:46).
- Runtime impact: ~8–9× memcpy amplification and ~10 short-lived allocations
  per 64 KiB chunk on JVM/Android (GC churn on Android is the practical cost);
  iOS pays the 5-copy chain with little append amplification. No correctness
  impact. | Platforms: all (worst on JVM/Android) | User-visible: no (CPU/GC
  headroom only, at LAN rates)
- Failure class: none
- Proposed fix (do NOT implement): (1) raise `BUFFER_SIZE` to 64 KiB to match
  the chunk size (parity with iOS `RECEIVE_MAX_LENGTH`; one-line change per
  platform, removes most append amplification); (2) restructure `FrameReader`
  to consume via a read offset instead of `copyOfRange` tail compaction, and
  decode the payload directly out of the shared buffer (merges the frameBytes
  + payload slices into one copy); (3) replace the per-read `withContext(IO)`
  pair with `flow { … }.flowOn(Dispatchers.IO)`; (4) table-lookup for
  `PacketType.fromCode`. Keep the wire format untouched.
- Required tests: existing FrameReaderTest suite must stay green over the
  refactor (split-boundary feeds, multi-frame feeds, unknown-type skip);
  loopback 5 MiB SHA-256 test as the end-to-end guard.

### PERF-2 — Send path: full-message materialization in Chunker + one encode copy per frame
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/.../protocol/Chunker.kt:53-66; DefaultP2pProtocol.kt:22-27, :102-105; FrameCodec.kt:31-48; StreamingFileSender.kt:40
- Category: improvement
- Root cause: `sendMessage` calls `chunker.chunk(message)` which eagerly builds
  the complete `List<Frame>` — for a 4 MiB message that is 64 × 64 KiB payload
  slices, i.e. a second full copy of the message resident before the first
  byte is written. Each frame is then encoded into yet another
  header+payload array. Peak transient memory per large send ≈ 2× message
  size + one frame. The single-frame path (≤ 64 KiB) is already zero-copy in
  the chunker — good.
- Evidence:
  ```kotlin
  // Chunker.kt:54-66 — eager list of payload copies
  return (0 until total).map { i -> ... payload = bytes.copyOfRange(start, end) }
  // DefaultP2pProtocol.kt:23-26
  val frames = chunker.chunk(message)
  for (frame in frames) { writeFrame(connection, frame) }
  ```
  File sends avoid the materialization (streamed one chunk at a time) but
  still allocate a fresh payload per chunk (`source.readByteArray(want)`) and
  a fresh encode buffer per frame; chunk N+1 is only read after chunk N's
  write returns (no single-chunk read-ahead to overlap disk and network).
- Runtime impact: 2× transient memory on large `send()` calls; steady per-chunk
  allocation on file sends. | Platforms: all | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): make `chunk` return a `Sequence<Frame>` (or
  chunk inside the write loop) so only one chunk copy is live at a time;
  optionally encode into a per-connection reusable buffer (the write is
  serialized by `sendMutex`, so one scratch buffer per session is safe).
  Optional: one-chunk read-ahead in `streamOutgoingPayload` to overlap source
  I/O with socket I/O.
- Required tests: ChunkerTest green over the signature change (internal API);
  loopback text/binary/file tests as end-to-end guards.

### PERF-3 — One watchdog coroutine launched and cancelled per write() (JVM + Android)
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-transport-lan/src/jvmMain/.../JvmRawConnection.kt:96-107, :144; androidMain/.../AndroidRawConnection.kt:96-107, :144
- Category: improvement
- Root cause: the (correct, audit-mandated) write watchdog is implemented as a
  fresh `connScope.launch { delay(30s) … }` + `AtomicInteger` per `write()`
  call, cancelled in `finally`. Every frame — each 64 KiB chunk, every PING —
  pays a coroutine launch, a timed-task schedule/cancel on `Dispatchers.Default`,
  and two atomics.
- Evidence:
  ```kotlin
  // JvmRawConnection.kt:96-98 (identical in AndroidRawConnection)
  val writeState = AtomicInteger(WRITE_INFLIGHT)
  val watchdog = connScope.launch { delay(WRITE_TIMEOUT_MILLIS); ... }
  ...
  finally { watchdog.cancel() }
  ```
- Runtime impact: ~80 launch/cancel cycles per 5 MiB file plus one per
  keep-alive frame; individually sub-microsecond, collectively avoidable
  scheduler churn on the shared Default pool. | Platforms: JVM, Android |
  User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): a single long-lived watchdog coroutine per
  connection polling a volatile `writeDeadline` (set on write entry, cleared on
  exit) at coarse granularity (e.g. 1 s), or a reusable deadline reset instead
  of launch/cancel. Must preserve the exact CAS semantics the audit fix
  established (INFLIGHT → DONE | TIMED_OUT) and JVM↔Android parity.
- Required tests: `CloseSemanticsTest` (wedged write → close returns) and
  `JvmLanLoopbackTest` unchanged and green.

### PERF-4 — Diagnostic-trace string work performed when tracing is disabled; iOS has no master gate at all
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-transport-lan/src/appleMain/.../IosLanDebug.kt:58-63; IosRawConnection.kt:219 (per-write), :189-211; jvmMain/.../JvmLanDiag.kt:58-69 with call sites JvmRawConnection.kt:111, :165; androidMain/.../AndroidLanDiag.kt:38-40 with call sites AndroidRawConnection.kt:111, :164; androidMain/.../AndroidLanDiscoveryTransport.kt (ungated `Log.d` throughout, e.g. :332-402 refresh path, :527-583 per browse result)
- Category: improvement
- Root cause: three related shapes, worst first.
  1. **iOS — no gate:** `IosLanDebug.log()` unconditionally builds an `NSDate`,
     a timestamp, and the full line string, then `tryEmit`s into a
     200-replay SharedFlow — for every transport event **including one per
     `write()` call** (`IosRawConnection.kt:219`
     `IosLanDebug.log("conn", "write(${bytes.size}): nw_connection_send")`).
     The AUDIT-2026-06 fix gated only the `println` mirror
     (`mirrorToConsole`, IosLanDebug.kt:74); the string-build + SharedFlow
     emission still run in every release build, per frame, inside the
     write lock.
  2. **JVM/Android — eager argument evaluation:** `JvmLanDiag.frame(...)` /
     `AndroidLanDiag.frame(...)` check their flags *inside* the callee, so the
     interpolated message (`"$label ${bytes.size}B"`) is built at the call
     site on every read (~640 per 5 MiB at 8 KiB reads) and every write, even
     with tracing off (default).
  3. **Android — ungated `Log.d`:** the discovery transport logs directly via
     `Log.d` (not `AndroidLanDiag.frame`) on every browse result, every
     refresh tick (2 + n lines per ~3 s tick per reconnecting session), and
     every connection lifecycle event. `Log.d` formats and writes to the
     logcat buffer unconditionally.
  In-repo precedent for the right pattern: `FrameTrace.emit` is `inline` with
  a `() -> String` lambda evaluated only when enabled (FrameTrace.kt:35-37) —
  zero cost when off.
- Runtime impact: per-frame allocations on the hottest paths for a
  diagnostics feature that is documented as default-off; on iOS additionally
  an NSDate + SharedFlow synchronization per frame write. Absolute cost is
  small at LAN rates (μs per frame) but it is pure waste and contradicts the
  "consumer sees nothing and pays nothing" contract FrameTrace documents. |
  Platforms: all (iOS worst) | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): give `IosLanDebug` a master `enabled` gate
  checked before any work (samples opt in, mirroring `JvmLanDiag.enabled`);
  convert `log`/`frame` on all three platforms to `inline fun log(tag: String,
  message: () -> String)` so arguments are lazy; route the Android discovery
  transport's per-event/`refresh` `Log.d` lines through the gated helper
  (keep warn-level lines as-is).
- Required tests: none functional; existing loopback + lifecycle suites green.
  (Sample apps must still see the trace when they enable it — manual check.)

### PERF-5 — Zombie-detection lookup runs per inbound message even when its only output (a warn log) is discarded by the default NoOp logger
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/.../internal/P2pSessionImpl.kt:499-515; SessionStore.kt:207-213; SessionManager.kt:243 (wiring `lookupRegistration = store::registrationOf`)
- Category: improvement
- Root cause: `routeEvents` consults `lookupRegistration` before **every**
  `ProtocolEvent.Message` emission. The lookup does a map get plus an O(active
  sessions) identity scan of the published list, wrapped in `runCatching`,
  allocating a `Result` + `SessionRegistration` per message. Its only effect is
  a `logger.warn("ZOMBIE …")` — invisible under the default `P2pLogger.NoOp`
  (P2pLogger.kt:17), so in the default configuration the SDK pays per-message
  work for a diagnostic that cannot be observed.
- Evidence:
  ```kotlin
  // P2pSessionImpl.kt:499-501 — per Message
  val reg = lookupRegistration?.let { lookup ->
      runCatching { lookup(this@P2pSessionImpl) }.getOrNull()
  }
  // SessionStore.kt:211 — O(n) scan per message
  isInPublicList = _sessions.value.any { it === session }
  ```
- Runtime impact: at 5–20 sessions the scan is tens of pointer compares plus
  2–3 small allocations per message — negligible CPU, but it is the single
  largest avoidable per-message cost in commonMain and sits directly on the
  receive hot path. | Platforms: all | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): skip the lookup when the logger is
  `P2pLogger.NoOp` (cheapest), or sample it (every Nth message / at most once
  per second per session), or gate behind an internal diagnostics flag the
  samples enable. Keep the mechanism — it exists to catch the hypothesis-B1
  leak — just stop paying for it when nobody can see the answer.
- Required tests: existing SessionFlowTest green; if gating on logger type,
  one unit test that a non-NoOp logger still gets the ZOMBIE warn in the
  forced scenario.

### PERF-6 — sendMutex is held across all chunks of a message; control frames (PONG replies, PINGs) queue behind large sends
- Severity: Improvement | Confidence: Confirmed (behavior); impact bounded by link speed
- File(s): p2p-core/.../internal/P2pSessionImpl.kt:235-242 (send), :518-522 (PONG reply takes the same mutex); DefaultP2pProtocol.kt:22-27 (loop inside one hold); contrast FileTransferDispatcher.kt:566-571 (file path correctly acquires per chunk)
- Category: improvement
- Root cause: `send()` wraps the whole `protocol.sendMessage(...)` — up to 64
  sequential 64 KiB socket writes for a 4 MiB message — in a single
  `sendMutex.withLock`. The file-transfer path deliberately takes the mutex
  per chunk (its `FileTransferConfig.chunkSizeBytes` KDoc even documents
  "lower chunkSizeBytes to give other traffic (PING, messages) more frequent
  slots on the write mutex"), so the two outbound paths have different
  fairness. While a large `send()` drains on a slow/congested link, the
  routeEvents PONG reply and the keep-alive PING wait for the entire message;
  worst case (peer stops draining mid-message) the hold approaches the 30 s
  write watchdog. Our own liveness is protected (keep-alive checks PONG age
  *before* acquiring the mutex — AUDIT-2026-06 fix, P2pSessionImpl.kt:573-581),
  but the *remote* peer's keep-alive sees our delayed PONG.
- Evidence:
  ```kotlin
  // P2pSessionImpl.kt:239-241
  sendMutex.withLock {
      protocol.sendMessage(connection, message)   // loops all chunks
  }
  // FileTransferDispatcher.kt:566-568 — the per-chunk pattern
  .collect { frame -> sendMutex.withLock { protocol.sendFileDataFrame(...) } }
  ```
- Runtime impact: on a healthy LAN a 4 MiB message drains in well under a
  second — no visible symptom. On a congested/half-wedged link, PONG latency
  up to the remaining message drain time (bounded by the 30 s watchdog); with
  the default remote timeout of 30 s this margin is thin only in the wedged
  case, which the watchdog then resolves anyway. | Platforms: all |
  User-visible: only under degraded links (peer may observe delayed PONGs)
- Failure class: none (latency/fairness)
- Proposed fix (do NOT implement): acquire the mutex per frame inside
  `sendMessage`'s loop (mirroring the file path). The wire protocol already
  supports interleaving — frames carry `messageId` and the `Reassembler`
  handles concurrent partials (MAX_PENDING_REASSEMBLIES=256). Note the
  behavior change: two concurrent `send()` calls could then interleave their
  chunk streams; receiver-side reassembly is unaffected, and per-message
  ordering is preserved by each call's own loop.
- Required tests: a commonTest with FakeRawConnection asserting a PONG (or
  PING) frame can be written between chunks of an in-flight multi-chunk send;
  existing SessionFlowTest / loopback tests green.

### PERF-7 — Reconnect discovery refresh is per-session with no cross-session coalescing; cost multiplies at K reconnecting sessions
- Severity: Improvement | Confidence: Confirmed (code); storm magnitude Uncertain (needs a multi-device AP-flap measurement to quantify mDNS traffic)
- File(s): p2p-core/.../internal/SessionManager.kt:498, :609-654 (per-session `launchPeriodicRefresh`, ~3 s ± 0.4 s); P2pKitImpl.kt:169-183 (each refresh fans out to every discovery transport); JvmLanDiscoveryTransport.kt:212-255; AndroidLanDiscoveryTransport.kt:332-402; IosLanDiscoveryTransport.kt:313-324
- Category: improvement
- Root cause: every reconnecting session runs its own periodic refresh loop,
  and each tick invokes the *global* `refreshDiscovery()` — refresh is not
  peer-scoped. With K sessions simultaneously in `Reconnecting` (typical
  after an AP reboot or Wi-Fi flap with many peers), the SDK performs K
  refreshes per ~3 s, each of which on JVM/Android rotates the JmDNS service
  listener (a fresh listener re-fires resolved callbacks for all cached
  services → n more registry events), executes a 200 ms blocking
  `list()` snapshot while holding the transport lock, and issues n
  `requestServiceInfo` mDNS queries; on iOS each refresh cancels and recreates
  the entire NWBrowser. K=10, n=10 → ~100 mDNS re-queries plus 10 browser/
  listener rebuild cycles every 3 s from one host, and every host on the LAN
  does the same. The per-session jitter (±400 ms) desynchronizes ticks but
  does not reduce the count.
- Evidence:
  ```kotlin
  // SessionManager.kt:498 — one loop per reconnecting session
  val periodicRefreshJob = launchPeriodicRefresh(session, peerShort)
  // P2pKitImpl.kt:174-175 — each tick is global
  discoveryTransports.forEach { transport -> runCatching { transport.refresh() } }
  // IosLanDiscoveryTransport.kt:319-322 — full browser teardown per tick
  browser?.let { nw_browser_cancel(it) } ... createBrowserLocked()
  ```
- Runtime impact: multiplied multicast traffic, transport-lock contention
  (200 ms holds back-to-back), browser/listener object churn, and n×K registry
  event reprocessing per 3 s during multi-session outages; single-session
  reconnects (the common case) are fine. | Platforms: all | User-visible:
  indirectly (slower collective recovery on busy LANs; radio wakeups on
  mobile during outage windows)
- Failure class: none (resource-efficiency under recovery load)
- Proposed fix (do NOT implement): hoist the periodic refresh into
  SessionManager as a single shared ticker that runs while ≥1 session is
  `Reconnecting` (reference-count enter/exit), keeping the same ~3 s cadence
  and jitter; per-session loops then just await rearm. The one-shot refresh at
  the Reconnecting edge can stay per-session (it is the latency-critical one).
- Required tests: commonTest with FakeDiscoveryTransport counting `refresh()`
  invocations: 3 concurrently-reconnecting sessions should produce ~1× (not
  3×) the single-session refresh rate over a fixed virtual-time window.
- Note: adjacent to, but distinct from, catalogued B:317 (the 200 ms snapshot
  bound itself — a deliberate latency trade-off I am not re-reporting).

### PERF-8 — [CATALOGUED extension of A14-SEC SEC-2] Registry republish work: per-event O(n) rebuild is fed every 5 s by the iOS announce loop, and the 1 Hz eviction loop allocates even when idle
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/.../internal/PeerRegistry.kt:79-106, :153-166; p2p-transport-lan/src/appleMain/.../IosLanDiscoveryTransport.kt:249-281 (announce loop, 5 s), :688
- Category: improvement
- Root cause: SEC-2 already catalogues the uncapped `tracked` map and the
  O(n²) republish pattern. New evidence on its steady-state drivers:
  (a) `PeerRegistry.processEvent` copies the whole map (`current + pair`),
  rebuilds the full public list, and deep-compares it (`Peer` data-class
  equality over name/platform/transport sets) on **every** event — and the
  iOS announce loop synthesizes n `PeerEvent.Updated` per 5 s while discovery
  runs, so an idle iOS kit with n peers performs n × O(n) map copies + list
  compares every 5 s indefinitely (jvm/android drivers: JmDNS re-resolves and
  refresh-tick listener rotations). (b) `evictStalePeers` runs every second
  for the kit's lifetime and always allocates: `filterValues` builds a new map
  and `publishPeers` builds a new list + deep-compares even when nothing was
  evicted and there are zero peers.
  ```kotlin
  // PeerRegistry.kt:97-105 — every 1 s tick, even with nothing stale
  tracked.update { current -> current.filterValues { ... } }
  publishPeers()
  ```
- Runtime impact: at the target scale (5–20 peers) this is microseconds per
  tick — CPU is a non-issue; the relevant costs are steady allocation churn
  and a permanent 1 Hz + 0.2 Hz wakeup cadence on mobile devices. |
  Platforms: all (announce-loop driver is iOS-specific) | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): in `evictStalePeers`, scan first and only
  rebuild/publish when at least one entry is stale; in `publishPeers`, skip
  the list rebuild when the map instance is unchanged; optionally have
  `processEvent` mutate `lastSeen` in place for heartbeat `Updated` events
  whose `InternalPeer` is equal to the stored one (no map copy, no publish).
  Cap discussion belongs to SEC-2.
- Required tests: PeerRegistryTest addition — heartbeat Updated does not cause
  `peers` re-emission (pin existing behavior) and eviction tick with no stale
  peers leaves the `tracked` StateFlow value identity-unchanged.

### PERF-9 — FrameReader buffering is quadratic against legal-but-non-conforming framing patterns
- Severity: Low | Confidence: Confirmed (arithmetic from code; not measured on device)
- File(s): p2p-core/.../protocol/FrameReader.kt:37-79
- Category: bug (defensive resource-efficiency gap)
- Root cause: `feed` copies the entire accumulated buffer on every append
  (lines 40-43) and copies the entire remaining tail after every extracted
  frame (line 76). Two inputs that are fully legal under the protocol limits
  make this quadratic:
  (a) a peer sending a single large frame near `MAX_FRAME_PAYLOAD_BYTES`
  (8 MiB) delivered in small TCP segments — at 8 KiB reads that is ~1024
  appends, each re-copying the partial frame: ≈ 4 GiB of memcpy for one 8 MiB
  frame; (b) a peer packing many tiny frames back-to-back — one 64 KiB feed
  containing ~1800 header-only frames performs ~1800 tail copies of the
  shrinking buffer (~57 MiB memcpy per 64 KiB received). Conforming senders
  (our own implementations chunk at 64 KiB) never trigger either shape, so
  this is a robustness/efficiency bound against excessive peer input, not a
  normal-operation defect. The 8 MiB length cap (checked before buffering,
  line 57) correctly bounds *memory*; the *CPU* per received byte is what
  remains unbounded (O(frame_size / read_size) per byte).
- Evidence:
  ```kotlin
  // FrameReader.kt:40-43 — full re-copy per feed
  val combined = ByteArray(buffer.size + bytes.size)
  buffer.copyInto(combined, 0); bytes.copyInto(combined, buffer.size)
  // FrameReader.kt:76 — full tail re-copy per extracted frame
  buffer = if (buffer.size == frameSize) EMPTY else buffer.copyOfRange(frameSize, buffer.size)
  ```
- Runtime impact: a non-conforming peer can pin roughly a core's worth of
  memcpy per connection while staying inside every protocol limit; sessions
  remain functional (degraded-but-recoverable), and closing the session ends
  it. On mobile this is battery/CPU pressure; no memory growth. | Platforms:
  all | User-visible: only under such input (UI jank / battery on mobile)
- Failure class: resource-limit (CPU) robustness
- Proposed fix (do NOT implement): offset-based consumption (read index into a
  retained buffer, compact only when the offset passes a threshold), which
  fixes both shapes and is the same refactor PERF-1(2) proposes; alternatively
  an amortized growth buffer (grow by doubling, append in place).
- Required tests: FrameReaderTest additions — (i) feed one 1 MiB frame in 8 KiB
  slices and assert output equivalence (guards the refactor); (ii) feed 1000
  concatenated empty-payload frames in one call and assert all decode. (No
  timing assertions — behavioral equivalence only, per no-test-masking rule.)

### PERF-10 — iOS listener (re)build blocks a Dispatchers.Default worker for up to 5 s; the kit's entire core runs on Default
- Severity: Improvement | Confidence: Confirmed (code); real-world stall frequency Uncertain (rebinds are event-driven: path changes, foregrounding)
- File(s): p2p-transport-lan/src/appleMain/.../IosLanDataTransport.kt:394-416 (`dispatch_semaphore_wait` with 5 s deadline inside `buildListener`), :277-278 (`rebindScope = SupervisorJob() + Dispatchers.Default`), :688 (`rebindNow` runs on that scope, under `startMutex`); p2p-core/.../internal/P2pKitImpl.kt:79 (kit scope = `Dispatchers.Default`)
- Category: improvement
- Root cause: `buildListener` parks the calling thread on a dispatch semaphore
  waiting for the listener to reach `.ready` (deadline 5 s). During initial
  `start()` this is a caller-context concern, but the rebind path invokes it
  from `rebindScope` on `Dispatchers.Default` — the same limited worker pool
  (sized to core count on Kotlin/Native) that runs every session's
  `routeEvents`, keep-alive, frame decode, and reassembly for the whole kit.
  A slow bind (constrained network transitions are exactly when rebinds fire)
  occupies one Default worker for up to 5 s while holding `startMutex`.
- Evidence:
  ```kotlin
  // IosLanDataTransport.kt:414-416
  nw_listener_start(l)
  val deadline = dispatch_time(DISPATCH_TIME_NOW, (5L * NSEC_PER_SEC.toLong()))
  dispatch_semaphore_wait(ready, deadline)   // blocks the coroutine's thread
  ```
- Runtime impact: during a rebind window on a low-core device, message
  routing/decoding for all sessions loses one worker; combined with a
  concurrent reconnect (also on Default) this can add visible latency at the
  exact moment the network is recovering. Not a hang (bounded 5 s). |
  Platforms: iOS | User-visible: possible brief stall during network
  transitions
- Failure class: none (dispatcher hygiene)
- Proposed fix (do NOT implement): replace the semaphore with a
  `suspendCancellableCoroutine` resumed from the state-changed handler (the
  handler already fires on the dedicated listener queue), or run
  `buildListener` on `Dispatchers.IO` (K/N has an IO dispatcher since
  kotlinx-coroutines 1.7) — either keeps `startMutex` semantics while freeing
  the Default worker.
- Required tests: iosSimulatorArm64 lifecycle tests green; no timing-based
  assertion added (flaky-prone) — code-review parity note in the PR instead.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Control-frame (PING/PONG) writability while a multi-chunk send is in flight (PERF-6) | Remote keep-alive sees our PONG latency; the file path already guarantees interleaving, `send()` does not | p2p-core commonTest (SessionFlowTest or new SendFairnessTest with FakeRawConnection) | unit/combination | P2 |
| Refresh invocation count with K concurrently-reconnecting sessions (PERF-7) | Multiplied global refresh is invisible in single-session tests; a coalescing regression would also be invisible | p2p-core commonTest (SessionReconnectRotationTest ext., FakeDiscoveryTransport counting refresh()) | unit | P2 |
| FrameReader behavioral equivalence under pathological feed shapes (large frame in 8 KiB slices; 1000 tiny frames in one feed) (PERF-9, PERF-1 refactor guard) | Any buffer-management refactor needs these as correctness anchors; today only friendly splits are tested | p2p-core commonTest FrameReaderTest | unit | P2 |
| Heartbeat-only `PeerEvent.Updated` does not re-emit `peers`; idle eviction tick leaves `tracked` value identity-unchanged (PERF-8) | Pins the de-noising behavior the public API relies on and enables the no-op-tick optimization safely | p2p-core commonTest PeerRegistryTest | unit | P3 |
| Single-frame send passes the caller's array without copy (PERF-2 anchor) | Zero-copy fast path is easy to regress silently in a chunker refactor | p2p-core commonTest ChunkerTest (assert payload === input for ≤ chunkSize) | unit | P3 |
| End-to-end throughput/allocation guardrail (5 MiB loopback with a coarse time bound or JMH-style harness, run manually) | Copy-chain regressions (PERF-1/2) are invisible to all current tests | :p2p-transport-lan jvmTest, manual/benchmark task (not CI-gating, to avoid flaky timing assertions) | manual/integration | P3 |
| Trace sinks perform no work when disabled (PERF-4) | The "pays nothing when off" contract is documented but only FrameTrace honors it structurally | jvmTest (JvmLanDiag with a counting sink + enabled=false) | unit | P3 |

## 4. Section summary

**What this review owns:** cross-cutting efficiency of the runtime hot paths —
data-plane copies/allocations (S6/S7), per-event work on session and registry
paths (S3/S4), discovery cadences (S5), file-transfer streaming (S8).

**Overall health:** good. The hot path is correctness-first and shows the
audit's fingerprints everywhere (bounded channels, capped reassembly, single
write choke point, per-chunk mutex on the file path, `FrameTrace`'s zero-cost
gate). There are **no High or Critical performance defects**: at the SDK's
target scale (LAN links, 5–20 peers, 64 KiB chunks) every inefficiency found
has comfortable headroom. The costs that do exist cluster in three places:
(1) the inbound byte pipeline makes ~5 sequential copies of every payload byte
with ~4.5× extra append amplification on JVM/Android due to the 8 KiB read
buffer (PERF-1/PERF-9 — one refactor fixes both); (2) recovery windows
multiply work per reconnecting session instead of sharing it (PERF-7); (3)
diagnostics do per-frame work even when nobody is listening (PERF-4, PERF-5),
with iOS lacking a master gate entirely.

**Top 3 risks:** 1) receive-path copy/GC amplification on Android under
sustained file transfer (PERF-1, PERF-9's quadratic corner against
non-conforming input); 2) uncoalesced K× global discovery refresh during
multi-session outages — multiplied mDNS traffic and lock contention exactly
when the network is weakest (PERF-7); 3) iOS per-frame ungated diagnostic
work inside the write lock (PERF-4).

**Cadence/idle-cost inventory** (for the record; all acceptable): registry
eviction 1 Hz (allocates when idle — PERF-8); keep-alive 0.1 Hz per session;
iOS announce loop 0.2 Hz emitting n Updated events (feeds the catalogued
O(n²) republish); reconnect refresh ~0.33 Hz per reconnecting session
(PERF-7); JVM/Android write watchdog one coroutine per frame (PERF-3).
Startup/first-connect latency contributors: JmDNS create/probe on first
start, iOS listener bind wait (≤5 s), TCP connect timeout 5 s, handshake
timeout 10 s, Android refresh snapshot 200 ms — all deliberate bounds, none
flagged.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy:** the map's structural claims for
the sections I crossed (S3–S8 file ownership, "P2pKitImpl constructs
DefaultP2pProtocol directly — P2pKitImpl.kt:97", S5↔S3 refresh dependency)
match the code I read. The map makes no performance assertions, so there is
nothing to correct from this review's angle. One nuance worth a map footnote:
row 6 lists A15-PERF as cross-cutting — correct; my findings attach to S3
(PERF-5/6/7), S4 (PERF-8), S5 (PERF-4/7/8), S6 (PERF-1/2/9), S7
(PERF-1/3/4/10), S8 (PERF-2 file-path notes).

**Catalogued items honored:** PeerRegistry uncapped map + O(n²) republish
(SEC-2) — extended, not re-derived, as PERF-8 [CATALOGUED]. Android 200 ms
`list()` snapshot (B:317) — not re-reported; PERF-7 addresses the orthogonal
K× multiplication. Reassembler remediation code (commit 6de50db) reviewed
fresh: its accounting is O(1) per chunk, eviction is read-driven with an
empty-map fast path, and the completion pass is a single linear copy —
efficient as written; no findings.
