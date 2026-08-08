# A4-IDENTITY — Peer identity & provenance (S4) review

Scope: 16 files (9 sources, 7 tests) under `p2p-core/src/`, reviewed at HEAD `870bf10` on
`audit/exhaustive-review-2026-06`. Cross-checked call sites in `SessionManager.kt`,
`P2pKitImpl.kt`, `Handshake.kt`, `Internal.kt`, `ManualPeerRegistrar.kt`, `Builders.kt`,
`Identity.kt`, and `JvmLanDiscoveryTransport.kt` (Lost-event provenance). Read-only; no
build/test run.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| commonMain/…/internal/PeerRegistry.kt | 186 | findings: IDN-1, IDN-2, IDN-3; improvements: IDN-7, IDN-9 | PeerRegistryTest (discovered-peer paths); ManualPeerIdentityTest (indirect, via connect) | Zero registry-level manual-peer tests: no eviction-exemption, no dedupe, no Lost-vs-manual, no peers-flow no-churn test |
| commonMain/…/internal/PeerIdStorage.kt | 34 | improvements: IDN-6 (KDoc omits iOS backend) | PeerIdPersistenceIntegrationTest (contract, indirectly) | Contract ("stable id on repeated calls") only pinned for JVM + in-memory impls |
| commonMain/…/internal/InMemoryPeerIdStorage.kt | 27 | improvements: IDN-9 (plain `var cached`; internal-only knob, single construction-time call) | InMemoryPeerIdStorageTest | None needed beyond existing (see IDN-9 note) |
| androidMain/…/internal/FilePeerIdStorage.kt | 74 | findings: IDN-4, IDN-6 | **None** — p2p-core has no Android unit-test source set (`src/` holds only commonTest+jvmTest) | Entire class untested; jvm twin's tests do not compile against it |
| jvmMain/…/internal/FilePeerIdStorage.kt | 125 | findings: IDN-4 | FilePeerIdStorageTest, PeerIdPersistenceIntegrationTest | Legacy `p2pkit`→`.p2pkit` migration (AUDIT-2026-06 behavior) has zero coverage; no unreadable-file or non-blank-garbage case |
| iosMain/…/internal/NSUserDefaultsPeerIdStorage.kt | 77 | findings: IDN-4 (shared); note: read path has no try/catch unlike JVM/Android — moot in practice, K/N `catch` cannot intercept ObjC exceptions and `stringForKey` doesn't throw, so the write-side try/catch (:48-56) is likewise decorative | **None** — no iosTest source set, despite the injectable `defaults` ctor param built for testing (:28) | Entire class + `sanitizeAppIdForKey` untested |
| androidMain/…/internal/PeerIdStorageFactory.android.kt | 19 | clean — loud warn + InMemory fallback matches the PeerIdStorage.kt:30-32 contract | None | Fallback-warn path untestable until an Android test target exists |
| jvmMain/…/internal/PeerIdStorageFactory.jvm.kt | 11 | clean — note: an empty (not null) `user.home` property skips the tmpdir fallback and yields a CWD-relative `.p2pkit`; pathological, not reported | None (indirect via integration test only when default is used — tests always override) | None pressing |
| iosMain/…/internal/PeerIdStorageFactory.ios.kt | 7 | clean | None | Trivial; covered transitively if iOS storage tests are added |
| commonTest/…/internal/PeerRegistryTest.kt | 221 | improvements: coverage gaps (see §3 rows 1-4) | n/a (is a test) | Only discovered-peer semantics tested; the entire manual-peer/provenance surface of PeerRegistry is unpinned |
| commonTest/…/internal/ManualPeerIdentityTest.kt | 231 | clean as written; nit: the "discovered-provenance" spoof test (:171-196) actually exercises P2pKitImpl.connect's registry-miss fallback (`internalPeer()` returns null → synthesized `InternalPeer` with default `Discovered` origin), not a registry entry created by a discovery event — same origin value, different code path than the comment claims | n/a | Add a variant where the manual-looking id enters via `PeerEvent.Found` (§3 row 11) |
| commonTest/…/internal/HandshakeIdentityTest.kt | 144 | clean; hidden-failure nit: in `connectRejectsWhenRemoteClaimsOurOwnPeerId` the acceptor side also rejects, but that is never asserted — `handleIncoming` swallows into `logger.warn` (NoOp in tests), so an acceptor-side regression would pass | n/a | Assert acceptor-side rejection (§3 row 10) |
| commonTest/…/internal/LocalIdentityTest.kt | 74 | clean — pins construction-time identity exposure and per-kit independence | n/a | None |
| commonTest/…/internal/InMemoryPeerIdStorageTest.kt | 30 | clean — pins stability, uniqueness, seed | n/a | None |
| jvmTest/…/internal/FilePeerIdStorageTest.kt | 86 | clean as far as it goes; blank-content, traversal, per-appId isolation all asserted | n/a | Missing: migration, non-blank garbage, unreadable file (§3 rows 6, 9, 12) |
| jvmTest/…/internal/PeerIdPersistenceIntegrationTest.kt | 151 | clean; asserts (a) storage round-trip across kit instances and (b) the kit calls `loadOrGenerate()` exactly once at construction (:94) — (b) is what makes the storages' lack of internal synchronization acceptable. Nit: test 1 compares the two *storages*' ids (:69-73), not `kitOne.localPeerId == kitTwo.localPeerId`; the direct kit-level assertion would pin the user-visible invariant without relying on test 2 | n/a | Add the kit-level `localPeerId` equality assertion |

