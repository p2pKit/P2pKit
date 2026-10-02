#!/usr/bin/env python3
"""Owner-authorized remaining ARM gates on the officially accepted Mac27/Xcode27 host.

Not a hosted-runner impersonation or a replacement executor. Reuses the original
native receipts, XCTest inventories, provenance assessors and finalizers. Prepare
copies only a pinned distribution ZIP and writes a NEW private session request;
it never downloads, extracts an archive, invokes sudo or executes an application.
Run needs that separately authorized fresh session. No global install, signing,
device access, cache restoration, deadline change or historical receipt promotion.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
BASELINE = 'e1ae3f37b27780cc4d9efaa16228fcb75c8e159b'
DEVELOPER = '/Applications/Xcode.app/Contents/Developer'
SCOPE = 'OFFICIAL_MAC27_XCODE27_REMAINING_ARM_AND_PHONE_GATES_NOT_FULL_RPC_LAN_QUALIFICATION'
PLAN = ('gradle-distribution', 'native-controls', 'toolchain', 'installed-tools', 'simulator-admission', 'apple-producer',
        'apple-project', 'swift-runtime', 'owned-swift-lifecycle', 'owned-swift-cancellation', 'phone-app',
        'mobile-driver', 'mac-generator-preflight')
SESSION_PROOF = dict(schema=1, scope='PROCESS_LOCAL_AUDIT_SESSION_NOT_OWNERSHIP_OR_PRODUCT_ADMISSION',
    freshAssignedSession=True, auditPolicyPreserved=True, invokingCredentialsRestored=True,
    rootCannotBeRegained=True, privilegedObservationOrProductExecution=False)


def need(condition, message='Local ARM qualification admission failed'):
    if not condition:
        raise RuntimeError(message)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


q = module('local_arm_maintained_qualification', 'run-rpc-qualification.py')
runner = module('local_arm_native_executor', 'run-audit-command.py')
bootstrap = module('local_arm_existing_bootstrap', 'with-darwin-audit-session.py')
distribution = module('local_arm_distribution_input', 'rpc_gradle_distribution.py')
xcodegen_package = module('local_arm_xcodegen_package', 'rpc_xcodegen_package.py')
signal_environment = module('local_arm_signal_environment', 'rpc_local_signal_environment.py')


def local_host(env, system, machine, uid, euid):
    need((system, machine) == ('Darwin', 'arm64') and uid == euid and uid > 0,
         'Native unprivileged ARM host required')
    need(not any(key in env for key in ('GITHUB_ACTIONS', 'RUNNER_ENVIRONMENT', 'P2PKIT_AUDIT_STATE_DIR',
                                      'P2PKIT_AUDIT_OWNERSHIP_CHAIN')),
         'No hosted identity or reused native state may enter the local controller')


def environment_versions(macos, xcode):
    need(re.fullmatch(rb'27\.[0-9]+(?:\.[0-9]+)?\n?', macos) and
         xcode.decode('ascii').splitlines()[0] == 'Xcode 27.0', 'Official macOS27 / Xcode27.0 required')


def private_parent(path):
    bootstrap.physical(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700 and
         not path.is_relative_to(ROOT) and not ROOT.is_relative_to(path), 'New private outside-source parent required')
    return path


def source_admission(expected):
    need(re.fullmatch('[a-f0-9]{40}', expected), 'Exact candidate SHA required')
    source = runner.source_snapshot(ROOT)
    need(source['commit'] == expected and source['status'] == '' and source['diffSha256'] == runner.digest(b''),
         'Candidate must remain clean and committed')
    need(runner.git(ROOT, 'symbolic-ref', 'HEAD').decode().strip() == q.REF and
         runner.git(ROOT, 'rev-parse', '--is-shallow-repository').strip() == b'false' and
         not runner.git(ROOT, 'for-each-ref', '--format=%(refname)', 'refs/tags').strip(),
         'Continue the existing full-history no-tags feature checkout, not the old project')
    need(runner.git(ROOT, 'config', '--get', 'remote.origin.url').decode().strip() in
         ('https://github.com/p2pKit/P2pKit', 'https://github.com/p2pKit/P2pKit.git'), 'Canonical feature origin required')
    runner.git(ROOT, 'merge-base', '--is-ancestor', BASELINE, expected)
    return source


def plan_for(swift_runtime_only, mac_generator_only=False, cli_process_only=False):
    selections = (swift_runtime_only, mac_generator_only, cli_process_only)
    need(all(type(value) is bool for value in selections) and sum(selections) <= 1,
         'Explicit mutually exclusive Boolean selections required')
    if cli_process_only:
        return ('gradle-distribution', 'native-controls', 'toolchain', 'cli-producer', 'cli-process')
    if mac_generator_only:
        return ('gradle-distribution', 'native-controls', 'toolchain', 'mac-generator-preflight')
    return PLAN[:8] if swift_runtime_only else PLAN


def run_argv(parent, expected, swift_runtime_only=False, mac_generator_only=False, cli_process_only=False):
    plan_for(swift_runtime_only, mac_generator_only, cli_process_only)
    return [str(Path(sys.executable).absolute()), '-B', str(Path(__file__).resolve()), 'run',
            '--owner-authorized-arm27', '--parent', str(parent), '--expected-commit', expected] + (
                ['--swift-runtime-only'] if swift_runtime_only else ['--mac-generator-only'] if mac_generator_only
                else ['--cli-process-only'] if cli_process_only else [])


def session_proof(value):
    need(type(value) is dict and set(value) == {*SESSION_PROOF, 'previousSessionAssigned'} and
         type(value['previousSessionAssigned']) is bool and
         all(type(value[k]) is type(v) and value[k] == v for k, v in SESSION_PROOF.items()),
         'Original fresh-session policy and permanent privilege drop are required')


def prepare(args):
    local_host(os.environ, platform.system(), platform.machine(), os.getuid(), os.geteuid())
    plan = plan_for(args.swift_runtime_only, args.mac_generator_only, args.cli_process_only)
    parent, source = private_parent(args.parent), source_admission(args.expected_commit)
    need(args.owner_authorized_arm27 and not list(parent.iterdir()), 'Explicit authorization and unused parent required')
    paths = {key: str(value.resolve(strict=True)) for key, value in (
        ('JAVA_HOME', args.java_home), ('P2PKIT_AUDIT_JDK21', args.jdk21), ('ANDROID_HOME', args.android_sdk))}
    xcodegen = args.xcodegen.resolve(strict=True)
    need(xcodegen.is_file() and os.access(xcodegen, os.X_OK) and Path(DEVELOPER).is_dir(), 'Installed Apple tools required')
    package = xcodegen_package.inventory(xcodegen)
    for key in ('JAVA_HOME', 'P2PKIT_AUDIT_JDK21'):
        need(all((Path(paths[key]) / 'bin' / name).is_file() for name in ('java', 'javac')), 'Installed JDKs required')
    sdk = Path(paths['ANDROID_HOME'])
    need(all((sdk / 'platforms' / name / 'android.jar').is_file() for name in ('android-36', 'android-37.0')),
         'Use the installed Android compile platforms; no SDK installation')
    env = dict(paths, DEVELOPER_DIR=DEVELOPER, LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8',
        PATH=os.pathsep.join((str(Path(sys.executable).parent), str(xcodegen.parent), '/usr/bin', '/bin', '/usr/sbin', '/sbin')))
    config = dict(uid=os.getuid(), gid=os.getgid(), cwd=str(ROOT),
                  argv=run_argv(parent, args.expected_commit, args.swift_runtime_only, args.mac_generator_only,
                                args.cli_process_only), environment=env)
    bootstrap.validate(config, os.getuid(), os.getgid())
    # Data input only, not a restored Gradle home/runtime or a finalizer bypass.
    # Verify before publishing any usable bootstrap request. No native execution.
    archive = distribution.prepare_archive(ROOT, args.gradle_distribution, parent)
    need(source_admission(args.expected_commit) == source, 'Source changed during distribution preparation')
    (parent / 'private-session').mkdir(mode=0o700)
    bootstrap.write_new(parent / 'private-session/session-config.json', config)
    bootstrap.write_new(parent / 'prepared.json', dict(schema=1, scope=SCOPE, baseline=BASELINE, source=source,
        xcodegen=str(xcodegen), xcodegenSha256=runner.file_digest(xcodegen), environment=env, plan=list(plan),
        swiftRuntimeOnly=args.swift_runtime_only, macGeneratorOnly=args.mac_generator_only, cliProcessOnly=args.cli_process_only,
        gradleDistribution=archive, xcodegenPackage=package,
        priorResultsReusedAsNativeAdmission=False, bootstrapExecuted=False, installationsRequested=False))
    print(parent / 'private-session/session-config.json')
    return 0


def admit_session(parent, expected, swift_runtime_only=False, mac_generator_only=False, cli_process_only=False):
    config_path = parent / 'private-session/session-config.json'
    proof_path = parent / 'private-session/session-admission.json'
    config = bootstrap.read_config(config_path, os.getuid())
    bootstrap.validate(config, os.getuid(), os.getgid())
    session_proof(bootstrap.read_config(proof_path, os.getuid()))
    need(config['cwd'] == str(ROOT) and
         config['argv'] == run_argv(parent, expected, swift_runtime_only, mac_generator_only, cli_process_only),
         'Exact prepared local command and selection required')
    observed = bootstrap.AuditInfo()
    system = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    system.getaudit_addr.argtypes = [ctypes.POINTER(bootstrap.AuditInfo), ctypes.c_int]
    system.getaudit_addr.restype = ctypes.c_int
    need(ctypes.sizeof(observed) == 48 and system.getaudit_addr(ctypes.byref(observed), 48) == 0 and
         observed.asid not in (0, -1) and os.environ.get('SECURITYSESSIONID') == format(observed.asid, 'x'),
         'Fresh kernel session must survive into the ordinary controller')
    return config


def admit_source_inputs(parent, expected, config, swift_runtime_only=False, mac_generator_only=False, cli_process_only=False):
    plan = plan_for(swift_runtime_only, mac_generator_only, cli_process_only)
    prepared = runner.read_json(parent / 'prepared.json')
    need(prepared['schema'] == 1 and prepared['scope'] == SCOPE and prepared['baseline'] == BASELINE and
         prepared['source'] == source_admission(expected) and prepared['plan'] == list(plan) and
         prepared.get('swiftRuntimeOnly') is swift_runtime_only and
         prepared.get('macGeneratorOnly') is mac_generator_only and
         prepared.get('cliProcessOnly') is cli_process_only and
         prepared['environment'] == config['environment'] and
         all(os.environ.get(k) == v for k, v in config['environment'].items()), 'Prepared source/environment changed')
    distribution.admit_archive(ROOT, parent, prepared['gradleDistribution'])
    need(xcodegen_package.admit(prepared['xcodegenPackage']) / 'bin/xcodegen' == Path(prepared['xcodegen']),
         'Prepared XcodeGen prefix differs')
    bootstrap.write_new(parent / 'local-session-admission.json', dict(schema=1, scope=SCOPE, baseline=BASELINE,
        source=prepared['source'], sessionPreparationNotOwnershipAdmission=True,
        configSha256=runner.file_digest(parent / 'private-session/session-config.json'),
        sessionProofSha256=runner.file_digest(parent / 'private-session/session-admission.json')))
    return prepared


def admit_execution_environment(parent, expected, swift_runtime_only=False, mac_generator_only=False, cli_process_only=False):
    config = admit_session(parent, expected, swift_runtime_only, mac_generator_only, cli_process_only)
    # The unchanged bootstrap has already permanently dropped privilege. Do not
    # let an authorization helper's blocked signals suppress native cancellation.
    # Restore before even Git's short-lived children can queue a blocked SIGCHLD.
    proof = signal_environment.normalize(
        lambda before: bootstrap.write_new(parent / 'local-signal-environment-before.json', before))
    bootstrap.write_new(parent / 'local-signal-environment.json', proof)
    prepared = admit_source_inputs(parent, expected, config, swift_runtime_only, mac_generator_only, cli_process_only)
    return prepared, proof


class LocalArm(q.Qualification):
    allowed_purposes = (*q.PURPOSES, 'installed-xcodegen', 'phone-runtimes', 'phone-controls',
                        'mobile-driver-producer', 'mac-generator-clock', 'cli-focused-tests-producer', 'cli-process-controls')
    allowed_phases = (*q.PHASES, 'gradle-distribution', 'installed-tools', 'phone-app', 'mobile-driver',
                      'mac-generator-preflight', 'cli-producer', 'cli-process')

    def __init__(self, args):
        local_host(os.environ, platform.system(), platform.machine(), os.getuid(), os.geteuid())
        need(args.owner_authorized_arm27, 'Explicit owner authorization required')
        self.parent = private_parent(args.parent)
        self.swift_runtime_only = args.swift_runtime_only
        self.mac_generator_only = args.mac_generator_only
        self.cli_process_only = args.cli_process_only
        plan = plan_for(self.swift_runtime_only, self.mac_generator_only, self.cli_process_only)
        self.prepared, signals = admit_execution_environment(self.parent, args.expected_commit,
            self.swift_runtime_only, self.mac_generator_only, self.cli_process_only)
        self.runner = runner
        self.checker = module('local_arm_receipts', 'check-audit-receipt.py')
        self.gate = module('local_arm_platform_policy', 'run-platform-tests.py')
        self.policy = module('local_arm_compile_policy', 'run-rpc-hosted-validation.py')
        self.lane, self.admission_only, self.intel_investigation = 'apple-arm64', False, None
        self.state = self.parent / 'state'
        with (self.parent / 'initialize.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            runner.initialize(argparse.Namespace(root=str(ROOT), state=str(self.state),
                expected_commit=args.expected_commit, host='macos-arm64'))
        self.state, self.context = runner.context_at(str(self.state))
        need(not self.context['preexistingOutputPaths'], 'Fresh source outputs required; no automatic cleanup of old work')
        for name in ('private', 'work', 'tmp', 'konan', 'android-user', 'tools'):
            (self.state / name).mkdir(mode=0o700)
        self.private, self.wrapper = self.state / 'private', ROOT / 'gradlew'
        os.environ.update(P2PKIT_AUDIT_STATE_DIR=str(self.state), GRADLE_USER_HOME=self.context['gradleHome'],
            KONAN_DATA_DIR=str(self.state / 'konan'), ANDROID_USER_HOME=str(self.state / 'android-user'),
            TMPDIR=str(self.state / 'tmp'), P2PKIT_GRADLE_EXECUTOR=str(ROOT / 'scripts/run-audit-command.py'),
            P2PKIT_PYTHON3=str(Path(sys.executable).absolute()), P2PKIT_XCODE_JOBS='2',
            PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
        self.unsafe, self.simulator, self.simulator_deleted = False, None, False
        self.kvm = self.advertising_preparation = self.phone_candidate = None
        self.result = dict(schema=1, scope=SCOPE, baseline=BASELINE, acceptedEnvironment='macOS27/Xcode27.0/native-arm64',
            qualificationComplete=False, foundationStatus='NOT_READY', lane=self.lane, admissionOnly=False,
            intelInvestigation=None, source=self.context['source'], result='FAIL', commands=[], phases={}, counts={},
            errors=[], productDiagnostics=dict(logs={}, native={}, simulator=dict(states={})), startedUtc=runner.utc(),
            swiftRuntimeOnly=self.swift_runtime_only, macGeneratorOnly=self.mac_generator_only,
            cliProcessOnly=self.cli_process_only, requestedPlan=list(plan),
            notRequestedPhases=[name for name in PLAN if name not in plan],
            signalEnvironment=signals,
            nativeRerunReason='Fresh product execution session requires its own native-executor admission; prior pure-command proof is not a receipt')
        runner.write_new_json(self.private / 'admission.json', self.result)

    def prepare_gradle_distribution(self):
        # A fresh verified ZIP is the only prepopulated input. The original
        # wrapper still performs SHA-256 validation/extraction and the complete
        # same-home --stop; its 120-second bound and receipt checker are unchanged.
        self.result['gradleDistributionPreparation'] = distribution.stage_archive(
            ROOT, self.parent, self.prepared['gradleDistribution'], self.state, self.context)

    def toolchain(self):
        for major, key in (('17', 'JAVA_HOME'), ('21', 'P2PKIT_AUDIT_JDK21')):
            proof = self.invoke('jdk' + major, [str(Path(os.environ[key]) / 'bin/java'), '-XshowSettings:properties', '-version'], 45)
            raw = self.output(proof, stream='stderr').decode()
            need(re.search(r'(?m)^\s*java\.specification\.version = ' + major + r'\s*$', raw) and
                 re.search(r'(?m)^\s*os\.arch = aarch64\s*$', raw), 'Actual native JDK required')
        sw = self.invoke('macos-version', ['/usr/bin/sw_vers', '-productVersion'], 45)
        xcode = self.invoke('xcode-version', ['/usr/bin/xcodebuild', '-version'], 45)
        environment_versions(self.output(sw), self.output(xcode))
        self.invoke('xcode-first-launch', ['/usr/bin/xcodebuild', '-checkFirstLaunchStatus'], 120)
        native = self.invoke('rosetta-admission', [sys.executable, '-c', q.NATIVE_ROLE_PROBE], 45)
        q.admit_native_apple_role(self.lane, self.output(native))
        self.result['actualToolchain'] = dict(macos=self.output(sw).decode().strip(), xcode=self.output(xcode).decode().splitlines())

    def installed_tools(self):
        original = Path(self.prepared['xcodegen'])
        need(runner.file_digest(original) == self.prepared['xcodegenSha256'], 'Installed XcodeGen changed')
        staged = xcodegen_package.stage(self.prepared['xcodegenPackage'], self.state / 'tools/xcodegen')
        target = Path(staged['executable'])
        directory = target.parent
        need(runner.file_digest(target) == self.prepared['xcodegenSha256'], 'Private XcodeGen copy changed')
        proof = self.invoke('installed-xcodegen', [str(target), '--version'], 45)
        need(self.output(proof).strip() == b'Version: 2.45.4', 'Maintained XcodeGen version required')
        os.environ['PATH'] = str(directory) + os.pathsep + os.environ['PATH']
        self.result['installedTools'] = dict(staged, xcodegenSha256=runner.file_digest(target),
                                             freshGradleAndKonanHomes=True)

    def selected_ios_runtime(self, purpose):
        runtime = super().selected_ios_runtime(purpose)
        need(runtime.get('supportedArchitectures') == ['arm64'], 'Use the installed ARM-only runtime, not a translated guest')
        return runtime

    def phone_app(self):
        handoff = module('local_arm_phone_handoff', 'run-rpc-ios-handoff.py')
        phone = module('local_arm_phone_controls', 'run-rpc-phone-ios-controls.py')
        proof = self.invoke('phone-runtimes', ['/usr/bin/xcrun', 'simctl', 'list', 'runtimes', '--json'], 120)
        runtime = handoff.runtime_selection(json.loads(self.output(proof), object_pairs_hook=runner.unique_object))
        argv = [sys.executable, str(ROOT / 'scripts/run-rpc-phone-ios-controls.py'), '--owner-authorized-phone-controls',
                '--root', str(ROOT), '--directory', str(self.state / 'work/phone-controls'), '--xcodegen',
                str(self.state / 'tools/xcodegen/bin/xcodegen'), '--runtime', runtime]
        outer = self.invoke('phone-controls', argv, handoff.BOUNDS['phone-controls'], allow_failure=True)
        self.result['phoneDiagnostics'], self.result['phoneProducerDiagnostic'] = handoff.phone_observations(
            self.state, self.context, outer, runtime, runner, q)
        need(outer['productExitCode'] == 0, 'Phone controls failed; no export')
        observations, app, manifest = handoff.assess_phone(self.state, self.context, outer, runtime, runner, self.checker, phone)
        self.result['phoneApp'] = observations
        self.phone_candidate = (handoff, app, manifest)

    def mobile_driver(self):
        # Prepare current-source tooling, not another JVM workload or a mobile
        # result. The older transferred driver cannot be relabeled as this SHA.
        directory = ROOT / 'samples/p2p-sample-rpc/build/capacity-lab'
        need(not directory.exists() and not directory.is_symlink(), 'Never replace a prepared distribution')
        proof = self.invoke('mobile-driver-producer', [':p2p-sample-rpc:prepareRpcCapacityLab', *self.policy.FLAGS],
                            1800, 'gradle')
        lab = module('local_arm_prepared_mobile_driver', 'run-rpc-capacity-lab.py')
        jars = lab.classpath(self.context['source']['commit']).split(os.pathsep)
        self.result['mobileDriver'] = dict(sourceSha=self.context['source']['commit'],
            manifestSha256=runner.file_digest(directory / 'manifest.json'), jarCount=len(jars),
            sourceInvocationId=proof['id'], workloadExecuted=False, capacityQualified=False)

    def mac_generator_preflight(self):
        # Independently executable without a phone. This full native clock
        # check is not reusable as admission for a later physical workload:
        # each real attempt must observe its own immediately preceding resources.
        clock = module('local_arm_mac_generator_clock', 'rpc_darwin_capacity.py')
        prior = os.environ.get('RPC_CAPACITY_LAB_AUTHORIZED')
        os.environ['RPC_CAPACITY_LAB_AUTHORIZED'] = 'synthetic-private-network-only'
        try:
            proof = self.invoke('mac-generator-clock', [sys.executable, str(ROOT / 'scripts/rpc_darwin_capacity.py'),
                '--directory', str(self.state / 'work/mobile-clock-arm27-preflight')], 150)
        finally:
            if prior is None:
                os.environ.pop('RPC_CAPACITY_LAB_AUTHORIZED', None)
            else:
                os.environ['RPC_CAPACITY_LAB_AUTHORIZED'] = prior
        value = clock.assess_clock(json.loads(self.output(proof), object_pairs_hook=runner.unique_object))
        self.result['macGeneratorPreflight'] = value
        need(value['healthyForAttempt'], 'Original Mac clock/memory requirements not met; retain the failed observation')

    def cli_producer(self):
        cli = module('local_arm_cli_process_producer', 'rpc_cli_process_controls.py')
        output = ROOT / 'samples/p2p-sample-desktop/build'
        need(not output.exists() and not output.is_symlink(), 'New CLI outputs required; never overwrite evidence')
        tests = [item for name in cli.CLASSES for item in ('--tests', 'dev.p2pkit.sample.desktop.' + name)]
        proof = self.invoke('cli-focused-tests-producer', [':p2p-sample-desktop:test', *tests,
            ':p2p-sample-desktop:installDist', *self.policy.FLAGS], 1800, 'gradle')
        methods = cli.focused_tests()
        manifest = cli.runtime_manifest(self.context['source']['commit'])
        runner.write_new_json(self.private / 'cli-runtime.json', manifest)
        self.result['cliProducer'] = dict(sourceSha=self.context['source']['commit'], sourceInvocationId=proof['id'],
            methods=methods, jarCount=len(manifest['jars']), manifestSha256=runner.file_digest(self.private / 'cli-runtime.json'),
            fullCampaignQualified=False)

    def cli_process(self):
        cli = module('local_arm_cli_process_assessment', 'rpc_cli_process_controls.py')
        prior = os.environ.get('RPC_CAPACITY_LAB_AUTHORIZED')
        os.environ['RPC_CAPACITY_LAB_AUTHORIZED'] = 'synthetic-private-network-only'
        try:
            proof = self.invoke('cli-process-controls', [sys.executable, '-B', str(ROOT / 'scripts/rpc_cli_process_controls.py'),
                '--owner-authorized-cli-controls', '--directory', str(self.state / 'work/cli-process-controls'),
                '--manifest', str(self.private / 'cli-runtime.json')], 3000)
        finally:
            if prior is None:
                os.environ.pop('RPC_CAPACITY_LAB_AUTHORIZED', None)
            else:
                os.environ['RPC_CAPACITY_LAB_AUTHORIZED'] = prior
        value = cli.assess_result(json.loads(self.output(proof), object_pairs_hook=runner.unique_object),
                                  self.context['source']['commit'])
        saved = runner.read_json(self.state / 'work/cli-process-controls/result.json')
        need(value == saved, 'CLI saved result differs from native command output')
        self.result['cliProcess'] = dict(sourceInvocationId=proof['id'], result=value,
            resultSha256=runner.file_digest(self.state / 'work/cli-process-controls/result.json'))

    def finish(self):
        super().finish()  # Original exact simulator deletion, source check and all native finalization predicates.
        if self.phone_candidate and not self.unsafe and self.result.get('simulatorRetired') and \
                self.result.get('sourceAfter') == self.context['source'] and \
                not any('finalizer' in error for error in self.result['errors']):
            handoff, app, manifest = self.phone_candidate
            archive = self.parent / handoff.ARCHIVE
            exported = handoff.export_app(app, archive, manifest, runner)
            runner.write_new_json(self.parent / 'phone-export.json', dict(schema=1, scope=SCOPE,
                source=self.context['source'], artifact=exported, applicationFiles=manifest,
                unsigned=True, physicalInstallable=False, qualificationComplete=False))

    def run(self):
        plan_for(self.swift_runtime_only, self.mac_generator_only, self.cli_process_only)
        try:
            prepared = self.phase('gradle-distribution', self.prepare_gradle_distribution)
            controls = self.phase('native-controls', self.native_controls, prepared)
            tools = self.phase('toolchain', self.toolchain, controls)
            if self.cli_process_only:
                producer = self.phase('cli-producer', self.cli_producer, tools)
                self.phase('cli-process', self.cli_process, producer)
            elif self.mac_generator_only:
                self.phase('mac-generator-preflight', self.mac_generator_preflight, tools)
            else:
                installed = self.phase('installed-tools', self.installed_tools, tools)
                simulator = self.phase('simulator-admission', self.select_simulator, installed)
                producer = self.phase('apple-producer', self.apple_producer, installed)
                project = self.phase('apple-project', self.apple_project, producer)
                self.phase('swift-runtime', self.swift_runtime, project and simulator)
                # Explicit new request, never automatic failure retry or promotion of
                # a different source's passes. The original whole 88+6 action stays
                # intact; unrelated lanes are absent, not reported as new passes.
                if not self.swift_runtime_only:
                    self.phase('owned-swift-lifecycle', lambda: self.owned_swift(False), project and simulator)
                    self.phase('owned-swift-cancellation', lambda: self.owned_swift(True), project and simulator)
                    self.phase('phone-app', self.phone_app, installed)
                    self.phase('mobile-driver', self.mobile_driver, installed)
                    self.phase('mac-generator-preflight', self.mac_generator_preflight, tools)
        finally:
            self.finish()
        return 0 if self.result['result'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--owner-authorized-arm27', action='store_true')
    parser.add_argument('--parent', required=True, type=Path)
    parser.add_argument('--expected-commit', required=True)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--swift-runtime-only', action='store_true',
                        help='Only the original ordinary Swift action, all fresh prerequisites and finalization; not a full run')
    selection.add_argument('--mac-generator-only', action='store_true',
                        help='Only the original 125-second clock/memory check, fresh native admission and finalization')
    selection.add_argument('--cli-process-only', action='store_true',
                        help='Only source-built focused JVM CLI process controls; no clock, Swift, simulator or phone reruns')
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--jdk21', type=Path)
    parser.add_argument('--android-sdk', type=Path)
    parser.add_argument('--xcodegen', type=Path)
    parser.add_argument('--gradle-distribution', type=Path,
                        help='Fresh data-only ZIP matching the checked-in wrapper SHA-256; no extracted/cache input')
    args = parser.parse_args()
    if args.action == 'prepare':
        need(all((args.java_home, args.jdk21, args.android_sdk, args.xcodegen, args.gradle_distribution)),
             'Select installed tools and the pinned distribution input explicitly')
        return prepare(args)
    need(not any((args.java_home, args.jdk21, args.android_sdk, args.xcodegen, args.gradle_distribution)),
         'Run uses only its prepared toolchain and verified data input')
    return LocalArm(args).run()


if __name__ == '__main__':
    sys.exit(main())
