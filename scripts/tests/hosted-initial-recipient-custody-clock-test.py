#!/usr/bin/env python3
"""Focused fixed custody child-clock models, not caller/native qualification.

AST-select the complete maintained child guard, unchanged _RecipientWindow,
history graph/checker, checked_now/data validators, canonical parser/encoder and
directed conversion. Do not import either controller or an earlier test suite.
The guard must exist in the driver: no private-fragment fallback or skip exists.

Only RAW/LOCAL/boot/cancellation and metadata/operative ownership are modeled.
The first Reading is an explicitly synthetic fixture, not a recovered original
observation. Ledger models retain independent row/resource tuples and perform
counter-only closes. They do NOT test _PrimaryOwner, _CustodyOwner, native close, host/frame
authentication, token handling, the complete child caller or hosted execution.
The selected cap's now/deadline are replaced by refusal spies solely to prove
that the guard uses its unchanged constructor/arithmetic, never its observer.
Private guard anchors are inspected to check retained frontiers and consumed
transitions; no original owner, live Recipient or historical LOCAL is restored.
"""
from __future__ import annotations

import ast
import dataclasses
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
D_PATH = SCRIPTS / "run-hosted-initial-recipient-custody.py"
B_PATH = SCRIPTS / "run-hosted-cache-bootstrap.py"
N_PATH = SCRIPTS / "run-hosted-initial-recipient.py"
CLOCK_PATH = SCRIPTS / "hosted_job_clock.py"
WIRE_PATH = SCRIPTS / "hosted_full_job_budget.py"
ORIGIN_PATH = SCRIPTS / "hosted_cache_bootstrap_origin.py"
IDENTITY_PATH = SCRIPTS / "hosted_test_identity.py"
GATE_PATH = SCRIPTS / "hosted_initial_recipient_gate.py"
STAGES_PATH = SCRIPTS / "hosted_initial_recipient_stages.py"
TREES = {path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path)) for path in
    (D_PATH, B_PATH, N_PATH, CLOCK_PATH, WIRE_PATH, ORIGIN_PATH, IDENTITY_PATH, GATE_PATH, STAGES_PATH)}
NS = 1_000_000_000
BOOT = "a" * 64


class ModelRefusal(ValueError):
    pass


class FalseyRefusal(ModelRefusal):
    def __bool__(self):
        return False


def model_require(value, reason):
    if not value:
        raise ModelRefusal(reason)


def target_names(target):
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(target_names(value) for value in target.elts))
    return set()


