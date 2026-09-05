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
registered with `createManualPeer(host, port, expectedFingerprint)` without
consuming the discovery budget. This bypasses discovery registration, not
network disruption or connection limits; it does not guarantee connectivity.
Do not trust a discovered name/address as approval, disable pin checks, or
downgrade to plaintext to recover. Restarting discovery is not protection
against an advertiser that immediately refills the slots.

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
