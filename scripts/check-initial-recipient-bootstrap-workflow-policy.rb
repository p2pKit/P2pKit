#!/usr/bin/env ruby
# Closed dormant wiring only. No source hash, model or YAML pass lifts a HOLD.
require "yaml"
require_relative "check-heavy-job-queue-policy"

module InitialRecipientBootstrapPolicy
    class Error < StandardError; end
    FILE = "dependency-cache-bootstrap.yml"
    REF = "refs/heads/work/release-foundation-20260926-1WzHcOIr"
    SELECTORS = %w[desktop-linux-x64 desktop-windows-x64 desktop-macos-arm64 desktop-macos-x64 full-macos-arm64 full-macos-x64].freeze
    RUNNERS = '${{ fromJSON(\'{"desktop-linux-x64":"ubuntu-latest","desktop-windows-x64":"windows-latest","desktop-macos-arm64":"macos-26","desktop-macos-x64":"macos-15-intel","full-macos-arm64":"macos-26","full-macos-x64":"macos-15-intel"}\')[inputs.selection] }}'
    HOLD = <<~'SH'
        echo 'INITIAL_RECIPIENT_STAGE1=HOLD; SOURCE_ACTIVATION_AND_QUALIFICATION_REQUIRED' >&2
        exit 125
    SH
    PREFLIGHT = <<~'SH'
        set -euo pipefail
        test "$GITHUB_REPOSITORY" = p2pKit/P2pKit
        test "$GITHUB_EVENT_NAME" = workflow_dispatch
        test "$GITHUB_REF" = refs/heads/work/release-foundation-20260926-1WzHcOIr
        [[ "$P2PKIT_EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]
        [[ "$P2PKIT_EXPECTED_TREE" =~ ^[0-9a-f]{40}$ ]]
        test "$GITHUB_SHA" = "$P2PKIT_EXPECTED_SHA"
        git -c credential.helper= -c http.extraheader= fetch --no-tags --unshallow https://github.com/p2pKit/P2pKit.git \
          refs/heads/main:refs/remotes/origin/main \
          refs/heads/work/release-foundation-20260926-1WzHcOIr:refs/remotes/origin/work/release-foundation-20260926-1WzHcOIr
        test "$(git rev-parse --is-shallow-repository)" = false
        test "$(git rev-parse HEAD)" = "$P2PKIT_EXPECTED_SHA"
        test "$(git rev-parse 'HEAD^{tree}')" = "$P2PKIT_EXPECTED_TREE"
        test "$(git rev-parse refs/remotes/origin/main)" = 3bc76f956f8f47447b51a62474fc878b9c43173c
        test "$(git rev-parse 'refs/remotes/origin/main^{tree}')" = 2a1105fde1d1ac299448489501e29d7a0d4a407a
        test "$(git rev-parse refs/remotes/origin/work/release-foundation-20260926-1WzHcOIr)" = "$P2PKIT_EXPECTED_SHA"
        git merge-base --is-ancestor 3bc76f956f8f47447b51a62474fc878b9c43173c "$P2PKIT_EXPECTED_SHA"
        source_status="$(git status --porcelain=v1 --untracked-files=all)"
        test -z "$source_status"
        repository_root="$(git rev-parse --show-toplevel)"
        workspace="$GITHUB_WORKSPACE"
        case "$RUNNER_OS" in
          Windows) repository_root="$(cygpath -u -- "$repository_root")"; workspace="$(cygpath -u -- "$workspace")" ;;
          Linux|macOS) ;;
          *) exit 125 ;;
        esac
        current_root="$(pwd -P)"
        repository_root="$(cd -- "$repository_root" && pwd -P)"
        workspace="$(cd -- "$workspace" && pwd -P)"
        test "$current_root" = "$repository_root"
        test "$current_root" = "$workspace"
    SH
    TOOLS = <<~'SH'
        set -euo pipefail
        case "$RUNNER_OS" in
          Windows) exec python -I -B -S "$(cygpath -w -- "$GITHUB_WORKSPACE/scripts/initial-recipient-runner-tools.py")" ;;
          Linux|macOS) exec python3 -I -B -S "$GITHUB_WORKSPACE/scripts/initial-recipient-runner-tools.py" ;;
          *) exit 125 ;;
        esac
    SH
    JDK = <<~'SH'
        set -euo pipefail
        case "$RUNNER_ARCH" in X64|ARM64) ;; *) exit 125 ;; esac
        daemon_variable="JAVA_HOME_21_${RUNNER_ARCH}"
        daemon_home="${!daemon_variable}"
        case "$daemon_home" in ''|*$'\n'*|*$'\r'*) exit 125 ;; esac
        printf 'P2PKIT_AUDIT_JDK21=%s\n' "$daemon_home" >> "$GITHUB_ENV"
    SH
    SEAL_FIELDS = {"SHA256" => "Sha256", "END_NS" => "EndNs", "CLOCK_ROLE" => "ClockRole",
        "CLOCK_DOMAIN" => "ClockDomain", "CLOCK_TICKS_PER_SECOND" => "ClockTicksPerSecond", "BOOT_SHA256" => "BootSha256"}.freeze
    UPLOAD_FIELDS = {"SHA256" => "receipt-sha256", "DIRECTORY_SHA256" => "directory-identity-sha256",
        "FILE_METADATA_SHA256" => "file-metadata-sha256", "OWNER_CLOSE_SHA256" => "file-owner-close-sha256"}.freeze
    ACTIONS = {
        "initial-recipient-cache-provider" => [%w[phase python tool-path],
            %w[readback-sha256 cache-primary-key cache-matched-key cache-hit],
            "require('../../../scripts/hosted-cache-provider-action.cjs').mainInitialRecipient();"],
        "initial-recipient-upload" => [%w[mode python tool-path],
            %w[artifact-id receipt-base64 receipt-sha256 directory-identity-sha256 file-metadata-sha256 file-owner-close-sha256],
            "require('../../../scripts/hosted-initial-artifact-action.cjs').main();"],
        "initial-recipient-productive-upload" => [%w[mode python tool-path],
            %w[artifact-id receipt-base64 receipt-sha256 directory-identity-sha256 file-metadata-sha256 file-owner-close-sha256],
            "require('../../../scripts/hosted-initial-artifact-action.cjs').mainProductive();"],
    }.freeze

    def self.need(value, reason)
        raise Error, reason unless value
    end

    def self.parse(text, label)
        tree = YAML.parse_stream(text)
        need(tree.children.size == 1, "#{label}: one YAML document required")
        HeavyJobQueuePolicy.check_yaml_keys(tree, label)
        walk = lambda do |node|
            need(!node.is_a?(Psych::Nodes::Alias), "#{label}: aliases are not admitted")
            Array(node.children).each { |child| walk.call(child) }
        end
        walk.call(tree)
        value = YAML.safe_load(text, aliases: false)
        need(value.is_a?(Hash), "#{label}: mapping required")
        value
    rescue Psych::Exception, HeavyJobQueuePolicy::Error => error
        raise Error, "#{label}: invalid YAML: #{error.message}"
    end

    def self.expression(value); "${{ #{value} }}"; end
    def self.output(id, field); expression("steps.#{id}.outputs.#{field}"); end
    def self.outcome(id); expression("steps.#{id}.outcome"); end
    def self.success(id); expression("success() && steps.#{id}.outcome == 'success'"); end

    def self.command(name, id, previous, file, arguments, claims, minutes = 3)
        {"name" => name, "id" => id, "if" => success(previous), "timeout-minutes" => minutes, "shell" => "bash",
            "env" => {"P2PKIT_PYTHON" => output("tools", "python"),
                "P2PKIT_ACTIONS_READ_TOKEN" => expression("github.token")}.merge(claims),
            "run" => <<~SH}
                set -euo pipefail
                case "$RUNNER_OS" in
                  Windows) script="$(cygpath -w -- "$GITHUB_WORKSPACE/scripts/#{file}")" ;;
                  Linux|macOS) script="$GITHUB_WORKSPACE/scripts/#{file}" ;;
                  *) exit 125 ;;
                esac
                exec "$P2PKIT_PYTHON" -I -B -S "$script" #{arguments}
            SH
    end

    def self.action(name, id, previous, local, mode, claims, minutes = 3)
        mode_field = local == "initial-recipient-cache-provider" ? "phase" : "mode"
        {"name" => name, "id" => id, "if" => success(previous), "timeout-minutes" => minutes,
            "uses" => "./.github/actions/#{local}", "with" => {mode_field => mode,
                "python" => output("tools", "python"), "tool-path" => output("tools", "tool-path")}, "env" => claims}
    end

    def self.common_steps
        [
            {"name" => "Hold all Stage1 execution until exact-source activation is approved", "shell" => "bash", "run" => HOLD},
            {"name" => "Check out the actual reviewed event source without persisted credentials", "timeout-minutes" => 2,
                "uses" => "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "env" => {"GIT_CONFIG_COUNT" => "1", "GIT_CONFIG_KEY_0" => "core.autocrlf", "GIT_CONFIG_VALUE_0" => "false"},
                "with" => {"ref" => expression("github.sha"), "fetch-depth" => 1, "fetch-tags" => false, "persist-credentials" => false}},
            {"name" => "Fetch full no-tag history and verify source before repository Python", "timeout-minutes" => 1,
                "shell" => "bash", "env" => {"GIT_TERMINAL_PROMPT" => "0", "P2PKIT_EXPECTED_SHA" => expression("inputs.expected_sha"),
                    "P2PKIT_EXPECTED_TREE" => expression("inputs.expected_tree")}, "run" => PREFLIGHT},
        ]
    end

    def self.tools_step
        {"name" => "Observe original native Python and tool PATH", "id" => "tools", "timeout-minutes" => 1,
            "shell" => "bash", "run" => TOOLS}
    end

    def self.seal_claims(prefix, id, output_prefix)
        SEAL_FIELDS.to_h { |suffix, field| [prefix + suffix, output(id, output_prefix + field)] }
    end

    def self.upload_claims(prefix, id)
        UPLOAD_FIELDS.to_h { |suffix, field| [prefix + suffix, output(id, field)] }.merge(prefix + "OUTCOME" => outcome(id))
    end

    def self.gate_steps
        primary = {"P2PKIT_INITIAL_PRIMARY_OUTCOME" => outcome("initial-originals"),
            "P2PKIT_INITIAL_PRIMARY_RESULT_SHA256" => output("initial-originals", "initialOriginalsSha256"),
            "P2PKIT_INITIAL_PRIMARY_HANDOFF_SHA256" => output("initial-originals", "gateHandoffSha256")}
        crypto = primary.merge("P2PKIT_INITIAL_CRYPTO_OUTCOME" => outcome("initial-custody-export"),
            "P2PKIT_INITIAL_CRYPTO_STEP_SHA256" => output("initial-custody-export", "initialCryptoStepSha256"),
            "P2PKIT_INITIAL_EXPORTER_RETURN_SHA256" => output("initial-custody-export", "initialExporterReturnSha256"))
        collected = crypto.merge("P2PKIT_INITIAL_CUSTODY_OUTCOME" => outcome("initial-custody"),
            "P2PKIT_INITIAL_CUSTODY_SHA256" => output("initial-custody", "initialCustodySha256"),
            "P2PKIT_INITIAL_CUSTODY_EXPORTER_RETURN_SHA256" => output("initial-custody", "initialExporterReturnSha256"))
        seed = seal_claims("P2PKIT_INITIAL_SEAL_", "initial-before", "initialSeal").merge(
            "P2PKIT_INITIAL_SEAL_OUTCOME" => outcome("initial-seal"),
            "P2PKIT_INITIAL_BEFORE_SHA256" => output("initial-before", "initialBeforeSha256"),
            "P2PKIT_INITIAL_BEFORE_OUTCOME" => outcome("initial-before"))
        common_steps + [tools_step,
            command("Acquire original nonproductive Stage1 eligibility", "initial-originals", "tools",
                "run-hosted-initial-recipient.py", "prepare-originals", {}),
            command("P2pKit initial custody export", "initial-custody-export", "initial-originals",
                "run-hosted-initial-recipient-custody.py", "collect-export --kind gate", primary, 6),
            command("P2pKit initial post-export custody", "initial-custody", "initial-custody-export",
                "run-hosted-initial-recipient-custody.py", "collect-close --kind gate", crypto, 1),
            command("P2pKit initial custody seal", "initial-seal", "initial-custody",
                "run-hosted-initial-recipient-custody.py", "seal-for-before --kind gate", collected, 1),
            command("P2pKit initial before-upload custody", "initial-before", "initial-seal",
                "run-hosted-initial-recipient-tail.py", "before-and-tail --kind gate", collected.merge(
                    seal_claims("P2PKIT_INITIAL_SEAL_", "initial-seal", "initialSeal"),
                    "P2PKIT_INITIAL_SEAL_OUTCOME" => outcome("initial-seal")), 1),
            action("P2pKit initial custody upload", "initial-upload", "initial-before", "initial-recipient-upload", "upload", seed, 1),
            action("P2pKit initial after-upload custody", "initial-after", "initial-upload", "initial-recipient-upload", "after",
                seed.merge(upload_claims("P2PKIT_INITIAL_UPLOAD_", "initial-upload")), 1),
        ]
    end

    def self.worker_steps
        primary = {"P2PKIT_INITIAL_PRIMARY_OUTCOME" => outcome("canonical-initialization"),
            "P2PKIT_INITIAL_PRIMARY_RESULT_SHA256" => output("canonical-initialization", "initialization-sha256"),
            "P2PKIT_INITIAL_PRIMARY_HANDOFF_SHA256" => output("canonical-initialization", "worker-handoff-sha256")}
        base = {"P2PKIT_BOOTSTRAP_PRODUCER_OUTCOME" => outcome("produce"),
            "P2PKIT_BOOTSTRAP_HANDOFF_SHA256" => output("produce", "handoffSha256"),
            "P2PKIT_BOOTSTRAP_PRODUCER_RETURN_SHA256" => output("produce", "producerReturnSha256")}
        prepared = base.merge("P2PKIT_BOOTSTRAP_SAVE_PREPARE_OUTCOME" => outcome("prepare-save"),
            "P2PKIT_BOOTSTRAP_SAVE_PREPARATION_SHA256" => output("prepare-save", "savePreparationSha256"))
        saved = prepared.merge("P2PKIT_BOOTSTRAP_SAVE_OUTCOME" => outcome("provider-save"),
            "P2PKIT_BOOTSTRAP_SAVE_READBACK_SHA256" => output("provider-save", "readback-sha256"))
        after = saved.merge("P2PKIT_BOOTSTRAP_AFTER_SAVE_OUTCOME" => outcome("after-save"),
            "P2PKIT_BOOTSTRAP_AFTER_SAVE_SHA256" => output("after-save", "afterSaveSha256"))
        probe = after.merge("P2PKIT_BOOTSTRAP_PROBE_PREPARE_OUTCOME" => outcome("prepare-probe"),
            "P2PKIT_BOOTSTRAP_PROBE_PREPARATION_SHA256" => output("prepare-probe", "probePreparationSha256"))
        probed = probe.merge("P2PKIT_BOOTSTRAP_PROBE_OUTCOME" => outcome("provider-probe"),
            "P2PKIT_BOOTSTRAP_PROBE_READBACK_SHA256" => output("provider-probe", "readback-sha256"))
        provider_outputs = {"P2PKIT_BOOTSTRAP_PROBE_PRIMARY_KEY" => output("provider-probe", "cache-primary-key"),
            "P2PKIT_BOOTSTRAP_PROBE_MATCHED_KEY" => output("provider-probe", "cache-matched-key"),
            "P2PKIT_BOOTSTRAP_PROBE_HIT" => output("provider-probe", "cache-hit")}
        final = probed.merge("P2PKIT_BOOTSTRAP_AFTER_PROBE_OUTCOME" => outcome("after-probe"),
            "P2PKIT_BOOTSTRAP_PROBE_SHA256" => output("after-probe", "probeSha256"))
        exported = final.merge("P2PKIT_INITIAL_PRODUCTIVE_EXPORT_OUTCOME" => outcome("productive-export"),
            "P2PKIT_INITIAL_PRODUCTIVE_EXPORT_TRANSFER_SHA256" => output("productive-export", "initialProductiveExportTransferSha256"),
            "P2PKIT_INITIAL_PRODUCTIVE_MANIFEST_SHA256" => output("productive-export", "initialProductiveManifestSha256"))
        collected = exported.merge("P2PKIT_INITIAL_PRODUCTIVE_COLLECT_OUTCOME" => outcome("productive-collect"),
            "P2PKIT_INITIAL_PRODUCTIVE_COLLECT_CLOSE_SHA256" => output("productive-collect", "initialProductiveCollectCloseSha256"))
        seed = {"P2PKIT_INITIAL_PRODUCTIVE_BEFORE_SHA256" => output("productive-before", "initialProductiveBeforeSha256"),
            "P2PKIT_INITIAL_PRODUCTIVE_BEFORE_OUTCOME" => outcome("productive-before"),
            "P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_SHA256" => output("productive-before", "initialProductiveDeadlineSha256"),
            "P2PKIT_INITIAL_PRODUCTIVE_DEADLINE_BASE64" => output("productive-before", "initialProductiveDeadlineBase64"),
            "P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME" => outcome("productive-seal")}
        productive = "run-hosted-initial-recipient-productive.py"
        common_steps + [
            {"name" => "Configure native daemon Java 21 and wrapper Java 17", "timeout-minutes" => 3,
                "uses" => "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961",
                "with" => {"distribution" => "temurin", "java-version" => "21\n17\n"}},
            {"name" => "Bind the native Stage1 daemon JDK", "timeout-minutes" => 1, "shell" => "bash", "run" => JDK},
            tools_step,
            {"name" => "Initialize the exact Stage1 source within existing component windows", "id" => "canonical-initialization",
                "if" => success("tools"), "timeout-minutes" => 12, "uses" => "./.github/actions/initial-recipient-initialize"},
            command("Produce the original configuration-only dependency cohort", "produce", "canonical-initialization", productive, "produce", primary, 56),
            command("Prepare original initial cache save", "prepare-save", "produce", productive, "prepare-save", base),
            action("Save the exact original initial dependency cohort", "provider-save", "prepare-save", "initial-recipient-cache-provider", "save", prepared),
            command("Observe original initial cache save and known retirement", "after-save", "provider-save", productive, "after-save", saved, 6),
            command("Prepare original initial cache lookup", "prepare-probe", "after-save", productive, "prepare-probe", after),
            action("Look up the exact saved initial dependency cohort", "provider-probe", "prepare-probe", "initial-recipient-cache-provider", "lookup", probe),
            command("Observe original initial cache lookup and known retirement", "after-probe", "provider-probe", productive, "after-probe", probed.merge(provider_outputs)),
            command("P2pKit initial productive custody export", "productive-export", "after-probe", productive, "custody-export", final, 6),
            command("P2pKit initial productive post-export custody", "productive-collect", "productive-export", productive, "custody-collect", exported),
            command("P2pKit initial productive custody seal", "productive-seal", "productive-collect", "run-hosted-initial-recipient-productive-receiver.py", "seal", collected),
            command("P2pKit initial productive before-upload custody", "productive-before", "productive-seal", "run-hosted-initial-recipient-productive-tail.py", "before",
                collected.merge(seal_claims("P2PKIT_INITIAL_PRODUCTIVE_SEAL_", "productive-seal", "initialProductiveSeal"),
                    "P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME" => outcome("productive-seal"))),
            action("P2pKit initial productive custody upload", "productive-upload", "productive-before", "initial-recipient-productive-upload", "upload", seed),
            action("P2pKit initial productive after-upload custody", "productive-after", "productive-upload", "initial-recipient-productive-upload", "after",
                seed.merge(upload_claims("P2PKIT_INITIAL_PRODUCTIVE_UPLOAD_", "productive-upload"))),
        ]
    end

    def self.check(workflow)
        value = workflow.dup
        if value.key?(true)
            need(!value.key?("on"), "ambiguous event key")
            value["on"] = value.delete(true)
        end
        need(value.keys.sort == %w[concurrency jobs name on permissions], "closed workflow fields")
        need(value["name"] == "Dependency cache bootstrap (productive stage held)", "workflow identity")
        inputs = {"selection" => {"description" => "Exact dependency cohort; not ordinary test acceptance", "type" => "choice",
            "required" => true, "options" => SELECTORS},
            "expected_sha" => {"description" => "Full independently reviewed source commit", "type" => "string", "required" => true},
            "expected_tree" => {"description" => "Full independently reviewed source tree", "type" => "string", "required" => true}}
        need(value["on"] == {"workflow_dispatch" => {"inputs" => inputs}}, "exact manual event and three inputs")
        need(value["permissions"] == {}, "closed workflow permissions")
        need(value["concurrency"] == {"group" => "p2pkit-initial-recipient-bootstrap", "queue" => "max", "cancel-in-progress" => false}, "separate non-cancelling workflow queue")
        jobs = value["jobs"]
        need(jobs.is_a?(Hash) && jobs.keys.sort == %w[initial-recipient-gate populate], "two exact unaliased jobs")
        gate = {"if" => expression("github.repository == 'p2pKit/P2pKit' && github.event_name == 'workflow_dispatch' && github.ref == '#{REF}' && github.sha == inputs.expected_sha"),
            "permissions" => {"contents" => "read", "actions" => "read"}, "runs-on" => "ubuntu-24.04", "timeout-minutes" => 6,
            "environment" => "initial-recipient-execution", "steps" => gate_steps}
        worker = {"needs" => "initial-recipient-gate", "permissions" => {"contents" => "read", "actions" => "read"},
            "runs-on" => RUNNERS, "timeout-minutes" => 90, "concurrency" => HeavyJobQueuePolicy::QUEUE, "steps" => worker_steps}
        {"initial-recipient-gate" => gate, "populate" => worker}.each do |id, expected|
            actual = jobs[id]
            need(actual.is_a?(Hash) && actual.keys.sort == expected.keys.sort, "#{id}: closed job fields")
            need(actual["timeout-minutes"].instance_of?(Integer), "#{id}: integer job ceiling")
            need(actual.reject { |key, _| key == "steps" } == expected.reject { |key, _| key == "steps" }, "#{id}: exact source/environment/runner/queue/needs")
            steps = actual["steps"]
            need(steps.is_a?(Array) && steps.size == expected["steps"].size, "#{id}: exact Step chain")
            expected["steps"].each_with_index do |step, index|
                if step["id"] == "produce"
                    need(steps[index].is_a?(Hash) && steps[index]["timeout-minutes"].instance_of?(Integer),
                        "#{id}: integer produce execution ceiling")
                end
                need(steps[index] == step, "#{id}: exact Step #{index + 1} #{step['name']}")
            end
        end
        true
    end

    def self.regular(root, relative)
        need(relative.match?(%r{\A(?:\.github/actions|scripts)/[a-zA-Z0-9_./-]+\z}) && !relative.split("/").include?(".."), "fixed source path")
        current = root
        relative.split("/").each do |part|
            current = File.join(current, part)
            need(!File.symlink?(current), "source symlink forbidden: #{relative}")
        end
        need(File.file?(current) && File.realpath(current) == File.join(File.realpath(root), relative), "regular canonical source required: #{relative}")
        File.read(current)
    end

    def self.check_sources(root)
        ACTIONS.each do |name, (inputs, outputs, entry)|
            action = parse(regular(root, ".github/actions/#{name}/action.yml"), name)
            need(action.keys.sort == %w[description inputs name outputs runs] &&
                %w[name description].all? { |key| action[key].is_a?(String) && !action[key].empty? }, "#{name}: closed Action descriptor")
            need(action["runs"] == {"using" => "node24", "main" => "index.cjs"}, "#{name}: fixed Node24 entry")
            need(action["inputs"].is_a?(Hash) && action["inputs"].keys.sort == inputs.sort &&
                action["inputs"].values.all? { |input| input.is_a?(Hash) && input.keys.sort == %w[description required] &&
                    input["required"] == true && input["description"].is_a?(String) && !input["description"].empty? }, "#{name}: three exact required inputs")
            need(action["outputs"].is_a?(Hash) && action["outputs"].keys.sort == outputs.sort &&
                action["outputs"].values.all? { |output| output.is_a?(Hash) && output.keys == ["description"] &&
                    output["description"].is_a?(String) && !output["description"].empty? }, "#{name}: exact output interface")
            lines = regular(root, ".github/actions/#{name}/index.cjs").lines.map(&:strip).reject { |line| line.empty? || line.start_with?("//") }
            need(lines == ["'use strict';", entry], "#{name}: fixed source entry only")
        end
        initializer = parse(regular(root, ".github/actions/initial-recipient-initialize/action.yml"), "initializer")
        need(initializer.keys.sort == %w[description name outputs runs] && initializer["runs"].is_a?(Hash) &&
            initializer["runs"].keys.sort == %w[steps using] && initializer["runs"]["using"] == "composite", "fixed initializer composite")
        outputs = initializer["outputs"]
        expected_outputs = {"recipient-crypto-originals-sha256" => output("recipient", "recipientCryptoOriginalsSha256"),
            "initialization-sha256" => output("initializer", "initializationSha256"),
            "worker-handoff-sha256" => output("initializer", "workerHandoffSha256")}
        need(outputs.is_a?(Hash) && outputs.keys.sort == expected_outputs.keys.sort &&
            expected_outputs.all? { |name, value| outputs[name].is_a?(Hash) && outputs[name].keys.sort == %w[description value] &&
                outputs[name]["description"].is_a?(String) && !outputs[name]["description"].empty? && outputs[name]["value"] == value },
            "original initializer outputs")
        steps = initializer["runs"]["steps"]
        need(steps.is_a?(Array) && steps.size == 2 && steps.map { |step| step["id"] } == %w[recipient initializer], "one canonical sender/initializer")
        need(steps[0]["name"] == "Validate recipient and retain private step continuity" && !steps[0].key?("if") &&
            steps[1]["name"] == "Initialize within the original receiving 120 seconds", "original initializer Steps")
        need(steps[0]["env"] == {"P2PKIT_ACTIONS_READ_TOKEN" => expression("github.token")} &&
            steps[1]["if"] == success("recipient") && steps[1]["env"] == {
                "P2PKIT_ACTIONS_READ_TOKEN" => expression("github.token"), "P2PKIT_INITIAL_RECIPIENT_OUTCOME" => outcome("recipient"),
                "P2PKIT_INITIAL_RECIPIENT_SENDER_SHA256" => output("recipient", "recipientSenderSha256"),
                "P2PKIT_INITIAL_RECIPIENT_STEP_SHA256" => output("recipient", "recipientStepSha256"),
                "P2PKIT_INITIAL_RECIPIENT_CRYPTO_ORIGINALS_SHA256" => output("recipient", "recipientCryptoOriginalsSha256")}, "original initializer token/claims")
        steps.zip(%w[sender-step initialize-step]).each do |step, operation|
            expected = "case \"$RUNNER_OS\" in\n  Windows) exec python -I -B -S scripts/run-hosted-initial-recipient.py #{operation} ;;\n  Linux|macOS) exec python3 -I -B -S scripts/run-hosted-initial-recipient.py #{operation} ;;\n  *) exit 125 ;;\nesac\n"
            need(step["shell"] == "bash" && step["working-directory"] == expression("github.workspace") && step["run"] == expected &&
                (step.keys - %w[name id if shell working-directory env run]).empty?, "fixed initializer source route")
        end
        true
    end
end

if $PROGRAM_NAME == __FILE__
    abort "Usage: #{$PROGRAM_NAME} [repository-root]" if ARGV.length > 1
    root = ARGV.fetch(0, File.expand_path("..", __dir__))
    begin
        path = File.join(root, ".github/workflows", InitialRecipientBootstrapPolicy::FILE)
        InitialRecipientBootstrapPolicy.need(File.file?(path) && !File.symlink?(path), "regular bootstrap workflow required")
        InitialRecipientBootstrapPolicy.check(InitialRecipientBootstrapPolicy.parse(File.read(path), path))
        InitialRecipientBootstrapPolicy.check_sources(root)
    rescue InitialRecipientBootstrapPolicy::Error, SystemCallError => error
        abort "FATAL: #{error.message}"
    end
    puts "RESULT: PASS — exact held Stage1 wiring and fixed Action interfaces only; no execution or qualification"
end
