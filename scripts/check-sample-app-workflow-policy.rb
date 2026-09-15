#!/usr/bin/env ruby
# Ordinary development app delivery only; no publisher or audit-host admission.
require "json"
require_relative "check-heavy-job-queue-policy"

module SampleAppWorkflowPolicy
    Error = HeavyJobQueuePolicy::Error
    ROOT = File.expand_path("..", __dir__)
    CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    JAVA = "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961"
    GRADLE = "gradle/actions/setup-gradle@9c971963bec38e04b3d30dcc455b5382be2fdbfb"
    UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    PATHS = %w[.github/workflows/desktop-cross-host.yml .gitattributes .gitignore LICENSE gradlew gradlew.bat
        build.gradle.kts settings.gradle.kts gradle.properties
        buildSrc/** gradle/wrapper/** gradle/gradle-daemon-jvm.properties gradle/libs.versions.toml
        gradle/verification-metadata.xml gradle/windows-directory-control.init.gradle scripts/run-windows-directory-control.py
        scripts/package-sample-apps.py scripts/tests/package-sample-apps-test.py scripts/check-sample-app-workflow-policy.rb
        scripts/tests/check-sample-app-workflow-policy-test.rb scripts/tests/run-windows-directory-control-test.py
        scripts/tests/check-windows-directory-control-policy-test.rb scripts/tests/fixtures/windows-directory-binding/settings.gradle
        scripts/tests/fixtures/windows-directory-binding/build.gradle gradle.lockfile buildscript-gradle.lockfile
        samples/p2p-sample-android/** samples/sample-kmp-shared/** samples/p2p-sample-desktop/** samples/p2p-sample-desktop-ui/**
        samples/p2p-sample-diagnostics/** library/p2p-core/** library/p2p-transport-lan/**
        library/p2p-network-provisioning-desktop/** library/p2p-network-provisioning-android/**].freeze
    RUBY_CHECK = "ruby scripts/tests/check-sample-app-workflow-policy-test.rb"
    PYTHON_CHECK = "python3 -I -B -S scripts/tests/package-sample-apps-test.py"
    STEP_NAME = "Verify development sample artifact policy"
    REJECT_UNKNOWN = <<~'SH'
        if [[ "$GITHUB_EVENT_NAME" == workflow_dispatch && "$P2PKIT_DESKTOP_OPERATION" != desktop ]]; then
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
        if [[ "$RUNNER_OS" == Linux ]]; then
          tasks+=(:p2p-sample-android:assembleDebug)
        fi
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
    STOP_IF = "${{ always() && (steps.sample-build.outcome == 'success' || steps.sample-build.outcome == 'failure' || steps.sample-build.outcome == 'cancelled') }}"
    PACKAGE_IF = "${{ success() && steps.sample-build.outcome == 'success' && steps.stop-sample-gradle.outcome == 'success' }}"
    OWNED_HOME = <<~'SH'
        # runner.temp is not available in job-level env; export after allocation.
        gradle_home="$RUNNER_TEMP/p2pkit-sample-gradle"
        if [[ -e "$gradle_home" || -L "$gradle_home" ]]; then
          echo 'FATAL: sample Gradle home already exists' >&2
          exit 1
        fi
        mkdir -m 700 "$gradle_home"
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

    def self.steps
        [
            {"name" => "Reject unknown Desktop dispatch operations", "shell" => "bash",
             "env" => {"P2PKIT_DESKTOP_OPERATION" => "${{ inputs.operation }}"}, "run" => REJECT_UNKNOWN},
            {"name" => "Check out repository", "uses" => CHECKOUT, "with" => {"persist-credentials" => false}},
            {"name" => "Bind fresh sample outputs and Gradle home to this run", "shell" => "bash",
             "run" => helper("prepare") + OWNED_HOME},
            {"name" => "Configure daemon Java 21 and wrapper Java 17", "uses" => JAVA,
             "with" => {"distribution" => "temurin", "java-version" => "21\n17\n"}},
            {"name" => "Validate wrapper and configure Gradle", "uses" => GRADLE,
             "with" => {"gradle-home-cache-excludes" => "caches/build-cache-1"}},
            {"name" => "Install Android compile platforms for the Linux APK producer", "if" => "runner.os == 'Linux'",
             "shell" => "bash", "run" => SDK},
            {"name" => "Verify CLI, Desktop runtime, tests, Hot Reload tooling, and application images",
             "id" => "sample-build", "shell" => "bash", "run" => BUILD},
            {"name" => "Stop the sample job's Gradle home on every attempted build", "id" => "stop-sample-gradle",
             "if" => STOP_IF, "shell" => "bash", "run" => STOP},
            {"name" => "Inspect and archive successful development sample apps", "id" => "sample-packaging",
             "if" => PACKAGE_IF, "shell" => "bash", "run" => helper("package")},
            upload("desktop"), upload("android"),
        ]
    end

    def self.check(workflow)
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") && !workflow.key?("defaults") &&
             !JSON.generate(workflow).match?(/secrets\.|id-token|pull_request_target/), "sample delivery must remain secret-free and contents-read")
        triggers = workflow.fetch("on") { workflow.fetch(true) }
        need(triggers.keys.sort == %w[pull_request push workflow_dispatch] &&
             triggers["push"] == {"branches" => ["main"], "paths" => PATHS} &&
             triggers["pull_request"] == {"paths" => PATHS}, "exact main/PR sample-input coverage required; no new doc-only builds")
        job = workflow.fetch("jobs").fetch("verify")
        need(job.keys.sort == %w[concurrency if name runs-on steps strategy timeout-minutes] &&
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
