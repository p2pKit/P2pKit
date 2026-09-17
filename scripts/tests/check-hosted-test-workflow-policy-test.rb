#!/usr/bin/env ruby
# Offline YAML mutations and the actual HOLD/terminal shell with synthetic
# outcomes. No controller/admission, GPG, cache, SDK, Gradle or hosted execution.
require "tempfile"
require "timeout"
require_relative "../check-sample-app-workflow-policy"

P = HostedTestWorkflowPolicy
workflows = HeavyJobQueuePolicy.read_workflows(File.join(P::ROOT, ".github/workflows"))
ci = workflows.fetch("ci.yml")
desktop = workflows.fetch("desktop-cross-host.yml")
checks = 0

def ordinary_job(workflow, profile)
    workflow.fetch("jobs").fetch(profile == "full" ? "complete-gate" : "verify")
end

def ordinary_step(workflow, profile, id)
    matches = ordinary_job(workflow, profile).fetch("steps").select { |step| step["id"] == id }
    raise "expected one #{profile}/#{id}" unless matches.length == 1
    matches.first
end

def check_profile(workflow, profile)
    profile == "full" ? P.check_full(workflow) : SampleAppWorkflowPolicy.check(workflow)
end

def shell_result(body, environment)
    Tempfile.create("p2pkit-ordinary-shell-") do |log|
        pid = Process.spawn({"PATH" => "/usr/bin:/bin"}.merge(environment),
                            "bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", body,
                            unsetenv_others: true, pgroup: true, out: log, err: log)
        begin
            status = Timeout.timeout(5) { Process.wait2(pid).last }
        rescue Timeout::Error
            Process.kill("KILL", -pid) rescue Errno::ESRCH
            Process.wait(pid) rescue Errno::ECHILD
            raise "bounded ordinary shell fixture timed out"
        end
        log.rewind
        [status.exitstatus, log.read]
    end
end

