# A7-PROTO — S6 Wire protocol review

Scope: `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/` (12 sources) +
`p2p-core/src/commonTest/kotlin/dev/p2pkit/core/protocol/` (8 tests). HEAD `870bf10`.
Note: the package also contains `StreamingFileReceiver.kt` / `StreamingFileSender.kt` (+ their tests) — per
`CODEBASE_REVIEW_MAP_2026-07.md` those belong to S8; not reviewed here beyond boundary checks.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| Chunker.kt | 75 | improvements: PRO-9 | ChunkerTest | multibyte-UTF-8 split across chunks; exact-multiple >1 chunk; no MAX_TOTAL_CHUNKS consistency test |
| DefaultP2pProtocol.kt | 219 | findings: PRO-7; improvements: PRO-12 | DefaultP2pProtocolTest, FileTransferProtocolTest | malformed HELLO/FILE_OFFER skip paths untested; decodeReasonCapped untested; evict-order untested |
| FileOfferPayload.kt | 54 | clean | FileOfferPayloadTest | all decode guards (negative size, name>4096, mime>255, bad JSON) untested |
| Frame.kt | 112 | improvements: PRO-9 (no construction/encode-side bounds) | FrameCodecTest (indirect) | none specific (validated on decode) |
| FrameCodec.kt | 126 | findings: PRO-6; improvements: PRO-9 | FrameCodecTest | oversized declared payload_len; forward-compat stance (reserved byte / high flag bits / version≠1) unpinned |
| FrameReader.kt | 86 | improvements: PRO-8, PRO-10, PRO-12 | FrameReaderTest | oversized declared payload_len (the 8 MiB resource-limit guard) has zero coverage; negative len via reader path |
| FrameTrace.kt | 38 | clean | none (diagnostic; exercised by samples) | none needed (behavior trivial; enabled=false default unasserted) |
| HelloPayload.kt | 59 | findings: PRO-1, PRO-4, PRO-5 | HelloPayloadTest | all decode guards (blank/oversized fields, >32 transports, bad JSON, missing fields) untested |
| P2pProtocol.kt | 46 | findings: PRO-2 (interface lacks sendAck vs spec §13.5) | via protocol tests | n/a (interface) |
| ProtocolConstants.kt | 64 | findings: PRO-3 (spec drift) | referenced by ReassemblerTest/FrameCodecTest | constants themselves fine; see PRO-11 for cross-module duplicate |
| ProtocolEvent.kt | 36 | clean | protocol tests | n/a |
| Reassembler.kt | 185 | findings: PRO-7 (interplay); accounting verified exact | ReassemblerTest (14 cases) | MAX_TOTAL_CHUNKS, MAX_PENDING_REASSEMBLIES, multi-chunk >MAX_PAYLOAD_BYTES, evict-releases-aggregate-budget all untested |
| ChunkerTest.kt | 149 | clean (asserts invariants, not just paths) | — | see Chunker row |
| DefaultP2pProtocolTest.kt | 175 | improvements: happy-path only | — | no malformed-input/error-path case at all |
| FileOfferPayloadTest.kt | 38 | improvements: happy-path only | — | no rejection case for any guard |
| FileTransferProtocolTest.kt | 177 | clean (round-trips assert ids+payloads) | — | no malformed FILE_OFFER, no >1024 B reason truncation |
| FrameCodecTest.kt | 162 | clean (good negative coverage) | — | missing oversized-payload_len and forward-compat pins |
| FrameReaderTest.kt | 130 | clean (byte-at-a-time, skip-unknown asserted) | — | missing oversized-declared-length rejection |
| HelloPayloadTest.kt | 66 | improvements: happy-path only | — | no rejection case for any guard |
| ReassemblerTest.kt | 312 | clean (new cases assert accounting exactness) | — | see Reassembler row |

