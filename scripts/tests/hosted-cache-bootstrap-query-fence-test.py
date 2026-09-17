#!/usr/bin/env python3
"""Offline controls for the optional, shortening-only native-query owner fence.

The existing query harness models Git/native owners and time. Only tiny private
POSIX fixture files are real; no hosted identity, process, build, dependency,
provider, service budget or bootstrap schedule is executed or qualified here.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("bootstrap_query_fence_models",
    ROOT / "scripts/tests/hosted-test-query-test.py")
MODELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODELS)
Q = MODELS.Q


class OwnerFenceTests(unittest.TestCase):
    # Reuse fixture setup, not inherited test methods or fake native evidence.
    setUp = MODELS.QueryTests.setUp
    tearDown = MODELS.QueryTests.tearDown
    make_scope = MODELS.QueryTests.make_scope
    outputs = MODELS.QueryTests.outputs
    cancellation = MODELS.QueryTests.cancellation
    arguments = MODELS.QueryTests.arguments
    query = MODELS.QueryTests.query
    close_failed = MODELS.QueryTests.close_failed

    def owner(self, deadlines=(105.0, 112.0)):
        value = Q.NativeGitQueries(self.root, self.state, check_cancel=self.cancellation,
                                   owner_deadlines=deadlines)
        self.owners.append(value)
        return value

    def admitted(self):
        return Q.identity.Admission(b'{"fixture":"SYNTHETIC"}\n', b'{}\n', b'{}\n',
            b'SYNTHETIC; NOT A KEY\n', 'a' * 40, 'b' * 64, 2_000_000_000)

    def test_invalid_or_expired_pair_refuses_before_native_or_file_allocation(self):
        invalid = (True, [], [105.0, 112.0], (105.0,), (105.0, 112.0, 130.0),
            (None, 112.0), (105.0, None), (True, 112.0), (105.0, False),
            (math.nan, 112.0), (105.0, math.inf), (-math.inf, 112.0),
            (10 ** 1000, 10 ** 1001), (100.0, 112.0), (99.0, 112.0),
            (112.0, 105.0), ('105', 112.0))
        for value in invalid:
            with self.subTest(value_type=type(value).__name__):
                with patch.object(Q.processes, 'host_role', side_effect=AssertionError('NO_NATIVE_CALL')):
                    with self.assertRaisesRegex(Q.QueryError, 'QUERY_OWNER_DEADLINES'):
                        self.owner(value)
                self.assertFalse(self.state.exists())
                self.assertFalse(self.events)

    def test_default_has_unchanged_per_query_and_final_records(self):
        owner = self.owner(None)
        self.assertEqual(owner.io_deadline, 145.0)
        self.assertEqual(self.query(owner), self.out)
        self.assertEqual(owner.io_deadline, 160.0)
        self.assertEqual(owner.records[0]['timeoutSeconds'], 15)
        self.assertNotIn('owner_deadlines', owner.records[0])
        self.clock.now = 110.0
        owner.close()
        self.assertEqual(owner.io_deadline, 155.0)
        self.assertTrue(all(row['closed'] for row in owner.resources))

    def test_owner_pair_only_shortens_never_extends_existing_query_caps(self):
        owner = self.owner((1000.0, 2000.0))
        self.assertEqual(owner.io_deadline, 145.0)
        self.assertEqual(self.query(owner), self.out)
        self.assertEqual(owner.io_deadline, 160.0)
        self.clock.now = 101.0
        owner.close()
        self.assertEqual(owner.io_deadline, 146.0)

    def test_work_fence_stops_polling_without_renewing_final_window(self):
        self.exit_code = None
        owner = self.owner((100.05, 101.0))
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertLess(self.clock.now, 100.1)
        self.assertEqual(owner.io_deadline, 101.0)
        self.assertEqual(owner.records[0]['result'], 'HOLD')
        self.assertTrue(any(event[0] == 'drain' for event in self.events))
        self.close_failed(owner)
        self.assertEqual(owner.io_deadline, 101.0)

    def test_large_owner_fences_cannot_extend_the_existing_15_second_query_wait(self):
        self.exit_code = None
        owner = self.owner((1000.0, 2000.0))
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertGreaterEqual(self.clock.now, 115.0)
        self.assertLess(self.clock.now, 115.1)
        self.assertEqual(owner.io_deadline, 160.0)
        self.close_failed(owner)

    def test_late_constructor_allocates_no_private_root(self):
        def delayed_role():
            self.clock.now = 112.0
            return 'macos-arm64'
        with patch.object(Q.processes, 'host_role', side_effect=delayed_role):
            with self.assertRaises(Q.QueryError):
                self.owner()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.events)

    def test_constructor_rechecks_work_fence_after_host_resolution(self):
        def delayed_role():
            self.clock.now = 105.0
            return 'macos-arm64'
        with patch.object(Q.processes, 'host_role', side_effect=delayed_role):
            with self.assertRaisesRegex(Q.QueryError, 'QUERY_OWNER_WORK_EXPIRED'):
                self.owner()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.events)

    def test_constructor_original_io_cap_forbids_a_late_root_allocation(self):
        def delayed_role():
            self.clock.now = 146.0  # Later than the original constructor IO45.
            return 'macos-arm64'
        with patch.object(Q.processes, 'host_role', side_effect=delayed_role), \
                patch.object(Q, '_new_private_directory', wraps=Q._new_private_directory) as create:
            with self.assertRaises(Q.QueryError):
                self.owner((1000.0, 2000.0))
            create.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_constructor_rechecks_work_after_each_returned_allocation_and_retention(self):
        new, child, sync = Q._new_private_directory, Q._PosixDirectory.create_directory, Q._PosixSink.sync
        for boundary in ('root', 'home', 'owner-record'):
            with self.subTest(boundary=boundary):
                self.state = self.base / boundary
                self.clock.now = 100.0
                def delayed_root(path):
                    result = new(path)
                    if boundary == 'root':
                        self.clock.now = 105.0
                    return result
                def delayed_home(directory, name, **kwargs):
                    result = child(directory, name, **kwargs)
                    if boundary == 'home' and name == 'query-home':
                        self.clock.now = 105.0
                    return result
                def delayed_record(stream):
                    result = sync(stream)
                    if boundary == 'owner-record' and stream.path.name == 'owner.json':
                        self.clock.now = 105.0
                    return result
                with patch.object(Q, '_new_private_directory', new=delayed_root), \
                        patch.object(Q._PosixDirectory, 'create_directory', new=delayed_home), \
                        patch.object(Q._PosixSink, 'sync', new=delayed_record):
                    with self.assertRaises(Q.QueryError):
                        self.owner()
                self.assertTrue(self.state.exists())  # No deletion authority.
                self.assertEqual((self.state / 'query-home').exists(), boundary != 'root')
                self.assertEqual((self.state / 'owner.json').exists(), boundary == 'owner-record')
                self.assertFalse(self.events)

    def test_second_query_cannot_restart_the_original_work_allowance(self):
        owner = self.owner()
        self.assertEqual(self.query(owner), self.out)
        self.clock.now = 105.0
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertEqual(len(owner.records), 1)
        self.assertEqual(len(self.calls), 1)
        self.close_failed(owner)
        self.assertEqual(owner.io_deadline, 112.0)

    def test_retaining_admission_uses_original_final_fence_for_every_write(self):
        owner = self.owner()
        self.clock.now = 104.0
        writes = []
        create = Q._PosixDirectory.create_file
        def observed_create(directory, name, **kwargs):
            writes.append((name, kwargs['deadline']))
            return create(directory, name, **kwargs)
        with patch.object(Q._PosixDirectory, 'create_file', new=observed_create):
            owner.retain_admission(self.admitted())
        self.assertEqual(len(writes), 5)
        self.assertEqual({end for _, end in writes}, {112.0})
        self.assertEqual((self.state / 'admission.json').read_bytes(), self.admitted().record)
        owner.close()

    def test_retention_crossing_final_fence_cannot_create_later_admission_files(self):
        owner = self.owner()
        sync = Q._PosixSink.sync
        def delayed_sync(stream):
            if stream.path.name == 'admission.json':
                self.clock.now = 112.0
            return sync(stream)
        with patch.object(Q._PosixSink, 'sync', new=delayed_sync):
            with self.assertRaises(Q.posix_files.EvidenceError):
                owner.retain_admission(self.admitted())
        self.assertTrue((self.state / 'admission.json').exists())
        self.assertFalse((self.state / 'original-event.json').exists())
        self.close_failed(owner)
        self.assertFalse((self.state / 'session-result.json').exists())
        self.assertTrue(all(row['closed'] for row in owner.resources))

    def test_failure_retention_and_close_cannot_resurrect_fresh_45_seconds(self):
        owner = self.owner()
        self.assertEqual(self.query(owner), self.out)
        first = RuntimeError('SYNTHETIC ORIGINAL FAILURE')
        self.clock.now = 112.0
        with patch.object(Q._PosixDirectory, 'create_file', side_effect=AssertionError('NO_LATE_WRITER')) as create:
            owner.record_admission_failure(first)
            self.close_failed(owner)
            create.assert_not_called()
        self.assertIs(owner.first_error, first)
        self.assertEqual(owner.io_deadline, 112.0)
        self.assertFalse((self.state / 'admission-failure.json').exists())
        self.assertFalse((self.state / 'session-result.json').exists())
        self.assertTrue(all(row['closed'] for row in owner.resources))

    def test_failure_originals_can_still_be_retained_inside_original_final_slot(self):
        owner = self.owner()
        self.clock.now = 106.0
        first = RuntimeError('SYNTHETIC ORIGINAL FAILURE')
        owner.record_admission_failure(first)
        self.assertTrue((self.state / 'admission-failure.json').exists())
        self.close_failed(owner)
        self.assertTrue((self.state / 'session-result.json').exists())
        self.assertIs(owner.first_error, first)
        self.assertEqual(owner.io_deadline, 112.0)

    def test_reader_and_writer_reclamp_even_if_local_io_deadline_is_replaced(self):
        owner = self.owner()
        owner.io_deadline = 9999.0
        self.clock.now = 112.0
        with patch.object(Q._PosixDirectory, 'create_file', side_effect=AssertionError('NO_LATE_WRITER')) as create, \
                patch.object(Q._PosixDirectory, 'read_bytes', side_effect=AssertionError('NO_LATE_READER')) as read:
            with self.assertRaises(Q.posix_files.EvidenceError):
                owner._write(owner.private, 'too-late.json', b'{}\n')
            with self.assertRaises(Q.posix_files.EvidenceError):
                owner._readback(owner.private, 'owner.json', 4096, 9999.0)
            self.close_failed(owner)
            create.assert_not_called()
            read.assert_not_called()
        self.assertFalse((self.state / 'too-late.json').exists())

    def test_expired_final_fence_forbids_new_delegated_allocation(self):
        owner = self.owner()
        self.clock.now = 112.0
        with patch.object(Q, '_new_private_directory', side_effect=AssertionError('NO_LATE_ALLOCATION')) as create:
            with self.assertRaises(Q.posix_files.EvidenceError):
                owner._acquire('too-late', lambda: Q._new_private_directory(self.base / 'late'))
            create.assert_not_called()
        self.assertFalse((self.base / 'late').exists())
        self.close_failed(owner)

    def test_late_native_drain_keeps_failure_and_closes_original_resources(self):
        owner = self.owner()
        drain = MODELS.Scope.drain
        def delayed_drain(scope, **kwargs):
            self.clock.now = 113.0
            return drain(scope, **kwargs)
        with patch.object(MODELS.Scope, 'drain', new=delayed_drain):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.assertEqual(owner.records[0]['result'], 'HOLD')
        self.assertTrue(any(event[0] == 'scope-close' for event in self.events))
        self.close_failed(owner)
        self.assertTrue(all(row['closed'] for row in owner.resources))
        self.assertFalse((self.state / 'session-result.json').exists())

    def test_unknown_retirement_still_quarantines_instead_of_forced_cleanup(self):
        owner = self.owner()
        self.drain_error = OSError('SYNTHETIC UNKNOWN DRAIN')
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.clock.now = 113.0
        self.close_failed(owner)
        self.assertTrue(owner.unknown)
        self.assertIn(owner, Q.QUARANTINE)
        for label in ('stdout', 'stderr', 'query-directory', 'private-root', 'query-home'):
            self.assertFalse(next(row for row in owner.resources if row['label'] == label)['closeAttempted'])

    def test_last_original_directory_close_cannot_report_an_on_time_return(self):
        owner = self.owner()
        self.assertEqual(self.query(owner), self.out)
        close = Q._PosixDirectory.close
        def delayed_close(directory):
            if directory is owner.private:
                self.clock.now = 113.0
            return close(directory)
        with patch.object(Q._PosixDirectory, 'close', new=delayed_close):
            with self.assertRaises(Q.QueryError):
                owner.close()
        self.assertTrue(owner.failed)
        self.assertFalse(owner.unknown)
        self.assertTrue(all(row['closed'] for row in owner.resources))
        # Its earlier provisional bytes cannot attest the subsequent real return.
        self.assertEqual(Q.identity.parse((self.state / 'session-result.json').read_bytes(),
            Q.MAX_RECEIPT_BYTES)['result'], 'READY_FOR_CALLER_SEAL')

    def test_original_cancellation_survives_late_retention_and_session_close(self):
        owner = self.owner()
        original = KeyboardInterrupt('SYNTHETIC ORIGINAL CANCEL')
        self.poll_error = original
        self.clock.now = 104.0
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.query(owner)
        self.assertIs(caught.exception, original)
        self.clock.now = 112.0
        owner.record_admission_failure(original)
        with self.assertRaises(KeyboardInterrupt) as caught:
            owner.close()
        self.assertIs(caught.exception, original)
        self.assertTrue(all(row['closed'] for row in owner.resources))


if __name__ == '__main__':
    unittest.main(verbosity=2)