{"full" => ci, "desktop" => desktop}.each do |profile, workflow|
    check_profile(workflow, profile)
    checks += 1
    mutations = {
        "activation lifted" => ->(v) { ordinary_step(v, profile, "ordinary-activation")["run"] = "echo ready\n" },
        "acquisition before activation" => ->(v) { ordinary_job(v, profile)["steps"].insert(1, {"run" => "./gradlew check"}) },
        "activation ignored" => ->(v) { ordinary_step(v, profile, "ordinary-activation")["continue-on-error"] = true },
        "admission bypass" => ->(v) { ordinary_step(v, profile, "ordinary-admission")["run"] = "echo admitted\n" },
        "forged identity" => ->(v) { ordinary_step(v, profile, "ordinary-admission")["env"] = {"GITHUB_EVENT_NAME" => "push"} },
        "stage omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "dependency-stage")) },
        "stage ignored" => ->(v) { ordinary_step(v, profile, "dependency-stage")["continue-on-error"] = true },
        "cache provider activated" => ->(v) { ordinary_job(v, profile)["steps"].insert(4, {"uses" => "actions/cache@#{'a' * 40}"}) },
        "wrong seed" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"]["P2PKIT_DEPENDENCY_SEED_STAGE_SHA256"] = "copied" },
        "failed stage admitted" => ->(v) { ordinary_step(v, profile, "ordinary-run")["if"] = "${{ always() }}" },
        "seed contract omitted" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!(" --seed-dependencies", "") },
        "echo instead of real run" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"] = "echo passed\n" },
        "wrong profile" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!("--profile #{profile}", "--profile invented") },
        "run failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-run")["continue-on-error"] = true },
        "provisional run output seals itself" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["run"] = "echo artifacts_ready=true >> \"$GITHUB_OUTPUT\"\n" },
        "seal failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["continue-on-error"] = true },
        "seal loses run outcome" => ->(v) { ordinary_step(v, profile, "ordinary-seal").delete("env") },
        "unsealed upload" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["if"] = "${{ always() }}" },
        "raw private upload" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"]["path"] = "${{ runner.temp }}/**" },
        "whole export upload" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"]["path"] = "${{ steps.ordinary-admission.outputs.session_directory }}/export/" },
        "upload timeout enlarged" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["timeout-minutes"] = 10 },
        "terminal skipped on failure" => ->(v) { ordinary_step(v, profile, "ordinary-required")["if"] = "${{ success() }}" },
        "terminal failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-required")["continue-on-error"] = true },
        "terminal uses conclusion" => ->(v) { ordinary_step(v, profile, "ordinary-required")["env"]["ORDINARY_RUN"] = "${{ steps.ordinary-run.conclusion }}" },
        "terminal provisional green" => ->(v) { ordinary_step(v, profile, "ordinary-required")["env"]["PROFILE_PASSED"] = "${{ steps.ordinary-run.outputs.profile_passed }}" },
        "post-seal product writer" => ->(v) { ordinary_job(v, profile)["steps"] << {"run" => "./gradlew assemble"} },
        "shared-home stop" => ->(v) { ordinary_job(v, profile)["steps"] << {"run" => "./gradlew --stop"} },
    }
    {"if-no-files-found" => "warn", "name" => "latest", "retention-days" => 90,
     "overwrite" => true, "include-hidden-files" => true}.each do |key, value|
        mutations["unsafe upload #{key}"] = ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"][key] = value }
    end
    if profile == "full"
        mutations.merge!({
            "global read token" => ->(v) { v["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
            "job read token" => ->(v) { ordinary_job(v, profile)["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
            "token in seal" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["env"]["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" },
            "missing minimal actions read" => ->(v) { ordinary_job(v, profile)["permissions"].delete("actions") },
            "publisher permission" => ->(v) { ordinary_job(v, profile)["permissions"]["contents"] = "write" },
            "no JVM prerequisite" => ->(v) { ordinary_job(v, profile).delete("needs") },
            "longer job deadline" => ->(v) { ordinary_job(v, profile)["timeout-minutes"] = 90 },
            "hidden acquisition in prefix" => ->(v) { ordinary_job(v, profile)["steps"].find { |s| s["run"] }["run"] += "\n./gradlew check\n" },
            "before guard omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "ordinary-upload-before")) },
            "before guard after upload" => ->(v) {
                steps = ordinary_job(v, profile)["steps"]
                before = steps.index(ordinary_step(v, profile, "ordinary-upload-before"))
                steps[before], steps[before + 1] = steps[before + 1], steps[before]
            },
            "after guard success-only" => ->(v) { ordinary_step(v, profile, "ordinary-upload-after")["if"] = "${{ success() }}" },
            "after guard loses hash" => ->(v) { ordinary_step(v, profile, "ordinary-upload-after")["env"].delete("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256") },
            "after guard assumes success" => ->(v) { ordinary_step(v, profile, "ordinary-upload-after")["env"]["P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME"] = "success" },
            "terminal ignores upload window" => ->(v) { ordinary_step(v, profile, "ordinary-required")["run"].sub!('test "$UPLOAD_COMPLETE" = true', "true") },
        })
    else
        mutations["FULL-only API used on Desktop"] = ->(v) { ordinary_job(v, profile)["steps"] << P.before }
        mutations["ordinary direct preview build"] = ->(v) { ordinary_step(v, profile, "sample-build").delete("if") }
        mutations["preview stop after ordinary seal"] = ->(v) { ordinary_step(v, profile, "stop-sample-gradle")["if"] = "${{ always() }}" }
    end
    mutations.each do |name, mutate|
        changed = Marshal.load(Marshal.dump(workflow))
        mutate.call(changed)
        raise "mutation had no effect: #{profile}/#{name}" if changed == workflow
        begin
            check_profile(changed, profile)
        rescue P::Error
            checks += 1
            next
        end
        raise "unsafe ordinary caller accepted: #{profile}/#{name}"
    end

    status, output = shell_result(ordinary_step(workflow, profile, "ordinary-activation").fetch("run"), {})
    raise "literal activation did not fail before acquisition" unless status == 125 &&
        output == "ORDINARY_TEST_ACTIVATION=HOLD; QUALIFIED_DEPENDENCY_CACHE_REQUIRED\n"
    checks += 1
    terminal = ordinary_step(workflow, profile, "ordinary-required")
    good = terminal.fetch("env").to_h { |key, value| [key, value.end_with?(".outcome }}") ? "success" : "true"] }
    good["RUNNER_OS"] = profile == "full" ? "macOS" : "Linux"
    raise "synthetic terminal positive failed" unless shell_result(terminal.fetch("run"), good).first == 0
    checks += 1
    terminal.fetch("env").each do |key, value|
        adverse = value.end_with?(".outcome }}") ? %w[failure cancelled skipped] + [""] : ["false", ""]
        adverse.each do |bad|
            raise "terminal admitted #{profile}/#{key}=#{bad.inspect}" if
                shell_result(terminal.fetch("run"), good.merge(key => bad)).first == 0
            checks += 1
        end
    end
    if profile == "desktop"
        %w[Windows macOS].each do |host|
            native = good.merge("RUNNER_OS" => host, "SDK_OUTCOME" => "skipped")
            raise "synthetic #{host} terminal positive failed" unless shell_result(terminal.fetch("run"), native).first == 0
            raise "unexpected #{host} SDK execution admitted" if shell_result(terminal.fetch("run"), native.merge("SDK_OUTCOME" => "success")).first == 0
            checks += 2
        end
        raise "unknown host admitted" if shell_result(terminal.fetch("run"), good.merge("RUNNER_OS" => "unknown")).first == 0
        checks += 1
    end
end

release = File.read(File.join(P::ROOT, "scripts/run-release-gate.sh"))
workflow_test = File.read(File.join(P::ROOT, "scripts/tests/release-workflow-test.sh"))
P.entrypoints(ci, release, workflow_test)
checks += 1
P::CONTROL_COMMANDS.each do |command|
    interpreter, _, script = command.rpartition(" ")
    rooted = "#{interpreter} \"$ROOT/#{script}\""
    [[ci, release.sub(command, "true"), workflow_test],
     [ci, release, workflow_test.sub(rooted, "true")],
     [ci, release + "\n#{command}\n", workflow_test]].each do |inputs|
        begin
            P.entrypoints(*inputs)
        rescue P::Error
            checks += 1
            next
        end
        raise "ordinary entrypoint bypass accepted"
    end
end
puts "RESULT: PASS — ordinary caller (#{checks} offline policy/synthetic-shell controls; ACTIVATION=HOLD, no runtime/cache qualification)"
