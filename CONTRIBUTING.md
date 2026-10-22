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

The maintained [modular CI](.github/workflows/ci.yml) runs all fourteen required
components for pull requests, main pushes and the weekly Monday 04:17 UTC
backstop. This includes documentation-only changes: there is no Markdown-only
qualification shortcut. [`scripts/ci_component.py`](scripts/ci_component.py)
owns the exact tasks and host assignments for source, dependencies, JVM,
Android, Apple, Desktop, security, compatibility, consumers and shared checks.

A component can be dispatched independently for diagnosis or rerun after a
failure. The final aggregation accepts only successful, unexpired results with
the exact same source commit, canonical version and required environment. It
rejects missing, stale, failed or mismatched results. A different source needs
fresh matching evidence; tree similarity and a green unrelated run are not
qualification. Optional diagnostics do not replace mandatory components.

Test reports and relevant logs are collected in source/run/attempt-bound
`ci-evidence-*` encrypted Actions artifacts with **14-day retention**. An
artifact or green job alone does not prove that the required tests executed:
inspect the manifest, task outcomes and original reports. Dependency caches are
an optimization; strict locks, verification and approved repositories remain
mandatory on cache hits and misses.

Concurrency groups do not cancel in-progress work. GitHub may queue or delay
jobs and weekly schedules; a schedule is not a one-week execution guarantee.
If necessary, dispatch the missing component on the intended exact source,
then request aggregation of its complete matching result set.

Keep the main ruleset's pull-request, deletion/non-fast-forward and strict
required checks (`complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`).
A focused pass is not the complete gate. Protected merge, immutable tagging,
Maven signing/publication, application freeze and post-build approval still
follow the [release checklist](docs/releasing/checklist.md).

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
