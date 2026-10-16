#!/usr/bin/env python3
"""NEW confined AUTHORITY-copy controls; AUTHORED, not execution evidence.

The maintained leaf, original Window, fresh _PrimaryOwner/native.Owner and
snapshot/stream/write/readback/aggregate/close helpers are real. The two checked
upstream returns, prior PRIMARY map and full281/58 authority inventory are
explicit SUPPLIED data, not authentic Steps, authority or native query evidence.
Tiny owned POSIX files retain the full38/243 file and7/51 directory distinctions;
no count, positive limit or deadline is reduced to make a positive fit.

No old suite is imported, discovered or run. No historical owner is restored.
RAW/LOCAL/boot are supplied; the new file owner's first/fence remain actual fixed
objects inside this modeled execution. Fault suppliers are limited to explicitly
named new-leaf callbacks/file-I/O edges. No process/network/native-library/GPG,
credential, private original, provider/cache/freeze/export or hosted qualification
is permitted or inferred. Final owner close is separately exercised by these
controls, never attributed to this non-closing byte-return leaf.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import ctypes  # Complete stdlib setup before rejecting native-library loads.
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_AUTHORITY_COPY_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("custody_authority_copy_supplied_upstreams",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS, BOOT = 1_000_000_000, "a" * 64
PINNED = {".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"}


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
    path.chmod(0o600)


def metadata(entries):
    return [[name, directory, list(identity), count, json.loads(raw)]
        for name, directory, identity, count, raw in D._snapshot_metadata(entries, False)]


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class Clock:
    def __init__(self):
        self.raw, self.local, self.callback = 1100 * NS, 100.0, lambda: None
        self.first = D.O.clocks.Reading(
            D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS), self.raw)

    def checked(self, clock, *, minimum_ns=0):
        if clock != self.first.clock or self.raw < minimum_ns:
            raise AssertionError("SUPPLIED_ORIGINAL_CLOCK_FRONTIER")
        return self.raw

    def cancelled(self):
        self.callback()


class SuppliedCopy:
    """Full authority shape, tiny actual files, explicitly supplied prior returns."""
    def __init__(self, kind="gate"):
        self.kind, self.stack, self.clock = kind, ExitStack(), Clock()
        self.primary_handle, self.authority_handle = object(), object()
        self.primary_checks, self.authority_checks = 0, 0
        self.owner = None

    def __enter__(self):
        try:
            self.stack.enter_context(patch.dict(D.os.environ, {}, clear=True))
            self.stack.enter_context(patch.object(D.time, "monotonic", lambda: self.clock.local))
            self.stack.enter_context(patch.object(D.O.clocks, "checked_now", self.clock.checked))
            self.stack.enter_context(patch.object(D.C, "boot_digest", lambda _role: BOOT))
            for module, name in ((D, "_WINDOWS"), (D, "_PRIMARY_OWNERS")):
                self.stack.enter_context(patch.object(module, name, {}))
            self.stack.enter_context(patch.object(D, "_PRIMARY_QUARANTINE", []))
            self.stack.enter_context(patch.object(D.native, "QUARANTINE", []))
            self.base = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="authority-copy-supplied-")))
            self.custody = self.base / "primary-custody"
            self.source, self.destination_path = self.custody / "authority-1", self.custody / "copied-evidence"
            for path in (self.custody, self.source, self.destination_path):
                path.mkdir(mode=0o700)
            self.roots, self.handoff = {"P": self.base / "primary"}, self.base / "primary-handoff"
            self.window = D.Window(self.clock.first, self.clock.local, BOOT,
                D.schedule(self.kind, 1050 * NS, self.clock.raw), self.clock.cancelled)
            self.window_binding = self.window._view().binding
            self.make_primary()
            self.make_authority()
            self.primary_reply = (self.window, self.primary, self.history, self.primary_raw, self.historical)
            self.refresh_authority_reply()
            self.stack.enter_context(patch.object(D, "_paths", self.paths))
            self.stack.enter_context(patch.object(D, "checked_primary", self.checked_primary))
            self.stack.enter_context(patch.object(D, "checked_custody_authority", self.checked_authority))
            native = D.native.Owner(self.window.deadline(900, final=True), self.window,
                first=self.clock.first, cancelled=self.clock.cancelled)
            native.work_limit, native.final_limit = self.window.work, self.window.final
            self.owner = D._PrimaryOwner(native)
            self.destination = D._private(self.owner, self.destination_path)
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        # Only genuinely available original resources may be closed. No UNKNOWN
        # retry; injected ambiguous-close controls retain their original rows.
        if self.owner is not None and not self.owner.finished and not self.owner.owner.unknown:
            try:
                self.owner.finish()
            except BaseException:
                pass  # The test's original refusal remains visible, never replaced by cleanup.
        return self.stack.__exit__(*args)

    def paths(self, kind):
        if kind != self.kind:
            raise AssertionError("SUPPLIED_FIXED_KIND")
        return self.roots, self.handoff, self.custody

    def checked_primary(self, result):
        if result is not self.primary_handle:
            raise AssertionError("SUPPLIED_ORIGINAL_PRIMARY_HANDLE")
        self.primary_checks += 1
        return self.primary_reply

    def checked_authority(self, result, primary):
        if result is not self.authority_handle or primary is not self.primary_handle:
            raise AssertionError("SUPPLIED_ORIGINAL_AUTHORITY_HANDLES")
        self.authority_checks += 1
        return self.authority_reply

    def make_primary(self):
        self.previous = (b"SUPPLIED_PRIOR_PRIMARY\n", b"", b"SUPPLIED_PRIOR_HANDOFF\n")
        for ordinal, raw in enumerate(self.previous):
            put(self.destination_path / D._member_name(ordinal), raw)
        entries = D.native.posix._snapshot(self.destination_path, D.MAX_BYTES, D.MAX_MEMBERS, 200.0)
        self.previous_metadata = metadata(entries)
        self.previous_stamps = dict(entries)
        members = []
        for ordinal, raw in enumerate(self.previous):
            name, stamp = D._member_name(ordinal), entries[D._member_name(ordinal)]
            members.append({"member": name, "bytes": len(raw), "sha256": sha(raw), "origin": "PRIMARY",
                "original": "P/supplied-" + str(ordinal), "originalMaximum": max(1, len(raw)),
                "provenance": "SUPPLIED_PRIOR_PRIMARY_DECLARATION", "carrier": "INDEXED_DISK_ORIGINAL",
                "destinationWriteMetadata": {"device": stamp[0], "inode": stamp[1], "size": stamp[5],
                    "mtime_ns": stamp[6], "ctime_ns": stamp[7]}})
        self.primary_map = {"schema": 1, "scope": D.PRIMARY_SCOPE, "origin": "PRIMARY", "members": members,
            "sourceMetadata": [], "originalDirectories": [], "handoffMetadata": [],
            "destination": str(self.destination_path), "destinationIdentity": list(entries[""][:2]),
            "destinationMetadata": self.previous_metadata, "memberCount": len(members),
            "totalBytes": sum(map(len, self.previous)), "nextOrdinal": len(members),
            "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE", "remainingOrigins": list(D.ORIGINS[1:]),
            "productiveAuthority": False, "currentAuthority": "NOT_ACQUIRED", "exportSaveAuthority": False}
        self.primary_raw = wire(self.primary_map)
        # Deliberately supplied upstream record, NOT the PRIMARY producer or an
        # authority inventory disguised as a Primary to enter its copy helper.
        self.primary = D.Primary(self.kind, "linux-x64", b"SUPPLIED_PRIOR_HANDOFF", b"SUPPLIED_PRIOR_INDEX",
            tuple(self.roots.items()), (), (), (), sha(b"SUPPLIED_PRIOR_RESULT"))
        self.history = wire({"scope": "SUPPLIED_PRIOR_HISTORY_NOT_A_STEP"})
        self.historical = (("SUPPLIED_HISTORY_ONLY", b"not-authentic"),)

    def make_authority(self):
        self.disk, self.maximum, directories = {}, {}, set(PINNED)
        def add(name, raw=b"{}\n", maximum=None):
            if name in self.disk:
                raise AssertionError("SUPPLIED_DUPLICATE_FILE")
            self.disk[name] = raw
            self.maximum[name] = max(1, len(raw)) if maximum is None else maximum
        for group, count in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
            directories.add(group + "/query-home")
            add(group + "/owner.json", b'{"scope":"SUPPLIED_QUERY_DECLARATION_NOT_NATIVE"}\n')
            for number in range(count):
                query = group + "/query-" + format(number + 1, "032x")
                directories.add(query)
                for name in ("start.json", "baseline.json", "result.json"):
                    add(query + "/" + name)
                limit = D.I.EVENT_LIMIT if number % 12 == 1 else D.I.POLICY_LIMIT if number % 12 == 11 else 4096
                add(query + "/stdout.log", b"", limit)
                add(query + "/stderr.log", b"", 4096)
            for name in (D.N.ORIGINAL_KEYS if group == "acquisition-queries" else D.N.SOURCE_KEYS):
                add(group + "/" + name + ".bin", b"" if name == "base_policy_entry" else b"SUPPLIED:" + name.encode("ascii"))
            add(group + "/session-result.json", wire({"scope": "SUPPLIED_CLOSED_QUERY_DECLARATION"}), D.Q.MAX_RECEIPT_BYTES)
            if group != "acquisition-queries":
                add(group + "/source-return.json", wire({"scope": "SUPPLIED_SOURCE_RETURN"}), D.native.LIMIT)
        add("authority-window.json", D._custody_authority_window(self.window), D.native.LIMIT)
        add("context.json", wire({"scope": "SUPPLIED_AUTHORITY_CONTEXT_NOT_AUTHORIZATION"}), D.native.LIMIT)
        for name in sorted(D.native.PHASE_FILES):
            raw = b"" if name.endswith(".log") else wire({"scope": "SUPPLIED_NATIVE_RECORD_NOT_EVIDENCE", "name": name})
            maximum = D.native.ACK_LIMIT if name == "stdout.log" else D.native.STDERR_LIMIT if name == "stderr.log" else D.native.LIMIT
            add("service/" + name, raw, maximum)
        add("service/child-result.json", wire({"scope": "SUPPLIED_CHILD_RETURN"}), D.native.LIMIT)
        match_type = D.A.gate.GateEligibility if self.kind == "gate" else D.A.stages.BootstrapMatch
        self.match = match_type(wire({"scope": "SUPPLIED_MATCH_NOT_A_LIVE_LEASE", "kind": self.kind}))
        self.disk["acquisition-queries/match.bin"] = self.match.record
        self.maximum["acquisition-queries/match.bin"] = len(self.match.record)
        self.captured = (self.disk["context.json"], tuple((name, self.disk["acquisition-queries/" + name + ".bin"])
            for name in D.N.ORIGINAL_KEYS), "d" * 32, self.clock.raw, self.window.work)
        original_names = ["authority-window.json", "context.json", "service/child-result.json",
            "acquisition-queries/session-result.json", *("service/" + name for name in sorted(D.native.PHASE_FILES)),
            *("acquisition-queries/" + name + ".bin" for name in D.N.ORIGINAL_KEYS)]
        for group in ("source-before", "source-after"):
            original_names.extend((group + "/source-return.json", group + "/session-result.json",
                *(group + "/" + name + ".bin" for name in D.N.SOURCE_KEYS)))
        self.chain = {"phaseSha256": {name: sha(self.disk["service/" + name]) for name in D.native.PHASE_FILES},
            "childSha256": sha(self.disk["service/child-result.json"]),
            "querySessionSha256": sha(self.disk["acquisition-queries/session-result.json"]),
            "originalsSha256": {name: sha(raw) for name, raw in self.captured[1]}, "checkedNs": self.clock.raw}
        pending = wire({"schema": 1, "scope": D._AUTHORITY_PENDING_SCOPE,
            "windowSha256": sha(self.disk["authority-window.json"]), "primaryResultSha256": self.primary.result_sha256,
            "primaryCopySha256": sha(self.primary_raw), "matchSha256": sha(self.match.record),
            "filesSha256": {name: sha(self.disk[name]) for name in original_names}, "originalChain": self.chain,
            "retainedNs": self.clock.raw, "retirement": "PENDING_OWNER_CLOSE", "exportSaveAuthority": False})
        add("authority-pending.json", pending, D.native.LIMIT)
        original_names.append("authority-pending.json")
        self.originals = tuple((name, self.disk[name]) for name in original_names)
        for name in sorted(directories, key=lambda value: (value.count("/"), value)):
            if name != ".":
                (self.source / name).mkdir(mode=0o700)
        for name, raw in self.disk.items():
            put(self.source / name, raw)
        self.source_stamps = D.native.posix._snapshot(self.source, D.MAX_BYTES, D.MAX_MEMBERS, 200.0)
        self.index = {"schema": 1, "scope": D._AUTHORITY_INDEX_SCOPE, "origin": D.ORIGINS[1],
            "root": str(self.source), "clock": D.O.clock_value(self.clock.first.clock),
            "contextSha256": sha(self.disk["context.json"]), "matchSha256": sha(self.match.record),
            "pendingSha256": sha(pending), "files": [{"relative": name, "maximum": self.maximum[name],
                "bytes": len(raw), "sha256": sha(raw), "provenance": "ACTUAL_RETAINED_BYTES" if name in original_names
                    else "ORIGINAL_QUERY_DECLARATION"} for name, raw in sorted(self.disk.items())],
            "directories": [{"relative": name, "identity": list(self.source_stamps["" if name == "." else name][:2])
                if name in PINNED else None, "provenance": "ORIGINAL_NATIVE_PIN" if name in PINNED
                else "ORIGINAL_QUERY_DECLARATION"} for name in sorted(directories)],
            "fileCount": 281, "directoryCount": 58, "totalBytes": sum(map(len, self.disk.values())),
            "copyState": "ORIGINAL_BYTES_NOT_COPIED", "exportSaveAuthority": False}
        self.closed = {"schema": 1, "scope": D._AUTHORITY_RETURN_SCOPE,
            "windowSha256": sha(self.disk["authority-window.json"]), "primaryResultSha256": self.primary.result_sha256,
            "primaryCopySha256": sha(self.primary_raw), "matchSha256": sha(self.match.record),
            "inventorySha256": sha(wire(self.index)), "pendingSha256": sha(pending), "originalChain": self.chain,
            "preCloseNs": self.clock.raw, "closedNs": self.clock.raw, "resourceCount": 7,
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}

    def refresh_authority_reply(self):
        self.inventory_raw = wire(self.index)
        self.closed["inventorySha256"] = sha(self.inventory_raw)
        self.closed_raw = wire(self.closed)
        self.authority_reply = (self.window, self.match, self.captured, self.closed_raw, self.inventory_raw, self.originals)

    def run(self, destination=None):
        return D._copy_authority(self.owner, self.primary_handle, self.authority_handle,
            self.destination if destination is None else destination)

    def appended(self):
        return sorted(path.name for path in self.destination_path.iterdir()
            if path.name not in {D._member_name(number) for number in range(len(self.previous))})


class AuthorityCopyControls(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.name, "posix", "This confined real-file envelope is POSIX-only, not a platform skip")

    def close_failed(self, rig, first, *, unknown=False):
        self.assertIs(rig.owner.failure, first)
        self.assertIs(rig.owner.owner.original, first)
        self.assertEqual(rig.owner.owner.unknown, unknown)
        with self.assertRaises(type(first)) as caught:
            rig.owner.finish()
        self.assertIs(caught.exception, first)
        if unknown:
            self.assertIn(rig.owner, D._PRIMARY_QUARANTINE)
        else:
            self.assertTrue(rig.owner.owner.closed)
            self.assertTrue(all(attempted and closed for _row, _label, _resource, attempted, closed in rig.owner.rows))

    def test_full_gate_and_worker_append_preserves_prior_primary_and_original_metadata(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), SuppliedCopy(kind) as rig:
                before_raw, old_bytes = rig.primary_raw, tuple(rig.previous)
                raw = rig.run()
                value = json.loads(raw)
                self.assertEqual(raw, wire(value))
                self.assertEqual((len(rig.disk), len(rig.source_stamps)), (281, 339))
                self.assertEqual((value["origin"], value["scope"]),
                    (D.ORIGINS[1], "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_COPY_V1"))
                self.assertEqual((value["previousMemberCount"], value["memberCount"], value["nextOrdinal"]), (3, 282, 285))
                self.assertEqual(value["aggregateMemberCount"], 285)
                self.assertEqual(value["primaryCopySha256"], sha(before_raw))
                self.assertEqual(value["primaryResultSha256"], rig.primary.result_sha256)
                self.assertEqual(value["authorityReturnSha256"], sha(rig.closed_raw))
                self.assertEqual(value["authorityInventorySha256"], sha(rig.inventory_raw))
                self.assertEqual(base64.b64decode(value["authorityInventoryBase64"], validate=True), rig.inventory_raw)
                self.assertEqual(value["originalDirectories"], rig.index["directories"])
                self.assertEqual(sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in value["members"]), 38)
                self.assertEqual(sum(row["provenance"] == "ORIGINAL_QUERY_DECLARATION" for row in value["members"]), 243)
                self.assertEqual(sum(row["provenance"] == "ORIGINAL_NATIVE_PIN" for row in value["originalDirectories"]), 7)
                self.assertEqual(sum(row["provenance"] == "ORIGINAL_QUERY_DECLARATION" for row in value["originalDirectories"]), 51)
                self.assertEqual(value["sourceMetadata"], metadata(rig.source_stamps))
                self.assertEqual(value["destinationRootBefore"], rig.previous_metadata[0])
                self.assertEqual(value["destinationBeforeMetadataSha256"], sha(wire({"metadata": rig.previous_metadata})))
                after = D.native.posix._snapshot(rig.destination_path, D.MAX_BYTES, D.MAX_MEMBERS, 200.0)
                self.assertEqual(value["destinationMetadata"], metadata(after))
                self.assertEqual(value["destinationMetadata"][1:4], rig.previous_metadata[1:])
                self.assertEqual(after[""][:2], rig.previous_stamps[""][:2])
                self.assertNotEqual(after[""], rig.previous_stamps[""])  # Truthful root append, not immutable root stamp.
                self.assertEqual(rig.primary_raw, before_raw)
                for ordinal, original in enumerate(old_bytes):
                    self.assertEqual((rig.destination_path / D._member_name(ordinal)).read_bytes(), original)
                for number, row in enumerate(value["members"], 3):
                    self.assertEqual(row["member"], D._member_name(number))
                    self.assertEqual(row["origin"], D.ORIGINS[1])
                    copied = (rig.destination_path / row["member"]).read_bytes()
                    self.assertEqual((len(copied), sha(copied)), (row["bytes"], row["sha256"]))
                    if row["carrier"] == "INDEXED_DISK_ORIGINAL":
                        self.assertEqual(copied, rig.disk[row["original"]])
                        self.assertEqual(row["sourceCopyIdentity"], list(rig.source_stamps[row["original"]][:2]))
                        self.assertEqual(row["originalMaximum"], rig.maximum[row["original"]])
                    else:
                        self.assertEqual(row["carrier"], "EMBEDDED_NOT_DISK_ORIGINAL")
                        self.assertEqual(row["original"], "authority-return.json")
                        self.assertEqual(row["provenance"], "ACTUAL_CLOSED_PARENT_RETURN")
                        self.assertIsNone(row["sourceCopyIdentity"])
                        self.assertEqual(copied, rig.closed_raw)
                self.assertEqual(value["totalBytes"], rig.index["totalBytes"] + len(rig.closed_raw))
                self.assertEqual(value["aggregateTotalBytes"], value["totalBytes"] + sum(map(len, old_bytes)))
                self.assertEqual(value["remainingOrigins"], [D.ORIGINS[2]])
                self.assertEqual(value["freeze"], "NOT_FINAL_THREE_ORIGIN_FREEZE")
                self.assertEqual(value["currentAuthority"], "CLOSED_HISTORY_NOT_LIVE_LEASE")
                self.assertIs(value["exportSaveAuthority"], False)
                self.assertIs(value["productiveAuthority"], False)
                self.assertIs(rig.window._view().binding, rig.window_binding)
                self.assertIs(rig.owner.owner.fence, rig.window)
                self.assertIs(rig.owner.owner.first, rig.clock.first)
                self.assertFalse(rig.owner.finished)  # A byte-return leaf cannot claim its outer close.
                self.assertEqual(len(rig.owner.snapshots), 3)
                self.assertGreater(rig.primary_checks, 1)
                self.assertGreater(rig.authority_checks, 1)
                closed = json.loads(rig.owner.finish())
                self.assertEqual(closed["retirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
                self.assertTrue(all(attempted and ended for _row, _label, _resource, attempted, ended in rig.owner.rows))
                self.assertEqual(len(rig.appended()), 282)
                self.assertFalse((rig.destination_path / "copy-map.json").exists())

    def test_different_authority_window_and_unregistered_destination_refuse(self):
        for change in ("window", "destination"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                destination = None
                if change == "window":
                    other = D.Window(rig.clock.first, rig.clock.local, BOOT,
                        D.schedule(rig.kind, 1050 * NS, rig.clock.raw), rig.clock.cancelled)
                    rig.authority_reply = (other, *rig.authority_reply[1:])
                    code = "AUTHORITY_COPY_ORIGINAL_WINDOW"
                else:
                    destination = D.Q._PosixDirectory(rig.destination_path)
                    code = "AUTHORITY_COPY_OWNED_DESTINATION"
                try:
                    with self.assertRaisesRegex(ValueError, code) as caught:
                        rig.run(destination)
                    self.assertEqual(rig.appended(), [])
                    self.close_failed(rig, caught.exception)
                finally:
                    if destination is not None:
                        destination.close()  # Test-owned negative argument, never registered by the leaf.

    def test_full_source_file_and_empty_directory_rosters_are_required(self):
        for change in ("missing-file", "extra-file", "missing-empty", "extra-empty"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                if change == "missing-file":
                    (rig.source / "source-before/query-00000000000000000000000000000001/stdout.log").unlink()
                elif change == "extra-file":
                    put(rig.source / "extra.bin", b"x")
                elif change == "missing-empty":
                    (rig.source / "source-before/query-home").rmdir()
                else:
                    (rig.source / "extra-empty").mkdir(mode=0o700)
                with self.assertRaisesRegex(ValueError, "AUTHORITY_COPY_EXACT_ROSTER") as caught:
                    rig.run()
                self.assertEqual(rig.appended(), [])
                self.close_failed(rig, caught.exception)

    def test_primary_destination_metadata_member_bytes_and_root_cannot_be_replaced(self):
        for change in ("old-bytes", "equal-old-replacement", "extra-member", "root-replacement"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                old = rig.destination_path / "member-00000.bin"
                if change == "old-bytes":
                    old.write_bytes(b"x" * len(rig.previous[0]))
                elif change == "equal-old-replacement":
                    old.rename(rig.base / "retained-original.bin")
                    put(old, rig.previous[0])
                elif change == "extra-member":
                    put(rig.destination_path / "unlisted.bin", b"x")
                else:
                    rig.destination_path.rename(rig.base / "retained-original-destination")
                    rig.destination_path.mkdir(mode=0o700)
                # The new root stamp disagrees with the original open-directory
                # pin before _snapshot_current calls directory.verify().
                code = "COPY_SNAPSHOT_CHANGED" if change == "root-replacement" else "AUTHORITY_COPY_PREVIOUS_DESTINATION"
                with self.assertRaisesRegex(ValueError, code) as caught:
                    rig.run()
                self.assertFalse((rig.destination_path / "member-00003.bin").exists())
                self.close_failed(rig, caught.exception)

    def test_exact_original_pin_and_file_directory_provenance_are_not_relabelled(self):
        for change in ("pin", "declared-pin", "native-provenance", "declared-provenance", "retained-file", "declared-file"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                if change in ("retained-file", "declared-file"):
                    required = "ACTUAL_RETAINED_BYTES" if change == "retained-file" else "ORIGINAL_QUERY_DECLARATION"
                    row = next(row for row in rig.index["files"] if row["provenance"] == required)
                    row["provenance"] = "ORIGINAL_QUERY_DECLARATION" if change == "retained-file" else "ACTUAL_RETAINED_BYTES"
                    code = "AUTHORITY_COPY_FILE_PROVENANCE"
                else:
                    pinned = change in ("pin", "native-provenance")
                    row = next(row for row in rig.index["directories"] if (row["relative"] in PINNED) == pinned)
                    if change == "pin":
                        row["identity"] = [row["identity"][0], row["identity"][1] + 1]
                        code = "AUTHORITY_COPY_ORIGINAL_PIN"
                    elif change == "declared-pin":
                        row["identity"] = list(rig.source_stamps[""][:2])
                        code = "AUTHORITY_COPY_DIRECTORY_PROVENANCE"
                    else:
                        row["provenance"] = "ORIGINAL_QUERY_DECLARATION" if pinned else "ORIGINAL_NATIVE_PIN"
                        code = "AUTHORITY_COPY_DIRECTORY_PROVENANCE"
                rig.refresh_authority_reply()  # Model a malformed supplied input, not changed trusted helper output.
                with self.assertRaisesRegex(ValueError, code) as caught:
                    rig.run()
                self.assertEqual(rig.appended(), [])
                self.close_failed(rig, caught.exception)

    def test_exact_retained_tuple_and_closed_index_links_are_required(self):
        for change in ("missing", "duplicate", "retained-bytes", "context", "return-link"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                if change == "missing":
                    rig.originals = rig.originals[:-1]
                    code = "AUTHORITY_COPY_RETAINED_ORIGINALS"
                elif change == "duplicate":
                    rig.originals = (*rig.originals[:-1], rig.originals[0])
                    code = "AUTHORITY_COPY_RETAINED_ORIGINALS"
                elif change in ("retained-bytes", "context"):
                    target = "acquisition-queries/event.bin" if change == "retained-bytes" else "context.json"
                    rig.originals = tuple((name, raw + b"changed" if name == target else raw) for name, raw in rig.originals)
                    code = "AUTHORITY_COPY_FILE_PROVENANCE" if change == "retained-bytes" else "AUTHORITY_COPY_CLOSED_LINKS"
                else:
                    rig.closed["primaryCopySha256"] = "0" * 64
                    code = "AUTHORITY_COPY_CLOSED_LINKS"
                rig.refresh_authority_reply()
                with self.assertRaisesRegex(ValueError, code) as caught:
                    rig.run()
                self.assertEqual(rig.appended(), [])
                self.close_failed(rig, caught.exception)

    def test_declared_file_maximum_size_and_digest_are_enforced_by_real_copy(self):
        for change in ("maximum", "size", "digest"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                row = next(row for row in rig.index["files"]
                    if row["provenance"] == "ORIGINAL_QUERY_DECLARATION" and row["bytes"] > 0)
                if change == "maximum":
                    row["maximum"] = 0
                    code = "AUTHORITY_COPY_FILE"
                elif change == "size":
                    row["bytes"] += 1
                    row["maximum"] = max(row["maximum"], row["bytes"])
                    rig.index["totalBytes"] += 1
                    code = "AUTHORITY_COPY_EXACT_ROSTER"
                else:
                    row["sha256"] = "0" * 64
                    code = "COPY_SIZE_HASH_EOF"
                rig.refresh_authority_reply()
                with self.assertRaisesRegex(ValueError, code) as caught:
                    rig.run()
                self.close_failed(rig, caught.exception)

    def test_actual_reader_return_cannot_hide_an_appended_eof_byte(self):
        with SuppliedCopy() as rig:
            actual, changed = D.native.posix._open_member, []
            target = "acquisition-queries/query-00000000000000000000000000000001/stdout.log"
            def append_after_open(root, name, snapshot):
                reader = actual(root, name, snapshot)
                if root == rig.source and name == target and not changed:
                    changed.append(reader)
                    with (root / name).open("ab") as stream:
                        stream.write(b"x")
                return reader
            with patch.object(D.native.posix, "_open_member", append_after_open):
                with self.assertRaisesRegex(ValueError, "COPY_SIZE_HASH_EOF") as caught:
                    rig.run()
            self.assertEqual(len(changed), 1)
            self.assertTrue(changed[0].closed)
            self.close_failed(rig, caught.exception)

    def test_short_boolean_write_and_falsey_first_keep_known_original_cleanup(self):
        for change in ("short", "boolean", "falsey"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                first = FalseyFailure("SUPPLIED_AUTHORITY_COPY_WRITE_FIRST")
                def refuse_write(_writer, _raw):
                    if change == "falsey":
                        raise first
                    return 0 if change == "short" else True
                with patch.object(D.Q._PosixSink, "write", refuse_write):
                    with self.assertRaises(Exception) as caught:
                        rig.run()
                if change == "falsey":
                    self.assertIs(caught.exception, first)
                else:
                    self.assertIn("COPY_SHORT_WRITE", str(caught.exception))
                self.close_failed(rig, caught.exception)

    def test_secondary_unknown_writer_close_preserves_falsey_first_and_never_retries(self):
        with SuppliedCopy() as rig:
            first, secondary = FalseyFailure("SUPPLIED_WRITE_FIRST"), RuntimeError("SUPPLIED_CLOSE_SECOND")
            actual_close, closes = D.Q._PosixSink.close, []
            def fail_close(writer):
                closes.append(writer)
                actual_close(writer)  # Close the test file once, then model an ambiguous return.
                raise secondary
            with patch.object(D.Q._PosixSink, "write", side_effect=first), \
                    patch.object(D.Q._PosixSink, "close", fail_close):
                with self.assertRaises(FalseyFailure) as caught:
                    rig.run()
                self.assertIs(caught.exception, first)
                self.assertEqual(len(closes), 1)
                self.assertTrue(closes[0].closed)
                row = next(row for row in rig.owner.rows if row[2] is closes[0])
                self.assertEqual(row[3:], (False, False))  # UNKNOWN return is not accepted as a known close.
                self.close_failed(rig, first, unknown=True)
                self.assertEqual(len(closes), 1)
                self.assertFalse(rig.owner.owner.closed)

    def test_real_source_hardlink_and_uppercase_case_alias_are_refused(self):
        for change in ("hardlink", "casefold"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                if change == "hardlink":
                    target = rig.source / "source-before/query-00000000000000000000000000000001/stdout.log"
                    target.unlink()
                    os.link(rig.source / "source-before/query-00000000000000000000000000000001/stderr.log", target)
                    code, unknown = "hard links", True
                else:
                    put(rig.source / "AUTHORITY-WINDOW.JSON", b"x")
                    # The fixed lowercase component grammar refuses this case
                    # alias before the later casefold-collision predicate.
                    code, unknown = "QUERY_COMPONENT", False
                with self.assertRaisesRegex(Exception, code) as caught:
                    rig.run()
                self.assertEqual(rig.appended(), [])
                self.close_failed(rig, caught.exception, unknown=unknown)

    def test_source_empty_directory_change_after_copy_is_caught_by_final_rescan(self):
        with SuppliedCopy() as rig:
            actual, changed = D._copy_member, []
            def change_unread_directory(*args, **kwargs):
                result = actual(*args, **kwargs)
                if not changed:
                    changed.append(True)
                    (rig.source / "control-home/late-empty").mkdir(mode=0o700)
                return result
            with patch.object(D, "_copy_member", change_unread_directory):
                with self.assertRaisesRegex(ValueError, "COPY_SOURCE_OR_DESTINATION_CHANGED") as caught:
                    rig.run()
            self.assertEqual(changed, [True])
            self.assertEqual(len(rig.appended()), 282)
            self.close_failed(rig, caught.exception)

    def test_append_transition_rejects_old_member_changes_and_unlisted_new_members(self):
        for change in ("old-member", "unlisted"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                actual, changed = D._copy_member, []
                def change_destination(*args, **kwargs):
                    result = actual(*args, **kwargs)
                    if not changed:
                        changed.append(True)
                        if change == "old-member":
                            (rig.destination_path / "member-00000.bin").write_bytes(b"x" * len(rig.previous[0]))
                        else:
                            put(rig.destination_path / "unlisted.bin", b"x")
                    return result
                with patch.object(D, "_copy_member", change_destination):
                    with self.assertRaisesRegex(ValueError, "AUTHORITY_COPY_APPEND_TRANSITION") as caught:
                        rig.run()
                self.assertEqual(changed, [True])
                self.close_failed(rig, caught.exception)

    def test_equal_new_member_replacement_does_not_replace_the_actual_writer_pin(self):
        with SuppliedCopy() as rig:
            actual, replaced = D._copy_member, []
            def replace_written(*args, **kwargs):
                result = actual(*args, **kwargs)
                if not replaced:
                    target = rig.destination_path / result[0]
                    raw = target.read_bytes()
                    target.rename(rig.base / "original-writer-output.bin")
                    put(target, raw)
                    replaced.append(result[0])
                return result
            with patch.object(D, "_copy_member", replace_written):
                with self.assertRaisesRegex(ValueError, "COPY_WRITER_SNAPSHOT_PIN") as caught:
                    rig.run()
            self.assertEqual(replaced, ["member-00003.bin"])
            self.close_failed(rig, caught.exception)

    def test_original_checked_return_links_cannot_change_from_the_real_window_callback(self):
        for change in ("primary-map", "history-tuple", "authority-raw", "captured-tuple", "originals-tuple"):
            with self.subTest(change=change), SuppliedCopy() as rig:
                changed = []
                def mutate():
                    if not changed and any(row["label"] == "writer" and row["closed"] for row in rig.owner.ledger):
                        changed.append(True)
                        if change in ("primary-map", "history-tuple"):
                            values = list(rig.primary_reply)
                            values[3 if change == "primary-map" else 4] = rig.primary_raw + b" " if change == "primary-map" \
                                else tuple(list(rig.historical))
                            rig.primary_reply = tuple(values)
                        else:
                            values = list(rig.authority_reply)
                            at = {"authority-raw": 3, "captured-tuple": 2, "originals-tuple": 5}[change]
                            values[at] = rig.closed_raw + b" " if change == "authority-raw" else tuple(list(values[at]))
                            rig.authority_reply = tuple(values)
                rig.clock.callback = mutate
                code = "AUTHORITY_COPY_PRIMARY_CHANGED" if change in ("primary-map", "history-tuple") else "AUTHORITY_COPY_RETURN_CHANGED"
                with self.assertRaisesRegex(ValueError, code) as caught:
                    rig.run()
                self.assertEqual(changed, [True])
                self.assertIs(rig.window._view().binding, rig.window_binding)
                self.close_failed(rig, caught.exception)

    def test_artificial_aggregate_bound_counts_previous_source_and_full_append_together(self):
        for bound in ("bytes", "members"):
            with self.subTest(bound=bound), SuppliedCopy() as rig:
                # Count the pre-append destination snapshot too; repeated source
                # observations are not removed to invent independent allowances.
                required_bytes = 2 * sum(map(len, rig.previous)) + 2 * rig.index["totalBytes"] + len(rig.closed_raw)
                required_members = (len(rig.previous) + 1) + 339 + (len(rig.previous) + 283)
                name, limit = ("MAX_BYTES", required_bytes - 1) if bound == "bytes" else ("MAX_MEMBERS", required_members - 1)
                original = getattr(D, name)
                with patch.object(D, name, limit):
                    with self.assertRaisesRegex(ValueError, "COPY_AGGREGATE_CAP") as caught:
                        rig.run()
                self.assertEqual(getattr(D, name), original)
                self.assertEqual(rig.appended(), [])
                self.assertEqual(len(rig.owner.snapshots), 2)
                self.close_failed(rig, caught.exception)


if __name__ == "__main__":
    unittest.main()
