#!/usr/bin/env ruby
# Source/negative controls for the maintained reusable component worker, not the
# retired platform-checks/artifact-checks cache-witness experiment. setup-java
# retains versioned JAVA_HOME_21_* while the second setup selects launcher 17;
# Gradle's checked-in daemon criteria selects 21 independently of JAVA_HOME.
require "yaml"

ROOT = File.expand_path("../..", __dir__)
POLICY_CALL = 'ruby "$ROOT/scripts/tests/check-ci-owned-jdk-policy-test.rb"'
JAVA_ACTION = "actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6"
GRADLE_ACTION = "gradle/actions/setup-gradle@3f5f9adaf7d9fecd50b5935e54106014257a94e6"
DAEMON = "Configure Java 21 daemon/runtime"
LAUNCHER = "Configure Java 17 library toolchain"
CACHE = "Configure optional verified dependency cache"
HOME = "Select this job's optional Gradle cache directory"
SETUP = "Install required platform tools"
EXECUTE = "Execute actual component and encrypt private evidence"
CHECKOUT = "Check out exact event source without credentials"
HOME_COMMAND = 'echo "GRADLE_USER_HOME=$RUNNER_TEMP/gradle-home" >> "$GITHUB_ENV"'
EXCLUDES = "caches/build-cache-1\ncaches/*/kotlin-dsl\ncaches/*/scripts\ncaches/*/groovy-dsl\n"

EXECUTION = <<~'BASH'
    if [[ "$COMPONENT" == jmdns-diagnostic || "$COMPONENT" == macos-shared || "$COMPONENT" == consumers || "$COMPONENT" == published-consumers-diagnostic || "$COMPONENT" == consumers-pom-diagnostic ]]; then
      if [[ "$COMPONENT" == jmdns-diagnostic ]]; then [[ "$MINUTES" == 30 ]]
      elif [[ "$COMPONENT" == consumers-pom-diagnostic ]]; then [[ "$MINUTES" == 60 ]]
      else [[ "$MINUTES" == 120 ]]; fi
      python3 -B scripts/run-ci-terminal-component.py --component "$COMPONENT"
    else
      python3 -B scripts/ci_evidence.py --component "$COMPONENT" --timeout-seconds "$((MINUTES * 60))" --output-dir "$RUNNER_TEMP/ci-evidence-$COMPONENT" --report-glob '**/build/test-results/**/*.xml' --report-glob 'build/reports/**/*' -- python3 -B scripts/ci_component.py "$COMPONENT"
    fi
BASH


def one_step(job, name)
    matches = job.fetch("steps").select { |step| step["name"] == name }
    raise "missing/duplicate #{name}" unless matches.size == 1
    matches.first
end

