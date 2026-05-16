# P2pKit — Kotlin Multiplatform P2P Data Transfer SDK

**Version:** 0.1 specification (with v0.2 planned design)
**Status:** Frozen — ready for implementation
**Last updated:** 2026-05-15

---

## 1. Project Overview

P2pKit is a Kotlin Multiplatform library that lets apps discover nearby devices, connect to them, and exchange text and binary messages — without forcing the developer to know about sockets, mDNS, Bluetooth, or platform-specific networking APIs.

The public API exposes peers, sessions, send, and receive. The library hides transport selection, framing, chunking, reconnection, and platform differences underneath.

P2pKit is **transport-agnostic by design**. v0.1 ships with a LAN/TCP transport. Future transports (BLE, Wi-Fi Direct, Apple Multipeer, Relay) plug in behind the same public API without breaking consumers.

---

## 2. Goals

- Provide a small, idiomatic Kotlin Multiplatform API for nearby-device communication.
- Keep the public API transport-agnostic. Developers should never see sockets, host/port, BLE service UUIDs, or platform networking types.
- Be honest about platform limits — surface `Unsupported` and `RequiresUserAction` rather than silently failing.
- Be modular. Each transport is a separate Gradle module so apps depend only on what they need.
- Use Kotlin coroutines and `Flow` / `StateFlow` everywhere. No callback-heavy APIs.
- Ship v0.1 quickly with Android + JVM desktop LAN support. Iterate from real usage, not speculation.

---

## 3. Non-Goals

- v0.1 will not include BLE, Wi-Fi Direct, Multipeer, or relay transports.
- v0.1 will not include iOS or macOS native support.
- v0.1 will not include encryption (`SecurityMode.NoneForMvp` only).
- v0.1 will not provide file transfer with resume semantics.
- The library will not request runtime permissions. The app is responsible for that.
- The library will not promise automatic LAN bring-up across platforms. Network provisioning is a v0.2 sidecar.

---

## 4. v0.1 Scope (must implement)

**Platforms**
- Android (API 24+, target latest stable)
- JVM desktop (Windows, Linux, macOS via JVM)

**Modules**
- `:p2p-core`
- `:p2p-transport-lan`
- `:p2p-sample-android`
- `:p2p-sample-desktop`

**Features**
- LAN peer discovery via mDNS (Android `NsdManager`, JVM `JmDNS`).
- TCP socket data transport.
- Send/receive `P2pMessage.Text` and `P2pMessage.Binary`.
- Outgoing connections via `connect(peer)`.
- Incoming connections via `incomingSessions` flow.
- Session lifecycle states.
- Internal protocol framing with HELLO handshake, DATA, ACK, PING/PONG, CLOSE, ERROR.
- Internal chunking for payloads larger than the configured chunk size.
- Configurable keepalive.
- Reconnect policy (disabled by default).
- Permission abstraction (`P2pPermissionManager`) — exposes required/missing permissions, never requests them.
- Typed errors (`P2pError`).
- Logger abstraction (no-op default).
- Lifecycle notifications (`notifyAppBackgrounded` / `notifyAppForegrounded`).
- Unit and loopback integration tests.

---

## 5. v0.2 Planned Scope (designed, not implemented in v0.1)

- `NetworkProvisioningManager` sidecar with Android `LocalOnlyHotspot` host support and Wi-Fi join helper.
- JVM desktop network state detection and manual IP fallback.
- iOS provisioning (join-only via `NEHotspotConfiguration`).
- Possibly: iOS LAN transport (Bonjour + `Network.framework`).

The provisioning API shape is locked in this spec under section 20. v0.2 implementation must conform to it.

---

## 6. Architecture Diagram

```
App
 ↓
P2pKit public API
 ├── NetworkProvisioningManager   (v0.2 sidecar — interface only in v0.1)
 ├── P2pPermissionManager         (sidecar)
 └── core pipeline:
     PeerRegistry / Discovery     ← aggregates DiscoveryTransport events
       ↓
     SessionManager               ← creates outgoing, accepts incoming
       ↓
     Protocol Layer               ← framing, chunking, ACK, keepalive
       ↓
     SecurityManager              ← NoOp in v0.1; encrypted in future
       ↓
     TransportManager             ← picks best DataTransport per peer
       ↓
     LAN Transport                ← mDNS + TCP (only transport in v0.1)
```

Provisioning sits **beside** the pipeline, not in it. The app uses it before discovery starts to help devices reach the same LAN. Discovery and transport never depend on provisioning.

---

## 7. Public API

### 7.1 Entry point

```kotlin
val p2p = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "Abdo Phone"

    transports {
        lan()
    }

    keepAlive {
        pingIntervalMillis = 10_000
        timeoutMillis = 30_000
    }

    lifecycle {
        reconnectPolicy = ReconnectPolicy.Disabled
        onBackground = BackgroundPolicy.CloseActiveSessions
        onAppKilled = AppKilledPolicy.NoPersistenceForMvp
    }

    security {
        mode = SecurityMode.NoneForMvp
    }

    logger = P2pLogger.NoOp
}
```

