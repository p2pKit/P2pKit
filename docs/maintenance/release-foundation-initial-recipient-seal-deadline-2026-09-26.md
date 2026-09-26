# Initial-recipient seal deadline: B0 source checkpoint

## Original source freeze: not yet independently reviewed or executed

**DORMANT / B0 SOURCE ONLY / CONTROLS AUTHORED, UNEXECUTED.** This increment is
based on `e41e7229f3bf8746ed87c4a45012cf61ae25d493`, tree
`141969fd3ccbc376d20afd1ceb55e55415555265`. It neither repeats the accepted K18
DATA run nor implements BEFORE authority, native metadata reads, complete K,
transport, workflow activation or current hosted qualification.

The independent B design verdict was **APPROVE_EXACT_PLAN_ONLY**, for external
plan-v2 SHA-256
`04354193f2110cd37e4f74ff3d42ff627e1b00c3a55b43639d613decc8198f1d`.
That verdict did not approve this implementation or authorize execution.
At this source freeze no B0 syntax check, project import or control invocation
has occurred. Independent implementation/control review and separate bounded
execution authorization remain required.

## Exact narrow change

`scripts/hosted_initial_recipient_continuity.py` adds a pure closed DATA codec.
`seal_deadline_data` accepts exactly six ordinary string keys/values and returns
the declared hash, end, clock identity and boot digest. It reads no clock, boot,
environment, file or native identity; syntactically valid substituted values
remain merely different DATA, never an authenticated original or admission.
The private encoder accepts only the previous exact hash sets or this exact
six-field set; it is not a generic string-output interface.

`scripts/run-hosted-initial-recipient-custody.py` adds fixed `seal-for-before`.
Legacy `seal` still selects the original one-hash bytes and public scope. Both
fixed entries invoke one shared seal episode, one genuinely registered closed
`_TailSeal`, and the same `_TailOutputFence`/once registry. The new closed mode
is pinned after the eight unchanged legacy binding indices, within the original
history graph. The real original seal is revalidated and values rederived at
each existing append guard and both original late checks. There is no second
seal, second append, restored owner or parallel output supervisor.

The optional mode emits these six strings in one sorted ASCII runner-file
command, at most 512 bytes:

| Field | Source/constraint |
| --- | --- |
| `initialSealSha256` | Existing genuine closed seal raw-byte SHA-256 |
| `initialSealEndNs` | **Original `frame.sealEndNs`**, canonical positive UINT64 decimal |
| `initialSealClockRole` | Original supported role |
| `initialSealClockDomain` | Exact original role-specific RAW domain |
| `initialSealClockTicksPerSecond` | Original positive INT64 frequency; POSIX 1e9, actual Windows QPC frequency |
| `initialSealBootSha256` | Original domain-separated boot digest, not raw boot ID |

The output deadline is still the original seal's narrower **`clock.work`**.
Exposing the original absolute `sealEndNs` does not enlarge SEAL's allowance.
The existing file writer retains its one write/fsync/readback/known-close,
zero-sized original output-file requirement, identity checks and failure path.
No workflow wiring is added; the new deadline mode remains dormant.

## Authored controls, not passes

`scripts/tests/hosted-initial-recipient-seal-deadline-test.py` contains **19
authored, unexecuted controls**, in two explicitly different categories:

- **12 pure DATA codec controls:** exact four-role encoding; UINT64 end and
  actual QPC frequency boundaries; malformed/overflow/aliased decimal strings;
  missing/extra/mixed keys; exact container/key/value types; lowercase hash
  grammar; role/domain/POSIX frequency; unchanged legacy hash encodings;
  refusal of arbitrary strings; valid changed DATA not being authority; and
  refusal of observation/IO during pure codec calls.
- **Seven source AST assertions:** mandatory registered original seal seam;
  original-window field derivation without replacing the output limit; mode
  graph and unchanged legacy binding indices/shared once check; same-seal
  rechecks; existing append/failure/two-late-check source; one fixed shared
  seal episode/CLI mapping; and unchanged single-file writer ordering.

The new file does not import old tests/fixtures or the custody implementation;
it parses that source as AST. It constructs neither real nor fake seals,
native/file/process owners or successful-Step/service originals. These seven
AST assertions are **not runtime execution** of seal ownership, failure,
once-only append or late checks. No output file is created by these controls.
Even a later passing invocation would qualify only its exact local DATA/source
scope, not native/provider/custody/recipient authority or scheduling.

## Obligations preserved for the next source slices

Before operative K/U, actual BEFORE still needs all of the following, with
independent exact implementation review:

1. Fixed successful seal Step/output custody and a genuine first RAW/LOCAL/
   role/frequency/boot observation. Its first actual metadata owner is capped
   **before its first read** by the original absolute end, then rebinds exact
   original seal bytes. No old TailClock or first+30/45/60 bootstrap is reused.
2. Actual fresh source/native/service acquisition and child ownership. Child
   caps must be inherited before its first context/start read; original
   `startedNs/workEndNs/finalEndNs`, start/launch argv and launch minimum remain
   bound. No expired-cleanup fallback gets a fresh45.
3. The complete bounded fresh selected `jobs.bin` Step schema, unique exact
   names/numbers, statuses and timestamp chronology against the original job
   and fresh service date. Fixed predecessors must really succeed; current
   BEFORE must be in progress, not self-attested complete. No polling/fallback.
4. Genuine capture of **all279** proposed authority files, not the old36
   convenient bindings. The pending close record lists all280 obligations and
   the other279 hashes/bytes; its own actual280th row comes only after its
   separate real writer known-close, in a registered same-call return.
5. Seven **target directories** need genuine original native pins. Multiple
   actual ledger handles may refer to a target; do not assert exactly seven
   handles/rows. The other51 required directory rows remain explicitly
   unpinned originals, then require fresh K reads. No historical DATA helper
   may fabricate or hydrate live B owner/SourceReturn objects.

Actual B/K acquisition, capture, new Recipient validation, encryption/readback,
all closes and B outputs remain strictly before original `sealEndNs`. Existing
Windows finish30 must fit or refuse before launch. P0 schema4/two-file bytes,
old producer clocks, both ordinary HOLDs, exact selectors, credential
boundaries and original deadlines remain unchanged. Windows900s/576MiB and
unadmitted bootstrap5400s remain unchanged. C1/C2, owner/environment approval,
formal PR/release acceptance and physical work are not supplied by this source.
