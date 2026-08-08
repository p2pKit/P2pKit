# P2pKit full source-code review

Review date: 2026-07-17

Reviewed commit: 6a05ccd04fcb6fb8106ed47941618fb6bcfd3fa6

## Executive conclusion

P2pKit is not ready for a production release on an untrusted or failure-prone network.

No finding was classified Critical, but there are multiple High-severity correctness, availability, data-integrity, security, and release defects. The most important are:

1. The shipped security mode is plaintext and unauthenticated, inbound identity is trusted, and the current security extension point cannot safely add encryption because the protocol reader starts on the raw connection first.
2. Kit lifecycle operations can outlive stop(), reopen resources, or publish a session after terminal shutdown.
3. Discovery aggregation is wrong for multiple transports: one transport can erase or overwrite another transport's live peer contribution.
4. FrameReader performs remotely triggerable quadratic copying.
5. File transfer can report Completed before receiver durability is known; the forced verification run actually observed Completed when cancellation was expected.
6. Accepted inbound transfers have no idle or overall timeout and race cancellation against sink I/O.
7. Apple LAN uses an unbounded live-connection channel and has several restoration, cancellation, peer-cache, and listener lifecycle failures.
8. Published dependency metadata omits compile-time dependencies used in public APIs.
9. Android hotspot/join provisioning has state/resource contradictions and cancellation races.
10. The sample receivers auto-accept untrusted files without consent, quota, or free-space checks; the iOS sample can silently discard disk-write failures while reporting success.
11. The checked-in Gradle wrapper JAR is an official older wrapper, not the 9.3.1 wrapper named by the properties file.
12. The full verification gate is red: Android lint fails, one forced JVM core test fails, one iOS core test times out, and two iOS LAN lifecycle tests time out.

The codebase has substantial test coverage and many thoughtful defensive comments, but several tests currently pin known-bad behavior or allow nondeterministic outcomes. Passing ordinary happy-path tests is therefore not a sufficient release signal.

The detailed register below contains 150 findings across core runtime, protocol, transfer, LAN, provisioning, samples, and build/release tooling.

## Scope and method

The project was split into these independently reviewed features:

- public API, configuration, DSL, errors, state, identity, logging
- kit lifecycle, discovery aggregation, sessions, reconnect, network-path recovery
- wire framing, protocol codec, handshake, messages, keepalive
- file-offer and streaming transfer state machines
- LAN discovery/data transports on JVM, Android, and Apple
- Android and desktop network provisioning
- Android, JVM, and iOS platform storage/observer adapters
- Android, desktop CLI, desktop UI, KMP, and Swift sample applications
- every test and fixture associated with those features
- every non-document build file, manifest, run configuration, script, version catalog, wrapper component, and publication configuration

Coverage:

| Area | Files reviewed |
| --- | ---: |
| Root files | 7 |
| IDE run configurations | 7 |
| Gradle support | 4 |
| iosApp | 6 |
| p2p-core | 132 |
| Android provisioning | 9 |
| Desktop provisioning | 6 |
| Android sample | 6 |
| Desktop CLI sample | 2 |
| Desktop UI sample | 4 |
| LAN transport | 40 |
| KMP sample | 7 |
| Scripts | 2 |
| Total | 232 |

The text portion is 39,033 lines. The tracked Gradle wrapper JAR was inspected as a binary archive, CRC/integrity checked, inventoried, hashed, and compared with official wrapper checksums; it was not misrepresented as source-reviewed.

Per the request not to read documentation, the review excluded all 26 tracked Markdown files, the entire docs/ tree including its seven non-Markdown code/log/config mirrors, and LICENSE. Those exclusions total 34 unique tracked files from the 266-file repository. Existing untracked .review-2026-07/ and DEFERRED_ITEMS_REGISTER_2026-07.md were not read or changed.

This was a source/configuration/build review, not a real-device certification or an online third-party vulnerability-advisory scan. The verification section states exactly what ran.

Severity meanings:

- High: can break security assumptions, corrupt or lose data, exhaust resources remotely, invalidate public consumption, or violate terminal lifecycle guarantees.
- Medium: real correctness/reliability defect with narrower conditions or an important release/portability gap.
- Low: hardening, diagnostics, maintainability, sample ergonomics, or a deliberately limited behavior that should be made explicit.

## Feature verdict summary

| Feature | Verdict |
| --- | --- |
| Public API and Maven consumption | Blocked by incorrect API dependency scopes |
| Security | Plaintext/unauthenticated MVP only; extension architecture is not usable for real security |
| Kit lifecycle | Stop/start/connect races and partial rollback gaps |
| Discovery and identity | Multi-transport aggregation and persistent-ID creation are unsafe |
| Sessions and messages | Cancellation, deduplication, backpressure, and terminal cleanup defects |
| Protocol parser | Functional tests are broad, but DoS/validation hardening is insufficient |
| File transfer | Not reliable for durability, cancellation, idle peers, or concurrent sink operations |
| LAN JVM | Builds and isolated tests pass; runtime cancellation/rotation/cleanup defects remain |
| LAN Android | Compiles; real platform behavior lacks instrumentation coverage and has network-selection gaps |
| LAN Apple | Builds; lifecycle tests fail and several production lifecycle defects are confirmed |
| Android provisioning | Fake-wrapper tests pass; real callback/permission/resource races remain |
| Desktop provisioning | Works as an approximation; interface selection and configuration validation are weak |
| Samples | Compile, but teach unsafe receive/lifecycle patterns |
| Release tooling | Artifact shape passes; remote upload, correct metadata, signatures gate, reproducibility, CI, and supply-chain controls are incomplete |

## Detailed findings: core runtime, API, identity, and sessions

### CORE-01 — High — stop() does not serialize terminal lifecycle with ongoing operations

Evidence: p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt:364-437 and 466-545.

startAdvertising(), startDiscovery(), and connect() pass ensureStarted() and then do their real work outside its mutex. stop() can set Stopped, tear down resources, and cancel the internal job while one of those calls continues. A late advertising failure can overwrite Stopped with Failed, and a late connect can register a session after closeAllSessions() took its snapshot.

Fix: use a single lifecycle gate or generation token through resource creation and final registration. Recheck the generation before committing, and roll back stale work.

### CORE-02 — High — PeerRegistry is not a correct multi-transport aggregator

Evidence: PeerRegistry.kt:70-85.

Transport provenance is discarded. Found/Updated replaces the full record by PeerId, and Lost removes it regardless of another transport still seeing it. A BLE contribution can overwrite LAN hints, and BLE Lost can erase a still-live LAN peer.

Fix: store contributions by PeerId plus discovery-transport instance, merge capabilities/hints, and publish Lost only after the final contribution disappears.

### CORE-03 — High — cancelled connect() can poison coalescing and leak a live session

Evidence: SessionManager.kt:218-246 and 331-361; SessionStore.kt:110-115.

Cleanup calls the suspending endPending() from an already-cancelled finally block. Mutex acquisition can throw before removing the pending slot. Coalesced callers can then join a stale deferred. Cancellation around session.start()/registration has no rollback for an uncommitted handshaked connection.

Fix: preserve CancellationException, complete the deferred consistently, remove pending state in NonCancellable, and close every connection/session not atomically committed.

### CORE-04 — High — application receive backpressure blocks protocol control handling

Evidence: P2pSessionImpl.kt:132-136 and 550-583; SessionManager.kt:401-410.

One event loop suspends while emitting application messages into a bounded SharedFlow. PING, PONG, CLOSE, and ERROR handling sit behind the same suspension. A slow subscriber lets a peer block control processing, trigger false keepalive failure, and retain a large queued byte volume.

Fix: separate control-plane processing from application delivery and use a byte-budgeted queue with an explicit overflow contract.

### CORE-05 — High — duplicate-session arbitration treats every active duplicate as simultaneous-open

Evidence: SessionStore.kt:138-161.

The existing session's direction is not recorded. Repeated same-direction inbound connections can replace a healthy inbound session depending only on lexicographic PeerId ordering, enabling repeated churn without increasing the session count.

Fix: retain direction and apply simultaneous-open arbitration only to opposite-direction candidates; reject same-direction duplicates.

### CORE-06 — High security limitation — peer identity is unauthenticated and traffic is plaintext

Evidence: Config.kt:79-82; SessionManager.kt:459-472; P2pKitImpl.kt:67-68 and 118.

NoneForMvp supplies no encryption or pairing. A LAN participant that knows the app ID can claim another PeerId and target that session slot. This is explicitly an MVP limitation, but it is a production blocker, not merely a future enhancement.

Fix: bind PeerId to authenticated key material, authenticate the handshake, encrypt the byte stream, and document the trust model prominently until then.

### CORE-07 — Medium architecture — the security extension point cannot safely implement encryption

Evidence: SessionManager.kt:406-419 and 483-490.

The protocol reader starts on RawConnection before the security handshake/wrapper is established. RawConnection.read() is single-collector, so a real security layer cannot safely consume handshake bytes, and an encrypted wrapper would be bypassed by the already-running reader.

Fix: establish the secure byte stream first, then create the sole protocol reader over that secured stream.