### 7.2 `P2pKit` interface

```kotlin
interface P2pKit {
    val state: StateFlow<P2pState>

    val peers: StateFlow<List<Peer>>
    val incomingSessions: SharedFlow<P2pSession>
    val sessions: StateFlow<List<P2pSession>>

    val permissions: P2pPermissionManager
    val networkProvisioning: NetworkProvisioningManager   // v0.2 — throws Unsupported in v0.1

    suspend fun startAdvertising()
    suspend fun stopAdvertising()

    suspend fun startDiscovery()
    suspend fun stopDiscovery()

    /**
     * Idempotent. If an active session exists for [peer]
     * (state in {Connecting, Handshaking, Connected, Reconnecting}),
     * the existing session is returned. Otherwise a new one is opened.
     *
     * Throws P2pError.NoTransportAvailable, P2pError.ConnectionFailed,
     * or P2pError.PermissionMissing.
     */
    suspend fun connect(peer: Peer): P2pSession

    fun lastSeen(peerId: PeerId): Long?   // epoch millis, null if unknown

    fun notifyAppBackgrounded()
    fun notifyAppForegrounded()

    suspend fun stop()

    companion object {
        fun create(block: P2pKitBuilder.() -> Unit): P2pKit
    }
}
```

### 7.3 `P2pSession` interface

```kotlin
interface P2pSession {
    val id: String
    val peer: Peer
    val state: StateFlow<ConnectionState>

    /**
     * Hot SharedFlow. replay = 0, extraBufferCapacity = 64,
     * onBufferOverflow = SUSPEND.
     *
     * Late subscribers will miss messages that arrived before they subscribed.
     * The expected pattern is to subscribe immediately after connect() / accept.
     */
    val incoming: SharedFlow<P2pMessage>

    /**
     * Safe to call from multiple coroutines. Writes are serialized internally
     * with a Mutex; frames will not interleave on the same connection.
     */
    suspend fun send(message: P2pMessage)

    suspend fun close()
}
```

### 7.4 DSL builder (sketch)

```kotlin
class P2pKitBuilder {
    var appId: AppId? = null
    var deviceName: String? = null
    var logger: P2pLogger = P2pLogger.NoOp

    fun transports(block: TransportsBuilder.() -> Unit)
    fun keepAlive(block: KeepAliveConfigBuilder.() -> Unit)
    fun lifecycle(block: LifecycleConfigBuilder.() -> Unit)
    fun security(block: SecurityConfigBuilder.() -> Unit)
}

class TransportsBuilder {
    fun lan()                              // v0.1
    // Future: fun ble(), wifiDirect(), multipeer(), relay()
}
```

### 7.5 Recommended usage pattern

```kotlin
val p2p = P2pKit.create { /* ... */ }
val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())

scope.launch {
    p2p.startAdvertising()
    p2p.startDiscovery()
}

p2p.peers
    .onEach { peers -> println("Current peers: $peers") }
    .launchIn(scope)

p2p.incomingSessions
    .onEach { session ->
        session.incoming
            .onEach { msg -> println("From ${session.peer.name}: $msg") }
            .launchIn(scope)
    }
    .launchIn(scope)

scope.launch {
    val peer = p2p.peers.first { it.isNotEmpty() }.first()
    val session = p2p.connect(peer)
    session.send(P2pMessage.Text("Hello"))
}
```

Never use nested `collect { collect { ... } }`. Always `launchIn(scope)`.

---

## 8. Internal Architecture

```
P2pKitImpl
 ├── PeerRegistry                — owns the public peers list
 ├── SessionManager              — creates/accepts/tracks sessions
 ├── TransportManager            — picks the best DataTransport per peer
 ├── P2pProtocol                 — framing, chunking, ACK, ping/pong
 ├── SecurityManager             — NoOp in v0.1; performs handshake
 ├── P2pPermissionManager        — platform-provided
 ├── NetworkProvisioningManager  — platform-provided (no-op in v0.1)
 └── P2pLogger                   — caller-provided
```

### 8.1 PeerRegistry

```kotlin
internal class PeerRegistry(
    private val discoveryTransports: List<DiscoveryTransport>,
    private val staleTimeoutMillis: Long = 15_000,
    private val scope: CoroutineScope,
    private val clock: () -> Long = { System.currentTimeMillis() }
) {
    private val tracked = MutableStateFlow<Map<PeerId, TrackedPeer>>(emptyMap())

    val peers: StateFlow<List<Peer>> = tracked
        .map { it.values.map(TrackedPeer::peer) }
        .stateIn(scope, SharingStarted.Eagerly, emptyList())

    fun lastSeen(peerId: PeerId): Long? = tracked.value[peerId]?.lastSeenAtMillis

    fun start() {
        discoveryTransports.forEach { transport ->
            transport.events.onEach(::apply).launchIn(scope)
        }
        scope.launch { evictLoop() }
    }

    private fun apply(event: PeerEvent) { /* mutate map */ }
    private suspend fun evictLoop() { /* periodic stale eviction */ }
}

internal data class TrackedPeer(val peer: Peer, val lastSeenAtMillis: Long)
```

