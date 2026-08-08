# A14-SEC — Resilience & resource-limit review (untrusted input, cross-cutting)

Cross-cutting reviewer. Owns no tracker rows; findings tagged with the owning
section. Dimension: how the SDK handles malformed or excessive input from a
non-conforming peer on the shared LAN sending arbitrary bytes/records (the SDK's
own documented threat model), plus end-to-end walks of every untrusted-input
path and every bounded resource.

Trust model (given — NOT re-reported; boundaries assessed): `SecurityMode.
NoneForMvp` — no encryption/authentication until the encryption milestone;
inbound HELLO peerId unverified BY DESIGN (`SessionManager.kt:360`
`TODO(encryption-milestone)`; own-peerId reflection guard present at :356);
identity collision within a shared appId is accepted-risk.

## 0. Headline

The **parsing/limit layer is genuinely well-hardened** — the AUDIT-2026-06 caps
(`MAX_FRAME_PAYLOAD_BYTES`, `MAX_TOTAL_CHUNKS`, `MAX_PENDING_REASSEMBLIES`,
`MAX_TOTAL_PENDING_BYTES`, `MAX_PENDING_INCOMING_OFFERS`, capped reason strings,
`StreamingFileReceiver` size cap, bounded HELLO/FILE_OFFER fields) close the
per-frame and per-message memory vectors, and I found no bypass of them. The
gaps are one layer up: **there is no admission control on how many untrusted
connections/sessions the SDK will service at once, and no cap on how many peers
the registry will track** — the byte-level caps bound each unit of work but not
the *number* of concurrent units. That is the through-line of SEC-1 and SEC-2.

## 1. Untrusted-input surface — walk verdicts (files I opened for this dimension)

| Path / file | Untrusted input | Resilience / resource-limit verdict |
|---|---|---|
| `protocol/FrameCodec.kt` (127) | raw frame header/payload | Clean. payloadLen `<0`/`>8MiB`, totalChunks `<=0`, chunkIndex range, truncation all rejected pre-alloc; `HEADER_SIZE+payloadLen` computed in Long. |
| `protocol/FrameReader.kt` (86) | TCP byte stream | Length-cap enforced before buffering (:57). **But** O(n²) append is peer-input-amplifiable → escalates PRO-10 (owner S6): SEC-I1. |
| `protocol/Reassembler.kt` (185) | multi-chunk DATA | Clean & exemplary. dup/range/mismatch reject; per-msg + aggregate byte caps; inactivity eviction. No bypass found. |
| `protocol/HelloPayload.kt` (59) | HELLO JSON | appId/peerId/deviceName/transports-count capped. `platform` + per-transport strings uncapped → SEC-I2 (owner S6, Low, frame-cap-bounded). |
| `protocol/FileOfferPayload.kt` (54) | FILE_OFFER JSON | name(4096)/mime(255)/size(≥0) capped. name is metadata only; SDK never opens a path from it (app supplies the sink) — no path traversal. Clean. |
| `protocol/DefaultP2pProtocol.kt` (219) | frame→event decode | Clean. malformed HELLO/FILE_OFFER `runCatching`→skip+warn; reason strings capped 1024 B; `evictStale()` driven per read batch. |
| `internal/FileTransferDispatcher.kt` (645) | FILE_* frames | Clean. size pre-check before state alloc; dup transferId reject; `MAX_PENDING_INCOMING_OFFERS=64`; per-transfer error isolation. |
| `protocol/StreamingFileReceiver.kt` (94) | FILE_DATA stream | Clean. writes capped at declared `sizeBytes` (:56); out-of-order reject (:49); no disk usage beyond `maxFileSizeBytes`. |
| `internal/Handshake.kt` (89) | HELLO exchange | 10 s receive timeout; appId/version checks. `sendHello` precedes the timed receive and is itself unbounded (SES-11) → feeds SEC-1 window. |
| `internal/SessionManager.kt` (789) | inbound connections | Event channel bounded 256 (good). **No cap on concurrent handshakes or total sessions** → SEC-1 (owner S3). Outgoing id-check + own-id guard present. |
| `internal/P2pSessionImpl.kt` (717) | routed events | Backpressure via SUSPEND SharedFlow(64) + bounded event channel is sound. Per-session footprint (~5 coroutines + fd) feeds SEC-1(b). |
| `internal/PeerRegistry.kt` (187) | PeerEvents | **No cap on `tracked`**; `publishPeers` O(n)/event → SEC-2 (owner S4). Discovered peers evict at 15 s; manual exempt. |
| `jvm/AndroidLanDataTransport` accept | inbound sockets | callbackFlow(64) + close-on-full is correct locally, but collector drains non-blocking → no real bound (SEC-1). Parity JVM≡Android confirmed. |
| `appleMain/IosLanDataTransport.kt` accept | inbound sockets | `Channel.UNLIMITED` (:185) compounds SEC-1 on iOS — see CON-9 (owner S7). |
| `jvm/JvmRawConnection.kt` (208) | socket read/write | `read()` into 8 KiB buffer; the peer controls segment sizes → SEC-I1. Write watchdog sound. |
| `appleMain/IosBonjour.kt` (97) | TXT records | Decode bounded per-key; parity edge cases owned by A05 DSC-12. |

