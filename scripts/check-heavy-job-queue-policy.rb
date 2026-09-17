#!/usr/bin/env ruby
# Focused GitHub concurrency schema/policy, not a replacement for actionlint.
# queue:max is documented by GitHub, but actionlint 1.7.12 cannot parse it.
require "yaml"

module HeavyJobQueuePolicy
    class Error < StandardError; end

    GROUP = "p2pkit-nonphysical-heavy"
    QUEUE = {"group" => GROUP, "queue" => "max", "cancel-in-progress" => false}.freeze
    JOBS = {
        "ci.yml" => {"jvm-library-checks" => "JVM libraries (${{ matrix.os }})", "complete-gate" => nil},
        "desktop-cross-host.yml" => {"verify" => "${{ matrix.os }}", "windows-directory-fsync-control" => "windows-directory-fsync-control",
            "windows-helper-controls" => "windows-helper-controls", "mac-host-admission-probe" => "mac-host-admission-probe", "dependency-lock-candidate" => "dependency-lock-candidate", "iphoneos-product" => "iphoneos-product"},
        "ios-x64-tests.yml" => {"ios-x64" => nil},
        "dependency-submission.yml" => {"submit" => nil},
    }.freeze
    # Separate workflow groups prevent a workflow holding the lease its jobs
    # need. Retain ordinary supersession and CI's independent scheduled backstop.
    WORKFLOW_CONCURRENCY = {
        "ci.yml" => {
            "group" => "ci-${{ github.workflow }}-${{ github.ref }}-${{ github.event_name == 'schedule' && 'schedule' || 'change' }}",
            "cancel-in-progress" => "${{ github.event_name != 'schedule' }}",
        },
        "desktop-cross-host.yml" => {
            "group" => "desktop-cross-host-${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'iphoneos-product' && format('iphoneos-{0}-{1}', github.run_id, github.run_attempt) || github.event_name == 'workflow_dispatch' && (inputs.operation == 'dependency-lock-candidate' || inputs.operation == 'dependency-lock-candidate-x64' || inputs.operation == 'dependency-lock-candidate-macos14') && format('lock-{0}-{1}', github.run_id, github.run_attempt) || github.event_name == 'workflow_dispatch' && (inputs.operation == 'windows-directory-fsync-control' || inputs.operation == 'windows-helper-controls' || inputs.operation == 'macos-arm64-admission' || inputs.operation == 'macos-x64-admission') && format('control-{0}-{1}', github.run_id, github.run_attempt) || github.ref }}",
            "cancel-in-progress" => "${{ github.event_name != 'workflow_dispatch' || (inputs.operation != 'windows-directory-fsync-control' && inputs.operation != 'windows-helper-controls' && inputs.operation != 'macos-arm64-admission' && inputs.operation != 'macos-x64-admission' && inputs.operation != 'dependency-lock-candidate' && inputs.operation != 'dependency-lock-candidate-x64' && inputs.operation != 'dependency-lock-candidate-macos14' && inputs.operation != 'iphoneos-product') }}",
        },
        "ios-x64-tests.yml" => {"group" => "ios-x64-tests-${{ github.ref }}", "cancel-in-progress" => false},
    }.freeze
    MATRICES = {
        ["ci.yml", "jvm-library-checks"] => {"include" => [
            {"os" => "ubuntu-latest", "wrapper" => "./gradlew"},
            {"os" => "windows-latest", "wrapper" => '.\gradlew.bat'},
        ]},
        ["desktop-cross-host.yml", "verify"] => {"os" => %w[ubuntu-latest windows-latest macos-15]},
    }.freeze
    CONDITIONS = {
        ["ci.yml", "complete-gate"] => "${{ always() }}",
        ["desktop-cross-host.yml", "verify"] => "${{ github.event_name != 'workflow_dispatch' || (inputs.operation != 'windows-directory-fsync-control' && inputs.operation != 'windows-helper-controls' && inputs.operation != 'macos-arm64-admission' && inputs.operation != 'macos-x64-admission' && inputs.operation != 'dependency-lock-candidate' && inputs.operation != 'dependency-lock-candidate-x64' && inputs.operation != 'dependency-lock-candidate-macos14' && inputs.operation != 'iphoneos-product') }}",
        ["desktop-cross-host.yml", "windows-directory-fsync-control"] => "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'windows-directory-fsync-control' }}",
        ["desktop-cross-host.yml", "windows-helper-controls"] => "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'windows-helper-controls' }}",
        ["desktop-cross-host.yml", "mac-host-admission-probe"] => "${{ github.event_name == 'workflow_dispatch' && (inputs.operation == 'macos-arm64-admission' || inputs.operation == 'macos-x64-admission') }}",
        ["desktop-cross-host.yml", "dependency-lock-candidate"] => "${{ github.event_name == 'workflow_dispatch' && (inputs.operation == 'dependency-lock-candidate' || inputs.operation == 'dependency-lock-candidate-x64' || inputs.operation == 'dependency-lock-candidate-macos14') }}",
        ["desktop-cross-host.yml", "iphoneos-product"] => "${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'iphoneos-product' }}",
    }.freeze

    def self.require_policy(condition, message)
        raise Error, message unless condition
    end

    def self.check_yaml_keys(node, path)
        if node.is_a?(Psych::Nodes::Mapping)
            keys = node.children.each_slice(2).map(&:first)
            require_policy(keys.all? { |key| key.is_a?(Psych::Nodes::Scalar) }, "#{path}: non-scalar YAML key")
            names = keys.map(&:value)
            require_policy(names.uniq == names, "#{path}: duplicate YAML key")
            require_policy(!names.include?("<<"), "#{path}: YAML merge overrides are not admitted")
        end
        Array(node.children).each { |child| check_yaml_keys(child, path) }
    end

    def self.parse(text, path)
        stream = YAML.parse_stream(text)
        require_policy(stream.children.size == 1, "#{path}: expected one YAML document")
        check_yaml_keys(stream, path)
        workflow = YAML.safe_load(text, aliases: true)
        require_policy(workflow.is_a?(Hash) && workflow["jobs"].is_a?(Hash), "#{path}: expected workflow/jobs mappings")
        workflow
    rescue Psych::Exception => error
        raise Error, "#{path}: invalid YAML: #{error.message}"
    end

    def self.read_workflows(directory)
        Dir[File.join(directory, "*.{yml,yaml}")].sort.to_h do |path|
            require_policy(File.file?(path) && !File.symlink?(path), "#{path}: expected a regular workflow file")
            [File.basename(path), parse(File.read(path), path)]
        end
    end

    def self.check(workflows)
        JOBS.each do |path, expected_jobs|
            workflow = workflows[path]
            require_policy(workflow.is_a?(Hash), "#{path}: missing participating workflow")
            expected_concurrency = WORKFLOW_CONCURRENCY[path]
            require_policy(expected_concurrency ? workflow["concurrency"] == expected_concurrency :
                !workflow.key?("concurrency"), "#{path}: preserve separate workflow concurrency/supersession")
            jobs = workflow["jobs"]
            require_policy(jobs.is_a?(Hash) && jobs.keys.sort == expected_jobs.keys.sort,
                           "#{path}: participating job IDs changed; review queue coverage")
            expected_jobs.each do |id, name|
                job = jobs[id]
                label = "#{path}: jobs.#{id}"
                require_policy(job.is_a?(Hash) && job["concurrency"] == QUEUE,
                               "#{label}: require exact job-level group, queue:max and boolean cancel-in-progress:false")
                require_policy(name ? job["name"] == name : !job.key?("name"), "#{label}: preserve job/check name")
                dependent = path == "ci.yml" && id == "complete-gate"
                require_policy(dependent ? job["needs"] == "jvm-library-checks" : !job.key?("needs"),
                               "#{label}: preserve acyclic job dependencies")
                condition = CONDITIONS[[path, id]]
                require_policy(condition ? job["if"] == condition : !job.key?("if"),
                               "#{label}: preserve unconditional jobs/required-gate guard")
                require_policy(!job.key?("continue-on-error"), "#{label}: failures must remain blocking")
                matrix = MATRICES[[path, id]]
                if matrix
                    strategy = job["strategy"]
                    require_policy(strategy.is_a?(Hash) && strategy.keys.sort == %w[fail-fast matrix max-parallel] &&
                        strategy["max-parallel"].is_a?(Integer) && strategy["max-parallel"] == 1 &&
                        strategy["fail-fast"] == false && strategy["matrix"] == matrix &&
                        job["runs-on"] == "${{ matrix.os }}", "#{label}: require unchanged native matrix, fail-fast:false, max-parallel:1")
                else
                    require_policy(!job.key?("strategy"), "#{label}: unexpected matrix/strategy")
                end
            end
        end

        # Other workflows are not participants. Prevent literal/case-insensitive
        # reuse of this reserved group, including at workflow level (deadlock).
        workflows.each do |path, workflow|
            scopes = [[nil, workflow["concurrency"]]]
            workflow.fetch("jobs").each do |id, job|
                require_policy(job.is_a?(Hash), "#{path}: jobs.#{id} must be a mapping")
                scopes << [id, job["concurrency"]]
            end
            scopes.each do |scope, concurrency|
                next if JOBS.fetch(path, {}).key?(scope)
                group = concurrency.is_a?(Hash) ? concurrency["group"] : concurrency
                require_policy(!group.is_a?(String) || !group.downcase.include?(GROUP),
                               "#{path}: #{scope || 'workflow'} cannot acquire the reserved participating-job group")
            end
        end
    end
end

if $PROGRAM_NAME == __FILE__
    abort "Usage: #{$PROGRAM_NAME} [workflow-directory]" if ARGV.length > 1
    directory = ARGV.fetch(0, File.expand_path("../.github/workflows", __dir__))
    begin
        HeavyJobQueuePolicy.check(HeavyJobQueuePolicy.read_workflows(directory))
    rescue HeavyJobQueuePolicy::Error, SystemCallError => error
        abort "FATAL: #{error.message}"
    end
    puts "RESULT: PASS — ten participating jobs share the bounded non-cancelling queue; workflow groups remain separate"
end
