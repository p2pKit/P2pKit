# Secure-v2 wire goldens

These immutable, public, synthetic test bytes were captured twice from unchanged production code at
`65d3689b7262f2ee3ee6584052d2e55ca6180725` (7 September 2026). They are not independent interoperability vectors
or a claim about every previously published release. Never use their fixed keys as installed identities.

See [provenance, inputs, byte layout and change policy](../../../../../../docs/testing/wire-goldens.md).
Whitespace separates lowercase hex; no resource is regenerated from a production encoder by the test build.
`generateWireGoldens` only transcribes these files into commonTest Kotlin literals for JVM, Android host and Native.
