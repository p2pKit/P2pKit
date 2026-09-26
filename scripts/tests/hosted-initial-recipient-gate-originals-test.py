#!/usr/bin/env python3
"""Focused gate-only custody models, NOT native/hosted/provider acceptance.

Only tiny ordinary-UID files and the existing explicit Git/service/clock models
are used. No old test method, accepted1,066-file generator/reader, native child,
crypto, network, toolchain or provider executes. All new methods are direct
TestCase controls; importing the fixture does not select its old methods.
"""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


F = load("gate_originals_native_models", "hosted-initial-recipient-native-test.py")
# The existing fixture installs its process/network/native guard BEFORE project imports.
N, S, O, I, Q, C = F.N, F.S, F.O, F.I, F.Q, F.N.continuity


def fixture(case):
    value = F.NativeModels("runTest")
    case.addCleanup(value.doCleanups)
    value.setUp()
    return value


class GateInventoryControls(unittest.TestCase):
    def setUp(self):
        self.fx = fixture(self)
        build, observed = N._gate_inventory, []
        def retain(*args):
            raw = build(*args)
            observed.append(args)
            return raw
        with patch.object(N, "_gate_inventory", retain):
            self.original = N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(observed), 1)
        self.inputs = dict(zip(("path", "prelude_raw", "context_raw", "before", "after", "phase", "match", "chain",
            "captured", "child_raw", "session_raw", "result_raw"), observed[0]))
        self.capture = N._gate_return(self.original)[2][0]

    def index(self, **changes):
        return N._gate_inventory(**{**self.inputs, **changes})

    def parts(self, name):
        source = self.inputs["before" if name == "source-before" else "after"] if name != "acquisition-queries" else None
        raw = self.inputs["session_raw"] if source is None else source.session
        data = dict(self.inputs["captured"][1] if source is None else source.records)
        return self.fx.path / name, raw, data, source

    def query(self, name="source-before", *, session=None, originals=None):
        path, raw, data, source = self.parts(name)
        if session is not None:
            raw = session if type(session) is bytes else Q.encoded(session)
            if source is not None:
                # Challenge the grammar itself, not just a stale sidecar digest.
                # The separate same-call return tests prohibit adopting this copy.
                side = O.parse(source.raw)
                side["sessionSha256"] = O.digest(raw)
                source = dataclasses.replace(source, session=raw, raw=O.encoded(side))
        return N._gate_query_index(path, raw, data if originals is None else originals, source=source)

    def test_exact281_files58_directories_and65_136_65_readbacks_preserve_original_hashes(self):
        value = O.parse(self.index())
        self.assertEqual(value["scope"], N.GATE_INVENTORY_SCOPE)
        self.assertEqual(len(value["files"]), 281)
        self.assertEqual(len(value["directories"]), 58)
        files = {row["relative"]: row for row in value["files"]}
        self.assertEqual(len(files), 281)
        self.assertEqual(list(files), sorted(files))
        self.assertEqual(value["directories"], sorted(set(value["directories"])))
        actual_files = {str(path.relative_to(self.fx.path)) for path in self.fx.path.rglob("*") if path.is_file()}
        actual_dirs = {".", *(str(path.relative_to(self.fx.path)) for path in self.fx.path.rglob("*") if path.is_dir())}
        self.assertEqual(set(files), actual_files)
        self.assertEqual(set(value["directories"]), actual_dirs)
        for name, row in files.items():
            raw = (self.fx.path / name).read_bytes()
            self.assertEqual((row["bytes"], row["sha256"]), (len(raw), O.digest(raw)))
        for name, declarations, indexed in (("source-before", 65, 67), ("acquisition-queries", 136, 137),
                                           ("source-after", 65, 67)):
            rows, directories = self.query(name)
            session = O.parse(self.parts(name)[1])
            self.assertEqual(len(session["readbacks"]), declarations)
            self.assertEqual(len(rows), indexed)
            self.assertEqual(len(directories), 26 if name == "acquisition-queries" else 14)
            self.assertEqual(session["readbacks"][0]["name"], "owner.json")
            self.assertEqual(list((self.fx.path / name / "query-home").iterdir()), [])
        self.assertEqual(list((self.fx.path / "control-home").iterdir()), [])
        self.assertEqual(list((self.fx.path / "temporary").iterdir()), [])
        self.assertTrue(any(row["bytes"] == 0 and row["sha256"] == O.digest(b"") for row in files.values()))
        pins = {(text, identity) for _directory, _path, text, identity in self.capture.pins}
        self.assertEqual(len(pins), 7)
        self.assertEqual(len({identity for _text, identity in pins}), 7)
        self.assertEqual(value["copyState"], "ORIGINAL_BYTES_NOT_COPIED")
        self.assertEqual(value["nestedNativePins"], "NOT_CAPTURED")
        self.assertIs(value["exportSaveAuthority"], False)

    def test_query_ids_count_canonical_bytes_and_schema_types_refuse(self):
        original = O.parse(self.parts("source-before")[1])
        changes = (
            lambda row: row["queries"].pop(),
            lambda row: row["queries"][1].update(id=row["queries"][0]["id"]),
            lambda row: row["queries"][0].update(id="NOT_A_QUERY_ID"),
            lambda row: row.update(schema=True),
            lambda row: row.update(retirement="UNKNOWN"),
            lambda row: row.update(unexpected="SYNTHETIC"),
        )
        for change in changes:
            value = copy.deepcopy(original)
            change(value)
            with self.subTest(change=changes.index(change)), self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_"):
                self.query(session=value)
        with self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_SESSION"):
            self.query(session=Q.encoded(original) + b"\n")
        with self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_SESSION_BYTES"):
            self.query(session=b"x" * (Q.MAX_RECEIPT_BYTES + 1))

    def test_query_readback_missing_extra_duplicate_order_and_parent_refuse(self):
        original = O.parse(self.parts("acquisition-queries")[1])
        changes = (
            lambda rows: rows.pop(),
            lambda rows: rows.append(dict(rows[-1])),
            lambda rows: rows.__setitem__(1, dict(rows[0])),
            lambda rows: rows.__setitem__(slice(0, 2), list(reversed(rows[:2]))),
            lambda rows: rows[0].update(parent=rows[1]["parent"] + "/wrong"),
            lambda rows: rows[0].update(name="undeclared.json"),
        )
        for change in changes:
            value = copy.deepcopy(original)
            change(value["readbacks"])
            with self.subTest(change=changes.index(change)), self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_READBACK"):
                self.query("acquisition-queries", session=value)

    def test_query_metadata_types_limits_retirement_and_zero_digest_refuse(self):
        original = O.parse(self.parts("source-before")[1])
        changes = (
            lambda row: row["queries"][0].update(stdoutLimit=4097),
            lambda row: row["queries"][0].update(stderrLimit=True),
            lambda row: row["queries"][0].update(waitExitCode=False),
            lambda row: row["queries"][0].update(home="/wrong-home"),
            lambda row: row["readbacks"][0].update(bytes=True),
            lambda row: row["readbacks"][0].update(maximum=row["readbacks"][0]["maximum"] + 1),
            lambda row: row["readbacks"][0].update(retirement="UNKNOWN"),
            lambda row: row["readbacks"][0].update(result="HOLD"),
            lambda row: row["readbacks"][0].update(sha256="not-a-hash"),
            lambda row: next(item for item in row["readbacks"] if item["bytes"] == 0).update(sha256="1" * 64),
        )
        for change in changes:
            value = copy.deepcopy(original)
            change(value)
            with self.subTest(change=changes.index(change)), self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_"):
                self.query(session=value)

    def test_source_session_return_and_original_bytes_cannot_be_substituted(self):
        path, raw, data, source = self.parts("source-before")
        for changed in ({**data, "base_policy_entry": b"invented\n"}, dict(reversed(tuple(data.items())))):
            with self.subTest(keys=tuple(changed)), self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_ORIGINAL_"):
                self.query(originals=changed)
        with self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_SOURCE_RETURN"):
            N._gate_query_index(path, raw, data, source=dataclasses.replace(source, session=raw + b"\n"))
        side = O.parse(source.raw)
        side["sessionSha256"] = "0" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_SOURCE_BINDING"):
            N._gate_query_index(path, raw, data, source=dataclasses.replace(source, raw=O.encoded(side)))
        side = O.parse(source.raw)
        side["originalsSha256"]["candidate_policy_raw"] = "0" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_SOURCE_BINDING"):
            N._gate_query_index(path, raw, data, source=dataclasses.replace(source, raw=O.encoded(side)))

    def test_inventory_requires_actual_gate_job_host_source_and_no_worker_authority(self):
        context = O.parse(self.inputs["context_raw"])
        changes = (
            lambda row: row["observed"].update(kind="worker"),
            lambda row: row["observed"].update(role="windows-x64"),
            lambda row: row["observed"]["github"].update(job="populate"),
            lambda row: row["observed"]["github"].update(runnerArch="ARM64"),
            lambda row: row["observed"]["github"].update(runId="999999"),
            lambda row: row["observed"]["source"].update(commit="0" * 40),
        )
        for change in changes:
            value = copy.deepcopy(context)
            change(value)
            raw = O.encoded(value)
            phase = dataclasses.replace(self.inputs["phase"], context=raw)
            captured = (raw, *self.inputs["captured"][1:])
            with self.subTest(change=changes.index(change)), self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_CONTEXT"):
                self.index(context_raw=raw, phase=phase, captured=captured)
        with self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_INPUTS"):
            self.index(match=N.acquisition.stages.BootstrapMatch(self.original._match.record))
        for name in ("workerIdentitySha256", "serviceTimeBasisSha256", "allocationProposalSha256"):
            pending = O.parse(self.original.raw)
            pending[name] = "1" * 64
            with self.subTest(name=name), self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_PENDING"):
                self.index(result_raw=O.encoded(pending))

    def test_inventory_binds_child_session_phase_and_pending_original_bytes(self):
        for name in ("child_raw", "session_raw"):
            with self.subTest(name=name), self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_CHAIN"):
                self.index(**{name: self.inputs[name] + b"\n"})
        phase = self.inputs["phase"]
        rows = tuple((name, raw + b"changed" if name == "stderr.log" else raw) for name, raw in phase.records)
        with self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_CHAIN"):
            self.index(phase=dataclasses.replace(phase, records=rows))
        pending = O.parse(self.original.raw)
        pending["sourceAfterSha256"] = "0" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_PENDING"):
            self.index(result_raw=O.encoded(pending))
        captured = self.inputs["captured"]
        with self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_INPUTS"):
            self.index(captured=(captured[0], tuple(reversed(captured[1])), *captured[2:]))

    def test_session64mib_and_index2mib_caps_are_enforced_without_big_captures(self):
        self.assertEqual(Q.MAX_SESSION_BYTES, 64 * 1024 * 1024)
        self.assertEqual(S.LIMIT, 2 * 1024 * 1024)
        raw = self.parts("acquisition-queries")[1]
        total = len(raw) + sum(row["bytes"] for row in O.parse(raw)["readbacks"])
        self.assertLess(total, Q.MAX_SESSION_BYTES)
        with patch.object(Q, "MAX_SESSION_BYTES", total - 1), self.assertRaisesRegex(I.AdmissionError, "GATE_QUERY_SESSION_LIMIT"):
            self.query("acquisition-queries")
        encode = O.encoded
        def oversized(value):
            # Exercise only the final metadata-size predicate, not large files
            # or an enlarged producer/cache/provider limit.
            if type(value) is dict and value.get("scope") == N.GATE_INVENTORY_SCOPE:
                return b"x" * (S.LIMIT + 1)
            return encode(value)
        with patch.object(O, "encoded", oversized), self.assertRaisesRegex(I.AdmissionError, "GATE_ORIGINAL_INDEX_LIMIT"):
            self.index()


