# Release Foundation: seal-only initial-recipient continuation

**Dormant seal-only source independently reviewed.** The exact execution
account below is **26 completed methods in a failed aggregate, plus separate
3-method and 4-method passes**, not a successful 33-method suite or hosted
qualification. The initial unexecuted WIP and its review corrections remain
preserved in Git history. This source increment starts at
`694685b9d2515995a415d70adce9190c650ac883` (tree
`55438e58ae9aa5dea1df1083f27804a7e47d42c4`). It neither repeats an accepted repair
nor completes the cache/sample delivery campaign.

## Narrow source change

The retained initial-recipient custody controller had `collect-export` and
`collect-close`, but no terminal seal command. This candidate adds only
`seal --kind gate|worker` and the fixed private `_tail-authority` child route.
It does **not** add `upload-before`, `upload-after`, an uploader, workflow
callers, provider/cache authority or a productive bootstrap bridge.

The [extraction note](release-foundation-cache-prerequisites-2026-09-26.md)
remains the historical extraction record; its original custody diagnosis is
not a claim that this new source has been accepted. The separate schema3
consumer, its tests, composition pins, Foundation workflows, source/recipient
approval constants, AGENTS.md, CLAUDE.md and published RC history are unchanged
by this increment.

### Prior Step data is not a revived capability

The new input reader binds the actual successful primary, crypto and collect
Step outcomes and their exact hashes. It reads the nine existing crypto/collect
inputs plus the actual persisted `returned/collect-close.json`, using new owned
file readers. It validates that collect record's inline authority hashes,
original schedule, chronology and known-close rows directly. There is no
persisted `authority2-return.json`, and this source does not invent one or
restore an old `Window`, collect clock, owner, Recipient or HTTP lease.

The returned-directory pin is historical. Windows also has a historical
export-output-directory pin in the crypto context. **POSIX has no historical
output-directory pin**: that context field is `None`. This candidate pins the
POSIX output directory only across this new tail's input and final owners;
its observation scope explicitly says
`THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN`.

The existing returned-directory whitelist is unchanged. Custody-root stage
rosters are fixed:

| Stage | Exact root members |
| --- | --- |
| Input | `authority-1`, `authority-2`, `copied-evidence`, `export-output`, `public-crypto`, `returned` |
| New authority | Input members plus `authority-seal` |
| Seal retained | Authority members plus `seal` |

An already present tail directory or an extra returned/root member refuses
the operation rather than enabling a retry or overwriting prior evidence.

### Fresh, bounded seal episode

The parent captures fresh FIRST RAW, LOCAL and boot observations and begins
with a 30-second metadata cap. The first fixed crypto-Step reader must be
known closed before one-shot **RAW and LOCAL narrowing**, and that narrowing
occurs before the other carrier/context/manifest/host reads. A separately
owned child starts with its own 45-second metadata cap and narrows immediately
after its first context reader closes. Neither metadata stage grants authority.

Only complete validated inputs and a known-closed metadata owner allow
operative binding. The parent seal cap is:

```text
min(parent FIRST RAW + 30 seconds, originalWindow.sealEndNs)
```

Child phases, native captures, queries, file reads/writes, closes and outputs
can only shorten that cap. The original gate six-minute / worker twenty-minute
job ceilings and full READ/SEAL/upload schedule are unchanged. An expired READ
window may not be renewed; an expired SEAL window cannot be repaired. Native
`Owner.local_end` is immutable: the effective fence narrows, and failure cleanup
uses only already captured ceilings. First failure, cancellation, identity
mutation and UNKNOWN remain terminal.

The new authority episode uses current source-before queries, the real fixed
child/native ownership API, a separate current eight-response acquisition and
source-after queries. It binds the exact old source/job/policy/approval identity
and original schedule. Serialised historical rows are not live returns. The
new token is removed from the child/parent environment; the token-bearing
parent helper returns before any seal-file/output frame runs.

### Seal and output limitations

The final new owner rereads prior bytes and streams only the fixed ciphertext
file, checking its exact manifest size/hash/EOF and two-file output roster.
This uses the existing 576MiB ciphertext bound, **not** the 512MiB plaintext
copier limit and not a Windows aggregate Snapshot. No 2GiB cohort is allocated
or treated as fitting the 576MiB Snapshot limit. Windows native-file lifetime
remains 900 seconds.

The new file is `custody/seal/seal-pending.json`. It retains the new authority
return and the old Step/manifest bindings, but deliberately says
`writerReturn=PENDING_OWNER_CLOSE` and `originalStepOutcome=NOT_OBSERVED`.
It cannot attest its own writer's or Step's eventual success. Decryption,
upload and test acceptance remain `NOT_PERFORMED`; productive/cache/save
authority is false and budget acceptance is `NOT_ADMITTED`.

