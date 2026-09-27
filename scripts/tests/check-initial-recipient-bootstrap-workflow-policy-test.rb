#!/usr/bin/env ruby
# Deterministic source/temporary-file controls only, not Actions qualification.
require "tmpdir"
require "fileutils"
require "open3"
require "rbconfig"
require_relative "../check-initial-recipient-bootstrap-workflow-policy"

ROOT = File.expand_path("../..", __dir__)
P = InitialRecipientBootstrapPolicy
TEXT = File.read(File.join(ROOT, ".github/workflows", P::FILE))
WORKFLOW = P.parse(TEXT, P::FILE)

def copy(value); Marshal.load(Marshal.dump(value)); end
def refuse(name)
    yield
    raise "unsafe bootstrap policy accepted: #{name}"
rescue P::Error
    1
end

P.check(WORKFLOW)
P.check_sources(ROOT)
checks = 2
# JOB90/produce56 are outer kill ceilings, not native fit or activation claims.
worker_steps = WORKFLOW.fetch("jobs").fetch("populate").fetch("steps")
{"initial-recipient-gate" => 6, "populate" => 90}.each do |job, expected|
    actual = WORKFLOW.fetch("jobs").fetch(job).fetch("timeout-minutes")
    raise "wrong integer JOB ceiling #{job}" unless actual.instance_of?(Integer) && actual == expected
    checks += 1
end
{"canonical-initialization" => 12, "produce" => 56}.each do |id, expected|
    matches = worker_steps.select { |step| step["id"] == id }
    raise "changed integer Step ceiling #{id}" unless matches.size == 1 &&
        matches[0]["timeout-minutes"].instance_of?(Integer) && matches[0]["timeout-minutes"] == expected
    checks += 1
end
mutations = {
    "extra event" => ->(w) { w.fetch(true)["push"] = {} },
    "optional source" => ->(w) { w[true]["workflow_dispatch"]["inputs"]["expected_sha"]["required"] = false },
    "extra selector" => ->(w) { w[true]["workflow_dispatch"]["inputs"]["selection"]["options"] << "latest-main" },
    "activation input" => ->(w) { w[true]["workflow_dispatch"]["inputs"]["activate"] = {"type" => "boolean"} },
    "workflow heavy deadlock" => ->(w) { w["concurrency"] = copy(HeavyJobQueuePolicy::QUEUE) },
    "workflow cancellation" => ->(w) { w["concurrency"]["cancel-in-progress"] = true },
    "workflow token" => ->(w) { w["env"] = {"P2PKIT_ACTIONS_READ_TOKEN" => "${{ github.token }}"} },
    "write permission" => ->(w) { w["permissions"] = {"contents" => "write"} },
    "extra job" => ->(w) { w["jobs"]["unreviewed"] = {} },
    "missing gate" => ->(w) { w["jobs"].delete("initial-recipient-gate") },
    "worker missing needs" => ->(w) { w["jobs"]["populate"].delete("needs") },
    "worker cycle" => ->(w) { w["jobs"]["populate"]["needs"] = "populate" },
    "worker alias" => ->(w) { w["jobs"]["populate"]["name"] = "friendly alias" },
    "worker matrix" => ->(w) { w["jobs"]["populate"]["strategy"] = {"matrix" => {"host" => ["ubuntu-latest"]}} },
    "wrong worker host" => ->(w) { w["jobs"]["populate"]["runs-on"] = "ubuntu-latest" },
    "changed worker cap" => ->(w) { w["jobs"]["populate"]["timeout-minutes"] = 21 },
    "gate environment removed" => ->(w) { w["jobs"]["initial-recipient-gate"].delete("environment") },
    "gate branch substitution" => ->(w) { w["jobs"]["initial-recipient-gate"]["if"] = "${{ success() }}" },
    "gate takes heavy lease" => ->(w) { w["jobs"]["initial-recipient-gate"]["concurrency"] = copy(HeavyJobQueuePolicy::QUEUE) },
}
[20, 89, 91, "90", 90.0, true, nil].each do |cap|
    mutations["worker JOB cap #{cap.inspect}"] = ->(w) { w["jobs"]["populate"]["timeout-minutes"] = cap }