### 8.2 SessionManager

Responsibilities:

- Initiate outgoing sessions on `connect(peer)`.
- Accept incoming raw connections from `DataTransport.incomingConnections()`.
- Run the protocol HELLO handshake on both sides.
- Validate the peer's `appId` matches local `appId` — reject otherwise.
- Wrap the connection with `SecurityManager.performHandshake()`.
- Emit accepted sessions on `incomingSessions`.
- Track active sessions in `sessions`.
- Apply `ReconnectPolicy` on failure.
- Close cleanly on `stop()`.

### 8.3 TransportManager

```kotlin
internal class TransportManager(
    private val transports: List<DataTransport>
) {
    fun selectBestTransport(peer: InternalPeer): DataTransport {
        return transports
            .filter { it.canConnect(peer) }
            .maxByOrNull { it.priority }
            ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
    }
}
```

---

## 9. Core Models

### 9.1 Identity

```kotlin
@JvmInline value class AppId(val value: String)
@JvmInline value class PeerId(val value: String)
```

`PeerId` is generated on first launch and persisted (Android: `DataStore` or `SharedPreferences`; JVM: file under user app data). It survives app restarts but may be lost on uninstall.

### 9.2 Peer (public)

```kotlin
data class Peer(
    val id: PeerId,
    val name: String,
    val platform: Platform,
    val supportedTransports: Set<TransportKind>
)

enum class Platform {
    ANDROID, JVM_DESKTOP, IOS, MACOS, WINDOWS, LINUX, UNKNOWN
}

enum class TransportKind {
    LAN, BLE, WIFI_DIRECT, MULTIPEER, RELAY
}
```

`Peer` is stable across heartbeats. Last-seen time is exposed via `P2pKit.lastSeen(peerId)`.

### 9.3 Internal peer (not exposed)

```kotlin
internal data class InternalPeer(
    val publicPeer: Peer,
    val transportHints: List<TransportHint>
)

internal data class TransportHint(
    val type: TransportKind,
    val host: String? = null,
    val port: Int? = null,
    val metadata: Map<String, String> = emptyMap()
)

internal data class LocalPeerInfo(
    val peerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    val appId: AppId,
    val supportedTransports: Set<TransportKind>
)
```

### 9.4 Messages (public)

```kotlin
sealed class P2pMessage {
    data class Text(
        val value: String,
        val metadata: Map<String, String> = emptyMap()
    ) : P2pMessage()

    data class Binary(
        val bytes: ByteArray,
        val metadata: Map<String, String> = emptyMap()
    ) : P2pMessage() {
        override fun equals(other: Any?): Boolean { /* content equality */ }
        override fun hashCode(): Int { /* content-based */ }
    }
}
```

No `FileChunk` in the public API. Chunking is internal.

**Max payload size for v0.1:** 4 MB per `send()` call. Larger payloads throw `P2pError.PayloadTooLarge`. File/stream APIs are v0.2+.

### 9.5 States

```kotlin
sealed class P2pState {
    data object Idle : P2pState()
    data object Starting : P2pState()
    data object Running : P2pState()
    data object Stopping : P2pState()
    data object Stopped : P2pState()
    data class Failed(val error: P2pError) : P2pState()
}

enum class ConnectionState {
    Idle, Connecting, Handshaking, Connected, Reconnecting, Closing, Closed, Failed
}
```

### 9.6 Config types

```kotlin
data class KeepAliveConfig(
    val pingIntervalMillis: Long = 10_000,
    val timeoutMillis: Long = 30_000
)

sealed class ReconnectPolicy {
    data object Disabled : ReconnectPolicy()
    data class Enabled(val maxAttempts: Int, val retryDelayMillis: Long) : ReconnectPolicy()
}

sealed class BackgroundPolicy {
    data object CloseActiveSessions : BackgroundPolicy()
    data object KeepRunning : BackgroundPolicy()   // app must run a foreground service
}

sealed class AppKilledPolicy {
    data object NoPersistenceForMvp : AppKilledPolicy()
}

sealed class SecurityMode {
    data object NoneForMvp : SecurityMode()
    // Future: PairingCode, QrCode
}
```

---

## 10. Session Behavior

