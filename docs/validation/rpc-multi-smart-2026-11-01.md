# Manual RPC Multi-device and Smart Test preparation — 2026-11-01

This report covers software preparation for owner-started application tests in
[PR #533](https://github.com/p2pKit/P2pKit/pull/533), stacked on
[PR #532](https://github.com/p2pKit/P2pKit/pull/532). It does not establish physical
128/256-client qualification. [#525](https://github.com/p2pKit/P2pKit/issues/525)
remains open.

## Source and products

Prepared implementation commit: `5683c28cdc0edfed8246b391904a2c0557ec319c`.
Tree: `5e8335aca5fdb8dcd67ce6665ec25a3cb0d4886c`. The clean preparation source descends
from verified main `eb6ba5da6c06a440de852477cf485264b2ab3dd3` and the preceding
manual test implementation `b62b80e910b1581626cd0eb7878f0972f6997aff`.
The report/screenshot commit is separate; it is not the artifact producer.

Native Apple-Silicon Mac, Python 3.14, Xcode 27.0 (27A266a), XcodeGen 2.45.4,
JDK 17.0.17 and 21.0.11 (aarch64), Android platforms 36 and 37.0 and pinned
NDK 29.0.14206865 passed maintained preparation. Existing local development
signing produced an arm64 iPhone app; signature verification passed. No tag,
publication, Maven credential, VPS access or signing-secret migration was used.

| Prepared product | SHA-256 |
| --- | --- |
| Android APK | `608b96dcfd3735d2870cc683554b723b1db628de008984ffd4c6383ec649abc7` |
| Signed iPhone executable | `586bbb9ac9cc9654d3652360fc456a9e191760b66bbf3f7cc4db09267ff7a976` |
| Signed iPhone code resources | `148bf74b28429dd5bb65cc105aa1b49f40f9e0b96d2df16da1bb1a8761eba1fe` |
| Signed iPhone debug dylib | `783caf778b8c0a35b2109c74d335c30b0ae81ab6ea157c13ead2110ed16f4f73` |
| iPhone arm64 framework | `bc23a92c33657a1369f347290b0c71ca1528cbf722a822220213a32a378eca44` |
| Mac driver JAR | `f183c7b82846a05d5a7e564df1e8d214ba81bc102692bc301f62828b1055ed9f` |
| Mac driver inventory | `b1d73f0f98328542bbb4a9e2682842e6eb5b8018ecbb458649588da3c698a0e8` |
| Mac native transport | `9c07edd53fda38e1f214fbb1d956997e8b26775369db1d814e00ec9ef2c96e9a` |
| Mac native manifest JAR | `a5b3a6f6523a43fff2664dc2abd3fdba4742fbcc79b1b705a87ddca27e0dc28f` |

The private complete preparation manifest is bound by SHA-256
`4b8596803ff342be79f1a8d8397325aa10d472b792e868efdd896c14c195c77c`.
The full signed app file inventory, represented as a UTF-8 JSON object of
app-relative filename → SHA-256, sorted by key without whitespace, has digest
`fe13f6d0933df08982245d3dc4cae44af6b01752641913d0862a5d7e57533a65`. The private manifest retains every original binding;
paths, device identifiers, approvals, signing material and raw evidence are not uploaded.

The later regression commit `ab350b6eb2b4a89518b5c2b7e92b1d7d736e477b`
changes only the CI roster check and two portable UTF-8 test assertions.
Its application sources are byte-identical to the frozen producer. These later
checks do not rebuild or substitute the prepared products above.

## Delivered behavior

- Separate Pair/Multi screens; up to 16 distinct trusted Clients in a Host-started
  group, isolated per-run progress, cancellation, telemetry and reports.
- Permanent bounded per-run archives with direction, source, timestamps, group,
  latency, counters, deliberate fault outcomes and available resource samples.
  Display clearing retains data; explicit selected deletion writes a durable
  deletion marker and blocks new admission during removal.
- Live progress and resource monitor; missing counters remain unavailable.
  Overlapping runs share one process; their resource totals cannot be summed.
- Adaptive request/in-flight search starting at 1 request/s, growing, detecting
  latency/error/scheduling pressure, backing off, refining and freshly confirming.
  Safety stop reasons and every bounded stage are retained.
- iPhone ordinary manual roles/tests use the existing non-renewing 25-second app
  switch allowance on the approved automatic Wi-Fi path. Lock, network change,
  OS expiration and memory/thermal pressure still stop safely.

Follow [the manual device guide](../rpc/manual-device-tests.md). Crypto, protected
identities, first-connection approval, Host admission, host128 defaults and the
Apple ABI are unchanged. RPC remains on the approved private LAN.

## Local verification

Application/native checks at the exact frozen implementation source:

- `:p2p-sample-rpc:jvmTest`: 705 tests, zero failures/errors/skips.
- `:p2p-sample-android:testDebugUnitTest`: 398 tests, zero failures/errors/skips.
- Maintained `prepare` completed the APK, XCFramework, signed iPhone app and
  native Mac driver; `prepare-macos-rpc-desktop.py` staged the manual Mac UI.
- All preparation receipts finalized with Stop exit 0, no errors or owned survivors.

- Native iPhone controls: 93 unit methods + 9 UI methods, 102 total, zero failures;
  `** TEST SUCCEEDED **`. The owned simulator was shut down and deleted.
- Mac UI opened as an owner-controlled manual application using the preserved
  selected profile. No role or workload was started by delivery.

Phone installation is awaiting the owner's current Stop and iPhone reconnect.
The working older phone apps and all their outputs remain intact at this point.
The screenshots in the manual guide are current-source idle fixtures, with no
physical workload or capacity credit.

Maintained Python controls also passed during refinement: 27 iPhone runner,
42 Mac campaign and 49 hosted validation tests; RPC policy negative controls
passed (33 cases). The corrected roster's 10 regressions passed at `d4b12f4e`.
Python 3.14 was selected explicitly; an initial system-Python 3.9 invocation
failed two unsupported `hashlib.file_digest` checks and was retained separately.

## Original failures and recovery

Private original attempts are retained separately. Earlier preparation encountered
an unavailable offline dependency, a duplicate test class name, a virtual-clock
opt-in requirement, and an Android lifecycle assertion mismatch. Fixes retained
original assertions and moved memory callback removal into the existing detach
lifecycle. The corrected intermediate source passed 705 JVM + 398 Android tests;
final source reran both successfully.

A native control attempt refused the existing generated-project directory. The
prepared project was retained separately and the runner's new-directory
precondition was preserved. A later native compile exposed a missing main-actor
annotation in a test; it was fixed. The intermediate native suite passed 99/102:
one stale manual-refresh expectation and two scroll/disabled-control checks
failed. Their assertions were corrected to the actual approved behavior. The
exact stalled Xcode invocation was cooperatively cancelled; its original
cancellation errors remain, with Stop exit 0 and no owned process survivors.
The separately identified owned simulator was shut down and deleted. The final
source passed all 102 methods and its original cleanup.

Native framework production invalidated an earlier complete preparation; that
manifest is not reused. The final attempt also refused a duplicate immutable
wrapper-cache receipt. Its already-successful seven Doctor and native receipts
were verified and reused, then preparation completed without repeating XCTest.

Hosted Apple common tests exposed two JVM-only `String.toByteArray()` assertions.
The local compiler reproduced those failures; its product exit was 1. A readback
command also created Python bytecode in the frozen producer, causing source
finalization to refuse (final exit 125, Stop exit 0, no owned survivors). The
created cache was moved to private retained evidence, restoring the clean source.
The two assertions now use portable `encodeToByteArray()` without relaxing bounds.
Their hosted ARM/x64 reruns are tracked below.

The initial idle preview refused before preparation. The clean preview rendered
both Mac pages and exported successful native screenshots, then refused because
`xcresulttool` added a derived SQLite index to the original result bundle. Every
original bundle file remained byte-identical. The single derived file was moved
to retained private evidence; a separately finalized review verified the restored
original bundle, screenshots, source and prepared products. No XCTest or physical
workload was repeated to obtain those images.

## Hosted checks

The earlier full modular run is retained:
[41297132805](https://github.com/p2pKit/P2pKit/actions/runs/41297132805).
Its stale iPhone roster check and Apple test compilation failures were fixed.
The same run's `macos-shared` component failed during shared platform tests:
command exit 1, Gradle Stop exit 0, known cleanup, no timeout. Public diagnostics
identify no failing task or assertion; its original encrypted evidence is retained.
That component is still unresolved and is not counted as passed.
The corrected source component passed at `d4b12f4e`:
[41298289841](https://github.com/p2pKit/P2pKit/actions/runs/41298289841).
Apple ARM and x64 checks at `ab350b6e` are in progress:
[41300124068](https://github.com/p2pKit/P2pKit/actions/runs/41300124068) and
[41300128988](https://github.com/p2pKit/P2pKit/actions/runs/41300128988).
This draft does not claim that every required component is green.

## Measurement limits and remaining scope

Smart Test measures each connected Client→Host path using the existing authenticated
connection. It creates zero independent Mac clients. A stable path result is not an
absolute Host capacity result. Default time/stage/concurrency/rate ceilings are
safety budgets; a reached ceiling is a lower bound, not a discovered maximum.
Missing or stale Host telemetry cannot certify Host resource safety. Workers drain
before results save; the application role connection remains until Stop.
Multi Clients adapt independently; non-aligned stable maxima must not be summed
into aggregate Host capacity. Independent connection pressure and a coordinated
aggregate Smart search remain outside these buttons.

Android temperature is a battery sensor, iOS thermal categories are coarse, and
Mac memory/thread counters are JVM heap/JVM threads. USB/external charging is not
battery-discharge evidence; unavailable native or current measurements are not
estimated.

| Physical Host | Capacity | Required measured steady | Completed in this campaign |
| --- | --- | --- | --- |
| Android | 128 | 1,800 seconds | 0 seconds |
| Android | 256 | 1,800 seconds | 0 seconds |
| iPhone | 128 | 1,800 seconds | 0 seconds |
| iPhone | 256 | 1,800 seconds | 0 seconds |

No per-capacity throughput, p95/p99, idle overhead or post-Stop resource-drain result
is asserted by these software checks. Source-matched physical independent cohorts,
255 Mac clients plus a phone, genuine socket slow consumers, long mixed faults,
full revocation/fairness coverage, reviewed unplugged discharge and the complete
application role matrix remain acceptance work. Existing manual results from an
older source are retained and are not relabeled as new-source evidence.
