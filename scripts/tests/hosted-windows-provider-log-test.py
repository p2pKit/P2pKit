#!/usr/bin/env python3
"""Fixed provider-log overlapping readback models, NOT native qualification."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("provider_log_sharing_models",
    Path(__file__).with_name("hosted-windows-provider-command-test.py"))
sharing = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sharing
spec.loader.exec_module(sharing)
files, base = sharing.files, sharing.base


class FalseyCancellation(BaseException):
    def __bool__(self):
        raise AssertionError("MODEL_EXCEPTION_MUST_NOT_BE_TRUTH_TESTED")


def caught(operation):
    try:
        operation()
    except BaseException as error:
        return error
    raise AssertionError("MODEL_EXPECTED_FAILURE")


class ProviderLogCallShapeModels(unittest.TestCase):
    setUp = base.NativeCallShapeTests.setUp
    convert = base.NativeCallShapeTests.convert
    create = base.NativeCallShapeTests.create
    free = base.NativeCallShapeTests.free
    close = base.NativeCallShapeTests.close

    def test_only_fixed_existing_log_names_have_read_access_share_three_without_delete(self):
        for name in files.PROVIDER_LOG_NAMES:
            with self.subTest(name=name):
                self.setUp()
                self.native_information = 1
                self.assertEqual(self.api.provider_log_reader(17, name), 202)
                self.assertEqual(self.calls, [{"parent": 17, "attributes": 0x40, "security": None,
                    "name": name, "length": len(name) * 2, "maximum": len(name) * 2 + 2,
                    "access": 0x00120081, "flags": 0x80, "sharing": 3, "disposition": 1,
                    "options": 0x00200060, "allocation": None, "ea": None, "ea_size": 0}])
                self.assertEqual(self.events, [("create",)])

    def test_name_access_creation_and_sharing_aliases_refuse_before_native_call(self):
        for name in ("provider-output.txt", "ordinary.log", "PROVIDER-STDOUT.LOG", "../provider-stdout.log", None, True):
            with self.subTest(name=name), self.assertRaises(files.FilesystemError):
                self.api.provider_log_reader(17, name)
        for options in ({"directory": True, "create": False, "writable": False, "sharing": 3},
                        {"directory": False, "create": True, "writable": False, "sharing": 3},
                        {"directory": False, "create": False, "writable": True, "sharing": 3},
                        {"directory": False, "create": False, "writable": False, "sharing": 7},
                        {"directory": False, "create": False, "writable": False, "sharing": True}):
            with self.subTest(options=options), self.assertRaises(files.FilesystemError):
                self.api._child(17, "provider-stdout.log", **options)
        self.assertEqual(self.calls, [])

    def test_ordinary_writer_and_reader_still_deny_write_delete_sharing(self):
        self.api.child(17, "provider-stdout.log", directory=False, create=True, writable=True)
        self.native_information = 1
        self.api.child(17, "provider-stdout.log", directory=False)
        self.assertEqual([(row["access"], row["sharing"], row["disposition"]) for row in self.calls],
                         [(0x00120082, 1, 2), (0x00120081, 1, 1)])

    def test_wrong_open_disposition_retires_returned_handle_once(self):
        self.native_information = 2
        with self.assertRaises(files.FilesystemError):
            self.api.provider_log_reader(17, "provider-stdout.log")
        self.assertEqual(self.events, [("create",), ("close", 202)])


class ProviderLogReadbackModels(unittest.TestCase):
    def setUp(self):
        self.elapsed = 100.0
        self.clock = patch.object(files, "time", SimpleNamespace(monotonic=lambda: self.elapsed))
        self.clock.start()
        self.api = sharing.ShareApi()
        self.root = files._root(r"C:\work\private", self.api, create=True)
        self.writers, self.unreturned_readers = [], []

    def tearDown(self):
        # Only model disposal after all once-only/UNKNOWN assertions. This is
        # not a production recovery path or evidence of real handle retirement.
        self.elapsed, self.api.close_failure = 100.0, None
        for handle in self.unreturned_readers:
            if handle in self.api.handles:
                self.api.close(handle)
        for writer in reversed(self.writers):
            handle = writer._provider_log_reader
            if handle in self.api.handles:
                self.api.close(handle)
            writer._provider_log_unknown = writer._provider_log_active = False
            writer.close()
        self.root.close()
        self.clock.stop()
        self.assertEqual(self.api.handles, {})

    def writer(self, data=b"MODEL_PRIVATE_LOG", *, name="provider-stdout.log", maximum=1024 * 1024):
        writer = self.root.create_file(name, max_bytes=maximum, deadline=120.0)
        self.writers.append(writer)
        writer.write(data)
        return writer

    def node(self, writer):
        return self.api.nodes[str(writer.path)]

    def temporary(self):
        return [handle for handle, mode in self.api.modes.items() if mode == (1, 3)]

    def assert_repeat_preserves(self, writer, original):
        before = list(self.api.events)
        self.assertIs(caught(writer.read_provider_log), original)
        self.assertEqual(self.api.events, before)

    def assert_pinned_unknown(self, writer, original):
        self.assertTrue(writer._provider_log_unknown)
        self.assertFalse(writer.closed)
        self.assertIn(writer._pins[-1].handle, self.api.handles)
        before = list(self.api.events)
        self.assertIs(caught(writer.close), original)
        self.assert_repeat_preserves(writer, original)
        for operation in (writer.verify, lambda: writer.native_handle, lambda: writer.write(b"x")):
            self.assertIsInstance(caught(operation), files.FilesystemError)
        self.assertFalse(writer.readable() or writer.writable() or writer.seekable())
        self.assertEqual(self.api.events, before)

    def test_bytes_return_only_after_temporary_reader_closes_with_original_writer_and_ancestors_pinned(self):
        writer = self.writer()
        original, position = writer.native_handle, writer.tell()
        self.root.close()  # The writer's original ancestor pins must suffice.
        value = writer.read_provider_log()
        self.assertIs(type(value), bytes)
        self.assertEqual(value, b"MODEL_PRIVATE_LOG")
        self.assertEqual(writer.tell(), position)
        self.assertFalse(writer.closed)
        self.assertTrue(writer.writable())
        self.assertFalse(writer.readable())
        self.assertEqual(self.api.modes[original], (2, 1))
        temporary = [event[1] for event in self.api.events if event[0] == "sharing" and event[2:] == (1, 3)]
        self.assertEqual(len(temporary), 1)
        self.assertEqual(sum(event[:2] == ("close", temporary[0]) for event in self.api.events), 1)
        self.assertFalse(any(event[:2] == ("close", original) for event in self.api.events))
        self.assertIsNone(writer._provider_log_reader)
        self.assertEqual(writer._deadline, 120.0)
        before = list(self.api.events)
        self.assertRegex(str(caught(writer.read_provider_log)), "one-use")
        self.assertEqual(self.api.events, before)

    def test_competing_write_and_delete_are_denied_during_open_read_and_both_sides_of_temporary_close(self):
        writer = self.writer()
        original, node, seen = writer.native_handle, self.node(writer), []
        read, opener, close = self.api.read, self.api.provider_log_reader, self.api.close
        def denial(stage):
            self.assertIn(original, self.api.handles)
            for access in (2, 4):
                with self.assertRaisesRegex(files.FilesystemError, "sharing"):
                    self.api.shared_open(node, access, 7)
            seen.append(stage)
        def opening(*args):
            denial("open")
            return opener(*args)
        def reading(*args):
            denial("read")
            return read(*args)
        def closing(handle):
            if self.api.modes[handle] == (1, 3):
                denial("preclose")
                close(handle)
                denial("postclose")
            else:
                close(handle)
        with patch.object(self.api, "provider_log_reader", opening), patch.object(self.api, "read", reading), \
                patch.object(self.api, "close", closing):
            self.assertEqual(writer.read_provider_log(), b"MODEL_PRIVATE_LOG")
        self.assertEqual(seen, ["open", "read", "preclose", "postclose"])

    def test_missing_original_writer_pin_cannot_make_permissive_readback_a_standalone_reader(self):
        writer = self.writer()
        writer.close()
        before = list(self.api.events)
        self.assertIsInstance(caught(writer.read_provider_log), files.FilesystemError)
        self.assertEqual(self.api.events, before)
        self.assertEqual(self.temporary(), [])

    def test_fixed_names_and_one_mib_cap_refuse_before_opening_a_readback_handle(self):
        for name, maximum in (("ordinary.log", 1024), ("provider-stderr.log", 1024 * 1024 + 1)):
            with self.subTest(name=name):
                writer = self.writer(name=name, maximum=maximum)
                before = list(self.api.events)
                self.assertIsInstance(caught(writer.read_provider_log), files.FilesystemError)
                self.assertEqual(self.api.events, before)
        self.assertEqual(self.temporary(), [])

    def test_empty_and_multi_chunk_outputs_are_exact_and_bounded(self):
        empty = self.writer(b"", maximum=0)
        self.assertEqual(empty.read_provider_log(), b"")
        self.assertEqual(self.api.read_sizes, [])
        data = b"x" * (files.CHUNK * 2 + 7)
        other = self.writer(data, name="provider-stderr.log", maximum=len(data))
        self.assertEqual(other.read_provider_log(), data)
        self.assertEqual(self.api.read_sizes, [files.CHUNK, files.CHUNK, 7])
        self.assertEqual(self.temporary(), [])

    def test_readback_cannot_accept_a_new_deadline_argument(self):
        writer = self.writer()
        before = list(self.api.events)
        with self.assertRaises(TypeError):
            writer.read_provider_log(deadline=900.0)
        self.assertEqual(self.api.events, before)
        self.assertFalse(writer._provider_log_started)

    def test_open_identity_change_is_rejected_and_temporary_reader_is_closed(self):
        writer = self.writer()
        node, opener = self.node(writer), self.api.provider_log_reader
        def replaced(*args):
            handle = opener(*args)
            node.version += 1
            return handle
        with patch.object(self.api, "provider_log_reader", replaced):
            error = caught(writer.read_provider_log)
        self.assertRegex(str(error), "identity or metadata")
        self.assertEqual(self.temporary(), [])
        self.assertFalse(writer.closed)
        self.assert_repeat_preserves(writer, error)

    def test_changed_size_or_metadata_after_read_refuses_immutable_byte_return(self):
        for index, change in enumerate((lambda node: setattr(node, "content", node.content + b"x"),
                                        lambda node: setattr(node, "version", node.version + 1))):
            with self.subTest(change=index):
                writer = self.writer(name=files.PROVIDER_LOG_NAMES[index])
                read, node = self.api.read, self.node(writer)
                def changed(*args):
                    result = read(*args)
                    change(node)
                    return result
                with patch.object(self.api, "read", changed):
                    error = caught(writer.read_provider_log)
                self.assertRegex(str(error), "changed during readback")
                self.assertEqual(self.temporary(), [])
                self.assert_repeat_preserves(writer, error)

    def test_post_read_ads_or_acl_change_remains_a_strict_inspection_failure(self):
        writer = self.writer()
        read, node = self.api.read, self.node(writer)
        def changed(*args):
            result = read(*args)
            node.extra_stream = True
            return result
        try:
            with patch.object(self.api, "read", changed):
                self.assertRegex(str(caught(writer.read_provider_log)), "privacy/ADS")
            self.assertEqual(self.temporary(), [])
        finally:
            node.extra_stream = False  # Model disposal only.

    def test_truncated_or_oversized_native_read_never_retries(self):
        for index, value in enumerate((b"", b"x" * 100)):
            with self.subTest(value_bytes=len(value)):
                writer = self.writer(name=files.PROVIDER_LOG_NAMES[index])
                with patch.object(self.api, "read", return_value=value) as read:
                    error = caught(writer.read_provider_log)
                self.assertRegex(str(error), "truncated or oversized")
                self.assertEqual(read.call_count, 1)
                self.assertEqual(self.temporary(), [])
                self.assert_repeat_preserves(writer, error)

    def test_falsey_open_cancellation_remains_first_and_does_not_release_original_writer(self):
        writer, original = self.writer(), FalseyCancellation("MODEL_OPEN_CANCEL")
        with patch.object(self.api, "provider_log_reader", side_effect=original):
            self.assertIs(caught(writer.read_provider_log), original)
        self.assertFalse(writer.closed)
        self.assertEqual(self.temporary(), [])
        self.assert_pinned_unknown(writer, original)

    def test_unreturned_opener_with_unknown_cleanup_keeps_original_pin_and_first_error(self):
        for index, released in enumerate((False, True)):
            with self.subTest(released_before_error=released):
                writer = self.writer(name=files.PROVIDER_LOG_NAMES[index])
                original = FalseyCancellation("MODEL_OPENER_REJECTED")
                opener, close, attempts = self.api.provider_log_reader, self.api.close, []
                def uncertain(handle):
                    attempts.append(handle)
                    if released:
                        close(handle)
                    raise files.FilesystemError("MODEL_CLOSE_FAILED")
                def unreturned(*args):
                    handle = opener(*args)
                    self.unreturned_readers.append(handle)
                    # Model the maintained opener's provisional-handle cleanup:
                    # failed close is retained, but the new handle never returns.
                    files._cleanup((lambda: files._close_native(self.api, handle),), original)
                    raise original
                with patch.object(self.api, "provider_log_reader", unreturned), patch.object(self.api, "close", uncertain):
                    self.assertIs(caught(writer.read_provider_log), original)
                handle = self.unreturned_readers[-1]
                self.assertEqual(attempts, [handle])
                self.assertIsNone(writer._provider_log_reader)
                self.assertEqual(handle in self.api.handles, not released)
                self.assertIn("UNKNOWN", " ".join(original.__notes__))
                self.assert_pinned_unknown(writer, original)

    def test_note_or_cause_only_supplier_unknown_stays_pinned_after_known_reader_close(self):
        for index, carrier in enumerate(("note", "cause")):
            with self.subTest(carrier=carrier):
                writer, original = self.writer(name=files.PROVIDER_LOG_NAMES[index]), FalseyCancellation("MODEL_INSPECT")
                if carrier == "note":
                    original.__notes__ = ["MODEL native obligation retirement UNKNOWN"]
                else:
                    original.__cause__ = files.FilesystemError("MODEL native obligation retirement UNKNOWN")
                inspect = self.api.inspect
                def failed(handle, *args, **kwargs):
                    if self.api.modes[handle] == (1, 3):
                        raise original
                    return inspect(handle, *args, **kwargs)
                with patch.object(self.api, "inspect", failed):
                    self.assertIs(caught(writer.read_provider_log), original)
                self.assertIsNone(writer._provider_log_reader)
                self.assertEqual(self.temporary(), [])
                self.assert_pinned_unknown(writer, original)

    def test_diagnostic_attachment_failure_never_replaces_read_or_close_primary(self):
        for index, stage in enumerate(("read", "close")):
            with self.subTest(stage=stage):
                writer = self.writer(name=files.PROVIDER_LOG_NAMES[index])
                diagnostic = RuntimeError("MODEL_NOTE_ATTACHMENT_FAILED")
                class Unnotable(FalseyCancellation):
                    def add_note(self, _message):
                        raise diagnostic
                original = Unnotable("MODEL_" + stage.upper() + "_CANCEL")
                operation = getattr(self.api, stage)
                def failed(handle, *args):
                    if self.api.modes[handle] == (1, 3):
                        raise original
                    return operation(handle, *args)
                with patch.object(self.api, stage, failed):
                    self.assertIs(caught(writer.read_provider_log), original)
                self.assertIn(diagnostic, writer._provider_log_secondary)
                self.assertEqual(writer._provider_log_reader is None, stage == "read")
                self.assert_pinned_unknown(writer, original)

    def test_read_cancellation_plus_uncertain_close_retains_both_originals_and_refuses_all_further_native_use(self):
        writer, original = self.writer(), FalseyCancellation("MODEL_READ_CANCEL")
        handle = writer.native_handle
        def cancelled(reader, _count):
            self.api.close_failure = reader
            raise original
        with patch.object(self.api, "read", cancelled):
            self.assertIs(caught(writer.read_provider_log), original)
        self.assertTrue(writer._provider_log_unknown)
        self.assertIsNotNone(writer._provider_log_reader)
        self.assertTrue(writer._provider_log_secondary)
        self.assertIn("UNKNOWN", " ".join(original.__notes__))
        self.assertIn(handle, self.api.handles)
        self.assertFalse(writer.closed)
        before = list(self.api.events)
        self.assertIs(caught(writer.close), original)
        for operation in (writer.verify, lambda: writer.native_handle, lambda: writer.write(b"x")):
            self.assertIsInstance(caught(operation), files.FilesystemError)
        self.assertFalse(writer.readable() or writer.writable() or writer.seekable())
        self.assertEqual(self.api.events, before)
        self.assert_repeat_preserves(writer, original)

    def test_failed_temporary_close_before_release_is_never_retried(self):
        writer, original = self.writer(), FalseyCancellation("MODEL_CLOSE_CANCEL")
        close = self.api.close
        def failed(handle):
            if self.api.modes[handle] == (1, 3):
                raise original
            close(handle)
        with patch.object(self.api, "close", failed):
            self.assertIs(caught(writer.read_provider_log), original)
        self.assertTrue(writer._provider_log_unknown)
        self.assertIn(writer._provider_log_reader, self.api.handles)
        self.assert_repeat_preserves(writer, original)

    def test_slow_read_and_slow_close_spend_original_end_without_losing_known_reader_close(self):
        for index, stage in enumerate(("read", "close")):
            with self.subTest(stage=stage):
                self.elapsed = 100.0
                writer = self.writer(name=files.PROVIDER_LOG_NAMES[index])
                operation = getattr(self.api, stage)
                def late(*args):
                    result = operation(*args)
                    self.elapsed = 120.0
                    return result
                with patch.object(self.api, stage, late):
                    error = caught(writer.read_provider_log)
                self.assertRegex(str(error), "deadline")
                self.assertIsNone(writer._provider_log_reader)
                self.assertFalse(writer.closed)
                self.assert_pinned_unknown(writer, error)

    def test_original_read_failure_survives_late_successful_reader_close(self):
        writer, original = self.writer(), FalseyCancellation("MODEL_READ_CANCEL")
        close = self.api.close
        def late(handle):
            close(handle)
            self.elapsed = 120.0
        with patch.object(self.api, "read", side_effect=original), patch.object(self.api, "close", late):
            self.assertIs(caught(writer.read_provider_log), original)
        self.assertTrue(writer._provider_log_secondary)
        self.assertIsNone(writer._provider_log_reader)
        self.assert_pinned_unknown(writer, original)

    def test_buffer_growth_spends_original_end_before_next_read_or_terminal_inspect(self):
        for index, size in enumerate((1, files.CHUNK + 1)):
            with self.subTest(size=size):
                self.elapsed = 100.0
                writer = self.writer(b"x" * size, name=files.PROVIDER_LOG_NAMES[index])
                late_inspects, inspect = [], self.api.inspect
                test = self
                class SlowGrowth(bytearray):
                    def extend(self, value):
                        super().extend(value)
                        test.elapsed = 120.0
                def observed(*args, **kwargs):
                    if self.elapsed >= 120.0:
                        late_inspects.append(args[0])
                    return inspect(*args, **kwargs)
                with patch.object(files, "bytearray", SlowGrowth, create=True), \
                        patch.object(self.api, "inspect", observed), patch.object(self.api, "read", wraps=self.api.read) as read:
                    error = caught(writer.read_provider_log)
                self.assertRegex(str(error), "deadline")
                self.assertEqual(read.call_count, 1)
                self.assertEqual(late_inspects, [])
                self.assertIsNone(writer._provider_log_reader)
                self.assert_pinned_unknown(writer, error)

    def test_caught_readback_or_writer_close_reentry_is_sticky_without_releasing_original_pin(self):
        for index, name in enumerate(("read_provider_log", "close")):
            with self.subTest(operation=name):
                writer = self.writer(name=files.PROVIDER_LOG_NAMES[index])
                original, read, nested = writer.native_handle, self.api.read, []
                def reentered(*args):
                    nested.append(caught(getattr(writer, name)))
                    self.assertIn(original, self.api.handles)
                    return read(*args)
                with patch.object(self.api, "read", reentered):
                    self.assertIs(caught(writer.read_provider_log), nested[0])
                self.assertEqual(self.temporary(), [])
                self.assertIn(original, self.api.handles)
                self.assert_repeat_preserves(writer, nested[0])

    def test_caught_reentry_at_last_reader_close_cannot_publish_otherwise_complete_bytes(self):
        writer = self.writer()
        close, nested = self.api.close, []
        def reentered(handle):
            close(handle)
            nested.append(caught(writer.read_provider_log))
        with patch.object(self.api, "close", reentered):
            self.assertIs(caught(writer.read_provider_log), nested[0])
        self.assertIsNone(writer._provider_log_reader)
        self.assert_pinned_unknown(writer, nested[0])


if __name__ == "__main__":
    unittest.main()
