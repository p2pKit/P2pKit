#!/usr/bin/env python3
"""Pure/model controls by default; --native additionally requires real Windows.

The default result explicitly records NATIVE_WINDOWS_FILES=NOT_RUN. Model passes
are never Windows ACL/NTFS qualification. Native controls touch only their new
invocation-owned temporary fixture, with no Gradle/GPG/downloads or private keys.
"""
from __future__ import annotations

import argparse
import ctypes
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import wraps
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hosted_windows_files", ROOT / "scripts/hosted_windows_files.py")
files = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = files
SPEC.loader.exec_module(files)
USER = "S-1-5-21-1-2-3-1001"
POLICY = files.AccessPolicy(USER, USER)


def stream_record(name="::$DATA", size=0, following=0):
    raw = name.encode("utf-16-le")
    return struct.pack("<IIqq", following, len(raw), size, size) + raw


def directory_record(name="report.xml", following=0):
    raw = name.encode("utf-16-le")
    header = bytearray(104)
    struct.pack_into("<I", header, 0, following)
    struct.pack_into("<I", header, 60, len(raw))
    return bytes(header) + raw


def acl(directory=True, protected=True, user=USER):
    flags = (3 if directory else 0) | (0 if protected else files.INHERITED_ACE)
    return [(0, flags, files.FILE_ALL_ACCESS, user), (0, flags, files.FILE_ALL_ACCESS, files.SYSTEM_SID)]


class PurePolicyTests(unittest.TestCase):
    def test_normalized_absolute_and_relative_paths(self):
        self.assertEqual(files.absolute_parts(r"c:\work\state"), ("C:\\", ("work", "state")))
        self.assertEqual(files.relative_parts("evidence/cli.xml"), ("evidence", "cli.xml"))
        self.assertEqual(files.final_path_matches(r"\\?\C:\work\State", r"c:\work\state"), r"C:\work\State")

    def test_path_authority_escapes_fail_closed(self):
        for value in (r"\\server\share\data", r"\\?\C:\data", r"\\.\PhysicalDrive0", "C:data", "C:/data",
                      "C:\\", "C:\\x\\", "C:\\x\\..\\y", "C:\\x\\.\\y", "C:\\x\\\\y", "C:\\x:secret"):
            with self.subTest(path=value), self.assertRaises(files.FilesystemError):
                files.absolute_parts(value)

    def test_component_devices_aliases_and_invalid_encoding_rejected(self):
        for value in ("NUL", "con.txt", "COM1.log", "LPT²", "CONIN$", "CONOUT$", "CLOCK$", "a ", "a.",
                      "a:b", "a\x00b", "a\n", "a\x7f", "a*b", "a?b", "a|b", "a<b", "a\"b", "a/b", "a\\b",
                      "\ud800", "x" * 256):
            with self.subTest(component=repr(value)), self.assertRaises(files.FilesystemError):
                files.component(value)
        self.assertEqual(files.component("COM10.log"), "COM10.log")
        self.assertEqual(files.component("a" * 255), "a" * 255)

    def test_relative_paths_cannot_choose_a_second_root_or_alias(self):
        for value in ("/root", "C:/root", "x\\y", "../root", "x/", "x//y", "x/./y", ":stream", ""):
            with self.subTest(path=value), self.assertRaises(files.FilesystemError):
                files.relative_parts(value)

    def test_final_path_rejects_short_names_subst_unc_and_unicode_folding_aliases(self):
        pairs = [(r"\\?\C:\Program Files\x", r"C:\PROGRA~1\x"), (r"\\?\C:\work", r"X:\work"),
                 (r"\\?\UNC\server\share\x", r"C:\x"), (r"C:\x", r"C:\x"),
                 ("\\\\?\\C:\\straße", "C:\\strasse")]
        for actual, requested in pairs:
            with self.subTest(actual=actual), self.assertRaises(files.FilesystemError):
                files.final_path_matches(actual, requested)

    def test_acl_at_creation_is_protected_and_only_user_system(self):
        self.assertEqual(POLICY.sddl(True), f"O:{USER}D:P(A;OICI;FA;;;{USER})(A;OICI;FA;;;S-1-5-18)")
        self.assertEqual(POLICY.sddl(False), f"O:{USER}D:P(A;;FA;;;{USER})(A;;FA;;;S-1-5-18)")
        self.assertTrue(files.validate_acl(POLICY, USER, 0x1004, 1, acl(), directory=True))
        self.assertTrue(files.validate_acl(POLICY, USER, 0x1004, 1, acl(False), directory=False))

    def test_supported_admin_default_owner_is_explicit_not_an_admin_access_ace(self):
        policy = files.AccessPolicy(USER, files.ADMINISTRATORS_SID)
        self.assertTrue(policy.sddl(True).startswith("O:S-1-5-32-544D:P"))
        self.assertNotIn(";;;S-1-5-32-544)", policy.sddl(True))
        files.validate_acl(policy, files.ADMINISTRATORS_SID, 0x1004, 1, acl(), directory=True)
        for user, owner in ((files.SYSTEM_SID, files.SYSTEM_SID), (USER, files.SYSTEM_SID),
                            (files.ADMINISTRATORS_SID, files.ADMINISTRATORS_SID), ("garbage", USER)):
            with self.subTest(user=user, owner=owner), self.assertRaises(files.FilesystemError):
                files.AccessPolicy(user, owner)

    def test_inherited_acl_only_below_an_admitted_root(self):
        with self.assertRaises(files.FilesystemError):
            files.validate_acl(POLICY, USER, 0x404, 1, acl(protected=False), directory=True)
        self.assertFalse(files.validate_acl(POLICY, USER, 0x404, 1, acl(protected=False),
                                            directory=True, inherited_allowed=True))
        self.assertFalse(files.validate_acl(POLICY, USER, 0x404, 1, acl(False, False),
                                            directory=False, inherited_allowed=True))

    def test_null_broad_unknown_inherited_and_mixed_aces_rejected(self):
        bad = [None, [], acl() + [(0, 3, files.FILE_ALL_ACCESS, "S-1-1-0")],
               [(0, 3, files.FILE_ALL_ACCESS, "S-1-1-0"), acl()[1]], [acl()[0], acl()[0]],
               [(1, 3, files.FILE_ALL_ACCESS, USER), acl()[1]],
               [(0, 3, 0x10000000, USER), acl()[1]],
               [(0, 7, files.FILE_ALL_ACCESS, USER), acl()[1]],
               [(0, 0x13, files.FILE_ALL_ACCESS, USER), acl()[1]]]
        for records in bad:
            with self.subTest(aces=records), self.assertRaises(files.FilesystemError):
                files.validate_acl(POLICY, USER, 0x1004, 1, records, directory=True, inherited_allowed=True)
        for owner, control, revision in ((files.SYSTEM_SID, 0x1004, 1), (USER, 0x1000, 1), (USER, 0x1004, 2)):
            with self.subTest(owner=owner, control=control, revision=revision), self.assertRaises(files.FilesystemError):
                files.validate_acl(POLICY, owner, control, revision, acl(), directory=True)

    def test_stream_default_and_empty_directory(self):
        self.assertEqual(files.decode_streams(stream_record(size=7), directory=False, size=7), (("::$DATA", 7),))
        self.assertEqual(files.decode_streams(None, directory=True, size=0), ())
        self.assertEqual(files.decode_streams(stream_record(), directory=True, size=0), (("::$DATA", 0),))

    def test_ads_wrong_size_absent_and_duplicate_default_stream_rejected(self):
        first = stream_record(size=3, following=40)
        duplicate = first + b"\0" * (40 - len(first)) + stream_record(size=3)
        for raw, directory, size in ((None, False, 0), (stream_record(":secret:$DATA", 3), False, 3),
                                     (stream_record(size=2), False, 3), (duplicate, False, 3),
                                     (stream_record(size=1), True, 1)):
            with self.subTest(raw=raw), self.assertRaises(files.FilesystemError):
                files.decode_streams(raw, directory=directory, size=size)

    def test_malformed_native_stream_and_directory_records_rejected(self):
        for raw in (b"", stream_record()[:-1], struct.pack("<IIqq", 0, 1, 0, 0) + b"x",
                    stream_record(following=1), stream_record(size=-1), stream_record(following=10000)):
            with self.subTest(raw=raw), self.assertRaises(files.FilesystemError):
                files.decode_streams(raw, directory=False, size=0)
        for raw in (b"", directory_record()[:-1], directory_record("x", 1), directory_record("x", 10000),
                    directory_record("NUL"), directory_record("child:stream")):
            with self.subTest(raw=raw), self.assertRaises(files.FilesystemError):
                files.decode_directory(raw)

    def test_native_directory_records_skip_dot_and_preserve_full_name(self):
        first = directory_record(".", following=112)
        raw = first + b"\0" * (112 - len(first)) + directory_record("full long name.xml")
        self.assertEqual(files.decode_directory(raw), ["full long name.xml"])

    def test_explicit_bounds_and_deadline_not_relaxed(self):
        for value in (True, -1, 0, 11, 1.0):
            with self.subTest(bound=value), self.assertRaises(files.FilesystemError):
                files._bound(value, 10, "test")
        self.assertEqual(files._bound(0, 10, "test", zero=True), 0)
        for value in (time.monotonic() - 1, time.monotonic() + 901, float("nan"), float("inf"), True):
            with self.subTest(deadline=value), self.assertRaises(files.FilesystemError):
                files._end(value)


