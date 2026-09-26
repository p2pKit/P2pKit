#!/usr/bin/env python3
"""Small offline staged-contract controls, not real authority or qualification.

All IDs/sources/history/packet references below are synthetic. Only the already
committed public policy is read. No key directory, crypto, child or network use.
"""
from __future__ import annotations

import copy
import dataclasses
import datetime
import hashlib
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
import hosted_initial_recipient_stages as S

I, B = S.identity, S.bootstrap
H1, T1, H2, T2, MERGE, OTHER = (c * 40 for c in "abcdef")
START, END = 1789948800, 1791158400
FIRST1, DONE1, FIRST2, NOW = START + 10, START + 100, START + 210, START + 240
POLICY = (ROOT / ".github/test-evidence-recipient.json").read_bytes()
BLOB = hashlib.sha1(b"blob " + str(len(POLICY)).encode("ascii") + b"\x00" + POLICY).hexdigest()
ENTRY = b"100644 blob " + BLOB.encode("ascii") + b"\t.github/test-evidence-recipient.json\x00"
OWNER = {"login": "Apdelrahman1911", "id": 104788132, "type": "User"}
ENVIRONMENT = {"name": "initial-recipient-execution", "id": 101,
    "branchPolicies": [{"id": 102, "name": "work/release-foundation-20260926-1WzHcOIr", "type": "branch"},
                       {"id": 103, "name": "refs/pull/*/merge", "type": "branch"}]}
SELECTIONS = tuple(x[0] for x in B.SELECTIONS)


def utc(value):
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def declaration(stage):
    return {"schema": 1, "scope": stage, "repository": "p2pKit/P2pKit", "base": dict(S.BASE),
        "reviewed": {"commit": H1 if stage == S.STAGE1 else H2, "tree": T1 if stage == S.STAGE1 else T2},
        "sourceRef": S.SOURCE_REF, "policySha256": S.POLICY_SHA256,
        "notBefore": START, "expiresAt": START + 150 if stage == S.STAGE1 else END,
        "environment": copy.deepcopy(ENVIRONMENT)}


def stage1():
    value = declaration(S.STAGE1)
    value["bootstrap"] = [{"selection": name, "runId": str(300 + n), "runAttempt": "1"}
                          for n, name in enumerate(SELECTIONS)]
    return value


def comment(value, identifier, created, *, stage=None):
    body = S.COMMANDS[stage or value["scope"]] + I.encoded(value).decode("ascii").removesuffix("\n")
    return {"id": identifier, "url": f"https://api.github.com/repos/p2pKit/P2pKit/issues/comments/{identifier}",
        "issue_url": "https://api.github.com/repos/p2pKit/P2pKit/issues/437",
        "html_url": f"https://github.com/p2pKit/P2pKit/issues/437#issuecomment-{identifier}",
        "user": dict(OWNER), "performed_via_github_app": None,
        "created_at": utc(created), "updated_at": utc(created), "body": body}


def body_hash(value):
    return hashlib.sha256(value["body"].encode("utf-8")).hexdigest()


def observation1(value, selection="desktop-linux-x64"):
    entry = next(x for x in value["bootstrap"] if x["selection"] == selection)
    _, _, system, arch = B.selection(selection)
    return {"repository": "p2pKit/P2pKit", "base": dict(S.BASE), "reviewed": dict(value["reviewed"]),
        "source": dict(value["reviewed"]), "firstUseAt": FIRST1,
        "github": {"profile": "cache-bootstrap", "event": "workflow_dispatch", "ref": S.SOURCE_REF,
            "workflow": B.WORKFLOW, "workflowSha": value["reviewed"]["commit"], "job": "populate",
            "runId": entry["runId"], "runAttempt": entry["runAttempt"], "runnerOS": system,
            "runnerArch": arch, "selection": selection}}


def policy_inputs():
    return {"base_policy_entry": b"", "ancestry_raw": S.BASE["commit"].encode("ascii") + b"\n",
            "candidate_policy_entry": ENTRY, "candidate_policy_raw": POLICY}


