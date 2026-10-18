# Foundation → Windows: supervisor implementation takeover

## Git delivery and ownership transfer

This handoff is added to the Windows agent's branch at the owner's explicit request.
It supersedes Foundation's earlier statement that Foundation would finish the supervisor.
Foundation implementation is paused; Windows now owns completing this increment.

The delivery commit adds documentation and **inert `.txt` source snapshots only**.
It does not install the draft into `scripts/`, wire it into CI, or qualify it.
It is based on Windows commit `2a0ed93001672404016123c33a53878be12437db`.
The Windows agent should fetch the branch, preserve local changes, and reconcile
this additive handoff without a hard reset or force push. If clean and still at
that base, a normal fast-forward is sufficient. If local commits exist, merge
normally and preserve them.

### Included draft inputs

| Intended maintained path | Inert draft snapshot |
| --- | --- |
| `scripts/run-windows-installed-diagnostic.ps1` | [PowerShell observer](drafts/run-windows-installed-diagnostic.ps1.txt) |
| `scripts/run-windows-installed-diagnostic.py` | [Python supervisor](drafts/run-windows-installed-diagnostic.py.txt) |
| `scripts/tests/run-windows-installed-diagnostic-test.py` | [Focused controls](drafts/run-windows-installed-diagnostic-test.py.txt) |

- [Reviewed design](SUPERVISOR-PLAN-v2.md)
- [Design review](SUPERVISOR-PLAN-v2-INDEPENDENT-REVIEW.json)
- [Python source-only review](SUPERVISOR-PYTHON-INDEPENDENT-REVIEW.json)
- [Delivered-file checksums](SHA256SUMS)

The Python review's paths identify the intended maintained paths, not the inert
snapshot filenames. Its byte hashes still match exactly. None of its 13 offline
methods or three Windows fixture cases has been executed for this draft.
The PowerShell observer still requires the corrections listed below.

Once this handoff is consumed, the draft documentation is not a second maintained
supervisor. Integrate the reviewed implementation into the canonical script paths
and remove obsolete draft copies in a subsequent coordinated change, retaining Git history.

The owner has asked Foundation to stop implementation and hand this work to you. Foundation and its two subagents have stopped; their worktrees are preserved. Please complete the supervisor and Windows work in your isolated branch, then return a reviewed, tested, pushed checkpoint. Foundation resumes integration after your handoff. This is not permission to merge main, tag, sign or publish.

## Exact starting state

- Foundation draft worktree: `/root/projects/p2pkit/windows-installed-supervisor-20261018.r94SUG2Y/source`
- Local branch: `work/windows-installed-supervisor-20261018-r94SUG2Y`
- Committed base: `33d524e311c3a67b9447d4617d141e73b3d3ac5d`
- Base tree: `04ad542a1963f82c2f8a8396d93907c3f13416b7`
- The three supplied script files are **uncommitted WIP**, not a pushed supervisor commit. Preserve the existing 33d installation and your later parsing repair; do not reset or overwrite your branch. Import/reconcile only these files into an isolated worktree/branch based on your current committed work.
- No local controls, Windows native controls, or installed invocation have run for this supervisor draft. Python source and its 13 offline test methods were independently approved FOR execution; this is not passing test evidence. PowerShell remains under repair/review.
- The supplied plan is design guidance, not execution evidence. No CI diagnostic route has yet been added.

## Required work

1. Finish/review the fixed-purpose outer supervisor using canonical `audit_processes.WindowsScope` and existing `ci_evidence.run_command`. Do not create a second PID-based supervisor or change the maintained native account policy.
2. Complete the PowerShell external observer. Known pending review items:
   - Prefer `.NET Process.Start` with `UseShellExecute=false` and its retained original process handle, plus bounded stdout/stderr stream tasks. The current `Start-Process` draft is not an approved original-handle implementation; do not call it qualified. Inspected PowerShell 7.5.2 internally opens by PID while the original process is pinned, so no PID-reuse race was demonstrated, but that does not satisfy the stated original-handle contract by itself.
   - Strictly validate JSON field types, exact source/counters and success predicates; current coercive PowerShell comparisons need correction.
   - Verify actual process exit, completed/closed bounded captures, and original-handle closure. Faulted or unfinished tasks, uncertain cleanup, or late exit must fail. No unbounded Wait/ReadToEnd or name/PID kill fallback.