class NativeCallShapeTests(unittest.TestCase):
    """Mocked ctypes call arguments/error paths, NOT a Windows ABI/runtime test."""
    def setUp(self):
        self.api = object.__new__(files._WinApi)  # Never load a Windows library on the offline host.
        self.api.policy = POLICY
        self.events, self.calls = [], []
        self.native_result, self.native_information = 0, None
        self.convert_ok, self.fail_free, self.fail_close = True, False, False
        self.api.checked = lambda result, operation: files.require(result, "Modeled " + operation + " failed")
        self.api.ConvertStringSecurityDescriptorToSecurityDescriptorW = self.convert
        self.api.NtCreateFile = self.create
        self.api.RtlNtStatusToDosError = lambda status: 5
        self.api._free, self.api.close = self.free, self.close

    def convert(self, text, revision, output, size):
        self.events.append(("descriptor", text, revision))
        ctypes.cast(output, ctypes.POINTER(files.PTR)).contents.value = 101
        return self.convert_ok

    def create(self, output, access, attributes, status, allocation, flags, sharing, disposition, options, ea, ea_size):
        self.events.append(("create",))
        attrs = ctypes.cast(attributes, ctypes.POINTER(files._ObjectAttributes)).contents
        name = attrs.name.contents
        self.calls.append({"parent": attrs.root, "attributes": attrs.attributes, "security": attrs.security,
                           "name": ctypes.wstring_at(name.buffer), "length": name.length, "maximum": name.maximum,
                           "access": access, "flags": flags, "sharing": sharing, "disposition": disposition,
                           "options": options, "allocation": allocation, "ea": ea, "ea_size": ea_size})
        ctypes.cast(output, ctypes.POINTER(files.PTR)).contents.value = 202
        ctypes.cast(status, ctypes.POINTER(files._IoStatus)).contents.information = (
            self.native_information if self.native_information is not None else disposition)
        return self.native_result

    def free(self, pointer):
        if pointer.value is not None:
            self.events.append(("free", pointer.value))
            if self.fail_free:
                raise files.FilesystemError("Modeled LocalFree failure")

    def close(self, handle):
        self.events.append(("close", handle.value if isinstance(handle, files.PTR) else handle))
        if self.fail_close:
            raise files.FilesystemError("Modeled CloseHandle failure")

    def test_exclusive_native_relative_create_has_atomic_acl_and_noninheritable_readonly_sharing(self):
        handle = self.api.child(17, "private.log", directory=False, create=True, writable=True)
        self.assertEqual(handle, 202)
        self.assertEqual(self.calls, [{"parent": 17, "attributes": 0x40, "security": 101, "name": "private.log",
                                      "length": 22, "maximum": 24, "access": 0x00120082, "flags": 0x80,
                                      "sharing": 1, "disposition": 2, "options": 0x00200060,
                                      "allocation": None, "ea": None, "ea_size": 0}])
        self.assertEqual(self.events, [("descriptor", POLICY.sddl(False), 1), ("create",), ("free", 101)])

    def test_directory_open_is_relative_readonly_nonreparse_and_cannot_replace(self):
        self.assertEqual(self.api.child(17, "nested", directory=True), 202)
        self.assertEqual(self.calls[0]["access"], 0x001200A1)
        self.assertEqual(self.calls[0]["options"], 0x00200021)
        self.assertEqual(self.calls[0]["disposition"], 1)
        self.assertIsNone(self.calls[0]["security"])
        self.assertEqual(self.events, [("create",)])

    def test_kind_probe_uses_attribute_only_nonreparse_open(self):
        self.api.child(17, "unknown", directory=None)
        self.assertEqual(self.calls[0]["access"], 0x00120080)
        self.assertEqual(self.calls[0]["options"], 0x00200020)

    def test_wrong_open_disposition_readback_does_not_transfer_handle(self):
        self.native_information = 3
        with self.assertRaisesRegex(files.FilesystemError, "creation/open result differs"):
            self.api.child(17, "private", directory=True, create=True)
        self.assertEqual(self.events[-2:], [("free", 101), ("close", 202)])

    def test_descriptor_retirement_failure_closes_a_successfully_created_handle(self):
        self.fail_free = True
        with self.assertRaises(files.FilesystemError) as caught:
            self.api.child(17, "private", directory=True, create=True)
        self.assertIn("LocalFree", " ".join(caught.exception.__notes__))
        self.assertEqual(self.events[-2:], [("free", 101), ("close", 202)])

    def test_native_failure_keeps_original_and_attempts_free_and_close_even_if_both_fail(self):
        self.native_result, self.fail_close, self.fail_free = -1, True, True
        with self.assertRaisesRegex(files.FilesystemError, "NtCreateFile failed") as caught:
            self.api.child(17, "private", directory=True, create=True)
        notes = " ".join(caught.exception.__notes__)
        self.assertIn("LocalFree", notes)
        self.assertIn("CloseHandle", notes)
        self.assertIn("retirement UNKNOWN", notes)
        self.assertEqual(self.events[-2:], [("free", 101), ("close", 202)])

    def test_failed_descriptor_conversion_also_retires_its_partial_allocation(self):
        self.convert_ok = False
        with self.assertRaisesRegex(files.FilesystemError, "Create protected security descriptor failed"):
            self.api.child(17, "private", directory=True, create=True)
        self.assertEqual(self.events[-1], ("free", 101))
        self.assertEqual(self.calls, [])

    def test_wow64_and_translated_native_architectures_are_not_admitted(self):
        self.api.GetCurrentProcess = lambda: -1
        for process, native, accepted in ((0, 0x8664, True), (0, 0xAA64, True), (0x8664, 0xAA64, False),
                                          (0x014C, 0x8664, False), (0, 0x014C, False), (0, 0, False)):
            def query(handle, process_output, native_output):
                ctypes.cast(process_output, ctypes.POINTER(files.U16)).contents.value = process
                ctypes.cast(native_output, ctypes.POINTER(files.U16)).contents.value = native
                return True
            self.api.IsWow64Process2 = query
            with self.subTest(process=process, native=native):
                if accepted:
                    self.api._native_architecture()
                else:
                    with self.assertRaises(files.FilesystemError):
                        self.api._native_architecture()


