#!/usr/bin/env python3
"""Scripted observation controls only, never native Apple or readiness evidence."""
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
import rpc_intel_boot_diagnostics as probe

DEVICE = '11111111-2222-3333-4444-555555555555'


class BootObservationControls(unittest.TestCase):
    def setUp(self):
        self.time = 0
        self.native = Mock()
        self.native.timebase.return_value = (1, 1)
        self.native.cpu.return_value = dict(user=1, system=2, idle=3, nice=0)
        self.native.pids.return_value = [321]
        self.native.bsd.return_value = SimpleNamespace(pid=321, startsec=12, startusec=0, uid=501, name=b'DataMigrator')
        self.native.path.return_value = 'DataMigrator'
        self.native.task.side_effect = lambda _: SimpleNamespace(totalUser=self.time // 2, totalSystem=0)
        self.child = Mock()
        self.child.poll.side_effect = lambda: None if self.time < 12 * 10 ** 9 else self.child.wait.return_value
        self.child.wait.return_value = 0
        self.launch = Mock(return_value=self.child)
        self.rows = []

    def sleep(self, seconds):
        self.assertEqual(seconds, .1)
        self.time += 100_000_000

    def execute(self):
        return probe.run_boot(DEVICE, native=self.native, now=lambda: self.time, sleep=self.sleep,
                              launch=self.launch, emit=self.rows.append)

    def test_exact_single_original_boot_with_no_retry_signal_or_extra_readiness_time(self):
        self.assertEqual(self.execute(), 0)
        self.launch.assert_called_once_with(['/usr/bin/xcrun', 'simctl', 'bootstatus', DEVICE, '-b'],
                                            stdin=probe.subprocess.DEVNULL)
        self.child.wait.assert_called_once_with()
        self.child.kill.assert_not_called()
        self.child.terminate.assert_not_called()
        self.assertEqual(len(self.rows), 3)
        self.assertTrue(all(row['executionAdmitted'] is False for row in self.rows))
        self.assertEqual(self.rows[-1]['childExitCode'], 0)
        self.assertEqual(self.rows[-1]['elapsedNanos'], 12 * 10 ** 9)
        self.assertEqual(self.rows[-1]['unobservedTailNanos'], 2 * 10 ** 9)
        self.assertEqual(self.rows[-1]['intervals'][0]['cpu']['roles']['DataMigrator']['userNanos'], 5 * 10 ** 9)

    def test_nonzero_boot_exit_is_not_retried_or_promoted(self):
        self.child.wait.return_value = 7
        self.assertEqual(self.execute(), 7)
        self.assertEqual(self.rows[-1]['childExitCode'], 7)
        self.assertEqual(self.launch.call_count, 1)

    def test_native_read_failure_retains_partial_frame_and_propagates_for_native_owner_cleanup(self):
        self.native.task.side_effect = [SimpleNamespace(totalUser=0, totalSystem=0), ValueError('native read')]
        with self.assertRaisesRegex(ValueError, 'native read'):
            self.execute()
        self.assertEqual(len(self.rows), 1)
        self.assertIsNone(self.rows[0]['childExitCode'])
        self.child.kill.assert_not_called()
        self.child.terminate.assert_not_called()

    def test_actual_native_role_admission_precedes_launch(self):
        with patch.object(probe.processes, 'NativeSnapshot', side_effect=ValueError('native denied')) as create:
            with self.assertRaisesRegex(ValueError, 'native denied'):
                probe.run_boot(DEVICE, launch=self.launch)
        create.assert_called_once_with(expected_role='macos-x64')
        self.launch.assert_not_called()

    def environment(self):
        return dict(RPC_INTEL_INVESTIGATION='runtime', RPC_APPLE_LANE='apple-x64', RPC_QUALIFY_REQUESTED='true',
            RPC_APPLE_TERMINAL_CONTEXT='true', P2PKIT_AUDIT_OWNERSHIP_CHAIN='scripted-not-native',
            DEVELOPER_DIR='/Applications/Xcode_26.3.app/Contents/Developer', P2PKIT_SELECTED_SIMULATOR=DEVICE)

    def test_only_explicit_intel_runtime_context_and_exact_owned_simulator_are_accepted(self):
        env = self.environment()
        probe.admit(env, DEVICE)
        for key in env:
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                probe.admit({**env, key: ''}, DEVICE)
        for device in ('booted', 'all', '', DEVICE.lower() + 'x', '66666666-2222-3333-4444-555555555555'):
            with self.assertRaises(ValueError):
                probe.admit(env, device)
        for lane, mode in (('apple-arm64', 'runtime'), ('apple-x64', 'cold-boot'), ('apple-x64', 'native')):
            with self.assertRaises(ValueError):
                probe.admit({**env, 'RPC_APPLE_LANE': lane, 'RPC_INTEL_INVESTIGATION': mode}, DEVICE)

    def test_private_identity_and_tool_text_never_enter_the_closed_numeric_record(self):
        self.execute()
        encode = lambda rows: ('PRIVATE_TOOL_TEXT\n' + '\n'.join(probe.PREFIX + json.dumps(row) for row in rows)).encode()
        self.assertEqual(probe.observation(encode(self.rows)), self.rows[-1])
        self.assertEqual(probe.observation(encode(self.rows[:-1])), self.rows[-2])
        self.assertIsNone(probe.observation(b'no observation\n'))
        raw = json.dumps(self.rows)
        for private in (DEVICE, '321', 'PRIVATE_TOOL_TEXT'):
            self.assertNotIn(private, raw)
        for change in (dict(executionAdmitted=True), dict(scope='BOOTED'), dict(childExitCode=True),
                       dict(pid=321), dict(childExitCode=256), dict(unobservedTailNanos=0)):
            with self.assertRaises(ValueError):
                probe.observation(encode([{**self.rows[-1], **change}]))
        for rows in (self.rows + [self.rows[-1]], self.rows[::-1], [self.rows[0]] * 35):
            with self.assertRaises(ValueError):
                probe.observation(encode(rows))
        changed = copy.deepcopy(self.rows[-1])
        changed['intervals'][0]['cpu']['roles']['PRIVATE'] = changed['intervals'][0]['cpu']['roles'].pop('DataMigrator')
        with self.assertRaises(ValueError):
            probe.observation(encode([changed]))

    def test_duplicate_json_keys_oversized_frames_and_rewritten_intervals_are_rejected(self):
        self.execute()
        with self.assertRaises(ValueError):
            probe.observation((probe.PREFIX + '{"schema":1,"schema":1}').encode())
        with self.assertRaises(ValueError):
            probe.observation(b'x' * (probe.MAX_LOG + 1))
        changed = copy.deepcopy(self.rows[-1])
        changed['intervals'][0]['cpu']['roles']['DataMigrator']['userNanos'] += 1
        with self.assertRaises(ValueError):
            probe.observation(('\n'.join(probe.PREFIX + json.dumps(row) for row in [self.rows[1], changed])).encode())


if __name__ == '__main__':
    unittest.main()
