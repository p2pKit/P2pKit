# First-Host header reflow investigation (#520)

This optional experiment tests a specific **hypothesis**, not a production fix:
inserting the existing Local Network hint above an editing Host field could
change its native ownership/focus during the first keyboard presentation.
The historical failure did not retain the native field or failure hierarchy;
its cause cannot be selected from source inspection alone.

Dispatch `component=apple-keyboard-reflow-diagnostic` in the existing CI workflow,
or run `bash scripts/run-ios-ui-tests.sh run-keyboard-reflow-cause` on macOS.
This runs only `KeyboardReflowCauseUITests` in the separate investigative target.
It does **not** repeat the previously completed native-query matrix, replace
ordinary English/German UI acceptance, or contribute to the 14-component gate.

Two fresh English app launches share one simulator:

- `beforeTarget`: insert the existing hint before revealing/tapping Host.
- `duringEditing`: insert it once on the next main-queue turn after the actual
  production Host receives its first native editing notification.

The fixture requires DEBUG, the explicit simulator compilation flag, a launch
argument, a generated UUID and a closed mode. It never assigns input, forces
focus, replaces `inputView`, changes preferences or suppresses real readiness
and banner retraction. An already-ready browser is recorded, not reset; the
hint is an explicitly synthetic layout stimulus, not a claim of network denial.
Existing unrelated errors must not be overwritten.

The test retains the original Start/port/Host prefix, one real Host tap, known
introduction handling, and five-second predicate for the original named `1`
key, finite positive geometry and real hittability. No characters are typed.
The original readiness result is frozen before diagnostic operations and
failures remain nonzero. Original Stop/termination and capture cleanup remain.

Native observations retain the original weak field/window identity, focus,
window and scroll-content coordinates, and scroll offset. The single deferred
sample is **not** an after-layout guarantee: a missing/no-op/replaced/retracted
stimulus cannot be credited as successful intervention evidence. Nothing forces
layout to make the measurement pass.

A nonce-scoped read-only Darwin receipt is requested only after the frozen
verdict. It reports cached stimulus facts, never samples or repairs the UI.
It does **not** carry the key-wait cutoff. Independent review must compare
native mutation/deferred/first-editing timestamps with the frozen wait times;
late or ambiguous realization remains unverified even if XCTest is green.
Do not infer in-budget reflow from the receipt alone.

The existing encrypted stdout and post-return native log capture retain the
observations. The failure-only hierarchy is later evidence, not readiness.
Result bundles and screenshots are not promised by this route. Native notices
do not prove accessibility-key presence (the earlier blank-input-view controls
produced keyboard notifications without any actual key). A passing experiment
records only those particular interventions; it cannot rule out intermittent
outcomes, explain the original failure or establish physical-device qualification.

## Observed result, not a repair

[40103793368/1](https://github.com/p2pKit/P2pKit/actions/runs/40103793368)
tested `9cc419613f6535a26ed3d50d60b8478135d8cea6` and **failed** with the
original XCTest exit 65. Both named-key predicates completed within five seconds,
but that does not turn the failed diagnostic into a pass:

- `beforeTarget` failed its stimulus assertion. The hint was inserted and moved
  the original field, then the real browser-ready handler retracted it **3.801
  seconds before targeting**. The rejection is correct; there was no retained
  hint at the intended interaction. The readiness check itself took 1.618 seconds.
- `duringEditing` passed. Original-field content and window Y moved 131.333 points
  with the same sampled field/window/scroll ownership and focus. The deferred
  sample preceded readiness by 0.808 seconds; readiness took 1.255 seconds. This
  was the **second app launch on the same simulator**, not a second system-cold
  keyboard. The later inactive-run event belonged to normal Stop.

Actual totals are **two XCTest methods: one failed, one passed**. Both reached
normal Stop and app termination. Original logs, seven report hashes, source/tree,
artifact digest and cleanup/capture closure were independently verified. Artifact
`12564238290` has ZIP SHA-256
`6f9f15e294cd13e009ea0fde0faa7ea2c68d11b1ea0ea4694003a561e3255fdf`.

The first absent-introduction lookup took 11.252 seconds while native observer
callbacks were also delayed. That does not identify a snapshot, scheduling or
application cause, and observers may perturb timing. Neither named-key check
reproduced the historical failure. Do not force the banner to remain, repeat
this intervention until green, or promote a speculative UI/readiness change.
The original cause in [#520](https://github.com/p2pKit/P2pKit/issues/520) remains
unconfirmed.