## 2. Findings

### SEC-1 — No admission control on inbound connection setup: unbounded concurrent pre-handshake handshakes and unbounded total sessions
- Severity: **High** | Confidence: Confirmed (code-path); exact rate-to-limit depends on host fd/heap limits
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:146-152` (`startAcceptingIncoming`), `:198-215` (`handleIncoming`), `:290-313` (`runHandshake` launches readerJob + 256-slot channel per connection); `internal/Handshake.kt:47-54` (sendHello precedes the timed receive); accept sources `jvmMain/.../JvmLanDataTransport.kt:132-171`, `androidMain/.../AndroidLanDataTransport.kt:122-158`, `appleMain/.../IosLanDataTransport.kt:185`
- Category: bug (design-level resource-limit / admission-control gap)
- Root cause: the inbound path has **no ceiling on concurrency at any layer**.
  `startAcceptingIncoming` collects each transport's `incomingConnections()`
  with `.onEach { handleIncoming(it) }.launchIn(scope)`, and `handleIncoming`
  is `scope.launch { setupSession(...) }` — it returns immediately, so the
  collector never blocks. The bounded accept queue (JVM/Android
  `callbackFlow`(64); iOS is `Channel.UNLIMITED`) therefore drains at O(1) and
  provides **no back-pressure onto the fan-out**. For every accepted socket the
  SDK spins up, before any authentication: one accepted-socket fd, a
  `setupSession` coroutine, a `readerJob` coroutine (`SessionManager.kt:301`), a
  256-slot `Channel<ProtocolEvent>` (:300), and a `FrameReader`+`Reassembler`
  (`DefaultP2pProtocol.events`). Nothing bounds how many of these exist at once.
  A `Semaphore`/limit search across `p2p-core` and `p2p-transport-lan` returns
  only the iOS bind semaphore and the Android multicast lock — there is no
  session/connection/handshake cap.
- Reclaim window is long: `performHandshake` calls `protocol.sendHello(...)`
  (`Handshake.kt:47`) **before** the 10 s `withTimeoutOrNull { events.receive() }`
  (:49). Against a peer that accepts the TCP connection but never drains,
  `sendHello`'s write wedges up to the 30 s write watchdog (`JvmRawConnection.kt:206`
  `WRITE_TIMEOUT_MILLIS`; SES-11 in A03), so each such connection pins its
  resources for ≈ 30 s + 10 s ≈ 40 s, not 10 s.
- Evidence:
  ```kotlin
  // SessionManager.kt
  fun startAcceptingIncoming(transports: List<DataTransport>) {
      for (transport in transports)
          transport.incomingConnections()
              .onEach { connection -> handleIncoming(connection) }   // O(1), never blocks
              .launchIn(scope)
  }
  private fun handleIncoming(connection: RawConnection) {
      scope.launch { setupSession(rawConnection = connection, ... ) }  // unbounded fan-out
  }
  ```
- Runtime impact: a single non-conforming LAN host has two escalation paths.
  **(a) Pre-handshake (no appId needed):** open connections faster than the
  ~40 s reclaim → unbounded concurrent {fd + 2 coroutines + 256-slot channel +
  reader buffers}. The first wall is running out of file descriptors, which
  manifests as **CON-3** (A06): the accept loop's own `sock.accept()` throws
  `EMFILE`, the callbackFlow closes exceptionally, and — no
  `CoroutineExceptionHandler` on the kit scope — the process crashes on Android /
  goes permanently inbound-deaf on JVM. So SEC-1 is the *upstream cause* that
  makes CON-3 reachable on demand, and it independently drives heap/coroutine
  growth on hosts with high fd limits. On iOS the `Channel.UNLIMITED` accept
  queue (CON-9) removes even the local back-pressure.
  **(b) Post-handshake (needs the shared appId — low barrier within one app,
  per the trust model):** a peer completing valid HELLOs while claiming N
  distinct peerIds registers N full `P2pSessionImpl` instances, each ~5
  coroutines (`routeEvents`+`keepAliveLoop`+`observeRawState`+reconnect/watchdog)
  + a socket + a keep-alive PING loop. `SessionStore` enforces one-session-*per-
  peer* but nothing caps the number of *distinct* peers, so this is unbounded.
  | Platforms: all (root cause is common `SessionManager`; iOS worst via CON-9) | User-visible: yes (crash / inbound-deafness / OOM)
- Failure class: resource-limit / unbounded-usage (fd + memory + coroutine) → crash/hang
- Relationship to catalogued items: **distinct root cause, not a duplicate.**
  CON-3 fixes the *symptom* (survive `EMFILE`); CON-9 bounds only the iOS accept
  *queue* and explicitly reasons JVM/Android are "bounded, none in steady state"
  — that reasoning covers the 64-slot handoff but misses that the non-blocking
  collector converts the bound into an unbounded downstream fan-out. SEC-1 is
  the admission-control gap that sits above both. SES-11 (A03) is a contributing
  amplifier (the 40 s window).
- Proposed fix (do NOT implement): introduce an inbound admission limit —
  a `Semaphore(maxConcurrentInboundHandshakes)` acquired in `handleIncoming`
  before `scope.launch` (tryAcquire → on failure `connection.close()` + warn, so
  excess connections are shed cheaply instead of accumulating), plus an overall
  active-session cap (and/or a per-remote-IP cap) checked in `registerSession`.
  Values configurable with safe defaults. No public-API change required
  (internal wiring); a `Config` knob would be additive if desired
  (`[API-CHANGE]` only if surfaced). Pair with CON-3's fix so a transient EMFILE
  event never kills the loop.
- Required tests: transport-lan jvmTest — open K (≫ limit) raw sockets that
  never send HELLO, assert the kit stays responsive (outbound + a legit inbound
  still succeed), fd/session count stays bounded, and no uncaught exception
  reaches the kit scope. commonTest with fakes — feed N incoming connections
  each claiming a distinct peerId, assert active sessions are capped and excess
  are closed.

### SEC-2 — PeerRegistry `tracked` map is uncapped: a high volume of mDNS discovery events inflates the peers list with O(n²) republish cost
- Severity: **Medium** | Confidence: Confirmed (code-path); magnitude bounded by the volume of records a LAN peer can multicast
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:79-93` (`processEvent`/`publishPeers`), `:95-106` (`evictStalePeers`)
- Category: bug (resource-limit / unbounded-growth, amplification)
- Root cause: `processEvent` adds every `PeerEvent.Found`/`Updated` to `tracked`
  with no size limit, and `publishPeers()` rebuilds the whole list and does an
  O(n) list-equality on every event:
  ```kotlin
  is PeerEvent.Found  -> current + (event.peer.publicPeer.id to TrackedPeer(event.peer, clock()))
  is PeerEvent.Updated-> current + (event.peer.publicPeer.id to TrackedPeer(event.peer, clock()))
  ...
  private fun publishPeers() {
      val newList = tracked.value.values.map { it.internalPeer.publicPeer }   // O(n)
      if (_peers.value != newList) _peers.value = newList                     // O(n) compare
  }
  ```
  A peer advertising many `_p2pkit._tcp` instances (distinct instance
  names → distinct peerIds in TXT) with the local appId drives N entries into
  `tracked` and the public `peers` StateFlow. Discovered peers are evicted after
  `staleTimeoutMillis` (15 s), but N is unbounded within that window and the
  sender keeps N alive by re-announcing. A burst of N unique Found events
  costs Σ O(k) ≈ O(N²) in list rebuild+compare, and emits N times to every
  `peers` collector (app UI recomposition).
