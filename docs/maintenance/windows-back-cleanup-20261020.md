# Windows Back cleanup investigation — 2026-10-20

**NOT_READY. Diagnostic improvement only; the installed Back deadline failure is
not repaired or retested by this change.** The productive rc4 provider, original
loader/JNI lifetime, MSI identity and standard-user admission remain unchanged.

## Preserved observation and source trace

The [recorded installed run](windows-local-network-and-native-20261019.md) reached
its second Host at 6871 ms and Back at 7050 ms. Its original aggregate ten-second
UI deadline expired at 10017 ms; normal application exit and enclosing retirement
did not make the UI cycle pass. There are still **zero fully accepted automated
installed cycles**, not twenty. The elapsed time alone does not identify whether
role retirement, profile close or another owner was pending.

`RpcDesktopPanel.beginClose` joins network refresh, the status observer, the exact
unlock task and role retirement before closing its retained protected profile.
It then waits for the panel and detached cleanup scopes. The new fixed labels
identify these rendered boundaries without changing their order, ownership,
exception/cancellation handling or any deadline. A failed diagnostic enqueue is
retained while the remaining physical cleanup is still attempted. The installed
control exports only exact finite phase categories; duplicate, conflicting or
unknown labels are not accepted as a phase.

Read-only tracing found that `JmdnsLifecycleCoordinator.stopAdvertising` performs
targeted service withdrawal before closing an idle mDNS handle. The native
JmDNS close separately preserves its host/service goodbye and resource-retirement
contract. Those sequential operations may contribute to the recorded Stop time;
this is **not causal proof of the historical Back timeout**. Neither the shared
coordinator nor the accepted #410 native lifecycle was changed to obtain a green
UI result. Any coalesced-close proposal needs separate exact ownership/protocol
review and evidence, not shorter waits or removal of goodbye/retirement checks.

## What was actually checked

- Linux x64, cached pinned Kotlin 2.4.10 and JDK17: compile of the exact three
  contiguous production UI helper functions and the maintained
  `WindowsInstalledUiWorkerTest`; **5/5 JUnit methods passed**, including real
  worker-thread retirement controls and finite-label/adversarial observations.
  This is not compilation of the complete Desktop module or native Windows.
- Python3 `-I -B -S`: existing installed-supervisor **28/28**, installed-admission
  driver **9/9**, native-smoke adapter **3/3** models passed. No payload was launched.
- The first focused compiler preparation refused an ambiguous cached stdlib
  filename match before compilation. Exact artifact-basename selection corrected
  the harness; no dependency/version change was made.

The maintained complete Desktop checks and genuine changed-source installed
diagnostic remain required. Neither hosted builds nor this small helper compile
can qualify Back, productive JNI or the W01–W11 matrix.

## Native environment and remaining acceptance

This continuation has a Linux terminal. The repository self-hosted-runner inventory
returned zero runners; it supplies no initialized interactive Standard-user Windows
context. No account, VM, token, DLL or installed receipt was fabricated, and none
of the earlier unchanged Error87/Error1314 launch recipes was repeated.

Use the existing canonical supervisor only after independently admitting the exact
installed source/MSI/runtime and disposable Standard-user context. Retain the first
failed result and its finite close phase. No forced fixture reset, profile deletion,
privilege grant or deadline extension is authorized. The
[W01–W11 checkpoint](windows-android-rpc-handoff-20261019.md) remains authoritative:

- W01–W04: remaining unsafe-token, first-load/module and hostile-filesystem negatives.
- W05–W07: bounded-record faults, tamper/interruption recovery and cancellation/
  uncertain-close ownership beyond the already accepted narrow native cases.
- W08–W09: independently recorded two-device typed operations, trust persistence,
  revocation and explicit-pin reconnect; owner manual success is not a full matrix.
- W10: repair/verify the actual Back boundary, then twenty accepted installed
  lifecycle cycles and resource/interruption/controller-failure cases.
- W11: exact artifact/source binding and independent review of every actual row.

Only sanitized source-bound observations belong in public records. Raw accounts,
network topology, profiles, screenshots, keys and process transcripts remain private.