## 2. Findings

### IDN-1 — PeerRegistry event path enforces no provenance invariants: Found/Updated can overwrite (and demote) a Manual entry, Lost can remove one, and event-carried `origin` is trusted verbatim
- Severity: Low | Confidence: Confirmed (code paths); reachability assessment below is reasoning, marked where uncertain
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:79-88; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/Internal.kt:35-40; corroborating: p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryTransport.kt:129-135
- Category: bug (defensive/invariant gap)
- Root cause: `processEvent` treats every `PeerEvent` uniformly by `PeerId` key with no origin check:
- Evidence:
  ```kotlin
  is PeerEvent.Found -> current + (event.peer.publicPeer.id to TrackedPeer(event.peer, clock()))
  is PeerEvent.Updated -> current + (event.peer.publicPeer.id to TrackedPeer(event.peer, clock()))
  is PeerEvent.Lost -> current - event.peerId          // PeerRegistry.kt:82-84
  ```
  and `TrackedPeer.isManual` is derived solely from the stored `internalPeer.origin` (:185), which for event-sourced entries is whatever the transport put in the `InternalPeer` (`origin` defaults to `Discovered`, Internal.kt:39, but is settable by any transport since the SPI is public).
  Three consequences: (a) a Found/Updated whose id collides with a manual entry replaces it wholesale — origin demoted to `Discovered` (entry becomes evictable and loses the SessionManager HELLO-mismatch exemption), host/port hints replaced, lastSeen reset; (b) a Lost with a manual id deletes the eviction-exempt entry (`current - event.peerId` applies to manual entries too); (c) a transport could emit `origin = PeerOrigin.Manual` and mint an eviction-exempt, mismatch-exempt entry the registry never created.
