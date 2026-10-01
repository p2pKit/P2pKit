#!/usr/bin/env python3
"""Offline policy/privacy/failure controls. No Java, SDK, networking, simulator or Gradle execution."""
import ast
import contextlib
import copy
import ctypes
import errno
import importlib.util
import io
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
spec = importlib.util.spec_from_file_location('qualification', ROOT / 'scripts/run-rpc-qualification.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def environment():
    return {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'GITHUB_REPOSITORY': 'p2pKit/P2pKit',
            'GITHUB_REF': q.REF, 'GITHUB_EVENT_NAME': 'push', 'RPC_QUALIFY_REQUESTED': 'true', 'GITHUB_SHA': 'a' * 40,
            'RPC_APPLE_LANE': 'apple-x64'}


def result():
    return {'source': {'commit': 'a' * 40, 'tree': 'b' * 40}, 'lane': 'apple-x64', 'result': 'FAIL',
            'commands': [], 'counts': {}, 'phases': {}}


class AdmissionTests(unittest.TestCase):
    def test_advertising_request_requires_matching_cli_environment_and_exact_native_scope(self):
        env = {**environment(), 'RPC_APPLE_BONJOUR_ADVERTISING': 'true', 'RPC_APPLE_TERMINAL_CONTEXT': 'true'}
        for mode in ('network', 'native', None):
            q.admit_advertising_request(True, 'apple-x64', False, mode, env)
        arm_env = {**env, 'RPC_APPLE_LANE': 'apple-arm64'}
        q.admit_advertising_request(True, 'apple-arm64', False, None, arm_env)
        for lane, candidate in (('apple-arm64', env), ('apple-x64', arm_env)):
            with self.assertRaises(q.QualificationError):
                q.admit_advertising_request(True, lane, False, None, candidate)
        for missing in (None, 'false', '', 'TRUE', '1', True):
            with self.subTest(missing=missing), self.assertRaises(q.QualificationError):
                q.admit_advertising_request(True, 'apple-x64', False, 'network',
                                            {**env, 'RPC_APPLE_BONJOUR_ADVERTISING': missing})
        for required, lane, admission, mode in ((False, 'apple-x64', False, 'network'),
                (True, 'apple-arm64', False, 'network'), (True, 'android-art', False, 'network'),
                (True, 'apple-x64', True, 'network'), (True, 'apple-x64', True, 'native'),
                (True, 'apple-x64', False, 'cold-boot'), (True, 'apple-x64', True, None)):
            with self.subTest(lane=lane, mode=mode, required=required, admission=admission), self.assertRaises(q.QualificationError):
                q.admit_advertising_request(required, lane, admission, mode, env)
        with self.assertRaises(q.QualificationError):
            q.admit_advertising_request(True, 'apple-x64', False, 'network', {**env, 'RPC_APPLE_TERMINAL_CONTEXT': 'false'})
        for flag in (None, 'false'):
            for lane in q.HOSTS:
                q.admit_advertising_request(False, lane, False, None, {'RPC_APPLE_BONJOUR_ADVERTISING': flag})
            for mode in (None, 'native'):
                with self.assertRaises(q.QualificationError):
                    q.admit_advertising_request(False, 'apple-x64', False, mode,
                        {'RPC_APPLE_BONJOUR_ADVERTISING': flag, 'RPC_APPLE_TERMINAL_CONTEXT': 'true'})

    def test_lost_nested_advertising_request_stops_before_native_work(self):
        argv = ['run-rpc-qualification.py', 'run', '--lane', 'apple-x64', '--intel-investigation', 'network',
                '--require-bonjour-advertising']
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, {}, clear=True), \
                patch.object(q, 'Qualification') as qualification, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(q.main(), 1)
            qualification.assert_not_called()
        env = {'RPC_APPLE_BONJOUR_ADVERTISING': 'true', 'RPC_APPLE_TERMINAL_CONTEXT': 'true',
               'RPC_APPLE_LANE': 'apple-x64'}
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, env, clear=True), \
                patch.object(q, 'Qualification') as qualification:
            qualification.return_value.run.return_value = 23  # Fixture return, NOT native success.
            self.assertEqual(q.main(), 23)
            qualification.assert_called_once_with('apple-x64', False, 'network')
            qualification.return_value.run.assert_called_once_with()

    def test_native_apple_role_requires_exact_api_output_not_empty_cli_success(self):
        for lane, role in (('apple-x64', b'macos-x64\n'), ('apple-arm64', b'macos-arm64\n')):
            q.admit_native_apple_role(lane, role)
            for wrong in (b'', b'0\n', b'1\n', b'macos-x64\nmacos-arm64\n', b'linux-x64\n',
                          b'macos-arm64\n' if lane == 'apple-x64' else b'macos-x64\n'):
                with self.assertRaises(q.QualificationError):
                    q.admit_native_apple_role(lane, wrong)
        with self.assertRaises(q.QualificationError):
            q.admit_native_apple_role('android-art', b'linux-x64\n')
        native = Mock(return_value='macos-x64')
        output = io.StringIO()
        with patch.dict(sys.modules, audit_processes=SimpleNamespace(host_role=native)), \
                patch.object(sys, 'path', list(sys.path)), contextlib.redirect_stdout(output):
            exec(q.NATIVE_ROLE_PROBE, {})
        native.assert_called_once_with()
        self.assertEqual(output.getvalue(), 'macos-x64\n')

    def test_maintained_native_api_accepts_intel_enoent_but_rejects_translation_and_query_errors(self):
        native = q.module('rpc_test_native_role', 'audit_processes.py')

        class Query:
            def __init__(self, result, error, value=0, size=4):
                self.result, self.error, self.value, self.size = result, error, value, size

            def __call__(self, name, value, length, new, size):
                self_test.assertEqual(name, b'sysctl.proc_translated')
                self_test.assertIsNone(new)
                value._obj.value, length._obj.value = self.value, self.size
                ctypes.set_errno(self.error)
                return self.result

        self_test = self
        for machine, query, expected in (
                ('x86_64', Query(-1, errno.ENOENT), 'macos-x64'),
                ('x86_64', Query(0, 0), 'macos-x64'), ('arm64', Query(0, 0), 'macos-arm64'),
                ('x86_64', Query(0, 0, value=1), None), ('x86_64', Query(0, 0, size=8), None),
                ('x86_64', Query(-1, errno.EACCES), None), ('x86_64', Query(-1, errno.EIO), None)):
            with patch.object(native.platform, 'system', return_value='Darwin'), \
                    patch.object(native.platform, 'machine', return_value=machine), \
                    patch.object(native.ctypes, 'CDLL', return_value=SimpleNamespace(sysctlbyname=query)):
                if expected:
                    self.assertEqual(native.host_role(), expected)
                else:
                    with self.assertRaises(native.OwnershipError):
                        native.host_role()

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
        self.assertEqual(q.control_inventory('macos-x64'), 128)
        self.assertEqual(q.control_inventory('macos-arm64'), 128)
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
    def test_recorded_pending_context_has_no_admission_and_rejects_private_labels_or_counts(self):
        observation = {'unclassifiedLifetimes': [{'identity': {'status': 2}}],
            'unclassifiedContext': {'scope': 'RECORDED_CONTEXT_NOT_OWNERSHIP_OR_EXIT',
                'roles': {'xctest': 1}, 'parentage': {'OWNED': 1}}}
        actual = q.darwin_observation_diagnostic(observation)
        self.assertEqual(actual['pendingCount'], 1)
        self.assertEqual(actual['pendingContext'], observation['unclassifiedContext'])
        for field, change in (('roles', {'private-name': 1}), ('parentage', {'private-parent': 1}),
                              ('roles', {'xctest': True}), ('roles', {'xctest': 0}),
                              ('parentage', {'OWNED': 2})):
            bad = copy.deepcopy(actual)
            bad['pendingContext'][field] = change
            with self.assertRaises(q.QualificationError):
                q.validate_darwin_diagnostic(bad)
        for field in ('pid', 'path', 'environment', 'cleanupVerified'):
            bad = copy.deepcopy(actual)
            bad['pendingContext'][field] = 'private'
            with self.assertRaises(q.QualificationError):
                q.validate_darwin_diagnostic(bad)

    def test_product_timeout_remains_failed_and_is_not_misattributed_to_recovered_exec_observations(self):
        proof = dict(errors=['AuditError: Product command timed out'], sourceUnchanged=True,
            productExitCode=-15, stopExitCode=0, finalExitCode=125, ownedSurvivors=[], ownership={
                'discoveryErrors': [], 'unclassifiedLifetimes': [], 'observationReconciliations': [{
                    'operation': 'environment', 'outcome': 'recovered',
                    'firstFailure': 'Darwin exec version changed during observation',
                    'lastFailure': 'Darwin exec version changed during observation'}]})
        result = q.receipt_diagnostic(proof, 'No Gradle daemons are running.')
        self.assertEqual(result['errorKinds'], ['PRODUCT_DEADLINE_EXCEEDED'])
        self.assertEqual(result['errorCount'], 1)
        self.assertEqual(result['darwinObservations']['outcomes'], {'RECOVERED': 1})
        self.assertEqual(result['darwinObservations']['pendingCount'], 0)
        self.assertEqual(result['finalExitCode'], 125)
        checker = q.module('timeout_still_fails_receipt', 'check-audit-receipt.py')
        with self.assertRaises(ValueError):
            checker.validate({**proof, 'schema': 1}, 125, 'intel-cold-boot-readiness', ROOT, ROOT / 'gradlew', [])

    def test_receipt_timing_exports_relative_intervals_not_timestamps_or_identity(self):
        proof = {'durationSeconds': 23.125, 'startedUtc': '2026-10-01T00:00:00+00:00',
                 'productStartedUtc': '2026-10-01T00:00:01+00:00',
                 'productEndedUtc': '2026-10-01T00:00:21+00:00',
                 'stopStartedUtc': '2026-10-01T00:00:21.500000+00:00',
                 'stopEndedUtc': '2026-10-01T00:00:22+00:00',
                 'endedUtc': '2026-10-01T00:00:23.125000+00:00', 'private': 'PRIVATE_SECRET'}
        timing = q.receipt_diagnostic(proof, '')['timing']
        self.assertEqual(timing, {'elapsedMillis': 23125, 'wallIntervalsMillis': {
            'beforeProduct': 1000, 'product': 20000, 'beforeStop': 500, 'stop': 500, 'afterStop': 1125}})
        self.assertNotIn('2026-', json.dumps(timing))
        self.assertNotIn('PRIVATE_SECRET', json.dumps(timing))
        self.assertEqual(q.validate_timing(timing), timing)

    def test_missing_or_reversed_wall_observations_do_not_fabricate_deadline_success(self):
        self.assertNotIn('timing', q.receipt_diagnostic({}, ''))
        timing = q.receipt_timing({'durationSeconds': 2,
                                  'productStartedUtc': '2026-10-01T00:00:03+00:00',
                                  'productEndedUtc': '2026-10-01T00:00:02+00:00'})
        self.assertEqual(timing['elapsedMillis'], 2000)
        self.assertEqual(timing['wallIntervalsMillis'], {
            'beforeProduct': None, 'product': -1000, 'beforeStop': None, 'stop': None, 'afterStop': None})
        self.assertNotIn('executionAdmitted', timing)

    def test_receipt_timing_rejects_invalid_private_or_unbounded_values(self):
        for duration in (None, True, -1, float('nan'), float('inf'), 172801, 'PRIVATE_SECRET'):
            with self.subTest(duration=duration), self.assertRaises(q.QualificationError):
                q.receipt_timing({'durationSeconds': duration})
        for timestamp in ('PRIVATE_SECRET', True, '2026-10-01T00:00:00', '2026-99-99T00:00:00+00:00'):
            with self.subTest(timestamp=timestamp), self.assertRaises(q.QualificationError):
                q.receipt_timing({'durationSeconds': 1, 'startedUtc': timestamp})
        timing = q.receipt_timing({'durationSeconds': 1})
        for change in ({'elapsedMillis': True}, {'pid': 1}, {'wallIntervalsMillis': {'PRIVATE_SECRET': 1}}):
            with self.subTest(change=change), self.assertRaises(q.QualificationError):
                q.validate_timing({**timing, **change})

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


