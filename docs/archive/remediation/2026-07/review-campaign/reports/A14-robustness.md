# A14 — ROBUSTNESS (input validation + resource-limit enforcement) cross-cutting review

Branch `audit/exhaustive-review-2026-06`, HEAD `870bf10`. Reviewer: A14
(ROBUSTNESS dimension). Cross-cutting: owns no files; findings tagged with the
owning section.

**Report-path note.** My assigned slot is `A14`, but `A14-sec.md` is being
written **concurrently** by the resilience / resource-limit reviewer (it was a stub when I
first opened it, then was overwritten mid-review with a full SEC-1..SEC-I2
report). To avoid clobbering a live peer report I write here
(`A14-robustness.md`). The two dimensions overlap heavily; per the campaign
rule my value is **only in NEW findings**, so I deduped against A01–A16 **and**
against the current A14-sec.md content.

## 0. Relationship to the concurrent A14-sec (resilience / resource-limit) report

A14-sec already owns the *resource-limit / volume* half of my question and did
it well: SEC-1 (no inbound admission control / unbounded sessions), SEC-2
(uncapped `PeerRegistry.tracked` + O(n²) republish), SEC-I1 (peer-input-amplified
`FrameReader` O(n²) copy), SEC-I2 (HELLO `platform`/per-transport strings
uncapped). I do **not** re-report those. I independently re-verified the
parsing/limit layer (`FrameCodec`, `Reassembler`, `HelloPayload`,
`FileOfferPayload`, `StreamingFileReceiver`) and concur it is genuinely
well-hardened — no bypass found.

My NEW contribution is on the *input-validation* half they (and the 14 section
reviewers) missed: **one specific untrusted remote string — the discovered
peer-id from an mDNS TXT record — reaches the throwing `PeerId()` constructor on
a platform callback thread with no guard, while the wire-HELLO path that
consumes the identical value was explicitly hardened.** That is RBS-1
(Critical). Two smaller items follow.

## 1. Untrusted-input / resource walk — verdicts for paths NOT already cleared by A14-sec

| Path / file | Untrusted input | My verdict |
|---|---|---|
| `IosLanDiscoveryTransport.kt` emitPeer/emitLostById (`:634`,`:675`) | TXT peer-id | **RBS-1** — `PeerId(pid)` unguarded; empty-value TXT → `PeerId("")` throws on NW queue → crash |
| `JvmLanDiscoveryTransport.kt` serviceResolved/Removed (`:171`,`:134`) | TXT peer-id | **RBS-1** — `PeerId(pid)` unguarded; whitespace peer-id throws on JmDNS listener thread |
| `AndroidLanDiscoveryTransport.kt` serviceResolved/Removed (`:567`,`:524`) | TXT peer-id | **RBS-1** — identical to JVM (lockstep pair) |
| `IosBonjour.txtRecordToMap` (`:70-90`) | TXT bytes | empty/no-value both decode `""` — the enabling quirk for RBS-1 on iOS (parity note owned by A05/DSC-12) |
| `FrameCodec.decode` (127) | frame header/payload | Clean. payloadLen `<0`/`>8MiB`, totalChunks `<=0`, chunkIndex range, `HEADER_SIZE+payloadLen` (no Int overflow — payloadLen capped 8MiB), truncation, unknown-type→skip. |
| `Reassembler.accept` (185) | multi-chunk DATA | Clean/exemplary; dup/range/mismatch reject; per-msg + aggregate caps; `sumOf{toLong}.toInt()` safe (bounded 4MiB). No bypass. |
| `HelloPayload.decode` (59) | HELLO JSON | peerId/appId **`isNotBlank()`+len** validated (`:44-47`) *and* caller-`runCatching` (`DefaultP2pProtocol.kt:154`) → the guarded twin of RBS-1. |
| `FileOfferPayload.decode` (54) | FILE_OFFER JSON | name(4096)/mime(255)/`sizeBytes>=0` validated; caller-`runCatching`. Clean (path-traversal of `name` = A08/FIL-8). |
| `registerManualPeer` (`PeerRegistry.kt:109-151`) | app host/port | Properly validated: `host.isNotBlank()`, `port in 1..65535`. Throw-doc gap = A02/API-18. |
| `IosManualNetworkProvisioningManager` (`:82-106`) | app host/port | Delegates to `registerManualPeer` (validated). Clean. |
| TXT `pv` (`TXT_PROTOCOL_VERSION`) | version string | **Write-only** — advertised but never parsed on receive → no `NumberFormatException` hazard. (dead metadata, not my dimension) |
| remote-string→log sinks (core+transport) | reason/name/`e.message` | **RBS-2** — capped but unsanitized into log lines (core `logger.warn`; transport trace `$name`/`$attrs`) |
| `announceCache` / `IosEndpointRegistry` (`IosLanDiscoveryTransport.kt:176`,`:635`) | discovered peers | **RBS-3** — unbounded transport-layer maps; reinforces A14-sec/SEC-2 (which cites only `PeerRegistry.kt`) |

