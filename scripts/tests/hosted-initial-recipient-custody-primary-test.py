#!/usr/bin/env python3
"""NEW focused PRIMARY-copy controls; SOURCE ONLY until separately admitted.

Tiny owned POSIX files exercise the low-level copy and fixed caller seams.
The caller model supplies primary_record/history results and host/Step/clocks;
its ownership, original30/Window transition, snapshot/copy and return gates stay
real. Separate coherent supplied-byte histories use the actual maintained pure
parsers (gate, worker and crypto), not authentic hosted originals. Original
receiving first LOCAL is never reconstructed. No old reader/fixture is imported,
current authority/Recipient acquired, native Windows operation or process run.
The shallow three-byte public packet is GRAMMAR ONLY; central crypto fixtures
use checked-in PUBLIC policy packets without GPG/key qualification. No result
here is a hosted/native/provider/timing/complete-carrier acceptance.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager, ExitStack
import ctypes  # Complete stdlib initialization before the no-native audit hook.
import dataclasses
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("custody_primary_supplied_models",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS, BOOT = 1_000_000_000, "a" * 64


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reading():
    return D.O.clocks.Reading(D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS), 50 * NS)


class Clocks:
    def __init__(self):
        self.local, self.raw, self.callback = 100.0, 60 * NS, lambda: None

    def monotonic(self):
        return self.local

    def checked(self, _clock, *, minimum_ns=0):
        if self.raw < minimum_ns:
            raise RuntimeError("SUPPLIED_RAW_BACKWARDS")
        return self.raw

    def cancelled(self):
        self.callback()


@contextmanager
def models():
    clock = Clocks()
    with patch.object(D.time, "monotonic", clock.monotonic), \
            patch.object(D.O.clocks, "checked_now", clock.checked), \
            patch.object(D.C, "boot_digest", lambda _role: BOOT):
        yield clock


def own(clock):
    return D._PrimaryOwner(D.native.Owner(200.0, first=reading(), cancelled=clock.cancelled))


def put(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
    path.chmod(0o600)


def tiny(owner, root, *, embedded=False):
    """Small actual POSIX files, deliberately NOT a valid281-file gate carrier."""
    source, handoff, destination = (root / name for name in ("primary", "handoff", "copy"))
    for path in (source, handoff, destination, source / "empty-dir"):
        path.mkdir(mode=0o700)
    contents = {"a.bin": b"sample-bytes\x00\xff", "empty.bin": b""}
    for name, raw in contents.items():
        put(source / name, raw)
    handoff_raw, handoff_name = b"SUPPLIED_HANDOFF_NOT_AN_AUTHENTIC_STEP\n", "gate-originals.json"
    put(handoff / handoff_name, handoff_raw)
    pins = {"P": D.native.posix._identity(source), "P/empty-dir": D.native.posix._identity(source / "empty-dir")}
    primary = D.Primary("gate", "linux-x64", handoff_raw, b"SUPPLIED_INDEX_NOT_AUTHENTICATED",
        (("P", source),), tuple((name, tuple(pin), "ORIGINAL_NATIVE_PIN") for name, pin in sorted(pins.items())),
        tuple(("P/" + name, max(1, len(raw)), len(raw), sha(raw), "ORIGINAL_PRIMARY_DECLARATION")
            for name, raw in sorted(contents.items())),
        (("receiving-authority-return.json", b"SUPPLIED_EMBEDDED_AUTHORITY"),
         ("initialization-history.json", b"SUPPLIED_EMBEDDED_HISTORY")) if embedded else (), sha(b"SUPPLIED_RESULT"))
    source_dir = D._private(owner, source)
    handoff_dir = D._private(owner, handoff)
    destination_dir = D._private(owner, destination)
    sources = (D._snapshot(owner, "P", source_dir),)
    handoff_snapshot = D._snapshot(owner, "HANDOFF", handoff_dir)
    return SimpleNamespace(primary=primary, sources=sources, handoff=handoff_snapshot, name=handoff_name,
        destination=destination_dir, source=source, path=destination, contents=contents)


def copy(owner, fixture):
    return D._copy_indexed(owner, fixture.primary, fixture.sources, fixture.handoff, fixture.name, fixture.destination)


class TinyPosixCopyTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.name, "posix", "This frozen offline file envelope is POSIX-only, never a platform skip")

    def test_real_empty_file_empty_directory_and_exact_flat_readback(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner, root = own(clock), Path(temp)
            fixture = tiny(owner, root)
            value = json.loads(copy(owner, fixture))
            self.assertEqual(value["memberCount"], 3)
            self.assertEqual(value["remainingOrigins"], ["AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT"])
            self.assertEqual(value["freeze"], "NOT_FINAL_THREE_ORIGIN_FREEZE")
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertEqual([row["member"] for row in value["members"]],
                ["member-00000.bin", "member-00001.bin", "member-00002.bin"])
            self.assertEqual((fixture.path / "member-00001.bin").read_bytes(), b"")
            self.assertEqual({row[0] for row in value["sourceMetadata"]}, {"P", "P/empty-dir", "P/a.bin", "P/empty.bin"})
            for row in value["members"]:
                raw = (fixture.path / row["member"]).read_bytes()
                self.assertEqual((len(raw), sha(raw)), (row["bytes"], row["sha256"]))
            closure = json.loads(owner.finish())
            self.assertEqual(closure["retirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
            self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.ledger))
            self.assertNotIn("copy-map.json", {path.name for path in fixture.path.iterdir()})

    def test_embedded_and_handoff_are_not_relabelled_as_indexed_disk(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp), embedded=True)
            value = json.loads(copy(owner, fixture))
            self.assertEqual([row["carrier"] for row in value["members"]],
                ["INDEXED_DISK_ORIGINAL", "INDEXED_DISK_ORIGINAL", "HANDOFF",
                 "EMBEDDED_NOT_DISK_ORIGINAL", "EMBEDDED_NOT_DISK_ORIGINAL"])
            self.assertEqual([row["original"] for row in value["members"][-2:]],
                ["receiving-authority-return.json", "initialization-history.json"])
            self.assertEqual((fixture.path / "member-00003.bin").read_bytes(), b"SUPPLIED_EMBEDDED_AUTHORITY")
            owner.finish()

    def test_changed_source_bytes_fail_hash_and_close_real_reader_writer(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            rows = list(fixture.primary.files)
            rows[0] = (*rows[0][:3], sha(b"wrong"), rows[0][4])
            fixture.primary = dataclasses.replace(fixture.primary, files=tuple(rows))
            with self.assertRaises(Exception):
                copy(owner, fixture)
            self.assertFalse(owner.owner.unknown)
            self.assertTrue(all(row["closed"] for row in owner.ledger if row["label"] in ("reader", "writer")))
            with self.assertRaises(Exception):
                owner.finish()
            self.assertTrue(owner.owner.closed)

    def test_source_roster_addition_is_not_ignored(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            put(fixture.source / "extra.bin", b"unlisted")
            with self.assertRaises(Exception):
                D._snapshot_current(owner, fixture.sources[0], rescan=True)
            owner.finish()

    def test_directory_pin_changed_rejects_before_first_write(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            rows = list(fixture.primary.directories)
            rows[0] = (rows[0][0], (rows[0][1][0], rows[0][1][1] + 1), rows[0][2])
            fixture.primary = dataclasses.replace(fixture.primary, directories=tuple(rows))
            with self.assertRaises(Exception):
                copy(owner, fixture)
            self.assertEqual(list(fixture.path.iterdir()), [])
            owner.finish()

    def test_missing_empty_directory_is_rejected(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            fixture.primary = dataclasses.replace(fixture.primary, directories=fixture.primary.directories[:1])
            with self.assertRaises(Exception):
                copy(owner, fixture)
            owner.finish()

    def test_actual_symlink_source_is_refused(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            root = Path(temp) / "source"
            root.mkdir(mode=0o700)
            put(root / "target", b"x")
            (root / "alias").symlink_to("target")
            private = D._private(owner, root)
            with self.assertRaises(Exception):
                D._snapshot(owner, "P", private)
            self.assertTrue(owner.owner.unknown)  # Supplier failure does not invent internal descriptor-close proof.

    def test_actual_hardlink_source_is_refused(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            root = Path(temp) / "source"
            root.mkdir(mode=0o700)
            put(root / "target", b"x")
            os.link(root / "target", root / "alias")
            private = D._private(owner, root)
            with self.assertRaises(Exception):
                D._snapshot(owner, "P", private)
            self.assertTrue(owner.owner.unknown)

    def test_existing_destination_is_exclusive_never_overwritten(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            target = fixture.path / "member-00000.bin"
            put(target, b"OWNER_EXISTING_BYTES")
            with self.assertRaises(Exception):
                copy(owner, fixture)
            self.assertEqual(target.read_bytes(), b"OWNER_EXISTING_BYTES")
            self.assertTrue(owner.owner.unknown)
            self.assertTrue(any(saved is owner for saved in D._PRIMARY_QUARANTINE))
            # The deliberately uncertain returned reader stays quarantined until
            # this one bounded offline process exits; do not retry/repair its row.

    def test_destination_replacement_after_write_fails_original_writer_pin(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            original = D._snapshot
            def replacement(control, group, directory):
                if group == "COPIED_PRIMARY":
                    target = directory.path / "member-00000.bin"
                    raw = target.read_bytes()
                    target.rename(directory.path / "discarded-original")
                    put(target, raw)
                    (directory.path / "discarded-original").unlink()
                return original(control, group, directory)
            with patch.object(D, "_snapshot", replacement), self.assertRaises(Exception):
                copy(owner, fixture)
            owner.finish()

    def test_destination_roster_addition_during_readback_is_refused(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            original, added = D._snapshot_reader, []
            def changed(control, snapshot, name):
                if snapshot.group == "COPIED_PRIMARY" and not added:
                    added.append(True)
                    put(snapshot.path / "unlisted.bin", b"x")
                return original(control, snapshot, name)
            with patch.object(D, "_snapshot_reader", changed), self.assertRaises(Exception):
                copy(owner, fixture)
            with self.assertRaises(Exception):
                owner.finish()

    def test_aggregate_counts_source_and_destination_not_content_deduplication(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            source_bytes = sum(len(raw) for raw in fixture.contents.values()) + len(fixture.primary.handoff_raw)
            with patch.object(D, "MAX_BYTES", source_bytes), self.assertRaises(Exception):
                copy(owner, fixture)
            self.assertEqual(list(fixture.path.iterdir()), [])
            owner.finish()

    def test_aggregate_includes_root_and_empty_directory_members(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            fixture = tiny(owner, Path(temp))
            with patch.object(D, "MAX_MEMBERS", 9), self.assertRaises(Exception):
                copy(owner, fixture)  # Source4 + handoff2 + destination4 ==10, not9.
            owner.finish()

    def test_preliminary_read_preserves_actual_empty_file(self):
        with models() as clock, tempfile.TemporaryDirectory(prefix="custody-primary-test-") as temp:
            owner = own(clock)
            root = Path(temp)
            put(root / "empty.bin", b"")
            private = D._private(owner, root)
            self.assertEqual(D._read_private(owner, private, "empty.bin", 1), b"")
            self.assertTrue(owner.ledger[-1]["closed"])
            owner.finish()


class FalseError(RuntimeError):
    def __bool__(self):
        return False


class Resource:
    def __init__(self, *, close_error=None, write_error=None, bool_write=False):
        self.closes, self.close_error, self.write_error, self.bool_write = 0, close_error, write_error, bool_write

    def close(self):
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error

    def write(self, raw):
        if self.write_error is not None:
            raise self.write_error
        return True if self.bool_write else len(raw)


class OwnershipAndBoundsTests(unittest.TestCase):
    def test_returned_resource_is_registered_before_post_return_callback(self):
        with models() as clock:
            owner, returned, observed = own(clock), Resource(), []
            def guard():
                if returned in owner.returned:
                    observed.append((owner.ledger[-1]["owner"] is returned, owner.rows[-1][2] is returned))
            clock.callback = guard
            self.assertIs(owner.acquire("reader", lambda: returned), returned)
            self.assertEqual(observed, [(True, True)])
            owner.finish()
            self.assertEqual(returned.closes, 1)

    def test_mutated_original_ledger_quarantines_actual_return(self):
        with models() as clock:
            owner, returned = own(clock), Resource()
            def changed():
                if returned in owner.returned:
                    owner.owner.resources = []
            clock.callback = changed
            with self.assertRaises(Exception):
                owner.acquire("reader", lambda: returned)
            self.assertTrue(owner.owner.unknown)
            self.assertIs(owner.returned[0], returned)
            self.assertEqual(returned.closes, 0)
            with self.assertRaises(Exception):
                owner.acquire("reader", lambda: Resource())

    def test_in_place_directory_row_erasure_retains_original_and_cannot_close_known(self):
        with models() as clock:
            owner, directory = own(clock), Resource()
            ledger, rows = owner.ledger, owner.rows
            def erase():
                if directory in owner.returned:
                    ledger.clear()
                    rows.clear()
            clock.callback = erase
            with self.assertRaises(Exception) as seen:
                owner.acquire("directory", lambda: directory)
            self.assertIs(owner.ledger, ledger)
            self.assertIs(owner.rows, rows)
            self.assertIs(owner.returned[0], directory)
            self.assertIs(owner._anchor().rows[0][2], directory)
            self.assertTrue(owner.owner.unknown)
            self.assertEqual(directory.closes, 0)
            with self.assertRaises(type(seen.exception)) as closed:
                owner.finish()
            self.assertIs(closed.exception, seen.exception)
            self.assertEqual(directory.closes, 0)
            self.assertTrue(any(value is owner for value in D._PRIMARY_QUARANTINE))
            self.assertEqual(ledger, [])  # Do not reconstruct a row to manufacture closure.

    def test_replaced_wrapper_binding_never_changes_original_owner(self):
        with models() as clock:
            owner, directory = own(clock), Resource()
            original, binding = owner.owner, owner._bound
            replacement = D.native.Owner(200.0, first=reading())
            def change():
                if directory in owner.returned:
                    owner._bound = (replacement, *binding[1:])
            clock.callback = change
            with self.assertRaises(Exception):
                owner.acquire("directory", lambda: directory)
            self.assertIs(owner.owner, original)
            self.assertIs(original.resources[0]["owner"], directory)
            self.assertTrue(original.unknown)
            self.assertEqual(replacement.resources, [])
            self.assertFalse(replacement.closed)
            with self.assertRaises(Exception):
                owner.finish()
            self.assertEqual(directory.closes, 0)

    def test_replaced_actual_native_dictionary_cannot_be_adopted(self):
        with models() as clock:
            owner, directory = own(clock), Resource()
            original_dictionary = owner.owner.__dict__
            def change():
                if directory in owner.returned:
                    owner.owner.__dict__ = dict(original_dictionary)
            clock.callback = change
            with self.assertRaises(Exception):
                owner.acquire("directory", lambda: directory)
            self.assertIs(owner._anchor().binding[1], original_dictionary)
            self.assertIs(owner._anchor().returned[0], directory)
            with self.assertRaises(Exception):
                owner.finish()
            self.assertEqual(directory.closes, 0)

    def test_first_falsey_failure_survives_later_directory_row_erasure(self):
        with models() as clock:
            owner, original = own(clock), FalseError("FIRST_DIRECTORY_FAILURE")
            directory = owner.acquire("directory", Resource)
            owner.remember(original)
            owner.ledger.clear()
            owner.rows.clear()
            with self.assertRaises(FalseError) as seen:
                owner.finish()
            self.assertIs(seen.exception, original)
            self.assertIs(owner._anchor().returned[0], directory)
            self.assertEqual(directory.closes, 0)
            with self.assertRaises(Exception):
                owner.finish()
            self.assertEqual(directory.closes, 0)

    def test_swallowed_allocation_reentry_is_sticky(self):
        with models() as clock:
            owner, nested = own(clock), []
            def reenter():
                if not nested:
                    nested.append(True)
                    try:
                        owner.acquire("reader", Resource)
                    except Exception:
                        pass
            clock.callback = reenter
            with self.assertRaises(Exception):
                owner.acquire("reader", Resource)
            self.assertIsNotNone(owner.failure)
            self.assertEqual(owner.returned, [])
            with self.assertRaises(Exception):
                owner.finish()

    def test_first_falsey_stream_failure_survives_unknown_close(self):
        with models() as clock:
            owner, original, secondary = own(clock), FalseError("ORIGINAL_FALSEY"), RuntimeError("SECONDARY_CLOSE")
            reader = owner.acquire("embedded-reader", lambda: io.BytesIO(b"x"))
            writer = owner.acquire("writer", lambda: Resource(write_error=original, close_error=secondary))
            with self.assertRaises(FalseError) as seen:
                D._consume(owner, reader, 1, sha(b"x"), lambda: None, writer=writer)
            self.assertIs(seen.exception, original)
            self.assertIs(owner.failure, original)
            self.assertIs(owner.owner.original, original)
            self.assertTrue(owner.owner.unknown)
            self.assertEqual(writer.closes, 1)
            with self.assertRaises(FalseError):
                owner.close_one(writer)
            self.assertEqual(writer.closes, 1)

    def test_exact_eof_refuses_extra_byte_and_closes_reader(self):
        with models() as clock:
            owner = own(clock)
            reader = owner.acquire("embedded-reader", lambda: io.BytesIO(b"xx"))
            with self.assertRaises(Exception):
                D._consume(owner, reader, 1, sha(b"x"), lambda: None)
            self.assertTrue(reader.closed)
            self.assertFalse(owner.owner.unknown)
            with self.assertRaises(Exception):
                owner.finish()

    def test_short_read_refuses_and_closes_reader(self):
        with models() as clock:
            owner = own(clock)
            reader = owner.acquire("embedded-reader", lambda: io.BytesIO(b""))
            with self.assertRaises(Exception):
                D._consume(owner, reader, 1, sha(b"x"), lambda: None)
            self.assertTrue(reader.closed)
            with self.assertRaises(Exception):
                owner.finish()

    def test_boolean_write_count_is_not_one_written_byte(self):
        with models() as clock:
            owner = own(clock)
            reader = owner.acquire("embedded-reader", lambda: io.BytesIO(b"x"))
            writer = owner.acquire("writer", lambda: Resource(bool_write=True))
            with self.assertRaises(Exception):
                D._consume(owner, reader, 1, sha(b"x"), lambda: None, writer=writer)
            self.assertTrue(reader.closed)
            self.assertEqual(writer.closes, 1)
            with self.assertRaises(Exception):
                owner.finish()

    def test_falsey_original_is_not_replaced_by_later_deadline(self):
        with models() as clock:
            owner, original = own(clock), FalseError("FIRST")
            resource = owner.acquire("reader", Resource)
            owner.remember(original)
            clock.local = 200.0
            with self.assertRaises(FalseError) as seen:
                owner.finish()
            self.assertIs(seen.exception, original)
            self.assertEqual(resource.closes, 1)
            self.assertTrue(owner.owner.closed)
            self.assertFalse(owner.owner.unknown)

    def test_member_name_is_only_fixed_ordinal_and_never_metadata(self):
        self.assertEqual(D._member_name(0), "member-00000.bin")
        self.assertEqual(D._member_name(9999), "member-09999.bin")
        for value in (-1, 10000, True, "../victim", "P/file", 0.0):
            with self.subTest(value=value), self.assertRaises(Exception):
                D._member_name(value)

    def test_attempt_reentry_invalidates_original_without_allocating(self):
        with patch.dict(D._PRIMARY_ATTEMPTS, {}, clear=True):
            original = D._begin_primary("gate")
            with self.assertRaises(Exception):
                D._begin_primary("gate")
            self.assertEqual(original["state"], "FAILED")
            self.assertIsNotNone(original["failure"])
            self.assertEqual(original["owners"], [])

    def test_unregistered_primary_copy_cannot_become_authentic_return(self):
        supplied = D.PrimaryCopy(None, None, b"{}\n", None, b"{}\n", (), b"{}\n", b"{}\n")
        with self.assertRaises(Exception):
            D.checked_primary(supplied)


def actual_model():
    env = {D.PRIMARY_OUTCOME: "success", D.PRIMARY_RESULT: "1" * 64, D.PRIMARY_HANDOFF: "2" * 64}
    return env, tuple(env.get(name) for name in D._ACTUAL_NAMES)


class PreliminaryAndWindowsModels(unittest.TestCase):
    def test_actual_step_digest_and_credential_models_fail_closed(self):
        env, values = actual_model()
        with patch.dict(os.environ, env, clear=True):
            D._actual_inputs(values)  # Supplied environment only, not real GitHub Step authentication.
            for key, value in ((D.PRIMARY_OUTCOME, "failure"), (D.PRIMARY_HANDOFF, "f" * 64), ("GH_TOKEN", "SYNTHETIC_NOT_A_CREDENTIAL")):
                with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(Exception):
                    D._actual_inputs(values)

    def test_preliminary_local_thirty_is_absolute_not_restarted(self):
        env, values = actual_model()
        with models() as clock, patch.dict(os.environ, env, clear=True):
            pre = D._Preliminary(reading(), 100.0, BOOT, values, lambda: None)
            self.assertEqual(pre.observe(), 60 * NS)
            clock.local = 130.0
            with self.assertRaises(Exception):
                pre.observe()
            clock.local = 100.0
            with self.assertRaises(Exception):
                pre.observe()

    def test_preliminary_raw_thirty_is_absolute_and_sticky(self):
        env, values = actual_model()
        with models() as clock, patch.dict(os.environ, env, clear=True):
            pre = D._Preliminary(reading(), 100.0, BOOT, values, lambda: None)
            clock.raw = 80 * NS
            with self.assertRaises(Exception):
                pre.observe()
            clock.raw = 60 * NS
            with self.assertRaises(Exception):
                pre.observe()

    def test_preliminary_keeps_known_close_raw_instead_of_earlier_first(self):
        env, values = actual_model()
        with models() as clock, patch.dict(os.environ, env, clear=True):
            pre = D._Preliminary(reading(), 100.0, BOOT, values, lambda: None)
            owner = D._PrimaryOwner(D.native.Owner(pre.end, first=pre.bound[0], cancelled=pre.observe))
            pre.bind_owner(owner)
            owner.acquire("reader", Resource)
            clock.raw = 65 * NS
            owner.finish()
            clock.raw = 64 * NS
            with self.assertRaisesRegex(RuntimeError, "SUPPLIED_RAW_BACKWARDS"):
                pre.observe()
            self.assertEqual(pre.last, 65 * NS)

    def test_preliminary_first_and_cap_are_readonly_originals(self):
        env, values = actual_model()
        with models(), patch.dict(os.environ, env, clear=True):
            first = reading()
            pre = D._Preliminary(first, 100.0, BOOT, values, lambda: None)
            original = pre.bound
            for field, changed in (("bound", (dataclasses.replace(first, nanoseconds=75 * NS), *original[1:])),
                    ("end", 160.0), ("owner", object())):
                with self.subTest(field=field), self.assertRaises(AttributeError):
                    setattr(pre, field, changed)
            self.assertIs(pre.bound, original)
            self.assertIs(pre.bound[0], first)
            self.assertLessEqual(pre.end, 130.0)

    def test_preliminary_callback_first_substitution_cannot_renew_original_thirty(self):
        env, values = actual_model()
        with models() as clock, patch.dict(os.environ, env, clear=True):
            first = reading()
            pre = D._Preliminary(first, 100.0, BOOT, values, clock.cancelled)
            original = pre.bound
            def substitute():
                pre._bound = (dataclasses.replace(first, nanoseconds=75 * NS), *original[1:])
            clock.callback = substitute
            with self.assertRaises(Exception) as seen:
                pre.observe()
            self.assertIs(pre.bound, original)
            self.assertIs(pre.bound[0], first)
            clock.local, clock.raw = 115.0, 85 * NS
            with self.assertRaises(type(seen.exception)) as later:
                pre.observe()
            self.assertIs(later.exception, seen.exception)
            self.assertLessEqual(pre.end, 130.0)

    def test_preliminary_callback_local_boot_environment_or_cancellation_replacement_refuses(self):
        env, values = actual_model()
        for index, changed in ((1, 120.0), (2, "b" * 64), (3, ("other",)), (4, lambda: None)):
            with self.subTest(index=index), models() as clock, patch.dict(os.environ, env, clear=True):
                pre = D._Preliminary(reading(), 100.0, BOOT, values, clock.cancelled)
                binding = pre.bound
                clock.callback = lambda: setattr(pre, "_bound", (*binding[:index], changed, *binding[index + 1:]))
                with self.assertRaises(Exception):
                    pre.observe()
                self.assertIs(pre.bound, binding)

    def test_preliminary_cannot_replace_its_once_bound_original_owner(self):
        env, values = actual_model()
        with models(), patch.dict(os.environ, env, clear=True):
            pre = D._Preliminary(reading(), 100.0, BOOT, values, lambda: None)
            original = D._PrimaryOwner(D.native.Owner(pre.end, first=pre.bound[0], cancelled=pre.observe))
            replacement = D._PrimaryOwner(D.native.Owner(pre.end, first=pre.bound[0], cancelled=pre.observe))
            pre.bind_owner(original)
            with self.assertRaises(Exception):
                pre.bind_owner(replacement)
            self.assertIs(pre.owner, original)
            self.assertIs(pre._anchor().owner_anchor, original._anchor())

    def test_preliminary_original_reading_graph_mutation_refuses(self):
        env, values = actual_model()
        with models(), patch.dict(os.environ, env, clear=True):
            first = reading()
            pre = D._Preliminary(first, 100.0, BOOT, values, lambda: None)
            object.__setattr__(first, "nanoseconds", 75 * NS)
            with self.assertRaises(Exception):
                pre.observe()

    def test_windows_metadata_model_checks_identity_and_aliases_without_native_calls(self):
        info = D.native.windows.FileInfo
        directory = info((1, "1" * 32), True, 0, 1, 16, 0, 0, 0, "S-1-5-21-1", True)
        file = info((1, "2" * 32), False, 1, 1, 0, 0, 0, 0, "S-1-5-21-1", True)
        rows = D._snapshot_metadata({"": directory, "a.bin": file}, True)
        self.assertEqual(rows[1][2], (1, "2" * 32))
        D._written_matches(wire(file.as_dict()), rows[1], True)
        with self.assertRaises(Exception):
            D._snapshot_metadata({"": directory, "a.bin": dataclasses.replace(file, identity=directory.identity)}, True)
        with self.assertRaises(Exception):
            D._written_matches(wire(dataclasses.replace(file, change_100ns=1).as_dict()), rows[1], True)

    def test_windows_case_alias_model_is_refused(self):
        info = D.native.windows.FileInfo
        rows = {"": info((1, "1" * 32), True, 0, 1, 16, 0, 0, 0),
            "a.bin": info((1, "2" * 32), False, 0, 1, 0, 0, 0, 0),
            "A.bin": info((1, "3" * 32), False, 0, 1, 0, 0, 0, 0)}
        with self.assertRaises(Exception):
            D._snapshot_metadata(rows, True)


def armor(packets=b"\xc6\x01\x04"):
    return b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" + base64.b64encode(packets) + b"\n-----END PGP PUBLIC KEY BLOCK-----\n"


def crypto_model(*, windows=False, home_files=0):
    role = "windows-x64" if windows else "linux-x64"
    operations = tuple("gpg-" + (str(number) * 32 if windows else "model_" + str(number)) for number in range(1, 4 if windows else 3))
    result = "recipient-validation-result-" + "a" * 32 + ".json"
    packets, public = b"\xc6\x01\x04", armor()
    root_members = sorted(("gnupg", "tmp", "recipient.asc", "recipient.gpg", *operations, *((result,) if windows else ())))
    def identity(number):
        return (1, format(number, "032x")) if windows else (1, number)
    directories = [{"relative": "", "identity": list(identity(1)), "members": root_members},
        {"relative": "gnupg", "identity": list(identity(2)), "members": ["home-" + str(n).zfill(2) for n in range(home_files)]},
        {"relative": "tmp", "identity": list(identity(3)), "members": []}]
    content = {"recipient.asc": public, "recipient.gpg": packets}
    if windows:
        content[result] = b"SUPPLIED_RESULT"
    for number, name in enumerate(operations, 4):
        members = sorted(("stdout", "stderr") if windows else ("stdout", "stderr", "status", "process.json"))
        directories.append({"relative": name, "identity": list(identity(number)), "members": members})
        for leaf in members:
            content[name + "/" + leaf] = b""
    for leaf in directories[1]["members"]:
        content["gnupg/" + leaf] = b"x"
    rows = [{"relative": name, "bytes": len(raw), "sha256": sha(raw)} for name, raw in sorted(content.items())]
    inventory = {"directories": directories, "files": rows, "totalBytes": sum(row["bytes"] for row in rows)}
    pins = tuple(("R/crypto" + ("/" + row["relative"] if row["relative"] else ""), tuple(row["identity"]),
        "AUTHENTICATED_ORIGINAL_CRYPTO_NATIVE_PIN" if row["relative"] else "RECEIVER_READBACK_NATIVE_PIN") for row in directories)
    # _worker_file normalizes the declaration, not the enclosing per-file cap.
    files = tuple(("R/crypto/" + row["relative"], max(1, row["bytes"]), row["bytes"], row["sha256"],
        "AUTHENTICATED_CRYPTO_DECLARATION") for row in rows)
    primary = D.Primary("worker", role, b"SUPPLIED", b"SUPPLIED", (), pins, files, (), "a" * 64)
    context = {"directories": {"crypto": list(identity(1))}}
    child = {"recipient": {"work_identity": list(identity(1)), "key_sha256": sha(public)}}
    return SimpleNamespace(primary=primary, inventory=inventory, context=context, child=child, public=public, armor=public, ring=packets)


def check_crypto(value):
    return D._crypto_roster(value.primary, value.inventory, value.context, value.child, value.public, value.armor, value.ring)


def tail_model():
    clock = {"role": "linux-x64", "domain": D.O.clocks.DOMAINS["linux-x64"], "ticksPerSecond": NS}
    return ({"clock": clock, "readEndNs": 200, "readLocalCeiling": 150.0, "capturedNs": 100},
        {"readEndNs": 200, "readbackCompletedNs": 90},
        {"clock": clock, "readEndNs": 200, "readLocalCeiling": 150.0, "previousLocal": 100.0, "previousNs": 140, "retainedNs": 150},
        {"clock": clock, "readEndNs": 200, "readLocalCeiling": 150.0, "lowerLocal": 110.0, "lowerNs": 160},
        {"clock": clock, "firstNs": 170, "previousNs": 150}, {"clock": clock, "returnedNs": 110},
        {"retainedNs": 120}, {"preCloseNs": 130, "closedNs": 140})


class RetainedCryptoTests(unittest.TestCase):
    def test_ten_posix_files_shallow_public_packet_grammar_only(self):
        value = crypto_model()
        self.assertEqual(len(check_crypto(value)), 10)

    def test_nine_windows_files_empty_homes_are_supplied_grammar_only(self):
        value = crypto_model(windows=True)
        self.assertEqual(len(check_crypto(value)), 9)

    def test_windows_home_addition_refuses_even_consistent_index(self):
        value = crypto_model(windows=True, home_files=1)
        with self.assertRaises(Exception):
            check_crypto(value)

    def test_directory_identity_alias_refuses(self):
        value = crypto_model()
        value.inventory["directories"][1]["identity"] = value.inventory["directories"][0]["identity"]
        with self.assertRaises(Exception):
            check_crypto(value)

    def test_original_pin_mismatch_refuses(self):
        value = crypto_model()
        value.primary = dataclasses.replace(value.primary,
            directories=((value.primary.directories[0][0], (1, 999), value.primary.directories[0][2]), *value.primary.directories[1:]))
        with self.assertRaises(Exception):
            check_crypto(value)

    def test_extra_shallow_root_member_is_not_prefix_accepted(self):
        value = crypto_model()
        value.inventory["directories"][0]["members"].append("unlisted")
        value.inventory["directories"][0]["members"].sort()
        with self.assertRaises(Exception):
            check_crypto(value)

    def test_file_provenance_cannot_be_relabelled_to_actual_bytes(self):
        value = crypto_model()
        rows = list(value.primary.files)
        rows[0] = (*rows[0][:4], "ACTUAL_RETAINED_BYTES")
        value.primary = dataclasses.replace(value.primary, files=tuple(rows))
        with self.assertRaises(Exception):
            check_crypto(value)

    def test_duplicate_or_reordered_file_declaration_refuses(self):
        value = crypto_model()
        value.inventory["files"][1] = value.inventory["files"][0]
        with self.assertRaises(Exception):
            check_crypto(value)

    def test_declared_crypto_sixteen_mib_is_not_per_file_budget(self):
        value = crypto_model(home_files=9)
        for row in value.inventory["files"]:
            if row["relative"].startswith("gnupg/"):
                row["bytes"] = D.native.LIMIT
        value.inventory["totalBytes"] = sum(row["bytes"] for row in value.inventory["files"])
        rows = {row["relative"]: row for row in value.inventory["files"]}
        value.primary = dataclasses.replace(value.primary, files=tuple((key, max(1, rows[key.removeprefix("R/crypto/")]["bytes"]),
            rows[key.removeprefix("R/crypto/")]["bytes"], checksum, provenance)
            for key, _maximum, _count, checksum, provenance in value.primary.files))
        with self.assertRaisesRegex(Exception, "CRYPTO_BYTE_CAP"):
            check_crypto(value)

    def test_public_armor_cannot_be_changed_to_secret_packet(self):
        value = crypto_model()
        value.armor = armor(b"\xc5\x01\x04")
        with self.assertRaises(Exception):
            check_crypto(value)
        with self.assertRaises(Exception):
            D.native.posix._public_armor(value.armor)

    def test_ring_must_be_same_public_packets_not_just_nonempty(self):
        value = crypto_model()
        value.ring = b"DIFFERENT_RING"
        rows = value.inventory["files"]
        row = next(row for row in rows if row["relative"] == "recipient.gpg")
        row["bytes"], row["sha256"] = len(value.ring), sha(value.ring)
        value.inventory["totalBytes"] = sum(row["bytes"] for row in rows)
        value.primary = dataclasses.replace(value.primary, files=tuple((key,
            max(1, len(value.ring)) if key == "R/crypto/recipient.gpg" else maximum,
            len(value.ring) if key == "R/crypto/recipient.gpg" else count,
            sha(value.ring) if key == "R/crypto/recipient.gpg" else checksum, provenance)
            for key, maximum, count, checksum, provenance in value.primary.files))
        with self.assertRaisesRegex(Exception, "CRYPTO_PUBLIC_ONLY_RING"):
            check_crypto(value)

    def test_retained_tail_explicitly_cannot_reconstruct_missing_first_local(self):
        values = tail_model()
        self.assertNotIn("local_start", values[4])
        self.assertEqual(D._retained_crypto_tail(*values), "NOT_INDEPENDENTLY_RECONSTRUCTIBLE")

    def test_retained_tail_reordered_capture_or_expired_lower_refuses(self):
        for target, field, changed in ((0, "capturedNs", 111), (3, "lowerNs", 200), (4, "firstNs", 159)):
            values = tail_model()
            values[target][field] = changed
            with self.subTest(field=field), self.assertRaises(Exception):
                D._retained_crypto_tail(*values)

    def test_retained_tail_local_ceiling_and_clock_are_closed(self):
        for target, field, changed in ((0, "readLocalCeiling", 150), (2, "previousLocal", 111.0),
                (3, "lowerLocal", float("nan")), (5, "clock", {"supplied": "OTHER_CLOCK"})):
            values = tail_model()
            values[target][field] = changed
            with self.subTest(field=field), self.assertRaises(Exception):
                D._retained_crypto_tail(*values)


def timestamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def supplied_phase(context_raw, path, clock, *, invocation, start, work, final, minimum, child,
        completed, finalized, recipient=False):
    """Supplied POSIX record grammar only: no real PID/launch/retirement claim."""
    context = json.loads(context_raw)
    interpreter = str(Path(sys.executable).resolve(strict=True))
    command = [interpreter, "-I", "-B", "-S", str(ROOT / "scripts/run-hosted-initial-recipient.py"),
        "_recipient" if recipient else "_service", "--context-sha256", sha(context_raw)]
    launch = command + ["--minimum-ns", str(minimum)]
    inherited = D.native.processes.ownership_environment({}, context["job"], invocation,
        str(path), str(path / "control-home"), allow_new_context=True)
    beginning = {"schema": 1, "scope": D.N.RECIPIENT_START_SCOPE if recipient else D.native.PHASE_SCOPE,
        "contextSha256": sha(context_raw), "argv": command, "cwd": str(ROOT), "role": "linux-x64",
        "job": context["job"], "invocation": invocation, "state": str(path), "home": str(path / "control-home"),
        "inheritedContext": {key: inherited[key] for key in D.Q._CONTEXT}, "startedNs": start,
        "workEndNs": work, "finalEndNs": final, "exitCode": None, "launchAttempted": False,
        "scopeAttempted": False, "retirement": "UNKNOWN"}
    first_raw = wire(beginning)
    child = {"schema": 1, "scope": D.N.RECIPIENT_CHILD_SCOPE if recipient else D.N.CHILD_SCOPE,
        "contextSha256": sha(context_raw), "startSha256": sha(first_raw), "invocation": invocation,
        "clock": clock, "launchMinimumNs": minimum, **child}
    child_raw = wire(child)
    leader, preparer = {"pid": 501, "startTicks": 601}, {"pid": 502, "startTicks": 602}
    ownership = {"backend": D.native.BACKENDS["linux-x64"], "job": context["job"], "invocation": invocation,
        "scope": "controlled-marker-inheriting-descendants", "discoveryErrors": [], "discoveryReconciliations": [],
        "launches": [{"created": True, "requestedArgv": launch, "resolvedArgv": launch, "cwd": str(ROOT),
            "pid": leader["pid"], "api": "subprocess.Popen", "shell": False, "executable": interpreter,
            "outputMode": "caller-owned-files"}], "startedIdentities": [leader]}
    records = {"start.json": first_raw, "baseline.json": wire({"role": "linux-x64", "baseline": [], "kernelJob": False}),
        "native-start.json": wire({"ownership": ownership, "leader": leader,
            "preparerIdentity": preparer, "observedNs": minimum}), "stderr.log": b"",
        "stdout.log": wire({"schema": 1,
            "scope": D.native.INITIAL_RECIPIENT_ACK_SCOPE if recipient else D.native.INITIAL_ACK_SCOPE,
            "invocation": invocation, "terminalSha256": sha(child_raw), "clock": clock,
            "closedNs": child["completedNs"] + NS})}
    terminal = {**beginning, "exitCode": 0, "launchAttempted": True, "scopeAttempted": True,
        "retirement": "KNOWN", "launchMinimumNs": minimum, "launchArgv": launch, "leader": leader,
        "ownership": ownership, "preparerIdentity": preparer, "scopeCloseAttempted": True, "scopeClosed": True,
        "completedNs": completed, "finalizedNs": finalized, "survivors": [], "errors": [],
        "nativeStartSha256": sha(records["native-start.json"]), "baselineSha256": sha(records["baseline.json"]),
        "captureOutcomes": {name: {key: True for key in ("synced", "verified", "closeAttempted", "closed", "readback")}
            for name in ("stdout", "stderr")},
        "captures": {name: {"sha256": sha(records[name + ".log"]), "bytes": len(records[name + ".log"])}
            for name in ("stdout", "stderr")}}
    if recipient:
        terminal.update(finalStartedNs=1053 * NS, finalEndNs=min(final, 1098 * NS),
            readStartedNs=1055 * NS, readEndNs=1085 * NS, readbackCompletedNs=1055 * NS)
    records["result.json"] = wire(terminal)
    return records, child_raw


class SuppliedHistory:
    """Coherent NEW byte fixture, not an authentic carrier or live old registry.

    Maintained pure policy/HTTP/match/identity/native/frame parsers are not mocked.
    Hash-bound query/authority session payloads are explicit opaque supplied bytes:
    this checker does not claim their native execution/retirement qualification.
    No full281/1361 inventory or successful Step is inferred from these Primary
    data values; primary_record is a separate caller-model boundary below.
    """
    def __init__(self, kind):
        self.kind, self.raw, self.special, self.pins = kind, {}, {}, {}
        self.clock = reading().clock
        self.clock_value = D.O.clock_value(self.clock)
        self.interpreter = str(Path(sys.executable).resolve(strict=True))
        self.roots = {key: Path("/SUPPLIED-CUSTODY-HISTORY") / key for key in
            (("P",) if kind == "gate" else ("P", "E", "R", "S", "I", "T", "C"))}
        self.policy_raw = (ROOT / ".github/test-evidence-recipient.json").read_bytes()  # Checked-in PUBLIC policy only.
        self.policy = json.loads(self.policy_raw)
        assert sha(self.policy_raw) == D.A.stages.POLICY_SHA256
        self.use = self.policy["notBefore"] + 120
        self.source = {"commit": "1" * 40, "tree": "2" * 40}
        self.selection, self.invocation = "desktop-linux-x64", "3" * 32
        self.run, self.attempt = "7001", "1"
        self.event = wire({"repository": {"full_name": D.I.REPOSITORY, "default_branch": "main"},
            "ref": D.A.stages.SOURCE_REF, "inputs": {"selection": self.selection,
                "expected_sha": self.source["commit"], "expected_tree": self.source["tree"]}})
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": D.I.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": D.A.stages.SOURCE_REF, "GITHUB_SHA": self.source["commit"],
            "GITHUB_WORKFLOW_SHA": self.source["commit"], "GITHUB_WORKFLOW_REF": D.I.REPOSITORY + "/" +
                D.A.stages.bootstrap.WORKFLOW + "@" + D.A.stages.SOURCE_REF,
            "GITHUB_RUN_ID": self.run, "GITHUB_RUN_ATTEMPT": self.attempt, "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "RUNNER_NAME": "SUPPLIED-OFFLINE-RUNNER", "GITHUB_JOB": D.A.gate.JOB if kind == "gate" else D.A.stages.bootstrap.JOB}
        self.observed = D.A._context(env, self.event, kind, self.use)
        owner = {"login": D.A.stages.joint.OWNER_LOGIN, "id": D.A.stages.joint.OWNER_ID, "type": "User"}
        environment = {"name": D.A.stages.ENVIRONMENT, "id": 8100, "branchPolicies": [
            {"id": 8101 + number, "name": name, "type": "branch"} for number, name in enumerate(D.A.stages.BRANCHES)]}
        declaration = {"schema": 1, "scope": D.A.stages.STAGE1, "repository": D.I.REPOSITORY,
            "base": D.A.stages.BASE, "reviewed": self.source, "sourceRef": D.A.stages.SOURCE_REF,
            "policySha256": D.A.stages.POLICY_SHA256, "notBefore": self.policy["notBefore"],
            "expiresAt": self.policy["expiresAt"], "environment": environment,
            "bootstrap": [{"selection": self.selection, "runId": self.run, "runAttempt": self.attempt}]}
        body = D.A.stages.COMMANDS[D.A.stages.STAGE1] + wire(declaration).decode("ascii").removesuffix("\n")
        api, web, comment_id = D.O.wire.ORIGIN + D.A.API, "https://github.com/" + D.I.REPOSITORY, 8200
        comment = wire({"id": comment_id, "url": api + "/issues/comments/8200", "issue_url": api + "/issues/437",
            "html_url": web + "/issues/437#issuecomment-8200", "user": owner, "performed_via_github_app": None,
            "created_at": timestamp(self.use - 30), "updated_at": timestamp(self.use - 30), "body": body})
        approvals = wire([{"state": "approved", "user": owner, "environments": [{"name": environment["name"], "id": 8100}],
            "comment": "AUTHORIZE_INITIAL_RECIPIENT stage1 " + self.run + "/1 8200 " + sha(body.encode("ascii"))}])
        env_raw = wire({"id": 8100, "name": environment["name"], "can_admins_bypass": False,
            "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
            "protection_rules": [{"type": "branch_policy"}, {"type": "required_reviewers", "prevent_self_review": False,
                "reviewers": [{"type": "User", "reviewer": owner}]}]})
        branches = wire({"total_count": 2, "branch_policies": environment["branchPolicies"]})
        blob = hashlib.sha1(b"blob " + str(len(self.policy_raw)).encode("ascii") + b"\0" + self.policy_raw).hexdigest()
        self.originals = {"event": self.event, "base_policy_entry": b"",
            "ancestry_raw": D.A.stages.BASE["commit"].encode("ascii") + b"\n",
            "candidate_policy_entry": b"100644 blob " + blob.encode("ascii") + b"\t" + D.I.POLICY_PATH.encode("ascii") + b"\0",
            "candidate_policy_raw": self.policy_raw}
        observation = {"repository": D.I.REPOSITORY, "base": D.A.stages.BASE, "reviewed": self.source,
            "source": self.source, "firstUseAt": self.use, "github": dict(self.observed["github"])}
        match_args = {name: self.originals[name] for name in D.N.SOURCE_KEYS}
        if kind == "gate":
            observation["inputs"] = self.observed["inputs"]
            self.match = D.A.gate.eligible(stage="stage1", approvals_raw=approvals, comment_raw=comment,
                environment_raw=env_raw, branches_raw=branches, observation_raw=wire(observation), now=self.use, **match_args)
        else:
            observation["github"].update(profile=D.A.stages.bootstrap.PROFILE, selection=self.selection)
            self.match = D.A.stages.match_bootstrap(comment_raw=comment, comment_id=comment_id,
                body_sha256=sha(body.encode("ascii")), observation_raw=wire(observation), now=self.use, **match_args)
        branch = D.A.stages.SOURCE_REF.removeprefix("refs/heads/")
        run = {"id": int(self.run), "run_attempt": 1, "repository": {"full_name": D.I.REPOSITORY},
            "head_repository": {"full_name": D.I.REPOSITORY}, "path": D.A.stages.bootstrap.WORKFLOW,
            "event": "workflow_dispatch", "head_sha": self.source["commit"], "head_branch": branch,
            "status": "in_progress", "conclusion": None, "pull_requests": [],
            "created_at": timestamp(self.use - 5), "run_started_at": timestamp(self.use - 4)}
        self.job = {"id": 8300, "name": env["GITHUB_JOB"], "run_id": int(self.run), "run_attempt": 1,
            "head_sha": self.source["commit"], "head_branch": branch, "url": api + "/actions/jobs/8300",
            "run_url": api + "/actions/runs/" + self.run, "status": "in_progress", "conclusion": None,
            "completed_at": None, "started_at": timestamp(self.use - 1), "runner_name": env["RUNNER_NAME"],
            "runner_id": 8400, "labels": [D.A.GATE_SELECTOR if kind == "gate" else D.O.SERVICE_SELECTORS["linux-x64"]],
            "runner_group_id": 0, "runner_group_name": "GitHub Actions"}
        jobs = [self.job]
        if kind == "worker":
            jobs.append({**self.job, "id": 8299, "name": D.A.gate.JOB, "url": api + "/actions/jobs/8299",
                "status": "completed", "conclusion": "success", "labels": [D.A.GATE_SELECTOR],
                "started_at": timestamp(self.use - 3), "completed_at": timestamp(self.use - 2)})
        run_path = D.A.API + "/actions/runs/" + self.run
        def ref(name, commit):
            return wire({"ref": "refs/heads/" + name, "url": api + "/git/refs/heads/" + name,
                "object": {"type": "commit", "sha": commit, "url": api + "/git/commits/" + commit}})
        bodies = (("attempt", run_path + "/attempts/1", wire(run)),
            ("jobs", run_path + "/attempts/1/jobs?per_page=100&page=1", wire({"total_count": len(jobs), "jobs": jobs})),
            ("approvals", run_path + "/approvals", approvals), ("comment", D.A.API + "/issues/comments/8200", comment),
            ("environment", D.A.API + "/environments/" + environment["name"], env_raw),
            ("branches", D.A.API + "/environments/" + environment["name"] + "/deployment-branch-policies?per_page=100&page=1", branches),
            ("main", D.A.API + "/git/ref/heads/main", ref("main", D.A.stages.BASE["commit"])),
            ("reviewed_ref", D.A.API + "/git/ref/heads/" + branch, ref(branch, self.source["commit"])))
        for number, (name, path, data) in enumerate(bodies):
            date = format_datetime(datetime.fromtimestamp(self.use, timezone.utc), usegmt=True)
            header = ("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: private, no-store\r\n"
                "X-GitHub-Api-Version-Selected: 2022-11-28\r\nX-GitHub-Request-Id: SUPPLIED-0001\r\nDate: " + date +
                "\r\nContent-Length: " + str(len(data)) + "\r\n\r\n").encode("ascii")
            self.originals[name] = wire({"schema": 1, "scope": D.O.RESPONSE_SCOPE, "origin": D.O.wire.ORIGIN,
                "method": "GET", "path": path, "invocation": self.invocation, "clock": self.clock_value,
                "startedNs": (1006 + number) * NS, "finishedNs": (1006 + number) * NS + NS // 4, "status": 200,
                "headersBase64": base64.b64encode(header).decode("ascii"), "bodyBase64": base64.b64encode(data).decode("ascii"),
                "complete": True, "retirement": "KNOWN", "error": None})
        self.originals.update(observation=wire(observation), match=self.match.record)
        for name in D.N.ORIGINAL_KEYS:
            self.keep("P/acquisition-queries/" + name + ".bin", self.originals[name])
        self.keep("P/acquisition-queries/session-result.json", b"SUPPLIED_QUERY_SESSION_NOT_NATIVE_PROOF\n")
        self.source_return("P/source-before", 1001 * NS)
        self.source_return("P/source-after", 1020 * NS)
        prelude = D.O.prelude(D.O.clocks.Reading(self.clock, 1000 * NS))
        self.keep("P/prelude.json", prelude)
        context = {"schema": 1, "scope": D.native.INITIAL_CONTEXT_SCOPE, "prelude": prelude,
            "observed": self.observed, "eventSha256": sha(self.event), "root": str(ROOT), "session": str(self.roots["P"]),
            "job": "4" * 32, "inheritedContext": {}, "sourceReturnSha256": self.hash("P/source-before/source-return.json"),
            "sourceReturnedNs": 1001 * NS, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.keep("P/context.json", context)
        phases, child = supplied_phase(self.raw["P/context.json"], self.roots["P"], self.clock_value,
            invocation=self.invocation, start=1002 * NS, work=1047 * NS, final=1092 * NS, minimum=1003 * NS,
            completed=1018 * NS, finalized=1019 * NS, child={"beganNs": 1004 * NS, "metadataLastNs": 1005 * NS,
                "acquiredNs": 1014 * NS, "queryReturnedNs": 1015 * NS, "completedNs": 1016 * NS,
                "querySessionSha256": self.hash("P/acquisition-queries/session-result.json"),
                "originalsSha256": {key: sha(raw) for key, raw in self.originals.items()},
                "matchSha256": sha(self.match.record), "retirement": "KNOWN", "errors": []})
        for name, raw in phases.items():
            self.keep("P/service/" + name, raw)
        self.keep("P/service/child-result.json", child)
        pending = {"schema": 1, "scope": D.N.RESULT_SCOPE, "contextSha256": self.hash("P/context.json"),
            "sourceBeforeSha256": self.hash("P/source-before/source-return.json"),
            "sourceAfterSha256": self.hash("P/source-after/source-return.json"), "matchSha256": sha(self.match.record),
            "originalChain": {"phaseSha256": {key: sha(raw) for key, raw in phases.items()}, "childSha256": sha(child),
                "querySessionSha256": self.hash("P/acquisition-queries/session-result.json"),
                "originalsSha256": {key: sha(raw) for key, raw in self.originals.items()}, "checkedNs": 1021 * NS},
            "retainedNs": 1022 * NS, "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED",
            "workerAdmission": "NOT_PERFORMED", "workerIdentitySha256": None, "serviceTimeBasisSha256": None,
            "allocationProposalSha256": None, "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False}
        self.embedded = ()
        self.index = {"source": self.source, "github": self.observed["github"]}
        self.handoff = {"scope": "SUPPLIED_HISTORY_ONLY_NOT_AUTHENTIC_HANDOFF"}
        if kind == "gate":
            self.keep("P/initial-result.json", pending)
            self.result = self.hash("P/initial-result.json")
            self.index.update(contextSha256=self.hash("P/context.json"), gateEligibilitySha256=sha(self.match.record),
                policy=json.loads(self.match.record)["policy"])
            self.handoff.update(gateEligibility=json.loads(self.match.record), originalClosedNs=1023 * NS,
                clock=self.clock_value, preludeSha256=self.hash("P/prelude.json"), bootDigest=BOOT)
        else:
            identity = D.N.initial_identity.bind_worker_match(self.match, event_raw=self.event,
                policy_raw=self.policy_raw, now=self.use)
            inputs = D.N._retained_match_inputs(context, self.originals, self.invocation,
                self.clock, 1002 * NS, 1047 * NS)
            self.service = inputs[2]
            basis, proposal = D.N._worker_time_values(identity, self.service, self.clock, self.invocation)
            self.keep("P/worker-identity.json", identity.record)
            self.keep("P/worker-service-time.json", basis)
            self.keep("P/worker-allocation-proposal.json", proposal)
            pending.update(workerIdentitySha256=sha(identity.record), serviceTimeBasisSha256=sha(basis),
                allocationProposalSha256=sha(proposal))
            self.keep("P/initial-result.json", pending)
            self.worker(identity, json.loads(proposal))

    def keep(self, name, value):
        self.raw[name] = value if type(value) is bytes else wire(value)
        if "/" in name:
            self.pin(name.rsplit("/", 1)[0])

    def pin(self, name):
        if name not in self.pins:
            self.pins[name] = ((17, 100 + len(self.pins)), "SUPPLIED_ORIGINAL_PIN")
        return self.pins[name][0]

    def hash(self, name):
        return sha(self.raw[name])

    def row(self, name):
        raw = self.raw[name]
        provenance = self.special.get(name, "ACTUAL_RETAINED_BYTES")
        return name, max(1, len(raw)), len(raw), sha(raw), provenance

    def source_return(self, prefix, returned):
        self.keep(prefix + "/session-result.json", b"SUPPLIED_SOURCE_SESSION_NOT_NATIVE_PROOF\n")
        for name in D.N.SOURCE_KEYS:
            self.keep(prefix + "/" + name + ".bin", self.originals[name])
        self.keep(prefix + "/source-return.json", {"schema": 1, "scope": D.N.SOURCE_SCOPE,
            "originalsSha256": {name: sha(self.originals[name]) for name in D.N.SOURCE_KEYS},
            "sessionSha256": self.hash(prefix + "/session-result.json"), "clock": self.clock_value, "returnedNs": returned})

    def authority_files(self, prefix):
        names = {name.removeprefix("P/") for name in D._history_names("gate")}
        names.difference_update(("prelude.json", "initial-result.json"))
        for name in sorted(names):
            self.keep(prefix + "/" + name, self.raw["P/" + name])
        self.keep(prefix + "/authority-window.json", {"scope": "SUPPLIED_AUTHORITY_WINDOW_LINK_ONLY"})
        names.add("authority-window.json")
        self.keep(prefix + "/authority-pending.json", {"scope": "SUPPLIED_AUTHORITY_PENDING_LINK_ONLY"})
        return {name: self.hash(prefix + "/" + name) for name in names}

    def authority_chain(self, prefix, checked):
        return {"phaseSha256": {name: self.hash(prefix + "/service/" + name) for name in D.native.PHASE_FILES},
            "childSha256": self.hash(prefix + "/service/child-result.json"),
            "querySessionSha256": self.hash(prefix + "/acquisition-queries/session-result.json"),
            "originalsSha256": {name: self.hash(prefix + "/acquisition-queries/" + name + ".bin") for name in D.N.ORIGINAL_KEYS},
            "checkedNs": checked}

    def worker(self, identity, proposal):
        identity_hash, proposal_hash = sha(identity.record), self.hash("P/worker-allocation-proposal.json")
        self.keep("S/readmission-return.json", {"scope": "SUPPLIED_READMISSION_HASH_LINK_NOT_NATIVE_RETURN"})
        fences = {key: proposal["phaseFencesNs"][key] for key in ("recipient-validation", "recipient-final", "recipient-read")}
        ends = tuple(min((1040 + seconds) * NS, fences[key], proposal["proposedJobEndNs"])
            for seconds, key in ((240, "recipient-validation"), (285, "recipient-final"), (315, "recipient-read")))
        frame = {"schema": 1, "scope": D.N.RECIPIENT_WINDOW_SCOPE, "clock": self.clock_value, "firstNs": 1040 * NS,
            "previousNs": 1039 * NS, "workEndNs": ends[0], "finalEndNs": ends[1], "readEndNs": ends[2],
            "firstUseAt": self.use, "originalReadmissionSha256": self.hash("S/readmission-return.json"),
            "workerIdentitySha256": identity_hash, "originalProposalSha256": proposal_hash, "originalFencesNs": fences,
            "originalProposedJobEndNs": proposal["proposedJobEndNs"], "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.keep("R/recipient-window.json", frame)
        for name, contents in (("worker-identity.json", identity.record), ("worker-match.json", self.match.record),
                ("worker-policy.json", self.policy_raw), ("worker-proposal.json", self.raw["P/worker-allocation-proposal.json"]),
                ("recipient-public.asc", identity.public_key)):
            self.keep("R/" + name, contents)
        authority = {"schema": 1, "scope": "INITIAL_RECIPIENT_USE_AUTHORITY_CLOSED_HISTORY_V1",
            "recipientWindowSha256": self.hash("R/recipient-window.json"),
            "originalReadmissionSha256": self.hash("S/readmission-return.json"), "workerIdentitySha256": identity_hash,
            "matchSha256": sha(self.match.record), "serviceTimeBasisSha256": self.hash("P/worker-service-time.json"),
            "originalProposalSha256": proposal_hash, "filesSha256": self.authority_files("R/authority"),
            "pendingSha256": self.hash("R/authority/authority-pending.json"),
            "originalChain": self.authority_chain("R/authority", 1041 * NS), "preCloseNs": 1041 * NS, "closedNs": 1042 * NS,
            "resourceCount": 7, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.keep("R/authority-return.json", authority)
        shallow = crypto_model()
        for name, pin, provenance in shallow.primary.directories:
            self.pins[name] = pin, provenance
        for name, _maximum, _count, _checksum, provenance in shallow.primary.files:
            value = identity.public_key if name.endswith("/recipient.asc") else (
                D.native.posix._public_armor(identity.public_key) if name.endswith("/recipient.gpg") else b"")
            self.keep(name, value)
            self.special[name] = provenance
        context = {"schema": 1, "scope": D.N.RECIPIENT_CONTEXT_SCOPE, "root": str(ROOT), "session": str(self.roots["R"]),
            "observed": self.observed, "eventSha256": sha(self.event), "inheritedContext": {}, "job": "5" * 32,
            "filesSha256": {name: self.hash("R/" + name) for name in D.N.RECIPIENT_FILES},
            "directories": {name: list(self.pin("R/" + name)) for name in D.N.RECIPIENT_DIRECTORIES},
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.keep("R/recipient-context.json", context)
        self.source_return("R/recipient-validation/source-before", 1047 * NS)
        self.source_return("R/recipient-validation/source-after", 1049 * NS)
        self.source_return("R/source-final", 1057 * NS)
        phases, child = supplied_phase(self.raw["R/recipient-context.json"], self.roots["R"], self.clock_value,
            invocation="6" * 32, start=1043 * NS, work=ends[0], final=ends[1], minimum=1044 * NS,
            completed=1052 * NS, finalized=1054 * NS, recipient=True, child={"beganNs": 1045 * NS, "metadataLastNs": 1046 * NS,
                "supplierReturnedNs": 1048 * NS, "completedNs": 1050 * NS, "identitySha256": identity_hash,
                "authoritySha256": self.hash("R/authority-return.json"),
                "sourceBeforeSha256": self.hash("R/recipient-validation/source-before/source-return.json"),
                "sourceAfterSha256": self.hash("R/recipient-validation/source-after/source-return.json"),
                "recipient": {"fingerprint": identity.fingerprint, "encryption_fingerprint": "A" * 40,
                    "expires_at": 0, "key_sha256": identity.key_sha256, "work_identity": list(self.pin("R/crypto")),
                    "executable": "/SUPPLIED-NOT-EXECUTED/gpg"}, "supplierReturned": True,
                "childResourceClose": "PENDING_CLOSE", "parentRetirement": "NOT_OBSERVED_HERE",
                "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        for name, raw in phases.items():
            self.keep("R/recipient-validation/" + name, raw)
        self.keep("R/recipient-validation/child-result.json", child)
        phase_hashes = {name: sha(contents) for name, contents in phases.items()}
        self.keep("R/recipient-pending.json", {"schema": 1, "scope": "INITIAL_RECIPIENT_VALIDATION_PENDING_OWNER_CLOSE_V1",
            "windowSha256": self.hash("R/recipient-window.json"), "contextSha256": self.hash("R/recipient-context.json"),
            "authoritySha256": self.hash("R/authority-return.json"), "phaseSha256": phase_hashes,
            "childSha256": sha(child), "sourceFinalSha256": self.hash("R/source-final/source-return.json"),
            "retainedNs": 1058 * NS, "retirement": "PENDING_OWNER_CLOSE", "liveRecipient": "NOT_TRANSFERRED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        self.keep("S/recipient-return.json", {"schema": 1, "scope": D.N.RECIPIENT_RETURN_SCOPE, "window": frame,
            "originalReadmissionSha256": self.hash("S/readmission-return.json"), "workerIdentitySha256": identity_hash,
            "authoritySha256": self.hash("R/authority-return.json"), "pendingSha256": self.hash("R/recipient-pending.json"),
            "preCloseNs": 1059 * NS, "closedNs": 1060 * NS, "resourceCount": 7, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
            "liveRecipient": "NOT_TRANSFERRED", "currentRemoteAuthority": "NOT_GRANTED_BY_HISTORY",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        self.keep("S/sender-pending.json", {"schema": 1, "scope": D.N.RECIPIENT_SENDER_SCOPE, "directory": str(self.roots["S"]),
            "directoryIdentity": list(self.pin("S")), "records": {name: {"bytes": len(self.raw["S/" + name]),
                "sha256": self.hash("S/" + name)} for name in ("readmission-return.json", "recipient-return.json")},
            "originalReferences": {"recipientSession": str(self.roots["R"]), "readmissionSession": str(self.roots["E"]),
                "scope": "PINNED_CONTEXT_REFERENCES_NOT_CURRENT_FILESYSTEM_OBSERVATIONS", "workerIdentitySha256": identity_hash,
                "serviceTimeBasisSha256": self.hash("P/worker-service-time.json"), "originalProposalSha256": proposal_hash},
            "readWindow": {"clock": self.clock_value, "previousNs": 1060 * NS, "previousLocal": 100.0,
                "readEndNs": 1085 * NS, "readLocalCeiling": 150.0, "retainedNs": 1061 * NS},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "originalStepOutcome": "NOT_OBSERVED",
            "completeOriginals": "NOT_ESTABLISHED_BY_THIS_BUNDLE", "liveRecipient": "NOT_TRANSFERRED",
            "currentRemoteAuthority": "NOT_GRANTED_BY_HISTORY", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        service_job = [self.job[key] for key in ("id", "started_at", "runner_name", "runner_id")]
        self.keep("T/step-pending.json", {"schema": 1, "scope": D.C.STEP_SCOPE, "directory": str(self.roots["T"]),
            "directoryIdentity": list(self.pin("T")), "senderSha256": self.hash("S/sender-pending.json"),
            "observed": self.observed, "serviceJob": service_job, "workerIdentitySha256": identity_hash,
            "originalProposalSha256": proposal_hash, "clock": self.clock_value, "bootSha256": BOOT,
            "lowerNs": 1062 * NS, "lowerLocal": 110.0, "readEndNs": 1085 * NS, "readLocalCeiling": 150.0,
            "sample": "AFTER_SENDER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        receiving = {"schema": 1, "scope": D.N.RECEIVING_WINDOW_SCOPE, "clock": self.clock_value, "firstNs": 1063 * NS,
            "previousNs": 1061 * NS, "workEndNs": min(1183 * NS, proposal["phaseFencesNs"]["canonical-init"], proposal["proposedJobEndNs"]),
            "firstUseAt": self.use, "senderSha256": self.hash("S/sender-pending.json"), "workerIdentitySha256": identity_hash,
            "originalProposalSha256": proposal_hash, "originalFencesNs": {key: proposal["phaseFencesNs"][key]
                for key in ("canonical-init", "canonical-init-final", "canonical-init-read")},
            "originalProposedJobEndNs": proposal["proposedJobEndNs"], "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.keep("I/receiving-window.json", receiving)
        crypto_rows = [{"relative": key.removeprefix("R/crypto/"), "bytes": len(raw), "sha256": sha(raw)}
            for key, raw in sorted(self.raw.items()) if key.startswith("R/crypto/")]
        inventory = {"schema": 1, "scope": D.N.CRYPTO_ORIGINALS_SCOPE, "root": str(self.roots["R"] / "crypto"),
            "contextSha256": self.hash("R/recipient-context.json"), "childSha256": sha(child), "phaseSha256": phase_hashes,
            "clock": self.clock_value, "readEndNs": 1085 * NS, "readLocalCeiling": 150.0, "capturedNs": 1056 * NS,
            "directories": shallow.inventory["directories"], "files": crypto_rows,
            "totalBytes": sum(row["bytes"] for row in crypto_rows), "copyState": "ORIGINAL_BYTES_NOT_COPIED",
            "liveRecipient": "NOT_TRANSFERRED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.keep("C/crypto-originals.json", {"schema": 1, "scope": D.N.CRYPTO_SIDECAR_SCOPE,
            "directory": str(self.roots["C"]), "directoryIdentity": list(self.pin("C")),
            "recipientValidationSha256": self.hash("S/recipient-return.json"), "recipientSenderSha256": self.hash("S/sender-pending.json"),
            "recipientStepSha256": self.hash("T/step-pending.json"), "inventory": inventory, "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        iauthority = {"schema": 1, "scope": "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_CLOSED_HISTORY_V1",
            "receivingWindowSha256": self.hash("I/receiving-window.json"), "senderSha256": self.hash("S/sender-pending.json"),
            "workerIdentitySha256": identity_hash, "matchSha256": sha(self.match.record), "originalProposalSha256": proposal_hash,
            "filesSha256": self.authority_files("I/authority"), "pendingSha256": self.hash("I/authority/authority-pending.json"),
            "originalChain": self.authority_chain("I/authority", 1064 * NS), "preCloseNs": 1065 * NS, "closedNs": 1066 * NS,
            "resourceCount": 7, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        iauthority_raw = wire(iauthority)
        self.keep("I/canonical-init/request.json", {"scope": "SUPPLIED_REQUEST_HASH_LINK_ONLY"})
        for name, contents in phases.items():
            self.keep("I/canonical-init/" + name, contents)
        self.keep("I/state/context.json", {"scope": "SUPPLIED_INITIALIZER_CONTEXT_HASH_LINK_ONLY"})
        self.keep("I/state/gradle-home/gradle.properties", b"# SUPPLIED; no Gradle invocation\n")
        self.keep("I/initializer-context.json", {"schema": 1, "scope": "INITIAL_RECIPIENT_CANONICAL_INITIALIZER_CONTEXT_V1",
            "job": "7" * 32, "receivingWindowSha256": self.hash("I/receiving-window.json"), "authoritySha256": sha(iauthority_raw),
            "senderSha256": self.hash("S/sender-pending.json"), "stepSha256": self.hash("T/step-pending.json"),
            "requestSha256": self.hash("I/canonical-init/request.json"), "workerIdentitySha256": identity_hash,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        original_names = ("I/receiving-window.json", "I/initializer-context.json",
            *("I/canonical-init/" + name for name in sorted(D.native.PHASE_FILES | {"request.json"})),
            "I/state/context.json", "I/state/gradle-home/gradle.properties")
        retained = []
        for name in original_names:
            parent, leaf = name.rsplit("/", 1)
            retained.append({"directory": str(self.roots["I"].joinpath(*parent.split("/")[1:])),
                "directoryIdentity": list(self.pin(parent)), "name": leaf, "bytes": len(self.raw[name]), "sha256": self.hash(name)})
        self.keep("I/initialization-pending.json", {"schema": 1, "scope": "INITIAL_RECIPIENT_CANONICAL_INITIALIZATION_PENDING_OWNER_CLOSE_V1",
            "window": receiving, "stepSha256": self.hash("T/step-pending.json"), "authoritySha256": sha(iauthority_raw),
            "originals": retained, "retainedNs": 1066 * NS, "retainedLocal": 120.0,
            "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT", "ownerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        self.result = self.hash("I/initialization-pending.json")
        closed = {"schema": 1, "scope": "INITIAL_RECIPIENT_CLOSED_INITIALIZATION_HISTORY_V1", "pendingSha256": self.result,
            "closedNs": 1067 * NS, "closedLocal": 121.0, "resourceCount": 7, "ownerReturn": "KNOWN_RESOURCE_CLOSE_ONLY",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.embedded = (("receiving-authority-return.json", iauthority_raw), ("initialization-history.json", wire(closed)))
        self.index.update(clock=self.clock_value, workerIdentitySha256=identity_hash,
            senderSha256=self.hash("S/sender-pending.json"), recipientStepSha256=self.hash("T/step-pending.json"),
            recipientCryptoOriginalsSha256=self.hash("C/crypto-originals.json"), initializationSha256=self.result,
            authoritySha256=sha(iauthority_raw))

    def primary(self):
        return D.Primary(self.kind, "linux-x64", wire(self.handoff), wire(self.index), tuple(self.roots.items()),
            tuple((key, pin, provenance) for key, (pin, provenance) in sorted(self.pins.items())),
            tuple(self.row(name) for name in sorted(self.raw)), self.embedded, self.result)

    def history(self):
        return D.primary_history(self.primary(), {name: self.raw[name] for name in D._history_names(self.kind)},
            self.observed, self.event, self.clock, self.interpreter)

    def crypto(self, historical):
        return D.crypto_history(self.primary(), {name: self.raw[name] for name in D._crypto_names()}, historical, self.interpreter)


@contextmanager
def pure_histories_only():
    """No old reader/owner/clock/authority reconstruction, even by accident."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("HISTORICAL_MODEL_MUST_NOT_READ_CURRENT_CLOCK_OR_RESTORE_OLD_OWNER")
    with ExitStack() as stack:
        for module, name in ((D.time, "time"), (D.time, "monotonic"), (D.O.clocks, "observe"),
                (D.O.clocks, "checked_now"), (D.native, "Owner"), (D.N, "_ReceivingWindow"),
                (D.N, "_read_initial_recipient_originals"), (D.N, "_worker_crypto_index")):
            stack.enter_context(patch.object(module, name, forbidden))
        yield


