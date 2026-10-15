#!/usr/bin/env python3
"""Offline native-lane binding controls, not Apple execution or architecture admission."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_runner_context as c


class NativeLaneControls(unittest.TestCase):
    def test_required_apple_matrix_roles_are_not_replaced_or_translated(self):
        spec = importlib.util.spec_from_file_location('apple_context_qualification', ROOT / 'scripts/run-rpc-qualification.py')
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        self.assertEqual(c.HOSTS, {lane: (q.HOSTS[lane][1], q.HOSTS[lane][2]) for lane in ('apple-x64', 'apple-arm64')})
        for lane, (machine, role) in c.HOSTS.items():
            with patch.object(c.platform, 'system', return_value='Darwin'), \
                    patch.object(c.platform, 'machine', return_value=machine), patch.object(c, 'host_role', return_value=role):
                self.assertEqual(c.native_lane({'RPC_APPLE_LANE': lane}), lane)
                for wrong in ('linux-x64', 'macos-arm64' if role == 'macos-x64' else 'macos-x64'):
                    with patch.object(c, 'host_role', return_value=wrong), self.assertRaises(RuntimeError):
                        c.native_lane({'RPC_APPLE_LANE': lane})
                for wrong in ('Linux', 'Windows'):
                    with patch.object(c.platform, 'system', return_value=wrong), self.assertRaises(RuntimeError):
                        c.native_lane({'RPC_APPLE_LANE': lane})
                with patch.object(c.platform, 'machine', return_value='arm64' if machine == 'x86_64' else 'x86_64'), \
                        self.assertRaises(RuntimeError):
                    c.native_lane({'RPC_APPLE_LANE': lane})

    def test_missing_or_unrecognized_lane_cannot_inherit_a_native_default(self):
        for value in (None, '', 'apple', 'android-art', 'x86_64', 'apple-arm64 ', True, []):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                c.selected_lane({'RPC_APPLE_LANE': value})
        with self.assertRaises(RuntimeError):
            c.selected_lane({})

    def test_source_equal_proofs_still_require_the_exact_native_lane(self):
        for lane in c.HOSTS:
            self.assertEqual(c.proof_lane(lane, lane), lane)
            other = 'apple-arm64' if lane == 'apple-x64' else 'apple-x64'
            with self.assertRaises(RuntimeError):
                c.proof_lane(lane, other)
        for value in (None, False, [], {}, 'android-art', 'macos-x64'):
            with self.assertRaises(RuntimeError):
                c.proof_lane(value, 'apple-x64')


if __name__ == '__main__':
    unittest.main(verbosity=2)
