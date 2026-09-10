# Authenticated-v2 wire contract — candidate and current continuation

**Status: candidate-bound preparation for #133, not an independent
interoperability result or professional cryptographic assurance. External #133
remains NOT_STARTED.** This describes the committed candidates in §1, including
caller behavior that a pure codec does not establish. It does not certify a
published release, execute an independent peer, or grant repository-repair or
whole-audit readiness credit. Labeled contract questions remain separate from
observed behavior; a discrepancy with the [maintained contract](../architecture/specification.md)
is a finding to resolve, not permission to codify an implementation accident.

## 1. Candidate, scope and notation

Original source binding date: **2026-09-09 UTC**; preserved historical preparation.

| Candidate identity | Exact value |
| --- | --- |
| Commit | `9f9e57ce8df84a7bae94b13b2b500f3d8225da4e` |
| Tree | `88a3b7fe4d016c526a1256f1b456ab04dd2ed954` |
| Source review scope | Candidate byte grammar and actual caller/state boundaries; no runtime or external acceptance claim |

The original [source manifest](secure-v2-wire-candidate.sources.tsv) retains the
70 source, documentation and existing-vector inputs, Git blob SHA-1 and literal
file SHA-256 from the reviewed `9f9e57c` description. That original commit/tree
and manifest are unchanged historical bindings, not a claim about later HEADs.

### Current source continuation — 2026-09-10

| Binding | Exact value / scope |
| --- | --- |
| Intermediate source comparison | `91e8a9a287333be52ca114022b0cd6c4a9664e23` / tree `f24ef0a0bdd4faa3b22a2b2d90231ccf04f1a250`; #399 reconnect-wake ordering, no wire-contract change; source inspection only |
| Current candidate | `4a409a8f60ad4b4f23db58725f71de0523a29bf5` |
| Current tree | `f45afc779049d6557485efe77936871dfeeb70a9` |
| Current delta | #403 diagnostic owner attribution and #404 lost-transport retirement; no byte grammar, key derivation or negotiated-feature change |

The [current sparse source bindings](secure-v2-wire-candidate.2026-09-10.sources.tsv)
replace five original manifest rows and add `ReconnectTransportRetirement.kt`.
The other 65 original inputs are byte-identical: the composed current inventory
has 71 paths. Source names below resolve through that composition at `4a409a8`,
not arbitrary later source. The five current rows also record the intermediate
`91e8a9a` blobs; its earlier source-only comparison remains historical evidence.
Section 9 adds the current local retirement/terminal boundary. This continuation
is source-contract preparation, not a new independent peer, runtime result,
cryptographic review or campaign acceptance.

Relative documentation links remain navigation, not future-source certification.
The original and current source commits precede their respective documentation
updates. Review/rebind any later relevant source delta; do not silently transfer
these bindings or turn observed implementation details into new normative rules.

Scope: one ordered, reliable, bidirectional byte stream, from secure preface
through encrypted application/file traffic and termination. LAN discovery,
platform identity storage, UI, physical networking and the plaintext migration
profile are outside this byte contract. Common protocol code supplies the
rules; that fact does not prove platform/provider equivalence.

Notation: `||` means concatenation; `B[n]` means exactly n bytes; `U8`, `U16`,
`U32`, `U64` are unsigned fixed-width **big-endian** values. Supported U32/U64
counts/lengths are at most `2^31-1`/`2^63-1`; high-bit encodings are rejected,
except uninterpreted fields of unknown application types (§5). A field-specific
bound can be smaller. `str16(x) = U16(len(UTF8(x))) || UTF8(x)`. Lengths count
bytes, not characters. Literals are ASCII; `\0` in a domain string is one NUL.
KiB/MiB/GiB are binary units. Key encodings and Noise nonces follow §3, not the
big-endian length convention.

Wire text is strict UTF-8/well-formed Unicode, without normalization or case
folding. Where bounded text validation is required, reject U+0000–001F,
U+007F–009F, U+061C, U+200E/200F, U+202A–202E and U+2066–2069. Character limits
are **UTF-16 code units** (a supplementary scalar counts twice), in addition
to UTF-8 byte limits. Nonblank fields must contain a non-whitespace character
under the candidate's Kotlin `isNotBlank` rule. Do not apply this control ban to
ordinary text-message content: it only requires strict UTF-8.

Sources: `WireText.kt`, `Builders.kt`, `P2pKitImpl.kt`, `ProtocolConstants.kt`.

## 2. AppId, identities and authorization

A real kit AppId is nonblank bounded wire text, at most 512 UTF-16 units and,
for authenticated v2, at most **1,024 UTF-8 bytes**. Builder HELLO validation
also enforces its general 2,048-byte field ceiling. The pure prologue helper
can encode an empty AppId; that is a codec boundary vector, **not a legal kit
configuration**. AppIds must match exactly at both peers.

