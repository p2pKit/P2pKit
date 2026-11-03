# RPC local public identity

`RpcHost.localIdentity` and `RpcClient.localIdentity` return an immutable
`RpcLocalIdentity` read from the actual factory-owned authenticated-v2 Kit.
It is available immediately after `create()`, before networking or enrollment.
Repeated reads return the same snapshot; it remains available after `close()`.

| Field | Meaning |
| --- | --- |
| `appId` | Actual Kit AppId and secure identity namespace. |
| `peerId` | Actual authenticated-v2, AppId-bound local PeerId. |
| `fingerprint` | Canonical local public identity pin; also returned by the existing `fingerprint` accessor. |
| `pairingQr` | Canonical local QR, bound to that AppId and fingerprint. Reading it creates no invitation. |
| `deviceName` | Actual local display name used by discovery and HELLO. It is not cryptographic authority. |

The snapshot contains no private key, endpoint or trust grant. Comparing it to a
retained native/SDK association is an application responsibility. A matching
snapshot alone does not admit a device, authorize an employee or prove possession
of a remote key. Exchange pins through a trusted channel and retain the existing
authenticated connection and authorization checks.

## Preserve a name when recreating a role

Persist the desired name separately from the platform secure identity store.
Supply it in either Host or Client configuration:

```kotlin
val client = RpcClient.create(platform, applicationScope) {
    appId = retainedAppId
    lan = approvedLan
    trustStore = durableTrustStore
    deviceName = retainedDeviceName
}
val actual = client.localIdentity
check(actual.appId == retainedAppId)
check(actual.peerId == retainedPeerId)
check(actual.fingerprint == retainedFingerprint)
check(actual.pairingQr == retainedPairingQr)
check(actual.deviceName == retainedDeviceName)
```

Use the same protected identity store and exact AppId to retain key identity.
Always close the owned role if comparison fails; do not start discovery, enrollment
or connection before the application finishes its association checks.

`deviceName = null` preserves the previous defaults: `P2pKit RPC host` and
`P2pKit RPC client`. Explicit names pass Core's existing wire-text validation;
blank, oversized or invalid text fails creation. Names are not trimmed or silently
replaced. Changing a valid name does not rotate the fingerprint, PeerId or QR.
Retaining keys without supplying a retained name keeps the role default, so a
name comparison can still detect a reconstruction mismatch.

This API preserves the existing factory signatures, owned `close()` boundary,
authentication, encryption, admission limits and Apple deployment baseline.
It introduces no borrowed-Kit injection or wire-protocol change.