Only `initialSealSha256` may reach the existing exact runner-output allowlist,
after this invocation's known closes. A one-shot output facade retains the
original two late guarded checks. Partial append, fsync/readback/close error,
late mutation or cancellation cannot make a successful Step. The post-cut
tail is **not inside the already frozen encrypted packet**; this seal does not
claim encrypted custody or delivery of its own terminal evidence. That
separate upload/tail-custody design and review remain outstanding.

## Focused model scope

`scripts/tests/hosted-initial-recipient-seal-test.py` adds focused controls for
the new grammar and complete seal-only composition. It imports the existing
lower-boundary fixture module, **not** earlier test suites, and does not execute
old collect/crypto producers or register old successful live returns. The
historical collect-close record is explicitly supplied DATA. The ciphertext
fixture is the tiny string `XYZ`, not real encryption or original evidence.

The authored controls cover exact hashes/outcomes/rosters; old-vs-new capability
separation; first-sample and original deadline floors/caps; early dual-clock
narrowing; RAW/LOCAL/boot mutation and reentry; fresh source/acquisition/HTTP
composition; token separation; wrong owner/source/job/policy; original return
substitution; setup, query and native UNKNOWN failures; ciphertext hash/size,
extra members, symlinks and fresh-directory replacement; pending seal scope;
writer/close failure; one digest append; and both late output checks. Two native
UNKNOWN models explicitly dispose only their tiny fixture streams after all
refusal assertions, without calling candidate close methods or repairing any
candidate ledger/UNKNOWN flag.

All host-shaped mappings stay inside supplier-module namespaces, never the
real process environment. The fixture audit hook forbids process, socket and
native-library execution. Any future authorised run must use a frozen exact
source archive as an actual nonroot user, not a patched UID. These
synthetic controls cannot qualify genuine native retirement, hosted identity,
provider/resolver/custody, encryption, timing, scheduling or uploaded artifacts.
No parser, syntax/import check or model had run at the initial WIP freeze.
Subsequent exact-source execution is recorded separately below.

## September 26 implementation review and executed evidence

The first implementation freeze was
`4862b463b62fae7348e9aceed09a85f8135ebe2d`. Independent implementation/model
review returned **REVISE before execution**: tighten only the new historical
phase chronology, correct the synthetic historical positives, restore mutated
clock inputs in sticky-failure controls, separate narrowing/binding reuse
controls, and correct the contemporary owner-authorization note. No original
producer, clock, deadline or accepted fixture was changed by those corrections.

The independently approved runtime/model successor is:

```text
commit eba5c28422fe7069efc2b0e86513107fbc5fa50b
tree   8c902138090dc440f8b3c03e59b790f9a61cba85
```

The verdict was **SOURCE + NEW MODEL SOURCE APPROVED**, not native, provider,
custody, delivery, timing or activation approval. Its new suite has 33 methods;
the existing fixture remains unchanged. Every execution below used an exact
fresh archive of that commit, not this later documentation update.

| Original attempt | Exact observed result | Scope |
| --- | --- | --- |
| Initial outer wrapper | Exit 127 before `runuser`, Python or any method: `/usr/bin/time` was absent | **PRE_TEST_INFRASTRUCTURE_FAILURE**, zero methods |
| Separately authorized Bash-timer correction, full new suite | Exit 124 at the external 90-second wall cutoff; wrapper returned after 92.010 seconds, within its five-second termination tail | **FAILED / INCOMPLETE**: 26 methods logged `ok`, the 27th started without a result, six did not start; no aggregate `OK` |
| Separately authorized remaining group A | Three exact methods, `OK`, original Python and outer monitor exit 0 | **3/3 PASS**, effective limits verified in the actual process |
| Separately authorized remaining group B | Four exact methods, `OK`, original Python and outer monitor exit 0 | **4/4 PASS**, effective limits verified in the actual process |

The failed full-suite wrapper placed `prlimit` **before** `runuser`/PAM.
Retained post-cutoff process observations showed CPU, address-space and
file-size limits reset to unlimited, with different descriptor/process limits.
Its shell-reported CPU counters therefore do not establish the candidate
child's CPU use or effective resource compliance. The original 127 and 124
packets remain preserved; neither was converted into a pass or attributed to a
production deadline/assertion failure. Log position alone did not prove a hang.

