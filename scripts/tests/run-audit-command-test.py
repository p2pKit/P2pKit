#!/usr/bin/env python3
"""Real current-host executor fixtures; never product, device or interoperability evidence.

Fake wrappers are explicitly fixture programs, not Gradle successes. Test fixture
contexts explicitly preserve every parent ownership domain. The current host's real ownership controls
are mandatory; another host's tests are not selected or counted as native evidence.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes

SPEC = importlib.util.spec_from_file_location("audit_runner", SCRIPTS / "run-audit-command.py")
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
EXECUTOR = SCRIPTS / "run-audit-command.py"
PYTHON = str(Path(sys.executable).resolve())
EVIDENCE_ROOT = None
CASE_EVIDENCE = None


def property_spellings(expression):
    for short, long in (("D", "system-prop"), ("P", "project-prop")):
        yield [f"-{short}{expression}"]
        for option in (f"-{short}", f"--{short}", f"-{long}", f"--{long}"):
            yield [option, expression]
            if option != f"-{long}":
                yield [option + "=" + expression]


def archive_fixture_file(source, destination, budget, *, count_entry=True):
    runner.reject_symlinks(source)
    before = source.lstat()
    runner.require(stat.S_ISREG(before.st_mode), "Required fixture evidence is not a regular file")
    if count_entry:
        budget["entries"] += 1
    runner.require(budget["entries"] <= runner.MAX_ARCHIVE_FILES, "Fixture evidence entry count exceeds its bound")
    runner.reject_symlinks(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    size = 0
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, flags), "rb") as input_stream, runner.new_file(destination) as output_stream:
        opened = os.fstat(input_stream.fileno())
        runner.require(stat.S_ISREG(opened.st_mode) and os.path.samestat(before, opened),
                       "Fixture evidence was replaced before copying")
        for block in iter(lambda: input_stream.read(65536), b""):
            size += len(block)
            budget["bytes"] += len(block)
            runner.require(budget["bytes"] <= runner.MAX_ARCHIVE_BYTES, "Fixture evidence bytes exceed their bound")
            output_stream.write(block)
        output_stream.flush()
        os.fsync(output_stream.fileno())
        after = os.fstat(input_stream.fileno())
        runner.require((opened.st_size, opened.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and
                       size == opened.st_size, "Fixture evidence changed during copying; retain its original directory")
    return {"source": str(source), "retained": str(destination), "bytes": size,
            "sha256": runner.file_digest(destination)}


def archive_fixture_tree(source, destination, errors, budget=None):
    """Best effort means retain other safe files after a fault, never follow links.

    This copies observed fixture evidence, not synthetic successful receipts. Any
    failure keeps the generated source fixture for inspection and fails the test.
    """
    if budget is None:
        budget = {"entries": 0, "bytes": 0}
    records = []
    pending = [(source, destination, 0)]
    budget["entries"] += 1
    while pending:
        parent, target, depth = pending.pop()
        try:
            runner.require(depth <= 256, "Fixture evidence depth exceeds its bound")
            runner.require(runner.physical_directory_present(parent), "Required fixture evidence directory is missing")
            runner.require(not runner.within(destination, source), "Fixture archive must be outside its source tree")
            runner.require(budget["entries"] <= runner.MAX_ARCHIVE_FILES,
                           "Fixture evidence entry count exceeds its bound")
            runner.reject_symlinks(target)
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            with os.scandir(parent) as entries:
                for entry in entries:
                    try:
                        budget["entries"] += 1
                        runner.require(budget["entries"] <= runner.MAX_ARCHIVE_FILES,
                                       "Fixture evidence entry count exceeds its bound")
                        info = entry.stat(follow_symlinks=False)
                        runner.require(not stat.S_ISLNK(info.st_mode) and
                                       not (getattr(info, "st_file_attributes", 0) & 0x400),
                                       "Linked fixture evidence is not admissible")
                        path, retained = Path(entry.path), target / entry.name
                        if stat.S_ISDIR(info.st_mode):
                            pending.append((path, retained, depth + 1))
                        else:
                            records.append(archive_fixture_file(path, retained, budget, count_entry=False))
                    except Exception as error:
                        errors.append(f"Fixture evidence entry {entry.path}: {type(error).__name__}: {error}")
                        if budget["entries"] > runner.MAX_ARCHIVE_FILES or \
                                budget["bytes"] > runner.MAX_ARCHIVE_BYTES:
                            return records
        except Exception as error:
            errors.append(f"Fixture evidence directory {parent}: {type(error).__name__}: {error}")
    return records

FIXTURE = r'''import json, os, pathlib, signal, subprocess, sys, time
state = pathlib.Path(os.environ["P2PKIT_AUDIT_STATE_DIR"])
arguments = sys.argv[1:]
record = {"argv": arguments, "pid": os.getpid(), "home": os.environ.get("GRADLE_USER_HOME"),
          "job": os.environ.get("P2PKIT_AUDIT_JOB_ID"), "chain": os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN")}
with (state / "fixture-calls.jsonl").open("a", encoding="utf-8") as output:
    output.write(json.dumps(record) + "\n")
if "--stop" in arguments:
    sys.stdout.buffer.write(b"STOP-ONLY-STDOUT\n")
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(b"STOP-ONLY-STDERR\n")
    sys.stderr.buffer.flush()
    if os.environ.get("FIXTURE_STOP_HANG") == "yes":
        while True: time.sleep(.05)
    raise SystemExit(int(os.environ.get("FIXTURE_STOP_EXIT", "0")))
mode = arguments[0]
if mode == "argv":
    print(json.dumps(arguments, ensure_ascii=True))
    raise SystemExit(0)
if mode == "mutation":
    pathlib.Path("source.txt").write_text("mutated source\n", encoding="utf-8")
if mode in ("report", "project-report"):
    project = pathlib.Path(arguments[arguments.index("-p") + 1]) if mode == "project-report" else pathlib.Path(".")
    output = project / "build/test-results/fixture/result.xml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('<testsuite tests="1" failures="0"/>\n', encoding="utf-8")
if mode == "escape":
    code = """import json, os, pathlib, signal, time
