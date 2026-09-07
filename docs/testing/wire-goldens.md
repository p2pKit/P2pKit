# Secure-v2 wire compatibility goldens

## Scope and provenance

The canonical [hex resources](../../library/p2p-core/src/commonTest/resources/wire-goldens/) pin a composed
secure-channel prefix: prefaces, all three Noise XX flights, encrypted HELLO, text and binary messages.
They do **not** include file transfer, reconnect, close or an entire application lifecycle.

Origin: unchanged production code at commit `65d3689b7262f2ee3ee6584052d2e55ca6180725`, tree
`3ca3de2052255eca7065946691ddca3b3ff2d5bb`, on 7 September 2026. Two JVM captures with a temporary test
produced identical bytes. The captures added that untracked test, not production changes. This freezes an audit
branch baseline on the post-RC3 stabilization line; it does not retrospectively certify a published release.

The expected values are **not** recomputed by production encoders during tests. `GenerateWireGoldensTask`
transcribes committed hex into generated **commonTest-only** literals, with declared Gradle inputs/outputs.
A missing input directory, empty fixture set or malformed hex fails generation. Required fixture names are checked
when tests request them: deleting one fails its consumers, not necessarily generation. Neither case silently refreshes
expected values. Native consumes the same fixtures without a JVM resource loader. Generated Kotlin belongs under
`build/`, not in Git or publications. Android host-test lint model/analysis tasks explicitly depend on the producer;
AGP 9.3 otherwise loses that dependency while copying KMP source roots. Recheck both consumers on plugin upgrades.

## Public synthetic inputs

All keys below are deliberately public test material. Never install them in a real identity store.

| Input | Initiator | Responder |
| --- | --- | --- |
| AppId | `wire.golden.π` | same |
| Static X25519 private bytes | ascending hex `00` through `1f` | `20` through `3f` |
| Ephemeral X25519 private bytes | `40` through `5f` | `60` through `7f` |
| HELLO name / platform / transports | `Golden initiator` / `UNKNOWN` / `["LAN"]` | `Golden responder` / same / same |
| HELLO version / sorted features | `2` / `app-message-envelope-v1`, `file-commit-sha256-v1` | same |
| 16-byte message IDs, in send order | `01..10`, `11..20`, `21..30` | `41..50`, `51..60`, `61..70` |
| Text / metadata | `Golden π 🚀` / present | same / absent |
| Binary / metadata | hex `00017f80ff` / absent | same / present |

Message-ID ranges in the table are **hexadecimal**. Each direction starts application sequence zero and
Noise transport nonce zero; HELLO consumes the first message ID and first transport nonce. Metadata is inserted
in this order: `é=café`, `z=` (empty value), `a=first`; its wire order is unsigned UTF-8 `a`, `z`, `é`.
`WireGoldenInputs.kt` records the fixed peer IDs/fingerprints and inputs, not an expected-byte encoder.

Standalone envelopes use message ID `00..0f`, sequence zero, sender `sender-π`, recipient `recipient`, and the
same text/binary/metadata values. Each decode uses a fresh negotiated receiving state.

## Layout and checksums

The prologue is a handshake input, **not** bytes sent as a separate wire frame. The two directional transcripts
start with their 16-byte preface. Initiator then sends length-prefixed XX flights 1 and 3; responder sends flight 2.
Each then sends three length-prefixed encrypted records (HELLO, text, binary). Application frames are inside those
records. Length prefixes are big-endian; the handshake bodies are 32, 96 and 64 bytes respectively.

The following are SHA-256 checksums of **decoded bytes**, not whitespace-formatted files:

