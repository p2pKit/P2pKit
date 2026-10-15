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
    altered('.github/workflows/ci.yml', ', bundle-diagnostic]', ']')
  end
  def test_bundle_diagnostic_cannot_aggregate
    altered('.github/workflows/ci.yml', "inputs.component != 'bundle-diagnostic' && needs.plan.result",
            'needs.plan.result')
  end
  def test_bundle_diagnostic_cannot_complete_gate
    altered('.github/workflows/ci.yml', "inputs.component != 'bundle-diagnostic' && (github.event_name",
            '(github.event_name')
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
