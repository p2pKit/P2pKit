#!/usr/bin/env ruby
# Closed caller/source mutations only; no Gradle, provider, crypto or hosted execution.
require "yaml"
require_relative "../check-hosted-test-workflow-policy"

JVM_JOB = "jvm-library-checks"
MATRIX = [
    {"os" => "ubuntu-latest", "wrapper" => "./gradlew"},
    {"os" => "windows-latest", "wrapper" => '.\gradlew.bat'},
].freeze
TASKS = %w[:p2p-core:jvmTest :p2p-transport-lan:jvmTest :p2p-network-provisioning-desktop:test].freeze
REPORTS = [
    ["p2p-core", "jvmTest"], ["p2p-transport-lan", "jvmTest"], ["p2p-network-provisioning-desktop", "test"],
].flat_map do |mod, task|
    ["library/#{mod}/build/test-results/#{task}/**", "library/#{mod}/build/reports/tests/#{task}/**"]
end.freeze
ALWAYS = "${{ always() }}"
WRAPPER = "${{ matrix.wrapper }}"
GUARD = 'test "$JVM_CHECK_RESULT" = success'

def jvm_step(workflow, id)
    matches = workflow.fetch("jobs").fetch(JVM_JOB).fetch("steps").select { |step| step["id"] == id }
    raise "expected exactly one JVM step: #{id}" unless matches.length == 1
    matches.first
end

def check_jvm_coverage(workflow)
    triggers = workflow.fetch("on") { workflow.fetch(true) }
    raise "JVM checks require unfiltered pull requests" unless
        triggers.key?("pull_request") && [nil, {}].include?(triggers["pull_request"])
    raise "JVM checks require main pushes and manual runs" unless
        triggers.fetch("push").fetch("branches") == ["main"] && triggers.key?("workflow_dispatch")

    jobs = workflow.fetch("jobs")
    jvm = jobs.fetch(JVM_JOB)
    raise "whole JVM job must wait for initial-recipient admission" unless jvm["needs"] == HeavyJobQueuePolicy::ROUTING_NEEDS
    raise "whole JVM job must retain the exact real recipient-route and protected gate" unless
        HeavyJobQueuePolicy.routing_jobs("full").all? { |id, job| jobs[id] == job }
    raise "JVM checks must use native runner defaults" if workflow.key?("defaults") || jvm.key?("defaults")
    raise "JVM matrix must require the exact successful origin/gate pair, including before always-cleanup" unless
        jvm["if"] == HeavyJobQueuePolicy::JVM_CONDITION && !jvm.key?("continue-on-error")
    raise "both host results must be retained" unless jvm.fetch("strategy").fetch("fail-fast") == false
    raise "JVM matrix must use both native host shells/wrappers" unless
        jvm.fetch("strategy").fetch("matrix") == {"include" => MATRIX}
    raise "JVM matrix host is not selected" unless jvm.fetch("runs-on") == "${{ matrix.os }}"
    # The canonical controller now owns all three tasks, strict/no-cache argv,
    # original stop/retirement and six report roots. Their executable suppliers
    # remain pinned by check-hosted-test-composition and covered by the existing
    # hosted-jvm-library controls; YAML must not reintroduce a direct/raw path.
    HostedTestWorkflowPolicy.check_jvm(workflow)

    gate = jobs.fetch("complete-gate")
    raise "required gate must wait for the JVM matrix" unless gate.fetch("needs") == [JVM_JOB, *HeavyJobQueuePolicy::ROUTING_NEEDS]
    raise "required gate must reject failed/skipped dependencies, not silently skip" unless gate["if"] == ALWAYS
    guard = gate.fetch("steps").first
    raise "required gate must first require matrix success" unless
        guard["id"] == "require-jvm-checks" && guard["shell"] == "bash" && guard["run"] == GUARD &&
        guard.fetch("env").fetch("JVM_CHECK_RESULT") == "${{ needs.jvm-library-checks.result }}" &&
        !guard.key?("if") && !guard.key?("continue-on-error") && !gate.key?("continue-on-error")
    raise "required gate must then require exact recipient routing before checkout" unless
        gate.fetch("steps")[1] == HeavyJobQueuePolicy.routing_guard
end

