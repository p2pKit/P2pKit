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

## Completed bounded campaign: no recurrence, not a fix

[40108197428/1](https://github.com/p2pKit/P2pKit/actions/runs/40108197428)
tested commit `9a6d68cab9f318c9bbc5852a49d8784aab42df88`, tree
`e9d145ae94dc5a3aceed0a5c1481cf57c316265c`, with Xcode 26.5 on hosted
macOS arm64 / iOS 26.5 Simulator. Actual native help advertised the three
options, and the retained invocation used one serial Xcode test command with
the reviewed six-total-execution cap. All six executions of the **one original
English method** passed:

| Execution | XCTest case duration (seconds) | Result |
| --- | ---: | --- |
| 1 | 112.799 | PASS |
| 2 | 63.652 | PASS |
| 3 | 73.146 | PASS |
| 4 | 70.773 | PASS |
| 5 | 65.786 | PASS |
| 6 | 65.559 | PASS |

These are six executions, not six unique methods. Each retained nine Host,
five Port and 37 pairing single-character input activities, three Done inputs,
the original value/dismissal assertions, and normal Stop followed by app
termination. All 36 cached introduction preflights were false; their
non-atomic scope is unchanged. No readiness failure or failure-only snapshot
was observed. The three probe switches were not enabled, and no passive
collector ran. The unused DEBUG passive helper still exists in this
investigative build; this is not historical binary identity.

Artifact `12565709838` is 53,629 bytes, ZIP SHA-256
`c4a0dc0f44a990cb3bffdaeb1aba51a02b70aeea580e57d9a59cc85c2c883509`.
All four original reports (509,751 bytes) were authenticated and reviewed.
The original component and final Gradle stop returned zero, with known cleanup
and closed captures. Original stderr retains the same-device architecture
selection warning and nonfatal LLDB version-metadata errors; neither is
established as the cause of the earlier failure.

**This campaign is finished at its original cap; #520 remains open.** Do not
raise the cap, repeat it to accumulate green results, promote the earlier
candidate waiter, or infer a causal repair. A genuine failure with its cached
query facts and later accessibility context, or a deterministic trigger, is
still missing. Existing main failure diagnostics remain available during
necessary ordinary CI. No production change, full compatibility qualification,
physical-device claim or new release follows from these six passes.
