# Controlled first-show keyboard experiment

This is supplemental investigation for #520, **not a fix, qualification, or
permission to retry a failing UI test**. The retained English failure occurred
before its first Host character; the subsequent German case passed. Those
originals did not observe hardware-keyboard attachment, focus, or the failed
keyboard hierarchy. Preference readback cannot retroactively establish a cause.

## Run two independent conditions

Use the existing `apple-keyboard-diagnostic` component/evidence wrapper in two
separate, otherwise idle disposable GitHub-hosted `macos-26` jobs. Keep the same
source, tools, iPhone 17 / iOS 26.5 selection and original EN/DE methods:

```bash
gh workflow run ci.yml --ref <same-reviewed-ref> \
  -f component=apple-keyboard-diagnostic -f keyboard_cause_mode=hardware-off
gh workflow run ci.yml --ref <same-reviewed-ref> \
  -f component=apple-keyboard-diagnostic -f keyboard_cause_mode=hardware-on
```

Keep that ref at the same reviewed commit for both dispatches and independently
verify both captured source SHAs. Mode-specific non-cancelling concurrency permits
independent jobs. Leave `qualification_selection` empty. The default `none`
preserves the previous unconfigured focused action. The controlled job invokes:

```bash
P2PKIT_KEYBOARD_CAUSE_MODE=hardware-off \
P2PKIT_KEYBOARD_CAUSE_ISOLATED_HOST=1 \
SIM_RUNTIME=com.apple.CoreSimulator.SimRuntime.iOS-26-5 \
bash scripts/run-ios-ui-tests.sh run-keyboard-readiness
```

The second job changes only `hardware-off` to `hardware-on`. The wrapper must
supply its original `P2PKIT_CI_COMMAND_DEADLINE_NS`; do not manufacture a new
outer deadline or supply `SIM_UDID`, `IOS_RUN_DIR`, or the internal
`P2PKIT_KEYBOARD_CAUSE_BUILD`. An existing report directory refuses a second run.
Ordinary Compatibility and unconfigured focused diagnostics are unchanged.

The controller:

- Refuses any running Simulator application or non-Shutdown simulator before
  changing a preference. A cooperative guard prevents concurrent probe jobs on
  the same account; the explicitly isolated hosted job remains a prerequisite.
- Preserves the exact absent/boolean current-user/any-host
  `com.apple.iphonesimulator:ConnectHardwareKeyboard` key, changes only that key,
  synchronizes, and checks explicit and effective CFPreferences readback before
  creating a fresh device and around the original UI invocation. No reviewed
  per-device setter is assumed. Readback is **not live hardware attachment
  attestation** or observation of Simulator's registered default.
- Binds cleanup authority to a newly created UUID absent from the initial
  inventory and the exact fresh name/runtime/type readback. Boots that device
  and launches the selected Xcode's Simulator application in both conditions.
- Compiles four pure Swift metadata controls, then runs each original EN/DE UI
  method once. The opt-in test build arms passive DEBUG-only UIKit focus and
  keyboard notification logging: closed field classifications, focus boolean,
  uptime and rectangles; never field values. It does not query accessibility,
  mutate focus/text, dismiss anything or change input/readiness/equality timing.
- Captures at most 512 KiB from the owned device with:

  ```text
  xcrun simctl spawn <owned-UUID> log show --style ndjson --info --last 1h \
    --predicate 'subsystem == "dev.p2pkit.sample.keyboard-cause-probe"'
  ```

- Uses the maintained native lifetime/audit-token supervisor and bounded capture
  implementation. Finalization shares one 120-second allowance within the
  original outer deadline: retire owned children, shut down/delete only the
  positively bound fixture, and restore/read back the original preference.
  Unexpected preference drift is not overwritten. No process-name/PID killing
  or borrowed-device cleanup is authorized.

## Evidence and interpretation

The existing encrypted report collector retains
`build/reports/keyboard-cause-probe/summary.json`, `events.ndjson`, bounded
`captures/`, and only the original `*.xcresult` subtree under `original-xcresult/`
(up to 128 MiB / 4096 entries). DerivedData and SwiftPM scratch remain outside
report discovery. The complete xcresult and raw UI captures are private evidence:
**never upload them unencrypted**. Closed partial captures preserve their error
and EOF/closure metadata; they cannot qualify a successful capture.

The original UI exit code is preserved separately. If instrumentation and
cleanup succeed, an intentional ON-condition UI failure still exits nonzero
(e.g. 65); infrastructure/capture/restoration failures exit 125, never PASS.
`underlyingHistoricalCauseEstablished` is always false in the producer summary.

Correlate `KEYBOARD_CAUSE_TEST_BEGIN`, the app's first Host editing/keyboard
notifications, the original readiness diagnostic, and its failure-only AX
snapshot. OFF interactive software keys versus ON focus retained but no visible
software-key area would support hardware suppression **in this controlled
fixture**. A visible keyboard with the wrong key/layout, a lost first responder,
or a newly observed introduction instead points to a different mechanism.
Keyboard frame geometry alone does not prove the required actual key is
hittable. If conditions do not distinguish the failure, do not claim causation
or count later passes as a correction; use the observations to choose the next
single discriminating experiment.

Portable controls:

```bash
python3 -B scripts/tests/ios-keyboard-cause-probe-test.py
python3 -B scripts/tests/ios-launcher-lifecycle-test.py
python3 -B scripts/tests/run-rpc-qualification-test.py
```
