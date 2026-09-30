#!/usr/bin/env python3
"""Offline policy/privacy/failure controls. No Java, SDK, networking, simulator or Gradle execution."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qualification', ROOT / 'scripts/run-rpc-qualification.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def environment():
    return {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'GITHUB_REPOSITORY': 'p2pKit/P2pKit',
            'GITHUB_REF': q.REF, 'GITHUB_EVENT_NAME': 'push', 'RPC_QUALIFY_REQUESTED': 'true', 'GITHUB_SHA': 'a' * 40}


def result():
    return {'source': {'commit': 'a' * 40, 'tree': 'b' * 40}, 'lane': 'apple-x64', 'result': 'FAIL',
            'commands': [], 'counts': {}, 'phases': {}}


class AdmissionTests(unittest.TestCase):
    def test_apple_diagnostic_marker_cannot_admit_products_or_android(self):
        for lane in ('apple-arm64', 'apple-x64'):
            q.admit_commit_marker('CI: diagnose [rpc-apple-admit]', lane, True)
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('CI: diagnose [rpc-apple-admit]', lane, False)
        for mode in (False, True):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('CI: diagnose [rpc-apple-admit]', 'android-art', mode)
        q.admit_commit_marker('CI: [rpc-art]', 'android-art', False)
        for lane in q.HOSTS:
            q.admit_commit_marker('CI: [rpc-admit]', lane, True)
            q.admit_commit_marker('CI: [rpc-qualify]', lane, False)

    def test_explicit_real_host_and_feature_admission(self):
        for lane, (system, machine, *_) in q.HOSTS.items():
            q.admit_event(environment(), system, machine, lane)

    def test_other_sessions_events_repositories_or_hosts_are_rejected(self):
        for name, value in (('GITHUB_ACTIONS', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                            ('GITHUB_REPOSITORY', 'fork/P2pKit'), ('GITHUB_REF', 'refs/heads/main'),
                            ('GITHUB_REF', 'refs/heads/work/release-foundation-20260926-1WzHcOIr'),
                            ('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_EVENT_NAME', 'workflow_dispatch'),
                            ('RPC_QUALIFY_REQUESTED', 'false'), ('GITHUB_SHA', 'HEAD')):
            with self.subTest(name=name, value=value), self.assertRaises(q.QualificationError):
                q.admit_event({**environment(), name: value}, 'Darwin', 'x86_64', 'apple-x64')
        for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')):
            with self.assertRaises(q.QualificationError):
                q.admit_event(environment(), system, machine, 'apple-x64')

    def test_original_readiness_deadlines_and_full_profile_are_preserved(self):
        self.assertEqual(q.BOUNDS, {'native-controls': 1800, 'platform': 7200, 'swift-readiness': 120,
                                   'swift-runtime': 7200, 'art-runtime': 7200, 'multicast-admission': 45,
                                   'archive-controls': 180})
        self.assertIn('task.device.finalizeValue()', q.SIMULATOR_INIT)
        self.assertIn("['iosX64Test', 'iosSimulatorArm64Test']", q.SIMULATOR_INIT)
        self.assertNotIn('enabled = false', q.SIMULATOR_INIT)
        self.assertEqual(q.control_inventory('macos-x64'), 122)
        self.assertEqual(q.control_inventory('macos-arm64'), 122)
        self.assertGreater(q.control_inventory('linux-x64'), 100)

    def test_no_legacy_executor_or_pid_signaling_path(self):
        source = (ROOT / 'scripts/run-rpc-qualification.py').read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ('kill', 'terminate', 'killpg', 'send_signal', 'terminate_process'))
                if isinstance(node.func.value, ast.Attribute) and node.func.value.attr in ('gate', 'policy'):
                    self.assertNotIn(node.func.attr, ('main', 'run', 'execute'))
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertFalse(literals.intersection(('sudo', '/usr/bin/sudo', 'setfacl', 'chmod', 'chown')))
        self.assertNotIn('"kvm-restored"', source)
        self.assertNotIn('"--write-locks"', source)
        self.assertNotIn('"--write-verification-metadata"', source)
        self.assertNotIn('publishToMavenLocal', source)
        self.assertIn('contextlib.redirect_stdout(log)', source)
        self.assertIn('contextlib.redirect_stderr(log)', source)

    def test_actual_xctest_inventory_is_closed_and_nonempty(self):
        cases = q.swift_inventory(ROOT)
        self.assertEqual({k: len(v) for k, v in cases.items()}, {'p2pkit-sample-tests': 88, 'p2pkit-sample-uitests': 6})

    def test_native_controls_reject_skipped_failed_or_partial_output(self):
        self.assertEqual(q.unittest_count('\nRan 122 tests in 190.25s\n\nOK\n'), 122)
        for raw in ('OK', '\nRan 0 tests in 0.0s\nOK', '\nRan 122 tests in 190s\nOK (skipped=1)',
                    '\nRan 122 tests in 190s\nFAILED (failures=1)', '\nRan 122 tests in 190s'):
            with self.subTest(raw=raw), self.assertRaises(q.QualificationError):
                q.unittest_count(raw)


class PrivacyTests(unittest.TestCase):
    def test_public_summary_excludes_arbitrary_private_data(self):
        private = result()
        private.update(errors=['private-password'], rawLog='private-payload', sourceAfter=private['source'],
                       producerIdentity='private-identity', path='/private/evidence')
        private['source']['extra'] = 'private-source-field'
        private['commands'] = [{'purpose': 'jdk17', 'argv': ['private-command'], 'rawExitCode': 0, 'verified': True,
                                'receipt': {'secret': 'private-receipt'}}]
        private['phases'] = {'toolchain': {'status': 'PASS', 'error': 'private-assertion'}}
        text = json.dumps(q.public_summary(private))
        self.assertNotIn('private-', text)
        self.assertNotIn('/private/', text)
        self.assertNotIn('argv', text)
        self.assertIn('NOT_READY', text)

    def test_unknown_summary_values_fail_instead_of_leaking(self):
        for mutate in (lambda r: r.update(lane='private-value'), lambda r: r['source'].update(commit='private-sha'),
                       lambda r: r.update(result='private-error'),
                       lambda r: r['counts'].update(junitPassed='private-count'),
                       lambda r: r['phases'].update(abi={'status': 'private-status'}),
                       lambda r: r['phases'].update(abi={'status': 'FAIL', 'code': 'private-error'}),
                       lambda r: r['commands'].append({'purpose': 'private-label', 'rawExitCode': 1}),
                       lambda r: r.update(multicastMarkers=['private-identity']),
                       lambda r: r.update(controlFailures=[{'method': 'test_private_secret', 'outcome': 'FAIL'}])):
            private = result()
            mutate(private)
            with self.assertRaises(q.QualificationError):
                q.public_summary(private)

    def test_only_source_inventory_control_failures_and_fixed_multicast_markers_survive(self):
        name = 'test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts'
        actual = q.control_failures('FAIL: ' + name + ' (__main__.DarwinNativeTests.' + name + ')\n'
                                    'ERROR: test_secret_password (__main__.Secret)\nprivate trace')
        self.assertEqual(actual, [{'method': name, 'outcome': 'FAIL'}])
        private = result()
        private.update(controlFailures=actual, multicastMarkers=['FAIL mode=control',
            'startup firstSendFailureClass=java.net.NoRouteToHostException firstSendDestinationIpv4Mdns=true'])
        observed = q.public_summary(private)
        self.assertEqual(observed['controlFailures'], actual)
        self.assertEqual(observed['multicastMarkers'], private['multicastMarkers'])

    def test_missing_results_never_imply_readiness(self):
        public = q.public_summary(result())
        self.assertEqual(public['result'], 'FAIL')
        self.assertFalse(public['rpcCapacityQualification'])
        self.assertFalse(public['physicalQualification'])
        self.assertFalse(public['simulatorRetired'])
        self.assertFalse(public['sourceUnchanged'])
        self.assertEqual(public['counts']['swiftUnitPassed'], 0)
        self.assertEqual(public['countsSemantics'], 'ADMITTED_COUNTS_ONLY_NOT_ATTEMPT_COUNTS')


class JunitTests(unittest.TestCase):
    XML = b'<testsuite tests="3" failures="1" errors="0" skipped="1"><testcase/><testcase><failure message="private"/></testcase><testcase><skipped/></testcase><system-out>private payload</system-out></testsuite>'

    def test_counted_cases_and_declared_counts_must_match(self):
        self.assertEqual(q.junit_counts(self.XML), {'passed': 1, 'failed': 1, 'errors': 0, 'skipped': 1})
        for before, after in ((b'tests="3"', b'tests="4"'), (b'failures="1"', b'failures="0"'),
                              (b'errors="0"', b'errors="1"'), (b'skipped="1"', b'skipped="0"'),
                              (b'<skipped/>', b'<skipped/><error/>')):
            with self.assertRaises(q.QualificationError):
                q.junit_counts(self.XML.replace(before, after))

    def test_entities_and_non_suite_root_are_rejected(self):
        for xml in (b'<!DOCTYPE testsuite>' + self.XML, b'<!ENTITY secret "private">' + self.XML,
                    b'<testsuites/>'):
            with self.assertRaises(q.QualificationError):
                q.junit_counts(xml)


class ExecutionBoundaryTests(unittest.TestCase):
    def fixture(self, directory, code=0):
        instance = q.Qualification.__new__(q.Qualification)
        instance.state = Path(directory)
        instance.private = Path(directory) / 'private'
        instance.private.mkdir()
        instance.wrapper = q.ROOT / 'gradlew'
        instance.unsafe = False
        instance.context = {'id': 'job', 'gradleHome': 'home', 'source': {'commit': 'a' * 40}}
        instance.result = {'commands': [], 'phases': {}, 'errors': []}
        proof = {'id': 'test', 'jobId': 'job', 'gradleHome': 'home', 'sourceBefore': instance.context['source'],
                 'ancestorInvocationIds': [], 'ownership': {'discoveryErrors': []}}
        instance.runner = Mock()
        instance.runner.read_json.return_value = proof
        instance.runner.file_digest.return_value = 'c' * 64
        def execute(_):
            sys.stdout.buffer.write(b'private-stdout\n')
            sys.stderr.buffer.write(b'private-stderr\n')
            return code
        instance.runner.main.side_effect = execute
        instance.checker = Mock()
        return instance

    def test_real_file_redirection_retains_raw_bytes_without_public_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.fixture(directory)
            live = io.StringIO()
            with contextlib.redirect_stdout(live), contextlib.redirect_stderr(live):
                instance.invoke('jdk17', ['synthetic', 'private-argument'], 45)
            self.assertNotIn('private-', live.getvalue())
            self.assertIn('private-stdout', (instance.private / 'jdk17.driver.log').read_text())
            self.assertIn('private-stderr', (instance.private / 'jdk17.driver.log').read_text())
            self.assertTrue(instance.result['commands'][0]['verified'])

    def test_failed_product_stays_failed_after_successful_finalization_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.fixture(directory, 1)
            with self.assertRaises(q.QualificationError) as failed:
                instance.invoke('jdk17', ['synthetic'], 45)
            self.assertEqual(failed.exception.code, 'PRODUCT_FAILED')
            self.assertTrue(instance.result['commands'][0]['verified'])
            self.assertFalse(instance.unsafe)
            with self.assertRaises(q.QualificationError):
                instance.invoke('jdk17', ['synthetic'], 45)
            instance.runner.main.assert_called_once()

    def test_invalid_receipt_blocks_later_products(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.fixture(directory)
            instance.checker.validate.side_effect = ValueError('synthetic bad receipt')
            with self.assertRaises(q.QualificationError) as failed:
                instance.invoke('jdk17', ['synthetic'], 45)
            self.assertEqual(failed.exception.code, 'OWNERSHIP_UNPROVEN')
            self.assertTrue(instance.unsafe)
            with self.assertRaises(q.QualificationError):
                instance.invoke('jdk21', ['synthetic'], 45)
            instance.runner.main.assert_called_once()

    def test_blocked_prerequisite_is_not_a_successful_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.fixture(directory)
            operation = Mock()
            self.assertFalse(instance.phase('full-platform', operation, False))
            self.assertEqual(instance.result['phases']['full-platform']['status'], 'BLOCKED_PREREQUISITE')
            operation.assert_not_called()


class DiagnosticTests(unittest.TestCase):
    def test_failed_inner_receipts_export_fixed_failure_and_source_site_not_private_output(self):
        name = 'test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts'
        raw = ('FAIL: ' + name + ' (__main__.DarwinNativeTests.' + name + ')\n'
               'Traceback (most recent call last):\n'
               '  File "/private/secret/scripts/tests/run-audit-command-test.py", line 3271, in ' + name + '\n'
               'AssertionError: private-password\n')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / name
            folder.mkdir()
            path = folder / 'receipt.json'
            path.write_text(json.dumps({'purpose': 'executor-fixture', 'errors': ['AuditError: Product command timed out'],
                                       'productExitCode': None, 'finalExitCode': 125,
                                       'ownedSurvivors': [], 'private': 'private-password'}))
            reader = Mock()
            reader.regular_report_files.return_value = [path]
            actual = q.control_diagnostics(raw, Path(directory), reader)
        self.assertEqual(actual[0]['method'], name)
        self.assertEqual(actual[0]['assertionLines'], [3271])
        self.assertIn('Product command timed out', actual[0]['receipts'][0]['diagnostic']['fixedErrorMessages'])
        self.assertNotIn('private-', json.dumps(actual))
        self.assertNotIn('/private/', json.dumps(actual))
        private = result()
        private['controlDiagnostics'] = actual
        self.assertEqual(q.public_summary(private)['controlDiagnostics'], actual)
        self.assertEqual(q.public_summary(private)['counts']['nativeControlTests'], 0)

    def test_diagnostic_only_accepts_closed_source_methods_lines_and_receipt_schema(self):
        original = [{'method': 'test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts',
                     'assertionLines': [3271], 'receipts': [{'purpose': 'executor-fixture', 'sha256': 'a' * 64,
                                                           'diagnostic': q.receipt_diagnostic({}, '')}]}]
        for mutate in (lambda d: d[0].update(method='test_private_password'),
                       lambda d: d[0].update(assertionLines=[True]),
                       lambda d: d[0].update(assertionLines=[1000000]),
                       lambda d: d[0].update(private='secret'),
                       lambda d: d[0]['receipts'][0].update(purpose='private-purpose'),
                       lambda d: d[0]['receipts'][0].update(raw='private-log'),
                       lambda d: d[0]['receipts'][0].update(sha256='private-path')):
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(q.QualificationError):
                q.validate_control_diagnostics(value)

    def test_darwin_observations_export_only_known_aggregates_not_identity_or_raw_errors(self):
        observation = {
            'observationReconciliations': [
                {'operation': 'task token', 'outcome': 'unresolved', 'identity': {'pid': 12345, 'uid': 501},
                 'firstFailure': 'Darwin task-name access unavailable: Mach result 5',
                 'lastFailure': 'Darwin task-name access unavailable: Mach result 5'},
                {'operation': 'environment', 'outcome': 'recovered', 'private': 'private-secret',
                 'firstFailure': 'Darwin process environment failed: errno 13'}],
            'unclassifiedLifetimes': [
                {'identity': {'pid': 12345, 'status': 3, 'path': '/private/identity'},
                 'firstFailure': 'Darwin task token unresolved after bounded observation: '
                                 'Darwin task-name access unavailable: Mach result 5',
                 'lastFailure': 'Darwin non-reaper original-parent lifetime was not observed'},
                {'lastIdentity': {'status': 2}, 'firstFailure': 'private-error'},
                {'lastIdentity': {'status': 'private-status'}, 'lastFailure': 'private-payload'}]}
        actual = q.darwin_observation_diagnostic(observation)
        self.assertEqual(actual, {'recorded': True, 'operations': {'TASK_TOKEN': 1, 'ENVIRONMENT': 1},
                                 'outcomes': {'UNRESOLVED': 1, 'RECOVERED': 1}, 'pendingCount': 3,
                                 'pendingStates': {'SLEEPING': 1, 'RUNNING': 1, 'OTHER': 1},
                                 'failureKinds': ['ENVIRONMENT_EACCES', 'OTHER', 'PARENT_UNOBSERVED', 'TASK_NAME_FAILURE']})
        self.assertNotIn('private-', json.dumps(actual))
        self.assertNotIn('12345', json.dumps(actual))
        self.assertNotIn('501', json.dumps(actual))

    def test_darwin_diagnostic_rejects_unknown_export_fields_labels_and_inconsistent_counts(self):
        original = q.darwin_observation_diagnostic({})
        self.assertFalse(original['recorded'])
        for mutate in (lambda d: d.update(private='secret'), lambda d: d.update(failureKinds=['private-value']),
                       lambda d: d['operations'].update(PRIVATE=1), lambda d: d['operations'].update(IDENTITY=True),
                       lambda d: d['pendingStates'].update(SLEEPING=1), lambda d: d.update(pendingCount=1025),
                       lambda d: d['outcomes'].update(UNRESOLVED=1), lambda d: d.update(recorded='secret')):
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(q.QualificationError):
                q.validate_darwin_diagnostic(value)
        for observation in ({'unclassifiedLifetimes': [{}] * 1025},
                            {'observationReconciliations': [{'lastFailure': 'x' * 4097}]},
                            {'unclassifiedLifetimes': [1]}):
            with self.assertRaises(q.QualificationError):
                q.darwin_observation_diagnostic(observation)

    def test_prior_diagnostic_schema_remains_readable_without_invented_darwin_counts(self):
        prior = q.receipt_diagnostic({}, '')
        prior.pop('darwinObservations')
        prior.pop('survivorInventoryState')
        prior['ownedSurvivorCount'] = 1  # Historical record count may include UNKNOWN.
        self.assertEqual(q.validate_diagnostic(prior), prior)
        self.assertNotIn('darwinObservations', prior)

    def test_unknown_or_missing_survivors_never_report_a_known_worker_count(self):
        for proof, state in (({}, 'MISSING'), ({'ownedSurvivors': [{'status': 'UNKNOWN', 'reason': 'final drain failed'}]},
                                             'UNKNOWN')):
            diagnostic = q.receipt_diagnostic(proof, '')
            self.assertEqual(diagnostic['survivorInventoryState'], state)
            self.assertIsNone(diagnostic['ownedSurvivorCount'])
            diagnostic['ownedSurvivorCount'] = 0
            with self.assertRaises(q.QualificationError):
                q.validate_diagnostic(diagnostic)
        empty = q.receipt_diagnostic({'ownedSurvivors': []}, '')
        self.assertEqual(empty['survivorInventoryState'], 'KNOWN')
        self.assertEqual(empty['ownedSurvivorCount'], 0)
        empty['ownedSurvivorCount'] = None
        with self.assertRaises(q.QualificationError):
            q.validate_diagnostic(empty)

    def test_failed_receipt_exports_only_fixed_source_messages_counts_and_enums(self):
        proof = {'errors': ['Pre-stop ownership drain failed: private-identity',
                            'OwnershipError: Owned process current context does not match its last domain',
                            'ValueError: private-password'], 'sourceUnchanged': True,
                 'ownedSurvivors': [{'pid': 12345, 'private': 'private-process'}],
                 'ownership': {'discoveryErrors': ['private-census']},
                 'productExitCode': 0, 'stopExitCode': 1, 'finalExitCode': 125}
        diagnostic = q.receipt_diagnostic(proof, 'Exception in thread private-arg\nprivate-password')
        self.assertEqual(diagnostic['errorCount'], 3)
        self.assertEqual(diagnostic['ownedSurvivorCount'], 1)
        self.assertEqual(diagnostic['discoveryErrorCount'], 1)
        self.assertEqual(diagnostic['fixedErrorMessages'], ['Owned process current context does not match its last domain'])
        self.assertEqual(diagnostic['stopMarkers'], ['EXCEPTION'])
        self.assertNotIn('private-', json.dumps(diagnostic))
        self.assertEqual(diagnostic['finalExitCode'], 125)

    def test_unknown_diagnostic_keys_messages_counts_or_status_are_not_exported(self):
        original = q.receipt_diagnostic({}, '')
        for mutate in (lambda d: d.update(private='secret'), lambda d: d.update(productExitCode='secret'),
                       lambda d: d.update(errorKinds=['secret']), lambda d: d.update(stopMarkers=['secret']),
                       lambda d: d.update(fixedErrorMessages=['private-password']), lambda d: d.update(errorCount=-1)):
            diagnostic = copy.deepcopy(original)
            mutate(diagnostic)
            with self.assertRaises(q.QualificationError):
                q.validate_diagnostic(diagnostic)

    def test_attempt_output_never_becomes_admitted_execution_count(self):
        for raw, count, status in (('', 0, 'MISSING_OUTPUT'), ('\nRan 122 tests in 190.3s\n\nOK\n', 122, 'PASS_OUTPUT_ONLY'),
                                   ('\nRan 122 tests in 190.3s\nFAILED (failures=1)\n', 122, 'FAIL_OUTPUT_ONLY')):
            attempt = q.native_attempt(raw)
            self.assertEqual(attempt, {'reportedTests': count, 'status': status, 'executionAdmitted': False})
            private = result()
            private['nativeAttempt'] = attempt
            public = q.public_summary(private)
            self.assertEqual(public['counts']['nativeControlTests'], 0)
            self.assertFalse(public['nativeAttempt']['executionAdmitted'])
        with self.assertRaises(q.QualificationError):
            q.native_attempt('Ran 122 tests in 1s\nRan 122 tests in 2s')

    def test_admission_only_never_runs_product_toolchain_or_simulator_checks(self):
        instance = q.Qualification.__new__(q.Qualification)
        instance.admission_only = True
        instance.native_controls = Mock()
        instance.phase = Mock(return_value=True)
        instance.finish = Mock()
        instance.result = {'result': 'PASS'}
        self.assertEqual(instance.run(), 0)
        instance.phase.assert_called_once_with('native-controls', instance.native_controls)
        instance.finish.assert_called_once_with()
        private = result()
        private['admissionOnly'] = True
        self.assertEqual(q.public_summary(private)['scope'], 'FEATURE_ONLY_EXECUTOR_DIAGNOSTIC_NOT_PRODUCT_QUALIFICATION')


class ArmFollowThroughTests(unittest.TestCase):
    def test_full_arm_matrix_requires_all_four_phases_but_intel_is_not_a_substitute(self):
        for lane in ('apple-arm64', 'apple-x64'):
            instance = q.Qualification.__new__(q.Qualification)
            instance.lane, instance.admission_only = lane, False
            instance.phase, instance.finish = Mock(return_value=True), Mock()
            instance.result = {'result': 'PASS'}
            self.assertEqual(instance.run(), 0)
            labels = [call.args[0] for call in instance.phase.call_args_list]
            self.assertIn('full-platform', labels)
            self.assertIn('swift-runtime', labels)
            if lane == 'apple-arm64':
                self.assertTrue(q.ARM_PHASES <= set(labels))
                self.assertEqual(labels[-1], 'owned-swift-cancellation')
                self.assertLess(labels.index('owned-native-helper-abi'), labels.index('apple-producer'))
            else:
                self.assertFalse(q.ARM_PHASES & set(labels))

    def test_only_created_native_arm_simulator_may_be_retired(self):
        instance = q.Qualification.__new__(q.Qualification)
        instance.invoke, instance.simulator_state = Mock(), Mock(return_value={'state': 'Booted'})
        instance.simulator, instance.simulator_deleted, instance.unsafe = 'owned', False, False
        for lane in ('apple-x64', 'android-art'):
            instance.lane = lane
            with self.assertRaises(q.QualificationError):
                instance.retire_owned_simulator('owned-native-retire')
        instance.lane = 'apple-arm64'
        for value in (None, ''):
            instance.simulator = value
            with self.assertRaises(q.QualificationError):
                instance.retire_owned_simulator('owned-native-retire')
        instance.invoke.assert_not_called()

    def test_retirement_uses_only_exact_device_and_never_awards_test_counts(self):
        instance = q.Qualification.__new__(q.Qualification)
        instance.lane, instance.simulator, instance.simulator_deleted = 'apple-arm64', 'owned', False
        instance.unsafe, instance.result = False, {'counts': {}}
        instance.simulator_state = Mock(side_effect=[{'state': 'Booted'}, {'state': 'Shutdown'}])
        instance.invoke = Mock()
        instance.retire_owned_simulator('owned-native-retire')
        instance.invoke.assert_called_once_with('owned-native-retire-shutdown',
            ['/usr/bin/xcrun', 'simctl', 'shutdown', 'owned'], 120, finalizer=True)
        self.assertEqual(instance.result['counts'], {})
        self.assertFalse(instance.unsafe)

    def test_failed_simulator_retirement_blocks_independent_product_phases(self):
        instance = q.Qualification.__new__(q.Qualification)
        instance.lane, instance.simulator, instance.simulator_deleted = 'apple-arm64', 'owned', False
        instance.unsafe, instance.result = False, {'phases': {}, 'errors': []}
        instance.simulator_state = Mock(return_value={'state': 'Booted'})
        instance.invoke = Mock()
        with self.assertRaises(q.QualificationError):
            instance.retire_owned_simulator('owned-native-retire')
        operation = Mock()
        self.assertFalse(instance.phase('owned-swift-cancellation', operation))
        operation.assert_not_called()
        self.assertTrue(instance.unsafe)

    def test_scoped_swift_always_retires_and_restores_environment_on_execution_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = q.Qualification.__new__(q.Qualification)
            instance.lane, instance.simulator, instance.state = 'apple-arm64', 'owned', Path(directory)
            instance.retire_owned_simulator = Mock()
            instance.invoke = Mock(side_effect=RuntimeError('synthetic execution failure'))
            instance.inspect_swift_result = Mock()
            with patch.dict(os.environ, {'IOS_RUN_DIR': 'original', 'SIM_UDID': 'original-device'}):
                with self.assertRaisesRegex(RuntimeError, 'synthetic execution failure'):
                    instance.owned_swift(True)
                self.assertEqual(os.environ['IOS_RUN_DIR'], 'original')
                self.assertEqual(os.environ['SIM_UDID'], 'original-device')
            self.assertEqual([call.args[0] for call in instance.retire_owned_simulator.call_args_list],
                             ['owned-swift-cancellation-isolate', 'owned-swift-cancellation-retire'])
            instance.inspect_swift_result.assert_not_called()

    def test_maintained_native_and_swift_assessors_not_campaign_execution_are_reused(self):
        source = (ROOT / 'scripts/run-rpc-qualification.py').read_text()
        self.assertIn('maintained.assess_owned_native(', source)
        self.assertIn('role="macos-arm64"', source)
        self.assertIn('"run-owned-cancellation" if cancellation else "run-owned-flow-lifecycle"', source)
        self.assertIn('selection=selection', source)
        self.assertIn('proof["productExitCode"] == 0', source)
        self.assertNotIn('audit/complete-', source)
        self.assertNotIn('Host(', source)
        self.assertIn('required |= ARM_PHASES', source)

    def test_scoped_counts_are_separate_and_cannot_be_boolean_or_private_text(self):
        for name in ('ownedNativePassed', 'ownedSwiftLifecyclePassed', 'ownedSwiftCancellationPassed'):
            private = result()
            private['counts'][name] = 4
            self.assertEqual(q.public_summary(private)['counts'][name], 4)
            for invalid in (True, 'private-secret', -1):
                private['counts'][name] = invalid
                with self.assertRaises(q.QualificationError):
                    q.public_summary(private)


class WorkflowTests(unittest.TestCase):
    def test_feature_only_non_cancelling_fresh_checkout_and_exact_public_upload(self):
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        for text in ('branches: [work/rpc-lan-20260927-054728-8b1b11da]', "'[rpc-qualify]'", 'contents: read',
                     'cancel-in-progress: false', 'fail-fast: false', '"os":"macos-26"', '"os":"macos-15-intel"',
                     '"os":"ubuntu-24.04"', 'Xcode_26.5.app', 'Xcode_26.3.app', 'fetch-tags: false',
                     'persist-credentials: false', 'git fetch --no-tags --unshallow', 'fetch-depth: 1', "'[rpc-admit]'", '--admission-only',
                     'path: ${{ env.RPC_QUALIFICATION_PARENT }}/public/summary.json'):
            self.assertIn(text, source)
        for forbidden in ('cancel-in-progress: true', 'secrets.', 'workflow_dispatch:', 'pull_request:',
                          'actions/cache', 'setup-gradle', 'sudo ', 'setfacl ', 'environment:',
                          'run-rpc-hosted-validation.py', '/evidence/**', '~/.m2'):
            self.assertNotIn(forbidden, source)
        for line in source.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'uses: [A-Za-z0-9/-]+@[0-9a-f]{40} #')

    def test_art_only_matrix_does_not_allocate_or_retry_apple_runners(self):
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        line = next(line for line in source.splitlines() if line.strip().startswith('matrix:'))
        import re
        matrices = [json.loads(value) for value in re.findall(r"'(\{[^']+\})'", line)]
        self.assertEqual(len(matrices), 4)
        self.assertEqual(matrices[0], {'include': [{'lane': 'apple-x64', 'os': 'macos-15-intel',
                                                  'developer': '/Applications/Xcode_26.3.app/Contents/Developer'}]})
        self.assertEqual(matrices[1], {'include': [{'lane': 'android-art', 'os': 'ubuntu-24.04', 'developer': ''}]})
        self.assertEqual({row['lane'] for row in matrices[2]['include']}, {'apple-arm64', 'apple-x64'})
        self.assertEqual({row['lane'] for row in matrices[3]['include']}, set(q.HOSTS))
        self.assertIn("contains(github.event.head_commit.message, '[rpc-art]') &&", line)
        self.assertIn("contains(github.event.head_commit.message, '[rpc-apple-admit]')", line)
        self.assertIn("contains(github.event.head_commit.message, '[rpc-apple-qualify]')", line)
        only = next(line for line in source.splitlines() if line.strip().startswith('RPC_ADMISSION_ONLY:'))
        self.assertIn("contains(github.event.head_commit.message, '[rpc-apple-admit]')", only)
        self.assertEqual(q.control_inventory('linux-x64'), 121)

    def test_full_apple_request_preserves_both_cells_without_admitting_android(self):
        for lane in ('apple-arm64', 'apple-x64'):
            q.admit_commit_marker('[rpc-apple-qualify]', lane, False)
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-apple-qualify]', lane, True)
        with self.assertRaises(q.QualificationError):
            q.admit_commit_marker('[rpc-apple-qualify]', 'android-art', False)
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        only = next(line for line in source.splitlines() if line.strip().startswith('RPC_ADMISSION_ONLY:'))
        self.assertNotIn('[rpc-apple-qualify]', only)
        self.assertIn("if test '${{ matrix.lane }}' != android-art; then", source)
        self.assertIn('scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" --', source)
        self.assertIn('python3 scripts/tests/with-darwin-audit-session-test.py', source)

    def test_intel_admission_marker_cannot_start_products_or_supply_arm_evidence(self):
        q.admit_commit_marker('[rpc-intel-admit]', 'apple-x64', True)
        for lane in q.HOSTS:
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-intel-admit]', lane, False)
        for lane in ('apple-arm64', 'android-art'):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-intel-admit]', lane, True)
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        group = next(line for line in source.splitlines() if line.strip().startswith('group:'))
        self.assertIn("&& 'admission' ||", group)
        self.assertIn('cancel-in-progress: false', source)

    def test_scoped_intel_product_followthrough_preserves_complete_required_matrix(self):
        q.admit_commit_marker('[rpc-intel-qualify]', 'apple-x64', False)
        for lane in q.HOSTS:
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-intel-qualify]', lane, True)
        for lane in ('apple-arm64', 'android-art'):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-intel-qualify]', lane, False)
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        line = next(line for line in source.splitlines() if line.strip().startswith('matrix:'))
        self.assertIn("'[rpc-intel-admit]') || contains(github.event.head_commit.message, '[rpc-intel-qualify]')", line)
        only = next(line for line in source.splitlines() if line.strip().startswith('RPC_ADMISSION_ONLY:'))
        self.assertNotIn('[rpc-intel-qualify]', only)
        group = next(line for line in source.splitlines() if line.strip().startswith('group:'))
        self.assertIn("&& 'intel-product' || 'product'", group)
        self.assertIn('cancel-in-progress: false', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
