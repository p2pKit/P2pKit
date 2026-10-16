#!/usr/bin/env python3
"""Offline gate/challenge models; no environment/run/API/native execution."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_gate as G

# Reuse synthetic builders, not prior test results; unittest.main is not run.
spec = importlib.util.spec_from_file_location("stage_models", Path(__file__).with_name("hosted-initial-recipient-stages-test.py"))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
S, I = G.stages, G.identity


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def environment():
    return {"id": 101, "name": "initial-recipient-execution", "can_admins_bypass": False,
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
        "protection_rules": [{"type": "required_reviewers", "prevent_self_review": False,
            "reviewers": [{"type": "User", "reviewer": dict(F.OWNER)}]}, {"type": "branch_policy"}]}


class GateModels(unittest.TestCase):
    def setUp(self):
        self.stage = "stage1"
        self.one = F.stage1()
        self.two, self.histories = F.stage2(self.one)
        self.env = environment()
        self.branches = {"total_count": 2, "branch_policies": copy.deepcopy(F.ENVIRONMENT["branchPolicies"])}
        self.select_stage()

    def select_stage(self, stage="stage1", profile="desktop"):
        self.stage = stage
        if stage == "stage1":
            self.declaration = self.one
            self.comment = F.comment(self.one, 8001, F.START - 60)
            self.observed = F.observation1(self.one, "full-macos-arm64")
            github = self.observed["github"]
            selection = github.pop("selection")
            self.observed["inputs"] = {"selection": selection, "expected_sha": F.H1, "expected_tree": F.T1}
        else:
            self.declaration = self.two
            self.comment = F.comment(self.two, 8002, F.START + 200)
            self.observed = F.observation2(self.two, profile, "linux-x64" if profile == "desktop" else "macos-arm64")
            github = self.observed["github"]
        github.pop("profile")
        github.update(job=G.JOB, runnerOS="Linux", runnerArch="X64")
        self.challenge = (f"AUTHORIZE_INITIAL_RECIPIENT {stage} {github['runId']}/{github['runAttempt']} "
                          f"{self.comment['id']} {F.body_hash(self.comment)}")
        self.history = [{"state": "approved", "user": dict(F.OWNER), "comment": self.challenge,
                         "environments": [{"id": 101, "name": "initial-recipient-execution"}]}]

    def select(self, **options):
        args = {"stage": self.stage, "run_id": self.observed["github"]["runId"],
                "attempt": self.observed["github"]["runAttempt"], "approvals_raw": encoded(self.history)}
        args.update(options)
        return G.select(**args)

    def check(self, **options):
        args = {"stage": self.stage, "approvals_raw": encoded(self.history), "comment_raw": encoded(self.comment),
            "environment_raw": encoded(self.env), "branches_raw": encoded(self.branches),
            "observation_raw": encoded(self.observed), "now": F.DONE1 if self.stage == "stage1" else F.NOW,
            **F.policy_inputs()}
        if self.stage == "stage2":
            args.update(histories=self.histories, prior_ancestry_raw=F.H1.encode("ascii") + b"\n")
        args.update(options)
        return G.eligible(**args)

    def refuse(self, code=".+", **options):
        with self.assertRaisesRegex(I.AdmissionError, code):
            self.check(**options)

    def test_selector_identifies_exact_comment_from_actual_challenge_shape(self):
        result = self.select()
        value = json.loads(result.record)
        self.assertIs(type(result), G.ApprovalSelector)
        self.assertEqual(value["commentId"], 8001)
        self.assertEqual(value["bodySha256"], F.body_hash(self.comment))
        self.assertNotIsInstance(result, I.Admission)

    def test_stage1_mac_selection_keeps_actual_linux_gate_not_fake_mac_populate(self):
        result = self.check()
        value = json.loads(result.record)
        self.assertIs(type(result), G.GateEligibility)
        self.assertEqual(value["scope"], "NONPRODUCTIVE_ELIGIBILITY")
        self.assertEqual(value["github"]["job"], G.JOB)
        self.assertEqual(value["github"]["runnerOS"], "Linux")
        self.assertEqual(value["workerAdmission"], "NOT_PERFORMED")
        self.assertEqual(value["qualificationAcceptance"], "NOT_ESTABLISHED_BY_GATE")
        self.assertNotIsInstance(result, (I.Admission, S.BootstrapMatch, S.OrdinaryMatch))

    def test_both_stage2_workflows_use_gate_identity_and_historical_h1(self):
        for profile in ("desktop", "full"):
            self.select_stage("stage2", profile)
            value = json.loads(self.check().record)
            self.assertEqual(value["github"]["runnerOS"], "Linux")
            self.assertEqual(value["github"]["job"], G.JOB)
            self.assertEqual(value["source"], {"commit": F.MERGE, "tree": F.T2})
            self.assertEqual(value["policy"]["commit"], F.H2)

    def test_history_cannot_reuse_prior_attempt_or_other_run(self):
        for run, attempt in (("304", "2"), ("999", "1")):
            with self.assertRaisesRegex(I.AdmissionError, "MISSING_OR_AMBIGUOUS_CHALLENGE"):
                self.select(run_id=run, attempt=attempt)

    def test_strict_challenge_rejects_spacing_case_prefix_suffix_and_crlf_aliases(self):
        for line in (" " + self.challenge, self.challenge + "\n", self.challenge + "\r\n", self.challenge.lower(),
                     self.challenge + " approved", self.challenge.replace("stage1 ", "stage1  "),
                     "```" + self.challenge + "```", self.challenge.replace("/1 ", "/01 ")):
            self.history[0]["comment"] = line
            self.refuse("MISSING_OR_AMBIGUOUS_CHALLENGE")

    def test_challenge_from_different_stage_cannot_be_used(self):
        self.history[0]["comment"] = self.challenge.replace("stage1", "stage2")
        self.refuse("MISSING_OR_AMBIGUOUS_CHALLENGE")

    def test_multiple_exact_run_challenges_refuse_instead_of_latest_wins(self):
        self.history.append(copy.deepcopy(self.history[0]))
        self.refuse("MISSING_OR_AMBIGUOUS_CHALLENGE")
        self.history[1]["comment"] = self.challenge.replace("8001 ", "8002 ")
        self.refuse("MISSING_OR_AMBIGUOUS_CHALLENGE")

    def test_other_attempt_history_is_retained_but_not_selected(self):
        self.history.append({**copy.deepcopy(self.history[0]), "comment": self.challenge.replace("/1 ", "/2 ")})
        self.check()

    def test_actual_approval_requires_owner_login_numeric_id_type_and_approved_state(self):
        for field, bad in (("login", "other"), ("id", "104788132"), ("id", True), ("type", "Bot")):
            self.history[0]["user"] = {**F.OWNER, field: bad}
            self.refuse("OWNER_APPROVAL")
        self.history[0]["user"] = dict(F.OWNER)
        for state in ("rejected", "pending", "success", True):
            self.history[0]["state"] = state
            self.refuse("OWNER_APPROVAL")

    def test_approval_must_name_only_the_exact_pre_execution_environment(self):
        for environments in ([], [{"id": 101, "name": "sample-development-release"}],
                             [{"id": 101, "name": S.ENVIRONMENT}] * 2, [{"id": True, "name": S.ENVIRONMENT}]):
            self.history[0]["environments"] = environments
            self.refuse()

    def test_approval_of_recreated_same_name_environment_cannot_use_old_statement(self):
        self.history[0]["environments"][0]["id"] = 202
        self.refuse("APPROVED_ENVIRONMENT_CHANGED")

    def test_selected_comment_must_exist_at_exact_id_location_and_body_hash(self):
        self.refuse(comment_raw=b"{}")
        self.comment["id"] = 8002
        self.refuse("COMMENT_LOCATION")
        self.comment["id"] = 8001
        self.comment["body"] += " "
        self.refuse("COMMENT_DIGEST")

    def test_selected_comment_cannot_be_edited_or_app_posted(self):
        self.comment["updated_at"] = F.utc(F.START)
        self.refuse("COMMENT_EDITED")
        self.comment["updated_at"] = self.comment["created_at"]
        self.comment["performed_via_github_app"] = {"id": 7}
        self.refuse("COMMENT_OWNER")

    def test_environment_has_no_admin_bypass_or_unrestricted_deployment_policy(self):
        for field, bad in (("can_admins_bypass", True), ("can_admins_bypass", 0),
                           ("deployment_branch_policy", None), ("deployment_branch_policy",
                            {"protected_branches": True, "custom_branch_policies": False})):
            saved = self.env[field]
            self.env[field] = bad
            self.refuse("ENVIRONMENT_CONFIGURATION")
            self.env[field] = saved

    def test_environment_must_be_same_id_with_complete_explicit_protections(self):
        for value in (202, True, "101"):
            self.env["id"] = value
            self.refuse("ENVIRONMENT_CONFIGURATION")
        self.env["id"] = 101
        for rules in ([], self.env["protection_rules"] + [{"type": "wait_timer"}], [{"type": "required_reviewers"}] * 2):
            self.env["protection_rules"] = rules
            self.refuse("PROTECTION_RULES")

    def test_environment_sole_owner_self_review_is_required_not_optional(self):
        rule = self.env["protection_rules"][0]
        rule["prevent_self_review"] = True
        self.refuse("SOLE_OWNER_REVIEWER")
        rule["prevent_self_review"] = False
        for reviewers in ([], [{"type": "Team", "reviewer": dict(F.OWNER)}],
                           [{"type": "User", "reviewer": dict(F.OWNER)}] * 2):
            rule["reviewers"] = reviewers
            self.refuse("SOLE_OWNER_REVIEWER")

    def test_incomplete_branch_pagination_missing_added_duplicate_and_tag_policies_refuse(self):
        good = copy.deepcopy(self.branches)
        for count in (1, 3, True, "2"):
            self.branches["total_count"] = count
            self.refuse("COMPLETE_BRANCH_POLICIES")
        self.branches = copy.deepcopy(good)
        self.branches["branch_policies"].pop()
        self.refuse("COMPLETE_BRANCH_POLICIES")
        for field, bad in (("id", 999), ("name", "*"), ("type", "tag")):
            self.branches = copy.deepcopy(good)
            self.branches["branch_policies"][0][field] = bad
            self.refuse("BRANCH_POLICY_CHANGED")
        self.branches = copy.deepcopy(good)
        self.branches["branch_policies"][1] = self.branches["branch_policies"][0]
        self.refuse("BRANCH_POLICY_CHANGED")

    def test_branch_api_order_and_unrelated_metadata_do_not_change_authority(self):
        original = self.check()
        self.branches["branch_policies"].reverse()
        self.env["url"] = "https://example.invalid/model"
        self.history[0]["user"]["avatar_url"] = "https://example.invalid/model"
        self.assertEqual(self.check(expected=original), original)

    def test_gate_refuses_productive_job_or_counterfeit_native_host_labels(self):
        for field, bad in (("job", "populate"), ("job", "complete-gate"), ("job", "verify"),
                           ("runnerOS", "macOS"), ("runnerArch", "ARM64")):
            saved = self.observed["github"][field]
            self.observed["github"][field] = bad
            self.refuse("NONPRODUCTIVE_JOB")
            self.observed["github"][field] = saved

    def test_gate_cannot_add_native_profile_to_observation(self):
        self.observed["github"]["profile"] = "cache-bootstrap"
        self.refuse("GATE_GITHUB_FIELDS")

    def test_gate_preserves_exact_dispatch_input_roster_and_bindings(self):
        inputs = self.observed["inputs"]
        inputs["commentId"] = "8001"
        self.refuse("DISPATCH_INPUTS")
        del inputs["commentId"]
        for field, bad in (("selection", "desktop-linux-x64"), ("expected_sha", F.H2), ("expected_tree", F.T2)):
            saved = inputs[field]
            inputs[field] = bad
            self.refuse("BOOTSTRAP_SELECTION")
            inputs[field] = saved

    def test_gate_requires_real_bootstrap_event_ref_workflow_and_source(self):
        for field, bad in (("event", "push"), ("ref", "refs/heads/main"), ("workflowSha", F.H2),
                           ("workflow", I.PROFILES["full"][0])):
            saved = self.observed["github"][field]
            self.observed["github"][field] = bad
            self.refuse("BOOTSTRAP_CONTEXT")
            self.observed["github"][field] = saved

    def test_stage1_gate_needs_no_pr_history(self):
        self.refuse("BOOTSTRAP_HAS_NO_PR_HISTORY", histories=self.histories)
        self.refuse("BOOTSTRAP_HAS_NO_PR_HISTORY", histories=[])
        self.refuse("BOOTSTRAP_HAS_NO_PR_HISTORY", prior_ancestry_raw=b"true")

    def test_stage2_gate_cannot_change_pr_state_merge_or_workflow_run(self):
        self.select_stage("stage2")
        self.observed["pullRequest"]["merged"] = True
        self.refuse("PR_CURRENT")
        self.observed["pullRequest"]["merged"] = False
        self.observed["mergeParents"].reverse()
        self.refuse("ORDINARY_MERGE")
        self.observed["mergeParents"].reverse()
        self.observed["github"]["workflow"] = I.PROFILES["full"][0]
        self.refuse("ORDINARY_RUN")

    def test_stage2_gate_requires_historical_records_not_selected_hashes_alone(self):
        self.select_stage("stage2")
        self.refuse("QUALIFICATION_ROSTER", histories=())
        self.refuse("STAGE1_ANCESTRY", prior_ancestry_raw=F.H2.encode() + b"\n")

    def test_gate_absence_policy_clock_and_current_head_are_still_required(self):
        self.refuse("BASE_POLICY_NOT_ABSENT", base_policy_entry=b"error")
        self.refuse("POLICY_DIGEST", candidate_policy_raw=F.POLICY + b"\n")
        self.refuse("VALIDITY", now=self.one["expiresAt"])
        self.observed["reviewed"]["tree"] = F.T2
        self.refuse("CURRENT_SOURCE")

    def test_selector_and_eligibility_have_distinct_immutable_recheck_types(self):
        selected, eligible = self.select(), self.check()
        self.assertEqual(self.select(expected=selected), selected)
        self.assertEqual(self.check(expected=eligible), eligible)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            eligible.record = b"changed"
        self.refuse("CHANGED_BEFORE_RECHECK", expected=selected)
        with self.assertRaisesRegex(I.AdmissionError, "CHANGED_BEFORE_RECHECK"):
            self.select(expected=eligible)

    def test_rechecks_require_exact_bytes_not_custom_equality(self):
        class Forged:
            def __eq__(self, other):
                raise AssertionError("Do not compare untrusted wrapper")
        class Bytes(bytes):
            def __eq__(self, other):
                raise AssertionError("Do not compare subclass")
        selected, eligible = self.select(), self.check()
        for good, kind, check in ((selected, G.ApprovalSelector, self.select), (eligible, G.GateEligibility, self.check)):
            for raw in (Forged(), Bytes(good.record), bytearray(good.record), memoryview(good.record)):
                with self.assertRaisesRegex(I.AdmissionError, "CHANGED_BEFORE_RECHECK"):
                    check(expected=kind(raw))

    def test_history_malformed_duplicate_keys_nonlist_and_oversize_refuse(self):
        for raw in (b"", b"{}", b"[", b'[{"state":1,"state":2}]', b"[NaN]", b"x" * (G.HISTORY_LIMIT + 1), b"[true]"):
            self.refuse(approvals_raw=raw)
        self.refuse("HISTORY_SHAPE", approvals_raw=encoded([{}] * 1001))

    def test_selector_rejects_malformed_original_with_a_wrapper_sibling(self):
        raw = encoded(self.history).rstrip(b"\n") + b',"injected":true'
        with self.assertRaises(json.JSONDecodeError):
            json.loads(raw)
        with self.assertRaisesRegex(I.AdmissionError, "HISTORY_SHAPE"):
            self.select(approvals_raw=raw)

    def test_gate_rejects_malformed_original_with_a_wrapper_sibling(self):
        raw = encoded(self.history).rstrip(b"\n") + b',"injected":true'
        self.refuse("HISTORY_SHAPE", approvals_raw=raw)

    def test_changed_selector_or_environment_invalidates_gate_recheck(self):
        original = self.check()
        self.observed["firstUseAt"] += 1
        self.refuse("CHANGED_BEFORE_RECHECK", expected=original)
        selected = self.select()
        self.history[0]["environments"][0]["id"] = 202
        with self.assertRaisesRegex(I.AdmissionError, "CHANGED_BEFORE_RECHECK"):
            self.select(expected=selected)


if __name__ == "__main__":
    unittest.main()
