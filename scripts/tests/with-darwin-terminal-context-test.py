#!/usr/bin/env python3
"""Offline controls only. No Terminal, GUI, compiler, privacy prompt or native product execution."""
import copy
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
TEMP = Path(tempfile.gettempdir()).resolve(strict=True)
PARENT = TEMP / 'p2pkit-terminal-fixture'
spec = importlib.util.spec_from_file_location('terminal_context_test', ROOT / 'scripts/with-darwin-terminal-context.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def config():
    python = str(Path(sys.executable).resolve())
    return dict(uid=501, gid=20, groups=[20, 80], source={'commit': 'a' * 40, 'tree': 'b' * 40},
        environment=dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
            GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=t.private.REF, GITHUB_EVENT_NAME='push', GITHUB_SHA='a' * 40,
            GITHUB_WORKSPACE=str(ROOT), RUNNER_TEMP=str(TEMP), RPC_QUALIFICATION_PARENT=str(PARENT),
            RPC_QUALIFY_REQUESTED='true', RPC_APPLE_TERMINAL_CONTEXT='true'), argv=[python,
            str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', str(PARENT), '--', python,
            str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64', '--intel-investigation', 'network'])


def proof():
    return dict(schema=1, scope=t.SCOPE, source=config()['source'], exitCode=1, stage='FINALIZED', logs={},
                failureCheck='NONE', openErrorDomain='NONE', openErrorCode=0,
                compilerDiagnostics=dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest(), diagnostics=[]),
                **dict.fromkeys(t.FLAGS, True))


class TerminalContext(unittest.TestCase):
    def setUp(self):
        account = type('Account', (), dict(pw_name='runner', pw_gid=20))()
        for obj, name, value in ((t.platform, 'system', 'Darwin'), (t.platform, 'machine', 'x86_64'),
                                 (t.os, 'getuid', 501), (t.os, 'geteuid', 501), (t.os, 'getgid', 20),
                                 (t.os, 'getegid', 20), (t.os, 'getgrouplist', [20, 80]),
                                 (t.pwd, 'getpwuid', account), (t.private, 'private_parent', None)):
            p = patch.object(obj, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_only_exact_nonroot_intel_feature_context_is_admitted(self):
        c = config()
        t.config_validate(c, PARENT / 'terminal-context')
        for key, value in (('GITHUB_REF', 'refs/heads/main'), ('RPC_APPLE_TERMINAL_CONTEXT', 'false'),
                           ('GITHUB_EVENT_NAME', 'workflow_dispatch'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                           ('GITHUB_REPOSITORY', 'other/repo'), ('GITHUB_SHA', 'HEAD'), ('GITHUB_WORKSPACE', '/')):
            changed = copy.deepcopy(c)
            changed['environment'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.config_validate(changed, PARENT / 'terminal-context')
        for obj, name, value in ((t.os, 'getuid', 0), (t.os, 'geteuid', 0), (t.os, 'getgid', 0),
                                 (t.os, 'getegid', 0), (t.platform, 'system', 'Linux'),
                                 (t.platform, 'machine', 'arm64')):
            with patch.object(obj, name, return_value=value), self.assertRaises(RuntimeError):
                t.config_validate(c, PARENT / 'terminal-context')

    def test_only_the_unchanged_audit_and_network_command_crosses_the_boundary(self):
        c = config()
        for command in ([], ['/bin/sh'], c['argv'][:-2], c['argv'][:-1] + ['native'],
                        c['argv'][:-3] + ['apple-arm64', '--intel-investigation', 'network'],
                        c['argv'] + ['--unsafe']):
            with self.subTest(command=command), self.assertRaises(RuntimeError):
                t.config_validate({**c, 'argv': command}, PARENT / 'terminal-context')
        for key, value in (('uid', 0), ('uid', True), ('gid', 0), ('groups', [20]), ('groups', [20, 80, 80]),
                           ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}), ('unknown', 'private')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.config_validate({**c, key: value}, PARENT / 'terminal-context')

    def test_no_secrets_loader_hooks_session_admission_or_other_context_is_forwarded(self):
        for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'BASH_ENV', 'PYTHONPATH', 'DYLD_INSERT_LIBRARIES',
                    'P2PKIT_AUDIT_OWNERSHIP_CHAIN', 'P2PKIT_AUDIT_STATE_DIR', 'SECURITYSESSIONID',
                    'RPC_APPLE_LAUNCHD_CONTEXT', 'RPC_APPLE_SSH_CONTEXT', 'SUDO_UID'):
            c = config()
            c['environment'][key] = 'private'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.config_validate(c, PARENT / 'terminal-context')

    def test_command_runs_only_fixed_child_then_waited_exit_record_without_prompt_or_payload(self):
        raw = t.command_bytes(PARENT / 'terminal-context').decode()
        self.assertTrue(raw.startswith('#!/bin/bash\numask 077\n'))
        self.assertIn(' -I -S ', raw)
        self.assertIn('--child ', raw)
        self.assertIn(' </dev/null ', raw)
        self.assertIn('status=$?\nprintf', raw)
        self.assertIn('shell-result.txt\nexit "$status"\n', raw)
        for forbidden in ('osascript', 'sudo', 'eval ', 'tccutil', 'defaults ', 'set -e', 'gradlew'):
            self.assertNotIn(forbidden, raw)

    def test_native_ancestry_checks_kernel_parent_identity_not_only_a_pid_or_process_name(self):
        terminal = dict(pid=10, uid=501, startSeconds=100, startMicroseconds=50)
        rows = {10: dict(terminal, realUid=501, parentPid=1, uniqueId=1000, parentUniqueId=1, live=True),
                20: dict(pid=20, uid=501, realUid=501, parentPid=10, uniqueId=2000, parentUniqueId=1000,
                         startSeconds=101, startMicroseconds=60, live=True)}
        t.ancestor_matches(rows.__getitem__, 20, terminal, 501)
        for label, bad in (('parentUniqueId', 999), ('uid', 0), ('realUid', 0), ('parentPid', 20), ('live', False)):
            changed = copy.deepcopy(rows)
            changed[20][label] = bad
            with self.subTest(label=label), self.assertRaises(RuntimeError):
                t.ancestor_matches(changed.__getitem__, 20, terminal, 501)
        for label, bad in (('startSeconds', 99), ('startMicroseconds', 51), ('uid', 502), ('pid', True), ('extra', 1)):
            with self.subTest(label=label), self.assertRaises(RuntimeError):
                t.ancestor_matches(rows.__getitem__, 20, {**terminal, label: bad}, 501)

    def test_application_lease_requires_console_fresh_instance_reaped_child_and_original_identity_before_quit(self):
        source = (ROOT / 'scripts/diagnostics/apple-terminal-context.m').read_text()
        for required in ('console.st_uid != uid', 'runningApplicationsWithBundleIdentifier:bundle].count != 0',
                         'configuration.createsNewApplicationInstance = YES', 'configuration.promptsUserIfNeeded = NO',
                         'configuration.addsToRecentItems = NO', 'configuration.activates = NO',
                         'before.pbi_start_tvsec != after.pbi_start_tvsec', 'before.pbi_start_tvusec != after.pbi_start_tvusec',
                         'application.terminated', '[application terminate]', '@"scriptChildReaped"] = @YES',
                         'NSProcessInfo.processInfo.systemUptime', 'NSDataWritingWithoutOverwriting'):
            self.assertIn(required, source)
        self.assertLess(source.index('@"scriptChildReaped"] = @YES'), source.index('[application terminate]'))
        self.assertLess(source.index('before.pbi_start_tvusec != after.pbi_start_tvusec'), source.index('[application terminate]'))
        for forbidden in ('forceTerminate', 'kill(', 'killpg(', 'system(', 'sudo', 'osascript', 'tccutil',
                          'csrutil', 'launchctl', 'defaults write', 'setuid(', 'setgid('):
            self.assertNotIn(forbidden, source)

    def test_failed_or_unfinalized_application_never_inherits_native_success(self):
        value = proof()
        self.assertEqual(t.validate_proof(value, value['source'])['exitCode'], 1)
        for field in t.FLAGS:
            invalid = {**value, field: False}
            self.assertEqual(t.validate_proof(invalid, value['source'], complete=False), invalid)
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                t.validate_proof(invalid, value['source'])
        for key, bad in (('exitCode', True), ('schema', True), ('stage', 'PRIVATE'), ('nonrootChild', 1),
                         ('scope', 'PRODUCT_PASS'), ('raw', 'private'), ('logs', {'private': {}}),
                         ('failureCheck', 'private'), ('openErrorCode', True), ('openErrorDomain', 'private')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.validate_proof({**value, key: bad}, value['source'], complete=False)
        for key, bad in (('compilerDiagnostics', None), ('failureCheck', 'QUIT_COMPLETION'),
                         ('openErrorDomain', 'OSSTATUS'), ('openErrorCode', -600)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.validate_proof({**value, key: bad}, value['source'])

    def test_context_log_exposes_only_closed_checks_not_private_details(self):
        raw = b'private identity and path\nCONTEXT_FAILURE NATIVE_ANCESTRY\nCONTEXT_FAILURE PRIVATE_NAME\n'
        row = t.log_metadata(raw)
        self.assertEqual(row, dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                   failedChecks=['NATIVE_ANCESTRY']))
        value = {**proof(), 'logs': {'child.stderr': row}}
        t.validate_proof(value, value['source'], complete=False)
        with self.assertRaises(RuntimeError):
            t.validate_proof(value, value['source'])
        for bad in (['PRIVATE_NAME'], ['NATIVE_ANCESTRY', 'NATIVE_ANCESTRY'], [1], 'NATIVE_ANCESTRY'):
            changed = {**value, 'logs': {'child.stderr': {**row, 'failedChecks': bad}}}
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                t.validate_proof(changed, value['source'], complete=False)
        self.assertEqual(t.check_category('Wrong native ancestor identity'), 'NATIVE_ANCESTRY')
        self.assertEqual(t.check_category('Replaced native parent refused'), 'NATIVE_ANCESTRY')
        self.assertEqual(t.check_category('Exact application identity required'), 'APPLICATION_RECEIPT')

    def test_public_collector_requires_exact_context_and_never_promotes_other_architectures(self):
        spec = importlib.util.spec_from_file_location('terminal_public_test', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        p = {**proof(), 'exitCode': 0}
        r = dict(source=p['source'], lane='apple-x64', result='PASS', intelInvestigation='network',
                 terminalContextRequired=True, appleTerminalContext=p)
        self.assertEqual(q.public_summary(r)['appleTerminalContext'], p)
        for field in t.FLAGS:
            bad = {**p, field: False}
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                q.public_summary({**r, 'appleTerminalContext': bad})
            self.assertFalse(q.public_summary({**r, 'result': 'FAIL', 'appleTerminalContext': bad})['appleTerminalContext'][field])
        for change in (dict(appleTerminalContext=None), dict(appleTerminalContext={**p, 'exitCode': 1}),
                       dict(sshContextRequired=True), dict(launchdContextRequired=True),
                       dict(intelInvestigation=None), dict(lane='apple-arm64')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                q.public_summary({**r, **change})

    def test_only_the_explicit_network_lane_changes_context_not_production_defaults(self):
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn("RPC_APPLE_TERMINAL_CONTEXT: ${{ matrix.investigation == 'network' }}", source)
        self.assertIn("RPC_APPLE_LAUNCHD_CONTEXT: 'false'", source)
        self.assertIn('python3 scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" --', source)
        self.assertIn('python3 scripts/tests/with-darwin-terminal-context-test.py', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
