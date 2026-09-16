#!/usr/bin/env ruby
require "yaml"
require "shellwords"
require_relative "../check-heavy-job-queue-policy"

def submission_arguments(workflow)
    steps = workflow.fetch("jobs").values.flat_map { |job| job.fetch("steps", []) }
    submissions = steps.select do |step|
        step["uses"].is_a?(String) && step["uses"].match?(/\Agradle\/actions\/dependency-submission@/i)
    end
    raise "expected exactly one dependency-submission action" unless submissions.length == 1

    inputs = submissions.first["with"]
    arguments = inputs["additional-arguments"] if inputs.is_a?(Hash)
    raise "dependency submission must explicitly override verification=off with strict" unless
        arguments.is_a?(String) && Shellwords.split(arguments) == ["--dependency-verification", "strict"]
end

def fixture(arguments)
    {"jobs" => {"submit" => {"steps" => [{
        "uses" => "gradle/actions/dependency-submission@#{'a' * 40}",
        "with" => {"additional-arguments" => arguments},
    }]}}}
end

submission_arguments(fixture("--dependency-verification strict"))
submission_arguments(fixture("  --dependency-verification 'strict'\n"))
checks = 2
[
    nil, false, [], "", "--no-daemon", "--dependency-verification off",
    "--dependency-verification lenient", "-Dorg.gradle.dependency.verification=strict",
    "${{ inputs.arguments }}", "--dependency-verification strict --dependency-verification off",
    "--dependency-verification strict --write-verification-metadata sha256",
    "--dependency-verification 'strict",
].each do |arguments|
    rejected = false
    begin
        submission_arguments(fixture(arguments))
    rescue RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe submission arguments accepted: #{arguments.inspect}" unless rejected
    checks += 1
end

safe = fixture("--dependency-verification strict")
safe["jobs"]["submit"]["steps"].unshift({"run" => "echo preceding step"})
safe["jobs"]["reusable"] = {"uses" => "example/repo/.github/workflows/test.yml@#{'a' * 40}"}
submission_arguments(safe)
checks += 1

def submission_prerequisites(workflow)
    check = ->(condition, message) { raise message unless condition }
    check.call(workflow.keys.sort_by(&:to_s) == ["name", "permissions", "jobs", true].sort_by(&:to_s),
               "retain closed submission workflow context")
    check.call(workflow["name"] == "Dependency submission" &&
               workflow[true] == {"push" => {"branches" => ["main"]}, "workflow_dispatch" => nil} &&
               workflow["permissions"] == {"contents" => "write"}, "retain ordinary triggers and existing token scope")
    jobs = workflow["jobs"]
    check.call(jobs.is_a?(Hash) && jobs.keys == ["submit"], "one ordinary submission job required")
    job = jobs.fetch("submit")
    check.call(job.keys.sort == %w[concurrency runs-on steps timeout-minutes] &&
               job["runs-on"] == "macos-latest" && job["timeout-minutes"] == 90 &&
               job["concurrency"] == HeavyJobQueuePolicy::QUEUE, "bounded macOS job and shared queue required")
    steps = job["steps"]
    check.call(steps.is_a?(Array) && steps.length == 8, "fixed submission prerequisite/finalizer path required")
    checkout, java, prepare, sdk, submit, stop, verify, upload = steps
    check.call(checkout.reject { |key, _| key == "name" } == {
        "uses" => "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "timeout-minutes" => 3, "with" => {"persist-credentials" => false},
    }, "checkout pin/source/credential boundary changed")
    check.call(java.reject { |key, _| key == "name" } == {
        "uses" => "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961",
        "timeout-minutes" => 10, "with" => {"distribution" => "temurin", "java-version" => "21\n17\n"},
    }, "explicit Java21 then wrapper Java17 required")
    helper = "python3 -I -B -S scripts/dependency-submission-prerequisites.py "
    check.call(prepare.reject { |key, _| key == "name" } == {
        "id" => "prepare", "timeout-minutes" => 3, "shell" => "bash", "run" => helper + "prepare",
    }, "fresh owned home and admission must precede action")
    state = {"P2PKIT_DEPENDENCY_STATE" => "${{ steps.prepare.outputs.state }}"}
    check.call(sdk.reject { |key, _| key == "name" } == {
        "timeout-minutes" => 15, "shell" => "bash", "env" => state, "run" => helper + "install-sdk",
    }, "literal missing-only compile SDK admission required")
    check.call(submit.reject { |key, _| key == "name" } == {
        "id" => "submit-graph", "timeout-minutes" => 40,
        "uses" => "gradle/actions/dependency-submission@9c971963bec38e04b3d30dcc455b5382be2fdbfb",
        "with" => {"gradle-home-cache-excludes" => "caches/build-cache-1",
                   "additional-arguments" => "--dependency-verification strict"},
    }, "retain pinned default full resolver/submission/cache contract without filters or overrides")
    always = "${{ always() && steps.prepare.outcome == 'success' }}"
    check.call(stop.reject { |key, _| key == "name" } == {
        "id" => "stop-gradle", "timeout-minutes" => 3, "shell" => "bash",
        "if" => "${{ always() && steps.prepare.outcome == 'success' && steps.submit-graph.outcome != 'skipped' }}",
        "env" => {"GRADLE_USER_HOME" => "${{ steps.prepare.outputs.gradle-home }}"},
        "run" => <<~BASH,
            set +e
            ./gradlew --stop --console=plain
            stop_status=$?
            printf 'exit-code=%s\\n' "$stop_status" >> "$GITHUB_OUTPUT"
            exit "$stop_status"
        BASH
    }, "always-run exact-wrapper/home stop must preserve original failure and exit code")
    check.call(verify.reject { |key, _| key == "name" } == {
        "if" => always, "timeout-minutes" => 3, "shell" => "bash", "run" => helper + "verify",
        "env" => state.merge("P2PKIT_DEPENDENCY_ACTION_OUTCOME" => "${{ steps.submit-graph.outcome }}",
            "P2PKIT_DEPENDENCY_STOP_OUTCOME" => "${{ steps.stop-gradle.outcome }}",
            "P2PKIT_DEPENDENCY_STOP_EXIT_CODE" => "${{ steps.stop-gradle.outputs.exit-code }}"),
    }, "post-main graph inspection must preserve failure outcomes")
    check.call(upload.reject { |key, _| key == "name" } == {
        "if" => always, "timeout-minutes" => 5,
        "uses" => "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "with" => {"name" => "dependency-submission-receipt-${{ github.run_id }}-${{ github.run_attempt }}",
            "path" => "${{ steps.prepare.outputs.receipt }}/*.json", "if-no-files-found" => "error", "retention-days" => 14},
    }, "bounded original receipt retention required; do not upload home or remove it before post")
