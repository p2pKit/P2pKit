# Release Foundation: historical seal DATA decoder

The original source/model freeze below is preserved as dated evidence. The
[contemporary review and execution addendum](#contemporary-review-and-execution-addendum)
records the later, separately authorized result; it grants no runtime authority.

## Original source/model freeze — before review and execution

**Source/model implementation review pending; authored controls unexecuted.**
This narrow dormant increment starts from
`fc9264dba3aaf46c8613ef132eab8908d4cfe97b` (tree
`cf09c391663e8aa2d02a4f1cf2115c1b3dd26c62`). It adds one pure decoder and a new
data-only control file. It adds no CLI, workflow caller, uploader, provider,
clock/owner capability, productive bridge or execution authorization.

## Why a separate historical decoder is necessary

The existing `_tail_seal_record` validates the original seal invocation through
its live `_TailInput` registry and known-closed input owner. A later Step cannot
reconstruct that object or registry to validate historical bytes. New
`_historical_seal_record` instead accepts the exact ten prior historical inputs,
seal bytes and a supplied successful Step outcome/hash, returning ordinary DATA.
Its caller must separately authenticate actual outcomes, acquire current
authority, open fresh owned readers and bind genuine clocks/deadlines.

The decoder preserves the old producers, parsers, clocks, registries, CLI and
pending source records. It binds the seal's predecessor, primary, source, job,
policy, original window and manifest to the prior bytes using canonical byte
equality, including boolean/integer distinctions. It reuses the pure inline
authority parser and additionally binds expected/fresh/original match, event
and candidate-policy hashes to the actual supplied inputs.

Collect `lastNs` must not follow seal FIRST; the historical seal cap remains exactly
`min(FIRST + 30s, original sealEndNs)`, with equal authority work/final caps,
ordered closes, strict final-end exclusion and the historical LOCAL floor.
Supplied Step success never rewrites `PENDING_OWNER_CLOSE`, `NOT_OBSERVED`,
`NOT_PERFORMED`, false productive/cache/export-save authority or `NOT_ADMITTED`.

Historical metadata-close rows remain DATA, not a live owner return. A Windows
output-directory pin must match its original context pin. POSIX's original
context pin remains `None`: the seal-observed pin is not promoted into a missing
historical pin. Its declared file-metadata hash still needs a new owned file
read before future upload; neither that hash nor this decoder proves present
bytes, file identity, upload, retention or decryption.

## Focused controls: authored, not run

`scripts/tests/hosted-initial-recipient-sealed-data-test.py` authors **15 test
methods**, including gate/worker and Linux/Windows historical role data with
both original cap branches. Negative controls cover exact supplied outcome/hash,
closed fields/rosters/canonical encoding/limits; independently rehashed
source/job/policy/predecessor/manifest and authority substitutions; strict time
and LOCAL boundaries; pending flags; historical close rows; and output pin/
artifact scope. Embedded boolean/integer alias controls use canonical binding.

The fixture constructs only small in-memory grammar and byte strings. Its
match/event/policy/key-shaped inputs are explicitly inert synthetic DATA, not a
current recipient or original evidence. No old fixture/test suite or complete
seal/native composition is imported or replayed, no file tree is created, and
no actual hosted environment is installed. The control audit hook refuses
process/network/native loading and environment mutation, plus file-open and
directory-enumeration audit events during guarded decoder calls. A dedicated
control denies live owner/clock/host calls
and verifies registries/attempts remain unchanged. These controls still require
independent implementation review before any separately authorized execution.

No Python parser, syntax/import check or test was executed for this increment.
Only bounded source/Git inspection, hashes and `git diff --check` were used.
Earlier exact seal results retain only their [recorded scope and failed/pass
accounting](release-foundation-initial-recipient-seal-2026-09-26.md); they do not
qualify this new source, and no accepted reader or old suite was replayed.

## Contemporary review and execution addendum

On 2026-09-26, independent implementation review first returned **REVISE** for
frozen tree `0dfa75c347bbbf61c56f6566987d0e8a21b58031`: the reused inline authority
parser's equality could accept an equal float for nested `authority.closedNs`.
The new decoder now requires that field to be an integer, with independently
rehashed float/boolean negative controls. The old parser, producers and accepted
controls were not changed or replayed. Independent review then approved the
exact source/model at commit `5ccc1ab5ac81f9b924f490d869fec46a6af227b1`, tree
`19b320e08bdc34c7f73daafc088f0a514a4c4c28`.

After separate review and launch authorization, **one invocation of the 15 new
DATA-only methods passed: 15/15, aggregate OK, Python/child/wrapper exits 0**.
It ran from `2026-09-26T11:51:38.025402321Z` to
`2026-09-26T11:51:39.484984300Z`; unittest reported 0.154s, the wrapper 1.456s,
and the actual Python process's terminal self CPU was 1.334442s. There was no
rerun and no ResourceWarning, traceback or failure in the original log.

The fresh read-only archive used the approved commit. The real process ran as
UID/GID 65534 with a clean environment; `prlimit` was applied **after**
runuser/PAM and the final environment, immediately before
`python3 -I -B -S -W error::ResourceWarning`. A same-process guard verified
actual UID/GID, `getrlimit`, original `/proc/self/limits` and eight focused source
hashes before importing the model. Limits were CPU 60s, wall 90s plus kill 5s,
address space 768MiB, output file 16MiB, 128 FDs, 32 processes and zero core.
The guard selected exactly the 15 reviewed methods, fail-fast. ENTRY/RETURN
retained the same actual PID 17924; it was absent after normal return. All
source-byte, metadata and guard comparisons passed: 1,456 source-file rows and
1,845 metadata rows were unchanged. Fresh HOME/TMP remained actually empty,
with a zero-byte fixture inventory.

Independent result review read the complete originals, verified their hashes,
method count/aggregate/exits, real process limits and timing, compared the
retained archive inventories with the current frozen sandbox, and directly
rechecked empty HOME/TMP and PID absence. Its verdict was **PASS as local DATA
models only**, not native, hosted, provider, custody or integration acceptance.
The following SHA-256 values identify the exact reviewed scope and originals:

| Item | SHA-256 |
| --- | --- |
| Decoder source at `5ccc1ab5` | `4925a0e54b2275e045dc16366e94c50e0dc235d7ed7186dba1da38c2ece9b4be` |
| New 15-method control file | `5d246e4737678cb02edb768fc57c1bbac4fb2567c5e92dbc646d7072cf9d17a1` |
| Full original control log | `3e32059e48b3475c3e400ea2d94fb01e184b450cf8c68964c7cedb0cc1c5ca6b` |
| Original wrapper resources | `0e61035824e46ca8e72c3e138ff1860ad58614c9a022e06408458efc7f291fee` |
| Original invocation status | `3b50eef895cdb842355ab407e69f7e83953964436541f55daa8c790a1572e8ac` |
| Author's result inspection | `64d6f50fe1c9a5be093a90e18e050b5494018ad1e6313db96db19570298900e0` |

This is a documentation-only result update; runtime/model source is unchanged.
It authenticates neither a supplied Step outcome nor historical host-looking
DATA and mints no live owner, clock, provider/upload permission or productive
bridge. No accepted reader, old suite or full native/seal composition was rerun.

## Remaining endpoint and execution HOLDs

Fresh upload-before ownership/readback, genuine provider Action start and exact
uploaded-byte ownership, absolute upload deadline, actual Step/service receipt
linkage, finite private evidence custody and the separate typed productive
bridge remain unresolved. Public artifact digest is not inner ciphertext SHA.
There is no extra upload budget after the original 60s upload and 15s AFTER;
gate AFTER ends at its original 360s job ceiling. Worker slack cannot renew its
window. A packet cannot contain its own subsequent close/upload observations.

Both ordinary activation HOLDs and the whole-JVM interlock remain. Bootstrap
5400s is unadmitted/unmeasured; Windows native-file 900s and Snapshot 576MiB
remain unchanged and do not accommodate a 2GiB Snapshot. Configuration-only
`help` cannot satisfy ordinary FULL, ABI, simulator or transcript acceptance.
No genuine native/provider/custody/delivery/scheduling qualification, hosted
dispatch, local build/download, publication or issue acceptance follows.
