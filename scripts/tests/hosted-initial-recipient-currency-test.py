#!/usr/bin/env python3
"""Offline currency controls; no native acquisition, credentials, HTTP or logs.

Execute selected, unchanged production functions, not another test suite. The
external/native seams are explicitly synthetic: host, retained-input transport
interpretation, matcher, service steps, clocks, current-owner callback, paths,
native metadata identity and the eleven input names/limits. Thus neither these
controls nor --benchmark qualify a native/hosted run or its remaining budget.
"""

import __future__
import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).resolve().parents[2]
OLD = "        raws, _input_metadata, _metadata = _checked_before_input(result.input)\n"
NEW = ("        _checked_before_input(result.input, _guard_only=True)\n"
       "        raws = dict(result.input.originals)\n")
BASE_SHA = "ada25c13de1e74659d074c8c19ce9fb18b7729d0bb978d061f5e44a69605a4e2"
# Only new failure codec is stripped for unchanged historical DATA suppliers.
_K_FAILURE_CODEC = b'def _tail_child_failure_projection(raw):\n    """One exact K-child refusal packet to finite DATA; never reader/close proof."""\n    try:\n        if type(raw) is not bytes or not 0 < len(raw) <= 65536:\n            return None\n        lines = raw.split(b"\\n")\n        if len(lines) != 3 or lines[0] != b"INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED" or \\\n                lines[2] != b"" or not 0 < len(lines[1]) <= 2048:\n            return None\n        line = lines[1].decode("ascii")\n\n        def pairs(items):\n            result = {}\n            for key, value in items:\n                if key in result:\n                    raise ValueError("TAIL_CHILD_DUPLICATE_FIELD")\n                result[key] = value\n            return result\n\n        def nonfinite(_value):\n            raise ValueError("TAIL_CHILD_NONFINITE_JSON")\n\n        value = json.loads(line, object_pairs_hook=pairs, parse_constant=nonfinite)\n        fixed = {"schema": 1, "scope": "INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",\n            "operation": "_tail-child", "kind": "UNAVAILABLE"}\n        if type(value) is not dict or set(value) != {*fixed, "stage", "origin", "sites", "truncated"} or \\\n                any(type(value[key]) is not type(expected) or value[key] != expected for key, expected in fixed.items()) or \\\n                type(value["origin"]) is not str or value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH") or \\\n                type(value["stage"]) is not str or not (value["stage"] in ("CHILD_ENTRY", "CHILD_WORK") or\n                    value["stage"] == "UNAVAILABLE" and value["origin"] == "FINAL_CATCH") or \\\n                type(value["truncated"]) is not bool or type(value["sites"]) is not list or len(value["sites"]) > 12:\n            return None\n        for row in value["sites"]:\n            if type(row) is not dict or set(row) != {"module", "line"} or type(row["module"]) is not str or \\\n                    row["module"] not in _TAIL_FAILURE_PATHS.values() or type(row["line"]) is not int or \\\n                    not 1 <= row["line"] <= 1_000_000:\n                return None\n        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)\n        return encoded if encoded == line else None\n    except BaseException:\n        return None\n\n\n'
SOURCE_PINS = {
    "run-hosted-initial-recipient.py": "fc305aaf82b26d3175a69ee02aa4bc9376ce820f9f6217bd243e13b54e49dcfc",
    "hosted_initial_recipient_before.py": "600e156921a806dc7880bf7e6ccefb08929b551c5e72463480aabc250e021688",
    "hosted_full_job_budget.py": "95fb79e994746e85439446d39a49017fefa782d2b7182523db4ad1f2b071b1a3",
    "hosted_test_identity.py": "07faeecd034439ea82dd2b05bcfd2f9ce4d6a44117b959b855d2c39651d3b770",
}
KEYS = ("seal", "step", "carrier", "context", "manifest", "original-match",
        "fresh-match", "event", "policy", "public", "collect")
GRAMMAR = tuple((key, "synthetic/" + key, 1024 * 1024) for key in KEYS)


