#!/usr/bin/env ruby
# Development app delivery; ordinary runtime evidence uses the closed custody
# caller while the explicit sample-apps preview remains a separate build-only path.
require "json"
require_relative "check-heavy-job-queue-policy"
require_relative "check-hosted-test-workflow-policy"

module SampleAppWorkflowPolicy
    Error = HeavyJobQueuePolicy::Error
    ROOT = File.expand_path("..", __dir__)
    CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    JAVA = "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961"
    GRADLE = "gradle/actions/setup-gradle@9c971963bec38e04b3d30dcc455b5382be2fdbfb"
    UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    CUSTODY = HostedTestWorkflowPolicy
    PATHS = %w[.github/workflows/desktop-cross-host.yml .github/test-evidence-recipient.json .gitattributes .gitignore LICENSE gradlew gradlew.bat
        build.gradle.kts settings.gradle.kts gradle.properties
        buildSrc/** gradle/wrapper/** gradle/gradle-daemon-jvm.properties gradle/libs.versions.toml
        gradle/verification-metadata.xml gradle/windows-directory-control.init.gradle scripts/run-windows-directory-control.py
        scripts/package-sample-apps.py scripts/tests/package-sample-apps-test.py scripts/check-sample-app-workflow-policy.rb
        scripts/tests/check-sample-app-workflow-policy-test.rb scripts/tests/run-windows-directory-control-test.py
        scripts/tests/check-windows-directory-control-policy-test.rb scripts/tests/fixtures/windows-directory-binding/settings.gradle
        scripts/tests/fixtures/windows-directory-binding/build.gradle
        gradle/test-transcript-custody.init.gradle scripts/run-hosted-test-admission.py scripts/run-hosted-test-custody.py
        scripts/test-transcript-custody.py scripts/run-audit-command.py scripts/check-audit-receipt.py scripts/audit_processes.py
        scripts/hosted_dependency_cache.py scripts/hosted_dependency_seed.py scripts/hosted_dependency_seed_files.py scripts/hosted_evidence.py
        scripts/hosted_full_job_budget.py scripts/hosted_full_simulator.py scripts/hosted_full_supplements.py
        scripts/hosted_job_clock.py scripts/hosted_lock_resources.py scripts/hosted_primary_abi.py scripts/hosted_test_identity.py
        scripts/hosted_test_query.py scripts/hosted_test_evidence.py scripts/hosted_windows_evidence.py
        scripts/hosted_windows_files.py scripts/check-gradle-wrapper.sh scripts/check-hosted-test-workflow-policy.rb
        scripts/check-hosted-test-composition.py scripts/tests/check-hosted-test-workflow-policy-test.rb
        scripts/tests/check-hosted-test-composition-test.py scripts/tests/hosted-consume-delivery-test.py
        scripts/tests/hosted-desktop-job-budget-test.py gradle.lockfile buildscript-gradle.lockfile
        samples/p2p-sample-android/** samples/sample-kmp-shared/** samples/p2p-sample-desktop/** samples/p2p-sample-desktop-ui/**
        samples/p2p-sample-diagnostics/** library/p2p-core/** library/p2p-transport-lan/**
        library/p2p-network-provisioning-desktop/** library/p2p-network-provisioning-android/**].freeze
    RUBY_CHECK = "ruby scripts/tests/check-sample-app-workflow-policy-test.rb"
    PYTHON_CHECK = "python3 -I -B -S scripts/tests/package-sample-apps-test.py"
    STEP_NAME = "Verify development sample artifact policy"
    REJECT_UNKNOWN = <<~'SH'
        if [[ "$GITHUB_EVENT_NAME" == workflow_dispatch && "$P2PKIT_DESKTOP_OPERATION" != desktop && "$P2PKIT_DESKTOP_OPERATION" != sample-apps ]]; then
          echo 'FATAL: unknown Desktop dispatch operation' >&2
          exit 1
        fi
    SH
    SDK = <<~'SH'
        "$ANDROID_HOME"/cmdline-tools/latest/bin/sdkmanager 'platforms;android-36' 'platforms;android-37.0'
        grep -Fxq 'AndroidVersion.ApiLevel=36' "$ANDROID_HOME/platforms/android-36/source.properties"
        grep -Fxq 'AndroidVersion.ApiLevel=37.0' "$ANDROID_HOME/platforms/android-37.0/source.properties"
    SH
    BUILD = <<~'SH'
        tasks=(
          :p2p-sample-desktop:check
          :p2p-sample-desktop:installDist
          :p2p-sample-desktop-ui:test
          :p2p-sample-desktop-ui:checkRuntime
          :p2p-sample-desktop-ui:hotRunArgfile
          :p2p-sample-desktop-ui:createDistributable
        )
        # The explicit build-only operation does not execute the CLI/UI test suites.
        # The ordinary Desktop and PR/main verification task set is unchanged.
        if [[ "$P2PKIT_SAMPLE_ONLY" == true ]]; then
          tasks=(
            :p2p-sample-desktop:installDist
            :p2p-sample-desktop-ui:checkRuntime
            :p2p-sample-desktop-ui:hotRunArgfile
            :p2p-sample-desktop-ui:createDistributable
          )
        fi
        if [[ "$RUNNER_OS" == Linux ]]; then
          tasks+=(:p2p-sample-android:assembleDebug)
        fi
        case "$RUNNER_OS" in
          Linux) tasks+=(:p2p-sample-desktop-ui:packageDeb) ;;
          Windows) tasks+=(:p2p-sample-desktop-ui:packageMsi) ;;
          macOS) tasks+=(:p2p-sample-desktop-ui:packageDmg) ;;
          *) echo 'FATAL: unsupported installer host' >&2; exit 1 ;;
        esac
        ./gradlew --no-daemon "${tasks[@]}" \
          --dependency-verification strict --no-build-cache --max-workers=2 --no-parallel --console=plain \
          -Dorg.gradle.java.installations.auto-download=false \
          -Dorg.gradle.java.installations.fromEnv=JAVA_HOME_17_X64,JAVA_HOME_21_X64,JAVA_HOME_17_ARM64,JAVA_HOME_21_ARM64 \
          '-Dorg.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=768m -XX:+UseParallelGC -Dfile.encoding=UTF-8' \
          -Pkotlin.compiler.execution.strategy=in-process
    SH
    STOP = <<~'SH'
        ./gradlew --stop --console=plain \
          -Dorg.gradle.java.installations.auto-download=false \
          -Dorg.gradle.java.installations.fromEnv=JAVA_HOME_17_X64,JAVA_HOME_21_X64,JAVA_HOME_17_ARM64,JAVA_HOME_21_ARM64
    SH
    STOP_IF = "${{ always() && github.event_name == 'workflow_dispatch' && inputs.operation == 'sample-apps' && (steps.sample-build.outcome == 'success' || steps.sample-build.outcome == 'failure' || steps.sample-build.outcome == 'cancelled') }}"
    PACKAGE_IF = "${{ success() && github.event_name == 'workflow_dispatch' && inputs.operation == 'sample-apps' && steps.sample-build.outcome == 'success' && steps.stop-sample-gradle.outcome == 'success' }}"
    OWNED_HOME = <<~'SH'
        # runner.temp is not available in job-level env; export after allocation.
        gradle_home="$RUNNER_TEMP/p2pkit-sample-gradle"
        if [[ -e "$gradle_home" || -L "$gradle_home" ]]; then
          echo 'FATAL: sample Gradle home already exists' >&2
          exit 1
        fi
        # Use the native API: Git Bash's mkdir -m can fail changing Windows ACLs.
        "$python_bin" -I -B -S -c 'from pathlib import Path; import sys; Path(sys.argv[1]).mkdir(mode=0o700)' "$gradle_home"
        printf 'GRADLE_USER_HOME=%s\n' "$gradle_home" >> "$GITHUB_ENV"
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
            "name" => android ? "Upload Android development APK" : "Upload native Desktop development apps",
            "if" => android ? "${{ success() && runner.os == 'Linux' && steps.sample-packaging.outcome == 'success' }}" :
                "${{ success() && steps.sample-packaging.outcome == 'success' }}",
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
         "if" => CUSTODY.when_profile("desktop", "steps.ordinary-required.outcome == 'success'"),
         "timeout-minutes" => 1, "shell" => "bash", "env" => delivery_environment(package: false),
         "run" => CUSTODY.python("desktop", "package-samples")}
    end

    def self.ordinary_before(kind)
        extra = "steps.ordinary-required.outcome == 'success' && steps.ordinary-package.outcome == 'success' && steps.ordinary-package.outputs.packaging_ready == 'true'"
        environment = delivery_environment
        if kind == "android"
            extra += " && runner.os == 'Linux' && steps.ordinary-desktop-after.outcome == 'success' && steps.ordinary-desktop-after.outputs.upload_complete == 'true'"
            environment["P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME"] = "${{ steps.ordinary-desktop-after.outcome }}"
        end
        {"name" => "Admit the original #{kind} sample upload window", "id" => "ordinary-#{kind}-before",
         "if" => CUSTODY.when_profile("desktop", extra), "shell" => "bash", "env" => environment,
         "run" => CUSTODY.python("desktop", "sample-upload-guard before --platform #{kind}")}
    end

    def self.ordinary_upload(kind)
        id = "ordinary-#{kind}-before"
        extra = "steps.#{id}.outcome == 'success' && steps.#{id}.outputs.upload_ready == 'true' && " +
            "(steps.#{id}.outputs.upload_timeout_minutes == '1' || steps.#{id}.outputs.upload_timeout_minutes == '2' || steps.#{id}.outputs.upload_timeout_minutes == '3')"
        extra += " && runner.os == 'Linux'" if kind == "android"
        upload(kind).merge("name" => kind == "android" ? "Upload ordinary Android development APK" : "Upload ordinary native Desktop development apps",
            "id" => "ordinary-#{kind}-apps", "if" => CUSTODY.when_profile("desktop", extra),
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
         "if" => CUSTODY.when_profile("desktop", extra, always: true), "shell" => "bash", "env" => environment,
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
         "if" => CUSTODY.when_profile("desktop", nil, always: true), "shell" => "bash", "env" => environment,
         "run" => body + CUSTODY.python("desktop", "sample-delivery-guard")}
    end

    def self.steps
        [
            {"name" => "Reject unknown Desktop dispatch operations", "shell" => "bash",
             "env" => {"P2PKIT_DESKTOP_OPERATION" => "${{ inputs.operation }}"}, "run" => REJECT_UNKNOWN},
            {"name" => "Check out repository", "uses" => CHECKOUT, "with" => {"fetch-depth" => 0, "persist-credentials" => false}},
            CUSTODY.activation("desktop"), CUSTODY.admission("desktop"),
            {"name" => "Bind fresh ordinary sample outputs to this run", "id" => "ordinary-output",
             "if" => CUSTODY.when_profile("desktop"), "shell" => "bash", "run" => helper("prepare")},
            {"name" => "Bind fresh sample outputs and Gradle home to this run", "id" => "preview-output",
             "if" => CUSTODY::PREVIEW, "shell" => "bash",
             "run" => helper("prepare") + OWNED_HOME},
            CUSTODY.stage("desktop"), CUSTODY.restore("desktop"), CUSTODY.restore_guard("desktop"),
            CUSTODY.java, CUSTODY.daemon("desktop"),
            {"name" => "Validate wrapper and configure Gradle", "id" => "preview-gradle", "if" => CUSTODY::PREVIEW,
             "uses" => GRADLE,
             "with" => {"gradle-home-cache-excludes" => "caches/build-cache-1"}},
            {"name" => "Verify the ordinary source wrapper", "id" => "ordinary-wrapper",
             "if" => CUSTODY.when_profile("desktop"), "shell" => "bash", "run" => "scripts/check-gradle-wrapper.sh"},
            {"name" => "Install Android compile platforms for the Linux APK producer", "id" => "sample-sdk", "if" => "runner.os == 'Linux'",
             "shell" => "bash", "run" => SDK},
            {"name" => "Verify CLI, Desktop runtime, tests, Hot Reload tooling, and application images",
             "id" => "sample-build", "if" => CUSTODY::PREVIEW, "shell" => "bash",
             "env" => {"P2PKIT_SAMPLE_ONLY" => "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'sample-apps' }}"},
             "run" => BUILD},
            {"name" => "Stop the sample job's Gradle home on every attempted build", "id" => "stop-sample-gradle",
             "if" => STOP_IF, "shell" => "bash", "run" => STOP},
            CUSTODY.run("desktop"), CUSTODY.seal("desktop"), CUSTODY.before("desktop"),
            CUSTODY.upload("desktop"), CUSTODY.after("desktop"), CUSTODY.terminal("desktop"),
            {"name" => "Inspect and archive successful development sample apps", "id" => "sample-packaging",
             "if" => PACKAGE_IF, "shell" => "bash", "run" => helper("package")},
            upload("desktop"), upload("android"),
            ordinary_package,
            ordinary_before("desktop"), ordinary_upload("desktop"), ordinary_after("desktop"),
            ordinary_before("android"), ordinary_upload("android"), ordinary_after("android"),
            ordinary_delivery,
        ]
    end

    def self.check(workflow)
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") && !workflow.key?("defaults") &&
             !JSON.generate(workflow).match?(/secrets\.|id-token|pull_request_target/), "sample delivery must remain secret-free and contents-read")
        triggers = workflow.fetch("on") { workflow.fetch(true) }
        need(triggers.keys.sort == %w[pull_request push workflow_dispatch] &&
             triggers["push"] == {"branches" => ["main"]} &&
             triggers["pull_request"] == {"paths" => PATHS}, "every main push and exact PR sample-input coverage required")
        job = workflow.fetch("jobs").fetch("verify")
        need(job.keys.sort == %w[concurrency if name permissions runs-on steps strategy timeout-minutes] &&
             job["permissions"] == {"contents" => "read", "actions" => "read"} &&
             job["name"] == "${{ matrix.os }}" && job["timeout-minutes"] == 30 &&
             job["concurrency"] == HeavyJobQueuePolicy::QUEUE &&
             job["if"] == HeavyJobQueuePolicy::CONDITIONS[["desktop-cross-host.yml", "verify"]] &&
             job["runs-on"] == "${{ matrix.os }}" &&
             job["strategy"] == {"fail-fast" => false, "max-parallel" => 1,
                                 "matrix" => HeavyJobQueuePolicy::MATRICES[["desktop-cross-host.yml", "verify"]]},
             "preserve ordinary native matrix, identity, queue, deadline and fail-closed operation guard")
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
