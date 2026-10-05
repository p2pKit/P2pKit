# Foreground RPC phone lab

This is a separate **test application**, not the existing P2P iOS sample, a
business server, or a capacity claim. The [RPC lab execution](../../../docs/rpc/vps-lab-runtime-20260929.md)
records ten actual supplemental API-24 controls, nine real Android shell-file
checks and nine earlier iPhone simulator XCTest methods,
plus the produced APKs/unsigned device app and exact source bindings. Consult the
[qualification record](../../../docs/rpc/qualification.md) for remaining gates.
An unsigned device build is **not an installable iPhone package**: physical
installation needs the owner's development team/signing and
device access. Never supply Apple credentials or provisioning material to Git.
The [device-testing handoff](../../../docs/rpc/device-testing-handoff.md) records
the verified owner bundle, matching prepared JVM driver, source/hash verification, safe Android installation
and the remaining physical-device checklist. An unsigned iPhone package still
requires owner signing. The [mobile USB coordinator candidates](../../../docs/rpc/mobile-capacity.md)
implement phone telemetry/control contracts but have not run on a physical USB
device. Same-host JVM results cannot substitute for actual mobile telemetry.
On official [Mac27/Xcode27](../../../docs/rpc/local-arm27-qualification.md), source
`77aed5dcf5a7c96980affb61f5e828dac7973320` passed **13 application-hosted unit methods
plus two UI methods**, including resources and sealed-file controls. Its unsigned
ARM64 app and matching JVM driver retain that exact source/artifact binding;
see the [verified checkpoint](../../../docs/rpc/mac27-continuation-status.md).
Do not rerun these completed simulator methods for unrelated changes. Real wired
CoreDevice behavior, signed installation, USB timing and physical resource series
remain unverified. The earlier nine-method result keeps its historical scope.

The shared [`RpcPhoneLab`](../src/commonMain/kotlin/dev/p2pkit/sample/rpc/RpcPhoneLab.kt)
registers only the two fixed synthetic echo procedures used by the capacity
contract. This Swift UI and the Android debug-only `RpcLabActivity` use the same
AppId, procedure descriptors, identity binding and trust semantics. Existing
P2P behavior, its launchers and the Android release dependency graph are unchanged.

## Simple iPhone setup

1. Join your authorized Wi-Fi and open **P2pKit RPC**. Review the detected local
   address, interface and private subnet, then tap **Use this Wi-Fi**. No CIDR,
   interface or IP typing is needed on an unambiguous private IPv4 Wi-Fi network;
   the host port defaults to `48123`. Detection reads the ordinary default path
   and this device's actual address/netmask; it does not assume `en0` or `/24`.
   Confirmation does **not** start RPC, trust a peer or prove multicast works.
   Leaving the app or changing the detected network clears confirmation; the
   active role is stopped and must be explicitly restarted. The shared strict
   LAN admission and original deadlines remain unchanged.
   If **Use this Wi-Fi** is disabled, the explanation beside it identifies the
   current failed check, pending observation, already-confirmed state or active
   RPC lifecycle. **Check Wi-Fi again** retires the old observer and passively
   re-reads the default path and addresses while idle. It clears Wi-Fi confirmation,
   not invitation/capacity inputs; it never starts RPC or changes network settings.
   **Wi-Fi check details** shows the app's path/transport, IPv4 availability,
   interface/address counts and numeric decoder errors without SSIDs or raw
   rejected addresses. A visible Wi-Fi icon or working internet is not proof that
   this app has an eligible private IPv4 Wi-Fi path. These observations are not
   persistent telemetry, a permission reset or a multicast test.
   **Advanced → Enter network settings manually** retains the original explicit
   CIDR/interface/address configuration for approved setups such as IPv6 ULA or
   routed private VLANs. Automatic setup refuses public, cellular/VPN, ambiguous,
   noncontiguous-mask and point-to-point candidates rather than guessing. Neither
   mode bypasses network permission or routing checks. Capacity and USB controls
   are optional and collapsed; leave them empty for ordinary pairing. Invalid
   setup displays **Cannot start RPC** and status beside the role buttons.
2. Start exactly one host. Create a two-minute, one-use invitation on its local
   administrator UI. Reveal it only on a trusted local display. The iPhone host
   can render a QR locally; these minimal test UIs accept invitation text and do
   not yet implement camera scanning. Transfer the synthetic invitation only
   through an approved **local** channel, never cloud chat, logs, synced
   clipboards or exported screenshots.
3. Tap **Start client** on the other iPhone (or create the other platform's
   client) and submit that host invitation. Starting a client does not connect it.
   On the host, refresh pending requests, verify the complete client fingerprint
   locally, then approve **that exact** request. Enrollment-only connections
   cannot invoke procedures. Reconnection requires the durable host pin and
   the same independently policy-validated numeric endpoint.
4. Tap **Send test message (1 KiB echo)**. The separate 20 × 1 MiB request/reply
   experiment at concurrency two is under **Reconnect or run a larger test**.
   The UI reports counts, elapsed time and typed
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

For the candidate iPhone USB flow, enter a **new** run label and press
**Prepare new USB slot (RPC stays stopped)**. This publishes the compiled source
and actual installed signed-executable hash, not trust or a listener. The Mac
coordinator copies bounded input and an exact name/length/SHA-256 seal into
staging names. The app alone validates and atomically creates canonical input;
raw `devicectl` copies are not assumed atomic or create-only. After coordination,
load the slot, review the network and all 128 pins, explicitly approve, then
start the host. Never reuse a label or overwrite an old slot. Stop/closed records
must prove native closure and pin retirement; retain the private files as evidence.
Real wired-device schema, transfer timing and signed-artifact matching remain
unverified until an owner-selected iPhone is available.

