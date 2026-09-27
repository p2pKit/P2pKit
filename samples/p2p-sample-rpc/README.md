# Shared RPC examples and explicit capacity driver

**JVM/Android example compilation and unit tests passed; no capacity or physical
application run has occurred. Apple compilation remains pending.** This sample does not
ship production business logic, protected keys, a trust database, a pairing UI,
a permissive transport or an always-running mobile service. See the
[RPC quick start](../../docs/rpc/README.md),
[security/deployment guide](../../docs/rpc/security-and-deployment.md) and
[qualification contract](../../docs/rpc/qualification.md).

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
declarations in the final app, and own foreground lifecycle explicitly. A real
Swift consumer/link/provenance test remains pending. No framework binary is
checked in or claimed available.

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
application-owned security setup and test telemetry. No provider/key generation,
automatic pairing or insecure storage fallback is bundled. Provision the host
and clients through a separately reviewed local process before the experiment.

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
