#!/usr/bin/env python3
"""NEW confined custody-owner/caller controls; authored, not execution evidence.

Import the maintained driver through the PRIMARY suite's fixture module solely
to reuse SuppliedHistory's public-policy/match byte grammar. No old TestCase is
instantiated, enumerated or run. There is no private-fragment fallback. The
fixture's offline audit hook refuses processes, network and native libraries.

Actual custody owner, original Window/child clock, metadata owner, source-query
and finalizer coordinators, phase-limit hooks, typed match pins, phase/readback,
complete index and same-process return accessors are exercised. Files/directories,
Git/query/resolver/host/Step returns, RAW/LOCAL/boot/wall observations and HTTP/native
phase production are explicitly supplied models. Buffered metadata readers are
real Python memory streams, not OS files. No fake GITHUB identity is installed in
the environment. Supplied native records are grammar, never producer/retirement
evidence. Original PRIMARY execution, old reader/native12/clock36 tests are not
replayed. Full native.phase is used only by the NEW setup/finally hook controls,
with refusal suppliers before process creation. There are no private originals,
builds, downloads, genuine authority, credentials or provider/hosted qualification.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("custody_authority_supplied_fixture_dependency",
    ROOT / "scripts/tests/hosted-initial-recipient-custody-primary-test.py")
FIXTURES = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = FIXTURES
_spec.loader.exec_module(FIXTURES)
D = FIXTURES.D
NS, BOOT = FIXTURES.NS, FIXTURES.BOOT
wire, sha = FIXTURES.wire, FIXTURES.sha
TOKEN = "SUPPLIED_OFFLINE_AUTHORITY_NOT_A_CREDENTIAL"
START = 1100 * NS


def model_require(value, reason):
    if not value:
        raise AssertionError("SUPPLIED_MODEL_" + reason)


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class Resource:
    """Counter-only close, not a native handle or ownership receipt."""
    def __init__(self, name="resource", *, close_error=None, close_hook=None):
        self.name, self.close_error, self.close_hook = name, close_error, close_hook
        self.close_calls, self.closed = 0, False

    def close(self):
        self.close_calls += 1
        if self.close_hook is not None:
            self.close_hook()
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class Clock:
    def __init__(self):
        self.identity = FIXTURES.reading().clock
        self.raw, self.local = START, 100.0
        self.callback = lambda: None
        self.observations, self.cancellations = [], 0

    def advance(self, seconds):
        self.raw, self.local = START + seconds * NS, 100.0 + seconds

    def checked(self, expected, *, minimum_ns=0):
        self.observations.append((expected, minimum_ns, self.raw))
        model_require(expected == self.identity and minimum_ns <= self.raw, "ORIGINAL_CLOCK_FRONTIER")
        return self.raw

    def reading(self):
        return D.O.clocks.Reading(self.identity, self.raw)

    def cancelled(self):
        self.cancellations += 1
        self.callback()


class Harness:
    """Fresh test registries, never restored historical production ownership."""
    def __init__(self):
        self.clock, self.stack = Clock(), ExitStack()

    def __enter__(self):
        for module, name in ((D, "_WINDOWS"), (D, "_PRIMARY_OWNERS"), (D, "_CUSTODY_OWNERS"),
                (D, "_CUSTODY_CHILD_CLOCKS"), (D, "_AUTHORITY_ATTEMPTS"), (D, "_AUTHORITY_RETURNS")):
            self.stack.enter_context(patch.object(module, name, {}))
        for module, name in ((D, "_PRIMARY_QUARANTINE"), (D.native, "QUARANTINE"),
                (D.Q, "QUARANTINE"), (D.native.diagnostics, "_QUARANTINE")):
            self.stack.enter_context(patch.object(module, name, []))
        self.stack.enter_context(patch.object(D.time, "monotonic", lambda: self.clock.local))
        self.stack.enter_context(patch.object(D.O.clocks, "checked_now", self.clock.checked))
        self.stack.enter_context(patch.object(D.O.clocks, "observe", self.clock.reading))
        self.stack.enter_context(patch.object(D.C, "boot_digest", lambda _role: BOOT))
        self.stack.enter_context(patch.dict(D.os.environ, {}, clear=True))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def window(self, kind="gate", *, basis=1050 * NS):
        first = self.clock.reading()
        limits = D.schedule(kind, basis, first.nanoseconds)
        return D.Window(first, self.clock.local, BOOT, limits, self.clock.cancelled)

    def owner(self, window=None):
        window = self.window() if window is None else window
        first = window._view().binding[0]
        local_end = window._view().binding[5][1]
        return D._CustodyOwner(local_end, window, first=first, cancelled=window._view().binding[6])


@dataclass(frozen=True)
class FileInfo:
    identity: tuple
    size: int


class MemoryFiles:
    """Supplied POSIX-shaped filesystem; no mkdir/open/fd/OS close occurs."""
    def __init__(self, rig):
        self.rig, self.directories, self.files, self.file_ids = rig, {}, {}, {}
        self.handles, self.readers, self.writers = [], [], []
        self.open_hook = self.read_hook = self.close_hook = None
        fs = self

        class Directory:
            def __init__(self, path):
                self.path = path
                model_require(type(path) is type(ROOT) and path in fs.directories, "EXISTING_DIRECTORY")
                self.identity, self.closed, self.close_calls = fs.directories[path], False, 0
                fs.handles.append(self)
                if fs.open_hook is not None:
                    fs.open_hook(self)

            def verify(self):
                model_require(not self.closed and fs.directories.get(self.path) == self.identity,
                    "ORIGINAL_DIRECTORY")

            def create_directory(self, name, *, deadline):
                self.verify()
                fs.deadline(deadline)
                D.Q._component(name)
                path = self.path / name
                model_require(path not in fs.directories and path not in fs.files, "EXCLUSIVE_DIRECTORY")
                fs.add_directory(path)
                return Directory(path)

            def create_file(self, name, *, max_bytes, deadline):
                self.verify()
                fs.deadline(deadline)
                D.Q._component(name)
                return Writer(self, name, max_bytes, deadline)

            def read_bytes(self, name, *, max_bytes, deadline):
                self.verify()
                fs.deadline(deadline)
                path = self.path / D.Q._component(name)
                raw = fs.files[path]
                model_require(type(raw) is bytes and len(raw) <= max_bytes, "READ_LIMIT")
                if fs.read_hook is not None:
                    fs.read_hook(self, name, raw)
                self.verify()
                return raw

            def close(self):
                self.close_calls += 1
                model_require(not self.closed, "DIRECTORY_CLOSE_ONCE")
                if fs.close_hook is not None:
                    fs.close_hook(self)
                self.closed = True

        class Writer:
            def __init__(self, parent, name, maximum, deadline):
                self.parent, self.path = parent, parent.path / name
                self.maximum, self.deadline = maximum, deadline
                self.closed, self.close_calls = False, 0
                model_require(self.path not in fs.files, "EXCLUSIVE_FILE")
                fs.put(self.path, b"")
                fs.writers.append(self)

            def verify(self):
                model_require(not self.closed, "WRITER_LIVE")
                self.parent.verify()
                fs.deadline(self.deadline)
                raw = fs.files[self.path]
                model_require(len(raw) <= self.maximum, "WRITE_LIMIT")
                return FileInfo(fs.file_ids[self.path], len(raw))

            def write(self, raw):
                self.verify()
                model_require(type(raw) is bytes and len(fs.files[self.path]) + len(raw) <= self.maximum,
                    "BOUNDED_WRITE")
                fs.put(self.path, fs.files[self.path] + raw)
                return len(raw)

            def sync(self):
                self.verify()

            def close(self):
                self.close_calls += 1
                model_require(not self.closed, "WRITER_CLOSE_ONCE")
                self.closed = True

        self.Directory, self.Writer = Directory, Writer

    def deadline(self, end):
        model_require(type(end) in (int, float) and self.rig.clock.local < end, "FINITE_ORIGINAL_LOCAL")

    def add_directory(self, path):
        if path not in self.directories:
            self.directories[path] = (17, len(self.directories) + 100)
        return self.directories[path]

    def put(self, path, raw):
        model_require(type(raw) is bytes and path.parent in self.directories, "DECLARED_FILE_PARENT")
        self.file_ids.setdefault(path, (17, 10000 + len(self.file_ids)))
        self.files[path] = raw

    def stream(self, path, flags, mode):
        model_require(flags == D.os.O_RDONLY | D.os.O_NOFOLLOW and mode == "rb", "METADATA_READ_ONLY")
        reader = io.BufferedReader(io.BytesIO(self.files[path]))
        self.readers.append((path, reader))
        return reader

    def file_info(self, path, reader, maximum):
        model_require(type(reader) is io.BufferedReader and not reader.closed and
            len(self.files[path]) <= maximum, "ORIGINAL_METADATA_READER")
        return FileInfo(self.file_ids[path], len(self.files[path]))

    def names(self, owner, directory):
        owner.end()
        directory.verify()
        return tuple(sorted(path.name for path in (*self.directories, *self.files) if path.parent == directory.path))

    def install(self):
        for module, name, value in ((D.Q, "_PosixDirectory", self.Directory),
                (D.Q, "_posix_stream", self.stream), (D.Q, "_file_info", self.file_info),
                (D.native, "_initializer_names", self.names)):
            self.rig.stack.enter_context(patch.object(module, name, value))


class QuerySupplier:
    """Explicit complete query DECLARATIONS and finalization effects, not Git.

    NativeGitQueries._finalize is the actual coordinator; its admission/close
    suppliers below are counter-only models. Query outputs are deliberately
    synthetic bytes even where the surrounding index grammar is genuine.
    """
    def __init__(self, rig, path, *, acquisition=False):
        self.rig, self.path, self.acquisition = rig, path, acquisition
        self.unknown, self.closed, self.first_error = False, False, None
        self.finalizers, self.close_calls, self.admission_errors = [], 0, []
        self.close_error = None
        fs = rig.fs
        fs.add_directory(path)
        fs.add_directory(path / "query-home")
        self.private = fs.Directory(path)
        self.job = ("a" if acquisition else "b" if path.name == "source-before" else "c") * 32
        self.queries, self.declarations = [], [(path, "owner.json", None)]
        fs.put(path / "owner.json", wire({"scope": "SUPPLIED_QUERY_OWNER_NOT_NATIVE_PROOF"}))
        if acquisition:
            self.declarations.append((path, "event.bin", None))
        commands = rig.source_commands()
        for number in range(24 if acquisition else 12):
            identifier = format(number + 1, "032x")
            target = path / ("query-" + identifier)
            fs.add_directory(target)
            stdout = D.I.EVENT_LIMIT if number % 12 == 1 else D.I.POLICY_LIMIT if number % 12 == 11 else 4096
            row = {"id": identifier, "stdoutLimit": stdout, "stderrLimit": 4096, "job": self.job,
                "state": str(path), "home": str(path / "query-home"), "cwd": str(ROOT),
                "argv": [rig.git, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                    "-C", str(ROOT), *commands[number % 12]],
                "launchAttempted": True, "scopeAttempted": True, "waitExitCode": 0,
                "retirement": "KNOWN", "result": "READY_FOR_CALLER_SEAL", "errors": [], "ownedSurvivors": []}
            self.queries.append(row)
            for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"):
                raw = b"" if name.endswith(".log") else wire({"scope": "SUPPLIED_QUERY_DECLARATION_ONLY", "id": identifier})
                fs.put(target / name, raw)
                limit = row[name[:-4] + "Limit"] if name.endswith(".log") else None
                self.declarations.append((target, name, limit))
            if acquisition and number == 11:
                self.declarations.extend((path, name + ".bin", None) for name in (*D.N.SOURCE_KEYS, *D.N.HTTP_KEYS))
        self.declarations.extend((path, name + ".bin", None)
            for name in (("observation", "match") if acquisition else D.N.SOURCE_KEYS))

    def __call__(self, **_kwargs):
        raise AssertionError("SUPPLIED_QUERY_MODEL_MUST_NOT_EXECUTE_GIT")

    def native_host_matches_actions(self):
        self.rig.events.append(("supplied-query-host", self.path.name))

    def _write(self, parent, name, value):
        model_require(parent is self.private, "SAME_QUERY_PRIVATE")
        raw = value if type(value) is bytes else wire(value)
        self.rig.fs.put(self.path / name, raw)
        return raw

    def record_admission_failure(self, error):
        self.admission_errors.append(error)
        if self.first_error is None:
            self.first_error = error

    def _error(self, _row, _stage, error):
        if self.first_error is None:
            self.first_error = error

    def close(self):
        self.close_calls += 1
        model_require(not self.closed, "QUERY_CLOSE_ONCE")
        self.closed = True
        if self.close_error is not None:
            self.unknown = True
            raise self.close_error
        if self.first_error is not None:
            self.unknown = True
            return
        if self.acquisition:
            self.rig.clock.advance(15)
        fs = self.rig.fs
        readbacks = []
        for parent, name, limit in self.declarations:
            raw = fs.files[parent / name]
            readbacks.append({"parent": str(parent), "name": name,
                "maximum": max(1, len(raw)) if limit is None else limit, "bytes": len(raw), "sha256": sha(raw),
                "retirement": "KNOWN", "result": "RETAINED"})
        session = {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
            "job": self.job, "queries": self.queries, "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN",
            "firstError": None, "errors": [], "readbacks": readbacks}
        if self.rig.session_change is not None:
            self.rig.session_change(self, session)
        self._write(self.private, "session-result.json", session)
        self.private.close()

    def _finalize(self, original):
        self.finalizers.append(original)
        return D.Q.NativeGitQueries._finalize(self, original)


class OwnerControls(unittest.TestCase):
    def test_actual_acquire_retains_original_before_post_return_row_erasure(self):
        with Harness() as rig:
            owner, resource = rig.owner(), Resource("custody-parent-root")
            def erase():
                if owner.resources:
                    owner.resources.clear()
            rig.clock.callback = erase
            with self.assertRaises(Exception) as caught:
                owner.acquire("directory", lambda: resource)
            anchor = owner._anchor()
            self.assertIs(anchor.failure, caught.exception)
            self.assertIs(owner.original, caught.exception)
            self.assertIs(anchor.rows[0][2], resource)
            self.assertEqual(anchor.rows[0][3:], (False, False))
            self.assertEqual(owner.resources, [])
            self.assertEqual(resource.close_calls, 0)
            self.assertTrue(anchor.unknown)
            self.assertIn(owner, D.native.QUARANTINE)
            for operation in (owner.close, owner.freeze, owner.known):
                with self.assertRaises(Exception):
                    operation()
            self.assertEqual(resource.close_calls, 0)

    def test_factory_mutation_retains_actual_pending_return_without_reconstruction(self):
        with Harness() as rig:
            owner, resource = rig.owner(), Resource()
            original_dictionary = owner.__dict__
            def allocate():
                owner.__dict__ = dict(owner.__dict__)
                return resource
            with self.assertRaises(Exception):
                owner.acquire("directory", allocate)
            anchor = owner._anchor()
            self.assertIs(anchor.dictionary, original_dictionary)
            self.assertIs(anchor.pending, resource)
            self.assertEqual(anchor.rows, ())
            self.assertEqual(anchor.binding[4], [])
            self.assertTrue(anchor.unknown)
            self.assertEqual(resource.close_calls, 0)

    def test_original_full_roster_freeze_includes_parent_root_and_actual_once_closes(self):
        with Harness() as rig:
            owner = rig.owner()
            values = [owner.acquire("directory", lambda name=name: Resource(name))
                for name in ("custody-parent", "authority-1", "one-of-seven-indexed-roots")]
            owner.freeze()
            frozen = owner._anchor().frozen
            self.assertEqual([row[2] for row in frozen], values)
            owner.close()
            self.assertIs(owner.known().frozen, frozen)
            self.assertTrue(all(value.close_calls == 1 and value.closed for value in values))
            self.assertTrue(all(attempted and closed for _row, _label, _resource, attempted, closed in owner._anchor().rows))
            owner.close()
            self.assertEqual([value.close_calls for value in values], [1, 1, 1])

    def test_close_fence_cannot_forge_actual_close_bits(self):
        with Harness() as rig:
            owner = rig.owner()
            resource = owner.acquire("directory", Resource)
            owner.freeze()
            def forge():
                if owner.closed:
                    owner.resources[0].update(attempted=True, closed=True)
            rig.clock.callback = forge
            with self.assertRaises(Exception):
                owner.close()
            self.assertEqual(resource.close_calls, 0)
            self.assertEqual(owner._anchor().rows[0][3:], (False, False))
            self.assertTrue(owner._anchor().unknown)
            with self.assertRaises(Exception):
                owner.known()

    def test_equal_owner_dictionary_replacement_cannot_be_adopted(self):
        with Harness() as rig:
            owner = rig.owner()
            resource = owner.acquire("directory", Resource)
            original = owner.__dict__
            owner.__dict__ = dict(original)
            with self.assertRaises(Exception):
                owner.check()
            self.assertIs(owner._anchor().dictionary, original)
            self.assertIs(owner._anchor().rows[0][2], resource)
            self.assertTrue(owner._anchor().unknown)
            self.assertEqual(resource.close_calls, 0)

    def test_falsey_actual_close_failure_remains_first_and_never_retries(self):
        with Harness() as rig:
            owner, first = rig.owner(), FalseyFailure("SUPPLIED_FALSEY_CLOSE")
            resource = owner.acquire("directory", lambda: Resource(close_error=first))
            owner.freeze()
            with self.assertRaises(FalseyFailure) as caught:
                owner.close()
            self.assertIs(caught.exception, first)
            self.assertIs(owner.original, first)
            self.assertIs(owner._anchor().failure, first)
            self.assertEqual(owner._anchor().rows[0][3:], (True, False))
            self.assertEqual(resource.close_calls, 1)
            for operation in (lambda: owner.close_one(resource), owner.known):
                with self.assertRaises(Exception):
                    operation()
            self.assertEqual(resource.close_calls, 1)

    def test_swallowed_allocation_reentry_cannot_accept_outer_return(self):
        with Harness() as rig:
            owner, resource, nested = rig.owner(), Resource(), []
            def allocate():
                try:
                    owner.acquire("directory", lambda: nested.append(Resource()))
                except Exception:
                    pass
                return resource
            with self.assertRaises(Exception) as caught:
                owner.acquire("directory", allocate)
            self.assertEqual(nested, [])
            self.assertIs(owner.original, caught.exception)
            self.assertIn(resource, [row[2] for row in owner._anchor().rows])
            with self.assertRaises(Exception):
                owner.freeze()

    def test_swallowed_post_registration_reentry_cannot_accept_outer_return(self):
        with Harness() as rig:
            owner, resource, nested = rig.owner(), Resource(), []
            def reenter():
                if owner.resources and owner.original is None:
                    try:
                        owner.acquire("directory", lambda: nested.append(Resource()))
                    except Exception:
                        pass
            rig.clock.callback = reenter
            with self.assertRaises(Exception) as caught:
                owner.acquire("directory", lambda: resource)
            self.assertEqual(nested, [])
            self.assertIs(owner.original, caught.exception)
            self.assertIs(owner._anchor().rows[0][2], resource)
            with self.assertRaises(Exception):
                owner.freeze()

    def test_swallowed_close_reentry_cannot_create_known_retirement(self):
        with Harness() as rig:
            owner = rig.owner()
            refusals = []
            def reenter():
                try:
                    owner.close_one(resource)
                except Exception as error:
                    refusals.append(error)
            resource = owner.acquire("directory", lambda: Resource(close_hook=reenter))
            owner.freeze()
            try:
                owner.close()
            except Exception:
                pass
            self.assertEqual(len(refusals), 1)
            self.assertIs(owner.original, refusals[0])
            self.assertIs(owner._anchor().failure, refusals[0])
            with self.assertRaises(Exception):
                owner.known()
            self.assertEqual(resource.close_calls, 1)

    def test_phase_is_exact_once_original45_and_restores_original_none_pair(self):
        with Harness() as rig:
            owner = rig.owner()
            window, binding = owner.fence, owner.fence._view().binding
            started = window.now()
            work, final = min(window.work, started + 45 * NS), min(window.final, started + 90 * NS)
            owner.enter_custody_phase(started, work, final)
            phase = owner._anchor().phase
            self.assertEqual(phase, (started, work, final, (None, None)))
            self.assertEqual((owner.work_limit, owner.final_limit), (work, final))
            owner.leave_custody_phase(started, work, final, (None, None))
            self.assertEqual((owner.work_limit, owner.final_limit), (None, None))
            self.assertIs(owner._anchor().phase, phase)
            self.assertFalse(owner._anchor().phase_active)
            self.assertIs(window._view().binding, binding)
            self.assertIs(window._view().binding[6], owner.cancelled)
            with self.assertRaises(Exception):
                owner.enter_custody_phase(started, work, final)

    def test_phase_limit_widening_is_not_implicitly_learned(self):
        with Harness() as rig:
            owner = rig.owner()
            start = owner.fence.now()
            owner.enter_custody_phase(start, start + 45 * NS, min(owner.fence.final, start + 90 * NS))
            owner.work_limit += NS
            with self.assertRaises(Exception):
                owner.check()
            self.assertTrue(owner._anchor().unknown)
            self.assertEqual(owner._anchor().phase[1], start + 45 * NS)


class MatchControls(unittest.TestCase):
    def test_gate_and_worker_pins_bind_actual_object_dictionary_and_record(self):
        for kind in ("gate", "worker"):
            for change in (None, "dictionary", "record", "extra-field"):
                with self.subTest(kind=kind, change=change):
                    match_type = D.A.gate.GateEligibility if kind == "gate" else D.A.stages.BootstrapMatch
                    raw = wire({"scope": "SUPPLIED_PIN_GRAMMAR_ONLY", "kind": kind})
                    match = match_type(raw)
                    pin = D._custody_match_pin(match, kind)
                    self.assertIs(pin[0], match)
                    self.assertIs(pin[2], match.__dict__)
                    self.assertIs(D._custody_match_check(pin), match)
                    if change is None:
                        continue
                    if change == "dictionary":
                        object.__setattr__(match, "__dict__", dict(match.__dict__))
                    elif change == "record":
                        object.__setattr__(match, "record", wire({"different": True}))
                    else:
                        match.__dict__["extra"] = "not-original"
                    with self.assertRaises(Exception):
                        D._custody_match_check(pin)

    def test_closed_kind_pin_rejects_lookalikes_and_cross_kind(self):
        for kind in ("gate", "worker"):
            match_type = D.A.gate.GateEligibility if kind == "gate" else D.A.stages.BootstrapMatch
            for match, selected in ((SimpleNamespace(record=b"{}\n"), kind),
                    (match_type(b"{}\n"), "worker" if kind == "gate" else "gate"),
                    (match_type(b"{}\n"), "other"), (match_type("not-bytes"), kind)):
                with self.assertRaises(Exception):
                    D._custody_match_pin(match, selected)


class CallerRig(Harness):
    """Composed real coordinators around supplied upstream producer boundaries."""
    def __init__(self, kind="gate"):
        super().__init__()
        self.kind, self.events, self.suppliers, self.retained_matches = kind, [], [], []
        self.source_failure = self.supplier_change = self.session_change = None
        self.phase_change = self.before_child = None
        self.acquisitions, self.acquisition_returned = 0, False
        self.operative_owner = self.returned_match = self.child_ack = self.child_clock = None
        self.inherited = {}
        self.git = "/SUPPLIED-NOT-INSTALLED/git/bin/git"
        self.invocation, self.primary_result = "d" * 32, object()

    def __enter__(self):
        super().__enter__()
        try:
            # Fixture construction/pure histories only, never its TestCases.
            self.fixture = FIXTURES.SuppliedHistory(self.kind)
            self.primary = self.fixture.primary()
            self.history_raw = self.fixture.history()
            self.history = json.loads(self.history_raw)
            self.historical = tuple((name, self.fixture.raw[name]) for name in D._history_names(self.kind))
            self.copy_raw = wire({"scope": "SUPPLIED_PRIMARY_COPY_UPSTREAM_NOT_A_STEP"})
            self.custody = Path("/SUPPLIED-CUSTODY-AUTHORITY") / self.kind / "custody"
            self.path = self.custody / "authority-1"
            self.live_window = self.window(self.kind, basis=self.history["originalJobBasisNs"])
            self.window_binding = self.live_window._view().binding
            self.fs = MemoryFiles(self)
            self.fs.add_directory(self.custody)
            self.fs.add_directory(self.custody / "copied-evidence")
            self.fs.install()
            self.stack.enter_context(patch.object(D.time, "time", lambda: self.fixture.use))
            self.stack.enter_context(patch.object(D, "checked_primary", self.checked_primary))
            self.stack.enter_context(patch.object(D, "_paths", self.paths))
            self.stack.enter_context(patch.object(D.N, "location", lambda: (self.kind, self.fixture.roots["P"])))
            self.stack.enter_context(patch.object(D.N, "host_context", self.host_context))
            self.stack.enter_context(patch.object(D.Q, "_inherited_context", lambda: dict(self.inherited)))
            self.stack.enter_context(patch.object(D.I, "GitView", lambda root, env, supplier:
                SimpleNamespace(root=root, environment=env, query_runner=supplier)))
            self.stack.enter_context(patch.object(D.A, "_source", self.source))
            self.stack.enter_context(patch.object(D.N, "query_owner", self.query_owner))
            self.stack.enter_context(patch.object(D.N, "_initial_service_query_git", self.query_git))
            self.stack.enter_context(patch.object(D.A, "acquire_bootstrap", self.acquire))
            self.original_phase = D.native.phase
            self.stack.enter_context(patch.object(D.native, "phase", self.phase))
            actual_retained_match = D.N.retained_match
            def retained(*args, **kwargs):
                result = actual_retained_match(*args, **kwargs)
                self.retained_matches.append(result[0])
                return result
            self.stack.enter_context(patch.object(D.N, "retained_match", retained))
            return self
        except BaseException:
            self.stack.close()
            raise

    def paths(self, kind):
        model_require(kind == self.kind, "FIXED_KIND")
        return self.fixture.roots, self.custody.parent / "handoff", self.custody

    def host_context(self, first_use):
        self.events.append(("supplied-host", first_use))
        return self.fixture.observed, self.fixture.roots["P"], self.fixture.event

    def checked_primary(self, result):
        model_require(result is self.primary_result, "ORIGINAL_SUPPLIED_PRIMARY")
        return self.live_window, self.primary, self.history_raw, self.copy_raw, self.historical

    def source_commands(self):
        source = self.fixture.source["commit"]
        blob = self.fixture.originals["candidate_policy_entry"].split(b" ", 2)[2].split(b"\t", 1)[0].decode("ascii")
        return (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", source + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            ("rev-parse", "--verify", D.A.stages.BASE["commit"] + "^{tree}"),
            ("ls-tree", "-z", D.A.stages.BASE["commit"], "--", D.I.POLICY_PATH),
            ("merge-base", D.A.stages.BASE["commit"], source), ("ls-tree", "-z", source, "--", D.I.POLICY_PATH),
            ("cat-file", "-s", blob), ("cat-file", "blob", blob))

    def source(self, view, context, check):
        supplier = view.query_runner
        model_require(supplier in self.suppliers and context == self.fixture.observed, "SOURCE_UPSTREAM_INPUTS")
        check()
        if self.source_failure is not None:
            raise self.source_failure
        self.clock.advance(1 if supplier.path.name == "source-before" else 20)
        check()
        return {name: self.fixture.originals[name] for name in D.N.SOURCE_KEYS}

    def query_owner(self, owner, fence, path):
        model_require(type(owner) is D._CustodyOwner and owner.fence is fence, "ACTUAL_CUSTODY_QUERY_OWNER")
        owner.end()
        acquisition = path.name == "acquisition-queries"
        if acquisition:
            self.operative_owner = owner
            metadata = fence._anchor().metadata
            model_require(metadata.finished and metadata.failure is None and metadata.owner.closed and
                len(metadata.rows) == 4 and all(attempted and closed for _, _, _, attempted, closed in metadata.rows),
                "METADATA_CLOSE_PRECEDES_QUERY_ALLOCATION")
            self.events.append(("operative-query-after-metadata-close", len(metadata.rows)))
        supplier = QuerySupplier(self, path, acquisition=acquisition)
        self.suppliers.append(supplier)
        if self.supplier_change is not None:
            self.supplier_change(supplier)
        return supplier

    def query_git(self, supplier):
        model_require(supplier is self.suppliers[-1] and supplier.acquisition, "FIXED_CHILD_QUERY_RESOLVER_MODEL")
        self.events.append(("supplied-resolver", supplier.path.name))

    def originals(self):
        result = dict(self.fixture.originals)
        for name in D.N.HTTP_KEYS:
            value = json.loads(result[name])
            value["invocation"] = self.invocation
            value["startedNs"] += 100 * NS
            value["finishedNs"] += 100 * NS
            result[name] = wire(value)
        return tuple((name, result[name]) for name in D.N.ORIGINAL_KEYS)

    def acquire(self, root, *, kind, query_runner, invocation, token, retain, fence,
            original_work_end, first_use_at, expected):
        model_require(root == ROOT and kind == self.kind and invocation == self.invocation and token == TOKEN and
            query_runner is self.suppliers[-1] and query_runner.acquisition and
            fence is self.operative_owner.fence and original_work_end == self.start["workEndNs"] and
            first_use_at == self.fixture.use and type(expected) is type(self.fixture.match) and
            expected.record == self.fixture.match.record, "FIXED_SUPPLIED_ACQUISITION")
        self.acquisitions += 1
        model_require(self.acquisitions == 1, "ONE_ACQUISITION_ONLY")
        self.clock.advance(14)
        originals = self.originals()
        for name, raw in originals:
            retain(name, raw, failed=False)
        match = type(self.fixture.match)(self.fixture.match.record)
        self.returned_match, self.acquisition_returned = match, True
        return match, originals

    def context(self):
        return {"schema": 1, "scope": D.native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE,
            "window": json.loads(D._custody_authority_window(self.live_window)), "history": json.loads(self.history_raw),
            "observed": self.fixture.observed, "expectedMatch": json.loads(self.fixture.match.record),
            "eventSha256": sha(self.fixture.event), "root": str(ROOT), "session": str(self.path), "job": "4" * 32,
            "inheritedContext": {}, "sourceReturnSha256": sha(b"SUPPLIED_CHILD_FRAME_SOURCE_UPSTREAM"),
            "sourceReturnedNs": START + NS, "primaryResultSha256": self.primary.result_sha256,
            "primaryCopySha256": sha(self.copy_raw), "directoryIdentity": list(self.fs.directories[self.path]),
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}

    def start_record(self, context_raw):
        context = json.loads(context_raw)
        began = START + 2 * NS
        work = min(self.live_window.work, began + 45 * NS)
        final = min(self.live_window.final, work + 45 * NS)
        env = D.native.processes.ownership_environment(context["inheritedContext"], context["job"], self.invocation,
            str(self.path), str(self.path / "control-home"), allow_new_context=True)
        return {"schema": 1, "scope": D.native.PHASE_SCOPE, "contextSha256": sha(context_raw),
            "argv": D.native.phase_command(context_raw), "cwd": str(ROOT), "role": "linux-x64",
            "job": context["job"], "invocation": self.invocation, "state": str(self.path),
            "home": str(self.path / "control-home"), "inheritedContext": {key: env[key] for key in D.Q._CONTEXT},
            "startedNs": began, "workEndNs": work, "finalEndNs": final, "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}

    def prepare_child(self, context_change=None, start_change=None):
        """Standalone child supplied frame, not a manufactured authentic parent."""
        for path in (self.path, self.path / "control-home", self.path / "temporary", self.path / "service"):
            self.fs.add_directory(path)
        context = self.context()
        if context_change is not None:
            context_change(context)
        self.context_raw = wire(context)
        self.start = self.start_record(self.context_raw)
        if start_change is not None:
            start_change(self.start)
        self.fs.put(self.path / "context.json", self.context_raw)
        self.fs.put(self.path / "service/start.json", wire(self.start))
        self.inherited = dict(self.start["inheritedContext"])
        self.clock.advance(4)

    def run_child(self, *, context_hash=None, minimum=START + 3 * NS):
        if self.before_child is not None:
            self.before_child()
        with patch.dict(D.os.environ, {D.O.wire.TOKEN_ENV: TOKEN}, clear=True):
            result = D.custody_authority_child(sha(self.context_raw) if context_hash is None else context_hash,
                minimum, self.clock.cancelled)
            model_require(D.O.wire.TOKEN_ENV not in D.os.environ, "CHILD_POPPED_SUPPLIED_TOKEN")
        self.child_ack, self.child_clock, self.child_limit = result
        return result

    def phase(self, owner, private, context_raw, token, fence, *, initial_git=None):
        """Supplied native producer; calls the ACTUAL child without any process.

        Its phase tuple/parent resources are real coordinator transitions over
        counter-only resources. Synthetic native identities/launches below are
        never reported as original native evidence or duration measurements.
        """
        model_require(private.path == self.path and owner.fence is fence is self.live_window and
            initial_git == self.git and token == TOKEN, "FIXED_PARENT_NATIVE_UPSTREAM")
        self.clock.advance(2)
        began = fence.now()
        self.start, self.context_raw = self.start_record(context_raw), context_raw
        model_require(began == self.start["startedNs"], "SAME_ACTUAL_PHASE_START")
        work, final = self.start["workEndNs"], self.start["finalEndNs"]
        old_limits = owner.work_limit, owner.final_limit
        owner.enter_custody_phase(began, work, final)
        try:
            service = owner.child(private, "service", create=True)
            start_raw = owner.write(service, "start.json", self.start)
            scope = owner.acquire("native-scope", lambda: Resource("SUPPLIED_NATIVE_SCOPE_COUNTER_ONLY"))
            capture_end = min(owner.local_end, fence.deadline(90, final=True, limit=final))
            streams = {name: owner.acquire(name, lambda name=name, maximum=maximum:
                service.create_file(name + ".log", max_bytes=maximum, deadline=capture_end))
                for name, maximum in (("stdout", D.native.ACK_LIMIT), ("stderr", D.native.STDERR_LIMIT))}
            leader, preparer = {"pid": 501, "startTicks": 601}, {"pid": 502, "startTicks": 602}
            baseline_raw = owner.write(service, "baseline.json", {"role": "linux-x64", "baseline": [], "kernelJob": False})
            self.clock.advance(3)
            minimum = fence.now(limit=work)
            argv = D.native.phase_command(context_raw, minimum)
            ownership = {"backend": D.native.BACKENDS["linux-x64"], "job": self.start["job"],
                "invocation": self.invocation, "scope": "controlled-marker-inheriting-descendants",
                "discoveryErrors": [], "discoveryReconciliations": [], "startedIdentities": [leader],
                "launches": [{"created": True, "requestedArgv": argv, "resolvedArgv": argv, "cwd": str(ROOT),
                    "pid": leader["pid"], "api": "subprocess.Popen", "shell": False, "executable": argv[0],
                    "outputMode": "caller-owned-files"}]}
            birth_raw = owner.write(service, "native-start.json", {"ownership": ownership, "leader": leader,
                "preparerIdentity": preparer, "observedNs": fence.now(limit=work)})
            self.inherited = dict(self.start["inheritedContext"])
            self.clock.advance(4)
            ack, child_clock, _limit = self.run_child(minimum=minimum)
            self.inherited = {}
            child_raw = self.fs.files[self.path / "service/child-result.json"]
            model_require(ack["terminalSha256"] == sha(child_raw) and child_clock is self.child_clock,
                "ACTUAL_CHILD_RETURN_HASH")
            captures = {"stdout": wire(ack), "stderr": b""}
            for name, stream in streams.items():
                raw = captures[name]
                if raw:
                    model_require(stream.write(raw) == len(raw), "SUPPLIED_CAPTURE_WRITE")
                stream.sync()
                stream.verify()
                owner.close_one(stream)
            self.clock.advance(18)
            owner.close_one(scope)
            row = {**self.start, "exitCode": 0, "launchAttempted": True, "scopeAttempted": True,
                "retirement": "KNOWN", "launchMinimumNs": minimum, "launchArgv": argv, "leader": leader,
                "ownership": ownership, "preparerIdentity": preparer, "scopeCloseAttempted": True, "scopeClosed": True,
                "completedNs": self.clock.raw, "finalizedNs": START + 19 * NS, "survivors": [], "errors": [],
                "nativeStartSha256": sha(birth_raw), "baselineSha256": sha(baseline_raw),
                "captureOutcomes": {name: {key: True for key in ("synced", "verified", "closeAttempted", "closed", "readback")}
                    for name in ("stdout", "stderr")},
                "captures": {name: {"sha256": sha(raw), "bytes": len(raw)} for name, raw in captures.items()}}
            self.clock.advance(19)
            terminal_raw = owner.write(service, "result.json", row)
            records = {"start.json": start_raw, "baseline.json": baseline_raw, "native-start.json": birth_raw,
                "result.json": terminal_raw, "stdout.log": captures["stdout"], "stderr.log": captures["stderr"]}
            if self.phase_change is not None:
                self.phase_change(records, child_raw)
            # Deliberate injected upstream mutations are the bytes retained by
            # this supplier, not repaired by the consumer's test fixture.
            for name, raw in records.items():
                self.fs.put(self.path / "service" / name, raw)
            original = D.native.OriginalPhase(context_raw, tuple(sorted(records.items())))
            model_require(owner.phase_originals is None, "ONE_SUPPLIED_NATIVE_PHASE")
            owner.phase_originals = original
            self.phase_result = original
            return service, original
        finally:
            self.inherited = {}
            owner.leave_custody_phase(began, work, final, old_limits)

    def run_parent(self):
        return D.custody_authority(self.primary_result, TOKEN)


class PhaseAndSourceControls(unittest.TestCase):
    def phase_fixture(self, rig):
        rig.fs = MemoryFiles(rig)
        rig.fs.install()
        path = Path("/SUPPLIED-CUSTODY-PHASE-HOOK")
        rig.fs.add_directory(path)
        owner = rig.owner()
        private = owner.open(path)
        raw = wire({"scope": D.native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE, "job": "4" * 32})
        return owner, private, raw

    def assert_restored(self, owner, first, binding):
        anchor = owner._anchor()
        self.assertIs(anchor.failure, first)
        self.assertIs(owner.original, first)
        self.assertEqual((owner.work_limit, owner.final_limit), (None, None))
        self.assertFalse(anchor.phase_active)
        self.assertEqual(anchor.phase[3], (None, None))
        self.assertEqual(anchor.phase[1], min(owner.fence.work, anchor.phase[0] + 45 * NS))
        self.assertEqual(anchor.phase[2], min(owner.fence.final, anchor.phase[1] + 45 * NS))
        self.assertIs(owner.fence._view().binding, binding)
        self.assertIsNone(owner.phase_originals)
        with self.assertRaises(Exception):
            owner.known()

    def test_actual_native_phase_setup_failure_restores_exact_original_limits(self):
        with Harness() as rig:
            owner, private, raw = self.phase_fixture(rig)
            binding, first = owner.fence._view().binding, FalseyFailure("SUPPLIED_SETUP_FIRST")
            with patch.object(D.native, "phase_command", side_effect=first):
                with self.assertRaises(FalseyFailure) as caught:
                    D.native.phase(owner, private, raw, TOKEN, owner.fence, initial_git="/SUPPLIED/git")
            self.assertIs(caught.exception, first)
            self.assert_restored(owner, first, binding)
            self.assertEqual(len(owner._anchor().rows), 1)
            self.assertFalse(owner.unknown)
            with self.assertRaises(Exception):
                owner.enter_custody_phase(*owner._anchor().phase[:3])

    def test_actual_native_phase_main_finally_restores_after_scope_allocation_failure(self):
        with Harness() as rig:
            owner, private, raw = self.phase_fixture(rig)
            binding, first, calls = owner.fence._view().binding, FalseyFailure("SUPPLIED_SCOPE_ALLOCATION_FIRST"), []
            def refuse_scope(*args):
                calls.append(args)
                raise first
            with patch.object(D.native, "_initial_service_environment", return_value={}), \
                    patch.object(D.native.processes, "make_scope", refuse_scope):
                with self.assertRaises(FalseyFailure) as caught:
                    D.native.phase(owner, private, raw, TOKEN, owner.fence, initial_git="/SUPPLIED/git")
            self.assertIs(caught.exception, first)
            self.assertEqual(len(calls), 1)
            self.assert_restored(owner, first, binding)
            self.assertTrue(owner.unknown)
            self.assertEqual([label for _row, label, _resource, _a, _c in owner._anchor().rows][-2:], ["stdout", "stderr"])
            self.assertFalse(any(label == "native-scope" for _row, label, _resource, _a, _c in owner._anchor().rows))

    def test_setup_restore_secondary_keeps_same_falsey_first_and_unknown(self):
        with Harness() as rig:
            owner, private, raw = self.phase_fixture(rig)
            binding = owner.fence._view().binding
            first, second = FalseyFailure("SUPPLIED_SETUP_FIRST"), RuntimeError("SUPPLIED_RESTORE_SECOND")
            actual_leave, calls = D._CustodyOwner.leave_custody_phase, []
            def fail_after_original_restore(actual_owner, *args):
                calls.append((actual_owner, args))
                actual_leave(actual_owner, *args)
                raise second
            with patch.object(D.native, "phase_command", side_effect=first), \
                    patch.object(D._CustodyOwner, "leave_custody_phase", fail_after_original_restore):
                with self.assertRaises(FalseyFailure) as caught:
                    D.native.phase(owner, private, raw, TOKEN, owner.fence, initial_git="/SUPPLIED/git")
            self.assertIs(caught.exception, first)
            self.assertEqual(len(calls), 1)
            self.assert_restored(owner, first, binding)
            self.assertTrue(owner.unknown)
            self.assertIn(owner, D.native.QUARANTINE)

    def test_actual_source_queries_preserves_falsey_first_through_one_unknown_finalizer(self):
        with CallerRig() as rig:
            owner, first = rig.owner(rig.live_window), FalseyFailure("SUPPLIED_SOURCE_FIRST")
            second = RuntimeError("SUPPLIED_QUERY_CLOSE_SECOND")
            rig.source_failure = first
            rig.supplier_change = lambda supplier: setattr(supplier, "close_error", second)
            with self.assertRaises(FalseyFailure) as caught:
                D.N.source_queries(owner, rig.live_window, rig.fixture.observed, rig.path / "source-before")
            self.assertIs(caught.exception, first)
            self.assertIs(owner.original, first)
            self.assertIs(owner._anchor().failure, first)
            self.assertTrue(owner.unknown)
            self.assertEqual(owner.initial_sources, {})
            self.assertEqual(len(rig.suppliers), 1)
            supplier = rig.suppliers[0]
            self.assertEqual(len(supplier.finalizers), 1)
            self.assertIs(supplier.finalizers[0], first)
            self.assertEqual(supplier.admission_errors, [first])
            self.assertEqual(supplier.close_calls, 1)
            self.assertTrue(supplier.unknown)


class ChildCallerControls(unittest.TestCase):
    def test_gate_and_worker_actual_child_close_metadata_before_single_acquisition(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), CallerRig(kind) as rig:
                rig.prepare_child()
                ack, clock, limit = rig.run_child()
                metadata = clock._anchor().metadata
                self.assertEqual([label for _, label, _, _, _ in metadata.rows], ["directory", "reader", "directory", "reader"])
                self.assertTrue(metadata.finished)
                self.assertIsNone(metadata.failure)
                self.assertTrue(all(attempted and closed for _, _, _, attempted, closed in metadata.rows))
                self.assertTrue(all(reader.closed for _, reader in rig.fs.readers))
                self.assertEqual(rig.acquisitions, 1)
                self.assertIn(("operative-query-after-metadata-close", 4), rig.events)
                self.assertIs(type(rig.operative_owner), D._CustodyOwner)
                self.assertIs(rig.operative_owner.first, clock._anchor().binding[0])
                self.assertIs(rig.operative_owner.fence, clock)
                self.assertIsNot(rig.operative_owner, metadata.owner)
                rig.operative_owner.known()
                self.assertEqual(limit, rig.start["workEndNs"])
                self.assertEqual(ack["scope"], D.native.INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE)
                self.assertEqual(ack["terminalSha256"], sha(rig.fs.files[rig.path / "service/child-result.json"]))
                self.assertLess(ack["closedNs"], limit)

    def test_unknown_metadata_close_prevents_any_operative_owner_or_http(self):
        with CallerRig() as rig:
            rig.prepare_child()
            first = FalseyFailure("SUPPLIED_METADATA_CLOSE_FIRST")
            def fail(directory):
                if directory.path == rig.path:
                    raise first
            rig.fs.close_hook = fail
            with self.assertRaises(FalseyFailure) as caught:
                rig.run_child()
            self.assertIs(caught.exception, first)
            self.assertEqual(rig.acquisitions, 0)
            self.assertEqual(rig.suppliers, [])
            self.assertEqual(D._CUSTODY_OWNERS, {})
            metadata = next(iter(D._CUSTODY_CHILD_CLOCKS.values())).metadata
            self.assertTrue(metadata.owner.unknown)
            self.assertIs(metadata.failure, first)
            self.assertEqual(metadata.rows[0][2].close_calls, 1)

    def test_metadata_consuming_parent45_cannot_start_new_child45_or210(self):
        with CallerRig() as rig:
            rig.prepare_child()
            def exhaust(directory):
                if directory.path == rig.path:
                    rig.clock.advance(47)  # Exactly parent started+45; still below metadata first+45.
            rig.fs.close_hook = exhaust
            with self.assertRaisesRegex(ValueError, "CHILD_FRAME_ORIGINAL_CAP"):
                rig.run_child()
            self.assertEqual(rig.acquisitions, 0)
            self.assertEqual(D._CUSTODY_OWNERS, {})
            anchor = next(iter(D._CUSTODY_CHILD_CLOCKS.values()))
            self.assertEqual(anchor.last, rig.start["workEndNs"])
            self.assertEqual(anchor.phase, "BINDING")
            self.assertTrue(anchor.metadata.finished)
            self.assertFalse(anchor.metadata.owner.unknown)

    def test_context_event_first_use_source_and_inherited_bindings_refuse_before_http(self):
        cases = ("context-hash", "event", "first-use", "source-time", "inherited", "minimum", "expected-match")
        codes = {"context-hash": "AUTHORITY_CHILD_CONTEXT_HASH", "event": "AUTHORITY_ACTUAL_CONTEXT",
            "first-use": "AUTHORITY_ACTUAL_CONTEXT", "source-time": "AUTHORITY_SOURCE_TIME",
            "inherited": "AUTHORITY_NATIVE_INHERITANCE", "minimum": "AUTHORITY_CHILD_PRECEDES_LAUNCH",
            "expected-match": "AUTHORITY_EXPECTED_HISTORY"}
        for case in cases:
            with self.subTest(case=case), CallerRig() as rig:
                def change(context):
                    if case == "first-use":
                        context["history"]["firstUseAt"] += 1
                    elif case == "source-time":
                        context["sourceReturnedNs"] = 0
                    elif case == "expected-match":
                        context["expectedMatch"]["firstUseAt"] += 1  # Original history digest is NOT rewritten.
                rig.prepare_child(context_change=change)
                if case == "event":
                    rig.stack.enter_context(patch.object(D.N, "host_context", return_value=
                        (rig.fixture.observed, rig.fixture.roots["P"], b"SUPPLIED_CHANGED_EVENT")))
                elif case == "inherited":
                    rig.inherited = {}
                args = {"context_hash": "0" * 64} if case == "context-hash" else \
                    {"minimum": START + 5 * NS} if case == "minimum" else {}
                with self.assertRaisesRegex(ValueError, codes[case]):
                    rig.run_child(**args)
                self.assertEqual(rig.acquisitions, 0)
                self.assertEqual(rig.suppliers, [])
                self.assertEqual(D._CUSTODY_OWNERS, {})

    def test_returned_gate_and_worker_match_dictionary_change_is_not_adopted(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), CallerRig(kind) as rig:
                rig.prepare_child()
                changed = []
                def change():
                    if rig.acquisition_returned and not changed:
                        match = rig.returned_match
                        changed.append(match.__dict__)
                        object.__setattr__(match, "__dict__", dict(match.__dict__))
                rig.clock.callback = change
                with self.assertRaisesRegex(ValueError, "AUTHORITY_MATCH_CHANGED"):
                    rig.run_child()
                self.assertEqual(len(changed), 1)
                self.assertEqual(rig.acquisitions, 1)
                self.assertIsNone(rig.child_ack)
                self.assertEqual(len(rig.suppliers[0].finalizers), 1)
                self.assertIs(rig.operative_owner._anchor().failure, rig.suppliers[0].finalizers[0])

    def test_operative_final_close_cannot_replace_actual_close_with_forged_bits(self):
        with CallerRig() as rig:
            rig.prepare_child()
            forged = []
            def forge():
                owner = rig.operative_owner
                if owner is not None and owner.closed and not forged:
                    row = next(row for row in owner.resources if row["label"] == "directory" and row["owner"].path == rig.path)
                    forged.append(row["owner"])
                    row.update(attempted=True, closed=True)
            rig.clock.callback = forge
            with self.assertRaisesRegex(ValueError, "AUTHORITY_OWNER_RESOURCE_CHANGED"):
                rig.run_child()
            self.assertEqual(rig.acquisitions, 1)
            self.assertEqual(len(forged), 1)
            self.assertEqual(forged[0].close_calls, 0)
            self.assertTrue(rig.operative_owner._anchor().unknown)
            self.assertIsNone(rig.child_ack)


class ParentCallerControls(unittest.TestCase):
    @staticmethod
    def change_original_link(owner, change):
        if change == "source-clear":
            owner.initial_sources.clear()
        elif change == "source-equal-return":
            key = next(key for key in owner.initial_sources if key.endswith("/source-after"))
            original = owner.initial_sources[key]
            owner.initial_sources[key] = D.N.SourceReturn(original.records, original.session, original.raw)
        elif change == "phase-none":
            owner.phase_originals = None
        else:
            model_require(change == "phase-equal-return", "CLOSED_LINK_PERTURBATION")
            original = owner.phase_originals
            owner.phase_originals = D.native.OriginalPhase(original.context, original.records)

    def test_gate_and_worker_same_window_full_index_and_original_once_closed_return(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), CallerRig(kind) as rig:
                result = rig.run_parent()
                returned = D.checked_custody_authority(result, rig.primary_result)
                window, match, captured, raw, inventory_raw, originals = returned
                owner = D._AUTHORITY_ATTEMPTS["fixed"]["owner"]
                index, receipt = json.loads(inventory_raw), json.loads(raw)
                self.assertIs(window, rig.live_window)
                self.assertIs(window._view().binding, rig.window_binding)
                self.assertIs(window._view().binding[6], owner.cancelled)
                self.assertIs(owner.first, rig.window_binding[0])
                self.assertIs(owner.fence, window)
                self.assertEqual((owner.work_limit, owner.final_limit), (None, None))
                self.assertFalse(owner._anchor().phase_active)
                self.assertEqual(owner._anchor().phase[:3], tuple(rig.start[key] for key in ("startedNs", "workEndNs", "finalEndNs")))
                self.assertIs(match, rig.retained_matches[-1])
                self.assertIs(type(match), type(rig.fixture.match))
                self.assertEqual(match.record, rig.fixture.match.record)
                self.assertEqual(dict(captured[1])["match"], match.record)
                self.assertEqual((index["fileCount"], index["directoryCount"]), (281, 58))
                self.assertEqual(len(originals), 38)
                self.assertEqual(len({name for name, _ in originals}), 38)
                self.assertEqual(sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in index["files"]), 38)
                self.assertEqual(sum(row["provenance"] == "ORIGINAL_QUERY_DECLARATION" for row in index["files"]), 243)
                available = dict(originals)
                self.assertEqual({row["relative"] for row in index["files"]
                    if row["provenance"] == "ACTUAL_RETAINED_BYTES"}, set(available))
                for row in index["files"]:
                    retained = row["relative"] in available
                    self.assertEqual(row["provenance"], "ACTUAL_RETAINED_BYTES" if retained else "ORIGINAL_QUERY_DECLARATION")
                    if retained:
                        original = available[row["relative"]]
                        self.assertEqual((row["bytes"], row["sha256"]), (len(original), sha(original)))
                self.assertEqual(sum(row["provenance"] == "ORIGINAL_NATIVE_PIN" for row in index["directories"]), 7)
                self.assertEqual(sum(row["provenance"] == "ORIGINAL_QUERY_DECLARATION" for row in index["directories"]), 51)
                pinned = {".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"}
                self.assertEqual({row["relative"] for row in index["directories"]
                    if row["provenance"] == "ORIGINAL_NATIVE_PIN"}, pinned)
                for row in index["directories"]:
                    native = row["relative"] in pinned
                    self.assertEqual(row["provenance"], "ORIGINAL_NATIVE_PIN" if native else "ORIGINAL_QUERY_DECLARATION")
                    self.assertEqual(row["identity"] is not None, native)
                self.assertEqual(index["totalBytes"], sum(row["bytes"] for row in index["files"]))
                self.assertEqual(receipt["resourceCount"], len(owner.known().rows))
                self.assertEqual(receipt["inventorySha256"], sha(inventory_raw))
                self.assertEqual(receipt["matchSha256"], sha(match.record))
                self.assertEqual(receipt["retirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
                self.assertEqual(receipt["budgetAcceptance"], "NOT_ADMITTED")
                self.assertIs(receipt["exportSaveAuthority"], False)
                parents = [resource for _row, label, resource, _a, _c in owner._anchor().rows
                    if label == "directory" and resource.path == rig.custody]
                self.assertEqual(len(parents), 1)
                self.assertEqual(parents[0].close_calls, 1)
                self.assertTrue(all(attempted and closed for _row, _label, _resource, attempted, closed in owner._anchor().rows))
                self.assertEqual(rig.acquisitions, 1)
                self.assertEqual([supplier.path.name for supplier in rig.suppliers],
                    ["source-before", "acquisition-queries", "source-after"])
                self.assertTrue(all(supplier.finalizers == [None] and supplier.close_calls == 1 for supplier in rig.suppliers))
                with self.assertRaisesRegex(ValueError, "AUTHORITY_REUSE"):
                    rig.run_parent()
                self.assertEqual(rig.acquisitions, 1)

    def test_post_registration_custody_parent_root_loss_stops_before_native_or_http(self):
        with CallerRig() as rig:
            lost = []
            def erase():
                attempt = D._AUTHORITY_ATTEMPTS.get("fixed")
                owner = None if attempt is None else attempt["owner"]
                if owner is not None and owner.resources and not lost:
                    row = owner.resources[0]
                    if row["label"] == "directory" and row["owner"].path == rig.custody:
                        lost.append(row["owner"])
                        owner.resources.clear()
            rig.clock.callback = erase
            with self.assertRaisesRegex(ValueError, "AUTHORITY_OWNER_ROSTER_CHANGED") as caught:
                rig.run_parent()
            owner = D._AUTHORITY_ATTEMPTS["fixed"]["owner"]
            self.assertEqual(len(lost), 1)
            self.assertIs(owner._anchor().rows[0][2], lost[0])
            self.assertIs(owner._anchor().failure, caught.exception)
            self.assertTrue(owner._anchor().unknown)
            self.assertEqual(lost[0].close_calls, 0)
            self.assertEqual(rig.suppliers, [])
            self.assertEqual(rig.acquisitions, 0)
            self.assertEqual(D._AUTHORITY_RETURNS, {})

    def test_parent_final_close_does_not_accept_forged_unindexed_root_close_bits(self):
        with CallerRig() as rig:
            forged = []
            def forge():
                attempt = D._AUTHORITY_ATTEMPTS.get("fixed")
                owner = None if attempt is None else attempt["owner"]
                if owner is not None and owner.closed and not forged:
                    row = next(row for row in owner.resources if row["label"] == "directory" and row["owner"].path == rig.custody)
                    forged.append(row["owner"])
                    row.update(attempted=True, closed=True)
            rig.clock.callback = forge
            with self.assertRaisesRegex(ValueError, "AUTHORITY_OWNER_RESOURCE_CHANGED"):
                rig.run_parent()
            owner = D._AUTHORITY_ATTEMPTS["fixed"]["owner"]
            self.assertEqual(rig.acquisitions, 1)
            self.assertEqual(len(forged), 1)
            self.assertEqual(forged[0].close_calls, 0)
            self.assertTrue(owner._anchor().unknown)
            self.assertEqual(D._AUTHORITY_RETURNS, {})

    def test_gate_and_worker_closed_return_match_dictionary_and_record_stay_bound(self):
        for kind in ("gate", "worker"):
            for change in ("dictionary", "record"):
                with self.subTest(kind=kind, change=change), CallerRig(kind) as rig:
                    result = rig.run_parent()
                    original = D.checked_custody_authority(result, rig.primary_result)[1]
                    if change == "dictionary":
                        object.__setattr__(original, "__dict__", dict(original.__dict__))
                    else:
                        object.__setattr__(original, "record", wire({"different": True}))
                    with self.assertRaisesRegex(ValueError, "AUTHORITY_MATCH_CHANGED") as caught:
                        D.checked_custody_authority(result, rig.primary_result)
                    self.assertEqual(D._AUTHORITY_ATTEMPTS["fixed"]["state"], "FAILED")
                    self.assertIs(D._AUTHORITY_ATTEMPTS["fixed"]["failure"], caught.exception)
                    self.assertEqual(rig.acquisitions, 1)

    def test_gate_and_worker_match_mutation_during_final_close_cannot_register_return(self):
        for kind in ("gate", "worker"):
            for change in ("dictionary", "record"):
                with self.subTest(kind=kind, change=change), CallerRig(kind) as rig:
                    changed = []
                    def mutate():
                        attempt = D._AUTHORITY_ATTEMPTS.get("fixed")
                        owner = None if attempt is None else attempt["owner"]
                        if owner is not None and owner.closed and not changed:
                            original = rig.retained_matches[-1]
                            changed.append(original)
                            if change == "dictionary":
                                object.__setattr__(original, "__dict__", dict(original.__dict__))
                            else:
                                object.__setattr__(original, "record", wire({"different": True}))
                    rig.clock.callback = mutate
                    with self.assertRaisesRegex(ValueError, "AUTHORITY_MATCH_CHANGED") as caught:
                        rig.run_parent()
                    self.assertEqual(len(changed), 1)
                    self.assertEqual(rig.acquisitions, 1)
                    self.assertEqual(D._AUTHORITY_RETURNS, {})
                    self.assertIs(D._AUTHORITY_ATTEMPTS["fixed"]["failure"], caught.exception)
                    self.assertEqual(D._AUTHORITY_ATTEMPTS["fixed"]["state"], "FAILED")
                    with self.assertRaisesRegex(ValueError, "AUTHORITY_REUSE"):
                        rig.run_parent()
                    self.assertEqual(rig.acquisitions, 1)

    def test_original_native_phase_ack_and_clock_predicates_are_not_relabelled_success(self):
        for change, code in (("native-close", "AUTHORITY_NATIVE_RETURN"), ("ack", "AUTHORITY_CHILD_ACK"),
                ("clock", "ENTRY_CLOCK_CHAIN"), ("metadata-close", "AUTHORITY_METADATA_ORIGINAL_ROSTER"),
                ("start-work", "AUTHORITY_ORIGINAL_PHASE"), ("native-start-hash", "AUTHORITY_NATIVE_RETURN"),
                ("capture-close", "AUTHORITY_CAPTURE_CLOSE")):
            with self.subTest(change=change), CallerRig() as rig:
                def mutate(records, child_raw):
                    if change == "start-work":
                        value = json.loads(records["start.json"])
                        value["workEndNs"] += NS
                        records["start.json"] = wire(value)
                    elif change in ("native-close", "native-start-hash", "capture-close"):
                        value = json.loads(records["result.json"])
                        if change == "native-close":
                            value["scopeClosed"] = False
                        elif change == "native-start-hash":
                            value["nativeStartSha256"] = "0" * 64
                        else:
                            value["captureOutcomes"]["stdout"]["closed"] = False
                        records["result.json"] = wire(value)
                    else:
                        ack = json.loads(records["stdout.log"])
                        if change == "ack":
                            ack["terminalSha256"] = "0" * 64
                        else:
                            child = json.loads(child_raw)
                            if change == "clock":
                                child["metadataLastNs"] = child["acquiredNs"] + 1
                            else:
                                child["metadataClose"]["resources"].pop()
                            child_raw = wire(child)
                            rig.fs.put(rig.path / "service/child-result.json", child_raw)
                            ack["terminalSha256"] = sha(child_raw)
                        records["stdout.log"] = wire(ack)
                        row = json.loads(records["result.json"])
                        row["captures"]["stdout"] = {"sha256": sha(records["stdout.log"]), "bytes": len(records["stdout.log"])}
                        records["result.json"] = wire(row)
                rig.phase_change = mutate
                with self.assertRaisesRegex(ValueError, code):
                    rig.run_parent()
                self.assertEqual(rig.acquisitions, 1)
                self.assertEqual(D._AUTHORITY_RETURNS, {})

    def test_full_query_declaration_roster_limits_and_ids_are_required(self):
        for change, code in (("missing", "GATE_QUERY_READBACK_ROSTER"), ("maximum", "GATE_QUERY_READBACK"),
                ("duplicate-id", "GATE_QUERY_IDS")):
            with self.subTest(change=change), CallerRig() as rig:
                def mutate(supplier, session):
                    if supplier.path.name != "source-after":
                        return
                    if change == "missing":
                        session["readbacks"].pop()
                    elif change == "maximum":
                        session["readbacks"][0]["maximum"] += 1
                    else:
                        session["queries"][1]["id"] = session["queries"][0]["id"]
                rig.session_change = mutate
                with self.assertRaisesRegex(ValueError, code):
                    rig.run_parent()
                self.assertEqual(len(rig.suppliers), 3)
                self.assertEqual(rig.acquisitions, 1)
                self.assertEqual(D._AUTHORITY_RETURNS, {})

    def test_seven_native_pin_targets_cannot_alias_despite_complete_query_declarations(self):
        with CallerRig() as rig:
            def alias(directory):
                if directory.path == rig.path / "control-home":
                    directory.identity = rig.fs.directories[directory.path] = rig.fs.directories[rig.path]
            rig.fs.open_hook = alias
            with self.assertRaisesRegex(ValueError, "WORKER_ORIGINAL_PIN_ROSTER"):
                rig.run_parent()
            self.assertEqual(rig.acquisitions, 1)
            self.assertEqual(D._AUTHORITY_RETURNS, {})

    def test_actual_full_index_refuses_artificial_aggregate_boundary_without_large_bytes(self):
        with CallerRig() as rig:
            actual_index, calls = D._custody_authority_index, []
            original_limit = D.MAX_BYTES
            def lower_only_index_ceiling(*args, **kwargs):
                supplied = {path: raw for path, raw in rig.fs.files.items() if rig.path in path.parents}
                self.assertEqual(len(supplied), 281)  # Never shrink the required shape to fit a tiny fixture.
                total = sum(len(raw) for raw in supplied.values())
                self.assertGreater(total, 1)
                calls.append(total)
                # Artificial stricter boundary on the unchanged helper. This is
                # NOT a >512MiB producer, allocation or authentic cohort test.
                with patch.object(D, "MAX_BYTES", total - 1):
                    return actual_index(*args, **kwargs)
            with patch.object(D, "_custody_authority_index", lower_only_index_ceiling):
                with self.assertRaisesRegex(ValueError, "AUTHORITY_INDEX_AVAILABLE_ROSTER") as caught:
                    rig.run_parent()
            self.assertEqual(len(calls), 1)
            self.assertEqual(D.MAX_BYTES, original_limit)
            self.assertEqual(D.MAX_BYTES, D.native.posix.MAX_BYTES)
            self.assertEqual(D.MAX_BYTES, 512 * 1024 * 1024)
            self.assertEqual(rig.acquisitions, 1)
            self.assertEqual(D._AUTHORITY_RETURNS, {})
            self.assertIs(D._AUTHORITY_ATTEMPTS["fixed"]["failure"], caught.exception)
            with self.assertRaisesRegex(ValueError, "AUTHORITY_REUSE"):
                rig.run_parent()
            self.assertEqual(rig.acquisitions, 1)

    def test_return_accessor_rejects_equal_owner_dictionary_and_replaced_originals(self):
        for change in ("owner-dictionary", "originals"):
            with self.subTest(change=change), CallerRig() as rig:
                result = rig.run_parent()
                owner = D._AUTHORITY_ATTEMPTS["fixed"]["owner"]
                if change == "owner-dictionary":
                    owner.__dict__ = dict(owner.__dict__)
                    code = "AUTHORITY_OWNER_CHANGED"
                else:
                    object.__setattr__(result, "originals", tuple(list(result.originals)))
                    code = "AUTHORITY_RETURN_CHANGED"
                with self.assertRaisesRegex(ValueError, code):
                    D.checked_custody_authority(result, rig.primary_result)
                self.assertEqual(D._AUTHORITY_ATTEMPTS["fixed"]["state"], "FAILED")
                self.assertEqual(rig.acquisitions, 1)

    def test_post_final_callback_cannot_erase_or_replace_actual_source_and_phase_links(self):
        for change in ("source-clear", "source-equal-return", "phase-none", "phase-equal-return"):
            with self.subTest(change=change), CallerRig() as rig:
                changed = []
                def mutate():
                    attempt = D._AUTHORITY_ATTEMPTS.get("fixed")
                    owner = None if attempt is None else attempt["owner"]
                    if owner is not None and owner.closed and not changed:
                        changed.append(owner)
                        self.change_original_link(owner, change)
                rig.clock.callback = mutate
                with self.assertRaisesRegex(ValueError, "AUTHORITY_ORIGINAL_LINKS_CHANGED") as caught:
                    rig.run_parent()
                self.assertEqual(len(changed), 1)
                self.assertEqual(rig.acquisitions, 1)
                self.assertEqual(D._AUTHORITY_RETURNS, {})
                self.assertIs(D._AUTHORITY_ATTEMPTS["fixed"]["failure"], caught.exception)
                self.assertEqual(D._AUTHORITY_ATTEMPTS["fixed"]["state"], "FAILED")

    def test_closed_accessor_pins_actual_source_and_phase_objects_not_equal_bytes(self):
        for change in ("source-clear", "source-equal-return", "phase-none", "phase-equal-return"):
            with self.subTest(change=change), CallerRig() as rig:
                result = rig.run_parent()
                owner = D._AUTHORITY_ATTEMPTS["fixed"]["owner"]
                self.change_original_link(owner, change)
                with self.assertRaisesRegex(ValueError, "AUTHORITY_ORIGINAL_LINKS_CHANGED") as caught:
                    D.checked_custody_authority(result, rig.primary_result)
                self.assertIs(D._AUTHORITY_ATTEMPTS["fixed"]["failure"], caught.exception)
                self.assertEqual(D._AUTHORITY_ATTEMPTS["fixed"]["state"], "FAILED")
                self.assertEqual(rig.acquisitions, 1)


if __name__ == "__main__":
    unittest.main()
