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
        self.assertIn("expected_role='macos-x64'", text)
        self.assertIn('host_role() == expected_role', text)
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

    def test_explicit_apple_role_must_match_actual_native_host_and_never_defaults_to_arm(self):
        for requested, actual in (('macos-arm64', 'macos-x64'), ('macos-x64', 'macos-arm64'),
                                  ('linux-x64', 'linux-x64'), ('macos', 'macos-arm64')):
            with self.subTest(requested=requested, actual=actual), patch.object(sys, 'platform', 'darwin'), \
                    patch.object(d, 'host_role', return_value=actual), patch.object(d.ctypes, 'CDLL') as load:
                with self.assertRaises(ValueError):
                    d.NativeSnapshot(expected_role=requested)
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


class CpuIntervalControls(unittest.TestCase):
    def fixture(self):
        native = Diagnostics().fixture()
        native.timebase.return_value = (3, 2)
        native.task.side_effect = [SimpleNamespace(totalUser=100, totalSystem=200),
                                   SimpleNamespace(totalUser=400, totalSystem=800)]
        return native

    def measure(self, native=None):
        clock = [0]
        def now():
            clock[0] += 1000
            return clock[0]
        def sleep(seconds):
            self.assertEqual(seconds, 10)
            clock[0] += seconds * 10 ** 9
        return d.cpu_interval(native or self.fixture(), now, sleep)

    def test_same_lifetime_counters_are_converted_with_actual_timebase_not_host_assumptions(self):
        result = self.measure()
        self.assertEqual(result['scope'], d.CPU_SCOPE)
        self.assertEqual(result['matchedCount'], 1)
        row = result['roles']['ReportCrash']
        self.assertEqual((row['count'], row['userNanos'], row['systemNanos']), (1, 450, 900))
        self.assertGreaterEqual(row['minIntervalNanos'], 10 ** 10)
        self.assertEqual(d.cpu_interval_observation(json.dumps(result).encode()), result)
        self.assertNotIn('pid', json.dumps(result))

    def test_pid_reuse_uid_change_name_change_or_unobserved_lifetime_is_not_attributed(self):
        for field, changed in (('startsec', 18), ('startusec', 13), ('uid', 502), ('name', b'another-private-name')):
            native = self.fixture()
            first = native.bsd.return_value
            last = SimpleNamespace(**{**vars(first), field: changed})
            native.bsd.side_effect = [first, first, last, last]
            result = self.measure(native)
            self.assertEqual(result['matchedCount'], 0)
            self.assertEqual((result['unmatchedBeforeCount'], result['unmatchedAfterCount']), (1, 1))
            self.assertEqual(result['roles'], {})
            self.assertNotIn('another-private-name', json.dumps(result))

    def test_normal_process_state_transition_does_not_falsely_reset_lifetime_cpu(self):
        native = self.fixture()
        first = native.bsd.return_value
        last = SimpleNamespace(**{**vars(first), 'status': 2})
        native.bsd.side_effect = [first, first, last, last]
        self.assertEqual(self.measure(native)['matchedCount'], 1)

    def test_unreadable_or_inconsistent_reads_stay_explicit_without_an_exit_claim(self):
        for field in ('denied', 'changed', 'wrong-pid'):
            native = self.fixture()
            first = native.bsd.return_value
            changed = SimpleNamespace(**{**vars(first), 'startsec': 18})
            if field == 'denied':
                native.bsd.side_effect = [first, first, None]
            elif field == 'wrong-pid':
                wrong = SimpleNamespace(**{**vars(first), 'pid': 32})
                native.bsd.side_effect = [first, first, wrong, wrong]
            else:
                native.bsd.side_effect = [first, first, first, changed]
            value = self.measure(native)
            self.assertEqual(value['matchedCount'], 0)
            self.assertEqual(value['unmatchedBeforeCount'], 1)
            self.assertEqual(value['after']['unreadableCount' if field == 'denied' else 'changedCount'], 1)
            self.assertNotIn('cleanupVerified', value)

    def test_counter_regression_or_role_change_is_not_reported_as_zero_cpu(self):
        for reset in ('user', 'system', 'role'):
            native = self.fixture()
            if reset == 'role':
                native.path.side_effect = ['ReportCrash', 'java']
            else:
                native.task.side_effect = [SimpleNamespace(totalUser=100, totalSystem=200),
                    SimpleNamespace(totalUser=99 if reset == 'user' else 101,
                                    totalSystem=199 if reset == 'system' else 201)]
            value = self.measure(native)
            self.assertEqual(value['counterResetCount'], 1)
            self.assertEqual(value['matchedCount'], 0)
            self.assertEqual(value['roles'], {})

    def test_unrelated_names_are_aggregated_but_fixed_tool_roles_remain_interpretable(self):
        for name, role in (('PRIVATE_SECRET', 'other-readable'), ('python3.14', 'python'), ('java', 'java')):
            native = self.fixture()
            native.path.return_value = name
            value = self.measure(native)
            self.assertEqual(set(value['roles']), {role})
            self.assertNotIn('PRIVATE_SECRET', json.dumps(value))

    def test_timebase_refusal_or_zero_denominator_stops_instead_of_guessing_units(self):
        for code, numerator, denominator in ((0, 0, 1), (0, 1, 0), (5, 1, 1), (0, 3, 2)):
            native = d.NativeSnapshot.__new__(d.NativeSnapshot)
            native.system = Mock()
            def read(pointer):
                pointer._obj.numerator, pointer._obj.denominator = numerator, denominator
                return code
            native.system.mach_timebase_info.side_effect = read
            if code == 0 and numerator > 0 and denominator > 0:
                self.assertEqual(native.timebase(), (numerator, denominator))
            else:
                with self.assertRaises(ValueError):
                    native.timebase()

    def test_framework_python_executable_is_not_hidden_in_unclassified_cpu(self):
        for name in ('Python', 'Python3', 'python', 'python3', 'python3.14'):
            native = self.fixture()
            native.path.return_value = name
            value = self.measure(native)
            self.assertEqual(set(value['roles']), {'python'})
            self.assertEqual(value['roles']['python']['userNanos'], 450)
        for name in ('PRIVATE_SECRET', 'Python-private', 'python3.14-private'):
            native = self.fixture()
            native.path.return_value = name
            value = self.measure(native)
            self.assertEqual(set(value['roles']), {'other-readable'})
            self.assertNotIn(name, json.dumps(value))

    def test_closed_interval_schema_preserves_churn_privacy_and_no_authority(self):
        base = self.measure()
        for change in (dict(pid=31), dict(unprivileged=False), dict(cleanupVerified=True),
                       dict(waitNanos=0), dict(matchedCount=2), dict(counterResetCount=True),
                       dict(roles={'PRIVATE_SECRET': {}}), dict(timebase=dict(numerator=1, denominator=0))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.validate_cpu_interval({**base, **change})
        for change in (dict(userNanos=-1), dict(userNanos=True), dict(count=2),
                       dict(minIntervalNanos=0), dict(path='/PRIVATE_SECRET')):
            value = copy.deepcopy(base)
            value['roles']['ReportCrash'].update(change)
            with self.assertRaises(ValueError):
                d.validate_cpu_interval(value)
        for raw in (b'{}', b'{"schema":1,"schema":1}', b'x' * (d.MAX_BYTES + 1)):
            with self.assertRaises(ValueError):
                d.cpu_interval_observation(raw)

    def test_public_collector_revalidates_the_exact_cpu_observation(self):
        base = self.measure()
        row = product.intel_environment_observation('nativeCpuInterval', json.dumps(base).encode())
        summary = {'intelEnvironment': {'after': {'nativeCpuInterval': row}}}
        self.assertEqual(product.validate(summary, ROOT, set()), summary)
        with self.assertRaises(ValueError):
            product.validate_intel_environment('nativeCpuInterval', {**row, 'pid': 31})


if __name__ == '__main__':
    unittest.main(verbosity=2)
