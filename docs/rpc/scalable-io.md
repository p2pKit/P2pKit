# Shared readiness I/O and the opt-in 256-client profile

This work starts from `69fd925d932e544a1a2feefd247adbcf0a397509` (`0.8.0-rc7`
source). It is not a change to previously published artifacts. The original
128-client campaign and its historical failures remain intact. In particular,
this work does not resolve the deferred physical-iOS discovery issue #520.

## Architecture decision

The former JVM/Android restricted reader used a 164-slot blocking IO dispatcher.
`InputStream.read()` occupied one worker while a connected peer was idle; simply
raising the client cap would require more parked threads and native stacks.
The 324-reader proposal is rejected. A coroutine around a blocking read does
**not** make that read asynchronous.

| Platform/path | Selected mechanism | Why / limitation |
| --- | --- | --- |
| JVM Linux/Windows, ordinary JVM sockets | Original `SocketChannel`, public Java 17 `Selector` | No new networking dependency, reflection, descriptor borrowing, IOCP adapter or thread per idle client. Runtime supplies epoll/kqueue/Windows selector implementation. Windows' selector may use helper threads at much larger handle counts; 512+ is not qualified here. |
| Android outbound and ordinary sockets | Public `SocketChannel`/`Selector`; existing `Network.bindSocket(Socket)` precedes connect | Preserves the selected network and retained original socket ownership. APIs are available at the maintained API24 floor. |
| Android organization-LAN accepted sockets | Shared public `Os.poll` batch plus nonblocking `socketpair` wake | Cannot portably turn an original `FileDescriptor` into a `SocketChannel`. No reflection/hidden API. Original descriptor leases prevent close/reuse while polled. API29-only Java flag fields are avoided on API24–28 by documented Linux UAPI flag values. |
| macOS scoped JVM TCP | Shared native poll/wake adapter over original generation-token owners | Preserves `IP_BOUND_IF`, actual inherited scope readback, pinned JNI library, per-socket `SO_NOSIGPIPE` and close-drain registry. Private native TCP ABI advances to 2; no public/wire ABI change. A kqueue-specific adapter remains a possible measured optimization, not necessary for 256 sockets. |
| iOS | Existing asynchronous `NWConnection` callbacks | Already event driven, with one outstanding receive and bounded delivery. No replacement or artificial JVM-style pool. Actual device resource/lifecycle qualification remains separate. |

Each process has one lazy readiness worker per backend, not per kit/client.
Restricted syscall lanes are shared: 16 reader, 16 writer and 16 setup workers
(limits, not eagerly allocated threads). Waiting for socket readiness suspends
the coroutine and releases its worker slot. Accept remains one blocking worker
per actual listening transport; dial-only clients create no listener.

The readiness worker only selects and schedules continuations. Even Unconfined
application continuations are dispatched away from it. Each original socket
has at most one read and one write waiter, no new payload queue. Writes retain
the existing mutex and watchdog, handle partial writes, and yield between
64 KiB syscall chunks. A large/backpressured writer cannot occupy a worker while
waiting or interleave another frame into its unfinished stream.

Readiness registration/cancellation/close wake the same backend. Snapshot
identity prevents an old event from resuming a replacement waiter. A single
1-second backend safety ceiling contains wake failures; there is no added
per-connection readiness polling timer. Last-owner close wakes, joins and
retires the poller. Failed startup/retirement stays failed and retained rather
than creating an unobserved replacement. Original socket close is still attempted
if backend cleanup fails; explicit close observes its original failure.

Authentication, encryption, session admission, frame order, write deadlines,
reconnect, notification priority/fairness and shared payload accounting remain
above the byte adapter. Caller cancellation of a partially written frame closes
that exact connection. Fresh before/after-I/O selected-network/topology checks
are **not cached or relaxed**. Their CPU cost is part of the authenticated
benchmark, unlike a raw socket benchmark.