end

path = ARGV.fetch(0, File.expand_path("../../.github/workflows/dependency-submission.yml", __dir__))
workflow = HeavyJobQueuePolicy.parse(File.read(path), path)
submission_arguments(workflow)
submission_prerequisites(workflow)
checks += 1

mutations = {
    "ambient workflow override" => ->(w) { w["env"] = {"GRADLE_OPTS" => "-Xmx8g"} },
    "loss of main trigger" => ->(w) { w[true]["push"]["branches"] = ["work/candidate"] },
    "manual custom task input" => ->(w) { w[true]["workflow_dispatch"] = {"inputs" => {"task" => {"type" => "string"}}} },
    "increased credential scope" => ->(w) { w["permissions"]["actions"] = "write" },
    "unbounded job" => ->(w) { w["jobs"]["submit"].delete("timeout-minutes") },
    "ignored job failure" => ->(w) { w["jobs"]["submit"]["continue-on-error"] = true },
    "overlapping queue" => ->(w) { w["jobs"]["submit"]["concurrency"]["cancel-in-progress"] = true },
}
step_changes = {
    0 => {"credential persistence" => ->(s) { s["with"]["persist-credentials"] = true },
          "moving source" => ->(s) { s["with"]["ref"] = "main" }},
    1 => {"only JDK17" => ->(s) { s["with"]["java-version"] = "17" },
          "wrong wrapper JDK" => ->(s) { s["with"]["java-version"] = "17\n21\n" }},
    2 => {"shared default home" => ->(s) { s["run"] = "echo ready" }},
    3 => {"skip SDK metadata" => ->(s) { s["run"] = "true" }},
    4 => {"partial resolver" => ->(s) { s["with"]["dependency-resolution-task"] = ":p2p-core:dependencies" },
          "changed provider" => ->(s) { s["with"]["cache-provider"] = "basic" },
          "graph generate only" => ->(s) { s["with"]["dependency-graph"] = "generate-and-upload" },
          "graph filters" => ->(s) { s["with"]["dependency-graph-exclude-projects"] = "samples" },
          "graph identity override" => ->(s) { s["env"] = {"GITHUB_DEPENDENCY_GRAPH_SHA" => "a" * 40} },
          "lenient graph" => ->(s) { s["with"]["dependency-graph-continue-on-failure"] = true },
          "unsafe build cache" => ->(s) { s["with"].delete("gradle-home-cache-excludes") }},
    5 => {"success-only stop" => ->(s) { s["if"] = "${{ success() }}" },
          "other wrapper" => ->(s) { s["run"].sub!("./gradlew", "gradle") },
          "other home" => ->(s) { s["env"]["GRADLE_USER_HOME"] = "~/.gradle" },
          "lost stop outcome" => ->(s) { s["run"].sub!('exit "$stop_status"', "exit 0") }},
    6 => {"fabricated success" => ->(s) { s["env"]["P2PKIT_DEPENDENCY_ACTION_OUTCOME"] = "success" },
          "success-only receipt" => ->(s) { s["if"] = "${{ success() }}" }},
    7 => {"upload entire state" => ->(s) { s["with"]["path"] = "${{ steps.prepare.outputs.state }}/**/*" },
          "drop missing evidence" => ->(s) { s["with"]["if-no-files-found"] = "ignore" }},
}
step_changes.each do |index, values|
    values.each { |name, mutate| mutations[name] = ->(w) { mutate.call(w["jobs"]["submit"]["steps"][index]) } }
end
(0...8).each do |index|
    mutations["unbounded step #{index}"] = ->(w) { w["jobs"]["submit"]["steps"][index].delete("timeout-minutes") }
    mutations["ignored step #{index}"] = ->(w) { w["jobs"]["submit"]["steps"][index]["continue-on-error"] = true }
end
mutations["pre-post home deletion"] = ->(w) { w["jobs"]["submit"]["steps"] << {"run" => 'rm -rf "$GRADLE_USER_HOME"'} }
mutations.each do |name, mutate|
    changed = Marshal.load(Marshal.dump(workflow))
    mutate.call(changed)
    begin
        submission_prerequisites(changed)
    rescue RuntimeError
        checks += 1
        next
    end
    raise "unsafe submission prerequisites accepted: #{name}"
end

hook = File.read(File.expand_path("release-workflow-test.sh", __dir__))
raise "maintained hook must retain prerequisite models" unless
    hook.lines.map(&:strip).include?('python3 -I -B -S "$ROOT/scripts/tests/dependency-submission-prerequisites-test.py"')
puts "RESULT: PASS — dependency submission strict/default scope and bounded prerequisites (#{checks} regression checks)"