## Security and lifecycle

- iPhone identity uses the existing device-only OS store. Approval records use
  non-synchronizable, `WhenUnlockedThisDeviceOnly` Keychain items, scoped by
  AppId/purpose. Android approval records use an Android Keystore AES-GCM key
  and fsynced atomic files under `noBackupFilesDir`. Corrupt, inaccessible or
  missing-key records fail closed; ordinary UI actions never silently erase them.
- Wi-Fi suggestions require a separate local confirmation and are rechecked at
  confirmation and startup. Monitoring is retired off-foreground; callbacks from
  an old observation cannot configure a later session. No SSID/location access,
  probe packets, automatic trust or new network/security entitlement is added.
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

The iPhone XcodeGen source is `project.yml` here. Generate with the absolute
`samples/p2p-sample-rpc/build/phone-ios` directory as **both** `--project-root`
and `--project`, and the absolute `project.yml` path as `--spec`;
generated projects/plists must not replace tracked source. Both Xcode schemes
run [`check-xcframework.sh`](check-xcframework.sh), which invokes the existing
typed Gradle provenance task for the sample's **Debug** XCFramework, checks its
clean commit binding and refuses stale binaries. This lab build configuration
must be recorded for any future physical measurement.
When `P2PKIT_GRADLE_EXECUTOR` selects the native executor, also bind
`P2PKIT_PYTHON3` to the owner's absolute installed Python executable. The phone
runner does this automatically; Xcode's modified `PATH` must not select an
unrelated interpreter for the mandatory nested verifier.

[`run-rpc-phone-ios-controls.py`](../../../scripts/run-rpc-phone-ios-controls.py)
requires owner authorization, an admitted native owner, installed XcodeGen and
an explicit installed simulator runtime. It generates and checks the actual
project's framework/plist references and first establishes one **new** exact
simulator's cold readiness within the original bound, before compiling the
current-source XCFramework. It requires all six Swift ownership controls, the actual Keychain
round-trip/namespace/revocation/retirement control, the resource/Mach-right
retirement control, six private-file/sealed-input controls, and four UI controls.
The current **33-unit/4-UI** inventory includes rejection of LF/CRLF-suffixed run
labels before a USB slot is created, four input-feedback controls, and ten
Wi-Fi/setup regressions: real-mask derivation, unsafe/ambiguous address rejection,
explicit confirmation, changed/stale observations, manual-mode isolation,
startup revalidation, pre-factory Stop and actual monitor retirement. Five more
regressions cover exact path/address rejection reasons, candidate/reason consistency,
passive refresh, input preservation, retired callbacks and lifecycle guards. UI checks
require hidden technical fields on launch and immediately visible explanations
for unconfirmed Wi-Fi and empty manual setup on both role buttons, plus visible
Wi-Fi diagnostics and refresh without approval or role selection. These English
test-app screens do not claim a localized production UI. Earlier results do not
cover the new regressions; deterministic injected address tests do not qualify
physical Wi-Fi or multicast behavior.
The runner assesses individual actual xcresult methods
(no skips), prepares an **unsigned**
arm64 device app, hashes artifacts and verifies exact simulator Shutdown and
deletion of only the newly created device.
Native ownership finalization is an additional prerequisite for accepting its
result. Simulator results do not satisfy the separate supported-host matrix,
dedicated ARM cancellation gate, physical interoperability or capacity gates.

The real Keychain control must run in the application-hosted XCTest process.
An unbundled Kotlin/Native test executable has no application Keychain
entitlement (the observed OS status is `errSecMissingEntitlement`, `-34018`).
It is not a mocked/skipped passing Native test. The fixed synthetic-only Kotlin
control creates its own fresh namespace; it cannot select or erase the UI's
stable approvals. Failure of this required XCTest still fails the phone gate.

On Android, build both `:p2p-sample-android:assembleDebug` and
`:p2p-sample-android:assembleDebugAndroidTest` in one successful source-bound
producer. The app adds a separate **P2pKit RPC Lab** debug launcher.
[`run-rpc-android-controls.py`](../../../scripts/run-rpc-android-controls.py)
requires that finalized producer, an already installed API 24 x86_64 image and
the native executor. Installed SDK command-line tools and build-tools are also
required: `apkanalyzer` must inspect the **actual test APK**, including both
explicit instrumentation entries, before an emulator starts. AGP injects the
configured default into the first manifest entry, so the maintained API-37
runner must remain first and the supplemental RPC runner second; do not change
the maintained default or weaken the binary-manifest guard.

The supplemental driver creates a new software AVD with 2-GiB userdata and a
private loopback ADB server,
executes all ten explicit RPC/Keystore/Activity/resource/file controls, and verifies cleanup.
This does not replace the maintained API 37/24/25 ART suite, API 37 LAN-permission
gate or real Android hosting tests. No phone pass follows from merely installing
an APK or compiling JVM tests.

The produced Android APK is debug-signed. Do not silently uninstall an existing
sample, erase its approvals, or reuse production signing material if Android
rejects an update signed by a different test key. Use a fresh owner-approved
test device/profile or explicitly coordinate any data-destructive replacement.

Run logs, source/tool hashes, xcresults and app manifests stay in the newly owned
private evidence location. Share only reviewed sanitized summaries. All Release
Foundation **NOT_READY**, HOLDs and external gates remain unchanged.
