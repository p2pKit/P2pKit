#!/usr/bin/env python3
"""Focused AST/memory controls, NOT a controller/leaf/native/hosted execution.

Only the new parent definitions run. Original collection binding, leaf, clock,
allocation, signals and directories are explicit models; no old fixture/suite
is imported. The real leaf's earlier results remain in their own reviewed scope.
"""
import ast
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace as NS
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "run-hosted-cache-bootstrap.py"
TREE = ast.parse(SOURCE.read_text())
SELECTED = ast.Module(body=[node for node in TREE.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    and node.name in ("NoLoaderPrefix", "_no_loader_parent_controls")], type_ignores=[])
assert len(SELECTED.body) == 2
CODE = compile(SELECTED, str(SOURCE), "exec", dont_inherit=True)
NS_PER_SECOND = 1_000_000_000


class Refusal(RuntimeError):
    pass


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False

    def __setattr__(self, name, value):
        raise RuntimeError("annotation unavailable")

    def __str__(self):
        raise RuntimeError("string unavailable")


def require(value, reason):
    if not value:
        raise Refusal(reason)


def integer(value):
    require(type(value) is int and 0 <= value <= 2**64 - 1, "INTEGER")
    return value


def local(value):
    require(type(value) in (int, float) and 0 <= value < float("inf"), "LOCAL")
    return float(value)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


@dataclass(frozen=True)
class Home:
    request_raw: bytes
    admitted_raw: bytes
    canonical_raw: bytes
    home_identity: tuple


@dataclass(frozen=True)
class Evidence:
    raw: bytes
    local_started: float
    checked_local: float


class Transition:
    pass