end
[20, 55, 57, "56", 56.0, true, nil].each do |cap|
    mutations["produce execution ceiling #{cap.inspect}"] = ->(w) {
        w["jobs"]["populate"]["steps"].find { |step| step["id"] == "produce" }["timeout-minutes"] = cap
    }
end
%w[initial-recipient-gate populate].each do |job|
    mutations["#{job} no first HOLD"] = ->(w) { w["jobs"][job]["steps"].shift }
    mutations["#{job} moved HOLD"] = ->(w) { steps = w["jobs"][job]["steps"]; steps[0], steps[1] = steps[1], steps[0] }
    mutations["#{job} success HOLD"] = ->(w) { w["jobs"][job]["steps"][0]["run"] = "echo success\n" }
    {"if" => false, "continue-on-error" => true, "env" => {"BYPASS" => "1"}}.each do |key, value|
        mutations["#{job} conditional HOLD #{key}"] = ->(w) { w["jobs"][job]["steps"][0][key] = value }
    end
    mutations["#{job} persisted checkout credential"] = ->(w) { w["jobs"][job]["steps"][1]["with"]["persist-credentials"] = true }
    mutations["#{job} floated checkout"] = ->(w) { w["jobs"][job]["steps"][1]["with"]["ref"] = "main" }
    mutations["#{job} source fetch tags"] = ->(w) { w["jobs"][job]["steps"][2]["run"].sub!("--no-tags", "--tags") }
    mutations["#{job} old campaign"] = ->(w) { w["jobs"][job]["steps"][2]["run"].gsub!(P::REF, "refs/heads/work/nonphysical-integration-20260915-022112") }
    WORKFLOW["jobs"][job]["steps"].each_with_index do |step, index|
        if step.key?("timeout-minutes")
            mutations["#{job}#{index} JOB90 does not extend Step cap"] = ->(w) {
                w["jobs"][job]["steps"][index]["timeout-minutes"] += 1
            }
        end
        next unless step["id"]
        mutations["#{job}#{index} wrong Step name"] = ->(w) { w["jobs"][job]["steps"][index]["name"] += " altered" }
        mutations["#{job}#{index} omitted Step"] = ->(w) { w["jobs"][job]["steps"].delete_at(index) }
        next unless step["env"]
        step["env"].each_key do |field|
            mutations["#{job}#{index} missing #{field}"] = ->(w) { w["jobs"][job]["steps"][index]["env"].delete(field) }
            next if field == "P2PKIT_ACTIONS_READ_TOKEN" || field == "P2PKIT_PYTHON"
            mutations["#{job}#{index} fabricated #{field}"] = ->(w) { w["jobs"][job]["steps"][index]["env"][field] = field.end_with?("OUTCOME") ? "success" : "a" * 64 }
        end
        if step["uses"]
            mutations["#{job}#{index} Node API token"] = ->(w) { w["jobs"][job]["steps"][index]["env"]["P2PKIT_ACTIONS_READ_TOKEN"] = "${{ github.token }}" }
            mutations["#{job}#{index} direct raw upload"] = ->(w) { w["jobs"][job]["steps"][index]["uses"] = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" }
            %w[artifact-id receipt-base64].each do |input|
                mutations["#{job}#{index} extra after input #{input}"] = ->(w) { w["jobs"][job]["steps"][index]["with"][input] = "not-an-authority" }
            end
        end
    end
end
mutations.each do |name, mutate|
    changed = copy(WORKFLOW)
    mutate.call(changed)
    raise "ineffective mutation #{name}" if Marshal.dump(changed) == Marshal.dump(WORKFLOW)
    checks += refuse(name) { P.check(changed) }
end
{
    "duplicate" => TEXT + "\njobs: {}\n", "merge" => "jobs:\n  a:\n    <<: {x: 1}\n",
    "multiple" => TEXT + "\n---\njobs: {}\n", "alias" => "a: &a {}\nb: *a\n", "malformed" => "jobs: [\n",
}.each { |name, text| checks += refuse(name) { P.parse(text, name) } }

workflow_test = File.read(File.join(ROOT, "scripts/tests/release-workflow-test.sh"))
[
    'ruby "$ROOT/scripts/tests/check-initial-recipient-bootstrap-workflow-policy-test.rb"',
    'python3 -I -B -S "$ROOT/scripts/tests/initial-recipient-runner-tools-test.py" -v',
    'python3 -I -B -S "$ROOT/scripts/tests/hosted-initial-recipient-productive-step-output-test.py" -v',
].each do |invocation|
    raise "maintained entrypoint missing exact #{invocation}" unless workflow_test.lines.map(&:strip).count(invocation) == 1
    checks += 1
end
functions = %w[is_local_workflow_reference is_local_action_reference].map do |name|
    body = workflow_test[/^#{name}\(\) \{\n.*?^\}/m]
    raise "missing closed local predicate #{name}" unless body
    body
end.join("\n")

Dir.mktmpdir("p2pkit-bootstrap-policy-") do |directory|
    FileUtils.mkdir_p(File.join(directory, ".github/workflows"))
    FileUtils.mkdir_p(File.join(directory, ".github/actions"))
    %w[initial-recipient-initialize initial-recipient-cache-provider initial-recipient-upload initial-recipient-productive-upload].each do |name|
        FileUtils.cp_r(File.join(ROOT, ".github/actions", name), File.join(directory, ".github/actions", name))
    end
    P.check_sources(directory)
    checks += 1
    P::ACTIONS.each_key do |name|
        path = File.join(directory, ".github/actions", name, "action.yml")
        original = File.read(path)
        action = P.parse(original, name)
        [->(a) { a["runs"]["using"] = "node20" }, ->(a) { a["inputs"]["artifact-id"] = {"required" => true} },
         ->(a) { a["inputs"].values.first["default"] = "upload" }, ->(a) { a["outputs"].delete(a["outputs"].keys.first) }].each do |mutate|
            changed = copy(action); mutate.call(changed); File.write(path, changed.to_yaml)
            checks += refuse("#{name} changed interface") { P.check_sources(directory) }
        end
        File.write(path, original)
        index = File.join(File.dirname(path), "index.cjs")
        original_index = File.read(index)
        File.write(index, original_index + "process.env.GITHUB_TOKEN = 'not-a-credential';\n")
        checks += refuse("#{name} arbitrary wrapper code") { P.check_sources(directory) }
        File.write(index, original_index)
    end
    marker = File.join(directory, ".github/workflows/source.yml")
    File.write(marker, "jobs: {}\n")
    [["init", "-q"], ["add", ".github"]].each do |arguments|
        _stdout, stderr, status = Open3.capture3("git", "-C", directory, *arguments)
        raise "fixture git failed: #{stderr}" unless status.success?
    end
    probe = lambda do |predicate, use, expected|
        _stdout, stderr, status = Open3.capture3("bash", "-c", functions + "\n#{predicate} \"$1\" \"$2\"\n", "predicate", directory, use)
        raise "local predicate mismatch #{use}: #{stderr}" unless status.success? == expected
        checks += 1
    end
    %w[initial-recipient-initialize initial-recipient-cache-provider initial-recipient-upload initial-recipient-productive-upload].each do |name|
        probe.call("is_local_action_reference", "./.github/actions/#{name}", true)
    end
    probe.call("is_local_workflow_reference", "./.github/workflows/source.yml", true)
    ["./.github/actions/unknown", "./.github/actions/../initial-recipient-upload", "/.github/actions/initial-recipient-upload",
     "./.github/actions/initial-recipient-upload/", "./.github/actions/initial-recipient-upload/action.yml"].each do |use|
        probe.call("is_local_action_reference", use, false)
    end
    index = File.join(directory, ".github/actions/initial-recipient-productive-upload/index.cjs")
    original = File.read(index)
    File.unlink(index)
    probe.call("is_local_action_reference", "./.github/actions/initial-recipient-productive-upload", false)
    File.symlink(marker, index)
    probe.call("is_local_action_reference", "./.github/actions/initial-recipient-productive-upload", false)
    File.unlink(index)
    File.write(index, original)
    _stdout, stderr, status = Open3.capture3("git", "-C", directory, "rm", "--cached", "--", ".github/actions/initial-recipient-productive-upload/index.cjs")
    raise "fixture untrack failed: #{stderr}" unless status.success?
    probe.call("is_local_action_reference", "./.github/actions/initial-recipient-productive-upload", false)
end
raise "controls changed workflow fixture" unless P.parse(TEXT, P::FILE) == WORKFLOW
puts "RESULT: PASS — #{checks} authored bootstrap wiring/interface/local-reference controls; not hosted qualification"
