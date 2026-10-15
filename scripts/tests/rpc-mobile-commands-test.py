#!/usr/bin/env python3
"""Offline stream-creation controls; no device, GUI, native admission or process launch."""
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_mobile_usb as m
spec = importlib.util.spec_from_file_location('command_test_files', ROOT / 'scripts/run-rpc-capacity-lab.py')
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


class PrivateStreams(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.base.chmod(0o700)
        with patch.dict(os.environ, P2PKIT_AUDIT_OWNERSHIP_CHAIN='OFFLINE_NOT_NATIVE_ADMISSION'):
            self.commands = m.Commands(self.base, {}, files)

    def child(self, _argv, *, stdout, stderr, **_kwargs):
        for stream in (stdout, stderr):
            info = os.fstat(stream.fileno())
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
            self.assertEqual(info.st_uid, os.getuid())
            self.assertEqual(info.st_nlink, 1)
        stdout.write(b'OFFLINE_OBSERVATION\n')
        return Mock(poll=Mock(return_value=0), returncode=0)

    def test_streams_are_private_before_launch_with_normal_umask(self):
        previous = os.umask(0o022)
        try:
            with patch.object(m.subprocess, 'Popen', side_effect=self.child) as launch:
                self.assertEqual(self.commands.run('observer', ['/NOT_EXECUTED'], timeout=2), (0, b'OFFLINE_OBSERVATION\n'))
            launch.assert_called_once()
        finally:
            self.assertEqual(os.umask(previous), 0o022)

    def test_streams_are_private_even_with_permissive_umask_without_global_change(self):
        previous = os.umask(0)
        try:
            with patch.object(m.subprocess, 'Popen', side_effect=self.child):
                self.commands.run('observer', ['/NOT_EXECUTED'], timeout=2)
        finally:
            self.assertEqual(os.umask(previous), 0)

    def test_existing_output_is_not_truncated_or_chmodded(self):
        output = self.base / '00001-observer.stdout'
        output.write_bytes(b'KEEP')
        output.chmod(0o644)
        with patch.object(m.subprocess, 'Popen') as launch, self.assertRaises(FileExistsError):
            self.commands.run('observer', ['/NOT_EXECUTED'])
        launch.assert_not_called()
        self.assertEqual(output.read_bytes(), b'KEEP')
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o644)

    def test_symlink_output_does_not_follow_or_modify_its_target(self):
        target = self.base / 'sentinel'
        target.write_bytes(b'KEEP')
        (self.base / '00001-observer.stderr').symlink_to(target)
        with patch.object(m.subprocess, 'Popen') as launch, self.assertRaises(OSError):
            self.commands.run('observer', ['/NOT_EXECUTED'])
        launch.assert_not_called()
        self.assertEqual(target.read_bytes(), b'KEEP')
        self.assertEqual(stat.S_IMODE((self.base / '00001-observer.stdout').stat().st_mode), 0o600)

    def test_fifo_output_is_refused_without_opening_it_or_launching(self):
        os.mkfifo(self.base / '00001-observer.stdout', 0o600)
        with patch.object(m.subprocess, 'Popen') as launch, self.assertRaises(OSError):
            self.commands.run('observer', ['/NOT_EXECUTED'])
        launch.assert_not_called()

    def test_original_setup_deadline_prevents_late_launch(self):
        with patch.object(m.subprocess, 'Popen') as launch, \
                patch.object(m.time, 'monotonic', side_effect=[0, 2]), self.assertRaises(ValueError):
            self.commands.run('observer', ['/NOT_EXECUTED'], timeout=2)
        launch.assert_not_called()
        self.assertEqual(self.commands.rows[0]['timeoutSeconds'], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
