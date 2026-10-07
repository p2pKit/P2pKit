# Shared RPC examples and explicit capacity driver

The interactive apps now share typed `users.get`, `items.list` and `message.send` examples and bounded
request-detail history. See [application parity work](../../docs/rpc/application-samples.md) for the APIs,
privacy boundaries and the still-open discovery/enrollment/reconnect work. This is not full feature completion.

For a hands-on phone test, follow the [manual Android ↔ iPhone steps](MANUAL-TESTING.md),
including where host approvals appear and how to copy safe diagnostics.

**Earlier source-bound example/JVM/Apple checks are recorded in the qualification
guide; they do not validate subsequently added phone apps or establish capacity.**
The new [foreground phone lab](phone-ios/README.md) supplies explicit Android
debug/iPhone test UIs and protected OS-backed synthetic approvals. The separate
[RPC lab record](../../docs/rpc/vps-lab-runtime-20260929.md) now records ten
actual supplemental Android API-24 controls, nine real Android shell-file checks,
nine earlier iPhone simulator XCTest methods and an unsigned
device build, each bound to its tested source. None establishes network
interoperability or capacity, and iPhone installation still needs owner signing.
The [Android mobile coordinator](../../docs/rpc/mobile-capacity.md) has offline
regression coverage and emulator shell integration; its first physical USB/LAN run remains required.
The [verified owner bundle](../../docs/rpc/device-testing-handoff.md) contains
source-matched Android APKs/JVM driver and explicit remaining prerequisites. The separate
[Mac27 checkpoint](../../docs/rpc/mac27-continuation-status.md) records completed
iPhone simulator resource/control tests; that source-bound result does not
establish physical USB qualification.
This sample ships no production business logic, private keys, permissive transport
or always-running mobile service. See the
[RPC quick start](../../docs/rpc/README.md),
[security/deployment guide](../../docs/rpc/security-and-deployment.md) and
[qualification contract](../../docs/rpc/qualification.md).

## Interactive Desktop RPC preview

```sh
./gradlew :p2p-sample-rpc:runRpcDesktopSample --console=plain
```

This opt-in JVM 17/Swing window uses the **real public `RpcPhoneLab` host/client**,
not the P2P Desktop UI or the 128-client capacity driver. It adds no dependency
and is not launched by `check`. The window displays its actual compiled source.
It is an English-only developer preview, not a localized production application.
Current execution scope is macOS; other desktop platforms remain unqualified.

**Known Desktop discovery blocker:** strict JmDNS discovery rejects any other UP, non-loopback
interface, including addressless or IPv6-only tunnels. The verified macOS adapter scopes **TCP only**;
it does not provide multicast socket scope. The current application reports this limitation from a fresh
read-only scan instead of implying that one eligible IPv4 suggestion proves discovery can start.
The transport retains its own independent checks. Supporting this topology requires adapter engineering,
not disabling interfaces, firewall, SIP or privacy protections. Host and Client discovery are both affected.

1. Unlock/create the persistent local encrypted RPC profile with a separate application passphrase,
   **not your computer login password**. Choose **Start host** or **Create client**. The application observes
   one eligible private LAN automatically and uses an OS-assigned listener port. It never changes routes
   or network/security settings. Ambiguous, unavailable or unsupported networking is an error, not a fallback.
2. A Client discovers advisory Host records. Select the intended device and explicitly confirm first-use
   trust, comparing fingerprints through a trusted channel. The Host must Approve that exact authenticated
   request or Reject it. A name, IP address or mDNS record does not grant trust.
3. After durable approval, only the explicitly selected saved host pin reconnects automatically, with
   bounded backoff and fresh discovery. Offline/ambiguous records do not select another host. An authenticated
   authorization rejection offers **Request approval again**; it never creates an automatic approval loop.
4. Call `users.get`, `items.list` or `message.send` from the editable forms/presets. Open **Request history**
   to inspect bounded payload previews, wire IDs, elapsed time and business/RPC outcomes. Counters update
   automatically. Echo is a diagnostic. Cancel does not roll back a remote effect or authorize unsafe replay.
5. Manage saved pins through **Trusted devices**. Stop closes the role but retains identity, trust and
   window-owned history. Window close closes the role before releasing the encrypted profile. Restart
   requires profile unlock, not identity replacement. History is memory-only; private request data is not
   automatically copied or exported. Failed cleanup prevents role replacement and preserves its evidence.

The profile is an owner-only, passphrase-encrypted POSIX file store, not an OS-backed Desktop keystore.
Windows storage is not implemented. See [application parity work](../../docs/rpc/application-samples.md)
for exact persistence and privacy boundaries. Existing invitation/capacity harnesses remain separate;
normal application screens use discovery, not the old invitation-first preview flow.