- **Registry-side verdict on the discovery reviewer's flag** (asked for explicitly): the flagged path is real — `JvmLanDiscoveryTransport.serviceRemoved` emits `Lost(PeerId(pid))` from the TXT `pid` with **no appId filter** (:130-134; `serviceResolved` does require the app TXT), and PeerRegistry applies it to manual entries unconditionally. However, I assess it as **not practically spoofable against manual entries**: the synthetic id is `"manual-" + Uuid.random()` (PeerRegistry.kt:133), a locally-minted CSPRNG UUID that never leaves the device — HELLO carries the *local* peer's id, not the dialer's alias for the remote; no TXT record, frame, or log (`take(8)` truncation in registerSession logging) exposes it. A remote peer cannot learn or guess the 122 random bits, so LAN-sourced collision requires a buggy or non-conforming *transport module*, which is app-linked trusted code. The unfiltered-Lost spoof is a real concern for **discovered** peers (whose ids are broadcast) — that is the discovery section's finding, not an identity one. Net: agree on mechanism, disagree on manual-entry reachability; still worth a one-line defense because the eviction-exemption and mismatch-exemption invariants currently rest on nothing but id unguessability.
- Runtime impact: none under shipped transports and honest LANs; under a colliding event, manual peer silently vanishes (Lost) or becomes a strange evictable hybrid (Found). Live sessions are unaffected (SessionReconnectHandler falls back to `originalInternalPeer`); a later `connect(manualPeer)` after eviction takes the P2pKitImpl.kt:386-392 fallback (hints without host/port) and fails typed. | Platforms: all | User-visible: only in the colliding case
- Failure class: spoofing (theoretical) / none in practice
- Proposed fix (do NOT implement): in `processEvent`, ignore any event whose `peerId` resolves to an existing entry with `origin == Manual` (covers Found/Updated/Lost in one guard), and coerce event-sourced `InternalPeer.origin` to `Discovered` (or log-and-drop) so transports cannot mint Manual provenance.
- Required tests: PeerRegistryTest — Lost with a manual id leaves the entry; Found/Updated with a manual id neither replaces hints nor demotes origin; a Found carrying `origin = Manual` is stored as Discovered (or dropped).

### IDN-2 — registerManualPeer dedupe is check-then-act: concurrent same-endpoint registrations mint duplicate permanent entries
- Severity: Low | Confidence: Confirmed (race window is plain in the code; likelihood assessment is judgment)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:126-149
- Category: bug
- Root cause: the dedupe lookup reads `tracked.value` outside the atomic update that inserts:
- Evidence:
  ```kotlin
  val existing = tracked.value.values.firstOrNull { t ->            // :126 — read
      t.isManual && t.internalPeer.transportHints.any { … } }
  if (existing != null) return existing.internalPeer.publicPeer
  …
  tracked.update { current -> current + (syntheticId to TrackedPeer(internal, clock())) }  // :148 — write
  ```
  Two threads registering the same `(host, port, kind)` can both miss the lookup and both insert, defeating exactly the unbounded-growth bug the dedupe comment (:120-125) says it exists to prevent — and manual entries are eviction-exempt, so duplicates persist until `kit.stop()`. Each duplicate has its own synthetic id, so `connect()` on each creates a separate session to the same device.
- Runtime impact: duplicate manual peers in `kit.peers` + possible double sessions to one endpoint; requires concurrent registration of the same endpoint (e.g. UI button + provisioning retry loop racing), so the window is narrow. | Platforms: all | User-visible: yes when hit
- Failure class: none (bounded duplication)
- Proposed fix (do NOT implement): perform lookup-or-insert inside a single `tracked.update` block (compute `existing` from `current`; the CAS-retried lambda stays side-effect-safe if the `syntheticId`/`clock()` mint is hoisted or tolerated), returning the pre-existing peer via a captured var; or serialize `registerManualPeer` with a plain Mutex — it is not a hot path.
- Required tests: PeerRegistryTest — N concurrent `registerManualPeer(same endpoint)` calls yield exactly one tracked entry (use a multithreaded dispatcher + latch); sequential repeat returns the identical `Peer` (also pins the currently untested happy-path dedupe, see IDN-5).

