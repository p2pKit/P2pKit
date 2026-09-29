# Supplemental Mac runtime continuation — 2026-09-29

## Scope

**All six planned supplemental phases passed on the exact candidate below:
fresh simulator readiness, the complete strict platform profile, Apple framework
production, Swift unit/UI runtime, fresh peer preparation and real Swift/JVM
sample integration. These results do not complete release qualification.**

This is source-bound supplemental evidence from the owner-authorized Intel
macOS 26.6.2 / Xcode 26.6 VPS, using the installed iOS 26.5 simulator runtime.
It is not the supported Apple Silicon/macOS 26/Xcode 26.5 or true
Intel/macOS 15/Xcode 26.3 matrix, Android ART, physical/security, or capacity
qualification. Release Foundation remains **NOT_READY**; all HOLDs remain.

Latest test candidate: `62716271ab5b9ee7f03bcb1ab2deb854ef1511f3`.
The earlier `c98945355438e017d91fcd7656916c7c17dc31ad` candidate and all its
successful and failed receipts remain bound to that source.
The existing feature branch is `work/rpc-lan-20260927-054728-8b1b11da`.
Fresh main remained `3bc76f956f8f47447b51a62474fc878b9c43173c`.
No unfinished Foundation source or repaired files were imported.

Only the authorized Mac executed Java/Gradle/Xcode/application commands.
No local Java/Gradle/Xcode/application execution, local SDK/dependency download,
shared hosted run, security-policy change, additional reboot/remount, external
publication, main merge, or release tag was performed in this continuation.
The existing private, identity-owned audit executor, original deadlines,
strict dependency verification, two-worker policy and same-home finalization
were retained. Each source candidate used a new full-history/no-tags,
canonical-origin clone and separate Gradle/Native homes. Failed attempts were
not overwritten or reused as producers.

## Safe resource cleanup and recovered simulator readiness

Normal Cocoa quit requests were used, not PID/group/name signals or force quit.
Notes and Activity Monitor closed; Xcode accepted its initial quit request but
had not exited after that invocation's ten-second observation. A later admitted
AppKit inventory verified that all three were closed, leaving Finder and
Simulator. SSH, system services and the owner's booted simulator were preserved.
No unsaved work was discarded.

A new task-owned simulator passed the original 120-second `simctl bootstatus`
bound. Its Booted state was independently observed, then exact owned Shutdown
was verified. Fresh native admission of the test candidate passed all 122
controls and its enclosing finalization. Earlier September 28 system-app
readiness failures remain failed; the later recovery is not a proven OS root
cause or a reason to extend deadlines.

The initial September 29 read-only process probe separately recorded one
native identity-observation permission failure. Its failed receipt was retained.
A later exact-lifetime query positively verified that the retained lifetime had
ended; absence from a process census was not accepted as proof. A new admission
context was used afterward. No elevated observer or OS policy bypass was used.

## Preserved full-profile failure and bounded test correction

The first September 29 full profile on `1a541f33337e7b9fba4c55d6595d6cd5d0bd4ef5`
failed one existing core test:
`StuckReconnectWatchdogTest.eagerlyEnteredHandlerOwnsAnUnstartedTimerAndImmediateRearmCancelsIt`.
The Native stack identifies the original line 112, the combined
`isCancelled && isCompleted` assertion. The report did not record the two
boolean operands individually, so it does not establish their individual
values. Partial core results were 791 iOS passes/one failure, 857 JVM passes,
and 82 Android-host passes. The other 17 required tasks did not complete.
That full profile remains **FAIL**, with product/final exit 1 and stop exit 0;
source integrity, empty owned-survivor/discovery-error inventories and exact
simulator Shutdown were verified. All 201 emitted XML suites, logs, coverage
and receipts were retained and independently reviewed.

The test was already present on main. Production `rearmWith` requests watchdog
cancellation but does not join completion; real epoch cleanup can suspend the
eager handler long enough for the initially lazy watchdog to start. Assuming
synchronous completion after `cancel()` is therefore unsafe. Commit `c9894535`
changes only the
[watchdog test](../../library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/StuckReconnectWatchdogTest.kt):

- Require cancellation to have been requested after the reconnect handler ends.
- Join the registered timer inside the existing real **five-second** settlement
  deadline, before asserting completion.
- Preserve the original final cancellation/completion assertion, child-count,
  warning and 30-second virtual diagnostic checks.
- Add a deterministic queued-cancellation control that proves join waits for
  completion without advancing virtual time.

No production behavior, dependency input, API, platform skip, assertion or
existing timeout was relaxed. This is independent of the previously corrected
stale `org.jmdns` baseline locks, not an RPC transport regression or an import
from Foundation.

## Preserved Swift failure and first-use keyboard correction

The `c9894535` candidate passed fresh admission and the complete strict profile:
**2,959 passes**, zero failures/errors, one pre-existing ignored diagnostic,
381 XML suites and all 20 required tasks. Both seven-case watchdog suites
passed on JVM and iOS x64. Its fresh Apple framework producer, provenance,
minimum-OS checks and maintained Xcode project generation also passed. These
results were independently reviewed from canonical receipts, logs, XML and
producer sidecars, not inferred from console success markers alone.

