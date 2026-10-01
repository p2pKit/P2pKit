#!/usr/bin/env python3
"""Offline topology/placement controls; no Java, network, workload or capacity claim."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capacity_cpu_test_subject', ROOT / 'scripts/rpc_capacity_cpu.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def topology():
    return dict(onlineCpus=[0, 1, 2, 3], guestCores=[
        dict(package=0, core=0, cpus=[0, 2]), dict(package=0, core=1, cpus=[1, 3])])


def proof(role='host'):
    p = c.plan([0, 1, 2, 3], topology())
    return dict(schema=1, scope=c.SCOPE, role=role, plan=p, launcherBefore=[0, 1, 2, 3],
                launcherStarted=p[role + 'Cpus'], launcherFinished=p[role + 'Cpus'], childMainSamples=1800,
                childMainCpus=p[role + 'Cpus'], topologyUnchanged=True, capacityQualified=False)


class PlacementControls(unittest.TestCase):
    def test_two_complete_guest_cores_are_never_split_between_roles(self):
        p = c.plan([0, 1, 2, 3], topology())
        self.assertEqual(p['hostCpus'], [0, 2])
        self.assertEqual(p['clientCpus'], [1, 3])
        self.assertFalse(set(p['hostCpus']) & set(p['clientCpus']))
        for row in p['topology']['guestCores']:
            self.assertTrue(set(row['cpus']) <= set(p['hostCpus']) or set(row['cpus']) <= set(p['clientCpus']))

    def test_four_singleton_guest_cores_keep_the_same_fixed_two_plus_two_budget(self):
        t = dict(onlineCpus=[4, 5, 6, 7], guestCores=[dict(package=0, core=n, cpus=[n]) for n in range(4, 8)])
        p = c.plan([4, 5, 6, 7], t)
        self.assertEqual(p['hostCpus'], [4, 5])
        self.assertEqual(p['clientCpus'], [6, 7])

    def test_mixed_groups_require_whole_groups_not_greedy_sibling_splitting(self):
        t = dict(onlineCpus=[0, 1, 2, 3], guestCores=[dict(package=0, core=0, cpus=[0]),
            dict(package=0, core=1, cpus=[1, 2]), dict(package=0, core=2, cpus=[3])])
        p = c.plan([0, 1, 2, 3], t)
        self.assertEqual(p['hostCpus'], [0, 3])
        self.assertEqual(p['clientCpus'], [1, 2])

    def test_wrong_budget_incomplete_or_ambiguous_guest_groups_fail(self):
        for available in ([0, 1], [0, 1, 2], [0, 1, 2, 3, 4], [False, 1, 2, 3], [0, 1, 1, 3]):
            with self.assertRaises(ValueError):
                c.plan(available, topology())
        for mutation in (
            lambda t: t.update(private='must-not-export'),
            lambda t: t.update(onlineCpus=[0, 1, 2]),
            lambda t: t['guestCores'][0].update(cpus=[0]),
            lambda t: t['guestCores'][1].update(core=0),
            lambda t: t['guestCores'][1].update(cpus=[1, 2]),
            lambda t: t['guestCores'][1].update(package=True),
            lambda t: t['guestCores'].reverse(),
            lambda t: t.update(guestCores=[dict(package=0, core=0, cpus=[0, 1, 2, 3])]),
        ):
            t = topology(); mutation(t)
            with self.assertRaises(ValueError):
                c.plan([0, 1, 2, 3], t)

    def test_numeric_sysfs_lists_are_bounded_ordered_unique_and_not_arbitrary_text(self):
        self.assertEqual(c.parse_cpus('0-1,3,5-6\n'), [0, 1, 3, 5, 6])
        for raw in ('', '0,0', '2,0', '0-3,3', '00', '-1', '0-4095', '4096', '1-0', '0\n\n', '0;command', True):
            with self.assertRaises(ValueError):
                c.parse_cpus(raw)

    def fixture(self, directory):
        (directory / 'online').write_text('0-3\n')
        for n in range(4):
            base = directory / ('cpu' + str(n)) / 'topology'
            base.mkdir(parents=True)
            (base / 'physical_package_id').write_text('0\n')
            (base / 'core_id').write_text(str(n % 2) + '\n')
            (base / 'thread_siblings_list').write_text('0,2\n' if n % 2 == 0 else '1,3\n')

    def test_each_sibling_independently_confirms_the_observed_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            self.assertEqual(c.topology([0, 1, 2, 3], root), topology())
            path = root / 'cpu2/topology/thread_siblings_list'
            for raw in ('2\n', '0,2,4\n', '1,3\n'):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    c.topology([0, 1, 2, 3], root)

    def test_missing_sysfs_or_hotplug_does_not_fall_back_to_assumed_cpu_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            real = c.text
            counts = [0]
            def changed(path):
                if path.name == 'online':
                    counts[0] += 1
                    if counts[0] > 1:
                        return '0-2\n'
                return real(path)
            with patch.object(c, 'text', side_effect=changed), self.assertRaises(ValueError):
                c.topology([0, 1, 2, 3], root)
            (root / 'cpu2/topology/core_id').unlink()
            with self.assertRaises(FileNotFoundError):
                c.topology([0, 1, 2, 3], root)

    def test_default_does_not_read_or_modify_any_affinity_or_topology(self):
        with patch.object(c.os, 'sched_getaffinity') as read, patch.object(c.os, 'sched_setaffinity') as change, \
                patch.object(c, 'topology') as topology_read:
            self.assertIsNone(c.begin(c.INHERITED, 'host'))
            c.observe_child(None, None)
            c.finish(None)
            read.assert_not_called(); change.assert_not_called(); topology_read.assert_not_called()
            with self.assertRaises(ValueError):
                c.begin('auto-tune', 'host')

    def test_only_self_is_restricted_and_actual_inherited_child_affinity_is_observed(self):
        affinity = [{0, 1, 2, 3}]
        def read(pid):
            self.assertIn(pid, (0, 123))
            return set(affinity[0])
        def change(pid, cpus):
            self.assertEqual(pid, 0)
            self.assertEqual(cpus, [0, 2])
            self.assertTrue(set(cpus) < affinity[0])
            affinity[0] = set(cpus)
        with patch.object(c.sys, 'platform', 'linux'), patch.object(c.os, 'getuid', return_value=1001), \
                patch.object(c.os, 'geteuid', return_value=1001), patch.object(c.os, 'listdir', return_value=['owned']), \
                patch.object(c.os, 'sched_getaffinity', side_effect=read), \
                patch.object(c.os, 'sched_setaffinity', side_effect=change) as changed, \
                patch.object(c, 'topology', return_value=topology()):
            value = c.begin(c.SPLIT, 'host')
            c.observe_child(value, SimpleNamespace(pid=123, returncode=None))
            c.finish(value)
        self.assertEqual(changed.call_count, 1)
        self.assertEqual(c.validate(value, 'host')['childMainSamples'], 1)

    def test_root_multithreaded_or_nonlinux_launcher_cannot_start_the_split(self):
        for platform, uid, euid, threads in (('darwin', 1001, 1001, ['one']), ('linux', 0, 0, ['one']),
                ('linux', 1001, 0, ['one']), ('linux', 1001, 1001, ['one', 'two'])):
            with patch.object(c.sys, 'platform', platform), patch.object(c.os, 'getuid', return_value=uid), \
                    patch.object(c.os, 'geteuid', return_value=euid), patch.object(c.os, 'listdir', return_value=threads), \
                    patch.object(c.os, 'sched_setaffinity') as changed, self.assertRaises(ValueError):
                c.begin(c.SPLIT, 'host')
            changed.assert_not_called()

    def test_changed_start_affinity_or_failed_kernel_application_is_not_accepted(self):
        for values in (({0, 1, 2, 3}, {0, 1, 2}), ({0, 1, 2, 3}, {0, 1, 2, 3}, {0, 1, 2, 3})):
            with patch.object(c.sys, 'platform', 'linux'), patch.object(c.os, 'getuid', return_value=1001), \
                    patch.object(c.os, 'geteuid', return_value=1001), patch.object(c.os, 'listdir', return_value=['one']), \
                    patch.object(c.os, 'sched_getaffinity', side_effect=values), \
                    patch.object(c.os, 'sched_setaffinity'), patch.object(c, 'topology', return_value=topology()), \
                    self.assertRaises(ValueError):
                c.begin(c.SPLIT, 'host')

    def test_reaped_child_wrong_affinity_or_missing_observation_is_not_zero_cpu_evidence(self):
        for child, cpus in ((SimpleNamespace(pid=123, returncode=0), {0, 2}),
                            (SimpleNamespace(pid=123, returncode=None), {0, 1, 2, 3})):
            with patch.object(c.os, 'sched_getaffinity', return_value=cpus), self.assertRaises(ValueError):
                c.observe_child(proof(), child)
        with patch.object(c.os, 'sched_getaffinity', side_effect=ProcessLookupError), self.assertRaises(ProcessLookupError):
            c.observe_child(proof(), SimpleNamespace(pid=123, returncode=None))

    def test_final_drift_or_missing_child_samples_remains_failed(self):
        for cpus, topo, samples in (({0, 1, 2, 3}, topology(), 1), ({0, 2}, {}, 1), ({0, 2}, topology(), 0)):
            value = proof(); value['childMainSamples'] = samples
            with patch.object(c.os, 'sched_getaffinity', return_value=cpus), patch.object(c, 'topology', return_value=topo), \
                    self.assertRaises(ValueError):
                c.finish(value)

    def test_closed_evidence_does_not_hide_drift_overlaps_or_award_capacity(self):
        for role in ('host', 'client'):
            self.assertEqual(c.validate(proof(role), role), proof(role))
        for changes in ({'role': 'client'}, {'schema': True}, {'capacityQualified': True},
                        {'topologyUnchanged': False}, {'childMainSamples': True}, {'childMainSamples': 0},
                        {'childMainSamples': 5001}, {'launcherFinished': [0, 1, 2, 3]}, {'private': 'secret'}):
            with self.assertRaises(ValueError):
                c.validate({**proof(), **changes}, 'host')
        value = proof(); value['plan']['clientCpus'] = [0, 2]
        with self.assertRaises(ValueError):
            c.validate(value, 'host')

    def test_no_global_runtime_priority_or_owner_changes_are_introduced(self):
        source = (ROOT / 'scripts/rpc_capacity_cpu.py').read_text()
        self.assertEqual(source.count('os.sched_setaffinity('), 1)
        self.assertIn('os.sched_setaffinity(0,', source)
        for name in ('os.kill(', 'setpriority(', 'sched_setscheduler(', 'sysctl(', 'Popen(', 'ActiveProcessorCount'):
            self.assertNotIn(name, source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
