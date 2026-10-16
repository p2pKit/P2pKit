# October 3: Mac-only closeout checkpoint

**Verdict: NOT_READY.** This is a reviewed engineering checkpoint, not a
merge-ready or release-qualified branch. `main` and the old checkout are not
changed. Mac27/Xcode27 remains the officially accepted ARM environment; neither
Mac26 nor Xcode26.5 is a prerequisite.

The implementation candidate is `dcc065205983bb2a7f6095970956bef28200e1f9`, tree
`c0a079c6ccac2e5436995f42ec735f50138041a2`. The continuation started from
`b3f9d7f89a86c11d5275f2530ded1c65110894b0`. The later CI/verification/test and
documentation changes below do not relabel binaries or results as built
from their own commit.

## Completed local engineering

| Change / source | Executed evidence and limit of the claim |
| --- | --- |
| Exact CLI continuation (`6b869d05`, `88e4250a`) | Selection, suffix, authorization and results are bound together; omitted cases are never inherited passes. The original case bodies, assertions and deadlines remain. |
| Darwin child limits (`88e4250a`) | Read-only `kern.maxprocperuid` observation explains the requested/readback mismatch. Only the child requests the stricter limit pair. The native continuation passed all three admission-pressure cases. |
| Identity-bound thread observations (`81bf03d2`) | Retained actual JVM dumps at 4.5/6.5 seconds and a separate JFR recording show failed native sends followed by recovery/close wait stacking. Observation is not a successful `adv off`. |
| Goodbye-budget candidate (`dcc06520`) | One original five-second protocol allowance is shared across recovery, service and host cancellation. Real resource ownership/drain proofs and the SDK's six-second deadline remain. Six socket-free JUnit tests passed; all 60 vendor Java sources compiled to 134 Java8 classes. **Real-resource validation remains blocked.** |
| Regression/provenance support (`26b16ee0`, `dcc06520`) | Two new real-resource modes; hosted consumers require ten natural child successes, never rescue. Patch replay reconstructs all 59 original relocated sources and all 60 final sources. Prior patch/upstream hashes remain unchanged. |
| Lock-writer repair (`0ea9e488`, `3a0780a9`) | Only the complete sanctioned writer may retire absent Dokka v1 lock graphs through Gradle's empty locked configurations. Existing configurations are rejected before task execution. The deprecated visibility API was removed. No lockfile was hand-edited. |
| Deferred diagnostic's lock inventory (post-`dcc06520` review) | Corrected stale twelve-lock admission/finalization to require all fourteen current locks. Six new offline tests execute the actual inline guards; all six and the existing workflow-allocation control passed. The pre-fix three failures/two errors are retained. No Intel job was executed and no runtime deadline, route, permission or interface changed. |
| Dependency-verifier scope (post-`dcc06520` review) | The old whole-file count falsely rejected the new independent locking rule and accepted commented-out root locking. The verifier now requires the direct, mandatory root buildscript rule. Thirteen scoped controls and the complete dependency-policy script passed, including its 7 parser, 32 artifact-locator and 15 isolated temporary-directory tests. The first implementation's property-reference false rejection is preserved. No metadata, dependency version, lock or trust setting changed. |

Focused offline results retained at their tested sources: **48 CLI-policy,
44 controller, 21 authorization, 23 hosted-consumer, 23 SBOM-parser controls**,
and **67 publication ZIP/metadata fixtures** passed. These are different scoped
suites, not additional RPC scenarios or an overall qualification denominator.

### Final non-network validation

The frozen `dcc06520` session is `aa431f3a0f8f4a4da95ca66ce878d546`, evidence
parent `P2pKit-mac-nonnetwork-final-20261003-b2ku6k6l`. It **passed** on
Mac27.0/Xcode27.0 (`27A266a`), finishing October3 at 09:00:48 UTC:

| Executed check | Result / invocation |
| --- | --- |
| Fresh ownership admission | 129 controls PASS in 131.455s; `58a83d28d45345b28622e1ad97d3f2c1`. |
| Focused `:p2p-transport-lan:jvmTest` selecting only `JmdnsGoodbyeBudgetTest`, plus `:p2p-transport-lan:jvmJar` | All six methods PASS, no failures/errors/skips; 14 tasks, 4m28s; `9d2538bc5e52403b97961a360afb875e`. |
| All five library `dokkaGeneratePublicationHtml` tasks | PASS, 85 tasks, 7m13s; `910b9abd2fce4f0780351218aa3e9b08`. |
| `cyclonedxBom` then complete `scripts/check-sbom.sh` | PASS, 10 generation tasks, 6m28s; 88 components, matching JSON/XML and actual private-producer hash; `ad0bf9d3ff4f479f96f1ae9455ad04b9`, `372975709cf74165b9ed98290acad3c6`. |
| `scripts/tests/check-lock-write-policy-test.sh` | PASS; six expected policy rejections plus the authorized dry-run, with unchanged locks; `e0aa2677747043a1b3e728da771838b2`. This does not prove positive full-writer retirement. |

JVM, Dokka and SBOM generation retained strict verification,
`--warning-mode=fail`, disabled build/configuration caches and their original
limits. Lock-policy controls used the maintained script's own arguments.
Independent review matched the exact six JUnit methods, all five Dokka outputs,
the 134 Java8 private classes and their
byte-identical inclusion in the JVM JAR. All **12 outer plus seven nested
finalizers** passed; all **453** recorded process lifetimes were independently
absent. All 14 locks and verification metadata remain byte-identical to `b3f9d7f8`.

Result SHA-256:
`6f0fe71a33493d14798c1a9ce44c28f64a91138baa1888bbe6def2ce18100a05`.
Independent review (`07-independent-review.json`) SHA-256:
`a30906998b103ab6e9f3090e0fdb3bd25d58ffbb3cfcf646d9aeace3c508f585`.
The two earlier read-only reviewer schema-assumption failures are retained;
correcting them did not rerun tests or modify evidence.

This session does not select network fixtures, CLI cases, full `check`, simulator,
Swift/phone/clock, Intel or ART. Its fresh 129 controls are ownership admission,
not 129 new RPC tests.

## Multicast: observed failure, unproven root cause

The original host-announcement control **passed once** at `6b869d05`, job
`e5b5bbbc4851400781d02bc43f440aa0`, without fixture rescue. All 11 enclosing
finalizers passed; 366 recorded process lifetimes were independently absent.
Result SHA-256:
`df85565021ba219fe027224762885d1bd4c9e689c4c73e025e8ec0c539f35398`.
This did not establish physical LAN delivery or explain earlier failures.

Subsequent failures remain failures:

- The `81bf03d2` JFR observation (job `d91abeeb53a947c097edb1c5800c6bd8`)
  recorded two `NoRouteToHostException` events at the actual native
  `DatagramChannelImpl.send0` boundary, followed by incomplete cleanup errors.
  Recording SHA-256:
  `f70adfec171a6dc870e76ddfb4635d805448228c9e7d6f9a9d6ec552fef739ee`.
- Both new regression modes first ran on the pre-fix `26b16ee0` source, job
  `4ac92a96c9fe4cb5b4f7b9cf3cf85f93`. They failed the **original 10-second host
  readiness check before either new cleanup assertion**. Rescue remains FAIL.
  All 11 finalizers passed; 424 recorded lifetimes were absent. Result SHA-256:
  `bc0dc6676105fdaa6840c60b008c56b50ab6c6acfca892a3ab830fc89716b291`.
- The third full dependency writer independently failed the original control
  with the same Java send exception. Its failure is not repaired by the later
  socket-free arithmetic tests.

Local Network permission is owner-confirmed enabled. Earlier gated Java/Python
process-attribution checks identified the responsible `org.python.python`
identity and matching allow preferences. Those observations, matching scoped
routes/interfaces, unrelated Bonjour logs and Python's byte counter are **not**
a per-socket kernel-policy decision or packet-egress proof. The available
capture/log attempts supplied no probe-correlated egress/drop record. SIP remains
enabled; unavailable DTrace providers were not enabled by weakening it.

**Exact missing evidence:** a supported Apple/network-extension diagnostic that
correlates the failing process lifetime/audit identity and socket with its
effective NECP/routing/filter decision and errno65, plus probe-specific
interface-egress/drop evidence. There is no verified working command for obtaining
that missing evidence under the present restrictions. Do not guess a router,
permission or interface root cause, reset permissions, alter routes, force an
interface, or retry blindly. Receiver/AP evidence for physical delivery is a
separate deferred campaign; an iPhone merely sharing Wi-Fi is not proof.

## Exact CLI accounting

