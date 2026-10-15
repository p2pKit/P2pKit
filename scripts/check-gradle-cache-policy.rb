#!/usr/bin/env ruby
# Kotlin's build-cache exception permits dependency caches, not persisted task
# output metadata. Inspect YAML values per action, not their inline/block style.
require "yaml"

module GradleCachePolicy
    REQUIRED_EXCLUSION = "caches/build-cache-1"

    def self.inspect_workflow(workflow, path)
        errors = []
        count = 0
        jobs = workflow.fetch("jobs")
        raise TypeError, "jobs must be a mapping" unless jobs.is_a?(Hash)
        jobs.each do |job_name, job|
            raise TypeError, "job must be a mapping" unless job.is_a?(Hash)
            steps = job.fetch("steps", [])
            raise TypeError, "steps must be an array" unless steps.is_a?(Array)
            steps.each_with_index do |step, index|
                raise TypeError, "step must be a mapping" unless step.is_a?(Hash)
                action = step["uses"]
                next unless action.is_a?(String) &&
                    action.match?(/\Agradle\/actions\/(setup-gradle|dependency-submission)@/i)

                count += 1
                inputs = step["with"]
                value = inputs.is_a?(Hash) ? inputs["gradle-home-cache-excludes"] : nil
                exclusions = value.is_a?(String) ? value.lines.map(&:strip).reject(&:empty?) : []
                # Expressions cannot prove a fixed exclusion, and negated globs
                # could re-include the vulnerable cache after excluding it.
                next if exclusions.include?(REQUIRED_EXCLUSION) &&
                    !value.include?("${{") && exclusions.none? { |line| line.start_with?("!") }

                errors << "#{path}: jobs.#{job_name}.steps[#{index + 1}] must set " \
                    "with.gradle-home-cache-excludes to include the exact #{REQUIRED_EXCLUSION} line " \
                    "without expressions or negated patterns"
            end
        end
        [count, errors]
    end

    def self.check(paths)
        count = 0
        errors = []
        paths.each do |path|
            begin
                workflow = YAML.safe_load(File.read(path), aliases: true)
                found, violations = inspect_workflow(workflow, path)
                count += found
                errors.concat(violations)
            rescue Psych::Exception, KeyError, TypeError, NoMethodError, SystemCallError => error
                errors << "#{path}: cannot inspect workflow: #{error.message}"
            end
        end
        errors << "no Gradle workflow cache policy was inspected" if count.zero?
        errors
    end
end

if $PROGRAM_NAME == __FILE__
    paths = ARGV.empty? ? Dir[File.expand_path("../.github/workflows/*.{yml,yaml}", __dir__)].sort : ARGV
    errors = GradleCachePolicy.check(paths)
    abort errors.map { |error| "FATAL: #{error}" }.join("\n") unless errors.empty?
    puts "RESULT: PASS — every Gradle action excludes persisted build-cache metadata"
end
