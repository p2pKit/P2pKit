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
- Android SDK Platform 36 for Android builds.
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

The required `complete-gate` check classifies each change conservatively:

- a non-empty Markdown-only change runs link, layout, release-metadata, scope,
  and whitespace checks;
- any source, build, workflow, script, dependency, security, license, API, or
  release change runs the complete module/platform, ABI, Dokka, SBOM,
  publication-consumer, XCFramework, provenance, and Swift gate;
- an empty or unclassifiable change set fails closed to the complete gate;
- a protected merge push reuses the complete check already required on the
  exact pull-request tree instead of repeating the expensive gate; and
- a manual workflow dispatch always runs the complete gate.

The lightweight path does not weaken branch protection: it produces the same
required check name after executing the checks appropriate to documentation
only. Adding any non-Markdown file automatically selects the complete path.

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
