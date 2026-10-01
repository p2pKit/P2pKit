#!/usr/bin/env python3
"""Offline failure/restoration controls. Never execute sudo or change host preferences."""
import copy
import json
import os
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_bonjour_environment as b

SOURCE = {'commit': 'a' * 40, 'tree': 'b' * 40}
BEFORE = {b.KEY: True, 'Unrelated': {'Enabled': True, 'Value': b'private-value'}}
ACTIVE = {**BEFORE, b.KEY: False}
POLICY = (0, 0, 0o644)
SERVICE_CONFIG = {'Label': 'com.apple.mDNSResponder.reloaded', 'ProgramArguments': ['/usr/sbin/mDNSResponder']}
SERVICE_SHA = b.digest(plistlib.dumps(SERVICE_CONFIG))


def snapshot(value, policy=POLICY):
    return copy.deepcopy(value), policy, plistlib.dumps(value)


def complete():
    return dict(schema=2, scope=b.SCOPE, source=SOURCE, nativeLane='apple-x64', stage='FINALIZED', failure='NONE', restoreFailure='NONE',
        serviceConfigurationSha256=SERVICE_SHA,
        observations={k: b.summarize(v) for k, v in (('before', BEFORE), ('active', ACTIVE), ('restored', BEFORE))},
        commands={k: dict(exitCode=0, timedOut=False, failure='NONE', bytes=0, sha256=b.digest(b'')) for k in b.COMMANDS},
        **dict.fromkeys(b.FLAGS, True))