- `connect(peer)` is **idempotent**. If a session exists with state in `{Connecting, Handshaking, Connected, Reconnecting}`, the existing instance is returned. Otherwise a new one is created.
- `P2pSession.send` is **safe under concurrent calls**. Writes are serialized via an internal `Mutex`.
- `P2pSession.incoming` is a **hot `SharedFlow`** with `replay = 0`, `extraBufferCapacity = 64`, `onBufferOverflow = SUSPEND`. Subscribe immediately after `connect()` or accept — late subscribers miss earlier messages.
- `close()` transitions: `Connected → Closing → Closed`. ACK/keepalive stops, underlying connection releases.
- A failed session emits `Failed` and is removed from `sessions` (after retention or immediately, see below).
- If `ReconnectPolicy.Enabled` is configured, the session transitions to `Reconnecting` and retries up to `maxAttempts` with `retryDelayMillis` between attempts. On exhaustion it becomes `Failed`.
- Closed/Failed sessions are removed from `P2pKit.sessions` after they emit their terminal state.

---

## 11. Discovery Behavior

### 11.1 Contract

```kotlin
interface DiscoveryTransport {
    val type: TransportKind
    val events: Flow<PeerEvent>

    suspend fun startAdvertising(localPeer: LocalPeerInfo)
    suspend fun stopAdvertising()
    suspend fun startDiscovery()
    suspend fun stopDiscovery()
}

internal sealed class PeerEvent {
    data class Found(val peer: InternalPeer) : PeerEvent()
    data class Updated(val peer: InternalPeer) : PeerEvent()
    data class Lost(val peerId: PeerId) : PeerEvent()
}
```

### 11.2 Rules

- Discovery is scoped by `AppId`. Peers advertising a different `AppId` are filtered out before reaching the registry.
- Peer updates with the same `PeerId` replace the existing tracked peer.
- A peer is evicted from the registry after `staleTimeoutMillis` (default 15s) without a refresh.
- The public `peers: StateFlow<List<Peer>>` only emits when the set of peers or their identifying fields change. Heartbeats alone do not trigger emissions because `lastSeen` is tracked separately.

---

## 12. Transport Behavior

### 12.1 Contract

```kotlin
interface DataTransport {
    val type: TransportKind
    val priority: Int

    fun canConnect(peer: InternalPeer): Boolean
    suspend fun connect(peer: InternalPeer): RawConnection
    fun incomingConnections(): Flow<RawConnection>
    suspend fun close()
}

interface RawConnection {
    val state: StateFlow<ConnectionState>
    suspend fun write(bytes: ByteArray)
    fun read(): Flow<ByteArray>
    suspend fun close()
}
```

### 12.2 Selection

`TransportManager.selectBestTransport(peer)` filters transports by `canConnect(peer)` and picks the one with the highest `priority`. v0.1 has only LAN. Future transports will set priorities so that the cheapest/most-reliable option wins automatically.

---

## 13. Protocol Framing

### 13.1 Packet types

```kotlin
internal enum class PacketType(val code: Byte) {
    HELLO(0x01),
    DATA(0x02),
    ACK(0x03),
    PING(0x04),
    PONG(0x05),
    ERROR(0x06),
    CLOSE(0x07)
}
```

### 13.2 Frame layout

```
| magic (4 bytes)         | 'P' 'P' '2' 'K'  = 0x50 0x50 0x32 0x4B
| version (1 byte)        | currently 0x01
| type (1 byte)           | PacketType code
| flags (1 byte)          | bit 0 = needs ACK
|                         | bit 1 = last chunk in sequence
|                         | bit 2 = is text payload
|                         | bits 3-7 reserved (must be 0)
| reserved (1 byte)       | must be 0
| message_id (16 bytes)   | UUID; same id for all chunks of one message
| chunk_index (4 bytes)   | big-endian uint32
| total_chunks (4 bytes)  | big-endian uint32
| payload_len (4 bytes)   | big-endian uint32; length of payload that follows
| payload (variable)      | up to payload_len bytes
```

Fixed header = 36 bytes. Payload follows immediately.

### 13.3 HELLO payload

JSON-encoded:

```json
{
  "appId": "com.example.transfer",
  "peerId": "5b3c...",
  "deviceName": "Abdo Phone",
  "platform": "ANDROID",
  "supportedTransports": ["LAN"],
  "protocolVersion": 1
}
```

Both sides exchange HELLO before any DATA. If `appId` doesn't match the local config, the receiver sends `ERROR` and closes. If `protocolVersion` major is different, the receiver sends `ERROR` and closes.

### 13.4 Chunking

- Default chunk size: 64 KB.
- A message larger than the chunk size is split. All chunks share `message_id`. `chunk_index` starts at 0. `total_chunks` is set in every frame for that message. The final chunk has `flags & LAST_CHUNK == 1`.
- The receiver reassembles by `message_id`. Reassembly state has a timeout (default 60s) to prevent memory leaks from incomplete messages.

### 13.5 ACK

- A DATA frame with `flags & NEEDS_ACK == 1` triggers an ACK.
- The ACK frame carries the same `message_id` and `chunk_index` in its header; payload is empty.
- v0.1 default: per-chunk ACK is **off** (TCP already guarantees delivery). The plumbing exists for future non-reliable transports.

### 13.6 Protocol interface

```kotlin
internal interface P2pProtocol {
    suspend fun send(connection: RawConnection, message: P2pMessage)
    fun receive(connection: RawConnection): Flow<P2pMessage>
}
```

