#!/usr/bin/env ruby
# Offline workflow-shape controls only: no CLI, native owner, API or hosted run.
require "json"
require "set"
require_relative "../check-heavy-job-queue-policy"

module InitialRecipientWorkflowPolicy
    class Error < StandardError; end

    SELECTIONS = {
        "desktop-linux-x64" => "ubuntu-latest",
        "desktop-windows-x64" => "windows-latest",
        "desktop-macos-arm64" => "macos-26",
        "desktop-macos-x64" => "macos-15-intel",
        "full-macos-arm64" => "macos-26",
        "full-macos-x64" => "macos-15-intel",
    }.freeze
    SELECTOR = "${{ fromJSON('#{JSON.generate(SELECTIONS)}')[inputs.selection] }}"
    CONDITION = "${{ github.repository == 'p2pKit/P2pKit' && github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/work/nonphysical-integration-20260915-022112' && github.sha == inputs.expected_sha }}"
    PRESTART = <<~'SH'
        set -euo pipefail
        test "$GITHUB_REPOSITORY" = p2pKit/P2pKit
        test "$GITHUB_EVENT_NAME" = workflow_dispatch
        test "$GITHUB_REF" = refs/heads/work/nonphysical-integration-20260915-022112
        [[ "$P2PKIT_EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]
        [[ "$P2PKIT_EXPECTED_TREE" =~ ^[0-9a-f]{40}$ ]]
        test "$GITHUB_SHA" = "$P2PKIT_EXPECTED_SHA"
        git fetch --no-tags --unshallow origin \
          refs/heads/main:refs/remotes/origin/main \
          refs/heads/work/nonphysical-integration-20260915-022112:refs/remotes/origin/work/nonphysical-integration-20260915-022112
        test "$(git rev-parse --is-shallow-repository)" = false
        test "$(git rev-parse HEAD)" = "$P2PKIT_EXPECTED_SHA"
        test "$(git rev-parse 'HEAD^{tree}')" = "$P2PKIT_EXPECTED_TREE"
        test "$(git rev-parse refs/remotes/origin/main)" = 3bc76f956f8f47447b51a62474fc878b9c43173c
        test "$(git rev-parse 'refs/remotes/origin/main^{tree}')" = 2a1105fde1d1ac299448489501e29d7a0d4a407a
        test "$(git rev-parse refs/remotes/origin/work/nonphysical-integration-20260915-022112)" = "$P2PKIT_EXPECTED_SHA"
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
    BIND_JDK = <<~'SH'
        set -euo pipefail
        case "$RUNNER_ARCH" in X64|ARM64) ;; *) echo 'FATAL: unsupported native Java architecture' >&2; exit 1 ;; esac
        daemon_variable="JAVA_HOME_21_${RUNNER_ARCH}"
        daemon_home="${!daemon_variable}"
        case "$daemon_home" in ''|*$'\n'*|*$'\r'*) echo 'FATAL: missing or invalid daemon JDK path' >&2; exit 1 ;; esac
        printf 'P2PKIT_AUDIT_JDK21=%s\n' "$daemon_home" >> "$GITHUB_ENV"
    SH
    ACQUIRE = "exec /usr/bin/python3 -I -B -S scripts/run-hosted-initial-recipient.py prepare-originals"
    HOLD = <<~'SH'
        echo 'INITIAL_RECIPIENT_STAGE1=HOLD; PRODUCTIVE_BOOTSTRAP_NOT_QUALIFIED' >&2
        exit 125
    SH
    CUSTODY_STEPS = [
        ["collect-export", "initial-custody-export"],
        ["collect-close", "initial-custody"],
        ["seal", "initial-seal"],
        ["upload-before", "initial-upload-before"],
        [nil, "initial-evidence"],
        ["upload-after", "initial-upload-after"],
    ].map(&:freeze).freeze

    def self.need(condition, message)
        raise Error, message unless condition
    end

    def self.keys(value, expected, message)
        need(value.is_a?(Hash) && value.keys.sort == expected.sort, message)
    end

    def self.timeout(value, minutes)
        need(value.instance_of?(Integer) && value == minutes, "exact reviewed workflow timeout changed")
    end

    def self.source_prefix(checkout, prestart)
        keys(checkout, %w[name timeout-minutes uses env with], "checkout cannot ignore failure or gain inputs")
        need(checkout["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "pinned checkout required")
        need(checkout["env"] == {"GIT_CONFIG_COUNT" => "1", "GIT_CONFIG_KEY_0" => "core.autocrlf",
                                 "GIT_CONFIG_VALUE_0" => "false"}, "LF checkout configuration must be step-local")
        need(checkout["with"] == {"ref" => "${{ github.sha }}", "fetch-depth" => 1, "fetch-tags" => false,
                                  "persist-credentials" => false} && checkout["with"]["fetch-depth"].instance_of?(Integer),
             "actual source, shallow no-tag checkout and no persisted credentials required")
        timeout(checkout["timeout-minutes"], 2)
        keys(prestart, %w[name timeout-minutes shell env run], "source history/prestart scope changed")
        need(prestart["shell"] == "bash" && prestart["env"] == {
            "GIT_TERMINAL_PROMPT" => "0", "P2PKIT_EXPECTED_SHA" => "${{ inputs.expected_sha }}",
            "P2PKIT_EXPECTED_TREE" => "${{ inputs.expected_tree }}",
        } && prestart["run"] == PRESTART, "fixed public full-history/pre-Python source check required")
        timeout(prestart["timeout-minutes"], 1)
    end

    def self.custody_tail(steps, kind)
        need(%w[gate worker].include?(kind) && steps.is_a?(Array) && steps.size == 6,
             "exact six-Step same-job custody tail required")
        primary = kind == "gate" ? "initial-originals" : "canonical-initialization"
        result = kind == "gate" ? "initialOriginalsSha256" : "initialization-sha256"
        handoff = kind == "gate" ? "gateHandoffSha256" : "worker-handoff-sha256"
        environment = {
            "P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}",
            "P2PKIT_INITIAL_PRIMARY_OUTCOME" => "${{ steps.#{primary}.outcome }}",
            "P2PKIT_INITIAL_PRIMARY_RESULT_SHA256" => "${{ steps.#{primary}.outputs.#{result} }}",
            "P2PKIT_INITIAL_PRIMARY_HANDOFF_SHA256" => "${{ steps.#{primary}.outputs.#{handoff} }}",
        }
        predecessors = [primary]
        CUSTODY_STEPS.each_with_index do |(operation, id), index|
            step = steps[index]
            keys(step, operation ? %w[name id if timeout-minutes shell env run] : %w[name id if timeout-minutes uses with],
                 "custody Step cannot acquire extra execution/authority fields")
            need(step["name"].is_a?(String) && !step["name"].empty? && step["id"] == id,
                 "fixed custody Step identity/order required")
            condition = "${{ success() && " + predecessors.map { |prior| "steps.#{prior}.outcome == 'success'" }.join(" && ") + " }}"
            need(step["if"] == condition, "every authentic preceding Step must succeed")
            timeout(step["timeout-minutes"], operation == "collect-export" ? 6 : 1)
            if operation
                command = "scripts/run-hosted-initial-recipient-custody.py #{operation} --kind #{kind}"
                run = if kind == "gate"
                    "exec /usr/bin/python3 -I -B -S #{command}"
                else
                    <<~SH
                        case "$RUNNER_OS" in
                          Windows) exec python -I -B -S #{command} ;;
                          Linux|macOS) exec python3 -I -B -S #{command} ;;
                          *) exit 125 ;;
                        esac
                    SH
                end
                need(step["shell"] == "bash" && step["run"] == run, "fixed isolated native custody command required")
                need(step["env"] == environment, "fresh Step-only token and exact original predecessor outputs required")
            else
                need(step["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
                     "fixed encrypted upload Action pin required")
                root = "${{ runner.temp }}/p2pkit-initial-recipient-${{ github.run_id }}-${{ github.run_attempt }}-#{kind}-custody/export-output/"
                expected = {
                    "name" => "stage1-#{kind}-evidence-${{ inputs.selection }}-${{ runner.os }}-${{ runner.arch }}-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
                    "path" => root + "evidence.tar.gz.gpg\n" + root + "manifest.json\n",
                    "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0,
                    "overwrite" => false, "include-hidden-files" => false,
                }
                need(step["with"] == expected && step["with"]["retention-days"].instance_of?(Integer) &&
                     step["with"]["compression-level"].instance_of?(Integer),
                     "only the two exact encrypted-output files and finite upload policy are permitted")
            end
            predecessors << id
            case id
            when "initial-custody-export"
                environment.merge!(
                    "P2PKIT_INITIAL_CRYPTO_OUTCOME" => "${{ steps.initial-custody-export.outcome }}",
                    "P2PKIT_INITIAL_CRYPTO_STEP_SHA256" => "${{ steps.initial-custody-export.outputs.initialCryptoStepSha256 }}",
                    "P2PKIT_INITIAL_EXPORTER_RETURN_SHA256" => "${{ steps.initial-custody-export.outputs.initialExporterReturnSha256 }}")
            when "initial-custody"
                environment.merge!(
                    "P2PKIT_INITIAL_CUSTODY_OUTCOME" => "${{ steps.initial-custody.outcome }}",
                    "P2PKIT_INITIAL_CUSTODY_SHA256" => "${{ steps.initial-custody.outputs.initialCustodySha256 }}",
                    "P2PKIT_INITIAL_CUSTODY_EXPORTER_RETURN_SHA256" => "${{ steps.initial-custody.outputs.initialExporterReturnSha256 }}")
            when "initial-seal"
                environment.merge!(
                    "P2PKIT_INITIAL_SEAL_OUTCOME" => "${{ steps.initial-seal.outcome }}",
                    "P2PKIT_INITIAL_SEAL_SHA256" => "${{ steps.initial-seal.outputs.initialSealSha256 }}")
            when "initial-upload-before"
                environment.merge!(
                    "P2PKIT_INITIAL_UPLOAD_BEFORE_OUTCOME" => "${{ steps.initial-upload-before.outcome }}",
                    "P2PKIT_INITIAL_UPLOAD_WINDOW_SHA256" => "${{ steps.initial-upload-before.outputs.initialUploadWindowSha256 }}")
            when "initial-evidence"
                environment.merge!(
                    "P2PKIT_INITIAL_UPLOAD_OUTCOME" => "${{ steps.initial-evidence.outcome }}",
                    "P2PKIT_INITIAL_ARTIFACT_ID" => "${{ steps.initial-evidence.outputs.artifact-id }}",
                    "P2PKIT_INITIAL_ARTIFACT_DIGEST" => "${{ steps.initial-evidence.outputs.artifact-digest }}")
            end
        end
    end

    def self.check(workflow)
        # Psych's YAML 1.1 parser represents the unquoted Actions `on` as true.
        event_key = workflow.key?("on") ? "on" : true
        need(workflow.keys.to_set == ["name", event_key, "permissions", "concurrency", "jobs"].to_set,
             "unexpected workflow-level execution or permission scope")
        need(workflow["name"] == "Dependency cache bootstrap (productive stage held)", "qualification scope changed")
        keys(workflow[event_key], ["workflow_dispatch"], "dispatch-only event required")
        dispatch = workflow[event_key]["workflow_dispatch"]
        keys(dispatch, ["inputs"], "unexpected dispatch contract")
        inputs = dispatch["inputs"]
        keys(inputs, %w[selection expected_sha expected_tree], "exact three inputs required")
        inputs.each do |name, input|
            keys(input, name == "selection" ? %w[description type required options] : %w[description type required],
                 "input defaults/aliases/extra authority forbidden")
            need(input["description"].is_a?(String) && !input["description"].empty? && input["required"] == true,
                 "required documented input")
            need(input["type"] == (name == "selection" ? "choice" : "string"), "input type changed")
        end
        need(inputs["selection"]["options"] == SELECTIONS.keys, "closed six-cohort selection required")
        need(workflow["permissions"] == {}, "no workflow-wide credentials")
        need(workflow["concurrency"] == {"group" => "p2pkit-initial-recipient-bootstrap", "queue" => "max",
                                       "cancel-in-progress" => false}, "preserve allocated gate attempts outside heavy queue")
        jobs = workflow["jobs"]
        keys(jobs, %w[initial-recipient-gate populate], "exact two jobs required")
        gate = jobs["initial-recipient-gate"]
        keys(gate, %w[if permissions runs-on timeout-minutes environment steps], "gate identity/authority scope changed")
        need(gate["if"] == CONDITION && gate["runs-on"] == "ubuntu-24.04", "actual Stage1 gate context required")
        need(gate["permissions"] == {"contents" => "read", "actions" => "read"}, "minimal gate read permissions required")
        need(gate["environment"] == "initial-recipient-execution", "separate pre-execution environment required")
        timeout(gate["timeout-minutes"], 6)
        steps = gate["steps"]
        need(steps.is_a?(Array) && steps.size == 9, "only original acquisition and exact encrypted custody tail permitted")
        checkout, prestart, acquire = steps.first(3)
        source_prefix(checkout, prestart)
        keys(acquire, %w[name id timeout-minutes shell env run], "original acquisition scope changed")
        need(acquire["id"] == "initial-originals" && acquire["shell"] == "bash" && acquire["run"] == ACQUIRE,
             "existing isolated nonproductive CLI required")
        need(acquire["env"] == {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"}, "read token must remain step scoped")
        timeout(acquire["timeout-minutes"], 3)
        custody_tail(steps.drop(3), "gate")
        worker = jobs["populate"]
        keys(worker, %w[needs permissions runs-on timeout-minutes concurrency steps], "exact nonproductive worker scope required")
        need(worker["needs"] == "initial-recipient-gate" &&
             worker["permissions"] == {"contents" => "read", "actions" => "read"} && worker["runs-on"] == SELECTOR,
             "actual dependent native selector required; no fallback")
        timeout(worker["timeout-minutes"], 20)
        need(worker["concurrency"] == HeavyJobQueuePolicy::QUEUE, "worker must join the noncancelling heavy queue")
        steps = worker["steps"]
        need(steps.is_a?(Array) && steps.size == 12, "exact nonproductive prefix, encrypted custody and held tail required")
        checkout, prestart, java, jdk, initializer = steps.first(5)
        hold = steps.last
        source_prefix(checkout, prestart)
        keys(java, %w[name timeout-minutes uses with], "only native pinned JDK setup permitted")
        need(java["uses"] == "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961" &&
             java["with"] == {"distribution" => "temurin", "java-version" => "21\n17\n"},
             "native21 then17 required without a cache or architecture override")
        timeout(java["timeout-minutes"], 3)
        keys(jdk, %w[name timeout-minutes shell run], "fixed native JDK binding required")
        need(jdk["shell"] == "bash" && jdk["run"] == BIND_JDK, "closed native daemon JDK path required")
        timeout(jdk["timeout-minutes"], 1)
        keys(initializer, %w[name id timeout-minutes uses], "only the maintained initializer Action permitted")
        need(initializer["id"] == "canonical-initialization" &&
             initializer["uses"] == "./.github/actions/initial-recipient-initialize", "exact same-job Steps edge required")
        timeout(initializer["timeout-minutes"], 12)
        custody_tail(steps[5, 6], "worker")
        need(hold == {"name" => "Hold the unqualified productive bootstrap", "timeout-minutes" => 1,
                      "shell" => "bash", "run" => HOLD} && hold["timeout-minutes"].instance_of?(Integer),
             "productive HOLD must remain unconditional and blocking after the prefix")
    end

    def self.custody_tail_controls(workflow)
        # One positive actual workflow plus NEW tail mutations only. This entry
        # never constructs/runs the earlier prefix or queue mutation suites.
        check(workflow)
        original = Marshal.dump(workflow)
        mutations = {}
        {"initial-recipient-gate" => [3, "gate"], "populate" => [5, "worker"]}.each do |job, (start, kind)|
            CUSTODY_STEPS.each_with_index do |(operation, id), offset|
                index = start + offset
                mutations["#{kind} missing #{id}"] = ->(w) { w["jobs"][job]["steps"].delete_at(index) }
                mutations["#{kind} changed #{id} identity"] = ->(w) { w["jobs"][job]["steps"][index]["id"] = "unbound-step" }
                mutations["#{kind} ignores #{id} failure"] = ->(w) { w["jobs"][job]["steps"][index]["continue-on-error"] = true }
                mutations["#{kind} unconditional #{id}"] = ->(w) { w["jobs"][job]["steps"][index]["if"] = "${{ always() }}" }
                mutations["#{kind} enlarged #{id} timeout"] = ->(w) { w["jobs"][job]["steps"][index]["timeout-minutes"] += 1 }
                if operation
                    mutations["#{kind} missing fresh #{id} token"] = ->(w) {
                        w["jobs"][job]["steps"][index]["env"].delete("P2PKIT_ACTIONS_READ_TOKEN")
                    }
                    mutations["#{kind} loses #{id} interpreter isolation"] = ->(w) {
                        w["jobs"][job]["steps"][index]["run"].sub!(" -I", "")
                    }
                end
            end
            5.times do |offset|
                mutations["#{kind} swaps tail edge #{offset}"] = ->(w) {
                    steps = w["jobs"][job]["steps"]
                    steps[start + offset], steps[start + offset + 1] = steps[start + offset + 1], steps[start + offset]
                }
            end
            workflow["jobs"][job]["steps"][start + 5]["env"].each_key do |name|
                mutations["#{kind} non-original after mapping #{name}"] = ->(w) {
                    w["jobs"][job]["steps"][start + 5]["env"][name] = "not-an-original-step-value"
                }
            end
            {
                "name" => "unbound-evidence",
                "path" => "${{ steps.initial-upload-before.outputs.path }}",
                "if-no-files-found" => "warn", "retention-days" => 15, "compression-level" => 1,
                "overwrite" => true, "include-hidden-files" => true,
            }.each do |name, value|
                mutations["#{kind} changed upload #{name}"] = ->(w) {
                    w["jobs"][job]["steps"][start + 4]["with"][name] = value
                }
            end
            mutations["#{kind} unpinned uploader"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["uses"] = "actions/upload-artifact@main"
            }
            mutations["#{kind} custody token enters uploader"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"}
            }
            mutations["#{kind} fractional retention"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["with"]["retention-days"] = 14.0
            }
            mutations["#{kind} fractional compression"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["with"]["compression-level"] = 0.0
            }
            mutations["#{kind} plaintext upload tail"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["with"]["path"] += "${{ runner.temp }}/private-originals.json\n"
            }
            mutations["#{kind} upload root wildcard"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["with"]["path"] = "${{ runner.temp }}/**\n"
            }
            mutations["#{kind} missing public manifest"] = ->(w) {
                upload = w["jobs"][job]["steps"][start + 4]["with"]
                upload["path"] = upload["path"].lines.first
            }
            mutations["#{kind} arbitrary upload input"] = ->(w) {
                w["jobs"][job]["steps"][start + 4]["with"]["extra"] = "unreviewed"
            }
            mutations["#{kind} wrong custody command kind"] = ->(w) {
                w["jobs"][job]["steps"][start]["run"].gsub!("--kind #{kind}", "--kind #{kind == 'gate' ? 'worker' : 'gate'}")
            }
            mutations["#{kind} fractional custody timeout"] = ->(w) {
                w["jobs"][job]["steps"][start + 5]["timeout-minutes"] = 1.0
            }
        end
        mutations["productive HOLD moved ahead of custody"] = ->(w) {
            steps = w["jobs"]["populate"]["steps"]
            steps[5], steps[11] = steps[11], steps[5]
        }
        mutations["productive HOLD removed after custody"] = ->(w) { w["jobs"]["populate"]["steps"].pop }
        checks = 1
        mutations.each do |name, mutate|
            candidate = Marshal.load(original)
            mutate.call(candidate)
            abort "FAIL: ineffective custody-tail mutation #{name}" if Marshal.dump(candidate) == original
            begin
                check(candidate)
            rescue Error
                checks += 1
                next
            end
            abort "FAIL: accepted custody-tail mutation #{name}"
        end
        abort "FAIL: custody-tail input workflow mutation" unless Marshal.dump(workflow) == original
        checks
    end
end

# Loading these predicates must not run either the old or new mutation suite.
if $PROGRAM_NAME == __FILE__
    arguments = ARGV.dup
    tail_only = arguments.first == "--custody-tail-only"
    arguments.shift if tail_only
    abort "Usage: #{$PROGRAM_NAME} [--custody-tail-only] [workflow.yml]" unless
        arguments.length <= 1 && (arguments.empty? || !arguments.first.start_with?("--"))
    path = arguments.fetch(0, File.expand_path("../../.github/workflows/dependency-cache-bootstrap.yml", __dir__))
    workflow = HeavyJobQueuePolicy.parse(File.read(path), path)
    if tail_only
        checks = InitialRecipientWorkflowPolicy.custody_tail_controls(workflow)
        puts "PASS: #{checks} NEW custody-tail workflow controls; legacy suites NOT_RUN; no hosted/native execution"
        exit 0
    end
    InitialRecipientWorkflowPolicy.check(workflow)
    checks = 1
    mutations = {
        "automatic producer event" => ->(w) { w.fetch(w.key?("on") ? "on" : true)["push"] = {} },
        "missing exact source input" => ->(w) { w.fetch(w.key?("on") ? "on" : true)["workflow_dispatch"]["inputs"].delete("expected_sha") },
        "defaulted owner source" => ->(w) { w.fetch(w.key?("on") ? "on" : true)["workflow_dispatch"]["inputs"]["expected_sha"]["default"] = "main" },
        "extra authority selector" => ->(w) { w.fetch(w.key?("on") ? "on" : true)["workflow_dispatch"]["inputs"]["comment_id"] = {} },
        "unknown cohort" => ->(w) { w.fetch(w.key?("on") ? "on" : true)["workflow_dispatch"]["inputs"]["selection"]["options"] << "other" },
        "workflow credential" => ->(w) { w["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
        "workflow write permission" => ->(w) { w["permissions"] = {"contents" => "write"} },
        "cancel allocated attempt" => ->(w) { w["concurrency"]["cancel-in-progress"] = true },
        "heavy queue before authorization" => ->(w) { w["concurrency"]["group"] = "p2pkit-nonphysical-heavy" },
        "drop pending queue" => ->(w) { w["concurrency"].delete("queue") },
        "extra job" => ->(w) { w["jobs"]["other"] = {} },
        "gate display alias" => ->(w) { w["jobs"]["initial-recipient-gate"]["name"] = "Gate" },
        "gate matrix alias" => ->(w) { w["jobs"]["initial-recipient-gate"]["strategy"] = {"matrix" => {"os" => ["ubuntu-24.04"]}} },
        "wrong native gate selector" => ->(w) { w["jobs"]["initial-recipient-gate"]["runs-on"] = "ubuntu-latest" },
        "unbound gate event" => ->(w) { w["jobs"]["initial-recipient-gate"].delete("if") },
        "post-build environment reused" => ->(w) { w["jobs"]["initial-recipient-gate"]["environment"] = "sample-development-release" },
        "ignored gate failure" => ->(w) { w["jobs"]["initial-recipient-gate"]["continue-on-error"] = true },
        "gate write token" => ->(w) { w["jobs"]["initial-recipient-gate"]["permissions"]["actions"] = "write" },
        "digest as cross-job authority" => ->(w) { w["jobs"]["initial-recipient-gate"]["outputs"] = {"admission" => "success"} },
        "float gate timeout" => ->(w) { w["jobs"]["initial-recipient-gate"]["timeout-minutes"] = 6.0 },
        "unreviewed checkout" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][0]["uses"] = "actions/checkout@main" },
        "different checkout source" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][0]["with"]["ref"] = "main" },
        "checkout all-tags route" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][0]["with"]["fetch-depth"] = 0 },
        "persist checkout credentials" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][0]["with"]["persist-credentials"] = true },
        "omitted full history" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"].delete_at(1) },
        "history fetch credentials" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][1]["env"]["GH_TOKEN"] = "${{ github.token }}" },
        "fetch tags" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][1]["run"].sub!("--no-tags", "--tags") },
        "missing interpreter isolation" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][2]["run"].sub!(" -I", "") },
        "productive command in gate" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][2]["run"] = "./gradlew help" },
        "ignored acquisition failure" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"][2]["continue-on-error"] = true },
        "extra gate setup" => ->(w) { w["jobs"]["initial-recipient-gate"]["steps"] << {"uses" => "actions/setup-java@main"} },
        "missing worker dependency" => ->(w) { w["jobs"]["populate"].delete("needs") },
        "worker runs after failed gate" => ->(w) { w["jobs"]["populate"]["if"] = "${{ always() }}" },
        "worker host relabel" => ->(w) { w["jobs"]["populate"]["runs-on"] = "ubuntu-latest" },
        "missing worker Actions read permission" => ->(w) { w["jobs"]["populate"]["permissions"] = {"contents" => "read"} },
        "worker automatic environment" => ->(w) { w["jobs"]["populate"]["environment"] = "initial-recipient-execution" },
        "ignored worker refusal" => ->(w) { w["jobs"]["populate"]["continue-on-error"] = true },
        "successful refusal" => ->(w) { w["jobs"]["populate"]["steps"].last["run"].sub!("exit 125", "exit 0") },
        "conditional refusal" => ->(w) { w["jobs"]["populate"]["steps"].last["if"] = "${{ false }}" },
        "ignored refusal step" => ->(w) { w["jobs"]["populate"]["steps"].last["continue-on-error"] = true },
        "provider before refusal" => ->(w) { w["jobs"]["populate"]["steps"].unshift({"uses" => "./.github/actions/dependency-cache-provider"}) },
        "unconditional Gradle cleanup" => ->(w) { w["jobs"]["populate"]["steps"] << {"if" => "${{ always() }}", "run" => "./gradlew --stop"} },
        "worker write permission" => ->(w) { w["jobs"]["populate"]["permissions"]["actions"] = "write" },
        "worker token scope" => ->(w) { w["jobs"]["populate"]["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
        "worker missing queue" => ->(w) { w["jobs"]["populate"].delete("concurrency") },
        "worker cancelling queue" => ->(w) { w["jobs"]["populate"]["concurrency"]["cancel-in-progress"] = true },
        "worker float envelope" => ->(w) { w["jobs"]["populate"]["timeout-minutes"] = 20.0 },
        "worker unknown step before source" => ->(w) { w["jobs"]["populate"]["steps"].unshift({"run" => "python arbitrary.py"}) },
        "worker unpinned Java" => ->(w) { w["jobs"]["populate"]["steps"][2]["uses"] = "actions/setup-java@main" },
        "worker reversed Java homes" => ->(w) { w["jobs"]["populate"]["steps"][2]["with"]["java-version"] = "17\n21\n" },
        "worker Gradle cache setup" => ->(w) { w["jobs"]["populate"]["steps"][2]["with"]["cache"] = "gradle" },
        "worker cross architecture" => ->(w) { w["jobs"]["populate"]["steps"][2]["with"]["architecture"] = "x64" },
        "worker JDK binding fallback" => ->(w) { w["jobs"]["populate"]["steps"][3]["run"] = "echo P2PKIT_AUDIT_JDK21=$JAVA_HOME >> $GITHUB_ENV\n" },
        "worker skipped initializer" => ->(w) { w["jobs"]["populate"]["steps"][4]["if"] = "${{ false }}" },
        "worker ignored initializer" => ->(w) { w["jobs"]["populate"]["steps"][4]["continue-on-error"] = true },
        "worker substituted initializer" => ->(w) { w["jobs"]["populate"]["steps"][4]["uses"] = "./.github/actions/dependency-cache-provider" },
        "worker duplicate initializer" => ->(w) { w["jobs"]["populate"]["steps"].insert(5, w["jobs"]["populate"]["steps"][4].dup) },
        "worker initializer authority input" => ->(w) { w["jobs"]["populate"]["steps"][4]["with"] = {"authorized" => "true"} },
        "worker enlarged initializer window" => ->(w) { w["jobs"]["populate"]["steps"][4]["timeout-minutes"] = 13 },
    }
    # Both real jobs must preserve every source predicate before repository Python.
    %w[initial-recipient-gate populate].each do |job|
        mutations["#{job} missing LF checkout"] = ->(w) { w["jobs"][job]["steps"][0].delete("env") }
        mutations["#{job} checkout config leaks into prestart"] = ->(w) {
            w["jobs"][job]["steps"][1]["env"]["GIT_CONFIG_COUNT"] = "1"
        }
        mutations["#{job} missing bound tree input"] = ->(w) {
            w["jobs"][job]["steps"][1]["env"].delete("P2PKIT_EXPECTED_TREE")
        }
        mutations["#{job} shell-interpolated owner input"] = ->(w) {
            w["jobs"][job]["steps"][1]["run"].sub!('$P2PKIT_EXPECTED_SHA', '${{ inputs.expected_sha }}')
        }
        mutations["#{job} failed status treated as empty clean output"] = ->(w) {
            w["jobs"][job]["steps"][1]["run"].sub!(
                "source_status=\"$(git status --porcelain=v1 --untracked-files=all)\"\ntest -z \"$source_status\"",
                'test -z "$(git status --porcelain=v1 --untracked-files=all)"')
        }
        InitialRecipientWorkflowPolicy::PRESTART.lines.each_with_index do |line, index|
            next unless line.lstrip.start_with?("test ", "[[ ", "git merge-base", "Windows)",
                                                "source_status=", "current_root=", "repository_root=", "workspace=")
            mutations["#{job} missing source/root predicate #{index}"] = ->(w) {
                w["jobs"][job]["steps"][1]["run"] = w["jobs"][job]["steps"][1]["run"].lines.reject.with_index { |_, n| n == index }.join
            }
        end
    end
    mutations.each do |name, mutate|
        candidate = Marshal.load(Marshal.dump(workflow))
        mutate.call(candidate)
        abort "FAIL: ineffective mutation #{name}" if Marshal.dump(candidate) == Marshal.dump(workflow)
        begin
            InitialRecipientWorkflowPolicy.check(candidate)
        rescue InitialRecipientWorkflowPolicy::Error
            checks += 1
            next
        end
        abort "FAIL: accepted #{name}"
    end

    # Exercise only the new queue participant/prerequisite cases here, against the
    # complete real workflow set. The common checker still owns the unchanged ten.
    workflows = HeavyJobQueuePolicy.read_workflows(File.expand_path("../../.github/workflows", __dir__))
    workflows["dependency-cache-bootstrap.yml"] = workflow
    original = Marshal.dump(workflows)
    HeavyJobQueuePolicy.check(workflows)
    queue_checks = 1
    queue_mutations = {
        "missing bootstrap workflow" => ->(w) { w.delete("dependency-cache-bootstrap.yml") },
        "extra bootstrap job" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["extra"] = {} },
        "workflow takes worker lease" => ->(w) { w["dependency-cache-bootstrap.yml"]["concurrency"] = HeavyJobQueuePolicy::QUEUE },
        "gate takes worker lease" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["initial-recipient-gate"]["concurrency"] = HeavyJobQueuePolicy::QUEUE },
        "gate depends on worker" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["initial-recipient-gate"]["needs"] = "populate" },
        "gate display alias" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["initial-recipient-gate"]["name"] = "Gate" },
        "gate drops protected environment" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["initial-recipient-gate"].delete("environment") },
        "gate drops source condition" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["initial-recipient-gate"].delete("if") },
        "worker skips dependency" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["populate"].delete("needs") },
        "worker lacks lease" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["populate"].delete("concurrency") },
        "worker cancels lease" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["populate"]["concurrency"]["cancel-in-progress"] = true },
        "worker runs despite gate failure" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["populate"]["if"] = "${{ always() }}" },
        "worker ignores failures" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["populate"]["continue-on-error"] = true },
        "worker display alias" => ->(w) { w["dependency-cache-bootstrap.yml"]["jobs"]["populate"]["name"] = "Populate" },
    }
    queue_mutations.each do |name, mutate|
        candidate = Marshal.load(original)
        mutate.call(candidate)
        abort "FAIL: ineffective queue mutation #{name}" if Marshal.dump(candidate) == original
        begin
            HeavyJobQueuePolicy.check(candidate)
        rescue HeavyJobQueuePolicy::Error
            queue_checks += 1
            next
        end
        abort "FAIL: accepted queue #{name}"
    end
    abort "FAIL: input workflow mutation" unless original == Marshal.dump(workflows)
    tail_checks = InitialRecipientWorkflowPolicy.custody_tail_controls(workflow)
    puts "PASS: #{checks} nonproductive Stage1 workflow controls, #{queue_checks} queue controls and #{tail_checks} custody-tail controls; no hosted/native execution"
end
