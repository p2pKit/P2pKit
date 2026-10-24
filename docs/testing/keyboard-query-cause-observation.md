# Native keyboard query comparison (#520)

This is an **investigation**, not a keyboard repair or a production-readiness
result. It does not alter the ordinary English/German input methods. Run it only
with explicit `component=apple-keyboard-query-diagnostic` in the existing CI
workflow, or `bash scripts/run-ios-ui-tests.sh run-keyboard-query-cause` on macOS.
The former retains source-bound encrypted observations; the local command alone
does not claim that evidence. It is never a required aggregate component. Two
warning-strict native Swift typechecks run first, before framework preparation,
so fixture compiler errors fail cheaply; they do not replace actual app/XCTest
execution. They retain the existing launcher ownership and run-directory cache.

## Falsifiable hypothesis

The original failed predicate completed one named-`1` existence query in about
4.314 seconds; its five-second outer expectation had no later evaluation.
XCTest's public `waitForExistence` uses its own polling, whereas a custom
predicate calling `exists` can incur nested native retries. This is an observed
API/timing difference, **not proof of a false negative or the historical cause**.

The diagnostic compares the original predicate with the native existence wait,
then the unchanged finite-positive geometry and actual hittability checks. The
candidate has **one absolute five-second budget**, including all phases, and
refuses any result completed after it. It never gets a second five seconds.

Each cell launches a new instance of the real sample, starts its actual kit,
reveals the production Host field and taps it exactly once. Before that tap,
a simulator-only DEBUG fixture admits exactly one attached, unfocused native
Host with its original `inputView == nil`. For delayed cells only, an empty
`UIInputView` temporarily replaces that field's standard keyboard. Nothing is
typed, pasted or assigned to its value. No focus is forced or retried.

A generated UUID scopes one install command and one wait-entry command over
Darwin notifications. Release is scheduled once from **app receipt of the wait
command**, not the earlier Host tap. The app records its monotonic receipt,
release, same-field attachment and focus; XCTest records wait/query timings and
acknowledgments. Only the originally owned input view can be restored to nil.
Field replacement, duplicate commands, lost focus or unexpected input-view
ownership refuse the cell rather than installing a successor.

Fixed cells for both strategies: no gate, 100 ms, 2,000 ms, 3,500 ms, never, and
6,000 ms. These are diagnostic availability timings, not new readiness budgets.
The late release is observed only after the original result, with no typing or
retroactive result change. Non-native scheduler calibration, if executed, is
reported separately and cannot establish how native `exists` behaves.

## Interpretation and negative controls

The app's release acknowledgment proves setter/reload return, **not an actual
visible or hittable key**. Passive UIKit focus/keyboard notifications are also
not accessibility proof. Authenticate original logs, cross-match UUID and uptime,
and inspect each realized cell before interpreting the A/B result.

- A delayed baseline must actually observe missing `1`; otherwise that cell
  did not realize the proposed trigger.
- A missing/never or too-late key must never be accepted by the candidate.
- A baseline false negative is causal evidence only if the same cell establishes
  actual available-key readiness within its budget, not merely a release timer.
- Passing repeats or both strategies behaving alike do not establish a repair.
- A newly displayed system introduction, lost app focus or unrealized release
  is a confound, not an assumed polling defect. No new/extra arbitrary system
  dismissal is added; the original Local Network interruption monitor remains.
  No preference or Simulator GUI state is changed.

The existing [post-return observer](keyboard-ordinary-context-observation.md)
collects the same log subsystem, original statuses and owned-reader retirement.
The command stays nonzero on assertion, capture or uncertain cleanup failure.
Matrix observations must be reviewed individually: successful diagnostic
execution is not successful product input, normal qualification or issue closure.

This route retains encrypted XCTest stdout and app telemetry, including the
post-verdict hierarchy when emitted. Its successful owned run directory is
normally cleaned up. The `.xcresult` and pre-Host screenshot are not uploaded by
this route; do not claim retained images or a failure-time screenshot. Paired
cells use distinct app launches on one simulator, not reset first-use state or
simultaneous observations. An A-fail/B-pass difference alone cannot prove the
baseline cell had a ready key before its deadline.