Profiling found repeated OS topology enumeration and selector-registration
churn. The idle prohibited-path watchdog now selects the current socket cohort
every 250 ms and then takes **one fresh** topology snapshot for that pass, rather
than enumerating the same interfaces separately for every idle socket. Every
original socket still gets its own address, native scope and Network-owner
checks. The snapshot is discarded after the pass; it never authorizes admission,
a later read/write, or a socket joining during that pass. A failed observation
closes affected sockets. Removal fences old callbacks, and the next watcher
epoch cannot overlap an unfinished old snapshot. There is no positive-result
TTL, new polling thread, reduced detection frequency, or cached I/O authority.
NIO likewise updates only changed key interests, instead of clearing and
re-registering all idle peers whenever any other peer becomes ready.

## Policy changes, not preallocated memory

| Resource | Default / `host128()` | Explicit `host256()` |
| --- | ---: | ---: |
| Trusted clients / Core trusted sessions | 128 | 256 |
| Running / queued RPC calls | 128 / 256 | 256 / 512 |
| Shared retained-payload budget | 64 MiB | 128 MiB |
| Result cache, inside payload budget | 32 MiB | 64 MiB |
| Total records | 131,072 | 262,144 |
| Host-wide notification admission | 1 MiB | 2 MiB |
| Outstanding calls / records per client | 8 / 1,024 | unchanged |
| Enrollment / inbound handshakes / pre-handshakes per source | 4 / 16 / 2 | unchanged |
| Queue/setup/write/close concurrency, wire/parser limits, retry/deadlines | existing | unchanged |

Limits remain configurable downwards within the constructor's bounded ceilings.
The payload budget is not process RSS: record/coroutine objects, crypto/runtime
allocations, OS buffers, thread stacks and application handlers cost extra.
Responses are still best-effort recoverable under cache pressure; tombstones
and at-most-once protection retain their existing semantics and deadlines.

Sample trust stores can retain 256 pins. iOS's serialized bound is 16,384 bytes;
Android's existing encrypted 16,384-byte bound already fits 256 canonical pins.
Only explicit capacity imports of exactly 128 or exactly 256 pins select those
profiles. Ordinary sample hosting stays at 128. The original mobile/USB schema1
campaign is still 128, not retrospectively reclassified as 256 qualification.

## Validation and reproducible commands

```bash
# JVM production channel path, races, timeout/cancellation/ordering and real raw 128/256 sockets
./gradlew :p2p-core:jvmTest :p2p-transport-lan:jvmTest :p2p-rpc:jvmTest \
  :p2p-transport-lan:testAndroidHostTest :p2p-rpc:testAndroidHostTest \
  :p2p-sample-rpc:jvmTest --dependency-verification=strict
python3 -B scripts/tests/check-rpc-scalable-io-test.py

# Clean committed source; standalone synthetic host/client tooling (not published)
./gradlew :p2p-sample-rpc:prepareRpcCapacityLab --dependency-verification=strict
# Linux namespace setup privilege; both JVMs drop all capabilities before product execution.
# Choose a NEW private output directory. Virtual link only; no host network/firewall edits.
sudo --preserve-env=JAVA_HOME python3 -B scripts/run-rpc-io-benchmark.py \
  --clients both --seconds 120 --output /tmp/p2pkit-io-comparison-NEW

# Actual Darwin native contract, including original leases, stale tokens, wake/cleanup and 256 pairs
bash scripts/tests/check-macos-lan-sockets.sh
./gradlew :p2p-transport-lan:stageMacTcp :p2p-transport-lan:macTcpNativeTest
```

The authenticated comparison uses real distinct keys, local durable trust,
production `RpcHost`/`RpcClient`, secure-v2 TCP, unchanged topology guards, and
phase-spaced 10 Hz/client 1 KiB echo calls. Setup connects in batches of two,
preserving pre-handshake admission. It records host CPU, native threads, RSS,
idle overhead, throughput and latency bucket bounds separately from the driver.
Every response and final host counter is checked. Original clients/host must
close, final process exits must be observed, and records/payload must return to
zero beyond the unchanged 60-second retention window. The run is **120 seconds,
not the previous 30-minute capacity campaign**. Slow scheduling is recorded, not
hidden; mechanical correctness alone is not a resource-efficiency verdict.

