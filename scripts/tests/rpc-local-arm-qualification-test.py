#!/usr/bin/env python3
"""Offline local admission/orchestration checks; never native/product receipts."""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('local_arm_test', ROOT / 'scripts/run-rpc-local-arm-qualification.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Admission(unittest.TestCase):
    def test_current_official_environment_is_27_not_26(self):
        m.environment_versions(b'27.0\n', b'Xcode 27.0\nBuild version 27A266a\n')
        for os_version, xcode in ((b'26.0\n', b'Xcode 27.0\n'), (b'27.0\n', b'Xcode 26.5\n'),
                                  (b'27.0\n', b'Xcode 27.1\n'), (b'27junk\n', b'Xcode 27.0\n')):
            with self.subTest(os=os_version, xcode=xcode), self.assertRaises(RuntimeError):
                m.environment_versions(os_version, xcode)

    def test_no_hosted_identity_translation_or_privilege_substitution(self):
        m.local_host({}, 'Darwin', 'arm64', 501, 501)
        for values in (({}, 'Darwin', 'x86_64', 501, 501), ({}, 'Linux', 'arm64', 501, 501),
                       ({}, 'Darwin', 'arm64', 0, 0), ({}, 'Darwin', 'arm64', 501, 0),
                       ({'GITHUB_ACTIONS': 'true'}, 'Darwin', 'arm64', 501, 501),
                       ({'RUNNER_ENVIRONMENT': 'github-hosted'}, 'Darwin', 'arm64', 501, 501),
                       ({'P2PKIT_AUDIT_STATE_DIR': '/USED'}, 'Darwin', 'arm64', 501, 501),
                       ({'P2PKIT_AUDIT_OWNERSHIP_CHAIN': 'USED'}, 'Darwin', 'arm64', 501, 501)):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                m.local_host(*values)

    def test_exact_one_shot_bootstrap_argv_never_contains_legacy_driver(self):
        argv = m.run_argv(Path('/PRIVATE'), 'a' * 40)
        self.assertEqual(argv[1], '-B')
        self.assertEqual(Path(argv[2]).name, 'run-rpc-local-arm-qualification.py')
        self.assertIn('--owner-authorized-arm27', argv)
        self.assertEqual(argv[-1], 'a' * 40)
        self.assertNotIn('sudo', ' '.join(argv))

    def test_private_parent_rejects_symlink_shared_mode_and_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            os.chmod(parent, 0o700)
            self.assertEqual(m.private_parent(parent), parent)
            linked = parent / 'alias'
            linked.symlink_to(parent, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                m.private_parent(linked)
            os.chmod(parent, 0o755)
            with self.assertRaises(RuntimeError):
                m.private_parent(parent)
            with self.assertRaises(RuntimeError):
                m.private_parent(ROOT)

    def test_session_proof_cannot_grant_native_or_product_admission(self):
        good = dict(m.SESSION_PROOF, previousSessionAssigned=True)
        m.session_proof(good)
        for change in (dict(rootCannotBeRegained=False), dict(privilegedObservationOrProductExecution=True),
                       dict(freshAssignedSession=1), dict(previousSessionAssigned='true'), dict(extra=True)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.session_proof(good | change)

    def test_canonical_origin_and_baseline_ancestry_cannot_be_substituted(self):
        source = dict(commit='a' * 40, tree='b' * 40, status='', diffSha256=m.runner.digest(b''))
        answers = {('symbolic-ref', 'HEAD'): (m.q.REF + '\n').encode(),
                   ('rev-parse', '--is-shallow-repository'): b'false\n',
                   ('for-each-ref', '--format=%(refname)', 'refs/tags'): b'',
                   ('config', '--get', 'remote.origin.url'): b'https://github.com/p2pKit/P2pKit\n',
                   ('merge-base', '--is-ancestor', m.BASELINE, source['commit']): b''}
        with patch.object(m.runner, 'source_snapshot', return_value=source), \
                patch.object(m.runner, 'git', side_effect=lambda root, *argv: answers[argv]) as git:
            self.assertEqual(m.source_admission(source['commit']), source)
            self.assertEqual(git.call_args.args[1:], ('merge-base', '--is-ancestor', m.BASELINE, source['commit']))
            answers[('config', '--get', 'remote.origin.url')] = b'https://github.com/p2pKit/P2pKit.git\n'
            self.assertEqual(m.source_admission(source['commit']), source)
            answers[('config', '--get', 'remote.origin.url')] = b'https://example.invalid/P2pKit\n'
            with self.assertRaises(RuntimeError):
                m.source_admission(source['commit'])


class Orchestration(unittest.TestCase):
    def test_signal_environment_is_prepared_only_after_fresh_session_admission(self):
        calls = []
        initial, proof, prepared = {'phase': 'before'}, {'nativeAdmission': False}, {'source': 'OFFLINE'}
        def normalize(retain):
            calls.append('normalize')
            retain(initial)
            return proof
        with patch.object(m, 'admit_session', side_effect=lambda *args: calls.append('session') or prepared), \
                patch.object(m, 'admit_source_inputs', side_effect=lambda *args: calls.append('source') or prepared), \
                patch.object(m.signal_environment, 'normalize', side_effect=normalize), \
                patch.object(m.bootstrap, 'write_new', side_effect=lambda path, value: calls.append(path.name)):
            self.assertEqual(m.admit_execution_environment(Path('/PRIVATE'), 'a' * 40), (prepared, proof))
        self.assertEqual(calls, ['session', 'normalize', 'local-signal-environment-before.json',
                                 'local-signal-environment.json', 'source'])

    def test_failed_signal_preparation_cannot_start_git_or_native_state(self):
        with patch.object(m, 'admit_session', return_value={'source': 'OFFLINE'}), \
                patch.object(m.signal_environment, 'normalize', side_effect=RuntimeError('OFFLINE pending signal')), \
                patch.object(m, 'admit_source_inputs') as source, patch.object(m.runner, 'initialize') as initialize:
            with self.assertRaises(RuntimeError):
                m.admit_execution_environment(Path('/PRIVATE'), 'a' * 40)
            source.assert_not_called()
            initialize.assert_not_called()

    def test_failed_session_cannot_normalize_signals_or_initialize_native_state(self):
        with patch.object(m, 'admit_session', side_effect=RuntimeError('OFFLINE session refused')), \
                patch.object(m.signal_environment, 'normalize') as normalize, \
                patch.object(m.runner, 'initialize') as initialize:
            with self.assertRaises(RuntimeError):
                m.admit_execution_environment(Path('/PRIVATE'), 'a' * 40)
            normalize.assert_not_called()
            initialize.assert_not_called()

    def test_installed_tool_keeps_its_prepared_settings_package_not_only_version(self):
        package = m.module('offline_local_arm_xcodegen_package', 'rpc_xcodegen_package.py')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            original = base / 'installed/bin/xcodegen'
            original.parent.mkdir(parents=True)
            original.write_bytes(b'OFFLINE NEVER EXECUTED')
            original.chmod(0o755)
            for name in package.REQUIRED_PRESETS:
                path = original.parent.parent / package.PRESETS / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'OFFLINE_SETTING: true\n')
                path.chmod(0o644)
            value = m.LocalArm.__new__(m.LocalArm)
            value.state = base / 'state'
            (value.state / 'tools').mkdir(mode=0o700, parents=True)
            value.prepared = dict(xcodegen=str(original), xcodegenSha256=m.runner.file_digest(original),
                                  xcodegenPackage=package.inventory(original))
            value.result = {}
            value.invoke = Mock(return_value={'id': 'OFFLINE'})
            value.output = Mock(return_value=b'Version: 2.45.4\n')
            with patch.dict(os.environ, PATH='/OFFLINE'):
                value.installed_tools()
                executable = value.state / 'tools/xcodegen/bin/xcodegen'
                value.invoke.assert_called_once_with('installed-xcodegen', [str(executable), '--version'], 45)
                self.assertEqual(package.inventory(executable)['files'], value.prepared['xcodegenPackage']['files'])
                self.assertEqual(value.result['installedTools']['resourceFiles'], len(package.REQUIRED_PRESETS))
                self.assertFalse(value.result['installedTools']['globalInstallation'])

    def fixture(self):
        value = m.LocalArm.__new__(m.LocalArm)
        value.unsafe = False
        value.result = dict(phases={}, errors=[], result='FAIL')
        for name in ('prepare_gradle_distribution', 'native_controls', 'toolchain', 'installed_tools', 'select_simulator', 'apple_producer',
                     'apple_project', 'swift_runtime', 'owned_swift', 'phone_app', 'mobile_driver',
                     'mac_generator_preflight', 'finish'):
            setattr(value, name, Mock())
        return value

    def test_only_remaining_actions_not_full_platform_abi_dokka_or_capacity_reruns(self):
        value = self.fixture()
        value.run()
        self.assertEqual(list(value.result['phases']), list(m.PLAN))
        self.assertEqual(m.PLAN[:2], ('gradle-distribution', 'native-controls'))
        self.assertEqual(value.owned_swift.call_args_list[0].args, (False,))
        self.assertEqual(value.owned_swift.call_args_list[1].args, (True,))
        value.phone_app.assert_called_once_with()
        value.mobile_driver.assert_called_once_with()
        value.mac_generator_preflight.assert_called_once_with()
        value.finish.assert_called_once_with()
        self.assertNotIn('full-platform', value.result['phases'])

    def test_assertion_failure_does_not_skip_independent_actual_cancellation_or_phone(self):
        value = self.fixture()
        value.swift_runtime.side_effect = RuntimeError('synthetic failure')
        value.run()
        self.assertEqual(value.result['phases']['swift-runtime']['status'], 'FAIL')
        self.assertEqual(value.owned_swift.call_count, 2)
        value.phone_app.assert_called_once_with()
        value.finish.assert_called_once_with()

    def test_native_finalization_failure_blocks_every_following_product_action(self):
        value = self.fixture()
        def unsafe():
            value.unsafe = True
            raise RuntimeError('synthetic ownership failure')
        value.native_controls.side_effect = unsafe
        value.run()
        value.toolchain.assert_not_called()
        value.owned_swift.assert_not_called()
        value.phone_app.assert_not_called()
        value.mobile_driver.assert_not_called()
        value.mac_generator_preflight.assert_not_called()
        value.finish.assert_called_once_with()
        self.assertTrue(all(v['status'] == 'BLOCKED_PREREQUISITE'
                            for k, v in value.result['phases'].items() if k not in ('gradle-distribution', 'native-controls')))
        self.assertEqual(value.result['phases']['gradle-distribution']['status'], 'PASS')

    def test_unverified_distribution_cannot_start_controls_or_any_product(self):
        value = self.fixture()
        value.prepare_gradle_distribution.side_effect = RuntimeError('OFFLINE wrong archive pin')
        value.run()
        value.native_controls.assert_not_called()
        value.toolchain.assert_not_called()
        value.phone_app.assert_not_called()
        value.mobile_driver.assert_not_called()
        value.finish.assert_called_once_with()
        self.assertEqual(value.result['phases']['gradle-distribution']['status'], 'FAIL')
        self.assertTrue(all(v['status'] == 'BLOCKED_PREREQUISITE'
                            for k, v in value.result['phases'].items() if k != 'gradle-distribution'))

    def test_distribution_stage_cannot_invoke_a_tool_or_change_finalizer_policy(self):
        value = m.LocalArm.__new__(m.LocalArm)
        value.parent, value.state = Path('/PRIVATE'), Path('/PRIVATE/state')
        value.context, value.prepared = {'id': 'OFFLINE'}, {'gradleDistribution': {'OFFLINE': True}}
        value.result = {}
        value.invoke = Mock(side_effect=AssertionError('Preparation must not execute a tool'))
        expected = dict(extracted=False, nativeAdmission=False, finalizerTimeoutSeconds=120)
        with patch.object(m.distribution, 'stage_archive', return_value=expected) as stage:
            value.prepare_gradle_distribution()
            stage.assert_called_once_with(m.ROOT, value.parent, value.prepared['gradleDistribution'],
                                          value.state, value.context)
            value.invoke.assert_not_called()
            self.assertEqual(value.result['gradleDistributionPreparation'], expected)
        self.assertIs(m.LocalArm.invoke, m.q.Qualification.invoke)
        self.assertIs(m.LocalArm.native_controls, m.q.Qualification.native_controls)

    def test_hosted_allowlists_remain_separate(self):
        self.assertNotIn('phone-app', m.q.Qualification.allowed_phases)
        self.assertIn('phone-app', m.LocalArm.allowed_phases)
        self.assertNotIn('installed-xcodegen', m.q.Qualification.allowed_purposes)
        self.assertIn('installed-xcodegen', m.LocalArm.allowed_purposes)

    def test_mobile_driver_requires_a_new_source_matched_producer_without_running_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = m.LocalArm.__new__(m.LocalArm)
            value.context = dict(source=dict(commit='a' * 40))
            value.result = {}
            value.policy = Mock(FLAGS=('--console=plain',))
            value.invoke = Mock(return_value=dict(id='OFFLINE-PRODUCER'))
            lab = Mock(classpath=Mock(return_value=os.pathsep.join(('/PRIVATE/a.jar', '/PRIVATE/b.jar'))))
            with patch.object(m, 'ROOT', Path(tmp)), patch.object(m, 'module', return_value=lab), \
                    patch.object(m.runner, 'file_digest', return_value='b' * 64):
                value.mobile_driver()
                value.invoke.assert_called_once_with('mobile-driver-producer',
                    [':p2p-sample-rpc:prepareRpcCapacityLab', '--console=plain'], 1800, 'gradle')
                lab.classpath.assert_called_once_with('a' * 40)
                self.assertEqual(value.result['mobileDriver']['jarCount'], 2)
                self.assertFalse(value.result['mobileDriver']['workloadExecuted'])
                (Path(tmp) / 'samples/p2p-sample-rpc/build/capacity-lab').mkdir(parents=True)
                with self.assertRaises(RuntimeError):
                    value.mobile_driver()
                self.assertEqual(value.invoke.call_count, 1)

    def test_phone_independent_full_mac_clock_keeps_native_budget_and_restores_authorization(self):
        value = m.LocalArm.__new__(m.LocalArm)
        value.state = Path('/NOT_EXECUTED/state')
        value.result = {}
        value.invoke = Mock(return_value={'id': 'OFFLINE'})
        value.output = Mock(return_value=b'{}')
        clock = Mock(assess_clock=Mock(return_value=dict(healthyForAttempt=True, capacityQualified=False)))
        with patch.object(m, 'module', return_value=clock), patch.dict(os.environ, RPC_CAPACITY_LAB_AUTHORIZED='BEFORE'):
            value.mac_generator_preflight()
            value.invoke.assert_called_once_with('mac-generator-clock',
                [sys.executable, str(m.ROOT / 'scripts/rpc_darwin_capacity.py'), '--directory',
                 '/NOT_EXECUTED/state/work/mobile-clock-arm27-preflight'], 150)
            self.assertEqual(os.environ['RPC_CAPACITY_LAB_AUTHORIZED'], 'BEFORE')
            self.assertFalse(value.result['macGeneratorPreflight']['capacityQualified'])
            clock.assess_clock.return_value = dict(healthyForAttempt=False, capacityQualified=False)
            with self.assertRaises(RuntimeError):
                value.mac_generator_preflight()
            self.assertFalse(value.result['macGeneratorPreflight']['healthyForAttempt'])
            value.invoke.side_effect = RuntimeError('OFFLINE native failure')
            with self.assertRaises(RuntimeError):
                value.mac_generator_preflight()
            self.assertEqual(os.environ['RPC_CAPACITY_LAB_AUTHORIZED'], 'BEFORE')


class Preparation(unittest.TestCase):
    def test_session_is_published_only_after_complete_distribution_and_source_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            parent = base / 'request'
            parent.mkdir(mode=0o700)
            developer = base / 'developer'
            developer.mkdir()
            java = base / 'jdk/bin'
            java.mkdir(parents=True)
            for name in ('java', 'javac'):
                (java / name).write_bytes(b'OFFLINE NOT EXECUTABLE')
            sdk = base / 'sdk'
            for name in ('android-36', 'android-37.0'):
                directory = sdk / 'platforms' / name
                directory.mkdir(parents=True)
                (directory / 'android.jar').write_bytes(b'OFFLINE')
            tool = base / 'installed/bin/xcodegen'
            tool.parent.mkdir(parents=True)
            tool.write_bytes(b'OFFLINE NEVER EXECUTED')
            tool.chmod(0o700)
            for name in m.xcodegen_package.REQUIRED_PRESETS:
                path = tool.parent.parent / m.xcodegen_package.PRESETS / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'OFFLINE_SETTING: true\n')
                path.chmod(0o644)
            args = argparse.Namespace(parent=parent, expected_commit='a' * 40, owner_authorized_arm27=True,
                java_home=java.parent, jdk21=java.parent, android_sdk=sdk, xcodegen=tool,
                gradle_distribution=base / 'explicit-input.zip')
            snapshot = dict(commit='a' * 40)
            with patch.object(m, 'local_host'), patch.object(m, 'DEVELOPER', str(developer)), \
                    patch.object(m, 'source_admission', return_value=snapshot), \
                    patch.object(m.distribution, 'prepare_archive', side_effect=RuntimeError('OFFLINE pin mismatch')) as archive:
                with self.assertRaises(RuntimeError):
                    m.prepare(args)
                archive.assert_called_once_with(m.ROOT, args.gradle_distribution, parent)
                self.assertEqual(list(parent.iterdir()), [])
                archive.side_effect = None
                archive.return_value = dict(scope='OFFLINE DATA ONLY')
                with patch('builtins.print') as published:
                    self.assertEqual(m.prepare(args), 0)
                published.assert_called_once_with(parent / 'private-session/session-config.json')
                prepared = json.loads((parent / 'prepared.json').read_text())
                self.assertEqual(prepared['gradleDistribution'], archive.return_value)
                self.assertEqual(prepared['xcodegenPackage'], m.xcodegen_package.inventory(tool))
                self.assertEqual(prepared['plan'], list(m.PLAN))
                self.assertFalse(prepared['bootstrapExecuted'])
                self.assertFalse(prepared['installationsRequested'])
                self.assertTrue((parent / 'private-session/session-config.json').is_file())
                self.assertFalse((parent / 'private-session/session-admission.json').exists())
                self.assertFalse((parent / 'state').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
