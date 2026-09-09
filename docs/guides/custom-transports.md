# Custom transport providers

The public transport SPI is for trusted in-process extensions. Application code
normally uses `P2pKit`, `Peer`, and `P2pSession`; provider code implements
[`TransportFactory`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/TransportFactory.kt),
[`DataTransport`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/DataTransport.kt),
and/or [`DiscoveryTransport`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/DiscoveryTransport.kt).
This guide describes obligations, not certification of arbitrary providers or
independent wire interoperability.

## Registration and lifecycle

Register the factory with `transports { register(factory) }` in the kit DSL.
The current API uses the existing `TransportKind` enum; it does not provide a
string-based kind registry. Do not register the same factory instance or kind
twice. Its stable `descriptor` declares `DATA`, `DISCOVERY`, or both. The kit
snapshots that descriptor during registration and checks that `build(context)`
returns exactly those paths with matching kinds. Static capability does not
mean permission, network reachability, or a negotiated peer feature.

| Phase | Provider obligation |
| --- | --- |
| Construction / `build` | Be resource-inert: no socket/listener, native handle, registered callback, or background I/O. Metadata getters are stable and side-effect free. A factory failure or contradictory pair becomes `TransportInitializationFailed`; do not rely on cleanup of an invalid, partly built pair. |
| Data `start()` | Acquire resources only here, publish success only when usable, and coalesce repeated/concurrent starts. Return ordinary startup failure as `Result.failure`; propagate caller cancellation rather than swallowing it in a successful result or retry. Discovery acquisition belongs to its corresponding `startAdvertising` / `startDiscovery`. |
| Operation | Keep `canConnect` fast and resource-inert. Preserve cancellation from `connect`. Bound accepted/queued work and native buffers; a core limit does not bound allocations made earlier by the provider. |
| Rollback / data `stop()` | Release startup resources, serialize against late startup, and remain restartable. Clean up partial startup even when the initiating coroutine was cancelled. Do not close streams already owned by sessions merely because the listener stops. |
| Discovery stop | Stop advertising and browsing independently and idempotently; fence late callbacks. The SPI has no separate discovery `close()`, so these stops must release their owned resources. A subsequent feature start may restart them while the kit remains live. |
| Data `close()` | Terminal and idempotent. Fence new starts and late publications as disposal begins; release owned resources even when read/write or another close races cleanup. A stopped kit is never restartable. |

The kit may subscribe to discovery events and incoming connections during
construction, before data `start()`. Those subscriptions must not themselves
bind listeners or start discovery. `incomingConnections()` has one active
collector, but collection may be restarted sequentially after a failure. Do not
permanently destroy its acceptance source merely because one collector ended.
Own accepted-but-not-delivered connections and close them on failed delivery or
listener disposal; handing a connection to the core transfers stream ownership.
A successful queue offer alone is not proof that a session took ownership.

Cleanup must preserve the original failure and account for retained resources.
Core bounds its cleanup attempts and reports failures; cancellation or a timeout
cannot forcibly stop a blocking native call. Do not treat a returned kit stop
or `Stopped` state as evidence that a broken provider released everything.
See the [lifecycle contract](../architecture/specification.md#lifecycle).

## Propagate the supplied security profile

The kit's `SecurityMode` selects the security engine. Authenticated v2 with
`RejectUnknown` is the default; failed authentication never falls back to v1.
`TransportContext.securityProfile` and `LocalPeerInfo.securityProfile` describe
that whole-kit choice. Their `LegacyPlaintextV1` constructor defaults exist for
source compatibility, **not as a provider policy or the kit default**. The kit
supplies both fields explicitly; never replace them with fresh default-valued
objects. Preserve the supplied full fingerprint along with the profile.

At `build(context)`, retain `context.securityProfile` and
`context.localFingerprint`. At `startAdvertising(localPeer)`, use the supplied
`localPeer.securityProfile` and `localPeer.fingerprint` in the advertised
namespace, protocol version, and metadata. If adapting that value, `copy()`
preserves both unless explicitly overridden. Reject inconsistent local input:
authenticated-v2 advertisements require a fingerprint; legacy advertisements
must not claim one. Do not derive the mode from an advertised remote record.

A concrete production example is
[`JvmLanTransportFactory.build`](../../library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDsl.kt):
it copies both fields into a resource-inert shared registration and returns data
and discovery transports. The LAN implementation's
[profile/metadata rules](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt)
keep `_p2pkit2._tcp`/version 2 separate from `_p2pkit._tcp`/version 1. These are
implementation examples, not internal types a custom provider should import.
Other media need an equivalent unambiguous profile mapping; they are not
required to use DNS-SD. Whole-kit profile is separate from optional features
negotiated by the encrypted HELLO exchange.

Discovery events are untrusted routing claims. Validate and bound them before
native callbacks publish them; do not label a discovered fingerprint as an
application pin. Neither a name, `AppId`, endpoint, nor claimed `PeerId`
authorizes a key. Core validates the event boundary, but cannot recover memory
already allocated by an unbounded native browser. Expiry and removal must match
the provider's documented discovery-lifetime policy.

## Raw stream and security ownership

[`RawConnection`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/RawConnection.kt)
is an ordered bidirectional byte stream, not an application message transport.
Preserve bytes and ordering across fragmented/coalesced reads and writes. The
core collects `read()` exactly once per connection; no competing collector may
steal, pre-consume, log, or reinterpret Noise handshake/record bytes. Implementing
the OS read inside that flow is necessary and is not a prohibited second reader.
Core establishes authenticated security before starting its protocol reader.

`close()` must be permanent, idempotent, and safe during cancellation or I/O
failure. Direct SPI users do not inherit the kit's handshake, keep-alive, and
session liveness policies automatically; they must own deadlines and cleanup.
Do not turn secure authentication/protocol rejection into recoverable transport
loss or implement a plaintext retry.

The provider, host application, logger, identity store, OS, and dependencies are
part of the trusted computing base. Selecting the engine in core does not
sandbox malicious extension code or protect process memory from it. Review
[the security model](../security/model.md), keep diagnostics free of secrets and
payloads, and verify lifecycle/ownership on each platform actually supported.