def check_policy(inputs)
    raise "Kotlin toolchain policy must execute owned-JDK controls" unless
        inputs.fetch(:caller).lines.map(&:strip).count(POLICY_CALL) == 1
    raise "Gradle daemon criteria must select JDK21" unless
        inputs.fetch(:criteria).lines.map(&:strip).grep(/^toolchainVersion=/) == ["toolchainVersion=21"]
    workflow = inputs.fetch(:worker)
    raise "worker permissions changed" unless workflow["permissions"] == {"contents" => "read", "actions" => "read"}
    job = workflow.fetch("jobs").fetch("run")
    raise "component must use the caller-selected host and finite job budget" unless
        job["runs-on"] == '${{ inputs.runner }}' && job["timeout-minutes"] == '${{ inputs.job_minutes }}'
    raise "worker cannot bypass execution" if %w[if continue-on-error container services].any? { |key| job.key?(key) }
    raise "worker shell changed" unless job["defaults"] == {"run" => {"shell" => "bash"}}
    raise "worker cannot override selected JDK/cache homes" unless job["env"] == {
        "PYTHONDONTWRITEBYTECODE" => "1",
        "CI_EVIDENCE_RECIPIENT_SHA256" => '${{ vars.CI_EVIDENCE_RECIPIENT_SHA256 }}',
        "CI_EVIDENCE_RECIPIENT_FINGERPRINT" => '${{ vars.CI_EVIDENCE_RECIPIENT_FINGERPRINT }}',
    }
    steps = job.fetch("steps")
    expected_names = [CHECKOUT, HOME, DAEMON, LAUNCHER, CACHE, SETUP, EXECUTE,
        "Retain genuine component evidence, including failures", "Retain exact inspected Android package",
        "Retain exact inspected desktop package"]
    raise "preparation/execution order changed or extra steps added" unless steps.map { |s| s["name"] } == expected_names
    raise "source checkout must not retain credentials or select another ref" unless one_step(job, CHECKOUT) == {
        "name" => CHECKOUT, "uses" => "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "with" => {"persist-credentials" => false, "fetch-depth" => 0},
    }
    raise "cache home must be job-owned before setup" unless one_step(job, HOME) == {"name" => HOME, "run" => HOME_COMMAND}
    [[DAEMON, "${{ inputs.component == 'desktop-windows' && '21.0.12+101.0' || '21' }}"], [LAUNCHER, "17"]].each do |label, version|
        raise "pinned unconditional JDK setup/order changed" unless one_step(job, label) == {
            "name" => label, "uses" => JAVA_ACTION, "with" => {"distribution" => "temurin", "java-version" => version},
        }
    end
    raise "cache trust/exclusions changed" unless one_step(job, CACHE) == {
        "name" => CACHE, "if" => "${{ inputs.component != 'source' && inputs.component != 'security' }}",
        "uses" => GRADLE_ACTION, "with" => {
            "cache-read-only" => "${{ github.ref != 'refs/heads/main' }}", "gradle-home-cache-excludes" => EXCLUDES,
        },
    }
    raise "platform setup must execute before Gradle without ignored failures" unless one_step(job, SETUP) == {
        "name" => SETUP, "env" => {"COMPONENT" => '${{ inputs.component }}'},
        "run" => 'bash scripts/setup-ci-component.sh "$COMPONENT"',
    }
    execute = one_step(job, EXECUTE)
    raise "component invocation must not override selected JDK/cache context or hide failure" unless
        execute.keys.sort == %w[env id name run] && execute["id"] == "execution" && execute["env"] == {
            "COMPONENT" => '${{ inputs.component }}', "MINUTES" => '${{ inputs.minutes }}',
        } && execute["run"] == EXECUTION
    route = inputs.fetch(:workflow).fetch("jobs").fetch("component")
    raise "components must execute same-source reusable worker" unless route["uses"] == "./.github/workflows/ci-component.yml"
    raise "matrix must preserve host/budget/component selection" unless route["with"] == {
        "component" => '${{ matrix.component }}', "runner" => '${{ matrix.os }}',
        "minutes" => '${{ matrix.minutes }}', "job_minutes" => '${{ matrix.job_minutes }}',
    } && route.fetch("strategy")["fail-fast"] == false && route["needs"] == "plan"
end

inputs = {
    workflow: YAML.safe_load(File.read(File.join(ROOT, ".github/workflows/ci.yml")), aliases: true),
    worker: YAML.safe_load(File.read(File.join(ROOT, ".github/workflows/ci-component.yml")), aliases: true),
    caller: File.read(File.join(ROOT, "scripts/tests/check-kotlin-toolchain-policy-test.sh")),
    criteria: File.read(File.join(ROOT, "gradle/gradle-daemon-jvm.properties")),
}
check_policy(inputs)
mutations = {
    "missing policy wiring" => ->(v) { v[:caller].sub!(POLICY_CALL, "true") },
    "wrong daemon criteria" => ->(v) { v[:criteria].sub!("toolchainVersion=21", "toolchainVersion=17") },
    "write token" => ->(v) { v[:worker]["permissions"]["contents"] = "write" },
    "remote worker" => ->(v) { v[:workflow]["jobs"]["component"]["uses"] = "owner/repo/.github/workflows/ci-component.yml@main" },
    "fail fast skips peers" => ->(v) { v[:workflow]["jobs"]["component"]["strategy"]["fail-fast"] = true },
}
%w[component runner minutes job_minutes].each do |key|
    mutations["changed caller #{key}"] = ->(v) { v[:workflow]["jobs"]["component"]["with"][key] = "other" }
