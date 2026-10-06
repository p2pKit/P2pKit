#!/usr/bin/env ruby
# Offline source controls only; no runner, Java, network or qualification.
require_relative "../check-heavy-job-queue-policy"

module JmdnsStartupWorkflow
    ROOT = File.expand_path("../..", __dir__)
    FILE = "audit-jmdns-startup-context.yml"
    INTERPRETER = "/Library/Developer/CommandLineTools/usr/bin/python3"
    ENTRY = "#{INTERPRETER} -I -B -S controller/scripts/run-hosted-jmdns-startup.py "
    REQUEST = {"P2PKIT_JMDNS_STARTUP_REQUEST" => "${{ toJSON(inputs) }}"}.freeze
    GUARD = REQUEST.merge(
        "P2PKIT_JMDNS_STARTUP_OUTCOME" => "${{ steps.startup.outcome }}",
        "P2PKIT_JMDNS_STARTUP_SUCCESS_SHA256" => "${{ steps.startup.outputs.successSha256 }}",
        "P2PKIT_JMDNS_STARTUP_FAILED_SHA256" => "${{ steps.startup.outputs.failedProductSha256 }}",
    ).freeze
    FAILED = "failure() && !cancelled() && steps.startup.outcome == 'failure' && steps.startup.outputs.failedProductSha256 != '' && steps.startup.outputs.successSha256 == ''"
    FAILED_CONDITIONS = ["${{ #{FAILED} }}", "${{ #{FAILED} && steps.failed_guard.outcome == 'success' }}",
        "${{ #{FAILED} && steps.failed_guard.outcome == 'success' && steps.failed_encrypted.outcome == 'success' }}"].freeze
    SOURCE_FETCH = <<~'BASH'
      set -euo pipefail
      test "$(git -C controller rev-parse --is-shallow-repository)" = true
      test -z "$(git -C controller for-each-ref --format='%(refname)' refs/tags)"
      git -C controller fetch --no-tags --no-recurse-submodules --unshallow origin '+refs/heads/*:refs/remotes/origin/*'
      test "$(git -C controller rev-parse --is-shallow-repository)" = false
      test -z "$(git -C controller for-each-ref --format='%(refname)' refs/tags)"
    BASH

    def self.require_control(condition)
        raise "unsafe direct-Java diagnostic workflow" unless condition
    end

    def self.check(workflow)
        events = workflow.fetch("on", workflow[true])
        require_control(workflow.keys.sort_by(&:to_s) == ["name", "on", "permissions", "env", "jobs"].sort_by(&:to_s) ||
            workflow.keys.sort_by(&:to_s) == ["name", true, "permissions", "env", "jobs"].sort_by(&:to_s))
        require_control(workflow["permissions"] == {"contents" => "read"} &&
            workflow["env"] == {"PYTHONDONTWRITEBYTECODE" => "1", "PYTHONUNBUFFERED" => "1",
                                "DEVELOPER_DIR" => "/Applications/Xcode_26.5.app/Contents/Developer"})
        require_control(events.keys.sort == %w[push workflow_dispatch] &&
            events["push"] == {"branches" => ["work/release-foundation-dependency-context-startup-*"],
                               "paths" => [".github/workflows/#{FILE}"]})
        inputs = events["workflow_dispatch"]["inputs"]
        require_control(inputs.keys.sort == %w[source_sha source_tree] && inputs.values.all? { |input|
            input.keys.sort == %w[description required type] && input["required"] == true && input["type"] == "string" })
        require_control(workflow["jobs"].keys == ["jmdns_startup"])
        job = workflow["jobs"]["jmdns_startup"]
        require_control(job.keys.sort == %w[concurrency defaults if runs-on steps timeout-minutes] &&
            job["if"] == HeavyJobQueuePolicy::CONDITIONS[[FILE, "jmdns_startup"]] &&
            job["concurrency"] == HeavyJobQueuePolicy::QUEUE && job["runs-on"] == "macos-26" &&
            job["timeout-minutes"] == 210 && job["defaults"] == {"run" => {"shell" => "bash"}})
        steps = job["steps"]
        require_control(steps.size == 13 && steps.all? { |step|
            !step.key?("continue-on-error") && step["timeout-minutes"].is_a?(Integer) && step["timeout-minutes"] > 0 } &&
            steps[0, 10].all? { |step| !step.key?("if") } && steps[10, 3].map { |step| step["if"] } == FAILED_CONDITIONS)
        require_control(steps.map { |step| step["timeout-minutes"] } == [1, 3, 3, 5, 1, 5, 165, 1, 10, 1, 1, 10, 1] &&
            steps[0, 7].sum { |step| step["timeout-minutes"] } +
            [steps[7, 3], steps[10, 3]].map { |tail| tail.sum { |step| step["timeout-minutes"] } }.max <= 210)
        require_control(steps[0]["shell"] == "#{INTERPRETER} -I -B -S {0}" && steps[0]["env"] == REQUEST)
        allocation = steps[0]["run"]
        ["SCOPE = 'DIRECT_JAVA_STARTUP_DIAGNOSTIC_V1'", "CLOCK_SCHEMA = 2",
         "CLOCK_DOMAIN = 'darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)'",
         "env.get('GITHUB_JOB') == 'jmdns_startup'", "env.get('RUNNER_ENVIRONMENT') == 'github-hosted'",
         "env.get('RUNNER_ARCH') == 'ARM64'", "env.get('RUNNER_OS') == 'macOS'",
         "0 < os.getuid() == os.geteuid()", "os.getgid() == os.getegid()",
         "set(request) == {'source_sha', 'source_tree'}",
         "request['source_sha'] == env['GITHUB_SHA'] == env['GITHUB_WORKFLOW_SHA']",
         "re.fullmatch(r'refs/heads/work/release-foundation-dependency-context-startup-[A-Za-z0-9-]+', ref)",
         "'p2pKit/P2pKit/.github/workflows/#{FILE}@' + ref", "require(wall < 1792508160 * 1000000000)",
         "parsed(raw)['inputs'] == request", "not any(name in env for name in ('P2PKIT_AUDIT_JOB_ID'",
         "tempfile.mkdtemp(prefix='p2pkit-jmdns-startup-', dir=temporary)",
         "source=request['source_sha'], sourceTree=request['source_tree']",
         "startedMonotonicNs=started, startedEpochNs=wall", "scope=SCOPE",
         "update = ('P2PKIT_JMDNS_STARTUP_OPERATION=' + str(parent)",
         "os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW", "os.fsync(output.fileno())"].each do |required|
            require_control(allocation.include?(required))
        end
        require_control(allocation.index("request['source_sha'] ==") < allocation.index("tempfile.mkdtemp") &&
            allocation.index("parsed(raw)['inputs'] == request") < allocation.index("tempfile.mkdtemp"))
        checkouts = steps.select { |step| step.fetch("uses", "").start_with?("actions/checkout@") }
        require_control(checkouts == [steps[1]] && steps[1]["uses"] == HeavyJobQueuePolicy::CHECKOUT &&
            steps[1]["with"] == {"ref" => "${{ github.sha }}", "path" => "controller", "fetch-depth" => 1,
                                 "fetch-tags" => false, "persist-credentials" => false})
        require_control(steps[2]["run"] == SOURCE_FETCH && steps[2]["env"] == {"GIT_TERMINAL_PROMPT" => "0"})
        [3, 5].zip(%w[21 17]).each do |index, version|
            require_control(steps[index]["uses"] == "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961" &&
                steps[index]["with"] == {"distribution" => "temurin", "java-version" => version})
        end
        require_control(steps[4]["run"] == "printf 'P2PKIT_AUDIT_JDK21=%s\\n' \"$JAVA_HOME\" >> \"$GITHUB_ENV\"")
        require_control(steps[6]["id"] == "startup" && steps[6]["run"] == ENTRY + "run" && steps[6]["env"] == REQUEST)
        [7, 9, 10, 12].zip(%w[before-upload after-upload before-failed-upload after-failed-upload]).each do |index, suffix|
            expected_env = GUARD.dup
            if [9, 12].include?(index)
                upload = index == 9 ? "encrypted" : "failed_encrypted"
                expected_env.merge!("P2PKIT_JMDNS_STARTUP_UPLOAD_OUTCOME" => "${{ steps.#{upload}.outcome }}",
                    "P2PKIT_JMDNS_STARTUP_ARTIFACT_ID" => "${{ steps.#{upload}.outputs.artifact-id }}",
                    "P2PKIT_JMDNS_STARTUP_ARTIFACT_DIGEST" => "${{ steps.#{upload}.outputs.artifact-digest }}")
            end
            require_control(steps[index]["run"] == ENTRY + suffix && steps[index]["env"] == expected_env)
        end
        require_control(steps[7]["id"] == "success_guard" && steps[10]["id"] == "failed_guard")
        uploads = steps.select { |step| step.fetch("uses", "").start_with?("actions/upload-artifact@") }
        require_control(uploads == [steps[8], steps[11]])
        [8, 11].zip(%w[encrypted failed-encrypted], %w[encrypted failed_encrypted],
                      %w[jmdns-startup-evidence jmdns-startup-failed-evidence]).each do |index, group, id, prefix|
            upload = steps[index]
            require_control(upload["id"] == id &&
                upload["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" &&
                upload["with"] == {
                    "name" => prefix + "-${{ github.run_id }}-${{ github.run_attempt }}",
                    "path" => %w[evidence.tar.gz.gpg manifest.json].map { |name|
                        "${{ env.P2PKIT_JMDNS_STARTUP_OPERATION }}/outputs/#{group}/#{name}\n" }.join,
                    "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
                    "overwrite" => false, "include-hidden-files" => false,
                })
        end
        require_control(!YAML.dump(workflow).match?(/secrets\.|github\.token|actions\/cache|setup-gradle|sudo|preferIPv|initial-recipient-execution|\.\/gradlew|publish-maven/))
    end
end

path = File.join(JmdnsStartupWorkflow::ROOT, ".github/workflows", JmdnsStartupWorkflow::FILE)
workflow = HeavyJobQueuePolicy.parse(File.read(path), path)
JmdnsStartupWorkflow.check(workflow)
checks = 1
mutations = [
    ->(w) { w["permissions"]["contents"] = "write" },
    ->(w) { w["concurrency"] = HeavyJobQueuePolicy::QUEUE },
    ->(w) { w.fetch("on", w[true])["push"]["branches"] = ["main"] },
    ->(w) { w.fetch("on", w[true])["workflow_dispatch"]["inputs"]["source_sha"]["required"] = false },
    ->(w) { w["jobs"]["jmdns_startup"]["if"] = "${{ always() }}" },
    ->(w) { w["jobs"]["jmdns_startup"]["runs-on"] = "macos-15" },
    ->(w) { w["jobs"]["jmdns_startup"]["environment"] = "initial-recipient-execution" },
    ->(w) { w["jobs"]["jmdns_startup"]["timeout-minutes"] = 211 },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][0]["run"].sub!("require(wall < 1792508160 * 1000000000)", "require(True)") },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][0]["run"].sub!("env['GITHUB_WORKFLOW_SHA']", "request['source_sha']") },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][0]["run"].sub!("scope=SCOPE", "scope='QUALIFICATION'") },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][1]["with"]["ref"] = "main" },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][1]["with"]["persist-credentials"] = true },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][2]["run"].sub!("--no-tags", "--tags") },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][5]["with"]["java-version"] = "21" },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][10]["if"].sub!("failure()", "always()") },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][10]["env"]["P2PKIT_JMDNS_STARTUP_FAILED_SHA256"] = "${{ steps.startup.outputs.successSha256 }}" },
    ->(w) { w["jobs"]["jmdns_startup"]["steps"][12]["env"]["P2PKIT_JMDNS_STARTUP_ARTIFACT_ID"] = "${{ steps.encrypted.outputs.artifact-id }}" },
]
workflow["jobs"]["jmdns_startup"]["steps"].each_index do |index|
    mutations << ->(w) { w["jobs"]["jmdns_startup"]["steps"][index]["continue-on-error"] = true }
    mutations << ->(w) { w["jobs"]["jmdns_startup"]["steps"][index]["if"] = "${{ always() }}" }
end
[8, 11].each do |index|
    mutations << ->(w) { w["jobs"]["jmdns_startup"]["steps"][index]["with"]["path"] = "${{ env.P2PKIT_JMDNS_STARTUP_OPERATION }}/**" }
    mutations << ->(w) { w["jobs"]["jmdns_startup"]["steps"][index]["with"]["retention-days"] = 90 }
    mutations << ->(w) { w["jobs"]["jmdns_startup"]["steps"][index]["with"]["overwrite"] = true }
end
mutations.each_with_index do |mutation, index|
    changed = Marshal.load(Marshal.dump(workflow))
    mutation.call(changed)
    raise "ineffective mutation #{index}" if Marshal.dump(changed) == Marshal.dump(workflow)
    begin
        JmdnsStartupWorkflow.check(changed)
    rescue StandardError
        checks += 1
        next
    end
    raise "direct-Java workflow accepted mutation #{index}"
end
puts "RESULT: PASS — #{checks} direct-Java workflow controls; no hosted or Release qualification"
