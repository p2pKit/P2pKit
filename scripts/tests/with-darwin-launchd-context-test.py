#!/usr/bin/env python3
"""Offline boundary controls. Never starts launchd, changes policy or runs a product."""
import copy
import ast
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('launchd_context', ROOT / 'scripts/with-darwin-launchd-context.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def environment():
    return dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=s.REF, GITHUB_EVENT_NAME='push',
                GITHUB_SHA='a' * 40, GITHUB_WORKSPACE=str(ROOT), RPC_QUALIFY_REQUESTED='true',
                RPC_APPLE_LAUNCHD_CONTEXT='true', RPC_QUALIFICATION_PARENT='/tmp/fixture', RUNNER_TEMP='/tmp')


def config():
    python = str(Path(sys.executable).resolve())
    return dict(uid=501, gid=20, groups=[20, 80], source={'commit': 'a' * 40, 'tree': 'b' * 40},
                environment=environment(), label='dev.p2pkit.rpc.qualification.' + 'a' * 32, argv=[python,
                str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', '/tmp/fixture', '--', python,
                str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64',
                '--intel-investigation', 'network'])


def proof():
    return dict(schema=1, scope=s.SCOPE, source=config()['source'], exitCode=1,
                stage='FINALIZED', logs={}, **dict.fromkeys(s.FLAGS, True))