class GateParentControls(unittest.TestCase):
    def setUp(self):
        self.fx = fixture(self)

    def test_real_parent_freezes_live_originals_and_registers_only_after_known_close(self):
        capture, read, observed, contracts = N._capture_gate_originals, N.read_phase, [], []
        def retained(*args):
            self.assertFalse(args[0].closed)
            self.assertFalse(N._GATE_RETURNS)
            self.assertFalse(N._PREPARED_RETURNS)
            anchor = capture(*args)
            self.assertIs(N._check_gate_capture(anchor, closed=False), anchor[0])
            observed.append(anchor)
            return anchor
        def read_three(*args):
            returned = read(*args)
            contracts.append(len(returned))
            return returned
        with patch.object(N, "_capture_gate_originals", retained), patch.object(N, "read_phase", read_three):
            original = N._prepare_originals(self.fx.cancelled)
        self.assertEqual(contracts, [3, 3])
        self.assertEqual(len(observed), 1)
        entry = N._gate_return(original)
        self.assertIs(entry[2], observed[0])
        self.assertIs(N._check_gate_capture(entry[2], closed=True).owner, original._owner)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in original._owner.resources))
        self.assertIsNone(original.identity)
        self.assertIsNone(original.service_time_raw)
        self.assertIsNone(original.proposal_raw)
        self.assertEqual([len(query.calls) for query in self.fx.queries], [12, 24, 12])
        self.assertEqual(len(self.fx.fixture.requests), 8)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_unknown_original_close_never_registers_gate_return(self):
        close = S.Owner.close
        failure = RuntimeError("SYNTHETIC_GATE_ORIGINAL_CLOSE_UNKNOWN")
        def unknown(owner):
            close(owner)
            if hasattr(owner, "_gate_capture_anchor"):
                owner.error("synthetic-gate-close", failure, unknown=True)
        with patch.object(S.Owner, "close", unknown), self.assertRaises(RuntimeError) as raised:
            N._prepare_originals(self.fx.cancelled)
        self.assertIs(raised.exception, failure)
        self.assertFalse(N._GATE_RETURNS)
        self.assertFalse(N._PREPARED_RETURNS)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_partial_original_ledger_close_is_not_owner_closed_acceptance(self):
        close = S.Owner.close
        observed = []
        def partial(owner):
            close(owner)
            if hasattr(owner, "_gate_capture_anchor"):
                owner.resources[-1]["closed"] = False  # Real tiny resource did close; model the incomplete ledger.
                observed.append(owner)
        with patch.object(S.Owner, "close", partial), self.assertRaisesRegex(I.AdmissionError, "GATE_CLOSE_RESOURCE_CHANGED"):
            N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0].closed)
        self.assertFalse(N._GATE_RETURNS)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_original_ledger_source_graph_and_native_identity_mutations_refuse_saved_return(self):
        original = N._prepare_originals(self.fx.cancelled)
        entry = N._gate_return(original)
        capture, owner = entry[2][0], original._owner
        directory = capture.pins[0][0]
        changes = ((owner, "resources", list(owner.resources)), (owner, "errors", []),
            (owner, "initial_sources", dict(owner.initial_sources)),
            (owner, "phase_originals", dataclasses.replace(owner.phase_originals)),
            (capture, "raw", capture.raw + b"changed"),
            (directory, "path", Path(str(directory.path))),
            (directory, "identity", (directory.identity[0], directory.identity[1] + 1)),
            (original, "raw", original.raw + b"changed"))
        for target, name, replacement in changes:
            saved = getattr(target, name)
            object.__setattr__(target, name, replacement)
            try:
                with self.subTest(name=name), self.assertRaises(I.AdmissionError):
                    N._gate_return(original)
            finally:
                object.__setattr__(target, name, saved)
        rows, row = owner.resources, owner.resources[0]
        rows[0] = dict(row)
        try:
            with self.assertRaisesRegex(I.AdmissionError, "GATE_CLOSE_RESOURCE_CHANGED"):
                N._gate_return(original)
        finally:
            rows[0] = row
        self.assertIs(N._gate_return(original), entry)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_freezing_the_completed_original_snapshot_cannot_cross_WORK75(self):
        initialize = N._GateRoster.__init__
        freezes = []
        def expired(roster, owner):
            initialize(roster, owner)
            if owner.phase_originals is not None and len(owner.initial_sources) == 2:
                freezes.append((owner, roster.frozen))
                self.fx.fixture.ns = owner.fence.work
        with patch.object(N._GateRoster, "__init__", expired), self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
            N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(freezes), 1)
        owner, frozen = freezes[0]
        self.assertIs(owner.closed, True)
        self.assertTrue(frozen)
        for row, label, resource, _attempted, _closed in frozen:
            self.assertTrue(any(current is row for current in owner.resources))
            self.assertEqual(row["label"], label)
            self.assertIs(row["owner"], resource)
            self.assertIs(row["attempted"], True)
            self.assertIs(row["closed"], True)
        self.assertFalse(N._PREPARED_RETURNS)
        self.assertFalse(N._GATE_RETURNS)
        self.assertEqual(self.fx.output.read_bytes(), b"")