if hasattr(signal, 'SIGTERM'): signal.signal(signal.SIGTERM, signal.SIG_IGN)
if hasattr(signal, 'SIGBREAK'): signal.signal(signal.SIGBREAK, signal.SIG_IGN)
pathlib.Path(os.environ['P2PKIT_AUDIT_STATE_DIR'], 'escaped-worker.json').write_text(json.dumps({'pid': os.getpid()}))
while True: time.sleep(.05)
"""
    options = {"creationflags": 0x208} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **options)
    ready = state / "escaped-worker.json"
    end = time.monotonic() + 10
    while not ready.exists():
        if time.monotonic() > end: raise SystemExit(9)
        time.sleep(.02)
if mode in ("hold", "timeout"):
    (state / "product-ready").write_text("ready\n")
    while not (state / "release-product").exists(): time.sleep(.02)
sys.stdout.buffer.write(b"PRODUCT-STDOUT\n")
sys.stdout.buffer.flush()
sys.stderr.buffer.write(b"PRODUCT-STDERR\n")
sys.stderr.buffer.flush()
raise SystemExit(7 if mode == "failure" else 0)
'''


class Capture:
    def __init__(self, child):
        self.child = child
        self.out, self.err = bytearray(), bytearray()
        self.errors = []
        self.threads = []
        self.directory = None
        if CASE_EVIDENCE is not None:
            self.directory = CASE_EVIDENCE / f"controller-{uuid.uuid4().hex}"
            self.directory.mkdir(mode=0o700)
            (self.directory / "start.json").write_text(json.dumps({"pid": child.pid}) + "\n")
        for source, destination, label in ((child.stdout, self.out, "stdout"), (child.stderr, self.err, "stderr")):
            log = (self.directory / f"{label}.log").open("xb", buffering=0) if self.directory else None
            thread = threading.Thread(target=self.copy, args=(source, destination, log), daemon=True)
            thread.start()
            self.threads.append(thread)

    def copy(self, source, destination, log):
        try:
            while True:
                block = source.read(65536)
                if not block:
                    return
                destination.extend(block)
                if log is not None:
                    log.write(block)
        except Exception as error:
            self.errors.append(f"Fixture capture failed: {type(error).__name__}: {error}")
        finally:
            try:
                source.close()
                if log is not None:
                    log.flush()
                    os.fsync(log.fileno())
                    log.close()
            except Exception as error:
                self.errors.append(f"Fixture capture close failed: {type(error).__name__}: {error}")

    def finish(self, scope, timeout=40):
        deadline = time.monotonic() + timeout
        while self.child.poll() is None:
            scope.discover()
            if time.monotonic() >= deadline:
                raise AssertionError("Fixture controller did not complete within its explicit bound")
            time.sleep(.05)
        for thread in self.threads:
            thread.join(timeout=5)
            if thread.is_alive():
                raise AssertionError("Fixture controller retained an open stdout/stderr pipe")
        if self.directory is not None:
            (self.directory / "completion.json").write_text(json.dumps({"pid": self.child.pid,
                "exitCode": self.child.poll(), "stdoutSha256": runner.digest(bytes(self.out)),
                "stderrSha256": runner.digest(bytes(self.err)), "errors": self.errors}) + "\n")
        if self.errors:
            raise AssertionError("; ".join(self.errors))
        return self.child.poll(), bytes(self.out), bytes(self.err)


class StatFields:
    """Override explicit metadata fields while forwarding the real no-follow result."""
    def __init__(self, actual, **fields):
        self.actual, self.fields = actual, fields

    def __getattr__(self, name):
        return self.fields[name] if name in self.fields else getattr(self.actual, name)


@contextmanager
def cleanup_metadata(test, *, cached_device=0, full_device=47, child_fields=None,
                     entry_fields=None, child_error=None, blocked_scan=None, leaf_fields=None):
    """Real tiny tree with modeled stat boundaries; never a native Windows claim.

    Windows DirEntry caches can have zero identity fields despite a nonzero full
    path-stat device. Keep type/reparse classification independent of that full
    observation so the tests cannot hide a removed no-follow or device guard.
    """
    with tempfile.TemporaryDirectory(prefix="audit cleanup metadata ") as temporary:
        root = Path(temporary).resolve() / "output"
        child, deeper = root / "nested", root / "nested/deeper"
        deeper.mkdir(parents=True)
        (deeper / "report.xml").write_bytes(b"synthetic report\n")
        directories = {root, child, deeper}
        events = []
        real_lstat, real_stat, real_scandir = Path.lstat, Path.stat, os.scandir

        def full_stat(path, *args, **kwargs):
            if path in directories:
                test.assertIs(kwargs.get("follow_symlinks", True), False, "Full stat must remain no-follow")
            return real_stat(path, *args, **kwargs)

        def full_lstat(path, *args, **kwargs):
            if path in directories:
                events.append(("lstat", path))
                if path == child and child_error is not None:
                    raise child_error
            actual = real_lstat(path, *args, **kwargs)
            if path == deeper / "report.xml" and leaf_fields is not None:
                return StatFields(actual, **{"st_dev": full_device, **leaf_fields})
            if path not in directories:
                return actual
            fields = {"st_dev": full_device}
            if path == child:
                fields.update(child_fields or {})
            return StatFields(actual, **fields)

        class Entry:
            def __init__(self, actual):
                self.actual, self.name, self.path = actual, actual.name, actual.path

            def stat(self, *, follow_symlinks=True):
                test.assertIs(follow_symlinks, False, "Initial entry classification must remain no-follow")
                events.append(("entry-stat", Path(self.path)))
                fields = {"st_dev": cached_device, "st_ino": 0, "st_nlink": 0}
                if Path(self.path) == child:
                    fields.update(entry_fields or {})
                return StatFields(self.actual.stat(follow_symlinks=follow_symlinks), **fields)

        @contextmanager
        def scan(path):
            path = Path(path)
            events.append(("scan", path))
            if path == {"root": root, "child": child}.get(blocked_scan):
                raise PermissionError("injected cleanup scan failure")
            with real_scandir(path) as entries:
                yield (Entry(entry) for entry in entries)

        with mock.patch.object(Path, "stat", new=full_stat), \
                mock.patch.object(Path, "lstat", new=full_lstat), mock.patch.object(os, "scandir", new=scan):
            yield root, child, deeper, events


class PurePolicyTests(unittest.TestCase):
    def test_readonly_retry_is_only_windows_exact_unlink_access_denied(self):
        denied = PermissionError(errno.EACCES, "synthetic original failure")
        denied.winerror = 5
        other_errno = PermissionError(errno.EPERM, "not the supported error")
        other_errno.winerror = 5
        other_winerror = PermissionError(errno.EACCES, "not the supported Windows error")
        other_winerror.winerror = 32
        impostor = mock.Mock(__name__="unlink")
        for platform, operation, error in (("linux", os.unlink, denied), ("darwin", os.unlink, denied),
                ("win32", os.rmdir, denied), ("win32", impostor, denied),
                ("win32", os.unlink, OSError(errno.EIO, "not a permission error")),
                ("win32", os.unlink, other_errno), ("win32", os.unlink, other_winerror)):
            with self.subTest(platform=platform, operation=operation, error=error), \
                    mock.patch.object(sys, "platform", platform), mock.patch.object(Path, "lstat") as metadata, \
                    mock.patch.object(os, "chmod") as chmod:
                persist = mock.Mock()
                self.assertFalse(runner.retry_windows_readonly_unlink(Path("unused"), {}, operation,
                                                                       "unused", error, {}, persist))
                metadata.assert_not_called()
                chmod.assert_not_called()
                persist.assert_not_called()

    def test_readonly_retry_refuses_unsafe_paths_ancestors_identity_types_and_hardlinks(self):
        denied = PermissionError(errno.EACCES, "synthetic original failure")
        denied.winerror = 5
        cases = ({"st_mode": stat.S_IFDIR | 0o700}, {"st_mode": stat.S_IFLNK | 0o777},
                 {"st_mode": stat.S_IFIFO | 0o600}, {"st_file_attributes": 0x421, "st_reparse_tag": 0xA000000C},
                 {"st_reparse_tag": 0xA0000003}, {"st_file_attributes": 0x20},
                 {"st_file_attributes": 0x3}, {"st_ino": 0}, {"st_nlink": 2}, {"st_dev": 53})
        for changed in cases:
            fields = {"st_file_attributes": 0x21, "st_reparse_tag": 0, **changed}
            with self.subTest(changed=changed), cleanup_metadata(self, leaf_fields=fields) as (root, _, deeper, _):
                identity = {"device": root.lstat().st_dev, "inode": root.lstat().st_ino}
                with mock.patch.object(sys, "platform", "win32"), mock.patch.object(os, "chmod") as chmod, \
                        mock.patch.object(os, "unlink") as unlink:
                    persist = mock.Mock()
                    with self.assertRaises(runner.AuditError):
                        runner.retry_windows_readonly_unlink(root, identity, os.unlink, deeper / "report.xml",
                                                               denied, {}, persist)
                    chmod.assert_not_called()
                    unlink.assert_not_called()
                    persist.assert_not_called()
        for child_fields, child_error, wrong_root in (({"st_file_attributes": 0x400}, None, False),
                ({"st_dev": 53}, None, False), ({}, PermissionError("unreadable parent"), False),
                ({}, FileNotFoundError("missing parent"), False), ({}, None, True)):
            with self.subTest(child_fields=child_fields, child_error=child_error, wrong_root=wrong_root), \
                    cleanup_metadata(self, child_fields=child_fields, child_error=child_error,
                                     leaf_fields={"st_file_attributes": 0x21, "st_reparse_tag": 0}) as fixture:
                root, _, deeper, _ = fixture
                identity = {"device": root.lstat().st_dev, "inode": root.lstat().st_ino ^ int(wrong_root)}
                with mock.patch.object(sys, "platform", "win32"), mock.patch.object(os, "chmod") as chmod, \
                        mock.patch.object(os, "unlink") as unlink:
                    persist = mock.Mock()
                    with self.assertRaises((runner.AuditError, OSError)):
                        runner.retry_windows_readonly_unlink(root, identity, os.unlink, deeper / "report.xml",
                                                               denied, {}, persist)
                    chmod.assert_not_called()
                    unlink.assert_not_called()
                    persist.assert_not_called()
        with cleanup_metadata(self) as (root, _, _, _):
            for leaf in (root, root.parent / "foreign", Path("relative"), root / ".." / "foreign", root / "file:stream"):
                with self.subTest(leaf=leaf), mock.patch.object(sys, "platform", "win32"), \
                        mock.patch.object(Path, "lstat") as metadata, mock.patch.object(os, "chmod") as chmod:
                    with self.assertRaises(runner.AuditError):
                        runner.retry_windows_readonly_unlink(root, {"inode": 1}, os.unlink, leaf, denied, {}, mock.Mock())
                    metadata.assert_not_called()
                    chmod.assert_not_called()

    def test_readonly_retry_retains_before_mutation_and_revalidates_before_one_unlink(self):
        cases = ((None, 0x21, 0x20), (None, 1, 0), (None, 1, 0x80),
                 *[(fault, 0x21, 0x20) for fault in ("journal", "before-identity", "chmod", "identity", "attributes", "unlink")])
        for fault, before_attributes, after_attributes in cases:
            fields = {"st_file_attributes": before_attributes, "st_reparse_tag": 0}
            with self.subTest(fault=fault, before=before_attributes, after=after_attributes), \
                    cleanup_metadata(self, leaf_fields=fields) as (root, _, deeper, _):
                leaf = deeper / "report.xml"
                identity = {"device": root.lstat().st_dev, "inode": root.lstat().st_ino}
                original_inode = leaf.lstat().st_ino
                denied = PermissionError(errno.EACCES, "synthetic original failure")
                denied.winerror = 5
                events, attempt = [], {}
                real_unlink = os.unlink

                def persist():
                    events.append("journal")
                    self.assertEqual(before_attributes, attempt["attributesBefore"])
                    if fault == "before-identity":
                        fields["st_ino"] = original_inode ^ 1
                    if fault == "journal":
                        raise OSError(errno.ENOSPC, "synthetic full evidence storage")

                def chmod(path, mode):
                    self.assertEqual((leaf, stat.S_IWRITE), (path, mode))
                    self.assertEqual(["journal"], events)
                    events.append("chmod")
                    if fault == "chmod":
                        raise PermissionError(errno.EACCES, "synthetic chmod failure")
                    fields["st_file_attributes"] = after_attributes if fault != "attributes" else 0x2
                    if fault == "identity":
                        fields["st_ino"] = original_inode ^ 1

                def unlink(path):
                    self.assertEqual(leaf, path)
                    self.assertEqual(["journal", "chmod"], events)
                    events.append("unlink")
                    if fault == "unlink":
                        raise PermissionError(errno.EACCES, "synthetic exact retry failure")
                    real_unlink(path)

                with mock.patch.object(sys, "platform", "win32"), mock.patch.object(os, "chmod", side_effect=chmod), \
                        mock.patch.object(os, "unlink", side_effect=unlink) as retry:
                    if fault is None:
                        self.assertTrue(runner.retry_windows_readonly_unlink(root, identity, os.unlink, leaf,
                                                                              denied, attempt, persist))
                        self.assertEqual("REMOVED", attempt["outcome"])
                    else:
                        with self.assertRaises((runner.AuditError, OSError)):
                            runner.retry_windows_readonly_unlink(root, identity, os.unlink, leaf, denied, attempt, persist)
                    self.assertEqual(1 if fault in (None, "unlink") else 0, retry.call_count)
                self.assertEqual(fault is not None, leaf.exists())

    def test_removal_diagnostic_reads_only_owned_no_follow_metadata(self):
        cases = ((stat.S_IFREG | 0o444, 1, 0, "file", True),
                 (stat.S_IFLNK | 0o777, 0x400, 0xA000000C, "symlink", False),
                 (stat.S_IFREG | 0o600, None, None, "file", None),
                 (stat.S_IFREG | 0o600, 2 ** 80, "not a native tag", "file", None))
        for mode, attributes, tag, kind, read_only in cases:
            with self.subTest(kind=kind, attributes=attributes), cleanup_metadata(self) as fixture:
                root, _, deeper, _ = fixture
                leaf = deeper / "report.xml"
                lstat, lookups = Path.lstat, []

                def metadata(path, *args, **kwargs):
                    lookups.append(path)
                    actual = lstat(path, *args, **kwargs)
                    return StatFields(actual, st_mode=mode, st_file_attributes=attributes, st_reparse_tag=tag) \
                        if path == leaf else actual

                error = PermissionError(errno.EACCES, "private exception text", "outside-private-filename")
                error.winerror = 5
                with mock.patch.object(Path, "lstat", new=metadata), \
                        mock.patch.object(Path, "resolve") as resolve, mock.patch.object(os, "readlink") as readlink, \
                        mock.patch.object(Path, "open") as opened:
                    detail = runner.removal_failure_detail(root, os.unlink, str(leaf), error)
                resolve.assert_not_called()
                readlink.assert_not_called()
                opened.assert_not_called()
                self.assertEqual([*reversed(leaf.parents), leaf], lookups)
                self.assertEqual(str(root), detail["failedRoot"])
                self.assertEqual("nested/deeper/report.xml", detail["relativePath"])
                self.assertEqual("unlink", detail["operation"])
                self.assertEqual(("PermissionError", errno.EACCES, 5),
                                 (detail["exceptionType"], detail["errno"], detail["winerror"]))
                observation = detail["metadataObservation"]
                self.assertEqual(("OBSERVED", mode, kind, read_only),
                                 (observation["status"], observation["mode"], observation["type"], observation["readOnly"]))
                self.assertTrue(observation["observedUtc"])
                self.assertEqual(attributes if attributes is None or attributes < 2 ** 32 else None,
                                 observation["fileAttributes"])
                self.assertEqual(tag if type(tag) is int else None, observation["reparseTag"])
                encoded = runner.json_bytes(detail)
                self.assertLessEqual(len(encoded), runner.MAX_REMOVAL_DETAIL_BYTES)
                for excluded in (b"private exception text", b"outside-private-filename", b"not a native tag"):
                    self.assertNotIn(excluded, encoded)

    def test_removal_diagnostic_refuses_foreign_relative_or_oversized_paths_before_stat(self):
        with cleanup_metadata(self) as (root, _, _, _):
            error = PermissionError(errno.EACCES, "private", "outside-private-filename")
            for entry in (str(root.parent / "outside-private-filename"), "relative", str(root / ".." / "outside"),
                          str(root / ("x" * 1025)), str(root / ("x" * 32769))):
                with self.subTest(entry_length=len(entry)), mock.patch.object(Path, "lstat") as metadata:
                    detail = runner.removal_failure_detail(root, os.unlink, entry, error)
                metadata.assert_not_called()
                self.assertEqual("REFUSED", detail["metadataObservation"]["status"])
                self.assertEqual("UNAVAILABLE", detail["relativePath"])
                self.assertNotIn(b"outside-private-filename", runner.json_bytes(detail))
            error.errno, error.winerror = "private nonnumeric errno", 2 ** 80
            with mock.patch.object(Path, "lstat") as metadata:
                detail = runner.removal_failure_detail(root, None, None, error)
            metadata.assert_not_called()
            self.assertEqual((None, None, "UNAVAILABLE", "UNAVAILABLE"),
                             (detail["errno"], detail["winerror"], detail["operation"], detail["relativePath"]))
            self.assertNotIn(b"private nonnumeric errno", runner.json_bytes(detail))

    def test_removal_diagnostic_stops_at_reparse_missing_or_unreadable_ancestor(self):
        cases = (({"st_file_attributes": 0x400, "st_reparse_tag": 0xA0000003}, None, "REFUSED"),
                 ({"st_mode": stat.S_IFLNK | 0o777}, None, "REFUSED"),
                 ({}, FileNotFoundError("injected absent ancestor"), "ABSENT"),
                 ({}, PermissionError("injected unreadable ancestor"), "UNAVAILABLE"))
        for fields, error, status in cases:
            with self.subTest(status=status, fields=fields), \
                    cleanup_metadata(self, child_fields=fields, child_error=error) as fixture:
                root, child, deeper, events = fixture
                with mock.patch.object(Path, "resolve") as resolve, mock.patch.object(os, "readlink") as readlink, \
                        mock.patch.object(Path, "open") as opened:
                    detail = runner.removal_failure_detail(root, os.unlink, deeper / "report.xml", PermissionError())
                self.assertEqual(status, detail["metadataObservation"]["status"])
                self.assertIn(("lstat", child), events)
                self.assertNotIn(("lstat", deeper), events)
                resolve.assert_not_called()
                readlink.assert_not_called()
                opened.assert_not_called()

    def test_cleanup_directory_identity_uses_full_stat_not_cached_fields(self):
        for cached, full in ((0, 47), (47, 47), (0, 0), (47, 0)):
            with self.subTest(cached=cached, full=full), \
                    cleanup_metadata(self, cached_device=cached, full_device=full) as (root, child, deeper, events):
                inspection = runner.inspect_disposable_tree(root)
                self.assertEqual(inspection["entryCount"], 3)
                self.assertEqual(inspection["links"], [])
                self.assertTrue(inspection["noTargetTraversal"])
                self.assertEqual([path for kind, path in events if kind == "scan"], [root, child, deeper])
                for directory in (child, deeper):
                    self.assertIn(("lstat", directory), events)
                    self.assertLess(events.index(("lstat", directory)), events.index(("scan", directory)))

    def test_cleanup_rejects_actual_cross_device_before_descending(self):
        for root_device, child_device in ((47, 53), (47, 0), (0, 53)):
            for cached in (0, 47):
                with self.subTest(root_device=root_device, child_device=child_device, cached=cached), \
                        cleanup_metadata(self, cached_device=cached, full_device=root_device,
                                         child_fields={"st_dev": child_device}) as fixture:
                    root, child, _, events = fixture
                    with self.assertRaisesRegex(runner.AuditError, "Cross-device descendant directory"):
                        runner.inspect_disposable_tree(root)
                    self.assertIn(("lstat", child), events)
                    self.assertNotIn(("scan", child), events)

    def test_cleanup_revalidates_directory_type_before_descending(self):
        for mode in (stat.S_IFREG, stat.S_IFLNK, stat.S_IFIFO):
            with self.subTest(mode=mode), cleanup_metadata(self, cached_device=47,
                    child_fields={"st_mode": mode | 0o700, "st_file_attributes": 0}) as fixture:
                root, child, _, events = fixture
                with self.assertRaisesRegex(runner.AuditError, "Descendant changed from a physical directory"):
                    runner.inspect_disposable_tree(root)
                self.assertIn(("lstat", child), events)
                self.assertNotIn(("scan", child), events)

    def test_cleanup_revalidates_directory_reparse_before_descending(self):
        for tag in (0xA0000003, 0xA000000C, 0x80000042):
            with self.subTest(tag=tag), cleanup_metadata(self, cached_device=47,
                    child_fields={"st_file_attributes": 0x400, "st_reparse_tag": tag}) as fixture:
                root, child, _, events = fixture
                with self.assertRaisesRegex(runner.AuditError, "Descendant changed from a physical directory"):
                    runner.inspect_disposable_tree(root)
                self.assertIn(("lstat", child), events)
                self.assertNotIn(("scan", child), events)

    def test_cleanup_rejects_unknown_cached_reparse_before_path_stat(self):
        with cleanup_metadata(self, entry_fields={"st_file_attributes": 0x400, "st_reparse_tag": 0x80000042},
                child_error=AssertionError("Unknown reparse must be rejected before full path lookup")) as fixture:
            root, child, _, events = fixture
            with mock.patch.object(os, "readlink", side_effect=AssertionError("Unknown reparse target was read")):
                with self.assertRaisesRegex(runner.AuditError, "Unknown descendant reparse type"):
                    runner.inspect_disposable_tree(root)
            self.assertNotIn(("lstat", child), events)
            self.assertNotIn(("scan", child), events)

    def test_cleanup_directory_full_stat_errors_fail_closed(self):
        for error in (FileNotFoundError("injected missing child"), PermissionError("injected child permission"),
                      OSError(errno.EIO, "injected child I/O")):
            with self.subTest(error=type(error).__name__), cleanup_metadata(self, child_error=error) as fixture:
                root, child, _, events = fixture
                with self.assertRaises(type(error)) as failure:
                    runner.inspect_disposable_tree(root)
                self.assertIs(failure.exception, error)
                self.assertNotIn(("scan", child), events)

    def test_cleanup_scan_failures_and_entry_bound_stay_fail_closed(self):
        for blocked in ("root", "child"):
            with self.subTest(blocked=blocked), cleanup_metadata(self, blocked_scan=blocked) as fixture:
                with self.assertRaisesRegex(PermissionError, "injected cleanup scan failure"):
                    runner.inspect_disposable_tree(fixture[0])
        with cleanup_metadata(self) as fixture, mock.patch.object(runner, "MAX_CLEANUP_ENTRIES", 1):
            with self.assertRaisesRegex(runner.AuditError, "Disposable output entry count exceeds its bound"):
                runner.inspect_disposable_tree(fixture[0])

    def test_cleanup_initial_special_file_is_rejected_before_path_stat(self):
        with cleanup_metadata(self, entry_fields={"st_mode": stat.S_IFIFO | 0o600}) as fixture:
            root, child, _, events = fixture
            with self.assertRaisesRegex(runner.AuditError, "Unexpected special file blocks disposable-output cleanup"):
                runner.inspect_disposable_tree(root)
            self.assertNotIn(("lstat", child), events)
            self.assertNotIn(("scan", child), events)

    def test_fixture_markers_are_flushed_raw_bytes_under_both_text_newline_policies(self):
        # Exercise the actual embedded program, not a duplicate marker implementation.
        # Buffered binary streams make a missing explicit flush observable before close.
        cases = ((["success"], 0, 0, b"PRODUCT"), (["failure"], 0, 7, b"PRODUCT"),
                 (["--stop"], 0, 0, b"STOP-ONLY"), (["--stop"], 7, 7, b"STOP-ONLY"))
        for newline in ("\n", "\r\n"):
            for arguments, stop_status, expected_status, marker in cases:
                with self.subTest(newline=repr(newline), arguments=arguments, stop_status=stop_status), \
                        tempfile.TemporaryDirectory(prefix="audit fixture newline ") as temporary:
                    stdout_bytes, stderr_bytes = io.BytesIO(), io.BytesIO()
                    with io.TextIOWrapper(io.BufferedWriter(stdout_bytes), encoding="utf-8", newline=newline) as stdout, \
                            io.TextIOWrapper(io.BufferedWriter(stderr_bytes), encoding="utf-8", newline=newline) as stderr:
                        environment = {"P2PKIT_AUDIT_STATE_DIR": temporary, "FIXTURE_STOP_HANG": "no",
                                       "FIXTURE_STOP_EXIT": str(stop_status)}
                        with mock.patch.dict(os.environ, environment), \
                                mock.patch.object(sys, "argv", ["fixture.py", *arguments]), \
                                mock.patch.object(sys, "stdout", stdout), mock.patch.object(sys, "stderr", stderr):
                            with self.assertRaises(SystemExit) as stopped:
                                exec(compile(FIXTURE, "actual-audit-fixture", "exec"), {})
                        self.assertEqual(stopped.exception.code, expected_status)
                        for stream, captured in ((b"STDOUT", stdout_bytes), (b"STDERR", stderr_bytes)):
                            with self.subTest(stream=stream):
                                self.assertEqual(captured.getvalue(), marker + b"-" + stream + b"\n")
                    calls = (Path(temporary) / "fixture-calls.jsonl").read_text(encoding="utf-8").splitlines()
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(json.loads(calls[0])["argv"], arguments)

    def test_resource_flags_and_original_arguments_are_preserved(self):
        original = ["publishToMavenLocal", "-Dmaven.repo.local=/tmp/fixture repository", "--configure-on-demand"]
        snapshot = list(original)
        result = runner.gradle_arguments(original)
        self.assertEqual(original, snapshot)
        self.assertEqual(result[:len(original)], original)
        self.assertNotIn("--no-configure-on-demand", result)
        self.assertIn("--no-parallel", result)
        self.assertIn("--max-workers=2", result)
        self.assertIn("strict", result)

    def test_real_init_script_negative_control_is_not_removed(self):
        original = ["indirectLockRefresh", "--dry-run", "--init-script", "/tmp/owned-policy.init.gradle.kts"]
        self.assertEqual(runner.gradle_arguments(original)[:len(original)], original)

    def test_security_resource_and_home_overrides_are_rejected(self):
        for arguments in (["check", "--parallel"], ["check", "--max-workers", "3"],
                          ["check", "--dependency-verification=off"], ["check", "--build-cache"],
                          ["check", "-g/tmp/shared"], ["check", "--gradle-user-home=/tmp/shared"],
                          ["check", "-Foff"], ["check", "-F", "lenient"],
                          ["check", "-Dorg.gradle.jvmargs=-Xmx8g"],
                          ["check", "-Pkotlin.compiler.execution.strategy=daemon"],
                          ["check", "-Dorg.gradle.java.home=/unowned"], ["check", "--write-verification-metadata=sha256"]):
            with self.subTest(arguments=arguments), self.assertRaises(runner.AuditError):
                runner.gradle_arguments(arguments)

    def test_every_property_alias_preserves_accepted_raw_tokens(self):
        expressions = ["maven.repo.local=/tmp/fixture repository", "fixture.value=first=second",
                       "fixture.flag", "fixture.empty=", "org.gradle.parallel=false",
                       "org.gradle.workers.max=2", "org.gradle.daemon=false",
                       "org.gradle.caching=false", "org.gradle.configuration-cache=false",
                       "org.gradle.jvmargs=" + runner.JVM_ARGUMENTS,
                       "kotlin.compiler.execution.strategy=in-process"]
        for expression in expressions:
            for spelling in property_spellings(expression):
                with self.subTest(expression=expression, spelling=spelling):
                    original = ["fixtureTask", *spelling, "--configure-on-demand", "--init-script", "/tmp/control.init"]
                    snapshot = list(original)
                    result = runner.gradle_arguments(original)
                    self.assertEqual(original, snapshot)
                    self.assertEqual(result, [*snapshot, *runner.AUDIT_FLAGS])

    def test_every_property_alias_rejects_home_resource_toolchain_and_security_override(self):
        expressions = ["gradle.user.home=/foreign/home", "gradle.user.home", "gradle.user.home=",
                       "java.home=/foreign/jdk",
                       "org.gradle.java.home=/foreign/jdk", "org.gradle.jvmargs=-Xmx8g",
                       "org.gradle.java.installations.paths=/foreign/jdk",
                       "org.gradle.java.installations.auto-download=true",
                       "org.gradle.parallel=true", "org.gradle.workers.max=3", "org.gradle.daemon=true",
                       "org.gradle.caching=true", "org.gradle.configuration-cache=true",
                       "org.gradle.dependency.verification=off", "org.gradle.project.fixture=override",
                       "kotlin.compiler.execution.strategy=daemon", "kotlin.daemon.jvmargs=-Xmx8g"]
        for expression in expressions:
            for spelling in property_spellings(expression):
                with self.subTest(expression=expression, spelling=spelling), self.assertRaises(runner.AuditError):
                    runner.gradle_arguments(["check", *spelling])

    def test_conflicting_option_aliases_and_inner_terminator_are_not_hidden(self):
        for name, value in (("g", "/foreign/home"), ("gradle-user-home", "/foreign/home"),
                            ("F", "off"), ("M", "sha256"), ("max-workers", "3"),
                            ("dependency-verification", "off"), ("console", "rich")):
            for prefix in ("-", "--"):
                for spelling in ([prefix + name, value], [prefix + name + "=" + value]):
                    with self.subTest(spelling=spelling), self.assertRaises(runner.AuditError):
                        runner.gradle_arguments(["check", *spelling])
        for arguments in (["check", "--", "--max-workers=3"], ["--", "check"],
                          ["check", "-system-prop=maven.repo.local=/tmp/fixture"],
                          ["check", "-project-prop=fixture.option=value"],
                          ["check", "-qDgradle.user.home=/foreign/home"], ["check", "-qD", "gradle.user.home=/foreign/home"],
                          ["check", "-imPorg.gradle.parallel=true"], ["check", "-qt"]):
            with self.subTest(arguments=arguments), self.assertRaises(runner.AuditError):
                runner.gradle_arguments(arguments)

    def test_missing_or_empty_property_keys_are_rejected_without_guessing(self):
        for option in ("-D", "-P", "--D", "--P", "--system-prop", "--project-prop", "-system-prop", "-project-prop"):
            for suffix in ([], [""], ["=value"], ["--parallel"]):
                arguments = ["check", option, *suffix]
                with self.subTest(arguments=arguments), self.assertRaises(runner.AuditError):
                    runner.gradle_arguments(arguments)
            with self.subTest(option=option), self.assertRaises(runner.AuditError):
                runner.gradle_arguments(["check", option + "="])

    def test_report_root_and_descendant_scan_errors_are_not_empty_success(self):
        # Deliberate function-level faults, not claims of native permissions or
        # a Gradle execution. PermissionError is injected even when running as root.
        with tempfile.TemporaryDirectory(prefix="audit report scan fixture ") as temporary:
            root = Path(temporary).resolve() / "source"
            state = Path(temporary).resolve() / "state"
            module = root / "library"
            reports = root / "build/reports"
            nested = reports / "nested"
            for directory in (state, module, nested):
                directory.mkdir(parents=True)
            (nested / "report.json").write_text('{"fixtureOnly":true}\n')
            actual_scandir = os.scandir
            for blocked in (module, reports, nested):
                def unavailable(path, *, target=blocked):
                    if Path(path) == target:
                        raise PermissionError("injected required inventory failure")
                    return actual_scandir(path)
                with self.subTest(blocked=blocked), mock.patch.object(runner.os, "scandir", side_effect=unavailable):
                    with self.assertRaisesRegex(PermissionError, "injected required inventory failure"):
                        runner.report_snapshot(root, state, [])

    def test_source_and_evidence_lstat_failures_are_not_treated_as_absence(self):
        with tempfile.TemporaryDirectory(prefix="audit report stat fixture ") as temporary:
            root = Path(temporary).resolve() / "source"
            state = Path(temporary).resolve() / "state"
            (root / "library").mkdir(parents=True)
            (root / "build/reports").mkdir(parents=True)
            state.mkdir()
            actual_lstat = Path.lstat
            for blocked in (root / "library", root / "build/reports"):
                def unavailable(path, *args, target=blocked, **kwargs):
                    if path == target:
                        raise PermissionError("injected required lstat failure")
                    return actual_lstat(path, *args, **kwargs)
                with self.subTest(blocked=blocked), mock.patch.object(Path, "lstat", new=unavailable):
                    with self.assertRaisesRegex(PermissionError, "injected required lstat failure"):
                        runner.report_snapshot(root, state, [])

    def test_report_entry_bound_counts_empty_directories_not_just_files(self):
        with tempfile.TemporaryDirectory(prefix="audit report bound fixture ") as temporary:
            root = Path(temporary).resolve() / "source"
            state = Path(temporary).resolve() / "state"
            for name in ("one", "two", "three", "four"):
                (root / "build/reports" / name).mkdir(parents=True)
            state.mkdir()
            with mock.patch.object(runner, "MAX_ARCHIVE_FILES", 3):
                with self.assertRaisesRegex(runner.AuditError, "entry count"):
                    runner.report_snapshot(root, state, [])

    def test_nested_environment_keeps_parent_and_binds_job_home(self):
        job, outer, inner = (uuid.uuid4().hex for _ in range(3))
        first = processes.ownership_environment({}, job, outer, "/state", "/home")
        second = processes.ownership_environment(first, job, inner, "/state", "/home")
        self.assertEqual(second[processes.CHAIN_ENV], outer + ":" + inner)
        with self.assertRaises(processes.OwnershipError):
            processes.ownership_environment({**first, "GRADLE_USER_HOME": "/different"}, job, inner, "/state", "/home")
        with self.assertRaises(processes.OwnershipError):
            processes.ownership_environment(first, uuid.uuid4().hex, inner, "/state", "/home")

    def test_explicit_fixture_context_crossing_preserves_exact_parent_domain(self):
        parent_job, child_job, outer, inner = (uuid.uuid4().hex for _ in range(4))
        first = processes.ownership_environment({}, parent_job, outer, "/parent-state", "/parent-home")
        child = processes.ownership_environment(first, child_job, inner, "/child-state", "/child-home",
                                                allow_new_context=True)
        domains = processes.ownership_domains(child[processes.CHAIN_ENV], child[processes.DOMAINS_ENV])
        self.assertEqual(domains, [{"id": outer, "job": parent_job, "state": "/parent-state", "home": "/parent-home"},
                                  {"id": inner, "job": child_job, "state": "/child-state", "home": "/child-home"}])
        invalid = {**first, processes.DOMAINS_ENV: "[]"}
        with self.assertRaises(processes.OwnershipError):
            processes.ownership_environment(invalid, child_job, inner, "/child-state", "/child-home",
                                            allow_new_context=True)

    def test_procargs_parser_discards_argv_and_selects_exact_environment(self):
        import struct
        raw = struct.pack("=i", 3) + b"/usr/bin/python\0\0python\0-c\0private payload\0" + \
            b"PRIVATE=not retained\0P2PKIT_AUDIT_JOB_ID=job\0P2PKIT_AUDIT_OWNERSHIP_CHAIN=outer:inner\0\0"
        result = processes.parse_procargs2(raw)
        self.assertEqual(result, {b"P2PKIT_AUDIT_JOB_ID": b"job", b"P2PKIT_AUDIT_OWNERSHIP_CHAIN": b"outer:inner"})
        for malformed in (b"", b"\1\0\0\0no terminator", raw[:16]):
            with self.subTest(malformed=malformed), self.assertRaises(processes.OwnershipError):
                processes.parse_procargs2(malformed)

    def test_restricted_batch_grammar_rejects_expansion_and_control(self):
        for value in ("%PATH%", "bang!", 'quote"', "pipe|", "and&", "lt<", "gt>", "caret^", "paren(", "line\n"):
            with self.subTest(value=value), self.assertRaises(processes.OwnershipError):
                processes.batch_command_line(r"C:\Windows\System32\cmd.exe", [r"C:\root\gradlew.bat", value])
        command = processes.batch_command_line(r"C:\Windows\System32\cmd.exe",
                                               [r"C:\space root\gradlew.bat", "two words", "Ω", "", "tail\\"])
        self.assertIn('/d /s /v:off /c ""', command)
        self.assertIn('""', command)

    def test_structure_layouts_are_explicit_not_native_acceptance(self):
        self.assertEqual(tuple(ctypes.sizeof(kind) for kind in (processes.DarwinBsdInfo, processes.DarwinUniqueInfo,
                                                               processes.DarwinIdentity, processes.AuditToken)),
                         (136, 56, 192, 32))
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(tuple(ctypes.sizeof(kind) for kind in (processes.SecurityAttributes,
                processes.ProcessInformation, processes.StartupInfo, processes.StartupInfoEx,
                processes.JobBasicLimits, processes.IoCounters, processes.JobExtendedLimits)),
                (24, 24, 104, 112, 64, 48, 144))


class DarwinObservationTests(unittest.TestCase):
    """Scripted Darwin API transitions, not native Mach/cleanup acceptance."""

    def setUp(self):
        self.scope = processes.DarwinScope.__new__(processes.DarwinScope)
        self.scope.job, self.scope.invocation = "a" * 32, "b" * 32
        self.scope.state, self.scope.home = "/fixture-state", "/fixture-home"
        self.scope.known, self.scope.handles = {}, {}
        self.scope.leaders, self.scope.launches = [], []
        self.scope.discovery_errors, self.scope.baseline = set(), set()
        self.scope.observation_reconciliations = []
        self.scope.self_port, self.scope.argmax = 7, 4096
        self.scope.system, self.scope.proc = mock.Mock(), mock.Mock()
        self.identity = {"pid": 43210, "uid": 1000, "realUid": 1000, "parentPid": 1, "group": 43210,
                         "uniqueId": 99, "parentUniqueId": 1, "pidVersion": 3,
                         "startSeconds": 123, "startMicroseconds": 456,
                         "status": 2, "flags": 4, "live": True}
        self.current = dict(self.identity)
        self.scope._identity = mock.Mock(side_effect=lambda _pid, **_kwargs:
                                        None if self.current is None else dict(self.current))
        self.scope._pids = lambda: [self.identity["pid"]]
        self.scope.system.task_name_for_pid.return_value = 5
        self.scope.system.mach_port_deallocate.return_value = 0
        self.elapsed = 0.0
        self.on_sleep = lambda: None

    @contextmanager
    def clock(self):
        def sleep(seconds):
            self.assertGreater(seconds, 0)
            self.elapsed += seconds
            self.on_sleep()
        with mock.patch.object(processes.time, "monotonic", side_effect=lambda: self.elapsed), \
                mock.patch.object(processes.time, "sleep", side_effect=sleep):
            yield

    def test_exiting_task_name_error_reconciles_to_terminal_not_inexit(self):
        for terminal in (None, {**self.identity, "status": 5, "live": False}):
            with self.subTest(terminal=terminal):
                self.current, self.elapsed = dict(self.identity), 0.0
                self.on_sleep = lambda: setattr(self, "current", terminal)
                with self.clock(), self.assertRaises(ProcessLookupError):
                    self.scope._acquire(self.identity)
                self.assertGreater(self.elapsed, 0, "INEXIT itself must not count as completed cleanup")
                self.scope.system.task_info.assert_not_called()
                self.scope.system.mach_port_deallocate.assert_not_called()

    def test_transient_environment_error_recovers_without_poisoning_discovery(self):
        environment = processes.ownership_environment({}, self.scope.job, self.scope.invocation,
                                                        self.scope.state, self.scope.home)
        raw = processes.struct.pack("=i", 1) + b"/fixture\0\0fixture\0" + b"\0".join(
            key.encode() + b"=" + value.encode() for key, value in environment.items()) + b"\0"
        for error in (errno.EINVAL, errno.EIO):
            with self.subTest(errno=error):
                self.scope.known.clear()
                self.scope.handles.clear()
                self.scope.discovery_errors.clear()
                self.elapsed = 0.0
                calls = []

                def sysctl(_mib, _count, data, length, _new, _size):
                    calls.append(True)
                    if len(calls) == 1:
                        ctypes.set_errno(error)
                        return -1
                    ctypes.memmove(data, raw, len(raw))
                    ctypes.cast(length, ctypes.POINTER(processes.SIZE)).contents.value = len(raw)
                    return 0

                self.scope.system.sysctl.side_effect = sysctl
                with self.clock(), mock.patch.object(processes.os, "getuid", return_value=1000, create=True), \
                        mock.patch.object(self.scope, "_acquire", return_value=processes.AuditToken()):
                    self.assertEqual(self.scope.discover(), [self.identity])
                self.assertEqual(self.scope.discovery_errors, set())
                self.assertEqual(len(calls), 2)

    def test_persistent_live_or_inexit_denial_is_bounded_and_fatal(self):
        for status, flags in ((2, 4), (2, 0), (2, 0x4000), (4, 0)):
            with self.subTest(status=status, flags=flags):
                self.current = {**self.identity, "status": status, "flags": flags}
                self.elapsed = 0.0
                self.scope.system.task_name_for_pid.reset_mock()
                with self.clock(), self.assertRaisesRegex(processes.OwnershipError, "unresolved"):
                    self.scope._acquire(self.identity)
                self.assertGreater(self.elapsed, 0)
                self.assertLessEqual(self.elapsed, 0.250001)
                self.assertLessEqual(self.scope.system.task_name_for_pid.call_count, 26)
                event = self.scope.description()["observationReconciliations"][-1]
                self.assertEqual(event["outcome"], "unresolved")
                self.assertEqual(event["lastIdentity"], self.current)
                self.assertIn("Mach result 5", event["firstFailure"])

    def test_reused_pid_does_not_acquire_or_signal_the_replacement(self):
        self.on_sleep = lambda: setattr(self, "current", {**self.identity, "uniqueId": 100})
        with self.clock(), self.assertRaises(ProcessLookupError):
            self.scope._acquire(self.identity)
        self.assertEqual(self.scope.system.task_name_for_pid.call_count, 1)
        self.scope.system.task_info.assert_not_called()
        self.scope.proc.proc_signal_with_audittoken.assert_not_called()
        self.assertEqual(self.scope.observation_reconciliations[-1]["outcome"], "replaced")

    def test_token_retries_release_ports_and_revalidate_exec_versions(self):
        for failure in ("task-name", "task-info", "token-size", "exec-version"):
            with self.subTest(failure=failure):
                self.current, self.elapsed = dict(self.identity), 0.0
                names, infos = [], []
                self.scope.system.mach_port_deallocate.reset_mock()

                def task_name(_self, _pid, port):
                    names.append(True)
                    ctypes.cast(port, ctypes.POINTER(processes.U32)).contents.value = 81
                    return 5 if failure == "task-name" and len(names) == 1 else 0

                def task_info(_port, _flavor, _token, count):
                    infos.append(True)
                    if len(names) == 1:
                        if failure == "task-info":
                            return 4
                        if failure == "token-size":
                            ctypes.cast(count, ctypes.POINTER(processes.U32)).contents.value = 7
                        if failure == "exec-version":
                            self.current["pidVersion"] += 1
                    return 0

                self.scope.system.task_name_for_pid.side_effect = task_name
                self.scope.system.task_info.side_effect = task_info
                with self.clock():
                    token = self.scope._acquire(self.identity)
                self.assertIsInstance(token, processes.AuditToken)
                self.assertEqual((len(names), self.scope.system.mach_port_deallocate.call_count), (2, 2))
                self.scope.proc.proc_signal_with_audittoken.assert_not_called()
                self.assertEqual(self.scope.observation_reconciliations[-1]["outcome"], "recovered")

    def test_port_release_failure_is_never_retried_or_masked_by_later_exit(self):
        def task_name(_self, _pid, port):
            ctypes.cast(port, ctypes.POINTER(processes.U32)).contents.value = 81
            return 5

        def failed_release(*_args):
            self.current = None
            return 5

        self.scope.system.task_name_for_pid.side_effect = task_name
        self.scope.system.mach_port_deallocate.side_effect = failed_release
        with self.clock(), self.assertRaisesRegex(processes.OwnershipError, "Cannot release"):
            self.scope._acquire(self.identity)
        self.assertEqual(self.elapsed, 0)
        self.assertEqual(self.scope.system.task_name_for_pid.call_count, 1)
        self.assertEqual(self.scope.system.mach_port_deallocate.call_count, 1)

    def test_required_identity_denial_or_ambiguous_empty_response_is_not_absence(self):
        self.scope._identity = processes.DarwinScope._identity.__get__(self.scope)
        for error in (0, errno.EPERM, errno.EACCES):
            with self.subTest(errno=error):
                self.elapsed = 0.0

                def unavailable(*_args):
                    ctypes.set_errno(error)
                    return 0

                self.scope.proc.proc_pidinfo.side_effect = unavailable
                with self.clock(), self.assertRaisesRegex(processes.OwnershipError, "unresolved"):
                    self.scope._acquire(self.identity)
                self.scope.system.task_name_for_pid.assert_not_called()
                self.assertEqual(self.scope.observation_reconciliations[-1]["outcome"], "unresolved")

    def test_native_status_flags_are_retained_but_only_zombie_is_terminal(self):
        self.scope._identity = processes.DarwinScope._identity.__get__(self.scope)
        for status, flags, live in ((2, 4, True), (2, 0x4000, True), (4, 0, True), (5, 4, False), (0, 4, None)):
            with self.subTest(status=status, flags=flags):
                def pidinfo(pid, _flavor, _arg, pointer, _size):
                    value = ctypes.cast(pointer, ctypes.POINTER(processes.DarwinIdentity)).contents
                    value.bsd.pid, value.bsd.uid = pid, 1000
                    value.bsd.status, value.bsd.flags = status, flags
                    return ctypes.sizeof(value)

                self.scope.proc.proc_pidinfo.side_effect = pidinfo
                if live is None:
                    with self.assertRaises(processes.OwnershipError):
                        self.scope._identity(self.identity["pid"], required=True)
                else:
                    result = self.scope._identity(self.identity["pid"], required=True)
                    self.assertEqual((result["status"], result["flags"], result["live"]), (status, flags, live))

    def test_persistent_environment_parser_failure_is_not_cleared_by_eligibility_read(self):
        ordinary_reads = []

        def identity(_pid, *, required=False):
            if required:
                return dict(self.identity)
            ordinary_reads.append(True)
            return dict(self.identity) if len(ordinary_reads) == 1 else None

        def malformed(_mib, _count, _data, length, _new, _size):
            ctypes.cast(length, ctypes.POINTER(processes.SIZE)).contents.value = 0
            return 0

        self.scope._identity.side_effect = identity
        self.scope.system.sysctl.side_effect = malformed
        with self.clock(), mock.patch.object(processes.os, "getuid", return_value=1000, create=True):
            self.assertEqual(self.scope.discover(), [])
        self.assertEqual(len(self.scope.discovery_errors), 1)
        self.assertEqual(len(ordinary_reads), 1, "A reconciled fatal must not be reclassified as ineligible")
        self.assertEqual(self.scope.observation_reconciliations[-1]["outcome"], "unresolved")

    def test_owned_candidate_identity_denial_is_not_skipped_before_acquisition(self):
        denied = False

        def identity(_pid, *, required=False):
            if denied:
                if required:
                    raise processes.DarwinObservationError("bound identity access denied")
                return None
            return dict(self.identity)

        def ours(_environment):
            nonlocal denied
            denied = True
            return True

        self.scope._identity.side_effect = identity
        with self.clock(), mock.patch.object(processes.os, "getuid", return_value=1000, create=True), \
                mock.patch.object(self.scope, "_inspect_environment", return_value={}), \
                mock.patch.object(self.scope, "_ours", side_effect=ours), \
                self.assertRaisesRegex(processes.OwnershipError, "bound identity access denied"):
            self.scope.discover()
        self.scope.system.task_name_for_pid.assert_not_called()

    def test_consumer_identity_observes_darwin_lifetime_without_signaling_or_reacquiring(self):
        fixture = PosixNativeTests()
        fixture.scope = self.scope
        entry = {"identity": self.identity, "handle": processes.AuditToken()}
        # XNU rejects signal zero before inspecting the token. This API cannot
        # implement Linux's pidfd liveness probe, even for a valid live token.
        self.scope.proc.proc_signal_with_audittoken.return_value = errno.EINVAL
        self.assertTrue(fixture.consumer_identity_live(entry))
        for terminal in (None, {**self.identity, "status": 5, "live": False},
                         {**self.identity, "uniqueId": 100}):
            with self.subTest(terminal=terminal):
                self.current = terminal
                self.assertFalse(fixture.consumer_identity_live(entry))
        self.scope.proc.proc_signal_with_audittoken.assert_not_called()
        self.scope.system.task_name_for_pid.assert_not_called()

    def test_consumer_identity_refuses_changed_darwin_epoch_credentials_or_unknown_liveness(self):
        fixture = PosixNativeTests()
        fixture.scope = self.scope
        entry = {"identity": self.identity, "handle": processes.AuditToken()}
        for field in ("pidVersion", "uid", "realUid"):
            with self.subTest(field=field):
                self.current = {**self.identity, field: self.identity[field] + 1}
                with self.assertRaisesRegex(runner.AuditError, "recorded credentials and exec version"):
                    fixture.consumer_identity_live(entry)
        self.scope._identity.side_effect = processes.DarwinObservationError("bound identity access denied")
        with self.clock(), self.assertRaisesRegex(processes.OwnershipError, "unresolved"):
            fixture.consumer_identity_live(entry)
        self.scope.proc.proc_signal_with_audittoken.assert_not_called()
        self.scope.system.task_name_for_pid.assert_not_called()


class ExecutorFixtureTests(unittest.TestCase):
    def setUp(self):
        global CASE_EVIDENCE
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit audit fixture ")
        # On an unexpected ownership/archive failure leave the private fixture for
        # inspection; only explicit successful cleanup may delete its generated data.
        self.temporary._finalizer.detach()
        self.addCleanup(self._cleanup_fixture)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "source Ω with spaces"
        self.root.mkdir()
        self.state = self.base / "state"
        self.sentinel_scopes = []
        self.fixture_retention_errors = []
        self.fixture_archivists = []
        if EVIDENCE_ROOT is not None:
            case = EVIDENCE_ROOT / self._testMethodName
            case.mkdir(mode=0o700)
            CASE_EVIDENCE = case
            (case / "case.json").write_text(json.dumps({"source": str(self.root), "state": str(self.state)}) + "\n")
        (self.root / ".gitignore").write_text("build/\n!**/src/**/build/\nsamples/iosApp/p2pkit-sample.xcodeproj/\n",
                                               encoding="utf-8")
        (self.root / "source.txt").write_text("original source\n", encoding="utf-8")
        (self.root / "fixture.py").write_text(FIXTURE, encoding="utf-8")
        (self.root / "gradlew").write_text('#!/bin/sh\nexec "' + PYTHON + '" "$(dirname "$0")/fixture.py" "$@"\n',
                                           encoding="utf-8")
        (self.root / "gradlew").chmod(0o755)
        (self.root / "gradlew.bat").write_text('@echo off\r\n"' + PYTHON + '" "%~dp0fixture.py" %*\r\nexit /b %errorlevel%\r\n',
                                               encoding="utf-8")
        source_build = self.root / "buildSrc/src/main/java/dev/p2pkit/build"
        source_build.mkdir(parents=True)
        (source_build / "Source.java").write_text("// source, never disposable\n", encoding="utf-8")
        for command in (["init", "-q"], ["config", "user.email", "fixture@example.invalid"],
                        ["config", "user.name", "Audit Fixture"], ["config", "core.autocrlf", "false"],
                        ["add", "."], ["commit", "-qm", "Fixture baseline"]):
            self.git(*command)
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        self.env = dict(os.environ)
        # Resource variables are not consumed by the fake wrapper; parent ownership
        # markers/domains are never stripped when switching this explicit fixture.
        for key in ("P2PKIT_GRADLE_EXECUTOR", "JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS",
                    "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            self.env.pop(key, None)
        result = subprocess.run([PYTHON, str(EXECUTOR), "init", "--root", str(self.root), "--state", str(self.state),
                                 "--expected-commit", self.commit, "--host", processes.host_role()], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        if CASE_EVIDENCE is not None:
            (CASE_EVIDENCE / "init.stdout.log").write_bytes(result.stdout)
            (CASE_EVIDENCE / "init.stderr.log").write_bytes(result.stderr)
            (CASE_EVIDENCE / "init.json").write_text(json.dumps({"expectedCommit": self.commit,
                "exitCode": result.returncode, "source": str(self.root), "state": str(self.state)}) + "\n")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.context = json.loads((self.state / "context.json").read_text())
        self.guard_id = uuid.uuid4().hex
        self.scope = processes.make_scope(self.context["id"], self.guard_id, str(self.state), self.context["gradleHome"])
        self.env = processes.ownership_environment(self.env, self.context["id"], self.guard_id,
                                                  str(self.state), self.context["gradleHome"], allow_new_context=True)
        self.wrapper = self.root / ("gradlew.bat" if os.name == "nt" else "gradlew")

    def _cleanup_fixture(self):
        errors = list(getattr(self, "fixture_retention_errors", []))
        fatal = []
        record = {"schema": 1, "kind": "executor-fixture-cleanup", "id": uuid.uuid4().hex,
                  "startedUtc": runner.utc(), "fixtureBase": str(getattr(self, "base", "")),
                  "state": str(getattr(self, "state", "")), "guardSurvivors": None, "sentinels": [],
                  "errors": errors, "archive": [], "dependentArchives": [],
                  "fixtureDataRemoved": False, "cleanupComplete": False}

        def attempt(label, action):
            try:
                return action()
            except BaseException as error:
                errors.append(f"{label}: {type(error).__name__}: {error}")
                if not isinstance(error, Exception):
                    fatal.append(error)
                return None

        if hasattr(self, "scope"):
            record["guardSurvivors"] = attempt("Fixture guard drain", lambda: self.scope.drain(grace=.5, kill_wait=5))
            if record["guardSurvivors"] is None:
                errors.append("Fixture guard worker retirement is unproven; retain the generated fixture")
            if record["guardSurvivors"]:
                errors.append(f"Fixture-owned survivors: {record['guardSurvivors']}")
            discovery = attempt("Fixture guard discovery status", lambda: sorted(self.scope.discovery_errors))
            if discovery:
                errors.append(f"Fixture ownership uncertainty: {discovery}")
            attempt("Fixture guard close", self.scope.close)
        else:
            errors.append("Fixture ownership guard was not established; retain the unadmitted generated fixture")
        for number, (sentinel_scope, capture) in enumerate(getattr(self, "sentinel_scopes", [])):
            survivors = attempt(f"Fixture sentinel {number} drain", lambda: sentinel_scope.drain(grace=.2, kill_wait=5))
            record["sentinels"].append({"index": number, "survivors": survivors})
            if survivors is None:
                errors.append(f"Separately-owned sentinel {number} retirement is unproven")
            if survivors:
                errors.append(f"Separately-owned sentinel {number} survived teardown")
            attempt(f"Fixture sentinel {number} capture", lambda: capture.finish(sentinel_scope, timeout=5))
            attempt(f"Fixture sentinel {number} close", sentinel_scope.close)
        for number, archivist in enumerate(getattr(self, "fixture_archivists", [])):
            retained = attempt(f"Dependent fixture evidence {number}", archivist)
            if retained is not None:
                record["dependentArchives"].append(retained)

        # Teardown is not allowed to short-circuit evidence retention. Give each
        # attempt a fresh directory: an injected/real failure and later recovery
        # must not overwrite one another's records or authentic invocation logs.
        destination = None
        if EVIDENCE_ROOT is not None:
            candidate = EVIDENCE_ROOT / self._testMethodName / f"teardown-{record['id']}"
            def create_destination():
                runner.reject_symlinks(candidate)
                candidate.mkdir(parents=True, mode=0o700)
                return candidate
            destination = attempt("Fixture archive directory creation", create_destination)
        else:
            errors.append("Fixture evidence root is unavailable; preserve all generated fixture data")
        if destination is not None:
            record["archiveDirectory"] = str(destination)
            budget = {"entries": 0, "bytes": 0}
            if hasattr(self, "state"):
                evidence = self.state / "evidence"
                def retain_invocations():
                    exists = runner.existing_lstat(evidence) is not None
                    runner.require(exists or not hasattr(self, "context"), "Initialized fixture evidence root is missing")
                    if exists:
                        record["archive"].extend(archive_fixture_tree(evidence, destination / "invocations", errors, budget))
                attempt("Fixture invocation evidence retention", retain_invocations)
                for name in ("context.json", "fixture-calls.jsonl"):
                    def retain_file(name=name):
                        source = self.state / name
                        exists = runner.existing_lstat(source) is not None
                        runner.require(exists or name != "context.json" or not hasattr(self, "context"),
                                       "Initialized fixture context is missing")
                        if exists:
                            record["archive"].append(archive_fixture_file(source, destination / name, budget))
                    attempt(f"Fixture {name} retention", retain_file)
            if hasattr(self, "scope"):
                description = attempt("Fixture guard description", self.scope.description)
                if description is not None:
                    attempt("Fixture guard evidence write", lambda: runner.write_new_json(destination / "guard.json", description))
            attempt("Fixture pre-disposal evidence write",
                    lambda: runner.write_new_json(destination / "cleanup-before-disposal.json", record))
        if hasattr(self, "temporary") and not errors:
            def dispose():
                self.temporary.cleanup()
                runner.require(runner.existing_lstat(self.base) is None, "Generated fixture directory still exists")
                record["fixtureDataRemoved"] = True
            attempt("Generated fixture disposal", dispose)
        record["endedUtc"] = runner.utc()
        record["cleanupComplete"] = not errors and record["fixtureDataRemoved"]
        if destination is not None:
            before_final_write = len(errors)
            attempt("Fixture final cleanup evidence write", lambda: runner.write_new_json(destination / "cleanup.json", record))
            if len(errors) != before_final_write:
                record["cleanupComplete"] = False
        if errors:
            record["cleanupComplete"] = False
            if hasattr(self, "base") and not record["fixtureDataRemoved"]:
                # Also preserve the unresolved path if upload storage is unavailable.
                attempt("Unresolved fixture path/error record", lambda: runner.write_new_json(
                    self.base / f"unresolved-fixture-cleanup-{record['id']}.json", record))
            if destination is not None:
                # A failed final write must not leave a partial/previous complete
                # JSON as the only outcome. The raised test failure is authoritative
                # even if storage also prevents this supplemental failure journal.
                attempt("Fixture cleanup failure journal", lambda: runner.write_new_json(
                    destination / "cleanup-failure.json", record))
        if fatal:
            raise fatal[0]
        if errors:
            self.fail("; ".join(errors))

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.root), *arguments], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return result.stdout

    def start(self, arguments, *, kind="gradle", env=None, timeout=20, stop_timeout=5, receipt=None, invocation=None):
        receipt = receipt or self.state / f"optional-{uuid.uuid4().hex}.json"
        command = [PYTHON, str(EXECUTOR), "--cwd", str(self.root), "--wrapper", str(self.wrapper),
                   "--purpose", "executor-fixture", "--kind", kind, "--timeout", str(timeout),
                   "--stop-timeout", str(stop_timeout), "--receipt", str(receipt), "--", *arguments]
        if invocation:
            command[2:2] = ["--id", invocation]
        child = self.scope.spawn(command, str(self.root), self.env if env is None else env)
        return Capture(child), receipt

    def run_leaf(self, arguments, **options):
        capture, path = self.start(arguments, **options)
        code, out, err = capture.finish(self.scope)
        document = json.loads(path.read_text()) if path.exists() and path.stat().st_size else None
        return code, out, err, document

    def calls(self):
        path = self.state / "fixture-calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def ready(self, path):
        deadline = time.monotonic() + 15
        while not path.exists():
            self.scope.discover()
            self.assertLess(time.monotonic(), deadline, "Real fixture child did not establish readiness")
            time.sleep(.05)

    def sentinel(self):
        identifier = uuid.uuid4().hex
        # Sibling of this fixture guard, not its descendant: the leaf must not stop
        # it, but the real outer controller's domains remain intact for cancellation.
        environment = processes.ownership_environment(dict(os.environ), self.context["id"], identifier,
            str(self.state), self.context["gradleHome"], allow_new_context=True)
        scope = processes.make_scope(self.context["id"], identifier, str(self.state), self.context["gradleHome"])
        child = scope.spawn([PYTHON, "-c", "import time; time.sleep(120)"], str(self.root), environment)
        self.sentinel_scopes.append((scope, Capture(child)))
        return child

    def test_success_has_unchanged_stdout_stderr_and_same_home_stop(self):
        code, out, err, receipt = self.run_leaf(["success"])
        self.assertEqual((code, out, err), (0, b"PRODUCT-STDOUT\n", b"PRODUCT-STDERR\n"))
        self.assertEqual(receipt["requestedArgv"], ["success"])
        self.assertEqual([receipt[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
        self.assertTrue(receipt["sourceUnchanged"])
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(receipt["ownedSurvivors"], [])
        launches = receipt["ownership"]["launches"]
        self.assertEqual(len(launches), 2)
        self.assertEqual(receipt["productLaunchIndex"], 0)
        self.assertEqual(receipt["stopLaunchIndex"], 1)
        self.assertEqual(launches[0]["requestedArgv"], receipt["executedArgv"])
        self.assertEqual(launches[1]["requestedArgv"], receipt["stopArgv"])
        self.assertEqual(launches[0]["pid"], receipt["productPid"])
        self.assertTrue(all(item["created"] and item["cwd"] == str(self.root) for item in launches))
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertIn("--stop", calls[1]["argv"])
        self.assertEqual({call["home"] for call in calls}, {self.context["gradleHome"]})
        self.assertTrue(all(self.guard_id in call["chain"].split(":") for call in calls))
        directory = Path(receipt["evidenceDirectory"])
        self.assertEqual((directory / "stop.stdout.log").read_bytes(), b"STOP-ONLY-STDOUT\n")
        self.assertEqual((directory / "stop.stderr.log").read_bytes(), b"STOP-ONLY-STDERR\n")

    def test_product_failure_is_distinct_from_infrastructure(self):
        code, _, _, receipt = self.run_leaf(["failure"])
        self.assertEqual(code, 7)
        self.assertEqual(receipt["productExitCode"], 7)
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["errors"], [])

    def test_stop_nonzero_never_becomes_expected_red_success(self):
        code, _, _, receipt = self.run_leaf(["failure"], env={**self.env, "FIXTURE_STOP_EXIT": "9"})
        self.assertEqual(code, 125)
        self.assertEqual(receipt["productExitCode"], 7)
        self.assertEqual(receipt["stopExitCode"], 9)
        self.assertTrue(receipt["errors"])

    def test_stop_timeout_is_infrastructure_and_drains_workers(self):
        code, _, _, receipt = self.run_leaf(["success"], env={**self.env, "FIXTURE_STOP_HANG": "yes"}, stop_timeout=.2)
        self.assertEqual(code, 125)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertTrue(any("stop timed out" in error for error in receipt["errors"]))

    def test_product_timeout_attempts_stop_and_is_infrastructure(self):
        code, _, _, receipt = self.run_leaf(["timeout"], timeout=.2)
        self.assertEqual(code, 125)
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertTrue(any("timed out" in error for error in receipt["errors"]))
        self.assertEqual(receipt["ownedSurvivors"], [])

    def test_source_mutation_is_retained_not_reset(self):
        code, _, _, receipt = self.run_leaf(["mutation"])
        self.assertEqual(code, 125)
        self.assertFalse(receipt["sourceUnchanged"])
        self.assertEqual((self.root / "source.txt").read_text(), "mutated source\n")
        self.assertEqual(receipt["stopExitCode"], 0)

    def test_exact_raw_argv_handles_spaces_unicode_empty_and_maven_path(self):
        arguments = ["argv", "two words", "Ω", "", "tail\\", "-Dmaven.repo.local=" + str(self.state / "isolated repository")]
        code, out, _, receipt = self.run_leaf(arguments)
        self.assertEqual(code, 0)
        self.assertEqual(receipt["requestedArgv"], arguments)
        self.assertEqual(json.loads(out)[:len(arguments)], arguments)

    def test_existing_optional_receipt_is_not_overwritten(self):
        path = self.state / "existing.json"
        path.write_text("keep these original bytes\n")
        capture, _ = self.start(["success"], receipt=path)
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        self.assertEqual(path.read_text(), "keep these original bytes\n")
        self.assertEqual(self.calls(), [])

    def test_missing_optional_parent_prevents_product_execution(self):
        capture, _ = self.start(["success"], receipt=self.state / "missing-parent" / "receipt.json")
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        self.assertEqual(self.calls(), [])

    def test_wrong_home_prevents_product_or_unrelated_stop(self):
        path = self.state / "wrong-home.json"
        arguments = [str(EXECUTOR), "--cwd", str(self.root), "--wrapper", str(self.wrapper), "--purpose", "wrong-home",
                     "--receipt", str(path), "--", "success"]
        # Mutate the input inside our already-owned controller. Do not forge a
        # contradictory OS ownership domain just to construct an admission control.
        bootstrap = ("import os,runpy,sys; sys.dont_write_bytecode=True; "
                     "sys.path.insert(0,sys.argv[1]); os.environ['GRADLE_USER_HOME']=sys.argv[2]; "
                     "sys.argv=sys.argv[3:]; runpy.run_path(sys.argv[0],run_name='__main__')")
        capture = Capture(self.scope.spawn([PYTHON, "-c", bootstrap, str(SCRIPTS), str(self.base / "shared"), *arguments],
                                           str(self.root), self.env))
        code, _, _ = capture.finish(self.scope)
        receipt = json.loads(path.read_text())
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["productExitCode"])
        self.assertIsNone(receipt["stopExitCode"])
        self.assertEqual(self.calls(), [])

    def test_property_alias_admission_refusal_never_launches_product_or_stop(self):
        foreign = self.state / "must-not-create-foreign-home"
        for spelling in property_spellings("gradle.user.home=" + str(foreign)):
            with self.subTest(spelling=spelling):
                requested = ["success", *spelling]
                code, _, _, receipt = self.run_leaf(requested)
                self.assertEqual(code, 125)
                self.assertEqual(receipt["requestedArgv"], requested)
                self.assertIsNone(receipt["productExitCode"])
                self.assertIsNone(receipt["stopExitCode"])
                self.assertEqual(self.calls(), [])
                self.assertFalse(foreign.exists())

    def test_cleanup_failures_still_archive_authentic_receipts_and_preserve_unresolved_fixture(self):
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 0)
        sentinel = self.sentinel()
        sentinel_scope, capture = self.sentinel_scopes[-1]
        case = EVIDENCE_ROOT / self._testMethodName
        previous = set(case.glob("teardown-*"))
        with mock.patch.object(self.scope, "drain", side_effect=PermissionError("injected guard drain error")), \
                mock.patch.object(self.scope, "close", side_effect=OSError("injected guard close error")), \
                mock.patch.object(sentinel_scope, "drain", side_effect=PermissionError("injected sentinel drain error")), \
                mock.patch.object(capture, "finish", side_effect=OSError("injected sentinel capture error")), \
                mock.patch.object(sentinel_scope, "close", side_effect=OSError("injected sentinel close error")):
            with self.assertRaisesRegex(AssertionError, "Fixture guard drain"):
                self._cleanup_fixture()
        attempts = set(case.glob("teardown-*")) - previous
        self.assertEqual(len(attempts), 1)
        destination = attempts.pop()
        record = json.loads((destination / "cleanup.json").read_text())
        self.assertFalse(record["cleanupComplete"])
        self.assertFalse(record["fixtureDataRemoved"])
        self.assertIsNone(record["guardSurvivors"])
        self.assertIsNone(record["sentinels"][0]["survivors"])
        for stage in ("guard drain", "guard close", "sentinel 0 drain", "sentinel 0 capture", "sentinel 0 close"):
            self.assertTrue(any(stage in error for error in record["errors"]), stage)
        self.assertTrue(self.base.is_dir())
        self.assertTrue((self.base / f"unresolved-fixture-cleanup-{record['id']}.json").is_file())
        original = Path(receipt["evidenceDirectory"])
        retained = destination / "invocations" / original.name
        for name in ("start.json", "receipt.json", "product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.assertEqual((retained / name).read_bytes(), (original / name).read_bytes(), name)
        self.assertIsNone(sentinel.poll())
        # unittest's already-registered normal cleanup now performs the real
        # identity-scoped drain and a separately recorded recovery attempt.
        # The injected failure and its authentic evidence are never overwritten.

    def test_wrong_source_prevents_product_or_stop(self):
        (self.root / "source.txt").write_text("user changes\n")
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["stopExitCode"])
        self.assertEqual(self.calls(), [])
        self.assertEqual((self.root / "source.txt").read_text(), "user changes\n")

    def test_home_policy_tampering_is_not_silently_rewritten(self):
        path = Path(self.context["gradleHome"]) / "gradle.properties"
        path.write_text(path.read_text() + "org.gradle.parallel=true\n")
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 125)
        self.assertIsNone(receipt)
        self.assertEqual(self.calls(), [])
        self.assertTrue(path.read_text().endswith("org.gradle.parallel=true\n"))

    def test_overlapping_leaf_is_refused_without_stopping_first(self):
        first, first_receipt = self.start(["hold"])
        self.ready(self.state / "product-ready")
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["stopExitCode"])
        self.assertFalse(any("--stop" in call["argv"] for call in self.calls()))
        self.assertIsNone(first.child.poll())
        (self.state / "release-product").write_text("release\n")
        self.assertEqual(first.finish(self.scope)[0], 0)
        self.assertEqual(json.loads(first_receipt.read_text())["stopExitCode"], 0)

    def test_outer_command_nested_leaf_has_no_lease_deadlock(self):
        inner_receipt = self.state / "nested.json"
        inner = [PYTHON, str(EXECUTOR), "--cwd", str(self.root), "--wrapper", str(self.wrapper),
                 "--purpose", "nested-leaf", "--receipt", str(inner_receipt), "--", "success"]
        code, out, err, receipt = self.run_leaf(inner, kind="command")
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(out, b"PRODUCT-STDOUT\n")
        self.assertEqual(json.loads(inner_receipt.read_text())["finalExitCode"], 0)
        self.assertEqual(receipt["requestedArgv"], inner)
        calls = self.calls()
        self.assertEqual(len([call for call in calls if "--stop" in call["argv"]]), 2)
        chains = [call["chain"].split(":") for call in calls]
        self.assertEqual(len(chains[0]), len(self.env[processes.CHAIN_ENV].split(":")) + 2)
        self.assertEqual(len(chains[-1]), len(self.env[processes.CHAIN_ENV].split(":")) + 1)

    def test_leader_exited_detached_term_resistant_worker_dies_sentinel_survives(self):
        sentinel = self.sentinel()
        code, _, err, receipt = self.run_leaf(["escape"])
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(receipt["ownedSurvivors"], [])
        worker_pid = json.loads((self.state / "escaped-worker.json").read_text())["pid"]
        self.assertIn(worker_pid, {item["pid"] for item in receipt["ownership"]["startedIdentities"]})
        self.assertNotIn(worker_pid, {item["pid"] for item in self.scope.discover()})
        self.assertIsNone(sentinel.poll())

    def test_explicit_foreign_fixture_context_detached_worker_remains_parent_owned(self):
        sentinel = self.sentinel()
        foreign_state = self.state / "foreign-fixture"
        foreign_state.mkdir()
        ready = foreign_state / "worker.json"
        foreign_job, foreign_leaf = uuid.uuid4().hex, uuid.uuid4().hex
        control = r'''import json, os, pathlib, subprocess, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import audit_processes as p
state, job, leaf, ready = sys.argv[2:]
home = str(pathlib.Path(state, 'gradle-home'))
scope = p.make_scope(job, leaf, state, home)
env = p.ownership_environment(dict(os.environ), job, leaf, state, home, allow_new_context=True)
worker = "import json,os,pathlib,signal,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid()})); time.sleep(120)"
producer = "import os,subprocess,sys; options={'creationflags':0x208} if os.name=='nt' else {'start_new_session':True}; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**options)"
scope.spawn([sys.executable, '-c', producer, worker, ready], os.getcwd(), env)
while True:
    scope.discover()
    time.sleep(.05)
'''
        capture = Capture(self.scope.spawn([PYTHON, "-c", control, str(SCRIPTS), str(foreign_state), foreign_job,
                                             foreign_leaf, str(ready)], str(self.root), self.env))
        self.ready(ready)
        worker_pid = json.loads(ready.read_text())["pid"]
        deadline = time.monotonic() + 5
        while worker_pid not in {row["pid"] for row in self.scope.discover()}:
            self.assertLess(time.monotonic(), deadline, "Parent lost ownership across explicit fixture context")
            time.sleep(.05)
        self.assertEqual(self.scope.drain(grace=.3, kill_wait=5), [])
        capture.finish(self.scope)
        self.assertIsNone(sentinel.poll())
        if EVIDENCE_ROOT is not None:
            (EVIDENCE_ROOT / self._testMethodName / "cross-context-proof.json").write_text(json.dumps({
                "parentJob": self.context["id"], "parentInvocation": self.guard_id, "foreignJob": foreign_job,
                "foreignInvocation": foreign_leaf, "workerPid": worker_pid, "unrelatedSentinelSurvived": True}) + "\n")

    def test_changed_report_is_retained_but_identical_xml_is_not_called_fresh(self):
        first = self.run_leaf(["report"])
        self.assertEqual(first[0], 0)
        rows = first[3]["reports"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["classification"], "changed-since-admission")
        retained = Path(first[3]["evidenceDirectory"]) / rows[0]["retained"]
        self.assertTrue(retained.is_file())
        second = self.run_leaf(["report"])
        self.assertEqual(second[0], 0)
        self.assertEqual(second[3]["reports"][0]["classification"], "preexisting-unchanged")
        self.assertNotIn("retained", second[3]["reports"][0])

    def test_external_owned_project_reports_are_retained_before_caller_cleanup(self):
        fixture = self.state / "work/consumer/consumer"
        fixture.mkdir(parents=True)
        code, _, _, receipt = self.run_leaf(["project-report", "-p", str(fixture)])
        self.assertEqual(code, 0)
        rows = receipt["reports"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["source"].startswith("external/work/consumer/consumer/build/test-results/"))
        retained = Path(receipt["evidenceDirectory"]) / rows[0]["retained"]
        self.assertEqual(retained.read_bytes(), (fixture / "build/test-results/fixture/result.xml").read_bytes())

    def cleanup_command(self, path):
        capture = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "cleanup", "--state", str(self.state),
                                             "--path", str(path)], str(self.root), self.env))
        return capture.finish(self.scope)

    def test_cleanup_exact_output_only_preserves_source_and_evidence(self):
        code, _, _, receipt = self.run_leaf(["report"])
        self.assertEqual(code, 0)
        self.assertEqual(self.cleanup_command(self.root / "build")[0], 0)
        self.assertFalse((self.root / "build").exists())
        self.assertTrue((Path(receipt["evidenceDirectory"]) / "receipt.json").is_file())
        source = self.root / "buildSrc/src/main/java/dev/p2pkit/build"
        self.assertEqual(self.cleanup_command(source)[0], 125)
        self.assertTrue((source / "Source.java").is_file())

    def test_cleanup_tracked_output_rejects_without_deleting_any_source(self):
        directory = self.root / "build"
        directory.mkdir()
        (directory / "user-source.txt").write_text("preserve\n")
        self.git("add", "-f", "build/user-source.txt")
        self.assertEqual(self.cleanup_command(directory)[0], 125)
        self.assertEqual((directory / "user-source.txt").read_text(), "preserve\n")

    def test_cleanup_preflights_all_targets_before_removing_any_output(self):
        first, second = self.root / "build", self.state / "fixtures"
        child = second / "nested"
        first.mkdir()
        child.mkdir(parents=True)
        (first / "keep.txt").write_bytes(b"first output must survive rejected preflight\n")
        (child / "keep.txt").write_bytes(b"second output must survive rejected preflight\n")
        context_bytes = (self.state / "context.json").read_bytes()
        real_lstat = Path.lstat
        observed = []

        def different_device(path, *args, **kwargs):
            actual = real_lstat(path, *args, **kwargs)
            if path == child:
                observed.append(path)
                return StatFields(actual, st_dev=actual.st_dev ^ 1)
            return actual

        # Real initialized context, source checks, leaf lock and cleanup caller;
        # only the descendant device boundary is modeled, not a native mount.
        with mock.patch.object(Path, "lstat", new=different_device):
            with self.assertRaisesRegex(runner.AuditError, "Cross-device descendant directory"):
                runner.cleanup(argparse.Namespace(state=str(self.state), path=[str(first), str(second)]))
        self.assertTrue(observed)
        self.assertEqual((first / "keep.txt").read_bytes(), b"first output must survive rejected preflight\n")
        self.assertEqual((child / "keep.txt").read_bytes(), b"second output must survive rejected preflight\n")
        self.assertEqual(list((self.state / "evidence").glob("cleanup-*.json")), [])
        self.assertEqual((self.state / "context.json").read_bytes(), context_bytes)
        self.assertEqual((self.root / "source.txt").read_text(), "original source\n")
        self.assertTrue((self.root / "buildSrc/src/main/java/dev/p2pkit/build/Source.java").is_file())

    def assert_cleanup_stops_on_original_removal_failure(self):
        first, second, third = self.root / "build", self.state / "fixtures", self.state / "xcode-deriveddata"
        for directory in (first, second, third):
            directory.mkdir()
            (directory / "keep.txt").write_bytes(b"synthetic cleanup output\n")
        failed_path = second / "keep.txt"
        original = PermissionError(errno.EACCES, "unretained exception text", "unretained filename")
        original.winerror = 5
        real_rmtree, calls, rethrown = shutil.rmtree, [], []

        def remove(path, *, onerror):
            calls.append(path)
            if path == first:
                return real_rmtree(path, onerror=onerror)
            self.assertEqual(second, path, "No retry or removal of a later root is permitted")
            try:
                raise original
            except PermissionError:
                exception = sys.exc_info()
            try:
                onerror(os.unlink, str(failed_path), exception)
            except BaseException as error:
                self.assertIs(original, error, "Diagnostics must rethrow the same removal exception")
                rethrown.append(error)
                raise
            self.fail("The removal callback suppressed its error")

        with mock.patch.object(shutil, "rmtree", side_effect=remove), mock.patch.object(os, "chmod") as chmod:
            result = runner.cleanup(argparse.Namespace(state=str(self.state),
                                                      path=[str(first), str(second), str(third)]))
        chmod.assert_not_called()
        self.assertEqual(125, result)
        self.assertEqual([first, second], calls)
        self.assertEqual([original], rethrown)
        self.assertFalse(first.exists())
        self.assertEqual(b"synthetic cleanup output\n", failed_path.read_bytes())
        self.assertEqual(b"synthetic cleanup output\n", (third / "keep.txt").read_bytes())
        self.assertEqual("original source\n", (self.root / "source.txt").read_text())
        records = [json.loads(path.read_text()) for path in (self.state / "evidence").glob("cleanup-*.json")
                   if not path.name.endswith("-start.json")]
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual([str(first), str(second), str(third)], record["paths"])
        self.assertEqual([str(first)], record["removed"])
        self.assertEqual(["Removal failed: PermissionError"], record["errors"])
        self.assertEqual(1, record["failureDetail"]["failedRootIndex"])
        self.assertEqual("PermissionError", record["failureDetail"]["exceptionType"])
        self.assertLessEqual(len(runner.json_bytes(record)), runner.MAX_JSON_BYTES)
        self.assertNotIn(b"unretained", runner.json_bytes(record))
        start = json.loads((self.state / "evidence" / f"cleanup-{record['id']}-start.json").read_text())
        self.assertEqual([], start["removed"])
        self.assertEqual(3, len(start["inspections"]))
        return record["failureDetail"]

    def test_cleanup_failure_keeps_partial_removal_and_original_error_without_remediation(self):
        detail = self.assert_cleanup_stops_on_original_removal_failure()
        self.assertEqual(str(self.state / "fixtures"), detail["failedRoot"])
        self.assertEqual(("unlink", "keep.txt", errno.EACCES, 5),
                         (detail["operation"], detail["relativePath"], detail["errno"], detail["winerror"]))
        self.assertEqual("OBSERVED", detail["metadataObservation"]["status"])

    def test_cleanup_diagnostic_failure_cannot_erase_original_removal_failure(self):
        with mock.patch.object(runner, "removal_failure_detail", side_effect=RuntimeError("diagnostic unavailable")):
            detail = self.assert_cleanup_stops_on_original_removal_failure()
        self.assertEqual("UNAVAILABLE", detail["metadataObservation"]["status"])
        self.assertEqual("UNAVAILABLE", detail["relativePath"])

    def test_modeled_readonly_retry_failure_keeps_original_error_and_does_not_advance_roots(self):
        directory, later = self.root / "build", self.state / "fixtures"
        directory.mkdir()
        later.mkdir()
        leaf = directory / "launcher.exe"
        leaf.write_bytes(b"synthetic readonly launcher")
        (later / "keep.txt").write_bytes(b"later output sentinel")
        original = PermissionError(errno.EACCES, "original private message")
        original.winerror = 5
        retry_error = PermissionError(errno.EACCES, "retry private message")
        retry_error.winerror = 5
        attrs, removals, retries = [0x21], [], []
        real_lstat, real_unlink = Path.lstat, os.unlink

        def metadata(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            return StatFields(info, st_file_attributes=attrs[0], st_reparse_tag=0) if path == leaf else info

        def chmod(path, mode):
            self.assertEqual((leaf, stat.S_IWRITE), (path, mode))
            starts = list((self.state / "evidence").glob("cleanup-*-readonly-1-start.json"))
            self.assertEqual(1, len(starts), "Original error must be durable before changing attributes")
            self.assertEqual(5, runner.read_json(starts[0])["recovery"]["originalFailure"]["winerror"])
            attrs[0] = 0x20

        def unlink(path, *args, **kwargs):
            if Path(path) != leaf:
                return real_unlink(path, *args, **kwargs)  # Preserve actual leaf-lock release.
            retries.append(Path(path))
            raise retry_error

        def remove(path, *, onerror):
            removals.append(path)
            self.assertEqual(directory, path, "A retry failure must not remove any later root")
            try:
                raise original
            except PermissionError:
                exception = sys.exc_info()
            with self.assertRaises(PermissionError) as caught:
                onerror(os.unlink, str(leaf), exception)
            self.assertIs(original, caught.exception)
            raise caught.exception

        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(Path, "lstat", new=metadata), \
                mock.patch.object(shutil, "rmtree", side_effect=remove), \
                mock.patch.object(os, "chmod", side_effect=chmod) as change, mock.patch.object(os, "unlink", side_effect=unlink):
            code = runner.cleanup(argparse.Namespace(state=str(self.state), path=[str(directory), str(later)]))
        self.assertEqual(125, code)
        self.assertEqual([directory], removals)
        self.assertEqual([leaf], retries)
        change.assert_called_once_with(leaf, stat.S_IWRITE)
        record = self.cleanup_record(expected_errors=("Removal failed: PermissionError",))
        self.assertEqual([], record["removed"])
        self.assertEqual(["Removal failed: PermissionError"], record["errors"])
        attempt = record["readonlyRecoveries"][0]
        self.assertEqual(("FAILED", "unlink-once", "PermissionError", errno.EACCES, 5),
                         (attempt["outcome"], attempt["stage"], attempt["failureType"], attempt["errno"], attempt["winerror"]))
        self.assertEqual(0x21, attempt["originalFailure"]["metadataObservation"]["fileAttributes"])
        self.assertNotIn(b"private message", runner.json_bytes(record))
        self.assertEqual(b"synthetic readonly launcher", leaf.read_bytes())
        self.assertEqual(b"later output sentinel", (later / "keep.txt").read_bytes())
        self.assertEqual("original source\n", (self.root / "source.txt").read_text())

    def test_cleanup_only_exact_new_xcode_project_and_preserves_preexisting_project(self):
        project = self.root / "samples/iosApp/p2pkit-sample.xcodeproj"
        project.mkdir(parents=True)
        (project / "project.pbxproj").write_text("generated fixture\n")
        self.assertEqual(self.cleanup_command(project)[0], 0)
        self.assertFalse(project.exists())
        project.mkdir()
        (project / "project.pbxproj").write_text("preexisting project\n")
        second_state = self.base / "second-context"
        initialize = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "init", "--root", str(self.root), "--state",
            str(second_state), "--expected-commit", self.commit, "--host", processes.host_role()], str(self.root), self.env))
        self.assertEqual(initialize.finish(self.scope)[0], 0)
        clean = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "cleanup", "--state", str(second_state), "--path",
                                          str(project)], str(self.root), self.env))
        self.assertEqual(clean.finish(self.scope)[0], 125)
        self.assertEqual((project / "project.pbxproj").read_text(), "preexisting project\n")
        if CASE_EVIDENCE is not None:
            shutil.copy2(second_state / "context.json", CASE_EVIDENCE / "preexisting-project-context.json")

    def cleanup_record(self, expected_errors=()):
        records = [json.loads(path.read_text()) for path in (self.state / "evidence").glob("cleanup-*.json")
                   if not path.name.endswith("-start.json")]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["errors"], list(expected_errors))
        return records[0]

    def test_cleanup_unlinks_child_symlinks_without_following_external_broken_or_loop_targets(self):
        directory = self.root / "build"
        directory.mkdir()
        outside = self.base / "outside-output"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"outside-output sentinel\x00\xff\n")
        targets = {"file-link": (sentinel, False), "directory-link": (outside, True),
                   "broken-link": (outside / "absent", False), "loop-link": (directory, True)}
        try:
            for name, (target, is_directory) in targets.items():
                (directory / name).symlink_to(target, target_is_directory=is_directory)
        except OSError as error:
            self.fail(f"Native no-follow cleanup fixture requires real symlink capability: {error}")
        expected = {name: runner.digest(os.fsencode(os.readlink(directory / name))) for name in targets}
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertFalse(directory.exists())
        self.assertTrue(outside.is_dir())
        self.assertEqual(sentinel.read_bytes(), b"outside-output sentinel\x00\xff\n")
        self.assertFalse((outside / "absent").exists())
        self.assertEqual((self.root / "source.txt").read_text(), "original source\n")
        record = self.cleanup_record()
        self.assertEqual(record["removed"], [str(directory)])
        self.assertTrue((self.state / "evidence" / f"cleanup-{record['id']}-start.json").is_file())
        inspection = record["inspections"][0]
        self.assertTrue(inspection["noTargetTraversal"])
        self.assertEqual(inspection["entryCount"], len(targets))
        self.assertEqual({row["path"]: row["targetSha256"] for row in inspection["links"]}, expected)
        self.assertTrue(all(row["kind"] == "symlink" and
                            row["policy"] == "unlink-entry-only; do-not-traverse-target"
                            for row in inspection["links"]))

    def test_cleanup_root_or_ancestor_symlink_is_still_rejected(self):
        outside = self.base / "outside-root"
        outside.mkdir()
        (outside / "nested").mkdir()
        (outside / "sentinel.txt").write_bytes(b"preserve root target\n")
        link = self.root / "build"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.fail(f"Native root/ancestor rejection fixture requires real symlink capability: {error}")
        for path in (link, link / "nested"):
            code, _, err = self.cleanup_command(path)
            self.assertEqual(code, 125)
            self.assertIn(b"Symlink/reparse-point", err)
        self.assertTrue(link.is_symlink())
        self.assertEqual((outside / "sentinel.txt").read_bytes(), b"preserve root target\n")

    def test_wrong_native_host_is_rejected_at_initialization(self):
        wrong = next(host for host in runner.HOSTS if host != processes.host_role())
        capture = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "init", "--root", str(self.root), "--state",
            str(self.base / "wrong-host"), "--expected-commit", self.commit, "--host", wrong], str(self.root), self.env))
        self.assertEqual(capture.finish(self.scope)[0], 125)
        self.assertFalse((self.base / "wrong-host").exists())

    def test_cooperative_cancellation_is_real_and_attempts_same_home_stop(self):
        invocation = uuid.uuid4().hex
        capture, path = self.start(["hold"], invocation=invocation)
        self.ready(self.state / "product-ready")
        cancel = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "request-cancel", "--state", str(self.state),
                                            "--id", invocation], str(self.root), self.env))
        self.assertEqual(cancel.finish(self.scope)[0], 0)
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        receipt = json.loads(path.read_text())
        self.assertTrue(receipt["cancelRequested"])
        self.assertEqual(receipt["cancelledSignals"], [])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])


class PosixNativeTests(ExecutorFixtureTests):
    def consumer_environment(self):
        temporary = self.state / "work/consumer-temp"
        temporary.mkdir(parents=True, mode=0o700)
        environment = {**self.env, "TMPDIR": str(temporary), "TMP": str(temporary), "TEMP": str(temporary)}
        environment.setdefault("P2PKIT_AUDIT_INVOCATION", "private-native-parent-" + uuid.uuid4().hex)
        environment.setdefault("P2PKIT_AUDIT_FIXTURE_ANCESTOR", "future native fixture ancestor must survive")
        return temporary, environment

    def assert_consumer_ancestors(self, observation, environment, invocation):
        ancestors = processes.ownership_domains(environment[processes.CHAIN_ENV], environment[processes.DOMAINS_ENV])
        ancestors.append({"id": invocation, "job": self.context["id"], "state": str(self.state),
                          "home": self.context["gradleHome"]})
        actual = processes.ownership_domains(observation[processes.CHAIN_ENV] or "",
                                              observation[processes.DOMAINS_ENV] or "")
        self.assertEqual(actual[:len(ancestors)], ancestors)
        self.assertEqual(observation[processes.JOB_ENV], actual[-1]["job"])
        self.assertEqual(observation[processes.STATE_ENV], actual[-1]["state"])
        self.assertEqual(observation["GRADLE_USER_HOME"], actual[-1]["home"])
        for name in ("P2PKIT_AUDIT_INVOCATION", "P2PKIT_AUDIT_FIXTURE_ANCESTOR"):
            self.assertEqual(observation[name], environment[name])

    def consumer_token_signal(self, entry, signum):
        # Use the independently acquired kernel capability, never a PID signal or
        # a process-name sweep. No reacquisition from a possibly reused PID occurs.
        if isinstance(self.scope, processes.LinuxScope):
            signal.pidfd_send_signal(entry["handle"], signum)
        elif isinstance(self.scope, processes.DarwinScope):
            result = self.scope.proc.proc_signal_with_audittoken(ctypes.byref(entry["handle"]), signum)
            if result == errno.ESRCH:
                raise ProcessLookupError(entry["identity"]["pid"])
            if result != 0:
                raise processes.OwnershipError(f"Fixture identity-scoped signal failed: errno {result}")
        else:
            raise processes.OwnershipError("Consumer cancellation requires the actual POSIX native backend")

    def consumer_identity_live(self, entry):
        previous = entry["identity"]
        if isinstance(self.scope, processes.DarwinScope):
            # proc_signal_with_audittoken does not support signal zero. Observe
            # the original lifetime instead; actual termination still uses the
            # stored opaque token, never a PID or newly acquired capability.
            try:
                current = self.scope._observe(previous, "consumer fixture identity", lambda identity: identity)
            except ProcessLookupError:
                return False
            runner.require(all(current[field] == previous[field] for field in ("uid", "realUid", "pidVersion")),
                           "Live consumer identity differs from its recorded credentials and exec version")
            return True
        current = self.scope._identity(previous["pid"])
        same = current is not None and self.scope._key(current) == self.scope._key(previous)
        try:
            self.consumer_token_signal(entry, 0)
        except ProcessLookupError:
            # The process may have exited between our identity read and token
            # probe. Reinspect before calling a still-live same-key identity an
            # expired-token fault.
            current = self.scope._identity(previous["pid"])
            same = current is not None and self.scope._key(current) == self.scope._key(previous)
            runner.require(not (same and current["live"]),
                           "Recorded consumer token expired while the same process remains live")
            return False
        runner.require(same and current["uid"] == previous["uid"],
                       "Live consumer token cannot be reconciled with its recorded same-UID identity")
        return current["live"]

    def consumer_obligation_record(self, obligation):
        capture = obligation.get("capture")
        return {key: obligation[key] for key in ("id", "invocation", "producerEvidence", "fixtureBase", "pending", "recoveryOf",
                "bindingComplete", "observedAncestry", "verifiedAncestry", "bindingErrors", "retentionReasons")} | {
            "controllerPid": capture.child.pid if capture is not None else None,
            "controller": obligation.get("controller"), "product": obligation.get("product"),
            "ready": obligation.get("ready"), "readySha256": obligation.get("readySha256"),
            "producerPid": obligation.get("producerPid"), "producerSha256": obligation.get("producerSha256"),
            "acquiredIdentities": [{"identity": entry["identity"], "released": entry["released"]}
                                   for entry in obligation["entries"]],
        }

    def consumer_obligation_event(self, obligation, event, **fields):
        path = CASE_EVIDENCE / f"consumer-cancellation-{obligation['id']}-{event}-{uuid.uuid4().hex}.json"
        runner.write_new_json(path, {"schema": 1, "kind": event, "utc": runner.utc(),
                                     "obligation": self.consumer_obligation_record(obligation), **fields})
        return path

    def consumer_retention_error(self, obligation, label, error):
        message = f"Consumer cancellation {obligation['id']} {label}: {type(error).__name__}: {error}"
        obligation["retentionReasons"].append(message)
        self.fixture_retention_errors.append(message)
        return message

    def begin_consumer_cancellation_obligation(self, invocation, evidence, *, recovery_of=None):
        identifier = uuid.uuid4().hex
        pending = f"Consumer cancellation {identifier}: whole-chain retirement remains unproven; preserve fixture data"
        obligation = {"id": identifier, "invocation": invocation, "producerEvidence": str(evidence),
                      "fixtureBase": str(self.base), "pending": True, "bindingComplete": False,
                      "observedAncestry": [], "verifiedAncestry": [], "entries": [], "bindingErrors": [],
                      "retentionReasons": [pending], "retirementProof": None, "recoveryOf": recovery_of}
        # Establish both in-memory retention and registered cleanup BEFORE any
        # producer launch/readiness/identity acquisition can fail. Marker-scope
        # drain alone cannot discharge this obligation for an erasure mutant.
        self.fixture_retention_errors.append(pending)
        self.addCleanup(self.cleanup_consumer_cancellation_fallback, obligation)
        try:
            self.consumer_obligation_event(obligation, "pending-recovery" if recovery_of else "pending-before-start")
        except BaseException as error:
            self.consumer_retention_error(obligation, "pending record", error)
            raise
        return obligation

    def start_consumer_cancellation_producer(self, obligation, command, environment):
        try:
            self.assertTrue(obligation["pending"])
            capture, receipt_path = self.start(command, kind="command", invocation=obligation["invocation"], env=environment)
            obligation["capture"] = capture
            evidence = Path(obligation["producerEvidence"])
            self.ready(evidence / "ready.json")
            return capture, receipt_path, runner.read_json(evidence / "ready.json"), runner.read_json(evidence / "producer-start.json")
        except BaseException as error:
            message = self.consumer_retention_error(obligation, "launch/readiness", error)
            obligation["bindingErrors"].append(message)
            try:
                self.consumer_obligation_event(obligation, "launch-or-readiness-failed")
            except BaseException as record_error:
                self.consumer_retention_error(obligation, "launch/readiness failure record", record_error)
            raise

    def bind_consumer_cancellation_fallback(self, obligation, capture, ready, producer):
        # Readiness is a locator, not signal authority. Keep the independently
        # expected WHOLE chain separate from the possibly partial handle subset.
        try:
            self.assertTrue(obligation["pending"])
            self.assertIs(obligation.get("capture"), capture)
            self.assertFalse(obligation["entries"], "A failed binding needs a separate explicit recovery proof")
            obligation["ready"] = ready
            obligation["producerPid"] = producer["pid"]
            evidence = Path(obligation["producerEvidence"])
            obligation["readySha256"] = runner.file_digest(evidence / "ready.json")
            obligation["producerSha256"] = runner.file_digest(evidence / "producer-start.json")
            controller = self.scope._identity(capture.child.pid)
            self.assertIsNone(capture.child.poll())
            self.assertIsNotNone(controller)
            self.assertTrue(controller["live"])
            self.assertEqual(controller["uid"], os.getuid())
            obligation["controller"] = controller
            product = self.scope._identity(producer["pid"])
            self.assertIsNotNone(product)
            self.assertTrue(product["live"])
            self.assertEqual(product["uid"], os.getuid())
            self.assertEqual(product["parentPid"], capture.child.pid)
            obligation["product"] = product
            identities, seen, pid = obligation["observedAncestry"], set(), ready["workerPid"]
            for _ in range(32):
                identity = self.scope._identity(pid)
                self.assertIsNotNone(identity, "Consumer cancellation ancestry disappeared before binding")
                self.assertTrue(identity["live"])
                self.assertEqual(identity["uid"], os.getuid())
                self.assertNotIn(self.scope._key(identity), seen)
                seen.add(self.scope._key(identity))
                identities.append(identity)
                if pid == producer["pid"]:
                    self.assertEqual(self.scope._key(identity), self.scope._key(product))
                    break
                pid = identity["parentPid"]
            else:
                self.fail("Consumer cancellation ancestry did not reach its actual product within 32 entries")
            self.assertEqual(identities[0]["parentPid"], ready["producerPid"])
            self.assertEqual(identities[0]["group"], ready["workerPid"], "Fixture worker did not detach its process group")
            self.assertEqual(identities[-1]["parentPid"], capture.child.pid)
            for child, parent in zip(identities, identities[1:]):
                self.assertEqual(child["parentPid"], parent["pid"])
                if "parentUniqueId" in child:
                    self.assertEqual(child["parentUniqueId"], parent["uniqueId"])
            obligation["verifiedAncestry"] = list(identities)
            for identity in identities:
                entry = {"identity": identity, "handle": self.scope._acquire(identity), "released": False}
                obligation["entries"].append(entry)
                current = self.scope._identity(identity["pid"])
                self.assertIsNotNone(current)
                self.assertEqual(self.scope._key(current), self.scope._key(identity))
                self.assertEqual(current["parentPid"], identity["parentPid"])
                self.assertEqual(current["uid"], os.getuid())
                if isinstance(self.scope, processes.DarwinScope):
                    self.assertEqual(current["pidVersion"], identity["pidVersion"],
                                     "Consumer exec version changed while acquiring its recorded token")
                self.assertTrue(self.consumer_identity_live(entry))
            self.consumer_obligation_event(obligation, "identity-binding", allChainCapabilitiesAcquired=True,
                signalAuthority=self.scope.name,
                scope="Fixture-specific ancestry proof; not a replacement for inherited native ownership.")
            obligation["bindingComplete"] = True
            return obligation["entries"]
        except BaseException as error:
            message = self.consumer_retention_error(obligation, "binding/acquisition", error)
            obligation["bindingErrors"].append(message)
            try:
                self.consumer_obligation_event(obligation, "binding-failed")
            except BaseException as record_error:
                self.consumer_retention_error(obligation, "binding failure record", record_error)
            raise

    def resolve_consumer_retention(self, obligation, proof_obligation, proof, proof_path):
        # A failure-control recovery may supply a SECOND fully bound capability
        # set. It must identify this exact capture/product/ready/source instance,
        # cover every observed/acquired stable key, and have a durable complete
        # retirement record. A marker-only drain is never recovery authority.
        self.assertTrue(obligation["pending"])
        self.assertTrue(proof_obligation["bindingComplete"])
        self.assertTrue(proof["wholeChainRetired"])
        self.assertEqual(proof["errors"], [])
        if proof_obligation is not obligation:
            self.assertFalse(proof_obligation["pending"])
            self.assertEqual(proof_obligation["recoveryOf"], obligation["id"])
            self.assertEqual(proof_obligation["retirementProof"], (proof, proof_path))
        self.assertIsNotNone(obligation.get("capture"))
        self.assertIs(obligation["capture"], proof_obligation["capture"])
        for key in ("invocation", "producerEvidence", "fixtureBase", "producerPid", "readySha256", "producerSha256"):
            self.assertEqual(obligation[key], proof_obligation[key], key)
        self.assertEqual(obligation["ready"], proof_obligation["ready"])
        expected = [self.scope._key(identity) for identity in proof_obligation["verifiedAncestry"]]
        self.assertTrue(expected)
        self.assertEqual(proof["expectedIdentityKeys"], [list(key) for key in expected])
        self.assertEqual([self.scope._key(identity) for identity in obligation["observedAncestry"]],
                         expected[:len(obligation["observedAncestry"])])
        if obligation["verifiedAncestry"]:
            self.assertEqual([self.scope._key(identity) for identity in obligation["verifiedAncestry"]], expected)
        for entry in obligation["entries"]:
            self.assertIn(self.scope._key(entry["identity"]), expected)
            self.assertTrue(entry["released"], "A recovery must not orphan an acquired capability")
        for key in ("controller", "product"):
            if obligation.get(key) is not None:
                self.assertEqual(self.scope._key(obligation[key]), self.scope._key(proof_obligation[key]))
        self.assertEqual(runner.read_json(proof_path)["cleanup"], proof)
        self.consumer_obligation_event(obligation, "retention-resolved", proofObligation=proof_obligation["id"],
            proofPath=str(proof_path), proofSha256=runner.file_digest(proof_path), wholeChainRetired=True,
            completeIdentityKeys=[list(key) for key in expected], historicalFailuresPreserved=True, retentionPendingAfter=False)
        # Remove only this obligation's exact, UUID-qualified current blockers.
        # Its error list and immutable failure journals remain historical evidence.
        owned = set(obligation["retentionReasons"])
        self.fixture_retention_errors[:] = [reason for reason in self.fixture_retention_errors if reason not in owned]
        obligation["pending"] = False
        obligation["retirementProof"] = (proof, proof_path)

    def cleanup_consumer_cancellation_fallback(self, obligation):
        if not obligation["pending"]:
            return
        entries = [entry for entry in obligation["entries"] if not entry["released"]]
        identities = obligation["verifiedAncestry"]
        expected = [self.scope._key(identity) for identity in identities]
        acquired = [self.scope._key(entry["identity"]) for entry in entries]
        complete = obligation["bindingComplete"] and bool(expected) and acquired == expected
        errors, fatal = [], []
        record = {"schema": 1, "kind": "consumer-identity-fallback-cleanup", "controller": obligation.get("controller"),
                  "verifiedAncestry": identities, "expectedIdentityKeys": [list(key) for key in expected],
                  "wholeChainCovered": complete, "wholeChainRetired": False, "retirementProven": False,
                  "unobservedAncestry": not bool(identities),
                  "unacquiredIdentities": [identity for identity in identities if self.scope._key(identity) not in acquired],
                  "bindingErrors": list(obligation["bindingErrors"]), "backend": self.scope.name, "fallbackUsed": False,
                  "signalledIdentities": [], "remainingAcquiredIdentities": None,
                  "acquiredSubsetRetired": None, "errors": errors,
                  "scope": "Any fallback use FAILS the native ownership test; it never converts the mutant into approval."}

        def attempt(label, action):
            try:
                return action()
            except BaseException as error:
                errors.append(f"{label}: {type(error).__name__}: {error}")
                if not isinstance(error, Exception):
                    fatal.append(error)
                return None

        def remaining():
            live = []
            for entry in entries:
                observation = attempt("Recorded consumer identity observation", lambda: self.consumer_identity_live(entry))
                if observation is None or observation:
                    live.append(entry)
            return live

        live = remaining()
        record["liveBeforeFallback"] = [entry["identity"] for entry in live]
        for entry in live:
            # An uncertain observation never authorizes a signal. A positive
            # recheck is mandatory immediately before using the bound capability.
            if attempt("Consumer pre-signal identity recheck", lambda: self.consumer_identity_live(entry)) is True:
                record["fallbackUsed"] = True
                record["signalledIdentities"].append(entry["identity"])
                def terminate():
                    try:
                        self.consumer_token_signal(entry, processes.SIG_KILL)
                    except ProcessLookupError:
                        pass
                attempt("Recorded consumer identity SIGKILL", terminate)
        deadline = time.monotonic() + 5
        while live and time.monotonic() < deadline:
            time.sleep(.05)
            live = remaining()
        record["remainingAcquiredIdentities"] = [entry["identity"] for entry in live]
        record["acquiredSubsetRetired"] = not errors and not live if entries else None
        if live:
            errors.append("Recorded consumer fixture retirement is unproven; preserve its generated data")
        for entry in entries:
            def release():
                self.scope._release(entry["handle"])
                entry["released"] = True
            attempt("Recorded consumer handle release", release)
        if not complete:
            errors.append("Whole-chain retirement remains unproven: binding/acquisition did not cover every expected identity")
        record["wholeChainRetired"] = complete and not errors and not live
        record["retirementProven"] = record["wholeChainRetired"]
        path = attempt("Consumer identity fallback evidence", lambda: self.consumer_obligation_event(
            obligation, "identity-cleanup", cleanup=record))
        if path is not None and record["wholeChainRetired"] and not errors:
            attempt("Consumer complete-proof retention resolution", lambda: self.resolve_consumer_retention(
                obligation, obligation, record, path))
        for error in errors:
            self.consumer_retention_error(obligation, "identity cleanup", AssertionError(error))
        if fatal:
            raise fatal[0]
        if errors or record["fallbackUsed"]:
            self.fail("Consumer native ownership required recorded exact-identity fallback cleanup; " + "; ".join(errors))

    def retain_consumer_fixture_states(self, temporary, evidence, *, expect_native=False):
        # Invoked after the fixture's actual ownership drain, including assertion
        # failures. Child native evidence is outside the outer state/evidence, so
        # it must move there before automatic TMPDIR disposal can be permitted.
        created = runner.read_json(evidence / "fixture-created.json")
        base = runner.absolute_path(created["fixtureBase"])
        runner.require(base != temporary and runner.within(base, temporary), "Consumer fixture escaped owned TMPDIR")
        destination = evidence / f"dependent-state-archive-{uuid.uuid4().hex}"
        destination.mkdir(mode=0o700)
        errors, records = [], []
        budget = {"entries": 0, "bytes": 0}
        # These are the producer's two explicit fixture contexts, not a search
        # for arbitrary directories named state or build. Partial setup remains
        # inspectable if producer.json was never successfully finalized.
        for name in ("audit state with spaces", "native audit state"):
            state = base / name
            try:
                present = runner.physical_directory_present(state)
                runner.require(present or (name == "native audit state" and not expect_native),
                               "Required consumer fixture state is missing; preserve unresolved fixture data")
                if not present:
                    continue
                target = destination / name
                target.mkdir(mode=0o700)
                for relative in ("context.json", "gradle-home/gradle.properties"):
                    source = state / relative
                    present = runner.existing_lstat(source) is not None
                    runner.require(present or (relative != "context.json" and name != "native audit state"),
                                   "Required consumer fixture context/policy is missing")
                    if present:
                        records.append(archive_fixture_file(source, target / relative, budget))
                child_evidence = state / "evidence"
                present = runner.existing_lstat(child_evidence) is not None
                runner.require(present or name != "native audit state", "Required native child evidence root is missing")
                if present:
                    records.extend(archive_fixture_tree(child_evidence, target / "evidence", errors, budget))
                with os.scandir(state) as entries:
                    for count, entry in enumerate(entries, start=1):
                        runner.require(count <= runner.MAX_ARCHIVE_FILES, "Child fixture state entry count exceeds its bound")
                        if entry.name.startswith("consumer-receipts."):
                            records.extend(archive_fixture_tree(Path(entry.path), target / entry.name, errors, budget))
            except Exception as error:
                errors.append(f"Consumer child state {state}: {type(error).__name__}: {error}")
        record = {"schema": 1, "kind": "consumer-dependent-state-archive", "fixtureBase": str(base),
                  "destination": str(destination), "archive": records, "errors": errors,
                  "complete": not errors, "scope": "Authentic fixture receipts/logs; wrapper/report bytes are synthetic."}
        runner.write_new_json(destination / "archive.json", record)
        self.assertFalse(errors, "; ".join(errors))
        return record

    def test_posix_launch_trace_keeps_logical_and_resolved_executable_distinct(self):
        requested = [Path(PYTHON).name, "-c", "print('TRACE-NATIVE')"]
        environment = {**self.env, "PATH": str(Path(PYTHON).parent) + os.pathsep + self.env.get("PATH", "")}
        code, out, err, receipt = self.run_leaf(requested, kind="command", env=environment)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(out, b"TRACE-NATIVE\n")
        self.assertEqual(receipt["requestedArgv"], requested)
        self.assertEqual(receipt["executedArgv"], requested)
        launch = receipt["ownership"]["launches"][receipt["productLaunchIndex"]]
        self.assertEqual(launch["api"], "subprocess.Popen")
        self.assertEqual(launch["resolvedArgv"], [PYTHON, *requested[1:]])
        self.assertEqual(launch["executable"], PYTHON)
        self.assertFalse(launch["shell"])
        self.assertNotIn("commandLine", launch)

    def test_real_controller_cancellation_finalizes_and_preserves_sentinel(self):
        sentinel = self.sentinel()
        capture, receipt_path = self.start(["hold"])
        self.ready(self.state / "product-ready")
        identity = self.scope._identity(capture.child.pid)
        self.assertIsNotNone(identity)
        self.scope.discover()
        key = self.scope._key(identity)
        self.scope._send(identity, self.scope.handles[key], processes.SIG_TERM)
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["cancelledSignals"], [signal.SIGTERM])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertIsNone(sentinel.poll())

    def test_actual_consumer_fixture_cancellation_retires_detached_child_and_preserves_sentinel(self):
        sentinel = self.sentinel()
        temporary, environment = self.consumer_environment()
        evidence = self.state / "evidence" / f"consumer-cancellation-{uuid.uuid4().hex}"
        ready_path = evidence / "ready.json"
        producer_script = SCRIPTS / "tests/audit-consumer-test.py"
        invocation = uuid.uuid4().hex
        self.fixture_archivists.append(lambda: self.retain_consumer_fixture_states(temporary, evidence))
        command = [PYTHON, str(producer_script), "--ownership-cancellation-fixture", str(ready_path),
                   "--fixture-evidence", str(evidence)]
        obligation = self.begin_consumer_cancellation_obligation(invocation, evidence)
        capture, receipt_path, ready, producer = self.start_consumer_cancellation_producer(obligation, command, environment)
        entries = self.bind_consumer_cancellation_fallback(obligation, capture, ready, producer)

        # Cancel and wait for the authentic outer final receipt BEFORE any marker
        # preservation assertion. The original-erasure negative must still get
        # its applicable wrapper stop; cleanup then retires only bound leftovers.
        cancel = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "request-cancel", "--state", str(self.state),
                                           "--id", invocation], str(self.root), self.env))
        cancelled = cancel.finish(self.scope)
        code, _, err = capture.finish(self.scope)
        receipt = runner.read_json(receipt_path)
        self.assertEqual(cancelled[0], 0, cancelled[2].decode(errors="replace"))
        self.assertEqual(code, 125, err.decode(errors="replace"))
        self.assertTrue(receipt["cancelRequested"])
        self.assertEqual(receipt["cancelledSignals"], [])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertEqual(receipt["productPid"], producer["pid"])
        self.assertEqual(receipt["requestedArgv"], command)
        self.assertEqual(receipt["gradleHome"], self.context["gradleHome"])
        self.assertEqual(receipt["stopArgv"][0], str(self.wrapper))
        self.assertTrue(receipt["sourceUnchanged"])
        self.assertIsNone(sentinel.poll())
        self.assertEqual(ready["schema"], 1)
        self.assertEqual(ready["kind"], "consumer-ownership-cancellation-fixture")
        self.assert_consumer_ancestors(ready["ownership"], environment, invocation)
        self.assert_consumer_ancestors(producer["parentOwnership"], environment, invocation)
        binding = runner.read_json(evidence / "producer.json")
        for observation in (binding["fixtureSetupOwnership"], binding["adapterOwnership"]):
            self.assert_consumer_ancestors(observation, environment, invocation)
        started = {self.scope._key(identity) for identity in receipt["ownership"]["startedIdentities"]}
        self.assertIn(self.scope._key(entries[0]["identity"]), started)
        self.assertTrue(all(not self.consumer_identity_live(entry) for entry in entries),
                        "Authentic cancellation left a bound consumer ancestor/worker live")
        self.assertEqual(producer["producerSha256"], runner.file_digest(producer_script))
        self.assertEqual(producer["consumerScriptSha256"], runner.file_digest(SCRIPTS / "check-published-consumers.sh"))
        self.assertTrue((evidence / "calls.jsonl").is_file())
        self.assertTrue((evidence / "consumer.stdout.log").is_file())
        self.assertTrue((evidence / "consumer.stderr.log").is_file())
        directory = Path(receipt["evidenceDirectory"])
        self.assertEqual((directory / "stop.stdout.log").read_bytes(), b"STOP-ONLY-STDOUT\n")
        self.assertEqual((directory / "stop.stderr.log").read_bytes(), b"STOP-ONLY-STDERR\n")
        runner.write_new_json(CASE_EVIDENCE / "consumer-cancellation-verdict.json", {
            "schema": 1, "receipt": str(receipt_path), "receiptSha256": runner.file_digest(receipt_path),
            "retiredWorker": entries[0]["identity"], "unrelatedSentinelPid": sentinel.pid,
            "unrelatedSentinelSurvived": True, "scope": "Actual native cancellation of synthetic consumer fixture only.",
        })

    def assert_consumer_binding_failure_retains_fixture(self, *, partial_acquisition):
        original_errors = list(self.fixture_retention_errors)
        temporary, environment = self.consumer_environment()
        evidence = self.state / "evidence" / f"consumer-binding-fault-{uuid.uuid4().hex}"
        invocation = uuid.uuid4().hex
        self.fixture_archivists.append(lambda: self.retain_consumer_fixture_states(temporary, evidence))
        command = [PYTHON, str(SCRIPTS / "tests/audit-consumer-test.py"),
                   "--ownership-cancellation-fixture", str(evidence / "ready.json"), "--fixture-evidence", str(evidence)]
        primary = self.begin_consumer_cancellation_obligation(invocation, evidence)
        self.assertTrue(primary["pending"])
        self.assertTrue(set(primary["retentionReasons"]).issubset(self.fixture_retention_errors))
        self.assertFalse((evidence / "ready.json").exists(), "Retention must be established before producer startup")
        capture, receipt_path, ready, producer = self.start_consumer_cancellation_producer(primary, command, environment)
        # Deliberate failure controls use the intact real caller, NEVER the strip
        # mutant. Its real marker scope can be cancelled normally. Independently
        # acquired full-chain tokens are the later recovery authority, not that
        # marker-scope empty survivor list or the incomplete primary binding.
        self.assert_consumer_ancestors(ready["ownership"], environment, invocation)
        recovery = self.begin_consumer_cancellation_obligation(invocation, evidence, recovery_of=primary["id"])
        recovery["capture"] = capture
        recovery_entries = self.bind_consumer_cancellation_fallback(recovery, capture, ready, producer)
        self.assertGreater(len(recovery_entries), 1)
        if partial_acquisition:
            actual_acquire, attempts = self.scope._acquire, []

            def fail_second_acquire(identity):
                attempts.append(dict(identity))
                if len(attempts) == 2:
                    raise PermissionError("injected second consumer capability acquisition failure")
                return actual_acquire(identity)

            with mock.patch.object(self.scope, "_acquire", side_effect=fail_second_acquire):
                with self.assertRaisesRegex(PermissionError, "injected second consumer capability"):
                    self.bind_consumer_cancellation_fallback(primary, capture, ready, producer)
            self.assertEqual(len(attempts), 2)
            self.assertEqual(len(primary["entries"]), 1)
            self.assertGreater(len(primary["verifiedAncestry"]), len(primary["entries"]))
        else:
            with mock.patch.object(self.scope, "_identity", side_effect=PermissionError("injected consumer prebind failure")):
                with self.assertRaisesRegex(PermissionError, "injected consumer prebind"):
                    self.bind_consumer_cancellation_fallback(primary, capture, ready, producer)
            self.assertEqual(primary["entries"], [])
            self.assertEqual(primary["verifiedAncestry"], [])
        self.assertFalse(primary["bindingComplete"])
        self.assertTrue(primary["bindingErrors"])
        self.assertTrue(set(primary["bindingErrors"]).issubset(self.fixture_retention_errors))
        with self.assertRaisesRegex(AssertionError, "Whole-chain retirement remains unproven"):
            self.cleanup_consumer_cancellation_fallback(primary)
        paths = list(CASE_EVIDENCE.glob(f"consumer-cancellation-{primary['id']}-identity-cleanup-*.json"))
        self.assertEqual(len(paths), 1)
        failed = runner.read_json(paths[0])["cleanup"]
        self.assertFalse(failed["wholeChainCovered"])
        self.assertFalse(failed["wholeChainRetired"])
        self.assertFalse(failed["retirementProven"])
        self.assertEqual(failed["acquiredSubsetRetired"], True if partial_acquisition else None)
        self.assertEqual(failed["fallbackUsed"], partial_acquisition)
        self.assertEqual(len(failed["unacquiredIdentities"]),
                         len(primary["verifiedAncestry"]) - len(primary["entries"]))
        self.assertEqual(failed["unobservedAncestry"], not partial_acquisition)
        self.assertTrue(primary["pending"])
        self.assertIsNone(primary["retirementProof"])
        self.assertTrue(any(self.consumer_identity_live(entry) for entry in recovery_entries[1:]),
                        "Control did not exercise still-live unacquired ancestors")

        cancel = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "request-cancel", "--state", str(self.state),
                                           "--id", invocation], str(self.root), self.env))
        cancelled = cancel.finish(self.scope)
        code, _, err = capture.finish(self.scope)
        receipt = runner.read_json(receipt_path)
        self.assertEqual(cancelled[0], 0)
        self.assertEqual(code, 125, err.decode(errors="replace"))
        self.assertTrue(receipt["cancelRequested"])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertTrue(receipt["sourceUnchanged"])
        self.cleanup_consumer_cancellation_fallback(recovery)
        self.assertFalse(recovery["pending"])
        proof, proof_path = recovery["retirementProof"]
        self.assertTrue(proof["wholeChainRetired"])
        self.assertFalse(proof["fallbackUsed"])
        self.assertTrue(primary["pending"], "A separate recovery proof must not implicitly resolve the failed primary")
        before = set(CASE_EVIDENCE.glob("teardown-*"))
        with self.assertRaisesRegex(AssertionError, "whole-chain retirement remains unproven"):
            self._cleanup_fixture()
        retained = set(CASE_EVIDENCE.glob("teardown-*")) - before
        self.assertEqual(len(retained), 1)
        retained = retained.pop()
        record = runner.read_json(retained / "cleanup.json")
        self.assertFalse(record["cleanupComplete"])
        self.assertFalse(record["fixtureDataRemoved"])
        self.assertEqual(record["guardSurvivors"], [])
        self.assertTrue(set(primary["retentionReasons"]).issubset(record["errors"]))
        self.assertTrue(self.base.is_dir())
        self.assertTrue(temporary.is_dir())
        self.assertTrue((self.base / f"unresolved-fixture-cleanup-{record['id']}.json").is_file())
        original = Path(receipt["evidenceDirectory"])
        for name in ("start.json", "receipt.json", "product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.assertEqual((retained / "invocations" / original.name / name).read_bytes(), (original / name).read_bytes())

        # Only now explicitly apply the complete same-capture/product/ready/key
        # recovery proof. The failed attempt and no-disposal archive stay intact.
        unrelated = f"test-only unrelated retention marker {uuid.uuid4().hex}"
        self.fixture_retention_errors.append(unrelated)
        self.resolve_consumer_retention(primary, recovery, proof, proof_path)
        self.assertFalse(primary["pending"])
        self.assertIn(unrelated, self.fixture_retention_errors)
        self.fixture_retention_errors.remove(unrelated)  # Only this deliberate test-owned marker, not a real cleanup error.
        self.assertEqual(self.fixture_retention_errors, original_errors)
        self.assertEqual(runner.read_json(paths[0])["cleanup"], failed)
        self.assertFalse(runner.read_json(retained / "cleanup.json")["fixtureDataRemoved"])
        # Registered cleanup sees resolved obligations and performs a separate
        # genuine evidence/disposal attempt; no mutation of native ownership.

    def test_consumer_prebind_failure_preserves_fixture_until_complete_recovery_proof(self):
        self.assert_consumer_binding_failure_retains_fixture(partial_acquisition=False)

    def test_consumer_partial_acquisition_never_promotes_subset_retirement_or_disposes_fixture(self):
        self.assert_consumer_binding_failure_retains_fixture(partial_acquisition=True)

    def test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts(self):
        sentinel = self.sentinel()
        temporary, environment = self.consumer_environment()
        evidence = self.state / "evidence" / f"consumer-integration-{uuid.uuid4().hex}"
        producer_script = SCRIPTS / "tests/audit-consumer-test.py"
        invocation = uuid.uuid4().hex
        self.fixture_archivists.append(lambda: self.retain_consumer_fixture_states(temporary, evidence, expect_native=True))
        command = [PYTHON, str(producer_script), "--executor-integration-fixture", "--executor", str(EXECUTOR),
                   "--fixture-evidence", str(evidence)]
        code, _, err, outer = self.run_leaf(command, kind="command", invocation=invocation, env=environment)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual([outer[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
        self.assertEqual(outer["ownedSurvivors"], [])
        self.assertEqual(outer["errors"], [])
        self.assertTrue(outer["sourceUnchanged"])
        self.assertIsNone(sentinel.poll())
        producer = runner.read_json(evidence / "producer-start.json")
        binding = runner.read_json(evidence / "producer.json")
        completion = runner.read_json(evidence / "producer-completion.json")
        self.assertEqual(completion["exitCode"], 0)
        self.assertEqual(binding["executor"], str(EXECUTOR))
        self.assertEqual(binding["executorSha256"], runner.file_digest(EXECUTOR))
        self.assertEqual(producer["producerSha256"], runner.file_digest(producer_script))
        self.assertEqual(producer["consumerScriptSha256"], runner.file_digest(SCRIPTS / "check-published-consumers.sh"))
        self.assertEqual(outer["productPid"], producer["pid"])
        self.assert_consumer_ancestors(producer["parentOwnership"], environment, invocation)
        self.assert_consumer_ancestors(binding["fixtureSetupOwnership"], environment, invocation)
        self.assert_consumer_ancestors(binding["adapterOwnership"], environment, invocation)
        paths = {key: runner.absolute_path(binding[key]) for key in
                 ("fixtureBase", "fixtureRoot", "fixtureState", "childState", "consumerWorkDir", "fixtureReport")}
        for key, path in paths.items():
            self.assertTrue(runner.within(path, temporary) and path != temporary, key)
            self.assertEqual(completion[key], str(path))
        self.assertEqual(paths["childState"], paths["fixtureBase"] / "native audit state")
        self.assertEqual(paths["consumerWorkDir"].parent, paths["childState"] / "work")
        child_state, fixture_root = paths["childState"], paths["fixtureRoot"]
        context = runner.read_json(child_state / "context.json")
        self.assertEqual(context["host"], processes.host_role())
        self.assertEqual(context["root"], str(fixture_root))
        self.assertEqual(context["source"], runner.source_snapshot(fixture_root))
        self.assertEqual(context["gradleHome"], str(child_state / "gradle-home"))
        self.assertEqual(context["gradlePropertiesSha256"],
                         runner.file_digest(child_state / "gradle-home/gradle.properties"))
        directories = list((child_state / "evidence").iterdir())
        self.assertEqual(len(directories), 2)
        receipts = {}
        for directory in directories:
            receipt_path = directory / "receipt.json"
            receipt = runner.read_json(receipt_path)
            self.assertEqual(receipt["id"], directory.name)
            self.assertEqual(receipt["evidenceDirectory"], str(directory))
            self.assertNotIn(receipt["purpose"], receipts)
            receipts[receipt["purpose"]] = receipt
            self.assertEqual(receipt["schema"], 1)
            self.assertEqual(receipt["host"], processes.host_role())
            self.assertEqual(receipt["jobId"], context["id"])
            self.assertEqual(receipt["kind"], "gradle")
            self.assertEqual(receipt["cwd"], str(fixture_root))
            self.assertEqual(receipt["wrapper"], str(fixture_root / "gradlew"))
            self.assertEqual(receipt["gradleHome"], context["gradleHome"])
            self.assertEqual(receipt["sourceBefore"], context["source"])
            self.assertEqual(receipt["sourceAfter"], context["source"])
            self.assertTrue(receipt["sourceUnchanged"])
            self.assertEqual([receipt[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
            self.assertEqual(receipt["errors"], [])
            self.assertEqual(receipt["ownedSurvivors"], [])
            self.assertEqual(receipt["ownership"]["backend"], self.scope.name)
            self.assertEqual(receipt["ownership"]["discoveryErrors"], [])
            self.assertIn(invocation, receipt["ancestorInvocationIds"])
            self.assertEqual(receipt["executedArgv"],
                             [str(fixture_root / "gradlew"), *receipt["requestedArgv"], *runner.AUDIT_FLAGS])
            self.assertEqual(receipt["stopArgv"], [str(fixture_root / "gradlew"), "--stop", "--console=plain",
                             "--no-parallel", "--max-workers=2", f"-Dorg.gradle.jvmargs={runner.JVM_ARGUMENTS}"])
            self.assertEqual(runner.read_json(directory / "start.json")["id"], receipt["id"])
            self.assertEqual((directory / "stop.stdout.log").read_bytes(), b"SYNTHETIC CONSUMER WRAPPER STOP\n")
            self.assertEqual((directory / "stop.stderr.log").read_bytes(), b"")
        self.assertEqual(set(receipts), {"consumer-publish", "consumer-build"})
        self.assertEqual(receipts["consumer-publish"]["requestedArgv"], ["--no-daemon", "--console=plain",
            "publishToMavenLocal", "-Dmaven.repo.local=" + str(paths["consumerWorkDir"] / "repository")])
        build = receipts["consumer-build"]
        self.assertEqual(build["requestedArgv"][:5], ["--no-daemon", "--console=plain", "-p",
            str(paths["consumerWorkDir"] / "consumer"), "-PconsumerRepo=" + str(paths["consumerWorkDir"] / "repository")])
        self.assertEqual(build["requestedArgv"][5:], [":coreJvm:compileKotlin", ":coreJvm:compileJava",
            ":lanJvm:compileKotlin", ":desktopJvm:compileKotlin", ":androidConsumer:compileDebugKotlin",
            ":androidConsumer:processDebugManifest", ":kmpConsumer:compileKotlinJvm", ":kmpConsumer:compileAndroidMain",
            ":kmpConsumer:compileKotlinIosSimulatorArm64", ":kmpConsumer:linkDebugFrameworkIosSimulatorArm64"])
        self.assertEqual(receipts["consumer-publish"]["reports"], [])
        self.assertEqual(len(build["reports"]), 1)
        report = build["reports"][0]
        expected = b'{"fixtureOnly":true,"result":"synthetic-consumer-report-not-compilation"}\n'
        self.assertEqual(report["source"], "external/" + paths["fixtureReport"].relative_to(child_state).as_posix())
        self.assertEqual(report["classification"], "changed-since-admission")
        self.assertEqual(report["sha256"], runner.digest(expected))
        self.assertEqual(report["bytes"], len(expected))
        self.assertEqual(paths["fixtureReport"].read_bytes(), expected)
        self.assertEqual(completion["fixtureReportSha256"], runner.digest(expected))
        self.assertEqual((Path(build["evidenceDirectory"]) / report["retained"]).read_bytes(), expected)
        optional = list(child_state.glob("consumer-receipts.*"))
        self.assertEqual(len(optional), 1)
        self.assertEqual({path.name for path in optional[0].iterdir()}, {"consumer-publish.json", "consumer-build.json"})
        for purpose, receipt in receipts.items():
            self.assertEqual((optional[0] / f"{purpose}.json").read_bytes(),
                             (Path(receipt["evidenceDirectory"]) / "receipt.json").read_bytes())
        calls = [json.loads(line) for line in (evidence / "calls.jsonl").read_text().splitlines()]
        leaves = [call for call in calls if call["kind"] == "gradle"]
        stops = [call for call in calls if call["kind"] == "gradle-stop"]
        self.assertEqual(len(leaves), 2)
        self.assertEqual(len(stops), 2)
        self.assertFalse(any(call["kind"] in ("executor", "curl") for call in calls))
        for call, receipt in zip(leaves, (receipts["consumer-publish"], build)):
            self.assertEqual(call["argv"], receipt["executedArgv"][1:])
            self.assertEqual(call["home"], context["gradleHome"])
            self.assert_consumer_ancestors(call["ownership"], environment, invocation)
        for call, receipt in zip(stops, (receipts["consumer-publish"], build)):
            self.assertEqual(call["argv"], receipt["stopArgv"][1:])
            self.assertEqual(call["home"], context["gradleHome"])
        runner.write_new_json(CASE_EVIDENCE / "consumer-native-integration-verdict.json", {
            "schema": 1, "outerReceipt": outer["evidenceDirectory"], "childState": str(child_state),
            "realNativeReceiptIds": [receipt["id"] for receipt in receipts.values()],
            "retainedReportSha256": report["sha256"], "unrelatedSentinelSurvived": True,
            "scope": "Native executor/caller/report integration with synthetic tools; not product compilation or Apple approval.",
        })


class LinuxNativeTests(PosixNativeTests):
    def test_real_pidfd_stale_handle_cannot_signal_unrelated_sentinel(self):
        child = self.scope.spawn([PYTHON, "-c", "import time; time.sleep(120)"], str(self.root), self.env)
        capture = Capture(child)
        self.scope.discover()
        identity = self.scope._identity(child.pid)
        self.assertIsNotNone(identity)
        handle = self.scope._acquire(identity)
        sentinel = self.sentinel()
        try:
            signal.pidfd_send_signal(handle, signal.SIGTERM)
            capture.finish(self.scope)
            with self.assertRaises(ProcessLookupError):
                signal.pidfd_send_signal(handle, signal.SIGTERM)
            self.assertIsNone(sentinel.poll())
        finally:
            os.close(handle)


class DarwinNativeTests(PosixNativeTests):
    def test_real_opaque_task_token_and_stale_token_leave_sentinel_alive(self):
        self.assertIsInstance(self.scope, processes.DarwinScope)
        child = self.scope.spawn([PYTHON, "-c", "import time; time.sleep(120)"], str(self.root), self.env)
        capture = Capture(child)
        identity = self.scope._identity(child.pid)
        self.assertIsNotNone(identity)
        token = self.scope._acquire(identity)
        sentinel = self.sentinel()
        result = self.scope.proc.proc_signal_with_audittoken(ctypes.byref(token), signal.SIGTERM)
        self.assertEqual(result, 0, "Actual Darwin identity-scoped signal was not admitted")
        capture.finish(self.scope)
        result = self.scope.proc.proc_signal_with_audittoken(ctypes.byref(token), signal.SIGTERM)
        self.assertEqual(result, errno.ESRCH, "Exited audit token must not be accepted or converted to a PID signal")
        self.assertIsNone(sentinel.poll())


class WindowsNativeTests(ExecutorFixtureTests):
    def test_windows_readonly_nested_launcher_cleanup_preserves_source_and_outside_sentinel(self):
        code, _, err, receipt = self.run_leaf(["report"])
        self.assertEqual(0, code, err.decode(errors="replace"))
        directory = self.root / "build"
        launcher = directory / "compose/binaries/main/app/P2pKit Sample/P2pKit Sample.exe"
        launcher.parent.mkdir(parents=True)
        launcher.write_bytes(b"synthetic packaged executable; not an actual application")
        outside = self.base / "outside-readonly.txt"
        outside.write_bytes(b"outside sentinel")
        os.chmod(outside, stat.S_IREAD)
        self.addCleanup(os.chmod, outside, stat.S_IWRITE)  # Only this exact test-created sentinel, after assertions.
        outside_info = outside.lstat()
        source = self.root / "buildSrc/src/main/java/dev/p2pkit/build/Source.java"
        source_bytes = source.read_bytes()
        os.chmod(launcher, stat.S_IREAD)
        before = launcher.lstat()
        self.assertTrue(before.st_file_attributes & 1)
        self.assertEqual((0, 1), (before.st_reparse_tag, before.st_nlink))
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(0, code, err.decode(errors="replace"))
        self.assertFalse(directory.exists())
        self.assertEqual(b"outside sentinel", outside.read_bytes())
        self.assertEqual(outside_info.st_file_attributes, outside.lstat().st_file_attributes)
        self.assertEqual(source_bytes, source.read_bytes())
        self.assertTrue((Path(receipt["evidenceDirectory"]) / "receipt.json").is_file())
        record = self.cleanup_record()
        self.assertEqual([str(directory)], record["removed"])
        self.assertEqual([], record["errors"])
        self.assertEqual(1, len(record["readonlyRecoveries"]))
        attempt = record["readonlyRecoveries"][0]
        self.assertEqual(("REMOVED", "finished", before.st_file_attributes),
                         (attempt["outcome"], attempt["stage"], attempt["attributesBefore"]))
        self.assertIn(attempt["attributesAfter"], (0, 0x80) if before.st_file_attributes == 1 else (0x20,))
        self.assertEqual(("unlink", errno.EACCES, 5), (attempt["originalFailure"]["operation"],
                         attempt["originalFailure"]["errno"], attempt["originalFailure"]["winerror"]))
        start = runner.read_json(self.state / "evidence" / f"cleanup-{record['id']}-readonly-1-start.json")
        self.assertEqual("PENDING", start["recovery"]["outcome"])
        self.assertEqual(before.st_ino, start["recovery"]["leafIdentity"]["inode"])

    def test_windows_readonly_hardlink_refusal_keeps_external_file_and_original_failure(self):
        directory = self.root / "build"
        directory.mkdir()
        outside = self.base / "outside-hardlinked-launcher.exe"
        outside.write_bytes(b"shared readonly sentinel")
        launcher = directory / "launcher.exe"
        os.link(outside, launcher)
        os.chmod(outside, stat.S_IREAD)
        self.addCleanup(os.chmod, outside, stat.S_IWRITE)  # Exact test-created shared file; production must refuse it.
        before = outside.lstat()
        self.assertEqual(2, before.st_nlink)
        self.assertTrue(before.st_file_attributes & 1)
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(125, code, err.decode(errors="replace"))
        self.assertEqual(b"shared readonly sentinel", outside.read_bytes())
        self.assertEqual(b"shared readonly sentinel", launcher.read_bytes())
        self.assertEqual(before.st_file_attributes, outside.lstat().st_file_attributes)
        record = self.cleanup_record(expected_errors=("Removal failed: PermissionError",))
        self.assertEqual([], record["removed"])
        self.assertEqual(["Removal failed: PermissionError"], record["errors"])
        self.assertEqual("REFUSED", record["readonlyRecoveries"][0]["outcome"])
        self.assertIn("hardlinked", record["readonlyRecoveries"][0]["reason"])
        self.assertEqual([], list((self.state / "evidence").glob("cleanup-*-readonly-*-start.json")))

    def test_windows_launch_trace_records_exact_system_cmd_framing(self):
        requested = ["argv", "two words", "Ω", "", "tail\\"]
        code, out, err, receipt = self.run_leaf(requested)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(json.loads(out)[:len(requested)], requested)
        launches = receipt["ownership"]["launches"]
        self.assertEqual(len(launches), 2)
        for key, argv in (("productLaunchIndex", receipt["executedArgv"]), ("stopLaunchIndex", receipt["stopArgv"])):
            launch = launches[receipt[key]]
            self.assertEqual(launch["api"], "CreateProcessW")
            self.assertEqual(launch["resolvedArgv"], argv)
            self.assertEqual(launch["applicationName"], self.scope.api.cmd())
            self.assertEqual(launch["commandLine"], processes.batch_command_line(self.scope.api.cmd(), argv))
            self.assertTrue(launch["batch"] and launch["created"] and launch["resumed"])
            self.assertTrue(launch["jobAssignedBeforeResume"])

    def test_windows_cleanup_removes_actual_child_junction_not_external_sentinel(self):
        directory = self.root / "build"
        directory.mkdir()
        outside = self.base / "outside-junction"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"junction target sentinel\x00\xff\n")
        link = directory / "runtime junction"
        command = [self.scope.api.cmd(), "/d", "/v:off", "/c", "mklink", "/J", str(link), str(outside)]
        capture = Capture(self.scope.spawn(command, str(self.root), self.env))
        code, _, err = capture.finish(self.scope)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(link.lstat().st_reparse_tag, 0xA0000003)
        target_bytes = os.fsencode(os.readlink(link))
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertFalse(directory.exists())
        self.assertTrue(outside.is_dir())
        self.assertEqual(sentinel.read_bytes(), b"junction target sentinel\x00\xff\n")
        inspection = self.cleanup_record()["inspections"][0]
        self.assertEqual(inspection["entryCount"], 1)
        self.assertEqual(inspection["links"], [{"path": link.name, "kind": "junction", "reparseTag": 0xA0000003,
            "targetSha256": runner.digest(target_bytes), "targetBytes": len(target_bytes),
            "policy": "unlink-entry-only; do-not-traverse-target"}])

    def test_windows_cleanup_nested_outputs_and_junction_preserve_external_sentinel(self):
        code, _, err, receipt = self.run_leaf(["report"])
        self.assertEqual(code, 0, err.decode(errors="replace"))
        directory = self.root / "build"
        outside = self.base / "outside-nested-junction"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"nested junction target sentinel\x00\xff\n")
        link = directory / "test-results/fixture/runtime junction"
        capture = Capture(self.scope.spawn([self.scope.api.cmd(), "/d", "/v:off", "/c", "mklink", "/J",
            str(link), str(outside)], str(self.root), self.env))
        code, _, err = capture.finish(self.scope)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(link.lstat().st_reparse_tag, 0xA0000003)
        target_bytes = os.fsencode(os.readlink(link))
        with os.scandir(directory) as entries:
            child = next(entry for entry in entries if entry.name == "test-results")
            metadata = {"python": sys.version, "rootDevice": directory.lstat().st_dev,
                        "cachedChildDevice": child.stat(follow_symlinks=False).st_dev,
                        "fullChildDevice": Path(child.path).lstat().st_dev}
        self.assertEqual(metadata["fullChildDevice"], metadata["rootDevice"])
        # Record actual fields, but do not require future Python caches to be zero.
        if CASE_EVIDENCE is not None:
            (CASE_EVIDENCE / "nested-directory-metadata.json").write_text(json.dumps(metadata) + "\n")
        source = self.root / "buildSrc/src/main/java/dev/p2pkit/build/Source.java"
        source_bytes = source.read_bytes()
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertFalse(directory.exists())
        self.assertTrue(outside.is_dir())
        self.assertEqual(sentinel.read_bytes(), b"nested junction target sentinel\x00\xff\n")
        self.assertEqual(source.read_bytes(), source_bytes)
        self.assertTrue((Path(receipt["evidenceDirectory"]) / "receipt.json").is_file())
        record = self.cleanup_record()
        self.assertEqual(record["removed"], [str(directory)])
        self.assertTrue((self.state / "evidence" / f"cleanup-{record['id']}-start.json").is_file())
        inspection = record["inspections"][0]
        self.assertEqual(inspection["entryCount"], 4)
        self.assertTrue(inspection["noTargetTraversal"])
        self.assertEqual(inspection["links"], [{"path": "test-results/fixture/runtime junction", "kind": "junction",
            "reparseTag": 0xA0000003, "targetSha256": runner.digest(target_bytes), "targetBytes": len(target_bytes),
            "policy": "unlink-entry-only; do-not-traverse-target"}])

    def test_actual_job_membership_is_verified_before_resume(self):
        marker = self.state / "resumed-marker"
        original_resume = self.scope.api.ResumeThread
        observed = []

        def inspect_before_real_resume(thread):
            members = self.scope._member_pids()
            self.assertTrue(members)
            self.assertFalse(marker.exists(), "Suspended child ran before membership admission")
            observed.extend(members)
            return original_resume(thread)

        self.scope.api.ResumeThread = inspect_before_real_resume
        try:
            capture = Capture(self.scope.spawn([PYTHON, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text('ran')",
                                                 str(marker)], str(self.root), self.env))
        finally:
            self.scope.api.ResumeThread = original_resume
        self.assertEqual(capture.finish(self.scope)[0], 0)
        self.assertIn(capture.child.pid, observed)
        self.assertEqual(marker.read_text(), "ran")

    def test_batch_injection_is_refused_without_product_or_shell_side_effect(self):
        side_effect = self.state / "injected"
        code, _, _, receipt = self.run_leaf(["argv", "x&echo injected>" + str(side_effect)])
        self.assertEqual(code, 125)
        self.assertFalse(side_effect.exists())
        self.assertIsNone(receipt["productExitCode"])

    def test_kernel_job_kills_child_when_controller_exits_without_finally(self):
        ready = self.state / "crash-worker-ready.json"
        control = r'''import json, os, pathlib, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import audit_processes as p
job, leaf, state, home, ready = sys.argv[2:]
scope = p.make_scope(job, leaf, state, home)
env = p.ownership_environment(dict(os.environ), job, leaf, state, home)
code = "import json,os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid()})); time.sleep(120)"
child = scope.spawn([sys.executable, '-c', code, ready], os.getcwd(), env)
end = time.monotonic() + 10
while not pathlib.Path(ready).exists():
    if time.monotonic() > end: os._exit(9)
    time.sleep(.02)
os._exit(0)
'''
        capture = Capture(self.scope.spawn([PYTHON, "-c", control, str(SCRIPTS), self.context["id"], uuid.uuid4().hex,
            str(self.state), self.context["gradleHome"], str(ready)], str(self.root), self.env))
        self.assertEqual(capture.finish(self.scope)[0], 0)
        pid = json.loads(ready.read_text())["pid"]
        deadline = time.monotonic() + 5
        while pid in {row["pid"] for row in self.scope.discover()} and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertNotIn(pid, {row["pid"] for row in self.scope.discover()}, "Kill-on-controller-close did not drain its job")

def main():
    global EVIDENCE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", choices=runner.HOSTS, default=processes.host_role())
    parser.add_argument("--evidence-root", "--evidence-dir", dest="evidence_root")
    args = parser.parse_args()
    if args.expected_host != processes.host_role():
        parser.error("Requested host does not match this native interpreter")
    if args.evidence_root:
        EVIDENCE_ROOT = runner.absolute_path(args.evidence_root, exists=False)
        EVIDENCE_ROOT.mkdir(mode=0o700)
    elif os.environ.get(processes.STATE_ENV):
        state = runner.absolute_path(os.environ[processes.STATE_ENV])
        EVIDENCE_ROOT = state / "evidence" / f"executor-fixtures-{uuid.uuid4().hex}"
        EVIDENCE_ROOT.mkdir(mode=0o700)
    else:
        EVIDENCE_ROOT = Path(tempfile.mkdtemp(prefix="p2pkit-executor-fixture-evidence-")).resolve()
    native = {"Linux": LinuxNativeTests, "Darwin": DarwinNativeTests, "Windows": WindowsNativeTests}.get(
        __import__("platform").system())
    if native is None:
        parser.error("No native ownership fixture suite for this host")
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(PurePolicyTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(DarwinObservationTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(native)])
    print(f"Running current-host real executor fixtures: {processes.host_role()}; no other-host/native claims", flush=True)
    print(f"Retained fixture receipts/logs: {EVIDENCE_ROOT}", flush=True)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
