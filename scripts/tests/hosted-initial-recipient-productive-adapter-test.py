#!/usr/bin/env python3
"""Focused initial adapter models; authored for independent review, not run.

These controls require the separately reviewed A2 C/N/P/U/provider postimages
in the SAME source tree. They do not import/select any historical test methods.
Two old modules supply pure fixture SETUP only. All owners/resources/clocks in
the lifecycle controls are synthetic memory objects, never native retirement.
No Git/HTTP, canonical execution, key, provider, archive, build or CI is used.
38 retained originals and a281-file declaration are NOT complete native custody.
Source-shape assertions supplement, never replace, original ownership models.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes  # Standard-library initialization before denying native loads.
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False
SIDE_EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        SIDE_EFFECTS.append(event)
        raise AssertionError("INITIAL_ADAPTER_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_adapter as A

D, P, U, O, N, B, F = A.D, A.P, A.U, A.O, A.N, A.B, A.F
S, C, E, V = A.staging, A.custody, A.dependency_export, A.save_set
R, Q, L, M = A.producer, A.producer_command, A.collection, A.no_loader
NS, BOOT = O.NS, "b" * 64
REFUSALS = (ValueError, RuntimeError)  # An audit AssertionError is never an expected refusal.


def fixture_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/tests" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


STAGE = fixture_module("initial_adapter_stage_fixtures", "hosted-initial-recipient-stages-test.py")
LEGACY = fixture_module("initial_adapter_producer_fixtures", "hosted-cache-bootstrap-producer-test.py")
SOURCE_NAMES = ("hosted_initial_recipient_productive_adapter.py", "hosted_initial_recipient_productive_data.py",
    "hosted_initial_recipient_productive.py", "hosted_cache_bootstrap_staging.py", "hosted_cache_bootstrap_custody.py",
    "hosted_cache_bootstrap_producer.py", "hosted_cache_bootstrap_producer_command.py",
    "hosted_cache_bootstrap_collection.py", "hosted_cache_bootstrap_collect_files.py",
    "hosted_cache_bootstrap_no_loader.py", "hosted_cache_bootstrap_export.py", "hosted_cache_bootstrap_save_set.py",
    "hosted_dependency_seed_files.py", "hosted_cache_provider_readback.py")
TEXT = {name: (ROOT / "scripts" / name).read_text(encoding="utf-8") for name in SOURCE_NAMES}


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    count = len(SIDE_EFFECTS)
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous
        if len(SIDE_EFFECTS) != count:
            # A fail-closed adapter may catch BaseException while retaining its
            # original cause. That must never hide this model's audit failure.
            raise AssertionError("INITIAL_ADAPTER_MODEL_SIDE_EFFECT")


def section(filename, start, end):
    raw = TEXT[filename]
    return raw[raw.index(start):raw.index(end, raw.index(start) + len(start))]


def clock():
    return O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)


def fake_worker():
    # Only identity-reference/DATA-snapshot models use this INVALID identity.
    return D.identity.InitialBootstrapIdentity(b"identity", b"event", b"policy", b"not-a-key",
        "A" * 40, "a" * 64, 1)


def binding(number):
    return {"identity": [7, number], "stampSha256": "d" * 64}


class LeafOriginControls(unittest.TestCase):
    def setUp(self):
        self.fixture = LEGACY.ProducerModels("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()  # Fixture setup ONLY; no old test method is selected.
        self.configure(LEGACY.I.SELECTIONS[0])

    def configure(self, row):
        self.fixture.configure(row)
        declaration = STAGE.stage1()
        observed = STAGE.observation1(declaration, row[0])
        match = STAGE.check1(declaration, observed)
        identity = D.identity
        event = {"repository": {"full_name": identity.I.REPOSITORY, "default_branch": "main"},
            "ref": identity.stages.SOURCE_REF, "inputs": {"selection": row[0],
            "expected_sha": STAGE.H1, "expected_tree": STAGE.T1}}
        self.worker = guarded(identity.bind_worker_match, match, event_raw=O.encoded(event),
            policy_raw=STAGE.POLICY, now=STAGE.DONE1)
        self.context = copy.deepcopy(self.fixture.context)
        self.context.update(expectedCommit=STAGE.H1, tree=STAGE.T1)
        self.context["source"].update(commit=STAGE.H1, tree=STAGE.T1)
        self.canonical = LEGACY.A.json_bytes(self.context)
        self.request = guarded(R.make_initial_recipient_request, self.worker.record, self.canonical,
            invocation="b" * 32, ancestor_invocations=["c" * 32])
        self.request_raw = R.encoded(self.request)
        self.start = copy.deepcopy(self.fixture.start)
        for name in self.start.keys() & self.request.keys():
            self.start[name] = copy.deepcopy(self.request[name])
        self.receipt = copy.deepcopy(self.fixture.receipt)
        self.receipt.update(sourceBefore=self.context["source"], sourceAfter=self.context["source"])
        self.start_raw, self.receipt_raw = map(LEGACY.A.json_bytes, (self.start, self.receipt))
        self.manifest_raw = O.encoded({"schema": 1, "records": [], "limitation":
            "Changed bytes are not proof of test execution; use the unchanged product assessor."})

    def producer_args(self, *, initial=True):
        if initial:
            return self.request_raw, self.worker.record, self.canonical, self.start_raw, self.receipt_raw
        f = self.fixture
        return f.request_raw, f.admitted_raw, f.canonical_raw, f.start_raw, f.receipt_raw

    def file_originals(self, *, initial=True):
        return L.FileOriginals(*self.producer_args(initial=initial), self.manifest_raw, 0, (7, 8), (7, 9),
            O.encoded({name: binding(20 + number) for number, name in enumerate(L.METADATA)}))

    def test_six_initial_requests_use_the_same_fixed_recipe_and_distinct_scope(self):
        for row in LEGACY.I.SELECTIONS:
            self.configure(row)
            with self.subTest(selection=row[0]):
                self.assertEqual(self.request["scope"], R.INITIAL_REQUEST_SCOPE)
                self.assertEqual(self.request["requestedArgv"], ["help", "--console=plain", "--no-configure-on-demand"])
                self.assertEqual(self.request["executedArgv"][1:], self.fixture.request["executedArgv"][1:])
                self.assertEqual(self.request["stopArgv"][1:], self.fixture.request["stopArgv"][1:])
                self.assertEqual(self.request["testAcceptance"], "NOT_PERFORMED")
                self.assertNotIsInstance(self.worker, R.bootstrap.ordinary.Admission)

    def test_both_request_routes_refuse_the_other_identity(self):
        for make, raw, context in ((R.make_request, self.worker.record, self.canonical),
            (R.make_initial_recipient_request, self.fixture.admitted_raw, self.fixture.canonical_raw)):
            with self.subTest(route=make.__name__), self.assertRaises(REFUSALS):
                guarded(make, raw, context, invocation="b" * 32, ancestor_invocations=["c" * 32])

    def test_initial_request_rejects_alias_ancestors_mutable_bytes_and_extra_schema(self):
        for invocation, ancestors in (("b" * 32, []), ("b" * 32, ["b" * 32]),
            ("b" * 32, ["c" * 32, "c" * 32]), (True, ["c" * 32]), ("b" * 32, iter(["c" * 32]))):
            with self.subTest(ancestors=type(ancestors)), self.assertRaises(REFUSALS):
                guarded(R.make_initial_recipient_request, self.worker.record, self.canonical,
                    invocation=invocation, ancestor_invocations=ancestors)
        for raw in (bytearray(self.worker.record), self.worker.record + b"\n",
                    O.encoded({**O.parse(self.worker.record), "scope": R.bootstrap.SCOPE})):
            with self.assertRaises(REFUSALS):
                guarded(R.make_initial_recipient_request, raw, self.canonical,
                    invocation="b" * 32, ancestor_invocations=["c" * 32])

    def test_initial_observe_and_validate_do_not_accept_ordinary_requests_or_late_zero(self):
        args = self.producer_args()
        observed = guarded(R.observe_initial_recipient_canonical, *args, original_exit_code=0)
        self.assertEqual(observed["scope"], R.INITIAL_OBSERVATION_SCOPE)
        self.assertIs(guarded(R.validate_initial_recipient_observation, observed, *args, original_exit_code=0), observed)
        for value in (None, False, True, "0", 1, 125):
            with self.assertRaises(REFUSALS):
                guarded(R.observe_initial_recipient_canonical, *args, original_exit_code=value)
        for observe, supplied in ((R.observe_canonical, args),
            (R.observe_initial_recipient_canonical, self.producer_args(initial=False))):
            with self.assertRaises(REFUSALS):
                guarded(observe, *supplied, original_exit_code=0)
        for name, value in (("scope", R.OBSERVATION_SCOPE), ("originalExitCode", False), ("testAcceptance", "PASS")):
            with self.assertRaises(REFUSALS):
                guarded(R.validate_initial_recipient_observation, {**observed, name: value}, *args, original_exit_code=0)

    def test_initial_collection_describe_validate_and_reciprocal_origin_refusals(self):
        args = (*self.producer_args(), self.manifest_raw)
        raw = guarded(L.inventory.describe_initial_recipient_inventory, *args, original_exit_code=0)
        self.assertEqual(guarded(L.inventory.validate_initial_recipient_inventory, raw, *args, original_exit_code=0), raw)
        self.assertEqual(O.parse(raw)["collectionState"], "NOT_PERFORMED")
        for call, supplied in ((L.inventory.describe_inventory, args),
            (L.inventory.describe_initial_recipient_inventory, (*self.producer_args(initial=False), self.manifest_raw))):
            with self.assertRaises(REFUSALS):
                guarded(call, *supplied, original_exit_code=0)
        with self.assertRaises(REFUSALS):
            guarded(L.inventory.validate_initial_recipient_inventory, raw + b"\n", *args, original_exit_code=0)

    def test_collect_files_initial_setup_and_legacy_setup_stay_separate(self):
        initial, ordinary = self.file_originals(), self.file_originals(initial=False)
        with patch.object(L, "_collect_inputs", side_effect=lambda owner, inputs, began: (owner, inputs, began)):
            owner = object()
            result = guarded(L.collect_initial_recipient_inventory, owner, initial)
            self.assertIs(result[0], owner)
            self.assertIs(type(result[1]), L._InitialInputs)
            self.assertNotIsInstance(result[1], L._Inputs)
            self.assertIs(type(guarded(L.collect_inventory, owner, ordinary)[1]), L._Inputs)
            for call, supplied in ((L.collect_inventory, initial), (L.collect_initial_recipient_inventory, ordinary)):
                with self.assertRaises(REFUSALS):
                    guarded(call, owner, supplied)

    def test_no_loader_initial_setup_preserves_the_exact_read_only_target(self):
        initial = M.HomeOriginals(self.request_raw, self.worker.record, self.canonical, (7, 8))
        ordinary = M.HomeOriginals(*self.producer_args(initial=False)[:3], (7, 8))
        with patch.object(M, "_observe_inputs", side_effect=lambda owner, inputs, began: inputs):
            result = guarded(M.observe_initial_recipient_absence, object(), initial)
            self.assertIs(type(result), M._InitialInputs)
            self.assertNotIsInstance(result, M._Inputs)
            self.assertEqual(result.binding()["target"], M.INIT_DIRECTORY + "/" + M.LOADER)
            self.assertIs(type(guarded(M.observe_absence, object(), ordinary)), M._Inputs)
            for call, supplied in ((M.observe_absence, initial), (M.observe_initial_recipient_absence, ordinary)):
                with self.assertRaises(REFUSALS):
                    guarded(call, object(), supplied)

    def test_initial_and_legacy_paths_share_only_the_fixed_provider_literal(self):
        github = O.parse(self.worker.record)["github"]
        run = github["runId"] + "-" + github["runAttempt"]
        base = Path("/model/runner-temp")
        initial = base / ("p2pkit-initial-recipient-" + run + "-worker-recipient-initializer")
        old = O.parse(self.fixture.admitted_raw)
        ordinary = base / ("p2pkit-cache-originals-" + old["github"]["runId"] + "-" +
            old["github"]["runAttempt"] + "-" + old["selection"] + "-productive") / "initializer"
        expected = base / "p2pkit-dependency-seed-desktop-linux-x64"
        self.assertEqual(guarded(F.stage_path, initial, "desktop", "linux-x64", admitted_raw=self.worker.record), expected)
        self.assertEqual(guarded(F.stage_path, ordinary, "desktop", "linux-x64", admitted_raw=self.fixture.admitted_raw), expected)
        for path, raw in ((ordinary, self.worker.record), (initial, self.fixture.admitted_raw),
            (initial.with_name(initial.name + "-copy"), self.worker.record), (Path("relative/initializer"), self.worker.record)):
            with self.assertRaises(REFUSALS):
                guarded(F.stage_path, path, "desktop", "linux-x64", admitted_raw=raw)

    def test_command_routes_snapshot_location_before_request_and_keep_six_hundred_stop120(self):
        context = {**self.context, "root": str(ROOT)}
        canonical = LEGACY.A.json_bytes(context)
        helper_raw = b"SYNTHETIC HELPER; NOT EXECUTABLE"
        helper = {"CANONICAL_SOURCE_LIMIT": 1024, "CANONICAL_NAMES": ("modeled.py",),
            "assemble": lambda *values: list(values)}
        with ExitStack() as stack:
            stack.enter_context(patch.object(Q.canonical, "_interpreter", return_value=(None, "/model/python")))
            stack.enter_context(patch.object(Q.canonical, "_load_canonical_helper", return_value=helper))
            stack.enter_context(patch.object(Q.canonical, "_canonical_source", return_value=helper_raw))
            stack.enter_context(patch.object(Q.canonical, "_CANONICAL_HELPER_SHA256", hashlib.sha256(helper_raw).hexdigest()))
            raw = guarded(Q.initial_recipient_command_request, self.worker.record, canonical,
                invocation="b" * 32, ancestor_invocations=["c" * 32])
            value = O.parse(raw)
            self.assertEqual(value["scope"], Q.INITIAL_SCOPE)
            self.assertEqual(value["argv"][value["argv"].index("--timeout") + 1], "600")
            self.assertEqual(value["argv"][value["argv"].index("--stop-timeout") + 1], "120")
            for call, supplied in ((Q.command_request, self.worker.record),
                (Q.initial_recipient_command_request, self.fixture.admitted_raw)):
                with self.assertRaises(REFUSALS):
                    guarded(call, supplied, canonical, invocation="b" * 32, ancestor_invocations=["c" * 32])


class ClosedWrapperControls(unittest.TestCase):
    def test_staging_and_seed_each_refuse_the_other_original_type_before_a_supplier(self):
        initial, ordinary, owner, phase = (object.__new__(D.InitialOriginals), object.__new__(S.Originals), object(), object())
        for call, supplied, tail in ((S.stage_empty, initial, ()),
            (S.stage_initial_recipient_empty, ordinary, ()), (S.observe_empty_seed, initial, (object(),)),
            (S.observe_initial_recipient_empty_seed, ordinary, (object(),))):
            with self.subTest(route=call.__name__), self.assertRaises(REFUSALS):
                guarded(call, owner, supplied, phase, *tail)
        for call in (S.observe_empty_seed, S.observe_initial_recipient_empty_seed):
            with self.assertRaises(REFUSALS):
                guarded(call, owner, initial, phase, None)

    def test_both_initial_staging_wrappers_call_only_the_shared_leaf_after_initial_setup(self):
        original, phase, parent, inputs, captured = (object() for _ in range(5))
        with ExitStack() as stack:
            stack.enter_context(patch.object(D, "capture_originals", return_value=captured))
            build = stack.enter_context(patch.object(D, "InitialInputs", return_value=inputs))
            stack.enter_context(patch.object(S, "_capture_phase", return_value=("phase",)))
            stack.enter_context(patch.object(S, "_capture_evidence", return_value=("evidence",)))
            leaf = stack.enter_context(patch.object(S, "_run_inputs", return_value="SHARED_LEAF_MODEL"))
            self.assertEqual(guarded(S.stage_initial_recipient_empty, parent, original, phase), "SHARED_LEAF_MODEL")
            self.assertEqual(leaf.call_args.args, (parent, inputs, phase, ("phase",), None, None))
            previous = object()
            guarded(S.observe_initial_recipient_empty_seed, parent, original, phase, previous)
            self.assertEqual(leaf.call_args.args, (parent, inputs, phase, ("phase",), previous, ("evidence",)))
            build.assert_called_with(original, captured)

    def test_custody_reservation_has_reciprocal_type_gates_and_no_ordinary_inheritance(self):
        self.assertFalse(issubclass(C._InitialInputs, C._Inputs))
        for call, original in ((C.reserve_configuration, object.__new__(D.InitialOriginals)),
            (C.reserve_initial_recipient_configuration, object.__new__(S.Originals))):
            with self.assertRaises(REFUSALS):
                guarded(call, object(), original, object(), object())
        with ExitStack() as stack:
            captured, inputs, staged, phase = (object() for _ in range(4))
            stack.enter_context(patch.object(D, "capture_originals", return_value=captured))
            stack.enter_context(patch.object(S, "_capture_phase", return_value=("phase",)))
            stack.enter_context(patch.object(C, "_capture_staged", return_value=("stage",)))
            constructor = stack.enter_context(patch.object(C, "_InitialInputs", return_value=inputs))
            engine = stack.enter_context(patch.object(C, "_reserve_inputs", return_value="RESERVATION_ONLY"))
            parent, original = object(), object()
            self.assertEqual(guarded(C.reserve_initial_recipient_configuration, parent, original, phase, staged), "RESERVATION_ONLY")
            constructor.assert_called_once_with(original, captured, staged, ("stage",))
            engine.assert_called_once_with(parent, inputs, phase, ("phase",), ("stage",))

    def test_export_before_after_wrappers_are_exact_and_reciprocal(self):
        old, initial = object.__new__(C._Inputs), object.__new__(C._InitialInputs)
        routes = ((E.export_snapshot, E._Window, old, (), E, "_export_inputs"),
            (E.export_initial_recipient_snapshot, E._InitialWindow, initial, (), E, "_export_inputs"),
            (V.before_save, V._Window, old, (b"{}",), V, "_observe_inputs"),
            (V.before_initial_recipient_save, V._InitialWindow, initial, (b"{}",), V, "_observe_inputs"),
            (V.after_save, V._AfterWindow, old, (b"{}", b"{}"), V, "_observe_inputs"),
            (V.after_initial_recipient_save, V._InitialAfterWindow, initial, (b"{}", b"{}"), V, "_observe_inputs"))
        for call, window_kind, inputs, raw, module, name in routes:
            window = object.__new__(window_kind)
            window.inputs = inputs
            with self.subTest(route=call.__name__), patch.object(module, name, return_value="SAME_ENGINE") as engine:
                self.assertEqual(guarded(call, object(), inputs, window, *raw), "SAME_ENGINE")
                self.assertEqual(engine.call_count, 1)
                foreign = initial if inputs is old else old
                with self.assertRaises(REFUSALS):
                    guarded(call, object(), foreign, window, *raw)
                class Derived(window_kind):
                    pass
                copied = object.__new__(Derived)
                copied.inputs = inputs
                with self.assertRaises(REFUSALS):
                    guarded(call, object(), inputs, copied, *raw)
                self.assertEqual(engine.call_count, 1)

    def test_initial_after_window_requires_new_process_floor_not_old_local_epoch(self):
        inputs = object.__new__(C._InitialInputs)
        inputs.clock = clock()
        inputs.proposal = {"phaseFencesNs": {"save-set-after": 1000 * NS}, "proposedJobEndNs": 1000 * NS}
        phase = S.PhaseStart(O.clocks.Reading(inputs.clock, 300 * NS), 5.0)
        previous = b"historical-before", 100 * NS, 900000.0
        with self.assertRaises(REFUSALS):
            guarded(V._InitialAfterWindow, inputs, phase, previous, current_process_floor=None)
        current = S.PhaseStart(O.clocks.Reading(inputs.clock, 290 * NS), 4.0)
        window = guarded(V._InitialAfterWindow, inputs, phase, previous, current_process_floor=current)
        self.assertEqual((window.first, window.hard, window.soft), (300 * NS, 420 * NS, 390 * NS))
        self.assertEqual(window.previous_local, 900000.0)  # Preserved, not compared with4.0/5.0.
        with self.assertRaises(REFUSALS):
            guarded(V._InitialAfterWindow, inputs, phase, previous,
                current_process_floor=S.PhaseStart(O.clocks.Reading(inputs.clock, 301 * NS), 4.0))

    def test_exact_twelve_files_eight_pins_and_original_retirement_roster(self):
        self.assertEqual(len(D.INITIALIZER_FILES), 12)
        self.assertEqual(len(D.INITIALIZER_DIRECTORIES), 8)
        self.assertIn("I/state/context.json", D.INITIALIZER_FILES)
        self.assertNotIn("I/initializer/context.json", D.INITIALIZER_FILES)
        labels = ["directory", *("reader",) * 3, "directory", *("reader",) * 7,
                  "directory", "reader", "directory", "reader"]
        close = {"schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
            "resources": [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
                          for number, label in enumerate(labels)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
        self.assertIs(guarded(D.retired_input_close, close), close)
        for change in (lambda value: value["resources"].pop(), lambda value: value["resources"][0].update(closed=False),
            lambda value: value.update(retirement="UNKNOWN"), lambda value: value["resources"][0].update(ordinal=False)):
            bad = copy.deepcopy(close)
            change(bad)
            with self.assertRaises(REFUSALS):
                guarded(D.retired_input_close, bad)

    def test_source_hash_rosters_and_two_gib_engine_bounds_are_not_extended(self):
        old, initial = object.__new__(C._Inputs), object.__new__(C._InitialInputs)
        self.assertEqual(S._bootstrap_sources(old), S.BOOTSTRAP_INPUTS)
        self.assertEqual(S._bootstrap_sources(initial), S.BOOTSTRAP_INPUTS + D.INITIAL_SOURCE_INPUTS)
        self.assertEqual(len(D.INITIAL_SOURCE_INPUTS), 12)
        self.assertEqual((F.FILE_LIMIT, F.TOTAL_LIMIT, F.MEMBER_LIMIT), (512 * 1024**2, 2 * 1024**3, 10000))

    def test_initializer_retired_local_keeps_exact_float_type(self):
        # capture_originals is only a DATA snapshot; these bytes deliberately
        # are NOT a semantically admitted initializer or initial identity.
        value = D.InitialOriginals(fake_worker(), O.encoded({"clock": O.clock_value(clock())}), b"{}", b"{}",
            tuple((name, b"") for name in D.SOURCE_KEYS), "/model/initial",
            tuple((name, b"{}") for name in D.INITIALIZER_FILES),
            tuple((name, (7, number + 1), "ORIGINAL_INITIALIZER_NATIVE_PIN")
                  for number, name in enumerate(D.INITIALIZER_DIRECTORIES)), 1, 1.0)
        self.assertEqual(guarded(D.capture_originals, value)[-1], 1.0)
        for changed in (1, True, float("nan"), float("inf")):
            object.__setattr__(value, "checked_local", changed)
            with self.assertRaises(REFUSALS):
                guarded(D.capture_originals, value)


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class Resource:
    def __init__(self):
        self.closes = 0
        self.on_close = lambda: None

    def close(self):
        self.closes += 1
        self.on_close()


class AdapterMemoryModels(unittest.TestCase):
    """Real adapter latch/window/owner code, entirely synthetic shell inputs."""
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.raw, self.local, self.boot, self.identity = 100 * NS, 1000.0, BOOT, clock()
        self.action = lambda: None
        self.observe_action = lambda: None
        for name in ("_RUNS", "_PARENTS", "_WINDOWS", "_OWNERS", "_RETURNS", "_HANDOFFS", "_READERS", "_INPUTS",
            "_DERIVES", "_OUTPUTS", "_PINS", "_RUN_LATCHES", "_FAILURES", "_CHILD_RETURNS", "_OWNER_RETURNS", "_LEAF_RETURNS"):
            self.stack.enter_context(patch.object(A, name, {}))
        self.stack.enter_context(patch.object(A, "_environment", lambda _run: None))  # Host checks are not modeled here.
        self.stack.enter_context(patch.object(time, "monotonic", lambda: self.local))
        self.stack.enter_context(patch.object(O.clocks, "observe", self.observe))
        self.stack.enter_context(patch.object(N.continuity, "boot_digest", lambda _role: self.boot))
        self.stack.enter_context(patch.object(B, "QUARANTINE", []))
        self.run = guarded(A._new_run, "prepare-save", lambda: self.action())
        self.state = guarded(A._new_phase, self.run, "save-transition", None)

    def observe(self):
        self.observe_action()
        return O.clocks.Reading(self.identity, self.raw)

    def owner(self):
        return guarded(A._new_owner, self.state)

    def synthetic_phase(self, name):
        """Window arithmetic unit only, not a fabricated productive entry."""
        cumulative, ends, locals_ = 0, [], []
        for _name, seconds, _soft in A._PHASES[name]:
            cumulative += seconds
            ends.append(self.raw + cumulative * NS)
            locals_.append(O.wire._directed_deadline(self.local, cumulative, ends[-1], self.raw))
        first, parent, window = O.clocks.Reading(self.identity, self.raw), A._Parent(), A._Window()
        state = A._track(A._ParentState(parent, self.run, name, first, self.local, self.boot, None, None,
            N._history_graph(first), tuple(ends), tuple(locals_), window,
            starts=((self.raw, self.local, ends[0], locals_[0]),), last=self.raw,
            last_reading=first, local_last=self.local, issued=locals_[0]))
        A._PARENTS[id(parent)], A._WINDOWS[id(window)] = state, state
        A._progress(self.run, current=state)
        self.state = state
        return state

    def handoff(self, owner):
        worker = fake_worker()
        data = D.InitialOriginals(worker, b"{}", b"{}", b"{}", (), "/model/initial", (), (), 1, 1.0)
        handoff = A.HandoffInputs(b"{}", worker, b"{}", b"{}", (), Path("/model/initial"), (7, 1), b"{}", (), data)
        reader = A._reader_state(owner, self.state.first, {name: "MODEL" for name in A._BASE_CLAIMS})
        A._READERS[id(owner)] = reader
        A._progress(reader, handoff=handoff)
        return reader, handoff

    def test_unregistered_or_copied_parent_window_refuses(self):
        with self.assertRaises(REFUSALS):
            guarded(A._state, A._Parent())
        with self.assertRaises(REFUSALS):
            guarded(A._Window().now)
        self.assertIs(guarded(A._state, self.state.parent), self.state)

    def test_mutated_parent_dictionary_then_restored_cannot_revive_original(self):
        original = self.state.__dict__
        self.state.__dict__ = dict(original)
        with self.assertRaises(REFUSALS) as failed:
            guarded(self.state.window.now)
        self.state.__dict__ = original
        with self.assertRaises(REFUSALS) as repeated:
            guarded(self.state.window.now)
        self.assertIs(failed.exception, repeated.exception)

    def test_nested_data_change_cannot_be_blessed_by_progress(self):
        data = {"nested": [1]}
        A._progress(self.state, proposal=data, graph=N._history_graph(data))
        data["nested"].append(2)
        with self.assertRaises(REFUSALS):
            guarded(A._progress, self.state, graph=N._history_graph(data))

    def test_data_dictionary_replacement_is_detected_even_when_equal(self):
        value = A.PendingHandoff(b"{}", 100 * NS, 1000.0)
        pins = A._data_pins(value)
        object.__setattr__(value, "__dict__", dict(value.__dict__))
        with self.assertRaises(REFUSALS):
            guarded(A._check_data_pins, pins)

    def test_resource_pin_class_replacement_cannot_preserve_original_authority(self):
        owner = self.owner()
        guarded(owner.acquire, "memory", Resource)
        pin = A._OWNERS[id(owner)].resources[0]
        class ForeignPin:
            pass
        object.__setattr__(pin, "__class__", ForeignPin)
        with self.assertRaises(REFUSALS) as failed:
            guarded(owner.end)
        object.__setattr__(pin, "__class__", A._Resource)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(owner.end)
        self.assertIs(failed.exception, repeated.exception)

    def test_capture_pin_class_replacement_is_not_an_equal_native_record(self):
        state = self.synthetic_phase("configuration")
        capture = A._Capture("stdout", Resource(), (7, 10), 0)
        native = A._track(A._Native(b"{}", (), b"{}", object(), (7, 9), {}, "a" * 32,
            captures=(capture,)))
        A._progress(state, native=native)
        class ForeignCapture:
            pass
        object.__setattr__(capture, "__class__", ForeignCapture)
        with self.assertRaises(REFUSALS) as failed:
            guarded(state.window.now)
        object.__setattr__(capture, "__class__", A._Capture)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(state.window.now)
        self.assertIs(failed.exception, repeated.exception)

    def test_raw_local_boot_and_containing_work_expiry_are_terminal(self):
        self.raw = self.state.ends[0]
        with self.assertRaises(REFUSALS) as expired:
            guarded(self.state.window.now)
        self.raw = 100 * NS
        with self.assertRaises(REFUSALS) as repeated:
            guarded(self.state.window.now)
        self.assertIs(expired.exception, repeated.exception)

    def test_local_expiry_does_not_borrow_raw_time(self):
        self.local = self.state.local_ends[0]
        with self.assertRaises(REFUSALS):
            guarded(self.state.window.now)

    def test_boot_change_does_not_borrow_a_new_process_clock(self):
        self.boot = "c" * 64
        with self.assertRaises(REFUSALS):
            guarded(self.state.window.now)

    def test_soft_is_new_work_only_but_hard_is_never_renewed(self):
        state = self.synthetic_phase("dependency-export")
        original = state.ends
        self.raw, self.local = 191 * NS, 1091.0
        self.assertEqual(guarded(state.window.now), self.raw)
        with self.assertRaises(REFUSALS):
            guarded(state.window.now, new=True)
        self.assertEqual(state.ends, original)
        self.assertEqual(guarded(state.window.now, final=True), self.raw)  # Cleanup only, not success.
        self.raw = original[0]
        with self.assertRaises(REFUSALS):
            guarded(state.window.now, final=True)

    def test_nested_clock_reentry_poison_survives_callback_catching_it(self):
        failures = []
        def reenter():
            try:
                self.state.window.now()
            except REFUSALS as error:
                failures.append(error)
        self.action = reenter
        with self.assertRaises(REFUSALS) as outer:
            guarded(self.state.window.now)
        self.assertIs(outer.exception, failures[0])
        self.assertIs(self.run.failure, failures[0])
        self.assertIs(self.state.sampling, False)

    def test_advance_reentry_does_not_reset_the_outer_busy_latch(self):
        state = self.synthetic_phase("configuration")
        observed = []
        def reenter():
            self.observe_action = lambda: None
            try:
                state.window.advance()
            except REFUSALS as error:
                observed.append((error, state.advancing))
        self.observe_action = reenter
        guarded(state.window.advance)  # Cleanup may proceed, but it can never restore success.
        self.assertTrue(observed[0][1])
        with self.assertRaises(REFUSALS) as refused:
            guarded(state.window.now)
        self.assertIs(refused.exception, observed[0][0])

    def test_cleanup_phases_refuse_new_acquisition_without_calling_factory(self):
        state = self.synthetic_phase("configuration")
        owner = self.owner()
        guarded(state.window.advance)
        called = []
        with self.assertRaises(REFUSALS):
            guarded(owner.acquire, "forbidden", lambda: called.append(True))
        self.assertEqual(called, [])
        self.assertEqual(state.phase, 1)

    def test_original_final_refusal_is_sticky_for_every_file_entry(self):
        owner = self.owner()
        with self.assertRaises(REFUSALS) as failed:
            guarded(owner.open, Path("/must/not/open"), final=True)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(owner.end)
        self.assertIs(failed.exception, repeated.exception)

    def test_actual_late_resource_return_is_retained_and_closed_once_not_accepted(self):
        owner, resource = self.owner(), Resource()
        def late():
            self.raw = self.state.ends[0]
            return resource
        with self.assertRaises(REFUSALS) as failed:
            guarded(owner.acquire, "late", late)
        self.assertIs(A._OWNER_RETURNS[id(owner)][0][1], resource)
        guarded(owner.close)
        guarded(owner.close)
        self.assertEqual(resource.closes, 1)
        with self.assertRaises(REFUSALS) as refused:
            guarded(A._known, owner)
        self.assertIs(refused.exception, failed.exception)

    def test_raw_return_survives_a_missing_close_method_and_registration_failure(self):
        owner, returned = self.owner(), object()
        with self.assertRaises(AttributeError) as failed:
            guarded(owner.acquire, "unknown", lambda: returned)
        self.assertIs(A._OWNER_RETURNS[id(owner)][0][1], returned)
        self.assertTrue(owner.unknown)
        self.assertIs(owner.original, failed.exception)

    def test_falsey_first_failure_is_not_replaced_by_a_later_close_error(self):
        owner, resource = self.owner(), Resource()
        guarded(owner.acquire, "memory", lambda: resource)
        first = FalseyFailure("FIRST_MODEL_ERROR")
        resource.on_close = lambda: (_ for _ in ()).throw(RuntimeError("LATER_CLOSE_ERROR"))
        owner.error("first", first)
        with self.assertRaises(FalseyFailure) as result:
            guarded(owner.close)
        self.assertIs(result.exception, first)
        self.assertIs(owner.original, first)
        self.assertTrue(owner.unknown)
        self.assertEqual(resource.closes, 1)

    def test_nested_acquisition_cannot_be_swallowed_to_publish_a_later_resource(self):
        owner, resource, nested = self.owner(), Resource(), []
        def factory():
            try:
                owner.acquire("nested", lambda: Resource())
            except REFUSALS as error:
                nested.append(error)
            return resource
        with self.assertRaises(REFUSALS) as refused:
            guarded(owner.acquire, "outer", factory)
        self.assertIs(refused.exception, nested[0])
        self.assertIs(A._OWNER_RETURNS[id(owner)][0][1], resource)

    def cancellation_model(self, fail_at):
        """Only cancellation allocation/retention is modeled, not native proof."""
        state = self.synthetic_phase("configuration")
        owner, calls = self.owner(), []
        first, allocation = FalseyFailure("ORIGINAL_WORK_FAILURE"), RuntimeError("PARTIAL_CANCEL_ALLOCATION")
        home, job, invocation = "/model/state/gradle-home", "a" * 32, "b" * 32
        class Info:
            identity = (7, 24)
            def __init__(self, size):
                self.size = size
            def as_dict(self):
                return {"identity": list(self.identity), "size": self.size, "modelOnly": True}
        class Writer(Resource):
            def write(self, raw):
                self.raw = raw
                return len(raw)
            def sync(self):
                pass
            def verify(self):
                return Info(len(self.raw))
        writer = Writer() if fail_at == "reader" else object()
        class Directory:
            def __init__(self, path, number):
                self.path, self.identity = Path(path), (7, number)
            def verify(self):
                return SimpleNamespace(identity=self.identity)
            def create_file(self, name, **_kw):
                calls.append(("writer", name))
                if fail_at == "writer":
                    raise allocation
                return writer
            def open_file(self, name, **_kw):
                calls.append(("reader", name))
                raise allocation
        handles = {name: Directory(path, number) for name, path, number in
            (("state", "/model/state", 20), ("gradle-home", home, 21),
             ("cancellations", "/model/state/cancellations", 22))}
        inputs = SimpleNamespace(directories={name: row.identity for name, row in handles.items()})
        A._progress(state, inputs=inputs)
        scope = guarded(owner.acquire, "native-scope", Resource)
        scope.job, scope.invocation, scope.state, scope.home = job, "c" * 32, "/model/state", home
        start = O.encoded({name: getattr(scope, name) for name in ("job", "invocation", "state", "home")})
        request = O.encoded({"id": invocation, "jobId": job, "gradleHome": home})
        descriptor = O.encoded({"requestBytes": request.decode("ascii"), "state": scope.state, "argv": ["NOT_EXECUTED"]})
        child = SimpleNamespace(pid=23)
        native = A._track(A._Native(descriptor, (), start, object(), (7, 10), handles, scope.invocation,
            child=child, child_kind=type(child), child_pid=child.pid, leader=b"{}", birth=b"{}"))
        A._progress(state, native=native)
        owner.error("original-work", first)
        guarded(state.window.advance)
        # Original native DATA validation is covered independently; this unit
        # supplies only its success frontier to exercise fixed allocation paths.
        with patch.object(B, "native_record", return_value=None), patch.object(A, "datetime",
                SimpleNamespace(now=lambda _tz: SimpleNamespace(isoformat=lambda: "2026-09-26T00:00:00+00:00"))):
            guarded(A._producer_cancel, state)
        self.assertIs(owner.original, first)
        self.assertTrue(owner.unknown)
        self.assertTrue(native.cancellation_attempted)
        expected = [("writer", invocation + ".json")]
        if fail_at == "reader":
            expected.append(("reader", invocation + ".json"))
            self.assertEqual(writer.closes, 1)
        elif fail_at == "registration":
            self.assertIs(A._OWNER_RETURNS[id(owner)][-1][1], writer)
        self.assertEqual(calls, expected)
        with self.assertRaises(REFUSALS):
            guarded(A._producer_cancel, state)
        self.assertEqual(calls, expected)

    def test_cancel_writer_allocation_exception_keeps_unknown_and_original_cause(self):
        self.cancellation_model("writer")

    def test_cancel_reader_allocation_exception_does_not_reopen_closed_writer(self):
        self.cancellation_model("reader")

    def test_cancel_actual_return_survives_failed_close_method_registration(self):
        self.cancellation_model("registration")

    def test_unrelated_unknown_file_still_owes_the_original_native_scope_drain_close(self):
        state = self.synthetic_phase("configuration")
        owner = self.owner()
        class Scope(Resource):
            job, invocation, state, home = "a" * 32, "b" * 32, "/model/state", "/model/state/gradle-home"
            def __init__(self):
                super().__init__()
                self.drains = 0
            def drain(self, **_kw):
                self.drains += 1
                return []
            def description(self):
                return {"discoveryErrors": []}
        scope = guarded(owner.acquire, "native-scope", Scope)
        start = O.encoded({name: getattr(scope, name) for name in ("job", "invocation", "state", "home")})
        native = A._track(A._Native(b"{}", (), start, object(), (7, 10), {}, scope.invocation, scope_attempted=True))
        A._progress(state, native=native)
        first = FalseyFailure("UNRELATED_FILE_UNKNOWN")
        owner.error("unrelated-file", first, unknown=True)
        guarded(A._producer_final, state)
        self.assertEqual((scope.drains, scope.closes), (1, 1))
        self.assertIs(owner.original, first)
        self.assertTrue(owner.unknown)
        with self.assertRaises(REFUSALS):
            guarded(A._known, owner)

    def test_output_final_flag_does_not_select_cleanup_or_extend_original_thirty(self):
        owner = self.owner()
        guarded(owner.acquire, "memory", Resource)
        guarded(owner.close)
        result = A._StepReturn({"pending": True}, A._OutputFence(), self.state.ends[0])
        guarded(A._register_output, self.state, result, b"{}")
        self.assertEqual(guarded(result.fence.now, final=True), self.raw)
        self.raw = result.hard_end_ns
        with self.assertRaises(REFUSALS):
            guarded(result.fence.now, final=True)

    def test_pending_or_equal_output_cannot_be_substituted_for_completed_handoff(self):
        pending = A.PendingHandoff(b"{}", self.raw, self.local)
        with self.assertRaises(REFUSALS):
            guarded(A.checked_productive_handoff, pending, object())
        with self.assertRaises(REFUSALS):
            guarded(A.checked_productive_handoff, A.ProductiveHandoff({}, A._OutputFence(), self.raw + NS), object())

    def test_passive_handoff_does_not_call_expired_parent_or_current_clocks(self):
        owner = self.owner()
        reader, handoff = self.handoff(owner)
        self.raw, self.local = 9999 * NS, 9999.0
        with patch.object(O.clocks, "observe", side_effect=AssertionError("HISTORICAL_CLOCK_FORBIDDEN")):
            self.assertIs(guarded(A.checked_handoff_inputs, owner, handoff), handoff)
        with self.assertRaises(REFUSALS):
            guarded(A.checked_handoff_inputs, owner, copy.copy(handoff))
        self.assertIs(reader.handoff, handoff)

    def test_handoff_nested_dictionary_replacement_is_sticky_after_restoration(self):
        owner = self.owner()
        _reader, handoff = self.handoff(owner)
        original = handoff.originals.__dict__
        object.__setattr__(handoff.originals, "__dict__", dict(original))
        with self.assertRaises(REFUSALS) as failed:
            guarded(A.checked_handoff_inputs, owner, handoff)
        object.__setattr__(handoff.originals, "__dict__", original)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.checked_handoff_inputs, owner, handoff)
        self.assertIs(failed.exception, repeated.exception)

    def test_handoff_class_restoration_cannot_erase_original_refusal(self):
        owner = self.owner()
        _reader, handoff = self.handoff(owner)
        class ForeignHandoff:
            pass
        object.__setattr__(handoff, "__class__", ForeignHandoff)
        with self.assertRaises(REFUSALS) as failed:
            guarded(A.checked_handoff_inputs, owner, handoff)
        object.__setattr__(handoff, "__class__", A.HandoffInputs)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.checked_handoff_inputs, owner, handoff)
        self.assertIs(failed.exception, repeated.exception)

    def test_preparation_entry_latches_original_registered_input_mutation(self):
        owner = self.owner()
        reader, handoff = self.handoff(owner)
        inputs = A.ProviderInputs({}, object(), handoff, {}, b"{}")
        A._INPUTS[id(handoff)] = (inputs, reader, N._history_graph(inputs.__dict__), handoff.identity, A._data_pins(inputs))
        A._DERIVES[id(handoff)] = handoff, owner, handoff.identity
        original = inputs.__dict__
        object.__setattr__(inputs, "__dict__", dict(original))
        with self.assertRaises(REFUSALS) as failed:
            guarded(A.validate_provider_preparation, owner, handoff, inputs, "save", reader.claims,
                object(), b"{}", self.state.first)
        object.__setattr__(inputs, "__dict__", original)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.recheck_provider_inputs, owner, inputs)
        self.assertIs(failed.exception, repeated.exception)

    def test_registered_input_class_mismatch_is_sticky_before_semantic_read(self):
        owner = self.owner()
        reader, handoff = self.handoff(owner)
        inputs = A.ProviderInputs({}, object(), handoff, {}, b"{}")
        A._INPUTS[id(handoff)] = (inputs, reader, N._history_graph(inputs.__dict__), handoff.identity, A._data_pins(inputs))
        class ForeignInputs:
            pass
        object.__setattr__(inputs, "__class__", ForeignInputs)
        with self.assertRaises(REFUSALS) as failed:
            guarded(A.recheck_provider_inputs, owner, inputs)
        object.__setattr__(inputs, "__class__", A.ProviderInputs)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.recheck_provider_inputs, owner, inputs)
        self.assertIs(failed.exception, repeated.exception)

    def test_distinct_reader_paths_cannot_alias_the_same_native_directory(self):
        owner = self.owner()
        reader, _handoff = self.handoff(owner)
        class Directory(Resource):
            identity = (7, 40)
            def __init__(self, path):
                super().__init__()
                self.path = path
            def verify(self):
                return SimpleNamespace(identity=self.identity)
        with patch.object(F, "private_root", side_effect=Directory):
            first = guarded(A._read_root, reader, Path("/model/one"))
            self.assertIs(guarded(A._read_root, reader, Path("/model/one")), first)
            with self.assertRaises(REFUSALS):
                guarded(A._read_root, reader, Path("/model/two"))
        self.assertEqual(tuple(reader.directories), (Path("/model/one"),))
        self.assertEqual(len(A._OWNER_RETURNS[id(owner)]), 2)  # Actual refused return remains retained.

    def test_distinct_reader_files_cannot_alias_the_same_native_file(self):
        owner = self.owner()
        reader, _handoff = self.handoff(owner)
        class Directory(Resource):
            identity = (7, 40)
            def __init__(self, path):
                super().__init__()
                self.path = path
            def verify(self):
                return SimpleNamespace(identity=self.identity)
        path = Path("/model/one")
        with patch.object(F, "private_root", side_effect=Directory), patch.object(S, "_read", return_value=(b"{}", binding(41))):
            self.assertEqual(guarded(A._read_file, reader, path, "one.json"), b"{}")
            with self.assertRaises(REFUSALS):
                guarded(A._read_file, reader, path, "two.json")
        self.assertEqual(tuple(reader.files), ((path, "one.json"),))

    def test_fresh_begin_requires_same_consumed_result_not_an_equal_identity_dto(self):
        owner = self.owner()
        reader, handoff = self.handoff(owner)
        A._progress(self.run, prefix=handoff)
        result = P.InitialUse(self.state.parent, "prepare-save/begin", handoff.identity, b"{}", b"{}", (), Path("/model/use"))
        A._progress(self.state, uses=(result,))
        with patch.object(P, "checked_consumed_use", side_effect=lambda value, parent, site: value if
                value is result and parent is self.state.parent and site == result.site else None):
            guarded(A._fresh_begin, reader, handoff.identity)
            equal = D.identity.InitialBootstrapIdentity(*D.worker_values(handoff.identity))
            self.assertEqual(D.worker_values(equal), D.worker_values(handoff.identity))
            with self.assertRaises(REFUSALS):
                guarded(A._fresh_begin, reader, equal)
            A._progress(self.state, inputs=object())
            with self.assertRaises(REFUSALS):
                guarded(A._fresh_begin, reader, handoff.identity)


def data_inputs():
    return SimpleNamespace(clock=clock(), history={"originalBootDigest": BOOT}, admitted=fake_worker(),
        proposal={"phaseFencesNs": {name: 10000 * NS for name in D.STEP_CAPS}, "proposedJobEndNs": 10000 * NS},
        admission={name: {"model": name} for name in ("source", "github", "selection", "cacheCohort")}, role="linux-x64")


def private_chain(inputs, operation="after-save", first=200 * NS):
    phase = D.STEP_PHASES[operation]
    work = first + D.STEP_CAPS[phase][0] * NS
    uses = []
    for number, edge in enumerate(("begin", "final")):
        site = operation + "/" + edge
        began = first + (number * 3 + 1) * NS
        window = U.frame(U.seed(site, first, work, began, BOOT), inputs.clock)
        returned = {"site": site, "windowSha256": O.digest(O.encoded(window)),
            "workerIdentitySha256": O.digest(inputs.admitted.record), "preCloseNs": began + NS, "closedNs": began + NS}
        inventory = {"modelOnly": True}
        uses.append({"site": site, "root": "/model/only", "return": returned, "window": window,
            "inventory": inventory, "returnSha256": O.digest(O.encoded(returned)),
            "inventorySha256": O.digest(O.encoded(inventory)), "originalsSha256": {}})
    return {"schema": 1, "scope": D.STEP_CHAIN_SCOPE, "operation": operation, "clock": O.clock_value(inputs.clock),
        "originalBootDigest": BOOT, "firstNs": first, "workEndNs": work, "handoffSha256": O.digest(b"{}"),
        "uses": uses, "checkedNs": first + 8 * NS, "ownerClose": D.PENDING,
        "providerExecution": "NOT_PERFORMED", "exportSaveAuthority": False}


class StepHistoricalDataControls(unittest.TestCase):
    def test_all_four_private_chains_bind_two_sites_inside_original_phase_only(self):
        inputs = data_inputs()
        for operation in D.STEP_PHASES:
            chain = private_chain(inputs, operation)
            self.assertEqual(guarded(D.private_chain_record, O.encoded(chain), inputs, b"{}", operation,
                chain["firstNs"], chain["workEndNs"]), chain)
            for change in (lambda value: value["uses"].reverse(), lambda value: value["uses"].pop(),
                lambda value: value.update(ownerClose="KNOWN"), lambda value: value.update(workEndNs=value["workEndNs"] + NS),
                lambda value: value["uses"][1]["window"].update(parentFirstNs=201 * NS),
                lambda value: value.update(checkedNs=True)):
                bad = copy.deepcopy(chain)
                change(bad)
                with self.subTest(operation=operation), self.assertRaises(REFUSALS):
                    guarded(D.private_chain_record, O.encoded(bad), inputs, b"{}", operation,
                        chain["firstNs"], chain["workEndNs"])

    def test_step_windows_use_original_raw_cap_and_new_local_history_only(self):
        inputs = data_inputs()
        for phase, (seconds, soft) in D.STEP_CAPS.items():
            window = {"phase": phase, "clock": O.clock_value(inputs.clock), "originalBootDigest": BOOT,
                "firstNs": 200 * NS, "softEndNs": (200 + soft) * NS, "hardEndNs": (200 + seconds) * NS,
                "localStarted": 1.0, "localScope": "THIS_COMMAND_ONLY"}
            self.assertIs(guarded(D.step_window_record, window, inputs, phase), window)
            for key, value in (("firstNs", True), ("hardEndNs", window["hardEndNs"] + 1),
                ("localStarted", 1), ("localScope", "PREVIOUS_PROCESS"), ("originalBootDigest", "c" * 64)):
                with self.assertRaises(REFUSALS):
                    guarded(D.step_window_record, {**window, key: value}, inputs, phase)

    def test_after_save_old_provider_end_is_only_a_historical_bound(self):
        inputs = data_inputs()
        handoff, produced = b"{}", O.encoded({"observedAfterReturnNs": 50 * NS})
        plan = {"planSha256": "f" * 64}
        handoff = O.encoded(plan)
        chain = private_chain(inputs)
        chain["handoffSha256"] = O.digest(handoff)
        retained = {name: b"{}" for name in D.AFTER_SAVE_FILES}
        retained["private-use-chain.json"] = O.encoded(chain)
        def close(phase, first, closed, local_first, previous_raw, previous_ns, *, leaf=None, chain_raw=None, old=None):
            seconds, soft = D.STEP_CAPS[phase]
            return {"schema": 1, "scope": D.STEP_CLOSE_SCOPE,
                "window": {"phase": phase, "clock": O.clock_value(inputs.clock), "originalBootDigest": BOOT,
                    "firstNs": first * NS, "softEndNs": (first + soft) * NS, "hardEndNs": (first + seconds) * NS,
                    "localStarted": float(local_first), "localScope": "THIS_COMMAND_ONLY"},
                "predecessorSha256": O.digest(previous_raw), "predecessorCheckedNs": previous_ns * NS,
                "privateUseChainSha256": None if chain_raw is None else O.digest(chain_raw),
                "leafSha256": None if leaf is None else O.digest(leaf),
                "leafCheckedNs": None if leaf is None else (closed - 1) * NS,
                "leafCheckedLocal": None if leaf is None else float(local_first + closed - first - 1),
                "historicalBefore": old, "closedNs": closed * NS, "closedLocal": float(local_first + closed - first),
                "resourceCount": 1, "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "nextPhaseAuthority": False,
                "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        readmission = close("save-readmission", 200, 210, 1000, produced, 50, chain_raw=retained["private-use-chain.json"])
        retained["readmission-close.json"] = O.encoded(readmission)
        after = close("save-set-after", 211, 215, 1011, retained["readmission-close.json"], 210, leaf=b"{}",
            old={"rawSha256": "a" * 64, "checkedNs": 40 * NS, "checkedLocal": 900000.0,
                 "localScope": "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND"})
        retained["after-parent-close.json"] = O.encoded(after)
        claims = {name: "success" if name.endswith("OUTCOME") else "d" * 64 for name in D.SAVE_CLAIMS}
        claims.update(HANDOFF_SHA256=O.digest(handoff), PRODUCER_RETURN_SHA256=O.digest(produced))
        common = {"schema": 1, **inputs.admission, "originalClaims": claims, "planSha256": plan["planSha256"],
            "clock": O.clock_value(inputs.clock), "originalBootDigest": BOOT, "providerStorage": "UNPROVEN",
            "providerDeadlineEnforcement": "NOT_ESTABLISHED", "providerRetirement": "NOT_OBSERVED", "writerReturn": D.PENDING,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        observation = close("save-observation", 216, 219, 1016, retained["after-parent-close.json"], 215)
        observed = {**common, "scope": D.SAVE_OBSERVATIONS_SCOPE, "firstPostProviderNs": 200 * NS,
            "firstPostProviderLocal": 1000.0, "providerEndNs": 205 * NS,
            "providerTimeScope": "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME",
            "files": {name: O.digest(raw) for name, raw in retained.items()}, "window": observation["window"]}
        observations_raw = O.encoded(observed)
        observation.update(leafSha256=O.digest(observations_raw), leafCheckedNs=218 * NS, leafCheckedLocal=1018.0)
        return_window = close("save-owner-return", 220, 222, 1020, b"{}", 219)["window"]
        returned = {**common, "scope": D.AFTER_SAVE_SCOPE, "directory": "/model/after-save", "directoryIdentity": [7, 9],
            "observationsSha256": O.digest(observations_raw), "observationOwnerReturn": observation,
            "returnWindow": return_window, "recordedNs": 221 * NS, "recordedLocal": 1021.0}
        raw = O.encoded(returned)
        later_claims = {**claims, "AFTER_SAVE_OUTCOME": "success", "AFTER_SAVE_SHA256": O.digest(raw)}
        args = (observations_raw, retained, inputs, handoff, produced, later_claims,
            O.clocks.Reading(inputs.clock, 500 * NS), Path("/model/after-save"), (7, 9))
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_HISTORICAL_NOW")), \
                patch.object(time, "time", side_effect=AssertionError("NO_HISTORICAL_POLICY_TIME")):
            self.assertEqual(guarded(D.after_save_records, raw, *args)[0], returned)
        for key, value in (("writerReturn", "success"), ("recordedNs", 200 * NS), ("providerStorage", "VERIFIED")):
            bad = O.encoded({**returned, key: value})
            changed = {**later_claims, "AFTER_SAVE_SHA256": O.digest(bad)}
            with self.assertRaises(REFUSALS):
                guarded(D.after_save_records, bad, *args[:5], changed, *args[6:])


class ConnectedSourceControls(unittest.TestCase):
    def test_entry_latch_uses_canonical_before_module_not_native_alias(self):
        self.assertIs(A.B, P.C.N.native)
        self.assertIs(A.C.B, A.B.initial_before)
        raw = section("hosted_initial_recipient_productive_adapter.py", "def _new_run(", "def _new_phase(")
        self.assertIn("entry = C.B.EntryLatch(attempts)", raw)
        self.assertNotIn("entry = B.EntryLatch(attempts)", raw)

    def test_one_canonical_controller_graph_no_admission_construction_or_legacy_owner(self):
        raw = TEXT["hosted_initial_recipient_productive_adapter.py"]
        self.assertIn("C, N, B, O, U = P.C, P.N, P.B, P.O, P.U", raw)
        for forbidden in ("Admission(", "_ProducerParent(", "spec_from_file_location", "SourceFileLoader", "exec(", "compile("):
            self.assertNotIn(forbidden, raw)
        data = TEXT["hosted_initial_recipient_productive_data.py"]
        self.assertNotIn("import hosted_initial_recipient_productive as", data)

    def test_fixed_nine_productive_and_four_step_phase_sequences(self):
        self.assertEqual(A._PRODUCTIVE_PHASES, ("dependency-stage", "empty-seed", "custody-prepare", "configuration",
            "custody-collect", "custody-uninstall", "dependency-export", "save-set-before", "producer-owner-return"))
        self.assertEqual(A._SEQUENCES["after-save"], ("save-readmission", "save-set-after", "save-observation", "save-owner-return"))
        self.assertEqual(A._SEQUENCES["after-probe"], ("custody-readmission", "provider-observation"))
        self.assertEqual(A._PHASES["configuration"], (("producer-work", 600, 600), ("producer-return", 225, 0),
            ("producer-final", 45, 0), ("producer-read", 30, 30)))
        self.assertEqual(A._PHASES["custody-prepare"], (("custody-prepare", 120, 120),))

    def test_driver_observes_function_return_before_completion_and_same45_fence(self):
        driver = section("hosted_initial_recipient_productive.py", "def productive(", "def step(")
        self.assertLess(driver.index("pending = adapter.produce("), driver.index("completed = adapter.complete_productive_handoff("))
        self.assertLess(driver.index("completed = adapter.complete_productive_handoff("), driver.index("adapter.checked_productive_handoff("))
        complete = section("hosted_initial_recipient_productive_adapter.py", "def complete_productive_handoff(",
            "def checked_productive_handoff(")
        self.assertIn("_new_owner(state)", complete)
        self.assertNotIn("_new_phase(", complete)
        self.assertLess(complete.index("complete_attempted=True"), complete.index("state.window.now("))
        self.assertLess(complete.index("owner.close()"), complete.index("_register_output("))
        self.assertIn('"producerStepOutcome": D.PENDING', complete)
        self.assertEqual(len(D.BLOB_NAMES), 31)

    def test_first_error_and_actual_return_refs_precede_fallible_registration(self):
        retain = section("hosted_initial_recipient_productive_adapter.py", "    def _retain(", "    def acquire(")
        self.assertLess(retain.index("_OWNER_RETURNS[id(self)] = returned"), retain.index('getattr(type(value), "close")'))
        launch = section("hosted_initial_recipient_productive_adapter.py", "def _launch_producer(", "def _read_captures(")
        self.assertLess(launch.index("_CHILD_RETURNS[id(native)] = child"), launch.index("_progress(native, child=child"))
        self.assertLess(launch.index("_progress(native, completed="), launch.index("_progress(native, work_accepted=True)"))

    def test_original_cancel_is_exact_same_home_and_late_zero_never_sets_work_success(self):
        cancel = section("hosted_initial_recipient_productive_adapter.py", "def _producer_cancel(", "def _producer_final(")
        self.assertIn("state.phase == 1", cancel)
        self.assertIn('start["home"] == request["gradleHome"]', cancel)
        self.assertIn('start["job"] == request["jobId"]', cancel)
        self.assertIn('cancellation_raw=O.encoded({"schema": 1, "id": request["id"],', cancel)
        for stage in ("writer", "reader"):
            self.assertIn('owner.error("producer-cancellation-' + stage + '-allocation", error, unknown=True)', cancel)
        self.assertNotIn("owner.acquire(", cancel)
        final = section("hosted_initial_recipient_productive_adapter.py", "def _producer_final(", "def _launch_producer(")
        self.assertNotIn("work_accepted=True", final)
        self.assertIn("scope.drain(", final)
        self.assertIn("owner._close_pin(pin)", final)

    def test_reader_requires_actual38_and_exact281_declarations_not_arbitrary_names(self):
        use = section("hosted_initial_recipient_productive_adapter.py", "def _read_use(", "def _read_productive_graph(")
        self.assertIn("len(names) == len(set(names)) == 38", use)
        self.assertIn("C._historical_query_index(query_view, side, originals)", use)
        self.assertIn("len(declared) == len({name for name, *_rest in declared}) == 281", use)
        self.assertIn("len(declared_directories) == len(set(declared_directories)) == 58", use)
        self.assertIn("readback._initial_use_index(", use)
        self.assertIn("now=history[\"firstUseAt\"]", use)
        self.assertNotIn("time.time(", use)
        self.assertNotIn("N.retained_match(", use)

    def test_public_and_private_five_file_packets_remain_distinct_actual_reads(self):
        self.assertEqual(D.STEP_USE_FILES, ("private-use-chain.json", "begin-use.json", "begin-use-index.json",
            "final-use.json", "final-use-index.json"))
        raw = section("hosted_initial_recipient_productive_adapter.py", "def _action_originals(", "def _after_save_history(")
        self.assertIn("for name in readback.INITIAL_USE_FILES", raw)
        self.assertIn("readback.validate_initial_action_return(", raw)
        self.assertIn("use_originals=native", raw)
        self.assertIn("_read_use(reader, row, site", raw)
        self.assertIn('"initial-use-chain.json"', TEXT["hosted_cache_provider_readback.py"])

    def test_large_captures_are_streamed_under_original_caps_not_snapshot_buffers(self):
        raw = section("hosted_initial_recipient_productive_adapter.py", "def _read_capture_original(", "def _productive_window(")
        self.assertIn("min(65536, count - consumed)", raw)
        self.assertIn("67174400", raw)
        self.assertNotIn("b\"\".join", raw)
        self.assertNotIn(".snapshot(", TEXT["hosted_initial_recipient_productive_adapter.py"])
        self.assertIn("134348800", TEXT["hosted_initial_recipient_productive_adapter.py"])

    def test_eight_step_uses_never_move_into_later_observation_or_return_slots(self):
        final = section("hosted_initial_recipient_productive_adapter.py", "def after_save(", "def after_probe(")
        self.assertLess(final.index("_step_final_use("), final.index('state = _new_phase(run, "save-set-after"'))
        later = final[final.index('state = _new_phase(run, "save-set-after"'):]
        self.assertNotIn("_use(", later)
        self.assertNotIn("_step_inputs(", later)
        probe = TEXT["hosted_initial_recipient_productive_adapter.py"].split("def after_probe(", 1)[1]
        self.assertLess(probe.index("_step_final_use("), probe.index('state = _new_phase(run, "provider-observation"'))
        self.assertNotIn("_use(", probe[probe.index('state = _new_phase(run, "provider-observation"'):])
        self.assertIn('"cacheContentsVerified": False, "resolverVerified": False', probe)

    def test_later_lookup_uses_hash_bound_old_post_action_raw_not_its_new_first(self):
        old = section("hosted_initial_recipient_productive_adapter.py", "def _after_save_history(", "def _step_window(")
        self.assertIn('historical_first = O.clocks.Reading(reader.first.clock, observed["firstPostProviderNs"])', old)
        self.assertIn('"save", old_claims, historical_first)', old)
        self.assertNotIn(".now(", old)
        self.assertNotIn("time.time(", old)
        self.assertNotIn("checked_use_parent(", old)
        writer = section("hosted_initial_recipient_productive_adapter.py", "def after_save(", "def after_probe(")
        self.assertNotIn('"AFTER_SAVE_OUTCOME": "success"', writer)
        self.assertNotIn("D.after_save_records(", writer)

    def test_new_readers_authenticate_actual_current_begin_not_identity_equality_alone(self):
        fresh = section("hosted_initial_recipient_productive_adapter.py", "def _fresh_begin(", "def _rederive_inputs(")
        for required in ("result.identity is fresh_identity", "P.checked_consumed_use(result, parent, site) is result",
            "provider._initial_state(entry[3])", "provider._initial_parent_current(state)", "len(state.uses) == 1"):
            self.assertIn(required, fresh)
        derive = section("hosted_initial_recipient_productive_adapter.py", "def rederive_provider_inputs(", "def _reader_failure(")
        self.assertLess(derive.index("_DERIVES[id(handoff)] ="), derive.index("_fresh_begin("))


if __name__ == "__main__":
    unittest.main()