### CORE-08 — Medium — SessionStore reads a mutable HashMap without its mutex

Evidence: SessionStore.kt:59-61 and 229-234.

Writes are mutex-protected, while registrationOf() reads byPeer lock-free for every message. Concurrent mutable-map reads/writes are unsafe even if the value is used only for diagnostics.

Fix: publish an immutable atomic snapshot or make the lookup suspend and use the mutex.

### CORE-09 — Medium — remotely terminated sessions leave an active child Job

Evidence: P2pSessionImpl.kt:126-127, 323-329, 361-369, and 451-456.

Remote close/failure performs resource cleanup but does not complete sessionJob. A later caller close returns early for terminal state, so each remote termination retains an active child until the whole kit stops.

Fix: complete sessionJob after terminal cleanup; reserve cancelAndJoin for externally initiated close.

### CORE-10 — Medium — public sessions can retain terminal entries after stop

Evidence: SessionManager.kt:849-865; P2pKitImpl.kt:543.

Removal depends on asynchronous watchers. stop() closes sessions and then cancels the watcher scope. A watcher that has not run leaves a terminal session permanently in the public StateFlow.

Fix: clear/remove store entries atomically inside closeAllSessions() before canceling the manager scope.

### CORE-11 — Medium — partial startup/advertising/discovery is not rolled back

Evidence: P2pKitImpl.kt:288-320, 375-391, and 405-419.

If transport N fails or cancellation occurs after earlier components start, those earlier components remain active. Retrying assumes idempotence that the transport interfaces do not require.

Fix: record committed components and roll them back in reverse order; specify and test idempotence where required.

### CORE-12 — Medium — teardown can report success while resources remain open

Evidence: P2pKitImpl.kt:555-560; P2pSessionImpl.kt:492-501.

Stop/close errors are discarded without logging. Individual transport/session closes are unbounded, so one hung close can hang stop() despite bounds elsewhere.

Fix: bound every close, retain/log every error, continue best-effort cleanup, and surface an aggregate diagnostic.

### CORE-13 — Medium — inbound setup timeout excludes operations that can hang

Evidence: Handshake.kt:39-50; SessionManager.kt:483-485.

HELLO is written before the timeout starts, and the security handshake is outside it. A hung write/security implementation can hold one of 16 inbound permits indefinitely.

Fix: place the entire setup transaction under one deadline and close on timeout.

### CORE-14 — Medium — keepalive uses wall clock and misses the exact deadline

Evidence: Platform.kt:5-6; P2pKitImpl.kt:651; P2pSessionImpl.kt:655-656 and 673-674.

Epoch clock jumps can cause immediate false failure or suppress timeouts. The comparison uses greater-than rather than greater-than-or-equal, so a nominal 30-second timeout with 10-second ticks commonly fires near 40 seconds.

Fix: use monotonic elapsed time and test exact boundary plus forward/backward clock changes.

### CORE-15 — Medium — global P2pState hides independent feature failures

Evidence: P2pKitImpl.kt:378-390 and 405-418.

Advertising/discovery errors set global Failed, while either subsystem's later success independently clears it to Running. Successful discovery can hide still-failed advertising.

Fix: reserve global state for core transport lifecycle and expose per-feature state/error.

### CORE-16 — Medium — one incoming-flow exception permanently disables a transport

Evidence: SessionManager.kt:177-201.

The collector logs and completes after a transient error. Existing sessions remain, but no further inbound session can be accepted without reconstructing/rebinding.

Fix: recollect with bounded exponential backoff coordinated with transport lifecycle.

### CORE-17 — Medium — public values expose mutable backing storage

Evidence: P2pMessage.kt:33-66 and related peer/network map/list models.

Binary stores and exposes the caller's ByteArray directly, so hash/equality and the bytes serialized by send() can change concurrently. Maps/lists are only shallowly read-only.

Fix: defensively copy at ownership boundaries or expose truly immutable byte/value containers.

### CORE-18 — Medium — distinct AppIds can collide in persistent identity storage

Evidence: Android FilePeerIdStorage.kt:20 and 65-74; JVM FilePeerIdStorage.kt:35 and 114-124; iOS NSUserDefaultsPeerIdStorage.kt:31 and 68-77.

The sanitizer is non-injective: punctuation replacement, leading-dot handling, truncation, and case-insensitive filesystems can map distinct IDs to one key.

Fix: add a full canonical hash suffix or use reversible encoding, with a migration path.

### CORE-19 — Medium — first-use PeerId creation is not concurrency-safe

Evidence: Android FilePeerIdStorage.kt:25-28 and 49-54; JVM:45-48 and 86-96; iOS:33-36 and 46-50.

Multiple instances can all observe missing state, return different IDs, and race the persisted winner.

Fix: use per-key/process synchronization plus cross-process atomic create, unique temporary files, and reread the winning value.

### CORE-20 — Medium — persistence failure breaks same-instance identity stability

Evidence: Android FilePeerIdStorage.kt:45-61; JVM:79-102; iOS:45-57.

On persistence failure the generated ID is returned but not memoized, so the same object can generate a new identity on its next call.

Fix: memoize the process-local value even when durable persistence fails, or make failure explicit.

### CORE-21 — Medium — Android/JVM identity fallback can truncate the durable value

Evidence: Android FilePeerIdStorage.kt:51-53; JVM:92-95.

After rename failure, fallback writes directly to the target and is not atomic. A crash can leave a partial identity file.

Fix: use Android AtomicFile or atomic move semantics with unique temp files and durable fsync/rename behavior.

### CORE-22 — Medium — Android/iOS path observers retain stale state and cleanup ownership

Evidence: AndroidNetworkPathObserver.kt:113-118; IosNetworkPathObserver.kt:105-109.

close() does not reset status to Unknown. Android also drops callback ownership after an unregister failure even though callbacks may continue.

Fix: reset state on every generation, generation-gate callbacks, log/retain failed cleanup ownership, and retry.

### CORE-23 — Medium — a newly registered session can miss an Unsatisfied path state

Evidence: P2pKitImpl.kt:348-356; SessionManager.kt:886-895.

Unsatisfied applies only to the current snapshot. A session registered just afterward misses it because StateFlow will not re-emit an unchanged value.

Fix: atomically apply the current authoritative path state during registration/rearm.

### CORE-24 — Medium API gap — NetworkProvisioningManager has no close contract

Evidence: NetworkProvisioningTypes.kt:24-43; NetworkProvisioningFactory.kt:60-68.

The parent Job is advisory to external implementations and P2pKit cannot explicitly dispose a manager that attaches incorrectly.

Fix: add idempotent suspending close() and invoke it during kit teardown.

### CORE-25 — Low — Android permission diagnostics omit two declared requirements

Evidence: PermissionManagerFactory.android.kt:18-20 and 55-58.

The text lists INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, and CHANGE_WIFI_MULTICAST_STATE, but code checks only the last two.

Fix: check all required normal permissions or provide them through mergeable library manifests.

### CORE-26 — Low limitation — Android defaults to a no-op path observer

Evidence: P2pKitAndroid.kt:22-33; AndroidNetworkPathObserverFactory.kt:7-19.

Android retains application Context but still uses the no-op default, unlike iOS. Recovery is opt-in.

### CORE-27 — Low API mismatch — transport factories cannot express discovery-only transport

Evidence: TransportFactory.kt:35-38.

TransportPair.data is non-null even though the extension description says either side may be supplied.

### CORE-28 — Low — builder validation is incomplete

Evidence: Builders.kt:145-150; PeerRegistry.kt:115-128.

Blank/very large device names, duplicate factories/kinds, and poorly normalized manual hosts are accepted.

### CORE-29 — Low — JVM identity fallback can silently select the working directory

Evidence: PeerIdStorageFactory.jvm.kt:8-10.

Blank or inaccessible user.home/tmpdir properties are not handled robustly.

### CORE-30 — Low — test fixtures hide important race conditions

Fake counters are plain mutable integers; strict fake discovery still drops pre-subscription events; simultaneous-open tests do not prove both peers kept the same physical connection; identity integration rechecks storage instead of the IDs actually advertised; a containment test uses string prefix rather than normalized Path.startsWith.

## Detailed findings: protocol and messaging

### PROTO-01 — High availability — FrameReader performs quadratic copying

Evidence: protocol/FrameReader.kt:39-43 and 48-76.

Each feed copies the accumulated buffer and each decoded frame copies its remaining tail. Tiny fragments of a large declared frame, or many small frames in one batch, create O(n²) allocation/work. Magic/type validity is delayed until the declared payload is fully buffered.

Fix: use a segmented buffer/read cursor, compact once per feed, and validate the fixed header immediately.

### PROTO-02 — Medium — frame header version is ignored

Evidence: FrameCodec.kt:72-110; DefaultP2pProtocol.kt:142-190; Handshake.kt:69-75.

The JSON HELLO version is checked, but Frame.version is not. A header version 99 with payload version 1 is accepted.

Fix: validate supported major header version as soon as the header is complete.

### PROTO-03 — Medium security/availability — packet-specific size limits are absent

Evidence: DefaultP2pProtocol.kt:45-46, 68-95, and 154-188; FrameCodec.kt:31-47.

