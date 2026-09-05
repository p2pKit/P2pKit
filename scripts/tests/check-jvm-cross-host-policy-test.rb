#!/usr/bin/env ruby
require "yaml"
require "shellwords"

JVM_JOB = "jvm-library-checks"
MATRIX = [
    {"os" => "ubuntu-latest", "wrapper" => "./gradlew"},
    {"os" => "windows-latest", "wrapper" => '.\gradlew.bat'},
].freeze
TASKS = %w[:p2p-core:jvmTest :p2p-transport-lan:jvmTest :p2p-network-provisioning-desktop:test].freeze
ARGUMENTS = ["./gradlew", "--no-daemon", *TASKS, "--continue", "--no-build-cache",
             "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain"].freeze
REPORTS = [
    ["p2p-core", "jvmTest"], ["p2p-transport-lan", "jvmTest"], ["p2p-network-provisioning-desktop", "test"],
].flat_map do |mod, task|
    ["library/#{mod}/build/test-results/#{task}/**", "library/#{mod}/build/reports/tests/#{task}/**"]
end.freeze
ALWAYS = "${{ always() }}"
WRAPPER = "${{ matrix.wrapper }}"
GUARD = 'test "$JVM_CHECK_RESULT" = success'

def check_jvm_coverage(workflow)
    triggers = workflow.fetch("on") { workflow.fetch(true) }
    raise "JVM checks require unfiltered pull requests" unless
        triggers.key?("pull_request") && [nil, {}].include?(triggers["pull_request"])
    raise "JVM checks require main pushes and manual runs" unless
        triggers.fetch("push").fetch("branches") == ["main"] && triggers.key?("workflow_dispatch")

    jobs = workflow.fetch("jobs")
    jvm = jobs.fetch(JVM_JOB)
    raise "JVM checks must use native runner defaults" if workflow.key?("defaults") || jvm.key?("defaults")
    raise "JVM matrix must run unconditionally" if jvm.key?("if") || jvm.key?("continue-on-error")
    raise "both host results must be retained" unless jvm.fetch("strategy").fetch("fail-fast") == false
    raise "JVM matrix must use both native host shells/wrappers" unless
        jvm.fetch("strategy").fetch("matrix") == {"include" => MATRIX}
    raise "JVM matrix host is not selected" unless jvm.fetch("runs-on") == "${{ matrix.os }}"
    steps = jvm.fetch("steps")
    raise "JVM steps cannot ignore failures" if steps.any? { |step| step.key?("continue-on-error") }
    by_id = ->(id) { steps.find { |step| step["id"] == id } || raise("missing #{id}") }
    tests = by_id.call("library-tests")
    raise "library tests cannot be conditional" if tests.key?("if")
    raise "library tests must use the native runner shell" if tests.key?("shell")
    command = tests.fetch("run").sub(WRAPPER, "./gradlew")
    raise "JVM command must execute all suites with strict, bounded, uncached verification" unless
        tests.fetch("run").start_with?(WRAPPER + " ") && Shellwords.split(command) == ARGUMENTS

    stop = by_id.call("stop-gradle")
    raise "Gradle must stop even after failure" unless
        stop["if"] == ALWAYS && !stop.key?("shell") && stop["run"] == WRAPPER + " --stop"
    reports = by_id.call("library-reports")
    raise "JVM reports must upload even after failure" unless reports["if"] == ALWAYS &&
        reports.fetch("uses").start_with?("actions/upload-artifact@")
    inputs = reports.fetch("with")
    raise "JVM evidence must be host/attempt-specific" unless
        inputs.fetch("name") == "jvm-library-tests-${{ matrix.os }}-${{ github.run_attempt }}"
    raise "all library XML/HTML reports must be retained" unless inputs.fetch("path").split.sort == REPORTS.sort
    raise "JVM report retention changed" unless inputs.fetch("retention-days") == 7
    raise "stop/reports must follow the tests" unless
        steps.index(tests) < steps.index(stop) && steps.index(stop) < steps.index(reports)

    gate = jobs.fetch("complete-gate")
    raise "required gate must wait for the JVM matrix" unless Array(gate.fetch("needs")) == [JVM_JOB]
    raise "required gate must reject failed/skipped dependencies, not silently skip" unless gate["if"] == ALWAYS
    guard = gate.fetch("steps").first
    raise "required gate must first require matrix success" unless
        guard["id"] == "require-jvm-checks" && guard["shell"] == "bash" && guard["run"] == GUARD &&
        guard.fetch("env").fetch("JVM_CHECK_RESULT") == "${{ needs.jvm-library-checks.result }}" &&
        !guard.key?("if") && !guard.key?("continue-on-error") && !gate.key?("continue-on-error")
