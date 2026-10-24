# Validation status

## Verified release scope

Use [`LATEST_PUBLISHED_VERSION`](../../gradle.properties) and its immutable
[release record](../README.md#test-and-release) for published evidence. The latest
verified record is [`0.8.0-rc7`](../releases/0.8.0-rc7.md), release source
`bc3a28e8e381b49585fb697160cb954bc642ea29`, tree
`1640bade9fd47504f2400ee1df44d4303697dd99`.
Accepted aggregate `39879254089/1` selects thirteen successful components from
actual main run `39863595940/1` and unchanged-source Intel replacement
`39864735586/1`. The original run, its Intel job `120120189650` and its derived
complete gate remain **FAILURE**. The observed runtime-enumeration command
timeout has no established underlying cause and receives no native-test credit;
a successful replacement does not prove that cause repaired.
All four frozen applications came from the original main producer attempt;
the aggregate reused those originals without rebuilding them.

Original protected publisher `39908887966/1` succeeded with 121 signed files
across 21 coordinates and 726 bundle members. Its genuine original log records
the 242-file remote-byte PASS, complete isolated remote-consumer marker and full
88-component signing-build SBOM validation. A distinct later read-only check
also matched all 242 current Central files against that signed bundle; it did
not rerun consumers. The inner consumer `command.log`/`result.json` were not
uploaded or independently retained: evidence is the actual successful step and
marker under the unchanged source-enforced completion/cleanup contract, not
separately retained inner cleanup/task receipts.

Separate protected sample publisher `39914877731/1` delivered the exact frozen
four-application set as `samples-v0.8.0-rc7` on `2026-10-23T07:54:10Z`.
Independent complete anonymous downloads passed for all seven public assets,
including notices, manifest and checksums: **364,059,569 verified bytes**.
Their byte counts and SHA-256 values match the approved originals. Delivery and
static package inspection do not establish installed-app, provider, physical
device or hostile-network qualification.

### Historical rc6 publication boundary

The [rc6 record](../releases/0.8.0-rc6.md) remains bound to source
`3ef2c6155abd66292011c3775b30fb71d280e9c7`. Its exact-source fourteen-component
qualification, four frozen applications, signed Maven originals and complete
anonymous download hashes are recorded there—not inferred from later `main`.
The rc6 publisher's final upload failed; its distinct read-only recovery and
subsequent application publication succeeded. The missing original rc6 final
publication/SBOM archive was not reconstructed or called retained. That archive
limitation and recovery must not be transferred to rc7.

Earlier [rc2](../releases/0.8.0-rc2.md) and
[0.7.0-rc3](../releases/0.7.0-rc3.md) evidence stays historical. No release certifies
subsequent source changes or completes the
[six external campaigns](../validation/README.md#current-status).
Windows sample Host/Client and installed loading/provider integration are
implemented; full W01–W11 qualification remains incomplete. See the
[precise Windows scope](../rpc/windows-release-scope.md).

## Informational automated history (not release or campaign evidence)

The final post-RC3 executable audit tree
`588421f59efd1bcb4cc7d3b7e1205b1ab28b4f85` (PR #103 head
`056708dfcda85d6b4aa9073c156ba386e17803b4`) passed complete gate
[31715657369](https://github.com/p2pKit/P2pKit/actions/runs/31715657369),
dependency review, both OSV contexts, and macOS/Linux/Windows Desktop sample
packaging and sample test checks.
It merged as `fbba43328df19cf72956df7417886361b335a570` with an identical tree.
That historical cross-host task list did not run the library JVM suites on
Windows/Linux. It is neither a published release nor substitute evidence for
those library tests or the campaigns below.

## Maintained hosted coverage and limits

The modular `ci.yml` workflow uses `ci-component.yml`; the current commands and
host assignment are maintained in `scripts/ci_component.py`. JVM library and
sample tests run in distinct Linux/Windows components; macOS shared checks and
native ARM64/Intel simulator components retain their own source-bound reports.
`complete-gate` requires their actual successful aggregation, including on
ordinary documentation PRs. A focused component pass is not complete qualification.

The recorded rc7 selection has actual same-source results for all fourteen
components, with the original/replacement identities above. They must not be
reused as a pass for changed source. Deterministic callbacks, loopback TCP and
hosted multicast still do not establish physical-network coverage.
**The published rc7 source still contains the High discovery-admission limitation
tracked in #120. Stable/production remains NOT_READY.**

## Kotlin target execution and structural gaps

`scripts/run-platform-tests.py` checks fresh, nonzero test events against
`gradle/platform-test-policy.json`. The `macos-shared`, `ios-arm64` and `ios-x64`
profiles together retain the complete portable task inventory and non-test
`check` dependencies. Cached XML, dry runs and cross-compilation are not native
execution. See [platform execution evidence](local.md#platform-execution-evidence).

| Target / suite | Verified release scope and remaining limitation |
| --- | --- |
| JVM | rc7 Linux: 1,975 PASS; Windows: 1,952 PASS. The distinct macOS shared gate has 3,212 PASS across its host-test inventory, not 3,212 additional unique library controls. |
| Android | rc7 Android component: 933 PASS, plus original debug APK inspection. Host JVM/stub/Robolectric tests are not ART or physical-device execution. Earlier source-bound instrumentation/privacy witnesses retain their own source/run identities. |
| `iosSimulatorArm64` | rc7 native ARM64 component: 1,225 PASS and 1 existing diagnostic SKIPPED (1,226 events); the skip is not a pass. |
| `iosX64` | Same-source replacement `39864735586/1`: 1,225 PASS and 1 existing diagnostic SKIPPED (1,226 events). Original Intel job failed before qualifying native tests; ARM64 cross-compilation is not Intel execution. |
| `iosArm64` | Device target still requires external hardware and real device-test execution. |
| KMP metadata | Compilation/publication checks, not a runtime test target. |
| Swift sample | rc7 compatibility originals: 99 unit and 24 UI cases, zero failures/errors/skips, on iOS 26.5 simulator. Sample deployment floor 15.0 and library XCFramework floor 14.0 are not physical minimum-OS test results. |
| Desktop samples | rc7 Linux: 156 PASS; Windows: 298 PASS; macOS: 156 PASS. Original DEB/MSI/DMG packaging and static metadata inspection do not establish installed-app or provider execution. |

Counts are per selected component, not a sum of unique controls. Focused cases,
source-expectation rows and repeated report projections are not additional
tests. Main consumers used unsigned local rc7 coordinates and 21 required task
outcomes; signature skips in that mode are not failed signatures or remote
Maven verification. Protected remote consumers belong to the separate release
publication evidence.

Historical rc2 used the temporary macOS 14 CLI/shared baseline. The maintained
macOS 15 Intel/Xcode 26.3 replacement has actual same-source shared/native and
consumer results in the later release records, including rc6. Do not revive the
retired macOS 14 setup or confuse historical macOS 26 JVM multicast failures with
a fresh result from the replacement. New source/toolchain changes still need
matching hosted qualification. Publication does not remove structural or
physical-device limits.

## External campaign status

The [canonical six-area table](../validation/README.md#current-status) is the
sole current campaign-status record. Its CLI/Desktop partial status refers to
automated coverage, not completed fault injection or headful observation.
Android instrumentation authoring/ART execution and the target gaps above are
separate prerequisites, not evidence of physical-device campaign completion.

Follow the table's individual handbooks for equipment, steps, observations,
logs, evidence exports, pass/fail criteria and result templates. The
cross-platform tracker-ID procedures and logging matrix are in the
[test catalog](../validation/test-catalog.md). No host or simulator result may
stand in for the required external evidence.
