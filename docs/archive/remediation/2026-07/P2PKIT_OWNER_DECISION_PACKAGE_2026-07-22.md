# P2pKit Owner Decision Package — 2026-07-22

No implementation was performed while preparing this document. These nine decisions currently block 12 finding rows and six numbered test-gap conjuncts. Several rows are partially complete; the dependency map identifies only what remains decision-blocked.

## Approval record

The owner approved all recommended choices on 2026-07-22:

1. `DATA-TRANSPORT-LIFECYCLE-API-01 restartable stop`
2. `PROVISIONING-CLOSE-API-01 required suspending close`
3. `PEER-STATE-API-01 separate feature states`
4. `IMMUTABLE-MODEL-API-01 deep snapshot values`
5. `TRANSPORT-FACTORY-API-01 declared capabilities`
6. `PARSE-META-01 negotiated authenticated envelope`
7. `XFER-OFFER-API-01 retained pendingFileOffers`
8. `XFER-ERROR-API-01 structured FileTransferFailed`
9. `XFER-PROTO-01 negotiated durable commit + prepared SHA-256 snapshot`

These approvals authorize the corresponding local implementation batches. They do not authorize a push, remote change, release, credential use, physical-device claim, hostile-network claim, or cryptographic-audit claim.

## Decision summary

| # | Recommended choice | Main compatibility effect |
|---|---|---|
| 1 | Restartable `DataTransport.stop()` plus terminal `close()` | Required SPI method; breaking for third-party transport implementers |
| 2 | Required, suspending, terminal, idempotent provisioning `close()` | Required interface method and new terminal state; implementer migration |
| 3 | Separate retained advertising and discovery `StateFlow`s | Additive public API; default accessors can soften implementer migration |
| 4 | Deep, cast-proof snapshot-backed public values | Some data classes must become hand-written value types; source/reflection risk |
| 5 | Required pre-build capability descriptor; nullable data/discovery paths | Factory and `TransportPair` implementer migration |
| 6 | Negotiated authenticated secure-v2 message envelope | Secure wire behavior change; legacy v1 stays metadata-free |
| 7 | Authoritative retained `pendingFileOffers` state | Additive API, but third-party `P2pSession` implementations must migrate |
| 8 | Structured `FileTransferFailed` with stable typed fields | Binary-additive; breaks exhaustive source `when` over sealed `P2pError` |
| 9 | Negotiated SHA-256 snapshot plus transactional durable receiver commit | New wire feature and source/destination APIs; old secure peers fail closed |

## 1. Restartable data-transport `stop()`

### Exact problem

`DataTransport` currently has `start()` and terminal `close()`, but no inverse of `start()`. Every shipped LAN implementation rejects `start()` after `close()`.

That makes partial startup impossible to correct safely:

1. Transport A starts successfully.
2. Transport B fails.
3. Closing A makes the documented retry permanently fail.
4. Leaving A running leaks a partial startup.

Blocked scope:

- Finding: `CORE-11`, data-start conjunct only.
- Test gap: `CORE-T09`, data rollback/restart conjunct.
- Direct API: `DataTransport`.
- Core owner: `P2pKitImpl`.
- Implementations: JVM/Desktop LAN, Android LAN, Apple LAN.
- Indirect consumers: all `P2pKit.start()`, lazy `connect()`, advertising, and discovery entry points.

Primary files include `DataTransport.kt`, `P2pKitImpl.kt`, and the three LAN data-transport implementations.

### Options and trade-offs

| Option | Behavior | Compatibility/usability | Reliability, security, performance, platforms |
|---|---|---|---|
| A. Restartable `stop()`, terminal `close()` | `stop()` releases listener/startup resources and permits later `start()`; `close()` permanently disposes the instance | Clear lifecycle; required method breaks third-party SPI implementations | Small state-machine cost; works consistently on JVM, Android, Apple, Desktop, CLI and Swift consumers |
| B. Make `stop()` terminal | `stop()` and `close()` have equivalent terminal behavior | Simplest API, but contradicts current retry-after-start-failure contract | Reliable only if the whole kit also becomes terminal after any partial startup |
| C. Rebuild transports after failure | Destroy and reconstruct factories, transports, registry connections, and listener ownership | Avoids restartable instances but creates a much larger internal lifecycle contract | More allocations, races, duplicated callbacks, registry replacement, and native-resource ownership complexity |
| D. Leave partial transports running | Retry starts only failed transports | No API change | Resource leak and inconsistent advertised/data state; unacceptable |

### Recommended lifecycle

Choose Option A:

```kotlin
interface DataTransport {
    suspend fun start(): Result<Unit>
    suspend fun stop()       // restartable
    suspend fun close()      // terminal
}
```

Internal states:

```text
Inactive → Starting → Active → Stopping → Inactive
    \                                /
     └──────── Closing → Closed ────┘
```

Required behavior:

- `start()` while active is an idempotent success.
- Concurrent `start()` calls share one start transaction.
- Concurrent `stop()` calls share one cleanup transaction.
- `start()` during `stop()` waits for cleanup, then starts a new generation.
- `stop()` during `start()` records stop intent; any late listener or callback is compensated before either call completes.
- `close()` wins over concurrent start/stop and permanently closes the instance.
- `stop()` cancels pending dials, releases listeners, terminates acceptance flow generation, and closes uncommitted inbound connections.
- Established `RawConnection`s whose ownership already moved to sessions are session-owned, not silently destroyed by a transport rollback.
- Late native callbacks are generation-gated and their resources immediately released.
- Cleanup failure prevents restart until a later `stop()` or `close()` successfully releases retained ownership.
- Cancellation remains `CancellationException`; operational failures are mapped by core to the existing typed public errors.
- `P2pKit.stop()` remains terminal. Only the lower-level transport `stop()` is restartable.

