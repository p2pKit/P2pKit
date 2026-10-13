#!/usr/bin/env ruby
require "yaml"
require "open3"

ROOT = File.expand_path("../..", __dir__)
JOB = "repository-checks"
GUARD = 'test "$REPOSITORY_CHECK_RESULT" = success'
# Reviewed inventory from the former complete-gate entry-point step. Moving
# these script fixtures must not remove any check or substitute build evidence.
COMMANDS = %w[
    scripts/check-gradle-wrapper.sh
    scripts/tests/check-gradle-wrapper-test.sh
    scripts/tests/check-lock-write-policy-test.sh
    scripts/tests/check-release-tag-test.sh
    scripts/tests/check-release-identity-test.sh
    scripts/check-release-metadata.sh
    scripts/tests/check-maven-release-environment-test.sh
    scripts/tests/check-maven-namespace-access-test.sh
    scripts/tests/check-maven-central-version-test.sh
    scripts/tests/publish-central-portal-bundle-test.sh
    scripts/tests/build-central-portal-bundle-test.sh
    scripts/tests/install-xcodegen-test.sh
    scripts/tests/release-workflow-test.sh
    scripts/tests/check-sample-run-profiles.sh
    scripts/tests/check-repository-layout.sh
    scripts/tests/check-osv-lockfile-coverage.sh
    scripts/tests/check-markdown-links.sh
    scripts/tests/classify-ci-scope-test.sh
    scripts/tests/resolve-ci-scope-test.sh
    scripts/tests/check-git-whitespace-test.sh
    scripts/tests/check-kotlin-toolchain-policy-test.sh
].freeze

def check_preflight(workflow)
    jobs = workflow.fetch("jobs")
    job = jobs.fetch(JOB)
    raise "preflight must run independently and unconditionally" if
        %w[if needs continue-on-error defaults env container services].any? { |key| job.key?(key) }
    raise "preflight must keep the supported host and bounded budget" unless
        job["runs-on"] == "macos-latest" && job["timeout-minutes"] == 30
    steps = job.fetch("steps")
    raise "preflight must only set up the pinned tools and execute the inventory" unless steps.length == 6
    raise "preflight steps cannot skip, ignore failures or override execution" if steps.any? do |step|
        %w[if continue-on-error env shell working-directory].any? { |key| step.key?(key) }
    end
    checkout, java, gradle, xcodegen, sdk, test = steps
    raise "preflight checkout must use the same immutable workflow source" unless
        checkout.fetch("uses").start_with?("actions/checkout@") && checkout["with"] == {
            "ref" => "${{ github.sha }}", "fetch-depth" => 0, "persist-credentials" => false,
        }
    raise "preflight must use JDK17" unless java.fetch("uses").start_with?("actions/setup-java@") &&
        java["with"] == {"distribution" => "temurin", "java-version" => "17"}
    raise "fixture builds must keep Gradle build-cache exclusions" unless
        gradle.fetch("uses").start_with?("gradle/actions/setup-gradle@") &&
        gradle["with"] == {"gradle-home-cache-excludes" => "caches/build-cache-1"}
    raise "fixture builds must retain pinned XcodeGen setup" unless
        xcodegen.fetch("run").lines.map(&:strip) == [
            'xcodegen_bin_dir="$(scripts/install-xcodegen.sh "$RUNNER_TEMP/p2pkit-xcodegen")"',
            'echo "$xcodegen_bin_dir" >> "$GITHUB_PATH"',
        ]
    raise "fixture builds must install Android SDKs before the inventory" unless sdk["name"] == "Install Android SDK platforms"
    raise "preflight must execute every original script without wrappers or ignored failures" unless
        test["id"] == "repository-tests" && test.fetch("run").lines.map(&:strip) == COMMANDS

    gate = jobs.fetch("complete-gate")
    raise "required gate must depend on both independent check jobs" unless
        gate["needs"] == ["jvm-library-checks", JOB]
    raise "required gate must run its failure guards, without extending its budget" unless
        gate["if"] == "${{ always() }}" && gate["timeout-minutes"] == 60 && !gate.key?("continue-on-error")
    guard = gate.fetch("steps")[1]
    raise "required gate must reject failed, cancelled or skipped preflight before any build" unless
        guard["id"] == "require-repository-checks" && guard["shell"] == "bash" && guard["run"] == GUARD &&
        guard["env"] == {"REPOSITORY_CHECK_RESULT" => "${{ needs.repository-checks.result }}"} &&
        !guard.key?("if") && !guard.key?("continue-on-error")
    # Existing full platform, API, UI and publication tests retain their own
    # policy checks. This split must leave the actual ABI graph on the build host.
    abi = gate.fetch("steps").select { |step| step["name"] == "Verify Android ABI graph" }
    raise "full ABI graph must remain blocking on the platform runner" unless abi.length == 1 &&
        abi.first["run"].strip == "scripts/check-android-abi-guard.sh" &&
        abi.first["if"] == "steps.scope.outputs.full == 'true'" && !abi.first.key?("continue-on-error")
