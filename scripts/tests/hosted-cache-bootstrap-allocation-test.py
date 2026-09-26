#!/usr/bin/env python3
"""Pure source-proposal/trace controls; no real clock, owner, provider or build.

Synthetic service/predecessor/phase records do not establish original custody.
The explicit roster excludes all inherited original-acquisition test methods.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_allocation as A
import hosted_dependency_cache as cache

spec = importlib.util.spec_from_file_location("bootstrap_allocation_original_models",
    Path(__file__).with_name("hosted-cache-bootstrap-origin-test.py"))
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
O = A.origin
NS = 1_000_000_000
EXPECTED = (
    ("productive-entry", 120),
    ("recipient-validation", 240), ("recipient-final", 45), ("recipient-read", 30),
    ("canonical-init", 120), ("canonical-init-final", 45), ("canonical-init-read", 30),
    ("dependency-stage", 120), ("empty-seed", 120),
    ("custody-prepare", 120), ("custody-prepare-final", 45), ("custody-prepare-read", 30),
    ("producer-work", 600), ("producer-return", 225), ("producer-final", 45), ("producer-read", 30),
    ("custody-collect", 120), ("custody-collect-final", 45), ("custody-collect-read", 30),
    ("custody-uninstall", 90), ("custody-uninstall-final", 45), ("custody-uninstall-read", 30),
    ("dependency-export", 120), ("save-set-before", 120), ("producer-owner-return", 45),
    ("save-transition", 30), ("provider-save", 180), ("save-readmission", 120),
    ("save-set-after", 120), ("save-observation", 30), ("save-owner-return", 45),
    ("probe-transition", 30), ("provider-probe", 180), ("custody-readmission", 120),
    ("provider-observation", 30), ("custody-freeze", 180),
    ("custody-encrypt", 240), ("custody-encrypt-final", 45), ("custody-encrypt-read", 30),
    ("ciphertext-open", 90), ("ciphertext-verify", 90), ("custody-owner-return", 45),
    ("seal-transition", 30), ("separate-seal", 120), ("upload-transition", 30),
    ("evidence-upload", 180), ("upload-after-guard", 30), ("delivery-return", 45),
)
COPIERS = ("empty-seed", "dependency-export", "save-set-before", "save-set-after")


class Fixture(M.OfflineCase):
    def setUp(self):
        super().setUp()
        self.responses = self.originals()
        self.proposal = self.derive()
        self.proposal_raw = O.encoded(self.proposal)
        self.predecessor_raw = b'{"scope":"SYNTHETIC_PREDECESSOR_NOT_NATIVE_CLOSE_EVIDENCE"}\n'
        self.predecessor = O.clocks.Reading(self.clock, 1003 * NS)

    def originals(self, admitted=None, clock=None, *, jobs_start=1002 * NS):
        admitted = self.admitted if admitted is None else admitted
        clock = self.clock if clock is None else clock
        return {name: M.response(admitted, clock, name, body, start=jobs_start - (1 - index) * NS)
                for index, (name, body) in enumerate(M.service_bodies(admitted, clock).items())}

    def derive(self, responses=None, admitted=None, clock=None):
        return A.derive(self.admitted if admitted is None else admitted,
            self.responses if responses is None else responses, "e" * 32,
            self.clock if clock is None else clock, M.RUNNER)

    def validate(self, raw, responses=None):
        return A.validate_proposal(raw, self.admitted, self.responses if responses is None else responses,
                                   "e" * 32, self.clock, M.RUNNER)

    def count_through(self, name):
        return [phase for phase, _ in EXPECTED].index(name) + 1

    def observations(self, count=48, *, changes=None):
        result, previous, last = [], O.digest(self.predecessor_raw), self.predecessor.nanoseconds
        for index, (name, _) in enumerate(EXPECTED[:count]):
            began = last + 1
            value = {"schema": 1, "scope": A.OBSERVATION_SCOPE, "phase": name, "clock": O.clock_value(self.clock),
                "previousSha256": previous, "beganNs": began, "returnedNs": began + 1,
                "lastNewWorkNs": began if name in COPIERS else None, "originalOutcome": "success",
                "retirement": "KNOWN", "cancelled": False}
            if changes and name in changes:
                value.update(changes[name])
            raw = O.encoded(value)
            result.append(raw)
            previous, last = O.digest(raw), value["returnedNs"]
        return result

    def trace(self, observations, *, proposal_raw=None, predecessor_raw=None, predecessor=None):
        return A.derive_trace(self.proposal_raw if proposal_raw is None else proposal_raw,
            self.admitted, self.responses, "e" * 32, self.clock, M.RUNNER,
            predecessor_raw=self.predecessor_raw if predecessor_raw is None else predecessor_raw,
            predecessor=self.predecessor if predecessor is None else predecessor, observations=observations)

    def validate_trace(self, raw, observations, *, predecessor_raw=None):
        return A.validate_trace(raw, self.proposal_raw, self.admitted, self.responses, "e" * 32, self.clock, M.RUNNER,
            predecessor_raw=self.predecessor_raw if predecessor_raw is None else predecessor_raw,
            predecessor=self.predecessor, observations=observations)


class ArithmeticTests(unittest.TestCase):
    def test_fixed_roster_and_original_end_without_authority_fields(self):
        value = A.fence_arithmetic(1000 * O.NS)
        self.assertEqual(set(value), {"allocationStartBasisNs", "proposedJobEndNs", "phaseFencesNs"})
        self.assertEqual(value["allocationStartBasisNs"], 1750 * O.NS)
        self.assertEqual(value["proposedJobEndNs"], 6400 * O.NS)
        self.assertEqual(len(value["phaseFencesNs"]), 48)
        self.assertEqual(value["phaseFencesNs"]["productive-entry"], 1870 * O.NS)
        self.assertEqual(value["phaseFencesNs"]["delivery-return"], 6400 * O.NS)
        self.assertEqual(A.fence_arithmetic(0)["proposedJobEndNs"], 5400 * O.NS)

    def test_integer_precision_end_boundary_and_no_renewal_or_override(self):
        start = O.clocks.UINT64 - 5400 * O.NS
        self.assertEqual(A.fence_arithmetic(start)["proposedJobEndNs"], O.clocks.UINT64)
        for value in (start + 1, -1, True, 1.0, "1", None):
            with self.subTest(value=value), self.assertRaises(A.AllocationError): A.fence_arithmetic(value)
        for name in ("phases", "job_seconds", "policy", "scope", "authority", "now"):
            with self.subTest(name=name), self.assertRaises(TypeError): A.fence_arithmetic(0, **{name: 5400})


class ProposalTests(Fixture):
    def test_literal_closed_roster_and_4650_second_accounting(self):
        value = self.proposal
        self.assertEqual(A.PHASES, EXPECTED)
        self.assertEqual(len(value["policy"]["phases"]), 48)
        self.assertEqual(value["policy"]["phases"],
            [{"name": name, "maximumSeconds": seconds} for name, seconds in EXPECTED])
        self.assertEqual(value["policy"]["proposedJobSeconds"], 5400)
        self.assertEqual(value["policy"]["allocatedSeconds"], 4650)
        self.assertEqual(value["policy"]["unallocatedSetupHeadroomSeconds"], 750)
        self.assertEqual(value["serviceTimeBasis"]["jobStartBasisNs"], 926 * NS)
        self.assertEqual(value["proposedJobEndNs"], 6326 * NS)
        self.assertEqual(value["allocationStartBasisNs"], 1676 * NS)
        cursor = 1676 * NS
        for name, seconds in EXPECTED:
            cursor += seconds * NS
            self.assertEqual(value["phaseFencesNs"][name], cursor)
        self.assertEqual(cursor, 6326 * NS)

    def test_all_six_cohorts_keep_separate_execution_identity(self):
        for selection in ("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "desktop-macos-x64",
                          "full-macos-arm64", "full-macos-x64"):
            admitted, clock, _ = M.model_admission(selection)
            with self.subTest(selection=selection):
                value = self.derive(self.originals(admitted, clock), admitted, clock)
                self.assertEqual(value["profile"], "cache-bootstrap")
                self.assertEqual(value["selection"], selection)
                self.assertEqual(value["cacheCohort"], O.parse(admitted.record)["cacheCohort"])
                self.assertEqual(value["clock"], O.clock_value(clock))
                self.assertEqual(value["proposedJobEndNs"], 6326 * NS)

    def test_policy_records_inclusive_870_capture_not_990_or_full_7200(self):
        policy = self.proposal["policy"]
        groups = {row["name"]: row for row in policy["nativeCaptureSpans"]}
        self.assertEqual({name: row["maximumSeconds"] for name, row in groups.items()},
            {"recipient": 285, "initializer": 165, "custody-prepare": 165, "producer": 870,
             "custody-collect": 165, "custody-uninstall": 135, "custody-encrypt": 285})
        self.assertEqual(groups["producer"]["phases"], ["producer-work", "producer-return", "producer-final"])
        self.assertEqual(policy["windowsNativeFileSeconds"], 900)
        self.assertEqual(policy["producerReturn"]["seconds"], 225)
        self.assertEqual(policy["producerReturn"]["sameHomeStopSeconds"], 120)
        self.assertIs(policy["producerReturn"]["sameHomeStopIncluded"], True)
        self.assertTrue(all(row["maximumSeconds"] < 900 for row in groups.values()))

    def test_dependency_windows_and_streaming_byte_limits_are_explicit(self):
        value = self.proposal["policy"]["dependencyObservations"]
        self.assertEqual(value, {"phases": list(COPIERS), "hardSeconds": 120, "newWorkSeconds": 90,
            "fileBytes": 536870912, "aggregateBytes": 2147483648,
            "strategy": "STREAM_PER_FILE_NOT_WINDOWS_AGGREGATE_SNAPSHOT"})

    def test_closed_scope_has_no_budget_owner_or_test_acceptance(self):
        value = self.proposal
        self.assertEqual((value["schema"], value["scope"]), (1, "BOOTSTRAP_ALLOCATION_SOURCE_PROPOSAL_V1"))
        self.assertEqual(set(value), {"schema", "scope", "profile", "selection", "cacheCohort", "source", "github",
            "clock", "serviceTimeBasis", "serviceTimeBasisSha256", "policy", "allocationStartBasisNs",
            "proposedJobEndNs", "phaseFencesNs", "budgetAcceptance", "testAcceptance", "productiveOwner",
            "exportSaveAuthority"})
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(value["productiveOwner"], "NOT_CREATED")
        self.assertIs(value["exportSaveAuthority"], False)
        self.assertNotIn("primaryAbiAccounting", value)

    def test_time_passage_and_fresh_prelude_do_not_renew_proposed_fences(self):
        before = copy.deepcopy(self.proposal)
        self.nanoseconds += 10_000 * NS
        O.prelude(O.clocks.Reading(self.clock, self.nanoseconds))
        self.assertEqual(self.derive(), before)
        self.assertEqual(self.fence.work, 1075 * NS)
        self.assertEqual(self.fence.final, 1120 * NS)

    def test_zero_service_basis_does_not_need_an_epoch_clamp(self):
        value = self.derive(self.originals(jobs_start=76 * NS))
        self.assertEqual(value["serviceTimeBasis"]["jobStartBasisNs"], 0)
        self.assertEqual(value["proposedJobEndNs"], 5400 * NS)
        self.assertEqual(value["allocationStartBasisNs"], 750 * NS)

    def test_uint64_end_exactly_representable_and_one_ns_overflow_refused(self):
        maximum = 18_446_744_073_709_551_615
        originals = self.originals(jobs_start=maximum - 5324 * NS)
        self.assertEqual(self.derive(originals)["proposedJobEndNs"], maximum)
        with self.assertRaisesRegex(A.AllocationError, "BOOTSTRAP_ALLOCATION_INTEGER"):
            self.derive(self.originals(jobs_start=maximum - 5324 * NS + 1))

    def test_integer_precision_and_typed_unsigned_boundaries(self):
        value = self.derive(self.originals(jobs_start=9_007_199_254_740_999))
        self.assertEqual(value["proposedJobEndNs"], 9_012_523_254_740_999)
        for invalid in (True, False, "1", 1.0, -1, None, 1 << 64):
            with self.subTest(value=invalid), self.assertRaises(A.AllocationError):
                A.integer(invalid)

    def test_validation_rederives_both_exact_original_responses(self):
        with patch.object(O, "service_identity", wraps=O.service_identity) as checked:
            self.assertEqual(self.validate(self.proposal_raw), self.proposal)
        checked.assert_called_once()
        for label in ("attempt", "jobs"):
            changed = {**self.responses, label: json.dumps(O.parse(self.responses[label]), indent=2).encode()}
            with self.subTest(label=label), self.assertRaisesRegex(A.AllocationError, "PROPOSAL_CHANGED"):
                self.validate(self.proposal_raw, changed)

    def test_original_service_failures_and_identity_substitutions_refuse(self):
        changed = dict(self.responses)
        changed["jobs"] = O.encoded({**O.parse(changed["jobs"]), "retirement": "UNKNOWN"})
        with self.assertRaises(O.OriginError):
            self.derive(changed)
        for admitted in (M.F.model_admission(), replace(self.admitted, original_event=b"{}")):
            with self.assertRaises(ValueError):
                self.derive(admitted=admitted)
        admitted, clock, _ = M.model_admission("desktop-windows-x64")
        with self.assertRaises(O.OriginError):
            self.derive(self.originals(admitted, clock), admitted, replace(clock, ticks_per_second=10_000_001))

    def test_canonical_proposal_bytes_not_parsed_equality(self):
        for raw in (b" " + self.proposal_raw, self.proposal_raw + b"\n", bytearray(self.proposal_raw),
                    json.dumps(self.proposal, indent=2).encode(), None):
            with self.subTest(kind=type(raw).__name__), self.assertRaises(A.AllocationError):
                self.validate(raw)
        for field, item in (("schema", True), ("exportSaveAuthority", 0), ("proposedJobEndNs", 6326 * NS + 1),
                            ("budgetAcceptance", "ADMITTED"), ("productiveOwner", "CREATED"), ("testAcceptance", "PASS")):
            with self.subTest(field=field), self.assertRaises(A.AllocationError):
                self.validate(O.encoded({**self.proposal, field: item}))

    def test_policy_phase_missing_extra_or_changed_cannot_validate(self):
        for mutate in (lambda v: v["policy"].update(proposedJobSeconds=5401),
                       lambda v: v["policy"].update(nativeCaptureSpans=[]),
                       lambda v: v["policy"]["phases"].pop(),
                       lambda v: v["policy"]["dependencyObservations"].update(newWorkSeconds=120),
                       lambda v: v["phaseFencesNs"].update(extra=v["proposedJobEndNs"]),
                       lambda v: v.pop("serviceTimeBasis")):
            value = copy.deepcopy(self.proposal); mutate(value)
            with self.assertRaises(A.AllocationError):
                self.validate(O.encoded(value))

    def test_no_duration_phase_or_authority_override_api(self):
        for field in ("job_seconds", "policy", "phases", "provider", "budget", "now", "trusted"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                A.derive(self.admitted, self.responses, "e" * 32, self.clock, M.RUNNER, **{field: 5400})

    def test_ordinary_budget_and_cache_execution_still_refuse_proposal(self):
        with self.assertRaises(O.wire.BudgetError):
            O.wire.Budget(self.proposal_raw).value
        with self.assertRaisesRegex(cache.files.SeedError, "SEED_BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
            cache.files.require_connected_execution(self.admitted.record)

    def test_import_and_all_pure_apis_do_not_read_clocks_files_or_providers(self):
        source = (ROOT / "scripts/hosted_cache_bootstrap_allocation.py").read_bytes()
        observations = self.observations(1)
        trace_raw = O.encoded(self.trace(observations))
        with ExitStack() as guards:
            for target, name in ((O.clocks, "observe"), (O.time, "monotonic"), (O.time, "time"), (O.time, "sleep"),
                                 (O.wire, "policy"), (cache, "export_snapshot"), (cache, "save_set"),
                                 (Path, "read_bytes"), (Path, "open"), (os, "open")):
                guards.enter_context(patch.object(target, name, side_effect=AssertionError("PURE_ONLY")))
            guards.enter_context(patch("builtins.open", side_effect=AssertionError("PURE_ONLY")))
            namespace = {"__name__": "offline_allocation_import"}
            exec(compile(source, "offline_allocation_import", "exec"), namespace)
            self.assertEqual(namespace["derive"](self.admitted, self.responses, "e" * 32, self.clock, M.RUNNER),
                             self.proposal)
            self.assertEqual(self.validate(self.proposal_raw), self.proposal)
            self.assertEqual(self.validate_trace(trace_raw, observations), O.parse(trace_raw))


class TraceTests(Fixture):
    def test_empty_and_partial_traces_are_not_complete_or_executed(self):
        for count in (0, 1, 47):
            with self.subTest(count=count):
                value = self.trace(self.observations(count))
                self.assertEqual(value["status"], "PREFIX_ONLY_SUPPLIED_TRACE")
                self.assertEqual(len(value["observations"]), count)
                self.assertEqual(value["failureReasons"], [])
                self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
                self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
                self.assertIs(value["exportSaveAuthority"], False)

    def test_complete_48_supplied_observations_remain_non_authorizing(self):
        observations = self.observations()
        value = self.trace(observations)
        self.assertEqual(value["status"], "COMPLETE_SUPPLIED_TRACE")
        self.assertEqual(value["lastNs"], 1003 * NS + 96)
        self.assertEqual(value["lastOriginalSha256"], O.digest(observations[-1]))
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(value["exportSaveAuthority"], False)
        self.assertEqual(self.validate_trace(O.encoded(value), observations), value)

    def test_source_plan_not_digest_alone_is_rederived_for_every_trace(self):
        with patch.object(A, "validate_proposal", wraps=A.validate_proposal) as checked:
            self.trace(self.observations(1))
        checked.assert_called_once()
        for value in (O.encoded({"sha256": O.digest(self.proposal_raw)}),
                      O.encoded({**self.proposal, "proposedJobEndNs": self.proposal["proposedJobEndNs"] + NS})):
            with self.assertRaises(A.AllocationError):
                self.trace(self.observations(1), proposal_raw=value)

    def test_changed_opaque_predecessor_bytes_cannot_validate_prior_trace(self):
        observations = self.observations(0)
        raw = O.encoded(self.trace(observations))
        with self.assertRaisesRegex(A.AllocationError, "TRACE_CHANGED"):
            self.validate_trace(raw, observations, predecessor_raw=self.predecessor_raw + b" ")
        with self.assertRaisesRegex(A.AllocationError, "PREDECESSOR_CHANGED"):
            self.trace(self.observations(1), predecessor_raw=b"another synthetic predecessor")

    def test_first_predecessor_cannot_precede_service_or_change_clock(self):
        for reading in (O.clocks.Reading(self.clock, 1002 * NS),
                        O.clocks.Reading(M.model_admission("desktop-windows-x64")[1], 1003 * NS)):
            with self.subTest(clock=reading.clock), self.assertRaisesRegex(A.AllocationError, "PREDECESSOR_CLOCK"):
                self.trace([], predecessor=reading)

    def test_backwards_first_observation_cannot_be_repaired_by_later_return(self):
        rows = self.observations(1, changes={"productive-entry": {"beganNs": 1003 * NS - 1,
                                                                 "returnedNs": 1004 * NS}})
        with self.assertRaisesRegex(A.AllocationError, "TRACE_BACKWARDS"):
            self.trace(rows)

    def test_backwards_later_start_or_return_is_refused(self):
        for changes in ({"recipient-validation": {"beganNs": 1003 * NS}},
                        {"productive-entry": {"returnedNs": 1003 * NS}}):
            rows = self.observations(2 if "recipient-validation" in changes else 1, changes=changes)
            with self.assertRaisesRegex(A.AllocationError, "TRACE_BACKWARDS"):
                self.trace(rows)

    def test_changed_clock_frequency_domain_or_boolean_units_refuse(self):
        for changed in ({**O.clock_value(self.clock), "ticksPerSecond": True},
                        {**O.clock_value(self.clock), "domain": O.clocks.DARWIN_DOMAIN},
                        O.clock_value(M.model_admission("desktop-windows-x64")[1])):
            rows = self.observations(1, changes={"productive-entry": {"clock": changed}})
            with self.assertRaisesRegex(A.AllocationError, "CLOCK_CHANGED"):
                self.trace(rows)

    def test_phase_repeat_reorder_skip_and_extra_phase_refuse(self):
        rows = self.observations(3)
        for changed in ([rows[1]], [rows[0], rows[0]], [rows[0], rows[2]], list(reversed(rows))):
            with self.assertRaisesRegex(A.AllocationError, "PHASE_OR_FIELDS"):
                self.trace(changed)
        with self.assertRaisesRegex(A.AllocationError, "TRACE_ORIGINALS"):
            self.trace(self.observations() + [rows[0]])

    def test_changed_hash_link_is_not_an_original_predecessor(self):
        rows = self.observations(2, changes={"recipient-validation": {"previousSha256": "f" * 64}})
        with self.assertRaisesRegex(A.AllocationError, "PREDECESSOR_CHANGED"):
            self.trace(rows)

    def test_global_original_cutoff_expires_at_equality_without_new_allowance(self):
        end = self.proposal["phaseFencesNs"]["productive-entry"]
        rows = self.observations(1, changes={"productive-entry": {"beganNs": end, "returnedNs": end + 1}})
        value = self.trace(rows)
        self.assertEqual(value["status"], "FAILED_SUPPLIED_TRACE")
        self.assertEqual(value["failureReasons"], ["PHASE_FENCE_EXPIRED"])
        self.assertEqual(value["observations"][0]["phaseEndNs"], end)
        self.assertEqual(value["lastNs"], end + 1)

    def test_per_phase_maximum_expires_even_before_global_cutoff(self):
        began = 1003 * NS + 1
        value = self.trace(self.observations(1, changes={"productive-entry": {"returnedNs": began + 120 * NS}}))
        self.assertEqual(value["failureReasons"], ["PHASE_FENCE_EXPIRED"])
        self.assertEqual(value["observations"][0]["phaseEndNs"], began + 120 * NS)

    def test_delayed_canonical_return_does_not_renew_225_or_45(self):
        began = 1100 * NS
        changes = {"producer-work": {"beganNs": began, "returnedNs": began + 599 * NS},
            "producer-return": {"beganNs": began + 824 * NS, "returnedNs": began + 825 * NS - 1},
            "producer-final": {"beganNs": began + 869 * NS, "returnedNs": began + 870 * NS - 1}}
        rows = self.observations(self.count_through("producer-final"), changes=changes)
        value = self.trace(rows)
        self.assertEqual(value["failureReasons"], [])
        indexed = {row["observation"]["phase"]: row for row in value["observations"]}
        self.assertEqual(indexed["producer-return"]["nativeCaptureEndNs"], began + 825 * NS)
        self.assertEqual(indexed["producer-final"]["nativeCaptureEndNs"], began + 870 * NS)
        changes["producer-final"]["returnedNs"] = began + 870 * NS
        failed = self.trace(self.observations(self.count_through("producer-final"), changes=changes))
        self.assertEqual(failed["failureReasons"], ["NATIVE_CAPTURE_FENCE_EXPIRED"])

    def test_late_return_at_original_825_is_not_a_fresh_stop_interval(self):
        began = 1100 * NS
        changes = {"producer-work": {"beganNs": began, "returnedNs": began + 599 * NS},
            "producer-return": {"beganNs": began + 824 * NS, "returnedNs": began + 825 * NS}}
        value = self.trace(self.observations(self.count_through("producer-return"), changes=changes))
        self.assertEqual(value["failureReasons"], ["NATIVE_CAPTURE_FENCE_EXPIRED"])

    def test_every_copy_phase_uses_90_new_work_and_120_return_without_snapshot(self):
        for phase in COPIERS:
            count = self.count_through(phase)
            prefix = self.observations(count)
            began = O.parse(prefix[-1])["beganNs"]
            changed = {phase: {"lastNewWorkNs": began + 90 * NS - 1, "returnedNs": began + 120 * NS - 1}}
            with self.subTest(phase=phase):
                value = self.trace(self.observations(count, changes=changed))
                self.assertEqual(value["failureReasons"], [])
                self.assertEqual(value["observations"][-1]["newWorkEndNs"], began + 90 * NS)
                self.assertEqual(value["observations"][-1]["phaseEndNs"], began + 120 * NS)
                changed[phase]["lastNewWorkNs"] = began + 90 * NS
                self.assertEqual(self.trace(self.observations(count, changes=changed))["failureReasons"],
                                 ["NEW_WORK_FENCE_EXPIRED"])

    def test_copy_return_at_120_keeps_late_original_failure(self):
        phase = "dependency-export"; count = self.count_through(phase)
        began = O.parse(self.observations(count)[-1])["beganNs"]
        rows = self.observations(count, changes={phase: {"returnedNs": began + 120 * NS}})
        value = self.trace(rows)
        self.assertEqual(value["status"], "FAILED_SUPPLIED_TRACE")
        self.assertEqual(value["failureReasons"], ["PHASE_FENCE_EXPIRED"])
        self.assertEqual(value["observations"][-1]["originalSha256"], O.digest(rows[-1]))

    def test_new_work_marker_must_match_phase_and_observed_interval(self):
        cases = [(1, {"productive-entry": {"lastNewWorkNs": 1003 * NS + 1}}),
            (self.count_through("empty-seed"), {"empty-seed": {"lastNewWorkNs": None}}),
            (self.count_through("empty-seed"), {"empty-seed": {"lastNewWorkNs": 1002 * NS}})]
        for count, changes in cases:
            with self.assertRaises(A.AllocationError):
                self.trace(self.observations(count, changes=changes))

    def test_failure_cancellation_and_unknown_are_terminal_not_save_permission(self):
        for changes, expected in (({"originalOutcome": "failure"}, ["STEP_NOT_SUCCESSFUL"]),
                ({"originalOutcome": "cancelled"}, ["STEP_NOT_SUCCESSFUL", "CANCELLED"]),
                ({"cancelled": True}, ["CANCELLED"]), ({"retirement": "UNKNOWN"}, ["RETIREMENT_UNKNOWN"]),
                ({"originalOutcome": "skipped"}, ["STEP_NOT_SUCCESSFUL"]),
                ({"originalOutcome": ""}, ["STEP_NOT_SUCCESSFUL"])):
            with self.subTest(changes=changes):
                rows = self.observations(1, changes={"productive-entry": changes})
                value = self.trace(rows)
                self.assertEqual(value["failureReasons"], expected)
                self.assertEqual(value["status"], "FAILED_SUPPLIED_TRACE")
                self.assertIs(value["exportSaveAuthority"], False)
                with self.assertRaisesRegex(A.AllocationError, "TERMINAL_REUSE"):
                    self.trace(self.observations(2, changes={"productive-entry": changes}))

    def test_combined_first_failure_originals_are_not_erased_by_unknown(self):
        rows = self.observations(1, changes={"productive-entry": {
            "originalOutcome": "failure", "cancelled": True, "retirement": "UNKNOWN"}})
        value = self.trace(rows)
        self.assertEqual(value["failureReasons"], ["STEP_NOT_SUCCESSFUL", "CANCELLED", "RETIREMENT_UNKNOWN"])
        self.assertEqual(value["observations"][0]["observation"], O.parse(rows[0]))
        self.assertEqual(value["observations"][0]["originalSha256"], O.digest(rows[0]))

    def test_complete_trace_cannot_claim_provider_storage_or_product_success(self):
        rows = self.observations()
        value = self.trace(rows)
        for key, replacement in (("status", "PASSED"), ("budgetAcceptance", "ADMITTED"),
                                 ("testAcceptance", "PASS"), ("exportSaveAuthority", True),
                                 ("providerStored", True), ("productiveOwner", "CREATED")):
            with self.subTest(key=key), self.assertRaisesRegex(A.AllocationError, "TRACE_CHANGED"):
                self.validate_trace(O.encoded({**value, key: replacement}), rows)

    def test_trace_canonical_bytes_and_complete_original_byte_hashes_are_required(self):
        rows = self.observations(1)
        value = self.trace(rows); raw = O.encoded(value)
        for changed in (raw + b" ", b"\n" + raw, bytearray(raw), json.dumps(value, indent=2).encode()):
            with self.assertRaises(A.AllocationError):
                self.validate_trace(changed, rows)
        reserialized = [json.dumps(O.parse(rows[0]), indent=2).encode()]
        self.assertEqual(O.parse(rows[0]), O.parse(reserialized[0]))
        with self.assertRaisesRegex(A.AllocationError, "TRACE_CHANGED"):
            self.validate_trace(raw, reserialized)

    def test_replayed_consistent_supplied_trace_never_claims_actual_single_use(self):
        rows = self.observations()
        first = self.trace(rows)
        replay = self.trace(tuple(bytes(bytearray(raw)) for raw in rows))
        self.assertEqual(first, replay)
        self.assertEqual(replay["consistencyScope"], "SUPPLIED_PREFIX_NOT_ORIGINAL_OUTCOME_CUSTODY_OR_SINGLE_USE")
        self.assertIs(replay["exportSaveAuthority"], False)

    def test_malformed_types_original_sizes_and_closed_dispositions_refuse(self):
        for changes in ({"schema": True}, {"beganNs": True}, {"returnedNs": 1.0}, {"extra": True},
                        {"originalOutcome": True}, {"retirement": "RETIRED"}, {"cancelled": 0}):
            with self.subTest(changes=changes), self.assertRaises(A.AllocationError):
                self.trace(self.observations(1, changes={"productive-entry": changes}))
        for rows in (None, {}, [bytearray(self.observations(1)[0])], [b" " * 16385]):
            with self.assertRaises(A.AllocationError):
                self.trace(rows)
        for raw in (b"", bytearray(self.predecessor_raw), b"x" * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(A.AllocationError):
                self.trace([], predecessor_raw=raw)


def load_tests(loader, _tests, _pattern):
    suite = unittest.TestSuite()
    for case in (ProposalTests, TraceTests):
        suite.addTests(case(name) for name in sorted(case.__dict__) if name.startswith("test_"))
    return suite


if __name__ == "__main__":
    unittest.main()