@dataclass
class Node:
    path: str
    directory: bool
    identifier: int
    private: bool = False
    protected: bool = True
    owner: str = USER
    links: int = 1
    reparse: bool = False
    version: int = 1
    content: bytes = b""
    extra_stream: bool = False
    bad_acl: bool = False


class ModelApi:
    """Handle/refcount/control-flow model ONLY, never Windows execution evidence."""
    def __init__(self):
        self.policy = POLICY
        self.nodes = {"C:\\": Node("C:\\", True, 1), r"C:\work": Node(r"C:\work", True, 2)}
        self.handles, self.events = {}, []
        self.next_handle, self.next_id = 1, 3
        self.close_failure = None
        self.flush_failure = False
        self.inspect_failure = None
        self.names_hook = None
        self.read_sizes, self.write_sizes = [], []

    def _open(self, node, writable=False):
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = [node, 0, writable]
        self.events.append(("open", handle, node.path))
        return handle

    def drive(self, drive):
        return self._open(self.nodes[drive])

    def child(self, parent, name, *, directory, create=False, writable=False):
        base = self.handles[parent][0]
        path = base.path + ("" if base.path.endswith("\\") else "\\") + name
        if create:
            files.require(path not in self.nodes, "Modeled FILE_CREATE collision")
            self.nodes[path] = Node(path, directory, self.next_id, private=True)
            self.next_id += 1
            base.version += 1
            self.events.append(("create-with-protected-acl", path, self.policy.sddl(directory)))
        files.require(path in self.nodes, "Modeled missing child")
        node = self.nodes[path]
        files.require(directory is None or node.directory == directory, "Modeled wrong kind")
        return self._open(node, writable)

    def inspect(self, handle, path, *, directory, private=False, inherited_allowed=False):
        node = self.handles[handle][0]
        if self.inspect_failure == node.path:
            raise files.FilesystemError("Modeled readback failure")
        files.require(node.path == path and node.directory == directory and not node.reparse and
                      (directory or node.links == 1), "Modeled identity/kind/link rejection")
        if private:
            files.require(node.private and not node.extra_stream, "Modeled privacy/ADS rejection")
            records = acl(directory, node.protected)
            if node.bad_acl:
                records.append((0, 3, files.FILE_ALL_ACCESS, "S-1-1-0"))
            files.validate_acl(self.policy, node.owner, 0x4 | (0x1000 if node.protected else 0), 1, records,
                               directory=directory, inherited_allowed=inherited_allowed)
        return files.FileInfo((1, f"{node.identifier:032x}"), directory, len(node.content), node.links,
                              files.DIRECTORY if directory else 0x20, 100, node.version, node.version,
                              node.owner if private else None, node.protected if private else None)

    def names(self, handle, maximum, deadline):
        files._check_time(deadline)
        path = self.handles[handle][0].path
        if self.names_hook:
            self.names_hook(path)
        prefix = path + "\\"
        names = [name[len(prefix):] for name in self.nodes if name.startswith(prefix) and "\\" not in name[len(prefix):]]
        files.require(len(names) <= maximum and len({n.casefold() for n in names}) == len(names), "Modeled inventory bound/alias")
        return names

    def kind(self, parent, name):
        path = self.handles[parent][0].path + "\\" + name
        files.require(not self.nodes[path].reparse, "Modeled reparse kind")
        return self.nodes[path].directory

    def read(self, handle, count):
        node, position, _ = self.handles[handle]
        self.read_sizes.append(count)
        value = node.content[position:position + count]
        self.handles[handle][1] += len(value)
        return value

    def write(self, handle, data):
        node, position, writable = self.handles[handle]
        files.require(writable, "Modeled read-only write")
        self.write_sizes.append(len(data))
        content = node.content.ljust(position, b"\0")
        node.content = content[:position] + data + content[position + len(data):]
        node.version += 1
        self.handles[handle][1] += len(data)
        return len(data)

    def seek(self, handle, position, whence):
        node, current, _ = self.handles[handle]
        absolute = position + (0 if whence == 0 else current if whence == 1 else len(node.content))
        self.handles[handle][1] = absolute
        return absolute

    def flush(self, handle):
        if self.flush_failure:
            raise files.FilesystemError("Modeled FlushFileBuffers failure")
        self.events.append(("flush", handle))

    def close(self, handle):
        files.require(handle in self.handles, "Modeled duplicate/unknown handle close")
        self.events.append(("close", handle, self.handles[handle][0].path))
        del self.handles[handle]
        if self.close_failure == handle:
            raise files.FilesystemError("Modeled uncertain CloseHandle result")


