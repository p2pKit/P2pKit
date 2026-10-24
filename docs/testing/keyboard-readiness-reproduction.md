# Bounded original-keyboard failure acquisition (#520)

This optional diagnostic tries to obtain a **genuine recurrence**, not to make a
failure disappear through retries. It is not a release gate or a product fix.
It follows the inconclusive [query](keyboard-query-cause-observation.md) and
[reflow](keyboard-reflow-cause-observation.md) screenings without their app-side
instrumentation or synthetic input-view/banner changes.

Dispatch `component=apple-keyboard-reproduction-diagnostic` in the existing CI
workflow, or run `bash scripts/run-ios-ui-tests.sh run-keyboard-reproduction`
on a suitable macOS host. The actual selected Xcode's help must advertise all
three required options before framework preparation begins.

One `xcodebuild test` selects the **unchanged original English Host/Port method**,
serially, using standard Xcode options:

```text
-run-tests-until-failure
-test-iterations 6
-test-repetition-relaunch-enabled YES
```

Six is the maximum **total executions**, not six retries after a failure.
Xcode stops at the first failure; the command's nonzero exit is retained.
Infrastructure or cleanup failure also remains a failure. There is no external
retry loop, retry-on-failure option, changed readiness deadline, alternate input,
assertion change, injected field value or failure-to-success conversion.

The original Start, real listener-port readback, Host input, named first-key
readiness, finite geometry and actual hit tests, per-character typing, exact
value equality, dismissal and Stop remain intact. Passive UIKit, query-gate and
reflow macros are **not enabled**. The original bounded-output post-wait
accessibility snapshot remains on the failure path only.

Runner relaunch does not reset simulator permissions, keyboard onboarding or
system caches. These are same-simulator repetitions, **not six cold profiles**.
English-only execution also omits the historical preceding test order. No
Simulator GUI, preference, device-reset or global-state intervention is added.

Inspect genuine original reports and the complete iteration inventory. Multiple
executions of this one method are not distinct test methods. If all six pass,
report only **no recurrence in six bounded executions**, then stop; do not raise
the cap, repeat the campaign to claim a fix or close #520 on that basis.

CI retains encrypted original stdout/reports and source/run/artifact hashes.
The existing owned launcher/process cleanup remains authoritative. This route
does not promise uploaded `.xcresult` bundles or screenshots. A post-wait
hierarchy is later context, not an observation of a key before its deadline.

The public Xcode repetition behavior is documented in Apple's
[test-running guide](https://developer.apple.com/documentation/xcode/running-tests-and-interpreting-results#Run-testing-repeatedly-to-determine-reliability).