This is the smallest correction that preserves the existing kit retry contract. It is a breaking SPI change for external `DataTransport` implementations.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve DATA-TRANSPORT-LIFECYCLE-API-01 restartable stop`
2. `Approve DATA-TRANSPORT-LIFECYCLE-API-01 terminal stop`
3. `Approve DATA-TRANSPORT-LIFECYCLE-API-01 rebuild transport instances`

## 2. Provisioning-manager `close()`

### Exact problem

`NetworkProvisioningManager` has no disposal method. Built-in Android and Desktop managers currently expose implementation-specific non-suspending `close()` functions, while the Apple manual manager and unsupported manager have none.

The `ProvisioningContext.parentJob` is advisory. A third-party manager may ignore it, attach resources incorrectly, or own native callbacks outside that job. Therefore `P2pKit.stop()` cannot guarantee that hotspot reservations, Wi-Fi callbacks, process binding, polling jobs, listeners, or credentials are released.

Blocked scope:

- Finding: `CORE-24`.
- No separately numbered explicit test gap; the row requires lifecycle, ABI, and external-implementer tests.
- Public API: `NetworkProvisioningManager` and `NetworkProvisioningState`.
- Platforms: Android provisioning, JVM/Desktop provisioning, Apple manual-IP manager, unsupported fallback.
- Core integration: `P2pKitImpl` must call it before cancelling the kit scope.

Primary files include `NetworkProvisioningTypes.kt`, the Android and Desktop managers, `IosManualNetworkProvisioningManager.kt`, and the unsupported fallback.

### Options and trade-offs

| Option | Compatibility | Reliability/security | Performance/platform/maintenance |
|---|---|---|---|
| A. Required suspending `close()` | Breaking for external implementers | Core can guarantee bounded, ordered resource cleanup | Uniform Kotlin, Java, Swift, Android, Apple and Desktop semantics |
| B. Default no-op `close()` | Source migration is easier | External managers can still leak; the API promises more than it enforces | Low immediate cost, permanent ambiguity |
| C. Optional `CloseableNetworkProvisioningManager` | Existing interface unchanged | Managers not implementing it remain undisposable | Repeated type checks and two lifecycle contracts |
| D. Parent-job cancellation only | No API change | Cannot control third-party/native ownership | Existing defect remains |

### Recommended contract

Choose Option A:

```kotlin
interface NetworkProvisioningManager {
    suspend fun close()
}
```

Semantics:

- Permanent: once close begins, the manager never accepts new work.
- Idempotent: repeated calls do not reacquire or double-release resources.
- Synchronous in lifecycle meaning, but suspending rather than thread-blocking: it returns after bounded cleanup attempts complete.
- Concurrent callers join the same close transaction.
- Active hotspot and join operations are cancelled and prevented from committing late handles.
- Android hotspot reservations, callbacks, network requests and process bindings are released.
- Desktop polling stops and its job completes.
- Apple and unsupported managers perform a terminal no-resource close.
- Future `startLocalNetwork` and `joinLocalNetwork` return their typed `Failed(ManagerClosed)` result.
- Future `getManualConnectionInfo` and `createManualPeer` throw a typed provisioning-closed error rather than returning misleading `null`.
- `stopLocalNetwork()` remains cleanup-idempotent after close.
- Add `NetworkProvisioningState.Closed`. This new sealed subtype can break exhaustive Kotlin `when` expressions.
- State and event callbacks stop changing after `Closed`.
- Credential references and callbacks are cleared. Because `WifiPassword` currently wraps an immutable `String`, secure zeroization cannot be guaranteed; the contract can guarantee removal of SDK references and no logging, not physical memory erasure.
- If native release fails, the manager becomes operationally closed, reports a typed cleanup failure, retains cleanup ownership, and lets a later `close()` retry the retained handle.

This should be required rather than a default no-op because cleanup is the entire reason for adding the API.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve PROVISIONING-CLOSE-API-01 required suspending close`
2. `Approve PROVISIONING-CLOSE-API-01 default no-op close`
3. `Approve PROVISIONING-CLOSE-API-01 optional closeable interface`

## 3. Advertising/discovery feature-state API

### Exact problem

`P2pKit.state` represents the whole kit. Both advertising and discovery currently write failures into that one value. A later success in either operation can replace the other operation’s failure with `Running`.

Consumers therefore cannot answer:

- Is advertising active while discovery failed?
- Is discovery waiting for permission?
- Is advertising unsupported?
- Is an operation stopping or merely idle?

Blocked scope:

- Finding: `CORE-15`.
- No numbered explicit test gap; required coverage is recorded as feature-state tests.
- Public APIs: `P2pKit.state`, `startAdvertising`, `stopAdvertising`, `startDiscovery`, `stopDiscovery`.
- Core: `P2pKitImpl`.
- Consumer impact: Android/iOS samples, Compose Desktop, CLI diagnostics, Java, Kotlin and Swift state rendering.

### Options and trade-offs

| Option | Compatibility/API | Reliability/usability | Performance/platform/future |
|---|---|---|---|
| A. Two separate retained state flows | Additive; default getters can ease mock migration | Exact independent state and error ownership | Two tiny flows; straightforward on Kotlin, Java and Swift |
| B. Replace `P2pState` with one composite object | Broad source and binary break | Complete snapshot in one read | More complex state updates and migration |
| C. One global state plus error properties | Smaller addition | Consumers must correlate several values and can observe inconsistent snapshots | More maintenance; hard to extend |
| D. Keep current global failure | No change | Does not resolve the finding | No cost, incorrect state |

### Recommended API

Choose Option A:

```kotlin
val advertisingState: StateFlow<FeatureState>
val discoveryState: StateFlow<FeatureState>

sealed class FeatureState {
    data object Idle
    data object Starting
    data object Active
    data object Stopping
    data class PermissionRequired(val missing: List<P2pPermission>)
    data class Unsupported(val reason: String)
    data class Failed(val error: P2pError)
}
```