Its ordinary Swift scheme actually executed all maintained methods: **88 unit
passes, five UI passes and one UI failure**. The English rendered-port test
failed at the production-control reachability assertion; the German counterpart
passed. Product/final exit 65 and stop exit 0, empty owned survivor/error
inventories, unchanged source and exact simulator Shutdown were verified.
The strict case assessor rejected the failed run; its actual xcresult remains
retained. Successful prerequisites do not erase that failure.

The retained failure recording, not just an invalid-hit-point log, showed iOS's
first-use **“Type English and German”** keyboard introduction covering the form
through the failure. The test had entered the unmodified rendered port but then
tried to tap the covered Done toolbar and swipe to the pairing field. The same
run's invalid-frame warning is not an established cause. The product port
parser and intended pairing guard were not reached by that failed case.

Commit `62716271` changes only the
[UI test harness](../../samples/iosApp/UITests/ContentViewPresentationUITests.swift).
It matches the exact known system heading and explanation, performs one reachable Continue action and
requires the sheet to disappear. It also requires the keyboard toolbar to be
hittable and the software keyboard to disappear after Done. It does not dismiss
arbitrary dialogs, modify global keyboard settings, inject application state,
retry an acknowledged introduction, remove a test or change existing deadlines,
the six-swipe bound, production controls or port-parser assertions.

All evidence interpretation and frame decoding used the owned original bundle,
bounded read-only observations and unchanged native command ownership. No
current owner desktop capture, custodian material or other session evidence
was used. Raw recordings and device identifiers remain private task artifacts,
not repository documentation.

## Preserved cold-tool admission failure

The first fresh `62716271` context completed all 122 native controls, but its
mandatory same-home `gradlew --stop` was still downloading the pinned Gradle
9.7.0 distribution when the unchanged 120-second stop deadline expired.
Product exit was 0; stop was 143 and final admission was 125. The original
failure remains **FAIL**, despite the successful test count and empty final
owned-survivor/discovery-error lists. No later product phase ran in that context.

A separate authorized tool-preparation command used the earlier fully admitted,
idle task context to download the public distribution once. Its **150,308,896**
bytes matched the checked-in SHA-256 pin:
`84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae`.
Only that archive was staged into another new context before admission. The
unchanged wrapper still had to verify/extract it and complete its real stop.
No build cache, Gradle daemon, resolved dependencies, false installation marker,
failed-home reuse, timeout extension or source/ownership-policy change was used.
The new context passed all 122 controls and successful enclosing finalization.

The failed-admission archive is retained with SHA-256
`932a11b66453a32ad30eeca24e7604988d1f1b20f47c4450d34273326ed6623a`.

## Latest immutable-candidate results

The new candidate passed **122 native controls** and their enclosing finalizer.
Fresh original-bound readiness, exact owned Shutdown, source integrity and the
GUI cleanup were independently verified. The strict full profile passed all
**20 required tasks**: **2,959 passes**, zero failures/errors, one pre-existing
ignored LAN diagnostic, and 381 independently matched XML suites. Both exact
watchdog controls executed successfully on JVM and iOS x64. The full phase ran
from 05:35:51 to 06:12:50 UTC, including preparation and finalization; this is not
a capacity measurement. Canonical receipt product/stop/final exits were all zero.

The subsequent same-source Apple phase passed fresh release XCFramework
production/provenance, minimum-OS inspection and maintained project generation.
The Swift phase then passed **all 88 unit and six UI methods**, with warnings as
errors, no test filters, an independently assessed actual xcresult, exactly one
mandatory nested producer receipt, and verified simulator Shutdown. The English
rendered-port case recorded the new identified keyboard-introduction activity
exactly once and passed. The German counterpart also passed. Thus the corrected
first-use branch actually ran; its success is not inferred from compilation.

Fresh CLI and dedicated UI-scheme preparation passed, with compiled-input hashes
and same-source framework provenance checked before runtime. The maintained
[`run-swift-jvm-transfer.py`](../../scripts/run-swift-jvm-transfer.py) then passed
its **one actual native test case** with **204,800 bytes in each direction**:
Swift to JVM and JVM to Swift. Both distinct transfers recorded matching sender/
receiver integrity and completion evidence. The original 360-second experiment,
900-second enclosing command and 30-second natural CLI-quit bounds were unchanged.
The pre-Dial RAW-clock activity, consent before receive, installed/prepared
artifact equality, real Swift Stop and natural CLI shutdown were verified.
No incomplete child or cleanup error remained; the exact owned simulator was
subsequently verified Shutdown. The full phase sequence finished at 06:38:27 UTC.

