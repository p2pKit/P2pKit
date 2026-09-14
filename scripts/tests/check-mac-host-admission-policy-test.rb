#!/usr/bin/env ruby
# Pure exact-workflow controls, not hosted/native admission or a dispatch.
require "json"
require_relative "../check-heavy-job-queue-policy"

module MacHostAdmissionPolicy
    ROOT = File.expand_path("../..", __dir__)
    JOB = "mac-host-admission-probe"
    OPERATIONS = %w[macos-arm64-admission macos-x64-admission].freeze
    RUBY_CHECK = "ruby scripts/tests/check-mac-host-admission-policy-test.rb"
    PYTHON_CHECK = "python3 -I -B -S scripts/tests/run-mac-host-admission-test.py"
    STEP_NAME = "Verify no-child Mac capacity policy"
    ENVIRONMENT = {
        "P2PKIT_OPERATION" => "${{ inputs.operation }}",
        "P2PKIT_EXPECTED_SHA" => "${{ inputs.expected_sha }}",
        "P2PKIT_EXPECTED_TREE" => "${{ inputs.expected_tree }}",
        "PYTHONDONTWRITEBYTECODE" => "1", "PYTHONUNBUFFERED" => "1",
    }.freeze
    STEPS = [
        {"name" => "Check out exact reviewed capacity source",
         "uses" => "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
         "with" => {"ref" => "${{ github.sha }}", "fetch-depth" => 0, "persist-credentials" => false}},
        {"name" => "Observe no-child Mac OS and capacity metadata", "id" => "snapshot",
         "timeout-minutes" => 2, "shell" => "bash",
         "run" => "exec python3 -I -B -S scripts/run-mac-host-admission.py run"},
        {"name" => "Validate exact public capacity evidence", "id" => "public", "if" => "${{ always() }}",
         "timeout-minutes" => 2, "shell" => "bash",
         "run" => "exec python3 -I -B -S scripts/run-mac-host-admission.py validate-public"},
        {"name" => "Retain nonprivate capacity metadata",
         "if" => "${{ always() && steps.public.outputs.artifacts_ready == 'true' }}",
         "uses" => "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
         "with" => {
             "name" => "mac-host-capacity-${{ inputs.operation }}-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
             "path" => "${{ runner.temp }}/p2pkit-mac-host-capacity-${{ github.run_id }}-${{ github.run_attempt }}",
             "retention-days" => 14, "if-no-files-found" => "error", "include-hidden-files" => false, "overwrite" => false}},
        {"name" => "Fail if safe capacity evidence is unavailable",
         "if" => "${{ always() && steps.public.outputs.artifacts_ready != 'true' }}", "shell" => "bash",
         "run" => "echo 'FATAL: no safe complete capacity evidence; no host admission claim' >&2\nexit 1\n"},
    ].freeze

    def self.need(condition, message)
        raise HeavyJobQueuePolicy::Error, message unless condition
    end

    def self.check(workflow)
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") &&
            !workflow.key?("defaults") && !JSON.generate(workflow).match?(/secrets\.|id-token|pull_request_target/),
            "capacity scope must remain secret-free and contents-read")
        triggers = workflow.fetch("on") { workflow.fetch(true) }
        inputs = triggers.fetch("workflow_dispatch").fetch("inputs")
        need(inputs.keys.sort == %w[expected_sha expected_tree operation], "capacity has exactly the existing three inputs")
        need(inputs.fetch("operation").fetch("options") == ["desktop", "windows-directory-fsync-control", *OPERATIONS],
            "capacity operation set changed")
        job = workflow.fetch("jobs").fetch(JOB)
        need(job.keys.sort == %w[concurrency env if name runs-on steps timeout-minutes], "unexpected Mac job authority")
        need(job["name"] == JOB && job["if"] == HeavyJobQueuePolicy::CONDITIONS[["desktop-cross-host.yml", JOB]] &&
            job["concurrency"] == HeavyJobQueuePolicy::QUEUE && job["timeout-minutes"] == 5 &&
            job["runs-on"] == "${{ inputs.operation == 'macos-arm64-admission' && 'macos-26' || 'macos-15-intel' }}",
            "fixed native role, dispatch guard, queue or deadline changed")
        need(job["env"] == ENVIRONMENT, "capacity has no extra credential/loader/command environment")
        need(job["steps"] == STEPS, "capacity steps must retain exact no-child, failure and public-evidence contracts")
    end

    def self.entrypoints(ci, release, workflow_test)
        steps = ci.fetch("jobs").fetch("complete-gate").fetch("steps")
        matches = steps.select { |step| step["name"] == STEP_NAME }
        need(matches == [{"name" => STEP_NAME, "run" => "#{RUBY_CHECK}\n#{PYTHON_CHECK}\n"}],
            "CI capacity controls must be unconditional and exact")
        scope = steps.find { |step| step["id"] == "scope" }
        need(scope && steps.index(matches.first) < steps.index(scope), "capacity controls must precede both CI scopes")
        [RUBY_CHECK, PYTHON_CHECK].each do |command|
            need(release.lines.map(&:strip).count(command) == 1, "release must execute each capacity control exactly once")
            interpreter, _, script = command.rpartition(" ")
            need(workflow_test.lines.map(&:strip).count("#{interpreter} \"$ROOT/#{script}\"") == 1,
                "release workflow controls must execute exact capacity controls")
        end
    end
