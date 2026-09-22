#!/usr/bin/env python3
"""Action receipt binding controls; no actual Action/provider/custody acceptance.

Wire/clock/step inputs are synthetic. The command controls AST-select existing
definitions over memory-file/admission models; they never import the complete
controller or initial-recipient receiver. No process, network or provider runs.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import hosted_cache_provider_readback as R

L, O = R.launch, R.outer
SECOND = L.clocks.NS


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "tests" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


C = load("action_return_contract_fixture", "hosted-cache-provider-contract-test.py")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Fixture:
    def __init__(self, case, phase="save"):
        contract = C.ProviderContract()
        contract.setUp()
        case.addCleanup(contract.doCleanups)
        self.phase = phase
        self.prefix = "SAVE" if phase == "save" else "PROBE"
        self.plan = deepcopy(contract.plan)
        self.clock = L.clocks.ClockIdentity("linux-x64", L.clocks.DOMAINS["linux-x64"], SECOND)
        self.first = L.clocks.Reading(self.clock, 245 * SECOND)
        self.context = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": "linux-x64",
            "frequency": SECOND, "firstNs": str(160 * SECOND), "issuedNs": str(100 * SECOND),
            "hardEndNs": str(280 * SECOND), "workerCutoffNs": str(250 * SECOND), "phase": phase,
            "job": "1" * 32, "outerId": "2" * 32, "innerId": "3" * 32,
            "directory": "/model/prepared/provider", "directoryIdentity": [1, 2],
            "home": "/model/prepared/provider-home", "homeIdentity": [1, 3],
            "node": "/model/tools/node", "toolPath": "/model/tools", "plan": self.plan}
        self.descriptor = {"scope": "BOOTSTRAP_" + self.prefix + "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1",
            "directory": "/model/prepared", "directoryIdentity": [1, 1], "plan": self.plan,
            "planSha256": digest(L.files.encoded(self.plan)), "clock": {"role": self.clock.role,
                "domain": self.clock.domain, "ticksPerSecond": SECOND},
            "providerWindow": {"issuedNs": 100 * SECOND, "hardEndNs": 280 * SECOND, "actualProviderStart": "NOT_OBSERVED"}}
        self.descriptor_raw = L.files.encoded(self.descriptor)
        names = R.BASE_CLAIMS + (R.LOOKUP_CLAIMS if phase == "lookup" else ())
        self.claims = {name: "success" if name.endswith("OUTCOME") else digest(("MODEL_" + name).encode()) for name in names}
        self.claims[self.prefix + "_PREPARATION_SHA256"] = digest(self.descriptor_raw)
        request = L.transport._json(self.context)
        worker_request = L.transport._json({**self.context, "schema": 1})
        references = tuple(O.FileReference(3, digest(b"abc"), (1, number)) for number in range(10, 14))
        transcript = NS(failed=False, worker_exit_code=0, provider_return=NS(kind="success"), observed_ns=240 * SECOND,
            closed_resources=("scope", "retirement-writer", "stdout-reader", "stderr-reader", "packet-reader", "stderr",
                              "stdout", "bundle", "capture_directory", "home", "directory"))
        acknowledgement = O.acknowledge(request, worker_request, transcript, references)
        sources = lambda names: {name: digest(("MODEL_SOURCE_" + name).encode()) for name in names}
        self.prepared = {"scope": "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1", "phase": phase,
            "preparationSha256": digest(self.descriptor_raw), "request": request.decode("ascii"),
            "bindings": sources(L.worker_source.outer_names("linux-x64")),
            "clockBindings": sources(R.clock_source.roster("linux-x64")), "firstNs": self.context["firstNs"],
            "originalClaims": dict(self.claims), "providerExecution": "NOT_PERFORMED", "enclosingActionReturn": "NOT_OBSERVED"}
        self.outputs = {} if phase == "save" else {"cache-primary-key": self.plan["key"],
            "cache-matched-key": self.plan["key"], "cache-hit": "true"}
        self.value = {"scope": "PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1", "phase": phase,
            "preparedSha256": digest(L.files.encoded(self.prepared)), "preparationSha256": digest(self.descriptor_raw),
            "acknowledgement": acknowledgement.decode("ascii"), "acknowledgementSha256": digest(acknowledgement),
            "python": "/model/tools/python3", "workerRequestSha256": digest(worker_request), "outputs": dict(self.outputs),
            "checkedNs": str(244 * SECOND), "originalClaims": dict(self.claims), "enclosingActionReturn": "NOT_OBSERVED",
            "providerAcceptance": "NOT_ESTABLISHED"}
        self.claims[self.prefix + "_OUTCOME"] = "success"
        self.originals = {}
        self.refresh()

    def refresh(self):
        self.originals[R.ACTION_FILES[0]] = L.files.encoded(self.prepared)
        self.value["preparedSha256"] = digest(self.originals[R.ACTION_FILES[0]])
        self.originals[R.ACTION_FILES[1]] = L.files.encoded(self.value)
        self.claims[self.prefix + "_READBACK_SHA256"] = digest(self.originals[R.ACTION_FILES[1]])

    def run(self):
        return R.validate_action_return(self.originals, self.descriptor_raw, self.claims, self.first,
                                       phase=self.phase, outputs=self.outputs)


class ReceiptControls(unittest.TestCase):
    def test_save_and_lookup_bind_original_receipts_without_native_reread_or_new_clock(self):
        for phase in ("save", "lookup"):
            with self.subTest(phase=phase):
                model = Fixture(self, phase)
                before = deepcopy((model.originals, model.claims, model.outputs))
                with patch.object(R, "read_success", side_effect=AssertionError("NO_NATIVE_REREAD")), \
                        patch.object(L.clocks, "observe", side_effect=AssertionError("NO_NEW_CLOCK")):
                    self.assertIsNone(model.run())
                self.assertEqual((model.originals, model.claims, model.outputs), before)
                self.assertEqual(model.value["providerAcceptance"], "NOT_ESTABLISHED")

    def test_failed_skipped_cancelled_or_conclusion_alias_cannot_use_a_valid_hash(self):
        model = Fixture(self)
        for outcome in (None, True, "failure", "cancelled", "skipped", "SUCCESS", ""):
            model.claims["SAVE_OUTCOME"] = outcome
            with self.subTest(outcome=outcome), self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_CLAIMS"):
                model.run()

    def test_missing_previous_save_hash_refuses_lookup(self):
        model = Fixture(self, "lookup")
        del model.claims["SAVE_READBACK_SHA256"]
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_CLAIMS"):
            model.run()

    def test_missing_extra_or_changed_metadata_is_not_replaced_by_a_success_label(self):
        model = Fixture(self)
        for name in R.ACTION_FILES:
            original = model.originals.pop(name)
            with self.assertRaisesRegex(L.ProviderLaunchError, "FILE_ROSTER"):
                model.run()
            model.originals[name] = original + b" "
            with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_HASH"):
                model.run()
            model.originals[name] = original
        model.originals["extra.json"] = b"{}"
        with self.assertRaisesRegex(L.ProviderLaunchError, "FILE_ROSTER"):
            model.run()

    def test_exact_emitted_hash_and_original_preparation_hash_are_required(self):
        for name in ("SAVE_READBACK_SHA256", "SAVE_PREPARATION_SHA256"):
            model = Fixture(self)
            model.claims[name] = digest(b"MODEL_WRONG_ORIGINAL")
            with self.subTest(name=name), self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_HASH"):
                model.run()

    def test_old_hash_only_receipt_cannot_invent_its_missing_acknowledgement(self):
        model = Fixture(self)
        del model.value["acknowledgement"]
        model.refresh()
        with self.assertRaisesRegex(L.ProviderLaunchError, "READBACK_RECORD"):
            model.run()

    def test_changed_ack_or_worker_digest_refuses_even_with_rehashed_outer_receipt(self):
        for field in ("acknowledgementSha256", "workerRequestSha256"):
            model = Fixture(self)
            model.value[field] = digest(b"MODEL_SUBSTITUTION")
            model.refresh()
            with self.subTest(field=field), self.assertRaisesRegex(L.ProviderLaunchError, "ACK_BINDING"):
                model.run()

    def test_truncated_noncanonical_or_failed_ack_is_not_a_successful_original(self):
        model = Fixture(self)
        original = model.value["acknowledgement"]
        failed = json.loads(original)
        failed.update(kind="failed", providerKind="failed", workerExitCode=65)
        for ack in (original[:-1], original + " ", L.transport._json(failed).decode("ascii") + "\n"):
            model.value["acknowledgement"] = ack
            model.value["acknowledgementSha256"] = digest(ack.encode())
            model.refresh()
            with self.assertRaises(L.transport.ProviderReturnError):
                model.run()

    def test_cross_phase_preparation_and_predecessor_substitution_refuse(self):
        for field, value in (("phase", "lookup"), ("preparationSha256", digest(b"OTHER_PREPARATION")),
                             ("originalClaims", {})):
            model = Fixture(self)
            model.prepared[field] = value
            model.refresh()
            with self.subTest(field=field), self.assertRaises(L.ProviderLaunchError):
                model.run()

    def test_request_from_another_run_or_plan_cannot_match_the_original_ack(self):
        for field, value in (("outerId", "4" * 32), ("plan", {"MODEL_CHANGED_PLAN": True})):
            model = Fixture(self)
            context = {**model.context, field: value}
            model.prepared["request"] = L.transport._json(context).decode("ascii")
            model.refresh()
            with self.subTest(field=field), self.assertRaisesRegex(L.transport.ProviderReturnError, "ACK_BINDING"):
                model.run()

    def test_descriptor_plan_path_and_original_window_are_not_caller_choices(self):
        for field, value in (("directory", "/model/other"), ("planSha256", digest(b"MODEL_OTHER_PLAN")),
                             ("providerWindow", {"issuedNs": 100 * SECOND, "hardEndNs": 281 * SECOND,
                                                 "actualProviderStart": "NOT_OBSERVED"})):
            model = Fixture(self)
            model.descriptor[field] = value
            model.descriptor_raw = L.files.encoded(model.descriptor)
            new_hash = digest(model.descriptor_raw)
            model.claims["SAVE_PREPARATION_SHA256"] = new_hash
            for record in (model.prepared, model.value):
                record["preparationSha256"] = new_hash
                record["originalClaims"]["SAVE_PREPARATION_SHA256"] = new_hash
            model.refresh()
            with self.subTest(field=field), self.assertRaises(L.ProviderLaunchError):
                model.run()

    def test_lookup_outputs_must_equal_the_original_action_not_merely_look_like_a_hit(self):
        model = Fixture(self, "lookup")
        for name in model.outputs:
            original = model.outputs[name]
            model.outputs[name] = original + "different"
            with self.subTest(name=name), self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_OUTPUTS"):
                model.run()
            model.outputs[name] = original

    def test_checked_raw_cannot_precede_ack_or_follow_original_post_action_observation(self):
        model = Fixture(self)
        for checked in (239 * SECOND, 246 * SECOND):
            model.value["checkedNs"] = str(checked)
            model.refresh()
            with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
                model.run()

    def test_old_end_is_exclusive_and_historical_receipt_does_not_use_a_fresh_epoch(self):
        model = Fixture(self)
        for observed in (243 * SECOND, 280 * SECOND, 300 * SECOND):
            model.first = L.clocks.Reading(model.clock, observed)
            with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
                model.run()
        model.first = L.clocks.Reading(model.clock, 245 * SECOND)
        self.assertIsNone(model.run())  # Historical original, not a new window.

    def test_other_native_clock_or_full_width_frequency_cannot_be_relabelled(self):
        model = Fixture(self)
        model.first = L.clocks.Reading(L.clocks.ClockIdentity("windows-x64", L.clocks.DOMAINS["windows-x64"],
                                                            2 ** 63 - 1), model.first.nanoseconds)
        with self.assertRaisesRegex(L.ProviderLaunchError, "CLOCK"):
            model.run()

    def test_pending_scope_and_source_rosters_cannot_be_promoted(self):
        for field, value in (("providerAcceptance", "ACCEPTED"), ("enclosingActionReturn", "success")):
            model = Fixture(self)
            model.value[field] = value
            model.refresh()
            with self.subTest(field=field), self.assertRaisesRegex(L.ProviderLaunchError, "READBACK_RECORD"):
                model.run()
        model = Fixture(self)
        model.prepared["clockBindings"]["audit_processes"] = digest(b"MODEL_OTHER_SOURCE")
        model.refresh()
        with self.assertRaisesRegex(L.ProviderLaunchError, "SOURCE_BINDINGS"):
            model.run()


class CallerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only selected-source memory models; no old test suite is run.
        cls.S = load("action_return_save_fixture", "hosted-cache-bootstrap-after-save-command-test.py")
        cls.P = load("action_return_probe_fixture", "hosted-cache-bootstrap-probe-test.py")

    def test_save_binds_receipt_before_admission_and_retains_both_originals(self):
        w = self.S.World()
        w.hooks["action-receipt:save"] = lambda: self.assertEqual(len(w.native_pairs), 0)
        w.run()
        originals, descriptor, claims, first, options = w.action_calls[0]
        self.assertEqual(options, {"phase": "save", "outputs": {}})
        self.assertEqual(descriptor, w.data[w.save_path]["files"]["save-preparation.json"])
        self.assertEqual(first.nanoseconds, w.retained("save-observations.json")["firstPostProviderNs"])
        for name, raw in originals.items():
            self.assertEqual(w.data[w.after_path]["files"][name], raw)
            self.assertEqual(w.retained("save-observations.json")["files"][name], digest(raw))
        self.assertEqual(claims["SAVE_READBACK_SHA256"], digest(originals["provider-readback.json"]))

    def test_missing_save_hash_or_validator_refusal_stops_before_native_admission(self):
        w = self.S.World()
        del w.env["P2PKIT_BOOTSTRAP_SAVE_READBACK_SHA256"]
        with self.assertRaisesRegex(self.S.Refusal, "ORIGINAL_HASHES"):
            w.run()
        self.assertEqual(w.native_pairs, [])
        w = self.S.World()
        def refuse(*args, **kwargs):
            raise self.S.Refusal("MODEL_RECEIPT_REFUSED")
        w.namespace["provider_readback"].validate_action_return = refuse
        with self.assertRaisesRegex(self.S.Refusal, "MODEL_RECEIPT_REFUSED"):
            w.run()
        self.assertEqual(w.native_pairs, [])
        self.assertNotIn("after-save-return.json", w.data.get(w.after_path, {}).get("files", {}))

    def test_final_save_readmission_cannot_replace_original_receipt(self):
        w = self.S.World()
        w.hooks["native-admit:2"] = lambda: w.data[w.save_path]["files"].update({"provider-readback.json": b"{}"})
        with self.assertRaisesRegex(self.S.Refusal, "FINAL_PROVIDER_ORIGINALS_CHANGED"):
            w.run()
        self.assertEqual(w.leaf_calls, 0)

    def test_lookup_binds_new_receipt_and_uses_saved_post_action_raw_for_save_history(self):
        w = self.P.World(after=True)
        w.action_calls.clear()
        w.run()
        self.assertEqual([call[4]["phase"] for call in w.action_calls], ["lookup", "save"])
        lookup, historical = w.action_calls
        self.assertEqual(lookup[3].nanoseconds, 1400 * SECOND)
        self.assertEqual(historical[3].nanoseconds, 1020 * SECOND)
        self.assertEqual(lookup[4]["outputs"], {"cache-primary-key": w.plan["key"],
            "cache-matched-key": w.plan["key"], "cache-hit": "true"})
        self.assertEqual(lookup[2]["PROBE_READBACK_SHA256"], digest(lookup[0]["provider-readback.json"]))
        for name, raw in lookup[0].items():
            self.assertEqual(w.data[w.guard_path]["files"][name], raw)
            self.assertEqual(w.record()["files"][name], digest(raw))

    def test_probe_requires_own_and_predecessor_hashes_and_complete_retained_roster(self):
        w = self.P.World(after=True)
        del w.env["P2PKIT_BOOTSTRAP_PROBE_READBACK_SHA256"]
        with self.assertRaisesRegex(self.P.Refusal, "ORIGINAL_HASHES"):
            w.run()
        self.assertEqual(w.native_pairs, [])
        w = self.P.World()
        w.update_after("save-observations.json", lambda value: value["files"].pop("provider-readback.json"), rehash=True)
        with self.assertRaisesRegex(self.P.Refusal, "OBSERVATIONS_ROSTER"):
            w.run()

    def test_final_probe_readmission_cannot_replace_prepared_original(self):
        w = self.P.World(after=True)
        w.hooks["native-admit:2"] = lambda: w.data[w.probe_path]["files"].update({"provider-prepared.json": b"{}"})
        with self.assertRaisesRegex(self.P.Refusal, "FINAL_PROVIDER_ORIGINALS_CHANGED"):
            w.run()
        self.assertNotIn("probe-result.json", w.data.get(w.guard_path, {}).get("files", {}))


if __name__ == "__main__":
    unittest.main()
