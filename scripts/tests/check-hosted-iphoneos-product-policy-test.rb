#!/usr/bin/env ruby
# Pure YAML/adverse controls. No runner, SDK, compiler, device or dispatch.
require_relative "../check-hosted-lock-candidate-policy"

module IphoneosProductPolicy
    P = HeavyJobQueuePolicy
    S = SampleAppWorkflowPolicy
    JOB = "iphoneos-product"
    ROOT = File.expand_path("../..", __dir__)
    PYTHON = '"$DEVELOPER_DIR/usr/bin/python3" -I -B -S scripts/run-hosted-iphoneos-product.py'
    ENVIRONMENT = {
        "DEVELOPER_DIR" => "/Applications/Xcode_26.5.app/Contents/Developer",
        "P2PKIT_OPERATION" => "${{ inputs.operation }}",
        "P2PKIT_EXPECTED_SHA" => "${{ inputs.expected_sha }}",
        "P2PKIT_EXPECTED_TREE" => "${{ inputs.expected_tree }}",
        "PYTHONDONTWRITEBYTECODE" => "1", "PYTHONUNBUFFERED" => "1",
    }.freeze
    SAVE_JDK = <<~'SH'
        jdk="${JAVA_HOME_21_ARM64:?Missing native daemon JDK}"
        [[ "$jdk" == /* && "$jdk" != *$'\n'* && "$jdk" != *$'\r'* ]]
        printf 'P2PKIT_AUDIT_JDK21=%s\n' "$jdk" >> "$GITHUB_ENV"
    SH
    STEPS = [
        {"name" => "Check out exact reviewed iphoneos recipe source", "timeout-minutes" => 5, "uses" => S::CHECKOUT,
         "with" => {"ref" => "${{ github.sha }}", "fetch-depth" => 0, "persist-credentials" => false}},
        {"name" => "Admit exact manual iphoneos product dispatch", "timeout-minutes" => 1,
         "shell" => "bash", "run" => "exec #{PYTHON} admit"},
        {"name" => "Configure native iphoneos producer JDKs", "timeout-minutes" => 10, "uses" => S::JAVA,
         "with" => {"distribution" => "temurin", "architecture" => "arm64", "java-version" => "21\n17\n"}},
        {"name" => "Bind native daemon JDK path", "timeout-minutes" => 1, "shell" => "bash", "run" => SAVE_JDK},
        {"name" => "Build and inspect fresh unsigned iphoneos recipe product", "id" => "product", "timeout-minutes" => 155,
         "shell" => "bash", "run" => "exec #{PYTHON} run"},
        {"name" => "Validate exact original iphoneos metadata after driver return", "id" => "public",
         "if" => "${{ always() }}", "timeout-minutes" => 2, "shell" => "bash",
         "env" => {"P2PKIT_IPHONEOS_RUN_OUTCOME" => "${{ steps.product.outcome }}"}, "run" => "exec #{PYTHON} validate-public"},
        {"name" => "Retain only allowlisted iphoneos recipe evidence", "id" => "evidence",
         "if" => "${{ always() && steps.public.outcome == 'success' && steps.public.outputs.artifacts_ready == 'true' }}",
         "timeout-minutes" => 3, "uses" => S::UPLOAD, "with" => {
             "name" => "iphoneos-product-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
             "path" => "${{ runner.temp }}/p2pkit-iphoneos-evidence-${{ github.run_id }}-${{ github.run_attempt }}",
             "retention-days" => 14, "if-no-files-found" => "error", "include-hidden-files" => false,
             "overwrite" => false, "compression-level" => 0}},
        {"name" => "Require actual product proof and retained evidence", "timeout-minutes" => 1, "shell" => "bash",
         "if" => "${{ always() && (steps.product.outcome != 'success' || steps.public.outcome != 'success' || steps.public.outputs.product_passed != 'true' || steps.public.outputs.artifacts_ready != 'true' || steps.evidence.outcome != 'success') }}",
         "run" => "echo 'FATAL: iphoneos recipe product or original evidence incomplete; no acceptance claim' >&2\nexit 1\n"},
    ].freeze

    def self.check(workflow)
        # Existing selectors, credentials, sample tasks and lock operation retain
        # their independently maintained policy, not a replacement permissive copy.
        HostedLockCandidatePolicy.check(workflow)
        job = workflow.fetch("jobs").fetch(JOB)
        P.require_policy(job.keys.sort == %w[concurrency env if name permissions runs-on steps timeout-minutes] &&
            job["name"] == JOB && job["runs-on"] == "macos-26" && job["permissions"] == {"contents" => "read"} &&
            job["concurrency"] == P::QUEUE && job["timeout-minutes"] == 180 &&
            job["if"] == P::CONDITIONS[["desktop-cross-host.yml", JOB]], "closed native manual iphoneos job required")
        P.require_policy(job["env"] == ENVIRONMENT && job["steps"] == STEPS,
            "exact iphoneos admission, read-only commands, finite budgets, original retention and failure guard required")
        P.require_policy(STEPS.sum { |step| step.fetch("timeout-minutes") } == 178,
            "iphoneos setup/driver/seal/upload/failure caps must leave two minutes job margin")
    end

    def self.entrypoint(text)
        lines = text.lines.map(&:strip)
        P.require_policy(lines.include?("set -euo pipefail"), "fail-closed workflow hook required")
        ['ruby "$ROOT/scripts/tests/check-hosted-iphoneos-product-policy-test.rb"',
         'python3 -I -B -S "$ROOT/scripts/tests/run-hosted-iphoneos-product-test.py"'].each do |command|
            P.require_policy(lines.count(command) == 1, "each iphoneos control must have one unconditional hook call")
        end
    end
end

p = IphoneosProductPolicy
workflows = HeavyJobQueuePolicy.read_workflows(File.join(p::ROOT, ".github/workflows"))
HeavyJobQueuePolicy.check(workflows)
workflow = workflows.fetch("desktop-cross-host.yml")
p.check(workflow)
checks = 1
mutations = {
    "ordinary push selects product" => ->(v) { v["jobs"][p::JOB]["if"] = true },
    "arbitrary runner" => ->(v) { v["jobs"][p::JOB]["runs-on"] = "macos-latest" },
    "translated JDK" => ->(v) { v["jobs"][p::JOB]["steps"][2]["with"]["architecture"] = "x64" },
    "publisher permission" => ->(v) { v["jobs"][p::JOB]["permissions"] = {"contents" => "write"} },
    "publisher environment" => ->(v) { v["jobs"][p::JOB]["environment"] = "release" },
    "arbitrary secret" => ->(v) { v["jobs"][p::JOB]["env"]["TOKEN"] = "${{ secrets.KEY }}" },
    "retired audit identity" => ->(v) { v["jobs"][p::JOB]["env"]["GITHUB_REF"] = "refs/heads/audit/complete-2026-09-04" },
    "SDK/license installer" => ->(v) { v["jobs"][p::JOB]["steps"] << {"run" => "sdkmanager platforms"} },
    "cache import" => ->(v) { v["jobs"][p::JOB]["steps"] << {"uses" => "actions/cache@#{'a' * 40}"} },
    "simulator runtime" => ->(v) { v["jobs"][p::JOB]["steps"][4]["run"] = "xcrun simctl boot all" },
    "unlimited job" => ->(v) { v["jobs"][p::JOB].delete("timeout-minutes") },
    "changed job cap" => ->(v) { v["jobs"][p::JOB]["timeout-minutes"] = 181 },
    "no shared lease" => ->(v) { v["jobs"][p::JOB].delete("concurrency") },
    "whole state upload" => ->(v) { v["jobs"][p::JOB]["steps"][6]["with"]["path"] = "${{ runner.temp }}/**" },
    "upload before seal" => ->(v) { v["jobs"][p::JOB]["steps"][5, 2] = v["jobs"][p::JOB]["steps"][5, 2].reverse },
    "masked driver failure" => ->(v) { v["jobs"][p::JOB]["steps"][5]["env"]["P2PKIT_IPHONEOS_RUN_OUTCOME"] = "success" },
    "artifact failure not blocking" => ->(v) { v["jobs"][p::JOB]["steps"][7]["if"].sub!(" || steps.evidence.outcome != 'success'", "") },
    "product proof not blocking" => ->(v) { v["jobs"][p::JOB]["steps"][7]["if"].sub!(" || steps.public.outputs.product_passed != 'true'", "") },
}
p::STEPS.each_index do |index|
    %w[if continue-on-error env working-directory shell run timeout-minutes].each do |field|
        mutations["step #{index} override #{field}"] = ->(v) { v["jobs"][p::JOB]["steps"][index][field] = "unsafe" }
    end
end
{"fetch-depth" => 1, "persist-credentials" => true, "ref" => "main"}.each do |field, value|
    mutations["checkout #{field}"] = ->(v) { v["jobs"][p::JOB]["steps"][0]["with"][field] = value }
end
mutations.each do |name, mutate|
    changed = Marshal.load(Marshal.dump(workflow))
    mutate.call(changed)
    begin
        p.check(changed)
    rescue HeavyJobQueuePolicy::Error
        checks += 1
        next
    end
    abort "FATAL: unsafe iphoneos workflow accepted: #{name}"
end
hook = File.read(File.join(p::ROOT, "scripts/tests/release-workflow-test.sh"))
p.entrypoint(hook)
checks += 1
[
    hook.sub('ruby "$ROOT/scripts/tests/check-hosted-iphoneos-product-policy-test.rb"', "true"),
    hook.sub('python3 -I -B -S "$ROOT/scripts/tests/run-hosted-iphoneos-product-test.py"', "true"),
].each do |changed|
    begin
        p.entrypoint(changed)
    rescue HeavyJobQueuePolicy::Error
        checks += 1
        next
    end
    abort "FATAL: iphoneos control hook omission accepted"
end
puts "RESULT: PASS — #{checks} pure iphoneos workflow controls; no hosted/product execution"