- Runtime impact: CPU + heap pressure proportional to the event volume, plus churn of
  every `kit.peers` subscriber. Self-heals within ~15 s once the event burst stops.
  Note the sender must be able to inject the local appId in TXT — which under
  `NoneForMvp` is exactly the accepted-risk boundary, so this is reachable.
  | Platforms: all (registry is common; the JmDNS/NWBrowser caches upstream are
  also uncapped) | User-visible: yes (peer list bloat, UI churn, lag)
- Failure class: resource-limit / unbounded-growth (bounded, recoverable)
- Relationship to catalogued items: A04 IDN-2/IDN-3 cover the manual-peer race
  and the `publishPeers` read-then-assign race; **neither covers the uncapped
  growth or the O(n)-per-event republish** under high event volume. A05 DSC-11/DSC-12
  cover forged `Lost` and TXT decode parity, not volume.
- Proposed fix (do NOT implement): cap `tracked` at a sane maximum
  (e.g. a few hundred) with oldest-lastSeen eviction when exceeded, and/or
  make `publishPeers` incremental (diff against previous rather than full
  rebuild+compare). A per-source-host cap on discovered peers would also blunt a
  single-host event burst.
- Required tests: PeerRegistryTest — inject N ≫ cap distinct Found events,
  assert `peers.value.size` is bounded and republish work is not O(N²)
  (e.g. via a counting clock or an emission counter).

