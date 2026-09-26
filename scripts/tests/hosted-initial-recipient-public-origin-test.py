#!/usr/bin/env python3
"""Focused offline public-provider transport/acquisition models only.

No native owner, real HTTP/Git child, provider, credential or key operation.
The HTTP response shape follows observed public metadata; all bodies, dates,
identities and approval statements here are explicitly synthetic. Existing
fixture builders are reused, but their TestCase methods are not rerun.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import ctypes  # Complete standard-library initialization before the guard.
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_originals as A
import hosted_initial_recipient_public_origin as P

spec = importlib.util.spec_from_file_location("public_original_builders",
    Path(__file__).with_name("hosted-initial-recipient-originals-test.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
F, I, S, O = M.F, A.identity, A.stages, A.origin
BEGIN, FINAL, PROBE_BEGIN, PROBE_FINAL = P.SITES


class CountingGit(M.ModelGit):
    def __init__(self):
        super().__init__()
        self.source_calls = []

    def root_matches(self):
        self.source_calls.append(("root_matches", ()))
        return super().root_matches()

    def clean(self):
        self.source_calls.append(("clean", ()))
        return super().clean()

    def commit(self, value):
        self.source_calls.append(("commit", (value,)))
        return super().commit(value)

    def tree(self, value):
        self.source_calls.append(("tree", (value,)))
        return super().tree(value)

    def query(self, *args, **kwargs):
        self.source_calls.append(("query", args))
        return super().query(*args, **kwargs)


def fixture():
    # Local class: unittest does not discover inherited historical tests.
    class Model(M.OriginalModels):
        def connection(self, *args, **kwargs):
            connection = super().connection(*args, **kwargs)
            request, close = connection.request, connection.close

            def send(method, path, *, headers):
                request(method, path, headers=headers)
                head, body = connection.sock.raw.split(b"\r\n\r\n", 1)
                lines = head.decode("ascii").split("\r\n")
                lines[0] = "HTTP/1.1 " + self.status
                changed = []
                for line in lines[1:]:
                    name, _, value = line.partition(":")
                    key = name.lower()
                    if key == "cache-control":
                        value = self.cache_policy
                    if key in self.header_overrides:
                        value = self.header_overrides[key]
                    if value is not None:
                        changed.append(name + ": " + value.strip())
                if self.quota is not None:
                    changed.append("X-RateLimit-Remaining: " + self.quota(len(self.requests)))
                changed.extend(name + ": " + value for name, value in self.extra_headers)
                connection.sock.raw = ("\r\n".join([lines[0], *changed]) + "\r\n\r\n").encode("ascii") + \
                    self.body_transform(body)

            def finish():
                self.connection_closes += 1
                close()

            connection.request, connection.close = send, finish
            return connection

    result = Model("runTest")
    result.setUp()
    return result


class PublicOriginModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.model = fixture()
        self.addCleanup(self.model.doCleanups)
        self.reset()

    def reset(self):
        m = self.model
        m.ns, m.requests, m.retained = 1000 * O.NS, [], {}
        m.service_date = F.FIRST1
        m.choose("worker", "desktop-linux-x64")
        m.git = CountingGit()
        m.status, m.cache_policy = "200 OK", "public, max-age=60, s-maxage=60"
        m.quota = lambda ordinal: str(60 - ordinal)
        m.header_overrides, m.extra_headers = {}, []
        m.body_transform = lambda raw: raw
        m.connection_closes = 0
        m.request_error, m.link = None, None
        m.before_request, m.after_close = lambda: None, lambda: None
        self.expected = F.check1(m.declaration, F.observation1(m.declaration))

    def acquire(self, **changes):
        m = self.model
        values = dict(context=m.context, event_raw=I.encoded(m.event), git=m.git, invocation=M.INVOCATION,
            retain=m.retain, fence=m.fence, original_work_end=1045 * O.NS, now=lambda: F.DONE1,
            expected=self.expected, site=BEGIN)
        values.update(changes)
        return A._acquire_provider_public(**values)

    def refuse(self, code=".+", **changes):
        with self.assertRaisesRegex((I.AdmissionError, O.OriginError, O.wire.BudgetError), code) as caught:
            self.acquire(**changes)
        return caught.exception

    def headers(self):
        self.acquire()
        record = json.loads(self.model.retained["attempt"][0])
        _, value = O.wire.headers(base64.b64decode(record["headersBase64"], validate=True))
        return value

    def test_observed_public_header_shape_is_distinct_and_private_still_refuses(self):
        fields = self.headers()
        self.assertEqual(P.freshness(fields), F.FIRST1)
        self.assertEqual(fields["cache-control"], "public, max-age=60, s-maxage=60")
        with self.assertRaisesRegex(O.wire.BudgetError, "JOB_TIME_CACHE_POLICY"):
            O.wire.freshness(fields)
        private = {**fields, "cache-control": "private, max-age=60, s-maxage=60"}
        self.assertEqual(O.wire.freshness(private), F.FIRST1)
        with self.assertRaisesRegex(O.wire.BudgetError, "INITIAL_PUBLIC_PROVIDER_CACHE_POLICY"):
            P.freshness(private)

    def test_public_directive_order_and_normal_whitespace_keep_exact_set(self):
        for value in ("public,max-age=60,s-maxage=60", "s-maxage=60, public, max-age=60",
                      " PUBLIC , max-age=60 , s-maxage=60 "):
            with self.subTest(value=value):
                self.reset()
                self.model.cache_policy = value
                self.assertEqual(self.acquire()[0], self.expected)

    def test_extra_missing_duplicate_or_non60_public_cache_directives_refuse(self):
        cases = ("", "public", "public,max-age=60", "public,max-age=60,s-maxage=60,no-cache",
            "private,max-age=60,s-maxage=60", "public,max-age=60,s-maxage=60,private",
            "public,max-age=60,s-maxage=60,public", "public,max-age=59,s-maxage=60",
            "public,max-age=60,s-maxage=61", "public,max-age=060,s-maxage=60",
            "public=1,max-age=60,s-maxage=60", "public,max-age=60,s-maxage=60,")
        for value in cases:
            with self.subTest(value=value):
                self.reset()
                self.model.cache_policy = value
                self.refuse("CACHE_POLICY")
                self.assertEqual(len(self.model.requests), 1)

    def test_original_age_intermediary_redirect_range_and_retry_refusals_remain(self):
        for name, value in (("Age", "1"), ("Age", "00"), ("Via", "proxy"), ("Warning", "110 stale"),
                ("Location", "https://example.invalid"), ("Content-Range", "bytes 0-1/2"),
                ("Retry-After", "1"), ("X-Cache", "HIT"), ("X-Cache", "REVALIDATED")):
            with self.subTest(name=name, value=value):
                self.reset()
                self.model.extra_headers = [(name, value)]
                self.refuse("STALE_OR_INTERMEDIARY")
                self.assertEqual(len(self.model.requests), 1)

    def test_type_encoding_version_request_id_date_and_duplicate_header_refuse(self):
        for name, value in (("content-type", "text/plain"), ("content-type", None),
                ("content-encoding", "gzip"), ("x-github-api-version-selected", "old"),
                ("x-github-request-id", "bad"), ("date", "not a date")):
            with self.subTest(name=name):
                self.reset()
                if name == "content-encoding":
                    self.model.extra_headers = [("Content-Encoding", value)]
                else:
                    self.model.header_overrides = {name: value}
                self.refuse()
        self.reset()
        self.model.extra_headers = [("Cache-Control", "public,max-age=60,s-maxage=60")]
        self.refuse("HEADER_DUPLICATE")

    def test_non200_and_conditional_response_do_not_retry_or_fall_back(self):
        for status in ("301 Moved", "304 Not Modified", "401 Unauthorized", "403 Forbidden",
                       "404 Not Found", "429 Too Many Requests", "500 Failed"):
            with self.subTest(status=status):
                self.reset()
                self.model.status = status
                self.refuse("SERVICE_STATUS")
                self.assertEqual(len(self.model.requests), 1)
                self.assertEqual(self.model.connection_closes, 1)
                self.assertTrue(self.model.retained["attempt"][1])

    def test_public_and_private_envelope_readers_refuse_cross_scope_without_relabelling(self):
        self.acquire()
        m = self.model
        raw = m.retained["attempt"][0]
        _, body, _ = O.initial_provider_response_bytes(raw, m.paths["attempt"], M.INVOCATION, m.clock)
        self.assertEqual(body, I.encoded(m.bodies["attempt"]))
        with self.assertRaisesRegex(O.OriginError, "BOOTSTRAP_SERVICE_RESPONSE"):
            O.response_bytes(raw, m.paths["attempt"], M.INVOCATION, m.clock)
        public = json.loads(raw)
        private = {**public, "scope": O.RESPONSE_SCOPE}
        with self.assertRaisesRegex(O.OriginError, "BOOTSTRAP_SERVICE_RESPONSE"):
            O.initial_provider_response_bytes(I.encoded(private), m.paths["attempt"], M.INVOCATION, m.clock)
        with self.assertRaisesRegex(O.wire.BudgetError, "JOB_TIME_CACHE_POLICY"):
            O.response_bytes(I.encoded(private), m.paths["attempt"], M.INVOCATION, m.clock)

    def test_original_response_path_clock_scope_status_completeness_and_close_are_required(self):
        self.acquire()
        m = self.model
        original = json.loads(m.retained["attempt"][0])
        for field, value in (("path", "/wrong"), ("clock", {}), ("scope", "unknown"),
                ("status", 201), ("complete", False), ("retirement", "UNKNOWN"), ("error", "failed")):
            with self.subTest(field=field):
                raw = I.encoded({**original, field: value})
                with self.assertRaises(O.OriginError):
                    O.initial_provider_response_bytes(raw, m.paths["attempt"], M.INVOCATION, m.clock)

    def test_unknown_shared_transport_selector_refuses_before_parser_or_request(self):
        m = self.model
        for scope in (None, True, "", "PUBLIC_BOOTSTRAP_SERVICE_RESPONSE_V1"):
            with self.subTest(scope=scope):
                with self.assertRaisesRegex(O.OriginError, "TRANSPORT_SCOPE"):
                    O._request_transport(m.paths["attempt"], None, M.INVOCATION, m.fence, 1045 * O.NS, scope)
                with self.assertRaisesRegex(O.OriginError, "TRANSPORT_SCOPE"):
                    O._response_bytes(b"", m.paths["attempt"], M.INVOCATION, m.clock, scope)
        self.assertEqual(m.requests, [])

    def test_eight_fresh_fixed_gets_and_two_complete_source_query_sets_preserve_bytes(self):
        result, originals = self.acquire()
        m = self.model
        self.assertIs(type(result), S.BootstrapMatch)
        self.assertEqual(result, self.expected)
        self.assertNotIsInstance(result, I.Admission)
        self.assertEqual([path for _method, path, _headers in m.requests], list(m.paths.values()))
        self.assertEqual(len(m.git.source_calls), 24)
        self.assertEqual(m.git.source_calls[:12], m.git.source_calls[12:])
        self.assertEqual([name for name, _args in m.git.source_calls[:12]],
            ["root_matches", "clean", "commit", "tree", "query", "commit", "tree",
             "query", "query", "query", "query", "query"])
        self.assertEqual(dict(originals), {name: raw for name, (raw, _failed) in m.retained.items()})
        for label, path in m.paths.items():
            raw, failed = m.retained[label]
            envelope, body, _ = O.initial_provider_response_bytes(raw, path, M.INVOCATION, m.clock)
            self.assertFalse(failed)
            self.assertEqual(envelope["scope"], P.RESPONSE_SCOPE)
            self.assertEqual(body, I.encoded(m.bodies[label]))
        self.assertEqual(m.connection_closes, 8)

    def test_public_requests_have_exact_noncredential_headers_and_no_conditional_fetch(self):
        self.acquire()
        expected = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "P2pKit-cache-bootstrap-originals", "Cache-Control": "no-cache, max-age=0",
            "Pragma": "no-cache", "Accept-Encoding": "identity", "Connection": "close"}
        for method, _path, headers in self.model.requests:
            self.assertEqual(method, "GET")
            self.assertEqual(headers, expected)
        self.assertTrue(all(M.TOKEN.encode() not in raw for raw, _failed in self.model.retained.values()))

    def test_all_four_fixed_sites_keep_exact_begin_and_final_quota_needs(self):
        for site in P.SITES:
            with self.subTest(site=site):
                self.reset()
                total = 16 if site.endswith("/begin") else 8
                self.model.quota = lambda ordinal, total=total: str(total - ordinal)
                self.assertEqual(self.acquire(site=site)[0], self.expected)
                self.assertEqual(len(self.model.requests), 8)

    def test_known_insufficient_quota_stops_after_original_response_without_sleep_retry(self):
        for site, remaining in ((BEGIN, "14"), (FINAL, "6"), (PROBE_BEGIN, "14"), (PROBE_FINAL, "6")):
            with self.subTest(site=site):
                self.reset()
                self.model.quota = lambda _ordinal, remaining=remaining: remaining
                self.refuse("INSUFFICIENT_QUOTA", site=site)
                self.assertEqual(len(self.model.requests), 1)
                self.assertEqual(self.model.connection_closes, 1)
                self.assertFalse(self.model.retained["attempt"][1])  # HTTP success is not acquisition success.

    def test_later_shared_quota_loss_is_failure_not_prior_quota_reservation(self):
        self.model.quota = lambda ordinal: "59" if ordinal == 1 else "0"
        self.refuse("INSUFFICIENT_QUOTA")
        self.assertEqual(len(self.model.requests), 2)
        self.assertEqual(self.model.connection_closes, 2)

    def test_missing_quota_is_not_invented_and_malformed_present_metadata_refuses(self):
        self.model.quota = None
        self.assertEqual(self.acquire()[0], self.expected)
        self.assertIsNone(P.remaining_requests({}, 15))
        for value in ("", "-1", "00", "1.5", "+15", "60 extra", "9" * 21):
            with self.subTest(value=value):
                self.reset()
                self.model.quota = lambda _ordinal, value=value: value
                self.refuse("QUOTA_METADATA")
                self.assertEqual(len(self.model.requests), 1)

    def test_arbitrary_endpoint_queries_origins_refs_and_ids_refuse_before_transport(self):
        base = A.API
        cases = ("https://api.github.com" + self.model.paths["attempt"], "//example.invalid/x",
            base + "/actions/runs/0/approvals", base + "/actions/runs/01/approvals",
            base + "/actions/runs/300/attempts/0", base + "/actions/runs/300/attempts/1/jobs?per_page=100&page=2",
            base + "/issues/comments/8001?fresh=1", base + "/issues/437/comments",
            base + "/git/ref/heads/unreviewed", base + "/environments/maven-central")
        for path in cases:
            with self.subTest(path=path):
                with self.assertRaisesRegex(O.wire.BudgetError, "FIXED_ENDPOINT"):
                    O._request_initial_provider_public(path, M.INVOCATION, self.model.fence, 1045 * O.NS)
        self.assertEqual(self.model.requests, [])

    def test_each_actual_api_or_runtime_credential_name_refuses_before_source_or_http(self):
        for name in P.CREDENTIAL_NAMES:
            with self.subTest(name=name):
                with patch.dict(os.environ, {name: "SYNTHETIC_NOT_A_CREDENTIAL"}):
                    self.refuse("CREDENTIAL_BOUNDARY")
        self.assertEqual(self.model.requests, [])
        self.assertEqual(self.model.git.source_calls, [])

    def test_public_worker_only_exact_site_and_expected_match_are_required(self):
        for site in (None, True, "", "provider-save/native-prepare", "ordinary", "provider-save/native-prepare/final/"):
            with self.subTest(site=site):
                self.refuse("FIXED_SITE", site=site)
        for expected in (None, self.expected.record, S.OrdinaryMatch(self.expected.record)):
            with self.subTest(expected=type(expected).__name__):
                self.refuse("PUBLIC_PROVIDER_WORKER", expected=expected)
        self.refuse("PUBLIC_PROVIDER_WORKER", context={**self.model.context, "kind": "gate"})
        self.assertEqual(self.model.requests, [])
        self.assertEqual(self.model.git.source_calls, [])

    def test_public_entry_has_no_token_kind_network_or_originals_override(self):
        names = tuple(inspect.signature(A.acquire_provider_public).parameters)
        self.assertEqual(names, ("root", "site", "query_runner", "invocation", "retain", "fence",
            "original_work_end", "first_use_at", "expected"))
        self.assertEqual(tuple(inspect.signature(A.acquire_bootstrap).parameters),
            ("root", "kind", "query_runner", "invocation", "token", "retain", "fence",
             "original_work_end", "first_use_at", "expected"))
        self.assertEqual(tuple(inspect.signature(O._request).parameters),
            ("path", "token", "invocation", "fence", "end"))
        self.assertEqual(tuple(inspect.signature(O.response_bytes).parameters), ("raw", "path", "invocation", "clock"))

    def test_public_entry_reads_actual_process_context_and_delegates_only_closed_git(self):
        # Synthetic process environment and explicitly modeled input boundaries:
        # this exercises the production entry, not a hosted-context claim.
        m = self.model
        event_path, query_runner = ROOT / "SYNTHETIC-event.json", object()
        event_raw = I.encoded(m.event)
        env = {**m.env, "GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": str(event_path)}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(I, "read_regular", return_value=event_raw) as read, \
                patch.object(I, "GitView", return_value=m.git) as git, \
                patch.object(A.time, "time", return_value=F.DONE1):
            result, _ = A.acquire_provider_public(ROOT, site=BEGIN, query_runner=query_runner,
                invocation=M.INVOCATION, retain=m.retain, fence=m.fence, original_work_end=1045 * O.NS,
                first_use_at=F.FIRST1, expected=self.expected)
        read.assert_called_once_with(event_path, I.EVENT_LIMIT)
        git.assert_called_once_with(ROOT, env, query_runner)
        self.assertEqual(result, self.expected)
        self.assertEqual(len(m.git.source_calls), 24)
        self.assertEqual(len(m.requests), 8)

    def test_public_entry_does_not_accept_supplied_or_unhosted_process_labels(self):
        m = self.model
        env = {**m.env, "GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": str(ROOT / "SYNTHETIC-event.json"),
            "RUNNER_ENVIRONMENT": "self-hosted"}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(I, "read_regular", return_value=I.encoded(m.event)), \
                patch.object(I, "GitView") as git:
            with self.assertRaisesRegex(I.AdmissionError, "HOSTED_CONTEXT"):
                A.acquire_provider_public(ROOT, site=BEGIN, query_runner=object(),
                    invocation=M.INVOCATION, retain=m.retain, fence=m.fence, original_work_end=1045 * O.NS,
                    first_use_at=F.FIRST1, expected=self.expected)
        git.assert_not_called()
        self.assertEqual(m.requests, [])

    def test_viewer_relative_association_does_not_rewrite_original_comment_or_owner_match(self):
        self.model.bodies["comment"]["author_association"] = "COLLABORATOR"
        result, _ = self.acquire()
        self.assertEqual(result, self.expected)
        _, raw, _ = O.initial_provider_response_bytes(self.model.retained["comment"][0],
            self.model.paths["comment"], M.INVOCATION, self.model.clock)
        self.assertEqual(raw, I.encoded(self.model.bodies["comment"]))
        self.assertEqual(json.loads(raw)["author_association"], "COLLABORATOR")

    def test_owner_comment_body_edited_timestamps_and_app_authorship_remain_mandatory(self):
        for mutate in (lambda value: value["user"].update(id=1),
                lambda value: value.update(body=value["body"] + " "),
                lambda value: value.update(updated_at=F.utc(F.START)),
                lambda value: value.update(performed_via_github_app={})):
            self.reset()
            mutate(self.model.bodies["comment"])
            self.refuse()
            self.assertEqual(len(self.model.requests), 4)

    def test_current_job_gate_environment_policy_and_remote_refs_remain_mandatory(self):
        mutations = (
            lambda b: b["attempt"].update(status="completed"),
            lambda b: b["jobs"]["jobs"][0].update(runner_name="different"),
            lambda b: b["jobs"]["jobs"][1].update(conclusion="failure"),
            lambda b: b["approvals"][0].update(state="rejected"),
            lambda b: b["environment"].update(can_admins_bypass=True),
            lambda b: b["branches"].update(total_count=3),
            lambda b: b["main"]["object"].update(sha=F.H2),
            lambda b: b["reviewed_ref"]["object"].update(sha=F.H2))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                self.reset()
                mutate(self.model.bodies)
                self.refuse()
                self.assertLessEqual(len(self.model.requests), 8)

    def test_incomplete_paginated_response_and_duplicate_approval_do_not_select_subset(self):
        self.model.link = '<https://api.github.com/next>; rel="next"'
        self.refuse("INCOMPLETE_RESPONSE")
        self.assertEqual(len(self.model.requests), 1)
        self.reset()
        self.model.bodies["approvals"] *= 2
        self.refuse("MISSING_OR_AMBIGUOUS_CHALLENGE")
        self.assertEqual(len(self.model.requests), 3)

    def test_source_policy_absence_and_both_source_sets_remain_required(self):
        self.model.git.base_entry = F.ENTRY
        self.refuse("BASE_POLICY_NOT_ABSENT")
        self.assertEqual(self.model.requests, [])
        self.reset()
        self.model.before_request = lambda: setattr(self.model.git, "clean_value", False) \
            if len(self.model.requests) == 8 else None
        self.refuse("SOURCE")
        self.assertEqual(len(self.model.requests), 8)

    def test_expired_statement_and_changed_expected_match_never_become_authority(self):
        self.refuse("VALIDITY", now=lambda: self.model.declaration["expiresAt"])
        self.reset()
        changed = json.loads(self.expected.record)
        changed["firstUseAt"] += 1
        self.refuse("CHANGED_BEFORE_RECHECK", expected=S.BootstrapMatch(I.encoded(changed)))

    def test_original_parent_end_is_not_renewed_for_public_transport(self):
        self.model.ns = 1045 * O.NS
        self.refuse("FENCE_EXPIRED")
        self.assertEqual(self.model.requests, [])
        self.reset()
        self.model.after_close = lambda: setattr(self.model, "ns", 1045 * O.NS)
        self.refuse("FENCE_EXPIRED")
        self.assertEqual(len(self.model.requests), 1)
        self.assertTrue(self.model.retained["attempt"][1])

    def test_service_date_drift_cannot_reset_the_whole_acquisition_allowance(self):
        self.model.before_request = lambda: setattr(self.model, "service_date", F.FIRST1 +
            30 * (len(self.model.requests) - 1))
        self.refuse("SERVICE_DATE_DRIFT")
        self.assertLess(len(self.model.requests), 8)

    def test_truncated_body_preserves_failed_original_and_closes_without_retry(self):
        self.model.body_transform = lambda raw: raw[:-1]
        self.refuse()
        self.assertEqual(len(self.model.requests), 1)
        self.assertEqual(self.model.connection_closes, 1)
        self.assertTrue(self.model.retained["attempt"][1])

    def test_connection_close_failure_keeps_unknown_retirement_and_fails_acquisition(self):
        def fail_close():
            raise RuntimeError("SYNTHETIC_CLOSE_FAILURE")
        self.model.after_close = fail_close
        self.refuse("SERVICE_CLOSE_FAILED")
        record = json.loads(self.model.retained["attempt"][0])
        self.assertEqual(record["scope"], P.RESPONSE_SCOPE)
        self.assertEqual(record["retirement"], "UNKNOWN")
        self.assertFalse(record["complete"])
        self.assertEqual(self.model.connection_closes, 1)
        self.assertEqual(len(self.model.requests), 1)

    def test_reader_eof_close_failure_is_not_retried_or_accepted_as_connection_close(self):
        original = O.wire._Reader.close
        calls = []
        def fail_after_close(reader):
            calls.append(reader)
            original(reader)
            raise O.OriginError("SYNTHETIC_READER_CLOSE")
        with patch.object(O.wire._Reader, "close", side_effect=fail_after_close, autospec=True):
            self.refuse()
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(self.model.retained["attempt"][0])["retirement"], "UNKNOWN")
        self.assertEqual(self.model.connection_closes, 1)

    def test_primary_transport_failure_survives_secondary_retention_failure(self):
        primary, secondary = O.OriginError("SYNTHETIC_HTTP_PRIMARY"), RuntimeError("SYNTHETIC_RETENTION")
        self.model.request_error = primary
        def retain(label, raw, *, failed):
            self.model.retain(label, raw, failed=failed)
            if label == "attempt":
                raise secondary
        failure = self.refuse("SYNTHETIC_HTTP_PRIMARY", retain=retain)
        self.assertIs(failure, primary)
        self.assertIs(failure.__cause__, secondary)
        self.assertEqual(len(self.model.requests), 1)

    def test_legacy_private_acquisition_keeps_bearer_private_scope_and_original_match(self):
        m = self.model
        m.cache_policy = "private, max-age=60, s-maxage=60"
        result, originals = A._acquire_bootstrap(m.context, I.encoded(m.event), m.git, M.INVOCATION, M.TOKEN,
            m.retain, m.fence, 1045 * O.NS, lambda: F.DONE1, self.expected)
        self.assertEqual(result, self.expected)
        self.assertEqual(len(m.requests), 8)
        for method, _path, headers in m.requests:
            self.assertEqual(method, "GET")
            self.assertEqual(headers["Authorization"], "Bearer " + M.TOKEN)
        for label in m.paths:
            self.assertEqual(json.loads(dict(originals)[label])["scope"], O.RESPONSE_SCOPE)


if __name__ == "__main__":
    unittest.main()