For raw static X25519 public key `S[32]` and AppId UTF-8 bytes `A`:

```text
F = SHA256("dev.p2pkit.x25519-fingerprint.v1\0" || S)
P = SHA256("dev.p2pkit.peer-id.v2\0" || U16(len(A)) || A || F)
fingerprint = "p2f1-"  || base32(F)
peerId      = "p2id2-" || base32(P)
```

`base32` is lowercase, unpadded RFC 4648 Base32; a digest produces 52
characters, with canonical zero unused bits. Fingerprints are 57 characters;
PeerIds are 58. Fingerprints are key-bound; PeerIds are also AppId-bound. They
are not hashes of a hex/base64/public-key-container representation.

Optional out-of-band pairing text, **not a handshake packet**:

```text
B = SHA256("dev.p2pkit.app-binding.v1\0" || U16(len(A)) || A)
"p2pkit:v2:p2a1-" || base32(B) || ":" || fingerprint
```

It is exactly 125 characters; its full AppId binding must match. No discovery
name/TXT record substitutes for proof of the static key or authorization.

After authenticating the remote static key, derive F/P and apply all supplied
target constraints. A mismatched expected PeerId or expected fingerprint is
`AuthenticatedIdentityMismatch` even under a permissive policy. A matching
**trusted per-connect fingerprint** authorizes; an expected PeerId alone does
not. Otherwise `RejectUnknown` rejects, `PinnedOnly` requires a matching
fingerprint digest, and explicit `AcceptAnyAuthenticatedSameApp` permits the
authenticated same-AppId peer. Rejection is `AuthorizationRejected`.
The engine also checks local key-pair/fingerprint/PeerId consistency.

Sources: `IdentityDerivation.kt`, `CanonicalIdentityText.kt`, `Identity.kt`,
`SecureIdentityService.kt`, `AuthenticatedV2SecurityEngine.kt`.

## 3. Prefaces and Noise XX

The TCP dialer is initiator I; the accepter is responder R. I writes its
preface then reads R's. R **validates I's preface before replying**. A wrong
magic/version/suite/role/flag/reserved byte aborts setup; there is no plaintext
version reply to legacy traffic, negotiation to another suite, or fallback.

| Offset | Bytes | Required value |
| ---: | ---: | --- |
| 0 | 4 | `P2KS` |
| 4 | 1 | preface format `1` |
| 5 | 1 | application major `2` |
| 6 | 1 | application minor `0` |
| 7 | 1 | suite `1` |
| 8 | 1 | role `1` = I, `2` = R; require the opposite role |
| 9 | 1 | flags `0` |
| 10 | 6 | reserved, all zero |

Locally construct, but do **not** separately transmit:

```text
prologue = "dev.p2pkit.secure-channel.v2\0"
           || U16(len(A)) || A || initiatorPreface[16] || responderPreface[16]
```

Use exact Noise name `Noise_XX_25519_ChaChaPoly_SHA256` (32 ASCII bytes):
X25519 (raw 32-byte RFC 7748 keys/u-coordinates), SHA-256, HMAC-SHA-256 and
RFC 8439 ChaCha20-Poly1305 (32-byte key, 16-byte tag). X25519 scalars/public
coordinates use that primitive's little-endian encoding, not U32/U64. Reject
an all-zero DH result. Use fresh ephemeral keys for every connection; fixed
keys are permitted only in clearly labeled public tests.

Each flight is `U16(bodyLength) || body`. The production driver requires the
following **exact** body lengths before reading the body; it does not expose
the generic Noise helper's 4,096-byte optional-payload allowance.

| Flight | Direction | Noise token order | Body |
| --- | --- | --- | --- |
| 1 | I → R | `e`, empty payload | I ephemeral public[32] |
| 2 | R → I | `e, ee, s, es`, empty payload | R ephemeral public[32], encrypted R static[48], encrypted empty payload[16] |
| 3 | I → R | `s, se`, empty payload | encrypted I static[48], encrypted empty payload[16] |

Minimal state definition sufficient to remove transcript/nonce ambiguity:

```text
h = ck = ASCII("Noise_XX_25519_ChaChaPoly_SHA256"); cipher initially unkeyed
MixHash(x): h = SHA256(h || x)
HKDF2(ck, ikm):
    t  = HMAC-SHA256(ck, ikm)
    o1 = HMAC-SHA256(t, 0x01)
    o2 = HMAC-SHA256(t, o1 || 0x02)
    return (o1, o2)
MixKey(x): (ck, k) = HKDF2(ck, x); cipher key = k; cipher nonce = 0
EncryptAndHash(p): c = EncryptWithAd(h, p); MixHash(c); return c
DecryptAndHash(c): p = DecryptWithAd(h, c); MixHash(c); return p
```

