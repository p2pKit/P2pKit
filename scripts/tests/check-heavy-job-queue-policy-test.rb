#!/usr/bin/env ruby
# Static policy controls only: no Gradle, scheduler simulation or hosted admission.
require "tmpdir"
require "open3"
require "rbconfig"
require_relative "../check-heavy-job-queue-policy"

ROOT = File.expand_path("../..", __dir__)
CHECKER = File.join(ROOT, "scripts/check-heavy-job-queue-policy.rb")
INVOCATION = "ruby scripts/tests/check-heavy-job-queue-policy-test.rb"
STEP_NAME = "Verify participating heavy-job queue policy"
POLICY = HeavyJobQueuePolicy

def copy(value)
    Marshal.load(Marshal.dump(value))
end

def reject(name, diagnostic)
    begin
        yield
    rescue HeavyJobQueuePolicy::Error => error
        raise "wrong rejection for #{name}: #{error.message}" unless error.message.include?(diagnostic)
        return 1
    end
    raise "unsafe heavy-job queue policy accepted: #{name}"
end

def check_entrypoints(ci, release, workflow_test)
    steps = ci.fetch("jobs").fetch("complete-gate").fetch("steps")
    policy_steps = steps.select { |step| step["name"] == STEP_NAME }
    POLICY.require_policy(policy_steps.size == 1 && policy_steps.first == {"name" => STEP_NAME, "run" => INVOCATION},
                          "CI must execute the queue policy unconditionally without overrides")
    scope = steps.find { |step| step["id"] == "scope" }
    POLICY.require_policy(scope && steps.index(policy_steps.first) < steps.index(scope),
                          "queue policy must cover both CI scopes")
    [release, workflow_test].each do |script|
        POLICY.require_policy(script.lines.map(&:strip).include?("set -euo pipefail"), "entrypoints must fail closed")
    end
    POLICY.require_policy(release.lines.map(&:strip).count(INVOCATION) == 1, "release gate must execute queue policy")
    # Keep the existing owners of task/evidence/security/required/schedule policy;
    # this queue checker intentionally does not reimplement those contracts.
    %w[check-heavy-job-queue-policy-test.rb check-jvm-cross-host-policy-test.rb check-ci-scope-policy-test.rb
       check-platform-test-policy-test.rb check-workflow-checkout-policy-test.rb
       check-dependency-submission-policy-test.rb].each do |script|
        command = 'ruby "$ROOT/scripts/tests/' + script + '"'
        POLICY.require_policy(workflow_test.lines.map(&:strip).count(command) == 1,
                              "release workflow tests must retain #{script}")
    end
end

workflows = POLICY.read_workflows(File.join(ROOT, ".github/workflows"))
original = Marshal.dump(workflows)
POLICY.check(workflows)
checks = 1
mutations = {}
POLICY::JOBS.each do |path, jobs|
    mutations["missing #{path}"] = ["missing participating workflow", ->(w) { w.delete(path) }]
    mutations["extra #{path} job"] = ["participating job IDs", ->(w) { w[path]["jobs"]["extra"] = {} }]
    jobs.each_key do |id|
        key = "#{path}/#{id}"
        mutations["#{key} missing concurrency"] = ["exact job-level", ->(w) { w[path]["jobs"][id].delete("concurrency") }]
        mutations["#{key} step-level concurrency"] = ["exact job-level", ->(w) {
            job = w[path]["jobs"][id]
            job["steps"].first["concurrency"] = job.delete("concurrency")
        }]
        mutations["#{key} string concurrency"] = ["exact job-level", ->(w) {
            w[path]["jobs"][id]["concurrency"] = POLICY::GROUP
        }]
        {"group" => ["other-heavy", POLICY::GROUP.upcase, POLICY::GROUP + "-${{ matrix.os }}"],
         "queue" => [nil, "single", "MAX", "${{ 'max' }}", true],
         "cancel-in-progress" => [nil, true, "false", "${{ false }}"],
         "unknown-option" => [1]}.each do |field, values|
            values.each do |value|
                mutations["#{key} #{field}=#{value.inspect}"] = ["exact job-level", ->(w) {
                    w[path]["jobs"][id]["concurrency"][field] = value
                }]
            end
        end
        %w[group queue cancel-in-progress].each do |field|
            mutations["#{key} absent #{field}"] = ["exact job-level", ->(w) {
                w[path]["jobs"][id]["concurrency"].delete(field)
            }]
        end
        mutations["#{key} renamed check"] = ["preserve job/check name", ->(w) { w[path]["jobs"][id]["name"] = "other" }]
        mutations["#{key} ignored failure"] = ["failures must remain blocking", ->(w) {
            w[path]["jobs"][id]["continue-on-error"] = true
        }]
        mutations["#{key} conditional job"] = ["required-gate guard", ->(w) { w[path]["jobs"][id]["if"] = false }]
        mutations["#{key} dependency cycle"] = ["acyclic job dependencies", ->(w) { w[path]["jobs"][id]["needs"] = id }]
    end
