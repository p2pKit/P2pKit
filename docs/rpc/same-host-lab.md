# Same-host RPC transport experiment

This opt-in Linux fixture is **not physical LAN, cross-device interoperability,
Android/iPhone hosting capacity or release qualification**. It is a fallback
when the existing approved machines cannot supply an SDK-verifiable direct LAN
path. It never substitutes for either required Apple host or native ARM tests.

## Topology and security boundary

[`run-rpc-same-host-lab.py`](../../scripts/run-rpc-same-host-lab.py) creates two
anonymous network namespaces, each with loopback and one explicitly named
`rpc-local` **veth** endpoint. The host uses `192.168.252.1/30:28473`; the client
process uses `192.168.252.2/30`. There is no gateway, bridge, host interface,
public endpoint, VPN, SSH forwarding or route to the physical host's network.
The link kind, addresses, all route tables and policy rules are retained.
Kernels that automatically instantiate `sit0` may retain only that exact
**DOWN, unaddressed, NOARP-only** fallback. It is never selected or activated;
an active/addressed fallback or any other extra interface fails admission.

This is a new, disposable, explicitly virtual test link, **not a renamed or
whitelisted existing interface**. Java's `NetworkInterface.isVirtual` describes
subinterfaces, not proof of physical Ethernet. The fixture explicitly verifies
the real kernel `veth` type and reports that limitation; it does not present
this network as physical LAN admission. The library's existing interface-name,
flag, source/destination, self-peer and private-subnet checks are unchanged.
No production factory gains a test override or arbitrary transport injection.
The namespaces give the two real sockets distinct local/remote endpoint views.

The existing capacity distribution still uses `RpcPlatform.jvm`, strict
`OrganizationLan`, authenticated-v2 peer identity, encryption, production
framing/serialization, registered handlers and real RPC clients. There are
128 distinct synthetic protected identities and explicit public-pin approvals,
not 128 aliases sharing a key. Only public synthetic pins/readiness/telemetry
are copied between private control directories. Fixture vaults are retired by
the existing provider's cleanup. No custodian, signing or application identity
is accessed. This does not infer physical-key assurance from synthetic storage.

## Admission and execution

Start with a **clean, immutable, full-history/no-tags candidate**, its fresh
native execution context, installed JDK 17/21 and dependencies. Run the complete
native controls before building, then produce
`:p2p-sample-rpc:prepareRpcCapacityLab` through `run-audit-command.py` in that
same context. Do not copy a distribution from another source or use a retired
context. The runtime checks its exact source and each manifest-listed JAR.
For a coordinator-only correction, an immutable newer **harness** checkout may
explicitly select the unchanged prepared **product** checkout with
`--source "$SOURCE"`. Both complete clean source snapshots and the harness
file hash are separately recorded and rechecked at exit; the executor,
fixtures, manifests, JARs and all product commands still come from the admitted
product checkout. This avoids rebuilding unchanged binaries to fix a Python
network-setup assumption. Never describe that as product execution of the
newer harness SHA or mutate either checkout during the experiment.
See [native ownership](../testing/darwin-process-ownership.md) and the
[capacity contract](qualification.md).

The Linux fixture requires existing permission to create private mount, PID
and network namespaces. It refuses to set up networking unless it is PID 1 and
its initial network contains only loopback/no routes (plus the exact inactive
kernel fallback described above). The setup phase creates
only the private link and a new 2-GiB fixture tmpfs. Every observer, controller
and JVM process drops **all** capability sets, with `no_new_privs`, before
execution. Native fixture admission is repeated inside the final isolated
environment before either workload gate is released. Missing namespace
privilege is a blocker; never change host security to manufacture it.

With `SOURCE`, `STATE`, `JAVA_HOME`, `P2PKIT_AUDIT_JDK21` and the task-local
tool environment already pointing to the admitted candidate, run:

```bash
cd "$SOURCE"
unshare --mount --pid --fork --mount-proc --propagation private --net -- \
  python3 scripts/run-rpc-same-host-lab.py \
  --owner-authorized-same-host --state "$STATE" --mode steady

# Separate execution, fresh control directories and new synthetic identities:
unshare --mount --pid --fork --mount-proc --propagation private --net -- \
  python3 scripts/run-rpc-same-host-lab.py \
  --owner-authorized-same-host --state "$STATE" --mode large

# Separate, explicitly selected real-socket correctness fixtures, not capacity:
unshare --mount --pid --fork --mount-proc --propagation private --net -- \
  python3 scripts/run-rpc-same-host-lab.py \
  --owner-authorized-same-host --state "$STATE" --mode correctness
```

