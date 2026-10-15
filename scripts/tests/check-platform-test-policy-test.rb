#!/usr/bin/env ruby
# Active modular callers must execute the maintained native coverage driver.
# These are offline routing/policy controls, not native test qualification.
require 'yaml'
require 'json'
require 'open3'

ROOT = File.expand_path('../..', __dir__)
REPORT = 'build/reports/platform-tests/**'

def need(value, message)
  raise ArgumentError, message unless value
end

def command_json(*arguments)
  stdout, stderr, status = Open3.capture3('python3', '-B', File.join(ROOT, 'scripts/ci_component.py'), *arguments)
  need(status.success? && stderr.empty?, 'Cannot observe actual component command routing')
  JSON.parse(stdout)
end

def execution(inputs)
  inputs[:worker].fetch('jobs').fetch('run').fetch('steps').find { |step| step['id'] == 'execution' }
end

def evidence(inputs)
  inputs[:worker].fetch('jobs').fetch('run').fetch('steps').find do |step|
    step.fetch('uses', '').start_with?('actions/upload-artifact@') &&
      step.fetch('with', {}).fetch('name', '').start_with?('ci-evidence-')
  end
end

def check_platform_policy(v)
  matrix = v[:matrix].fetch('include').to_h { |row| [row.fetch('component'), row] }
  {'apple-arm64' => ['macos-26', 150, 'full'], 'apple-x64' => ['macos-15-intel', 120, 'ios-x64']}.each do |name, (os, minutes, profile)|
    need(matrix.fetch(name).values_at('os', 'minutes') == [os, minutes], 'Wrong native platform or operational budget')
    commands = v.fetch(name.to_sym)
    need(commands.size == 1 && commands[0][0] == 'native-platform-tests' &&
         File.basename(commands[0][1][0]).start_with?('python') &&
         commands[0][1].drop(1) == ['-B', 'scripts/run-platform-tests.py', profile],
         'Native coverage driver/profile bypassed')
  end
  component = v[:ci].fetch('jobs').fetch('component')
  need(component['uses'] == './.github/workflows/ci-component.yml' &&
       component.dig('strategy', 'fail-fast') == false && !component.key?('continue-on-error'),
       'Native components must execute independently without ignored failures')
  intel = v[:intel]
  need(intel['permissions'] == {'contents' => 'read', 'actions' => 'read'} && !JSON.generate(intel).include?('secrets.'),
       'Intel workflow must remain read-only and secret-free')
  triggers = intel.fetch('on') { intel.fetch(true) }
  need(triggers.keys.sort == %w[schedule workflow_dispatch] && triggers['workflow_dispatch'].nil? &&
       triggers['schedule'] == [{'cron' => '27 3 * * 1'}], 'Intel manual/weekly coverage changed')
  job = intel.fetch('jobs').fetch('component')
  need(job['uses'] == './.github/workflows/ci-component.yml' &&
       job['with'] == {'component' => 'apple-x64', 'runner' => 'macos-15-intel', 'minutes' => 120} &&
       !%w[if environment continue-on-error].any? { |key| job.key?(key) }, 'Intel native invocation changed')
  worker = v[:worker].fetch('jobs').fetch('run')
  need(worker['timeout-minutes'] == '${{ inputs.minutes + 10 }}' &&
       !worker.key?('continue-on-error'), 'Missing bounded command plus cleanup/evidence window')
  run = execution(v)
  need(run && !%w[if continue-on-error shell working-directory].any? { |key| run.key?(key) },
       'Native execution may not be skipped or ignored')
  text = run.fetch('run')
  need(text.scan('scripts/ci_evidence.py').size == 1 && text.scan('scripts/ci_component.py').size == 1 &&
       text.include?('--timeout-seconds "$((MINUTES * 60))"') && !text.include?('||'), 'Actual bounded component wrapper missing')
  need(text.include?("--report-glob '**/build/test-results/**/*.xml'") &&
       text.include?("--report-glob 'build/reports/**/*'"), 'Native XML/coverage report capture missing')
  upload = evidence(v)
  need(upload && upload['if'] == "${{ always() && steps.execution.outcome != 'skipped' }}" &&
       !upload.key?('continue-on-error'), 'Failure evidence must still be retained')
  need(upload['with'].values_at('path', 'retention-days', 'overwrite', 'if-no-files-found') ==
       ['${{ runner.temp }}/ci-evidence-${{ inputs.component }}/*', 14, false, 'error'],
       'Evidence must be nonempty immutable encrypted bundle, not raw logs')
  need(worker['steps'].index(run) < worker['steps'].index(upload), 'Evidence precedes actual execution')
  need(v[:setup].include?('/Applications/Xcode_26.5.app/Contents/Developer') &&
       v[:setup].include?('/Applications/Xcode_26.3.app/Contents/Developer') &&
       v[:setup].include?('echo "DEVELOPER_DIR=$xcode" >> "$GITHUB_ENV"'), 'Admitted ARM/Intel Xcode selections missing')
  # Retain actual coverage/failure decisions in the maintained driver. Its
  # behavioral tests are invoked by release-gate and the source component.
  %w[gradle/platform-test-coverage.init.gradle build/reports/platform-tests].each do |path|
    need(v[:driver].include?(path), 'Native execution evidence location missing')
  end
  need(v[:driver].include?('assess(report, policy, profile, arch, token,') &&
       v[:driver].include?('return (code or 1) if errors else 0'), 'Native coverage/failure assessment bypassed')
  {dry: ['local-release', '$RELEASE_SHA'], publish: ['verify-release', '$GITHUB_SHA']}.each do |key, (job_name, source)|
    steps = v[key].fetch('jobs').fetch(job_name).fetch('steps')
    caller = steps.find { |step| step.fetch('run', '').include?('scripts/ci_qualification.py verify --source') }
    command = caller && caller['run'].lines.map(&:strip).find { |line| line.start_with?('python3 -B scripts/ci_qualification.py verify ') }
    need(command && command.include?("--source \"#{source}\"") &&
         command.include?('--output "$RUNNER_TEMP/qualification.json"') && !command.match?(/(?:\|\||&&|;)/) &&
         !%w[if continue-on-error].any? { |field| caller.key?(field) }, 'Release must verify exact qualified source without rebuilding')
    if key == :publish
      need(command.include?('--selection "$RUNNER_TEMP/qualification-binding.json"') &&
           caller.fetch('env', {})['FROZEN_QUALIFICATION_BINDING'] == '${{ needs.freeze-applications.outputs.qualification_binding }}' &&
           caller['run'].lines.any? { |line| line.strip == 'printf \'%s\\n\' "$FROZEN_QUALIFICATION_BINDING" > "$RUNNER_TEMP/qualification-binding.json"' },
           'Tag verification must consume the already-frozen qualification, not reselect mutable settings')
    end
    need(!steps.any? { |step| step.fetch('run', '').include?('scripts/run-release-gate.sh') },
         'Release selection must not restart a monolithic build after qualification')
    upload = steps.find { |step| step.fetch('uses', '').start_with?('actions/upload-artifact@') }
    need(upload && upload.fetch('with').values_at('path', 'retention-days', 'overwrite', 'if-no-files-found') ==
         ['${{ runner.temp }}/qualification.json', 14, false, 'error'], 'Release must retain immutable qualification reference')
  end
  # Publication consumes already-qualified components; do not require a second
  # monolithic platform rerun after the tag/protected approval boundary.
  publish_jobs = v[:publish].fetch('jobs')
  freeze = publish_jobs.fetch('freeze-applications')
  publisher = publish_jobs.fetch('publish-release')
  need(freeze['steps'].any? { |step| step['run'] == 'python3 -I -B -S scripts/release_application_set.py freeze' },
       'Publisher must freeze real qualification before approval')
  need(publisher.fetch('needs').include?('freeze-applications') && publisher.key?('environment'),
       'Publication requires frozen set and protected approval')
  need(publisher['steps'].any? { |step| step.fetch('run', '').include?('scripts/release_application_set.py revalidate --artifact') &&
       !step.key?('continue-on-error') }, 'Publication must revalidate original frozen evidence')
  lines = v[:release].lines.map(&:strip)
  need(lines.include?('set -euo pipefail'), 'Release shell must propagate failures')
  need(lines.count('python3 scripts/run-platform-tests.py full') == 1, 'Release FULL driver bypassed')
  %w[check-platform-test-policy-test.rb run-platform-tests-test.py].each do |script|
    interpreter = script.end_with?('.rb') ? 'ruby' : 'python3'
    need(lines.include?("#{interpreter} scripts/tests/#{script}"), 'Release native regression missing')
  end