An 8 MiB HELLO, PING, or FILE_OFFER reaches generic buffering/JSON parsing. Locally supplied names, MIME values, and reasons are not bounded consistently. Parsing runCatching can catch fatal Throwable values.

Fix: apply small per-packet caps before parsing, catch expected parse exceptions only, validate outbound fields, and enforce the universal maximum in encode().

### PROTO-04 — Medium — control/chunk structures are too permissive

Evidence: DefaultP2pProtocol.kt:142-190; Reassembler.kt:87-159; StreamingFileReceiver.kt:41-65.

Control frames may carry arbitrary flags, indices, totals, and payloads. Reassembly does not require stable IS_TEXT/correct LAST placement. File chunks do not require stable totalChunks/LAST, and an ACCEPT followed by REJECT can move a streaming transfer to Rejected.

Fix: centralize packet-type structural validation and define an explicit transition table.

### PROTO-05 — Medium — diagnostics can change protocol behavior

Evidence: FrameTrace.kt:35-36; DefaultP2pProtocol.kt:102-105 and 133-137.

A throwing trace callback prevents sends or tears down receive processing.

Fix: isolate callback failures and disable/log a failed trace sink.

### PROTO-06 — Low — remote text fields accept invalid/canonicalization-hostile data

Evidence: Reassembler.kt:182-184; HelloPayload.kt:39-40; DefaultP2pProtocol.kt:216-218; FileOfferPayload.kt:37-51.

UTF-8 decoding substitutes invalid sequences. Names/reasons allow empty values, separators, NUL/control characters, and log controls.

Fix: use strict UTF-8 where canonical text is required; validate/sanitize wire and log fields.

### PROTO-07 — Low — malformed/unknown frames can flood logs

Evidence: FrameReader.kt:71-75; DefaultP2pProtocol.kt:154-175.

One warning is emitted per frame. Rate-limit and aggregate peer-controlled diagnostics.

### PROTO-08 — Low API surprise — P2pMessage metadata is never transmitted

Evidence: P2pMessage.kt:33-48; Chunker.kt:28-32; Reassembler.kt:182-184.

Tests intentionally pin this behavior, but the public model implies metadata belongs to the message. Remove it until supported or add a versioned envelope.

## Detailed findings: file transfer

### FILE-01 — High — cancellation during accept() can orphan an accepted transfer and sink

Evidence: FileTransferDispatcher.kt:231-258.

accept() cancels the offer timer, installs the receiver, and sets Accepted before the suspending FILE_ACCEPT write. Cancellation is rethrown without rolling back, leaving no handle for the caller and an accepted sink the application cannot control.

Fix: make acceptance transactional and perform bounded NonCancellable abort/reject cleanup for ambiguous writes.

### FILE-02 — High availability — accepted inbound transfers have no idle/overall timeout

Evidence: FileTransferConfig.kt:12-26; FileTransferDispatcher.kt:241-244 and 347-376; StreamingFileReceiver.kt:49-65.

Accept cancels the only timer. A peer can remain idle while answering keepalives or send endless zero-length sequential chunks. Sixty-four stalled accepts can exhaust the inbound cap.

Fix: add idle/overall deadlines, reset only on positive valid progress, and reject empty/inconsistent/over-size/LAST-invalid data.

### FILE-03 — High data race — receive, finish, and cancel operate concurrently on the sink

Evidence: StreamingFileReceiver.kt:30-91; FileTransferDispatcher.kt:289-299, 466-505, 508-536, and 550-555.

A chunk can pass closed checks, cancellation can flush/close, and then the chunk can write. Concurrent write/flush/close allows bytes after terminal state and unflushed data.

Fix: serialize each receiver through a per-transfer actor/mutex without holding the global map mutex for I/O.

### FILE-04 — High data-integrity contract — sender reports Completed before receiver durability

Evidence: FileTransferDispatcher.kt:631-644 and receiver failure path 524-535.

The sender completes after writing FILE_DONE; there is no receiver acknowledgement. Receiver flush can fail afterward. The isolated forced JVM run exposed the related race: cancelMidStreamPropagatesToReceiver expected Cancelled but sender was already Completed.

Fix: add FILE_COMPLETE/FILE_FAILED acknowledgement and expose Completed only after acknowledgement or a clearly defined durability contract.

### FILE-05 — Medium — actionable offers can disappear or arrive stale/out of order

Evidence: FileTransferDispatcher.kt:72-77 and 408-412; SessionManager.kt:360-380.

SharedFlow replay is zero, so offers vanish without an active subscriber. Session routing begins before the incoming session is published. Separate launched emissions can reorder or arrive after timeout.

Fix: retain pending offers in an ordered state/queue until answered.

### FILE-06 — Medium — offer timeout starts before the offer is writable/observable

Evidence: FileTransferDispatcher.kt:124-176, 387-412, and 684-727.

Sender timeout starts before send-mutex acquisition/write; receiver timeout starts before delivery to the app. Busy writers can consume the whole window.

Fix: register/start timers after successful write or observable publication.

### FILE-07 — Medium — timeout terminal states are nondeterministic

Evidence: FileTransferDispatcher.kt:539-556 and 684-727; FileTransferState.kt:16-21.

Both sides use the same deadline, while sender cancel races receiver timeout/reject. Existing tests accept either Cancelled or timeout Rejected.

Fix: assign one timeout authority and pin exact terminal states.

### FILE-08 — Medium — user-controlled I/O runs under the global dispatcher mutex

Evidence: FileTransferDispatcher.kt:207-214, 289-299, and 684-692; OutgoingFileTransferImpl.kt:80-93.

RawSource.close() and sink.flush() can block or reenter while every transfer/session close/reconnect waits on the same map lock.

Fix: decide/remove ownership under lock, then perform bounded I/O outside it.

### FILE-09 — Medium — terminal handles retain sources/sinks

Evidence: OutgoingFileTransferImpl.kt:28 and 48-53; IncomingFileSession.kt:43-59.

Terminal handles keep strong references to potentially large sources and receiver/sink objects.

Fix: use clearable atomic nullable references and release them on every terminal transition.

### FILE-10 — Medium — chunk arithmetic can overflow under valid configuration

Evidence: StreamingFileSender.kt:35; FileTransferConfig.kt:12-33; StreamingFileReceiver.kt:55; OutgoingFileTransferImpl.kt:68-70.

The default 2 GiB maximum with chunk size 1 produces 2^31 chunks and a negative Int. Long arithmetic can overflow near Long.MAX_VALUE.

Fix: use 1 + (size - 1) / chunk, bound total chunks to Int.MAX_VALUE, constrain configuration, and use subtraction-based receiver comparisons.

### FILE-11 — Medium API — transfer failures use misleading error types and lose causes

Evidence: Errors.kt:22-42; FileTransferDispatcher.kt:255, 485-503, 524-533, and 648-656.

Disk/source I/O becomes ConnectionFailed although the session remains connected. Isolated transfer protocol errors become ProtocolError even though that type says the session closes. Causes are usually discarded.

Fix: introduce transfer-I/O and transfer-protocol errors with retained causes.

### FILE-12 — Medium — progress can advance after terminal state

Evidence: IncomingFileSession.kt:67-72; OutgoingFileTransferImpl.kt:68-73.

Byte flows update before checking terminal state. Serialize byte/state commits and freeze progress after terminal.

### FILE-13 — Low integrity — byte count is checked but content is not

Evidence: FileOfferPayload.kt:17-20; StreamingFileReceiver.kt:55-81.

A changing source can produce a same-length hybrid file. Add optional digest metadata and verify it before completion acknowledgement.

### FILE-14 — Low — generated transfer ID collision overwrites existing ownership

Evidence: FileTransferDispatcher.kt:113-143.

The probability is small with good randomness, but deterministic/broken randomness leaks the earlier handle/source. Generate under lock until absent from both maps.

### FILE-15 — Low — platform file helpers do not define snapshot semantics

Evidence: JVM FileTransferJvm.kt:22-33; Android FileTransferAndroid.kt:28-45 and 54-77.

JVM opens before measuring, Android trusts mutable provider metadata, and negative/changed sizes are not handled consistently.

## Detailed findings: LAN transport

### LAN-01 — High — cancellation can leak a ghost JmDNS service or listener

Evidence: JmdnsLifecycleCoordinator.kt:211-229, 260-277, 498-524, and 570-584; JvmLanDiscoveryTransport.kt:82-117, 144-159, and 373-415; AndroidLanDiscoveryTransport.kt:217-280.

withContext(IO) has prompt-cancellation semantics. Blocking registration/listener creation can succeed, then cancellation can discard the token before it is stored. Rebind also wraps suspending restoration in runCatching and can swallow CancellationException.

Fix: capture tokens across the cancellable boundary; unregister/remove them in NonCancellable + IO on cancellation, then rethrow.

### LAN-02 — High — failed restoration is committed as a successful rebind

Evidence: JmdnsLifecycleCoordinator.kt:415-423 and 498-524; JmdnsLifecycleCoordinatorTest.kt:458-480.

Registration/listener restoration failures are logged, but bound-network markers are still advanced and retry state reset. The same-network event is then ignored indefinitely. A test explicitly pins this broken behavior.

