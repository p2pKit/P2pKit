# p2p-rpc

Optional Kotlin Multiplatform organization-LAN RPC over the existing P2pKit core
and LAN transport. One explicitly selected authenticated host, dial-only clients,
typed registered procedures, bounded recovery/pairing/notifications.

**Published development-stage library.** Use the same
[`LATEST_PUBLISHED_VERSION`](../../gradle.properties) for RPC, core and LAN;
see the [release records](../../docs/README.md#test-and-release) for immutable source and
platform evidence. Publication does not complete physical-network, installed
Windows, independent interoperability or production-capacity qualification.
Do not mix it with historical core/LAN binaries. No exactly-once execution,
durable queue, database, cloud dependency or arbitrary remote code execution.

- [API quick start and architecture](../../docs/rpc/README.md)
- [Reliability and limits](../../docs/rpc/reliability.md)
- [Security and deployment](../../docs/rpc/security-and-deployment.md)
- [Protocol](../../docs/rpc/protocol.md)
- [Verification requirements and blockers](../../docs/rpc/qualification.md)
- [Shared inventory example and capacity driver](../../samples/p2p-sample-rpc/README.md)

The maintained [release pipeline](../../docs/releasing/release-foundation.md)
uses modular exact-source CI and frozen application artifacts. Its old bootstrap
authorization protocols are retired, not passed tests. See the
[current external validation status](../../docs/validation/README.md#current-status)
and [Windows scope](../../docs/rpc/windows-release-scope.md) for remaining limits;
earlier implementation checkpoints retain only their dated evidence scope.