class ModelCustodyTests(unittest.TestCase):
    def setUp(self):
        self.api = ModelApi()
        self.root = files._root(r"C:\work\state", self.api, create=True)
        self.owners = []

    def tearDown(self):
        for owner in reversed(self.owners):
            owner.close()
        self.root.close()
        self.assertEqual(self.api.handles, {}, "Modeled handles leaked")

    def keep(self, owner):
        self.owners.append(owner)
        return owner

    def put(self, name, data=b"original"):
        with self.root.create_file(name, max_bytes=len(data)) as stream:
            self.assertFalse(stream.readable())
            self.assertTrue(stream.writable())
            self.assertEqual(stream.write(data), len(data))
        return str(self.root.path) + "\\" + name.replace("/", "\\")

    def test_root_exclusive_creation_retains_existing_on_collision(self):
        with self.assertRaises(files.FilesystemError):
            files._root(r"C:\work\state", self.api, create=True)
        self.root.verify()
        self.assertEqual(len(self.api.handles), 3)
        self.assertTrue(any(row[0] == "create-with-protected-acl" for row in self.api.events))

    def test_created_file_reopened_bounded_and_no_overwrite(self):
        self.put("original.log", b"abc")
        self.assertEqual(self.root.read_bytes("original.log", max_bytes=3), b"abc")
        with self.assertRaises(files.FilesystemError):
            self.root.create_file("original.log", max_bytes=3)
        with self.assertRaises(files.FilesystemError):
            self.root.open_file("original.log", max_bytes=2)
        self.assertEqual(self.root.read_bytes("original.log", max_bytes=3), b"abc")

    def test_child_retains_all_ancestors_after_root_closes(self):
        child = self.keep(self.root.create_directory("evidence"))
        stream = self.keep(child.create_file("raw.log", max_bytes=3))
        pins = set(self.api.handles)
        self.root.close()
        child.close()
        self.assertTrue(pins <= set(self.api.handles))
        stream.write(b"abc")
        stream.close()
        self.assertEqual(self.api.handles, {})

    def test_handle_borrow_is_not_a_crt_descriptor_or_ownership_transfer(self):
        with self.root.create_file("stream", max_bytes=1) as stream:
            handle = stream.native_handle
            self.assertIn(handle, self.api.handles)
            with self.assertRaises(io.UnsupportedOperation):
                stream.fileno()
            stream.write(b"x")
            stream.verify()
        with self.assertRaises(files.FilesystemError):
            _ = stream.native_handle
        stream.close()
        self.assertEqual(sum(row[:2] == ("close", handle) for row in self.api.events), 1)

    def test_private_inherited_subtree_accepted_not_standalone_inherited_root(self):
        child = self.keep(self.root.create_directory("nested"))
        self.api.nodes[str(child.path)].protected = False
        child.close()
        with self.root.open_directory("nested") as reopened:
            self.assertFalse(reopened.verify().protected_dacl)
        with self.assertRaises(files.FilesystemError):
            files._root(r"C:\work\state\nested", self.api, create=False)

    def test_owner_acl_reparse_hardlink_and_ads_changes_rejected(self):
        path = self.put("raw")
        original = self.api.nodes[path]
        for change in ({"owner": files.SYSTEM_SID}, {"bad_acl": True}, {"reparse": True}, {"links": 2},
                       {"extra_stream": True}, {"directory": True}):
            with self.subTest(change=change):
                self.api.nodes[path] = replace(original, **change)
                with self.assertRaises(files.FilesystemError):
                    self.root.open_file("raw", max_bytes=8)
        self.api.nodes[path] = original

    def test_failed_creation_readback_preserves_new_file_and_closes_handles(self):
        self.api.inspect_failure = r"C:\work\state\bad"
        before = set(self.api.handles)
        with self.assertRaises(files.FilesystemError):
            self.root.create_file("bad", max_bytes=8)
        self.assertEqual(set(self.api.handles), before)
        self.assertIn(r"C:\work\state\bad", self.api.nodes)
        self.api.inspect_failure = None

    def test_root_failed_readback_closes_every_acquired_parent(self):
        api = ModelApi()
        api.inspect_failure = r"C:\work\new"
        with self.assertRaises(files.FilesystemError):
            files._root(r"C:\work\new", api, create=True)
        self.assertEqual(api.handles, {})
        self.assertIn(r"C:\work\new", api.nodes)

    def test_root_readback_failure_keeps_original_when_raw_handle_retirement_also_fails(self):
        api = ModelApi()
        api.inspect_failure = r"C:\work\new"
        api.close_failure = 3
        with self.assertRaisesRegex(files.FilesystemError, "Modeled readback failure") as caught:
            files._root(r"C:\work\new", api, create=True)
        self.assertEqual(api.handles, {})
        self.assertTrue(any("retirement UNKNOWN" in note for note in caught.exception.__notes__))

    def test_stream_exact_bound_partial_reads_seek_and_chunking(self):
        value = b"a" * (files.CHUNK + 13)
        self.put("raw", value)
        with self.root.open_file("raw", max_bytes=len(value)) as stream:
            self.assertEqual(stream.read(5), b"a" * 5)
            self.assertEqual(stream.seek(-3, 1), 2)
            self.assertEqual(len(stream.read()), len(value) - 2)
            self.assertEqual(stream.read(1), b"")
            with self.assertRaises(files.FilesystemError):
                stream.seek(1, 2)
        self.assertLessEqual(max(self.api.read_sizes), files.CHUNK)
        self.assertLessEqual(max(self.api.write_sizes), files.CHUNK)

    def test_one_byte_over_write_bound_is_rejected_before_write(self):
        with self.root.create_file("raw", max_bytes=3) as stream:
            stream.write(b"abc")
            before = list(self.api.write_sizes)
            with self.assertRaises(files.FilesystemError):
                stream.write(b"d")
            self.assertEqual(self.api.write_sizes, before)
        self.assertEqual(self.root.read_bytes("raw", max_bytes=3), b"abc")

    def test_readall_preserves_aggregate_cap_not_just_each_chunk_limit(self):
        self.put("raw", b"x" * 20_000)
        with patch.object(files, "MAX_READ_BYTES", 10_000):
            with self.root.open_file("raw", max_bytes=20_000) as stream:
                for materialize in (stream.read, stream.readall):
                    with self.subTest(method=materialize.__name__), self.assertRaises(files.FilesystemError):
                        materialize()
                    self.assertEqual(stream.tell(), 0, "Oversized reads must be rejected before consuming input")
                stream.seek(10_000)
                self.assertEqual(stream.readall(), b"x" * 10_000)
                self.assertEqual(stream.readall(), b"")

    def test_inherited_line_materializers_and_iteration_cannot_escape_binary_read_bound(self):
        self.put("raw", b"x" * 20_000 + b"\n")
        with patch.object(files, "MAX_READ_BYTES", 10_000):
            with self.root.open_file("raw", max_bytes=20_001) as stream:
                for name, materialize in (("readline", stream.readline), ("readlines", stream.readlines),
                                           ("list", lambda: list(stream)), ("next", lambda: next(stream))):
                    with self.subTest(method=name), self.assertRaises(io.UnsupportedOperation):
                        materialize()
                    self.assertEqual(stream.tell(), 0)
                with self.assertRaises(io.UnsupportedOperation):
                    stream.readline(1)
                with self.assertRaises(io.UnsupportedOperation):
                    stream.readlines(1)
                self.assertEqual(stream.read(1), b"x")

    def test_reader_mutation_and_truncation_remain_failures(self):
        path = self.put("raw", b"abc")
        stream = self.keep(self.root.open_file("raw", max_bytes=3))
        self.api.nodes[path].content = b"a"
        self.api.nodes[path].version += 1
        with self.assertRaises(files.FilesystemError):
            stream.read(3)
        with self.assertRaises(files.FilesystemError):
            stream.close()
        stream.close()

    def test_snapshot_pins_nested_files_can_stream_tar_with_identity_checked_relative_reopens(self):
        self.keep(self.root.create_directory("nested")).close()
        self.put("nested/raw.log", b"private-original")
        self.put("empty", b"")
        snapshot = self.keep(self.root.snapshot(max_bytes=16, max_members=4))
        self.root.close()
        self.assertEqual(set(snapshot.entries), {"", "nested", "nested/raw.log", "empty"})
        self.assertEqual(snapshot.total_bytes, 16)
        sink = io.BytesIO()
        with tarfile.open(fileobj=sink, mode="w|") as archive:
            for name, info in snapshot.entries.items():
                if name and not info.is_directory:
                    entry = tarfile.TarInfo(name)
                    entry.size = info.size
                    with snapshot.open_file(name) as stream:
                        archive.addfile(entry, stream)
        snapshot.verify()
        with tarfile.open(fileobj=io.BytesIO(sink.getvalue()), mode="r:") as archive:
            self.assertEqual(archive.extractfile("nested/raw.log").read(), b"private-original")

    def test_snapshot_byte_and_member_limits_fail_without_leaking_handles(self):
        self.put("raw", b"abc")
        for size, members in ((2, 2), (3, 1)):
            with self.subTest(size=size, members=members):
                before = set(self.api.handles)
                with self.assertRaises(files.FilesystemError):
                    self.root.snapshot(max_bytes=size, max_members=members)
                self.assertEqual(set(self.api.handles), before)

    def test_snapshot_membership_mutation_rejected_without_deleting_originals(self):
        path = self.put("raw", b"abc")
        snapshot = self.keep(self.root.snapshot(max_bytes=3, max_members=3))
        self.api.nodes[r"C:\work\state\new"] = Node(r"C:\work\state\new", False, 99, private=True)
        with self.assertRaises(files.FilesystemError):
            snapshot.verify()
        self.assertEqual(self.api.nodes[path].content, b"abc")

    def test_snapshot_aliases_and_unclassified_reparse_are_not_ignored(self):
        path = self.put("raw")
        self.api.nodes[r"C:\work\state\RAW"] = replace(self.api.nodes[path], path=r"C:\work\state\RAW", identifier=99)
        with self.assertRaises(files.FilesystemError):
            self.root.snapshot(max_bytes=16, max_members=3)
        del self.api.nodes[r"C:\work\state\RAW"]
        self.api.nodes[path].reparse = True
        with self.assertRaises(files.FilesystemError):
            self.root.snapshot(max_bytes=16, max_members=3)

    def test_original_exception_not_replaced_by_flush_failure_and_all_handles_close(self):
        stream = self.root.create_file("raw", max_bytes=1)
        self.api.flush_failure = True
        with self.assertRaisesRegex(RuntimeError, "original product error") as caught:
            with stream:
                raise RuntimeError("original product error")
        self.api.flush_failure = False
        self.assertTrue(any("finalization" in note for note in caught.exception.__notes__))
        self.assertTrue(stream.closed)
        self.assertEqual(len(self.api.handles), 3)

    def test_expired_read_and_finalization_fail_but_retire_handles(self):
        self.put("raw", b"abc")
        stream = self.root.open_file("raw", max_bytes=3)
        stream._deadline = time.monotonic() - 1
        with self.assertRaises(files.FilesystemError):
            stream.read()
        with self.assertRaises(files.FilesystemError):
            stream.close()
        self.assertEqual(len(self.api.handles), 3)

    def test_close_failure_does_not_prevent_other_handles_closing(self):
        self.api.close_failure = self.root._pins[-1].handle
        with self.assertRaises(files.FilesystemError) as caught:
            self.root.close()
        self.assertEqual(self.api.handles, {})
        self.assertTrue(any("retirement UNKNOWN" in note for note in caught.exception.__notes__))
        self.root.close()

    def test_reference_acquisition_failure_rolls_back_prior_refs(self):
        first = self.root._pins[0]
        dead = files._Pin(self.api, 999, "dead", first.info, private=False)
        dead.references = 0
        before = first.references
        with self.assertRaises(files.FilesystemError):
            files._acquire([first, dead])
        self.assertEqual(first.references, before)

    def test_close_cannot_free_a_handle_during_an_active_stream_read(self):
        self.put("raw", b"abc")
        stream = self.root.open_file("raw", max_bytes=3)
        entered, release, close_started, closed = (threading.Event() for _ in range(4))
        original_read = self.api.read
        results, errors = [], []

        def held_read(handle, count):
            entered.set()
            if not release.wait(2):
                raise AssertionError("Modeled read release was not delivered")
            self.assertIn(handle, self.api.handles)
            return original_read(handle, count)

        def reader():
            try:
                results.append(stream.read(1))
            except BaseException as error:
                errors.append(error)

        def closer():
            close_started.set()
            try:
                stream.close()
                closed.set()
            except BaseException as error:
                errors.append(error)

        self.api.read = held_read
        threads = [threading.Thread(target=reader), threading.Thread(target=closer)]
        try:
            threads[0].start()
            self.assertTrue(entered.wait(2))
            threads[1].start()
            self.assertTrue(close_started.wait(2))
            acquired = stream._operation_lock.acquire(blocking=False)
            if acquired:
                stream._operation_lock.release()
            self.assertFalse(acquired, "The active read must retain its handle lifetime fence")
            self.assertFalse(closed.is_set())
        finally:
            release.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(2)
            self.api.read = original_read
            stream.close()
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(results, [b"a"])
        self.assertTrue(closed.is_set())