Behavior:

- Advertising and discovery have completely independent state.
- `P2pState` remains the core instance lifecycle: Idle/Starting/Running/Stopping/Stopped/Failed.
- `startAdvertising()` changes only advertising state.
- `startDiscovery()` changes only discovery state.
- Start while active is idempotent.
- Concurrent starts coalesce.
- Stop during start records stop intent, rolls back any late resource, and reaches `Idle`.
- Failed cleanup remains `Failed`; it is not overwritten by success in the other feature.
- Missing permissions produce `PermissionRequired` and the existing thrown `PermissionMissing`.
- With the current permission API, `PermissionRequired` reflects the last authoritative operation attempt. It cannot automatically notice a Settings change until retry/refresh because the permission manager exposes suspend queries, not an observation flow.
- No registered feature path produces `Unsupported`.
- StateFlow supplies immediate retained observation for Swift, Java, CLI and UI consumers.
- Collection fields in state must follow Decision 4’s immutable snapshot contract.

This is additive for normal consumers. Third-party `P2pKit` mocks need new properties, so default interface accessors should be supplied for a migration release and verified through JVM/Android/KMP/Swift consumer gates.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve PEER-STATE-API-01 separate feature states`
2. `Approve PEER-STATE-API-01 composite P2pState`
3. `Approve PEER-STATE-API-01 global state plus error properties`

## 4. Immutable public model contract

### Exact problem

Kotlin `List`, `Set`, and `Map` are read-only interfaces, not immutable collections. A constructor can retain a caller-owned mutable collection, and a returned implementation may be cast back to `MutableList`, `MutableSet`, `MutableMap`, or Java collection interfaces.

Currently affected public values include:

- `Peer.supportedTransports`
- `InternalPeer.transportHints`
- `TransportHint.metadata`
- `LocalPeerInfo.supportedTransports`
- `PeerAuthorizationPolicy.PinnedOnly.fingerprints`
- `P2pMessage.Text.metadata`
- `NetworkState.ConnectedToWifi.localIpAddresses`
- `NetworkState.ConnectedToEthernet.localIpAddresses`
- `NetworkState.LocalNetworkHosted.localIpAddresses`
- `ManualConnectionInfo.hostAddresses`
- `P2pError.PermissionMissing.permissions`
- `NetworkProvisioningError.PermissionMissingForProvisioning.permissions`
- Published list snapshots such as `P2pKit.peers`, `P2pKit.sessions`, and the proposed pending-offer list.

Transitive provisioning result/event models are affected whenever they contain one of these values.

Already corrected:

- `P2pMessage.Binary` copies its `ByteArray` and metadata.
- Internal registry publication snapshots its inputs.

Blocked scope:

- Finding: remaining public portion of `CORE-17`.
- No separately numbered test gap; mutation, ownership, ABI, Java and Swift consumer tests are required.
- Modules: primarily `p2p-core`; transport and provisioning modules consume the public models.
- Platforms: all.

### Options and trade-offs

| Option | Compatibility | Safety/reliability | Performance/platform/maintenance |
|---|---|---|---|
| A. Deep cast-proof snapshots | Some data classes become hand-written value types | Strong ownership and concurrency guarantee | One construction copy; stable reads; custom wrappers need multiplatform tests |
| B. Shallow `toList`/`toMap` snapshot | Usually preserves data-class ABI | Caller’s original mutations are isolated, but returned backing may still be cast/mutated | Low implementation cost |
| C. Copy on every getter | Constructor and getter signatures can remain | SDK state cannot be mutated through a returned copy | Repeated allocations, surprising reference identity, costly Swift bridging |
| D. Persistent immutable collection types | Strongest type-level contract | Clear immutability | New public dependency and broad Kotlin/Java/Swift API break |
| E. Documentation only | No migration | No actual protection | Defect remains |

### Recommended contract

Choose Option A:

- Deeply immutable means the complete SDK-owned value graph is snapshotted. Strings, enums, inline IDs and fingerprints are already immutable; collections and arrays require ownership protection.
- Constructor inputs are copied once.
- Getters return cast-proof unmodifiable views or immutable wrappers.
- Java mutation attempts fail rather than changing SDK state.
- Swift receives stable snapshots and not a live mutable Kotlin backing collection.
- Arrays continue to use defensive copying.
- Published StateFlow list values are immutable snapshots; contained sessions remain live session objects by design.

Some Kotlin `data class` declarations cannot safely snapshot a constructor property without retaining it. Those should become ordinary hand-written value classes preserving, where ABI permits:

- constructor signatures;
- property getters;
- `equals`, `hashCode`, and `toString`;
- practical `componentN` and `copy` source use.

Even when method descriptors are reproduced, Kotlin reflection’s `isData`, generated metadata, `copy$default`, serialization assumptions, and exhaustive consumer ABI must be checked. This is therefore a potentially breaking source/reflection change, though Java and Swift initializer/getter surfaces can largely be preserved.

Persistent collections are weaker for this library because they would expose an implementation dependency throughout the public API. Getter-copying is safe but unnecessarily allocates on every read.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve IMMUTABLE-MODEL-API-01 deep snapshot values`
2. `Approve IMMUTABLE-MODEL-API-01 copy-on-access values`
3. `Approve IMMUTABLE-MODEL-API-01 persistent collection types`
4. `Approve IMMUTABLE-MODEL-API-01 shallow snapshots only`

## 5. Transport factory capabilities and nullability

### Exact problem

`TransportFactory` currently declares only:

```kotlin
fun build(context: TransportContext): TransportPair
```

`TransportPair.data` is non-null, so a discovery-only transport cannot be expressed. The factory also does not declare its kind or capabilities until after resources are constructed.

