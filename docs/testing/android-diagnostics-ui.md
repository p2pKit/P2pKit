# Rendered Android diagnostics acceptance — #317

This is a **test harness and execution contract, not a recorded pass**. The
[integrated source repair](../audit/2026-09-04/repairs/317.md) already has host
Compose coverage. Its remaining [#317](https://github.com/p2pKit/P2pKit/issues/317)
criterion is a newly recorded event becoming visible while the real diagnostics
screen remains open and untouched. This narrowly scoped case may use an eligible
emulator. It does not replace any physical-device requirement in the
[validation catalog](../validation/test-catalog.md), establish frame performance,
or exercise #324 restoration or #372 permission/network enforcement.

## Component and admission

`UiAcceptanceInstrumentation` is a second, explicitly selected Android framework
`Instrumentation`, in the ordinary sample's `androidTest` source set. It accepts
**only** `case=317`, a fresh 32-lowercase-hex `token`, and 40-lowercase-hex
`sourceCommit`/`sourceTree`. Unknown/missing arguments fail. There is no default
test selection and no third-party runner or new dependency.

The existing `testInstrumentationRunner` in the Gradle file remains
`dev.p2pkit.sample.android.runtime.LanPermissionRuntimeInstrumentation`. Before
execution, inspect the **freshly generated merged test manifest and packaged
APK manifest**: both complete component names must exist exactly once, target
`dev.p2pkit.sample.android`, and the default #372 component/runner must remain
unchanged. Manifest source inspection alone does not prove the merge result.
If AGP does not preserve both, stop and review that admission failure; do not
silently redirect the default runner.

Use one newly created, invocation-owned **API35+ emulator**, a fresh sample
install/data directory, the pinned compile SDKs, and current clean source-built
app/test APKs. The app still targets API37. Record the exact runtime API, ABI,
system-image/emulator versions, device ownership, target, display metrics,
source commit/tree and both APK hashes outside Git. The runtime checks the
embedded library commit and clean-source flag; a supplied tree string is only
a declaration until the host checks source/APK provenance.

The production screen is a fixed column, not a scrollable settings page.
Pre-admit a portrait display with **at least 900dp width and 1500dp height**,
hardware rendering, screen on/unlocked, no IME and no overlay covering a target.
Do not change display size, density, font scale, window flags or production
layout during the test to obtain a pass. A smaller/occluded/clipped display is
an admission failure, not permission to scroll during observation. Screenshots
are limited to 16,777,216 pixels; individual retained PNGs to 16 MiB.

Do not boot an owner's AVD or use the Linux-only API37 driver under fabricated
host identities. Follow the [Mac ownership/evidence contract](mac-handoff.md)
and acquire the shared serial execution lease. This source addition does not
itself admit a host/emulator controller. Before launching anything, install
the controller's unconditional failure/cancellation retention and exact-owned
process/emulator teardown. No physical phone is needed or requested.

## What the harness does

1. Launch the actual `MainActivity` and obtain **its** `P2pKitViewModel` from
   `ViewModelProvider`. Require no room/smoke kit or pending operation. Select
   a synthetic `UI317`/`observer` session through existing VM methods and seed
   `probe317_a` through the actual `recordDiagnostic`/recorder/sink/revision path.
   No LAN kit, provisioning manager, permission grant, replacement content or
   production test seam is involved.
2. Open Diagnostics using its real accessibility click handler. Set the actual
   Search and Session filter fields before observation, with framework
   `ACTION_SET_TEXT`. Require their visible values, the session header,
   `1 event(s); tap rows to select`, the exact baseline row and live mode.
   Clear field focus, if any, through its real accessibility action before
   the fixed one-second settling allowance. Require no focused editable field.
3. Retain the baseline accessibility tree and **actual display screenshot**
   (`UiAutomation.takeScreenshot`), after a hardware
   `ViewTreeObserver.registerFrameCommitCallback` witness. Require nonblank,
   in-bounds target crops, an active focused app window and no higher reported
   Android window intersecting a target. This is not `View.draw(Canvas)` output.
4. Freeze input. Retain actual Activity/VM/window-token/public `ComposeView` and
   full Android View-hierarchy identity, configuration/viewport, lifecycle
   counters, window callbacks, filter/session/permission values and input-action
   counters. Observe an additional 500ms quiet interval. Read-only accessibility
   inspection and ordinary main-thread assertions do not request a recomposition.
5. On the main thread record **one** `probe317_b`, then register a callback for
   the next naturally committed hardware frame. Require exactly one recorder
   entry and revision increment, no dropped event and no other recorder mutation.
   Within **five seconds measured from recording completion**, require the same
   open/root/session/filter/lifecycle/input identity, `2 event(s)`, both exact
   rows and a new frame committed after the record. Retain the after-tree and
   screenshot; require a changed screenshot hash and a further 300ms stable
   observation. There is no click, scroll, `setContent`, `requestLayout`,
   `invalidate`, snapshot notification or Compose-state write in this interval.

The fixed body deadline is 60 seconds; setup is separately bounded to 25 seconds,
each main-thread handoff to five seconds, and each cleanup action to ten seconds.
These are fail-closed bounds, not overridable runner arguments. Framework Binder
calls are not made magically interruptible by coroutine timeouts: an approved
host controller must also impose a **180-second outer command deadline**, retain
the original failure and retire only its owned process/emulator if it expires.
An outer kill or unknown retirement is never a harness pass.

The accessibility oracle accepts either separate title text or the public
clickable Card's exact merged `title\nLOCAL` text. It rejects ambiguous targets.
It uses no reflection, internal Compose root/slot-table access, test recomposer,
fake frame clock or copied Compose implementation. Input observation includes
window key/touch/trackball/generic-motion/shortcut callbacks and framework
click/focus/text/scroll/selection/touch accessibility events. An unexpected
input, lifecycle transition, content replacement, permission-state transition
or configuration change fails rather than being filtered away.

## Fresh build and explicit invocation

After source review, host admission and strict supported-lock qualification,
build through the maintained immutable executor, with its same-home stop and
retention policy, requesting:

```text
:p2p-sample-android:assembleDebug :p2p-sample-android:assembleDebugAndroidTest
```

Inspect manifests and source/APK bindings before installation. Within the
separately admitted, deadline/cleanup-owning controller, the instrumentation
command is:

```bash
adb -s "$OWNED_ANDROID_SERIAL" shell am instrument -w -r \
  -e case 317 -e token "$TOKEN" \
  -e sourceCommit "$SOURCE" -e sourceTree "$TREE" \
  dev.p2pkit.sample.android.test/dev.p2pkit.sample.android.runtime.UiAcceptanceInstrumentation
```

These are command contracts, **not evidence of execution**. Do not invoke the
ambiguous package-only runner, `connectedAndroidTest`'s default component, or
the #372 runner and describe that as #317 execution.

The raw result identifies `no_backup/ui-317-<token>/` beneath this newly owned
sample install. Preserve that complete directory, raw instrumentation stdout/
stderr/exit status, host receipt, logcat and runtime/install/source records.
Files include `result.json`, `events.jsonl`, before/after tree JSON and PNGs;
a stale-render failure retains `failed-tree.json` and `failed.png` where the
window remains observable. No existing evidence file is overwritten. Hash the
complete retained set externally as well as checking the PNG hashes in JSON.
Only synthetic fixture evidence belongs here; never commit raw files to Git.

## Mandatory inert-bridge mutation oracle

Qualify the harness itself, not just the positive app. In a separate owned
worktree from the exact harness candidate, change **only the body** of
`rememberDiagnosticEvents` in `AndroidDiagnosticsScreen.kt` to the original
unread-delegate behavior:

```kotlin
    @Suppress("UNUSED_VARIABLE")
    val currentRevision by revision.collectAsState()
    return snapshot(filter)
```

Retain the complete one-body diff and new clean mutant commit/tree, independently
review the mutation, and produce fresh mutant app/test APKs through the same
strict build path. The harness, dependencies, display, deadlines and observation
rules remain identical. Use a new token and fresh owned install, with the mutant
commit/tree passed to the same explicit component. Never edit published history,
hand-edit locks, or suppress an unrelated build/manifest/admission failure.

For an interpretable negative control, the baseline **must pass**: the baseline
record is seeded before opening/filtering the real screen. The new record and
revision increment must then be present in retained diagnostic/injection evidence,
while the unchanged Activity/root/filter/input/lifecycle interval fails specifically
at `hands-off-refresh` because the new row/count/frame witness never arrives.
Compare the actual failed pixels/tree and original failure with the positive run.
An earlier setup failure, missed injection, different input, timeout elsewhere,
or cleanup failure is **inconclusive**, not the intended red result. A positive
mutant means the harness has an incidental refresh and must be corrected/reviewed;
do not waive this oracle or replace it with the historical host-only red test.

## Review and cleanup boundary

`HARNESS_PASS_PENDING_REVIEW` reports automated observations only. An independent
reviewer must inspect the full before/after screenshots at their recorded scale:
both event names and the count must actually be legible, not ellipsized, clipped,
black or hidden behind app-owned content. A nonblank crop is not OCR or proof of
exact text by itself. Review the frame/injection timing, immutable interval,
source/artifact provenance, expected mutant failure and every cleanup result.
Only then can this narrow rendered criterion be accepted. #317 still needs normal
review/merge/issue-closure conditions; no whole-audit or release-ready claim follows.

Finally attempts every pending frame callback removal, restores only its owned
window callback, finishes only Activities it launched, requires destruction and
the real VM's cleared/cancelled-scope witness, and removes lifecycle/accessibility
observers. The no-kit admission remains checked. Diagnostics are retained after
VM clearing. This is **Activity/observer retirement**, not a claim to inspect the
VM's private final-cleanup Job or prove the whole ART process exited. The outer
controller must verify/retire its exact invocation-owned test process, preserve
all evidence, shut down its one owned emulator, confirm retirement, stop the same
owned Gradle home if it built anything, and remove only proved-disposable outputs
after review. Unknown retirement blocks a conflicting run. Do not use `killall`,
`shutdown all`, shared-cache deletion or data clearing on an unrelated install.
