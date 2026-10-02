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
            environment=config['environment'], gradleDistribution={'OFFLINE': True}, xcodegen='/OFFLINE/bin/xcodegen',
            xcodegenPackage={'OFFLINE': True}, bootstrapExecuted=False, installationsRequested=False,
            priorResultsReusedAsNativeAdmission=False)
        b.write_new(parent / 'private-session/session-config.json', config)
        b.write_new(parent / 'prepared.json', prepared)
        local = SimpleNamespace(ROOT=root, SCOPE=prepared['scope'], BASELINE=prepared['baseline'], PLAN=('OFFLINE_PLAN',),
            bootstrap=b, local_host=Mock(), private_parent=lambda path: path, run_argv=lambda *_args: argv,
            source_admission=Mock(return_value=source),
            runner=SimpleNamespace(read_json=lambda path: json.loads(path.read_text()),
                                   disposable_roots=lambda _root: [root / 'build']),
            distribution=SimpleNamespace(admit_archive=Mock()),
            xcodegen_package=SimpleNamespace(admit=Mock(return_value=Path('/OFFLINE'))))
        return parent, local, config, prepared

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
