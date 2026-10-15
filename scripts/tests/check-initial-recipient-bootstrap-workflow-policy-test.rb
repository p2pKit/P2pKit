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
{"initial-recipient-gate" => 60, "populate" => 90}.each do |job, expected|
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
# Authored source controls for the separate public companion, not a new native
# upload allowance or proof that original U/A files were acquired on a runner.
def receipt_step(workflow, id)
    workflow.fetch("jobs").fetch("populate").fetch("steps").find { |step| step["id"] == id }
end
capture = receipt_step(WORKFLOW, "productive-receipts")
publication = receipt_step(WORKFLOW, "productive-receipts-upload")
raise "receipt companion interrupted B/U/A or its fixed post-A pair" unless worker_steps.last(5).map { |step| step["id"] } ==
    %w[productive-before productive-upload productive-after productive-receipts productive-receipts-upload]
checks += 1
expected_capture_env = {"P2PKIT_PYTHON" => '${{ steps.tools.outputs.python }}',
    "P2PKIT_EXPECTED_SHA" => '${{ inputs.expected_sha }}', "P2PKIT_EXPECTED_TREE" => '${{ inputs.expected_tree }}',
    "P2PKIT_INITIAL_SELECTION" => '${{ inputs.selection }}'}
{"UPLOAD" => "productive-upload", "AFTER" => "productive-after"}.each do |role, id|
    prefix = "P2PKIT_RECEIPT_#{role}_"
    expected_capture_env[prefix + "OUTCOME"] = "${{ steps.#{id}.outcome }}"
    {"ARTIFACT_ID" => "artifact-id", "SHA256" => "receipt-sha256", "DIRECTORY_SHA256" => "directory-identity-sha256",
     "FILE_METADATA_SHA256" => "file-metadata-sha256", "OWNER_CLOSE_SHA256" => "file-owner-close-sha256"}.each do |field, output|
        expected_capture_env[prefix + field] = "${{ steps.#{id}.outputs.#{output} }}"
    end
end
raise "capture does not bind exactly the original safe outputs without a credential" unless capture["env"] == expected_capture_env
raise "capture substituted a finite/old owner or accepts a path" unless capture["run"].end_with?(
    "exec \"$P2PKIT_PYTHON\" -I -B -S \"$script\" capture-public-originals --kind worker\n")
raise "capture does not require both original U/A outcomes" unless capture["if"] ==
    "${{ success() && steps.productive-upload.outcome == 'success' && steps.productive-after.outcome == 'success' }}"
checks += 3
raise "publication does not require original U/A and closed capture readiness" unless publication["if"] ==
    "${{ success() && steps.productive-upload.outcome == 'success' && steps.productive-after.outcome == 'success' && " \
    "steps.productive-receipts.outcome == 'success' && steps.productive-receipts.outputs.publicReceiptReady == 'true' && " \
    "steps.productive-receipts.outputs.publicReceiptManifestSha256 != '' }}"
receipt_directory = '${{ runner.temp }}/p2pkit-initial-recipient-${{ github.run_id }}-${{ github.run_attempt }}-worker-custody/productive-receipt-originals'
raise "companion is not the exact three public members at the native fixed path" unless publication.dig("with", "path") ==
    %w[upload-pending.json delivery-pending.json receipt-manifest.json].map { |name| "#{receipt_directory}/#{name}\n" }.join
raise "companion uploader/settings changed" unless publication["uses"] ==
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" && publication["with"].reject { |name, _| name == "path" } == {
        "name" => 'initial-recipient-productive-receipts-${{ github.run_id }}-${{ github.run_attempt }}-worker-${{ inputs.selection }}',
        "if-no-files-found" => "error", "retention-days" => 14, "compression-level" => 0, "overwrite" => false}
checks += 3
{"productive-receipts" => 1, "productive-receipts-upload" => 2}.each do |id, expected|
    step = receipt_step(WORKFLOW, id)
    raise "changed integer public-companion ceiling #{id}" unless step["timeout-minutes"].instance_of?(Integer) &&
        step["timeout-minutes"] == expected
    checks += 1
end
# Gate sealEnd = originalJobBasis+3525; this outer forty-five-minute kill
# ceiling does not renew that absolute fence or the gate3600 envelope.
gate_before = WORKFLOW.fetch("jobs").fetch("initial-recipient-gate").fetch("steps").select { |step| step["id"] == "initial-before" }
raise "changed integer gate before-upload ceiling" unless gate_before.size == 1 &&
    gate_before[0]["timeout-minutes"].instance_of?(Integer) && gate_before[0]["timeout-minutes"] == 45
