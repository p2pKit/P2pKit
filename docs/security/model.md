# Security model

## Scope and assumptions

This model describes the maintained source beside this document, not every
published version. A review or validation campaign must freeze the exact commit,
artifacts, dependencies and platform configuration, and bind these source/test
references to that commit. It is an input to the
[cryptographic review package](../validation/cryptographic-audit-preparation.md),
not a completed professional assessment or a complete byte-level wire specification.

Assume the application, its in-process extensions and its authorized pin source
are trusted; the OS, cryptographic providers/RNG and protected storage behave as
specified; and the transport supplies an ordered byte stream. Applications still
own lifecycle, protected diagnostic handling, business authorization and validation
of decrypted content. A broken assumption is not repaired by successful encryption.

## Default profile

P2pKit `0.7` defaults to authenticated protocol v2 using
`Noise_XX_25519_ChaChaPoly_SHA256`. It provides confidentiality, integrity,
peer key possession, authenticated metadata, replay protection, and downgrade
resistance for protocol records. Authenticated application metadata and the
application-envelope replay checks below apply when the envelope feature is
negotiated; the secure profile and optional features are not interchangeable.

`PeerAuthorizationPolicy.RejectUnknown` is the fail-closed default. A caller
must supply an exact trusted fingerprint or configure an approved pin. Pairing
QR text and full fingerprints must be exchanged through a trusted out-of-band
channel. Display names, peer IDs, mDNS TXT records, short codes, and `AppId`
values are public claims and are not authorization.

## Assets

- Persistent X25519 private identity keys, ephemeral handshake keys and session keys.
- Full trusted fingerprints, authorization pins and their binding to the intended peer.
- Message/file contents, authenticated metadata and integrity of transfer results.
- Destination data and publication/durability state; sender success must not be
  confused with arbitrary future survival across every filesystem or power failure.
- Availability of discovery, connections, transfer capacity and application resources.
- Privacy of diagnostics, exports, crash reports and the application data they can expose.

## Actors and attacker capabilities

| Actor | Capability and boundary |
| --- | --- |
| <a id="actor-passive"></a>Passive network observer | Can observe addresses, discovery, timing and traffic sizes. Secure records protect content, not traffic-analysis or discovery privacy. |
| <a id="actor-network"></a>Active network/discovery attacker | Can forge discovery, intercept, modify, drop, replay or delay traffic. Authentication/pins reject unauthorized channels and record modification; they do not provide connectivity or fair admission. See the discovery limitation below. |
| <a id="actor-same-app"></a>Unauthorized same-AppId peer | Can choose the public AppId and generate a valid key. Key possession alone does not authorize it: the default requires a trusted fingerprint. The explicit-risk policy below deliberately changes admission. |
| <a id="actor-authorized"></a>Malicious authorized peer | Can send hostile but authenticated input and intentionally consume resources. Bounds and parser checks remain necessary; there is no guarantee of benign intent, business authorization, honest destination behavior or safe application content. |
| <a id="actor-local"></a>Co-resident unprivileged application | May attempt to read or alter identity files and diagnostics. OS access controls and platform/host storage are the boundary; confidentiality of arbitrary app-created copies or exports is not supplied by the transport. |
| <a id="actor-privileged"></a>Compromised OS/root or in-process code | Can inspect memory or misuse keys and trusted APIs. P2pKit is not a sandbox and makes no endpoint-compromise guarantee. A malicious custom provider or injected identity store crosses the same trusted-process boundary. |
| <a id="actor-supply-chain"></a>Supply-chain or diagnostic consumer attacker | Can target dependencies, build inputs, exported data or viewers. Release/provenance checks and application-side validation are separate controls, not consequences of a successful Noise handshake. |

## Trust boundaries

| Boundary | Required separation |
| --- | --- |
| <a id="boundary-discovery"></a>Discovery to admission | Names, endpoints, peer IDs and advertised fingerprints are routing claims, never approval. Only a trusted out-of-band/application decision supplies authorization pins. |
| <a id="boundary-raw"></a>Raw transport to secure session | The security engine owns the sole raw reader and establishes/authenticates the channel before the protocol reader is created. Provider code itself is trusted, not remotely sandboxed. |
| <a id="boundary-storage"></a>Memory to persistent identity | Platform storage or the host-provided JVM store protects records and concurrent updates. Identity failures are typed and fail closed; reset is explicit and invalidates peer approval. |
| <a id="boundary-application"></a>Authenticated peer to application | Verified key/record identity does not make metadata, files or messages safe. The app must bound and validate inputs and implement its own authorization and acknowledgements. |
| <a id="boundary-destination"></a>Transfer to destination/OS | Completion depends on the destination callback's durability contract. Custom callbacks and filesystem/OS behavior are trusted inputs, not proven by an encrypted COMMIT. |

