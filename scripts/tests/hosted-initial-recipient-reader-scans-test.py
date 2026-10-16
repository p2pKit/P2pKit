#!/usr/bin/env python3
"""Small receiver scan controls; no graph fixture, native owner or authority.

ReaderScanDiagnostics is a separately selected scan-cost diagnostic,
NOT complete1066/owner-close acceptance. No filesystem fixture is constructed.
The existing pre-project process/network/native-loader guard remains active.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("reader_scan_graph_fixtures",
    Path(__file__).with_name("hosted-initial-recipient-original-graph-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
N, I = F.N, F.I
ORIGINAL_HISTORY = N._check_reader_path_history


def original_query_roster(owner, ledger, prefix, held, new_rows, missing):
    # Exact preimage expression, not the new helper used as its own oracle.
    return owner.resources is ledger and len(ledger) == len(prefix) + len(held) and all(
        row is saved and type(row) is dict and len(row) == 4 and
        type(row.get("label")) is str and row.get("label") == label and row.get("owner", missing) is resource and
        row.get("attempted") is attempted and row.get("closed") is closed
        for row, (saved, label, resource, attempted, closed) in zip(ledger, prefix)) and all(
        type(row) is dict and len(row) == 4 and
        row.get("label") == "directory" and row.get("owner", missing) is resource and
        row.get("attempted") is False and row.get("closed") is False
        for row, resource in zip(ledger[len(prefix):], held)) and all(
        row is saved for row, saved in zip(ledger[len(prefix):], new_rows))


def original_graph_roster(owner, ledger, rows, missing, *, tail=False):
    return owner.resources is ledger and (len(ledger) >= len(rows) if tail else len(ledger) == len(rows)) and all(
        actual is saved and type(actual) is dict and len(actual) == 4 and actual.get("label", missing) is not missing and
        actual.get("label") == label and actual.get("owner", missing) is resource and
        actual.get("attempted") is attempted and actual.get("closed") is closed
        for actual, (saved, label, resource, attempted, closed) in zip(ledger, rows))


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class ModelPath:
    def __init__(self, name, log):
        self.name, self.log, self.hooks = name, log, {}
        self.values = {"str": name, "parts": (name,), "drive": "", "root": ""}

    def take(self, field):
        self.log.append((self.name, field))
        if field in self.hooks:
            self.hooks[field]()
        return self.values[field]

    def __str__(self):
        return self.take("str")

    @property
    def parts(self):
        return self.take("parts")

    @property
    def drive(self):
        return self.take("drive")

    @property
    def root(self):
        return self.take("root")


def node(value):
    return value, type(value), "path", (value.name, (value.name,), "", "")


def visits(*names):
    return [(name, field) for name in names for field in ("str", "parts", "drive", "root")]


def fail(error):
    raise error


class ReaderHistoryModels(unittest.TestCase):
    def equivalent(self, factory, *, error=None):
        outcomes = []
        for planned in (False, True):
            log = []
            nodes = factory(log)
            if planned:
                history = N._ReaderPathHistory(nodes)
                self.assertEqual(log, [], "planning must not observe current fields or consume custom inputs")
                check = history.check
            else:
                check = lambda: ORIGINAL_HISTORY(nodes)
            try:
                result = check()
                outcome = ("return", result)
            except BaseException as caught:
                if error is not None:
                    self.assertIs(caught, error)
                outcome = ("raise", type(caught), caught.args)
            if error is not None:
                self.assertEqual(outcome[0], "raise")
            outcomes.append((outcome, log))
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[1]

    def test_same_nodes_duplicates_equal_distinct_and_each_current_field(self):
        for field, changed in ((None, None), ("str", "changed"), ("parts", ("changed",)),
                ("drive", "changed"), ("root", "changed")):
            def factory(log):
                a, b = ModelPath("a", log), ModelPath("a", log)
                nodes = (node(a), node(b), node(a))
                if field is not None:
                    b.values[field] = changed
                return nodes
            with self.subTest(field=field):
                outcome, log = self.equivalent(factory)
                self.assertEqual(log, visits(*(("a",) * (3 if field is None else 2))))
                self.assertEqual(outcome[0], "return" if field is None else "raise")
        def wrong_type(log):
            a = ModelPath("a", log)
            return ((a, str, "path", node(a)[3]),)
        self.assertEqual(self.equivalent(wrong_type)[1], [])

    def test_getter_and_comparison_failures_preserve_original_exception(self):
        error = FalseyFailure("MODEL_ORIGINAL_GETTER_FAILURE")
        for field in ("str", "parts", "drive", "root"):
            def factory(log):
                a = ModelPath("a", log)
                a.hooks[field] = lambda: fail(error)
                return (node(a),)
            with self.subTest(field=field):
                self.equivalent(factory, error=error)
        def comparison(log):
            class Equality:
                def __eq__(self, other):
                    log.append(("comparison", "eq"))
                    raise error
            a = ModelPath("a", log)
            a.values["parts"] = (Equality(),)
            return ((a, ModelPath, "path", ("a", (object(),), "", "")),)
        self.assertEqual(self.equivalent(comparison, error=error)[1], visits("a") + [("comparison", "eq")])

    def test_unsupported_metadata_defers_to_original_validation_boundary(self):
        class OtherPath(ModelPath):
            pass
        for shape in ("short", "mutable", "custom-mode", "nonpath", "different-kind", "none", "iterator"):
            def factory(log):
                a = ModelPath("a", log)
                if shape == "none":
                    return None
                if shape == "iterator":
                    def supplied():
                        log.append(("iterator", "next"))
                        yield node(a)
                    return supplied()
                if shape == "short":
                    return (node(a), ("malformed",))
                if shape == "mutable":
                    return (list(node(a)),)
                if shape == "custom-mode":
                    class Mode:
                        def __eq__(self, other):
                            log.append(("mode", "eq"))
                            return other == "path"
                    return ((a, ModelPath, Mode(), node(a)[3]),)
                if shape == "different-kind":
                    return (node(a), node(OtherPath("b", log)))
                return (node(a), *N._history_graph({"items": [1, False]}), node(a))
            with self.subTest(shape=shape):
                self.equivalent(factory)
        a = ModelPath("a", [])
        mutable = list(node(a))
        history = N._ReaderPathHistory((mutable,))
        mutable[1] = str
        with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
            history.check()
        self.assertEqual(a.log, [])

    def test_supplied_mutable_container_keeps_live_iteration(self):
        def factory(log):
            a, b = ModelPath("a", log), ModelPath("b", log)
            nodes = [node(a)]
            def append():
                del a.hooks["root"]
                nodes.append(node(b))
            a.hooks["root"] = append
            return nodes
        self.assertEqual(self.equivalent(factory)[1], visits("a", "b"))

    def test_private_accumulator_observes_every_extension_and_repeat(self):
        log = []
        a, b = ModelPath("a", log), ModelPath("b", log)
        history = N._ReaderPathHistory.accumulating()
        history.check()
        self.assertEqual(log, [])
        history.extend((node(a), node(b)))
        history.extend((node(a),))
        self.assertEqual(log, [])
        history.check()
        history.check()
        self.assertEqual(log, visits("a", "b", "a") * 2)

    def test_interception_restoration_keeps_exposed_list_live_forever(self):
        log, exposed = [], []
        a, b = ModelPath("a", log), ModelPath("b", log)
        history = N._ReaderPathHistory.accumulating()
        history.extend((node(a),))
        class Replacement:
            def __getattribute__(self, name):
                if name == "__code__":
                    raise AssertionError("do not inspect an arbitrary helper's code")
                return object.__getattribute__(self, name)
            def __call__(self, nodes):
                exposed.append(nodes)
                return ORIGINAL_HISTORY(nodes)
        with patch.object(N, "_check_reader_path_history", Replacement()):
            history.check()
        self.assertIs(type(exposed[0]), list)
        exposed[0].append(node(b))
        history.extend((node(a),))
        log.clear()
        history.check()
        self.assertEqual(log, visits("a", "b", "a"))
        for prefix in ((node(a),), [node(a)]):
            exposed.clear()
            log.clear()
            with self.subTest(prefix=type(prefix).__name__):
                with patch.object(N, "_check_reader_path_history", Replacement()):
                    prefixed = N._ReaderPathHistory(prefix)
                    self.assertEqual(log, [])
                    prefixed.check()
                self.assertIs(exposed[0], prefix)
                self.assertIs(prefixed._fallback, True)
                if type(prefix) is list:
                    prefix.append(node(b))
                prefixed.check()
                self.assertEqual(log, visits("a", "a", *(("b",) if type(prefix) is list else ())))

    def test_fallback_releases_removed_saved_node_before_original_scan(self):
        for deletion in ("inside-helper", "after-restoration"):
            outcomes = []
            for planned in (False, True):
                log = []
                a = ModelPath("a", log)
                class Saved:
                    def __del__(self):
                        log.append(("saved", "released"))
                        a.values["root"] = "changed"
                nodes = [node(a), (ModelPath("b", log), ModelPath, "path", Saved())]
                if planned:
                    history = N._ReaderPathHistory.accumulating()
                    history.extend(nodes)
                    del nodes  # No external node/saved reference may mask the finalizer.
                    check = history.check
                else:
                    check = lambda: N._check_reader_path_history(nodes)
                def replacement(current):
                    del current[-1]
                    return ORIGINAL_HISTORY(current)
                with self.subTest(deletion=deletion, planned=planned):
                    if deletion == "inside-helper":
                        with patch.object(N, "_check_reader_path_history", replacement):
                            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED") as caught:
                                check()
                    else:
                        with patch.object(N, "_check_reader_path_history", lambda current: current):
                            retained = check()
                        self.assertEqual(log, [])
                        del retained[-1]
                        with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED") as caught:
                            check()
                    self.assertEqual(log, [("saved", "released")] + visits("a"))
                    outcomes.append((type(caught.exception), caught.exception.args, log))
            self.assertEqual(outcomes[0], outcomes[1])

    def test_inplace_helper_code_replacement_cannot_resume_a_stale_plan(self):
        log = []
        a, b = ModelPath("a", log), ModelPath("b", log)
        history = N._ReaderPathHistory.accumulating()
        history.extend((node(a),))
        def expose(nodes):
            return nodes
        code = ORIGINAL_HISTORY.__code__
        try:
            ORIGINAL_HISTORY.__code__ = expose.__code__
            exposed = history.check()
        finally:
            ORIGINAL_HISTORY.__code__ = code
        self.assertIs(type(exposed), list)
        exposed.append(node(b))
        history.check()
        self.assertEqual(log, visits("a", "b"))

    def test_helper_change_during_getter_applies_at_next_boundary_only(self):
        log, exposed = [], []
        a, b = ModelPath("a", log), ModelPath("b", log)
        history = N._ReaderPathHistory((node(a), node(b)))
        def replacement(nodes):
            exposed.append(nodes)
            return ORIGINAL_HISTORY(nodes)
        def change():
            del a.hooks["parts"]
            N._check_reader_path_history = replacement
        a.hooks["parts"] = change
        with patch.object(N, "_check_reader_path_history", ORIGINAL_HISTORY):
            history.check()
            self.assertEqual(log, visits("a", "b"))
            self.assertEqual(exposed, [])
            history.check()
        self.assertEqual(log, visits("a", "b") * 2)
        self.assertIs(type(exposed[0]), tuple)

    def test_partial_extension_and_plan_failure_preserve_original_nodes(self):
        for failure_kind in ("iterator", "plan"):
            log = []
            a = ModelPath("a", log)
            history = N._ReaderPathHistory.accumulating()
            error = FalseyFailure("MODEL_EXTENSION_FAILURE")
            def supplied():
                yield node(a)
                raise error
            with self.subTest(failure_kind=failure_kind):
                try:
                    if failure_kind == "iterator":
                        history.extend(supplied())
                    else:
                        with patch.object(N._ReaderPathHistory, "_append_plan", side_effect=error):
                            history.extend((node(a),))
                except BaseException as caught:
                    self.assertIs(caught, error)
                else:
                    self.fail("the original extension failure must escape")
                history.check()
                self.assertEqual(log, visits("a"))

    def test_reentrant_extension_or_check_never_clears_fallback_latch(self):
        for reentry in ("extend", "check"):
            log, exposed = [], []
            a, b, c = (ModelPath(name, log) for name in ("a", "b", "c"))
            history = N._ReaderPathHistory.accumulating()
            def replacement(nodes):
                exposed.append(nodes)
                N._check_reader_path_history = ORIGINAL_HISTORY
                return ORIGINAL_HISTORY(nodes)
            def supplied():
                yield node(a)
                if reentry == "extend":
                    history.extend((node(b),))
                else:
                    history.check()
                    yield node(b)
                yield node(c)
            with self.subTest(reentry=reentry), patch.object(N, "_check_reader_path_history", replacement):
                history.extend(supplied())
            self.assertIs(history._fallback, True, "reentrant extension/check must latch fallback permanently")
            if exposed:
                exposed[0].append(node(a))
            log.clear()
            history.check()
            self.assertEqual(log, visits("a", "b", "c", *(("a",) if exposed else ())))


class Key:
    def __init__(self, name, index, log, error=None):
        self.name, self.index, self.log, self.error = name, index, log, error

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if type(other) is str and other == self.name:
            self.log.append((self.index, self.name))
            if self.error is not None:
                raise self.error
            return True
        return False


def roster_fixture(log):
    resources = [object() for _ in range(5)]
    ledger = [{"label": "directory", "owner": resource, "attempted": False, "closed": False} for resource in resources]
    rows = [(row, "directory", resource, False, False) for row, resource in zip(ledger, resources)]
    return SimpleNamespace(owner=SimpleNamespace(resources=ledger), ledger=ledger, rows=rows,
        prefix=tuple(rows[:2]), held=resources[2:], new_rows=ledger[2:], missing=object(), log=log)


def traced_keys(fixture, *, error_at=None, error=None):
    for index, row in enumerate(fixture.ledger):
        items = list(row.items())
        row.clear()
        row.update((Key(name, index, fixture.log, error if (index, name) == error_at else None), value)
            for name, value in items)


class ReaderRosterModels(unittest.TestCase):
    def equivalent(self, kind, configure, *, tail=False, error=None):
        functions = ((original_graph_roster, N._graph_reader_roster) if kind == "graph" else
            (original_query_roster, N._query_reader_roster))
        outcomes = []
        for function in functions:
            log = []
            fixture = roster_fixture(log)
            configure(fixture)
            log.clear()
            try:
                if kind == "graph":
                    result = function(fixture.owner, fixture.ledger, fixture.rows, fixture.missing, tail=tail)
                else:
                    result = function(fixture.owner, fixture.ledger, fixture.prefix, fixture.held, fixture.new_rows, fixture.missing)
                self.assertIs(type(result), bool)
                outcome = ("return", result)
            except BaseException as caught:
                if error is not None:
                    self.assertIs(caught, error)
                outcome = ("raise", type(caught), caught.args)
            if error is not None:
                self.assertEqual(outcome[0], "raise")
            outcomes.append((outcome, log))
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[1]

    def test_first_middle_last_binding_mutations_match_exact_preimage(self):
        mutations = {
            "unchanged": lambda f, i: None,
            "row-copy": lambda f, i: f.ledger.__setitem__(i, dict(f.ledger[i])),
            "row-type": lambda f, i: f.ledger.__setitem__(i, object()),
            "owner": lambda f, i: f.ledger[i].__setitem__("owner", object()),
            "label": lambda f, i: f.ledger[i].__setitem__("label", "writer"),
            "attempted-alias": lambda f, i: f.ledger[i].__setitem__("attempted", 0),
            "closed-alias": lambda f, i: f.ledger[i].__setitem__("closed", 0),
            "extra-key": lambda f, i: f.ledger[i].__setitem__("extra", None),
            "missing-label": lambda f, i: (f.ledger[i].pop("label"), f.ledger[i].__setitem__("extra", None)),
            "missing-owner": lambda f, i: (f.ledger[i].pop("owner"), f.ledger[i].__setitem__("extra", None)),
        }
        for kind in ("graph", "query"):
            for index in (0, 2, 4):
                for name, mutate in mutations.items():
                    with self.subTest(kind=kind, index=index, mutation=name):
                        outcome, _ = self.equivalent(kind, lambda f: mutate(f, index))
                        self.assertEqual(outcome, ("return", name == "unchanged"))

    def test_ledger_length_identity_tail_and_query_row_phase(self):
        changes = (
            lambda f: setattr(f.owner, "resources", list(f.ledger)),
            lambda f: f.ledger.pop(),
            lambda f: f.ledger.append(dict(f.ledger[-1])),
        )
        for kind in ("graph", "query"):
            for change in changes:
                self.assertEqual(self.equivalent(kind, change)[0], ("return", False))
        self.assertEqual(self.equivalent("graph", changes[2], tail=True)[0], ("return", True))
        self.assertEqual(self.equivalent("graph", changes[1], tail=True)[0], ("return", False))
        self.assertEqual(self.equivalent("query", lambda f: f.new_rows.__setitem__(1, dict(f.new_rows[1])))[0], ("return", False))

    def test_query_tail_row_finalizer_runs_before_fresh_identity_slice(self):
        def configure(fixture):
            class Label:
                def __eq__(self, other):
                    fixture.log.append(("tail", "restore"))
                    fixture.ledger[-1] = fixture.new_rows[-1]
                    return other == "directory"
                def __del__(self):
                    fixture.log.append(("tail", "released"))
                    fixture.ledger[-1] = object()
            copied = dict(fixture.new_rows[-1])
            copied["label"] = Label()
            fixture.ledger[-1] = copied
        outcome, log = self.equivalent("query", configure)
        self.assertEqual(outcome, ("return", False))
        self.assertEqual(log, [("tail", "restore"), ("tail", "released")])

    def test_both_label_lookups_and_ordered_phase_traces_are_preserved(self):
        for kind in ("graph", "query"):
            outcome, log = self.equivalent(kind, traced_keys)
            self.assertEqual(outcome, ("return", True))
            self.assertEqual(log.count((0, "label")), 2)
            self.assertEqual(log.count((4, "label")), 2 if kind == "graph" else 1)

    def test_custom_key_exception_is_not_converted_or_swallowed(self):
        error = KeyError("MODEL_ORIGINAL_KEY_EQUALITY")
        for kind in ("graph", "query"):
            for index in (0, 2, 4):
                with self.subTest(kind=kind, index=index):
                    self.equivalent(kind, lambda f: traced_keys(f, error_at=(index, "label"), error=error), error=error)

    def test_stateful_truth_conversion_release_and_original_failure(self):
        error = FalseyFailure("MODEL_ORIGINAL_TRUTH_FAILURE")
        for kind in ("graph", "query"):
            for states in ((False, False), (False, True), (True,), (False, error)):
                def configure(fixture):
                    class Truth:
                        def __init__(self):
                            self.states = iter(states)
                        def __bool__(self):
                            value = next(self.states)
                            fixture.log.append(("truth", "raise" if value is error else value))
                            if value is error:
                                raise error
                            return value
                        def __del__(self):
                            fixture.log.append(("truth", "released"))
                    class Label:
                        def __eq__(self, other):
                            fixture.log.append(("label", "eq"))
                            return Truth()
                    fixture.ledger[2]["label"] = Label()
                    traced_keys(fixture)
                with self.subTest(kind=kind, states=tuple("error" if v is error else v for v in states)):
                    self.equivalent(kind, configure, error=error if any(v is error for v in states) else None)

    def test_first_refusal_does_not_observe_later_row(self):
        def configure(fixture):
            fixture.ledger[0]["extra"] = None
            traced_keys(fixture, error_at=(4, "label"), error=AssertionError("later row must not be observed"))
        for kind in ("graph", "query"):
            self.assertEqual(self.equivalent(kind, configure)[0], ("return", False))


class ReaderScanDiagnostics(unittest.TestCase):
    def test_bounded_saved_metadata_and_roster_cost_only(self):
        # Independent selection only. No pass here can qualify the real reader.
        nodes = tuple(node_ for index in range(221) for node_ in N._history_graph(
            Path("/MODEL/receiver/fixed/graph") / str(index), Path("/MODEL/receiver/fixed/graph") / str(index)))
        self.assertEqual(len(nodes), 442)
        baseline = list(nodes)
        planned = N._ReaderPathHistory.accumulating()
        planned.extend(nodes)
        fixture = roster_fixture([])
        for _ in range(218):
            resource = object()
            row = {"label": "directory", "owner": resource, "attempted": False, "closed": False}
            fixture.ledger.append(row)
            fixture.rows.append((row, "directory", resource, False, False))
        self.assertEqual(len(fixture.rows), 223)
        def scan(original):
            if original:
                ORIGINAL_HISTORY(baseline)
                valid = original_graph_roster(fixture.owner, fixture.ledger, fixture.rows, fixture.missing)
            else:
                planned.check()
                valid = N._graph_reader_roster(fixture.owner, fixture.ledger, fixture.rows, fixture.missing)
            if not valid:
                raise AssertionError("MODEL_SCAN_ROSTER_CHANGED")
        for _ in range(10):
            scan(True)
            scan(False)
        print("SCAN_DIAGNOSTIC_ONLY PATH_NODES=442 ROWS=223 LOOPS_PER_SAMPLE=1000 SAMPLES_PER_IMPLEMENTATION=2", flush=True)
        for original in (True, False, False, True):
            before = time.process_time_ns()
            for _ in range(1000):
                scan(original)
            elapsed = time.process_time_ns() - before
            print("SCAN_IMPLEMENTATION=%s CPU_NS=%d" % ("preimage" if original else "candidate", elapsed), flush=True)
        print("NO_COMPLETE_GRAPH NO_OWNER_CLOSE NO_NATIVE_PROVIDER NO_AUTHORITY NO_CPU20_QUALIFICATION", flush=True)


if __name__ == "__main__":
    unittest.main()
