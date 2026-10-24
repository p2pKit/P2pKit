# First-show keyboard: passive ordinary-context observation

This temporary investigative branch observes #520; it is not a keyboard fix or
evidence that the historical cause is known. The controlled preference OFF and ON
observations both passed the original English/German inputs. They did not
reproduce or distinguish the missing-key failure. Preference readback was not
independent hardware-attachment attestation.

## Deliberately retained context

Use the existing hosted **Compatibility** route, not the focused keyboard action.
Its eight prerequisites, ordinary launcher, selected runtime/device, headless
launch behavior, full **99 unit + 25 UI methods**, and original consent predecessor
remain unchanged. There is no preference transaction, Simulator GUI launch,
fresh-device controller, setup warm-up, extra native control stage, test filter,
retry, text injection, or change to any five-second input/equality/dismissal wait.
Original strings, per-character typing, key geometry/hittability and assertions
remain the original test's decision.

The only pre-test instrumentation is a compile define on the existing Debug
Xcode invocation. It arms the already-native-verified passive UIKit observer in
the consent and two locale app launches. The app record/observer sources and
their four standalone Swift contracts are copied unchanged from `e027b7a9`.
Those standalone controls are **not executed before the ordinary test target**.
The observer does not query accessibility, inspect field values, change focus,
send input, or alter a preference. Per app process it emits at most 64 events
plus one terminal limit marker. The test prints its existing locale/uptime marker.

## Post-return capture and status

Only on this branch's hosted Compatibility invocation, an EXIT finalizer runs
after the original Xcode command naturally returns. It reads the exact already
selected UUID, while the original launcher lock is still held and before the
enclosing owner retires native descendants. This device is **borrowed**: capture
confers no authority to boot, shut down or delete it. The reader is registered as
a foreground lock worker and owns only its own log-command descendants.

One fixed `simctl spawn <selected-UUID> log show` reads the probe subsystem, with
a retrospective three-hour window covering the unchanged 180-minute outer
Compatibility command. This window is not a sleep or execution allowance.
Collection has a 30-second ceiling and one 30-second retirement reserve, both
clamped inside the **inherited original outer deadline**. No deadline, canonical
ownership chain/domain or Gradle home is replaced. Native admission and logging
can themselves be slow; late completion remains a diagnostic failure.

The existing bounded Capture primitive retains at most 512 KiB per stream.
Only closed sinks are copied into `build/reports/keyboard-passive-probe/` and
forwarded to the already encrypted outer capture, including closed partial
failure evidence. Active writers are never copied. A closed partial sink is not
complete telemetry. Missing arming, output/capture failure, late completion or
uncertain native retirement is never diagnostic success.

The summary separates original command/launcher exits from log/capture/retirement
results. An original nonzero launcher status always survives, even if capture
passes or fails. Capture failure changes only an otherwise successful launcher
exit to 125. Signals retain 130/143; an unobserved command exit stays unknown and
no new native read begins after cancellation. The original Xcode helper is never
wrapped in `if`, `!` or `||`, which would disable Bash errexit inside it. Existing
launcher cleanup is still called once with the selected status.

## Reading an observation

Authenticate/decrypt the original packet and verify every member, exact source,
run/attempt and binding before interpreting it. Confirm all 99+25 original cases
and their order. Match each test uptime/arming record to its app process; require
contiguous events and account for any event limit or retrospective-window gap.
Do not equate XCTest's `t=` clock with UIKit uptime without an established offset.

Focus and keyboard frames distinguish app-side presentation hypotheses, but do
not establish accessibility-key existence or hittability. An original readiness
failure and its cached observation remain failures; a later AX snapshot cannot
retroactively explain that earlier state on its own. A passing full run, or a
single absent event, does not close #520. This branch must not be merged as a
default hardware-keyboard preference “fix.”

Portable checks: `bash scripts/tests/run-ios-app-test.sh`. Native Swift/UI results
still require the authorized hosted observation; Linux controls are not causal
evidence. No push or dispatch is authorized merely by preparing this branch.