end
POLICY::MATRICES.each_key do |path, id|
    [nil, 0, 2, true, "1", 1.0, "${{ 1 }}"].each do |value|
        mutations["#{path} max-parallel=#{value.inspect}"] = ["max-parallel:1", ->(w) {
            w[path]["jobs"][id]["strategy"]["max-parallel"] = value
        }]
    end
    mutations["#{path} absent max-parallel"] = ["max-parallel:1", ->(w) {
        w[path]["jobs"][id]["strategy"].delete("max-parallel")
    }]
    mutations["#{path} fail-fast"] = ["fail-fast:false", ->(w) { w[path]["jobs"][id]["strategy"]["fail-fast"] = true }]
    mutations["#{path} missing host"] = ["unchanged native matrix", ->(w) {
        w[path]["jobs"][id]["strategy"]["matrix"].values.first.pop
    }]
    mutations["#{path} additional axis"] = ["unchanged native matrix", ->(w) {
        w[path]["jobs"][id]["strategy"]["matrix"]["extra"] = [1, 2]
    }]
end
POLICY::JOBS.each_key do |path|
    mutations["#{path} workflow/job deadlock"] = ["separate workflow concurrency", ->(w) {
        w[path]["concurrency"] = copy(POLICY::QUEUE)
    }]
end
POLICY::WORKFLOW_CONCURRENCY.each_key do |path|
    mutations["#{path} dropped workflow supersession"] = ["separate workflow concurrency", ->(w) {
        w[path].delete("concurrency")
    }]
    mutations["#{path} changed workflow cancellation"] = ["separate workflow concurrency", ->(w) {
        w[path]["concurrency"]["cancel-in-progress"] = !w[path]["concurrency"]["cancel-in-progress"]
    }]
end
mutations["lock operation falls through into ordinary sample matrix"] = ["required-gate guard", ->(w) {
    w["desktop-cross-host.yml"]["jobs"]["verify"]["if"].sub!(" && inputs.operation != 'dependency-lock-candidate'", "")
}]
mutations["helper operation falls through into ordinary sample matrix"] = ["required-gate guard", ->(w) {
    w["desktop-cross-host.yml"]["jobs"]["verify"]["if"].sub!(" && inputs.operation != 'windows-helper-controls'", "")
}]
mutations["helper workflow cancellation bypass"] = ["separate workflow concurrency", ->(w) {
    w["desktop-cross-host.yml"]["concurrency"]["cancel-in-progress"].sub!(" && inputs.operation != 'windows-helper-controls'", "")
}]
mutations["helper workflow loses run-specific group"] = ["separate workflow concurrency", ->(w) {
    w["desktop-cross-host.yml"]["concurrency"]["group"].sub!(" || inputs.operation == 'windows-helper-controls'", "")
}]
mutations["lock workflow can supersede other work"] = ["separate workflow concurrency", ->(w) {
    w["desktop-cross-host.yml"]["concurrency"]["group"] = "desktop-cross-host-${{ github.ref }}"
}]
[POLICY::GROUP, POLICY::GROUP.upcase, "${{ '#{POLICY::GROUP}' }}", POLICY::QUEUE].each do |concurrency|
    ["workflow", "job"].each do |scope|
        mutations["unreviewed #{scope} group #{concurrency}"] = ["reserved participating-job group", ->(w) {
            # A job literally named workflow must not hide workflow-level use.
            extra = {"jobs" => {"workflow" => {}}}
            target = scope == "workflow" ? extra : extra["jobs"]["workflow"]
            target["concurrency"] = concurrency
            w["unreviewed.yml"] = extra
        }]
    end
end
mutations.each do |name, (diagnostic, mutate)|
    changed = copy(workflows)
    mutate.call(changed)
    checks += reject(name, diagnostic) { POLICY.check(changed) }
end

ci_text = File.read(File.join(ROOT, ".github/workflows/ci.yml"))
{
    "duplicate queue" => [ci_text.sub("queue: max", "queue: single\n      queue: max"), "duplicate YAML key"],
    "duplicate jobs" => [ci_text + "\njobs: {}\n", "duplicate YAML key"],
    "merge override" => ["jobs:\n  build:\n    <<: {concurrency: wrong}\n", "merge overrides"],
    "multiple documents" => [ci_text + "\n---\njobs: {}\n", "one YAML document"],
    "malformed YAML" => ["jobs: [\n", "invalid YAML"],
    "non-workflow YAML" => ["[jobs]\n", "workflow/jobs mappings"],
}.each do |name, (text, diagnostic)|
    checks += reject(name, diagnostic) { POLICY.parse(text, name) }
