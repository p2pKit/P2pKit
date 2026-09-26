# Initial-recipient BEFORE authority: B1 source checkpoints

## F1/F2 successor: original pre-review source checkpoint

**UNREVIEWED SUCCESSOR / DORMANT / 60 AUTHORED CONTROLS, NONE EXECUTED.**
This narrow successor preserves the original B1 commit
`36ff2b11b84fcbff140852162227beae0c7afb0b`, tree
`728cd04140f7b1740a980eb708df0d2993dabe6a`, unchanged in ancestry. Its independent
285-line review, SHA-256
`a07afa491f6af10bb7bab7c17a4073555bf64dd18de5c1549c5f6c4409744696`, gave
**REQUEST_CHANGES_EXACT_B1_SOURCE_NO_EXECUTION_OR_K_APPROVAL**. That report
positively described the bounded real protocol/roster while requiring two
corrections; it did not approve B1 or supply a test/native/hosted result.

The report's F1 was a concrete disconnected entry-failure latch: duplicate
entry or swallowed callback reentry could fail the outer entry while the
clock/acquired/authority chain still accepted its separate authority attempt.
F2 was an unsupported Windows cross-lifetime metadata equality, **not an
observed Windows failure**. The maintained writable-file backend does not
promise that a pre-close `verify()` stamp's last-write/change times equal
those observed after the writing handle really closes.

### Original entry lineage and the public return boundary

The B helper now also supplies the small production `EntryLatch`, an actual
**in-memory state machine**, not a pure DATA codec, native owner or B capability.
C creates one original instance bound to its original attempt registry. Its
private immutable state tuples pin the original visible entry dictionary,
STARTED/RETURNED transition, exact result identity and first exception. There
is no reset. Restoring visible dictionary fields after refusal cannot revive
it; changing/removing/replacing the original entry or registry also refuses.

The same original `(latch, attempt)` tuple is appended to the actual parent
clock binding and independently retained in the acquisition and authority
registries. Parent clock checks consult it before other current-state work,
including the existing immediate check after the cancellation callback. The
acquisition's retained closure, acquired checker, currency path and both
authority checks also bind it. Failure propagates back into that original
latch, including a duplicate after successful return and a late outer failure.
The actual original owner/anchor references remain pinned before currency
callbacks, and existing cleanup/UNKNOWN paths are not replaced or bypassed.

Only the private `_checked_before_authority` may inspect a pending internal
closed result while the outer entry is STARTED. The public
`checked_before_authority` requires original entry completion and its exact
result identity both before and after its structural checks. Completion is
recorded only after the real closed-result path returns. Any subsequent outer
failure invalidates the same latch and therefore that registered result.
This remains a passive check, not a K continuation or upload permission.

The child must still have `entry=None`; no latch, attempt or parent registry
handle is passed in context, argv or JSON. Its authority continues to come
from its actual native launch and original inherited cap/identity checks.
No new clock, observation, allowance or cleanup reservation is introduced.

### Distinct close-writer observations, finite Windows policy

The new B close writer retains separately:

- `preCloseWrite`: the actual `_consume` writer-verify metadata taken **before**
  its original close, exact bytes/hash, original writer ordinal and the later
  real known-writer-close result;
- `readback`: the separate actual post-close reader's complete metadata,
  bytes/hash/EOF and known-reader-close observation, unchanged in provenance.

Both observations are retained in full and pinned by the returned graph; the
writer/reader owner-close records remain actual. The post-close reader still
requires full metadata equality for its whole own lifetime. Both backends,
old readers, `_consume`, and all original authority/readback paths are unchanged.

Only this new B writer's cross-lifetime DATA comparison may permit Windows
`modified_100ns` and `change_100ns` to differ. Each remains a strict nonnegative
UINT64. There is no invented timestamp, direction/monotonicity claim or time
credit. Windows identity, kind, exact size, links, attributes, creation time,
owner SID and protected DACL must all remain equal, with the real native
privacy/stream checks unchanged. POSIX retains full metadata equality,
including mtime/ctime. Missing/extra fields and numeric aliases refuse. The
same actual bytes/hash/EOF and writer/reader known-close obligations still
hold. This policy is not genuine Windows lifetime qualification.

### Authored successor controls, not a pass

The file now has **60 unexecuted methods:35 DATA +11 in-memory latch +14 AST**.
The original37 methods remain, with one AST check following the renamed
private structural checker. The23 additional methods comprise seven supplied
metadata controls, eleven direct controls of the real small latch used by C,
and five source-wiring assertions. No parallel latch model, fake B/native
owner or synthetic original registry entry is used to stand in for C.

