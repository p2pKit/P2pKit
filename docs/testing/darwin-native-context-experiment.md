# Darwin native-context experiment

This is a **manual, nonproductive diagnostic**, not a Release gate or a
LaunchDaemon implementation for dependency generation. The original failed
JmDNS send still has **UNKNOWN cause**. A successful send here would not prove
Local Network Privacy denial, network delivery, or JVM descendant behavior.
Existing execution HOLDs and Release **NOT_READY** remain unchanged.

## Entry and authorization

The separate workflow is
[darwin-native-context-experiment.yml](../../.github/workflows/darwin-native-context-experiment.yml).
Its only executable job is `context_experiment`, on the GitHub-hosted
`macos-26` ARM64 runner, serialized in `p2pkit-nonphysical-heavy` with cancellation
of an existing run disabled. A push to an exact reviewed
`work/release-foundation-context-*` branch registers source only: the experiment
job is skipped. Registration is not evidence that dispatch from that ref works.

Before execution, root must approve the reviewed implementation, focused offline
control results and exact source/run admission, and verify the genuine registered
workflow ID/path/ref and support for that manual source. Only two public inputs
are accepted: full lowercase `source_sha` and `source_tree`. They must match the
actual original GitHub event, workflow SHA, checkout SHA/tree, repository,
workflow path, job, owner actor/ID, triggering actor and run/attempt. Matching
mock environment labels provide no hosted/native authority.

No alternative old-controller request, workflow, ref, source mutation or main/
settings change is a fallback for failed admission. There is one immutable,
credential-free checkout; no dependency/SDK installation, Java/Gradle/Xcode or
application build, canonical initializer, cache/bootstrap or Release execution.
The selected developer directory remains
`/Applications/Xcode_26.5.app/Contents/Developer`. Missing installed tools or
unsupported OS behavior causes refusal, not installation or a settings repair.

## Four fixed native cases

Each case has the original foreground process F, a fresh system LaunchDaemon D
running as the original **nonroot** account before project Python starts, and
D's single direct Python child P. Original real/effective UID/GID and the
supplementary group set must match; the experiment never repairs a mismatch.
A separate F-owned `/bin/cat` sentinel must survive scoped cancellation and then
be retired by F through its original input EOF/direct wait and stream joins.

| Case | Required observation | Limited meaning |
| --- | --- | --- |
| N1 | One fixed42-byte synthetic IPv4 mDNS datagram, actual socket close, child0 and service0. | Kernel acceptance in this exact observed context only. |
| N2 | No UDP; child exits23, service directly waits23 and exits23; F observes its native status23. | Nonzero status preservation. |
| N3 | No UDP; real control-write EOF after readiness, original child SIGTERM/direct wait, closed streams and service24; sentinel remains the same live process. | This scoped cancellation and retirement only. |
| N4 | No UDP; child0 already joined, service sends its final frame and closes streams, then dies by SIGTERM. | Final frame/EOF cannot substitute for actual native terminal status. |

N2–N4 can pass their **negative controls** while N1 fails. A well-closed N1
failure remains an overall experiment failure; it is never normalized to success.
Unknown ownership, native status or resource closure stops subsequent cases.
There are no retries, interface hopping, alternative payloads or new foreground
comparators. Only N1 can create a UDP socket or send a packet.

Before workload START, F must register original nonchild observations for both D
and P with `NOTE_EXIT | NOTE_EXITSTATUS`, acknowledge registration and recheck
native lifetimes. Actual returned event bits and wait-status decoding are
required; missing status is never exit0. D separately retains P's original
`Popen` and direct wait. Fresh post-exec F↔D peer observations are distinct from
the inherited D↔P socketpair; inherited peer credentials do not identify P.

The whole case has **at most eight transmitted16KiB frames across both channels**,
not eight per hop:

1. D→F `HELLO`.
2. F→D `PREPARE`.
3. P→D `CHILD_READY`.
4. D→F `CHILD_READY`.
5. F→D `START`.
6. D→P `START`.
7. P→D `RESULT` (omitted in N3).
8. D→F `CHILD_RESULT_AND_EXIT_READY`, only after actual P wait/capture closure.

N3 uses seven frames: D forwards START before handling ordered F control EOF,
then requires actual P SIGTERM/wait and stream closure. It does not claim P
consumed START or made post-START progress, and invents no P RESULT. There is no
extra acknowledgment, reconnect or channel. F's independent actual P/D events
and all retirement obligations remain necessary after the final frame, including
the N4 service SIGTERM result.

