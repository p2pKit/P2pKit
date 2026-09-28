#!/usr/bin/env ruby
# Offline YAML mutations and the actual routing/provider/terminal shell with synthetic
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
    workflow.fetch("jobs").fetch(profile == "jvm-library" ? "jvm-library-checks" : profile == "full" ? "complete-gate" : "verify")
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

# Explicit DATA outcomes/locators. These never acquire a native current, open
# a cache or call a controller. The real workflow shell is what is exercised.
def provider_model(origin)
    environment = {"RECIPIENT_ORIGIN" => origin}
    values = {
        "DEPENDENCY_SEED_READY" => "true", "DEPENDENCY_CACHE_READY" => "true", "NATIVE_PROVIDER_READY" => "true",
        "DEPENDENCY_SEED_HOME" => "/model/seed", "DEPENDENCY_SEED_STAGING_SHA256" => "a" * 64,
        "PREPARATION_SHA256" => "b" * 64, "RESTORATION_SHA256" => "c" * 64,
        "CACHE_KEY" => "model-exact-key", "CACHE_PATH" => "/model/cache",
    }
    %w[ordinary initial].each do |candidate|
        prefix = candidate.upcase
        environment["#{prefix}_PROVIDER"] = candidate == origin ? "success" : "skipped"
        values.each { |name, value| environment["#{prefix}_#{name}"] = candidate == origin ? value : "" }
    end
    environment["INITIAL_INITIAL_CURRENT_HISTORY_SHA256"] = origin == "initial" ? "d" * 64 : ""
    environment
end

def result_model(origin, profile)
    environment = provider_model(origin).merge("RECIPIENT_REQUIRED" => "success",
        "ORDINARY_ADMISSION" => origin == "ordinary" ? "success" : "skipped")
    %w[ordinary initial].each do |candidate|
        prefix, active = candidate.upcase, candidate == origin
        %w[RUN SEAL EVIDENCE UPLOAD_BEFORE UPLOAD_AFTER REQUIRED].each do |name|
            environment["#{prefix}_#{name}"] = active ? "success" : "skipped"
        end
        {"SEAL_ARTIFACTS_READY" => "true", "SEAL_PROFILE_PASSED" => "true",
         "UPLOAD_BEFORE_UPLOAD_READY" => "true", "UPLOAD_BEFORE_UPLOAD_GUARD_SHA256" => "e" * 64,
         "UPLOAD_BEFORE_UPLOAD_TIMEOUT_MINUTES" => "3", "UPLOAD_AFTER_UPLOAD_COMPLETE" => "true"}.each do |name, value|
            environment["#{prefix}_#{name}"] = active ? value : ""
        end
    end
    if profile == "desktop"
        %w[ORDINARY_OUTPUT SAMPLE_SDK ORDINARY_PACKAGE ORDINARY_DESKTOP_BEFORE ORDINARY_DESKTOP_APPS
           ORDINARY_DESKTOP_AFTER ORDINARY_ANDROID_BEFORE ORDINARY_ANDROID_APPS ORDINARY_ANDROID_AFTER
           ORDINARY_DELIVERY].each { |name| environment[name] = "skipped" }
        environment["SAMPLE_PACKAGING_REQUIRED"] = origin == "ordinary" ? "false" : ""
        %w[PACKAGING_READY PACKAGING_SHA256 SAMPLE_DESKTOP_UPLOAD_READY SAMPLE_DESKTOP_UPLOAD_GUARD_SHA256
           SAMPLE_DESKTOP_UPLOAD_TIMEOUT_MINUTES SAMPLE_DESKTOP_UPLOAD_COMPLETE SAMPLE_ANDROID_UPLOAD_READY
           SAMPLE_ANDROID_UPLOAD_GUARD_SHA256 SAMPLE_ANDROID_UPLOAD_TIMEOUT_MINUTES SAMPLE_ANDROID_UPLOAD_COMPLETE].each do |name|
            environment[name] = ""
        end
    end
    environment
end

