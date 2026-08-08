#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/publish-maven-central.yml"
CI_WORKFLOW="$ROOT/.github/workflows/ci.yml"
DRY_RUN_WORKFLOW="$ROOT/.github/workflows/release-dry-run.yml"
DESKTOP_WORKFLOW="$ROOT/.github/workflows/desktop-cross-host.yml"
ANDROID_LOCK="$ROOT/samples/p2p-sample-android/gradle.lockfile"
DESKTOP_BUILD="$ROOT/samples/p2p-sample-desktop-ui/build.gradle.kts"
DESKTOP_LOCK="$ROOT/samples/p2p-sample-desktop-ui/gradle.lockfile"
VERSION_CATALOG="$ROOT/gradle/libs.versions.toml"
XCODEGEN_INSTALLER="$ROOT/scripts/install-xcodegen.sh"
CI_SCOPE_CLASSIFIER="$ROOT/scripts/classify-ci-scope.sh"

[[ -f "$WORKFLOW" ]] || { echo "FATAL: Maven Central workflow is missing" >&2; exit 1; }
[[ -f "$DESKTOP_WORKFLOW" ]] || { echo "FATAL: Desktop cross-host workflow is missing" >&2; exit 1; }
ruby -e 'require "yaml"; YAML.safe_load_file(ARGV.fetch(0), aliases: true)' "$WORKFLOW"
ruby -e 'require "yaml"; YAML.safe_load_file(ARGV.fetch(0), aliases: true)' "$DESKTOP_WORKFLOW"
ruby - "$WORKFLOW" <<'RUBY'
require "json"
require "yaml"

workflow = YAML.safe_load_file(ARGV.fetch(0), aliases: true)
jobs = workflow.fetch("jobs")
publish = jobs.fetch("publish-release")
raise "release secrets must not be job-scoped" if publish.key?("env")

secret_steps = publish.fetch("steps").map do |step|
  step.fetch("name") if JSON.generate(step).include?("secrets.")
end.compact
expected = [
  "Revalidate approved release and credentials",
  "Build and inspect signed Central bundle",
  "Upload once and wait for publication",
]
raise "unexpected secret-bearing steps: #{secret_steps.inspect}" unless secret_steps == expected

other_jobs = jobs.reject { |name, _| name == "publish-release" }
raise "release secrets escaped the protected job" if JSON.generate(other_jobs).include?("secrets.")
RUBY

require_text() {
    local text="$1"
    grep -Fq -- "$text" "$WORKFLOW" || {
        echo "FATAL: release workflow is missing: $text" >&2
        exit 1
    }
}

require_text 'tags: ["v*"]'
require_text 'environment:'
require_text 'name: maven-central'
require_text 'persist-credentials: false'
require_text 'scripts/check-maven-central-version.sh absent'
require_text 'MAVEN_CENTRAL_NAMESPACE: io.github.apdelrahman1911'
require_text 'scripts/tests/check-maven-namespace-access-test.sh'
require_text 'scripts/build-central-portal-bundle.sh'
require_text 'scripts/publish-central-portal-bundle.sh'
require_text 'cancel-in-progress: false'
if grep -Fq 'MAVEN_CENTRAL_NAMESPACE: io.github.p2pkit' "$WORKFLOW"; then
    echo "FATAL: release workflow contains the unverified io.github.p2pkit namespace" >&2
    exit 1
fi
grep -Fq 'publishingType=AUTOMATIC' "$ROOT/scripts/publish-central-portal-bundle.sh" || {
    echo "FATAL: Portal client is not locked to automatic publication" >&2
    exit 1
}

if grep -Eq 'pull_request_target|contents:[[:space:]]*write|id-token:[[:space:]]*write' "$WORKFLOW"; then
    echo "FATAL: release workflow grants an unsafe trigger or permission" >&2
    exit 1
fi

while IFS= read -r use; do
    revision="${use##*@}"
    revision="${revision%% *}"
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || {
        echo "FATAL: release action is not pinned by full commit: $use" >&2
        exit 1
    }
