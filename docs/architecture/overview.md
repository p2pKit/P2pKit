# Architecture overview

P2pKit is a Kotlin Multiplatform local-network peer-to-peer library. The host
application owns product admission, user identity, application messages,
lifecycle integration, and coroutine scopes. P2pKit owns discovery, sessions,
the secure transport protocol, bounded framing, reconnect, and durable file
transfer.

```text
Application
  ├─ product identity, admission, and data model
  ├─ lifecycle and coroutine ownership
  └─ P2pKit API
       ├─ peer registry and feature state
       ├─ session manager and reconnect arbitration
       ├─ authenticated-v2 records and protocol framing
       ├─ durable file transfer and SHA-256 commit
       ├─ LAN transport: JmDNS/Bonjour + TCP
       └─ optional Android/JVM provisioning sidecars
```

## Module boundaries

| Gradle project | Responsibility |
| --- | --- |
| `:p2p-core` | Public API, state, protocol, authenticated-v2 security, sessions, file transfer |
| `:p2p-transport-lan` | Android/JVM JmDNS, Apple Bonjour, TCP connections, platform path handling |
| `:p2p-network-provisioning-android` | Optional LocalOnlyHotspot and Wi-Fi join integration |
| `:p2p-network-provisioning-desktop` | Optional manual-endpoint fallback for JVM/Desktop |

Production modules live under `library/`; runnable diagnostics and consumer
examples live under `samples/`. Gradle project names and published artifact IDs
remain independent of physical directory layout.

## Security boundary

Authenticated v2 encrypts and authenticates transport records and binds peer
identity to persistent X25519 keys. It does not decide whether a person or
device is authorized for a product action. Applications must pin identities
through a trusted channel or implement an explicit admission protocol. See the
[security model](../security/model.md).

## Delivery semantics

Message `send()` confirms a local transport write, not remote application
processing. File transfer has a stronger negotiated contract: completion is
reported after the receiver verifies the prepared SHA-256 snapshot and durably
commits the destination. Applications still own domain-level idempotency,
ordering, acknowledgements, and repair.
