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
    RESTORE = "actions/cache/restore@caa296126883cff596d87d8935842f9db880ef25"
    FULL = "steps.scope.outputs.full == 'true'"
    DESKTOP = "github.event_name != 'workflow_dispatch' || inputs.operation == 'desktop'"
    PREVIEW = "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'sample-apps' }}"
    CONTROL_NAME = "Verify ordinary custody caller policy"
    CONTROL_COMMANDS = ["ruby scripts/tests/check-hosted-test-workflow-policy-test.rb",
                        "python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py",
                        "python3 -I -B -S scripts/tests/hosted-controller-import-test.py",
                        "python3 -I -B -S scripts/tests/hosted-consume-delivery-test.py",
                        "python3 -I -B -S scripts/tests/hosted-desktop-job-budget-test.py"].freeze
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
    # Reviewed pre-acquisition CI prefix with offline caller/composition, cold
    # controller-import, connected-consume/delivery and Desktop-budget controls.
    # Canonical key ordering; no value is derived from the workflow here.
    # This fences even a product command inserted in an otherwise named policy step.
    FULL_PREFIX_SHA256 = "d08c699fd6ca504fd2a1e387313aa215ab29ac277873c51933bd09fcfb7e9ee8"

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
        environment = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"}
        environment["DEVELOPER_DIR"] = "/Applications/Xcode_26.5.app/Contents/Developer" if profile == "full"
        {"name" => "Bind original ordinary job timing and dependency consume plan", "id" => "dependency-stage",
         "if" => when_profile(profile), "shell" => "bash",
         "env" => environment,
         "run" => python(profile, "prepare-consume")}
    end

    def self.restore(profile)
        {"name" => "Restore only the exact ordinary dependency byte cohort", "id" => "dependency-restore",
         "if" => when_profile(profile, "steps.dependency-stage.outcome == 'success' && steps.dependency-stage.outputs.dependency_seed_ready == 'true' && (steps.dependency-stage.outputs.cache_restore_timeout_minutes == '1' || steps.dependency-stage.outputs.cache_restore_timeout_minutes == '2' || steps.dependency-stage.outputs.cache_restore_timeout_minutes == '3')"),
         "timeout-minutes" => "${{ fromJSON(steps.dependency-stage.outputs.cache_restore_timeout_minutes) }}", "uses" => RESTORE,
         "with" => {"path" => "${{ steps.dependency-stage.outputs.cache_path }}",
                    "key" => "${{ steps.dependency-stage.outputs.cache_key }}",
                    "enableCrossOsArchive" => false, "fail-on-cache-miss" => true, "lookup-only" => false}}
    end

    def self.restore_guard(profile)
        {"name" => "Validate the original ordinary restore result", "id" => "dependency-restore-guard",
         "if" => when_profile(profile, "(steps.dependency-stage.outcome == 'success' || steps.dependency-stage.outcome == 'failure' || steps.dependency-stage.outcome == 'cancelled')", always: true),
         "shell" => "bash", "env" => {
             "P2PKIT_HOSTED_PREPARE_OUTCOME" => "${{ steps.dependency-stage.outcome }}",
             "P2PKIT_HOSTED_PREPARE_SHA256" => "${{ steps.dependency-stage.outputs.preparation_sha256 }}",
             "P2PKIT_CACHE_RESTORE_OUTCOME" => "${{ steps.dependency-restore.outcome }}",
             "P2PKIT_CACHE_RESTORE_PRIMARY_KEY" => "${{ steps.dependency-restore.outputs.cache-primary-key }}",
             "P2PKIT_CACHE_RESTORE_MATCHED_KEY" => "${{ steps.dependency-restore.outputs.cache-matched-key }}",
             "P2PKIT_CACHE_RESTORE_HIT" => "${{ steps.dependency-restore.outputs.cache-hit }}",
         }, "run" => python(profile, "restore-guard")}
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
            "P2PKIT_HOSTED_PREPARE_OUTCOME" => "${{ steps.dependency-stage.outcome }}",
            "P2PKIT_HOSTED_PREPARE_SHA256" => "${{ steps.dependency-stage.outputs.preparation_sha256 }}",
            "P2PKIT_CACHE_GUARD_OUTCOME" => "${{ steps.dependency-restore-guard.outcome }}",
            "P2PKIT_CACHE_RESTORATION_SHA256" => "${{ steps.dependency-restore-guard.outputs.restoration_sha256 }}",
        }
        if profile == "full"
            environment["DEVELOPER_DIR"] = "/Applications/Xcode_26.5.app/Contents/Developer"
        end
        {"name" => "Run ordinary #{profile} with private custody", "id" => "ordinary-run",
         "if" => when_profile(profile, "steps.dependency-stage.outcome == 'success' && steps.dependency-stage.outputs.dependency_seed_ready == 'true' && steps.dependency-restore-guard.outcome == 'success' && steps.dependency-restore-guard.outputs.dependency_cache_ready == 'true'"),
         "shell" => "bash", "env" => environment,
         "run" => python(profile, "run").sub(" --profile #{profile}", " --profile #{profile} --consume-dependencies")}
    end

    def self.seal(profile)
        {"name" => "Seal ordinary #{profile} evidence after controller return", "id" => "ordinary-seal",
         "if" => when_profile(profile, "steps.ordinary-run.outcome == 'success'", always: true),
         "timeout-minutes" => 2, "shell" => "bash", "env" => {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}"},
         "run" => python(profile, "validate-public")}
    end

    def self.sealed
        "steps.ordinary-run.outcome == 'success' && steps.ordinary-seal.outcome == 'success' && steps.ordinary-seal.outputs.artifacts_ready == 'true'"
    end

    def self.before(profile)
        {"name" => "Admit the original #{profile.upcase} evidence upload window", "id" => "ordinary-upload-before",
         "if" => when_profile(profile, sealed, always: true), "shell" => "bash",
         "env" => {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}",
                   "P2PKIT_HOSTED_TEST_SEAL_OUTCOME" => "${{ steps.ordinary-seal.outcome }}"},
         "run" => python(profile, "upload-guard before")}
    end

    def self.upload(profile)
        extra = sealed + " && steps.ordinary-upload-before.outcome == 'success' && steps.ordinary-upload-before.outputs.upload_ready == 'true'"
        extra += profile == "full" ? " && steps.ordinary-upload-before.outputs.upload_timeout_minutes == '3'" :
            " && (steps.ordinary-upload-before.outputs.upload_timeout_minutes == '1' || steps.ordinary-upload-before.outputs.upload_timeout_minutes == '2' || steps.ordinary-upload-before.outputs.upload_timeout_minutes == '3')"
        timeout = profile == "full" ? 3 : "${{ fromJSON(steps.ordinary-upload-before.outputs.upload_timeout_minutes) }}"
        {"name" => "Upload only sealed ordinary #{profile} evidence", "id" => "ordinary-evidence",
         "if" => when_profile(profile, extra, always: true), "timeout-minutes" => timeout, "uses" => UPLOAD,
         "with" => {
             "name" => "ordinary-#{profile}-evidence-${{ runner.os }}-${{ runner.arch }}-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
             "path" => "${{ steps.ordinary-admission.outputs.session_directory }}/export/evidence.tar.gz.gpg\n${{ steps.ordinary-admission.outputs.session_directory }}/export/manifest.json\n",
             "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
             "include-hidden-files" => false, "overwrite" => false,
         }}
    end

    def self.after(profile)
        {"name" => "Verify #{profile.upcase} upload completed inside its original window", "id" => "ordinary-upload-after",
         "if" => when_profile(profile, "#{sealed} && steps.ordinary-upload-before.outcome == 'success' && steps.ordinary-upload-before.outputs.upload_ready == 'true'", always: true),
         "shell" => "bash",
         "env" => {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.ordinary-run.outcome }}",
                   "P2PKIT_HOSTED_TEST_SEAL_OUTCOME" => "${{ steps.ordinary-seal.outcome }}",
                   "P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME" => "${{ steps.ordinary-evidence.outcome }}",
                   "P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256" => "${{ steps.ordinary-upload-before.outputs.upload_guard_sha256 }}"},
         "run" => python(profile, "upload-guard after")}
    end

    def self.terminal(profile)
        outcomes = %w[ordinary-activation ordinary-admission dependency-stage dependency-restore dependency-restore-guard java ordinary-jdk21]
        outcomes += profile == "full" ? %w[ordinary-xcodegen ordinary-sdk ordinary-entrypoints] : %w[ordinary-output ordinary-wrapper]
        outcomes += %w[ordinary-run ordinary-seal ordinary-evidence]
        outcomes += %w[ordinary-upload-before ordinary-upload-after]
        environment = outcomes.to_h { |id| [id.upcase.tr("-", "_"), "${{ steps.#{id}.outcome }}"] }
        body = outcomes.map { |id| "test \"$#{id.upcase.tr('-', '_')}\" = success\n" }.join
        environment["SEED_READY"] = "${{ steps.dependency-stage.outputs.dependency_seed_ready }}"
        environment["CACHE_READY"] = "${{ steps.dependency-restore-guard.outputs.dependency_cache_ready }}"
        environment["ARTIFACTS_READY"] = "${{ steps.ordinary-seal.outputs.artifacts_ready }}"
        environment["PROFILE_PASSED"] = "${{ steps.ordinary-seal.outputs.profile_passed }}"
        body += "test \"$SEED_READY\" = true\ntest \"$CACHE_READY\" = true\ntest \"$ARTIFACTS_READY\" = true\ntest \"$PROFILE_PASSED\" = true\n"
        environment["UPLOAD_COMPLETE"] = "${{ steps.ordinary-upload-after.outputs.upload_complete }}"
        body += "test \"$UPLOAD_COMPLETE\" = true\n"
        if profile == "desktop"
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
        [activation("full"), admission("full"), stage("full"), restore("full"), restore_guard("full"), java("full"), daemon("full"),
         {"name" => "Install pinned XcodeGen", "id" => "ordinary-xcodegen", "if" => when_profile("full"),
          "run" => "xcodegen_bin_dir=\"$(scripts/install-xcodegen.sh \"$RUNNER_TEMP/p2pkit-xcodegen\")\"\necho \"$xcodegen_bin_dir\" >> \"$GITHUB_PATH\"\n"},
         {"name" => "Install Android SDK platforms", "id" => "ordinary-sdk", "if" => when_profile("full"),
          "run" => SDK},
         {"name" => "Verify repository entry points", "id" => "ordinary-entrypoints", "if" => FULL, "run" => ENTRYPOINTS},
         run("full"), seal("full"), before("full"), upload("full"), after("full"), terminal("full")]
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
        need(token_steps == [stage("full")], "actions-read token belongs only to the original FULL timing/consume preparation")
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
