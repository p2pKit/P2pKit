#!/usr/bin/env ruby
# Foundation ordinary app delivery through the closed custody caller only.
# No preview, lock writer, phone producer or alternate manual input path.
require "json"
require_relative "check-heavy-job-queue-policy"
require_relative "check-hosted-test-workflow-policy"

module SampleAppWorkflowPolicy
    Error = HeavyJobQueuePolicy::Error
    ROOT = File.expand_path("..", __dir__)
    CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    CUSTODY = HostedTestWorkflowPolicy
    PATHS = %w[.github/workflows/desktop-cross-host.yml .github/test-evidence-recipient.json .gitattributes .gitignore LICENSE gradlew gradlew.bat
        build.gradle.kts settings.gradle.kts gradle.properties
        buildSrc/** gradle/** scripts/** gradle.lockfile buildscript-gradle.lockfile
        samples/p2p-sample-android/** samples/sample-kmp-shared/** samples/p2p-sample-desktop/** samples/p2p-sample-desktop-ui/**
        samples/p2p-sample-diagnostics/** library/p2p-core/** library/p2p-transport-lan/**
        library/p2p-network-provisioning-desktop/** library/p2p-network-provisioning-android/**].freeze
    RUBY_CHECK = "ruby scripts/tests/check-sample-app-workflow-policy-test.rb"
    PYTHON_CHECK = "python3 -I -B scripts/tests/package-sample-apps-test.py"
    STEP_NAME = "Verify development sample artifact policy"
    SDK = <<~'SH'
        "$ANDROID_HOME"/cmdline-tools/latest/bin/sdkmanager 'platforms;android-36' 'platforms;android-37.0'
        grep -Fxq 'AndroidVersion.ApiLevel=36' "$ANDROID_HOME/platforms/android-36/source.properties"
        grep -Fxq 'AndroidVersion.ApiLevel=37.0' "$ANDROID_HOME/platforms/android-37.0/source.properties"
    SH

    def self.need(condition, message)
        raise Error, message unless condition
    end

    def self.helper(command)
        <<~SH
            python_bin=python3
            if [[ "$RUNNER_OS" == Windows ]]; then python_bin=python; fi
            "$python_bin" -I -B -S scripts/package-sample-apps.py #{command} --output "$RUNNER_TEMP/p2pkit-sample-apps"
        SH
    end

    def self.upload(kind)
        android = kind == "android"
        {
            "uses" => UPLOAD,
            "with" => {
                "name" => "sample-#{kind}-#{android ? '' : '${{ runner.os }}-${{ runner.arch }}-'}${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
                "path" => "${{ runner.temp }}/p2pkit-sample-apps/#{kind}/",
                "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
                "include-hidden-files" => false, "overwrite" => false,
            },
        }
    end

    def self.delivery_environment(package: true)
        environment = {
            "P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}",
            "P2PKIT_HOSTED_TEST_SEAL_OUTCOME" => "${{ steps.ordinary-seal.outcome }}",
            "P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME" => "${{ steps.ordinary-evidence.outcome }}",
            "P2PKIT_HOSTED_TEST_UPLOAD_AFTER_OUTCOME" => "${{ steps.ordinary-upload-after.outcome }}",
        }
        if package
            environment["P2PKIT_SAMPLE_PACKAGE_OUTCOME"] = "${{ steps.ordinary-package.outcome }}"
            environment["P2PKIT_SAMPLE_PACKAGE_SHA256"] = "${{ steps.ordinary-package.outputs.packaging_sha256 }}"
        end
        environment
    end

    def self.ordinary_package
        {"name" => "Verify original packaged samples before delivery", "id" => "ordinary-package",
         "if" => when_samples("steps.ordinary-required.outcome == 'success'"),
         "timeout-minutes" => 1, "shell" => "bash", "env" => delivery_environment(package: false),
         "run" => CUSTODY.python("desktop", "package-samples")}
    end

    def self.when_samples(extra = nil, always: false)
        CUSTODY.when_profile("desktop", CUSTODY::SAMPLE_INTENT + (extra ? " && " + extra : ""), always: always)
    end

    def self.ordinary_before(kind)
        extra = "steps.ordinary-required.outcome == 'success' && steps.ordinary-package.outcome == 'success' && steps.ordinary-package.outputs.packaging_ready == 'true'"
        environment = delivery_environment
        if kind == "android"
            extra += " && runner.os == 'Linux' && steps.ordinary-desktop-after.outcome == 'success' && steps.ordinary-desktop-after.outputs.upload_complete == 'true'"
            environment["P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME"] = "${{ steps.ordinary-desktop-after.outcome }}"
        end
        {"name" => "Admit the original #{kind} sample upload window", "id" => "ordinary-#{kind}-before",
         "if" => when_samples(extra), "shell" => "bash", "env" => environment,
         "run" => CUSTODY.python("desktop", "sample-upload-guard before --platform #{kind}")}
    end

    def self.ordinary_upload(kind)
        id = "ordinary-#{kind}-before"
        extra = "steps.#{id}.outcome == 'success' && steps.#{id}.outputs.upload_ready == 'true' && " +
            "(steps.#{id}.outputs.upload_timeout_minutes == '1' || steps.#{id}.outputs.upload_timeout_minutes == '2' || steps.#{id}.outputs.upload_timeout_minutes == '3')"
        extra += " && runner.os == 'Linux'" if kind == "android"
        upload(kind).merge("name" => kind == "android" ? "Upload ordinary Android development APK" : "Upload ordinary native Desktop development apps",
            "id" => "ordinary-#{kind}-apps", "if" => when_samples(extra),
            "timeout-minutes" => "${{ fromJSON(steps.#{id}.outputs.upload_timeout_minutes) }}")
    end

    def self.ordinary_after(kind)
        extra = "steps.ordinary-#{kind}-before.outcome == 'success' && steps.ordinary-#{kind}-before.outputs.upload_ready == 'true'"
        extra += " && runner.os == 'Linux'" if kind == "android"
        environment = delivery_environment
        environment["P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME"] = "${{ steps.ordinary-desktop-after.outcome }}" if kind == "android"
        environment["P2PKIT_SAMPLE_UPLOAD_OUTCOME"] = "${{ steps.ordinary-#{kind}-apps.outcome }}"
        environment["P2PKIT_SAMPLE_UPLOAD_GUARD_SHA256"] = "${{ steps.ordinary-#{kind}-before.outputs.upload_guard_sha256 }}"
        {"name" => "Verify #{kind} sample upload inside the original window", "id" => "ordinary-#{kind}-after",
         "if" => when_samples(extra, always: true), "shell" => "bash", "env" => environment,
         "run" => CUSTODY.python("desktop", "sample-upload-guard after --platform #{kind}")}
    end

    def self.ordinary_delivery
        environment = delivery_environment
        %w[desktop android].each do |kind|
            {"BEFORE" => "before", "UPLOAD" => "apps", "AFTER" => "after"}.each do |name, id|
                environment["P2PKIT_SAMPLE_#{kind.upcase}_#{name}_OUTCOME"] = "${{ steps.ordinary-#{kind}-#{id}.outcome }}"
            end
        end
        environment["ORDINARY_REQUIRED"] = "${{ steps.ordinary-required.outcome }}"
        environment["PACKAGING_READY"] = "${{ steps.ordinary-package.outputs.packaging_ready }}"
        environment["DESKTOP_UPLOAD_COMPLETE"] = "${{ steps.ordinary-desktop-after.outputs.upload_complete }}"
        environment["ANDROID_UPLOAD_COMPLETE"] = "${{ steps.ordinary-android-after.outputs.upload_complete }}"
        body = <<~'SH'
            test "$ORDINARY_REQUIRED" = success
            test "$P2PKIT_SAMPLE_PACKAGE_OUTCOME" = success
            test "$PACKAGING_READY" = true
            test "$P2PKIT_SAMPLE_DESKTOP_BEFORE_OUTCOME" = success
            test "$P2PKIT_SAMPLE_DESKTOP_UPLOAD_OUTCOME" = success
            test "$P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME" = success
            test "$DESKTOP_UPLOAD_COMPLETE" = true
            case "$RUNNER_OS" in
              Linux)
                test "$P2PKIT_SAMPLE_ANDROID_BEFORE_OUTCOME" = success
                test "$P2PKIT_SAMPLE_ANDROID_UPLOAD_OUTCOME" = success
                test "$P2PKIT_SAMPLE_ANDROID_AFTER_OUTCOME" = success
                test "$ANDROID_UPLOAD_COMPLETE" = true
                ;;
              Windows|macOS)
                test "$P2PKIT_SAMPLE_ANDROID_BEFORE_OUTCOME" = skipped
                test "$P2PKIT_SAMPLE_ANDROID_UPLOAD_OUTCOME" = skipped
                test "$P2PKIT_SAMPLE_ANDROID_AFTER_OUTCOME" = skipped
                test -z "$ANDROID_UPLOAD_COMPLETE"
                ;;
              *) exit 1 ;;
            esac
        SH
        {"name" => "Require complete ordinary sample delivery inside its original deadline", "id" => "ordinary-delivery",
         "if" => when_samples(nil, always: true), "shell" => "bash", "env" => environment,
         "run" => body + CUSTODY.python("desktop", "sample-delivery-guard")}
    end

    def self.steps
        [
            {"name" => "Check out repository", "uses" => CHECKOUT, "with" => {"fetch-depth" => 0, "persist-credentials" => false}},
            CUSTODY.activation("desktop"), CUSTODY.admission("desktop"),
            {"name" => "Bind fresh ordinary sample outputs to this run", "id" => "ordinary-output",
             "if" => when_samples, "shell" => "bash", "run" => helper("prepare")},
            CUSTODY.stage("desktop"), CUSTODY.restore("desktop"), CUSTODY.restore_guard("desktop"),
            CUSTODY.java, CUSTODY.daemon("desktop"),
            {"name" => "Verify the ordinary source wrapper", "id" => "ordinary-wrapper",
             "if" => CUSTODY.when_profile("desktop"), "shell" => "bash", "run" => "scripts/check-gradle-wrapper.sh"},
            {"name" => "Install Android compile platforms for the Linux APK producer", "id" => "sample-sdk",
             "if" => when_samples("runner.os == 'Linux'"),
             "shell" => "bash", "run" => SDK},
            CUSTODY.run("desktop"), CUSTODY.seal("desktop"), CUSTODY.before("desktop"),
            CUSTODY.upload("desktop"), CUSTODY.after("desktop"), CUSTODY.terminal("desktop"),
            ordinary_package,
            ordinary_before("desktop"), ordinary_upload("desktop"), ordinary_after("desktop"),
            ordinary_before("android"), ordinary_upload("android"), ordinary_after("android"),
            ordinary_delivery,
        ]
    end

    def self.check(workflow)
        keys = ["name", workflow.key?("on") ? "on" : true, "permissions", "concurrency", "jobs"]
        need(workflow.keys.length == keys.length && keys.all? { |key| workflow.key?(key) } &&
             workflow["name"] == "Desktop cross-host" && workflow["jobs"].keys == ["verify"] &&
             workflow["concurrency"] == HeavyJobQueuePolicy::WORKFLOW_CONCURRENCY["desktop-cross-host.yml"],
             "Foundation Desktop has only its ordinary job and unchanged per-ref supersession")
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") && !workflow.key?("defaults") &&
             !JSON.generate(workflow).match?(/secrets\.|id-token|pull_request_target/), "sample delivery must remain secret-free and contents-read")
        triggers = workflow.fetch("on") { workflow.fetch(true) }
        need(triggers.keys.sort == %w[pull_request push workflow_dispatch] &&
             triggers["push"] == {"branches" => ["main"]} &&
             triggers["pull_request"] == {"paths" => PATHS}, "every main push and exact PR sample-input coverage required")
        need([nil, {}].include?(triggers["workflow_dispatch"]), "ordinary Desktop manual dispatch must remain input-free")
        job = workflow.fetch("jobs").fetch("verify")
        need(job.keys.sort == %w[concurrency name permissions runs-on steps strategy timeout-minutes] &&
             job["permissions"] == {"contents" => "read", "actions" => "read"} &&
             job["name"] == "${{ matrix.os }}" && job["timeout-minutes"] == 30 &&
             job["concurrency"] == HeavyJobQueuePolicy::QUEUE &&
             job["runs-on"] == "${{ matrix.os }}" &&
             job["strategy"] == {"fail-fast" => false, "max-parallel" => 1,
                                 "matrix" => HeavyJobQueuePolicy::MATRICES[["desktop-cross-host.yml", "verify"]]},
             "preserve unconditional ordinary native matrix, identity, queue and deadline")
        expected = steps
        need(job["steps"].is_a?(Array) && job["steps"].length == expected.length, "sample setup/build/stop/pack/upload step count changed")
        expected.each_with_index do |step, index|
            need(job["steps"][index] == step, "sample step #{index + 1} changed its source, build, failure, cache or artifact contract")
        end
        token_steps = job["steps"].select { |step| JSON.generate(step).include?("github.token") || JSON.generate(step).include?("P2PKIT_ACTIONS_READ_TOKEN") }
        need(token_steps == [CUSTODY.stage("desktop")], "actions-read token belongs only to the original Desktop timing/consume preparation")
    end

    def self.entrypoints(ci, release, workflow_test)
        ci_steps = ci.fetch("jobs").fetch("complete-gate").fetch("steps")
        controls = ci_steps.select { |step| step["name"] == STEP_NAME }
        need(controls == [{"name" => STEP_NAME, "run" => "#{RUBY_CHECK}\n#{PYTHON_CHECK}\n"}], "sample controls must be unconditional")
        scope = ci_steps.find { |step| step["id"] == "scope" }
        need(scope && ci_steps.index(controls.first) < ci_steps.index(scope), "sample controls must cover both CI scopes")
        [RUBY_CHECK, PYTHON_CHECK].each do |command|
            need(release.lines.map(&:strip).count(command) == 1, "release gate must run the sample controls exactly once")
            interpreter, _, script = command.rpartition(" ")
            need(workflow_test.lines.map(&:strip).count("#{interpreter} \"$ROOT/#{script}\"") == 1,
                 "workflow controls must run the sample checks exactly once")
        end
    end
end

if $PROGRAM_NAME == __FILE__
    abort "Usage: #{$PROGRAM_NAME} [workflow-file]" if ARGV.length > 1
    file = ARGV.fetch(0, File.join(SampleAppWorkflowPolicy::ROOT, ".github/workflows/desktop-cross-host.yml"))
    begin
        SampleAppWorkflowPolicy.check(HeavyJobQueuePolicy.parse(File.read(file), file))
    rescue SampleAppWorkflowPolicy::Error, SystemCallError => error
        abort "FATAL: #{error.message}"
    end
    puts "RESULT: PASS — development sample workflow policy only; no build/runtime claim"
end