end
# An actual alias of an exact job-level mapping is unambiguous and legal;
# do not require a particular formatting while rejecting merge/duplicate keys.
aliased = ci_text.sub("    concurrency:\n", "    concurrency: &heavy\n")
aliased.sub!("    concurrency:\n      group: #{POLICY::GROUP}\n      queue: max\n      cancel-in-progress: false\n",
             "    concurrency: *heavy\n")
POLICY.check(workflows.merge("ci.yml" => POLICY.parse(aliased, "aliased.yml")))
checks += 1

release = File.read(File.join(ROOT, "scripts/run-release-gate.sh"))
workflow_test = File.read(File.join(ROOT, "scripts/tests/release-workflow-test.sh"))
check_entrypoints(workflows["ci.yml"], release, workflow_test)
checks += 1
%w[if continue-on-error env shell working-directory].each do |field|
    changed = copy(workflows["ci.yml"])
    changed["jobs"]["complete-gate"]["steps"].find { |step| step["name"] == STEP_NAME }[field] = true
    checks += reject("conditional/overridden queue policy #{field}", "unconditionally without overrides") {
        check_entrypoints(changed, release, workflow_test)
    }
end
checks += reject("release policy bypass", "release gate must execute queue policy") {
    check_entrypoints(workflows["ci.yml"], release.sub(INVOCATION, INVOCATION + " || true"), workflow_test)
}
checks += reject("removed full workflow regression", "retain check-heavy-job-queue-policy-test.rb") {
    check_entrypoints(workflows["ci.yml"], release, workflow_test.sub("check-heavy-job-queue-policy-test.rb", "omitted.rb"))
}

Dir.mktmpdir("p2pkit-heavy-queue-policy-") do |directory|
    Dir[File.join(ROOT, ".github/workflows/*.{yml,yaml}")].each do |path|
        File.write(File.join(directory, File.basename(path)), File.read(path))
    end
    stdout, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, directory)
    raise "queue policy CLI rejected source: #{stdout}#{stderr}" unless status.success? && stdout.include?("RESULT: PASS")
    checks += 1
    File.write(File.join(directory, "ci.yml"), ci_text.sub("queue: max", "queue: single"))
    stdout, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, directory)
    raise "queue policy CLI accepted default replacement" unless !status.success? && stdout.empty? && stderr.include?("queue:max")
    checks += 1

    # Reuse real policy owners for the untouched command/result/schedule guards,
    # rather than embedding another copy of the full CI workflow contract here.
    {"check-jvm-cross-host-policy-test.rb" => [
        [ci_text, nil],
        [ci_text.sub('test "$JVM_CHECK_RESULT" = success', "true"), "first require matrix success"],
        [ci_text.sub(":p2p-core:jvmTest", ":p2p-core:jvmTest --tests '*subset*'"), "execute all suites"],
    ], "check-ci-scope-policy-test.rb" => [
        [ci_text, nil],
        [ci_text.sub('17 4 * * 1', '17 4 1 * *'), "weekly full-gate backstop"],
        [ci_text.sub("github.event_name != 'schedule'", "true"), "isolated and non-cancelling"],
    ]}.each do |script, cases|
        cases.each do |text, diagnostic|
            File.write(File.join(directory, "ci.yml"), text)
            stdout, stderr, status = Open3.capture3(RbConfig.ruby, File.join(__dir__, script), File.join(directory, "ci.yml"))
            valid = diagnostic ? !status.success? && stderr.include?(diagnostic) : status.success? && stdout.include?("RESULT: PASS")
            raise "existing #{script} control failed: #{stdout}#{stderr}" unless valid
            checks += 1
        end
    end
end
{"unreviewed/new-input.bin\0" => "full", "" => "full", "docs/example.md\0" => "lightweight"}.each do |paths, expected|
    stdout, stderr, status = Open3.capture3("bash", File.join(ROOT, "scripts/classify-ci-scope.sh"), stdin_data: paths)
    raise "queue changes weakened unknown-path/full-gate selection" unless status.success? && stdout.strip == expected && stderr.empty?
    checks += 1
end
raise "policy tests mutated their input" unless original == Marshal.dump(workflows)
puts "RESULT: PASS — participating heavy-job queue/schema and preserved CI guards (#{checks} regression checks)"