A second permitted, non-self endpoint is required to verify pairing and RPC. Two identities/windows on one
Mac cannot bypass the existing self-address rejection. Loopback/hairpin paths, ordinary emulator NAT,
merely sharing Wi-Fi or a USB connection are **not** interoperability evidence. The attempted same-Mac
application probe was invalid for that topology and never passed; its failure remains preserved.
The new explicitly authorized local advertising probe covers only one Host's start/advertise/Stop lifecycle,
not discovery delivery, approval, application responses or durable reconnection. Those gates remain open.
The [manual testing guide](MANUAL-TESTING.md) and [earlier preview checklist](testing-preview.md) describe
older invitation-based builds; they are not proof that the new discovery workflow has passed.

Focused owner, input-policy and store-lifetime regressions:

```sh
./gradlew :p2p-sample-rpc:jvmTest --tests 'dev.p2pkit.sample.rpc.desktop.*' --console=plain
```

## Inventory example: application-owned operations

[`InventoryContract.kt`](src/commonMain/kotlin/dev/p2pkit/sample/rpc/InventoryContract.kt)
contains serializable DTOs, a safe read descriptor, an **unsafe-to-replay** stock
reservation, a lightweight stock-changed notification and the
`InventoryApplication` interface. The application supplies authorization,
validation, stock storage, transactions and the meaning of a reservation receipt.

```kotlin
// Explicit role selection in the application: create one role, never both implicitly.
val host = RpcHost.create(platform, applicationScope) {
    appId = AppId("org.example.inventory.rpc")
    lan = applicationSelectedOrganizationLan
    trustStore = applicationLocalDurableTrustStore
    advertise = false
    inventory(applicationInventoryService)
}
host.start()
// Display a locally trusted invitation, then approve a specific pending device.
val invitation = host.pairing.createInvitation()
// host.pairing.approve(selectedRequest.id) is an administrator action, not automatic.
```

[`InventoryClient.kt`](src/commonMain/kotlin/dev/p2pkit/sample/rpc/InventoryClient.kt)
provides concrete read DTOs, pairing, connection and observation helpers. A
client connects only to a previously selected host pin; an uncertain reservation
must be reconciled through application state, not resubmitted automatically.
No notification implies a transaction commit or a completed RPC response.

```kotlin
val client = InventoryClient.create(platform, applicationScope, appId, lan, trustStore)
val host = client.pairFromTrustedQr(qrFromTrustedLocalUi)
client.connect(host)
val stock = client.readStock("SKU-123")
// Explicitly inspect businessError/infrastructureError/executionEvidence.
val observation = client.observeChanges { changed -> refreshThroughNormalRead(changed.sku) }
// When the application role ends:
observation.cancel()
client.close()
```

The sample has JVM/Android/iOS source targets. Its static `P2pKitRpcExample`
framework exposes a thin shared-Kotlin façade for an application-owned Swift UI,
not a replacement for the maintained P2P `P2pKitShared` sample framework. Keep
suspend errors/cancellation catchable, install the required LAN/Bonjour usage
declarations in the final app, and own foreground lifecycle explicitly. The
[scoped hosted compiler run](../../docs/rpc/hosted-validation.md) linked all three
Apple frameworks and typechecked the Swift fixture against their actual public
interfaces. This is not application/runtime, packaged-XCFramework or full consumer
qualification. No framework binary is checked in, uploaded or published.

[`RpcSwiftApiCheck.swift`](verification/RpcSwiftApiCheck.swift) is a compile-only
consumer fixture for pairing/connection, typed reads, unsafe reservations,
notifications, cleanup and typed error recovery. The feature-only hosted
`compile-apple` mode links the actual example frameworks and typechecks this
fixture without invoking it or publishing artifacts. A successful typecheck is
not a Swift application/lifecycle, physical-device or interoperability test.

The façade uses the application-owned Kotlin coroutine scope; callbacks are not
implicitly dispatched onto Swift's main actor. Also, cancelling a Swift `Task`
alone does not establish cancellation of an imported Kotlin suspend operation.
Own/cancel the shared Kotlin scope or an application cancellation bridge and
close the client explicitly when its role ends. Neither local nor remote
cancellation rolls back side effects or makes an uncertain reservation safe to replay.

## Capacity qualification source

[`RpcCapacityContract.kt`](src/commonMain/kotlin/dev/p2pkit/sample/rpc/RpcCapacityContract.kt)
fixes the approved workload and shared host façade. It requires **exactly 128**
durably trusted synthetic identities and registers only explicit trivial echo
procedures. String bodies use ASCII `a` data plus JSON quotes, so encoded sizes
are exactly 1,024 bytes or 1,048,576 bytes. They are not real application data.

