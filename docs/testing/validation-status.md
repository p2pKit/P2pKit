# Validation status

## Verified release scope

Use [`LATEST_PUBLISHED_VERSION`](../../gradle.properties) and its immutable
[release record](../README.md#test-and-release) for published evidence. The latest
verified record when this guidance was reconciled is
[`0.8.0-rc6`](../releases/0.8.0-rc6.md), source
`3ef2c6155abd66292011c3775b30fb71d280e9c7`. Its exact-source fourteen-component
qualification, four frozen applications, signed Maven originals and complete
anonymous download hashes are recorded there—not inferred from later `main`.
The original publisher's final upload failed; the distinct read-only recovery
and subsequent application publication succeeded. The missing original final
publication/SBOM archive was not reconstructed or called retained.

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

The recorded rc6 has actual same-source results for these components, as recorded above.
They must not be reused as a pass for changed source. Deterministic callbacks,
loopback TCP and hosted multicast still do not establish physical-network coverage.

## Kotlin target execution and structural gaps

`scripts/run-platform-tests.py` checks fresh, nonzero test events against
`gradle/platform-test-policy.json`. The `macos-shared`, `ios-arm64` and `ios-x64`
profiles together retain the complete portable task inventory and non-test
`check` dependencies. Cached XML, dry runs and cross-compilation are not native
execution. See [platform execution evidence](local.md#platform-execution-evidence).

| Target / suite | Verified release scope and remaining limitation |
| --- | --- |
| JVM | Linux/Windows components and macOS shared gate passed for the recorded rc6 source. |
| Android | Host JVM tests and APK inspection passed; framework stubs/Robolectric are not ART or physical devices. Separate source-bound instrumentation results must be consulted for ART/privacy cases; they are not a complete physical-device suite. |
| `iosSimulatorArm64` | Native simulator profile passed for the recorded rc6 source. |
| `iosX64` | Separate native Intel simulator profile passed for rc6; ARM64 cross-compilation is not its evidence. |
| `iosArm64` | Device target still requires external hardware and real device-test execution. |
| KMP metadata | Compilation/publication checks, not a runtime test target. |
| Swift sample | Recorded rc6 Swift unit/UI and XCFramework checks passed within their exact simulator scope; physical-device behavior and later changes need separate evidence. |

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
