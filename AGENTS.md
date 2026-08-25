# Repository Guidelines

## Project Structure & Module Organization

P2pKit is a Kotlin Multiplatform library. Production modules live under `library/`: `p2p-core` contains the public API, protocol, security, sessions, and file transfer; `p2p-transport-lan` provides Bonjour/JmDNS and TCP transport; and the provisioning modules add Android or Desktop network setup. Applications and test harnesses belong in `samples/`. Shared build logic is in `buildSrc/`, repository checks are in `scripts/`, and architecture, testing, and release guidance is in `docs/`. Keep Gradle project and published artifact names stable.

## Build, Test, and Development Commands

Use JDK 17, the checked-in Gradle wrapper, and Android SDK Platform 36.

- `./gradlew check --console=plain` runs the standard cross-module test and verification gate.
- `scripts/tests/check-repository-layout.sh` validates repository layout.
- `scripts/tests/check-osv-lockfile-coverage.sh` checks vulnerability-scan lockfile coverage.
- `scripts/tests/check-markdown-links.sh` verifies documentation links.
- `scripts/check-release-metadata.sh` checks version and release metadata consistency.
- `./gradlew :p2p-sample-desktop-ui:run` launches the Desktop UI sample.
- `./gradlew :p2p-sample-android:assembleDebug` builds the Android sample.

Run `git diff --check` before submitting. Release-facing changes must also follow `docs/releasing/checklist.md`.

## Coding Style & Naming Conventions

Follow `.editorconfig`: UTF-8, LF endings, final newlines, spaces, and four-space indentation (two spaces for XML, YAML, and TOML). Kotlin lines are limited to 120 characters; wildcard imports are forbidden, and filenames must follow ktlint conventions. Use idiomatic Kotlin naming: `UpperCamelCase` types, `lowerCamelCase` functions/properties, and descriptive test names. Keep JVM, Android, and Apple protocol behavior aligned.

## Testing Guidelines

Place tests in the appropriate source set, such as `commonTest`, `jvmTest`, `androidUnitTest`, or Apple test sources. Add deterministic regression coverage for behavior changes; do not mask failures with relaxed assertions, longer timeouts, or platform skips. Physical-device, hostile-network, and interoperability claims require the evidence defined in `docs/validation/test-catalog.md`.

## Commit & Pull Request Guidelines

Recent commits use concise imperative subjects, often with a scope (`build(deps): ...`, `CI: ...`, `Test ...`). Keep commits coherent and separate cleanup from functional changes. Pull requests must explain the problem and compatibility impact, list exact commands and results, link relevant issues, and identify remaining external validation. Include screenshots for visible UI changes. Never commit credentials, signing material, personal device identifiers, payload evidence, or generated artifacts.
