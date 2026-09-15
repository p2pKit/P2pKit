# Hosted lock attempt: failed before Gradle — 15 September 2026

**The authorized hosted attempt finished, and its encrypted failure evidence was
retrieved and independently inspected. No lock writer or sample build ran.**
Do not retry the unchanged matrix or treat successful evidence upload as a
successful build. Another hosted attempt is not currently authorized.

This is the execution result for the
[reviewed hosted controller](hosted-lock-candidate-2026-09-15.md), not a replacement
for its earlier source/offline checkpoint or for historical local failures.

## Immutable run and source

| Identity | Actual value |
| --- | --- |
| Run / attempt | [35007680254 / 1](https://github.com/p2pKit/P2pKit/actions/runs/35007680254) |
| Workflow / job | `desktop-cross-host.yml` / `dependency-lock-candidate`, job `104511471875` |
| Event | Genuine `workflow_dispatch`; no hosted identity was emulated locally |
| Source | [`41758f3912f2c76c3a68be4c1e53286356cf16af`](https://github.com/p2pKit/P2pKit/commit/41758f3912f2c76c3a68be4c1e53286356cf16af) |
| Git tree | `5808aebb1b04880d5f738b2ce57f4a971160b4f2` |
| UTC interval | `2026-09-15T18:28:18Z`–`2026-09-15T18:30:58Z` |
| Conclusion | **FAILURE**; controller exit `125`, candidate `HOLD`, accepted `false` |

The native ARM GitHub host reported macOS 26.6.2, Xcode 26.5 (`17F42`), Temurin
JDK 17.0.20.1 / 21.0.12.1, and 7 GiB physical RAM. Installed SDK 36 / 37.0,
first-launch, actual iOS 26.5 runtime inventory and an originally Shutdown iPhone
17 simulator passed setup admission. Inventory is not simulator application or
physical-phone execution. No phone, emulator, simulator app or transfer ran.

## Actually executed, not planned checks

| Scope | Result / limitation |
| --- | --- |
| Native executor controls | **93/93 PASS**, 100.260 s: **35 pure + 19 modeled + 39 real Darwin fixture cases**. Not 93 native cases or a Gradle/library gate. |
| Narrow JmDNS prerequisites | Hash-pinned, at-most-1-MiB SLF4J acquisition passed. JDK 17's `javac --release 8` compiled the 60 vendored sources; `javac --release 17` compiled the lifecycle fixture. Both passed. |
| `JmdnsCloseLifecycleFixture control` | **FAIL**, exit 1, approximately 10.7 s after launch within the unchanged 45-second bound. |
| Full maintained writer / Gradle stop | **NOT_STARTED**: `writer=null`, `stop=null`; a real Gradle stop was neither needed nor claimed. |
| #424 custody / real library tests | `NOT_STARTED` / `NOT_APPLICABLE`; the initializer, 9 CLI / 23 diagnostics methods and 2 / 4 exports were not executed. |
| Candidate locks / metadata | All twelve before/after lockfiles and verification XML retained and identical to the run source; empty source diff. Six stale JmDNS memberships remain. |
| ABI / Dokka / SBOM / samples / release gate | Not executed by this attempt; no generated candidate, APK, MSI, DMG or DEB was produced. |

The actual native-control argv, with only owned absolute roots represented by
`$ROOT` and `$STATE`, was:

```sh
/Applications/Xcode_26.5.app/Contents/Developer/usr/bin/python3 -I -B -S \
  "$ROOT/scripts/tests/run-audit-command-test.py" --expected-host macos-arm64 \
  --evidence-dir "$STATE/evidence/native-controls" \
  --fixture-parent "$STATE/fixtures/native-tmp"
```

Exact compiler/control argv, private streams, source bindings and exits remain in
the encrypted original packet. The executor fixtures use substitute wrappers;
they do not silently execute a real dependency writer.

### Decisive failure and separate diagnostic omission

The first IPv4 mDNS send threw `java.net.NoRouteToHostException`. The fixture
recorded **2 send calls, 0 successful returns**, no announcement, and
`FAIL mode=control` / `AssertionError: host_not_announced`. Its explicit rescue
finished while preserving the original failure. This is not natural lifecycle
success or packet-delivery evidence. Post-failure route observations did not
establish a provider, privacy, OS or network-policy root cause.

Both additional JDK/Python primitive diagnostics were then skipped with
`primitivePair attempted=false reason=CANONICAL_INTERPRETER_REQUIRED`.
That confirmed a separate caller/input-contract defect, now tracked as
[#440](https://github.com/p2pKit/P2pKit/issues/440). It does not explain the earlier
send exception. Closed #420's UDP reuse repair is not reopened or reimplemented.

## Evidence custody and retirement

The always-run seal, public validation and encrypted upload succeeded despite
the failed operation. Artifact `10411544059` contains only ciphertext and a
minimal manifest, bound to the exact source/run/attempt above:

- Downloaded ZIP: **655,284 bytes**; SHA-256
  `384f380d8d8c605c8b6c9db0e653bcef026ae29f0c17130ee0da1cac7742e4e9`.
- Original hosted expiry: **2026-09-29T18:30:54Z**. A verified private local copy
  is retained; future continuation must not depend on an expired Actions URL.
- Private decryption returned `DECRYPTION_OKAY` / `GOODMDC`. Archive allowlist,
  manifest/ciphertext hashes and all extracted bytes were inspected: 1,714
  members, comprising 1,321 files and 393 directories, 5,774,909 file bytes.
- All **32** original command ownership/baseline records and terminal quiescence
  observations were checked: no owned survivors, unresolved discovery/drain
  errors or truncated streams. All **39** real fixture cases have final scoped
  cleanup; three deliberately injected earlier failures remain recorded.
- The selected simulator remained Shutdown. No blanket simulator shutdown or
  another user's process cleanup occurred. The retrieval's owned GPG agent was
  stopped and its sockets were absent; no key/passphrase/raw evidence was uploaded.

The helper recorded 67 fast / 27 network samples: NORMAL pressure, zero swap
growth, minimum 102,352,281,600 bytes free disk, and 16,291,135 bytes sampled
whole-host inbound growth. That is **not a dependency-download byte total or a
hard quota**. Same-helper sample gaps remain valid. Its parent's cross-process
`time.monotonic()` freshness subtraction on Python 3.9 was not qualified; see
[#441](https://github.com/p2pKit/P2pKit/issues/441). This did not cause the recorded
multicast-control failure and does not invalidate the distinct within-helper
resource observations.

Independent original-result verdict: **accept authentic FAILED-run custody and
scoped retirement only**. Report SHA-256:
`699ce308929a8d222881d0cacdbc83b98bcc3ccdf7bcdcc2955a8c68e5ebcc78`.
Private packet handles are `hosted-lock-run-35007680254-6ztmncjb` and
`review-hosted-lock-run-35007680254-y7bhei0z`, under the owner's retained evidence
root. Transfer only selected necessary evidence privately; never publish the key
or raw packet. The independent review is not formal PR approval.

## Subsequent corrections are not a new hosted result

- **#440:** [`39085217a0183b472ba9f57e14259d1a43c7330f`](https://github.com/p2pKit/P2pKit/commit/39085217a0183b472ba9f57e14259d1a43c7330f),
  tree `a9830f65c0284e79ab34758afc1fd72c827179d7`, resolves the running Python
  interpreter strictly and requires an absolute regular executable before
  multicast acquisition. Java admission, networking, timeouts and cleanup are
  unchanged. Eight real-caller pure regressions produced seven expected preimage
  failures; all **90** postimage controller tests passed independently.
  Source/pure review SHA-256:
  `cdb1f79fc27573fad2f1f188f13de45f0c330e45b2706f3c4a4622c09c6c6346`.
  Actual postimage Java/Python diagnostic admission remains unexecuted.
- **#441:** [`e870057163421e73b59f508328e5802db339416e`](https://github.com/p2pKit/P2pKit/commit/e870057163421e73b59f508328e5802db339416e),
  tree `61987915ab4967653da4e83756569f97f1ff22ac`, stamps schema-2 samples with
  explicit shared RAW nanoseconds. The real controller rejects wrong schemas,
  domains, malformed/future/stale times; 5/8-second limits and failure-safe
  stop/drains are unchanged. Independent full controller **101 PASS** and resource
  **26 PASS**, using fake native clocks/tools; source/pure review SHA-256:
  `2ef2043f75291e45d558da64f745fac3723d7d305f469bd023bf5f5d81aae41d`.
  Eleven selected controller methods produced 23 failing preimage assertions
  and one old-clock exception; seven producer methods produced ten failing
  assertions and two missing-field errors. These are assertion counts, not extra
  test methods. Earlier test-authoring failures and their corrections remain
  retained separately; they are not native product failures. A local two-process
  Python 3.9.6 diagnosis confirmed different local monotonic epochs and a shared
  RAW interval, but genuine postimage producer/consumer acceptance is still
  unexecuted. Do not reinterpret this run's schema-1 timestamps as RAW evidence.

The later offline controls use installed Python with `-I -B -S`, synthetic
filesystem fixtures and mocked native/child/network boundaries. They start no
Gradle, JVM, SDK download, emulator or hosted job. Final-source tests cannot turn
run 35007680254 into a postimage pass. Unchanged source-bound policy/crypto results
may be reused for their original scope; changed executable inputs need their own
review/tests. Actionlint 1.7.12's four unsupported `queue` diagnostics remain an
**exit-1 limitation**, not a lint pass. No full release monolith was rerun.

## Remaining work and safe continuation

1. **Host admission:** this cloud Mac could not send the required multicast.
   A genuinely functioning multicast-capable Mac/runner or an evidenced correction
   to that environment is needed before the full writer. The local writer and
   further hosted attempts remain held; no deadline/privacy/readiness bypass or
   speculative unchanged retry is authorized.
2. **#425 / strict locks:** complete the maintained writer, then independently
   inspect all twelve locks, checksums, producer/SBOM and provenance, and perform
   applicable current scan/submission. No handwritten or partial lock promotion.
3. **#424 / #410:** obtain actual final test-JVM custody and packaged JmDNS/JUnit,
   consumer and platform acceptance. The earlier ordinary-Mac R410 eight-mode
   direct-source success remains valid for its own scope; this different cloud
   failure neither erases it nor supplies packaged/full-gate proof.
4. **#439 / #437:** genuine corrected Windows setup and the Android/Linux/macOS/
   Windows sample matrix remain unexecuted. Keep Windows fix `614e534` and the
   existing sample/publisher source. The earlier sample run 34978847218 remains
   failed/cancelled with zero artifacts. No downloadable samples are claimed.
5. **Reviewed delivery:** complete required CI and independent formal exact-head
   PR review, normal main merge/preservation, then the authorized development
   prerelease workflow. No PR was opened because that would start held checks.
   Strict `complete-gate`, `review`, `scan / osv-scan` and `osv-scanner` are not
   bypassed. No merge, release, issue closure or branch deletion occurred here.

At the **2026-09-15T19:04:47Z** live refresh, **63 issues were open**, separately
from unchanged historical **206/234** repair approvals. The continuation branch
is `work/nonphysical-integration-20260915-022112`; main remains
`3bc76f956f8f47447b51a62474fc878b9c43173c`, tree
`2a1105fde1d1ac299448489501e29d7a0d4a407a`. Keep the six retained dependency
proposals and all necessary blocked-work evidence.

Kotlin 2.4.10's GHSA-r937-wjx7-w2jp / CVE-2026-53914 remains
**EXCEPTED_NOT_FIXED**, exception expiry **2026-10-31**; no new scan, qualified
upgrade or remediation is claimed. Physical-phone work stays deferred; production
publication remains unauthorized. The whole audit/release remains **NOT_READY**.