Post-build duplicate-kind validation is unsafe: construction is synchronous, but transport cleanup is suspending. Detecting a duplicate only after building can leak the rejected transport.

Blocked scope:

- `CORE-27`.
- Duplicate-kind conjunct of `CORE-28`.
- No numbered explicit gap; factory, ABI, duplicate-kind and external-consumer tests are required.
- APIs: `TransportFactory`, `TransportPair`, transport DSL registration.
- Modules: core and every transport provider.
- Platforms: JVM/Desktop, Android, Apple and future BLE/relay providers.

### Options and trade-offs

| Option | Compatibility/API | Reliability | Platform/performance/future |
|---|---|---|---|
| A. Descriptor before build plus nullable pair paths | Breaking for factories; clear caller contract | Duplicate and invalid configurations rejected before resources exist | Supports discovery-only, data-only and combined providers |
| B. Nullable factory result | Small API | `null` cannot distinguish unsupported, temporarily unavailable or failed initialization | Poor Java/Swift diagnostics |
| C. Exceptions only | Familiar | Capabilities remain unknowable until construction | Late failure and cleanup complexity |
| D. Typed build result only | Good initialization diagnostics | Still too late for duplicate-kind ownership unless descriptor is also present | Extra result handling in every factory |
| E. Unsupported placeholder transports | Preserves non-null pair | Fails late during selection/start and advertises misleading support | Persistent maintenance burden |

### Recommended API

Choose Option A:

```kotlin
data class TransportDescriptor(
    val kind: TransportKind,
    val capabilities: Set<TransportCapability>
)

enum class TransportCapability {
    DATA,
    DISCOVERY
}

interface TransportFactory {
    val descriptor: TransportDescriptor
    fun build(context: TransportContext): TransportPair
}

data class TransportPair(
    val data: DataTransport?,
    val discovery: DiscoveryTransport?
)
```

Invariants:

- At least one pair member must be non-null.
- The built pair must match the declared descriptor.
- Duplicate `TransportKind` registrations are rejected before `build()`.
- Static support belongs in the descriptor.
- Dynamic conditions such as permissions, radio state, entitlement, multicast availability, or port exhaustion do not change static support. They surface through start results and Decision 3’s feature state.
- Synchronous construction failures remain typed initialization exceptions; `start()` failures remain `TransportStartFailed`.
- A factory should not return `null` for “unsupported.”
- A platform that cannot provide a transport either does not register its factory or declares no valid capability and is rejected during configuration.

This makes support discoverable without conflating it with momentary availability. It is a source/ABI change for factory implementers, and changing `data` to nullable requires Kotlin call-site migration even where the JVM getter descriptor is similar.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve TRANSPORT-FACTORY-API-01 declared capabilities`
2. `Approve TRANSPORT-FACTORY-API-01 typed build outcome without descriptors`
3. `Approve TRANSPORT-FACTORY-API-01 nullable factory results`
4. `Approve TRANSPORT-FACTORY-API-01 parallel v2 factory interface`

## 6. Authenticated message-metadata envelope

### Exact problem

`P2pMessage.Text.metadata` and `Binary.metadata` are public, but neither legacy v1 nor authenticated secure v2 sends them. `Chunker` writes only content bytes, and `Reassembler` constructs received messages with empty metadata.

Blocked scope:

- `PROTO-08`.
- No separately numbered gap; the tracker requires envelope, downgrade, compatibility, malformed-input and metadata-boundary tests.
- APIs: `P2pMessage.Text`, `P2pMessage.Binary`, `P2pSession.send`.
- Wire components: `Chunker`, `Reassembler`, frame/protocol HELLO feature negotiation, secure-v2 protocol.
- All platforms must produce identical bytes and validation outcomes.

### Options and trade-offs

| Option | Compatibility/API | Security/reliability | Performance/platform/future |
|---|---|---|---|
| A. Negotiated secure-v2 envelope | No signature break; behavioral/wire change | Metadata and content context are authenticated; downgrade can fail closed | Small header/digest overhead; strongest extensibility |
| B. Remove/deprecate metadata | Public source break and migration | Eliminates misleading contract | Simplest wire, poor feature capability |
| C. Keep metadata local-only | Compatible | Surprising and easy for apps to misuse | No implementation cost; finding remains |
| D. New protocol major | Cleanest separation | Strong fail-closed boundary | Largest deployment and interoperability cost |

### Recommended envelope

Choose Option A. Negotiate an authenticated feature such as `app-message-envelope-v1` inside the encrypted HELLO. Do not change secure preface bytes or fall back to plaintext.

Illustrative logical structure:

```text
APP_MESSAGE_V1 {
  envelopeVersion: 1
  messageType: TEXT | BINARY
  messageId: 16 bytes
  senderPeerId: UTF-8
  recipientPeerId: UTF-8
  sequence: unsigned 64-bit
  sentAtEpochMillis: optional informational field
  metadata: sorted list of { key, value }
  contentLength: unsigned 64-bit
  contentSha256: 32 bytes
  content: exact message bytes
}
```

Authentication rules:

- The complete frame bytes are already encrypted and authenticated by the Noise secure channel.
- Message type, ID, chunk information, sender, recipient, sequence, metadata, content length, digest, and envelope version are therefore authenticated.
- Sender/recipient IDs must match the authenticated session identities.
- Frame message ID must match the envelope ID.
- Sequence numbers start at zero per direction/session and are strictly increasing.
- Duplicate or out-of-order sequence numbers are rejected.
- Fresh Noise keys protect cross-session replay. A bounded per-session message-ID set handles accidental duplicate logical messages.
- `sentAtEpochMillis` should be optional and informational. It must not control acceptance because device clocks are not trustworthy.
- SHA-256 covers exact content bytes. It is supplementary corruption detection; Noise AEAD already supplies cryptographic integrity.
- Metadata itself is authenticated by the envelope and is not included in the content digest.

Canonicalization:

- Use a fixed canonical binary/TLV format, not JSON object ordering.
- Fixed big-endian integer encoding.
- Explicit length prefixes.
- UTF-8 text with the existing strict validation.
- Sort metadata by raw UTF-8 key bytes.
- Reject duplicate keys.
- Do not perform implicit Unicode normalization.
- Recommended limits: 64 entries, 256 UTF-8 bytes per key, 4 KiB per value, and 32 KiB aggregate metadata.

Compatibility and failures:

- Legacy plaintext v1 remains explicitly metadata-free.
- A secure peer not advertising the feature may receive old raw DATA only when metadata is empty.
- Sending non-empty metadata to such a peer fails with typed `UnsupportedFeature`; it must not silently discard metadata.
- After both peers advertise the feature, malformed envelopes, identity mismatch, sequence replay or digest mismatch close the session with a typed protocol/authentication error.
- Authentication failure never retries as plaintext.
- No new HMAC or identity-key signature is required while the envelope remains inside Noise. Identity keys should not be repurposed as HMAC keys.

The behavioral change is intentional: secure peers will actually receive metadata. Apps relying on its current omission need release notes.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve PARSE-META-01 negotiated authenticated envelope`
2. `Approve PARSE-META-01 remove metadata`
3. `Approve PARSE-META-01 permanently local-only metadata`
4. `Approve PARSE-META-01 new protocol major`