def selected(path, names, bindings=None, *, constants=()):
    """Select whole definitions/constants from this checkout, never a fallback."""
    wanted, constant_names = set(names), set(constants)
    counts = {name: 0 for name in (*names, *constants)}
    nodes = []
    for node in TREES[path].body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
            counts[node.name] += 1
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            supplied = set().union(*(target_names(target) for target in node.targets)) & constant_names
            if supplied:
                for name in supplied:
                    counts[name] += 1
                nodes.append(node)
    model_require(all(value == 1 for value in counts.values()), "MODEL_UNIQUE_SOURCE_DEFINITIONS")
    space = {"__name__": __name__, "dataclass": dataclass, "field": field, "dataclasses": dataclasses}
    space.update(bindings or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec", dont_inherit=True), space)
    model_require((wanted | constant_names) <= space.keys(), "MODEL_MISSING_SOURCE_DEFINITION")
    return space


class NativeOwnerModel:
    """Data-only native-owner shape; never opens or retires anything native."""
    def __init__(self, first, fence):
        self.first, self.fence = first, fence
        self.resources, self.errors = [], []
        self.closed, self.original, self.unknown = False, None, False


class ResourceModel:
    def __init__(self, name):
        self.identity = {"modelResource": name}
        self.close_calls, self.closed = 0, False

    def close(self, *, failure=None):
        self.close_calls += 1
        if failure is not None:
            raise failure
        self.closed = True


class LedgerModel:
    """Explicit strong owner-contract model, not the PRIMARY implementation."""
    def __init__(self, rig):
        self._rig = rig
        self.owner = NativeOwnerModel(rig.first, rig.guard)
        self.first, self.window = rig.first, rig.guard
        self.rows, self.errors = [], self.owner.errors
        self.finished, self.failure = False, None
        rig.ledgers[self] = SimpleNamespace(owner=self.owner, dictionary=self.owner.__dict__,
            resources=self.owner.resources, rows=self.rows, errors=self.errors, entries=(),
            closed=False, finished=False, failure=None, unknown=False, saved_errors=())

    def structural(self):
        rig, saved = self._rig, self._rig.ledgers[self]
        rig.model_checks += 1
        model_require(self.owner is saved.owner and type(self.owner) is NativeOwnerModel and
            self.owner.__dict__ is saved.dictionary and self.owner.first is rig.first and
            self.owner.fence is rig.guard and self.first is rig.first and self.window is rig.guard,
            "MODEL_ORIGINAL_OWNER")
        model_require(self.rows is saved.rows and self.owner.resources is saved.resources and
            self.errors is saved.errors and self.owner.errors is saved.errors and
            tuple(self.errors) == saved.saved_errors and self.finished is saved.finished and
            self.failure is saved.failure and self.owner.original is saved.failure and
            self.owner.unknown is saved.unknown and self.owner.closed is saved.closed,
            "MODEL_ORIGINAL_LEDGER")
        model_require(len(self.rows) == len(self.owner.resources) == len(saved.entries), "MODEL_RETAINED_ROWS")
        for number, (row, native_row, resource, identity, graph, attempted, closed) in enumerate(saved.entries):
            model_require(self.rows[number] is row and self.owner.resources[number] is native_row and
                type(row) is list and len(row) == 5 and row[0] == "directory" and
                row[1] is resource and row[2] is identity and row[3] is attempted and row[4] is closed and
                type(native_row) is list and len(native_row) == 2 and native_row[0] == "directory" and
                native_row[1] is resource and resource.identity is identity and
                resource.close_calls == int(attempted) and resource.closed is closed,
                "MODEL_ORIGINAL_RETURNED_RESOURCE")
            rig.N._check_history(graph)

    def register(self, name):
        self.structural()
        saved = self._rig.ledgers[self]
        model_require(not saved.finished, "MODEL_OWNER_CLOSED")
        resource = ResourceModel(name)
        row, native_row = ["directory", resource, resource.identity, False, False], ["directory", resource]
        saved.entries += ((row, native_row, resource, resource.identity,
            self._rig.N._history_graph(resource.identity), False, False),)
        self.rows.append(row)
        self.owner.resources.append(native_row)
        self.structural()
        return resource

    def finish(self, *, failure=None):
        """Counter-only known close, or an explicit terminal unknown-close model."""
        self.structural()
        saved = self._rig.ledgers[self]
        model_require(not saved.finished, "MODEL_CLOSE_ONCE")
        entries = []
        for row, native_row, resource, identity, graph, _attempted, _closed in saved.entries:
            row[3] = True
            try:
                resource.close(failure=failure)
            except BaseException as error:
                if error is not failure:
                    raise
            else:
                row[4] = True
            entries.append((row, native_row, resource, identity, graph, True, failure is None))
        saved.entries = tuple(entries)
        saved.closed = self.owner.closed = True
        saved.finished = self.finished = True
        saved.failure = self.failure = self.owner.original = failure
        saved.unknown = self.owner.unknown = failure is not None
        if failure is not None:
            self.errors.append(failure)
        saved.saved_errors = tuple(self.errors)
        self.structural()


class PrimaryOwnerModel(LedgerModel):
    pass


class CustodyOwnerModel:
    """Direct operative-owner contract, with independently retained model rows.

    This is not the actual _CustodyOwner. The earlier roster-wrapper/native-owner
    first/window perturbations now address the same direct first/fence fields;
    both named cases remain, but are not claimed as additional distinct coverage.
    """
    def __init__(self, rig):
        self._rig, self.first, self.fence = rig, rig.first, rig.guard
        self.resources, self.rows, self.errors = [], [], []
        self.closed, self.original, self.unknown = False, None, False
        rig.ledgers[self] = SimpleNamespace(dictionary=self.__dict__, resources=self.resources,
            rows=self.rows, errors=self.errors, entries=(), closed=False, pending=None)

    def _anchor(self):
        return self._rig.ledgers[self]

    def check(self):
        rig, saved = self._rig, self._rig.ledgers[self]
        rig.model_checks += 1
        model_require(self.__dict__ is saved.dictionary and self.first is rig.first and self.fence is rig.guard and
            self.resources is saved.resources and self.rows is saved.rows and self.errors is saved.errors and
            self.errors == [] and self.original is None and self.unknown is False and self.closed is saved.closed,
            "MODEL_ORIGINAL_OWNER")
        model_require(len(self.rows) == len(self.resources) == len(saved.entries), "MODEL_RETAINED_ROWS")
        for number, (row, native_row, resource, identity, graph, attempted, closed) in enumerate(saved.entries):
            model_require(self.rows[number] is row and self.resources[number] is native_row and
                type(row) is list and len(row) == 5 and row[0] == "directory" and
                row[1] is resource and row[2] is identity and row[3] is attempted and row[4] is closed and
                type(native_row) is list and len(native_row) == 2 and native_row[0] == "directory" and
                native_row[1] is resource and resource.identity is identity and
                resource.close_calls == int(attempted) and resource.closed is closed,
                "MODEL_ORIGINAL_RETURNED_RESOURCE")
            rig.N._check_history(graph)
        return saved

    def register(self, name):
        self.check()
        saved = self._rig.ledgers[self]
        model_require(not saved.closed, "MODEL_OWNER_CLOSED")
        resource = ResourceModel(name)
        row, native_row = ["directory", resource, resource.identity, False, False], ["directory", resource]
        saved.entries += ((row, native_row, resource, resource.identity,
            self._rig.N._history_graph(resource.identity), False, False),)
        self.rows.append(row)
        self.resources.append(native_row)
        self.check()
        return resource

    def finish(self):
        self.check()
        saved = self._rig.ledgers[self]
        model_require(not saved.closed, "MODEL_CLOSE_ONCE")
        entries = []
        for row, native_row, resource, identity, graph, _attempted, _closed in saved.entries:
            row[3] = True
            resource.close()
            row[4] = True
            entries.append((row, native_row, resource, identity, graph, True, True))
        saved.entries = tuple(entries)
        saved.closed = self.closed = True
        self.check()


def namespace(rig):
    identity = SimpleNamespace(**selected(IDENTITY_PATH, ("AdmissionError", "require", "parse"), {"json": json}))
    rig.clock_space = selected(CLOCK_PATH,
        ("ClockError", "require", "integer", "ClockIdentity", "Reading", "validate_identity",
         "validate_reading", "elapsed_ns", "checked_now"), {"observe": rig.observe},
        constants=("NS", "UINT64", "INT64", "DARWIN_DOMAIN", "LINUX_DOMAIN", "WINDOWS_DOMAIN", "DOMAINS"))
    rig.clocks = SimpleNamespace(**rig.clock_space)
    rig.clocks.checked_now = rig.checked_now  # Record arguments; delegate to the selected full function.
    wire = SimpleNamespace(**selected(WIRE_PATH,
        ("BudgetError", "require", "clock_value", "encoded", "parse", "_directed_deadline"),
        {"json": json, "math": math, "identity": identity, "_clocks": lambda: rig.clocks},
        constants=("NS", "UINT64", "RECORD_LIMIT")))
    origin = SimpleNamespace(**selected(ORIGIN_PATH,
        ("OriginError", "require", "integer", "encoded", "parse", "clock_value"),
        {"clocks": rig.clocks, "wire": wire}, constants=("NS",)))
    origin.Fence = type("UnusedFenceRecord", (), {})
    gate = SimpleNamespace(**selected(GATE_PATH, ("GateEligibility",)))
    stages = SimpleNamespace(**selected(STAGES_PATH, ("BootstrapMatch",)))
    rig.A = SimpleNamespace(gate=gate, stages=stages)
    native = SimpleNamespace(**selected(B_PATH, ("require", "_RecipientWindow"),
        {"origin": origin, "math": math, "time": SimpleNamespace(monotonic=rig.monotonic)}, constants=("LIMIT",)))
    native.Owner, native.OriginalPhase = NativeOwnerModel, type("UnusedOriginalPhaseRecord", (), {})

    def forbidden_now(*args, **kwargs):
        rig.helper_calls.append("now")
        raise AssertionError("CAP_HELPER_NOW_MUST_NOT_RUN")

    def forbidden_deadline(*args, **kwargs):
        rig.helper_calls.append("deadline")
        raise AssertionError("CAP_HELPER_DEADLINE_MUST_NOT_RUN")

    native._RecipientWindow.now, native._RecipientWindow.deadline = forbidden_now, forbidden_deadline
    graph_bindings = {name: type("Unused" + name, (), {}) for name in
        ("_ReadmissionReturn", "_ReadmissionBinding", "_ReadmissionClaim", "_PreparationBinding",
         "_OriginalPreparation", "_EntryWindowBinding", "_ReadmissionWindow", "SourceReturn",
         "_AuthorityReturn", "_AuthorityState", "_RecipientNativeReturn", "_RecipientValidationReturn",
         "_RecipientState", "_RecipientCryptoOriginals")}
    graph_bindings.update(I=identity, O=origin, native=native, ROOT=ROOT, acquisition=rig.A,
        initial_identity=SimpleNamespace(InitialBootstrapIdentity=type("UnusedBootstrapIdentityRecord", (), {})),
        _RecipientRoster=type("UnusedRecipientRosterRecord", (), {}))
    rig.N = SimpleNamespace(**selected(N_PATH, ("require", "_history_graph", "_check_history"), graph_bindings))
    rig.O, rig.native = origin, native
    return selected(D_PATH,
        ("require", "digest", "local_value", "canonical", "_CustodyChildAnchor", "_CustodyChildClock"),
        {"I": identity, "O": origin, "N": rig.N, "native": native, "A": rig.A,
         "C": SimpleNamespace(boot_digest=rig.boot_digest), "_PrimaryOwner": PrimaryOwnerModel,
         "_CustodyOwner": CustodyOwnerModel,
         "math": math, "re": re, "time": SimpleNamespace(monotonic=rig.monotonic)},
        constants=("_CUSTODY_CHILD_CLOCKS",))


class Rig:
    def __init__(self):
        self.events, self.checked, self.boot_roles, self.helper_calls = [], [], [], []
        self.local_samples, self.raw_samples, self.ledgers = [], [], {}
        self.local, self.raw, self.boot = 100.0, 50 * NS, BOOT
        self.local_hook = self.raw_hook = self.boot_hook = self.cancel_hook = None
        self.model_checks = 0
        self.space = namespace(self)
        self.identity = self.clocks.ClockIdentity("linux-x64", self.clocks.LINUX_DOMAIN, NS)
        self.observed_identity = self.identity
        self.first = self.clocks.Reading(self.identity, self.raw)
        self.original_local = self.local
        self.guard = self.space["_CustodyChildClock"](self.first, self.original_local, BOOT, self.cancelled)

    @property
    def anchor(self):
        return self.space["_CUSTODY_CHILD_CLOCKS"][id(self.guard)]

    def monotonic(self):
        self.events.append("local")
        if self.local_samples:
            self.local = self.local_samples.pop(0)
        if isinstance(self.local, BaseException):
            raise self.local
        if self.local_hook is not None:
            self.local_hook()
        return self.local

    def observe(self):
        self.events.append("raw")
        if self.raw_samples:
            self.raw = self.raw_samples.pop(0)
        if isinstance(self.raw, BaseException):
            raise self.raw
        if self.raw_hook is not None:
            self.raw_hook()
        return self.clocks.Reading(self.observed_identity, self.raw)

    def checked_now(self, expected, *, minimum_ns=0):
        self.checked.append((expected, minimum_ns))
        return self.clock_space["checked_now"](expected, minimum_ns=minimum_ns)

    def boot_digest(self, role):
        self.events.append("boot")
        self.boot_roles.append(role)
        if self.boot_hook is not None:
            self.boot_hook()
        return self.boot

    def cancelled(self):
        self.events.append("cancel")
        if self.cancel_hook is not None:
            self.cancel_hook()

    def metadata(self, *, closed=True, failure=None):
        value = PrimaryOwnerModel(self)
        self.guard.attach_metadata(value)
        value.register("metadata-frame")
        if closed:
            value.finish(failure=failure)
        return value

    def frame(self, kind="gate", *, started=40 * NS, work=100 * NS):
        # These are only the guard's data prerequisites, NOT authenticated host,
        # parent-launch, service/Step or complete custody frame records.
        context = {"observed": {"kind": kind}, "expectedMatch": {"modelExpected": kind},
            "window": {"originalBootDigest": BOOT, "clock": self.O.clock_value(self.identity), "workEndNs": work}}
        start = {"startedNs": started, "workEndNs": min(work, started + 45 * NS)}
        expected_type = self.A.gate.GateEligibility if kind == "gate" else self.A.stages.BootstrapMatch
        expected = expected_type(self.O.encoded(context["expectedMatch"]))
        return (self.O.encoded(context), context, self.O.encoded(start), start,
            expected, b"SYNTHETIC_EVENT\n", {"modelInherited": ["original"]})

    def bound(self, kind="gate"):
        metadata, frame = self.metadata(), self.frame(kind)
        self.guard.bind(*frame)
        return metadata, frame


class ChildClockTests(unittest.TestCase):
    def refuses(self, rig, operation, suffix=None):
        with self.assertRaises(ValueError) as caught:
            operation()
        if suffix is not None:
            self.assertTrue(str(caught.exception).endswith(suffix), str(caught.exception))
        self.assertIs(rig.anchor.failure, caught.exception)
        self.assertFalse(rig.anchor.busy)
        return caught.exception

    def sticky(self, rig, error):
        previous = list(rig.events)
        for operation in (rig.guard.now, lambda: rig.guard.deadline(1),
                lambda: rig.guard.attach_metadata(None), lambda: rig.guard.bind(*((None,) * 7)),
                lambda: rig.guard.attach_operative(None)):
            with self.assertRaises(ValueError) as caught:
                operation()
            self.assertIs(caught.exception, error)
        self.assertEqual(rig.events, previous)

    def test_metadata_cap_uses_exact_original_first_local_without_sampling(self):
        rig = Rig()
        cap = rig.anchor.cap
        self.assertIs(cap.reading, rig.first)
        self.assertIs(cap.clock, rig.identity)
        self.assertEqual((cap.first, cap.metadata_last, cap.last), (50 * NS,) * 3)
        self.assertIs(cap.local_start, rig.original_local)
        self.assertTrue(cap.metadata)
        self.assertIsNone(cap.parent_work)
        self.assertEqual((cap.work, cap.final), (95 * NS, 95 * NS))
        self.assertEqual(cap.local_end, rig.O.wire._directed_deadline(100.0, 45, 95 * NS, 50 * NS))
        self.assertLess(cap.local_end, 145.0)
        self.assertEqual(rig.events, [])

    def test_helper_is_cap_only_and_never_supplies_now_deadline_or_mutable_last(self):
        rig = Rig()
        cap, dictionary = rig.anchor.cap, rig.anchor.cap.__dict__
        saved = dict(dictionary)
        rig.raw_samples = [51 * NS, 52 * NS, 53 * NS, 54 * NS]
        self.assertEqual(rig.guard.now(), 52 * NS)
        self.assertLessEqual(rig.guard.deadline(10), rig.guard.local_end)
        self.assertEqual(rig.guard.last, 54 * NS)
        self.assertIs(cap.__dict__, dictionary)
        self.assertEqual(dictionary, saved)
        self.assertEqual(cap.last, 50 * NS)
        self.assertEqual(rig.helper_calls, [])

    def test_now_retains_checked_raw_local_and_same_original_identity(self):
        rig = Rig()
        rig.raw_samples, rig.local_samples = [60 * NS, 61 * NS], [101.0, 102.0, 103.0]
        self.assertEqual(rig.guard.now(minimum=59 * NS), 61 * NS)
        self.assertEqual(rig.checked, [(rig.identity, 59 * NS), (rig.identity, 60 * NS)])
        self.assertTrue(all(identity is rig.identity for identity, _ in rig.checked))
        self.assertEqual((rig.anchor.last, rig.anchor.local_last), (61 * NS, 103.0))
        self.assertEqual(rig.events, ["local", "raw", "boot", "cancel", "local", "raw", "boot", "local"])
        self.assertEqual(rig.boot_roles, ["linux-x64", "linux-x64"])

    def test_deadline_samples_local_before_raw_and_uses_directed_shortened_limit(self):
        rig = Rig()
        rig.local_samples, rig.raw_samples = [101.0, 102.0, 103.0, 104.0], [60 * NS, 61 * NS]
        result = rig.guard.deadline(10, limit=70 * NS)
        self.assertEqual(result, rig.O.wire._directed_deadline(101.0, 10, 70 * NS, 61 * NS))
        self.assertLess(result, 110.0)
        self.assertEqual(rig.events[:3], ["local", "local", "raw"])
        self.assertEqual((rig.anchor.last, rig.anchor.local_last), (61 * NS, 104.0))

    def test_deadline_is_clipped_to_original_local_cap(self):
        rig = Rig()
        rig.local = 144.0
        result = rig.guard.deadline(210)
        self.assertEqual(result, rig.anchor.cap.local_end)
        self.assertLess(result, 145.0)
        self.assertEqual(rig.helper_calls, [])

    def test_raw_rollback_keeps_previous_frontier_and_first_failure(self):
        rig = Rig()
        rig.raw_samples = [60 * NS, 61 * NS]
        rig.guard.now()
        rig.raw = 60 * NS
        error = self.refuses(rig, rig.guard.now, "JOB_CLOCK_BACKWARDS")
        self.assertEqual(rig.anchor.last, 61 * NS)
        self.sticky(rig, error)

    def test_local_rollback_fails_before_another_raw_and_keeps_frontier(self):
        rig = Rig()
        rig.local_samples = [101.0, 102.0, 103.0]
        rig.guard.now()
        count = len(rig.checked)
        rig.local = 102.0
        error = self.refuses(rig, rig.guard.now, "CHILD_CLOCK_LOCAL_BACKWARDS")
        self.assertEqual((rig.anchor.local_last, len(rig.checked)), (103.0, count))
        self.sticky(rig, error)

    def test_first_valid_raw_is_retained_before_falsey_cancellation_failure(self):
        rig = Rig()
        failure = FalseyRefusal("MODEL_CANCELLED")
        rig.raw, rig.local = 60 * NS, 101.0

        def cancel():
            raise failure

        rig.cancel_hook = cancel
        self.assertIs(self.refuses(rig, rig.guard.now), failure)
        self.assertEqual((rig.anchor.last, rig.anchor.local_last), (60 * NS, 101.0))
        self.assertEqual(len(rig.checked), 1)
        self.sticky(rig, failure)

    def test_second_valid_raw_is_retained_before_boot_or_graph_failure(self):
        for change in ("boot", "cap"):
            with self.subTest(change=change):
                rig = Rig()
                rig.raw_samples = [60 * NS, 61 * NS]

                def mutate():
                    if len(rig.checked) == 2:
                        if change == "boot":
                            rig.boot = "b" * 64
                        else:
                            object.__setattr__(rig.anchor.cap, "last", 0)

                rig.raw_hook = mutate
                error = self.refuses(rig, rig.guard.now)
                self.assertEqual(rig.anchor.last, 61 * NS)
                self.sticky(rig, error)

    def test_valid_local_is_retained_before_expiry_or_graph_failure(self):
        for change in ("expiry", "graph"):
            with self.subTest(change=change):
                rig = Rig()
                rig.local = rig.anchor.cap.local_end if change == "expiry" else 101.0
                if change == "graph":
                    rig.local_hook = lambda: object.__setattr__(rig.anchor.cap, "work", 999 * NS)
                error = self.refuses(rig, rig.guard.now)
                self.assertEqual(rig.anchor.local_last, rig.local)
                self.assertEqual(rig.checked, [])
                self.sticky(rig, error)

    def test_constructor_rejects_invalid_first_local_boot_and_callback(self):
        cases = ("reading", "negative", "nonfinite", "boolean", "boot", "callback")
        for case in cases:
            with self.subTest(case=case):
                rig = Rig()
                first, local, boot, cancel = rig.first, rig.original_local, BOOT, rig.cancelled
                if case == "reading":
                    first = SimpleNamespace(clock=rig.identity, nanoseconds=50 * NS)
                elif case == "negative":
                    local = -1.0
                elif case == "nonfinite":
                    local = math.nan
                elif case == "boolean":
                    local = True
                elif case == "boot":
                    boot = "not-a-boot-digest"
                else:
                    cancel = None
                with self.assertRaises(ValueError):
                    rig.space["_CustodyChildClock"](first, local, boot, cancel)
                self.assertEqual(rig.events, [])
                self.assertEqual(len(rig.space["_CUSTODY_CHILD_CLOCKS"]), 1)

    def test_changed_observed_clock_identity_is_not_a_new_epoch(self):
        rig = Rig()
        rig.observed_identity = rig.clocks.ClockIdentity("windows-x64", rig.clocks.WINDOWS_DOMAIN, 10_000_000)
        rig.raw = 60 * NS
        error = self.refuses(rig, rig.guard.now, "JOB_CLOCK_IDENTITY_CHANGED")
        self.assertEqual(rig.anchor.last, 50 * NS)
        self.sticky(rig, error)

    def test_invalid_live_samples_cannot_replace_retained_frontiers(self):
        for case in ("local-nan", "local-bool", "local-negative", "raw-nan", "raw-bool", "raw-overflow"):
            with self.subTest(case=case):
                rig = Rig()
                rig.local = 101.0
                if case.startswith("local-"):
                    rig.local = {"local-nan": math.nan, "local-bool": True, "local-negative": -1.0}[case]
                else:
                    rig.raw = {"raw-nan": math.nan, "raw-bool": True,
                        "raw-overflow": rig.clocks.UINT64 + 1}[case]
                error = self.refuses(rig, rig.guard.now)
                self.assertEqual(rig.anchor.last, 50 * NS)
                self.assertEqual(rig.anchor.local_last, 100.0 if case.startswith("local-") else 101.0)
                self.sticky(rig, error)

    def test_boot_change_in_cancellation_is_rechecked_after_second_raw(self):
        rig = Rig()
        rig.raw_samples = [60 * NS, 61 * NS]
        rig.cancel_hook = lambda: setattr(rig, "boot", "b" * 64)
        error = self.refuses(rig, rig.guard.now, "CHILD_CLOCK_BOOT_CHANGED")
        self.assertEqual(rig.anchor.last, 61 * NS)
        self.assertEqual(rig.boot_roles, ["linux-x64", "linux-x64"])
        self.assertIs(rig.observed_identity, rig.identity)
        self.sticky(rig, error)

    def test_second_raw_supplier_boot_change_is_rejected_without_identity_change(self):
        rig = Rig()

        def changed_boot():
            if len(rig.checked) == 2:
                rig.boot = "b" * 64

        rig.raw_hook = changed_boot
        self.refuses(rig, rig.guard.now, "CHILD_CLOCK_BOOT_CHANGED")
        self.assertEqual(len(rig.checked), 2)
        self.assertIs(rig.observed_identity, rig.identity)

    def test_final_and_deadline_also_check_boot_and_cancellation(self):
        for operation in ("final-now", "deadline", "final-deadline"):
            with self.subTest(operation=operation):
                rig = Rig()
                rig.cancel_hook = lambda: setattr(rig, "boot", "b" * 64)
                action = (lambda: rig.guard.now(final=True)) if operation == "final-now" else (
                    lambda: rig.guard.deadline(1, final=operation == "final-deadline"))
                self.refuses(rig, action, "CHILD_CLOCK_BOOT_CHANGED")
                self.assertEqual(rig.events.count("cancel"), 1)
                self.assertEqual(len(rig.boot_roles), 2)

    def test_swallowed_callback_reentry_preserves_original_refusal(self):
        for operation in ("now", "deadline"):
            with self.subTest(operation=operation):
                rig, caught = Rig(), []

                def reenter():
                    try:
                        rig.guard.now() if operation == "now" else rig.guard.deadline(1)
                    except ValueError as error:
                        caught.append(error)

                rig.cancel_hook = reenter
                error = self.refuses(rig, rig.guard.now, "CHILD_CLOCK_REENTRY")
                self.assertEqual(len(caught), 1)
                self.assertIs(error, caught[0])
                self.assertEqual(len(rig.checked), 1)
                self.sticky(rig, error)

    def test_falsey_clock_failure_is_sticky_across_all_mutating_entrypoints(self):
        rig = Rig()
        failure = FalseyRefusal("MODEL_RAW_UNAVAILABLE")
        rig.raw_samples = [60 * NS, failure]
        self.assertIs(self.refuses(rig, rig.guard.now), failure)
        self.assertEqual(rig.anchor.last, 60 * NS)
        self.assertFalse(bool(failure))
        self.sticky(rig, failure)

    def test_first_clock_cap_and_binding_mutations_are_rejected_before_sampling(self):
        for case in ("reading", "clock", "reading-clock", "reading-dict", "cap-reading", "cap-last", "cap-dict", "binding"):
            with self.subTest(case=case):
                rig = Rig()
                if case == "reading":
                    object.__setattr__(rig.first, "nanoseconds", 51 * NS)
                elif case == "clock":
                    object.__setattr__(rig.identity, "ticks_per_second", 2 * NS)
                elif case == "reading-clock":
                    object.__setattr__(rig.first, "clock",
                        rig.clocks.ClockIdentity("linux-x64", rig.clocks.LINUX_DOMAIN, NS))
                elif case == "reading-dict":
                    object.__setattr__(rig.first, "__dict__", dict(rig.first.__dict__))
                elif case == "cap-reading":
                    object.__setattr__(rig.anchor.cap, "reading", rig.clocks.Reading(rig.identity, 50 * NS))
                elif case == "cap-last":
                    object.__setattr__(rig.anchor.cap, "last", 51 * NS)
                elif case == "cap-dict":
                    object.__setattr__(rig.anchor.cap, "__dict__", dict(rig.anchor.cap.__dict__))
                else:
                    rig.guard._binding = tuple(list(rig.guard._binding))
                error = self.refuses(rig, rig.guard.now)
                self.assertEqual(rig.events, [])
                self.sticky(rig, error)

    def test_invalid_operation_bounds_refuse_without_any_helper_observation(self):
        cases = ("final", "minimum", "limit", "zero", "negative", "boolean", "nan", "infinite", "renewal")
        for case in cases:
            with self.subTest(case=case):
                rig = Rig()
                if case == "final":
                    action = lambda: rig.guard.now(final=1)
                elif case == "minimum":
                    action = lambda: rig.guard.now(minimum=True)
                elif case == "limit":
                    action = lambda: rig.guard.now(limit=-1)
                else:
                    value = {"zero": 0, "negative": -1, "boolean": True, "nan": math.nan,
                        "infinite": math.inf, "renewal": 211}[case]
                    action = lambda: rig.guard.deadline(value)
                error = self.refuses(rig, action)
                self.assertEqual(rig.events, [])
                self.assertEqual(rig.helper_calls, [])
                self.sticky(rig, error)

    def test_limit_and_cap_equality_expire_without_losing_observed_raw(self):
        for final in (False, True):
            for limit in (70 * NS, None):
                with self.subTest(final=final, limit=limit):
                    rig = Rig()
                    rig.raw = 95 * NS if limit is None else limit
                    error = self.refuses(rig, lambda: rig.guard.now(final=final, limit=limit),
                        "CHILD_CLOCK_RAW_EXPIRED_OR_CHANGED")
                    self.assertEqual(rig.anchor.last, rig.raw)
                    self.sticky(rig, error)

    def test_metadata_attach_requires_original_same_first_fence_and_empty_rows(self):
        for case in ("type", "first", "fence", "rows", "finished", "twice"):
            with self.subTest(case=case):
                rig = Rig()
                owner = PrimaryOwnerModel(rig)
                if case == "type":
                    owner = CustodyOwnerModel(rig)
                elif case == "first":
                    owner.owner.first = rig.clocks.Reading(rig.identity, 50 * NS)
                elif case == "fence":
                    owner.owner.fence = object()
                elif case == "rows":
                    owner.register("too-early")
                elif case == "finished":
                    owner.finish()
                else:
                    rig.guard.attach_metadata(owner)
                self.refuses(rig, lambda: rig.guard.attach_metadata(owner), "CHILD_METADATA_ORIGINAL_OWNER")
                self.assertEqual(rig.events, [])

    def test_bind_requires_known_closed_metadata_including_falsey_failure(self):
        for outcome in ("missing", "open", "unknown"):
            with self.subTest(outcome=outcome):
                rig = Rig()
                metadata = None
                if outcome != "missing":
                    metadata = rig.metadata(closed=outcome == "unknown",
                        failure=FalseyRefusal("MODEL_CLOSE_UNKNOWN") if outcome == "unknown" else None)
                error = self.refuses(rig, lambda: rig.guard.bind(*rig.frame()))
                self.assertEqual(rig.anchor.phase, "METADATA" if outcome == "missing" else "BINDING")
                self.assertTrue(rig.anchor.cap.metadata)
                self.assertEqual(rig.checked, [])
                if metadata is not None and outcome == "unknown":
                    self.assertFalse(bool(metadata.failure))
                    self.assertTrue(metadata.owner.unknown)
                    self.assertEqual(metadata.rows[0][1].close_calls, 1)
                self.sticky(rig, error)

    def test_gate_and_worker_bind_keep_actual_first_local_and_metadata_frontier(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind):
                rig = Rig()
                metadata = rig.metadata()
                oldcap, olddict = rig.anchor.cap, rig.anchor.cap.__dict__
                rig.raw_samples = [60 * NS, 61 * NS]
                rig.guard.now()
                frame = rig.frame(kind)
                rig.raw_samples = [62 * NS, 63 * NS]
                rig.guard.bind(*frame)
                cap = rig.anchor.cap
                self.assertEqual(rig.anchor.phase, "OPERATIVE")
                self.assertIs(cap.reading, rig.first)
                self.assertIs(cap.local_start, rig.original_local)
                self.assertEqual((cap.metadata_last, cap.last, rig.guard.last), (61 * NS, 61 * NS, 63 * NS))
                self.assertEqual((cap.work, cap.final, cap.parent_work), (85 * NS,) * 3)
                self.assertLess(cap.local_end, 135.0)
                self.assertFalse(cap.metadata)
                self.assertIs(rig.anchor.frame[-3], oldcap)
                self.assertIs(rig.anchor.frame[-2], olddict)
                self.assertEqual(oldcap.last, 50 * NS)
                self.assertIs(rig.anchor.metadata, metadata)
                self.assertEqual(metadata.rows[0][1].close_calls, 1)
                self.assertEqual(rig.helper_calls, [])

    def test_bind_is_single_use_and_does_not_renew_operative_cap(self):
        rig = Rig()
        _metadata, frame = rig.bound()
        cap = rig.anchor.cap
        error = self.refuses(rig, lambda: rig.guard.bind(*frame), "CHILD_CLOCK_BIND_ONCE")
        self.assertIs(rig.anchor.cap, cap)
        self.assertEqual((cap.first, cap.work), (50 * NS, 85 * NS))
        self.sticky(rig, error)

    def test_spent_parent45_cannot_be_replaced_with_fresh_child45_or210(self):
        rig = Rig()
        rig.metadata()
        oldcap = rig.anchor.cap
        rig.raw = 85 * NS
        rig.guard.now()  # Still inside metadata95, but the original parent45 is spent.
        frame = rig.frame()
        error = self.refuses(rig, lambda: rig.guard.bind(*frame), "CHILD_FRAME_ORIGINAL_CAP")
        self.assertEqual(rig.anchor.phase, "BINDING")
        self.assertIs(rig.anchor.cap, oldcap)
        self.assertEqual(rig.anchor.last, 85 * NS)
        self.sticky(rig, error)

    def test_bind_failure_consumes_transition_and_preserves_original_frame_refusal(self):
        rig = Rig()
        rig.metadata()
        frame = list(rig.frame())
        frame[0] = b" " + frame[0]
        error = self.refuses(rig, lambda: rig.guard.bind(*frame), "CANONICAL_RECORD")
        self.assertEqual(rig.anchor.phase, "BINDING")
        self.assertEqual(rig.checked, [])
        self.sticky(rig, error)

    def test_expiry_during_bind_consumes_transition_without_operative_ownership(self):
        for clock in ("raw", "local"):
            with self.subTest(clock=clock):
                rig = Rig()
                rig.metadata()
                if clock == "raw":
                    rig.raw = 85 * NS
                else:
                    rig.local = 138.0  # Metadata145 is unspent; operative135 is already spent.
                error = self.refuses(rig, lambda: rig.guard.bind(*rig.frame()))
                self.assertEqual(rig.anchor.phase, "OPERATIVE")
                self.assertIsNone(rig.anchor.operative)
                self.assertEqual((rig.anchor.cap.first, rig.anchor.cap.local_start, rig.anchor.cap.work),
                    (50 * NS, 100.0, 85 * NS))
                self.assertEqual(rig.anchor.last, 85 * NS if clock == "raw" else 50 * NS)
                self.assertEqual(rig.anchor.local_last, 138.0 if clock == "local" else 100.0)
                self.sticky(rig, error)

    def test_bind_checks_original_frame_bytes_expected_type_clock_boot_and_parent_cap(self):
        cases = ("raw-type", "context", "start", "expected-type", "expected-record", "event", "inherited",
                 "boot", "clock", "future-start", "renewed-work")
        for case in cases:
            with self.subTest(case=case):
                rig = Rig()
                rig.metadata()
                frame = list(rig.frame())
                if case == "raw-type":
                    frame[0] = bytearray(frame[0])
                elif case == "context":
                    frame[1]["extra"] = True
                elif case == "start":
                    frame[3]["extra"] = True
                elif case == "expected-type":
                    frame[4] = rig.A.stages.BootstrapMatch(frame[4].record)
                elif case == "expected-record":
                    object.__setattr__(frame[4], "record", b"{}\n")
                elif case == "event":
                    frame[5] = bytearray(frame[5])
                elif case == "inherited":
                    frame[6] = []
                else:
                    if case == "boot":
                        frame[1]["window"]["originalBootDigest"] = "b" * 64
                    elif case == "clock":
                        frame[1]["window"]["clock"]["ticksPerSecond"] = 2 * NS
                    elif case == "future-start":
                        frame[3]["startedNs"] = 51 * NS
                        frame[3]["workEndNs"] = 96 * NS
                    else:
                        frame[3]["workEndNs"] = 95 * NS
                    frame[0], frame[2] = rig.O.encoded(frame[1]), rig.O.encoded(frame[3])
                error = self.refuses(rig, lambda: rig.guard.bind(*frame))
                self.assertEqual(rig.anchor.phase, "BINDING")
                self.assertEqual(rig.checked, [])
                self.sticky(rig, error)

    def test_closed_metadata_owner_and_retired_cap_graphs_remain_pinned(self):
        for case in ("owner-extra-field", "old-cap", "old-cap-dict"):
            with self.subTest(case=case):
                rig = Rig()
                metadata, _frame = rig.bound()
                oldcap = rig.anchor.frame[-3]
                if case == "owner-extra-field":
                    metadata.owner.extra = "post-close-change"
                    metadata.structural()  # Model permits extra fields; the real guard graph must not.
                elif case == "old-cap":
                    object.__setattr__(oldcap, "work", 999 * NS)
                else:
                    object.__setattr__(oldcap, "__dict__", dict(oldcap.__dict__))
                rig.events.clear()
                error = self.refuses(rig, rig.guard.now)
                self.assertEqual(rig.events, [])
                self.sticky(rig, error)

    def test_original_context_start_expected_and_inherited_graphs_cannot_change(self):
        for kind in ("gate", "worker"):
            for case in ("context", "nested-frame", "start", "expected", "expected-dict", "inherited"):
                with self.subTest(kind=kind, case=case):
                    rig = Rig()
                    _metadata, frame = rig.bound(kind)
                    if case == "context":
                        frame[1]["observed"] = dict(frame[1]["observed"])
                    elif case == "nested-frame":
                        frame[1]["window"]["workEndNs"] += NS
                    elif case == "start":
                        frame[3]["workEndNs"] += NS
                    elif case == "expected":
                        object.__setattr__(frame[4], "record", b"{}\n")
                    elif case == "expected-dict":
                        object.__setattr__(frame[4], "__dict__", dict(frame[4].__dict__))
                    else:
                        frame[6]["modelInherited"].append("replacement")
                    rig.events.clear()
                    error = self.refuses(rig, rig.guard.now)
                    self.assertEqual(rig.events, [])
                    self.sticky(rig, error)

    def test_operative_attach_requires_original_empty_roster_same_first_and_guard(self):
        for case in ("phase", "type", "first", "window", "owner-first", "owner-fence", "closed", "rows", "twice"):
            with self.subTest(case=case):
                rig = Rig()
                if case != "phase":
                    rig.bound()
                roster = CustodyOwnerModel(rig)
                if case == "type":
                    roster = PrimaryOwnerModel(rig)
                elif case == "first":
                    roster.first = rig.clocks.Reading(rig.identity, 50 * NS)
                elif case == "window":
                    roster.fence = object()
                elif case == "owner-first":
                    roster.first = rig.clocks.Reading(rig.identity, 50 * NS)
                elif case == "owner-fence":
                    roster.fence = object()
                elif case == "closed":
                    roster.finish()
                elif case == "rows":
                    roster.register("too-early")
                elif case == "twice":
                    rig.guard.attach_operative(roster)
                self.refuses(rig, lambda: rig.guard.attach_operative(roster), "CHILD_OPERATIVE_ORIGINAL_OWNER")

    def test_operative_returned_row_erasure_is_detected_before_any_clock_callback(self):
        rig = Rig()
        rig.bound()
        roster = CustodyOwnerModel(rig)
        rig.guard.attach_operative(roster)
        resource = roster.register("operative-return")
        rig.guard.now()  # Valid modeled append remains usable; not an empty-roster-only probe.
        roster.rows.clear()
        roster.resources.clear()
        rig.events.clear()
        error = self.refuses(rig, rig.guard.now, "MODEL_RETAINED_ROWS")
        self.assertEqual(rig.events, [])
        self.assertEqual(resource.close_calls, 0)
        self.assertIs(rig.ledgers[roster].entries[0][2], resource)
        self.sticky(rig, error)

    def test_operative_roster_mutation_from_cancel_preserves_raw_and_first_error(self):
        rig = Rig()
        rig.bound()
        roster = CustodyOwnerModel(rig)
        rig.guard.attach_operative(roster)
        resource = roster.register("operative-return")
        rig.raw = 60 * NS
        rig.cancel_hook = lambda: resource.identity.update(modelResource="changed")
        error = self.refuses(rig, rig.guard.now, "RECIPIENT_HISTORY_CHANGED")
        self.assertEqual(rig.anchor.last, 60 * NS)
        self.sticky(rig, error)

    def test_closed_metadata_rows_cannot_be_erased_after_bind(self):
        rig = Rig()
        metadata, _frame = rig.bound()
        resource = metadata.rows[0][1]
        metadata.rows.clear()
        metadata.owner.resources.clear()
        rig.events.clear()
        error = self.refuses(rig, rig.guard.now, "MODEL_RETAINED_ROWS")
        self.assertEqual(rig.events, [])
        self.assertEqual(resource.close_calls, 1)
        self.sticky(rig, error)

    def test_shortened_parent_raw_and_original_local_caps_cannot_be_renewed(self):
        for clock in ("raw", "local"):
            with self.subTest(clock=clock):
                rig = Rig()
                rig.bound()
                self.assertEqual(rig.guard.work, 85 * NS)
                self.assertLess(rig.guard.local_end, 135.0)
                if clock == "raw":
                    rig.raw = 85 * NS
                else:
                    rig.local = rig.guard.local_end
                error = self.refuses(rig, lambda: rig.guard.deadline(210, final=True))
                self.assertEqual(rig.anchor.cap.first, 50 * NS)
                self.assertEqual(rig.anchor.cap.local_start, 100.0)
                self.assertEqual(rig.helper_calls, [])
                self.sticky(rig, error)


if __name__ == "__main__":
    unittest.main()
