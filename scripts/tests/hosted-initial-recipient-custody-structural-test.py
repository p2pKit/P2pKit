#!/usr/bin/env python3
"""Focused structural parity controls and opt-in unprofiled SUPPLIED comparison.

No old suite discovery, provider/network/native execution or original evidence.
The baseline is the verbatim function from Git367, not reversed candidate code.
--compare is separately bounded/admitted operational measurement, never a CI test
or proof of hosted timing. Its upstream history/Step/clock values are supplied.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import dataclasses
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("structural_supplied_primary_models",
    ROOT / "scripts/tests/hosted-initial-recipient-custody-primary-test.py")
F = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = F
_spec.loader.exec_module(F)  # Definitions only; retained offline audit hook applies.
D = F.D
BASELINE_COMMIT = "367efd052e001f8333b5ec00ebef80f738d75278"
BASELINE_SHA256 = '9a0a4bb26ccf7b9ff01d50e11d7dfed9a83bef3696898ad2b4ddeb8ce194e851'
BASELINE_SOURCE = 'def structural(self):\n    anchor = self._anchor()\n    owner, dictionary, ledger, errors, bound, graph, rows, returned, snapshots = anchor.binding\n    require(self._bound is anchor.binding and owner.__dict__ is dictionary, "COPY_ORIGINAL_OWNER_BINDING")\n    N._check_history(graph)\n    require(type(owner) is native.Owner and owner.resources is ledger and owner.errors is errors and\n        owner.first is bound[0] and owner.fence is bound[1] and owner.cancelled is bound[2] and\n        type(owner.local_end) is type(bound[3]) and owner.local_end == bound[3] and\n        type(owner.work_limit) is type(bound[4]) and owner.work_limit == bound[4] and\n        type(owner.final_limit) is type(bound[5]) and owner.final_limit == bound[5] and\n        type(ledger) is list and type(errors) is list and type(rows) is list and type(returned) is list and\n        len(ledger) == len(rows) == len(anchor.rows) == len(returned) == len(anchor.returned) <= MAX_MEMBERS and\n        all(actual is original for actual, original in zip(rows, anchor.rows)) and\n        all(actual is original for actual, original in zip(returned, anchor.returned)) and\n        type(owner.closed) is bool and (not owner.closed or anchor.finished), "COPY_OWNER_CHANGED")\n    for current, (row, label, resource, attempted, closed), actual in zip(ledger, anchor.rows, anchor.returned):\n        require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and\n            type(row["label"]) is str and row["label"] == label and row["owner"] is resource is actual and\n            type(row["attempted"]) is bool and type(row["closed"]) is bool and\n            (not row["closed"] or row["attempted"]) and\n            ((row["attempted"] is attempted and row["closed"] is closed) or\n                anchor.closing is resource and not attempted and not closed and row["attempted"] is True),\n            "COPY_LEDGER_CHANGED")\n    require(len({id(row) for row, *_ in anchor.rows}) == len(anchor.rows) ==\n        len({id(resource) for _, _, resource, _, _ in anchor.rows}), "COPY_RESOURCE_ALIAS")\n    require(type(snapshots) is list and len(snapshots) == len(anchor.snapshots) and\n        all(actual is original for actual, (original, _graph) in zip(snapshots, anchor.snapshots)),\n        "COPY_SNAPSHOT_ROSTER_CHANGED")\n    for snapshot, saved in anchor.snapshots:\n        N._check_history(saved)\n'
assert hashlib.sha256(BASELINE_SOURCE.encode()).hexdigest() == BASELINE_SHA256
_namespace = {}
exec(compile(BASELINE_SOURCE, "<original-Git367-structural>", "exec"), D.__dict__, _namespace)
BASELINE = _namespace["structural"]
CANDIDATE = D._PrimaryOwner.structural


class Entry:
    """Non-indexable replacement iterable; never a real constructor-created row."""
    def __init__(self, values, trace, mode):
        self.values, self.trace, self.mode, self.round = values, trace, mode, 0

    def __iter__(self):
        self.round += 1
        self.trace.append(("entry-iteration", self.round))
        values = self.values[:-1] if self.mode == "stateful" and self.round == 2 else self.values
        trace, fail_hint = self.trace, self.mode == "hint-error"
        class Iterator:
            def __init__(self):
                self.index = 0
            def __iter__(self):
                return self
            def __next__(self):
                trace.append(("next", self.index))
                if self.index == len(values):
                    raise StopIteration
                value = values[self.index]
                self.index += 1
                return value
            def __length_hint__(self):
                trace.append(("length-hint", self.index))
                if fail_hint:
                    raise ValueError("SUPPLIED_LENGTH_HINT_FAILURE")
                return len(values) - self.index
        return Iterator()


def replace_entry(owner, value, index=0):
    anchor = owner._anchor()
    anchor.rows = (*anchor.rows[:index], value, *anchor.rows[index+1:])
    owner.rows[index] = value


def snapshot(owner):
    child = {"items": ["original"]}
    value = D._PrimarySnapshot("SUPPLIED", Path("/supplied-not-opened"), object(), (1, 2),
        object(), child, (), D.N._history_graph(child), False)
    owner.retain_snapshot(value)
    return value


def outcome(call):
    try:
        call()
        return ("RETURNED", None)
    except Exception as error:
        return (type(error).__name__, str(error))


def differential(function, change, *, size=2, state="open"):
    trace = []
    with F.models() as clock, patch.dict(D._PRIMARY_OWNERS, {}, clear=True), \
            patch.object(D._PrimaryOwner, "structural", function):
        owner = F.own(clock)
        for _ in range(size):
            owner.acquire("reader", F.Resource)
        snap = snapshot(owner)
        if state == "closed":
            owner.finish()
        elif state == "closing":
            owner._anchor().closing = owner.returned[0]
            owner.ledger[0]["attempted"] = True
        change(owner, snap, trace)
        require, history = D.require, D.N._check_history
        def checked(value, code):
            if not value:
                trace.append(("refusal", code))
            return require(value, code)
        def visit(graph):
            trace.append(("history", len(graph)))
            return history(graph)
        before = (owner.owner.closed, owner.owner.unknown, owner.finished,
            tuple(resource.closes for resource in owner.returned if isinstance(resource, F.Resource)))
        with patch.object(D, "require", checked), patch.object(D.N, "_check_history", visit):
            result = outcome(lambda: function(owner))
        after = (owner.owner.closed, owner.owner.unknown, owner.finished,
            tuple(resource.closes for resource in owner.returned if isinstance(resource, F.Resource)))
        # These fixtures hold Python-only supplied resources, not live file handles.
        return result, trace, before, after


def callback_case(function, change):
    with tempfile.TemporaryDirectory(prefix="structural-callback-") as temp, \
            F.fixed_caller_model(Path(temp)) as fixture, patch.object(D._PrimaryOwner, "structural", function):
        result = D.copy_primary("gate", cancelled=fixture.clock.cancelled)
        owner = fixture.attempt["owners"][-1]
        assert owner.finished and owner.owner.closed
        events, original = [], F.FalseError("SUPPLIED_ORIGINAL_CALLBACK_FAILURE")
        def structural(current):
            if current is owner:
                events.append("STRUCTURAL")
            return function(current)
        def cancelled():
            events.append("CANCELLED")
            if change == "mutation":
                owner.ledger[0]["attempted"] = False
            elif change == "failure":
                raise original
            elif change == "reentry":
                result.window.now()
        fixture.callback = cancelled
        with patch.object(D._PrimaryOwner, "structural", structural):
            observed = outcome(result.window.now)
        failed = result.window._anchor().failure
        return observed, events, failed is original, owner.finished, owner.owner.closed


class StructuralParityTests(unittest.TestCase):
    def assert_parity(self, change, **kwargs):
        old, new = (differential(fn, change, **kwargs) for fn in (BASELINE, CANDIDATE))
        self.assertEqual(old, new)
        self.assertEqual(old[2], old[3], "structural must not mutate supplied owner state")
        return old

    def test_only_original_predicate_failure_call_changes_and_starred_unpack_stays(self):
        old = ast.parse(BASELINE_SOURCE)
        new = ast.parse(textwrap.dedent(inspect.getsource(CANDIDATE)))
        hits = []
        class FailureOnly(ast.NodeTransformer):
            def visit_Expr(self, node):
                call = node.value
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "require" and \
                        len(call.args) == 2 and isinstance(call.args[1], ast.Constant) and call.args[1].value == "COPY_LEDGER_CHANGED":
                    hits.append(call)
                    return ast.If(test=ast.UnaryOp(op=ast.Not(), operand=call.args[0]),
                        body=[ast.Expr(value=ast.Call(func=call.func,
                            args=[ast.Constant(value=False), call.args[1]], keywords=[]))], orelse=[])
                return node
        expected = FailureOnly().visit(old)
        self.assertEqual(len(hits), 1)
        self.assertEqual(ast.dump(expected, include_attributes=False), ast.dump(new, include_attributes=False))
        self.assertEqual(sum(isinstance(node, ast.Starred) for node in ast.walk(new)), 1)

    def test_empty_growing_closed_and_active_close_states_match(self):
        for size, state in ((0, "open"), (1, "open"), (3, "open"), (3, "closed"), (1, "closing")):
            with self.subTest(size=size, state=state):
                result = self.assert_parity(lambda *_: None, size=size, state=state)
                self.assertEqual(result[0], ("RETURNED", None))

    def test_owner_row_flags_alias_and_snapshot_refusals_match(self):
        def resource_alias(owner, _snapshot, _trace):
            anchor = owner._anchor()
            resource = owner.returned[0]
            row = owner.ledger[1]
            row["owner"] = resource
            replace_entry(owner, (row, "reader", resource, False, False), 1)
            anchor.returned = (resource, resource)
            owner.returned[1] = resource
        def row_alias(owner, _snapshot, _trace):
            anchor = owner._anchor()
            owner.ledger[1] = owner.ledger[0]
            replace_entry(owner, owner.rows[0], 1)
            anchor.returned = (owner.returned[0], owner.returned[0])
            owner.returned[1] = owner.returned[0]
        changes = {
            "binding": lambda o,s,t: setattr(o, "_bound", tuple(list(o._bound))),
            "dictionary": lambda o,s,t: setattr(o.owner, "__dict__", dict(o.owner.__dict__)),
            "ledger": lambda o,s,t: setattr(o.owner, "resources", []),
            "errors": lambda o,s,t: setattr(o.owner, "errors", []),
            "first": lambda o,s,t: setattr(o.owner, "first", dataclasses.replace(o.owner.first)),
            "fence": lambda o,s,t: setattr(o.owner, "fence", object()),
            "cancelled": lambda o,s,t: setattr(o.owner, "cancelled", lambda: None),
            "local-type": lambda o,s,t: setattr(o.owner, "local_end", int(o.owner.local_end)),
            "work": lambda o,s,t: setattr(o.owner, "work_limit", 1),
            "final": lambda o,s,t: setattr(o.owner, "final_limit", 1),
            "owner-closed-type": lambda o,s,t: setattr(o.owner, "closed", 1),
            "row-order": lambda o,s,t: o.rows.reverse(),
            "ledger-order": lambda o,s,t: o.ledger.reverse(),
            "returned-order": lambda o,s,t: o.returned.reverse(),
            "extra-key": lambda o,s,t: o.ledger[0].update(extra=True),
            "missing-key": lambda o,s,t: o.ledger[0].pop("label"),
            "label-type": lambda o,s,t: o.ledger[0].update(label=1),
            "label-value": lambda o,s,t: o.ledger[0].update(label="writer"),
            "resource": lambda o,s,t: o.ledger[0].update(owner=object()),
            "attempted-type": lambda o,s,t: o.ledger[0].update(attempted=1),
            "closed-type": lambda o,s,t: o.ledger[0].update(closed=1),
            "closed-without-attempt": lambda o,s,t: o.ledger[0].update(closed=True),
            "attempt-without-closing": lambda o,s,t: o.ledger[0].update(attempted=True),
            "resource-alias": resource_alias,
            "row-alias": row_alias,
            "snapshot-roster": lambda o,s,t: o.snapshots.clear(),
            "snapshot-descendant": lambda o,s,t: s.original["items"].append("changed"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                result = self.assert_parity(change)
                self.assertNotEqual(result[0][0], "RETURNED")

    def test_malformed_nonindexable_stateful_and_length_hint_entries_match(self):
        for mode in ("four", "six", "iterable", "stateful", "hint-error"):
            def change(owner, _snapshot, trace):
                values = owner.rows[0]
                if mode == "four": entry = values[:-1]
                elif mode == "six": entry = (*values, None)
                else: entry = Entry(values, trace, mode)
                replace_entry(owner, entry)
            with self.subTest(mode=mode):
                result = self.assert_parity(change)
                if mode in ("four", "six", "hint-error"):
                    self.assertNotEqual(result[0][0], "RETURNED")
                else:
                    self.assertEqual(result[0], ("RETURNED", None))
                if mode == "hint-error":
                    self.assertEqual(result[0], ("ValueError", "SUPPLIED_LENGTH_HINT_FAILURE"))
                    self.assertTrue(any(row[0] == "length-hint" for row in result[1]))

    def test_original_closed_callback_bracket_failure_mutation_and_reentry_match(self):
        for change in ("none", "failure", "mutation", "reentry"):
            with self.subTest(change=change):
                old, new = (callback_case(fn, change) for fn in (BASELINE, CANDIDATE))
                self.assertEqual(old, new)
                self.assertEqual(old[1][:2], ["STRUCTURAL", "CANCELLED"])
                self.assertTrue(old[3] and old[4])
                if change == "none":
                    self.assertEqual(old[1], ["STRUCTURAL", "CANCELLED", "STRUCTURAL"])
                    self.assertEqual(old[0], ("RETURNED", None))
                else:
                    self.assertNotEqual(old[0][0], "RETURNED")
                if change == "failure":
                    self.assertTrue(old[2])

    def test_close_error_keeps_first_exception_and_no_retry(self):
        results = []
        for function in (BASELINE, CANDIDATE):
            with F.models() as clock, patch.dict(D._PRIMARY_OWNERS, {}, clear=True), \
                    patch.object(D._PrimaryOwner, "structural", function), \
                    patch.object(D, "_PRIMARY_QUARANTINE", []):
                owner, first = F.own(clock), F.FalseError("SUPPLIED_FIRST_CLOSE")
                resource = owner.acquire("reader", lambda: F.Resource(close_error=first))
                initial = outcome(owner.finish)
                repeated = outcome(owner.finish)
                results.append((initial, repeated, owner.failure is first, owner.owner.original is first,
                    owner.owner.unknown, resource.closes))
        self.assertEqual(results[0], results[1])
        self.assertTrue(results[0][2] and results[0][3] and results[0][4])
        self.assertEqual(results[0][5], 1)


def full_primary_roster(fixture):
    """Expand only the SUPPLIED upstream Primary before any actual copy starts.

    Counts are the maintained gate grammar's 281 files/58 directories. Tiny new
    bytes and indexed identities are real; primary_record/history remain the
    fixture's explicitly supplied upstream returns, not authentic hosted input.
    """
    for number in range(281 - len(fixture.contents)):
        name = "supplied-" + str(number).zfill(3) + ".bin"
        fixture.contents[name] = b"x"
        F.put(fixture.source / name, b"x")
    for number in range(58 - len(fixture.primary.directories)):
        (fixture.source / ("supplied-dir-" + str(number).zfill(3))).mkdir(mode=0o700)
    directories = [fixture.source, *(p for p in fixture.source.iterdir() if p.is_dir())]
    # This object is the fixture's SUPPLIED return, before source graphs/owners
    # exist. No retained production owner, row, snapshot or callback is rebuilt.
    object.__setattr__(fixture.primary, "files", tuple(("P/" + name, max(1,len(raw)),len(raw),F.sha(raw),
        "ORIGINAL_PRIMARY_DECLARATION") for name,raw in sorted(fixture.contents.items())))
    object.__setattr__(fixture.primary, "directories", tuple(("P" + ("/" + p.name if p != fixture.source else ""),
        tuple(D.native.posix._identity(p)), "ORIGINAL_NATIVE_PIN") for p in sorted(directories)))
    assert len(fixture.primary.files) == 281 and len(fixture.primary.directories) == 58


def comparison_run(label, function):
    began, cpu = time.perf_counter(), time.process_time()
    with tempfile.TemporaryDirectory(prefix="structural-comparison-") as temp, \
            F.fixed_caller_model(Path(temp)) as fixture, patch.object(D._PrimaryOwner, "structural", function):
        full_primary_roster(fixture)
        result = D.copy_primary("gate", cancelled=fixture.clock.cancelled)
        owner = fixture.attempt["owners"][-1]
        assert owner.finished and owner.owner.closed and all(attempted and closed for _,_,_,attempted,closed in owner.rows)
        copied = json.loads(result.copy)
        assert copied["memberCount"] == 282
        for row in copied["members"]:
            raw = (fixture.custody / "copied-evidence" / row["member"]).read_bytes()
            assert (len(raw), F.sha(raw)) == (row["bytes"], row["sha256"])
            assert raw == (fixture.handoff_raw if row["carrier"] == "HANDOFF" else fixture.contents[row["original"].removeprefix("P/")])
        setup_cpu, setup_wall = time.process_time()-cpu, time.perf_counter()-began
        calls = {"structural":0, "cancelled":0}
        def checked(current):
            if current is owner: calls["structural"] += 1
            return function(current)
        def cancelled():
            calls["cancelled"] += 1
        fixture.callback = cancelled
        started, cpu = time.perf_counter(), time.process_time()
        with patch.object(D._PrimaryOwner, "structural", checked):
            for _ in range(1000):
                result.window.now()
        measured_cpu, measured_wall = time.process_time()-cpu, time.perf_counter()-started
        assert calls == {"structural":2000, "cancelled":1000}
        D.checked_primary(result)
        return {"candidate":label, "setupCpuSeconds":setup_cpu, "setupWallSeconds":setup_wall,
            "callbackCpuSeconds":measured_cpu, "callbackWallSeconds":measured_wall,
            "callbacks":calls["cancelled"], "closedOwnerStructuralCalls":calls["structural"],
            "retainedClosedRows":len(owner.rows), "retainedSnapshots":len(owner.snapshots),
            "primaryFiles":281,"primaryDirectories":58,"copiedMembersReread":282,"knownClose":True}


def compare():
    rows = [comparison_run(label,function) for label,function in
        (("BASELINE",BASELINE),("CANDIDATE",CANDIDATE),("CANDIDATE",CANDIDATE),("BASELINE",BASELINE))]
    assert len({(row["retainedClosedRows"],row["retainedSnapshots"]) for row in rows}) == 1
    print(json.dumps({"schema":1,"scope":"SUPPLIED_CLOSED_PRIMARY_CALLBACK_ABBA_NOT_QUALIFICATION",
        "baselineCommit":BASELINE_COMMIT,"baselineFunctionSha256":BASELINE_SHA256,
        "rows":rows,"upstreamAndClocksSupplied":True,"profiled":False,"hostedFailureResolved":False},sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--compare"]:
        compare()
    else:
        unittest.main()
