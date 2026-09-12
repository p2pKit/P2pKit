# Continue the audit on a Mac

**Start from `main`; do not restart the audit.** The [checkpoint](../../AUDIT_CHECKPOINT.md)
and [issue records](../audit/2026-09-04/issues.json) retain the completed work and
exact limitations. [Consolidation/branch decisions](../maintenance/repository-consolidation-2026-09.md)
explain the six unqualified dependency proposals intentionally kept separate.

Status at handoff: **206/234 repair approvals (88.0%), 207 resolved (88.5%),
27 unresolved (11.5%)**. Those are issue-row counts, not effort or readiness.
The audit is **NOT_READY**; independent interoperability **#133 NOT_STARTED**.
No tag, release, issue closure, product decision or additional behavior change
is authorized by repository consolidation. Preserve `0.7.0-SNAPSHOT`, immutable
RC3 and the [0.8.0+ behavior restrictions](../releasing/checklist.md).

## 1. Get the preserved source

Use a new destination; never reset, clean or overwrite an existing checkout:

```bash
git clone --branch main https://github.com/p2pKit/P2pKit.git "$HOME/P2pKit-mac"
cd "$HOME/P2pKit-mac"
git status --short --branch
git rev-parse HEAD 'HEAD^{tree}'
git merge-base --is-ancestor 85c72e530d2881f8a7387c665d8331c553e5d26f HEAD
```

Compare the printed commit/tree with the final consolidation report. If main
advanced, inspect/reconcile the newer commits rather than resetting it. Use a
full-history clone so retired prose remains retrievable with `git show`.
Read `AGENTS.md` and `CLAUDE.md` without editing them, then the checkpoint,
[audit index](../audit/2026-09-04/README.md), [follow-ups](../audit/2026-09-04/followups.md),
[local testing](local.md) and [release checklist](../releasing/checklist.md).
Refresh affected GitHub issues/comments/PRs before choosing the next repair.

Do not copy `.gradle`, `.konan`, DerivedData, old CLI/XCFramework binaries,
credentials, signing keys or somebody else's `local.properties` into this clone.
Private historical evidence is reviewed separately, never restored as build input.

## 2. Install the actual prerequisites

Use an ordinary user Terminal/SSH session on a native Mac. The retained toolchain
selections are **Apple Silicon/macOS 26/Xcode 26.5**, or **true Intel/macOS 15/Xcode
26.3**. Install full Xcode, complete its normal first-launch setup and install the
applicable iOS simulator runtime. A different toolchain needs reviewed admission,
not silent substitution. Rosetta is not native Intel qualification.

Install native **JDK 17 and JDK 21**: 17 launches the wrapper/library test toolchain;
`gradle/gradle-daemon-jvm.properties` selects daemon 21. The isolated executor
disables JDK auto-download. Also provide native Python 3, Bash, Git, Ruby (standard
library), curl, unzip, shasum, jq and xmllint. Artifact review needs gpg/gpgconf and
your own authenticated GitHub CLI (`gh`); do not transfer another agent's credentials.

```bash
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
export P2PKIT_AUDIT_JDK21="$(/usr/libexec/java_home -v 21)"
export PATH="$JAVA_HOME/bin:$PATH"
case "$(uname -m)" in
  arm64) ROLE=macos-arm64; export DEVELOPER_DIR=/Applications/Xcode_26.5.app/Contents/Developer ;;
  x86_64) ROLE=macos-x64; export DEVELOPER_DIR=/Applications/Xcode_26.3.app/Contents/Developer ;;
  *) echo 'A supported native Mac is required' >&2; exit 1 ;;
esac
export ROLE
python3 -c 'import platform; print(platform.system(), platform.machine())'
"$JAVA_HOME/bin/java" -version
"$P2PKIT_AUDIT_JDK21/bin/java" -version
xcodebuild -version
xcodebuild -checkFirstLaunchStatus
ruby --version
df -h .
vm_stat
```

