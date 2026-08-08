# P2pKit — Kotlin Multiplatform P2P Data Transfer SDK

**Version:** 0.7 specification (historical v0.1 baseline plus shipped amendments through authenticated protocol v2)
**Status:** Living contract — the locked API shapes below are amended in place as features ship; public-API changes require a spec rev
**Last updated:** 2026-07-28

---

## 0. Normative v0.7 amendment

This section summarizes the current release contract. Historical milestone
sections remain below to preserve design rationale; where a historical
v0.1-v0.6 statement conflicts with this amendment or the current public API,
this amendment and the checked ABI declarations are authoritative.

- `SecurityMode.AuthenticatedV2(PeerAuthorizationPolicy.RejectUnknown)` is the
  default. The fixed profile is `Noise_XX_25519_ChaChaPoly_SHA256`.
- Authenticated v2 uses protocol version 2 and the `_p2pkit2._tcp` Bonjour
  namespace (`_p2pkit2._tcp.local.` for JmDNS). A failed secure handshake is
  terminal and never retries as plaintext.
- Deprecated `SecurityMode.NoneForMvp` explicitly selects legacy plaintext
  protocol version 1 and `_p2pkit._tcp`. It exists only for migration and is
  never auto-negotiated.
- mDNS/TXT identity and fingerprint values are discovery claims, not trust
  decisions. Secure authorization requires an exact per-connect pin,
  `PinnedOnly`, or the explicit-risk `AcceptAnyAuthenticatedSameApp` policy.
- Android secure identity uses Keystore-wrapped no-backup storage after
  `P2pKitAndroid.initialize(applicationContext)`. iOS uses a device-only
  Keychain item. JVM consumers must provide a protected, durable
  `JvmSecureIdentityStore`; core has no plaintext fallback.
- `send()` confirms a local transport write, not remote application handling.
  `P2pSession.incoming` remains hot and replay-zero. Applications own admission,
  readiness, ids/sequences, deduplication, acknowledgements, and state repair.
- LAN remains the only shipped data/discovery transport. It provides no public
  internet reachability, NAT traversal, rendezvous, or relay.
- Version `0.7.0` is staged as new immutable coordinates; remote Central
  publication remains an external release gate. No `0.6.x` artifact may be
  replaced with v0.7 bytes.

The operational migration contract is
[`docs/MIGRATING_TO_0.7.md`](docs/MIGRATING_TO_0.7.md).

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
- v0.1 did not include encryption; v0.7 defaults to authenticated encryption.
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
- LAN peer discovery via mDNS (in-process `JmDNS` on Android & JVM, Bonjour/`NWBrowser` on iOS).
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
- ~~iOS provisioning (join-only via `NEHotspotConfiguration`)~~ — **dropped from v0.2.** iOS provisioning is not implementable under current App Store policy and is removed from the roadmap.
- ~~Possibly: iOS LAN transport (Bonjour + `Network.framework`)~~ — **deferred to v0.3.** v0.2 ships **iOS core scaffolding only** (see §5.1 below).

The provisioning API shape is locked in this spec under section 20. v0.2 implementation must conform to it.

### 5.1 v0.2 iOS scope (Task 4 — implemented as scaffolding only)

`:p2p-core` declares `iosX64`, `iosArm64`, and `iosSimulatorArm64` targets and provides `iosMain` actuals:

- `currentPlatform()` returns `Platform.IOS`.
- `systemTimeMillis()` is backed by `NSDate().timeIntervalSince1970`.
- `defaultPeerIdStorage(appId, logger)` returns a `NSUserDefaultsPeerIdStorage` that persists the `PeerId` under key `dev.p2pkit.peerId.<sanitized-appId>` in `NSUserDefaults.standardUserDefaults`. Survives app restarts and iOS upgrades; cleared on uninstall — same on-uninstall semantics as the Android `filesDir` backing.

Explicitly **not** in v0.2:

- iOS LAN transport (`:p2p-transport-lan` does not declare iOS targets in v0.2).
- iOS Bonjour discovery (`NWBrowser`).
- iOS TCP listener (`NWListener`) or client (`NWConnection`).
- iOS sample app.
- iOS Network Provisioning.

iOS LAN/TCP cross-talk with Android/JVM peers shipped in **v0.3**, using Apple's `Network.framework` (`NWBrowser` + `NWListener` + `NWConnection`). In v0.7 all platforms use `_p2pkit2._tcp` and protocol version 2 for authenticated mode; explicit deprecated legacy mode remains on `_p2pkit._tcp` and protocol version 1.

iOS Network Provisioning is **never planned**. Apple does not allow third-party apps to create Wi-Fi hotspots, and silent Wi-Fi join is not exposed to third-party apps. `P2pKit.networkProvisioning` will continue to throw `Unsupported` on iOS in every future version.

### 5.2 v0.2 local identity accessors (Task 7)

