#!/usr/bin/env python3
"""Offline fixture controls for read-only KVM metadata, not hardware execution."""
import errno
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('kvm_observation', ROOT / 'scripts/diagnostics/kvm-environment.py')
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class KvmObservations(unittest.TestCase):
    def test_missing_device_and_flags_do_not_become_a_virtualization_diagnosis_or_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            value = subject.observe(p / 'absent', p / 'cpu', p / 'modules')
        self.assertEqual(value['device']['inspection'], 'MISSING')
        self.assertIsNone(value['device']['readable'])
        self.assertEqual(value['cpuFlagsInspection'], 'MISSING')
        self.assertFalse(value['emulatorBooted'])
        self.assertFalse(value['artQualified'])
        self.assertFalse(value['deviceOpenAttempted'])

    def test_device_metadata_distinguishes_permission_group_and_type_without_opening_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            info = SimpleNamespace(st_mode=stat.S_IFCHR | 0o660, st_uid=0, st_gid=105)
            with patch.object(Path, 'lstat', return_value=info), patch.object(subject.os, 'geteuid', return_value=1001), \
                    patch.object(subject.os, 'getegid', return_value=1001), patch.object(subject.os, 'getgroups', return_value=[1001]), \
                    patch.object(subject.os, 'access', return_value=False) as access:
                value = subject.observe(root / 'device', root / 'cpu', root / 'modules')
            self.assertEqual(access.call_count, 2)
            self.assertEqual(value['device']['permissionMode'], '0660')
            self.assertTrue(value['device']['characterDevice'])
            self.assertFalse(value['device']['effectiveGroupMatches'])
            self.assertFalse(value['device']['readable'])
            self.assertFalse(value['deviceOpenAttempted'])
            self.assertFalse(value['policyChanged'])

    def test_device_symlink_is_reported_but_not_followed_or_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'device').symlink_to(p / 'missing-target')
            with patch.object(subject.os, 'access') as access:
                value = subject.observe(p / 'device', p / 'cpu', p / 'modules')
            access.assert_not_called()
            self.assertTrue(value['device']['symlink'])
            self.assertIsNone(value['device']['readable'])

    def test_kernel_content_exports_only_closed_flags_and_parameter_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'cpu').write_bytes(b'processor serial : PRIVATE\nflags : vmx sse PRIVATE\n')
            for module, raw in (('kvm_intel', b'Y\n'), ('kvm_amd', b'PRIVATE\n')):
                path = p / 'modules' / module / 'parameters/nested'
                path.parent.mkdir(parents=True)
                path.write_bytes(raw)
            value = subject.observe(p / 'absent', p / 'cpu', p / 'modules')
            self.assertTrue(value['vmxExposed'])
            self.assertFalse(value['svmExposed'])
            self.assertEqual(value['nestedParameters'], {'kvm_intel': 'ENABLED', 'kvm_amd': 'OTHER_VALUE'})
            self.assertNotIn('PRIVATE', json.dumps(value))
            self.assertFalse(value['artQualified'])

    def test_denial_symlink_oversize_and_unknown_errors_remain_distinct(self):
        self.assertEqual(subject.error_kind(OSError(errno.EACCES, 'PRIVATE')), 'DENIED')
        self.assertEqual(subject.error_kind(OSError(errno.EIO, 'PRIVATE')), 'OTHER_ERROR')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'large').write_bytes(b'a' * 65)
            (p / 'link').symlink_to(p / 'large')
            self.assertEqual(subject.read_bounded(p / 'large', 64), ('TOO_LARGE', None))
            self.assertEqual(subject.read_bounded(p / 'link', 64), ('SYMLINK', None))

    def test_observer_has_no_mutation_or_admission_path_and_workflow_keeps_original_gate(self):
        source = (ROOT / 'scripts/diagnostics/kvm-environment.py').read_text()
        for forbidden in ('os.setgroups(', 'os.setuid(', 'os.chmod(', 'setfacl', 'modprobe', 'ioctl(', 'subprocess.'):
            self.assertNotIn(forbidden, source)
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        self.assertIn("if: ${{ matrix.lane == 'android-art' }}", workflow)
        self.assertIn('python3 scripts/diagnostics/kvm-environment.py', workflow)
        gate = (ROOT / 'scripts/run-rpc-qualification.py').read_text()
        self.assertIn('Existing KVM access is required; no policy change is authorized', gate)
        self.assertIn('self.kvm == self.kvm_snapshot("kvm-policy-after")', gate)

    def test_alternate_runner_probe_is_explicit_read_only_and_not_an_art_substitute(self):
        workflow = (ROOT / '.github/workflows/rpc-qualification.yml').read_text()
        original, probe = workflow.split('\n  alternate-kvm-observation:\n')
        self.assertIn('"lane":"android-art","os":"ubuntu-24.04"', original)
        self.assertIn('runs-on: ubuntu-22.04', probe)
        self.assertIn("contains(github.event.head_commit.message, '[rpc-kvm-probe]')", probe)
        self.assertIn("github.ref == 'refs/heads/work/rpc-lan-20260927-054728-8b1b11da'", probe)
        self.assertIn('timeout-minutes: 5', probe)
        self.assertIn('fetch-tags: false', probe)
        self.assertIn('persist-credentials: false', probe)
        self.assertIn('git fetch --no-tags --unshallow', probe)
        self.assertIn('python3 -B scripts/diagnostics/kvm-environment.py', probe)
        for forbidden in ('sudo ', 'chmod ', 'setfacl ', 'usermod ', 'modprobe ', 'gradlew',
                          'sdkmanager', 'run-android-art-smoke', 'run-rpc-qualification.py', 'cancel-in-progress: true'):
            self.assertNotIn(forbidden, probe)


if __name__ == '__main__':
    unittest.main(verbosity=2)
