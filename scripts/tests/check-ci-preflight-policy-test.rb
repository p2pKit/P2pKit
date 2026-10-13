#!/usr/bin/env ruby
require "yaml"
require "open3"

ROOT = File.expand_path("../..", __dir__)
JOB = "repository-checks"
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

WORKERS = {"ios-checks" => 30, "platform-checks" => 60, "artifact-checks" => 60}.freeze
REQUIRED = ["jvm-library-checks", JOB, *WORKERS.keys].freeze
FULL = "needs.repository-checks.outputs.full == 'true'"
SCOPE_GUARD = <<~'BASH'
    case "$FULL_SCOPE" in true|false) ;; *) exit 1 ;; esac
    test "$SOURCE_SHA" = "$GITHUB_SHA"
    test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
BASH
RESULT_VARS = %w[JVM_CHECK_RESULT REPOSITORY_CHECK_RESULT IOS_CHECKS_RESULT PLATFORM_CHECKS_RESULT ARTIFACT_CHECKS_RESULT].freeze
SCOPE_ENV = {
    "FULL_SCOPE" => "${{ needs.repository-checks.outputs.full }}",
    "SOURCE_SHA" => "${{ needs.repository-checks.outputs.head }}",
}.freeze
PHASE_COMMANDS = {
    "ios-checks" => {
        "Verify iOS entry points" => <<~'BASH',
            python3 scripts/tests/ios-project-generation-test.py
            source scripts/run-ios-app.sh
            device_json="$(xcrun simctl list -j devices available)"
            SIM_UDID="$(select_latest_available_simulator_udid "iPhone 17" "$device_json")"
            export SIM_UDID
            echo "Selected exact iOS simulator UDID: $SIM_UDID"
            scripts/run-ios-ui-tests.sh
            scripts/tests/run-ios-app-test.sh
        BASH
    },
    "platform-checks" => {"Run complete module and platform checks" => "python3 scripts/run-platform-tests.py full"},
    "artifact-checks" => {
        "Verify Android ABI graph" => "scripts/check-android-abi-guard.sh",
        "Verify API, documentation, and SBOM" => <<~'BASH',
            ./gradlew :p2p-core:checkKotlinAbi :p2p-transport-lan:checkKotlinAbi :p2p-rpc:checkKotlinAbi :p2p-network-provisioning-android:checkKotlinAbi :p2p-network-provisioning-desktop:checkKotlinAbi :p2p-core:checkAndroidAbi :p2p-transport-lan:checkAndroidAbi :p2p-network-provisioning-android:checkAndroidAbi :p2p-rpc:checkAndroidAbi --console=plain
            ./gradlew :p2p-core:dokkaGeneratePublicationHtml :p2p-transport-lan:dokkaGeneratePublicationHtml :p2p-rpc:dokkaGeneratePublicationHtml :p2p-network-provisioning-android:dokkaGeneratePublicationHtml :p2p-network-provisioning-desktop:dokkaGeneratePublicationHtml --console=plain
            scripts/check-sbom.sh
        BASH
        "Verify local release artifacts and consumers" => <<~'BASH',
            scripts/check-publish-artifacts.sh
            scripts/check-published-consumers.sh
            ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance --console=plain
            scripts/check-xcframework-minimum-os.sh
        BASH
    },
}.freeze

def one_step(job, name)
    steps = job.fetch("steps").select { |step| step["name"] == name }
    raise "missing/duplicate step #{name}" unless steps.length == 1
    steps.first
end