The latch controls cover post-return duplication, a caught recursive begin
followed by the same post-callback check, first-error preservation, late
failure, dictionary/registry substitution and attempted visible restoration,
foreign/unregistered latch use, exact result identity and rejected pending,
duplicate or reinitialized completion. Metadata controls cover both full
observations, only the two Windows time differences, strict typed fields,
stable privacy/identity/content-size data and unchanged POSIX equality. AST
controls trace the single production latch through clock/callback/acquired/
public-result boundaries and both actual writer/reader observation paths.

These are **authored, not syntax-checked, imported, AST-parsed or executed**.
No B1, B0/B019, K18/D15, old seal/reader suite or native fixture was run. Any
later exact offline packet needs independent implementation/control review
and separate root authorization. Native cancellation/ownership/retirement,
token transport, Windows lifetime, provider, timing and scheduling remain
unqualified. This successor adds no K, Recipient, workflow, Release or held
execution authority; all original limits and HOLDs below remain unchanged.

## Original B1 source freeze: historical pre-review, unexecuted

**UNREVIEWED / DORMANT / 37 AUTHORED CONTROLS, NONE EXECUTED.** This source
increment starts at `b5e4bbd0e8d1b92c8abd8f500d109b9b2f1e221f`, tree
`d64de95cc7246946e048bbbe44b6c3b457e65abd`. There has been no B1 syntax check,
project import, AST parse, test invocation, native episode or hosted execution.
Only source/Git inspection and whitespace checks precede this freeze.

The governing B plan-v2 has SHA-256
`04354193f2110cd37e4f74ff3d42ff627e1b00c3a55b43639d613decc8198f1d` and independent
verdict **APPROVE_EXACT_PLAN_ONLY**. K plan-v4 has SHA-256
`6b2466ae30472cde7ed039c1d2cd0f7958cfbabe4358fe21cd795f537d7833fc`.
Neither plan approval nor the separate B0/K18/D15 results approves these new
implementation bytes. None of those accepted controls or old seal/reader
fixtures was rerun or added to B1's authored count.

This increment adds the intended actual BEFORE acquisition/owned-readback
protocol, not a fake B record for K. Independent review of its whole protocol
and all279-plus-close obligations is required before building K upon it.
The private child route exists; **there is no public parent BEFORE CLI, output
append, workflow caller, Recipient validation, K export or upload success**.

## Fixed source seams and immutable first-read ceiling

`scripts/hosted_initial_recipient_before.py` contains pure DATA codecs for the
six B0 deadline strings, inherited phase tuple, exact Step grammar and member
declarations. It obtains no clock, boot, native identity, file or HTTP response.
Typed DATA, including a valid substituted clock/boot, is never authority.

The dormant internal `before_authority` in the custody driver uses a new
one-shot `_BeforeClock`. The outer metadata/acquisition helper removes the
read token from its environment and observes actual FIRST LOCAL/RAW, supported
role/domain/frequency and boot before any file owner. The B0 six-field seed
must match that actual identity and supply an absolute original `sealEndNs`
strictly after FIRST. One directed LOCAL work/final pair is derived from this
FIRST pair and the existing absolute end. There is no FIRST+30/45/60 bootstrap,
old TailClock restoration, service-Date RAW credit or proposed5400s budget.

The first actual `_PrimaryOwner` reads only `seal/seal-pending.json` initially.
Its already-enforced ceiling is rebound to that exact hash/window through a
known-closed reader, not granted retrospectively. The remaining ten unchanged
`_tail_records` inputs are then read: the prior export Step/carrier/context,
P0 manifest, original/fresh matches, event, candidate policy, public armor and
collect-close. All eleven originals receive a second byte/size/hash/metadata
readback before the input owner closes: exactly four directory resources and
22 reader resources. The original returned pin, genuine Windows output pin
and seal-observed output pin remain distinct. No missing producer-side POSIX
export-output pin is manufactured from a fresh observation.

Parent metadata, operative authority, readback and close-file writer owners
retain their actual dictionaries/registries/ledger rows and same original
clock. The registered acquisition keeps independent original owner/anchor
references before any token-free currency callback, so early refusal enters
the original close path rather than trusting a changed return dictionary.
Metadata-owner attachment is also inside its cleanup region. Failure remains
sticky; original close attempts may end UNKNOWN/quarantined and never become
successful through replay, new caps or changed flags.

## New genuine source/native/service episode

The fixed `authority-before/` path uses the maintained original source-query,
installed-Git, native-phase, HTTP and readback suppliers: real12-query source
before,24-query acquisition,12-query source after. Existing `SourceReturn`,
phase and native-owner return bindings remain operative, not hydrated from
historical JSON. Context/child/ACK/close scopes are distinct B-only literals.

Native phase setup derives its actual original tuple:

- `workEndNs = min(original sealEndNs, startedNs + 45s)`;
- `finalEndNs = min(original sealEndNs, workEndNs + 45s)`.