### IDN-3 — publishPeers read-then-assign race can publish a stale peers list over a newer one (self-heals within one eviction poll)
- Severity: Low | Confidence: Confirmed as a possible interleaving by code reading; Uncertain how often real schedules hit it (a stress test with two racing event coroutines on Dispatchers.Default would settle it)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:90-93 (with callers :87, :105, :149)
- Category: bug
- Root cause: `tracked.update` is atomic, but the follow-up publish is a separate non-atomic read-compare-assign:
- Evidence:
  ```kotlin
  private fun publishPeers() {
      val newList = tracked.value.values.map { it.internalPeer.publicPeer }
      if (_peers.value != newList) _peers.value = newList
  }
  ```
  Interleaving: coroutine A (Found p1) updates `tracked` and computes `newListA=[p1]`; coroutine B (Lost p1) then updates `tracked` to `{}`, publishes `[]`; A resumes and assigns `[p1]`. End state: `tracked = {}` but `_peers = [p1]`. Concurrency is real: the kit scope is `Dispatchers.Default` (P2pKitImpl.kt:79), and `processEvent` (event collectors), `registerManualPeer` (caller thread), and `evictStalePeers` (evict loop) all call `publishPeers` concurrently. The divergence is bounded: `evictLoop` → `evictStalePeers` → `publishPeers` runs unconditionally every `evictionPollMillis` (1 s default) and recomputes from `tracked`, repairing `_peers`.
- Runtime impact: `kit.peers` can show a just-lost peer (or hide a just-found one) for up to ~1 s; `internalPeer()`/`lastSeen()` read `tracked` directly, so connect/reconnect resolution is unaffected. | Platforms: all | User-visible: yes (transient UI ghost)
- Failure class: none (transient inconsistency)
- Proposed fix (do NOT implement): make the publish ordered — e.g. guard `publishPeers` with a small lock, or have each mutator pass the map returned by its own `update` through a monotonic-generation gate; simplest is computing the list inside a `_peers.update { }` that re-reads `tracked.value` (same read, but assign via CAS against a captured generation counter).
- Required tests: stress test — interleave Found/Lost bursts from two coroutines, then assert `peers.value` matches `tracked`-derived state after quiescence *without* waiting for an eviction tick (tick disabled via large `evictionPollMillis`).

### IDN-4 — No storage backend validates loaded peer-id content beyond "non-blank"; a corrupt-but-nonblank value becomes the advertised identity (and the JVM KDoc overclaims "unparseable → overwritten")
- Severity: Low | Confidence: Confirmed for the storage/PeerId code; Uncertain on the exact JmDNS/NWListener failure mode for oversized TXT values (a manual test with a 300-char peer-id file would settle whether it truncates, throws, or drops the record)
- File(s): p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt:68-77 (and KDoc :14-16), p2p-core/src/androidMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt:30-42, p2p-core/src/iosMain/kotlin/dev/p2pkit/core/internal/NSUserDefaultsPeerIdStorage.kt:39-43; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt:27-31
- Category: bug (defensive gap + doc mismatch)
- Root cause: all three read paths accept any trimmed non-empty string as the identity; `PeerId` itself only requires `isNotBlank()`:
- Evidence:
  ```kotlin
  val content = file.readText().trim()
  if (content.isBlank()) null else PeerId(content)      // jvm FilePeerIdStorage.kt:71-72 (android :33-34, ios :41-42 analogous)
  ```
  ```kotlin
  public value class PeerId(public val value: String) { init { require(value.isNotBlank()) … } }  // Identity.kt:27-31
  ```
  The JVM KDoc claims "If the file ever exists but is empty or **unparseable**, it's overwritten on the next loadOrGenerate" (:15-16) — nothing parses the content; only blank triggers regeneration. A tampered/corrupted file containing e.g. 10 KB of text, interior control characters, or newlines mid-string (trim only strips the ends) is adopted verbatim, then advertised as the mDNS TXT `pid` value (`LanConstants.TXT_PEER_ID`), where individual TXT key=value pairs are capped at ~255 bytes — the advertised id can truncate or the record fail while HELLO carries the full string, producing "peerId mismatch" rejections on every inbound connect with no hint of the root cause. `readText()` also loads an arbitrarily large corrupt file into memory.
