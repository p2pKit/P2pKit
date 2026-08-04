#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKFLOW="$ROOT/.github/workflows/publish-maven-central.yml"
CI_WORKFLOW="$ROOT/.github/workflows/ci.yml"
DRY_RUN_WORKFLOW="$ROOT/.github/workflows/release-dry-run.yml"
ANDROID_LOCK="$ROOT/p2p-sample-android/gradle.lockfile"
XCODEGEN_INSTALLER="$ROOT/scripts/install-xcodegen.sh"

[[ -f "$WORKFLOW" ]] || { echo "FATAL: Maven Central workflow is missing" >&2; exit 1; }
ruby -e 'require "yaml"; YAML.safe_load_file(ARGV.fetch(0), aliases: true)' "$WORKFLOW"
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
require_text 'scripts/build-central-portal-bundle.sh'
require_text 'scripts/publish-central-portal-bundle.sh'
require_text 'cancel-in-progress: false'
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
    grep -Fq "'platforms;android-36'" "$workflow" || {
        echo "FATAL: workflow does not install the stable Android API-36 platform: $workflow" >&2
        exit 1
    }
    if grep -Fq "platforms;android-37" "$workflow"; then
        echo "FATAL: workflow requests unavailable Android API-37 platform: $workflow" >&2
        exit 1
    fi
    grep -Fq 'scripts/install-xcodegen.sh "$RUNNER_TEMP/p2pkit-xcodegen"' "$workflow" || {
        echo "FATAL: workflow does not install the pinned XcodeGen tool: $workflow" >&2
        exit 1
    }
done

grep -Fq 'XCODEGEN_VERSION="2.45.4"' "$XCODEGEN_INSTALLER" || {
    echo "FATAL: XcodeGen installer version is not pinned" >&2
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
grep -Fq 'io.netty:netty-codec-http:4.1.136.Final=' "$ANDROID_LOCK" || {
    echo "FATAL: Android test tooling is not locked to patched Netty" >&2
    exit 1
}
if grep -Fq 'io.netty:netty-codec-http:4.1.135.Final=' "$ANDROID_LOCK"; then
    echo "FATAL: vulnerable Netty remains in the Android test-tooling lock" >&2
    exit 1
fi

echo "RESULT: PASS — release workflow, Android SDK, and Netty security policy are locked"
