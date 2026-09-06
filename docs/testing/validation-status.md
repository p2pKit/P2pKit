# Validation status

## Completed locally or through publication infrastructure

- Complete committed module/platform gate, ABI baselines, strict Dokka,
  publication shape, isolated consumers, SBOM, signing, provenance,
  Swift warnings-as-errors, and XCFramework provenance have passed for the
  published `0.7.0-rc3` release commit.
- `BUILD-02` and `ENV-07` remote publication/consumer evidence are recorded in
  the [`0.7.0-rc3` release record](../releases/0.7.0-rc3.md).

Those are immutable historical RC3 results. Current `main` is a post-RC3
`0.7.0-SNAPSHOT` development line. Automated results for current `main` do not
retroactively validate RC3, and RC3 results do not validate later fixes. The
six campaigns below must use one separately frozen commit and artifact set.

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

## Configured JVM host coverage

The checked-in `CI` workflow runs `:p2p-core:jvmTest`,
`:p2p-transport-lan:jvmTest`, and `:p2p-network-provisioning-desktop:test` on
Ubuntu and Windows; the macOS `complete-gate` runs them through `check`.
`complete-gate` explicitly fails unless both other hosts succeed, including
for documentation-only changes. The separate `Desktop cross-host` workflow
continues to cover sample tests and packaging, not these library suites.

This is configured coverage, not evidence that the new hosted jobs have passed.
No Windows/Linux library result for this revision is recorded here yet. Retain
per-host results and the exact tested commit before claiming execution; see
[the local testing guide](local.md#jvm-host-coverage). Deterministic discovery
callbacks and real loopback TCP do not establish physical mDNS/network coverage.

## Kotlin target execution and structural gaps

The current full macOS gate uses `scripts/run-platform-tests.py full` around
`check`. It requires fresh, nonzero test events for each host-executable task
in `gradle/platform-test-policy.json`, and reports every configured Kotlin
target. Cached XML, a dry-run, disabled tasks, and compilation are not execution.

| Target / suite | Configured coverage and limitation |
| --- | --- |
| JVM | Full macOS gate; required Ubuntu/Windows library matrix described above. |
| Android | Host JVM only: framework stubs and provisioning Robolectric shadows. Core's `*AndroidHostTest` filter excludes its common suite; there is no authored instrumented/device suite or ART runner. |
| `iosSimulatorArm64` | Expected execution on the default Apple Silicon macOS runner. |
| `iosX64` | Published simulator slice; task is registered but disabled on arm64. Weekly/manual `Intel iOS simulator tests` uses `macos-15-intel` and requires both library suites to execute. No hosted Intel pass for this revision is recorded here. |
| `iosArm64` | Device target has no configured device-test execution task. GitHub-hosted simulators cannot establish physical-device coverage; external hardware/runner integration is required. |
| KMP metadata | Compilation-only; not a runtime test target. |
| Swift sample | Unit/UI simulator tests run separately through Xcode in CI, outside Gradle `check`. The local release gate builds the sample with warnings-as-errors; that build is not Swift test execution. |

Intel runner configuration is not a claim of execution or a decision to ship
untested. Retain a same-source Intel result before claiming that slice tested;
runner availability must be rechecked rather than assuming an end-of-support
date. Android instrumentation requires new test authoring before any emulator
job can supply evidence. These structural gaps differ from an existing physical
test procedure that has not yet been performed. See
[platform execution evidence](local.md#platform-execution-evidence).

## Pending external validation

The following remain pending and must not be described as verified:

1. Android instrumented-suite authoring, ART execution, and physical-device validation.
2. Apple physical-device, AWDL, path-rotation, background, and process-restart validation.
3. Two-machine hostile-network validation.
4. CLI fault injection and headful Desktop observation.
5. Independent secure-v2 interoperability validation.
6. Professional cryptographic audit.

The exact equipment, steps, UI observations, logs, evidence exports, pass/fail
criteria, and result templates are in the
[real-world validation handbook](../validation/README.md). The cross-platform
tracker-ID procedures and logging matrix are in its
[test catalog](../validation/test-catalog.md).