## 7. Retained pending-transfer-offer API

### Exact problem

`P2pSession.incomingFiles` is a replay-zero `SharedFlow`. Offers emitted before subscription are lost.

Increasing replay does not solve this:

- terminal offers cannot be selectively removed from replay;
- rebuilding the replay cache re-emits duplicate offers to current collectors;
- third-party implementations cannot reproduce the required subscription hook with public coroutine APIs.

Blocked scope:

- `FILE-05`.
- Receiver-observability conjunct of `FILE-06`.
- Test gaps `PT-T12`, `PT-T13`, and the retained-offer portion of `PT-T21`.
- APIs: `P2pSession.incomingFiles`, `P2pFileOffer`.
- Core: `FileTransferDispatcher`, `IncomingFileSession`.
- Samples and Swift consumers must switch from ephemeral receipt to retained state.

### Options and trade-offs

| Option | Compatibility/API | Reliability/security | Performance/platform/future |
|---|---|---|---|
| A. Add retained `pendingFileOffers` and deprecate event flow | Additive for consumers; implementers migrate | No lost/stale offers; deterministic terminal removal | Tiny bounded list; excellent UI and Swift behavior |
| B. Replace `incomingFiles` directly with StateFlow | Cleanest final API | Reliable | Broad source/ABI break |
| C. SharedFlow with replay | Small change | Stale entries and duplicate live emissions | Incorrect lifecycle semantics |
| D. Persist offers across process restarts | Large storage/privacy API | Can survive process death | Requires encrypted storage, remote liveness and resume protocol |

### Recommended API and retention rules

Choose Option A:

```kotlin
val pendingFileOffers: StateFlow<List<P2pFileOffer>>

@Deprecated("Observe pendingFileOffers")
val incomingFiles: SharedFlow<P2pFileOffer>
```

Rules:

- Insert a validated offer into retained state before starting its response timer.
- Retain it until exactly one of: accept commit, reject, timeout, remote cancel, session close, or protocol invalidation.
- Default retention deadline remains `offerTimeoutMillis`, currently 30 seconds.
- Keep the existing maximum of 64 pending incoming offers per session.
- Cap retained encoded offer metadata at the existing 32 KiB per offer, therefore at most 2 MiB of retained offer metadata per session.
- Declared file size is validated against `maxFileSizeBytes`, but disk space is not reserved until acceptance.
- Offers are ordered by admission sequence, not callback scheduling.
- Exact duplicate `(authenticated sender, transferId, payload)` is idempotent.
- Same ID with conflicting metadata is a transfer protocol violation.
- `accept` and `reject` are atomic one-shot operations. Concurrent losers receive the existing already-terminal failure.
- Once acceptance commits, the offer disappears from pending state and the returned transfer handle owns progress.
- Late accept after expiration fails and cannot revive the offer.
- Session close rejects or cancels every pending offer and clears the retained list.
- No process-restart persistence in this version. Sessions and transfer protocol state are already process-local; persisting names, MIME types and sender identities would introduce privacy and stale-liveness problems without a resume protocol.
- Snapshots must follow Decision 4’s cast-proof immutability.
- `incomingFiles` can continue to emit only newly admitted offers during migration; it is no longer authoritative.

