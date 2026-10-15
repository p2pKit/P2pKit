# RPC security and organization-LAN deployment

**JVM/Android deterministic checks passed; platform/path/security qualification is pending.**
Read the [RPC overview](README.md), [reliability contract](reliability.md) and
[qualification requirements](qualification.md) before deployment. A private LAN
is not a trust boundary. Release Foundation remains **NOT_READY** and this
feature does not satisfy its HOLDs or external security gates.

## Explicit host, authenticated identities

The application selects one `RpcDiscoveredHost` with a current advisory discovery claim, or
one `RpcSelectedHost`: a full AppId-bound
`PeerFingerprint` plus a numeric `RpcEndpoint`. The full pin must already be in
the client's local durable trust store, or be acquired by the administrator
pairing workflow below. An address change is not permission to replace the pin.
Discovery names, IP addresses, abbreviated fingerprints and QR text received
from an untrusted channel are not proof of the intended host's identity.

Both directions reuse core authenticated-v2 Noise XX, X25519 identities and
ChaCha20-Poly1305 encrypted records. There is no alternate cryptographic
protocol, plaintext fallback, global accept-any admission or TLS/cloud service
requirement. A pin/authentication/protocol failure is terminal, not a reason to
try a weaker mode. Clients do not listen, advertise or connect to other clients.

JVM applications supply the existing protected `JvmSecureIdentityStore`;
Android reuses Keystore-backed identity; iOS reuses device-only Keychain
identity. Never ship the test fixtures or an in-memory/plaintext identity-store
default. Device identity is not a user login or business entitlement.

## Pairing is an administrator operation

1. A running host creates an invitation with a CSPRNG 128-bit invitation ID,
   **256-bit secret**, full host pairing QR and numeric endpoint. Lifetime is
   at most two minutes; at most four invitations/quarantine connections exist.
2. Display the QR through a trusted **local** UI/channel. Do not upload it,
   log it, put it in analytics, share it through a cloud-backed clipboard, or
   persist it as ordinary application data. Its `toString()` is redacted, but
   `qr` intentionally exposes the secret for display. Clear/dismiss invitation
   objects when finished; managed-runtime strings cannot be reliably erased.
3. The client validates AppId binding and LAN policy and pins that host **before**
   sending enrollment material through the encrypted connection.
4. The first valid proof binds the invitation to that authenticated client
   identity. Competing identities, expired/reused secrets and malformed proofs
   are rejected. A pending request is not an approved client.
5. A host administrator explicitly chooses `pairing.approve(request.id)` after
   verifying the requesting device through a trusted local process. Persist the
   host's trust grant before sending approval. `reject` destroys the invitation.
6. The client persists the host pin. Both sides then use a **fresh authenticated
   connection**. The original connection stays enrollment-only even after a
   durable grant; it cannot invoke procedures, read cached results, transfer
   files or receive notifications.

Lost approval replies/storage interruption can leave the two trust stores out
of sync. Report the failure and reconcile locally; do not assume the grant was
undone or disable authentication to recover. Re-pairing to the same verified
host can observe an already-durable host grant, then persist the missing local
pin. Pairing and connection timeouts are bounded, not proof of remote rollback.

### Opt-in nearby first-use approval

`allowNearbyPairing = true` additionally admits unknown authenticated peers **only** to bounded
quarantine. Clients explicitly select and confirm a full fingerprint before `requestApproval`;
hosts separately approve the authenticated client in their local UI. Without independent fingerprint
comparison this is informed trust-on-first-use, not the invitation's out-of-band secret assurance.
Discovery alone never approves either side. The old invitation flow and default configuration are unchanged.

Nearby requests use a distinct bodyless wire kind, four shared pending slots, 120-second non-renewable
expiry and a bounded 30-second rejection/expiry cooldown. Silent enrollment links also expire, and
closed nearby links cannot leave an actionable approval. Both sides persist trust before normal use,
then establish a fresh authenticated connection. See [wire details](protocol.md).

## Application-owned local durable trust

Implement `RpcTrustStore.load/replace` with atomic, integrity-protected local
security storage. Returning from `replace` must mean the replacement is durable;
do not start a later asynchronous write. Separate namespaces by AppId and
`RpcTrustPurpose` (`HostClients` versus `SelectedHosts`). The separate `SelectedHostPreference`
namespace stores the application's chosen reconnect target only; it is **never an authorization grant**.
Coordinate concurrent
processes externally. Protect access with OS permissions/secure storage, exclude
unapproved backup/synchronization, and never use cloud preferences or a remote
service as this store. RPC limits a loaded trust namespace to 4,096 entries.

`trust.revoke(pin)` denies new work and cached-result access immediately,
requests cancellation of active handlers and closes affected connections, then
persists revocation. A cleanup failure does not skip persistence. Storage failure
latches the runtime closed to admission; it is not reported as a persisted
success. Recreate only after the application has repaired/reconciled durable
state. Revocation cannot retract data already sent or undo business side effects.

For identity rotation, revoke the old pin, explicitly provision/pair the new
full identity through the trusted local administrator workflow, and reconnect.
Do not silently trust a new key at the same IP or discovery name. Manage lost
keys, application reinstalls, backups and trust-store recovery in the app.

## Enforced network policy

Every RPC runtime requires `OrganizationLan` with:

- 1–64 explicit RFC1918 IPv4 / IPv6 ULA CIDRs with zero host bits;
- an explicit OS interface name and a numeric local address in those CIDRs;
- an optional fixed listening port (zero asks the OS for an available port).

Public, loopback, link-local, multicast, mapped/scoped IPv6, ambiguous IPv4 and
hostname endpoints are rejected. There is no general DNS resolution in the
manual path. Known tunnel/VPN/peer-to-peer interface names are forbidden.
Binding failure or an unverifiable path fails closed; the SDK does not fall
back to the process-default route, cellular, a relay or another interface.

