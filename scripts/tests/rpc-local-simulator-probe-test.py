#!/usr/bin/env python3
"""Offline local-probe controls; no simulator, process scope, or tool is executed."""
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_local_simulator_probe as p


class LocalSimulatorProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.runtime = self.root / 'runtime'
        (self.runtime / 'bin').mkdir(parents=True)
        self.executable = self.runtime / 'bin/launchctl'
        self.executable.write_bytes(self.binary())
        self.executable.chmod(0o755)
        self.devices = self.root / 'private-devices'
        self.devices.mkdir(mode=0o700)
        self.identifier = '00000000-0000-0000-0000-000000000001'
        self.selected = 'com.apple.CoreSimulator.SimRuntime.iOS-27-0'
        self.row = dict(identifier=self.selected, isAvailable=True, supportedArchitectures=['arm64'],
                        runtimeRoot=str(self.runtime))

    def binary(self, *, cpu=0x0100000c, kind=2, platform=7, count=1, size=24, command_size=24):
        return (struct.pack('<8I', 0xfeedfacf, cpu, 0, kind, count, size, 0, 0) +
                struct.pack('<6I', 0x32, command_size, platform, 0, 0, 0) + b'synthetic fixture, not executable code')

    def tool(self):
        return p.runtime_tool(self.row, self.selected)

    def test_runtime_binary_is_bound_without_executing_it(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No native execution in binding')):
            value = self.tool()
        self.assertEqual(value, dict(runtime=self.selected, executable=str(self.executable),
            sha256=hashlib.sha256(self.executable.read_bytes()).hexdigest(),
            architecture='arm64', platform='IOSSIMULATOR'))

    def test_boot_explicitly_selects_arm64_without_standalone_or_job_overrides(self):
        commands = p.probe_commands(self.devices, self.identifier, self.tool())
        self.assertEqual(commands['boot'], ['/usr/bin/xcrun', 'simctl', '--set', str(self.devices),
                                            'boot', self.identifier, '--arch=arm64'])

    def test_missing_guest_uname_does_not_break_the_actual_runtime_probe(self):
        self.assertFalse((self.runtime / 'usr/bin/uname').exists())
        commands = p.probe_commands(self.devices, self.identifier, self.tool())
        self.assertEqual(commands['architecture'], ['/usr/bin/xcrun', 'simctl', '--set', str(self.devices),
            'spawn', '--arch=arm64', self.identifier, str(self.executable), 'manageruid'])
        self.assertNotIn('/usr/bin/uname', commands['architecture'])
        self.assertNotIn('/bin/launchctl', commands['architecture'])  # That would be the HOST binary.

    def test_probe_output_requires_the_actual_nonroot_manager_uid(self):
        p.verify_probe_output(b'501\n', 501)
        p.verify_probe_output(b'123456\n', 123456)
        for value in (b'arm64\n', b'0\n', b'502\n', b'501\nextra', b' 501\n', b'501', b'', '501\n'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                p.verify_probe_output(value, 501)
        for uid in (0, -1, True, '501'):
            with self.subTest(uid=uid), self.assertRaises(RuntimeError):
                p.verify_probe_output(b'501\n', uid)

    def test_exact_available_arm64_only_runtime_is_required(self):
        for change in (dict(identifier='other'), dict(isAvailable=False), dict(isAvailable=1),
                       dict(supportedArchitectures=['x86_64']), dict(supportedArchitectures=['arm64', 'x86_64']),
                       dict(supportedArchitectures=['arm64', 'arm64']), dict(supportedArchitectures='arm64')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                p.runtime_tool({**self.row, **change}, self.selected)
        for selected in (None, 'booted', '../runtime', 1):
            with self.subTest(selected=selected), self.assertRaises(RuntimeError):
                p.runtime_tool(self.row, selected)

    def test_missing_runtime_launchctl_has_no_host_or_uname_fallback(self):
        self.executable.unlink()
        with self.assertRaises(OSError):
            self.tool()

    def test_binary_and_ancestor_symlinks_are_rejected(self):
        actual = self.runtime / 'bin/actual'
        self.executable.rename(actual)
        self.executable.symlink_to(actual)
        with self.assertRaises(RuntimeError):
            self.tool()
        self.executable.unlink()
        actual.rename(self.executable)
        alias = self.root / 'alias'
        alias.symlink_to(self.runtime, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            p.runtime_tool({**self.row, 'runtimeRoot': str(alias)}, self.selected)

    def test_relative_and_traversing_runtime_roots_are_rejected(self):
        for root in ('runtime', str(self.runtime) + '/../runtime', str(self.runtime) + '/', '', None, '/bad\0path'):
            with self.subTest(root=root), self.assertRaises((RuntimeError, OSError, ValueError)):
                p.runtime_tool({**self.row, 'runtimeRoot': root}, self.selected)

    def test_fifo_and_nonexecutable_or_privileged_files_are_rejected(self):
        for mode in (0o644, 0o4755, 0o2755):
            self.executable.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                self.tool()
        self.executable.unlink()
        os.mkfifo(self.executable, 0o700)
        with self.assertRaises(RuntimeError):
            self.tool()

    def test_non_arm_and_host_or_device_platforms_are_rejected(self):
        for change in (dict(cpu=0x01000007), dict(cpu=12), dict(kind=6), dict(platform=1), dict(platform=2)):
            self.executable.write_bytes(self.binary(**change))
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.tool()

    def test_universal_and_swapped_endian_binaries_are_not_a_fallback(self):
        for magic in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf', b'\xfe\xed\xfa\xcf'):
            self.executable.write_bytes(magic + self.binary()[4:])
            with self.subTest(magic=magic), self.assertRaises(RuntimeError):
                self.tool()

    def test_malformed_or_missing_load_commands_are_rejected(self):
        for change in (dict(count=0), dict(count=1025), dict(count=2), dict(size=0), dict(size=8),
                       dict(size=p.MAX_COMMANDS + 1), dict(command_size=0), dict(command_size=16),
                       dict(command_size=32), dict(command_size=25)):
            self.executable.write_bytes(self.binary(**change))
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.tool()
        self.executable.write_bytes(self.binary()[:32])
        with self.assertRaises(RuntimeError):
            self.tool()

    def test_duplicate_build_versions_are_rejected(self):
        self.executable.write_bytes(struct.pack('<8I', 0xfeedfacf, 0x0100000c, 0, 2, 2, 48, 0, 0) +
                                    struct.pack('<6I', 0x32, 24, 7, 0, 0, 0) * 2)
        with self.assertRaises(RuntimeError):
            self.tool()

    def test_file_size_bound_is_not_relaxed(self):
        with patch.object(p, 'MAX_TOOL', self.executable.stat().st_size - 1), self.assertRaises(RuntimeError):
            self.tool()

    def test_exact_id_physical_device_set_and_bound_tool_are_required(self):
        tool = self.tool()
        for identifier in ('booted', 'all', '', None, True, self.identifier + '\n'):
            with self.subTest(identifier=identifier), self.assertRaises(RuntimeError):
                p.probe_commands(self.devices, identifier, tool)
        for devices in (Path('relative'), str(self.devices), self.root / 'missing'):
            with self.subTest(devices=devices), self.assertRaises((RuntimeError, OSError)):
                p.probe_commands(devices, self.identifier, tool)
        for change in (dict(architecture='x86_64'), dict(platform='MACOS'), dict(sha256='invalid'),
                       dict(executable='launchctl')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                p.probe_commands(self.devices, self.identifier, {**tool, **change})


if __name__ == '__main__':
    unittest.main(verbosity=2)
