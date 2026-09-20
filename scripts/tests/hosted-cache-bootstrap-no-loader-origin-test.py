#!/usr/bin/env python3
"""AST/memory controls of original collection publication and no-loader binding.

Run the actual new registry/publication/lookup/typed graph/prefix bodies and the
exact selected collection return tail. Earlier collection work, final check,
producer/predecessor/host/query/leaf outcomes and scalar/encoding suppliers are
explicit models. The modeled final check replaces the private frame, as the
actual check's roster bookkeeping does. No old fixture/suite is imported.

Closed lifecycle/file/query methods and original clocks are poisoned or absent;
not every inherited method/property is replaced. No no-loader leaf, full
controller import, producer, file collection, filesystem/native,
provider, Gradle or hosted admission is exercised. An outer bounded observer
must supply the separately recorded source/resource/execution envelope.
"""
from __future__ import annotations

import ast
from collections import namedtuple
import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import signal
import sys
import threading
from types import SimpleNamespace as Box
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
NS = 1_000_000_000


class Refusal(ValueError):
    pass


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class UnannotatableFailure(FalseyFailure):
    def __setattr__(self, name, value):
        raise RuntimeError("MODELED_ANNOTATION_FAILURE")


def require(value, reason):
    if not value:
        raise Refusal(reason)


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value < 2**64, "MODEL_INTEGER")
    return value


def local(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "MODEL_LOCAL")
    return float(value)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def poison(*_args, **_kwargs):
    raise AssertionError("NO_CLOSED_METHOD_OR_LIVE_SUPPLIER")


def assignment_names(node):
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return set().union(*(assignment_names(item) for item in node.elts))
    return set()


CLASSES = {"NewEntryTransition", "Owner", "_CollectionPhaseOwner", "_CollectionPhaseWindow", "_CollectionPhaseParent",
    "CollectionPrefix", "ConfigurationPrefix", "_CollectionOrigin", "_StagingClosedGraph", "_CollectionReturnGraph",
    "_NoLoaderOrigin"}
FUNCTIONS = {"directory_identity", "_collection_phase_controls", "_collection_phase_closed_return", "_collection_phase_query_identity",
    "_collection_phase_query_checked", "_check_collection_return_graph", "_no_loader_origin_controls",
    "_checked_no_loader_origin", "_begin_no_loader_after_entry"}
RECORDS = {"_StagingFrame", "_StagingLimits", "_CustodyRequestPin", "_StagingSequenceFrame", "_ProducerFrame",
    "_ProducerPredecessor", "_ProducerLimits", "_ProducerNative", "_ProducerPhase", "_ProducerResource", "_ProducerFile",
    "_ProducerCapture", "_CollectionOriginFrame", "_CollectionPhaseFrame", "_CollectionPhaseLimits", "_CollectionPhaseStep",
    "_CollectionPhaseResource", "_CollectionPhaseFile", "_CollectionPhaseQueryOrigin", "_CollectionPhaseQueryBefore",
    "_CollectionPhaseResultPin", "_NoLoaderOriginFrame"}


def selected():
    path = SCRIPTS / "run-hosted-cache-bootstrap.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    nodes, found, tail = [], set(), None
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in CLASSES | FUNCTIONS:
            nodes.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            names = set().union(*(assignment_names(target) for target in node.targets))
            if names & RECORDS:
                nodes.append(node)
                found.update(names & RECORDS)
        if isinstance(node, ast.FunctionDef) and node.name == "_run_collection_phase":
            block = node.body[-1]
            require(isinstance(block, ast.Try), "RETURN_TAIL_SHAPE")
            start = next(index for index, item in enumerate(block.body) if isinstance(item, ast.Assign) and
                         any(assignment_names(target) == {"result"} for target in item.targets))
            tail = block.body[start:]
    require(found == CLASSES | FUNCTIONS | RECORDS and tail is not None, "EXTRACTION_ROSTER_CHANGED")
    # Execute these ORIGINAL statements, not a rewritten successful tail. The
    # earlier body/finalization and last parent.check are modeled, not replayed.
    tail_function = ast.parse("def selected_return_tail(parent, raw, frame, checked):\n    pass\n").body[0]
    tail_function.body = tail
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    return compile(ast.fix_missing_locations(ast.Module(body=[future, *nodes, tail_function], type_ignores=[])), str(path), "exec")


def leaf_records():
    path = SCRIPTS / "hosted_cache_bootstrap_collect_files.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    names = {"FileOriginals", "FileCollectionEvidence", "_capture"}
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    require({node.name for node in nodes} == names, "LEAF_RECORD_ROSTER")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    return compile(ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[])), str(path), "exec")


CODE, LEAF = selected(), leaf_records()


@dataclass(frozen=True)
class Clock:
    role: str = "linux-x64"
    domain: str = "MODEL_NOT_OBSERVED"
    frequency: int = NS


@dataclass(frozen=True)
class Reading:
    clock: object
    nanoseconds: int


@dataclass(frozen=True)
class Admission:
    record: bytes = b"MODEL_NOT_ADMITTED\n"


