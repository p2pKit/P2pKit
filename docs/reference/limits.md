# Operational limits

This reference describes the current **0.7.0-SNAPSHOT post-RC3 source**, not a
retroactive guarantee about published RC3 binaries. Use the source and docs for
the exact version you deploy. `KiB`, `MiB`, and `GiB` are binary units; byte caps
on text mean UTF-8 bytes, while character caps mean Kotlin `String.length`
(UTF-16 code units), not displayed glyphs.

Except for the public settings below, these are **internal policy**, documented
for diagnosis and capacity planning, not consumer-tunable API or permanent
compatibility guarantees. Maintainers may tune policy in a later release,
subject to the [compatibility policy](../compatibility.md); update this reference
and its source citations in the same change. This document changes no constant,
wire version, authorization rule, or published artifact. Limits are not a
negotiated allowance: the receiving peer enforces its own policy, and all
applicable layers must accept the operation.

## Public configuration

Configure `keepAlive { ... }`, `fileTransfer { ... }`, and
`lifecycle { reconnectPolicy = ... }` in the kit DSL. Invalid local
configuration throws `IllegalArgumentException` rather than silently clamping.
File policies are applied by each session's transfer dispatcher, **not a
kit-wide disk reservation**; budget across peers in the application.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `KeepAliveConfig.pingIntervalMillis` | `10,000` ms (10 s) | Default PING interval per connected session; must be positive. | [Config.kt:15](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt#L15) |
| `KeepAliveConfig.timeoutMillis` | `30,000` ms (30 s) | PONG deadline; must exceed the PING interval. Expiry loses the connection: outgoing owner may reconnect if enabled; otherwise the session fails. | [Config.kt:16](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt#L16) |
| `FileTransferConfig.maxFileSizeBytes` | `2,147,483,648` bytes (2 GiB) | Positive per-file cap. Oversized local send throws PayloadTooLarge; the receiver rejects an oversized offer. | [FileTransferConfig.kt:15](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt#L15) |
| `FileTransferConfig.chunkSizeBytes` | `65,536` bytes (64 KiB) | Default FILE_DATA chunk; configurable in 1..4 MiB. Configured maximum file size must fit in Int.MAX_VALUE chunks. | [FileTransferConfig.kt:22](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt#L22) |
| `FileTransferConfig.offerTimeoutMillis` | `30,000` ms (30 s) | Positive offer-decision/operation-wait budget; unanswered receiver offers auto-reject. Also accepted-transfer idle and commit/ack wait; see derived deadlines below. | [FileTransferConfig.kt:32](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt#L32) |
| `FileTransferConfig.maxConcurrentIncomingBytes` | `8,589,934,592` bytes (8 GiB) | Positive sum of declared sizes of active incoming offers/transfers per session, reserved before opening a sink. Further offers are rejected; terminal transfers release accounting. | [FileTransferConfig.kt:43](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt#L43) |

On JVM/Android, `durableFileDestination(target, minimumFreeSpaceBytes)` is an
additional public storage-policy knob: the margin must be non-negative and
defaults to 64 MiB beyond the declared file size. See the
[JVM](../../library/p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/transfer/FileTransferDestinationJvm.kt#L25)
and [Android](../../library/p2p-core/src/androidMain/kotlin/dev/p2pkit/core/transfer/FileTransferDestinationAndroid.kt#L22)
factories; application-provided destinations own their storage policy.

Reconnect is **disabled by default**. [`ReconnectPolicy.Enabled`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt#L59)
requires `maxAttempts > 0` and `retryDelayMillis >= 0`; only the outgoing owner
retries, and a satisfied network-path transition can wake a parked retry early.
Clean close never reconnects. A delay is not an overall retry/connection deadline.

The accepted-transfer overall deadline is `20 × offerTimeoutMillis` (default
600 s). The sender's unanswered-offer watchdog starts after writing the offer
and adds `max(1,000 ms, offerTimeoutMillis / 4)` (default total 37.5 s), avoiding
a race with the receiver's decision timer. Both calculations saturate at
`Long.MAX_VALUE`. Source/sink callbacks have separate bounded waits; these are
not a universal deadline for application-side source preparation. A timed-out
commit can still finish a fully durable publish after its point of no return;
a missing acknowledgement is not proof that no output exists. See
[FileTransferConfig](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt#L93)
and the [destination contract](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferResources.kt#L45).

## Admission and application receive backlog

Admission limits are layered. For example, a single LAN source cannot occupy
all core handshake slots because the per-source limit is enforced first.
These are **not** supported mesh-size or whole-process memory guarantees.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS` | `16` setups | Per kit, inbound pre-handshake work only. At capacity, new inbound connections are warned about and closed; outgoing setups are exempt. | [SessionManager.kt:1825](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1825) |
| `MAX_TOTAL_ACTIVE_SESSIONS` | `64` active sessions | Refuses net-new inbound registration when active-session count reaches this threshold. Outgoing connects, terminal entries and simultaneous-open replacement are exempt; not a hard total-session ceiling. Warn and close; no required typed local application error. | [SessionManager.kt:1883](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1883) |
| `MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE` | `2` connections/source | Per LAN transport, held until handshake settlement/close. A further connection from that source is refused before core admission; source address is not authenticated identity. | [PerSourceAdmissionLimiter.kt:89](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/PerSourceAdmissionLimiter.kt#L89) |
| `MAX_TRACKED_PRE_HANDSHAKE_SOURCES` | `96` sources | Per LAN transport, bounds distinct keys with outstanding admission leases. A new source is refused at capacity; this does not authorize 192 concurrent core setups. | [PerSourceAdmissionLimiter.kt:92](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/PerSourceAdmissionLimiter.kt#L92) |
| `MAX_BUFFERED_INBOUND_CONNECTIONS` | `16` connections | Apple-only accepted-connection queue, distinct from active sessions. A connection that cannot be queued is cancelled. | [IosLanDataTransport.kt:1256](../../library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDataTransport.kt#L1256) |
| `MAX_QUEUED_APPLICATION_MESSAGES` | `64` messages | Per session, includes the message currently being emitted to incoming. Further admission fails the session and logs the receive-backlog reason. | [P2pSessionImpl.kt:1624](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt#L1624) |
| `MAX_QUEUED_APPLICATION_BYTES` | `8,388,608` bytes (8 MiB) | Same backlog: accounted payload plus UTF-8 metadata bytes. Exceeding it fails the session; excludes object/string overhead and other protocol buffers, so it is not a heap cap. | [P2pSessionImpl.kt:1625](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt#L1625) |

JVM/Android accepted-connection `callbackFlow` uses the coroutine library's
default buffer (normally 64, subject to its JVM default-buffer property), not
Apple's explicit queue policy; failed `trySend` closes the offered connection.
See [JVM accept](../../library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDataTransport.kt#L279)
and [Android accept](../../library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDataTransport.kt#L320).

Subscribe to session `incoming` promptly and keep collectors fast. It has zero
replay: with no subscriber, emitted messages are not saved for later. A slow
subscribed collector holds the dedicated delivery coroutine, while a separate
bounded application queue lets protocol control continue. Move expensive work
to an **application-owned bounded queue**, with explicit overload policy; do
not replace backpressure with unbounded launches. Successful `send()` means a
successful local write, **not** remote application processing or persistence.
Observe session state and retain sanitized logger diagnostics (`P2pLogger.NoOp`
is the default); inbound refusal need not surface as a local `P2pError`.

## Framing, messages and reassembly

These application-protocol frame limits apply after decryption in v2 and to
explicit plaintext-v1 frames. A received oversized declared frame fails with
`ProtocolError` and closes/fails the session; it is not truncated or retried in
plaintext. Smaller per-type/message limits always win over the universal cap.
This is a capacity reference, not the complete wire grammar.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `DEFAULT_CHUNK_SIZE` | `65,536` bytes (64 KiB) | Default application-message split size, not a maximum message size. Larger allowed messages/envelopes are split into multiple DATA frames. | [ProtocolConstants.kt:28](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L28) |
| `MAX_PAYLOAD_BYTES` | `4,194,304` bytes (4 MiB) | Text UTF-8 content or binary payload per message, excluding metadata. A local excess throws PayloadTooLarge; received excess is a protocol violation. | [ProtocolConstants.kt:31](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L31) |
| `MAX_APP_MESSAGE_ENVELOPE_BYTES` | `4,231,630` bytes (4 MiB + 37,326) | Authenticated encoded envelope/reassembly ceiling including identities, metadata and overhead; does not increase the content cap. Received excess fails the session. | [ProtocolConstants.kt:34](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L34) |
| `MAX_FRAME_PAYLOAD_BYTES` | `8,388,608` bytes (8 MiB) | Universal inbound frame-payload ceiling before payload buffering; not permission to send an 8 MiB DATA chunk. | [ProtocolConstants.kt:46](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L46) |
| `MAX_UNKNOWN_PACKET_PAYLOAD_BYTES` | `65,536` bytes (64 KiB) | Unknown packet payload ceiling. Within this ceiling unknown types can be skipped; exceeding it is a protocol violation. | [ProtocolConstants.kt:49](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L49) |
| `MAX_HELLO_PAYLOAD_BYTES` | `98,304` bytes (96 KiB) | Encoded HELLO ceiling, enforced before JSON parsing. A larger declared HELLO is a protocol violation, not a larger identity allowance. | [ProtocolConstants.kt:52](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L52) |
| `MAX_FILE_OFFER_PAYLOAD_BYTES` | `32,768` bytes (32 KiB) | Encoded FILE_OFFER ceiling before parsing. A larger declared offer is a protocol violation; this is not the offered file-size cap. | [ProtocolConstants.kt:55](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L55) |
| `MAX_REASON_PAYLOAD_BYTES` | `1,024` bytes (1 KiB) | ERROR / FILE_REJECT / FILE_CANCEL reason ceiling. Received excess is a protocol violation; local encoders reject rather than truncate. | [ProtocolConstants.kt:58](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L58) |
| `MAX_DATA_FRAME_PAYLOAD_BYTES` | `4,194,304` bytes (4 MiB) | One DATA or FILE_DATA chunk. A larger declared chunk is a protocol violation; envelope metadata may require another DATA chunk. | [ProtocolConstants.kt:61](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L61) |
| `MAX_TOTAL_CHUNKS` | `1,024` chunks | Per DATA message (also legacy ACK shape), not the total FILE_DATA count. Excess advertised count fails the session. | [ProtocolConstants.kt:69](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L69) |
| `MAX_PENDING_REASSEMBLIES` | `256` partial messages | Concurrent incomplete DATA messages per connection reassembler. Starting another at capacity fails the session. | [ProtocolConstants.kt:77](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L77) |
| `MAX_TOTAL_PENDING_BYTES` | `16,777,216` bytes (16 MiB) | Aggregate buffered partial DATA chunk bytes per reassembler, independently of per-message caps. Excess fails the session; not total session heap. | [ProtocolConstants.kt:88](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L88) |
| `DEFAULT_REASSEMBLY_TIMEOUT_MS` | `60,000` ms (60 s) | Partial-message inactivity threshold. Eviction runs when later inbound frames arrive, not on a dedicated timer. Silent-peer buffers are reclaimed on session teardown. | [ProtocolConstants.kt:91](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolConstants.kt#L91) |

Enforcement: [frame header/type validation](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameReader.kt#L88),
[per-packet shapes](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FrameValidation.kt#L13),
and [reassembly](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Reassembler.kt#L55).
Additional string/feature and file-name validity rules still apply; a byte
ceiling alone does not make a packet valid.

### Authenticated metadata and secure transport

Metadata bounds are separate from the 4 MiB content allowance. SDK local send
validation rejects an invalid envelope; received violations fail closed.
Secure records fragment the byte stream independently of DATA chunks.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `MAX_METADATA_ENTRIES` | `64` entries | Per authenticated message metadata map. More entries are rejected. | [AppMessageEnvelope.kt:14](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/AppMessageEnvelope.kt#L14) |
| `MAX_METADATA_KEY_BYTES` | `256` bytes | UTF-8 bytes in one metadata key; excess is rejected. | [AppMessageEnvelope.kt:15](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/AppMessageEnvelope.kt#L15) |
| `MAX_METADATA_VALUE_BYTES` | `4,096` bytes (4 KiB) | UTF-8 bytes in one metadata value; excess is rejected. | [AppMessageEnvelope.kt:16](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/AppMessageEnvelope.kt#L16) |
| `MAX_METADATA_BYTES` | `32,768` bytes (32 KiB) | Sum of UTF-8 key/value bytes per message, excluding their wire length prefixes. Excess is rejected even if each entry fits. | [AppMessageEnvelope.kt:17](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/AppMessageEnvelope.kt#L17) |
| `SECURE_RECORD_MAX_PLAINTEXT_BYTES` | `16,384` bytes (16 KiB) | Per encrypted record plaintext, not a message limit. The SDK splits larger writes into records. | [NoiseRecordCodec.kt:3](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseRecordCodec.kt#L3) |
| `SECURE_RECORD_MAX_CIPHERTEXT_BYTES` | `16,400` bytes | Record ciphertext including the 16-byte authentication tag; invalid declared length terminates secure transport. | [NoiseRecordCodec.kt:5](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseRecordCodec.kt#L5) |
| `SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES` | `4,192` bytes | Framed Noise handshake message ceiling (96 bytes + 4 KiB payload allowance); excess is rejected without downgrade. | [SecureProtocolV2Wire.kt:7](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/SecureProtocolV2Wire.kt#L7) |
| `SECURE_V2_MAX_APP_ID_UTF8_BYTES` | `1,024` bytes (1 KiB) | Secure AppId binding ceiling. create() rejects excess with SecurityConfigurationInvalid; HELLO and LAN TXT constraints can be tighter. | [SecureProtocolV2Wire.kt:5](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/SecureProtocolV2Wire.kt#L5) |

## Discovery and peer registry

Invalid or excess discovery claims are ignored, with bounded/rejection-latched
diagnostics rather than a promised per-packet public error. Discovery metadata
is unauthenticated and never a replacement for a trusted fingerprint.
Multiple constraints apply to one field: for example, LAN `app=<AppId>` must
fit the entire TXT entry, so AppId has at most 251 UTF-8 bytes on that path,
even though secure binding permits more. LAN display names are safely truncated
to fit their TXT entry; an AppId is not silently truncated.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `MAX_DISCOVERED_PEERS` | `1,024` peers | Distinct peers with discovery contributions per kit; manual-only entries are not counted. New discovered identities are ignored at capacity; existing updates/removals still work. | [PeerRegistry.kt:626](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L626) |
| `MAX_TRACKED_LAN_PEERS` | `256` peers | Earlier per-LAN-transport live-peer relay ceiling. New identities are ignored at capacity; it can bind before the core registry ceiling. | [ReliablePeerEventRelay.kt:118](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/ReliablePeerEventRelay.kt#L118) |
| `DEFAULT_STALE_TIMEOUT_MS` | `15,000` ms (15 s) | Unrefreshed discovery contributions older than this are removed unless transport-managed. LAN uses transport-managed lifetime; manual entries are exempt. Not a universal LAN peer TTL. | [PeerRegistry.kt:624](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L624) |
| `DEFAULT_EVICTION_POLL_MS` | `1,000` ms (1 s) | Core stale-eviction polling interval. Eligible stale contributions disappear on a later poll, not at an exact wall-clock instant. | [PeerRegistry.kt:625](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L625) |
| `MAX_DISCOVERY_HINTS` | `32` hints | Per discovered peer. A claim with more routing hints is rejected. | [PeerRegistry.kt:633](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L633) |
| `MAX_DISCOVERY_METADATA_ENTRIES` | `16` entries/hint | Per discovery transport hint; a claim exceeding this metadata count is rejected. | [PeerRegistry.kt:634](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L634) |
| `MAX_DISCOVERY_METADATA_KEY_CHARS` | `64` characters | Discovery metadata key length; the claim is rejected if exceeded (and its UTF-8 bound also applies). | [PeerRegistry.kt:635](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L635) |
| `MAX_DISCOVERY_METADATA_KEY_UTF8_BYTES` | `256` bytes | Discovery metadata key UTF-8 ceiling; exceeding it rejects the claim. | [PeerRegistry.kt:636](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L636) |
| `MAX_DISCOVERY_METADATA_VALUE_CHARS` | `256` characters | Discovery metadata value length; exceeding it rejects the claim. | [PeerRegistry.kt:638](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L638) |
| `MAX_DISCOVERY_METADATA_VALUE_UTF8_BYTES` | `1,024` bytes | Discovery metadata value UTF-8 ceiling; exceeding it rejects the claim. | [PeerRegistry.kt:639](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L639) |
| `MAX_DISCOVERY_HOST_CHARS` | `253` characters | Discovery hint host length; excess rejects the claim. Blank, control-bearing or whitespace-containing hosts are also invalid. | [PeerRegistry.kt:631](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L631) |
| `MAX_DISCOVERY_HOST_UTF8_BYTES` | `1,012` bytes | Discovery hint host UTF-8 ceiling; exceeding it rejects the claim. | [PeerRegistry.kt:632](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L632) |
| `MAX_MANUAL_HOST_CHARS` | `253` characters | Normalized manual host length; invalid local registration throws rather than creating a peer. | [PeerRegistry.kt:630](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt#L630) |
| `MAX_DNS_SD_TXT_ENTRY_BYTES` | `255` bytes | Whole key=value TXT entry. Oversized consumed remote fields reject the record; oversized local non-display-name fields prevent advertising. | [Lan.kt:446](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt#L446) |
| `MAX_FIELD_LEN` | `512` characters | Core HELLO/peer name and identity string ceiling; invalid local fields fail validation and invalid remote claims are rejected. Not a way to bypass smaller LAN TXT limits. | [HelloPayload.kt:39](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt#L39) |
| `MAX_FIELD_UTF8_BYTES` | `2,048` bytes (2 KiB) | UTF-8 companion ceiling for those core string fields; the character ceiling still applies. | [HelloPayload.kt:42](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt#L42) |

## Network and provisioning deadlines

These are budgets for the named phase. Queue/mutex waits, name resolution,
subsequent handshake and cleanup can add time; OS scheduling and uncooperative
native callbacks prevent treating them as hard whole-API wall-clock deadlines.
A write completing locally is still not remote processing acknowledgement.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `DEFAULT_HANDSHAKE_TIMEOUT_MS` | `10,000` ms (10 s) | Core setup budget covers Noise/authentication plus HELLO after dialing. Timeout closes setup and surfaces AuthenticationFailed (v2) or HandshakeRejected (v1); never fallback. | [Handshake.kt:120](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt#L120) |
| `TCP_CONNECT_TIMEOUT_MS` | `5,000` ms (5 s) | JVM/Android TCP connect budget shared by candidate attempts. Exhaustion fails the dial with ConnectionFailed; not the Apple budget. | [Lan.kt:174](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt#L174) |
| `MAX_DIAL_CANDIDATES` | `8` endpoints | JVM/Android selected address fan-out per dial. Further candidates are not attempted in that operation. | [Lan.kt:177](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt#L177) |
| `TCP_CANDIDATE_CONNECT_TIMEOUT_MS` | `1,500` ms (1.5 s) | JVM/Android maximum slice when multiple candidates exist, within the shared connect budget. A single candidate receives the full budget. | [Lan.kt:180](../../library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/Lan.kt#L180) |
| `CONNECT_TIMEOUT_MILLIS` | `10,000` ms (10 s) | Apple outbound NWConnection readiness wait. Timeout cancels the connection, invalidates the failed cached endpoint and throws ConnectionFailed. | [IosLanDataTransport.kt:1259](../../library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDataTransport.kt#L1259) |
| `WRITE_TIMEOUT_MILLIS` | `30,000` ms (30 s) | JVM raw socket-write watchdog. Expiry closes the socket and fails the write; excludes time waiting for the write mutex. | [JvmRawConnection.kt:267](../../library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt#L267) |
| `WRITE_TIMEOUT_MILLIS` | `30,000` ms (30 s) | Android raw socket-write watchdog, with the same close/fail behavior and mutex-wait exclusion. | [AndroidRawConnection.kt:263](../../library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidRawConnection.kt#L263) |
| `WRITE_READY_TIMEOUT_MILLIS` | `10,000` ms (10 s) | Apple raw write awaiting a Connecting-to-ready transition. Expiry cancels the connection and fails that write. | [IosRawConnection.kt:413](../../library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt#L413) |
| `WRITE_TIMEOUT_MILLIS` | `30,000` ms (30 s) | Apple send-completion wait after readiness/write serialization. Expiry cancels the connection and fails the write; not a total send deadline. | [IosRawConnection.kt:425](../../library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt#L425) |
| `OS_CALLBACK_TIMEOUT_MS` | `60,000` ms (60 s) | Android LOHS acquisition / Wi-Fi join approval wait. Expiry returns failed result/state: HotspotStopped for hosting, JoinFailed for joining; not permission to retain a late OS resource. | [AndroidNetworkProvisioningManager.kt:601](../../library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManager.kt#L601) |

## Shutdown and recovery waits

These bound **individual waits**, not a single aggregate `session.close()` or
`kit.stop()` duration. Cleanup phases can compose. A deadline reports incomplete
cleanup; it is not proof that an OS resource or non-cooperative worker is gone.
The kit retains failed ownership where supported. Keep callbacks prompt and
cancellation-cooperative, inspect cleanup errors, and do not interpret a deadline
as a successful release of storage, radios, identity leases or sockets.

| Policy or setting | Current value | Scope and observable consequence | Source |
| --- | --- | --- | --- |
| `HANDSHAKE_CLEANUP_TIMEOUT_MS` | `2,000` ms (2 s) | Per resource during incomplete-handshake rollback, including best-effort clean-close work. Expiry retains/reports cleanup failure rather than waiting indefinitely. | [SessionManager.kt:1828](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1828) |
| `SESSION_COMMIT_CLEANUP_TIMEOUT_MS` | `2,000` ms (2 s) | Per raw connection during failed session-publication rollback. Expiry reports incomplete cleanup. | [SessionManager.kt:1831](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1831) |
| `DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS` | `6,000` ms (6 s) | One reconnect discovery-refresh callback. Timeout is logged and does not itself exhaust the reconnect policy. | [SessionManager.kt:1834](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1834) |
| `SESSION_CLOSE_TIMEOUT_MS` | `10,000` ms (10 s) | Manager wait for each session/setup during background or terminal cleanup; direct public close can compose several phases. Expiry is a cleanup issue, not a clean-close guarantee. | [SessionManager.kt:1837](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1837) |
| `CLOSE_FRAME_TIMEOUT_MS` | `2,000` ms (2 s) | Best-effort CLOSE send wait. Expiry proceeds to teardown; delivery is not guaranteed. | [P2pSessionImpl.kt:1618](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt#L1618) |
| `SESSION_RESOURCE_CLOSE_TIMEOUT_MS` | `2,000` ms (2 s) | Each terminal session-resource attempt (also default application-delivery cancellation wait). Expiry reports an incomplete cleanup attempt. | [P2pSessionImpl.kt:1621](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt#L1621) |
| `SESSION_RUNTIME_CLOSE_TIMEOUT_MS` | `2,000` ms (2 s) | Final session runtime join phase. Expiry reports incomplete runtime termination; it is separate from resource waits. | [P2pSessionImpl.kt:1622](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt#L1622) |
| `STOP_START_MUTEX_TIMEOUT_MS` | `5,000` ms (5 s) | Kit stop waiting for an active startup lock. Expiry warns, records a cleanup issue and continues terminal teardown without that lock. | [P2pKitImpl.kt:1541](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt#L1541) |
| `OBSERVER_CLOSE_TIMEOUT_MS` | `5,000` ms (5 s) | Kit path-observer close wait. Expiry records incomplete observer cleanup. | [P2pKitImpl.kt:1549](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt#L1549) |
| `INTERNAL_JOB_CLOSE_TIMEOUT_MS` | `5,000` ms (5 s) | Kit internal-job cancellation/join wait. Expiry records failure and retains the destructive-identity-reset lease fail-closed. | [P2pKitImpl.kt:1552](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt#L1552) |
| `STALE_OPERATION_CLEANUP_TIMEOUT_MS` | `2,000` ms (2 s) | Each resource produced by a stale lifecycle operation. Expiry is reported; late work is not declared cleaned. | [P2pKitImpl.kt:1555](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt#L1555) |
| `RESOURCE_CLOSE_TIMEOUT_MS` | `6,000` ms (6 s) | Each kit-owned transport/provisioning close attempt. Expiry reports incomplete cleanup instead of claiming success. | [P2pKitImpl.kt:1566](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt#L1566) |
| `DEFAULT_FEATURE_OPERATION_SETTLE_TIMEOUT_MS` | `6,000` ms (6 s) | Explicit advertising/discovery stop waiting for the concurrent start owner. Expiry fails the operation with retained cleanup context. | [P2pKitImpl.kt:1608](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt#L1608) |

## Diagnose a limit hit

- **Connection refused:** correlate the receiving side's sanitized admission log
  with source, pre-handshake and active-session budgets. Stagger authorized
  connection attempts; do not weaken identity checks or expect a local typed
  error for every refused inbound socket.
- **Session fails while receiving:** distinguish protocol-limit violations from
  application-backlog overload. Reduce message/metadata size, drain `incoming`
  promptly and keep downstream work bounded. A 16 MiB partial-data cap or
  8 MiB accounted backlog is not an 8/16 MiB process-heap promise.
- **Peer disappears or is absent:** distinguish invalid/capacity-rejected
  discovery records, transport-managed loss and core stale eviction. A manual
  endpoint does not bypass authentication or connection admission.
- **Transfer fails or times out:** inspect the structured transfer failure,
  receiver policy and storage capacity. The built-in JVM/Android destinations'
  [default free-space margin](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferResources.kt#L124)
  is 64 MiB beyond the declared file size; the check is not an OS disk
  reservation or protection against later disk exhaustion. Never weaken the
  receiver's commit/ack durability boundary to bypass a timeout.

Use the [CLI/Desktop D5 resource-pressure procedure](../validation/cli-desktop-faults.md#d5--safe-resource-pressure)
only with synthetic peers and preapproved host safety limits. Static constants,
unit tests and simulator checks do not complete the
[physical/hostile-network/independent validation gates](../validation/README.md).