## 2. Findings

### RBS-1 — Discovered peer-id from an mDNS TXT record reaches `PeerId()` unguarded on all three platforms; an empty/whitespace peer-id crashes the discovery callback (iOS: process crash on malformed discovery input, no appId required)
- Severity: **Critical** | Confidence: Confirmed for the throw and the iOS-crash mechanism (Kotlin/Native: an uncaught exception propagating out of a Kotlin lambda across a C/Objective-C callback boundary terminates the process). **Uncertain** only on the *exact* JmDNS disposition of a listener-thread throw on JVM/Android (silent notification loss vs worker-thread death) — a crafted-advertiser runtime test would settle it; either disposition is already an invariant violation.
- File(s):
  - iOS: `p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDiscoveryTransport.kt:634` (`emitPeer`: `val peerId = PeerId(pid)`), `:675` (`emitLostById`: `val peerId = PeerId(pid)`); enabling decode `IosBonjour.kt:70-90` (empty-value **and** no-value TXT both → `""`); invoked from the browse-results handler `:531-540` running on `dataTransport.queue`.
  - JVM: `p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryTransport.kt:171` (`serviceResolved`), `:134` (`serviceRemoved`).
  - Android (lockstep pair): `p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDiscoveryTransport.kt:567` (`serviceResolved`), `:524` (`serviceRemoved`).
  - Contrast (the guarded twin): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt:44-47` + `internal/protocol/DefaultP2pProtocol.kt:154-157`.
  - Constructor: `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt:27-31` (`require(value.isNotBlank())`).
- Category: bug (input-validation gap → crash / untyped failure)
- Root cause: `PeerId(value)` throws `IllegalArgumentException` when the string
  is blank. The **wire-HELLO** path that consumes a remote peer-id was hardened
  in AUDIT-2026-06 — `HelloPayload.decode` does `require(payload.peerId.isNotBlank() …)`
  (comment: *"Validate untrusted peer-supplied fields before they flow into
  PeerId / session id"*) and its caller wraps the decode in `runCatching`. The
  **discovery/TXT** path — the *first* place a remote peer-id is trusted —
  applies **neither** guard. The peer-id string is read straight from the TXT
  record and passed to `PeerId(pid)` inline in the platform discovery callback:
  ```kotlin
  // IosLanDiscoveryTransport.emitPeer (iOS)   — no isNotBlank, no runCatching
  val pid = attrs[LanConstants.TXT_PEER_ID]      // empty TXT value → ""
  if (pid == null) { … return }                  // "" passes the null check
  … appId/self filters …
  val peerId = PeerId(pid)                        // PeerId("") → throws on the NW queue
  ```
- Trigger reachability (per platform):
  - **iOS Lost path — no appId secret required.** `nw_browser` tracks every
    `_p2pkit._tcp` instance regardless of TXT contents. When such an instance is
    withdrawn, `handleBrowseResultChange` calls `emitLost` → `emitLostById(pid)`,
    and `emitLostById` (`:674-680`) does **only** a self-check — **no appId
    gate** — before `PeerId(pid)`. So a non-conforming or buggy LAN device that advertises
    `_p2pkit._tcp` with an **empty peer-id TXT value** (any appId, or none) and
    then stops advertising drives `PeerId("")` on the dispatch queue → uncaught
    K/N exception → **process termination**. (The Found path `emitPeer` filters
    appId at `:616-622` *before* `PeerId`, so it is appId-gated; the removal path
    is not.)
  - **JVM / Android.** JmDNS `getPropertyString` returns `"true"` for an
    empty-value TXT key (so `""` does not reach `PeerId` here), but a
    **whitespace** peer-id (`"   "`) survives verbatim → `PeerId("   ")` throws.
    `serviceResolved` is appId-gated first; `serviceRemoved` (`:134`/`:524`) is
    **not** appId-gated — only self-checked — so a whitespace peer-id in a
    removed record throws on the JmDNS listener thread with no appId needed. Best
    case JmDNS logs-and-drops the notification (untyped failure, peer silently
    lost, no `P2pError`); worst case the dispatch thread dies and discovery
    degrades.
- Evidence: quoted above; all six call sites enumerated by grep and read.
- Runtime impact: iOS — a same-LAN device can crash every P2pKit-iOS instance in
  range (no shared secret required via the removal path). JVM/Android —
  discovery-thread disruption / silent peer loss with no typed error. Violates
  the codebase invariant *"typed failures … no silent swallowing … never crash
  on malformed LAN input."* | Platforms: all (iOS worst) | User-visible: yes
  (crash / discovery stops)
- Failure class: crash (iOS) / untyped-failure + silent-drop (JVM/Android)
- Relationship to catalogued items: **NEW.** A02/API-17 flagged only the
  *contract* (blank `PeerId`/`AppId` is a throw hazard for network strings) and
  **explicitly deferred the call sites**: *"the risky call sites are
  transport-side (outside this scope) and flagged for those reviewers."* The
  transport reviewers did not pick it up — A05/DSC-11 is the *Lost-appId-filter
  spoofing* angle and DSC-12 is *TXT-decode parity / deviceName length*; neither
  is the `PeerId()`-throws crash. A04/IDN-4 is about the *local* stored peer-id,
  not discovered remote ids. A14-sec does not cover it (its scope is
  limits/volume). So this call-site defect is unreported.
- Proposed fix (do NOT implement): mirror the HELLO guard at the discovery
  boundary — validate `pid.isNotBlank()` (and optionally length ≤ `MAX_FIELD_LEN`)
  before constructing `PeerId`, skipping the record on failure; and/or wrap each
  discovery callback body in `runCatching { … }.onFailure { log }` so a
  malformed record can never throw out of a JmDNS listener or an NW dispatch
  block. Apply to all six sites (Found + Lost × 3 platforms), keeping JVM/Android
  in lockstep. No public-API change.
- Required tests: (1) transport-lan `iosSimulatorArm64Test` — advertise a
  service with an empty-value `peer-id` TXT, then stop; assert the kit does not
  crash and the record is skipped. (2) `JvmLanLoopbackTest` — advertise a
  whitespace peer-id (resolved and removed); assert no exception escapes and no
  bogus `PeerEvent` is emitted. (3) unit: a `parsePeerRecord` helper (if
  extracted) rejects blank/whitespace and returns null.

### RBS-2 — Remote-controlled strings reach SDK log lines unsanitized (core `logger.warn` + transport trace); no sanitization and no logger-contract warning
- Severity: **Low** | Confidence: Confirmed (code paths); real-world impact depends on the app-supplied `P2pLogger` sink (default is NoOp)
- File(s): `p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:536` (`logger.warn("Session $id: peer error: ${event.reason}")`); `protocol/DefaultP2pProtocol.kt:155` and `:174` (`"Skipping malformed HELLO/FILE_OFFER frame: ${e.message …}"` — `e.message` can embed peer-supplied JSON fragments); transport trace `IosLanDiscoveryTransport.kt:600` (`"emitPeer: txt=$attrs"`) and `:653` (`$name`), `JvmLanDiscoveryTransport.kt:170-185`/`AndroidLanDiscoveryTransport.kt:566-583` (candidate/name lines).
- Category: bug (defensive gap along the "…or a log line?" arm of the review question)
- Root cause: the ERROR/reject `reason` is length-capped (1024 B via
  `decodeReasonCapped`) but **not** stripped of control characters / newlines,
  and it flows into the injectable `P2pLogger`. The transport trace embeds the
  remote `deviceName` (`$name`) and the whole TXT map (`$attrs`) verbatim. A peer
  can therefore inject `\n`-delimited forged log lines or terminal escape
  sequences into any file/console sink an app wires behind `P2pLogger` (or into
  the trace, which CLAUDE.md says is default-off in the SDK but **on in all
  samples**).
- Runtime impact: log forging / terminal-escape injection when the SDK's logs
  land in a terminal or shared log store. | Platforms: all | User-visible: only
  via the logging sink
- Relationship to catalogued items: A16/SMP-6 fixed this for the **sample**
  app's own `stderr`/`logcat` prints and noted the fix was applied "only to the
  CLI". The **SDK-core / transport** instances above are a *different layer*
  (the SDK's own diagnostics, not sample UI code) and are not covered by SMP-6.
- Proposed fix (do NOT implement): sanitize remote strings (strip/escape CR/LF
  and C0 control chars, ideally single-line-truncate) before they enter any
  `logger.*` or trace call; and document in the `P2pLogger` KDoc that message
  arguments may contain remote-controlled content. No API change.
- Required tests: unit — a sanitizer helper maps `"a\nFAKE LOG"` → a single
  escaped line; a peer ERROR reason with embedded newlines produces one log line.

## 3. Improvements (not defects)

### RBS-3 — iOS transport-layer discovery maps (`announceCache`, `IosEndpointRegistry`) are unbounded — reinforces A14-sec/SEC-2 one layer down
- `announceCache` (`IosLanDiscoveryTransport.kt:176`, grown at `:650`) and
  `endpointRegistry` (`:635`) add an entry per discovered peer and remove only on
  `Lost` (`:676-677`) — the same unbounded-under-high-volume profile as
  `PeerRegistry.tracked`. A14-sec/SEC-2 cites only `PeerRegistry.kt`; a mDNS
  a high volume of Found events inflates these two transport maps in lockstep. Fix alongside SEC-2
  (cap + oldest-eviction, or bound by the same per-source limit). Improvement,
  not a separate defect — same root high-volume condition as SEC-2.

## 4. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| A blank/empty/whitespace TXT peer-id never throws out of a discovery callback (skipped, no crash) | RBS-1 — iOS crash on malformed discovery input; untyped failure JVM/Android | transport-lan `iosSimulatorArm64Test` + `JvmLanLoopbackTest` | integration | P1 |
| A removed record with an empty peer-id does not crash iOS (Lost path, no appId gate) | RBS-1 — the no-appId-secret iOS trigger | transport-lan `iosSimulatorArm64Test` | integration | P1 |
| Remote reason/name strings are single-lined/escaped before logging | RBS-2 — log forging via app logger sink | commonTest (sanitizer unit) | unit | P3 |
| iOS `announceCache`/`endpointRegistry` stay bounded under a high volume of Found events | RBS-3 / SEC-2 | appleTest | unit | P3 |

## 5. Section summary

**What this cross-cutting pass owns:** input validation + resource-limit
enforcement for every byte/string the SDK ingests from the network or another
process, before it reaches app code / a collection / a file path / a log line.

**Overall health:** the **content-validation and per-unit limit layer is
strong** — the AUDIT-2026-06 caps and the JSON-field guards are exemplary and I
found no bypass, and A14-sec has thoroughly covered the *volume/admission* gaps
(SEC-1/2). The one material hole along my dimension is a **boundary asymmetry**:
the same untrusted peer-id value is rigorously validated on the wire-HELLO path
but trusted raw on the mDNS-discovery path, producing a crash-grade
input-validation defect (RBS-1) that every prior reviewer missed because A02
explicitly punted the call sites to the transport reviewers and the transport
reviewers read the discovery files for *spoofing/parity*, not for *"does this
string throw when constructed"*.

**Top 3 risks:**
1. RBS-1 — unguarded `PeerId()` from mDNS TXT → iOS process
   crash on malformed discovery input (no appId required via the Lost path) + untyped discovery-thread failure
   on JVM/Android. **Critical, NEW.**
2. (A14-sec) SEC-1 — no inbound admission control. Already reported; I concur.
3. (A14-sec) SEC-2 — uncapped peer registry; RBS-3 extends it to the iOS
   transport's own maps.

**Map accuracy (`CODEBASE_REVIEW_MAP_2026-07.md`):** accurate for this
dimension. RBS-1 lands in S5 (discovery, flagged High) and is the concrete
crash the map's "malformed-input coverage is the review question" note
anticipates; it should be filed against S5 with an A04/API-17 cross-reference
(the deferred contract that named the hazard but not the call sites). No map
edits required.