First `MixHash(prologue)`. For `e`, append/read the public key and MixHash it.
For `ee`, MixKey(DH(I ephemeral, R ephemeral)); for `es`, MixKey(DH(I
ephemeral, R static)); for `se`, MixKey(DH(I static, R ephemeral)). For `s`,
EncryptAndHash/DecryptAndHash the static public key. Finally apply
EncryptAndHash/DecryptAndHash to **the empty payload on every flight**. An
unkeyed cipher copies bytes without a nonce/tag, but still MixHash-es them;
flight 1 therefore includes a hash step for empty bytes. Failed authentication
does not advance h; it irreversibly aborts the handshake/cipher.

Keyed nonces are `00 00 00 00 || U64-little-endian(counter)`. Each successful
encrypt/decrypt increments its cipher counter. `MixKey` resets it to zero;
the static token in flight 3 consequently uses the existing counter **1**
from the `es` cipher before `se` resets it. Counters `0..2^64-2` are permitted;
`2^64-1` is reserved. Exhaustion or cryptographic failure terminalizes that
cipher; never rewind/retry ciphertext under a reused key/nonce.

After flight 3, `(kIR, kRI) = HKDF2(ck, empty)`; create separate transport
ciphers with nonce zero. First key is I→R, second R→I. The final h is the
handshake hash. I authorizes R **after flight 2 and before sending flight 3**;
R authorizes I after flight 3. No application data is handed to the protocol
before local Noise authentication/authorization completes.

Sources: `SecureProtocolV2Wire.kt`, `SecureV2HandshakeDriver.kt`,
`NoiseXXHandshake.kt`, `NoiseTypes.kt`, `AuthenticatedV2SecurityEngine.kt`.

## 4. Encrypted records form a plaintext stream

```text
record = U16(ciphertextLength) || ChaCha20Poly1305(key, nonce, AD=empty, plaintext)
```

Plaintext is 0..16,384 bytes; ciphertext including tag is 16..16,400 bytes.
The length prefix itself is **not** additional AEAD associated data. Reject
an invalid length before reading/allocating its body; never deliver plaintext
from an unauthenticated/incomplete record. Each direction has its own counter.
An empty record consumes a nonce and yields zero plaintext bytes, not EOF.

Concatenate successful plaintext records as a byte stream. An application
frame may span records, and a record may contain multiple application frames.
P2pKit splits an outbound write into at-most-16,384-byte records under a
directional lock, with an empty write producing one empty record. Neither TCP
read boundaries nor record boundaries replace application length framing.

EOF before a new record header is a raw stream close; EOF inside a two-byte
header or declared body is `NoiseTransportEofException`. Neither is a clean
**session** close without an authenticated application CLOSE (§9). A malformed
record length is published as `ProtocolError`; a bad tag as
`AuthenticationFailed`. Queued final records are authenticated before raw EOF
can mask a tamper. Nonce exhaustion is a local epoch-lifetime failure, not a
claim that the peer misbehaved. A fresh epoch requires a fresh handshake.

Sources: `NoiseRecordCodec.kt`, `NoiseSecureRawConnection.kt`,
`SingleCollectorRawPump.kt`, `SecureTerminalFailureSource.kt`.

## 5. Application frame header, packet shapes and DATA reassembly

Inside the decrypted stream, each frame has a 36-byte header followed by the
exact declared payload. **Application magic is `PP2K`, not preface `P2KS`.**

| Offset | Bytes | Field |
| ---: | ---: | --- |
| 0 | 4 | `PP2K` |
| 4 | 1 | version `2` |
| 5 | 1 | type, table below |
| 6 | 1 | flags: NEEDS_ACK=`01`, LAST=`02`, TEXT=`04`, ENVELOPE=`08` (hex) |
| 7 | 1 | reserved `0` for known types |
| 8 | 16 | opaque messageId; not a numeric UUID encoding |
| 24 | 4 | U32 chunkIndex |
| 28 | 4 | U32 totalChunks |
| 32 | 4 | U32 payloadLength |

For every known type require `totalChunks > 0` and
`0 <= chunkIndex < totalChunks`. `S` below means singleton: flags exactly
LAST, chunkIndex=0, totalChunks=1. All type maxima are enforced in addition
to the universal 8 MiB frame-payload ceiling.