---

## 14. KeepAlive Behavior

- Every `pingIntervalMillis` (default 10s), each side sends a `PING`.
- Receivers reply with `PONG` immediately.
- If no `PONG` is observed within `timeoutMillis` (default 30s), the session transitions to `Failed` (or `Reconnecting` if policy is enabled).
- PING/PONG carries no payload.

---

## 15. Permission Handling

### 15.1 Interface

```kotlin
interface P2pPermissionManager {
    suspend fun requiredPermissions(): List<P2pPermission>
    suspend fun missingPermissions(): List<P2pPermission>
    suspend fun hasRequiredPermissions(): Boolean
}

enum class P2pPermission {
    LocalNetwork,
    NearbyWifiDevices,
    Bluetooth,
    Location,
    WifiState,
    ChangeWifiState
}
```

### 15.2 Rules

- Only **runtime** permissions appear in `P2pPermission`. Install-time permissions (`INTERNET`, `ACCESS_NETWORK_STATE`) are documented in the README, not surfaced here.
- The library **never requests** permissions. The app must request them.
- `startAdvertising()` and `startDiscovery()` throw `P2pError.PermissionMissing` if any required runtime permission is absent.

### 15.3 v0.1 platform mappings

| Platform | Required at runtime |
|---|---|
| Android (LAN only) | none for plain LAN/mDNS on most versions; document `NearbyWifiDevices` if discovery requires it on the device's API level |
| JVM desktop | none |

---

## 16. Lifecycle Behavior

### 16.1 Notifications

```kotlin
fun notifyAppBackgrounded()   // non-suspending, fire-and-forget
fun notifyAppForegrounded()   // non-suspending, fire-and-forget
```

Calling either method posts to an internal channel; a worker coroutine applies the configured policy.

### 16.2 v0.1 default behavior

- **Android backgrounded** (with default `BackgroundPolicy.CloseActiveSessions`):
  - Active sessions are closed.
  - Advertising and discovery stop.
  - `P2pState` becomes `Stopped`.
  - No background transfer guarantee.
- **JVM desktop minimized/backgrounded:**
  - No special action. The library keeps running.
- **App foregrounded:**
  - The app must re-call `startAdvertising()` and `startDiscovery()`. v0.1 does **not** auto-restart.
  - If `ReconnectPolicy.Enabled`, sessions that were `Reconnecting` continue retry. Sessions that were `Closed` do not auto-reopen.
- **Process death:**
  - All sessions are lost. `PeerId` persists; everything else is rebuilt fresh.

### 16.3 Network change handling

If the underlying socket dies due to a network change (Wi-Fi → mobile data, network switch, etc.):

- The session emits `Failed` immediately.
- If `ReconnectPolicy.Enabled`, the session enters `Reconnecting` and retries.
- Discovery does **not** automatically restart in v0.1. The app should observe `P2pState` / `permissions` and re-invoke discovery as needed.

---

## 17. Error Handling

```kotlin
sealed class P2pError(message: String? = null) : Exception(message) {
    data class NoTransportAvailable(val peer: Peer) :
        P2pError("No transport available for peer: ${peer.id.value}")

    data class ConnectionFailed(val reason: String) : P2pError(reason)

    data class ProtocolError(val reason: String) : P2pError(reason)

    data class PermissionMissing(val permissions: List<P2pPermission>) :
        P2pError("Missing permissions: $permissions")

    data class PayloadTooLarge(val maxBytes: Long, val actualBytes: Long) :
        P2pError("Payload too large: $actualBytes > $maxBytes")

    data class HandshakeRejected(val reason: String) : P2pError(reason)

    data class VersionMismatch(val localVersion: Int, val remoteVersion: Int) :
        P2pError("Protocol version mismatch: local=$localVersion remote=$remoteVersion")
}
```

Fallback rules:

- Unknown packet type → ignored; logged at warn level. Does not close the session.
- Unknown peer capability → peer is still discovered; transports just skip it.
- `appId` mismatch during HELLO → `HandshakeRejected`, session closes.
- Protocol major version mismatch → `VersionMismatch`, session closes.

---

## 18. Security Abstraction

### 18.1 Interfaces

```kotlin
interface SecurityManager {
    suspend fun performHandshake(connection: RawConnection, peer: Peer): SecureConnection
}

internal interface SecureConnection : RawConnection {
    val peerIdentity: PeerIdentity
}

data class PeerIdentity(
    val peerId: PeerId,
    val publicKeyFingerprint: String?   // null under SecurityMode.NoneForMvp
)
```

### 18.2 v0.1 implementation

`NoOpSecurityManager` returns a passthrough wrapper. No keys, no encryption.

### 18.3 Future shape (v0.3+, not in v0.1)