done < <(sed -n 's/^[[:space:]]*uses:[[:space:]]*//p' "$WORKFLOW")

for workflow in "$CI_WORKFLOW" "$DRY_RUN_WORKFLOW" "$WORKFLOW"; do
    grep -Fq "'platforms;android-36' 'platforms;android-37.0'" "$workflow" || {
        echo "FATAL: workflow does not install API 36 for libraries and API 37 for the Android sample: $workflow" >&2
        exit 1
    }
    grep -Fq 'scripts/install-xcodegen.sh "$RUNNER_TEMP/p2pkit-xcodegen"' "$workflow" || {
        echo "FATAL: workflow does not install the pinned XcodeGen tool: $workflow" >&2
        exit 1
    }
done

grep -Fq 'os: [ubuntu-latest, windows-latest]' "$DESKTOP_WORKFLOW" || {
    echo "FATAL: Desktop cross-host workflow does not cover Linux and Windows" >&2
    exit 1
}
for task in \
    ':p2p-sample-desktop-ui:test' \
    ':p2p-sample-desktop-ui:checkRuntime' \
    ':p2p-sample-desktop-ui:hotRunArgfile' \
    ':p2p-sample-desktop-ui:createDistributable'; do
    grep -Fq -- "$task" "$DESKTOP_WORKFLOW" || {
        echo "FATAL: Desktop cross-host workflow is missing $task" >&2
        exit 1
    }
done
if grep -Eq -- 'continue-on-error|--offline|--write-locks|--write-verification-metadata' "$DESKTOP_WORKFLOW"; then
    echo "FATAL: Desktop cross-host verification is non-blocking, assumes a warm cache, or rewrites dependency state" >&2
    exit 1
fi
while IFS= read -r use; do
    revision="${use##*@}"
    revision="${revision%% *}"
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || {
        echo "FATAL: Desktop cross-host action is not pinned by full commit: $use" >&2
        exit 1
    }
done < <(sed -n 's/^[[:space:]]*uses:[[:space:]]*//p' "$DESKTOP_WORKFLOW")

for target in linux-arm64 linux-x64 macos-arm64 macos-x64 windows-arm64 windows-x64; do
    grep -Fq "\"$target\"" "$DESKTOP_BUILD" || {
        echo "FATAL: Desktop build does not declare lock target $target" >&2
        exit 1
    }
    catalog_target="${target//-/.}"
    grep -Fq "libs.jetbrains.compose.desktop.$catalog_target" "$DESKTOP_BUILD" || {
        echo "FATAL: Desktop build does not map lock target $target to the catalog" >&2
        exit 1
    }
    grep -Fq "jetbrains-compose-desktop-$target" "$VERSION_CATALOG" || {
        echo "FATAL: version catalog is missing Desktop target $target" >&2
        exit 1
    }
done
grep -Fq 'p2pkit.desktop.lockTarget is for dependency resolution only' "$DESKTOP_BUILD" || {
    echo "FATAL: foreign Desktop runtime execution is not guarded" >&2
    exit 1
}
if grep -Eq 'org\.jetbrains\.compose\.desktop:desktop-jvm-(linux|macos|windows)|org\.jetbrains\.skiko:skiko-awt-runtime-(linux|macos|windows)' "$DESKTOP_LOCK"; then
    echo "FATAL: Desktop lock remains tied to one operating system or architecture" >&2
    exit 1
fi

ruby - "$CI_WORKFLOW" <<'RUBY'
require "yaml"

workflow = YAML.safe_load_file(ARGV.fetch(0), aliases: true)
timeout = workflow.fetch("jobs").fetch("complete-gate").fetch("timeout-minutes")
raise "CI complete-gate timeout must be at least 60 minutes" unless timeout >= 60
RUBY

grep -Fq 'XCODEGEN_VERSION="2.45.4"' "$XCODEGEN_INSTALLER" || {
    echo "FATAL: XcodeGen installer version is not pinned" >&2
    exit 1
}

