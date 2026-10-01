#!/usr/bin/env python3
"""Offline hosted-capacity admission/evidence controls. No products, timers or namespaces."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capacity_job', ROOT / 'scripts/run-rpc-capacity-qualification.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def environment():
    return dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=c.REF, GITHUB_EVENT_NAME='push',
                GITHUB_SHA='a' * 40, GITHUB_WORKSPACE=str(ROOT), RPC_CAPACITY_REQUESTED='true')


def result():
    return dict(schema=1, scope=c.SCOPE, source={'commit': 'a' * 40, 'tree': 'b' * 40}, result='FAIL',
                commands=[], phases={}, workloads={}, foundationStatus='NOT_READY', physicalQualification=False,
                mobileCapacityQualification=False, rpcCapacityQualification=False, sourceUnchanged=True)


class HostedCapacity(unittest.TestCase):
    def test_native_count_requires_every_control_in_the_current_source(self):
        q = c.module('capacity_inventory_control', 'run-rpc-qualification.py')
        expected = q.control_inventory('linux-x64')
        self.assertEqual(expected, 124)
        observed = c.public_result({**result(), 'nativeControlTests': expected}, [], {}, False)
        self.assertEqual(observed['nativeControlTests'], expected)
        for count in (121, expected - 1, expected + 1, True):
            with self.subTest(count=count), self.assertRaisesRegex(RuntimeError, 'Incomplete native controls'):
                c.public_result({**result(), 'nativeControlTests': count}, [], {}, False)

    def test_product_failure_retains_actual_source_bound_diagnostics_before_stopping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            source = root / 'samples/x/src/jvmTest/kotlin/Fixture.kt'
            source.parent.mkdir(parents=True)
            source.write_text('package sample\nclass Fixture {\n fun fails() {}\n}\n')
            state = root / 'state'
            private = state / 'private'
            private.mkdir(parents=True)
            logdir = state / 'evidence' / ('a' * 32)
            logdir.mkdir(parents=True)
            (logdir / 'product.stdout.log').write_text('> Task :p2p-sample-rpc:jvmTest FAILED\nPRIVATE_SECRET\n')
            (logdir / 'product.stderr.log').write_text('e: /private/Fixture.kt:3:2 Unresolved reference PRIVATE_SECRET\n')
            token = 'b' * 32
            argv = ['-Pp2pkit.testCoverageToken=' + token, '-Pp2pkit.testCoverageRoot=' + str(root)]
            report = root / 'build/reports/platform-tests' / token / 'execution.json'
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps(dict(token=token, buildFailed=True)))
            xml = root / 'samples/x/build/test-results/jvmTest/TEST-fixture.xml'
            xml.parent.mkdir(parents=True)
            xml.write_text('<testsuite><testcase classname="sample.Fixture" name="fails">'
                           '<failure>AssertionError at Fixture.kt:3 PRIVATE_SECRET</failure></testcase></testsuite>')
            proof = dict(purpose='jvm-regression', id='a' * 32, kind='gradle', requestedArgv=argv, jobId='job',
                         sourceBefore={}, sourceAfter={}, ancestorInvocationIds=[], errors=[], ownedSurvivors=[],
                         ownership={'discoveryErrors': []}, stopExitCode=0)
            job = object.__new__(c.Job)
            job.result, job.unsafe, job.state, job.private = result(), False, state, private
            job.context = {'id': 'job', 'source': {}}
            job.runner = SimpleNamespace(main=Mock(return_value=1), read_json=Mock(return_value=proof),
                                         file_digest=Mock(return_value='c' * 64))
            job.checker = SimpleNamespace(validate=Mock())
            with patch.object(c, 'ROOT', root):
                with self.assertRaisesRegex(RuntimeError, 'Native command product failed'):
                    job.invoke('jvm-regression', argv, 7200, 'gradle')
                self.assertFalse(job.unsafe)  # Product failure != unproven native finalization.
                self.assertTrue(job.result['commands'][0]['verified'])
                self.assertEqual(job.result['commands'][0]['exitCode'], 1)
                row = job.result['productDiagnostics']
                self.assertEqual(row['jvm']['jvm-regression']['failedMethods'], [['sample.Fixture', 'fails']])
                self.assertFalse(row['jvm']['jvm-regression']['executionAdmitted'])
                self.assertEqual(row, c.product_observation(state, proof))  # Independent re-read.
                self.assertNotIn('PRIVATE_SECRET', json.dumps(c.public_result(job.result, [], {}, False)))
                self.assertNotIn('jvmTests', job.result)
                (logdir / 'product.stderr.log').write_text('Compilation error\n')
                self.assertNotEqual(row, c.product_observation(state, proof))
                report.write_text(json.dumps(dict(token='d' * 32)))
                with self.assertRaisesRegex(RuntimeError, 'another invocation'):
                    c.product_observation(state, proof)
                report.unlink()
                self.assertIsNone(c.product_observation(state, proof)['jvm']['jvm-regression']['buildFailed'])
                for changed in (dict(id='../private'), dict(kind='command'), dict(purpose='clock-preflight'),
                                dict(requestedArgv=argv + argv), dict(requestedArgv=[])):
                    with self.assertRaises(RuntimeError):
                        c.product_observation(state, {**proof, **changed})

    def test_collector_rechecks_diagnostics_and_the_public_schema_cannot_broaden_scope(self):
        source = (ROOT / 'scripts/run-rpc-capacity-qualification.py').read_text()
        collector = source[source.index('def collect():'):source.index('def failed_source_sites')]
        self.assertIn('product_observation(state, proof)', collector)
        self.assertIn("rechecked_diagnostics == result.get('productDiagnostics', {})", collector)
        self.assertLess(collector.index('checker.validate(proof'), collector.index('product_observation(state, proof)'))
        self.assertLess(collector.index('rechecked_diagnostics =='), collector.index('public_result('))
        for value in ({'private': 'PRIVATE_SECRET'}, {'native': {}}, {'androidHost': {}}, {'logs': {}}, []):
            with self.assertRaises(RuntimeError):
                c.public_result({**result(), 'productDiagnostics': value}, [], {}, False)
        with self.assertRaises(ValueError):
            c.public_result({**result(), 'productDiagnostics': {'build': {'jvm-regression': {'raw': 'private'}}}}, [], {}, False)
        target = {'build': {'jvm-regression': {}}}
        with self.assertRaises(RuntimeError):
            c.merge_product_observations(target, {'build': {'jvm-regression': {}}})

    def test_only_the_native_nonroot_feature_runner_is_admitted(self):
        with patch.object(c.platform, 'system', return_value='Linux'), patch.object(c.platform, 'machine', return_value='x86_64'), \
             patch.object(c.os, 'getuid', return_value=1001), patch.object(c.os, 'geteuid', return_value=1001):
            c.admit(environment())
            for key, value in (('GITHUB_REF', 'refs/heads/main'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                               ('RPC_CAPACITY_REQUESTED', 'false'), ('GITHUB_REPOSITORY', 'fork/repo'),
                               ('GITHUB_EVENT_NAME', 'workflow_dispatch'), ('GITHUB_SHA', 'HEAD')):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    c.admit({**environment(), key: value})
            for key in ('getuid', 'geteuid'):
                with patch.object(c.os, key, return_value=0), self.assertRaises(RuntimeError):
                    c.admit(environment())
            with patch.object(c.platform, 'machine', return_value='aarch64'), self.assertRaises(RuntimeError):
                c.admit(environment())

    def test_namespace_setup_does_not_change_host_security_or_reassign_source_ownership(self):
        env = {**environment(), 'JAVA_HOME': '/jdk', 'GH_TOKEN': 'private', 'PYTHONPATH': '/untrusted',
               'P2PKIT_AUDIT_OWNERSHIP_CHAIN': 'not-inherited', 'LD_PRELOAD': '/untrusted'}
        command = c.namespace_command(env, Path('/fixture'), 'steady', 1001, 1001, '/python')
        self.assertEqual(command[:4], ['/usr/bin/sudo', '-n', '/usr/bin/env', '-i'])
        self.assertIn('SUDO_UID=1001', command)
        self.assertIn('SUDO_GID=1001', command)
        self.assertIn('JAVA_HOME=/jdk', command)
        for item in command:
            if item != 'private':  # mount propagation is explicitly private
                self.assertNotIn('private', item)
            self.assertNotIn('untrusted', item)
            self.assertNotIn('not-inherited', item)
        for forbidden in ('--user', '--map-root-user', '--map-users', 'chown', 'sysctl', 'iptables', 'setfacl', 'nsenter'):
            self.assertFalse(any(forbidden in item for item in command))
        self.assertIn('--mount-proc', command)
        self.assertIn('--pid', command)
        self.assertIn('--net', command)
        self.assertIn('--owner-authorized-same-host', command)
        for uid, gid, mode in ((0, 1001, 'steady'), (1001, 0, 'steady'), (True, 1001, 'steady'), (1001, 1001, 'short')):
            with self.assertRaises(RuntimeError):
                c.namespace_command(env, Path('/fixture'), mode, uid, gid, '/python')

    def test_regression_requires_actual_model_and_all_four_fresh_jvm_executions(self):
        policy = json.loads((ROOT / 'gradle/platform-test-policy.json').read_text())
        tasks = {t for m in policy['model'].values() for t in m['tests']}
        records = {t: dict(enabled=True, inGraph=False, outcome='NOT_REQUESTED', passed=0, failed=0, skipped=0) for t in tasks}
        for name in c.MODULES:
            records[':' + name + ':jvmTest'].update(inGraph=True, outcome='EXECUTED', passed=3)
        report = dict(schema=1, token='a' * 32, dryRun=False, buildFailed=False, model=policy['model'],
                      host={'os': 'Linux', 'arch': 'amd64'}, tests=records)
        self.assertEqual(len(c.jvm_execution(report, policy, 'a' * 32)), 4)
        for key, value in (('token', 'b' * 32), ('dryRun', True), ('buildFailed', True), ('schema', True),
                           ('host', {'os': 'Mac OS X', 'arch': 'x86_64'}), ('model', {})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.jvm_execution({**report, key: value}, policy, 'a' * 32)
        for key, value in (('passed', 0), ('passed', True), ('failed', 1), ('skipped', 1), ('inGraph', False),
                           ('outcome', 'UP-TO-DATE'), ('outcome', 'FROM-CACHE'), ('enabled', False)):
            changed = copy.deepcopy(report)
            changed['tests'][':p2p-rpc:jvmTest'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.jvm_execution(changed, policy, 'a' * 32)

    def test_failed_and_partial_results_cannot_award_capacity_or_release_qualification(self):
        r = result()
        public = c.public_result(r, [], {}, False)
        self.assertEqual(public['result'], 'FAIL')
        self.assertFalse(public['rpcCapacityQualification'])
        self.assertEqual(public['foundationStatus'], 'NOT_READY')
        for key, value in (('scope', 'PHYSICAL'), ('foundationStatus', 'READY'), ('physicalQualification', True),
                           ('schema', True), ('source', {'commit': 'private', 'tree': 'b' * 40}),
                           ('mobileCapacityQualification', True), ('rpcCapacityQualification', True), ('secret', 'never-export'),
                           ('phases', {'private-label': 'PASS'}), ('nativeControlTests', 120),
                           ('result', 'MECHANICAL_AND_CLEANUP_PASS_PENDING_RESOURCE_REVIEW')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.public_result({**r, key: value}, [], {}, False)

    def test_public_hashes_and_environment_cannot_contain_arbitrary_data(self):
        for key in ('jvmExecutionSha256', 'distributionManifestSha256'):
            for value in (True, 'not-a-hash', 'a' * 63):
                with self.assertRaises(RuntimeError):
                    c.public_result({**result(), key: value}, [], {}, False)
        with self.assertRaises(RuntimeError):
            c.public_result({**result(), 'environment': {'raw': 'private'}}, [], {}, False)

    def test_native_failure_observations_do_not_become_admitted_counts_or_leak_text(self):
        value = {**result(), 'nativeAttempt': {'reportedTests': 121, 'status': 'FAIL_OUTPUT_ONLY', 'executionAdmitted': False},
                 'controlFailures': [], 'controlDiagnostics': []}
        public = c.public_result(value, [], {}, False)
        self.assertEqual(public['nativeAttempt'], value['nativeAttempt'])
        self.assertNotIn('nativeControlTests', public)
        for field, bad in (('controlFailures', [{'raw': 'private'}]), ('controlDiagnostics', [{'secret': 'private'}]),
                           ('nativeAttempt', {**value['nativeAttempt'], 'executionAdmitted': True})):
            with self.assertRaises(RuntimeError):
                c.public_result({**value, field: bad}, [], {}, False)

    def test_missing_attempt_measurement_stays_unadmitted_not_zero_or_passing(self):
        with tempfile.TemporaryDirectory() as name:
            state = Path(name)
            value = c.failed_attempt(state, 'steady', 1)
            self.assertEqual(value['result'], 'FAIL')
            self.assertIsNone(value['measurement'])
            self.assertEqual(value['sourceSites'], [])
            self.assertIn('UNADMITTED', value['scope'])
            self.assertEqual(value['coordinator'], {'observation': 'MISSING'})
            self.assertTrue(all(v == {'observation': 'MISSING', 'finalizationVerified': False}
                                for v in value['nativeReceipts'].values()))
            self.assertTrue(all(v == {'observation': 'MISSING'} for v in value['jvmLogs'].values()))

    def test_initialization_cannot_replace_the_full_workload_or_native_admission(self):
        source = (ROOT / 'scripts/run-rpc-capacity-qualification.py').read_text()
        self.assertIn("initial = evidence.initialization(client['initialization'])", source)
        self.assertIn("initial['status'] == 'INITIALIZED_NOT_CAPACITY'", source)
        self.assertIn("measurement['measurements']['hostAcceptedDelta']", source)
        self.assertIn("measurement['measurements']['hostCompletedDelta']", source)
        driver = (ROOT / 'samples/p2p-sample-rpc/src/jvmMain/kotlin/dev/p2pkit/sample/rpc/RpcCapacityMain.kt').read_text()
        self.assertLess(driver.index('if (!large) runInitialization(clients, environment)'),
                        driver.index('measured = if (large) runLarge(clients.single()) else runSteady(clients, environment)'))
        self.assertIn('val permits = List(clients.size) { Semaphore(8) }', driver)
        self.assertIn('val end = start + RpcCapacityContract.STEADY_SECONDS * 1_000_000_000L', driver)
        self.assertIn('counters.missedDispatches.get() == 0L', driver)

    def test_actual_log_records_require_one_complete_ordered_measurement_and_cleanup(self):
        init = b'RPC_CAPACITY_INITIALIZATION_JSON:{"status":"INITIALIZED_NOT_CAPACITY"}\n'
        measured = b'RPC_CAPACITY_RESULT_JSON:{"completed":2304000}\n'
        cleanup = b'RPC_CAPACITY_FINAL_JSON:{"cleanupVerified":true}\n'
        self.assertEqual(c.workload_records(init + measured + cleanup, 'steady'),
                         {'initialization': {'status': 'INITIALIZED_NOT_CAPACITY'},
                          'measurement': {'completed': 2304000}, 'cleanup': {'cleanupVerified': True}})
        for mode in ('correctness', 'large'):
            self.assertEqual(set(c.workload_records(measured + cleanup, mode)), {'measurement', 'cleanup'})
            with self.assertRaises(RuntimeError):
                c.workload_records(init + measured + cleanup, mode)
        for raw in (b'', init, init + cleanup, measured + cleanup, measured + init + cleanup,
                    init + cleanup + measured, init + init + measured + cleanup,
                    init + measured + cleanup + measured):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                c.workload_records(raw, 'steady')
        with self.assertRaises(ValueError):
            c.workload_records(init + measured.replace(b'2304000', b'2304000,"completed":0') + cleanup, 'steady')

    def test_original_no_traceback_prerequisite_error_retains_exact_source_site(self):
        message = 'Host readiness failed or timed out'
        path = ROOT / 'scripts/run-rpc-same-host-lab.py'
        line = next(n.lineno for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Name) and n.func.id == 'need' and len(n.args) == 2 and
                    isinstance(n.args[1], ast.Constant) and n.args[1].value == message)
        with tempfile.TemporaryDirectory() as name:
            state = Path(name)
            (state / 'private').mkdir()
            (state / 'private/namespace-steady.log').write_text(
                'Same-host virtual-network experiment failed: ' + message + '\n')
            value = c.failed_attempt(state, 'steady', 125)
        self.assertEqual(value['sourceSites'], [{'script': path.name, 'line': line}])
        self.assertEqual(value['failureLogs']['namespace']['sourceSites'], value['sourceSites'])
        self.assertEqual(value['result'], 'FAIL')
        self.assertIsNone(value['measurement'])

    def test_exhausted_telemetry_observations_retain_the_exact_literal_failure_site(self):
        path = ROOT / 'scripts/run-rpc-capacity-lab.py'
        line = next(n for n, text in enumerate(path.read_text().splitlines(), start=1)
                    if 'raise ControlFileLifetimeChanged("Control file lifetime changed")' in text)
        self.assertEqual(c.failed_source_sites(
            b'Same-host virtual-network experiment failed: Control file lifetime changed\n'),
            [{'script': path.name, 'line': line}])
        self.assertEqual(c.failed_source_sites(
            b'Same-host virtual-network experiment failed: Control file lifetime changed: secret\n'), [])

    def test_failure_location_parser_refuses_private_suffixes_and_outside_source_frames(self):
        for line in ('Host readiness failed or timed out SECRET',
                     'SECRET Host readiness failed or timed out', 'SECRET'):
            self.assertEqual(c.failed_source_sites(('Same-host virtual-network experiment failed: ' + line).encode()), [])
        self.assertEqual(c.failed_source_sites(b'File "/private/credentials.py", line 1, in read'), [])
        with self.assertRaises(RuntimeError):
            c.failed_source_sites(('File "' + str(ROOT / 'scripts/run-rpc-same-host-lab.py') +
                                   '", line 999999, in wrong').encode())
        for mode, code in (('../private', 1), ('steady', True), ('steady', 999)):
            with self.assertRaises(RuntimeError):
                c.failed_attempt(Path('/not-read'), mode, code)

    def test_failed_native_receipts_expose_counts_not_identity_and_never_admit_execution(self):
        with tempfile.TemporaryDirectory() as name:
            state = Path(name)
            directory = state / 'evidence' / ('a' * 32)
            directory.mkdir(parents=True)
            (directory / 'product.stderr.log').write_text('Ran 121 tests in 1.0s\n\nFAILED (failures=1)\n')
            proof = dict(id='a' * 32, errors=['PRIVATE_SECRET', 'Product command timed out'],
                         ownership={'discoveryErrors': ['PRIVATE_SECRET']}, ownedSurvivors=[{'pid': 4242}],
                         sourceUnchanged=True, productExitCode=-15, stopExitCode=0, finalExitCode=125,
                         privateKey='PRIVATE_SECRET')
            path = state / 'receipt.json'
            path.write_text(json.dumps(proof))
            observed = c.failed_native_receipt(state, path, controls=True)
            self.assertEqual(observed['observation'], 'OBSERVED_UNADMITTED')
            self.assertFalse(observed['finalizationVerified'])
            self.assertEqual(observed['diagnostic']['ownedSurvivorCount'], 1)
            self.assertEqual(observed['diagnostic']['discoveryErrorCount'], 1)
            self.assertEqual(observed['diagnostic']['fixedErrorMessages'], ['Product command timed out'])
            self.assertEqual(observed['nativeAttempt'], dict(reportedTests=121, status='FAIL_OUTPUT_ONLY', executionAdmitted=False))
            self.assertNotIn('PRIVATE_SECRET', json.dumps(observed))
            self.assertNotIn('"pid"', json.dumps(observed))
            for bad in ({**proof, 'id': '../private'}, {**proof, 'ownedSurvivors': 'PRIVATE_SECRET'},
                        {**proof, 'productExitCode': True}):
                path.write_text(json.dumps(bad))
                self.assertEqual(c.failed_native_receipt(state, path),
                                 {'observation': 'INVALID', 'finalizationVerified': False})

    def test_failed_coordinator_preserves_cleanup_failure_without_exporting_raw_fields(self):
        raw = dict(scope='SAME_HOST_VIRTUAL_ETHERNET_NOT_PHYSICAL_LAN_OR_DEVICE_QUALIFICATION',
                   mode='steady', status='FAIL', workersReaped=False, sourceUnchanged=True,
                   harnessUnchanged=True, invokingCredentialsPreserved=True,
                   workerExitCodes={'host': -15}, cleanupErrors=['PRIVATE_SECRET'], nativeControlTests=121,
                   source='/PRIVATE_SECRET', keys=['PRIVATE_SECRET'])
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'result.json'
            path.write_text(json.dumps(raw))
            value = c.failed_coordinator(path, 'steady')
            self.assertEqual(value['observation'], 'OBSERVED_UNADMITTED')
            self.assertFalse(value['workersReaped'])
            self.assertEqual(value['cleanupErrorCount'], 1)
            self.assertEqual(value['workerExitCodes'], {'host': -15})
            self.assertNotIn('PRIVATE_SECRET', json.dumps(value))
            for key, changed in (('mode', 'large'), ('status', 'PRIVATE_SECRET'), ('workersReaped', 1),
                                 ('workerExitCodes', {'PRIVATE_SECRET': 0}), ('workerExitCodes', {'host': True})):
                path.write_text(json.dumps({**raw, key: changed}))
                self.assertEqual(c.failed_coordinator(path, 'steady'), {'observation': 'INVALID'})

    def test_failed_jvm_observations_keep_typed_error_and_cleanup_not_payload_or_false_pass(self):
        cleanup = dict(schema=1, mechanicalChecksPassed=False, cleanupVerified=False, capacityQualified=False)
        lines = ['PRIVATE_SECRET', 'ABORTED: RPC Authentication/Negotiation; qualification not established',
                 'SYNTHETIC_HOST_FAILED: host-start/PermissionMissing/Admission; no capacity pass',
                 'SYNTHETIC_HOST_FAILED: PRIVATE_SECRET; setup, telemetry or cleanup failed; no capacity pass',
                 'RPC_CAPACITY_FINAL_JSON:' + json.dumps(cleanup)]
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'jvm.log'
            path.write_text('\n'.join(lines))
            value = c.failed_jvm_log(path)
            self.assertEqual(value['observation'], 'OBSERVED_UNADMITTED')
            self.assertEqual(value['cleanup'], cleanup)
            self.assertFalse(value['steadyScheduleObserved'])
            self.assertEqual(value['failures'], [dict(role='client', kind='Authentication', phase='Negotiation'),
                                               dict(role='host', stage='host-start', kind='PermissionMissing', phase='Admission')])
            self.assertNotIn('PRIVATE_SECRET', json.dumps(value))
            for record in ({**cleanup, 'private': 'PRIVATE_SECRET'}, {**cleanup, 'capacityQualified': True},
                           {**cleanup, 'cleanupVerified': 1}, {**cleanup, 'schema': True}):
                path.write_text('RPC_CAPACITY_FINAL_JSON:' + json.dumps(record))
                self.assertEqual(c.failed_jvm_log(path), {'observation': 'INVALID'})
            path.write_text('\n'.join(['RPC_CAPACITY_FINAL_JSON:' + json.dumps(cleanup)] * 2))
            self.assertEqual(c.failed_jvm_log(path), {'observation': 'INVALID'})

    def test_failed_attempt_collects_each_layer_without_promoting_a_partial_workload(self):
        with tempfile.TemporaryDirectory() as name:
            state = Path(name)
            control = state / 'work/same-host-steady'
            control.mkdir(parents=True)
            (state / 'private').mkdir()
            (state / 'private/namespace-steady.log').write_text(
                'Same-host virtual-network experiment failed: A workload/cleanup failed\n')
            (control / 'client-worker.log').write_text('PRIVATE_SECRET\n')
            (control / 'result.json').write_text(json.dumps(dict(
                scope='SAME_HOST_VIRTUAL_ETHERNET_NOT_PHYSICAL_LAN_OR_DEVICE_QUALIFICATION', mode='steady',
                status='FAIL', workersReaped=True, sourceUnchanged=True, harnessUnchanged=True,
                invokingCredentialsPreserved=True, workerExitCodes={'client': 1, 'host': 0},
                cleanupErrors=[], nativeControlTests=121)))
            for i, role in enumerate(('local-native-controls', 'local-host', 'local-client'), 1):
                identity = str(i) * 32
                directory = state / 'evidence' / identity
                directory.mkdir(parents=True)
                proof = dict(id=identity, errors=[], ownership={'discoveryErrors': []}, ownedSurvivors=[],
                             sourceUnchanged=True, productExitCode=int(role == 'local-client'), stopExitCode=0,
                             finalExitCode=int(role == 'local-client'), private='PRIVATE_SECRET')
                (control / (role + '.json')).write_text(json.dumps(proof))
                if role == 'local-native-controls':
                    (directory / 'product.stderr.log').write_text('Ran 121 tests in 1.0s\n\nOK\n')
            client = state / 'work/local-steady-client'
            client.mkdir()
            (client / 'jvm.log').write_text(
                'ABORTED: RPC DeadlineExceeded/Negotiation; qualification not established\n')
            value = c.failed_attempt(state, 'steady', 125)
            public = c.public_result(result(), [], {'steady': value}, True)
        self.assertEqual(public['result'], 'FAIL')
        self.assertFalse(public['rpcCapacityQualification'])
        self.assertEqual(value['coordinator']['workerExitCodes'], {'client': 1, 'host': 0})
        self.assertEqual(value['jvmLogs']['client']['failures'],
                         [dict(role='client', kind='DeadlineExceeded', phase='Negotiation')])
        self.assertEqual(value['nativeReceipts']['local-native-controls']['nativeAttempt']['reportedTests'], 121)
        self.assertTrue(all(not row['finalizationVerified'] for row in value['nativeReceipts'].values()))
        self.assertIsNone(value['measurement'])
        self.assertTrue(value['sourceSites'])
        self.assertNotIn('PRIVATE_SECRET', json.dumps(public))

    def test_workflow_has_one_opt_in_runner_and_only_the_sanitized_output(self):
        workflow = (ROOT / '.github/workflows/rpc-capacity.yml').read_text()
        for value in ('contents: read', 'cancel-in-progress: false', 'runs-on: ubuntu-24.04',
                      'persist-credentials: false', 'fetch-tags: false', 'git fetch --no-tags --unshallow',
                      "contains(github.event.head_commit.message, '[rpc-capacity]')",
                      'path: ${{ env.RPC_CAPACITY_PARENT }}/public/summary.json',
                      'scripts/run-rpc-capacity-qualification.py run', 'scripts/run-rpc-capacity-qualification.py collect'):
            self.assertIn(value, workflow)
        for forbidden in ('secrets.', 'actions/cache', 'setfacl', 'sysctl', '/evidence/**', 'cancel-in-progress: true',
                          'pull_request:', 'workflow_dispatch:', 'continue-on-error:'):
            self.assertNotIn(forbidden, workflow)
        for line in workflow.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'uses: [A-Za-z0-9/-]+@[0-9a-f]{40} #')

    def test_all_products_use_original_native_owner_and_original_full_workloads(self):
        source = (ROOT / 'scripts/run-rpc-capacity-qualification.py').read_text()
        self.assertIn('self.checker.validate(proof, code, purpose', source)
        self.assertIn('proof[\'ancestorInvocationIds\'] == []', source)
        self.assertIn("q.control_inventory('linux-x64')", source)
        self.assertIn("same.retention_admission(raw['postRetention']['before']", source)
        self.assertIn("checker.validate(proof, code, purpose", source)
        for forbidden in ('killpg(', 'os.kill(', '.terminate(', 'RpcTestLink', '--duration', '--calls-per-second'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