To make the SDK testable and to support diagnostics, support logs, and member-display UIs, `P2pKit` exposes three read-only properties for the identity it was constructed with:

```kotlin
public interface P2pKit {
    public val appId: AppId
    public val localDeviceName: String
    public val localPeerId: PeerId
    // …existing surface unchanged
}
```

These properties expose existing state — no new behavior:

- `appId` is the value passed into `P2pKit.create { appId = … }`.
- `localDeviceName` is the value passed into `P2pKit.create { deviceName = … }`.
- `localPeerId` is the value the kit's internal `PeerIdStorage` returns from `loadOrGenerate()` at construction. The storage stays internal — apps never touch it. The id is stable across process restarts on platforms with default persistence (JVM file, Android `filesDir` after `P2pKitAndroid.initialize`, iOS `NSUserDefaults`).

All three are immutable for the lifetime of the kit. They are pure accessors, not flows — the values do not change once `create` returns. No setter; no way to override `localPeerId` via the public API.

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
     Security engine             ← authenticated Noise v2 by default; explicit legacy v1
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
    // AuthenticatedV2(RejectUnknown) is the default.

    logger = P2pLogger.NoOp
}
```

### 7.2 `P2pKit` interface

```kotlin
interface P2pKit {
    val appId: AppId               // v0.2 identity accessors — see §5.2
    val localDeviceName: String
    val localPeerId: PeerId
    val localFingerprint: PeerFingerprint?
    val localPairingQr: String?

    fun parsePeerPairingQr(value: String): PeerFingerprint?

    val state: StateFlow<P2pState>
    val advertisingState: StateFlow<FeatureState>
    val discoveryState: StateFlow<FeatureState>

    val peers: StateFlow<List<Peer>>
    val incomingSessions: SharedFlow<P2pSession>
    val sessions: StateFlow<List<P2pSession>>

    val permissions: P2pPermissionManager
    val networkProvisioning: NetworkProvisioningManager   // real sidecars since v0.2.1; Unsupported stub otherwise

    /**
     * v0.4. Host device's default network path status, driven by the
     * configured NetworkPathObserver: iOS gets a real nw_path_monitor
     * observer by default; Android host apps supply
     * AndroidNetworkPathObserver(applicationContext) via the lifecycle DSL;
     * JVM desktop stays NetworkPathStatus.Unknown unless the host provides
     * an observer. Values: Unknown / Satisfied / Unsatisfied. The SDK uses
     * the same flow internally to fail Connected sessions on path loss and
     * to wake Reconnecting sessions' retry delay on path recovery.
     */
    val networkPathStatus: StateFlow<NetworkPathStatus>

    /**
     * v0.4. Bring up all registered transports and the provisioning sidecar.
     * Optional — startAdvertising(), startDiscovery(), and connect() each
     * lazily start the kit on their first invocation. Calling start()
     * explicitly is preferred because it surfaces
     * P2pError.TransportStartFailed at a single, predictable call site.
     * Idempotent after a successful start; after a failed start the next
     * call retries.
     */
    suspend fun start()

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
     * P2pError.PermissionMissing, or P2pError.TransportStartFailed
     * (when the implicit lazy start fails).
     */
    suspend fun connect(peer: Peer): P2pSession
    suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession

    fun lastSeen(peerId: PeerId): Long?   // epoch millis, null if unknown

    fun notifyAppBackgrounded()
    fun notifyAppForegrounded()

    /**
     * Terminal. Cancels the kit's internal scope; the instance cannot be
     * restarted — any lifecycle call after stop() throws
     * IllegalStateException. Create a new instance to start again.
     */
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

    /** Authoritative retained, admission-ordered pending inbound offers. */
    val pendingFileOffers: StateFlow<List<P2pFileOffer>>

    /** Migration-only event stream; replay = 0 and not authoritative. */
    @Deprecated("Observe pendingFileOffers")
    val incomingFiles: SharedFlow<P2pFileOffer>

    /**
     * Safe to call from multiple coroutines. Writes are serialized internally
     * with a Mutex; frames will not interleave on the same connection.
     */
    suspend fun send(message: P2pMessage)

    /**
     * v0.2.2. Offer a file to the peer. Bytes are pulled from [source] in
     * chunkSizeBytes chunks — the file is never fully buffered in memory.
     * The caller closes [source] after the returned transfer reaches a
     * terminal state.
     *
     * Throws P2pError.PayloadTooLarge if sizeBytes exceeds the configured
     * maxFileSizeBytes (default 2 GiB), or P2pError.FileTransferFailed with
     * stable kind/phase/retryability fields. See §7.6.
     */
    suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: kotlinx.io.RawSource
    ): P2pFileTransfer

    suspend fun sendFile(
        name: String,
        mimeType: String?,
        source: PreparedFileSource
    ): P2pFileTransfer

    suspend fun close()
}
```

### 7.4 DSL builder (sketch)

```kotlin
class P2pKitBuilder {
    var appId: AppId? = null
    var deviceName: String? = null
    var logger: P2pLogger = P2pLogger.NoOp
    var permissionManager: P2pPermissionManager? = null   // null = platform default

