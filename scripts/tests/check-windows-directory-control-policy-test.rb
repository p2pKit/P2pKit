#!/usr/bin/env ruby
# Pure workflow/adverse policy checks. No dispatch, native execution or publication.
require "json"
require_relative "../check-heavy-job-queue-policy"
require_relative "../check-sample-app-workflow-policy"

module WindowsDirectoryControlPolicy
    Error = HeavyJobQueuePolicy::Error
    ROOT = File.expand_path("../..", __dir__)
    OPERATION = "windows-directory-fsync-control"
    HELPER = "windows-helper-controls"
    RUBY_CHECK = "ruby scripts/tests/check-windows-directory-control-policy-test.rb"
    PYTHON_CHECK = "python3 -B scripts/tests/run-windows-directory-control-test.py"
    CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    JAVA = "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961"
    UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    STEPNAME = "Verify Windows directory control policy"
    SAVE_JDK = <<~'PS'
        if ([string]::IsNullOrWhiteSpace($env:JAVA_HOME) -or $env:JAVA_HOME.Contains("`n") -or $env:JAVA_HOME.Contains("`r")) {
          throw 'Missing or invalid daemon JDK path'
        }
        Add-Content -LiteralPath $env:GITHUB_ENV -Encoding utf8 -Value "P2PKIT_AUDIT_JDK21=$env:JAVA_HOME"
    PS

    def self.need(condition, message)
        raise Error, message unless condition
    end

    def self.step(steps, index, expected)
        need(steps[index] == expected, "control step #{index + 1} changed admission, credential, action, command or retention contract")
    end

    def self.check(workflow)
        # The ordinary job now delivers main sample apps. Its narrow reviewed
        # contract is shared, not relaxed; witness authority below is unchanged.
        SampleAppWorkflowPolicy.check(workflow)
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") && !workflow.key?("defaults") &&
             !JSON.generate(workflow).match?(/secrets\.|id-token|pull_request_target/), "control must remain secret-free and contents-read")
        triggers = workflow.fetch("on") { workflow.fetch(true) }
        inputs = triggers.fetch("workflow_dispatch").fetch("inputs")
        need(inputs.keys.sort == %w[evidence_fingerprint evidence_public_key expected_sha expected_tree operation reviewed_base],
             "no arbitrary control inputs")
        expected = {"operation" => {"type" => "choice", "options" => ["desktop", "sample-apps", OPERATION, HELPER,
            "macos-arm64-admission", "macos-x64-admission", "dependency-lock-candidate", "dependency-lock-candidate-x64", "dependency-lock-candidate-macos14", "iphoneos-product"], "default" => "desktop", "required" => true}}
        %w[expected_sha expected_tree reviewed_base evidence_public_key evidence_fingerprint].each do |name|
            expected[name] = {"type" => "string", "required" => false, "default" => ""}
        end
        inputs.each do |name, value|
            need(value.is_a?(Hash) && value["description"].is_a?(String) &&
                 value.reject { |key, _| key == "description" } == expected[name], "exact operation/default/source inputs required")
        end
        need(workflow["concurrency"] == HeavyJobQueuePolicy::WORKFLOW_CONCURRENCY["desktop-cross-host.yml"],
             "control reruns cannot share ordinary cancelling workflow group")
        jobs = workflow.fetch("jobs")
        need(jobs.keys.sort == ["verify", OPERATION, HELPER, "mac-host-admission-probe", "dependency-lock-candidate", "iphoneos-product"].sort,
             "unexpected or missing Desktop/control job")
        helper(jobs.fetch(HELPER))
        job = jobs.fetch(OPERATION)
        need(job.keys.sort == %w[concurrency env if name runs-on steps timeout-minutes] &&
             job["name"] == OPERATION && job["runs-on"] == "windows-latest" && job["timeout-minutes"] == 110 &&
             job["if"] == HeavyJobQueuePolicy::CONDITIONS[["desktop-cross-host.yml", OPERATION]] &&
             job["concurrency"] == HeavyJobQueuePolicy::QUEUE, "native Windows job/queue/deadline/condition changed")
        need(job["env"] == {"P2PKIT_OPERATION" => "${{ inputs.operation }}", "P2PKIT_EXPECTED_SHA" => "${{ inputs.expected_sha }}",
             "P2PKIT_EXPECTED_TREE" => "${{ inputs.expected_tree }}", "PYTHONDONTWRITEBYTECODE" => "1", "PYTHONUNBUFFERED" => "1"},
             "control environment override or missing source binding")
        steps = job.fetch("steps")
        need(steps.length == 10, "extra/missing control step; no cache, publisher, download or arbitrary command path")
        step(steps, 0, {"name" => "Check out exact reviewed control source", "uses" => CHECKOUT,
            "env" => {"GIT_CONFIG_COUNT" => "1", "GIT_CONFIG_KEY_0" => "core.autocrlf", "GIT_CONFIG_VALUE_0" => "false"},
            "with" => {"ref" => "${{ github.sha }}", "fetch-depth" => 0, "persist-credentials" => false}})
        step(steps, 1, {"name" => "Admit genuine dispatch and exact clean source", "shell" => "pwsh",
            "run" => "python -B scripts/run-windows-directory-control.py admit\nexit $LASTEXITCODE\n"})
        step(steps, 2, {"name" => "Configure native daemon Java 21", "uses" => JAVA,
            "with" => {"distribution" => "temurin", "java-version" => "21", "architecture" => "x64"}})
        step(steps, 3, {"name" => "Retain daemon JDK path", "shell" => "pwsh", "run" => SAVE_JDK})
        step(steps, 4, {"name" => "Configure native wrapper and test Java 17", "uses" => JAVA,
            "with" => {"distribution" => "temurin", "java-version" => "17", "architecture" => "x64"}})
        step(steps, 5, {"name" => "Run current then method-preimage Windows witness", "id" => "control", "timeout-minutes" => 92,
            "shell" => "pwsh", "run" => "python -B scripts/run-windows-directory-control.py run\nexit $LASTEXITCODE\n"})
        %w[admission current preimage].each_with_index do |name, index|
            title = {"admission" => "admission", "current" => "current-source", "preimage" => "preimage"}.fetch(name)
            step(steps, 6 + index, {"name" => "Retain nonprivate #{title} evidence", "uses" => UPLOAD,
                "if" => "${{ always() && steps.control.outputs.artifacts_ready == 'true' }}", "with" => {
                    "name" => "windows-directory-fsync-#{name}-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
                    "path" => "${{ steps.control.outputs.public_root }}/#{name}", "retention-days" => 14,
                    "if-no-files-found" => "error", "include-hidden-files" => false, "overwrite" => false}})
        end
        step(steps, 9, {"name" => "Fail if safe retained evidence is unavailable",
            "if" => "${{ always() && steps.control.outputs.artifacts_ready != 'true' }}", "shell" => "pwsh",
            "run" => "throw 'Windows control did not seal safe original evidence; no acceptance claim'"})
    end

    def self.helper(job)
        need(job.keys.sort == %w[concurrency env if name permissions runs-on steps timeout-minutes] &&
             job["name"] == HELPER && job["runs-on"] == "windows-latest" && job["timeout-minutes"] == 25 &&
             job["permissions"] == {"contents" => "read"} && job["concurrency"] == HeavyJobQueuePolicy::QUEUE &&
             job["if"] == HeavyJobQueuePolicy::CONDITIONS[["desktop-cross-host.yml", HELPER]],
             "helper requires exact native host, no credentials, bounded envelope and serialized manual queue")
        need(job["env"] == {"P2PKIT_OPERATION" => "${{ inputs.operation }}", "P2PKIT_EXPECTED_SHA" => "${{ inputs.expected_sha }}",
             "P2PKIT_EXPECTED_TREE" => "${{ inputs.expected_tree }}", "P2PKIT_REVIEWED_BASE" => "${{ inputs.reviewed_base }}",
             "P2PKIT_EVIDENCE_PUBLIC_KEY" => "${{ inputs.evidence_public_key }}",
             "P2PKIT_EVIDENCE_FINGERPRINT" => "${{ inputs.evidence_fingerprint }}",
             "PYTHONDONTWRITEBYTECODE" => "1", "PYTHONUNBUFFERED" => "1"}, "helper identity must be actual with explicit public recipient")
        steps = job.fetch("steps")
        need(steps.length == 5, "helper forbids installers, caches, SDK/Gradle, arbitrary commands and bootstrap")
        step(steps, 0, {"name" => "Check out exact reviewed helper source", "uses" => CHECKOUT,
            "env" => {"GIT_CONFIG_COUNT" => "1", "GIT_CONFIG_KEY_0" => "core.autocrlf", "GIT_CONFIG_VALUE_0" => "false"},
            "with" => {"ref" => "${{ github.sha }}", "fetch-depth" => 0, "persist-credentials" => false}})
        step(steps, 1, {"name" => "Run fixed native Windows helper controls with private custody", "id" => "control",
            "timeout-minutes" => 21, "shell" => "pwsh",
            "run" => "python -I -B -S scripts/run-hosted-windows-helper-controls.py run\nexit $LASTEXITCODE\n"})
        step(steps, 2, {"name" => "Seal exact ciphertext after the helper interpreter returns", "id" => "seal",
            "if" => "${{ always() }}", "timeout-minutes" => 2, "shell" => "pwsh",
            "env" => {"P2PKIT_HELPER_RUN_OUTCOME" => "${{ steps.control.outcome }}"},
            "run" => "python -I -B -S scripts/run-hosted-windows-helper-controls.py validate-public\nexit $LASTEXITCODE\n"})
        step(steps, 3, {"name" => "Retain only sealed encrypted helper evidence", "id" => "ciphertext", "uses" => UPLOAD,
            "if" => "${{ always() && steps.seal.outcome == 'success' && steps.seal.outputs.artifacts_ready == 'true' }}", "with" => {
                "name" => "windows-helper-controls-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
                "path" => "${{ runner.temp }}/p2pkit-windows-helper-export-${{ github.run_id }}-${{ github.run_attempt }}/evidence.tar.gz.gpg\n" +
                    "${{ runner.temp }}/p2pkit-windows-helper-export-${{ github.run_id }}-${{ github.run_attempt }}/manifest.json\n",
                "retention-days" => 14, "if-no-files-found" => "error", "include-hidden-files" => false, "overwrite" => false}})
        step(steps, 4, {"name" => "Require passing controls and complete encrypted retention",
            "if" => "${{ always() && (steps.control.outcome != 'success' || steps.seal.outcome != 'success' || steps.seal.outputs.artifacts_ready != 'true' || steps.seal.outputs.controls_passed != 'true' || steps.ciphertext.outcome != 'success') }}",
            "shell" => "pwsh", "run" => "throw 'Windows helper controls or encrypted retention failed; private review is still required'"})
    end

    def self.entrypoints(ci, release, workflow_test)
        steps = ci.fetch("jobs").fetch("complete-gate").fetch("steps")
        matches = steps.select { |step| step["name"] == STEPNAME }
        need(matches == [{"name" => STEPNAME, "run" => "#{RUBY_CHECK}\n#{PYTHON_CHECK}\n"}],
             "CI control fixtures must be unconditional without overrides")
        scope = steps.find { |step| step["id"] == "scope" }
        need(scope && steps.index(matches.first) < steps.index(scope), "control policy must cover both CI scopes")
        [RUBY_CHECK, PYTHON_CHECK].each do |command|
            need(release.lines.map(&:strip).count(command) == 1, "release gate must execute exact control checks")
            script = command.split.last
            interpreter = command.start_with?("ruby") ? "ruby" : "python3 -B"
            need(workflow_test.lines.map(&:strip).count("#{interpreter} \"$ROOT/#{script}\"") == 1,
                 "release workflow tests must execute exact control checks")
        end
    end