end
{"runs-on" => "macos-latest", "timeout-minutes" => 360, "if" => false,
 "continue-on-error" => true, "defaults" => {"run" => {"shell" => "sh"}},
 "env" => {"JAVA_HOME" => "/other"}}.each do |key, value|
    mutations["changed worker #{key}"] = ->(v) { v[:worker]["jobs"]["run"][key] = value }
end
[CHECKOUT, HOME, DAEMON, LAUNCHER, CACHE, SETUP, EXECUTE].each do |name|
    mutations["missing #{name}"] = ->(v) { v[:worker]["jobs"]["run"]["steps"].delete(one_step(v[:worker]["jobs"]["run"], name)) }
    mutations["duplicate #{name}"] = ->(v) { v[:worker]["jobs"]["run"]["steps"] << one_step(v[:worker]["jobs"]["run"], name).dup }
    mutations["reordered #{name}"] = ->(v) do
        steps = v[:worker]["jobs"]["run"]["steps"]
        steps << steps.delete(one_step(v[:worker]["jobs"]["run"], name))
    end
    {"if" => false, "continue-on-error" => true, "env" => {"JAVA_HOME" => "/other"}}.each do |key, value|
        mutations["#{name} #{key}"] = ->(v) { one_step(v[:worker]["jobs"]["run"], name)[key] = value }
    end
end
[DAEMON, LAUNCHER].each do |name|
    %w[distribution java-version].each do |key|
        mutations["#{name} wrong #{key}"] = ->(v) { one_step(v[:worker]["jobs"]["run"], name)["with"][key] = "other" }
    end
    mutations["#{name} unpinned"] = ->(v) { one_step(v[:worker]["jobs"]["run"], name)["uses"] = "actions/setup-java@main" }
end
{"persist-credentials" => true, "ref" => "other"}.each do |key, value|
    mutations["checkout #{key}"] = ->(v) { one_step(v[:worker]["jobs"]["run"], CHECKOUT)["with"][key] = value }
end
mutations["shared home"] = ->(v) { one_step(v[:worker]["jobs"]["run"], HOME)["run"] = HOME_COMMAND.sub("$RUNNER_TEMP", "$HOME") }
mutations["cache write on PR"] = ->(v) { one_step(v[:worker]["jobs"]["run"], CACHE)["with"]["cache-read-only"] = false }
EXCLUDES.lines.map(&:strip).each do |exclusion|
    mutations["missing cache exclusion #{exclusion}"] = ->(v) { one_step(v[:worker]["jobs"]["run"], CACHE)["with"]["gradle-home-cache-excludes"].sub!(exclusion + "\n", "") }
end
{
    "ignored component failure" => EXECUTION + "\nanything || true\n",
    "disabled shell errexit" => "set +e\n" + EXECUTION,
    "echo instead of invocation" => EXECUTION.gsub("python3 -B", "echo python3 -B"),
    "early success" => "exit 0\n" + EXECUTION,
    "changed terminal budget" => EXECUTION.sub('== 120', '== 360'),
    "POM diagnostic bypasses Terminal context" => EXECUTION.sub(' || "$COMPONENT" == consumers-pom-diagnostic', ''),
    "changed POM diagnostic budget" => EXECUTION.sub('[[ "$MINUTES" == 60 ]]', '[[ "$MINUTES" == 120 ]]'),
}.each do |label, command|
    mutations[label] = ->(v) { one_step(v[:worker]["jobs"]["run"], EXECUTE)["run"] = command }
end
mutations.each do |label, mutate|
    changed = Marshal.load(Marshal.dump(inputs))
    mutate.call(changed)
    rejected = false
    begin
        check_policy(changed)
    rescue KeyError, RuntimeError, ArgumentError
        rejected = true
    end
    raise "negative control accepted: #{label}" unless rejected
end
puts "RESULT: PASS — modular owned-JDK/cache/source policy and #{mutations.size} negative controls (no native execution claim)"