# Per-field alternatives, not a permission to relax production types. Include
# case, truncation, empty and non-success GitHub outcomes, never conclusion.
def denied_values(value)
    case value
    when "success" then ["failure", "cancelled", "skipped", "true", ""]
    when "skipped" then ["success", "failure", "cancelled", ""]
    when "true" then ["false", "success", "TRUE", ""]
    when "false" then ["true", "", "invalid"]
    when "" then ["true", "success", "a" * 64]
    when "ordinary", "initial" then ["", "unknown", value == "ordinary" ? "initial" : "ordinary"]
    when /\A[0-9a-f]{64}\z/ then ["", "a" * 63, "A" * 64, "g" * 64]
    when "3" then ["", "0", "4", "true"]
    else [""]
    end
end

{"full" => ci, "desktop" => desktop}.each do |profile, workflow|
    check_profile(workflow, profile)
    checks += 1
    mutations = {
        "source route falsely succeeds" => ->(v) { v["jobs"][HeavyJobQueuePolicy::ROUTE_JOB]["steps"][-1]["run"] = "echo ready\n" },
        "acquisition before native admission" => ->(v) { ordinary_job(v, profile)["steps"].insert(1, {"run" => "./gradlew check"}) },
        "recipient route failure ignored" => ->(v) { ordinary_step(v, profile, "recipient-required")["continue-on-error"] = true },
        "admission bypass" => ->(v) { ordinary_step(v, profile, "ordinary-admission")["run"] = "echo admitted\n" },
        "forged identity" => ->(v) { ordinary_step(v, profile, "ordinary-admission")["env"] = {"GITHUB_EVENT_NAME" => "push"} },
        "stage omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "dependency-stage")) },
        "stage ignored" => ->(v) { ordinary_step(v, profile, "dependency-stage")["continue-on-error"] = true },
        "combined cache restore-save activated" => ->(v) { ordinary_job(v, profile)["steps"].insert(4, {"uses" => "actions/cache@#{'a' * 40}"}) },
        "old staging skips original job timing" => ->(v) { ordinary_step(v, profile, "dependency-stage")["run"] = P.python(profile, "stage-dependencies") },
        "restore omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "dependency-stage")) },
        "restore moving pin" => ->(v) { ordinary_step(v, profile, "dependency-stage")["uses"] = "actions/cache/restore@main" },
        "restore whole execution home" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["path"] = "~/.gradle" },
        "restore key not bound to plan" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["key"] = "latest" },
        "restore fallback prefix" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["restore-keys"] = "p2pkit-" },
        "restore cross-OS archive" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["enableCrossOsArchive"] = true },
        "restore miss silently cold" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["fail-on-cache-miss"] = false },
        "restore lookup instead of bytes" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["lookup-only"] = true },
        "restore allowance renewed" => ->(v) { ordinary_step(v, profile, "dependency-stage")["timeout-minutes"] = 10 },
        "restore cap renewed from constant" => ->(v) { ordinary_step(v, profile, "dependency-stage")["timeout-minutes"] = 3 },
        "restore dynamic cap widened" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["cache_restore_timeout_minutes"] = 4 },
        "restore failure ignored" => ->(v) { ordinary_step(v, profile, "dependency-stage")["continue-on-error"] = true },
        "restore after failed prepare" => ->(v) { ordinary_step(v, profile, "dependency-stage")["if"] = "${{ always() }}" },
        "restore guard omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "dependency-ready")) },
        "restore guard success-only" => ->(v) { ordinary_step(v, profile, "dependency-ready")["if"] = "${{ success() }}" },
        "restore guard no preparation binding" => ->(v) { ordinary_step(v, profile, "dependency-ready")["env"].delete("ORDINARY_PREPARATION_SHA256") },
        "restore guard substitutes outcome" => ->(v) { ordinary_step(v, profile, "dependency-ready")["env"]["ORDINARY_PROVIDER"] = "success" },
        "restore guard substitutes primary key" => ->(v) { ordinary_step(v, profile, "dependency-ready")["env"]["ORDINARY_CACHE_KEY"] = "request-key-not-original-provider" },
        "restore guard substitutes matched key" => ->(v) { ordinary_step(v, profile, "dependency-stage")["with"]["cache-matched-key"] = "request-key-not-original-provider" },
        "restore guard assumes hit" => ->(v) { ordinary_step(v, profile, "dependency-ready")["env"]["ORDINARY_DEPENDENCY_CACHE_READY"] = "true" },
        "wrong seed" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"]["P2PKIT_DEPENDENCY_SEED_STAGE_SHA256"] = "copied" },
        "failed stage admitted" => ->(v) { ordinary_step(v, profile, "ordinary-run")["if"] = "${{ always() }}" },
        "consume contract omitted" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!(" --consume-dependencies", "") },
        "empty seed masquerades as cache qualification" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!("--consume-dependencies", "--seed-dependencies") },
        "run no restore binding" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"].delete("P2PKIT_CACHE_RESTORATION_SHA256") },
        "run provisional restore qualification" => ->(v) { ordinary_step(v, profile, "ordinary-run")["env"]["P2PKIT_CACHE_GUARD_OUTCOME"] = "${{ steps.dependency-ready.outcome }}" },
        "echo instead of real run" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"] = "echo passed\n" },
        "wrong profile" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!("--profile #{profile}", "--profile invented") },
        "run failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-run")["continue-on-error"] = true },
        "provisional run output seals itself" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["run"] = "echo artifacts_ready=true >> \"$GITHUB_OUTPUT\"\n" },
        "seal failure ignored" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["continue-on-error"] = true },
        "seal allowance enlarged" => ->(v) { ordinary_step(v, profile, "ordinary-seal")["timeout-minutes"] = 3 },
        "seal loses run outcome" => ->(v) { ordinary_step(v, profile, "ordinary-seal").delete("env") },
        "unsealed upload" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["if"] = "${{ always() }}" },
        "raw private upload" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"]["path"] = "${{ runner.temp }}/**" },
        "whole export upload" => ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"]["path"] = "${{ steps.session-path.outputs.session_directory }}/export/" },
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
        "token in restore guard" => ->(v) { ordinary_step(v, profile, "dependency-ready")["env"]["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" },
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
        "recipient result guard omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "recipient-result")) },
        "recipient result success-only" => ->(v) { ordinary_step(v, profile, "recipient-result")["if"] = "${{ success() }}" },
        "recipient result uses conclusion" => ->(v) { ordinary_step(v, profile, "recipient-result")["env"]["INITIAL_REQUIRED"] = "${{ steps.initial-required.conclusion }}" },
        "recipient result ignores initial output leakage" => ->(v) { ordinary_step(v, profile, "recipient-result")["run"].sub!('test -z "$INITIAL_UPLOAD_AFTER_UPLOAD_COMPLETE"', "true") },
        "recipient result substitutes ordinary provider output" => ->(v) { ordinary_step(v, profile, "recipient-result")["env"]["INITIAL_RESTORATION_SHA256"] = "${{ steps.dependency-stage.outputs.restoration_sha256 }}" },
        "recipient result ignores native readiness" => ->(v) { ordinary_step(v, profile, "recipient-result")["run"].sub!('test "$INITIAL_NATIVE_PROVIDER_READY" = true', "true") },
        "recipient route guard conditional bypass" => ->(v) { ordinary_step(v, profile, "recipient-required")["if"] = "${{ success() }}" },
        "recipient route guard trusts conclusion" => ->(v) { ordinary_step(v, profile, "recipient-required")["env"]["ROUTE_RESULT"] = "${{ needs.recipient-route.conclusion }}" },
        "provider-ready accepts partial initial" => ->(v) { ordinary_step(v, profile, "dependency-ready")["run"].sub!('test "$INITIAL_NATIVE_PROVIDER_READY" = true', "true") },
        "provider-ready ignores opposite output" => ->(v) { ordinary_step(v, profile, "dependency-ready")["run"].sub!('test -z "$ORDINARY_PREPARATION_SHA256"', "true") },
        "setup bypasses provider closure" => ->(v) { ordinary_step(v, profile, "java")["if"] = P.when_profile(profile) },
        "session locator invents worker authority" => ->(v) { ordinary_step(v, profile, "session-path")["run"] += "echo admitted=true >> \"$GITHUB_OUTPUT\"\n" },
        "initial provider omitted" => ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, "initial-dependency-stage")) },
        "initial provider replaced by ordinary" => ->(v) { ordinary_step(v, profile, "initial-dependency-stage")["uses"] = "./.github/actions/ordinary-cache-provider" },
        "ordinary provider replaced by initial" => ->(v) { ordinary_step(v, profile, "dependency-stage")["uses"] = "./.github/actions/initial-ordinary-cache-provider" },
        "initial provider wrong profile" => ->(v) { ordinary_step(v, profile, "initial-dependency-stage")["with"]["profile"] = profile == "full" ? "desktop" : "full" },
        "initial provider unbound help" => ->(v) { ordinary_step(v, profile, "initial-dependency-stage")["with"]["tasks"] = "help" },
        "initial provider no read token" => ->(v) { ordinary_step(v, profile, "initial-dependency-stage")["env"].delete("P2PKIT_ACTIONS_READ_TOKEN") },
        "initial provider after ordinary admission" => ->(v) { ordinary_step(v, profile, "initial-dependency-stage")["if"].sub!("steps.ordinary-admission.outcome == 'skipped'", "steps.ordinary-admission.outcome == 'success'") },
        "initial run loses current history" => ->(v) { ordinary_step(v, profile, "initial-run")["env"].delete("P2PKIT_INITIAL_CURRENT_HISTORY_SHA256") },
        "initial run adopts ordinary command" => ->(v) { ordinary_step(v, profile, "initial-run")["run"] = P.python(profile, "run --consume-dependencies") },
        "initial seal renewed allowance" => ->(v) { ordinary_step(v, profile, "initial-seal")["timeout-minutes"] = 3 },
        "initial upload uses ordinary artifact name" => ->(v) { ordinary_step(v, profile, "initial-evidence")["with"]["name"] = ordinary_step(v, profile, "ordinary-evidence")["with"]["name"] },
        "initial upload no original guard hash" => ->(v) { ordinary_step(v, profile, "initial-upload-after")["env"].delete("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256") },
        "initial terminal trusts provisional run" => ->(v) { ordinary_step(v, profile, "initial-required")["env"]["PROFILE_PASSED"] = "${{ steps.initial-run.outputs.profile_passed }}" },
    }
    %w[run seal upload-before upload-after required].each do |suffix|
        id = "initial-#{suffix}"
        mutations["#{id} missing"] = ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, id)) }
        mutations["#{id} ignores failure"] = ->(v) { ordinary_step(v, profile, id)["continue-on-error"] = true }
        mutations["#{id} unconditionally succeeds"] = ->(v) { ordinary_step(v, profile, id)["run"] = "true\n" }
    end
    %w[run seal upload-before upload-after].each do |suffix|
        id = "initial-#{suffix}"
        mutations["#{id} no legitimate token"] = ->(v) { ordinary_step(v, profile, id)["env"].delete("P2PKIT_ACTIONS_READ_TOKEN") }
        mutations["#{id} retains service credential"] = ->(v) { ordinary_step(v, profile, id)["env"]["ACTIONS_RUNTIME_TOKEN"] = "${{ github.token }}" }
        mutations["#{id} selects ordinary origin"] = ->(v) { ordinary_step(v, profile, id)["if"].sub!("outputs.origin == 'initial'", "outputs.origin == 'ordinary'") }
    end
    %w[P2PKIT_DEPENDENCY_SEED_STAGE_OUTCOME P2PKIT_DEPENDENCY_SEED_STAGE_SHA256 P2PKIT_HOSTED_PREPARE_OUTCOME
       P2PKIT_HOSTED_PREPARE_SHA256 P2PKIT_CACHE_GUARD_OUTCOME P2PKIT_CACHE_RESTORATION_SHA256 P2PKIT_NATIVE_PROVIDER_OUTCOME].each do |key|
        mutations["initial run cross-origin #{key}"] = ->(v) {
            ordinary_step(v, profile, "initial-run")["env"][key] = ordinary_step(v, profile, "ordinary-run")["env"].fetch(key)
        }
    end
    {"if-no-files-found" => "warn", "name" => "latest", "retention-days" => 90,
     "overwrite" => true, "include-hidden-files" => true}.each do |key, value|
        mutations["unsafe upload #{key}"] = ->(v) { ordinary_step(v, profile, "ordinary-evidence")["with"][key] = value }
        mutations["unsafe initial upload #{key}"] = ->(v) { ordinary_step(v, profile, "initial-evidence")["with"][key] = value }
    end
    mutations["unsafe initial raw upload"] = ->(v) { ordinary_step(v, profile, "initial-evidence")["with"]["path"] = "${{ runner.temp }}/**" }
    mutations["unsafe initial upload renewed timeout"] = ->(v) { ordinary_step(v, profile, "initial-evidence")["timeout-minutes"] = 10 }
    mutations["initial upload bypasses seal"] = ->(v) { ordinary_step(v, profile, "initial-evidence")["if"] = "${{ always() }}" }
    if profile == "full"
        mutations.merge!({
            "JVM setup bypasses initial prerequisite" => ->(v) { v["jobs"]["jvm-library-checks"].delete("needs") },
            "JVM always-cleanup bypasses initial failure" => ->(v) { v["jobs"]["jvm-library-checks"]["if"] = "${{ always() }}" },
            "protected gate claims success" => ->(v) { v["jobs"][HeavyJobQueuePolicy::INITIAL_JOB]["steps"][-1]["run"] = "true\n" },
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

    # Real guards must refuse absent outcomes; source-stop removal provides no
    # synthetic route/provider result. These shells cannot acquire authority.
    %w[recipient-required dependency-ready].each do |id|
        status, _output = shell_result(ordinary_step(workflow, profile, id).fetch("run"), {})
        raise "#{profile}/#{id} accepted absent original outcomes" unless status.is_a?(Integer) && status != 0
        checks += 1
    end
    if profile == "full"
        # Actual fixed result-guard shell, not a GitHub scheduler simulation.
        # A skipped JVM job must not turn the required complete-gate green.
        guard = ordinary_job(ci, profile).fetch("steps").first.fetch("run")
        %w[success failure cancelled skipped true].push("").each do |outcome|
            code, text = shell_result(guard, {"JVM_CHECK_RESULT" => outcome})
            raise "required gate hid failed/skipped JVM dependency" unless (code == 0) == (outcome == "success") && text.empty?
            checks += 1
        end
    end

    route = ordinary_step(workflow, profile, "recipient-required")
    %w[ordinary initial].each do |origin|
        environment = {"ROUTE_RESULT" => "success", "RECIPIENT_ORIGIN" => origin,
            "ROUTE_SHA256" => "a" * 64, "INITIAL_GATE_RESULT" => origin == "ordinary" ? "skipped" : "success",
            "INITIAL_GATE_READY" => origin == "ordinary" ? "" : "true", "INITIAL_GATE_SHA256" => origin == "ordinary" ? "" : "b" * 64}
        raise "route model field drift" unless environment.keys.sort == route.fetch("env").keys.sort
        raise "valid source route rejected" unless shell_result(route.fetch("run"), environment) == [0, ""]
        checks += 1
        environment.each do |name, value|
            denied_values(value).each do |bad|
                raise "route accepted #{profile}/#{origin}/#{name}=#{bad.inspect}" if shell_result(route.fetch("run"), environment.merge(name => bad)).first == 0
                checks += 1
            end
        end
        # Neither success for ordinary nor skipped/failure for initial can be
        # hidden by supplying plausible ready/hash outputs.
        %w[success failure cancelled skipped].push("").each do |outcome|
            %w[true false].push("").each do |ready|
                modeled = environment.merge("INITIAL_GATE_RESULT" => outcome, "INITIAL_GATE_READY" => ready)
                expected = origin == "ordinary" ? outcome == "skipped" && ready == "" : outcome == "success" && ready == "true"
                raise "closed gate result table violated" unless (shell_result(route.fetch("run"), modeled).first == 0) == expected
                checks += 1
            end
        end
    end

    provider = ordinary_step(workflow, profile, "dependency-ready")
    final = ordinary_step(workflow, profile, "recipient-result")
    %w[ordinary initial].each do |origin|
        [[provider, provider_model(origin)], [final, result_model(origin, profile)]].each do |step, environment|
            raise "origin model field drift" unless environment.keys.sort == step.fetch("env").keys.sort
            raise "complete #{profile}/#{origin}/#{step['id']} rejected" unless shell_result(step.fetch("run"), environment) == [0, ""]
            checks += 1
            environment.each do |name, value|
                denied_values(value).each do |bad|
                    raise "partial/cross-origin result accepted: #{profile}/#{origin}/#{step['id']}/#{name}=#{bad.inspect}" if
                        shell_result(step.fetch("run"), environment.merge(name => bad)).first == 0
                    checks += 1
                end
            end
        end
        %w[1 2 3].each do |minutes|
            environment = result_model(origin, profile).merge("#{origin.upcase}_UPLOAD_BEFORE_UPLOAD_TIMEOUT_MINUTES" => minutes)
            raise "actual profile upload cap changed" unless
                (shell_result(final.fetch("run"), environment).first == 0) == (profile == "desktop" || minutes == "3")
            checks += 1
        end
    end

    initial_terminal = ordinary_step(workflow, profile, "initial-required")
    initial_good = initial_terminal.fetch("env").to_h { |key, value| [key, value.end_with?(".outcome }}") ? "success" : "true"] }
    raise "complete initial terminal rejected" unless shell_result(initial_terminal.fetch("run"), initial_good) == [0, ""]
    checks += 1
    initial_good.each do |key, value|
        denied_values(value).each do |bad|
            raise "initial terminal accepted #{profile}/#{key}=#{bad.inspect}" if
                shell_result(initial_terminal.fetch("run"), initial_good.merge(key => bad)).first == 0
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
        # The marked ordinary path still delegates complete host-specific
        # sample delivery to its original terminal. Initial can never select
        # that path, even if supplied the same-looking complete sample DATA.
        marked = result_model("ordinary", profile).merge("SAMPLE_PACKAGING_REQUIRED" => "true", "ORDINARY_DELIVERY" => "success")
        raise "marked ordinary final result rejected" unless shell_result(final.fetch("run"), marked) == [0, ""]
        checks += 1
        %w[failure cancelled skipped].push("").each do |bad|
            raise "marked ordinary delivery incomplete" if shell_result(final.fetch("run"), marked.merge("ORDINARY_DELIVERY" => bad)).first == 0
            checks += 1
        end
        {"SAMPLE_PACKAGING_REQUIRED" => "true", "ORDINARY_DELIVERY" => "success"}.each do |name, value|
            raise "initial path admitted sample delivery" if
                shell_result(final.fetch("run"), result_model("initial", profile).merge(name => value)).first == 0
            checks += 1
        end
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

# JVM is a distinct CI worker, not a FULL/Desktop alias. Expected steps are
# enumerated independently by the policy, never learned from these YAML bytes.
profile = "jvm-library"
P.check_full(ci)
checks += 1
mutations = {
    "missing whole-job source route" => ->(v) { ordinary_job(v, profile)["needs"].delete(HeavyJobQueuePolicy::ROUTE_JOB) },
    "missing whole-job protected gate" => ->(v) { ordinary_job(v, profile)["needs"].delete(HeavyJobQueuePolicy::INITIAL_JOB) },
    "unconditional job" => ->(v) { ordinary_job(v, profile)["if"] = "${{ always() }}" },
    "changed service selector" => ->(v) { ordinary_job(v, profile)["name"] = "JVM tests" },
    "extra host" => ->(v) { ordinary_job(v, profile)["strategy"]["matrix"]["include"] << {"os" => "macos-15"} },
    "concurrent matrix" => ->(v) { ordinary_job(v, profile)["strategy"]["max-parallel"] = 2 },
    "cancel matrix" => ->(v) { ordinary_job(v, profile)["strategy"]["fail-fast"] = true },
    "unshared queue" => ->(v) { ordinary_job(v, profile)["concurrency"]["group"] = "jvm-only" },
    "longer job" => ->(v) { ordinary_job(v, profile)["timeout-minutes"] = 31 },
    "write permission" => ->(v) { ordinary_job(v, profile)["permissions"]["contents"] = "write" },
    "missing actions read" => ->(v) { ordinary_job(v, profile)["permissions"].delete("actions") },
    "floating checkout" => ->(v) { ordinary_job(v, profile)["steps"].first["with"]["ref"] = "main" },
    "shallow checkout" => ->(v) { ordinary_job(v, profile)["steps"].first["with"]["fetch-depth"] = 1 },
    "persist checkout credential" => ->(v) { ordinary_job(v, profile)["steps"].first["with"]["persist-credentials"] = true },
    "setup before provider" => ->(v) {
        steps = ordinary_job(v, profile)["steps"]
        steps.insert(2, steps.delete(ordinary_step(v, profile, "java")))
    },
    "automatic Gradle cache" => ->(v) { ordinary_job(v, profile)["steps"].insert(2, {"uses" => "gradle/actions/setup-gradle@main"}) },
    "bare product" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"] = "./gradlew :p2p-core:jvmTest" },
    "unowned stop" => ->(v) { ordinary_job(v, profile)["steps"] << {"if" => "${{ always() }}", "run" => "./gradlew --stop"} },
    "missing JDK21" => ->(v) { ordinary_step(v, profile, "java")["with"]["java-version"] = "17" },
    "missing JDK17" => ->(v) { ordinary_step(v, profile, "java")["with"]["java-version"] = "21" },
    "SDK writer" => ->(v) { ordinary_job(v, profile)["steps"] << {"run" => "sdkmanager platforms"} },
    "package writer" => ->(v) { ordinary_job(v, profile)["steps"] << {"run" => "./gradlew packageMsi"} },
    "wrong admission type" => ->(v) { ordinary_step(v, profile, "ordinary-admission")["run"].sub!("--profile jvm-library", "--profile desktop") },
    "provider before admission" => ->(v) { ordinary_step(v, profile, "dependency-stage")["if"] = "${{ always() }}" },
    "provider guard ignores opposite output" => ->(v) { ordinary_step(v, profile, "dependency-ready")["run"].sub!('test -z "$ORDINARY_PREPARATION_SHA256"', "true") },
    "initial history omitted" => ->(v) { ordinary_step(v, profile, "initial-run")["env"].delete("P2PKIT_INITIAL_CURRENT_HISTORY_SHA256") },
    "missing native consume" => ->(v) { ordinary_step(v, profile, "ordinary-run")["run"].sub!(" --consume-dependencies", "") },
    "result trusts run boolean" => ->(v) { ordinary_step(v, profile, "ordinary-required")["env"]["PROFILE_PASSED"] = "${{ steps.ordinary-run.outputs.profile_passed }}" },
    "result trusts opposite source" => ->(v) { ordinary_step(v, profile, "recipient-result")["env"]["ORDINARY_SEAL_PROFILE_PASSED"] = "${{ steps.initial-seal.outputs.profile_passed }}" },
    "result ignores opposite skipped" => ->(v) { ordinary_step(v, profile, "recipient-result")["run"].sub!('test "$INITIAL_REQUIRED" = skipped', "true") },
    "result ignores upload" => ->(v) { ordinary_step(v, profile, "recipient-result")["run"].sub!('test "$ORDINARY_EVIDENCE" = success', "true") },
}
%w[recipient-required ordinary-wrapper session-path ordinary-admission dependency-stage initial-dependency-stage
   dependency-ready java ordinary-jdk21 ordinary-run initial-run ordinary-seal initial-seal ordinary-upload-before
   initial-upload-before ordinary-evidence initial-evidence ordinary-upload-after initial-upload-after
   ordinary-required initial-required recipient-result].each do |id|
    mutations["missing #{id}"] = ->(v) { ordinary_job(v, profile)["steps"].delete(ordinary_step(v, profile, id)) }
    mutations["ignored #{id} failure"] = ->(v) { ordinary_step(v, profile, id)["continue-on-error"] = true }
end
%w[ordinary initial].each do |origin|
    %w[run seal upload-before upload-after required].each do |suffix|
        id = "#{origin}-#{suffix}"
        mutations["#{id} success-only"] = ->(v) { ordinary_step(v, profile, id)["if"] = "${{ success() }}" }
        mutations["#{id} claims success"] = ->(v) { ordinary_step(v, profile, id)["run"] = "true\n" }
        mutations["#{id} service credentials"] = ->(v) { ordinary_step(v, profile, id)["env"]["ACTIONS_RUNTIME_TOKEN"] = "${{ github.token }}" }
    end
    id = "#{origin}-evidence"
    {"path" => "${{ runner.temp }}/**", "name" => "latest", "retention-days" => 7,
     "if-no-files-found" => "warn", "overwrite" => true, "include-hidden-files" => true}.each do |key, value|
        mutations["#{id} unsafe #{key}"] = ->(v) { ordinary_step(v, profile, id)["with"][key] = value }
    end
    mutations["#{id} renewed timeout"] = ->(v) { ordinary_step(v, profile, id)["timeout-minutes"] = 3 }
    mutations["#{origin} after no guard hash"] = ->(v) { ordinary_step(v, profile, "#{origin}-upload-after")["env"].delete("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256") }
end
mutations.each do |name, mutate|
    changed = Marshal.load(Marshal.dump(ci))
    mutate.call(changed)
    raise "JVM mutation had no effect: #{name}" if changed == ci
    begin
        P.check_full(changed)
    rescue P::Error
        checks += 1
        next
    end
    raise "unsafe JVM caller accepted: #{name}"
end
%w[ordinary initial].each do |origin|
    [["dependency-ready", provider_model(origin)], ["recipient-result", result_model(origin, profile)]].each do |id, environment|
        step = ordinary_step(ci, profile, id)
        raise "JVM model field drift" unless environment.keys.sort == step.fetch("env").keys.sort
        raise "complete JVM #{origin}/#{id} rejected" unless shell_result(step.fetch("run"), environment) == [0, ""]
        checks += 1
        environment.each do |name, value|
            denied_values(value).each do |bad|
                raise "JVM accepted partial #{origin}/#{id}/#{name}" if shell_result(step.fetch("run"), environment.merge(name => bad)).first == 0
                checks += 1
            end
        end
    end
    final = ordinary_step(ci, profile, "recipient-result")
    %w[1 2 3].each do |minutes|
        environment = result_model(origin, profile).merge("#{origin.upcase}_UPLOAD_BEFORE_UPLOAD_TIMEOUT_MINUTES" => minutes)
        raise "JVM short-job original upload allowance rejected" unless shell_result(final.fetch("run"), environment) == [0, ""]
        checks += 1
    end
    step = ordinary_step(ci, profile, "#{origin}-required")
    environment = step.fetch("env").to_h { |key, value| [key, value.end_with?(".outcome }}") ? "success" : "true"] }
    raise "complete JVM terminal rejected" unless shell_result(step.fetch("run"), environment) == [0, ""]
    checks += 1
    environment.each do |name, value|
        denied_values(value).each do |bad|
            raise "JVM terminal accepted #{name}" if shell_result(step.fetch("run"), environment.merge(name => bad)).first == 0
            checks += 1
        end
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
commands = P::CONTROL_COMMANDS
first, last = commands.first, commands.last
rooted_first, rooted_last = [first, last].map do |command|
    interpreter, _, script = command.rpartition(" ")
    "#{interpreter} \"$ROOT/#{script}\""
end
swapped_release = release.lines.map { |line| line.strip == first ? "#{last}\n" : line.strip == last ? "#{first}\n" : line }.join
swapped_workflow = workflow_test.lines.map { |line| line.strip == rooted_first ? "#{rooted_last}\n" : line.strip == rooted_last ? "#{rooted_first}\n" : line }.join
[[ci, swapped_release, workflow_test], [ci, release, swapped_workflow]].each do |inputs|
    begin
        P.entrypoints(*inputs)
    rescue P::Error
        checks += 1
        next
    end
    raise "reordered ordinary control registration accepted"
end
puts "RESULT: PASS — ordinary caller (#{checks} offline policy/synthetic-shell controls; ACTIVATION=HOLD, no runtime/cache qualification)"