| Platform | Source enforcement and limitation |
| --- | --- |
| JVM 17 | Select and bind the exact local address; reject loopback/virtual/point-to-point interfaces and non-policy endpoints. Portable Java 17 cannot prove device-bound egress on a multihomed machine, so strict mode requires **one up non-loopback interface**. Extra active adapters, bridges, containers or VPNs cause refusal, even if ordinary P2P could use them. |
| Android | Select a Wi-Fi/Ethernet `Network` with `NOT_VPN` and matching interface/address; bind outgoing sockets and the host's unconnected listener descriptor to that Network, then bind the exact local address before listening. Accepted TCP children inherit the listener's network mark. Reject observed VPNs and revalidate the Network and numeric endpoints before/after I/O. No process binding, interface-name exemptions, hotspot/null-Network fallback or retry on another Network. |
| iOS | Require an actual selected Wi-Fi/wired `NWInterface` and numeric local endpoint; prohibit cellular, other/loopback and peer-to-peer/AWDL. Validate effective numeric local/remote endpoints and current path before traffic and on path changes. An opaque/unverifiable Bonjour connection is not used by strict mode. |

JVM/Android restricted connections recheck before/after I/O and poll idle paths
at 250 ms. iOS uses Network.framework path notifications plus I/O checks.
Reconnection repeats endpoint/path/authentication checks. These checks and OS
binding are not an instantaneous firewall or proof about upstream routing.
Network changes can close a connection and leave an already-sent call uncertain.
The Android listener uses public `Network.bindSocket(FileDescriptor)` and
`android.system.Os` APIs. Nonblocking descriptor operations retain ownership
through readiness waits; close gates new work and drains bounded waits before
releasing a descriptor. The original single-interface guard remains fail-closed
for unbound Java-socket checks; it is not replaced with a `dummy0` name allowlist.
After a selected local address/interface changes, close and explicitly recreate
the runtime with the new approved configuration rather than silently broadening it.

**Deployment assurance remains necessary.** A router may forward RFC1918/ULA
traffic through a private WAN/tunnel outside the organization. The SDK cannot
inspect upstream forwarding or defeat an administrator-compromised OS. Apply
managed routing/egress firewall rules that prohibit offsite forwarding, verify
the actual paths in an owner-approved network test, and repeat after policy
changes. The app, its trust-store/provider implementations, handlers and third-
party telemetry must also obey local-only requirements; RPC cannot sandbox
application code. No automatic telemetry export is introduced by the module.

## Enterprise connectivity and platform lifecycle

Use the same pin with an explicitly shared numeric host address and fixed TCP
port when enterprise networks filter mDNS. Disable host advertising and omit
client discovery in that deployment. Multicast does not cross most VLANs;
private routed VLAN TCP is permitted only within the approved CIDRs and firewall
policy. AP client isolation/firewalls must permit client-to-host TCP. Neither
fallback nor discovery creates a public relay or automatic host selection.

- **Android:** declare the base LAN permissions in the [platform setup](../../README.md#android).
  For apps targeting SDK 37+ on Android 17/API 37+, request the live
  `ACCESS_LOCAL_NETWORK` grant as documented there. Preflight `permissions`
  before starting/connecting, handle denial/revocation, and do not start prompt
  loops. Hosting is foreground-first; any allowed foreground service, user
  notification, battery policy and service shutdown belong to the application.
- **iOS 14+:** add `NSLocalNetworkUsageDescription`; when using Bonjour, declare
  the secure `_p2pkit2._tcp` service in `NSBonjourServices` as in the maintained
  [iOS sample configuration](../../samples/iosApp/project.yml). Permission is
  OS/user-controlled. No continuous background iOS server is promised. Sleep,
  suspension, termination and Wi-Fi roaming can disconnect callers. Maintain
  the documented [iOS build floor](../compatibility.md) in application binaries.
- **JVM:** use JDK 17, protected local identity storage and OS firewall rules.
  Check the strict multihoming restriction before selecting this host platform.

## Authorization, defensive processing and diagnostics

Procedure registration is explicit and frozen at runtime creation; missing
`authorize` callbacks deny access. Only registered name/version descriptors can
run. There is no executable code, reflection target or class name in a request.
Use the authenticated `RpcCallContext.peer`, then apply business/resource/user
checks in the handler. Trust grants transport admission, not every procedure.
Authorization is rechecked for new and retained results. Each authorization
callback has a five-second maximum wait; initial admission uses the shorter
remaining request budget. An exception or owned timeout denies access, never
grants it. If result authorization times out, the outcome remains eligible for
authorized status recovery within normal retention instead of pinning a
cooperative finalizer forever. Callbacks/handlers must cooperate with
cancellation; blocking application code is not isolated in a sandbox or forcibly
rolled back, and cannot be forcibly freed by this timeout.

Length limits precede large allocations. JSON preflight rejects duplicate keys,
malformed syntax, excessive depth/tokens/keys and trailing values. Core frames,
reassembly, application queues, RPC calls/cache and notifications have bounded
policy budgets; see [limits and overload behavior](reliability.md). Quarantine
also keeps the existing two-pre-handshakes-per-source and 16-global-handshake
protection. These bounds are not measured CPU/RSS guarantees or immunity to DoS.

Diagnostics expose typed states and bounded counters, not payloads, secret QR
material, raw exception text, SQL errors, credentials or automatic logs to an
external endpoint. The app may display full identities only where required for
local administrator decisions; keep them out of exported diagnostics. Failure
handling must preserve Kotlin cancellation and uncertainty rather than retry
non-idempotent business operations automatically.