def check1(value, observed, *, override=None, **options):
    authority = comment(value, 8001, START - 60, stage=S.STAGE1)
    authority.update(override or {})
    kwargs = {"comment_raw": I.encoded(authority), "comment_id": 8001, "body_sha256": body_hash(authority),
              "observation_raw": I.encoded(observed), "now": DONE1, **policy_inputs()}
    kwargs.update(options)
    return S.match_bootstrap(**kwargs)


def ref(n):
    return {"bytes": 100 + n, "sha256": hashlib.sha256(str(n).encode("ascii")).hexdigest()}


def stage2(prior):
    value = declaration(S.STAGE2)
    value["firstPullRequest"] = {"number": 999, "merge": {"commit": MERGE, "tree": T2}, "runs": [
        {"profile": "desktop", "role": "linux-x64", "runId": "401", "runAttempt": "1"},
        {"profile": "desktop", "role": "windows-x64", "runId": "401", "runAttempt": "1"},
        {"profile": "desktop", "role": "macos-arm64", "runId": "401", "runAttempt": "1"},
        {"profile": "full", "role": "macos-arm64", "runId": "402", "runAttempt": "1"}]}
    authority = comment(prior, 8001, START - 60)
    value["stage1"] = {"commentId": 8001, "bodySha256": body_hash(authority), "reviewed": dict(prior["reviewed"])}
    entries, histories = [], []
    for n, name in enumerate(("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "full-macos-arm64")):
        observed = observation1(prior, name)
        entries.append({**next(x for x in prior["bootstrap"] if x["selection"] == name), "completedAt": DONE1,
            "packet": {"artifactId": 1000 + n, **ref(n)}, "inventory": ref(n + 4),
            "compatibility": ref(n + 8), "review": ref(n + 12)})
        histories.append(S.BootstrapHistory(I.encoded(authority), I.encoded(observed), b"",
            S.BASE["commit"].encode("ascii") + b"\n", ENTRY, POLICY, DONE1, check1(prior, observed)))
    value["qualifications"] = entries
    return value, tuple(histories)


def observation2(value, profile="desktop", role="linux-x64"):
    first, reviewed = value["firstPullRequest"], value["reviewed"]
    entry = next(x for x in first["runs"] if (x["profile"], x["role"]) == (profile, role))
    system, arch = S.joint.ROLES[role]
    workflow, job, _ = I.PROFILES[profile]
    return {"repository": "p2pKit/P2pKit", "base": dict(S.BASE), "reviewed": dict(reviewed),
        "source": dict(first["merge"]), "firstUseAt": FIRST2,
        "github": {"profile": profile, "event": "pull_request", "ref": "refs/pull/999/merge",
            "workflow": workflow, "workflowSha": first["merge"]["commit"], "job": job,
            "runId": entry["runId"], "runAttempt": entry["runAttempt"], "runnerOS": system, "runnerArch": arch},
        "mergeParents": [S.BASE["commit"], reviewed["commit"]],
        "pullRequest": {"number": 999, "state": "open", "merged": False, "merge_commit_sha": first["merge"]["commit"],
            "user": dict(OWNER), "auto_merge": None, "url": "https://api.github.com/repos/p2pKit/P2pKit/pulls/999",
            "html_url": "https://github.com/p2pKit/P2pKit/pull/999",
            "base": {"sha": S.BASE["commit"], "ref": "main", "repo": {"full_name": "p2pKit/P2pKit"}},
            "head": {"sha": reviewed["commit"], "ref": S.SOURCE_REF.removeprefix("refs/heads/"),
                     "repo": {"full_name": "p2pKit/P2pKit"}}}}


class StagedModels(unittest.TestCase):
    def setUp(self):
        self.one = stage1()
        self.obs1 = observation1(self.one)
        self.two, self.history = stage2(self.one)
        self.obs2 = observation2(self.two)
        self.override = {}

    def check1(self, **options):
        return check1(self.one, self.obs1, override=self.override, **options)

    def check2(self, **options):
        authority = comment(self.two, 8002, START + 200, stage=S.STAGE2)
        authority.update(self.override)
        kwargs = {"comment_raw": I.encoded(authority), "comment_id": 8002, "body_sha256": body_hash(authority),
            "observation_raw": I.encoded(self.obs2), "histories": self.history, "now": NOW,
            "prior_ancestry_raw": H1.encode("ascii") + b"\n", **policy_inputs()}
        kwargs.update(options)
        return S.match_ordinary(**kwargs)

    def refuse1(self, code=".+", **options):
        with self.assertRaisesRegex(I.AdmissionError, code):
            self.check1(**options)

    def refuse2(self, code=".+", **options):
        with self.assertRaisesRegex(I.AdmissionError, code):
            self.check2(**options)

    def test_public_policy_exact_bytes_are_not_private_key_use(self):
        self.assertEqual(len(POLICY), 3631)
        self.assertEqual(hashlib.sha256(POLICY).hexdigest(), S.POLICY_SHA256)
        self.assertEqual(BLOB, "118bf7577771ca79aeaf016d9f9602cb5b666dfa")

    def test_foundation_lane_and_branch_policy_have_fixed_independent_expectations(self):
        expected = "work/release-foundation-20260926-1WzHcOIr"
        self.assertEqual(S.SOURCE_REF, "refs/heads/" + expected)
        self.assertEqual(S.BRANCHES, (expected, "refs/pull/*/merge"))
        self.assertEqual(ENVIRONMENT["branchPolicies"][0]["name"], expected)
        self.assertIs(type(self.check1()), S.BootstrapMatch)
        self.assertIs(type(self.check2()), S.OrdinaryMatch)

    def test_old_campaign_declarations_refuse_both_stages_after_rehash(self):
        for value, refuse in ((self.one, self.refuse1), (self.two, self.refuse2)):
            previous = value["sourceRef"]
            value["sourceRef"] = "refs/heads/work/nonphysical-integration-20260915-022112"
            # check1/check2 construct freshly hashed supplied comments.
            refuse("STATEMENT_SCOPE")
            value["sourceRef"] = previous

    def test_old_campaign_environment_refuses_both_stages_after_rehash(self):
        for value, refuse in ((self.one, self.refuse1), (self.two, self.refuse2)):
            policy = value["environment"]["branchPolicies"][0]
            previous = policy["name"]
            policy["name"] = "work/nonphysical-integration-20260915-022112"
            refuse("ENVIRONMENT_BRANCHES")
            policy["name"] = previous

    def test_old_campaign_actual_execution_refuses_foundation_declarations(self):
        previous = "work/nonphysical-integration-20260915-022112"
        self.obs1["github"]["ref"] = "refs/heads/" + previous
        self.refuse1("BOOTSTRAP_EXECUTION")
        self.obs2["pullRequest"]["head"]["ref"] = previous
        self.refuse2("PR_BASE_OR_HEAD")

    def test_stage1_all_six_roles_work_without_a_pr(self):
        for name in SELECTIONS:
            self.obs1 = observation1(self.one, name)
            result = self.check1()
            self.assertIs(type(result), S.BootstrapMatch)
            self.assertNotIsInstance(result, I.Admission)
            self.assertEqual(json.loads(result.record)["source"], self.one["reviewed"])

    def test_stage1_single_slot_does_not_reserve_ordinary_execution(self):
        self.one["bootstrap"] = self.one["bootstrap"][:1]
        self.check1()

    def test_stage1_excludes_pr_and_ordinary_fields_even_null(self):
        for target, name in ((self.one, "firstPullRequest"), (self.one, "qualifications"),
                             (self.obs1, "pullRequest"), (self.obs1, "mergeParents")):
            target[name] = None
            self.refuse1("FIELDS")
            del target[name]

    def test_stage2_excludes_live_bootstrap_roster(self):
        self.two["bootstrap"] = self.one["bootstrap"]
        self.refuse2("STATEMENT_FIELDS")

    def test_stage1_empty_overlong_and_duplicate_rosters_refuse(self):
        original = copy.deepcopy(self.one["bootstrap"])
        for entries in ([], original + original[:1], [original[0], original[0]], None):
            self.one["bootstrap"] = entries
            self.refuse1()
        self.one["bootstrap"] = original
        self.one["bootstrap"][1]["runId"] = self.one["bootstrap"][0]["runId"]
        self.refuse1("DUPLICATE_BOOTSTRAP")

    def test_stage1_run_attempt_and_selection_are_exact(self):
        for field, value in (("runId", "9999"), ("runAttempt", "2"), ("selection", "full-macos-arm64")):
            saved = self.obs1["github"][field]
            self.obs1["github"][field] = value
            self.refuse1("UNLISTED_BOOTSTRAP")
            self.obs1["github"][field] = saved

    def test_stage1_gate_cannot_impersonate_populate_native_identity(self):
        for field, value in (("job", "initial-recipient-gate"), ("runnerOS", "macOS"),
                             ("runnerArch", "ARM64"), ("profile", "desktop"), ("event", "push")):
            saved = self.obs1["github"][field]
            self.obs1["github"][field] = value
            self.refuse1("BOOTSTRAP_EXECUTION")
            self.obs1["github"][field] = saved

    def test_stage1_source_workflow_and_ref_must_be_actual_reviewed_head(self):
        for field, value in (("workflowSha", H2), ("ref", "refs/heads/main"), ("workflow", I.PROFILES["full"][0])):
            saved = self.obs1["github"][field]
            self.obs1["github"][field] = value
            self.refuse1("BOOTSTRAP_EXECUTION")
            self.obs1["github"][field] = saved
        self.obs1["source"] = {"commit": MERGE, "tree": T1}
        self.refuse1("BOOTSTRAP_EXECUTION")

    def test_cross_stage_and_legacy_comments_do_not_fall_back(self):
        other = comment(self.two, 8001, START - 60)
        self.refuse1("COMMENT_BODY", comment_raw=I.encoded(other), body_sha256=body_hash(other))
        other = comment(self.one, 8002, START + 200)
        self.refuse2("COMMENT_BODY", comment_raw=I.encoded(other), body_sha256=body_hash(other))
        other = comment(self.one, 8001, START - 60)
        other["body"] = S.joint.COMMAND + other["body"].split(" ", 2)[-1]
        self.refuse1("COMMENT_BODY", comment_raw=I.encoded(other), body_sha256=body_hash(other))

    def test_stage2_four_actual_job_tuples_match_references_only(self):
        for entry in self.two["firstPullRequest"]["runs"]:
            self.obs2 = observation2(self.two, entry["profile"], entry["role"])
            result = self.check2()
            value = json.loads(result.record)
            self.assertIs(type(result), S.OrdinaryMatch)
            self.assertNotIsInstance(result, I.Admission)
            self.assertEqual(value["source"], {"commit": MERGE, "tree": T2})
            self.assertEqual(value["policy"]["origin"], "reviewed-head")
            self.assertEqual(value["policy"]["commit"], H2)
            self.assertEqual(value["qualificationAcceptance"], "NOT_ESTABLISHED_BY_REFERENCE_MATCH")

    def test_stage2_validates_expired_stage1_historically_without_resetting_clocks(self):
        self.assertGreater(NOW, self.one["expiresAt"])
        self.refuse1("VALIDITY", now=NOW)
        value = json.loads(self.check2().record)
        first = json.loads(self.history[0].expected.record)
        self.assertEqual(first["firstUseAt"], FIRST1)
        self.assertEqual(first["expiresAt"], START + 150)
        self.assertEqual(value["firstUseAt"], FIRST2)
        self.assertEqual(value["reviewed"]["commit"], H2)

    def test_stage2_cannot_replace_historical_h1_with_current_h2(self):
        observed = json.loads(self.history[0].observation_raw)
        observed["reviewed"] = dict(self.two["reviewed"])
        histories = (dataclasses.replace(self.history[0], observation_raw=I.encoded(observed)), *self.history[1:])
        self.refuse2("CURRENT_SOURCE", histories=histories)

    def test_stage2_requires_distinct_reviewed_h2_and_h1_ancestry(self):
        for raw in (None, H2.encode() + b"\n", b"", b" " + H1.encode() + b"\n"):
            self.refuse2("STAGE1_ANCESTRY", prior_ancestry_raw=raw)
        self.two["stage1"]["reviewed"]["commit"] = H2
        self.refuse2("SEPARATE_REVIEWED_HEADS")

    def test_stage2_qualification_must_precede_its_new_personal_authority(self):
        for completed in (START + 200, START + 201, True, 0):
            self.two["qualifications"][0]["completedAt"] = completed
            histories = (dataclasses.replace(self.history[0], completed_at=completed), *self.history[1:])
            self.refuse2("QUALIFICATION_BEFORE_AUTHORITY", histories=histories)

    def test_stage2_cannot_extend_completed_stage1_window(self):
        self.two["qualifications"][0]["completedAt"] = START + 180
        histories = (dataclasses.replace(self.history[0], completed_at=START + 180), *self.history[1:])
        self.refuse2("VALIDITY", histories=histories)

    def test_historical_attempt_change_is_not_authorized(self):
        observed = json.loads(self.history[0].observation_raw)
        observed["github"]["runAttempt"] = "2"
        histories = (dataclasses.replace(self.history[0], observation_raw=I.encoded(observed)), *self.history[1:])
        self.refuse2("UNLISTED_BOOTSTRAP", histories=histories)

    def test_historical_comment_edited_or_missing_refuses(self):
        self.refuse2(histories=(dataclasses.replace(self.history[0], comment_raw=b""), *self.history[1:]))
        old = json.loads(self.history[0].comment_raw)
        old["updated_at"] = utc(START)
        self.refuse2("COMMENT_EDITED", histories=(dataclasses.replace(self.history[0], comment_raw=I.encoded(old)),
                                                    *self.history[1:]))

    def test_stage2_requires_every_exact_ordinary_cohort(self):
        self.two["qualifications"].pop()
        self.refuse2("QUALIFICATION_ROSTER")
        self.setUp()
        self.two["qualifications"][0] = copy.deepcopy(self.two["qualifications"][1])
        self.refuse2()

    def test_stage2_slot_reference_cannot_reuse_an_ordinary_run(self):
        self.two["qualifications"][0]["runId"] = "401"
        self.refuse2("QUALIFICATION_COHORT_OR_RUN")

    def test_stage2_cannot_reuse_one_packet_for_different_cohorts(self):
        self.two["qualifications"][1]["packet"]["artifactId"] = self.two["qualifications"][0]["packet"]["artifactId"]
        self.refuse2("DUPLICATE_PACKET")

    def test_stage2_swapped_histories_do_not_match_selected_packets(self):
        self.refuse2("HISTORICAL_SOURCE_OR_USE", histories=tuple(reversed(self.history)))

    def test_stage2_packet_inventory_compatibility_and_review_are_required_not_status_flags(self):
        for field in ("packet", "inventory", "compatibility", "review"):
            saved = self.two["qualifications"][0].pop(field)
            self.refuse2("QUALIFICATION_FIELDS")
            self.two["qualifications"][0][field] = saved
        for field in ("qualified", "cacheKey", "cacheHit", "saveSuccess", "probePresence"):
            self.two["qualifications"][0][field] = True
            self.refuse2("QUALIFICATION_FIELDS")
            del self.two["qualifications"][0][field]

    def test_reference_sizes_and_digests_are_not_wildcards(self):
        for name in ("packet", "inventory", "compatibility", "review"):
            for key, bad in (("bytes", 0), ("bytes", True), ("bytes", 1024 ** 3), ("sha256", "*"), ("sha256", "A" * 64)):
                saved = self.two["qualifications"][0][name][key]
                self.two["qualifications"][0][name][key] = bad
                self.refuse2()
                self.two["qualifications"][0][name][key] = saved

    def test_stage2_changed_reference_invalidates_original_recheck(self):
        expected = self.check2()
        for name in ("packet", "inventory", "compatibility", "review"):
            saved = self.two["qualifications"][0][name]["sha256"]
            self.two["qualifications"][0][name]["sha256"] = "f" * 64
            self.refuse2("CHANGED_BEFORE_RECHECK", expected=expected)
            self.two["qualifications"][0][name]["sha256"] = saved

    def test_stage2_rejects_closed_merged_changed_or_automatic_pr(self):
        for name, bad in (("state", "closed"), ("merged", True), ("merge_commit_sha", H2), ("auto_merge", {}), ("number", 998)):
            saved = self.obs2["pullRequest"][name]
            self.obs2["pullRequest"][name] = bad
            self.refuse2("PR_CURRENT")
            self.obs2["pullRequest"][name] = saved

    def test_stage2_rejects_changed_pr_base_head_branch_or_repository(self):
        for side in ("base", "head"):
            for name, value in (("sha", OTHER), ("ref", "other"), ("repo", {"full_name": "fork/P2pKit"})):
                saved = self.obs2["pullRequest"][side][name]
                self.obs2["pullRequest"][side][name] = value
                self.refuse2("PR_BASE_OR_HEAD")
                self.obs2["pullRequest"][side][name] = saved

    def test_stage2_requires_real_merge_identity_and_ordered_parents(self):
        for parents in ([H2, S.BASE["commit"]], [H2], None):
            self.obs2["mergeParents"] = parents
            self.refuse2("ORDINARY_MERGE")
        self.obs2["mergeParents"] = [S.BASE["commit"], H2]
        self.obs2["source"] = dict(self.two["reviewed"])
        self.refuse2("ORDINARY_MERGE")

    def test_stage2_merge_tree_must_equal_reviewed_h2_tree(self):
        self.two["firstPullRequest"]["merge"]["tree"] = T1
        self.refuse2("PR_MERGE_SOURCE")

    def test_ordinary_roster_has_three_desktops_one_full_and_distinct_run_ids(self):
        for index, field, value in ((3, "runId", "401"), (1, "runId", "999"), (1, "runAttempt", "2"),
                                     (3, "role", "linux-x64"), (2, "role", "linux-x64")):
            saved = self.two["firstPullRequest"]["runs"][index][field]
            self.two["firstPullRequest"]["runs"][index][field] = value
            self.refuse2()
            self.two["firstPullRequest"]["runs"][index][field] = saved

    def test_ordinary_job_run_attempt_workflow_host_and_ref_remain_exact(self):
        for name, value in (("runAttempt", "2"), ("runId", "402"), ("job", "initial-recipient-gate"),
                            ("ref", S.SOURCE_REF), ("workflowSha", H2), ("runnerArch", "ARM64"), ("event", "push")):
            saved = self.obs2["github"][name]
            self.obs2["github"][name] = value
            self.refuse2()
            self.obs2["github"][name] = saved

    def test_exact_base_commit_tree_ref_and_policy_pin_are_common_to_both_stages(self):
        for value, check in ((self.one, self.refuse1), (self.two, self.refuse2)):
            for name, bad in (("sourceRef", "refs/heads/main"), ("policySha256", "0" * 64),
                              ("schema", True), ("repository", "fork/P2pKit")):
                saved = value[name]
                value[name] = bad
                check("STATEMENT_SCOPE")
                value[name] = saved
            for name in ("commit", "tree"):
                saved = value["base"][name]
                value["base"][name] = OTHER
                check("STATEMENT_SCOPE")
                value["base"][name] = saved

    def test_observed_main_head_or_tree_changes_refuse(self):
        for observed, check in ((self.obs1, self.refuse1), (self.obs2, self.refuse2)):
            for side in ("base", "reviewed"):
                for name in ("commit", "tree"):
                    saved = observed[side][name]
                    observed[side][name] = OTHER
                    check("CURRENT_SOURCE")
                    observed[side][name] = saved

    def test_only_exact_empty_policy_query_stdout_counts_as_supplied_absence(self):
        for raw in (None, "", bytearray(), b"\n", b"MISSING_TRUSTED_RECIPIENT_POLICY", ENTRY,
                    ENTRY.replace(b"100644", b"100755"), ENTRY.replace(b"100644", b"120000")):
            self.refuse1("BASE_POLICY_NOT_ABSENT", base_policy_entry=raw)
            self.refuse2("BASE_POLICY_NOT_ABSENT", base_policy_entry=raw)

    def test_full_ancestry_requires_exact_line_not_truthy_success_or_whitespace(self):
        for raw in (None, b"true", b"", H1.encode() + b"\n", b" " + S.BASE["commit"].encode() + b"\n"):
            self.refuse1("BASE_ANCESTRY", ancestry_raw=raw)
            self.refuse2("BASE_ANCESTRY", ancestry_raw=raw)
        self.check1(ancestry_raw=S.BASE["commit"].encode() + b"\r\n")

    def test_policy_blob_mode_path_exact_bytes_and_hash_cannot_be_substituted(self):
        for raw in (None, ENTRY + ENTRY, ENTRY.replace(b"100644", b"120000"), ENTRY.replace(b".github", b"otherxx")):
            self.refuse1("POLICY_ENTRY", candidate_policy_entry=raw)
        self.refuse1("POLICY_BLOB", candidate_policy_entry=ENTRY.replace(BLOB.encode(), b"f" * 40))
        for raw in (None, b"", POLICY + b"\n"):
            self.refuse1("POLICY_DIGEST", candidate_policy_raw=raw)
            self.refuse2("POLICY_DIGEST", candidate_policy_raw=raw)

    def test_integer_windows_first_use_and_original_expiry_are_enforced(self):
        for now in (True, float(DONE1), FIRST1 - 1, self.one["expiresAt"]):
            self.refuse1(now=now)
        self.refuse2(now=END)
        for value, check in ((self.one, self.refuse1), (self.two, self.refuse2)):
            old = value["expiresAt"]
            value["expiresAt"] = END + 1
            check("VALIDITY")
            value["expiresAt"] = old
            value["notBefore"] = START - 1
            check("VALIDITY")

    def test_authority_after_first_use_is_not_retrospective_permission(self):
        self.override.update(created_at=utc(FIRST1 + 1), updated_at=utc(FIRST1 + 1))
        self.refuse1("VALIDITY_OR_PRIOR_AUTHORITY")
        self.override.update(created_at=utc(FIRST2 + 1), updated_at=utc(FIRST2 + 1))
        self.refuse2("VALIDITY_OR_PRIOR_AUTHORITY")

    def test_selected_comment_identity_location_and_body_digest_are_exact(self):
        self.refuse1("COMMENT_LOCATION", comment_id=8002)
        self.refuse1("COMMENT_DIGEST", body_sha256="f" * 64)
        for field in ("url", "html_url", "issue_url"):
            self.override[field] = "https://github.com/fork/P2pKit"
            self.refuse1("COMMENT_LOCATION")
            self.override.clear()

    def test_login_numeric_id_type_and_non_app_author_are_all_required(self):
        for field, bad in (("login", "apdelrahman1911"), ("id", "104788132"), ("id", True), ("type", "Bot")):
            self.override["user"] = {**OWNER, field: bad}
            self.refuse1("COMMENT_OWNER")
            self.refuse2("COMMENT_OWNER")
        self.override = {"performed_via_github_app": {"id": 3}}
        self.refuse1("COMMENT_OWNER")

    def test_edited_comment_and_command_whitespace_aliases_refuse(self):
        self.override["updated_at"] = utc(START)
        self.refuse1("COMMENT_EDITED")
        self.override.clear()
        original = comment(self.one, 8001, START - 60)["body"]
        for body in (original + "\n", original + " ", " " + original, "```\n" + original + "\n```"):
            self.override["body"] = body
            self.refuse1()

    def test_environment_actual_id_branch_policy_ids_and_order_are_pinned(self):
        original = self.check1()
        self.one["environment"]["id"] = 200
        self.refuse1("CHANGED_BEFORE_RECHECK", expected=original)
        self.one["environment"]["id"] = 101
        self.one["environment"]["branchPolicies"].reverse()
        self.refuse1("ENVIRONMENT_BRANCHES")

    def test_environment_rejects_publication_environment_wildcard_or_tag_policy(self):
        self.one["environment"]["name"] = "sample-development-release"
        self.refuse1("ENVIRONMENT_NAME")
        self.one["environment"]["name"] = S.ENVIRONMENT
        for field, bad in (("name", "*"), ("type", "tag"), ("id", True)):
            saved = self.one["environment"]["branchPolicies"][0][field]
            self.one["environment"]["branchPolicies"][0][field] = bad
            self.refuse1()
            self.one["environment"]["branchPolicies"][0][field] = saved

    def test_stage2_cannot_accept_recreated_environment_from_stage1(self):
        self.two["environment"]["id"] = 202
        self.refuse2("HISTORICAL_SOURCE_OR_USE")

    def test_closed_fields_missing_fields_and_bad_json_refuse(self):
        for value, check in ((self.one, self.refuse1), (self.two, self.refuse2),
                             (self.obs1, self.refuse1), (self.obs2, self.refuse2)):
            for field in list(value):
                saved = value.pop(field)
                check()
                value[field] = saved
            value["assumedAuthority"] = True
            check("FIELDS")
            del value["assumedAuthority"]
        for raw in (b"", b"[]", b"{", b'{"x":1,"x":1}', b'{"x":NaN}', b"x" * (S.LIMIT + 1)):
            self.refuse1(comment_raw=raw)
            self.refuse2(observation_raw=raw)

    def test_results_are_immutable_and_cross_stage_rechecks_refuse(self):
        first, second = self.check1(), self.check2()
        self.assertEqual(self.check1(expected=first, now=DONE1 + 1), first)
        self.assertEqual(self.check2(expected=second, now=NOW + 1), second)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.record = b"changed"
        self.refuse1("CHANGED_BEFORE_RECHECK", expected=second)
        self.refuse2("CHANGED_BEFORE_RECHECK", expected=first)

    def test_rechecks_reject_nonexact_bytes_before_equality_can_override(self):
        class Forged:
            def __eq__(self, other):
                raise AssertionError("Comparison must not run")
        class Bytes(bytes):
            def __eq__(self, other):
                raise AssertionError("Subclass comparison must not run")
        for good, kind, refuse in ((self.check1(), S.BootstrapMatch, self.refuse1),
                                    (self.check2(), S.OrdinaryMatch, self.refuse2)):
            for raw in (Forged(), Bytes(good.record), bytearray(good.record), memoryview(good.record)):
                refuse("CHANGED_BEFORE_RECHECK", expected=kind(raw))

    def test_historical_record_cannot_override_equality(self):
        histories = (dataclasses.replace(self.history[0], expected=S.BootstrapMatch(bytearray(self.history[0].expected.record))),
                     *self.history[1:])
        self.refuse2("HISTORICAL_RECORD_TYPE", histories=histories)

    def test_unrelated_rest_metadata_is_not_changed_authority(self):
        expected = self.check1()
        self.override = {"reactions": {"total_count": 10}, "user": {**OWNER, "avatar_url": "https://example.invalid/model"}}
        self.assertEqual(self.check1(expected=expected), expected)


if __name__ == "__main__":
    unittest.main()
