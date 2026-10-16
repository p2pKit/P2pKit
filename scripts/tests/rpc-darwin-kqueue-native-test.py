#!/usr/bin/env python3
"""Two read-only native Mac controls; NOT the 125-second preflight or RPC qualification.

No subprocesses, audit bootstrap, app/device access, resource pressure, signing or
system changes. The only allocated kernel object is this process's own kqueue FD.
"""
import errno
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import rpc_darwin_capacity as m
from audit_processes import host_role


class NativeReadOnly(unittest.TestCase):
    def setUp(self):
        self.assertEqual(host_role(), 'macos-arm64')
        self.assertGreater(os.getuid(), 0)
        self.assertEqual(os.getuid(), os.geteuid())

    def test_actual_native_hardware_query_has_no_virtual_or_missing_field_fallback(self):
        row = m.native_hardware()
        self.assertTrue(row['nativeMacModelObserved'])
        self.assertFalse(row['hypervisorPresent'])
        self.assertGreater(row['memoryBytes'], 0)
        self.assertGreater(row['logicalCpus'], 0)

    def test_actual_kernel_expirations_and_exact_owned_descriptor_retirement(self):
        with m.Timer() as timer:
            descriptor = timer.queue.fileno()
            first, second = timer.read(.5), timer.read(.5)
            self.assertIsInstance(first, int)
            self.assertIsInstance(second, int)
            self.assertGreaterEqual(first, 1)
            self.assertGreaterEqual(second, 1)
        with self.assertRaises(OSError) as caught:
            os.fstat(descriptor)
        self.assertEqual(caught.exception.errno, errno.EBADF)


if __name__ == '__main__':
    unittest.main(verbosity=2)