| Resource (`.hex`) | Bytes | SHA-256 |
| --- | ---: | --- |
| `static-public-0` | 32 | `eedd883da0a9451593dc0a38e583fb770fa27dbbed209c20404e075e68c4f0c9` |
| `static-public-1` | 32 | `a0289810032eb417274eebc4a38e6899b935321d53554e32ec6322f0fa1e724e` |
| `preface-initiator` | 16 | `711b79db988ce0ec90e1dd979e087034b75aafa9ec80351268dbcdd1b29ea936` |
| `preface-responder` | 16 | `adddb2abfe3b514686af55ea835dfb164a3d5da44c1e2ceda9bc8db968ff6fe9` |
| `prologue` | 77 | `60403e5d3796e5745d007bf1ff78672fe248afb2b8a9e003f18dfa6b6ff50a85` |
| `handshake-hash` | 32 | `51e5091c5337ac35ccd089f3cb3b1d2f47967c8a760c78fdf554add43658bb42` |
| `session-initiator` | 979 | `801e3970b513bd6790c04e4bf5e4323ab609c4e96b7eee93b43f1fdea7d4fe77` |
| `session-responder` | 977 | `eeebe7ed7d65fab2f3c90d4bab18e1cee68dba28d2ce0b794ff6ed83011aa071` |
| `envelope-text` | 110 | `4a28de93f518671264b7fc69fadcbdf0af1042d67c918ea782d3140993add36b` |
| `envelope-text-metadata` | 142 | `cc99520e0b6856d9dd15dd01777bab10e5a2bb782b6d79636feac66f42f91c2b` |
| `envelope-binary` | 101 | `3704f46d880d088faf4dc65ab832468cbf36f6184f4c5556b76d9b3c80dbeb66` |
| `envelope-binary-metadata` | 133 | `d5e9bbbb64626135b61a52ba0020bdffcf29be0f65395ee0faa02da85c91dcc1` |

## Executable coverage

- `SecureSessionWireGoldenTest` independently replays each endpoint against the opposite fixed transcript,
  using real platform cryptography with fixed ephemeral generation. It pins authorization input, public identity,
  handshake hash, negotiated HELLO/messages, all generated local bytes, single-reader ownership and cleanup.
  Read sizes 1, 19 and 2,048 exercise byte fragmentation and a coalesced transcript.
- `AppMessageEnvelopeGoldenTest` separately checks production encoding and fixed-byte decoding for all four
  text/binary variants. A synchronized encoder/decoder change cannot hide behind a round trip.
- `MixedSecurityProfileIntegrationTest` runs real kits/managers over the fake stream in both v1/v2 directions,
  twice per kit pair, under exact/fragmented/coalesced reads. Active subscribers, empty stores, typed causes,
  no application frames/delivery, closed raw streams and final dial counts guard fail-closed behavior.
  The secure side reports `AuthenticationFailed` with a `NoiseProtocolException`; the legacy side reports
  `ConnectionFailed` from EOF. A responder rejecting legacy magic sends **no plaintext version reply**.
- `WireGoldenAndroidHostTest` deliberately selects the Android-source crypto/envelope checks without changing
  core's host filter. This executes the Android provider on a host JVM, **not** Android framework APIs or ART.

Focused JVM run (Bash; cleanup executes on failure too):

```bash
(
  trap './gradlew --stop' EXIT
  ./gradlew :p2p-core:jvmTest --tests '*SecureSessionWireGoldenTest' \
    --tests '*AppMessageEnvelopeGoldenTest' --tests '*MixedSecurityProfileIntegrationTest' \
    --max-workers=2 --no-parallel --console=plain
)
```

Also run `:p2p-core:testAndroidHostTest` and, on the configured Mac, `:p2p-core:iosSimulatorArm64Test`.
The ordinary `check` gate includes them. Preserve reports, stop invocation-owned workers and remove disposable
outputs after dependent checks; do not delete shared caches or source directories named `build`.

## Change policy and remaining validation

Never refresh these bytes merely to make a failing test pass. Review any intentional wire change against the
protocol/version contract, explain its compatibility effect, retain existing-v2 fixtures, and add versioned fixtures
when introducing a new protocol. Record the independently reviewed source/capture provenance for new vectors.
As a negative control, change envelope version in both encoder and decoder or change both preface reserved-byte
write/validation rules: symmetric round trips may still pass, but the fixed-byte tests must fail. Restore all mutations.

These fixtures improve same-implementation **compatibility regression resistance**. They are not an independently
authored encoder/state machine, a two-process cross-platform connection, LAN discovery, device/OEM behavior,
file durability or cryptographic assurance. Existing Cacophony primitive vectors remain valuable but narrower.
[Independent secure-v2 interoperability](../validation/secure-v2-interoperability.md) remains **NOT STARTED**,
and the [external validation catalog](../validation/test-catalog.md) remains authoritative for device/network gates.
