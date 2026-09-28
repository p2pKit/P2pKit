# RPC implementation checkpoint — 2026-09-27–28

## Scope and baseline

The approved [Optional LAN RPC plan](../../RPC_MODULE_PLAN.md) is implemented
in source. **JVM/Android tests, scoped ARM simulator tests, strict core/LAN/RPC
Dokka and Apple framework/Swift API compilation passed. Supplemental Mac VPS work
also passed all eight direct-source JmDNS modes and generated/reviewed Native ABI
baselines. A long iOS-runtime security scan blocked new script launches on that
VPS; after it completed, nine unchanged startup probes and fresh 122-test
executor admission passed. The next simulator readiness attempt timed out during
Apple data migration before running Native tests. New current-source admission
then passed all 122 contained tests but failed its enclosing cleanup on an
unclassified privileged macOS login-window process. Product testing is on HOLD;
the cancelled complete writer has not been rerun. Full Apple,
real-network/security and capacity qualification remain pending.**
This is a feature-workstream checkpoint, not approval to merge or release. The plan is
preserved unchanged as the original planning snapshot.

The [Mac VPS continuation](mac-vps-validation.md) records the latest successful
and failed attempts. Earlier hosted multicast failures below remain historical
failures, not the current VPS diagnosis or a new RPC regression.

- Isolated clone: `/root/projects/p2pkit-feature-prep-20260927-yiDjCB`.
- Feature branch: `work/rpc-lan-20260927-054728-8b1b11da`.
- Exact base and freshly fetched `origin/main`:
  `3bc76f956f8f47447b51a62474fc878b9c43173c` (no advancement).
- `AGENTS.md` and `CLAUDE.md` were read completely and remain unchanged.
- No Foundation/campaign source, keys, worktrees or private evidence were used.
  Release Foundation remains **NOT_READY**; every existing HOLD and external
  gate remains intact. Future integration must come from main normally.

## Source delivered

1. Additive core/LAN prerequisites: opt-in authenticated admission/quarantine,
   shared payload leases, binary-only restrictions, retained session failure
   and generation observations, generation-bound sending, bounded reconnect,
   explicit organization-private endpoint/interface policy, dial-only clients
   and separate restricted JVM/Android I/O dispatch views. Ordinary P2P defaults
   remain unchanged unless callers select the new profiles.
2. Optional `p2p-rpc`: explicit typed procedures, bounded JSON/wire protocol,
   HELLO/READY, host-owned concurrent execution, deadlines, cancellation,
   correlation, stable-ID recovery, deduplication/tombstones and retained
   outcomes. Ambiguous unsafe calls are not silently re-executed.
3. Pairing/trust and notifications: short-lived single-use invitations,
   administrator approval, application-local durable trust, fresh authorized
   connections, live revocation, bounded best-effort updates and sanitized
   connection/diagnostic observations.
4. Deterministic regressions, an inventory example/shared mobile façade, an
   explicitly invoked JVM capacity driver, developer documentation and applicable
   repository/ABI/dependency/platform/publication inventories. No permissive
   transport, identity store or lab provider is bundled.

The [qualification guide](qualification.md) maps tests to the required platform
and security experiments. The [sample](../../samples/p2p-sample-rpc/README.md)
describes the local integration needed for an authorized driver run. Capacity
requirements remain **128 authenticated clients, 1,280 calls/second, 1 KiB
request/reply bodies, 30 minutes on each actual JVM/Android/iOS host**, plus
physical interoperability and a separate 1 MiB experiment. None has run.

## Earlier authorized local validation

The owner authorized isolated JVM/Android compilation, tests, dependency
retrieval and genuine ABI/lock/checksum generation. The owner subsequently
authorized [feature-only GitHub-hosted macOS validation](hosted-validation.md),
including required hosted SDK/dependency downloads and sanitized artifacts.
The results below remain the completed **local JVM/Android** record; no hosted
Apple pass is inferred from workflow configuration. Real-device/network/capacity
experiments, publishing, merges, tags and repository/environment changes remain
separately gated. No Foundation or release workflow is authorized by that approval.

Validation used the checked-in Gradle 9.7.0 wrapper with strict dependency
verification, warning-as-error policy, no daemon persistence, no parallel
execution and two workers. The installed launcher/toolchain is JDK 17 (the
repository daemon criteria select installed JDK 21), with Android SDK 36,
Kotlin 2.4.10 and AGP 9.3.1. SDK/JDK auto-download was disabled. HOME, Gradle,
Android/Konan state and temporary output were newly owned inside this clone;
no other session's caches or keys were reused. Each Gradle command recorded
its result and stopped only this workstream's Gradle home.

