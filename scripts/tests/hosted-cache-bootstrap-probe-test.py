#!/usr/bin/env python3
"""Fixed probe composition over memory files, not hosted/provider evidence.

Selected actual command/Owner/admission composition, historical readers, plan,
inventory and lookup classification execute. The fixture creates its after-save
record with the selected actual after-save command over the same memory models;
no prior test suite runs. Native admission, allocation, source acquisition,
elapsed clocks and private files are modeled. No full runner import, native
file/process/provider, download, build or encrypted custody is executed.
"""
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
prior = runpy.run_path(str(ROOT / "tests/hosted-cache-bootstrap-after-save-command-test.py"), run_name="after_save_fixtures")
selected, require, Refusal, FalseyFailure = (prior[name] for name in ("selected", "require", "Refusal", "FalseyFailure"))
encoded, digest, SECOND = (prior[name] for name in ("encoded", "digest", "SECOND"))
CODE = selected("run-hosted-cache-bootstrap.py", {"_probe_after_save_records", "_probe_preparation_record", "_probe_command",
                                               "prepare_probe", "after_probe_originals"})


def throw(error):
    raise error


class World(prior["World"]):
    def __init__(self, *, after=False):
        super().__init__()
        self.probe_path = self.original_path.with_name(self.original_path.name + "-probe")
        self.guard_path = self.original_path.with_name(self.original_path.name + "-after-probe")
        self.proposal["phaseFencesNs"].update({"probe-transition": 1500 * SECOND, "provider-probe": 1700 * SECOND,
            "custody-readmission": 1900 * SECOND, "provider-observation": 1930 * SECOND})
        self.proposal["proposedJobEndNs"] = 2000 * SECOND
        self.rebind_proposal()
        # Rebind only this synthetic supplied-input graph after extending its
        # modeled proposal. Do not bypass the actual staged-record validators.
        returns = self.value["chain"]["returns"]
        stage_return, seed_return = returns["dependency-stage"]["leaf"], returns["empty-seed"]["leaf"]
        stage_leaf = self.staging.LeafEvidence(self.blobs["stage-leaf.json"], self.stage_raw,
            stage_return["checkedNs"], stage_return["localStarted"], stage_return["checkedLocal"])
        seed = json.loads(self.blobs["seed-leaf.json"])
        seed.update(stageEvidenceSha256=digest(stage_leaf.raw), stageReturnBindingSha256=digest(encoded({
            "rawSha256": digest(stage_leaf.raw), "checkedNs": stage_leaf.checked_ns,
            "localStarted": stage_leaf.local_started, "localChecked": stage_leaf.checked_local})))
        seed["window"]["predecessorSha256"] = digest(stage_leaf.raw)
        seed_leaf = self.staging.LeafEvidence(encoded(seed), self.stage_raw,
            seed_return["checkedNs"], seed_return["localStarted"], seed_return["checkedLocal"])
        self.blobs["seed-leaf.json"] = seed_leaf.raw
        self.blobs["stage-parent.json"] = self.parent_record(stage_leaf, self.blobs["initializer-parent.json"],
                                                           returns["initializer"]["checkedNs"])
        self.blobs["seed-parent.json"] = self.parent_record(seed_leaf, self.blobs["stage-parent.json"],
                                                          returns["dependency-stage"]["parent"]["checkedNs"])
        predecessors = self.map_inputs().predecessors()
        for name in ("export-leaf.json", "before-leaf.json"):
            value = json.loads(self.blobs[name])
            value["predecessors"] = predecessors
            self.blobs[name] = encoded(value)
        self.relink()
        self.prepared.update(handoffSha256=self.expected, producerReturnSha256=digest(encoded(self.returned)))
        self.preparation_bytes()
        exec(CODE, self.namespace)
        result, _, _ = self.namespace["after_save_originals"]([])
        self.env.update(P2PKIT_BOOTSTRAP_AFTER_SAVE_OUTCOME="success", P2PKIT_BOOTSTRAP_AFTER_SAVE_SHA256=result["afterSaveSha256"])
        self.fixture_leaf_calls = self.leaf_calls
        self.after = False
        self.reset_observation(1300, 10.0)  # New process; LOCAL deliberately below all old command LOCAL values.
        self.classifications = []
        actual = self.staging.cache.provider_observation

        def classify(*args, **kwargs):
            self.classifications.append(args[1])
            return actual(*args, **kwargs)

        self.staging.cache.provider_observation = classify
        if after:
            result, _, _ = self.run()
            self.env.update(P2PKIT_BOOTSTRAP_PROBE_PREPARE_OUTCOME="success",
                P2PKIT_BOOTSTRAP_PROBE_PREPARATION_SHA256=result["probePreparationSha256"],
                P2PKIT_BOOTSTRAP_PROBE_OUTCOME="success", P2PKIT_BOOTSTRAP_PROBE_PRIMARY_KEY=self.plan["key"],
                P2PKIT_BOOTSTRAP_PROBE_MATCHED_KEY=self.plan["key"], P2PKIT_BOOTSTRAP_PROBE_HIT="true")
            self.add_action_originals(self.probe_path, "PROBE")
            self.after = True
            self.reset_observation(1400, 5.0)
            self.classifications = []

    def reset_observation(self, raw_seconds, local):
        self.raw_ns, self.local = raw_seconds * SECOND, local
        self.first = self.clocks.Reading(self.clock, self.raw_ns)
        self.events, self.hooks, self.owners, self.handles, self.reads = [], {}, [], [], []
        self.native_pairs, self.native_expected, self.source_calls, self.proposal_calls = [], [], [], []
        self.namespace["sys"].stdout.buffer = io.BytesIO()

    def new_directory(self, path):
        self.hit("new-dir:" + path.name)
        require(path in (self.after_path, self.probe_path, self.guard_path), "MODEL_FIXED_PROBE_TARGET")
        self.add_directory(path, 500 if path == self.after_path else 600 if path == self.probe_path else 700)
        return self.open_directory(path)

    def run(self, *, guarded=False, cancelled=None):
        operation = self.namespace["after_probe_originals" if self.after else "prepare_probe"]
        return self.namespace["guarded"](operation) if guarded else operation([] if cancelled is None else cancelled)

    @property
    def target(self):
        return self.guard_path if self.after else self.probe_path

    def record(self, name=None):
        name = name or ("probe-result.json" if self.after else "probe-preparation.json")
        return json.loads(self.data[self.target]["files"][name])

    def update_after(self, name, change, *, rehash=False):
        files = self.data[self.after_path]["files"]
        value = json.loads(files[name])
        change(value)
        files[name] = encoded(value)
        if rehash:
            observations = json.loads(files["save-observations.json"])
            for member in observations["files"]:
                observations["files"][member] = digest(files[member])
            files["save-observations.json"] = encoded(observations)
            returned = json.loads(files["after-save-return.json"])
            returned["observationsSha256"] = digest(files["save-observations.json"])
            files["after-save-return.json"] = encoded(returned)
            self.env["P2PKIT_BOOTSTRAP_AFTER_SAVE_SHA256"] = digest(files["after-save-return.json"])

    def update_preparation(self, change, *, rehash=True):
        files = self.data[self.probe_path]["files"]
        value = json.loads(files["probe-preparation.json"])
        change(value)
        files["probe-preparation.json"] = encoded(value)
        if rehash:
            self.env["P2PKIT_BOOTSTRAP_PROBE_PREPARATION_SHA256"] = digest(files["probe-preparation.json"])


