#!/usr/bin/env python3
"""Offline controls only: no simulator, SDK, host commands, or product tests."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('intel_diagnostic', Path(__file__).parents[1] / 'diagnose-intel-simulator.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class Controls(unittest.TestCase):
    def setUp(self):
        d.CANCELLED.clear()

    def test_fixed_scope_and_commands(self):
        self.assertEqual(d.INVENTORY, ['/usr/bin/xcrun', 'simctl', 'list', '--json', 'runtimes'])
        self.assertEqual(d.INVENTORY_SECONDS, 600)
        self.assertEqual(d.SAMPLE_AT, (90, 180))
        self.assertEqual(d.owner.simulator.SECONDS, 120)
        commands = d.sample_commands(123)
        self.assertEqual(commands[0][1], ['/usr/bin/sample', '123', '1', '1', '-mayDie', '-file', '/dev/stdout'])
        self.assertEqual(commands[1][1], ['/bin/ps', '-p', '123', '-o', 'pid=,ppid=,pgid=,sess=,stat=,comm='])
        for pid in (True, 0, 1, '123'):
            with self.assertRaises(RuntimeError):
                d.sample_commands(pid)

    def test_capture_overflow_keeps_draining_to_eof(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b'0123456789')
        os.close(write_fd)
        with os.fdopen(read_fd, 'rb') as stream:
            capture = d.Capture.__new__(d.Capture)
            capture.process = SimpleNamespace(stdout=stream)
            capture.stop = threading.Event()
            capture.overflow = threading.Event()
            capture.read_error = threading.Event()
            capture.done = {'stdout': threading.Event()}
            capture.eof = {'stdout': threading.Event()}
            capture.buffers = {'stdout': bytearray()}
            with patch.object(d, 'STREAM_LIMITS', {'stdout': 4}):
                capture.drain('stdout')
            self.assertEqual(capture.buffers['stdout'], b'0123')
            self.assertTrue(capture.overflow.is_set())
            self.assertTrue(capture.eof['stdout'].is_set())
            self.assertFalse(capture.read_error.is_set())

    def test_real_concurrent_pipe_drains_are_capped_without_deadlock(self):
        reads, writes = {}, {}
        for name in ('stdout', 'stderr'):
            read_fd, writes[name] = os.pipe()
            reads[name] = os.fdopen(read_fd, 'rb')
        process = SimpleNamespace(**reads, returncode=0)
        def writer(name):
            try:
                data = b'x' * 65536
                while data:
                    data = data[os.write(writes[name], data):]
            finally:
                os.close(writes[name])
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(d.subprocess, 'Popen', return_value=process) as launch, \
                patch.object(d.owner, 'terminate_process', return_value=True), \
                patch.object(d, 'STREAM_LIMITS', {'stdout': 4096, 'stderr': 1024}):
            capture = d.Capture('pipes', ['/fixed/offline-fixture'], 1, Path(directory))
            writers = [threading.Thread(target=writer, args=(name,)) for name in writes]
            for thread in writers:
                thread.start()
            try:
                self.assertTrue(all(event.wait(2) for event in capture.done.values()))
            finally:
                row = capture.close('OUTPUT_LIMIT')
                for thread in writers:
                    thread.join(timeout=2)
            self.assertFalse(any(thread.is_alive() for thread in writers))
            self.assertTrue(row['capturesClosed'] and row['streamsReachedEof'])
            self.assertTrue(row['outputLimitExceeded'])
            self.assertEqual(row['stdout']['bytes'], 4096)
            self.assertEqual(row['stderr']['bytes'], 1024)
            self.assertFalse(d.observed(row))
            self.assertTrue(launch.call_args.kwargs['start_new_session'])
            self.assertEqual(launch.call_args.kwargs['stdin'], d.subprocess.DEVNULL)

    def test_original_poll_is_forbidden_while_sampling(self):
        capture = d.Capture.__new__(d.Capture)
        capture.overflow = threading.Event()
        capture.read_error = threading.Event()
        capture.deadline = 99
        capture.done = {'stdout': threading.Event()}
        capture.process = SimpleNamespace(poll=lambda: self.fail('reaped PID-targeted original'))
        with patch.object(d.time, 'monotonic', return_value=1):
            self.assertIsNone(capture.reason(allow_reap=False))

    def test_one_inventory_parallel_samples_and_retirement_order(self):
        clock, records, active = [0.0], [], set()
        test = self
        class Fake:
            def __init__(self, label, argv, seconds):
                self.label, self.began, self.deadline = label, clock[0], clock[0] + seconds
                self.process = SimpleNamespace(pid=123, poll=self.poll, returncode=0)
                self.row = None
                records.append(('launch', label, tuple(argv), seconds))
                if label != 'inventory':
                    active.add(label)
            def poll(self):
                if self.label == 'inventory':
                    test.assertFalse(active, 'original reaped while sampler active')
                return None
            def reason(self, allow_reap=True):
                if self.label == 'inventory':
                    if allow_reap:
                        self.poll()
                    return 'TIMEOUT' if clock[0] >= 600 else None
                return 'EXITED' if clock[0] >= self.began + .1 else None
            def close(self, reason):
                if self.label == 'inventory':
                    test.assertFalse(active)
                else:
                    active.remove(self.label)
                records.append(('close', self.label, reason))
                return {'label': self.label, 'reason': reason, 'ownedGroupDrained': True, 'capturesClosed': True}
        with patch.object(d, 'Capture', Fake), patch.object(d.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(d.time, 'sleep', side_effect=lambda _: clock.__setitem__(0, clock[0] + 1)):
            row, samplers = d.inventory_observation()
        self.assertEqual(row['reason'], 'TIMEOUT')
        self.assertEqual(len(samplers), 4)
        self.assertEqual(sum(r[0] == 'launch' and r[1] == 'inventory' for r in records), 1)
        self.assertEqual([r[1] for r in records if r[0] == 'launch'],
                         ['inventory', 'sample-90', 'process-90', 'sample-180', 'process-180'])
        self.assertEqual(records[-1], ('close', 'inventory', 'TIMEOUT'))

    def test_sampler_close_error_still_retires_original_and_others(self):
        clock, closed = [0.0], []
        class Fake:
            def __init__(self, label, argv, seconds):
                self.label, self.began = label, clock[0]
                self.process = SimpleNamespace(pid=123, poll=lambda: None, returncode=0)
            def reason(self, allow_reap=True):
                if self.label == 'inventory' and clock[0] > 90:
                    return 'CANCELLED'
                return None
            def close(self, reason):
                closed.append(self.label)
                if self.label == 'sample-90':
                    raise OSError('private arbitrary detail')
                return {'label': self.label}
        with patch.object(d, 'Capture', Fake), patch.object(d.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(d.time, 'sleep', side_effect=lambda _: clock.__setitem__(0, clock[0] + 1)):
            with self.assertRaisesRegex(RuntimeError, '^DIAGNOSTIC_RETIREMENT_FAILED$'):
                d.inventory_observation()
        self.assertEqual(closed, ['sample-90', 'process-90', 'inventory'])

    def test_primary_error_is_preserved_if_retirement_also_raises(self):
        closed = []
        class Fake:
            def __init__(self, label, argv, seconds):
                self.label, self.began = label, 0
            def reason(self, allow_reap=True):
                raise ValueError('ORIGINAL_FAILURE')
            def close(self, reason):
                closed.append((self.label, reason))
                raise OSError('SECONDARY_CLEANUP_FAILURE')
        with patch.object(d, 'Capture', Fake):
            with self.assertRaisesRegex(ValueError, '^ORIGINAL_FAILURE$') as error:
                d.inventory_observation()
        self.assertEqual(closed, [('inventory', 'INTERRUPTED')])
        self.assertEqual(error.exception.__notes__, ['DIAGNOSTIC_RETIREMENT_FAILED'])

    def test_uncertain_group_stops_new_targets_even_with_direct_exit(self):
        clock, launched, closed = [0.0], [], []
        class Fake:
            def __init__(self, label, argv, seconds):
                self.label, self.began = label, clock[0]
                launched.append(label)
                self.process = SimpleNamespace(pid=123, returncode=0, poll=lambda: None)
            def reason(self, allow_reap=True):
                return 'EXITED' if self.label != 'inventory' else None
            def close(self, reason):
                closed.append(self.label)
                return {'label': self.label, 'ownedGroupDrained': False, 'capturesClosed': True}
        with patch.object(d, 'Capture', Fake), patch.object(d.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(d.time, 'sleep', side_effect=lambda _: clock.__setitem__(0, clock[0] + 90)):
            with self.assertRaisesRegex(RuntimeError, '^OBSERVER_RETIREMENT_UNKNOWN$'):
                d.inventory_observation()
        self.assertEqual(launched, ['inventory', 'sample-90', 'process-90'])
        self.assertEqual(closed[-1], 'inventory')

    def test_unconfirmed_direct_exit_retains_inventory_for_outer_cleanup(self):
        clock, closed, recoveries = [0.0], [], []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            class Fake:
                def __init__(self, label, argv, seconds):
                    self.label, self.began = label, clock[0]
                    self.directory = output / label
                    self.directory.mkdir()
                    self.process = SimpleNamespace(pid=123, returncode=None if label == 'sample-90' else 0,
                                                   poll=lambda: None, kill=self.kill, wait=self.wait)
                def kill(self):
                    recoveries.append('kill')
                def wait(self, timeout):
                    recoveries.append(timeout)
                    raise d.subprocess.TimeoutExpired('fixed-observer', timeout)
                def reason(self, allow_reap=True):
                    return 'EXITED' if self.label != 'inventory' else None
                def close(self, reason):
                    closed.append(self.label)
                    return {'label': self.label, 'ownedGroupDrained': False, 'capturesClosed': True}
            with patch.object(d, 'Capture', Fake), patch.object(d, 'OUTPUT', output), \
                    patch.object(d, 'OUTER_DEADLINE', 900), patch.object(d.CANCELLED, 'wait', return_value=True), \
                    patch.object(d.time, 'monotonic', side_effect=lambda: clock[0]), \
                    patch.object(d.time, 'sleep', side_effect=lambda _: clock.__setitem__(0, clock[0] + 90)):
                with self.assertRaisesRegex(RuntimeError, '^OBSERVER_DIRECT_EXIT_UNKNOWN$'):
                    d.inventory_observation()
            self.assertNotIn('inventory', closed)
            self.assertEqual(recoveries, ['kill', 5])
            handoff = json.loads((output / 'original-guard-handoff.json').read_text())
            self.assertFalse(handoff['inventoryLocallyReaped'])
            self.assertFalse(handoff['cleanupKnown'])

    def test_exceptional_handoff_wait_is_existing_bounded_event_only(self):
        process = SimpleNamespace(poll=lambda: self.fail('must not reap original'))
        original = SimpleNamespace(process=process)
        with tempfile.TemporaryDirectory() as directory, patch.object(d, 'OUTPUT', Path(directory)), \
                patch.object(d, 'OUTER_DEADLINE', 900), patch.object(d.time, 'monotonic', return_value=200), \
                patch.object(d.CANCELLED, 'wait', return_value=True) as wait:
            d.retain_original_until_outer_handoff(original)
            wait.assert_called_once_with(720)
            row = json.loads((Path(directory) / 'original-guard-handoff-end.json').read_text())
            self.assertTrue(row['outerCancellationObserved'])
            self.assertFalse(row['cleanupKnown'])
            self.assertFalse(row['pidHoldAfterInterpreterExitClaimed'])

    def test_success_requires_complete_original_streams_and_cleanup(self):
        row = {'reason': 'EXITED', 'exitCode': 0, 'ownedGroupDrained': True, 'capturesClosed': True,
               'streamsReachedEof': True, 'outputLimitExceeded': False, 'captureError': False}
        self.assertTrue(d.observed(row))
        for key, bad in [('reason', 'TIMEOUT'), ('exitCode', True), ('ownedGroupDrained', False),
                         ('capturesClosed', False), ('streamsReachedEof', False),
                         ('outputLimitExceeded', True), ('captureError', True)]:
            self.assertFalse(d.observed({**row, key: bad}), key)

    def test_retirement_uses_original_and_records_work_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = d.Capture.__new__(d.Capture)
            capture.label, capture.argv = 'inventory', d.INVENTORY
            capture.directory, capture.began, capture.started_utc = Path(directory), 10, '2026-10-20T00:00:00Z'
            capture.row = None
            capture.threads = []
            capture.stop, capture.overflow, capture.read_error = threading.Event(), threading.Event(), threading.Event()
            capture.eof = {'stdout': threading.Event(), 'stderr': threading.Event()}
            for event in capture.eof.values():
                event.set()
            capture.process = SimpleNamespace(returncode=0, stdout=io.BytesIO(), stderr=io.BytesIO())
            capture.buffers = {'stdout': bytearray(b'{}'), 'stderr': bytearray()}
            with patch.object(d.owner, 'terminate_process', return_value=True) as retire, \
                    patch.object(d.time, 'monotonic', side_effect=[129, 131]):
                row = capture.close('EXITED')
            retire.assert_called_once_with(capture.process)
            self.assertEqual(row['workElapsedSeconds'], 119)
            self.assertEqual(row['elapsedSeconds'], 121)
            self.assertTrue(d.observed(row))
            self.assertEqual(json.loads((Path(directory) / 'result.json').read_text()), row)


if __name__ == '__main__':
    unittest.main()