Fix: commit the binding only after every intended resource is restored; otherwise close and retry the transaction.

### LAN-03 — High — Apple browser/listener failure can pin ghost peers permanently

Evidence: IosLanDiscoveryTransport.kt:249-279 and 501-529; IosLanDataTransport.kt:693-722.

Browser failure retains host intent/generation/cache, so the announce loop keeps publishing cached peers as Updated forever. Failed listener rebuild can leave listener null, after which rebindNow() skips future rebuilding.

Fix: model intent separately from live resources, invalidate cache generation on failure, stop synthetic heartbeats, and retry browser/listener creation with bounded backoff.

### LAN-04 — High availability — Apple inbound connection buffering is unbounded

Evidence: IosLanDataTransport.kt:185, 362-377, and 501-510.

Channel.UNLIMITED stores already-started live NWConnections. A LAN peer can accumulate descriptors faster than core admission consumes them, and close does not drain/cancel buffered elements.

Fix: size the channel to admission capacity, reject overflow immediately, provide onUndeliveredElement cleanup, and drain/cancel during close.

### LAN-05 — Medium — cancelled JVM/Android outbound connect can orphan a socket

Evidence: JvmLanDataTransport.kt:99-121; AndroidLanDataTransport.kt:93-115.

Socket.connect() may succeed immediately before withContext return cancellation discards the socket.

Fix: hold ownership outside the cancellable block and close on CancellationException.

### LAN-06 — Medium — cancelled Apple outbound connect leaves NWConnection active

Evidence: IosLanDataTransport.kt:481-490.

Only TimeoutCancellationException cleans up; ordinary parent cancellation propagates without canceling raw.

### LAN-07 — Medium — fatal JVM/Android accept-loop exit leaves a stale advertised port

Evidence: JvmLanDataTransport.kt:60-67 and 132-162; AndroidLanDataTransport.kt:57-64 and 122-149; JvmLanAcceptLoopResilienceTest.kt:124-166.

The flow ends while serverSocket and tcpPort remain populated. A later start reports success against a dead listener while discovery advertises the old port.

Fix: clear state/port atomically, unadvertise, and retry bind/accept or expose fatal state.

### LAN-08 — Medium — ordinary write failure leaves raw connection marked connected

Evidence: JvmRawConnection.kt:124-137; AndroidRawConnection.kt:124-137.

Watchdog timeout closes correctly, but normal IOException only logs/rethrows and retains connected state/descriptor.

Fix: funnel every terminal write error through one close-once path.

### LAN-09 — Medium — raw-read cancellation does not unblock I/O

Evidence: JvmRawConnection.kt:157-193; AndroidRawConnection.kt:157-192; IosRawConnection.kt:284-331; JvmRawConnectionCancellationTest.kt:121-125.

JVM/Android require closing the peer socket after cancellation; Apple continuation has no cancellation handler.

Fix: bind coroutine cancellation to local socket/NWConnection cancellation or use interruptible I/O.

### LAN-10 — Medium — cleanup failure discards ownership

Evidence: JmdnsLifecycleCoordinator.kt:239-258, 288-309, 445-451, and 577-585; JvmLanDiscoveryTransport.kt:131-142, 418-433, and 487-492; AndroidLanDiscoveryTransport.kt:375-379 and 755-769.

Unregister/remove/close failures are swallowed while tokens, handles, callbacks, or multicast-lock ownership are cleared. Later starts can create duplicates around leaked resources.

Fix: retain cleanup-pending ownership, generation-gate callbacks, retry in NonCancellable, and close the owning handle as fallback.

### LAN-11 — Medium — Apple listener start/close races and retains stale state

Evidence: IosLanDataTransport.kt:304-332, 344-426, and 501-511.

start() checks listener before closed; close() does not clear listener/port. A close racing initial construction can return before start installs a live listener. Direct start-after-close can report success using the cancelled listener. Semaphore waits block a thread for up to five seconds.

Fix: serialize lifecycle transitions, recheck closed before commit, clear state on close, cancel uncommitted resources, and use cancellable async bridging.

### LAN-12 — Medium — Apple cache pruning can delete a fresh rediscovery

Evidence: IosLanDiscoveryTransport.kt:259-278, 626-654, and 685-696.

A stale ID is removed, a callback re-adds it, then emitLostById unconditionally removes the new endpoint and emits Lost.

Fix: condition final removal/event on generation/version or use tombstones.

### LAN-13 — Medium — network rotation support is incomplete on every platform

Evidence: JvmLanDiscoveryTransport.kt:62-80 and 435-492; IosLanDataTransport.kt:545-594; AndroidLanDiscoveryTransport.kt:362, 407-421, and 664-681.

- JVM does not monitor concrete interface changes.
- Apple fingerprints only path status/interface type and can miss Wi-Fi-to-Wi-Fi address rotation.
- Android can bind initial default/cellular then skip the first primary Wi-Fi/Ethernet callback.
- Android binding is IPv4-only and outbound sockets are not bound to the selected Network.

Fix: monitor interface/address identity, support IPv6, deduplicate first-primary events correctly, and bind outbound traffic to the selected network.

### LAN-14 — Medium — synthetic cache heartbeat treats cache presence as liveness

Evidence: JvmLanDiscoveryTransport.kt:203-225; AndroidLanDiscoveryTransport.kt:341-359; JmdnsLifecycleCoordinator.kt:53-64.

Crashed peers can remain live until resolver cache expiry, not core's shorter stale timeout. On Apple browser failure, this can become indefinite.

Fix: refresh lastSeen only on fresh network resolution/answer, or align eviction explicitly with DNS TTL.

### LAN-15 — Medium — local TXT values are unbounded and failures are silent

Evidence: JvmLanDiscoveryTransport.kt:85-100; AndroidLanDiscoveryTransport.kt:428-446; IosBonjour.kt:41-59; IosBonjourTest.kt:158-168.

JmDNS can return an empty TXT payload when an encoded entry exceeds 255 bytes, so registration appears successful but peers reject the missing identity/app record. Apple ignores the native setter's Boolean failure.

Fix: validate entry byte lengths centrally, bound identity/app values, safely truncate only display names, and propagate native failure.

### LAN-16 — Medium security — discovery records are trusted too broadly

Evidence: Lan.kt:87-105; JvmLanDiscoveryTransport.kt:526-539; AndroidLanDiscoveryTransport.kt:802-815; IosEndpointRegistry.kt:25-40; IosLanDiscoveryTransport.kt:626-696.

Validation ignores advertised protocol version, accepts unbounded/control fields, chooses the first global address without subnet affinity, and keys Apple ownership only by PID. A hostile service can replace/withdraw another peer's endpoint.

Fix: enforce bounded schema/version, associate service-instance ownership, validate subnet/interface reachability, try alternate candidates, sanitize logs, and authenticate identity at handshake.

### LAN-17 — Medium — Apple discovers AWDL endpoints its data parameters may reject

Evidence: IosLanDiscoveryTransport.kt:485-495; IosLanDataTransport.kt:158-167.

Browser peer-to-peer is enabled, while listener/dial parameters omit it.

Fix: enable peer-to-peer consistently or do not advertise discovery support that cannot connect.

### LAN-18 — Medium — only one advertised address is retained

Evidence: JvmLanDiscoveryTransport.kt:526-539; AndroidLanDiscoveryTransport.kt:802-815.

Dual-homed/VPN peers can select a valid but unreachable first address despite later reachable candidates.

Fix: retain ordered candidates, prefer current subnet/interface, and retry alternates.

### LAN-19 — Low — library manifests do not supply normal network permissions

Evidence: AndroidLanDsl.kt:29-35 and module manifests.

Consumers must manually copy normal permissions. Supplying safe normal permissions through manifest merge would reduce integration failures while leaving runtime permission UX to hosts.

### LAN-20 — Low — Apple packaging denial has weak diagnostics

Host apps must provide local-network/Bonjour plist entries. Add preflight diagnostics that distinguish packaging denial from ordinary no-peer state.

### LAN-21 — Low — provenance stamp may silently become unknown/missing

Evidence: p2p-transport-lan/build.gradle.kts:104-131.

Git failure writes unknown, and a missing output directory can prevent a meaningful release stamp. See BUILD-07 for the task-output defect.

### LAN-22 — Low — diagnostics accept peer-controlled control characters

Android logging is unconditional; Apple retains 200 log entries even when mirroring is disabled. Sanitize fields and make retention configurable.

### LAN-23 — Low — terminal close retains listener ports/references

This misleads diagnostics and makes unsupported direct reuse unsafe even where transports are intended one-shot.

### LAN-24 — Low race — Apple queued writer can run after connection close

Evidence: IosRawConnection.kt:187-214.

Closed state is checked before acquiring the write mutex, not again inside it.

### LAN-25 — Medium — exhausted create-retry budget carries into a genuinely new network

Evidence: JmdnsLifecycleCoordinator.kt:183-196, 468-496, and 596-612.

rebindRetryAttempts resets only after a successful bind or when both intents stop. After the budget is exhausted, a real network change gets one create attempt whose counter is already beyond the budget, so that new target receives no self-scheduled retries.