path = ARGV.fetch(0, File.expand_path("../../.github/workflows/ci.yml", __dir__))
workflow = YAML.safe_load(File.read(path), aliases: true)
check_jvm_coverage(workflow)
checks = 1
mutations = {
    "missing job" => ->(w) { w["jobs"].delete(JVM_JOB) },
    "missing protected-gate prerequisite" => ->(w) { w["jobs"][JVM_JOB]["needs"].delete(HeavyJobQueuePolicy::INITIAL_JOB) },
    "missing source-route prerequisite" => ->(w) { w["jobs"][JVM_JOB]["needs"].delete(HeavyJobQueuePolicy::ROUTE_JOB) },
    "no whole-job initial prerequisite" => ->(w) { w["jobs"][JVM_JOB].delete("needs") },
    "wrong whole-job initial prerequisite" => ->(w) { w["jobs"][JVM_JOB]["needs"] = "other" },
    "ignored protected-gate failure" => ->(w) { w["jobs"]["initial-recipient-gate"]["continue-on-error"] = true },
    "conditional source routing" => ->(w) { w["jobs"]["recipient-route"]["if"] = false },
    "route receipt as authority" => ->(w) { w["jobs"]["recipient-route"]["steps"][-1]["run"] = "echo admitted\n" },
    "product before source routing" => ->(w) { w["jobs"]["recipient-route"]["steps"].unshift({"run" => "./gradlew help"}) },
    "source route requests protected environment" => ->(w) { w["jobs"]["recipient-route"]["environment"] = "initial-recipient-execution" },
    "protected gate takes heavy lease" => ->(w) { w["jobs"]["initial-recipient-gate"]["concurrency"] = "p2pkit-nonphysical-heavy" },
    "missing actual protected gate" => ->(w) { w["jobs"].delete("initial-recipient-gate") },
    "missing source route" => ->(w) { w["jobs"].delete("recipient-route") },
    "gate replaced by success echo" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][-1]["run"] = "echo approved" },
    "ordinary jobs request initial environment" => ->(w) { w["jobs"]["initial-recipient-gate"].delete("if") },
    "gate wrong protected environment" => ->(w) { w["jobs"]["initial-recipient-gate"]["environment"] = "sample-development-release" },
    "always cleanup runs after initial gate fails" => ->(w) { w["jobs"][JVM_JOB]["if"] = ALWAYS },
    "skipped route can run whole JVM job" => ->(w) { w["jobs"][JVM_JOB]["if"].sub!("needs.recipient-route.result == 'success'", "true") },
    "ordinary accepts successful initial gate" => ->(w) { w["jobs"][JVM_JOB]["if"].sub!("needs.initial-recipient-gate.result == 'skipped'", "needs.initial-recipient-gate.result == 'success'") },
    "route guard after checkout" => ->(w) {
        steps = w["jobs"]["complete-gate"]["steps"]
        steps[1], steps[2] = steps[2], steps[1]
    },
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
%w[ordinary initial].each do |origin|
    provider = origin == "ordinary" ? "dependency-stage" : "initial-dependency-stage"
    mutations["#{origin} provider omitted"] = ->(w) {
        w["jobs"][JVM_JOB]["steps"].delete(jvm_step(w, provider))
    }
    mutations["#{origin} provider uses a different profile"] = ->(w) {
        jvm_step(w, provider)["with"]["profile"] = "desktop"
    }
    mutations["#{origin} custody command selects a subset"] = ->(w) {
        jvm_step(w, "#{origin}-run")["run"].sub!(" --profile jvm-library",
            " --profile jvm-library --tests '*subset*'")
    }
    mutations["#{origin} custody loses original restore binding"] = ->(w) {
        jvm_step(w, "#{origin}-run")["env"].delete("P2PKIT_CACHE_RESTORATION_SHA256")
    }
    mutations["#{origin} separate seal omitted"] = ->(w) {
        w["jobs"][JVM_JOB]["steps"].delete(jvm_step(w, "#{origin}-seal"))
    }
    mutations["#{origin} unsealed raw report upload"] = ->(w) {
        jvm_step(w, "#{origin}-evidence")["with"]["path"] = REPORTS.join("\n")
    }
    mutations["#{origin} obsolete seven-day retention"] = ->(w) {
        jvm_step(w, "#{origin}-evidence")["with"]["retention-days"] = 7
    }
    mutations["#{origin} evidence lacks exact source and run attempt"] = ->(w) {
        jvm_step(w, "#{origin}-evidence")["with"]["name"] = "jvm-library-tests-${{ matrix.os }}"
    }
    mutations["#{origin} upload loses original window binding"] = ->(w) {
        jvm_step(w, "#{origin}-upload-after")["env"].delete("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256")
    }
    mutations["#{origin} provisional run result becomes acceptance"] = ->(w) {
        jvm_step(w, "#{origin}-required")["env"]["PROFILE_PASSED"] = "${{ steps.#{origin}-run.outputs.profile_passed }}"
    }
end
mutations["ordinary consume contract omitted"] = ->(w) {
    jvm_step(w, "ordinary-run")["run"].sub!(" --consume-dependencies", "")
}
mutations["initial current history omitted"] = ->(w) {
    jvm_step(w, "initial-run")["env"].delete("P2PKIT_INITIAL_CURRENT_HISTORY_SHA256")
}
mutations["direct Gradle bypasses native custody"] = ->(w) {
    w["jobs"][JVM_JOB]["steps"].insert(3, {"id" => "library-tests", "run" => "#{WRAPPER} #{TASKS.join(' ')}"})
}
mutations["direct shared-home stop"] = ->(w) {
    w["jobs"][JVM_JOB]["steps"] << {"id" => "stop-gradle", "if" => ALWAYS, "run" => WRAPPER + " --stop"}
}
mutations["Java setup before provider closure"] = ->(w) {
    steps = w["jobs"][JVM_JOB]["steps"]
    guard, java = steps.index(jvm_step(w, "dependency-ready")), steps.index(jvm_step(w, "java"))
    steps[guard], steps[java] = steps[java], steps[guard]
}
mutations["missing final recipient-origin result"] = ->(w) {
    w["jobs"][JVM_JOB]["steps"].delete(jvm_step(w, "recipient-result"))
}

mutations["filtered PRs"] = ->(w) {
    triggers = w.fetch("on") { w.fetch(true) }
    triggers["pull_request"] = {"paths" => ["library/**"]}
}
mutations.each do |name, mutate|
    copy = Marshal.load(Marshal.dump(workflow))
    mutate.call(copy)
    raise "JVM mutation had no effect: #{name}" if copy == workflow
    rejected = false
    begin
        check_jvm_coverage(copy)
    rescue KeyError, RuntimeError, ArgumentError, HostedTestWorkflowPolicy::Error
        rejected = true
    end
    raise "unsafe JVM policy accepted: #{name}" unless rejected
    checks += 1
end
puts "RESULT: PASS — required Linux/Windows JVM custody source policy (#{checks} regression checks; no hosted qualification)"