Historical non-option progress: **2 PASS** at `6b869d05` (command contract,
including `adv off`, and three-peer contract), then **37 PASS** at `88e4250a`.
The latter job `8bc07eaa59ba4824a028d0977de56286` failed at
`transfer-sender-kill-1`; all nine finalizers passed and 538 recorded lifetimes
were absent. The `81bf03d2` suffix added **zero** passes before another startup
failure; its nine finalizers passed and 405 recorded lifetimes were absent.

These **17 cases never completed**:

```text
transfer-sender-kill-1
handshake-term-2       handshake-kill-2       handshake-eof-2
handshake-stop-cont-2  handshake-hup-2
idle-term-2            idle-kill-2            idle-eof-2
idle-stop-cont-2       idle-hup-2
transfer-term-2        transfer-kill-2        transfer-eof-2
transfer-stop-cont-2   transfer-hup-2         transfer-sender-kill-2
```

Thus all original 56 incomplete cases are accounted for: 39 historical passes
plus these 17. **The product change in `dcc06520` requires all 56 non-option
cases to be requalified at the new source**, not just the final suffix. The
29 previously passed early-exit option cases are unaffected and are not reopened.
Use the [remaining-only plan](../validation/mac-cli-process-controls.md), without
`--cli-first-case`, only after the narrow prerequisite passes. Do not claim
historical 68/85 case coverage as current-source or full RPC/LAN completion.

## Dependency remediation: eight advisories still open

All three attempts used the complete maintained writer; none produced an
importable, fully verified security update:

| Writer job | Actual outcome |
| --- | --- |
| `8c5e0284b32f4a44b5dff3f094de000a` | Full 360-task build/check/five-Dokka/SBOM execution passed, including the original eight lifecycle modes. Independent review verified 15 new candidate artifacts. Post-check **failed 12 stale vulnerable rows** in obsolete Dokka configurations. Ten original plus seven mutable finalizers passed; 744 lifetimes absent. |
| `951d0ed7b7a842dd84f1c90b999c9d61` | Writer failed when its daemon disappeared during native linking; the evidence does not prove OOM. ENOSPC then prevented the original stop log; stop -15 remains **FAIL**. Later same-home stops/drain passed with 539 lifetimes absent, without rewriting that failure. |
| `735f58780c9b4b53a070fc7ee8f88fa6` | Writer ran 351 tasks, including all five Dokka tasks and SBOM generation, then **failed original JmDNS host announcement**. Final lock-retirement and maintained postwriter artifact-review steps were not reached. Ten original plus five mutable finalizers passed; 559 lifetimes absent; owned simulator retired. |

All 14 before/after lockfiles, raw failures, resolved candidate bytes and reports
remain private. **No partial floors, locks or verification metadata were imported.**
The third writer result SHA-256 is
`d9ed3de06ba441f801430a1834c8be6d6d5bb2ae259b201c0874ef1f88bead18`.

A fresh read-only OSV API inventory at `dcc06520` queried **745 unique Maven
coordinates** from all 14 tracked locks (12 populated) and the admitted upstream
inventory. It found **eight distinct unwaived advisory IDs**:

| Dependency | Advisory IDs still affecting current locks |
| --- | --- |
| Jackson databind | `GHSA-gx83-3vf8-gh7j`, `GHSA-q4xh-88c3-wmh7`, `GHSA-wjgm-6hv5-3cvf`, **`GHSA-cxp5-3px4-pw24`, `GHSA-wv8q-qhhj-9h54`** |
| Jackson core | **`GHSA-7hhh-6rmp-j9qf`, `GHSA-p6pp-m3f8-5c89`** |
| FreeMarker | `GHSA-27j2-h3m2-8237` |

Bold IDs were additional findings beyond the four originally tracked. Their
reviewed ranges also affect the old proposed Jackson **2.22.2**. The revised
candidate is **Jackson 2.22.3 / FreeMarker 2.3.35**. Direct API queries returned
no advisories for those three candidate package/version coordinates at query time.
Both Jackson core/databind 2.22.3 POMs and JARs passed independent SHA-256 sidecar
and detached-signature review, pinned to publisher
`28118C070CB22A0175A2E8D43D12CA2AC19F3181`. Isolated GPG shutdown and temporary-path
removal passed. No downloaded JAR was executed or installed by that review.

This is **not** a complete newly resolved artifact review, OSV-scanner/SARIF
execution, exploit test, or completed remediation. The old 2.22.2 proposal and
all writer failures are preserved. The revised proposal remains private and
apply-checked only. The existing Kotlin exception through October31 is unchanged.