## 3. Improvements (not defects — risk-reduction / escalations of catalogued items)

### SEC-I1 — PRO-10 (A07, owner S6) is peer-input-controlled, not merely an app-chunk-size perf note
- `FrameReader.feed` reallocates+copies the whole accumulated buffer per call.
  A07/PRO-10 estimates the cost from the transport's 8 KiB read buffer and marks
  it "correctness unaffected." But `input.read(buffer)` (`JvmRawConnection.kt:154`,
  `AndroidRawConnection` mirror) returns *as few as 1 byte* — the number of
  `feed` calls to assemble a frame is set by the sender's TCP segmentation,
  which the peer controls. Delivering one ≤8 MiB frame in tiny segments
  drives the true worst case (Σ copies ≈ O(frameSize²), tens of GB of memcpy
  for a single 8 MiB frame), sustainable across the (per SEC-1, unbounded)
  connections. Recommend re-rating PRO-10 as a peer-driven CPU-cost issue (Medium) and
  fixing with an offset/ring buffer (consume without reallocation) or a cap on
  bytes buffered for a single not-yet-complete frame relative to progress.

### SEC-I2 — HELLO `platform` and per-transport strings are not length-validated (owner S6)
- `HelloPayload.decode` (`HelloPayload.kt:44-55`) caps `appId`, `peerId`,
  `deviceName`, and the transports *count* (32), but not `platform` nor each
  `supportedTransports[i]`. Bounded by the 8 MiB frame cap and discarded
  promptly (`toPeer` parses `platform` to an enum with UNKNOWN fallback,
  `Handshake.kt:86-87`; A07 assessed retention as bounded), so this is a
  defensive-symmetry gap, not a live vector. Cap them like the sibling fields.

