# Optional organization-LAN RPC

RPC is published as part of **`0.8.0-rc2`** under
`io.github.apdelrahman1911:p2p-rpc:0.8.0-rc2`. The
[release record](../releases/0.8.0-rc2.md) binds the actual combined-source hosted
checks, Maven publication and existing sample application artifacts.
This does not establish complete physical-LAN, protected-profile or installed-app
qualification. **Windows sample Host/Client remains unavailable**; see the
[Windows prerelease scope](windows-release-scope.md).

Earlier [implementation checks](implementation-status.md),
[same-host qualification](qualification.md) and the
[supplemental RPC lab record](vps-lab-runtime-20260929.md) retain their own exact
source/environment scopes. They are not substituted for current release evidence
or physical Android/iPhone hosting-capacity tests.

RPC is an optional usage model above P2pKit: an application explicitly chooses
one local host and connects several clients to it. Clients are dial-only; they
do not advertise, accept other clients, select a leader, forward requests, or
form a mesh. Both roles have JVM 17, Android API 24+, and iOS 14+ source targets.
Mobile hosting is foreground-first, not a promise of continuous background service.

## Architecture and reuse

The interactive Android, iOS and Desktop previews are being evolved together; see
[application sample parity work](application-samples.md) for shared typed procedures, bounded request
details and the still-open discovery/enrollment/reconnect gates.
See [preview app builds](preview-app-builds.md) for UI scope, downloadable artifacts and platform limitations. This does not supersede qualification holds.

```text
Application: schemas, authorization, handlers, business storage/transactions
                                  |
                               p2p-rpc
                                  |
                    p2p-core + p2p-transport-lan
                                  |
               existing Noise v2 / framing / TCP adapters
```

The façade owns a dedicated kit and its coroutine scopes. It does not accept
an arbitrary kit, raw socket, security engine, or transport injection. Existing
P2P callers keep their defaults unless they explicitly select the new generic
core/LAN profiles. Ordinary P2P and immutable published-release contracts are
not retroactively changed.

Source map:

- [RPC public API](../../library/p2p-rpc/src/commonMain/kotlin/dev/p2pkit/rpc)
  contains explicit descriptors, host/client façades, trust, pairing and errors.
- [RPC engines](../../library/p2p-rpc/src/commonMain/kotlin/dev/p2pkit/rpc/internal)
  own correlation, handler jobs, in-memory records, bounded JSON and message queues.
- [Core session profile](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/SessionProfile.kt)
  adds opt-in live authenticated admission, quarantine and shared payload leases.
- [Connection observations](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/SessionConnectionInfo.kt)
  expose generations and sanitized failures, not exception-string parsing.
- [Organization LAN policy](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/OrganizationLan.kt)
  and its platform adapters enforce the restrictions described in
  [security and deployment](security-and-deployment.md).

There is no new socket stack, alternate encryption, application ACK-based
transport, durable offline queue, database, transaction manager, remote class
loading, reflection-based invocation, or business synchronization framework.
Existing durable **file transfer is not durable RPC**; file-transfer paths are
disabled in the RPC-owned restricted session.

## Dependency and source-workspace integration

Use the matching published core/LAN/RPC version from Maven Central:

```kotlin
commonMain.dependencies {
    implementation("io.github.apdelrahman1911:p2p-rpc:0.8.0-rc2")
}
```

Within this repository, `:p2p-rpc` remains at `library/p2p-rpc` and its shared
sample code is `:p2p-sample-rpc` at `samples/p2p-sample-rpc`; project dependencies
are appropriate for source development. Do not mix newer source changes with
older published libraries. The historical `0.7.0-rc3` publication has no RPC
coordinate; its immutable artifacts are unchanged.

## Shared procedure contract

These examples use the descriptors and DTOs in the
[inventory sample](../../samples/p2p-sample-rpc/src/commonMain/kotlin/dev/p2pkit/sample/rpc/InventoryContract.kt).
Applications register each procedure explicitly; registration freezes at
runtime creation. Duplicate name/version pairs fail locally.

```kotlin
val readStock = RpcProcedure(
    name = "inventory.read-stock",
    version = 1,
    request = StockQuery.serializer(),
    response = StockReply.serializer(),
    applicationError = StockProblem.serializer(),
    retrySafety = RpcRetrySafety.Idempotent,
)
```

Use explicit `kotlinx.serialization` serializers on both ends. Names are
1–96 ASCII characters, beginning with a lowercase letter, followed by lowercase
letters, digits, dots or hyphens. Versions are 1–65,535. JSON is strict:
unknown keys, duplicate keys, excessive nesting and malformed values fail.
Change the procedure version for incompatible schema changes; register both
versions during an application-controlled migration. There is no automatic
schema negotiation or code generation.

## Platform wiring and host setup

Choose the platform factory in the corresponding platform source set:

