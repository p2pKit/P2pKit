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
requires ordinary libproc/Mach/libbsm access. There is no private entitlement, privileged
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
5. Pass an additional anonymous-pipe endpoint through the gate. The controller
   retains **both** endpoints until finalization, preventing kernel-object reuse.
   libproc's bounded descriptor census can identify that same kernel pipe in a
   restricted executable even after reparenting and exec. A descriptor number,
   pathname or environment digest alone is never proof. Nested adapters pass
   only inherited descriptors whose live pipe identity matches their binding;
   closed or reused descriptors are not forwarded. Raw opaque pipe handles are
   never included in the environment, logs or receipts.
6. Accept exact inherited-domain proof where observable. Retain a bounded kernel
   identity history for non-reaper parent links. An observed chain to a positively
   owned lifetime is additional proof; a preexisting non-reaper foreign ancestor
   can establish nonownership. Traced parentage is not accepted as such proof.

**Important kernel limitation:** `p_puniqueid` survives ordinary reparenting, but
an **exec after reparenting replaces it with the current parent's unique ID**.
Consequently, an observed launchd identity is **not** an original-parent anchor
and never proves that an unmarked process is unrelated. The retained
`originalParentPidVersion` field is diagnostic only: a wrapping 32-bit version
without the original parent's lifetime cannot reconstruct that relationship.
The native reparent-before-exec control must exercise this case, not just win a
favorable scheduling race.

For otherwise unresolved processes, an actual Mach token decoded with libbsm
can establish a **different, assigned kernel audit session** from the controller.
This excludes unrelated OS services without guessing from PID 1 or missing
markers. Matching or unassigned sessions confer **no ownership or nonownership**.
This is a controlled-inheritance contract: ordinary fork/exec retains its audit
session. Work that deliberately creates/joins another audit session, or is
delegated to an OS service, requires a separate explicit lifecycle owner. This
adapter does not authorize unaccounted session-changing tools.

Receipts retain the real bootstrap argv separately from the resolved requested
command, gate release, direct bound identity, and each ownership proof. No opaque
token bytes or arbitrary process arguments/environment are collected by discovery.
Foreign-session observations confer no signaling authority; receipts record the
reason and process lifetime, not raw session IDs.

## Fail-closed limitations

This is **not kernel containment** of arbitrary or malicious workloads. macOS
does not support kqueue `NOTE_TRACK` recursive fork tracking. A short-lived
intermediate can fork and exit between censuses. Some tools close nonstandard
descriptors when spawning. If the descendant's environment is hidden, its pipe
capability is lost, and its non-reaper lineage was not observed, that missing
provenance cannot be invented. Such a same-audit-session live process is retained
as **unclassified**, is not signaled without proof, and blocks successful cleanup.
Only a later positive ownership/nonownership observation or verified end of that
exact lifetime can reconcile it. A missing census row alone is not exit evidence.

History is limited to 65,536 observed lifetimes; ancestry walks to 256 links,
descriptor censuses to 65,536 entries, and inherited pipe bindings to 32 domains.
Exhaustion, identity collisions, cycles, unresolved access failures or leaked
Mach rights fail validation rather than broaden authority. Work delegated to an
unrelated OS service remains outside the process tree: simulator/device ownership
still needs its explicit, separately verified lifecycle finalizer.

An infrastructure-failed receipt is never changed into a pass after later cleanup.
Retain it and use fresh source-bound admission before resuming heavy work.

## Required verification

[Executor controls](../../scripts/tests/run-audit-command-test.py) cover system
shells/utilities, TERM resistance, actual reparent-before-exec, early leader exit,
pre-exec refusal, cancellation and stdout/stderr EOF, same-executable unrelated
sentinels, stale tokens/PID reuse, and an intentionally unobserved real intermediate
whose optional pipe markers are deliberately closed. Scripted controls cover
missing/cyclic/reused/traced ancestry, reaper nonownership refusal even when
original-parent versions match, pipe identity/FD reuse, foreign/unassigned audit
sessions, bounds, malformed bindings, and observation failures.

Native records distinguish genuine hidden-environment execution from hosts which
expose the inherited markers; neither path fabricates SIP evidence. Passing these
controls authorizes no product, supported-Intel, device, security or capacity claim.
Native requalification of this change is required before further Mac product work.

## Explicit lab audit-session isolation

The feature-only Apple runner may opt into
[`with-darwin-audit-session.py`](../../scripts/with-darwin-audit-session.py)
**before** creating any ownership scope. A shared/unassigned runner login session
is not a private ownership domain: new launchd-reparented processes can have no
observable non-reaper ancestry and no distinguishable audit session. Increasing
timeouts or accepting missing markers cannot resolve that ambiguity safely.

The small bootstrap uses existing noninteractive administrator authorization only
to call `setaudit_addr(AU_ASSIGN_ASID)` for **itself**. It preserves every other
audit field, including masks, user ID, terminal and session flags, verifies that
preservation while the masks remain observable, then permanently restores the
invoking account's groups and real/effective/saved user identity. It verifies that
root cannot be regained. No ownership observer, product, compiler, census, signal,
or evidence writer executes with setup privilege. It does not change host audit
policy, SIP, authentication, login sessions belonging to others, or file ACLs.

Only an explicit allowlist of non-secret execution environment fields crosses
this boundary; Python site hooks and caller module paths are excluded during
setup. The returned private-session record is **not** native admission. All
original fixtures, unobservable-same-session negative controls, opaque-token
checks and finalizers still run unchanged as the ordinary user. Work that changes
sessions or delegates to OS services still needs explicit lifecycle ownership.
An unavailable setup privilege or failed policy/credential check blocks this
configuration rather than falling back to a privileged observer.

This is a test-environment isolation alternative, not an expansion of production
process or RPC admission. The exact Apple ARM/Intel matrix and dedicated cleanup
gates require their own successful execution; a local bootstrap probe cannot
establish those results.

Recovery fixtures separate native process finalization from evidence/disposal
attempts. After a scope is positively drained, its discovery errors are empty,
its required output capture completes and its capabilities close successfully,
a later disposal attempt can reference that same finalized instance and unchanged
launch ledger. It must not reuse a closed adapter to invent a new census. Failed
or incomplete finalizations are never cached, and independent whole-chain
retention obligations still block disposal until their explicit recovery proof.