    fun transports(block: TransportsBuilder.() -> Unit)
    fun keepAlive(block: KeepAliveConfigBuilder.() -> Unit)
    fun lifecycle(block: LifecycleConfigBuilder.() -> Unit)
    fun security(block: SecurityConfigBuilder.() -> Unit)
    fun networkProvisioning(block: NetworkProvisioningConfigBuilder.() -> Unit)  // v0.2.1 — see §20.4
    fun fileTransfer(block: FileTransferConfigBuilder.() -> Unit)                // v0.2.2 — see §7.6
}

class TransportsBuilder {
    fun register(factory: TransportFactory)
    // Transport modules contribute extension helpers; see §19.1 for the
    // per-platform lan() signatures (Android's takes a Context).
}

class LifecycleConfigBuilder {
    var reconnectPolicy: ReconnectPolicy
    var onBackground: BackgroundPolicy
    var onAppKilled: AppKilledPolicy

    /**
     * v0.4. Host-provided override feeding P2pKit.networkPathStatus. null =
     * platform default: a real nw_path_monitor observer on iOS; no-op on JVM
     * and Android. Android hosts that want path-change recovery set
     * `networkPathObserver = AndroidNetworkPathObserver(applicationContext)`.
     */
    var networkPathObserver: NetworkPathObserver?
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

### 7.6 File transfer (v0.2.2 — normative)

Discrete-file streaming on top of an existing session. The whole file is never
buffered in memory; bytes stream in `chunkSizeBytes` frames through the
session's write mutex so messages and keepalive still get slots mid-transfer.

**Secure-v2 flow.** The sender supplies a repeatable `PreparedFileSource`
containing a size and SHA-256 snapshot. The authenticated HELLO must negotiate
`file-commit-sha256-v1`; otherwise the operation fails with
`UNSUPPORTED_FEATURE` without opening the source. The receiver gets a retained
`P2pFileOffer` and accepts a transactional `FileTransferDestination`. FILE_DATA
streams only after acceptance. The sender hashes the exact streamed content,
sends FILE_FINISH with size/chunk count/content digest/offer hash, and remains
nonterminal. The receiver verifies all values, flushes, durably commits, then
sends FILE_COMMIT. Only a matching authenticated FILE_COMMIT completes the
sender. FILE_RESULT carries typed verification/storage/protocol/source/timeout
failure. Retry always creates a new transfer id; resume is not supported.

**Legacy-v1 flow.** The deprecated `RawSource` / `RawSink` overloads retain the
original FILE_OFFER → FILE_ACCEPT → FILE_DATA → FILE_DONE behavior and complete
after receiver flush. Secure sessions never downgrade to this path.

**Unanswered-offer terminal states:** a conforming receiver is the timeout
authority and sends FILE_REJECT, so both sides end as `Rejected("timeout")`.
The sender's later safety watchdog covers a non-conforming peer that sends no
decision; that local transfer ends as `Failed(FileTransferFailed)` with kind
`TIMEOUT`, phase `OFFER`, and `RETRY_SAME_SESSION`.

**Public types** (package `dev.p2pkit.core.transfer`):

```kotlin
interface P2pFileOffer {
    val id: String          // 32-char hex transfer id
    val peer: Peer
    val name: String
    val sizeBytes: Long
    val mimeType: String?

    /** Legacy only: Completed = flushed, not closed — the caller closes the sink. */
    @Deprecated("Legacy flush-only transfer")
    suspend fun accept(sink: kotlinx.io.RawSink): P2pFileTransfer
    /** Secure-v2: verify, flush, durably commit, then acknowledge. */
    suspend fun accept(destination: FileTransferDestination): P2pFileTransfer
    /** Decline. Sender observes FileTransferState.Rejected. No-op if already answered. */
    suspend fun reject(reason: String? = null)
}

interface P2pFileTransfer {
    val id: String
    val peer: Peer
    val name: String
    val sizeBytes: Long
    val mimeType: String?
    val state: StateFlow<FileTransferState>
    val bytesTransferred: StateFlow<Long>   // monotonic until terminal
    suspend fun cancel(reason: String? = null)
}

sealed class FileTransferState {
    data object Offered : FileTransferState()
    data object Accepted : FileTransferState()
    data class Sending(val progress: Float) : FileTransferState()   // 0.0..1.0
    data object Completed : FileTransferState()                      // terminal
    data class Rejected(val reason: String?) : FileTransferState()   // terminal
    data class Cancelled(val reason: String?) : FileTransferState()  // terminal
    data class Failed(val error: P2pError) : FileTransferState()     // terminal
}

data class FileTransferConfig(
    val maxFileSizeBytes: Long = 2L * 1024 * 1024 * 1024,  // 2 GiB cap; sendFile throws PayloadTooLarge above it
    val chunkSizeBytes: Int = 64 * 1024,                   // bytes per FILE_DATA frame (1..4 MiB)
    val offerTimeoutMillis: Long = 30_000                  // unanswered offers auto-reject with "timeout"
)
```

Configured via `fileTransfer { … }` on the builder. Convenience extensions:
JVM `session.sendFile(java.io.File)` and Android
`session.sendFile(Context, Uri)` resolve name/size/mime and open the source
for you. Terminal states release resources; all transfers on a session are
closed when the session closes.

---

## 8. Internal Architecture

```
P2pKitImpl
 ├── PeerRegistry                — owns the public peers list
 ├── SessionManager              — creates/accepts/tracks sessions
 ├── TransportManager            — picks the best DataTransport per peer
 ├── P2pProtocol                 — framing, chunking, ACK, ping/pong
 ├── Security engine            — Noise-v2 handshake/records or explicit legacy passthrough
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

### 9.3 Internal peer (transport SPI)

These types are declared `public` because transports are implemented in
separate Gradle modules (`:p2p-transport-lan` etc.) and must construct them.
They are SPI, not app API — application code should use `Peer` and never
depend on `host`/`port`.

```kotlin
public data class InternalPeer(
    val publicPeer: Peer,
    val transportHints: List<TransportHint>
)

public data class TransportHint(
    val type: TransportKind,
    val host: String? = null,
    val port: Int? = null,
    val metadata: Map<String, String> = emptyMap()
)

public data class LocalPeerInfo(
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

    // Plain class, NOT a data class: avoids compiler-generated copy() /
    // componentN() over a mutable ByteArray. equals/hashCode/toString are
    // hand-written and content-based.
    class Binary(
        val bytes: ByteArray,
        val metadata: Map<String, String> = emptyMap()
    ) : P2pMessage() {
        override fun equals(other: Any?): Boolean { /* content equality */ }
        override fun hashCode(): Int { /* content-based */ }
    }
}
```

No `FileChunk` in the public API. Chunking is internal.

**Metadata compatibility (PARSE-META-01, approved 2026-07-22):** explicit
legacy protocol v1 remains metadata-free. Authenticated secure peers negotiate
`app-message-envelope-v1` in encrypted HELLO and then authenticate a canonical
envelope containing message type/id, per-direction sequence, sender, recipient,
sorted UTF-8 metadata, content length, content SHA-256, and content. A secure
peer lacking the feature may still exchange raw DATA only when metadata is
empty; non-empty metadata fails with `P2pError.UnsupportedFeature` instead of
being silently discarded. Bounds are 64 entries, 256 UTF-8 bytes per key,
4 KiB per value, and 32 KiB aggregate key/value bytes.

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

`Stopped` is **terminal**: `stop()` cancels the kit's internal scope
permanently, and any lifecycle call after it throws `IllegalStateException` —
create a new instance to start again. `Failed` carries the `P2pError` that
aborted startup (e.g. `TransportStartFailed`); unlike `Stopped`, the next
lifecycle call after `Failed` retries through `Starting`. Backgrounding never
produces `Stopped` (see §16.2).

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
    data class AuthenticatedV2(
        val authorization: PeerAuthorizationPolicy =
            PeerAuthorizationPolicy.RejectUnknown
    ) : SecurityMode()

    @Deprecated("Use AuthenticatedV2 and configure peer authorization")
    data object NoneForMvp : SecurityMode()
}

sealed interface PeerAuthorizationPolicy {
    data object RejectUnknown : PeerAuthorizationPolicy
    class PinnedOnly(
        val fingerprints: Set<PeerFingerprint>
    ) : PeerAuthorizationPolicy

    @ExplicitSecurityRisk
    data object AcceptAnyAuthenticatedSameApp : PeerAuthorizationPolicy
}
```

---

## 10. Session Behavior

- `connect(peer)` is **idempotent**. If a session exists with state in `{Connecting, Handshaking, Connected, Reconnecting}`, the existing instance is returned. Otherwise a new one is created.
- `P2pSession.send` is **safe under concurrent calls**. Writes are serialized via an internal `Mutex`.
- `P2pSession.incoming` is a **hot `SharedFlow`** with `replay = 0`, `extraBufferCapacity = 64`, `onBufferOverflow = SUSPEND`. Subscribe immediately after `connect()` or accept — late subscribers miss earlier messages. For an **incoming** session this window is inherent (decision #13b, 2026-07-04): the session is created by the remote's dial, so its first messages race the app's subscription — a peer that sends immediately after connecting can deliver a message before any collector is attached, and that message is dropped. Recommended pattern: subscribe to a fresh session's flows before sending on it, and have the dialing side wait for an app-level ready/greeting reply (or apply a short grace delay) before its first real payload.
- `close()` transitions directly `Connected → Closed`; `Closing` is a reserved `ConnectionState` constant and is not emitted by the current implementation (decision #10a, 2026-07-04). ACK/keepalive stops, underlying connection releases.
- A failed session emits `Failed` and is removed from `sessions` (after retention or immediately, see below).
- If `ReconnectPolicy.Enabled` is configured, the session transitions to `Reconnecting` and retries up to `maxAttempts` with `retryDelayMillis` between attempts. On exhaustion it becomes `Failed`.
- Closed/Failed sessions are removed from `P2pKit.sessions` after they emit their terminal state.
- **Simultaneous-open arbitration** (v0.2). If both peers `connect()` each other at the same instant, two physical TCP connections form (one in each direction) and each side ends up with two `P2pSession` candidates for the other peer (one outgoing, one incoming). The SDK arbitrates this deterministically inside `SessionManager.registerSession` so `P2pKit.sessions` never contains more than one session per peer:
  - the **smaller-id peer** keeps its **outgoing** session; closes its incoming;
  - the **larger-id peer** keeps its **incoming** session; closes its outgoing.
  Both sides converge on the same physical TCP connection (the one initiated by the smaller-id peer). The other peer that observes the loser's close treats it like a clean session close. App code that observes `P2pKit.sessions` sees the surviving session only. App code that captured the return value of `connect()` may briefly hold the rejected session — `P2pKit.sessions` is the source of truth.

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

    /**
     * V0.4-DISCOVERY-REFRESH. Send a fresh round of active discovery queries
     * (stop + restart the underlying browser / force per-peer re-query) so a
     * peer that rebound its listener is re-resolved promptly. Called by
     * SessionManager repeatedly (~3 s cadence) while any outgoing session is
     * Reconnecting. No-op if discovery is not running; default impl is a
     * no-op for transports without a fresh-query primitive.
     */
    suspend fun refresh() {}
}

// Public (not internal): transports in separate modules emit these.
// Application code never sees them — only the aggregated P2pKit.peers.
public sealed class PeerEvent {
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

    /**
     * v0.4. Bring the transport up (bind sockets, create listeners). Called
     * by P2pKit.start() — or implicitly on the first startAdvertising() /
     * connect() when the host app skips the explicit start. Must be
     * idempotent: a second call after success returns Result.success.
     * Transports do not throw from start(); a bind failure is returned as
     * Result.failure and the kit wraps it in P2pError.TransportStartFailed.
     * Default impl is a no-op success for outbound-only transports.
     */
    suspend fun start(): Result<Unit> = Result.success(Unit)

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
    CLOSE(0x07),

    // File transfer (v0.2.2). Same frame format; message_id carries the
    // transferId for the lifetime of a single file offer (see §7.6).
    FILE_OFFER(0x10),    // JSON offer payload: name, sizeBytes, mimeType
    FILE_ACCEPT(0x11),   // empty payload
    FILE_REJECT(0x12),   // optional UTF-8 reason payload
    FILE_DATA(0x13),     // one chunk of file bytes
    FILE_DONE(0x14),     // legacy sender finished; empty payload
    FILE_CANCEL(0x15),   // either side aborts; optional UTF-8 reason
    FILE_FINISH(0x16),   // secure-v2 streamed size/chunks/digest/offer hash
    FILE_COMMIT(0x17),   // receiver durably committed matching content
    FILE_RESULT(0x18)    // typed secure-v2 terminal failure
}
```

All three platform transports must speak this exact frame vocabulary — a new
code added on one platform must be mirrored on the others.

### 13.2 Frame layout

```
| magic (4 bytes)         | 'P' 'P' '2' 'K'  = 0x50 0x50 0x32 0x4B
| version (1 byte)        | 0x01 explicit legacy; 0x02 authenticated secure
| type (1 byte)           | PacketType code
| flags (1 byte)          | bit 0 = needs ACK
|                         | bit 1 = last chunk in sequence
|                         | bit 2 = is text payload
|                         | bit 3 = authenticated application envelope (DATA only)
|                         | bits 4-7 reserved (must be 0)
| reserved (1 byte)       | must be 0
| message_id (16 bytes)   | UUID; same id for all chunks of one message
| chunk_index (4 bytes)   | big-endian uint32
| total_chunks (4 bytes)  | big-endian uint32
| payload_len (4 bytes)   | big-endian uint32; length of payload that follows
| payload (variable)      | up to payload_len bytes
```

Fixed header = 36 bytes. Payload follows immediately.

Receivers enforce `payload_len ≤ 8 MiB` (`MAX_FRAME_PAYLOAD_BYTES`) **before**
buffering or allocating — a frame declaring more is a protocol violation and
closes the session (DoS guard: a peer must not be able to declare a ~2 GiB
payload and drive the process to OOM).

### 13.3 HELLO payload

JSON-encoded:

```json
{
  "appId": "com.example.transfer",
  "peerId": "5b3c...",
  "deviceName": "Abdo Phone",
  "platform": "ANDROID",
  "supportedTransports": ["LAN"],
  "protocolVersion": 2,
  "features": ["app-message-envelope-v1", "file-commit-sha256-v1"]
}
```

Both sides exchange HELLO before any DATA. In secure-v2, HELLO is inside the
authenticated encrypted channel and feature intersection is fixed for that
connection epoch. If `appId` doesn't match the local config, the receiver sends
`ERROR` and closes. If the protocol version is incompatible, the receiver sends
`ERROR` and closes. Unknown feature identifiers are ignored; required features
fail closed at the operation boundary.

### 13.4 Chunking

- Default chunk size: 64 KB.
- A message larger than the chunk size is split. All chunks share `message_id`. `chunk_index` starts at 0. `total_chunks` is set in every frame for that message. The final chunk has `flags & LAST_CHUNK == 1`.
- The receiver reassembles by `message_id`. Reassembly state has a timeout (default 60s) to prevent memory leaks from incomplete messages.
- **Receive-path caps (session-closing).** In addition to the 8 MiB per-frame payload cap (§13.2), receivers enforce `total_chunks ≤ 1024` (`MAX_TOTAL_CHUNKS`) per message and at most 256 concurrently-incomplete multi-chunk messages (`MAX_PENDING_REASSEMBLIES`) per connection. Exceeding either is treated as a protocol violation and **closes the session**, even when every individual frame is otherwise well-formed — conforming senders must chunk a ≤ 4 MiB message into ≤ 1024 chunks (the 64 KiB default yields at most 64).

### 13.5 ACK

- A DATA frame with `flags & NEEDS_ACK == 1` triggers an ACK.
- The ACK frame carries the same `message_id` and `chunk_index` in its header; payload is empty.
- v0.1 default: per-chunk ACK is **off** (TCP already guarantees delivery). The plumbing exists for future non-reliable transports.

### 13.6 Protocol interface

Control frames and file transfer are routed by `SessionManager` /
`P2pSessionImpl`, not hidden behind a message-only `receive()` — the protocol
layer exposes one typed send method per frame kind plus a single decoded
event stream:

```kotlin
internal interface P2pProtocol {
    suspend fun sendMessage(connection: RawConnection, message: P2pMessage)
    suspend fun sendHello(connection: RawConnection, hello: HelloPayload)
    suspend fun sendPing(connection: RawConnection)
    suspend fun sendPong(connection: RawConnection)
    suspend fun sendClose(connection: RawConnection)
    suspend fun sendError(connection: RawConnection, reason: String)

    // File transfer (v0.2.2); transferId is reused as the frame's message_id.
    suspend fun sendFileOffer(connection: RawConnection, transferId: MessageId, offer: FileOfferPayload)
    suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId)
    suspend fun sendFileReject(connection: RawConnection, transferId: MessageId, reason: String?)
    suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame)
    suspend fun sendFileDone(connection: RawConnection, transferId: MessageId)
    suspend fun sendFileCancel(connection: RawConnection, transferId: MessageId, reason: String?)

