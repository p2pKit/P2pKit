#!/usr/bin/env python3
"""Scripted context/record controls only; never sudo, native Apple or product evidence."""
import copy
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_audit_context as a

SOURCE = dict(commit='a' * 40, tree='b' * 40)
TEMP = Path(tempfile.gettempdir()).resolve(strict=True)
PARENT = TEMP / 'scripted-audit-context'


def environment():
    return dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
        GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=a.private.REF, GITHUB_EVENT_NAME='push',
        GITHUB_SHA=SOURCE['commit'], GITHUB_WORKSPACE=str(ROOT), RUNNER_TEMP=str(TEMP),
        RPC_QUALIFICATION_PARENT=str(PARENT), RPC_QUALIFY_REQUESTED='true', RPC_ADMISSION_ONLY='false',
        RPC_APPLE_LANE='apple-x64', RPC_INTEL_INVESTIGATION='runtime', RPC_APPLE_BONJOUR_ADVERTISING='true',
        RPC_APPLE_AUDIT_CONTEXT='true', RPC_APPLE_TERMINAL_CONTEXT='false', RPC_APPLE_SSH_CONTEXT='false',
        RPC_APPLE_LAUNCHD_CONTEXT='false', DEVELOPER_DIR='/Applications/Xcode_26.3.app/Contents/Developer')