end

P = WindowsDirectoryControlPolicy
workflows = HeavyJobQueuePolicy.read_workflows(File.join(P::ROOT, ".github/workflows"))
HeavyJobQueuePolicy.check(workflows)
workflow = workflows.fetch("desktop-cross-host.yml")
P.check(workflow)
checks = 1
mutations = {
    "secret scope" => ->(v) { v["env"] = {"TOKEN" => "${{ secrets.PUBLISH }}"} },
    "wrong default" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["operation"]["default"] = P::OPERATION },
    "arbitrary input" => ->(v) { (v["on"] || v[true])["workflow_dispatch"]["inputs"]["command"] = {"type" => "string"} },
    "missing PR coverage" => ->(v) { (v["on"] || v[true])["pull_request"]["paths"].pop },
    "ordinary skipped green" => ->(v) { v["jobs"]["verify"]["if"] = false },
    "missing unknown guard" => ->(v) { v["jobs"]["verify"]["steps"].shift },
    "ordinary tasks omitted" => ->(v) { v["jobs"]["verify"]["steps"].find { |s| s["id"] == "sample-build" }["run"] = "echo pass" },
    "wrong native host" => ->(v) { v["jobs"][P::OPERATION]["runs-on"] = "ubuntu-latest" },
    "control cancellation" => ->(v) { v["concurrency"]["cancel-in-progress"] = true },
    "missing queue" => ->(v) { v["jobs"][P::OPERATION].delete("concurrency") },
    "extended deadline" => ->(v) { v["jobs"][P::OPERATION]["timeout-minutes"] = 120 },
    "publisher environment" => ->(v) { v["jobs"][P::OPERATION]["environment"] = "release" },
    "extra cache step" => ->(v) { v["jobs"][P::OPERATION]["steps"] << {"uses" => "actions/cache@#{'a' * 40}"} },
}
{
    "wrong native host" => ->(j) { j["runs-on"] = "ubuntu-latest" },
    "credential scope" => ->(j) { j["permissions"] = {"contents" => "write"} },
    "missing serialized lease" => ->(j) { j.delete("concurrency") },
    "ordinary event fallback" => ->(j) { j["if"] = true },
    "widened helper deadline" => ->(j) { j["timeout-minutes"] = 90 },
    "ordinary recipient bootstrap" => ->(j) { j["env"]["P2PKIT_EVIDENCE_PUBLIC_KEY"] = "from-policy" },
    "fake hosted identity" => ->(j) { j["env"]["GITHUB_JOB"] = P::HELPER },
    "native installer" => ->(j) { j["steps"] << {"run" => "choco install gnupg"} },
    "Gradle/product scope" => ->(j) { j["steps"] << {"run" => "./gradlew check"} },
    "missing post-return identity" => ->(j) { j["steps"][2].delete("env") },
    "control failure ignored" => ->(j) { j["steps"][1]["continue-on-error"] = true },
    "unsafe raw upload" => ->(j) { j["steps"][3]["with"]["path"] = "${{ runner.temp }}/**" },
    "unsigned upload without seal" => ->(j) { j["steps"][3]["if"] = "${{ always() }}" },
    "skipped tests green" => ->(j) { j["steps"][4]["if"] = "${{ false }}" },
    "upload failure ignored" => ->(j) { j["steps"][4]["if"].sub!(" || steps.ciphertext.outcome != 'success'", "") },
}.each do |name, mutate|
    mutations["helper #{name}"] = ->(v) { mutate.call(v["jobs"][P::HELPER]) }
