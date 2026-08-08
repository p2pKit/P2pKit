# A8-FILET — S8 File transfer review

Reviewed at HEAD `870bf10` (branch `audit/exhaustive-review-2026-06`). All 12 assigned files read in full; commit `7854ca7` (isolation fixes #3/#16/E:370 + CE-rethrow) reviewed as new code. Call-site cross-checks: `P2pSessionImpl` (dispatcher wiring, `closeAll`/`reopen`/`rearmWith`/`transitionToTerminal`/`routeEvents`), `SessionManager` (session construction, `closeAllSessions`), `DefaultP2pProtocol` (FILE_* encode/decode), `FileOfferPayload`, `Frame`/`MessageId`, `FileTransferConfig`, public `P2pSession`/`P2pFileOffer`/`P2pFileTransfer` KDoc, `p2p-core/build.gradle.kts` (source-set hierarchy), `FakeRawConnection`.

Base path prefix used below: `p2p-core/src/` = `/Users/abdelrahman/Projects/P2pKit/p2p-core/src/`.

## 1. Per-file verdicts

| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
|---|---|---|---|---|
| commonMain/…/internal/FileTransferDispatcher.kt | 644 | findings: FIL-1, FIL-2, FIL-3, FIL-4, FIL-5, FIL-6, FIL-7; improvements: FIL-12, FIL-13, FIL-14 | FileTransferFlowTest, FileTransferErrorIsolationTest | No source-close, dup-FILE_ACCEPT, sender-read-failure, cap, or close-mid-transfer tests |
| commonMain/…/internal/IncomingFileSession.kt | 86 | findings: FIL-10 (doc) | FileTransferFlowTest (indirect) | No direct test of terminal-CAS under contention |
| commonMain/…/internal/OutgoingFileTransferImpl.kt | 79 | findings: FIL-10 (doc) | FileTransferFlowTest (indirect) | No test that bytesTransferred can't exceed sizeBytes |
| commonMain/…/protocol/StreamingFileReceiver.kt | 94 | findings: FIL-5 (shared), FIL-10 (doc) | StreamingFileReceiverTest | abort() idempotency/after-finish, double finish() untested |
| commonMain/…/protocol/StreamingFileSender.kt | 55 | clean | StreamingFileSenderTest | Short-source EOF and mid-collect cancellation untested |
| androidMain/…/transfer/FileTransferAndroid.kt | 78 | findings: FIL-9 | none (no instrumented Android tests — documented repo policy) | Entirely untested; manual only |
| jvmMain/…/transfer/FileTransferJvm.kt | 38 | findings: FIL-9 (shared) | FileTransferJvmTest | Unreadable file, delete-between-check-and-open, source-close untested |
| commonTest/…/internal/FileTransferFlowTest.kt | 573 | findings: FIL-11; improvements: FIL-15 | n/a (test) | See FIL-11 + §3 |
| commonTest/…/internal/FileTransferErrorIsolationTest.kt | 199 | clean | n/a (test) | Only finish()-time (flush) failure isolated; onFileData write-path isolation untested E2E |
| commonTest/…/protocol/StreamingFileReceiverTest.kt | 112 | clean | n/a (test) | Missing abort/double-finish/chunk-after-finish cases |
| commonTest/…/protocol/StreamingFileSenderTest.kt | 125 | clean | n/a (test) | Missing short-source (EOF) and cancellation cases |
| jvmTest/…/transfer/FileTransferJvmTest.kt | 163 | clean | n/a (test) | Missing permission-denied file and stream-closed-after-terminal assertions |

Scope-brief answers on commit `7854ca7` in one place: `onFileDone` rethrows CE before catch(Throwable) — correct (FileTransferDispatcher.kt:476-487); its `finally { lock.withLock { remove } }` is benign under cancellation (entry left for `closeAll` sweep; nothing masked because the original Throwable was already consumed). Best-effort sends rethrow CE at **all 8** sites (lines 188-192, 218-224, 246-249, 278-281, 305-308, 337-340, 454-457, 608-611) plus `acceptOffer` and `streamOutgoingPayload` — complete. `CoroutineStart.LAZY` streamer: a cancel landing between registration and `start()` cancels the LAZY job so `start()` never runs, and every late interleaving is backstopped by the terminal re-check at streamOutgoingPayload:556 — the E:370 fix is sound (but the same function has a different hole, FIL-4). `onFileOffer` closed re-check under lock closes the insert-leak leg, but the emit stays outside the lock (FIL-7), and the symmetric outgoing-side re-check was never added (FIL-6).

## 2. Findings

### FIL-1 — `sendFile` source-close watcher is cancelled by `close()` before it can close the source → contract-violating RawSource/fd leak
- Severity: High | Confidence: Confirmed (code-path analysis; deterministic on single-threaded event loops, racy on Dispatchers.Default)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:141-144; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:291-301; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt:75-77
- Category: bug
- Root cause: the ownership watcher is a plain sequential coroutine with no cleanup-on-cancellation:
- Evidence:
  ```kotlin
  // FileTransferDispatcher.kt:141
  scope.launch {
      handle.state.first { it.isTerminal() }
      runCatching { source.close() }
  }
  ```
  `close()` (P2pSessionImpl.kt:291-301) calls `transitionToTerminal(...)` — whose NonCancellable block runs `fileTransferDispatcher.closeAll(...)` marking every outgoing handle `Failed` (terminal) — and then immediately `sessionJob.cancelAndJoin()`. The watcher is a child of `sessionJob`, suspended in `first{}` with a freshly *scheduled* resumption; `cancel()` marks it cancelled before the scheduled continuation executes, so `first{}` throws CancellationException and `source.close()` on the next line never runs. On a single-threaded event loop (runBlocking-driven CLI app) this ordering is deterministic; on Dispatchers.Default (production kit scope, P2pKitImpl.kt:79) it is a race with a wide window. `kit.stop()` reaches the same path via `SessionManager.closeAllSessions()` → `session.close()` (SessionManager.kt:739-742). The public KDoc promises the opposite: "The kit takes ownership of [source] and closes it automatically … callers must not close it themselves" (P2pSession.kt:75-77) — the audit's #21 was ruled a false positive *because* of this KDoc, which makes the implementation gap load-bearing. The JVM/Android convenience wrappers' `InputStream`s ride on this same watcher (dispatcher comment at FileTransferDispatcher.kt:137-140), so `close()`/`stop()` mid-transfer leaks their fds too; iOS apps passing their own `RawSource` have no GC backstop at all.
- Runtime impact: one leaked source/fd per in-flight outgoing transfer whenever a session (or the kit) is closed mid-transfer. | Platforms: all | User-visible: yes (fd exhaustion in long-lived apps with peer churn; StrictMode violations on Android)
- Failure class: leak
- Proposed fix (do NOT implement): make the close unconditional on watcher exit — `scope.launch { try { handle.state.first { it.isTerminal() } } finally { runCatching { source.close() } } }` (closing on cancellation is safe: teardown also cancels the streamer, and closing the source only unblocks it). Alternative: `job.invokeOnCompletion { runCatching { source.close() } }`, or have `closeAll` close swept outgoing entries' sources directly.
- Required tests: commonTest with a close-tracking fake `RawSource`: start a transfer, `session.close()` mid-stream (and separately `kit.stop()`), assert source closed exactly once. Repeat for completed/rejected/cancelled/offer-write-failure paths (each must close exactly once — the platform wrappers' catch already double-closes benignly, keep asserting idempotency).

### FIL-2 — Sender-side source read failure never notifies the receiver → accepted incoming transfer hangs forever
- Severity: High | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:582-587; contrast :450-458; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/StreamingFileSender.kt:15-16,40
- Category: bug
- Root cause: `streamOutgoingPayload`'s failure branch fails the local handle but sends nothing to the peer:
  ```kotlin
  } catch (e: Throwable) {
      val err = if (e is P2pError) e else P2pError.ConnectionFailed("FILE_DATA write failed: ${e.message}")
      handle.markFailed(err)
      lock.withLock { outgoing.remove(handle.transferId) }
      logger.warn("Session $sessionId: outgoing transfer ${handle.transferId} failed", e)
  }
  ```
- Evidence: `streamFileData` throws EOF when the source has fewer than `sizeBytes` bytes (KDoc StreamingFileSender.kt:15-16; `source.readByteArray(want)` at :40). That is a *read* failure on a *healthy* connection — realistic: file truncated/modified between `file.length()` (FileTransferJvm.kt:31) and streaming; Android content-provider stream shorter than its `SIZE` column (FileTransferAndroid.kt:71-74); any IOException from a URI-backed stream. For *write* failures the connection dies and the receiver terminalizes via its own session teardown — but for read failures nothing reaches the receiver. The receiver's accepted transfer has no post-accept timer (`IncomingEntry.timer` is cancelled at accept, FileTransferDispatcher.kt:208-209, and never re-armed) and the session keep-alive keeps the connection alive, so `incomingTransfer.state` stays `Sending(x)` forever; an app `await`ing a terminal state hangs until manual `cancel()`/session close. Compare the receiver→sender direction, which *does* notify: onFileData's failure path sends best-effort FILE_CANCEL (:450-458). Secondary defect in the same line: read failures are labelled `"FILE_DATA write failed"` — misleading diagnostics.
- Runtime impact: permanent per-transfer hang on the remote peer in normal use. | Platforms: all | User-visible: yes
- Failure class: hang
- Proposed fix (do NOT implement): in the catch(Throwable) branch, after `markFailed`, best-effort `sendMutex.withLock { protocol.sendFileCancel(getConnection(), handle.transferId, "sender error: …") }` with the standard rethrow-CE-first wrapper (pattern already used at :450-458); split the error string into read vs write phrasing.
- Required tests: E2E commonTest — sender source that throws IOException (or is shorter than sizeBytes) mid-stream; assert sender `Failed`, receiver reaches a terminal state within a bounded time, session stays Connected (isolation), FILE_CANCEL recorded on the wire (direct-dispatcher variant with RecordingFileProtocol).

### FIL-3 — No post-accept inactivity timeout; stalled transfers permanently consume the pending-offer budget
- Severity: Medium | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:318-343 (cap counts `incoming.size`), :91-95 (IncomingEntry has only the offer timer), :208-209 (timer cancelled at accept, never re-armed)
- Category: bug
- Root cause: `MAX_PENDING_INCOMING_OFFERS` (64) is enforced against `incoming.size`, which includes *accepted, in-flight* transfers; nothing bounds how long an accepted transfer may sit without progress.
- Evidence:
  ```kotlin
  val pendingState = lock.withLock {
      when {
          incoming.containsKey(transferId) || outgoing.containsKey(transferId) -> -1
          else -> incoming.size   // includes accepted in-flight transfers
      }
  }
  …
  if (pendingState >= MAX_PENDING_INCOMING_OFFERS) { …sendFileReject(…, "too many pending offers")… }
  ```
  A malicious or buggy sender that offers, waits for accept, streams part of the file and then stops (keep-alive still answered) pins its entry in `incoming` for the session's lifetime. 64 such stalls — or 64 FIL-2 occurrences — and every subsequent legitimate FILE_OFFER on that session is auto-rejected "too many pending offers" until the session closes. There is no recovery path other than the app manually cancelling stalled transfers it has no reason to know are dead. Also mislabelled: active transfers are rejected as "pending offers".
- Runtime impact: session-scoped inbound file-transfer denial of service; each stall also holds the app's sink open indefinitely. | Platforms: all | User-visible: yes (adversarial or after FIL-2)
- Failure class: DoS / hang
- Proposed fix (do NOT implement): add a per-transfer inactivity deadline after accept (re-arm `entry.timer` on each `onFileData`, e.g. reusing `offerTimeoutMillis` or a new `transferStallTimeoutMillis` config default ~60 s; on expiry: markFailed + abort + best-effort FILE_CANCEL + remove). Independently, count only `!acceptedOrRejected` entries against the offer cap.
- Required tests: direct-dispatcher test — accept, deliver one FILE_DATA, advance time past the stall deadline, assert transfer Failed and entry removed; cap test — 64 accepted-but-stalled transfers must not starve a 65th fresh offer (post-fix semantics).

### FIL-4 — Duplicate FILE_ACCEPT launches a second concurrent streamer over the same source
- Severity: Medium | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:381-405 (no Offered-state guard); :552-588; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/StreamingFileSender.kt:34
- Category: bug (defect adjacent to the new E:370 fix — reviewed as new code)
- Root cause: `onFileAccept` guards only against *terminal* states, not against the transfer already being accepted/streaming:
- Evidence:
  ```kotlin
  if (handle.state.value.isTerminal()) return
  handle.setState(FileTransferState.Accepted)
  …
  val job = scope.launch(start = CoroutineStart.LAZY) { streamOutgoingPayload(handle) }
  lock.withLock { entry.sender = job }
  job.start()
  ```
  The entry stays in `outgoing` for the whole streaming phase (removed only at :578). A second FILE_ACCEPT for the same transferId (buggy peer retransmit, or adversarial — FILE_ACCEPT is a bare control frame any peer can repeat, DefaultP2pProtocol.kt:179) therefore: (a) regresses the public state `Sending(x)` → `Accepted` (`updateUnlessTerminal` allows non-terminal overwrites); (b) launches a second streamer whose `streamFileData` wraps the *same* `RawSource` in a second `buffered()` reader — the two readers split the underlying bytes and each emits its own `chunkIndex 0,1,2…` sequence, interleaved on the wire; the receiver's `StreamingFileReceiver` sees an out-of-order chunkIndex and fails the transfer with ProtocolError; (c) overwrites `entry.sender`, orphaning the first job so FILE_CANCEL/closeAll can no longer cancel it (it keeps draining the source and sending FILE_DATA/FILE_DONE for an already-removed transfer until EOF); (d) double-counts `recordBytesSent`, so public `bytesTransferred` exceeds `sizeBytes`.
- Runtime impact: transfer fails with confusing protocol errors, full-file bandwidth wasted by the orphan streamer, state regression visible to observers. Isolation holds (no session teardown). | Platforms: all | User-visible: yes (with a non-conforming peer)
- Failure class: DoS (per-transfer) / none for the session
- Proposed fix (do NOT implement): make the Offered→Accepted transition atomic and gate the streamer on it — inside `lock.withLock`, check `entry.sender == null` and current state is `Offered` before proceeding; ignore (debug-log) duplicates, matching onFileOffer's duplicate-id policy.
- Required tests: direct-dispatcher test — sendFile, `onFileAccept(id)` twice; assert exactly one FILE_DONE, chunk sequence 0..n-1 emitted once (RecordingFileProtocol can capture frames), state never regresses from Sending to Accepted, bytesTransferred == sizeBytes.

### FIL-5 — Receiver sink data race: `acceptDataChunk` (outside lock) vs `abort()` (cancel/teardown paths)
- Severity: Medium | Confidence: Confirmed as a data race; corruption consequences Uncertain (would need a stress test on Default dispatcher to observe)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:421-459 (write path outside `lock`), :255-265 (`cancelIncoming` aborts under `lock`), :541-547 (`closeAll` aborts outside `lock`, runs *before* epoch cancel per P2pSessionImpl.kt:420-434); p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/StreamingFileReceiver.kt:30-33, 84-91
- Category: bug
- Root cause: `StreamingFileReceiver` (plain vars `bytesWritten`, `nextExpectedIndex`, `closed`; a shared non-thread-safe kotlinx-io buffered `Sink`) is mutated from two coroutines without a common lock: routeEvents' `onFileData` fetches the entry under the dispatcher lock but calls `recv.acceptDataChunk(frame)` → `sink.write(...)` after releasing it; concurrently, a user `cancel()` (`cancelIncoming`) or session teardown (`closeAll`, which `transitionToTerminal` runs *before* cancelling the epoch, so routeEvents can still be mid-write) calls `recv.abort()` → `sink.flush()`.
- Evidence:
  ```kotlin
  // onFileData — outside the dispatcher lock:
  val total = recv.acceptDataChunk(frame)      // sink.write(frame.payload)
  // cancelIncoming — under the lock, different coroutine:
  session.receiver?.abort()                     // closed = true; sink.flush()
  ```
  Concurrent `write`+`flush` on one buffered `Sink` is undefined in kotlinx-io (segment-list mutation). Exceptions are contained per-transfer (onFileData catch(Throwable), abort's runCatching), but the buffer's internal state — and hence the bytes flushed into the app's sink — can be corrupted; on the aborted-transfer path the partial file is discarded anyway, which is why impact is degraded-but-recoverable rather than data loss.
- Runtime impact: rare exceptions/garbage in an already-dying transfer; no session impact. | Platforms: all (multi-threaded dispatchers) | User-visible: rarely
- Failure class: data corruption (contained) / none
- Proposed fix (do NOT implement): make `StreamingFileReceiver` internally synchronized (a small Mutex or atomics around `closed` + sink ops), or route all receiver mutations through the dispatcher lock (take the lock for `acceptDataChunk` — writes are already serialized by routeEvents, so contention is only with cancel paths).
- Required tests: multi-threaded stress test (JVM): pump FILE_DATA while concurrently calling `cancel()`; assert no exception escapes the transfer scope and the receiver terminal state is Cancelled/Failed only.

### FIL-6 — `sendFile` lacks the closed re-check under lock that the #16 fix added to `onFileOffer` (TOCTOU asymmetry); worst case a handle that never terminalizes
- Severity: Medium | Confidence: Confirmed (window analysis; end-state depends on interleaving)
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:109-134; contrast :361-373
- Category: bug (gap in the new #16 fix's symmetry — reviewed as new code)
- Root cause: `sendFile` checks `closed` at entry (:109) but inserts into `outgoing` at :133 without re-checking under the lock, exactly the TOCTOU shape the same commit fixed for the incoming side (:361-373).
- Evidence:
  ```kotlin
  if (closed) { throw P2pError.ConnectionFailed(…) }        // :109 — check
  …
  lock.withLock {
      outgoing[transferId] = OutgoingEntry(handle = handle, timer = timer, sender = null)  // :133 — no re-check
  }
  ```
  If `closeAll` (terminal close or rearm) latches `closed` and sweeps the maps between :109 and :133, the entry is inserted into a closed dispatcher. Outcomes by interleaving: (a) usual case — the FILE_OFFER write races `connection.close()` (transitionToTerminal closes the raw *after* closeAll) and fails → caller gets `Failed`, entry removed: only wrong-window noise; (b) write sneaks out before the raw closes → `sendFile` *returns a live handle stuck in `Offered`* on a dead session; the offer timer would eventually flip it to `Cancelled("offer not accepted within …ms")` — the wrong error semantics — but if the caller path was `close()`, `sessionJob.cancelAndJoin()` kills both the timer and the source-close watcher, so the handle **never reaches a terminal state** (caller `await`ing it hangs) and the source is never closed (compounds FIL-1); (c) on the rearm path the stray entry lands in a dispatcher that is then `reopen()`ed with a swapped connection — accidental survival, unowned by the closeAll-fails-everything contract (P2pSessionImpl.kt:324-338). Related nit: `sendFile` also skips the cross-map duplicate check `onFileOffer` performs (`incoming.containsKey`, :320) — harmless at 128-bit ids (Frame.kt:98) but asymmetric.
- Runtime impact: mis-typed terminal state; in the (b)+close() interleaving a permanent app-side hang and source leak. | Platforms: all | User-visible: yes (narrow window)
- Failure class: hang / leak (narrow) ; wrong error semantics otherwise
- Proposed fix (do NOT implement): inside the `lock.withLock` insert block, re-check `closed` (mirroring :368-371): cancel the timer, mark the handle `Failed(ConnectionFailed("session closed"))`, and throw — before any wire write.
- Required tests: direct-dispatcher analogue of `offerProcessedWhileDispatcherClosedIsDropped…` for the outgoing side: `closeAll()` concurrent with `sendFile` (deterministic single-thread interleaving: call closeAll between a fake protocol's suspension), assert sendFile throws/hands back a terminal handle, `outgoing` is empty, source closed.

### FIL-7 — Offer emit happens outside the closed re-check lock: ghost offer can surface after `closeAll`
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:361-378
- Category: bug (residual gap in the #16 fix — reviewed as new code)
- Root cause: the #16 fix moved the *insert* under a `closed` re-check, but the emit is launched after the lock is released:
- Evidence:
  ```kotlin
  lock.withLock {
      if (closed) { timer.cancel(); return }
      incoming[transferId] = IncomingEntry(session = session, timer = timer)
  }
  scope.launch { _incomingOffers.emit(session) }   // outside the lock
  ```
  Interleaving: insert succeeds (closed=false) → `closeAll` latches `closed`, sweeps the map, cancels the timer and marks the session `Failed` → the launched emit still runs (failure-path terminals do not cancel the session scope) and delivers an offer whose state is already `Failed`. No entry leaks (the sweep saw it), but the app receives a dead offer; `accept()` then throws `IllegalStateException("Offer … is no longer pending")`. The test `offerProcessedWhileDispatcherClosedIsDroppedAndLeaksNoEntry` covers only the check-before-insert leg, not this insert-before-sweep leg.
- Runtime impact: app-visible ghost offer; accept throws ISE. | Platforms: all | User-visible: yes (rare)
- Failure class: none (cosmetic/state-consistency)
- Proposed fix (do NOT implement): emit inside the same `lock.withLock` block via `tryEmit` (buffer capacity 64 makes suspension near-impossible; fall back to the launched emit only if tryEmit fails), or re-check `closed`/entry-presence inside the launched emit before emitting.
- Required tests: direct-dispatcher: onFileOffer that inserts, then closeAll before the emit coroutine runs (single-thread ordering), assert no offer surfaces.

### FIL-8 — `P2pFileOffer.name` is a remote-controlled string with no sanitization warning anywhere in the API docs (path-traversal trap)
- Severity: Medium | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/P2pFileOffer.kt:24-25; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/P2pFileTransfer.kt:28-29; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FileOfferPayload.kt:37-52
- Category: bug (documentation/API-hardening gap; SDK code itself never touches the filesystem with the name — correct)
- Root cause: the only KDoc on the field is `/** Suggested file name. */`; nothing in `P2pFileOffer`, `P2pFileTransfer`, or `P2pSession.incomingFiles` warns that `name` comes verbatim from the peer.
- Evidence: `FileOfferPayload.decode` validates only length (`MAX_NAME_LEN = 4096`) and passes through any content — `"../../../.ssh/authorized_keys"`, absolute paths, backslashes, control characters, NUL. The obvious app idiom for `accept(sink)` is `File(downloadsDir, offer.name)` → a remote peer gets an arbitrary-relative-path write primitive in every consuming app. The SDK cannot sanitize on the app's behalf (it never builds the sink) — which is precisely why the doc must carry the warning; today it reads as an endorsement ("Suggested file name").
- Runtime impact: none in SDK; predictable path-traversal vulnerabilities in downstream apps. | Platforms: all | User-visible: via consuming apps
- Failure class: spoofing (enables app-level file write outside intended directory)
- Proposed fix (do NOT implement): KDoc on `P2pFileOffer.name` + `accept()` (and mirrored on `P2pFileTransfer.name`): "peer-controlled; treat as a display label — never use as a filesystem path without stripping separators/`..` (e.g. use only the last path segment and reject reserved characters)". Optionally (defense-in-depth, no API change): reject or normalize names containing `/`, `\`, NUL, or ISO control chars in `FileOfferPayload.decode` — flag as behavior change for cross-version interop review. Documenting-only is the no-API-change baseline.
- Required tests: decode test asserting the chosen policy for `"../x"`, `"a/b"`, `"C:\\x"`, `""` names (post-decision); doc presence is review-checked.

### FIL-9 — Platform wrapper defects: Android KDoc directs to a `sendFile(File)` overload that does not exist on Android; error-typing gaps in both wrappers
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/androidMain/kotlin/dev/p2pkit/core/transfer/FileTransferAndroid.kt:23-27, 31-35, 71-74; p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/transfer/FileTransferJvm.kt:20-25; p2p-core/build.gradle.kts:80-94
- Category: bug
- Root cause / Evidence:
  1. `FileTransferAndroid.kt:25-26` ("save to a temp file first and use the JVM `sendFile(File)` overload") and the thrown message at :34 ("use sendFile(file) instead") reference `sendFile(file: File)` — which lives only in `jvmMain`. `jvm()` and `android {}` are sibling KMP targets with no shared jvm+android source set (build.gradle.kts:80-94), so that overload does not exist for Android consumers; the documented remediation cannot compile.
  2. Negative `SIZE` column: some DocumentsProviders return `-1` for unknown size; `cursor.isNull` passes, `sizeBytes = -1` flows into core `sendFile`, which fails with `require(sizeBytes >= 0)` `IllegalArgumentException("sizeBytes must be non-negative, got -1")` (FileTransferDispatcher.kt:105) instead of the wrapper's purpose-built "Cannot determine size for $uri…" message.
  3. Error-typing drift vs the documented `@throws IllegalArgumentException`: `cr.openInputStream` can throw `FileNotFoundException` (only its `null` return is converted to IAE); `cr.query` can throw `SecurityException` on revoked grants. JVM side: file deleted (or unreadable due to permissions) between `require(file.exists())` and `file.inputStream()` surfaces as raw `FileNotFoundException`, not the documented IAE.
- Runtime impact: developer-facing confusion / undocumented exception types; no data-path defect. | Platforms: Android (1,2,3), JVM (3) | User-visible: developer-visible
- Failure class: none (doc/typing)
- Proposed fix (do NOT implement): treat `sizeBytes < 0` as unknown (fold into the null-size error path); fix the KDoc to give an Android-valid recipe (`FileInputStream(file).asSource()` + core `sendFile`) or add an Android `sendFile(File)` overload / shared jvmAndroid source set `[API-CHANGE]` (addition-only); widen the `@throws` docs to mention pass-through `FileNotFoundException`/`SecurityException` or wrap them.
- Required tests: Robolectric/host test for the `-1` SIZE branch if feasible; JVM test with an unreadable file asserting the documented exception type.

### FIL-10 — Stale/contradictory concurrency- and ownership-doc comments across the transfer internals
- Severity: Low | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/OutgoingFileTransferImpl.kt:19-20 vs :45-48; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/IncomingFileSession.kt:23-24; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/StreamingFileReceiver.kt:10 vs :88-89; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:226-228
- Category: bug (documentation mismatch — misleads the next maintainer on which mechanism is load-bearing)
- Evidence: `OutgoingFileTransferImpl`'s class KDoc still says "State transitions are guarded by the dispatcher's lock — direct callers of [setState] / [recordBytesSent] are expected to hold it" while the AUDIT-2026-06 comment inside `setState` states the opposite ("the KDoc'd lock discipline was never actually applied by all callers") and the real mechanism is the CAS in `updateUnlessTerminal`. `IncomingFileSession` KDoc claims "The dispatcher's lock serializes [setReceiver]/[setState]/[recordBytesReceived] calls" — false: `onFileData` calls `recordBytesReceived` and `onFileDone` calls `setState` outside the lock (FileTransferDispatcher.kt:435, 475). `StreamingFileReceiver` class KDoc says it "Owns the receiver-side [Sink]" while `abort()` says "The caller (session dispatcher) owns the sink" — and the actual owner is the *app* per the public contract ("flushed but not closed — the caller is responsible for closing it", P2pFileOffer.kt:35-37). `acceptOffer`'s zero-byte comment references a "Sending(1.0) on the first FILE_DONE" transition that `onFileDone` does not perform (it sets Completed directly).
- Runtime impact: none today; high refactor-hazard (a maintainer "restoring" the documented lock discipline or sink ownership would introduce bugs). | Platforms: all | User-visible: no
- Failure class: none
- Proposed fix (do NOT implement): rewrite the three KDoc blocks to name CAS-with-terminal-latch as the mechanism and the app as sink owner; delete the stale zero-byte comment.
- Required tests: n/a (docs).

### FIL-11 — `assertSubscriberSeesNoOffer` is a no-op: the oversize-auto-reject test asserts nothing about its headline invariant
- Severity: Medium (test defect) | Confidence: Confirmed
- File(s): p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/FileTransferFlowTest.kt:231-233, 519-523
- Category: bug (hidden test failure — looks like an assertion, asserts nothing)
- Evidence:
  ```kotlin
  // Receiver should never have surfaced the offer to its incomingFiles flow.
  assertSubscriberSeesNoOffer(incomingSession.incomingFiles.toString())
  …
  @Suppress("UNUSED_PARAMETER")
  private fun assertSubscriberSeesNoOffer(name: String) {
      // No-op probe — left as a hook so future versions can replace with
      // a definitive "flow received nothing in N ms" assertion.
  }
  ```
  The invariant "an oversize offer is rejected *before* being surfaced to the app" (`onFileOffer`'s early return at FileTransferDispatcher.kt:292-311) is real and regressable — e.g. reordering the size check after the emit would silently pass this test. The call even feeds `flow.toString()`, cementing that nothing observable is checked.
- Runtime impact: coverage illusion for a security-relevant guard (size-cap bypass to the app layer). | Platforms: test | User-visible: no
- Failure class: none (test)
- Proposed fix (do NOT implement): subscribe (`onSubscription`-gated) *before* sending the oversize offer, collect into a list, and after the sender observes `Rejected`, `yield()`/drain and assert the list is empty — same deterministic pattern the direct-dispatcher test already uses at :443-451. Do not add sleeps.
- Required tests: this is the test.

### FIL-12 — [Improvement] Inbound FILE_DATA sink writes run inline in `routeEvents` (head-of-line blocking of PONG replies and message dispatch)
- Severity: Improvement | Confidence: Confirmed behavior; impact needs slow-sink measurement
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt:518-522, 543; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:434
- Category: improvement
- Evidence: `routeEvents` processes events serially; `onFileData` → `acceptDataChunk` → `sink.write` is blocking disk I/O executed on the same coroutine that answers inbound PING (:518) and emits messages (:516). A slow app sink (SD card, SAF pipe) delays our PONG replies; if the write stalls beyond the peer's `keepAlive.timeoutMillis`, the *peer* declares us dead mid-receive. Works fine today at ≤64 KiB chunks on normal disks; also the writes run on the kit's `Dispatchers.Default` (P2pKitImpl.kt:79) — CPU pool doing blocking I/O.
- Proposed direction: per-transfer writer coroutine fed by a small bounded channel (backpressure = suspend routeEvents only when that transfer's channel is full), or at minimum document the sink-latency requirement on `accept(sink)`.
- Required tests: integration test with an artificially slow sink asserting PONGs still flow (post-change).

### FIL-13 — [Improvement] Lock-discipline consistency: `onFileAccept` mutates `entry.timer` outside the dispatcher lock
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:388-390
- Category: improvement
- Evidence: `entry.timer?.cancel(); entry.timer = null` runs after the lock is released, while `closeAll`/`handleOutgoingTimeout` read the same fields from other coroutines. Consequences today are benign (double `Job.cancel()` is safe; the FIL-4 fix would move this under the lock anyway), but every other entry-field mutation in the file is lock-guarded — keep the invariant uniform so the "per-transfer state machines under the dispatcher lock" contract stays auditable.

### FIL-14 — [Improvement] TransferId generation: seedable-but-default `Random.Default`, and no cross-map duplicate check in `sendFile`
- Severity: Improvement | Confidence: Confirmed
- File(s): p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:113; p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt:232-244 (random not passed → `Random.Default`); p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Frame.kt:98-100
- Category: improvement
- Evidence: 16-byte ids from a non-cryptographic PRNG whose prior outputs are wire-observable (message ids share the generator family). A peer predicting our next transferId gains nothing beyond its existing authority over the shared transfer (it is the counterparty), so this is not a vulnerability — but `onFileCancel`'s outgoing-map-first lookup (:493-514) would misroute a cancel if an id ever existed in both maps, and `sendFile` omits the `incoming.containsKey` check `onFileOffer` performs (:320). Cheap hardening: check both maps in `sendFile` and regenerate on collision.

### FIL-15 — [Improvement] `cancelMidStreamPropagatesToReceiver` tolerates two outcomes but hard-asserts the sender side
- Severity: Improvement | Confidence: Confirmed (reads as latent flake)
- File(s): p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/FileTransferFlowTest.kt:326-352
- Category: improvement
- Evidence: the receiver assertion accepts `Cancelled || Completed` (racy by design), but the sender assertion demands `Cancelled` unconditionally. If the 8-byte stream completes before `transfer.cancel(...)` runs (entirely possible once dispatch order shifts — `cancelOutgoing` no-ops on a terminal/removed entry), the sender lands in `Completed` and the test fails spuriously. Either pin the race deterministically (gate the streamer with a fake protocol that parks the first FILE_DATA send until cancel has been issued) or align the sender assertion with the receiver's tolerance and add a separate deterministic direct-dispatcher cancel test (one already exists for the pre-stream phase: `acceptThenImmediateCancelNeverStreamsOrSendsFileDone`). Do not widen timeouts.

## 3. Missing tests

| Invariant untested | Why it matters | Where it should live | Type | Priority |
|---|---|---|---|---|
| Source closed exactly once on EVERY outgoing terminal path (complete, reject, cancel-before/after-accept, offer-write failure, `session.close()`/`kit.stop()` mid-stream, rearm closeAll) | KDoc contract "kit closes it"; FIL-1/FIL-6 show live gaps | commonTest FileTransferFlowTest (close-tracking fake RawSource) | unit/combination | P1 |
| Sender source read failure → receiver reaches terminal state (FILE_CANCEL emitted) | FIL-2 permanent receiver hang | commonTest (direct-dispatcher + E2E) | combination | P1 |
| Duplicate FILE_ACCEPT ignored (single streamer, single FILE_DONE, no state regression) | FIL-4 | commonTest direct-dispatcher w/ RecordingFileProtocol | unit | P1 |
| Oversize offer never surfaces on `incomingFiles` (real assertion) | FIL-11 — current assertion is a no-op | FileTransferFlowTest | combination | P1 |
| Session close mid-transfer: both sides' transfer handles terminalize (no awaiter hang) | Guards transitionToTerminal↔dispatcher contract | commonTest | combination | P1 |
| Adversarial FILE_DATA/FILE_DONE/FILE_ACCEPT/FILE_CANCEL for unknown/never-offered ids leave no state change | Adversarial LAN robustness; today only debug-logged — regression-prone | commonTest direct-dispatcher | unit | P2 |
| MAX_PENDING_INCOMING_OFFERS: 65th concurrent offer auto-rejected; map stays bounded; accepted transfers don't permanently starve offers (post-FIL-3) | DoS bound is untested | commonTest direct-dispatcher | unit | P2 |
| onFileData write-path failure isolation E2E (sink.write throws, not flush) | Code claims parity with onFileDone; only finish() leg tested | FileTransferErrorIsolationTest | combination | P2 |
| FILE_DATA before accept is dropped without state damage | Protocol-order robustness | commonTest direct-dispatcher | unit | P2 |
| StreamingFileReceiver: chunk-after-finish, double finish(), abort() idempotency/after-finish | Terminal-latch semantics of the receiver | StreamingFileReceiverTest | unit | P2 |
| streamFileData: source shorter than sizeBytes throws; cancellation mid-collect leaves source open (caller-owned) | FIL-2 trigger + ownership contract | StreamingFileSenderTest | unit | P2 |
| Zero-byte file end-to-end (offer→accept→FILE_DONE→Completed both sides) | Only unit-level halves are covered | FileTransferFlowTest | combination | P3 |
| Android URI wrapper (null/-1 SIZE, FNF, SecurityException) | Wrapper entirely untested (no instrumented tests — repo policy) | manual recipe INTERNAL_TESTING.md (or Robolectric host test) | manual/unit | P3 |

## 4. Section summary

**What S8 owns.** The per-session file-transfer subsystem: `FileTransferDispatcher` (FILE_* state machines for both directions, offer cap, timers, error isolation), the two transfer-handle implementations (CAS terminal-latched state holders), the kotlinx-io streaming halves (`StreamingFileSender`/`Receiver`), and the JVM/Android convenience constructors. Wired into `P2pSessionImpl.routeEvents` (serial event dispatch) and torn down via `closeAll` from `transitionToTerminal`/`rearmWith`.

**Overall health.** The core design is sound and the `7854ca7` isolation work is genuinely good: the transfer-failure-never-kills-the-session invariant now holds on every inbound Throwable path I traced, CE rethrow is complete across all 10 best-effort/streamer sites, and the LAZY-streamer registration closes E:370 with a correct double backstop. The weak flank is *lifecycle edges*: resource ownership on `close()` (FIL-1), the sender→receiver failure channel (FIL-2/FIL-3), and residual TOCTOU legs the #16 fix didn't mirror (FIL-6/FIL-7). Protocol-input hardening (name/mime caps, reason caps, size checks, offer cap, malformed-offer skip) is in good shape; the state machine trusts frame *sequencing* more than it should (FIL-4).

**Top 3 risks.**
1. Receiver-side permanent hang when a sender's source fails mid-stream on a healthy connection (FIL-2, compounded by FIL-3's missing inactivity timeout and cap coupling).
2. `sendFile` source leak on `close()`/`stop()` — direct violation of the documented ownership contract the audit's #21 dismissal leans on (FIL-1).
3. Apps inheriting a path-traversal write primitive from the undocumented remote-controlled `offer.name` (FIL-8).

**CODEBASE_REVIEW_MAP_2026-07.md accuracy (S8 entry, lines 207-224).** Mostly accurate (ownership list, dependencies, "transfer failure must never tear down a healthy session"). Discrepancies: (a) "Test coverage: good, incl. new error-isolation tests" overstates — one headline assertion is a no-op (FIL-11), and there are zero tests for source-close ownership, adversarial FILE_* sequences, the 64-offer cap, or close-mid-transfer; (b) "sender owns the source (kit closes it — documented contract)" is stated as an established fact, but the implementation does not honor it on the close path (FIL-1); (c) "per-transfer state machines under one dispatcher lock" is only half-true — terminal-state integrity actually rests on CAS latches, with several state mutations deliberately outside the lock (see FIL-10/FIL-13); the map (like the internal KDoc) names the wrong mechanism.

---

## Orchestrator verification (2026-07-04) — FIL-1 & FIL-2 CONFIRMED

Independently re-checked against source (not the report text) at HEAD `870bf10`:

**FIL-1 — CONFIRMED (High).** The load-bearing fact — that the source-close
watcher is a child of `sessionJob` and is therefore killed by `close()` — is
verified:
- Watcher: `scope.launch { handle.state.first { it.isTerminal() }; runCatching { source.close() } }` — no `finally` (FileTransferDispatcher.kt:141-144).
- `scope` identity: `private val scope = CoroutineScope(parentScope.coroutineContext + sessionJob)` (P2pSessionImpl.kt:126), and the dispatcher is built with `scope = scope` (P2pSessionImpl.kt:172). So the watcher IS a direct child of `sessionJob`.
- `close()` ordering: `transitionToTerminal(...)` (:291) → its NonCancellable `closeAll` calls `handle.markFailed(...)` (FileTransferDispatcher.kt:538), which flips `handle.state` to a terminal value and *schedules* the watcher's resume; then `close()` immediately runs `sessionJob.cancelAndJoin()` (:301), cancelling the watcher.
- Verdict on the race: on a single-threaded dispatcher (runBlocking CLI / confined test) `cancelAndJoin`'s synchronous `cancel()` marks the watcher cancelled before it gets CPU, so `first{}` resumes into a cancelled coroutine → CancellationException → `source.close()` is **deterministically skipped**. On `Dispatchers.Default` (production kit scope) it is a wide race. Either way the "kit closes it automatically … callers must not close it" contract (P2pSession.kt:75-77) — the exact KDoc the earlier remediation used to rule audit finding **#21 a false positive** — is violated on the `close()`/`stop()` mid-transfer paths.
- Scope refinement (added by orchestrator): the **rearm** path is NOT affected — `rearmWith` runs `closeAll` (which markFaileds handles, letting the watcher resume and close the source normally) but does **not** cancel `sessionJob` (only `epochJob`), so the watcher survives there. The leak is specific to `close()` and `kit.stop()` (→ `SessionManager.closeAllSessions()` → `session.close()`) while a transfer is in flight. Normal completion/reject/cancel paths also close the source correctly (no concurrent `sessionJob` cancel).
- This makes FIL-1 a direct correction to REMEDIATION_2026-07.md's #21 disposition: #21's *KDoc claim* is right, but the *implementation* does not honor it on close/stop. Recorded as a confirmed High.

**FIL-2 — CONFIRMED (High).** Verified the asymmetry directly:
- `streamOutgoingPayload` catch(Throwable) (FileTransferDispatcher.kt:582-587): `markFailed` + `outgoing.remove` + `logger.warn` — **no wire notification to the peer**.
- Contrast onFileData failure (FileTransferDispatcher.kt:449-461): best-effort `sendFileCancel(...)` with CE-rethrow-first. The receiver→sender direction notifies; the sender→receiver direction does not.
- Receiver has no post-accept timer: the offer timer is cancelled at accept (`e.timer?.cancel(); e.timer = null`, FileTransferDispatcher.kt:208-209) and never re-armed; session keep-alive keeps the healthy connection up. So on a sender-side **read** failure (source shorter than `sizeBytes`, truncated file, URI stream error) the receiver's transfer state stays non-terminal indefinitely → an app awaiting a terminal state hangs. (A sender-side **write** failure is different: the connection dies and the receiver terminalizes via its own session teardown, so only the read-failure-on-healthy-connection case hangs — exactly the report's claim.) Recorded as a confirmed High.

Both findings' impact statements and required-tests in §2/§3 above stand as written. No code changed.