### SEC-A1 — Boundaries assessed as SOUND (no change needed)
- Reassembler caps and accounting (dup/range/mismatch, per-msg + aggregate,
  inactivity eviction) — no bypass found; exemplary.
- `StreamingFileReceiver` caps writes at the peer-declared `sizeBytes` and that
  size is pre-validated against `maxFileSizeBytes` — no disk usage beyond the
  configured cap. Out-of-order FILE_DATA rejected.
- Bounded `Channel<ProtocolEvent>(256)` in `runHandshake` + SUSPEND-overflow
  `_incoming`/`_incomingOffers` SharedFlows correctly push back-pressure to TCP
  (per-connection buffering is bounded). The problem is only the *number* of
  connections (SEC-1), not per-connection buffering.
- ERROR/FILE_REJECT/FILE_CANCEL reason strings capped at 1024 B
  (`DefaultP2pProtocol.decodeReasonCapped`).
- Outgoing peerId-mismatch check + own-peerId reflection guard
  (`SessionManager.kt:344-359`) are the correct MVP-level guards; inbound-peerId
  trust is the documented `[CATALOGUED]` encryption-milestone deferral — sound
  as a deferral given `SecurityMode.NoneForMvp`.

## 4. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Concurrent inbound handshakes/sessions are bounded; excess connections are shed, not accumulated | SEC-1 — the primary resource-limit gap under excessive inbound connections; nothing pins any ceiling today | transport-lan jvmTest + core commonTest (fakes) | integration + combination | P1 |
| N distinct-peerId HELLOs do not create unbounded sessions | SEC-1(b) — post-handshake session multiplication | commonTest with FakeDataTransport | combination | P2 |
| mDNS Found-event burst keeps `peers` bounded and republish sub-quadratic | SEC-2 — registry growth/CPU under high event volume | PeerRegistryTest | unit | P2 |
| Frame delivered in 1-byte segments does not incur quadratic copy cost | SEC-I1 — peer-controlled amplification of PRO-10 | FrameReaderTest (feed one byte at a time; assert work bound) | unit | P2 |
| HELLO with a multi-MB `platform`/transport string is bounded/rejected | SEC-I2 | HelloPayloadTest | unit | P3 |

## 5. Section summary

**What this cross-cutting pass owns:** the resilience / resource-limit dimension across all
untrusted-input paths (frame/JSON/TXT parsing) and all bounded resources (fds,
sockets/NW objects, coroutines, scopes, reassembly/dispatcher buffers, the peer
registry).

**Overall health:** the *content* validation is strong — the AUDIT-2026-06
remediation genuinely closed the per-frame/per-message memory vectors and I
found no bypass. The weakness is *volume/admission* control: the SDK will
service an unbounded number of untrusted connections/sessions (SEC-1) and track
an unbounded number of peers (SEC-2). These are the classic "the caps bound each
item but not the count" gaps that a per-section lens misses because each section
correctly bounds its own unit of work.

**Top 3 risks:**
1. SEC-1 — no inbound admission control (High): a single non-conforming host can
   drive unbounded fd/heap/coroutine growth; makes CON-3's crash/inbound-deafness
   reachable on demand.
2. SEC-2 — uncapped peer registry + O(n²) republish under a high volume of mDNS events (Medium).
3. SEC-I1 — peer-controlled O(n²) frame-copy amplification (escalates
   A07/PRO-10 from perf note to a peer-driven CPU-cost issue).

**Map accuracy (`CODEBASE_REVIEW_MAP_2026-07.md`):** accurate for this
dimension. It flags S3 (High, "concurrency heart"), S5/S7 (High), and S6
(Medium-High, "parses untrusted bytes; malformed-input coverage is the review
question") — SEC-1/SEC-2/SEC-I1 land squarely in those. One nuance the map's
S7/S3 split obscures: the inbound *admission* gap is neither purely S7 (accept
transport) nor purely S3 (session) — it is the common `SessionManager` fan-out
between them, which is why no single per-section owner reported it. No
discrepancies requiring a map edit; SEC-1 should be filed against S3 with an
S7 cross-reference.
