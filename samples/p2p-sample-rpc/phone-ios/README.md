# Foreground RPC phone lab

This is a separate **test application**, not the existing P2P iOS sample, a
business server, or a capacity claim. Source and tests are prepared; consult the
[qualification record](../../../docs/rpc/qualification.md) for actual executed,
source-bound results. An unsigned device build is **not an installable iPhone
package**: physical installation needs the owner's development team/signing and
device access. Never supply Apple credentials or provisioning material to Git.

The shared [`RpcPhoneLab`](../src/commonMain/kotlin/dev/p2pkit/sample/rpc/RpcPhoneLab.kt)
registers only the two fixed synthetic echo procedures used by the capacity
contract. This Swift UI and the Android debug-only `RpcLabActivity` use the same
AppId, procedure descriptors, identity binding and trust semantics. Existing
P2P behavior, its launchers and the Android release dependency graph are unchanged.

## Explicit local setup

1. Obtain the organization's approved private CIDRs, Wi-Fi interface, this
   device's numeric LAN address and fixed unprivileged host port. No role,
   interface, subnet or trusted host is selected automatically. Do not substitute
   a public address, cellular/VPN route or SSH tunnel for LAN acceptance.
2. Start exactly one host. Create a two-minute, one-use invitation on its local
   administrator UI. Reveal it only on a trusted local display. The iPhone host
   can render a QR locally; these minimal test UIs accept invitation text and do
   not yet implement camera scanning. Transfer the synthetic invitation only
   through an approved **local** channel, never cloud chat, logs, synced
   clipboards or exported screenshots.
3. Explicitly create the other device's client and submit that host invitation.
   On the host, refresh pending requests, verify the complete client fingerprint
   locally, then approve **that exact** request. Enrollment-only connections
   cannot invoke procedures. Reconnection requires the durable host pin and
   the same independently policy-validated numeric endpoint.
4. Run the single 1 KiB request/reply, then the separate 20 × 1 MiB request/reply
   experiment at concurrency two. The UI reports counts, elapsed time and typed
   infrastructure/execution evidence, never payload contents or raw exceptions.
   These small interactive experiments do not run the 30-minute workload.
5. Exercise explicit cancellation, Stop, restart, revoked trust and permission
   denial. A timeout, disconnect or cancellation may leave a remote outcome
   unknown and never authorizes an unsafe automatic replay.

The optional 128-pin import replaces this test host's approved synthetic-client
set **only after an explicit local administrator acknowledgement**. It requires
exactly 128 distinct well-formed public fingerprints, not private keys. Never
import production/custodian identities. Test provisioning and telemetry for a
physical capacity run still require the approved coordinator and actual
host-process measurements; filling this field is not a capacity test.

## Security and lifecycle

- iPhone identity uses the existing device-only OS store. Approval records use
  non-synchronizable, `WhenUnlockedThisDeviceOnly` Keychain items, scoped by
  AppId/purpose. Android approval records use an Android Keystore AES-GCM key
  and fsynced atomic files under `noBackupFilesDir`. Corrupt, inaccessible or
  missing-key records fail closed; ordinary UI actions never silently erase them.
- No process arguments, URLs/intents, preferences or logs configure peers or
  import invitations. No cloud endpoint or general DNS fallback is added.
- These are foreground-only apps. The active role prevents idle sleep, but
  switching apps, losing foreground, or locking the device closes the runtime
  and clears displayed invitation/import material. No background-server
  entitlement/service is claimed. Permission prompts may require selecting
  the role again after granting access.
- Swift retains the actual Kotlin cancellation handle. Cancelling a Swift
  `Task` alone is not enough. The run owner awaits late-created resources and
  native close, rejects new roles until cleanup finishes, and retains ownership
  after a failed close. Android likewise joins startup and closes late results.
- iOS obscures inactive app snapshots; unlike Android's `FLAG_SECURE`, it cannot
  generally prevent user screenshots. Treat the local administrator display
  accordingly. Immutable strings cannot promise guaranteed memory zeroization.
- iOS requires local-network permission. The maintained secure Bonjour
  declaration remains in the XcodeGen spec even though this lab does not
  advertise/discover. Android API 37 permission handling remains separate from
  older-API ART controls. Neither app requests firewall/security exceptions.

## Build and reproducible verification

Use an explicitly authorized, admitted native execution context with a clean
committed source candidate and the repository's strict locks/checksums. The
feature's public framework is not a downloaded or published substitute.

The iPhone XcodeGen source is `project.yml` here. Generate with the repository
as `--project-root` and `samples/p2p-sample-rpc/build/phone-ios` as `--project`;
generated projects/plists must not replace tracked source. Both Xcode schemes
run [`check-xcframework.sh`](check-xcframework.sh), which invokes the existing
typed Gradle provenance task for the sample's **Debug** XCFramework, checks its
clean commit binding and refuses stale binaries. This lab build configuration
must be recorded for any future physical measurement.

[`run-rpc-phone-ios-controls.py`](../../../scripts/run-rpc-phone-ios-controls.py)
requires owner authorization, an admitted native owner, installed XcodeGen and
an explicit installed simulator runtime. It generates the project, boots a
**new** exact simulator, runs all six Swift ownership and two UI controls,
assesses individual actual xcresult methods (no skips), prepares an **unsigned**
arm64 device app, hashes artifacts and verifies exact simulator Shutdown.
Native ownership finalization is an additional prerequisite for accepting its
result. Simulator results do not satisfy the separate supported-host matrix,
dedicated ARM cancellation gate, physical interoperability or capacity gates.

On Android, build both `:p2p-sample-android:assembleDebug` and
`:p2p-sample-android:assembleDebugAndroidTest` in one successful source-bound
producer. The app adds a separate **P2pKit RPC Lab** debug launcher.
[`run-rpc-android-controls.py`](../../../scripts/run-rpc-android-controls.py)
requires that finalized producer, an already installed API 24 x86_64 image and
the native executor. It creates a new software AVD/private loopback ADB server,
executes all eight explicit RPC/Keystore/Activity controls, and verifies cleanup.
This does not replace the maintained API 37/24/25 ART suite, API 37 LAN-permission
gate or real Android hosting tests. No phone pass follows from merely installing
an APK or compiling JVM tests.

Run logs, source/tool hashes, xcresults and app manifests stay in the newly owned
private evidence location. Share only reviewed sanitized summaries. All Release
Foundation **NOT_READY**, HOLDs and external gates remain unchanged.
