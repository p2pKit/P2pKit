# P2pKit — Gap Analysis & Roadmap to a Production-Ready, Generic P2P Library

Date: 2026-07-03 · Basis: v0.6-dev source on `audit/exhaustive-review-2026-06` (12 commits ahead of `main`, unmerged) · Method: full source audit of the public API / wire protocol / SPI / platform impls / build, cross-checked against the repo's own trackers (PROBLEMS_P2PKIT.md, AUDIT_REPORT_2026-06.md, STABILIZATION_AND_RELEASE.md, production-readiness.md, INTERNAL_TESTING.md, 24 open GitHub issues).

> **Status (committed 2026-07-04, decision #1a):** this is a **point-in-time**
> strategic gap analysis of the 2026-07-03 tree, committed to the repo for
> preservation. Where its findings overlap the 2026-07 review campaign,
> `CODEBASE_FINDINGS_2026-07.md` is the authoritative register and supersedes
> this document — a number of items below have since been remediated on this
> branch. Two corrections were applied at commit time (the §4.3
> `incomingSessions` claim and the P7 real-network-test gating suggestion);
> the rest of the text is unedited.

**Scope note:** this evaluates P2pKit as a *general-purpose* nearby-communication SDK. A consuming app (e.g. Kira Manga's local-sharing feature) appears only as a stress-test of genericity in §5 — nothing app-specific is proposed for the SDK.

---

## 1. Executive summary

P2pKit's bones are genuinely good: a clean transport-agnostic public API (`Peer`/`P2pSession`/flows, no callbacks), a disciplined binary wire format identical across Android/JVM/iOS, a session layer that has survived two exhaustive self-audits (all 12 criticals across both waves fixed), real reconnect hardening proven on physical devices (v0.4–v0.6 Wi-Fi-flap work), streaming file transfer with progress/cancel on all platforms, and an honesty culture (typed `Unsupported`, documented platform limits) that most SDKs never reach.

What separates it from a **strong, reusable, production-ready** library is not one big thing but six pillars, in dependency order:

| # | Pillar | One-line state |
|---|---|---|
| P0 | **Release engineering & repo state** | Unreleasable today: hardening branch unmerged, zero CI, no remote publish target, device matrix never executed, no consumer R8 rules, no API-stability tooling |
| P1 | **Security & trust** | Not just "encryption missing" — the `SecurityManager` seam is dead as wired (read path bypasses it; hook sits after the cleartext HELLO); inbound identity unverified |
| P2 | **Transfer robustness** | No resume, no integrity hash, receiver writes block the session's control loop, no stall timeout — each one a per-app workaround today |
| P3 | **Protocol honesty & compatibility** | `P2pMessage.metadata` is public API that silently never transmits; "version negotiation" is exact-equality; TXT protocol-version written but never read |
| P4 | **Generic app-protocol ergonomics** | Every consumer must hand-roll correlation, typed payloads, and metadata side-channels — the strongest genericity lever is making these SDK features |
| P5 | **Platform/lifecycle polish + SPI maturity** | Interface selection (VPN-NIC bug, live-confirmed), iOS AWDL asymmetry, fixed-delay reconnect, no background helpers; SPI is TCP-shaped and would fight BLE/Multipeer/Relay |

Suggested arc: **v0.7 ship-ability → v0.8 transfer/protocol completeness → v0.9 security → v1.0 stability contract → v1.x transport expansion** (§6). The single most important near-term action is P0 — everything else is polish on a library nobody can consume.

---

## 2. What is already strong (keep, don't churn)

- **API shape** — small surface, coroutines/`Flow` everywhere, DSL config, `@Throws` for Swift, `@RequiresOptIn` already used for experimental surfaces (`ExperimentalP2pApi`). The spec (`P2pKit-Spec.md`) treats the API as a contract.
- **Wire discipline** — one binary format (magic `PP2K`, versioned 36-byte header, big-endian), identical Bonjour service type + TXT keys across three OS stacks; unknown frame types skip-not-kill; `ignoreUnknownKeys` on JSON control payloads leaves additive room.
- **Session-layer correctness work** — `SessionStore` single source of truth, one `transitionToTerminal` codepath, simultaneous-open arbitration in the SDK, connect dedup, epoch-scoped connections, CAS-final transfer states, post-audit DoS caps (8 MiB frame, reassembly aggregate caps), malformed-control-frame isolation, outgoing-dial identity check, write watchdogs/timeouts.
- **Reconnect machinery** — endpoint re-resolution per attempt, discovery force-refresh loop through the whole `Reconnecting` window, network-path early wake, stuck watchdog; real-device validated through Wi-Fi-flap cycles including the cellular-interface edge (v0.6).
- **Test culture** — 28 commonTest files driven by proper fakes; real-socket loopback suites on JVM **and** iOS simulator (incl. SHA-256-verified 5 MiB file); consumer-loopback test in `sample-kmp-shared`.
- **Self-knowledge** — two audits totaling 600+ findings with severities and per-item fix specs; an RC checklist; honest known-limitations docs. Most of §3 below is *aggregation and prioritization* of what the project already knows, plus a handful of findings the trackers don't have (marked **NEW**).

---

## 3. Gap analysis

Severity key: 🔴 blocks any production release · 🟠 blocks "strong/reusable" status · 🟡 quality/competitiveness gap.

### P0 — Release engineering & repo state 🔴

The library cannot currently be adopted by anyone, including its own author's other projects, without manual steps that have never been exercised end-to-end.

| Gap | Evidence | What "done" looks like |
|---|---|---|
| Hardening branch unmerged | `audit/exhaustive-review-2026-06` is 12 commits ahead of `main` (all critical fixes, publishing, RC checklist live only there); no v0.6 or RC tag | Merge to `main`, tag `v0.6.0-rc1` per the existing STABILIZATION checklist |
| **No CI at all** | `.github/` absent | GitHub Actions: JVM+Android compile & test, `iosSimulatorArm64Test` on a macOS runner, lint of the samples, `publishToMavenLocal` dry-run, artifact upload on tag. Real-network loopback tests need a multicast-capable runner or a gated tag (see P8) |
| No remote publish target | `gradle.properties:5-9` concedes only `publishToMavenLocal` works; signing/POMs done but upload never smoke-tested | Central Portal (or GitHub Packages first) wired + one real publish dry-run; KMP modules need the missing javadoc jar (empty-javadoc is acceptable to Central; only the desktop module has one today) |
| No consumer R8/ProGuard rules | Zero `consumer-rules.pro` in repo; JmDNS + kotlinx-serialization under host-app minification = release-only crashes for every Android consumer | `consumerProguardFiles` in `:p2p-core` and `:p2p-transport-lan` covering serialization + JmDNS reflection surface; a minified-sample smoke test |
| No API-stability tooling | No `explicitApi()`, no kotlinx binary-compatibility-validator, no Dokka (greps: 0 hits) | `explicitApi()` on library modules (code already uses `public` by convention — cheap), BCV with checked-in `.api` dumps, Dokka HTML published per release |
| Device-validation program never executed | RC matrix A1–A12 all `▢`; INTERNAL_TESTING §4 all 15 boxes unchecked; §H/§I hotspot verification pending since v0.2.1 and gating three tags | One recorded pass of the existing runbooks on ≥2 Android devices + 1 iPhone + 1 desktop, results committed (the runbooks already define PASS/FAIL templates — they just need to be run) |
| Missing packaging hygiene | No `AndroidManifest.xml` in `:p2p-transport-lan` declaring the permissions the transport needs (consumers must copy them from README); XCFramework has no SPM `Package.swift`/podspec for Swift-only consumers | Manifest with the 4 install-time permissions merged automatically; an SPM binary-target manifest published alongside the XCFramework |
| Tracker hygiene | 24 open GitHub issues (mostly pre-audit `needs-real-device-validation`), 1 stale open PR (#46, likely superseded) | Triage sweep: close what the audit branch fixed, convert the rest into the roadmap milestones below |

### P1 — Security & trust 🔴 (for any untrusted-network posture) / 🟠 (for consented same-LAN apps)

The spec's security *design* is right (connection-wrapping `SecurityManager`, `TrustedDeviceStore`, PairingCode/QrCode modes, X25519+HKDF+AEAD). The gap is that the implementation seam has drifted from the design:

- **NEW — the seam is dead as wired.** The frame-reader coroutine starts collecting `rawConnection.read()` *before* the security wrap, and `RawConnection.read()` is single-collector — so a `SecureConnection` that decrypts in `read()` would never see a byte; writes go through the wrapper but reads bypass it (`SessionManager.kt:280-293` vs `:347`). A real handshake that needs its own byte exchange can't run either (the frame reader already owns the stream). Implementing encryption is therefore a **re-plumb of `runHandshake`/connection ownership**, not just a new `SecurityManager` — schedule it as such.
- **Hook is after the cleartext HELLO** — appId, peerId, deviceName, platform leak before security engages (`SessionManager.kt:296` → `:347`). The encrypted design should run the key handshake first and move HELLO inside the tunnel.
- **No injection point**: DSL `security { }` exposes only `mode`; `P2pKitImpl` hardcodes `NoOpSecurityManager` (`Builders.kt:194`, `P2pKitImpl.kt:66,95`) — even an app willing to bring its own crypto can't.
- **Identity is claim-based**: PeerId is a random UUID with no key material; inbound HELLO peerId trusted at face value (`SessionManager.kt:336` `TODO(encryption-milestone)`) — a rogue LAN peer sharing the appId can claim any peerId and hijack its session slot. TXT records (name/platform/caps) are likewise unauthenticated display data.
- **Residual input-hardening tail**: file-offer `name` sanitization still partial (`"../../etc/x"` passes decode — receivers must never treat it as a path, but the SDK should ship `sanitizedFileName()` + doc), mDNS TXT value validation, per-frame version byte policy (deliberate today; needs a documented decision at v1.0).

What "done" looks like (staying generic): per-peer identity keypair + fingerprint persisted alongside PeerId; handshake-first connection bring-up; `SecurityMode.PairingCode`/`QrCode` with `TrustedDeviceStore` (app-pluggable storage); session tickets optional later; `SecurityManager` injectable for BYO-crypto; HELLO inside the tunnel; downgrade protection (mode advertised in TXT + enforced both sides). None of this needs public-API changes beyond the already-spec'd types — the spec had this right.

### P2 — Transfer robustness 🟠

The streaming core is solid (chunked, never whole-file in memory, both-side progress, CAS-terminal states, offer timeout, reconnect-safe teardown). Four gaps force every serious consumer to build the same workarounds:

1. **No resume.** No offset in `FileOfferPayload`; receiver hardwired to chunk 0 (`StreamingFileReceiver.kt:32`). Any drop = restart from zero; apps degrade to item-granular retry. *Done:* offer carries `resumeOffset` negotiated from the receiver's accept (receiver states how many verified bytes it already has); sender seeks its `RawSource` (API addition: `sendFile(..., source, resumeFrom)` or a seekable-source capability interface). Additive JSON fields — wire-compatible via `ignoreUnknownKeys`.
2. **No integrity.** No hash slot in the offer, no per-frame checksum; TCP protects transit but not truncation/app bugs/(future) unreliable transports. *Done:* optional `contentHash` (algo-tagged) on the offer; SDK verifies incrementally on receive and fails the transfer on mismatch; per-frame CRC32 deferred to the unreliable-transport work (P5/SPI) where it belongs.
3. **`blocking-sink-write-on-route-loop`** (known-open High): inbound `FILE_DATA` → `sink.write` runs on the same coroutine that services PING/PONG/CLOSE (`P2pSessionImpl.kt:533` → `StreamingFileReceiver.kt:62`); a slow sink stalls keep-alive and backpressures the socket through the 256-event channel. The fix is already specified in PROBLEMS (per-transfer bounded-channel writer) — the offer path even shows the pattern (`FileTransferDispatcher.kt:346-350`). *Done:* per-transfer writer coroutine + bounded channel, slow-receiver policy (suspend sender via flow control vs fail transfer) documented.
4. **Accepted-but-stalled transfers never time out** (Medium :440) and the **sink-close contract** is implicit (SDK flushes, never closes — correct, but under-documented; abort paths should guarantee no further writes). *Done:* configurable inactivity timeout per transfer; KDoc the sink ownership contract; add `Failed(TimedOut)` state.

Also worth deciding here: concurrent-transfer policy (unbounded outgoing today, no fairness across transfers sharing one `sendMutex`) — cap + round-robin interleave, or document the single-flight recommendation.

### P3 — Protocol honesty & compatibility 🟠

- **NEW — `P2pMessage.metadata` is silently dropped.** Public constructor field on `Text`/`Binary`, never serialized (`Chunker.kt:29-31`), always empty on receive (`Reassembler.kt:124-126`). This is the worst kind of API dishonesty — code compiles, runs, and loses data. *Fix (pick one):* transmit it (length-capped JSON side-block in the DATA frame — also the foundation for P4), or remove/deprecate the field until it transmits. Shipping v0.7 without deciding this would be a mistake.
- **NEW — `incomingSessions` replay contradicts its KDoc** (`P2pKit.kt:85-87` says eager subscribers won't miss sessions; impl is replay=0 buffer-64 — a subscriber attached even a frame late misses the session; the iOS sample's poll workaround is a symptom). *Fix:* replay a bounded window (or a `pendingSessions: StateFlow` snapshot) + align docs.
- **Version negotiation doesn't negotiate.** HELLO check is exact int equality (`Handshake.kt:69-75`); the TXT `pv` key is advertised by all three platforms but never read on browse. *Done:* `minSupported..current` range in HELLO; discovery-time pre-filter on TXT `pv` (peers you can't talk to shouldn't appear connectable); a written compat policy (what a frame-version bump means; when `ignoreUnknownKeys` suffices vs a version gate) — this is the contract app protocols will rely on.
- **Hardcoded protocol knobs**: 10 s HELLO timeout (`Handshake.kt:36`), message chunk size, reassembly timeouts — fine defaults, but per-transport tuning (P5) needs them injectable; expose in the DSL where meaningful, keep the DoS caps compile-time.
- **Reassembler eviction is read-driven only** (a silent peer's partials live until keep-alive kills the session) — attach eviction to the keep-alive tick, cheap.
- **Normative protocol spec**: the wire format lives in code + CLAUDE.md prose. *Done:* a versioned `PROTOCOL.md` (frame layout, control payload schemas, state machines, compat rules) — required the moment two independently-shipped app versions must interoperate, and the artifact third-party transport authors will code against.

### P4 — Generic app-protocol ergonomics 🟠 (the "stay generic" pillar)

Observation from the first real consumer design (manga sharing): the app had to invent (a) a JSON envelope protocol with type+version+correlation ids over `P2pMessage.Text`, (b) a metadata side-channel for offers, (c) hash verification, (d) its own request/response matching. **Every** nontrivial consumer will rebuild exactly these four things. Making them SDK features is what turns P2pKit from "transport + file pipe" into a *platform*, and none of them require domain awareness:

1. **Transmitted, bounded message metadata** (fixes the P3 honesty bug and gives every message a typed-tag channel: `metadata: Map<String,String>`, size-capped, documented).
2. **Offer metadata**: `sendFile(..., metadata: Map<String,String>)` → `P2pFileOffer.metadata`. Additive JSON field; kills the "describe the file in a separate message and correlate by name" dance. (Name stays display-only; the metadata map is where apps put their correlation keys.)
3. **Request/response correlation helper**: `suspend session.request(payload, timeout): P2pMessage` + `session.answers { request -> response }` built on a reserved metadata key — optional sugar, massively reduces consumer protocol boilerplate, trivially implementable over the existing DATA path.
4. **Optional typed-payload module** (`:p2p-serialization`): `session.send(serializer, value)` / `incoming.decode(serializer)` with kotlinx-serialization — keeps `:p2p-core` dependency-light while giving 90% of apps their envelope layer for free.
5. **Bounded app-defined peer extras** in the TXT record (`advertising { extras = mapOf(...) }` → `Peer.extras`), with a documented byte budget (TXT records are ~255 B/key, total-size constrained) — the classic Bonjour pattern; lets apps advertise capability hints without connecting.
6. **AppId isolation hardening**: today every P2pKit app shares `_p2pkit._tcp` and filters by TXT appId — cross-app discovery noise scales with adoption, and iOS requires each consumer to declare the service type anyway. *Option:* derived service type (`_p2pkit-<hash8(appId)>._tcp`) as an opt-in, documented iOS `NSBonjourServices` implication. Keep the default for wire simplicity; decide before v1.0 because it's discovery-breaking later.

Guardrail for all of P4: features land as *capability primitives* (maps, correlation, serializers) — never domain vocabulary. If a proposed API mentions files-with-chapters, libraries, or any consumer concept, it belongs in the consumer.

### P5 — Lifecycle & platform polish 🟠→🟡

Known-open items, ordered by consumer pain:

- **Interface selection (Issue #2, live-confirmed)**: JVM JmDNS binds via default heuristic — bound `utun5` (VPN) on the dev Mac; Android binds active-network IPv4 but JVM has no rebind on network rotation. *Done:* routable-interface picker (skip loopback/virtual/VPN unless only option), JVM rotation rebind, an explicit `lan { bindInterface/bindAddress }` escape hatch.
- **iOS AWDL asymmetry (Issue #3)**: browser opts into peer-to-peer (AWDL) but listener/dials don't — AWDL-discovered peers may be undialable. Decide: enable `include_peer_to_peer` symmetrically (validated on hardware) or stop browsing it.
- **Reconnect maturity**: still fixed-delay — the already-designed exponential backoff + jitter (production-readiness §2); plus an opt-in policy for *incoming*-session reconnect (today: remote must redial — correct default, but one-sided links surprise consumers); document that iOS's listener port rotates on rebind (peers must re-resolve — the refresh loop handles it, but transport authors need the invariant).
- **Background lifecycle helpers**: `BackgroundPolicy` is close-or-nothing and `notifyAppForegrounded` is log-only; the designed `IosBackgroundTaskGuard` (finish in-flight transfers in a BG task window) and an Android foreground-service recipe/sample don't exist. These are the difference between "transfers die when the screen locks" and a shippable UX for consumers.
- **Construction-thread I/O** (open High): PeerId disk read/write on the `create{}` caller thread — move behind the first suspend point or a lazy async load.
- **NEW — no dispatcher/scope injection**: kit scope is hardcoded `Dispatchers.Default` (`P2pKitImpl.kt:78`) — untestable-under-virtual-time and rude to host apps with their own threading policy; add an optional `dispatcher`/`parentScope` DSL knob.
- **Android path observer not auto-wired** (default NoOp even though `AndroidNetworkPathObserver` exists and `P2pKitAndroid.initialize` could supply the Context) — auto-wire when initialized, keep manual override.
- **Hotspot-join fragility**: `onLost` tears down the join with no debounce/grace (open half of a High), and the whole provisioning path has never been device-verified (§H/§I) — gate the provisioning modules behind `@ExperimentalP2pApi` until A9 passes.
- **Maintainability**: JVM/Android transports are hand-synced near-duplicates ("keep both copies in sync" comments) — extract a `jvmCommonMain`; `ConnectionState.Closing` declared but never emitted (emit or remove); `appKilledPolicy`/`securityMode` plumbed-but-unused (`@Suppress("unused")`) — implement or drop before the API freeze; macOS native target decision (JVM covers macOS desktop; a native target only matters for SwiftUI-mac consumers — explicitly defer).

**SPI maturity for the transport roadmap** (BLE / Wi-Fi Direct / Multipeer / Relay are the stated v0.4+ vision — the current SPI would fight all four):
- Address model is TCP-shaped (`TransportHint(host, port)`, `HasLocalTcpEndpoint`); iOS already routes around it with an out-of-band endpoint registry — replace with an opaque per-transport `TransportEndpoint` the transport itself resolves.
- Reliable-ordered-stream assumption is baked in (no per-frame integrity, FILE_DATA strictly in-order, ACK plumbing exists but is dead code) — define the reliability contract at the SPI (`RawConnection.isReliableOrdered`; SDK activates ACK/ordering layer when false).
- No MTU/preferred-chunk hint, no per-transport handshake/keep-alive tuning, `TransportKind` is a closed enum, selection is single-winner with no failover, and `TransportContext` has no logger slot (the root cause of the three ad-hoc debug singletons). All cheap to fix *before* a second transport exists, expensive after.

### P6 — Observability & diagnosability 🟡

- `P2pLogger` = 4 methods, no levels/tags/structure; transports grew three divergent debug channels (`FrameTrace` process-global, `JvmLanDiag` sysprop, `IosLanDebug` object, raw unconditional `Log.d` on Android). *Done:* leveled+tagged logger, `TransportContext.logger`, one per-kit trace facility replacing the singletons (keep sysprop bridges for field debugging).
- No metrics API. *Done (small):* `P2pKitStats` snapshot + flows — session counts, per-session RTT (PINGs already exist — just timestamp them), bytes/frames in/out, transfer throughput, discovery event counts, reconnect attempt histogram. This is what consumers need for support tickets ("no peers found", "slow transfer") — pair it with a `diagnosticsSnapshot(): String` dump for bug reports (the LAN_DIAGNOSTICS runbooks show exactly which fields matter).

### P7 — Testing & QA infrastructure 🟡 (multiplier for everything above)

- CI matrix (P0) plus: **instrumented Android tests** (none exist — the Android LAN path is review+manual only), **separation of real-network tests** (the iOS loopback suite runs real Bonjour with 30–120 s timeouts in the default unit cycle — worth moving real-network suites into their own Gradle task/source set so the unit cycle is deterministic; per the repo's known-flaky policy the two simulator churn tests must **never** be `@Ignore`d or otherwise masked — they stay visible in their suite, with the peer-Lost path validated on real hardware via smoke-matrix row A4), strengthen the weak arbitration test (asserts count, not direction/loser-closed/round-trip — known-open High).
- **Codec/protocol fuzzing**: FrameReader/Reassembler/JSON payload decoders against malformed/adversarial input (the DoS fixes exist; fuzz locks them), property-based chunker/reassembler round-trips.
- **Soak & churn**: N-peer discovery churn, 1000-message soak, parallel transfers + reconnect storm (the runbook's Test 5) as automated JVM loopback where possible.
- **Performance baseline**: throughput benchmark (loopback + real LAN) with regression thresholds — consumers will ask "how fast is it" and today there is no answer.

### P8 — Documentation & DX 🟡

- Dokka API site + versioned `PROTOCOL.md` (P3) + a real integration guide per platform (Android incl. R8, JVM, iOS-via-SPM/XCFramework incl. Info.plist keys and the local-network prompt UX, Compose samples as living docs).
- A stated **semver + deprecation policy** and the BCV gate to enforce it — "reusable" means consumers can upgrade without fear.
- README truth-sync is already good; keep the honest platform-limits tables (they are a differentiator).

---

## 4. Findings NOT in the project's own trackers (net-new from this review)

1. `P2pMessage.metadata` accepted but never transmitted (silent data loss; API honesty).
2. `SecurityManager` read-path seam is dead as wired (frame reader owns the raw stream pre-wrap; single-collector `read()`); hook placed after cleartext HELLO; no injection point despite the spec's extension-point claim.
3. `incomingSessions` late-subscriber semantics. *Corrected at commit time (2026-07-04, verified against the tree):* the original claim here — that replay=0 "contradicts" the KDoc — is inaccurate. `P2pKit.kt`'s promise is explicitly scoped to **eager** subscription ("sessions are not silently dropped if subscribed eagerly"), and that promise holds: inbound sessions can only be emitted after the transports start, so a collector attached before `start()` cannot miss one, and with a collector attached the flow's `SUSPEND` overflow policy never drops. Only a subscriber attached *after* sessions were already emitted misses them (ordinary replay=0 semantics). The real subscription-window trap is the per-session `incoming` message flow on incoming sessions — documented in spec §10 and the README per decision #13b. The longer form of this claim in §3/P3 above should be read with this correction.
4. TXT `pv` written by all three advertisers, read by none.
5. Kit dispatcher/scope not injectable.
6. `ConnectionState.Closing` never emitted; `appKilledPolicy`/`securityMode` dead config.
7. TXT-derived service-type isolation question (all P2pKit apps share one Bonjour type) — needs a pre-1.0 decision.
8. KMP modules missing javadoc jars for Central; no SPM manifest for the XCFramework; no merged AndroidManifest permissions in the transport module.

---

## 5. Genericity cross-check (using manga-sharing as the stress case)

The consumer plan (Kira `LOCAL_MANGA_SHARING_PLAN.md`) needed: peer discovery+consent UX (✅ have), streaming file send (✅ have), **metadata on offers** (P4.2), **integrity hash** (P2.2), **resume** (P2.1), **request/response control protocol** (P4.3/P4.4), **non-blocking receive sinks** (P2.3), **encryption eventually** (P1). Every one of these generalizes — the SDK never needs to know what a manga, chapter, or CBZ is. Conversely, the things that SHOULD stay in the consumer forever: content manifests/schemas, staging/import pipelines, dedupe against app databases, consent dialogs, storage quotas. That boundary — *capability primitives in the SDK, domain protocols in the app* — is the definition of "generic" this roadmap protects.

---

## 6. Roadmap

Each phase has a theme, exit criteria, and only additive/compatible wire changes until v1.0.

### v0.7 — "Anyone can consume it" (P0, ~1–2 weeks of focused work + one device-day)
Merge the audit branch → CI (JVM/Android/iOS-sim test + assemble + publish dry-run) → consumer ProGuard rules + transport AndroidManifest → `explicitApi()` + BCV baseline + Dokka → javadoc jars + remote repo (GitHub Packages first, Central when ready) → gate real-network tests out of the unit cycle → execute the A1–A12 device matrix once and record results → triage the 24 open issues → tag `v0.7.0`.
**Quick wins to fold in** (small, high leverage): decide `P2pMessage.metadata` (transmit or deprecate), fix `incomingSessions` replay/KDoc, move PeerId I/O off the construct thread, make the HELLO timeout configurable, emit-or-remove `Closing`, auto-wire the Android path observer, keep-alive-driven reassembler eviction.
*Exit: a version an external app adds from a Maven repo and ships to stores without folklore.*

### v0.8 — "Transfers and protocols you can build products on" (P2 + P3 + P4)
Per-transfer bounded writer (kills the route-loop stall) → offer `metadata` + optional `contentHash` with SDK-side incremental verify → resume offsets → transfer stall timeout + sink-contract docs → transmitted message metadata → request/response helper → `:p2p-serialization` module → version-range negotiation + TXT `pv` pre-filter → `PROTOCOL.md` v1 → backoff+jitter + optional incoming-session reconnect → interface-selection fix (Issue #2) + AWDL decision (Issue #3) on hardware.
*Exit: the manga-sharing class of app needs zero protocol workarounds; two app versions interoperate across an SDK minor.*

### v0.9 — "Trustworthy by default" (P1)
Connection bring-up re-plumb (handshake owns the stream before the frame reader; HELLO inside the tunnel) → per-peer identity keys + fingerprints → `PairingCode`/`QrCode` modes + `TrustedDeviceStore` → injectable `SecurityManager` → downgrade protection → filename-sanitization completion + TXT validation sweep → threat-model doc (what LAN adversaries can/can't do in each mode).
*Exit: plaintext is an explicit opt-in (`NoneForMvp` renamed to say so), not the silent default.*

### v1.0 — "Stability contract"
API freeze behind BCV, semver + deprecation policy published, docs site complete, background-lifecycle helpers (iOS BG-task guard, Android FGS recipe/sample) landed, `jvmCommonMain` dedup done, per-app service-type decision made, performance baseline published, RC checklist green including a full device-matrix pass.
*Exit: consumers upgrade minors blind.*

### v1.x — "More ways to meet" (P5-SPI, then transports)
SPI rework first (opaque endpoints, reliability contract + activated ACK layer, MTU hints, per-transport tuning, failover, logger in context, `TransportKind` extensibility) — **before** the second transport, while there's still only one implementation to migrate. Then, in the order of consumer value: Wi-Fi Direct (Android↔Android offline) / Multipeer (Apple↔Apple offline) → BLE (discovery + small messages) → Relay (internet fallback; brings its own auth requirements — depends on v0.9 identity). macOS native target opportunistically.

---

## 7. Anti-goals (how the library stays generic while serving demanding consumers)

1. **No domain types, ever** — the API vocabulary stops at peers, sessions, messages, files, metadata maps.
2. **App needs arrive as capability primitives** — metadata, correlation, serializers, hashes, offsets; if a feature request can't be phrased without a consumer's nouns, it's the consumer's code.
3. **Optional modules over core growth** — serialization sugar, provisioning, future transports stay separate artifacts; `:p2p-core` keeps its dependency budget (coroutines + serialization + kotlinx-io).
4. **Defaults tuned for the class of use, knobs for the instance** — caps/timeouts configurable with documented safe ranges; never tuned to one app's payload profile.
5. **Honesty is the brand** — keep surfacing `Unsupported`/limits/threat-model truthfully; a generic library's reputation is exactly its documentation's accuracy.

---

*Prepared as analysis only — no code changes made. Suggested first action: the v0.7 P0 block, starting with merging `audit/exhaustive-review-2026-06`.*