- Runtime impact: local-tamper/disk-corruption edge; device becomes undiscoverable-or-unconnectable with a maximally confusing symptom. | Platforms: all three (identical gap — the one behavioral parity divergence found is the iOS read path lacking the JVM/Android try/catch, which is moot since K/N `catch` cannot intercept ObjC exceptions and `stringForKey` does not throw) | User-visible: yes when hit
- Failure class: none (availability/diagnosability)
- Proposed fix (do NOT implement): shared sanity check applied identically on all three read paths — accept only ids of bounded length (e.g. ≤ 128 chars) with no ISO control characters, otherwise warn + regenerate (matching the documented "unparseable" contract); optionally clamp at generation too.
- Required tests: FilePeerIdStorageTest (jvm) — 300-char and control-character files regenerate + overwrite; mirrored cases if/when Android/iOS test targets exist (§3 rows 7-8).

### IDN-5 — The "registerManualPeer has no host:port dedupe — deferred" record is stale: dedupe has existed since b9f6311, contradicting REMEDIATION_2026-07.md and the review map (and the dedupe itself is untested)
- Severity: Low | Confidence: Confirmed (git history)
- File(s): REMEDIATION_2026-07.md:63; CODEBASE_REVIEW_MAP_2026-07.md:132-134; code: p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:117-131
- Category: bug (documentation of record contradicts shipped behavior)
- Root cause: commit `b9f6311` (2026-06-12, "…manual-peer dedup…") implemented dedupe by `(host, port, kind)` — `git show b9f6311` commit message: "registerManualPeer dedups by host:port:kind (session-scoped, in-memory)…" — but the 2026-07 remediation report still lists it under "Deliberately deferred":
- Evidence:
  ```
  REMEDIATION_2026-07.md:63 — "Repeated `createManualPeer(host,port)` still mints a fresh id
  with no `(host,port)` dedup — noted by the original audit as deferred; unchanged here."
  ```
  vs. PeerRegistry.kt:126-131 (`val existing = tracked.value.values.firstOrNull { … it.host == host && it.port == port } … if (existing != null) return …`). The per-agent BRIEF's catalogued-decision list carries the same stale line. Aggravating factor: **nothing pins the dedupe** — PeerRegistryTest has no manual-peer test, ManualPeerIdentityTest registers each endpoint once, and the desktop provisioning tests use a fake registrar (JvmNetworkProvisioningManagerTest) — so doc and code disagree with no test arbitrating.
- Runtime impact: none at runtime; a future maintainer following the doc of record may re-implement, mis-assess risk, or silently regress the untested behavior. | Platforms: n/a | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): correct REMEDIATION_2026-07.md:63 and the map's S4 deferral list to state the dedupe landed in `b9f6311` (only the fresh-id *format* per new endpoint remains true); add the pinning test.
- Required tests: PeerRegistryTest — repeated `registerManualPeer(same host, port, kind)` returns the same `Peer` (same id) and leaves exactly one tracked entry; different endpoint mints a new one.

### IDN-6 — Android FilePeerIdStorage header still claims it is a same-semantics "copy" of the JVM file that will "converge" — following that instruction now would orphan every Android install's identity
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/androidMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt:9-13, :20; p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt:35, :38-40, :59-66; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerIdStorage.kt:25-33
- Category: bug (doc drift with foot-gun potential)
- Root cause: since `b9f6311`, the JVM implementation moved to hidden `<root>/.p2pkit/...` **with a one-time legacy migration** from `<root>/p2pkit/...`; the Android implementation intentionally stayed at `<filesDir>/p2pkit/...` with **no migration** — correct, because Android's path never changed and `filesDir` needs no hidden dir (this directly answers the scope question "does Android migrate?" — no, and it should not). But the Android header was not updated:
- Evidence:
  ```kotlin
  /**
   * Android copy of the JVM [FilePeerIdStorage]. Same `java.io.File` semantics;
   * duplicated because :p2p-core does not ship a `jvmAndroidMain` intermediate
   * source set in v0.2. If/when one is added, the two copies converge.
   */                                                    // androidMain FilePeerIdStorage.kt:9-13
  private val storageDir: File = File(File(rootDir, "p2pkit"), …)   // :20  (jvm twin: ".p2pkit", :35)
  ```
  The files are no longer copies (path constant + 50 lines of migration logic differ). A future "converge them" refactor that adopts the JVM file verbatim silently changes every Android device's storage path from `p2pkit` to `.p2pkit` — the JVM migration would mask it on desktop while Android identities churn (remote peers see a stranger; old sessions' ids never re-appear). Secondary: the common `defaultPeerIdStorage` KDoc (PeerIdStorage.kt:25-33) documents JVM, Android, and Android-without-init but omits the iOS NSUserDefaults backend entirely.