```kotlin
sealed class SecurityMode {
    data object NoneForMvp : SecurityMode()
    data class PairingCode(val trustedDeviceStore: TrustedDeviceStore) : SecurityMode()
    data class QrCode(val trustedDeviceStore: TrustedDeviceStore) : SecurityMode()
}

interface TrustedDeviceStore {
    suspend fun trust(peerId: PeerId, fingerprint: String)
    suspend fun isTrusted(peerId: PeerId, fingerprint: String): Boolean
    suspend fun forget(peerId: PeerId)
}
```

Encryption primitives planned: X25519 key exchange, HKDF, AES-GCM or ChaCha20-Poly1305.

The public API does not need to change to add encryption. `SecurityManager.performHandshake` is the extension point.

---

## 19. LAN Transport Details

### 19.1 Module: `:p2p-transport-lan`

Two cooperating internal classes share a `LanServiceRegistration`:

```kotlin
internal class LanServiceRegistration(
    val appId: AppId,
    val localPeerId: PeerId,
    val tcpPort: Int,
    val deviceName: String,
    val platform: Platform
)

internal class LanDiscoveryTransport(
    private val registration: LanServiceRegistration
) : DiscoveryTransport

internal class LanDataTransport(
    private val registration: LanServiceRegistration
) : DataTransport

fun TransportsBuilder.lan() {
    val registration = /* built when P2pKit starts */
    register(LanDiscoveryTransport(registration))
    register(LanDataTransport(registration))
}
```

### 19.2 mDNS

- Service type: `_p2pkit._tcp.`
- TXT record fields:
  - `pid` — peer id
  - `app` — app id
  - `name` — device name (URL-encoded)
  - `plat` — `ANDROID` / `JVM_DESKTOP` / etc.
  - `caps` — comma-separated `TransportKind` values
  - `pv` — protocol version (currently `1`)
- Android: `NsdManager` for both advertising and discovery.
- JVM: `JmDNS` (jmdns library) for both advertising and discovery.

### 19.3 TCP

- Server: each device listens on an ephemeral port at startup; the chosen port is advertised in the mDNS service.
- Client: connects to the peer's advertised host:port.
- Reads and writes are framed by the protocol layer (section 13).
- Sockets close on session close.

### 19.4 Loopback testing

JVM tests must be able to run two `P2pKit` instances in the same process on `127.0.0.1` with different ephemeral ports and different `PeerId`s. The advertising/discovery, framing, and TCP code paths must all be exercisable in-process.

---

## 20. Network Provisioning Planned Design (v0.2)

**Status:** API shape locked. Implementation deferred to v0.2.

### 20.1 Manager interface

```kotlin
interface NetworkProvisioningManager {
    val state: StateFlow<NetworkProvisioningState>
    val networkState: StateFlow<NetworkState>
    val events: Flow<NetworkProvisioningEvent>

    suspend fun startLocalNetwork(config: LocalNetworkConfig = LocalNetworkConfig()): LocalNetworkResult
    suspend fun stopLocalNetwork()

    suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult

    suspend fun getManualConnectionInfo(): ManualConnectionInfo?

    @ExperimentalP2pApi
    suspend fun createManualPeer(host: String, port: Int): Peer
}
```

In v0.1, the implementation throws `Unsupported` from every method.

### 20.2 States and results

```kotlin
sealed class NetworkProvisioningState {
    data object Idle : NetworkProvisioningState()
    data object StartingLocalNetwork : NetworkProvisioningState()
    data object LocalNetworkRunning : NetworkProvisioningState()
    data object JoiningNetwork : NetworkProvisioningState()
    data object JoinedNetwork : NetworkProvisioningState()
    data object StoppingLocalNetwork : NetworkProvisioningState()
    data class Failed(val error: NetworkProvisioningError) : NetworkProvisioningState()
}

sealed class NetworkState {
    data object Unknown : NetworkState()
    data object NoNetwork : NetworkState()
    data class ConnectedToWifi(
        val ssid: String?,                       // null when OS hides it without location permission
        val localIpAddresses: List<String>
    ) : NetworkState()
    data class ConnectedToEthernet(val localIpAddresses: List<String>) : NetworkState()
    data class LocalNetworkHosted(
        val credentials: WifiCredentials?,       // may be null on OEMs that don't expose it
        val localIpAddresses: List<String>
    ) : NetworkState()
}

sealed class LocalNetworkResult {
    data class Started(
        val credentials: WifiCredentials,
        val manualConnectionInfo: ManualConnectionInfo?
    ) : LocalNetworkResult()

    data class StartedWithoutCredentials(
        val manualConnectionInfo: ManualConnectionInfo
    ) : LocalNetworkResult()

    data class RequiresUserAction(val instruction: String) : LocalNetworkResult()
    data class Unsupported(val reason: String) : LocalNetworkResult()
    data class Failed(val error: NetworkProvisioningError) : LocalNetworkResult()
}

sealed class JoinNetworkResult {
    /** Request accepted; observe `events` for the final Joined/Failed outcome. */
    data object Pending : JoinNetworkResult()
    data class Joined(val networkState: NetworkState) : JoinNetworkResult()
    data class RequiresUserAction(val instruction: String) : JoinNetworkResult()
    data class Unsupported(val reason: String) : JoinNetworkResult()
    data class Failed(val error: NetworkProvisioningError) : JoinNetworkResult()
}

sealed class NetworkProvisioningEvent {
    data class LocalNetworkStarted(val credentials: WifiCredentials?) : NetworkProvisioningEvent()
    data object LocalNetworkStopped : NetworkProvisioningEvent()
    data class NetworkJoined(val state: NetworkState) : NetworkProvisioningEvent()
    data class UserActionRequired(val instruction: String) : NetworkProvisioningEvent()
    data class Failed(val error: NetworkProvisioningError) : NetworkProvisioningEvent()
}
```