class PreparationModels(unittest.TestCase):
    def reject(self, world, reason=None):
        with (self.assertRaises(Refusal) if reason is None else self.assertRaisesRegex(Refusal, reason)) as caught:
            world.run()
        self.assertNotIn("probe-preparation.json", world.data.get(world.probe_path, {}).get("files", {}))
        return caught.exception

    def test_actual_preparation_reuses_readers_and_never_repeats_save_walk(self):
        w = World()
        output, fence, hard = w.run()
        value = w.record()
        self.assertEqual(len(w.owners), 1)
        self.assertEqual(len(w.native_pairs), 2)
        self.assertEqual(w.leaf_calls, w.fixture_leaf_calls)
        self.assertEqual(w.classifications, ["save"])  # Historical supplied-record validation, not a provider call.
        self.assertTrue(all(handle.closes == 1 for handle in w.handles))
        self.assertTrue(all(owner.closed and owner.original is None and not owner.unknown for owner in w.owners))
        self.assertEqual(value["originalClaims"]["AFTER_SAVE_SHA256"], w.env["P2PKIT_BOOTSTRAP_AFTER_SAVE_SHA256"])
        self.assertEqual(value["providerWindow"], {"issuedNs": 1300 * SECOND, "hardEndNs": 1480 * SECOND,
                                                  "actualProviderStart": "NOT_OBSERVED"})
        self.assertEqual(value["providerRequest"], {"action": w.plan["provider"]["restore"], "path": w.plan["path"],
            "key": w.plan["key"], "lookupOnly": True, "restoreKeys": [], "failOnCacheMiss": True,
            "enableCrossOsArchive": False, "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"})
        self.assertEqual(value["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(hard, fence.hard_end)
        self.assertEqual(output["probePreparationSha256"], digest(encoded(value)))

    def test_historical_save_end_does_not_constrain_new_probe_transition(self):
        w = World()
        self.assertGreater(w.raw_ns, w.prepared["providerWindow"]["hardEndNs"])
        self.assertLess(w.local, w.retained("save-observations.json")["firstPostProviderLocal"])
        w.run()
        self.assertEqual(w.record()["firstNs"], 1300 * SECOND)

    def test_all_original_outcomes_require_literal_success_before_ownership(self):
        for name in ("PRODUCER_OUTCOME", "SAVE_PREPARE_OUTCOME", "SAVE_OUTCOME", "AFTER_SAVE_OUTCOME"):
            for value in (None, "", "failure", "cancelled", "skipped", "SUCCESS", True):
                with self.subTest(name=name, value=value):
                    w = World()
                    w.env["P2PKIT_BOOTSTRAP_" + name] = value
                    self.reject(w, "ORIGINAL_OUTCOMES")
                    self.assertEqual(w.owners, [])

    def test_missing_malformed_and_wrong_original_hashes_refuse(self):
        for name in ("HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARATION_SHA256", "AFTER_SAVE_SHA256"):
            for value in (None, "A" * 64, "a" * 63, "a" * 64):
                with self.subTest(name=name, value=value):
                    w = World()
                    w.env["P2PKIT_BOOTSTRAP_" + name] = value
                    self.reject(w)

    def test_retained_after_save_member_change_is_not_a_new_baseline(self):
        w = World()
        w.update_after("after-leaf.json", lambda value: value.update(status="FAILED"))
        self.reject(w, "OBSERVATION_CHANGED")

    def test_matching_rehashed_claims_cannot_change_retained_identity_or_disposition(self):
        cases = (("source", {"commit": "f" * 40}), ("selection", "full-macos-x64"),
                 ("providerRetirement", "KNOWN"), ("providerDeadlineEnforcement", "ESTABLISHED"),
                 ("writerReturn", "SUCCESS"), ("exportSaveAuthority", True))
        for name, value in cases:
            with self.subTest(name=name):
                w = World()
                w.update_after("save-observations.json", lambda record: record.update({name: value}), rehash=True)
                self.reject(w)

    def test_matching_rehash_cannot_relabel_after_save_source_byte_set(self):
        for name, value in (("files", []), ("counts", {"hashedBytes": 0}), ("beforeSaveSha256", "f" * 64),
                            ("saveSetInputs", {})):
            with self.subTest(name=name):
                w = World()
                w.update_after("after-leaf.json", lambda record: record.update({name: value}), rehash=True)
                self.reject(w, "AFTER_SAVE_SET_CHANGED")

    def test_original_after_save_closed_parent_and_local_chronology_are_required(self):
        for name, value in (("parentResourceClose", "UNKNOWN"), ("resourceCount", 0), ("closedNs", 999 * SECOND),
                            ("closedLocal", -1.0), ("leafCheckedNs", 9999 * SECOND)):
            with self.subTest(name=name):
                w = World()
                w.update_after("after-parent-close.json", lambda record: record.update({name: value}), rehash=True)
                self.reject(w)

    def test_original_save_post_bound_cannot_be_replaced_with_new_probe_time(self):
        w = World()
        w.update_after("save-observations.json", lambda value: value.update(firstPostProviderNs=w.raw_ns), rehash=True)
        self.reject(w, "PROVIDER_RETURN_BOUND")

    def test_extra_member_duplicate_key_and_noncanonical_after_return_refuse(self):
        for mode in ("extra", "duplicate", "noncanonical"):
            with self.subTest(mode=mode):
                w = World()
                files = w.data[w.after_path]["files"]
                raw = files["after-save-return.json"]
                if mode == "extra":
                    raw = encoded({**json.loads(raw), "trusted": True})
                elif mode == "duplicate":
                    raw = b'{"schema":1,' + raw[1:]
                else:
                    raw = json.dumps(json.loads(raw), indent=2).encode()
                files["after-save-return.json"] = raw
                w.env["P2PKIT_BOOTSTRAP_AFTER_SAVE_SHA256"] = digest(raw)
                with self.assertRaises(ValueError):
                    w.run()

    def test_expired_original_probe_transition_denies_before_native(self):
        w = World()
        w.raw_ns = w.proposal["phaseFencesNs"]["probe-transition"]
        self.reject(w, "^JOB_TIME_LOCAL_DEADLINE$")
        self.assertEqual(w.native_pairs, [])

    def test_native_delay_cannot_restart_first30(self):
        w = World()
        w.hooks["native-admit:1"] = lambda: setattr(w, "local", w.local + 31)
        self.reject(w)
        self.assertEqual(len(w.native_pairs), 1)

    def test_final_same_byte_staging_replacement_is_not_original_file(self):
        w = World()
        w.hooks["native-admit:2"] = lambda: w.data[w.container_path]["infos"].update(
            {"staging.json": replace(w.stage_info, identity=w.ids(999))})
        self.reject(w, "^BOOTSTRAP_SEED_FILE_REPLACED$")

    def test_final_changed_after_save_record_is_rejected(self):
        w = World()
        w.hooks["native-admit:2"] = lambda: w.update_after("after-leaf.json", lambda value: value.update(status="FAILED"))
        self.reject(w, "FINAL_AFTER_SAVE_CHANGED")

    def test_token_ambient_overrides_and_mutated_original_outcome_refuse(self):
        for kind in ("token", "override", "mutated"):
            with self.subTest(kind=kind):
                w = World()
                if kind == "token":
                    w.env[w.origin.wire.TOKEN_ENV] = "not-a-token"
                elif kind == "override":
                    w.env["JAVA_TOOL_OPTIONS"] = "-Dmodeled=true"
                else:
                    w.hooks["native-admit:2"] = lambda: w.env.update(P2PKIT_BOOTSTRAP_AFTER_SAVE_OUTCOME="failure")
                self.reject(w)

    def test_prepare_close_unknown_preserves_original_and_pending_not_digest(self):
        w = World()
        error = FalseyFailure("modeled-prepare-close")
        w.hooks["close-file:probe-preparation.json"] = lambda: throw(error)
        with self.assertRaises(FalseyFailure) as caught:
            w.run(guarded=True)
        self.assertIs(caught.exception, error)
        self.assertTrue(w.owners[-1].unknown)
        self.assertEqual(w.namespace["sys"].stdout.buffer.getvalue(), b"")
        self.assertEqual(w.record()["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")

    def test_prepare_late_output_flush_cannot_convert_pending_to_success(self):
        w = World()
        class Output(io.BytesIO):
            def flush(self):
                w.local += 31
        w.namespace["sys"].stdout.buffer = Output()
        with self.assertRaisesRegex(Refusal, "PHASE_EXPIRED"):
            w.run(guarded=True)
        self.assertIn(b"probePreparationSha256", w.namespace["sys"].stdout.buffer.getvalue())


class ProbeModels(unittest.TestCase):
    def reject(self, world, reason=None):
        with (self.assertRaises(Refusal) if reason is None else self.assertRaisesRegex(Refusal, reason)) as caught:
            world.run()
        self.assertNotIn("probe-result.json", world.data.get(world.guard_path, {}).get("files", {}))
        return caught.exception

    def test_actual_post_guard_classifies_exact_lookup_under_new30_with_no_extra45(self):
        w = World(after=True)
        output, fence, hard = w.run()
        result = w.record()
        self.assertEqual(len(w.owners), 2)
        self.assertEqual(len(w.native_pairs), 2)
        self.assertEqual(w.classifications, ["save", "lookup"])
        self.assertEqual(w.leaf_calls, w.fixture_leaf_calls)
        self.assertEqual(result["status"], "REPORTED_EXACT_HIT_PRESENCE_ONLY")
        self.assertEqual(result["providerEndNs"], 1480 * SECOND)
        self.assertEqual(result["firstPostProviderNs"], 1400 * SECOND)
        self.assertEqual(result["observationWindow"]["phase"], "provider-observation")
        self.assertEqual(hard - result["observationWindow"]["firstNs"], 30 * SECOND)
        self.assertEqual(fence.hard_end, hard)
        self.assertEqual(result["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(result["providerRetirement"], "NOT_OBSERVED")
        self.assertEqual(result["providerDeadlineEnforcement"], "NOT_ESTABLISHED")
        self.assertEqual((result["cacheContents"], result["resolverReuse"]), ("NOT_PROVEN", "NOT_PROVEN"))
        self.assertFalse(result["exportSaveAuthority"])
        self.assertEqual(output["probeSha256"], digest(encoded(result)))
        self.assertTrue(all(handle.closes == 1 for handle in w.handles))
        self.assertTrue(all(row["attempted"] and row["closed"] for owner in w.owners for row in owner.resources))

    def test_original_prepare_and_probe_outcomes_are_not_conclusions_or_labels(self):
        for name in ("PROBE_PREPARE_OUTCOME", "PROBE_OUTCOME"):
            for value in (None, "", "failure", "cancelled", "skipped", "SUCCESS", True):
                with self.subTest(name=name, value=value):
                    w = World(after=True)
                    w.env["P2PKIT_BOOTSTRAP_" + name] = value
                    self.reject(w, "ORIGINAL_OUTCOMES")
                    self.assertEqual(w.owners, [])

    def test_three_original_outputs_are_required_and_bounded(self):
        for suffix in ("PRIMARY_KEY", "MATCHED_KEY", "HIT"):
            for value in (None, True, "x" * 513, "value\n", "\u00e9"):
                with self.subTest(suffix=suffix, value=value):
                    w = World(after=True)
                    w.env["P2PKIT_BOOTSTRAP_PROBE_" + suffix] = value
                    self.reject(w, "ORIGINAL_OUTPUTS")
                    self.assertEqual(w.owners, [])

    def test_false_blank_or_case_changed_hit_cannot_be_positive_presence(self):
        for value in ("", "false", "True", "TRUE"):
            with self.subTest(value=value):
                w = World(after=True)
                w.env["P2PKIT_BOOTSTRAP_PROBE_HIT"] = value
                self.reject(w, "QUALIFIED_EXACT_HIT|PROVIDER_HIT_VALUE")
                if value in ("", "false"):
                    self.assertEqual(w.record("provider-probe.json")["status"], "NO_QUALIFIED_EXACT_HIT")

    def test_primary_and_matched_keys_must_both_equal_original_exact_key(self):
        for suffix in ("PRIMARY_KEY", "MATCHED_KEY"):
            for value in ("", "inexact-prefix", "other-key"):
                with self.subTest(suffix=suffix, value=value):
                    w = World(after=True)
                    w.env["P2PKIT_BOOTSTRAP_PROBE_" + suffix] = value
                    self.reject(w, "NO_QUALIFIED_EXACT_HIT")

    def test_output_change_after_native_entry_is_not_current_original(self):
        w = World(after=True)
        w.hooks["native-admit:1"] = lambda: w.env.update(P2PKIT_BOOTSTRAP_PROBE_MATCHED_KEY="changed")
        self.reject(w, "ORIGINAL_OUTPUTS")
        self.assertNotIn("lookup", w.classifications)

    def test_original_preparation_digest_is_required_even_for_convincing_hit(self):
        w = World(after=True)
        w.env["P2PKIT_BOOTSTRAP_PROBE_PREPARATION_SHA256"] = "f" * 64
        self.reject(w, "PREPARATION_HASH")
        self.assertEqual(w.native_pairs, [])

    def test_rehashed_descriptor_cannot_choose_provider_path_key_or_restore_mode(self):
        for name, value in (("action", "actions/cache@other"), ("path", "/other"), ("key", "other"),
                ("lookupOnly", False), ("restoreKeys", ["prefix"]), ("enableCrossOsArchive", True),
                ("failOnCacheMiss", False)):
            with self.subTest(name=name):
                w = World(after=True)
                w.update_preparation(lambda record: record["providerRequest"].update({name: value}))
                self.reject(w, "PROVIDER_REQUEST")

    def test_rehashed_descriptor_cannot_change_source_plan_original_claims_or_return(self):
        for name, value in (("source", {"commit": "f" * 40}), ("planSha256", "f" * 64),
                ("originalClaims", {}), ("writerReturn", "SUCCESS"), ("exportSaveAuthority", True)):
            with self.subTest(name=name):
                w = World(after=True)
                w.update_preparation(lambda record: record.update({name: value}))
                self.reject(w)

    def test_expired_original_probe_end_denies_before_native_not_fresh180(self):
        w = World(after=True)
        w.raw_ns = 1480 * SECOND
        self.reject(w, "PROVIDER_RETURN_BOUND")
        self.assertEqual(w.native_pairs, [])

    def test_rehashed_renewed_end_and_fabricated_provider_start_refuse(self):
        for change in (lambda window: window.update(hardEndNs=1880 * SECOND),
                       lambda window: window.update(actualProviderStart=1300 * SECOND)):
            w = World(after=True)
            w.update_preparation(lambda record: change(record["providerWindow"]))
            self.reject(w, "PROVIDER_RETURN_BOUND|PROVIDER_WINDOW")

    def test_readmission_after_original_probe_end_keeps_timely_first_upper_bound(self):
        w = World(after=True)
        def delayed():
            w.local += 100
            w.raw_ns += 100 * SECOND
        w.hooks["native-admit:1"] = delayed
        w.run()
        self.assertEqual(w.record()["firstPostProviderNs"], 1400 * SECOND)
        self.assertGreater(w.record("readmission-close.json")["closedNs"], w.record()["providerEndNs"])
        self.assertEqual(w.record()["observationWindow"]["firstNs"], 1500 * SECOND)

    def test_readmission_cannot_spend_a_fresh120_after_late_native_return(self):
        w = World(after=True)
        w.hooks["native-admit:1"] = lambda: setattr(w, "local", w.local + 121)
        self.reject(w)
        self.assertNotIn("lookup", w.classifications)

    def test_slow_lookup_classification_spends_original_observation30(self):
        w = World(after=True)
        actual = w.staging.cache.provider_observation
        def delayed(plan, phase, **kwargs):
            result = actual(plan, phase, **kwargs)
            if phase == "lookup":
                w.local += 31
            return result
        w.staging.cache.provider_observation = delayed
        self.reject(w, "PHASE_EXPIRED")
        self.assertEqual(len(w.owners), 2)

    def test_backward_raw_or_local_during_lookup_is_not_rebased(self):
        for clock in ("raw_ns", "local"):
            with self.subTest(clock=clock):
                w = World(after=True)
                actual = w.staging.cache.provider_observation
                def backwards(plan, phase, **kwargs):
                    result = actual(plan, phase, **kwargs)
                    if phase == "lookup":
                        setattr(w, clock, getattr(w, clock) - 1)
                    return result
                w.staging.cache.provider_observation = backwards
                self.reject(w, "BACKWARDS")

    def test_changed_preparation_during_final_admission_refuses(self):
        w = World(after=True)
        w.hooks["native-admit:2"] = lambda: w.update_preparation(lambda value: value.update(writerReturn="SUCCESS"), rehash=False)
        self.reject(w, "FINAL_PREPARATION_CHANGED")

    def test_readmission_close_failure_cannot_start_provider_observation(self):
        w = World(after=True)
        error = FalseyFailure("modeled-readmission-close")
        w.hooks["close-dir:" + w.guard_path.name] = lambda: throw(error)
        with self.assertRaises(FalseyFailure) as caught:
            w.run()
        self.assertIs(caught.exception, error)
        self.assertEqual(len(w.owners), 1)
        self.assertNotIn("lookup", w.classifications)

    def test_final_writer_unknown_retains_original_pending_only_without_digest(self):
        w = World(after=True)
        error = FalseyFailure("modeled-result-close")
        w.hooks["close-file:probe-result.json"] = lambda: throw(error)
        with self.assertRaises(FalseyFailure) as caught:
            w.run(guarded=True)
        self.assertIs(caught.exception, error)
        self.assertEqual(len(w.owners), 2)
        self.assertTrue(w.owners[-1].unknown)
        self.assertEqual(w.namespace["sys"].stdout.buffer.getvalue(), b"")
        self.assertEqual(w.record()["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")

    def test_cancellation_does_not_get_an_observation_or_delivery_allowance(self):
        w = World(after=True)
        cancelled = []
        w.hooks["native-admit:2"] = lambda: cancelled.append(15)
        with self.assertRaises(BaseException):
            w.run(cancelled=cancelled)
        self.assertNotIn("lookup", w.classifications)
        self.assertEqual(len(w.owners), 1)

    def test_replay_refuses_the_fixed_owned_target_before_new_native_work(self):
        w = World(after=True)
        w.run()
        calls = len(w.native_pairs)
        with self.assertRaisesRegex(Refusal, "EXCLUSIVE_DIRECTORY"):
            w.run()
        self.assertEqual(len(w.native_pairs), calls)
        self.assertEqual(w.classifications.count("lookup"), 1)

    def test_guarded_result_is_digest_only_not_github_output_or_cache_acceptance(self):
        w = World(after=True)
        w.run(guarded=True)
        value = json.loads(w.namespace["sys"].stdout.buffer.getvalue())
        self.assertEqual(set(value), {"scope", "probeSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertFalse(value["exportSaveAuthority"])
        self.assertNotIn("GITHUB_OUTPUT", w.env)

    def test_final_flush_must_finish_in_same_observation30_not_another45(self):
        w = World(after=True)
        class Output(io.BytesIO):
            def flush(self):
                w.local += 31
        w.namespace["sys"].stdout.buffer = Output()
        with self.assertRaisesRegex(Refusal, "PHASE_EXPIRED"):
            w.run(guarded=True)
        self.assertIn(b"probeSha256", w.namespace["sys"].stdout.buffer.getvalue())
        self.assertEqual(len(w.owners), 2)
        self.assertTrue(all(owner.closed for owner in w.owners))


class CliModels(unittest.TestCase):
    def test_both_fixed_cli_selectors_reach_only_their_guarded_functions(self):
        w = World()
        calls = []
        w.namespace["guarded"] = calls.append
        for command, function in (("prepare-probe", "prepare_probe"), ("after-probe", "after_probe_originals")):
            with patch("sys.argv", ["run-hosted-cache-bootstrap.py", command]):
                self.assertEqual(w.namespace["main"](), 0)
            self.assertIs(calls[-1], w.namespace[function])

    def test_no_path_key_command_budget_or_cross_os_cli_override(self):
        w = World()
        from contextlib import redirect_stderr
        for command in ("prepare-probe", "after-probe"):
            for argument in ("--path", "--key", "--command", "--duration", "--lookup-only", "--cross-os"):
                with self.subTest(command=command, argument=argument), patch("sys.argv", ["runner", command, argument, "x"]):
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                        w.namespace["main"]()
                    self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