checks += 1
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
    "worker ignores failed gate" => ->(w) { w["jobs"]["populate"]["if"] = "${{ always() }}" },
    "worker cycle" => ->(w) { w["jobs"]["populate"]["needs"] = "populate" },
    "worker alias" => ->(w) { w["jobs"]["populate"]["name"] = "friendly alias" },
    "worker matrix" => ->(w) { w["jobs"]["populate"]["strategy"] = {"matrix" => {"host" => ["ubuntu-latest"]}} },
    "wrong worker host" => ->(w) { w["jobs"]["populate"]["runs-on"] = "ubuntu-latest" },
    "changed worker cap" => ->(w) { w["jobs"]["populate"]["timeout-minutes"] = 21 },
    "gate environment removed" => ->(w) { w["jobs"]["initial-recipient-gate"].delete("environment") },
    "gate branch substitution" => ->(w) { w["jobs"]["initial-recipient-gate"]["if"] = "${{ success() }}" },
    "gate takes heavy lease" => ->(w) { w["jobs"]["initial-recipient-gate"]["concurrency"] = copy(HeavyJobQueuePolicy::QUEUE) },
    "gate replaces original acquisition with success" => ->(w) {
        w["jobs"]["initial-recipient-gate"]["steps"].find { |step| step["id"] == "initial-originals" }["run"] = "echo success\n"
    },
}
[6, 9, 10, 11, 19, 20, 21, 29, 30, 31, 59, 61, "10", 10.0, "20", 20.0, "30", 30.0, "60", 60.0, true, nil].each do |cap|
    mutations["gate JOB cap #{cap.inspect}"] = ->(w) { w["jobs"]["initial-recipient-gate"]["timeout-minutes"] = cap }
end
[20, 89, 91, "90", 90.0, true, nil].each do |cap|
    mutations["worker JOB cap #{cap.inspect}"] = ->(w) { w["jobs"]["populate"]["timeout-minutes"] = cap }
end
[20, 55, 57, "56", 56.0, true, nil].each do |cap|
    mutations["produce execution ceiling #{cap.inspect}"] = ->(w) {
        w["jobs"]["populate"]["steps"].find { |step| step["id"] == "produce" }["timeout-minutes"] = cap
    }
end
[1, 5, 6, 7, 14, 15, 16, 24, 25, 26, 44, 46, "6", 6.0, "15", 15.0, "25", 25.0, "45", 45.0, true, nil].each do |cap|
    mutations["gate before-upload outer ceiling #{cap.inspect}"] = ->(w) {
        w["jobs"]["initial-recipient-gate"]["steps"].find { |step| step["id"] == "initial-before" }["timeout-minutes"] = cap
    }
end
mutations["gate before-upload missing outer ceiling"] = ->(w) {
    w["jobs"]["initial-recipient-gate"]["steps"].find { |step| step["id"] == "initial-before" }.delete("timeout-minutes")
}
{
    "capture before original A return" => ->(w) {
        steps = w["jobs"]["populate"]["steps"]; steps[-3], steps[-2] = steps[-2], steps[-3]
    },
    "publication before capture" => ->(w) {
        steps = w["jobs"]["populate"]["steps"]; steps[-2], steps[-1] = steps[-1], steps[-2]
    },
    "extra post-A writer" => ->(w) { w["jobs"]["populate"]["steps"].insert(-2, {"name" => "unreviewed writer", "run" => "true"}) },
    "capture reuses old A owner" => ->(w) {
        receipt_step(w, "productive-receipts")["run"].sub!("capture-public-originals --kind worker", "after --kind worker")
    },
    "capture takes a source path" => ->(w) {
        receipt_step(w, "productive-receipts")["run"].sub!("capture-public-originals --kind worker", "capture-public-originals --kind worker --path /arbitrary")
    },
    "capture ignores original U success" => ->(w) {
        receipt_step(w, "productive-receipts")["if"].sub!("steps.productive-upload.outcome == 'success' && ", "")
    },
    "capture passes reconstructed U bytes" => ->(w) {
        receipt_step(w, "productive-receipts")["env"]["P2PKIT_RECEIPT_UPLOAD_SHA256"] = '${{ steps.productive-upload.outputs.receipt-base64 }}'
    },
    "capture trusts caller path" => ->(w) { receipt_step(w, "productive-receipts")["env"]["P2PKIT_RECEIPT_DIRECTORY"] = "/arbitrary" },
    "publication ignores failed capture" => ->(w) {
        receipt_step(w, "productive-receipts-upload")["if"].sub!(" && steps.productive-receipts.outcome == 'success'", "")
    },
    "publication ignores original A success" => ->(w) {
        receipt_step(w, "productive-receipts-upload")["if"].sub!(" && steps.productive-after.outcome == 'success'", "")
    },
    "publication accepts ready presence only" => ->(w) {
        receipt_step(w, "productive-receipts-upload")["if"].sub!("publicReceiptReady == 'true'", "publicReceiptReady != ''")
    },
    "publication ignores capture manifest hash" => ->(w) {
        receipt_step(w, "productive-receipts-upload")["if"].sub!(" && steps.productive-receipts.outputs.publicReceiptManifestSha256 != ''", "")
    },
    "publication success despite no capture" => ->(w) { receipt_step(w, "productive-receipts-upload")["if"] = '${{ always() }}' },
    "floated companion uploader" => ->(w) { receipt_step(w, "productive-receipts-upload")["uses"] = "actions/upload-artifact@main" },
    "companion overwrites original evidence" => ->(w) { receipt_step(w, "productive-receipts-upload")["with"]["overwrite"] = true },
    "missing companion passes" => ->(w) { receipt_step(w, "productive-receipts-upload")["with"]["if-no-files-found"] = "ignore" },
    "companion selects complete private root" => ->(w) { receipt_step(w, "productive-receipts-upload")["with"]["path"] = receipt_directory + "/\n" },
    "companion selects wildcard" => ->(w) { receipt_step(w, "productive-receipts-upload")["with"]["path"] = receipt_directory + "/*\n" },
    "companion drops original A" => ->(w) {
        step = receipt_step(w, "productive-receipts-upload"); step["with"]["path"] = step["with"]["path"].lines.reject { |line| line.include?("delivery-pending.json") }.join
    },
    "companion adds private original" => ->(w) { receipt_step(w, "productive-receipts-upload")["with"]["path"] += receipt_directory + "/private-original.json\n" },
    "companion trusts output path" => ->(w) { receipt_step(w, "productive-receipts-upload")["with"]["path"] = '${{ steps.productive-receipts.outputs.path }}' },
    "companion impersonates primary packet" => ->(w) {
        receipt_step(w, "productive-receipts-upload")["with"]["name"].sub!("productive-receipts-", "productive-custody-")
    },
    "companion omits selection identity" => ->(w) {
        receipt_step(w, "productive-receipts-upload")["with"]["name"].sub!('-${{ inputs.selection }}', "")
    },
}.each { |name, mutate| mutations["public companion #{name}"] = mutate }
%w[P2PKIT_ACTIONS_READ_TOKEN GITHUB_TOKEN GH_TOKEN ACTIONS_RUNTIME_TOKEN ACTIONS_CACHE_URL ACTIONS_RESULTS_URL].each do |name|
    mutations["public capture credential #{name}"] = ->(w) { receipt_step(w, "productive-receipts")["env"][name] = "SYNTHETIC_NOT_A_CREDENTIAL" }