end

workflow = YAML.safe_load(File.read(File.join(ROOT, ".github/workflows/ci.yml")), aliases: true)
check_preflight(workflow)
checks = 1
mutations = {
    "conditional prerequisite" => ->(w) { w["jobs"][JOB]["if"] = false },
    "ignored prerequisite" => ->(w) { w["jobs"][JOB]["continue-on-error"] = true },
    "dependent prerequisite" => ->(w) { w["jobs"][JOB]["needs"] = "complete-gate" },
    "different source" => ->(w) { w["jobs"][JOB]["steps"][0]["with"]["ref"] = "main" },
    "conditional checkout" => ->(w) { w["jobs"][JOB]["steps"][0]["if"] = false },
    "credentials retained" => ->(w) { w["jobs"][JOB]["steps"][0]["with"]["persist-credentials"] = true },
    "wrong host" => ->(w) { w["jobs"][JOB]["runs-on"] = "ubuntu-latest" },
    "extended preflight" => ->(w) { w["jobs"][JOB]["timeout-minutes"] = 90 },
    "extended build" => ->(w) { w["jobs"]["complete-gate"]["timeout-minutes"] = 120 },
    "missing prerequisite" => ->(w) { w["jobs"]["complete-gate"]["needs"] = ["jvm-library-checks"] },
    "skipped required gate" => ->(w) { w["jobs"]["complete-gate"].delete("if") },
    "missing result guard" => ->(w) { w["jobs"]["complete-gate"]["steps"].delete_at(1) },
    "conditional result guard" => ->(w) { w["jobs"]["complete-gate"]["steps"][1]["if"] = false },
    "forged result" => ->(w) { w["jobs"]["complete-gate"]["steps"][1]["env"]["REPOSITORY_CHECK_RESULT"] = "success" },
    "ignored result" => ->(w) { w["jobs"]["complete-gate"]["steps"][1]["run"] += " || true" },
    "ignored inventory" => ->(w) { w["jobs"][JOB]["steps"][5]["continue-on-error"] = true },
    "ignored graph" => ->(w) {
        w["jobs"]["complete-gate"]["steps"].find { |s| s["name"] == "Verify Android ABI graph" }["run"] += " || true"
    },
}
COMMANDS.each do |command|
    mutations["missing #{command}"] = ->(w) do
        w["jobs"][JOB]["steps"][5]["run"] = COMMANDS.reject { |value| value == command }.join("\n") + "\n"
    end
end
mutations.each do |name, mutate|
    copy = Marshal.load(Marshal.dump(workflow))
    mutate.call(copy)
    rejected = false
    begin
        check_preflight(copy)
    rescue RuntimeError
        rejected = true
    end
    raise "unsafe preflight accepted: #{name}" unless rejected
    checks += 1
end

%w[success failure cancelled skipped unknown].push("").each do |result|
    _stdout, _stderr, status = Open3.capture3({"REPOSITORY_CHECK_RESULT" => result}, "bash", "-c", GUARD)
    raise "result guard misclassified #{result.inspect}" unless status.success? == (result == "success")
    checks += 1
end
release_test = File.read(File.join(ROOT, "scripts/tests/release-workflow-test.sh"))
raise "preflight regression is not wired into release tooling" unless release_test.lines.any? do |line|
    line.strip == 'ruby "$ROOT/scripts/tests/check-ci-preflight-policy-test.rb"'
end
puts "RESULT: PASS — #{checks} same-source preflight inventory and fail-closed dependency controls"