3. Keep one QPC 30,000 ms acceptance deadline beginning before helper creation. The proposed fatal self-TerminateProcess watchdog fires at original start+29 seconds to reserve termination/observation time, remains armed through process exit, and does not append another work allowance. Late execution is never PASS. Failure-only retirement time is not acceptance time. Preserve actual launcher relaunch/descendants: do not change PATH to avoid them.
4. Run the 13 focused offline controls; add/execute reviewed actual Windows controls through the external observer for normal nested descendants, nonzero/output refusal, blocked inner worker, blocked outer observation, and cleanup/final exit. The supplied three native fixture choices are harmless controls, NOT installed-app tests. Observe owned original process objects; do not infer death only from PID disappearance. Preserve failed results and review repairs before rerunning affected cases.
5. After the complete supervisor passes independent review and actual Windows controls, run the installed diagnostic under your already-admitted Standard-user environment using the verified existing MSI. The helper fixes the executable to `Program Files/P2pKit Sample/P2pKit Sample.exe` and the sole argument `--rpc-windows-installed-admission`. No arbitrary launcher/command option is intended.
6. Continue the applicable installed/profile tests after their prerequisites are genuinely met. Admission success is NOT W01–W11, productive Host/Client, profile durability, or release qualification. Surface remaining implementation blockers rather than claiming a diagnostic proves them.
7. Commit logical changes, push your non-protected branch, and post a handoff on PR #470 containing exact branch/commit/tree, reviewed diff, tests/receipts, actual command and unresolved blockers. Do not force-push shared history or modify Foundation's paused worktree. GitHub Actions can be handled separately; no new exclusive window, C1 protocol or complete rebuild is required solely to test this supervisor.

## Command shape — NOT YET APPROVED TO EXECUTE

After fixing, reviewing and qualifying the observer, its current interface is:

```powershell
& '<reviewed-checkout>\scripts\run-windows-installed-diagnostic.ps1' -ExpectedSource '33d524e311c3a67b9447d4617d141e73b3d3ac5d' -PrivateParent '<already-admitted-private-NTFS-directory>' -Python '<admitted-64-bit-python.exe>'
```

These are descriptive path placeholders, not fabricated paths. Supply the actual admitted paths in your final working command. The existing installed app remains source 33d; the newly committed supervisor has its own different source identity. Bind both explicitly. The script does not itself grant installation/account authority.

## Existing installation to preserve

- Windows package run `39083768201/1`, desktop-windows PASS.
- Installed MSI SHA-256: `1ca2db89c33cefb908ec8a99ee7d81a40e369aeae3f4a4795e3300b9a8d1f089`.
- Installed application source: `33d524e311c3a67b9447d4617d141e73b3d3ac5d`.
- Your already initialized Standard-user session, tools and verified installation should be reused where still valid. Do not reinstall or rebuild merely because supervisor source changes.
- Preserve your bounded SID parsing repair and the deliberate native-contract/harness account-policy distinction.
- No keys, credentials, decrypted logs, machine/account identifiers or private payloads are included in this bundle. Keep raw execution evidence private; report only scoped sanitized results and hashes.

## Review status and limitations

The included Python source-only review is bound to the two exact files in its `files` map. Any change invalidates that reviewed-byte claim and needs a focused review of the change. PowerShell and complete native execution remain unverified. Trusted CPython/runtime/OS progress is an explicit assumption; no arbitrary scheduler/kernel-stall hard real-time guarantee is claimed.
