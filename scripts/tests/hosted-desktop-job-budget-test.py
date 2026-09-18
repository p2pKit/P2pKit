#!/usr/bin/env python3
"""Offline Desktop clock/API/envelope models, never genuine hosted acceptance.

No native clock, HTTP/TLS/socket, process owner, build or workflow is executed.
All identities and service replies below are explicitly synthetic model data.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
from dataclasses import replace
import importlib.util
import math
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_full_job_budget as J
import hosted_job_clock as C
import hosted_test_identity as I

SPEC = importlib.util.spec_from_file_location("full_budget_models", Path(__file__).with_name("hosted-full-job-budget-test.py"))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)
HOSTS = {
    "linux-x64": ("Linux", "X64", "ubuntu-latest"),
    "windows-x64": ("Windows", "X64", "windows-latest"),
    "macos-arm64": ("macOS", "ARM64", "macos-15"),
    "macos-x64": ("macOS", "X64", "macos-15"),
}


def clock(role):
    return C.ClockIdentity(role, C.DOMAINS[role], 10_000_000 if role == "windows-x64" else C.NS)


def admission(role="windows-x64", event="push"):
    original = F.model_admission(event)
    value = J.parse(original.record)
    host, arch, _ = HOSTS[role]
    value.update(profile="desktop", suites=["cli"])
    value["github"].update(workflow=I.PROFILES["desktop"][0], job="verify", runnerOS=host, runnerArch=arch)
    return replace(original, record=I.encoded(value))


def originals(admitted, bound_clock, *, elapsed=120, raw_ns=10000 * J.NS):
    values = F.model_responses(admitted, elapsed=elapsed, raw_ns=raw_ns)
    selector = HOSTS[bound_clock.role][2]
    values["jobs"] = F.replace_body(values["jobs"],
        lambda body: body["jobs"][0].update(name=selector, labels=[selector]))
    for name, raw in values.items():
        value = J.parse(raw)
        value.update(schema=2, profile="desktop", clock=J.clock_value(bound_clock), clockDomain=bound_clock.domain)
        values[name] = J.encoded(value)
    return values


class DesktopBudgetModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, name in ((J, "shared_raw_ns"), (C, "observe"), (C.processes, "host_role"),
                             (J.http.client, "HTTPSConnection"), (J.ssl, "create_default_context"),
                             (socket, "socket"), (socket, "create_connection")):
            self.stack.enter_context(patch.object(target, name, side_effect=AssertionError("NO_NATIVE_OR_NETWORK")))

    def budget(self, role="windows-x64", *, elapsed=120):
        admitted, exact = admission(role), clock(role)
        return J.derive(admitted, originals(admitted, exact, elapsed=elapsed), F.provenance(), clock=exact)

    def test_three_service_matrix_selectors_bind_actual_job_and_original_time(self):
        for role in HOSTS:
            with self.subTest(role=role):
                budget = self.budget(role)
                self.assertEqual(budget.profile, "desktop")
                self.assertEqual(budget.clock, clock(role))
                self.assertEqual(budget.value["github"]["job"], "verify")
                self.assertEqual(budget.value["numericJobId"], 456)
                self.assertEqual(budget.value["runner"]["labels"], [HOSTS[role][2]])
                self.assertEqual(budget.fence("delivery"), (10000 + 1800 - 120 - 66) * J.NS)
                self.assertEqual(budget.fence("controller-return"), budget.fence("delivery") - 600 * J.NS)
                self.assertEqual(budget.fence("productive"), budget.fence("controller-return") - 270 * J.NS)
                self.assertEqual(budget.fence("product-return"), budget.fence("productive") + 225 * J.NS)
                self.assertEqual(budget.fence("product-final"), budget.fence("controller-return"))

    def test_shared_caps_do_not_pretend_all_operation_maxima_are_reserved(self):
        budget = self.budget()
        policy = budget.value["policy"]
        self.assertEqual((policy["jobSeconds"], policy["controllerSeconds"], policy["productSeconds"],
                          policy["outerSeconds"]), (1800, 1500, 600, 825))
        self.assertEqual((policy["deliverySeconds"], policy["sealSeconds"], policy["eachUploadSeconds"],
                          policy["packageSeconds"], policy["eachTransitionSeconds"]), (600, 120, 180, 120, 30))
        self.assertIn("NOT_MAXIMUM_DURATION_FIT_OR_DELIVERY_GUARANTEES", policy["scope"])
        for stage in J.DESKTOP_CONTROLLER_STAGES:
            self.assertEqual(budget.fence(stage), budget.fence("controller-return"))
        for stage in J.DESKTOP_DELIVERY_STAGES:
            self.assertEqual(budget.fence(stage), budget.fence("delivery"))
        self.assertGreater(policy["sealSeconds"] + 2 * policy["eachUploadSeconds"] + policy["packageSeconds"] +
                           2 * policy["eachTransitionSeconds"], policy["deliverySeconds"])
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_CLOSED_STAGE"):
            budget.fence("simulator-shutdown")

    def test_desktop_cannot_use_the_legacy_full_clock_or_schema(self):
        admitted, exact = admission(), clock("windows-x64")
        replies = originals(admitted, exact)
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_DESKTOP_CLOCK_REQUIRED"):
            J.derive(admitted, replies, F.provenance())
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_DESKTOP_CLOCK_REQUIRED"):
            J.acquire(admitted, "e" * 32, F.TOKEN, lambda *args: self.fail("NO_RETENTION"))
        value = J.parse(replies["jobs"])
        value.update(schema=1)
        value.pop("clock")
        value.pop("profile")
        replies["jobs"] = J.encoded(value)
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_RESPONSE_BINDING"):
            J.derive(admitted, replies, F.provenance(), clock=exact)

    def test_service_name_is_selector_not_github_job_or_a_fictional_matrix_name(self):
        admitted, exact = admission("linux-x64"), clock("linux-x64")
        for name in ("verify", "verify (ubuntu-latest)", "complete-gate", "windows-latest"):
            replies = originals(admitted, exact)
            replies["jobs"] = F.replace_body(replies["jobs"], lambda body: body["jobs"][0].update(name=name))
            with self.subTest(name=name), self.assertRaisesRegex(J.BudgetError, "JOB_TIME_EXACT_JOB_REQUIRED"):
                J.derive(admitted, replies, F.provenance(), clock=exact)

    def test_admitted_job_workflow_event_and_native_host_cannot_change(self):
        original = admission()
        for changes in ({"job": "windows-latest"}, {"job": "complete-gate"},
                        {"workflow": I.PROFILES["full"][0]}, {"event": "schedule"},
                        {"runnerOS": "Windows", "runnerArch": "ARM64"}, {"workflowSha": "0" * 40}):
            value = J.parse(original.record)
            value["github"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(J.BudgetError):
                J.admitted_identity(replace(original, record=I.encoded(value)))
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_CLOCK_HOST_CHANGED"):
            J.derive(original, originals(original, clock("windows-x64")), F.provenance(), clock=clock("linux-x64"))

    def test_attempt_runner_numeric_id_and_complete_page_remain_exact(self):
        admitted, exact = admission(), clock("windows-x64")
        changes = {"runner_name": "other-runner", "runner_id": 0, "id": True, "run_attempt": 2,
                   "labels": ["windows-latest", "self-hosted"], "run_id": 124, "head_sha": "f" * 40}
        for key, value in changes.items():
            replies = originals(admitted, exact)
            replies["jobs"] = F.replace_body(replies["jobs"], lambda body: body["jobs"][0].update({key: value}))
            with self.subTest(key=key), self.assertRaises(J.BudgetError):
                J.derive(admitted, replies, F.provenance(), clock=exact)
        replies = originals(admitted, exact)
        replies["jobs"] = F.replace_body(replies["jobs"], lambda body: body.update(total_count=2))
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_COMPLETE_PAGE_REQUIRED"):
            J.derive(admitted, replies, F.provenance(), clock=exact)

    def test_pull_request_api_head_binds_admitted_original_not_merge_source(self):
        admitted, exact = admission(event="pull_request"), clock("windows-x64")
        replies = originals(admitted, exact)
        self.assertEqual(J.derive(admitted, replies, F.provenance(), clock=exact).value["source"]["commit"], "a" * 40)
        replies["jobs"] = F.replace_body(replies["jobs"], lambda body: body["jobs"][0].update(head_sha="a" * 40))
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_JOB_IDENTITY"):
            J.derive(admitted, replies, F.provenance(), clock=exact)

    def test_response_profile_role_domain_frequency_and_invocation_are_not_replayable(self):
        admitted, exact = admission(), clock("windows-x64")
        mutations = [lambda value: value.update(profile="full"),
                     lambda value: value.update(clockDomain=C.DARWIN_DOMAIN),
                     lambda value: value.update(clock=J.clock_value(clock("linux-x64"))),
                     lambda value: value["clock"].update(ticksPerSecond=10_000_001),
                     lambda value: value["clock"].update(ticksPerSecond=True),
                     lambda value: value.update(invocation="0" * 32),
                     lambda value: value.update(startedRawNs=9999 * J.NS, finishedRawNs=9999 * J.NS)]
        for index, mutate in enumerate(mutations):
            replies = originals(admitted, exact)
            value = J.parse(replies["jobs"])
            mutate(value)
            replies["jobs"] = J.encoded(value)
            with self.subTest(index=index), self.assertRaises((J.BudgetError, C.ClockError)):
                J.derive(admitted, replies, F.provenance(), clock=exact)

    def test_original_setup_time_cannot_be_reset_by_a_new_controller_or_local_epoch(self):
        budget = self.budget(elapsed=1000)
        with patch.object(C, "observe", return_value=C.Reading(budget.clock, 10000 * J.NS)), \
                patch.object(J.time, "monotonic", return_value=100.):
            with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_FENCE_EXPIRED"):
                budget.deadline("productive", 600)
        admitted, exact = admission(), clock("windows-x64")
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_ALREADY_EXPIRED"):
            J.derive(admitted, originals(admitted, exact, elapsed=1750), F.provenance(), clock=exact)

    def test_delivery_checks_share_one_end_and_never_renew600s(self):
        budget = self.budget()
        unchanged = budget.record
        end = budget.fence("delivery")
        tracker = J.BudgetClock(budget)
        for stage, elapsed in (("seal", 50), ("upload", 40), ("package", 30), ("samples", 20), ("delivery", 10)):
            with self.subTest(stage=stage), patch.object(C, "observe", return_value=C.Reading(budget.clock, end - elapsed * J.NS)), \
                    patch.object(J.time, "monotonic", return_value=100.):
                deadline = tracker.deadline(stage, 180)
                self.assertLess(deadline, 100 + elapsed)
                self.assertGreater(deadline, 100 + elapsed - 0.000001)
        with patch.object(C, "observe", return_value=C.Reading(budget.clock, end)):
            with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_FENCE_EXPIRED"):
                tracker.check("delivery")
        self.assertEqual(budget.record, unchanged)

    def test_return_clock_change_and_backwards_reading_refuse_without_fallback(self):
        budget = self.budget()
        for reading in (C.Reading(clock("linux-x64"), 10001 * J.NS),
                        C.Reading(replace(budget.clock, ticks_per_second=1), 10001 * J.NS),
                        C.Reading(budget.clock, 9999 * J.NS)):
            with self.subTest(reading=reading), patch.object(C, "observe", return_value=reading), self.assertRaises(C.ClockError):
                budget.check("productive")
        tracker = J.BudgetClock(budget)
        with patch.object(C, "observe", side_effect=[C.Reading(budget.clock, 10002 * J.NS),
                                                   C.Reading(budget.clock, 10001 * J.NS)]):
            tracker.check("productive")
            with self.assertRaisesRegex(C.ClockError, "JOB_CLOCK_BACKWARDS"):
                tracker.check("productive")

    def test_serialized_fence_policy_or_clock_tamper_is_rejected(self):
        budget = self.budget()
        mutations = [lambda value: value["fencesRawNs"].update(delivery=budget.fence("delivery") + J.NS),
                     lambda value: value["fencesRawNs"].update(productive=float(budget.fence("productive"))),
                     lambda value: value["policy"].update(deliverySeconds=601),
                     lambda value: value["policy"].update(deliverySeconds=600.0),
                     lambda value: value["clock"].update(ticksPerSecond=10_000_001),
                     lambda value: value.update(profile="full"), lambda value: value.update(schema=1)]
        for index, mutate in enumerate(mutations):
            value = budget.value
            mutate(value)
            with self.subTest(index=index), self.assertRaises((J.BudgetError, C.ClockError)):
                J.Budget(J.encoded(value)).fence("delivery")

    def test_explicit_clock_local_conversion_rejects_invalid_local_sample_and_limits(self):
        budget = self.budget()
        with patch.object(C, "observe", return_value=C.Reading(budget.clock, 10000 * J.NS)):
            for local in (math.nan, math.inf, -1., True):
                with self.subTest(local=local), patch.object(J.time, "monotonic", return_value=local), \
                        self.assertRaisesRegex(J.BudgetError, "JOB_TIME_LOCAL_CLOCK"):
                    budget.deadline("productive", 600)
            for seconds in (math.nan, math.inf, 0, -1, True):
                with self.subTest(seconds=seconds), self.assertRaisesRegex(J.BudgetError, "JOB_TIME_OPERATION_MAXIMUM"):
                    budget.deadline("productive", seconds)

    def test_current_reading_retains_first_native_value_and_identity(self):
        for role in HOSTS:
            exact = clock(role)
            with self.subTest(role=role), patch.object(C, "observe", return_value=C.Reading(exact, 123)) as observed:
                self.assertEqual(J.current_reading("desktop"), C.Reading(exact, 123))
                observed.assert_called_once_with()
        with patch.object(C, "observe", return_value=C.Reading(clock("linux-x64"), 123)):
            with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_FULL_CLOCK_REQUIRED"):
                J.current_reading("full")

    def test_full_explicit_identity_keeps_every_original_fence_and2430reserve(self):
        admitted = F.model_admission()
        legacy_originals = F.model_responses(admitted)
        legacy = J.derive(admitted, legacy_originals, F.provenance())
        exact = clock("macos-arm64")
        bound_originals = {}
        for name, raw in legacy_originals.items():
            value = J.parse(raw)
            value.update(schema=2, profile="full", clock=J.clock_value(exact))
            bound_originals[name] = J.encoded(value)
        bound = J.derive(admitted, bound_originals, F.provenance(), clock=exact)
        self.assertEqual(bound.profile, "full")
        self.assertIsNone(legacy.clock)
        self.assertEqual(legacy.value["fencesRawNs"], bound.value["fencesRawNs"])
        self.assertEqual(bound.value["policy"]["reserveSeconds"], 2430)
        self.assertEqual(bound.clock.domain, J.RAW_CLOCK_DOMAIN)


class DesktopHttpModels(unittest.TestCase):
    connection = F.HttpModels.connection

    def setUp(self):
        F.HttpModels.setUp(self)
        self.stack.enter_context(patch.object(J, "shared_raw_ns", side_effect=AssertionError("NO_DARWIN_READ")))
        self.stack.enter_context(patch.object(C.processes, "host_role", side_effect=AssertionError("NO_NATIVE_HOST")))
        self.exact = clock("windows-x64")
        self.stack.enter_context(patch.object(C, "observe", side_effect=lambda: C.Reading(self.exact, self.now)))

    def supply(self, admitted):
        modeled = originals(admitted, self.exact)
        for name in ("attempt", "jobs"):
            value = J.parse(modeled[name])
            self.responses.append(base64.b64decode(value["headersBase64"]) + base64.b64decode(value["bodyBase64"]))

    def test_two_http_gets_use_exact_windows_clock_in_all_originals(self):
        admitted = admission()
        self.supply(admitted)
        retained = {}
        result, completed = J.acquire(admitted, "e" * 32, F.TOKEN, lambda name, raw: retained.update({name: raw}), clock=self.exact)
        self.assertEqual(result, retained)
        self.assertEqual(completed, self.now)
        self.assertEqual(len(self.requests), 2)
        for raw in retained.values():
            self.assertEqual(J.parse(raw)["clock"], J.clock_value(self.exact))
            self.assertEqual(J.parse(raw)["profile"], "desktop")
            self.assertNotIn(F.TOKEN.encode(), raw)
        self.assertTrue(all(value.closed and value.original_sock.stream.closed for value in self.connections))
        J.derive(admitted, result, F.provenance(), clock=self.exact)

    def test_acquisition_entry_uses_the_callers_original_highwater_before_http(self):
        for profile in ("full", "desktop"):
            admitted = F.model_admission() if profile == "full" else admission()
            options = {} if profile == "full" else {"clock": self.exact}
            error = J.BudgetError if profile == "full" else C.ClockError
            with self.subTest(profile=profile), patch.object(J, "shared_raw_ns", return_value=self.now), \
                    self.assertRaises(error):
                J.acquire(admitted, "e" * 32, F.TOKEN, lambda *_: self.fail("NO_RETENTION"),
                          minimum=self.now + 1, **options)
            self.assertEqual(self.requests, [])
            self.assertEqual(self.connections, [])

    def test_acquisition_returns_the_post_retention_highwater_to_its_caller(self):
        admitted = admission()
        self.supply(admitted)
        retained = {}
        def retain(name, raw):
            retained[name] = raw
            if name == "jobs":
                self.now += J.NS
        result, completed = J.acquire(admitted, "e" * 32, F.TOKEN, retain,
                                      clock=self.exact, minimum=self.now)
        self.assertEqual(result, retained)
        self.assertEqual(completed, self.now)
        self.assertGreater(completed, max(J.parse(raw)["finishedRawNs"] for raw in retained.values()))
        self.assertTrue(all(value.closed and value.original_sock.stream.closed for value in self.connections))

    def test_post_retention_check_keeps_original_acquisition_45_second_limit(self):
        self.assertEqual(J.ACQUIRE_SECONDS, 45)
        admitted = admission()
        self.supply(admitted)
        retained = {}
        def retain(name, raw):
            retained[name] = raw
            if name == "jobs":
                self.now += 45 * J.NS
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_HTTP_TIMEOUT"):
            J.acquire(admitted, "e" * 32, F.TOKEN, retain, clock=self.exact, minimum=self.now)
        self.assertEqual(set(retained), {"attempt", "jobs"})
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(value.closed and value.original_sock.stream.closed for value in self.connections))

    def test_frequency_change_during_http_is_original_failed_evidence_not_retry(self):
        admitted = admission()
        self.supply(admitted)
        readings = [C.Reading(self.exact, self.now)] * 3
        readings.append(C.Reading(replace(self.exact, ticks_per_second=1), self.now))
        readings.append(C.Reading(self.exact, self.now))
        retained = {}
        with patch.object(C, "observe", side_effect=readings), self.assertRaises(J.BudgetError):
            J.acquire(admitted, "e" * 32, F.TOKEN, lambda name, raw: retained.update({name: raw}), clock=self.exact)
        self.assertEqual(set(retained), {"attempt"})
        self.assertFalse(J.parse(retained["attempt"])["complete"])
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.connections[0].closed)
        self.assertNotIn(F.TOKEN.encode(), retained["attempt"])

    def terminal_clock_above_start_must_refuse(self, profile):
        admitted = admission() if profile == "desktop" else F.model_admission()
        modeled = originals(admitted, self.exact) if profile == "desktop" else F.model_responses(admitted)
        for label in ("attempt", "jobs"):
            value = J.parse(modeled[label])
            self.responses.append(base64.b64decode(value["headersBase64"]) + base64.b64decode(value["bodyBase64"]))
        retained, readings = {}, []
        original = self.connection

        def connection(*args, **kwargs):
            value = original(*args, **kwargs)
            getresponse, close = value.getresponse, value.close

            def read_body():
                response = getresponse()
                self.now += 10 * J.NS
                return response

            def finish():
                close()
                self.now -= 5 * J.NS

            value.getresponse, value.close = read_body, finish
            return value

        def observed():
            readings.append(self.now)
            return self.now

        error = None
        with patch.object(J.http.client, "HTTPSConnection", side_effect=connection), \
                patch.object(J, "shared_raw_ns", side_effect=observed), \
                patch.object(C, "observe", side_effect=lambda: C.Reading(self.exact, observed())):
            try:
                options = {"clock": self.exact} if profile == "desktop" else {}
                J.acquire(admitted, "e" * 32, F.TOKEN, lambda name, raw: retained.update({name: raw}), **options)
            except (J.BudgetError, C.ClockError) as caught:
                error = caught
        self.assertTrue(any(right < left for left, right in zip(readings, readings[1:])))
        self.assertGreater(readings[-1], readings[0], "The backward final sample must still exceed request start")
        self.assertIsInstance(error, J.BudgetError, "Parser high-water must survive response/connection close")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(set(retained), {"attempt"})
        value = J.parse(retained["attempt"])
        expected = J.parse(modeled["attempt"])
        self.assertEqual(value["headersBase64"], expected["headersBase64"])
        self.assertEqual(value["bodyBase64"], expected["bodyBase64"])
        self.assertFalse(value["complete"])
        self.assertIsNone(value["finishedRawNs"])
        self.assertEqual(value["error"], "JOB_TIME_CLOCK_FAILED")
        self.assertEqual(value["retirement"], "KNOWN")
        self.assertTrue(self.connections[0].closed and self.connections[0].original_sock.stream.closed)
        self.assertNotIn(F.TOKEN.encode(), retained["attempt"])

    def test_desktop_final_backward_sample_keeps_failed_first_original_and_never_retries(self):
        self.terminal_clock_above_start_must_refuse("desktop")

    def test_legacy_full_final_backward_sample_keeps_failed_first_original_and_never_retries(self):
        self.terminal_clock_above_start_must_refuse("full")

    def test_desktop_implicit_close_unknown_reaches_owner_with_exact_clock(self):
        for role in HOSTS:
            with self.subTest(role=role):
                self.exact = clock(role)
                admitted, retained, before = admission(role), {}, len(self.requests)
                self.responses.append(F.HttpModels._framed_response(self, "chunked"))
                streams, fixture = F.HttpModels._close_fixture(self, OSError("SYNTHETIC_DESKTOP_READER_CLOSE"))
                with fixture, self.assertRaises(J.BudgetError) as caught:
                    J.acquire(admitted, "e" * 32, F.TOKEN, lambda name, raw: retained.update({name: raw}),
                              clock=self.exact, minimum=self.now)
                self.assertEqual(set(retained), {"attempt"})
                value = J.parse(retained["attempt"])
                self.assertEqual(value["clock"], J.clock_value(self.exact))
                self.assertEqual(value["clockDomain"], self.exact.domain)
                self.assertEqual(value["profile"], "desktop")
                self.assertFalse(value["complete"])
                self.assertEqual(value["retirement"], "UNKNOWN")
                self.assertTrue(F.HttpModels._original_owner(self, caught.exception).unknown)
                self.assertEqual(streams[0].close_calls, 1)
                self.assertEqual(self.connections[-1].close_calls, 1)
                self.assertEqual(len(self.requests), before + 1)

    def test_desktop_failed_retention_preserves_cancellation_and_unknown(self):
        for kind in (KeyboardInterrupt, SystemExit):
            with self.subTest(kind=kind.__name__):
                cancellation = kind("SYNTHETIC_PRIVATE_DESKTOP_CANCELLATION")
                secondary = RuntimeError("SYNTHETIC_SECONDARY_RETENTION_FAILURE")
                retained, before = {}, len(self.requests)
                self.responses.append(F.HttpModels._framed_response(self, "length"))
                streams, fixture = F.HttpModels._close_fixture(self, cancellation)
                def retain(name, raw):
                    retained[name] = raw
                    raise secondary
                with fixture, self.assertRaises(BaseException) as caught:
                    J.acquire(admission(), "e" * 32, F.TOKEN, retain, clock=self.exact, minimum=self.now)
                self.assertIs(caught.exception, cancellation)
                self.assertIs(caught.exception.__context__, secondary)
                self.assertTrue(F.HttpModels._original_owner(self, caught.exception).unknown)
                self.assertEqual(set(retained), {"attempt"})
                value = J.parse(retained["attempt"])
                self.assertEqual(value["clock"], J.clock_value(self.exact))
                self.assertFalse(value["complete"])
                self.assertEqual(value["retirement"], "UNKNOWN")
                self.assertNotIn(b"SYNTHETIC_PRIVATE_DESKTOP_CANCELLATION", retained["attempt"])
                self.assertEqual(streams[0].close_calls, 1)
                self.assertEqual(len(self.requests), before + 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