grep -Fq 'scripts/tests/check-markdown-links.sh' "$CI_WORKFLOW" || {
    echo "FATAL: CI does not validate active Markdown links" >&2
    exit 1
}
grep -Fq 'id: scope' "$CI_WORKFLOW" || {
    echo "FATAL: CI does not classify full versus lightweight required checks" >&2
    exit 1
}
grep -Fq 'protected merge push reuses the required PR gate' "$CI_WORKFLOW" || {
    echo "FATAL: CI does not avoid the redundant post-merge complete gate" >&2
    exit 1
}
grep -Fq "if: steps.scope.outputs.full == 'true'" "$CI_WORKFLOW" || {
    echo "FATAL: CI full-gate steps are not scope guarded" >&2
    exit 1
}
grep -Fq "if: steps.scope.outputs.full != 'true'" "$CI_WORKFLOW" || {
    echo "FATAL: CI does not provide the lightweight required-check path" >&2
    exit 1
}
grep -Fq 'fetch-depth: 0' "$CI_WORKFLOW" || {
    echo "FATAL: CI cannot classify changes without complete comparison history" >&2
    exit 1
}
[[ -x "$CI_SCOPE_CLASSIFIER" ]] || {
    echo "FATAL: CI scope classifier is missing or not executable" >&2
    exit 1
}
grep -Fq 'scripts/tests/classify-ci-scope-test.sh' "$CI_WORKFLOW" || {
    echo "FATAL: CI scope classifier regression test is not wired into CI" >&2
    exit 1
}
grep -Fq 'scripts/tests/classify-ci-scope-test.sh' "$ROOT/scripts/run-release-gate.sh" || {
    echo "FATAL: CI scope classifier regression test is not in the release gate" >&2
    exit 1
}
grep -Fq 'scripts/tests/check-kotlin-toolchain-policy-test.sh' "$CI_WORKFLOW" || {
    echo "FATAL: CI does not enforce Kotlin/iOS toolchain compatibility policy" >&2
    exit 1
}
grep -Fq 'scripts/tests/check-kotlin-toolchain-policy-test.sh' "$ROOT/scripts/run-release-gate.sh" || {
    echo "FATAL: release gate does not enforce Kotlin/iOS toolchain compatibility policy" >&2
    exit 1
}
grep -Fq 'scripts/tests/check-markdown-links.sh' "$ROOT/scripts/run-release-gate.sh" || {
    echo "FATAL: release gate does not validate active Markdown links" >&2
    exit 1
}
grep -Fq 'XCODEGEN_SHA256="090ec29491aad50aec10631bf6e62253fed733c50f3aab0f5ffc86bc170bdbef"' "$XCODEGEN_INSTALLER" || {
    echo "FATAL: XcodeGen installer checksum is not pinned" >&2
    exit 1
}

grep -Fq '"io.netty" -> "4.1.136.Final"' "$ROOT/build.gradle.kts" || {
    echo "FATAL: Netty advisory floor is not 4.1.136.Final" >&2
    exit 1
}
[[ "$(grep -Fc '"org.jsoup:jsoup" to "1.23.1"' "$ROOT/build.gradle.kts")" == "2" ]] || {
    echo "FATAL: root and project build-tool jsoup advisory floors are not 1.23.1" >&2
    exit 1
}
grep -Fq 'io.netty:netty-codec-http:4.1.136.Final=' "$ANDROID_LOCK" || {
    echo "FATAL: Android test tooling is not locked to patched Netty" >&2
    exit 1
}
if grep -Fq 'io.netty:netty-codec-http:4.1.135.Final=' "$ANDROID_LOCK"; then
    echo "FATAL: vulnerable Netty remains in the Android test-tooling lock" >&2
    exit 1
fi

for module in \
    library/p2p-core \
    library/p2p-transport-lan \
    library/p2p-network-provisioning-android \
    library/p2p-network-provisioning-desktop; do
    grep -Fq 'offlineMode.set(true)' "$ROOT/$module/build.gradle.kts" || {
        echo "FATAL: published-module Dokka is not deterministic/offline: $module" >&2
        exit 1
    }
done

echo "RESULT: PASS — release and Desktop cross-host workflows, deterministic Dokka, Android SDK, and build-tool security policy are locked"
