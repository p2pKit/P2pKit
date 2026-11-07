# RPC durable result acceptance — #543

The rc12 source candidate adds `RpcClient.callWithAcceptance` and immutable
`RpcResultAcceptance`. See the [API contract and usage example](../rpc/durable-result-acceptance.md).
The implementation branch starts at main `8dff5c05ab1bf9bbaf4dc10269a528ff158abaa9`.
This record covers source review and automated regression, not physical-device
qualification or Maven publication. The PR supplies the final source and CI links.

## Four additional review passes

These are four separate reviews by the lead agent, with different checklists;
they are not claims of four independent human reviewers.

| Pass | Reviewed | Findings and resolution |
| --- | --- | --- |
| 1 — acceptance and association | Terminal decode, callback, failure propagation and exact Receipt fields | Added hostile request-ID, procedure name/version, Host-incarnation and attachment tests, concurrent-result isolation, typed business-error acceptance/rejection, validation/write failures and fatal/cancellation exceptions. No user-accessible Receipt token exists. Acceptance failure never reenters the transport retry loop. |
| 2 — cancellation and scheduling | Call deadline, callback suspension, queued ticket lifetime and physical-generation changes | Found that a blocking callback could outlast the monotonic deadline before timeout dispatch. Added an explicit post-callback clock check and a writer deadline guard. Added swallowed-cancellation, queued-cancellation, Receipt timeout, generation change after queueing, actual `SessionRpcLink` writer and eight-slot admission tests. Unstarted tickets and payload leases drain. |
| 3 — security and recovery | Authenticated link/Host association, original request digest, scoped control authorization, idempotency, retention and duplicate delivery | Host authorization and retention code remain unchanged. Verified fresh scoped Receipt denial retains the body, lost-response recovery accepts once with one handler execution, and lost Receipt plus duplicate Invoke does not reexecute. Found that a nested RPC failure from an acceptance callback could acquire the outer call's ID/evidence; preserve the nested exception and its original retry advice instead. Added a regression. Body expiry and non-reinvocable tombstones retain their existing bounds. No durable resume-by-ID or application transaction guarantee is invented. |
| 4 — compatibility and integration | Public/default signatures, JVM/Android/Native API baselines, legacy calls, metrics, documentation and release constraints | Existing signatures remain; all four generated ABI views contain only additions. Kept the new decoded snapshot allocation inside the opt-in branch. Legacy calls still automatically Receipt; completion totals remain after the timeout return boundary. Added a real JVM forced-file journal/failed-write check, and documented commit/Receipt/crash races. |

## Automated verification

Run using native JDK 17, the pinned wrapper, strict dependency verification and
the canonical Android SDKs. Local builds use a task-owned Gradle home and stop
that home's Gradle processes after each run.

```bash
./gradlew --no-daemon --no-build-cache --no-configuration-cache \
  --dependency-verification strict --console=plain --max-workers=2 \
  :p2p-rpc:jvmTest :p2p-sample-rpc:jvmTest :p2p-rpc:testAndroidHostTest \
  :p2p-rpc:checkKotlinAbi :p2p-rpc:checkAndroidAbi \
  :p2p-rpc:dokkaGeneratePublicationHtml
```

The final local regression report records 160 RPC JVM, 670 sample RPC JVM and 147 RPC
Android-host cases, with zero failures/errors/skips. The JVM journal test awaits
`FileChannel.force(true)` before Receipt and verifies an actual closed-channel
write failure sends no Receipt. This tests application-owned persistence ordering;
it is not a calibrated power-loss or database durability qualification.

All six tasks above passed after the nested-exception correction. The preceding
`:p2p-rpc:updateKotlinAbi` and `:p2p-rpc:updateAndroidAbi` generation also passed;
all four resulting baseline diffs were independently reviewed as additions only.
Normal modular PR CI also covers
both JVM operating systems, native Apple execution, Android, ABI, strict Dokka,
isolated consumers, security/dependency policy, SBOM and packaging. CI results
must be read from the exact PR revision; no release-main qualification is inferred.

Repository layout, lockfile coverage, Markdown links, release metadata and
whitespace checks also apply. `scripts/check-maven-central-version.sh absent`
confirmed that rc12 was absent during preparation; this is not a publication pass.

## Retained failures and limits

- The initial focused suite had one fixture failure: coroutine-debug exception
  recovery copied a standard exception. A non-copyable application exception now
  retains the exact original-identity assertion and the full no-Receipt/no-retry checks.
- The first real-I/O fixture used virtual coroutine time while disk I/O ran on
  another thread, producing a deadline failure. It now uses real coroutine time
  with the same timeout. A missing constructor invocation in that correction
  caused one compile failure and was fixed before the successful regression run.
- Original failed logs/results are retained privately. No deadline, assertion,
  verification checksum, lock, target or platform test was disabled to obtain a pass.
- The first PR CI run at the earlier source was superseded and cancelled after
  the nested acceptance-exception review fix. Its jobs do not qualify the final revision.
- Receipt is best effort after local acceptance. Cancellation/crash after a
  durable commit cannot undo that commit or recall an already-started Receipt.
  Persistence and business idempotency remain the application's responsibility.
- `VERSION_NAME=0.8.0-rc12` is a prepared candidate;
  `LATEST_PUBLISHED_VERSION=0.8.0-rc11` remains the verified public version.
  The owner explicitly requires an unmerged PR. The maintained publisher requires
  a qualified main merge, so no rc12 tag/upload is authorized by this state and
  no new Maven availability or consumer-resolution pass is claimed.

The existing installed phone/Mac applications, profiles, saved tests, deferred
#520 investigation and cancelled full audit are outside this source change.
