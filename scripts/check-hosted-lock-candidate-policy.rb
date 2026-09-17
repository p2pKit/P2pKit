#!/usr/bin/env ruby
# Exact workflow boundary only, not native admission, a writer or encryption proof.
require_relative "check-heavy-job-queue-policy"
require_relative "check-sample-app-workflow-policy"

module HostedLockCandidatePolicy
    Error = HeavyJobQueuePolicy::Error
    ROOT = File.expand_path("..", __dir__)
    JOB = "dependency-lock-candidate"
    INTEL_OPERATION = "dependency-lock-candidate-x64"
    MACOS14_OPERATION = "dependency-lock-candidate-macos14"
    RUNNER = "${{ inputs.operation == 'dependency-lock-candidate-macos14' && 'macos-14' || inputs.operation == 'dependency-lock-candidate-x64' && 'macos-15-intel' || 'macos-26' }}"
    PYTHON = '"$DEVELOPER_DIR/usr/bin/python3"'
    STEP_NAME = "Verify isolated hosted lock-candidate controls"
    CHECKS = [
        "ruby scripts/tests/check-hosted-lock-candidate-policy-test.rb",
        "python3 -I -B -S scripts/tests/run-hosted-lock-candidate-test.py",
        "python3 -I -B -S scripts/tests/hosted-lock-resources-test.py",
        "python3 -I -B -S scripts/tests/hosted-apple-link-test.py",
        "python3 -I -B -S scripts/tests/encrypt-hosted-evidence-test.py",
    ].freeze
    # These small, reviewed prologues are deliberately not a general shell
    # parser. Before the controls, admit only this setup and standalone script
    # calls: a matching command hidden in a function/if/heredoc is not a gate.
    RELEASE_PROLOGUE = <<~'SH'.lines.map(&:strip).freeze
        set -euo pipefail
        ROOT="$(cd "$(dirname "$0")/.." && pwd)"
        REPORT_DIR="$ROOT/build/reports/release"
        mkdir -p "$REPORT_DIR"
        cd "$ROOT"
    SH
    WORKFLOW_TEST_PROLOGUE = <<~'SH'.lines.map(&:strip).freeze
        set -euo pipefail
        ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
        WORKFLOW="$ROOT/.github/workflows/publish-maven-central.yml"
        CI_WORKFLOW="$ROOT/.github/workflows/ci.yml"
        DRY_RUN_WORKFLOW="$ROOT/.github/workflows/release-dry-run.yml"
        DESKTOP_WORKFLOW="$ROOT/.github/workflows/desktop-cross-host.yml"
        ANDROID_LOCK="$ROOT/samples/p2p-sample-android/gradle.lockfile"
        DESKTOP_BUILD="$ROOT/samples/p2p-sample-desktop-ui/build.gradle.kts"
        DESKTOP_LOCK="$ROOT/samples/p2p-sample-desktop-ui/gradle.lockfile"
        VERSION_CATALOG="$ROOT/gradle/libs.versions.toml"
        XCODEGEN_INSTALLER="$ROOT/scripts/install-xcodegen.sh"
        CI_SCOPE_CLASSIFIER="$ROOT/scripts/classify-ci-scope.sh"
        CI_SCOPE_RESOLVER="$ROOT/scripts/resolve-ci-scope.sh"
        GIT_WHITESPACE_CHECK="$ROOT/scripts/check-git-whitespace.sh"
        RELEASE_IDENTITY_CHECK="$ROOT/scripts/check-release-identity.sh"
        BUNDLE_BUILDER="$ROOT/scripts/build-central-portal-bundle.sh"
        RELEASE_METADATA_CHECK="$ROOT/scripts/check-release-metadata.sh"
        is_local_workflow_reference() {
        local root="$1" use="$2"
        [[ "$use" =~ ^\./\.github/workflows/[a-zA-Z0-9_-]+\.ya?ml$ ]] &&
        [[ ! -L "$root/.github" && ! -L "$root/.github/workflows" &&
        -f "$root/${use#./}" && ! -L "$root/${use#./}" ]] &&
        git -C "$root" ls-files --error-unmatch -- "${use#./}" >/dev/null 2>&1
        }
        [[ -f "$WORKFLOW" ]] || { echo "FATAL: Maven Central workflow is missing" >&2; exit 1; }
        [[ -f "$DESKTOP_WORKFLOW" ]] || { echo "FATAL: Desktop cross-host workflow is missing" >&2; exit 1; }
    SH
    RELEASE_CALL = %r{\A(?:scripts/(?:tests/)?[a-z0-9-]+\.sh|ruby scripts/(?:tests/)?[a-z0-9-]+\.rb|python3(?: -B| -I -B -S)? scripts/(?:tests/)?[a-z0-9-]+\.py)\z}
    WORKFLOW_TEST_CALL = %r{\A(?:"\$ROOT/scripts/(?:tests/)?[a-z0-9-]+\.sh"|ruby "\$ROOT/scripts/(?:tests/)?[a-z0-9-]+\.rb"|python3(?: -B| -I -B -S)? "\$ROOT/scripts/(?:tests/)?[a-z0-9-]+\.py")\z}
    ENVIRONMENT = {
        "DEVELOPER_DIR" => "${{ inputs.operation == 'dependency-lock-candidate-macos14' && '/Applications/Xcode_16.2.app/Contents/Developer' || inputs.operation == 'dependency-lock-candidate-x64' && '/Applications/Xcode_26.3.app/Contents/Developer' || '/Applications/Xcode_26.5.app/Contents/Developer' }}",
        "P2PKIT_OPERATION" => "${{ inputs.operation }}",
        "P2PKIT_EXPECTED_SHA" => "${{ inputs.expected_sha }}",
        "P2PKIT_EXPECTED_TREE" => "${{ inputs.expected_tree }}",
        "P2PKIT_REVIEWED_BASE" => "${{ inputs.reviewed_base }}",
        "P2PKIT_EVIDENCE_PUBLIC_KEY" => "${{ inputs.evidence_public_key }}",
        "P2PKIT_EVIDENCE_FINGERPRINT" => "${{ inputs.evidence_fingerprint }}",
        "PYTHONDONTWRITEBYTECODE" => "1", "PYTHONUNBUFFERED" => "1",
    }.freeze
    STEPS = [
        {"name" => "Check out exact reviewed lock-candidate source", "uses" => SampleAppWorkflowPolicy::CHECKOUT,
         "with" => {"ref" => "${{ github.sha }}", "fetch-depth" => 0, "persist-credentials" => false}},
        {"name" => "Admit host and generate private full-lock candidate", "id" => "candidate",
         "timeout-minutes" => 170, "shell" => "bash",
         "run" => "exec #{PYTHON} -I -B -S scripts/run-hosted-lock-candidate.py run"},
        {"name" => "Seal private original evidence after controller exit", "id" => "seal", "if" => "${{ always() }}",
         "timeout-minutes" => 15, "shell" => "bash",
         "run" => "exec #{PYTHON} -I -B -S scripts/run-hosted-lock-candidate.py seal"},
        {"name" => "Validate exact encrypted public evidence", "id" => "public", "if" => "${{ always() }}",
         "timeout-minutes" => 2, "shell" => "bash",
         "run" => "exec #{PYTHON} -I -B -S scripts/run-hosted-lock-candidate.py validate-public"},
        {"name" => "Retain encrypted lock-candidate evidence", "uses" => SampleAppWorkflowPolicy::UPLOAD,
         "if" => "${{ always() && steps.public.outputs.artifacts_ready == 'true' }}",
         "with" => {
             "name" => "encrypted-lock-candidate-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
             "path" => "${{ runner.temp }}/p2pkit-lock-export-${{ github.run_id }}-${{ github.run_attempt }}",
             "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
             "include-hidden-files" => false, "overwrite" => false}},
        {"name" => "Fail if encrypted retained evidence is unavailable",
         "if" => "${{ always() && steps.public.outputs.artifacts_ready != 'true' }}", "shell" => "bash",
         "run" => "echo 'FATAL: no safe encrypted lock-candidate evidence; no acceptance claim' >&2\nexit 1\n"},
    ].freeze

    def self.need(condition, message)
        raise Error, message unless condition
    end

    def self.check(workflow)
        # Keep the ordinary matrix/tasks/publisher-independent authority unchanged.
        SampleAppWorkflowPolicy.check(workflow)
        need(workflow["name"] == "Desktop cross-host", "preserve genuine shared workflow identity")
        need(workflow["concurrency"] == HeavyJobQueuePolicy::WORKFLOW_CONCURRENCY["desktop-cross-host.yml"],
             "manual writer cannot cancel or hold the ordinary/control workflow group")
        triggers = workflow.fetch("on") { workflow.fetch(true) }
        inputs = triggers.fetch("workflow_dispatch").fetch("inputs")
        need(inputs.is_a?(Hash) && inputs.keys.sort ==
             %w[evidence_fingerprint evidence_public_key expected_sha expected_tree operation reviewed_base],
             "exact six shared dispatch inputs required")
        expected = {"operation" => {"type" => "choice", "options" => ["desktop", "sample-apps",
            "windows-directory-fsync-control", "windows-helper-controls", "macos-arm64-admission", "macos-x64-admission", JOB, INTEL_OPERATION, MACOS14_OPERATION, "iphoneos-product"],
            "default" => "desktop", "required" => true}}
        %w[expected_sha expected_tree reviewed_base evidence_public_key evidence_fingerprint].each do |name|
            expected[name] = {"type" => "string", "required" => false, "default" => ""}
        end
        inputs.each do |name, value|
            need(value.is_a?(Hash) && value["description"].is_a?(String) && !value["description"].empty? &&
                 value.reject { |key, _| key == "description" } == expected[name],
                 "shared operation/source/public-recipient fields must keep exact types and empty defaults")
        end
        jobs = workflow.fetch("jobs")
        need(jobs.keys.sort == HeavyJobQueuePolicy::JOBS["desktop-cross-host.yml"].keys.sort,
             "unexpected Desktop/writer job authority")
        job = jobs.fetch(JOB)
        need(job.is_a?(Hash) && job.keys.sort == %w[concurrency env if name permissions runs-on steps timeout-minutes] &&
             job["name"] == JOB && job["runs-on"] == RUNNER && job["timeout-minutes"] == 195 &&
             job["permissions"] == {"contents" => "read"} &&
             job["if"] == HeavyJobQueuePolicy::CONDITIONS[["desktop-cross-host.yml", JOB]] &&
             job["concurrency"] == HeavyJobQueuePolicy::QUEUE,
             "writer requires isolated manual native job, read-only token, finite deadline and shared non-cancelling queue")
        need(job["env"] == ENVIRONMENT, "writer environment must bind source/base/public recipient and pinned Xcode only")
        need(job["steps"] == STEPS,
             "writer must keep exact full checkout, controller, unconditional sealing/validation, encrypted upload and failure guard")
    end

    def self.shell_entrypoint(body, commands, prologue, allowed_call, label)
        need(body.is_a?(String) && body.lines.first == "#!/usr/bin/env bash\n",
             "#{label}: the reviewed Bash entrypoint is required")
        lines = body.lines.map(&:strip).reject { |line| line.empty? || line.start_with?("#") }
        commands.each do |command|
            script = command.split(" ").last.delete('"').delete_prefix("$ROOT/")
            need(lines.count(command) == 1 && lines.sum { |line| line.scan(Regexp.new(Regexp.escape(script))).length } == 1,
                 "#{label}: each hosted control must be called exactly once, without wrappers or ignored failures")
        end
        first = lines.index(commands.first)
        need(lines[first, commands.length] == commands,
             "#{label}: keep the five exact hosted controls in one ordered, fail-closed block")
        prefix = lines.take(first)
        need(prefix.take(prologue.length) == prologue &&
             prefix.drop(prologue.length).all? { |line| allowed_call.match?(line) },
             "#{label}: controls require the reviewed strict prologue and unconditional standalone calls")
    end

    def self.entrypoints(ci, release, workflow_test)
        need(ci.is_a?(Hash) && ci["jobs"].is_a?(Hash), "CI must retain its jobs mapping")
        job = ci["jobs"]["complete-gate"]
        need(job.is_a?(Hash) && job["steps"].is_a?(Array) && job["steps"].all? { |step| step.is_a?(Hash) },
             "CI must retain its complete-gate steps")
        need(job["if"] == "${{ always() }}" && job["runs-on"] == "macos-latest" &&
             %w[continue-on-error defaults env].none? { |key| job.key?(key) } &&
             %w[defaults env].none? { |key| ci.key?(key) },
             "CI hosted controls cannot inherit conditional admission, ignored errors or execution overrides")
        steps = job["steps"]
        controls = steps.select { |step| step["name"] == STEP_NAME }
        need(controls == [{"name" => STEP_NAME, "run" => CHECKS.join("\n") + "\n"}],
             "CI hosted controls must be exact and unconditional without step overrides")
        scopes = steps.select { |step| step["id"] == "scope" }
        need(scopes.length == 1 && steps.index(controls.first) < steps.index(scopes.first),
             "CI hosted controls must cover both scopes before the unique scope classifier")
        CHECKS.each do |command|
            script = command.split(" ").last
            need(steps.sum { |step| step.fetch("run", "").scan(Regexp.new(Regexp.escape(script))).length } == 1,
                 "CI must run each hosted control exactly once")
        end
        shell_entrypoint(release, CHECKS, RELEASE_PROLOGUE, RELEASE_CALL, "release gate")
        rooted = CHECKS.map do |command|
            interpreter, _, script = command.rpartition(" ")
            "#{interpreter} \"$ROOT/#{script}\""
        end
        shell_entrypoint(workflow_test, rooted, WORKFLOW_TEST_PROLOGUE, WORKFLOW_TEST_CALL, "workflow controls")
    end
end

if $PROGRAM_NAME == __FILE__
    abort "Usage: #{$PROGRAM_NAME} [workflow-file]" if ARGV.length > 1
    path = ARGV.fetch(0, File.join(HostedLockCandidatePolicy::ROOT, ".github/workflows/desktop-cross-host.yml"))
    begin
        HostedLockCandidatePolicy.check(HeavyJobQueuePolicy.parse(File.read(path), path))
    rescue HostedLockCandidatePolicy::Error, SystemCallError => error
        abort "FATAL: #{error.message}"
    end
    puts "RESULT: PASS — encrypted lock-candidate workflow boundary only; no native/build/encryption claim"
end
