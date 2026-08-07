# iOS sample app scripts

## `check-xcframework.sh`

V0.4-PROVENANCE (L3) — Xcode pre-build validation for the `P2pKitShared`
XCFramework. Re-runs `:p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework`
and fails the Xcode build if the resulting XCFramework's `BUILD_COMMIT.txt`
sidecar does not match `git rev-parse HEAD`.

### One-time setup (per-developer)

The Xcode project (`iosApp/p2pkit-sample.xcodeproj/`) is git-ignored, so
each developer must wire this script as a Run Script build phase in
their own copy of the project. To set it up:

1. Open `iosApp/p2pkit-sample.xcodeproj` in Xcode.
2. Select the `p2pkit-sample` target → Build Phases tab.
3. Click `+ → New Run Script Phase`.
4. Drag the new phase to be the **FIRST** build phase (above
   "Compile Sources").
5. Rename it: `Verify XCFramework freshness (V0.4-PROVENANCE)`.
6. Set the Shell to `/bin/sh`.
7. Set the Script body to a single line:
   ```sh
   "$SRCROOT/scripts/check-xcframework.sh"
   ```
8. Untick "Based on dependency analysis" (so the script runs every
   build; otherwise Xcode would skip it after the first run).
9. Leave Input Files / Output Files empty.
10. Build the app once to verify the phase runs and the script
    succeeds. On success you'll see `✅ XCFramework is fresh: <hash>`
    in Xcode's build log.

### What the script does

- Runs `./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework`
  to ensure the XCFramework is up to date.
- Reads `p2p-transport-lan/build/XCFrameworks/release/BUILD_COMMIT.txt`
  (a sidecar file written by the Gradle task `writeXcframeworkCommit`).
- Compares the recorded commit against `git rev-parse HEAD`.
- Fails the build if they differ — refusing to compile against stale
  framework code.
- Soft-warns (does not fail) when the working tree is dirty — uncommitted
  changes are routine during active development.