### JVM/Android test results

All rows below executed nonempty XML test suites with **zero failures, errors
or skips in the final run for that row**: 1,923 successful test executions in
total. Common tests executed on both platforms are counted once per platform,
not claimed as distinct test designs or as a capacity measurement.

| Task | Tests passed |
| --- | ---: |
| `:p2p-core:jvmTest` | 857 |
| `:p2p-core:testAndroidHostTest` | 82 |
| `:p2p-transport-lan:jvmTest` | 231 |
| `:p2p-transport-lan:testAndroidHostTest` | 121 |
| `:p2p-network-provisioning-desktop:test` | 20 |
| `:p2p-network-provisioning-android:testAndroidHostTest` | 162 |
| `:p2p-rpc:jvmTest` | 45 |
| `:p2p-rpc:testAndroidHostTest` | 45 |
| `:p2p-sample-rpc:jvmTest` | 5 |
| `:p2p-sample-rpc:testAndroidHostTest` | 3 |
| `:sample-kmp-shared:jvmTest` | 5 |
| `:sample-kmp-shared:testAndroidHostTest` | 1 |
| `:p2p-sample-android:testDebugUnitTest` | 122 |
| `:p2p-sample-desktop:test` | 67 |
| `:p2p-sample-desktop-ui:test` | 39 |
| `:p2p-sample-diagnostics:test` | 118 |

The core/RPC/RPC-sample final run used `--rerun-tasks --continue --offline`.
Core filesystem tests ran on a bounded, privately mounted POSIX tmpfs inside
the clone's temporary directory. This establishes those tests on that
filesystem, **not persistent-disk crash durability or device qualification**.

Initial core runs on the container's ordinary workspace filesystem failed
`FileTransferJvmTest.durableDestinationUsesSiblingStagingAndPrivatePosixPermissions`
and `AndroidDurableFileDestinationAndroidHostTest.stagingPermissionsAreAppliedBeforeOpeningPayloadStream`.
A small Java probe reproduced different filesystem device IDs for a directory
and its own staging file, despite correct private permissions; tmpfs preserved
the same device ID. The entire affected production/test files are unchanged
from main. Both complete suites subsequently passed on private tmpfs. No
assertion, timeout or platform requirement was weakened to obtain that result.

The four remaining sample suites also passed complete offline reruns. They
used private mount/PID/network namespaces, installed font configuration and
owned temporary/home paths; test JVM flags were supplied explicitly instead
of inherited launcher-banner variables, preserving exact subprocess-output
assertions. The first CLI run lacked a non-loopback interface, so its unchanged
manual-pairing test could not obtain local connection information. A
namespace-only synthetic veth supplied that prerequisite for the final run,
with no default route or access to the host network. Setup capabilities were
dropped before Gradle started. These are synthetic/loopback regression results,
not real-LAN, Android ART, GUI deployment or physical-network qualification.

Local compiler validation also found and fixed:

- Coroutines 1.11.0 requires `DelicateCoroutinesApi` for `CoroutineStart.ATOMIC`.
  The local opt-in preserves admitted-record cleanup and cancellation semantics.
- The new internal Android route option had displaced a trailing lambda.
  Restoring the lambda-last constructor preserved existing tests; two additional
  tests verify fresh lookup and rejection of stale-route fallback.
- Sample framework export calls needed the non-deprecated dependency notation.
  This does not establish successful Apple framework compilation.

### ABI and dependency evidence

- Genuine core/LAN Android ABI generation and all four Android library ABI
  comparisons passed, including their compiled public-constant guards.
- JVM dumps for core/LAN/RPC were extracted with the same pinned built-in Kotlin
  dumper, JVM inputs, filters and services in an isolated supplemental task.
  Core/LAN add 101/20 lines respectively on each platform, with no removed
  signatures. RPC's complete JVM/Android dumps were reviewed. All four JVM
  public-constant guards passed. **The complete JVM/KLIB compatibility gate is
  still required; no Native ABI is inferred from this focused extraction.**
- The Android dumper retains synthetic companion-access bridges for private
  constructors. The guard now recognizes that exact JVM bridge shape while
  still rejecting internal classes, ordinary constructors, methods and fields.
  Existing negative controls and six additional leak controls passed; genuine
  ABI output was not hand-edited to hide the bridges.
