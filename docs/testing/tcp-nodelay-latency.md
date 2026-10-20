# TCP_NODELAY latency measurement

The #156 option repair is already delivered on JVM, Android and Apple. Do not
change that policy to run a benchmark. The remaining acceptance is measured
before/after PING/PONG latency, not another socket-option assertion.

`run-tcp-nodelay-latency.py` compiles/runs the checked-in Java source with an
explicit installed **JDK 17**, without Gradle, an SDK download or dependencies.
It binds the exact fixture, coordinator and three production option-source
hashes. It retains raw samples, original stdout/stderr and the source commit
and dirty flag in a new private directory outside the checkout.

```bash
python3 -B scripts/tests/tcp-nodelay-latency-test.py -v
python3 -B scripts/run-tcp-nodelay-latency.py \
  --java /path/to/jdk17/bin/java --output /outside/checkout/new-latency-result
```

The default mode is real loopback TCP, **not a real LAN or an authenticated
P2pKit session**. The two endpoints exchange fixed synthetic 40-byte PING/PONG
records with an exact sequence/payload check. This microbenchmark isolates the
transport option; it does not execute P2pKit's protocol, Kotlin scheduler, Noise,
keep-alive deadlines, or shipped LAN adapters. It is not #133 interoperability.

For each write shape (one 40-byte write; separate 4/36-byte writes), four fresh
connections use `TCP_NODELAY=false,true,true,false`. Both actual socket options
are read back before measurement. Each connection discards eight explicitly
reported warmup exchanges and retains all 32 subsequent monotonic nanosecond
samples. The control recreates only the former option policy on actual sockets;
it is **not a build of the historical library**. No deliberate sleeps, OS delayed-
ACK tuning, forced quick-ACK or protocol deadline changes manufacture an effect.
Both shapes use identical bytes and no assertion requires a speedup. Raw per-block
samples allow checking drift hidden by a pooled median/p95.

Each connect/read/accept is bounded; both directions must half-close and observe
actual EOF outside the measured exchanges. The coordinator bounds the Java
process to 120 seconds. A nonzero exit, missing block, mismatched bytes/option,
unexpected stderr, incomplete peer close or changed source is a failure, not a
slow measurement. Original failed captures remain available. No automatic retry.

## Explicit authorized two-host mode

On a separately authorized host with the **same reviewed fixture**, start one
bounded server (use a specific test-interface address, not a wildcard):

```bash
timeout 120 /path/to/jdk17/bin/java scripts/diagnostics/TcpNoDelayLatency.java \
  serve TEST_INTERFACE_ADDRESS 43156
```

Then, while the server is waiting, run the coordinator on the measuring host
with `--peer TEST_PEER_ADDRESS --port 43156`. The server accepts exactly eight
connections and exposes no general echo or arbitrary-payload service. This is an
unauthenticated measurement-only endpoint: use an isolated authorized network,
not an Internet/public interface. Retain the server source/runtime identities,
READY/COMPLETE/exit, both network/interface inventories and originals separately;
client-side metadata alone does not establish remote provenance or a LAN route.
Use a host-native bounded process supervisor instead of `timeout` where unavailable.

## Acceptance limits

A successful result says `MEASURED_TRANSPORT_ONLY` and
`acceptance: NOT_ESTABLISHED`. Loopback diagnostics can establish the mechanism
and validate the measurement pipeline, but cannot discharge #156's real-LAN
criterion or justify platform-wide speedup claims. A complete issue decision
still needs reviewed source-bound real-LAN results (and, if required by the
reviewer, the shipped P2pKit PING/PONG path rather than this synthetic transport
probe). Preserve accepted socket-option/native parity evidence; do not repeat
those original suites just to manufacture new totals.
