#!/usr/bin/env python3
"""Offline controls only: never starts SSH, alters security or executes an Apple product."""
import copy
import base64
import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ssh_context', ROOT / 'scripts/with-darwin-ssh-context.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def environment():
    return dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=s.REF, GITHUB_EVENT_NAME='push',
                GITHUB_SHA='a' * 40, GITHUB_WORKSPACE=str(ROOT), RPC_QUALIFY_REQUESTED='true',
                RPC_APPLE_SSH_CONTEXT='true', RPC_QUALIFICATION_PARENT='/fixture')


def config():
    python = str(Path(sys.executable).resolve())
    return dict(uid=501, gid=20, groups=[20, 80], source={'commit': 'a' * 40, 'tree': 'b' * 40},
                sessionMode='REALLOCATED', controllerSession=41,
                environment=environment(), ports=[42000, 42001], argv=[python,
                str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', '/fixture', '--', python,
                str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64',
                '--intel-investigation', 'network'])


def proof():
    return dict(schema=2, scope=s.SCOPE, source=config()['source'], exitCode=1, serverExitCode=0,
                stage='FINALIZED', diagnostics={}, finalizationErrors=[], sessionMode='REALLOCATED',
                auditSession=dict.fromkeys(s.SESSION_FIELDS, True),
                serverClose=dict(acceptedKey=1, applicationDisconnect=0, disconnectedUser=0, eof=1,
                                 unexpectedLines=0, sequence='EOF'),
                **dict.fromkeys(s.PROOF_FLAGS, True))


