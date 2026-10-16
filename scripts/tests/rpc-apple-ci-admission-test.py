#!/usr/bin/env python3
"""Pure admission/arithmetic controls; no GUI, native, GitHub, Git or product execution."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("apple_ci_admission_tested", ROOT / "scripts/rpc_apple_ci_admission.py")
admission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admission)


def binding():
    root, python = "/private/ci/source", "/opt/toolchain/python3"
    return {
        "schema": 1, "scope": admission.SCOPE, "repository": "p2pKit/P2pKit",
        "event": "pull_request", "ref": "refs/pull/463/merge", "runId": 38481196694,
        "runAttempt": 1, "profile": "platform-full",
        "source": {"commit": "a" * 40, "tree": "d" * 40},
        "ciScope": {"full": True, "head": "a" * 40},
        "pr": {"number": 463, "base": "b" * 40, "head": "c" * 40},
        "root": root, "python": python, "argv": admission.command_for("platform-full", root, python),
    }


def checkout():
    return {"commit": "a" * 40, "tree": "d" * 40, "parents": ["b" * 40, "c" * 40], "status": ""}


def observed_run(candidate=None):
    candidate = binding() if candidate is None else candidate
    return {"repository": candidate["repository"], "event": candidate["event"], "ref": candidate["ref"],
            "runId": candidate["runId"], "runAttempt": candidate["runAttempt"],
            "sha": candidate["source"]["commit"], "profile": candidate["profile"]}


def clock():
    return {"jobStartedWall": 1_000_000_000, "observedWall": 1_000_000_600,
            "observedMonotonic": 10_000, "nowWall": 1_000_000_900, "nowMonotonic": 10_300,
            "observedBootSession": "ABCDEF12-1234-5678-9abc-abcdef123456",
            "nowBootSession": "abcdef12-1234-5678-9ABC-ABCDEF123456"}


class CiAdmissionTests(unittest.TestCase):
    def refuse(self, change=None, observation=None):
        candidate, actual = binding(), checkout()
        if change:
            change(candidate)
        if observation:
            observation(actual)
        try:
            current = observed_run(candidate)
        except (KeyError, TypeError):
            current = observed_run()
        with self.assertRaises(ValueError):
            admission.admit_context(candidate, actual, current)

    def test_exact_pr_synthetic_merge_admitted(self):
        self.assertEqual(binding(), admission.admit_context(binding(), checkout(), observed_run()))

    def test_returned_binding_does_not_alias_caller_mutable_data(self):
        original = binding()
        result = admission.admit_context(original, checkout(), observed_run())
        original["source"]["tree"] = "e" * 40
        original["argv"].append("--unsafe")
        self.assertEqual("d" * 40, result["source"]["tree"])
        self.assertEqual(3, len(result["argv"]))

    def test_exact_complete_consumer_command(self):
        candidate = binding()
        candidate["profile"] = "consumers-complete"
        candidate["argv"] = ["/bin/bash", candidate["root"] + "/scripts/check-published-consumers.sh"]
        self.assertEqual(candidate, admission.admit_context(candidate, checkout(), observed_run(candidate)))

    def test_main_push_dispatch_and_schedule(self):
        for event in ("push", "workflow_dispatch", "schedule"):
            candidate = {**binding(), "event": event, "ref": "refs/heads/main", "pr": None}
            with self.subTest(event=event):
                self.assertEqual(candidate, admission.admit_context(candidate, checkout(), observed_run(candidate)))

    def test_manual_scoped_branch_is_admitted(self):
        candidate = {**binding(), "event": "workflow_dispatch", "ref": "refs/heads/work/rpc-ci", "pr": None}
        self.assertEqual(candidate, admission.admit_context(candidate, checkout(), observed_run(candidate)))

    def test_unknown_missing_and_nonobject_binding_fields_refused(self):
        for key in admission.BINDING_KEYS:
            self.refuse(lambda value, key=key: value.pop(key))
        self.refuse(lambda value: value.update(unexpected=True))
        for value in (None, [], "source", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                admission.admit_context(value, checkout(), observed_run())

    def test_scope_schema_and_repository_cannot_be_relabelled(self):
        for changes in ({"scope": "DISPOSABLE_NONROOT_TERMINAL_CONTEXT_NOT_APP_PERMISSION_OR_PHYSICAL_LAN"},
                        {"scope": ""}, {"schema": True}, {"schema": 2},
                        {"repository": "other/P2pKit"}, {"repository": "p2pkit/p2pkit"}):
            with self.subTest(changes=changes):
                self.refuse(lambda value: value.update(changes))

    def test_unsupported_events_refused(self):
        for event in ("pull_request_target", "release", "workflow_run", "unknown", "", None, True):
            with self.subTest(event=event):
                self.refuse(lambda value: value.update(event=event))

    def test_run_and_attempt_are_positive_bounded_integer_identities(self):
        for name, maximum in (("runId", 2**63 - 1), ("runAttempt", 2**31 - 1)):
            for value in (0, -1, True, "1", 1.0, maximum + 1, None):
                with self.subTest(name=name, value=value):
                    self.refuse(lambda row: row.update({name: value}))

    def test_saved_run_or_attempt_cannot_be_relabelled_as_current(self):
        for key in ("runId", "runAttempt"):
            current = observed_run()
            current[key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                admission.admit_context(binding(), checkout(), current)
            saved = binding()
            saved[key] += 1
            with self.assertRaises(ValueError):
                admission.admit_context(saved, checkout(), observed_run())

    def test_independent_current_event_source_and_profile_must_match(self):
        for key, value in (("repository", "other/P2pKit"), ("event", "workflow_dispatch"),
                           ("ref", "refs/heads/main"), ("sha", "c" * 40), ("profile", "consumers-complete")):
            current = {**observed_run(), key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                admission.admit_context(binding(), checkout(), current)

    def test_current_run_observation_is_closed_and_typed(self):
        for key in admission.RUN_KEYS:
            current = observed_run()
            current.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                admission.admit_context(binding(), checkout(), current)
        for change in ({"runAttempt": True}, {"runId": float(binding()["runId"])}, {"trusted": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                admission.admit_context(binding(), checkout(), {**observed_run(), **change})

    def test_checkout_commit_tree_and_status_are_independent_checks(self):
        for field, value in (("commit", "c" * 40), ("tree", "e" * 40), ("status", " M script.py\n"),
                             ("status", None), ("status", False)):
            with self.subTest(field=field):
                self.refuse(observation=lambda row: row.update({field: value}))

    def test_closed_checkout_observation(self):
        for field in checkout():
            self.refuse(observation=lambda row, field=field: row.pop(field))
        self.refuse(observation=lambda row: row.update(trusted=True))

    def test_invalid_source_ids_refused(self):
        for value in ("HEAD", "A" * 40, "a" * 39, "a" * 41, "0" * 40, None, True):
            for field in ("commit", "tree"):
                with self.subTest(value=value, field=field):
                    self.refuse(lambda row: row["source"].update({field: value}))

    def test_source_hash_algorithm_must_match(self):
        self.refuse(lambda row: row["source"].update(tree="d" * 64))

    def test_consistent_sha256_git_identity_can_be_bound(self):
        candidate, actual = binding(), checkout()
        candidate["source"] = {"commit": "a" * 64, "tree": "d" * 64}
        candidate["ciScope"]["head"] = "a" * 64
        candidate["pr"].update(base="b" * 64, head="c" * 64)
        actual.update(commit="a" * 64, tree="d" * 64, parents=["b" * 64, "c" * 64])
        self.assertEqual(candidate, admission.admit_context(candidate, actual, observed_run(candidate)))

    def test_pr_parent_count_and_order_match_resolver_semantics(self):
        for parents in ([], ["b" * 40], ["c" * 40, "b" * 40],
                        ["b" * 40, "c" * 40, "e" * 40], ["b" * 40, "e" * 40]):
            with self.subTest(parents=parents):
                self.refuse(observation=lambda row: row.update(parents=parents))

    def test_pr_advertised_head_cannot_substitute_for_synthetic_merge(self):
        candidate, actual = binding(), checkout()
        candidate["source"]["commit"] = candidate["pr"]["head"]
        candidate["ciScope"]["head"] = candidate["pr"]["head"]
        actual["commit"] = candidate["pr"]["head"]
        with self.assertRaisesRegex(ValueError, "PR branch head cannot substitute"):
            admission.admit_context(candidate, actual, observed_run(candidate))

    def test_pr_base_or_head_event_change_is_refused(self):
        for key in ("base", "head"):
            with self.subTest(key=key):
                self.refuse(lambda row: row["pr"].update({key: "e" * 40}))

    def test_pr_ref_and_number_must_match(self):
        for ref in ("refs/pull/462/merge", "refs/pull/463/head", "refs/heads/main", "463/merge"):
            self.refuse(lambda row: row.update(ref=ref))
        for number in (0, True, "463", -1):
            self.refuse(lambda row: row["pr"].update(number=number))

    def test_pr_fields_are_closed(self):
        self.refuse(lambda row: row.update(pr=None))
        self.refuse(lambda row: row["pr"].update(approved=True))

    def test_actual_parent_inventory_is_typed_and_bounded(self):
        for parents in (None, "b" * 40, ("b" * 40, "c" * 40), [True], ["b" * 40] * 257,
                        ["b" * 64, "c" * 40]):
            with self.subTest(parents=parents):
                self.refuse(observation=lambda row: row.update(parents=parents))

    def test_lightweight_stale_or_truthy_scope_does_not_launch_heavy_profile(self):
        for scope in ({"full": False, "head": "a" * 40}, {"full": "true", "head": "a" * 40},
                      {"full": 1, "head": "a" * 40}, {"full": True, "head": "c" * 40},
                      {"full": True, "head": "a" * 40, "skip": False}):
            self.refuse(lambda row: row.update(ciScope=scope))

    def test_push_or_schedule_cannot_select_feature_branch(self):
        for event in ("push", "schedule"):
            self.refuse(lambda row: row.update(event=event, pr=None, ref="refs/heads/work/rpc"))

    def test_nonpr_event_refuses_pr_payload(self):
        self.refuse(lambda row: row.update(event="workflow_dispatch", ref="refs/heads/main"))

    def test_manual_ref_must_be_canonical_branch(self):
        for ref in ("refs/tags/v0.8.0-rc1", "refs/heads/", "refs/heads/a//b", "refs/heads/a/../b",
                    "refs/heads/.hidden", "refs/heads/a.lock", "refs/heads/a.", "refs/heads/a\n"):
            self.refuse(lambda row: row.update(event="workflow_dispatch", pr=None, ref=ref))

    def test_no_arbitrary_profile_command_or_partial_consumer_argv(self):
        for profile in ("lan-jvm-android", "ios-arm64", "native", "qualification", "", None):
            self.refuse(lambda row: row.update(profile=profile))
        for argv in ([], ["/bin/sh", "-c", "something"], binding()["argv"] + ["--skip"],
                     ["/bin/bash", "/private/ci/source/scripts/check-published-consumers.sh", "--latest-published"]):
            self.refuse(lambda row: row.update(argv=argv))

    def test_fixed_profile_cannot_select_another_interpreter_or_checkout(self):
        self.refuse(lambda row: row.update(root="/private/ci/another"))
        self.refuse(lambda row: row.update(python="/another/python3"))

    def test_path_validation_is_lexical_canonical_not_shell_parsing(self):
        for value in ("relative", "/", "/tmp/../root", "/tmp/./root", "/tmp//root", "//tmp/root",
                      "/tmp/root/", "/tmp/root\n", "/tmp/\x00root", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                admission.command_for("platform-full", value, "/usr/bin/python3")
        self.assertEqual(["/usr/bin/python3", "/private/has space/scripts/run-platform-tests.py", "full"],
                         admission.command_for("platform-full", "/private/has space", "/usr/bin/python3"))


class EnvelopeTests(unittest.TestCase):
    def plan(self, clocks=None, **changes):
        arguments = {"product_seconds": 500, "finalization_seconds": 400, "enclosing_cutoff": 20_000}
        arguments.update(changes)
        return admission.plan_envelope(clock() if clocks is None else clocks, **arguments)

    def test_job_budget_charges_setup_before_and_after_clock_observation(self):
        plan = self.plan()
        self.assertEqual(3600, plan["jobSeconds"])
        self.assertEqual(901, plan["elapsedSetupSeconds"])
        self.assertLess(plan["jobCutoffMonotonic"], 12_999)
        self.assertEqual(10_800, plan["productCutoffMonotonic"])
        self.assertFalse(plan["nativeExecutionAuthorized"])
        self.assertFalse(plan["cleanupVerified"])

    def test_planning_does_not_modify_observed_clock_facts(self):
        inputs = clock()
        original = copy.deepcopy(inputs)
        self.plan(inputs)
        self.assertEqual(original, inputs)

    def test_later_setup_cannot_renew_retained_deadline(self):
        first = self.plan()
        later = clock()
        later["nowWall"] += 100
        later["nowMonotonic"] += 100
        second = self.plan(later)
        self.assertLessEqual(second["jobCutoffMonotonic"], first["jobCutoffMonotonic"])
        self.assertEqual(first["elapsedSetupSeconds"] + 100, second["elapsedSetupSeconds"])

    def test_earlier_enclosing_cutoff_is_preserved(self):
        self.assertEqual(11_500, self.plan(enclosing_cutoff=11_500)["enclosingCutoffMonotonic"])

    def test_later_enclosing_cutoff_never_extends_original_hour(self):
        plan = self.plan(enclosing_cutoff=10**8)
        self.assertEqual(plan["jobCutoffMonotonic"], plan["enclosingCutoffMonotonic"])

    def test_insufficient_remaining_time_refused_before_work(self):
        for changes in ({"product_seconds": 2600}, {"finalization_seconds": 2600},
                        {"enclosing_cutoff": 11_100}, {"enclosing_cutoff": 10_300}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan(**changes)

    def test_original_shell_quit_interval_cannot_be_omitted(self):
        for interval in (0, 1, 29.999):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                self.plan(finalization_seconds=interval)
        # Arithmetic minimum only; this is NOT a claim that 30s covers executor cleanup.
        self.assertEqual(30, self.plan(finalization_seconds=30)["finalizationSeconds"])

    def test_future_job_start_and_reversed_clocks_refused(self):
        for changes in ({"jobStartedWall": 1_000_000_601}, {"nowWall": 1_000_000_599},
                        {"nowMonotonic": 9999}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan({**clock(), **changes})

    def test_expired_original_job_cannot_receive_fresh_hour(self):
        changed = clock()
        changed.update(nowWall=1_000_003_600, nowMonotonic=13_000)
        with self.assertRaises(ValueError):
            self.plan(changed)

    def test_wall_monotonic_drift_above_fixed_uncertainty_refused(self):
        for offset in (-1.001, 1.001, 10, 60):
            changed = clock()
            changed["nowWall"] += offset
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.plan(changed)

    def test_small_wall_lag_does_not_gain_time(self):
        changed = clock()
        changed["nowWall"] -= 0.5
        self.assertLessEqual(self.plan(changed)["jobCutoffMonotonic"], self.plan()["jobCutoffMonotonic"])

    def test_small_wall_advance_conservatively_loses_time(self):
        changed = clock()
        changed["nowWall"] += 0.5
        self.assertLess(self.plan(changed)["jobCutoffMonotonic"], self.plan()["jobCutoffMonotonic"])

    def test_nonfinite_negative_boolean_or_unrepresentable_numbers_refused(self):
        invalid = (math.nan, math.inf, -math.inf, -1, True, "10", None, 10**1000)
        for value in invalid:
            for field in admission.CLOCK_KEYS:
                with self.subTest(field=field, kind=type(value).__name__), self.assertRaises(ValueError):
                    self.plan({**clock(), field: value})
            for field in ("product_seconds", "finalization_seconds", "enclosing_cutoff"):
                with self.subTest(field=field, kind=type(value).__name__), self.assertRaises(ValueError):
                    self.plan(**{field: value})

    def test_missing_extra_or_nonobject_clock_refused(self):
        for field in admission.CLOCK_KEYS:
            changed = clock()
            changed.pop(field)
            with self.assertRaises(ValueError):
                self.plan(changed)
        with self.assertRaises(ValueError):
            self.plan({**clock(), "extend": True})
        with self.assertRaises(ValueError):
            admission.plan_envelope([], product_seconds=1, finalization_seconds=30, enclosing_cutoff=1000)

    def test_zero_product_or_enclosing_interval_refused(self):
        for changes in ({"product_seconds": 0}, {"enclosing_cutoff": 0}):
            with self.assertRaises(ValueError):
                self.plan(**changes)

    def test_large_clock_that_loses_product_precision_refused(self):
        changed = {**clock(), "jobStartedWall": 100, "observedWall": 100, "observedMonotonic": 1e30,
                   "nowWall": 100, "nowMonotonic": 1e30}
        with self.assertRaises(ValueError):
            self.plan(changed, enclosing_cutoff=1e31)

    def test_uncertainty_margin_refuses_exact_unrounded_capacity(self):
        with self.assertRaises(ValueError):
            self.plan(product_seconds=2300, finalization_seconds=400)

    def test_boot_change_refused_even_if_clocks_numerically_agree(self):
        changed = {**clock(), "nowBootSession": "abcdef12-1234-5678-9abc-abcdef123457"}
        with self.assertRaisesRegex(ValueError, "^Boot session changed"):
            self.plan(changed)

    def test_unknown_zero_or_malformed_boot_identity_refused(self):
        for value in ("", "unknown", "0" * 32, "00000000-0000-0000-0000-000000000000", None, 123):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan({**clock(), "observedBootSession": value, "nowBootSession": value})


if __name__ == "__main__":
    unittest.main(verbosity=2)
