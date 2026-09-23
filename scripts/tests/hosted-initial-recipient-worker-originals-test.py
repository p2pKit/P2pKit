#!/usr/bin/env python3
"""Authored worker-originals controls; NOT native/hosted/custody acceptance.

Direct new TestCases only. Compose fixture setup, never select old test methods.
The accepted1066 reader and its generator do NOT execute: a separately supplied
exact-shaped tiny return model provides its bytes and live directory roster.
Only the new capture/handoff composition and tiny ordinary-UID files execute
when separately authorized. Git/service/native process/clock/boot observations
remain explicit models; no GPG, provider, toolchain or external process runs.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import copy
import dataclasses
import importlib.util
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


F = load("worker_originals_initialization_models", "hosted-initial-recipient-initialization-test.py")
# Its existing native fixture installs the audit prohibition BEFORE project imports.
N, S, O, I, Q, C = F.N, F.S, F.O, F.I, F.Q, F.C
WORKER_REGISTRIES = (
    "_WORKER_READER_CAPTURES", "_WORKER_AUTHORITY_CAPTURES", "_WORKER_AUTHORITY_RETURNS",
    "_WORKER_CRYPTO_CAPTURES", "_WORKER_ORIGINAL_CAPTURES", "_WORKER_HANDOFF_ATTEMPTS")
ALL_REGISTRIES = (
    "_RECEIVING_WINDOWS", "_RECEIVING_CONTINUATIONS", "_RECEIVING_INIT_ATTEMPTS", "_RECEIVING_INIT_RETURNS",
    "_RECEIVING_CLOSED_RETURNS", "_AUTHORITY_WINDOWS", "_AUTHORITY_RETURNS", *WORKER_REGISTRIES)


class WorkerModel:
    """Supplied old-reader return, not validation of the modeled old history."""

    def __init__(self, case):
        self.case = case
        self.init = F.InitializationControls("runTest")
        case.addCleanup(self.init.doCleanups)
        self.init.setUp()
        self.rx, self.fx, self.stack = self.init.rx, self.init.fx, self.init.stack
        self.fx.complete_worker_queries = True
        case.addCleanup(self.cleanup)
        recipient = N._recipient_path()
        preparation = recipient.with_name(recipient.name.removesuffix("-recipient"))
        self.roots = {"P": preparation, "E": preparation.with_name(preparation.name + "-entry"), "R": recipient,
            "S": recipient.with_name(recipient.name + "-output"), "I": N._receiving_path(), "T": N._step_path(),
            "C": N._crypto_originals_path()}
        self.layout()
        self.stack.enter_context(patch.object(N, "_read_initial_recipient_originals", side_effect=self.supplied_return))
        self.stack.enter_context(patch.object(N, "_read_initial_query_originals",
            side_effect=AssertionError("NO_ACCEPTED_QUERY_READER_EXECUTION")))
        self.stack.enter_context(patch.object(N, "_capture_recipient_crypto_originals",
            side_effect=AssertionError("NO_ACCEPTED_CRYPTO_SCANNER_EXECUTION")))
        self.stack.enter_context(patch.object(N, "_retain_gate_handoff",
            side_effect=AssertionError("NO_GATE_HANDOFF_ON_WORKER_ROUTE")))

    def cleanup(self):
        # Fake-domain/tiny-file teardown only, not a production UNKNOWN repair.
        for attempt in N._WORKER_HANDOFF_ATTEMPTS.values():
            for value in attempt[4]:
                if type(value) is S.Owner:
                    for row in reversed(value.resources):
                        if row["label"] != "native-scope":
                            row["owner"].close()
        for name in WORKER_REGISTRIES:
            getattr(N, name).clear()

    def target(self, relative):
        pieces = relative.split("/")
        return self.roots[pieces[0]].joinpath(*pieces[1:])

    def put(self, target, raw):
        target.write_bytes(raw)
        target.chmod(0o600)

    @staticmethod
    def identity(path):
        value = path.stat()
        return [value.st_dev, value.st_ino]

    def layout(self):
        """Fixed named positions, tiny supplied bytes, no accepted generator."""
        old, rows, directories = dict(self.rx.graph), {}, set()
        stamp, clock = self.fx.fixture.ns, self.rx.clock
        read_end, read_local = stamp + 30 * O.NS, stamp / O.NS + 30
        context = O.parse(old["P/context.json"])
        context.update(root=str(F.ROOT), session=str(self.roots["P"]))
        records = {name: old["P/acquisition-queries/" + name + ".bin"] for name in N.ORIGINAL_KEYS}
        identity = N.initial_identity.bind_worker_match(N.acquisition.stages.BootstrapMatch(records["match"]),
            event_raw=records["event"], policy_raw=records["candidate_policy_raw"], now=context["observed"]["firstUseAt"])

        def add(name, raw=None):
            self.case.assertNotIn(name, rows)
            rows[name] = O.encoded({"syntheticSuppliedOriginal": name}) if raw is None else raw
            directories.add(name.rsplit("/", 1)[0])

        def query(key, acquisition=False):
            directories.add(key + "/query-home")
            add(key + "/owner.json")
            add(key + "/session-result.json")
            for name in N.ORIGINAL_KEYS if acquisition else N.SOURCE_KEYS:
                add(key + "/" + name + ".bin", records[name])
            if not acquisition:
                add(key + "/source-return.json", O.encoded({"syntheticSuppliedOriginal": key,
                    "clock": O.clock_value(clock), "returnedNs": stamp - 6000}))
            for number in range(1, 25 if acquisition else 13):
                parent = key + "/query-" + f"{number:032x}"
                for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"):
                    add(parent + "/" + name, b"" if name == "stderr.log" else None)

        for group, names in (
            ("P", ("prelude.json", "context.json", "worker-identity.json", "worker-service-time.json",
                "worker-allocation-proposal.json", "initial-result.json")),
            ("E", ("entry-window.json", "context.json", "entry-pending.json")),
            ("R/authority", ("authority-window.json", "context.json", "authority-pending.json"))):
            for name in names:
                add(group + "/" + name)
            for name in (*sorted(S.PHASE_FILES), "child-result.json"):
                add(group + "/service/" + name, b"" if name == "stderr.log" else None)
            directories.update(group + "/" + name for name in ("control-home", "temporary"))
            for name in ("source-before", "acquisition-queries", "source-after"):
                query(group + "/" + name, name == "acquisition-queries")
        for name in (*N.RECIPIENT_FILES, "recipient-context.json", "recipient-pending.json"):
            add("R/" + name)
        for name in (*sorted(S.PHASE_FILES), "child-result.json"):
            add("R/recipient-validation/" + name, b"" if name == "stderr.log" else None)
        for key in ("R/recipient-validation/source-before", "R/recipient-validation/source-after", "R/source-final"):
            query(key)
        for name in ("readmission-return.json", "recipient-return.json", "sender-pending.json"):
            add("S/" + name)
        directories.update("R/" + name for name in ("control-home", "temporary", "crypto"))
        self.case.assertEqual(len(rows), 1066)
        self.case.assertEqual({key: sum(name.split("/", 1)[0] == key for name in rows) for key in ("P", "E", "R", "S")},
            {"P": 284, "E": 281, "R": 498, "S": 3})
        self.case.assertEqual(len(directories), 222)
        for name in sorted(directories, key=lambda key: (key.count("/"), key)):
            self.target(name).mkdir(parents=True, mode=0o700, exist_ok=True)
        self.old_directories = tuple(sorted(directories))
        crypto = self.roots["R"] / "crypto"
        operations = ("gpg-model001", "gpg-model002")
        for name in ("gnupg", "tmp", *operations):
            (crypto / name).mkdir(mode=0o700)
        crypto_files = {"recipient.asc": identity.public_key, "recipient.gpg": b"SYNTHETIC_PUBLIC_RING_NOT_A_KEY\n"}
        for name in operations:
            crypto_files.update({name + "/stdout": b"SYNTHETIC_LISTING\n", name + "/stderr": b"",
                name + "/status": b"", name + "/process.json": b'{"synthetic":true}\n'})
        for name, raw in crypto_files.items():
            self.put(crypto / name, raw)
        start = O.parse(old["P/service/start.json"])
        context_raw = O.encoded(context)
        captured = (context_raw, tuple(records.items()), start["invocation"], start["startedNs"], start["workEndNs"])
        basis, proposal = N._worker_time_records(identity, captured, clock)
        rows.update({"P/context.json": context_raw, "P/service/start.json": old["P/service/start.json"],
            "P/worker-identity.json": identity.record, "P/worker-service-time.json": basis,
            "P/worker-allocation-proposal.json": proposal, "R/recipient-public.asc": identity.public_key,
            "R/recipient-context.json": O.encoded({"job": "c" * 32, "session": str(self.roots["R"]),
                "root": str(F.ROOT), "observed": context["observed"], "directories": {"crypto": self.identity(crypto)}}),
            "R/recipient-validation/child-result.json": O.encoded({"clock": O.clock_value(clock),
                "recipient": {"key_sha256": O.digest(identity.public_key), "work_identity": self.identity(crypto)}}),
            "R/recipient-validation/result.json": O.encoded({"readEndNs": read_end, "readbackCompletedNs": stamp - 8000}),
            "R/recipient-pending.json": O.encoded({"retainedNs": stamp - 5000}),
            "S/recipient-return.json": O.encoded({"preCloseNs": stamp - 4000, "closedNs": stamp - 3000}),
            "S/sender-pending.json": O.encoded({"readWindow": {"clock": O.clock_value(clock),
                "previousNs": stamp - 3000, "previousLocal": stamp / O.NS - 0.001,
                "retainedNs": stamp - 1000, "readEndNs": read_end, "readLocalCeiling": read_local}})})
        self.rx.graph = tuple(sorted(rows.items()))
        self.rx.sender_hash = O.digest(rows["S/sender-pending.json"])
        os.environ[N.RECEIVING_HASH_ENV] = self.rx.sender_hash
        for name, raw in self.rx.graph:
            self.put(self.target(name), raw)
        step_path = self.roots["T"] / C.STEP_FILE
        step = O.parse(step_path.read_bytes())
        step.update(senderSha256=self.rx.sender_hash, workerIdentitySha256=O.digest(identity.record),
            originalProposalSha256=O.digest(proposal), serviceJob=list(N._service_job(captured, clock)),
            lowerNs=stamp, lowerLocal=stamp / O.NS, readEndNs=read_end, readLocalCeiling=read_local)
        step_raw = O.encoded(step)
        self.put(step_path, step_raw)
        os.environ[C.STEP_HASH_ENV] = O.digest(step_raw)
        self.roots["C"].mkdir(mode=0o700)
        inventory = {"schema": 1, "scope": N.CRYPTO_ORIGINALS_SCOPE, "root": str(crypto),
            "contextSha256": O.digest(rows["R/recipient-context.json"]),
            "childSha256": O.digest(rows["R/recipient-validation/child-result.json"]),
            "phaseSha256": {name: O.digest(rows["R/recipient-validation/" + name]) for name in S.PHASE_FILES},
            "clock": O.clock_value(clock), "readEndNs": read_end, "readLocalCeiling": read_local, "capturedNs": stamp - 7000,
            "directories": [{"relative": name, "identity": self.identity(crypto / name),
                "members": sorted(path.name for path in (crypto / name).iterdir())} for name in ("", "gnupg", "tmp", *operations)],
            "files": [{"relative": name, "bytes": len(raw), "sha256": O.digest(raw)} for name, raw in sorted(crypto_files.items())],
            "totalBytes": sum(map(len, crypto_files.values())), "copyState": "ORIGINAL_BYTES_NOT_COPIED",
            "liveRecipient": "NOT_TRANSFERRED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.sidecar = {"schema": 1, "scope": N.CRYPTO_SIDECAR_SCOPE, "directory": str(self.roots["C"]),
            "directoryIdentity": self.identity(self.roots["C"]),
            "recipientValidationSha256": O.digest(rows["S/recipient-return.json"]), "recipientSenderSha256": self.rx.sender_hash,
            "recipientStepSha256": O.digest(step_raw), "inventory": inventory, "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.crypto_raw = O.encoded(self.sidecar)
        self.put(self.roots["C"] / N.CRYPTO_ORIGINALS_FILE, self.crypto_raw)
        os.environ[N.RECEIVING_CRYPTO_HASH_ENV] = O.digest(self.crypto_raw)

    def supplied_return(self, owner, directory, *, recipient_outcome, expected_sha256):
        self.case.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        self.case.assertEqual((recipient_outcome, expected_sha256), ("success", self.rx.sender_hash))
        self.case.assertIs(type(owner), S.Owner)
        self.case.assertIs(type(owner.fence), N._ReceivingWindow)
        self.case.assertFalse(owner.closed)
        self.case.assertEqual(directory.path, self.roots["S"])
        self.rx.read_calls.append((owner, owner.fence, owner.first, directory))
        for name in self.old_directories:
            if name != "S":
                owner.open(self.target(name))  # Explicit modeled reader's ownership tail; NO old-byte reread.
        self.fx.fixture.ns += self.rx.reader_delay
        if self.rx.reader_error is not None:
            raise self.rx.reader_error
        return self.rx.graph

    @contextmanager
    def active(self):
        with N._receive_initialization(self.fx.cancelled, crypto_sha256=os.environ[N.RECEIVING_CRYPTO_HASH_ENV]) as continuation:
            self.continuation = continuation
            self.result = N._initialize_receiving(continuation)
            self.anchor = N._capture_worker_originals(continuation, self.result)
            yield self.anchor

    def closed(self):
        with self.active():
            pass
        return self.anchor

    @property
    def state(self):
        return N._RECEIVING_WINDOWS[id(self.anchor[0].reader[0].window)]

    @property
    def handoff_path(self):
        return self.roots["I"].with_name(self.roots["I"].name + "-handoff")

    def handoff(self):
        return N._retain_worker_handoff(self.continuation, self.result, self.anchor, self.fx.cancelled)

    def metadata_owner(self):
        return N._WORKER_HANDOFF_ATTEMPTS[id(self.continuation)][4][0]

    def run_step(self):
        capture = N._capture_worker_originals
        def saved(continuation, result):
            self.continuation, self.result = continuation, result
            self.anchor = capture(continuation, result)
            return self.anchor
        with patch.object(N, "_capture_worker_originals", saved):
            return self.init.run_step()


class WorkerValueControls(unittest.TestCase):
    def test_file_scalars_logical_names_empty_digest_and_limits_are_closed(self):
        row = N._worker_file("P/source-before/query-" + "1" * 32 + "/stderr.log", 4096, 0,
            O.digest(b""), "ACTUAL_RETAINED_BYTES")
        self.assertEqual((row["maximum"], row["bytes"]), (1, 0))
        self.assertEqual(row["parent"], row["relative"].rsplit("/", 1)[0])
        base = ("I/authority/context.json", 4096, 3, O.digest(b"abc"), "ORIGINAL_AUTHORITY_QUERY_DECLARATION")
        bad = ((0, "X/context.json"), (0, "I/../outside"), (0, "I/a\\b"), (0, "I//context.json"),
            (1, True), (1, S.LIMIT + 1), (1, 2), (2, False), (2, -1), (3, "z" * 64), (4, "FRESH_COPY_PIN"))
        for index, value in bad:
            args = list(base)
            args[index] = value
            with self.subTest(index=index, value=value), self.assertRaises((I.AdmissionError, Q.QueryError)):
                N._worker_file(*args)
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_ORIGINAL_FILE"):
            N._worker_file("I/context.json", 1, 0, "1" * 64, "ACTUAL_RETAINED_BYTES")

    def test_handoff_embeds_exact_two_original_byte_strings_not_reencoded_records(self):
        authority, initialized = b'{ "supplied": "authority" }\n', b'{"supplied":"closed"}\n'
        raw = N._worker_handoff_record(Path("/supplied/I-handoff"), (7, 11), b'{"suppliedIndex":true}', authority, initialized)
        value = O.parse(raw)
        self.assertEqual([row["name"] for row in value["embeddedOriginals"]],
            ["receiving-authority-return.json", "initialization-history.json"])
        for row, original in zip(value["embeddedOriginals"], (authority, initialized)):
            self.assertEqual(set(row), {"name", "bytes", "sha256", "rawBase64"})
            self.assertEqual(base64.b64decode(row["rawBase64"], validate=True), original)
            self.assertEqual(row["rawBase64"], base64.b64encode(original).decode("ascii"))
            self.assertEqual((row["bytes"], row["sha256"]), (len(original), O.digest(original)))
        self.assertEqual(value["writerReturn"], "PENDING_OWNER_CLOSE")
        self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
        self.assertIs(value["exportSaveAuthority"], False)

    def test_manifest_cap_counts_base64_and_refuses_empty_or_nonstrict_originals(self):
        args = (Path("/supplied/I-handoff"), (7, 11), b"{}")
        for raw in (b"", bytearray(b"{}"), b"x" * (S.LIMIT + 1)):
            with self.subTest(kind=type(raw).__name__, count=len(raw)), self.assertRaisesRegex(I.AdmissionError, "WORKER_EMBEDDED_ORIGINAL_LIMIT"):
                N._worker_handoff_record(*args, raw, b"{}")
        # The shared bounded encoder refuses this base64-expanded record before
        # the handoff's additional length check. Require that exact refusal.
        with self.assertRaisesRegex(O.wire.BudgetError, "^JOB_TIME_RECORD_LIMIT$"):
            N._worker_handoff_record(*args, b"x" * (S.LIMIT // 2), b"y" * (S.LIMIT // 2))


class WorkerIndexControls(unittest.TestCase):
    def setUp(self):
        self.m = WorkerModel(self)

    def test_exact1371_files294_directories_original_hashes_empties_and_pin_provenance(self):
        anchor = self.m.closed()
        value = O.parse(anchor[0].raw)
        self.assertEqual(value["scope"], N.WORKER_INVENTORY_SCOPE)
        self.assertEqual(value["fileCount"], 1371)
        self.assertEqual(value["directoryCount"], 294)
        self.assertEqual(value["fileCounts"], {"P": 284, "E": 281, "R": 508, "S": 3, "I": 293, "T": 1, "C": 1})
        self.assertEqual(value["directoryCounts"], {"P": 58, "E": 58, "R": 109, "S": 1, "I": 66, "T": 1, "C": 1})
        self.assertEqual(value["roots"], [{"group": key, "path": str(path)} for key, path in self.m.roots.items()])
        files = {row["relative"]: row for row in value["files"]}
        directories = {row["relative"]: row for row in value["directories"]}
        self.assertEqual(list(files), sorted(files))
        self.assertEqual(list(directories), sorted(directories))
        self.assertTrue(set(files).isdisjoint(directories))
        for name, row in files.items():
            raw = self.m.target(name).read_bytes()
            self.assertEqual((row["bytes"], row["sha256"], row["maximum"]), (len(raw), O.digest(raw), max(1, len(raw))))
            self.assertIn(row["parent"], directories)
        self.assertEqual(value["totalBytes"], sum(row["bytes"] for row in files.values()))
        self.assertTrue(any(row["bytes"] == 0 for row in files.values()))
        self.assertEqual(sum(row["identity"] is None for row in directories.values()), 51)
        self.assertEqual(sum(row["provenance"] == "RECEIVER_READBACK_NATIVE_PIN" for row in directories.values()), 222)
        self.assertEqual(sum(row["provenance"] == "ORIGINAL_AUTHORITY_NATIVE_PIN" for row in directories.values()), 7)
        for name in ("P/control-home", "E/temporary", "R/authority/source-before/query-home", "I/state/evidence",
                     "I/state/cancellations", "R/crypto/gnupg", "R/crypto/tmp"):
            self.assertIn(name, directories)
            self.assertEqual(list(self.m.target(name).iterdir()), [])
        self.assertEqual(sum(row["provenance"] == "ORIGINAL_AUTHORITY_QUERY_DECLARATION" for row in files.values()), 243)
        self.assertEqual(sum(row["provenance"] == "AUTHENTICATED_CRYPTO_DECLARATION" for row in files.values()), 10)
        self.assertEqual(value["copyState"], "ORIGINAL_BYTES_NOT_COPIED")
        self.assertEqual(value["liveRecipient"], "NOT_TRANSFERRED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(value["exportSaveAuthority"], False)
        self.assertEqual(len(self.m.rx.read_calls), 1)
        self.assertFalse(N._RECEIVING_CLOSED_RETURNS)
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_capture_precedes_bind_and_authority_uses_only_original281_index_and_seven_pins(self):
        bind, capture, seen = N._bind_receiving_originals, N._capture_worker_authority, []
        def bound(window, original):
            anchor = N._WORKER_READER_CAPTURES[id(window)]
            self.assertIs(anchor[0].originals, original)
            self.assertIs(original, self.m.rx.graph)
            self.assertIsNone(window.state().raw)
            self.assertEqual(len(anchor[0].pins), 224)
            seen.append("reader")
            return bind(window, original)
        def authority(*args):
            self.assertFalse(args[2].closed)
            self.assertFalse(N._WORKER_AUTHORITY_RETURNS)
            anchor = capture(*args)
            self.assertEqual((len(anchor[0].files), len(anchor[0].directories), len(anchor[0].pins)), (281, 58, 7))
            self.assertEqual(sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in anchor[0].files), 38)
            seen.append("authority")
            return anchor
        with patch.object(N, "_bind_receiving_originals", bound), patch.object(N, "_capture_worker_authority", authority):
            self.m.closed()
        self.assertEqual(seen, ["reader", "authority"])
        self.assertEqual([len(query.calls) for query in self.m.fx.queries], [12, 24, 12])
        self.assertTrue(all(query.closed and query.finalizations == 1 for query in self.m.fx.queries))
        original = self.m.anchor[0].authority
        self.assertEqual(len(original[2]), 6)  # Original authority return shape unchanged.
        self.assertIs(original[2][0], original[0])
        self.assertEqual(original[1], original[0].raw)
        self.assertEqual(len(self.m.result.originals), 11)
        self.assertEqual(len(N._RECEIVING_INIT_RETURNS[id(self.m.result)]), 6)

    def test_copied_reader_tuple_before_binding_cannot_authenticate_itself(self):
        bind = N._bind_receiving_originals
        def copied(window, original):
            return bind(window, tuple(list(original)))
        with patch.object(N, "_bind_receiving_originals", copied), self.assertRaisesRegex(I.AdmissionError, "WORKER_READER_TUPLE_REPLACED"):
            self.m.closed()
        self.assertEqual(self.m.fx.queries, [])
        self.assertFalse(N._RECEIVING_INIT_RETURNS)
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_replaced_receiving_roster_after_bind_cannot_become_original(self):
        bind = N._bind_receiving_originals
        def copied(window, original):
            bind(window, original)
            state = N._RECEIVING_WINDOWS[id(window)]
            N._RECEIVING_WINDOWS[id(window)] = dataclasses.replace(state, roster=copy.copy(state.roster))
        with patch.object(N, "_bind_receiving_originals", copied), self.assertRaisesRegex(I.AdmissionError, "WORKER_READER_RECEIVING_CHANGED"):
            self.m.closed()
        self.assertEqual(self.m.fx.queries, [])
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_supplement_mutations_and_native_pin_replacements_refuse_closed_accessor(self):
        anchor = self.m.closed()
        original, reader, crypto, authority = anchor[0], anchor[0].reader[0], anchor[0].crypto[0], anchor[0].authority[4][0]
        directory = reader.pins[0][2]
        changes = ((original, "raw", original.raw + b"changed"),
            (reader, "originals", tuple(list(reader.originals))), (crypto, "raw", crypto.raw + b"changed"),
            (authority, "files", tuple(dict(row) for row in authority.files)),
            (reader.step[0], "__dict__", dict(reader.step[0].__dict__)),
            (directory, "path", Path(str(directory.path))),
            (directory, "identity", (directory.identity[0], directory.identity[1] + 1)))
        for target, name, value in changes:
            saved = getattr(target, name)
            object.__setattr__(target, name, value)
            try:
                with self.subTest(name=name), self.assertRaises(I.AdmissionError):
                    N._check_worker_originals(anchor, closed=True)
            finally:
                object.__setattr__(target, name, saved)
        row = authority.files[0]
        saved = dict(row)
        row["bytes"] += 1
        try:
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                N._check_worker_originals(anchor, closed=True)
        finally:
            row.clear()
            row.update(saved)
        self.assertIs(N._check_worker_originals(anchor, closed=True), original)

    def test_registry_container_and_return_entry_copies_do_not_rebind_originals(self):
        anchor = self.m.closed()
        for name in ALL_REGISTRIES:
            with self.subTest(name=name), patch.object(N, name, dict(getattr(N, name))), self.assertRaisesRegex(I.AdmissionError, "WORKER_"):
                N._check_worker_originals(anchor, closed=True)
        for registry, key in ((N._RECEIVING_CONTINUATIONS, id(self.m.continuation)),
                (N._RECEIVING_INIT_ATTEMPTS, id(self.m.continuation)), (N._RECEIVING_INIT_RETURNS, id(self.m.result)),
                (N._AUTHORITY_RETURNS, id(anchor[0].authority[0])),
                (N._WORKER_AUTHORITY_RETURNS, id(anchor[0].authority[0]))):
            old = registry[key]
            registry[key] = tuple(list(old))
            try:
                with self.subTest(key=key), self.assertRaises(I.AdmissionError):
                    N._check_worker_originals(anchor, closed=True)
            finally:
                registry[key] = old
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_AUTHORITY_NOT_ORIGINAL_RETURN"):
            N._worker_authority_return(dataclasses.replace(anchor[0].authority[0]))
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_original_step_dictionary_and_boot_cannot_be_replaced_at_receiving_close(self):
        close, changed = S.Owner.close, []
        def replacement(owner):
            close(owner)
            if hasattr(owner, "_worker_reader_capture"):
                step = owner._worker_reader_capture.step[0]
                object.__setattr__(step, "__dict__", {**step.__dict__, "boot": "d" * 64})
                self.m.stack.enter_context(patch.object(C, "boot_digest", return_value="d" * 64))
                changed.append(step)
        with patch.object(S.Owner, "close", replacement), self.assertRaises(I.AdmissionError):
            self.m.closed()
        self.assertEqual(len(changed), 1)
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertFalse(self.m.handoff_path.exists())
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_later_initializer_cannot_replace_supplemental_authority_return_and_declarations(self):
        changed = []
        def replacement():
            state = self.m.init.window().state()
            returned = N._WORKER_AUTHORITY_RETURNS[id(state.authority)]
            anchor = returned[4]
            capture, owner, _window, _episode, evidence, files, directories, pins, roster, _binding, _graph, _registries = anchor
            target = next(row["relative"] for row in files if row["provenance"] == "ORIGINAL_AUTHORITY_QUERY_DECLARATION"
                and row["bytes"] > 0)
            forged = tuple({**row, **({"sha256": "f" * 64} if row["relative"] == target else {})} for row in files)
            object.__setattr__(capture, "files", forged)
            path = next(path for key, _row, _directory, path, _identity in pins if key == "I/authority")
            graph = N._history_graph(evidence, path, roster.first) + N._history_graph(forged, directories,
                tuple(path for _key, _row, _directory, path, _identity in pins))
            substitute = (*anchor[:5], forged, *anchor[6:10], graph, anchor[11])
            N._WORKER_AUTHORITY_CAPTURES[id(owner)] = substitute
            N._WORKER_AUTHORITY_RETURNS[id(state.authority)] = (*returned[:4], substitute, returned[5])
            # Ordinary closed raw, actual return object and old history stay
            # byte-for-byte untouched; only its opaque supplement is attacked.
            self.assertEqual(state.authority.raw, returned[1])
            changed.append(target)
        self.m.init.before_init = replacement
        with self.assertRaises(I.AdmissionError):
            self.m.closed()
        self.assertEqual(len(changed), 1)
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertEqual(self.m.init.output.read_bytes(), b"")


class WorkerCryptoControls(unittest.TestCase):
    def setUp(self):
        self.m = WorkerModel(self)

    def index(self, value=None, *, expected=None):
        raw = self.m.crypto_raw if value is None else O.encoded(value)
        original = self.m.anchor[0]
        return N._worker_crypto_index(raw, original.reader, original.crypto[0].pin,
            O.digest(raw) if expected is None else expected)

    def test_one_fixed_sidecar_read_binds_transport_and_original_crosslinks(self):
        read, names = S.Owner.read, []
        def tracked(owner, directory, name, *args, **kwargs):
            if directory.path == self.m.roots["C"]:
                names.append((name, args))
            return read(owner, directory, name, *args, **kwargs)
        with patch.object(S.Owner, "read", tracked), self.m.active():
            files, directories = self.index()
            self.assertEqual((len(files), len(directories)), (10, 4))
            self.assertTrue(all(row["provenance"] == "AUTHENTICATED_CRYPTO_DECLARATION" for row in files))
            self.assertEqual(self.m.anchor[0].crypto[0].raw, self.m.crypto_raw)
            with self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_TRANSPORT_HASH"):
                self.index(expected="0" * 64)
        self.assertEqual(names, [(N.CRYPTO_ORIGINALS_FILE, (S.LIMIT,))])

    def test_sidecar_schema_transport_links_and_original_chronology_refuse_rehashed_changes(self):
        changes = (
            lambda v: v.update(schema=True), lambda v: v.update(extra="not-a-field"),
            lambda v: v.update(directory=v["directory"] + "-other"),
            lambda v: v.update(recipientValidationSha256="0" * 64),
            lambda v: v.update(recipientSenderSha256="0" * 64),
            lambda v: v.update(recipientStepSha256="0" * 64),
            lambda v: v.update(writerReturn="KNOWN_CLOSE"), lambda v: v.update(exportSaveAuthority=True),
            lambda v: v["inventory"].update(contextSha256="0" * 64),
            lambda v: v["inventory"].update(childSha256="0" * 64),
            lambda v: v["inventory"]["phaseSha256"].update({"stderr.log": "0" * 64}),
            lambda v: v["inventory"].update(readEndNs=v["inventory"]["readEndNs"] + 1),
            lambda v: v["inventory"].update(readLocalCeiling=v["inventory"]["readLocalCeiling"] + 1),
            lambda v: v["inventory"].update(capturedNs=v["inventory"]["capturedNs"] + 2000),
        )
        with self.m.active():
            for number, change in enumerate(changes):
                value = copy.deepcopy(self.m.sidecar)
                change(value)
                with self.subTest(number=number), self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_"):
                    self.index(value)
            self.assertEqual(len(self.index()[0]), 10)

    def test_crypto_exact_names_typed_sizes_identity_roster_and_declared_total_refuse(self):
        changes = (
            lambda v: v["files"].pop(), lambda v: v["files"].append(dict(v["files"][-1])),
            lambda v: v["files"].reverse(), lambda v: v["files"][0].update(bytes=True),
            lambda v: v["files"][0].update(sha256="not-a-hash"),
            lambda v: next(row for row in v["files"] if row["bytes"] == 0).update(sha256="1" * 64),
            lambda v: next(row for row in v["files"] if row["relative"] == "recipient.asc").update(sha256="0" * 64),
            lambda v: next(row for row in v["files"] if row["relative"] == "recipient.gpg").update(bytes=0, sha256=O.digest(b"")),
            lambda v: v["directories"][1].update(identity=v["directories"][0]["identity"]),
            lambda v: v["directories"][0]["members"].append("undeclared"),
            lambda v: v["directories"][-1]["members"].pop(),
            lambda v: v.update(totalBytes=True), lambda v: v.update(totalBytes=v["totalBytes"] + 1),
        )
        with self.m.active():
            for number, change in enumerate(changes):
                value = copy.deepcopy(self.m.sidecar)
                change(value["inventory"])
                with self.subTest(number=number), self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_|WORKER_ORIGINAL_FILE"):
                    self.index(value)
            large = copy.deepcopy(self.m.sidecar)
            inventory = large["inventory"]
            for directory in inventory["directories"][1:3]:
                directory["members"] = ["model-" + f"{number:02d}" for number in range(32)]
                inventory["files"].extend({"relative": directory["relative"] + "/" + name,
                    "bytes": S.LIMIT, "sha256": "1" * 64} for name in directory["members"])
            inventory["files"].sort(key=lambda row: row["relative"])
            inventory["totalBytes"] = sum(row["bytes"] for row in inventory["files"])
            self.assertEqual(len(inventory["files"]), 74)
            self.assertGreater(inventory["totalBytes"], 16 * 1024 * 1024)
            with self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_TOTAL_LIMIT"):
                self.index(large)  # Only small declarations, never these large bytes.

    def test_replaced_transported_hash_after_capture_cannot_rebind_custody(self):
        anchor = self.m.closed()
        with patch.dict(os.environ, {N.RECEIVING_CRYPTO_HASH_ENV: "0" * 64}), \
                self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_CAPTURE_CHANGED"):
            N._check_worker_originals(anchor, closed=True)
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_windows_nine_file_five_nested_directory_schema_is_only_a_supplied_parser_model(self):
        # This call isolates the NEW declaration parser. No Windows owner,
        # clock observation, actual returned capability or native identity is
        # asserted. Linux live composition has separate direct controls above.
        with self.m.active():
            original = self.m.anchor[0].reader[0]
            rows, roots = dict(original.originals), dict(original.roots)
            clock = O.clocks.ClockIdentity("windows-x64", O.clocks.DOMAINS["windows-x64"], 10_000_000)
            root_id, c_id = [7, "1" * 32], [7, "2" * 32]
            context, child = O.parse(rows["R/recipient-context.json"]), O.parse(rows["R/recipient-validation/child-result.json"])
            context["directories"]["crypto"] = root_id
            child["clock"], child["recipient"]["work_identity"] = O.clock_value(clock), root_id
            rows["R/recipient-context.json"], rows["R/recipient-validation/child-result.json"] = O.encoded(context), O.encoded(child)
            sender, source = O.parse(rows["S/sender-pending.json"]), O.parse(rows["R/source-final/source-return.json"])
            sender["readWindow"]["clock"], source["clock"] = O.clock_value(clock), O.clock_value(clock)
            rows["S/sender-pending.json"], rows["R/source-final/source-return.json"] = O.encoded(sender), O.encoded(source)
            step = O.parse(original.step[0].raw)
            step.update(clock=O.clock_value(clock), directoryIdentity=[7, "3" * 32], senderSha256=O.digest(rows["S/sender-pending.json"]))
            step_raw = O.encoded(step)
            window = object()
            reader_capture = dataclasses.replace(original, window=window, originals=tuple(rows.items()),
                pins=(("R/crypto", None, None, roots["R"] / "crypto", tuple(root_id)),),
                step=(SimpleNamespace(raw=step_raw), None))
            reader = (reader_capture,)
            state = SimpleNamespace(clock=clock, clock_raw=O.encoded(O.clock_value(clock)),
                step=("success", step["senderSha256"]), step_hash=O.digest(step_raw),
                local_start=self.m.state.local_start, first=self.m.state.first)
            value = copy.deepcopy(self.m.sidecar)
            value.update(directoryIdentity=c_id, recipientSenderSha256=step["senderSha256"], recipientStepSha256=O.digest(step_raw))
            inventory = value["inventory"]
            inventory.update(contextSha256=O.digest(rows["R/recipient-context.json"]),
                childSha256=O.digest(rows["R/recipient-validation/child-result.json"]), clock=O.clock_value(clock))
            operations = tuple("gpg-" + f"{number:032x}" for number in range(1, 4))
            result_name = "recipient-validation-result-" + "a" * 32 + ".json"
            files = {"recipient.asc": rows["R/recipient-public.asc"], "recipient.gpg": b"MODEL_RING", result_name: b"{}"}
            for name in operations:
                files.update({name + "/stdout": b"MODEL_LISTING", name + "/stderr": b""})
            inventory["files"] = [{"relative": name, "bytes": len(raw), "sha256": O.digest(raw)} for name, raw in sorted(files.items())]
            inventory["totalBytes"] = sum(map(len, files.values()))
            inventory["directories"] = [{"relative": "", "identity": root_id,
                "members": sorted(("recipient.asc", "recipient.gpg", "gnupg", "tmp", *operations, result_name))}]
            inventory["directories"].extend({"relative": name, "identity": [7, f"{number:032x}"],
                "members": [] if name in ("gnupg", "tmp") else ["stderr", "stdout"]}
                for number, name in enumerate(("gnupg", "tmp", *operations), 11))
            pin = ("C", None, None, roots["C"], tuple(c_id))
            def supplied(actual, **kwargs):
                self.assertIs(actual, reader)
                self.assertEqual(kwargs, {})
                return reader_capture
            def parse(row):
                raw = O.encoded(row)
                return N._worker_crypto_index(raw, reader, pin, O.digest(raw))
            with patch.dict(N._RECEIVING_WINDOWS, {id(window): state}), patch.object(N, "_check_worker_reader", supplied):
                indexed, nested = parse(value)
                self.assertEqual((len(indexed), len(nested)), (9, 5))
                self.assertEqual(1361 + len(indexed), 1370)
                self.assertTrue(all(type(identity[1]) is str for _name, identity in nested))
                changed = copy.deepcopy(value)
                changed["inventory"]["directories"][1]["members"] = ["not-empty"]
                with self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_WINDOWS_HOME_NOT_EMPTY"):
                    parse(changed)
                changed = copy.deepcopy(value)
                changed["inventory"]["directories"][-1]["members"].append("status")
                with self.assertRaisesRegex(I.AdmissionError, "WORKER_CRYPTO_OPERATION_ROSTER|WORKER_CRYPTO_DIRECTORIES"):
                    parse(changed)


class WorkerHandoffControls(unittest.TestCase):
    def setUp(self):
        self.m = WorkerModel(self)

    def assert_spent_without_output(self):
        attempt = N._WORKER_HANDOFF_ATTEMPTS[id(self.m.continuation)]
        self.assertIs(attempt[0], self.m.continuation)
        self.assertEqual(self.m.init.output.read_bytes(), b"")
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_HANDOFF_ALREADY_CLAIMED"):
            self.m.handoff()
        self.assertIs(N._WORKER_HANDOFF_ATTEMPTS[id(self.m.continuation)], attempt)

    def test_fixed_step_closes_one_metadata_sibling_before_append_and_exact_two_guarded_checks(self):
        append, now, end = C.append_outputs, N._ReceivingWindow.now, S.Owner.end
        outputs, deadlines = [], []
        def active_only(window, **kwargs):
            self.assertFalse(window.state(cleanup=True).terminal, "no active retired receiver observation")
            return now(window, **kwargs)
        def deadline(owner, **kwargs):
            value = end(owner, **kwargs)
            if type(owner.fence).__name__ == "MetadataFence":
                deadlines.append(value)
                self.assertLessEqual(value, self.m.state.locals[0])
                self.assertEqual(owner.local_end, self.m.state.locals[0])
                self.assertGreaterEqual(owner.first.nanoseconds, self.m.state.last)
            return value
        def appended(values, check):
            owner = self.m.metadata_owner()
            self.assertTrue(self.m.state.terminal and self.m.state.roster.owner.closed)
            self.assertTrue(owner.closed)
            self.assertFalse(owner.unknown)
            self.assertIsNone(owner.original)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))
            self.assertEqual([row["label"] for row in owner.resources], ["directory", "writer"])
            self.assertIs(owner.cancelled, self.m.state.cancelled)
            self.assertIsNot(owner.fence, self.m.state.window)
            outputs.append(dict(values))
            return append(values, check)
        with patch.object(C, "append_outputs", appended), patch.object(N._ReceivingWindow, "now", active_only), \
                patch.object(S.Owner, "end", deadline):
            public = self.m.run_step()
        self.assertTrue(deadlines)
        raw = (self.m.handoff_path / N.WORKER_HANDOFF_FILE).read_bytes()
        value = O.parse(raw)
        self.assertEqual(tuple(path.name for path in self.m.handoff_path.iterdir()), (N.WORKER_HANDOFF_FILE,))
        self.assertEqual(value["scope"], N.WORKER_HANDOFF_SCOPE)
        self.assertEqual(value["inventory"], O.parse(self.m.anchor[0].raw))
        self.assertEqual(value["directory"], str(self.m.handoff_path))
        self.assertEqual(value["directoryIdentity"], self.m.identity(self.m.handoff_path))
        closed = N._RECEIVING_CLOSED_RETURNS[id(self.m.continuation)]
        self.assertEqual(len(closed), 4)
        embedded = tuple(base64.b64decode(row["rawBase64"], validate=True) for row in value["embeddedOriginals"])
        self.assertEqual(embedded, (self.m.anchor[0].authority[1], closed[3]))
        self.assertEqual(value["originalClose"], {"authority": "KNOWN_RESOURCE_CLOSE_ONLY", "receiving": "KNOWN_RESOURCE_CLOSE_ONLY"})
        self.assertEqual((value["writerReturn"], value["originalStepOutcome"]), ("PENDING_OWNER_CLOSE", "NOT_OBSERVED"))
        expected = {"initializationSha256": O.digest(self.m.result.pending), "workerHandoffSha256": O.digest(raw)}
        self.assertEqual(outputs, [expected])
        self.assertEqual(dict(line.split("=", 1) for line in self.m.init.output.read_text().splitlines()), expected)
        self.assertEqual(len(public), 1)
        public_value = O.parse(public[0])
        self.assertEqual(public_value, {"scope": "INITIAL_RECIPIENT_INITIALIZATION_PENDING_STEP_RETURN_V1", **expected,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        self.assertEqual(self.m.init.init_events, ["construct", "spawn", "drain", "close"])
        self.assertEqual(len(self.m.rx.read_calls), 1)
        self.assertEqual(self.m.state.work, self.m.state.first + 120 * O.NS)
        returned = self.m.init.packet
        self.assertFalse(hasattr(returned[1], "deadline"))
        # guarded already used both checks. No third output observation/replay.
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_OUTPUT_FINAL_ONLY"):
            returned[1].now(final=True, limit=returned[2])
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_HANDOFF_ALREADY_CLAIMED"):
            self.m.handoff()

    def test_no_handoff_before_receiving_close_and_copied_continuation_has_no_authority(self):
        with self.m.active():
            with self.assertRaisesRegex(I.AdmissionError, "WORKER_ORIGINAL_OWNER_FAILED"):
                self.m.handoff()
            self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_CLOSED_RETURN"):
            N._retain_worker_handoff(copy.copy(self.m.continuation), self.m.result, self.m.anchor, self.m.fx.cancelled)
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertFalse(self.m.handoff_path.exists())

    def test_unknown_actual_receiving_close_never_starts_metadata_owner(self):
        close, first = S.Owner.close, F.R.FirstFailure("SYNTHETIC_RECEIVER_CLOSE_UNKNOWN")
        def unknown(owner):
            close(owner)
            if hasattr(owner, "_worker_reader_capture"):
                owner.error("synthetic-receiver-close", first, unknown=True)
        with patch.object(S.Owner, "close", unknown), self.assertRaises(F.R.FirstFailure) as caught:
            self.m.closed()
        self.assertIs(caught.exception, first)
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertFalse(self.m.handoff_path.exists())
        self.assertEqual(self.m.init.output.read_bytes(), b"")

    def test_preexisting_sibling_is_not_overwritten_and_consumption_precedes_allocation(self):
        self.m.closed()
        self.m.handoff_path.mkdir(mode=0o700)
        sentinel = self.m.handoff_path / "unrelated"
        self.m.put(sentinel, b"PRESERVE_EXISTING_TINY_MODEL\n")
        with self.assertRaises((I.AdmissionError, O.OriginError, Q.QueryError, FileExistsError)):
            self.m.handoff()
        self.assertEqual(sentinel.read_bytes(), b"PRESERVE_EXISTING_TINY_MODEL\n")
        self.assert_spent_without_output()

    def test_changed_metadata_readback_has_no_hash_output_or_second_attempt(self):
        self.m.closed()
        read, calls = S.Owner.read, []
        def changed(owner, directory, name, *args, **kwargs):
            raw = read(owner, directory, name, *args, **kwargs)
            if directory.path == self.m.handoff_path:
                calls.append(name)
                return raw + b"changed"
            return raw
        with patch.object(S.Owner, "read", changed), self.assertRaises((I.AdmissionError, O.OriginError)):
            self.m.handoff()
        self.assertTrue(calls)
        self.assertTrue(self.m.metadata_owner().closed)
        self.assert_spent_without_output()

    def test_partial_metadata_ledger_close_is_not_known_complete_close(self):
        self.m.closed()
        close, changed = S.Owner.close, []
        def partial(owner):
            close(owner)
            if type(owner.fence).__name__ == "MetadataFence":
                owner.resources[-1]["closed"] = False
                changed.append(owner)
        with patch.object(S.Owner, "close", partial), self.assertRaises(I.AdmissionError):
            self.m.handoff()
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0].closed)
        self.assertTrue(changed[0].unknown)
        self.assertTrue(any(owner is changed[0] for owner in S.QUARANTINE))
        self.assert_spent_without_output()

    def test_unknown_metadata_close_preserves_falsey_first_error_and_original_resources(self):
        self.m.closed()
        close, first = S.Owner.close, F.R.FirstFailure("SYNTHETIC_METADATA_UNKNOWN")
        def unknown(owner):
            close(owner)
            if type(owner.fence).__name__ == "MetadataFence":
                owner.error("synthetic-metadata-close", first, unknown=True)
        with patch.object(S.Owner, "close", unknown), self.assertRaises(F.R.FirstFailure) as caught:
            self.m.handoff()
        self.assertIs(caught.exception, first)
        owner = self.m.metadata_owner()
        self.assertTrue(owner.closed and owner.unknown)
        self.assertIs(owner.original, first)
        self.assertTrue(any(value is owner for value in S.QUARANTINE))
        self.assertEqual(len(owner.resources), 2)
        self.assert_spent_without_output()

    def test_metadata_raw_expiry_spends_original120_and_cannot_start_another_interval(self):
        self.m.closed()
        self.m.fx.fixture.ns = self.m.state.work
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT120_OUTPUT_EXPIRED"):
            self.m.handoff()
        self.assertEqual(N._WORKER_HANDOFF_ATTEMPTS[id(self.m.continuation)][4], [])
        self.assert_spent_without_output()

    def test_metadata_local_expiry_refuses_even_when_raw_still_before_work_end(self):
        self.m.closed()
        self.assertLess(self.m.fx.fixture.ns, self.m.state.work)
        with patch.object(N.time, "monotonic", return_value=self.m.state.locals[0]), \
                self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT120_OUTPUT_EXPIRED"):
            self.m.handoff()
        self.assert_spent_without_output()

    def test_metadata_boot_change_is_not_a_fresh_step_or_output_authority(self):
        self.m.closed()
        with patch.object(C, "boot_digest", return_value="d" * 64), \
                self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_OUTPUT_BOOT_CHANGED"):
            self.m.handoff()
        self.assert_spent_without_output()

    def test_metadata_cancellation_is_preserved_before_any_owner_allocation(self):
        self.m.closed()
        self.m.fx.cancelled.append(signal.SIGTERM)
        with self.assertRaisesRegex(KeyboardInterrupt, "BOOTSTRAP_ORIGIN_CANCELLED"):
            self.m.handoff()
        self.assertEqual(N._WORKER_HANDOFF_ATTEMPTS[id(self.m.continuation)][4], [])
        self.assert_spent_without_output()

    def test_reentry_during_metadata_deadline_is_sticky_even_if_callback_swallows_failure(self):
        self.m.closed()
        end, observe, reentered = S.Owner.end, O.clocks.observe, []
        def deadline(owner, **kwargs):
            if type(owner.fence).__name__ != "MetadataFence" or reentered:
                return end(owner, **kwargs)
            def callback():
                if not reentered:
                    reentered.append(owner)
                    with self.assertRaisesRegex(I.AdmissionError, "WORKER_HANDOFF_METADATA_ONLY"):
                        owner.fence.now()
                return observe()
            with patch.object(O.clocks, "observe", callback):
                return end(owner, **kwargs)
        with patch.object(S.Owner, "end", deadline), self.assertRaisesRegex(I.AdmissionError, "WORKER_HANDOFF_METADATA_ONLY"):
            self.m.handoff()
        self.assertEqual(len(reentered), 1)
        self.assert_spent_without_output()

    def test_file_command_failure_leaves_pending_record_but_never_a_successful_return(self):
        self.m.closed()
        first = F.R.FirstFailure("SYNTHETIC_FILE_COMMAND_FAILURE")
        with patch.object(C, "append_outputs", side_effect=first), self.assertRaises(F.R.FirstFailure) as caught:
            self.m.handoff()
        self.assertIs(caught.exception, first)
        self.assertTrue(self.m.metadata_owner().closed)
        self.assertEqual(O.parse((self.m.handoff_path / N.WORKER_HANDOFF_FILE).read_bytes())["originalStepOutcome"], "NOT_OBSERVED")
        self.assert_spent_without_output()

    def test_late_guarded_flush_failure_does_not_upgrade_escaped_hashes_to_step_success(self):
        self.m.closed()
        returned = self.m.handoff()
        public = []
        def late_flush():
            self.m.stack.enter_context(patch.object(C, "boot_digest", return_value="d" * 64))
        stdout = SimpleNamespace(buffer=SimpleNamespace(write=lambda raw: (public.append(raw), len(raw))[1], flush=late_flush))
        with patch.object(S.sys, "stdout", stdout), self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_OUTPUT_BOOT_CHANGED"):
            S.guarded(lambda _cancelled: returned)
        self.assertEqual(len(public), 1)
        self.assertEqual(len(self.m.init.output.read_text().splitlines()), 2)
        self.assertEqual(O.parse((self.m.handoff_path / N.WORKER_HANDOFF_FILE).read_bytes())["originalStepOutcome"], "NOT_OBSERVED")
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_OUTPUT_FINAL_ONLY"):
            returned[1].now(final=True, limit=returned[2])

    def test_fixed_completing_route_requires_crypto_but_bare_initializer_seam_does_not_export(self):
        os.environ.pop(N.RECEIVING_CRYPTO_HASH_ENV)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_FIXED_CRYPTO_HASH_REQUIRED"):
            N._initialize_step(self.m.fx.cancelled)
        self.assertEqual(self.m.rx.read_calls, [])
        with N._receive_initialization(self.m.fx.cancelled) as continuation:
            result = N._initialize_receiving(continuation)
        self.assertIs(N._receiving_initialization_return(continuation, closed=True), result)
        self.assertFalse(N._WORKER_CRYPTO_CAPTURES)
        self.assertFalse(N._WORKER_ORIGINAL_CAPTURES)
        self.assertFalse(N._WORKER_HANDOFF_ATTEMPTS)
        self.assertFalse(self.m.handoff_path.exists())
        self.assertEqual(self.m.init.output.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main(failfast=True)
