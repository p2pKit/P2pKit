#!/usr/bin/env python3
"""Offline read-only diagnostic controls; no actual system preference/service operations."""
import copy
from contextlib import ExitStack
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('intel_bonjour_diagnostic', ROOT / 'scripts/diagnose-intel-bonjour-environment.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
SOURCE = {'commit': 'a' * 40, 'tree': 'b' * 40}
ENV = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', GITHUB_REPOSITORY='p2pKit/P2pKit',
           GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_WORKFLOW='Intel iOS simulator tests',
           GITHUB_JOB='intel-environment-diagnostics', RUNNER_OS='macOS', RUNNER_ARCH='X64',
           GITHUB_REF='refs/heads/work/rpc-intel-readonly-20261015', GITHUB_SHA=SOURCE['commit'],
           GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_WORKSPACE=str(ROOT))


class IntelReadOnlyControls(unittest.TestCase):
    def environment(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for owner, name, value in ((d.platform, 'system', 'Darwin'), (d.platform, 'machine', 'x86_64'),
                                   (d, 'host_role', 'macos-x64'), (d.os, 'getuid', 501), (d.os, 'geteuid', 501),
                                   (d.os, 'getgid', 20), (d.os, 'getegid', 20)):
            stack.enter_context(patch.object(owner, name, return_value=value))
        return stack

    def collect(self, preference=True, service_code=0, console_uid=501):
        with patch.object(d, 'admit', return_value={'id': 123, 'attempt': 1}), \
                patch.object(d, 'source_snapshot', return_value=SOURCE), \
                patch.object(d.Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFCHR, st_uid=console_uid)), \
                patch.object(d.os, 'getuid', return_value=501), \
                patch.object(d.bonjour, 'read_service_configuration', return_value='c' * 64), \
                patch.object(d.bonjour, 'read_preference', return_value=(
                    {d.bonjour.KEY: preference, 'private-unrelated-key': b'secret'}, (0, 0, 0o644), b'private bytes')), \
                patch.object(d, 'capture', return_value=(service_code, b'private process identities')) as capture, \
                patch.object(d.bonjour, 'AdvertisingPreparation', side_effect=AssertionError('NO MUTATION')):
            result = d.collect(ENV)
        self.assertEqual(capture.call_args.args[0], 'service')
        return result

    def test_exact_native_manual_diagnostic_context_admitted(self):
        self.environment()
        self.assertEqual(d.admit(ENV), {'id': 123, 'attempt': 1})

    def test_wrong_event_source_job_arch_or_repository_refused(self):
        self.environment()
        changes = [('GITHUB_EVENT_NAME', 'push'), ('GITHUB_JOB', 'ios-x64'), ('GITHUB_SHA', '0' * 40),
                   ('GITHUB_REF', 'refs/heads/main'), ('RUNNER_ARCH', 'ARM64'), ('GITHUB_RUN_ATTEMPT', '0'),
                   ('GITHUB_RUN_ID', '-1'), ('GITHUB_REPOSITORY', 'other/repository'),
                   ('RUNNER_ENVIRONMENT', 'self-hosted'), ('GITHUB_WORKSPACE', '/'),
                   ('GITHUB_REF', 'refs/heads/work/rpc-a/../main')]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(d.Refusal):
                d.admit({**ENV, key: value})

    def test_root_foreign_os_and_translated_contexts_refused(self):
        self.environment()
        for owner, key, value in ((d.os, 'geteuid', 0), (d.platform, 'system', 'Linux'),
                                  (d.platform, 'machine', 'arm64'), (d, 'host_role', 'macos-arm64')):
            with self.subTest(key=key), patch.object(owner, key, return_value=value), self.assertRaises(d.Refusal):
                d.admit(ENV)

    def test_true_false_are_observations_not_mutation_or_qualification(self):
        for enabled in (True, False):
            result = self.collect(enabled)
            self.assertEqual(result['status'], 'OBSERVED')
            self.assertEqual(result['bonjour']['preference'], 'TRUE' if enabled else 'FALSE')
            self.assertEqual(result['qualification'], 'NOT_PERFORMED')
            self.assertFalse(result['configurationChanged'])
            self.assertFalse(result['privilegesChanged'])
            self.assertFalse(result['productExecuted'])
            self.assertEqual(result['testsExecuted'], 0)
            for forbidden in ('secret', 'private-unrelated-key', 'private bytes', 'process identities'):
                self.assertNotIn(forbidden, json.dumps(result))

    def test_nonconsole_user_and_service_read_refusal_remain_explicit(self):
        result = self.collect(service_code=113, console_uid=0)
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertFalse(result['context']['consoleUserMatches'])
        self.assertEqual(result['bonjour']['registration'], 'READ_UNAVAILABLE')

    def observation_patches(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for owner, name, value in ((d, 'admit', {'id': 123, 'attempt': 1}), (d, 'source_snapshot', SOURCE),
                                  (d.Path, 'stat', SimpleNamespace(st_mode=stat.S_IFCHR, st_uid=501)),
                                  (d.os, 'getuid', 501), (d.bonjour, 'read_service_configuration', 'c' * 64),
                                  (d, 'capture', (0, b''))):
            stack.enter_context(patch.object(owner, name, return_value=value))
        return stack

    def test_missing_domain_requires_repeated_protected_absence(self):
        self.observation_patches()
        with patch.object(d.bonjour, 'read_preference', side_effect=d.bonjour.PreparationFailure('PREFERENCE_MISSING')), \
                patch.object(d.bonjour, 'absent_domain_observation', return_value='d' * 64) as absent:
            result = d.collect(ENV)
            self.assertEqual(result['bonjour']['preference'], 'DOMAIN_ABSENT')
            self.assertEqual(absent.call_count, 2)

    def test_missing_key_type_or_unreadable_domain_is_not_absence(self):
        self.observation_patches()
        for category in ('PREFERENCE_KEY_TYPE', 'PREFERENCE_UNREADABLE', 'PREFERENCE_KEY_MISSING'):
            with self.subTest(category=category), \
                    patch.object(d.bonjour, 'read_preference', side_effect=d.bonjour.PreparationFailure(category)), \
                    patch.object(d.bonjour, 'absent_domain_observation') as absent:
                result = d.collect(ENV)
                self.assertEqual(result['status'], 'REFUSED')
                self.assertEqual(result['error'], 'SYSTEM_OBSERVATION')
                absent.assert_not_called()

    def test_disappearing_or_changing_preference_is_refused_not_absent(self):
        self.observation_patches()
        before = ({d.bonjour.KEY: True}, (0, 0, 0o644), b'original')
        after = ({d.bonjour.KEY: False}, (0, 0, 0o644), b'changed')
        for changed in (after, d.bonjour.PreparationFailure('PREFERENCE_MISSING')):
            with patch.object(d.bonjour, 'read_preference', side_effect=[before, changed]), \
                    patch.object(d.bonjour, 'absent_domain_observation') as absent:
                self.assertEqual(d.collect(ENV)['status'], 'REFUSED')
                absent.assert_not_called()

    def test_unexpected_exception_exports_only_closed_failure_label(self):
        with patch.object(d, 'admit', side_effect=RuntimeError('sensitive-token-and-process-id')):
            result = d.collect(ENV)
        self.assertEqual(result['error'], 'SYSTEM_OBSERVATION')
        self.assertNotIn('sensitive', json.dumps(result))

    def test_changed_source_never_reports_observed_success(self):
        self.observation_patches()
        with patch.object(d.bonjour, 'read_preference', return_value=({d.bonjour.KEY: True}, (), b'a')), \
                patch.object(d, 'source_snapshot', side_effect=[SOURCE, {**SOURCE, 'tree': 'd' * 40}]):
            self.assertEqual(d.collect(ENV)['error'], 'SOURCE_CHANGED')

    def test_source_requires_clean_exact_oids(self):
        for replies, reason in (([(0, b' M tracked'), (0, b'a' * 40), (0, b'b' * 40)], 'SOURCE_DIRTY'),
                                ([(1, b'')], 'SOURCE_QUERY'),
                                ([(0, b''), (0, b'0' * 40), (0, b'b' * 40)], 'SOURCE_QUERY')):
            with patch.object(d, 'capture', side_effect=replies), self.assertRaisesRegex(d.Refusal, reason):
                d.source_snapshot(time.monotonic() + 1)

    def test_schema_refuses_extra_identifiers_or_test_success_claims(self):
        baseline = self.collect()
        for key, value in (('pid', 123), ('testsExecuted', 1), ('qualification', 'PASS'),
                           ('configurationChanged', True), ('productExecuted', True), ('schema', True)):
            with self.subTest(key=key), self.assertRaises(d.Refusal):
                d.validate_report({**baseline, key: value})
        copied = copy.deepcopy(baseline)
        copied['context']['uid'] = 501
        with self.assertRaises(d.Refusal):
            d.validate_report(copied)

    def test_capture_rejects_unknown_or_expired_commands_before_spawn(self):
        with patch.object(d.subprocess, 'Popen') as launch:
            for name, cutoff in (('reload', time.monotonic() + 1), ('service', 0)):
                with self.assertRaises(d.Refusal):
                    d.capture(name, cutoff)
            launch.assert_not_called()

    def test_actual_capture_bounds_output_and_direct_child_lifetime(self):
        with patch.dict(d.COMMANDS, {'control': [sys.executable, '-I', '-S', '-c', "print('bounded')"]}):
            self.assertEqual(d.capture('control', time.monotonic() + 5), (0, b'bounded\n'))
        for program, duration in (("import sys;sys.stdout.write('x'*200000)", 5),
                                   ('import time;time.sleep(30)', 0.1)):
            with patch.dict(d.COMMANDS, {'control': [sys.executable, '-I', '-S', '-c', program]}), \
                    self.assertRaises(d.Refusal):
                d.capture('control', time.monotonic() + duration)

    def test_only_read_only_fixed_commands_exist(self):
        self.assertEqual(set(d.COMMANDS), {'status', 'commit', 'tree', 'service'})
        self.assertEqual(d.COMMANDS['service'], ['/bin/launchctl', 'print', d.bonjour.SERVICE])
        self.assertTrue(all(argv[:2] == ['/usr/bin/git', '--no-optional-locks']
                            for name, argv in d.COMMANDS.items() if name != 'service'))

    def test_output_is_exclusive_private_and_never_overwrites_a_symlink(self):
        report = self.collect()
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            env = {'RUNNER_TEMP': str(parent)}
            d.write_report(report, env)
            path = parent / d.OUTPUT
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                d.write_report(report, env)
            path.unlink()
            target = parent / 'unchanged'
            target.write_text('retained')
            path.symlink_to(target)
            with self.assertRaises(OSError):
                d.write_report(report, env)
            self.assertEqual(target.read_text(), 'retained')

    def test_output_failure_prints_no_raw_exception_or_identifier(self):
        report = self.collect()
        with patch.object(d, 'collect', return_value=report), \
                patch.object(d, 'write_report', side_effect=OSError('private-path-and-identity')), \
                patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
            self.assertEqual(d.main(), 1)
        self.assertNotIn('private-path', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error'], 'OUTPUT_POLICY')

    def test_workflow_default_and_normal_gate_stay_unchanged(self):
        text = (ROOT / '.github/workflows/ios-x64-tests.yml').read_text()
        self.assertIn('default: false', text)
        normal, diagnostic = text.split('  intel-environment-diagnostics:\n')
        self.assertIn("github.event_name != 'workflow_dispatch' || inputs.diagnostics-only != true", normal)
        self.assertIn('timeout-minutes: 40', normal)
        self.assertIn('run: python3 scripts/run-platform-tests.py ios-x64', normal)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.diagnostics-only == true", diagnostic)
        for forbidden in ('setup-java', 'setup-gradle', 'sdkmanager', 'sudo', 'run-platform-tests.py'):
            self.assertNotIn(forbidden, diagnostic)


if __name__ == '__main__':
    unittest.main()
