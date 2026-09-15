#!/usr/bin/env ruby
# Source/mutation controls only. No hosted identity, artifact or publication proof.
require "yaml"
require "json"

ROOT = File.expand_path("../..", __dir__)
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
READ = {"contents" => "read", "actions" => "read", "checks" => "read", "pull-requests" => "read"}.freeze
COMMAND = "python3 -I -B -S scripts/publish-sample-release.py"
ARGS = ' --source "$SOURCE" --producer "$PRODUCER" --attempt "$ATTEMPT"'
ADMIT_IF = %q!${{ github.repository == 'p2pKit/P2pKit' && github.ref == 'refs/heads/main' && (github.event_name == 'workflow_dispatch' || (contains(fromJSON('["push","schedule","workflow_dispatch"]'), github.event.workflow_run.event) && github.event.workflow_run.head_repository.full_name == github.repository && github.event.workflow_run.conclusion == 'success')) }}!

def need(value, reason)
    raise ArgumentError, reason unless value
end

def check(workflow)
    need(workflow.keys.sort == %w[concurrency jobs name on permissions], "unexpected workflow authority")
    need(workflow["permissions"] == READ, "read-only workflow default required")
    need(workflow["concurrency"] == {"group" => "development-samples-${{ github.event.workflow_run.head_sha || inputs.source_sha }}",
                                    "cancel-in-progress" => false}, "publication must not be cancelled or overlap by source")
    triggers = workflow["on"]
    need(triggers.keys.sort == %w[workflow_dispatch workflow_run], "no PR/tag or unsafe publisher trigger")
    need(triggers["workflow_run"] == {"workflows" => ["Desktop cross-host", "CI", "OSV Advisory Scan"],
                                     "types" => ["completed"], "branches" => ["main"]}, "trusted main completion triggers required")
    inputs = triggers["workflow_dispatch"]["inputs"]
    need(inputs.keys.sort == %w[operation producer_attempt producer_run source_sha] &&
         inputs.values.all? { |x| x["required"] == true } &&
         inputs["operation"]["options"] == %w[verify publish] && inputs["operation"]["default"] == "verify",
         "manual default must not publish or accept an unbound producer")
    jobs = workflow["jobs"]
    need(jobs.keys.sort == %w[admit publish verify-only], "unexpected publisher job")
    need(jobs["admit"]["if"] == ADMIT_IF && !jobs["admit"].key?("permissions"), "read-only admission guard changed")
    need(jobs["verify-only"]["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'verify' }}" &&
         !jobs["verify-only"].key?("permissions"), "verify may not receive write permission")
    need(jobs["publish"]["if"] == "${{ github.event_name != 'workflow_dispatch' || inputs.operation == 'publish' }}" &&
         jobs["publish"]["permissions"] == READ.merge("contents" => "write"), "isolate only the sample publisher's write token")
    jobs.each do |name, job|
        need(job["runs-on"] == "ubuntu-latest" && job["timeout-minutes"] == (name == "admit" ? 5 : 20), "bounded hosted job required")
        need(!job.key?("environment") && !job.key?("env") && !job.key?("defaults") && !job.key?("continue-on-error"),
             "no publisher environments, ambient credentials or failure bypass")
        need(name == "admit" || job["needs"] == "admit", "publication must depend on successful admission")
        steps = job.fetch("steps")
        need(steps.length == (name == "admit" ? 2 : 4), "extra/missing publisher step")
        need(steps[0]["uses"] == CHECKOUT && steps[0]["with"] == {"ref" => "${{ github.workflow_sha }}", "persist-credentials" => false},
             "never execute producer/artifact/fork code with publication credentials")
        operation = name == "verify-only" ? "verify" : name
        need(steps[1]["run"] == COMMAND + " " + operation + ARGS && !steps[1].key?("if") &&
             !steps[1].key?("continue-on-error"), "exact fail-closed publisher command required")
        expected_env = {"GH_TOKEN" => "${{ github.token }}"}
        %w[SOURCE PRODUCER ATTEMPT].zip(%w[source_sha producer_run producer_attempt], %w[source producer attempt]).each do |key, input, output|
            expected_env[key] = name == "admit" ? "${{ inputs.#{input} }}" : "${{ needs.admit.outputs.#{output} }}"
        end
        need(steps[1]["env"] == expected_env, "do not interpolate untrusted inputs into code or add credentials")
        next if name == "admit"
        upload, cleanup = steps[2], steps[3]
        need(upload["uses"] == UPLOAD && upload["id"] == "evidence" && upload["if"] == "${{ always() }}" &&
             upload["with"]["path"].lines.map(&:strip) == %w[receipt.json sample-release.json SHA256SUMS].map { |x|
                 "${{ runner.temp }}/p2pkit-sample-release/#{x}"
             } && upload["with"]["retention-days"] == 14 && upload["with"]["overwrite"] == false,
             "only fixed public provenance may be uploaded")
        need(cleanup["if"] == "${{ always() && steps.evidence.outcome == 'success' }}" && cleanup["run"] == COMMAND + " cleanup",
             "owned metadata cleanup must follow evidence retention")
    end
    need(!JSON.generate(workflow).match?(/secrets\.|id-token|pull_request_target|setup-gradle|setup-java|publish-maven/),
         "no signing, build, Maven or privileged PR surface")
end

path = File.join(ROOT, ".github/workflows/sample-development-releases.yml")
workflow = YAML.safe_load(File.read(path), permitted_classes: [], permitted_symbols: [], aliases: false)
workflow["on"] = workflow.delete(true) if workflow.key?(true)
check(workflow)
controls = 1
mutations = [
    ->(x) { x["permissions"]["contents"] = "write" },
    ->(x) { x["on"]["pull_request_target"] = {} },
    ->(x) { x["on"]["workflow_run"]["branches"] = ["*"] },
    ->(x) { x["on"]["workflow_dispatch"]["inputs"]["operation"]["default"] = "publish" },
    ->(x) { x["concurrency"]["cancel-in-progress"] = true },
    ->(x) { x["jobs"]["admit"].delete("if") },
    ->(x) { x["jobs"]["verify-only"]["permissions"] = READ.merge("contents" => "write") },
    ->(x) { x["jobs"]["publish"].delete("needs") },
    ->(x) { x["jobs"]["publish"]["permissions"]["id-token"] = "write" },
    ->(x) { x["jobs"]["publish"]["steps"][0]["with"]["ref"] = "${{ github.event.workflow_run.head_sha }}" },
    ->(x) { x["jobs"]["publish"]["steps"][0]["with"]["persist-credentials"] = true },
    ->(x) { x["jobs"]["publish"]["steps"][1]["run"] += " || true" },
    ->(x) { x["jobs"]["publish"]["steps"][1]["continue-on-error"] = true },
    ->(x) { x["jobs"]["publish"]["steps"][1]["env"]["GH_TOKEN"] = "${{ secrets.PUBLISH_TOKEN }}" },
    ->(x) { x["jobs"]["publish"]["steps"][2]["with"]["path"] = "**/*.log" },
    ->(x) { x["jobs"]["publish"]["steps"][3]["run"] = "rm -rf $RUNNER_TEMP" },
    ->(x) { x["jobs"]["publish"]["steps"] << {"run" => "./gradlew build"} },
]
mutations.each_with_index do |mutation, i|
    changed = Marshal.load(Marshal.dump(workflow))
    mutation.call(changed)
    rejected = false
    begin
        check(changed)
    rescue ArgumentError
        rejected = true
    end
    abort "FATAL: publisher mutation #{i} accepted" unless rejected
    controls += 1
end

command = "python3 -I -B -S scripts/tests/publish-sample-release-test.py"
ruby_command = "ruby scripts/tests/sample-release-workflow-test.rb"
ci = YAML.safe_load(File.read(File.join(ROOT, ".github/workflows/ci.yml")), permitted_classes: [], aliases: false)
steps = ci["jobs"]["complete-gate"]["steps"]
index = steps.index { |x| x["name"] == "Verify development sample release policy" }
need(index && index < steps.index { |x| x["id"] == "scope" } &&
     steps[index] == {"name" => "Verify development sample release policy", "run" => ruby_command + "\n" + command + "\n"},
     "release controls must run in either CI scope")
[command, ruby_command].each do |line|
    need(File.read(File.join(ROOT, "scripts/run-release-gate.sh")).lines.map(&:strip).count(line) == 1, "release control missing")
    interpreter, _, script = line.rpartition(" ")
    need(File.read(File.join(ROOT, "scripts/tests/release-workflow-test.sh")).lines.map(&:strip).count("#{interpreter} \"$ROOT/#{script}\"") == 1,
         "workflow control missing")
end
puts "PASS: #{controls} development-release workflow controls; no hosted publication executed"