def unknown_retirement(error):
    """Unittest must never consume uncertain native cleanup as a negative pass."""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if len(seen) > 64:
            return True  # An uninspectable exception graph is not disposal authority.
        if any(isinstance(text, str) and "Native handle retirement UNKNOWN" in text
               for text in (str(current), *getattr(current, "__notes__", ()))):
            return True
        pending.extend((getattr(current, "__cause__", None), getattr(current, "__context__", None)))
        pending.extend(getattr(current, "exceptions", ()))
    return False


def native_control(method):
    @wraps(method)
    def guarded(self):
        try:
            return method(self)
        except BaseException as error:
            self.retirement_unknown |= unknown_retirement(error)
            raise
    return guarded


class NativeWindowsTests(unittest.TestCase):
    """Selected only by --native; any missing native prerequisite is FAILURE."""
    def setUp(self):
        self.parent = Path(tempfile.mkdtemp(prefix="p2pkit-windows-files-control-"))
        self.root_path = self.parent / "private"
        self.root = None
        self.retirement_unknown = False
        self.addCleanup(self.cleanup_fixture)
        try:
            self.root = files.create_private_directory(self.root_path)
        except BaseException as error:
            self.retirement_unknown = unknown_retirement(error)
            raise

    def cleanup_fixture(self):
        # Attempt every still-owned known root closure even when an earlier
        # child retirement was uncertain. Never delete that retained fixture.
        if self.root is not None:
            try:
                self.root.close()
            except BaseException as error:
                self.retirement_unknown |= unknown_retirement(error)
                raise
        if self.retirement_unknown:
            return
        # Exact per-test fixture only, after every owned native handle is closed.
        shutil.rmtree(self.parent)

    @contextmanager
    def expected_rejection(self, kind):
        # Ordinary assertRaises would swallow an expected filesystem rejection
        # even if its cleanup simultaneously reported UNKNOWN handle retirement.
        try:
            yield
        except BaseException as error:
            if unknown_retirement(error):
                self.retirement_unknown = True
                raise
            if not isinstance(error, kind):
                raise
            return
        self.fail("Native negative control did not reject its invalid operation")

    def put(self, name, data=b"native-original"):
        with self.root.create_file(name, max_bytes=len(data)) as stream:
            stream.write(data)
            stream.sync()
            self.assertEqual(stream.verify().size, len(data))

    def set_fixture_dacl(self, sddl):
        """Native negative control on this test's new empty directory only."""
        api = self.root._api
        self.assertEqual(self.root_path.parent, self.parent)
        descriptor, dacl = files.PTR(), files.PTR()
        present, defaulted = ctypes.c_int32(), ctypes.c_int32()
        get_dacl = api.advapi.GetSecurityDescriptorDacl
        get_dacl.argtypes = [files.PTR, ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(files.PTR),
                             ctypes.POINTER(ctypes.c_int32)]
        get_dacl.restype = ctypes.c_int32
        set_info = api.advapi.SetNamedSecurityInfoW
        set_info.argtypes = [ctypes.c_wchar_p, files.U32, files.U32, files.PTR, files.PTR, files.PTR, files.PTR]
        set_info.restype = files.U32
        try:
            if sddl is not None:
                api.checked(api.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None),
                            "Native control security descriptor")
                api.checked(get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)),
                            "Native control GetSecurityDescriptorDacl")
                self.assertTrue(present.value)
            self.assertEqual(set_info(str(self.root_path), 1, 0x80000004, None, None, dacl, None), 0)
        finally:
            api._free(descriptor)

    @native_control
    def test_native_protected_root_owner_readback_reopen_and_exclusive_create(self):
        info = self.root.verify()
        self.assertTrue(info.protected_dacl)
        self.assertEqual(info.owner_sid, self.root._api.policy.owner_sid)
        with self.expected_rejection(files.FilesystemError):
            files.create_private_directory(self.root_path)
        self.root.close()
        with files.open_private_directory(self.root_path) as reopened:
            self.assertEqual(reopened.identity, info.identity)

    @native_control
    def test_native_default_inheritance_is_recognized_under_private_root(self):
        nested = self.root_path / "inherited"
        nested.mkdir()
        (nested / "raw").write_bytes(b"inherited-original")
        with self.root.open_directory("inherited") as directory:
            self.assertEqual(directory.read_bytes("raw", max_bytes=18), b"inherited-original")
        with self.expected_rejection(files.FilesystemError):
            files.open_private_directory(nested)

    @native_control
    def test_native_null_and_broad_dacl_rejected_by_real_readback(self):
        self.root.close()
        valid = self.root._api.policy.sddl(True)
        try:
            for bad in (valid + "(A;OICI;FA;;;WD)", None):
                self.set_fixture_dacl(bad)
                with self.expected_rejection(files.FilesystemError):
                    files.open_private_directory(self.root_path)
        finally:
            self.set_fixture_dacl(valid)
        with files.open_private_directory(self.root_path) as checked:
            self.assertTrue(checked.verify().protected_dacl)

    @native_control
    def test_native_parent_and_file_pins_block_rename_and_write(self):
        self.put("raw")
        with self.root.snapshot(max_bytes=100, max_members=2) as snapshot:
            with self.expected_rejection(OSError):
                os.rename(self.root_path, self.parent / "renamed")
            with self.expected_rejection(OSError):
                (self.root_path / "raw").write_bytes(b"replacement")
            with self.expected_rejection(OSError):
                os.rename(self.root_path / "raw", self.root_path / "renamed-raw")
            with snapshot.open_file("raw") as stream:
                self.assertEqual(stream.read(), b"native-original")
            snapshot.verify()
        self.assertEqual(self.root.read_bytes("raw", max_bytes=100), b"native-original")

    @native_control
    def test_native_hardlink_and_alternate_data_streams_rejected(self):
        self.put("hard")
        os.link(self.root_path / "hard", self.root_path / "hard-alias")
        with self.expected_rejection(files.FilesystemError):
            self.root.open_file("hard", max_bytes=100)
        self.put("ads")
        with open(str(self.root_path / "ads") + ":hidden", "wb") as stream:
            stream.write(b"must-not-be-omitted")
        with self.expected_rejection(files.FilesystemError):
            self.root.open_file("ads", max_bytes=100)

    @native_control
    def test_native_symlink_reparse_rejected_without_following_target(self):
        target = self.parent / "target"
        target.mkdir()
        (target / "unrelated").write_bytes(b"untouched")
        os.symlink(target, self.root_path / "linked", target_is_directory=True)
        with self.expected_rejection(files.FilesystemError):
            self.root.open_directory("linked")
        with self.expected_rejection(files.FilesystemError):
            files.open_private_directory(self.root_path / "linked")
        self.assertEqual((target / "unrelated").read_bytes(), b"untouched")
        (self.root_path / "linked").unlink()

    @native_control
    def test_native_bounded_tar_original_bytes_and_handle_retirement(self):
        payload = bytes(range(256)) * 513
        self.put("raw.bin", payload)
        with self.root.snapshot(max_bytes=len(payload), max_members=2) as snapshot:
            with snapshot.open_file("raw.bin") as stream:
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(files.CHUNK), b""):
                    digest.update(block)
            self.assertEqual(digest.digest(), hashlib.sha256(payload).digest())
            snapshot.verify()
        self.root.close()
        renamed = self.parent / "retired"
        os.rename(self.root_path, renamed)  # Native pins actually retired, not a model flag.
        renamed.rename(self.root_path)