| Type (hex) | Name | Maximum payload bytes | Shape/body requirement |
| --- | --- | ---: | --- |
| 01 | HELLO | 98,304 | S, nonempty JSON (§6) |
| 02 | DATA | 4,194,304 | chunk rules below; empty permitted |
| 03 | ACK | 0 | LAST only, totalChunks≤1,024; index may acknowledge any valid chunk |
| 04 / 05 | PING / PONG | 0 | S |
| 06 | ERROR | 1,024 | S, nonblank bounded reason |
| 07 | CLOSE | 0 | S |
| 10 | FILE_OFFER | 32,768 | S, nonempty (§8) |
| 11 | FILE_ACCEPT | 64 | S; secure schema requires exactly 32 bytes |
| 12 | FILE_REJECT | 1,024 | S, optional reason |
| 13 | FILE_DATA | 4,194,304 | nonempty; only LAST flag permitted |
| 14 | FILE_DONE | 0 | S, legacy completion marker, not v2 success |
| 15 | FILE_CANCEL | 1,024 | S, optional reason |
| 16 / 17 | FILE_FINISH / FILE_COMMIT | 128 each | S, nonempty (§8) |
| 18 | FILE_RESULT | 1,088 | S, nonempty (§8) |

DATA permits only the four defined flag bits; ENVELOPE cannot combine with
TEXT or NEEDS_ACK. DATA totalChunks≤1,024. For both DATA and FILE_DATA, LAST
is set **iff** chunkIndex is totalChunks−1. FILE_DATA can use up to
`2^31-1` total chunks, subject to transfer limits and ordered streaming (§8).

Unknown type: still require correct magic/version and a nonnegative payload
length≤65,536 bytes. Skip that whole frame with bounded warning; its flags,
reserved byte, chunkIndex and totalChunks are **not interpreted/validated**.
Do not resynchronize after invalid magic. A wrong version is `VersionMismatch`;
malformed known headers/oversize declarations are `ProtocolError`.

On the multi-chunk path (`totalChunks > 1`), DATA chunks of one messageId must
agree on totalChunks and TEXT/ENVELOPE/NEEDS_ACK; duplicate indices are invalid.
Out-of-order DATA chunks are allowed, then concatenated by index.
Do not confuse this with FILE_DATA, which is strictly ordered. Reassembly
limits: 256 incomplete messages, 16 MiB aggregate retained chunk bytes, and
4 MiB per raw message or 4 MiB + 37,326 bytes per encoded envelope. Stale
partials are evicted on a later read after more than 60 seconds of inactivity,
not by a dedicated timer. Normal sender chunks are 64 KiB. A zero-length raw
message uses one empty DATA chunk with LAST; a zero-length file uses none.

Candidate fast-path distinction: a singleton DATA is decoded directly without
consulting an active partial with the same ID, and does not remove that partial.
There is no immediate singleton/partial collision rejection. Complete-envelope
sequence/recent-ID checks (§7) are a separate, later boundary. Stronger
cross-shape ID exclusion is a separate contract question, not a confirmed new
defect or an approved normative exception in this draft.

Raw DATA with TEXT uses strict UTF-8; otherwise it is binary. ACK is parsed
but ignored by session routing; NEEDS_ACK does not provide retransmission,
application-delivery confirmation or file durability.

Sources: `Frame.kt`, `FrameCodec.kt`, `FrameReader.kt`, `FrameValidation.kt`,
`ProtocolConstants.kt`, `Chunker.kt`, `Reassembler.kt`, `DefaultP2pProtocol.kt`.

## 6. Encrypted HELLO and feature negotiation

Both sides send HELLO after completing their local Noise/authorization step,
then wait for the peer's HELLO. The first **emitted protocol event** must be
HELLO; skipped unknown frames/malformed HELLO bodies do not emit events.
Do not send application messages/files before HELLO is accepted.

HELLO payload is a UTF-8 JSON object with these fields:

| Field | JSON type | Rule |
| --- | --- | --- |
| appId, peerId, deviceName, platform | string | required, nonblank bounded wire text; each≤512 UTF-16 units / 2,048 UTF-8 bytes |
| supportedTransports | array of strings | required, ≤32 entries; each follows the same string bounds; empty allowed |
| protocolVersion | integer | absent defaults to 1; schema accepts 1..255, authenticated session requires 2 |
| features | array of strings | absent defaults to empty; ≤32 canonical ASCII tokens, 1..128 bytes each |

Feature tokens consist only of `[a-z0-9-]`, in strictly ascending order with
no duplicates. Unknown feature names are syntactically valid. Unknown
top-level JSON members are accepted, but **all top-level member names** must
be unique, including unknown names and escaped/literal spellings of the same
name. JSON ordering, whitespace and ordinary escapes are not canonicalized.
P2pKit emits the declaration order shown above, includes protocolVersion and
omits empty features. Exact golden JSON is one encoder output, not the only
valid wire JSON. Unknown platform names project to UNKNOWN; unknown transport
tags are ignored in the public transport set, not authentication errors.

