#!/usr/bin/env ruby
require "tmpdir"
require "open3"
require "rbconfig"
require_relative "../check-workflow-checkout-policy"

CHECKER = File.expand_path("../check-workflow-checkout-policy.rb", __dir__)
CHECKOUT = "actions/checkout@#{'a' * 40}"
checks = 0

def violations(steps)
    WorkflowCheckoutPolicy.violations({"jobs" => {"build" => {"steps" => steps}}}, "fixture.yml")
end

def checkout(inputs = {})
    {"uses" => CHECKOUT, "with" => inputs}
end

raise "boolean false rejected" unless violations([checkout({"persist-credentials" => false})]).empty?
checks += 1

[
    {}, {"persist-credentials" => true}, {"persist-credentials" => nil},
    {"persist-credentials" => "false"}, {"persist-credentials" => "${{ false }}"},
    {"persist-credentials" => 0}, "persist-credentials: false", [], nil,
].each do |inputs|
    errors = violations([checkout(inputs)])
    raise "unsafe checkout inputs accepted" unless errors == [
        "fixture.yml: jobs.build.steps[1] must set checkout with.persist-credentials to boolean false",
    ]
    checks += 1
end

raise "omitted with accepted" unless violations([{"uses" => CHECKOUT}]).length == 1
checks += 1
raise "case-sensitive action detection" unless violations([{"uses" => CHECKOUT.upcase}]).length == 1
checks += 1
raise "only first checkout checked" unless violations([
    checkout({"persist-credentials" => false}), {"run" => "echo safe"}, checkout,
]).first.include?("steps[3]")
checks += 1
raise "unrelated actions rejected" unless violations([
    {"uses" => "example/checkout@#{'a' * 40}"}, {"uses" => "./actions/checkout"},
    {"uses" => "actions/checkout-helper@#{'a' * 40}"}, {"run" => "echo checkout"},
]).empty?
checks += 1

# Parse actual YAML, including aliases, rather than testing Hash fixtures alone.
Dir.mktmpdir("p2pkit-checkout-policy-") do |directory|
    safe = File.join(directory, "safe.yml")
    File.write(safe, <<~YAML)
        on: push
        jobs:
          first:
            steps:
              - &checkout
                uses: #{CHECKOUT}
                with:
                  fetch-depth: 0
                  persist-credentials: false
          second:
            steps:
              - *checkout
          reusable:
            uses: example/repo/.github/workflows/test.yml@#{'a' * 40}
    YAML
    raise "safe alias/reusable workflow rejected" unless WorkflowCheckoutPolicy.check([safe]).empty?
    checks += 1

    unsafe = File.join(directory, "unsafe.yaml")
    File.write(unsafe, File.read(safe).sub("persist-credentials: false", 'persist-credentials: "false"'))
    errors = WorkflowCheckoutPolicy.check([safe, unsafe])
    raise "YAML strings, later files, jobs or aliases bypassed policy" unless errors.length == 2 &&
        errors[0].include?("unsafe.yaml: jobs.first.steps[1]") &&
        errors[1].include?("unsafe.yaml: jobs.second.steps[1]")
    checks += 1

    stdout, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, safe)
    raise "CLI rejects safe workflow" unless status.success? && stdout.include?("RESULT: PASS") && stderr.empty?
    checks += 1
    stdout, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, safe, unsafe)
    raise "CLI fails to reject/identify unsafe workflow" unless !status.success? && stdout.empty? &&
        stderr.lines.length == 2 && stderr.include?("jobs.second.steps[1]")
    checks += 1

    invalid = File.join(directory, "invalid.yml")
    File.write(invalid, "jobs: [invalid\n")
    stdout, _stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, safe, invalid)
    raise "invalid YAML accepted" unless !status.success? && stdout.empty?
    checks += 1
end

puts "RESULT: PASS — #{checks} checkout-policy regression checks"
