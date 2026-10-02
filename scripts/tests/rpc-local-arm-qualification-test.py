#!/usr/bin/env python3
"""Offline local admission/orchestration checks; never native/product receipts."""
import importlib.util
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
    def fixture(self):
        value = m.LocalArm.__new__(m.LocalArm)
        value.unsafe = False
        value.result = dict(phases={}, errors=[], result='FAIL')
        for name in ('native_controls', 'toolchain', 'installed_tools', 'select_simulator', 'apple_producer',
                     'apple_project', 'swift_runtime', 'owned_swift', 'phone_app', 'mobile_driver', 'finish'):
            setattr(value, name, Mock())
        return value

    def test_only_remaining_actions_not_full_platform_abi_dokka_or_capacity_reruns(self):
        value = self.fixture()
        value.run()
        self.assertEqual(list(value.result['phases']), list(m.PLAN))
        self.assertEqual(value.owned_swift.call_args_list[0].args, (False,))
        self.assertEqual(value.owned_swift.call_args_list[1].args, (True,))
        value.phone_app.assert_called_once_with()
        value.mobile_driver.assert_called_once_with()
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
        value.finish.assert_called_once_with()
        self.assertTrue(all(v['status'] == 'BLOCKED_PREREQUISITE'
                            for k, v in value.result['phases'].items() if k != 'native-controls'))

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
