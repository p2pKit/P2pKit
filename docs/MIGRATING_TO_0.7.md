# Migrating from 0.6.x to 0.7.0-rc2

P2pKit 0.7.0-rc2 changes the default runtime security profile. This is a deliberate
new-version migration; do not replace or republish any existing `0.6.x`
artifact with the 0.7 source.

## Compatibility summary

| Concern | 0.6.x default | 0.7.0-rc2 default |
|---|---|---|
| Security mode | plaintext protocol v1 | authenticated/encrypted protocol v2 |
| Peer authorization | none | `RejectUnknown` (fail closed) |
| Bonjour/DNS-SD service | `_p2pkit._tcp` | `_p2pkit2._tcp` |
| Protocol version | 1 | 2 |
| Identity | persisted legacy peer id | AppId-bound id derived from persistent X25519 key |
| JVM identity storage | legacy file default | explicit protected `JvmSecureIdentityStore` required |
| Android identity storage | legacy storage/fallback | initialize application context; Keystore-wrapped no-backup record |
| iOS identity storage | legacy preferences | device-only Keychain record |

Authenticated v2 and plaintext v1 do not discover, negotiate with, or silently
downgrade to each other.

## 1. Pin a new artifact version

Update every P2pKit module together to `0.7.0-rc2` under the exact Maven group
`io.github.apdelrahman1911`. Do not rely on a global
`mavenLocal()` repository that may contain a different build under the same
coordinate. For source validation, publish to an isolated directory and opt
the consumer into that exact path:

```bash
./gradlew publishToMavenLocal \
  -Dmaven.repo.local=/absolute/path/to/isolated-p2pkit-repository
```

Before shipping, verify the resolved artifact origin and checksum in the
consumer build.

## 2. Configure persistent secure identity

### Android

Call `P2pKitAndroid.initialize(applicationContext)` once from
`Application.onCreate()` before constructing the kit. A missing initialization
is a configuration failure in authenticated mode; do not catch it and fall
back to an ephemeral identity.

### iOS

No identity-store hook is required. P2pKit uses a device-only Keychain item.
Treat identity reset/loss as a new peer that must be approved again.

### JVM

Implement `JvmSecureIdentityStore` using an operating-system credential/secret
store or an equivalently protected application store, then install it with:

```kotlin
P2pKit.create {
    // ...
    jvmSecureIdentityStore(protectedStore)
}
```

The implementation must provide confidentiality and integrity at rest,
cross-thread and cross-process safety, atomic `putIfAbsent`, durable writes,
and defensive copies. Do not copy the samples' development-only in-memory
store into production and do not substitute a passwordless plaintext file.

## 3. Choose and document peer authorization

The default is:

```kotlin
SecurityMode.AuthenticatedV2(
    authorization = PeerAuthorizationPolicy.RejectUnknown,
)
```

It rejects a connection unless the application supplies an exact trusted
fingerprint on `connect(peer, expectedFingerprint)` or configured the remote
fingerprint in `PinnedOnly`. Exchange full fingerprints or
`localPairingQr` text through a trusted out-of-band channel. Parse QR input with
`parsePeerPairingQr`; this binds it to the exact local `AppId`.

Discovery TXT fingerprints, display names, peer ids, short room codes, and
shared `AppId` values are untrusted claims and are not substitutes for an
out-of-band pin.

If the product deliberately performs admission above the transport, it can opt
into `AcceptAnyAuthenticatedSameApp`. This proves possession of an encrypted
transport key but does not establish a human/device identity because `AppId`
is public. The API is annotated `@ExplicitSecurityRisk`. Record the threat
model and ensure the application admission protocol rate-limits attempts,
binds actions to the transport-derived peer, and never authorizes based only
on a payload-supplied sender id.

## 4. Update the iOS host declaration

Authenticated v2 requires the exact secure service type:

```xml
<key>NSLocalNetworkUsageDescription</key>
<string>Find and connect to nearby devices on your local network.</string>
<key>NSBonjourServices</key>
<array>
    <string>_p2pkit2._tcp</string>
</array>
```

Keep the keys in the source that generates the final application Info.plist.
Add legacy `_p2pkit._tcp` only to a build that intentionally constructs a
plaintext-v1 kit. The maintained 0.7 sample declares only the secure service.

## 5. Stage mixed-version fleets explicitly

Preferred migration: update all mutually communicating peers to 0.7 before
enabling a session.

If a short compatibility window is unavoidable, build a separately identified
migration configuration that explicitly selects deprecated
`SecurityMode.NoneForMvp`. It continues to use protocol v1 and
`_p2pkit._tcp`. Never accept an authenticated-v2 failure and retry it as
plaintext, never hide the selected profile from users/operators, and remove the
legacy configuration after the fleet transition.

One `P2pKit` instance has one security profile. Running both profiles requires
separate instances, discovery declarations, lifecycle ownership, and a clear
application boundary; it is not an automatic bridge.

## 6. Treat session delivery as a transport primitive

0.7 hardens SDK bounds and cleanup but does not turn `send()` into a remote
application acknowledgement:

- Subscribe to `incomingSessions` before advertising.
- Attach `session.incoming` immediately; it is replay-zero.
- Exchange an application-level ready/admission message before real data.
- Add message/command ids, monotonic sequence or revision checks,
  deduplication, acknowledgements, and state repair where the domain requires
  them.
- Bound serialized application messages below P2pKit's 4 MiB transport cap and
  fail closed on malformed/unknown input.

## 7. Wire lifecycle and cleanup

Call mobile foreground/background notifications from the process/application
lifecycle. The default background policy closes active sessions and stops
advertising/discovery. Incoming sessions do not auto-reconnect; the remote
outgoing owner redials. On teardown, stop application collectors, close
sessions, and call terminal `P2pKit.stop()`.

## 8. Verify the migration

At minimum:

1. Assert local identity persists across a normal process restart.
2. Verify a correct pin connects and a wrong/unknown pin fails before a session
   is published.
3. Verify a v1 peer is not visible to a v2 kit and no downgrade occurs.
4. Exercise Android/JVM/iOS pairs on physical devices, including background,
   Wi-Fi changes, abrupt departure, and repeated create/stop cycles.
5. Inspect the final iOS app Info.plist for `_p2pkit2._tcp`.
6. Verify consumer dependency provenance and run the published-consumer gate.

The complete automated and physical-device release matrix is in
[`STABILIZATION_AND_RELEASE.md`](STABILIZATION_AND_RELEASE.md).