    /** Decoded frames from [connection] as typed events (data, control, file). */
    fun events(connection: RawConnection): Flow<ProtocolEvent>
}
```

Send methods are not synchronized — the session serializes writes per
connection with its Mutex.

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

### 15.3 Platform mappings

| Platform | Required at runtime |
|---|---|
| Android (LAN only) | none for plain LAN/mDNS on most versions; document `NearbyWifiDevices` if discovery requires it on the device's API level. Hotspot/Wi-Fi-join provisioning (v0.2.1) needs `NEARBY_WIFI_DEVICES` (API 33+) / `ACCESS_FINE_LOCATION` (API ≤ 32) |
| JVM desktop | none |
| iOS (LAN, v0.3+) | none in the `P2pPermission` sense — the OS shows the Local Network privacy prompt on first use; the app must declare `NSLocalNetworkUsageDescription` and the exact selected service (`NSBonjourServices = ["_p2pkit2._tcp"]` for default authenticated v2; legacy `_p2pkit._tcp` only for an explicit plaintext build) |

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
  - `P2pState` **stays `Running`** — the data transports remain bound and the
    kit is still functional, so reporting `Stopped` would lie to host UIs and
    never recover on foreground. `Stopped` is only ever produced by `stop()`.
  - No background transfer guarantee.
- **JVM desktop minimized/backgrounded:**
  - No special action. The library keeps running.
- **App foregrounded:**
  - The app must re-call `startAdvertising()` and `startDiscovery()`. v0.1 does **not** auto-restart.
  - If `ReconnectPolicy.Enabled`, sessions that were `Reconnecting` continue retry. Sessions that were `Closed` do not auto-reopen.
- **Process death:**
  - All sessions are lost. `PeerId` persists; everything else is rebuilt fresh.

  **v0.2 status (Task 1):** Persistence is implemented. JVM writes to
  `<user.home>/.p2pkit/<sanitized-appId>/peer-id`. Android writes to
  `<filesDir>/p2pkit/<sanitized-appId>/peer-id` **after** the host app
  calls `P2pKitAndroid.initialize(applicationContext)` from
  `Application.onCreate()`. Without that init call on Android, the kit
  falls back to in-memory storage and logs a `P2pLogger.warn` at
  construction. JVM has no init step — persistence is automatic.

### 16.3 Network change handling

If the underlying socket dies due to a network change (Wi-Fi → mobile data, network switch, etc.):

- The session emits `Failed` immediately.
- If `ReconnectPolicy.Enabled`, the session enters `Reconnecting` and retries.
- Discovery does **not** automatically restart in v0.1. The app should observe `P2pState` / `permissions` and re-invoke discovery as needed.

---

## 17. Error Handling

```kotlin
sealed class P2pError(message: String? = null, cause: Throwable? = null) : Exception(message, cause) {
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