### 20.3 Credentials and connection info

```kotlin
data class WifiCredentials(
    val ssid: String?,
    val password: WifiPassword?,
    val securityType: WifiSecurityType
)

@JvmInline
value class WifiPassword(private val value: String) {
    fun reveal(): String = value
    override fun toString(): String = "***"   // never log the password
}

enum class WifiSecurityType { OPEN, WPA2, WPA3, UNKNOWN }

data class ManualConnectionInfo(
    val hostAddresses: List<String>,
    val port: Int,
    val appId: AppId,
    val peerId: PeerId,
    val deviceName: String
)

data class LocalNetworkConfig(
    val preferredSsidPrefix: String? = null   // hint only; OS may ignore
)

sealed class NetworkProvisioningError : P2pError() {
    data class PlatformError(val cause: Throwable) : NetworkProvisioningError()
    data class PermissionMissingForProvisioning(val permissions: List<P2pPermission>) : NetworkProvisioningError()
    data class HotspotStopped(val reason: String) : NetworkProvisioningError()
    data class JoinFailed(val reason: String) : NetworkProvisioningError()
}
```

### 20.4 DSL

```kotlin
P2pKit.create {
    // ...
    networkProvisioning {
        enableLocalHotspot = true
        enableWifiJoin = true
        enableManualIpFallback = true
    }
}

data class NetworkProvisioningConfig(
    val enableLocalHotspot: Boolean = false,
    val enableWifiJoin: Boolean = false,
    val enableManualIpFallback: Boolean = true
)
```

### 20.5 QR Wi-Fi credential format

The standard `WIFI:` URI:

```
WIFI:T:WPA;S:<ssid>;P:<password>;;
```

Apps can render any QR encoder over this string. Most camera apps and password managers can scan it natively.

### 20.6 Manual connection flow

If discovery fails, the app may call `createManualPeer(host, port)` to produce a synthetic `Peer`. The app then calls `p2p.connect(peer)` as usual. The host/port pair only lives inside `ManualConnectionInfo` / `createManualPeer` — it never leaks elsewhere.

---

## 21. Platform Limitations

### 21.1 Promises the library makes

- LAN discovery and TCP transport work on Android and JVM desktop where mDNS and TCP are not blocked.
- The library does not silently swallow platform restrictions — it returns `Unsupported`, `RequiresUserAction`, or throws `P2pError`.

### 21.2 Promises the library does NOT make

- It does **not** claim to put devices on the same LAN automatically.
- It does **not** claim Wi-Fi Direct works between all platforms.
- It does **not** claim BLE is suitable for large file transfer.
- It does **not** claim iOS apps can create hotspots programmatically.
- It does **not** claim silent Wi-Fi join on Android. User confirmation is often required.
- It does **not** claim mDNS works on every network. Corporate, guest, and some mobile networks block it.

### 21.3 Per-platform v0.1 reality

| Platform | Discovery | Transport | Provisioning |
|---|---|---|---|
| Android | mDNS via `NsdManager` | TCP | not in v0.1 (planned v0.2) |
| JVM (Win/Lin/Mac) | mDNS via `JmDNS` | TCP | not in v0.1 (planned v0.2 with manual-info only) |
| iOS / macOS native | not in v0.1 | not in v0.1 | not in v0.1 |

### 21.4 Firewall and network notes (document in README)

- Windows: first run will prompt the firewall. Document this; suggest a sample app manifest.
- Linux: firewall config varies; document `ufw` example.
- Corporate / guest / hotel Wi-Fi may block mDNS (UDP 5353) and peer-to-peer TCP. Document this as the most common cause of "no peers found."
- Android phones on mobile data only cannot use LAN discovery — they must be on Wi-Fi.

---

## 22. Testing Strategy

### 22.1 Unit tests (`:p2p-core`)

- Frame encoding/decoding roundtrip (all `PacketType`s).
- Chunking and reassembly for payloads under, equal to, and over the chunk size.
- Reassembly timeout cleans up partial messages.
- `TransportManager.selectBestTransport` priority logic.
- `TransportManager.selectBestTransport` throws `NoTransportAvailable` on empty match.
- `PeerRegistry` Found / Updated / Lost transitions.
- `PeerRegistry` stale eviction.
- Protocol version mismatch produces `VersionMismatch` and closes.
- `AppId` mismatch in HELLO produces `HandshakeRejected`.
- Concurrent `P2pSession.send` calls serialize correctly (no interleaved frames).
- `P2pError.PayloadTooLarge` thrown for oversized messages.
- Unknown packet types are ignored at warn level (no crash).