Check `sysctl -in sysctl.proc_translated` separately: accept native `0`, or the
absent-key/exit-1 case on a native host—not `1` or an unexplained failure. Verify
Python and both Java architectures too; `uname` alone does not establish native
execution. Do not run that optional-key query under unconditional `set -e`.

Install Android Command-line Tools and **both** compile platforms. The protected
agent guide names the library platform only; the sample additionally needs 37.0:

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"  # your actual SDK installation
unset ANDROID_SDK_ROOT
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$ANDROID_HOME" --licenses
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$ANDROID_HOME" \
  'platforms;android-36' 'platforms;android-37.0' 'platform-tools'
grep '^AndroidVersion.ApiLevel' "$ANDROID_HOME/platforms/android-36/source.properties"
grep '^AndroidVersion.ApiLevel' "$ANDROID_HOME/platforms/android-37.0/source.properties"
```

Require literal metadata `36` / `37.0`. Do not rename SDK directories or change
catalog pins. Any local `sdk.dir` overrides `ANDROID_HOME` and must agree with it.
Accept licenses yourself. Install pinned XcodeGen with
`bash scripts/install-xcodegen.sh /absolute/new/owned/xcodegen` when Swift/project
work is next; add the returned bin directory to PATH rather than installing a
different version. See [canonical setup](local.md#android-sdk-setup).

## 3. Resume in this order

1. **Real host admission:** functioning local multicast and real simulator/runtime
   inventory. The old Intel 120-second runtime timeout and startup5 SEND failures
   are not fixed by moving a branch. An ordinary new Mac is a meaningful new host;
   do not repeat the unchanged hosted failure, widen deadlines, fabricate events,
   override privacy controls or infer readiness from `simctl help`.
2. **Complete supported lock generation:** six locks still retain removed upstream
   JmDNS membership. On a dedicated mutable branch from the selected main commit,
   run the maintained writer below. This includes check/Dokka/SBOM and requires
   working prerequisites; it is not a cheap resolution-only probe.
3. **Freeze the reviewed candidate**, then qualify #410 lifecycle and #413 retained
   aggregate ABI, and #409's genuine current Swift/JVM RAW-clock/activity case.
   #417/#420 and earlier approved repairs must not be reimplemented. Obtain fresh
   independent final review of each completed repair before starting another.
4. **Final current gates:** whole check, applicable samples/consumers, strict
   Dokka/publication shape/SBOM, all required ABI, Swift/XCFramework and true Intel
   execution. Plan one final release-gate cycle instead of repeating its component
   full builds. External host/simulator scope is not physical/independent acceptance.
5. Only after these are complete, revisit the **21 external rows and owner decisions
   #120/#274/#284**, as previously ordered. They remain deferred, not waived.

### Mutable lock writer (not an immutable audit leaf)

```bash
BASE="$(git rev-parse HEAD)"
git switch -c work/mac-lock-qualification
# Set a fresh exclusively owned GRADLE_USER_HOME and bounded policy first.
scripts/prepare-dependency-update.sh "$BASE"
# Unconditional same-home stop is required, also on failure/cancellation:
./gradlew --stop --console=plain
git diff --binary HEAD -- '*lockfile' gradle/verification-metadata.xml
git diff --check
```

Arrange an EXIT/failure finalizer for that stop **before** launching the writer;
retain original command and stop statuses separately. Use at most two Gradle
workers, no parallel execution, bounded heap and in-process Kotlin compilation in
the owned home's `gradle.properties`. Keep raw command/stop logs, all 12 before/after
lockfiles, metadata and independent artifact-review results outside Git. Stop only
workers owned by this invocation; preserve evidence before disposing its outputs.

The underlying full operation is `./gradlew resolveAndLockAll --write-locks
--write-verification-metadata sha256 --no-configure-on-demand`. Do not hand-edit
locks, exclude required tasks, accept partial writer output, weaken strict
verification or wrap the mutating writer in the immutable leaf executor (which
correctly rejects source changes). Review the complete candidate before committing;
then use a clean checkout and new immutable state for qualification. No version
bump is part of the consolidation. Follow the [dependency procedure](local.md#reviewed-update-workflow).

The only current pre-lock standalone JmDNS diagnostic is inline in the historical
startup workflow. If an ordinary Mac needs that narrow probe, extract/review its
public logic separately; do not use a large blind writer rerun as an OS probe or
depend on an unpublished private helper.

## 4. Branch-agnostic immutable execution

For bounded host-admission probes, initialize a **new** state at clean main now.
After the mutable writer, initialize a different new state at the reviewed clean
candidate for qualification. Keep each state outside its checkout.
Resolve conflicting ambient JVM/Gradle options first; do not
bypass executor rejections. The public leaf creates real local ownership IDs,
uses strict verification/two workers/no parallelism and always stops its own
Gradle home and drains owned descendants. It is not the hosted `Host.run()`.

```bash
umask 077
export ROOT="$(pwd -P)" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
mkdir -p "$HOME/P2pKit-local-evidence"
EVIDENCE_BASE="$(cd "$HOME/P2pKit-local-evidence" && pwd -P)"
RUN_PARENT="$(mktemp -d "$EVIDENCE_BASE/mac-$ROLE.XXXXXX")"
export P2PKIT_AUDIT_STATE_DIR="$RUN_PARENT/state"
SOURCE="$(git rev-parse HEAD)"
python3 scripts/run-audit-command.py init --root "$ROOT" \
  --state "$P2PKIT_AUDIT_STATE_DIR" --expected-commit "$SOURCE" --host "$ROLE"