    /**
     * v0.4. A registered transport could not be brought up by start() — or by
     * the first startAdvertising()/connect() that triggered lazy startup.
     * Carries the failed transport's kind and the underlying cause (port
     * exhaustion, missing entitlement, listener bind timeout, ...).
     */
    data class TransportStartFailed(
        val transportKind: TransportKind,
        val reason: String,
        val underlying: Throwable? = null
    ) : P2pError("Transport $transportKind failed to start: $reason", underlying)
}
```

**`send()`/`sendFile()` error boundary (decision #12a, 2026-07-04):** an
unexpected transport-level failure crossing the `send()`/`sendFile()` boundary
surfaces as `P2pError.ConnectionFailed` with the original exception preserved
as `cause`; `CancellationException` and already-typed `P2pError`s pass through
unchanged.

Fallback rules:

- Unknown packet type → ignored; logged at warn level. Does not close the session.
- Unknown peer capability → peer is still discovered; transports just skip it.
- `appId` mismatch during HELLO → `HandshakeRejected`, session closes.
- Protocol major version mismatch → `VersionMismatch`, session closes.

---

## 18. Security Abstraction

### 18.1 Authenticated protocol v2

The default fixed profile is `Noise_XX_25519_ChaChaPoly_SHA256`:

1. Each kit loads or creates one persistent X25519 static identity for the
   exact `AppId`.
2. Both sides exchange fixed secure-v2 prefaces and complete Noise XX before
   any P2pKit HELLO/frame parsing.
3. The remote proves possession of its static private key. P2pKit derives the
   canonical `PeerFingerprint` and AppId-bound `PeerId`.
4. Authorization evaluates the proven fingerprint against an exact
   per-connect/manual pin or the configured policy.
5. Only after authentication and authorization succeeds does the encrypted
   connection carry HELLO, DATA, keepalive, close, and file-transfer records.

All handshake/record inputs are bounded and time-limited. AEAD failure,
unexpected role/version/cipher suite, wrong pin, AppId mismatch, replayed
record nonce, malformed record, or authorization rejection closes the
connection. There is no downgrade path.

`RejectUnknown` is the default. `PinnedOnly` admits only its immutable set of
full canonical fingerprints. `AcceptAnyAuthenticatedSameApp` is an explicit
security-risk policy: it authenticates a key and exact AppId binding but does
not authorize a human/device because AppId is public.

Discovery's fingerprint is only an `UntrustedDiscoveryClaim`; the handshake
must prove the key, and `RejectUnknown` does not turn that claim into a pin.

### 18.2 Identity storage

- Android: Keystore-wrapped identity record in no-backup app storage.
  `P2pKitAndroid.initialize(applicationContext)` is required before kit
  construction.
- iOS: device-only Keychain item.
- JVM: the host must provide `JvmSecureIdentityStore` through
  `jvmSecureIdentityStore(store)`. Core deliberately provides no
  passwordless/plain-file secure default.

Resetting or losing the secure identity changes both fingerprint and peer id;
remote applications must treat it as a new identity and approve it again.

### 18.3 Explicit legacy compatibility

`SecurityMode.NoneForMvp` and the old `SecurityManager`/`SecureConnection`
extension point remain deprecated for source/binary migration. They select the
separate plaintext-v1 wire/discovery profile and are never used by the built-in
authenticated-v2 engine. New production code must not depend on them.

---

## 19. LAN Transport Details

### 19.1 Module: `:p2p-transport-lan`

Two cooperating internal classes per platform (illustrative sketch — the
shipped classes are `JvmLan*` / `AndroidLan*` / `IosLan*`) share a
`LanServiceRegistration`:

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
```