class PlatformSimulatorLifecycleTests(unittest.TestCase):
    def fixture(self, lane):
        instance = q.Qualification.__new__(q.Qualification)
        instance.lane, instance.simulator, instance.simulator_deleted = lane, 'owned', False
        instance.unsafe, instance.result = False, {'counts': {}, 'phases': {}, 'errors': []}
        instance.invoke = Mock()
        return instance

    def test_both_platform_roles_retire_only_the_exact_created_device(self):
        for lane in ('apple-x64', 'apple-arm64'):
            with self.subTest(lane=lane):
                instance = self.fixture(lane)
                instance.simulator_state = Mock(side_effect=[{'state': 'Booted'}, {'state': 'Shutdown'}])
                instance.retire_created_simulator('platform-native-retire')
                instance.invoke.assert_called_once_with('platform-native-retire-shutdown',
                    ['/usr/bin/xcrun', 'simctl', 'shutdown', 'owned'], 120, finalizer=True)
                self.assertEqual(instance.result['counts'], {})
                self.assertFalse(instance.unsafe)

    def test_already_shutdown_is_verified_without_restart_reset_or_extra_boot(self):
        instance = self.fixture('apple-x64')
        instance.simulator_state = Mock(return_value={'state': 'Shutdown'})
        instance.retire_created_simulator('platform-native-isolate')
        instance.invoke.assert_not_called()
        self.assertEqual([call.args for call in instance.simulator_state.call_args_list],
                         [('platform-native-isolate-before', True), ('platform-native-isolate-after', True)])

    def test_platform_helper_cannot_supply_arm_followthrough_or_adopt_a_device(self):
        for lane, prefix, device, deleted in (
                ('apple-x64', 'owned-native-retire', 'owned', False),
                ('android-art', 'platform-native-retire', 'owned', False),
                ('apple-x64', 'arbitrary', 'owned', False),
                ('apple-arm64', 'platform-native-retire', None, False),
                ('apple-x64', 'platform-native-retire', 'owned', True)):
            with self.subTest(lane=lane, prefix=prefix, device=device, deleted=deleted):
                instance = self.fixture(lane)
                instance.simulator, instance.simulator_deleted = device, deleted
                instance.simulator_state = Mock()
                with self.assertRaises(q.QualificationError):
                    instance.retire_created_simulator(prefix)
                instance.invoke.assert_not_called()
                instance.simulator_state.assert_not_called()

    def test_native_invocation_failure_still_retires_before_any_assessment(self):
        for full in (False, True):
            with self.subTest(full=full):
                instance = self.fixture('apple-x64')
                instance.sim_init = Path('/owned/binding.gradle')
                instance.gate = SimpleNamespace(PROFILES={'full': ['check'], 'ios-x64': [':p2p-core:iosX64Test']}, FLAGS=[])
                instance.retire_created_simulator = Mock()
                instance.invoke.side_effect = RuntimeError('synthetic execution failure')
                with self.assertRaisesRegex(RuntimeError, 'synthetic execution failure'):
                    instance.platform_tests(full)
                self.assertEqual([call.args[0] for call in instance.retire_created_simulator.call_args_list],
                                 ['platform-native-isolate', 'platform-native-retire'])
                self.assertEqual(instance.result['counts'], {})
                self.assertEqual(instance.invoke.call_args.args[2], q.BOUNDS['platform'])

    def test_full_profile_keeps_each_runtime_failure_before_strict_assessment(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(q, 'ROOT', Path(directory)):
            root = Path(directory)
            token = 'a' * 32
            coverage = root / 'build/reports/platform-tests' / token / 'execution.json'
            report = {'buildFailed': True, 'tests': {}}
            instance = self.fixture('apple-arm64')
            instance.sim_init, instance.private = Path('/owned/binding.gradle'), root
            instance.result['productDiagnostics'] = {'native': {}}
            instance.retire_created_simulator = Mock()
            def product(*args, **kwargs):
                coverage.parent.mkdir(parents=True)
                coverage.write_text('{}')
                return {'productExitCode': 1}
            instance.invoke = Mock(side_effect=product)
            instance.runner = Mock()
            instance.gate = SimpleNamespace(PROFILES={'full': ['check']}, FLAGS=[],
                read_json=Mock(side_effect=[report, {}]),
                assess=Mock(side_effect=q.QualificationError('product failed')))
            with patch.object(q.uuid, 'uuid4', return_value=SimpleNamespace(hex=token)), \
                    patch.object(q.product_diagnostics, 'native_observation',
                                 side_effect=lambda root, report, family='native': {'family': family}) as observe:
                with self.assertRaises(q.QualificationError):
                    instance.platform_tests(True)
            self.assertEqual(instance.result['productDiagnostics'], {
                family: {'full-platform': {'family': family}} for family in ('native', 'androidHost', 'jvm')})
            self.assertEqual(observe.call_count, 3)
            self.assertEqual(instance.result['counts'], {})
            instance.gate.assess.assert_called_once()

    def test_unproven_retirement_blocks_later_product_work(self):
        instance = self.fixture('apple-x64')
        instance.simulator_state = Mock(return_value={'state': 'Booted'})
        with self.assertRaises(q.QualificationError):
            instance.retire_created_simulator('platform-native-retire')
        operation = Mock()
        self.assertFalse(instance.phase('swift-runtime', operation))
        operation.assert_not_called()
        self.assertTrue(instance.unsafe)

    def test_swift_cannot_adopt_a_headless_native_boot_as_gui_readiness(self):
        instance = self.fixture('apple-x64')
        instance.simulator_state = Mock(return_value={'state': 'Booted'})
        with self.assertRaises(q.QualificationError):
            instance.swift_runtime()
        instance.invoke.assert_not_called()
        self.assertEqual(q.BOUNDS['swift-readiness'], 120)


class ArmFollowThroughTests(unittest.TestCase):
    def test_native_helper_has_one_immutable_device_binding_and_always_retires(self):
        instance = q.Qualification.__new__(q.Qualification)
        instance.lane, instance.simulator, instance.sim_init = 'apple-arm64', 'owned-device', Path('/owned/binding.gradle')
        instance.retire_owned_simulator = Mock()
        instance.invoke = Mock(side_effect=RuntimeError('synthetic execution failure'))
        instance.retained_report = Mock()
        with self.assertRaisesRegex(RuntimeError, 'synthetic execution failure'):
            instance.owned_native_helper()
        purpose, argv, bound, kind = instance.invoke.call_args.args
        self.assertEqual((purpose, bound, kind), ('owned-native-helper-abi', q.BOUNDS['platform'], 'gradle'))
        self.assertEqual(argv[:3], [':p2p-transport-lan:iosSimulatorArm64Test', '--tests',
                                   'dev.p2pkit.transport.lan.IosOwnedFlowCollectionTest'])
        self.assertIn(':p2p-transport-lan:checkKotlinAbi', argv)
        self.assertNotIn('--device', argv)
        self.assertNotIn('owned-device', argv)
        self.assertEqual(argv.count(str(instance.sim_init)), 1)
        self.assertEqual(argv[argv.index(str(instance.sim_init)) - 1], '--init-script')
        self.assertIn('task.device.finalizeValue()', q.SIMULATOR_INIT)
        self.assertIn("if (task.device.get() != System.getenv('P2PKIT_SELECTED_SIMULATOR'))", q.SIMULATOR_INIT)
        self.assertEqual([call.args[0] for call in instance.retire_owned_simulator.call_args_list],
                         ['owned-native-isolate', 'owned-native-retire'])
        instance.retained_report.assert_not_called()

    def test_full_arm_matrix_requires_all_four_phases_but_intel_is_not_a_substitute(self):
        for lane in ('apple-arm64', 'apple-x64'):
            instance = q.Qualification.__new__(q.Qualification)
            instance.lane, instance.admission_only = lane, False
            instance.intel_investigation = None
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
        self.assertEqual(len(matrices), 9)
        diagnostic, native_only, network_only, runtime_only, *matrices = matrices
        self.assertEqual(diagnostic, {'include': [
            {'lane': 'apple-x64', 'os': 'macos-15-intel',
             'developer': '/Applications/Xcode_26.3.app/Contents/Developer', 'investigation': mode}
            for mode in ('native', 'cold-boot')]})
        self.assertEqual(native_only, {'include': [diagnostic['include'][0]]})
        self.assertEqual(network_only, {'include': [{**diagnostic['include'][0], 'investigation': 'network'}]})
        self.assertEqual(runtime_only, {'include': [{**diagnostic['include'][0], 'investigation': 'runtime'}]})
        self.assertEqual(matrices[0], {'include': [{'lane': 'apple-x64', 'os': 'macos-15-intel',
                                                  'developer': '/Applications/Xcode_26.3.app/Contents/Developer'}]})
        self.assertEqual(matrices[1], {'include': [{'lane': 'apple-arm64', 'os': 'macos-26',
                                                  'developer': '/Applications/Xcode_26.5.app/Contents/Developer'}]})
        self.assertEqual(matrices[2], {'include': [{'lane': 'android-art', 'os': 'ubuntu-24.04', 'developer': ''}]})
        self.assertEqual({row['lane'] for row in matrices[3]['include']}, {'apple-arm64', 'apple-x64'})
        self.assertEqual({row['lane'] for row in matrices[4]['include']}, set(q.HOSTS))
        self.assertIn("contains(github.event.head_commit.message, '[rpc-art]') &&", line)
        self.assertIn("contains(github.event.head_commit.message, '[rpc-apple-admit]')", line)
        self.assertIn("contains(github.event.head_commit.message, '[rpc-apple-qualify]')", line)
        only = next(line for line in source.splitlines() if line.strip().startswith('RPC_ADMISSION_ONLY:'))
        self.assertIn("contains(github.event.head_commit.message, '[rpc-apple-admit]')", only)
        self.assertEqual(q.control_inventory('linux-x64'), 127)

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
        self.assertIn("&& 'intel-product' ||", group)
        self.assertIn('cancel-in-progress: false', source)

    def test_scoped_arm_product_request_cannot_replace_intel_or_skip_native_followthrough(self):
        q.admit_commit_marker('[rpc-arm-qualify]', 'apple-arm64', False)
        for lane in q.HOSTS:
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-arm-qualify]', lane, True)
        for lane in ('apple-x64', 'android-art'):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-arm-qualify]', lane, False)
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        line = next(line for line in source.splitlines() if line.strip().startswith('matrix:'))
        self.assertIn("contains(github.event.head_commit.message, '[rpc-arm-qualify]') &&", line)
        # Check the actual earlier guard, not just the list of matrix values:
        # putting ARM in the Intel guard would allocate the wrong native host.
        intel_guard = line.split("' || ", 4)[4].split(' && ', 1)[0]
        self.assertEqual(intel_guard,
                         "(contains(github.event.head_commit.message, '[rpc-intel-admit]') || "
                         "contains(github.event.head_commit.message, '[rpc-intel-qualify]'))")
        only = next(line for line in source.splitlines() if line.strip().startswith('RPC_ADMISSION_ONLY:'))
        self.assertNotIn('[rpc-arm-qualify]', only)
        group = next(line for line in source.splitlines() if line.strip().startswith('group:'))
        self.assertIn("&& 'arm-product' || 'product'", group)
        self.assertIn('cancel-in-progress: false', source)


