#!/usr/bin/env python3
"""Offline authorization transport controls. No GUI, sudo or privileged execution."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('arm_authorization_tests', ROOT / 'scripts/authorize-rpc-local-arm.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
spec = importlib.util.spec_from_file_location('authorization_existing_bootstrap', ROOT / 'scripts/with-darwin-audit-session.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class Authorization(unittest.TestCase):
    def test_suffix_is_explicit_and_cannot_change_between_preparation_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, config, prepared = self.fixture(Path(tmp).resolve())
            prepared.update(cliRemainingOnly=True, cliFirstCase='admission-pressure-0', plan=['OFFLINE_CLI'])
            config['argv'] = local.run_argv(parent, 'a' * 40, False, False, False, True, 'admission-pressure-0')
            (parent / 'private-session/session-config.json').write_text(json.dumps(config))
            (parent / 'prepared.json').write_text(json.dumps(prepared))
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run:
                request = m.preflight(parent, 'a' * 40, local)
                self.assertEqual(request['cliFirstCase'], 'admission-pressure-0')
                for first in (None, True, [], 'admission-pressure-1', 'command-contract'):
                    with self.subTest(first=first), self.assertRaises(RuntimeError):
                        (parent / 'prepared.json').write_text(json.dumps(prepared | {'cliFirstCase': first}))
                        m.preflight(parent, 'a' * 40, local)
                del prepared['cliFirstCase']
                (parent / 'prepared.json').write_text(json.dumps(prepared))
                with self.assertRaises(RuntimeError):
                    m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_native_result_cannot_change_or_omit_the_requested_suffix(self):
        for first, omitted in ((None, False), ('admission-pressure-1', False), (True, False), ('admission-pressure-0', True)):
            with self.subTest(first=first, omitted=omitted), tempfile.TemporaryDirectory() as tmp:
                parent, local, config, prepared = self.fixture(Path(tmp).resolve())
                prepared.update(cliRemainingOnly=True, cliFirstCase='admission-pressure-0', plan=['OFFLINE_CLI'])
                config['argv'] = local.run_argv(parent, 'a' * 40, False, False, False, True, 'admission-pressure-0')
                (parent / 'private-session/session-config.json').write_text(json.dumps(config))
                (parent / 'prepared.json').write_text(json.dumps(prepared))
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run', side_effect=self.result_fixture(parent, local, plan=['OFFLINE_CLI'],
                            remaining_mode=True, first_case=first, omit_first=omitted)) as run, self.assertRaises(RuntimeError):
                    m.authorize(parent, 'a' * 40, local)
                run.assert_called_once()
                self.assertFalse((parent / 'gui-authorization-result.json').exists())

    def test_explicit_null_suffix_is_required_even_for_other_qualification_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, _, prepared = self.fixture(Path(tmp).resolve())
            del prepared['cliFirstCase']
            (parent / 'prepared.json').write_text(json.dumps(prepared))
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run, self.assertRaises(RuntimeError):
                m.preflight(parent, 'a' * 40, local)
            run.assert_not_called()

    def test_remaining_cli_selection_is_bound_before_prompt_and_cannot_be_downgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, config, prepared = self.fixture(Path(tmp).resolve())
            prepared.update(cliRemainingOnly=True, plan=['OFFLINE_CLI'])
            config['argv'] = local.run_argv(parent, 'a' * 40, False, False, False, True)
            (parent / 'private-session/session-config.json').write_text(json.dumps(config))
            (parent / 'prepared.json').write_text(json.dumps(prepared))
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run:
                request = m.preflight(parent, 'a' * 40, local)
                self.assertIs(request['cliRemainingOnly'], True)
                self.assertIs(request['cliProcessOnly'], False)
                for change in ({'cliRemainingOnly': False}, {'cliRemainingOnly': 1}, {'cliRemainingOnly': None},
                               {'cliProcessOnly': True}, {'plan': ['OFFLINE_PLAN']}):
                    with self.subTest(change=change), self.assertRaises(RuntimeError):
                        (parent / 'prepared.json').write_text(json.dumps(prepared | change))
                        m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_result_cannot_substitute_remaining_selection_or_missing_boolean(self):
        for mode in (True, 0, None):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                parent, local, _, _ = self.fixture(Path(tmp).resolve())
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run', side_effect=self.result_fixture(
                            parent, local, remaining_mode=mode)) as run, self.assertRaises(RuntimeError):
                    m.authorize(parent, 'a' * 40, local)
                run.assert_called_once()
                self.assertFalse((parent / 'gui-authorization-result.json').exists())

    def test_cli_only_preflight_binds_explicit_selector_and_refuses_plan_or_command_substitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, config, prepared = self.fixture(Path(tmp).resolve())
            prepared.update(cliProcessOnly=True, plan=['OFFLINE_CLI'])
            config['argv'] = local.run_argv(parent, 'a' * 40, False, False, True)
            (parent / 'private-session/session-config.json').write_text(json.dumps(config))
            (parent / 'prepared.json').write_text(json.dumps(prepared))
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run:
                request = m.preflight(parent, 'a' * 40, local)
                self.assertIs(request['cliProcessOnly'], True)
                self.assertEqual(request['requestedPlan'], ['OFFLINE_CLI'])
                for change in ({'cliProcessOnly': False}, {'cliProcessOnly': 1}, {'cliProcessOnly': None},
                               {'plan': ['OFFLINE_PLAN']}):
                    with self.subTest(change=change), self.assertRaises(RuntimeError):
                        (parent / 'prepared.json').write_text(json.dumps(prepared | change))
                        m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_result_cannot_substitute_cli_selection_or_missing_boolean(self):
        for mode in (True, 0, None):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                parent, local, _, _ = self.fixture(Path(tmp).resolve())
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run', side_effect=self.result_fixture(
                            parent, local, cli_mode=mode)) as run, self.assertRaises(RuntimeError):
                    m.authorize(parent, 'a' * 40, local)
                run.assert_called_once()
                self.assertFalse((parent / 'gui-authorization-result.json').exists())

    def fixture(self, base):
        parent, root = base / 'request', base / 'source'
        parent.mkdir(mode=0o700)
        (parent / 'private-session').mkdir(mode=0o700)
        (root / 'scripts').mkdir(parents=True)
        (root / 'scripts/with-darwin-audit-session.py').write_bytes(b'OFFLINE NEVER EXECUTED')
        source = dict(commit='a' * 40, tree='b' * 40, status='', diffSha256='c' * 64)
        argv = [sys.executable, '-B', str(root / 'scripts/run-rpc-local-arm-qualification.py'), 'run',
                '--owner-authorized-arm27', '--parent', str(parent), '--expected-commit', source['commit']]
        config = dict(uid=os.getuid(), gid=os.getgid(), cwd=str(root), argv=argv, environment={'PATH': '/OFFLINE'})
        prepared = dict(schema=1, scope='OFFLINE_SCOPE', baseline='d' * 40, source=source, plan=['OFFLINE_PLAN'],
            swiftRuntimeOnly=False, macGeneratorOnly=False, cliProcessOnly=False, cliRemainingOnly=False, cliFirstCase=None,
            environment=config['environment'], gradleDistribution={'OFFLINE': True}, xcodegen='/OFFLINE/bin/xcodegen',
            xcodegenPackage={'OFFLINE': True}, bootstrapExecuted=False, installationsRequested=False,
            priorResultsReusedAsNativeAdmission=False)
        b.write_new(parent / 'private-session/session-config.json', config)
        b.write_new(parent / 'prepared.json', prepared)
        local = SimpleNamespace(ROOT=root, SCOPE=prepared['scope'], BASELINE=prepared['baseline'], PLAN=('OFFLINE_PLAN',),
            bootstrap=b, local_host=Mock(), private_parent=lambda path: path,
            run_argv=lambda _parent, _expected, only=False, clock=False, cli=False, remaining=False, first=None: argv + (
                ['--swift-runtime-only'] if only else ['--mac-generator-only'] if clock else ['--cli-process-only'] if cli
                else ['--cli-remaining-only'] if remaining else []) + (['--cli-first-case', first] if first is not None else []),
            plan_for=lambda only, clock=False, cli=False, remaining=False, first=None: ('OFFLINE_SWIFT',) if only else (
                'OFFLINE_CLOCK',) if clock else ('OFFLINE_CLI',) if cli or remaining else ('OFFLINE_PLAN',),
            source_admission=Mock(return_value=source),
            runner=SimpleNamespace(read_json=lambda path: json.loads(path.read_text()),
                                   disposable_roots=lambda _root: [root / 'build']),
            distribution=SimpleNamespace(admit_archive=Mock()),
            xcodegen_package=SimpleNamespace(admit=Mock(return_value=Path('/OFFLINE'))))
        return parent, local, config, prepared

    def test_swift_only_preflight_binds_selector_plan_and_exact_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, config, prepared = self.fixture(Path(tmp).resolve())
            config['argv'] = config['argv'] + ['--swift-runtime-only']
            prepared.update(swiftRuntimeOnly=True, plan=['OFFLINE_SWIFT'])
            (parent / 'private-session/session-config.json').write_text(json.dumps(config))
            (parent / 'prepared.json').write_text(json.dumps(prepared))
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run:
                request = m.preflight(parent, 'a' * 40, local)
            run.assert_not_called()
            self.assertTrue(request['swiftRuntimeOnly'])
            self.assertEqual(request['requestedPlan'], ['OFFLINE_SWIFT'])

    def test_missing_ambiguous_or_mismatched_selection_never_opens_a_dialog(self):
        for kind in ('missing', 'integer', 'string', 'argv', 'plan'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                parent, local, config, prepared = self.fixture(Path(tmp).resolve())
                if kind == 'missing':
                    del prepared['swiftRuntimeOnly']
                elif kind == 'integer':
                    prepared['swiftRuntimeOnly'] = 0
                elif kind == 'string':
                    prepared['swiftRuntimeOnly'] = 'false'
                elif kind == 'argv':
                    config['argv'] = config['argv'] + ['--swift-runtime-only']
                else:
                    prepared['plan'] = ['OFFLINE_SWIFT']
                (parent / 'private-session/session-config.json').write_text(json.dumps(config))
                (parent / 'prepared.json').write_text(json.dumps(prepared))
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run') as run, self.assertRaises(RuntimeError):
                    m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_only_native_logged_in_unprivileged_console_account_may_prompt(self):
        m.gui_session('Darwin', 501, 501, 501)
        for values in (('Linux', 501, 501, 501), ('Darwin', 0, 0, 0), ('Darwin', 501, 0, 501),
                       ('Darwin', 501, 501, 0), ('Darwin', 501, 501, 502)):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                m.gui_session(*values)

    def test_dialog_receives_data_not_interpolated_applescript_or_a_password(self):
        python = Path('/EXPLICIT/python3')
        bootstrap = Path('/SOURCE/strange \"quote\"/with-darwin-audit-session.py')
        config = Path("/PRIVATE/space; 'quote'/session-config.json")
        argv = m.dialog_argv(python, bootstrap, config, 501, 20)
        self.assertEqual(argv[:2], ['/usr/bin/osascript', '-e'])
        self.assertEqual(argv[2], m.APPLESCRIPT)
        self.assertEqual(shlex.split(argv[3]), ['exec', '/usr/bin/env', '-i', 'SUDO_UID=501', 'SUDO_GID=20',
            str(python), '-I', '-S', str(bootstrap), '--bootstrap', str(config)])
        self.assertNotIn(str(config), m.APPLESCRIPT)
        self.assertIn('with administrator privileges', m.APPLESCRIPT)
        self.assertNotIn('password', m.APPLESCRIPT)
        self.assertNotIn('user name', m.APPLESCRIPT)
        self.assertNotIn('sudoers', ' '.join(argv))

    def test_preflight_checks_exact_source_inputs_and_runs_no_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, config, _ = self.fixture(Path(tmp).resolve())
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run:
                request = m.preflight(parent, 'a' * 40, local)
            run.assert_not_called()
            local.source_admission.assert_called_once_with('a' * 40)
            local.distribution.admit_archive.assert_called_once()
            local.xcodegen_package.admit.assert_called_once()
            self.assertEqual(request['configPath'], str(parent / 'private-session/session-config.json'))
            self.assertFalse(request['persistentPrivilege'])
            self.assertEqual(config['uid'], request['uid'])

    def test_consumed_or_already_prompted_request_is_rejected_before_any_dialog(self):
        for marker in ('state', 'local-session-admission.json', 'private-session/session-admission.json',
                       'gui-authorization-request.json'):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as tmp:
                parent, local, _, _ = self.fixture(Path(tmp).resolve())
                (parent / marker).write_bytes(b'CONSUMED')
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run') as run, self.assertRaises(RuntimeError):
                    m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_wrong_command_and_environment_cannot_be_authorized(self):
        for kind in ('command', 'environment'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                parent, local, config, _ = self.fixture(Path(tmp).resolve())
                if kind == 'command':
                    config['argv'] = ['/NOT_ADMITTED']
                else:
                    config['environment'] = {'PATH': '/OTHER'}
                (parent / 'private-session/session-config.json').write_text(json.dumps(config))
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        self.assertRaises(RuntimeError):
                    m.preflight(parent, 'a' * 40, local)

    def test_unprepared_input_or_existing_outputs_prevents_a_prompt(self):
        for kind in ('archive', 'package', 'outputs'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                parent, local, _, _ = self.fixture(Path(tmp).resolve())
                if kind == 'archive':
                    local.distribution.admit_archive.side_effect = RuntimeError('OFFLINE changed input')
                elif kind == 'package':
                    local.xcodegen_package.admit.side_effect = RuntimeError('OFFLINE missing preset')
                else:
                    (local.ROOT / 'build').mkdir()
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run') as run, self.assertRaises(RuntimeError):
                    m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_cancellation_is_recorded_once_and_never_retries_or_forges_a_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, _, _ = self.fixture(Path(tmp).resolve())
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=1)) as run, \
                    patch('builtins.print'):
                self.assertEqual(m.authorize(parent, 'a' * 40, local), 1)
                with self.assertRaises(RuntimeError):
                    m.authorize(parent, 'a' * 40, local)
            run.assert_called_once()
            self.assertFalse(run.call_args.kwargs.get('shell', False))
            self.assertEqual(run.call_args.kwargs['stdin'], m.subprocess.DEVNULL)
            self.assertFalse((parent / 'private-session/session-admission.json').exists())
            self.assertFalse((parent / 'state').exists())
            record = json.loads((parent / 'gui-authorization-result.json').read_text())
            self.assertEqual(record['authorizationTransportExitCode'], 1)
            self.assertIsNone(record['nativeResult'])
            self.assertFalse(record['bootstrapAutomaticallyRetried'])

    def test_successful_dialog_without_native_result_is_not_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, _, _ = self.fixture(Path(tmp).resolve())
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                    patch('builtins.print'):
                self.assertEqual(m.authorize(parent, 'a' * 40, local), 125)

    def result_fixture(self, parent, local, mode=False, plan=None, clock_mode=False, cli_mode=False, remaining_mode=False,
                       first_case=None, omit_first=False):
        def executed(_argv, **_kwargs):
            directory = parent / 'state/private'
            directory.mkdir(parents=True)
            # Synthetic transport input, never an admitted native receipt.
            result = dict(source=local.source_admission.return_value, scope=local.SCOPE, result='PASS',
                          swiftRuntimeOnly=mode, macGeneratorOnly=clock_mode, cliProcessOnly=cli_mode,
                          cliRemainingOnly=remaining_mode, cliFirstCase=first_case,
                          requestedPlan=['OFFLINE_PLAN'] if plan is None else plan)
            if omit_first:
                del result['cliFirstCase']
            (directory / 'result.json').write_text(json.dumps(result))
            return SimpleNamespace(returncode=0)
        return executed

    def test_matching_result_still_requires_independent_native_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, _, _ = self.fixture(Path(tmp).resolve())
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run', side_effect=self.result_fixture(parent, local)), \
                    patch('builtins.print'):
                self.assertEqual(m.authorize(parent, 'a' * 40, local), 0)
            record = json.loads((parent / 'gui-authorization-result.json').read_text())
            self.assertEqual(record['nativeResult'], 'PASS')
            self.assertFalse(record['nativeResultIndependentlyVerified'])

    def test_result_for_different_selector_or_plan_cannot_be_returned_as_success(self):
        for mode, plan in ((True, ['OFFLINE_PLAN']), (False, ['OFFLINE_SWIFT']), (0, ['OFFLINE_PLAN'])):
            with self.subTest(mode=mode, plan=plan), tempfile.TemporaryDirectory() as tmp:
                parent, local, _, _ = self.fixture(Path(tmp).resolve())
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run', side_effect=self.result_fixture(parent, local, mode, plan)) as run, \
                        self.assertRaises(RuntimeError):
                    m.authorize(parent, 'a' * 40, local)
                run.assert_called_once()
                self.assertTrue((parent / 'gui-authorization-request.json').is_file())
                self.assertFalse((parent / 'gui-authorization-result.json').exists())

    def test_clock_only_preflight_binds_command_plan_and_explicit_selector(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, local, config, prepared = self.fixture(Path(tmp).resolve())
            prepared.update(macGeneratorOnly=True, plan=['OFFLINE_CLOCK'])
            config['argv'] = local.run_argv(parent, 'a' * 40, False, True)
            (parent / 'private-session/session-config.json').write_text(json.dumps(config))
            (parent / 'prepared.json').write_text(json.dumps(prepared))
            with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                    patch.object(m.subprocess, 'run') as run:
                request = m.preflight(parent, 'a' * 40, local)
                self.assertIs(request['macGeneratorOnly'], True)
                self.assertEqual(request['requestedPlan'], ['OFFLINE_CLOCK'])
                for change in ({'macGeneratorOnly': False}, {'macGeneratorOnly': 1}, {'macGeneratorOnly': None},
                               {'plan': ['OFFLINE_PLAN']}):
                    with self.subTest(change=change), self.assertRaises(RuntimeError):
                        (parent / 'prepared.json').write_text(json.dumps(prepared | change))
                        m.preflight(parent, 'a' * 40, local)
                run.assert_not_called()

    def test_result_cannot_substitute_clock_selection_or_missing_boolean(self):
        for mode in (True, 0, None):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                parent, local, _, _ = self.fixture(Path(tmp).resolve())
                with patch.object(m, 'gui_session'), patch.object(m, 'console_uid', return_value=os.getuid()), \
                        patch.object(m.subprocess, 'run', side_effect=self.result_fixture(
                            parent, local, clock_mode=mode)) as run, self.assertRaises(RuntimeError):
                    m.authorize(parent, 'a' * 40, local)
                run.assert_called_once()
                self.assertFalse((parent / 'gui-authorization-result.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