```kotlin
// JVM: import dev.p2pkit.rpc.jvm
val platform = RpcPlatform.jvm(applicationProtectedIdentityStore)
// Android: RpcPlatform.android(applicationContext), import dev.p2pkit.rpc.android
// iOS: RpcPlatform.ios(), import dev.p2pkit.rpc.ios
```

JVM identity storage must implement the existing protected
`JvmSecureIdentityStore` contract. There is no plaintext or passwordless file
default. Android reuses Keystore-backed identity; iOS reuses device-only
Keychain identity. All roles require an application-owned **local durable**
`RpcTrustStore`; see [storage and pairing requirements](security-and-deployment.md).

```kotlin
val host = RpcHost.create(platform, applicationScope) {
    appId = AppId("org.example.inventory.rpc")
    lan = OrganizationLan(
        allowedSubnets = listOf("10.42.0.0/16"),
        interfaceName = applicationSelectedInterface,
        localAddress = applicationSelectedLocalAddress,
        listenPort = 45454,
    )
    trustStore = applicationLocalDurableTrustStore
    limits = RpcLimits.host128() // Policy bounds, NOT proven device capacity.
    advertise = false // Numeric fallback is sufficient; mDNS is optional.
    register(readStock, authorize = application::mayRead) { context, request ->
        application.read(context, request)
    }
}

// The app presents/request permissions; this API only reports requirements.
if (host.permissions.hasRequiredPermissions()) host.start()
val endpoint = host.endpoint()
```

Authorization defaults to **deny** if omitted. The authenticated
`RpcCallContext.peer` identifies the caller; do not trust a body-supplied user
or device identity. Authorization callbacks must be fast/cooperative.
Resource-specific validation, authorization, database transactions, and the
meaning of handler success remain application responsibilities.

## Enrollment and a typed client call

```kotlin
val invitation = host.pairing.createInvitation()
// Display invitation.qr ONLY through the trusted local administrator UI.
// Observe host.pairing.pending. The administrator selects a specific request:
host.pairing.approve(selectedRequest.id)
// Or host.pairing.reject(selectedRequest.id).
```

The client uses the same AppId, its own selected interface/local address,
and its own durable trust store:

```kotlin
val client = RpcClient.create(platform, applicationScope) {
    appId = AppId("org.example.inventory.rpc")
    lan = clientOrganizationLan
    trustStore = applicationLocalDurableTrustStore
}
val scanned = RpcInvitation.parse(qrFromTrustedLocalChannel)
val selectedHost = try { client.pair(scanned) } finally { scanned.clear() }
client.connect(selectedHost) // Fresh authenticated connection after approval.

try {
    when (val reply = client.call(readStock, StockQuery("SKU-123"))) {
        is RpcReply.Success -> displayStock(reply.value)
        is RpcReply.ApplicationError -> displayBusinessError(reply.error)
    }
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (failure: RpcFailure) {
    showInfrastructureState(failure.kind, failure.executionEvidence)
    // MayHaveExecuted requires reconciliation, not a fresh automatic submission.
}
```

`pair` pins the scanned AppId-bound host before transmitting the enrollment
secret and persists trust after the host administrator approves. Clear/dismiss
the host's invitation object when its local UI is finished too. Invitation
objects redact `toString`; the `qr` property is intentionally sensitive.
For an already provisioned host, construct `RpcSelectedHost` from its existing
durable pin and a new policy-checked `RpcEndpoint`; changing an address does not
authorize changing the identity. Discovery results are advisory, not trusted selection.

## Notifications and lifecycle

Register the same `RpcNotification<T>` descriptor in host and client
configuration with `notification(descriptor)`. Use
`client.notifications(descriptor)` for a typed local `Flow<T>` and
`host.tryNotify(peerFingerprint, descriptor, value)` to attempt delivery.
The host application decides which clients may receive each update.

Notifications are distinct from responses: bounded, best-effort, non-durable,
non-replayed, and with no remote subscription or streaming contract. `Enqueued`
means local acceptance, not remote receipt. An absent/slow subscriber can miss
events; reconcile important state through a normal procedure.

Observe `client.state`, `host.state`, `host.connections`, and `diagnostics`.
Counters have bounded shape and contain no payloads, invitation material or
automatic telemetry export. Host payload gauges refresh periodically; they
are policy-accounting snapshots, **not measured RSS**. Notification-drop counters
count local capacity/decoding refusals, not every subsequent network loss.

Close the façade and cancel application-owned collectors when the role/UI
ends. Parent-scope cancellation initiates owned cleanup. Repeated close can
reobserve retained core cleanup failures; a timeout is not evidence that native
work or a non-cooperative handler terminated. Recreate the façade to change
roles. See the [reliability contract](reliability.md),
[wire contract](protocol.md), and [sample instructions](../../samples/p2p-sample-rpc/README.md).
