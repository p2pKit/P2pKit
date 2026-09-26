#!/usr/bin/env python3
"""Offline supplied-record models, NOT approvals, GPG or hosted trust acquisition.

Only the already committed PUBLIC policy is read. Commit/run/PR/comment records
are synthetic, with explicit modeled times. No custodian-directory access.
The audit guard is installed before every project import; no child/network use.
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
import hosted_initial_recipient_exception as E

I, B = E.identity, E.bootstrap
HEAD, TREE, MERGE, OTHER = (c * 40 for c in "abcd")
START, END, NOW = 1789948800, 1791158400, 1789948920
POLICY = (ROOT / ".github/test-evidence-recipient.json").read_bytes()
BLOB = hashlib.sha1(b"blob " + str(len(POLICY)).encode("ascii") + b"\x00" + POLICY).hexdigest()
ENTRY = b"100644 blob " + BLOB.encode("ascii") + b"\t.github/test-evidence-recipient.json\x00"
OWNER = {"login": "Apdelrahman1911", "id": 104788132, "type": "User"}
SELECTIONS = ("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "desktop-macos-x64",
              "full-macos-arm64", "full-macos-x64")


def utc(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def declaration():
    return {"schema": 1, "scope": "P2PKIT_INITIAL_RECIPIENT_EXCEPTION_V1", "repository": "p2pKit/P2pKit",
            "base": dict(E.BASE), "reviewed": {"commit": HEAD, "tree": TREE},
            "sourceRef": "refs/heads/work/release-foundation-20260926-1WzHcOIr",
            "policySha256": "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521",
            "notBefore": START, "expiresAt": END,
            "bootstrap": [{"selection": name, "runId": str(100 + n), "runAttempt": "1"}
                          for n, name in enumerate(SELECTIONS)],
            "firstPullRequest": {"number": 999, "merge": {"commit": MERGE, "tree": TREE}, "runs": [
                {"profile": "desktop", "role": "linux-x64", "runId": "201", "runAttempt": "1"},
                {"profile": "desktop", "role": "windows-x64", "runId": "201", "runAttempt": "1"},
                {"profile": "desktop", "role": "macos-arm64", "runId": "201", "runAttempt": "1"},
                {"profile": "full", "role": "macos-arm64", "runId": "202", "runAttempt": "1"}]}}


def comment(value):
    body = E.COMMAND + I.encoded(value).decode("ascii").removesuffix("\n")
    return {"id": 9001, "url": "https://api.github.com/repos/p2pKit/P2pKit/issues/comments/9001",
            "issue_url": "https://api.github.com/repos/p2pKit/P2pKit/issues/437",
            "html_url": "https://github.com/p2pKit/P2pKit/issues/437#issuecomment-9001",
            "user": dict(OWNER), "performed_via_github_app": None,
            "created_at": utc(START - 60), "updated_at": utc(START - 60), "body": body}


def observation(value, *, selection="desktop-linux-x64", profile="cache-bootstrap", role="linux-x64"):
    initial = profile == "cache-bootstrap"
    if initial:
        entry = next(x for x in value["bootstrap"] if x["selection"] == selection)
        _, role, system, arch = B.selection(selection)
        source = value["reviewed"]
        workflow, job, event, ref = B.WORKFLOW, B.JOB, "workflow_dispatch", value["sourceRef"]
    else:
        entry = next(x for x in value["firstPullRequest"]["runs"] if x["profile"] == profile and x["role"] == role)
        system, arch = E.ROLES[role]
        source = value["firstPullRequest"]["merge"]
        workflow, job, _ = I.PROFILES[profile]
        event, ref = "pull_request", "refs/pull/999/merge"
    github = {"profile": profile, "event": event, "ref": ref, "workflow": workflow,
              "workflowSha": source["commit"], "job": job, "runId": entry["runId"], "runAttempt": entry["runAttempt"],
              "runnerOS": system, "runnerArch": arch}
    if initial:
        github["selection"] = selection
    pr = {"number": 999, "state": "open", "merged": False,
        "merge_commit_sha": MERGE, "user": dict(OWNER), "auto_merge": None,
        "url": "https://api.github.com/repos/p2pKit/P2pKit/pulls/999",
        "html_url": "https://github.com/p2pKit/P2pKit/pull/999",
        "base": {"sha": E.BASE["commit"], "ref": "main", "repo": {"full_name": "p2pKit/P2pKit"}},
        "head": {"sha": HEAD, "ref": value["sourceRef"].removeprefix("refs/heads/"),
                 "repo": {"full_name": "p2pKit/P2pKit"}}}
    return {"repository": "p2pKit/P2pKit", "base": dict(value["base"]), "reviewed": dict(value["reviewed"]),
            "source": dict(source), "github": github, "pullRequest": pr,
            "mergeParents": None if initial else [E.BASE["commit"], HEAD], "firstUseAt": START + 60}


class SuppliedRecordModels(unittest.TestCase):
    def setUp(self):
        self.value = declaration()
        self.observed = observation(self.value)
        self.override = {}
        self.options = {}

    def check(self, **kwargs):
        authored = comment(self.value)
        authored.update(self.override)
        options = {"comment_raw": I.encoded(authored), "comment_id": 9001,
                   "body_sha256": hashlib.sha256(authored["body"].encode("utf-8")).hexdigest(),
                   "observation_raw": I.encoded(self.observed), "base_policy_entry": b"",
                   "ancestry_raw": E.BASE["commit"].encode("ascii") + b"\n",
                   "candidate_policy_entry": ENTRY, "candidate_policy_raw": POLICY, "now": NOW}
        options.update(self.options)
        options.update(kwargs)
        return E.match(**options)

    def refuse(self, code=None, **kwargs):
        with self.assertRaisesRegex(I.AdmissionError, code or ".+"):
            self.check(**kwargs)

    def pr(self, profile="desktop", role="linux-x64"):
        self.observed = observation(self.value, profile=profile, role=role)

    def test_public_policy_pin_without_crypto_or_key_generation(self):
        self.assertEqual(len(POLICY), 3631)
        self.assertEqual(hashlib.sha256(POLICY).hexdigest(), E.POLICY_SHA256)
        self.assertEqual(BLOB, "118bf7577771ca79aeaf016d9f9602cb5b666dfa")

    def test_foundation_lane_has_an_independent_fixed_positive(self):
        expected = "refs/heads/work/release-foundation-20260926-1WzHcOIr"
        self.assertEqual(E.SOURCE_REF, expected)
        self.assertEqual(self.value["sourceRef"], expected)
        self.assertIs(type(self.check()), E.Match)

    def test_previous_campaign_statement_cannot_authorize_foundation(self):
        self.value["sourceRef"] = "refs/heads/work/nonphysical-integration-20260915-022112"
        # Reconstruct a consistent old-lane observation and rehash the actual
        # supplied comment. Refusal must be the fixed lane, not a stale digest.
        self.observed = observation(self.value)
        self.refuse("STATEMENT_SCOPE")

    def test_all_six_closed_bootstrap_tuples_match_only(self):
        for name in SELECTIONS:
            with self.subTest(selection=name):
                self.observed = observation(self.value, selection=name)
                result = self.check()
                self.assertIs(type(result), E.Match)
                self.assertNotIsInstance(result, I.Admission)
                self.assertTrue(json.loads(result.record)["scope"].endswith("MATCH_ONLY_NOT_ADMISSION"))

    def test_four_first_pr_jobs_keep_real_merge_and_candidate_policy_source_distinct(self):
        for profile, role in (("desktop", "linux-x64"), ("desktop", "windows-x64"),
                              ("desktop", "macos-arm64"), ("full", "macos-arm64")):
            self.pr(profile, role)
            record = json.loads(self.check().record)
            self.assertEqual(record["source"], {"commit": MERGE, "tree": TREE})
            self.assertEqual(record["policy"]["commit"], HEAD)
            self.assertEqual(record["originalBase"], E.BASE)

    def test_explicit_intel_host_rosters_do_not_inherit_arm_host_authority(self):
        self.value["firstPullRequest"]["runs"][2]["role"] = "macos-x64"
        self.value["firstPullRequest"]["runs"][3]["role"] = "macos-x64"
        for profile in ("desktop", "full"):
            self.pr(profile, "macos-x64")
            self.check()
            self.observed["github"]["runnerArch"] = "ARM64"
            self.refuse("UNLISTED_USE")

    def test_frozen_result_and_repeat_validation_are_idempotent_not_consumption(self):
        original = self.check()
        self.assertEqual(self.check(expected=original, now=NOW + 1), original)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            original.record = b"changed"
        record = json.loads(original.record)
        record["source"]["commit"] = OTHER
        self.assertEqual(json.loads(original.record)["source"]["commit"], HEAD)

    def test_unrelated_rest_metadata_change_preserves_stable_authority(self):
        original = self.check()
        self.override["reactions"] = {"total_count": 7}
        self.override["user"] = {**OWNER, "avatar_url": "https://example.invalid/synthetic"}
        self.assertEqual(self.check(expected=original), original)

    def test_initial_absence_is_exact_empty_original_not_mode_type_or_error(self):
        for raw in (None, "", b"\n", b"MISSING_TRUSTED_RECIPIENT_POLICY", ENTRY,
                    ENTRY.replace(b"100644", b"100755"), ENTRY.replace(b"100644", b"120000"),
                    ENTRY.replace(b"100644 blob", b"160000 commit"),
                    ENTRY.replace(b"100644 blob", b"040000 tree"), ENTRY + ENTRY):
            with self.subTest(kind=type(raw).__name__):
                self.refuse("BASE_POLICY_NOT_ABSENT", base_policy_entry=raw)

    def test_original_ancestry_refuses_failure_wrong_sha_and_loose_whitespace(self):
        self.check(ancestry_raw=E.BASE["commit"].encode("ascii") + b"\r\n")
        for raw in (None, b"", b"false\n", HEAD.encode() + b"\n", E.BASE["commit"].encode(),
                    b" " + E.BASE["commit"].encode() + b"\n"):
            self.refuse("BASE_ANCESTRY", ancestry_raw=raw)

    def test_candidate_policy_requires_exact_regular_blob_path_and_bytes(self):
        for raw in (None, b"", ENTRY.replace(b"100644", b"100755"), ENTRY.replace(b"100644", b"120000"),
                    ENTRY.replace(b"blob", b"tree"), ENTRY.replace(b".github/", b"other/"), ENTRY + ENTRY,
                    ENTRY[:-1], b"x" * 257):
            self.refuse("POLICY_ENTRY", candidate_policy_entry=raw)
        self.refuse("POLICY_BLOB", candidate_policy_entry=ENTRY.replace(BLOB.encode(), b"f" * 40))
        for raw in (None, b"", POLICY + b"\n", POLICY.replace(b"Apdelrahman1911", b"some-other-owner")):
            self.refuse("POLICY_DIGEST", candidate_policy_raw=raw)

    def test_statement_source_base_tree_policy_and_branch_are_not_repinable(self):
        for field, value in (("repository", "fork/P2pKit"), ("scope", "ordinary"), ("schema", True),
                             ("policySha256", "0" * 64), ("sourceRef", "refs/heads/main")):
            with self.subTest(field=field):
                good = self.value[field]
                self.value[field] = value
                self.refuse("STATEMENT_SCOPE")
                self.value[field] = good
        for field in ("commit", "tree"):
            old = self.value["base"][field]
            self.value["base"][field] = OTHER
            self.refuse("STATEMENT_SCOPE")
            self.value["base"][field] = old

    def test_observed_main_reviewed_head_and_tree_changes_fail_closed(self):
        for container in ("base", "reviewed", "source"):
            for field in ("commit", "tree"):
                old = self.observed[container][field]
                self.observed[container][field] = OTHER
                self.refuse()
                self.observed[container][field] = old

    def test_abbreviated_nonstring_and_uppercase_shas_refuse(self):
        for bad in ("a" * 7, "G" * 40, "A" * 40, None, True, [], HEAD + "\n"):
            self.observed["reviewed"]["commit"] = bad
            self.refuse()

    def test_closed_statement_and_observation_fields_reject_extensions_and_omissions(self):
        for target in (self.value, self.observed):
            for field in list(target):
                saved = target.pop(field)
                self.refuse()
                target[field] = saved
            target["trusted"] = True
            self.refuse()
            del target["trusted"]

    def test_duplicate_nonfinite_malformed_oversize_json_refuses(self):
        for raw in (b"", b"[]", b"{", b'{"schema":1,"schema":1}', b'{"number":NaN}', b"x" * (E.LIMIT + 1)):
            self.refuse(comment_raw=raw)
            self.refuse(observation_raw=raw)

    def test_owner_requires_login_numeric_id_human_type_and_no_app(self):
        for field, value in (("login", "other"), ("login", "apdelrahman1911"), ("id", 104788133),
                             ("id", "104788132"), ("id", True), ("type", "Bot")):
            self.override["user"] = {**OWNER, field: value}
            self.refuse("COMMENT_OWNER")
        del self.override["user"]
        self.override["performed_via_github_app"] = {"id": 1}
        self.refuse("COMMENT_OWNER")
        value = comment(self.value)
        del value["performed_via_github_app"]
        self.refuse("COMMENT_OWNER", comment_raw=I.encoded(value))

    def test_exact_comment_location_and_explicit_selected_id(self):
        for field, value in (("id", 9002), ("id", "9001"), ("url", "https://example.invalid"),
                             ("issue_url", "https://api.github.com/repos/p2pKit/P2pKit/issues/424"),
                             ("html_url", "https://github.com/p2pKit/P2pKit/pull/999#issuecomment-9001")):
            self.override = {field: value}
            self.refuse("COMMENT_LOCATION")
        self.override = {}
        for value in (True, 0, -1, "9001", 10 ** 20):
            self.refuse("COMMENT_ID", comment_id=value)

    def test_wrong_pinned_body_digest_and_noncanonical_authorization_refuse(self):
        self.refuse("COMMENT_DIGEST", body_sha256="0" * 64)
        for bad in (None, "0" * 63, "A" * 64):
            self.refuse("COMMENT_DIGEST", body_sha256=bad)
        good = comment(self.value)["body"]
        for body in (good + "\n", good + " ", good.replace('"schema":1', '"schema": 1'),
                     "```\n" + good + "\n```", "/p2pkit approve-pr " + HEAD, "Agent progress: " + good):
            self.override["body"] = body
            self.refuse()

    def test_invalid_unicode_in_body_is_a_fixed_safe_error(self):
        value = comment(self.value)
        value["body"] = E.COMMAND + '\ud800'
        self.refuse("COMMENT_BODY", comment_raw=I.encoded(value))

    def test_edited_invalid_or_missing_comment_time_refuses(self):
        self.override["updated_at"] = utc(START)
        self.refuse("COMMENT_EDITED")
        for bad in (None, "", "2026-02-30T00:00:00Z", "2026-09-21", "2026-09-21T00:00:00+00:00"):
            self.override = {"created_at": bad, "updated_at": bad}
            self.refuse("COMMENT_TIME")

    def test_authority_must_predate_original_first_use_and_not_be_from_future(self):
        for epoch in (START + 61, NOW + 1):
            self.override = {"created_at": utc(epoch), "updated_at": utc(epoch)}
            self.refuse("VALIDITY_OR_PRIOR_AUTHORITY")
        self.override = {"created_at": utc(START + 60), "updated_at": utc(START + 60)}
        self.check()

    def test_real_policy_window_inclusive_start_exclusive_end_only_in_models(self):
        self.observed["firstUseAt"] = START
        self.check(now=START)
        self.check(now=END - 1)
        for epoch in (START - 1, END, True, "1789948800"):
            self.refuse("RECIPIENT_POLICY_VALIDITY", now=epoch)

    def test_exception_can_shorten_but_not_renew_or_backdate_policy(self):
        self.value["notBefore"], self.value["expiresAt"] = START + 60, NOW + 1
        self.check()
        self.refuse("VALIDITY_OR_PRIOR_AUTHORITY", now=NOW + 1)
        self.value["expiresAt"] = END + 1
        self.refuse("VALIDITY_OR_PRIOR_AUTHORITY")
        self.value["expiresAt"], self.value["notBefore"] = END, START - 1
        self.refuse("VALIDITY_OR_PRIOR_AUTHORITY")

    def test_times_are_exact_integers_and_first_use_cannot_be_reset_on_recheck(self):
        for field in ("notBefore", "expiresAt"):
            old = self.value[field]
            for bad in (True, None, "1789948800", 1789948800.0):
                self.value[field] = bad
                self.refuse("VALIDITY_OR_PRIOR_AUTHORITY")
            self.value[field] = old
        old = self.check()
        self.observed["firstUseAt"] += 1
        self.refuse("CHANGED_BEFORE_RECHECK", expected=old)
        for bad in (True, None, NOW + 1, START - 1):
            self.observed["firstUseAt"] = bad
            self.refuse("VALIDITY_OR_PRIOR_AUTHORITY")

    def test_source_merge_and_tree_cannot_substitute_for_reviewed_head(self):
        self.pr()
        self.observed["source"]["commit"] = HEAD
        self.refuse("PR_SOURCE")
        self.observed["source"]["commit"] = MERGE
        self.value["firstPullRequest"]["merge"]["tree"] = OTHER
        self.observed["source"]["tree"] = OTHER
        self.refuse("PR_MERGE_SOURCE")
        self.value["firstPullRequest"]["merge"]["tree"] = TREE
        for bad in (HEAD, E.BASE["commit"]):
            self.value["firstPullRequest"]["merge"]["commit"] = bad
            self.refuse("PR_MERGE_SOURCE")

    def test_pr_requires_exact_two_ordered_parents(self):
        self.pr()
        for parents in (None, [], [HEAD, E.BASE["commit"]], [HEAD], [E.BASE["commit"], HEAD, OTHER]):
            self.observed["mergeParents"] = parents
            self.refuse("PR_SOURCE")

    def test_exact_open_unmerged_owner_pr_without_auto_merge(self):
        self.pr()
        pr = self.observed["pullRequest"]
        for field, bad in (("number", 998), ("state", "closed"), ("merged", True), ("merged", 0),
                           ("merge_commit_sha", OTHER), ("user", {**OWNER, "id": 99}),
                           ("auto_merge", {}), ("url", "https://example.invalid"), ("html_url", "")):
            old = pr[field]
            pr[field] = bad
            self.refuse("PR_CURRENT")
            pr[field] = old

    def test_other_pr_base_head_branch_or_repository_is_not_the_first_pr(self):
        self.pr()
        for side in ("base", "head"):
            value = self.observed["pullRequest"][side]
            for field in ("sha", "ref", "repo"):
                old = value[field]
                value[field] = {"full_name": "fork/P2pKit"} if field == "repo" else OTHER
                self.refuse("PR_BASE_OR_HEAD")
                value[field] = old

    def test_pr_numbers_are_bounded_integers_not_bool_or_wildcards(self):
        for value in (None, True, 0, -1, 10 ** 10 + 1, "999", "*"):
            self.value["firstPullRequest"]["number"] = value
            self.refuse("NUMBER")

    def test_first_pr_roster_requires_all_four_native_jobs(self):
        entries = copy.deepcopy(self.value["firstPullRequest"]["runs"])
        for rows in (None, [], entries[:-1], entries + [entries[0]], entries[:2] + [entries[2], entries[2]]):
            self.value["firstPullRequest"]["runs"] = rows
            self.refuse()

    def test_one_desktop_run_and_separate_full_run_with_closed_roles(self):
        entries = self.value["firstPullRequest"]["runs"]
        for field, bad in (("runId", "301"), ("runAttempt", "2"), ("profile", "manual"), ("role", "linux-arm64")):
            old = entries[1][field]
            entries[1][field] = bad
            self.refuse()
            entries[1][field] = old
        entries[3]["runId"] = "201"
        self.refuse("DUPLICATE_RUN")

    def test_bootstrap_roster_cannot_be_empty_duplicated_or_omit_a_pr_cohort(self):
        entries = copy.deepcopy(self.value["bootstrap"])
        for rows in (None, [], entries + [entries[0]], entries[1:], entries[:-1] + [entries[0]]):
            self.value["bootstrap"] = rows
            self.refuse()
        # Optional Intel cohorts may be left out; missing ordinary cohorts may not.
        self.value["bootstrap"] = [entries[n] for n in (0, 1, 2, 4)]
        self.check()

    def test_distinct_run_ids_cannot_overlap_profiles_cohorts_or_attempts(self):
        for value in ("201", "202", "101"):
            self.value["bootstrap"][0]["runId"] = value
            self.refuse("DUPLICATE_RUN")
        self.value["bootstrap"][0]["runAttempt"] = "2"
        self.refuse("DUPLICATE_RUN")

    def test_placeholder_alias_and_unbounded_run_identifiers_refuse(self):
        for field in ("runId", "runAttempt"):
            old = self.value["bootstrap"][0][field]
            for bad in (None, True, 1, "", "*", "TBD", "0", "01", "1\n", "1" * 21):
                self.value["bootstrap"][0][field] = bad
                self.refuse("RUN")
            self.value["bootstrap"][0][field] = old

    def test_bootstrap_selections_and_roster_fields_are_closed(self):
        seed = self.value["bootstrap"][0]
        for value in (None, "desktop", "full-linux-x64", "*", "desktop-linux-x64\n"):
            seed["selection"] = value
            self.refuse("BOOTSTRAP_SELECTION")
        seed["selection"] = "desktop-linux-x64"
        for key in ("command", "recipient", "timeout", "trusted"):
            seed[key] = ""
            self.refuse("BOOTSTRAP_RUN_FIELDS")
            del seed[key]

    def test_missing_or_added_roster_fields_refuse(self):
        for target in (self.value["bootstrap"][0], self.value["firstPullRequest"], self.value["firstPullRequest"]["runs"][0]):
            for key in list(target):
                saved = target.pop(key)
                self.refuse()
                target[key] = saved
            target["extra"] = None
            self.refuse()
            del target["extra"]

    def test_rerun_new_run_or_cross_cohort_replay_is_not_approved(self):
        for mode in ("cache-bootstrap", "desktop", "full"):
            self.observed = observation(self.value, profile=mode, role="macos-arm64" if mode == "full" else "linux-x64")
            for key, bad in (("runId", "9999"), ("runAttempt", "2")):
                old = self.observed["github"][key]
                self.observed["github"][key] = bad
                self.refuse("UNLISTED_USE")
                self.observed["github"][key] = old
        self.observed = observation(self.value)
        self.observed["github"]["selection"] = "desktop-windows-x64"
        self.refuse("UNLISTED_USE")

    def test_job_workflow_ref_host_or_event_cannot_be_relabelled(self):
        for mode in ("cache-bootstrap", "desktop", "full"):
            self.observed = observation(self.value, profile=mode, role="macos-arm64" if mode == "full" else "linux-x64")
            for key in ("event", "ref", "workflow", "workflowSha", "job", "runnerOS", "runnerArch"):
                old = self.observed["github"][key]
                for bad in (None, "other", True):
                    self.observed["github"][key] = bad
                    self.refuse()
                self.observed["github"][key] = old
            for event in ("push", "schedule", "workflow_run", "pull_request_target", "release"):
                self.observed["github"]["event"] = event
                self.refuse("EXECUTION_BINDING")

    def test_bootstrap_requires_joint_pr_identity_and_no_merge_parent_substitution(self):
        self.observed["pullRequest"] = {}
        self.refuse("PR_CURRENT")
        self.observed["pullRequest"] = observation(self.value)["pullRequest"]
        self.observed["mergeParents"] = [E.BASE["commit"], HEAD]
        self.refuse("BOOTSTRAP_SOURCE")

    def test_pr_closure_merge_and_head_change_retire_unused_bootstrap_slots_too(self):
        for name in SELECTIONS:
            for key, value in (("state", "closed"), ("merged", True), ("merge_commit_sha", OTHER)):
                self.observed = observation(self.value, selection=name)
                self.observed["pullRequest"][key] = value
                self.refuse("PR_CURRENT")
            self.observed = observation(self.value, selection=name)
            self.observed["pullRequest"]["head"]["sha"] = OTHER
            self.refuse("PR_BASE_OR_HEAD")

    def test_use_fields_do_not_admit_extra_or_missing_execution_authority(self):
        for mode in ("cache-bootstrap", "desktop"):
            self.observed = observation(self.value, profile=mode)
            value = self.observed["github"]
            for key in list(value):
                saved = value.pop(key)
                self.refuse()
                value[key] = saved
            value["approved"] = True
            self.refuse("GITHUB_FIELDS")

    def test_recheck_does_not_accept_new_authority_even_for_same_source(self):
        original = self.check()
        self.override = {"id": 9002, "url": "https://api.github.com/repos/p2pKit/P2pKit/issues/comments/9002",
                         "html_url": "https://github.com/p2pKit/P2pKit/issues/437#issuecomment-9002"}
        self.refuse("CHANGED_BEFORE_RECHECK", expected=original, comment_id=9002)
        self.override = {}
        self.value["expiresAt"] -= 1
        self.refuse("CHANGED_BEFORE_RECHECK", expected=original)
        self.refuse("CHANGED_BEFORE_RECHECK", expected={"record": original.record})

    def test_expected_record_rejects_mutable_and_nonbyte_values(self):
        record = self.check().record
        for value in (None, record.decode("ascii"), bytearray(record), memoryview(record)):
            with self.subTest(kind=type(value).__name__):
                self.refuse("CHANGED_BEFORE_RECHECK", expected=E.Match(value))

    def test_expected_record_cannot_override_byte_comparison(self):
        calls = []

        class ForgedRecord:
            def __eq__(self, other):
                calls.append("nonbyte-comparison")
                return True

        class OverridingBytes(bytes):
            def __eq__(self, other):
                calls.append("subclass-comparison")
                return True

        for value in (ForgedRecord(), OverridingBytes(self.check().record)):
            with self.subTest(kind=type(value).__name__):
                self.refuse("CHANGED_BEFORE_RECHECK", expected=E.Match(value))
                self.assertEqual(calls, [])

    def test_original_ordinary_and_bootstrap_admission_still_refuse_absent_base(self):
        class AbsentBase:
            def __init__(self, commit):
                self.head, self.reads = commit, []
            def root_matches(self): return True
            def clean(self): return True
            def commit(self, ref): return self.head if ref == "HEAD" else E.BASE["commit"]
            def tree(self, commit): return TREE
            def parents(self, commit): return [E.BASE["commit"], HEAD]
            def query(self, *args): return b"false" if args[0] == "rev-parse" else E.BASE["commit"].encode()
            def policy(self, commit):
                self.reads.append(commit)
                raise I.AdmissionError("MISSING_TRUSTED_RECIPIENT_POLICY")
        for profile in ("cache-bootstrap", "desktop", "full"):
            current = observation(self.value, profile=profile, role="macos-arm64" if profile == "full" else "linux-x64")
            github = current["github"]
            env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY,
                   "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
                   "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": github["runnerOS"], "RUNNER_ARCH": github["runnerArch"],
                   "GITHUB_JOB": github["job"], "GITHUB_RUN_ID": github["runId"], "GITHUB_RUN_ATTEMPT": github["runAttempt"],
                   "GITHUB_EVENT_NAME": github["event"], "GITHUB_REF": github["ref"],
                   "GITHUB_SHA": current["source"]["commit"], "GITHUB_WORKFLOW_SHA": current["source"]["commit"],
                   "GITHUB_WORKFLOW_REF": I.REPOSITORY + "/" + github["workflow"] + "@" + github["ref"]}
            event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"}}
            if profile == "cache-bootstrap":
                event.update(ref=E.SOURCE_REF, inputs={"selection": "desktop-linux-x64", "expected_sha": HEAD, "expected_tree": TREE})
            else:
                event.update(number=999, action="opened", pull_request=current["pullRequest"])
            git = AbsentBase(current["source"]["commit"])
            with self.assertRaisesRegex(I.AdmissionError, "^MISSING_TRUSTED_RECIPIENT_POLICY$"):
                if profile == "cache-bootstrap":
                    B._admit(env, I.encoded(event), git, NOW)
                else:
                    I._admit(profile, env, I.encoded(event), git, NOW)
            self.assertEqual(git.reads, [E.BASE["commit"]])


if __name__ == "__main__":
    unittest.main()