The registration entry point is a per-platform `TransportsBuilder` extension —
**the signatures differ**:

```kotlin
// JVM
fun TransportsBuilder.lan()

// iOS (iosX64 / iosArm64 / iosSimulatorArm64)
fun TransportsBuilder.lan()

// Android — requires a Context (uses applicationContext internally for
// WifiManager.MulticastLock and ConnectivityManager callbacks)
fun TransportsBuilder.lan(applicationContext: Context)
```

### 19.2 mDNS

- Authenticated-v2 service type: `_p2pkit2._tcp.local.` on JmDNS and
  `_p2pkit2._tcp` on Bonjour.
- Explicit deprecated legacy-v1 service type: `_p2pkit._tcp.local.` on JmDNS
  and `_p2pkit._tcp` on Bonjour.
- A kit browses/advertises only its selected profile. Profiles never
  auto-negotiate or downgrade.
- TXT record fields:
  - `pid` — peer id
  - `app` — app id
  - `name` — device name (URL-encoded)
  - `plat` — `ANDROID` / `JVM_DESKTOP` / etc.
  - `caps` — comma-separated `TransportKind` values
  - `pv` — selected protocol version (`2` authenticated, `1` legacy)
  - `fp` — canonical fingerprint in authenticated v2; absent in legacy