export GRADLE_USER_HOME="$P2PKIT_AUDIT_STATE_DIR/gradle-home"
export KONAN_DATA_DIR="$P2PKIT_AUDIT_STATE_DIR/konan"
export ANDROID_USER_HOME="$P2PKIT_AUDIT_STATE_DIR/android-user"
export P2PKIT_GRADLE_EXECUTOR="$ROOT/scripts/run-audit-command.py"
export P2PKIT_XCODE_JOBS=2

leaf() {
  local kind="$1" purpose="$2" seconds="$3" code receipt
  shift 3
  receipt="$P2PKIT_AUDIT_STATE_DIR/host-$purpose.json"
  if python3 "$ROOT/scripts/run-audit-command.py" --cwd "$ROOT" \
      --wrapper "$ROOT/gradlew" --kind "$kind" --purpose "$purpose" \
      --timeout "$seconds" --receipt "$receipt" -- "$@"; then code=0; else code=$?; fi
  python3 "$ROOT/scripts/check-audit-receipt.py" --purpose "$purpose" \
    --cwd "$ROOT" --wrapper "$ROOT/gradlew" "$receipt" "$code" -- "$@" || return 125
  return "$code"
}

# New-host ownership controls, not product or native protocol qualification:
leaf command executor-native-controls 1800 python3 scripts/tests/run-audit-command-test.py \
  --expected-host "$ROLE" --evidence-dir "$P2PKIT_AUDIT_STATE_DIR/evidence/native-controls"