Accept only the exact local AppId, version 2, and a peerId equal to the
authenticated key-derived remote PeerId (§2). Reject the local peer's own
identity as a remote identity. A name/transport/platform never grants trust.
Late HELLO events are ignored and do not renegotiate identities/features.

Current default advertised features, in order:
`app-message-envelope-v1`, `file-commit-sha256-v1`. Negotiated features are
the local/remote intersection. Security is **not** a feature negotiation:

- With the envelope feature, every DATA message must use ENVELOPE. A raw DATA
  frame is a protocol violation. An unnegotiated envelope is also invalid.
- Without it, ordinary text/binary DATA remains inside Noise; sending nonempty
  metadata fails locally with `UnsupportedFeature`, rather than dropping it.
- Without the file-commit feature, prepared sending fails locally with
  `FileTransferFailed(UNSUPPORTED_FEATURE, OFFER, NOT_RETRYABLE)` before an
  offer. Receiving any known file-transfer type is `ProtocolError`. There is
  no implicit legacy/flush-only transfer fallback.

**Error-boundary nuance:** malformed HELLO JSON/text, including duplicate
member names, is rejected by the decoder but warned/skipped by the caller;
it is not necessarily an immediate TCP/session failure. Setup cannot succeed
on that body. With no subsequent valid HELLO, setup times out; if the next
emitted event is not HELLO, setup is rejected. Do not invent an immediate
`ProtocolError` expectation solely from a pure decoder exception.

Sources: `HelloPayload.kt`, `JsonWireValidation.kt`, `Handshake.kt`,
`ProtocolFeatures.kt`, `DefaultP2pProtocol.kt`, `SessionManager.kt`,
`P2pSessionImpl.kt`.

## 7. Authenticated application envelope

Reassemble ENVELOPE DATA before parsing. No padding/trailing bytes:

```text
"P2ME" || U8(1) || U8(type) || U16(0) || messageId[16] || U64(sequence)
|| str16(senderPeerId) || str16(recipientPeerId) || U16(metadataCount)
|| entries || U64(contentLength) || SHA256(content)[32] || content

entry = str16(key) || U32(len(UTF8(value))) || UTF8(value)
type = 1 for UTF-8 text, 2 for binary
```

Require embedded messageId equal to the DATA header ID. Sender/recipient are
bounded nonblank wire text (HELLO string limits) and must equal the negotiated
remote/local PeerIds respectively; mismatch is `AuthenticatedIdentityMismatch`.
Metadata keys are strictly lexicographically ordered by **unsigned UTF-8
bytes** (shorter prefix first), not locale, UTF-16, insertion or signed-byte
order. Duplicate keys are invalid. No normalization is performed.

Metadata bounds:≤64 entries; key nonblank≤256 UTF-16 units and UTF-8 bytes;
value may be empty,≤4,096 units/bytes; combined key+value bytes≤32,768,
excluding the 6 bytes of length prefixes per entry. Both use bounded wire-text
validation. Content≤4 MiB; contentLength equals exactly the remaining bytes
after the digest. Verify SHA-256 over **content only**; text content is strict
UTF-8. The digest is not independent authentication; Noise protects the whole
envelope. Unknown type/version/flags, bad lengths/digest/text/order are
`ProtocolError`.

Separate inbound/outbound sequence counters start at zero per epoch. HELLO
does not consume this counter (it does consume a transport nonce). Require
exactly the next inbound sequence, not merely a greater value. The greatest
accepted/emitted sequence is `2^63-2`. Reject a messageId reused among the
last 256 accepted envelopes. This is **not** an unlimited lifetime ID set;
the sequence counter supplies monotonic replay protection.

Commit inbound sequence/ID only after complete decode, identity/digest/text
validation and immutable message construction. Commit outbound sequence only
after every frame of the message was successfully written. A failed wire
write ends that secure connection; it is not permission to retry ciphertext.
Fixed envelope overhead is 78 bytes; the general upper overhead bound is
`78 + 2*2048 + 32768 + 64*6 = 37326` bytes (actual derived PeerIds are shorter).

Sources: `AppMessageEnvelope.kt`, `ProtocolFeatures.kt`, `DefaultP2pProtocol.kt`,
`Reassembler.kt`, `P2pSessionImpl.kt`.

## 8. Authenticated durable file transfer

All file frames use messageId = transferId. These payloads are binary schemas
inside Noise, **not JSON FILE_OFFER and not application envelopes**. Require
schema version 1, exact lengths/no trailing bytes and each embedded transferId
equal to the frame ID. No resume offset other than zero is supported.