- Android: in-process `JmDNS` for both advertising and discovery (**v0.5+** — replaced the v0.1–v0.4 `NsdManager` implementation so the SDK owns the mDNS cache and can force re-queries during reconnect; do not reintroduce `NsdManager`).
- JVM: `JmDNS` (jmdns library) for both advertising and discovery.
- iOS (v0.3+): `nw_browser_t` for discovery, `nw_listener_set_advertise_descriptor` for advertising — same service type and TXT keys, wire-indistinguishable from JmDNS peers.

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
    // Named platformException (not `cause`) because `cause` clashes with
    // Throwable.cause. The wrapped throwable is also threaded into
    // Throwable.cause for stack-trace purposes.
    data class PlatformError(val platformException: Throwable) : NetworkProvisioningError()
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

### 21.3 Per-platform reality (v0.7)

| Platform | Discovery | Transport | Provisioning |
|---|---|---|---|
| Android | mDNS via in-process `JmDNS`; secure identity requires application-context initialization | TCP via `java.net.Socket`, authenticated Noise v2 by default | `LocalOnlyHotspot` host + Wi-Fi join via `:p2p-network-provisioning-android` |
| JVM (Win/Lin/Mac) | mDNS via `JmDNS`; host-provided protected identity store required | TCP via `java.net.Socket`, authenticated Noise v2 by default | manual-IP fallback via `:p2p-network-provisioning-desktop` |
| iOS | Bonjour via `nw_browser_t`; device-only Keychain identity | TCP via `nw_connection_t`, authenticated Noise v2 by default; cellular interface prohibited | hotspot/join unsupported; manual-IP fallback available |
| macOS native | not shipped (v0.3.x candidate) | not shipped | not shipped |

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