- Gradle generated 13 new `kotlinx-serialization-json-io:1.11.0` checksum entries.
  Independent official Maven downloads, SHA-256 sidecars and detached signatures
  verified all 13. The reviewer supports authenticated reciprocal KMP metadata
  and exact-hash local filename aliases; 32 locator/curator tests passed.
  Existing checksum history and trust configuration were preserved unchanged.

Fresh main still contains six obsolete external `org.jmdns:jmdns:3.6.3` lock
entries. Strict LAN compilation first reproduced the reported baseline failure.
After verifying main's unchanged private embedded producer and unused external
catalog alias, only those six obsolete lines were independently removed. No
Foundation repair was read or copied. Subsequent strict JVM/Android resolution
and tests passed. This is a **separate baseline correction**, not an RPC regression.

A second independent baseline tripwire still expected a literal
`publishToMavenLocal` invocation, whereas main's unchanged consumer script now
selects a fixed `publish_tasks` array. The source-policy check was aligned with
that actual command, retaining `--no-daemon` and explicitly requiring the
complete default publication profile. No consumer publication was executed.

The reviewed source checkpoint is `7a8a7960` on the feature branch. Baseline
lock cleanup (`13172e1a`) and the consumer-policy correction (`57434844`) are
separate from authenticated dependency review (`2bf61072`) and the RPC/compiler/
ABI fixes. All 127 changed non-Markdown files were hash-compared against the
validated working tree and that committed tree; they match exactly. Validation
logs retain their original HEAD plus dirty-state record, not a fabricated
post-commit execution claim.

### Source and policy checks

| Command/check | Observed result |
| --- | --- |
| `git fetch --no-tags origin main`, ancestry and instruction hashes | Main unchanged; guidance and approved plan unchanged. |
| `git diff --check`; added Kotlin-line/import scan; changed Python AST/TOML parsing | Passed; not a substitute for ktlint. |
| `bash scripts/check-dependency-verification.sh` | Passed strict checksum/trust-policy validation. |
| `python3 scripts/tests/check-rpc-module-policy-test.py` | Passed, including seven negative controls. |
| `bash scripts/tests/check-repository-layout.sh` | Passed for 12 projects, including Android/RPC inventory controls. |
| `bash scripts/tests/check-markdown-links.sh` | Passed active-document relative links. |
| `bash scripts/check-release-metadata.sh`; `python3 scripts/tests/check-release-metadata-test.py` | Passed; 11 tests, versions unchanged. |
| `bash scripts/tests/check-dependency-update-policy-test.sh` | Passed, including 7 bounded-reader, 32 locator/curator and 15 temporary-directory tests. |
| `python3 scripts/tests/run-platform-tests-test.py` | All 23 policy/lifecycle fixtures passed; these are not platform execution. |
| `bash scripts/tests/check-kotlin-toolchain-policy-test.sh` | Passed, including host-checksum, Android-ABI and version-input negative controls. |
| `ruby scripts/tests/check-jvm-cross-host-policy-test.rb` | 34 checks passed. |
| `ruby scripts/tests/check-platform-test-policy-test.rb` | 31 checks passed. |
| `ruby scripts/tests/check-publication-sbom-policy-test.rb` | Current policy, 27 negative mutations and seven fake-wrapper/real-validator cases passed. |
| `python3 scripts/tests/check-sbom-test.py` | 23 tests passed; not an actual publication SBOM. |
| `cyclonedxBom`, then `bash scripts/check-sbom.sh <generated-json> <generated-xml>` | Passed actual generation and independent validation: 88 components, a connected five-library root, verified embedded JmDNS provenance and no build/sample contamination. No publication occurred. |
| `:p2p-sample-android:lintDebug`, `:p2p-rpc:lintAnalyzeAndroidHostTest`, `:p2p-sample-rpc:lintAnalyzeAndroidHostTest` | Passed; Android sample report contains zero issues. RPC tasks are host-test analysis, not a substitute for full published-consumer or device checks. |
| `python3 scripts/tests/check-publish-license-test.py` | 11 license and 67 embedded-JmDNS fixtures passed; no publication. |
| `JAVA_HOME=<installed JDK 17> bash scripts/tests/check-public-constant-abi.sh` | 26 compiled Java positive/negative controls passed. |

The temporary-directory and process-lifecycle fixtures initially encountered
long GPG socket paths and unreaped orphan zombies in the ambient container.
They passed unchanged in private mount/PID/network namespaces: the source was
read-only, every temporary file remained backed by a newly owned directory
inside this clone, and only disposable synthetic keyrings were used. No
socket limit, cleanup assertion or timeout was relaxed.

