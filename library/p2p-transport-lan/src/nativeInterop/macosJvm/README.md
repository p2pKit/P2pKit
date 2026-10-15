# macOS JVM scoped TCP adapter

The private ARM64 JNI adapter implements IPv4/TCP for the **manual Desktop RPC** path
(`advertise=false`). It is not a multicast fix. JmDNS and the portable Java multi-interface
guard remain unchanged. Android/iOS source, routes, permissions and global protections
are not changed by this adapter.

## Ownership and admission

- `IP_BOUND_IF` is applied before bind/listen/connect and independently read back from
  the actual socket. Accepted children must inherit scope; they are not repaired later.
- Each dial rechecks the complete interface inventory, selected name/index/address,
  numeric CIDR and self/hairpin restrictions before sending. Connected paths repeat
  admission through the unchanged 250 ms guard. Other interfaces are not hidden.
- Native generation handles own nonblocking, close-on-exec, `SO_NOSIGPIPE` descriptors.
  Java holders exist before allocation/accept, including an error returning an owned
  handle. JNI bounds every buffer and zeroes temporary transfer storage.
- The transport owns inert candidates and handed-off connections until verified release.
  Stop seals allocation, closes outside its ownership lock, drains accept/I/O/close and
  prevents restart after failed cleanup. Failed native closes are quarantined, not retried
  against potentially recycled descriptor numbers. Core suppression cannot erase them.
- Reads/writes remain at most 64 KiB per native call; polls are at most 100 ms. Existing
  dial, candidate, write, invitation, authentication and approval deadlines are unchanged.

## Explicit producer and loader

`./gradlew :p2p-transport-lan:stageMacTcp` requires clean committed source, JDK 17,
macOS ARM64 and the already-installed Xcode compiler. It does not download anything.
The create-only stage is `build/macos-tcp/<commit>/` in this module. Failed stages and
previous commits are preserved. Signing is local ad-hoc, **not distribution notarization**.

The loader is enabled only by `dev.p2pkit.lan.macos.nativeDir`. An invalid explicit
configuration fails closed without fallback. It requires one trusted classpath manifest
identical to the private external manifest, matching clean compiled source, bounded
size/SHA-256, ARM64 Mach-O dylib, ABI/source probe, nonsymlink owner-private files and
safe ancestor permissions. It uses one absolute `System.load`, never a global search.
Classpath/build ownership is a trust boundary; this does not defend against a compromised
same-user JVM/classpath. Neither loading nor successful staging proves network scope.

## Local Desktop package

`./gradlew :p2p-sample-rpc:prepareRpcDesktopMac` prepares a separate create-only
`build/desktop-macos/<commit>/` package in the sample. It copies exact source-bound JARs,
manifest and native bytes and independently checks the copied ad-hoc signature. Its
`run-desktop.py` verifies artifact hashes/signature before launching the pinned JDK.
It does not start a role until the user explicitly selects a network and presses Start.
`runRpcDesktopSample` uses this adapter on ARM64 Macs; other platforms retain portable
behavior. Explicit native tasks reject unsupported hosts rather than claiming a pass.

## Focused validation and boundaries

- `scripts/tests/check-macos-lan-sockets.sh`: existing C contract plus ASan/UBSan controls.
- `:p2p-transport-lan:jvmTest --tests 'dev.p2pkit.transport.lan.MacLan*Test'`:
  deterministic socket/binding/raw ownership controls (native-only classes excluded).
- `:p2p-transport-lan:macTcpNativeTest`: explicit real JNI loopback and POSIX staging
  adversaries; no skips are promoted into passes.
- Rerun affected portable ownership/admission/cancellation/watchdog and Desktop UI model
  tests. A source change requires a fresh source-bound stage and artifact review.

Loopback proves mechanics only. Actual local Desktop Host/Stop needs its own approved
interface-bound receipt. Peer pairing, physical LAN/multicast, Intel and ART remain
separate gates; this adapter does not mark them complete.

For an independently authorized **local Host/Stop** check, the packaged classpath also
contains `dev.p2pkit.sample.rpc.desktop.RpcDesktopLocalReadinessMainKt`. Its arguments
must be `--approved-local-host <interface> <numeric-ipv4> <private-cidr> <port> <empty-private-parent>`.
Use the verified native directory/property and the package's exact JAR classpath. It
prints only source/PID/phase, holds Host for five seconds for owner-specific readback,
then closes and verifies its empty owned identity directory. It does not select a
network, mint an invitation, approve a client or perform a multicast campaign. An
independent observer must verify listener retirement after process exit.