class IntelInvestigationTests(unittest.TestCase):
    def setUp(self):
        # Offline fixtures choose their own mode, regardless of the hosting job's
        # explicit real-run configuration. The A/B tests opt in independently.
        self.env = patch.dict(os.environ, RPC_APPLE_BONJOUR_ADVERTISING='false')
        self.env.start()
        self.addCleanup(self.env.stop)

    def fixture(self, mode):
        instance = q.Qualification.__new__(q.Qualification)
        instance.lane, instance.admission_only, instance.intel_investigation = 'apple-x64', False, mode
        instance.simulator, instance.simulator_deleted, instance.unsafe = 'owned', False, False
        instance.result = {'result': 'FAIL', 'counts': {}, 'phases': {}, 'errors': [],
                           'productDiagnostics': {'logs': {}, 'native': {}, 'simulator': {'states': {}}}}
        instance.invoke = Mock()
        return instance

    def test_separate_marker_and_mode_cannot_admit_full_products_arm_or_art(self):
        for mode in ('native', 'cold-boot'):
            q.admit_commit_marker('[rpc-intel-investigate]', 'apple-x64', False, mode)
            for lane, admission in (('apple-x64', True), ('apple-arm64', False), ('android-art', False)):
                with self.assertRaises(q.QualificationError):
                    q.admit_commit_marker('[rpc-intel-investigate]', lane, admission, mode)
            for marker in ('[rpc-qualify]', '[rpc-admit]', '[rpc-apple-admit]', '[rpc-intel-admit]',
                           '[rpc-intel-qualify]', '[rpc-arm-qualify]', '[rpc-apple-qualify]', '[rpc-art]'):
                for message in (marker, marker + ' [rpc-intel-investigate]'):
                    with self.assertRaises(q.QualificationError):
                        q.admit_commit_marker(message, 'apple-x64', False, mode)
        for mode in (None, 'unknown'):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker('[rpc-intel-investigate]', 'apple-x64', False, mode)

    def test_native_only_diagnostic_does_not_repeat_boot_or_admit_any_product_lane(self):
        marker = '[rpc-intel-native-investigate]'
        q.admit_commit_marker(marker, 'apple-x64', False, 'native')
        for lane in q.HOSTS:
            for mode in (None, 'native', 'cold-boot', 'network'):
                for admission in (False, True):
                    if (lane, mode, admission) == ('apple-x64', 'native', False):
                        continue
                    with self.subTest(lane=lane, mode=mode, admission=admission), self.assertRaises(q.QualificationError):
                        q.admit_commit_marker(marker, lane, admission, mode)
        for other in ('[rpc-intel-network-investigate]', '[rpc-intel-investigate]', '[rpc-qualify]', '[rpc-admit]', '[rpc-apple-admit]',
                      '[rpc-intel-admit]', '[rpc-intel-qualify]', '[rpc-arm-qualify]', '[rpc-apple-qualify]', '[rpc-art]'):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker(marker + ' ' + other, 'apple-x64', False, 'native')
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        line = next(line for line in source.splitlines() if line.strip().startswith('matrix:'))
        guard, value = line.split("' || ", 2)[1].split(' && ', 1)
        self.assertEqual(guard, "contains(github.event.head_commit.message, '[rpc-intel-native-investigate]')")
        self.assertEqual(json.loads(value[1:]), {'include': [{'lane': 'apple-x64', 'os': 'macos-15-intel',
            'developer': '/Applications/Xcode_26.3.app/Contents/Developer', 'investigation': 'native'}]})

    def test_original_required_phase_inventories_remain_complete(self):
        apple = {'native-controls', 'toolchain', 'tool-installation', 'archive-controls', 'multicast-admission',
                 'simulator-admission', 'full-platform', 'abi', 'dokka', 'rpc-frameworks', 'swift-api', 'sbom',
                 'apple-producer', 'apple-project', 'swift-runtime'}
        self.assertEqual(q.required_phases('apple-x64', False), apple)
        self.assertEqual(q.required_phases('apple-arm64', False), apple | q.ARM_PHASES)
        self.assertEqual(q.required_phases('android-art', False),
                         {'native-controls', 'toolchain', 'kvm-admission', 'art-runtime'})
        for lane in q.HOSTS:
            self.assertEqual(q.required_phases(lane, True), {'native-controls'})
        self.assertEqual(q.required_phases('apple-x64', False, 'cold-boot'),
                         {'native-controls', 'toolchain', 'simulator-admission', 'intel-cold-boot'})
        self.assertEqual(q.required_phases('apple-x64', False, 'native'),
                         {'native-controls', 'toolchain', 'simulator-admission', 'tool-installation',
                          'multicast-admission', 'scoped-native'})
        self.assertEqual(q.required_phases('apple-x64', False, 'network'),
                         {'native-controls', 'toolchain', 'simulator-admission', 'apple-network-diagnostic'})
        for lane in ('apple-arm64', 'android-art', 'unknown'):
            with self.assertRaises(q.QualificationError):
                q.required_phases(lane, False, 'native')

    def test_cold_boot_runs_no_preceding_native_or_swift_products_and_always_finalizes(self):
        for mode in ('native', 'cold-boot'):
            instance = self.fixture(mode)
            instance.phase, instance.finish = Mock(return_value=True), Mock()
            self.assertEqual(instance.run(), 1)  # A mocked operation cannot award a result.
            labels = [call.args[0] for call in instance.phase.call_args_list]
            self.assertEqual(set(labels), q.required_phases('apple-x64', False, mode))
            self.assertEqual(labels[:2], ['native-controls', 'toolchain'])
            instance.finish.assert_called_once_with()

    def test_only_untouched_shutdown_device_may_boot_once_with_original_deadline(self):
        instance = self.fixture('cold-boot')
        instance.simulator_state = Mock(side_effect=[{'state': 'Shutdown'}, {'state': 'Booted'}])
        instance.intel_environment_observation = Mock()
        instance.intel_cold_boot()
        instance.invoke.assert_called_once_with('intel-cold-boot-readiness',
            ['/usr/bin/xcrun', 'simctl', 'bootstatus', 'owned', '-b'], 120)
        self.assertEqual([call.args for call in instance.simulator_state.call_args_list],
                         [('intel-cold-boot-initial',), ('intel-cold-boot-ready',)])
        self.assertEqual([call.args for call in instance.intel_environment_observation.call_args_list],
                         [('before',), ('after',)])
        self.assertEqual(instance.intel_environment_observation.call_args.kwargs, {'finalizer': True})
        for state in ('Booted', 'Booting', 'Creating', 'Shutting Down'):
            instance = self.fixture('cold-boot')
            instance.simulator_state = Mock(return_value={'state': state})
            instance.intel_environment_observation = Mock()
            with self.assertRaises(q.QualificationError):
                instance.intel_cold_boot()
            instance.invoke.assert_not_called()
            instance.intel_environment_observation.assert_not_called()

    def test_post_failure_diagnostics_neither_hide_boot_failure_nor_resume_products(self):
        for observation_fails in (False, True):
            instance = self.fixture('cold-boot')
            original = q.QualificationError('synthetic boot timeout', 'OWNERSHIP_UNPROVEN')
            def fail(*args):
                instance.unsafe = True
                raise original
            instance.invoke.side_effect = fail
            instance.simulator_state = Mock(return_value={'state': 'Shutdown'})
            instance.intel_environment_observation = Mock(side_effect=(
                [None, ValueError('synthetic missing snapshot')] if observation_fails else None))
            with self.assertRaises(q.QualificationError) as caught:
                instance.intel_cold_boot()
            self.assertIs(caught.exception, original)
            self.assertTrue(instance.unsafe)
            instance.simulator_state.assert_called_once_with('intel-cold-boot-initial')
            instance.intel_environment_observation.assert_called_with('after', finalizer=True)
            self.assertEqual(len(instance.result['errors']), int(observation_fails))
            operation = Mock()
            self.assertFalse(instance.phase('swift-runtime', operation))
            operation.assert_not_called()

    def test_snapshots_are_exact_owned_read_only_commands_with_no_override_for_before(self):
        instance = self.fixture('cold-boot')
        instance.output = Mock(return_value=b'synthetic')
        with patch.object(q.product_diagnostics, 'intel_environment_observation', return_value={}) as parse:
            instance.intel_environment_observation('before')
            instance.unsafe = True
            instance.intel_environment_observation('after', finalizer=True)
        expected = [(sys.executable, str(ROOT / 'scripts/rpc_intel_process_diagnostics.py'), 'snapshot'),
                    ('/usr/sbin/sysctl', '-n', 'hw.memsize', 'hw.logicalcpu'), ('/usr/bin/vm_stat',),
                    (sys.executable, '-c', q.INTEL_HOST_PROBE)]
        # Fixed read-only CPU interval is post-attempt only. It adds no boot
        # time, retries, production work, ownership exemptions or user actions.
        expected = expected + [(sys.executable, str(ROOT / 'scripts/rpc_intel_process_diagnostics.py'),
                                'cpu-interval')] + expected
        self.assertEqual(len(instance.invoke.call_args_list), len(expected))
        for i, call in enumerate(instance.invoke.call_args_list):
            self.assertEqual(tuple(call.args[1]), expected[i])
            self.assertEqual(call.args[2], 30)
            self.assertEqual(call.kwargs, {'finalizer': i >= 4})
        self.assertEqual(parse.call_count, 9)
        self.assertTrue(instance.unsafe)
        for phase, finalizer in (('before', True), ('after', False), ('unknown', True)):
            with self.assertRaises(q.QualificationError):
                instance.intel_environment_observation(phase, finalizer)

    def test_host_probe_reads_only_metadata_and_load_without_executing_or_altering_ps(self):
        output = io.StringIO()
        with patch.object(os, 'stat', return_value=SimpleNamespace(st_mode=0o104755, st_uid=0)) as metadata, \
                patch.object(os, 'getloadavg', return_value=(1.25, 2.5, 3.75)), \
                patch.object(os, 'getuid', return_value=501), patch.object(os, 'geteuid', return_value=501), \
                contextlib.redirect_stdout(output):
            exec(q.INTEL_HOST_PROBE, {})
        metadata.assert_called_once_with('/bin/ps')
        value = json.loads(output.getvalue())
        self.assertEqual(value, {'loadMilli': [1250, 2500, 3750], 'psSetuid': True, 'psSetgid': False,
                                 'psOwnedByRoot': True, 'unprivileged': True})
        parsed = q.product_diagnostics.intel_environment_observation('host', output.getvalue().encode())
        self.assertNotIn('/bin/', json.dumps(parsed))
        tree = ast.parse(q.INTEL_HOST_PROBE)
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and
                 isinstance(node.func, ast.Attribute)}
        self.assertEqual(calls, {'stat', 'getloadavg', 'getuid', 'geteuid', 'dumps'})

    def test_late_snapshot_failure_retains_earlier_observations_without_claiming_phase_success(self):
        instance = self.fixture('cold-boot')
        instance.output = Mock(return_value=b'synthetic')
        instance.invoke.side_effect = [{}, {}, q.QualificationError('synthetic unadmitted probe', 'OWNERSHIP_UNPROVEN')]
        with patch.object(q.product_diagnostics, 'intel_environment_observation', return_value={}):
            self.assertFalse(instance.phase('intel-cold-boot', lambda: instance.intel_environment_observation('before')))
        self.assertEqual(instance.result['productDiagnostics']['intelEnvironment']['before'],
                         {'nativeProcesses': {}, 'hardware': {}})
        self.assertEqual(instance.result['phases']['intel-cold-boot'],
                         {'status': 'FAIL', 'code': 'OWNERSHIP_UNPROVEN'})

    def test_failed_cold_boot_still_uses_existing_exact_device_retirement_and_failed_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.fixture('cold-boot')
            instance.private, instance.state = Path(directory), Path(directory)
            instance.context = {'source': {'commit': 'a' * 40}}
            instance.result['errors'].append({'phase': 'intel-cold-boot', 'error': 'synthetic timeout'})
            instance.unsafe, instance.kvm = True, None
            instance.runner = Mock()
            instance.runner.source_snapshot.return_value = instance.context['source']
            instance.simulator_state = Mock(side_effect=[{'state': 'Booted'}, {'state': 'Shutdown'}, None])
            instance.finish()
            self.assertEqual([call.args for call in instance.invoke.call_args_list], [
                ('owned-simulator-shutdown', ['/usr/bin/xcrun', 'simctl', 'shutdown', 'owned'], 120),
                ('owned-simulator-delete', ['/usr/bin/xcrun', 'simctl', 'delete', 'owned'], 120)])
            self.assertTrue(all(call.kwargs == {'finalizer': True} for call in instance.invoke.call_args_list))
            self.assertTrue(instance.result['simulatorRetired'])
            self.assertTrue(instance.unsafe)
            self.assertEqual(instance.result['result'], 'FAIL')

    def test_native_diagnostic_uses_real_lan_profile_but_cannot_replace_full_platform(self):
        instance = self.fixture('native')
        instance.sim_init = Path('/owned/binding.gradle')
        instance.gate = SimpleNamespace(PROFILES={'ios-lan-x64': [':p2p-transport-lan:iosX64Test']}, FLAGS=[])
        instance.retire_created_simulator = Mock()
        instance.invoke.side_effect = RuntimeError('synthetic execution failure')
        with self.assertRaises(q.QualificationError):
            instance.platform_tests(True)
        instance.invoke.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, 'synthetic execution failure'):
            instance.platform_tests(False)
        self.assertEqual(instance.invoke.call_args.args[1][0], ':p2p-transport-lan:iosX64Test')
        self.assertEqual(instance.invoke.call_args.args[2], 7200)
        self.assertEqual([call.args[0] for call in instance.retire_created_simulator.call_args_list],
                         ['platform-native-isolate', 'platform-native-retire'])

    def test_public_diagnostic_verdict_cannot_be_mislabeled_as_product_qualification(self):
        private = result()
        for mode in ('native', 'cold-boot', 'network'):
            private['intelInvestigation'] = mode
            public = q.public_summary(private)
            self.assertEqual(public['scope'], 'FEATURE_ONLY_INTEL_DIAGNOSTIC_NOT_PRODUCT_QUALIFICATION')
            self.assertEqual(public['intelInvestigation'], mode)
            self.assertEqual(public['foundationStatus'], 'NOT_READY')
            self.assertFalse(public['physicalQualification'])
            self.assertFalse(public['rpcCapacityQualification'])
        for lane, admission in (('apple-arm64', False), ('android-art', False), ('apple-x64', True)):
            with self.assertRaises(q.QualificationError):
                q.public_summary({**private, 'lane': lane, 'admissionOnly': admission})

    def test_collector_rejects_mode_mismatch_and_incomplete_full_inventory(self):
        for mismatch in (True, False):
            with tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                state = parent / 'state'
                (state / 'private').mkdir(parents=True)
                (state / 'private/result.json').touch()
                private = result()
                private.update(admissionOnly=False, intelInvestigation='native' if mismatch else None,
                               result='FAIL' if mismatch else 'PASS', errors=[], simulatorRetired=True)
                private['phases'] = {key: {'status': 'PASS'} for key in q.required_phases('apple-x64', False, 'native')}
                private['sourceAfter'] = private['source']
                runner = Mock()
                runner.absolute_path.return_value = parent
                runner.read_json.return_value = private
                runner.context_at.return_value = (state, {'source': private['source']})
                runner.source_snapshot.return_value = private['source']
                with patch.object(q, 'module', return_value=runner), \
                        patch.object(q.platform, 'system', return_value='Darwin'), \
                        patch.object(q.platform, 'machine', return_value='x86_64'), \
                        patch.dict(os.environ, {**environment(), 'RUNNER_TEMP': directory,
                                                'RPC_QUALIFICATION_PARENT': directory}):
                    with self.assertRaises(q.QualificationError):
                        q.collect('apple-x64', False)
                runner.write_new_json.assert_not_called()

    def test_workflow_diagnostic_jobs_have_distinct_artifacts_and_explicit_run_collect_modes(self):
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        line = next(line for line in source.splitlines() if line.strip().startswith('matrix:'))
        self.assertEqual(line.strip().split(' && ', 1)[0],
                         "matrix: ${{ fromJSON(contains(github.event.head_commit.message, '[rpc-intel-investigate]')")
        self.assertIn("format('-intel-{0}', matrix.investigation)", source)
        self.assertIn("RPC_INTEL_INVESTIGATION: ${{ matrix.investigation || '' }}", source)
        self.assertEqual(source.count('args+=(--intel-investigation "$RPC_INTEL_INVESTIGATION")'), 2)
        self.assertIn('cancel-in-progress: false', source)

    def test_network_diagnostic_is_explicit_and_cannot_admit_products_or_other_architectures(self):
        marker = '[rpc-intel-network-investigate]'
        q.admit_commit_marker(marker, 'apple-x64', False, 'network')
        for lane in q.HOSTS:
            for mode in (None, 'native', 'cold-boot', 'network'):
                for admission in (False, True):
                    if (lane, mode, admission) == ('apple-x64', 'network', False):
                        continue
                    with self.assertRaises(q.QualificationError):
                        q.admit_commit_marker(marker, lane, admission, mode)
        for other in (q.MARKER, q.ADMISSION_MARKER, q.INTEL_INVESTIGATION_MARKER,
                      q.INTEL_NATIVE_INVESTIGATION_MARKER, q.INTEL_MARKER, q.ARM_MARKER):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker(marker + other, 'apple-x64', False, 'network')
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        line = next(line for line in source.splitlines() if line.strip().startswith('matrix:'))
        guard, value = line.split("' || ", 3)[2].split(' && ', 1)
        self.assertEqual(guard, "contains(github.event.head_commit.message, '[rpc-intel-network-investigate]')")
        self.assertEqual(json.loads(value[1:]), {'include': [{'lane': 'apple-x64', 'os': 'macos-15-intel',
            'developer': '/Applications/Xcode_26.3.app/Contents/Developer', 'investigation': 'network'}]})

    def test_network_diagnostic_keeps_failures_attempts_both_contexts_and_retires_owned_device(self):
        instance = self.fixture('network')
        instance.retire_created_simulator = Mock()
        with tempfile.TemporaryDirectory() as directory:
            instance.state = Path(directory)
            (instance.state / 'work').mkdir()
            sdk = instance.state / 'developer/sdk'
            sdk.mkdir(parents=True)
            instance.output = Mock(side_effect=lambda p, **k: str(sdk).encode() if p['purpose'].endswith('-sdk') else b'')
            instance.invoke.side_effect = lambda purpose, *a, **k: dict(purpose=purpose,
                productExitCode=0 if purpose.endswith(('-sdk', '-compile')) else 1)
            with patch.dict(os.environ, DEVELOPER_DIR=str(sdk.parent)), \
                    patch.object(q.network_diagnostics, 'observe', return_value={'observation': {'probeExit': 1}}) as parse:
                with self.assertRaises(q.QualificationError):
                    instance.apple_network_diagnostic()
            self.assertEqual(parse.call_count, len(q.network_diagnostics.CONTEXTS) * len(q.network_diagnostics.MODES))
            self.assertEqual(set(instance.result['productDiagnostics']['appleNetwork']),
                             {c + '-' + m for c in q.network_diagnostics.CONTEXTS for m in q.network_diagnostics.MODES})
            calls = instance.invoke.call_args_list
            self.assertEqual(len(calls), len(q.network_diagnostics.CONTEXTS) * (len(q.network_diagnostics.MODES) + 3))
            for call in calls:
                label, argv, timeout = call.args
                self.assertIn(label, q.PURPOSES)
                if label.endswith('-compile'):
                    self.assertIn('-Werror', argv)
                    # Apple's DNSService* ABI is in implicit libSystem. The
                    # POSIX -ldns_sd flag fails on the required Xcode 26.3 SDK.
                    self.assertNotIn('-ldns_sd', argv)
                    self.assertEqual(argv[argv.index('-framework') + 1], 'Network')
                    self.assertIn('CoreFoundation', argv)
                    if '-declared-' in label:
                        self.assertEqual(argv[-8:], ['-Xlinker', '-sectcreate', '-Xlinker', '__TEXT',
                            '-Xlinker', '__info_plist', '-Xlinker',
                            str(ROOT / 'scripts/diagnostics/apple-bonjour-probe-info.plist')])
                    else:
                        self.assertNotIn('-sectcreate', argv)
                    self.assertIn('x86_64-apple-macos15.0' if '-host-' in label else 'x86_64-apple-ios15.0-simulator', argv)
                    self.assertEqual(timeout, 120)
                elif not label.endswith('-sdk'):
                    self.assertTrue(call.kwargs['allow_failure'])
                    self.assertEqual(timeout, 45)
                    if '-simulator-' in label:
                        self.assertEqual(argv[:5], ['/usr/bin/xcrun', 'simctl', 'spawn', '--standalone', 'owned'])
                    else:
                        self.assertEqual(len(argv), 2)
                    self.assertEqual('-declared' in argv[-2], argv[-1] == 'network-declared')
        self.assertEqual([call.args for call in instance.retire_created_simulator.call_args_list],
                         [('network-probe-isolate',), ('network-probe-retire',)])
        self.assertEqual(instance.result['counts'], {})

    def test_network_diagnostic_compile_exception_still_retires_and_never_continues_unowned(self):
        instance = self.fixture('network')
        instance.retire_created_simulator = Mock()
        with tempfile.TemporaryDirectory() as directory:
            instance.state = Path(directory)
            (instance.state / 'work').mkdir()
            instance.invoke.side_effect = q.QualificationError('synthetic ownership failure')
            with self.assertRaises(q.QualificationError):
                instance.apple_network_diagnostic()
        self.assertEqual(instance.invoke.call_count, 1)
        self.assertEqual([call.args for call in instance.retire_created_simulator.call_args_list],
                         [('network-probe-isolate',), ('network-probe-retire',)])

    def test_advertising_ab_runs_baseline_before_change_and_always_restores_after_original_probes(self):
        for failure in (None, 'apply', 'probe', 'retire'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                instance = self.fixture('network')
                instance.state = instance.parent = Path(directory)
                instance.context = {'source': result()['source']}
                (instance.state / 'work').mkdir()
                sdk = instance.state / 'developer/sdk'
                sdk.mkdir(parents=True)
                events = []

                def invoke(purpose, *args, **kwargs):
                    events.append(purpose)
                    if failure == 'probe' and purpose == 'network-probe-host-bsd':
                        raise q.QualificationError('synthetic ownership failure')
                    return dict(purpose=purpose, productExitCode=0)

                def output(proof, **kwargs):
                    return str(sdk).encode() if proof['purpose'].endswith('-sdk') else b'' if proof['purpose'].endswith('-compile') else proof['purpose'].encode()

                def parse(raw, context, mode, code):
                    before = b'baseline' in raw
                    return {'observation': {'probeExit': int(before and mode != 'mdns-policy'),
                                            'preferenceKind': 'TRUE' if before else 'FALSE'}}

                def apply():
                    events.append('apply')
                    if failure == 'apply':
                        raise q.QualificationError('synthetic setup refusal')

                def retire(label):
                    events.append(label)
                    if failure == 'retire' and label.endswith('retire'):
                        raise q.QualificationError('synthetic retirement refusal')

                preparation = Mock()
                preparation.apply.side_effect = apply
                preparation.finish.side_effect = lambda: events.append('restore')
                instance.invoke.side_effect, instance.output = invoke, Mock(side_effect=output)
                instance.retire_created_simulator = Mock(side_effect=retire)
                with patch.dict(os.environ, DEVELOPER_DIR=str(sdk.parent), RPC_APPLE_BONJOUR_ADVERTISING='true'), \
                        patch.object(q.network_diagnostics, 'observe', side_effect=parse), \
                        patch.object(q.bonjour_environment, 'AdvertisingPreparation', return_value=preparation):
                    if failure:
                        with self.assertRaises(q.QualificationError):
                            instance.apple_network_diagnostic()
                    else:
                        instance.apple_network_diagnostic()
                baseline = instance.result['productDiagnostics']['appleNetworkBaseline']
                self.assertEqual(set(baseline), {c + '-' + m for c in q.network_diagnostics.CONTEXTS
                                               for m in q.network_diagnostics.BASELINE_MODES})
                self.assertEqual(baseline['host-dns-selected']['observation']['probeExit'], 1)
                self.assertGreater(events.index('apply'), events.index('network-probe-baseline-simulator-network-production-shape'))
                self.assertEqual(events[-2:], ['network-probe-retire', 'restore'])
                preparation.finish.assert_called_once_with()
                after = instance.result['productDiagnostics']['appleNetwork']
                if failure in (None, 'retire'):
                    self.assertEqual(len(after), 2 * len(q.network_diagnostics.MODES))
                else:
                    self.assertEqual(after, {})
                self.assertEqual(instance.result['counts'], {})  # Mocks cannot supply admitted native/product counts.

    def test_advertising_integration_uses_actual_source_schema_and_real_preparation_admission(self):
        # Exercise the actual constructor/admit/apply/finally/finish boundary.
        # Only OS observations/commands are fixtures; no sudo/native work runs.
        b = q.bonjour_environment
        source = result()['source']
        with tempfile.TemporaryDirectory() as directory:
            instance = self.fixture('network')
            instance.state = instance.parent = parent = Path(directory).resolve(strict=True)
            instance.context = {'source': {**source, 'status': '', 'diffSha256': b.digest(b'')}}
            (parent / 'work').mkdir()
            sdk = parent / 'developer/sdk'
            sdk.mkdir(parents=True)
            instance.retire_created_simulator = Mock()
            instance.invoke.side_effect = lambda purpose, *a, **kw: dict(purpose=purpose, productExitCode=0)
            instance.output = lambda proof, **kw: (str(sdk).encode() if proof['purpose'].endswith('-sdk') else
                                                    b'' if proof['purpose'].endswith('-compile') else proof['purpose'].encode())
            env = {**environment(), 'GITHUB_WORKSPACE': str(ROOT), 'RUNNER_TEMP': str(parent.parent),
                   'RPC_QUALIFICATION_PARENT': str(parent), 'RPC_APPLE_BONJOUR_ADVERTISING': 'true',
                   'RPC_APPLE_TERMINAL_CONTEXT': 'true', 'DEVELOPER_DIR': str(sdk.parent)}
            snapshots = [({b.KEY: flag}, (0, 0, 0o644), b'fixture preference') for flag in (True, False, False, True)]

            def command(preparation, label):
                preparation.proof['commands'][label] = dict(exitCode=0, timedOut=False, failure='NONE',
                                                            bytes=0, sha256=b.digest(b''))

            def observe(raw, context, mode, code):
                return {'observation': {'probeExit': 0, 'preferenceKind': 'TRUE' if b'baseline' in raw else 'FALSE'}}

            with patch.dict(os.environ, env), patch.object(b.platform, 'system', return_value='Darwin'), \
                    patch.object(b.platform, 'machine', return_value='x86_64'), \
                    patch.object(b.apple_context, 'host_role', return_value='macos-x64'), \
                    patch.object(b.os, 'getuid', return_value=501), patch.object(b.os, 'geteuid', return_value=501), \
                    patch.object(b.os, 'getgid', return_value=20), patch.object(b.os, 'getegid', return_value=20), \
                    patch.object(b.private, 'private_parent'), patch.object(b.private, 'source_snapshot', return_value=source), \
                    patch.object(b, 'read_service_configuration', return_value='d' * 64), \
                    patch.object(b, 'read_preference', side_effect=snapshots), \
                    patch.object(b.AdvertisingPreparation, 'command', command), \
                    patch.object(q.network_diagnostics, 'observe', side_effect=observe):
                instance.apple_network_diagnostic()
            proof = b.validate(json.loads((parent / 'bonjour-advertising/result.json').read_text()), source)
            self.assertEqual(proof['source'], source)
            self.assertEqual(set(proof['commands']), b.REPAIR_COMMANDS)
            self.assertTrue(proof['restored'])
            self.assertEqual(len(instance.result['productDiagnostics']['appleNetworkBaseline']), 12)
            self.assertEqual(len(instance.result['productDiagnostics']['appleNetwork']), 38)
            self.assertEqual(instance.result['counts'], {})  # A fixture is never native/product evidence.

    def test_advertising_proof_and_baseline_cannot_be_omitted_or_claimed_in_another_scope(self):
        private = {**result(), 'intelInvestigation': 'network', 'bonjourAdvertisingRequired': True,
                   'terminalContextRequired': True}
        self.assertIsNone(q.public_summary(private)['appleBonjourAdvertising'])
        for change in (dict(result='PASS'), dict(intelInvestigation='cold-boot'), dict(lane='apple-arm64'),
                       dict(terminalContextRequired=False), dict(bonjourAdvertisingRequired=1)):
            with self.subTest(change=change), self.assertRaises(Exception):
                q.public_summary({**private, **change})
        for change in (dict(appleBonjourAdvertising={}), dict(productDiagnostics={'appleNetworkBaseline': {'host-bsd': {}}})):
            with self.assertRaises(Exception):
                q.public_summary({**result(), 'intelInvestigation': 'network', **change})
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn("RPC_APPLE_BONJOUR_ADVERTISING: ${{ (matrix.lane == 'apple-x64' || matrix.lane == 'apple-arm64') && matrix.investigation != 'cold-boot'", workflow)
        self.assertIn('python3 scripts/tests/rpc-apple-bonjour-environment-test.py', workflow)

    def test_original_product_inventories_add_preparation_without_removing_any_gate(self):
        for mode in (None, 'native'):
            self.assertEqual(q.required_phases('apple-x64', False, mode, True),
                             q.required_phases('apple-x64', False, mode) | {'bonjour-advertising'})
            instance = self.fixture(mode)
            instance.phase, instance.finish = Mock(return_value=True), Mock()
            with patch.dict(os.environ, RPC_APPLE_BONJOUR_ADVERTISING='true'):
                self.assertEqual(instance.run(), 1)  # No native pass from mocked phases.
            labels = [call.args[0] for call in instance.phase.call_args_list]
            self.assertEqual(set(labels), q.required_phases('apple-x64', False, mode, True))
            self.assertLess(labels.index('toolchain'), labels.index('bonjour-advertising'))
            self.assertLess(labels.index('bonjour-advertising'), labels.index('multicast-admission'))
            instance.finish.assert_called_once_with()
        self.assertEqual(q.required_phases('apple-x64', False, 'network', True),
                         q.required_phases('apple-x64', False, 'network'))
        self.assertEqual(q.required_phases('apple-arm64', False, advertising=True),
                         q.required_phases('apple-arm64', False) | {'bonjour-advertising'})
        self.assertTrue(q.ARM_PHASES <= q.required_phases('apple-arm64', False, advertising=True))
        for lane, admission, mode in (('apple-arm64', False, 'native'), ('android-art', False, None),
                                     ('apple-x64', True, None), ('apple-x64', False, 'cold-boot')):
            with self.assertRaises(q.QualificationError):
                q.required_phases(lane, admission, mode, True)

    def test_failed_preparation_blocks_product_start_but_not_finalization(self):
        for lane, mode in (('apple-x64', None), ('apple-x64', 'native'), ('apple-arm64', None)):
            instance = self.fixture(mode)
            instance.lane = lane
            instance.native_controls, instance.toolchain, instance.finish = Mock(), Mock(), Mock()
            instance.prepare_bonjour_advertising = Mock(side_effect=RuntimeError('synthetic prerequisite'))
            instance.install_apple_tools = Mock()
            with patch.dict(os.environ, RPC_APPLE_BONJOUR_ADVERTISING='true'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(instance.run(), 1)
            self.assertEqual(instance.result['phases']['bonjour-advertising']['status'], 'FAIL')
            self.assertTrue(all(row['status'] == 'BLOCKED_PREREQUISITE' for key, row in instance.result['phases'].items()
                                if key not in ('native-controls', 'toolchain', 'bonjour-advertising')))
            instance.install_apple_tools.assert_not_called()
            instance.invoke.assert_not_called()
            instance.finish.assert_called_once_with()

    def test_full_arm_execution_preserves_every_original_phase_and_cleanup_after_preparation(self):
        instance = self.fixture(None)
        instance.lane = 'apple-arm64'
        instance.phase, instance.finish = Mock(return_value=True), Mock()
        with patch.dict(os.environ, RPC_APPLE_BONJOUR_ADVERTISING='true'):
            self.assertEqual(instance.run(), 1)  # This fixture supplies no native success.
        labels = [call.args[0] for call in instance.phase.call_args_list]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual(set(labels), q.required_phases('apple-arm64', False, advertising=True))
        self.assertTrue(q.ARM_PHASES <= set(labels))
        self.assertNotIn('scoped-native', labels)  # Never substitute a subset for full-platform.
        self.assertLess(labels.index('toolchain'), labels.index('bonjour-advertising'))
        self.assertLess(labels.index('bonjour-advertising'), labels.index('tool-installation'))
        self.assertLess(labels.index('multicast-admission'), labels.index('full-platform'))
        instance.finish.assert_called_once_with()

    def test_product_preparation_uses_real_source_schema_and_restores_after_all_failure_paths(self):
        b = q.bonjour_environment
        source = result()['source']
        for failure in ('product', 'ownership', 'simulator', 'apply', 'restore'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                instance = self.fixture('native')
                instance.parent = instance.state = instance.private = parent = Path(directory).resolve(strict=True)
                instance.context = {'source': {**source, 'status': '', 'diffSha256': b.digest(b'')}}
                instance.simulator, instance.kvm = None, None
                instance.runner = Mock()
                instance.runner.source_snapshot.return_value = instance.context['source']
                if failure == 'simulator':
                    instance.simulator = 'exact-owned'
                    instance.simulator_state = Mock(side_effect=RuntimeError('synthetic retirement'))
                env = {**environment(), 'GITHUB_WORKSPACE': str(ROOT), 'RUNNER_TEMP': str(parent.parent),
                       'RPC_QUALIFICATION_PARENT': str(parent), 'RPC_APPLE_BONJOUR_ADVERTISING': 'true',
                       'RPC_APPLE_TERMINAL_CONTEXT': 'true'}
                snapshots = [({b.KEY: flag}, (0, 0, 0o644), b'fixture preference')
                             for flag in ((True, False, True) if failure == 'apply' else (True, False, False, True))]
                commands = []
                def command(preparation, label):
                    commands.append(label)
                    denied = label == failure
                    preparation.proof['commands'][label] = dict(exitCode=1 if denied else 0, timedOut=False,
                        failure='COMMAND_FAILED' if denied else 'NONE', bytes=0, sha256=b.digest(b''))
                    if denied:
                        raise b.PreparationFailure('COMMAND_FAILED')
                with patch.dict(os.environ, env), patch.object(b.platform, 'system', return_value='Darwin'), \
                        patch.object(b.platform, 'machine', return_value='x86_64'), \
                        patch.object(b.apple_context, 'host_role', return_value='macos-x64'), \
                        patch.object(b.os, 'getuid', return_value=501), patch.object(b.os, 'geteuid', return_value=501), \
                        patch.object(b.os, 'getgid', return_value=20), patch.object(b.os, 'getegid', return_value=20), \
                        patch.object(b.private, 'private_parent'), patch.object(b.private, 'source_snapshot', return_value=source), \
                        patch.object(b, 'read_service_configuration', return_value='d' * 64), \
                        patch.object(b, 'read_preference', side_effect=snapshots), \
                        patch.object(b.AdvertisingPreparation, 'command', command):
                    if failure == 'apply':
                        with self.assertRaises(b.PreparationFailure):
                            instance.prepare_bonjour_advertising()
                    else:
                        instance.prepare_bonjour_advertising()
                    self.assertEqual(instance.advertising_preparation.source, source)
                    instance.result['errors'].append({'phase': 'scoped-native', 'error': 'retained synthetic failure'})
                    instance.unsafe = failure == 'ownership'
                    instance.finish()
                retained = b.validate(json.loads((parent / 'bonjour-advertising/result.json').read_text()), source, complete=False)
                self.assertEqual(commands[:2], ['inspect', 'apply'])
                self.assertIn('restore', commands)
                if failure not in ('apply', 'restore'):
                    b.validate(retained, source)
                    self.assertTrue(retained['restored'])
                    self.assertEqual(commands[-2:], ['restore', 'restore-reload'])
                else:
                    self.assertTrue(any(row.get('finalizer') == 'bonjour-advertising' for row in instance.result['errors']))
                if failure == 'simulator':
                    self.assertTrue(any(row.get('finalizer') == 'simulator' for row in instance.result['errors']))
                self.assertEqual(instance.result['result'], 'FAIL')
                self.assertEqual(instance.result['counts'], {})
                self.assertEqual(instance.unsafe, failure == 'ownership')

    def test_network_primitive_result_cannot_be_exported_as_full_qualification(self):
        for mode in (None, 'native', 'cold-boot'):
            private = {**result(), 'intelInvestigation': mode, 'productDiagnostics': {'appleNetwork': {'host-bsd': {}}}}
            with self.assertRaises(q.QualificationError):
                q.public_summary(private)

    def test_network_scope_does_not_boot_or_start_gradle_or_weaken_retirement(self):
        instance = self.fixture('network')
        instance.phase = Mock(return_value=True)
        instance.investigate_intel(True)
        self.assertEqual([call.args[0] for call in instance.phase.call_args_list],
                         ['simulator-admission', 'apple-network-diagnostic'])
        for mode in ('native', 'cold-boot', None):
            instance.intel_investigation = mode
            with self.assertRaises(q.QualificationError):
                instance.retire_created_simulator('network-probe-retire')
        instance.intel_investigation = 'network'
        instance.simulator_state = Mock(return_value={'state': 'Shutdown'})
        instance.retire_created_simulator('network-probe-retire')
        self.assertEqual([call.args[0] for call in instance.simulator_state.call_args_list],
                         ['network-probe-retire-before', 'network-probe-retire-after'])
        instance.lane = 'apple-arm64'
        with self.assertRaises(q.QualificationError):
            instance.retire_created_simulator('network-probe-retire')


class IntelRuntimeControls(unittest.TestCase):
    def report(self):
        policy = json.loads((ROOT / 'gradle/platform-test-policy.json').read_text())
        tasks = {t for model in policy['model'].values() for t in model['tests']}
        records = {t: dict(enabled=True, inGraph=False, outcome='NOT_REQUESTED', passed=0, failed=0, skipped=0)
                   for t in tasks}
        for task in q.INTEL_HOST_TASKS:
            records[task].update(inGraph=True, outcome='EXECUTED', passed=1)
        return policy, dict(schema=1, model=policy['model'], token='a' * 32, dryRun=False, buildFailed=False,
                            host={'os': 'Mac OS X', 'arch': 'x86_64'}, tests=records)

    def test_host_model_requires_exact_requested_runtime_execution_not_a_dry_run_or_native_substitute(self):
        policy, report = self.report()
        self.assertEqual(q.intel_host_execution(report, policy, 'a' * 32), q.INTEL_HOST_TASKS)
        for key, value in (('schema', True), ('token', 'b' * 32), ('dryRun', True), ('buildFailed', True),
                           ('model', {}), ('host', {'os': 'Mac OS X', 'arch': 'arm64'}),
                           ('host', {'os': 'Linux', 'arch': 'x86_64'}), ('tests', {})):
            with self.subTest(key=key), self.assertRaises(q.QualificationError):
                q.intel_host_execution({**report, key: value}, policy, 'a' * 32)
        for task in q.INTEL_HOST_TASKS:
            for key, value in (('passed', 0), ('passed', True), ('failed', 1), ('skipped', 1), ('enabled', False),
                               ('inGraph', False), ('outcome', 'UP-TO-DATE'), ('outcome', 'FROM-CACHE'),
                               ('outcome', 'NOT_COMPLETED')):
                changed = copy.deepcopy(report)
                changed['tests'][task][key] = value
                with self.subTest(task=task, key=key), self.assertRaises(q.QualificationError):
                    q.intel_host_execution(changed, policy, 'a' * 32)
        changed = copy.deepcopy(report)
        changed['tests'][':p2p-core:iosX64Test']['inGraph'] = True
        with self.assertRaises(q.QualificationError):
            q.intel_host_execution(changed, policy, 'a' * 32)

    def test_runtime_diagnostic_requires_its_exact_marker_native_host_and_separate_inventory(self):
        marker = '[rpc-intel-runtime-investigate]'
        q.admit_commit_marker(marker, 'apple-x64', False, 'runtime')
        for lane in q.HOSTS:
            for mode in (None, 'native', 'cold-boot', 'network', 'runtime'):
                for admission in (False, True):
                    if (lane, mode, admission) == ('apple-x64', 'runtime', False):
                        continue
                    with self.subTest(lane=lane, mode=mode, admission=admission), self.assertRaises(q.QualificationError):
                        q.admit_commit_marker(marker, lane, admission, mode)
        for other in ('[rpc-intel-investigate]', '[rpc-intel-native-investigate]', '[rpc-intel-network-investigate]',
                      '[rpc-qualify]', '[rpc-admit]', '[rpc-intel-qualify]', '[rpc-arm-qualify]', '[rpc-art]'):
            with self.assertRaises(q.QualificationError):
                q.admit_commit_marker(marker + ' ' + other, 'apple-x64', False, 'runtime')
        phases = q.required_phases('apple-x64', False, 'runtime', advertising=True)
        self.assertEqual(phases, {'native-controls', 'toolchain', 'bonjour-advertising', 'tool-installation',
                                 'multicast-admission', 'intel-host-tests', 'simulator-admission', 'intel-cold-boot'})
        self.assertNotIn('full-platform', phases)
        self.assertNotIn('owned-swift-cancellation', phases)
        self.assertEqual(q.BOUNDS['swift-readiness'], 120)
        self.assertEqual(q.BOUNDS['platform'], 7200)

    def test_runtime_is_independent_of_failed_host_assertions_but_not_unverified_ownership(self):
        instance = q.Qualification.__new__(q.Qualification)
        instance.lane, instance.intel_investigation = 'apple-x64', 'runtime'
        instance.phase = Mock(return_value=True)
        instance.investigate_intel(True)
        self.assertEqual([row.args[0] for row in instance.phase.call_args_list],
                         ['tool-installation', 'multicast-admission', 'intel-host-tests', 'simulator-admission', 'intel-cold-boot'])
        # Real phase() preserves the existing unsafe prerequisite even in this scope.
        instance.unsafe = True
        instance.result = {'phases': {}, 'errors': []}
        operation = Mock()
        self.assertFalse(q.Qualification.phase(instance, 'intel-cold-boot', operation, True))
        operation.assert_not_called()
        self.assertEqual(instance.result['phases']['intel-cold-boot']['status'], 'BLOCKED_PREREQUISITE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