end

inputs = {ci: 'ci.yml', worker: 'ci-component.yml', intel: 'ios-x64-tests.yml',
          dry: 'release-dry-run.yml', publish: 'publish-maven-central.yml'}.transform_values do |file|
  YAML.safe_load(File.read(File.join(ROOT, '.github/workflows', file)), aliases: false)
end
inputs.merge!(matrix: command_json('--matrix', 'all'),
              'apple-arm64': command_json('apple-arm64', '--list-commands'),
              'apple-x64': command_json('apple-x64', '--list-commands'),
              setup: File.read(File.join(ROOT, 'scripts/setup-ci-component.sh')),
              driver: File.read(File.join(ROOT, 'scripts/run-platform-tests.py')),
              release: File.read(File.join(ROOT, 'scripts/run-release-gate.sh')))
check_platform_policy(inputs)
mutations = {
  'raw FULL bypass' => ->(v) { v[:'apple-arm64'][0][1] = ['./gradlew', 'check'] },
  'wrong Intel profile' => ->(v) { v[:'apple-x64'][0][1][-1] = 'full' },
  'echo not execution' => ->(v) { v[:'apple-arm64'][0][1].unshift('echo') },
  'wrong Intel host' => ->(v) { v[:matrix]['include'].find { |x| x['component'] == 'apple-x64' }['os'] = 'macos-26' },
  'missing native budget' => ->(v) { v[:matrix]['include'].find { |x| x['component'] == 'apple-arm64' }.delete('minutes') },
  'cancel unrelated components' => ->(v) { v[:ci]['jobs']['component']['strategy']['fail-fast'] = true },
  'ignored native matrix' => ->(v) { v[:ci]['jobs']['component']['continue-on-error'] = true },
  'disabled Intel' => ->(v) { v[:intel]['jobs']['component']['if'] = false },
  'wrong Intel reusable route' => ->(v) { v[:intel]['jobs']['component']['with']['component'] = 'apple-arm64' },
  'missing Intel schedule' => ->(v) { (v[:intel]['on'] || v[:intel][true]).delete('schedule') },
  'missing worker budget' => ->(v) { v[:worker]['jobs']['run'].delete('timeout-minutes') },
  'ignored execution' => ->(v) { execution(v)['continue-on-error'] = true },
  'skipped execution' => ->(v) { execution(v)['if'] = false },
  'unwrapped native output' => ->(v) { execution(v)['run'].sub!('scripts/ci_evidence.py', 'scripts/unrelated.py') },
  'ignored shell failure' => ->(v) { execution(v)['run'] += ' || true' },
  'missing XML reports' => ->(v) { execution(v)['run'].sub!("--report-glob '**/build/test-results/**/*.xml'", '') },
  'missing coverage reports' => ->(v) { execution(v)['run'].sub!("--report-glob 'build/reports/**/*'", '') },
  'only successful evidence' => ->(v) { evidence(v)['if'] = 'success()' },
  'ignored evidence failure' => ->(v) { evidence(v)['continue-on-error'] = true },
  'raw private upload' => ->(v) { evidence(v)['with']['path'] = 'build/reports/**' },
  'missing evidence accepted' => ->(v) { evidence(v)['with']['if-no-files-found'] = 'warn' },
  'mutable evidence' => ->(v) { evidence(v)['with']['overwrite'] = true },
  'unbounded retention' => ->(v) { evidence(v)['with']['retention-days'] = 90 },
  'missing Intel Xcode' => ->(v) { v[:setup].sub!('/Applications/Xcode_26.3.app/Contents/Developer', '/Applications/Xcode.app/Contents/Developer') },
  'missing ARM Xcode' => ->(v) { v[:setup].sub!('/Applications/Xcode_26.5.app/Contents/Developer', '/Applications/Xcode.app/Contents/Developer') },
  'bypassed coverage' => ->(v) { v[:driver].gsub!('assess(report, policy, profile, arch, token,', 'skipped_coverage(') },
  'ignored native errors' => ->(v) { v[:driver].sub!('return (code or 1) if errors else 0', 'return 0') },
  'raw release check' => ->(v) { v[:release].sub!('python3 scripts/run-platform-tests.py full', './gradlew check') },
  'ignored release errors' => ->(v) { v[:release].sub!('python3 scripts/run-platform-tests.py full', 'python3 scripts/run-platform-tests.py full || true') },
  'missing regression' => ->(v) { v[:release].sub!('python3 scripts/tests/run-platform-tests-test.py', 'true') }
}
{dry: 'local-release', publish: 'verify-release'}.each do |workflow, name|
  mutations["#{workflow} wrong qualified source"] = ->(v) {
    v[workflow]['jobs'][name]['steps'].each do |step|
      step['run'] = step['run'].gsub('ci_qualification.py verify --source', 'ci_qualification.py verify --other-source') if step['run']
    end
  }
  mutations["#{workflow} missing qualification artifact"] = ->(v) {
    v[workflow]['jobs'][name]['steps'].each do |step|
      step['with']['path'] = 'build/reports/**' if step.fetch('with', {}).key?('path')
    end
  }
