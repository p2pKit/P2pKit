#!/usr/bin/env python3
"""Offline actual-caller controls plus a real bounded local child (no multicast/JDK/download)."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('jmdns_diagnostic', ROOT / 'scripts/run-jmdns-interpreter-diagnostic.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
PIN = '5d6298b93a1905c32cda6478808ac14c2d4a47e91535e53c41f7feeb85d946f4'


def outcome(exit_code=0, **changes):
    return dict({'exitCode': exit_code, 'code': 'PASS' if exit_code == 0 else 'COMMAND_FAILED',
                 'timedOut': False, 'cleanupKnown': True, 'capturesClosed': True}, **changes)


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'jdk'
        (self.home / 'bin').mkdir(parents=True)
        (self.home / 'release').write_text('JAVA_VERSION="17.0.20.1"\n')
        for name in ('java', 'javac'):
            (self.home / 'bin' / name).write_text('test-only')
            (self.home / 'bin' / name).chmod(0o700)
        self.env = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                    'JAVA_HOME': str(self.home), 'PATH': os.environ.get('PATH', '')}
        self.count = 0

    def diagnostic(self, end=None, cancelled=None):
        self.count += 1
        state = self.root / ('state-' + str(self.count))
        state.mkdir()
        return d.Diagnostic(state, end or time.monotonic() + 420, cancelled or threading.Event())

    @contextlib.contextmanager
    def controller(self, *, fail_at=None, failure=None, raw='PASS mode=control\n'):
        calls = []
        original_sha256 = hashlib.sha256

        def fake_sha256(data=b''):
            return Mock(hexdigest=lambda: PIN) if data == b'modeled-reviewed-jar' else original_sha256(data)

        def command(argv, **kwargs):
            calls.append((argv, kwargs))
            private = kwargs['private']
            private.mkdir(mode=0o700)
            (private / 'stdout.log').write_text(raw if len(calls) == 4 else '')
            (private / 'stderr.log').write_text('')
            if len(calls) == 1:
                Path(argv[argv.index('--output') + 1]).write_bytes(b'modeled-reviewed-jar')
            return failure if len(calls) == fail_at else outcome()

        with patch.dict(os.environ, self.env, clear=True), \
                patch.object(d.evidence, 'run_command', side_effect=command), \
                patch.object(d.rpc.hashlib, 'sha256', side_effect=fake_sha256):
            diagnostic = self.diagnostic()
            yield diagnostic, calls

    def test_actual_controller_uses_canonical_launcher_and_unchanged_bounds_pins(self):
        launcher = self.root / 'python launcher'
        launcher.symlink_to(Path(sys.executable).resolve())
        with self.controller() as (diagnostic, calls), patch.object(d.rpc.sys, 'executable', str(launcher)):
            diagnostic.run()
        self.assertEqual(diagnostic.result['status'], 'PASS')
        self.assertEqual([row['purpose'] for row in diagnostic.result['commands']], list(d.COMMANDS))
        self.assertEqual([kwargs['timeout'] for _, kwargs in calls], [90, 90, 90, 45])
        curl, java = calls[0][0], calls[-1][0]
        self.assertEqual(curl[0], '/usr/bin/curl')
        self.assertIn('--disable', curl)
        self.assertEqual(curl[-1], 'https://repo.maven.apache.org/maven2/org/slf4j/slf4j-api/2.0.7/slf4j-api-2.0.7.jar')
        self.assertEqual(java[-1], 'control')
        self.assertEqual([arg for arg in java if arg.startswith('-Dp2pkit.audit.pythonExecutable=')],
                         ['-Dp2pkit.audit.pythonExecutable=' + str(Path(sys.executable).resolve())])
        self.assertIn('-Dp2pkit.audit.jmdnsStartupPrimitives=true', java)
        self.assertEqual(calls[1][0][calls[1][0].index('--release') + 1], '8')
        self.assertEqual(calls[2][0][calls[2][0].index('--release') + 1], '17')
        for _, kwargs in calls:
            self.assertEqual(kwargs['cleanup_seconds'], 15)
            self.assertEqual(kwargs['log_limit'], 1024 * 1024)
            self.assertIs(kwargs['create_gradle_home'], False)
            self.assertEqual(kwargs['cwd'], ROOT)
            self.assertFalse(kwargs['cancelled']())

    def test_acquisition_and_compile_failure_stop_at_first_command(self):
        for index in (1, 2, 3):
            with self.subTest(index=index), self.controller(fail_at=index, failure=outcome(7)) as (diagnostic, calls):
                with self.assertRaises(d.rpc.QualificationError):
                    diagnostic.run()
                self.assertEqual(len(calls), index)
                self.assertEqual(diagnostic.result['commands'][-1]['exitCode'], 7)
                self.assertEqual(diagnostic.result['status'], 'FAIL')

    def test_control_failure_partial_duplicate_and_rescue_are_not_success(self):
        for exit_code, raw in ((1, 'FAIL mode=control phase=host_not_announced\n'),
                               (1, 'PASS mode=control\n'), (0, ''),
                               (0, 'PASS mode=control\nPASS mode=control\n'),
                               (0, 'PASS mode=control\nFAIL mode=control\n'),
                               (0, 'PASS mode=control\nphase=fixture_rescue_begin\n')):
            with self.subTest(exit_code=exit_code, raw=raw), self.controller(
                    fail_at=4, failure=outcome(exit_code), raw=raw) as (diagnostic, calls):
                with self.assertRaises(d.rpc.QualificationError):
                    diagnostic.run()
                self.assertEqual(len(calls), 4)
                self.assertEqual(diagnostic.result['status'], 'FAIL')

    def test_unsafe_or_inconsistent_outcome_never_reads_control_captures(self):
        for changes in ({'cleanupKnown': False}, {'capturesClosed': False}, {'timedOut': True},
                        {'code': 'CANCELLED'}, {'code': 'OUTPUT_LIMIT'}, {'exitCode': None},
                        {'exitCode': True}, {'code': 'PASS', 'exitCode': 1}):
            with self.subTest(changes=changes), self.controller(
                    fail_at=4, failure=outcome(**changes)) as (diagnostic, calls), \
                    patch.object(diagnostic, 'output', side_effect=AssertionError('Unclosed read')):
                with self.assertRaises(d.rpc.QualificationError):
                    diagnostic.run()
                self.assertEqual(len(calls), 4)
                self.assertEqual(diagnostic.result['status'], 'FAIL')

    def test_bad_launcher_or_override_refused_before_acquisition(self):
        for changes in ({'P2PKIT_JMDNS_FIXTURE_IPV4': '127.0.0.1'}, {}):
            with self.controller() as (diagnostic, calls), patch.dict(os.environ, changes), \
                    patch.object(d.rpc.sys, 'executable', 'relative-python'):
                with self.assertRaises(d.rpc.QualificationError):
                    diagnostic.run()
                self.assertEqual(calls, [])
                self.assertFalse((diagnostic.state / 'work/multicast').exists())

    def test_dependency_pin_mismatch_refused_before_compilation(self):
        with self.controller() as (diagnostic, calls), \
                patch.object(d.rpc.hashlib, 'sha256', return_value=Mock(hexdigest=lambda: '0' * 64)):
            with self.assertRaisesRegex(d.rpc.QualificationError, 'Dependency pin failed'):
                diagnostic.run()
            self.assertEqual(len(calls), 1)

    def test_changed_reviewed_metadata_pin_refused_before_download(self):
        document = d.rpc.ET.parse(ROOT / 'gradle/verification-metadata.xml')
        namespace = {'v': 'https://schema.gradle.org/dependency-verification'}
        pins = document.getroot().findall(
            "./v:components/v:component[@group='org.slf4j'][@name='slf4j-api'][@version='2.0.7']/"
            "v:artifact[@name='slf4j-api-2.0.7.jar']/v:sha256", namespace)
        self.assertEqual([pin.get('value') for pin in pins], [PIN])
        pins[0].set('value', '0' * 64)
        with self.controller() as (diagnostic, calls), patch.object(d.rpc.ET, 'parse', return_value=document):
            with self.assertRaisesRegex(d.rpc.QualificationError, 'Reviewed source dependency pin differs'):
                diagnostic.run()
            self.assertEqual(calls, [])

    def test_environment_filters_injection_and_secrets_but_retains_ownership(self):
        keys = (d.evidence.audit_processes.JOB_ENV, d.evidence.audit_processes.CHAIN_ENV,
                d.evidence.audit_processes.DOMAINS_ENV, d.evidence.audit_processes.STATE_ENV,
                d.evidence.audit_processes.PIPE_ENV, 'GRADLE_USER_HOME')
        forbidden = ('GITHUB_TOKEN', 'GH_TOKEN', 'MAVEN_SIGNING_KEY', 'JAVA_TOOL_OPTIONS',
                     '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'PYTHONPATH', 'HTTPS_PROXY', 'DYLD_INSERT_LIBRARIES')
        env = dict(self.env, **{key: 'test-owned' for key in keys}, **{key: 'DO_NOT_FORWARD' for key in forbidden})
        with patch.dict(os.environ, env, clear=True):
            diagnostic = self.diagnostic()
        self.assertTrue(all(diagnostic.environment[key] == 'test-owned' for key in keys))
        self.assertFalse(set(forbidden) & diagnostic.environment.keys())

    def test_cancel_and_exhausted_cumulative_budget_do_not_spawn(self):
        for cancelled, end in ((True, time.monotonic() + 90), (False, time.monotonic() + 10)):
            event = threading.Event()
            if cancelled:
                event.set()
            diagnostic = self.diagnostic(end, event)
            with patch.object(d.evidence, 'run_command') as command, self.assertRaises(d.rpc.QualificationError):
                diagnostic.invoke(d.COMMANDS[0], ['unused'], 90)
            command.assert_not_called()

    def test_shorter_parent_deadline_is_not_renewed(self):
        with patch.dict(os.environ, dict(self.env, **{d.DEADLINE: '130000000000'}), clear=True), \
                patch.object(d.platform, 'system', return_value='Darwin'), \
                patch.object(d.time, 'monotonic', return_value=100):
            self.assertEqual(d.admit(), 130)
            diagnostic = self.diagnostic(end=130)
            private = diagnostic.state / d.COMMANDS[0]
            private.mkdir()
            with patch.object(d.evidence, 'run_command', return_value=outcome()) as command:
                diagnostic.invoke(d.COMMANDS[0], ['unused'], 90)
            self.assertEqual(command.call_args.kwargs['timeout'], 15)

    def test_host_jdk_deadline_and_cli_admission_fail_closed(self):
        for env_changes, system in (({}, 'Linux'), ({'GITHUB_ACTIONS': 'false'}, 'Darwin'),
                                    ({'RUNNER_ENVIRONMENT': 'self-hosted'}, 'Darwin'),
                                    ({d.DEADLINE: 'bad'}, 'Darwin'), ({d.DEADLINE: '1'}, 'Darwin')):
            with self.subTest(env_changes=env_changes, system=system), \
                    patch.dict(os.environ, dict(self.env, **env_changes), clear=True), \
                    patch.object(d.platform, 'system', return_value=system), \
                    self.assertRaises(d.rpc.QualificationError):
                d.admit()
        (self.home / 'release').write_text('JAVA_VERSION="21.0.1"\n')
        with patch.dict(os.environ, self.env, clear=True), patch.object(d.platform, 'system', return_value='Darwin'), \
                self.assertRaises(d.rpc.QualificationError):
            d.admit()
        with patch.object(d, 'admit') as admit, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(d.main(['--force']), 1)
        admit.assert_not_called()

    def test_main_private_report_signal_restore_and_failure_status(self):
        for failed in (False, True):
            def run(diagnostic):
                if failed:
                    raise RuntimeError('PRIVATE')
                diagnostic.result['status'] = 'PASS'

            with self.subTest(failed=failed), patch.object(d, 'ROOT', self.root), \
                    patch.object(d, 'admit', return_value=time.monotonic() + 420), \
                    patch.object(d.Diagnostic, 'run', run), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
                self.assertEqual(d.main([]), int(failed))
                self.assertEqual({sig: signal.getsignal(sig) for sig in before}, before)
                self.assertNotIn('PRIVATE', output.getvalue())
                self.assertEqual(output.getvalue(), ('FAIL' if failed else 'PASS') + ' ' + d.SCOPE + '\n')
        reports = list((self.root / 'build/reports/jmdns-interpreter-diagnostic').glob('run-*/result.json'))
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertEqual(json.loads(report.read_text())['scope'], d.SCOPE)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_real_owned_subprocess_retains_original_failure_and_closed_captures(self):
        # Real local ownership/pipe cleanup, not native multicast evidence. No toolchain/network.
        with patch.dict(os.environ, {'PATH': os.environ.get('PATH', '')}, clear=True):
            diagnostic = self.diagnostic()
        with self.assertRaises(d.rpc.QualificationError):
            diagnostic.invoke(d.COMMANDS[0], [sys.executable, '-I', '-S', '-B', '-c',
                'print("LOCAL_CHILD_ONLY"); raise SystemExit(7)'], 90)
        row = diagnostic.result['commands'][0]
        self.assertEqual(row['exitCode'], 7)
        self.assertEqual(row['code'], 'COMMAND_FAILED')
        self.assertIs(row['cleanupKnown'], True)
        self.assertIs(row['capturesClosed'], True)
        self.assertEqual(diagnostic.output({'id': d.COMMANDS[0]}), b'LOCAL_CHILD_ONLY\n')
        self.assertEqual(diagnostic.result['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