class NativeFixtureOrchestrationTests(unittest.TestCase):
    """Only mocked test-fixture control flow; no Windows or real file operations."""
    def case(self):
        class RootModel:
            identity = (1, "synthetic")
            _api = SimpleNamespace(policy=SimpleNamespace(owner_sid=USER))
            close_count = 0
            verify_error = None
            close_error = None

            def verify(self):
                if self.verify_error is not None:
                    raise self.verify_error
                return SimpleNamespace(identity=self.identity, protected_dacl=True, owner_sid=USER)

            def close(self):
                self.close_count += 1
                if self.close_error is not None:
                    raise self.close_error

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        case = NativeWindowsTests("test_native_protected_root_owner_readback_reopen_and_exclusive_create")
        case.root = RootModel()
        case.parent = Path("/synthetic-never-created")
        case.root_path = case.parent / "private"
        case.retirement_unknown = False
        return case

    def uncertain(self):
        error = files.FilesystemError("Synthetic expected rejection plus uncertain cleanup")
        files._note(error, "Native handle retirement UNKNOWN: 202")
        return error

    def test_expected_rejection_cannot_swallow_unknown_retirement_or_dispose_fixture(self):
        case, error = self.case(), self.uncertain()
        with patch.object(files, "create_private_directory", side_effect=error), \
                patch.object(files, "open_private_directory", return_value=case.root) as reopen, \
                patch.object(shutil, "rmtree") as remove:
            with self.assertRaises(files.FilesystemError) as caught:
                case.test_native_protected_root_owner_readback_reopen_and_exclusive_create()
            self.assertIs(caught.exception, error)
            self.assertTrue(case.retirement_unknown)
            case.cleanup_fixture()
            self.assertFalse(reopen.called)
            self.assertFalse(remove.called)
            self.assertEqual(case.root.close_count, 1, "Known root closure must still be attempted")

    def test_known_expected_rejection_still_passes_and_disposes_only_its_owned_fixture(self):
        case = self.case()
        with patch.object(files, "create_private_directory", side_effect=files.FilesystemError("Known collision")), \
                patch.object(files, "open_private_directory", return_value=case.root), \
                patch.object(shutil, "rmtree") as remove:
            case.test_native_protected_root_owner_readback_reopen_and_exclusive_create()
            case.cleanup_fixture()
            self.assertFalse(case.retirement_unknown)
            remove.assert_called_once_with(case.parent)

    def test_unexpected_body_failure_also_records_unknown_and_retains_fixture(self):
        case, error = self.case(), self.uncertain()
        case.root.verify_error = error
        with patch.object(shutil, "rmtree") as remove:
            with self.assertRaises(files.FilesystemError) as caught:
                case.test_native_protected_root_owner_readback_reopen_and_exclusive_create()
            self.assertIs(caught.exception, error)
            case.cleanup_fixture()
            self.assertTrue(case.retirement_unknown)
            self.assertFalse(remove.called)
            self.assertEqual(case.root.close_count, 1)

    def test_cleanup_unknown_is_an_error_and_never_becomes_disposal_authority(self):
        case, error = self.case(), self.uncertain()
        case.root.close_error = error
        with patch.object(shutil, "rmtree") as remove:
            with self.assertRaises(files.FilesystemError) as caught:
                case.cleanup_fixture()
            self.assertIs(caught.exception, error)
            self.assertTrue(case.retirement_unknown)
            self.assertFalse(remove.called)

    def test_setup_unknown_retains_fixture_and_does_not_start_a_body(self):
        case, error = self.case(), self.uncertain()
        with patch.object(tempfile, "mkdtemp", return_value=str(case.parent)), \
                patch.object(files, "create_private_directory", side_effect=error), \
                patch.object(shutil, "rmtree") as remove:
            with self.assertRaises(files.FilesystemError) as caught:
                case.setUp()
            self.assertIs(caught.exception, error)
            self.assertIsNone(case.root)
            self.assertTrue(case.retirement_unknown)
            case.cleanup_fixture()
            self.assertFalse(remove.called)

    def test_wrapped_or_grouped_unknown_cleanup_is_not_hidden_from_the_guard(self):
        case, error = self.case(), self.uncertain()
        wrapper = files.FilesystemError("Primary failure")
        wrapper.__cause__ = error
        self.assertTrue(unknown_retirement(wrapper))
        grouped = files.FilesystemError("Grouped failure")
        grouped.exceptions = (error,)
        self.assertTrue(unknown_retirement(grouped))
        with self.assertRaises(files.FilesystemError) as caught:
            with case.expected_rejection(files.FilesystemError):
                raise wrapper
        self.assertIs(caught.exception, wrapper)
        self.assertTrue(case.retirement_unknown)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true", help="Run real NTFS/ACL/handle controls; requires native Windows")
    args = parser.parse_args()
    if args.native and os.name != "nt":
        print("NATIVE_WINDOWS_FILES=FAIL: --native requires genuine Windows, not this host", file=sys.stderr)
        return 2
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    for case in (PurePolicyTests, NativeCallShapeTests, ModelCustodyTests, NativeFixtureOrchestrationTests):
        suite.addTests(loader.loadTestsFromTestCase(case))
    if args.native:
        suite.addTests(loader.loadTestsFromTestCase(NativeWindowsTests))
    result = unittest.TextTestRunner(verbosity=2, failfast=args.native).run(suite)
    print("NATIVE_WINDOWS_FILES=" + ("PASS" if args.native and result.wasSuccessful() else
                                     "FAIL" if args.native else "NOT_RUN (offline/model controls only)"))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
