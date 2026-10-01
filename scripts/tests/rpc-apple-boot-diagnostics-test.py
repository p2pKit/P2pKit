#!/usr/bin/env python3
"""Offline observation/privacy controls, never native Apple readiness evidence."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_boot_diagnostics as boot
import rpc_phone_diagnostics as phone


class BootControls(unittest.TestCase):
    def setUp(self):
        self.time = 0
        self.native = Mock()
        self.native.timebase.return_value = (1, 1)
        self.native.cpu.return_value = dict(user=1, system=2, idle=3, nice=0)
        self.native.pids.return_value = [321]
        self.native.bsd.return_value = SimpleNamespace(pid=321, startsec=12, startusec=0, uid=501, name=b'Python')
        self.native.path.return_value = 'Python'
        self.native.task.side_effect = lambda _: SimpleNamespace(totalUser=self.time // 2, totalSystem=self.time // 4)
        self.observer = boot.BootObserver('macos-arm64', native=self.native, now=lambda: self.time)

    def observation(self):
        self.observer.start()
        self.time = 10 * 10 ** 9
        self.observer.sample()
        self.time = 12 * 10 ** 9
        return self.observer.finish()

    def test_sampling_does_not_wait_create_processes_or_claim_full_coverage(self):
        self.observer.start()
        self.time = boot.PERIOD - 1
        self.observer.sample()
        self.assertEqual(self.native.pids.call_count, 1)
        early = self.observer.finish()
        self.assertEqual(early['intervals'], [])
        self.assertEqual(early['unobservedTailNanos'], self.time)
        self.assertFalse(early['executionAdmitted'])
        text = (ROOT / 'scripts/rpc_apple_boot_diagnostics.py').read_text()
        for forbidden in ('time.sleep(', 'threading', 'subprocess', 'os.kill', 'task_name_for_pid', 'sudo'):
            self.assertNotIn(forbidden, text)

    def test_closed_cpu_intervals_keep_tail_and_no_process_keys_or_private_names(self):
        actual = self.observation()
        self.assertEqual(len(actual['intervals']), 1)
        self.assertEqual(actual['unobservedTailNanos'], 2 * 10 ** 9)
        row = actual['intervals'][0]['cpu']['roles']['python']
        self.assertEqual(row['userNanos'], 5 * 10 ** 9)
        self.assertEqual(row['systemNanos'], 25 * 10 ** 8)
        self.assertEqual(self.native.pids.call_count, 2)
        self.assertNotIn('321', json.dumps(actual))
        self.assertNotIn('uid', json.dumps(actual))
        self.assertNotIn('records', json.dumps(actual))

    def test_sampling_errors_and_port_release_errors_are_not_suppressed(self):
        self.observer.start()
        self.time = boot.PERIOD
        self.native.cpu.side_effect = ValueError('native observation failed')
        with self.assertRaises(ValueError):
            self.observer.sample()
        self.assertEqual(self.observer.intervals, [])

    def test_invalid_roles_and_restarted_observers_are_rejected(self):
        for role in ('linux-x64', 'arm64', '', True):
            with self.assertRaises(ValueError):
                boot.BootObserver(role, native=self.native)
        with patch.object(boot.processes, 'NativeSnapshot', return_value=self.native) as create:
            boot.BootObserver('macos-arm64')
            create.assert_called_once_with(expected_role='macos-arm64')
        with self.assertRaises(ValueError):
            self.observer.sample()
        self.observer.start()
        with self.assertRaises(ValueError):
            self.observer.start()

    def test_unknown_fields_private_roles_inconsistent_times_and_forged_admission_are_refused(self):
        actual = self.observation()
        for change in (dict(executionAdmitted=True), dict(pid=321), dict(nativeRole='linux-x64'),
                       dict(unobservedTailNanos=0), dict(elapsedNanos=True)):
            with self.assertRaises(ValueError):
                boot.validate({**actual, **change})
        for field, value in (('roles', {'PRIVATE_SECRET': {}}), ('matchedCount', 2), ('cleanupVerified', True)):
            bad = copy.deepcopy(actual)
            bad['intervals'][0]['cpu'][field] = value
            with self.assertRaises(ValueError):
                boot.validate(bad)

    def test_phone_export_only_accepts_original_boot_observation_and_cannot_grant_readiness(self):
        actual = self.observation()
        private = dict(status='FAIL', commands=[dict(label='boot-readiness', timeoutSeconds=120,
            exitCode=None, processObservation=actual)], errors=[], **dict.fromkeys(phone.FLAGS, False))
        public = phone.observe(private, {}, ROOT)
        self.assertEqual(public['bootProcesses'], actual)
        self.assertFalse(public['executionAdmitted'])
        self.assertEqual(public['reportedStatus'], 'FAIL')
        private['commands'][0]['label'] = 'framework-producer'
        private['commands'][0]['timeoutSeconds'] = 3900
        with self.assertRaises(RuntimeError):
            phone.observe(private, {}, ROOT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
