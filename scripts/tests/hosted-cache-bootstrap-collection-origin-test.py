#!/usr/bin/env python3
"""Memory-only controls of the new original-call/closed-producer binding.

AST-extract the actual binding, producer private registry/accessor, container
declarations, pure native-record guards and accepted closed-graph engine. The
producer operation, earlier predecessor check, canonical observation validator
and scalar/parser suppliers are explicit inert models. CLOSED
frames below are supplied data, NOT observed producer/native/query executions.
No prior test fixture or accepted test method is imported or replayed. All old
parent/owner/window/resource methods are poisoned. No file acquisition, manifest,
native clock/process, host identity, provider, Java, Gradle or download is used.

Only this source file and the runner source are read. The optional outer audit
harness must enforce the separately recorded invocation/resource envelope.
"""
from __future__ import annotations

import ast
from collections import namedtuple
import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import signal
import subprocess
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "run-hosted-cache-bootstrap.py"
NS = 1_000_000_000


class Refusal(ValueError):
    pass


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


def require(value, reason):
    if not value:
        raise Refusal(reason)


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= (1 << 64) - 1, "MODEL_INTEGER")
    return value


def local(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "MODEL_LOCAL")
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def poison(*_args, **_kwargs):
    raise AssertionError("NO_CLOSED_METHOD_OR_LIVE_SUPPLIER")


@dataclass(frozen=True)
class ModelClock:
    values: tuple = ("linux-x64", "MODEL_CLOCK_NOT_OBSERVED", NS)


@dataclass(frozen=True)
class ModelReading:
    clock: object
    nanoseconds: int


class ModelDirectory:
    def __init__(self, path, identity):
        self.path = path if type(path) in (PurePosixPath, PureWindowsPath) else PurePosixPath(path)
        self.identity = identity

    open_file = create_file = open_directory = create_directory = verify = close = poison


class ModelStream:
    def __init__(self, path, role="linux-x64"):
        self.path = path
        if role == "windows-x64":
            self.max_bytes, self._deadline = 67174400, 970.0
        else:
            self.maximum, self.deadline = 67174400, 970.0

    read = write = sync = verify = close = observe_live_output = poison


class ModelNative:
    # A native supplier need not have a generic .closed property. The original
    # private close roster, not an invented backend attribute, proves its duty.
    spawn = discover = drain = description = close = poison


class ModelQuery:
    def __init__(self, root, path):
        self.root, self.path = root, path
        self.closed, self.unknown, self.failed, self.active = True, False, False, False
        self.first_error = self.cancellation = None
        self.private = ModelDirectory(path, (1, 501))
        self.home = ModelDirectory(path / "query-home", (1, 502))
        self.errors = []
        self.resources = [{"label": name, "owner": value, "closeAttempted": True, "closed": True}
            for name, value in (("private-root", self.private), ("query-home", self.home),
                ("owner.json", ModelStream(path / "owner.json")),
                ("session-result.json", ModelStream(path / "session-result.json")))]
        self.records = [{"MODEL": "ORIGINAL_QUERY_NOT_EXECUTED", "argv": ["status"], "result": "READY_FOR_CALLER_SEAL"}]
        self.readbacks = [{"MODEL": "ORIGINAL_READBACK_NOT_EXECUTED", "name": "session-result.json",
                           "retirement": "KNOWN", "result": "RETAINED"}]
        self._owner_deadlines = (175.0, 190.0)

    _finalize = check = run = close = poison


class ModelChild:
    pid, stdout, stderr = 31, None, None
    poll = wait = terminate = kill = poison


CLASSES = {
    "NewEntryTransition", "ConfigurationPrefix", "ConfigurationCustodyPrefix",
    "_StagingSequence", "_StagingClosedGraph", "_ProducerParent", "_ProducerWindow",
    "_ProducerOwner", "_CollectionOrigin",
}
FUNCTIONS = {
    "_producer_private_controls", "_collection_origin_controls", "_collection_closed_producer",
    "_capture_collection_producer", "_checked_collection_origin", "_begin_collection_after_entry",
    "_collection_producer_original_bytes", "_capture_producer_graph", "_check_producer_result_graph",
    "native_record", "baseline_record", "lifetime", "closed_lifetime",
}
RECORDS = {
    "_StagingSequenceFrame", "_StagingFrame", "_StagingLimits", "_CustodyRequestPin",
    "_ProducerPredecessor", "_ProducerLimits", "_ProducerPhase", "_ProducerResource",
    "_ProducerFile", "_ProducerCapture", "_ProducerNative", "_ProducerFrame", "_ProducerResultPin", "_CollectionOriginFrame",
    "BACKENDS", "LIFETIME_FIELDS",
}
ALIASES = {"_claim_producer", "_claim_collection_origin"}


def extracted_source():
    """Parse only source; never import the controller or execute its top level."""
    tree = ast.parse(SOURCE.read_bytes(), filename=str(SOURCE))
    nodes, found = [], set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in CLASSES | FUNCTIONS:
            nodes.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            names = {item.id for target in node.targets for item in ast.walk(target) if isinstance(item, ast.Name)}
            if names & (RECORDS | ALIASES):
                nodes.append(node)
                found.update(names & (RECORDS | ALIASES))
        elif isinstance(node, ast.Delete) and any(isinstance(target, ast.Name) and target.id in
                {"_producer_private_controls", "_collection_origin_controls"} for target in node.targets):
            nodes.append(node)
    require(found == CLASSES | FUNCTIONS | RECORDS | ALIASES, "EXTRACTION_ROSTER_CHANGED")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    return compile(ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[])), str(SOURCE), "exec")


class BindingModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = extracted_source()

    def setUp(self):
        name = "collection_origin_memory_" + self._testMethodName
        self.s = ModuleType(name)
        sys.modules[name] = self.s
        self.addCleanup(sys.modules.pop, name, None)
        s = self.s
        self.guard_log = []
        def tracked_require(value, reason):
            self.guard_log.append((reason, value is True))
            return require(value, reason)
        s.__dict__.update(dataclass=dataclass, field=field, namedtuple=namedtuple, threading=threading,
            require=tracked_require, math=math, re=re, signal=signal, LIMIT=4 * 1024 * 1024, Path=PurePosixPath,
            subprocess=SimpleNamespace(list2cmdline=subprocess.list2cmdline))
        # Unrelated exact graph-whitelist families are inert modeled containers.
        for label in ("Owner", "_EntryAttempt", "ClosedEntryTransition", "OriginalEntry", "OriginalPhase",
                "_StagingFileOwner", "_NewEntryWindow", "_RecipientParent", "_InitializerParent",
                "_RecipientParentWindow", "_InitializerWindow", "_RecipientParentBindings", "_RecipientResource",
                "_ParentControl", "_RecipientPredecessorGraph", "_InitializerPredecessor", "_InitializationInputs",
                "InitializationPrefix", "_StagingPhaseParent", "_StagingWindow", "_StagingPhaseReturn", "StagingPrefix"):
            setattr(s, label, type(label, (), {}))
        s.origin = SimpleNamespace(OriginError=Refusal, Fence=type("ModelFence", (), {}), NS=NS,
            integer=integer, parse=lambda raw: json.loads(raw), encoded=encoded,
            digest=lambda raw: hashlib.sha256(raw).hexdigest(),
            clock_value=lambda clock: dict(zip(("role", "domain", "ticksPerSecond"), clock.values)),
            clocks=SimpleNamespace(Reading=ModelReading, ClockIdentity=ModelClock, observe=poison, checked_now=poison,
                UINT64=(1 << 64) - 1))
        s.I = SimpleNamespace(Admission=type("ModelAdmission", (), {}))
        s.initialization = SimpleNamespace(InstalledToolchains=type("ModelTools", (), {}))
        s.custody = SimpleNamespace(StagedEvidence=type("ModelStaged", (), {}),
            ReservationEvidence=type("ModelReservation", (), {}))
        s.staging = SimpleNamespace(_local=local, _clock=lambda clock: clock.values,
            Originals=type("ModelOriginals", (), {}), PhaseStart=type("ModelPhase", (), {}),
            LeafEvidence=type("ModelLeaf", (), {}))
        s.query, s.diagnostics, s.QUARANTINE = SimpleNamespace(QUARANTINE=[], _CONTEXT=("MODEL_CONTEXT",)), SimpleNamespace(_QUARANTINE=[]), []
        s.producer = SimpleNamespace(parse=lambda raw: json.loads(raw), validate_observation=self.model_observation)
        for label in ("_ENTRY_ATTEMPTS", "_RECIPIENT_ATTEMPTS", "_INITIALIZER_ATTEMPTS", "_PARENT_CONTROLS", "_STAGING_ATTEMPTS"):
            setattr(s, label, {})
        s._recipient_after_entry = poison
        s.configure_after_entry = self.model_producer
        s._producer_predecessor_checked = self.model_predecessor
        self.calls, self.predecessor_calls = [], []
        self.before_publication = lambda: None
        self.before_return = lambda: None
        self.during_producer = lambda: None
        self.producer_error = self.predecessor_error = None
        self.parent = self.origin = None
        self.role = "linux-x64"
        exec(self.code, s.__dict__)
        for kind in (s._ProducerParent, s._ProducerOwner, s._ProducerWindow):
            for label, value in tuple(vars(kind).items()):
                if not label.startswith("__") and (callable(value) or isinstance(value, property)):
                    setattr(kind, label, property(poison) if isinstance(value, property) else poison)
        self.entry = s.NewEntryTransition(b"MODEL_ENTRY_NOT_EXECUTED", object(), 1, 2, 3)

    def model_observation(self, value, request, admitted, canonical, start, receipt, *, original_exit_code):
        # This is the explicit modeled predecessor-record validator boundary,
        # not execution/retesting of the accepted canonical observation helper.
        require(value == self.observation and (request, admitted, canonical, start, receipt) == self.observation_inputs and
                type(original_exit_code) is int and original_exit_code == 0, "MODEL_OBSERVATION_BINDING")
        return value

    def model_predecessor(self, parent):
        self.predecessor_calls.append(parent)
        if self.predecessor_error is not None:
            raise self.predecessor_error
        require(parent is self.parent and self.s._producer_frame(parent).predecessor is self.predecessor,
                "MODEL_ORIGINAL_PREDECESSOR_CHANGED")
        # Only these stored modeled graph facts are consulted, never old methods.
        self.predecessor.graph.checked()
        self.predecessor.frame.graph.checked()
        return self.predecessor.frame

    def model_producer(self, transition):
        self.calls.append(transition)
        self.assertIs(transition, self.entry)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            self.s._claim_collection_origin(transition)
        self.during_producer()
        if self.producer_error is not None:
            raise self.producer_error
        self.make_closed_producer(transition)
        self.before_return()
        return self.returned

    def make_closed_producer(self, transition):
        s = self.s
        path_type = PureWindowsPath if self.role == "windows-x64" else PurePosixPath
        s.Path = path_type
        root = path_type("C:/model/checkout" if self.role == "windows-x64" else "/model/checkout")
        state = path_type("C:/model/state" if self.role == "windows-x64" else "/model/state")
        p = self.parent = s._claim_producer(transition)
        first = ModelReading(ModelClock((self.role, "MODEL_CLOCK_NOT_OBSERVED", NS)), 100 * NS)
        limits = s._ProducerLimits(first.clock.values, first.nanoseconds, 100.0,
            tuple(x * NS for x in (700, 925, 970, 1000)), (700.0, 925.0, 970.0, 1000.0))
        phases = tuple(s._ProducerPhase(name, start * NS, float(start), end * NS, float(end)) for name, start, end in
            (("WORK", 100, 700), ("RETURN", 200, 425), ("FINAL", 205, 250), ("READ", 210, 240)))
        window = s._ProducerWindow(p)
        owner = object.__new__(s._ProducerOwner)
        owner.__dict__.update(closed=True, original=None, unknown=False, resources=[], errors=[], admissions={},
            local_end=1000.0, cancelled=poison, first=first, fence=window, work_limit=None, final_limit=None,
            early_last=first.nanoseconds, phase_originals=None, entry_original=None, entry_close_attempted=False,
            entry_close_original=None, entry_close_snapshot=None)
        p.owner, p.window, p.state = owner, window, "COMPLETE"
        file_id = lambda number: (1, f"{number:032x}" if self.role == "windows-x64" else number)
        directory = self.directory = ModelDirectory(state.parent / "configuration-parent", file_id(21))
        canonical = self.canonical = ModelDirectory(state / "evidence" / "original", file_id(22))
        streams = tuple(ModelStream(directory.path / (name + ".log"), self.role) for name in ("stdout", "stderr"))
        self.streams, self.native, self.query = streams, ModelNative(), ModelQuery(root, directory.path / "admission")
        resources = []
        for label, value in (("directory", directory), ("directory", canonical), ("stdout", streams[0]),
                ("stderr", streams[1]), ("native-scope", self.native)):
            row = {"label": label, "owner": value, "attempted": True, "closed": True}
            owner.resources.append(row)
            resources.append(s._ProducerResource(row, label, value, type(value), True, True))
        handles = (("phase", directory, directory.path, directory.identity),
            ("capture-output", directory, directory.path, directory.identity),
            ("canonical-invocation", canonical, canonical.path, canonical.identity))
        p.handles.update((row[0], row[1]) for row in handles)
        request = {"MODEL": "NO_PRODUCER_EXECUTION", "host": self.role, "cwd": str(root), "jobId": "b" * 32,
            "id": "c" * 32, "gradleHome": str(state / "gradle-home")}
        request_raw = encoded(request)
        start_raw, receipt_raw = encoded({"controllerPid": 31, "MODEL": "start"}), encoded({"controllerPid": 31, "MODEL": "receipt"})
        handlers = ((signal.SIGINT, signal.SIG_DFL), (signal.SIGTERM, signal.SIG_IGN))
        p.handlers.update(handlers)
        captures = tuple(s._ProducerCapture(name, stream, file_id(30 + index), 8,
            ((file_id(30 + index), 8, b"MODEL_WINDOWS_FULL_STAMP") if self.role == "windows-x64" else
             (file_id(30 + index), 8, 11, 12)), True, True, (8, hashlib.sha256(b"MODELLOG").hexdigest(),
                (212 + index) * NS, float(212 + index)))
            for index, (name, stream) in enumerate(zip(("stdout", "stderr"), streams)))
        admitted_raw, canonical_raw = encoded({"MODEL": "admission"}), encoded({"MODEL": "canonical-context"})
        argv = [str(root / "MODEL_NOT_EXECUTED.py"), "model-configuration"]
        descriptor = {"requestBytes": request_raw.decode("ascii"), "requestSha256": s.origin.digest(request_raw),
            "argv": argv, "role": self.role, "root": str(root), "state": str(state), "gradleHome": request["gradleHome"],
            "admissionSha256": s.origin.digest(admitted_raw), "canonicalContextSha256": s.origin.digest(canonical_raw)}
        descriptor_raw = encoded(descriptor)
        outer = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_PARENT_PRELAUNCH_V1",
            "contextSha256": s.origin.digest(canonical_raw), "argv": argv, "cwd": str(root), "role": self.role,
            "job": request["jobId"], "invocation": "a" * 32, "state": str(state), "home": request["gradleHome"],
            "inheritedContext": {"MODEL_CONTEXT": "NO_EXECUTION"}, "startedNs": 100 * NS,
            "workEndNs": 700 * NS, "finalEndNs": 970 * NS, "exitCode": None, "launchAttempted": False,
            "scopeAttempted": False, "retirement": "UNKNOWN"}
        self.native.invocation = outer["invocation"]
        if self.role == "windows-x64":
            self.native.job_id = outer["job"]
            leader, preparer = {"pid": 31, "creationFileTime": 400, "jobAssignedBeforeResume": True}, {"pid": 7, "creationFileTime": 10}
        elif self.role.startswith("macos-"):
            leader = {"pid": 31, "uniqueId": 400, "startSeconds": 200, "startMicroseconds": 1, "pidVersion": 1}
            preparer = {"pid": 7, "uniqueId": 10, "startSeconds": 100, "startMicroseconds": 1, "pidVersion": 1}
        else:
            leader, preparer = {"pid": 31, "startTicks": 400}, {"pid": 7, "startTicks": 10}
        if self.role != "windows-x64":
            self.native.job, self.native.state, self.native.home = outer["job"], outer["state"], outer["home"]
        launch = {"created": True, "requestedArgv": argv, "resolvedArgv": argv, "cwd": str(root), "pid": 31}
        if self.role == "windows-x64":
            launch.update(api="CreateProcessW", batch=False, applicationName=argv[0], commandLine=subprocess.list2cmdline(argv),
                resumed=True, jobAssignedBeforeResume=True, outputMode="caller-owned-native-files",
                resourceCleanup=[{"phase": "launch-temporary", "resource": name, "status": "RETIRED"} for name in
                    ("startup-attributes", "launch-handle-0", "launch-handle-1", "launch-handle-2", "primary-thread")])
        else:
            launch.update(api="subprocess.Popen", shell=False, executable=argv[0], outputMode="caller-owned-files")
        birth = {"backend": s.BACKENDS[self.role], "job": outer["job"], "invocation": outer["invocation"],
            "discoveryErrors": [], "scope": "kernel-job-no-breakaway-kill-on-close" if self.role == "windows-x64" else
                "controlled-marker-inheriting-descendants", "launches": [launch], "startedIdentities": [leader],
            "discoveryReconciliations": [], "observationReconciliations": [],
            "drainReconciliations": [{"outcome": "retired", "signalReconciliations": []}]}
        baseline_raw = encoded({"role": self.role, "baseline": None if self.role == "windows-x64" else [],
            "kernelJob": self.role == "windows-x64"})
        born_raw = encoded({"ownership": birth, "leader": leader, "preparerIdentity": preparer, "observedNs": 160 * NS})
        native = s._ProducerNative(scope_attempted=True, launch_attempted=True, child=ModelChild(), child_kind=ModelChild,
            child_pid=31, baseline_raw=baseline_raw, preparer_raw=encoded(preparer),
            birth_raw=encoded(birth), leader_raw=encoded(leader), launch_minimum=150 * NS,
            argv=tuple(argv), exit_code=0, completed_ns=180 * NS, work_accepted=True,
            drain_attempted=True, survivors_raw=encoded({"survivors": []}),
            terminal_raw=encoded(birth), retired=True, finalized_ns=207 * NS)
        files = tuple(s._ProducerFile(key, place, place.path, place.identity, name, 4 * 1024 * 1024, raw,
            encoded({"MODEL_FULL_BINDING": key})) for key, place, name, raw in
            (("canonical-start", canonical, "start.json", start_raw),
             ("canonical-receipt", canonical, "receipt.json", receipt_raw),
             ("outer-start", directory, "outer-start.json", encoded(outer)),
             ("baseline", directory, "baseline.json", baseline_raw),
             ("native-start", directory, "native-start.json", born_raw)))
        p.records.update((row.key, row.raw) for row in files)
        sequence = s._StagingSequence(object(), object())
        earlier_nodes = s._StagingClosedGraph.capture({"original": [b"MODEL_PREDECESSOR"]}).nodes
        earlier = s._StagingClosedGraph(earlier_nodes, ((directory, ModelDirectory, directory.path, directory.identity),))
        originals = s.staging.Originals()
        originals.admitted = s.I.Admission()
        originals.admitted.record, originals.canonical_raw = admitted_raw, canonical_raw
        frame_values = dict.fromkeys(s._StagingSequenceFrame._fields)
        frame_values.update(call=sequence, graph=earlier, originals=originals, paths=(), callbacks=(poison,), phases=(),
            state="COMPLETE", plan=("dependency-stage", "empty-seed", "custody-prepare"))
        preceding = s._StagingSequenceFrame(**frame_values)
        self.predecessor = s._ProducerPredecessor(sequence, preceding,
            (sequence.__dict__, tuple(sequence.__dict__.items())), (), s._StagingClosedGraph.capture({"pin": [b"MODEL"]}))
        reservation = s.ConfigurationCustodyPrefix(b"MODEL_RESERVATION_NOT_EXECUTED", None, None, 90 * NS, 90.0)
        self.observation = {"MODEL": "observation"}
        self.observation_inputs = (request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw)
        observation_raw = encoded(self.observation)
        closed = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_PARENT_CLOSED_OBSERVATIONS_V1",
            "reservationSha256": s.origin.digest(reservation.raw), "descriptorSha256": s.origin.digest(descriptor_raw),
            "requestSha256": s.origin.digest(request_raw), "canonicalObservationSha256": s.origin.digest(observation_raw),
            "window": {"clock": s.origin.clock_value(first.clock), "firstNs": 100 * NS,
                "globalEndsNs": {"WORK": 700 * NS, "RETURN": 925 * NS, "FINAL": 970 * NS, "READ": 1000 * NS},
                "phases": [{"phase": phase.name, "startedNs": phase.started, "endNs": phase.end} for phase in phases],
                "budgetAcceptance": "NOT_ADMITTED"}, "closedNs": 219 * NS, "originalExitCode": 0,
            "workCompletedNs": 180 * NS, "outerNativeRetirement": "KNOWN_ORIGINAL_SCOPE_CLOSE",
            "outerStartSha256": s.origin.digest(encoded(outer)), "outerBaselineSha256": s.origin.digest(baseline_raw),
            "outerBirthSha256": s.origin.digest(native.birth_raw), "outerTerminalSha256": s.origin.digest(native.terminal_raw),
            "outerCaptures": {row.name: {"bytes": row.readback[0], "sha256": row.readback[1], "readNs": row.readback[2]}
                for row in captures}, "outerCaptureScope": "TWO_ORIGINAL_STREAMS_OBSERVED_SIZE_NOT_KERNEL_QUOTA_OR_COMPLETE_CUSTODY",
            "canonicalFourLogReportCollection": "NOT_PERFORMED", "dependencyPopulation": "NOT_ATTESTED",
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "resourceCount": len(resources), "nextPhaseAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.returned = s.ConfigurationPrefix(encoded(closed), request_raw, start_raw, receipt_raw, observation_raw, 220 * NS, 220.5)
        s._update_producer(p, state="COMPLETE", first=first, limits=limits, window=window, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end, owner.cancelled),
            last=self.returned.checked_ns, local_last=self.returned.checked_local, phases=phases,
            resources=tuple(resources), handles=handles, files=files, handlers=handlers, restored=handlers,
            close_roster=tuple((id(row.row), row.label, id(row.value)) for row in resources),
            descriptor=descriptor_raw, environment=(("MODEL_CONTEXT", "NO_EXECUTION"),), reservation=reservation,
            outer_invocation="a" * 32, native=native, captures=captures, query_attempted=True,
            query=(self.query, type(self.query), self.query._owner_deadlines, 175 * NS, 190 * NS),
            query_returned=(True, 120 * NS, 120.0), predecessor=self.predecessor)
        # Negative terminal-fact controls inject ONLY before the actual private
        # publication. Later frame mutations instead test the distinct original-
        # frame pin and cannot count as coverage of deeper terminal predicates.
        self.before_publication()
        s._update_producer(p, state="COMPLETE", result=self.returned)
        p.result = self.returned

    def begin(self):
        self.origin = self.s._begin_collection_after_entry(self.entry)
        return self.origin

    def frame(self):
        return self.s._producer_frame(self.parent)

    def mutate(self, **values):
        self.s._update_producer(self.parent, **values)

    def rejected_return(self, mutate, reason):
        original_aliases = {name: getattr(self.s, name) for name in ("configure_after_entry", "_producer_original_call",
            "_producer_original_result", "_ENTRY_ATTEMPTS", "_RECIPIENT_ATTEMPTS", "_INITIALIZER_ATTEMPTS",
            "_PARENT_CONTROLS", "_STAGING_ATTEMPTS")}
        self.before_return = mutate
        with self.assertRaisesRegex(Refusal, "^" + re.escape(reason) + "$") as caught:
            self.begin()
        self.assertEqual(self.guard_log.count((reason, False)), 1, "The intended refusing guard must be reached once")
        call = caught.exception.bootstrap_collection_origin
        saved = self.s._collection_origin_frame(call)
        self.assertEqual(saved.state, "FAILED")
        self.assertIs(saved.returned, self.returned)
        self.assertIs(saved.original, caught.exception)
        # Repairing published aliases cannot renew a failed original claim.
        for name, value in original_aliases.items():
            setattr(self.s, name, value)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            self.begin()
        self.assertEqual(self.calls, [self.entry])
        return saved

    def rejected_facts(self, mutate, reason):
        self.before_publication = mutate
        saved = self.rejected_return(lambda: None, reason)
        self.assertGreaterEqual(len(self.predecessor_calls), 1)
        self.assertIn(("BOOTSTRAP_PRODUCER_RESULT_NOT_ORIGINAL", True), self.guard_log)
        self.assertNotIn(("BOOTSTRAP_PRODUCER_RESULT_NOT_ORIGINAL", False), self.guard_log)
        return saved

    def test_actual_binding_uses_original_call_and_leaves_closed_frame_untouched(self):
        call = self.begin()
        frame = self.frame()
        self.assertIs(self.s._producer_original_call(self.entry), self.parent)
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, frame)
        self.assertIs(self.frame(), frame)
        self.assertEqual((call.state, self.parent.state, self.calls), ("BOUND", "COMPLETE", [self.entry]))
        self.assertIs(call.returned, self.returned)
        self.assertFalse(hasattr(call, "owner"))

    def test_duplicate_and_equal_copied_transition_do_not_select_original_call(self):
        call = self.begin()
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            self.begin()
        copied = copy.copy(self.entry)
        self.assertEqual(copied, self.entry)
        with self.assertRaisesRegex(Refusal, "NOT_ORIGINAL_CALL"):
            self.s._producer_original_call(copied)
        self.assertIs(self.s._checked_collection_origin(call).producer, self.parent)

    def test_constructor_and_prefix_are_not_claims(self):
        forged = self.s._CollectionOrigin(self.entry)
        with self.assertRaisesRegex(Refusal, "NOT_CLAIMED"):
            self.s._checked_collection_origin(forged)
        call = self.begin()
        for value in (call.returned, copy.copy(call), object()):
            with self.subTest(kind=type(value).__name__), self.assertRaises(Refusal):
                self.s._checked_collection_origin(value)
        with self.assertRaisesRegex(Refusal, "TRANSITION_KIND"):
            self.s._begin_collection_after_entry(call.returned)

    def test_reentry_consumes_outer_claim_before_original_producer(self):
        self.during_producer = lambda: self.s._begin_collection_after_entry(self.entry)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED") as caught:
            self.begin()
        self.assertEqual(self.calls, [self.entry])
        self.assertEqual(self.s._collection_origin_frame(caught.exception.bootstrap_collection_origin).state, "FAILED")
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            self.begin()

    def test_original_falsey_exception_is_retained_and_not_retried(self):
        first = self.producer_error = FalseyFailure("MODEL_FIRST")
        with self.assertRaises(FalseyFailure) as caught:
            self.begin()
        self.assertIs(caught.exception, first)
        frame = self.s._collection_origin_frame(first.bootstrap_collection_origin)
        self.assertIs(frame.original, first)
        self.assertIsNone(frame.returned)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            self.begin()

    def test_existing_direct_producer_claim_is_not_adopted(self):
        direct = self.s._claim_producer(self.entry)
        with self.assertRaisesRegex(Refusal, "PRODUCER_ALREADY_CLAIMED") as caught:
            self.begin()
        self.assertIs(self.s._producer_original_call(self.entry), direct)
        self.assertEqual(self.s._producer_frame(direct).state, "CLAIMED")
        self.assertEqual(self.s._collection_origin_frame(caught.exception.bootstrap_collection_origin).state, "FAILED")

    def test_changed_operation_after_return_retains_actual_return_and_consumes_claim(self):
        self.rejected_return(lambda: setattr(self.s, "configure_after_entry", poison),
                             "BOOTSTRAP_COLLECTION_ORIGINAL_OPERATION_CHANGED")

    def test_changed_lookup_after_return_retains_actual_return(self):
        self.rejected_return(lambda: setattr(self.s, "_producer_original_call", poison),
                             "BOOTSTRAP_COLLECTION_ORIGINAL_OPERATION_CHANGED")

    def test_changed_original_registry_root_after_return_refuses(self):
        self.rejected_return(lambda: setattr(self.s, "_ENTRY_ATTEMPTS", {}), "BOOTSTRAP_PRODUCER_ORIGINAL_CALL_CHANGED")

    def test_copied_actual_return_is_not_private_producer_result(self):
        self.rejected_return(lambda: setattr(self, "returned", copy.copy(self.returned)),
                             "BOOTSTRAP_COLLECTION_PRODUCER_NOT_COMPLETE")

    def test_incomplete_or_unknown_closed_producer_refuses(self):
        def changed():
            self.mutate(unknown=True)
            self.parent.unknown = True
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_NOT_COMPLETE")

    def test_owner_error_and_falsey_original_cannot_be_success(self):
        self.rejected_facts(lambda: setattr(self.parent.owner, "original", FalseyFailure("MODEL_OWNER_FAILURE")),
                            "BOOTSTRAP_COLLECTION_PRODUCER_OWNER_NOT_CLOSED")

    def test_replaced_public_roster_list_refuses(self):
        self.rejected_facts(lambda: setattr(self.parent.owner, "resources", list(self.parent.owner.resources)),
                            "BOOTSTRAP_COLLECTION_PRODUCER_OWNER_NOT_CLOSED")

    def test_unclosed_private_resource_refuses(self):
        def changed():
            rows = self.frame().resources
            rows[0].row["closed"] = False
            self.mutate(resources=(rows[0]._replace(closed=False), *rows[1:]))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_CLOSE_ROSTER")

    def test_missing_original_native_scope_close_refuses(self):
        def changed():
            rows = tuple(row for row in self.frame().resources if row.label != "native-scope")
            self.parent.owner.resources[:] = [row.row for row in rows]
            self.mutate(resources=rows, close_roster=tuple((id(row.row), row.label, id(row.value)) for row in rows))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_REQUIRED_CLOSE")

    def test_handlers_must_have_original_restoration(self):
        self.rejected_facts(lambda: self.mutate(restored=()), "BOOTSTRAP_COLLECTION_PRODUCER_CLOSE_ROSTER")

    def test_query_original_must_be_known_closed(self):
        self.rejected_facts(lambda: setattr(self.query, "closed", False), "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")

    def test_capture_stream_must_match_original_closed_resource(self):
        def changed():
            rows = self.frame().captures
            self.mutate(captures=(rows[0]._replace(stream=ModelStream(self.streams[0].path)), rows[1]))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_BINDING")

    def test_capture_readback_must_match_original_final_size(self):
        def changed():
            rows = self.frame().captures
            self.mutate(captures=(rows[0]._replace(readback=(7, *rows[0].readback[1:])), rows[1]))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_BINDING")

    def test_final_highwater_bool_is_not_integer(self):
        def changed():
            self.mutate(last=True)
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_FINAL_HIGHWATER")

    def test_final_local_nan_refuses(self):
        def changed():
            self.mutate(local_last=float("nan"))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_FINAL_HIGHWATER")

    def test_phase_chronology_cannot_be_reversed(self):
        def changed():
            phases = self.frame().phases
            self.mutate(phases=(*phases[:-1], phases[-1]._replace(started=50 * NS)))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_PHASE_CHRONOLOGY")

    def test_returned_raw_bytes_cannot_change_before_collection_first_capture(self):
        self.rejected_return(lambda: object.__setattr__(self.returned, "raw", encoded({"nextPhaseAuthority": True})),
                             "BOOTSTRAP_PRODUCER_RESULT_ORIGINALS_CHANGED")

    def test_observation_bytes_cannot_change_before_collection_first_capture(self):
        self.rejected_return(lambda: object.__setattr__(self.returned, "observation_raw", b"CHANGED_OBSERVATION"),
                             "BOOTSTRAP_PRODUCER_RESULT_ORIGINALS_CHANGED")

    def test_canonical_original_bytes_remain_bound(self):
        self.rejected_return(lambda: object.__setattr__(self.returned, "start_raw", b"CHANGED_START"),
                             "BOOTSTRAP_PRODUCER_RESULT_ORIGINALS_CHANGED")

    def test_original_descriptor_request_remains_bound(self):
        self.rejected_facts(lambda: self.mutate(descriptor=encoded({"requestBytes": "CHANGED_REQUEST"})),
                            "BOOTSTRAP_COLLECTION_PRODUCER_REQUEST_CHANGED")

    def test_bound_parent_dictionary_replacement_refuses(self):
        call = self.begin()
        self.parent.__dict__ = dict(self.parent.__dict__)
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_owner_admission_nested_mutation_refuses(self):
        call = self.begin()
        self.parent.owner.admissions["CHANGED"] = [b"not original"]
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_private_producer_frame_replacement_refuses_even_equal(self):
        call = self.begin()
        self.mutate(state="COMPLETE")
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_directory_path_replacement_refuses(self):
        call = self.begin()
        self.directory.path = PurePosixPath("/changed")
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_capture_path_replacement_refuses(self):
        call = self.begin()
        self.streams[0].path = PurePosixPath("/changed")
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_predecessor_graph_nodes_cannot_be_erased(self):
        call = self.begin()
        object.__setattr__(self.predecessor.graph, "nodes", ())
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_sequence_graph_dictionary_cannot_be_replaced(self):
        call = self.begin()
        graph = self.predecessor.frame.graph
        object.__setattr__(graph, "__dict__", dict(graph.__dict__))
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_collection_graph_cannot_erase_its_own_pins(self):
        call = self.begin()
        graph = self.s._collection_origin_frame(call).graph
        object.__setattr__(graph, "nodes", ())
        object.__setattr__(graph, "paths", ())
        self.parent.owner.admissions["CHANGED"] = True
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_bound_query_unknown_refuses_without_finalizer_dispatch(self):
        call = self.begin()
        self.query.unknown = True
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_each_bound_quarantine_refuses(self):
        call = self.begin()
        for values in (self.s.QUARANTINE, self.s.query.QUARANTINE, self.s.diagnostics._QUARANTINE):
            values.append(object())
            with self.assertRaises(Refusal):
                self.s._checked_collection_origin(call)
            values.clear()

    def test_original_result_publication_is_single_use(self):
        call = self.begin()
        frame = self.frame()
        pin = self.s._producer_original_result(self.parent)
        with self.assertRaisesRegex(Refusal, "RESULT_REENTRY"):
            self.mutate(result=self.returned, state="COMPLETE")
        self.assertIs(self.frame(), frame)
        self.assertIs(self.s._producer_original_result(self.parent), pin)
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, frame)

    def test_pre_capture_result_dictionary_replacement_is_not_original(self):
        self.rejected_return(lambda: object.__setattr__(self.returned, "__dict__", dict(self.returned.__dict__)),
                             "BOOTSTRAP_PRODUCER_RESULT_NOT_ORIGINAL")

    def test_result_lookup_function_replacement_refuses(self):
        self.before_return = lambda: setattr(self.s, "_producer_original_result", poison)
        with self.assertRaisesRegex(Refusal, "ORIGINAL_OPERATION_CHANGED") as caught:
            self.begin()
        saved = self.s._collection_origin_frame(caught.exception.bootstrap_collection_origin)
        self.assertIs(saved.returned, self.returned)
        self.assertEqual(saved.state, "FAILED")

    def test_original_result_pin_covers_all_five_fields_and_two_highwaters(self):
        call = self.begin()
        originals = dict(self.returned.__dict__)
        for name in ("raw", "request_raw", "start_raw", "receipt_raw", "observation_raw", "checked_ns", "checked_local"):
            replacement = b"CHANGED" if name.endswith("raw") else originals[name] + 1
            object.__setattr__(self.returned, name, replacement)
            with self.subTest(field=name), self.assertRaisesRegex(Refusal, "RESULT_ORIGINALS_CHANGED"):
                self.s._checked_collection_origin(call)
            object.__setattr__(self.returned, name, originals[name])

    def test_closed_record_can_precede_the_actual_final_highwater(self):
        call = self.begin()
        self.assertLess(json.loads(call.returned.raw)["closedNs"], self.frame().last)
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, self.frame())

    def test_pure_parent_record_disclaimers_and_time_are_cross_checked(self):
        self.begin()
        original = json.loads(self.returned.raw)
        for name, value in (("closedNs", 221 * NS), ("nextPhaseAuthority", True), ("schema", True),
                ("resourceCount", 99), ("outerNativeRetirement", "UNKNOWN")):
            copy_result = copy.copy(self.returned)
            object.__setattr__(copy_result, "raw", encoded({**original, name: value}))
            with self.subTest(field=name), self.assertRaises(Refusal):
                self.s._collection_producer_original_bytes(self.frame(), copy_result)
        self.assertEqual(self.parent.state, "COMPLETE")

    def test_pure_native_record_identity_corruption_refuses(self):
        self.begin()
        frame = self.frame()
        for name in ("birth_raw", "terminal_raw"):
            changed = {**json.loads(getattr(frame.native, name)), "job": "changed-original"}
            supplied = frame._replace(native=frame.native._replace(**{name: encoded(changed)}))
            with self.subTest(record=name), self.assertRaisesRegex(Refusal, "NATIVE_BINDING"):
                self.s._collection_producer_original_bytes(supplied, self.returned)
        self.assertIs(self.frame(), frame)

    def test_query_terminal_fields_remain_passively_bound(self):
        call = self.begin()
        for name, value in (("failed", True), ("active", True), ("first_error", FalseyFailure("model")),
                ("cancellation", KeyboardInterrupt("model")), ("errors", ["model"])):
            old = getattr(self.query, name)
            setattr(self.query, name, value)
            with self.subTest(field=name), self.assertRaises(Refusal):
                self.s._checked_collection_origin(call)
            setattr(self.query, name, old)

    def test_query_deadline_pair_cannot_be_replaced_even_with_equal_values(self):
        self.rejected_facts(lambda: setattr(self.query, "_owner_deadlines", tuple(list(self.query._owner_deadlines))),
                            "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")

    def test_query_path_remains_original(self):
        self.rejected_facts(lambda: setattr(self.query, "path", self.query.path / "changed"),
                            "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_LOCATION_CHANGED")

    def test_query_dictionary_pointer_remains_original(self):
        call = self.begin()
        self.query.__dict__ = dict(self.query.__dict__)
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_child_pid_and_selected_direct_output_facts_remain_original(self):
        call = self.begin()
        child = self.frame().native.child
        for name, value in (("pid", 999), ("stdout", object()), ("stderr", object())):
            old = getattr(child, name)
            setattr(child, name, value)
            with self.subTest(field=name), self.assertRaises(Refusal):
                self.s._checked_collection_origin(call)
            setattr(child, name, old)

    def test_posix_capture_dictionary_and_bounds_are_original(self):
        call = self.begin()
        stream = self.streams[0]
        for name, value in (("maximum", 67174401), ("deadline", 971.0)):
            old = getattr(stream, name)
            setattr(stream, name, value)
            with self.subTest(field=name), self.assertRaises(Refusal):
                self.s._checked_collection_origin(call)
            setattr(stream, name, old)
        stream.__dict__ = dict(stream.__dict__)
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_windows_memory_layout_and_bounds_not_native_windows_execution(self):
        self.role = "windows-x64"
        call = self.begin()
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, self.frame())
        stream = self.streams[0]
        self.assertFalse(hasattr(stream, "maximum"))
        for name, value in (("max_bytes", 67174401), ("_deadline", 971.0)):
            old = getattr(stream, name)
            setattr(stream, name, value)
            with self.subTest(field=name), self.assertRaises(Refusal):
                self.s._checked_collection_origin(call)
            setattr(stream, name, old)

    def test_macos_memory_records_not_native_darwin_execution(self):
        self.role = "macos-arm64"
        call = self.begin()
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, self.frame())
        self.native.home += "/changed"
        with self.assertRaises(Refusal):
            self.s._checked_collection_origin(call)

    def test_original_query_ledger_cannot_be_cleared_before_first_capture(self):
        self.rejected_return(lambda: self.query.resources.clear(), "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_query_ledger_cannot_be_replaced_before_first_capture(self):
        self.rejected_return(lambda: setattr(self.query, "resources", []), "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_one_original_query_row_cannot_disappear_before_first_capture(self):
        self.rejected_return(lambda: self.query.resources.pop(2), "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_query_records_cannot_be_replaced_before_first_capture(self):
        self.rejected_return(lambda: setattr(self.query, "records", list(self.query.records)),
                             "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_query_readback_row_cannot_change_before_first_capture(self):
        self.rejected_return(lambda: self.query.readbacks[0].update(retirement="UNKNOWN"),
                             "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_query_dictionary_cannot_be_replaced_before_first_capture(self):
        self.rejected_return(lambda: setattr(self.query, "__dict__", dict(self.query.__dict__)),
                             "BOOTSTRAP_PRODUCER_RESULT_DICTIONARY_CHANGED")

    def test_original_query_row_owner_cannot_be_replaced_before_first_capture(self):
        self.rejected_return(lambda: self.query.resources[2].update(owner=object()),
                             "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_predecessor_witness_cannot_be_erased_before_first_capture(self):
        self.rejected_return(lambda: object.__setattr__(self.predecessor.graph, "nodes", ()),
                             "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_sequence_path_witness_cannot_be_erased_before_first_capture(self):
        self.rejected_return(lambda: object.__setattr__(self.predecessor.frame.graph, "paths", ()),
                             "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")

    def test_original_sequence_witness_dictionary_cannot_be_replaced_before_first_capture(self):
        self.rejected_return(lambda: object.__setattr__(self.predecessor.frame.graph, "__dict__",
            dict(self.predecessor.frame.graph.__dict__)), "BOOTSTRAP_PRODUCER_RESULT_DICTIONARY_CHANGED")

    def test_original_publication_graph_cannot_erase_its_own_nodes(self):
        def changed():
            pin = self.s._producer_original_result(self.parent)
            object.__setattr__(pin.graph, "nodes", ())
        self.rejected_return(changed, "BOOTSTRAP_PRODUCER_RESULT_GRAPH_CHANGED")

    def test_original_nonempty_query_ledger_and_records_are_retained(self):
        call = self.begin()
        pin = self.s._producer_original_result(self.parent)
        self.assertEqual(len(self.query.resources), 4)
        self.assertTrue(self.query.records and self.query.readbacks and self.predecessor.frame.graph.paths)
        for original in (self.query.__dict__, self.query.resources, self.query.records, self.query.readbacks,
                self.predecessor.graph.__dict__, self.predecessor.frame.graph.__dict__):
            self.assertTrue(any(row[0] is original for row in pin.graph.nodes))
        self.assertFalse(any(row[0] is self.parent for row in pin.records))
        self.assertTrue(any(row[0] is self.parent for row in self.s._collection_origin_frame(call).records))
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, pin.frame)

    def test_missing_mandatory_query_row_is_a_terminal_predicate_not_frame_replacement(self):
        self.rejected_facts(lambda: self.query.resources.pop(), "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_ROSTER")

    def test_query_home_must_be_the_original_closed_row_owner(self):
        self.rejected_facts(lambda: setattr(self.query, "home", object()), "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_ROSTER")

    def test_later_outer_local_sample_may_follow_the_contracted_supplier_pair(self):
        self.before_publication = lambda: self.mutate(query_returned=(True, 120 * NS, 195.0))
        call = self.begin()
        frame = self.frame()
        self.assertLess(self.query._owner_deadlines[1], frame.query_returned[2])
        self.assertLess(frame.query_returned[2], frame.phases[0].local_end)
        self.assertLess(frame.query_returned[1], frame.query[4])
        self.assertIs(self.s._checked_collection_origin(call).producer_frame, frame)

    def test_outer_query_raw_equality_with_original_final_refuses(self):
        def changed():
            row = self.frame().query
            self.mutate(query=(*row[:3], 110 * NS, 120 * NS))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")

    def test_outer_query_local_equality_with_original_work_fence_refuses(self):
        def changed():
            frame = self.frame()
            self.query._owner_deadlines = (110.0, 115.0)
            self.mutate(query=(*frame.query[:2], self.query._owner_deadlines, *frame.query[3:]),
                limits=frame.limits._replace(local_ends=(120.0, *frame.limits.local_ends[1:])),
                phases=(frame.phases[0]._replace(local_end=120.0), *frame.phases[1:]))
        self.rejected_facts(changed, "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")

    def test_original_supplier_failure_never_becomes_success_from_later_outer_sample(self):
        self.rejected_facts(lambda: setattr(self.query, "failed", True), "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")

    def test_scope_string_subclass_refuses_without_custom_equality_dispatch(self):
        equality_calls = []
        class EqualString(str):
            def __eq__(self, other):
                equality_calls.append(other)
                return True
        self.rejected_facts(lambda: setattr(self.native, "job", EqualString(self.native.job)),
                            "BOOTSTRAP_COLLECTION_PRODUCER_SCOPE_CHANGED")
        self.assertEqual(equality_calls, [])

    def test_publication_graph_cap_failure_consumes_publication_and_collection_claims(self):
        self.before_publication = lambda: self.query.records.append([{} for _ in range(10001)])
        with self.assertRaisesRegex(Refusal, "^BOOTSTRAP_COLLECTION_GRAPH_LIMIT$") as caught:
            self.begin()
        saved = self.s._collection_origin_frame(caught.exception.bootstrap_collection_origin)
        self.assertEqual(saved.state, "FAILED")
        self.assertIs(saved.original, caught.exception)
        self.assertIsNone(saved.returned)
        self.assertIsNone(self.frame().result)
        frame = self.frame()
        with self.assertRaisesRegex(Refusal, "^BOOTSTRAP_PRODUCER_RESULT_REENTRY$"):
            self.mutate(result=self.returned, state="COMPLETE")
        with self.assertRaisesRegex(Refusal, "^BOOTSTRAP_COLLECTION_ALREADY_CLAIMED$"):
            self.begin()
        self.assertIs(self.frame(), frame)


if __name__ == "__main__":
    unittest.main()
