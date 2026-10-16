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

def validate(maven, samples, recovery)
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
  signed = 'Retain reviewed signed bundle before Central upload'
  receipt = 'Retain original PUBLISHED deployment receipt'
  need(names.index('Generate and verify publication-build SBOM') < names.index('Validate signed originals before retention') &&
       names.index('Validate signed originals before retention') + 1 == names.index(signed) &&
       names.index(signed) < names.index(last) &&
       names.index('Upload once and wait for publication') + 1 == names.index('Bind original completed Portal publication') &&
       names.index('Bind original completed Portal publication') + 1 == names.index(receipt) &&
       names.index(receipt) + 1 == names.index('Verify immutable remote bytes and consumers'),
       'original bundle/deployment retention must bracket upload and precede fallible remote verification')
  need(step(publish, 'Validate signed originals before retention')['run'].include?('python3 -I -B -S scripts/central_bundle_evidence.py') &&
       step(publish, 'Validate signed originals before retention')['run'].include?('--public-key "$BASE.public.asc"') &&
       step(publish, 'Validate signed originals before retention')['run'].include?('--source-sha "$GITHUB_SHA"'),
       'missing exact signed quartet verification before irreversible publication')
  expected_originals = {
    signed => ['maven-central-signed-bundle-', %w[zip manifest.sha256 summary.json public.asc].map { |suffix|
      '${{ steps.original-bundle.outputs.base }}.' + suffix }],
    receipt => ['maven-central-deployment-', %w[deployment-receipt.json portal-events.jsonl status.json
                                              bundle.sha256 commit-sha.txt deployment-id.txt].map { |f| 'build/reports/maven-central/' + f }],
  }
  expected_originals.each do |name, (prefix, paths)|
    s = step(publish, name)
    need(!s.key?('if') && s.fetch('with')['name'] == prefix + '${{ github.ref_name }}-${{ github.run_id }}-${{ github.run_attempt }}' &&
         s.fetch('with')['path'].lines.map(&:strip).reject(&:empty?) == paths && s.fetch('with')['retention-days'] == 14 &&
         s.fetch('with')['overwrite'] == false && s.fetch('with')['if-no-files-found'] == 'error',
         'original publication evidence must be required, immutable, exact-attempt and finite')
  end
  need(step(publish, 'Bind original completed Portal publication')['run'] ==
       'python3 -I -B -S scripts/central_deployment_evidence.py', 'missing original Portal receipt binding')
  need(step(publish, 'Validate signed originals before retention')['id'] == 'original-bundle' &&
       step(publish, 'Validate signed originals before retention')['run'].include?('echo "base=$BASE" >> "$GITHUB_OUTPUT"'),
       'retention paths must come only from the verified original quartet')

  need(event(samples).fetch('workflow_run') == {
         'workflows' => ['Publish Maven Central', 'Recover Maven Central verification'], 'types' => ['completed']},
       'apps require original Maven success or separately successful read-only recovery')
  inputs = event(samples).fetch('workflow_dispatch').fetch('inputs')
  original_inputs = %w[frozen_artifact frozen_sha256 maven_attempt maven_run operation source_sha]
  recovery_inputs = %w[recovery_artifact recovery_attempt recovery_run recovery_sha256]
  need(inputs.keys.sort == (original_inputs + recovery_inputs).sort &&
       original_inputs.all? { |name| inputs.fetch(name)['required'] == true } &&
       recovery_inputs.all? { |name| inputs.fetch(name)['required'] == false && inputs.fetch(name)['type'] == 'string' },
       'manual resume must bind the original identity and optional complete recovery descriptor')
  need(inputs.fetch('operation')['options'] == %w[verify publish], 'manual path must not rebuild or republish Maven')
  need(samples['permissions'] == READ && samples['concurrency'] == {
         'group' => 'development-samples', 'cancel-in-progress' => false},
       'one writer must serialize original, manual and recovery delivery without cancellation')
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
    need(command.include?('--authority "$AUTHORITY" --recovery-run "$RECOVERY_RUN" --recovery-attempt "$RECOVERY_ATTEMPT" --recovery-artifact "$RECOVERY_ARTIFACT" --recovery-sha256 "$RECOVERY_SHA256"'),
         'sample operation lost its distinct recovery authority binding')
  end
  sample_jobs.each do |name, job|
    operation = job.fetch('steps').select { |s| s.fetch('run', '').match?(/scripts\/publish-sample-release.py (?!cleanup)/) }
    need(operation.size == 1, 'sample stage needs exactly one bound policy invocation')
    values = operation.first.fetch('env')
    (%w[authority] + recovery_inputs).each do |key|
      expected = if name == 'admit'
                   key == 'authority' ? "${{ inputs.recovery_run != '' && 'recovery' || '' }}" : '${{ inputs.' + key + ' }}'
                 else
                   '${{ needs.admit.outputs.' + key + ' }}'
                 end
      need(values[key.upcase] == expected, 'sample stage substituted the admitted recovery binding')
    end
  end

  need(recovery['name'] == 'Recover Maven Central verification' &&
       event(recovery).keys == ['workflow_dispatch'], 'recovery must be separately dispatched, never a tag publisher')
  recovery_fields = event(recovery).fetch('workflow_dispatch').fetch('inputs')
  need(recovery_fields.keys.sort == original_inputs.reject { |name| name == 'operation' } &&
       recovery_fields.values.all? { |value| value['required'] == true && value['type'] == 'string' },
       'recovery requires the complete original source/run/attempt/frozen descriptor')
  need(recovery['permissions'] == READ && recovery['concurrency'] == {
         'group' => 'maven-recovery-${{ inputs.maven_run }}-${{ inputs.maven_attempt }}', 'cancel-in-progress' => false} &&
       recovery['defaults'] == {'run' => {'shell' => 'bash', 'working-directory' => 'controller'}} &&
       !JSON.generate(recovery).include?('secrets.'), 'recovery must stay read-only, secret-free and original-attempt serialized')
  recovery_jobs = recovery.fetch('jobs')
  need(recovery_jobs.keys.sort == %w[prepare-recovery verify-recovery], 'recovery stage roster differs')
  prepare, verify_recovery = recovery_jobs.values_at('prepare-recovery', 'verify-recovery')
  need(prepare['if'] == "${{ github.repository == 'p2pKit/P2pKit' && github.ref == 'refs/heads/main' }}" &&
       prepare['runs-on'] == 'ubuntu-latest' && prepare['timeout-minutes'] == 20 && !prepare.key?('environment') &&
       verify_recovery['needs'] == 'prepare-recovery' && verify_recovery['runs-on'] == 'macos-15' &&
       verify_recovery['timeout-minutes'] == 90 && verify_recovery['environment'] == 'maven-central-recovery' &&
       !verify_recovery.key?('if') && recovery_jobs.values.none? { |job| job.key?('permissions') },
       'recovery must pass preparation then the separate protected bounded native verification job')
  prepare_names = ['Check out trusted main recovery controller', 'Prepare the exact original recovery request',
                   'Retain the immutable recovery request']
  verify_names = ['Check out trusted main recovery controller', 'Require the exact protected recovery approval',
                  'Check out the original frozen source separately, never current version overrides',
                  'Configure Java 17 for complete remote consumer fixtures only',
                  'Install Android SDK platform for original remote consumers',
                  'Verify original public signatures and immutable remote bytes',
                  'Verify complete remote consumers without republishing',
                  'Record fresh recovery verification and original custody',
                  'Retain the successful public recovery result']
  need(prepare.fetch('steps').map { |s| s['name'] } == prepare_names &&
       verify_recovery.fetch('steps').map { |s| s['name'] } == verify_names,
       'recovery order/step roster changed; no signing, upload, skipped verification or extra execution')
  recovery_jobs.each_value do |job|
    checkout = step(job, prepare_names.first)
    need(checkout['uses'].start_with?('actions/checkout@') && checkout['with'] == {
           'ref' => '${{ github.workflow_sha }}', 'path' => 'controller', 'persist-credentials' => false},
         'recovery controller must use trusted workflow source, not release or user-supplied code')
    job.fetch('steps').each { |s| need(!s.key?('if'), 'recovery stages cannot be skipped or retain success after failure') }
  end
  original_checkout = step(verify_recovery, verify_names[2])
  need(original_checkout['uses'].start_with?('actions/checkout@') && original_checkout['with'] == {
         'ref' => '${{ needs.prepare-recovery.outputs.original_source }}', 'path' => 'original', 'persist-credentials' => false},
       'original source must be checked out separately at S, never at current main')
  need(prepare['outputs'] == {
         'original_source' => '${{ steps.prepare.outputs.original_source }}',
         'request_sha256' => '${{ steps.prepare.outputs.sha256 }}',
         'request_artifact' => '${{ steps.request.outputs.artifact-id }}'} &&
       verify_recovery['env'] == {
         'REQUEST_ARTIFACT' => '${{ needs.prepare-recovery.outputs.request_artifact }}',
         'REQUEST_SHA256' => '${{ needs.prepare-recovery.outputs.request_sha256 }}',
         'ORIGINAL_ROOT' => '${{ github.workspace }}/original'}, 'recovery preparation outputs were substituted')
  preparation = step(prepare, prepare_names[1])
  need(preparation['id'] == 'prepare' && preparation['run'] ==
       'python3 -I -B -S scripts/maven_recovery.py prepare --source "$SOURCE" --maven-run "$MAVEN_RUN" --maven-attempt "$MAVEN_ATTEMPT" --frozen-artifact "$FROZEN_ARTIFACT" --frozen-sha256 "$FROZEN_SHA256"' &&
       preparation['env'] == {'GH_TOKEN' => '${{ github.token }}', 'SOURCE' => '${{ inputs.source_sha }}',
         'MAVEN_RUN' => '${{ inputs.maven_run }}', 'MAVEN_ATTEMPT' => '${{ inputs.maven_attempt }}',
         'FROZEN_ARTIFACT' => '${{ inputs.frozen_artifact }}', 'FROZEN_SHA256' => '${{ inputs.frozen_sha256 }}'},
       'recovery request must bind every original input directly')
  {verify_names[1] => 'authorize', verify_names[5] => 'verify-originals',
   verify_names[6] => 'verify-consumers', verify_names[7] => 'finish'}.each do |name, operation|
    expected = 'python3 -I -B -S scripts/maven_recovery.py ' + operation +
               ' --request-artifact "$REQUEST_ARTIFACT" --request-sha256 "$REQUEST_SHA256"'
    expected += ' --original-root "$ORIGINAL_ROOT"' unless operation == 'authorize'
    value = step(verify_recovery, name)
    need(value['run'] == expected && value['env'] == {'GH_TOKEN' => '${{ github.token }}'},
         'recovery must run its required original-bound verification, without alternate arguments or credentials')
  end
  java = step(verify_recovery, verify_names[3])
  need(java['uses'].start_with?('actions/setup-java@') && java['with'] == {'distribution' => 'temurin', 'java-version' => '17'} &&
       step(verify_recovery, verify_names[4])['run'] == '"$ANDROID_HOME"/cmdline-tools/latest/bin/sdkmanager "platforms;android-36"',
       'recovery consumer toolchain differs')
  [[prepare, prepare_names.last, 'maven-central-recovery-request-', 'recovery-request.json'],
   [verify_recovery, verify_names.last, 'maven-central-recovery-', 'recovery-result.json']].each do |job, name, prefix, file|
    value = step(job, name)
    need(value['uses'].start_with?('actions/upload-artifact@') && value['with'] == {
           'name' => prefix + '${{ github.run_id }}-${{ github.run_attempt }}',
           'path' => '${{ runner.temp }}/p2pkit-maven-recovery/' + file,
           'if-no-files-found' => 'error', 'retention-days' => 14, 'overwrite' => false},
         'recovery public records must be exact-attempt, finite and immutable')
  end
  need(step(prepare, prepare_names.last)['id'] == 'request', 'recovery request artifact output is not connected')

  [maven, samples, recovery].each do |workflow|
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
recovery = YAML.safe_load(File.read(File.join(ROOT, '.github/workflows/recover-maven-central.yml')), aliases: true)
validate(maven, samples, recovery)
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
  ->(m, _) { step(m['jobs']['publish-release'], 'Retain reviewed signed bundle before Central upload')['with']['overwrite'] = true },
  ->(m, _) { step(m['jobs']['publish-release'], 'Retain original PUBLISHED deployment receipt')['if'] = 'always()' },
  ->(m, _) { step(m['jobs']['publish-release'], 'Retain original PUBLISHED deployment receipt')['with']['path'] = 'build/reports/maven-central/status.json' },
  ->(m, _) { step(m['jobs']['publish-release'], 'Bind original completed Portal publication')['run'] = 'true' },
  ->(m, _) { step(m['jobs']['publish-release'], 'Validate signed originals before retention')['run'] = 'true' },
]
recovery_controls = [
  ->(_m, s, _r) { event(s)['workflow_dispatch']['inputs'].delete('recovery_sha256') },
  ->(_m, s, _r) { s['concurrency']['group'] = 'development-samples-${{ github.sha }}' },
  ->(_m, s, _r) { step(s['jobs']['publish'], 'Publish frozen development bytes and verify all anonymous full-download hashes')['env']['RECOVERY_ARTIFACT'] = '${{ inputs.recovery_artifact }}' },
  ->(_m, _s, r) { r['permissions']['contents'] = 'write' },
  ->(_m, _s, r) { event(r)['push'] = {'tags' => ['v*']} },
  ->(_m, _s, r) { event(r)['workflow_dispatch']['inputs'].delete('source_sha') },
  ->(_m, _s, r) { r['jobs']['prepare-recovery']['if'] = 'always()' },
  ->(_m, _s, r) { r['jobs']['verify-recovery']['needs'] = [] },
  ->(_m, _s, r) { r['jobs']['verify-recovery']['environment'] = 'maven-central' },
  ->(_m, _s, r) { r['jobs']['verify-recovery']['timeout-minutes'] = 120 },
  ->(_m, _s, r) { r['jobs']['verify-recovery']['env']['REQUEST_SHA256'] = '${{ inputs.frozen_sha256 }}' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Check out trusted main recovery controller')['with']['ref'] = '${{ inputs.source_sha }}' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Check out the original frozen source separately, never current version overrides')['with']['ref'] = '${{ github.sha }}' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Require the exact protected recovery approval')['run'] = 'true' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Verify original public signatures and immutable remote bytes')['run'] = 'true' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Verify complete remote consumers without republishing')['run'] = 'true' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Record fresh recovery verification and original custody')['env']['TOKEN'] = '${{ secrets.MAVEN_CENTRAL_PASSWORD }}' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Retain the successful public recovery result')['with']['overwrite'] = true },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Retain the successful public recovery result')['with']['retention-days'] = 30 },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Retain the successful public recovery result')['if'] = 'always()' },
  ->(_m, _s, r) { step(r['jobs']['verify-recovery'], 'Retain the successful public recovery result')['continue-on-error'] = true },
  ->(_m, _s, r) { r['jobs']['verify-recovery']['steps'].reverse! },
]
(controls + recovery_controls).each_with_index do |change, index|
  copies = Marshal.load(Marshal.dump([maven, samples, recovery]))
  change.call(*copies.take(change.arity))
  rejected = false
  begin
    validate(*copies)
  rescue StandardError
    rejected = true
  end
  need(rejected, "negative topology control #{index + 1} was accepted")
end
puts "PASS: maintained workflow topology and #{controls.size + recovery_controls.size} negative controls (source only)"