Fix: reset the retry generation/counter when the observed target changes, while keeping retries bounded per target.

### LAN-26 — Low concurrency risk — rebind job scheduling is unsynchronized

Evidence: JmdnsLifecycleCoordinator.kt:369-385.

scheduleRebind() reads/cancels/replaces pendingRebindJob outside the coordinator mutex. Concurrent platform callbacks can lose cancellation or leave more than one debounced job. Serialize scheduling with a small lock/actor or guarantee and assert a single callback queue on every platform.

## Detailed findings: Android network provisioning

### PROV-A01 — Medium — start can return Failed while the hotspot is live

Evidence: AndroidNetworkProvisioningManager.kt:153-165 and 342-359.

Success commits the handle/state/event as LocalNetworkStarted, then buildStartedResult() can return Failed if credentials/manual connection data are unavailable. The caller sees failure but owns a live resource it cannot infer from the result.

Fix: either return a started result with partial metadata or close/roll back and publish one consistent failure state.

### PROV-A02 — Medium — start is allowed after parent lifecycle cancellation

Evidence: AndroidNetworkProvisioningManager.kt:323-330; AndroidNetworkProvisioningManagerTest.kt:403-439.

The test explicitly pins starting a new hotspot after parentJob is cancelled; it stays reserved until explicit close.

Fix: add a closed/liveness guard and reject post-parent-cancellation starts.

### PROV-A03 — Medium/High race — close is not serialized with start/join

Evidence: AndroidNetworkProvisioningManager.kt:332-338 and lifecycleLock use in start/join.

Concurrent completion can publish state and install a handle after close, while its watcher launches in a cancelled scope.

Fix: serialize close and every resource commit under one lifecycle generation.

### PROV-A04 — Medium — hotspot callback cancellation can lose a reservation handle

Evidence: WifiManagerWrapperImpl.kt:78-89 and 109-111.

Cancellation can occur after onStarted passes the active check but before handle ownership is stored.

Fix: use atomic ownership and continuation resume cleanup/onCancellation.

### PROV-A05 — Medium — join callback cancellation can leak process binding

Evidence: WifiManagerWrapperImpl.kt:153-177 and 195-198.

onAvailable can bind the process, cancellation can observe no handle, and the handle is then assigned after cleanup.

### PROV-A06 — Medium — bindProcessToNetwork result/exception is ignored

Evidence: WifiManagerWrapperImpl.kt:165-173.

Joined can be returned even if binding returns false or fails. Check the result and clean up on failure.

### PROV-A07 — Medium — queued onAvailable can rebind after handle close

Evidence: WifiManagerWrapperImpl.kt:174-177 and JoinHandle close.

There is no closed generation flag around later callbacks.

### PROV-A08 — Medium — process network binding has no global ownership arbitration

Evidence: WifiManagerWrapperImpl.kt:232-235.

Binding is process-wide. Multiple managers/app components can overwrite each other; close unconditionally binds null and can clear someone else's selection.

Fix: coordinate ownership process-wide and restore the prior binding where possible.

### PROV-A09 — Medium — joined-network snapshot enumerates unrelated interfaces

Evidence: AndroidNetworkProvisioningManager.kt:218-229.

VPN/Ethernet addresses can be reported as the joined Wi-Fi network. Use LinkProperties for the specific Network.

### PROV-A10 — Medium — normal-permission failures are missing or misdiagnosed

Evidence: AndroidNetworkProvisioningManager.kt:394-418; p2p-network-provisioning-android/src/androidMain/AndroidManifest.xml:10-12.

All SecurityException values map to runtime permission failure, including a missing CHANGE_NETWORK_STATE declaration.

Fix: diagnose required normal manifest permissions separately and preserve PlatformError detail.

### PROV-A11 — Low — capability/input validation is shallow

SDK level alone is treated as specifier support, Wi-Fi hardware is not checked, and invalid security/passphrase combinations reach the platform builder rather than typed validation.

### PROV-A12 — Test gap — real Android callbacks are untested

Tests use a fake wrapper. There is no Robolectric/instrumented coverage for callback/cancellation races, process binding, real permissions, or LinkProperties.

## Detailed findings: desktop provisioning

### PROV-D01 — Medium — pollIntervalMillis is not validated

Zero produces a busy loop; negative values fail at runtime. Require a positive bounded duration.

### PROV-D02 — Medium/Low — interface scan can report unreachable addresses as Wi-Fi

JvmNetworkProvisioningManager enumerates VPN, container, Ethernet, and virtual interfaces and labels the approximation ConnectedToWifi.

Fix: rank/filter interfaces or make the approximation explicit in the returned type.

### PROV-D03 — Low — broad Throwable catch can hide fatal errors

Evidence: JvmNetworkProvisioningManager.kt:141.

Catch expected network/security exceptions and preserve cancellation/fatal failures.

### PROV-D04 — Low — tests allow a null manual result without asserting behavior

manualConnectionInfoCarries... becomes vacuous on null and does not prove a usable address.

### PROV-D05 — Low — tests mutate process-global properties

Manual loopback and KMP tests mutate user.home and JmDNS binding properties, which is unsafe under parallel test execution. Restore prior values and isolate processes.

## Detailed findings: sample applications

These findings are sample-layer defects, not all core-library defects. They still matter because official samples become copied integration guidance.

### SAMPLE-01 — High data integrity — iOS suppresses sink write failure

Evidence: iosApp/ContentView.swift:1492-1522, including early-buffer exhaustion at 1506-1508.

FileHandleRawSink catches disk-write errors, marks a private failed flag, then silently no-ops later writes. Nothing tells the SDK, so transfer accounting can reach Completed with a truncated destination.

Fix: propagate failure/cancel the transfer, verify final length, close, and delete the partial file.

### SAMPLE-02 — High data integrity — iOS same-name destination selection is non-atomic

Evidence: ContentView.swift:937-949.

It checks the original name, then uses a one-second timestamp fallback once without checking or atomically claiming it. Concurrent offers can open the same file; an existing timestamp path can be reused.

Fix: use exclusive create in a retry loop or a transfer-ID/UUID name.

### SAMPLE-03 — High availability/security — every sample auto-accepts untrusted files

Evidence: desktop CLI Main.kt:658-704; desktop UI Main.kt:669-696; Android P2pKitViewModel.kt:650-693; iOS ContentView.swift:915-959.

There is no user consent, quota, file-count limit, accepted-size policy, or free-space check. A connected LAN peer can fill storage. iOS writes into Documents, which may also be included in normal document backup behavior.

Fix: require explicit consent or an intentionally enabled test mode; enforce count/size/free-space/path policies.

### SAMPLE-04 — High availability — Android retains remote binary payloads in UI history

Evidence: P2pKitViewModel.kt:1031-1043 and 1071-1075; MainActivity display at 1174-1178.

The timeline stores complete P2pMessage.Binary objects while rendering only their byte size. A 500-entry count cap with 4 MiB messages can retain roughly 2 GiB.

Fix: convert to a size-only summary before storage and impose a total byte/character budget.

### SAMPLE-05 — Medium — failed/cancelled incoming transfers retain partial files everywhere

Evidence: CLI Main.kt:690-703; desktop UI Main.kt:742-775; Android P2pKitViewModel.kt:747-760; iOS ContentView.swift:957-959 and 1014-1058.

Use .part files and rename only after verified completion; delete every non-completed destination.

### SAMPLE-06 — Medium — desktop UI/Android can leak an opened stream during accept cancellation

Evidence: desktop UI Main.kt:683, 689, 745, and 959-965; Android P2pKitViewModel.kt:656-675 and 746.

The destination is opened, accept() suspends, and ownership is registered only afterward. Cancellation in between bypasses cleanup. Android withContext(IO) also has prompt-cancellation resource loss.

Fix: wrap acquisition/accept/registration in one try/finally ownership transaction.

### SAMPLE-07 — Medium — Android/CLI transfer collectors never terminate

Evidence: Android P2pKitViewModel.kt:716-721 and 748-760; CLI Main.kt:516-528, 637-657, and 690-706.

StateFlow is collected forever after terminal state; CLI per-session collectors can also outlive session removal.

Fix: use first { terminal }, cancel paired byte collectors in finally, and use a per-session child scope.

### SAMPLE-08 — Medium — P2pKit.create failure permanently wedges GUI Start

Evidence: desktop UI Main.kt:289-381; Android P2pKitViewModel.kt:270-395.

isStarting is set before synchronous construction and cleared only much later. A constructor/setup exception leaves Start disabled forever.

Fix: cover the entire construction/setup transaction with try/finally and clean partial ownership.

### SAMPLE-09 — Medium — desktop UI can overlap old/new kits

Evidence: desktop UI Main.kt:281-293, 575-609, and 1057-1099.

start() ignores isStopping. stop() immediately clears isRunning before asynchronous kit.stop() completes, so Setup exposes Start and a second kit can be created.

Fix: use a single serialized lifecycle state machine and expose Start only after cleanup completes.

### SAMPLE-10 — Medium — stop failure is swallowed after ownership is discarded

Evidence: desktop UI Main.kt:575-609; Android P2pKitViewModel.kt:935-977; iOS ContentView.swift:1297-1338.