| Packet | Exact payload grammar |
| --- | --- |
| OFFER | `"P2FO" || U8(1) || U8(1) || U8(1) || U8(flags) || id[16] || U64(size) || str16(name) || [str16(mime)] || digest[32]` |
| ACCEPT | `"P2FA" || U8(1) || zero[3] || id[16] || U64(0)` (32 bytes) |
| FINISH | `"P2FF" || U8(1) || zero[3] || id[16] || U64(size) || U32(chunkCount) || digest[32] || offerHash[32]` (100 bytes) |
| COMMIT | `"P2FC" || U8(1) || zero[3] || id[16] || U64(size) || digest[32] || offerHash[32]` (96 bytes) |
| RESULT | `"P2FR" || U8(1) || U8(code) || U8(phase) || U8(reasonPresence) || id[16] || str16(reason)` (26 + reason bytes) |
| REJECT / CANCEL | empty payload = no reason, otherwise strict bounded nonblank UTF-8 reason |
| DATA | raw next file bytes, with FILE_DATA header rules (§5) |

OFFER's three ones mean schema 1, digest algorithm SHA-256 (1), and required
durable completion (1). Only flag bit 0 is legal: it includes the MIME field.
Size may be zero. Name is nonblank≤4,096 UTF-16 units / 16,384 UTF-8 bytes,
must not be `.`/`..`, and contains neither `/` nor `\`. MIME when present is
nonblank≤255 units/bytes. Both use bounded wire-text validation. The name is
a single component, not authorization to use it as an unchecked destination.
`offerHash = SHA256(exact complete OFFER payload)`; do not hash a JSON or
reformatted representation. Fixed OFFER size is 66 + name bytes, plus
2 + MIME bytes when present.

RESULT reasonPresence is 0 iff reason length is zero, otherwise exactly 1;
present reason is nonblank bounded wire text≤1,024 units/bytes. The same
reason text bounds apply to ERROR/REJECT/CANCEL. Unknown code/phase is invalid.

| Code | Meaning | Public failure kind / retryability |
| ---: | --- | --- |
| 1 | digest mismatch | INTEGRITY / NOT_RETRYABLE |
| 2 | storage failure | STORAGE / RETRY_AFTER_USER_ACTION |
| 3 | protocol failure | TRANSFER_PROTOCOL / NOT_RETRYABLE |
| 4 | source changed | SOURCE_CHANGED / NOT_RETRYABLE |
| 5 | timeout | TIMEOUT / RETRY_NEW_SESSION |

Phase codes: OFFER=1, ACCEPT=2, SOURCE_READ=3, SEND=4, RECEIVE=5, VERIFY=6,
FLUSH=7, DURABLE_COMMIT=8. These are RESULT fields, not an ERROR-frame numeric
error protocol. Public diagnostic strings may be bounded/sanitized separately;
do not require exact incidental wording for interop.

### Required successful transaction

1. Sender prepares/hashes the exact immutable advertised source before OFFER,
   retains its expected size/digest and waits for valid ACCEPT(offset=0).
2. Receiver explicitly accepts a transactional destination; accepting a legacy
   flush-only RawSink does not satisfy authenticated transfer.
3. Sender streams FILE_DATA indices 0,1,… with constant totalChunks. Receiver
   rejects duplicate/out-of-order indices, changed totals, excess bytes and
   LAST inconsistent with either final index or reaching exactly offered size.
   A zero-byte file has **no FILE_DATA**, chunkCount=0 and SHA-256(empty).
4. Sender checks source EOF at exactly size (not only its prefix), validates
   the streamed digest against preparation, enters commit-wait and sends
   FINISH containing size, chunk count, digest and offer hash.
5. Receiver verifies FINISH against OFFER and received bytes/chunks/digest,
   then flushes and invokes destination.commit(). Only after successful
   publication does it mark Completed and send matching COMMIT.
6. Sender marks Completed only on matching COMMIT while in commit-wait.
   Byte progress/local write/FILE_DONE is never durable v2 success.

Receiver publication and sender observation are separate facts: lost COMMIT
can leave a complete receiver file while the sender fails. A timeout may win
the public terminal-state race while noncooperative, already-irreversible
destination publication completes late. Do not promise that every timeout
means no file exists, delete a committed target automatically, or claim an
automatic resume/reconciliation protocol. Destination-specific atomicity and
crash durability require separate platform validation.

### State/duplicate boundaries in this candidate

These rules apply **after payload/header validation**; an unknown transferId
does not excuse malformed wire bytes.

FINISH and DONE share a finalization-admission step: if it observes ACCEPTING,
it waits for acceptanceCommitted. A false result is ignored as missing;
otherwise it rechecks the current entry/phase. Only ACCEPTED transitions to FINALIZING. The table's
finalization outcomes follow that step, not an unconditional immediate decision
while acceptance is still in progress.

| Valid packet/state | Candidate action |
| --- | --- |
| exact active OFFER duplicate | ignore; do not open another destination |
| conflicting active/terminal OFFER, or OFFER colliding with an outgoing ID | structural TRANSFER_PROTOCOL failure; terminal session, not reconnect |
| exact terminal incoming OFFER replay | replay saved COMMIT/RESULT/REJECT/CANCEL response |
| OFFER exceeding policy/ledger capacity | best-effort REJECT; no admission |
| ACCEPT for unknown transfer or after first acceptance | ignore |
| REJECT after acceptance | warn/ignore; cannot retract accepted state |
| DATA for unknown transfer | ignore |
| DATA while still OFFERED or FINALIZING | drop; no destination write |
| DATA while ACCEPTING/ACCEPTED | serialized receive; ordering/storage failure fails that transfer and sends RESULT |
| FINISH unknown or finalization already started | ignore |
| FINISH still not accepted after the admission step, or mismatched/incomplete FINISH | fail that transfer with RESULT; do not publish success |
| DONE unknown, still OFFERED/not accepted, or finalization already started | ignore; warn for the not-accepted case |
| DONE admitted from ACCEPTED for a secure transfer | fail that transfer with RESULT(PROTOCOL_FAILURE, VERIFY); never durable success |
| COMMIT unknown | ignore |
| COMMIT outside commit-wait, or mismatched | fail that outgoing transfer, not false completion |
| RESULT / CANCEL | terminalize matching live outgoing/incoming transfer; unknown ID ignored |

The secure incoming replay ledger reserves at most 256 **admitted active plus
terminal** transactions per epoch, without evicting completed entries to admit
new ones. At capacity reject new offers; a fresh connection resets it. An ID
retired after ambiguous acceptance gets CANCEL, not a second admission.
Do not extrapolate this to unbounded idempotence or a cross-reconnect ledger.
FILE_DONE is never an authenticated-v2 success signal, including the ignored
phases above.

Sources: `FileTransferWire.kt`, `FileOfferPayload.kt`, `DefaultP2pProtocol.kt`,
`FileTransferDispatcher.kt`, `IncomingFileSession.kt`,
`OutgoingFileTransferImpl.kt`, `StreamingFileSender.kt`,
`StreamingFileReceiver.kt`, `FileTransferResources.kt`, `FileTransferConfig.kt`.

## 9. Setup, errors, EOF and local policy

| Boundary | Candidate outcome |
| --- | --- |
| preface/Noise/framing failure during setup | close stream, normally AuthenticationFailed; preserve explicit identity/authorization/configuration P2pErrors |
| no successful setup by deadline | AuthenticationFailed in authenticated SessionManager's outer setup timer; no downgrade |
| first emitted event not HELLO, or wrong HELLO AppId | HandshakeRejected; best-effort encrypted ERROR when possible |
| valid-schema HELLO with wrong version | VersionMismatch |
| HELLO/envelope claiming wrong authenticated identity | AuthenticatedIdentityMismatch |
| malformed HELLO body | skip/warn (§6); not necessarily an immediate terminal error |
| established invalid record/header/envelope/secure transfer schema | terminal ProtocolError / VersionMismatch / AuthenticationFailed as applicable; no automatic reconnect |
| valid file packet with transfer-local failure | §8 RESULT/failure policy; do not equate every transfer failure with session failure |
| authenticated CLOSE frame | clean terminal close, no reconnect |
| EOF/read loss without CLOSE | connection loss; eligible outgoing session may bounded-reconnect, otherwise Failed |
| received ERROR reason | connection loss, not a universal typed numeric wire error |

Incomplete application frame at a **complete record boundary** is not emitted
when the stream ends. `DefaultP2pProtocol.events` has no application
`FrameReader.finish` step: do not promise a distinct ProtocolError for that
case. The session still treats absence of CLOSE as connection loss, not clean
completion. Partial secure records have the separate EOF behavior in §4.

On an active epoch, PING prompts PONG. P2pKit creates a new PONG messageId rather
than echoing the PING ID. PONG refreshes the keepalive deadline. Reconnect creates fresh Noise
keys/counters, HELLO/feature state and transfer epoch; it is not silent protocol
downgrade or automatic file resume. An established authentication/protocol
terminal outcome must not be replaced by a reconnectable raw EOF.

### Current outgoing-reconnect retirement boundary

Before the outgoing retry driver refreshes discovery or dials a replacement,
P2pKit retires the lost raw transport and waits, within its existing local cleanup
budget, for the old secure/protocol reader and event router to finish classifying
buffered input. It does not install a replacement connection at this stage.
During this local retirement, new secure writes are rejected; failures of writes
interrupted by retirement do not discard queued receive records. Those records
still undergo the original authentication and protocol checks. An already-queued
CLOSE or typed authentication/protocol failure therefore remains authoritative
over retry; a retryable PONG-write/peer-error event does not abandon the remaining
queued events. Failed or incomplete controlled retirement does not authorize a
new dial. Ordinary write failure outside retirement still disposes the secure
stream; ciphertext and nonce state are never reused for a replacement connection.

Local retirement is **not a wire acknowledgement that the remote session/store
has processed EOF**. A remote owner that is still healthy can legitimately reject
a duplicate replacement. This is local lifecycle/admission behavior, not a new
packet, handshake flight, peer timeout, negotiated feature or durable-file ACK.

Sources: `ReconnectTransportRetirement.kt`, `AuthenticatedV2SecurityEngine.kt`,
`NoiseSecureRawConnection.kt`, `SingleCollectorRawPump.kt`, `P2pSessionImpl.kt`,
`SessionManager.kt`.

Current defaults below are **local resource/time policy**, not fields that
HELLO negotiates or promises an arbitrary peer will share:

- One 10-second setup budget covers secure prefaces, Noise, HELLO and identity
  validation; do not independently add a new full timeout for each step.
- PING interval 10 seconds; PONG deadline 30 seconds.
- 64 active incoming and 64 active outgoing files; 2 GiB/file; 8 GiB aggregate
  offered incoming bytes; 64 KiB outgoing file chunks (configurable 1..4 MiB).
- Offer/accepted-idle/receiver-commit/sender-commit-ack budgets default to 30
  seconds each; accepted streaming phase has a 600-second budget. These are
  phase budgets, not one end-to-end completion/cleanup ceiling. The unanswered
  outgoing-offer watchdog starts after sending and gives 37.5 seconds at the
  default, allowing grace for the receiver's 30-second rejection.

Sources: `SessionManager.kt`, `Handshake.kt`, `P2pSessionImpl.kt`,
`NoiseSecureRawConnection.kt`, `DefaultP2pProtocol.kt`, `Config.kt`,
`FileTransferConfig.kt`, `FileTransferDispatcher.kt`.

## 10. Existing vectors and what remains external

Use the [frozen wire fixtures](../../library/p2p-core/src/commonTest/resources/wire-goldens/)
and the [wire-golden guide](../testing/wire-goldens.md). The guide contains the
byte counts and SHA-256 of **decoded bytes**; the candidate source manifest
hashes the literal files. Do not confuse those two hashes or regenerate expected
bytes to make a check pass.

These twelve fixtures were generated by P2pKit at
`65d3689b7262f2ee3ee6584052d2e55ca6180725`, tree
`3ca3de2052255eca7065946691ddca3b3ff2d5bb`, on 2026-09-07. Public synthetic
inputs: AppId `wire.golden.π`; static private byte ranges `00..1f`/`20..3f`;
ephemeral ranges `40..5f`/`60..7f`. Never install these keys. The 77-byte
prologue and 979-/977-byte directional transcripts cover preface, three Noise
flights, HELLO, text and binary; they do not cover files, reconnect or close.
Four standalone envelope fixtures cover text/binary with/without metadata;
their synthetic sender/recipient strings are pure-codec inputs, not real
key-derived kit identities. `WireGoldenInputs.kt` supplies all inputs.

Existing consumers are `SecureSessionWireGoldenTest`,
`AppMessageEnvelopeGoldenTest` and `MixedSecurityProfileIntegrationTest`.
Their presence/provenance is not a fresh execution in this task. The
`cacophonyNoiseXx25519ChaChaPolySha256Vector` case in `NoiseXXHandshakeTest`
pins independently sourced Noise primitive/handshake behavior, including
generic nonempty handshake payloads; those payload sizes are **not** legal
production-v2 flights. Neither that vector nor P2pKit-to-P2pKit goldens supply
a separate P2pKit protocol/state-machine implementation.

The original source review and candidate rebinding remain preserved; §1 records
the focused current continuation separately. Resolve any labeled contract question
before using the affected clause as a normative external negative oracle. An
independently owned implementation can then use the reviewed specification and
independent crypto dependencies, without copying/linking P2pKit codecs. New independently generated
vectors/transcripts must have their own provenance; do not relabel the existing
goldens. Full external acceptance still requires the roles, negative/durable
cases, people/dependency provenance and physical platform matrix in the
[interoperability guide](secure-v2-interoperability.md). Hosted Linux/macOS/Windows
and simulators are useful but do not supply physical Android/Apple/AWDL evidence
or professional cryptographic validation. No acceptance checkbox or
repository-repair denominator changes with this document.
