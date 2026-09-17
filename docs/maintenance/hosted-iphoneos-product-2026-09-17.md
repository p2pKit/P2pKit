# Hosted unsigned iphoneos recipe proof

This is the narrow remaining computer-only acceptance route for
[#327](https://github.com/p2pKit/P2pKit/issues/327), not an iOS application release.
The original DerivedData recipe correction
`0a6f16b7aa1231268fc09c4e8752bd53d30df4c2` is already on main and is unchanged.
The new route is **source/test preparation until independently reviewed and
actually executed**. Authored tests and synthetic parser fixtures do not prove
a genuine Xcode build. Physical installation remains separately deferred.

## Closed operation and prerequisites

The existing [Desktop workflow](../../.github/workflows/desktop-cross-host.yml)
adds only the manual `iphoneos-product` operation. Its source commit **and tree**
must equal the reviewed branch tip, full-history clean checkout, genuine event
and workflow identity. The retired audit branch is refused. Shared writer/base/
recipient inputs must be empty. The ordinary push/PR/Desktop/sample selectors,
tasks, deadlines and credential isolation are not replaced or weakened.

The job requires genuine native ARM64 macOS 26, Xcode 26.5 at
`/Applications/Xcode_26.5.app/Contents/Developer`, completed first launch, native
JDK 17 and 21, both Apple compile SDKs, at least 16 GiB free disk/6 GiB physical
RAM, and **already installed** Android compile platforms with literal metadata
`36` and `37.0`. Current original SDK metadata is retained. The dated hosted
ARM [Xcode 26.5 inventory](hosted-lock-route-2026-09-15.md#reachable-github-path-and-its-real-prerequisites)
and [actual host admission](hosted-lock-result-2026-09-15.md#immutable-run-and-source)
are rationale to attempt admission, not a future runner/image guarantee.
Missing SDKs produce HOLD; this route installs no Android SDK, accepts no
licenses, and starts no simulator, emulator, runtime fixture or phone.

The pinned setup-java action supplies the two native JDKs. The canonical
[XcodeGen installer](../../scripts/install-xcodegen.sh) supplies 2.45.4 to one
new owned directory. A new immutable audit state creates its bounded Gradle
home; it imports neither build outputs nor a shared Gradle home/cache. Existing
dependency-seed qualification is **not** populated-seed availability and is not
automatically connected to this route. Dependency downloads on the hosted
runner are possible. Every started canonical leaf, including command-kind
leaves, runs same-home wrapper `--stop`; an empty home's first stop may itself
bootstrap Gradle. Nothing here promises zero downloads or measured bandwidth
savings. No local build/download is implied by preparing this workflow.

## Exact proof, not a substitute product

The [closed driver](../../scripts/run-hosted-iphoneos-product.py) uses the
existing native ownership backend for small tool/controller commands and the
unchanged public immutable leaf for:

1. Installing pinned XcodeGen.
2. A fresh producer with purpose `xcframework-build`, requested task exactly
   `:p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance`.
3. `:iosApp:regenerateXcodeProject`.
4. The corrected generic unsigned recipe:

   ```bash
   xcodebuild -jobs 2 -project samples/iosApp/p2pkit-sample.xcodeproj \
     -scheme p2pkit-sample-ui -configuration Debug -sdk iphoneos \
     -destination generic/platform=iOS -derivedDataPath "$STATE/xcode-deriveddata" \
     CODE_SIGNING_ALLOWED=NO SWIFT_TREAT_WARNINGS_AS_ERRORS=YES build
   ```

DerivedData must not exist before this build. The inspected product is exactly
`$STATE/xcode-deriveddata/Build/Products/Debug-iphoneos/p2pkit-sample.app`.
Its actual Info.plist must identify the expected app/version, secure Bonjour
namespace and device SDK. Original `vtool -show-build` and `lipo -archs` outcomes
must identify `IOS/arm64`, app minimum 15.0 and framework minimum 14.0, not an
arm64 simulator binary.

The four producer sidecars and producer receipt are retained before Xcode runs.
A separate original observation binds the actual device-framework hash/size
to that producer. The embedded framework must match those actual producer
bytes before and after inspection. `BUILD_ARTIFACTS_SHA256.txt` is an aggregate
over paths and raw artifact bytes, **not** a per-binary hash list; a binary hash
cannot be reconstructed from it. The metadata-only proof therefore combines
the executed canonical verifier, original sidecars and separate producer and
embedded-binary observations. It is not a signature or binary redistribution.

The maintained Xcode prebuild script must actually execute its one nested
`xcode-provenance` leaf, bind the outer build ancestor and the same producer,
and report unchanged `xcframeworkReuse`. Exporting an executor path alone is
not accepted reuse. Generated scheme/project identity, real app inventory,
binary hashes/sizes, all command exits and native retirement are retained.
If XcodeGen changes tracked Info.plist, immutable admission fails. There is no
dirty-source exception or automatic source rewrite to hide that outcome.

## Finite scheduling and retention contract

The new job cap is 180 minutes. Step caps are checkout 5, dispatch admission 1,
JDK setup 10, path export 1, driver 155, separate validation 2, upload 3, final
failure guard 1: **178 minutes**, leaving two minutes job margin. The driver's
absolute cap is **150 minutes/9000 seconds from entry**, leaving five minutes
before its step cap. These are unmeasured scheduling limits, not duration or
download estimates. No ordinary workflow deadline is increased.

Each productive leaf is clamped to the remaining absolute budget minus a fixed
600-second completion reserve and 300-second final assessment/retention/cleanup
reserve. Individual caps are installer 900 seconds, generator 600, producer and
xcodebuild 7200 each. Two full 7200-second grants are not promised to fit.
Insufficient time is NOT_EXECUTED/HOLD, never an optional success. Cooperative
cancellation is requested once; early cancellation can only shorten the
completion deadline, never reset/extend it. Its last ten seconds include the
existing native 5+5-second drain. The canonical nested 150-second cancellation,
120-second stop and native drain bounds are unchanged. Missed deadlines or
unknown retirement cannot pass or authorize another productive command.

Only reviewed fixed **compile/metadata** commands run with a closed child
environment: no Actions token, signing/publishing value, recipient, arbitrary
command, runtime fixture, event dump, JVM/Gradle/loader hook or inherited key
home. These commands' raw outputs are classified as public build diagnostics
*before* their canonical Tee starts; no payload/private runtime suite is run.
Do not expand the task set under this classification without review.

The public allowlist contains original command/stop logs and terminal receipts,
source/context/resource policy, toolchain metadata, the four sidecars and their
manifest, producer observation, generated scheme, app/framework Info.plist,
product inventory/hashes, original cleanup records and final result. It excludes
whole state/home/cache, raw app/framework, DerivedData, xcresult, arbitrary
report trees, credentials and raw shared event data. Export caps are:

- At most **96 logs**, at most 32 MiB each and 128 MiB combined.
- At most **64 metadata files** (including the manifest), at most 4 MiB each;
  **256 MiB** total including the manifest.
- At most **224 filesystem entries**, including empty directories, in the
  closed two-directory-level export structure.

The earlier planning note's illustrative 32-log ceiling did not account for
both controller and canonical copies. The reviewed candidate proposes 96;
this is an explicit policy change from that proposal, not measured output size.
Oversized originals are not truncated: they stay privately in the owned runner
work directory, the export fails, and no acceptance is claimed. Hosted runner
ephemerality is not durable private retention; such a run needs a new reviewed
retention plan before any retry requiring those unexported originals.

Every attempted/started canonical leaf's terminal receipt/stop/ownership is
audited independently of retention success, even when another start is malformed.
Before **any** cache/tool deletion, all seven original leaf members (including
both stop logs), original command captures, and the completed phases' metadata
must be retained byte-for-byte. Missing, oversized or changing originals and any
canonical finalization error latch unsafe; empty survivor lists cannot override
unknown stream/handle retirement. Incomplete evidence blocks deletion and export.
A fully finalized, uncancelled nonzero product exit is distinct from an
infrastructure failure: a known-safe productive prefix may export HOLD diagnostics
with actual `sourceAfter`. Unstarted phases alone may omit their evidence. Identity
normalization for failure export never converts dirty source to a PASS.
Successful cleanup removes only proved-owned outputs/tools/caches after their
required original metadata is retained. Post-return validation rechecks the
complete allowlist, hashes, source, commands, producer/nested mappings, fresh
path identity and actual cleanup absence, rather than trusting `result: PASS`.
HOLD undergoes the same command/leaf/capture checks for each attempted phase and
must prove original cleanup records and actual absence; a rehashed top-level HOLD
does not authorize incomplete evidence. A successful build without complete
product inspection remains an evidence hold, not a deletion/export permission.
The seal also checks each command's own cap, serial order, executable and
caller-owned output mode. Original output retention stays inside that command's
completion budget; late record writes or cancellation cannot grant a new window.
Upload success is part of the final job guard.

## Verification and continuation boundary

The focused controls are:

```bash
python3 -I -B -S scripts/tests/run-hosted-iphoneos-product-test.py
ruby scripts/tests/check-hosted-iphoneos-product-policy-test.rb
```

They are registered in `scripts/tests/release-workflow-test.sh`; the whole hook
is not an offline substitute and must not be run merely to execute these tests.
Offline parser/model tests establish routing and failure policy only. Genuine
runner admission, producer/download behavior, XcodeGen immutability, native
build/product inspection, retention sizes/timing, independent evidence review
and normal merge remain necessary before #327 closure. This route provides no
runtime, simulator, physical-device, signing, installation, release or whole-
audit readiness evidence. Dispatch/merge/closure remain coordinator decisions
after final review; preparation itself starts none of them.
