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
    PROVIDERS = {"ordinary" => "./.github/actions/ordinary-cache-provider",
                 "initial" => "./.github/actions/initial-ordinary-cache-provider"}.freeze
    PROVIDER_OUTPUTS = %w[dependency_seed_ready dependency_cache_ready native_provider_ready dependency_seed_home
        dependency_seed_staging_sha256 preparation_sha256 restoration_sha256 cache_key cache_path].freeze
    INITIAL_OUTPUT = "initial_current_history_sha256"
    SAMPLE_STEPS = %w[ordinary-output sample-sdk ordinary-package ordinary-desktop-before ordinary-desktop-apps
        ordinary-desktop-after ordinary-android-before ordinary-android-apps ordinary-android-after ordinary-delivery].freeze
    FULL = "steps.scope.outputs.full == 'true'"
    DESKTOP = "github.event_name == 'push' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch'"
    SAMPLE_INTENT = "steps.ordinary-admission.outcome == 'success' && steps.ordinary-admission.outputs.sample_packaging_required == 'true'"
    CONTROL_NAME = "Verify ordinary custody caller policy"
    CONTROL_COMMANDS = ["ruby scripts/tests/check-hosted-test-workflow-policy-test.rb",
                        "python3 -I -B -S scripts/tests/hosted-test-identity-test.py",
                        "python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py",
                        "python3 -I -B -S scripts/tests/hosted-controller-import-test.py",
                        "python3 -I -B -S scripts/tests/hosted-canonical-python-test.py",
                        "python3 -I -B -S scripts/tests/hosted-consume-delivery-test.py",
                        "python3 -I -B -S scripts/tests/hosted-desktop-job-budget-test.py",
                        "python3 -I -B -S scripts/tests/hosted-recipient-routing-test.py"].freeze
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
    def self.need(value, message)
        raise Error, message unless value
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

    def self.origin_condition(origin)
        need(PROVIDERS.key?(origin), "closed recipient origin")
        "needs.recipient-route.outputs.origin == '#{origin}'"
    end

    def self.provider_id(origin)
        need(PROVIDERS.key?(origin), "closed recipient origin")
        origin == "ordinary" ? "dependency-stage" : "initial-dependency-stage"
    end

    def self.session_path(profile)
        roles = profile == "full" ? "" : "  Linux/X64) role=linux-x64 ;;\n  Windows/X64) role=windows-x64 ;;\n"
        {"name" => "Locate the fixed native custody session", "id" => "session-path",
         "if" => when_profile(profile), "shell" => "bash", "run" => <<~SH}
            case "$RUNNER_OS/$RUNNER_ARCH" in
            #{roles}  macOS/ARM64) role=macos-arm64 ;;
              macOS/X64) role=macos-x64 ;;
              *) echo 'FATAL: unsupported ordinary native host' >&2; exit 1 ;;
            esac
            printf 'session_directory=%s/p2pkit-test-#{profile}-%s-%s-%s\\n' "$RUNNER_TEMP" "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT" "$role" >> "$GITHUB_OUTPUT"
        SH
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
        SH
        {"name" => "Admit ordinary #{profile} source and trusted recipient policy", "id" => "ordinary-admission",
         "if" => when_profile(profile, "#{origin_condition('ordinary')} && steps.session-path.outcome == 'success'"),
         "shell" => "bash", "run" => body}
    end

    def self.stage(profile, origin = "ordinary")
        environment = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"}
        environment["DEVELOPER_DIR"] = "/Applications/Xcode_26.5.app/Contents/Developer" if profile == "full"
        extra = "#{origin_condition(origin)} && steps.session-path.outcome == 'success' && steps.ordinary-admission.outcome == '#{origin == 'ordinary' ? 'success' : 'skipped'}'"
        extra += " && steps.dependency-stage.outcome == 'skipped'" if origin == "initial"
        {"name" => "Restore the exact #{origin} dependency cohort through its native owner", "id" => provider_id(origin),
         "if" => when_profile(profile, extra), "uses" => PROVIDERS.fetch(origin),
         "with" => {"profile" => profile}, "env" => environment}
    end

    def self.provider_environment
        environment = {"RECIPIENT_ORIGIN" => "${{ needs.recipient-route.outputs.origin }}"}
        PROVIDERS.each_key do |origin|
            id = provider_id(origin)
            environment["#{origin.upcase}_PROVIDER"] = "${{ steps.#{id}.outcome }}"
            (PROVIDER_OUTPUTS + (origin == "initial" ? [INITIAL_OUTPUT] : [])).each do |name|
                environment["#{origin.upcase}_#{name.upcase}"] = "${{ steps.#{id}.outputs.#{name} }}"
            end
        end
        environment
    end

    def self.provider_body(origin)
        opposite = origin == "ordinary" ? "initial" : "ordinary"
        active, inactive = origin.upcase, opposite.upcase
        body = "test \"$#{active}_PROVIDER\" = success\ntest \"$#{inactive}_PROVIDER\" = skipped\n"
        PROVIDER_OUTPUTS.first(3).each { |name| body += "test \"$#{active}_#{name.upcase}\" = true\n" }
        %w[dependency_seed_staging_sha256 preparation_sha256 restoration_sha256].each do |name|
            body += "[[ \"$#{active}_#{name.upcase}\" =~ ^[0-9a-f]{64}$ ]]\n"
        end
        %w[dependency_seed_home cache_key cache_path].each { |name| body += "test -n \"$#{active}_#{name.upcase}\"\n" }
        body += "[[ \"$INITIAL_INITIAL_CURRENT_HISTORY_SHA256\" =~ ^[0-9a-f]{64}$ ]]\n" if origin == "initial"
        (PROVIDER_OUTPUTS + (opposite == "initial" ? [INITIAL_OUTPUT] : [])).each do |name|
            body += "test -z \"$#{inactive}_#{name.upcase}\"\n"
        end
        body
    end

    def self.provider_guard(profile)
        body = "case \"$RECIPIENT_ORIGIN\" in\n"
        PROVIDERS.each_key { |origin| body += "  #{origin})\n" + provider_body(origin).lines.map { |line| "    " + line }.join + "    ;;\n" }
        body += "  *) exit 1 ;;\nesac\n"
        {"name" => "Require the selected native dependency provider", "id" => "dependency-ready",
         "if" => when_profile(profile, nil, always: true), "shell" => "bash", "env" => provider_environment, "run" => body}
    end

    def self.setup_condition(profile)
        when_profile(profile, "steps.dependency-ready.outcome == 'success'")
    end

    def self.java(profile)
        value = {"name" => "Configure daemon Java 21 and wrapper Java 17", "id" => "java", "uses" => JAVA,
                 "with" => {"distribution" => "temurin", "java-version" => "21\n17\n"}}
        value["if"] = setup_condition(profile)
        value
    end

    def self.daemon(profile)
        {"name" => "Bind the native ordinary daemon JDK", "id" => "ordinary-jdk21",
         "if" => setup_condition(profile), "shell" => "bash", "run" => JDK21}
    end

    def self.run(profile, origin = "ordinary")
        id = provider_id(origin)
        environment = {
            "P2PKIT_DEPENDENCY_SEED_STAGE_OUTCOME" => "${{ steps.#{id}.outcome }}",
            "P2PKIT_DEPENDENCY_SEED_STAGE_SHA256" => "${{ steps.#{id}.outputs.dependency_seed_staging_sha256 }}",
            "P2PKIT_HOSTED_PREPARE_OUTCOME" => "${{ steps.#{id}.outcome }}",
            "P2PKIT_HOSTED_PREPARE_SHA256" => "${{ steps.#{id}.outputs.preparation_sha256 }}",
            "P2PKIT_CACHE_GUARD_OUTCOME" => "${{ steps.#{id}.outcome }}",
            "P2PKIT_CACHE_RESTORATION_SHA256" => "${{ steps.#{id}.outputs.restoration_sha256 }}",
            "P2PKIT_NATIVE_PROVIDER_OUTCOME" => "${{ steps.#{id}.outcome }}",
        }
        environment["DEVELOPER_DIR"] = "/Applications/Xcode_26.5.app/Contents/Developer" if profile == "full"
        if origin == "initial"
            environment["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}"
            environment["P2PKIT_INITIAL_CURRENT_HISTORY_SHA256"] = "${{ steps.#{id}.outputs.initial_current_history_sha256 }}"
        end
        extra = "#{origin_condition(origin)} && steps.dependency-ready.outcome == 'success' && steps.#{id}.outcome == 'success'"
        PROVIDER_OUTPUTS.first(3).each { |name| extra += " && steps.#{id}.outputs.#{name} == 'true'" }
        command = origin == "ordinary" ? python(profile, "run").sub(" --profile #{profile}", " --profile #{profile} --consume-dependencies") : python(profile, "initial-run")
        {"name" => "Run #{origin} #{profile} with private custody", "id" => "#{origin}-run",
         "if" => when_profile(profile, extra),
         "shell" => "bash", "env" => environment,
         "run" => command}
    end

    def self.evidence_environment(origin, seal: false, upload: false)
        environment = {"P2PKIT_HOSTED_TEST_RUN_OUTCOME" => "${{ steps.#{origin}-run.outcome }}"}
        environment["P2PKIT_HOSTED_TEST_SEAL_OUTCOME"] = "${{ steps.#{origin}-seal.outcome }}" if seal
        if upload
            environment["P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME"] = "${{ steps.#{origin}-evidence.outcome }}"
            environment["P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256"] = "${{ steps.#{origin}-upload-before.outputs.upload_guard_sha256 }}"
        end
        environment["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" if origin == "initial"
        environment
    end

    def self.seal(profile, origin = "ordinary")
        {"name" => "Seal #{origin} #{profile} evidence after controller return", "id" => "#{origin}-seal",
         "if" => when_profile(profile, "#{origin_condition(origin)} && steps.#{origin}-run.outcome == 'success'", always: true),
         "timeout-minutes" => 2, "shell" => "bash", "env" => evidence_environment(origin),
         "run" => python(profile, origin == "ordinary" ? "validate-public" : "initial-validate-public")}
    end

    def self.sealed(origin = "ordinary")
        "#{origin_condition(origin)} && steps.#{origin}-run.outcome == 'success' && steps.#{origin}-seal.outcome == 'success' && steps.#{origin}-seal.outputs.artifacts_ready == 'true'"
    end

    def self.before(profile, origin = "ordinary")
        {"name" => "Admit the original #{origin} #{profile.upcase} evidence upload window", "id" => "#{origin}-upload-before",
         "if" => when_profile(profile, sealed(origin), always: true), "shell" => "bash",
         "env" => evidence_environment(origin, seal: true),
         "run" => python(profile, (origin == "ordinary" ? "" : "initial-") + "upload-guard before")}
    end

    def self.upload(profile, origin = "ordinary")
        extra = sealed(origin) + " && steps.#{origin}-upload-before.outcome == 'success' && steps.#{origin}-upload-before.outputs.upload_ready == 'true'"
        extra += profile == "full" ? " && steps.#{origin}-upload-before.outputs.upload_timeout_minutes == '3'" :
            " && (steps.#{origin}-upload-before.outputs.upload_timeout_minutes == '1' || steps.#{origin}-upload-before.outputs.upload_timeout_minutes == '2' || steps.#{origin}-upload-before.outputs.upload_timeout_minutes == '3')"
        timeout = profile == "full" ? 3 : "${{ fromJSON(steps.#{origin}-upload-before.outputs.upload_timeout_minutes) }}"
        {"name" => "Upload only sealed #{origin} #{profile} evidence", "id" => "#{origin}-evidence",
         "if" => when_profile(profile, extra, always: true), "timeout-minutes" => timeout, "uses" => UPLOAD,
         "with" => {
             "name" => "#{origin == 'ordinary' ? 'ordinary' : 'initial-ordinary'}-#{profile}-evidence-${{ runner.os }}-${{ runner.arch }}-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
             "path" => "${{ steps.session-path.outputs.session_directory }}/export/evidence.tar.gz.gpg\n${{ steps.session-path.outputs.session_directory }}/export/manifest.json\n",
             "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
             "include-hidden-files" => false, "overwrite" => false,
         }}
    end

    def self.after(profile, origin = "ordinary")
        {"name" => "Verify #{origin} #{profile.upcase} upload completed inside its original window", "id" => "#{origin}-upload-after",
         "if" => when_profile(profile, "#{sealed(origin)} && steps.#{origin}-upload-before.outcome == 'success' && steps.#{origin}-upload-before.outputs.upload_ready == 'true'", always: true),
         "shell" => "bash",
         "env" => evidence_environment(origin, seal: true, upload: true),
         "run" => python(profile, (origin == "ordinary" ? "" : "initial-") + "upload-guard after")}
    end

    def self.terminal(profile, origin = "ordinary")
        id = provider_id(origin)
        outcomes = %w[ordinary-activation session-path dependency-ready]
        outcomes += %w[ordinary-admission] if origin == "ordinary"
        outcomes += [id, "java", "ordinary-jdk21"]
        outcomes += profile == "full" ? %w[ordinary-xcodegen ordinary-sdk ordinary-entrypoints] : %w[ordinary-wrapper]
        outcomes += %w[run seal evidence upload-before upload-after].map { |suffix| "#{origin}-#{suffix}" }
        environment = outcomes.to_h { |id| [id.upcase.tr("-", "_"), "${{ steps.#{id}.outcome }}"] }
        body = outcomes.map { |id| "test \"$#{id.upcase.tr('-', '_')}\" = success\n" }.join
        environment["SEED_READY"] = "${{ steps.#{id}.outputs.dependency_seed_ready }}"
        environment["CACHE_READY"] = "${{ steps.#{id}.outputs.dependency_cache_ready }}"
        environment["NATIVE_READY"] = "${{ steps.#{id}.outputs.native_provider_ready }}"
        environment["ARTIFACTS_READY"] = "${{ steps.#{origin}-seal.outputs.artifacts_ready }}"
        environment["PROFILE_PASSED"] = "${{ steps.#{origin}-seal.outputs.profile_passed }}"
        body += "test \"$SEED_READY\" = true\ntest \"$CACHE_READY\" = true\ntest \"$NATIVE_READY\" = true\ntest \"$ARTIFACTS_READY\" = true\ntest \"$PROFILE_PASSED\" = true\n"
        environment["UPLOAD_COMPLETE"] = "${{ steps.#{origin}-upload-after.outputs.upload_complete }}"
        body += "test \"$UPLOAD_COMPLETE\" = true\n"
        if profile == "desktop" && origin == "ordinary"
            environment["SDK_OUTCOME"] = "${{ steps.sample-sdk.outcome }}"
            environment["ORDINARY_OUTPUT"] = "${{ steps.ordinary-output.outcome }}"
            environment["SAMPLE_PACKAGING_REQUIRED"] = "${{ steps.ordinary-admission.outputs.sample_packaging_required }}"
            body += <<~'SH'
                case "$SAMPLE_PACKAGING_REQUIRED" in
                  true)
                    test "$ORDINARY_OUTPUT" = success
                    case "$RUNNER_OS" in
                      Linux) test "$SDK_OUTCOME" = success ;;
                      Windows|macOS) test "$SDK_OUTCOME" = skipped ;;
                      *) exit 1 ;;
                    esac
                    ;;
                  false)
                    test "$ORDINARY_OUTPUT" = skipped
                    test "$SDK_OUTCOME" = skipped
                    case "$RUNNER_OS" in Linux|Windows|macOS) ;; *) exit 1 ;; esac
                    ;;
                  *) exit 1 ;;
                esac
            SH
        end
        {"name" => "Require the complete #{origin} #{profile} result", "id" => "#{origin}-required",
         "if" => when_profile(profile, origin_condition(origin), always: true), "shell" => "bash", "env" => environment, "run" => body}
    end

    def self.result_guard(profile)
        environment = provider_environment.merge("RECIPIENT_REQUIRED" => "${{ steps.recipient-required.outcome }}",
            "ORDINARY_ADMISSION" => "${{ steps.ordinary-admission.outcome }}")
        evidence_outputs = {"seal" => %w[artifacts_ready profile_passed],
                            "upload-before" => %w[upload_ready upload_guard_sha256 upload_timeout_minutes],
                            "upload-after" => %w[upload_complete]}
        PROVIDERS.each_key do |origin|
            %w[run seal evidence upload-before upload-after required].each do |suffix|
                environment["#{origin}_#{suffix}".upcase.tr("-", "_")] = "${{ steps.#{origin}-#{suffix}.outcome }}"
            end
            evidence_outputs.each do |step, names|
                names.each do |name|
                    environment["#{origin}_#{step}_#{name}".upcase.tr("-", "_")] = "${{ steps.#{origin}-#{step}.outputs.#{name} }}"
                end
            end
        end
        if profile == "desktop"
            SAMPLE_STEPS.each { |id| environment[id.upcase.tr("-", "_")] = "${{ steps.#{id}.outcome }}" }
            environment["SAMPLE_PACKAGING_REQUIRED"] = "${{ steps.ordinary-admission.outputs.sample_packaging_required }}"
            environment["PACKAGING_READY"] = "${{ steps.ordinary-package.outputs.packaging_ready }}"
            environment["PACKAGING_SHA256"] = "${{ steps.ordinary-package.outputs.packaging_sha256 }}"
            %w[desktop android].each do |kind|
                %w[upload_ready upload_guard_sha256 upload_timeout_minutes].each do |name|
                    environment["SAMPLE_#{kind}_#{name}".upcase] = "${{ steps.ordinary-#{kind}-before.outputs.#{name} }}"
                end
                environment["SAMPLE_#{kind.upcase}_UPLOAD_COMPLETE"] = "${{ steps.ordinary-#{kind}-after.outputs.upload_complete }}"
            end
        end
        no_samples = ""
        if profile == "desktop"
            SAMPLE_STEPS.each { |id| no_samples += "test \"$#{id.upcase.tr('-', '_')}\" = skipped\n" }
            (%w[PACKAGING_READY PACKAGING_SHA256] + environment.keys.grep(/\ASAMPLE_(?:DESKTOP|ANDROID)_/)).each do |name|
                no_samples += "test -z \"$#{name}\"\n"
            end
        end
        body = "test \"$RECIPIENT_REQUIRED\" = success\ncase \"$RECIPIENT_ORIGIN\" in\n"
        PROVIDERS.each_key do |origin|
            opposite = origin == "ordinary" ? "initial" : "ordinary"
            branch = provider_body(origin)
            %w[run seal evidence upload-before upload-after required].each do |suffix|
                variable = "#{origin}_#{suffix}".upcase.tr("-", "_")
                branch += "test \"$#{variable}\" = success\n"
            end
            %w[SEAL_ARTIFACTS_READY SEAL_PROFILE_PASSED UPLOAD_BEFORE_UPLOAD_READY UPLOAD_AFTER_UPLOAD_COMPLETE].each do |suffix|
                branch += "test \"$#{origin.upcase}_#{suffix}\" = true\n"
            end
            branch += "[[ \"$#{origin.upcase}_UPLOAD_BEFORE_UPLOAD_GUARD_SHA256\" =~ ^[0-9a-f]{64}$ ]]\n"
            branch += "case \"$#{origin.upcase}_UPLOAD_BEFORE_UPLOAD_TIMEOUT_MINUTES\" in #{profile == 'full' ? '3' : '1|2|3'}) ;; *) exit 1 ;; esac\n"
            %w[run seal evidence upload-before upload-after required].each do |suffix|
                variable = "#{opposite}_#{suffix}".upcase.tr("-", "_")
                branch += "test \"$#{variable}\" = skipped\n"
            end
            evidence_outputs.each do |step, names|
                names.each do |name|
                    variable = "#{opposite}_#{step}_#{name}".upcase.tr("-", "_")
                    branch += "test -z \"$#{variable}\"\n"
                end
            end
            branch += "test \"$ORDINARY_ADMISSION\" = #{origin == 'ordinary' ? 'success' : 'skipped'}\n"
            if profile == "desktop"
                if origin == "initial"
                    branch += "test -z \"$SAMPLE_PACKAGING_REQUIRED\"\n" + no_samples
                else
                    branch += "case \"$SAMPLE_PACKAGING_REQUIRED\" in\n  true) test \"$ORDINARY_DELIVERY\" = success ;;\n  false)\n" +
                        no_samples.lines.map { |line| "    " + line }.join + "    ;;\n  *) exit 1 ;;\nesac\n"
                end
            end
            body += "  #{origin})\n" + branch.lines.map { |line| "    " + line }.join + "    ;;\n"
        end
        body += "  *) exit 1 ;;\nesac\n"
        {"name" => "Require one complete recipient-origin result", "id" => "recipient-result",
         "if" => when_profile(profile, nil, always: true), "shell" => "bash", "env" => environment, "run" => body}
    end

    def self.full_tail
        [activation("full"), session_path("full"), admission("full"), stage("full"), stage("full", "initial"), provider_guard("full"), java("full"), daemon("full"),
         {"name" => "Install pinned XcodeGen", "id" => "ordinary-xcodegen", "if" => setup_condition("full"),
          "run" => "xcodegen_bin_dir=\"$(scripts/install-xcodegen.sh \"$RUNNER_TEMP/p2pkit-xcodegen\")\"\necho \"$xcodegen_bin_dir\" >> \"$GITHUB_PATH\"\n"},
         {"name" => "Install Android SDK platforms", "id" => "ordinary-sdk", "if" => setup_condition("full"),
          "run" => SDK},
         {"name" => "Verify repository entry points", "id" => "ordinary-entrypoints", "if" => setup_condition("full"), "run" => ENTRYPOINTS},
         run("full"), run("full", "initial"), seal("full"), seal("full", "initial"),
         before("full"), upload("full"), after("full"), before("full", "initial"), upload("full", "initial"), after("full", "initial"),
         terminal("full"), terminal("full", "initial"), result_guard("full")]
    end

    def self.full_prefix
        # Explicit Foundation contract, not the donor campaign's unrelated
        # probe/lock/preview prefix hash or an expectation derived from YAML.
        # Every pre-acquisition command is enumerated, including script tests
        # which keep their existing Foundation/Maven/recovery registrations.
        [
            {"name" => "Require successful Linux and Windows library tests", "id" => "require-jvm-checks",
             "shell" => "bash", "env" => {"JVM_CHECK_RESULT" => "${{ needs.jvm-library-checks.result }}"},
             "run" => 'test "$JVM_CHECK_RESULT" = success'},
            HeavyJobQueuePolicy.routing_guard,
            {"name" => "Check out repository", "uses" => "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
             "with" => {"fetch-depth" => 0, "persist-credentials" => false}},
            {"name" => "Verify participating heavy-job queue policy", "run" => "ruby scripts/tests/check-heavy-job-queue-policy-test.rb"},
            {"name" => "Verify development sample artifact policy", "run" =>
                "ruby scripts/tests/check-sample-app-workflow-policy-test.rb\npython3 -I -B scripts/tests/package-sample-apps-test.py\n"},
            {"name" => "Verify private test-transcript custody controls", "run" => "python3 -I -B -S scripts/tests/test-transcript-custody-test.py"},
            {"name" => CONTROL_NAME, "run" => CONTROL_COMMANDS.join("\n") + "\n"},
            {"name" => "Classify required-check scope", "id" => "scope", "shell" => "bash", "env" => {
                "EVENT_NAME" => "${{ github.event_name }}", "REF_NAME" => "${{ github.ref_name }}",
                "BEFORE_SHA" => "${{ github.event.before }}", "PR_BASE_SHA" => "${{ github.event.pull_request.base.sha }}",
                "PR_HEAD_SHA" => "${{ github.event.pull_request.head.sha }}"},
             "run" => 'scripts/resolve-ci-scope.sh >> "$GITHUB_OUTPUT"'},
            {"name" => "Verify committed and local whitespace", "env" => {
                "BASE_SHA" => "${{ steps.scope.outputs.base }}", "HEAD_SHA" => "${{ steps.scope.outputs.head }}"},
             "run" => 'scripts/check-git-whitespace.sh "$BASE_SHA" "$HEAD_SHA"'},
            {"name" => "Verify dependency update completeness", "if" => FULL, "env" => {
                "BASE_SHA" => "${{ steps.scope.outputs.base }}", "HEAD_SHA" => "${{ steps.scope.outputs.head }}"},
             "run" => "scripts/check-dependency-update.sh \"$BASE_SHA\" \"$HEAD_SHA\"\nscripts/tests/check-dependency-update-policy-test.sh\n"},
            {"name" => "Verify lightweight documentation change", "if" => "steps.scope.outputs.full != 'true'", "env" => {
                "BASE_SHA" => "${{ steps.scope.outputs.base }}", "HEAD_SHA" => "${{ steps.scope.outputs.head }}"},
             "run" => ["scripts/tests/classify-ci-scope-test.sh", "scripts/tests/resolve-ci-scope-test.sh",
                 "ruby scripts/tests/check-ci-scope-policy-test.rb", "scripts/tests/check-git-whitespace-test.sh",
                 "scripts/check-release-metadata.sh", "scripts/tests/check-repository-layout.sh",
                 "scripts/tests/check-markdown-links.sh"].join("\n") + "\n"},
        ]
    end

    def self.check_full(workflow)
        need(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("env") && !workflow.key?("defaults"),
             "ordinary FULL keeps global read-only permissions and no execution overrides")
        jobs = workflow.fetch("jobs")
        jvm = jobs.fetch("jvm-library-checks")
        HeavyJobQueuePolicy.check_routing(jobs, "full")
        need(jobs.keys.sort == [*HeavyJobQueuePolicy::ROUTING_NEEDS, "jvm-library-checks", "complete-gate"].sort &&
             jvm["needs"] == HeavyJobQueuePolicy::ROUTING_NEEDS && jvm["if"] == HeavyJobQueuePolicy::JVM_CONDITION &&
             !jvm.key?("continue-on-error"), "whole JVM job including always-cleanup must wait for exact recipient routing")
        job = workflow.fetch("jobs").fetch("complete-gate")
        need(job.keys.sort == %w[concurrency if needs permissions runs-on steps timeout-minutes] &&
             job["permissions"] == {"contents" => "read", "actions" => "read"} &&
             job["needs"] == ["jvm-library-checks", *HeavyJobQueuePolicy::ROUTING_NEEDS] && job["if"] == "${{ always() }}" &&
             job["concurrency"] == HeavyJobQueuePolicy::QUEUE && job["runs-on"] == "macos-latest" && job["timeout-minutes"] == 60,
             "ordinary FULL preserves prerequisite result guard, queue, native host, deadline and minimal read permission")
        actual = job.fetch("steps")
        expected = full_tail
        prefix = full_prefix
        need(actual.take(prefix.length) == prefix,
             "ordinary FULL pre-acquisition prefix changed; no earlier product/cache/tool acquisition is admitted")
        need(actual.drop(prefix.length) == expected,
             "ordinary FULL must keep literal HOLD, admission, private run, separate seal, bounded upload and terminal guards")
        token_steps = actual.select { |step| JSON.generate(step).include?("github.token") || JSON.generate(step).include?("P2PKIT_ACTIONS_READ_TOKEN") }
        need(token_steps == credential_steps("full"), "actions-read token belongs only to fixed native preparation and initial-current consumers")
    end

    def self.credential_steps(profile)
        [stage(profile), stage(profile, "initial"), run(profile, "initial"), seal(profile, "initial"),
         before(profile, "initial"), after(profile, "initial")]
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
