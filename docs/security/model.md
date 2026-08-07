# Security model

## Default profile

P2pKit `0.7` defaults to authenticated protocol v2 using
`Noise_XX_25519_ChaChaPoly_SHA256`. It provides confidentiality, integrity,
peer key possession, authenticated metadata, replay protection, and downgrade
resistance for protocol records.

`PeerAuthorizationPolicy.RejectUnknown` is the fail-closed default. A caller
must supply an exact trusted fingerprint or configure an approved pin. Pairing
QR text and full fingerprints must be exchanged through a trusted out-of-band
channel. Display names, peer IDs, mDNS TXT records, short codes, and `AppId`
values are public claims and are not authorization.

## Identity storage

- Android requires `P2pKitAndroid.initialize(applicationContext)` and stores a
  Keystore-wrapped record in no-backup storage.
- Apple uses a device-only Keychain item.
- JVM applications must provide a confidential, integrity-protected,
  cross-process-safe `JvmSecureIdentityStore`. Sample in-memory stores are not
  production storage.

Identity reset produces a new peer identity and requires re-approval.

## Explicitly risky compatibility mode

`AcceptAnyAuthenticatedSameApp` authenticates possession of a key and encrypts
traffic, but it does not establish a product/user identity because `AppId` is
not secret. It is an explicit-risk policy intended only when the application
runs its own bounded admission protocol.

Deprecated `NoneForMvp` is plaintext protocol v1. It has a separate discovery
namespace and is never selected as fallback after a v2 failure.

## Out of scope and limitations

P2pKit does not provide internet signaling, NAT traversal, relay protection,
accounts, human identity, application authorization, or protection from a
malicious already-authorized peer. Metadata and payloads remain untrusted
application input after decryption and must be bounded and validated.

Physical-device hostile-network evidence, independent secure-v2
interoperability, and a professional cryptographic audit remain pending. Do not
describe the release candidate as independently audited or fully production
validated. Report vulnerabilities through the process in
[`../../SECURITY.md`](../../SECURITY.md).
