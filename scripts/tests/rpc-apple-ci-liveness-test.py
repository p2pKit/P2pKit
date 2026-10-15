#!/usr/bin/env python3
"""Own-process pipe controls only: no child, signal, Terminal or runtime proof.

Regular-file replacement and consumed-owner tests below cover those exact local
cases, not pipe-to-pipe ABA or concurrent check/use races. Surfaced read errors
are injected at the Python boundary; they do not test CPython's EINTR retries.
"""
from dataclasses import FrozenInstanceError
import errno
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rpc_apple_ci_liveness as pipe


@unittest.skipUnless(os.name == "posix", "POSIX-only descriptor component")
class LivenessControls(unittest.TestCase):
    def pair(self):
        writer, reader = pipe.open_facade_pipe()
        self.addCleanup(writer.close)
        self.addCleanup(reader.close)
        return writer, reader

    def test_actual_descriptors_are_cloexec_and_read_is_nonblocking(self):
        writer, reader = self.pair()
        for fd in (writer._fd, reader._fd):
            self.assertFalse(os.get_inheritable(fd))
            self.assertTrue(pipe.fcntl.fcntl(fd, pipe.fcntl.F_GETFD) & pipe.fcntl.FD_CLOEXEC)
        self.assertFalse(os.get_blocking(reader._fd))

    def test_empty_open_pipe_is_only_undecided_not_facade_lifetime(self):
        _, reader = self.pair()
        for _ in range(3):
            self.assertEqual(reader.observe(), pipe.PipeObservation("UNDECIDED"))
        self.assertIn("NOT_NATIVE_OR_RELEASE_QUALIFICATION", pipe.SCOPE)

    def test_sole_writer_close_is_observed_as_irreversible_eof(self):
        writer, reader = self.pair()
        self.assertTrue(writer.close())
        result = reader.observe()
        self.assertEqual(result, pipe.PipeObservation("CANCEL", "EOF"))
        with patch.object(pipe.os, "read", side_effect=AssertionError("No reads after cancellation")):
            self.assertIs(reader.observe(), result)
        reader.close()
        self.assertIs(reader.observe(), result)

    def test_every_byte_is_invalid_including_extra_and_zero_bytes(self):
        for data in (b"x", b"\0", b"xy", b"\xff" * 64):
            with self.subTest(size=len(data)):
                writer, reader = self.pair()
                self.assertEqual(os.write(writer._fd, data), len(data))
                result = reader.observe()
                self.assertEqual(result, pipe.PipeObservation("CANCEL", "UNEXPECTED_DATA"))
                writer.close()
                with patch.object(pipe.os, "read", side_effect=AssertionError("No drain/recovery")):
                    self.assertIs(reader.observe(), result)

    def test_close_before_observe_is_irreversible(self):
        _, reader = self.pair()
        self.assertTrue(reader.close())
        self.assertEqual(reader.observe(), pipe.PipeObservation("CANCEL", "CLOSED"))
        self.assertTrue(reader.close())

    def test_spawn_plan_preserves_parent_reader_and_never_includes_writer(self):
        writer, reader = self.pair()
        plan = reader.spawn_plan()
        self.assertEqual(plan.pass_fds, (reader._fd,))
        self.assertTrue(plan.close_fds)
        self.assertNotIn(writer._fd, plan.pass_fds)
        self.assertIs(reader.spawn_plan(), plan)
        self.assertEqual(reader.observe().state, "UNDECIDED")  # A failed spawn would leave it owned.
        self.assertFalse(hasattr(writer, "spawn_plan"))
        self.assertFalse(hasattr(writer, "write"))
        with self.assertRaises(FrozenInstanceError):
            plan.close_fds = False

    def test_parent_closes_read_copy_only_after_explicit_success_notification(self):
        writer, reader = self.pair()
        plan = reader.spawn_plan()
        received = os.dup(plan.pass_fds[0])  # Same-process copy, NOT a spawned keeper.
        os.set_inheritable(received, True)  # Emulate pass_fds inheritance for adoption controls.
        child_reader = pipe.KeeperReadEnd.adopt_inherited(received)
        self.addCleanup(child_reader.close)
        self.assertFalse(os.get_inheritable(received))
        self.assertEqual(reader.observe().state, "UNDECIDED")
        self.assertTrue(reader.keeper_started(plan))
        self.assertEqual(child_reader.observe().state, "UNDECIDED")
        self.assertIsNotNone(writer._fd)
        self.assertTrue(writer.close())
        self.assertEqual(child_reader.observe(), pipe.PipeObservation("CANCEL", "EOF"))

    def test_foreign_stale_or_replayed_spawn_plan_cannot_close_reader(self):
        _, reader = self.pair()
        plan = reader.spawn_plan()
        for invalid in (None, pipe.KeeperSpawnPlan(plan.pass_fds), object()):
            with self.assertRaises(ValueError):
                reader.keeper_started(invalid)
            self.assertEqual(reader.observe().state, "UNDECIDED")
        self.assertTrue(reader.keeper_started(plan))
        with self.assertRaises(ValueError):
            reader.keeper_started(plan)

    def test_cancelled_reader_cannot_offer_another_transfer(self):
        writer, reader = self.pair()
        writer.close()
        reader.observe()
        with self.assertRaises(ValueError):
            reader.spawn_plan()

    def test_reader_adoption_never_takes_or_closes_the_parent_writer(self):
        writer, reader = self.pair()
        fd = writer._fd
        flags = pipe.fcntl.fcntl(fd, pipe.fcntl.F_GETFD)
        with self.assertRaises(ValueError):
            pipe.KeeperReadEnd.adopt_inherited(fd)
        self.assertEqual(flags, pipe.fcntl.fcntl(fd, pipe.fcntl.F_GETFD))
        self.assertEqual(reader.observe().state, "UNDECIDED")
        writer.close()
        self.assertEqual(reader.observe().reason, "EOF")

    def test_invalid_descriptor_numbers_are_refused_without_any_fd_operation(self):
        for value in (None, True, 0, 1, 2, -1, 3.0, "3"):
            with self.subTest(value=value), patch.object(pipe.os, "fstat") as probe:
                with self.assertRaises(ValueError):
                    pipe.KeeperReadEnd.adopt_inherited(value)
                probe.assert_not_called()

    def test_unrelated_file_is_not_closed_or_reconfigured_on_refused_adoption(self):
        with tempfile.TemporaryFile() as owned_file:
            fd = owned_file.fileno()
            flags = pipe.fcntl.fcntl(fd, pipe.fcntl.F_GETFD)
            with self.assertRaises(ValueError):
                pipe.KeeperReadEnd.adopt_inherited(fd)
            self.assertEqual(flags, pipe.fcntl.fcntl(fd, pipe.fcntl.F_GETFD))
            owned_file.write(b"still owned by this test")

    def test_blocking_reader_is_refused_without_adoption_or_flag_repair(self):
        read_fd, write_fd = os.pipe()
        try:
            with self.assertRaises(ValueError):
                pipe.KeeperReadEnd.adopt_inherited(read_fd)
            self.assertTrue(os.get_blocking(read_fd))
            os.fstat(write_fd)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_lost_nonblocking_flag_refuses_before_read_and_cannot_recover(self):
        _, reader = self.pair()
        os.set_blocking(reader._fd, True)
        with patch.object(pipe.os, "read") as read:
            result = reader.observe()
            read.assert_not_called()
        self.assertEqual(result.reason, "DESCRIPTOR_FLAGS")
        os.set_blocking(reader._fd, False)
        self.assertIs(reader.observe(), result)

    def test_inheritable_reader_is_refused_not_silently_repaired_during_observation(self):
        _, reader = self.pair()
        os.set_inheritable(reader._fd, True)
        self.assertEqual(reader.observe().reason, "DESCRIPTOR_FLAGS")
        self.assertTrue(os.get_inheritable(reader._fd))
        os.set_inheritable(reader._fd, False)
        self.assertEqual(reader.observe().state, "CANCEL")

    def test_surfaced_read_errors_latch_without_application_level_retry(self):
        for code in (errno.EIO, errno.EPERM, errno.EINTR):
            _, reader = self.pair()
            with self.subTest(errno=code), patch.object(pipe.os, "read", side_effect=OSError(code, "fixture")) as read:
                result = reader.observe()
                self.assertEqual(result.reason, "READ_ERROR")
                self.assertIs(reader.observe(), result)
                read.assert_called_once_with(reader._fd, 1)

    def test_only_would_block_is_undecided_not_an_arbitrary_blocking_error(self):
        for code in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EIO):
            _, reader = self.pair()
            with patch.object(pipe.os, "read", side_effect=BlockingIOError(code, "fixture")):
                self.assertEqual(reader.observe().state, "CANCEL" if code == errno.EIO else "UNDECIDED")

    def test_invalid_read_return_cancels(self):
        for value in (None, "", False, bytearray()):
            _, reader = self.pair()
            with patch.object(pipe.os, "read", return_value=value):
                self.assertEqual(reader.observe().reason, "READ_RESULT_INVALID")

    def test_ebadf_observation_relinquishes_local_number_before_later_file_reuse(self):
        _, reader = self.pair()
        fd = reader._fd
        with tempfile.TemporaryFile() as owned_file:
            os.close(fd)  # Deliberate local contract violation; never a foreign descriptor.
            self.assertEqual(reader.observe().reason, "DESCRIPTOR_UNCERTAIN")
            os.dup2(owned_file.fileno(), fd)
            try:
                self.assertFalse(reader.close())
                self.assertEqual(os.fstat(fd).st_ino, os.fstat(owned_file.fileno()).st_ino)
            finally:
                os.close(fd)

    def test_readonly_pipe_to_regular_file_mismatch_refuses_read_and_close(self):
        _, reader = self.pair()
        fd = reader._fd
        with tempfile.TemporaryFile() as owned_file:
            os.dup2(owned_file.fileno(), fd)  # Replace only this test's pipe endpoint.
            try:
                with patch.object(pipe.os, "read") as read:
                    self.assertEqual(reader.observe().reason, "DESCRIPTOR_UNCERTAIN")
                    read.assert_not_called()
                self.assertFalse(reader.close())
                os.fstat(fd)
            finally:
                os.close(fd)

    def test_consumed_owners_do_not_repeat_close_after_regular_file_reuse(self):
        writer, reader = self.pair()
        for owner in (writer, reader):
            fd = owner._fd
            with tempfile.TemporaryFile() as owned_file:
                self.assertTrue(owner.close())
                os.dup2(owned_file.fileno(), fd)
                try:
                    with patch.object(pipe.os, "close", side_effect=AssertionError("Double-close forbidden")):
                        self.assertTrue(owner.close())
                    os.fstat(fd)
                finally:
                    os.close(fd)

    def test_close_error_consumes_local_state_before_mocked_file_reuse(self):
        writer, reader = self.pair()
        fd = writer._fd
        real_close = os.close
        with tempfile.TemporaryFile() as owned_file:
            def uncertain_close(value):
                self.assertEqual(value, fd)
                self.assertIsNone(writer._fd)
                real_close(value)
                os.dup2(owned_file.fileno(), value)
                raise OSError(errno.EINTR, "fixture close result uncertain")
            with patch.object(pipe.os, "close", side_effect=uncertain_close) as close:
                self.assertFalse(writer.close())
                self.assertFalse(writer.close())
                close.assert_called_once_with(fd)
            try:
                os.fstat(fd)
                self.assertEqual(reader.observe().reason, "EOF")
            finally:
                real_close(fd)

    def test_ebadf_read_error_does_not_later_close_that_number(self):
        _, reader = self.pair()
        fd = reader._fd
        try:
            with patch.object(pipe.os, "read", side_effect=OSError(errno.EBADF, "fixture")):
                self.assertEqual(reader.observe().reason, "READ_ERROR")
            with patch.object(pipe.os, "close", side_effect=AssertionError("Unknown fd must not close")):
                self.assertFalse(reader.close())
        finally:
            os.close(fd)  # The mocked error left this test-owned descriptor open.

    def test_factory_failure_closes_both_own_descriptors(self):
        real_pipe = os.pipe
        allocated = []
        def allocate():
            result = real_pipe()
            allocated.extend(result)
            return result
        with patch.object(pipe.os, "pipe", side_effect=allocate), \
                patch.object(pipe.os, "set_blocking", side_effect=OSError(errno.EIO, "fixture")):
            with self.assertRaises(OSError):
                pipe.open_facade_pipe()
        self.assertEqual(len(allocated), 2)
        for fd in allocated:
            with self.assertRaises(OSError) as error:
                os.fstat(fd)
            self.assertEqual(error.exception.errno, errno.EBADF)

    def test_partial_factory_ownership_is_cleaned_up_without_double_close(self):
        real_pipe = os.pipe
        allocated = []
        def allocate():
            result = real_pipe()
            allocated.extend(result)
            return result
        with patch.object(pipe.os, "pipe", side_effect=allocate), \
                patch.object(pipe, "FacadeWriteEnd", side_effect=ValueError("fixture construction refused")):
            with self.assertRaises(ValueError):
                pipe.open_facade_pipe()
        for fd in allocated:
            with self.assertRaises(OSError) as error:
                os.fstat(fd)
            self.assertEqual(error.exception.errno, errno.EBADF)

    def test_factory_cleanup_error_does_not_skip_the_other_owned_endpoint(self):
        real_pipe, real_close = os.pipe, os.close
        allocated, closed = [], []
        def allocate():
            result = real_pipe()
            allocated.extend(result)
            return result
        def close_once(fd):
            self.assertIn(fd, allocated)
            self.assertNotIn(fd, closed)
            real_close(fd)
            closed.append(fd)
            if len(closed) == 1:
                raise OSError(errno.EINTR, "fixture close result uncertain")
        with patch.object(pipe.os, "pipe", side_effect=allocate), \
                patch.object(pipe.os, "set_blocking", side_effect=OSError(errno.EIO, "fixture")), \
                patch.object(pipe.os, "close", side_effect=close_once):
            with self.assertRaisesRegex(OSError, "cleanup uncertain"):
                pipe.open_facade_pipe()
        self.assertEqual(closed, allocated)
        for fd in allocated:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_writeonly_pipe_to_regular_file_mismatch_refuses_close(self):
        writer, _ = self.pair()
        fd = writer._fd
        with tempfile.TemporaryFile() as owned_file:
            os.dup2(owned_file.fileno(), fd)
            try:
                self.assertFalse(writer.close())
                os.fstat(fd)
            finally:
                os.close(fd)

    def test_unknown_descriptor_observation_remains_cancelled_after_plausible_reads(self):
        _, reader = self.pair()
        fd = reader._fd
        try:
            with patch.object(pipe.os, "fstat", side_effect=OSError(errno.EPERM, "fixture")):
                result = reader.observe()
            self.assertEqual(result.reason, "DESCRIPTOR_UNCERTAIN")
            self.assertIs(reader.observe(), result)
            self.assertFalse(reader.close())
        finally:
            os.close(fd)  # Mocked denial; descriptor was still this test's pipe.


if __name__ == "__main__":
    unittest.main(verbosity=2)
