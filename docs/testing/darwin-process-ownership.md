# macOS validation process ownership

This is validation-runner infrastructure, not an RPC delivery or capacity feature.
It does not change the Release Foundation's **NOT_READY** status or any HOLD.

## Why environment markers are insufficient

On a SIP-enabled Mac, `KERN_PROCARGS2` intentionally omits environment variables
for `CS_RESTRICT` executables. A system shell or utility can inherit the exact
audit domain without exposing it to the controller. Missing markers therefore
do **not** prove that a process is unrelated. Installing another shell does not
solve ownership of the system utilities it invokes.

The [native adapter](../../scripts/audit_processes.py) keeps SIP enabled and
requires ordinary libproc/Mach access. There is no private entitlement, privileged
environment reader, process-name sweep, `killpg`, or PID-signaling fallback.

## Launch and discovery contract

1. Validate the inherited invocation/job/state/home domain before launch.
2. Start the small [exec gate](../../scripts/audit_exec_gate.py) with the admitted
   native Python, `-I -S`, and two explicitly passed anonymous pipes. The gate
   cannot start the requested executable until the controller releases it.
3. Bind the direct child's PID, kernel unique ID and start time, check its
   original parent and credentials, and acquire an opaque Mach audit token.
4. Release the gate. `exec` preserves the bound process lifetime; signaling
   reacquires/revalidates a token across exec-version changes. EOF, timeout or
   failed admission refuses product execution. Gate admission is bounded to
   ten seconds; it does not relax a product's test deadline.
5. Retain observed kernel identities in a bounded census history. The kernel's
   `p_puniqueid` is the **original parent's unique ID**, retained across ordinary
   reparenting, unlike numeric PPID. An observed chain to a positively owned
   lifetime establishes descendant ownership even when SIP hides its markers.
6. Accept the existing exact inherited-domain proof where observable. An
   observed chain to a preexisting foreign lifetime proves nonownership. Neither
   an executable name, argument, process group, nor a matching/reused numeric
   parent PID establishes ownership.

Receipts retain the real bootstrap argv separately from the resolved requested
command, gate release, direct bound identity, and each ownership proof. No opaque
token bytes or arbitrary process arguments/environment are collected by discovery.

## Fail-closed limitations

This is **not kernel containment** of arbitrary or malicious workloads. macOS
does not support kqueue `NOTE_TRACK` recursive fork tracking. A short-lived
intermediate can fork and exit between censuses; if its descendant's environment
is hidden, the missing lineage cannot be invented. Such a live process is retained
as **unclassified**, is not signaled without proof, and blocks successful cleanup.
Only a later positive ownership/nonownership observation or verified end of that
exact lifetime can reconcile it. A missing census row alone is not exit evidence.

History is limited to 65,536 observed lifetimes; ancestry walks to 256 links.
Exhaustion, identity collisions, cycles, unresolved access failures or leaked
Mach rights fail validation rather than broaden authority. Work delegated to an
unrelated OS service remains outside the process tree: simulator/device ownership
still needs its explicit, separately verified lifecycle finalizer.

An infrastructure-failed receipt is never changed into a pass after later cleanup.
Retain it and use fresh source-bound admission before resuming heavy work.

## Required verification

[Executor controls](../../scripts/tests/run-audit-command-test.py) cover system
shells/utilities, TERM resistance, actual reparenting, early leader exit, pre-exec
refusal, cancellation and pipe EOF, same-executable unrelated sentinels, stale
tokens/PID reuse, and an intentionally unobserved real intermediate. Scripted
controls cover missing/cyclic/reused ancestry and observation failures.

Native records distinguish genuine hidden-environment execution from hosts which
expose the inherited markers; neither path fabricates SIP evidence. Passing these
controls authorizes no product, supported-Intel, device, security or capacity claim.
Native requalification of this change is required before further Mac product work.