class SshContextTests(unittest.TestCase):
    def setUp(self):
        for name, value in (('getuid', 501), ('geteuid', 501), ('getgid', 20), ('getegid', 20), ('getgroups', [20, 80])):
            p = patch.object(s.os, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(s.platform, 'system', return_value='Darwin')
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(s.platform, 'machine', return_value='x86_64')
        p.start()
        self.addCleanup(p.stop)

    def test_only_exact_feature_hosted_nonroot_context_is_admitted(self):
        s.admit_environment(environment())
        for key, value in (('GITHUB_REF', 'refs/heads/main'), ('RPC_APPLE_SSH_CONTEXT', 'false'),
                           ('GITHUB_REPOSITORY', 'other/repo'), ('GITHUB_EVENT_NAME', 'workflow_dispatch'),
                           ('RUNNER_ENVIRONMENT', 'self-hosted'), ('RPC_QUALIFY_REQUESTED', 'false'),
                           ('GITHUB_SHA', 'HEAD'), ('GITHUB_WORKSPACE', '/')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.admit_environment({**environment(), key: value})
        for key in ('getuid', 'geteuid', 'getgid', 'getegid'):
            with patch.object(s.os, key, return_value=0), self.assertRaises(RuntimeError):
                s.admit_environment(environment())
        with patch.object(s.platform, 'system', return_value='Linux'), self.assertRaises(RuntimeError):
            s.admit_environment(environment())

    def test_original_native_audit_command_is_required_in_every_mode(self):
        for lane in ('apple-x64', 'apple-arm64'):
            for tail in ([], ['--admission-only'], ['--intel-investigation', 'network'],
                         ['--intel-investigation', 'native'], ['--intel-investigation', 'cold-boot']):
                c = config()
                c['argv'] = c['argv'][:9] + [lane] + tail
                if lane == 'apple-arm64' and len(tail) == 2:
                    with self.assertRaises(RuntimeError):
                        s.config_validate(c)
                else:
                    s.config_validate(c)
        for argv in ([], ['/bin/sh'], config()['argv'][5:], config()['argv'] + ['--unsafe'],
                     config()['argv'][:9] + ['android-art'], config()['argv'][:10] + ['--admission-only', '--unsafe']):
            with self.subTest(argv=argv), self.assertRaises(RuntimeError):
                s.config_validate({**config(), 'argv': argv})

    def test_changed_credentials_source_and_reserved_or_unbounded_ports_are_rejected(self):
        for key, value in (('uid', 502), ('gid', 21), ('groups', [20]), ('groups', [20, 20, 80]),
                           ('ports', [22, 42001]), ('ports', [True, 42001]), ('ports', [42001, 65536]),
                           ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}), ('unexpected', 'private'),
                           ('sessionMode', 'SKIP_ADMISSION'), ('controllerSession', True),
                           ('controllerSession', -1), ('controllerSession', 0x100000000)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.config_validate({**config(), key: value})

    def test_no_tokens_ssh_agents_loader_hooks_or_native_ownership_override_forwarded(self):
        for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'SSH_AUTH_SOCK', 'SUDO_UID', 'SECURITYSESSIONID', 'BASH_ENV',
                    'PYTHONPATH', 'DYLD_INSERT_LIBRARIES', 'P2PKIT_AUDIT_STATE_DIR', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN'):
            c = config()
            c['environment'][key] = 'must-not-be-forwarded'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.config_validate(c)

    def test_server_restricts_authentication_interfaces_users_and_every_forwarding_path(self):
        text = s.server_config(Path('/fixture'), 'runner', ['/python', '-I', '-S', '/fixed-child']).decode()
        self.assertIn('AllowUsers runner\n', text)
        self.assertIn('ForceCommand /python -I -S /fixed-child\n', text)
        for key, value in {'ListenAddress': '127.0.0.1', 'AuthenticationMethods': 'publickey',
                           'PermitRootLogin': 'no', 'PasswordAuthentication': 'no', 'KbdInteractiveAuthentication': 'no',
                           'StrictModes': 'yes', 'PermitUserRC': 'no', 'PermitUserEnvironment': 'no',
                           'PermitTTY': 'no', 'DisableForwarding': 'yes', 'AllowTcpForwarding': 'no',
                           'AllowStreamLocalForwarding': 'no', 'AllowAgentForwarding': 'no', 'X11Forwarding': 'no',
                           'GatewayPorts': 'no', 'PermitTunnel': 'no', 'MaxSessions': '1', 'UsePAM': 'yes'}.items():
            self.assertIn(key + ' ' + value + '\n', text)
        self.assertNotIn('Include ', text)
        for account in ('root\nPermitRootLogin yes', '*', 'runner other', 'runner@*', ''):
            with self.assertRaises(RuntimeError):
                s.server_config(Path('/fixture'), account, ['/fixed'])

    def test_client_pins_only_fresh_identity_and_never_inherits_user_ssh_configuration(self):
        cmd = s.client_command(Path('/fixture'), 42001, 'runner')
        self.assertEqual(cmd[:5], ['/usr/bin/ssh', '-4', '-T', '-F', '/dev/null'])
        self.assertEqual(cmd[-2:], ['runner@127.0.0.1', 'p2pkit-fixed-command'])
        for option in ('StrictHostKeyChecking=yes', 'IdentitiesOnly=yes', 'IdentityAgent=none',
                       'UserKnownHostsFile=/fixture/known_hosts', 'GlobalKnownHostsFile=/dev/null',
                       'UpdateHostKeys=no', 'VerifyHostKeyDNS=no', 'ClearAllForwardings=yes',
                       'ControlPath=none', 'ProxyCommand=none', 'ProxyJump=none'):
            self.assertIn(option, cmd)
        self.assertNotIn('-L', cmd)
        self.assertNotIn('-R', cmd)

    def test_control_finalization_does_not_turn_failed_tests_into_success(self):
        p = proof()
        self.assertEqual(s.validate_proof(p, p['source'])['exitCode'], 1)
        for key in s.PROOF_FLAGS:
            wrong = {**p, key: False}
            self.assertEqual(s.validate_proof(wrong, p['source'], complete=False), wrong)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.validate_proof(wrong, p['source'])
        for key, value in (('exitCode', 255), ('serverExitCode', None), ('serverExitCode', 1), ('serverExitCode', 255),
                           ('serverClose', None), ('auditSession', None), ('stage', 'CHILD'),
                           ('finalizationErrors', ['SOCKET_CLOSE'])):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.validate_proof({**p, key: value}, p['source'])

    def test_proof_rejects_unknown_output_and_type_confusion(self):
        p = proof()
        for key, value in (('exitCode', True), ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}),
                           ('scope', 'PHYSICAL_LAN'), ('schema', True), ('stage', 'PRIVATE_HOSTNAME'),
                           ('authenticatedInvokingUser', 1), ('private-key', 'must-not-export'),
                           ('auditSession', {'id': 42}), ('sessionMode', 'PUBLIC_LAN'),
                           ('serverClose', {**p['serverClose'], 'eof': True}),
                           ('diagnostics', {'setup': {'raw': 'private'}})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.validate_proof({**p, key: value}, p['source'], complete=False)

    def test_public_collector_requires_all_ssh_finalization_flags_before_pass(self):
        spec = importlib.util.spec_from_file_location('q_ssh_test', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        p = proof()
        p['exitCode'] = 0
        r = dict(source=p['source'], lane='apple-x64', result='PASS', sshContextRequired=True, appleSshContext=p)
        self.assertEqual(q.public_summary(r)['appleSshContext'], p)
        for field in s.PROOF_FLAGS:
            wrong = copy.deepcopy(r)
            wrong['appleSshContext'][field] = False
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                q.public_summary(wrong)
            wrong['result'] = 'FAIL'
            self.assertFalse(q.public_summary(wrong)['appleSshContext'][field])
        for context in (None, {**p, 'exitCode': 1}):
            with self.assertRaises(RuntimeError):
                q.public_summary({**r, 'appleSshContext': context})

    def test_only_explicit_native_intel_network_mode_can_retain_the_authenticated_session(self):
        c = config()
        c['sessionMode'] = 'AUTHENTICATED_SSH'
        c['argv'] = c['argv'][5:]
        s.config_validate(c)
        for argv in (config()['argv'], c['argv'] + ['--unsafe'], c['argv'][:-2],
                     c['argv'][:-1] + ['native'], c['argv'][:4] + ['apple-arm64'] + c['argv'][5:]):
            with self.subTest(argv=argv), self.assertRaises(RuntimeError):
                s.config_validate({**c, 'argv': argv})
        with patch.object(s.platform, 'machine', return_value='arm64'), self.assertRaises(RuntimeError):
            s.config_validate(c)
        spec = importlib.util.spec_from_file_location('q_ssh_native_test', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        p = {**proof(), 'exitCode': 0, 'sessionMode': 'AUTHENTICATED_SSH'}
        r = dict(source=p['source'], lane='apple-x64', result='PASS', sshContextRequired=True,
                 intelInvestigation='network', appleSshContext=p)
        self.assertEqual(q.public_summary(r)['appleSshContext'], p)
        for change in (dict(lane='apple-arm64'), dict(intelInvestigation=None), dict(intelInvestigation='native')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                q.public_summary({**r, **change})

    def test_unassigned_shared_wrong_user_or_changed_sessions_never_admit_native_inheritance(self):
        before = dict(id=42, auditUser=501, observedSha256='c' * 64)
        self.assertEqual(s.session_observation(41, before, before), dict.fromkeys(s.SESSION_FIELDS, True))
        cases = [('assigned', 41, {**before, 'id': 0}, {**before, 'id': 0}),
                 ('assigned', 41, {**before, 'id': 0xffffffff}, {**before, 'id': 0xffffffff}),
                 ('differentFromController', 42, before, before),
                 ('authenticatedAuditUser', 41, {**before, 'auditUser': 0}, {**before, 'auditUser': 0}),
                 ('unchanged', 41, before, None), ('unchanged', 41, before, {**before, 'id': 43}),
                 ('unchanged', 41, before, {**before, 'observedSha256': 'd' * 64})]
        for field, controller, first, after in cases:
            session = s.session_observation(controller, first, after)
            self.assertFalse(session[field])
            p = {**proof(), 'sessionMode': 'AUTHENTICATED_SSH', 'auditSession': session}
            s.validate_proof(p, p['source'], complete=False)
            with self.subTest(field=field, controller=controller), self.assertRaises(RuntimeError):
                s.validate_proof(p, p['source'])
        for key, value in (('id', True), ('id', -1), ('id', 0x100000000), ('auditUser', None),
                           ('observedSha256', 'PRIVATE'), ('extra', 'private')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.session_observation(41, {**before, key: value})
        for wrong in (None, True, -1, 0x100000000):
            with self.subTest(controller=wrong), self.assertRaises(RuntimeError):
                s.session_observation(wrong, before)

    def test_server_255_requires_actual_exact_authenticated_application_disconnect_not_a_bare_exit(self):
        key = b'\0\0\0\x0bssh-ed25519\0\0\0\x20' + b'\0' * 32  # Parser fixture; not a usable SSH credential.
        public = 'ssh-ed25519 ' + base64.b64encode(key).decode()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip('=')
        accepted = 'Accepted publickey for runner from 127.0.0.1 port 42000 ssh2: ED25519 ' + fingerprint + '\n'
        disconnect = 'Received disconnect from 127.0.0.1 port 42000:11: disconnected by user\n'
        final = 'Disconnected from user runner 127.0.0.1 port 42000\n'
        raw = (accepted + disconnect + final).encode()
        close = s.server_close_observation(raw, 'runner', 42000, public)
        self.assertTrue(s.server_close_matches(255, close))
        p = {**proof(), 'serverExitCode': 255, 'serverClose': close}
        self.assertEqual(s.validate_proof(p, p['source'])['exitCode'], 1)  # Failed child stays failed.
        invalid = [raw.replace(b':11:', b':2:'), raw.replace(b'42000', b'42002'),
                   raw.replace(b'runner', b'root'), raw.replace(fingerprint.encode(), b'SHA256:wrong'),
                   raw.replace(b'127.0.0.1', b'192.0.2.1'), raw + disconnect.encode(),
                   raw + b'fatal: native error\n', (accepted + final).encode(),
                   (disconnect + accepted + final).encode(), b'']
        for value in invalid:
            observation = s.server_close_observation(value, 'runner', 42000, public)
            self.assertFalse(s.server_close_matches(255, observation))
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                s.validate_proof({**p, 'serverClose': observation}, p['source'])
        for code in (True, False, None, 0, 1, -15):
            self.assertFalse(s.server_close_matches(code, close))
        with self.assertRaises(RuntimeError):
            s.server_close_observation(b'unknown\n' * 513, 'runner', 42000, public)

    def test_private_server_records_do_not_depend_on_runner_umask_and_cannot_overwrite_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            with patch.object(s.os, 'getuid', return_value=parent.stat().st_uid):
                previous = os.umask(0)
                try:
                    path = parent / 'ssh-server.log'
                    with s.private_output(path) as stream:
                        stream.write(b'synthetic nonsecret log\n')
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(s.read_private(path), b'synthetic nonsecret log\n')
                    with self.assertRaises(FileExistsError):
                        s.private_output(path)
                    link = parent / 'link.log'
                    link.symlink_to(path)
                    with self.assertRaises(OSError):
                        s.private_output(link)
                    self.assertEqual(s.read_private(path), b'synthetic nonsecret log\n')
                finally:
                    os.umask(previous)

    def test_session_reader_is_nonprivileged_and_cannot_allocate_or_join_a_session(self):
        import inspect
        source = inspect.getsource(s.own_audit_session)
        self.assertIn('system.getaudit_addr(', source)
        self.assertIn('os.getuid() == os.geteuid() != 0', source)
        for forbidden in ('setaudit_addr(', 'setuid(', 'subprocess.', 'sudo', 'auditon(', 'SessionCreate('):
            self.assertNotIn(forbidden, source)

    def test_actual_native_session_reader_layout_and_api_failures_are_checked_offline(self):
        from unittest.mock import Mock
        spec = importlib.util.spec_from_file_location('ssh_native_layout_test', ROOT / 'scripts/with-darwin-audit-session.py')
        layout = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(layout)
        native = layout.AuditInfo()
        native.auid, native.asid = 501, 42
        api = Mock()
        def read(pointer, size):
            self.assertEqual(size, 48)
            ctypes.memmove(pointer, ctypes.byref(native), size)
            return 0
        api.getaudit_addr.side_effect = read
        with patch.object(s.ctypes, 'CDLL', return_value=api):
            self.assertEqual(s.own_audit_session(), dict(id=42, auditUser=501,
                                                       observedSha256=hashlib.sha256(bytes(native)).hexdigest()))
            api.getaudit_addr.side_effect = None
            api.getaudit_addr.return_value = -1
            with self.assertRaises(RuntimeError):
                s.own_audit_session()
        with patch.object(s.os, 'geteuid', return_value=0), patch.object(s.ctypes, 'CDLL') as library:
            with self.assertRaises(RuntimeError):
                s.own_audit_session()
            library.assert_not_called()

    def test_diagnostic_workflow_opts_in_explicitly_and_preserves_default_execution(self):
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn("RPC_APPLE_SSH_CONTEXT: 'false'", workflow)
        self.assertIn('--native-session --lane', workflow)
        self.assertIn('elif test "$RPC_APPLE_SSH_CONTEXT" = true; then', workflow)
        self.assertIn('python3 scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" --', workflow)
        self.assertIn('python3 scripts/tests/with-darwin-ssh-context-test.py', workflow)


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
                s.write_json(directory / 'new.json', {})


if __name__ == '__main__':
    unittest.main()
