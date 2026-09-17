# Independent-peer terminal capture

This is **coordinator tooling**, not an independently implemented protocol peer,
a repair of a demonstrated P2pKit runtime defect, or interoperability acceptance.
The [independent interoperability handbook](../validation/secure-v2-interoperability.md)
still defines the matrix and the independence boundary. The existing repository
goldens and mixed-profile repair are not replaced.

## Purpose and separation

The separately authored peer exposes `TerminalDiagnostics()` and
`run(input_fd, output_fd, lifetime_seconds, diagnostics=holder)`. Its normal
launcher does not collect the holder. Repointing an old launcher to newer peer
source therefore does not retain diagnostics. The coordinator must opt in and
export the detached snapshot after that **same call**, including nonzero returns
and escaping exceptions. No protocol logic or peer source change is necessary.

[`independent_peer_capture.py`](../../scripts/independent_peer_capture.py) is an
import-safe, standard-library helper. It does not import a peer, start a process,
create a socket, acquire a dependency, or provide a standalone execution command.
The separately reviewed, candidate-bound launcher and JVM parent remain required.
Do not send primary implementation code, plans, counterpart bytes or failure
observations to the source-isolated peer author/reviewer. A coordinator reviewer
may inspect both sides; that is not independent-human or organizational certification.

## One call; unchanged outcome

`invoke_with_capture(run, holder, input_fd, output_fd, sink)` invokes the existing
callable once with the same borrowed descriptors and the maintained **120-second**
peer lifetime. It exports `holder.snapshot` in `finally` and closes only its own
directory descriptor. Diagnostic-only snapshot/export/close errors do not replace
the original return, exception object or control exception, retry the peer, add
stdout/stderr, or close/redirect/change the blocking mode of borrowed stdio.

An unhandled original exception can still produce interpreter stderr and fail the
existing empty-stderr oracle. Do not suppress it to make a run pass. Pre-run
admission refusal is a separate HOLD, not an executed peer result. The parent's
**125-second natural /130-second hard** limits and existing start/write/rescue
bounds remain authoritative; there is no new diagnostic grace period. Native
filesystem calls are not claimed real-time cancellable.

## Separate bounded record

The fixed private filename is `peer-terminal.raw.json`; the entire UTF-8 JSON
record, including its newline, is capped at **64KiB**. The closed envelope is:

```text
schema = p2pkit-independent-peer-terminal/1
invocationId, caseId, pid, parentPid
bridgeSha256, helperSha256, peerManifestSha256
terminal
```

The launcher supplies its **actual** PID/parent PID; the parent compares them to
the actual child handle and owning JVM. Source hashes are references bound by the
outer immutable plan, not self-authentication of echoed values. `terminal` keeps
all three levels: callable state/return/final-output/stdio restoration; actor
code/flags/resource finalization; endpoint protocol/shutdown/actual drain-read
EOF/close and their separate cause lists. No exception text, keys, payloads,
addresses, dynamic class names or arbitrary metadata belongs in this schema.

Only exact built-in types and finite vocabularies are accepted. Each cause list
has at most one cause per fixed stage: **36 per level /108 total** in this pinned
schema. Unknown fields/tokens, duplicate or escaped-duplicate names, malformed
UTF-8/JSON, trailing non-whitespace, invented return codes, invalid integers and
binding drift fail closed. A changed peer schema needs reviewed admission, not
truncation or silently ignored fields.

The actor's `exitCode` is intentionally **not** equated with the callable's
`returnCode`. A returned holder must agree with the parent's actual process exit;
an escaping exception has a null return code. `unused`, `running`, `raised`, or a
missing actor/endpoint may be retained as incomplete observations, but cannot
qualify natural success. A complete, structurally valid **70 remains a failed
process**, never an allowed natural exit. Do not require all cause lists to be
empty merely to retain an otherwise valid failed observation.

## Ownership and retention

The launcher pins a newly admitted state, not an arbitrary output path.
`OwnedCapture` accepts only that state's
`work/core-tcp-interop/<invocationId>/<caseId>` directory, with private ordinary-UID
ownership, the exact owner marker, no symlink components, unchanged directory
identities and an absent target. Export uses directory-FD-relative
`O_EXCL | O_NOFOLLOW`, mode0600, with finite writes and no zero-progress retry.
Existing files are not adopted or overwritten; failed partial files are retained.
Only invocation-owned temporary fixtures may be removed after review.

The parent must collect **after a known process exit**, outside stdout/stderr
pumps, with no-follow/private-file/directory-identity checks and a bounded read.
Retain original bytes, size and SHA256 **before** decoding. Missing, malformed,
oversized or misbound capture is evidence failure, even if a prior stdout
transcript and exit0 looked good. An oversized file stays retained but cannot be
described as completely read or hashed by a bounded reader. Failure-path
collection is additive: preserve the original exit/exception/rescue/unknown
retirement facts. Later cases after quarantine are NOT_EXECUTED, not passes.

Path/identity checks are not isolation from a malicious same-UID process.
A successful readback proves retained bytes, **not** successful exporter close,
fsync, crash durability, actual remote receipt or orderly TCP EOF. For example,
a close exception after all bytes were written can leave a valid readable file.
Only the peer's actual draining read can set its EOF fact; `FIONREAD0`, protocol
CLOSE and a successful close call cannot substitute for it.

## Focused offline checks and remaining execution

```bash
python3 -I -B -S scripts/tests/independent-peer-capture-test.py -v
```

These are synthetic content/call-parity controls and small owned filesystem
fixtures. They import no peer or native library and perform no TCP, Java/Gradle,
emulator, simulator or dependency acquisition. They do not compile or execute the
separate Kotlin parent or prove native source/runtime/ownership admission.

A new private source packet may copy and update the coordinator, but must not
modify frozen prior peer/harness/evidence packets or copy old execution authority.
Bind its complete source, exact peer inventory and new attachment; obtain fresh
independent coordinator review. Only a subsequently authorized, qualified host
can compile/run it under the maintained executor with new ownership and retained
failure-path evidence. The original process failure is not retrospectively
explained by these fixtures. Runtime/file/platform matrices, formal review and
delivery remain separate acceptance work; physical-phone cells stay deferred.
