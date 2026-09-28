#!/usr/bin/env ruby
# Structural/source controls only; no scheduling, provider or build execution.
require "yaml"
require_relative "../check-heavy-job-queue-policy"

ROOT = File.expand_path("../..", __dir__)
PATH = File.join(ROOT, ".github/workflows/dependency-update-candidate.yml")
WORKFLOW = HeavyJobQueuePolicy.parse(File.read(PATH), PATH)
GENERATOR = "python3 -I -B -S controller/scripts/run-hosted-dependency-update.py "
PIN_INPUTS = %w[controller_sha controller_tree candidate_sha candidate_tree dependency_base_sha].freeze
GENERATOR_CONDITION = "${{ inputs.operation == 'generate' }}"
FAILED = "failure() && !cancelled() && inputs.operation == 'generate' && steps.generate.outcome == 'failure' && steps.generate.outputs.failedProductSha256 != '' && steps.generate.outputs.successSha256 == '' && steps.generate.outputs.diagnosticSha256 == ''"
FAILED_CONDITIONS = ["${{ #{FAILED} }}", "${{ #{FAILED} && steps.failed_guard.outcome == 'success' }}",
    "${{ #{FAILED} && steps.failed_guard.outcome == 'success' && steps.failed_encrypted.outcome == 'success' }}"].freeze
DIAGNOSTIC = "always() && !cancelled() && inputs.operation == 'diagnose-jmdns' && (steps.generate.outcome == 'success' || steps.generate.outcome == 'failure') && steps.generate.outputs.diagnosticSha256 != '' && steps.generate.outputs.successSha256 == '' && steps.generate.outputs.failedProductSha256 == ''"
DIAGNOSTIC_CONDITIONS = ["${{ #{DIAGNOSTIC} }}", "${{ #{DIAGNOSTIC} && steps.diagnostic_guard.outcome == 'success' }}",
    "${{ #{DIAGNOSTIC} && steps.diagnostic_guard.outcome == 'success' && steps.diagnostic_encrypted.outcome == 'success' }}"].freeze
RETURN_ENV = {
    "P2PKIT_DEPENDENCY_GENERATOR_OUTCOME" => "${{ steps.generate.outcome }}",
    "P2PKIT_DEPENDENCY_SUCCESS_SHA256" => "${{ steps.generate.outputs.successSha256 }}",
    "P2PKIT_DEPENDENCY_FAILED_SHA256" => "${{ steps.generate.outputs.failedProductSha256 }}",
    "P2PKIT_DEPENDENCY_DIAGNOSTIC_SHA256" => "${{ steps.generate.outputs.diagnosticSha256 }}",
}.freeze
ALLOCATION_SOURCE = <<~'PYTHON'
  import json
  import os
  from pathlib import Path
  import re
  import tempfile
  import time

  os.umask(0o077)
  assert os.environ['RUNNER_ENVIRONMENT'] == 'github-hosted'
  request = json.loads(os.environ['P2PKIT_MAINTENANCE_REQUEST'])
  pins = {'controller_sha', 'controller_tree', 'candidate_sha', 'candidate_tree', 'dependency_base_sha'}
  assert set(request) == pins | {'operation'}
  assert type(request['operation']) is str and request['operation'] in ('generate', 'diagnose-jmdns')
  assert all(type(request[name]) is str and re.fullmatch(r'[0-9a-f]{40}', request[name]) for name in pins)
  assert request['controller_sha'] == os.environ['GITHUB_SHA'] == os.environ['GITHUB_WORKFLOW_SHA']
  temporary = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
  parent = Path(tempfile.mkdtemp(prefix='p2pkit-dependency-update-', dir=temporary))
  record = {'schema': 1, 'source': os.environ['GITHUB_SHA'],
            'runId': os.environ['GITHUB_RUN_ID'], 'runAttempt': os.environ['GITHUB_RUN_ATTEMPT'],
            'startedMonotonicNs': time.monotonic_ns(), 'startedEpochNs': time.time_ns()}
  with (parent / 'allocation.json').open('x', encoding='ascii') as stream:
      json.dump(record, stream, sort_keys=True, separators=(',', ':'))
      stream.write('\n')
      stream.flush()
      os.fsync(stream.fileno())
  with Path(os.environ['GITHUB_ENV']).open('a', encoding='utf-8') as stream:
      stream.write('P2PKIT_DEPENDENCY_OPERATION=' + str(parent) + '\n')
