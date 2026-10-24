#!/usr/bin/env ruby
require 'minitest/autorun'
require 'tmpdir'
require 'fileutils'
require_relative '../check-modular-ci-policy'
class ModularPolicyTests < Minitest::Test
  ROOT = File.expand_path('../..', __dir__)
  def altered(relative, before, after)
    Dir.mktmpdir('modular-policy-') do |dir|
      FileUtils.mkdir_p(File.join(dir, '.github'))
      FileUtils.cp_r(File.join(ROOT, '.github/workflows'), File.join(dir, '.github/workflows'))
      path = File.join(dir, relative)
      old = File.read(path)
      raise 'missing mutation input' unless old.include?(before)
      File.write(path, old.sub(before, after))
      assert_raises(ArgumentError) { ModularCI.check(dir) }
    end
  end
  def test_actual_contract
    assert ModularCI.check(ROOT)
  end
  def test_bundle_diagnostic_requires_explicit_choice
    altered('.github/workflows/ci.yml', ', bundle-diagnostic,', ',')
  end
  def test_jmdns_diagnostic_requires_choice_and_excludes_qualification
    altered('.github/workflows/ci.yml', ', jmdns-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'jmdns-diagnostic' && inputs.component", 'inputs.component')
    altered('.github/workflows/ci.yml', "inputs.component != 'jmdns-diagnostic' && inputs.component != 'bundle-diagnostic' && (github.event_name",
            "inputs.component != 'bundle-diagnostic' && (github.event_name")
  end
  def test_bundle_diagnostic_cannot_aggregate
    altered('.github/workflows/ci.yml', "inputs.component != 'bundle-diagnostic' && needs.plan.result",
            'needs.plan.result')
  end
  def test_bundle_diagnostic_cannot_complete_gate
    altered('.github/workflows/ci.yml', "inputs.component != 'bundle-diagnostic' && (github.event_name",
            '(github.event_name')
  end
  def test_shared_checks_remain_independently_required
    altered('.github/workflows/ci.yml', ', macos-shared,', ',')
  end
  def test_pom_diagnostic_remains_explicit_and_cannot_qualify
    altered('.github/workflows/ci.yml', ', consumers-pom-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'consumers-pom-diagnostic' && inputs.component", 'inputs.component')
    altered('.github/workflows/ci.yml', ', apple-keyboard-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'apple-keyboard-diagnostic' && inputs.component", 'inputs.component')
  end
  def test_keyboard_query_diagnostic_requires_choice_and_cannot_qualify
    altered('.github/workflows/ci.yml', ', apple-keyboard-query-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'apple-keyboard-query-diagnostic' && inputs.component", 'inputs.component')
    altered('.github/workflows/ci.yml', ', apple-keyboard-reflow-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'apple-keyboard-reflow-diagnostic' && inputs.component", 'inputs.component')
    altered('.github/workflows/ci.yml', ', apple-keyboard-reproduction-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'apple-keyboard-reproduction-diagnostic' && inputs.component", 'inputs.component')
  end
  def test_published_consumer_diagnostic_requires_choice_and_cannot_qualify
    altered('.github/workflows/ci.yml', ', published-consumers-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'published-consumers-diagnostic' && inputs.component", 'inputs.component')
    altered('.github/workflows/ci.yml', "  complete-gate:\n    needs: [qualify]\n    if: ${{ always() && inputs.component != 'android-legacy-task-preview' && inputs.component != 'apple-issue-diagnostic' && inputs.component != 'android-permission-diagnostic' && inputs.component != 'android-ui-diagnostic' && inputs.component != 'published-consumers-diagnostic' && inputs.component",
            "  complete-gate:\n    needs: [qualify]\n    if: ${{ always() && inputs.component != 'android-legacy-task-preview' && inputs.component != 'apple-issue-diagnostic' && inputs.component != 'android-permission-diagnostic' && inputs.component != 'android-ui-diagnostic' && inputs.component")
  end
  def test_workflow_diagnostics_cannot_launch_matrix_or_qualify
    %w[apple-issue-diagnostic android-ui-diagnostic android-permission-diagnostic android-legacy-task-preview].each do |name|
      %w[plan component qualify complete-gate].each do |stage|
        original = File.read(File.join(ROOT, '.github/workflows/ci.yml'))
        section = original[/^  #{stage}:\n.*?(?=^  [a-z]|\z)/m]
        altered('.github/workflows/ci.yml', section,
                section.sub("inputs.component != '#{name}'", 'true'))
      end
    end
  end
  def test_workflow_diagnostics_remain_bounded_manual_same_source_and_read_only
    %w[apple-issue-diagnostic android-ui-diagnostic android-permission-diagnostic android-legacy-task-preview].each do |name|
      altered('.github/workflows/ci.yml',
              "github.event_name == 'workflow_dispatch' && inputs.component == '#{name}'",
              "inputs.component == '#{name}'")
      original = File.read(File.join(ROOT, '.github/workflows/ci.yml'))
      section = original[/^  #{name}:\n.*?(?=^  [a-z]|\z)/m]
      ['contents: write', "contents: read\n      actions: write"].each do |permissions|
        altered('.github/workflows/ci.yml', section, section.sub('contents: read', permissions))
      end
      altered('.github/workflows/ci.yml', section, section + "    secrets: inherit\n")
      altered('.github/workflows/ci.yml', section, section.sub('./.github/workflows/', 'other/repo/.github/workflows/'))
    end
    altered('.github/workflows/ci.yml', 'options: [both, iphoneos-product, swift-jvm-transfer]',
            'options: [both, iphoneos-product, swift-jvm-transfer, arbitrary]')
    altered('.github/workflows/ci.yml', "options: [both, '317', '324']", "options: [both, '317', '324', '372']")
    altered('.github/workflows/ci.yml', 'default: both', 'default: iphoneos-product')
    altered('.github/workflows/ci.yml', 'uses: ./.github/workflows/android-permission-validation.yml',
            "uses: ./.github/workflows/android-permission-validation.yml\n    with:\n      command: arbitrary")
  end
  def test_complete_consumers_remain_independently_required
    altered('.github/workflows/ci.yml', ', consumers,', ',')
  end

  def test_legacy_api_choice_and_direct_forward_contract_accepted
    ci = ModularCI.load(File.join(ROOT, '.github/workflows/ci.yml'))
    triggers = ci.fetch('on') { ci.fetch(true) }
    selector = triggers.dig('workflow_dispatch', 'inputs', 'android_legacy_api')
    assert_equal %w[both 24 32], selector.fetch('options')
    assert_equal 'both', selector.fetch('default')
    assert_equal({'api' => '${{ inputs.android_legacy_api }}'}, ci.dig('jobs', 'android-legacy-task-preview', 'with'))
    assert ModularCI.check(ROOT)
  end
  def test_legacy_api_input_cannot_be_missing_unbounded_or_redefaulted
    path = '.github/workflows/ci.yml'
    original = File.read(File.join(ROOT, path))
    section = original[/^      android_legacy_api:\n.*?(?=^      [a-z]|\z)/m]
    assert section
    ['', section.sub('type: choice', 'type: string'), section.sub('default: both', "default: '24'"),
     *["[both, '24']", "[both, '32']", "['24', '32']", "[both, '24', '32', '35']"].map { |options|
       section.sub("[both, '24', '32']", options)
     }].each do |replacement|
      error = altered(path, section, replacement)
      assert_match(/Issue diagnostic selector must remain bounded/, error.message)
    end
  end
  def test_legacy_api_forwarding_cannot_be_missing_changed_or_silently_defaulted
    original = "    with:\n      api: ${{ inputs.android_legacy_api }}\n"
    ['', original.sub('api:', 'command:'), original.sub('inputs.android_legacy_api', 'inputs.android_case'),
     original.sub('${{ inputs.android_legacy_api }}', 'both'),
     original.sub('${{ inputs.android_legacy_api }}', "${{ inputs.android_legacy_api || 'both' }}"),
     original + "      command: arbitrary\n"].each do |replacement|
      error = altered('.github/workflows/ci.yml', original, replacement)
      assert_match(/Issue diagnostic must remain explicit, same-source/, error.message)
    end
  end

  def test_publisher_remote_consumers_cannot_revert_to_unqualified_cli_context
    altered('.github/workflows/publish-maven-central.yml',
            "          python3 -I -B -S scripts/run-published-consumers.py\n", "          scripts/check-published-consumers.sh\n")
  end
  def test_publisher_http_requires_original_job_clock_before_each_stage
    path = '.github/workflows/publish-maven-central.yml'
    original = File.read(File.join(ROOT, path))
    ['Revalidate approved release and credentials', 'Upload once and wait for publication',
     'Verify immutable remote bytes and consumers'].each do |name|
      section = original[/^      - name: #{Regexp.escape(name)}\n.*?(?=^      - name:|\z)/m]
      clock = section.lines.find { |line| line.include?('--http-deadline ') }
      altered(path, section, section.sub(clock, ''))
      altered(path, section, section.sub('export P2PKIT_CENTRAL_JOB_DEADLINE', 'true'))
      altered(path, section, section.sub('GH_TOKEN: ${{ github.token }}', 'GH_TOKEN: literal'))
      altered(path, section, section.sub(clock, clock.sub('--http-deadline ', '--not-a-clock ')))
    end
    altered(path, 'timeout-minutes: 150', 'timeout-minutes: 120')
  end
  def test_writer_cannot_select_floating_or_native_toolchain_baseline
    altered('.github/workflows/dependency-update-candidate.yml', 'runs-on: macos-15-intel', 'runs-on: macos-latest')
    altered('.github/workflows/dependency-update-candidate.yml', 'setup-ci-component.sh dependency-update',
            'setup-ci-component.sh dependencies')
  end
  def test_publication_and_recovery_require_supported_complete_consumer_context
    %w[publish-maven-central recover-maven-central].each do |workflow|
      path = ".github/workflows/#{workflow}.yml"
      altered(path, 'runs-on: macos-15-intel', 'runs-on: macos-26')
      altered(path, 'run: bash scripts/setup-ci-component.sh consumers', 'run: true')
      altered(path, 'java-version: "21"', 'java-version: "17"')
      step = workflow == 'publish-maven-central' ? 'Verify immutable remote bytes and consumers' :
                                                  'Verify complete remote consumers without republishing'
      altered(path, "- name: #{step}", "- name: #{step}\n        continue-on-error: true")
    end
  end
  def test_publisher_keeps_original_three_job_recovery_contract
    altered('.github/workflows/publish-maven-central.yml', '  publish-release:', '  different-publication:')
  end
  def test_component_failure_not_masked
    altered('.github/workflows/ci-component.yml', 'id: execution', "id: execution\n        continue-on-error: true")
  end
  def test_no_cross_component_cancel
    altered('.github/workflows/ci.yml', 'fail-fast: false', 'fail-fast: true')
  end
  def test_no_missing_qualification
    altered('.github/workflows/ci.yml', 'test "$QUALIFICATION" = success', 'true')
  end
  def test_recipient_is_independently_pinned
    altered('.github/workflows/ci-component.yml', 'vars.CI_EVIDENCE_RECIPIENT_SHA256', 'inputs.recipient')
  end
  def test_no_overwritten_evidence
    altered('.github/workflows/ci-component.yml', 'overwrite: false', 'overwrite: true')
  end
  def test_no_trusted_cache_writes_by_pr
    altered('.github/workflows/ci-component.yml', "cache-read-only: ${{ github.ref != 'refs/heads/main' }}", 'cache-read-only: false')
  end
end
