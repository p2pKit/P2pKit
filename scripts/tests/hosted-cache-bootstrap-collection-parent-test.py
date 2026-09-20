#!/usr/bin/env python3
"""Focused NEW collection-parent AST/memory controls; NOT native acceptance.

The exact new registry/owner/window/reader/parent/orchestration and the existing
Owner constructor/error and graph engine are selected from source. Closed
producer binding, historical-chain readmission, host/toolchain/domain checks,
native Git, allocation rederivation, inventory grammar and file-copy operation
are explicit models. The new manifest/read/binding/current-membership/query-
return logic runs over memory-only files. No old suite/fixture is imported.
The later original-return publication is an explicit model here; its separate
no-loader-origin controls own that boundary. Historical results for this fixture
are not executions of this later fixture revision or that publication code.

No actual producer, private/native file, Git query, clock, loader, provider,
Gradle, application, network, subprocess, or hosted identity is exercised.
The separately retained outer harness supplies the small execution envelope.
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


def require(value, reason):
    if not value:
        raise Refusal(reason)


def integer(value):
    require(type(value) is int and 0 <= value < 2**64, "MODEL_INTEGER")
    return value


def local(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "MODEL_LOCAL")
    return float(value)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    return json.loads(raw)


def poisoned(*_args, **_kwargs):
    raise AssertionError("NO_OLD_LIVE_METHOD_OR_PRODUCT_SUPPLIER")


def names(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in names(item)]
    return []


def selected(path, keep):
    tree = ast.parse(path.read_text(), filename=str(path))
    nodes = []
    for node in tree.body:
        keys = [node.name] if isinstance(node, (ast.ClassDef, ast.FunctionDef)) else (
            [name for target in node.targets for name in names(target)] if isinstance(node, ast.Assign) else [])
        if keys and any(keep(name) for name in keys):
            nodes.append(node)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                              *nodes], type_ignores=[])
    return compile(ast.fix_missing_locations(module), str(path), "exec")


RUNNER = selected(SCRIPTS / "run-hosted-cache-bootstrap.py", lambda name:
    name.startswith(("_CollectionPhase", "_collection_phase", "_claim_collection_phase", "_update_collection_phase",
                     "_invoke_collection_phase", "_run_collection_phase", "_close_collection_phase")) or
    name in {"CollectionPrefix", "collect_after_entry", "Owner", "_StagingClosedGraph", "NewEntryTransition", "_new_entry_owned"})
LEAF_RECORDS = selected(SCRIPTS / "hosted_cache_bootstrap_collect_files.py", lambda name:
    name in {"FileOriginals", "FileCollectionEvidence", "_Member", "_capture"})
FILE_RECORDS = selected(SCRIPTS / "hosted_dependency_seed_files.py", lambda name: name in {"_identity", "_file_binding"})


@dataclass(frozen=True)
class Clock:
    role: str = "linux-x64"
    domain: str = "MODEL_NOT_OBSERVED"
    frequency: int = NS


@dataclass(frozen=True)
class Reading:
    clock: Clock
    nanoseconds: int


@dataclass(frozen=True)
class Admission:
    record: bytes = b"admitted\n"
    original_event: bytes = b"event\n"
    original_policy: bytes = b"policy\n"
    public_key: bytes = b"PUBLIC_DATA_MODEL_NOT_A_KEY\n"


@dataclass(frozen=True)
class Info:
    identity: tuple
    is_directory: bool
    size: int
    version: int

    def as_dict(self):
        return {"identity": list(self.identity), "directory": self.is_directory, "size": self.size, "version": self.version}


class Node:
    def __init__(self, model, directory, raw=b""):
        model.counter += 1
        self.identity = (1, model.counter)
        self.directory, self.raw, self.children, self.version = directory, raw, {}, 0
        self.unsafe = False

    def info(self):
        require(not self.unsafe, "MODEL_UNSAFE_FILE")
        return Info(self.identity, self.directory, len(self.children) if self.directory else len(self.raw), self.version)


class Handle:
    def __init__(self, model, node, path, maximum=None):
        self.model, self.node, self.path, self.maximum = model, node, path, maximum
        self.identity, self.initial_info = node.identity, node.info()
        self.closed, self.close_calls, self.position, self.close_failure = False, 0, 0, None
        if maximum is not None:
            require(len(node.raw) <= maximum, "MODEL_FILE_TOO_LARGE")

    def verify(self):
        require(not self.closed, "MODEL_CLOSED_HANDLE")
        return self.node.info()

    def read(self, maximum):
        require(not self.closed and type(maximum) is int and maximum > 0, "MODEL_POSITIVE_READ")
        self.model.read_sizes.append(maximum)
        part = self.node.raw[self.position:self.position + maximum]
        self.position += len(part)
        return part

    def write(self, raw):
        require(not self.closed and len(self.node.raw) + len(raw) <= self.maximum, "MODEL_WRITE_LIMIT")
        self.node.raw += raw
        self.node.version += 1
        return len(raw)

    def sync(self):
        self.verify()

    def close(self):
        self.close_calls += 1
        if self.close_failure is not None:
            raise self.close_failure
        require(not self.closed, "MODEL_DUPLICATE_CLOSE")
        self.closed = True

    def names(self, *, max_names, deadline):
        self.model.file_call(deadline)
        self.verify()
        require(len(self.node.children) <= max_names, "MODEL_MEMBER_LIMIT")
        return tuple(sorted(self.node.children))

    def open_directory(self, name, *, deadline):
        self.model.file_call(deadline)
        self.verify()
        child = self.node.children[name]
        require(child.directory, "MODEL_NOT_DIRECTORY")
        return Handle(self.model, child, self.path / name)

    def create_directory(self, name, *, deadline):
        self.model.file_call(deadline)
        self.verify()
        require(name not in self.node.children, "MODEL_EXCLUSIVE_DIRECTORY")
        self.model.mkdir(self.path / name)
        return self.open_directory(name, deadline=deadline)

    def open_file(self, name, *, max_bytes, deadline):
        self.model.file_call(deadline)
        self.verify()
        child = self.node.children[name]
        require(not child.directory, "MODEL_NOT_FILE")
        return Handle(self.model, child, self.path / name, max_bytes)

    def create_file(self, name, *, max_bytes, deadline):
        self.model.file_call(deadline)
        require(name not in self.node.children, "MODEL_EXCLUSIVE_FILE")
        self.model.put(self.path / name, b"")
        return self.open_file(name, max_bytes=max_bytes, deadline=deadline)


class Model:
    """All external authority is modeled; original new-parent code is not."""
    def __init__(self):
        self.raw, self.local, self.clock = 110 * NS, 110.0, Clock()
        self.local_values, self.raw_hook, self.begin_hook, self.leaf_hook = [], None, None, None
        self.query_body_hook, self.query_final_hook, self.query_after_hook = None, None, None
        self.checked_hook, self.reject_binding, self.forbid_files = None, False, False
        self.begin_calls, self.leaf_calls, self.counter, self.file_calls = 0, 0, 10, 0
        self.nodes, self.read_sizes, self.events, self.queries = {}, [], [], []
        self.restore_failure = None
        self.admitted, self.query_reuse = Admission(), None
        self.proposal = {"phaseFencesNs": {name: 1000 * NS for name in
            ("custody-collect", "custody-collect-final", "custody-collect-read")}, "proposedJobEndNs": 1000 * NS}
        namespace = {"__name__": __name__, "namedtuple": namedtuple, "dataclass": dataclass, "field": field,
            "threading": threading, "math": math, "Path": Path, "re": re, "hashlib": hashlib, "require": require,
            "LIMIT": 2097152, "QUARANTINE": [], "ROOT": Path("/source"), "time": Box(monotonic=self.monotonic),
            "I": Box(Admission=Admission), "cancellation": lambda values: require(not values, "MODEL_CANCELLED")}
        self.n = namespace
        unused = "OriginalEntry ClosedEntryTransition _EntryAttempt OriginalPhase _StagingFileOwner _NewEntryWindow _RecipientParent _InitializerParent _RecipientParentWindow _InitializerWindow _RecipientParentBindings _RecipientResource _ParentControl _RecipientPredecessorGraph _InitializerPredecessor _InitializationInputs InitializationPrefix _StagingPhaseParent _StagingWindow _StagingPhaseReturn StagingPrefix ConfigurationCustodyPrefix _StagingFrame _StagingLimits _CustodyRequestPin".split()
        namespace.update({name: type(name, (), {}) for name in unused})
        origin = Box(OriginError=Refusal, NS=NS, integer=integer, encoded=encoded, digest=digest, parse=parse,
            clock_value=lambda clock: {"role": clock.role, "domain": clock.domain, "frequency": clock.frequency},
            Fence=type("UnusedFence", (), {}), require=require)
        origin.clocks = Box(ClockIdentity=Clock, Reading=Reading, checked_now=self.now, observe=lambda: Reading(self.clock, self.raw),
                            validate_reading=self.valid_reading)
        origin.wire = Box(_directed_deadline=lambda start, maximum, end, now: min(start + maximum, start + (end - now) / NS))
        namespace["origin"] = origin
        file_ns = {"require": require, "re": re}
        exec(FILE_RECORDS, file_ns)
        self.files = Box(**{name: file_ns[name] for name in ("_identity", "_file_binding")},
            encoded=encoded, digest=digest, record=parse, PosixInfo=Info, _info_binding=self.binding,
            public_root=lambda path: self.open(path), private_root=lambda path, create=False: self.open(path, create=create))
        namespace["staging"] = Box(files=self.files, _local=local,
            _clock=lambda clock: (clock.role, clock.domain, clock.frequency), _names=self.check_names,
            DIRECTORIES=("session", "state", "gradle-home", "evidence", "cancellations"),
            Originals=type("UnusedOriginals", (), {}), PhaseStart=type("UnusedPhaseStart", (), {}),
            LeafEvidence=type("UnusedLeafEvidence", (), {}))
        namespace["windows"] = Box(FileInfo=type("UnusedWindowsInfo", (), {}))
        namespace["diagnostics"] = Box(_QUARANTINE=[], _exception_detail=lambda error:
            {"retirementUnknown": bool(getattr(error, "retirement_unknown", False)), "code": type(error).__name__})
        namespace["initialization"] = Box(InstalledToolchains=type("UnusedInstalled", (), {}))
        namespace["custody"] = Box(StagedEvidence=type("UnusedStaged", (), {}), ReservationEvidence=type("UnusedReservation", (), {}),
            _Inputs=lambda *_: self.inputs, _sources=lambda *_: self.source_fields, _stage_readback=self.stage_readback)
        namespace["allocation"] = Box(validate_proposal=lambda *_: self.proposal)
        namespace["producer"] = Box(LIMIT=4194304, _uuid=lambda name: name == "a" * 32)
        namespace["directory_identity"] = lambda value, _role: value if self.files._identity(value) else poisoned()
        namespace["_begin_collection_after_entry"] = self.begin
        namespace["_checked_collection_origin"] = self.checked
        namespace["_collection_origin_roots"] = lambda: None
        namespace["load_admission"] = lambda _owner, _directory: self.admitted
        namespace["bootstrap"] = Box(admit=self.admit)
        handlers = {signal.SIGINT: signal.SIG_DFL, signal.SIGTERM: signal.SIG_DFL}
        def install(number, handler):
            if self.restore_failure is not None and handler is signal.SIG_DFL:
                raise self.restore_failure
            old = handlers[number]
            handlers[number] = handler
            return old
        namespace["signal"] = Box(Signals=signal.Signals, SIGINT=signal.SIGINT, SIGTERM=signal.SIGTERM,
            getsignal=lambda number: handlers[number], signal=install)
        self.handlers = handlers
        inventory = Box(_bytes=lambda raw: require(type(raw) is bytes and 0 < len(raw) <= 4194304, "MODEL_METADATA_BYTES"),
                        describe_inventory=poisoned)
        leaf_ns = {"__name__": __name__, "dataclass": dataclass, "field": field, "require": require,
                   "inventory": inventory, "files": self.files}
        exec(LEAF_RECORDS, leaf_ns)
        self.leaf = Box(**{name: leaf_ns[name] for name in ("FileOriginals", "FileCollectionEvidence", "_Member", "_capture")},
            inventory=inventory, _Inputs=self.leaf_inputs, collect_inventory=self.copy_leaf, MAX_BYTES=817889280,
            METADATA=("start.json", "receipt.json", "report-manifest.json"))
        namespace["collect_files"] = self.leaf
        model = self
        class NativeQuery:
            def __new__(cls, *_args, **_kwargs):
                return model.query_reuse if model.query_reuse is not None else super().__new__(cls)

            def __init__(self, root, path, *, check_cancel, owner_deadlines):
                if self is model.query_reuse:
                    return
                self.closed, self.unknown, self.failed, self.active = False, False, False, False
                self.first_error = self.cancellation = None
                self.errors, self.resources, self.finalize_calls = [], [], 0
                self.records, self.readbacks = [], []
                self._owner_deadlines, self.root, self.path = owner_deadlines, root, path
                model.mkdir(path)
                model.mkdir(path / "query-home")
                self.private, self.home = model.open(path), model.open(path / "query-home")
                for label, value in (("private-root", self.private), ("query-home", self.home)):
                    self.resources.append({"label": label, "owner": value, "closeAttempted": False, "closed": False})
                model.put(path / "owner.json", b"MODELED_QUERY_OWNER\n")
                self.owner_record = model.open(path / "owner.json")
                self.owner_record.close()
                self.resources.append({"label": "owner.json", "owner": self.owner_record,
                                       "closeAttempted": True, "closed": True})
                model.queries.append(self)

            def native_host_matches_actions(self):
                model.events.append("MODELED_NATIVE_HOST")

            def retain_admission(self, result):
                for name, raw in (("admission.json", result.record), ("original-event.json", result.original_event),
                        ("original-policy.json", result.original_policy), ("recipient-public.asc", result.public_key)):
                    model.put(self.private.path / name, raw)
                model.put(self.private.path / "session-result.json", encoded({"schema": 1,
                    "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": "b" * 32, "queries": self.records, "readbacks": self.readbacks,
                    "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN", "firstError": None, "errors": []}))

            def _finalize(self, original):
                self.finalize_calls += 1
                if model.query_final_hook:
                    model.query_final_hook(self)
                writer = model.open(self.private.path / "session-result.json") if original is None else object()
                self.resources.append({"label": "session-result.json", "owner": writer,
                                       "closeAttempted": False, "closed": False})
                for row in reversed(self.resources):
                    if not row["closeAttempted"]:
                        row["closeAttempted"] = True
                        if type(row["owner"]) is Handle:
                            row["owner"].close()
                        row["closed"] = True
                self.closed, self.failed, self.first_error = True, original is not None, original
                raw = model.nodes[self.private.path / "session-result.json"].raw if original is None else b"FAILED_MODEL"
                self.readbacks.append({"parent": str(self.path), "name": "session-result.json", "maximum": len(raw),
                                      "retirement": "KNOWN", "result": "RETAINED", "bytes": len(raw)})
                if model.query_after_hook:
                    model.query_after_hook(self)
        namespace["query"] = Box(NativeGitQueries=NativeQuery, QUARANTINE=[])
        exec(RUNNER, namespace)
        namespace["_publish_collection_phase"] = lambda parent, returned: (
            require(parent.result is returned and parent.state == "COMPLETE", "MODEL_COLLECTION_PUBLICATION"),
            self.events.append("MODELED_COLLECTION_PUBLICATION"))
        self.Parent = namespace["_CollectionPhaseParent"]
        # ONLY these explicitly historical/host boundaries are replaced. The
        # new source/state/manifest/query/read/copy-return/close code still runs.
        self.Parent.read_originals = lambda parent: (parent.live(), self.events.append("MODELED_ORIGINAL_CHAIN"))
        self.Parent.host = lambda parent: (parent.live(), self.events.append("MODELED_HOST"))
        self.transition = namespace["NewEntryTransition"](b"entry", Box(admitted=self.admitted), 90 * NS, 95 * NS, 100 * NS)
        self.layout()

    def valid_reading(self, reading):
        require(type(reading) is Reading and type(reading.clock) is Clock and
                reading.clock.role == "linux-x64" and reading.clock.domain == "MODEL_NOT_OBSERVED" and
                reading.clock.frequency == NS, "MODEL_CLOCK_IDENTITY")
        integer(reading.nanoseconds)
        return reading

    def monotonic(self):
        if self.local_values:
            value = self.local_values.pop(0)
            if callable(value):
                return value()
            return value
        return self.local

    def now(self, clock, *, minimum_ns):
        require(clock == self.clock and self.raw >= minimum_ns, "MODEL_RAW_BACKWARDS_OR_DOMAIN")
        result = integer(self.raw)
        if self.raw_hook:
            hook, self.raw_hook = self.raw_hook, None
            hook()
        return result

    def file_call(self, deadline):
        require(not self.forbid_files and self.local < deadline, "MODEL_FILE_PHASE_OR_DEADLINE")
        self.file_calls += 1

    def mkdir(self, path):
        path = Path(path)
        if path not in self.nodes:
            self.nodes[path] = Node(self, True)
            if path != path.parent:
                self.mkdir(path.parent)
                self.nodes[path.parent].children[path.name] = self.nodes[path]
                self.nodes[path.parent].version += 1
        return self.nodes[path]

    def put(self, path, raw):
        path = Path(path)
        self.mkdir(path.parent)
        self.nodes[path] = Node(self, False, raw)
        self.nodes[path.parent].children[path.name] = self.nodes[path]
        self.nodes[path.parent].version += 1
        return self.nodes[path]

    def open(self, path, *, create=False):
        require(not self.forbid_files, "MODEL_FILE_PHASE_OR_DEADLINE")
        path = Path(path)
        if create:
            require(path not in self.nodes, "MODEL_EXCLUSIVE_ROOT")
            self.mkdir(path)
        return Handle(self, self.nodes[path], path)

    @staticmethod
    def binding(info):
        return {"identity": list(info.identity), "stampSha256": digest(encoded(info.as_dict()))}

    def check_names(self, facade, directory, expected):
        require(directory.names(max_names=10000, deadline=facade.end(new=True)) == tuple(sorted(expected)), "MODEL_MEMBERS")

    def stage_readback(self, facade, inputs, container, restore):
        self.check_names(facade, container, ("restore-home", "staging.json"))
        self.check_names(facade, restore, ())

    def layout(self):
        self.session = Path("/private/initializer")
        self.state = self.session / "state"
        self.evidence = self.state / "evidence" / ("a" * 32)
        self.reservation = self.session / "configuration-custody"
        self.retained = self.reservation / "retained"
        for path in (self.state / "gradle-home", self.evidence, self.state / "cancellations", self.retained,
                     self.session / "stage/restore-home", Path("/source/scripts")):
            self.mkdir(path)
        self.put(self.session / "initializer-context.json", b"initializer\n")
        self.put(self.state / "context.json", b"canonical\n")
        self.put(self.state / "gradle.lock", b"lock\n")
        self.put(self.state / "gradle-home/gradle.properties", b"properties\n")
        self.put(self.state / "gradle-home/warmed-not-attested.jar", b"warm\n")
        self.put(self.session / "stage/staging.json", b"staging\n")
        for name in ("hosted_cache_bootstrap_collection.py", "hosted_cache_bootstrap_collect_files.py"):
            self.put(Path("/source/scripts") / name, b"MODELED_SOURCE_CONTENT\n")
        for name, raw in (("start.json", b"start\n"), ("receipt.json", b"receipt\n"), ("report-manifest.json", b"manifest\n"),
                ("product.stdout.log", b"out\n"), ("product.stderr.log", b""), ("stop.stdout.log", b"stop\n"),
                ("stop.stderr.log", b""), ("reports/one/report.txt", b"report\n")):
            self.put(self.evidence / name, raw)
        directories = {"session": self.nodes[self.session].identity, "state": self.nodes[self.state].identity,
                       **{name: self.nodes[self.state / name].identity for name in ("gradle-home", "evidence", "cancellations")}}
        self.inputs = Box(session=self.session, state=self.state, home=self.state / "gradle-home", directories=directories,
            container=self.session / "stage", restore=self.session / "stage/restore-home", canonical={"id": "b" * 32},
            context_raw=b"initializer\n", canonical_raw=b"canonical\n", properties_raw=b"properties\n", admitted=self.admitted,
            staging_raw=b"staging\n")
        self.source_fields = {"inputs": {"main": "model"}, "bootstrapInputs": {"bootstrap": "model"}, "custodyInputs": {"custody": "model"}}
        request = {**self.source_fields, "owner": {"job": "b" * 32, "productInvocation": "a" * 32, "sameHomeStopInvocation": "a" * 32},
            "evidenceDirectory": str(self.evidence), "fileBindings": {
                key: self.binding(self.nodes[path].info()) for key, path in (("initializer-context", self.session / "initializer-context.json"),
                ("canonical-context", self.state / "context.json"), ("properties", self.state / "gradle-home/gradle.properties"))}}
        request_raw = encoded(request)
        request_node = self.put(self.reservation / "request.json", request_raw)
        closed = Box(leaf=Box(request_raw=request_raw), request_pin=Box(path=str(self.reservation),
            directory=self.nodes[self.reservation].identity, retained=self.nodes[self.retained].identity,
            binding_raw=encoded(self.binding(request_node.info()))), staged=None, staged_pin=None)
        original_clock = Box(clock=Clock(), proposal_raw=b"proposal", admitted=self.admitted, responses=(b"attempt", b"jobs"),
                             invocation="c" * 32, runner_name="MODELED_RUNNER_NOT_HOSTED")
        saved = Box(originals=original_clock, original_pin=None, callbacks=(self.callback,))
        predecessor = Box(frame=saved, phases=((Box(), closed),))
        old_dir = self.open(self.evidence)
        old_dir.close()
        old_dir.verify = old_dir.read = old_dir.open_file = old_dir.close = poisoned
        self.old = old_dir
        row = namedtuple("ProducerFileModel", "key directory path identity name maximum raw binding_raw")
        files = tuple(row("canonical-" + name, old_dir, self.evidence, old_dir.identity, name + ".json", 4194304,
                          self.nodes[self.evidence / (name + ".json")].raw,
                          encoded(self.binding(self.nodes[self.evidence / (name + ".json")].info()))) for name in ("start", "receipt"))
        self.original_return = Box(raw=b"closed producer\n", request_raw=encoded({"host": "linux-x64", "evidenceDirectory": str(self.evidence),
            "gradleHome": str(self.state / "gradle-home")}), start_raw=files[0].raw, receipt_raw=files[1].raw,
            checked_ns=100 * NS, checked_local=100.0)
        self.producer_frame = Box(predecessor=predecessor, files=files, native=Box(exit_code=0))
        self.bound_call = Box()
        self.bound = Box(transition=self.transition, graph=Box(nodes=((old_dir, type(old_dir), "opaque", None),)),
            records=(), producer=Box(close=poisoned), returned=self.original_return, producer_frame=self.producer_frame)

    def callback(self):
        if self.checked_hook:
            callback, self.checked_hook = self.checked_hook, None
            callback()

    def begin(self, transition):
        self.begin_calls += 1
        require(transition is self.transition, "MODEL_TRANSITION")
        if self.begin_hook:
            self.begin_hook()
        return self.bound_call

    def checked(self, binding):
        require(binding is self.bound_call and not self.reject_binding, "MODEL_PREDECESSOR_CHANGED")
        return self.bound

    def admit(self, _root, *, query_runner, expected):
        require(expected is self.admitted and query_runner in self.queries, "MODEL_ADMISSION_BINDING")
        if self.query_body_hook:
            self.query_body_hook(query_runner)
        return self.admitted

    def leaf_inputs(self, originals):
        self.leaf._capture(originals)
        tree, members = {}, 0
        bindings = parse(originals.metadata_bindings_raw)
        expected = {}
        for name, raw in (("start.json", originals.start_raw), ("receipt.json", originals.receipt_raw),
                          ("report-manifest.json", originals.manifest_raw)):
            expected[name] = self.leaf._Member(4194304, len(raw), digest(raw), raw, encoded(bindings[name]))
        for name in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            expected[name] = self.leaf._Member(67108864)
        expected["reports/one/report.txt"] = self.leaf._Member(536870912, 7, digest(b"report\n"))
        for name, member in expected.items():
            current = tree
            parts = name.split("/")
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                    members += 1
                current = current[part]
            current[parts[-1]] = member
            members += 1
        return Box(tree=tree, members=members, role="linux-x64", source=self.evidence, target=self.retained,
            identities={"source": originals.evidence_identity, "destination": originals.retained_identity},
            inventory_raw=encoded({"MODEL_INVENTORY_NOT_REAL_GRAMMAR": digest(originals.manifest_raw)}))

    def copy_leaf(self, owner, originals):
        self.leaf_calls += 1
        inputs, rows = self.leaf_inputs(originals), []
        began = self.local
        def walk(tree, prefix=""):
            for name, member in sorted(tree.items()):
                path = prefix + ("/" if prefix else "") + name
                if type(member) is dict:
                    self.mkdir(self.retained / path)
                    walk(member, path)
                else:
                    source = self.nodes[self.evidence / path]
                    target = self.put(self.retained / path, source.raw)
                    rows.append({"path": path, "bytes": len(source.raw), "sha256": digest(source.raw),
                        "sourceBinding": self.binding(source.info()), "destinationBinding": self.binding(target.info())})
        require(not self.nodes[self.retained].children, "MODEL_RETAINED_NOT_EMPTY")
        resource = owner.acquire("bootstrap-collection-root", lambda: self.open(self.retained))
        walk(inputs.tree)
        owner.close_one(resource)
        total = sum(row["bytes"] for row in rows)
        metadata = sum(len(raw) for raw in (originals.start_raw, originals.receipt_raw, originals.manifest_raw))
        self.leaf_value = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_FILE_COPY_LEAF_V1",
            "inventorySha256": digest(inputs.inventory_raw), "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL",
            "collectionState": "COPIED_AND_READ_BACK", "completed": True, "leafHandleClose": "KNOWN",
            "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "noLoaderObservation": "NOT_OBSERVED",
            "dependencyPopulation": "NOT_ATTESTED", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "nextPhaseAuthority": False, "exportSaveAuthority": False, "readBoundary": "POSIX_POSITIVE_READ_EMPTY_AND_SAME_DESCRIPTOR_VERIFY",
            "sourceDirectory": str(self.evidence), "retainedDirectory": str(self.retained),
            "directoryBindings": {key: list(value) for key, value in inputs.identities.items()}, "files": rows,
            "counts": {"sourceReadBytes": 2 * total + metadata, "destinationReadBytes": total,
                       "outputBytesRequested": total, "outputBytesAcknowledged": total,
                       **{key: inputs.members for key in ("sourceMembers", "destinationMembers", "sourceFinalMembers", "destinationFinalMembers")}},
            "localWindow": {"started": began, "end": began + 120, "observed": self.local,
                            "scope": "LOCAL120_SHORTENS_CALLER_NOT_SHARED_CLOCK_OR_JOB_ADMISSION"}}
        result = self.leaf.FileCollectionEvidence(encoded(self.leaf_value), inputs.inventory_raw, began, self.local)
        self.actual_leaf_return = result
        if self.leaf_hook:
            result = self.leaf_hook(owner, originals, result)
        return result

    def claim(self):
        parent = self.n["_claim_collection_phase"](self.transition)
        self.n["_invoke_collection_phase_begin"](parent)
        self.parent = parent
        return parent

    def live(self):
        """Pre-publication facts seam for focused owner/window/file controls."""
        parent = self.claim()
        self.n["_collection_phase_state"](parent, "STARTING")
        first = Reading(self.clock, self.raw)
        limits = self.n["_CollectionPhaseLimits"]((self.clock.role, self.clock.domain, self.clock.frequency),
            self.raw, self.local, (230 * NS, 275 * NS, 305 * NS), (230.0, 275.0, 305.0))
        window = self.n["_CollectionPhaseWindow"](parent)
        self.n["_update_collection_phase"](parent, first=first, limits=limits, window=window, last=self.raw, local_last=self.local,
            phases=(self.n["_CollectionPhaseStep"]("WORK", self.raw, self.local, limits.ends[0], limits.local_ends[0]),))
        parent.window = window
        callback = parent.cancel
        owner = self.n["_CollectionPhaseOwner"](305.0, window, first=first, cancelled=callback)
        self.n["_update_collection_phase"](parent, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end, callback), state="RUNNING")
        parent.owner, parent.state = owner, "RUNNING"
        return parent

    def prepare(self, *, query=True):
        parent = self.live()
        parent.state_readback(after=False)
        initial = parent.handles["initializer"]
        parent.directory("phase", initial.path / "configuration-collection-parent", parent=initial, create=True)
        parent.source_inputs(first=True)
        if query:
            parent.admit()
        return parent

    def copied(self):
        parent = self.prepare()
        originals = parent.manifest()
        self.n["_invoke_collection_phase_leaf"](parent, originals)
        return parent

    def frame(self, parent=None):
        return self.n["_collection_phase_frame"](parent or self.parent)

    def run(self):
        return self.n["collect_after_entry"](self.transition)


class IntentModels(unittest.TestCase):
    def test_new_parent_closes_once_without_reviving_old_methods_or_authority(self):
        m = Model()
        result = m.run()
        self.assertEqual((m.begin_calls, m.leaf_calls), (1, 1))
        value = parse(result.raw)
        self.assertEqual(value["noLoaderObservation"], "NOT_OBSERVED")
        self.assertFalse(value["nextPhaseAuthority"])
        self.assertFalse(value["exportSaveAuthority"])
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(value["window"]["readSlotScope"], "POST_CLOSE_RETURN_OBSERVATIONS_ONLY_NO_FILE_READ_EXECUTION")

    def test_constructor_and_prefix_are_not_claims(self):
        m = Model()
        with self.assertRaisesRegex(Refusal, "NOT_CLAIMED"):
            m.Parent(m.transition).check()
        with self.assertRaisesRegex(Refusal, "TRANSITION_KIND"):
            m.n["collect_after_entry"](m.original_return)
        self.assertEqual(m.begin_calls, 0)

    def test_once_claim_is_consumed_even_when_begin_raises_falsey_failure(self):
        m, error = Model(), FalseyFailure("model original")
        m.begin_hook = lambda: (_ for _ in ()).throw(error)
        with self.assertRaises(FalseyFailure) as raised:
            m.run()
        self.assertIs(raised.exception, error)
        parent = error.bootstrap_collection_parent
        self.assertIsNone(m.frame(parent).binding)
        self.assertIsNone(m.frame(parent).owner)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            m.run()
        self.assertEqual(m.begin_calls, 1)

    def test_actual_begin_return_survives_failed_lookup(self):
        m = Model()
        m.reject_binding = True
        with self.assertRaisesRegex(Refusal, "MODEL_PREDECESSOR_CHANGED") as raised:
            m.run()
        frame = m.frame(raised.exception.bootstrap_collection_parent)
        self.assertIs(frame.binding, m.bound_call)
        self.assertIsNone(frame.owner)

    def test_nested_claim_does_not_hold_lock_or_create_second_producer(self):
        m = Model()
        def reentry():
            with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
                m.run()
        m.begin_hook = reentry
        m.run()
        self.assertEqual(m.begin_calls, 1)

    def test_replaced_begin_binding_is_rejected_before_call(self):
        m = Model()
        m.n["_begin_collection_after_entry"] = poisoned
        with self.assertRaisesRegex(Refusal, "OPERATION_CHANGED"):
            m.run()
        self.assertEqual(m.begin_calls, 0)

    def test_predecessor_callback_drift_stops_new_acquisition(self):
        m = Model()
        parent = m.live()
        m.checked_hook = lambda: setattr(m, "reject_binding", True)
        calls = []
        with self.assertRaisesRegex(Refusal, "MODEL_PREDECESSOR_CHANGED"):
            parent.owner.acquire("reader", lambda: calls.append(True))
        self.assertEqual(calls, [])


class WindowModels(unittest.TestCase):
    def test_work_final_return_caps_do_not_renew(self):
        m = Model()
        result = m.run()
        caps = parse(result.raw)["window"]
        self.assertEqual(caps["globalEndsNs"], {"WORK": 230 * NS, "FINAL": 275 * NS, "READ": 305 * NS})
        self.assertEqual([row["endNs"] for row in caps["phases"]], [230 * NS, 155 * NS, 140 * NS])

    def test_original_cumulative_caps_shorten_every_phase(self):
        m = Model()
        m.proposal["phaseFencesNs"] = dict(zip(("custody-collect", "custody-collect-final", "custody-collect-read"),
                                               (150 * NS, 160 * NS, 170 * NS)))
        self.assertEqual(parse(m.run().raw)["window"]["globalEndsNs"], {"WORK": 150 * NS, "FINAL": 160 * NS, "READ": 170 * NS})

    def test_original_job_end_shortens_not_extends(self):
        m = Model()
        m.proposal["proposedJobEndNs"] = 130 * NS
        self.assertEqual(set(parse(m.run().raw)["window"]["globalEndsNs"].values()), {130 * NS})

    def test_equal_first_cap_expires_without_owner(self):
        m = Model()
        m.proposal["proposedJobEndNs"] = m.raw
        with self.assertRaisesRegex(Refusal, "NO_INTERVAL") as raised:
            m.run()
        self.assertIsNone(m.frame(raised.exception.bootstrap_collection_parent).owner)

    def test_predecessor_final_high_water_is_required(self):
        m = Model()
        m.original_return.checked_ns = 111 * NS
        with self.assertRaisesRegex(Refusal, "PREDECESSOR_CLOCK"):
            m.run()
        self.assertEqual(m.leaf_calls, 0)

    def test_wrong_clock_domain_does_not_create_owner(self):
        m = Model()
        m.clock = Clock(domain="WRONG_MODEL_DOMAIN")
        with self.assertRaisesRegex(Refusal, "MODEL_CLOCK_IDENTITY") as raised:
            m.run()
        self.assertIsNone(m.frame(raised.exception.bootstrap_collection_parent).owner)

    def test_backward_local_clock_is_rejected(self):
        m = Model()
        parent = m.live()
        m.local = 109.0
        with self.assertRaisesRegex(Refusal, "LOCAL_BACKWARDS"):
            parent.window.now()

    def test_backward_raw_clock_is_rejected(self):
        m = Model()
        parent = m.live()
        m.raw = 109 * NS
        with self.assertRaisesRegex(Refusal, "MODEL_RAW_BACKWARDS"):
            parent.window.now()

    def test_valid_raw_survives_following_invalid_local(self):
        m = Model()
        parent = m.live()
        m.raw = 111 * NS
        m.local_values = [110.0, float("nan")]
        with self.assertRaisesRegex(Refusal, "MODEL_LOCAL"):
            parent.window.now()
        self.assertEqual(m.frame().last, 111 * NS)

    def test_returned_raw_stays_with_original_frame_after_alias_mutation(self):
        m = Model()
        parent = m.live()
        m.raw = 112 * NS
        m.raw_hook = lambda: object.__setattr__(parent.window, "call", object())
        with self.assertRaisesRegex(Refusal, "WINDOW_NOT_BOUND"):
            parent.window.now()
        self.assertEqual(m.frame().last, 112 * NS)

    def test_failed_final_start_cannot_be_repaired_by_read_slot(self):
        m = Model()
        parent = m.live()
        m.local = 109.0
        with self.assertRaisesRegex(Refusal, "LOCAL_BACKWARDS"):
            parent.window.advance("FINAL")
        m.local = 111.0
        with self.assertRaisesRegex(Refusal, "PRIOR_START_FAILED"):
            parent.window.advance("READ")
        self.assertEqual(m.frame().phases[-1].end, 0)

    def test_equality_expires_work_and_forbids_acquisition(self):
        m = Model()
        parent = m.live()
        m.raw, m.local = 230 * NS, 230.0
        with self.assertRaisesRegex(Refusal, "EXPIRED"):
            parent.owner.end()


class OwnerModels(unittest.TestCase):
    def test_actual_factory_return_is_retained_before_parent_alias_failure(self):
        m = Model()
        parent = m.live()
        value = m.open(m.evidence)
        def factory():
            parent.owner = object()
            return value
        with self.assertRaisesRegex(Refusal, "PARENT_CHANGED"):
            m.frame().owner.acquire("reader", factory)
        self.assertIs(m.frame().resources[0].value, value)
        m.n["_close_collection_phase"](parent)
        self.assertEqual(value.close_calls, 1)

    def test_duplicate_return_is_not_a_second_close_obligation(self):
        m = Model()
        parent = m.live()
        value = parent.owner.acquire("reader", lambda: m.open(m.evidence))
        with self.assertRaisesRegex(Refusal, "DUPLICATE_RESOURCE"):
            parent.owner.acquire("reader", lambda: value)
        self.assertEqual(len(m.frame().resources), 1)
        m.n["_close_collection_phase"](parent)
        self.assertEqual(value.close_calls, 1)

    def test_old_borrowed_handle_is_not_adopted_or_closed(self):
        m = Model()
        parent = m.live()
        with self.assertRaisesRegex(Refusal, "DUPLICATE_RESOURCE"):
            parent.owner.acquire("reader", lambda: m.old)
        self.assertEqual(m.frame().resources, ())

    def test_forged_close_flag_is_sticky_unknown(self):
        m = Model()
        parent = m.live()
        value = parent.owner.acquire("reader", lambda: m.open(m.evidence))
        parent.owner.resources[0]["closed"] = True
        with self.assertRaisesRegex(Refusal, "ROSTER_CHANGED"):
            parent.check()
        parent.owner.resources[0]["closed"] = False
        self.assertTrue(m.frame().unknown)
        parent.owner.close_one(value)
        self.assertEqual(value.close_calls, 0)

    def test_known_close_happens_once_and_owner_is_not_reopenable(self):
        m = Model()
        parent = m.live()
        owner = parent.owner
        value = owner.acquire("reader", lambda: m.open(m.evidence))
        owner.close_one(value)
        owner.close_one(value)
        m.n["_close_collection_phase"](parent)
        self.assertEqual(value.close_calls, 1)
        with self.assertRaisesRegex(Refusal, "NOT_LIVE"):
            owner.acquire("reader", poisoned)

    def test_falsey_first_survives_failed_close(self):
        m, first, secondary = Model(), FalseyFailure("first"), RuntimeError("close")
        parent = m.live()
        value = parent.owner.acquire("reader", lambda: m.open(m.evidence))
        value.close_failure = secondary
        parent.error("modeled-first", first)
        m.n["_close_collection_phase"](parent)
        self.assertIs(m.frame().original, first)
        self.assertTrue(m.frame().unknown)
        self.assertEqual(value.close_calls, 1)

    def test_fixed_expiry_does_not_exhaust_error_roster_for_known_closes(self):
        m = Model()
        parent = m.live()
        values = [parent.owner.acquire("reader", lambda: m.open(m.evidence)) for _ in range(70)]
        m.raw, m.local = 400 * NS, 400.0
        m.n["_close_collection_phase"](parent)
        self.assertTrue(all(value.close_calls == 1 for value in values))
        self.assertFalse(m.frame().unknown)
        self.assertLess(len(m.frame().errors), 10)

    def test_final_or_unknown_labels_never_invoke_factory(self):
        m = Model()
        parent = m.live()
        for label, final in (("native-scope", False), ("writer", True), ("loader", False)):
            with self.assertRaisesRegex(Refusal, "RESOURCE_LABEL"):
                parent.owner.acquire(label, poisoned, final=final)
        parent.window.advance("FINAL")
        with self.assertRaisesRegex(Refusal, "NOT_LIVE"):
            parent.owner.acquire("reader", poisoned)

    def test_failed_handler_restore_cannot_publish_success(self):
        m, error = Model(), RuntimeError("MODELED_RESTORE_FAILURE")
        m.restore_failure = error
        with self.assertRaises(RuntimeError) as raised:
            m.run()
        self.assertIs(raised.exception, error)
        self.assertEqual(m.frame(error.bootstrap_collection_parent).state, "FAILED")


class ReviewBoundaryModels(unittest.TestCase):
    """R1 reviewer findings: unchanged expected refusals, not native effects."""
    def test_roster_unknown_during_preclose_does_not_dispatch_close(self):
        m = Model()
        parent = m.live()
        value = parent.owner.acquire("reader", lambda: m.open(m.evidence))
        original = m.frame().resources[0]
        def changed():
            m.events.append("PRE_CLOSE_ROSTER_CHANGED")
            original.row["closed"] = True
        m.raw_hook = changed
        parent.owner.close_one(value)
        self.assertIn("PRE_CLOSE_ROSTER_CHANGED", m.events)
        self.assertTrue(m.frame().unknown)
        self.assertIs(m.frame().resources[0].value, value)
        self.assertEqual(value.close_calls, 0)
        self.assertFalse(m.frame().resources[0].attempted)

    def test_owner_unknown_during_preclose_does_not_dispatch_close(self):
        m = Model()
        parent = m.live()
        value = parent.owner.acquire("reader", lambda: m.open(m.evidence))
        m.raw_hook = lambda: setattr(parent.owner, "unknown", True)
        parent.owner.close_one(value)
        self.assertTrue(parent.owner.unknown)
        self.assertEqual(value.close_calls, 0)
        self.assertFalse(m.frame().resources[0].attempted)

    def test_preclose_error_overflow_keeps_original_unattempted_resource(self):
        m, first = Model(), FalseyFailure("FIRST_BEFORE_PRE_CLOSE")
        parent = m.live()
        value = parent.owner.acquire("reader", lambda: m.open(m.evidence))
        for _ in range(64):
            parent.error("MODELED_PRIOR_ERROR", first)
        self.assertFalse(m.frame().unknown)
        m.raw_hook = lambda: (_ for _ in ()).throw(Refusal("PRE_CLOSE_CLOCK_FAILURE"))
        parent.owner.close_one(value)
        self.assertIs(m.frame().original, first)
        self.assertTrue(m.frame().unknown)
        self.assertEqual(value.close_calls, 0)
        self.assertFalse(m.frame().resources[0].attempted)

    def query_refuses(self, mutate):
        m = Model()
        parent = m.prepare(query=False)
        returned = []
        def changed(supplier):
            mutate(supplier)
            returned.append(supplier)
        m.query_after_hook = changed
        with self.assertRaisesRegex(Refusal, "COLLECTION_PHASE_QUERY"):
            parent.admit()
        self.assertEqual(len(returned), 1, "the finalizer actually returned from the injected last boundary")
        frame = m.frame()
        self.assertIs(frame.query[0], returned[0])
        self.assertIs(frame.query_result, m.admitted)
        self.assertTrue(frame.query_returned[0], "post-return validation must not relabel the finalizer as thrown")
        self.assertIsNone(frame.query_pin)
        self.assertEqual(m.leaf_calls, 0)
        return m, parent

    def test_terminal_query_missing_required_root_refuses(self):
        self.query_refuses(lambda supplier: supplier.resources.__setitem__(slice(None),
            [row for row in supplier.resources if row["label"] != "query-home"]))

    def test_terminal_query_duplicate_row_refuses(self):
        self.query_refuses(lambda supplier: supplier.resources.append(supplier.resources[0]))

    def test_terminal_query_unclosed_row_refuses(self):
        self.query_refuses(lambda supplier: supplier.resources[-1].__setitem__("closed", False))

    def test_terminal_query_equal_but_replaced_deadline_pair_refuses(self):
        self.query_refuses(lambda supplier: setattr(supplier, "_owner_deadlines", tuple(list(supplier._owner_deadlines))))

    def test_terminal_query_changed_root_refuses(self):
        self.query_refuses(lambda supplier: setattr(supplier, "root", Path("/foreign-source")))

    def test_terminal_query_changed_location_refuses(self):
        self.query_refuses(lambda supplier: setattr(supplier, "path", Path("/foreign-query")))

    def test_terminal_query_changed_private_root_location_refuses(self):
        self.query_refuses(lambda supplier: setattr(supplier.private, "path", Path("/foreign-private-root")))

    def test_terminal_query_erased_nonrequired_original_row_refuses(self):
        self.query_refuses(lambda supplier: supplier.resources.__setitem__(slice(None),
            [row for row in supplier.resources if row["label"] != "owner.json"]))

    def test_terminal_query_replaced_original_row_refuses(self):
        self.query_refuses(lambda supplier: supplier.resources.__setitem__(2, dict(supplier.resources[2])))


class OriginalModels(unittest.TestCase):
    def test_manifest_reads_above_generic_two_mib_under_exact_four_mib(self):
        m = Model()
        m.nodes[m.evidence / "report-manifest.json"].raw = b"m" * (3 * 1024 * 1024)
        parent = m.prepare()
        originals = parent.manifest()
        self.assertEqual(len(originals.manifest_raw), 3 * 1024 * 1024)
        self.assertLessEqual(max(m.read_sizes), 65536)
        self.assertIn(1, m.read_sizes)

    def test_oversized_manifest_is_refused_before_leaf_or_output(self):
        m = Model()
        parent = m.prepare()
        m.nodes[m.evidence / "report-manifest.json"].raw = b"m" * 4194305
        with self.assertRaisesRegex(Refusal, "MODEL_FILE_TOO_LARGE"):
            parent.manifest()
        self.assertEqual(m.leaf_calls, 0)
        self.assertEqual(m.nodes[m.retained].children, {})

    def test_original_start_inode_is_not_same_byte_rebaselined(self):
        m = Model()
        parent = m.prepare()
        m.put(m.evidence / "start.json", b"start\n")
        with self.assertRaisesRegex(Refusal, "ORIGINAL_FILE_REPLACED"):
            parent.manifest()
        self.assertEqual(m.leaf_calls, 0)

    def test_original_receipt_inode_is_not_same_byte_rebaselined(self):
        m = Model()
        parent = m.prepare()
        m.put(m.evidence / "receipt.json", b"receipt\n")
        with self.assertRaisesRegex(Refusal, "ORIGINAL_FILE_REPLACED"):
            parent.manifest()

    def test_first_manifest_binding_is_retained_and_reread(self):
        m = Model()
        parent = m.prepare()
        original = parent.manifest()
        pin = m.frame().manifest_pin
        self.assertEqual(parse(original.metadata_bindings_raw)["report-manifest.json"], parse(pin[4]))
        m.put(m.evidence / "report-manifest.json", original.manifest_raw)
        with self.assertRaisesRegex(Refusal, "ORIGINAL_FILE_REPLACED"):
            parent.reread()
        self.assertEqual(m.frame().manifest_pin, pin)

    def test_manifest_attempt_cannot_repeat(self):
        m = Model()
        parent = m.prepare()
        parent.manifest()
        with self.assertRaisesRegex(Refusal, "MANIFEST_REENTRY"):
            parent.manifest()

    def test_warmed_home_empty_before_and_nonempty_after_copy_have_distinct_oracles(self):
        m = Model()
        parent = m.copied()
        parent.state_readback(after=True)
        self.assertIn("warmed-not-attested.jar", m.nodes[m.state / "gradle-home"].children)
        self.assertTrue(m.nodes[m.retained].children)
        with self.assertRaisesRegex(Refusal, "STATE_ORDER"):
            parent.state_readback(after=False)

    def test_extra_empty_directory_after_copy_is_not_accepted(self):
        m = Model()
        parent = m.copied()
        m.mkdir(m.retained / "extra")
        with self.assertRaisesRegex(Refusal, "CURRENT_MEMBERS"):
            parent.state_readback(after=True)

    def test_replaced_copied_file_binding_is_not_accepted(self):
        m = Model()
        parent = m.copied()
        m.put(m.retained / "start.json", b"start\n")
        with self.assertRaisesRegex(Refusal, "CURRENT_FILE_CHANGED"):
            parent.current_membership()

    def test_new_unsafe_descendant_observation_is_refused(self):
        m = Model()
        parent = m.copied()
        m.nodes[m.retained / "reports/one"].unsafe = True
        with self.assertRaisesRegex(Refusal, "MODEL_UNSAFE_FILE"):
            parent.current_membership()

    def test_same_byte_extra_source_inode_replacement_after_query_is_rejected(self):
        m = Model()
        parent = m.prepare()
        path = Path("/source/scripts/hosted_cache_bootstrap_collection.py")
        m.put(path, m.nodes[path].raw)
        with self.assertRaisesRegex(Refusal, "SOURCE_CHANGED"):
            parent.source_inputs()


class QueryModels(unittest.TestCase):
    def test_new_supplier_actual_closed_return_is_required(self):
        m = Model()
        parent = m.prepare()
        frame = m.frame()
        self.assertIs(frame.query_result, m.admitted)
        self.assertTrue(frame.query_returned[0])
        self.assertIsNotNone(frame.query_pin)
        self.assertEqual(m.queries[0].finalize_calls, 1)
        self.assertEqual(frame.query[2], (185.0, 230.0))
        parent.check()

    def test_provisional_success_does_not_replace_failed_finalizer(self):
        m, error = Model(), RuntimeError("MODEL_FINALIZER_FAILURE")
        m.query_final_hook = lambda _supplier: (_ for _ in ()).throw(error)
        with self.assertRaises(RuntimeError) as raised:
            m.run()
        frame = m.frame(error.bootstrap_collection_parent)
        self.assertIs(raised.exception, error)
        self.assertFalse(frame.query_returned[0])
        self.assertIs(frame.query_result, m.admitted)
        self.assertEqual(m.leaf_calls, 0)

    def test_late_finalizer_return_is_not_productive_time(self):
        m = Model()
        def late(_supplier):
            m.raw, m.local = 230 * NS, 230.0
        m.query_after_hook = late
        with self.assertRaisesRegex(Refusal, "EXPIRED") as raised:
            m.run()
        self.assertTrue(m.frame(raised.exception.bootstrap_collection_parent).query_returned[0])
        self.assertEqual(m.leaf_calls, 0)

    def test_unknown_finalizer_cannot_publish_collection(self):
        m = Model()
        m.query_final_hook = lambda supplier: setattr(supplier, "unknown", True)
        with self.assertRaises(Refusal) as raised:
            m.run()
        self.assertTrue(m.frame(raised.exception.bootstrap_collection_parent).unknown)
        self.assertEqual(m.leaf_calls, 0)

    def test_falsey_body_error_and_secondary_finalizer_are_both_retained(self):
        m, first, secondary = Model(), FalseyFailure("body"), RuntimeError("final")
        m.query_body_hook = lambda _supplier: (_ for _ in ()).throw(first)
        m.query_final_hook = lambda _supplier: (_ for _ in ()).throw(secondary)
        with self.assertRaises(FalseyFailure) as raised:
            m.run()
        frame = m.frame(first.bootstrap_collection_parent)
        self.assertIs(raised.exception, first)
        self.assertEqual(frame.query_errors[:2], (("body", first), ("final", secondary)))

    def test_changed_actual_admission_return_is_rejected_after_close(self):
        m = Model()
        parent = m.prepare()
        object.__setattr__(m.admitted, "original_policy", b"replaced policy")
        with self.assertRaisesRegex(Refusal, "CLOSED_GRAPH_CHANGED"):
            parent.check()


class QueryCustodyModels(unittest.TestCase):
    def test_pre_final_replaced_list_retains_original_and_never_calls_finalizer(self):
        m = Model()
        parent = m.prepare(query=False)
        originals = []
        def replaced(supplier):
            originals.append(supplier.resources)
            supplier.resources = list(supplier.resources)
        m.query_body_hook = replaced
        with self.assertRaisesRegex(Refusal, "QUERY_ORIGIN_CHANGED"):
            parent.admit()
        frame = m.frame()
        self.assertIs(frame.query_origin.resources, originals[0])
        self.assertIsNone(frame.query_returned)
        self.assertFalse(frame.query_final_attempted)
        self.assertEqual(m.queries[0].finalize_calls, 0)
        self.assertTrue(frame.unknown)
        self.assertIn(m.queries[0], m.n["query"].QUARANTINE)

    def test_pre_final_invalid_flag_keeps_row_value_before_validation(self):
        m = Model()
        parent = m.prepare(query=False)
        m.query_body_hook = lambda supplier: supplier.resources[0].__setitem__("closed", True)
        with self.assertRaisesRegex(Refusal, "QUERY_ROSTER"):
            parent.admit()
        frame = m.frame()
        self.assertIs(frame.query_preclose.rows[0].value, m.queries[0].private)
        self.assertFalse(frame.query_final_attempted)
        self.assertIsNone(frame.query_returned)
        self.assertEqual(m.queries[0].finalize_calls, 0)

    def terminal_refuses(self, changed, reason, *, body=None):
        m = Model()
        parent = m.prepare(query=False)
        m.query_body_hook, m.query_after_hook = body, changed
        with self.assertRaisesRegex(Refusal, reason):
            parent.admit()
        frame = m.frame()
        self.assertTrue(frame.query_final_attempted)
        self.assertTrue(frame.query_returned[0])
        self.assertTrue(frame.unknown)
        self.assertIsNone(frame.query_pin)
        self.assertIn(m.queries[0], m.n["query"].QUARANTINE)
        return m, frame

    def test_nonrequired_original_owner_reference_survives_erasure(self):
        def erase(supplier):
            supplier.resources[:] = [row for row in supplier.resources if row["label"] != "owner.json"]
        m, frame = self.terminal_refuses(erase, "QUERY_FINAL_ROSTER")
        self.assertIs(frame.query_preclose.rows[2].value, m.queries[0].owner_record)
        self.assertTrue(frame.query_preclose.rows[2].closed)

    def test_unexpected_success_finalizer_addition_is_not_adopted(self):
        self.terminal_refuses(lambda supplier: supplier.resources.append(
            {"label": "unexpected", "owner": object(), "closeAttempted": True, "closed": True}), "QUERY_FINAL_ROSTER")

    def test_missing_final_receipt_readback_is_not_fabricated(self):
        self.terminal_refuses(lambda supplier: supplier.readbacks.clear(), "QUERY_READBACK_ROSTER")

    def test_boolean_tail_byte_count_is_not_an_integer_receipt(self):
        self.terminal_refuses(lambda supplier: supplier.readbacks[-1].__setitem__("bytes", True), "QUERY_FINAL_READBACK")

    def test_original_query_record_mutation_during_finalizer_refuses(self):
        self.terminal_refuses(lambda supplier: supplier.records[0]["nested"].append("changed"), "CLOSED_GRAPH_CHANGED",
            body=lambda supplier: supplier.records.append({"nested": ["original"]}))

    def test_original_readback_mutation_during_finalizer_refuses(self):
        self.terminal_refuses(lambda supplier: supplier.readbacks[0].__setitem__("original", False), "CLOSED_GRAPH_CHANGED",
            body=lambda supplier: supplier.readbacks.append({"original": True}))

    def test_exact_original_query_and_readback_records_survive_known_finalizer(self):
        m = Model()
        def originals(supplier):
            supplier.records.append({"MODELED_NOT_NATIVE_QUERY": ["original"]})
            supplier.readbacks.append({"MODELED_NOT_ACTUAL_READBACK": True})
        m.query_body_hook = originals
        parent = m.prepare()
        self.assertIs(m.frame().query_preclose.readbacks[0], m.queries[0].readbacks[0])
        self.assertEqual(parse(parent.records["admission/session-result.json"])["queries"], m.queries[0].records)
        parent.check()


class ReaderModels(unittest.TestCase):
    @staticmethod
    def reader():
        m = Model()
        parent = m.live()
        first, fence = object(), Box(now=poisoned, close=poisoned)
        parent.transition._attempt.transition = Box(_fence=fence, _limits=(*range(8), first))
        m.n["history"] = Box(snapshot=lambda supplied: "HISTORY_MODEL" if supplied is fence else poisoned(), checked=lambda value: value)
        return m, parent, m.n["_CollectionPhaseReader"](parent)

    def test_reader_uses_new_owner_clock_not_old_live_methods(self):
        m, parent, reader = self.reader()
        m.raw = 111 * NS
        self.assertIs(reader.owner, parent.owner)
        self.assertIs(reader.current, parent.window)
        self.assertEqual(reader.observe(final=False, minimum=110 * NS), 111 * NS)

    def test_reader_retarget_is_refused_before_other_parent_method(self):
        m, parent, reader = self.reader()
        other = m.Parent(m.transition)
        other.check = poisoned
        object.__setattr__(reader, "call", other)
        with self.assertRaisesRegex(Refusal, "READER_CHANGED"):
            reader.checked()
        self.assertFalse(m.frame().unknown)

    def test_reader_historical_view_cannot_be_replaced(self):
        _m, _parent, reader = self.reader()
        object.__setattr__(reader, "past", "REPLACED")
        with self.assertRaisesRegex(Refusal, "READER_CHANGED"):
            reader.checked()

    def test_reader_never_opens_file_work_in_final_slot(self):
        _m, parent, reader = self.reader()
        parent.window.advance("FINAL")
        with self.assertRaisesRegex(Refusal, "NOT_LIVE"):
            reader.observe(final=True, minimum=110 * NS)


class LeafReturnModels(unittest.TestCase):
    def test_leaf_once_and_exact_actual_return_are_retained(self):
        m = Model()
        parent = m.copied()
        self.assertIs(m.frame().leaf, m.actual_leaf_return)
        with self.assertRaisesRegex(Refusal, "LEAF_REENTRY"):
            m.n["_invoke_collection_phase_leaf"](parent, m.frame().leaf_originals)
        self.assertEqual(m.leaf_calls, 1)

    def test_wrong_return_kind_is_retained_before_validation(self):
        m, returned = Model(), object()
        m.leaf_hook = lambda *_: returned
        with self.assertRaisesRegex(Refusal, "LEAF_KIND") as raised:
            m.run()
        self.assertIs(m.frame(raised.exception.bootstrap_collection_parent).leaf, returned)

    def test_return_bytes_mutation_at_post_return_callback_is_rejected(self):
        m = Model()
        def alter(_owner, _originals, returned):
            m.checked_hook = lambda: object.__setattr__(returned, "raw", b"changed")
            return returned
        m.leaf_hook = alter
        with self.assertRaisesRegex(Refusal, "LEAF_RETURN_CHANGED") as raised:
            m.run()
        self.assertIs(m.frame(raised.exception.bootstrap_collection_parent).leaf, m.actual_leaf_return)

    def test_oversized_return_is_retained_without_parent_success(self):
        m = Model()
        def oversize(_owner, _originals, returned):
            object.__setattr__(returned, "raw", b"x" * 4194305)
            return returned
        m.leaf_hook = oversize
        with self.assertRaisesRegex(Refusal, "LEAF_BYTES") as raised:
            m.run()
        self.assertIs(m.frame(raised.exception.bootstrap_collection_parent).leaf, m.actual_leaf_return)

    def test_late_leaf_zero_like_success_does_not_repair_expired_work(self):
        m = Model()
        def late(_owner, _originals, returned):
            m.raw, m.local = 230 * NS, 230.0
            return returned
        m.leaf_hook = late
        with self.assertRaisesRegex(Refusal, "EXPIRED") as raised:
            m.run()
        self.assertIs(m.frame(raised.exception.bootstrap_collection_parent).leaf, m.actual_leaf_return)

    def test_no_loader_and_export_authority_cannot_be_fabricated_in_return(self):
        for key, value in (("noLoaderObservation", "ABSENT"), ("exportSaveAuthority", True), ("completed", 1)):
            with self.subTest(key=key):
                m = Model()
                def malformed(_owner, _originals, returned):
                    m.leaf_value[key] = value
                    object.__setattr__(returned, "raw", encoded(m.leaf_value))
                    return returned
                m.leaf_hook = malformed
                with self.assertRaisesRegex(Refusal, "LEAF_RECORD"):
                    m.run()

    def test_metadata_binding_cannot_be_substituted_in_leaf_return(self):
        m = Model()
        def malformed(_owner, _originals, returned):
            row = next(row for row in m.leaf_value["files"] if row["path"] == "start.json")
            row["sourceBinding"]["identity"][1] += 10000
            object.__setattr__(returned, "raw", encoded(m.leaf_value))
            return returned
        m.leaf_hook = malformed
        with self.assertRaisesRegex(Refusal, "ORIGINAL_METADATA_BINDING"):
            m.run()

    def test_postclose_return_uses_no_file_or_copy_operation(self):
        m = Model()
        original_close = m.n["_close_collection_phase"]
        def close(parent):
            original_close(parent)
            m.forbid_files = True
        m.n["_close_collection_phase"] = close
        result = m.run()
        self.assertEqual(m.leaf_calls, 1)
        self.assertEqual(parse(result.raw)["parentResourceClose"], "KNOWN_RESOURCE_CLOSE_ONLY")


if __name__ == "__main__":
    unittest.main()
