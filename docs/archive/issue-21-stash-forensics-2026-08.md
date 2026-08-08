# Issue #21 diagnostic stash forensics — 2026-08-08

This record preserves the useful diagnostic intent from the uncommitted
`diag/issue-21-android-discovery-trace` experiment without applying its old
source or publication configuration to the current repository.

## Immutable stash identity

- Stash commit: `5ae6b82201e631ec9966742284aff7e8d46b1ff0`
- Base commit: `ea436b9b2a16bb7f13295d0a8f79599248f2ab10`
- Index parent: `4e64f2891c4583920d7ac2ea25657a34684c50af`
- Description: `diag/#21 traces — restore with git stash pop`
- Full binary-show SHA-256:
  `b8d7baa7126306a9584bd315e46c0f933e8a355370d263cd7ecf6dd1865e6d75`
- Selected four-file diagnostic diff SHA-256:
  `e5e94884f7511206c5e281e556a63a40985269de021bf3462e1e294343175f17`
- Shape: six tracked files, 72 insertions, four deletions, and no untracked
  files parent.

The stash contains no captured runtime logs, generated files, credentials, or
private payloads. Its paths predate the repository consolidation and must not
be restored directly onto current `main`.

## File-level disposition

| Old path | Stashed blob | Meaning | Disposition |
| --- | --- | --- | --- |
| `p2p-core/build.gradle.kts` | `6bede71178d55a7db62b974fba2b753e97060e29` | Adds `maven-publish`, group `dev.p2pkit`, and version `0.6.0`. | **Obsolete.** Conflicts with the verified `io.github.apdelrahman1911` publication architecture. Do not preserve as code. |
| `p2p-core/.../P2pKitImpl.kt` | `63402a40a0242d7ab5208504376b569c49f658c2` | Wires a logger into the former registry implementation. | **Historical diagnostic intent.** Current structured diagnostics supersede it. |
| `p2p-core/.../PeerRegistry.kt` | `b89ccbdbe621bcd3499f5441facab15fb83a5ff5` | Logs Found/Updated/Lost input and the age/threshold of old core stale eviction. | **Superseded diagnostic evidence.** Android discovery now uses transport-managed lifetime. |
| `p2p-sample-android/.../P2pKitViewModel.kt` | `e23d8d8e632e750075b95971fe8e4e8cc9b5148c` | Logs peer IDs removed between consecutive UI flow emissions. | **Historical diagnostic intent.** The sample now exports structured peer-loss events. |
| `p2p-transport-lan/build.gradle.kts` | `1a9edc76c5b61db1dbf049699c5a61b51d4c8976` | Adds obsolete `dev.p2pkit:0.6.0` publication configuration. | **Obsolete.** Do not preserve as code. |
| `p2p-transport-lan/.../AndroidLanDiscoveryTransport.kt` | `e8255bc24d147c0bd6a892b693d0759e3402bafe` | Logs raw JmDNS add/remove/resolve callbacks and the conversion to `PeerEvent.Lost`. | **Useful historical observation map.** Current transport diagnostics and admitted-service tracking supersede the implementation. |

## Preserved observation model

The four useful hunks attempted to distinguish these stages:

1. JmDNS invokes `serviceAdded`, `serviceRemoved`, or `serviceResolved`.
2. The Android LAN adapter converts the callback into Found or Lost.
3. `PeerRegistry` receives the event and may apply lifetime policy.
4. The public peer flow changes and the Android UI renders the new snapshot.

The stable search strings in the experiment were `JmDNS.serviceAdded`,
`JmDNS.serviceRemoved invoked`, `adapter→PeerEvent.Lost`,
`serviceResolved (heartbeat)`, `PeerRegistry.processEvent`,
`PeerRegistry.evictStalePeers: EVICTED`, and
`sample.peers.collect: peers dropped from kit flow`. This transcript preserves
the observation vocabulary without preserving the obsolete ad-hoc logger as
production behavior.

For the old 15-second hypothesis, the registry trace also recorded the peer's
age and the eviction threshold. That exact measurement is no longer applicable
to Android LAN peers because current discovery contributions declare
transport-managed lifetime and are not removed by the former core timeout.

Current evidence must instead correlate these stable structured events and
states:

- `discovery.peer.discovered` and `discovery.peer.lost`;
- `transport.log` for JmDNS callback, admission, generation, and removal data;
- `network.path.changed` and the discovery feature state;
- the UI peer snapshot and active test/session identifiers.

Current deterministic coverage includes transport-managed peer survival,
JmDNS heartbeat/reconciliation, generation/lease handling, and admitted-service
removal. These tests do not replace the outstanding long-idle physical-device
matrix required by Issue #21 and `LAN-T01`.

## Final disposition and deletion gate

The approved disposition is **SELECTIVELY RECOVER SPECIFIC CONTENT**: preserve
this sanitized diagnostic model and its immutable hashes, but never reapply
the source or Gradle hunks.

Keep the stash object until Issue #21's required Android API/OEM long-idle
evidence has passed. Before dropping it, a reviewer must confirm all of the
following:

- this record still identifies the exact stash/base/index commits;
- every stashed file has an explicit disposition above;
- the current test/evidence package records all four observation stages;
- both obsolete publication hunks remain excluded;
- the Issue #21 evidence can be reconstructed without the stash;
- the stash reference still resolves to the recorded stash commit.

Only after those checks may the exact stash be dropped. Any SHA mismatch stops
the operation. The stash is evidence retention, not a development branch or a
source of production changes.
