# Two-machine hostile-network validation

**Status: NOT STARTED.** Loopback tests and a single-host firewall do not
satisfy `LAN-T08` or `ENV-02`.

## Purpose and safety boundary

Reproduce adverse LAN conditions between two independent physical machines or
devices and verify bounded, authenticated, recoverable behavior. The test
network must be isolated from production users. Obtain authorization before
capturing traffic or changing router/firewall policy; never run record-flood or
spoofing tools on a shared network.

## Required topology

- Two physical endpoints running different P2pKit sample implementations where
  possible (JVM CLI/Desktop, Android, or Apple), plus an optional third Linux
  bridge/router that applies impairment independently of both peers.
- A managed AP/router or Ethernet switch, administrative credentials, packet
  capture on the bridge/mirror port, and synchronized UTC clocks.
- Linux `iproute2`/`tc`/`nftables` is the reference impairment host. On macOS,
  use an approved Network Link Conditioner profile or `pf`/`dnctl` under an
  administrator-authored ruleset. On Windows, use a dedicated lab tool such as
  clumsy or a managed router; record its version and seed. Do not claim
  equivalence unless the tool proves the requested direction and parameters.
- Synthetic source files: 200 KiB, 5 MiB, and 49 MiB with recorded SHA-256.

Prefer this routed layout so the impairment cannot be bypassed:

```text
peer A <-> isolated LAN A <-> Linux bridge/router <-> isolated LAN B <-> peer B
```

Disable alternate routes (cellular, VPN, second Wi-Fi, direct Ethernet) or
prove from capture/path diagnostics that they were not selected.

## Baseline and evidence setup

Build/install the samples using the [test catalog](test-catalog.md). Start a
shared `LAN-T08` or `ENV-02` diagnostic session on both peers. Capture:

```bash
sudo tcpdump -i <bridge-interface> -s 0 -w <evidence-dir>/traffic.pcap
ip -details link show > <evidence-dir>/bridge-links-before.txt
ip route show table all > <evidence-dir>/routes-before.txt
sudo nft list ruleset > <evidence-dir>/nft-before.txt
```

First run an unimpaired discovery, authenticated connection, bidirectional text
message, and 5 MiB transfer three times. Record discovery/handshake/transfer
latencies and negotiated timeouts. If baseline is not deterministic, stop; an
impaired result is not interpretable.

For Linux impairment, replace `<if-to-B>` with the bridge egress toward peer B:

```bash
sudo tc qdisc replace dev <if-to-B> root netem delay 100ms 20ms distribution normal
sudo tc qdisc show dev <if-to-B>
```

Use `tc -s qdisc show` after each case. To test both directions, configure the
corresponding egress in both directions; a one-sided qdisc is intentionally
asymmetric.

## Scenario matrix

Each case starts from a clean connected baseline unless the procedure says
otherwise. Export evidence from both peers before resetting the impairment.

### C1 — latency, jitter, loss, and bandwidth

Run these profiles separately, then the combined profile:

| Profile | Reference Linux setting | Expected behavior |
| --- | --- | --- |
| Latency | `netem delay 250ms` | Handshake/transfer completes within documented bounds or fails with a typed timeout; no UI-only success. |
| Jitter/reorder | `netem delay 100ms 75ms distribution normal reorder 10% 50%` | TCP/wire framing remains ordered; retries remain bounded. |
| Loss | `netem loss 1%`, then `5%`, then `20%` | Low loss may recover; terminal timeout/disconnect at high loss is explicit and consistent on both peers. |
| Bandwidth | TBF or managed-router limit at 64 kbit/s and 1 Mbit/s | Progress advances without unbounded buffering; timeout behavior matches configuration. |
| Duplicate/corrupt simulation | `netem duplicate 2%` for packets; approved protocol harness for record duplication/corruption | TCP duplicate packets must not duplicate application records. Replayed/invalid protocol records fail authentication/replay checks. |

Example combined qdisc (record the actual kernel acceptance/output):

```bash
sudo tc qdisc replace dev <if-to-B> root netem \
  delay 150ms 50ms distribution normal loss 5% reorder 2% 50% duplicate 1%
```

Do not use packet-level duplication as evidence of application-record replay;
TCP normally de-duplicates packets. Replay/malformed records require the
independent approved harness in the secure-v2 plan.

### C2 — abrupt disconnect and peer disappearance

During discovery, handshake, idle connection, and 49 MiB transfer separately:

1. Unplug peer B's Ethernet cable or administratively bring its only interface
   down without stopping the app.
2. Wait through the configured timeout/reconnect window.
3. Restore the same interface and topology.
4. Repeat by killing peer B, then restarting it with the same authorized
   identity and with a reset identity.

The live peer must leave `Connected`, a partial transfer must not become
`Completed`, stale discovery must be removed, retries must stop at policy
bounds, and a restored peer must use a fresh connection ID. Identity reset must
require the configured authorization decision; it must not silently inherit
trust.

### C3 — interface and subnet switching