def check_preflight(workflow)
    raise "CI cannot override global execution" if %w[env defaults].any? { |key| workflow.key?(key) }
    jobs = workflow.fetch("jobs")
    REQUIRED.each do |name|
        job = jobs.fetch(name)
        raise "required jobs cannot skip, ignore failure or override execution" if
            %w[if continue-on-error defaults env container services].any? { |key| job.key?(key) }
        job.fetch("steps").each do |step|
            raise "required steps cannot ignore failure" if step.key?("continue-on-error")
        end
        checkout = job.fetch("steps").first
        raise "all checkouts must bind immutable workflow source" unless
            checkout.fetch("uses").start_with?("actions/checkout@") &&
            checkout.fetch("with")["ref"] == "${{ github.sha }}" &&
            checkout.fetch("with")["persist-credentials"] == false && !checkout.key?("if")
    end
    job = jobs.fetch(JOB)
    raise "preflight must run independently" if job.key?("needs")
    raise "preflight must retain supported host and bounded budget" unless
        job["runs-on"] == "macos-latest" && job["timeout-minutes"] == 30
    raise "scope outputs must bind exact resolver outputs" unless job["outputs"] ==
        %w[full base head].to_h { |key| [key, "${{ steps.scope.outputs.#{key} }}"] }
    test = one_step(job, "Verify repository script and policy entry points")
    raise "preflight must execute every original script unconditionally" unless
        test["id"] == "repository-tests" && test.fetch("run").lines.map(&:strip) == COMMANDS &&
        !%w[if env shell working-directory].any? { |key| test.key?(key) }

    {JOB => nil}.merge(WORKERS.transform_values { FULL }).each do |name, condition|
        job = jobs.fetch(name)
        java = one_step(job, "Configure Java 17")
        gradle = one_step(job, "Validate wrapper and configure Gradle")
        xcodegen = one_step(job, "Install pinned XcodeGen")
        sdk = one_step(job, "Install Android SDK platforms")
        [java, gradle, xcodegen, sdk].each do |step|
            raise "tool setup cannot be bypassed or overridden" unless step["if"] == condition &&
                !%w[env shell working-directory].any? { |key| step.key?(key) }
        end
        raise "every build must use JDK17" unless java.fetch("uses").start_with?("actions/setup-java@") &&
            java["with"] == {"distribution" => "temurin", "java-version" => "17"}
        raise "every build must exclude Gradle build caches" unless
            gradle.fetch("uses").start_with?("gradle/actions/setup-gradle@") &&
            gradle["with"] == {"gradle-home-cache-excludes" => "caches/build-cache-1"}
        raise "every build must retain pinned XcodeGen" unless xcodegen.fetch("run").lines.map(&:strip) == [
            'xcodegen_bin_dir="$(scripts/install-xcodegen.sh "$RUNNER_TEMP/p2pkit-xcodegen")"',
            'echo "$xcodegen_bin_dir" >> "$GITHUB_PATH"',
        ]
        steps = job.fetch("steps")
        first_build = steps.index(one_step(job, name == JOB ? test["name"] : PHASE_COMMANDS.fetch(name).keys.first))
        raise "setup must precede execution" unless [java, gradle, xcodegen, sdk].all? { |s| steps.index(s) < first_build }
    end

    WORKERS.each do |name, timeout|
        job = jobs.fetch(name)
        raise "worker must depend on same-source preflight, with bounded execution" unless
            job["needs"] == JOB && job["runs-on"] == "macos-latest" && job["timeout-minutes"] == timeout
        scope = job.fetch("steps")[1]
        raise "worker must validate scope and checkout before any tools or tests" unless
            scope == {"name" => "Validate same-source scope", "id" => "validate-scope", "shell" => "bash",
                      "env" => SCOPE_ENV, "run" => SCOPE_GUARD}
        PHASE_COMMANDS.fetch(name).each do |label, command|
            step = one_step(job, label)
            raise "required phase changed, skipped or overridden: #{label}" unless
                step.fetch("run").strip == command.strip && step["if"] == FULL &&
                !%w[env shell working-directory].any? { |key| step.key?(key) }
        end
    end
    gate = jobs.fetch("complete-gate")
    raise "aggregate must wait for all required jobs and run on failures" unless
        gate["needs"] == REQUIRED && gate["if"] == "${{ always() }}" &&
        gate["runs-on"] == "ubuntu-latest" && gate["timeout-minutes"] == 5 &&
        !%w[continue-on-error defaults env container services].any? { |key| gate.key?(key) }
    guards = gate.fetch("steps")
    raise "aggregate must contain exactly five result guards" unless guards.length == REQUIRED.length
    REQUIRED.zip(RESULT_VARS).each_with_index do |(name, var), index|
        guard = guards[index]
        id = name == "jvm-library-checks" ? "require-jvm-checks" : "require-#{name}"
        raise "aggregate must reject every nonsuccess result: #{name}" unless
            guard.reject { |key, _| key == "name" } == {
                "id" => id, "shell" => "bash", "env" => {var => "${{ needs.#{name}.result }}"},
                "run" => "test \"$#{var}\" = success",
            }
    end
end