class World:
    def __init__(self):
        self.local, self.raw = 100.0, 500 * NS_PER_SECOND
        self.clock = NS(role="linux-x64", boot="modeled-boot", domain="modeled-raw")
        self.transition, self.binding = Transition(), object()
        self.begin_calls = self.leaf_calls = self.close_calls = 0
        self.before_begin = self.before_leaf = self.after_acquire = self.before_return = lambda: None
        self.callback_hook = self.raw_hook = self.signal_hook = self.encode_hook = lambda *args: None
        self.changed = False
        self.init_present = False
        self.close_failure = self.begin_failure = None
        self.directories, self.owners = [], []
        self.quarantine = []
        self.signals = {2: object(), 15: object()}
        self.original_signals = self.signals.copy()
        self.fences = {name: self.raw + seconds * NS_PER_SECOND for name, seconds in
            (("custody-uninstall", 300), ("custody-uninstall-final", 400), ("custody-uninstall-read", 500))}
        self.job_end = self.raw + 600 * NS_PER_SECOND
        self.saved = NS(clock=self.clock, proposal_raw=b"proposal", admitted=NS(record=b"admission"),
            responses={}, invocation="modeled", runner_name="modeled", canonical_raw=b"canonical",
            directories={"gradle-home": (10, 20)})
        self.bound = NS(transition=self.transition, returned=NS(raw=b"collection", checked_ns=self.raw - 1,
            checked_local=self.local - 1), pin=NS(frame=NS(predecessor=NS(frame=NS(originals=self.saved,
            callbacks=(self.callback,))), bound=NS(returned=NS(request_raw=b"request"))), graph=NS(nodes=[])))
        world = self

        class Directory:
            def __init__(self):
                self.closes = 0
                world.directories.append(self)

            def close(self):
                self.closes += 1
                world.close_calls += 1
                if world.close_failure is not None:
                    raise world.close_failure

        self.directory_kind = Directory
        self.factory = Directory

        class Inputs:
            def __init__(self, originals):
                require(type(originals) is Home, "INPUT_KIND")
                self.originals, self.pin, self.kind = originals, tuple(vars(originals).values()), Directory

            def unchanged(self):
                require(tuple(vars(self.originals).values()) == self.pin, "INPUT_CHANGED")

            def binding(self):
                return {"modeledOriginalHome": list(self.originals.home_identity)}

        self.leaf = NS(observe_absence=self.observe, HomeOriginals=Home, AbsenceEvidence=Evidence,
            _Inputs=Inputs, _capture=lambda value: tuple(vars(value).values()), SCOPE="MODELED_LEAF_SCOPE")
        origin = NS(OriginError=Refusal, NS=NS_PER_SECOND, integer=integer, encoded=self.encode,
            parse=lambda raw: json.loads(raw), digest=lambda raw: hashlib.sha256(raw).hexdigest(),
            clock_value=lambda clock: vars(clock).copy(), clocks=NS(observe=self.observe_clock,
                validate_reading=lambda reading: reading, checked_now=self.checked_clock),
            wire=NS(_directed_deadline=lambda began, seconds, end, now:
                began + min(seconds, (end - now) / NS_PER_SECOND)))
        self.namespace = {"__name__": "no_loader_parent_memory", "dataclass": dataclass, "field": field,
            "require": require, "threading": threading, "NewEntryTransition": Transition,
            "_begin_no_loader_after_entry": self.begin, "_checked_no_loader_origin": self.checked,
            "_no_loader_origin_roots": lambda: None, "no_loader": self.leaf, "origin": origin,
            "staging": NS(_local=local, _clock=lambda clock: tuple(vars(clock).values())),
            "time": NS(monotonic=self.monotonic), "allocation": NS(validate_proposal=self.proposal),
            "signal": NS(SIGINT=2, SIGTERM=15, getsignal=lambda number: self.signals[number], signal=self.set_signal),
            "diagnostics": NS(_exception_detail=lambda failure: {"retirementUnknown": False}, _QUARANTINE=[]),
            "query": NS(QUARANTINE=[]), "QUARANTINE": self.quarantine,
            "cancellation": lambda values: require(not values, "CANCELLED"), "LIMIT": 2 * 1024 * 1024}
        exec(CODE, self.namespace)
        self.run, self.closed_return = self.namespace["_no_loader_parent_controls"]()

    def state(self):
        cells = dict(zip(self.run.__code__.co_freevars, self.run.__closure__))
        return cells["calls"].cell_contents[id(self.transition)]

    def monotonic(self):
        self.local += 0.001
        return self.local

    def checked_clock(self, clock, *, minimum_ns):
        self.raw_hook()
        self.raw += 1_000_000
        require(clock is self.clock and self.raw >= minimum_ns, "RAW_BACKWARDS")
        return self.raw

    def observe_clock(self):
        return NS(clock=self.clock, nanoseconds=self.raw)

    def proposal(self, *args):
        require(args == (self.saved.proposal_raw, self.saved.admitted, self.saved.responses,
                        self.saved.invocation, self.saved.clock, self.saved.runner_name), "PROPOSAL_INPUTS")
        return {"phaseFencesNs": self.fences, "proposedJobEndNs": self.job_end}

    def callback(self):
        self.callback_hook()

    def set_signal(self, number, handler):
        self.signals[number] = handler
        self.signal_hook(number, handler)

    def encode(self, value):
        self.encode_hook(value)
        return encoded(value)

    def begin(self, transition):
        self.begin_calls += 1
        self.before_begin()
        require(transition is self.transition and self.begin_calls == 1, "ORIGINAL_BEGIN")
        if self.begin_failure is not None:
            raise self.begin_failure
        return self.binding

    def checked(self, binding):
        require(binding is self.binding and not self.changed, "ORIGINAL_CHANGED")
        return self.bound

    def observe(self, owner, originals):
        self.leaf_calls += 1
        self.owners.append(owner)
        self.before_leaf()
        began = self.monotonic()
        for label in ("home", "init") if self.init_present else ("home",):
            owner.acquire("bootstrap-collection-no-loader-" + label, self.factory)
        self.after_acquire()
        for row in reversed(owner.resources):
            owner.close_one(row["owner"])
        owner.end()
        value = {"schema": 1, "scope": self.leaf.SCOPE, "binding": self.leaf._Inputs(originals).binding(),
            "completed": True, "observationState": "EXACT_TARGET_ABSENT_AT_LISTINGS",
            "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL", "leafHandleClose": "KNOWN",
            "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "producerAndCollectionReturn": "NOT_OBSERVED_HERE",
            "historicalLoaderExecution": "NOT_OBSERVED", "otherInitializerContents": "NOT_INSPECTED",
            "deletionPerformed": False, "fileContentsRead": False,
            "observationBoundary": "PINNED_LISTINGS_AND_SAME_HANDLE_VERIFY_NOT_ATOMIC_OR_HISTORICAL_ABSENCE",
            "dependencyPopulation": "NOT_ATTESTED", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "nextPhaseAuthority": False, "exportSaveAuthority": False,
            "initDirectory": "OBSERVED_DIRECTORY" if self.init_present else "ABSENT_IN_HOME_LISTINGS",
            "listings": [{}] * (4 if self.init_present else 2),
            "localWindow": {"started": began, "end": began + 90, "observed": self.monotonic(),
                "scope": "LOCAL90_SHORTENS_CALLER_NOT_SHARED_CLOCK_OR_JOB_ADMISSION"}}
        self.leaf_value = value
        self.before_return()
        self.leaf_return = Evidence(encoded(value), began, self.monotonic())
        return self.leaf_return


