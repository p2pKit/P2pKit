#!/usr/bin/env ruby
require "yaml"
require "json"
require "shellwords"

ROOT = File.expand_path("../..", __dir__)
FULL = "needs.repository-checks.outputs.full == 'true'"
ALWAYS_FULL = "${{ always() && needs.repository-checks.outputs.full == 'true' }}"
ALWAYS = "${{ always() }}"
REPORT = "build/reports/platform-tests/**"
INTEL_NORMAL = "${{ github.event_name != 'workflow_dispatch' || inputs.diagnostics-only != true }}"
INTEL_DIAGNOSTIC = "${{ github.event_name == 'workflow_dispatch' && inputs.diagnostics-only == true }}"
INTEL_DIAGNOSTIC_INPUT = {
    "inputs" => {"diagnostics-only" => {
        "description" => "Read-only Intel Bonjour environment observations; NOT qualification",
        "type" => "boolean", "required" => false, "default" => false,
    }},
}.freeze
APPLE_FAILURE_REPORTS = %w[
    library/p2p-core/build/test-results/iosSimulatorArm64Test/**
    library/p2p-transport-lan/build/test-results/iosSimulatorArm64Test/**
    library/p2p-rpc/build/test-results/iosSimulatorArm64Test/**
    samples/p2p-sample-rpc/build/test-results/iosSimulatorArm64Test/**
].freeze
LAN_FAILURE_REPORTS = %w[
    library/p2p-transport-lan/build/test-results/jvmTest/**
    library/p2p-transport-lan/build/reports/jmdns-close/**
].freeze

def by_id(job, id)
    matches = job.fetch("steps").select { |step| step["id"] == id }
    raise "expected one #{id} step" unless matches.size == 1
    matches.first
end

def check_job(job, profile, scoped)
    raise "platform test failures cannot be ignored" if job.key?("continue-on-error")
    test = by_id(job, "platform-tests")
    raise "wrong platform-test invocation" unless
        Shellwords.split(test.fetch("run")) == ["python3", "scripts/run-platform-tests.py", profile]
    raise "platform tests cannot override execution context" if
        %w[continue-on-error env shell working-directory].any? { |key| test.key?(key) }
    raise "wrong platform-test condition" unless scoped ? test["if"] == FULL : !test.key?("if")

    stop = by_id(job, "stop-platform-gradle")
    evidence = by_id(job, "platform-reports")
    condition = scoped ? ALWAYS_FULL : ALWAYS
    [stop, evidence].each do |step|
        raise "platform cleanup/evidence must run after failure" unless step["if"] == condition
        raise "platform cleanup/evidence cannot ignore failure" if step.key?("continue-on-error")
    end
    raise "must stop the applicable Gradle wrapper" unless stop["run"] == "./gradlew --stop"
    raise "test execution reports must be uploaded" unless
        evidence.fetch("uses").start_with?("actions/upload-artifact@") &&
        evidence.fetch("with").fetch("path").split.include?(REPORT)
    paths = evidence.fetch("with").fetch("path").split
    raise "report exclusions are not allowed" if paths.any? { |path| path.start_with?("!") }
    if profile == "full"
        raise "full gate must retain Apple failure details, not only task totals" unless
            (APPLE_FAILURE_REPORTS - paths).empty?
        raise "full gate must retain native LAN failures, not only task totals" unless
            (LAN_FAILURE_REPORTS - paths).empty?
    end
    if profile == "ios-x64"
        %w[library/p2p-core library/p2p-transport-lan library/p2p-rpc samples/p2p-sample-rpc].each do |project|
            raise "missing Intel XML evidence" unless paths.include?("#{project}/build/test-results/iosX64Test/**")
        end
    end
    raise "platform evidence requires bounded retention" unless evidence.fetch("with")["retention-days"] == 7
    raise "early failure must not manufacture missing-report failure" unless
        evidence.fetch("with")["if-no-files-found"] == "warn"
    steps = job.fetch("steps")
    raise "platform test/cleanup/evidence order changed" unless
        steps.index(test) < steps.index(stop) && steps.index(stop) < steps.index(evidence)
end

def check_platform_policy(inputs)
    ci, intel, dry, publish, release = inputs.values_at(:ci, :intel, :dry, :publish, :release)
    check_job(ci.fetch("jobs").fetch("platform-checks"), "full", true)
    raise "Intel simulator validation must remain secret-free/read-only" unless
        intel.fetch("permissions") == {"contents" => "read"} && !JSON.generate(intel).include?("secrets.")
    triggers = intel.fetch("on") { intel.fetch(true) }
    raise "Intel coverage needs default manual/weekly tests and an explicit optional read-only diagnostic" unless
        triggers.keys.sort == %w[schedule workflow_dispatch] &&
        triggers["workflow_dispatch"] == INTEL_DIAGNOSTIC_INPUT &&
        triggers["schedule"] == [{"cron" => "27 3 * * 1"}]
    raise "Intel test invocations must not overlap" unless
        intel.fetch("concurrency") == {"group" => "ios-x64-tests-${{ github.ref }}", "cancel-in-progress" => false}
    job = intel.fetch("jobs").fetch("ios-x64")
    raise "Intel job must run on a native Intel Mac" unless job["runs-on"] == "macos-15-intel"
    raise "Intel normal tests require the exact default-on guard and no protection change" unless
        job["if"] == INTEL_NORMAL && !job.key?("environment")
    raise "Intel job needs a bounded timeout" unless job["timeout-minutes"] == 40
    java = job.fetch("steps").find { |step| step.fetch("uses", "").start_with?("actions/setup-java@") }
    raise "Intel job requires JDK 17" unless java && java.fetch("with")["java-version"] == "17"
    check_job(job, "ios-x64", false)
    raise "Intel tests and diagnostics must remain separate jobs" unless
        intel.fetch("jobs").keys.sort == %w[intel-environment-diagnostics ios-x64]
    diagnostic = intel.fetch("jobs").fetch("intel-environment-diagnostics")
    raise "Intel diagnostics must be explicit, bounded and non-qualifying" unless
        diagnostic["if"] == INTEL_DIAGNOSTIC && diagnostic["runs-on"] == "macos-15-intel" &&
        diagnostic["timeout-minutes"] == 5 && !diagnostic.key?("environment") &&
        !diagnostic.key?("continue-on-error") && diagnostic["name"].include?("NOT QUALIFICATION")
    diagnostic_steps = diagnostic.fetch("steps")
    raise "Intel diagnostic cannot substitute product tests or acquire tools" unless
        diagnostic_steps.size == 4 && diagnostic_steps.map { |step| step["run"] }.compact == [
            "python3 -I -S -B scripts/tests/intel-bonjour-environment-test.py",
            "python3 -I -S -B scripts/diagnose-intel-bonjour-environment.py",
        ] && diagnostic_steps.none? { |step| step.key?("continue-on-error") }
    diagnostic_report = diagnostic_steps.last
    raise "Intel diagnostic observations must not be relabeled as test evidence" unless
        diagnostic_report["if"] == ALWAYS &&
        diagnostic_report.fetch("with")["path"] == "${{ runner.temp }}/rpc-intel-bonjour-diagnostic.json" &&
        diagnostic_report.fetch("with")["name"] == "intel-bonjour-diagnostic-${{ github.sha }}-${{ github.run_attempt }}"
    {dry => ["local-release", "Upload local release evidence"],
     publish => ["verify-release", "Upload verification evidence"]}.each do |workflow, names|
        steps = workflow.fetch("jobs").fetch(names[0]).fetch("steps")
        caller = steps.find { |step| step["run"] == "scripts/run-release-gate.sh" }
        raise "release caller must not bypass the platform gate" unless caller && !caller.key?("continue-on-error")
        upload = steps.find { |step| step["name"] == names[1] }
        raise "release caller must preserve execution evidence on failure" unless upload &&
            upload["if"] == "always()" && upload.fetch("with").fetch("path").split.include?(REPORT)
    end
    lines = release.lines.map(&:strip)
    raise "release gate must enforce shell failures" unless lines.include?("set -euo pipefail")
    %w[check-platform-test-policy-test.rb run-platform-tests-test.py].each do |script|
        interpreter = script.end_with?(".rb") ? "ruby" : "python3"
        raise "release gate must execute #{script}" unless lines.include?("#{interpreter} scripts/tests/#{script}")
    end
    raise "release gate must run the same full platform driver" unless
        lines.count("python3 scripts/run-platform-tests.py full") == 1
end

inputs = {
    ci: "ci.yml", intel: "ios-x64-tests.yml", dry: "release-dry-run.yml", publish: "publish-maven-central.yml",
}.transform_values { |name| YAML.safe_load(File.read(File.join(ROOT, ".github/workflows", name)), aliases: true) }
inputs[:release] = File.read(File.join(ROOT, "scripts/run-release-gate.sh"))
check_platform_policy(inputs)
mutations = {
    "raw check bypass" => ->(v) { by_id(v[:ci]["jobs"]["platform-checks"], "platform-tests")["run"] = "./gradlew check" },
    "echo instead of execution" => ->(v) {
        by_id(v[:ci]["jobs"]["platform-checks"], "platform-tests")["run"] = "echo python3 scripts/run-platform-tests.py full"
    },
    "missing full report" => ->(v) {
        v[:ci]["jobs"]["platform-checks"]["steps"].delete(by_id(v[:ci]["jobs"]["platform-checks"], "platform-reports"))
    },
    "arm64 instead of Intel" => ->(v) { v[:intel]["jobs"]["ios-x64"]["runs-on"] = "macos-latest" },
    "Intel job disabled" => ->(v) { v[:intel]["jobs"]["ios-x64"]["if"] = false },
    "Intel default diagnostic instead of tests" => ->(v) {
        (v[:intel]["on"] || v[:intel][true])["workflow_dispatch"]["inputs"]["diagnostics-only"]["default"] = true
    },
    "Intel implicit diagnostic default" => ->(v) {
        (v[:intel]["on"] || v[:intel][true])["workflow_dispatch"]["inputs"]["diagnostics-only"].delete("default")
    },
    "Intel mandatory diagnostic input" => ->(v) {
        (v[:intel]["on"] || v[:intel][true])["workflow_dispatch"]["inputs"]["diagnostics-only"]["required"] = true
    },
    "Intel untyped diagnostic input" => ->(v) {
        (v[:intel]["on"] || v[:intel][true])["workflow_dispatch"]["inputs"]["diagnostics-only"]["type"] = "string"
    },
    "Intel weekly coverage disabled" => ->(v) {
        v[:intel]["jobs"]["ios-x64"]["if"] = "${{ github.event_name == 'workflow_dispatch' }}"
    },
    "Intel normal guard inverted" => ->(v) { v[:intel]["jobs"]["ios-x64"]["if"] = INTEL_DIAGNOSTIC },
    "Intel diagnostic guard inverted" => ->(v) {
        v[:intel]["jobs"]["intel-environment-diagnostics"]["if"] = INTEL_NORMAL
    },
    "Intel diagnostic always runs" => ->(v) {
        v[:intel]["jobs"]["intel-environment-diagnostics"].delete("if")
    },
    "Intel product replaced with diagnostic" => ->(v) {
        by_id(v[:intel]["jobs"]["ios-x64"], "platform-tests")["run"] =
            "python3 -I -S -B scripts/diagnose-intel-bonjour-environment.py"
    },
    "Intel diagnostic executes product" => ->(v) {
        v[:intel]["jobs"]["intel-environment-diagnostics"]["steps"][2]["run"] =
            "python3 scripts/run-platform-tests.py ios-x64"
    },
    "Intel diagnostic mislabels evidence" => ->(v) {
        v[:intel]["jobs"]["intel-environment-diagnostics"]["steps"].last["with"]["path"] = REPORT
    },
    "missing Intel schedule" => ->(v) { (v[:intel]["on"] || v[:intel][true]).delete("schedule") },
    "ignored Intel failures" => ->(v) { v[:intel]["jobs"]["ios-x64"]["continue-on-error"] = true },
    "wrong Intel profile" => ->(v) {
        by_id(v[:intel]["jobs"]["ios-x64"], "platform-tests")["run"] = "python3 scripts/run-platform-tests.py full"
    },
    "raw release check" => ->(v) { v[:release].sub!("python3 scripts/run-platform-tests.py full", "./gradlew check") },
    "ignored release failure" => ->(v) { v[:release].sub!("python3 scripts/run-platform-tests.py full",
                                                                         "python3 scripts/run-platform-tests.py full || true") },
    "missing release policy" => ->(v) { v[:release].sub!("ruby scripts/tests/check-platform-test-policy-test.rb", "true") },
    "missing release regression" => ->(v) { v[:release].sub!("python3 scripts/tests/run-platform-tests-test.py", "true") },
}
(APPLE_FAILURE_REPORTS + LAN_FAILURE_REPORTS).each do |report|
    mutations["missing native failure evidence #{report}"] = ->(v) do
        by_id(v[:ci]["jobs"]["platform-checks"], "platform-reports")["with"]["path"].sub!(report, "")
    end
end
{ci: "platform-checks", intel: "ios-x64"}.each do |workflow, job|
    %w[platform-tests stop-platform-gradle platform-reports].each do |id|
        mutations["#{workflow} ignored #{id}"] = ->(v) { by_id(v[workflow]["jobs"][job], id)["continue-on-error"] = true }
        mutations["#{workflow} conditional #{id}"] = ->(v) { by_id(v[workflow]["jobs"][job], id)["if"] = "success()" }
    end
    mutations["#{workflow} missing evidence path"] = ->(v) {
        by_id(v[workflow]["jobs"][job], "platform-reports")["with"]["path"] = "build/reports/unrelated/**"
    }
    mutations["#{workflow} missing stop"] = ->(v) {
        by_id(v[workflow]["jobs"][job], "stop-platform-gradle")["run"] = "echo stopped"
    }
end
{dry: "local-release", publish: "verify-release"}.each do |workflow, job|
    mutations["#{workflow} missing platform evidence"] = ->(v) {
        v[workflow]["jobs"][job]["steps"].each do |step|
            step["with"]["path"] = step["with"]["path"].sub(REPORT, "") if step.fetch("with", {}).key?("path")
        end
    }
end
mutations.each do |name, mutate|
    altered = Marshal.load(Marshal.dump(inputs))
    mutate.call(altered)
    rejected = false
    begin
        check_platform_policy(altered)
    rescue KeyError, RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe platform-test policy accepted: #{name}" unless rejected
end
puts "RESULT: PASS — platform test callers/evidence (#{mutations.size + 1} policy checks)"
