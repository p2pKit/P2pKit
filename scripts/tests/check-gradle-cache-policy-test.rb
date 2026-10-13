#!/usr/bin/env ruby
require "tmpdir"
require "open3"
require "rbconfig"
require_relative "../check-gradle-cache-policy"

CHECKER = File.expand_path("../check-gradle-cache-policy.rb", __dir__)
ACTIONS = %w[setup-gradle dependency-submission].map { |name| "gradle/actions/#{name}@#{'a' * 40}" }
checks = 0

def inspect_steps(steps)
    GradleCachePolicy.inspect_workflow({"jobs" => {"build" => {"steps" => steps}}}, "fixture.yml")
end

def action_step(action, value)
    {"uses" => action, "with" => {"gradle-home-cache-excludes" => value}}
end

ACTIONS.each do |action|
    ["caches/build-cache-1", "caches/build-cache-1\ninit.d\n", "\n init.d\n caches/build-cache-1 \n"].each do |value|
        count, errors = inspect_steps([action_step(action, value)])
        raise "literal exclusion rejected" unless count == 1 && errors.empty?
        checks += 1
    end
    [nil, false, [], {}, "", "init.d", "caches/build-cache-10", "caches/build-cache-1/**",
     "# caches/build-cache-1", "caches/build-cache-1 init.d", "${{ inputs.exclusions }}",
     "caches/build-cache-1\n${{ inputs.more }}", "caches/build-cache-1\n!caches/build-cache-1",
     "!caches/**\ncaches/build-cache-1", "caches/build-cache-1 # not a YAML comment inside a block"].each do |value|
        count, errors = inspect_steps([action_step(action, value)])
        raise "unsafe exclusion accepted: #{value.inspect}" unless count == 1 && errors.length == 1 &&
            errors.first.include?("jobs.build.steps[1]")
        checks += 1
    end
    [nil, [], "gradle-home-cache-excludes: caches/build-cache-1", {}].each do |inputs|
        _, errors = inspect_steps([action_step(action, "caches/build-cache-1"), {"uses" => action, "with" => inputs}])
        raise "previous action's exclusion leaked into next step" unless errors.length == 1 &&
            errors.first.include?("steps[2]")
        checks += 1
    end
    count, errors = inspect_steps([{"uses" => action.upcase}])
    raise "case variant or omitted with accepted" unless count == 1 && errors.length == 1
    checks += 1
end

count, errors = inspect_steps([
    {"run" => "echo gradle/actions/setup-gradle@pin"},
    {"uses" => "example/setup-gradle@pin"}, {"uses" => "gradle/actions/setup-gradle-helper@pin"},
])
raise "non-Gradle actions matched" unless count.zero? && errors.empty?
checks += 1

Dir.mktmpdir("p2pkit-gradle-cache-policy-") do |directory|
    safe = File.join(directory, "safe.yml")
    File.write(safe, <<~YAML)
        on: push
        jobs:
          first:
            steps:
              - &cached
                uses: #{ACTIONS.first}
                with:
                  gradle-home-cache-excludes: |
                    caches/build-cache-1
                    init.d
              - with:
                  gradle-home-cache-excludes: 'caches/build-cache-1' # YAML comment
                uses: #{ACTIONS.last}
          second:
            steps:
              - *cached
          reusable:
            uses: example/repo/.github/workflows/test.yml@#{'a' * 40}
    YAML
    raise "actual block/inline/alias YAML rejected" unless GradleCachePolicy.check([safe]).empty?
    checks += 1

    # Exercise parser semantics, not only already-decoded strings. A neighboring
    # step or run-string/comment must never lend its exclusion to an action.
    mutations = {
        "missing block line" => File.read(safe).sub("            caches/build-cache-1\n", ""),
        "folded two-path scalar" => File.read(safe).sub("excludes: |", "excludes: >"),
        "comment-only inline" => File.read(safe).sub("'caches/build-cache-1'", "# caches/build-cache-1"),
        "wrong step" => <<~YAML,
            jobs:
              build:
                steps:
                  - uses: #{ACTIONS.first}
                  - name: unrelated
                    with:
                      gradle-home-cache-excludes: caches/build-cache-1
                    run: echo unrelated
        YAML
        "run string" => <<~YAML,
            jobs:
              build:
                steps:
                  - run: |
                      gradle-home-cache-excludes: caches/build-cache-1
                  - uses: #{ACTIONS.first}
        YAML
        "invalid YAML" => "jobs: [invalid\n",
        "invalid structure" => "jobs: []\n",
        "invalid job" => "jobs: {build: []}\n",
        "invalid steps" => "jobs: {build: {steps: {}}}\n",
        "invalid step" => "jobs: {build: {steps: [[]]}}\n",
        "no action" => "jobs: {build: {steps: [{run: echo no-gradle}]}}\n",
    }
    mutations.each do |name, source|
        bad = File.join(directory, "bad.yaml")
        File.write(bad, source)
        paths = name == "no action" ? [bad] : [safe, bad]
        stdout, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, *paths)
        raise "CLI accepted #{name}" unless !status.success? && stdout.empty? && stderr.include?("FATAL:")
        checks += 1
    end
    unsafe_alias = File.join(directory, "unsafe-alias.yaml")
    File.write(unsafe_alias, File.read(safe).sub("            caches/build-cache-1\n", ""))
    errors = GradleCachePolicy.check([unsafe_alias])
    raise "later job or alias not checked" unless errors.length == 2 &&
        errors.first.include?("jobs.first.steps[1]") && errors.last.include?("jobs.second.steps[1]")
    checks += 1
    stdout, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, safe)
    raise "CLI rejects safe workflow" unless status.success? && stdout.include?("RESULT: PASS") && stderr.empty?
    checks += 1
    _, stderr, status = Open3.capture3(RbConfig.ruby, CHECKER, File.join(directory, "missing.yml"))
    raise "CLI accepted missing workflow" unless !status.success? && stderr.include?("cannot inspect workflow")
    checks += 1
end

# Keep the new semantic guard and its regressions on the actual failing gate.
outer = File.read(File.expand_path("check-kotlin-toolchain-policy-test.sh", __dir__))
['ruby "$ROOT/scripts/check-gradle-cache-policy.rb"',
 'ruby "$ROOT/scripts/tests/check-gradle-cache-policy-test.rb"'].each do |command|
    raise "outer policy no longer executes #{command}" unless outer.lines.any? { |line| line.strip == command }
    checks += 1
end

puts "RESULT: PASS — #{checks} Gradle cache-policy regression checks"