workflow = YAML.safe_load(File.read(File.join(ROOT, ".github/workflows/ci.yml")), aliases: true)
check_preflight(workflow)
mutations = {
    "dependent preflight" => ->(w) { w["jobs"][JOB]["needs"] = "complete-gate" },
    "missing scope output" => ->(w) { w["jobs"][JOB]["outputs"].delete("full") },
    "forged scope" => ->(w) { w["jobs"][JOB]["outputs"]["full"] = "false" },
    "PR head instead of merge" => ->(w) { w["jobs"][JOB]["outputs"]["head"] = "${{ github.event.pull_request.head.sha }}" },
    "conditional aggregate" => ->(w) { w["jobs"]["complete-gate"]["if"] = "success()" },
    "ignored aggregate" => ->(w) { w["jobs"]["complete-gate"]["continue-on-error"] = true },
    "extra aggregate guard" => ->(w) { w["jobs"]["complete-gate"]["steps"] << {"run" => "true"} },
}
REQUIRED.each_with_index do |name, index|
    mutations["missing #{name} dependency"] = ->(w) { w["jobs"]["complete-gate"]["needs"].delete(name) }
    %w[if continue-on-error env].each do |field|
        mutations["#{name} #{field}"] = ->(w) { w["jobs"][name][field] = false }
    end
    mutations["#{name} mutable checkout"] = ->(w) { w["jobs"][name]["steps"][0]["with"]["ref"] = "main" }
    mutations["#{name} forged success"] = ->(w) do
        w["jobs"]["complete-gate"]["steps"][index]["env"][RESULT_VARS[index]] = "success"
    end
    {"if" => false, "continue-on-error" => true, "run" => "true"}.each do |field, value|
        mutations["#{name} guard #{field}"] = ->(w) { w["jobs"]["complete-gate"]["steps"][index][field] = value }
    end
end
WORKERS.each_key do |name|
    mutations["#{name} extended timeout"] = ->(w) { w["jobs"][name]["timeout-minutes"] = 120 }
    mutations["#{name} missing scope validation"] = ->(w) { w["jobs"][name]["steps"].delete_at(1) }
    mutations["#{name} wrong scope source"] = ->(w) { w["jobs"][name]["steps"][1]["env"]["SOURCE_SHA"] = "main" }
    mutations["#{name} skipped validation"] = ->(w) { w["jobs"][name]["steps"][1]["if"] = FULL }
    PHASE_COMMANDS.fetch(name).each do |label, commands|
        commands.lines.each do |command|
            mutations["#{name} missing #{command.strip}"] = ->(w) do
                one_step(w["jobs"][name], label)["run"] = commands.lines.reject { |line| line == command }.join
            end
        end
        mutations["#{name} conditional #{label}"] = ->(w) { one_step(w["jobs"][name], label)["if"] = false }
    end
end
COMMANDS.each do |command|
    mutations["missing #{command}"] = ->(w) do
        one_step(w["jobs"][JOB], "Verify repository script and policy entry points")["run"] =
            COMMANDS.reject { |value| value == command }.join("\n") + "\n"
    end
end
mutations.each do |name, mutate|
    copy = Marshal.load(Marshal.dump(workflow))
    mutate.call(copy)
    rejected = false
    begin
        check_preflight(copy)
    rescue KeyError, RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe CI phase policy accepted: #{name}" unless rejected
end
checks = mutations.size + 1
# Execute actual YAML guards, including every predecessor failing independently.
base_env = RESULT_VARS.to_h { |var| [var, "success"] }
command = workflow["jobs"]["complete-gate"]["steps"].map { |s| s.fetch("run") }.join("\n")
RESULT_VARS.each do |var|
    %w[success failure cancelled skipped unknown].push("").each do |result|
        _out, _err, status = Open3.capture3(base_env.merge(var => result), "bash", "--noprofile", "--norc", "-e", "-c", command)
        raise "aggregate misclassified #{var}=#{result.inspect}" unless status.success? == (result == "success")
        checks += 1
    end
end
sha, status = Open3.capture2("git", "rev-parse", "HEAD", chdir: ROOT)
raise "cannot bind scope regression source" unless status.success?
%w[true false invalid].push("").product([sha.strip, "different"]).each do |full, source|
    env = {"FULL_SCOPE" => full, "SOURCE_SHA" => source, "GITHUB_SHA" => sha.strip}
    _out, _err, status = Open3.capture3(env, "bash", "--noprofile", "--norc", "-e", "-c", SCOPE_GUARD, chdir: ROOT)
    expected = %w[true false].include?(full) && source == sha.strip
    raise "scope validation misclassified #{env}" unless status.success? == expected
    checks += 1
end
release_test = File.read(File.join(ROOT, "scripts/tests/release-workflow-test.sh"))
raise "phase policy regression is not wired into release tooling" unless release_test.lines.any? do |line|
    line.strip == 'ruby "$ROOT/scripts/tests/check-ci-preflight-policy-test.rb"'
end
puts "RESULT: PASS — #{checks} same-source phase inventory and fail-closed aggregate controls"
