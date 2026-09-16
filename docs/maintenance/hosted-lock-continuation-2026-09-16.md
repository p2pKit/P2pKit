# Hosted sample-build prerequisites — 16 September 2026

The owner now requests GitHub-only execution until the sample workflow works.
Local source/offline checks are allowed; local Gradle, SDK/dependency acquisition
and app/device builds remain held. This supersedes the earlier dated no-retry
instruction, not required admission, evidence, review or publication safeguards.
No physical-phone work or production publication is authorized.

## ARM postimage: diagnostic fixes exercised, writer still blocked

Genuine [run 35042663299/1](https://github.com/p2pKit/P2pKit/actions/runs/35042663299),
job `104625667542`, used source/base
`2cc7ab8e8361f9a8a948c83aa5324d26b320b813`, tree
`77489dff12ec6331f32f255350aa207003813d4a`, from
`2026-09-16T01:05:07Z` to `01:08:03Z`. **FAILURE**, controller `125`, candidate
`HOLD`. The earlier [35007680254 failure](hosted-lock-result-2026-09-15.md) stays
failed and is not overwritten by these distinct results.

Native ARM macOS 26.6.2 / Xcode 26.5 (`17F42`), installed JDK 17.0.20.1/21.0.12.1,
SDK 36/37.0 and available iOS 26.5/iPhone 17 inventory passed their setup portions.
The simulator remained Shutdown; inventory is not app execution. Actual commands:

| Executed scope | Result and boundary |
| --- | --- |
| `python3 -I -B -S scripts/tests/run-audit-command-test.py --expected-host macos-arm64 --evidence-dir <owned>/evidence/native-controls --fixture-parent <owned>/fixtures/native-tmp` | **93 PASS**, 108.432 s: 35 pure, 19 modeled, 39 real Darwin fixtures. Not library/Gradle tests. |
| JDK 17 `javac --release 8` for 60 current vendored Java sources, then `javac --release 17` for the maintained lifecycle fixture | Both exit 0 after the bounded hash-pinned SLF4J acquisition. |
| `JmdnsCloseLifecycleFixture control` | Exit 1, `host_not_announced`, 2 sends attempted/0 returned; original FAIL and rescue retained. Not eight-mode lifecycle acceptance. |
| Post-failure paired primitives | JDK: SEND/`NoRouteToHostException`/0 bytes. Python: valid report, SEND/`KERNEL_ACCEPTED`/42 bytes, closed/reaped. **Kernel acceptance is not delivery.** |

The real canonical Python argument now admits both primitives: the missing
[#440](https://github.com/p2pKit/P2pKit/issues/440) postimage caller gate is covered.
The separate resource process emitted 73 fast/30 network schema-2 RAW samples;
the real parent continued checking their freshness through the failed control.
That covers [#441](https://github.com/p2pKit/P2pKit/issues/441)'s positive native
producer/consumer path, not native fault injection or a per-check age transcript.
Prior exact-source offline negatives remain separately scoped evidence.

**Gradle never started:** `writer=null`, `stop=null`, #424 custody
`NOT_STARTED/NOT_APPLICABLE`; no wrapper stop was needed. All twelve locks and
verification XML match the source. Six stale JmDNS lock memberships still block
the sample builds. No generated ABI, Dokka, SBOM, APK/MSI/DMG/DEB or complete gate
result exists from this attempt. The Java/Python difference establishes no
socket-family, privacy, provider or OS cause; no global IPv4 workaround is adopted.

### Authenticated custody and independent result review

Artifact `10426485005` expires `2026-09-30T01:07:55Z`; its verified private copy
is retained. ZIP size 662,845 bytes; SHA-256
`7dcbec2dea86af619f27c21476c2d098110fc1b14451ed45538c48b8c5c74f63`.
Authenticated decryption returned `DECRYPTION_OKAY`/`GOODMDC`; all 1,714 archive
members and 5,867,138 file bytes were checked. All 32 command scopes and 39 final
native fixture retirements were inspected, with deliberate earlier failures
preserved. The retrieval's owned GPG agent retired; no private key/raw log is public.

Independent nonimplementing verdict: **APPROVE authentic failed-run custody and
bounded native postimages #440/#441; HOLD host/writer/samples/closure**. Report
SHA-256 `94de987eab6d3b691dd5d4f034fab34fdfb74b490375d6699682e693add5f65c`.
Private packet handles: `hosted-lock-run-35042663299-lu_onpvq` and
`review-arm-postimage-35042663299-wOWMqnIj`, under the retained evidence root.
NORMAL sampled pressure, zero swap growth and 6,065,067 sampled inbound-growth
bytes are whole-host observations, not dependency totals or hard quotas.

## Meaningfully different next host: closed Intel profile

The existing [isolated writer](../../scripts/run-hosted-lock-candidate.py) now
also supports `dependency-lock-candidate-x64` in the same dedicated job. The
ordinary sample matrix and publisher do not run for either writer operation.
ARM pins remain unchanged. Intel requires genuine `macos-15-intel`, native
`X64`/`macos-x64`, macOS 15, Xcode 26.3 (`17C529`), native JDK 17/21 and the
applicable available **iOS 26.2** runtime with an originally Shutdown iPhone 17.
It is not Rosetta, a root workaround or an assertion that inventory is admission.

The [immutable official image inventory](https://github.com/actions/runner-images/blob/07cc2190cd4d100d9f69478219017720c02c40f6/images/macos/macos-15-Readme.md)
lists that combination. Actual tool/runtime/native/resource/multicast admission
must still succeed before the complete supported writer. The historical Intel
runtime timeout remains a failure; a new host/profile needs its own result.

Selected operation is bound into dispatch, context, seal and recovery equality.
The resource helper must match that native role. Full writer/strict verification,
credential isolation, non-cancelling shared queue, deadlines, ownership, failure
retention and encrypted-only export remain unchanged. No lock is hand-edited or
promoted from a failed/partial writer. The dispatch recipe in the
[writer contract](hosted-lock-candidate-2026-09-15.md#encrypted-artifact-and-safe-resumption)
is reused with `operation=dependency-lock-candidate-x64`, and **the new reviewed
full SHA for both `expected_sha` and `reviewed_base`** plus its exact tree.

Actually executed offline on installed Python 3.9.6/Ruby 2.6.10, before any Intel
dispatch: controller 111 tests, resource 28 tests, workflow policy 289, queue
policy 261, Mac policy 63, Windows policy 70 and sample policy 76 controls all
passed; `git diff --check` passed. Commands are respectively
`python3 -I -B -S scripts/tests/run-hosted-lock-candidate-test.py`,
`python3 -I -B -S scripts/tests/hosted-lock-resources-test.py`, and
`ruby scripts/tests/check-{hosted-lock-candidate,heavy-job-queue,mac-host-admission,windows-directory-control,sample-app-workflow}-policy-test.rb`
(one invocation per Ruby file). These mock native/network children; they are
not hosted Intel, Gradle or sample evidence. Logs are retained in
`hosted-intel-profile-controls-rv1tvhh0`; fixture-authoring failures are separate
from the corrected failure-first ARM-only preimage. These ran under private
evidence umask 077; the independently confirmed default-umask fixture race
[#442](https://github.com/p2pKit/P2pKit/issues/442) is a separate repair, not fixed
by this profile or by changing the test environment. Added pure controls cover
cross-profile seal/recovery rejection and selected-simulator-only retirement.
Source review/dispatch and any later generated candidate require their own exact
bindings.

## Actual Intel result: same admission failure, not accepted locks

[Run 35044849839/1](https://github.com/p2pKit/P2pKit/actions/runs/35044849839),
job `104632364405`, executed `dependency-lock-candidate-x64` at source/base
`50b7e6b50b419639054487c2431eb23f05659776`, tree
`68344d0a8561a62f893a1108855854c6c1f414a6`, completing at
`2026-09-16T01:41:26Z`. **FAILURE/HOLD**, controller 125. The source includes
the separately reviewed, test-only [#442](https://github.com/p2pKit/P2pKit/issues/442)
exclusive-private stop-marker correction; production resource logic is unchanged.

Real Intel macOS 15.7.9, Xcode 26.3/17C529 and native JDK 17.0.20.1/21.0.12.1
passed their setup checks. The applicable iOS 26.2 runtime and selected Shutdown
iPhone 17 were inventoried; no simulator boot/app execution occurred. The same
native-control command as above, with `--expected-host macos-x64`, passed **93
tests in 135.858 s**. Both current vendored-source/fixture `javac` commands passed.
`JmdnsCloseLifecycleFixture control` then failed: `host_not_announced`, two send
calls/zero returns, original exit 1 and rescue preserved. Other modes were not run
in this attempt; earlier ordinary-Mac eight-mode evidence retains its separate scope.

The default JDK primitive again failed SEND/`NoRouteToHostException`/0 bytes;
canonical Python reported SEND/`KERNEL_ACCEPTED`/42 bytes, closed/reaped.
This does not establish delivery or a network, privacy, provider or family cause.
The resource observer emitted 90 fast/37 network shared-RAW samples, consumed by
the real controller with unchanged freshness limits; all 217 original resource
queries were independently inspected. No native fault injection is claimed.

**Writer/stop null; no Gradle, #424 suites/custody or sample build started.** All
twelve locks and verification XML remain byte-identical; six obsolete memberships
still block compilation. All 32 command scopes and 39 final native fixture
retirements were verified; selected simulator remained Shutdown. Artifact
`10426309873` expires `2026-09-30T01:41:20Z`; its 677,980-byte ZIP has SHA-256
`f50e0e452d41e9cdc88875254101f3db093bfa3fad6a501618fdaf6e82a5bf83`.
Authenticated decryption and all 1,714 archive members/6,165,729 file bytes were
checked, with the retrieval's owned GPG agent retired. Private packet:
`hosted-lock-run-35044849839-73yzg_5m`.

Independent verdict **APPROVE_SCOPED_INTEL_POSTIMAGE_AND_FAILED_RUN_CUSTODY**;
report SHA-256 `945c8386da5e53374e47d7a19af21c609efd6efea0e7fa4109d9718625b48015`.
It does not approve the failed host/writer, apps, formal PR or closure. Separate
review-only parser errors are preserved in the private report; they are not
hosted failures. No unchanged full writer/sample retry is justified by this result.

## Next diagnostic: explicit IPv4 in the same JVM, not a product workaround

The two real hosts justify one narrower comparison, rather than speculative
global JVM flags. The controller now opts into
`-Dp2pkit.audit.jmdnsIpv4ChannelPrimitive=true` inside the existing guarded,
post-failure Mac/control/IPv4-NoRoute path. The private fixture helper opens
`DatagramChannel.open(StandardProtocolFamily.INET)` in the **same JVM**. It
sets/verifies both reuse options before explicit IPv4 wildcard binding, matches
the captured interface/group/port, validates membership/TTL/loopback, and sends
the same fixed 42-byte diagnostic once in nonblocking mode. Zero/short sends fail.
It closes its channel in `finally`, observes membership invalidation, rechecks
interface/interruption between probes and stops the sequence on uncertain cleanup.
Only exception classes and fixed-label observations are logged, never addresses.

Original readiness/FAIL/rescue, 45-second outer command, full-writer admission,
Python bounds, production socket behavior and IPv6 support are unchanged. A
successful explicit-INET send would establish only a same-process **socket/API-path
difference**, not family causation, packet delivery or a production repair. If
both Java paths reach SEND and fail with `NoRouteToHostException` while Python
accepts 42 bytes, explicit INET alone did not suffice for this diagnostic. Setup
failure, zero send, timeout or uncertain retirement leave the comparison
inconclusive. Neither outcome establishes global JVM-flag/product behavior or
an OS/privacy explanation.

Actually executed offline: `python3 -I -B -S
scripts/tests/run-hosted-lock-candidate-test.py` — **116 PASS**, 1.016 s. The
same final focused tests first produced two intended absent-opt-in failures;
the existing rejection of original FAIL, stray PASS and rescue remained intact.
Every compiler/network/native child is mocked in this suite. Python AST and
whitespace passed. Raw logs/patch/source binding are retained in
`inet-diagnostic-offline-qcqcz34_`. **New Java compilation/native send/cleanup
are not yet executed** at this source checkpoint; no Mac build or dependency
download was performed. Independent exact-diff approval must precede a single
source-bound hosted invocation; diagnostic success cannot admit the writer.

## Delivery acceptance still required

Refs [#425](https://github.com/p2pKit/P2pKit/issues/425),
[#437](https://github.com/p2pKit/P2pKit/issues/437),
[#439](https://github.com/p2pKit/P2pKit/issues/439),
[#410](https://github.com/p2pKit/P2pKit/issues/410). After a genuinely complete
writer: independently review all twelve locks/XML, generated producer/SBOM and
original test custody, then current applicable scan/submission and sample builds.
The Windows allocation repair remains preserved but not Windows-retested.
Ordinary CI/Desktop still needs the documented
[#424 private-custody adapter](../testing/local.md#subprocess-transcript-custody-on-failure).
The main publisher still requires normal merge, required checks and an independent
formal exact-head PR approval; subagent approval is not that approval.

No issue closure or historical 234-row credit is added: **206/234** repair
approvals remain historical. Kotlin advisory GHSA-r937-wjx7-w2jp remains
**EXCEPTED_NOT_FIXED**, expiry **2026-10-31**; no fresh scan/remediation is claimed.
Whole audit/release remains **NOT_READY**. Physical-phone criteria stay deferred.