Root administration is limited to literal OS executables/arguments through
`sudo -n --`. Exclusive root-private plist creation precedes held-byte tee/cat
readback; tee itself is not exclusive creation. Genuine exact-label registration,
bootout and original file/directory removal must be observed. There is no
privileged shell/project helper, broad process search/kill, leftover adoption or
recursive cleanup. An admin timeout does not prove root-process retirement.
The prospective exact-target absence parser accepts only a completed nonzero
`launchctl print` return, empty stdout, and the exact named-service diagnostic
with its optional fixed `Bad request.` prefix. It does not invent an expected
numeric exit code or treat arbitrary errors as absence. Installed output and
return semantics still require genuine observation.

## Evidence and upload

F performs one public-recipient validation against the already owner-decided
policy and keeps that original Recipient object until the one public encrypted
export. Workers never receive a keyring, Recipient, GitHub command file or
credential. No private key, new key generation or decryption occurs here.

Before freeze/export, every attempted child/service, sentinel, administrator,
stream, native handle, registration and original plist must be known retired or
closed, and source must remain exact. Freeze covers at most2MiB/128 members;
streams are separately bounded to64KiB. Unknown closure or export cleanup failure
means **no seal and no upload**, even if ciphertext files exist.

Only successful exporter return allows the same original experiment Step to
write an exclusive success or known-closed-failure seal digest to its original
`GITHUB_OUTPUT`. `export-return.json` is written after exporter return, and
`step-return.json` only after the original command-file write and close return.
Neither record is falsely claimed to be in the earlier ciphertext; the upload
guards require both. Before-upload and after-upload guards bind that seal, actual
Step outcome, source/run/attempt, exact ciphertext/manifest and actual artifact
ID/digest. A failure seal cannot pass the experiment. External cancellation,
skipped/failed guards and unsealed partial runs do not upload. Later export/
upload observations are post-export records, not falsely included in the cipher.
The after-upload guard checks and records the original action-return tuple; it
does not claim that a well-shaped artifact ID proves remote existence. Root must
independently read back the genuine run/attempt/artifact metadata and inspect
the original encrypted evidence before accepting a native result.

Only `evidence.tar.gz.gpg` and its minimal `manifest.json` enter one Actions
artifact, retained for14 days. No plaintext summary/log artifact, hidden-file
upload, overwrite or separate backup service is introduced. Encrypted artifact
access follows repository Actions permissions; decryption remains owner-controlled.
Original private inspection is still necessary before accepting native results.

Policy SHA256 remains
`2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521`.
It expires **2026-10-05T00:00:00Z**. Admission must leave the entire1440-second job
inside that window and occur before **2026-10-04T20:30:00Z**. This experiment does
not renew the policy or relax the earlier productive latest-entry boundary.

## Bounds, controls and interpretation

The proposed caps remain unmeasured until genuine execution: job1440 seconds;
allocation60; one checkout180; experiment Step720; before-upload60; one upload300;
after-upload60. Inside the original Step: prepare120, one suite-wide native/admin
window180 (each case at most40), one shared abort/retirement window120, freeze60,
export120. Every wait is bounded by its original enclosing deadlines. Neither a
case transition nor an abort obtains a fresh lease. Existing productive windows
are unchanged.

The focused suite is
[hosted-darwin-context-experiment-test.py](../../scripts/tests/hosted-darwin-context-experiment-test.py).
Its eleven offline families cover request/source preservation, root-OS
exclusivity, identity/channel distinctions, registration/status ordering,
protocol bounds, fixed socket/control outcomes, cancellation/retirement,
one-original-recipient export, upload custody and nonactivation. Offline DATA,
fake event/OS adapters and source assertions never qualify native behavior.
Do not run the suite or workflow merely because this document exists; their
separate exact-source execution decisions remain required.

Even all four cases passing and original encrypted evidence being inspected can
establish only `CONTEXT_SEND_AND_TINY_NATIVE_MECHANICS_QUALIFIED_FOR_EXACT_RUN`.
That permits considering a separately reviewed generator integration, not its
activation. It does not qualify JmDNS8 modes, JVM descendants, F/VM loss recovery,
productive orphan survival, dependency generation, cache/provider/custody chain,
ordinary scheduling, H1/H2 or Release publication. Physical work remains deferred.
