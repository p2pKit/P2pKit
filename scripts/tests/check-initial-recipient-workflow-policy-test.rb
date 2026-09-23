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
        need(steps.is_a?(Array) && steps.size == 3, "only checkout/history/prestart/original acquisition permitted")
        checkout, prestart, acquire = steps
        source_prefix(checkout, prestart)
        keys(acquire, %w[name id timeout-minutes shell env run], "original acquisition scope changed")
        need(acquire["id"] == "initial-originals" && acquire["shell"] == "bash" && acquire["run"] == ACQUIRE,
             "existing isolated nonproductive CLI required")
        need(acquire["env"] == {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"}, "read token must remain step scoped")
        timeout(acquire["timeout-minutes"], 3)
        worker = jobs["populate"]
        keys(worker, %w[needs permissions runs-on timeout-minutes concurrency steps], "exact nonproductive worker scope required")
        need(worker["needs"] == "initial-recipient-gate" &&
             worker["permissions"] == {"contents" => "read", "actions" => "read"} && worker["runs-on"] == SELECTOR,
             "actual dependent native selector required; no fallback")
        timeout(worker["timeout-minutes"], 20)
        need(worker["concurrency"] == HeavyJobQueuePolicy::QUEUE, "worker must join the noncancelling heavy queue")
        steps = worker["steps"]
        need(steps.is_a?(Array) && steps.size == 6, "exact nonproductive prefix and held tail required")
        checkout, prestart, java, jdk, initializer, hold = steps
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
        need(hold == {"name" => "Hold the unqualified productive bootstrap", "timeout-minutes" => 1,
                      "shell" => "bash", "run" => HOLD} && hold["timeout-minutes"].instance_of?(Integer),
             "productive HOLD must remain unconditional and blocking after the prefix")
    end
end

path = ARGV.fetch(0, File.expand_path("../../.github/workflows/dependency-cache-bootstrap.yml", __dir__))
workflow = HeavyJobQueuePolicy.parse(File.read(path), path)
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
    abort "FAIL: ineffective mutation #{name}" if candidate == workflow
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
    abort "FAIL: ineffective queue mutation #{name}" if candidate == workflows
    begin
        HeavyJobQueuePolicy.check(candidate)
    rescue HeavyJobQueuePolicy::Error
        queue_checks += 1
        next
    end
    abort "FAIL: accepted queue #{name}"
end
abort "FAIL: input workflow mutation" unless original == Marshal.dump(workflows)
puts "PASS: #{checks} nonproductive Stage1 workflow controls and #{queue_checks} new queue controls; no hosted/native execution"