`CI — modular qualification` has an independent `rpc-io` diagnostic selection;
`rpc_io_part` selects all or one of `jvm-linux`, `jvm-windows`, `macos`,
`macos-abi`, `android-24`, `android-35`. The additive Apple ABI candidate is
generated independently from native socket tests, without editing its baseline.
Failures do not cancel another platform. Evidence uses
the maintained source-bound collector and encryption, not new authorization or
custody protocols. These focused checks do not mint release qualification.

Android instrumentation is opt-in with `-Pp2pkit.lan.readinessDeviceTest=true`.
It compiles the real production adapters into one test APK, then exercises both
NIO and native accepted sockets at 128/256 over loopback on ART. It measures raw
I/O resources and exact echoes, **not authenticated RPC, Network binding,
installed sample behavior, Wi-Fi, Doze, physical devices or sustainable mobile
host capacity**. The runner requires actual KVM and a fresh emulator; host JVM
tests are not substituted if that environment is missing.

### Evidence status

The initial shared-readiness implementation at `f6dffa0a` completed a real
authenticated Linux virtual-link comparison: 153,600 correct responses at 128
clients and 307,200 at 256, over 120 seconds each. Both original processes exited
zero; record/payload retention returned to zero after the unchanged retention
window. Host threads after load were 76/78 (not 164/324), p95 upper buckets 7/24 ms,
and p99 23/56 ms. Host idle CPU was still **19.69%/52.54% of one core** and active
CPU 165.90%/351.12%; RSS after load was 519.3/609.8 MiB. Scheduling lateness was
recorded, not hidden. The virtual-link JVMs dropped all capabilities but retained
UID0: this is **not ordinary-user or physical qualification**. These measurements
precede the cohort/selector optimization above and must not be reused to qualify it.

[Hosted initial checks](https://github.com/p2pKit/P2pKit/actions/runs/40123111532)
verified Linux and Windows XML (Core 960, LAN 386, RPC 83; sample 637 Linux / 614
Windows), with zero failures/errors/skips. Raw 128/256 socket counts were 32/32
JVM threads on Linux and 29/28 on Windows. Android35 ART completed all four raw
backend/population cases, with low idle CPU and bounded threads; several nominal
30-second workloads actually took 45–85 seconds. That is **mechanical completion,
not sustained target throughput** and not authenticated mobile capacity.

Earlier Android24 attempts failed before ART execution: its OS lacks
`sha256sum`, then the replacement host-hash collector incorrectly rejected dotted
package paths. The collector now hashes bytes pulled from the installed package
and covers both old/new layouts; the failed attempts remain failures.
[The next macOS attempt](https://github.com/p2pKit/P2pKit/actions/runs/40124417134)
passed 25 actual C contract groups in both strict and ASan/UBSan builds, plus
the existing JNI controls, but the new 128/256 async JNI integration failed.
That failure and Apple ABI/mobile qualification remain open at this checkpoint.
New optimization results require fresh, exact-source checks. No physical mobile
capacity or 512-client capability is claimed.

The old 128-raw-socket baseline observed 151 JVM threads (9 before connections).
Initial new raw 128/256 tests observed 30 threads in both cases. Their short,
sequential raw echoes and different warm-up do **not** establish authenticated
throughput or a controlled before/after CPU/latency comparison. Final resource
evidence must be evaluated with source, environment and workload scope intact.

## Scaling beyond 256

No dedicated-reader growth is required to reach larger populations. Memory,
socket handles, events and protocol state still scale with clients; a constant
thread count does not make those free. Native poll has O(n) batches and the
macOS registry currently holds at most 1,024 original handles including wake
and listener owners. Java selectors and Network.framework have platform-specific
kernel limits. Before considering 512, measure these boundaries, coroutine/GC
allocation, crypto/topology CPU, foreground mobile thermal behavior, record
retention, slow readers/handlers, reconnect bursts, cancellation, revocation,
notifications and full cleanup under mixed load. Do not widen API/handshake
ceilings or advertise 512 from a readiness-model test.
