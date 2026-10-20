# Actual secure-v2 PING/PONG latency diagnostic

This explicit JVM diagnostic addresses [#156](https://github.com/p2pKit/P2pKit/issues/156)'s
before/after protocol RTT criterion. It is not the separate synthetic40-byte TCP
probe, an independent implementation, physical-network qualification or normal CI.

Two actual P2pKit instances use unchanged `JvmLanDataTransport`, `JvmRawConnection`,
Noise-v2 authentication/record framing, `DefaultP2pProtocol` and session keepalive.
Both directions require full trusted fingerprints. Only endpoint discovery is
scripted: real TCP uses127.0.0.1, with no multicast claim. Existing test-only
socket/server factories supply real sockets. Their option setter asserts the
production transport requested TCP_NODELAY and applies either false (controlled
pre-fix option state) or true (current state). Kernel readback on the two actual
connected sockets must match before and after observation. No historical build
is substituted, no plaintext mode is enabled, and no write is split or delayed.

The initiator uses the existing100ms configurable keepalive; responder60s avoids
its own PING in the15s observation window. An observer may initially intersect
an incomplete exchange; it does not count that exchange. Thereafter every sample
requires the strict production sequence TXPING→RXPING→TXPONG→RXPONG, with monotonic
clock observations, no overlapping/reordered exchange, and no DATA frame.
RTT starts immediately before production frame encoding/encryption/write and
ends when its PONG has been decrypted/decoded at the protocol RX trace. It
includes actual JVM/coroutine scheduling, crypto, both socket paths and responder
routing; it excludes the idle time waiting for the keepalive timer. It is not
wire-only RTT or application-message response latency. Trace callbacks retain
only fixed frame types/timestamps, never payloads, identities, keys or addresses.

Four fresh connection blocks use false,true,true,false (ABBA). Each retains8
warmup+32measured RTTs. Warmups remain in the raw record but not summaries.
Fresh connection blocks are not statistically independent samples.
Per-block results are retained to expose drift; p95 uses nearest rank. The
fixture imposes no speedup threshold: no improvement on coalesced loopback is a
valid observation, not a reason to change framing or select favorable samples.

Run only a clean committed source with supported JDK17/SDK prerequisites and
strict locks/checksums; coordinate this bounded local build with other agents:

```sh
SOURCE=$(git rev-parse HEAD)
TREE=$(git rev-parse HEAD^{tree})
# Choose a new private directory; never overwrite a failed original.
REPORT=$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-protocol-rtt.XXXXXXXX")
chmod 700 "$REPORT"
./gradlew :p2p-transport-lan:jvmTest --tests '*ProtocolPingLatencyTest' \
  --no-daemon --no-parallel --max-workers=1 --dependency-verification=strict
./gradlew :p2p-transport-lan:protocolPingLatency \
  -PprotocolLatencyReport="$REPORT/raw.jsonl" \
  -PprotocolLatencyCommit="$SOURCE" -PprotocolLatencyTree="$TREE" \
  --no-daemon --no-parallel --max-workers=1 --dependency-verification=strict
python3 scripts/summarize-protocol-ping-latency.py "$REPORT/raw.jsonl" "$REPORT/report.json"
```

`protocolPingLatency` is an explicit JavaExec over the test compilation, not
wired into `check` or `jvmTest`. The measurement work has a90s coroutine bound; non-cancellable cleanup can add
two15s kit-stop budgets (up to120s before bounded source-observer overhead), so
retain a separate whole-command/retirement bound.
Setup, observation and each kit's cleanup are separately bounded. All exact
created sockets/listeners must be closed and SDK warning/error count zero before
a block passes. A first failure remains FAIL. Retain command exit, original
stdout/stderr, raw records and summaries; independently verify source/tree,
full-worktree clean pre/post readbacks (BuildInfo alone scopes only core inputs), option readbacks, event sequence and all retirements.
A source check/model or summary by itself does not prove an executed run.
