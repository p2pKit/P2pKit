# Windows directory-fsync method-preimage control

This is one bounded acceptance witness for [#141](https://github.com/p2pKit/P2pKit/issues/141),
not the full Windows/Linux library gate, Desktop matrix, sudden-power-loss proof,
or release qualification. A configured workflow, pure fixture pass or another
host's result does not establish Windows execution.

## Exact question and source identities

The unchanged test is:

```text
:p2p-core:jvmTest --tests dev.p2pkit.core.transfer.FileTransferJvmTest.durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent --console=plain
```

It calls the public factory, writes 4096 synthetic bytes through the real sink,
checks that publication is not premature, commits twice, and checks final bytes
and directory contents. It does not inject an operating-system name or a
directory-sync function. Its real Windows JDK behavior is the question.

Fix [1df5c0670c90b579de767b6ff568a4beac97ad05](https://github.com/p2pKit/P2pKit/commit/1df5c0670c90b579de767b6ff568a4beac97ad05)
has parent `ba208af23b9ce8e8f6efe1e3f63b0b81b38a4c7a`. Only the old
`syncParentDirectory()` method is restored in a disposable derivative:

```kotlin
private fun syncParentDirectory() {
    FileChannel.open(parent.toPath(), StandardOpenOption.READ).use { it.force(true) }
}
```

The controller independently pins current/historical/transformed source-file
hashes and the unchanged historical/current selected test block. It rejects
preimage drift, checkout CRLF conversion and any additional tracked tree delta.
This is a **historical method on current surrounding source**, not execution of
the whole historical revision. No production source or test is changed in the
campaign checkout. A changed pinned source needs a new reviewed witness, not
automatic hash regeneration.

Each case receives a separate full-history, byte-verified source copy and fresh
sibling executor state/home. Git archive membership and every Git blob are
verified; links, filtering/substitution, omitted files and Windows path aliases
are refused. Each newly owned clone receives repository-local `core.longpaths=true`,
with its effective boolean read back before source preparation. Original config
commands/results are retained; the immutable executor and later ordinary Git
callers inherit this policy. No campaign, global Git or OS settings are changed.
The one-method derivative is committed **locally before** immutable
state initialization, with the exact candidate as its parent. It is never pushed.
Generated BuildInfo must name the actual clean current/derivative commit.

## Dispatch and admission

First obtain independent source review, coordinate the campaign's shared execution
lease, and inspect queued/running Actions, including older/unparticipating jobs.
The six participating jobs' [queue](local.md#participating-hosted-job-queue) is not
a global lease. This Windows question does not authorize another unchanged ARM
multicast probe, a retired audit workflow, or forged hosted identity variables.

After review, an authorized maintainer can use this recipe at the reviewed branch:

```bash
SOURCE="$(git rev-parse HEAD)"
TREE="$(git rev-parse 'HEAD^{tree}')"
BRANCH="$(git branch --show-current)"
gh workflow run desktop-cross-host.yml --repo p2pKit/P2pKit --ref "$BRANCH" \
  -f operation=windows-directory-fsync-control \
  -f expected_sha="$SOURCE" -f expected_tree="$TREE"
```

The controller requires genuine `workflow_dispatch`, repository/ref/workflow
SHA/run/attempt identity and the exact clean expected commit/tree. The default
`desktop` operation remains the ordinary three-host matrix; unknown operations
fail rather than skipping all jobs green. The control job is Windows-only,
contents-read, credential-free, full-history and exact-SHA, without a Gradle cache
action, release environment, arbitrary command input or publishing path.

Admission checks actual native Windows AMD64 Python and PE/JVM JDK architectures,
JDK17 wrapper/Test launcher, JDK21 daemon, and literal SDK36/37.0 metadata. SDK
installation has no interactive stdin and never accepts license prompts. Missing
licenses/platforms are blockers. Initial resource admission requires 6GiB RAM
(2GiB available) and 10GiB free disk; ongoing checks preserve a 7GiB disk reserve.
The controller is bounded to 80 minutes plus a 10-minute finalization allowance,
inside the workflow's separate step/job bounds.

For [#428](https://github.com/p2pKit/P2pKit/issues/428), the Windows batch boundary
quotes every argument in full, including the SDK executable and `--sdk_root`
under `Program Files (x86)`. Parentheses are literal only inside those quotes;
embedded quotes, expansion/control characters and the interpreter's original
restricted grammar remain rejected. `/d /s /v:off /c`, trailing-backslash handling
and before-resume Job ownership are unchanged. Synthetic SDK-shaped native
fixtures test argument forwarding, not the installed SDK or Java itself.

`sdk-tool-before.json` and `sdk-tool-after.json` retain only SHA-256/byte counts for
the actual `cmdline-tools/latest/bin/sdkmanager.bat` and command-tools
`source.properties` (each bounded to 256KiB). No raw installed launcher or
command-tools metadata is uploaded. Post-install drift, unreadable inputs or
missing snapshot retention block native continuation/disposal without replacing
an original SDK-leaf failure. Matching snapshots are not provenance approval or
proof against transient modification: native acceptance must also match them to
separately reviewed exact official Windows SDK package bytes and inspect the
launcher's Java/argument forwarding. Missing or mismatched counterparts remain a
hold; never substitute another package, a Unix launcher or an 8.3 path guess.

Run the **complete maintained Windows executor fixture suite**, retaining its
actual test count and each fixture's cleanup history. Never substitute a Mac
fixture count. Intentional negative nested receipts remain negative evidence;
unexpected fixture failures or unknown retirement block the product witness.

The controller passes the suite's optional `--fixture-parent` argument for its
existing, empty `state/fixtures/native-tmp` directory. The suite validates the
current-state binding and physical path, requires retained evidence outside that
parent, and supplies explicit Python allocation parents without changing
`TEMP`, `TMP`, `TMPDIR` or Python's default temporary directory. The outer
executor and its mandatory real wrapper `--stop` retain the separate owned
`process-tmp` environment. Callers without this option retain default allocation
behavior. The same complete empty-before/empty-after metadata and fixture cleanup
requirements still apply; no residual directory is whitelisted or guessed safe.

## Product and assessment

The public immutable executor and receipt checker own every wrapper invocation,
with strict verification, rerun/no caches, at most two workers, no parallel Gradle,
bounded heap, in-process Kotlin and disabled automatic JDK downloads. Each leaf
must use before-resume Windows Job Object ownership and finish same-wrapper,
same-home `--stop` with no unknown survivors. A separate fallback stop may recover
resources after a broken finalizer; it never repairs a failed receipt into a pass.

Only the exact core selector and normal buildSrc/core prerequisites are allowed.
The scoped init observer records the actual task graph/outcomes, selected filter,
JDK17 launcher, worker JVM arguments and test events. It sets the Test JVM's
`java.io.tmpdir` explicitly to the fresh owned directory; a daemon `-D` flag alone
would not establish that bridge. Test source remains unchanged.
The observer's host properties and `doFirst` run in the **JDK21 daemon**, not the
Test worker. JDK17 attribution separately requires the admitted native JDK17
executable/version probe, its exact JavaLauncher path and the original info log's
actually launched Test-worker command. Daemon metadata alone is insufficient.

The parentless root consumes its own three explicit request properties. Only its
exact direct `buildSrc` child may consume that root parent's complete triplet;
Gradle's nested build does not reliably inherit the command-line properties.
Foreign/deeper builds, a different physical authority root, and partial or
conflicting child properties fail closed. Both scope reports retain the observed
authority, parent root and locally present three-key subset, not all properties.
The independent assessor checks these observations against the fresh request.

After native admission, one small owned `binding-controls` Gradle leaf executes
the complete production observer callback against 24 finite adverse **models**.
It has no plugins/dependencies/product tasks and copies the checked-in daemon
criteria. Its bounded report distinguishes precise binding/request rejections
from wrong exceptions or later host refusal; canonical leaf retention is required
for acceptance. An unbound failure copy cannot become a passing result. These
models are not real Gradle parents. The subsequent current/preimage products must
still supply actual root/buildSrc observations and all original native criteria.

Accept current positive **before** attempting the preimage:

- Current: product/stop/final `0/0/0`, exactly one selected passing test, no skip,
  error, extra test, cached required task or changed source.
- Preimage: product/stop/final **`1/0/1`**, exactly one selected failure whose
  original XML type is `java.nio.file.AccessDeniedException`. The stack must pass
  through WindowsFileSystemProvider, FileChannel.open, syncParentDirectory,
  commit and the selected test. Its filename must be the owned temporary root's
  direct `p2pkit-durable-destination-<digits>` directory child, not a `.part` or
  target-file permission error.
- Fresh nonce/source/run-bound task events, selected JUnit XML, actual worker
  command and native receipts must agree. Compilation/setup failure, stale or
  missing XML, cancellation, stop failure or exit125 is not the expected red.
- Independently verify fixture retirement after the worker drains; the existing
  test's silent best-effort teardown is not proof of deletion.

The outer assessor may return zero after detecting the expected red, but preserves
the original producer exit1 and failed XML. The preimage stops before the second
commit/final assertions; it is not a passing library suite or all of #141.

## Retention and cleanup

Capture complete raw-producing commands before live log delivery. Public upload
is a finite allowlist of nonprivate synthetic-test evidence: source/run/tool/lock
bindings, literal derivative patch and commit, actual observer/BuildInfo/XML,
commands, receipts, fixture cleanup histories and original product/stop statuses.
Do not upload whole states/source trees, `.git`, caches, payload files, credentials
or private device data. Public artifacts are **not** a private retention channel.

The three manifests/artifacts bind `admission`, `current` and `preimage` separately
to SHA/run/attempt and expire after 14 days. Download and independently review
required originals before expiry. An unbound XML salvage is explicitly failure
evidence and never substitutes for fresh producer-bound XML.

Retain and verify required originals before deleting only this allocation's
source copy, Gradle home, fixture, Konan and Android-user roots. Source drift,
incomplete native cleanup, missing retention or invalid leaf finalization blocks
that deletion. The maintained read-only-file retry may change only a proven
owned Windows leaf's READONLY bit, with its original error retained first;
diagnostic/retry failure cannot replace the original removal error.

Failure evidence and unresolved allocations remain distinct from successful
retirement. If safe artifacts cannot be sealed, the job fails; do not rely on
ephemeral runner files surviving job teardown. No subsequent dependent case may
start after uncertain retirement. Campaign/unrelated branches, shared SDKs and
required evidence are never disposable controller inputs.

The [pure fixtures](../../scripts/tests/run-windows-directory-control-test.py) and
[workflow policy controls](../../scripts/tests/check-windows-directory-control-policy-test.rb)
run in both CI scopes and the release/workflow checks. They establish policy only;
genuine hosted execution and independent evidence review remain separate gates.
