#!/usr/bin/env python3
"""Pure source/API cross-check controls; no network, Terminal or native work."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rpc_apple_ci_metadata as m

ROOT, PYTHON = "/private/ci/source", "/private/tools/python3"
SHA, TREE, BASE, HEAD = (character * 40 for character in "abcd")


def fixture():
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": m.REPOSITORY,
           "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": m.API,
           "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
           "GITHUB_JOB": "platform-checks", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
           "GITHUB_SHA": SHA, "GITHUB_WORKSPACE": ROOT, "GITHUB_REF": "refs/pull/463/merge",
           "GITHUB_WORKFLOW_REF": m.REPOSITORY + "/.github/workflows/ci.yml@refs/pull/463/merge",
           "GITHUB_EVENT_NAME": "pull_request", "RUNNER_NAME": "synthetic-worker"}
    event = {"repository": {"full_name": m.REPOSITORY}, "number": 463,
             "pull_request": {"base": {"sha": BASE, "repo": {"full_name": m.REPOSITORY}},
                              "head": {"sha": HEAD}}}
    checkout = {"commit": SHA, "tree": TREE, "parents": [BASE, HEAD], "status": ""}
    scope = {"full": True, "head": SHA}
    run = {"id": 123, "run_attempt": 2, "event": "pull_request", "head_sha": HEAD,
           "path": ".github/workflows/ci.yml", "status": "in_progress", "conclusion": None,
           "repository": {"full_name": m.REPOSITORY}}
    job = {"id": 456, "run_id": 123, "run_attempt": 2, "head_sha": HEAD,
           "name": "platform-checks", "status": "in_progress", "conclusion": None,
           "completed_at": None, "runner_name": "synthetic-worker", "runner_id": 789,
           "started_at": "2026-10-14T03:50:19Z"}
    jobs = {"total_count": 1, "jobs": [job]}
    return [env, event, checkout, scope, run, jobs]


def project(values):
    return m.project_context(*values, root=ROOT, python=PYTHON)


class MetadataControls(unittest.TestCase):
    def test_pr_api_head_is_branch_head_and_execution_remains_actual_synthetic_merge(self):
        value = project(fixture())
        self.assertEqual(value["binding"]["source"], {"commit": SHA, "tree": TREE})
        self.assertEqual(value["observedRun"]["sha"], SHA)
        self.assertEqual(value["binding"]["pr"]["head"], HEAD)
        self.assertFalse(value["nativeExecutionAuthorized"])
        self.assertFalse(value["cleanupVerified"])
        self.assertEqual(value["job"]["startedWall"], 1791949819.0)

    def test_api_synthetic_sha_cannot_substitute_for_recorded_pr_head(self):
        for target in (4, 5):
            value = fixture()
            row = value[4] if target == 4 else value[5]["jobs"][0]
            row["head_sha"] = SHA
            with self.subTest(target=target), self.assertRaises(ValueError):
                project(value)

    def test_exact_git_parents_and_clean_tree_are_independently_required(self):
        for change in ({"commit": HEAD}, {"parents": [HEAD, BASE]}, {"parents": [HEAD]},
                       {"status": " M source.kt"}):
            value = fixture()
            value[2].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                project(value)

    def test_real_ci_profiles_only_not_narrow_consumer_or_other_job(self):
        value = fixture()
        value[0]["GITHUB_JOB"] = value[5]["jobs"][0]["name"] = "artifact-checks"
        result = project(value)
        self.assertEqual(result["binding"]["profile"], "consumers-complete")
        self.assertEqual(result["binding"]["argv"], ["/bin/bash", ROOT + "/scripts/check-published-consumers.sh"])
        value[0]["GITHUB_JOB"] = value[5]["jobs"][0]["name"] = "diagnostic"
        with self.assertRaises(ValueError):
            project(value)

    def test_source_repository_event_and_current_attempt_cannot_change(self):
        changes = {"id": 124, "run_attempt": 1, "event": "push", "path": "other.yml",
                   "repository": {"full_name": "other/repository"}, "head_sha": BASE,
                   "status": "completed", "conclusion": "success"}
        for key, changed in changes.items():
            value = fixture()
            value[4][key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(value)

    def test_host_workflow_and_exact_job_identity_are_required(self):
        changes = {"GITHUB_SERVER_URL": "https://other.invalid", "GITHUB_API_URL": "https://other.invalid",
                   "GITHUB_ACTIONS": "false", "GITHUB_REPOSITORY": "other/repo",
                   "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X86",
                   "RUNNER_NAME": "another-worker", "GITHUB_WORKSPACE": "/private/other",
                   "GITHUB_WORKFLOW_REF": m.REPOSITORY + "/.github/workflows/ci.yml@refs/heads/main",
                   "GITHUB_RUN_ID": "0123", "GITHUB_RUN_ATTEMPT": "1"}
        for key, changed in changes.items():
            value = fixture()
            value[0][key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(value)

    def test_missing_duplicate_truncated_or_oversized_job_lists_fail(self):
        for jobs in ({}, {"total_count": 1, "jobs": []}, {"total_count": True, "jobs": []},
                     {"total_count": 2, "jobs": fixture()[5]["jobs"] * 2},
                     {"total_count": 101, "jobs": fixture()[5]["jobs"] * 101}):
            value = fixture()
            value[5] = jobs
            with self.subTest(jobs_count=jobs.get("total_count")), self.assertRaises(ValueError):
                project(value)

    def test_other_jobs_may_exist_but_cannot_replace_this_job(self):
        value = fixture()
        other = {**value[5]["jobs"][0], "name": "ios-checks", "id": 457}
        value[5]["jobs"].append(other)
        value[5]["total_count"] = 2
        self.assertEqual(project(value)["job"]["id"], 456)

    def test_completed_replaced_or_unknown_worker_is_not_live_admission(self):
        changes = {"id": True, "run_id": 124, "run_attempt": 1, "runner_name": None,
                   "runner_id": 0, "status": "completed", "conclusion": "success",
                   "completed_at": "2026-10-14T04:00:00Z", "started_at": None}
        for key, changed in changes.items():
            value = fixture()
            value[5]["jobs"][0][key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(value)

    def test_explicit_null_liveness_fields_cannot_be_omitted(self):
        for target, key in ((4, "conclusion"), (5, "conclusion"), (5, "completed_at")):
            value = fixture()
            row = value[4] if target == 4 else value[5]["jobs"][0]
            del row[key]
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                project(value)

    def test_every_input_observation_must_be_a_document(self):
        for index in range(len(fixture())):
            for invalid in (None, [], True, "{}"):
                value = fixture()
                value[index] = invalid
                with self.subTest(index=index, invalid=invalid), self.assertRaises(ValueError):
                    project(value)

    def test_invalid_job_timestamp_does_not_start_a_new_lease(self):
        for stamp in (None, True, "", "now", "2026-10-14T03:50:19+01:00", "2026-99-14T03:50:19Z"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                m.timestamp(stamp)

    def test_metadata_secret_fields_do_not_enter_projection(self):
        value = fixture()
        for dictionary in (value[0], value[1], value[4], value[5]["jobs"][0]):
            dictionary["UNKNOWN_SECRET"] = "synthetic-not-a-real-secret"
        result = json.dumps(project(value))
        self.assertNotIn("UNKNOWN_SECRET", result)
        self.assertNotIn("synthetic-not-a-real-secret", result)

    def test_main_push_event_must_match_source_and_not_be_deleted(self):
        value = fixture()
        value[0].update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main",
                        GITHUB_WORKFLOW_REF=m.REPOSITORY + "/.github/workflows/ci.yml@refs/heads/main")
        value[1] = {"repository": {"full_name": m.REPOSITORY}, "after": SHA,
                    "ref": "refs/heads/main", "deleted": False}
        value[4].update(event="push", head_sha=SHA)
        value[5]["jobs"][0]["head_sha"] = SHA
        self.assertIsNone(project(value)["binding"]["pr"])
        value[1]["deleted"] = True
        with self.assertRaises(ValueError):
            project(value)

    def test_json_refuses_duplicate_nonfinite_empty_oversized_or_nonobject(self):
        for raw in (b"", b"[]", b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}',
                    b'{"a":-1e999}', b"\xff", b"{" * (m.MAX_RESPONSE + 1)):
            with self.subTest(prefix=raw[:10]), self.assertRaises(ValueError):
                m.decode_metadata(raw)
        self.assertEqual(m.decode_metadata(b'{"id":1}'), {"id": 1})
        self.assertEqual(m.decode_metadata(b'{"value":1.25}'), {"value": 1.25})

    def test_excessive_metadata_nesting_is_a_sanitized_refusal(self):
        raw = b'{"a":' * 2000 + b'0' + b'}' * 2000
        with self.assertRaisesRegex(ValueError, "^Invalid metadata encoding$"):
            m.decode_metadata(raw)

    def test_only_pinned_readonly_metadata_endpoints_can_be_requested(self):
        for path in ("https://other.invalid", "/repos/other/repo/actions/runs/1/attempts/1",
                     "/repos/p2pKit/P2pKit/actions/runs/1/cancel",
                     "/repos/p2pKit/P2pKit/actions/runs/1/attempts/1/jobs?per_page=1"):
            with self.subTest(path=path), patch.object(m.urllib.request, "build_opener") as opener:
                with self.assertRaises(ValueError):
                    m.github_json(path)
                opener.assert_not_called()

    def test_request_is_get_with_socket_timeout_no_redirect_and_token_not_in_result(self):
        path = "/repos/p2pKit/P2pKit/actions/runs/123/attempts/2/jobs?per_page=100"
        response = io.BytesIO(b'{"jobs":[]}')
        response.status, response.url = 200, m.API + path
        with patch.object(m.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(m.github_json(path, "synthetic-token"), {"jobs": []})
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.full_url, m.API + path)
            self.assertEqual(opener.return_value.open.call_args.kwargs, {"timeout": 30})
            self.assertEqual(request.headers["Authorization"], "Bearer synthetic-token")
        self.assertIsNone(m.NoRedirects().redirect_request(None, None, 302, "", {}, "https://other.invalid"))

    def test_network_error_does_not_echo_request_or_credentials(self):
        with patch.object(m.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = OSError("synthetic sensitive payload")
            with self.assertRaisesRegex(ValueError, "^GitHub metadata acquisition failed$"):
                m.github_json("/repos/p2pKit/P2pKit/actions/runs/123/attempts/2")

    def test_denied_http_response_is_closed_without_echoing_its_body(self):
        body = io.BytesIO(b"synthetic sensitive response")
        error = m.urllib.error.HTTPError("https://api.github.com", 403, "refused", {}, body)
        with patch.object(m.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(ValueError, "^GitHub metadata acquisition failed$"):
                m.github_json("/repos/p2pKit/P2pKit/actions/runs/123/attempts/2")
        self.assertTrue(body.closed)

    def test_malformed_http_protocol_is_sanitized(self):
        with patch.object(m.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = m.http.client.BadStatusLine("synthetic sensitive response")
            with self.assertRaisesRegex(ValueError, "^GitHub metadata acquisition failed$"):
                m.github_json("/repos/p2pKit/P2pKit/actions/runs/123/attempts/2")

    def test_input_documents_remain_unchanged(self):
        value = fixture()
        before = copy.deepcopy(value)
        project(value)
        self.assertEqual(before, value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