- Runtime impact: none today; identity loss across the entire Android install base if the comment is followed naively. | Platforms: Android (risk), iOS (doc omission) | User-visible: no (until triggered)
- Failure class: none (latent data-loss-of-identity foot-gun)
- Proposed fix (do NOT implement): rewrite the Android header to state the deliberate divergence ("Android stays at `<filesDir>/p2pkit`; do NOT adopt the JVM `.p2pkit` path without an Android-side migration"); add the iOS line to the `defaultPeerIdStorage` KDoc. Behavioral write-path parity (tmp + rename + fallback, warn-and-continue) is otherwise intact between the two files and should be called out as the part that must stay in lockstep.
- Required tests: none (doc); the JVM migration itself needs a test regardless (§3 row 6).

## Improvements

### IDN-7 — No unregister/expiry path for manual peers; dedupe-hit silently ignores a new deviceName
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/ManualPeerRegistrar.kt:24-43; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:126-131
- Category: improvement
- Detail: `ManualPeerRegistrar` exposes only `registerManualPeer`; a mistyped IP produces a peer that sits in `kit.peers` (eviction-exempt) until `kit.stop()` with no way to remove it. Session-scoping (AUDIT-2026-06 comment, :123-125) bounds the damage to one run. Also, re-registering an endpoint with a different `deviceName` returns the old entry with the old display name — the new name is silently dropped. `[API-CHANGE]` a `unregisterManualPeer(peerId)` would be the clean fix; no-API-change alternative: document the lifetime explicitly in the registrar KDoc and refresh the stored display name on dedupe-hit (registry-internal, no surface change).
- Required tests: dedupe-hit-with-new-name behavior, whichever way it is decided.

### IDN-8 — Manual-peer handshake is silently exempt from the mismatch check: log the remote's actual HELLO id; `lastSeen` KDoc wrong for manual peers
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:344-352; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pKit.kt:171-172; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:61
- Category: improvement
- Detail: for `isManualPeer` sessions the peerId-mismatch check is skipped (by design) and `resolvedPeer` keeps the synthetic identity — so the remote's *real* HELLO peerId is discarded without a trace. One `logger.info("manual peer <synthetic> answered with real id <hello.peerId>")` would make "the DHCP lease moved and a different device now answers this IP" (including on every reconnect re-handshake, :552-556) diagnosable; today only the own-id guard stands between a manual session and a silent stranger, which is inherent to manual-IP semantics but currently also invisible. Separately, `P2pKit.lastSeen` KDoc says "Last time the peer … was observed by discovery" — for manual peers it returns the registration timestamp forever (no heartbeats), so an app renders a healthy manual peer as "last seen hours ago".
- Required tests: none (logging/doc); optionally assert the log line in ManualPeerIdentityTest via a capturing logger.

### IDN-9 — Minor robustness nits: evictLoop swallows Throwable with no logger; InMemoryPeerIdStorage uses a plain `var`
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt:158-164; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/InMemoryPeerIdStorage.kt:18-26
- Category: improvement
- Detail: (a) the evict loop's catch block is deliberately silent ("No logger here by design") because PeerRegistry has no logger — but the codebase convention is "no silent swallowing"; P2pKitImpl already holds the logger one line above the registry construction (P2pKitImpl.kt:148-152), so threading it in is free. CancellationException is correctly rethrown. (b) `InMemoryPeerIdStorage.cached` is an unsynchronized `var`; harmless today because `loadOrGenerate` is called exactly once at kit construction (P2pKitImpl.kt:543, pinned by PeerIdPersistenceIntegrationTest:94) and the `peerIdStorage` knob is `internal` (Builders.kt:71), but a comment or `@Volatile` would keep it honest if the knob ever goes public.

