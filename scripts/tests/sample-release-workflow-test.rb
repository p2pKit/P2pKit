#!/usr/bin/env ruby
# Source/mutation controls only. No hosted identity, artifact or publication proof.
require "yaml"
require "json"

ROOT = File.expand_path("../..", __dir__)
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
READ = {"contents" => "read", "actions" => "read", "checks" => "read", "pull-requests" => "read", "deployments" => "read"}.freeze
COMMAND = "python3 -I -B -S scripts/publish-sample-release.py"
ARGS = ' --source "$SOURCE" --producer "$PRODUCER" --attempt "$ATTEMPT"'
ADMIT_IF = %q!${{ github.repository == 'p2pKit/P2pKit' && github.ref == 'refs/heads/main' && (github.event_name == 'workflow_dispatch' || (github.event.workflow_run.head_repository.full_name == github.repository && github.event.workflow_run.conclusion == 'success' && ((github.event.workflow_run.name == 'Publish Maven Central' && github.event.workflow_run.event == 'push' && startsWith(github.event.workflow_run.head_branch, 'v')) || (contains(fromJSON('["Desktop cross-host","CI","OSV Advisory Scan"]'), github.event.workflow_run.name) && github.event.workflow_run.head_branch == 'main' && contains(fromJSON('["push","schedule","workflow_dispatch"]'), github.event.workflow_run.event))))) }}!

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
    need(triggers["workflow_run"] == {"workflows" => ["Desktop cross-host", "CI", "OSV Advisory Scan", "Publish Maven Central"],
                                     "types" => ["completed"]}, "main and Maven tag completions must reach explicit admission")
    inputs = triggers["workflow_dispatch"]["inputs"]
    need(inputs.keys.sort == %w[operation producer_attempt producer_run source_sha] &&
         inputs.values.all? { |x| x["required"] == true } &&
         inputs["operation"]["options"] == %w[verify publish] && inputs["operation"]["default"] == "verify",
         "manual default must not publish or accept an unbound producer")
    jobs = workflow["jobs"]
    need(jobs.keys.sort == %w[admit prepare-review publish verify-only], "unexpected publisher job")
    need(jobs["admit"]["if"] == ADMIT_IF && !jobs["admit"].key?("permissions"), "read-only admission guard changed")
    need(jobs["verify-only"]["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'verify' }}" &&
         !jobs["verify-only"].key?("permissions"), "verify may not receive write permission")
    need(jobs["publish"]["if"] == "${{ github.event_name != 'workflow_dispatch' || inputs.operation == 'publish' }}" &&
         jobs["publish"]["permissions"] == READ.merge("contents" => "write"), "isolate only the sample publisher's write token")
    need(jobs["prepare-review"]["if"] == jobs["publish"]["if"] && !jobs["prepare-review"].key?("permissions"),
         "manual and automatic publication must both prepare a read-only evidence review")
    need(jobs["admit"]["outputs"] == %w[source producer attempt].to_h { |x| [x, "${{ steps.admit.outputs.#{x} }}"] } &&
         jobs["prepare-review"]["outputs"] == {"request_sha256" => "${{ steps.prepare.outputs.request_sha256 }}",
                                               "artifact_id" => "${{ steps.evidence.outputs.artifact-id }}"},
         "bind downstream jobs to original admission and the immutable review upload")
    jobs.each do |name, job|
        need(job["runs-on"] == "ubuntu-latest" && job["timeout-minutes"] == (name == "admit" ? 5 : 20), "bounded hosted job required")
        need((name == "publish" ? job["environment"] == "sample-development-release" : !job.key?("environment")) &&
             !job.key?("env") && !job.key?("defaults") && !job.key?("continue-on-error"),
             "only publication may enter the exact protected environment; no ambient credentials or failure bypass")
        need(name == "admit" || job["needs"] == (name == "publish" ? %w[admit prepare-review] : "admit"),
             "publication must depend on successful admission and original evidence review preparation")
        steps = job.fetch("steps")
        need(steps.length == (name == "admit" ? 2 : 4), "extra/missing publisher step")
        need(steps[0]["uses"] == CHECKOUT && steps[0]["with"] == {"ref" => "${{ github.workflow_sha }}", "persist-credentials" => false},
             "never execute producer/artifact/fork code with publication credentials")
        operation = name == "verify-only" ? "verify" : name
        review_args = name == "publish" ? ' --review-artifact "$REVIEW_ARTIFACT" --review-request "$REVIEW_REQUEST"' : ""
        need(steps[1]["run"] == COMMAND + " " + operation + ARGS + review_args && !steps[1].key?("if") &&
             !steps[1].key?("continue-on-error"), "exact fail-closed publisher command required")
        need(steps[1]["id"] == "admit", "original admission outputs required") if name == "admit"
        need(steps[1]["id"] == "prepare", "original review outputs required") if name == "prepare-review"
        expected_env = {"GH_TOKEN" => "${{ github.token }}"}
        %w[SOURCE PRODUCER ATTEMPT].zip(%w[source_sha producer_run producer_attempt], %w[source producer attempt]).each do |key, input, output|
            expected_env[key] = name == "admit" ? "${{ inputs.#{input} }}" : "${{ needs.admit.outputs.#{output} }}"
        end
        if name == "publish"
            expected_env["REVIEW_ARTIFACT"] = "${{ needs.prepare-review.outputs.artifact_id }}"
            expected_env["REVIEW_REQUEST"] = "${{ needs.prepare-review.outputs.request_sha256 }}"
        end
        need(steps[1]["env"] == expected_env, "do not interpolate untrusted inputs into code or add credentials")
        next if name == "admit"
        upload, cleanup = steps[2], steps[3]
        files = %w[receipt.json sample-release.json SHA256SUMS]
        files << "review-request.json" unless name == "verify-only"
        files << "approval-receipt.json" if name == "publish"
        purpose = {"verify-only" => "verification", "prepare-review" => "review", "publish" => "publication"}.fetch(name)
        need(upload["uses"] == UPLOAD && upload["id"] == "evidence" &&
             (name == "prepare-review" ? !upload.key?("if") : upload["if"] == "${{ always() }}") &&
             upload["with"]["name"] == "sample-release-#{purpose}-${{ github.run_id }}-${{ github.run_attempt }}" &&
             upload["with"]["if-no-files-found"] == (name == "prepare-review" ? "error" : "warn") &&
             upload["with"]["path"].lines.map(&:strip) == files.map { |x|
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
    ->(x) { x["on"]["workflow_run"]["branches"] = ["main"] },
    ->(x) { x["on"]["workflow_run"]["workflows"].delete("Publish Maven Central") },
    ->(x) { x["on"]["workflow_dispatch"]["inputs"]["operation"]["default"] = "publish" },
    ->(x) { x["concurrency"]["cancel-in-progress"] = true },
    ->(x) { x["jobs"]["admit"].delete("if") },
    ->(x) { x["jobs"]["admit"]["if"] = x["jobs"]["admit"]["if"].sub("github.event.workflow_run.head_branch == 'main'", "true") },
    ->(x) { x["jobs"]["admit"]["if"] = x["jobs"]["admit"]["if"].sub("github.event.workflow_run.conclusion == 'success'", "true") },
    ->(x) { x["jobs"]["admit"]["if"] = x["jobs"]["admit"]["if"].sub("github.event.workflow_run.event == 'push'", "true") },
    ->(x) { x["jobs"]["verify-only"]["permissions"] = READ.merge("contents" => "write") },
    ->(x) { x["jobs"]["publish"].delete("needs") },
    ->(x) { x["jobs"]["publish"]["needs"] = "admit" },
    ->(x) { x["jobs"]["publish"].delete("environment") },
    ->(x) { x["jobs"]["publish"]["environment"] = "maven-central" },
    ->(x) { x["jobs"]["prepare-review"]["environment"] = "sample-development-release" },
    ->(x) { x["jobs"]["prepare-review"]["permissions"] = READ.merge("contents" => "write") },
    ->(x) { x["jobs"]["prepare-review"]["outputs"]["request_sha256"] = "${{ inputs.source_sha }}" },
    ->(x) { x["jobs"]["prepare-review"]["steps"][2]["with"]["if-no-files-found"] = "warn" },
    ->(x) { x["jobs"]["prepare-review"]["steps"][2]["with"]["overwrite"] = true },
    ->(x) { x["jobs"]["publish"]["steps"][1]["run"] = COMMAND + " publish" + ARGS },
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
