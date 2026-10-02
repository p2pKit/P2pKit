# Android mobile-host capacity candidate

This is **offline-tested coordination tooling with verified emulator shell
integration, not a completed physical USB, LAN or mobile-capacity run**. Use it
only on an owner-approved physical test
phone and organization LAN. Foundation remains **NOT_READY**. The independently
verified [same-host JVM workload](qualification.md) is a different configuration;
it need not be repeated merely to begin device testing.

## What is implemented, and what is not verified

[`run-rpc-mobile-capacity.py`](../../scripts/run-rpc-mobile-capacity.py) runs the
existing JVM synthetic client driver on **Linux x86-64**, with a physical Android
phone as host. The existing native executor owns all child processes and must
pass its complete native control inventory. No new transport, permissive identity
store, automatic pairing, KVM exception or public endpoint is introduced.

- A new private ADB server uses only its own Unix socket and fresh test host
  keys; no existing key, global server, wireless connection or forwarding is
  used. The owner authorizes that new USB identity on the selected phone.
- ADB shell-v2 carries only bounded app-private configuration, readiness,
  telemetry and Stop records. **RPC traffic itself goes over the selected LAN**,
  through `RpcPlatform.android` and the existing authenticated JVM clients.
- Exactly 128 independent protected client identities are created and retired
  by the existing provider. The phone imports their public pins only after the
  owner reviews the network/pins and explicitly presses **Start host**.
- The ready/telemetry/Stop/closed records bind run nonce, product commit,
  installed APK hash and Android platform. JVM telemetry cannot stand in for
  Android CPU/RSS/thread measurements. Duplicate samples do not refresh time.
- Immutable Android records are create-only data plus empty `.complete-<name>`
  seals; partial/orphan/malformed records fail closed. Only telemetry rotates.
  The shell has separate security predicates, not fall-through `test A && test B`
  expressions under `set -e`. This is not crash-safe RPC storage.
- Descriptor metadata uses the source-matched debug APK's fixed `RpcLabFdStat`
  entry through system `app_process`, still under the app's `run-as` UID. Public
  `Os.fstat` retains dev/inode/mode/owner/link/size/time checks on the actual open
  descriptor; it does not assume API24's `stat` supports `-L` or reopen a path.
  Only this fixed installed internal/base APK is admitted, not split APKs,
  adopted storage, arbitrary classes or an older package lacking the helper.
- The selected Linux route must be direct, use the approved source/interface,
  and contain no gateway/tunnel/encapsulation. That diagnostic is **not physical
  LAN proof**; the production OS/path admission still executes on both peers.
- The original healthy 125-second generator preflight, full workloads,
  initialization accounting, call/readiness/freshness limits, exact native
  finalization, 65-second idle retention and Stop/pin cleanup remain required.

The Python/POSIX controls cover hostile files, concurrent writers, foreign
source/run/role records, stale observations, failed workloads, source drift and
cleanup. Mocked phones/receipts are expressly **not** device evidence. The actual
Android file/resource methods passed on the supplemental API-24 emulator; the
first complete private-server/shell-v2/physical-phone control run is still required.

The [source-bound handoff at `ea566ef4`](device-testing-handoff.md) additionally
passed **all nine actual Android shell-v2 file commands**, including exact
descriptor metadata, original-content re-read, missing records and refused
overwrite/duplicate Stop. Software-emulator preparation took 5.003 s and reads
10.006–10.606 s, under that harness's unchanged **40-second** command limit.
Those timings do **not** establish the physical coordinator's original
**four-second observation budget**; it remains unchanged and untested on a phone.
Do not run a phone workload until that actual USB/readiness admission succeeds,
or lengthen its limit to reuse a slower emulator result.

There is **no admitted iPhone USB coordinator**. The candidate `IosUsb` explicitly
refuses execution rather than relying on guessed `devicectl` copy/exit behavior.
Create-only app-container publication, partial-read protection, source binding
and exact cleanup must be verified with real Xcode/device access before that
adapter can be implemented safely. This does not remove any Apple/ARM gate.

