# p2p-rpc

Optional Kotlin Multiplatform organization-LAN RPC over the existing P2pKit core
and LAN transport. One explicitly selected authenticated host, dial-only clients,
typed registered procedures, bounded recovery/pairing/notifications.

**Unpublished feature: JVM/Android compilation and deterministic tests passed;
Apple, security and capacity qualification remain pending.** Do not
mix it with historical published core/LAN binaries. No exactly-once execution,
durable queue, database, cloud dependency or arbitrary remote code execution.

- [API quick start and architecture](../../docs/rpc/README.md)
- [Reliability and limits](../../docs/rpc/reliability.md)
- [Security and deployment](../../docs/rpc/security-and-deployment.md)
- [Protocol](../../docs/rpc/protocol.md)
- [Verification requirements and blockers](../../docs/rpc/qualification.md)
- [Shared inventory example and capacity driver](../../samples/p2p-sample-rpc/README.md)

Release Foundation remains **NOT_READY**. All HOLDs and release/external
validation gates remain unchanged. See the [validation checkpoint](../../docs/rpc/implementation-status.md)
for executed checks and the remaining separately authorized work.
