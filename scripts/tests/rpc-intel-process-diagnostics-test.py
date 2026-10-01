#!/usr/bin/env python3
"""Offline read-API/schema controls, not native Apple execution."""
import copy
import ctypes
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_intel_process_diagnostics as d
import rpc_product_diagnostics as product


class Diagnostics(unittest.TestCase):
    def fixture(self):
        native = Mock()
        native.cpu.return_value = dict(user=1, system=2, idle=3, nice=4)
        native.pids.return_value = [31]
        native.bsd.return_value = SimpleNamespace(pid=31, startsec=17, startusec=12, uid=501,
                                                 status=3, name=b'ReportCrash')
        native.path.return_value = 'ReportCrash'
        native.task.return_value = SimpleNamespace(resident=1024, threadCount=2, runningThreads=1)
        return native

    def snapshot(self, native=None):
        return d.snapshot(native or self.fixture(), Mock(side_effect=[0, 10]), uid=501)

    def test_native_layout_and_fixed_apis_do_not_execute_set_id_tools_or_signal(self):
        self.assertEqual(ctypes.sizeof(d.TaskInfo), 96)
        self.assertEqual(ctypes.sizeof(d.DarwinBsdInfo), 136)
        text = (ROOT / 'scripts/rpc_intel_process_diagnostics.py').read_text()
        for forbidden in ('subprocess.', 'os.kill(', 'proc_signal', 'task_name_for_pid', 'KERN_PROCARGS',
                          'getattr(self.proc, name)(', 'sudo', 'chmod', 'setuid('):
            self.assertNotIn(forbidden, text)
        self.assertIn("host_role() == 'macos-x64'", text)
        self.assertIn('P2PKIT_AUDIT_OWNERSHIP_CHAIN', text)

    def test_wrong_host_or_root_cannot_initialize_native_probe(self):
        for platform, host, uid in (('linux', 'linux-x64', 501), ('darwin', 'macos-arm64', 501),
                                    ('darwin', 'macos-x64', 0)):
            with self.subTest(platform=platform, host=host, uid=uid), patch.object(sys, 'platform', platform), \
                    patch.object(d, 'host_role', return_value=host), patch.object(d.os, 'getuid', return_value=uid), \
                    patch.object(d.os, 'geteuid', return_value=uid), patch.object(d.ctypes, 'CDLL') as load:
                with self.assertRaises(ValueError):
                    d.NativeSnapshot()
                load.assert_not_called()

    def test_host_port_always_deallocated_and_cleanup_errors_propagate(self):
        for success, release in ((True, 0), (False, 0), (True, 5)):
            native = d.NativeSnapshot.__new__(d.NativeSnapshot)
            native.self_port = 9
            native.system = Mock()
            native.system.mach_host_self.return_value = 12
            native.system.host_statistics.return_value = 0 if success else 5
            native.system.mach_port_deallocate.return_value = release
            if success and release == 0:
                self.assertEqual(native.cpu(), dict(user=0, system=0, idle=0, nice=0))
            else:
                with self.assertRaises(ValueError):
                    native.cpu()
            native.system.mach_port_deallocate.assert_called_once_with(9, 12)

    def test_aggregates_fixed_roles_without_ids_paths_or_unrelated_names(self):
        native = self.fixture()
        native.pids.return_value = [31, 32]
        native.path.side_effect = ['ReportCrash', 'PRIVATE_SECRET']
        value = self.snapshot(native)
        self.assertEqual(value['censusCount'], 2)
        self.assertEqual(value['otherRoleCount'], 1)
        self.assertEqual(value['observedCount'], 1)
        self.assertEqual(value['roles']['ReportCrash'], dict(count=1, residentBytes=1024, threads=2,
            runningThreads=1, running=0, sleeping=1, other=0, sameUid=1, rootUid=0, otherUid=0))
        self.assertNotIn('PRIVATE_SECRET', json.dumps(value))
        self.assertNotIn('pid', json.dumps(value))
        self.assertEqual(d.observation(json.dumps(value).encode()), value)

    def test_denied_disappearing_or_changed_process_is_not_counted_as_cleaned_up(self):
        for change, key in ((lambda n: setattr(n.bsd, 'return_value', None), 'unreadableCount'),
                            (lambda n: setattr(n.task, 'return_value', None), 'unreadableCount'),
                            (lambda n: setattr(n.path, 'return_value', None), 'unreadableCount'),
                            (lambda n: setattr(n.bsd, 'side_effect', [n.bsd.return_value,
                                SimpleNamespace(pid=31, startsec=18, startusec=12, uid=501,
                                                status=3, name=b'ReportCrash')]), 'changedCount')):
            native = self.fixture()
            change(native)
            value = self.snapshot(native)
            self.assertEqual(value[key], 1)
            self.assertEqual(value['observedCount'], 0)
            self.assertEqual(value['roles'], {})
            self.assertNotIn('cleanupVerified', value)

    def test_invalid_or_private_fields_and_forged_authority_are_rejected(self):
        base = self.snapshot()
        for change in (dict(pid=31), dict(unprivileged=False), dict(executionAdmitted=True), dict(elapsedNanos=-1),
                       dict(censusCount=2), dict(observedCount=True), dict(roles={'PRIVATE_SECRET': {}}),
                       dict(cpuTicks=dict(user=True, system=0, idle=0, nice=0))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.validate({**base, **change})
        for change in (dict(count=2), dict(residentBytes=0), dict(runningThreads=3), dict(sameUid=0),
                       dict(command='PRIVATE_SECRET')):
            value = copy.deepcopy(base)
            value['roles']['ReportCrash'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.validate(value)
        for raw in (b'{}', b'{"schema":1,"schema":1}', b'x' * (d.MAX_BYTES + 1)):
            with self.assertRaises(ValueError):
                d.observation(raw)

    def test_public_collector_validates_identical_closed_native_snapshot(self):
        value = self.snapshot()
        observed = product.intel_environment_observation('nativeProcesses', json.dumps(value).encode())
        self.assertEqual({k: v for k, v in observed.items() if k not in ('bytes', 'sha256')}, value)
        summary = {'intelEnvironment': {'before': {'nativeProcesses': observed}}}
        self.assertEqual(product.validate(summary, ROOT, set()), summary)
        with self.assertRaises(ValueError):
            product.validate_intel_environment('nativeProcesses', {**observed, 'path': '/PRIVATE_SECRET'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
