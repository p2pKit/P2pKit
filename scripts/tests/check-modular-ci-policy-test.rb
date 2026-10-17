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
    altered('.github/workflows/ci.yml', ', consumers-pom-diagnostic]', ']')
    altered('.github/workflows/ci.yml', "inputs.component != 'consumers-pom-diagnostic' && inputs.component", 'inputs.component')
  end
  def test_published_consumer_diagnostic_requires_choice_and_cannot_qualify
    altered('.github/workflows/ci.yml', ', published-consumers-diagnostic,', ',')
    altered('.github/workflows/ci.yml', "inputs.component != 'published-consumers-diagnostic' && inputs.component", 'inputs.component')
    altered('.github/workflows/ci.yml', "  complete-gate:\n    needs: [qualify]\n    if: ${{ always() && inputs.component != 'published-consumers-diagnostic' && inputs.component",
            "  complete-gate:\n    needs: [qualify]\n    if: ${{ always() && inputs.component")
  end
  def test_complete_consumers_remain_independently_required
    altered('.github/workflows/ci.yml', ', consumers,', ',')
  end

  def test_publisher_remote_consumers_cannot_revert_to_unqualified_cli_context
    altered('.github/workflows/publish-maven-central.yml',
            'python3 -I -B -S scripts/run-published-consumers.py', 'scripts/check-published-consumers.sh')
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