## Prerequisites and source-matched driver

Use a dedicated Linux x86-64 generator with installed Python 3.12+, JDK 17,
`iproute2` and current Android platform-tools; no install/build is performed by
this coordinator. The unchanged preflight requires at least 6 GiB available,
no balloon inflation and no 100-ms clock gap. Stable resources throughout the
full run, not just the preflight, remain part of evidence review.

Keep the phone foreground, physically attached by USB, on the approved Wi-Fi
network, and running the source-matched **P2pKit RPC Lab** debug app. Inspect its
actual interface/address; `wlan0` below is an example, not an inferred selection.
Resolve local-network permission and device Developer/USB approval locally. Do
not disable production authentication, SELinux, firewall or network admission.

The feature-only Android handoff additionally supports the separate artifact
`rpc-mobile-jvm-test-driver-<exact-product-commit>-<attempt>`. Its exporter rechecks
all six original native receipts and canonical copies, complete native inventory,
all ten instrumentation controls, both original/exported APKs, and every prepared
JAR before exposing the archive. A failed/changed/partial handoff exports no
driver. This is a **test distribution**, never a Maven/release publication.
Only use an artifact whose actual successful run and hashes are recorded in the
[handoff](device-testing-handoff.md); workflow configuration alone is not delivery.

Verify the downloaded driver manifest, original Android manifest hash, archive
size/hash and every entry before extracting its flat `manifest.json`/JAR set into
a **new** `samples/p2p-sample-rpc/build/capacity-lab/` in the exact product checkout.
Never replace an existing distribution. The launcher independently rechecks the
source commit and every JAR. Do not mix an APK and JAR manifest from different
commits, or relabel old binaries as a newer source.

Set `SOURCE` to that absolute canonical, clean product checkout and `HARNESS`
to a clean checkout containing the coordinator. Usually these are the same.
The optional `--source` permits a later harness/documentation-only revision while
leaving the verified product immutable: **both** snapshots and the coordinator
hash are separately recorded and rechecked. All native/product commands and
the prepared driver still come from `SOURCE`.

## Private configuration and one execution

These are owner-device commands, **not commands already executed on a phone**.
Use a new private native state **outside** either checkout, with a short path
(the private ADB Unix socket must fit the original 100-byte bound):

```bash
umask 077
parent=$(mktemp -d "${TMPDIR:-/tmp}/rpc-m.XXXXXX")
export STATE="$parent/s"
source_sha=$(git -C "$SOURCE" rev-parse HEAD)
python3 -B "$SOURCE/scripts/run-audit-command.py" init \
  --root "$SOURCE" --state "$STATE" --expected-commit "$source_sha" --host linux-x64
mkdir -m 700 "$STATE/work" "$STATE/private"
export P2PKIT_AUDIT_STATE_DIR="$STATE"
export GRADLE_USER_HOME="$STATE/gradle-home"
export RPC_CAPACITY_LAB_AUTHORIZED=synthetic-private-network-only
```

`JAVA_HOME` must already select the installed native JDK 17. Keep signing,
publishing and GitHub credentials out of this test shell. Do **not** fabricate
`P2PKIT_AUDIT_OWNERSHIP_CHAIN`; the real outer executor establishes it.

Create `$STATE/private/settings.txt`, mode **0600**, using the exact selected
device, approved numeric addresses/subnet and installed APK hash. All eleven
keys are required; no private key or pairing invitation belongs in this file:

```text
schema=1
sourceSha=<exact product commit>
hostArtifactSha256=<verified installed base APK SHA-256>
endpointAddress=192.168.14.2
port=48123
subnets=192.168.14.0/24
interface=eth0
localAddress=192.168.14.3
hostInterface=wlan0
androidUsbSerial=<explicit physical USB device serial>
adb=/absolute/installed/platform-tools/adb
```