class Directory:
    def __init__(self, path, identity):
        self.path, self.identity = Path(path), identity

    open_file = open_directory = verify = close = poison


class Query:
    _finalize = close = run = check = native_host_matches_actions = retain_admission = poison


class Model:
    """Supplied CLOSED data plus fixed operation models, never runtime evidence."""
    def __init__(self):
        self.calls, self.events, self.parents = 0, [], []
        self.before_publish = self.after_publish = self.collect_error = None
        self.no_publication, self.return_override = False, None
        self.root = Path("/MODEL_NOT_A_REAL_CHECKOUT")
        n = {"__name__": __name__, "dataclass": dataclass, "field": field, "namedtuple": namedtuple,
            "require": require, "math": math, "re": re, "signal": signal, "threading": threading, "Path": Path,
            "time": Box(monotonic=poison, sleep=poison), "QUARANTINE": [], "LIMIT": 4 * 1024 * 1024}
        self.n = n
        unused = "_EntryAttempt ClosedEntryTransition OriginalEntry OriginalPhase _StagingFileOwner _NewEntryWindow _RecipientParent _InitializerParent _RecipientParentWindow _InitializerWindow _RecipientParentBindings _RecipientResource _ParentControl _RecipientPredecessorGraph _InitializerPredecessor _InitializationInputs InitializationPrefix _StagingPhaseParent _StagingWindow _StagingPhaseReturn StagingPrefix ConfigurationCustodyPrefix _StagingSequence _ProducerParent _ProducerWindow _ProducerOwner".split()
        n.update({name: type(name, (), {}) for name in unused})
        n["origin"] = Box(OriginError=Refusal, NS=NS, integer=integer, encoded=encoded, digest=digest, parse=json.loads,
            clock_value=lambda clock: {"role": clock.role, "domain": clock.domain, "frequency": clock.frequency},
            Fence=type("UnusedFence", (), {}), clocks=Box(ClockIdentity=Clock, Reading=Reading, UINT64=2**64 - 1,
                checked_now=poison, observe=poison, validate_reading=poison))
        n["I"] = Box(Admission=Admission)
        n["staging"] = Box(_local=local, _clock=lambda clock: (clock.role, clock.domain, clock.frequency),
            Originals=type("UnusedOriginals", (), {}), PhaseStart=type("UnusedStart", (), {}),
            LeafEvidence=type("UnusedLeaf", (), {}))
        n["initialization"] = Box(InstalledToolchains=type("UnusedInstalled", (), {}))
        n["custody"] = Box(StagedEvidence=type("UnusedStaged", (), {}), ReservationEvidence=type("UnusedReservation", (), {}))
        n["diagnostics"] = Box(_QUARANTINE=[])
        n["query"] = Box(NativeGitQueries=Query, QUARANTINE=[])
        leaf = {"__name__": __name__, "dataclass": dataclass, "field": field, "require": require,
            "inventory": Box(_bytes=lambda raw: require(type(raw) is bytes and 0 < len(raw) <= 4194304, "MODEL_BYTES")),
            "files": Box(_identity=lambda value: type(value) is list and len(value) == 2 and
                         all(type(item) is int and item > 0 for item in value))}
        exec(LEAF, leaf)
        n["collect_files"] = Box(**{name: leaf[name] for name in ("FileOriginals", "FileCollectionEvidence", "_capture")},
            _Inputs=poison, inventory=Box(describe_inventory=poison), collect_inventory=poison)
        n["_begin_collection_after_entry"] = poison
        n["_checked_collection_origin"] = self.checked_bound
        n["_collection_origin_roots"] = lambda: None
        n["collect_after_entry"] = self.collect
        exec(CODE, n)
        aliases = ("_claim_collection_phase", "_collection_phase_frame", "_update_collection_phase", "_invoke_collection_phase_begin",
            "_collection_phase_roots", "_collection_phase_owner_frame", "_collection_phase_window_frame", "_invoke_collection_phase_leaf",
            "_publish_collection_phase", "_collection_phase_original_call", "_collection_phase_original_result")
        n.update(zip(aliases, n["_collection_phase_controls"]()))
        aliases = ("_claim_no_loader_origin", "_no_loader_origin_frame", "_update_no_loader_origin", "_invoke_no_loader_collection",
            "_no_loader_origin_roots")
        n.update(zip(aliases, n["_no_loader_origin_controls"]()))
        for kind in (n["_CollectionPhaseOwner"], n["_CollectionPhaseWindow"], n["_CollectionPhaseParent"]):
            for name, value in list(vars(kind).items()):
                if callable(value) and name not in ("__init__", "__repr__", "__eq__", "__hash__"):
                    setattr(kind, name, poison)
        self.transition = n["NewEntryTransition"](b"MODEL_NOT_ENTRY", Box(admitted=Admission()), 40 * NS, 50 * NS, 60 * NS)

    def checked_bound(self, binding):
        require(any(binding is parent._model_binding for parent in self.parents), "MODEL_ORIGINAL_BINDING")
        return next(parent._model_bound for parent in self.parents if parent._model_binding is binding)

    def frame(self, parent=None):
        return self.n["_collection_phase_frame"](parent or self.parents[-1])

    def change(self, parent=None, **values):
        return self.n["_update_collection_phase"](parent or self.parents[-1], **values)

    def prepare(self, transition=None):
        n = self.n
        parent = n["_claim_collection_phase"](self.transition if transition is None else transition)
        self.parents.append(parent)
        clock, reading = Clock(), Reading(Clock(), 100 * NS)
        window = n["_CollectionPhaseWindow"](parent)
        owner = object.__new__(n["_CollectionPhaseOwner"])
        phase = Directory(self.root / "phase", (1, 20))
        row = {"label": "directory", "owner": phase, "attempted": True, "closed": True}
        owner.__dict__.update(resources=[row], errors=[], admissions=[Admission()], local_end=295.0, cancelled=poison,
            first=reading, fence=window, work_limit=None, final_limit=None, early_last=100 * NS,
            closed=True, original=None, unknown=False)
        leaf = n["collect_files"].FileCollectionEvidence(b"MODEL_COPIED", b"MODEL_INVENTORY", 140.0, 145.0)
        originals = n["collect_files"].FileOriginals(b"MODEL_REQUEST", b"MODEL_ADMITTED", b"MODEL_CANONICAL",
            b"MODEL_START", b"MODEL_RECEIPT", b"MODEL_MANIFEST", 0, (1, 50), (1, 51), b"MODEL_METADATA_BINDINGS")
        supplier = Query()
        supplier.root, supplier.path = self.root, phase.path / "admission"
        supplier.private = Directory(supplier.path, (1, 30))
        supplier.home = Directory(supplier.path / "query-home", (1, 31))
        supplier.resources = [{"label": name, "owner": value, "closeAttempted": True, "closed": True} for name, value in
            (("private-root", supplier.private), ("query-home", supplier.home), ("nonrequired-original", object()),
             ("session-result.json", object()))]
        supplier.records, supplier.readbacks = [{"MODEL": ["ORIGINAL_QUERY"]}], [{"MODEL": ["ORIGINAL_READBACK"]}]
        supplier.closed, supplier.unknown, supplier.failed, supplier.active = True, False, False, False
        supplier.first_error = supplier.cancellation = None
        supplier.errors, supplier._owner_deadlines = [], (130.0, 150.0)
        query_roots = tuple((directory, type(directory), directory.path, directory.identity)
                            for directory in (supplier.private, supplier.home))
        qgraph = n["_StagingClosedGraph"].capture(supplier.__dict__)
        qgraph = n["_StagingClosedGraph"](qgraph.nodes, query_roots)
        old_data = {"MODEL_CLOSED_PREDECESSOR": ["ORIGINAL_WITNESS"]}
        oldgraph = n["_StagingClosedGraph"].capture(old_data)
        oldgraph = n["_StagingClosedGraph"](oldgraph.nodes, ((phase, type(phase), phase.path, phase.identity),))
        predecessor = n["_ProducerPredecessor"](None, None, None, (), oldgraph)
        producer_frame = n["_ProducerFrame"](predecessor=predecessor)
        produced = n["ConfigurationPrefix"](b"MODEL_PRODUCER_RETURN", b"r", b"s", b"p", b"o", 50 * NS, 50.0)
        binding = n["_CollectionOrigin"](parent.transition, state="BOUND", producer=None, returned=produced)
        bound = n["_CollectionOriginFrame"](binding, parent.transition, "BOUND", None, produced, producer_frame,
            (), oldgraph, (oldgraph.__dict__, oldgraph.nodes, oldgraph.paths), None)
        # Test-only pointers are part of the parent dictionary being pinned.
        parent._model_binding, parent._model_bound = binding, bound
        parent.owner, parent.window, parent.state = owner, window, "CLOSING"
        parent.handles["phase"] = phase
        parent.handlers[signal.SIGINT] = signal.SIG_DFL
        pending = b"MODEL_PENDING"
        parent.records["collection-pending"] = pending
        file = n["_CollectionPhaseFile"]("collection-pending", phase, phase.path, phase.identity,
            "collection-pending.json", 4194304, pending, b"MODEL_BINDING")
        self.change(parent, state="CLOSING", binding=binding, bound=bound, predecessor=predecessor, first=reading,
            limits=n["_CollectionPhaseLimits"]((clock.role, clock.domain, clock.frequency), 100 * NS, 100.0,
                (220 * NS, 265 * NS, 295 * NS), (220.0, 265.0, 295.0)), window=window, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end, poison), last=170 * NS,
            local_last=170.0, phases=tuple(n["_CollectionPhaseStep"](name, start * NS, float(start), end * NS, float(end))
                for name, start, end in (("WORK", 100, 220), ("FINAL", 150, 195), ("READ", 160, 190))),
            resources=(n["_CollectionPhaseResource"](row, row["label"], phase, type(phase), True, True),),
            handles=(("phase", phase, phase.path, phase.identity),), files=(file,), handlers=tuple(parent.handlers.items()),
            restored=tuple(parent.handlers.items()), close_roster=((id(row), row["label"], id(phase)),), owner_closed=True,
            query_attempted=True, query=(supplier, Query, supplier._owner_deadlines, 130 * NS, 150 * NS),
            query_returned=(True, 140 * NS, 140.0), query_result=owner.admissions[0], query_final_attempted=True,
            query_origin=n["_CollectionPhaseQueryOrigin"](supplier.__dict__, supplier.root, supplier.path, query_roots,
                supplier.resources, supplier.records, supplier.readbacks),
            query_preclose=n["_CollectionPhaseQueryBefore"]((), (), oldgraph, (oldgraph.__dict__, oldgraph.nodes, oldgraph.paths)),
            query_pin=(supplier.__dict__, qgraph, qgraph.__dict__, qgraph.nodes, qgraph.paths),
            source_attempted=True, source_pin=(((1, 60), (1, 61)), (("scripts/MODEL_SOURCE.py", b"MODEL_SOURCE", b"MODEL_STAT"),)),
            manifest_attempted=True, manifest_pin=(phase, phase.path, phase.identity, originals.manifest_raw, b"MODEL_STAT"),
            leaf_attempted=True, leaf_originals=originals, leaf_originals_pin=n["collect_files"]._capture(originals), leaf=leaf,
            leaf_pin=(leaf.__dict__, leaf.raw, leaf.inventory_raw, leaf.local_started, leaf.checked_local),
            leaf_began=(139 * NS, 139.0), pending_raw=pending)
        return parent

    def raw(self, frame, closed=165 * NS):
        return encoded({"schema": 1, "scope": "BOOTSTRAP_COLLECTION_PARENT_CLOSED_OBSERVATIONS_V1",
            "producerSha256": digest(frame.bound.returned.raw), "producerCheckedNs": frame.bound.returned.checked_ns,
            "manifestSha256": digest(frame.manifest_pin[3]), "leafSha256": digest(frame.leaf_pin[1]),
            "inventorySha256": digest(frame.leaf_pin[2]), "pendingSha256": digest(frame.pending_raw),
            "window": {"clock": self.n["origin"].clock_value(frame.first.clock), "firstNs": frame.limits.first,
                "globalEndsNs": dict(zip(("WORK", "FINAL", "READ"), frame.limits.ends)),
                "phases": [{"phase": row.name, "startedNs": row.started, "endNs": row.end} for row in frame.phases],
                "readSlotScope": "POST_CLOSE_RETURN_OBSERVATIONS_ONLY_NO_FILE_READ_EXECUTION", "budgetAcceptance": "NOT_ADMITTED"},
            "closedNs": closed, "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "resourceCount": len(frame.resources),
            "currentFileObservation": "MEMBERSHIP_ROOT_AND_FILE_BINDINGS_NOT_DESCENDANT_CONTINUITY_OR_FREEZE",
            "noLoaderObservation": "NOT_OBSERVED", "dependencyPopulation": "NOT_ATTESTED", "nextPhaseAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})

    def complete(self, parent):
        frame = self.frame(parent)
        self.before_tail = frame
        def final_check(actual):
            require(actual is parent and actual.state == "COMPLETE" and actual.result is self.frame(parent).result,
                    "MODEL_FINAL_PUBLIC_BOOKKEEPING")
            self.events.append("MODELED_FINAL_CHECK_REPLACES_FRAME")
            self.change(parent, foreign=())
            if self.before_publish:
                self.before_publish(parent)
        self.n["_CollectionPhaseParent"].check = final_check
        old = self.n["_publish_collection_phase"]
        if self.no_publication:
            self.n["_publish_collection_phase"] = lambda *_: None
        try:
            result = self.n["selected_return_tail"](parent, self.raw(frame), frame, frame.last)
        finally:
            self.n["_CollectionPhaseParent"].check = poison
            self.n["_publish_collection_phase"] = old
        self.after_tail = self.frame(parent)
        return result

    def collect(self, transition):
        self.calls += 1
        require(transition is self.transition, "MODEL_NOT_ORIGINAL_ENTRY")
        if self.collect_error is not None:
            raise self.collect_error
        parent = self.prepare(transition)
        result = self.complete(parent)
        if self.after_publish:
            self.after_publish(parent)
        return result if self.return_override is None else self.return_override

    def begin(self):
        return self.n["_begin_no_loader_after_entry"](self.transition)

    def bound(self):
        call = self.begin()
        return call, self.n["_checked_no_loader_origin"](call)


class PublicationModels(unittest.TestCase):
    def test_actual_selected_tail_publishes_only_after_final_frame_replacement(self):
        m = Model(); call, saved = m.bound()
        self.assertIs(saved.pin.frame, m.after_tail)
        self.assertIsNot(saved.pin.frame, m.before_tail)
        self.assertEqual(m.events, ["MODELED_FINAL_CHECK_REPLACES_FRAME"])
        self.assertIs(m.frame(), saved.pin.frame)
        self.assertEqual(call.state, "BOUND")

    def test_lookup_is_passive_and_keeps_the_exact_original_pin(self):
        m = Model(); call, saved = m.bound()
        parent, frame, dictionary = saved.collection, saved.pin.frame, dict(saved.collection.__dict__)
        for _ in range(3):
            self.assertIs(m.n["_checked_no_loader_origin"](call), saved)
        self.assertIs(m.frame(parent), frame)
        self.assertEqual(parent.__dict__, dictionary)
        self.assertEqual(m.calls, 1)

    def test_consistent_return_without_original_publication_is_not_authority(self):
        m = Model(); m.no_publication = True
        with self.assertRaisesRegex(Refusal, "RESULT_NOT_PUBLISHED") as caught: m.begin()
        call = caught.exception.bootstrap_no_loader_origin
        self.assertIs(call.returned, m.parents[-1].result)
        self.assertEqual(call.state, "FAILED")

    def test_publication_cannot_be_repeated_after_success(self):
        m = Model(); _, saved = m.bound()
        with self.assertRaisesRegex(Refusal, "PUBLICATION_REENTRY"):
            m.n["_publish_collection_phase"](saved.collection, saved.returned)

    def test_failed_capture_is_consumed_without_late_rebaseline(self):
        m = Model(); parent = m.prepare()
        m.before_publish = lambda p: p.owner.admissions.append([0] * 10001)
        with self.assertRaisesRegex(Refusal, "EDGE_LIMIT"): m.complete(parent)
        parent.owner.admissions.pop()
        with self.assertRaisesRegex(Refusal, "PUBLICATION_REENTRY"):
            m.n["_publish_collection_phase"](parent, parent.result)
        with self.assertRaisesRegex(Refusal, "RESULT_NOT_PUBLISHED"):
            m.n["_collection_phase_original_result"](parent)

    def test_equal_replacement_private_frame_refuses(self):
        m = Model(); call, saved = m.bound()
        m.change(foreign=())
        self.assertIsNot(m.frame(), saved.pin.frame)
        with self.assertRaisesRegex(Refusal, "RESULT_NOT_PUBLISHED"): m.n["_checked_no_loader_origin"](call)

    def test_failed_frame_cannot_reuse_an_earlier_publication(self):
        m = Model(); call, _ = m.bound()
        m.change(state="FAILED"); m.parents[-1].state = "FAILED"
        with self.assertRaisesRegex(Refusal, "RESULT_NOT_PUBLISHED"): m.n["_checked_no_loader_origin"](call)

    def test_earlier_closed_time_is_not_relabelled_as_final_highwater(self):
        m = Model(); _, saved = m.bound()
        self.assertEqual(json.loads(saved.returned.raw)["closedNs"], 165 * NS)
        self.assertEqual(saved.returned.checked_ns, 170 * NS)


class OriginModels(unittest.TestCase):
    def test_second_begin_never_dispatches_a_second_collector(self):
        m = Model(); m.begin()
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"): m.begin()
        self.assertEqual(m.calls, 1)

    def test_reentry_during_collector_does_not_hold_claim_lock(self):
        m = Model()
        def nested(_):
            with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"): m.begin()
        m.before_publish = nested
        m.begin(); self.assertEqual(m.calls, 1)

    def test_preexisting_direct_collection_is_not_adopted(self):
        m = Model(); m.collect(m.transition)
        with self.assertRaisesRegex(Refusal, "COLLECTION_PHASE_ALREADY_CLAIMED") as caught: m.begin()
        self.assertIsNone(caught.exception.bootstrap_no_loader_origin.returned)
        self.assertEqual(len(m.parents), 1)

    def test_falsey_failure_and_failed_annotation_preserve_the_original(self):
        m = Model(); failure = UnannotatableFailure("MODEL_FIRST")
        m.collect_error = failure
        with self.assertRaises(UnannotatableFailure) as caught: m.begin()
        self.assertIs(caught.exception, failure)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"): m.begin()
        self.assertEqual(m.calls, 1)

    def test_collector_failure_keeps_return_unobserved(self):
        m = Model(); m.collect_error = FalseyFailure("MODEL_FIRST")
        with self.assertRaises(FalseyFailure) as caught: m.begin()
        call = caught.exception.bootstrap_no_loader_origin
        self.assertIs(call.original, m.collect_error)
        self.assertIsNone(call.returned)
        self.assertIsNone(call.collection)

    def test_changed_operation_after_return_keeps_the_actual_object(self):
        m = Model(); m.after_publish = lambda _: m.n.__setitem__("collect_after_entry", poison)
        with self.assertRaisesRegex(Refusal, "OPERATION_CHANGED") as caught: m.begin()
        self.assertIs(caught.exception.bootstrap_no_loader_origin.returned, m.parents[-1].result)
        self.assertIsNone(caught.exception.bootstrap_no_loader_origin.collection)

    def test_changed_lookup_after_return_is_not_called(self):
        m = Model(); m.after_publish = lambda _: m.n.__setitem__("_collection_phase_original_call", poison)
        with self.assertRaisesRegex(Refusal, "OPERATION_CHANGED") as caught: m.begin()
        self.assertIs(caught.exception.bootstrap_no_loader_origin.returned, m.parents[-1].result)

    def test_changed_result_lookup_after_return_is_not_called(self):
        m = Model(); m.after_publish = lambda _: m.n.__setitem__("_collection_phase_original_result", poison)
        with self.assertRaisesRegex(Refusal, "OPERATION_CHANGED") as caught: m.begin()
        self.assertIs(caught.exception.bootstrap_no_loader_origin.returned, m.parents[-1].result)

    def test_equal_copied_prefix_is_not_the_actual_published_return(self):
        m = Model(); m.after_publish = lambda p: setattr(m, "return_override", copy.copy(p.result))
        with self.assertRaisesRegex(Refusal, "NOT_ORIGINAL_COLLECTION_RETURN") as caught: m.begin()
        self.assertIs(caught.exception.bootstrap_no_loader_origin.returned, m.return_override)
        self.assertIsNot(m.return_override, m.parents[-1].result)

    def test_malformed_actual_return_is_retained(self):
        m = Model(); m.return_override = object()
        with self.assertRaisesRegex(Refusal, "NOT_ORIGINAL_COLLECTION_RETURN") as caught: m.begin()
        self.assertIs(caught.exception.bootstrap_no_loader_origin.returned, m.return_override)

    def test_copied_transition_has_no_original_lookup(self):
        m = Model(); m.begin()
        with self.assertRaisesRegex(Refusal, "NOT_ORIGINAL_CALL"):
            m.n["_collection_phase_original_call"](copy.copy(m.transition))

    def test_constructed_or_copied_binding_is_not_a_claim(self):
        m = Model(); call = m.begin()
        for other in (m.n["_NoLoaderOrigin"](m.transition), copy.copy(call)):
            with self.subTest(kind=type(other).__name__), self.assertRaisesRegex(Refusal, "NOT_CLAIMED"):
                m.n["_checked_no_loader_origin"](other)

    def test_changed_public_binding_is_not_repaired_from_private_state(self):
        m = Model(); call = m.begin(); call.returned = copy.copy(call.returned)
        with self.assertRaisesRegex(Refusal, "ORIGIN_NOT_BOUND"): m.n["_checked_no_loader_origin"](call)

    def test_failed_attempt_is_consumed_after_post_return_corruption(self):
        m = Model(); m.after_publish = lambda p: p.owner.resources.clear()
        with self.assertRaises(Refusal): m.begin()
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"): m.begin()
        self.assertEqual(m.calls, 1)

    def test_bound_exposes_no_new_owner_deadline_leaf_or_acceptance(self):
        m = Model(); call, saved = m.bound()
        self.assertEqual(set(call.__dict__), {"transition", "state", "collection", "returned", "original"})
        value = json.loads(saved.returned.raw)
        self.assertEqual(value["noLoaderObservation"], "NOT_OBSERVED")
        self.assertEqual(value["dependencyPopulation"], "NOT_ATTESTED")
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(value["nextPhaseAuthority"], False)
        self.assertIs(value["exportSaveAuthority"], False)


class GraphModels(unittest.TestCase):
    def refused_between_return_and_first_lookup(self, mutation):
        m = Model(); m.after_publish = lambda p: mutation(m, p)
        with self.assertRaises(Refusal) as caught: m.begin()
        self.assertIs(caught.exception.bootstrap_no_loader_origin.returned, m.parents[-1].result)
        self.assertEqual(caught.exception.bootstrap_no_loader_origin.state, "FAILED")
        self.assertEqual(m.calls, 1)

    def test_erased_nonrequired_query_row_is_not_a_first_lookup_baseline(self):
        self.refused_between_return_and_first_lookup(lambda m, p: m.frame(p).query[0].resources.pop(2))

    def test_equal_query_list_replacement_refuses(self):
        self.refused_between_return_and_first_lookup(lambda m, p: setattr(m.frame(p).query[0], "records", list(m.frame(p).query[0].records)))

    def test_original_query_record_contents_are_transitively_pinned(self):
        self.refused_between_return_and_first_lookup(lambda m, p: m.frame(p).query[0].records[0]["MODEL"].clear())

    def test_original_query_dictionary_identity_is_pinned(self):
        self.refused_between_return_and_first_lookup(lambda m, p: object.__setattr__(m.frame(p).query[0], "__dict__", dict(m.frame(p).query[0].__dict__)))

    def test_leaf_originals_are_not_opaque(self):
        self.refused_between_return_and_first_lookup(lambda m, p: object.__setattr__(m.frame(p).leaf_originals, "metadata_bindings_raw", b"CHANGED"))

    def test_leaf_result_dictionary_is_not_opaque(self):
        self.refused_between_return_and_first_lookup(lambda m, p: object.__setattr__(m.frame(p).leaf, "__dict__", dict(m.frame(p).leaf.__dict__)))

    def test_parent_dictionary_identity_is_pinned(self):
        self.refused_between_return_and_first_lookup(lambda _m, p: object.__setattr__(p, "__dict__", dict(p.__dict__)))

    def test_equal_result_dictionary_replacement_refuses(self):
        self.refused_between_return_and_first_lookup(lambda _m, p: object.__setattr__(p.result, "__dict__", dict(p.result.__dict__)))

    def test_older_witness_nodes_cannot_be_erased(self):
        self.refused_between_return_and_first_lookup(lambda m, p: object.__setattr__(m.frame(p).bound.graph, "nodes", ()))

    def test_older_witness_paths_cannot_be_erased(self):
        self.refused_between_return_and_first_lookup(lambda m, p: object.__setattr__(m.frame(p).bound.graph, "paths", ()))

    def test_older_witness_dictionary_cannot_be_replaced(self):
        self.refused_between_return_and_first_lookup(lambda m, p: object.__setattr__(m.frame(p).bound.graph, "__dict__", dict(m.frame(p).bound.graph.__dict__)))

    def test_original_native_path_pin_refuses_changed_directory_identity(self):
        self.refused_between_return_and_first_lookup(lambda _m, p: setattr(p.handles["phase"], "identity", (1, 999)))

    def test_query_root_native_path_is_checked_without_verify(self):
        self.refused_between_return_and_first_lookup(lambda m, p: setattr(m.frame(p).query[0].private, "path", m.root / "CHANGED"))

    def test_new_witness_nodes_cannot_be_erased(self):
        m = Model(); call, saved = m.bound()
        object.__setattr__(saved.pin.graph, "nodes", ())
        with self.assertRaisesRegex(Refusal, "WITNESS_CHANGED"): m.n["_checked_no_loader_origin"](call)

    def test_new_witness_dictionary_cannot_be_replaced(self):
        m = Model(); call, saved = m.bound()
        object.__setattr__(saved.pin.graph, "__dict__", dict(saved.pin.graph.__dict__))
        with self.assertRaisesRegex(Refusal, "WITNESS_CHANGED"): m.n["_checked_no_loader_origin"](call)

    def test_later_bound_check_still_uses_the_original_baseline(self):
        m = Model(); call, saved = m.bound(); saved.pin.frame.query[0].readbacks.clear()
        with self.assertRaises(Refusal): m.n["_checked_no_loader_origin"](call)

    def test_cycles_are_identity_deduplicated_not_unbounded_recursion(self):
        m = Model()
        def cycle(parent):
            original = []; original.append(original); parent.owner.admissions.append(original)
        m.before_publish = cycle
        m.begin(); self.assertEqual(m.calls, 1)

    def test_scalar_only_mapping_is_bounded_before_snapshot(self):
        m = Model(); m.before_publish = lambda p: p.owner.admissions.append({number: 0 for number in range(10001)})
        with self.assertRaisesRegex(Refusal, "EDGE_LIMIT"): m.begin()

    def test_many_unique_objects_cannot_escape_the_edge_bound(self):
        m = Model(); m.before_publish = lambda p: p.owner.admissions.append([object() for _ in range(10001)])
        with self.assertRaisesRegex(Refusal, "EDGE_LIMIT"): m.begin()


class ClosedRecordModels(unittest.TestCase):
    def refuses_before_publication(self, mutation, reason):
        m = Model(); parent = m.prepare()
        m.before_publish = lambda p: mutation(m, p)
        with self.assertRaisesRegex(Refusal, reason): m.complete(parent)
        with self.assertRaisesRegex(Refusal, "PUBLICATION_REENTRY"):
            m.n["_publish_collection_phase"](parent, parent.result)

    def test_unknown_owner_is_not_retired(self):
        self.refuses_before_publication(lambda _m, p: setattr(p.owner, "unknown", True), "OWNER_NOT_CLOSED")

    def test_unclosed_resource_is_not_fixed_by_lookup(self):
        self.refuses_before_publication(lambda _m, p: p.owner.resources[0].__setitem__("closed", False), "ROSTER")

    def test_missing_handler_restore_refuses_without_restoring_it(self):
        self.refuses_before_publication(lambda m, p: m.change(p, restored=()), "ROSTER")

    def test_cancelled_closed_parent_cannot_publish(self):
        self.refuses_before_publication(lambda _m, p: p.cancelled.append(signal.SIGINT), "NOT_COMPLETE")

    def test_failed_original_cannot_publish(self):
        def fail(m, p):
            first = FalseyFailure("MODEL_FIRST"); p.original = first; m.change(p, original=first)
        self.refuses_before_publication(fail, "NOT_COMPLETE")

    def test_bool_highwater_cannot_replace_an_integer(self):
        m = Model(); m.after_publish = lambda p: object.__setattr__(p.result, "checked_ns", True)
        with self.assertRaisesRegex(Refusal, "PUBLISHED_FIELDS_CHANGED"): m.begin()

    def test_nonfinite_local_highwater_refuses(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                m = Model(); m.after_publish = lambda p: object.__setattr__(p.result, "checked_local", value)
                with self.assertRaisesRegex(Refusal, "PUBLISHED_FIELDS_CHANGED"): m.begin()

    def test_equal_numeric_local_type_replacement_refuses(self):
        m = Model(); m.after_publish = lambda p: object.__setattr__(p.result, "checked_local", 170)
        with self.assertRaisesRegex(Refusal, "PUBLISHED_FIELDS_CHANGED"): m.begin()

    def test_changed_manifest_bytes_refuse(self):
        m = Model(); m.after_publish = lambda p: object.__setattr__(p.result, "manifest_raw", b"CHANGED")
        with self.assertRaisesRegex(Refusal, "PUBLISHED_FIELDS_CHANGED"): m.begin()

    def test_promoted_export_flag_is_not_a_valid_closed_record(self):
        m = Model(); parent = m.prepare()
        def promote(p):
            value = json.loads(p.result.raw); value["exportSaveAuthority"] = True; raw = encoded(value)
            object.__setattr__(p.result, "raw", raw)
            pin = m.frame(p).result_pin
            m.change(p, result_pin=(pin[0], raw, *pin[2:]))
        m.before_publish = promote
        with self.assertRaisesRegex(Refusal, "RECORD_CHANGED"): m.complete(parent)

    def test_closed_timestamp_after_final_highwater_refuses(self):
        m = Model(); parent = m.prepare()
        original = m.raw; m.raw = lambda frame: original(frame, 171 * NS)
        with self.assertRaisesRegex(Refusal, "CLOSED_TIME"): m.complete(parent)

    def test_original_return_must_be_strictly_before_read_deadline(self):
        self.refuses_before_publication(lambda m, p: m.change(p,
            phases=(*m.frame(p).phases[:-1], m.frame(p).phases[-1]._replace(end=170 * NS))), "CHRONOLOGY")

    def test_unknown_global_quarantine_refuses_without_cleanup(self):
        self.refuses_before_publication(lambda m, _p: m.n["QUARANTINE"].append(object()), "PRIOR_UNKNOWN")


class ReviewBoundaryModels(unittest.TestCase):
    """New F1/F2 regressions; native identities remain explicit model data."""
    def refuse_before_first_lookup(self, identity):
        m = Model(); m.after_publish = lambda p: setattr(p.handles["phase"], "identity", identity)
        with self.assertRaises(Refusal): m.begin()

    def refuse_after_bound(self, identity):
        m = Model(); call = m.begin()
        m.parents[-1].handles["phase"].identity = identity
        with self.assertRaises(Refusal): m.n["_checked_no_loader_origin"](call)

    def graph_input(self, identity, role="linux-x64"):
        m = Model()
        directory = Directory(m.root / "graph-only", identity)
        limits = m.n["_CollectionPhaseLimits"]((role, "MODEL_NOT_OBSERVED", NS), 0, 0.0,
            (120 * NS, 165 * NS, 195 * NS), (120.0, 165.0, 195.0))
        frame = m.n["_CollectionPhaseFrame"](limits=limits,
            handles=(("graph-only", directory, directory.path, identity),), files=())
        return m, directory, frame

    def test_bool_native_component_before_first_lookup_refuses(self):
        self.refuse_before_first_lookup((True, 20))

    def test_equal_float_native_component_before_first_lookup_refuses(self):
        self.refuse_before_first_lookup((1, 20.0))

    def test_bool_native_component_after_bound_refuses(self):
        self.refuse_after_bound((True, 20))

    def test_equal_float_native_component_after_bound_refuses(self):
        self.refuse_after_bound((1.0, 20))

    def test_conflicting_typed_original_aliases_refuse(self):
        m, directory, frame = self.graph_input((1, 20))
        frame = frame._replace(handles=(*frame.handles, ("typed-alias", directory, directory.path, (1.0, 20))))
        with self.assertRaises(Refusal): m.n["_CollectionReturnGraph"].capture(frame)

    def test_original_native_identity_grammar_refuses_bool(self):
        m, _, frame = self.graph_input((True, 20))
        with self.assertRaises(Refusal): m.n["_CollectionReturnGraph"].capture(frame)

    def test_windows_shaped_original_path_pin_is_valid_model_data(self):
        m, directory, frame = self.graph_input((1, "12" * 16), "windows-x64")
        graph = m.n["_CollectionReturnGraph"].capture(frame)
        graph.checked()
        self.assertEqual(graph.paths, ((directory, Directory, directory.path, directory.identity),))

    def test_posix_value_normalization_does_not_claim_original_container_identity(self):
        m, directory, frame = self.graph_input((1, 20))
        graph = m.n["_CollectionReturnGraph"].capture(frame)
        directory.identity = [1, 20]
        graph.checked()  # The existing contract normalizes tuple/list values.

    def test_five_key_resource_row_refuses_before_set_projection(self):
        m = Model(); parent = m.prepare()
        row = parent.owner.resources[0]
        row["MODEL_EXTRA_KEY"] = True
        projections = []
        def observed_set(value=()):
            if value is row:
                projections.append("RESOURCE_ROW_SET_CALLED")
            return set(value)
        m.n["set"] = observed_set  # Explicit set-call observation, not a large allocation.
        with self.assertRaises(Refusal): m.complete(parent)
        self.assertEqual(projections, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