The first offline Android lint attempt lacked the pinned AAPT2 artifact in the
new cache. Fetching that existing, checksum-listed build dependency under the
authorized strict resolver allowed the complete focused command to pass; no
SDK installation, checksum bypass or source suppression was needed. Generated
SBOM JSON/XML and lint reports were snapshotted and hashed in the owned logs.

## Unfinished gates and evidence

- **Complete dependency locks:** RPC and sample locks remain absent, not
  fabricated. The root requires `resolveAndLockAll --write-locks
  --write-verification-metadata sha256 --no-configure-on-demand`, whose graph
  includes Apple work and every required check. Partial configuration-time
  candidates from graph inspection were quarantined and original locks restored.
  The OSV coverage guard still correctly fails: 12 requested lock inputs but
  only 10 populated inputs. Embedded-producer lock coverage also needs the
  complete writer. The hosted writer failed at multicast readiness. All eight
  direct-source lifecycle modes later passed on the supplemental VPS, but its
  complete writer stalled at core Intel simulator execution and was cancelled;
  fresh executor admission then failed. The later scan diagnosis and restored
  executor admission do not replace that writer failure. A later 120-second
  simulator-readiness attempt failed during Apple data migration, before Native
  test startup. Current-source executor controls passed individually but their
  enclosing admission failed to classify a privileged macOS login-window
  lifetime; cleanup remains unproven and further product work is held. No partial
  locks/checksums were imported.
  See the [current Mac evidence and next steps](mac-vps-validation.md).
- **Apple and complete ABI:** the [first hosted follow-up](hosted-validation.md)
  compiled Native/Cinterop and generated genuine core/LAN/RPC ABI candidates.
  Core/RPC/RPC-sample ARM simulator tests passed, but LAN had a Native failure
  and an unchanged-main JVM lifecycle failure. The complete writer failed and
  no partial candidates from that failed run were imported. A later successful
  maintained ABI-generation run on the VPS supplied the reviewed Native baselines
  committed in `1b2bc035`; complete strict-input gates and matching supported
  Intel execution remain outstanding.
  A scoped diagnostic confirmed unchanged JmDNS `host_not_announced` with first
  send `NoRouteToHostException` before lifecycle assertions; its cause is unknown.
  Seven later child modes did not run. A new Native test's unavailable libc
  binding was also found and corrected; that run executed no Native tests.
  The corrected Native-only follow-up passed all 194 enabled LAN ARM simulator
  tests (plus the one pre-existing ignored diagnostic), including all three new
  endpoint-helper regressions, under normal strict resolution with unchanged
  inputs. Fresh counts/XML and cleanup were verified; it did not repeat JmDNS.
  A later strict compiler run linked all three RPC sample Apple frameworks and
  typechecked the Swift consumer fixture for each matching SDK/iOS-14 target;
  actual outputs/minimum-OS metadata and cleanup were verified. This is not
  Swift application/runtime, physical-device or true-Intel execution evidence.
- **Strict Dokka:** core/LAN/RPC `dokkaGeneratePublicationHtml` passed with normal
  strict resolution, warnings-as-errors and unchanged inputs in the hosted
  compiler run. Nonempty outputs were hashed. No task was disabled and no
  publication occurred; the complete writer/release gate is still outstanding.
- **Full release/consumer validation:** the actual SBOM, focused Android lint
  and scoped framework/Swift compiler passes do not establish packaging,
  published-consumer, Swift application/runtime or complete cross-platform
  release-gate success. No publication occurred; shared Foundation/release
  workflows were not dispatched.
- **Physical/security/capacity qualification:** none has run. Follow the exact
  experiments and evidence rules in [qualification](qualification.md). A failed
  capacity or security contract is a stop-and-review decision, not permission
  to shrink the workload, enlarge limits blindly or change the architecture.
- No merge, publication, tag, cancellation of another run,
  repository/environment change or readiness promotion occurred. Feature pushes
  have not been used as a substitute for complete checks or coordination.
  The subsequently authorized hosted work is tracked separately from this local
  checkpoint and does not change any Foundation HOLD or external gate.

Owned command logs, XML snapshots, graph inspections and review receipts remain
under `.git/rpc-validation-20260927-RkXqJ9/` in the isolated clone, not in source
control. They include unsuccessful exploratory runs as well as final results;
only explicitly successful checks above are reported as passed.
The separately authorized [hosted continuation](hosted-validation.md) retains all
four run records and verified sanitized artifacts in
`.git/rpc-hosted-20260927-0k7TY6/`; it ran no local Java/Gradle/Xcode build, accessed
no other worktree/keys/private evidence, and imported no partial generated inputs.
