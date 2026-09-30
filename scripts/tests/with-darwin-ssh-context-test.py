#!/usr/bin/env python3
"""Offline controls only: never starts SSH, alters security or executes an Apple product."""
import copy
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
                environment=environment(), ports=[42000, 42001], argv=[python,
                str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', '/fixture', '--', python,
                str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64',
                '--intel-investigation', 'network'])


def proof():
    return dict(schema=1, scope=s.SCOPE, source=config()['source'], exitCode=1, serverExitCode=0,
                stage='FINALIZED', diagnostics={}, finalizationErrors=[], **dict.fromkeys(s.PROOF_FLAGS, True))


class SshContextTests(unittest.TestCase):
    def setUp(self):
        for name, value in (('getuid', 501), ('geteuid', 501), ('getgid', 20), ('getegid', 20), ('getgroups', [20, 80])):
            p = patch.object(s.os, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(s.platform, 'system', return_value='Darwin')
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
                           ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}), ('unexpected', 'private')):
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
        for key, value in (('exitCode', 255), ('serverExitCode', None), ('serverExitCode', 1), ('stage', 'CHILD'),
                           ('finalizationErrors', ['SOCKET_CLOSE'])):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.validate_proof({**p, key: value}, p['source'])

    def test_proof_rejects_unknown_output_and_type_confusion(self):
        p = proof()
        for key, value in (('exitCode', True), ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}),
                           ('scope', 'PHYSICAL_LAN'), ('schema', True), ('stage', 'PRIVATE_HOSTNAME'),
                           ('authenticatedInvokingUser', 1), ('private-key', 'must-not-export'),
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

    def test_diagnostic_workflow_opts_in_explicitly_and_preserves_default_execution(self):
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn("RPC_APPLE_SSH_CONTEXT: ${{ matrix.investigation == 'network' }}", workflow)
        self.assertIn('if test "$RPC_APPLE_SSH_CONTEXT" = true; then', workflow)
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
