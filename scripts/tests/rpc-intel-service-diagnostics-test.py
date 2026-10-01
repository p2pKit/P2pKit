#!/usr/bin/env python3
"""Offline log/privacy controls. No Apple log query, simulator or native claim."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_intel_service_diagnostics as d


class ServiceLogControls(unittest.TestCase):
    def encode(self, messages=(), code=0):
        lines = [d.BEGIN, json.dumps({'logArchive': '/PRIVATE/header'})]
        lines += [json.dumps(dict(eventMessage=m, messageType='Error', processID=4321,
                                 senderImagePath='/PRIVATE/tool', timestamp='PRIVATE')) for m in messages]
        if code is not None:
            lines.append(d.END + json.dumps(dict(exitCode=code)))
        return ('\n'.join(lines) + '\n').encode()

    def test_fixed_bounded_read_only_query_and_no_service_or_privilege_mutation(self):
        self.assertEqual(d.COMMAND[:8], ('/usr/bin/log', 'show', '--style', 'ndjson', '--info', '--last', '120s', '--predicate'))
        self.assertEqual(d.QUERY_AFTER_NANOS, 60 * 10 ** 9)
        self.assertEqual(d.MAX_BYTES, 4 * 1024 * 1024)
        for word in ('sudo', 'config', 'erase', 'collect', '--debug', '--private', '--all'):
            self.assertNotIn(word, d.COMMAND)
        self.assertIn('process == "simctl"', d.COMMAND[-1])
        self.assertIn('subsystem BEGINSWITH "com.apple.CoreSimulator"', d.COMMAND[-1])

    def test_known_error_categories_keep_only_counts_and_actual_log_digest(self):
        raw = self.encode(['CoreSimulatorService connection became invalid PRIVATE',
                           'Error: Permission denied /PRIVATE/path', 'unmapped PRIVATE body'])
        row = d.observation(raw)
        self.assertEqual(row['records'], 3)
        self.assertEqual(row['unclassifiedRecords'], 1)
        self.assertEqual(row['levels'], {'Error': 3})
        self.assertEqual(row['markers'], {'XPC_CONNECTION_INVALID': 1, 'PERMISSION_DENIED': 1})
        self.assertEqual(row['bytes'], len(raw))
        self.assertEqual(row['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(row['readerExitCode'], 0)
        self.assertFalse(row['executionAdmitted'])
        for private in ('PRIVATE', '4321', 'eventMessage', 'timestamp', '/path'):
            self.assertNotIn(private, json.dumps(row))

    def test_reader_failure_and_missing_exit_are_explicit_not_passing_or_zero(self):
        self.assertEqual(d.observation(self.encode(code=7))['readerExitCode'], 7)
        self.assertIsNone(d.observation(self.encode(code=None))['readerExitCode'])
        self.assertIsNone(d.observation(b'No service query was started\n'))
        self.assertFalse(d.observation(self.encode())['executionAdmitted'])

    def test_interleaved_cpu_frames_never_become_service_log_records(self):
        raw = self.encode(['waiting for service PRIVATE'], code=None)
        raw += b'RPC_INTEL_INVENTORY_CPU_JSON:{"private":"fixture"}\n'
        raw += (d.END + '{"exitCode":0}\n').encode()
        row = d.observation(raw)
        self.assertEqual(row['records'], 1)
        self.assertEqual(row['markers'], {'SERVICE_WAITING': 1})

    def test_duplicate_begin_end_keys_invalid_types_or_excessive_output_fail_closed(self):
        for raw in (self.encode() + (d.BEGIN + '\n').encode(),
                    (d.END + '{"exitCode":0}\n').encode(),
                    self.encode() + (d.END + '{"exitCode":0}\n').encode(),
                    (d.BEGIN + '\n' + d.END + '{"exitCode":0,"exitCode":0}\n').encode(),
                    (d.BEGIN + '\n{"eventMessage":"one","eventMessage":"two"}\n').encode(),
                    (d.BEGIN + '\n{"eventMessage":42}\n').encode(),
                    self.encode(code=True), self.encode(code=256), b'x' * (d.MAX_BYTES + 1)):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                d.observation(raw)

    def test_public_schema_refuses_unknown_fields_categories_or_inconsistent_counts(self):
        row = d.observation(self.encode(['Permission denied']))
        for changes in (dict(pid=4321), dict(scope='READINESS_PASS'), dict(executionAdmitted=True),
                        dict(readerExitCode=True), dict(readerExitCode=-256), dict(records=True),
                        dict(markers={'PRIVATE': 1}), dict(levels={'Private': 1}),
                        dict(levels={}), dict(records=0), dict(unclassifiedRecords=2),
                        dict(sha256='PRIVATE'), dict(bytes=0)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                d.validate({**row, **changes})

    def test_unknown_native_level_is_counted_not_exported(self):
        raw = self.encode(['unclassified']).replace(b'"Error"', b'"PRIVATE"')
        self.assertEqual(d.observation(raw)['levels'], {'Unknown': 1})

    def test_missing_screen_profile_keys_are_not_inferred_from_error_code_alone(self):
        raw = self.encode([
            'Error Domain=com.apple.CoreSimulator.SimError Code=402 "Missing keys to define the main screen: '
            '/PRIVATE/device.simdevicetype/Contents/Resources/profile.plist"',
            'Error Domain=com.apple.CoreSimulator.SimError Code=402 "PRIVATE unrelated description"',
        ])
        row = d.observation(raw)
        self.assertEqual(row['markers'], {'DEVICE_TYPE_SCREEN_KEYS_MISSING': 1})
        self.assertEqual(row['unclassifiedRecords'], 1)
        self.assertFalse(row['executionAdmitted'])
        self.assertNotIn('PRIVATE', json.dumps(row))
        self.assertNotIn('profile.plist', json.dumps(row))


if __name__ == '__main__':
    unittest.main(verbosity=2)
