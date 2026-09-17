#!/usr/bin/env ruby
# Exact ordinary caller wiring only. The literal activation HOLD is intentional;
# these source checks neither qualify a cache provider nor make a required gate green.
require "digest"
require "json"
require_relative "check-heavy-job-queue-policy"

module HostedTestWorkflowPolicy
    Error = HeavyJobQueuePolicy::Error
    ROOT = File.expand_path("..", __dir__)
    JAVA = "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961"
    UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    FULL = "steps.scope.outputs.full == 'true'"
    DESKTOP = "github.event_name != 'workflow_dispatch' || inputs.operation == 'desktop'"
    PREVIEW = "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'sample-apps' }}"
    CONTROL_NAME = "Verify ordinary custody caller policy"
    CONTROL_COMMANDS = ["ruby scripts/tests/check-hosted-test-workflow-policy-test.rb",
                        "python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py",
                        "python3 -I -B -S scripts/tests/hosted-controller-import-test.py"].freeze
    HOLD = <<~'SH'
        echo 'ORDINARY_TEST_ACTIVATION=HOLD; QUALIFIED_DEPENDENCY_CACHE_REQUIRED' >&2
        exit 125
    SH
    JDK21 = <<~'SH'
        case "$RUNNER_ARCH" in X64|ARM64) ;; *) echo 'FATAL: unsupported native Java architecture' >&2; exit 1 ;; esac
        daemon_variable="JAVA_HOME_21_${RUNNER_ARCH}"
        daemon_home="${!daemon_variable}"
        case "$daemon_home" in ''|*$'\n'*|*$'\r'*) echo 'FATAL: missing or invalid daemon JDK path' >&2; exit 1 ;; esac
        printf 'P2PKIT_AUDIT_JDK21=%s\n' "$daemon_home" >> "$GITHUB_ENV"
    SH
    ENTRYPOINTS = <<~'SH'
        scripts/check-gradle-wrapper.sh
        scripts/tests/check-gradle-wrapper-test.sh
        scripts/tests/check-release-tag-test.sh
        scripts/tests/check-release-identity-test.sh
        scripts/check-release-metadata.sh
        scripts/tests/check-maven-release-environment-test.sh
        scripts/tests/check-maven-namespace-access-test.sh
        scripts/tests/check-maven-central-version-test.sh
        scripts/tests/publish-central-portal-bundle-test.sh
        scripts/tests/install-xcodegen-test.sh
        scripts/tests/release-workflow-test.sh
        scripts/tests/check-sample-run-profiles.sh
        scripts/tests/check-repository-layout.sh
        scripts/tests/check-osv-lockfile-coverage.sh
        scripts/tests/check-markdown-links.sh
        scripts/tests/classify-ci-scope-test.sh
        scripts/tests/resolve-ci-scope-test.sh
        scripts/tests/check-git-whitespace-test.sh
        scripts/tests/check-kotlin-toolchain-policy-test.sh
        scripts/tests/run-ios-app-test.sh
    SH
    SDK = <<~'SH'
        "$ANDROID_HOME"/cmdline-tools/latest/bin/sdkmanager 'platforms;android-36' 'platforms;android-37.0'
        grep -Fxq 'AndroidVersion.ApiLevel=36' "$ANDROID_HOME/platforms/android-36/source.properties"
        grep -Fxq 'AndroidVersion.ApiLevel=37.0' "$ANDROID_HOME/platforms/android-37.0/source.properties"
    SH
    # Reviewed pre-acquisition CI prefix with the offline caller/composition and
    # cold controller-import controls. Canonical key ordering; no value is derived
    # from the workflow here.
    # This fences even a product command inserted in an otherwise named policy step.
    FULL_PREFIX_SHA256 = "e36b33b4316970b3fca74256a655287dc7068dbe689938347d0a0d65bcbc24b4"

    def self.need(value, message)
        raise Error, message unless value
    end

    def self.canonical(value)
        case value
        when Hash then value.keys.sort.to_h { |key| [key, canonical(value.fetch(key))] }
        when Array then value.map { |entry| canonical(entry) }
        else value
        end
    end

    def self.condition(profile)
        profile == "full" ? FULL : DESKTOP
    end

    def self.when_profile(profile, extra = nil, always: false)
        "${{ #{always ? 'always()' : 'success()'} && (#{condition(profile)})#{extra ? ' && ' + extra : ''} }}"
    end

    def self.python(profile, arguments)
        command = "scripts/run-hosted-test-custody.py #{arguments} --profile #{profile}"
        return "python3 -I -B -S #{command}\n" if profile == "full"
        <<~SH
            python_bin=python3
            if [[ "$RUNNER_OS" == Windows ]]; then python_bin=python; fi
            "$python_bin" -I -B -S #{command}
        SH
    end

    def self.activation(profile)
        {"name" => "Hold ordinary #{profile} acquisition until cache qualification", "id" => "ordinary-activation",
         "if" => when_profile(profile), "shell" => "bash", "run" => HOLD}
    end

    def self.admission(profile)
        roles = profile == "full" ? "" : "  Linux/X64) role=linux-x64 ;;\n  Windows/X64) role=windows-x64 ;;\n"
        body = <<~SH
            python_bin=python3
            if [[ "$RUNNER_OS" == Windows ]]; then python_bin=python; fi
            case "$RUNNER_OS/$RUNNER_ARCH" in
            #{roles}  macOS/ARM64) role=macos-arm64 ;;
              macOS/X64) role=macos-x64 ;;
              *) echo 'FATAL: unsupported ordinary native host' >&2; exit 1 ;;
            esac
            "$python_bin" -I -B -S scripts/run-hosted-test-admission.py --profile #{profile} \\
              --root "$GITHUB_WORKSPACE" \\
              --evidence-directory "$RUNNER_TEMP/p2pkit-test-admission-#{profile}-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT-$role"
            printf 'session_directory=%s/p2pkit-test-#{profile}-%s-%s-%s\\n' "$RUNNER_TEMP" "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT" "$role" >> "$GITHUB_OUTPUT"
        SH
        {"name" => "Admit ordinary #{profile} source and trusted recipient policy", "id" => "ordinary-admission",
         "if" => when_profile(profile), "shell" => "bash", "run" => body}
    end

    def self.stage(profile)
        {"name" => "Allocate separate ordinary dependency staging", "id" => "dependency-stage",
         "if" => when_profile(profile), "shell" => "bash", "run" => python(profile, "stage-dependencies")}
    end

    def self.java(profile = nil)
        value = {"name" => "Configure daemon Java 21 and wrapper Java 17", "id" => "java", "uses" => JAVA,
                 "with" => {"distribution" => "temurin", "java-version" => "21\n17\n"}}
        value["if"] = when_profile(profile) if profile
        value
    end

    def self.daemon(profile)
        {"name" => "Bind the native ordinary daemon JDK", "id" => "ordinary-jdk21",
         "if" => when_profile(profile), "shell" => "bash", "run" => JDK21}
    end

    def self.run(profile)
        environment = {
            "P2PKIT_DEPENDENCY_SEED_STAGE_OUTCOME" => "${{ steps.dependency-stage.outcome }}",
            "P2PKIT_DEPENDENCY_SEED_STAGE_SHA256" => "${{ steps.dependency-stage.outputs.dependency_seed_staging_sha256 }}",
        }
        if profile == "full"
            environment["DEVELOPER_DIR"] = "/Applications/Xcode_26.5.app/Contents/Developer"
            environment["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}"
        end
        {"name" => "Run ordinary #{profile} with private custody", "id" => "ordinary-run",
         "if" => when_profile(profile, "steps.dependency-stage.outcome == 'success' && steps.dependency-stage.outputs.dependency_seed_ready == 'true'"),
         "shell" => "bash", "env" => environment,
         "run" => python(profile, "run").sub(" --profile #{profile}", " --profile #{profile} --seed-dependencies")}
    end

    def self.seal(profile)
        {"name" => "Seal ordinary #{profile} evidence after controller return", "id" => "ordinary-seal",
         "if" => when_profile(profile, "steps.ordinary-run.outcome == 'success'", always: true),
         "shell" => "bash", "env" => {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}"},
         "run" => python(profile, "validate-public")}
    end

    def self.sealed
        "steps.ordinary-run.outcome == 'success' && steps.ordinary-seal.outcome == 'success' && steps.ordinary-seal.outputs.artifacts_ready == 'true'"
    end

    def self.before
        {"name" => "Admit the original FULL evidence upload window", "id" => "ordinary-upload-before",
         "if" => when_profile("full", sealed, always: true), "shell" => "bash",
         "env" => {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}",
                   "P2PKIT_HOSTED_TEST_SEAL_OUTCOME" => "${{ steps.ordinary-seal.outcome }}"},
         "run" => python("full", "upload-guard before")}
    end

    def self.upload(profile)
        extra = sealed
        extra += " && steps.ordinary-upload-before.outcome == 'success' && steps.ordinary-upload-before.outputs.upload_ready == 'true' && steps.ordinary-upload-before.outputs.upload_timeout_minutes == '3'" if profile == "full"
        {"name" => "Upload only sealed ordinary #{profile} evidence", "id" => "ordinary-evidence",
         "if" => when_profile(profile, extra, always: true), "timeout-minutes" => 3, "uses" => UPLOAD,
         "with" => {
             "name" => "ordinary-#{profile}-evidence-${{ runner.os }}-${{ runner.arch }}-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
             "path" => "${{ steps.ordinary-admission.outputs.session_directory }}/export/evidence.tar.gz.gpg\n${{ steps.ordinary-admission.outputs.session_directory }}/export/manifest.json\n",
             "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
             "include-hidden-files" => false, "overwrite" => false,
         }}
    end

    def self.after
        {"name" => "Verify FULL upload completed inside its original window", "id" => "ordinary-upload-after",
         "if" => when_profile("full", "#{sealed} && steps.ordinary-upload-before.outcome == 'success' && steps.ordinary-upload-before.outputs.upload_ready == 'true'", always: true),
         "shell" => "bash",
         "env" => {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}",
                   "P2PKIT_HOSTED_TEST_SEAL_OUTCOME" => "${{ steps.ordinary-seal.outcome }}",
                   "P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME" => "${{ steps.ordinary-evidence.outcome }}",
                   "P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256" => "${{ steps.ordinary-upload-before.outputs.upload_guard_sha256 }}"},
         "run" => python("full", "upload-guard after")}
    end

    def self.terminal(profile)
        outcomes = %w[ordinary-activation ordinary-admission dependency-stage java ordinary-jdk21]
        outcomes += profile == "full" ? %w[ordinary-xcodegen ordinary-sdk ordinary-entrypoints] : %w[ordinary-output ordinary-wrapper]
        outcomes += %w[ordinary-run ordinary-seal ordinary-evidence]
        outcomes += %w[ordinary-upload-before ordinary-upload-after] if profile == "full"
        environment = outcomes.to_h { |id| [id.upcase.tr("-", "_"), "${{ steps.#{id}.outcome }}"] }
        body = outcomes.map { |id| "test \"$#{id.upcase.tr('-', '_')}\" = success\n" }.join
        environment["SEED_READY"] = "${{ steps.dependency-stage.outputs.dependency_seed_ready }}"
        environment["ARTIFACTS_READY"] = "${{ steps.ordinary-seal.outputs.artifacts_ready }}"
        environment["PROFILE_PASSED"] = "${{ steps.ordinary-seal.outputs.profile_passed }}"
        body += "test \"$SEED_READY\" = true\ntest \"$ARTIFACTS_READY\" = true\ntest \"$PROFILE_PASSED\" = true\n"
        if profile == "full"
            environment["UPLOAD_COMPLETE"] = "${{ steps.ordinary-upload-after.outputs.upload_complete }}"
            body += "test \"$UPLOAD_COMPLETE\" = true\n"
        else
            environment["SDK_OUTCOME"] = "${{ steps.sample-sdk.outcome }}"
            body += <<~'SH'
                case "$RUNNER_OS" in
                  Linux) test "$SDK_OUTCOME" = success ;;
                  Windows|macOS) test "$SDK_OUTCOME" = skipped ;;
                  *) exit 1 ;;
                esac
            SH
        end
        {"name" => "Require the complete ordinary #{profile} result", "id" => "ordinary-required",
         "if" => when_profile(profile, nil, always: true), "shell" => "bash", "env" => environment, "run" => body}
    end

    def self.full_tail
        [activation("full"), admission("full"), stage("full"), java("full"), daemon("full"),
         {"name" => "Install pinned XcodeGen", "id" => "ordinary-xcodegen", "if" => when_profile("full"),
          "run" => "xcodegen_bin_dir=\"$(scripts/install-xcodegen.sh \"$RUNNER_TEMP/p2pkit-xcodegen\")\"\necho \"$xcodegen_bin_dir\" >> \"$GITHUB_PATH\"\n"},
         {"name" => "Install Android SDK platforms", "id" => "ordinary-sdk", "if" => when_profile("full"),
          "run" => SDK},
         {"name" => "Verify repository entry points", "id" => "ordinary-entrypoints", "if" => FULL, "run" => ENTRYPOINTS},
         run("full"), seal("full"), before, upload("full"), after, terminal("full")]
    end

    def self.check_full(workflow)
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") && !workflow.key?("defaults"),
             "ordinary FULL keeps global read-only permissions and no execution overrides")
        job = workflow.fetch("jobs").fetch("complete-gate")
        need(job.keys.sort == %w[concurrency if needs permissions runs-on steps timeout-minutes] &&
             job["permissions"] == {"contents" => "read", "actions" => "read"} &&
             job["needs"] == "jvm-library-checks" && job["if"] == "${{ always() }}" &&
             job["concurrency"] == HeavyJobQueuePolicy::QUEUE && job["runs-on"] == "macos-latest" && job["timeout-minutes"] == 60,
             "ordinary FULL preserves prerequisite result guard, queue, native host, deadline and minimal read permission")
        actual = job.fetch("steps")
        expected = full_tail
        prefix = actual.take(actual.length - expected.length)
        need(Digest::SHA256.hexdigest(JSON.generate(canonical(prefix))) == FULL_PREFIX_SHA256,
             "ordinary FULL pre-acquisition prefix changed; no earlier product/cache/tool acquisition is admitted")
        need(actual.drop(prefix.length) == expected,
             "ordinary FULL must keep literal HOLD, admission, private run, separate seal, bounded upload and terminal guards")
        token_steps = actual.select { |step| JSON.generate(step).include?("github.token") || JSON.generate(step).include?("P2PKIT_ACTIONS_READ_TOKEN") }
        need(token_steps == [run("full")], "actions-read token belongs only to the exact FULL run step")
    end

    def self.entrypoints(ci, release, workflow_test)
        steps = ci.fetch("jobs").fetch("complete-gate").fetch("steps")
        controls = steps.select { |step| step["name"] == CONTROL_NAME }
        need(controls == [{"name" => CONTROL_NAME, "run" => CONTROL_COMMANDS.join("\n") + "\n"}],
             "ordinary caller controls must remain unconditional")
        scope = steps.find { |step| step["id"] == "scope" }
        need(scope && steps.index(controls.first) < steps.index(scope), "ordinary controls must cover both CI scopes")
        CONTROL_COMMANDS.each do |command|
            need(release.lines.map(&:strip).count(command) == 1, "release gate must run each ordinary control exactly once")
            interpreter, _, script = command.rpartition(" ")
            need(workflow_test.lines.map(&:strip).count("#{interpreter} \"$ROOT/#{script}\"") == 1,
                 "workflow controls must run each ordinary control exactly once")
        end
    end
end

if $PROGRAM_NAME == __FILE__
    abort "Usage: #{$PROGRAM_NAME} [ci-workflow]" if ARGV.length > 1
    path = ARGV.fetch(0, File.join(HostedTestWorkflowPolicy::ROOT, ".github/workflows/ci.yml"))
    begin
        HostedTestWorkflowPolicy.check_full(HeavyJobQueuePolicy.parse(File.read(path), path))
    rescue HostedTestWorkflowPolicy::Error, KeyError, SystemCallError => error
        abort "FATAL: #{error.message}"
    end
    puts "RESULT: PASS — ordinary FULL caller source contract; ACTIVATION=HOLD, no runtime/cache qualification"
end