class Refusal(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Refusal(code)


def encoded(value):
    # Fixture construction only; measured consumers use extracted wire encoding.
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def source_trees():
    candidate = (ROOT / "scripts/run-hosted-initial-recipient-custody.py").read_bytes()
    require(candidate.count(NEW.encode()) == 1 and OLD.encode() not in candidate, "EXACT_CURRENCY_DELTA")
    old_schedule, new_schedule = b'    work = min(O.integer(start + 240 * O.NS), job_end - 180 * O.NS)\n', b'    work = (job_end - 180 * O.NS if kind == "gate" else\n        min(O.integer(start + 240 * O.NS), job_end - 180 * O.NS))\n'
    require(candidate.count(new_schedule) == 1, "EXACT_GATE_ALLOCATION_DELTA")
    baseline = candidate.replace(new_schedule, old_schedule, 1).replace(NEW.encode(), OLD.encode(), 1)
    require(hashlib.sha256(baseline).hexdigest() == BASE_SHA, "EXACT_77_CUSTODY_SOURCE")
    sources = {"candidate": candidate, "baseline": baseline,
               "currency-only-candidate": candidate.replace(new_schedule, old_schedule, 1)}
    for name, pin in SOURCE_PINS.items():
        raw = (ROOT / "scripts" / name).read_bytes()
        if name == "hosted_initial_recipient_before.py":
            require(raw.count(_K_FAILURE_CODEC) == 1, "EXACT_K_FAILURE_CODEC_ADDITION")
            raw = raw.replace(_K_FAILURE_CODEC, b"", 1)
        require(hashlib.sha256(raw).hexdigest() == pin, "UNCHANGED_DEPENDENCY:" + name)
        sources[name] = raw
    return {name: ast.parse(raw, filename=name) for name, raw in sources.items()}


def extract(tree, names, space):
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                and node.name in names]
    require({node.name for node in selected} == set(names), "EXTRACT_EXACT_NAMES")
    code = compile(ast.Module(body=selected, type_ignores=[]), "<actual-production-functions>", "exec",
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(code, space)


@dataclass
class Match:
    record: bytes


class Fixture:
    """Pure declared objects; even paths are never opened or claimed native."""

    def __init__(self, trees, variant="candidate", size=1024):
        self.events, self.counts, self.hooks = [], Counter(), {}
        self.error, self.fault, self.epoch = RuntimeError("synthetic callback failure"), None, 10
        self.matches, self.priors = [], []
        self.trace = True
        dummy = type("UnusedSyntheticRecord", (), {})
        history = dict(__name__=__name__, require=require, ROOT=ROOT)
        for name in ("_ReadmissionReturn", "_ReadmissionBinding", "_ReadmissionClaim", "_PreparationBinding",
                     "_OriginalPreparation", "_OriginalServiceJobAdmission", "_EntryWindowBinding",
                     "_ReadmissionWindow", "SourceReturn", "_AuthorityReturn", "_AuthorityState",
                     "_RecipientRoster", "_RecipientNativeReturn", "_RecipientValidationReturn",
                     "_RecipientState", "_RecipientCryptoOriginals"):
            history[name] = dummy
        history.update(native=NS(Owner=dummy, OriginalPhase=dummy),
                       O=NS(Fence=dummy, clocks=NS(Reading=dummy, ClockIdentity=dummy)),
                       initial_identity=NS(InitialBootstrapIdentity=dummy),
                       acquisition=NS(stages=NS(BootstrapMatch=Match)))
        primary = trees["run-hosted-initial-recipient.py"]
        extract(primary, ("_history_graph", "_check_history"), history)
        latch = dict(__name__=__name__, require=require, BeforeError=Refusal, _ENTRY_LATCHES={},
                     _tail_failure_remember=lambda error: None)
        extract(trees["hosted_initial_recipient_before.py"], ("EntryLatch",), latch)
        retained = dict(__name__=__name__, require=require, _retained_match_inputs=self.interpret,
                        acquisition=NS(gate=NS(eligible=self.matcher), stages=NS(match_bootstrap=self.matcher)),
                        time=NS(time=self.wall_time))
        extract(primary, ("_retained_match_at", "retained_match"), retained)
        parser = dict(__name__=__name__, require=require, json=json, AdmissionError=Refusal)
        extract(trees["hosted_test_identity.py"], ("parse",), parser)
        wire = dict(__name__=__name__, require=require, json=json, hashlib=hashlib, RECORD_LIMIT=2*1024*1024,
                    UINT64=(1 << 64) - 1, identity=NS(parse=parser["parse"]))
        extract(trees["hosted_full_job_budget.py"], ("encoded", "parse", "integer", "digest"), wire)
        self.wire = NS(**wire)
        self.history = NS(**history)
        self.space = dict(__name__=__name__, dataclass=dataclass, require=require, re=re, math=math, MAX_MEMBERS=1000,
                          O=NS(integer=wire["integer"], encoded=wire["encoded"], parse=wire["parse"], digest=self.digest,
                               clocks=NS(DOMAINS={"linux-x64": "synthetic"})),
                          native=NS(LIMIT=1024 * 1024, directory_identity=lambda value, role: tuple(value)),
                          N=NS(_history_graph=history["_history_graph"], _check_history=history["_check_history"],
                               retained_match=retained["retained_match"]),
                          A=NS(gate=NS(GateEligibility=Match), stages=NS(BootstrapMatch=Match)),
                          B=NS(EntryLatch=latch["EntryLatch"]), os=NS(environ={}), _CREDENTIAL_NAMES=("TOKEN",),
                          _BEFORE_INPUTS={}, _BEFORE_INPUT_PROOFS={}, _BEFORE_ACQUIRED={}, _BEFORE_ATTEMPTS={},
                          _before_originals=lambda: GRAMMAR, _TAIL_LIMITS=dict.fromkeys(KEYS[1:], 1024 * 1024),
                          _before_actual=lambda actual: self.event("actual"),
                          _collect_directory_closed=lambda directory, role: directory.closed,
                          _tail_bundle=self.bundle, _tail_host=self.host, _before_service_steps=self.service_steps)
        extract(trees[variant], ("fields", "digest", "local_value", "canonical", "_same",
                                "_BeforeInput", "_checked_before_input", "_before_metadata", "_before_same_read",
                                "_before_input_data", "_collect_close_rows", "_collect_file_close",
                                "_BeforeAcquired", "_checked_before_acquired", "_before_entry_current",
                                "_custody_match_pin", "_custody_match_check", "_before_currency"), self.space)
        self.actual_canonical = self.space["canonical"]
        self.space["canonical"] = self.canonical
        self.api = NS(**self.space)
        attempts = self.space["_BEFORE_ATTEMPTS"]
        entry_latch = latch["EntryLatch"](attempts)
        self.space["_BEFORE_ENTRY"] = entry_latch
        self.entry = (entry_latch, entry_latch.begin(attempts))
        self.identity = NS(role="linux-x64")
        self.owner = NS(first=NS(clock=self.identity), closed=True, unknown=False, original=None)
        self.anchor = object()
        self.metadata = NS(_anchor=lambda: self.anchor, structural=lambda: self.event("structural"),
                           finished=True, failure=None, owner=self.owner, errors=[], rows=[])
        resources = [dict(ordinal=n, label="reader" if n < 22 else "directory", closeAttempted=True, closed=True)
                     for n in range(26)]
        self.metadata.rows = [(n, row["label"], object(), True, True) for n, row in enumerate(resources)]
        rows, originals = [], []
        for n, (key, relative, maximum) in enumerate(GRAMMAR):
            raw = bytes([65 + n]) * size
            originals.append((key, raw))
            info = dict(device=1, inode=100+n, size=size, mtime_ns=1, ctime_ns=1)
            first = dict(bytes=size, sha256=hashlib.sha256(raw).hexdigest(), metadata=info,
                         readerOrdinal=2*n, retirement="KNOWN_READER_CLOSE")
            rows.append(dict(key=key, relative=relative, maximum=maximum, first=first,
                             readback=dict(first, metadata=dict(info), readerOrdinal=2*n+1)))
        close = dict(schema=1, scope="INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1", resources=resources,
                     retirement="KNOWN_RESOURCE_CLOSE_ONLY", exportSaveAuthority=False)
        raw = encoded(dict(firstNs=1, firstLocal=1, closedNs=2, closedLocal=2, files=rows, ownerClose=close))
        self.input = self.api._BeforeInput(tuple(originals), raw)
        self.directories = [NS(path=Path("/synthetic-not-opened/d" + str(n)), identity=(1, n+1), closed=True)
                            for n in range(4)]
        pins = tuple((str(n), directory, directory.path, directory.identity)
                     for n, directory in enumerate(self.directories))
        self.input_saved = (self.input, self.input.__dict__, self.input.originals, raw, self.metadata, self.anchor,
                            pins, history["_history_graph"](self.input.__dict__, self.owner.__dict__), ("synthetic",))
        self.space["_BEFORE_INPUTS"][id(self.input)] = self.input_saved
        self.clock_anchor = NS(binding=(None,) * 9 + (self.entry,), failure=None)
        self.clock = NS(clock=self.identity, frame={"kind": "gate"}, now=lambda: self.event("clock.now"),
                        _view=lambda: self.event("clock.view", self.clock_anchor))
        acquired_owner = NS(_anchor=lambda: self.anchor)
        captured = (encoded({"synthetic": True}), (("record", b"synthetic"),), "synthetic-invocation", 1, 2)
        self.result = self.api._BeforeAcquired(self.input, self.clock, acquired_owner, None, None, None, None, None,
                                              captured, Match(b"synthetic-match"), {"serviceSteps": ["synthetic"]})
        self.saved = (self.result, self.result.__dict__, lambda: self.event("current"),
                      history["_history_graph"](self.result.__dict__), {"failure": None, "state": "ACQUIRED"},
                      b"child", b"session", b"context", acquired_owner, self.anchor, self.clock, self.entry)
        self.space["_BEFORE_ACQUIRED"][id(self.result)] = self.saved

    def event(self, name, value=None):
        if self.trace:
            self.events.append(name)
        self.counts[name] += 1
        if self.fault == name:
            raise self.error
        hook = self.hooks.pop(name, None)
        if hook is not None:
            hook()
        return value

    def canonical(self, raw):
        self.counts["canonical"] += 1
        return self.actual_canonical(raw)

    def digest(self, raw):
        self.counts["digest"] += 1
        return self.wire.digest(raw)

    def bundle(self, prior):
        return self.event("bundle", {"synthetic": True})

    def host(self, prior, bundle, clock):
        self.priors.append(prior)
        match = Match(b"synthetic-match")
        self.matches.append(match)
        return self.event("host", match)

    def interpret(self, context, originals, invocation, clock, began, end):
        require(context == {"synthetic": True} and originals == {"record": b"synthetic"}, "SYNTHETIC_CAPTURE")
        return self.event("interpret", ("gate", {"deadline": 20}, {"synthetic": True}))

    def wall_time(self):
        return self.event("wall-time", self.epoch)

    def matcher(self, *, now, deadline):
        self.event("matcher")
        require(now < deadline, "SYNTHETIC_EXPIRED")
        match = Match(b"synthetic-match")
        self.matches.append(match)
        return match

    def service_steps(self, captured, clock):
        return self.event("service-steps", ["synthetic"])

    def currency(self):
        return self.api._before_currency(self.result)

    def reset_counts(self):
        self.counts.clear()
        self.events.clear()


class CurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trees = source_trees()

    def fixture(self, variant="candidate"):
        return Fixture(self.trees, variant)

    def test_exact_inverse_and_only_currency_ast_changes(self):
        def functions(tree):
            return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        old, new = functions(self.trees["baseline"]), functions(self.trees["currency-only-candidate"])
        self.assertEqual(set(old), set(new))
        self.assertEqual([name for name in old if old[name] != new[name]], ["_before_currency"])

    def test_cold_and_warm_preserve_live_order_but_remove_only_repeated_pure_work(self):
        baseline, candidate = self.fixture("baseline"), self.fixture()
        expected = ["current", "clock.view", "actual", "structural", "bundle", "host", "interpret",
                    "wall-time", "matcher", "service-steps", "clock.now", "current", "clock.view"]
        for round_number in range(3):
            for fixture in (baseline, candidate):
                fixture.reset_counts()
                self.assertIs(fixture.currency(), fixture.saved)
                self.assertEqual(fixture.events, expected)
            self.assertEqual(baseline.counts["digest"], 11)
            self.assertEqual(candidate.counts["digest"], 11 if round_number == 0 else 0)
            self.assertEqual(baseline.counts["canonical"], 3)
            self.assertEqual(candidate.counts["canonical"], 3 if round_number == 0 else 1)
            self.assertEqual(baseline.priors[-1], candidate.priors[-1])
        self.assertIsNot(candidate.priors[0], candidate.priors[1])
        candidate.priors[0].clear()
        self.assertEqual(len(candidate.priors[1]), 10)

    def test_original_full_check_keeps_fresh_mutable_returns_after_guard(self):
        f = self.fixture()
        check = f.api._checked_before_input
        self.assertIsNone(check(f.input, _guard_only=True))
        first, second = check(f.input), check(f.input)
        self.assertEqual(first[:2], second[:2])
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[1], second[1])
        self.assertIs(first[2], f.metadata)
        first[0].clear()
        first[1]["files"][0]["first"]["sha256"] = "0" * 64
        self.assertEqual(check(f.input)[:2], second[:2])
        for bad in (None, 0, 1, "guard"):
            with self.assertRaisesRegex(Refusal, "BEFORE_INPUT_GUARD_MODE"):
                check(f.input, _guard_only=bad)

    def test_cold_hash_validation_cannot_be_replaced_by_guard(self):
        for variant in ("baseline", "candidate"):
            f = self.fixture(variant)
            originals = ((KEYS[0], b"changed"), *f.input.originals[1:])
            object.__setattr__(f.input, "originals", originals)
            saved = list(f.input_saved)
            saved[2], saved[7] = originals, f.history._history_graph(f.input.__dict__, f.owner.__dict__)
            f.space["_BEFORE_INPUTS"][id(f.input)] = tuple(saved)
            with self.assertRaisesRegex(Refusal, "BEFORE_INPUT_HASH_CHANGED"):
                f.currency()
            self.assertNotIn(id(f.input), f.space["_BEFORE_INPUT_PROOFS"])
            self.assertNotIn("host", f.events)

    def test_warm_proof_does_not_bypass_mutation_owner_or_directory_guards(self):
        changes = {
            "registry": lambda f: f.space["_BEFORE_INPUTS"].__setitem__(id(f.input), tuple(list(f.input_saved))),
            "proof": lambda f: f.space["_BEFORE_INPUT_PROOFS"].__setitem__(id(f.input), (f.input_saved, "other")),
            "originals": lambda f: object.__setattr__(f.input, "originals", tuple(list(f.input.originals))),
            "metadata": lambda f: object.__setattr__(f.input, "metadata", f.input.metadata + b" "),
            "unknown": lambda f: setattr(f.owner, "unknown", True),
            "not-closed": lambda f: setattr(f.owner, "closed", False),
            "native-original": lambda f: setattr(f.owner, "original", object()),
            "metadata-failure": lambda f: setattr(f.metadata, "failure", f.error),
            "unfinished": lambda f: setattr(f.metadata, "finished", False),
            "row-close": lambda f: f.metadata.rows.__setitem__(0, (0, "reader", object(), True, False)),
            "anchor": lambda f: setattr(f, "anchor", object()),
            "path": lambda f: setattr(f.directories[0], "path", Path("/synthetic-not-opened/replaced")),
            "identity": lambda f: setattr(f.directories[0], "identity", (2, 3)),
            "directory-close": lambda f: setattr(f.directories[0], "closed", False),
            "role": lambda f: setattr(f.identity, "role", "windows-x64"),
        }
        for variant in ("baseline", "candidate"):
            for name, change in changes.items():
                with self.subTest(variant=variant, change=name):
                    f = self.fixture(variant)
                    f.currency()
                    f.reset_counts()
                    change(f)
                    with self.assertRaises(Refusal) as first:
                        f.currency()
                    self.assertNotIn("host", f.events)
                    with self.assertRaises(Refusal) as second:
                        f.currency()
                    self.assertIs(first.exception, second.exception)

    def test_callback_failures_are_sticky_and_do_not_continue(self):
        names = ("current", "clock.view", "actual", "structural", "bundle", "host", "interpret", "wall-time",
                 "matcher", "service-steps", "clock.now")
        for variant in ("baseline", "candidate"):
            for name in names:
                with self.subTest(variant=variant, callback=name):
                    f = self.fixture(variant)
                    f.currency()
                    f.reset_counts()
                    f.fault = name
                    with self.assertRaises(RuntimeError) as first:
                        f.currency()
                    self.assertIs(first.exception, f.error)
                    self.assertEqual(f.events[-1], name)
                    f.fault = None
                    before = list(f.events)
                    with self.assertRaises(RuntimeError) as second:
                        f.currency()
                    self.assertIs(second.exception, f.error)
                    self.assertEqual(f.events, before)

    def test_late_time_live_host_match_pins_and_final_acquisition_remain_checked(self):
        for variant in ("baseline", "candidate"):
            for boundary in ("late-expiry", "host-match", "expected-pin", "retained-pin", "final-acquisition"):
                with self.subTest(variant=variant, boundary=boundary):
                    f = self.fixture(variant)
                    f.currency()
                    f.reset_counts()
                    if boundary == "late-expiry":
                        f.hooks["interpret"] = lambda: setattr(f, "epoch", 20)
                    elif boundary == "host-match":
                        f.hooks["host"] = lambda: setattr(f.matches[-1], "record", b"changed")
                    elif boundary in ("expected-pin", "retained-pin"):
                        index = -2 if boundary == "expected-pin" else -1
                        f.hooks["clock.now"] = lambda: setattr(f.matches[index], "record", b"changed")
                    else:
                        f.hooks["clock.now"] = lambda: f.space["_BEFORE_ACQUIRED"].__setitem__(
                            id(f.result), tuple(list(f.saved)))
                    with self.assertRaises(Refusal) as first:
                        f.currency()
                    if boundary == "late-expiry":
                        self.assertEqual(f.events[-3:], ["interpret", "wall-time", "matcher"])
                        self.assertEqual(str(first.exception), "SYNTHETIC_EXPIRED")
                    with self.assertRaises(Refusal) as second:
                        f.currency()
                    self.assertIs(first.exception, second.exception)

    def test_reentrant_callback_cannot_hide_original_latch_failure(self):
        for variant in ("baseline", "candidate"):
            f = self.fixture(variant)
            f.currency()
            def reenter():
                f.fault = "matcher"
                try:
                    f.currency()
                except RuntimeError as error:
                    self.assertIs(error, f.error)
                finally:
                    f.fault = None
            f.hooks["host"] = reenter
            with self.assertRaises(RuntimeError) as failure:
                f.currency()
            self.assertIs(failure.exception, f.error)
            self.assertIs(f.entry[1]["failure"], f.error)


