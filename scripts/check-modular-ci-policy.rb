#!/usr/bin/env ruby
# Active pipeline invariants, not historical step counts or bootstrap proofs.
require 'yaml'
module ModularCI
  def self.require!(condition, message)
    raise ArgumentError, message unless condition
  end
  def self.load(path)
    YAML.safe_load(File.read(path), aliases: false)
  end
  def self.check(root)
    workflows = Dir[File.join(root, '.github/workflows/*.yml')]
    require!(!File.exist?(File.join(root, '.github/workflows/dependency-cache-bootstrap.yml')), 'Retired bootstrap remains active')
    workflows.each do |path|
      workflow = load(path)
      require!(!File.read(path).include?('p2pkit-nonphysical-heavy'), 'Repository-global execution lock remains')
      workflow.fetch('jobs').each_value do |job|
        ([job] + job.fetch('steps', [])).each do |step|
          if step['uses']
            use = step['uses']
            require!(use.match?(%r{\A\./\.github/workflows/[a-z0-9-]+\.yml\z}) ||
                     use.match?(%r{@[0-9a-f]{40}\z}), 'Action must be exact-commit pinned')
          end
          if step['uses'].to_s.start_with?('actions/checkout@')
            require!(step.fetch('with')['persist-credentials'] == false, 'Checkout persisted credentials')
          end
        end
      end
    end
    ci = load(File.join(root, '.github/workflows/ci.yml'))
    worker = load(File.join(root, '.github/workflows/ci-component.yml'))
    jobs = ci.fetch('jobs')
    require!(jobs.keys.sort == %w[android-legacy-task-preview android-permission-diagnostic android-ui-diagnostic apple-issue-diagnostic complete-gate component plan qualify], 'Missing or extra active CI stage')
    triggers = ci.fetch('on') { ci.fetch(true) }
    required = %w[source dependencies jvm-linux jvm-windows android apple-arm64 apple-x64
                  desktop-linux desktop-windows desktop-macos security compatibility consumers macos-shared]
    require!(triggers.dig('workflow_dispatch', 'inputs', 'component', 'options').sort ==
             ['all', *required, 'bundle-diagnostic', 'jmdns-diagnostic', 'published-consumers-diagnostic', 'consumers-pom-diagnostic', 'apple-issue-diagnostic', 'android-ui-diagnostic', 'android-permission-diagnostic', 'android-legacy-task-preview'].sort,
             'Missing or extra independently selectable required component')
    writer = load(File.join(root, '.github/workflows/dependency-update-candidate.yml')).fetch('jobs').fetch('generate')
    require!(writer['runs-on'] == 'macos-15-intel' && writer.fetch('steps').any? { |s|
               s['run'] == 'bash scripts/setup-ci-component.sh dependency-update' },
             'Dependency writer must use the explicit reviewed CLI baseline')
    publisher = load(File.join(root, '.github/workflows/publish-maven-central.yml')).fetch('jobs')
    recovery = load(File.join(root, '.github/workflows/recover-maven-central.yml')).fetch('jobs')
    require!(publisher.keys.sort == %w[freeze-applications publish-release verify-release],
             'Maven success/recovery must retain the existing three-job contract')
    {publisher.fetch('publish-release') => 'maven-central',
     recovery.fetch('verify-recovery') => 'maven-central-recovery'}.each do |job, environment|
      require!(job['runs-on'] == 'macos-15-intel' &&
               (job['environment'].is_a?(Hash) ? job['environment']['name'] : job['environment']) == environment,
               'Publication/recovery must retain protected supported CLI execution')
      steps = job.fetch('steps')
      setup = steps.index { |step| step['run'] == 'bash scripts/setup-ci-component.sh consumers' &&
                                  !step['if'] && !step['continue-on-error'] }
      java = steps.filter_map { |step| step.dig('with', 'java-version').to_s if
                                step['uses'].to_s.start_with?('actions/setup-java@') }
      require!(setup && java == %w[21 17], 'Publication/recovery must prepare the reviewed consumer tools')
      consumer_command = environment == 'maven-central' ?
        'python3 -I -B -S scripts/run-published-consumers.py' : 'scripts/maven_recovery.py verify-consumers '
      consumer = steps.index { |step| environment == 'maven-central' ?
        step['run'].to_s.lines.map(&:strip).count(consumer_command) == 1 : step['run'].to_s.include?(consumer_command) }
      require!(consumer && setup < consumer && !steps[consumer]['if'] && !steps[consumer]['continue-on-error'],
               'Complete remote consumers must remain required after supported setup')
    end
    publication = publisher.fetch('publish-release')
    require!(publication['timeout-minutes'] == 150, 'Publisher HTTP clock must match the actual job timeout')
    {
      'Revalidate approved release and credentials' => ['verify', 'scripts/check-maven-central-version.sh absent'],
      'Upload once and wait for publication' => ['upload', 'scripts/publish-central-portal-bundle.sh \\'],
      'Verify immutable remote bytes and consumers' => ['verify', 'scripts/check-maven-central-version.sh published \\'],
    }.each do |name, (purpose, command)|
      selected = publication.fetch('steps').select { |step| step['name'] == name }
      require!(selected.length == 1, 'Publisher HTTP step must be unique')
      step = selected.first
      clock = 'P2PKIT_CENTRAL_JOB_DEADLINE="$(python3 -I -B -S scripts/run-published-consumers.py --http-deadline ' + purpose + ')"'
      lines = step['run'].to_s.lines.map(&:strip)
      index = lines.index(clock)
      require!(index && lines.count(clock) == 1 &&
               lines[index, 3] == [clock, 'export P2PKIT_CENTRAL_JOB_DEADLINE', command] &&
               step.dig('env', 'GH_TOKEN') == '${{ github.token }}' && !step['if'] && !step['continue-on-error'],
               'Publisher HTTP work must admit and retain the original-job deadline before requests')
    end
    %w[bundle-diagnostic jmdns-diagnostic published-consumers-diagnostic consumers-pom-diagnostic apple-issue-diagnostic android-ui-diagnostic android-permission-diagnostic android-legacy-task-preview].each do |diagnostic|
      require!(triggers.dig('workflow_dispatch', 'inputs', 'component', 'options').include?(diagnostic),
               'Explicit focused diagnostic route missing')
      %w[qualify complete-gate].each do |name|
        require!(jobs[name].fetch('if').include?("inputs.component != '#{diagnostic}' &&"),
                 'Diagnostic must not aggregate or complete qualification')
      end
    end
    # A manual issue run must not launch the regular matrix, gain credentials,
    # or become a green release gate even when qualification_selection is set.
    {'apple-issue-diagnostic' => ['apple-issue-validation', 'operation', 'apple_operation',
                                 %w[both iphoneos-product swift-jvm-transfer]],
     'android-ui-diagnostic' => ['android-ui-validation', 'case', 'android_case',
                                %w[both 317 324]],
     'android-permission-diagnostic' => ['android-permission-validation', nil, nil, nil],
     'android-legacy-task-preview' => ['android-legacy-task-preview', 'api', 'android_legacy_api',
                                     %w[both 24 32]]}.each do |name, (workflow, argument, input, options)|
      if input
        selector = triggers.dig('workflow_dispatch', 'inputs', input)
        require!(selector && selector['type'] == 'choice' && selector['default'] == 'both' &&
                 selector['options'] == options, 'Issue diagnostic selector must remain bounded')
        # Legacy defaults are declared inputs; explicit empty/invalid values must reach its rejecting selector.
        forwarded = name == 'android-legacy-task-preview' ? "${{ inputs.#{input} }}" :
                                                          "${{ inputs.#{input} || 'both' }}"
      end
      job = jobs.fetch(name)
      require!(job.keys.sort == (input ? %w[if permissions uses with] : %w[if permissions uses]) &&
               job['if'] == "${{ github.event_name == 'workflow_dispatch' && inputs.component == '#{name}' }}" &&
               job['permissions'] == {'contents' => 'read'} &&
               job['uses'] == "./.github/workflows/#{workflow}.yml" &&
               job['with'] == (input ? {argument => forwarded} : nil),
               'Issue diagnostic must remain explicit, same-source and without secrets or publication rights')
      %w[plan component].each do |stage|
        require!(jobs.fetch(stage).fetch('if').include?("inputs.component != '#{name}'"),
                 'Issue diagnostic must not launch the component matrix')
      end
    end
    require!(jobs['component'].dig('strategy', 'fail-fast') == false, 'One component must not cancel another')
    require!(jobs['component']['uses'] == './.github/workflows/ci-component.yml', 'Component executor changed')
    require!(jobs['complete-gate']['needs'] == ['qualify'] &&
             jobs['complete-gate']['if'].include?('always()'), 'Complete gate must reject skipped/failed qualification')
    require!(jobs['complete-gate']['steps'].any? { |s| s['run'] == 'test "$QUALIFICATION" = success' }, 'No actual qualification result guard')
    text = File.read(File.join(root, '.github/workflows/ci-component.yml'))
    require!(!text.match?(/initial-recipient|run-hosted-test-custody|cache-provider/), 'Obsolete bootstrap dependency')
    steps = worker.fetch('jobs').fetch('run').fetch('steps')
    run = steps.find { |s| s['id'] == 'execution' }
    require!(run && run['run'].include?('scripts/ci_evidence.py') && run['run'].include?('scripts/ci_component.py'), 'Missing genuine component/evidence invocation')
    require!(steps.any? { |s| s['run'].to_s.include?('scripts/setup-ci-component.sh') }, 'Missing platform setup')
    require!(!run['continue-on-error'], 'Real component failure cannot be ignored')
    require!(worker.dig('jobs', 'run', 'env', 'CI_EVIDENCE_RECIPIENT_SHA256') == '${{ vars.CI_EVIDENCE_RECIPIENT_SHA256 }}', 'Recipient must be independently pinned')
    cache = steps.find { |s| s['uses'].to_s.start_with?('gradle/actions/setup-gradle@') }
    require!(cache && cache.dig('with', 'cache-read-only') == "${{ github.ref != 'refs/heads/main' }}", 'Untrusted refs cannot write release dependency caches')
    require!(cache.dig('with', 'gradle-home-cache-excludes').include?('caches/build-cache-1'), 'Affected Kotlin build-cache metadata cannot be restored')
    steps.select { |s| s['uses'].to_s.start_with?('actions/upload-artifact@') }.each do |step|
      require!(step.dig('with', 'retention-days') == 14 && step.dig('with', 'overwrite') == false &&
               step.dig('with', 'if-no-files-found') == 'error', 'Evidence/package upload must be immutable and nonempty')
    end
    true
  end
end
if $PROGRAM_NAME == __FILE__
  begin
    ModularCI.check(ARGV[0] || File.expand_path('..', __dir__))
    puts 'PASS: modular CI retains real component, integrity and immutable evidence gates'
  rescue ArgumentError, KeyError, Psych::Exception => error
    abort "FAIL: #{error.message}"
  end
end