PYTHON
SOURCE_FETCH = <<~BASH
  set -euo pipefail
  # checkout's depth=0 includes an explicit tags refspec even when
  # fetch-tags=false. Exact-SHA depth=1 followed by this fetch does not.
  for source in controller candidate; do
    test "$(git -C "$source" rev-parse --is-shallow-repository)" = true
    test -z "$(git -C "$source" for-each-ref --format='%(refname)' refs/tags)"
    git -C "$source" fetch --no-tags --no-recurse-submodules --unshallow origin '+refs/heads/*:refs/remotes/origin/*'
    test "$(git -C "$source" rev-parse --is-shallow-repository)" = false
    test -z "$(git -C "$source" for-each-ref --format='%(refname)' refs/tags)"
  done
BASH

def check(workflow)
    require_policy = ->(condition) { raise "unsafe maintenance workflow" unless condition }
    events = workflow.fetch("on", workflow[true])
    inputs = events["workflow_dispatch"]["inputs"]
    require_policy.call(workflow["permissions"] == {"contents" => "read"} && !workflow.key?("concurrency"))
    require_policy.call(events.keys.sort == %w[push workflow_dispatch] &&
        events["push"] == {"branches" => ["work/release-foundation-*"], "paths" => [".github/workflows/dependency-update-candidate.yml"]})
    require_policy.call(inputs.keys.sort == (PIN_INPUTS + ["operation"]).sort && PIN_INPUTS.all? { |name|
        input = inputs[name]
        input.keys.sort == %w[description required type] && input["required"] == true && input["type"] == "string" })
    operation = inputs["operation"]
    require_policy.call(operation.keys.sort == %w[description options required type] &&
        operation["required"] == true && operation["type"] == "choice" && operation["options"] == %w[generate diagnose-jmdns])
    require_policy.call(workflow["jobs"].keys == ["generate"])
    job = workflow["jobs"]["generate"]
    require_policy.call(job["if"] == HeavyJobQueuePolicy::CONDITIONS[["dependency-update-candidate.yml", "generate"]] &&
        job["concurrency"] == HeavyJobQueuePolicy::QUEUE && job["runs-on"] == "macos-26" && job["timeout-minutes"] == 210 &&
        !job.key?("environment") && !job.key?("continue-on-error") && !job.key?("permissions"))
    steps = job["steps"]
    require_policy.call(steps.size == 18 && steps.all? { |step| !step.key?("continue-on-error") &&
        step["timeout-minutes"].is_a?(Integer) && step["timeout-minutes"] > 0 } &&
        steps[0, 8].all? { |step| !step.key?("if") } &&
        steps[8, 4].all? { |step| step["if"] == GENERATOR_CONDITION } &&
        steps[12, 3].map { |step| step["if"] } == FAILED_CONDITIONS &&
        steps[15, 3].map { |step| step["if"] } == DIAGNOSTIC_CONDITIONS)
    # Generator-success, generator-failure and diagnostic tails are mutually
    # exclusive. Their largest complete paths remain208/198/198 minutes.
    common = steps[0, 8].sum { |step| step["timeout-minutes"] }
    require_policy.call(common + [steps[8, 4], steps[12, 3], steps[15, 3]].map { |path|
        path.sum { |step| step["timeout-minutes"] } }.max <= 210)
    require_policy.call(steps[0]["env"] == {"P2PKIT_MAINTENANCE_REQUEST" => "${{ toJSON(inputs) }}"} &&
        steps[0]["shell"] == "python3 {0}" && steps[0]["run"] == ALLOCATION_SOURCE)
    checkouts = steps.select { |step| step.fetch("uses", "").start_with?("actions/checkout@") }
    require_policy.call(checkouts.size == 2 && checkouts.map { |step| step["with"]["path"] } == %w[controller candidate] &&
        checkouts.all? { |step| step["with"]["fetch-depth"] == 1 && step["with"]["fetch-tags"] == false &&
            step["with"]["persist-credentials"] == false &&
            step["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" } &&
        checkouts[0]["with"]["ref"] == "${{ github.sha }}" && checkouts[1]["with"]["ref"] == "${{ inputs.candidate_sha }}")
    require_policy.call(steps[3]["run"] == SOURCE_FETCH && steps[3]["env"] == {"GIT_TERMINAL_PROMPT" => "0"} &&
        steps[3]["timeout-minutes"] == 3)
    commands = steps.select { |step| step.fetch("run", "").start_with?(GENERATOR) }
    require_policy.call(commands.map { |step| step["run"] } ==
        %w[generate before-upload after-upload before-failed-upload after-failed-upload
           before-diagnostic-upload after-diagnostic-upload].map { |name| GENERATOR + name })
    require_policy.call(commands[0]["env"] == {"P2PKIT_MAINTENANCE_REQUEST" => "${{ toJSON(inputs) }}"} &&
        commands[0]["id"] == "generate" && commands[0]["timeout-minutes"] == 165)
    require_policy.call(commands[1..].all? { |step| step["timeout-minutes"] == 1 })
    RETURN_ENV.each do |key, value|
        require_policy.call(commands[1..].all? { |step| step["env"][key] == value })
    end
    require_policy.call(commands[3]["id"] == "failed_guard" && commands[5]["id"] == "diagnostic_guard" &&
        [commands[1], commands[3], commands[5]].all? { |step| step["env"] == RETURN_ENV })
    uploads = steps.select { |step| step.fetch("uses", "").start_with?("actions/upload-artifact@") }
    require_policy.call(uploads.size == 4 && steps.index(commands[1]) < steps.index(uploads[0]) &&
        steps.index(uploads[1]) < steps.index(commands[2]) && steps.index(commands[3]) < steps.index(uploads[2]) &&
        steps.index(uploads[2]) < steps.index(commands[4]) && steps.index(commands[5]) < steps.index(uploads[3]) &&
        steps.index(uploads[3]) < steps.index(commands[6]) &&
        uploads.map { |step| step["id"] } == %w[public encrypted failed_encrypted diagnostic_encrypted])
    groups = %w[public encrypted failed-encrypted diagnostic-encrypted]
    names_by_group = [%w[generated-dependencies.patch generated-dependencies.json], %w[evidence.tar.gz.gpg manifest.json],
                     %w[evidence.tar.gz.gpg manifest.json], %w[evidence.tar.gz.gpg manifest.json]]
    artifact_prefixes = %w[dependency-candidate dependency-evidence dependency-failed-product-evidence jmdns-diagnostic-evidence]
    groups.zip(names_by_group).each_with_index do |(group, names), index|
        with = uploads[index]["with"]
        require_policy.call(with["path"].lines.map(&:strip) == names.map { |name| "${{ env.P2PKIT_DEPENDENCY_OPERATION }}/outputs/#{group}/#{name}" } &&
            with["retention-days"] == 14 && with["if-no-files-found"] == "error" && with["compression-level"] == 0 &&
            with["name"] == artifact_prefixes[index] + "-${{ github.run_id }}-${{ github.run_attempt }}" &&
            uploads[index]["timeout-minutes"] == 10 &&
            uploads[index]["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a")
    end
    [[commands[2], %w[PUBLIC ENCRYPTED], %w[public encrypted]],
     [commands[4], ["FAILED_ENCRYPTED"], ["failed_encrypted"]],
     [commands[6], ["DIAGNOSTIC_ENCRYPTED"], ["diagnostic_encrypted"]]].each do |command, labels, ids|
        expected = RETURN_ENV.dup
        labels.zip(ids).each do |label, id|
            expected["P2PKIT_#{label}_OUTCOME"] = "${{ steps.#{id}.outcome }}"
            expected["P2PKIT_#{label}_ARTIFACT_ID"] = "${{ steps.#{id}.outputs.artifact-id }}"
            expected["P2PKIT_#{label}_ARTIFACT_DIGEST"] = "${{ steps.#{id}.outputs.artifact-digest }}"
        end
        require_policy.call(command["env"] == expected)
    end
    text = YAML.dump(workflow)
    require_policy.call(!text.match?(/secrets\.|github\.token|actions\/cache|setup-gradle|publish-maven|initial-recipient-execution/))
end

def dispatch_inputs(workflow)
    workflow.fetch("on", workflow[true])["workflow_dispatch"]["inputs"]
end

check(WORKFLOW)
checks = 1
mutations = [
    ->(w) { w["permissions"]["contents"] = "write" },
    ->(w) { w["concurrency"] = HeavyJobQueuePolicy::QUEUE },
    ->(w) { w["jobs"]["generate"]["if"] = "${{ always() }}" },
    ->(w) { w["jobs"]["generate"]["environment"] = "initial-recipient-execution" },
    ->(w) { w["jobs"]["generate"]["continue-on-error"] = true },
    ->(w) { w["jobs"]["generate"]["timeout-minutes"] = 211 },
    ->(w) { w["jobs"]["generate"]["runs-on"] = "self-hosted" },
    ->(w) { w["jobs"]["generate"]["steps"].delete_at(7) },
    ->(w) { w["jobs"]["generate"]["steps"][1]["with"]["fetch-depth"] = 0 },
    ->(w) { w["jobs"]["generate"]["steps"][2]["with"]["fetch-tags"] = true },
    ->(w) { w["jobs"]["generate"]["steps"][2]["with"]["persist-credentials"] = true },
    ->(w) { w["jobs"]["generate"]["steps"][3]["run"].sub!("--no-tags", "--tags") },
    ->(w) { w["jobs"]["generate"]["steps"][3]["run"].sub!("refs/heads/*", "refs/tags/*") },
    ->(w) { w["jobs"]["generate"]["steps"][7]["timeout-minutes"] = 180 },
    ->(w) { w["jobs"]["generate"]["steps"][12]["if"].sub!("failure()", "always()") },
    ->(w) { w["jobs"]["generate"]["steps"][12]["if"].sub!("!cancelled()", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][13]["if"].sub!("steps.failed_guard.outcome == 'success'", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][14]["if"].sub!("steps.failed_encrypted.outcome == 'success'", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][12]["env"]["P2PKIT_DEPENDENCY_FAILED_SHA256"] = "${{ steps.generate.outputs.successSha256 }}" },
    ->(w) { dispatch_inputs(w).delete("operation") },
    ->(w) { dispatch_inputs(w)["operation"]["type"] = "string" },
    ->(w) { dispatch_inputs(w)["operation"]["required"] = false },
    ->(w) { dispatch_inputs(w)["operation"]["default"] = "generate" },
    ->(w) { dispatch_inputs(w)["operation"]["options"] << "arbitrary-task" },
    ->(w) { dispatch_inputs(w)["operation"]["options"][1] = "Diagnose-jmdns" },
    ->(w) { dispatch_inputs(w).delete("candidate_tree") },
    ->(w) { dispatch_inputs(w)["candidate_sha"]["required"] = false },
    ->(w) { w["jobs"]["generate"]["steps"][0]["run"].sub!("pins | {'operation'}", "pins") },
    ->(w) { w["jobs"]["generate"]["steps"][0]["run"].sub!("('generate', 'diagnose-jmdns')", "('generate', 'diagnose-jmdns', 'arbitrary-task')") },
    ->(w) { w["jobs"]["generate"]["steps"][0]["run"].sub!("re.fullmatch(r'[0-9a-f]{40}', request[name])", "True") },
    ->(w) { w["jobs"]["generate"]["steps"][0]["run"].sub!(" == os.environ['GITHUB_WORKFLOW_SHA']", "") },
    ->(w) { w["jobs"]["generate"]["steps"][8].delete("if") },
    ->(w) { w["jobs"]["generate"]["steps"][9]["if"] = "${{ inputs.operation == 'diagnose-jmdns' }}" },
    ->(w) { w["jobs"]["generate"]["steps"][12]["if"].sub!("inputs.operation == 'generate'", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][12]["if"].sub!("steps.generate.outputs.diagnosticSha256 == ''", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("always()", "failure()") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("!cancelled()", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("inputs.operation == 'diagnose-jmdns'", "inputs.operation == 'generate'") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("(steps.generate.outcome == 'success' || steps.generate.outcome == 'failure')", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("steps.generate.outputs.diagnosticSha256 != ''", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("steps.generate.outputs.successSha256 == ''", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["if"].sub!("steps.generate.outputs.failedProductSha256 == ''", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][15]["env"]["P2PKIT_DEPENDENCY_DIAGNOSTIC_SHA256"] = "${{ steps.generate.outputs.failedProductSha256 }}" },
    ->(w) { w["jobs"]["generate"]["steps"][15]["run"].sub!("before-diagnostic-upload", "before-failed-upload") },
    ->(w) { w["jobs"]["generate"]["steps"][16]["if"].sub!("steps.diagnostic_guard.outcome == 'success'", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][16]["with"]["name"].sub!("jmdns-diagnostic-evidence", "dependency-evidence") },
    ->(w) { w["jobs"]["generate"]["steps"][16]["with"]["path"].gsub!("/diagnostic-encrypted/", "/encrypted/") },
    ->(w) { w["jobs"]["generate"]["steps"][17]["if"].sub!("steps.diagnostic_encrypted.outcome == 'success'", "true") },
    ->(w) { w["jobs"]["generate"]["steps"][17]["env"]["P2PKIT_DIAGNOSTIC_ENCRYPTED_ARTIFACT_ID"] = "${{ steps.failed_encrypted.outputs.artifact-id }}" },
    ->(w) { w["jobs"]["generate"]["steps"][17]["env"]["P2PKIT_DIAGNOSTIC_ENCRYPTED_ARTIFACT_DIGEST"] = "${{ steps.encrypted.outputs.artifact-digest }}" },
    ->(w) { w["jobs"]["generate"]["steps"][16]["timeout-minutes"] = 11 },
]
WORKFLOW["jobs"]["generate"]["steps"].each_index do |index|
    mutations << ->(w) { w["jobs"]["generate"]["steps"][index]["if"] = "${{ always() }}" }
    mutations << ->(w) { w["jobs"]["generate"]["steps"][index]["continue-on-error"] = true }
end
[9, 10, 13, 16].each do |index|
    mutations << ->(w) { w["jobs"]["generate"]["steps"][index]["with"]["path"] = "${{ env.P2PKIT_DEPENDENCY_OPERATION }}/**" }
    mutations << ->(w) { w["jobs"]["generate"]["steps"][index]["with"]["retention-days"] = 90 }
end
mutations.each_with_index do |mutate, index|
    changed = Marshal.load(Marshal.dump(WORKFLOW))
    mutate.call(changed)
    raise "ineffective mutation #{index}" if Marshal.dump(changed) == Marshal.dump(WORKFLOW)
    begin
        check(changed)
    rescue StandardError
        checks += 1
        next
    end
    raise "maintenance policy accepted mutation #{index}"
end
puts "RESULT: PASS — #{checks} manual dependency/diagnostic workflow controls; no hosted qualification"