## Remaining gates and ownership

1. **Mac host-side evidence/fix — BLOCKED:** obtain the correlated OS/socket
   evidence described above without weakening protections. Any supported local
   product/adapter fix remains agent-owned; no proven router fix is available.
2. **Current-source native/CLI — BLOCKED:** after that fix, one original
   head-bound diagnostic must pass host announcement and sends with no rescue
   and independently verified cleanup. Keep the 10-second readiness/45-second
   child limits. Then validate all ten JmDNS modes and all 56 affected CLI cases,
   preserving the SDK 6000ms and original harness limits. Fix actual failures.
3. **Atomic dependency update — BLOCKED, agent-owned:** use the maintained writer
   with the newly reviewed targets; complete all required check/Dokka/SBOM work,
   Gradle-generated retirement, all 14 lockfiles and independent verification of
   every newly resolved artifact. No task exclusion, hand-edited lock or trust
   weakening. The required real-resource multicast control currently prevents
   completion.
4. **Final merge-ready gate — BLOCKED:** after both lanes pass, freeze the full
   resulting tree, perform affected strict checks, review all changes, commit and
   push the feature branch. A pushed blocked checkpoint does not satisfy this.

**Deferred by owner decision:** native Intel qualification and Android ART
API37/API24/API25 on a legitimate KVM runner. Mac cross-compilation or host JVM
tests do not replace them. No unavailable runner was reprobed.

**Separate device/infrastructure campaigns:** physical iPhone USB/signing/trust,
resource/capacity/interoperability and controlled physical LAN/multi-OS campaigns
remain open under the [device handoff](device-testing-handoff.md). They do not
absorb the agent-owned CLI, dependency or final-review work above.

Completed ARM Swift, lifecycle/cancellation, iPhone simulator and the requested
125-second clock/memory gate remain closed at their
[recorded sources](mac27-continuation-status.md). No overall percentage is
claimed by adding these overlapping tests.

## Evidence retention

Local evidence root: `P2pKit-mac-local-closeout-20261003-0gxjgdak` (`E` below),
with append-only continuation journal outside both checkouts. Important reviews:

- `E/52-*`, `63-*`, `72-*`, `75-*`: CLI/native failure and independent cleanup.
- `E/78-*`, `79-*`, `80-*`: six socket-free tests, patch replay and complete
  cleanup-candidate source review; not real-resource passes.
- `E/82-cli-source-transition-ledger.json`: all 56 non-option cases, original
  source/results and the changed-product requalification requirement.
- `E/84-live-osv-current/result.json`, SHA-256
  `1c7fef1be27e1b4becbe4159d647705ad898145a0fc0e945b942ba27f99f2f69`.
- `E/86-candidate-signature-review.json`, SHA-256
  `dd4b48e8257a49c25ec9eb28f8b87b89b75bc6e2204e4013e1f2b09b2db38ba3`.
- `E/89-startup-lock-inventory-red.*`, `90-startup-lock-inventory-green.log`:
  failure-first offline coverage for the corrected workflow lock inventory.
- `E/91-final-repository-checks.*`: source-bound repository checks, including the
  original verifier failure. `92-*`/`93-*` preserve the scoped-guard failures;
  `94-buildscript-lock-scope-green.log` and `95-focused-repository-recheck.json`
  record the completed policy suite, corrected verifier and action-pin check.
- `P2pKit-mac-dependency-writer-complete-20261003-07wfd5r3/09-*`: third writer's
  independent failed-run review and retained partial outputs. Review SHA-256
  `b346e1b3d6c054066cf47d126dfa40d28b2a98283583f6f052aaf0bd4c656439`.
- `P2pKit-mac-nonnetwork-final-20261003-b2ku6k6l/07-*`: final scoped non-network
  review, artifacts and cleanup, as detailed above. Its `08-*` retirement record
  proves only the two owned Gradle/Konan caches were removed: 3,400,397,299 regular
  file bytes, with 12,926 protected source/evidence entries unchanged and all
  453 recorded lifetimes rechecked absent.

Only finalized, exactly owned caches were retired after protecting source, logs,
reports and artifact hashes. Original failures are never overwritten. Native
sessions are consumed, not reusable bootstrap/configuration requests. Raw private
payloads, device identities, signing material and generated artifacts are not
committed to the repository.