class ParentModels(unittest.TestCase):
    def setUp(self):
        self.w = World()

    def success(self):
        result = self.w.run(self.w.transition)
        self.assertTrue(self.w.state()["complete"])
        self.assertEqual(self.w.signals, self.w.original_signals)
        self.assertIs(result.leaf, self.w.leaf_return)
        self.assertEqual((self.w.begin_calls, self.w.leaf_calls), (1, 1))
        self.assertTrue(all(value.closes == 1 for value in self.w.directories))
        return json.loads(result.raw)

    def refusal(self, text=None):
        with self.assertRaises(Refusal) as caught:
            self.w.run(self.w.transition)
        if text is not None:
            self.assertIn(text, str(caught.exception))
        self.assertFalse(self.w.state()["complete"])
        self.assertEqual(self.w.signals, self.w.original_signals)
        return caught.exception

    def test_absent_init_completes_directory_only(self):
        value = self.success()
        self.assertEqual(value["resourceCount"], 1)
        self.assertEqual(value["operation"], "OBSERVE_EXACT_LOADER_NOT_UNINSTALL")
        self.assertFalse(value["nextPhaseAuthority"] or value["exportSaveAuthority"])
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")

    def test_present_init_closes_two_handles_once(self):
        self.w.init_present = True
        self.assertEqual(self.success()["resourceCount"], 2)

    def test_repeat_does_not_reinvoke_original(self):
        self.success()
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            self.w.run(self.w.transition)
        self.assertEqual(self.w.begin_calls, 1)

    def test_reentry_is_claimed_before_begin(self):
        def reentry():
            with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
                self.w.run(self.w.transition)
        self.w.before_begin = reentry
        self.success()

    def test_prior_original_cannot_be_adopted(self):
        self.w.begin(self.w.transition)
        self.refusal("ORIGINAL_BEGIN")
        self.assertEqual(self.w.leaf_calls, 0)

    def test_actual_begin_return_retained_before_lookup_failure(self):
        self.w.before_begin = lambda: setattr(self.w, "changed", True)
        self.refusal("ORIGINAL_CHANGED")
        self.assertIs(self.w.state()["binding"], self.w.binding)
        self.assertEqual(self.w.leaf_calls, 0)

    def test_falsey_unannotatable_begin_failure_is_original(self):
        failure = self.w.begin_failure = FalseyFailure()
        with self.assertRaises(FalseyFailure) as caught:
            self.w.run(self.w.transition)
        self.assertIs(caught.exception, failure)
        self.assertIs(self.w.state()["original"], failure)
        self.assertEqual(self.w.leaf_calls, 0)

    def test_raw_start_cannot_precede_collection(self):
        self.w.bound.returned.checked_ns = self.w.raw + 1
        self.refusal("PREDECESSOR_CLOCK")

    def test_local_start_cannot_precede_collection(self):
        self.w.bound.returned.checked_local = self.w.local + 1
        self.refusal("PREDECESSOR_CLOCK")

    def test_original_allocation_exhaustion_is_not_renewed(self):
        self.w.fences["custody-uninstall"] = self.w.raw
        self.refusal("NO_INTERVAL")
        self.assertEqual(self.w.leaf_calls, 0)

    def test_original_phase_and_job_fences_intersect_cumulative_caps(self):
        first = self.w.raw
        self.w.fences["custody-uninstall"] = first + 20 * NS_PER_SECOND
        self.w.job_end = first + 100 * NS_PER_SECOND
        ends = self.success()["globalEndsNs"]
        self.assertEqual(ends, {"custody-uninstall": first + 20 * NS_PER_SECOND,
            "custody-uninstall-final": first + 100 * NS_PER_SECOND,
            "custody-uninstall-read": first + 100 * NS_PER_SECOND})

    def test_work_expiry_still_closes_known_directory(self):
        self.w.after_acquire = lambda: setattr(self.w, "raw", self.w.raw + 91 * NS_PER_SECOND)
        self.refusal("EXPIRED")
        self.assertEqual(self.w.close_calls, 1)
        self.assertFalse(self.w.state()["unknown"])

    def test_local_work_expiry_refuses_without_raw_expiry(self):
        self.w.after_acquire = lambda: setattr(self.w, "local", self.w.local + 91)
        self.refusal("EXPIRED")
        self.assertEqual(self.w.close_calls, 1)

    def test_final_expiry_still_closes_known_directories(self):
        self.w.init_present = True
        self.w.after_acquire = lambda: setattr(self.w, "raw", self.w.raw + 200 * NS_PER_SECOND)
        self.refusal("EXPIRED")
        self.assertEqual(self.w.close_calls, 2)
        self.assertFalse(self.w.state()["unknown"])

    def test_advance_keeps_its_actual_raw_highwater(self):
        changed = []
        def raw_hook():
            phases = self.w.state()["phases"]
            if len(phases) == 2:
                if not changed:
                    self.w.raw += 10 * NS_PER_SECOND
                    changed.append(True)
                elif len(changed) == 1:
                    self.w.raw -= 5 * NS_PER_SECOND
                    changed.append(True)
        self.w.raw_hook = raw_hook
        self.refusal("RAW_BACKWARDS")
        self.assertEqual(self.w.close_calls, 1)

    def test_late_restore_cannot_restart_read_allowance(self):
        def restored(number, handler):
            if handler is self.w.original_signals[number]:
                self.w.raw += 46 * NS_PER_SECOND
        self.w.signal_hook = restored
        self.refusal("EXPIRED")

    def test_cancellation_stops_work_and_restores_handlers(self):
        self.w.before_leaf = lambda: self.w.signals[2](2, None)
        self.refusal("CANCELLED")
        self.assertEqual(self.w.close_calls, 0)

    def test_owner_has_no_writable_flags_or_file_writer(self):
        def check_owner():
            owner = self.w.owners[-1]
            for name in ("closed", "unknown", "resources", "cancelled"):
                with self.assertRaises(AttributeError):
                    setattr(owner, name, None)
            self.assertFalse(hasattr(owner, "write") or hasattr(owner, "new"))
        self.w.before_leaf = check_owner
        self.success()

    def test_invalid_label_never_calls_factory(self):
        def invalid():
            self.w.owners[-1].acquire("writer", lambda: self.fail("factory ran"))
        self.w.before_leaf = invalid
        self.refusal("RESOURCE")

    def test_wrong_kind_return_is_retained_unknown_not_closed(self):
        value = object()
        self.w.factory = lambda: value
        self.refusal("BORROWED_RESOURCE")
        self.assertIs(self.w.state()["returns"][0], value)
        self.assertTrue(self.w.state()["unknown"])
        self.assertEqual(self.w.close_calls, 0)

    def test_predecessor_handle_is_not_borrowed_or_closed(self):
        value = self.w.directory_kind()
        self.w.bound.pin.graph.nodes = [(value, type(value), "opaque", None)]
        self.w.factory = lambda: value
        self.refusal("BORROWED_RESOURCE")
        self.assertEqual(value.closes, 0)

    def test_duplicate_handle_does_not_become_new_obligation(self):
        value = self.w.directory_kind()
        self.w.init_present = True
        self.w.factory = lambda: value
        self.refusal("BORROWED_RESOURCE")
        self.assertEqual(len(self.w.state()["pins"]), 1)
        self.assertEqual(value.closes, 0)  # UNKNOWN quarantines rather than retrying.

    def test_erased_public_row_keeps_private_original(self):
        self.w.after_acquire = lambda: self.w.owners[-1].resources.clear()
        self.refusal("ROSTER")
        self.assertIs(self.w.state()["pins"][0][2], self.w.directories[0])
        self.assertTrue(self.w.state()["unknown"])

    def test_changed_row_key_count_refuses_before_success(self):
        self.w.after_acquire = lambda: self.w.owners[-1].resources[0].update(extra=True)
        self.refusal("ROSTER")
        self.assertTrue(self.w.state()["unknown"])

    def test_native_close_failure_is_never_retried(self):
        failure = self.w.close_failure = Refusal("CLOSE_FAILED")
        self.assertIs(self.refusal("CLOSE_FAILED"), failure)
        self.assertEqual(self.w.close_calls, 1)
        self.assertTrue(self.w.state()["pins"][0][4])
        self.assertFalse(self.w.state()["pins"][0][5])

    def test_falsey_body_failure_survives_secondary_close(self):
        first = FalseyFailure()
        self.w.close_failure = Refusal("SECONDARY_CLOSE")
        def fail():
            raise first
        self.w.after_acquire = fail
        with self.assertRaises(FalseyFailure) as caught:
            self.w.run(self.w.transition)
        self.assertIs(caught.exception, first)
        self.assertEqual(self.w.close_calls, 1)
        self.assertTrue(self.w.state()["unknown"])

    def test_actual_malformed_leaf_return_is_retained(self):
        value = object()
        self.w.leaf.observe_absence = lambda owner, originals: value
        self.w.run = self.w.namespace["_no_loader_parent_controls"]()
        self.refusal("LEAF_KIND")
        self.assertIs(self.w.state()["leaf"], value)

    def test_changed_leaf_after_capture_cannot_return(self):
        def mutate():
            leaf = self.w.state()["leaf"]
            if leaf is not None:
                vars(leaf)["checked_local"] += 0.001
        self.w.callback_hook = mutate
        self.refusal("LEAF_CHANGED")

    def test_leaf_cannot_promote_export_acceptance(self):
        self.w.before_return = lambda: self.w.leaf_value.update(exportSaveAuthority=True)
        self.refusal("LEAF_DISPOSITION")

    def test_leaf_listing_count_matches_actual_new_handles(self):
        self.w.before_return = lambda: self.w.leaf_value.update(listings=[{}] * 4)
        self.refusal("LEAF_DISPOSITION")

    def test_partial_handler_install_keeps_restore_duty(self):
        attempted = []
        def partial(number, handler):
            if not attempted:
                attempted.append(True)
                raise Refusal("PARTIAL_INSTALL")
        self.w.signal_hook = partial
        self.refusal("PARTIAL_INSTALL")
        self.assertEqual(self.w.leaf_calls, 0)

    def test_final_encoding_failure_has_no_success_or_new_close(self):
        def fail(value):
            if value.get("scope") == "BOOTSTRAP_NO_LOADER_PARENT_CLOSED_OBSERVATIONS_V1":
                raise Refusal("FINAL_ENCODING")
        self.w.encode_hook = fail
        self.refusal("FINAL_ENCODING")
        self.assertEqual(self.w.close_calls, 1)


