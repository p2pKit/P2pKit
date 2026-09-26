# Release Foundation: historical seal DATA decoder

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