leaf command simulator-runtimes 120 xcrun simctl list --json runtimes
leaf command simulator-devices 120 xcrun simctl list --json devices available
```

Stop on any failed admission/receipt. Inspect the actual runtime/device JSON and
select one available **originally Shutdown iPhone 17**. Record its UUID privately.
Around every simulator run, arrange a finally action to re-inventory, shut down
only that owned device if it booted, and verify Shutdown; retain all observations.
Unknown retirement blocks the next run. No `shutdown all`, `killall` or service reset.

Select the smallest still-needed gate, not all of these consecutively:

```bash
# Full profile actually runs ./gradlew check --console=plain plus strict/fresh flags.
leaf command mac-platform-full 7200 python3 scripts/run-platform-tests.py full
# Final complete secret-free gate includes that profile, ABI and consumer work:
leaf command release-gate 10800 bash scripts/run-release-gate.sh
# Separate true Intel host only, after its own real runtime admission:
leaf command intel-platform 7200 python3 scripts/run-platform-tests.py ios-x64
```

These are choices for the next operator, **not executions performed during cleanup**.
Do not claim a replay of components ran the release monolith. Use unique purpose
names; never overwrite failed receipts. Sample requests not already covered include
`:p2p-sample-android:assembleDebug`, `:p2p-sample-desktop:installDist` and
`:p2p-sample-desktop-ui:createDistributable` through `leaf gradle`.

## 5. Retain evidence before immediate owned cleanup

The leaf retains reports/test-results, **not every generated ABI dump or Swift
xcresult**. Before disposing outputs, retain/hash the actual generated counterparts
of all eight committed ABI baselines, their task/path map and original logs.
Do not copy baselines as claimed generated evidence. The three custom Android ABI
checks remain mandatory; Android-only built-in `NO_SUPPORTED_DUMP` is not a pass.

#410 needs the natural outcomes/resource/goodbye logs of all eight lifecycle modes,
not just its startup diagnostic. #413 needs the retained additive Klib aggregate
and independent final review. R21 Swift28 + isolated1 and R22 ARM4 are dated scoped
positives: review current input deltas and decisive raw evidence for reuse rather
than automatically rerunning them.

#409 still needs the real 204800-byte transfer **in each direction**, pre-Dial
activity and RAW timing, current CLI/app/framework provenance, consent/pin, Swift
Stop and natural CLI quit. Its public shell actions are `prepare-jvm-transfer` /
`run-jvm-transfer` in `scripts/run-ios-ui-tests.sh`. They require a real fresh
producer, the four sidecars and `xcframework-sidecars.json` bound to
`host-xcframework-build.json`; merely exporting an executor does not establish reuse.
Use the maintained producer/retention contract in `scripts/run-audit-host.py` as
source guidance, **not** a local host-driver invocation. Keep `work/swift-ui`
results and `.xcresult` bundles before cleaning; never transfer synthetic key homes.

Use `python3 scripts/run-audit-command.py cleanup --state "$P2PKIT_AUDIT_STATE_DIR"
--path /exact/owned/output` only for confirmed allowed roots absent at init, after
dependent consumers/evidence retention. The guard refuses tracked source, unknown
ownership and unfinished leaves. It does not admit `state/work/swift-ui`; explicitly
retain that work until review, then remove only its proved-owned disposable contents.
Remove invocation-only caches/tools when no longer needed; preserve required
dependencies, evidence and unrelated tasks. Never recursively delete directories
by the name `build`: `buildSrc/src/main/java/dev/p2pkit/build` is production source.
Check disk/RAM during long work and leave no owned servers, workers or simulators running.

## 6. Historical evidence and hosted boundaries

The VPS's private raw packets remain outside Git at `/root/p2pkit-audit-2026-09-08/`;
the requested owner worksheet is `/root/projects/P2pKit-remaining-work-2026-09-12.md`.
If needed for review, transfer **selected** packets via the owner's private SSH/SFTP
channel and verify the manifests/hashes recorded in `checkpoint.json`. Do not copy
the whole tree with cache symlinks, credentials or old build inputs. Preserve failure
and partial-salvage limitations. Some original raw evidence was already lost; do not
invent it. A clone is sufficient to continue source work, not to certify missing raw
evidence or automatically accept historical results.

The four audit-branch-only workflows and `run-audit-host.py` are deliberately not
retargeted. Never fabricate `GITHUB_*`/`RUNNER_*` IDs, resurrect the retired branch
or remove exact-ref admission to make local execution look hosted. Normal CI/OSV,
dependency submission and the separate Intel workflow remain active. Reconcile
queued/running work and hold the shared execution lease before local builds; do
not overlap independent heavy jobs or cancel unrelated tasks.

OSV remains **EXCEPTED_NOT_FIXED** for GHSA-r937-wjx7-w2jp / CVE-2026-53914,
expiry **2026-10-31**. Kotlin 2.4.10 is affected; available 2.4.20 is unqualified.
Changed locks require a current scan/submission. Do not extend the exception or
call a zero-unignored-result scan vulnerability-free. No whole-audit completion
date is defensible until ordinary-host admission, remaining gates and external
requirements are satisfied.
