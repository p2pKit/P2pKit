# Contributing to P2pKit

Thank you for improving P2pKit. The project is a Kotlin Multiplatform library,
so apparently local changes can affect Android, JVM/Desktop, Apple binaries,
published metadata, and the wire protocol.

## Before opening a change

1. Search existing issues and read the [documentation index](docs/README.md).
2. For a security vulnerability, use the private process in
   [SECURITY.md](SECURITY.md), not a public issue.
3. Discuss breaking API/protocol changes before implementation. Published
   coordinates and tags are immutable.

## Development setup

- JDK 17 and the checked-in Gradle wrapper.
- Bash, Git, and Ruby with its standard library for the shell checks (`ruby --version`).
  On Windows, run `.sh` gates in Bash with Ruby on `PATH`; see [local testing](docs/testing/local.md).
- Android SDKs from the [canonical Android setup](docs/testing/local.md#android-sdk-setup).
  Both the library/shared-module and Android app sample platforms are required for repository-wide checks.
- macOS/Xcode and the pinned XcodeGen installer for Apple checks.

Run the fast local gate:

```bash
scripts/tests/check-repository-layout.sh
scripts/tests/check-osv-lockfile-coverage.sh
scripts/tests/check-markdown-links.sh
scripts/check-release-metadata.sh
./gradlew check --console=plain
git diff --check
```

Before requesting a release-facing review, follow
[`docs/testing/local.md`](docs/testing/local.md) and the complete
[`docs/releasing/checklist.md`](docs/releasing/checklist.md).

## CI scope policy

Every CI event runs the Linux and Windows library suites. The required
`complete-gate` rejects failed, cancelled or skipped results from either host,
then classifies the macOS work conservatively:

- a non-empty Markdown-only PR/push delta runs link, layout, release-metadata, scope,
  and whitespace checks;
- any delta containing a non-`.md` path runs the complete module/platform, ABI, Dokka, SBOM,
  publication-consumer, XCFramework, provenance, and Swift gate;
- empty deltas and unavailable/non-ancestor push bases select the full gate;
  invalid event identities or Git inspection failures fail the job;
- every main push is classified from its complete event-before-to-HEAD delta,
  including merges whose tree equals the pull-request head. Git topology is
  not proof of a successful check; no previous check result is reused; and
- manual dispatches and the weekly schedule (Monday, 04:17 UTC) always request
  the full gate, with all-tree whitespace/dependency checking.

The schedule uses GitHub's default branch (`main`) and a separate concurrency
group, so ordinary pushes/dispatches cannot cancel it; a later scheduled run
does not cancel an already running backstop. This is defense in depth, not a
one-week execution guarantee: GitHub can delay/drop scheduled runs, and checks
can fail. Inspect missing/failed runs and dispatch `CI` on the intended ref
when necessary; verify its recorded commit and actual full-gate results.

Keep the main ruleset's pull-request, deletion/non-fast-forward and strict
required checks (`complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`).
The administrator bypass and branch-creation exception remain owner-controlled;
scope classification does not assume they were unused or prevent bypass itself.
Both scopes keep the required check name; a green lightweight result proves
its documentation checks and the two JVM hosts, not the full macOS gate.

## Change rules

- Keep production modules under `library/` and test/sample applications under
  `samples/`; preserve Gradle project and artifact names.
- Add deterministic regression tests for behavior changes. Do not weaken
  assertions, hide failures with larger timeouts, or skip required platforms.
- Keep JVM, Android, and Apple protocol behavior aligned.
- Never commit credentials, private/signing keys, access tokens, personal
  device identifiers, payload evidence, or generated build artifacts.
- Do not mark physical-device, hostile-network, interoperability, or audit work
  complete without the evidence required by the external validation plan.
- Keep structural cleanup separate from functional changes.

## Pull requests

Use a focused title, explain the problem and compatibility impact, list exact
commands/results, and identify any validation that remains external. A pull
request should be reviewable as a small number of coherent commits. Do not
rewrite published release history or move release tags.