def benchmark(trees):
    """Fixed work, warm proofs, alternating order; no timing acceptance test."""
    batches, calls, size = 5, 64, 65536
    fixtures = {name: Fixture(trees, name, size) for name in ("baseline", "candidate")}
    elapsed, counts = {name: [] for name in fixtures}, {}
    for fixture in fixtures.values():
        fixture.trace = False
        fixture.currency()  # Cold validation excluded equally, not skipped.
        fixture.reset_counts()
    for batch in range(batches):
        for name in (("baseline", "candidate") if batch % 2 == 0 else ("candidate", "baseline")):
            fixture = fixtures[name]
            started = time.perf_counter_ns()
            for _ in range(calls):
                require(fixture.currency() is fixture.saved, "BENCHMARK_RETURN")
            elapsed[name].append(time.perf_counter_ns() - started)
    for name, fixture in fixtures.items():
        counts[name] = dict(fixture.counts)
    print(json.dumps({"scope": "OFFLINE_SYNTHETIC_CURRENCY_ONLY", "nativeQualification": False,
                      "hostedBudgetSufficiency": "NOT_ESTABLISHED", "baselineSourceSha256": BASE_SHA,
                      "batches": batches, "callsPerBatch": calls, "originalCount": 11,
                      "bytesPerOriginal": size, "totalOriginalBytes": 11 * size,
                      "batchNs": elapsed, "medianNsPerCall": {name: statistics.median(values) / calls
                                                               for name, values in elapsed.items()},
                      "minNsPerCall": {name: min(values) / calls for name, values in elapsed.items()},
                      "operationCounts": counts}, sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--benchmark"]:
        benchmark(source_trees())
    else:
        unittest.main(failfast=True)
