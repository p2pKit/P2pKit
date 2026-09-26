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
        "combined cache restore-save activated" => ->(v) { ordinary_job(v, profile)["steps"].insert(4, {"uses" => "actions/cache@#{'a' * 40}"}) },
        "old staging skips original job timing" => ->(v) { ordinary_step(v, profile, "dependency-stage")["run"].sub!("prepare-consume", "stage-dependencies") },
        "restore omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "dependency-restore")) },
        "restore moving pin" => ->(v) { ordinary_step(v, profile, "dependency-restore")["uses"] = "actions/cache/restore@main" },
        "restore whole execution home" => ->(v) { ordinary_step(v, profile, "dependency-restore")["with"]["path"] = "~/.gradle" },
        "restore key not bound to plan" => ->(v) { ordinary_step(v, profile, "dependency-restore")["with"]["key"] = "latest" },
        "restore fallback prefix" => ->(v) { ordinary_step(v, profile, "dependency-restore")["with"]["restore-keys"] = "p2pkit-" },
        "restore cross-OS archive" => ->(v) { ordinary_step(v, profile, "dependency-restore")["with"]["enableCrossOsArchive"] = true },
        "restore miss silently cold" => ->(v) { ordinary_step(v, profile, "dependency-restore")["with"]["fail-on-cache-miss"] = false },
        "restore lookup instead of bytes" => ->(v) { ordinary_step(v, profile, "dependency-restore")["with"]["lookup-only"] = true },
        "restore allowance renewed" => ->(v) { ordinary_step(v, profile, "dependency-restore")["timeout-minutes"] = 10 },
        "restore cap renewed from constant" => ->(v) { ordinary_step(v, profile, "dependency-restore")["timeout-minutes"] = 3 },
        "restore dynamic cap widened" => ->(v) { ordinary_step(v, profile, "dependency-restore")["if"].sub!("cache_restore_timeout_minutes == '3'", "cache_restore_timeout_minutes == '4'") },
        "restore failure ignored" => ->(v) { ordinary_step(v, profile, "dependency-restore")["continue-on-error"] = true },
        "restore after failed prepare" => ->(v) { ordinary_step(v, profile, "dependency-restore")["if"] = "${{ always() }}" },
        "restore guard omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "dependency-restore-guard")) },
        "restore guard success-only" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["if"] = "${{ success() }}" },
        "restore guard no preparation binding" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["env"].delete("P2PKIT_HOSTED_PREPARE_SHA256") },
        "restore guard substitutes outcome" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["env"]["P2PKIT_CACHE_RESTORE_OUTCOME"] = "success" },
        "restore guard substitutes primary key" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["env"]["P2PKIT_CACHE_RESTORE_PRIMARY_KEY"] = "${{ steps.dependency-stage.outputs.cache_key }}" },
        "restore guard substitutes matched key" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["env"]["P2PKIT_CACHE_RESTORE_MATCHED_KEY"] = "${{ steps.dependency-stage.outputs.cache_key }}" },
        "restore guard assumes hit" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["env"]["P2PKIT_CACHE_RESTORE_HIT"] = "true" },
        "wrong seed" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"]["P2PKIT_DEPENDENCY_SEED_STAGE_SHA256"] = "copied" },
        "failed stage admitted" => ->(v) { ordinary_step(v, profile, "ordinary-run")["if"] = "${{ always() }}" },
        "consume contract omitted" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!(" --consume-dependencies", "") },
        "empty seed masquerades as cache qualification" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!("--consume-dependencies", "--seed-dependencies") },
        "run no restore binding" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"].delete("P2PKIT_CACHE_RESTORATION_SHA256") },
        "run provisional restore qualification" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"]["P2PKIT_CACHE_GUARD_OUTCOME"] = "${{ steps.dependency-restore.outcome }}" },
        "echo instead of real run" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"] = "echo passed\n" },
        "wrong profile" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!("--profile #{profile}", "--profile invented") },
        "run failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-run")["continue-on-error"] = true },
        "provisional run output seals itself" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["run"] = "echo artifacts_ready=true >> \"$GITHUB_OUTPUT\"\n" },
        "seal failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["continue-on-error"] = true },
        "seal allowance enlarged" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["timeout-minutes"] = 3 },
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
        "global read token" => ->(v) { v["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
        "job read token" => ->(v) { ordinary_job(v, profile)["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
        "token in run" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"]["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" },
        "token in restore guard" => ->(v) { ordinary_step(v, profile, "dependency-restore-guard")["env"]["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" },
        "token in seal" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["env"]["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" },
        "missing original timing token" => ->(v) { ordinary_step(v, profile, "dependency-stage").delete("env") },
        "missing minimal actions read" => ->(v) { ordinary_job(v, profile)["permissions"].delete("actions") },
        "publisher permission" => ->(v) { ordinary_job(v, profile)["permissions"]["contents"] = "write" },
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
        "terminal ignores exact cache result" => ->(v) { ordinary_step(v, profile, "ordinary-required")["run"].sub!('test "$CACHE_READY" = true', "true") },
    }
    {"if-no-files-found" => "warn", "name" => "latest", "retention-days" => 90,
     "overwrite" => true, "include-hidden-files" => true}.each do |key, value|
        mutations["unsafe upload #{key}"] = ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"][key] = value }
    end
    if profile == "full"
        mutations.merge!({
            "JVM setup bypasses initial prerequisite" => ->(v) { v["jobs"]["jvm-library-checks"].delete("needs") },
            "JVM always-cleanup bypasses initial failure" => ->(v) { v["jobs"]["jvm-library-checks"]["if"] = "${{ always() }}" },
            "initial interlock claims success" => ->(v) { v["jobs"][HeavyJobQueuePolicy::INITIAL_JOB]["steps"][0]["run"] = "true\n" },
            "no JVM prerequisite" => ->(v) { ordinary_job(v, profile).delete("needs") },
            "longer job deadline" => ->(v) { ordinary_job(v, profile)["timeout-minutes"] = 90 },
            "hidden acquisition in prefix" => ->(v) { ordinary_job(v, profile)["steps"].find { |s| s["run"] }["run"] += "\n./gradlew check\n" },
        })
    else
        mutations["FULL profile used on Desktop"] = ->(v) { ordinary_step(v, profile, "ordinary-upload-before")["run"] = P.python("full", "upload-guard before") }
        mutations["Desktop upload gives renewed three minutes"] = ->(v) { ordinary_step(v, profile, "ordinary-evidence")["timeout-minutes"] = 3 }
        mutations["Desktop upload cap widened"] = ->(v) { ordinary_step(v, profile, "ordinary-evidence")["if"].sub!("upload_timeout_minutes == '3'", "upload_timeout_minutes == '4'") }
        mutations["ordinary direct preview build"] = ->(v) { ordinary_job(v, profile)["steps"].insert(1, {"run" => "./gradlew assemble"}) }
        mutations["preview stop after ordinary seal"] = ->(v) { ordinary_job(v, profile)["steps"] << {"if" => "${{ always() }}", "run" => "./gradlew --stop"} }
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
    if profile == "full"
        status, output = shell_result(ci.fetch("jobs").fetch(HeavyJobQueuePolicy::INITIAL_JOB).fetch("steps").first.fetch("run"), {})
        raise "initial interlock must fail without claiming admission" unless status == 125 &&
            output == "INITIAL_RECIPIENT_STAGE2=HOLD; WHOLE_JVM_JOB_ADMISSION_REQUIRED\n"
        checks += 1
        # Actual fixed result-guard shell, not a GitHub scheduler simulation.
        # A skipped JVM job must not turn the required complete-gate green.
        guard = ordinary_job(ci, profile).fetch("steps").first.fetch("run")
        %w[success failure cancelled skipped true].push("").each do |outcome|
            code, text = shell_result(guard, {"JVM_CHECK_RESULT" => outcome})
            raise "required gate hid failed/skipped JVM dependency" unless (code == 0) == (outcome == "success") && text.empty?
            checks += 1
        end
    end
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
        %w[Linux Windows macOS].each do |host|
            unmarked = good.merge("RUNNER_OS" => host, "SAMPLE_PACKAGING_REQUIRED" => "false",
                                  "SDK_OUTCOME" => "skipped", "ORDINARY_OUTPUT" => "skipped")
            raise "unmarked ordinary #{host} verification failed" unless shell_result(terminal.fetch("run"), unmarked).first == 0
            checks += 1
            {"ORDINARY_OUTPUT" => "success", "SDK_OUTCOME" => "success", "ORDINARY_RUN" => "skipped",
             "ORDINARY_EVIDENCE" => "skipped", "PROFILE_PASSED" => "false", "SAMPLE_PACKAGING_REQUIRED" => ""}.each do |key, bad|
                raise "unmarked ordinary #{host} admitted #{key}=#{bad}" if shell_result(terminal.fetch("run"), unmarked.merge(key => bad)).first == 0
                checks += 1
            end
        end
        %w[Windows macOS].each do |host|
            native = good.merge("RUNNER_OS" => host, "SDK_OUTCOME" => "skipped")
            raise "synthetic #{host} terminal positive failed" unless shell_result(terminal.fetch("run"), native).first == 0
            raise "unexpected #{host} SDK execution admitted" if shell_result(terminal.fetch("run"), native.merge("SDK_OUTCOME" => "success")).first == 0
            checks += 2
        end
        raise "unknown host admitted" if shell_result(terminal.fetch("run"), good.merge("RUNNER_OS" => "unknown")).first == 0
        checks += 1

        # Execute the actual final workflow shell only. The exact final Python
        # call is a shell function that checks argv and reports a MODEL marker;
        # no controller, clock, native API, provider or application is executed.
        delivery = ordinary_step(workflow, profile, "ordinary-delivery")
        dispatch_model = <<~'SH'
            python3() {
              test "$*" = '-I -B -S scripts/run-hosted-test-custody.py sample-delivery-guard --profile desktop'
              printf 'DELIVERY_GUARD_MODEL\n'
            }
            python() { python3 "$@"; }
        SH
        delivery_shell = dispatch_model + delivery.fetch("run")
        environment = delivery.fetch("env").to_h do |key, value|
            [key, value.end_with?(".outcome }}") ? "success" : key.end_with?("SHA256") ? "a" * 64 : "true"]
        end
        required = %w[ORDINARY_REQUIRED P2PKIT_SAMPLE_PACKAGE_OUTCOME PACKAGING_READY
            P2PKIT_SAMPLE_DESKTOP_BEFORE_OUTCOME P2PKIT_SAMPLE_DESKTOP_UPLOAD_OUTCOME
            P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME DESKTOP_UPLOAD_COMPLETE
            P2PKIT_SAMPLE_ANDROID_BEFORE_OUTCOME P2PKIT_SAMPLE_ANDROID_UPLOAD_OUTCOME
            P2PKIT_SAMPLE_ANDROID_AFTER_OUTCOME ANDROID_UPLOAD_COMPLETE]
        %w[Linux Windows macOS].each do |host|
            current = environment.merge("RUNNER_OS" => host)
            unless host == "Linux"
                %w[BEFORE UPLOAD AFTER].each { |name| current["P2PKIT_SAMPLE_ANDROID_#{name}_OUTCOME"] = "skipped" }
                current["ANDROID_UPLOAD_COMPLETE"] = ""
            end
            status, output = shell_result(delivery_shell, current)
            raise "synthetic delivery #{host} did not reach exact modeled dispatch" unless
                status == 0 && output == "DELIVERY_GUARD_MODEL\n"
            checks += 1
            required.each do |key|
                wrong = (%w[success failure cancelled skipped true false] + [""]).reject { |value| value == current[key] }
                wrong.each do |bad|
                    status, output = shell_result(delivery_shell, current.merge(key => bad))
                    raise "delivery shell admitted #{host}/#{key}=#{bad.inspect}" if status == 0 || output.include?("DELIVERY_GUARD_MODEL")
                    checks += 1
                end
            end
        end
        raise "delivery shell admitted unknown host" if
            shell_result(delivery_shell, environment.merge("RUNNER_OS" => "unknown")).first == 0
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