end
{"productive-receipts" => 1, "productive-receipts-upload" => 2}.each do |id, expected|
    [0, expected + 1, expected.to_s, expected.to_f, true, nil].each do |cap|
        mutations["#{id} exact integer ceiling #{cap.inspect}"] = ->(w) { receipt_step(w, id)["timeout-minutes"] = cap }
    end
    mutations["#{id} ignores failure"] = ->(w) { receipt_step(w, id)["continue-on-error"] = true }
end
{"retention-days" => [0, 15, "14", 14.0, true, nil], "compression-level" => [1, "0", 0.0, false, nil]}.each do |field, values|
    values.each do |value|
        mutations["companion exact integer #{field} #{value.inspect}"] = ->(w) { receipt_step(w, "productive-receipts-upload")["with"][field] = value }
    end
end
%w[initial-recipient-gate populate].each do |job|
    mutations["#{job} missing exact-source checkout"] = ->(w) { w["jobs"][job]["steps"].shift }
    mutations["#{job} preflight before checkout"] = ->(w) { steps = w["jobs"][job]["steps"]; steps[0], steps[1] = steps[1], steps[0] }
    mutations["#{job} missing source preflight"] = ->(w) { w["jobs"][job]["steps"].delete_at(1) }
    mutations["#{job} preflight after tool acquisition"] = ->(w) { steps = w["jobs"][job]["steps"]; steps[1], steps[2] = steps[2], steps[1] }
    mutations["#{job} successful no-op preflight"] = ->(w) { w["jobs"][job]["steps"][1]["run"] = "echo success\n" }
    {"if" => false, "continue-on-error" => true, "env" => {"BYPASS" => "1"}}.each do |key, value|
        mutations["#{job} conditional source preflight #{key}"] = ->(w) { w["jobs"][job]["steps"][1][key] = value }
    end
    mutations["#{job} persisted checkout credential"] = ->(w) { w["jobs"][job]["steps"][0]["with"]["persist-credentials"] = true }
    mutations["#{job} floated checkout"] = ->(w) { w["jobs"][job]["steps"][0]["with"]["ref"] = "main" }
    mutations["#{job} source fetch tags"] = ->(w) { w["jobs"][job]["steps"][1]["run"].sub!("--no-tags", "--tags") }
    mutations["#{job} old campaign"] = ->(w) { w["jobs"][job]["steps"][1]["run"].gsub!(P::REF, "refs/heads/work/nonphysical-integration-20260915-022112") }
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
    # Mutate only these owned copies, even when the original checkout is read-only.
    FileUtils.chmod_R("u+w", File.join(directory, ".github/actions"))
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
