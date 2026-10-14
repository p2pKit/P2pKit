#!/usr/bin/env ruby
require "yaml"

ROOT = File.expand_path("../..", __dir__)
FULL = "needs.repository-checks.outputs.full == 'true'"
JAVA_ACTION = "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961"
DAEMON = "Configure Java 21 daemon toolchain"
CAPTURE = "Retain the daemon toolchain selection"
LAUNCHER = "Configure Java 17"
CAPTURE_COMMAND = %q(printf 'P2PKIT_AUDIT_JDK21=%s\n' "$JAVA_HOME" >> "$GITHUB_ENV")
POLICY_CALL = 'ruby "$ROOT/scripts/tests/check-ci-owned-jdk-policy-test.rb"'
COMMANDS = {
    "platform-checks" => {
        "Run complete module and platform checks" => "python3 scripts/run-platform-tests.py full",
    },
    "artifact-checks" => {
        "Verify local release artifacts and consumers" => <<~'BASH'.strip,
            scripts/check-publish-artifacts.sh
            scripts/check-published-consumers.sh
            ./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance --console=plain
            scripts/check-xcframework-minimum-os.sh
        BASH
    },
}.freeze

def one_step(job, name)
    matches = job.fetch("steps").select { |step| step["name"] == name }
    raise "missing/duplicate #{name}" unless matches.size == 1
    matches.first
end

def check_policy(inputs)
    raise "Kotlin toolchain policy must execute the owned-JDK controls" unless
        inputs.fetch(:caller).lines.map(&:strip).count(POLICY_CALL) == 1
    jobs = inputs.fetch(:workflow).fetch("jobs")
    COMMANDS.each do |name, commands|
        job = jobs.fetch(name)
        raise "owned-JDK preparation must retain the same-source 60-minute worker" unless
            job["needs"] == "repository-checks" && job["timeout-minutes"] == 60 && job["runs-on"] == "macos-latest"
        raise "worker execution cannot be overridden" if
            %w[if env defaults continue-on-error].any? { |key| job.key?(key) }
        steps = job.fetch("steps")
        daemon, capture, launcher = [DAEMON, CAPTURE, LAUNCHER].map { |label| one_step(job, label) }
        [[daemon, DAEMON, "21"], [launcher, LAUNCHER, "17"]].each do |step, label, version|
            raise "exact full-scope pinned JDK#{version} setup required" unless step == {
                "name" => label, "if" => FULL, "uses" => JAVA_ACTION,
                "with" => {"distribution" => "temurin", "java-version" => version},
            }
        end
        raise "must retain JDK21 before JAVA_HOME changes back to JDK17" unless capture == {
            "name" => CAPTURE, "if" => FULL, "run" => CAPTURE_COMMAND,
        }
        java_steps = steps.select { |step| step.fetch("uses", "").start_with?("actions/setup-java@") }
        raise "no additional Java setup may replace the selected launcher" unless java_steps == [daemon, launcher]
        first = steps.index(daemon)
        gradle = steps.index(one_step(job, "Validate wrapper and configure Gradle"))
        raise "setup21, capture and setup17 must remain consecutive after source admission" unless
            steps[first, 3] == [daemon, capture, launcher] &&
            steps.index(one_step(job, "Validate same-source scope")) < first &&
            first + 2 < gradle
        commands.each do |label, command|
            step = one_step(job, label)
            raise "complete command or scope changed during toolchain preparation" unless
                step.fetch("run").strip == command && step["if"] == FULL &&
                (step.keys - %w[name id if run]).empty? && gradle < steps.index(step)
        end
    end
end

