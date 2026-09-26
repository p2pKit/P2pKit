#!/usr/bin/env ruby
# Source-only topology controls; never starts a job, build or publication.
require 'json'
require 'yaml'

ROOT = File.expand_path('../..', __dir__)
READ = {'contents' => 'read', 'actions' => 'read', 'checks' => 'read',
        'pull-requests' => 'read', 'deployments' => 'read'}.freeze

def need(value, message)
  raise message unless value
end

def event(workflow)
  workflow.fetch('on') { workflow.fetch(true) }
end

def step(job, name)
  rows = job.fetch('steps').select { |s| s['name'] == name }
  need(rows.size == 1, "missing/duplicate step #{name}")
  rows.first
end

def validate(maven, samples)
  need(event(maven) == {'push' => {'tags' => ['v*']}}, 'Maven must stay exact tag-push only')
  need(maven['permissions'] == READ, 'Maven permission surface changed')
  jobs = maven.fetch('jobs')
  need(jobs.keys.sort == %w[freeze-applications publish-release verify-release], 'Maven stages differ')
  freeze, verify, publish = jobs.values_at('freeze-applications', 'verify-release', 'publish-release')
  need(freeze['timeout-minutes'] == 20 && !freeze.key?('environment') &&
       !JSON.generate(freeze).include?('secrets.'), 'freeze must be bounded and secret-free')
  need(step(freeze, 'Freeze the exact qualified main application and evidence set')['run'] ==
       'python3 -I -B -S scripts/release_application_set.py freeze', 'missing pre-Maven application freeze')
  upload = step(freeze, 'Retain the immutable public application-set record').fetch('with')
  need(upload['name'] == 'release-application-set-${{ github.run_id }}-${{ github.run_attempt }}' &&
       upload['path'] == '${{ runner.temp }}/p2pkit-release-application-set/release-application-set.json' &&
       upload['retention-days'] == 14 && upload['overwrite'] == false && upload['if-no-files-found'] == 'error',
       'frozen upload must be exact-attempt immutable public JSON')
  need(verify['needs'] == 'freeze-applications' &&
       step(verify, 'Run complete release gate')['run'] == 'scripts/run-release-gate.sh', 'verification gate omitted')
  need(publish['needs'] == %w[freeze-applications verify-release] &&
       publish['timeout-minutes'] == 90 && publish.fetch('environment')['name'] == 'maven-central',
       'protected Maven dependencies or budget changed')
  secret_steps = publish.fetch('steps').select { |s| JSON.generate(s).include?('secrets.') }.map { |s| s['name'] }
  need(secret_steps == ['Revalidate approved release and credentials', 'Build and inspect signed Central bundle',
                       'Upload once and wait for publication'], 'Maven signing/Portal credentials escaped their steps')
  names = publish.fetch('steps').map { |s| s['name'] }
  before = 'Revalidate frozen applications and exact owner approval'
  last = 'Revalidate original readiness immediately before irreversible upload'
  need(names.index(before) < names.index('Revalidate approved release and credentials') &&
       names.index(last) + 1 == names.index('Upload once and wait for publication'), 'readiness/approval revalidation misplaced')
  [before, last].each do |name|
    value = step(publish, name)
    need(value['run'] == 'python3 -I -B -S scripts/release_application_set.py revalidate --artifact "$FROZEN_ARTIFACT" --sha256 "$FROZEN_SHA256"' &&
         value.fetch('env')['FROZEN_ARTIFACT'] == '${{ needs.freeze-applications.outputs.artifact_id }}' &&
         value.fetch('env')['FROZEN_SHA256'] == '${{ needs.freeze-applications.outputs.sha256 }}',
         'Maven must revalidate the original freeze outputs, not another set')
  end
  need(step(publish, 'Verify immutable remote bytes and consumers').fetch('run').include?('scripts/check-maven-central-version.sh published') &&
       step(publish, 'Generate and verify publication-build SBOM').fetch('run').include?('scripts/check-sbom.sh'),
       'existing publication/remote/SBOM gate removed')

  need(event(samples).fetch('workflow_run') == {'workflows' => ['Publish Maven Central'], 'types' => ['completed']},
       'apps may be delivered automatically only after Maven completion')
  inputs = event(samples).fetch('workflow_dispatch').fetch('inputs')
  need(inputs.keys.sort == %w[frozen_artifact frozen_sha256 maven_attempt maven_run operation source_sha] &&
       inputs.values.all? { |x| x['required'] == true }, 'manual resume must bind the complete original identity')
  need(inputs.fetch('operation')['options'] == %w[verify publish], 'manual path must not rebuild or republish Maven')
  need(samples['permissions'] == READ && samples.fetch('concurrency')['cancel-in-progress'] == false,
       'sample default permissions/cancellation changed')
  sample_jobs = samples.fetch('jobs')
  need(sample_jobs.keys.sort == %w[admit prepare-review publish verify-only], 'sample stage graph differs')
  mutating = sample_jobs.fetch('publish')
  need(mutating['needs'] == %w[admit prepare-review] && mutating['environment'] == 'sample-development-release' &&
       mutating['permissions'] == READ.merge('contents' => 'write'), 'sample publication bypasses evidence approval')
  need(sample_jobs.reject { |k, _| k == 'publish' }.values.none? { |j| j.key?('environment') || j.key?('permissions') },
       'unapproved sample job has a protected environment or permission override')
  commands = sample_jobs.values.flat_map { |j| j.fetch('steps') }.map { |s| s.fetch('run', '') }
  need(commands.none? { |s| s.match?(/gradlew|sdkmanager|xcodebuild|publish-central-portal-bundle/) }, 'delivery must not rebuild or upload Maven')
  commands.grep(/scripts\/publish-sample-release.py (?!cleanup)/).each do |command|
    need(command.include?('--maven-run "$MAVEN_RUN" --maven-attempt "$MAVEN_ATTEMPT" --frozen-artifact "$FROZEN_ARTIFACT" --frozen-sha256 "$FROZEN_SHA256"'),
         'sample operation lost its original Maven/frozen binding')
  end
  [maven, samples].each do |workflow|
    workflow.fetch('jobs').each_value do |job|
      need(!job.key?('continue-on-error'), 'job failure must remain fatal')
      job.fetch('steps').each do |s|
        need(!s.key?('continue-on-error'), 'step failure must remain fatal')
        need(s.fetch('uses').match?(/@[0-9a-f]{40}\z/), 'unpinned action') if s.key?('uses')
      end
    end
  end