These network values are examples. Record the real route/interface and physical
topology privately; do not use the example subnet unless it is actually approved.
An emulator, network ADB serial, gateway route or stale APK/source binding is
rejected, not a reason to loosen a gate.

Run one mode through the existing native executor, keeping its exit and receipt:

```bash
label=android-01  # New per attempt; never reuse or overwrite a phone run directory.
mode=large      # Start with the separate 20-call / 1-MiB / concurrency-two gate.
args=(python3 -B "$HARNESS/scripts/run-rpc-mobile-capacity.py"
  --owner-authorized-mobile --source "$SOURCE"
  --settings "$STATE/private/settings.txt" --run-label "$label" --mode "$mode")
status=0
python3 -B "$SOURCE/scripts/run-audit-command.py" \
  --cwd "$SOURCE" --wrapper "$SOURCE/gradlew" --kind command \
  --purpose mobile-coordinator --timeout 4800 \
  --receipt "$STATE/private/mobile-outer.json" -- "${args[@]}" || status=$?
python3 -B "$SOURCE/scripts/check-audit-receipt.py" \
  --purpose mobile-coordinator --cwd "$SOURCE" --wrapper "$SOURCE/gradlew" \
  "$STATE/private/mobile-outer.json" "$status" -- "${args[@]}"
test "$status" = 0
```

The outer envelope includes the complete native controls and preflight; it does
not extend any inner workload, RPC or cleanup deadline. On the phone, approve
only this new private USB key when prompted. After the coordinator announces the
prepared run, enter its label, select **Load prepared USB capacity session (not
approval)**, review the network and synthetic pins, tick the import approval,
then **Start host**. Loading is not approval. The original 120-second RPC
readiness bound begins after USB authorization and is not extended for slow UI
interaction. No background service or automatic permission approval is used.

For `steady`, use a **fresh state and label**, repeating the exact source-bound
setup with `mode=steady`. The measured workload is still 128 clients × 10 Hz ×
1,800 seconds, with 1-KiB bodies both ways and **2,304,000 successful replies**.
The separately counted 76,800 initialization calls are not steady replies.
No missed clock, local permit refusal, failed RPC, timeout or failed cleanup
can be turned into a pass by retries or catch-up traffic.

## Evidence, cleanup and handoff

Private results are under `$STATE/work/mobile-control-<label>/result.json`,
with the existing client/provider evidence under `mobile-client-<label>` and
all native receipts under `$STATE/evidence`. Retain failed attempts. The result
includes source and harness snapshots, settings/tool hashes, real host samples,
client latency/accounting, initialization, resource observations, retention,
Stop and USB cleanup. Client-call percentiles are not wire RTT or isolated
server processing time. No numerical latency SLO was approved; record p95/p99
without inventing a pass threshold.

The coordinator can report only
`MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW`; both physical-LAN and
mobile-capacity qualification booleans remain false. Review the full source-bound
measurement and phone resource series, verify the outer native receipt, exact
identity retirement and actual topology, and complete physical/security tests
before awarding the appropriate gate. A valid failed measurement is retained
even when a separate control/cleanup failure prevents success.

Controlled Stop requires runtime closure and retirement of the imported RPC
pins. Only the newly created ADB server/keys are retired; no global server or
unrelated device/process is stopped. Unknown/replaced key metadata fails cleanup
and is preserved for review, never deleted by guessed PID or wildcard.

The phone's private run control files are **retained as evidence**, not silently
purged. They contain synthetic public pins and selected endpoints, not private
client keys. USB authorization on the phone is not automatically revoked; retire
it through the owner's device controls after preserving evidence. Use a dedicated
test profile/app installation if later deletion is desired. Do not erase an
existing production application's storage or unrelated USB authorizations.
Never upload raw control directories, device serials, keys, invitations or
unsanitized network/application logs. Supply only a reviewed numeric/source/hash
summary under the existing [validation rules](../validation/README.md).
