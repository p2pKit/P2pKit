#!/usr/bin/env python3
"""Offline service-time arithmetic and read-only chain controls, not admission.

All clock/native/query/HTTP boundaries are models. Only tiny ordinary-UID POSIX
files/descriptors are real in the chain fixtures. No build, provider, dependency,
native child or service request executes. Inherited cases are not counted again.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_service_time as T

spec = importlib.util.spec_from_file_location("bootstrap_service_time_entry_models",
    Path(__file__).with_name("hosted-cache-bootstrap-entry-test.py"))
E = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = E
spec.loader.exec_module(E)
M, S, O = E.H.M, E.S, E.O


class ArithmeticTests(unittest.TestCase):
    def test_literal_jobs_start_translation_and_zero_basis(self):
        self.assertEqual(T.basis_arithmetic(1002 * O.NS, 200, 210), {
            "jobsRequestStartedNs": 1002 * O.NS, "jobStartedEpochSeconds": 200,
            "serviceAgeSeconds": 10, "chargedAgeNs": 76 * O.NS, "jobStartBasisNs": 926 * O.NS})
        self.assertEqual(T.basis_arithmetic(66 * O.NS, 0, 0)["jobStartBasisNs"], 0)

    def test_typed_integer_only_and_no_underflow_or_charge_overflow(self):
        for position in range(3):
            for value in (True, 1.0, -1, "1", None, O.clocks.UINT64 + 1):
                args = [1002 * O.NS, 200, 210]; args[position] = value
                with self.subTest(position=position, value=value), self.assertRaises(T.ServiceTimeError):
                    T.basis_arithmetic(*args)
        for args in ((66 * O.NS - 1, 0, 0), (1002 * O.NS, 201, 200),
                     (O.clocks.UINT64, 0, O.clocks.UINT64)):
            with self.subTest(args=args), self.assertRaises(T.ServiceTimeError): T.basis_arithmetic(*args)

    def test_exact_large_integer_and_no_duration_policy_or_clock_override(self):
        start = (1 << 60) + 1
        self.assertEqual(T.basis_arithmetic(start, 0, 0)["jobStartBasisNs"], start - 66 * O.NS)
        for name in ("policy", "clock_margin", "maximum_age", "now", "trusted", "job_seconds"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                T.basis_arithmetic(start, 0, 0, **{name: 0})


class BasisTests(M.OfflineCase):
    def originals(self, admitted=None, clock=None, *, jobs_start=1_002_000_000_000):
        admitted = self.admitted if admitted is None else admitted
        clock = self.clock if clock is None else clock
        return {name: M.response(admitted, clock, name, body, start=jobs_start - (1 - index) * O.NS)
                for index, (name, body) in enumerate(M.service_bodies(admitted, clock).items())}

    def derive(self, originals=None, admitted=None, clock=None):
        return T.derive(self.admitted if admitted is None else admitted,
            self.originals() if originals is None else originals, "e" * 32,
            self.clock if clock is None else clock, M.RUNNER)

    def validate(self, raw, originals=None, admitted=None, clock=None):
        return T.validate_basis(raw, self.admitted if admitted is None else admitted,
            self.originals() if originals is None else originals, "e" * 32,
            self.clock if clock is None else clock, M.RUNNER)

    def change_header(self, originals, change):
        result = dict(originals)
        for name, raw in originals.items():
            value = O.parse(raw)
            value["headersBase64"] = base64.b64encode(change(base64.b64decode(value["headersBase64"]))).decode("ascii")
            result[name] = O.encoded(value)
        return result

    def change_body(self, originals, label, change, *, date=M.F.SERVICE_EPOCH):
        result = dict(originals)
        value = O.parse(result[label])
        body = O.parse(base64.b64decode(value["bodyBase64"]))
        change(body)
        body_raw = O.encoded(body)
        value["bodyBase64"] = base64.b64encode(body_raw).decode("ascii")
        value["headersBase64"] = base64.b64encode(M.F.header(body_raw, date=date)).decode("ascii")
        result[label] = O.encoded(value)
        return result

    def test_literal_arithmetic_charges_ten_seconds_plus_fixed_sixty_six(self):
        value = self.derive()
        self.assertEqual(value["jobsRequestStartedNs"], 1_002_000_000_000)
        self.assertEqual(value["jobStartedEpochSeconds"], 1_789_516_790)
        self.assertEqual(value["serviceAgeSeconds"], 10)
        self.assertEqual(value["chargedAgeNs"], 76_000_000_000)
        self.assertEqual(value["jobStartBasisNs"], 926_000_000_000)
        self.assertIs(type(value["jobStartBasisNs"]), int)

    def test_all_six_cohorts_keep_bootstrap_identity_and_exact_clock(self):
        for selected in ("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "desktop-macos-x64",
                         "full-macos-arm64", "full-macos-x64"):
            admitted, clock, _ = M.model_admission(selected)
            with self.subTest(selection=selected):
                value = self.derive(self.originals(admitted, clock), admitted, clock)
                self.assertEqual(value["profile"], "cache-bootstrap")
                self.assertEqual(value["selection"], selected)
                self.assertEqual(value["cacheCohort"], O.parse(admitted.record)["cacheCohort"])
                self.assertEqual(value["clock"], O.clock_value(clock))
                self.assertEqual(value["jobStartBasisNs"], 926_000_000_000)

    def test_closed_policy_contains_no_ordinary_allocation(self):
        self.assertEqual(T.policy(), {
            "scope": "SERVICE_DATE_TRANSLATION_NOT_NATIVE_START_OR_JOB_ALLOCATION",
            "anchor": "ORIGINAL_JOBS_REQUEST_STARTED_NS", "dateQuantizationSeconds": 1,
            "maximumServiceCacheSeconds": 60, "clockMarginSeconds": 5})
        self.assertEqual(set(self.derive()), {"schema", "scope", "profile", "selection", "cacheCohort", "source",
            "github", "admissionSha256", "clock", "invocation", "service", "policy", "jobsRequestStartedNs",
            "jobStartedEpochSeconds", "serviceAgeSeconds", "chargedAgeNs", "jobStartBasisNs", "budgetAcceptance",
            "testAcceptance", "exportSaveAuthority"})
        value = self.derive()
        self.assertEqual((value["schema"], value["scope"]), (1, "BOOTSTRAP_SERVICE_TIME_BASIS_V1"))
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(value["exportSaveAuthority"], False)

    def test_start_not_finish_attempt_start_or_current_clock_is_the_anchor(self):
        originals = self.originals()
        right = O.parse(originals["jobs"])
        right["finishedNs"] += 7_000_000_000
        originals["jobs"] = O.encoded(right)
        self.nanoseconds = 80_000_000_000_000
        value = self.derive(originals)
        self.assertEqual(value["jobStartBasisNs"], 926_000_000_000)
        self.assertEqual(value["service"]["firstNs"], 1_001_000_000_000)
        self.assertEqual(value["service"]["lastNs"], 1_009_000_000_001)

    def test_jobs_date_not_the_earlier_attempt_date_drives_age(self):
        originals = self.change_body(self.originals(), "attempt", lambda _: None, date=M.F.SERVICE_EPOCH - 3)
        value = self.derive(originals)
        self.assertEqual(value["serviceAgeSeconds"], 10)
        self.assertEqual(value["jobStartBasisNs"], 926_000_000_000)

    def test_date_advancement_charges_all_extra_service_age(self):
        originals = self.originals()
        for label in ("attempt", "jobs"):
            originals = self.change_body(originals, label, lambda _: None, date=M.F.SERVICE_EPOCH + 20)
        value = self.derive(originals)
        self.assertEqual(value["chargedAgeNs"], 96_000_000_000)
        self.assertEqual(value["jobStartBasisNs"], 906_000_000_000)

    def test_zero_service_age_still_charges_all_fixed_sixty_six_seconds(self):
        originals = self.change_body(self.originals(), "jobs",
            lambda body: body["jobs"][0].update(started_at=M.F.iso(M.F.SERVICE_EPOCH)))
        value = self.derive(originals)
        self.assertEqual(value["serviceAgeSeconds"], 0)
        self.assertEqual(value["chargedAgeNs"], 66_000_000_000)
        self.assertEqual(value["jobStartBasisNs"], 936_000_000_000)

    def test_zero_or_absent_age_and_zero_cache_headers_do_not_discount_policy(self):
        for age in (b"", b"Age: 0\r\n"):
            originals = self.change_header(self.originals(), lambda raw:
                raw.replace(b"max-age=60, s-maxage=60", b"max-age=0, s-maxage=0").replace(
                    b"Connection: close", age + b"Connection: close"))
            with self.subTest(age=age):
                self.assertEqual(self.derive(originals)["chargedAgeNs"], 76_000_000_000)

    def test_exact_zero_is_representable_without_a_new_epoch(self):
        value = self.derive(self.originals(jobs_start=76_000_000_000))
        self.assertEqual(value["jobStartBasisNs"], 0)
        self.assertIs(type(value["jobStartBasisNs"]), int)
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")

    def test_one_nanosecond_underflow_is_rejected_not_clamped(self):
        with self.assertRaisesRegex(T.ServiceTimeError, "BOOTSTRAP_SERVICE_TIME_INTEGER"):
            self.derive(self.originals(jobs_start=75_999_999_999))

    def test_integer_precision_above_double_exact_range(self):
        value = self.derive(self.originals(jobs_start=9_007_199_254_740_999))
        self.assertEqual(value["jobStartBasisNs"], 9_007_123_254_740_999)
        self.assertIs(type(value["jobStartBasisNs"]), int)

    def test_uint64_terminal_boundary_is_checked_without_float_rounding(self):
        value = self.derive(self.originals(jobs_start=18_446_744_073_709_551_614))
        self.assertEqual(value["service"]["lastNs"], 18_446_744_073_709_551_615)
        self.assertEqual(value["jobStartBasisNs"], 18_446_743_997_709_551_614)

    def test_nanosecond_charge_overflow_refuses_even_when_epoch_seconds_are_valid(self):
        originals = self.originals(jobs_start=18_446_744_073_709_551_614)
        originals = self.change_body(originals, "attempt", lambda body:
            body.update(created_at="1970-01-01T00:00:01Z", run_started_at="1970-01-01T00:00:01Z"),
            date=32_503_680_000)
        originals = self.change_body(originals, "jobs", lambda body:
            body["jobs"][0].update(started_at="1970-01-01T00:00:01Z"), date=32_503_680_000)
        with self.assertRaisesRegex(T.ServiceTimeError, "BOOTSTRAP_SERVICE_TIME_INTEGER"):
            self.derive(originals)

    def test_unsigned_integer_boundary_refuses_boolean_float_and_oversized_values(self):
        for value in (True, False, None, -1, 1.0, "1", 18_446_744_073_709_551_616):
            with self.subTest(value=value), self.assertRaises(T.ServiceTimeError):
                T.integer(value)
        self.assertEqual(T.integer(0), 0)
        self.assertEqual(T.integer(18_446_744_073_709_551_615), 18_446_744_073_709_551_615)

    def test_malformed_original_start_and_finish_are_not_arithmetic_inputs(self):
        for field, value in (("startedNs", True), ("startedNs", -1), ("startedNs", "1002000000000"),
                             ("finishedNs", 18_446_744_073_709_551_616), ("finishedNs", False)):
            originals = self.originals()
            row = O.parse(originals["jobs"]); row[field] = value; originals["jobs"] = O.encoded(row)
            with self.subTest(field=field, value=value), self.assertRaises(O.OriginError):
                self.derive(originals)

    def test_exact_clock_type_domain_role_and_frequency_are_required(self):
        class OtherClock(O.clocks.ClockIdentity):
            pass
        invalid = (None, O.clock_value(self.clock), OtherClock(self.clock.role, self.clock.domain, O.NS),
            O.clocks.ClockIdentity("linux-x64", O.clocks.DARWIN_DOMAIN, O.NS),
            O.clocks.ClockIdentity("linux-x64", O.clocks.LINUX_DOMAIN, True),
            O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, 0),
            O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, 1 << 63))
        for clock in invalid:
            with self.subTest(clock=clock), self.assertRaises(O.clocks.ClockError):
                T.derive(self.admitted, self.originals(), "e" * 32, clock, M.RUNNER)

    def test_qpc_frequency_and_cross_role_substitution_cannot_reuse_originals(self):
        admitted, clock, _ = M.model_admission("desktop-windows-x64")
        originals = self.originals(admitted, clock)
        with self.assertRaisesRegex(O.OriginError, "BOOTSTRAP_SERVICE_RESPONSE"):
            self.derive(originals, admitted, replace(clock, ticks_per_second=10_000_001))
        with self.assertRaisesRegex(O.OriginError, "BOOTSTRAP_SERVICE_NATIVE_ROLE"):
            self.derive(originals, admitted, self.clock)

    def test_exact_two_bytes_records_required_not_a_supplied_service_summary(self):
        class OtherDict(dict):
            pass
        originals = self.originals()
        for value in (None, [], {}, {"jobs": originals["jobs"]}, OtherDict(originals),
                      {**originals, "service": self.derive()["service"]},
                      {**originals, "attempt": bytearray(originals["attempt"])},
                      {**originals, "jobs": O.parse(originals["jobs"])}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(T.ServiceTimeError):
                T.derive(self.admitted, value, "e" * 32, self.clock, M.RUNNER)

    def test_service_identity_is_rechecked_for_original_failure_or_inconsistency(self):
        for label, field, value in (("jobs", "complete", False), ("attempt", "retirement", "UNKNOWN"),
                                    ("jobs", "status", 503), ("attempt", "invocation", "f" * 32),
                                    ("jobs", "path", "/repos/other/jobs")):
            originals = self.originals()
            row = O.parse(originals[label]); row[field] = value; originals[label] = O.encoded(row)
            with self.subTest(label=label, field=field), self.assertRaises((O.OriginError, O.wire.BudgetError)):
                self.derive(originals)

    def test_service_freshness_and_exact_job_page_are_not_skipped(self):
        cases = [self.change_header(self.originals(), lambda raw: raw.replace(
                    b"Connection: close", b"Age: 1\r\nConnection: close")),
            self.change_body(self.originals(), "jobs", lambda body: body.update(total_count=101)),
            self.change_body(self.originals(), "jobs", lambda body: body["jobs"][0].update(name="complete-gate")),
            self.change_body(self.originals(), "attempt", lambda body: body.update(run_attempt=2)),
            self.change_body(self.originals(), "jobs", lambda body:
                body["jobs"][0].update(started_at=M.F.iso(M.F.SERVICE_EPOCH + 1)))]
        for index, originals in enumerate(cases):
            with self.subTest(index=index), self.assertRaises((O.OriginError, O.wire.BudgetError)):
                self.derive(originals)

    def test_original_admission_source_run_policy_and_byte_hashes_are_bound(self):
        originals = self.originals()
        value = self.derive(originals)
        admitted = O.parse(self.admitted.record)
        self.assertEqual(value["source"], admitted["source"])
        self.assertEqual(value["github"], admitted["github"])
        self.assertEqual(value["admissionSha256"], hashlib.sha256(self.admitted.record).hexdigest())
        self.assertEqual(value["service"]["originalsSha256"],
            {name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()})
        for changed in (replace(self.admitted, original_event=self.admitted.original_event + b" "),
                        replace(self.admitted, original_policy=self.admitted.original_policy + b" "),
                        replace(self.admitted, public_key=b"SYNTHETIC_DIFFERENT_PUBLIC_INPUT")):
            with self.assertRaisesRegex(O.OriginError, "BOOTSTRAP_ORIGINAL_ADMISSION_BYTES"):
                self.derive(originals, changed)

    def test_ordinary_admission_cannot_gain_a_bootstrap_basis(self):
        with self.assertRaises(ValueError):
            self.derive(admitted=M.F.model_admission())

    def test_runner_and_invocation_are_original_service_bindings(self):
        for invocation, runner in (("f" * 32, M.RUNNER), ("e" * 32, "another synthetic runner")):
            with self.subTest(invocation=invocation, runner=runner), self.assertRaises(O.OriginError):
                T.derive(self.admitted, self.originals(), invocation, self.clock, runner)

    def test_retained_basis_validates_only_by_fresh_derivation(self):
        value = self.derive()
        raw = O.encoded(value)
        with patch.object(O, "service_identity", wraps=O.service_identity) as checked:
            self.assertEqual(self.validate(raw), value)
        checked.assert_called_once()

    def test_semantically_equal_reserialized_original_response_cannot_validate_old_basis(self):
        originals = self.originals()
        raw = O.encoded(self.derive(originals))
        for label in ("attempt", "jobs"):
            changed = {**originals, label: json.dumps(O.parse(originals[label]), indent=2).encode() + b"\n"}
            self.assertEqual(O.parse(changed[label]), O.parse(originals[label]))
            with self.subTest(label=label), self.assertRaises(T.ServiceTimeError):
                self.validate(raw, changed)
            self.assertNotEqual(self.derive(changed)["service"]["originalsSha256"],
                                self.derive(originals)["service"]["originalsSha256"])

    def test_changed_inner_response_bytes_also_invalidate_old_basis(self):
        originals = self.originals()
        raw = O.encoded(self.derive(originals))
        changed = self.change_body(originals, "jobs", lambda body: body["jobs"][0].update(id=457,
            url="https://api.github.com/repos/p2pKit/P2pKit/actions/jobs/457"))
        self.assertEqual(self.derive(changed)["service"]["numericJobId"], 457)
        with self.assertRaises(T.ServiceTimeError):
            self.validate(raw, changed)

    def test_basis_serialization_and_types_are_exact_not_parsed_equality(self):
        value = self.derive(); raw = O.encoded(value)
        for changed in (b" " + raw, raw + b"\n", json.dumps(value, indent=2).encode(), bytearray(raw),
                        memoryview(raw), None, b"{}", raw + raw):
            with self.subTest(kind=type(changed).__name__), self.assertRaises(T.ServiceTimeError):
                self.validate(changed)
        for field, item in (("schema", True), ("exportSaveAuthority", 0), ("jobStartBasisNs", 926_000_000_000.0)):
            changed = {**value, field: item}
            with self.subTest(field=field), self.assertRaises(T.ServiceTimeError):
                self.validate(O.encoded(changed))

    def test_changed_missing_or_extra_basis_policy_and_authority_fields_refuse(self):
        value = self.derive()
        variants = [{**value, name: item} for name, item in (("jobSeconds", 5400), ("workEndNs", 6400 * O.NS),
            ("exportSaveAuthority", True), ("budgetAcceptance", "ADMITTED"), ("testAcceptance", "PASS"),
            ("jobStartBasisNs", value["jobStartBasisNs"] + 1), ("profile", "full"))]
        missing = dict(value); del missing["service"]; variants.append(missing)
        for field in ("dateQuantizationSeconds", "maximumServiceCacheSeconds", "clockMarginSeconds"):
            variants.append({**value, "policy": {**value["policy"], field: 0}})
        variants.append({**value, "policy": {**value["policy"], "jobSeconds": 5400}})
        for index, changed in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(T.ServiceTimeError):
                self.validate(O.encoded(changed))

    def test_no_caller_budget_clock_read_or_trust_override_parameters_exist(self):
        for name in ("budget", "job_seconds", "policy", "now", "observed_start", "trusted"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                T.derive(self.admitted, self.originals(), "e" * 32, self.clock, M.RUNNER, **{name: 5400})

    def test_pure_equal_records_are_not_same_call_provenance_or_authority(self):
        before = self.originals(); saved = copy.deepcopy(before)
        value = self.derive(before)
        self.assertEqual(self.derive(dict(before), replace(self.admitted)), value)
        self.assertEqual(before, saved)
        value["policy"]["clockMarginSeconds"] = 0
        self.assertEqual(T.policy()["clockMarginSeconds"], 5)
        self.assertEqual(self.derive()["budgetAcceptance"], "NOT_ADMITTED")
        self.assertIs(self.derive()["exportSaveAuthority"], False)

    def test_derive_and_validate_do_not_read_files_clocks_or_execute_suppliers(self):
        originals = self.originals(); raw = O.encoded(self.derive(originals))
        guards = []
        with ExitStack() as stack:
            for module, name in ((Path, "read_bytes"), (Path, "write_bytes"), (M.os, "open"),
                (O.time, "time"), (O.time, "monotonic"), (O.clocks, "observe"), (O.clocks, "checked_now"),
                (O, "acquire"), (O, "_request"), (O.wire, "policy"), (S, "phase")):
                guards.append(stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_IO_OR_AUTHORITY"))))
            self.assertEqual(O.encoded(self.derive(originals)), raw)
            self.assertEqual(O.encoded(self.validate(raw, originals)), raw)
        for guard in guards:
            guard.assert_not_called()


class ChainTests(E.EntryModels):
    def rebind_parent(self, path, ack, change):
        """Coherently tamper SYNTHETIC files, never rewrite genuine originals."""
        result = O.parse((path / "origin-result.json").read_bytes())
        change(result["originalChain"])
        raw = O.encoded(result); (path / "origin-result.json").write_bytes(raw)
        handoff = O.parse((path / "prepare-handoff.json").read_bytes())
        handoff["originSha256"] = O.digest(raw)
        raw = O.encoded(handoff); (path / "prepare-handoff.json").write_bytes(raw)
        return {**ack, "handoffSha256": O.digest(raw)}

    def test_prepare_retains_basis_from_actual_modeled_original_response_files(self):
        path, _, _, result = self.prepare_handoff()
        basis = result["originalChain"]["serviceTimeBasis"]
        originals = {name: (path / "service" / (name + ".json")).read_bytes() for name in ("attempt", "jobs")}
        invocation = O.parse((path / "service/start.json").read_bytes())["invocation"]
        self.assertEqual(T.validate_basis(O.encoded(basis), self.admitted, originals, invocation, self.clock, M.RUNNER), basis)
        self.assertEqual(basis["service"], result["originalChain"]["service"])
        self.assertEqual(basis["jobStartBasisNs"], O.parse(originals["jobs"])["startedNs"] - 76_000_000_000)
        self.assertEqual(basis["chargedAgeNs"], 76_000_000_000)
        self.assertEqual((len(self.requests), len(self.scopes), len(self.admissions)), (2, 1, 2))

    def test_adoption_entry_and_receipt_keep_the_same_non_authorizing_basis(self):
        path, _, ack, result = self.prepare_handoff()
        before = {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        with self.adopter(ack):
            _, public = self.public_adoption()
        target = path.with_name(path.name + "-adoption")
        entry = O.parse((target / "entry-context.json").read_bytes())
        receipt = O.parse((target / "adoption-result.json").read_bytes())
        basis = result["originalChain"]["serviceTimeBasis"]
        self.assertEqual(entry["preparation"]["originalChain"]["serviceTimeBasis"], basis)
        self.assertEqual(receipt["originals"]["originalChain"]["serviceTimeBasis"], basis)
        self.assertEqual(basis["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(basis["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(basis["exportSaveAuthority"], False)
        self.assertNotIn("serviceTimeBasis", public)
        self.assertEqual(before, {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()})
        self.assertEqual((len(self.requests), len(self.scopes), len(self.admissions)), (2, 1, 3))

    def test_old_chain_missing_basis_cannot_be_backfilled_from_response_bytes(self):
        path, _, ack, _ = self.prepare_handoff()
        ack = self.rebind_parent(path, ack, lambda chain: chain.pop("serviceTimeBasis"))
        self.failed_adoption(ack, O.OriginError, "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN_CHANGED")
        self.assertEqual(len(self.admissions), 2)
        self.assertFalse(path.with_name(path.name + "-adoption").exists())

    def test_coherently_rehashed_false_basis_is_rederived_not_trusted(self):
        path, _, ack, _ = self.prepare_handoff()
        def change(chain):
            chain["serviceTimeBasis"]["jobStartBasisNs"] += 1
        ack = self.rebind_parent(path, ack, change)
        self.failed_adoption(ack, O.OriginError, "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN_CHANGED")
        self.assertEqual(len(self.admissions), 2)

    def test_coherently_rehashed_ordinary_budget_cannot_extend_the_chain(self):
        path, _, ack, _ = self.prepare_handoff()
        ack = self.rebind_parent(path, ack, lambda chain: chain["serviceTimeBasis"].update(
            jobSeconds=5400, budgetAcceptance="ADMITTED", exportSaveAuthority=True))
        self.failed_adoption(ack, O.OriginError, "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN_CHANGED")

    def test_same_preparation_normalizes_only_revalidation_not_service_basis(self):
        _, _, _, result = self.prepare_handoff()
        before = {"originalChain": result["originalChain"]}
        after = copy.deepcopy(before)
        after["originalChain"]["revalidatedNs"] += 1
        self.assertTrue(S.same_preparation(after, before))
        after["originalChain"]["serviceTimeBasis"]["jobStartBasisNs"] += 1
        self.assertFalse(S.same_preparation(after, before))

    def test_original_work_cutoff_still_applies_after_basis_rederivation(self):
        _, _, ack, _ = self.prepare_handoff()
        original = T.derive
        def delayed(*args):
            value = original(*args)
            self.nanoseconds = 1_075_000_000_000
            return value
        with patch.object(T, "derive", side_effect=delayed):
            self.failed_adoption(ack, O.OriginError, "BOOTSTRAP_ORIGINAL_FENCE_EXPIRED")
        self.assertEqual(len(self.admissions), 2)

    def test_basis_rederivation_does_not_renew_local_io45(self):
        _, _, ack, _ = self.prepare_handoff()
        original = T.derive
        def delayed(*args):
            value = original(*args)
            self.nanoseconds += 45_000_000_001
            self.assertLess(self.nanoseconds, 1_075_000_000_000)
            return value
        with patch.object(T, "derive", side_effect=delayed):
            self.failed_adoption(ack, S.posix.EvidenceError)
        self.assertEqual(len(self.admissions), 2)

    def test_basis_failure_stays_primary_over_later_close_failure(self):
        _, _, ack, _ = self.prepare_handoff()
        failure, close = T.ServiceTimeError("SYNTHETIC_BASIS_FAILURE"), S.Owner.close
        def failed_close(owner):
            close(owner)
            raise OSError("SYNTHETIC_LATER_CLOSE_FAILURE")
        with patch.object(T, "derive", side_effect=failure), patch.object(S.Owner, "close", side_effect=failed_close, autospec=True):
            caught = self.failed_adoption(ack, T.ServiceTimeError, "SYNTHETIC_BASIS_FAILURE")
        self.assertIs(caught, failure)

    def test_no_configuration_producer_cache_or_provider_is_called(self):
        import hosted_cache_bootstrap_producer as producer
        import hosted_dependency_cache as cache
        import hosted_dependency_seed_files as files
        guards = []
        with ExitStack() as stack:
            for module, name in ((producer, "make_request"), (producer, "observe_canonical"), (files, "seed_home"),
                                 (cache, "export_snapshot"), (cache, "save_set"), (cache, "provider_observation")):
                guards.append(stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_EXECUTION"))))
            _, _, ack, _ = self.prepare_handoff()
            with self.adopter(ack):
                S.adopt_originals([])
        for guard in guards:
            guard.assert_not_called()
        with self.assertRaisesRegex(files.SeedError, "SEED_BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
            files.require_connected_execution(self.admitted.record)


def load_tests(loader, _standard, _pattern):
    return unittest.TestSuite(kind(name) for kind in (BasisTests, ChainTests)
        for name in sorted(kind.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