All three clear kit ownership and report stopped/best effort even when cleanup fails, preventing retry.

Fix: retain a failed-cleanup handle/state and allow bounded retry or explicit abandonment.

### SAMPLE-11 — Medium — CLI exceptions bypass shutdown

Evidence: desktop CLI Main.kt:175-194 and direct provisioning command at 539-565.

repl is not inside finally, so a command/read failure skips p2p.stop() and scope cancellation.

### SAMPLE-12 — Medium — iOS stops watchers/sinks before quiescing SDK writers

Evidence: ContentView.swift:1307-1327 and 1053-1057.

Watcher cancellation invokes terminal sink/source close before kit.stop(). A background SDK write can race FileHandle close, whose flags are also unsynchronized.

Fix: quiesce the kit/transfer engine first, then close application resources in structured order.

### SAMPLE-13 — Medium — Swift flow adapters spawn unstructured Tasks

Evidence: ContentView.swift:1373-1442.

Each emission creates a new untracked Task. Cancelling outer collection does not reliably cancel in-progress offer handling, which can accept a file or mutate UI after stop.

Fix: use structured async bridging or one serialized actor/task per flow.

### SAMPLE-14 — Medium data loss — Android collision cap can return an occupied file

Evidence: P2pKitViewModel.kt:807-818.

After 10,000 failed createNewFile attempts, the last unclaimed candidate is returned and outputStream may truncate it.

Fix: return failure when no exclusive claim succeeds.

### SAMPLE-15 — Medium path isolation — remote peer name dot segments escape sender directory

Evidence: CLI Main.kt:659-670 and 709-718; desktop UI Main.kt:672-679 and 815-818; Android P2pKitViewModel.kt:658-664 and 795-798.

Sanitizers remove separators but allow "." and "..". A peer named ".." moves writes into the parent directory.

Fix: use stable PeerId-derived directory names, reject dot segments, and verify normalized containment.

### SAMPLE-16 — Medium — Android sample omits CHANGE_NETWORK_STATE

Evidence: p2p-sample-android/src/main/AndroidManifest.xml:5-18; MainActivity.kt:1073-1263.

WifiNetworkSpecifier join/request/bind can throw SecurityException. Add the normal permission and include it in diagnostics.

### SAMPLE-17 — Medium — Android lint fails because coarse location is omitted

Evidence: AndroidManifest.xml:16-18.

The manifest requests ACCESS_FINE_LOCATION through API 32 without ACCESS_COARSE_LOCATION. :p2p-sample-android:lintDebug fails with CoarseFineLocation. Add both declarations for the affected API range and handle approximate permission behavior.

### SAMPLE-18 — Medium — CLI option parsing can turn options into identity

Evidence: desktop CLI Main.kt:73-93.

Only reconnect= is filtered in fixed positional slots. trace= can become device name; a leading option shifts appId parsing incorrectly.

Fix: parse named options independently, then derive positionals from the remainder.

### SAMPLE-19 — Medium — CLI first-match targeting is ambiguous

Evidence: Main.kt:445, 467, 506, and 599-603.

The first exact name or ID prefix can send, close, or transfer to the wrong peer/session.

Fix: require a unique match and print all candidates on ambiguity.

### SAMPLE-20 — Medium — manual IPv6 parsing rejects common local addresses

Evidence: desktop UI Main.kt:426-440; CLI Main.kt:280-299; iOS ContentView.swift:1155-1179.

Desktop UI splits at the first colon; CLI/iOS reject percent scope identifiers, and iOS rejects bracket forms. Scoped link-local IPv6 is common on LANs.

Fix: use a real host/port parser supporting bracketed and scoped IPv6.

### SAMPLE-21 — Medium — KMP demo leaks session on send failure

Evidence: sample-kmp-shared Demo.kt:24-34.

close() runs only after successful send. Advertising/discovery also remain active after success/timeout without making that ownership explicit.

Fix: close session in finally and expose a cleanup/ownership option for discovery activities.

### SAMPLE-22 — Medium — desktop UI accept failure leaves an empty claimed file

Evidence: desktop UI Main.kt:683-695.

It neither deletes the preclaimed file nor attempts rejection after accept failure.

### SAMPLE-23 — Medium — iOS transfer history is unbounded

Evidence: ContentView.swift:15, 164-175, and 1020-1031.

Rows retain P2pFileTransfer objects until Start/Stop. Long-running repeated transfers grow indefinitely.

### SAMPLE-24 — Medium — GUI text histories are count-bounded, not byte-bounded

Evidence: desktop UI Main.kt:850-869 and 884-886; iOS ContentView.swift:883-899 and 1343-1348.

Hundreds of multi-megabyte text messages can still create memory and layout pressure.

### SAMPLE-25 — Low — rapid advertise/discover toggles race stale UI booleans

CLI, desktop UI, and Android launch concurrent operations without per-operation in-flight guards. Serialize intent.

### SAMPLE-26 — Low — Android labels connecting/reconnecting sessions as connected

Evidence: MainActivity.kt:427-430 and 497-501.

Heading and Send counts use the broader live-session list and can mislead debugging.

### SAMPLE-27 — Low — permission diagnostic failure becomes “nothing missing”

Evidence: P2pKitViewModel.kt:428-434.

An exception maps to an empty list and can enable an action that is guaranteed to fail.

### SAMPLE-28 — Low security UX — Android displays credentials in clear text

Evidence: MainActivity.kt:913-919 and 1287-1293.

Acceptable for a test harness only if explicitly labelled; add reveal controls and screenshot warning.

### SAMPLE-29 — Low security — desktop logs do not consistently sanitize terminal controls

Evidence: CLI StdErrLogger Main.kt:754-762; desktop UI TailLogger Main.kt:1031-1049 and peer-name rendering.

ANSI/OSC and Unicode-direction controls from peers/SDK messages can spoof transcripts.

### SAMPLE-30 — Low — iOS PeerRow equality suppresses meaningful updates

Evidence: ContentView.swift:91-98.

Equality ignores platform, transports, and the bridged Peer object, so same-ID/name updates may not replace the stored row.

### SAMPLE-31 — Low — iOS cross-check diagnostics flood normal selective-connect state

Evidence: ContentView.swift:834-850.

Once any session exists, every discovered peer without a session logs every second even though that is normal.

### SAMPLE-32 — Low — unknown bridged transfer state is permanently nonterminal

Evidence: ContentView.swift:1063-1081.

Add logging and a bounded cancel/failure path for unrecognized future enum cases.

### SAMPLE-33 — Low — desktop window cleanup uses a scope being disposed

Evidence: desktop UI Main.kt:129-140 and 820-823.

Asynchronous cleanup is launched into the composition scope that is being cancelled, so goodbye/stop is only best effort.

### SAMPLE-34 — Low — duplicated unique-file helpers have divergent unsafe behavior

Evidence: UniqueSaveFile.kt:22-39; UniqueSaveFileTest.kt:103-113; CLI and Android copies.

Desktop probing is unbounded and returns an unclaimed path after exception; Android has the truncating cap defect. Centralize one exclusive-create utility and test every platform.

### SAMPLE-35 — Low — run configurations for Alice/Bob share one PeerId

Evidence: .run/JVM CLI Alice.run.xml:7,13; Bob equivalent; CLI Main.kt:77-81; JVM FilePeerIdStorage.kt:35-36; SessionManager.kt:459-464.

Both processes use the same app ID and user.home-backed identity key, so they load the same PeerId and reject one another as self. A first-use race may briefly hide this with two IDs, which is itself CORE-19.

Fix: add per-instance storage/profile roots while preserving the shared app ID required for discovery.

### SAMPLE-36 — Medium — Android reports Running after partial feature startup

Evidence: P2pKitViewModel.kt:344-395.

The ViewModel publishes running ownership before advertising/discovery are known to have succeeded; failures are logged while the sample continues to present a running state.

Fix: model core-started, advertising, and discovery states independently, or roll back the whole sample transaction when a required feature fails.

### SAMPLE-37 — Low — CLI close reports success after close failure

Evidence: desktop CLI Main.kt:472-478.

The session is removed and “closed” is printed even if session.close() fails. Preserve the session/failed-cleanup state or print an accurate failure.

### SAMPLE-38 — Low — CLI shutdown orders kit stop before cancelling app jobs

The quit path stops P2pKit while auto-mesh/send/collector work in the application scope can still race it. Stop accepting commands, cancel/join app-owned jobs, then stop the kit.

### SAMPLE-39 — Low — Android onCleared cleanup has no durable owner

onCleared launches asynchronous cleanup in a custom scope and cancels that scope on completion, but no host lifetime guarantees the work runs before process/activity teardown. Move critical cleanup into an explicit lifecycle stop path and keep onCleared as bounded fallback.

## Detailed findings: build, publication, tooling, and configuration

### BUILD-01 — High — published compile dependency metadata is incorrect

Evidence:

- p2p-core/build.gradle.kts:99 declares coroutines implementation while public P2pKit/P2pSession/provisioning APIs expose Flow, SharedFlow, StateFlow, and Job.
- p2p-network-provisioning-android/build.gradle.kts:19-20 exposes core/coroutine types through implementation dependencies.
- p2p-network-provisioning-desktop/build.gradle.kts:18 and 20 has the same defect.
- p2p-transport-lan/build.gradle.kts:65 exposes coroutine types while publishing coroutines at runtime scope.
- Generated POMs and Gradle module API variants confirm the missing compile dependencies.

External consumers can fail compilation unless they add dependencies independently.

Fix: use api for every dependency present in the public ABI and add a clean external-consumer compile test against the published repository.

Desktop provisioning also publishes LAN as runtime dependency at build.gradle.kts:19 although production does not import it; only ManualIpLoopbackTest does. Move it to testImplementation.

### BUILD-02 — High release blocker — no remote publication target exists

Evidence: gradle.properties:7-8; root build.gradle.kts signing configuration.

Only Maven-local publication tasks exist. There is no publishing.repositories or Central Portal upload integration. Signing alone cannot publish a release.

Fix: configure a supported Central Portal publishing/upload path with credentials supplied only by CI, staging/validation, and release status handling.

### BUILD-03 — Medium — BuildInfo defeats incremental/reproducible builds

Evidence: p2p-core/build.gradle.kts:20-24, 42, 63, and 71-75.

The task is always out of date and embeds Instant.now(), so generated content changes every run. Two consecutive compileKotlinJvm runs both regenerated and recompiled. Identical source commits produce different binaries.

Additional defect: branch text is interpolated into Kotlin without string escaping; valid branch characters such as quotes or dollar signs can break generated source. Public const provenance can also be inlined into consumers.

Fix: use stable commit/SOURCE_DATE_EPOCH inputs, escape Kotlin literals, declare inputs/outputs correctly, and avoid volatile compiled constants.

### BUILD-04 — Medium — the publication gate can pass an invalid release

Evidence: scripts/check-publish-artifacts.sh:4-7 and 49-54.

The script checks only expected primary/source/Javadoc/POM/module filenames. It does not validate signatures, checksums, signature validity, archive/XML content, dependency scopes, or clean/tagged provenance. It passed all 15 publications in this review despite BUILD-01 and without requiring signatures.

Maven Central's current requirements call for GPG/PGP signatures and checksums; the checker should validate the actual chosen portal bundle flow: [Central requirements](https://central.sonatype.org/publish/requirements/).

### BUILD-05 — Medium — Gradle wrapper components are version-skewed

Evidence: gradle/wrapper/gradle-wrapper.properties:3; tracked wrapper JAR SHA-256 76805e32c009c0cf0dd5d206bddc9fb22ea42e84db904b764f3047de095493f3.

The properties request Gradle 9.3.1, but the JAR hash is the official Gradle 9.1.0 wrapper. The official 9.3.1 wrapper hash is b3a875ddc1f044746e1b1a55f645584505f4a10438c1afea9f15e92a7c42ec13. The JAR is a valid official older archive, so this is version skew rather than evidence of tampering.