end
mutations['missing frozen publisher dependency'] = ->(v) { v[:publish]['jobs']['publish-release']['needs'].delete('freeze-applications') }
mutations['tag verification reselects mutable qualification'] = ->(v) {
  v[:publish]['jobs']['verify-release']['steps'].each do |step|
    step['run'] = step['run'].gsub('--selection "$RUNNER_TEMP/qualification-binding.json"', '') if step['run']
  end
}
mutations['tag verification uses mutable binding'] = ->(v) {
  v[:publish]['jobs']['verify-release']['steps'].each do |step|
    step['env']['FROZEN_QUALIFICATION_BINDING'] = '${{ vars.RELEASE_QUALIFICATION_BINDING }}' if step.fetch('env', {}).key?('FROZEN_QUALIFICATION_BINDING')
  end
}
mutations['unprotected publisher'] = ->(v) { v[:publish]['jobs']['publish-release'].delete('environment') }
mutations['missing frozen evidence revalidation'] = ->(v) {
  v[:publish]['jobs']['publish-release']['steps'].each do |step|
    step['run'] = step['run'].gsub('scripts/release_application_set.py revalidate --artifact', 'echo skipped') if step['run']
  end
}
mutations.each do |name, mutate|
  altered = Marshal.load(Marshal.dump(inputs))
  mutate.call(altered)
  raise "mutation had no effect: #{name}" if altered == inputs
  rejected = false
  begin
    check_platform_policy(altered)
  rescue KeyError, ArgumentError, TypeError
    rejected = true
  end
  raise "unsafe platform policy accepted: #{name}" unless rejected
end
puts "RESULT: PASS — modular native callers/coverage/failure evidence (#{mutations.size + 1} policy checks)"
