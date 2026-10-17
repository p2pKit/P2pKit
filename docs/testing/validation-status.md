# Validation status

## Verified release scope

The [`0.8.0-rc2` release record](../releases/0.8.0-rc2.md) binds the following
results to source `bd98deeb6ab44b5f5126d88742aa69b57f290c32`, not to later
`0.8.0-SNAPSHOT` development:

- Exact-source modular qualification, including JVM Linux/Windows/macOS,
  Android host checks and packaging, native ARM64/Intel iOS simulator execution,
  API/ABI, strict Dokka, dependency/security checks, SBOM, publication shape,
  isolated consumers and Swift/XCFramework checks.
- Actual protected Maven publication with signed-original and remote-byte
  verification and complete remote-consumer checks.
- The same-source frozen APK/MSI/ARM64-DMG/DEB development prerelease, with full
  anonymous-download hashes verified for all seven public assets.

The prior [`0.7.0-rc3` record](../releases/0.7.0-rc3.md) remains historical.
Neither release's results certify subsequent source changes or complete the
six campaigns in the [canonical status table](../validation/README.md#current-status).
Windows sample RPC Host/Client is still unavailable; see its
[explicit implementation and runtime limitations](../rpc/windows-release-scope.md).

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

`0.8.0-rc2` has actual same-source results for these components, as recorded above.
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
| JVM | Linux/Windows components and macOS shared gate passed for the recorded rc2 source. |
| Android | Host JVM tests and APK inspection passed; framework stubs/Robolectric are not ART or physical devices. The authored focused API37 case does not constitute a complete device suite. |
| `iosSimulatorArm64` | Native simulator profile passed for the recorded rc2 source. |
| `iosX64` | Separate native Intel simulator profile passed for rc2; ARM64 cross-compilation is not its evidence. |
| `iosArm64` | Device target still requires external hardware and real device-test execution. |
| KMP metadata | Compilation/publication checks, not a runtime test target. |
| Swift sample | Swift warnings-as-errors and XCFramework provenance checks are not a claim of unit/UI or physical-device execution. |

The published rc2 used the temporary macOS 14 CLI/shared baseline, which retires
on `2026-11-02`. Current source selects a macOS 15 Intel/Xcode 26.3 replacement;
its configured routes are not yet a passing hosted qualification. Retain actual
same-source JmDNS/shared/consumer execution before claiming the replacement
accepted. Native ARM64/Intel and Desktop/Swift lanes remain unchanged. These
structural and runtime limits are not changed by publication.

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
