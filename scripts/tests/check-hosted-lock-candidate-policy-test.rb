#!/usr/bin/env ruby
# Offline/adversarial workflow models only. No dispatch, native work or downloads.
require_relative "../check-hosted-lock-candidate-policy"

policy = HostedLockCandidatePolicy
workflows = HeavyJobQueuePolicy.read_workflows(File.join(policy::ROOT, ".github/workflows"))
HeavyJobQueuePolicy.check(workflows)
workflow = workflows.fetch("desktop-cross-host.yml")
original = Marshal.dump(workflow)
policy.check(workflow)
checks = 1

mutations = {
    "write token" => ->(v) { v["permissions"]["contents"] = "write" },
    "publisher credentials" => ->(v) { v["env"] = {"TOKEN" => "${{ secrets.PUBLISH }}"} },
    "alternate workflow identity" => ->(v) { v["name"] = "Lock publisher" },
    "ordinary workflow cancellation group" => ->(v) { v["concurrency"]["group"] = "desktop-cross-host-${{ github.ref }}" },
    "writer cancellation" => ->(v) { v["concurrency"]["cancel-in-progress"] = true },
    "writer falls through to samples" => ->(v) {
        v["jobs"]["verify"]["if"].sub!(" && inputs.operation != 'dependency-lock-candidate'", "")
    },
    "Intel writer falls through to samples" => ->(v) {
        v["jobs"]["verify"]["if"].sub!(" && inputs.operation != 'dependency-lock-candidate-x64'", "")
    },
    "Intel writer enters cancelling workflow group" => ->(v) {
        v["concurrency"]["cancel-in-progress"].sub!(" && inputs.operation != 'dependency-lock-candidate-x64'", "")
    },
    "Intel runner confused with ordinary ARM Mac" => ->(v) {
        v["jobs"][policy::JOB]["runs-on"].sub!("macos-15-intel", "macos-15")
    },
    "Intel uses wrong Xcode" => ->(v) {
        v["jobs"][policy::JOB]["env"]["DEVELOPER_DIR"].sub!("Xcode_26.3", "Xcode_26.5")
    },
    "macOS14 writer falls through to samples" => ->(v) {
        v["jobs"]["verify"]["if"].sub!(" && inputs.operation != 'dependency-lock-candidate-macos14'", "")
    },
    "macOS14 writer enters cancelling workflow group" => ->(v) {
        v["concurrency"]["cancel-in-progress"].sub!(" && inputs.operation != 'dependency-lock-candidate-macos14'", "")
    },
    "macOS14 writer silently substitutes another image" => ->(v) {
        v["jobs"][policy::JOB]["runs-on"].sub!("'macos-14'", "'macos-15'")
    },
    "macOS14 writer silently substitutes default Xcode" => ->(v) {
        v["jobs"][policy::JOB]["env"]["DEVELOPER_DIR"].sub!("Xcode_16.2", "Xcode")
    },
    "arbitrary command input" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["command"] = {"type" => "string"} },
    "default writer operation" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["operation"]["default"] = policy::JOB },
    "unknown operation" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["operation"]["options"] << "shell" },
    "extra job authority" => ->(v) { v["jobs"]["publish"] = {"run" => "gh release create tag"} },
    "wrong runner" => ->(v) { v["jobs"][policy::JOB]["runs-on"] = "macos-latest" },
    "nonmanual writer" => ->(v) { v["jobs"][policy::JOB]["if"] = true },
    "extended job deadline" => ->(v) { v["jobs"][policy::JOB]["timeout-minutes"] = 196 },
    "write job scope" => ->(v) { v["jobs"][policy::JOB]["permissions"]["contents"] = "write" },
    "publisher environment" => ->(v) { v["jobs"][policy::JOB]["environment"] = "release" },
    "ignored job failure" => ->(v) { v["jobs"][policy::JOB]["continue-on-error"] = true },
    "missing heavy queue" => ->(v) { v["jobs"][policy::JOB].delete("concurrency") },
    "new tool acquisition step" => ->(v) { v["jobs"][policy::JOB]["steps"].insert(1, {"uses" => SampleAppWorkflowPolicy::JAVA}) },
    "cache restore" => ->(v) { v["jobs"][policy::JOB]["steps"] << {"uses" => "actions/cache@#{'a' * 40}"} },
    "release side effect" => ->(v) { v["jobs"][policy::JOB]["steps"] << {"run" => "gh release create tag"} },
    "input command interpolation" => ->(v) { v["jobs"][policy::JOB]["steps"][1]["run"] += " ${{ inputs.reviewed_base }}" },
    "raw command output tee" => ->(v) { v["jobs"][policy::JOB]["steps"][1]["run"] += " | tee raw.log" },
    "validation before sealing" => ->(v) { v["jobs"][policy::JOB]["steps"][2, 2] = v["jobs"][policy::JOB]["steps"][2, 2].reverse },
    "upload before validation" => ->(v) { v["jobs"][policy::JOB]["steps"][3, 2] = v["jobs"][policy::JOB]["steps"][3, 2].reverse },
    "success-only sealing" => ->(v) { v["jobs"][policy::JOB]["steps"][2]["if"] = "${{ success() }}" },
    "raw sealing stdout tee" => ->(v) { v["jobs"][policy::JOB]["steps"][2]["run"] += " | tee raw.log" },
    "unsafe readiness from product step" => ->(v) {
        v["jobs"][policy::JOB]["steps"][4]["if"] = "${{ always() && steps.candidate.outputs.artifacts_ready == 'true' }}"
    },
}
%w[expected_sha expected_tree reviewed_base evidence_public_key evidence_fingerprint].each do |name|
    {"type" => "choice", "required" => true, "default" => "unsafe"}.each do |field, value|
        mutations["input #{name} changed #{field}"] = ->(v) {
            (v["on"] || v[true])["workflow_dispatch"]["inputs"][name][field] = value
        }
    end
    mutations["missing input #{name}"] = ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"].delete(name) }