### 22.2 Integration tests (`:p2p-transport-lan` on JVM)

- Two `P2pKit` instances in one JVM process:
  - Advertise on loopback.
  - Discover each other.
  - Connect outgoing from instance A.
  - Accept incoming on instance B.
  - Exchange text and binary messages both directions.
  - Close cleanly.
- Disconnect mid-session triggers `Failed`.
- With `ReconnectPolicy.Enabled`, a forced disconnect retries.
- Keepalive timeout transitions to `Failed`/`Reconnecting`.

### 22.3 Android device tests

- Manual device matrix:
  - Android 9, 11, 13, 14.
  - Two devices on same Wi-Fi.
  - Discover, connect, send text, send 1 MB binary, send 4 MB binary.
- Background/foreground transitions follow `BackgroundPolicy.CloseActiveSessions`.

### 22.4 Future v0.2 tests

- Network provisioning fake (in-memory implementation of `NetworkProvisioningManager`).
- Android `LocalOnlyHotspot` integration on a real device (instrumentation test).

---

## 23. Implementation Order

1. `:p2p-core` — models, interfaces, errors, `P2pState`, `ConnectionState`, `TransportManager`, `PeerRegistry`, `SessionManager` skeleton, `NoOpSecurityManager`, `P2pLogger`, DSL builder. Unit tests for `TransportManager` and `PeerRegistry`.
2. Protocol framing and encoding/decoding in `:p2p-core`. Unit tests for round-trip, chunking, packet handling, HELLO validation.
3. `:p2p-transport-lan` JVM target. `JmDNS` discovery + TCP server/client. Loopback integration tests.
4. `:p2p-transport-lan` Android target. `NsdManager` discovery + TCP. Manual two-device verification.
5. `:p2p-sample-desktop` — Compose for Desktop (or plain CLI) showing advertise, discover, connect, send text.
6. `:p2p-sample-android` — Compose UI showing the same flow.
7. Documentation: README, KDoc, sample walkthrough.
8. Provisioning interfaces in `:p2p-core` with `Unsupported` stubs. Locked v0.2 shapes from section 20.

Each step lands as its own PR with passing tests before the next begins.

---

## 24. README Requirements

The published README must contain:

1. **What P2pKit is** — one-paragraph elevator pitch.
2. **What P2pKit is not** — explicit non-goals (no encryption in v0.1, no iOS in v0.1, no automatic cross-platform LAN setup).
3. **v0.1 platform support matrix** — section 21.3 table.
4. **Quick start** — the recommended usage pattern from section 7.5.
5. **Required permissions** — runtime list per platform plus install-time permissions to declare in `AndroidManifest.xml`.
6. **Why LAN/TCP is the first transport** — short rationale.
7. **Future transport roadmap** — BLE, Wi-Fi Direct, Multipeer, Relay, with realistic expectations.
8. **Network provisioning vs transport** — explain the distinction; mark provisioning as v0.2.
9. **Recommended connection flow** — same LAN → manual fallback. (Hotspot flow added in v0.2.)
10. **Firewall and network notes** — section 21.4.
11. **Architecture diagram** — section 6.
12. **Example app links** — `:p2p-sample-android`, `:p2p-sample-desktop`.

---

## 25. Roadmap

### v0.1 (this spec)

- `:p2p-core`
- `:p2p-transport-lan` (Android, JVM)
- Two sample apps
- `NoOpSecurityManager`
- Provisioning interfaces only (no implementation)

### v0.2

- `:p2p-network-provisioning` interface module
- `:p2p-network-provisioning-android` — `LocalOnlyHotspot` host + Wi-Fi join helper
- `:p2p-network-provisioning-desktop` — manual info, network state detection
- File transfer API: `sendFile(file: P2pFile): Flow<TransferProgress>` and `sendStream(chunks: Flow<ByteArray>): Flow<TransferProgress>`

### v0.3

- iOS / macOS LAN transport (Bonjour + `Network.framework`)
- `:p2p-network-provisioning-ios` (join-only via `NEHotspotConfiguration`)
- `:p2p-sample-ios`

### v0.4+

- `:p2p-transport-ble` — small messages and discovery
- `:p2p-transport-android-wifidirect`
- `:p2p-transport-apple-multipeer`
- `:p2p-transport-relay` — internet fallback
- Encryption: `SecurityMode.PairingCode`, `SecurityMode.QrCode`; X25519 + HKDF + AES-GCM / ChaCha20-Poly1305
- Windows / Linux native Wi-Fi Direct bridges (long-term, opportunistic)

---

**End of spec.** Implementation may begin with `:p2p-core`.
