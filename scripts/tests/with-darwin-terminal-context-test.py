#!/usr/bin/env python3
"""Offline controls only. No Terminal, GUI, compiler, privacy prompt or native product execution."""
import copy
import ctypes
import errno
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
spec = importlib.util.spec_from_file_location('terminal_native_layout_test', ROOT / 'scripts/audit_processes.py')
native = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)


def config():
    python = str(Path(sys.executable).resolve())
    return dict(uid=501, gid=20, groups=[20, 80], source={'commit': 'a' * 40, 'tree': 'b' * 40},
        environment=dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
            GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=t.private.REF, GITHUB_EVENT_NAME='push', GITHUB_SHA='a' * 40,
            GITHUB_WORKSPACE=str(ROOT), RUNNER_TEMP=str(TEMP), RPC_QUALIFICATION_PARENT=str(PARENT),
            RPC_QUALIFY_REQUESTED='true', RPC_APPLE_TERMINAL_CONTEXT='true',
            RPC_ADMISSION_ONLY='false', RPC_INTEL_INVESTIGATION='network', RPC_APPLE_LANE='apple-x64'), argv=[python,
            str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', str(PARENT), '--', python,
            str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64', '--intel-investigation', 'network'])


def proof():
    return dict(schema=4, scope=t.SCOPE, source=config()['source'], nativeLane='apple-x64', executionMode='network', exitCode=1, stage='FINALIZED', logs={},
                failureCheck='NONE', openErrorDomain='NONE', openErrorCode=0,
                ancestry=dict(method=t.ANCESTRY_METHOD, depth=2, systemLoginAncestors=0, restrictedCombinedDenials=0),
                compilerDiagnostics=dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest(), diagnostics=[]),
                **dict.fromkeys(t.FLAGS, True))


class ReadOnlyApi:
    """Layout/decision fixture only; never an actual Darwin execution result."""
    def __init__(self, uid=0, image=b'/usr/bin/login', changed=None, fail_flavor=None):
        self.uid, self.image, self.changed, self.fail_flavor = uid, image, changed, fail_flavor
        self.calls, self.unique_reads, self.short_reads = [], 0, 0

    def proc_pidinfo(self, pid, flavor, argument, pointer, size):
        self.calls.append(flavor)
        if flavor == self.fail_flavor or (flavor == 18 and self.uid == 0):
            ctypes.set_errno(errno.EPERM)
            return 0
        keys = dict(pid=pid, ppid=10, pgid=10, status=3, uid=self.uid, ruid=501,
                    gid=20, rgid=20, svuid=self.uid, svgid=20)
        unique = native.DarwinUniqueInfo()
        unique.uniqueid, unique.parentuniqueid, unique.pidversion = 2000, 1000, 1
        if flavor == 17:
            self.unique_reads += 1
            value = unique
            if self.unique_reads == 2 and self.changed in ('uniqueid', 'parentuniqueid', 'pidversion'):
                setattr(value, self.changed, getattr(value, self.changed) + 1)
        elif flavor == 13:
            self.short_reads += 1
            value = t.DarwinShortInfo()
            for key, item in keys.items():
                setattr(value, key, item)
            if self.short_reads == 2 and self.changed in ('uid', 'ruid', 'ppid', 'pid', 'status'):
                setattr(value, self.changed, 5 if self.changed == 'status' else getattr(value, self.changed) + 1)
        elif flavor == 18:
            value = native.DarwinIdentity()
            value.unique = unique
            for key, item in keys.items():
                setattr(value.bsd, key, item)
            value.bsd.startsec, value.bsd.startusec = 100, 50
            if self.changed == 'combined':
                value.unique.uniqueid += 1
        else:
            raise AssertionError('Unapproved fixture operation')
        assert argument == 1 and size == ctypes.sizeof(value)
        ctypes.memmove(pointer, ctypes.byref(value), size)
        return size

    def proc_pidpath(self, pid, pointer, size):
        assert len(self.image) + 1 <= size
        ctypes.memmove(pointer, self.image + b'\0', len(self.image) + 1)
        return len(self.image)


