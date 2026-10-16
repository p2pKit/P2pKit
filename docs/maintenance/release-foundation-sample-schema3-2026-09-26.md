# Foundation sample schema3: source-only consumer adaptation

The following is the original implementation record at `694685b9`. Later
review, focused execution and the separate composition update are recorded at
the end; they do not qualify the unintegrated ordinary path.

**SOURCE ONLY / INDEPENDENT IMPLEMENTATION REVIEW PENDING / TESTS AUTHORED BUT
UNEXECUTED / NOT INTEGRATED.** No parser, import, test execution, build, native
inspection, hosted run or Release acceptance is claimed by this increment.

## Exact base and limited change

- Working base: extraction `8831e589176aa0b3f2df3b8810d070abf46f3ec6`, tree
  `e045f637d6b72138007bd903e1d9b9067b8ad09f`.
- Foundation parent: `3359862eb812d0130528909a2f90db716bee7843`.
- Extraction donor: `72cae80c0057257dd0b32b4b91cdcb8449734afc`.
- Branch: `work/cache-prereqs-foundation-20260926-094031`.

The extracted ordinary `sample_snapshot()` required schema2. The unchanged
Foundation producer emits schema3 with canonical/native/Android version binding
and retained inspection records. This increment adapts that consumer, its tiny
synthetic fixture and new focused controls; it does not replace the Foundation
producer or rerun its accepted work. The historical extraction TSV is unchanged
and is not a claim that the new adapter/test bytes came from the donor.

The adapter adds only the existing pure `application_release_version` import;
it does not import or call native package inspectors. Unchanged supplier hashes:

| Supplier | SHA-256 |
| --- | --- |
| `scripts/application_release_version.py` | `060542d8e7ac2a2776b026cccbf56e08928242490e17c31cc2fca5c5bf23e242` |
| `scripts/package-sample-apps.py` | `5cb05987f6480df8c61d9113c2cfba1bfd4ec306a6c4245f5c0a71fdea4f7a0e` |
| `scripts/sample_artifact_identity.py` | `bc4b40b8cdafc623e73223ecd2dadca6f948ed550a57f954e7dcb5b1a18732e8` |

It uses the existing one-shot parent owner and pinned source reader for a
maximum 64KiB `gradle.properties` read, derives the complete version mapping from
that original source, rereads the same pinned source root before success, and
requires known source-reader/directory closure. The existing absolute deadline
is passed through; no fresh allowance is derived. Failures remain with the
parent ledger, and read/close dual failures retain the primary error.

Closed prepare/complete context and generated-root records, the exact unqualified
sample scope, schema3 version binding, embedded source/version identities, Desktop
layout/native-version inspection records, and Android AGP/binary-manifest records
must agree. Bool aliases for integer identity fields are rejected. The snapshot
adds the source-properties SHA-256 and complete version mapping. Existing output
paths, file hashes, checksums, licenses, file identities and byte bounds remain.

These checks bind the **original packager's supplied inspection records** and
retained output files. They are not independent inspection of an APK/MSI/DMG/DEB
or bundled executable. Archive inventories are retained as bounded lists of
records, not re-extracted or independently checked member-by-member. The adapter
does not install, verify signatures, launch an app, repackage, build, or claim
network/physical-device behavior. The successful original packaging phase and
encrypted custody/delivery guards remain prerequisites outside this adapter.

## Authored controls and first-execution boundary

`Schema3SnapshotModels` in `scripts/tests/hosted-consume-delivery-test.py` authors
positive Linux/Android, Windows, arm64 Mac and Intel Mac **record models**. The
small actual files are explicitly synthetic; platform labels do not make them
native packages or native Windows/Mac filesystems.

Authored negative controls cover schema2/missing/extra/duplicate JSON fields,
original scope/generated-root changes, each version field, coherent manifest
substitution against a different source version, malformed/duplicate/escaped or
oversized source declarations, mid-hash source mutation, embedded source/version
and integer types, Desktop architecture/native metadata, Android AGP/binary
disagreement and unsupported signing claims, and read/close/UNKNOWN/deadline
failures. Optional bundled Java/release architecture and Mac universal-image
records have positive cases. Semantic mutations recompute checksums so stale
checksum failures cannot stand in for the intended identity guard.

**None of these controls has run.** Independently review exact implementation,
fixture, new supplier dependency and test bytes before their first execution.
The proposed first selector, from an ordinary-user-accessible reviewed copy, is:

```text
python3 -I -B -S scripts/tests/hosted-consume-delivery-test.py Schema3SnapshotModels -v
```

The fixture's parent directory must be writable by that actual ordinary user;
do not run as root and spoof or weaken the source reader's nonroot requirement.
The selected class loads older modules as fixture suppliers but must not execute
their historical aggregates. Review any further exact selectors separately,
including the existing Windows-file-ID and no-repackage delivery controls.
No historical aggregate or accepted1066-reader rerun is authorized here.

