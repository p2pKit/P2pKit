#!/usr/bin/env ruby
require "yaml"

# The cadence is a reviewed policy, not a guarantee that GitHub will deliver
# every scheduled run. A schedule must never share push cancellation ownership.
SCHEDULE = [{"cron" => "17 4 * * 1"}].freeze
CONCURRENCY = {
    "group" => "ci-${{ github.workflow }}-${{ github.ref }}-${{ github.event_name == 'schedule' && 'schedule' || 'change' }}",
    "cancel-in-progress" => "${{ github.event_name != 'schedule' }}",
}.freeze
SCOPE_ENV = {
    "EVENT_NAME" => "${{ github.event_name }}",
    "REF_NAME" => "${{ github.ref_name }}",
    "BEFORE_SHA" => "${{ github.event.before }}",
    "PR_BASE_SHA" => "${{ github.event.pull_request.base.sha }}",
    "PR_HEAD_SHA" => "${{ github.event.pull_request.head.sha }}",
}.freeze
SCOPE_COMMAND = 'scripts/resolve-ci-scope.sh >> "$GITHUB_OUTPUT"'

def triggers(workflow)
    # Psych versions following YAML 1.1 parse the unquoted key `on` as true.
    workflow.fetch("on") { workflow.fetch(true) }
end

def scope_steps(workflow)
    workflow.fetch("jobs").fetch("complete-gate").fetch("steps").select { |step| step["id"] == "scope" }
end

def check_ci_scope(workflow)
    events = triggers(workflow)
    raise "CI must keep push, PR, manual and scheduled triggers" unless
        events.keys.sort == %w[pull_request push schedule workflow_dispatch]
    raise "CI must keep unfiltered main pushes" unless events["push"] == {"branches" => ["main"]}
    raise "CI must keep unfiltered PRs and manual dispatches" unless
        ["pull_request", "workflow_dispatch"].all? { |name| [nil, {}].include?(events[name]) }
    raise "CI must keep the weekly full-gate backstop" unless events["schedule"] == SCHEDULE
    raise "CI schedules must be isolated and non-cancelling; ordinary runs must retain per-ref supersession" unless
        workflow["concurrency"] == CONCURRENCY
    raise "CI scope does not need check-run or write permissions" unless workflow["permissions"] == {"contents" => "read"}

    scopes = scope_steps(workflow)
    raise "CI must have exactly one scope resolver" unless scopes.length == 1
    scope = scopes.first
    raise "CI must execute the resolver and persist its outputs" unless scope["run"] == SCOPE_COMMAND
    raise "CI scope must be bound to the complete event identity" unless scope["env"] == SCOPE_ENV
    raise "CI scope must use Bash without conditional or ignored failures" unless
        scope["shell"] == "bash" && !scope.key?("if") && !scope.key?("continue-on-error")

    steps = workflow.fetch("jobs").fetch("complete-gate").fetch("steps")
    lightweight = steps.find { |step| step["name"] == "Verify lightweight documentation change" }
    raise "CI lightweight checks must retain the scope policy regression" unless lightweight &&
        lightweight.fetch("run").lines.map(&:strip).include?("ruby scripts/tests/check-ci-scope-policy-test.rb")
end

path = ARGV.fetch(0, File.expand_path("../../.github/workflows/ci.yml", __dir__))
workflow = YAML.safe_load(File.read(path), aliases: true)
check_ci_scope(workflow)
checks = 1

mutations = {
    "missing schedule" => ["scheduled triggers", ->(w) { triggers(w).delete("schedule") }],
    "empty schedule" => ["weekly full-gate backstop", ->(w) { triggers(w)["schedule"] = [] }],
    "changed schedule" => ["weekly full-gate backstop", ->(w) { triggers(w)["schedule"] = [{"cron" => "17 4 1 * *"}] }],
    "filtered push" => ["unfiltered main pushes", ->(w) { triggers(w)["push"]["paths"] = ["docs/**"] }],
    "filtered PR" => ["unfiltered PRs", ->(w) { triggers(w)["pull_request"] = {"paths" => ["docs/**"]} }],
    "missing manual run" => ["manual and scheduled triggers", ->(w) { triggers(w).delete("workflow_dispatch") }],
    "missing concurrency" => ["isolated and non-cancelling", ->(w) { w.delete("concurrency") }],
    "shared push cancellation" => ["isolated and non-cancelling", ->(w) {
        w["concurrency"]["group"] = "ci-${{ github.workflow }}-${{ github.ref }}"
    }],
    "cancelling schedules" => ["isolated and non-cancelling", ->(w) { w["concurrency"]["cancel-in-progress"] = true }],
    "uncancelled stale pushes" => ["per-ref supersession", ->(w) { w["concurrency"]["cancel-in-progress"] = false }],
    "unneeded permissions" => ["check-run or write permissions", ->(w) { w["permissions"]["checks"] = "read" }],
    "missing scope" => ["exactly one scope resolver", ->(w) { scope_steps(w).first.delete("id") }],
    "duplicate scope" => ["exactly one scope resolver", ->(w) {
        w["jobs"]["complete-gate"]["steps"] << scope_steps(w).first.dup
    }],
    "printed scope command" => ["execute the resolver", ->(w) { scope_steps(w).first["run"] = "echo #{SCOPE_COMMAND}" }],
    "constant event" => ["complete event identity", ->(w) { scope_steps(w).first["env"]["EVENT_NAME"] = "push" }],
    "wrong push base" => ["complete event identity", ->(w) {
        scope_steps(w).first["env"]["BEFORE_SHA"] = "${{ github.sha }}"
    }],
    "conditional scope" => ["without conditional or ignored failures", ->(w) { scope_steps(w).first["if"] = false }],
    "ignored scope failure" => ["without conditional or ignored failures", ->(w) {
        scope_steps(w).first["continue-on-error"] = true
    }],
    "wrong scope shell" => ["must use Bash", ->(w) { scope_steps(w).first["shell"] = "sh" }],
    "missing lightweight policy check" => ["retain the scope policy regression", ->(w) {
        w["jobs"]["complete-gate"]["steps"].find do |step|
            step["name"] == "Verify lightweight documentation change"
        end["run"].sub!("ruby scripts/tests/check-ci-scope-policy-test.rb", "echo omitted")
    }],
}

mutations.each do |name, (diagnostic, mutate)|
    copy = Marshal.load(Marshal.dump(workflow))
    mutate.call(copy)
    rejected = false
    begin
        check_ci_scope(copy)
    rescue RuntimeError => error
        raise "wrong rejection for #{name}: #{error.message}" unless error.message.include?(diagnostic)
        rejected = true
    end
    raise "unsafe CI scope policy accepted: #{name}" unless rejected
    checks += 1
end

puts "RESULT: PASS — weekly CI scope, cancellation isolation and exact resolver wiring (#{checks} regression checks)"