[`RpcCapacityMain.kt`](src/jvmMain/kotlin/dev/p2pkit/sample/rpc/RpcCapacityMain.kt)
is a JVM driver with two separate modes:

- `--steady`: 128 independent client runtimes, 10 scheduled calls/second each,
  30 minutes, 1 KiB encoded bodies. At most eight outstanding calls/client;
  saturation/scheduler misses invalidate the experiment, not lower its rate.
- `--large`: one selected client, two concurrent calls, ten rounds of 1 MiB
  bodies. This is not peak-rate/overload/interoperability qualification.

Steady mode first completes a fixed, separately reported 600 real calls/client,
one outstanding/client and at least 100 ms between starts, within a 120-second
call-phase deadline. Any initialization failure prevents measurement. These
76,800 additional replies **never count toward** the subsequent full 30-minute /
2,304,000-response steady gate. This is not a cold-start guarantee; the earlier
cold-path permit-saturation failure remains recorded. See the
[same-host accounting contract](../../docs/rpc/same-host-lab.md).

Connections are established in batches of **two** so synthetic clients sharing
one source address do not bypass core's existing per-source pre-handshake gate.
Teardown is in bounded batches of 16. Responses/control remain prioritized over
notifications, with no durable call queue or automatic unsafe replay.

### Supply an owner-approved local environment

Implement [`RpcCapacityEnvironment`](src/jvmMain/kotlin/dev/p2pkit/sample/rpc/RpcCapacityEnvironment.kt)
in a separate application-owned local provider artifact and register exactly
one provider through Java `ServiceLoader` (`META-INF/services/` plus the
interface's qualified name). Supply:

1. Distinct protected `JvmSecureIdentityStore` instances for client indices
   0–127 and local durable per-client `RpcTrustStore` implementations.
2. The selected full host pin/endpoint and explicit organization CIDRs/interface/
   local address. Never encode secrets in command arguments or this repository.
3. A non-secret artifact/source manifest computed from the **actual** artifacts.
4. Fresh real-host CPU/RSS/thread/uptime and `RpcCapacityHost.snapshot()` data via
   an owner-approved **local test** integration. Driver measurements do not
   substitute for host measurements. Collection must be cancellation-cooperative.
5. Owned provider cleanup without deleting anyone else's identities or evidence.

The provider does not inject a transport into RPC. It supplies only the driver's
application-owned security setup and test telemetry. The opt-in `jvmLab`
compilation now supplies a synthetic-only provider, not part of the main sample
or library publication: 128 distinct generated client identities, encrypted
local vaults, explicit public-pin provisioning, strict organization-LAN factories
and host-process telemetry. It never automatically approves arbitrary peers.
The protected per-machine coordinator is
[`run-rpc-capacity-lab.py`](../../scripts/run-rpc-capacity-lab.py). It requires
native admission and a same-source `prepareRpcCapacityLab` artifact manifest;
control traffic may use the approved pinned SSH connection, but RPC traffic
still requires a direct, verified approved LAN path. No tunnel/interface/firewall
fallback is provided. Setup failures remove only owned synthetic vaults and
must not produce a capacity pass. See the qualification guide for actual runs.

### Execution requires separate authorization

`:p2p-sample-rpc:runRpcCapacity` is an explicit `JavaExec` task, **not** a dependency
of `check`, platform tests or any workflow. Its arguments must be exactly
`--owner-authorized-capacity-run --steady` or
`--owner-authorized-capacity-run --large`. The acknowledgement is a guardrail,
not permission. Before any run, obtain owner approval for the build/toolchain,
provider classpath integration, chosen real host, network, protected fixture
provisioning and local evidence destination. Do not use a shared hosted runner
without coordination. Do not download SDKs/dependencies under implementation-
only approval.

An application-owned Gradle init script can add the already-reviewed local
provider artifact to the task classpath for a later authorized run; keep its
machine-specific paths outside tracked source. No remote provider resolution is
needed for normal operation. Follow the repository's strict verification policy
for every actual build input; do not use flags that bypass it.

The driver checks exact completions and host counters, bounded sampling and
connection health, reports bounded latency histograms and sanitized counters,
and exits nonzero on mechanical failure. A zero exit prints
`PENDING_HOST_RESOURCE_REVIEW_AND_PHYSICAL_INTEROPERABILITY`; it means neither
performance qualification nor release readiness. Review resource time series,
post-retention cleanup, each real host platform and physical interoperability
as required by the [qualification guide](../../docs/rpc/qualification.md).

The tests `RpcSampleContractTest` and `RpcCapacityDriverTest` are deterministic
unit regressions, not a load-test pass. Release Foundation remains **NOT_READY**;
this sample changes none of its HOLDs or existing security/release gates.