This is reliable for Kotlin UI, Java observers and Swift collectors without storing source data or file contents.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve XFER-OFFER-API-01 retained pendingFileOffers`
2. `Approve XFER-OFFER-API-01 replace incomingFiles with StateFlow`
3. `Approve XFER-OFFER-API-01 replayed SharedFlow`
4. `Approve XFER-OFFER-API-01 persistent cross-process offers`

## 8. Typed transfer-error API

### Exact problem

Current transfer failures are mapped too broadly:

- Local source/sink I/O commonly becomes `ConnectionFailed`.
- Transfer-specific protocol errors can become session-closing `ProtocolError`.
- Rejection, cancellation and several timeouts are encoded only as strings in terminal state.
- Unexpected causes are now preserved, but their public classification remains misleading.

Blocked scope:

- `FILE-11`.
- No numbered explicit gap; typed cause-preservation and external-consumer compatibility tests are required.
- APIs: `P2pError`, `FileTransferState`, `P2pSession.sendFile`, `P2pFileOffer.accept`.
- Core dispatcher, source/sink helpers and Decision 9’s future digest/commit failures.
- Kotlin sealed exhaustiveness, Java `instanceof`, Swift exported error inspection.

### Current and proposed mapping

| Failure | Proposed classification | Transfer/session effect |
|---|---|---|
| Socket/control/data write failure | `TRANSPORT` | Transfer terminal; session may reconnect/fail separately |
| Remote socket disappears | `REMOTE_DISCONNECTED` | Retry on a new/reconnected session |
| Offer/data/commit timeout | `TIMEOUT`, with phase | Transfer terminal |
| Caller cancellation | `FileTransferState.Cancelled` | Not wrapped as an error |
| Remote/app rejection | `FileTransferState.Rejected` | Not an error |
| Invalid name, size, MIME or offer metadata | `INVALID_METADATA` | Reject isolated offer; repeated hostile violations may close session |
| Noise/record authentication failure | Existing `AuthenticationFailed` | Session terminal; every active transfer fails causally |
| SHA-256 mismatch | `INTEGRITY` | Transfer terminal; never silently retry |
| Sender source changed after digest | `SOURCE_CHANGED` | Transfer terminal; caller must prepare a new source |
| Source read failure | `SOURCE_IO` | Usually retryable after fixing/reopening source |
| Receiver write/flush/fsync/rename failure | `STORAGE` with operation | Retryability depends on storage condition |
| Peer lacks negotiated feature | `UNSUPPORTED_FEATURE` | Terminal for this attempted transfer, session stays usable |
| Transfer ordering/state violation | `TRANSFER_PROTOCOL` | Isolated where safe; structural/authentication failures close session |
| Oversized preflight request | Existing `PayloadTooLarge` | No transfer handle is created |

### Options and trade-offs

| Option | Compatibility/API | Usability/extensibility | Platform/testing |
|---|---|---|---|
| A. One structured `FileTransferFailed` subtype | One new direct sealed branch; exhaustive `P2pError` whens break once | Stable fields and easy future extension | Best Java/Swift/Kotlin mapping |
| B. Many direct `P2pError` subclasses | Idiomatic Kotlin | Every added case expands sealed-exhaustiveness risk | Larger Swift/Java type surface |
| C. Only `FileTransferIoFailed` and `FileTransferProtocolError` | Matches minimal tracker sketch | Too coarse for digest, timeout, storage and unsupported feature | Smaller initial tests, likely another API revision |
| D. Make `P2pError` non-sealed | Allows future subclasses without sealed expansion | Consumers lose compiler exhaustiveness | Broad contract change |
| E. Keep generic errors | Compatible | Defect remains | Lowest cost |

### Recommended model

Choose Option A:

```kotlin
data class FileTransferFailed(
    val kind: FileTransferFailureKind,
    val phase: FileTransferPhase,
    val retryability: Retryability,
    val transferId: String?,
    val reason: String
) : P2pError(reason) {
    // SDK-preserved platform cause; not part of stable equality.
}
```

Stable enums should include:

```text
TRANSPORT
REMOTE_DISCONNECTED
TIMEOUT
INVALID_METADATA
AUTHENTICATION
INTEGRITY
SOURCE_CHANGED
SOURCE_IO
STORAGE
UNSUPPORTED_FEATURE
TRANSFER_PROTOCOL
```

Phases should include:

```text
OFFER, ACCEPT, SOURCE_READ, SEND, RECEIVE, VERIFY, FLUSH, DURABLE_COMMIT
```

Retryability:

```text
RETRY_SAME_SESSION
RETRY_NEW_SESSION
RETRY_AFTER_USER_ACTION
NOT_RETRYABLE
```

Important semantics:

- Every `FileTransferFailed` is terminal for that transfer.
- “Recoverable” means the app may begin a new transfer; it does not mean the failed handle resumes.
- `CancellationException` continues to propagate unchanged from a cancelled API coroutine.
- Intentional transfer cancellation remains `FileTransferState.Cancelled`.
- Remote rejection remains `FileTransferState.Rejected`.
- A conforming receiver’s unanswered-offer timeout may remain a typed rejection policy; an unresponsive peer’s watchdog timeout becomes `FileTransferFailed(TIMEOUT, OFFER, …)`.
- Platform `IOException`, Android provider exceptions and Apple native errors are preserved as diagnostic causes, but portable behavior depends only on `kind`, `phase` and `retryability`.
- Swift switches on the stable kind/phase values instead of relying on Kotlin sealed-class exhaustiveness.
- Causes must never contain credentials or unbounded peer text.

Adding one new direct `P2pError` subtype is binary-additive but breaks source recompilation of exhaustive `when (error: P2pError)` expressions. This should be called out in migration notes.

The tracker’s two-subtype sketch is weaker because it would immediately become insufficient for Decision 9.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve XFER-ERROR-API-01 structured FileTransferFailed`
2. `Approve XFER-ERROR-API-01 many typed subclasses`
3. `Approve XFER-ERROR-API-01 two minimal subtypes`
4. `Approve XFER-ERROR-API-01 unseal P2pError`

## 9. Receiver durability acknowledgement and SHA-256 protocol

### Exact problem

Today the sender sends `FILE_DONE` and immediately marks itself `Completed`. The receiver may subsequently fail to write or flush its sink, and no frame communicates that failure back.

The current protocol also checks byte count but not exact content. More importantly, the public sender accepts a one-shot `RawSource`; calculating a digest before the offer is impossible without:

- a repeatable/snapshot source;
- a caller-supplied digest; or
- staging the complete stream.

Likewise, `P2pFileOffer.accept(RawSink)` only lets the SDK call `flush()`. It cannot truthfully claim fsync, atomic rename, or durable persistence for an arbitrary sink.

Blocked scope:

- `FILE-04`, sender completion before receiver durability.
- `FILE-13`, exact-content digest.
- `PT-T16`, receiver flush/durability failure result at sender.
- `PT-T18`, source mutation/digest mismatch.
- Protocol, dispatcher, streaming sender/receiver, file-transfer configuration and platform file helpers.
- Public source and destination APIs.
- JVM/Desktop, Android, Apple, Swift and CLI/sample file paths.

### Protocol options and trade-offs

| Option | Compatibility | Integrity/reliability | Performance/platform/maintenance |
|---|---|---|---|
| A. Negotiated prepared snapshot + durable commit | New additive APIs and secure feature; old secure peers fail closed | Resolves both findings honestly | Pre-hash cost; non-repeatable sources may need staging |
| B. Streaming digest sent only at end | Preserves one-shot source and one-pass performance | Detects receiver mismatch but not mutation relative to an intended pre-send snapshot | Simpler, does not fully close `PT-T18` |
| C. Receiver acknowledgement only | Small wire change | Resolves durability outcome only; no content integrity | Lowest overhead |
| D. SHA-256 only | No receiver commit | Sender still completes before receiver durability | Does not resolve `FILE-04` |
| E. New protocol major | Cleanest wire separation | Strongest hard boundary | Largest rollout and interoperability break |
| F. Keep current protocol | Compatible | Both findings remain | No cost |

### Recommended API prerequisites

Choose Option A and introduce two explicit ownership abstractions.

A prepared source:

```kotlin
interface PreparedFileSource {
    val sizeBytes: Long
    val sha256: Sha256Digest
    fun open(): RawSource
}
```

A transactional destination:

```kotlin
interface FileTransferDestination {
    fun openSink(): RawSink
    suspend fun commit()
    suspend fun abort(cause: FileTransferFailed?)
}
```

Source rules:

- Platform File/URI helpers calculate SHA-256 before sending.
- A seekable source can be hashed and reopened.
- A non-repeatable URI/stream must be staged to bounded application cache or supplied with a caller-prepared digest/source.
- While streaming, the sender calculates SHA-256 again and compares it with the offered digest. A mismatch means `SOURCE_CHANGED`.
- Memory remains O(chunk size); regular repeatable files require two reads but no whole-file buffering.
- The existing raw `sendFile(..., RawSource)` overload remains available for explicit legacy mode but is deprecated for guaranteed secure transfer. Secure durability/integrity mode must not silently claim guarantees it cannot provide.

Destination rules:

- The SDK writes and hashes exact incoming bytes.
- It verifies size and SHA-256.
- It flushes the SDK buffer.
- It calls `destination.commit()`.
- A production file destination performs platform-appropriate close/fsync/atomic rename and, where available, parent-directory synchronization.
- Only after `commit()` succeeds may the receiver send a durable commit.
- Arbitrary `RawSink` acceptance cannot advertise durable persistence. Keep it deprecated as a flush-only compatibility API.

This is an additive signature design, but enabling fail-closed secure durability by default is a behavioral breaking change for old callers and peers.

### Negotiation

Add authenticated HELLO features such as:

```text
app-message-envelope-v1
file-commit-sha256-v1
```

Rules:

- Both peers must advertise `file-commit-sha256-v1`.
- Negotiation occurs inside the Noise-authenticated session.
- No fallback to plaintext or unauthenticated SHA-256.
- If a secure peer lacks the feature, secure file transfer fails with `UNSUPPORTED_FEATURE`.
- Legacy v1 can retain documented old transfer semantics but must not call itself authenticated or durable.

### Example message structures

These are logical examples. The production encoding should be canonical binary with fixed lengths and strict bounds.

```text
FILE_OFFER_V1 {
  transferId: 16 bytes
  schemaVersion: 1
  name: UTF-8
  sizeBytes: u64
  mimeType: optional UTF-8
  digestAlgorithm: SHA256
  contentDigest: 32 bytes
  requiredCompletion: DURABLE_COMMIT
  resumeSupported: false
}
```

```text
FILE_ACCEPT_V1 {
  transferId: 16 bytes
  acceptedOffset: 0
}
```

```text
FILE_FINISH_V1 {
  transferId: 16 bytes
  sizeBytes: u64
  chunkCount: u32
  contentDigest: 32 bytes
  offerHash: 32 bytes
}
```

```text
FILE_COMMIT_V1 {
  transferId: 16 bytes
  status: COMMITTED
  sizeBytes: u64
  contentDigest: 32 bytes
  offerHash: 32 bytes
}
```

Failure response:

```text
FILE_RESULT_V1 {
  transferId: 16 bytes
  status: FAILED
  failureCode: DIGEST_MISMATCH | STORAGE_FAILURE | PROTOCOL_FAILURE
  phase: VERIFY | FLUSH | DURABLE_COMMIT
  boundedReason: optional UTF-8
}
```

`contentDigest` covers only exact file bytes. Name, MIME type, size, sender, recipient, transaction ID, algorithm and required completion mode are separately authenticated by Noise. `offerHash` binds FINISH and COMMIT to the exact canonical offer.

### Step-by-step sender/receiver sequence

1. Secure Noise handshake completes and authenticates both peers.
2. Encrypted HELLO negotiation confirms `file-commit-sha256-v1`.
3. Sender prepares a stable source and calculates its expected SHA-256.
4. Sender emits authenticated `FILE_OFFER_V1`.
5. Receiver validates transfer ID, metadata, size, algorithm, quota and pending-offer capacity.
6. Receiver inserts the offer into retained `pendingFileOffers`.
7. Receiver either rejects with a typed `FILE_REJECT`, or accepts with a transactional destination and sends `FILE_ACCEPT_V1`.
8. Sender streams ordered `FILE_DATA` frames from offset zero while calculating SHA-256 again.
9. Frames must remain ordered and use stable transfer ID, total chunk count and last-chunk semantics.
10. If the streamed source digest differs from the offered digest, sender sends failure/cancel and ends with `SOURCE_CHANGED`.
11. Sender sends authenticated `FILE_FINISH_V1`.
12. Receiver verifies the exact transfer ID, byte count, chunk order, final-chunk position, SHA-256, and canonical offer hash.
13. Receiver flushes its buffer.
14. Receiver calls `destination.commit()`.
15. Only after successful durable commit does the receiver send `FILE_COMMIT_V1`.
16. Sender verifies the commit fields and only then enters `Completed`.
17. If verify, flush or commit fails, receiver aborts/deletes the partial destination and sends typed `FILE_RESULT_V1`.
18. Sender enters `Failed` with the corresponding structured transfer error.