end

policy = MacHostAdmissionPolicy
workflows = HeavyJobQueuePolicy.read_workflows(File.join(policy::ROOT, ".github/workflows"))
HeavyJobQueuePolicy.check(workflows)
workflow = workflows.fetch("desktop-cross-host.yml")
policy.check(workflow)
checks = 1
mutations = {
    "secrets" => ->(v) { v["env"] = {"TOKEN" => "${{ secrets.PUBLISH }}"} },
    "write scope" => ->(v) { v["permissions"]["contents"] = "write" },
    "extra input" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["runner"] = {"type" => "string"} },
    "extra operation" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["operation"]["options"] << "arbitrary" },
    "wrong role" => ->(v) { v["jobs"][policy::JOB]["runs-on"] = "macos-latest" },
    "missing guard" => ->(v) { v["jobs"][policy::JOB].delete("if") },
    "extra matrix" => ->(v) { v["jobs"][policy::JOB]["strategy"] = {"matrix" => {"os" => %w[macos-26 macos-15-intel]}} },
    "missing queue" => ->(v) { v["jobs"][policy::JOB].delete("concurrency") },
    "extended deadline" => ->(v) { v["jobs"][policy::JOB]["timeout-minutes"] = 6 },
    "publisher environment" => ->(v) { v["jobs"][policy::JOB]["environment"] = "release" },
    "extra variable" => ->(v) { v["jobs"][policy::JOB]["env"]["COMMAND"] = "unsafe" },
    "extra step" => ->(v) { v["jobs"][policy::JOB]["steps"] << {"run" => "./gradlew check"} },
    "missing source binding" => ->(v) { v["jobs"][policy::JOB]["env"].delete("P2PKIT_EXPECTED_TREE") },
    "swapped validation/upload" => ->(v) { v["jobs"][policy::JOB]["steps"][2, 2] = v["jobs"][policy::JOB]["steps"][2, 2].reverse },
}
policy::STEPS.each_index do |index|
    %w[if continue-on-error env working-directory shell run timeout-minutes].each do |field|
        mutations["step #{index} #{field} override"] = ->(v) { v["jobs"][policy::JOB]["steps"][index][field] = "unsafe" }
    end
end
{"fetch-depth" => 1, "persist-credentials" => true, "ref" => "main"}.each do |field, value|
    mutations["checkout #{field}"] = ->(v) { v["jobs"][policy::JOB]["steps"][0]["with"][field] = value }
end
{"path" => "${{ runner.temp }}", "include-hidden-files" => true, "overwrite" => true,
 "if-no-files-found" => "ignore", "retention-days" => 1}.each do |field, value|
    mutations["upload #{field}"] = ->(v) { v["jobs"][policy::JOB]["steps"][3]["with"][field] = value }
end
mutations.each do |name, mutation|
    changed = Marshal.load(Marshal.dump(workflow))
    mutation.call(changed)
    begin
        policy.check(changed)
    rescue HeavyJobQueuePolicy::Error
        checks += 1
        next
    end
    abort "FATAL: accepted capacity mutation: #{name}"
end

ci = workflows.fetch("ci.yml")
release = File.read(File.join(policy::ROOT, "scripts/run-release-gate.sh"))
workflow_test = File.read(File.join(policy::ROOT, "scripts/tests/release-workflow-test.sh"))
policy.entrypoints(ci, release, workflow_test)
checks += 1
[
    ->(v) { v["jobs"]["complete-gate"]["steps"].find { |s| s["name"] == policy::STEP_NAME }["if"] = "false" },
    ->(v) { v["jobs"]["complete-gate"]["steps"].reject! { |s| s["name"] == policy::STEP_NAME } },
].each do |mutation|
    changed = Marshal.load(Marshal.dump(ci))
    mutation.call(changed)
    begin
        policy.entrypoints(changed, release, workflow_test)
    rescue HeavyJobQueuePolicy::Error
        checks += 1
        next
    end
    abort "FATAL: accepted capacity entrypoint omission/override"
end
[
    [ci, release.sub(policy::PYTHON_CHECK, "true"), workflow_test],
    [ci, release, workflow_test.sub('ruby "$ROOT/scripts/tests/check-mac-host-admission-policy-test.rb"', "true")],
].each do |inputs|
    begin
        policy.entrypoints(*inputs)
    rescue HeavyJobQueuePolicy::Error
        checks += 1
        next
    end
    abort "FATAL: accepted capacity release-entrypoint omission"
end
puts "RESULT: PASS — #{checks} pure Mac capacity workflow controls; no hosted/native execution"
