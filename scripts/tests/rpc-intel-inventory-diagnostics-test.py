#!/usr/bin/env python3
"""Scripted CPU/privacy/command controls, not native Intel or simulator evidence."""
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
import rpc_intel_inventory_diagnostics as probe


class InventoryControls(unittest.TestCase):
    def setUp(self):
        self.time = 0
        self.native = Mock()
        self.native.timebase.return_value = (1, 1)
        self.native.cpu.return_value = dict(user=1, system=2, idle=3, nice=0)
        self.native.pids.return_value = [321]
        self.native.bsd.return_value = SimpleNamespace(pid=321, startsec=12, startusec=0, uid=501, name=b'simctl')
        self.native.path.return_value = 'simctl'
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
        return probe.run_inventory(native=self.native, now=lambda: self.time, sleep=self.sleep,
                                   launch=self.launch, emit=self.rows.append)

    def test_one_original_command_inherits_output_and_has_no_retry_or_signal(self):
        self.assertEqual(self.execute(), 0)
        self.launch.assert_called_once_with(['/usr/bin/xcrun', 'simctl', 'list', '--json', 'runtimes'],
                                            stdin=probe.subprocess.DEVNULL)
        self.child.wait.assert_called_once_with()
        self.child.kill.assert_not_called()
        self.child.terminate.assert_not_called()
        self.assertEqual(len(self.rows), 3)
        self.assertTrue(all(not row['executionAdmitted'] for row in self.rows))
        self.assertEqual(self.rows[-1]['intervals'][0]['cpu']['roles']['simctl']['userNanos'], 5 * 10 ** 9)
        self.assertEqual(self.rows[-1]['unobservedTailNanos'], 2 * 10 ** 9)

    def test_failed_tool_is_returned_and_not_called_again(self):
        self.child.wait.return_value = 7
        self.assertEqual(self.execute(), 7)
        self.assertEqual(self.rows[-1]['childExitCode'], 7)
        self.assertEqual(self.launch.call_count, 1)

    def test_native_observation_error_propagates_without_signalling_or_promoting_child(self):
        self.native.task.side_effect = [SimpleNamespace(totalUser=0, totalSystem=0), ValueError('read failure')]
        with self.assertRaisesRegex(ValueError, 'read failure'):
            self.execute()
        self.assertEqual(len(self.rows), 1)
        self.assertIsNone(self.rows[0]['childExitCode'])
        self.child.kill.assert_not_called()
        self.child.terminate.assert_not_called()

    def test_native_role_admission_precedes_child_and_cannot_be_faked_by_environment(self):
        with patch.object(probe.processes, 'NativeSnapshot', side_effect=ValueError('native denied')) as create:
            with self.assertRaisesRegex(ValueError, 'native denied'):
                probe.run_inventory(launch=self.launch)
        create.assert_called_once_with(expected_role='macos-x64')
        self.launch.assert_not_called()

    def test_only_explicit_runtime_scope_can_start_observations(self):
        env = dict(RPC_INTEL_INVESTIGATION='runtime', RPC_APPLE_LANE='apple-x64', RPC_QUALIFY_REQUESTED='true',
                   RPC_APPLE_TERMINAL_CONTEXT='true', P2PKIT_AUDIT_OWNERSHIP_CHAIN='fixture-not-native-evidence',
                   DEVELOPER_DIR='/Applications/Xcode_26.3.app/Contents/Developer')
        probe.admit(env)
        for key in env:
            with self.assertRaises(ValueError):
                probe.admit({**env, key: ''})
        for changes in (dict(RPC_APPLE_LANE='apple-arm64'), dict(RPC_INTEL_INVESTIGATION='native')):
            with self.assertRaises(ValueError):
                probe.admit({**env, **changes})

    def test_partial_and_complete_frames_are_consistent_closed_numeric_records(self):
        self.execute()
        encode = lambda rows: ('PRIVATE_TOOL_TEXT\n' + '\n'.join(probe.PREFIX + json.dumps(row) for row in rows)).encode()
        self.assertEqual(probe.observation(encode(self.rows)), self.rows[-1])
        self.assertEqual(probe.observation(encode(self.rows[:-1])), self.rows[-2])
        self.assertIsNone(probe.observation(b'no observations\n'))
        self.assertNotIn('321', json.dumps(self.rows))
        self.assertNotIn('PRIVATE_TOOL_TEXT', json.dumps(probe.observation(encode(self.rows))))
        for changes in (dict(executionAdmitted=True), dict(scope='COLD_BOOT'), dict(pid=321),
                        dict(childExitCode=True), dict(childExitCode=256), dict(unobservedTailNanos=0)):
            with self.assertRaises(ValueError):
                probe.observation(encode([{**self.rows[-1], **changes}]))
        for rows in (self.rows + [self.rows[-1]], self.rows[::-1], [self.rows[1], self.rows[0]], [self.rows[0]] * 35):
            with self.assertRaises(ValueError):
                probe.observation(encode(rows))
        bad = copy.deepcopy(self.rows[-1])
        bad['intervals'][0]['cpu']['roles']['PRIVATE'] = bad['intervals'][0]['cpu']['roles'].pop('simctl')
        with self.assertRaises(ValueError):
            probe.observation(encode([bad]))
        with self.assertRaises(ValueError):
            probe.observation((probe.PREFIX + '{"schema":1,"schema":1}').encode())

    def test_no_hidden_second_inventory_boot_priority_or_ownership_override(self):
        text = (ROOT / 'scripts/rpc_intel_inventory_diagnostics.py').read_text()
        for forbidden in ('bootstatus', 'dyld_shared_cache', 'os.kill(', '.terminate(', '.kill(', 'setpriority',
                          'sudo', 'signal.signal', 'task_name_for_pid', 'os.environ['):
            self.assertNotIn(forbidden, text)
        self.assertEqual(text.count('child = launch('), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