Move peer B from Wi-Fi to Ethernet, AP A to AP B, and IPv4 to dual-stack while
peer A remains active. Repeat during idle and transfer. A route/path event must
precede or explain reconnect; the next connection must use refreshed endpoint
hints. It must never continue to display or dial a stale address indefinitely.

### C4 — firewall, blocked ports, and asymmetric connectivity

Use router/nftables rules, not application changes, to:

- block the advertised TCP port in both directions;
- allow discovery but block data;
- allow A-to-B establishment while dropping B-to-A return traffic;
- block multicast DNS while allowing an already-known TCP endpoint;
- reject with TCP reset, then silently drop;
- isolate one peer from all LAN traffic.

Record the exact rules and counters. Discovery-only reachability must not be
reported as an authenticated session. Reject and drop should produce distinct
timing but both must terminate deterministically. Remove a rule before moving
to the next case.

### C5 — NAT/router variation

Repeat baseline and interruption cases on two consumer router models and one
routed/subnet-separated lab topology. P2pKit is LAN-oriented and does not claim
internet NAT traversal; failure across NAT without configured reachability is
acceptable only when explicit and bounded. No result may be described as NAT
traversal support.

### C6 — hostile discovery records and admission pressure

Run the owner-approved record generator on the isolated network. Send
wrong-AppId, malformed TXT, oversized fields, duplicate instance names,
contradictory secure/plaintext metadata, link-local/scoped addresses, rapid
add/remove churn, and a bounded flood at documented rates. Open pre-handshake
TCP connections up to and just beyond the admission limit.

Invalid records must not appear as peers, secure-v2 must not downgrade, removed
records must produce bounded lost-state cleanup, and excess connections must be
refused without starving an authorized connection. Stop immediately if memory,
file descriptors, or CPU exceed the safe host limits set in the result record.

### C7 — link-local-only direct segment

Connect two physical macOS/Linux machines by a dedicated Ethernet cable with
no DHCP server. Disable Wi-Fi, VPN, cellular tethering, and every alternate
route. Wait for both interfaces to self-assign IPv4 `169.254/16` addresses;
record interface indexes, prefixes, routes, multicast membership, and
`ping`/`arp` or `ip neigh` results. Run the JVM CLI/Desktop sample at both ends,
enable diagnostics, advertise and discover in both directions, establish
secure-v2 sessions from each end, and exchange the 200 KiB and 5 MiB fixtures.
Repeat with an Android USB-Ethernet or approved mobile peer only when its OS
exposes the physical link as Ethernet. Repeat with scoped IPv6 link-local when
both endpoints provide stable scope IDs.

The selected JmDNS bind target, discovery candidate, and TCP route must all
name the same physical interface. IPv6 literals must retain their scope; no
unscoped `fe80::` candidate may be dialed. PASS requires three repeatable
bidirectional discovery/connect/transfer cycles with matching hashes and PCAP
on the direct interface. Asymmetric discovery, binding an alternate interface,
scope loss, false Connected state, or recovery that requires enabling a routed
network is FAIL. Restore DHCP and ordinary interfaces during cleanup.

## What must never happen

- Plaintext fallback after secure-v2 failure or an authorization bypass.
- `Connected`/`Completed` UI without matching authenticated/durable events.
- Unbounded reconnect, queue growth, memory growth, file-descriptor growth, or
  disk consumption.
- Committed partial/corrupt output, duplicate committed output for one transfer
  ID, or acceptance of replayed/malformed authenticated records.
- Use of an unintended interface, cellular path, VPN, or production network.

## Pass/fail, reproducibility, and evidence

Run each mandatory profile three times with a new session ID and the same
documented seed/settings. Pass only when outcomes are deterministic within the
stated timing tolerance and both peers/capture agree. An expected typed failure
is a pass for a negative case; a hang, ambiguous state, or missing evidence is a
failure.

Retain both evidence ZIPs/JSONL files, terminal/UI recordings, PCAP, qdisc and
firewall commands/counters, router configuration export, interface/routes,
resource metrics, test-tool version/seed, exact timestamps, and file hashes.
PCAP is mandatory for `LAN-T08` and every route/firewall assertion.

## Cleanup/reset

```bash
sudo tc qdisc del dev <if-to-B> root
sudo nft list ruleset > <evidence-dir>/nft-final-before-reset.txt
```

Restore the lab's approved firewall baseline, re-enable interfaces, confirm
ordinary connectivity, stop captures, terminate record generators, remove
synthetic files, and compare routes/rules with the before snapshot. Never flush
an entire host firewall remotely unless the lab procedure guarantees recovery.

## Completion checklist

- [ ] Independent two-machine baseline completed.
- [ ] Every latency/loss/jitter/bandwidth profile repeated three times.
- [ ] Disconnect, restart, interface, firewall, isolation, and router cases completed.
- [ ] Hostile discovery/admission limits exercised safely.
- [ ] Link-local-only IPv4 and available scoped-IPv6 cases completed on a
      direct physical segment.
- [ ] Both-peer logs, PCAP, configuration, metrics, and hashes retained.
- [ ] Independent reviewer reproduced each pass/fail decision.
