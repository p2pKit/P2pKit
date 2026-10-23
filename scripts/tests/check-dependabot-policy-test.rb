#!/usr/bin/env ruby
require 'minitest/autorun'
require 'yaml'

class DependabotPolicyTests < Minitest::Test
    ROOT = File.expand_path('../..', __dir__)
    ECOSYSTEMS = %w[github-actions gradle].freeze

    def setup
        @config = YAML.safe_load(File.read(File.join(ROOT, '.github/dependabot.yml')))
        @updates = @config.fetch('updates')
    end

    def test_reviewed_ecosystems_and_schedules_are_retained
        assert_equal %w[updates version], @config.keys.sort
        assert_instance_of Integer, @config.fetch('version')
        assert_equal 2, @config.fetch('version')
        assert_instance_of Array, @updates
        assert_equal ECOSYSTEMS, @updates.map { |update| update.fetch('package-ecosystem') }.sort
        @updates.each do |update|
            assert_equal '/', update.fetch('directory')
            assert_equal({ 'interval' => 'weekly' }, update.fetch('schedule'))
        end
    end

    def test_every_version_update_generator_has_an_explicit_integer_zero_limit
        @updates.each do |update|
            ecosystem = update.fetch('package-ecosystem')
            limit = update.fetch('open-pull-requests-limit')
            assert_instance_of Integer, limit, "#{ecosystem}: the pause must use an integer limit"
            assert_equal 0, limit, "#{ecosystem}: automatic version PRs must remain paused"
        end
    end

    def test_automatic_rebasing_is_disabled_for_every_ecosystem
        @updates.each do |update|
            assert_equal 'disabled', update.fetch('rebase-strategy'),
                         "#{update.fetch('package-ecosystem')}: automatic rebasing must remain disabled"
        end
    end

    def test_android_gradle_toolchain_remains_one_compatibility_unit
        gradle = @updates.find { |update| update.fetch('package-ecosystem') == 'gradle' }
        assert_equal({
            'android-gradle-toolchain' => { 'patterns' => %w[agp gradle-wrapper] }
        }, gradle.fetch('groups'))
    end

    def test_pause_does_not_add_ignore_rules_or_change_update_scope
        @updates.each do |update|
            expected = %w[directory open-pull-requests-limit package-ecosystem rebase-strategy schedule]
            expected << 'groups' if update.fetch('package-ecosystem') == 'gradle'
            assert_equal expected.sort, update.keys.sort
        end
    end
end
