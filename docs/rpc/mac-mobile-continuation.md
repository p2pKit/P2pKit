# Continue the physical RPC campaign entirely on your Mac

This is the maintained entry point for [#525](https://github.com/p2pKit/P2pKit/issues/525).
It prepares development builds and real tests, **not a release or a physical
capacity pass**. The Linux VPS, its worktrees, private audit folders, Maven token
and old downloaded evidence are not prerequisites. Do not resume the cancelled
repository-wide audit or publish a new Maven version merely to test this source.

## Delivered software and remaining device work

The source includes the opt-in `host256()` and shared readiness I/O from
[PR #524](https://github.com/p2pKit/P2pKit/pull/524). The handoff adds:

- Native ARM Mac control of Android and iPhone hosts, using the existing native
  supervisor and original protected client identities. RPC uses the approved
  physical LAN; USB is deployment/control/evidence, never a data tunnel.
- Explicit source/run/artifact-bound **schema2 128/256 profiles**. Schema1 stays
  exactly128, and defaults/`host128()` remain unchanged.
- Source-bound Mac scoped-TCP JNI staging, fixed manifest/JAR verification,
  strict dependency resolution, Android APK and signed iPhone preparation.
- Development-only exact-inbox commands for foreground test setup/start, exact
  Stop and healthy next-run preparation. Ordinary application trust/pairing
  remains explicit; this is not arbitrary peer auto-trust.
- Phone CPU/RSS/native threads plus available battery/thermal observations.
  Missing sensors remain unavailable. Serious/critical thermal observations
  abort the attempt and still require cleanup.
- Independent large-body, correctness, reconnect and thirty-minute steady
  attempts; failed evidence is retained, not overwritten or promoted by a retry.
- RPC regression repairs for fatal serializer/result-authorization ownership,
  receipt-timeout outcome reporting and terminal discovery retry refusal.

The checked-in test harness is not proof that a particular phone, signed
installation, CoreDevice output schema, USB observation deadline or physical
network has passed. The file backend accepts the historical flat CoreDevice
fields and the observed nested `metadata.size`/`resources` fields. Both paths
still require exact sizes and directory/link flags; incomplete or conflicting
metadata fails admission. The exact reviewed commit/PR and hosted checks are linked
from #525. Published [`0.8.0-rc8`](../releases/0.8.0-rc8.md) includes `host256()`
and shared readiness I/O; immutable rc7 does not. This development campaign still
requires the exact pinned source below and its source-matched lab preparation,
not a mixture of Maven binaries and newer test tooling.

## One-time preparation

1. Run the agent **on the Mac**, in an ordinary logged-in native Apple-Silicon
   Terminal session. Intel/Rosetta are not admitted by this campaign. Give the
   agent the final handoff commit and this file; no VPS access is needed.
2. Provide full compatible Xcode, complete its normal first-launch/license
   setup, and configure existing local Apple development signing. The physical
   iPhone must be registered/provisioned for that team. Apple ID/2FA, keychain
   unlock and signing keys stay on the Mac; never send them in an issue.
3. Install native JDK17 **and JDK21**, Python3.12+, Git, Bash and the maintained
   XcodeGen. The wrapper uses the repository's daemon/toolchain criteria;
   declaring `JAVA_HOME` alone is not a substitute for installing JDK21.
   For autonomous GitHub issue updates, pushes, PRs and Actions, install the
   GitHub CLI and verify the Mac's own repository access with `gh auth status`.
   If not already authenticated, use its normal local login once. Never migrate
   the VPS's authentication files or credentials; Maven credentials are not
   needed for this development campaign.
4. Install [the canonical Android SDK inputs](../testing/local.md#android-sdk-setup):
   platforms36 and37.0, platform-tools and **NDK29.0.14206865**. Accept the normal
   SDK licenses. Do not rename SDK directories or edit dependency locks.
5. iPhone: data cable, unlock, **Trust This Computer**, Developer Mode (including
   its reboot confirmation), any developer-app trust and Local Network prompt.
   The lab app targets iOS15+. Android: data cable, API24+, Developer Options,
   USB debugging, the selected test ADB RSA approval and OEM installation/app
   permission prompts. The task-private test ADB key can be reused across
   attempts; the owner's global ADB server/keys are not used.
6. Join the same approved private Wi-Fi/LAN without client isolation. Select the
   actual phone/Mac addresses and interfaces; allow only required application
   firewall access. Do not disable VPN/path admission, authentication, SELinux
   or general firewall protections to get a pass.
7. Use test devices/back up important data. Stop any existing Host before the
   first deployment. Keep the selected host app foreground/unlocked, the Mac
   awake/powered and sufficient free memory/storage. At least6GiB generator
   available memory is required during its actual preflight; allow substantial
   additional space for Xcode/NDK/Gradle and private reports.

   An owner-selected schema2 campaign may explicitly set
   `macGeneratorMinimumAvailableGiB=1` in each private settings file. Omission
   retains6GiB; schema1 and Linux do not accept this override. The actual native
   clock command records the selected threshold in schema2 evidence and the
   coordinator independently checks it against the original settings. The
   125-second observation, <100ms maximum scheduling gap and all workload,
   thermal and cleanup checks remain unchanged. A lower memory admission
   threshold is not evidence that the generator can sustain the workload;
   inspect its utilization, GC, scheduling and observed available memory.

Trust, Developer Mode, signing and OS permission prompts cannot legitimately
be fabricated by automation. Reboot/reconnect/OEM prompts may recur. Apart from
these physical/platform boundaries, the agent can build, deploy, run, collect
and diagnose locally without returning to the VPS.

## Get the exact source and prepare once

Use a new destination, never reset/clean an existing checkout. Set `HANDOFF_SHA`
to the verified handoff commit linked in #525/the final response, **not** an old
published tag or an unreviewed moving branch:

```bash
git clone https://github.com/p2pKit/P2pKit.git "$HOME/P2pKit-mobile"
cd "$HOME/P2pKit-mobile"
git checkout --detach "$HANDOFF_SHA"
export SOURCE="$(pwd -P)"
git rev-parse HEAD 'HEAD^{tree}'
git status --short
cat AGENTS.md

export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
export P2PKIT_AUDIT_JDK21="$(/usr/libexec/java_home -v 21)"
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$JAVA_HOME/bin:$PATH"
python3 --version
xcodebuild -version
xcodebuild -checkFirstLaunchStatus
```

If XcodeGen is not installed, its maintained checksum-verified installer accepts
a **new directory**, not a binary filename:

```bash
bash scripts/install-xcodegen.sh "$HOME/.local/p2pkit-xcodegen"
export PATH="$HOME/.local/p2pkit-xcodegen/bin:$PATH"
```

Remove conflicting `JAVA_OPTS`, `GRADLE_OPTS`, `JAVA_TOOL_OPTIONS`,
`JDK_JAVA_OPTIONS` and `_JAVA_OPTIONS` from this test shell. Do not put signing,
publishing or GitHub tokens in it. The runner strips publication credentials
from its child environment; it does not alter the owner's shell.

Use a **short canonical private session outside the source**. The private ADB
Unix socket has a real100-byte portable bound; a long home/DerivedData pathname
is unnecessary. `/private/tmp` avoids macOS's `/tmp` symlink:

```bash
umask 077
parent=$(mktemp -d /private/tmp/rpcm.XXXXXX)
export STATE="$parent/s"
python3 -B scripts/run-rpc-mac-campaign.py prepare --new-session \
  --state "$STATE" --team "$APPLE_DEVELOPMENT_TEAM"
python3 -B scripts/run-rpc-mac-campaign.py verify --state "$STATE"
```

`APPLE_DEVELOPMENT_TEAM` is the existing ten-character team identifier, **not a
token**. Preparation uses normal Xcode automatic development provisioning and
may require the one-time local account/keychain setup. It does not create,
revoke or upload a credential. Omitting `--team` prepares Android/Mac only;
prepare a new session after signing is available to add the iPhone producer.

Preparation runs independently supervised strict Gradle builds, stages the
source-matched Mac native library and exactly its manifest JAR, verifies the
XCFramework provenance, builds the signed development iPhone app and verifies
its signature. JVM facade and Android unit regressions must pass their original
native finalization before products are prepared. Before the tool checks, it bootstraps the checked-in Gradle
distribution with a separately supervised `--version` command in the new private
Gradle home. Distribution download has its own preparation deadline; the
unchanged 120-second wrapper Stop deadline remains a cleanup boundary.
`$STATE/private/preparation.json` binds source/tree, every
prepared JAR/native entry, APK, framework and complete signed app inventory.
Changing/additionally inserting files makes reuse fail. Unsigned app ZIP hashes
cannot stand in for the signed installed executable hash.

Source-prepared mobile campaigns use a dedicated, stable capacity-approval
namespace on each phone. Ordinary application pairing keeps its existing
Keychain/Keystore namespace and device identity. Campaign import and exact-pin
retirement cannot replace ordinary approvals. Earlier products used the ordinary
namespace: do not erase or migrate its approvals to make an old attempt start.
The capacity namespace must still be empty before import; retained approvals
produce `CapacityApprovalsRetained` and require review of the previous run.
The iPhone's development failure record retains a fixed-vocabulary `reason`
when available. Neither a refusal code nor an idle screen proves runtime closure.

Retain the exact `SOURCE`, `STATE`, pinned SHA and private settings locally in a
mode0600 continuation note outside Git. Do not copy old VPS caches, keys,
compiled frameworks or evidence into this build. A cache miss resolves normal
dependencies through the approved locked/integrity-verified repositories.

## Configure the actual devices and LAN once

Create independent settings files with the exact prepared hashes:

```bash
for phone in android ios; do
  for clients in 128 256; do
    python3 -B scripts/run-rpc-mac-campaign.py settings --state "$STATE" \
      --platform "$phone" --clients "$clients" \
      --output "$STATE/private/$phone-$clients.txt"
  done
done
```

The generated device/network placeholders are **deliberately invalid**. The Mac
agent replaces them with observed, owner-approved values, preserving source,
hash, schema and client count. Android settings select a physical USB serial
and installed ADB explicitly; iOS settings select the **wired CoreDevice UUID**,
not the simulator or an inferred first device. Keep personal device IDs private.
Select actual `enN` Mac/iPhone interfaces and the Android's actual Wi-Fi
interface. Use the source's direct-route observation as a prerequisite, not as
proof of physical Wi-Fi. A tunnel, gateway substitute, stale artifact or unknown
CoreDevice JSON is a failed admission, never a reason to invent field values.

Schema2's optional `adbCampaignKeys` points to this task's private generated key
directory. The source/tool/keys are hash-bound in its own small manifest.
Fresh servers receive owned copies and retire them; the original campaign key
stays private for later attempts. No user's `~/.android` material is opened or
copied. Approve only the test key actually displayed on the selected phone.

### Explicit wireless iPhone control

When the owner selects wireless development control, schema2 iPhone settings
may explicitly add `iosControlTransport=wireless`. First verify the selected
physical CoreDevice UUID reports `transportType=localNetwork`, an existing
manual pairing, a connected Apple control channel and enabled Developer Mode.
The backend rechecks those observations on every device verification. It never
infers wireless permission from a tunnel address, hostname or failed USB attempt;
omitting this setting retains the existing wired requirement. Schema1 does not
accept the option.

The same installed native Apple tool performs source-bound installation and
sealed app-container control over the approved local network. All RPC still
uses the separately selected production private-LAN path. The existing record
names and `usbCleanup` report field are legacy control-protocol labels; inspect
`iosControlTransport` and the explicit wireless result scope to identify the
actual control transport. File integrity, four-second observations, freshness,
Stop, identity retirement and outer native finalization remain required. An
unplugged phone's charging state and wireless observation overhead must be
reported separately; wireless control alone is not a battery-discharge pass.

## Run independent phases and retry only the failed phase

Run the small gate first. First deployment comes from the verified preparation
manifest, not an arbitrary APK/app path. Reuse the same source-bound products
thereafter; changing source requires preparing/requalifying affected products.
Each run uses a **new short label**, create-only app records and original native
cleanup. iPhone healthy next-slot preparation happens in-process; it must not
kill an active runtime just to deliver launch arguments.
Known-invalid settings are rejected before dispatch. An atomic per-phone pending
lease and immutable planned attempt are flushed, including their parent directory,
**before** installation/launch. A stable private per-phone advisory lock covers
run/recovery through retirement, so two commands cannot delete each other's lease.
Android and iPhone locks are independent; this is not a repository or Actions
exclusive window. Never delete an owner lock file to force a competing command.
A failed first attempt cannot make
the next command silently reinstall an app with uncertain existing ownership.
Continuations also bind the selected physical device, not only its product hash.

The actual native fixture runner and its prerequisite assessor share the same
current-host class selection, including capture, deadline, report-retention and
supervisor controls. A prerequisite rejection before device control can retire
only its original pending lease after native finalization, an explicit untouched
result and empty dispatch directories. The durable device-control checkpoint
is published before the first device command; an existing or partially published
checkpoint prevents this recovery. No installed continuation or phone-cleanup
claim is created from a prerequisite-only failure.

```bash
python3 -B scripts/run-rpc-mac-campaign.py run --state "$STATE" \
  --platform android --clients 128 --mode large \
  --settings "$STATE/private/android-128.txt" --run-label a128-large-01

python3 -B scripts/run-rpc-mac-campaign.py run --state "$STATE" \
  --platform ios --clients 128 --mode large \
  --settings "$STATE/private/ios-128.txt" --run-label i128-large-01
```

After admission/cleanup works on the real selected phones, run each selected
phone/profile/mode independently with new labels:

| Mode | What must be inspected | Not a substitute for |
| --- | --- | --- |
| `large` |20 exact1MiB request/reply calls on one selected real client, concurrency2, exact identity/cleanup | Full connected cohort, sustained capacity or latency qualification |
| `correctness` | Full authenticated cohort, correlation/echo, typed business/authorization errors, sent deadline/cancellation, slow-handler fairness, disconnect/reconnect and surviving cohort | A peer that refuses to consume socket bytes; result explicitly says `trueSlowConsumerQualified=false` |
| `churn` |5 rounds using the original client identities; reconnect batches≤2, exact echoes/outcomes and full cohort after | Thirty minutes of uninterrupted steady successes |
| `steady` | Separate initialization, connected-idle observations and1800s measured steady workload | Cold-start, physical radio count, background/Doze or512-client capacity |

For example:

```bash
python3 -B scripts/run-rpc-mac-campaign.py run --state "$STATE" \
  --platform android --clients 256 --mode steady \
  --settings "$STATE/private/android-256.txt" --run-label a256-steady-01
```

Once both devices' first admission/Stop attempts are healthy, the Mac agent can
schedule the remaining independent attempts without rebuilding products or
requiring another VPS command. For example, in a failure-stopping shell:

```bash
set -e
for phone in android ios; do
  for clients in 128 256; do
    for mode in large correctness churn steady; do
      if [ "$clients" = 128 ] && [ "$mode" = large ]; then continue; fi
      label="${phone:0:1}${clients}-${mode}-02"
      python3 -B scripts/run-rpc-mac-campaign.py run --state "$STATE" \
        --platform "$phone" --clients "$clients" --mode "$mode" \
        --settings "$STATE/private/$phone-$clients.txt" --run-label "$label"
    done
  done
done
```

The new labels must really be unused. A failure stops this example rather than
blindly continuing to another workload on an uncertain phone owner. The agent
can diagnose/recover and resume only the uncompleted phase with another label.
The four steady runs alone require two hours of measured workload, before setup,
idle observation and retirement. Run the phones one at a time for comparable
initial measurements; this is not the mixed physical-client topology below.

The reference steady counts are exact:128×10×1800 = **2,304,000** replies;
256×10×1800 = **4,608,000**. Initialization and idle calls/time are not steady
successes. Deliberate cancels/refusals/reconnect outcomes are separately counted;
unexpected failures, missed schedule slots, source drift, uncertain cleanup and
thermal aborts remain failures. No catch-up/retry can relabel a failed attempt.

Each coordinator retains `$STATE/work/mobile-control-<label>/result.json`, phone
series, command captures and native receipts. The JVM result, initialization and
cleanup are under `$STATE/work/mobile-client-<label>/`. Observe the real original
client exit, exact phone Stop/pin retirement and the unchanged65s post-client
record/payload drain, not just a ready message or green launcher exit.

The observation cadence is1s (formerly0.25s), aligned with1Hz phone telemetry;
the command inventory cap is20,000 (formerly15,000) for bounded protocol/retention
headroom. Duplicate sequences do not refresh freshness. The existing4s shared
USB observation and4.5s freshness bounds are not silently extended. The first
real wired control attempt must establish that this selected environment meets
them. If it cannot, retain original stage/elapsed evidence and make a reviewed
local adjustment with honest qualification scope; do not repeatedly launch an
identical doomed thirty-minute attempt.

## Analyze and recover locally

```bash
python3 -B scripts/run-rpc-mac-campaign.py analyze \
  --result "$STATE/work/mobile-control-a256-steady-01/result.json" \
  --output "$STATE/private/a256-steady-01-summary.json"
```

The report uses **phone** monotonic CPU deltas, RSS and native threads, not Mac
figures. CPU is percent of one core and can exceed100%. Inspect generator CPU,
GC and schedule lateness separately. p95/p99 are observed call-latency histogram
upper buckets, not isolated network/server latency. No arbitrary new SLO is
invented by this helper. Match charge state, brightness, ambient conditions and
workload when comparing128/256; disclose observation overhead.

USB charging means battery percentage/current/temperature are observations,
**not standalone battery drain**. Android battery temperature is not CPU/SoC
temperature; current support is OEM-dependent. iOS public APIs provide coarse
battery level/state and thermal categories, not precise internal temperatures,
per-app joules or calibrated electrical power. Missing values stay unavailable.
Actual discharge needs a separately reviewed unplugged on-device recorder or
explicitly supported control phase/external instrumentation. Simulated battery
unplug commands do not physically stop USB charging.

On failure, preserve all receipts/files. Do not reuse a run label, overwrite an
orphan seal, remove an active ownership domain, force-stop a live Host or
pre-authorize arbitrary pins. A healthy observed closed slot permits a fresh
next slot. Failed/uncertain Stop requires local diagnosis and verified retirement
before retrying; it cannot be papered over with another install. The Mac agent
can fix code, run focused tests and push a PR from this checkout; the VPS is not
part of that recovery. Do not change the maintained Apple ABI baseline merely
because an environment/provenance check failed.

If a workload fails but the original native invocation, exact phone Stop/pin
retirement and USB retirement are all healthy, the helper records that reuse
authority while preserving **FAIL** and exits nonzero. Resume only the failed
phase with another label; no reinstall or promotion of failed evidence occurs.
If the outer command was interrupted after writing its records, inspect them and
use the bounded record-verification recovery path:

```bash
python3 -B scripts/run-rpc-mac-campaign.py recover --state "$STATE" --platform ios
```

`recover` verifies the original source/argv/native receipts and exact
source/artifact/inbox-bound healthy closure before releasing this session's
pending lease. It executes no app command and never erases the original result.
Missing records, source drift, uncertain cleanup, a control-retirement failure or
a thermal abort are refused; diagnose and verify real retirement locally rather
than deleting the lease. Android uses the same command with `--platform android`.
Terminal thermal/failure records may be present on the phone even when the
coordinator stopped before copying that final sample; its local summary is not
an exhaustive sensor history.

## Remaining campaign scope, explicitly not hidden

- Physical Mac/device access, signing, wired copy schemas/timing, real LAN and
  full128/256 measurements still need their actual original evidence.
- The simultaneous **255 Mac clients + one physical-phone client** topology
  needs an explicit generator/physical-pin roster and phone-client outcome
  protocol extension. Current schema2 correctly refuses255/257; a separate
  Android↔iPhone or Mac Host↔two phones smoke is not that256-client test.
- Existing application UI supports that separately labeled functional role
  matrix: start the source-built Mac Desktop Host (`:p2p-sample-desktop-ui:run`),
  use each phone Client, compare/approve exact pins and run `users.get(123)`,
  `items.list(0,20)`, `message.send`, typed error cases, diagnostic echo, reconnect,
  revocation and Stop. Do the reciprocal Android/iPhone Host/Client cases. Use
  actual application outcomes, not generator counters, as smoke evidence.
- True socket slow-consumer/backpressure, long mixed fault workloads, precise
  battery energy and any explicitly physical background/Doze/radio/AWDL tests
  must remain pending until implemented and observed. The delivered slow-handler
  test is deliberately not described as those capabilities.
- #520's real-iOS intermittent investigation stays deferred by the owner's
  separate decision. This campaign does not silently close #462/#133 or other
  installed/physical qualification issues.

Update #525 with a sanitized source/artifact/tool/OS-bound summary and actual
completed checklist entries. Keep raw signed bundles, device IDs, addresses,
private keys and logs local/private. **Leave the issue open until its full
accepted physical scope has genuinely been met.**