## Scope-question verdicts not covered above

- **Is `origin = Manual` set exactly once?** Yes in shipped code — the only assignment is PeerRegistry.kt:146; shipped transports never reference `PeerOrigin` (grep over p2p-transport-lan: zero hits), so all event-sourced peers default to `Discovered` (Internal.kt:39). The gap is that the registry does not *enforce* this (IDN-1c).
- **Eviction driver:** verified. `PeerRegistry.start()` (:70-77) launches `evictLoop` on the kit scope; called from P2pKitImpl's init (:185); the scope dies via `internalJob.cancel()` in `stop()` (:470). Note the loop starts at kit *construction*, before `start()` — harmless (one 1 s timer). The loop delays first, then sweeps; `while (scope.isActive)` + rethrown CancellationException terminate it cleanly.
- **Handshake identity checks — weakened or strengthened by the new code?** Strengthened. 012e49e: outgoing sessions now *always* keep the dialed identity (SessionManager.kt:367-376), the manual exemption is provenance-driven (:186, :344-347, threaded through reconnect at :552-556), the own-peerId guard is intact and applies to manual connects (:356-359, pinned by ManualPeerIdentityTest:199-225), and appId/version rejection in `performHandshake` (Handshake.kt:63-75) is untouched (pinned by HandshakeTest:78). The inbound-HELLO-peerId deferral is unchanged, comment intact (SessionManager.kt:360-366) `[CATALOGUED]`.
- **Identity churn across restarts (storage loses the id):** handled gracefully by the identity layer — every persistence failure warns loudly ("PeerId will not survive restart"); on the remote side the old id ages out of the registry in 15 s and a redial to it fails with a *typed* `HandshakeRejected("peerId mismatch")`, so churn degrades to "a new device appeared", never a wrong-peer session. The three backends behave identically for missing storage (generate+persist), blank content (regenerate+overwrite), and unwritable storage (warn + ephemeral id); the un-validated non-blank-corrupt case is IDN-4. iOS additionally has the (accepted) platform quirk that `NSUserDefaults` persists asynchronously — a crash immediately after first launch can lose the id once; not reported as a finding.
- **`connect()` fallback provenance:** a peer absent from the registry gets a synthesized `InternalPeer` with default `Discovered` origin and host-less hints (P2pKitImpl.kt:386-392) — correct direction of failure: an unknown peer can never acquire the manual exemption, and the dial fails typed for want of an address.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| 1. Manual peers are exempt from staleness eviction (survive `evictStalePeers` after clock advance) | Manual peers have no heartbeats; a regression makes every manual peer vanish 15 s after registration | PeerRegistryTest | unit | P1 |
| 2. `registerManualPeer` dedupes by (host, port, kind): repeat returns the same Peer, one tracked entry | Doc-of-record contradiction (IDN-5); currently nothing pins it against regression | PeerRegistryTest | unit | P1 |
| 3. JVM legacy migration `<root>/p2pkit` → `<root>/.p2pkit` adopts and re-persists the old id | AUDIT-2026-06 identity-preserving behavior with zero coverage; silent breakage = desktop identity churn | jvmTest FilePeerIdStorageTest | unit | P1 |
| 4. Lost/Found/Updated colliding with a manual entry does not remove/overwrite/demote it (post-IDN-1 fix) | Pins the provenance invariants the origin model exists for | PeerRegistryTest | unit | P2 |
| 5. `peers` flow does not re-emit on heartbeat (Updated with identical payload) | KDoc-promised de-noising (PeerRegistry.kt:54-58) is unpinned | PeerRegistryTest (count emissions) | unit | P2 |
| 6. Concurrent same-endpoint `registerManualPeer` yields one entry (IDN-2) | Guards the dedupe against the check-then-act race | PeerRegistryTest (multithreaded dispatcher) | unit | P2 |
| 7. Android `FilePeerIdStorage` + factory fallback behavior (no test target exists at all) | A 74-line divergent twin with zero compilable tests; parity asserted only by eyeball | new p2p-core Android host-test source set (or converged source set + shared tests) | unit | P2 |
| 8. iOS `NSUserDefaultsPeerIdStorage` load/generate/blank/regenerate via injected suite | Injectable `defaults` ctor exists precisely for this; currently dead test surface | new p2p-core iosTest source set | unit | P2 |
| 9. Acceptor-side own-peerId rejection (no session registered, nothing emitted on `incomingSessions`) | Currently only the dialer side is asserted; acceptor regression hides behind NoOp logger | HandshakeIdentityTest | combination | P2 |
| 10. Manual-looking id arriving via a real `PeerEvent.Found` (registry entry, origin=Discovered) is rejected on mismatch | Current spoof test exercises the registry-miss fallback path, not the discovered-entry path its comment describes | ManualPeerIdentityTest + FakeDiscoveryTransport | combination | P2 |
| 11. Oversized / control-character peer-id file → regenerate (post-IDN-4) or documented current behavior | Corrupt-non-blank is the one corrupt class with no defined behavior | jvmTest FilePeerIdStorageTest | unit | P2 |
| 12. Unreadable storage file (chmod 000) → warn + ephemeral id, no throw | "Unwritable/unreadable storage" contract asserted nowhere | jvmTest FilePeerIdStorageTest | unit | P3 |
| 13. `kitOne.localPeerId == kitTwo.localPeerId` direct assertion in the persistence integration test | Pins the user-visible invariant without inference via the tracking test | PeerIdPersistenceIntegrationTest | integration | P3 |