class GateHandoffControls(unittest.TestCase):
    def setUp(self):
        self.fx = fixture(self)

    def closed(self):
        return N._prepare_originals(self.fx.cancelled)

    def path(self):
        return self.fx.path.with_name(self.fx.path.name + "-handoff")

    def final_failure_is_sticky(self, returned, expected, change, restore):
        _value, fence, limit = returned
        change()
        try:
            with self.assertRaises(expected) as first:
                fence.now(final=True, limit=limit)
        finally:
            restore()
        with self.assertRaises(expected) as second:
            fence.now(final=True, limit=limit)
        self.assertIs(second.exception, first.exception)
        self.assertEqual(len(self.fx.output.read_text().splitlines()), 2)

    def test_two_hash_handoff_closes_fresh_sibling_before_single_append_and_two_final_checks(self):
        original = self.closed()
        append, close, observed, siblings = C.append_outputs, S.Owner.close, [], []
        def closed(owner):
            value = close(owner)
            if owner is not original._owner:
                siblings.append(owner)
            return value
        def checked(values, check):
            self.assertEqual(len(siblings), 1)
            owner = siblings[0]
            self.assertIs(owner.fence, original._fence)
            self.assertEqual(owner.local_end, original._owner.local_end)
            self.assertIs(owner.cancelled, original._fence.cancelled)
            self.assertTrue(owner.closed)
            self.assertFalse(owner.unknown)
            self.assertIsNone(owner.original)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))
            self.assertEqual([row["label"] for row in owner.resources], ["directory", "writer"])
            self.assertEqual(owner.resources[0]["owner"].path, self.path())
            self.assertTrue(original._owner.closed)
            observed.append(dict(values))
            return append(values, check)
        with patch.object(C, "append_outputs", checked), patch.object(S.Owner, "close", closed):
            returned = N._retain_gate_handoff(original)
        raw = (self.path() / N.GATE_HANDOFF_FILE).read_bytes()
        value = O.parse(raw)
        self.assertEqual(value["scope"], N.GATE_HANDOFF_SCOPE)
        self.assertEqual(value["inventory"], O.parse(N._gate_return(original)[2][0].raw))
        self.assertEqual(value["originalClosedNs"], N._gate_return(original)[3])
        self.assertEqual(value["writerReturn"], "PENDING_OWNER_CLOSE")
        self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
        self.assertEqual(len(value["originalNativeDirectories"]), 7)
        expected = {"initialOriginalsSha256": O.digest(original.raw), "gateHandoffSha256": O.digest(raw)}
        self.assertEqual(observed, [expected])
        self.assertEqual(dict(line.split("=", 1) for line in self.fx.output.read_text().splitlines()), expected)
        self.assertEqual(returned[0]["scope"], N.OUTPUT_SCOPE)
        self.assertEqual({name: returned[0][name] for name in expected}, expected)
        readings, observe = [], O.clocks.observe
        def counted():
            readings.append(True)
            return observe()
        with patch.object(O.clocks, "observe", counted):
            returned[1].now(final=True, limit=returned[2])
            returned[1].now(final=True, limit=returned[2])
            with self.assertRaisesRegex(I.AdmissionError, "GATE_FINAL_OUTPUT_ONLY"):
                returned[1].now(final=True, limit=returned[2])
        self.assertEqual(len(readings), 2)
        with self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_ALREADY_CONSUMED"):
            N._retain_gate_handoff(original)

    def test_worker_keeps_old_three_value_route_without_gate_capability(self):
        self.fx.choose("worker", "desktop-linux-x64")
        with patch.object(N, "_capture_gate_originals", side_effect=AssertionError("NO_WORKER_GATE_CAPTURE")), \
                patch.object(N, "_retain_gate_handoff", side_effect=AssertionError("NO_WORKER_GATE_HANDOFF")), \
                patch.object(C, "append_outputs", side_effect=AssertionError("NO_WORKER_GATE_OUTPUT")):
            value, fence, limit = N.prepare_originals(self.fx.cancelled)
        self.assertEqual(value["scope"], N.OUTPUT_SCOPE)
        self.assertNotIn("gateHandoffSha256", value)
        self.assertIs(type(fence), O.Fence)
        self.assertEqual(limit, fence.final)
        self.assertFalse(N._GATE_RETURNS)
        self.assertFalse(N._GATE_CAPTURES)
        self.assertFalse(self.path().exists())
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertTrue(all(not query.gate for query in self.fx.queries))
        self.assertTrue(all(O.parse((query.path / "session-result.json").read_bytes())["readbacks"] == []
            for query in self.fx.queries))
        binding = next(iter(N._PREPARED_RETURNS.values()))
        self.assertIsNotNone(binding.identity)
        self.assertIsNotNone(binding.service_time_raw)
        self.assertIsNotNone(binding.proposal_raw)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_GATE_RETURN"):
            N._gate_return(binding.original)

    def test_missing_copied_or_replaced_registrations_cannot_start_handoff(self):
        original = self.closed()
        entry = N._gate_return(original)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_GATE_RETURN"):
            N._retain_gate_handoff(dataclasses.replace(original))
        N._GATE_RETURNS.pop(id(original))
        try:
            with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_GATE_RETURN"):
                N._retain_gate_handoff(original)
        finally:
            N._GATE_RETURNS[id(original)] = entry
        with patch.dict(N._GATE_RETURNS, {id(original): tuple(list(entry))}), \
                self.assertRaisesRegex(I.AdmissionError, "GATE_RETURN_CHANGED"):
            N._retain_gate_handoff(original)
        with patch.object(N, "_PREPARED_RETURNS", dict(N._PREPARED_RETURNS)), \
                self.assertRaisesRegex(I.AdmissionError, "GATE_CAPTURE_CHANGED"):
            N._retain_gate_handoff(original)
        self.assertFalse(N._GATE_HANDOFF_ATTEMPTS)
        self.assertFalse(self.path().exists())
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_metadata_callback_registry_substitution_is_sticky_consumption(self):
        original = self.closed()
        acquire, registry = S.Owner.acquire, N._GATE_RETURNS
        def changed(owner, label, factory, **kwargs):
            value = acquire(owner, label, factory, **kwargs)
            if owner is not original._owner and label == "directory":
                N._GATE_RETURNS = dict(registry)
            return value
        try:
            with patch.object(S.Owner, "acquire", changed), self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_GATE_RETURN"):
                N._retain_gate_handoff(original)
        finally:
            N._GATE_RETURNS = registry
        self.assertEqual(self.fx.output.read_bytes(), b"")
        with self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_ALREADY_CONSUMED"):
            N._retain_gate_handoff(original)

    def test_sidecar_second_readback_mismatch_prevents_output(self):
        original = self.closed()
        read, observed = S.Owner.read, []
        def changed(owner, directory, name, *args, **kwargs):
            raw = read(owner, directory, name, *args, **kwargs)
            if name == N.GATE_HANDOFF_FILE:
                observed.append(True)
                if len(observed) == 2:
                    return b"SYNTHETIC_CHANGED_GATE_HANDOFF\n"
            return raw
        with patch.object(S.Owner, "read", changed), self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_READBACK"):
            N._retain_gate_handoff(original)
        self.assertEqual(len(observed), 2)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_unknown_sibling_close_retains_owner_and_never_emits_hashes(self):
        original = self.closed()
        close = Q._PosixDirectory.close
        def unknown(directory):
            close(directory)
            if directory.path == self.path():
                raise OSError("SYNTHETIC_GATE_HANDOFF_CLOSE_UNKNOWN")
        with patch.object(Q._PosixDirectory, "close", unknown), \
                self.assertRaisesRegex(OSError, "SYNTHETIC_GATE_HANDOFF_CLOSE_UNKNOWN"):
            N._retain_gate_handoff(original)
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.assertTrue(S.QUARANTINE)
        self.assertTrue(any(owner is N._GATE_HANDOFF_ATTEMPTS[id(original)][2][0] for owner in S.QUARANTINE))

    def test_sibling_closed_boolean_cannot_hide_incomplete_resource_ledger(self):
        original = self.closed()
        close = S.Owner.close
        def partial(owner):
            close(owner)
            if owner is not original._owner:
                owner.resources[-1]["closed"] = False
        with patch.object(S.Owner, "close", partial), self.assertRaisesRegex(I.AdmissionError, "GATE_CLOSE_RESOURCE_CHANGED"):
            N._retain_gate_handoff(original)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_sibling_native_identity_changed_at_close_is_not_fresh_authority(self):
        original = self.closed()
        close = S.Owner.close
        def changed(owner):
            close(owner)
            if owner is not original._owner:
                directory = owner.resources[0]["owner"]
                directory.identity = (directory.identity[0], directory.identity[1] + 1)
        with patch.object(S.Owner, "close", changed), self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_PIN_CHANGED"):
            N._retain_gate_handoff(original)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_append_failure_consumes_the_original_once_without_retry(self):
        original = self.closed()
        failure = RuntimeError("SYNTHETIC_GATE_OUTPUT_FAILURE")
        with patch.object(C, "append_outputs", side_effect=failure), self.assertRaises(RuntimeError) as raised:
            N._retain_gate_handoff(original)
        self.assertIs(raised.exception, failure)
        self.assertEqual(self.fx.output.read_bytes(), b"")
        with self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_ALREADY_CONSUMED"):
            N._retain_gate_handoff(original)

    def test_gate_output_shape_rejects_single_hash_extra_authority_and_nonhash(self):
        value = {"initialOriginalsSha256": "a" * 64, "gateHandoffSha256": "b" * 64}
        for row in ({"gateHandoffSha256": "b" * 64}, {**value, "ready": "c" * 64},
                    {**value, "gateHandoffSha256": "NOT_A_HASH"}, {**value, "initialOriginalsSha256": True}):
            with self.subTest(fields=tuple(row)), self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_FIELDS"):
                C.append_outputs(row, lambda: None)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_actual_short_runner_append_is_not_success_or_retry_authority(self):
        original = self.closed()
        write, calls = C.os.write, []
        def short(descriptor, raw):
            calls.append(raw)
            return write(descriptor, raw[:-1])
        with patch.object(C.os, "write", short), self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_SHORT_WRITE"):
            N._retain_gate_handoff(original)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.fx.output.read_bytes(), calls[0][:-1])
        with self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_ALREADY_CONSUMED"):
            N._retain_gate_handoff(original)

    def test_late_cancellation_after_hash_append_is_sticky_not_step_success(self):
        returned = N._retain_gate_handoff(self.closed())
        self.final_failure_is_sticky(returned, (I.AdmissionError, KeyboardInterrupt),
            lambda: self.fx.cancelled.append(15), self.fx.cancelled.clear)

    def test_late_RAW_FINAL120_expiry_cannot_be_erased_after_hash_append(self):
        original = self.closed()
        returned = N._retain_gate_handoff(original)
        previous = self.fx.fixture.ns
        self.final_failure_is_sticky(returned, O.OriginError,
            lambda: setattr(self.fx.fixture, "ns", original._fence.final),
            lambda: setattr(self.fx.fixture, "ns", previous))

    def test_late_LOCAL_expiry_cannot_be_renewed_after_hash_append(self):
        original = self.closed()
        returned = N._retain_gate_handoff(original)
        replacement = patch.object(N.time, "monotonic", return_value=original._owner.local_end)
        self.final_failure_is_sticky(returned, I.AdmissionError, replacement.start, replacement.stop)

    def test_reentrant_final_clock_callback_fails_closed_after_hash_append(self):
        returned = N._retain_gate_handoff(self.closed())
        _value, fence, limit = returned
        def recursive():
            return fence.now(final=True, limit=limit)
        with patch.object(O.clocks, "observe", recursive), self.assertRaisesRegex(O.OriginError, "GATE_HANDOFF_REENTRY") as first:
            fence.now(final=True, limit=limit)
        with self.assertRaises(O.OriginError) as second:
            fence.now(final=True, limit=limit)
        self.assertIs(second.exception, first.exception)
        self.assertEqual(len(self.fx.output.read_text().splitlines()), 2)

    def test_existing_sibling_is_not_reopened_or_rewritten_as_a_new_handoff(self):
        original = self.closed()
        self.path().mkdir(mode=0o700)
        sentinel = self.path() / N.GATE_HANDOFF_FILE
        sentinel.write_bytes(b"EXISTING_SYNTHETIC_GATE_HANDOFF\n")
        sentinel.chmod(0o600)
        with self.assertRaises(FileExistsError):
            N._retain_gate_handoff(original)
        self.assertEqual(sentinel.read_bytes(), b"EXISTING_SYNTHETIC_GATE_HANDOFF\n")
        self.assertEqual(self.fx.output.read_bytes(), b"")
        attempt = N._GATE_HANDOFF_ATTEMPTS[id(original)]
        self.assertIs(attempt[0], original)
        self.assertTrue(attempt[2][0].unknown)  # Constructor failure is not recovery/retry authority.


if __name__ == "__main__":
    unittest.main(failfast=True)