### Retry, duplicates and ordering

- Initial version has no partial resume; accepted offset must be zero.
- A retry creates a new transfer unless the same transaction ID is deliberately retried.
- Exact duplicate offer with identical authenticated sender, ID, digest and metadata is idempotent.
- A conflicting reuse of an ID is a protocol failure.
- Duplicate COMMIT is idempotent.
- Out-of-order DATA, FINISH before complete data, DATA after FINISH, or COMMIT without FINISH is rejected.
- Transfer-local ordering failures should fail that transfer where parser/session safety remains intact.
- Structural framing or authentication failures remain session-terminal.

### Timeouts

- Offer decision: existing `offerTimeoutMillis`, currently 30 seconds.
- Accepted idle deadline: existing configured derived deadline.
- Accepted overall deadline: existing derived deadline.
- Add a distinct commit deadline, recommended default 30 seconds.
- Sender remains non-terminal while waiting for COMMIT.
- Commit timeout produces `FileTransferFailed(TIMEOUT, DURABLE_COMMIT, …)`.
- No existing timeout should be increased to mask failures.

### Crash recovery

Initial scope should be explicit:

- If the receiver crashes before durable commit, no COMMIT exists; sender fails or times out.
- If the receiver durably commits but crashes before COMMIT reaches the sender, receiver data may be safe while sender observes an ambiguous failure. Sender must not claim success.
- Automatic process-restart resume is not included.
- Temporary receiver files require startup cleanup.
- True exactly-once recovery would require durable journals on both peers keyed by authenticated sender fingerprint, transfer ID and digest. That is a separate persistence/privacy design.
- The protocol’s stable transaction ID permits such a future extension without changing digest semantics.

### SHA-256 security limitation

SHA-256 by itself does not authenticate anything. On plaintext v1, an attacker can replace both content and digest.

For authenticated secure v2:

- Noise AEAD authenticates the offer, data, digest, finish and commit.
- No additional HMAC is required.
- Do not derive an HMAC key from the long-term identity key.
- A signature is unnecessary unless future requirements include offline verification, forwarding through untrusted intermediaries, or non-repudiation.
- SHA-256 primarily detects source mutation, implementation errors, storage corruption and transaction mixups; authenticated transport prevents an on-path attacker from replacing the digest.

### Required owner response

Choose exactly one:

1. **Recommended:** `Approve XFER-PROTO-01 negotiated durable commit + prepared SHA-256 snapshot`
2. `Approve XFER-PROTO-01 durable commit + streaming final digest`
3. `Approve XFER-PROTO-01 receiver acknowledgement only`
4. `Approve XFER-PROTO-01 new protocol major`
5. `Approve XFER-PROTO-01 SHA-256 only without durable commit`

The tracker’s shorter previous wording, `Approve XFER-PROTO-01 receiver commit + SHA-256 digest`, is ambiguous about source and destination ownership. Choice 1 above is the production-ready interpretation.

## Dependency map

| Decision | Blocked finding rows unlocked | Explicit numbered gaps unlocked | Important downstream relationship |
|---|---|---|---|
| 1. Data transport stop | Remaining data-start conjunct of `CORE-11` | Remaining `CORE-T09` conjunct | Completes partial-start rollback and restart/rebind tests |
| 2. Provisioning close | `CORE-24` | None separately numbered | Final Android/Desktop/Apple/unsupported manager disposal integration |
| 3. Feature states | `CORE-15` | None separately numbered | Best finalized after Decision 5 defines static transport support |
| 4. Immutable models | Remaining public portion of `CORE-17` | None separately numbered | Supplies immutable state values for Decisions 3, 6 and 7 |
| 5. Factory capabilities | `CORE-27`; duplicate-kind conjunct of `CORE-28` | None separately numbered | Allows correct `Unsupported` state in Decision 3 |
| 6. Metadata envelope | `PROTO-08` | No separately numbered row | Should share authenticated HELLO feature negotiation with Decision 9 |
| 7. Retained offers | `FILE-05`; receiver conjunct of `FILE-06` | `PT-T12`, `PT-T13`, retained-offer conjunct of `PT-T21` | Should precede the new transactional destination flow in Decision 9 |
| 8. Typed transfer errors | `FILE-11` | None separately numbered | Defines the error mapping used by Decision 9 |
| 9. Digest and durable commit | `FILE-04`, `FILE-13` | `PT-T16`, `PT-T18` | Depends operationally on Decisions 7 and 8; shares wire negotiation with 6 |

Recommended implementation order after approval:

```text
Decisions 1 + 2       lifecycle batch
Decision 4            immutable public values
Decision 5 → 3        factory capabilities, then feature state
Decision 7 → 8        retained offers, then typed failures
Decisions 6 + 9       one negotiated authenticated wire batch
```

Approving all nine does not finish every remediation blocker. Physical Android/Apple evidence, hostile-network testing, runtime UI/device matrices, professional cryptographic audit, credentialed publication, and remote push authorization remain external. `SCM-PUSH-01` also remains unapproved; no remote change or push is authorized by any of the nine design approvals above.