class CentralHistoricalByteTests(unittest.TestCase):
    def test_gate_primary_history_uses_original_first_use_and_jobs_request_start(self):
        with pure_histories_only():
            fixture = SuppliedHistory("gate")
            value = json.loads(fixture.history())
        self.assertEqual(value["observed"], fixture.observed)
        self.assertEqual(value["observed"]["source"], fixture.source)
        self.assertEqual(value["observed"]["github"]["job"], D.A.gate.JOB)
        self.assertEqual(value["observed"]["inputs"]["selection"], fixture.selection)
        self.assertEqual(value["firstUseAt"], fixture.use)
        self.assertEqual(value["matchSha256"], sha(fixture.match.record))
        self.assertEqual((value["originalBootDigest"], value["originalPreviousNs"]), (BOOT, 1023 * NS))
        self.assertEqual(value["originalJobBasisNs"], (1007 - 1 - 1 - 60 - 5) * NS)
        self.assertEqual(value["serviceArithmetic"]["jobsRequestStartedNs"], 1007 * NS)
        self.assertNotEqual(value["originalJobBasisNs"],
            json.loads(fixture.originals["jobs"])["finishedNs"] - value["serviceArithmetic"]["chargedAgeNs"])
        self.assertEqual(value["serviceJob"], [fixture.job[name] for name in ("id", "started_at", "runner_name", "runner_id")])
        self.assertEqual(value["originalLocalScope"], "NO_SERIALIZED_LOCAL_ADOPTION")
        self.assertEqual(value["currentAuthority"], "NOT_ACQUIRED")
        self.assertIs(value["exportSaveAuthority"], False)

    def test_worker_primary_history_links_identity_basis_step_and_missing_original_local(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            value = json.loads(fixture.history())
        self.assertEqual(value["observed"], fixture.observed)
        self.assertEqual(value["observed"]["github"]["job"], D.A.stages.bootstrap.JOB)
        self.assertEqual(value["observed"]["inputs"]["selection"], fixture.selection)
        self.assertEqual(value["matchSha256"], fixture.hash("R/worker-match.json"))
        self.assertEqual((value["originalBootDigest"], value["originalPreviousNs"], value["firstUseAt"]), (BOOT, 1067 * NS, fixture.use))
        self.assertEqual(value["originalJobBasisNs"], json.loads(fixture.raw["P/worker-service-time.json"])["jobStartBasisNs"])
        self.assertEqual(value["originalJobBasisNs"], 940 * NS)
        self.assertEqual(value["serviceJob"][0], 8300)
        self.assertEqual(value["originalLocalScope"], "ORIGINAL_RECEIVING_FIRST_LOCAL_NOT_INDEPENDENTLY_RECONSTRUCTIBLE")
        self.assertNotIn("local_start", json.loads(fixture.raw["I/receiving-window.json"]))
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")

    def test_historical_gate_and_worker_changed_source_refuse_even_reindexed_bytes(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), pure_histories_only():
                fixture = SuppliedHistory(kind)
                original = json.loads(fixture.raw["P/source-after/source-return.json"])
                original["originalsSha256"]["ancestry_raw"] = "f" * 64
                fixture.keep("P/source-after/source-return.json", original)
                with self.assertRaisesRegex(Exception, "HISTORY_SOURCE"):
                    fixture.history()

    def test_historical_bytes_without_original_index_hash_refuse(self):
        with pure_histories_only():
            fixture = SuppliedHistory("gate")
            primary = fixture.primary()
            raw = {name: fixture.raw[name] for name in D._history_names("gate")}
            raw["P/acquisition-queries/match.bin"] += b" "
            with self.assertRaisesRegex(Exception, "HISTORY_BYTES"):
                D.primary_history(primary, raw, fixture.observed, fixture.event, fixture.clock, fixture.interpreter)

    def test_historical_changed_match_cannot_be_reapproved_by_current_wall_time(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            match = json.loads(fixture.raw["P/acquisition-queries/match.bin"])
            match["firstUseAt"] += 1
            fixture.keep("P/acquisition-queries/match.bin", match)
            with self.assertRaisesRegex(Exception, "CHANGED_BEFORE_RECHECK"):
                fixture.history()

    def test_historical_changed_prelude_frame_refuses(self):
        with pure_histories_only():
            fixture = SuppliedHistory("gate")
            prelude = json.loads(fixture.raw["P/prelude.json"])
            prelude["workEndNs"] += NS
            fixture.keep("P/prelude.json", prelude)
            with self.assertRaisesRegex(Exception, "PRELUDE_CHANGED"):
                fixture.history()

    def test_historical_worker_changed_step_job_refuses(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            step = json.loads(fixture.raw["T/step-pending.json"])
            step["serviceJob"][0] += 1
            fixture.keep("T/step-pending.json", step)
            with self.assertRaisesRegex(Exception, "HISTORY_RECEIVING_BINDINGS"):
                fixture.history()

    def test_complete_worker_crypto_history_keeps_original_local_unavailable(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            history = fixture.history()
            value = json.loads(fixture.crypto(history))
        self.assertEqual(value["files"], 10)
        self.assertEqual(value["sidecarSha256"], fixture.hash("C/crypto-originals.json"))
        self.assertEqual(value["originalReceivingFirstLocal"], "NOT_INDEPENDENTLY_RECONSTRUCTIBLE")
        self.assertEqual(value["missingOriginalIfRequiredForQualification"], "UNAVAILABLE")
        self.assertEqual(value["liveRecipient"], "NOT_RESTORED")
        self.assertEqual(value["currentAuthority"], "NOT_ACQUIRED")
        self.assertIs(value["exportSaveAuthority"], False)
        self.assertNotIn("local_start", json.loads(fixture.raw["I/receiving-window.json"]))

    def test_crypto_changed_context_refuses_before_native_link_adoption(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            history = fixture.history()
            context = json.loads(fixture.raw["R/recipient-context.json"])
            context["directories"]["crypto"][1] += 1
            fixture.keep("R/recipient-context.json", context)
            with self.assertRaisesRegex(Exception, "CRYPTO_CONTEXT"):
                fixture.crypto(history)

    def test_crypto_changed_native_phase_closure_refuses(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            history = fixture.history()
            phase = json.loads(fixture.raw["R/recipient-validation/result.json"])
            phase["scopeClosed"] = False
            fixture.keep("R/recipient-validation/result.json", phase)
            with self.assertRaisesRegex(Exception, "GRAPH_NATIVE_RETIREMENT"):
                fixture.crypto(history)

    def test_crypto_changed_sender_reference_refuses_even_with_relinked_sidecar(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            history = fixture.history()
            sender = json.loads(fixture.raw["S/sender-pending.json"])
            sender["originalReferences"]["recipientSession"] = "/DIFFERENT-SUPPLIED-SESSION"
            fixture.keep("S/sender-pending.json", sender)
            fixture.index["senderSha256"] = fixture.hash("S/sender-pending.json")
            side = json.loads(fixture.raw["C/crypto-originals.json"])
            side["recipientSenderSha256"] = fixture.index["senderSha256"]
            fixture.keep("C/crypto-originals.json", side)
            fixture.index["recipientCryptoOriginalsSha256"] = fixture.hash("C/crypto-originals.json")
            with self.assertRaisesRegex(Exception, "CRYPTO_WORKER_LINKS"):
                fixture.crypto(history)

    def test_crypto_changed_step_cap_refuses_even_with_relinked_sidecar(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            history = fixture.history()
            step = json.loads(fixture.raw["T/step-pending.json"])
            step["readLocalCeiling"] += 1.0
            fixture.keep("T/step-pending.json", step)
            fixture.index["recipientStepSha256"] = fixture.hash("T/step-pending.json")
            side = json.loads(fixture.raw["C/crypto-originals.json"])
            side["recipientStepSha256"] = fixture.index["recipientStepSha256"]
            fixture.keep("C/crypto-originals.json", side)
            fixture.index["recipientCryptoOriginalsSha256"] = fixture.hash("C/crypto-originals.json")
            with self.assertRaisesRegex(Exception, "CRYPTO_CAPS"):
                fixture.crypto(history)

    def test_crypto_changed_capture_chronology_refuses_even_with_reindexed_sidecar(self):
        with pure_histories_only():
            fixture = SuppliedHistory("worker")
            history = fixture.history()
            side = json.loads(fixture.raw["C/crypto-originals.json"])
            side["inventory"]["capturedNs"] = 1058 * NS
            fixture.keep("C/crypto-originals.json", side)
            fixture.index["recipientCryptoOriginalsSha256"] = fixture.hash("C/crypto-originals.json")
            with self.assertRaisesRegex(Exception, "CRYPTO_TAIL_CHRONOLOGY"):
                fixture.crypto(history)


@contextmanager
def fixed_caller_model(root, *, basis=100 * NS, metadata_raw=212 * NS):
    """Actual copy/ownership/transition gates, supplied carrier/host/Step/clock.

    Only primary_record, primary_history, the names consumed by that supplied
    history, and host/path/clock observations are model boundaries. No new owner,
    Preliminary, Window, snapshot, copy, finish or checked-return gate is stubbed.
    Every file is tiny and newly created here; no original hosted files/reader.
    """
    source, handoff, custody = (root / name for name in ("primary", "handoff", "custody"))
    source.mkdir(mode=0o700)
    handoff.mkdir(mode=0o700)
    (source / "empty-dir").mkdir(mode=0o700)
    first = dataclasses.replace(reading(), nanoseconds=200 * NS)
    observed, event = {"firstUseAt": 1, "scope": "SUPPLIED_HOST_STEP_MODEL"}, b"SUPPLIED_EVENT_NOT_AUTHENTICATED"
    contents = {"context.json": wire({"observed": observed}), "data.bin": b"TINY_PUBLIC_PRIMARY\0", "empty.bin": b""}
    for name, raw in contents.items():
        put(source / name, raw)
    name = D.N.GATE_HANDOFF_FILE
    original_pin = tuple(D.native.posix._identity(handoff))
    handoff_raw = wire({"directory": str(handoff), "directoryIdentity": list(original_pin),
        "scope": "SUPPLIED_CALLER_CARRIER_NOT_AUTHENTIC_STEP"})
    put(handoff / name, handoff_raw)
    primary = D.Primary("gate", "linux-x64", handoff_raw, b"SUPPLIED_INDEX_HELPER_RETURN", (("P", source),),
        (("P", tuple(D.native.posix._identity(source)), "ORIGINAL_NATIVE_PIN"),
         ("P/empty-dir", tuple(D.native.posix._identity(source / "empty-dir")), "ORIGINAL_NATIVE_PIN")),
        tuple(("P/" + key, max(1, len(value)), len(value), sha(value), "ORIGINAL_PRIMARY_DECLARATION")
            for key, value in sorted(contents.items())), (), sha(b"SUPPLIED_RESULT_HASH"))
    env = {D.PRIMARY_OUTCOME: "success", D.PRIMARY_RESULT: primary.result_sha256, D.PRIMARY_HANDOFF: sha(handoff_raw)}
    fixture = SimpleNamespace(primary=primary, first=first, source=source, handoff=handoff, custody=custody,
        handoff_name=name, handoff_raw=handoff_raw, pin=original_pin, contents=contents, observed=observed,
        callback=lambda: None, events=[], attempt=None, changed=False, observe_calls=0)
    names = ("P/context.json", "P/empty.bin")
    def record(kind, role, roots, path, pin, raw, **step):
        # Fixture-bound supply only; primary_record's complete grammar is NOT
        # exercised by this caller model. Its accepted source is not weakened.
        assert (kind, role, roots, path, tuple(pin), raw) == (
            "gate", "linux-x64", {"P": source}, handoff, original_pin, handoff_raw)
        assert step == {"outcome": "success", "result_sha256": primary.result_sha256, "handoff_sha256": sha(handoff_raw)}
        return primary
    with models() as clock, ExitStack() as stack:
        clock.raw = 210 * NS
        fixture.clock = clock
        def history(supplied, raw, actual, actual_event, role_clock, interpreter):
            assert supplied is primary and raw == {key: contents[key.split("/", 1)[1]] for key in names}
            assert actual == observed and actual_event == event and role_clock is first.clock
            assert interpreter == str(Path(sys.executable).resolve(strict=True))
            fixture.events.append("supplied-history-before-original-metadata-close")
            clock.raw, clock.local = metadata_raw, 103.0
            return wire({"originalBootDigest": BOOT, "originalPreviousNs": 190 * NS, "originalJobBasisNs": basis,
                "scope": "SUPPLIED_HISTORICAL_HELPER_RETURN_NOT_CURRENT_AUTHORITY"})
        def observe():
            fixture.observe_calls += 1
            return first
        def cancelled():
            attempt = D._PRIMARY_ATTEMPTS.get("fixed")
            fixture.attempt = attempt
            if attempt is not None and attempt["owners"]:
                prior = attempt["owners"][0]
                if prior.finished and prior.owner.closed:
                    if "original-metadata-known-close" not in fixture.events:
                        fixture.events.append("original-metadata-known-close")
                    if len(attempt["owners"]) == 2 and "same-original-window-copy" not in fixture.events:
                        fixture.events.append("same-original-window-copy")
            fixture.callback()
        clock.callback = cancelled
        # Fresh isolated NEW invocation only; no old registry is restored into a
        # new live owner. Other negative tests' quarantine objects are untouched.
        for module, attr, value in ((D, "_PRIMARY_ATTEMPTS", {}), (D, "_PRIMARY_RETURNS", {}),
                (D, "_PRIMARY_OWNERS", {}), (D, "_PRELIMINARIES", {}), (D, "_WINDOWS", {}),
                (D, "_PRIMARY_QUARANTINE", []), (D.native, "QUARANTINE", []), (D.Q, "QUARANTINE", []),
                (D.C, "QUARANTINE", []), (D.native.diagnostics, "_QUARANTINE", [])):
            stack.enter_context(patch.object(module, attr, value))
        stack.enter_context(patch.dict(os.environ, env, clear=True))
        stack.enter_context(patch.object(D.O.clocks, "observe", observe))
        stack.enter_context(patch.object(D.native.processes, "host_role", lambda: "linux-x64"))
        stack.enter_context(patch.object(D, "_paths", lambda kind: ({"P": source}, handoff, custody) if kind == "gate" else None))
        stack.enter_context(patch.object(D.N, "host_context", lambda use: (observed, source, event) if use == 1 else None))
        stack.enter_context(patch.object(D, "_history_names", lambda kind: names if kind == "gate" else ()))
        stack.enter_context(patch.object(D, "primary_record", record))
        stack.enter_context(patch.object(D, "primary_history", history))
        yield fixture


class FixedCallerTransitionTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.name, "posix", "This new tiny-file caller envelope is POSIX-only, never a native platform skip")

    def test_fixed_caller_known_close_to_same_window_and_original_checked_return(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, fixed_caller_model(Path(temp)) as fixture:
            result = D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            with patch.object(D.O.clocks, "checked_now", side_effect=AssertionError("PASSIVE_CHECK_MUST_NOT_OBSERVE")), \
                    patch.object(D.time, "monotonic", side_effect=AssertionError("PASSIVE_CHECK_MUST_NOT_OBSERVE")):
                window, primary, history, copied, originals = D.checked_primary(result)
            self.assertIs(window, result.window)
            self.assertIs(primary, fixture.primary)
            self.assertIs(originals, result.originals)
            self.assertEqual(history, result.history)
            self.assertEqual(fixture.observe_calls, 1)
            self.assertIs(window._anchor().binding[0], fixture.first)
            self.assertEqual(window._anchor().binding[1], 100.0)
            self.assertEqual((fixture.first.nanoseconds, window.last), (200 * NS, 212 * NS))
            self.assertEqual(window._anchor().local_last, 103.0)
            self.assertEqual(fixture.events, ["supplied-history-before-original-metadata-close",
                "original-metadata-known-close", "same-original-window-copy"])
            self.assertEqual(len(fixture.attempt["owners"]), 2)
            for wrapper in fixture.attempt["owners"]:
                self.assertTrue(wrapper.finished and wrapper.owner.closed)
                self.assertIsNone(wrapper.failure)
                self.assertFalse(wrapper.owner.unknown)
                self.assertTrue(all(row["attempted"] and row["closed"] for row in wrapper.ledger))
                self.assertTrue(all(getattr(resource, "closed", False) for resource in wrapper.returned))
            self.assertEqual(json.loads(result.preliminary_close)["retirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
            self.assertEqual(json.loads(result.native_close)["retirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
            value = json.loads(copied)
            self.assertEqual(value["memberCount"], 4)
            self.assertEqual({row["origin"] for row in value["members"]}, {"PRIMARY"})
            self.assertEqual(value["remainingOrigins"], ["AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT"])
            self.assertEqual(value["freeze"], "NOT_FINAL_THREE_ORIGIN_FREEZE")
            self.assertEqual(value["currentAuthority"], "NOT_ACQUIRED")
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertIsNone(result.crypto_history)
            self.assertEqual(sorted(path.name for path in fixture.custody.iterdir()), ["copied-evidence"])
            self.assertEqual(sorted(path.name for path in (fixture.custody / "copied-evidence").iterdir()),
                ["member-00000.bin", "member-00001.bin", "member-00002.bin", "member-00003.bin"])
            self.assertNotIn("GITHUB_OUTPUT", os.environ)
            self.assertEqual(fixture.attempt["state"], "RETURNED")
            self.assertIs(fixture.attempt["return"], result)

    def test_metadata_consumed_original_work_cannot_be_renewed_by_new_window(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, \
                fixed_caller_model(Path(temp), basis=35 * NS, metadata_raw=220 * NS) as fixture:
            # Original metadata30 ends230, but original job basis leaves work215.
            with self.assertRaisesRegex(Exception, "PRELIMINARY_SPENT_WORK"):
                D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            self.assertEqual(len(fixture.attempt["owners"]), 1)
            self.assertTrue(fixture.attempt["owners"][0].owner.closed)
            self.assertEqual(D._WINDOWS, {})
            self.assertEqual(D._PRIMARY_RETURNS, {})
            self.assertFalse(fixture.custody.exists())

    def test_failed_metadata_close_preserves_falsey_original_and_no_copy_owner(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, fixed_caller_model(Path(temp)) as fixture:
            original, calls = FalseError("SUPPLIED_ORIGINAL_METADATA_CLOSE_FAILURE"), []
            close = D.Q._PosixDirectory.close
            def fails(directory):
                close(directory)  # A return failure is UNKNOWN despite this modeled physical close.
                if directory.path == fixture.source:
                    calls.append(directory)
                    raise original
            with patch.object(D.Q._PosixDirectory, "close", fails), self.assertRaises(FalseError) as seen:
                D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            self.assertIs(seen.exception, original)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(fixture.attempt["owners"]), 1)
            wrapper = fixture.attempt["owners"][0]
            self.assertTrue(wrapper.owner.unknown)
            self.assertIs(wrapper.failure, original)
            self.assertEqual(D._WINDOWS, {})
            self.assertEqual(D._PRIMARY_RETURNS, {})
            self.assertFalse(fixture.custody.exists())
            with self.assertRaises(Exception):
                wrapper.finish()
            self.assertEqual(len(calls), 1)

    def test_identical_handoff_replacement_after_preliminary_close_cannot_adopt_retired_pin(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, fixed_caller_model(Path(temp)) as fixture:
            retired = []
            def replace():
                attempt = fixture.attempt
                if fixture.changed or attempt is None or not attempt["owners"]:
                    return
                owner = attempt["owners"][0]
                if not (owner.finished and owner.owner.closed):
                    return
                original = next(resource for row, label, resource, _attempted, _closed in owner.rows
                    if label == "directory" and resource.path == fixture.handoff)
                self.assertTrue(original.closed)
                self.assertEqual(tuple(original.identity), fixture.pin)
                fixture.handoff.rename(fixture.handoff.with_name("retired-handoff"))
                fixture.handoff.mkdir(mode=0o700)
                put(fixture.handoff / fixture.handoff_name, fixture.handoff_raw)
                replacement_pin = tuple(D.native.posix._identity(fixture.handoff))
                self.assertNotEqual(replacement_pin, fixture.pin)
                original.identity = replacement_pin  # Exact F1: mutable CLOSED supplier field changes.
                retired.append(original)
                fixture.changed = True
            fixture.callback = replace
            with self.assertRaisesRegex(Exception, "PRIMARY_HANDOFF_PIN_CHANGED"):
                D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            self.assertTrue(fixture.changed)
            self.assertEqual((fixture.handoff / fixture.handoff_name).read_bytes(), fixture.handoff_raw)
            self.assertEqual(json.loads(fixture.primary.handoff_raw)["directoryIdentity"], list(fixture.pin))
            self.assertNotEqual(tuple(retired[0].identity), fixture.pin)
            self.assertEqual(D._PRIMARY_RETURNS, {})
            self.assertFalse(fixture.custody.exists())

    def test_fixed_caller_synchronized_directory_row_erasure_never_returns_known_close(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, fixed_caller_model(Path(temp)) as fixture:
            original = []
            def erase():
                attempt = fixture.attempt
                if original or attempt is None or not attempt["owners"]:
                    return
                wrapper = attempt["owners"][0]
                if wrapper.rows:
                    original.append(wrapper.rows[0][2])
                    wrapper.ledger.clear()
                    wrapper.rows.clear()
            fixture.callback = erase
            with self.assertRaises(Exception):
                D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            wrapper = fixture.attempt["owners"][0]
            self.assertIs(wrapper._anchor().returned[0], original[0])
            self.assertIs(wrapper._anchor().rows[0][2], original[0])
            self.assertFalse(original[0].closed)
            self.assertTrue(wrapper.owner.unknown)
            self.assertEqual(D._PRIMARY_RETURNS, {})
            self.assertFalse(fixture.custody.exists())

    def test_fixed_caller_preliminary_first_substitution_stays_failed_before_window(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, fixed_caller_model(Path(temp)) as fixture:
            original = []
            def replace():
                attempt = fixture.attempt
                if original or attempt is None or not attempt["owners"]:
                    return
                pre = attempt["owners"][0].owner.cancelled.__self__
                original.append(pre)
                bound = pre.bound
                pre._bound = (dataclasses.replace(bound[0], nanoseconds=225 * NS), *bound[1:])
            fixture.callback = replace
            with self.assertRaisesRegex(Exception, "PRELIMINARY_ORIGINAL_BINDING"):
                D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            self.assertIs(original[0].bound[0], fixture.first)
            self.assertEqual(original[0].bound[0].nanoseconds, 200 * NS)
            self.assertLessEqual(original[0].end, 130.0)
            self.assertEqual(D._WINDOWS, {})
            self.assertEqual(D._PRIMARY_RETURNS, {})
            self.assertFalse(fixture.custody.exists())

    def test_checked_primary_keeps_original_closed_owner_anchor_after_return(self):
        with tempfile.TemporaryDirectory(prefix="custody-caller-test-") as temp, fixed_caller_model(Path(temp)) as fixture:
            result = D.copy_primary("gate", cancelled=fixture.clock.cancelled)
            D.checked_primary(result)
            owner = fixture.attempt["owners"][0]
            original = owner._anchor().rows
            owner.ledger.clear()
            owner.rows.clear()
            with self.assertRaises(Exception):
                D.checked_primary(result)
            self.assertIs(owner._anchor().rows, original)
            self.assertTrue(original)
            self.assertEqual(fixture.attempt["state"], "FAILED")


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