inputs = {
    workflow: YAML.safe_load(File.read(File.join(ROOT, ".github/workflows/ci.yml")), aliases: true),
    caller: File.read(File.join(ROOT, "scripts/tests/check-kotlin-toolchain-policy-test.sh")),
}
check_policy(inputs)
mutations = {"missing policy wiring" => ->(v) { v[:caller].sub!(POLICY_CALL, "true") }}
COMMANDS.each do |name, commands|
    [DAEMON, CAPTURE, LAUNCHER].each do |label|
        mutations["#{name} missing #{label}"] = ->(v) do
            job = v[:workflow]["jobs"][name]
            job["steps"].delete(one_step(job, label))
        end
        {"missing condition" => nil, "disabled condition" => false}.each do |description, value|
            mutations["#{name} #{label} #{description}"] = ->(v) do
                one_step(v[:workflow]["jobs"][name], label)["if"] = value
            end
        end
        {"continue-on-error" => true, "env" => {"JAVA_HOME" => "/other"}}.each do |key, value|
            mutations["#{name} #{label} #{key}"] = ->(v) do
                one_step(v[:workflow]["jobs"][name], label)[key] = value
            end
        end
    end
    [DAEMON, LAUNCHER].each do |label|
        mutations["#{name} wrong #{label} version"] = ->(v) do
            one_step(v[:workflow]["jobs"][name], label)["with"]["java-version"] = "22"
        end
        mutations["#{name} unpinned #{label}"] = ->(v) do
            one_step(v[:workflow]["jobs"][name], label)["uses"] = "actions/setup-java@v5"
        end
    end
    ["JAVA_HOME_21_X64", "GITHUB_OUTPUT"].each do |replacement|
        mutations["#{name} wrong capture #{replacement}"] = ->(v) do
            capture = one_step(v[:workflow]["jobs"][name], CAPTURE)
            capture["run"] = CAPTURE_COMMAND.sub(replacement == "GITHUB_OUTPUT" ? "GITHUB_ENV" : "JAVA_HOME", replacement)
        end
    end
    mutations["#{name} swapped Java setups"] = ->(v) do
        steps = v[:workflow]["jobs"][name]["steps"]
        left, right = [DAEMON, LAUNCHER].map { |label| steps.index { |step| step["name"] == label } }
        steps[left], steps[right] = steps[right], steps[left]
    end
    [DAEMON, LAUNCHER].each do |label|
        mutations["#{name} capture swapped with #{label}"] = ->(v) do
            steps = v[:workflow]["jobs"][name]["steps"]
            left, right = [CAPTURE, label].map { |item| steps.index { |step| step["name"] == item } }
            steps[left], steps[right] = steps[right], steps[left]
        end
    end
    ["Validate same-source scope", "Validate wrapper and configure Gradle"].each do |label|
        mutations["#{name} wrong setup boundary #{label}"] = ->(v) do
            steps = v[:workflow]["jobs"][name]["steps"]
            index = steps.index { |step| step["name"] == label }
            steps << steps.delete_at(index)
        end
    end
    [nil, 61].each do |timeout|
        mutations["#{name} changed job timeout #{timeout}"] = ->(v) do
            v[:workflow]["jobs"][name]["timeout-minutes"] = timeout
        end
    end
    commands.each_key do |label|
        mutations["#{name} changed complete command"] = ->(v) do
            one_step(v[:workflow]["jobs"][name], label)["run"] += "\ntrue"
        end
        mutations["#{name} conditional complete command"] = ->(v) do
            one_step(v[:workflow]["jobs"][name], label)["if"] = false
        end
        mutations["#{name} added product timeout"] = ->(v) do
            one_step(v[:workflow]["jobs"][name], label)["timeout-minutes"] = 120
        end
    end
end
mutations.each do |name, mutate|
    altered = Marshal.load(Marshal.dump(inputs))
    mutate.call(altered)
    rejected = false
    begin
        check_policy(altered)
    rescue KeyError, RuntimeError, ArgumentError
        rejected = true
    end
    raise "unsafe owned-JDK policy accepted: #{name}" unless rejected
end
puts "RESULT: PASS — explicit CI daemon21/launcher17 preparation (#{mutations.size + 1} policy checks)"