class ReviewBoundaryModels(unittest.TestCase):
    def test_inner_preclose_reentry_does_not_close_twice(self):
        world, armed = World(), []
        world.after_acquire = lambda: armed.append(True)
        def reenter():
            if armed:
                armed.clear()
                world.owners[-1].close_one(world.directories[0])
        world.raw_hook = reenter
        world.run(world.transition)
        self.assertEqual(world.close_calls, 1)

    def test_inner_preclose_global_quarantine_prevents_close(self):
        world, armed = World(), []
        world.after_acquire = lambda: armed.append(True)
        def change():
            if armed:
                armed.clear()
                world.namespace["query"].QUARANTINE.append(object())
        world.raw_hook = change
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(world.close_calls, 0)
        self.assertFalse(world.state()["pins"][0][4])
        self.assertTrue(world.state()["unknown"])

    def test_failed_advance_raw_keeps_prior_valid_local_reading(self):
        world, armed, failures = World(), [], []
        original = Refusal("ADVANCE_RAW_FAILURE")
        def monotonic():
            if len(world.state()["phases"]) == 2:
                if not armed:
                    armed.append(True)
                    return 150.0
                return 149.0
            return world.monotonic()
        def raw():
            if armed == [True]:
                armed.append(False)
                raise original
        def detail(failure):
            failures.append(failure)
            return {"retirementUnknown": False}
        world.namespace["time"].monotonic = monotonic
        world.namespace["diagnostics"]._exception_detail = detail
        world.raw_hook = raw
        with self.assertRaises(Refusal) as caught:
            world.run(world.transition)
        self.assertIs(caught.exception, original)
        self.assertTrue(any(failure.args == ("BOOTSTRAP_NO_LOADER_PARENT_LOCAL_BACKWARDS",) for failure in failures))

    def test_final_encoding_or_sample_cancellation_prevents_return(self):
        for boundary in ("encoding", "final-sample"):
            with self.subTest(boundary=boundary):
                world, armed = World(), []
                def encode(value):
                    if value.get("scope") == "BOOTSTRAP_NO_LOADER_PARENT_CLOSED_OBSERVATIONS_V1":
                        if boundary == "encoding":
                            world.state()["cancelled"].append(2)
                        else:
                            armed.append(True)
                def raw():
                    if armed:
                        armed.clear()
                        world.state()["cancelled"].append(2)
                world.encode_hook, world.raw_hook = encode, raw
                with self.assertRaisesRegex(Refusal, "CANCELLED"):
                    world.run(world.transition)
                self.assertEqual(world.close_calls, 1)
                self.assertFalse(world.state()["complete"])

    def test_inner_preclose_clock_unknown_prevents_close_dispatch(self):
        world, armed = World(), []
        failure = Refusal("INNER_CLOCK_UNKNOWN")
        world.after_acquire = lambda: armed.append(True)
        def change():
            if armed:
                armed.clear()
                world.owners[-1].error("modeled-inner-clock", failure, unknown=True)
        world.raw_hook = change
        with self.assertRaises(Refusal) as caught:
            world.run(world.transition)
        self.assertIs(caught.exception, failure)
        self.assertEqual(world.close_calls, 0)
        self.assertFalse(world.state()["pins"][0][4])
        self.assertIs(world.state()["pins"][0][2], world.directories[0])
        self.assertTrue(world.state()["unknown"])

    def test_inner_preclose_clock_row_change_prevents_close_dispatch(self):
        world, armed = World(), []
        world.after_acquire = lambda: armed.append(True)
        def change():
            if armed:
                armed.clear()
                world.owners[-1].resources[0]["extra"] = True
        world.raw_hook = change
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(world.close_calls, 0)
        self.assertFalse(world.state()["pins"][0][4])
        self.assertIs(world.state()["pins"][0][2], world.directories[0])
        self.assertTrue(world.state()["unknown"])


if __name__ == "__main__":
    unittest.main()