end
policy::ENVIRONMENT.each_key do |name|
    mutations["missing environment binding #{name}"] = ->(v) { v["jobs"][policy::JOB]["env"].delete(name) }
    mutations["changed environment binding #{name}"] = ->(v) { v["jobs"][policy::JOB]["env"][name] = "unreviewed" }
end
policy::STEPS.each_index do |index|
    %w[if continue-on-error env working-directory shell run timeout-minutes].each do |field|
        mutations["step #{index} #{field} override"] = ->(v) { v["jobs"][policy::JOB]["steps"][index][field] = "unsafe" }
    end
    mutations["missing step #{index}"] = ->(v) { v["jobs"][policy::JOB]["steps"].delete_at(index) }
end
{"fetch-depth" => 1, "persist-credentials" => true, "ref" => "main"}.each do |field, value|
    mutations["checkout #{field}"] = ->(v) { v["jobs"][policy::JOB]["steps"][0]["with"][field] = value }
end
{"path" => "${{ runner.temp }}", "name" => "latest", "include-hidden-files" => true, "overwrite" => true,
 "if-no-files-found" => "ignore", "retention-days" => 90, "compression-level" => 9}.each do |field, value|
    mutations["upload #{field}"] = ->(v) { v["jobs"][policy::JOB]["steps"][4]["with"][field] = value }
end
mutations.each do |name, mutation|
    changed = Marshal.load(Marshal.dump(workflow))
    mutation.call(changed)
    begin
        policy.check(changed)
    rescue policy::Error
        checks += 1
        next
    end
    abort "FATAL: accepted lock-candidate workflow mutation: #{name}"
end
raise "workflow policy tests mutated their source fixture" unless original == Marshal.dump(workflow)

ci = workflows.fetch("ci.yml")
release = File.read(File.join(policy::ROOT, "scripts/run-release-gate.sh"))
workflow_test = File.read(File.join(policy::ROOT, "scripts/tests/release-workflow-test.sh"))
entrypoints = [ci, release, workflow_test]
original_entrypoints = Marshal.dump(entrypoints)
policy.entrypoints(*entrypoints)
checks += 1

control_step = ->(v) { v[0]["jobs"]["complete-gate"]["steps"].find { |step| step["name"] == policy::STEP_NAME } }
entrypoint_mutations = {
    "missing CI controls" => ->(v) {
        v[0]["jobs"]["complete-gate"]["steps"].delete(control_step.call(v))
    },
    "duplicate CI controls" => ->(v) {
        v[0]["jobs"]["complete-gate"]["steps"] << Marshal.load(Marshal.dump(control_step.call(v)))
    },
    "CI controls after scope selection" => ->(v) {
        steps = v[0]["jobs"]["complete-gate"]["steps"]
        steps << steps.delete(control_step.call(v))
    },
    "missing CI scope classifier" => ->(v) {
        v[0]["jobs"]["complete-gate"]["steps"].reject! { |step| step["id"] == "scope" }
    },
    "duplicate CI scope classifier" => ->(v) {
        steps = v[0]["jobs"]["complete-gate"]["steps"]
        steps << Marshal.load(Marshal.dump(steps.find { |step| step["id"] == "scope" }))
    },
    "missing complete-gate" => ->(v) { v[0]["jobs"].delete("complete-gate") },
    "CI job can skip controls" => ->(v) { v[0]["jobs"]["complete-gate"]["if"] = "false" },
    "CI implicit success-only job" => ->(v) { v[0]["jobs"]["complete-gate"].delete("if") },
    "CI wrong shell host" => ->(v) { v[0]["jobs"]["complete-gate"]["runs-on"] = "windows-latest" },
    "ignored CI job failure" => ->(v) { v[0]["jobs"]["complete-gate"]["continue-on-error"] = true },
}
{"if" => "false", "continue-on-error" => true, "shell" => "bash -n {0}",
 "env" => {"BASH_ENV" => "/tmp/skip"}, "working-directory" => "/tmp"}.each do |field, value|
    entrypoint_mutations["CI control step #{field} override"] = ->(v) { control_step.call(v)[field] = value }