class TerminalContext(unittest.TestCase):
    def setUp(self):
        account = type('Account', (), dict(pw_name='runner', pw_gid=20))()
        for obj, name, value in ((t.platform, 'system', 'Darwin'), (t.platform, 'machine', 'x86_64'),
                                 (t.apple_context, 'host_role', 'macos-x64'),
                                 (t.os, 'getuid', 501), (t.os, 'geteuid', 501), (t.os, 'getgid', 20),
                                 (t.os, 'getegid', 20), (t.os, 'getgrouplist', [20, 80]),
                                 (t.pwd, 'getpwuid', account), (t.private, 'private_parent', None)):
            p = patch.object(obj, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_exact_native_arm_full_inventory_cannot_select_intel_diagnostics_or_x86_proofs(self):
        c = config()
        c['environment'].update(RPC_APPLE_LANE='apple-arm64', RPC_INTEL_INVESTIGATION='',
                                RPC_APPLE_BONJOUR_ADVERTISING='true')
        c['argv'] = t.qualification_argv(PARENT, c['environment'])
        self.assertEqual(c['argv'][-3:], ['--lane', 'apple-arm64', '--require-bonjour-advertising'])
        with patch.object(t.platform, 'machine', return_value='arm64'), \
                patch.object(t.apple_context, 'host_role', return_value='macos-arm64'):
            t.config_validate(c, PARENT / 'terminal-context')
            for mode in ('native', 'network', 'runtime', 'cold-boot'):
                with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                    t.qualification_argv(PARENT, {**c['environment'], 'RPC_INTEL_INVESTIGATION': mode})
            changed = copy.deepcopy(c)
            changed['argv'][9] = 'apple-x64'
            with self.assertRaises(RuntimeError):
                t.config_validate(changed, PARENT / 'terminal-context')
        with self.assertRaises(RuntimeError):
            t.config_validate(c, PARENT / 'terminal-context')  # x86 must not supply this lane.
        p = {**proof(), 'nativeLane': 'apple-arm64', 'executionMode': 'qualification'}
        t.validate_proof(p, p['source'], expected_lane='apple-arm64')
        for lane in ('apple-x64', 'android-art'):
            with self.assertRaises(RuntimeError):
                t.validate_proof(p, p['source'], expected_lane=lane)
        for mode in ('network', 'native', 'runtime'):
            with self.assertRaises(RuntimeError):
                t.validate_proof({**p, 'executionMode': mode}, p['source'], expected_lane='apple-arm64')

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

    def test_requested_advertising_survives_both_actual_environment_allowlists(self):
        spec = importlib.util.spec_from_file_location('terminal_audit_forwarding_test',
                                                     ROOT / 'scripts/with-darwin-audit-session.py')
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        incoming = {**config()['environment'], 'RPC_APPLE_BONJOUR_ADVERTISING': 'true',
                    'GH_TOKEN': 'not-a-secret-fixture', 'DYLD_INSERT_LIBRARIES': '/untrusted',
                    'P2PKIT_AUDIT_OWNERSHIP_CHAIN': 'untrusted'}
        terminal_env = {k: v for k, v in incoming.items() if k in t.ENVIRONMENT}
        audit_env = {k: v for k, v in terminal_env.items() if k in audit.ENVIRONMENT}
        self.assertEqual(audit_env.get('RPC_APPLE_BONJOUR_ADVERTISING'), 'true')
        self.assertEqual(audit_env, terminal_env)
        for key in ('GH_TOKEN', 'DYLD_INSERT_LIBRARIES', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN'):
            self.assertNotIn(key, audit_env)

    def test_advertising_request_is_bound_to_exact_command_and_cannot_disappear(self):
        c = config()
        self.assertEqual(t.qualification_argv(PARENT, c['environment']), c['argv'])
        c['environment']['RPC_APPLE_BONJOUR_ADVERTISING'] = 'true'
        c['argv'] = t.qualification_argv(PARENT, c['environment'])
        self.assertEqual(c['argv'], config()['argv'] + ['--require-bonjour-advertising'])
        t.config_validate(c, PARENT / 'terminal-context')
        with self.assertRaises(RuntimeError):
            t.config_validate({**c, 'argv': c['argv'][:-1]}, PARENT / 'terminal-context')
        for value in (None, 'false', '', 'TRUE', '1', True):
            changed = copy.deepcopy(c)
            changed['environment']['RPC_APPLE_BONJOUR_ADVERTISING'] = value
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                t.config_validate(changed, PARENT / 'terminal-context')

    def test_original_native_and_full_inventories_require_exact_mode_and_preparation(self):
        for mode in ('native', 'runtime', ''):
            c = config()
            c['environment'].update(RPC_INTEL_INVESTIGATION=mode, RPC_APPLE_BONJOUR_ADVERTISING='true')
            c['argv'] = t.qualification_argv(PARENT, c['environment'])
            original = config()['argv'][:-2]
            self.assertEqual(c['argv'], original + (['--intel-investigation', mode] if mode else []) +
                             ['--require-bonjour-advertising'])
            t.config_validate(c, PARENT / 'terminal-context')
            for key, value in (('RPC_INTEL_INVESTIGATION', 'network'), ('RPC_INTEL_INVESTIGATION', None),
                               ('RPC_INTEL_INVESTIGATION', 'cold-boot'), ('RPC_INTEL_INVESTIGATION', 'other'),
                               ('RPC_ADMISSION_ONLY', 'true'), ('RPC_ADMISSION_ONLY', None),
                               ('RPC_APPLE_BONJOUR_ADVERTISING', 'false'), ('RPC_APPLE_BONJOUR_ADVERTISING', None)):
                changed = copy.deepcopy(c)
                changed['environment'][key] = value
                with self.subTest(mode=mode, key=key, value=value), self.assertRaises(RuntimeError):
                    t.config_validate(changed, PARENT / 'terminal-context')
            # Even matching argv cannot turn an arbitrary mode into admitted work.
            for value in ('cold-boot', 'arbitrary', None):
                with self.assertRaises(RuntimeError):
                    t.qualification_argv(PARENT, {**c['environment'], 'RPC_INTEL_INVESTIGATION': value})

    def test_new_inventory_reaches_unchanged_audit_allowlist_without_mode_or_flag_loss(self):
        spec = importlib.util.spec_from_file_location('terminal_mode_audit_forwarding',
                                                     ROOT / 'scripts/with-darwin-audit-session.py')
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        for mode in ('network', 'native', 'runtime', ''):
            incoming = {**config()['environment'], 'RPC_INTEL_INVESTIGATION': mode,
                        'RPC_APPLE_BONJOUR_ADVERTISING': 'true', 'GITHUB_TOKEN': 'synthetic'}
            terminal_env = {k: v for k, v in incoming.items() if k in t.ENVIRONMENT}
            audit_env = {k: v for k, v in terminal_env.items() if k in audit.ENVIRONMENT}
            self.assertEqual(audit_env, terminal_env)
            self.assertEqual(t.execution_mode(audit_env), mode or 'qualification')
            self.assertNotIn('GITHUB_TOKEN', audit_env)

    def test_cli_mode_mismatch_fails_before_opening_an_application(self):
        for mode in ('network', 'native', 'runtime', ''):
            base = ['with-darwin-terminal-context.py', '--parent', str(PARENT), '--lane', 'apple-x64']
            argv = base + (['--intel-investigation', mode] if mode else [])
            env = {**config()['environment'], 'RPC_INTEL_INVESTIGATION': mode, 'RPC_APPLE_BONJOUR_ADVERTISING': 'true'}
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, env, clear=True), patch.object(t, 'run') as run:
                run.return_value = 1  # Fixture only, not an application result.
                self.assertEqual(t.main(), 1)
                run.assert_called_once_with(PARENT)
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, {**env, 'RPC_INTEL_INVESTIGATION': 'different'}, clear=True), \
                    patch.object(t, 'run') as run, self.assertRaises(RuntimeError):
                t.main()
            run.assert_not_called()

    def test_context_envelope_is_closed_while_original_diagnostic_and_cleanup_bounds_remain(self):
        source = (ROOT / 'scripts/diagnostics/apple-terminal-context.m').read_text()
        self.assertIn('argc != 3', source)
        self.assertIn('@{@"network":@1800, @"native":@19200, @"runtime":@19200, @"qualification":@19200}[executionMode]', source)
        self.assertIn('if (!childBound) return 125', source)
        self.assertIn('waitUntil(childBound.doubleValue', source)
        self.assertIn('waitUntil(30, ^BOOL{ return opened; })', source)
        self.assertEqual(source.count('NSProcessInfo.processInfo.systemUptime + 30'), 1)
        self.assertIn('waitUntil(quitDeadline - NSProcessInfo.processInfo.systemUptime, ^BOOL{ return application.terminated; })', source)
        self.assertIn('NSProcessInfo.processInfo.systemUptime > quitDeadline', source)
        self.assertNotIn('atof(', source)
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn('timeout-minutes: 325', workflow)

    def test_public_inventory_cannot_exchange_network_native_full_or_arm_proofs(self):
        spec = importlib.util.spec_from_file_location('terminal_inventory_public', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        for mode in ('network', 'native', None):
            p = {**proof(), 'executionMode': mode or 'qualification', 'exitCode': 0}
            r = dict(source=p['source'], lane='apple-x64', result='PASS', intelInvestigation=mode,
                     terminalContextRequired=True, appleTerminalContext=p)
            if mode != 'network':
                with self.assertRaises(RuntimeError):
                    q.public_summary(r)  # Preparation is mandatory for original product inventories.
                b = q.bonjour_environment
                before, active = b.summarize({b.KEY: True}), b.summarize({b.KEY: False})
                preparation = dict(schema=3, scope=b.SCOPE, source=p['source'], nativeLane='apple-x64',
                    operation='EXPLICIT_TRUE_REPAIR', absence=None, stage='FINALIZED', failure='NONE',
                    restoreFailure='NONE', serviceConfigurationSha256='d' * 64,
                    observations=dict(before=before, active=active, restored=before),
                    commands={key: dict(exitCode=0, timedOut=False, failure='NONE', bytes=0,
                                        sha256=b.digest(b'')) for key in b.REPAIR_COMMANDS}, **dict.fromkeys(b.FLAGS, True))
                r.update(bonjourAdvertisingRequired=True, appleBonjourAdvertising=preparation,
                         phases={'bonjour-advertising': {'status': 'PASS'}})
                for key in b.FLAGS:
                    with self.subTest(mode=mode, key=key), self.assertRaises(RuntimeError):
                        q.public_summary({**r, 'appleBonjourAdvertising': {**preparation, key: False}})
                for change in (dict(phases={}), dict(bonjourAdvertisingRequired=False), dict(appleBonjourAdvertising=None)):
                    with self.assertRaises(RuntimeError):
                        q.public_summary({**r, **change})
            self.assertEqual(q.public_summary(r)['appleTerminalContext']['executionMode'], mode or 'qualification')
            for other in ('network', 'native', None):
                if other != mode:
                    with self.subTest(mode=mode, other=other), self.assertRaises(RuntimeError):
                        q.public_summary({**r, 'intelInvestigation': other})
            for change in (dict(lane='apple-arm64'), dict(lane='android-art'), dict(admissionOnly=True)):
                with self.assertRaises(RuntimeError):
                    q.public_summary({**r, **change})

    def test_arm_absence_evidence_does_not_replace_native_terminal_or_intel_restoration(self):
        spec = importlib.util.spec_from_file_location('terminal_arm_absence_public', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        b = q.bonjour_environment
        terminal = {**proof(), 'executionMode': 'qualification', 'nativeLane': 'apple-arm64', 'exitCode': 0}
        preparation = dict(schema=3, scope=b.SCOPE, source=terminal['source'], nativeLane='apple-arm64',
            operation='ARM_ABSENT_DOMAIN_NO_CHANGE', absence=dict(before='e' * 64, after='e' * 64),
            stage='FINALIZED', failure='NONE', restoreFailure='NONE', serviceConfigurationSha256='d' * 64,
            observations={}, commands={key: dict(exitCode=0, timedOut=False, failure='NONE', bytes=0,
                sha256=b.digest(b'')) for key in ('inspect', 'inspect-unchanged')}, **dict.fromkeys(b.FLAGS, False))
        preparation.update(sourceUnchanged=True, serviceRegistered=True)
        value = dict(source=terminal['source'], lane='apple-arm64', result='PASS', terminalContextRequired=True,
            appleTerminalContext=terminal, bonjourAdvertisingRequired=True, appleBonjourAdvertising=preparation,
            phases={'bonjour-advertising': {'status': 'PASS'}})
        # Privacy-schema fixture only. Full-phase/native coverage is independently
        # required by collect(); this constructed object is NOT runtime evidence.
        self.assertEqual(q.public_summary(value)['appleBonjourAdvertising']['operation'], 'ARM_ABSENT_DOMAIN_NO_CHANGE')
        for change in (dict(lane='apple-x64'), dict(terminalContextRequired=False), dict(appleTerminalContext=None),
                       dict(bonjourAdvertisingRequired=False), dict(appleBonjourAdvertising=None)):
            with self.assertRaises(RuntimeError):
                q.public_summary({**value, **change})

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

    def test_limited_native_reader_brackets_root_login_and_retains_original_permission_denial(self):
        api = ReadOnlyApi()
        row = t.observe_ancestor(api, native, 20)
        self.assertTrue(row['systemLogin'])
        self.assertTrue(row['restrictedCombinedDenied'])
        self.assertEqual((row['uid'], row['realUid'], row['uniqueId'], row['parentUniqueId']), (0, 501, 2000, 1000))
        self.assertIsNone(row['startSeconds'])  # No fabricated full/owned identity for this intermediary.
        self.assertEqual(api.calls, [17, 13, 18, 13, 17])
        owned = t.observe_ancestor(ReadOnlyApi(uid=501, image=b'/usr/bin/python3'), native, 30)
        self.assertEqual((owned['startSeconds'], owned['startMicroseconds']), (100, 50))
        self.assertFalse(owned['restrictedCombinedDenied'])
        self.assertFalse(owned['systemLogin'])
        self.assertEqual((ctypes.sizeof(t.DarwinShortInfo), ctypes.sizeof(native.DarwinUniqueInfo)), (64, 56))

    def test_limited_reader_rejects_replacement_exec_reparent_credential_and_native_api_failures(self):
        for changed in ('uniqueid', 'parentuniqueid', 'pidversion', 'uid', 'ruid', 'ppid', 'pid', 'status'):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                t.observe_ancestor(ReadOnlyApi(changed=changed), native, 20)
        for flavor in (13, 17, 18):
            with self.subTest(flavor=flavor), self.assertRaises(RuntimeError):
                t.observe_ancestor(ReadOnlyApi(uid=501, fail_flavor=flavor), native, 20)
        with self.assertRaises(RuntimeError):
            t.observe_ancestor(ReadOnlyApi(uid=501, changed='combined'), native, 20)

    def test_only_exact_os_login_intermediary_may_link_nonroot_child_to_owned_terminal(self):
        terminal = dict(pid=10, uid=501, startSeconds=100, startMicroseconds=50)
        rows = {
            10: dict(terminal, realUid=501, parentPid=1, uniqueId=1000, parentUniqueId=1, live=True),
            20: t.observe_ancestor(ReadOnlyApi(), native, 20),
            30: dict(pid=30, uid=501, realUid=501, parentPid=20, uniqueId=3000, parentUniqueId=2000,
                     startSeconds=101, startMicroseconds=60, live=True),
        }
        self.assertEqual(t.ancestor_matches(rows.__getitem__, 30, terminal, 501),
                         dict(method=t.ANCESTRY_METHOD, depth=3, systemLoginAncestors=1, restrictedCombinedDenials=1))
        for key, bad in (('systemLogin', False), ('realUid', 502), ('uid', 502), ('parentPid', 5),
                         ('parentUniqueId', 999), ('live', False)):
            changed = copy.deepcopy(rows)
            changed[20][key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.ancestor_matches(changed.__getitem__, 30, terminal, 501)
        for image in (b'/tmp/login', b'/usr/bin/login-other', b'login', b''):
            changed = {**rows, 20: t.observe_ancestor(ReadOnlyApi(image=image), native, 20)}
            with self.subTest(image=image), self.assertRaises(RuntimeError):
                t.ancestor_matches(changed.__getitem__, 30, terminal, 501)
        with self.assertRaises(RuntimeError):
            t.ancestor_matches(rows.__getitem__, 20, terminal, 501)  # The product/child itself may NEVER be root.
        changed = copy.deepcopy(rows)
        changed[10]['startMicroseconds'] += 1
        with self.assertRaises(RuntimeError):
            t.ancestor_matches(changed.__getitem__, 30, terminal, 501)

    def test_command_shell_registration_reuses_the_verified_native_ancestry(self):
        terminal = dict(pid=10, uid=501, startSeconds=100, startMicroseconds=50)
        rows = {
            10: dict(terminal, realUid=501, parentPid=1, uniqueId=1000, parentUniqueId=1, live=True),
            20: t.observe_ancestor(ReadOnlyApi(), native, 20),
            30: dict(pid=30, uid=501, realUid=501, parentPid=20, uniqueId=3000, parentUniqueId=2000,
                     startSeconds=101, startMicroseconds=60, live=True),
            40: dict(pid=40, uid=501, realUid=501, parentPid=30, uniqueId=4000, parentUniqueId=3000,
                     startSeconds=102, startMicroseconds=70, live=True),
        }
        ancestry, record = t.command_shell_ancestry(rows.__getitem__, 40, terminal, 501, config()['source'])
        self.assertEqual(ancestry, dict(method=t.ANCESTRY_METHOD, depth=4, systemLoginAncestors=1,
                                       restrictedCombinedDenials=1))
        self.assertEqual(record, dict(schema=1, source=config()['source'], terminal=terminal,
            shells=[dict(pid=30, uid=501, uniqueId=3000, startSeconds=101, startMicroseconds=60)]))
        extended = {**rows, 50: dict(pid=50, uid=501, realUid=501, parentPid=40, uniqueId=5000,
                                    parentUniqueId=4000, startSeconds=103, startMicroseconds=80, live=True)}
        _, chain = t.command_shell_ancestry(extended.__getitem__, 50, terminal, 501, config()['source'])
        self.assertEqual([row['pid'] for row in chain['shells']], [40, 30])
        # This is the nonroot .command parent, never the privileged login or the Terminal process.
        for key, bad in (('uid', 0), ('realUid', 0), ('parentUniqueId', 999), ('live', False),
                         ('uniqueId', True), ('startSeconds', 0), ('startMicroseconds', 1_000_000)):
            changed = copy.deepcopy(rows)
            changed[30][key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.command_shell_ancestry(changed.__getitem__, 40, terminal, 501, config()['source'])
        with self.assertRaises(RuntimeError):
            t.command_shell_ancestry(rows.__getitem__, 30, terminal, 501, config()['source'])
        for source in ({}, {**config()['source'], 'extra': 1}, {'commit': 'HEAD', 'tree': 'b' * 40}):
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                t.command_shell_ancestry(rows.__getitem__, 40, terminal, 501, source)

    def test_shell_exit_file_does_not_prove_shell_retirement_or_authorize_early_quit(self):
        source = (ROOT / 'scripts/diagnostics/apple-terminal-context.m').read_text()
        self.assertIn('command-shell.json', source)
        self.assertIn('@"commandShellsObserved"] = @YES', source)
        self.assertIn('@"commandShellsRetired"] = @YES', source)
        self.assertLess(source.index('@"scriptChildReaped"] = @YES'), source.index('command-shell.json'))
        self.assertLess(source.index('@"commandShellsRetired"] = @YES'), source.index('[application terminate]'))
        self.assertIn('NSProcessInfo.processInfo.systemUptime + 30', source)
        self.assertIn('waitUntil(quitDeadline - NSProcessInfo.processInfo.systemUptime', source)
        self.assertIn('shellRetirement(shellIdentity, uid)', source)
        self.assertIn('shellObservation < 0', source)  # Permission/unknown is fatal, never absence.
        for flag in ('commandShellsObserved', 'commandShellsRetired'):
            self.assertIn(flag, t.APPLICATION_FLAGS)
        for check in ('SHELL_REGISTRATION', 'SHELL_OBSERVATION', 'SHELL_RETIREMENT'):
            self.assertIn(check, t.CHECKS)

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
        for key, bad in (('executionMode', 'arm64'), ('executionMode', None), ('exitCode', True), ('schema', True), ('schema', 1), ('stage', 'PRIVATE'), ('nonrootChild', 1),
                         ('scope', 'PRODUCT_PASS'), ('raw', 'private'), ('logs', {'private': {}}),
                         ('failureCheck', 'private'), ('openErrorCode', True), ('openErrorDomain', 'private')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.validate_proof({**value, key: bad}, value['source'], complete=False)
        for key, bad in (('compilerDiagnostics', None), ('ancestry', None), ('failureCheck', 'QUIT_COMPLETION'),
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
        self.assertEqual(t.check_category('Replaced native parent refused'), 'ANCESTOR_PARENT_IDENTITY')
        self.assertEqual(t.check_category('Exact application identity required'), 'APPLICATION_RECEIPT')

    def test_pre_context_source_failure_remains_specific_without_exporting_git_output(self):
        for message, category in t.private.SOURCE_CHECKS.items():
            self.assertEqual(t.check_category(message), category)
            self.assertEqual(t.log_metadata(('CONTEXT_FAILURE ' + category + '\nprivate output\n').encode())[
                'failedChecks'], [category])
        self.assertEqual(t.log_metadata(b'CONTEXT_FAILURE SOURCE_UNKNOWN_TIMEOUT\n')['failedChecks'], [])

    def test_ancestry_evidence_is_bounded_and_never_contains_native_identifiers(self):
        value = proof()['ancestry']
        t.validate_ancestry(value)
        for key, bad in (('method', 'PID_ONLY'), ('depth', 1), ('depth', 33), ('depth', True),
                         ('systemLoginAncestors', 2), ('systemLoginAncestors', True),
                         ('restrictedCombinedDenials', 1), ('pid', 10), ('uid', 501), ('path', '/private')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                t.validate_ancestry({**value, key: bad})

    def test_specific_ancestry_failure_is_reported_without_admitting_root_or_exporting_identity(self):
        terminal = dict(pid=10, uid=501, startSeconds=100, startMicroseconds=50)
        row = dict(pid=20, uid=0, realUid=0, parentPid=10, uniqueId=2000, parentUniqueId=1000,
                   startSeconds=101, startMicroseconds=60, live=True, systemLogin=True)
        with self.assertRaisesRegex(RuntimeError, '^Native ancestor is privileged system login$') as failure:
            t.ancestor_matches(lambda _: row, 20, terminal, 501)
        self.assertEqual(t.check_category(str(failure.exception)), 'ANCESTOR_SYSTEM_LOGIN')
        with self.assertRaisesRegex(RuntimeError, '^Native ancestor credentials differ$'):
            t.ancestor_matches(lambda _: {**row, 'systemLogin': False}, 20, terminal, 501)
        for message, category in t.ANCESTRY_CHECKS.items():
            self.assertEqual(t.log_metadata(('CONTEXT_FAILURE ' + category + '\n').encode())['failedChecks'], [category])
            self.assertEqual(t.check_category(message), category)

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

    def test_only_explicit_native_apple_product_lanes_prepare_context_not_production_defaults(self):
        source = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        context = next(line.split(': ', 1)[1] for line in source.splitlines() if 'RPC_APPLE_TERMINAL_CONTEXT:' in line)
        advertising = next(line.split(': ', 1)[1] for line in source.splitlines() if 'RPC_APPLE_BONJOUR_ADVERTISING:' in line)
        modifier = " && !contains(github.event.head_commit.message, '[rpc-intel-audit-context]')"
        self.assertEqual(context.count(modifier), 1)
        # Only this separately admitted runtime diagnostic avoids creating a
        # Terminal lease. Every ordinary lane keeps its exact original context
        # and advertising predicate, not an arbitrary exemption or broad skip.
        self.assertEqual(context.replace(modifier, '', 1), advertising)
        self.assertEqual(advertising, "${{ (matrix.lane == 'apple-x64' || matrix.lane == 'apple-arm64') && matrix.investigation != 'cold-boot' && "
                         "!(contains(github.event.head_commit.message, '[rpc-admit]') || "
                         "contains(github.event.head_commit.message, '[rpc-apple-admit]') || "
                         "contains(github.event.head_commit.message, '[rpc-intel-admit]')) }}")
        self.assertIn("RPC_APPLE_SSH_CONTEXT: 'false'", source)
        self.assertIn("RPC_APPLE_LAUNCHD_CONTEXT: 'false'", source)
        self.assertIn('python3 scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" --', source)
        self.assertIn('python3 scripts/tests/with-darwin-terminal-context-test.py', source)
        self.assertIn('RPC_APPLE_LANE: ${{ matrix.lane }}', source)
        self.assertIn('python3 scripts/tests/rpc-apple-runner-context-test.py', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