class ContextTests(unittest.TestCase):
    def setUp(self):
        account = type('Account', (), dict(pw_name='runner', pw_gid=20))()
        for obj, name, value in ((s.platform, 'system', 'Darwin'), (s.pwd, 'getpwuid', account),
                                 (s.os, 'getgrouplist', [20, 80]), (s.os, 'getuid', 501),
                                 (s.os, 'geteuid', 501), (s, 'private_parent', None)):
            p = patch.object(obj, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.directory = Path('/tmp/fixture/launchd-context')

    def test_only_exact_hosted_feature_context_is_admitted(self):
        s.environment_admit(environment())
        for key, value in (('GITHUB_REF', 'refs/heads/main'), ('RPC_APPLE_LAUNCHD_CONTEXT', 'false'),
                           ('GITHUB_REPOSITORY', 'other/repo'), ('GITHUB_EVENT_NAME', 'workflow_dispatch'),
                           ('RUNNER_ENVIRONMENT', 'self-hosted'), ('RPC_QUALIFY_REQUESTED', 'false'),
                           ('GITHUB_SHA', 'HEAD'), ('GITHUB_WORKSPACE', '/')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.environment_admit({**environment(), key: value})
        with patch.object(s.platform, 'system', return_value='Linux'), self.assertRaises(RuntimeError):
            s.environment_admit(environment())

    def test_all_modes_preserve_original_audit_and_native_command(self):
        for lane in ('apple-x64', 'apple-arm64'):
            for tail in ([], ['--admission-only'], ['--intel-investigation', 'network'],
                         ['--intel-investigation', 'native'], ['--intel-investigation', 'cold-boot']):
                c = config()
                c['argv'] = c['argv'][:9] + [lane] + tail
                if lane == 'apple-arm64' and len(tail) == 2:
                    with self.assertRaises(RuntimeError):
                        s.config_validate(c, 501, 20, self.directory)
                else:
                    s.config_validate(c, 501, 20, self.directory)
        for argv in ([], ['/bin/sh'], config()['argv'][5:], config()['argv'] + ['--unsafe'],
                     config()['argv'][:9] + ['android-art']):
            with self.subTest(argv=argv), self.assertRaises(RuntimeError):
                s.config_validate({**config(), 'argv': argv}, 501, 20, self.directory)

    def test_root_wrong_user_changed_groups_or_arbitrary_job_label_rejected(self):
        for key, value in (('uid', 0), ('uid', 502), ('gid', 0), ('groups', [20]), ('groups', [20, 20, 80]),
                           ('label', 'com.apple.unrelated'), ('label', 'system/other'), ('label', 'a' * 32),
                           ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}), ('unexpected', 'private')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.config_validate({**config(), key: value}, 501, 20, self.directory)
        for uid, gid in ((0, 20), (501, 0), (True, 20), (501, True)):
            with self.assertRaises(RuntimeError):
                s.config_validate(config(), uid, gid, self.directory)
        with self.assertRaises(RuntimeError):
            s.config_validate(config(), 501, 20, Path('/tmp/unrelated'))

    def test_no_tokens_loader_hooks_native_bypass_or_other_context_forwarded(self):
        for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'SSH_AUTH_SOCK', 'SUDO_UID', 'SECURITYSESSIONID', 'BASH_ENV',
                    'PYTHONPATH', 'DYLD_INSERT_LIBRARIES', 'P2PKIT_AUDIT_STATE_DIR', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN',
                    'RPC_APPLE_SSH_CONTEXT'):
            c = config()
            c['environment'][key] = 'must-not-be-forwarded'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.config_validate(c, 501, 20, self.directory)

    def test_fixed_nonroot_system_job_has_no_socket_calendar_keepalive_or_gui_agent(self):
        group = type('Group', (), dict(gr_name='staff'))()
        with patch.object(s.grp, 'getgrgid', return_value=group):
            p = s.job_plist(config(), self.directory)
        self.assertEqual(p['UserName'], 'runner')
        self.assertEqual(p['GroupName'], 'staff')
        self.assertIs(p['InitGroups'], True)
        self.assertIs(p['KeepAlive'], False)
        self.assertIs(p['RunAtLoad'], True)
        self.assertEqual(p['ProcessType'], 'Background')
        self.assertEqual(p['ProgramArguments'][1:3], ['-I', '-S'])
        self.assertEqual(p['ProgramArguments'][3:], [str(ROOT / 'scripts/with-darwin-launchd-context.py'),
                                                   '--child', str(self.directory / 'config.json')])
        self.assertEqual(set(p), {'Label', 'UserName', 'GroupName', 'InitGroups', 'ProgramArguments', 'WorkingDirectory',
                                 'EnvironmentVariables', 'ProcessType', 'RunAtLoad', 'KeepAlive',
                                 'StandardOutPath', 'StandardErrorPath'})
        self.assertNotIn('/Library/LaunchDaemons', str(p))

    def test_stopped_job_requires_no_pid_and_an_exact_exit_not_a_stale_exit(self):
        self.assertEqual(s.job_status(b'\tstate = not running\n\tlast exit code = 1\n'), (True, 1))
        self.assertEqual(s.job_status(b'\tstate = running\n\tpid = 99\n\tlast exit code = 0\n'), (False, 0))
        self.assertEqual(s.job_status(b'\tstate = not running\n\tpid = 99\n\tlast exit code = 0\n'), (False, 0))
        self.assertEqual(s.job_status(b'\tstate = not running\n\tlast exit code = (never exited)\n'), (False, None))
        for raw in (b'', b'state = running\nstate = not running\n', b'state = not running\nlast exit code = 999\n'):
            with self.assertRaises(RuntimeError):
                s.job_status(raw)

    def test_privileged_setup_never_imports_executes_or_signals_product_code(self):
        source = (ROOT / 'scripts/with-darwin-launchd-context.py').read_text()
        tree = ast.parse(source)
        setup = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setup')
        body = ast.get_source_segment(source, setup)
        for forbidden in ('source_snapshot(', 'Popen(', 'os.exec', 'os.kill', 'importlib', 'run-audit-command',
                          'tccutil', 'launchctl("kill"', 'launchctl("enable"'):
            self.assertNotIn(forbidden, body)
        self.assertIn('job_status(state.stdout) == (True, finished["exitCode"])', body)
        self.assertIn('read_private(plist, 0) == expected', body)
        self.assertIn('launchctl("print", target).returncode == 113', body)

    def test_child_cannot_inspect_source_or_reach_native_command_before_credential_and_parent_checks(self):
        c = config()
        with patch.object(s, 'read_json', return_value=c), patch.object(s, 'source_snapshot') as snapshot, \
             patch.object(s.subprocess, 'call') as call:
            for uid, euid, gid, egid, parent in ((0, 0, 0, 0, 1), (501, 0, 20, 20, 1),
                                              (501, 501, 20, 0, 1), (501, 501, 20, 20, 99)):
                with patch.object(s.os, 'getuid', return_value=uid), patch.object(s.os, 'geteuid', return_value=euid), \
                     patch.object(s.os, 'getgid', return_value=gid), patch.object(s.os, 'getegid', return_value=egid), \
                     patch.object(s.os, 'getppid', return_value=parent), self.assertRaises(RuntimeError):
                    s.child(self.directory / 'config.json')
            snapshot.assert_not_called()
            call.assert_not_called()

    def test_cleanup_cannot_convert_failed_native_command_to_pass(self):
        p = proof()
        self.assertEqual(s.validate_proof(p, p['source'])['exitCode'], 1)
        for field in s.FLAGS:
            wrong = {**p, field: False}
            self.assertEqual(s.validate_proof(wrong, p['source'], complete=False), wrong)
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                s.validate_proof(wrong, p['source'])
        for key, value in (('exitCode', 255), ('stage', 'CHILD')):
            with self.assertRaises(RuntimeError):
                s.validate_proof({**p, key: value}, p['source'])

    def test_public_proof_is_closed_and_type_strict(self):
        p = proof()
        for key, value in (('exitCode', True), ('schema', True), ('nonrootChild', 1), ('scope', 'PHYSICAL_LAN'),
                           ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}), ('private-log', 'private'),
                           ('logs', {'child.stderr': {'raw': 'private'}})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.validate_proof({**p, key: value}, p['source'], complete=False)

    def test_public_collector_requires_removed_job_plist_and_exact_success(self):
        spec = importlib.util.spec_from_file_location('q_launchd_test', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        p = proof()
        p['exitCode'] = 0
        r = dict(source=p['source'], lane='apple-x64', result='PASS', launchdContextRequired=True, appleLaunchdContext=p)
        self.assertEqual(q.public_summary(r)['appleLaunchdContext'], p)
        for field in s.FLAGS:
            wrong = copy.deepcopy(r)
            wrong['appleLaunchdContext'][field] = False
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                q.public_summary(wrong)
            wrong['result'] = 'FAIL'
            self.assertFalse(q.public_summary(wrong)['appleLaunchdContext'][field])
        for context in (None, {**p, 'exitCode': 1}):
            with self.assertRaises(RuntimeError):
                q.public_summary({**r, 'appleLaunchdContext': context})
        with self.assertRaises(RuntimeError):
            q.public_summary({**r, 'sshContextRequired': True})

    def test_workflow_starts_with_diagnostic_only_and_preserves_direct_default(self):
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn("RPC_APPLE_LAUNCHD_CONTEXT: ${{ matrix.investigation == 'network' }}", workflow)
        self.assertIn('if test "$RPC_APPLE_LAUNCHD_CONTEXT" = true; then', workflow)
        self.assertIn('python3 scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" --', workflow)
        self.assertIn('python3 scripts/tests/with-darwin-launchd-context-test.py', workflow)


class PrivateFiles(unittest.TestCase):
    def test_no_symlinks_ambiguous_keys_or_nonprivate_files(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name).resolve()
            path = directory / 'config.json'
            s.write_json(path, {'schema': 1})
            self.assertEqual(s.read_json(path), {'schema': 1})
            with self.assertRaises(FileExistsError):
                s.write_json(path, {})
            path.chmod(0o644)
            with self.assertRaises(RuntimeError):
                s.read_json(path)
            path.chmod(0o600)
            path.write_text('{"schema":1,"schema":2}')
            with self.assertRaises(RuntimeError):
                s.read_json(path)
            link = directory / 'link'
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                s.read_json(link)
            directory.chmod(0o755)
            with self.assertRaises(RuntimeError):
                s.private_parent(directory, os.getuid())


if __name__ == '__main__':
    unittest.main()