end
(0...5).each do |index|
    %w[if continue-on-error env working-directory shell].each do |field|
        mutations["helper step #{index} #{field} override"] = ->(v) { v["jobs"][P::HELPER]["steps"][index][field] = "unsafe" }
    end
end
{"fetch-depth" => 1, "persist-credentials" => true, "ref" => "main"}.each do |field, value|
    mutations["helper checkout #{field}"] = ->(v) { v["jobs"][P::HELPER]["steps"][0]["with"][field] = value }
end
(0...10).each do |index|
    %w[if continue-on-error env working-directory shell].each do |field|
        mutations["step #{index} #{field} override"] = ->(v) { v["jobs"][P::OPERATION]["steps"][index][field] = "unsafe" }
    end
end
{"fetch-depth" => 1, "persist-credentials" => true, "ref" => "main"}.each do |field, value|
    mutations["checkout #{field}"] = ->(v) { v["jobs"][P::OPERATION]["steps"][0]["with"][field] = value }
end
mutations.each do |name, mutate|
    altered = Marshal.load(Marshal.dump(workflow))
    mutate.call(altered)
    begin
        P.check(altered)
    rescue P::Error
        checks += 1
        next
    end
    raise "unsafe Windows control policy accepted: #{name}"
end
release = File.read(File.join(P::ROOT, "scripts/run-release-gate.sh"))
workflow_test = File.read(File.join(P::ROOT, "scripts/tests/release-workflow-test.sh"))
ci = workflows.fetch("ci.yml")
P.entrypoints(ci, release, workflow_test)
checks += 1
[
    [ci, release.sub(P::PYTHON_CHECK, "true"), workflow_test],
    [ci, release, workflow_test.sub('ruby "$ROOT/scripts/tests/check-windows-directory-control-policy-test.rb"', "true")],
].each do |inputs|
    begin
        P.entrypoints(*inputs)
    rescue P::Error
        checks += 1
        next
    end
    raise "control entrypoint bypass accepted"
end
puts "RESULT: PASS — Windows control workflow/default Desktop contract (#{checks} pure policy checks; no hosted claim)"