No candidate source was changed or optimized after the cutoff. The 26 completed
methods were not replayed. A separately reviewed, root-authorized correction
put `prlimit` **after** `runuser`/PAM and the final clean environment, immediately
before the actual Python process. The new guard checked real UID/GID 65534,
same-process `getrlimit` and original `/proc/self/limits` before importing the
fixture, then retained the same PID, effective limits and `getrusage` at return.
Genuine timing/CPU suppliers were captured before the fixture's model clock
installation. The guard selected only these remaining methods:

| Group | Exact `SealAndOutputControls` methods |
| --- | --- |
| A | `test_output_early_wrong_limit_equal_binding_or_expiry_cannot_recover`; `test_output_pin_is_new_tail_observation_not_phantom_posix_history`; `test_output_whitelist_does_not_admit_future_upload_or_paths` |
| B | `test_partial_append_fsync_readback_or_ambiguous_close_never_success`; `test_seal_files_cannot_attest_their_own_close_or_mint_registered_result`; `test_second_late_currency_callback_cannot_replace_seal_dictionary`; `test_writer_and_close_errors_cannot_issue_seal_digest` |

Each group ran once, serially, fail-fast, as actual `nobody`, with `-I -B -S`,
`-W error::ResourceWarning`, `-v -f`, a clean environment and the reviewed fixture
hook prohibiting subprocess, socket and native-library activity. Each retained
the original CPU **60 seconds**, wall **90 seconds** plus five-second termination
tail, address-space **768MiB**, single-file **16MiB**, descriptor **128** and
process **32** limits. These are local model-run safety limits, not new hosted
or production budgets. No earlier test suite or accepted reader-control suite
was rerun; existing production callees used by the new seal composition did
execute.

| Successful group | Unittest elapsed | Full wrapper elapsed | Same-process terminal user + system CPU |
| --- | --- | --- | --- |
| A | 25.931 seconds | 27.187 seconds | 25.359773 + 0.857836 = 26.217609 seconds |
| B | 39.649 seconds | 41.154 seconds | 39.655785 + 0.711899 = 40.367684 seconds |

For both groups, before/after source-byte, source-metadata and guard comparisons
returned 0; the fixture directories were empty after normal completion.
Independent result review verified each exact method roster, original
entry/return resource observations, complete log, exit and unchanged archive.
This does **not** retroactively make the full 33-method invocation successful or
resource-compliant. The defensible accounting remains **26 completions in the
failed aggregate, plus separately constrained 3/3 and 4/4 passes**.

Private original packets are retained locally; only hashes and bounded result
summaries are recorded here. No raw log, fixture tree, cache, payload, credential
or private key is committed.

| Retained original | SHA-256 |
| --- | --- |
| Initial pre-test failure log | `9e445dc4a6d24e53e93127402618a278aa63dcdba82cb67802731aa66d6c4c93` |
| Failed full-suite log | `59355db3fd5727dea5965924a8096980f554242cdc14192f03689dadb992b810` |
| Group A complete log | `7931cb8e1668b9f2d77474e55dc863dddb23d39aec6f77eb2b146239dfa4f463` |
| Group B complete log | `c8631942fe63f866f2ce6ebbd53aacca1fa38ecc31e81eaf8bad168a0851de89` |
| Effective-limit guard | `88808ad6781a7950462aa029d008afe2b0f3d772dee98d00293f39b80581b609` |
| Effective-limit outer wrapper | `b2fd7e185b47ea86bac646e2bc02b4a7ce46546fb149574ea642584b4dd2e445` |

## Remaining prerequisites and HOLDs

The exact seal-only source/model and the bounded results above have independent
review. No upload/provider/native integration has been accepted; future source
increments still require their own exact review. The original Stage1 initializer
must not be moved or rerun to impersonate legacy staging; a distinct typed fresh-authority
productive producer/retirement/export/freeze/save/probe bridge remains needed.
Stage2 original acquisition and ordinary custody/simulator/workflow integration
remain separate. Configuration-only work cannot supply ordinary ABI, simulator
or transcript acceptance.

Both ordinary activation HOLDs and the whole-JVM interlock remain. The proposed
5,400-second bootstrap budget is **UNADMITTED / UNMEASURED**. An exact-head owner
PR authorization comment, trusted-original-base recipient bootstrap, current
genuine environment/run allocation, required GitHub checks and the normal PR
merge path, and native/provider/resolver/custody/delivery/scheduling
qualification are still required. At the September 26 metadata refresh,
GitHub's native required-review count was **0**; this note does not impose an
extra different-account approval requirement. Independent agent source review
does not supply the owner's authorization or a GitHub-native review. No local
Java/Gradle/Xcode/app build, SDK/dependency download, emulator, simulator, held
CI dispatch, policy deadline change or publication follows from this source.
No acceptance claim or issue closure is made here.