distributionSha256Sum is also absent; the official 9.3.1 binary ZIP hash is b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06. Source: [Gradle checksum reference](https://gradle.org/release-checksums/).

Fix: regenerate the complete wrapper at 9.3.1 and pin distributionSha256Sum.

### BUILD-06 — Medium — supply-chain and release automation controls are absent

No tracked configuration exists for CI, Gradle dependency verification metadata, dependency locks, vulnerability scanning, SBOM/provenance attestations, public ABI baselines, coverage gates, ktlint/detekt/Spotless execution, or multi-platform release gates.

.editorconfig configures ktlint behavior, but no task enforces it.

### BUILD-07 — Medium — XCFramework commit stamp is an undeclared/mis-targeted side effect

Evidence: p2p-transport-lan/build.gradle.kts:104-130; iosApp/scripts/check-xcframework.sh:50-54.

BUILD_COMMIT.txt is written only in doLast and is not an outputs.file. If deleted/corrupted while the XCFramework is up to date, the suggested plain assembly rerun may do nothing. The broad task-name matcher also catches intermediate device/simulator tasks and lets them stamp the shared release directory before final assembly.

Fix: use a dedicated declared output task and exact final aggregate task names.

### BUILD-08 — Medium — Android official sample's manifest fails the project check

See SAMPLE-16 and SAMPLE-17. The normal join permission is absent, and Android lint reports one error plus three warnings.

### BUILD-09 — Low — iOS launcher uses predictable/shared paths and name-first selection

Evidence: scripts/run-ios-app.sh:35, 40-48, and 87-105.

Fixed /tmp/p2pkit-ios-build.log allows concurrent clobbering and local symlink/truncation risk. The script builds by simulator name before resolving UDID, so duplicate names across runtimes are ambiguous and a missing device is discovered late. Repo-local DerivedData also contends across concurrent runs.

Fix: resolve one UDID first, build with destination id, and use mktemp/per-run DerivedData.

### BUILD-10 — Low — nested Gradle/Xcode preflight duplicates framework work

Evidence: iosApp/build.gradle.kts:9-15; iosApp/project.yml:62-74; check-xcframework.sh:31-32.

The Gradle launcher assembles, Xcode's prebuild invokes the checker, and the checker invokes Gradle again. During this review a fresh XCFramework build was repeated inside xcodebuild. BuildInfo volatility makes that more expensive.

Fix: make one layer own assembly; other layers should validate declared outputs only.

### BUILD-11 — Low — dirty-tree provenance ignores untracked inputs

Evidence: check-xcframework.sh:76-79 and 92-97.

git diff-index omits untracked sources, and the framework-relevant path list omits root/settings/compiler inputs. A release can be stamped as HEAD without warning while including an untracked source.

### BUILD-12 — Low — provenance exposes local/volatile build information

BuildInfo compiles branch, dirty flag, and wall-clock build time into public binaries. Besides reproducibility, this can disclose local branch naming and makes ordinary artifacts unique.

### BUILD-13 — Low — release usability/maintenance gaps

- KMP Javadoc JARs are empty placeholders.
- POM metadata is duplicated across four build files.
- No task enforces clean tree, matching version tag, or immutable CI commit.
- .run/iOS Simulator Tests.run.xml runs LAN iOS tests but not core iOS tests.
- committed framework run configurations build individual frameworks while the maintained app consumes the release XCFramework; names are easy to misinterpret.

### BUILD-14 — Low — compiler/test hygiene warnings are not gated

The forced build emitted numerous missing ExperimentalCoroutinesApi opt-in warnings in core tests, a deprecated JVM multicast API warning, and an Android nullable CharSequence type-mismatch warning. None fails the build.

### BUILD-15 — Low — Android lint also reports three warnings

Besides the blocking CoarseFineLocation error, lint reports a redundant activity label, obsolete backup configuration without dataExtractionRules, and an OldTargetApi warning from the installed toolchain. The target is configured as API 36; treat the last warning as a toolchain/current-SDK maintenance signal, not proof of a specific unsupported target.

## Verification results

### Passing checks

- Gradle wrapper launched Gradle 9.3.1 successfully.
- Wrapper JAR ZIP/CRC validation passed; its manifest and 33 wrapper classes were inventoried.
- Every shell script passed syntax checking.
- Every tracked run-configuration XML, Android XML, and plist parsed successfully.
- iosApp/project.yml generated an Xcode project successfully with XcodeGen.
- The native interop header passed Clang Objective-C syntax checking with warnings treated as errors.
- Generated JVM/Android/KMP POM XML parsed successfully.
- Generated POM and Gradle module metadata reproduced BUILD-01.
- Two consecutive core JVM compiles reproduced BUILD-03: generateBuildInfo and compileKotlinJvm ran both times.
- Core JVM tests passed in the first ordinary run: 258 tests.
- Protocol/transfer focused JVM suites passed: 127 scoped tests.
- Android and desktop provisioning tests passed.
- Desktop UI filename tests and KMP shared JVM tests passed.
- Android and iOS-simulator core/LAN compilation passed.
- Isolated p2p-transport-lan:jvmTest passed.
- scripts/check-publish-artifacts.sh passed all 15 publication shape rows. This is useful shape evidence, but does not negate BUILD-01/02/04.
- The release P2pKitShared XCFramework built and its commit stamp matched 6a05ccd.
- The Swift sample compiled and linked for a generic iOS Simulator with code signing disabled: Xcode ended with BUILD SUCCEEDED.

### Failing or unstable checks

1. Android lint is deterministically red:

   - Task: p2p-sample-android:lintDebug
   - Result: 1 error, 3 warnings
   - Blocking error: ACCESS_FINE_LOCATION is requested for API 32 and below without ACCESS_COARSE_LOCATION.

2. The isolated forced repository check, excluding only that known lint task, is red:

   - p2p-core JVM: 258 tests, 1 failure.
   - Failure: FileTransferFlowTest.cancelMidStreamPropagatesToReceiver.
   - Assertion: sender should observe Cancelled, got Completed.
   - This directly supports FILE-04 and the transfer terminal-state race.

3. p2p-core iOS Simulator ARM64: 243 tests, 1 failure.

   - Failure: SessionReconnectRotationTest.reconnectUsesRefreshedHintsAfterPeerRegistryUpdate.
   - Timeout: 3,500 ms.
   - The same suite had passed in an earlier non-forced run, so the gate is timing-sensitive/nondeterministic.

4. p2p-transport-lan iOS Simulator ARM64: 37 tests, 2 failures, 1 intentionally skipped diagnostic.

   - IosLanLifecycleTest.peerLostEventFiresWhenPeerStops timed out after 30 seconds.
   - IosLanLifecycleTest.advertiseStopRestartProducesObservablePeerChurn timed out after 30 seconds.
   - These two failures occurred both during the initial full check and again after concurrent Gradle work had ended, so they cannot be dismissed solely as cross-agent output interference.

5. The build emitted many un-gated warnings described in BUILD-14.

Therefore there is no green repository-wide check result for this commit.

### Not executed / environmental boundaries

- No physical Android or Apple device tests.
- No two-machine or hostile-network hardware validation.
- No simulator app launch or UI automation; the Swift app was compiled only.
- iOS X64 test tasks were linked but skipped on the ARM host.
- The intentionally ignored Apple diagnostic test was not force-enabled.
- No third-party dependency CVE/advisory scanner was installed or run.
- No remote Maven Central upload was possible because none is configured.

## Missing or weak tests to add

### Core lifecycle/session/identity

- stop() racing connect, advertising, discovery, and delayed observer start
- cancellation at every outgoing-connect suspension point followed by a successful retry
- two discovery transports contributing and losing the same PeerId
- repeated same-direction inbound connection arbitration
- a slow message subscriber while PONG/CLOSE arrives
- exact keepalive deadline and monotonic clock jumps
- session child Job completion after remote termination
- public sessions empty after stop regardless of watcher scheduling
- partial multi-transport startup rollback
- throwing and permanently hung close operations
- identity sanitizer collisions, concurrent first creation, persistence failure, and atomic replacement
- path-observer close/restart, stale callbacks, unregister failure, and generation gating
- clean external consumer compilation from the published temp repository

### Protocol and transfer

- FrameReader fragmented/batched complexity and bad-magic early rejection
- header-version mismatch and every packet-type structural invariant
- large HELLO/OFFER/control payload attacks and log flooding
- strict malformed UTF-8 and invalid flag/LAST combinations
- outbound name/MIME/reason limits
- 2 GiB with chunk size 1 and Long overflow boundaries
- empty FILE_DATA, changing totalChunks, invalid LAST, and data after full size
- accepted-transfer idle exhaustion and full 64-slot admission exhaustion
- cancellation during accept mutex wait and FILE_ACCEPT write
- cancel/close racing sink write/finish
- blocking/reentrant source close and sink flush
- timer scheduling before map registration, wire write, and offer emission
- ordered multi-offer delivery and emission after terminal
- exact timeout authority/states on both peers
- bytes frozen after terminal
- sender result when receiver flush fails
- release of source/sink references after terminal
- source content mutation/digest mismatch
- deterministic transfer-ID collision
- Android hostile/null/negative provider metadata
- fuzz/property tests for codec, reader, reassembler, and transfer transitions

### LAN

- Android instrumentation for multicast locks, callback ordering, network rotation, permissions, unregister failure, process binding, and IPv6
- partial-completion cancellation for service/listener registration
- unregister/remove/close failures and concurrent rebind scheduling
- outbound-connect cancellation on all platforms
- normal write IOException terminal state
- restart/re-advertise after fatal accept failure
- Apple browser/listener recovery, start-close race, parent cancellation, inbound flood/drain, cache-prune race, same-type path rotation, and AWDL
- oversized TXT, unsupported pv, control characters, duplicate-PID spoof, off-subnet hosts, alternate address candidates, and connection flood
- replace global replay-count assertions with per-test baselines
- prove old Apple listener descriptors are released, not merely that a new ephemeral port differs
- isolate tests that mutate user.home, JmDNS properties, and NSUserDefaults

### Provisioning and samples

- real Android provisioning callback/cancellation and permission behavior
- process-wide binding ownership between multiple managers
- desktop poll interval boundaries and interface-ranking behavior
- Android sample unit/instrumentation tests
- CLI option parsing, target ambiguity, shutdown finally, and terminal collector cleanup
- desktop GUI create/stop races, accept cancellation, and byte-budgeted history
- Swift sink failure, atomic filename collision, partial-file cleanup, and unstructured collector cancellation
- dot-segment peer names and scoped IPv6 on every sample
- KMP Android runtime consumer and iOS consumer target

## Recommended remediation order

### P0 — before claiming production security or data reliability

1. Design authenticated identity and encryption; restructure the reader so security wraps the stream before protocol parsing.
2. Transactionalize kit lifecycle and session registration against stop().
3. Replace FrameReader's copy model and enforce early/per-type protocol validation.
4. Redesign file completion around receiver acknowledgement, accepted-transfer deadlines, and per-transfer I/O serialization.
5. Bound and clean Apple inbound connections; repair Apple/JmDNS restoration and cancellation ownership.
6. Fix multi-transport PeerRegistry aggregation and duplicate-session direction handling.
7. Correct all public-ABI dependency scopes and add an external consumer smoke test.
8. Make the full test/lint gate deterministic and green.

### P1 — reliability and platform correctness

1. Repair PeerId keying/concurrency/atomic persistence.
2. Add robust rollback/bounded cleanup for transport/session/provisioning resources.
3. Fix Android provisioning callback/process-binding races and manifest diagnostics.
4. Use monotonic keepalive timing and authoritative network-path state.
5. Fix LAN interface rotation, TXT validation, alternate-address selection, and cache liveness.
6. Replace unsafe sample file acceptance/path/history/lifecycle patterns.

### P2 — release engineering and maintainability

1. Configure remote Central Portal publication and validate the actual signed bundle.
2. Regenerate/pin the full Gradle wrapper; enable dependency verification/locking.
3. Remove volatile BuildInfo inputs and declare XCFramework provenance outputs.
4. Add CI across JVM, Android, and Apple plus ABI, coverage, lint/static analysis, SBOM, and vulnerability gates.
5. Centralize duplicated POM metadata and filename/path helpers.

## Exact coverage ledger

The inclusion rule was: every tracked file except Markdown, LICENSE, and everything under docs/. This produced exactly 232 files.

### Root and project tooling

- .editorconfig
- .gitignore
- build.gradle.kts
- settings.gradle.kts
- gradle.properties
- gradlew
- gradlew.bat
- all seven files under .run/
- gradle/gradle-daemon-jvm.properties
- gradle/libs.versions.toml
- gradle/wrapper/gradle-wrapper.properties
- gradle/wrapper/gradle-wrapper.jar
- scripts/check-publish-artifacts.sh
- scripts/run-ios-app.sh

### Library modules

- p2p-core/build.gradle.kts and every tracked file under p2p-core/src/ (132 module files total)
- p2p-transport-lan/build.gradle.kts and every tracked file under p2p-transport-lan/src/ (40 module files total)
- p2p-network-provisioning-android/build.gradle.kts and every tracked file under its src/ tree (9 total)
- p2p-network-provisioning-desktop/build.gradle.kts and every tracked file under its src/ tree (6 total)

This includes all common/platform production sources, protocol and transfer sources, cinterop definition/header files, fixtures, common tests, JVM tests, Android host tests, and Apple tests.

### Samples

- iosApp/ContentView.swift
- iosApp/P2pKitSampleApp.swift
- iosApp/Info.plist
- iosApp/build.gradle.kts
- iosApp/project.yml
- iosApp/scripts/check-xcframework.sh
- p2p-sample-android/build.gradle.kts
- p2p-sample-android/src/main/AndroidManifest.xml
- p2p-sample-android/src/main/java/dev/p2pkit/sample/android/MainActivity.kt
- p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitSampleApplication.kt
- p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitViewModel.kt
- p2p-sample-android/src/main/res/values/themes.xml
- p2p-sample-desktop/build.gradle.kts
- p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt
- p2p-sample-desktop-ui/build.gradle.kts
- p2p-sample-desktop-ui/src/main/kotlin/dev/p2pkit/sample/desktop/ui/Main.kt
- p2p-sample-desktop-ui/src/main/kotlin/dev/p2pkit/sample/desktop/ui/UniqueSaveFile.kt
- p2p-sample-desktop-ui/src/test/kotlin/dev/p2pkit/sample/desktop/ui/UniqueSaveFileTest.kt
- sample-kmp-shared/build.gradle.kts
- every tracked source/test file under sample-kmp-shared/src/

No additional issue was found in the basic application initializer, theme values, plist syntax, native interop declaration/header syntax, the non-Alice/Bob run-configuration structure, or the simple KMP factory actuals beyond the cross-cutting findings already listed.

## Final assessment

The project has a useful architecture and unusually broad protocol/unit coverage for its stage, but the current guarantees are weaker than the public surface suggests. The top problems are not cosmetic: terminal lifecycle is not transactional, remote input can create disproportionate parser/resource work, successful file delivery is not end-to-end acknowledged, Apple LAN recovery/admission is unsafe, and the official publication metadata is not consumable on its own.

Treat version 0.6.0 as an experimental plaintext local-network build until the P0 list is complete and the full cross-platform gate is consistently green.
