# iOS sample app scripts

## `check-xcframework.sh`

V0.4-PROVENANCE (L3) — Xcode pre-build validation for the `P2pKitShared`
XCFramework. Runs
`:p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance`, which
assembles the framework as needed and checks its commit, relevant source state,
input fingerprint, and framework binary/header fingerprint before Xcode links it.

### How the gate is wired

The maintained [project.yml](../project.yml) declares
`Check P2pKitShared XCFramework provenance` under `preBuildScripts`, using
`sh "$SRCROOT/scripts/check-xcframework.sh"` and
`basedOnDependencyAnalysis: false`. XcodeGen writes this phase into the ignored
`samples/iosApp/p2pkit-sample.xcodeproj` on every regeneration, ahead of compilation.
Do not add a second phase manually: hand-edited project settings/phases are lost
on the next regeneration. Keep changes to the gate in `project.yml` or the script.

Machine prerequisites are Xcode with its command-line tools selected, JDK 17,
and XcodeGen (`brew install xcodegen`). Use the repository's
[local testing setup](../../../docs/testing/local.md). Device builds also require
an Apple ID/development team and a valid development signing setup. The project
uses automatic signing; supply the team through local build settings, such as
`DEVELOPMENT_TEAM=<team-id>` for command-line device builds. Never commit signing
identifiers, profiles, or credentials. See the
[physical-device handbook](../../../docs/validation/apple-physical-awdl.md).

Supported entry points, run from the repository root:

- `./gradlew :iosApp:regenerateXcodeProject` — regenerate the Xcode project only.
- `./gradlew :iosApp:runIosSimulator` — regenerate, build, install, and launch on
  one exact simulator.
- `./gradlew :iosApp:runIosUiTests` — regenerate and run the unit/UI simulator suites.

For direct Xcode work, verify/assemble the release XCFramework first if absent,
generate the project, and open `samples/iosApp/p2pkit-sample.xcodeproj`. Build once
and confirm the generated phase runs. Its success line in the Xcode build log is
`✅ XCFramework is fresh: <hash> (matches HEAD, source state: <state>)`.

### What the script does

- Invokes the release provenance verifier. Its dependency
  `writeP2pKitSharedReleaseXCFrameworkProvenance` runs after successful assembly
  and writes four sidecars under
  `library/p2p-transport-lan/build/XCFrameworks/release/`: `BUILD_COMMIT.txt`,
  `BUILD_SOURCE_STATE.txt`, `BUILD_INPUTS_SHA256.txt`, and
  `BUILD_ARTIFACTS_SHA256.txt`. The Gradle verifier checks all four against the
  current inputs and framework artifacts.
- Requires both `ios-arm64` and `ios-arm64_x86_64-simulator` framework binaries.
- Re-reads the commit, source-state, and input-fingerprint sidecars in the shell;
  rejects a commit different from `git rev-parse HEAD`, invalid source state,
  or a malformed SHA-256 fingerprint.
- Warns, rather than fails, when relevant tracked or untracked framework inputs
  are dirty. That artifact may be current for local development, but is not
  reproducible from the commit alone. This warning does not satisfy the clean,
  immutable-source requirement for release or external-validation evidence.
