# RPC protocol version 1

RPC messages are carried inside secure-v2 `P2pMessage.Binary`, with no
application metadata. Existing P2pKit envelopes, fragmentation, record
encryption and TCP remain in charge of transport. Core ACKs are not RPC
completion acknowledgements. No change to the published P2P wire constants is
required. This new RPC wire format is not present in historical releases.

Source of truth: [RpcWire](../../library/p2p-rpc/src/commonMain/kotlin/dev/p2pkit/rpc/internal/RpcWire.kt)
and [codec tests](../../library/p2p-rpc/src/commonTest/kotlin/dev/p2pkit/rpc/internal/RpcCodecTest.kt).

## Envelope

All integers are big-endian. A 56-byte fixed header precedes the ASCII name
and length-delimited body. Bodies are JSON UTF-8 for business values, not
JSON-wrapped byte arrays. STATUS/CANCEL/RECEIPT and pairing have fixed binary bodies.

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 4 | `PRPC` magic |
| 4 | 1 | Major version `1` |
| 5 | 1 | Message kind |
| 6 | 2 | Required feature/reserved bits: currently zero; unknown bits rejected |
| 8 | 16 | Nonzero logical request/negotiation ID |
| 24 | 16 | Host incarnation; zero only in HELLO |
| 40 | 4 | Procedure/notification schema version; zero for connection/pairing controls |
| 44 | 4 | Remaining invocation allowance or bounded overload retry-after, milliseconds |
| 48 | 1 | Call attempt, 1–3 for INVOKE/STATUS; otherwise zero |
| 49 | 1 | Kind-specific status/admission/reinvocation code |
| 50 | 2 | Name length, 0–96 bytes |
| 52 | 4 | Body length; validated against message kind and total packet length |

Unsupported major versions produce `IncompatibleVersion`; unknown required
bits, kinds, invalid fields, trailing bytes and prohibited combinations are
protocol errors. There is no silent fallback or plaintext downgrade.

## Message families

1. **HELLO / READY:** fresh random negotiation ID after every authenticated
   connection generation. READY echoes that ID and supplies host incarnation
   and trusted/enrollment-only admission. Stale IDs cannot authorize a new
   generation. HELLO repeats at bounded intervals for at most five seconds,
   covering the underlying replay-zero flow subscription race. Collectors are
   installed before host start/public readiness.
2. **INVOKE:** procedure/version, frozen JSON request, overall remaining allowance,
   logical request ID and attempt. Explicit reinvocation code requires an
   idempotent registered descriptor as well as client opt-in.
3. **SUCCESS / APPLICATION_ERROR:** same ID/schema/incarnation and a required
   typed JSON body. These are the only business outcomes.
4. **FAILURE:** a closed infrastructure-error code set. Never remote exception
   text, stack traces, payload fragments or SQL errors.
5. **STATUS / RUNNING:** recover/observe retained execution. STATUS carries the
   32-byte SHA-256 digest of the frozen request; it never creates execution.
6. **CANCEL:** same digest and procedure identity, best-effort cooperative stop.
7. **RECEIPT:** same digest/identity, best-effort response-body reclamation only.
8. **PAIR_REQUEST / PAIR_PENDING / PAIR_APPROVED / PAIR_DENIED:** encrypted
   quarantine workflow. Proof is a 16-byte invitation ID plus a 32-byte secret.
9. **NOTIFY:** registered notification name/version and JSON body. Distinct
   from procedure responses; no durable subscription or replay log.
10. **REQUEST_APPROVAL (kind 16):** bodyless opt-in first-use enrollment, distinct from
    the 48-byte invitation proof. Old peers reject this unknown kind; clients must not
    fall back to an empty/fabricated invitation. The local client confirms the selected
    fingerprint and the host administrator separately approves the authenticated client.
    `allowNearbyPairing` defaults to false. Nearby and invitation requests share four
    slots; nearby requests expire after 120 seconds without retry renewal. Decided/expired
    identities have a 30-second cooldown, held in a bounded 128-entry table that fails
    closed at capacity. Nearby hosts also retire silent enrollment links after 120 seconds.
    Trust is written durably before approval; the old enrollment link is always closed.
    First-use discovery approval is TOFU unless fingerprints are independently compared;
    mDNS names, addresses and TXT fingerprints are never an authenticated pairing channel.

The host rechecks trust and application authorization before returning retained
results. Pairing approval cannot change the captured admission of the old
connection. Enrollment clients cannot invoke procedures, retrieve cached results,
transfer files or receive notifications.

The [reliability contract](reliability.md) defines uncertain outcomes, duplicate
handling, retention, cancellation and retries. Transport ordering does not order
concurrent handlers or introduce exactly-once semantics.