## Implemented properties and authored negative checks

These are **source enforcement and authored test assertions**, not fresh test
results, formal proof, independent interoperability or professional cryptographic
assurance. A negative test demonstrates a particular rejection, not that every
attack on the property has been excluded. See the
[validation authority](../validation/README.md#current-status) for campaign status.

| Claimed property | Enforcement in current source | Specific authored negative assertion | Scope / residual risk |
| --- | --- | --- | --- |
| Confidentiality of secure records | [Noise handshake/cipher][noise], [record codec][records] and [secure connection][secure-connection]; [session setup][sessions] establishes security before creating a protocol reader. | [SecureV2TransportTest][transport-tests] `queuedTamperedRecordIsClassifiedBeforeSecureStateBecomesTerminal` rejects changed ciphertext with authentication failure rather than delivering plaintext. | Relies on provider/RNG/key secrecy. This assertion checks fail-closed delivery, not a proof of the cipher; discovery, sizes and timing remain visible. |
| Integrity and terminal record failure | [Noise cipher][noise] authenticates associated data/ciphertext and destroys failed state; [secure connection][secure-connection] publishes the typed terminal failure. | [NoiseXXHandshakeTest][noise-tests] `cipherAuthenticationAndNonceFailuresAreTerminal` rejects a changed tag and refuses even the original valid ciphertext after failure; it also rejects nonce exhaustion and reuse of that failed state. | Does not make an authorized endpoint honest or provide durable application-level delivery. |
| Peer key possession and approved identity | [Secure-v2 engine][engine] authorizes the Noise-authenticated static key; [identity derivation][identity] binds peer identity to AppId and the key fingerprint, not discovery text. | [AuthenticatedV2SecurityEngineTest][engine-tests] `rejectUnknownDoesNotTreatExpectedPeerIdAsAuthorization`, `pinnedOnlyRejectsWhenNoConfiguredFingerprintMatches` and `differentExactAppIdsCannotCompleteTheHandshake` reject those unauthorized/mismatched cases. | Trusted full pins/OOB exchange remain essential. AppId and possession of a key do not prove human/product identity. |
| Authenticated application metadata | [Envelope codec][envelopes] binds identities, message ID, sequence, length, digest and bounded metadata inside encrypted records. | [SecureMessageEnvelopeTest][envelope-tests] `digestTamperIdentityMismatchAndSequenceReplayFailClosed` rejects content/identity/frame-ID mismatch; `malformedAuthenticatedMetadataTextIsNormalizedBeforeStateCommit` rejects invalid metadata without consuming replay state. | This is the negotiated envelope feature, not a promise that every secure peer supports it. Decrypted values still need application validation. |
| Replay protection | [Noise cipher][noise] maintains per-direction nonces; [envelope codec][envelopes] and [protocol session state][protocol-state] require the next sequence and bound the recent message-ID window. | [SecureMessageEnvelopeTest][envelope-tests] `digestTamperIdentityMismatchAndSequenceReplayFailClosed` rejects a repeated sequence and a duplicate recent ID even at the next sequence. | State is per connection epoch, not persistent application deduplication or global message-ID uniqueness. The recent-ID window is bounded. |
| No automatic security downgrade | [Secure-v2 handshake driver][driver] rejects invalid prefaces; [session setup][sessions] selects one engine from local SecurityMode, without remote fallback; [protocol feature state][protocol-state] preserves negotiated envelope use. | [SecureV2TransportTest][transport-tests] `unsupportedPrefaceClosesPumpWithoutNoiseOrPlaintextFallback` closes on an unsupported preface; [SecureMessageEnvelopeTest][envelope-tests] `negotiatedReceiverRejectsRawDataDowngrade` rejects raw DATA once envelopes are negotiated. | An explicit local deprecated plaintext configuration is still possible and is not interoperable with v2. Failures must not cause the app to reconfigure to plaintext. |

[noise]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseXXHandshake.kt
[records]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseRecordCodec.kt
[secure-connection]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseSecureRawConnection.kt
[sessions]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt
[engine]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/AuthenticatedV2SecurityEngine.kt
[identity]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/security/IdentityDerivation.kt
[envelopes]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/AppMessageEnvelope.kt
[protocol-state]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/ProtocolFeatures.kt
[driver]: ../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/SecureV2HandshakeDriver.kt
[transport-tests]: ../../library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/security/noise/SecureV2TransportTest.kt
[noise-tests]: ../../library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/security/noise/NoiseXXHandshakeTest.kt
[engine-tests]: ../../library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/security/AuthenticatedV2SecurityEngineTest.kt
[envelope-tests]: ../../library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/protocol/SecureMessageEnvelopeTest.kt

## Trusted transport extensions

`SecurityMode`, not a discovery record or transport-carrier default, selects the
whole-kit security engine. A custom provider must preserve the supplied profile
and exclusive raw-reader ownership; see [custom transports](../guides/custom-transports.md).
This is not a sandbox: trusted in-process extensions can access application
memory and are part of the security boundary.

## Identity storage

- Android requires `P2pKitAndroid.initialize(applicationContext)` and stores a
  Keystore-wrapped record in no-backup storage.
- Apple uses a device-only Keychain item.
- JVM applications must provide a confidential, integrity-protected,
  cross-process-safe `JvmSecureIdentityStore`. Sample in-memory stores are not
  production storage.

Identity reset produces a new peer identity and requires re-approval. Follow
[typed identity/error recovery](../guides/error-handling.md), never an automatic
reset or security downgrade after failure.

## Explicitly risky compatibility mode

`AcceptAnyAuthenticatedSameApp` authenticates possession of a key and encrypts
traffic, but it does not establish a product/user identity because `AppId` is
not secret. It is an explicit-risk policy intended only when the application
runs its own bounded admission protocol.

Deprecated `NoneForMvp` is plaintext protocol v1. It has a separate discovery
namespace and is never selected as fallback after a v2 failure.

## Discovery availability on hostile networks

Discovery is unauthenticated and **not denial-of-service resistant**. Shipped
LAN discovery admission caps live records at 256 per transport; the downstream
core discovery budget is 1,024 peers. These admission limits establish neither
fairness nor a bound on every native/resolver allocation: a hostile advertiser
can occupy the LAN slots and prevent later legitimate discoveries.
Updates and native removals still work, but continuous advertising can sustain
the lockout. Secure-v2 authentication does not protect this pre-handshake stage.

Advertised addresses and fingerprints are not trusted responder identities.
The current discovery callbacks expose neither trustworthy origin accounting
nor active-session priority. Raising the cap or evicting the oldest record is
not a security fix; a continuing attacker can consume more memory or evict
legitimate peers. The admission-policy redesign remains tracked in
[#120](https://github.com/p2pKit/P2pKit/issues/120).

Use a controlled network when discovery availability matters. For a known,
reachable peer, an out-of-band endpoint and full trusted fingerprint can be
registered with
`kit.networkProvisioning.createManualPeer(host, port, expectedFingerprint)`.
First register the platform factory in `networkProvisioning { ... }`: `jvm()`
from `p2p-network-provisioning-desktop`, `android(applicationContext)` from
`p2p-network-provisioning-android`, or `iosManualIp()` from Apple
`p2p-transport-lan`. Without a factory, the default manager rejects manual
registration. Manual peers do not consume the discovery budget.
This bypasses discovery registration, not
network disruption or connection limits; it does not guarantee connectivity.
Do not trust a discovered name/address as approval, disable pin checks, or
downgrade to plaintext to recover. Restarting discovery is not protection
against an advertiser that immediately refills the slots.

## Out of scope and limitations

P2pKit does not provide internet signaling, NAT traversal, relay protection,
accounts, human identity, application authorization, or protection from a
malicious already-authorized peer. Metadata and payloads remain untrusted
application input after decryption and must be bounded and validated.

Memory wiping is best effort on managed/native runtimes; copies, crash dumps,
OS compromise and dependency compromise are not eliminated. Android hardware
backing/StrongBox is not universal, and Keystore/Keychain accessibility choices
do not promise that an identity becomes inaccessible whenever a device locks.
Platform storage and filesystem durability differ; the JVM Windows destination
cannot supply the POSIX parent-directory fsync barrier. See the
[platform durability limits](../architecture/specification.md#file-transfer).

The six campaign areas and their exact evidence requirements remain governed by
[the validation handbook](../validation/README.md#current-status); host or
simulator tests cannot promote physical-device, hostile-network, headful/fault,
independent-interoperability or professional-review results.

Physical-device hostile-network evidence, independent secure-v2
interoperability, and a professional cryptographic audit remain pending. Do not
describe the release candidate as independently audited or fully production
validated. Report vulnerabilities through the process in
[`../../SECURITY.md`](../../SECURITY.md).