Verified funnel/parity cross-checks (no findings): every send path routes through the single
`writeFrame` choke point (`DefaultP2pProtocol.kt:102-105`; grep shows no `RawConnection.write` caller
outside it — `P2pSessionImpl`/`Handshake`/`FileTransferDispatcher` all call `protocol.send*`, and all
share one `sendMutex`, dispatcher receives it at `P2pSessionImpl.kt:171`). `evictStale()` runs on every
ingest batch (`DefaultP2pProtocol.kt:132`). Header math 4+1+1+1+1+16+4+4+4 = 36 matches spec §13.2 and
`HEADER_SIZE`. Signed-int reads of the uint32 fields are safe: values ≥ 2^31 parse negative and are
rejected (`payloadLen < 0`, `totalChunks <= 0`, `chunkIndex < 0`). `Reassembler.totalPendingBytes`
cannot drift: every increment (`Reassembler.kt:126-127`) is followed only by throw-paths that call
`removePending` first, or by the store at line 144; `removePending` (`Reassembler.kt:178-180`) is the
only map-removal path. FILE_DATA frames deliberately bypass the reassembler
(`decodeEvent → ProtocolEvent.FileData`), so `MAX_TOTAL_CHUNKS` correctly does not constrain file
transfers (a 2 GiB file = 32768 chunks passes `FrameCodec.decode`). `FileTransferConfig.chunkSizeBytes`
is capped at 4 MiB, consistent with the 8 MiB frame cap's stated headroom. Malformed UTF-8 in a text
payload cannot crash: `decodeToString()` substitutes U+FFFD on all targets.

## 2. Findings

### PRO-1 — HELLO wire caps enforced only on decode: an over-limit local config fails every handshake with a generic timeout
- Severity: Medium | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt:36-57`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt:41,127`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt:13-17`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/DefaultP2pProtocol.kt:148-158`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt:49-54`
- Category: bug
- Root cause: `HelloPayload.decode` rejects `appId`/`peerId`/`deviceName` over `MAX_FIELD_LEN = 512`, but nothing validates the *locally configured* values before `encode` — the builder only null-checks `deviceName` (`Builders.kt:127` `deviceName ?: error(...)`), and `AppId` only requires non-blank (`Identity.kt:15`). Enforcement is asymmetric: this SDK can emit a HELLO that every hardened receiver (including itself) drops.
- Evidence:
  ```kotlin
  // HelloPayload.decode (receive side)
  require(payload.deviceName.length <= MAX_FIELD_LEN) { ... }
  // Builders.kt:127 (send side — no length check anywhere)
  val resolvedName = deviceName ?: error("deviceName must be set on the P2pKit builder")
  ```
  On the receiver the malformed HELLO is skipped (`DefaultP2pProtocol.kt:154-157` runCatching → warn → `return null`), so both sides just hit the 10 s handshake timeout (`Handshake.kt:49-54`) — `HandshakeRejected("Handshake timed out …")`. With the default NoOp logger the receiver-side warn is invisible.
- Runtime impact: an app that sets `deviceName` (or `appId`) longer than 512 chars can discover peers but never connect; every attempt (and every reconnect retry) ends in a generic timeout on both sides with no hint of the cause. | Platforms: all | User-visible: yes
- Failure class: none (wrong error semantics / misleading diagnostics)
- Proposed fix (do NOT implement): validate at the choke points the SDK already owns — `require(...)` in `P2pKitBuilder.build()` (or in `HelloPayload.encode`, mirroring `decode`) so the failure is an immediate, local, self-explanatory `IllegalArgumentException`/typed error instead of a remote timeout. No public API shape change (stricter argument validation only).
- Required tests: builder/encode rejection at 513 chars and acceptance at 512; existing round-trip tests unchanged.

### PRO-2 — Spec §13.5 promises "a DATA frame with NEEDS_ACK triggers an ACK", but no code can ever send an ACK
- Severity: Low | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/P2pProtocol.kt:18-45` (no `sendAck`), `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:527-529`, `P2pKit-Spec.md` §13.5
- Category: bug (spec/impl mismatch)
- Root cause: only the decode half of ACK exists. `PacketType.ACK` decodes into `ProtocolEvent.Ack` (`DefaultP2pProtocol.kt:167`), which the session ignores ("Reserved for v0.2 reliability work", `P2pSessionImpl.kt:527-529`). There is no `sendAck` in the `P2pProtocol` interface and grep confirms no ACK frame is ever constructed for sending; production never sets `needsAck` either (`chunker.chunk(message)` at `DefaultP2pProtocol.kt:23` uses the default `false`).
- Evidence:
  ```
  Spec §13.5: "A DATA frame with `flags & NEEDS_ACK == 1` triggers an ACK."
  P2pProtocol.kt: sendMessage/sendHello/sendPing/sendPong/sendClose/sendError/sendFile* — no sendAck
  ```
