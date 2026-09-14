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
The root observer and independent assessor require the original Gradle
`StartParameter.taskNames` triple `[TASK, "--tests", SELECTOR]`; that API retains
task arguments, not just names. Missing/duplicate filters, other/glob selectors,
abbreviations and extra tokens are rejected without filtering or rewriting the
observed list. The separate buildSrc graph does not use the root's command tokens.
Dry runs, excluded tasks and the exact Test filter/graph/worker checks remain
independent rejection boundaries. Global options such as the maintained `--info`
are parsed separately, not part of this triple. Pure report models do not prove
real Gradle parsing or execute the observer; the genuine current/preimage witness
must supply those observations before [#433](https://github.com/p2pKit/P2pKit/issues/433) can close.
The scoped init observer records the actual task graph/outcomes, selected filter,
JDK17 launcher, worker JVM arguments and test events. It sets the Test JVM's
`java.io.tmpdir` explicitly to the fresh owned directory; a daemon `-D` flag alone
would not establish that bridge. Test source remains unchanged.
The observer's host properties and `doFirst` run in the **JDK21 daemon**, not the
Test worker. JDK17 attribution separately requires the admitted native JDK17
executable/version probe, its exact JavaLauncher path and the original info log's
actually launched Test-worker command. Daemon metadata alone is insufficient.

For [#434](https://github.com/p2pKit/P2pKit/issues/434), Java's actual
`temporaryFileKey` is a **nullable diagnostic**, not native identity authority.
The standard Windows JDK provider returns null; requiring a key rejects the
supported host. Present JSON null is valid, but a missing field or a non-null
empty/oversized/non-string value is not. Never synthesize a key or stringify null.
The Java guard still verifies the physical, ordinary, non-other/nonlinked, empty
directory, request/owner hashes and all original Test/launcher/argument rules.
Its admission explicitly names the request's exact `temporaryOwnerSha256`.

The controller instead records positive bounded native Python device/inode
identity (and available birth time) **at its owned `mkdir`**. The canonical
`temporary-owner.json` binds that creation to source/run/case/nonce/context job
and path. Schema-2 `temporary-before.json` and `temporary-after.json` compare
root-first full `lstat` observations to that identity and the exact owner hash,
immediately before the selected leaf and after its same-home stop. They retain
bounded direct-entry metadata only, also on failure: no payload reads, recursive
scratch inventory, guessed cleanup or raw scratch upload. Missing/zero/replaced
identity, symlink/reparse ancestry, changed/unreadable owner, observation errors,
nonempty roots or missing retention block acceptance and disposal. Original
product/stop errors remain authoritative when a later observation also fails.
Metadata files do not claim product success; original selected-test/receipt and
case/outer retirement must all pass separately before final acceptance.

This is an invocation-owned, otherwise quiescent before/after snapshot contract,
**not an atomic directory pin**. It cannot exclude hostile replace-and-restore,
file-ID reuse or modification after the last observation. The former non-null
Java key was never compared with another key and supplied no such guarantee.

The parentless root consumes its own three explicit request properties. Only its
exact direct `buildSrc` child may consume that root parent's complete triplet;
Gradle's nested build does not reliably inherit the command-line properties.
Foreign/deeper builds, a different physical authority root, and partial or
conflicting child properties fail closed. Both scope reports retain the observed
authority, parent root and locally present three-key subset, not all properties.
The independent assessor checks these observations against the fresh request.

After native admission, one small owned `binding-controls` Gradle leaf executes
the complete production observer callback against 24 finite adverse **models**.
The same fixture loads the production task-policy class from that fresh observer
GroovyShell's classloader and exercises 21 **constructed real StartParameter**
inputs: exact root and distinct buildSrc positives, missing/duplicate/broadened
selectors, extra tasks/options, and root/child dry-run/exclusion negatives.
Eight additional modeled `BasicFileAttributes` inputs execute the production
temporary-policy class from the same loader: null/non-null-key positives and
non-directory/other/link/nonempty/invalid-key negatives. These exercise the actual
shared predicates, not actual command-line parsing, a Windows filesystem provider,
or a complete successful observer invocation. Another 25 worker-policy models
exercise the same observer class's exact rendering, native-charset selection,
bounded new-file selection and capture/write-error preservation. They do **not**
execute an actual failed Test's `afterTask` callback. The schema-4 report retains exact
observed fields, nullable key diagnostics and precise exception outcomes for independent checking.
It has no plugins/dependencies/product tasks and copies the checked-in daemon
criteria. Its bounded report distinguishes precise binding/request rejections
from wrong exceptions or later host refusal; canonical leaf retention is required
for acceptance. An unbound failure copy cannot become a passing result. These
models are not real Gradle parents. The subsequent current/preimage products must
still supply actual root/buildSrc observations and all original native criteria.

Accept current positive **before** attempting the preimage:

- The pinned Kotlin JVM report uses suite `FileTransferJvmTest[jvm]` and testcase
  `durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent[jvm]`.
  Its `classname` stays `dev.p2pkit.core.transfer.FileTransferJvmTest`; selectors
  and listener events keep the canonical class and bare method. For
  [#435](https://github.com/p2pKit/P2pKit/issues/435), require exactly those distinct
  identities, not arbitrary suffixes or the old model-only report labels.
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

### Selected worker argument file (#436)

Gradle 9.7.0's pinned
[worker producer](https://github.com/gradle/gradle/blob/3defbfc59d757b873d787b2261de5c7f8a00970a/platforms/core-execution/worker-process-services/src/main/java/org/gradle/process/internal/worker/child/ApplicationClassesInSystemClassLoaderWorkerImplementationFactory.java)
uses one generated Java9+ classpath argument file. This is not permission for
caller-supplied `@` options. The supported basename is
`gradle-worker-classpath[0-9]{1,20}txt` (**no dot** before `txt`), a direct child
of this case's fresh `state/gradle-home/.tmp`. The distinct compiler-worker file
is a prelaunch baseline member, never the selected Test file.

Before Test launch, `workerExpansion` in `test-admission.json` records the actual
Gradle version/home, nonmodular JUnit framework observation, `WORKER_MAIN`
registry bootstrap path/size/hash, and ordered application classpath with file,
directory or missing-output kind. The actual module detector supplies this
classpath; missing core build outputs are recorded and omitted just as the
worker builder does. The bootstrap comes from Gradle's registry, not an argfile
or cache search. Existing class/resource directories and JARs must belong to the
current core build or case-owned strict dependency cache. Shared/sibling homes,
module paths, wildcard/aliased paths and other producer shapes fail closed.

This finite profile admits canonical printable ASCII Windows paths, excluding
quotes (including apostrophes), semicolons, control characters, traversal, ADS,
reserved names and wildcards. Logged paths must also be whitespace-free;
classpath entries may contain spaces or `#`. Expected tokens are independently
formed as `-cp` and one semicolon-joined bootstrap/application classpath. They use
the pinned ArgWriter's doubled backslashes, conditional whole-argument quoting
and CRLF after **each** token. The observed daemon native charset follows
`native.encoding`, supported `sun.jnu.encoding`, then the default charset.
Encoding the **entire** authorized string must equal strict ASCII bytes; neither
JDK21's default nor worker `file.encoding=UTF-8` is treated as that proof. There
are at most 64 path components, 512 effective entries and 256KiB of bytes. Unsupported encodings or
paths require a separately reviewed profile, not normalization or extra options.

The selected `afterTask` callback, including an actual failed Test, rechecks its
authority and selects exactly one new file absent from the bounded prelaunch
inventory. It retains exact original bytes as private `worker-classpath.raw`
before Gradle returns and before same-home stop. NIO checks physical ancestors,
ordinary type, size, modification time and any available file key; a null Java
key remains valid and is **not** native identity. No unrelated temporary file
contents are read. Write-once `worker-classpath.json` (schema 1) binds the request,
admission hash, callback time, finite after-inventory, original path/size/hash and
`CAPTURED` or a bounded `REFUSED` reason. Capture failures do not replace the
original Test outcome, and missing capture is not synthesized.

After the finalized product/stop leaf, the controller independently renders and
checks the bytes and joins the one new file to exactly one original logged Test
launch/start ID, admitted JDK17, working directory, full JVM options, exact
`worker.org.gradle.process.internal.worker.GradleWorkerMain` and display-name
argument. No other `@`, classpath/module override, OS override, agent or changed
critical option is admitted. Native `regular()`/`lstat` checks then verify the
original, private snapshot and bootstrap, including nonreparse ancestry,
`nlink == 1`, stable identity/attributes and unchanged size/hash/content.

The separate, small `worker-classpath-retention.json` (schema 1) records actual
post-stop native identities/attributes and `QUALIFIED` or finite `REFUSED` status,
transitively bound to the original request/capture/leaf. It never edits a
`CAPTURED` observer report into a refusal. Public `worker-classpath.args` is an
exact copy of the **read original snapshot bytes**, allowed only after content,
launch association and native checks pass. A later XML/product failure does not
erase safely retained originals or replace the primary failure. New classpath
metadata is safety-checked before copying observer reports. All four existing
seal/verify/pre-disposal entrypoints revalidate these three fixed public files;
unknown raw files, malformed fields, stale hashes or changed bytes block them.

These are source-bound, quiescent before/after snapshots, **not** creator-PID
tracing, hostile atomic pinning or full product acceptance. If the original is
missing after stop, retain the before-stop snapshot as private unqualified
evidence, block disposal and never reconstruct it. Unsafe raw bytes are never
uploaded; an ephemeral hosted machine is not a durable private evidence channel.
The inspected producer does not establish that stop necessarily deletes files.

Historical [R10/attempt1](https://github.com/p2pKit/P2pKit/actions/runs/34861390053/attempts/1)
remains **FAILED**: current product/stop/final `0/0/0`, preimage **NOT_EXECUTED**.
The XML label predicate failed first; the blanket `@` guard was **NOT REACHED**.
R10 did not retain the argument-file contents, so its pathname is not an
expansion-integrity pass. Closing [#436](https://github.com/p2pKit/P2pKit/issues/436)
still requires independent source/design review, genuine fresh Windows
current/preimage original-byte and native-result acceptance, required checks,
formal review and normal merge. Pure/model controls do not satisfy those gates.

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
