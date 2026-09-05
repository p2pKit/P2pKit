#!/usr/bin/env ruby
# Keep checkout's temporary fetch credentials out of subsequent build steps.
require "yaml"

module WorkflowCheckoutPolicy
    def self.violations(workflow, path)
        errors = []
        workflow.fetch("jobs").each do |job_name, job|
            job.fetch("steps", []).each_with_index do |step, index|
                action = step["uses"]
                next unless action.is_a?(String) && action.match?(/\Aactions\/checkout@/i)

                inputs = step["with"]
                next if inputs.is_a?(Hash) && inputs["persist-credentials"] == false

                errors << "#{path}: jobs.#{job_name}.steps[#{index + 1}] " \
                    "must set checkout with.persist-credentials to boolean false"
            end
        end
        errors
    end

    def self.check(paths)
        paths.flat_map do |path|
            workflow = YAML.safe_load(File.read(path), aliases: true)
            violations(workflow, path)
        end
    end
end

if $PROGRAM_NAME == __FILE__
    paths = ARGV.empty? ? Dir[File.expand_path("../.github/workflows/**/*.{yml,yaml}", __dir__)].sort : ARGV
    abort "FATAL: no workflow files found" if paths.empty?
    errors = WorkflowCheckoutPolicy.check(paths)
    abort errors.map { |error| "FATAL: #{error}" }.join("\n") unless errors.empty?
    puts "RESULT: PASS — checkout credential persistence is disabled in every workflow step"
end