Both original start argv and actual launch argv bind this same tuple and the
six safe seed strings; launch argv additionally binds its actual launch
minimum. The child validates canonical decimals/identity/boot and inherits
these work/final caps **before its first context read**, never child FIRST+45.
Context/start metadata reread and its real six-resource close precede actual
acquisition. The child authenticates the inherited native domain and tuple
against those already-capped originals before HTTP.

The only native/primary-driver changes add the exact B command and scope to
fixed initial-service/installed-Git seams, plus B-specific enter/leave paths.
The setup-error, normal finalization and expired-cleanup paths retain the
original limits; B cannot fall back to a fresh45 cleanup allowance. Legacy
routes reject B's extra phase tuple. Old producers, old seal bytes/defaults,
other phase clocks and old32-entry directory helpers are unchanged.

The token-bearing parent helper and acquisition call return completely before
the exhaustive279-file readback and separate writer. The top `before_authority`
frame never holds the token. Child/native launch transport uses the unchanged
fixed token environment and clears its references after acquisition/failure.
No token, private key or credential is supplied to the readback/copy path.

## Exact selected service Step contract

The retained original `attempt`/`jobs` responses from actual acquisition must
select the original same service job through the maintained matcher. Complete
bounded jobs enumeration remains <=100 with exact total and no Link; it refuses
truncation, without extra HTTP, polling or an alternate response source.

The selected job must supply a nonempty list of at most256 Step objects, each
with exactly `name,status,conclusion,number,started_at,completed_at`. Names are
nonempty, control-free, unique and <=256 characters. Numbers are strictly
positive int32, unique and ascending; gaps are permitted. Unknown fields,
statuses, conclusions or alternate timestamp spellings refuse.

| Role | Exact name | Required current service state |
| --- | --- | --- |
| export | `P2pKit initial custody export` | completed/success |
| collect | `P2pKit initial post-export custody` | completed/success |
| seal | `P2pKit initial custody seal` | completed/success |
| BEFORE | `P2pKit initial before-upload custody` | in_progress, no conclusion/end |

These four rows must have ordered numbers and predecessor completion <= next
start. Required predecessors have real started/completed timestamps; BEFORE
has a real start and cannot attest its own success. All earlier rows are
completed; all later rows are queued, with no concurrent current row. Queued
rows have null times/conclusion. Completed conclusions are restricted to
success/failure/neutral/cancelled/skipped/timed_out/action_required; only a
skipped completed row may have both timestamps null. All real times use exact
second-resolution UTC `YYYY-MM-DDTHH:MM:SSZ`, between job start and service Date.
These wall-time checks do not award RAW time or satisfy later B-Step success.

This source contract was checked against existing public completed/success
Step metadata for its six-field shape, second-resolution times and gapped
numbers only. No genuine running BEFORE, queued/skipped case or B runtime was
observed. Their new control inputs are explicitly synthetic DATA. Unknown
service shapes remain a qualification blocker rather than a silent widening.

## Complete actual producer/readback obligations

The B-only declaration helper is cross-checked against actual query sessions
and original returned hashes. It is not an arbitrary caller-provided manifest.

| Subtree | Original required files | Count |
| --- | --- | --- |
| `source-before/` | owner/session/source-return, four source inputs,12 queries x five files | 67 |
| `source-after/` | independent same grammar | 67 |
| `acquisition-queries/` | owner/session,15 original inputs,24 queries x five files | 137 |
| root/service | context, child result and six original native phase files | 8 |
| root | separate `authority-close.json` | 1 |
| **Total** | **279 existing originals plus one declared close obligation** | **280** |

Every query requires actual `start.json`, `baseline.json`, `stdout.log`,
`stderr.log`, `result.json`, including owned zero-byte stream reads. The15
acquisition inputs are event, four source inputs, eight original HTTP responses,
observation and match. Query owner/start/baseline/result/stream bytes are bound
back to their genuine sessions. Existing per-file2MiB, per-session64MiB and
aggregate limits remain; smaller actual available capacity must refuse.

All58 directory memberships are checked before and after readback: authority
root/control-home/temporary/service, three session roots/query homes and48
actual distinct query directories. Only B's separate exact-cardinality helper
admits its42-entry acquisition root; other directory names and unknown extras
refuse. Native file/directory identities and case/path aliases are checked.

Original native pins come from the genuine authority ledger for exactly seven
**logical targets**, not necessarily seven handles: root, control-home,
temporary, service and the three session roots. Every actual matching handle
is retained through known-close. The other51 directory rows explicitly say
`UNPINNED_ORIGINAL_DIRECTORY`; all58 separately retain fresh `readbackIdentity`.
Fresh readback is not retroactively labeled original producer observation.