This is the **existing P2P sample's same-codebase host/simulator integration**, not
RPC application or independent implementation/physical interoperability. Swift
pins the CLI; incoming CLI peers still use the existing authenticated same-AppId
development policy. It is not organization RPC authorization, physical-network,
crash-durability, professional cryptography or capacity qualification.

Every phase was independently checked from bounded, finalized receipts, original
logs, XML/native summaries, source/invocation bindings and retained bundle/producer
manifests. The final export also passed its own source/ownership finalizer. No
unresolved ownership discovery error or invocation-owned survivor was accepted.
Actual xcresult bundles remain on the Mac; only bounded text evidence was copied
into this workstream's private local evidence. No dependency or compiled binary
was downloaded locally.

The previously successful artifact/consumer candidate remains `5ed6dbed`, and the
ABI/Dokka/SBOM/sample-build record remains `ec44b7d0`. Comparing library, sample
and build inputs from `5ed6dbed` to `62716271` finds only the two test-file changes
described above. Those older results are not relabeled as fresh current-source
executions or added again as unique test coverage.

## Offline documentation follow-up

The documentation-only follow-up ran these permitted local checks successfully:

- `scripts/tests/check-repository-layout.sh`: all 12 project mappings, 15 Android
  setup negative controls and seven RPC inventory negative controls.
- `scripts/tests/check-osv-lockfile-coverage.sh`: all 12 nonempty lock inputs and
  the verified embedded upstream inventory; **not** a vulnerability scan.
- `scripts/tests/check-markdown-links.sh`: 531 links across 104 active documents.
- `scripts/check-release-metadata.sh`, `git diff --check` and staged whitespace
  checks. Source/publication versions, instructions and the approved plan are
  unchanged. No local compiled-language build or dependency download ran.

These checks do not relabel the tested `62716271` runtime as an execution of a
later documentation-only commit.

## Evidence binding

The following hashes identify retained task-owned evidence, not an independent
third-party qualification or release approval:

| Source / evidence | SHA-256 |
|---|---|
| `1a541f33` preserved failed full-profile archive | `0a2b62422db7076da1bac95ccac2459cd0a742b2ac06f70a1f55d01aa935540b` |
| `c9894535` successful core/full archive | `cb1fa36567d69c5d8ac467f89a2f495898304336899d046e7fb2f66457f623fe` |
| `c9894535` successful Apple/prerequisite archive | `3bdbcd03ba0744fe4160bfd46ef8366b0a06483b1cca30c1822684fcc1762dd2` |
| `c9894535` preserved Swift-failure archive | `022415a27a35613f0f1ab288c961d9e4ea66c4007e9c3c33ece6567e3bc30904` |
| Preserved failure recording/attachment export | `d61d54cada8aa16ca0c4fa36b70003ecad03958cfd4a8bce878814ab12af65eb` |
| `62716271` complete full-profile archive | `452b3a82e9e5d0745c6f7ccf236637c930247b09e926d6d355374b75c211ab3c` |
| `62716271` Apple/Swift and prerequisite archive | `de73f1e443a2f48429af28290b628c7c2d6a5d78471d6a711134edb1983dfe6a` |
| `62716271` all six successful phases, complete bounded text archive | `02d8f61deff47948d894e269ced6d74b31b5ceadc2c5204c401350038c0e6e64` |
| Latest native admission receipt | `84d6c9969765ffcad901d5aa172670a51faba3661ec6b77c18ddec8ed251a3a5` |
| Latest full-profile receipt | `07fa0cea42af2660dd7d393f2853ccb74617f60c81952d6c50c67f09f2095bec` |
| Latest XCFramework producer receipt | `ce07d788aff093cc1fbabb41815e9d33aac1ba0b04721fd91656fe221b33e540` |
| Final text-export receipt | `bb8214930ac5a3c649a3e962e0d80b84a807f7115000b49b0adcaa6df4fe772a` |

## Remaining gates

- Supported-host Apple matrix: Apple Silicon/macOS 26/Xcode 26.5 and true
  Intel/macOS 15/Xcode 26.3. Prior hosted ownership-admission failures remain
  failures and were not retried or bypassed here.
- The separately gated owned-cancellation follow-through. Its maintained route
  requires ARM; ordinary Swift cases, clean shutdown and this Intel integration
  do not replace it or authorize an Intel/raw-process bypass.
- Android ART. This VPS previously reported `kern.hv_support=0`; no accelerated
  Android emulator was launched. The separately requested temporary Linux
  runner KVM-access exception remains unanswered.
- Real iPhone/Android application integration, permissions, approved identity
  and trust storage, physical interoperability, and real-network/security tests.
- Each actual host's 128 authenticated clients × 10 calls/second × 1,800 seconds
  at 1 KiB request/reply (**2,304,000 successful responses**), actual host
  telemetry, and the separate bounded 1 MiB experiment. No such capacity has
  been measured or qualified by these tests.

The RPC sample remains shared source and a qualification driver, not a turnkey
signed phone installer. Existing P2P sample tests do not silently become RPC
application, real-network, crash-durability, independent implementation or
physical-device evidence.