Only bounded Git/shell readback, path/hash comparison and `git diff --check` were
performed while authoring. This is not syntax, import or implementation-test
evidence. No Python/Node parser or test, Java/Gradle/Xcode command, native package
inspector or ownership backend, download, encryption/private-material handling,
CI dispatch or setting change was performed by this increment.

## Composition tripwire deliberately not updated

`scripts/check-hosted-test-composition.py` and all seven expectations are unchanged.
Its controller expectation remains
`e0c4a4aa8c742643253a8e9e47928f8c249837b00f3ffcd2fd8329d0cf29aee2`.
The changed controller therefore is **not a claimed passing composition**.

After exact independent implementation review and authorized bounded parsing,
derive the candidate using that unchanged checker's
`source_digest(final_controller_bytes, "scripts/run-hosted-test-custody.py")`.
Review and explicitly update only the affected expectation in a separate step;
do not automatically bless a computed digest or copy a historical pass. No new
AST digest was calculated here. The other six expectations and suppliers remain
outside this repair.

## Extraction correction and remaining HOLDs

The [extraction note](release-foundation-cache-prerequisites-2026-09-26.md) now
explicitly corrects its overly broad dormant/safe-preservation implication.
Imported `run-platform-tests.py` and the Gradle platform init contract already
activate mandatory ordinary custody from `GITHUB_ACTIONS=true` and
`GITHUB_JOB=complete-gate`; Foundation CI still calls FULL directly. **The
extraction must remain unintegrated until ordinary workflow/controller
integration resolves this incompatibility without weakening anti-fallback.**
This schema3 adapter does not resolve it.

No workflow, Stage1 tail, policy, production/sample code, Foundation packager,
protected instruction or published history was changed. Neither ordinary campaign
activation HOLD is lifted. Missing fixture postimages, typed Stage1/legacy
producer bridging, initializer-path integration, initial-recipient
seal/upload-before/upload-after, Stage2 acquisition/qualification and whole-job
admission remain separate work.

The proposed 5,400-second bootstrap budget remains unadmitted/unmeasured; Windows
native-file 900-second and Snapshot 576MiB limits remain unchanged.
Configuration-only execution is not ordinary ABI/simulator/transcript acceptance.
Genuine native/provider/resolver, custody/delivery/scheduling qualification and
required GitHub checks/personal owner exact-commit authorization still gate normal PR
integration and development sample Releases. No issue is fully accepted or closed
by this source increment.

## Subsequent exact-source review and focused result

Independent implementation review approved source only at
`694685b9d2515995a415d70adce9190c650ac883`, tree
`55438e58ae9aa5dea1df1083f27804a7e47d42c4`. The selected
`Schema3SnapshotModels` executed once as a real nonroot OS user in an exact
Git-archive copy: **24/24 PASS**, 1.341 seconds, exit 0. All inputs were synthetic;
no native inspector, network, build, hosted identity or prior 1,066-file reader
was executed. Independent result review confirmed all 24 named passes, unchanged
before/after supplier hashes and all 211 copied Python suppliers against Git.

Original result-log SHA-256:
`ae6de931b65554085087972ed8574ffe4d92890b8be176b8e50dc556992d289f`.
Execution UID/command/exit are in the original tool record, not inferred from
file ownership or added retroactively to that log.

Only after that review/result, the separate composition increment derives the
controller AST expectation
`ec23554ccc212d16f6bf4a1df9801064986f0564be1d2bf3bc1489fcb97a7d03`
from the exact approved controller bytes. Six other expectations remain unchanged.
Seven authored AST mutations require the schema3 join, source-derived version,
final source reread, known close and retained inspection joins. This pin/control
increment was initially authored awaiting its own review and first execution;
it changes no runtime supplier and does not fix the direct FULL/controller
incompatibility.

The subsequent independent implementation review approved the exact three-file
composition delta. Its first bounded AST-only packet passed the maintained
checker and **35/35 controls**, with 28.477 seconds reported by unittest and
packet exit 0. Independent result review confirmed all named passes and unchanged
before/after checker, test, note and controller hashes. The packet ran as UID 0;
it parsed supplier bytes without importing or executing those suppliers. This
is not a native, runtime, provider, custody or ordinary-integration result.
Original result-log SHA-256:
`3109b8c18836db78de8d48c736a53d94d9ee4060c5c483c57b37b344c15ec8ab`.

The owner-approved PR authorization mechanism is the personal exact-final-head
comment, not a fabricated GitHub author self-review or a different-account
requirement. Agent review is still not personal owner authorization. All other
trust, activation, qualification and publication HOLDs remain.
