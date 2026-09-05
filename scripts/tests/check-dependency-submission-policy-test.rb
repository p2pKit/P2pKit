#!/usr/bin/env ruby
require "yaml"
require "shellwords"

def submission_arguments(workflow)
    steps = workflow.fetch("jobs").values.flat_map { |job| job.fetch("steps", []) }
    submissions = steps.select do |step|
        step["uses"].is_a?(String) && step["uses"].match?(/\Agradle\/actions\/dependency-submission@/i)
    end
    raise "expected exactly one dependency-submission action" unless submissions.length == 1

    inputs = submissions.first["with"]
    arguments = inputs["additional-arguments"] if inputs.is_a?(Hash)
    raise "dependency submission must explicitly override verification=off with strict" unless
        arguments.is_a?(String) && Shellwords.split(arguments) == ["--dependency-verification", "strict"]
end

def fixture(arguments)
    {"jobs" => {"submit" => {"steps" => [{
        "uses" => "gradle/actions/dependency-submission@#{'a' * 40}",
        "with" => {"additional-arguments" => arguments},
    }]}}}
end

submission_arguments(fixture("--dependency-verification strict"))
submission_arguments(fixture("  --dependency-verification 'strict'\n"))
checks = 2
[
    nil, false, [], "", "--no-daemon", "--dependency-verification off",
    "--dependency-verification lenient", "-Dorg.gradle.dependency.verification=strict",
    "${{ inputs.arguments }}", "--dependency-verification strict --dependency-verification off",
    "--dependency-verification strict --write-verification-metadata sha256",
    "--dependency-verification 'strict",
].each do |arguments|
    rejected = false
    begin
        submission_arguments(fixture(arguments))
    rescue RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe submission arguments accepted: #{arguments.inspect}" unless rejected
    checks += 1
end

safe = fixture("--dependency-verification strict")
safe["jobs"]["submit"]["steps"].unshift({"run" => "echo preceding step"})
safe["jobs"]["reusable"] = {"uses" => "example/repo/.github/workflows/test.yml@#{'a' * 40}"}
submission_arguments(safe)
checks += 1

path = ARGV.fetch(0, File.expand_path("../../.github/workflows/dependency-submission.yml", __dir__))
submission_arguments(YAML.safe_load(File.read(path), aliases: true))
puts "RESULT: PASS — dependency submission enforces strict verification (#{checks} regression checks)"