- Runtime impact: none today (both endpoints are this SDK and never request ACKs). A third-party implementation written from the spec that sets NEEDS_ACK would wait for ACKs that never come. | Platforms: all | User-visible: no
- Failure class: none (latent interop)
- Proposed fix (do NOT implement): amend spec §13.5 to state that v1 receivers do not emit ACKs (flag is reserved plumbing), or implement the responder. Doc-only change suffices for RC.
- Required tests: if the responder is ever implemented, loopback test: DATA with NEEDS_ACK → ACK with same messageId/chunkIndex.

### PRO-3 — Spec §13.4's "receive-path caps (session-closing)" list omits the new `MAX_TOTAL_PENDING_BYTES` cap
- Severity: Low | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt:51-60`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Reassembler.kt:135-143`, `P2pKit-Spec.md` §13.4 (lines ~836-841)
- Category: bug (doc mismatch in the locked contract; defect in the 6de50db fix's documentation, not its code)
- Root cause: commit `6de50db` added a third session-closing receive cap (16 MiB aggregate across pending partials). §13.4 explicitly enumerates the other two (`MAX_TOTAL_CHUNKS`, `MAX_PENDING_REASSEMBLIES`) as protocol-violation caps but not this one (grep of the spec for `MAX_TOTAL_PENDING`/"aggregate" — no hit).
- Evidence:
  ```
  Spec §13.4: "receivers enforce total_chunks ≤ 1024 … and at most 256 concurrently-incomplete
  multi-chunk messages … Exceeding either is treated as a protocol violation"   ← "either", two caps
  Reassembler.kt:135: if (totalPendingBytes > ProtocolConstants.MAX_TOTAL_PENDING_BYTES) { … ProtocolError }
  ```
  The spec also never states the assumption that makes 16 MiB safe: a conforming sender writes one message's chunks back-to-back (this SDK does — whole-message send under `sendMutex`, `P2pSessionImpl.kt:239-241`). A spec-conforming sender that interleaved chunks of 5 × 4 MiB messages would violate no stated rule yet get its session closed.
- Runtime impact: none between this SDK's endpoints; interop/contract gap only. | Platforms: all | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): amend §13.4 to list the aggregate cap and state the back-to-back chunk-ordering expectation for conforming senders.
- Required tests: n/a (doc).

### PRO-4 — `HelloPayload.decode` bounds neither `platform` nor the individual `supportedTransports` strings
- Severity: Low | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt:44-56`
- Category: bug (inconsistent untrusted-input hardening)
- Root cause: the validation block caps `appId`, `peerId`, `deviceName` at 512 chars and the transport *count* at 32, but not `platform` length nor each transport string's length — a malformed HELLO can pack ~8 MiB (frame cap) of junk into those fields and still pass validation.
- Evidence:
  ```kotlin
  require(payload.deviceName.length <= MAX_FIELD_LEN) { ... }
  require(payload.supportedTransports.size <= MAX_TRANSPORTS) { ... }
  // no requirement on payload.platform.length or supportedTransports[i].length
  ```
- Runtime impact: bounded — `toPeer()` (`Handshake.kt:79-87`) immediately parses both into enums (`Platform.valueOf` → UNKNOWN fallback; unknown transports dropped), so nothing oversized is retained past the handshake; cost is transient JSON-decode allocation already bounded by the 8 MiB frame cap. | Platforms: all | User-visible: no
- Failure class: resource-limit (marginal, transient)
- Proposed fix (do NOT implement): add `require(payload.platform.length <= MAX_FIELD_LEN)` and `require(payload.supportedTransports.all { it.length <= MAX_FIELD_LEN })` for consistency.
- Required tests: decode rejects an over-limit platform / transport tag (alongside the currently missing guard tests, see §3).

### PRO-5 — Version-check documentation claims "major component" semantics; implementation is exact-match on a single Int
- Severity: Low | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt:11-13` (KDoc), `P2pKit-Spec.md:831,1013`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt:69-75`
- Category: bug (doc mismatch)
- Root cause: KDoc/spec say the receiver rejects "if protocolVersion **major** is different", implying a major.minor scheme with minor-tolerance. `protocolVersion` is one Int and the check is `peerHello.protocolVersion != ProtocolConstants.VERSION.toInt()` — any difference rejects. Equivalent today (version 1), divergent the day a "minor" bump is attempted per the documented rule.
- Evidence:
  ```kotlin
  if (peerHello.protocolVersion != ProtocolConstants.VERSION.toInt()) { … VersionMismatch … }
  ```
- Runtime impact: none today. | Platforms: all | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): reword KDoc + spec §13.3/§17 to "any difference in protocolVersion rejects" (or actually define the major/minor split before v2).
- Required tests: n/a (doc), or a Handshake test pinning exact-match rejection (exists? `HandshakeTest` covers mismatch — orchestrator may cross-check S3).

### PRO-6 — Frame-header `version` byte is never validated on receive, and unlike byte 7 this stance is undocumented and untested
- Severity: Low | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameCodec.kt:72,75-78,110`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Frame.kt:27` (only consumers: equals/hashCode/encode)
- Category: bug (validation/documentation gap)
- Root cause: `decode` carefully documents why the reserved byte and unused flag bits are accepted, but silently applies the same leniency to `bytes[4]` (version): a frame stamped version 0x07 decodes and is processed as v1 forever. Grep confirms no consumer reads `Frame.version` for gating. The only version gate is the HELLO JSON field — which a peer can satisfy while stamping arbitrary header versions. Spec §13.2 says only "currently 0x01" with no receiver rule.
- Evidence:
  ```kotlin
  val version = bytes[4]
  // bytes[7] reserved — deliberately NOT validated on decode … (comment covers byte 7 and flag bits only)
  return Frame(type, flags, messageId, chunkIndex, totalChunks, payload, version)
  ```
- Runtime impact: none today; if v2 ever changes header *layout*, a v1 decoder will misparse v2 frames as garbage (bad magic/length errors) rather than cleanly rejecting on the version byte. | Platforms: all | User-visible: no
- Failure class: none (forward-compat ambiguity)
- Proposed fix (do NOT implement): decide and document — either reject `version != VERSION` at decode (cheap, unambiguous; HELLO gate makes it near-unreachable for conforming peers) or extend the byte-7 comment + spec to state version is negotiated solely via HELLO. Pin whichever with a test.
- Required tests: `FrameCodecTest`: frame with version byte 2 → (chosen behavior).

### PRO-7 — `evictStale()` runs before the batch that could refresh a partial; late chunks then resurrect an uncompletable "zombie" pending
- Severity: Low | Confidence: Confirmed (mechanism); impact bounded by existing mitigations
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/DefaultP2pProtocol.kt:124-139`, `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Reassembler.kt:87-96,163-170`
- Category: bug (edge defect in/around the 6de50db fix — the call placement predates the fix, but the new inactivity semantics were built around it without revisiting order)
- Root cause: in `events()` the order is `evictStale()` → `reader.feed(bytes)`. A chunk that is *already in this batch* cannot refresh its message's `lastSeenMillis` before eviction is decided, so a partial idle marginally past the timeout is dropped even though its next chunk has already arrived. Worse, the remaining chunks of the evicted message then pass `getOrPut` and re-create a fresh `Pending` that is missing the evicted chunks and can never complete — it pins up to 4 MiB and keeps refreshing its own `lastSeenMillis` while the tail chunks flow, then dies by idle-eviction. The message is silently lost: no error, no event, on either side.
- Evidence:
  ```kotlin
  reassembler.evictStale()          // decides on staleness first
  val frames = reader.feed(bytes)   // …then processes the chunk that would have refreshed it
  ```
- Runtime impact: requires a >60 s mid-message stall on a connection that stays alive — largely precluded for this SDK's own traffic (whole-message send under `sendMutex`, 30 s write watchdog, keep-alive), so the realistic window is tiny; memory is bounded by the per-message/aggregate caps. | Platforms: all | User-visible: no (silent loss in the edge case)
- Failure class: data loss (narrow edge)
- Proposed fix (do NOT implement): call `evictStale()` *after* processing the batch (or after `reader.feed` but before the loop, keyed on pre-feed timestamps of ids not present in the batch). Optionally keep a small tombstone set of recently evicted messageIds so stragglers are dropped instead of re-opening state.
- Required tests: `ReassemblerTest`/protocol test: chunk arriving in the same ingest batch as the eviction boundary survives; post-eviction straggler chunks do not build an uncompletable pending.

## 2b. Improvements

### PRO-8 — FrameReader trusts `payload_len` before checking magic
- Severity: Improvement | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameReader.kt:48-66`
- Category: improvement (defense-in-depth / fail-fast)
- Once `HEADER_SIZE` bytes are buffered, `feed` reads the length at offset 32 and, if the (garbage) value is plausible (0..8 MiB), silently waits for up to 8 MiB more bytes before `FrameCodec.decode` finally rejects the bad magic. The full header is already in hand — validating magic (bytes 0-3) right there costs nothing and turns a desynced/garbage stream into an immediate `ProtocolError` instead of delayed detection + up to 8 MiB of pointless buffering.
- Proposed fix: check the 4 magic bytes in `feed` before reading `payloadLen`.
- Required tests: feed 36 bytes of garbage with a plausible length field → immediate ProtocolError (no waiting for the declared payload).

### PRO-9 — No sender-side symmetry guards: Chunker can exceed `MAX_TOTAL_CHUNKS`, `encode` can exceed `MAX_FRAME_PAYLOAD_BYTES`
- Severity: Improvement | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Chunker.kt:53` , `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameCodec.kt:31-48`
- Category: improvement (latent-config hazard; no current trigger)
- `Chunker(chunkSize = n)` with `n < payload/1024` produces `totalChunks > MAX_TOTAL_CHUNKS`, and `FrameCodec.encode` accepts any payload size — in both cases a compliant receiver kills the session (`Reassembler.kt:73-77`, `FrameCodec.decode:88-92`). Today only defaults reach production (`DefaultP2pProtocol.kt:16` default `Chunker()`; `P2pKitImpl.kt:97` passes no chunker; grep shows custom chunk sizes in tests only), so this cannot fire — but nothing stops a future config knob from shipping frames that hard-kill sessions on the receiving end.
- Proposed fix: `init`-require in Chunker that `ceil(maxPayloadBytes/chunkSize) <= MAX_TOTAL_CHUNKS`; `require(payload.size <= MAX_FRAME_PAYLOAD_BYTES)` in `encode`.
- Required tests: Chunker rejects an inconsistent (chunkSize, maxPayloadBytes) pair at construction; encode rejects an oversized payload.

### PRO-10 — FrameReader O(n²) copy amplification while accumulating a frame
- Severity: Improvement (performance) | Confidence: Confirmed
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameReader.kt:39-44,68,76`
- Every `feed` reallocates and copies the whole buffer, and each drained frame copies both the frame and the remainder. Transports read in 8 KiB chunks (`JvmRawConnection.kt:192`, `AndroidRawConnection.kt:191` — `BUFFER_SIZE = 8 * 1024`): a default 64 KiB frame costs ~4.5x memcpy amplification; an app-configured 4 MiB `chunkSizeBytes` (allowed by `FileTransferConfig`) costs ~256x (≈1 GiB of copies per 4 MiB frame), plus one short-lived allocation per feed for GC to chew. Correctness is unaffected.
- Proposed fix: offset-based draining (consume via a read cursor, compact occasionally) or a growable ring buffer.
- Required tests: existing FrameReaderTest semantics unchanged; add a large-frame accumulation test if refactored.

### PRO-11 — `LanConstants.PROTOCOL_VERSION` duplicate of `ProtocolConstants.VERSION` has no parity assertion
- Severity: Improvement | Confidence: Confirmed
- File(s): `p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt:52-53`, `p2p-core/.../ProtocolConstants.kt:13`
- The TXT `pv` value is a comment-enforced duplicate ("Must match `ProtocolConstants.VERSION`") because `ProtocolConstants` is module-internal. All three platforms advertise it (`JvmLanDiscoveryTransport.kt:80`, `AndroidLanDiscoveryTransport.kt:494`, `IosLanDiscoveryTransport.kt:561`) and none reads it back — drift would mislabel discovery metadata while HELLO still gates on the real version. Add a parity test (e.g. transport-lan jvmTest reading `ProtocolConstants.VERSION` reflectively, or a shared internal constant) and/or document that `pv` is advisory-only.

### PRO-12 — Documentation/diagnostic nits (batched)
- Severity: Improvement | Confidence: Confirmed
- File(s)/items:
  - `FrameReader.kt:17-18`: KDoc `@param skippedUnknownFrames` documents a property as a constructor param (doesn't resolve).
  - `P2pKit-Spec.md` §13.2: calls `message_id` a "UUID"; implementation is 16 `kotlin.random.Random` bytes (`Frame.kt:100`) with no RFC 4122 version/variant bits — fine functionally (correlation-only ids), wording should say "16 random bytes".
  - `DefaultP2pProtocol.kt:216-219` `decodeReasonCapped`: `copyOfRange(0, 1024)` can split a multi-byte UTF-8 sequence → stray U+FFFD before the "[truncated …]" suffix. Cosmetic.
  - `FrameReader.kt:74`: warn-per-skipped-frame is unthrottled; a non-conforming peer can emit many unknown-type frames, producing unbounded log volume (spec §17 does mandate warn-level logging; a simple counter-based suppression after N would keep the spirit).

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Declared `payload_len` > `MAX_FRAME_PAYLOAD_BYTES` → immediate ProtocolError, no buffering (reader) and decode rejection (codec) | This is THE OOM / resource-limit guard the constants KDoc and spec §13.2 advertise; zero regression coverage | FrameReaderTest + FrameCodecTest | unit | P1 |
| `HelloPayload.decode` guards: malformed JSON, missing fields, blank appId/peerId, 513-char fields, 33 transports | Untrusted-input surface; guards were hardening fixes and are wholly untested — a refactor could silently drop them | HelloPayloadTest | unit | P1 |
| Malformed HELLO / FILE_OFFER frame is skipped (warn) and the events flow keeps delivering subsequent frames | The skip-not-throw policy is an audit fix guarding against session-teardown/reconnect loops; only the happy path is tested | DefaultP2pProtocolTest / FileTransferProtocolTest | combination | P1 |
| `totalChunks > MAX_TOTAL_CHUNKS` → ProtocolError | Session-closing cap promised in spec §13.4; untested | ReassemblerTest | unit | P2 |
| 257th concurrent partial → ProtocolError (`MAX_PENDING_REASSEMBLIES`) | Session-closing cap promised in spec §13.4; untested | ReassemblerTest | unit | P2 |
| Multi-chunk `bufferedBytes` > `MAX_PAYLOAD_BYTES` → ProtocolError + entry removed (accounting) | The per-message cap on the multi-chunk path (line 128) has no direct test (dup-test throws earlier) | ReassemblerTest | unit | P2 |
| `evictStale` releases aggregate budget (evict a large partial → equally large new partial fits) | `totalPendingBytes` exactness through the eviction path — only the completion path is asserted today | ReassemblerTest | unit | P2 |
| `FileOfferPayload.decode` guards: negative sizeBytes, name > 4096, mime > 255, malformed JSON | Untrusted-input surface, untested | FileOfferPayloadTest | unit | P2 |
| Reason strings > 1024 B are truncated (`decodeReasonCapped`) for ERROR/FILE_REJECT/FILE_CANCEL | AUDIT-2026-06 fix with no regression test | DefaultP2pProtocolTest | unit | P3 |
| Forward-compat acceptance: nonzero reserved byte, unknown flag bits, version byte ≠ 1 | Documented decoder stance (FrameCodec.kt:75-78) unpinned — a "tightening" refactor would break cross-version interop silently | FrameCodecTest | unit | P3 |
| Multibyte UTF-8 text split across chunk boundaries round-trips | Byte-level chunking of text; reassembly-order dependent | ReassemblerTest | unit | P3 |
| Chunk arriving in the same batch as the eviction boundary survives; post-eviction stragglers don't build zombie pendings | Pins the PRO-7 fix | ReassemblerTest / DefaultP2pProtocolTest | unit | P3 (P2 if PRO-7 fixed) |

## 4. Section summary

S6 owns the byte-level contract: framing/parsing (`Frame`/`FrameCodec`/`FrameReader`), chunk/reassembly
(`Chunker`/`Reassembler`), payload codecs (`HelloPayload`/`FileOfferPayload`), the protocol facade
(`P2pProtocol`/`DefaultP2pProtocol`/`ProtocolEvent`), limits (`ProtocolConstants`), and the frame trace.

**Overall health: good.** The parsing surfaces are defensively written (length-before-allocation, signed-read
rejection, caps at every buffering point), the 6de50db reassembler rewrite is sound — I traced every
increment/decrement of `totalPendingBytes` and found the accounting exact, with `removePending` genuinely the
single removal path — and the single-`writeFrame`/single-`sendMutex` funnel claimed by the docs is real. No
Critical or High findings. The dominant theme is **asymmetry**: receive-side hardening (caps, skip-paths) far
outpaces send-side validation (PRO-1 is the one Medium — a >512-char local deviceName turns into an
undiagnosable both-sides handshake timeout) and far outpaces test coverage — most of the untrusted-input guards,
including the flagship 8 MiB anti-OOM check, have zero regression tests (they work today; nothing keeps them
working).

Top 3 risks:
1. Hardening guards without tests (P1 rows in §3) — a refactor can silently drop the resource-limit caps or the
   malformed-payload skip policy; nothing would fail until a malformed or buggy peer shows up.
2. Send-side validation gaps (PRO-1, PRO-9) — the SDK can emit wire traffic its own receiver rejects, and the
   failure surfaces as generic timeouts on the wrong machine.
3. Spec drift around the new caps and ACK semantics (PRO-2, PRO-3, PRO-5, PRO-6) — the spec is the locked
   contract for future implementations, and it currently under-specifies exactly the behaviors that close
   sessions.

`CODEBASE_REVIEW_MAP_2026-07.md` describes S6 accurately: file count (20), ownership list, "ReassemblerTest
(14 cases)" (verified: 14 @Test), evictStale-per-read-batch, the parity rule, and the S8 ownership of the two
`StreamingFile*` files in the same package all match the tree. No discrepancies found.
