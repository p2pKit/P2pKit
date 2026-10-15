#!/usr/bin/env python3
"""Offline runner comparison controls, not native, performance or capacity results."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_capacity_runner as r


def env(image='ubuntu-24.04', mode='baseline'):
    return dict(RPC_CAPACITY_RUNNER=image, RPC_CAPACITY_EXPERIMENT=mode, ImageOS=r.IMAGES[image][0])


def topology():
    return dict(onlineCpus=[0, 1, 2, 3], guestCores=[dict(package=0, core=0, cpus=[0, 1]),
                                                dict(package=0, core=1, cpus=[2, 3])])


def cpuinfo():
    return '\n\n'.join('\n'.join(f'{k}\t: {v}' for k, v in {
        'processor': n, 'vendor_id': 'AuthenticAMD', 'cpu family': 25, 'model': 17, 'stepping': 1,
        'physical id': 0, 'core id': n // 2, 'cpu cores': 2, 'siblings': 4,
        'model name': 'PRIVATE_NEVER_EXPORT', 'address sizes': 'PRIVATE_NEVER_EXPORT'}.items()) for n in range(4))


def observation():
    return dict(schema=1, scope=r.SCOPE, request=r.request(env()), osVersion=[24, 4],
                kernel=r.kernel('6.11.0-1018-azure'), availableCpus=[0, 1, 2, 3], topology=topology(),
                cpuIdentification=r.identification(cpuinfo(), [0, 1, 2, 3]))


class RunnerControls(unittest.TestCase):
    def test_ubuntu22_followthrough_is_explicit_without_rerunning_unchanged_ubuntu24(self):
        selected = env('ubuntu-22.04', 'ubuntu22-follow-through')
        self.assertEqual(r.request(selected, r.UBUNTU22_MARKER),
                         dict(runner='ubuntu-22.04', experiment='ubuntu22-follow-through', imageOS='ubuntu22'))
        for wrong in (env('ubuntu-24.04', 'ubuntu22-follow-through'), env('ubuntu-22.04', 'baseline'), env()):
            with self.assertRaises(ValueError):
                r.request(wrong, r.UBUNTU22_MARKER)
        for mode, marker in r.MARKERS.items():
            candidate = env('ubuntu-22.04' if mode == 'ubuntu22-follow-through' else 'ubuntu-24.04', mode)
            self.assertEqual(r.request(candidate, marker)['experiment'], mode)
            for other in set(r.MARKERS.values()) - {marker}:
                with self.assertRaises(ValueError):
                    r.request(candidate, marker + other)
        workflow = (ROOT / '.github/workflows/rpc-capacity.yml').read_text()
        self.assertIn("'[\"ubuntu-22.04\"]'", workflow)
        self.assertIn("'[\"ubuntu-22.04\",\"ubuntu-24.04\"]'", workflow)
        self.assertIn("'[\"ubuntu-24.04\"]'", workflow)
        self.assertIn("contains(github.event.head_commit.message, '[rpc-capacity-ubuntu22]')", workflow)
        self.assertIn("'ubuntu22-follow-through'", workflow)

    def test_comparison_requires_its_own_marker_and_keeps_both_native_images(self):
        for image in r.IMAGES:
            value = r.request(env(image, 'image-comparison'), 'Compare ' + r.COMPARISON_MARKER)
            self.assertEqual(value['runner'], image)
            self.assertEqual(value['experiment'], 'image-comparison')
        self.assertEqual(r.request(env(), 'Original ' + r.BASELINE_MARKER)['runner'], 'ubuntu-24.04')
        for image, mode, message in (
            ('ubuntu-22.04', 'baseline', r.BASELINE_MARKER),
            ('ubuntu-24.04', 'baseline', r.COMPARISON_MARKER),
            ('ubuntu-24.04', 'image-comparison', r.BASELINE_MARKER),
            ('ubuntu-24.04', 'image-comparison', r.COMPARISON_MARKER + r.BASELINE_MARKER),
            ('ubuntu-24.04', 'baseline', 'ordinary unrequested push'),
        ):
            with self.subTest(image=image, mode=mode, message=message), self.assertRaises(ValueError):
                r.request(env(image, mode), message)

    def test_unrequested_images_or_wrong_actual_image_cannot_enter_comparison(self):
        for changes in ({'RPC_CAPACITY_RUNNER': 'ubuntu-latest'}, {'RPC_CAPACITY_RUNNER': 'ubuntu-24.04-arm'},
                        {'RPC_CAPACITY_EXPERIMENT': 'override'}, {'ImageOS': 'ubuntu22'}, {'ImageOS': ''},
                        {'RPC_CAPACITY_RUNNER': []}, {'RPC_CAPACITY_EXPERIMENT': True}):
            with self.assertRaises(ValueError):
                r.request({**env(), **changes})
        with self.assertRaises(ValueError):
            r.request({})

    def test_actual_os_release_must_match_requested_image_without_evaluating_text(self):
        for image, (_, version) in r.IMAGES.items():
            for quote in ('', '"'):
                self.assertEqual(r.distribution(f'NAME=ignored\nID=ubuntu\nVERSION_ID={quote}{version}{quote}\n', image),
                                 list(map(int, version.split('.'))))
        for raw in ('ID=ubuntu\nVERSION_ID="22.04"', 'ID=debian\nVERSION_ID="24.04"',
                    'ID=ubuntu\nVERSION_ID="24.04"\nVERSION_ID="24.04"',
                    'ID=ubuntu\nVERSION_ID="$(private-command)"', 'PRIVATE'):
            with self.assertRaises(ValueError):
                r.distribution(raw, 'ubuntu-24.04')

    def test_kernel_is_only_numeric_version_abi_and_closed_flavor(self):
        self.assertEqual(r.kernel('6.11.0-1018-azure'), dict(version=[6, 11, 0], abi=1018, flavor='AZURE'))
        self.assertEqual(r.kernel('5.15.0-102-generic'), dict(version=[5, 15, 0], abi=102, flavor='GENERIC'))
        self.assertEqual(r.kernel('6.1.72'), dict(version=[6, 1, 72], abi=None, flavor='OTHER'))
        self.assertEqual(r.kernel('6.1.72-private_suffix')['flavor'], 'OTHER')
        for raw in ('private', '6.1.0\nsecret', '6.1.0; command', '1' * 129, True):
            with self.assertRaises(ValueError):
                r.kernel(raw)

    def test_cpu_models_are_numeric_complete_and_never_export_arbitrary_fields(self):
        rows = r.identification(cpuinfo(), [0, 1, 2, 3])
        self.assertEqual([row['cpu'] for row in rows], [0, 1, 2, 3])
        self.assertEqual({row['vendor'] for row in rows}, {'AMD'})
        self.assertEqual({row['family'] for row in rows}, {25})
        self.assertNotIn('PRIVATE', json.dumps(rows))
        self.assertEqual(r.identification(cpuinfo().replace('AuthenticAMD', 'private'), [0, 1, 2, 3])[0]['vendor'], 'OTHER')
        self.assertEqual(r.identification(cpuinfo(), [0, 1]), rows[:2])

    def test_missing_repeated_unbounded_or_textual_cpu_fields_are_rejected(self):
        for raw in (cpuinfo().replace('model\t: 17', 'model\t: private', 1),
                    cpuinfo().replace('processor\t: 1', 'processor\t: 0', 1),
                    cpuinfo().replace('model\t: 17', 'model\t: 17\nmodel\t: 17', 1),
                    cpuinfo().replace('stepping\t: 1\n', '', 1),
                    cpuinfo().split('\n\n')[0], 'x' * (1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                r.identification(raw, [0, 1, 2, 3])

    def test_actual_observer_reads_only_metadata_without_changing_cpu_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            os_release, cpus = base / 'os-release', base / 'cpuinfo'
            os_release.write_text('ID=ubuntu\nVERSION_ID="24.04"')
            cpus.write_text(cpuinfo())
            with patch.object(r.platform, 'system', return_value='Linux'), \
                    patch.object(r.platform, 'machine', return_value='x86_64'), \
                    patch.object(r.platform, 'release', return_value='6.11.0-1018-azure'), \
                    patch.object(r.os, 'sched_getaffinity', return_value={0, 1, 2, 3}), \
                    patch.object(r.os, 'sched_setaffinity') as changed, \
                    patch.object(r.cpu, 'topology', return_value=topology()):
                self.assertEqual(r.observe(env(), os_release, cpus), observation())
                changed.assert_not_called()
                with patch.object(r.os, 'sched_getaffinity', side_effect=({0, 1, 2, 3}, {0, 1, 2})), \
                        self.assertRaises(ValueError):
                    r.observe(env(), os_release, cpus)

    def test_closed_observation_cannot_add_private_text_change_topology_or_award_capacity(self):
        original = observation()
        self.assertEqual(r.validate(original), original)
        for change in (
            lambda v: v.update(raw='PRIVATE'), lambda v: v.update(schema=True),
            lambda v: v.update(scope='CAPACITY_QUALIFIED'), lambda v: v.update(osVersion=[22, 4]),
            lambda v: v['kernel'].update(flavor='PRIVATE'), lambda v: v['kernel'].update(abi=True),
            lambda v: v['cpuIdentification'][0].update(core=1),
            lambda v: v['cpuIdentification'][0].update(model=True),
            lambda v: v['cpuIdentification'][0].update(modelName='PRIVATE'),
            lambda v: v['cpuIdentification'][0].update(vendor='PRIVATE'),
            lambda v: v['cpuIdentification'].reverse(), lambda v: v['cpuIdentification'].pop(),
            lambda v: v['request'].update(experiment='override'),
        ):
            value = copy.deepcopy(original); change(value)
            with self.assertRaises(ValueError):
                r.validate(value)

    def test_no_priority_governor_resource_or_security_modification_is_available(self):
        source = (ROOT / 'scripts/rpc_capacity_runner.py').read_text()
        for forbidden in ('subprocess', 'os.system', 'sysctl(', 'setaffinity(', 'setpriority(', 'chmod(',
                          'sched_setscheduler(', 'sudo', 'Popen(', 'os.kill(', 'os.environ['):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