## 4. Section summary

**What S4 owns:** the peer registry (aggregation, dedupe, staleness, manual-peer provenance) and the only persistent state in the SDK — the local peer-id, across three per-platform storage backends plus the in-memory fallback, and the identity checks those feed (HELLO mismatch/own-id/appId, provenance-keyed manual exemption).

**Overall health: good.** The 012e49e provenance fix is sound where it matters: origin is minted in exactly one place, derived (not duplicated) into `isManual`, threaded through connect and reconnect, and the dialed-identity rule plus own-id guard are correctly pinned by ManualPeerIdentityTest/HandshakeIdentityTest. The catalogued inbound-HELLO deferral is unchanged. No Critical or High findings; the six bugs are defensive gaps, narrow races, and doc drift.

**Top 3 risks:**
1. **Registry enforces no provenance invariants on the event path** (IDN-1) — today protected only by the unguessability of the synthetic uuid; one cheap guard closes Found/Updated/Lost and transport-minted `Manual` in one place.
2. **The manual-peer registry surface is entirely untested at the registry level** (eviction exemption, dedupe, Lost interplay — §3 rows 1, 2, 4) while the docs of record (REMEDIATION_2026-07.md, review map) actively misdescribe the dedupe as absent (IDN-5): code, docs, and tests currently form a triangle in which any silent regression re-validates the wrong doc.
3. **The Android/JVM storage twins have silently diverged under a header that still says "identical, converge later"** (IDN-6), and Android/iOS storage has zero compilable tests (§3 rows 7-8) — the exact setup in which a well-meaning refactor churns the entire Android install base's identity.

**CODEBASE_REVIEW_MAP_2026-07.md accuracy for S4:** substantially accurate (file list, dependency edges, "3 storage backends must behave identically", jvm-only corrupt-path coverage, Medium-High risk call). Discrepancies: (1) the "Known deliberate deferrals" bullet repeats the stale "no host:port dedupe" claim — dedupe has existed since b9f6311 (IDN-5); (2) "Test coverage: good on registry/identity" overstates the registry side — the manual-peer/provenance half of PeerRegistry has no direct tests at all; (3) "storage … partially covered (jvm only)" is itself generous: the jvm coverage also omits the legacy migration, the one identity-preserving behavior the JVM file uniquely carries.
