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

## Later exact-source review and local result — 2026-09-26

The source-freeze status above is historical, not the current review/result
status. Author commit `b5e4bbd0e8d1b92c8abd8f500d109b9b2f1e221f`, tree
`d64de95cc7246946e048bbbe44b6c3b457e65abd`, received independent verdict
**APPROVE_EXACT_B0_SOURCE_AND_AUTHORED_CONTROLS_ONLY**. Its four postimages were
integrated unchanged into Foundation commit
`c15b461c344c822aae4eb8109eb61d4c8e0385be` after checking their exact preimages.
The original source-review report SHA-256 is
`3acf14bc6491ddc4c5679f70a6b01225b8a1482f83692bb38189d8f2cc7732de`.

One separately reviewed, fixed, stop-on-failure local invocation executed all
**19/19 controls successfully: 12 pure DATA controls and seven AST assertions**.
It used a read-only extraction of the author commit, not the subsequent B1
worktree. No old suite, accepted reader or fixture was repeated. All child,
RETURN, wrapper and tool exit codes were zero. The unittest interval was
0.144 seconds; the complete wrapper measured 1.078 wall / 0.863 user / 0.149
system seconds. Actual UID/GID was 65534, with post-PAM CPU60, address-space
768MiB, file-size16MiB, FD128, NPROC32 and core0 limits, plus an external
wall90/kill5 bound. These are local probe limits, not native/Release budgets.
All 1,460 source hashes and 1,849 metadata rows including the extraction root
were unchanged; the original process was independently confirmed absent.

The consumed packet is
`seal-deadline19-b5e4bbd0-offline-20260926.Aga3AD`; its result-manifest SHA-256 is
`16df81977d67373d07dc0596d4ce9fd605cb917de502672d6dd9ced1642fc130`.
Independent result verdict:
**PASS_19_OF_19_LOCAL_OFFLINE_DATA_AND_AST_CONTROLS_ONLY**, report SHA-256
`d8e3148d11df9d380e385af5d4a1c0042972b670e0bc7bde3f7a684f7ed5ac30`.
Private original packets remain outside source; this note publishes no raw
logs or evidence payloads.

The maintained source-control workflow now selects this same 19-method file
with `-v -f`. That is future source-test wiring, not an execution result.
The successful source-only hosted run
[36267041395/1](https://github.com/p2pKit/P2pKit/actions/runs/36267041395)
used earlier commit `47924e7802d22ad7037c8a57c2c3ea86030f99c2` and does **not**
cover B0. Neither the local controls nor this wiring execute the actual
seal/fence/output lifecycle or supply BEFORE, K, provider, custody, native
timing, C1/C2, owner approval or hosted qualification. All obligations and
HOLDs listed above remain unchanged.
