#!/usr/bin/env python3
"""Tiny file/ownership fixtures, NOT native-provider/Gradle/cache qualification.

No restored cache, real dependency archive, download, child process, GPG or
resolver is used. The accepted independent XML parser tests remain unchanged.
"""
from contextlib import ExitStack
import copy
import errno
import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_dependency_seed_files as S
SPEC = importlib.util.spec_from_file_location("seed_file_controller_models", ROOT / "scripts/run-hosted-test-custody.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def metadata(rows):
    components = "".join('<component group="org.fixture" name="' + name + '" version="1.0">' +
        '<artifact name="' + name + '.jar"><sha256 value="' + S.digest(raw) + '"/></artifact></component>'
        for name, raw in sorted(rows.items()))
    return ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' + S.authority.NAMESPACE +
        '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="' + S.authority.SCHEMA_LOCATION +
        '"><configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures>' +
        '</configuration><components>' + components + '</components></verification-metadata>').encode()


class SeedFiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="seed-file-model-", dir=ROOT.parent)
        self.path = Path(self.temp.name).resolve(strict=True)
        self.session = self.path / "session"
        self.session.mkdir(mode=0o700)
        (self.session / "state").mkdir(mode=0o700)
        self.home = self.session / "state/gradle-home"
        self.home.mkdir(mode=0o700)
        self.properties = b"org.gradle.workers.max=2\n"
        (self.home / "gradle.properties").write_bytes(self.properties)
        (self.home / "gradle.properties").chmod(0o600)
        self.container = S.stage_path(self.session, "desktop", "macos-arm64")
        self.container.mkdir(mode=0o700)
        self.source = self.container / "restore-home"
        self.source.mkdir(mode=0o755)
        self.owner = C.PrivateOwner()
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")))
        self.stack.enter_context(patch.object(socket, "create_connection", side_effect=AssertionError("NO_NETWORK")))
        self.stack.enter_context(patch.object(subprocess, "Popen", side_effect=AssertionError("NO_PROCESS")))
        self.quarantine = list(C.QUARANTINE)
        self.rows = {"FastInfoset": b"synthetic fixture bytes, not an artifact"}
        self.bind()

    def tearDown(self):
        self.stack.close()
        # Only synthetic local descriptors. UNKNOWN assertions precede this
        # fixture teardown; this is not a production quarantine recovery API.
        for row in reversed(self.owner.resources):
            try:
                row["owner"].close()
            except BaseException:
                pass
        C.QUARANTINE[:] = self.quarantine
        self.temp.cleanup()

    def bind(self):
        self.xml = metadata(self.rows)
        self.compiled = S.authority.parse_allowlist(self.xml)
        self.inputs = {"files": {name: S.digest(self.xml if index == 0 else name.encode())
                                for index, name in enumerate(S.INPUTS)},
                       "allowlistSha256": self.compiled.authority_sha256, "artifacts": len(self.rows),
                       "components": len(self.rows), "policy": S.policy()}
        self.admitted_raw = S.encoded({"source": {"commit": "a" * 40, "tree": "b" * 40},
                                      "github": {"runId": "123", "runAttempt": "1"}})
        self.staging = S.stage_record(self.admitted_raw, "desktop", "macos-arm64", self.container,
                                     S._info(self.container.stat()), S._info(self.source.stat()), self.inputs)
        self.staging_raw = S.encoded(self.staging)
        self.intent = S.seed_intent(self.admitted_raw, "desktop", "macos-arm64", self.container,
                                   self.staging_raw, self.inputs)
        self.context_raw = S.encoded({"session": str(self.session), "profile": "desktop", "role": "macos-arm64",
             "source": S.record(self.admitted_raw)["source"], "dependencySeed": self.intent})
        self.canonical_raw = S.encoded({"gradleHome": str(self.home),
                                       "gradlePropertiesSha256": S.digest(self.properties)})

    def candidate(self, name="FastInfoset", *, data=None, bucket=None):
        raw = self.rows[name] if data is None else data
        bucket = hashlib.sha1(raw).hexdigest() if bucket is None else bucket
        path = self.source.joinpath(*S.PREFIX, "org.fixture", name, "1.0", bucket, name + ".jar")
        path.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
        return path

    def seed(self, *, now=None, check=lambda: None):
        clock = now or (lambda: int(time.monotonic() * 10**9))
        began = clock()
        self.interval = S.window(began, began + 120 * 10**9, began + 90 * 10**9, raw=False, job_budget=None)
        return S.seed_home(self.owner, self.home, self.intent, self.staging, self.compiled, self.context_raw,
                           self.canonical_raw, self.admitted_raw, end=time.monotonic() + 120,
                           check=check, now=clock, interval=self.interval)

    def validate(self, result):
        return S.validate_receipt(result, self.intent, self.staging_raw, self.context_raw, self.canonical_raw,
                                  self.admitted_raw, self.compiled)

    def assert_known_closed(self):
        self.assertFalse(self.owner.unknown)
        self.assertTrue(all(row["closed"] for row in self.owner.resources))

    def test_public_bytes_copy_same_reader_then_close_readback_before_admission(self):
        candidate = self.candidate()
        events, original = [], S.PosixFile
        for method in ("read", "seek", "write", "sync", "verify", "close"):
            delegate = getattr(original, method)
            def invoke(stream, *args, _method=method, _delegate=delegate):
                if stream.path.name == "FastInfoset.jar":
                    events.append((_method, id(stream), str(stream.path), stream.writable))
                return _delegate(stream, *args)
            self.stack.enter_context(patch.object(original, method, invoke))
        result = self.seed()
        self.validate(result)
        self.assertEqual(result["status"], "KNOWN_SEEDED")
        self.assertEqual(result["wrapper"], S.WRAPPER)
        destination = self.home / result["admitted"][0]["path"]
        self.assertEqual(destination.read_bytes(), candidate.read_bytes())
        self.assertNotEqual(destination.stat().st_ino, candidate.stat().st_ino)
        reads = [row for row in events if row[0] == "read" and row[2] == str(candidate)]
        self.assertEqual(len({row[1] for row in reads}), 1)
        rewind = next(i for i, row in enumerate(events) if row[0] == "seek")
        write = next(i for i, row in enumerate(events) if row[0] == "write")
        sync = next(i for i, row in enumerate(events) if row[0] == "sync")
        close = next(i for i, row in enumerate(events) if row[0] == "close" and row[3])
        readback = next(i for i, row in enumerate(events) if row[0] == "read" and row[2] == str(destination))
        self.assertTrue(0 < rewind < write < sync < close < readback)
        self.assertEqual((destination.stat().st_mode & 0o777, destination.parent.stat().st_mode & 0o777), (0o600, 0o700))
        self.assert_known_closed()

    def test_absence_is_completed_known_miss_and_creates_no_cache_namespace(self):
        result = self.seed()
        self.validate(result)
        self.assertEqual(result["status"], "KNOWN_MISS")
        self.assertEqual(result["misses"], [{"index": 0, "reason": "ABSENT", "rejected": 0}])
        self.assertEqual({p.name for p in self.home.iterdir()}, {"gradle.properties"})
        self.assert_known_closed()

    def test_opaque_unselected_state_and_wrapper_are_never_opened_or_copied(self):
        self.candidate()
        for name in ("init.d/loader", "wrapper/distribution.zip.ok", "wrapper/gradle/bin/gradle",
                     "caches/metadata-2.100/resource.bin", "caches/transforms/a.class", "konan/toolchain", "secret.log"):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"UNTRUSTED UNSELECTED")
        opened, original = [], S._PosixDirectory._child
        def observe(view, name, **kwargs):
            opened.append(str(view.path / name))
            return original(view, name, **kwargs)
        with patch.object(S._PosixDirectory, "_child", observe):
            result = self.seed()
        self.assertEqual(result["status"], "KNOWN_SEEDED")
        self.assertFalse(any("metadata-2" in path or "/wrapper" in path or "/init.d" in path for path in opened))
        self.assertEqual(len([path for path in self.home.rglob("*") if path.is_file()]), 2)

    def test_stable_hash_or_layout_mismatch_is_rejected_before_any_target(self):
        for mismatch in ("sha256", "bucket"):
            with self.subTest(mismatch=mismatch):
                candidate = self.candidate(data=b"wrong" if mismatch == "sha256" else None,
                                           bucket="0" * 40 if mismatch == "bucket" else None)
                result = self.seed()
                self.validate(result)
                self.assertEqual(result["status"], "KNOWN_MISS")
                self.assertEqual(result["misses"][0]["reason"],
                                 "SHA256_REJECTED" if mismatch == "sha256" else "LAYOUT_REJECTED")
                self.assertFalse((self.home / "caches").exists())
                candidate.unlink()
                self.assert_known_closed()

    def test_rejected_then_valid_candidate_charges_prehash_without_losing_authority(self):
        self.candidate(data=b"wrong", bucket="0" * 40)
        self.candidate()
        result = self.seed()
        self.validate(result)
        self.assertEqual(result["status"], "KNOWN_SEEDED")
        self.assertEqual(result["counts"]["prehashBytes"], len(self.rows["FastInfoset"]) + 5)
        self.assertEqual(result["counts"]["sha256Rejected"], 1)

    def test_short_io_makes_progress_and_is_hashed_exactly(self):
        self.candidate()
        read, write = S.os.read, S.os.write
        with patch.object(S.os, "read", side_effect=lambda fd, size: read(fd, min(size, 3))), \
                patch.object(S.os, "write", side_effect=lambda fd, raw: write(fd, raw[:2])):
            result = self.seed()
        self.assertEqual(result["status"], "KNOWN_SEEDED")
        self.validate(result)
        self.assert_known_closed()

    def test_zero_progress_read_or_write_fails_and_never_admits_partial_output(self):
        self.candidate()
        with patch.object(S.PosixFile, "read", return_value=b""):
            with self.assertRaises(S.SeedError):
                self.seed()
        self.assertFalse((self.home / "caches").exists())
        with patch.object(S.PosixFile, "write", return_value=0):
            with self.assertRaises(S.SeedError) as caught:
                self.seed()
        self.assertFalse(caught.exception.seed_result["completed"])
        self.assertEqual(caught.exception.seed_result["admitted"], [])

    def test_positive_entry_open_failure_is_not_an_absence_miss(self):
        self.candidate()
        original = S.PosixSourceDirectory.open_file
        def denied(directory, name, **kwargs):
            if name == "FastInfoset.jar":
                raise PermissionError("synthetic selected entry denial")
            return original(directory, name, **kwargs)
        with patch.object(S.PosixSourceDirectory, "open_file", denied):
            with self.assertRaises(PermissionError) as caught:
                self.seed()
        self.assertEqual(caught.exception.seed_result["status"], "UNKNOWN")
        self.assertFalse(caught.exception.seed_result["completed"])
        self.assertFalse((self.home / "caches").exists())

    def test_source_rewind_mutation_is_not_hash_mismatch_or_retry(self):
        candidate = self.candidate()
        original = S.PosixFile.seek
        def mutate(reader, offset, whence=0):
            if reader.path == candidate:
                candidate.write_bytes(b"x" * candidate.stat().st_size)
            return original(reader, offset, whence)
        with patch.object(S.PosixFile, "seek", mutate):
            with self.assertRaises(S.SeedError) as caught:
                self.seed()
        self.assertFalse(caught.exception.seed_result["completed"])
        self.assertFalse((self.home / "caches").exists())

    def test_readback_corruption_after_writer_close_blocks_admission(self):
        self.candidate()
        original = S.PosixFile.close
        def corrupt(stream):
            mutate = stream.writable and stream.path.name == "FastInfoset.jar" and not stream.closed
            original(stream)
            if mutate:
                stream.path.write_bytes(b"x" * stream.path.stat().st_size)
        with patch.object(S.PosixFile, "close", corrupt):
            with self.assertRaises(S.SeedError) as caught:
                self.seed()
        self.assertEqual(caught.exception.seed_result["admitted"], [])
        self.assertEqual(caught.exception.seed_result["status"], "FAILED")

    def test_public_source_permissions_do_not_relax_private_destination_permissions(self):
        candidate = self.candidate()
        self.assertEqual(candidate.stat().st_mode & 0o777, 0o644)
        (self.home / "gradle.properties").chmod(0o644)
        with self.assertRaises(S.SeedError):
            self.seed()
        self.assertFalse((self.home / "caches").exists())

    def test_unsafe_selected_symlink_and_hardlink_refuse(self):
        candidate = self.candidate()
        other = self.path / "other"
        other.write_bytes(candidate.read_bytes())
        candidate.unlink()
        candidate.symlink_to(other)
        with self.assertRaises(OSError):
            self.seed()
        candidate.unlink()
        os.link(other, candidate)
        with self.assertRaises(S.SeedError):
            self.seed()
        self.assertFalse((self.home / "caches").exists())

    def assert_selected_fifo_refused(self, *, swap_at_open):
        candidate = self.candidate()
        if not swap_at_open:
            candidate.unlink()
            os.mkfifo(candidate, 0o600)
        original, opened = S.os.open, []
        inode = candidate.parent.stat().st_ino
        def guarded(name, flags, *args, **kwargs):
            selected = name == candidate.name and "dir_fd" in kwargs and os.fstat(kwargs["dir_fd"]).st_ino == inode
            if selected:
                if swap_at_open:
                    candidate.unlink()
                    os.mkfifo(candidate, 0o600)
                # Refuse an unsafe call in the test instead of hanging a host.
                self.assertTrue(flags & os.O_NONBLOCK, "Selected FIFO must never enter a blocking open")
                self.assertTrue(flags & os.O_NOFOLLOW)
            fd = original(name, flags, *args, **kwargs)
            if selected:
                opened.append(fd)
                self.assertTrue(stat.S_ISFIFO(os.fstat(fd).st_mode))
            return fd
        with patch.object(S.os, "open", side_effect=guarded):
            with self.assertRaisesRegex(S.SeedError, "SEED_DESCRIPTOR_IDENTITY_OR_KIND") as caught:
                self.seed()
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError) as closed:
            os.fstat(opened[0])
        self.assertEqual(closed.exception.errno, errno.EBADF)
        self.assertFalse(caught.exception.seed_result["completed"])
        self.assertEqual(caught.exception.seed_result["admitted"], [])
        self.assertFalse((self.home / "caches").exists())

    def test_selected_fifo_is_nonblocking_and_refused_with_new_descriptor_retired(self):
        self.assert_selected_fifo_refused(swap_at_open=False)

    def test_regular_selected_file_swapped_to_fifo_at_open_is_nonblocking_and_refused(self):
        self.assert_selected_fifo_refused(swap_at_open=True)

    def test_fresh_home_rejects_foreign_namespace_even_if_empty(self):
        self.candidate()
        (self.home / "caches").mkdir(mode=0o700)
        with self.assertRaisesRegex(S.SeedError, "SEED_HOME_NOT_FRESH"):
            self.seed()

    def test_selected_directory_member_and_version_overflow_are_not_absence(self):
        self.candidate()
        version = self.source.joinpath(*S.PREFIX, "org.fixture/FastInfoset/1.0")
        (version / ("0" * 40)).mkdir()
        with patch.object(S, "VERSION_LIMIT", 1):
            with self.assertRaisesRegex(S.SeedError, "OVERFLOW"):
                self.seed()

    def test_casefold_alias_list_refuses_before_selected_opens(self):
        self.candidate()
        # Case-insensitive APFS cannot materialize two aliases. Model ONLY the
        # cursor's hostile names; the production listing/admission code runs.
        class Cursor:
            def __iter__(self):
                return iter((SimpleNamespace(name="caches"), SimpleNamespace(name="CACHES")))
            def close(self):
                pass
        scan, inode = S.os.scandir, self.source.stat().st_ino
        def selected(fd):
            return Cursor() if isinstance(fd, int) and os.fstat(fd).st_ino == inode else scan(fd)
        with patch.object(S.os, "scandir", side_effect=selected):
            with self.assertRaisesRegex(S.SeedError, "ALIAS"):
                self.seed()

    def test_oversized_selected_file_is_rejected_without_payload_reads(self):
        candidate = self.candidate()
        original, reads = S.PosixFile.read, []
        def observe(reader, size):
            reads.append(reader.path.name)
            return original(reader, size)
        source = self.owner.acquire("bounded-source", lambda: S.public_root(candidate.parent))
        with patch.object(S.PosixFile, "read", observe):
            with self.assertRaisesRegex(S.SeedError, "SEED_FILE_LIMIT"):
                source.open_file(candidate.name, max_bytes=4, deadline=time.monotonic() + 30)
        self.assertNotIn("FastInfoset.jar", reads)

    def test_byte_budget_partial_is_only_at_a_closed_candidate_boundary(self):
        self.rows = {"A": b"123", "B": b"456"}
        with patch.object(S, "TOTAL_LIMIT", 5):
            self.bind()
            self.candidate("A")
            self.candidate("B")
            result = self.seed()
            self.validate(result)
        self.assertEqual(result["status"], "KNOWN_PARTIAL")
        self.assertEqual(result["counts"]["outputBytes"], 3)
        self.assertEqual(result["misses"][0]["reason"], "BYTE_BUDGET")
        self.assert_known_closed()

    def test_soft_stop_is_known_miss_but_active_hard_timeout_fails(self):
        self.candidate()
        clock = [10**9]
        def soft():
            clock[0] = self.interval["softEndNs"]
        result = self.seed(now=lambda: clock[0], check=soft)
        self.assertEqual(result["status"], "KNOWN_MISS")
        self.assertEqual(result["misses"][0]["reason"], "BUDGET_NOT_STARTED")
        clock[0] = 10**9
        def hard():
            clock[0] = self.interval["hardEndNs"]
        with self.assertRaisesRegex(S.SeedError, "HARD_DEADLINE"):
            self.seed(now=lambda: clock[0], check=hard)

    def test_primary_failure_retains_secondary_close_and_sticky_unknown(self):
        self.candidate()
        original = S.PosixFile.close
        failure = OSError("synthetic primary sync failure")
        def fail_close(stream):
            candidate = stream.writable and stream.path.name == "FastInfoset.jar" and not stream.closed
            original(stream)
            if candidate:
                raise OSError("synthetic late close failure after fixture descriptor retired")
        with patch.object(S.PosixFile, "sync", side_effect=failure), patch.object(S.PosixFile, "close", fail_close):
            with self.assertRaises(OSError) as caught:
                self.seed()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.owner.original, failure)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(caught.exception.seed_result["status"], "UNKNOWN")
        self.assertTrue(getattr(failure, "__notes__", ()))
        self.assertTrue(any(row["stage"].endswith("-close") for row in self.owner.errors))

    def test_rejected_candidate_close_unknown_stops_other_candidate_and_remaining_closes(self):
        rejected = self.candidate(data=b"wrong", bucket="0" * 40)
        self.candidate()
        original, attempts = S.PosixFile.close, []
        def failed(stream):
            first = stream.path == rejected and not stream.closed
            attempts.append((str(stream.path), stream.closed))
            original(stream)
            if first:
                raise OSError("synthetic source close uncertainty after actual fixture close")
        with patch.object(S.PosixFile, "close", failed):
            with self.assertRaises(S.SeedError) as caught:
                self.seed()
        self.assertEqual(caught.exception.seed_result["status"], "UNKNOWN")
        candidates = [row for row in self.owner.resources if row["label"] == "dependency-seed-candidate"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(sum(path == str(rejected) for path, _closed in attempts), 1)
        # The original policy does not touch additional owners after uncertainty.
        self.assertFalse(next(row for row in self.owner.resources if row["label"] == "dependency-seed-restore-root")["attempted"])

    def test_directory_cursor_failure_keeps_primary_and_secondary_close_uncertainty(self):
        self.candidate()
        original, inode = S.os.scandir, self.source.stat().st_ino
        failure = OSError("synthetic primary enumeration failure")
        class Cursor:
            def __init__(self, delegate):
                self.delegate = delegate
            def __iter__(self):
                raise failure
            def close(self):
                self.delegate.close()
                raise OSError("synthetic cursor close uncertainty")
        def selected(fd):
            cursor = original(fd)
            return Cursor(cursor) if isinstance(fd, int) and os.fstat(fd).st_ino == inode else cursor
        with patch.object(S.os, "scandir", side_effect=selected):
            with self.assertRaises(OSError) as caught:
                self.seed()
        self.assertIs(caught.exception, failure)
        self.assertTrue(self.owner.unknown)
        self.assertTrue(getattr(failure, "__notes__", ()))

    def test_directory_cursor_close_only_failure_is_unknown_before_other_retirement(self):
        self.candidate()
        original, inode = S.os.scandir, self.source.stat().st_ino
        failure = OSError("synthetic first cursor close uncertainty")
        owner, at_failure = self.owner, []
        class Cursor:
            def __init__(self, delegate):
                self.delegate = delegate
            def __iter__(self):
                return iter(self.delegate)
            def close(self):
                self.delegate.close()  # Retire the actual tiny fixture cursor.
                at_failure[:] = [(id(row["owner"]), row["attempted"], row["closed"]) for row in owner.resources]
                raise failure
        def selected(fd):
            cursor = original(fd)
            return Cursor(cursor) if isinstance(fd, int) and os.fstat(fd).st_ino == inode else cursor
        with patch.object(S.os, "scandir", side_effect=selected):
            with self.assertRaises(OSError) as caught:
                self.seed()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.owner.original, failure)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(caught.exception.seed_result["status"], "UNKNOWN")
        self.assertEqual(caught.exception.seed_result["retirement"], "UNKNOWN")
        self.assertTrue(any("directory-cursor retirement UNKNOWN" in note for note in failure.__notes__))
        self.assertTrue(at_failure)
        self.assertEqual([(id(row["owner"]), row["attempted"], row["closed"]) for row in owner.resources], at_failure)
        self.assertFalse(next(row for row in owner.resources if row["label"] == "dependency-seed-restore-root")["attempted"])

    def test_original_source_ancestor_replacement_cannot_rebind_open_descriptor(self):
        candidate = self.candidate()
        source = self.owner.acquire("retained-source", lambda: S.public_root(candidate.parent))
        before = candidate.parent
        after = before.with_name("1" * 40)
        before.rename(after)
        before.mkdir()
        with self.assertRaisesRegex(S.SeedError, "IDENTITY"):
            source.verify()
        with self.assertRaises(S.SeedError):
            source.close()

    def test_same_restored_home_under_replaced_control_container_is_rejected(self):
        self.candidate()
        previous = self.container.with_name(self.container.name + "-previous")
        self.container.rename(previous)
        self.container.mkdir(mode=0o700)
        (previous / "restore-home").rename(self.source)
        with self.assertRaisesRegex(S.SeedError, "CONTAINER_REPLACED"):
            self.seed()
        self.assertFalse((self.home / "caches").exists())

    def test_receipt_budget_stops_before_creating_a_target(self):
        with patch.object(S, "RECEIPT_LIMIT", 12000):
            self.bind()
            self.candidate()
            result = self.seed()
            self.validate(result)
        self.assertEqual(result["status"], "KNOWN_MISS")
        self.assertEqual(result["misses"][0]["reason"], "BYTE_OR_RECEIPT_BUDGET")
        self.assertFalse((self.home / "caches").exists())
        self.assert_known_closed()

    def test_destination_member_limit_cannot_be_hidden_by_partial_directory_creation(self):
        self.candidate()
        with patch.object(S, "MEMBER_LIMIT", 7), patch.object(S, "NAMES_LIMIT", 7):
            self.bind()
            with self.assertRaises(S.SeedError) as caught:
                self.seed()
        self.assertEqual(caught.exception.seed_result["admitted"], [])
        self.assertFalse(caught.exception.seed_result["completed"])

    def test_unexpected_destination_member_after_copy_and_changed_properties_fail(self):
        self.candidate()
        original = S._Destination.verify
        def foreign(destination, admitted):
            (self.home / "foreign").write_bytes(b"foreign")
            return original(destination, admitted)
        with patch.object(S._Destination, "verify", foreign):
            with self.assertRaisesRegex(S.SeedError, "FOREIGN_DESTINATION"):
                self.seed()

    def test_receipt_tampering_cannot_relabel_missing_or_wrong_authority_as_seeded(self):
        self.candidate()
        result = self.seed()
        changes = [lambda v: v.update(status="KNOWN_MISS"), lambda v: v.update(completed=False),
            lambda v: v.update(retirement="UNKNOWN"), lambda v: v.update(schema=True),
            lambda v: v["admitted"][0].update(path="caches/evil"),
            lambda v: v["admitted"][0].update(sha256="0" * 64),
            lambda v: v["admitted"][0].update(index=True),
            lambda v: v["counts"].update(outputBytes=0),
            lambda v: v["counts"].update(destinationMembers=0),
            lambda v: v["window"].update(finishedNs=v["window"]["hardEndNs"]),
            lambda v: v.update(stagingSha256="0" * 64), lambda v: v.update(contextSha256="0" * 64),
            lambda v: v.update(propertiesAfterSha256="0" * 64),
            lambda v: v.update(wrapper="HIT"), lambda v: v.update(extra="not admitted")]
        for mutate in changes:
            candidate = copy.deepcopy(result)
            mutate(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(S.SeedError):
                self.validate(candidate)

    def test_original_receipt_does_not_snapshot_later_legitimate_product_cache_changes(self):
        self.candidate()
        result = self.seed()
        (self.home / result["admitted"][0]["path"]).unlink()
        (self.home / "caches/metadata-new").mkdir()
        (self.source / "action-post").write_bytes(b"synthetic post-action change")
        self.assertEqual(self.validate(result), result)
        self.assertTrue(S.profile_passed({"contextSha256": S.digest(self.context_raw),
                                         "dependencySeed": S.disposition(S.encoded(result))}))

    def test_source_inputs_reads_only_closed_roster_and_parser_remains_authority(self):
        root = self.path / "admitted-source"
        root.mkdir(mode=0o755)
        for index, name in enumerate(S.INPUTS):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.xml if index == 0 else name.encode())
        (root / "unrelated").symlink_to(self.path / "absent")
        inputs, compiled = S.source_inputs(self.owner, root, time.monotonic() + 30, lambda: None)
        self.assertEqual(inputs, self.inputs)
        self.assertEqual(compiled, self.compiled)
        self.assert_known_closed()

    def test_duplicate_json_keys_and_nonfinite_values_are_not_receipt_authority(self):
        for raw in (b'{"status":"FAILED","status":"KNOWN_SEEDED"}', b'{"count":NaN}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(S.SeedError):
                S.record(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