end

maven = YAML.safe_load(File.read(File.join(ROOT, '.github/workflows/publish-maven-central.yml')), aliases: true)
samples = YAML.safe_load(File.read(File.join(ROOT, '.github/workflows/sample-development-releases.yml')), aliases: true)
validate(maven, samples)
controls = [
  ->(m, _) { m['jobs']['publish-release']['needs'] = ['verify-release'] },
  ->(m, _) { m['jobs']['verify-release']['needs'] = [] },
  ->(m, _) { m['jobs']['freeze-applications']['environment'] = 'maven-central' },
  ->(m, _) { m['jobs']['publish-release']['environment']['name'] = 'unprotected' },
  ->(m, _) { step(m['jobs']['freeze-applications'], 'Retain the immutable public application-set record')['with']['overwrite'] = true },
  ->(m, _) { step(m['jobs']['publish-release'], 'Revalidate original readiness immediately before irreversible upload')['run'] = 'true' },
  ->(_, s) { event(s)['workflow_run']['workflows'] << 'Desktop cross-host' },
  ->(_, s) { event(s)['workflow_dispatch']['inputs'].delete('frozen_sha256') },
  ->(_, s) { s['jobs']['publish']['needs'] = ['admit'] },
  ->(_, s) { s['jobs']['publish']['environment'] = nil },
  ->(_, s) { s['jobs']['prepare-review']['permissions'] = {'contents' => 'write'} },
  ->(_, s) { s['jobs']['publish']['steps'].last['continue-on-error'] = true },
]
controls.each_with_index do |change, index|
  copies = Marshal.load(Marshal.dump([maven, samples]))
  change.call(*copies)
  rejected = false
  begin
    validate(*copies)
  rescue StandardError
    rejected = true
  end
  need(rejected, "negative topology control #{index + 1} was accepted")
end
puts "PASS: maintained workflow topology and #{controls.size} negative controls (source only)"