class AdvertisingControls(unittest.TestCase):
    def prepare(self, parent):
        service = patch.object(b, 'read_service_configuration', return_value=SERVICE_SHA)
        service.start()
        self.addCleanup(service.stop)
        with patch.object(b, 'admit', return_value='apple-x64'):
            # Darwin's temporary path commonly contains /var -> /private/var.
            # Accepted fixtures must use the same physical form as real state;
            # production symlink rejection is deliberately unchanged.
            return b.AdvertisingPreparation(parent.resolve(strict=True), SOURCE)

    def fake_commands(self, instance, fail=None):
        calls = []

        def command(label):
            calls.append(label)
            category = 'PROTECTED_SERVICE' if label == fail else 'NONE'
            instance.proof['commands'][label] = dict(exitCode=1 if label == fail else 0, timedOut=False,
                failure=category, bytes=0, sha256=b.digest(b''))
            if label == fail:
                raise b.PreparationFailure(category)
        instance.command = command
        return calls

    def test_only_fixed_boolean_and_service_manager_commands_are_available(self):
        self.assertEqual(set(b.COMMANDS), {'inspect', 'apply', 'reload', 'restore', 'restore-reload'})
        for label, argv in b.COMMANDS.items():
            if label == 'inspect':
                self.assertEqual(argv, ['/bin/launchctl', 'print', 'system/com.apple.mDNSResponder.reloaded'])
                continue
            self.assertEqual(argv[:2], ['/usr/bin/sudo', '-n'])
            if label in ('apply', 'restore'):
                self.assertEqual(argv[2:], ['/usr/bin/defaults', 'write', b.DOMAIN, b.KEY, '-bool',
                                          'false' if label == 'apply' else 'true'])
            else:
                self.assertEqual(argv[2:], ['/bin/launchctl', 'kickstart', '-k', 'system/com.apple.mDNSResponder.reloaded'])
        text = (ROOT / 'scripts/rpc_apple_bonjour_environment.py').read_text()
        for forbidden in ('os.kill(', 'killall', 'tccutil', 'osascript', 'csrutil', 'chmod(', 'setuid(', 'shell=True'):
            self.assertNotIn(forbidden, text)

    def test_only_own_disposable_native_intel_nonroot_context_is_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            env = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', GITHUB_REPOSITORY='p2pKit/P2pKit',
                GITHUB_REF=b.private.REF, GITHUB_EVENT_NAME='push', GITHUB_SHA=SOURCE['commit'], GITHUB_WORKSPACE=str(ROOT),
                RPC_QUALIFY_REQUESTED='true', RPC_APPLE_BONJOUR_ADVERTISING='true', RPC_APPLE_TERMINAL_CONTEXT='true',
                RPC_QUALIFICATION_PARENT=str(parent), RUNNER_TEMP=str(parent), RPC_APPLE_LANE='apple-x64')
            with patch.object(b.platform, 'system', return_value='Darwin'), patch.object(b.platform, 'machine', return_value='x86_64'), \
                    patch.object(b.apple_context, 'host_role', return_value='macos-x64'), \
                    patch.object(b.os, 'getuid', return_value=501), patch.object(b.os, 'geteuid', return_value=501), \
                    patch.object(b.os, 'getgid', return_value=20), patch.object(b.os, 'getegid', return_value=20), \
                    patch.object(b.private, 'private_parent'), patch.object(b.private, 'source_snapshot', return_value=SOURCE):
                b.admit(env, parent, SOURCE)
                for key, wrong in (('GITHUB_REF', 'refs/heads/main'), ('GITHUB_EVENT_NAME', 'pull_request'),
                        ('RUNNER_ENVIRONMENT', 'self-hosted'), ('GITHUB_SHA', 'c' * 40), ('GITHUB_REPOSITORY', 'other/repo'),
                        ('RPC_APPLE_BONJOUR_ADVERTISING', 'false'), ('RPC_APPLE_TERMINAL_CONTEXT', 'false'),
                        ('GITHUB_WORKSPACE', str(parent)), ('RPC_QUALIFICATION_PARENT', str(parent / 'other'))):
                    with self.subTest(key=key), self.assertRaises(Exception):
                        b.admit({**env, key: wrong}, parent, SOURCE)
                for attribute, wrong in (('getuid', 0), ('geteuid', 0), ('getgid', 0), ('getegid', 0)):
                    with patch.object(b.os, attribute, return_value=wrong), self.assertRaises(Exception):
                        b.admit(env, parent, SOURCE)
                for attribute, wrong in (('system', 'Linux'), ('machine', 'arm64')):
                    with patch.object(b.platform, attribute, return_value=wrong), self.assertRaises(Exception):
                        b.admit(env, parent, SOURCE)
                with patch.object(b.platform, 'machine', return_value='arm64'), \
                        patch.object(b.apple_context, 'host_role', return_value='macos-arm64'):
                    arm = {**env, 'RPC_APPLE_LANE': 'apple-arm64'}
                    self.assertEqual(b.admit(arm, parent, SOURCE), 'apple-arm64')
                    with self.assertRaises(RuntimeError):
                        b.admit(env, parent, SOURCE)

    def test_complete_restoration_proofs_cannot_cross_native_architectures(self):
        for lane in b.apple_context.HOSTS:
            p = {**complete(), 'nativeLane': lane}
            self.assertEqual(b.validate(p, SOURCE, expected_lane=lane), p)
            for wrong in (None, 'android-art', 'apple-arm64' if lane == 'apple-x64' else 'apple-x64'):
                with self.assertRaises(RuntimeError):
                    b.validate({**p, 'nativeLane': wrong}, SOURCE, expected_lane=lane)

    def test_success_requires_round_trip_of_all_preferences_and_file_policy(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(ACTIVE), snapshot(BEFORE)]), \
                patch.object(b.private, 'source_snapshot', return_value=SOURCE):
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance)
            instance.apply()
            instance.finish()
            self.assertEqual(calls, ['inspect', 'apply', 'reload', 'restore', 'restore-reload'])
            self.assertEqual(instance.proof, complete())
            self.assertEqual(plistlib.loads((instance.directory / 'original.plist').read_bytes()), BEFORE)
            self.assertEqual((instance.directory / 'original.plist').stat().st_mode & 0o777, 0o600)
            self.assertNotIn('private-value', json.dumps(instance.proof))

    def test_a_product_exception_still_requires_restoration_and_does_not_change_its_result(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(ACTIVE), snapshot(BEFORE)]), \
                patch.object(b.private, 'source_snapshot', return_value=SOURCE):
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance)
            with self.assertRaisesRegex(RuntimeError, 'product failed'):
                try:
                    instance.apply()
                    raise RuntimeError('product failed')
                finally:
                    instance.finish()
            self.assertEqual(calls[-2:], ['restore', 'restore-reload'])

    def test_service_protection_failure_restores_disk_without_retrying_or_falling_back(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(ACTIVE), snapshot(BEFORE)]), \
                patch.object(b.private, 'source_snapshot', return_value=SOURCE):
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance, fail='reload')
            with self.assertRaises(b.PreparationFailure):
                instance.apply()
            with self.assertRaises(Exception):
                instance.finish()
            self.assertEqual(calls, ['inspect', 'apply', 'reload', 'restore'])
            self.assertTrue(instance.proof['restored'])
            self.assertFalse(instance.proof['restoreReloadSucceeded'])
            self.assertEqual(instance.proof['failure'], 'PROTECTED_SERVICE')
            b.validate(instance.proof, SOURCE, complete=False)

    def test_failed_write_that_partially_changed_the_key_is_restored(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(BEFORE)]), \
                patch.object(b.private, 'source_snapshot', return_value=SOURCE):
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance, fail='apply')
            with self.assertRaises(b.PreparationFailure):
                instance.apply()
            with self.assertRaises(Exception):
                instance.finish()
            self.assertEqual(calls, ['inspect', 'apply', 'restore'])
            self.assertTrue(instance.proof['restored'])

    def test_no_existing_suppression_is_not_permission_to_write_new_preferences(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference', return_value=snapshot(ACTIVE)), \
                patch.object(b.private, 'source_snapshot', return_value=SOURCE):
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance)
            with self.assertRaises(Exception):
                instance.apply()
            with self.assertRaises(Exception):
                instance.finish()
            self.assertEqual(calls, ['inspect'])  # Read-only; no preference mutation.
            self.assertFalse(instance.proof['changeAttempted'])

    def test_unrelated_preference_or_file_permission_drift_remains_failure_after_key_restoration(self):
        for current, policy in (({**ACTIVE, 'Unexpected': 'private'}, POLICY), (ACTIVE, (0, 0, 0o640))):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                    side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(current, policy), snapshot({**current, b.KEY: True}, policy)]), \
                    patch.object(b.private, 'source_snapshot', return_value=SOURCE):
                instance = self.prepare(Path(tmp))
                calls = self.fake_commands(instance)
                instance.apply()
                with self.assertRaises(Exception):
                    instance.finish()
                self.assertEqual(calls[-2:], ['restore', 'restore-reload'])
                self.assertEqual(instance.proof['restoreFailure'], 'RESTORATION')
                self.assertFalse(instance.proof['restored'])

    def test_plist_boolean_and_integer_are_not_equivalent_unchanged_preferences(self):
        self.assertFalse(b.equal_preferences({'Other': True}, {'Other': 1}))
        self.assertTrue(b.equal_preferences({'Second': 2, 'First': True}, {'First': True, 'Second': 2}))

    def test_actual_service_label_is_not_inferred_from_the_plist_filename(self):
        with patch.object(b, 'read_system_file', return_value=(plistlib.dumps(SERVICE_CONFIG), POLICY)) as read:
            self.assertEqual(b.read_service_configuration(), SERVICE_SHA)
            read.assert_called_once_with(Path('/System/Library/LaunchDaemons/com.apple.mDNSResponder.plist'))
            self.assertEqual(b.SERVICE, 'system/' + SERVICE_CONFIG['Label'])
            self.assertNotEqual(b.SERVICE.removeprefix('system/'), b.SERVICE_CONFIGURATION.stem)

    def test_unexpected_service_program_arguments_label_and_suppression_are_rejected(self):
        for change in ({'Label': 'com.apple.mDNSResponder'}, {'Label': 'untrusted'},
                {'Program': '/bin/sh'}, {'ProgramArguments': ['/bin/sh']}, {'ProgramArguments': []},
                {'ProgramArguments': ['/usr/sbin/mDNSResponder', '-NoMulticastAdvertisements']},
                {'ProgramArguments': '/usr/sbin/mDNSResponder'}, {'ProgramArguments': ['/usr/sbin/mDNSResponder', 1]}):
            raw = plistlib.dumps({**SERVICE_CONFIG, **change})
            with self.subTest(change=change), patch.object(b, 'read_system_file', return_value=(raw, POLICY)), \
                    self.assertRaises(RuntimeError):
                b.read_service_configuration()

    def test_absent_or_refused_service_is_checked_before_any_preference_mutation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.private, 'source_snapshot', return_value=SOURCE), \
                patch.object(b, 'read_preference') as preference:
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance, fail='inspect')
            with self.assertRaises(b.PreparationFailure):
                instance.apply()
            with self.assertRaises(RuntimeError):
                instance.finish()
            preference.assert_not_called()
            self.assertEqual(calls, ['inspect'])
            self.assertFalse(instance.proof['changeAttempted'])
            self.assertFalse(instance.proof['serviceRegistered'])
            self.assertEqual(instance.proof['stage'], 'SERVICE')

    def test_changed_service_configuration_never_reaches_a_service_command(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.subprocess, 'run') as run:
            instance = self.prepare(Path(tmp))
            instance.proof['serviceConfigurationSha256'] = 'c' * 64
            for command in ('inspect', 'reload', 'restore-reload'):
                with self.subTest(command=command), self.assertRaisesRegex(RuntimeError, 'configuration changed'):
                    instance.command(command)
            run.assert_not_called()

    def test_failed_restore_and_failed_restore_reload_are_never_suppressed(self):
        for fail in ('restore', 'restore-reload'):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                    side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(ACTIVE), snapshot(BEFORE)]), \
                    patch.object(b.private, 'source_snapshot', return_value=SOURCE):
                instance = self.prepare(Path(tmp))
                self.fake_commands(instance, fail=fail)
                instance.apply()
                with self.assertRaises(Exception):
                    instance.finish()
                self.assertEqual(instance.proof['restoreFailure'], 'PROTECTED_SERVICE')
                self.assertTrue((instance.directory / 'result.json').is_file())

    def test_source_drift_still_restores_system_setting_but_cannot_finalize(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'read_preference',
                side_effect=[snapshot(BEFORE), snapshot(ACTIVE), snapshot(ACTIVE), snapshot(BEFORE)]), \
                patch.object(b.private, 'source_snapshot', return_value={**SOURCE, 'tree': 'c' * 40}):
            instance = self.prepare(Path(tmp))
            calls = self.fake_commands(instance)
            instance.apply()
            with self.assertRaises(Exception):
                instance.finish()
            self.assertEqual(calls[-2:], ['restore', 'restore-reload'])
            self.assertFalse(instance.proof['sourceUnchanged'])

    def test_missing_flags_and_wrong_types_cannot_finalize(self):
        b.validate(complete(), SOURCE)
        for key in b.FLAGS:
            for bad in (False, 1, 'true'):
                with self.subTest(key=key, bad=bad), self.assertRaises(Exception):
                    b.validate({**complete(), key: bad}, SOURCE)
        for change in (dict(schema=True), dict(scope='LAN_PASS'), dict(stage='ACTIVE'), dict(failure='PROTECTED_SERVICE'),
                       dict(restoreFailure='RESTORATION'), dict(commands={}), dict(source={**SOURCE, 'tree': 'c' * 40})):
            with self.assertRaises(Exception):
                b.validate({**complete(), **change}, SOURCE)

    def test_arbitrary_preference_log_and_identity_fields_are_never_public(self):
        for key in ('value', 'key', 'path', 'interface', 'payload', 'identity', 'stderr'):
            for part in (None, 'observations', 'commands'):
                value = complete()
                target = value if part is None else value[part]['before' if part == 'observations' else 'apply']
                target[key] = 'private'
                with self.assertRaises(Exception):
                    b.validate(value, SOURCE, complete=False)
        value = complete()
        value['observations']['active']['otherPreferencesSha256'] = 'd' * 64
        with self.assertRaises(Exception):
            b.validate(value, SOURCE)

    def test_failure_classifier_exports_closed_categories_not_raw_messages(self):
        for raw, category in ((b'Operation not permitted while System Integrity Protection is engaged', 'PROTECTED_SERVICE'),
                (b'sudo: a password is required', 'PRIVILEGE_UNAVAILABLE'), (b'Operation not permitted', 'OPERATION_NOT_PERMITTED'),
                (b'Could not find service', 'SERVICE_UNAVAILABLE'), (b'private-detail', 'COMMAND_FAILED')):
            self.assertEqual(b.command_failure(raw, 1, False), category)
        self.assertEqual(b.command_failure(b'private', 0, False), 'NONE')
        self.assertEqual(b.command_failure(b'', 125, True), 'COMMAND_TIMEOUT')

    def test_actual_subprocess_path_is_bounded_private_fixed_and_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            instance = self.prepare(Path(tmp))
            instance.command('apply')
            argv, kwargs = run.call_args
            self.assertEqual(argv, (b.COMMANDS['apply'],))
            self.assertEqual(kwargs['timeout'], 30)
            self.assertEqual(kwargs['env'], {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'C', 'LC_ALL': 'C'})
            self.assertEqual((instance.directory / 'apply.log').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(Exception):
                instance.command('apply')
            with self.assertRaises(Exception):
                instance.command('arbitrary')
            self.assertEqual(run.call_count, 1)

    def test_accepted_fixture_resolves_temporary_alias_but_reader_still_rejects_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            actual = root / 'actual'
            actual.mkdir(mode=0o700)
            alias = root / 'alias'
            alias.symlink_to(actual, target_is_directory=True)
            instance = self.prepare(alias)
            self.assertEqual(instance.directory, actual / 'bonjour-advertising')
            value = instance.directory / 'probe.log'
            b.private.write_new(value, b'')
            self.assertEqual(b.private.read_private(value, os.getuid()), b'')
            with self.assertRaises(Exception):
                b.private.read_private(alias / 'bonjour-advertising/probe.log', os.getuid())

    def test_system_preference_reader_refuses_links_wrong_owner_and_nonboolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / 'preference.plist'
            path.write_bytes(plistlib.dumps(BEFORE))
            path.chmod(0o600)
            with patch.object(b, 'PREFERENCE', path):
                # This test may run as either root in the local container or as
                # nonroot on Actions. Simulate only the root-owned file metadata.
                original = Path.lstat

                def info(item):
                    result = original(item)
                    if item != path:
                        return result
                    fields = list(result)
                    fields[4] = 0
                    return os.stat_result(fields)
                with patch.object(Path, 'lstat', info):
                    self.assertEqual(b.read_preference()[0], BEFORE)
                    path.write_bytes(plistlib.dumps({b.KEY: 1}))
                    with self.assertRaises(Exception):
                        b.read_preference()
                link = path.parent / 'alias'
                link.symlink_to(path)
                with patch.object(b, 'PREFERENCE', link), self.assertRaises(Exception):
                    b.read_preference()
                path.chmod(0o666)
                with self.assertRaises(Exception):
                    b.read_preference()


if __name__ == '__main__':
    unittest.main(verbosity=2)