Never wrap these commands in an unowned kill-by-PID timeout. The original
bounded executor owns and finalizes product descendants; the controller holds
kernel pidfds only for its own workers. EOF refuses unreleased workload gates.
Failure data is retained, and an unverified drain remains failed.
An explicitly numbered `--attempt 2` (through 99) uses new `steady-2` / `large-2` / `correctness-2`
control and evidence paths rather than overwriting or deleting the first attempt.
The argument is propagated through every bootstrap stage. It is not an automatic
retry or permission to claim that a preceding failed workload passed.

`steady` retains the original 128 clients × 10 calls/s × 1,800-second schedule,
1-KiB encoded request/reply and target 2,304,000 completed calls. `large` is the
separate 20-call, 1-MiB-each-way, concurrency-two workload. It does not shorten
the interval, replay unsafe calls or relax timeouts/limits. A completed local
workload is not an approved deployment capacity or latency claim.
After the client process and its native descendants have retired, the coordinator
keeps the real host alive for at least **65 seconds of host uptime**. It requires
fresh telemetry, unchanged RPC activity/error counts and return of connected
clients, running/queued work, records and payload accounting to zero. The host
then closes normally and undergoes native finalization. A failed retention
assertion remains failed even when close succeeds. No GC is forced, process RSS
reset is promised, or original host/worker execution timeout extended.

The maintained driver uses **128 phase-spaced 10-Hz clocks** on a separately
owned single-thread scheduler; serialization, crypto and RPC calls remain on
the ordinary worker pool. It does not impose an additional synchronized
128-call microburst every 100 ms. Each client still has exactly 18,000 scheduled
calls in the same 30-minute window, at most eight outstanding calls, the same
100-ms missed-clock criterion and original call/drain deadlines. Record the
schedule version when comparing results with earlier burst-driven attempts.
Client CPU and GC MXBean counters supplement latency/scheduling observations;
GC collection time is the JVM-reported cumulative metric, **not a maximum pause
measurement**. Final host completion counters must catch up with already
successful replies within the original five-second telemetry deadline; a stale
copied sample cannot silently stand in for that final observation.

## Separate real-socket correctness mode

`correctness` starts two independent authenticated clients and a separately
selected real `RpcHost`, using the same private namespaces, production
factories, encrypted TCP/framing, durable synthetic pins and native ownership
gate. Its six exact controls cover concurrent typed response correlation with
escaped/Unicode JSON, a normal application error, rejected procedure
authorization with zero unauthorized handler entries, a deadline after verified
remote handler entry, caller cancellation after verified entry, and connection
close during an active call. The last case requires an uncertain sent outcome,
retained/idempotent close, rejection of further calls as not sent, and continued
operation of the independent observer client.

The close control distinguishes the connection's retained `Closed` state from
the existing call-admission error: with no selected attachment, a new call
fails `NotConnected` / `Admission` / `NotSent`, without allocating a request ID.
It does not demand a different error enum or modify production close behavior
to fit the fixture. Reattaching a permanently closed engine remains rejected.
Closed-set step/error diagnostics contain no exception text, IDs or payloads.

Remote entry/retirement is queried through a registered **real RPC procedure**,
not inferred from a local send. The waiting handler is deliberately cooperative
and has no side effects; this does not promise rollback or cancellation of
non-cooperative application work. Disconnect may leave it running until its
original deadline. Its deadline is not extended, and default recovery never
reinvokes the unsafe operation. Fixed, bounded test-only procedures live only
in the opt-in `jvmLab` compilation and are not registered on the steady/large
capacity host or shipped in public library artifacts. There is no arbitrary
procedure execution, authentication bypass or production factory injection.

An exit-zero process is insufficient: the launcher requires the exact six-case
record and verified client/environment cleanup, followed by the same 65-second
host retention observation and native process finalization. This mode is not
a latency/capacity qualification or a replacement for physical-network failure,
crash/restart, hostile-network, mobile or Apple/ARM execution gates.

## Evidence and limitations

Inspect `STATE/work/same-host-{steady,large,correctness}/` for actual topology, complete
native-control admission, finalization receipts and coordinator results.
`STATE/work/local-{steady,large,correctness}-{host,client}/` retains configuration,
classpath manifests, launcher results and JVM logs. These private artifacts
must not be uploaded wholesale: retain only reviewed aggregate measurements in
the runtime report. Native executor evidence remains in `STATE/evidence/`.

The existing latency histogram measures **client call-to-reply completion**
(including serialization, transport, dispatch and reply handling), using
millisecond bucket upper bounds. Scheduling delay is a separate histogram.
There is no independent wire-only or handler-only latency attribution.
Host process CPU, RSS, threads, connections, queue/retention counters and client
heap/outstanding-call samples are actual telemetry, not a hardware reservation.
Host and load generator share physical CPU/memory; report contention and
failures rather than attributing every miss to the RPC host. Percentiles for
only 20 large calls have limited statistical significance. Physical LAN,
network permissions/changes, mobile hosts and all release HOLDs remain separate.