end
["workflow", "job"].each do |scope|
    {"defaults" => {"run" => {"shell" => "bash {0}"}}, "env" => {"PATH" => "/tmp"}}.each do |field, value|
        entrypoint_mutations["CI #{scope} #{field} override"] = ->(v) {
            target = scope == "workflow" ? v[0] : v[0]["jobs"]["complete-gate"]
            target[field] = value
        }
    end
end
policy::CHECKS.each do |command|
    script = command.split(" ").last
    entrypoint_mutations["CI removes #{script}"] = ->(v) { control_step.call(v)["run"].sub!(command, "true") }
    entrypoint_mutations["CI ignores #{script}"] = ->(v) { control_step.call(v)["run"].sub!(command, "#{command} || true") }
    entrypoint_mutations["CI repeats #{script} elsewhere"] = ->(v) {
        v[0]["jobs"]["complete-gate"]["steps"] << {"name" => "Duplicate control", "run" => command}
    }
end

# Mutate only in-memory shell text. These controls neither source nor execute
# either broad entrypoint, nor invoke any Python test, native tool or build.
[[1, "release gate"], [2, "workflow controls"]].each do |index, label|
    commands = policy::CHECKS.map do |command|
        interpreter, _, script = command.rpartition(" ")
        index == 1 ? command : "#{interpreter} \"$ROOT/#{script}\""
    end
    commands.each do |command|
        {
            "removed" => "true",
            "commented out" => "# #{command}",
            "duplicated" => "#{command}\n#{command}",
            "ignored failure" => "#{command} || true",
            "piped failure" => "#{command} | cat",
            "inline conditional" => "false && #{command}",
            "conditional block" => "if false; then\n#{command}\nfi",
            "uninvoked function" => "skipped_control() {\n#{command}\n}",
            "heredoc data" => ": <<'IGNORED_CONTROL'\n#{command}\nIGNORED_CONTROL",
            "disabled errexit" => "set +e\n#{command}\nset -e",
            "successful early exit" => "exit 0\n#{command}",
            "successful early return" => "return 0\n#{command}",
            "error trap" => "trap 'exit 0' ERR\n#{command}",
            "continued previous line" => "printf ignored \\\n#{command}",
            "preceding conditional operator" => "false &&\n#{command}",
        }.each do |mutation, replacement|
            entrypoint_mutations["#{label}: #{mutation}: #{command}"] = ->(v) {
                v[index].sub!(command, replacement)
            }
        end
    end
    entrypoint_mutations["#{label}: no strict shell preamble"] = ->(v) { v[index].sub!("set -euo pipefail", "set -u") }
    entrypoint_mutations["#{label}: wrong interpreter"] = ->(v) { v[index].sub!("#!/usr/bin/env bash", "#!/usr/bin/env sh") }
    entrypoint_mutations["#{label}: blocks reordered"] = ->(v) {
        v[index].sub!(commands.join("\n"), commands.reverse.join("\n"))
    }
    entrypoint_mutations["#{label}: entire strict script conditional"] = ->(v) {
        v[index].sub!("set -euo pipefail", "if false; then\nset -euo pipefail")
        v[index] += "\nfi\n"
    }
end
entrypoint_mutations.each do |name, mutation|
    changed = Marshal.load(original_entrypoints)
    mutation.call(changed)
    raise "entrypoint mutation had no effect: #{name}" if Marshal.dump(changed) == original_entrypoints
    begin
        policy.entrypoints(*changed)
    rescue policy::Error
        checks += 1
        next
    end
    abort "FATAL: accepted hosted control entrypoint mutation: #{name}"
end

# Comments/blank lines do not change an otherwise reviewed, unconditional
# command. Unlike source hashes, this contract permits that harmless change.
commented = Marshal.load(original_entrypoints)
[1, 2].each do |index|
    commented[index].sub!("set -euo pipefail", "# Retain strict shell failure semantics.\n\nset -euo pipefail")
end
policy.entrypoints(*commented)
checks += 1
raise "entrypoint tests mutated their source fixtures" unless original_entrypoints == Marshal.dump(entrypoints)
puts "RESULT: PASS — #{checks} offline lock-candidate workflow/entrypoint controls; no native/writer/encryption execution"