end

path = ARGV.fetch(0, File.expand_path("../../.github/workflows/ci.yml", __dir__))
workflow = YAML.safe_load(File.read(path), aliases: true)
check_jvm_coverage(workflow)
checks = 1
mutations = {
    "missing job" => ->(w) { w["jobs"].delete(JVM_JOB) },
    "missing Windows" => ->(w) { w["jobs"][JVM_JOB]["strategy"]["matrix"]["include"].pop },
    "missing Linux" => ->(w) { w["jobs"][JVM_JOB]["strategy"]["matrix"]["include"].shift },
    "non-native Windows wrapper" => ->(w) {
        w["jobs"][JVM_JOB]["strategy"]["matrix"]["include"][1]["wrapper"] = "./gradlew"
    },
    "fail fast" => ->(w) { w["jobs"][JVM_JOB]["strategy"]["fail-fast"] = true },
    "conditional matrix" => ->(w) { w["jobs"][JVM_JOB]["if"] = false },
    "non-native default shell" => ->(w) { w["defaults"] = {"run" => {"shell" => "bash"}} },
    "ignored job failure" => ->(w) { w["jobs"][JVM_JOB]["continue-on-error"] = true },
    "missing gate dependency" => ->(w) { w["jobs"]["complete-gate"].delete("needs") },
    "skipped required gate" => ->(w) { w["jobs"]["complete-gate"].delete("if") },
    "ignored required gate failure" => ->(w) { w["jobs"]["complete-gate"]["continue-on-error"] = true },
    "misplaced result guard" => ->(w) { w["jobs"]["complete-gate"]["steps"].rotate! },
    "successful failure guard" => ->(w) { w["jobs"]["complete-gate"]["steps"][0]["run"] += " || true" },
    "conditional guard" => ->(w) { w["jobs"]["complete-gate"]["steps"][0]["if"] = false },
    "wrong result" => ->(w) { w["jobs"]["complete-gate"]["steps"][0]["env"]["JVM_CHECK_RESULT"] = "success" },
}
TASKS.each do |task|
    mutations["missing #{task}"] = ->(w) {
        w["jobs"][JVM_JOB]["steps"].find { |s| s["id"] == "library-tests" }["run"].sub!(task, "")
    }
end
{
    "library-tests" => {"if" => false, "continue-on-error" => true, "shell" => "bash",
                        "run" => "echo #{WRAPPER} #{ARGUMENTS.drop(1).join(' ')}"},
    "stop-gradle" => {"if" => "${{ success() }}", "run" => "echo stopped"},
    "library-reports" => {"if" => "${{ success() }}"},
}.each do |id, fields|
    fields.each do |key, value|
        mutations["#{id} #{key}"] = ->(w) { w["jobs"][JVM_JOB]["steps"].find { |s| s["id"] == id }[key] = value }
    end
end
[" --tests '*subset*'", " -x :p2p-core:jvmTest", " --dependency-verification off", " || true"].each do |suffix|
    mutations["unsafe command #{suffix}"] = ->(w) {
        w["jobs"][JVM_JOB]["steps"].find { |s| s["id"] == "library-tests" }["run"] += suffix
    }
end
mutations["missing report"] = ->(w) {
    w["jobs"][JVM_JOB]["steps"].find { |s| s["id"] == "library-reports" }["with"]["path"] = REPORTS.drop(1).join("\n")
}
mutations["filtered PRs"] = ->(w) {
    triggers = w.fetch("on") { w.fetch(true) }
    triggers["pull_request"] = {"paths" => ["library/**"]}
}
mutations.each do |name, mutate|
    copy = Marshal.load(Marshal.dump(workflow))
    mutate.call(copy)
    rejected = false
    begin
        check_jvm_coverage(copy)
    rescue KeyError, RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe JVM policy accepted: #{name}" unless rejected
    checks += 1
end
puts "RESULT: PASS — required Linux/Windows JVM coverage (#{checks} regression checks)"