## 23. Historical implementation order

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
2. **What P2pKit is not** — especially no internet/NAT/relay, room protocol,
   user identity, or application delivery guarantee.
3. **Current platform support matrix** — section 21.3.
4. **Secure quick start** — default fail-closed authorization plus exact
   fingerprint/QR pinning.
5. **Identity-store requirements** — Android initialization, iOS Keychain, and
   required JVM protected store.
6. **Required permissions/privacy declarations** — Android install/runtime
   distinction and exact iOS Bonjour service.
7. **Protocol migration** — secure v2 versus explicit deprecated plaintext v1,
   separate namespaces, and no downgrade.
8. **Session/lifecycle contract** — replay-zero receive flow, local-write send
   semantics, reconnect direction, and terminal cleanup.
9. **Architecture, modules, limits, verification, and publication status.**

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
- File transfer API — **shipped in v0.2.2** and now exposes negotiated secure-v2 `PreparedFileSource` / `FileTransferDestination` durability plus authoritative `pendingFileOffers: StateFlow<List<P2pFileOffer>>`; the legacy flush-only overload and replay-zero `incomingFiles` event remain deprecated for migration (see §7.6). No `sendStream` API shipped.

### v0.3

- iOS / macOS LAN transport (Bonjour + `Network.framework`) — iOS shipped in v0.3; macOS native remains a candidate
- iOS sample app (shipped v0.4 as the `iosApp/` Xcode project)

### v0.4-v0.6

- `:p2p-transport-ble` — small messages and discovery
- `:p2p-transport-android-wifidirect`
- `:p2p-transport-apple-multipeer`
- `:p2p-transport-relay` — internet fallback
- Windows / Linux native Wi-Fi Direct bridges (long-term, opportunistic)

### v0.7

- Authenticated Noise v2 default with fail-closed authorization.
- Platform-protected persistent identity and canonical fingerprints/pairing QR.
- Separate secure-v2/legacy-v1 discovery and wire profiles with no downgrade.
- Authenticated message metadata and durable SHA-256 file commit.
- Central-shaped immutable `0.7.0` artifacts and local Portal bundle gate.

---

**End of spec.** Implementation may begin with `:p2p-core`.
