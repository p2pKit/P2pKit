#!/usr/bin/env python3
"""Bounded native-call/sharing models only; never Windows/provider qualification."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("command_file_models",
    Path(__file__).with_name("hosted-windows-files-test.py"))
base = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = base
SPEC.loader.exec_module(base)
files = base.files
NAME = "provider-output.txt"


class ShareApi(base.ModelApi):
    """Two-way READ/WRITE/DELETE sharing model, not a Win32 or libuv execution."""
    def __init__(self):
        super().__init__()
        self.modes = {}

    def shared_open(self, node, access, sharing):
        for handle, (other, _, _) in self.handles.items():
            if other is node:
                old_access, old_share = self.modes[handle]
                files.require(not (access & ~old_share or old_access & ~sharing), "Modeled sharing violation")
        handle = super()._open(node, bool(access & 2))
        self.modes[handle] = (access, sharing)
        self.events.append(("sharing", handle, access, sharing))
        return handle

    def _open(self, node, writable=False):
        return self.shared_open(node, 2 if writable else 1, 1)

    def provider_command_file(self, parent):
        directory = self.handles[parent][0]
        path = directory.path + "\\" + NAME
        files.require(path not in self.nodes, "Modeled FILE_CREATE collision")
        node = base.Node(path, False, self.next_id, private=True)
        self.next_id += 1
        self.nodes[path] = node
        directory.version += 1
        self.events.append(("create-with-protected-acl", path, self.policy.sddl(False)))
        return self.shared_open(node, 1, 3)

    def provider_log_reader(self, parent, name):
        files.require(type(name) is str and name in files.PROVIDER_LOG_NAMES, "Modeled provider log name")
        directory = self.handles[parent][0]
        path = directory.path + "\\" + name
        files.require(path in self.nodes and not self.nodes[path].directory, "Modeled provider log missing/wrong-kind")
        return self.shared_open(self.nodes[path], 1, 3)

    def close(self, handle):
        try:
            super().close(handle)
        finally:
            if handle not in self.handles:
                self.modes.pop(handle, None)


class ProviderCallShapeTests(unittest.TestCase):
    setUp = base.NativeCallShapeTests.setUp
    convert = base.NativeCallShapeTests.convert
    create = base.NativeCallShapeTests.create
    free = base.NativeCallShapeTests.free
    close = base.NativeCallShapeTests.close

    def test_creator_is_fixed_relative_read_access_share_read_write_without_delete(self):
        self.assertEqual(self.api.provider_command_file(17), 202)
        self.assertEqual(self.calls, [{"parent": 17, "attributes": 0x40, "security": 101,
            "name": NAME, "length": len(NAME) * 2, "maximum": len(NAME) * 2 + 2,
            "access": 0x00120081, "flags": 0x80, "sharing": 3, "disposition": 2,
            "options": 0x00200060, "allocation": None, "ea": None, "ea_size": 0}])
        self.assertEqual(self.events, [("descriptor", base.POLICY.sddl(False), 1), ("create",), ("free", 101)])

    def test_ordinary_freeze_open_keeps_original_read_only_sharing(self):
        self.api.child(17, NAME, directory=False)
        self.assertEqual((self.calls[0]["access"], self.calls[0]["sharing"], self.calls[0]["disposition"]),
                         (0x00120081, 1, 1))
        self.assertIsNone(self.calls[0]["security"])

    def test_creator_has_no_path_or_share_mask_option(self):
        with self.assertRaises(TypeError):
            self.api.provider_command_file(17, name="other", sharing=7)
        self.assertEqual(self.calls, [])

    def test_factored_internal_creator_rejects_other_shared_write_shapes(self):
        for name, create, writable, sharing in (("other", True, False, 3), (NAME, False, False, 3),
                (NAME, True, True, 3), (NAME, True, False, 7), (NAME, True, False, True)):
            with self.subTest(name=name, sharing=sharing), self.assertRaises(files.FilesystemError):
                self.api._child(17, name, directory=False, create=create, writable=writable, sharing=sharing)
        self.assertEqual(self.calls, [])

    def test_creator_wrong_disposition_and_descriptor_failure_retire_partial_handles(self):
        for disposition, failed_free in ((3, False), (2, True)):
            with self.subTest(disposition=disposition, failed_free=failed_free):
                self.setUp()
                self.native_information, self.fail_free = disposition, failed_free
                with self.assertRaises(files.FilesystemError):
                    self.api.provider_command_file(17)
                self.assertEqual(self.events[-2:], [("free", 101), ("close", 202)])


class ProviderCommandModels(unittest.TestCase):
    def setUp(self):
        self.elapsed = 100.0
        self.clock = patch.object(files, "time", SimpleNamespace(monotonic=lambda: self.elapsed))
        self.clock.start()
        self.api = ShareApi()
        self.root = files._root(r"C:\work\private", self.api, create=True)
        self.owners = [self.root]

    def tearDown(self):
        self.api.close_failure = None
        try:
            for owner in reversed(self.owners):
                owner.close()
            self.assertEqual(self.api.handles, {})
        finally:
            self.clock.stop()

    def command(self, maximum=4096, end=120.0):
        command = self.root.create_provider_command_file(max_bytes=maximum, deadline=end)
        self.owners.append(command)
        return command

    def node(self):
        return self.api.nodes[r"C:\work\private\provider-output.txt"]

    def append(self, data):
        node = self.node()
        handle = self.api.shared_open(node, 2, 7)
        self.api.seek(handle, len(node.content), 0)
        self.api.write(handle, data)
        self.api.close(handle)

    def freeze(self, command):
        reader = command.freeze()
        self.owners.append(reader)
        return reader

    def test_actual_owner_allows_path_append_then_freezes_without_an_unpinned_gap(self):
        command = self.command()
        original = command._pins[-1].handle
        self.assertEqual(self.api.modes[original], (1, 3))
        self.assertFalse(command._pins[-1].writable)
        self.append(b"original commands\r\n")
        self.assertEqual(command.observe().size, 19)
        self.assertFalse(hasattr(command, "final_info"))
        self.root.close()
        reader = self.freeze(command)
        strict = reader.native_handle
        self.assertEqual(self.api.modes[strict], (1, 1))
        events = self.api.events
        opened = next(i for i, event in enumerate(events) if event[:2] == ("open", strict))
        retired = next(i for i, event in enumerate(events) if event[:2] == ("close", original))
        self.assertLess(opened, retired)
        self.assertTrue(all(pin.references > 0 for pin in reader._pins))
        self.assertEqual(reader.read(), b"original commands\r\n")
        self.assertEqual(reader.verify(), reader.initial_info)
        self.assertEqual(reader._deadline, 120.0)
        self.assertFalse(any(event[0] == "flush" for event in events))

    def test_live_owner_exposes_no_native_writer_reader_or_descriptor_api(self):
        command = self.command()
        for name in ("native_handle", "fileno", "write", "read", "readall", "writable", "sync"):
            self.assertFalse(hasattr(command, name), name)

    def test_existing_file_is_never_adopted_truncated_or_deleted(self):
        command = self.command()
        self.append(b"sentinel")
        identity = command.identity
        with self.assertRaisesRegex(files.FilesystemError, "collision"):
            self.command()
        self.assertEqual(self.node().content, b"sentinel")
        self.assertEqual(command.observe().identity, identity)

    def test_actual_ordinary_writer_blocks_path_append_and_cannot_be_used_as_this_capability(self):
        stream = self.root.create_file("ordinary.log", max_bytes=32, deadline=120)
        self.owners.append(stream)
        node = self.api.nodes[r"C:\work\private\ordinary.log"]
        with self.assertRaisesRegex(files.FilesystemError, "sharing"):
            self.api.shared_open(node, 2, 7)
        self.assertEqual(self.api.modes[stream.native_handle], (2, 1))

    def test_two_way_model_refuses_a_writable_original_even_if_its_share_mask_is_three(self):
        command = self.command()
        handle = command._pins[-1].handle
        self.api.modes[handle] = (2, 3)  # Deliberately wrong modeled creator, not a production option.
        with self.assertRaisesRegex(files.FilesystemError, "sharing"):
            self.freeze(command)
        self.assertIn(handle, self.api.handles)

    def test_live_writer_blocks_freeze_without_early_close_or_retry(self):
        command = self.command()
        original = command._pins[-1].handle
        writer = self.api.shared_open(self.node(), 2, 7)
        try:
            with self.assertRaisesRegex(files.FilesystemError, "sharing"):
                self.freeze(command)
            self.assertIn(original, self.api.handles)
        finally:
            self.api.close(writer)
        with self.assertRaises(files.FilesystemError):
            self.freeze(command)  # A failed attempt cannot later manufacture success.

    def test_delete_is_denied_while_original_or_final_reader_is_retained(self):
        command = self.command()
        for phase in ("original", "frozen"):
            with self.subTest(phase=phase), self.assertRaisesRegex(files.FilesystemError, "sharing"):
                self.api.shared_open(self.node(), 4, 7)
            if phase == "original":
                self.freeze(command)
        with self.assertRaisesRegex(files.FilesystemError, "sharing"):
            self.append(b"late")

    def test_one_shot_transfer_and_use_after_close_are_refused(self):
        command = self.command()
        self.freeze(command)
        for method in (command.freeze, command.observe):
            with self.assertRaises(files.FilesystemError):
                method()
        command.close()

    def test_closed_small_byte_limit_and_explicit_original_deadline_are_required(self):
        for value in (-1, 4097, True, 1.0, None):
            with self.subTest(maximum=value), self.assertRaises(files.FilesystemError):
                self.command(maximum=value)
        for end in (None, True, 100, 1001, float("inf"), float("nan")):
            with self.subTest(end=end), self.assertRaises(files.FilesystemError):
                self.command(end=end)
        self.assertNotIn(r"C:\work\private\provider-output.txt", self.api.nodes)
        command = self.command(maximum=0)
        self.assertEqual(self.freeze(command).read(), b"")

    def test_observed_shrink_and_overflow_fail_without_recovery(self):
        command = self.command(maximum=8)
        self.append(b"1234")
        self.assertEqual(command.observe().size, 4)
        self.node().content = b"12"
        with self.assertRaises(files.FilesystemError):
            command.observe()
        self.node().content = b"1234"
        with self.assertRaises(files.FilesystemError):
            command.freeze()

    def test_bound_is_observational_not_a_kernel_write_quota(self):
        command = self.command(maximum=2)
        self.append(b"123")  # Model write is allowed; the next observation must fail.
        with self.assertRaises(files.FilesystemError):
            command.observe()
        self.assertEqual(self.node().content, b"123")

    def test_private_shape_and_original_identity_changes_are_rejected(self):
        command = self.command()
        self.node().identifier += 100
        with self.assertRaisesRegex(files.FilesystemError, "identity"):
            command.observe()

    def test_freeze_rechecks_stream_link_acl_and_path_policy(self):
        for field, value in (("extra_stream", True), ("links", 2), ("reparse", True),
                             ("bad_acl", True), ("owner", files.SYSTEM_SID), ("protected", False),
                             ("path", r"C:\elsewhere")):
            with self.subTest(field=field):
                command = self.command()
                node = self.node()
                old = getattr(node, field)
                setattr(node, field, value)
                with self.assertRaises(files.FilesystemError):
                    command.freeze()
                setattr(node, field, old)
                command.close()
                # New independent model fixture; production never deletes or retries.
                self.tearDown()
                self.setUp()

    def test_creation_rejects_cross_volume_readback_without_adopting_or_deleting(self):
        before = set(self.api.handles)
        inspect = self.api.inspect
        def changed(handle, *args, **kwargs):
            value = inspect(handle, *args, **kwargs)
            return replace(value, identity=(2, value.identity[1])) if not value.is_directory else value
        with patch.object(self.api, "inspect", side_effect=changed):
            with self.assertRaisesRegex(files.FilesystemError, "volume"):
                self.command()
        self.assertEqual(set(self.api.handles), before)
        self.assertEqual(self.node().content, b"")

    def test_actual_inspector_allows_interquery_growth_only_in_live_observation(self):
        queries = base.StreamQueryModel(self.api)
        command = self.command(maximum=8)
        handle = command._pins[-1].handle
        queries.after_standard[handle] = lambda: self.append(b"12345678")
        self.assertEqual(command.observe().size, 8)
        self.assertEqual(self.freeze(command).read(), b"12345678")
        self.assertEqual(queries.observations[-1][1], None)

    def test_actual_inspector_rejects_interquery_overflow_without_changing_pin_kind(self):
        queries = base.StreamQueryModel(self.api)
        command = self.command(maximum=2)
        handle = command._pins[-1].handle
        queries.after_standard[handle] = lambda: self.append(b"123")
        with self.assertRaises(files.FilesystemError):
            command.observe()
        self.assertFalse(command._pins[-1].writable)
        with self.assertRaises(files.FilesystemError):
            command._pins[-1].observe(live_output_max_bytes=2)

    def test_actual_inspector_refuses_malformed_command_streams(self):
        queries = base.StreamQueryModel(self.api)
        command = self.command()
        queries.raw_streams[command._pins[-1].handle] = base.stream_record(":unexpected:$DATA", 0)
        with self.assertRaises(files.FilesystemError):
            command.observe()

    def test_freeze_without_another_live_poll_still_enforces_observed_high_water(self):
        command = self.command()
        self.append(b"1234")
        command.observe()
        self.node().content = b"12"  # Injected model corruption, not a claimed NTFS write.
        with self.assertRaisesRegex(files.FilesystemError, "final"):
            command.freeze()

    def test_strict_reader_rejects_same_size_stamp_mutation_after_transfer(self):
        reader = self.freeze(self.command())
        self.node().version += 1  # Backstop test; bypasses the sharing model deliberately.
        with self.assertRaises(files.FilesystemError):
            reader.verify()
        with self.assertRaises(files.FilesystemError):
            reader.close()

    def test_strict_overlap_compares_full_final_info_not_only_identity_or_size(self):
        command = self.command()
        original = command._pins[-1].handle
        inspect = self.api.inspect
        def changed(handle, *args, **kwargs):
            value = inspect(handle, *args, **kwargs)
            return replace(value, change_100ns=value.change_100ns + 1) if handle == original else value
        with patch.object(self.api, "inspect", side_effect=changed):
            with self.assertRaisesRegex(files.FilesystemError, "final"):
                command.freeze()
        self.assertIn(original, self.api.handles)

    def test_new_owner_constructor_failure_releases_every_partial_acquisition(self):
        before = set(self.api.handles)
        with patch.object(files, "_ProviderCommandFile", side_effect=ValueError("constructor")):
            with self.assertRaisesRegex(ValueError, "constructor"):
                self.command()
        self.assertEqual(set(self.api.handles), before)
        self.assertIn(r"C:\work\private\provider-output.txt", self.api.nodes)

    def test_freeze_constructor_failure_keeps_original_owned_and_releases_new_pin(self):
        command = self.command()
        before = set(self.api.handles)
        with patch.object(files, "NativeFile", side_effect=ValueError("reader constructor")):
            with self.assertRaisesRegex(ValueError, "reader constructor"):
                command.freeze()
        self.assertEqual(set(self.api.handles), before)
        with self.assertRaises(files.FilesystemError):
            command.freeze()

    def test_freeze_ancestor_acquisition_failure_keeps_original_and_rolls_back_new_refs(self):
        command = self.command()
        before = {pin.handle: pin.references for pin in command._pins}
        with patch.object(command._pins[1], "acquire", side_effect=ValueError("ancestor acquisition")):
            with self.assertRaisesRegex(ValueError, "ancestor acquisition"):
                command.freeze()
        self.assertEqual({pin.handle: pin.references for pin in command._pins}, before)
        self.assertEqual(set(self.api.handles), set(before))

    def test_cancellation_and_secondary_close_error_preserve_the_first_failure(self):
        command = self.command()
        before = set(self.api.handles)
        original = KeyboardInterrupt("modeled cancellation")
        inspect = self.api.inspect
        def interrupted(handle, *args, **kwargs):
            if handle not in before:
                self.api.close_failure = handle
                raise original
            return inspect(handle, *args, **kwargs)
        with patch.object(self.api, "inspect", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt) as caught:
                command.freeze()
        self.assertIs(caught.exception, original)
        self.assertIn("retirement UNKNOWN", " ".join(original.__notes__))
        self.assertEqual(set(self.api.handles), before)
        with self.assertRaises(files.FilesystemError):
            command.freeze()

    def test_failed_original_close_never_returns_a_success_reader_or_retries_handle(self):
        command = self.command()
        original = command._pins[-1].handle
        self.api.close_failure = original
        with self.assertRaises(files.FilesystemError) as caught:
            command.freeze()
        self.assertIn("closure", str(caught.exception))
        self.assertTrue(command._failed_pins)
        command.close()
        self.assertEqual(sum(event[:2] == ("close", original) for event in self.api.events), 1)
        self.assertFalse(any(node is self.node() for node, _, _ in self.api.handles.values()))

    def test_expired_freeze_does_not_open_or_renew_any_handle(self):
        command = self.command()
        before = list(self.api.events)
        self.elapsed = 120
        with self.assertRaises(files.FilesystemError):
            command.freeze()
        self.assertEqual(self.api.events, before)
        with self.assertRaises(files.FilesystemError):
            command.close()  # Cleanup still attempts every handle, but is not timely success.

    def test_slow_native_reopen_cannot_return_a_late_success_or_leak_new_handle(self):
        command = self.command()
        before = set(self.api.handles)
        child = self.api.child
        def slow(*args, **kwargs):
            handle = child(*args, **kwargs)
            self.elapsed = 120
            return handle
        with patch.object(self.api, "child", side_effect=slow):
            with self.assertRaises(files.FilesystemError):
                command.freeze()
        self.assertEqual(set(self.api.handles), before)
        with self.assertRaises(files.FilesystemError):
            command.close()

    def test_slow_live_observation_cannot_succeed_after_original_end(self):
        command = self.command()
        inspect = self.api.inspect
        def slow(handle, *args, **kwargs):
            result = inspect(handle, *args, **kwargs)
            if handle == command._pins[-1].handle:
                self.elapsed = 120
            return result
        with patch.object(self.api, "inspect", side_effect=slow):
            with self.assertRaises(files.FilesystemError):
                command.observe()
        with self.assertRaises(files.FilesystemError):
            command.close()

    def test_final_reader_rejects_late_handle_close_without_renewing_or_retrying(self):
        command = self.command()
        reader = self.freeze(command)
        strict = reader.native_handle
        close = self.api.close
        def slow(handle):
            close(handle)
            if handle == strict:
                self.elapsed = 120
        with patch.object(self.api, "close", side_effect=slow):
            with self.assertRaises(files.FilesystemError) as caught:
                reader.close()
        self.assertIn("deadline exceeded", " ".join(caught.exception.__notes__))
        self.assertTrue(reader.closed)
        self.assertEqual(reader._deadline, command._deadline)
        events = list(self.api.events)
        reader.close()  # Once-only retirement cannot retry an uncertain handle.
        self.assertEqual(self.api.events, events)

    def test_final_reader_rejects_late_last_ancestor_close(self):
        command = self.command()
        self.root.close()  # Remaining ancestor references belong to command/reader.
        reader = self.freeze(command)
        last = reader._pins[0].handle
        close = self.api.close
        def slow(handle):
            close(handle)
            if handle == last:
                self.elapsed = 120
        with patch.object(self.api, "close", side_effect=slow):
            with self.assertRaises(files.FilesystemError) as caught:
                reader.close()
        self.assertIn("deadline exceeded", " ".join(caught.exception.__notes__))
        self.assertEqual(self.api.handles, {})
        self.assertEqual(self.api.events[-1], ("close", last, "C:\\"))
        self.assertEqual(reader._deadline, 120.0)

    def test_final_reader_preserves_unknown_close_and_late_postcheck(self):
        command = self.command()
        self.root.close()
        reader = self.freeze(command)
        strict = reader.native_handle
        self.api.close_failure = strict
        close = self.api.close
        def slow_unknown(handle):
            try:
                close(handle)
            finally:
                if handle == strict:
                    self.elapsed = 120
        with patch.object(self.api, "close", side_effect=slow_unknown):
            with self.assertRaises(files.FilesystemError) as caught:
                reader.close()
        self.assertIn("closure failed", str(caught.exception.__cause__))
        notes = " ".join(caught.exception.__notes__)
        self.assertIn("retirement UNKNOWN", notes)
        self.assertIn("deadline exceeded", notes)
        self.assertEqual(self.api.handles, {})  # Model closes then reports UNKNOWN.
        events = list(self.api.events)
        reader.close()
        self.assertEqual(self.api.events, events)

    def test_other_original_directory_owner_still_requires_final_caller_postcheck(self):
        command = self.command()
        reader = self.freeze(command)
        reader.close()
        # NativeFile can only postcheck release of its own references. A
        # separate original directory may own the last ancestor references.
        last = self.root._pins[0].handle
        close = self.api.close
        def slow(handle):
            close(handle)
            if handle == last:
                self.elapsed = 120
        with patch.object(self.api, "close", side_effect=slow):
            self.root.close()
        self.assertEqual(self.api.handles, {})
        with self.assertRaises(files.FilesystemError):
            files._check_time(command._deadline)

    def test_close_waits_for_the_active_observation_instead_of_releasing_its_pin(self):
        command = self.command()
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        original, errors = self.api.inspect, []
        def inspect(handle, *args, **kwargs):
            if handle == command._pins[-1].handle:
                entered.set()
                if not release.wait(2):
                    raise AssertionError("test release missing")
            return original(handle, *args, **kwargs)
        def observe():
            try:
                command.observe()
            except BaseException as error:
                errors.append(error)
        def close():
            try:
                command.close()
                closed.set()
            except BaseException as error:
                errors.append(error)
        threads = [threading.Thread(target=observe), threading.Thread(target=close)]
        with patch.object(self.api, "inspect", side_effect=inspect):
            try:
                threads[0].start()
                self.assertTrue(entered.wait(2))
                threads[1].start()
                self.assertFalse(closed.is_set())
            finally:
                release.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(2)
        self.assertEqual(errors, [])
        self.assertTrue(closed.is_set())
        self.assertFalse(any(thread.is_alive() for thread in threads))


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    print("NATIVE_WINDOWS_PROVIDER_COMMAND=NOT_RUN (call/sharing models only)")
    raise SystemExit(0 if result.wasSuccessful() else 1)