class ContextControls(unittest.TestCase):
    def setUp(self):
        self.env = environment()
        self.config = dict(uid=501, gid=20, cwd=str(ROOT), environment=copy.deepcopy(self.env),
            argv=[str(Path(sys.executable).absolute()), str(ROOT / 'scripts/run-rpc-qualification.py'),
                  'run', '--lane', 'apple-x64', '--intel-investigation', 'runtime', '--require-bonjour-advertising'])
        self.receipt = {**a.BOOTSTRAP, 'previousSessionAssigned': True}
        self.records = {'session-config.json': self.config, 'session-admission.json': self.receipt}
        for target, name, value in ((a.context, 'native_lane', 'apple-x64'), (a.os, 'getuid', 501),
            (a.os, 'geteuid', 501), (a.os, 'getgid', 20), (a.os, 'getegid', 20),
            (a.private, 'private_parent', None), (a.private, 'source_snapshot', SOURCE)):
            p = patch.object(target, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        for name, operation in (
            ('read_json', lambda path: copy.deepcopy(self.records[path.name])),
            ('read_private', lambda path, uid: json.dumps(self.records[path.name], sort_keys=True).encode())):
            p = patch.object(a.private, name, side_effect=operation)
            p.start()
            self.addCleanup(p.stop)

    def expected(self):
        return a.expected(self.env, PARENT, SOURCE)

    def test_exact_original_bootstrap_and_command_are_required(self):
        proof = self.expected()
        self.assertEqual(proof['source'], SOURCE)
        self.assertEqual(proof['executionMode'], 'runtime')
        self.assertEqual(proof['nativeLane'], 'apple-x64')
        self.assertFalse(proof['privilegedObservationOrProductExecution'])
        self.assertTrue(all(proof[k] for k in a.FLAGS))

    def test_only_explicit_runtime_context_can_be_requested(self):
        self.assertFalse(a.requested({}))
        self.assertFalse(a.requested({'RPC_APPLE_AUDIT_CONTEXT': 'false'}))
        for wrong in ('', True, 1, [], 'TRUE'):
            with self.subTest(flag=wrong), self.assertRaises(RuntimeError):
                a.requested({**self.env, 'RPC_APPLE_AUDIT_CONTEXT': wrong})
        for key, wrong in (('RPC_INTEL_INVESTIGATION', 'native'), ('RPC_INTEL_INVESTIGATION', ''),
            ('RPC_APPLE_LANE', 'apple-arm64'), ('RPC_ADMISSION_ONLY', 'true'),
            ('RPC_APPLE_BONJOUR_ADVERTISING', 'false'), ('RPC_APPLE_TERMINAL_CONTEXT', 'true'),
            ('RPC_APPLE_SSH_CONTEXT', 'true'), ('RPC_APPLE_LAUNCHD_CONTEXT', 'true')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                a.requested({**self.env, key: wrong})

    def test_root_and_wrong_native_host_cannot_admit_records(self):
        for key in ('getuid', 'geteuid', 'getgid', 'getegid'):
            with patch.object(a.os, key, return_value=0), self.assertRaises(RuntimeError):
                self.expected()
        with patch.object(a.context, 'native_lane', side_effect=RuntimeError('wrong role')), self.assertRaises(RuntimeError):
            self.expected()

    def test_wrong_source_or_workflow_and_context_drift_fail_closed(self):
        for key, wrong in (('GITHUB_SHA', 'c' * 40), ('GITHUB_REF', 'refs/heads/main'),
            ('GITHUB_REPOSITORY', 'other/repo'), ('GITHUB_EVENT_NAME', 'pull_request'),
            ('GITHUB_WORKSPACE', str(TEMP)), ('RPC_QUALIFICATION_PARENT', str(TEMP)),
            ('RUNNER_ENVIRONMENT', 'self-hosted'), ('RPC_QUALIFY_REQUESTED', 'false'),
            ('DEVELOPER_DIR', '/Applications/Xcode_26.5.app/Contents/Developer')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                a.expected({**self.env, key: wrong}, PARENT, SOURCE)
        with patch.object(a.private, 'source_snapshot', return_value={**SOURCE, 'tree': 'c' * 40}), self.assertRaises(RuntimeError):
            self.expected()
        self.config['environment']['GITHUB_SHA'] = 'd' * 40
        with self.assertRaises(RuntimeError):
            self.expected()

    def test_bootstrap_flags_cannot_be_missing_changed_or_guessed(self):
        original = copy.deepcopy(self.receipt)
        for key in a.BOOTSTRAP:
            self.receipt.clear()
            self.receipt.update(original)
            self.receipt[key] = False if original[key] is True else True
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.expected()
        self.receipt.clear()
        self.receipt.update(original)
        self.receipt['privateExtra'] = 'must not be exported'
        with self.assertRaises(RuntimeError):
            self.expected()
        del self.records['session-admission.json']
        with self.assertRaises(KeyError):
            self.expected()

    def test_arbitrary_or_other_inventory_commands_and_credentials_are_rejected(self):
        argv = list(self.config['argv'])
        for wrong in (argv[:-1], ['/bin/sh'], argv[:-2] + ['native', '--require-bonjour-advertising'],
                      argv + ['--admission-only'], ['python3', *argv[1:]]):
            self.config['argv'] = wrong
            with self.subTest(argv=wrong), self.assertRaises(RuntimeError):
                self.expected()
        self.config['argv'] = argv
        self.config['uid'] = 0
        with self.assertRaises(RuntimeError):
            self.expected()

    def native(self, asid=73, code=0):
        def read(pointer, size):
            self.assertEqual(size, 48)
            value = a.session.AuditInfo()
            value.asid = asid
            ctypes.memmove(pointer, ctypes.byref(value), size)
            return code
        return type('ReadOnlyNative', (), {'getaudit_addr': Mock(side_effect=read)})()

    def test_child_must_observe_its_original_assigned_native_session(self):
        with patch.object(a.ctypes, 'CDLL', return_value=self.native()), patch.object(a.private, 'write_json') as save:
            proof = a.admit({**self.env, 'SECURITYSESSIONID': format(73, 'x')}, PARENT, SOURCE)
            save.assert_called_once_with(PARENT / 'audit-context.json', proof)

    def test_missing_mismatched_or_unreadable_native_session_never_writes_admission(self):
        for asid, code, presented in ((73, 0, None), (73, 0, '4a'), (0, 0, '0'), (-1, 0, '-1'), (73, -1, '49')):
            with self.subTest(asid=asid, code=code, presented=presented), \
                    patch.object(a.ctypes, 'CDLL', return_value=self.native(asid, code)), \
                    patch.object(a.private, 'write_json') as save, self.assertRaises(RuntimeError):
                a.admit({**self.env, 'SECURITYSESSIONID': presented}, PARENT, SOURCE)
            save.assert_not_called()

    def test_collector_rereads_both_exact_records_instead_of_trusting_child_boolean(self):
        self.records['audit-context.json'] = self.expected()
        self.assertEqual(a.recheck(self.env, PARENT, SOURCE), self.records['audit-context.json'])
        self.receipt['previousSessionAssigned'] = False  # Allowed bootstrap observation, different original bytes.
        with self.assertRaises(RuntimeError):
            a.recheck(self.env, PARENT, SOURCE)

    def test_public_record_is_closed_and_no_field_alone_admits_ownership(self):
        proof = self.expected()
        for key, wrong in (('nativeSessionObserved', False), ('schema', True), ('executionMode', 'qualification'),
            ('nativeLane', 'apple-arm64'), ('configSha256', 'no'), ('source', {'commit': 'a' * 40})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                a.validate({**proof, key: wrong}, SOURCE)
        with self.assertRaises(RuntimeError):
            a.validate({**proof, 'pid': 73}, SOURCE)
        for forbidden in ('pid', 'uid', 'path', 'argv', 'sessionId', 'environment', 'executionAdmitted'):
            self.assertNotIn(forbidden, proof)


if __name__ == '__main__':
    unittest.main(verbosity=2)
