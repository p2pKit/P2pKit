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
    FETCH = "git fetch --no-tags --unshallow origin " \
        "refs/heads/main:refs/remotes/origin/main " \
        "refs/heads/work/nonphysical-integration-20260915-022112:refs/remotes/origin/work/nonphysical-integration-20260915-022112"
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
        need(value.instance_of?(Integer) && value == minutes, "original workflow timeout changed")
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
        need(steps.is_a?(Array) && steps.size == 3, "only checkout/history/original acquisition permitted")
        checkout, fetch, acquire = steps
        keys(checkout, %w[name timeout-minutes uses with], "checkout cannot ignore failure or gain inputs")
        need(checkout["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "pinned checkout required")
        need(checkout["with"] == {"ref" => "${{ github.sha }}", "fetch-depth" => 1, "fetch-tags" => false,
                                  "persist-credentials" => false} && checkout["with"]["fetch-depth"].instance_of?(Integer),
             "actual source, shallow no-tag checkout and no persisted credentials required")
        timeout(checkout["timeout-minutes"], 2)
        keys(fetch, %w[name timeout-minutes shell env run], "source history fetch scope changed")
        need(fetch["shell"] == "bash" && fetch["env"] == {"GIT_TERMINAL_PROMPT" => "0"} && fetch["run"] == FETCH,
             "fixed public no-tags full-history fetch required")
        timeout(fetch["timeout-minutes"], 1)
        keys(acquire, %w[name id timeout-minutes shell env run], "original acquisition scope changed")
        need(acquire["id"] == "initial-originals" && acquire["shell"] == "bash" && acquire["run"] == ACQUIRE,
             "existing isolated nonproductive CLI required")
        need(acquire["env"] == {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"}, "read token must remain step scoped")
        timeout(acquire["timeout-minutes"], 3)
        worker = jobs["populate"]
        keys(worker, %w[needs permissions runs-on timeout-minutes steps], "held worker must not gain authority/setup")
        need(worker["needs"] == "initial-recipient-gate" && worker["permissions"] == {} && worker["runs-on"] == SELECTOR,
             "actual dependent native selector required; no fallback")
        timeout(worker["timeout-minutes"], 1)
        need(worker["steps"] == [{"name" => "Hold the unqualified productive bootstrap", "shell" => "bash", "run" => HOLD}],
             "productive HOLD must be unconditional, blocking and before every side effect")
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
    "worker secret permission" => ->(w) { w["jobs"]["populate"]["permissions"] = {"contents" => "read"} },
    "worker automatic environment" => ->(w) { w["jobs"]["populate"]["environment"] = "initial-recipient-execution" },
    "ignored worker refusal" => ->(w) { w["jobs"]["populate"]["continue-on-error"] = true },
    "successful refusal" => ->(w) { w["jobs"]["populate"]["steps"][0]["run"].sub!("exit 125", "exit 0") },
    "conditional refusal" => ->(w) { w["jobs"]["populate"]["steps"][0]["if"] = "${{ false }}" },
    "ignored refusal step" => ->(w) { w["jobs"]["populate"]["steps"][0]["continue-on-error"] = true },
    "provider before refusal" => ->(w) { w["jobs"]["populate"]["steps"].unshift({"uses" => "./.github/actions/dependency-cache-provider"}) },
    "unconditional Gradle cleanup" => ->(w) { w["jobs"]["populate"]["steps"] << {"if" => "${{ always() }}", "run" => "./gradlew --stop"} },
}
mutations.each do |name, mutate|
    candidate = Marshal.load(Marshal.dump(workflow))
    mutate.call(candidate)
    begin
        InitialRecipientWorkflowPolicy.check(candidate)
    rescue InitialRecipientWorkflowPolicy::Error
        checks += 1
        next
    end
    abort "FAIL: accepted #{name}"
end
puts "PASS: #{checks} nonproductive Stage1 workflow controls; no hosted/native execution"
