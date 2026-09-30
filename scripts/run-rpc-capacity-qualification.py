#!/usr/bin/env python3
"""Feature-only hosted SAME-HOST RPC experiment using the maintained native executor.

Never a physical-LAN/mobile/release pass. No restored outputs, credential access,
public RPC port, policy override, namespace UID remapping or raw-PID cleanup.
All measurements and native finalizations are rechecked before bounded export.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_capacity_evidence as evidence

REF = 'refs/heads/work/rpc-lan-20260927-054728-8b1b11da'
MARKER = '[rpc-capacity]'
SCOPE = 'HOSTED_SAME_HOST_VETH_NOT_PHYSICAL_LAN_MOBILE_OR_RELEASE'
MODULES = {'p2p-core': 'library', 'p2p-transport-lan': 'library', 'p2p-rpc': 'library', 'p2p-sample-rpc': 'samples'}
PURPOSES = ('native-controls', 'jdk17', 'jdk21', 'android-compile-platforms', 'jvm-regression', 'capacity-producer', 'clock-preflight')
MODES = ('correctness', 'large', 'steady')
ENVIRONMENT = frozenset(('PATH', 'LANG', 'LC_ALL', 'HOME', 'USER', 'LOGNAME', 'JAVA_HOME', 'P2PKIT_AUDIT_JDK21',
                         'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'ANDROID_USER_HOME', 'KONAN_DATA_DIR',
                         'P2PKIT_AUDIT_STATE_DIR', 'GRADLE_USER_HOME', 'P2PKIT_GRADLE_EXECUTOR',
                         'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED'))


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def admit(env):
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64' and os.getuid() == os.geteuid() != 0,
         'A native nonroot Linux hosted account is required')
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and env.get('RPC_CAPACITY_REQUESTED') == 'true' and
         re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')), 'Explicit feature capacity request required')
    need(Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT, 'Wrong source checkout')


def namespace_command(env, state, mode, uid, gid, python):
    need(mode in MODES and type(uid) is int and type(gid) is int and uid > 0 and gid > 0,
         'Exact invoking nonroot credentials and mode required')
    selected = {k: v for k, v in env.items() if k in ENVIRONMENT}
    need('PATH' in selected and all(type(v) is str and '\0' not in v for v in selected.values()), 'Invalid environment')
    selected.update(SUDO_UID=str(uid), SUDO_GID=str(gid), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    # sudo is solely the private namespace/veth/tmpfs bootstrap. The fixture
    # verifies SUDO_UID/GID against the admitted state owner and drops to that
    # original account plus zero capabilities BEFORE all controls/products.
    return ['/usr/bin/sudo', '-n', '/usr/bin/env', '-i', *[k + '=' + v for k, v in sorted(selected.items())],
            '/usr/bin/unshare', '--mount', '--pid', '--fork', '--mount-proc', '--propagation', 'private', '--net', '--',
            python, '-I', '-S', str(ROOT / 'scripts/run-rpc-same-host-lab.py'), '--owner-authorized-same-host',
            '--state', str(state), '--mode', mode]


def jvm_execution(report, policy, token):
    tasks = {':' + name + ':jvmTest' for name in MODULES}
    need(type(report) is dict and type(report.get('schema')) is int and report['schema'] == 1 and report.get('token') == token and
         report.get('dryRun') is False and report.get('buildFailed') is False and report.get('model') == policy['model'] and
         report.get('host') in ({'os': 'Linux', 'arch': 'amd64'}, {'os': 'Linux', 'arch': 'x86_64'}),
         'Wrong fresh JVM execution/model/architecture')
    records = report.get('tests', {})
    need(set(records) == {task for entry in policy['model'].values() for task in entry['tests']}, 'Missing task inventory')
    for name, row in records.items():
        need(type(row) is dict and type(row.get('failed')) is int and row['failed'] == 0 and row.get('outcome') != 'FAILED',
             'A test task failed')
        if name in tasks:
            need(row.get('inGraph') is True and row.get('enabled') is True and row.get('outcome') == 'EXECUTED' and
                 type(row.get('passed')) is int and row['passed'] > 0 and type(row.get('skipped')) is int and row['skipped'] == 0,
                 'Required JVM tests did not actually execute completely')
    need(tasks <= set(records), 'Required JVM modules missing')
    return {name: {'passed': records[name]['passed'], 'failed': 0, 'skipped': 0} for name in sorted(tasks)}


class Job:
    def __init__(self):
        admit(os.environ)
        self.runner = module('capacity_native_executor', 'run-audit-command.py')
        self.checker = module('capacity_native_checker', 'check-audit-receipt.py')
        self.q = module('capacity_common_diagnostics', 'run-rpc-qualification.py')
        self.same = module('capacity_same_host', 'run-rpc-same-host-lab.py')
        self.lab = module('capacity_lab', 'run-rpc-capacity-lab.py')
        self.parent = self.runner.absolute_path(os.environ['RPC_CAPACITY_PARENT'])
        self.lab.private_directory(self.parent)
        need(self.parent.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve(strict=True)), 'Task-private parent required')
        need(self.runner.git(ROOT, 'rev-parse', '--is-shallow-repository').strip() == b'false' and
             not self.runner.git(ROOT, 'for-each-ref', '--format=%(refname)', 'refs/tags').strip(), 'Full no-tags history required')
        need(MARKER in self.runner.git(ROOT, 'show', '-s', '--format=%B', 'HEAD').decode(), 'Exact intentional commit marker required')
        self.state = self.parent / 'state'
        with (self.parent / 'initialize.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            self.runner.initialize(argparse.Namespace(root=str(ROOT), state=str(self.state),
                expected_commit=os.environ['GITHUB_SHA'], host='linux-x64'))
        self.state, self.context = self.runner.context_at(str(self.state))
        need(not self.context['preexistingOutputPaths'], 'No restored/preexisting product outputs admitted')
        for name in ('private', 'work', 'tmp', 'konan', 'android-user'):
            (self.state / name).mkdir(mode=0o700)
        self.private = self.state / 'private'
        os.environ.update(P2PKIT_AUDIT_STATE_DIR=str(self.state), GRADLE_USER_HOME=self.context['gradleHome'],
            KONAN_DATA_DIR=str(self.state / 'konan'), ANDROID_USER_HOME=str(self.state / 'android-user'),
            TMPDIR=str(self.state / 'tmp'), P2PKIT_GRADLE_EXECUTOR=str(ROOT / 'scripts/run-audit-command.py'),
            PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
        for key in list(os.environ):
            if key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN') or key.upper().startswith(
                    ('SIGNING_', 'ORG_GRADLE_PROJECT_SIGNING', 'MAVEN_CENTRAL_', 'SONATYPE_')):
                os.environ.pop(key)
        self.result = {'schema': 1, 'scope': SCOPE, 'source': self.context['source'], 'result': 'FAIL', 'commands': [],
                       'phases': {}, 'workloads': {}, 'foundationStatus': 'NOT_READY', 'physicalQualification': False,
                       'mobileCapacityQualification': False, 'rpcCapacityQualification': False}
        self.unsafe = False

    def invoke(self, purpose, argv, timeout, kind='command'):
        need(not self.unsafe and purpose in PURPOSES and purpose not in [r['purpose'] for r in self.result['commands']],
             'Cannot repeat or run after unproven native ownership')
        row = {'purpose': purpose, 'verified': False, 'argv': argv, 'exitCode': None}
        self.result['commands'].append(row)
        print('START ' + purpose, flush=True)
        alias = self.private / (purpose + '.json')
        with (self.private / (purpose + '.driver.log')).open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = self.runner.main(['--cwd', str(ROOT), '--wrapper', str(ROOT / 'gradlew'), '--kind', kind,
                '--purpose', purpose, '--timeout', str(timeout), '--receipt', str(alias), '--', *argv])
        row['exitCode'] = code
        try:
            proof = self.runner.read_json(alias)
            self.checker.validate(proof, code, purpose, ROOT, ROOT / 'gradlew', argv)
            need(proof['jobId'] == self.context['id'] and proof['sourceBefore'] == proof['sourceAfter'] == self.context['source'] and
                 proof['ancestorInvocationIds'] == [] and not proof['errors'] and not proof['ownedSurvivors'] and
                 not proof['ownership']['discoveryErrors'] and proof['stopExitCode'] == 0, 'Unproven native finalization')
            need(proof == self.runner.read_json(self.state / 'evidence' / proof['id'] / 'receipt.json'), 'Receipt aliases differ')
            row.update(verified=True, receiptSha256=self.runner.file_digest(alias))
        except BaseException:
            self.unsafe = True
            raise
        print('END ' + purpose + ' exit=' + str(code), flush=True)
        if purpose == 'native-controls':
            raw = self.output(proof, 'stderr').decode()
            self.result['nativeAttempt'] = self.q.native_attempt(raw)
            self.result['controlFailures'] = self.q.control_failures(raw)
            self.result['controlDiagnostics'] = self.q.control_diagnostics(
                raw, self.state / 'evidence/native-controls', self.runner)
        need(code == 0, 'Native command product failed')
        return proof

    def output(self, proof, stream='stdout'):
        return evidence.bounded(self.state / 'evidence' / proof['id'] / ('product.' + stream + '.log'), 64 * 1024 * 1024)

    def phase(self, label, operation, prerequisite=True):
        need(label not in self.result['phases'], 'Repeated phase')
        if not prerequisite or self.unsafe:
            self.result['phases'][label] = 'BLOCKED_PREREQUISITE'
            return False
        try:
            operation()
            self.result['phases'][label] = 'PASS'
            return True
        except Exception:
            self.result['phases'][label] = 'OWNERSHIP_UNPROVEN' if self.unsafe else 'FAIL'
            print('PHASE ' + label + ' ' + self.result['phases'][label], flush=True)
            return False

    def controls(self):
        proof = self.invoke('native-controls', [sys.executable, 'scripts/tests/run-audit-command-test.py',
            '--expected-host', 'linux-x64', '--evidence-dir', str(self.state / 'evidence/native-controls')], 1800)
        count = self.q.unittest_count(self.output(proof, 'stderr').decode())
        need(count == self.q.control_inventory('linux-x64'), 'Incomplete native control inventory')
        self.result['nativeControlTests'] = count

    def toolchain(self):
        for major, key in (('17', 'JAVA_HOME'), ('21', 'P2PKIT_AUDIT_JDK21')):
            proof = self.invoke('jdk' + major, [str(Path(os.environ[key]).resolve(strict=True) / 'bin/java'),
                                                '-XshowSettings:properties', '-version'], 45)
            raw = self.output(proof, 'stderr').decode()
            need(re.search(r'(?m)^\s*java\.specification\.version = ' + major + r'\s*$', raw) and
                 re.search(r'(?m)^\s*os\.arch = amd64\s*$', raw), 'Wrong JDK or architecture')
        self.result['environment'] = {'os': 'Linux', 'arch': 'x86_64', 'jdkMajors': [17, 21],
                                      'before': evidence.clock_snapshot()}
        base = Path(os.environ['ANDROID_HOME']).resolve(strict=True)
        sdk = self.state / 'work/sdk'
        sdk.mkdir()
        for name in ('cmdline-tools/latest', 'licenses'):
            need((base / name).is_dir(), 'Preinstalled SDK tools/licenses missing')
            shutil.copytree(base / name, sdk / name)
        os.environ.pop('ANDROID_SDK_ROOT', None)
        os.environ['ANDROID_HOME'] = str(sdk)
        self.invoke('android-compile-platforms', [str(sdk / 'cmdline-tools/latest/bin/sdkmanager'),
            '--sdk_root=' + str(sdk), 'platforms;android-36', 'platforms;android-37.0', 'platform-tools'], 900)

    def regression(self):
        gate = module('capacity_coverage_policy', 'run-platform-tests.py')
        token = uuid.uuid4().hex
        report_path = ROOT / 'build/reports/platform-tests' / token / 'execution.json'
        need(not report_path.parent.exists(), 'Fresh coverage path required')
        self.invoke('jvm-regression', [*(':' + name + ':jvmTest' for name in MODULES), *gate.FLAGS,
            '--init-script', str(ROOT / 'gradle/platform-test-coverage.init.gradle'),
            '-Pp2pkit.testCoverageRoot=' + str(ROOT), '-Pp2pkit.testCoverageToken=' + token,
            '--no-configure-on-demand', '--warning-mode=fail', '--stacktrace'], 7200, 'gradle')
        results = jvm_execution(gate.read_json(report_path), gate.read_json(ROOT / 'gradle/platform-test-policy.json'), token)
        for name, container in MODULES.items():
            counts = dict(passed=0, failed=0, errors=0, skipped=0)
            files = sorted((ROOT / container / name / 'build/test-results/jvmTest').glob('TEST-*.xml'))
            need(0 < len(files) <= 4096, 'Missing JVM XML')
            for path in files:
                for key, value in self.q.junit_counts(evidence.bounded(path)).items():
                    counts[key] += value
            need(counts.pop('errors') == 0 and counts == results[':' + name + ':jvmTest'], 'XML/execution counts differ')
        self.result['jvmTests'] = results
        self.result['jvmExecutionSha256'] = evidence.file_hash(report_path)

    def producer(self):
        gate = module('capacity_producer_flags', 'run-platform-tests.py')
        self.invoke('capacity-producer', [':p2p-sample-rpc:prepareRpcCapacityLab', *gate.FLAGS,
                                          '--no-configure-on-demand', '--warning-mode=fail', '--stacktrace'], 3600, 'gradle')
        self.lab.classpath(self.context['source']['commit'])
        manifest = ROOT / 'samples/p2p-sample-rpc/build/capacity-lab/manifest.json'
        self.result['distributionManifestSha256'] = evidence.file_hash(manifest)

    def preflight(self):
        proof = self.invoke('clock-preflight', [sys.executable, str(Path(__file__).resolve()), 'clock'], 150)
        observed = evidence.clock_evidence(json.loads(self.output(proof), object_pairs_hook=evidence.unique))
        # No latency pass threshold or different workload is inferred from this control.
        need(observed['scope'] == 'INDEPENDENT_CLOCK_PREFLIGHT_NOT_CAPACITY' and observed['capacityQualified'] is False,
             'Wrong timer control')
        self.result['clockPreflight'] = observed
        need(observed['healthyForAttempt'] is True, 'Generator environment failed the conservative attempt preflight')

    def workload(self, mode):
        need(not self.unsafe, 'Cannot run after unproven native ownership')
        argv = namespace_command(os.environ, self.state, mode, os.getuid(), os.getgid(), str(Path(sys.executable).resolve()))
        print('START same-host-' + mode, flush=True)
        with (self.private / ('namespace-' + mode + '.log')).open('x') as log:
            code = subprocess.call(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        self.result['workloads'][mode] = {'namespaceExitCode': code, 'result': 'FAIL'}
        try:
            review = review_workload(self.state, self.context, mode)
        except Exception:
            # A namespace/process exit alone cannot establish native cleanup. Do
            # not launch another workload after an uninspectable experiment.
            self.unsafe = True
            raise
        self.result['workloads'][mode].update(review)
        print('END same-host-' + mode + ' exit=' + str(code), flush=True)
        need(code == 0 and review['result'] == 'MECHANICAL_AND_CLEANUP_PASS_PENDING_RESOURCE_REVIEW',
             'Same-host workload failed')

    def run(self):
        try:
            controls = self.phase('native-controls', self.controls)
            tools = self.phase('toolchain', self.toolchain, controls)
            regression = self.phase('jvm-regression', self.regression, tools)
            producer = self.phase('capacity-producer', self.producer, regression)
            # Exercise the same new hosted fixture cheaply before the full workload.
            correctness = self.phase('correctness', lambda: self.workload('correctness'), producer)
            large = self.phase('large', lambda: self.workload('large'), correctness)
            clock = self.phase('clock-preflight', self.preflight, large)
            self.phase('steady', lambda: self.workload('steady'), clock)
        finally:
            self.result['sourceUnchanged'] = self.runner.source_snapshot(ROOT) == self.context['source']
            if 'environment' in self.result:
                self.result['environment']['after'] = evidence.clock_snapshot()
            if self.result['sourceUnchanged'] and not self.unsafe and len(self.result['phases']) == 8 and all(
                    p == 'PASS' for p in self.result['phases'].values()):
                self.result['result'] = 'MECHANICAL_AND_CLEANUP_PASS_PENDING_RESOURCE_REVIEW'
            self.runner.write_new_json(self.private / 'result.json', self.result)
        return 0 if self.result['result'].startswith('MECHANICAL_') else 1


def review_workload(state, context, mode):
    """Re-read actual source/JARs, receipts, topology, counters, retention and cleanup."""
    same = module('capacity_review_same_host', 'run-rpc-same-host-lab.py')
    runner = module('capacity_review_executor', 'run-audit-command.py')
    checker = module('capacity_review_checker', 'check-audit-receipt.py')
    lab = module('capacity_review_lab', 'run-rpc-capacity-lab.py')
    q = module('capacity_review_counts', 'run-rpc-qualification.py')
    need(mode in MODES and runner.source_snapshot(ROOT) == context['source'], 'Source changed')
    lab.classpath(context['source']['commit'])
    control = state / 'work' / ('same-host-' + mode)
    raw = evidence.read(control / 'result.json')
    need(raw['scope'] == same.SCOPE and raw['mode'] == mode and raw['attempt'] == 1 and
         raw['source'] == raw['harnessSource'] == context['source'] and raw['sourceUnchanged'] is True and
         raw['harnessUnchanged'] is True and raw['harnessSha256'] == evidence.file_hash(ROOT / 'scripts/run-rpc-same-host-lab.py') and
         raw['invokingCredentialsPreserved'] is True and raw['physicalLanQualified'] is False and raw['deviceCapacityQualified'] is False and
         raw['workersReaped'] is True and raw['cleanupErrors'] == [], 'Unproven source or native fixture finalization')
    proofs = []
    for purpose in ('local-native-controls', 'local-host', 'local-client'):
        path = control / (purpose + '.json')
        proof = runner.read_json(path)
        code = proof['finalExitCode']
        checker.validate(proof, code, purpose, ROOT, ROOT / 'gradlew', proof['requestedArgv'])
        need(proof == runner.read_json(state / 'evidence' / proof['id'] / 'receipt.json') and
             proof['jobId'] == context['id'] and proof['sourceBefore'] == proof['sourceAfter'] == context['source'] and
             not proof['errors'] and not proof['ownership']['discoveryErrors'] and not proof['ownedSurvivors'] and
             proof['ancestorInvocationIds'] == [] and proof['stopExitCode'] == 0, 'Native receipt failed')
        if purpose == 'local-native-controls':
            count = q.unittest_count(evidence.bounded(state / 'evidence' / proof['id'] / 'product.stderr.log').decode())
            need(code == 0 and count == raw['nativeControlTests'] == q.control_inventory('linux-x64') and
                 evidence.file_hash(path) == raw['nativeReceiptSha256'], 'Missing full namespace admission')
        else:
            role = purpose.removeprefix('local-')
            final = evidence.read(control / (role + '-final.json'))
            need(final['nativeFinalizationVerified'] is True and final['exitCode'] == raw['workerExitCodes'][role] == code and
                 final['source'] == context['source'] and final['receiptSha256'] == evidence.file_hash(path), 'Worker result differs')
        proofs.append({'purpose': purpose, 'exitCode': code, 'nativeFinalizationVerified': True, 'sha256': evidence.file_hash(path)})
    topology = evidence.read(control / 'network-setup.json')
    need(topology['invokingUid'] == os.getuid() and topology['invokingGid'] == os.getgid(), 'Wrong invoking account')
    for role in ('host', 'client'):
        t = topology['topology'][role]
        same.topology_admission(t['links'], t['routes'], t['addresses'], role)
    client_dir, host_dir = [state / 'work' / ('local-' + mode + '-' + role) for role in ('client', 'host')]
    client, host = [evidence.read(p / 'launcher-result.json') for p in (client_dir, host_dir)]
    for role, value in (('client', client), ('host', host)):
        need(value['sourceSha'] == context['source']['commit'] and value['mode'] == mode and value['role'] == role and
             value['runLabel'] == 'same-host-' + mode and value['capacityQualified'] is False and
             value['launcherSha256'] == evidence.file_hash(ROOT / 'scripts/run-rpc-capacity-lab.py'), 'Launcher source differs')
    for directory, file in ((client_dir, 'clients-closed.txt'), (host_dir, 'host-closed.txt')):
        need(lab.parse(lab.read_private(directory / file)) == {'closed': 'true', 'fixturesRemoved': 'true'}, 'Fixtures not retired')
    lines = evidence.bounded(client_dir / 'jvm.log').splitlines()
    parsed = {}
    for line in lines:
        for prefix, field in ((b'RPC_CAPACITY_RESULT_JSON:', 'measurement'), (b'RPC_CAPACITY_FINAL_JSON:', 'cleanup')):
            if line.startswith(prefix):
                need(field not in parsed, 'Duplicate actual JVM record')
                parsed[field] = json.loads(line[len(prefix):], object_pairs_hook=evidence.unique)
    need(parsed == {k: client[k] for k in ('measurement', 'cleanup')} and client['cleanup']['cleanupVerified'] is True,
         'Actual JVM output and launcher records differ')
    measurement = client['measurement']
    if mode == 'correctness':
        need(lab.correctness_result(measurement), 'Real-socket correctness cases failed/incomplete')
    else:
        measurement = evidence.measurement(measurement, mode)
    samples = []
    for path in sorted(host_dir.glob('sample-*.txt')):
        values = lab.parse(lab.read_private(path))
        need(values.pop('schema') == '1' and values.pop('runLabel') == 'same-host-' + mode and
             all(v.isascii() and v.isdecimal() for v in values.values()), 'Invalid numeric host sample')
        sample = {k: int(v) for k, v in values.items()}
        need(sample['sequence'] == len(samples), 'Missing host sample')
        samples.append(sample)
    series = evidence.host_series(samples)
    need(same.retention_admission(raw['postRetention']['before'], raw['postRetention']['after']) == raw['postRetention'],
         'Original idle-retention gate failed')
    need(type(raw['elapsedIncludingProvisioningSeconds']) in (int, float) and
         math.isfinite(raw['elapsedIncludingProvisioningSeconds']) and 0 < raw['elapsedIncludingProvisioningSeconds'] < 3000,
         'Invalid actual workload duration')
    result = {'result': 'FAIL', 'scope': same.SCOPE, 'measurement': measurement, 'hostSeries': series,
              'postRetention': raw['postRetention'], 'proofs': proofs, 'nativeControlTests': raw['nativeControlTests'],
              'elapsedIncludingProvisioningSeconds': raw['elapsedIncludingProvisioningSeconds'],
              'topologyVerified': True, 'separateProcesses': True, 'invokingCredentialsPreserved': True,
              'workersReaped': True, 'syntheticIdentitiesRetired': True,
              'hashes': {k: evidence.file_hash(p) for k, p in {
                  'coordinator': control / 'result.json', 'topology': control / 'network-setup.json',
                  'clientLog': client_dir / 'jvm.log', 'clientLauncher': client_dir / 'launcher-result.json',
                  'hostLauncher': host_dir / 'launcher-result.json'}.items()}}
    if mode == 'steady':
        analyzer = module('capacity_schedule_analyzer', 'analyze-rpc-capacity-diagnostics.py')
        result['generatorDiagnostics'] = analyzer.analyze(evidence.bounded(client_dir / 'jvm.log'),
            analyzer.read_timings(sorted(client_dir.glob('jvm-timing.log*'))))
    if (raw['status'] == 'COMPLETED_PENDING_RESOURCE_REVIEW_SAME_HOST_ONLY' and
            all(p['exitCode'] == 0 for p in proofs) and client['cleanup']['mechanicalChecksPassed'] is True and
            all(v['exitCode'] == 0 and v['status'] == 'PENDING_RESOURCE_AND_NETWORK_REVIEW' for v in (client, host)) and
            measurement['status'] == 'PENDING_RESOURCE_AND_NETWORK_REVIEW'):
        result['result'] = 'MECHANICAL_AND_CLEANUP_PASS_PENDING_RESOURCE_REVIEW'
    return result


def collect():
    admit(os.environ)
    runner = module('capacity_collector_executor', 'run-audit-command.py')
    checker = module('capacity_collector_checker', 'check-audit-receipt.py')
    parent = runner.absolute_path(os.environ['RPC_CAPACITY_PARENT'])
    state = parent / 'state'
    _, context = runner.context_at(str(state))
    result = evidence.read(state / 'private/result.json')
    need(result['source'] == context['source'] and result['source']['commit'] == os.environ['GITHUB_SHA'] and
         runner.source_snapshot(ROOT) == context['source'], 'Collector source differs')
    command_rows = []
    invalid = False
    for row in result['commands']:
        need(row['purpose'] in PURPOSES, 'Unknown command')
        observed = {'purpose': row['purpose'], 'verified': False, 'exitCode': row['exitCode']}
        need(observed['exitCode'] is None or type(observed['exitCode']) is int and -255 <= observed['exitCode'] <= 255,
             'Invalid command exit')
        try:
            proof = runner.read_json(state / 'private' / (row['purpose'] + '.json'))
            checker.validate(proof, row['exitCode'], row['purpose'], ROOT, ROOT / 'gradlew', row['argv'])
            need(row['verified'] is True and row['receiptSha256'] == runner.file_digest(
                state / 'evidence' / proof['id'] / 'receipt.json'), 'Receipt alias differs')
            need(proof == runner.read_json(state / 'evidence' / proof['id'] / 'receipt.json') and
                 proof['jobId'] == context['id'] and proof['sourceBefore'] == proof['sourceAfter'] == context['source'] and
                 proof['ancestorInvocationIds'] == [] and not proof['errors'] and not proof['ownedSurvivors'] and
                 not proof['ownership']['discoveryErrors'] and proof['stopExitCode'] == 0,
                 'Collector requires the original exact context and finalization')
            observed.update(verified=True, receiptSha256=row['receiptSha256'])
        except Exception:
            invalid = True
        command_rows.append(observed)
    workloads = {}
    for mode, row in result['workloads'].items():
        need(mode in MODES and type(row['namespaceExitCode']) is int and -255 <= row['namespaceExitCode'] <= 255,
             'Invalid workload mode/exit')
        try:
            reviewed = review_workload(state, context, mode)
            need({k: v for k, v in row.items() if k != 'namespaceExitCode'} == reviewed,
                 'Workload evidence changed before collection')
            workloads[mode] = {**reviewed, 'namespaceExitCode': row['namespaceExitCode']}
        except Exception:
            invalid = True
            workloads[mode] = failed_attempt(state, mode, row['namespaceExitCode'])
    # Serialize only fields constructed from closed validated shapes. No raw log,
    # identity, endpoint, key, process PID or arbitrary exception is exported.
    public = public_result(result, command_rows, workloads, invalid)
    target = parent / 'public'
    target.mkdir(mode=0o700)
    runner.write_new_json(target / 'summary.json', public)
    print('CAPACITY ' + result['result'] + '; same-host only; independent resource review required', flush=True)
    return 0


def failed_attempt(state, mode, code):
    """Closed diagnostic only, never native admission or a passing workload."""
    output = {'scope': 'FAILED_UNADMITTED_ATTEMPT_NOT_QUALIFICATION', 'result': 'FAIL', 'namespaceExitCode': code,
              'sourceSites': [], 'measurement': None}
    log = state / 'private' / ('namespace-' + mode + '.log')
    if log.is_file():
        raw = evidence.bounded(log, 8 * 1024 * 1024)
        output['namespaceLogSha256'] = hashlib.sha256(raw).hexdigest()
        for file in ('run-rpc-same-host-lab.py', 'run-rpc-capacity-lab.py'):
            path = ROOT / 'scripts' / file
            for match in re.finditer(r'File "' + re.escape(str(path)) + r'", line ([0-9]+), in ', raw.decode(errors='replace')):
                line = int(match[1])
                need(1 <= line <= len(path.read_text().splitlines()), 'Invalid source-bound failure location')
                row = {'script': file, 'line': line}
                if row not in output['sourceSites']:
                    output['sourceSites'].append(row)
    path = state / 'work' / ('local-' + mode + '-client/launcher-result.json')
    if path.is_file() and mode != 'correctness':
        try:
            output['measurement'] = evidence.measurement(evidence.read(path)['measurement'], mode)
        except (ValueError, KeyError):
            pass  # Invalid/partial measurement stays explicitly None and unadmitted.
    return output


def public_result(result, commands, workloads, invalid):
    required = {'schema', 'scope', 'source', 'result', 'commands', 'phases', 'workloads', 'foundationStatus',
                'physicalQualification', 'mobileCapacityQualification', 'rpcCapacityQualification', 'sourceUnchanged'}
    optional = {'nativeControlTests', 'environment', 'jvmTests', 'jvmExecutionSha256', 'distributionManifestSha256', 'clockPreflight'}
    diagnostic = {'nativeAttempt', 'controlFailures', 'controlDiagnostics'}
    need(type(result) is dict and required <= set(result) <= required | optional | diagnostic and
         type(result['schema']) is int and result['schema'] == 1 and
         result['scope'] == SCOPE and result['foundationStatus'] == 'NOT_READY' and result['physicalQualification'] is False and
         result['mobileCapacityQualification'] is False and result['rpcCapacityQualification'] is False and
         type(result['sourceUnchanged']) is bool and
         result['result'] in ('FAIL', 'MECHANICAL_AND_CLEANUP_PASS_PENDING_RESOURCE_REVIEW'), 'Invalid public result')
    phases = result['phases']
    need(type(phases) is dict and set(phases) <= {'native-controls', 'toolchain', 'jvm-regression', 'capacity-producer',
         'correctness', 'large', 'clock-preflight', 'steady'} and
         all(v in ('PASS', 'FAIL', 'OWNERSHIP_UNPROVEN', 'BLOCKED_PREREQUISITE') for v in phases.values()), 'Invalid phases')
    public = {k: result[k] for k in required - {'commands', 'source', 'workloads'}}
    need(type(result['source']) is dict and all(type(result['source'].get(k)) is str and
         re.fullmatch('[0-9a-f]{40}', result['source'][k]) for k in ('commit', 'tree')), 'Invalid public source identity')
    public.update(source={k: result['source'][k] for k in ('commit', 'tree')}, commands=commands, workloads=workloads)
    if invalid:
        public['result'] = 'FAIL'
    if diagnostic & set(result):
        # Reuse the maintained closed native-control schema; never export an
        # exception, private source path, raw test log or process identity.
        q = module('capacity_public_control_diagnostics', 'run-rpc-qualification.py')
        sanitized = q.public_summary({'source': public['source'], 'lane': 'android-art', 'result': 'FAIL',
                                     **{k: result[k] for k in diagnostic if k in result}})
        public.update({k: sanitized[k] for k in diagnostic})
    for name in ('jvmExecutionSha256', 'distributionManifestSha256'):
        if name in result:
            need(type(result[name]) is str and re.fullmatch('[0-9a-f]{64}', result[name]), 'Invalid digest')
            public[name] = result[name]
    if 'nativeControlTests' in result:
        need(type(result['nativeControlTests']) is int and result['nativeControlTests'] == 121, 'Incomplete native controls')
        public['nativeControlTests'] = result['nativeControlTests']
    if 'environment' in result:
        env = result['environment']
        need(type(env) is dict and set(env) == {'os', 'arch', 'jdkMajors', 'before', 'after'} and env['os'] == 'Linux' and
             env['arch'] == 'x86_64' and env['jdkMajors'] == [17, 21], 'Invalid environment')
        public['environment'] = {**env, 'before': evidence.snapshot(env['before']), 'after': evidence.snapshot(env['after'])}
    if 'clockPreflight' in result:
        public['clockPreflight'] = evidence.clock_evidence(result['clockPreflight'])
    if 'jvmTests' in result:
        need(type(result['jvmTests']) is dict and set(result['jvmTests']) == {':' + name + ':jvmTest' for name in MODULES},
             'Incomplete JVM modules')
        for counts in result['jvmTests'].values():
            evidence.numbers(counts, ('passed', 'failed', 'skipped'))
            need(counts['passed'] > 0 and counts['failed'] == counts['skipped'] == 0, 'Failed/incomplete JVM suite')
        public['jvmTests'] = result['jvmTests']
    if public['result'].startswith('MECHANICAL_'):
        need(len(phases) == 8 and all(v == 'PASS' for v in phases.values()) and set(workloads) == set(MODES) and
             all(w['result'] == public['result'] and w['namespaceExitCode'] == 0 for w in workloads.values()) and
             len(commands) == len(PURPOSES) and {c['purpose'] for c in commands} == set(PURPOSES) and
             all(c['verified'] is True and c['exitCode'] == 0 for c in commands) and
             public['sourceUnchanged'] is True and optional <= set(public), 'Incomplete evidence cannot pass')
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'collect', 'clock'))
    args = parser.parse_args()
    if args.operation == 'clock':
        print(json.dumps(evidence.clock_control(), sort_keys=True))
        return 0
    return Job().run() if args.operation == 'run' else collect()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('Capacity qualification failed: ' + type(error).__name__ + '; no qualification claim', file=sys.stderr)
        raise SystemExit(1)