After279 actual bounded reads/EOF/metadata checks, the separate readback owner
closes, then the actual authority/query/native owner closes. Only then does a
new capped file owner write `authority-close.json`. That private record names
all280 obligations and the other279 actual byte/hash/metadata rows, original
input/readback/authority closes, current service binding and seven-target pins.
Its own row has only name, maximum and
`PENDING_SEPARATE_WRITER_READBACK_AND_CLOSE`: no self-hash, self-byte count,
self-close or enclosing-Step success. The root's only permitted addition is
this declared close file; all58 directory identities/memberships are rechecked.

Actual sync/verify/readback and original writer/reader known-close produce a
separate same-call writer return. Only that return supplies the280th actual
bytes/hash/metadata row. Reader ordinals belong to their respective original
input/readback/writer owner-close records, not one global ordinal namespace.
The registered `_BeforeAuthority` binds all280 raw originals, exact index,
separate closes and original graphs; a dataclass instance or its DATA bytes
cannot mint it. Its checker is passive and does not itself mint K authority.

## Authored controls and unresolved acceptance

`scripts/tests/hosted-initial-recipient-before-test.py` contains37 unexecuted
methods: **28 pure DATA controls** and **nine AST source-shape assertions**.
DATA covers exact original/inherited caps, first identity/boot/QPC, strict
decimal/type/shape negatives, no child renewal, complete Step grammar and
chronology, missing/extra/current-state cases, exact280/58 grammar, query IDs,
five-file completeness,42-member root and only the declared close addition.
It checks input immutability and denies native clock/boot suppliers.

AST assertions cover first-cap-before-read, twice-bound phase argv, actual
eleven-input reread path, exhaustive279/58 paths, non-self-attesting close,
original cleanup regions/authority-close-before-writer, token-frame split,
all native phase leave/expired-cleanup seams and old limits/no parent output.
The file imports only the pure B dependency chain; custody/native/primary code
is read as AST, not imported or executed. Audit guards deny process/network,
native loading and environment mutation, plus file-open/enumeration during
guarded pure calls. They do not claim universal interception of low-level IO.
Any later invocation requires `-v -f` and separate exact packet/guard review.

These assertions are **not** actual clock/registry-mutation, native ownership,
EOF/cancellation/UNKNOWN, Windows metadata-lifetime, token transport, custody,
provider, performance or scheduling tests. Those operational behaviors still
need focused genuine qualification. No current native/provider/recipient or
application acceptance follows even if all37 local controls later pass.

K still needs the remaining historical/P0 diagnostic groups, new same-process
Recipient validation, owned immutable capture/map, new closed tail manifest
and exact four-file carrier. Its original aggregate512MiB plaintext/576MiB
ciphertext/10,000-member limits include maps/duplicates/archive roots. B/K
work, closes and output must remain before original `sealEndNs`; U starts
before sealEnd and closes before uploadEnd; A retains its original15s/afterEnd.
Existing cleanup reservations must fit without a deadline extension.

P0 two-file/schema4 bytes, both ordinary activation HOLDs, the whole-JVM
interlock, exact selectors/credential boundaries, Windows900s/576MiB and the
unadmitted/unmeasured5400s proposal remain unchanged. No workflow, cache
producer/export/save/probe, formal C1/C2/owner/environment/PR approval, Release
or productive Stage2 authority is supplied. Protected instructions, RC3 and
unrelated dependency proposals remain untouched; no build/download/native/key
operation, physical-device request or held CI dispatch is authorized here.

## Later exact-source review, controls and Foundation integration

Successor `4769fcd65b6f38367783a573f5c15f08db22e6ed`, tree
`652b33ff7ae72ebf1bbac80b80cd6aaade92450f`, received independent
`ACCEPT_EXACT_B1_SUCCESSOR_SOURCE_ONLY`, report SHA-256
`eb4a41ffccd74a697a182286b43f39562a045384735354db78ed801e563d60b5`.
Foundation `1fafe274` integrates its six reviewed postimages unchanged, without
importing donor ancestry. The pre-review descriptions above remain historical.

The separately reviewed bounded offline invocation passed **60/60** methods:
**35 DATA, 11 actual in-memory EntryLatch controls and 14 AST assertions**.
The original test and wrapper exited 0. Unittest reported 0.266 seconds; the
whole wrapper measured 3.147 wall, 2.773 user and 0.299 system seconds. Those
different measurement spans are not native timing qualification. The 1,463-file
read-only snapshot remained unchanged; the private temporary fixtures were empty.
Independent result verdict: `ACCEPT_EXACT_BEFORE60_LOCAL_DATA_LATCH_AST_RESULT_ONLY`,
report SHA-256 `fd606c1ed44ae7c2e2ec95f4706e6cf56954d7d7534936a43b09c7712e33bfb1`.

The source workflow now includes these controls; that wiring is not a hosted
result. No old successful reader/seal suite was repeated in this local packet.
Real BEFORE, native/Windows lifetime, service, provider, custody, K, scheduling
and timing qualification remain outstanding. No activation HOLD is lifted.
