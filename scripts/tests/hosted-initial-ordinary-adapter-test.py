#!/usr/bin/env python3
"""Focused offline C seam controls; NOT native/provider/current qualification.

Only synthetic clocks/HTTP envelopes/owners and the repository's public policy
are used. Prior fixture BUILDERS are reused, never earlier test methods. Process,
network and native-loader audit events are forbidden. Nothing is dispatched.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import builtins
import copy
import ctypes  # Stdlib setup before the native-loader audit guard.
import hashlib
import importlib.util
import io
import math
import os
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_ordinary_adapter as H
import hosted_dependency_seed_files as SEED
import hosted_dependency_cache as CACHE
import hosted_cache_provider_clock as CLOCK
import hosted_cache_provider_prepare as PREPARE
import hosted_cache_provider_readback as READBACK
import hosted_cache_provider_return as TRANSPORT
import hosted_cache_provider_supervisor_return as OUTER
import hosted_cache_provider_worker as WORKER


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


C = load("initial_ordinary_adapter_custody_subject", ROOT / "scripts/run-hosted-test-custody.py")
M = load("initial_ordinary_adapter_original_fixture", Path(__file__).with_name(
    "hosted-initial-ordinary-originals-test.py"))
F, I, B, NS = M.F, H.I, H.job_time, H.NS


@contextmanager
def fixture(profile="desktop", role="linux-x64"):
    """Synthetic original-byte graph, not a successful native transcript."""
    model = M.OriginalModels(methodName="runTest")
    model.setUp()
    try:
        model.choose("worker", profile, role)
        observation = F.observation2(model.declaration, profile, role)
        match = H.identity.stages.match_ordinary(comment_raw=I.encoded(model.comment), comment_id=8002,
            body_sha256=F.body_hash(model.comment), observation_raw=I.encoded(observation), now=F.NOW,
            histories=model.histories, prior_ancestry_raw=F.H1.encode() + b"\n", **F.policy_inputs())
        bound = H.identity.bind_worker_match(match, comment_raw=I.encoded(model.comment),
            event_raw=I.encoded(model.event), policy_raw=F.POLICY, now=F.NOW)
        first = 1000 * NS
        context = {"schema": 1, "scope": "INITIAL_ORDINARY_NATIVE_ACQUISITION_CONTEXT_V1", "root": str(ROOT),
            "session": r"C:\model\source" if role == "windows-x64" else "/model/source", "job": "a" * 32,
            "invocation": M.INVOCATION, "observed": copy.deepcopy(model.context),
            "eventSha256": H.digest(bound.original_event), "previous": None, "expectedMatch": None,
            "window": {"clock": B.clock_value(model.clock), "firstNs": first,
                       "workEndNs": first + 75 * NS, "finalEndNs": first + 120 * NS}}
        values = {"model": model, "bound": bound, "context": context,
            "session": {"scope": "ORDINARY_GIT_QUERIES_ONLY", "result": "READY_FOR_CALLER_SEAL",
                "retirement": "KNOWN", "firstError": None, "errors": []},
            "start": {"scope": "INITIAL_ORDINARY_NATIVE_ACQUISITION_START_V1", "invocation": M.INVOCATION,
                "clock": B.clock_value(model.clock), "startedNs": first},
            "child": {"scope": "INITIAL_ORDINARY_ACQUIRED_PENDING_NATIVE_PARENT_CLOSE_V1", "completedNs": first + 3 * NS},
            "ack": {"scope": "INITIAL_ORDINARY_CHILD_ORIGINAL_OWNER_RETURN_V1", "retirement": "KNOWN",
                    "closedNs": first + 4 * NS},
            "native": {"scope": "INITIAL_ORDINARY_NATIVE_CHILD_RETURN_PENDING_OWNER_CLOSE_V1", "invocation": M.INVOCATION,
                "launchAttempted": True, "scopeAttempted": True, "exitCode": 0, "retirement": "KNOWN",
                "ownedSurvivors": [], "errors": [], "ownership": {"discoveryErrors": []}, "completedNs": first + 5 * NS},
            "close": {"scope": "INITIAL_ORDINARY_ACTUAL_OWNER_CLOSE_V1", "retirement": "KNOWN", "errors": [],
                "closedNs": first + 6 * NS}}
        yield values
    finally:
        model.doCleanups()


def originals(values, *, change_session=lambda _value: None):
    """Bind modeled producer bytes faithfully so negative controls reach a seam."""
    model, bound = values["model"], values["bound"]
    responses = {name: model.request(model.paths[name], M.TOKEN, M.INVOCATION,
        model.fence, 1045 * NS)[0] for name in ("attempt", "jobs")}
    context_raw = I.encoded(values["context"])
    path = PureWindowsPath if model.clock.role == "windows-x64" else Path
    session = copy.deepcopy(values["session"])
    session["readbacks"] = [{"parent": str(path(values["context"]["session"]) / "current-first"),
        "name": name + ".bin", "maximum": len(raw), "retirement": "KNOWN", "result": "RETAINED",
        "bytes": len(raw), "sha256": H.digest(raw)} for name, raw in responses.items()]
    change_session(session)
    session_raw = I.encoded(session)
    start_raw = I.encoded({**values["start"], "contextSha256": H.digest(context_raw)})
    child_raw = I.encoded({**values["child"], "contextSha256": H.digest(context_raw),
        "startSha256": H.digest(start_raw), "firstSessionSha256": H.digest(session_raw)})
    ack_raw = I.encoded({**values["ack"], "contextSha256": H.digest(context_raw), "terminalSha256": H.digest(child_raw)})
    native_raw = I.encoded({**values["native"], "startSha256": H.digest(start_raw),
        "captures": {"stdout": {"sha256": H.digest(ack_raw)}}})
    close_raw = I.encoded(values["close"])
    current = current_data(bound, model.clock.role)
    current.update(contextSha256=H.digest(context_raw), nativeReturnSha256=H.digest(native_raw),
                   ownerCloseSha256=H.digest(close_raw))
    return {"current_raw": I.encoded(current), "context_raw": context_raw, "identity_raw": bound.record,
        "attempt_raw": responses["attempt"], "jobs_raw": responses["jobs"], "first_session_raw": session_raw,
        "child_raw": child_raw, "child_ack_raw": ack_raw, "native_start_raw": start_raw,
        "native_return_raw": native_raw, "owner_close_raw": close_raw}


def current_data(bound, role):
    record = I.parse(bound.record, 4 * 1024 * 1024)
    return {"schema": 1, "scope": "INITIAL_ORDINARY_ORIGINAL_CURRENT_SOURCE_V1", "contextSha256": "1" * 64,
        "source": record["source"], "reviewed": record["initialRecipient"]["reviewed"], "kind": "worker",
        "profile": record["profile"], "role": role, "matchSha256": H.digest(I.encoded(record["initialRecipient"])),
        "identitySha256": H.digest(bound.record), "qualifications": [char * 64 for char in "2345"],
        "ownerCloseSha256": "6" * 64, "nativeReturnSha256": "7" * 64, "pendingSha256": "8" * 64,
        "ordinaryAcceptance": "NOT_PERFORMED", "h2ProviderAcceptance": "NOT_PERFORMED", "cryptoAcceptance": "NOT_PERFORMED",
        "budgetAcceptance": "NOT_ADMITTED", "publicationAuthority": False}


def crypto_fixture(values, budget, operation="export"):
    bound = values["bound"]
    record = I.parse(bound.record, 4 * 1024 * 1024)
    current = current_data(bound, values["model"].clock.role)
    context = {"scope": H.INITIAL_CONTEXT_SCOPE, "profile": budget.profile, "role": values["model"].clock.role,
        "job": "a" * 32, "root": str(ROOT), "session": "/model/session", "source": record["source"],
        "admissionSha256": H.digest(bound.record), "jobBudgetSha256": budget.sha256,
        "initialOrdinary": {"historySha256": "c" * 64, "identitySha256": H.digest(bound.record),
                            "sourceBudgetSha256": budget.sha256, "samplePackagingRequired": False}}
    context_raw = I.encoded(context)
    began = budget.value["responseFinishedRawNs"] + 10 * NS
    started = {"job": context["job"], "invocation": "b" * 32, "state": context["session"],
        "home": str(Path(context["session"]) / "control-home"), "cwd": str(ROOT),
        "phase": "export" if operation == "export" else "recipient-validation", "startedRawNs": began,
        "jobBudgetSha256": budget.sha256, "clock": B.clock_value(budget.clock)}
    request = {"schema": 1, "scope": H.CRYPTO_SCOPE, "operation": operation, "source": record["source"],
        "github": record["github"], "identitySha256": H.digest(bound.record), "policySha256": H.digest(bound.original_policy),
        "contextSha256": H.digest(context_raw), "historySha256": "c" * 64, "jobBudgetSha256": budget.sha256,
        "currentSha256": H.digest(I.encoded(current)), "current": I.encoded(current).decode("ascii"),
        "native": {name: started[name] for name in ("job", "invocation", "state", "home", "cwd", "phase")},
        "window": {"clock": B.clock_value(budget.clock), "startedNs": began,
                   "workEndNs": began + 240 * NS, "finalEndNs": began + 285 * NS}}
    return request, context_raw, started


class DataControls(unittest.TestCase):
    def test_four_worker_current_data_keep_all_pending_acceptance_fields(self):
        for profile, role in (("desktop", "linux-x64"), ("desktop", "windows-x64"),
                ("desktop", "macos-arm64"), ("full", "macos-arm64")):
            with self.subTest(profile=profile, role=role), fixture(profile, role) as values:
                bound = values["bound"]
                current = current_data(bound, role)
                self.assertEqual(H.identity.retained_current(I.encoded(current), bound, role), current)
                self.assertIs(current["publicationAuthority"], False)
                self.assertIsNone(SEED.validate_cohort(bound.record, profile, role))
                self.assertNotIsInstance(bound, I.Admission)

    def test_current_missing_extra_gate_bool_and_claimed_acceptance_are_refused(self):
        with fixture() as values:
            bound, role = values["bound"], "linux-x64"
            for change in ({"extra": 1}, {"schema": True}, {"kind": "gate"}, {"scope": H.identity.SCOPE},
                    {"ordinaryAcceptance": "PASS"}, {"h2ProviderAcceptance": "PASS"}, {"cryptoAcceptance": "PASS"},
                    {"budgetAcceptance": "ADMITTED"}, {"publicationAuthority": 0}, {"pendingSha256": "bad"},
                    {"role": "macos-arm64"}, {"matchSha256": "f" * 64}, {"qualifications": ["1" * 64]}):
                with self.subTest(change=change), self.assertRaises(I.AdmissionError):
                    H.identity.retained_current(I.encoded({**current_data(bound, role), **change}), bound, role)
            current = current_data(bound, role)
            del current["pendingSha256"]
            with self.assertRaises(I.AdmissionError):
                H.identity.retained_current(I.encoded(current), bound, role)

    def test_current_exact_canonical_bytes_and_original_identity_are_required(self):
        with fixture() as values:
            raw = I.encoded(current_data(values["bound"], "linux-x64"))
            for bad in (raw + b"\n", b" " + raw, raw.replace(b'"schema":1', b'"schema":1,"schema":1')):
                with self.assertRaises((I.AdmissionError, ValueError)):
                    H.identity.retained_current(bad, values["bound"], "linux-x64")
            with self.assertRaises(I.AdmissionError):
                H.identity.retained_current(raw, SimpleNamespace(record=values["bound"].record), "linux-x64")

    def test_retained_identity_binds_real_public_policy_bytes_without_private_access(self):
        with fixture() as values:
            bound = values["bound"]
            self.assertEqual(H.identity.retained_identity(bound.record, bound.original_event,
                bound.original_policy, bound.public_key, now=F.NOW), bound)
            for key in (b"", bound.public_key + b"\n"):
                with self.assertRaises(I.AdmissionError):
                    H.identity.retained_identity(bound.record, bound.original_event, bound.original_policy, key, now=F.NOW)

    def test_initial_context_refuses_sample_packaging_and_ordinary_scope(self):
        with fixture() as values:
            budget = B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
            _request, context_raw, _started = crypto_fixture(values, budget)
            context = I.parse(context_raw, 4 * 1024 * 1024)
            self.assertIs(H.initial_context(context)["samplePackagingRequired"], False)
            for change in ({"scope": "CLOSED_ORDINARY_TEST_CONTROLLER"}, {"samplePackagingRequired": True},
                    {"initialOrdinary": {**context["initialOrdinary"], "samplePackagingRequired": 0}},
                    {"jobBudgetSha256": "f" * 64}):
                with self.assertRaises(I.AdmissionError):
                    H.initial_context({**context, **change})

    def test_first_response_budget_retains_exact_original_caps_on_four_cohorts(self):
        for profile, role in (("desktop", "linux-x64"), ("desktop", "windows-x64"),
                ("desktop", "macos-arm64"), ("full", "macos-arm64")):
            with self.subTest(profile=profile, role=role), fixture(profile, role) as values:
                data = originals(values)
                budget = B.derive_initial_retained(values["bound"], data, "a" * 32)
                value = budget.value
                self.assertEqual((value["schema"], budget.profile, budget.clock), (3, profile, values["model"].clock))
                self.assertEqual(value["policy"], B.policy(profile, clock=budget.clock))
                self.assertEqual(value["originalsSha256"], {name: H.digest(data[name + "_raw"]) for name in ("attempt", "jobs")})
                self.assertEqual(value["provenance"]["sourceCurrentSha256"], H.digest(data["current_raw"]))
                self.assertNotIn("admissionSha256", value)
                self.assertNotIn("phaseResultSha256", value["provenance"])
                self.assertEqual(B.Budget(budget.record).record, budget.record)

    def test_budget_refuses_refreshed_origin_instead_of_renewing_first_job_time(self):
        for field, value in (("previous", []), ("expectedMatch", "e" * 64)):
            with fixture() as values:
                values["context"][field] = value
                with self.assertRaisesRegex(B.BudgetError, "FIRST_WORKER_CONTEXT"):
                    B.derive_initial_retained(values["bound"], originals(values), "a" * 32)

    def test_budget_requires_source_readback_not_merely_adjacent_http_hashes(self):
        changes = (lambda s: s.update(readbacks=[]), lambda s: s["readbacks"][0].update(parent="/other"),
                   lambda s: s["readbacks"][1].update(retirement="UNKNOWN"))
        for change in changes:
            with fixture() as values:
                with self.assertRaisesRegex(B.BudgetError, "RESPONSE_NOT_RETAINED_BY_SOURCE"):
                    B.derive_initial_retained(values["bound"], originals(values, change_session=change), "a" * 32)

    def test_budget_original_native_failure_or_missing_predecessor_never_grants_time(self):
        for part, field, value in (("native", "exitCode", True), ("native", "retirement", "UNKNOWN"),
                ("close", "errors", ["SYNTHETIC"]), ("ack", "retirement", "UNKNOWN")):
            with fixture() as values:
                values[part][field] = value
                with self.assertRaises(B.BudgetError):
                    B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
        with fixture() as values:
            values["model"].bodies["jobs"]["jobs"].pop()
            values["model"].bodies["jobs"]["total_count"] = 1
            with self.assertRaises((I.AdmissionError, B.BudgetError)):
                B.derive_initial_retained(values["bound"], originals(values), "a" * 32)

    def test_budget_schema_and_original_fences_cannot_be_relabeled_or_extended(self):
        with fixture() as values:
            budget = B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
            for change in ({"scope": "IMMUTABLE_ORDINARY_DESKTOP_JOB_BUDGET"}, {"schema": True},
                    {"identitySha256": "bad"}, {"fencesRawNs": {**budget.value["fencesRawNs"],
                        "productive": budget.fence("productive") + 1}}, {"extra": "forbidden"}):
                with self.assertRaises(B.BudgetError):
                    B.Budget(I.encoded({**budget.value, **change})).value

    def test_inverse_clock_mapping_never_exceeds_exact_local_or_raw_remainder(self):
        from fractions import Fraction
        for local, end in ((1000.0, 1030.0), (1000.1, 1030.3), (1e8, math.nextafter(1e8, math.inf))):
            cap = H.local_raw_cap(1000, 10 ** 14, local, end)
            exact = (Fraction(end) - Fraction(local)) * NS
            self.assertLessEqual(cap - 1000, exact)
            self.assertGreater(cap, 1000)
        self.assertEqual(H.local_raw_cap(1000, 1500, 1000.0, 1030.0), 1500)
        for args in ((True, 1500, 1.0, 2.0), (1000, 1000, 1.0, 2.0), (1000, 1500, 2.0, 1.0),
                     (1000, 1500, 1.0, math.inf), (1000, 1500, 0.0, 1e-20)):
            with self.assertRaises(I.AdmissionError):
                H.local_raw_cap(*args)

    def test_unregistered_session_and_preloaded_registry_cannot_be_hydrated(self):
        with self.assertRaises(I.AdmissionError):
            H.CurrentSession.check(object.__new__(H.CurrentSession), current=False)
        with patch.object(H, "_MODULE", None), patch.dict(sys.modules, {H.MODULE_NAME: object()}):
            with self.assertRaisesRegex(I.AdmissionError, "PRELOADED_CURRENT_NAMESPACE"):
                H.current_module()

    def test_crypto_data_requires_exact_current_native_request_and_original_window(self):
        with fixture() as values:
            budget = B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
            for operation in ("validate", "export"):
                request, context, start = crypto_fixture(values, budget, operation)
                self.assertIs(type(H.crypto_request_data(I.encoded(request), values["bound"], context, budget, start,
                    operation)), H.CryptoRequest)
                for change in ({"operation": "validate" if operation == "export" else "export"},
                        {"historySha256": "f" * 64}, {"currentSha256": "f" * 64},
                        {"native": {**request["native"], "job": "c" * 32}},
                        {"window": {**request["window"], "finalEndNs": request["window"]["finalEndNs"] + 1}}):
                    with self.assertRaises(I.AdmissionError):
                        H.crypto_request_data(I.encoded({**request, **change}), values["bound"], context, budget, start, operation)
                current = I.parse(request["current"].encode(), 4 * 1024 * 1024)
                current["extra"] = True
                raw = I.encoded(current)
                with self.assertRaises(I.AdmissionError):
                    H.crypto_request_data(I.encoded({**request, "current": raw.decode(), "currentSha256": H.digest(raw)}),
                        values["bound"], context, budget, start, operation)

    def test_crypto_child_also_requires_actual_inherited_domain_not_just_request_data(self):
        with fixture() as values:
            budget = B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
            request, context, start = crypto_fixture(values, budget)
            env = H.processes.ownership_environment({}, start["job"], start["invocation"], start["state"],
                                                    start["home"], allow_new_context=True)
            inherited = {name: env[name] for name in H.query._CONTEXT}
            self.assertIs(type(H.crypto_request(I.encoded(request), values["bound"], context, budget, start, inherited,
                "export")), H.CryptoRequest)
            for bad in ({}, {**inherited, H.processes.JOB_ENV: "f" * 32}):
                with self.assertRaises((I.AdmissionError, H.processes.OwnershipError)):
                    H.crypto_request(I.encoded(request), values["bound"], context, budget, start, bad, "export")

    def test_schema5_manifest_keeps_first_pr_and_outside_frozen_scope_explicit(self):
        with fixture() as values:
            budget = B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
            request, context, start = crypto_fixture(values, budget)
            admitted = H.crypto_request_data(I.encoded(request), values["bound"], context, budget, start, "export")
            manifest = H.manifest_data(admitted)
            self.assertEqual(manifest["schema"], 5)
            self.assertEqual(manifest["scope"], "ENCRYPTED_PRIVATE_INITIAL_ORDINARY_TEST_EVIDENCE")
            self.assertIs(manifest["initialOrdinary"]["samplePackagingRequired"], False)
            self.assertEqual(manifest["initialOrdinary"]["lateSourceOriginals"], "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD")
            self.assertEqual(manifest["initialOrdinary"]["privateOwnerInspection"], "NOT_PERFORMED_BY_WORKFLOW")
            self.assertEqual(manifest["initialOrdinary"]["requestSha256"], H.digest(admitted.raw))

    def test_late_source_and_seal_data_cannot_claim_delivered_originals_or_decryption(self):
        with fixture() as values:
            budget = B.derive_initial_retained(values["bound"], originals(values), "a" * 32)
            _request, context_raw, _start = crypto_fixture(values, budget)
            context = I.parse(context_raw, 4 * 1024 * 1024)
            source = {"identitySha256": H.digest(values["bound"].record), "historySha256": "c" * 64,
                "currentSha256": "d" * 64, "lateSourceOriginals": "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD"}
            self.assertEqual(C.initial_operation_source_data(source, context), source)
            for change in ({"historySha256": "f" * 64}, {"lateSourceOriginals": "RETAINED_14_DAYS"}, {"owner": "invented"}):
                with self.assertRaises(C.ControllerError):
                    C.initial_operation_source_data({**source, **change}, context)
            seal = dict.fromkeys(("controllerResultSha256", "manifestSha256", "artifact", "profilePassed", "source",
                "retirement", "jobBudgetSha256", "clockDomain", "sealedAtRawNs", "upload", "deliveryEndRawNs"))
            seal.update(schema=1, scope="INITIAL_ORDINARY_POST_RETURN_SEAL_V1", decryption="NOT_PERFORMED", initialOrdinary=source)
            self.assertEqual(C.initial_seal_data(seal, context), source)
            for change in ({"scope": "ORDINARY_POST_RETURN_SEAL_V1"}, {"decryption": "PASS"}, {"extra": True}):
                with self.assertRaises(C.ControllerError):
                    C.initial_seal_data({**seal, **change}, context)


def service_fixture(initial=True, role="linux-x64"):
    windows = role == "windows-x64"
    base = r"C:\model" if windows else "/model"
    request = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": role, "frequency": 10 ** 7 if windows else NS,
        "firstNs": str(101 * NS), "issuedNs": str(100 * NS), "hardEndNs": str(280 * NS),
        "workerCutoffNs": str(250 * NS), "phase": "restore", "job": "1" * 32, "outerId": "2" * 32, "innerId": "3" * 32,
        "directory": base + (r"\provider" if windows else "/provider"), "directoryIdentity": [1, "a" * 32] if windows else [1, 1],
        "home": base + (r"\provider-home" if windows else "/provider-home"), "homeIdentity": [1, "b" * 32] if windows else [1, 2],
        "node": base + (r"\node.exe" if windows else "/node"), "toolPath": base,
        "plan": {"mode": "consume", "session": base, "MODEL_NOT_ADMISSION": True}}
    raw = TRANSPORT._json(request)
    python = base + (r"\python.exe" if windows else "/python3")
    bindings = tuple((name, "a" * 64) for name in WORKER.outer_names(role))
    clocks = tuple((name, "a" * 64) for name in CLOCK.roster(role))
    prepared = PREPARE.PreparedProvider(raw, bindings, clocks, "b" * 64, 102 * NS)
    frame = H.service_frame(prepared, python, initial_ordinary=initial)
    refs = tuple(OUTER.FileReference(3, H.digest(b"abc"), (1, str(n) * 32) if windows else (1, n)) for n in range(3, 7))
    closes = ["scope", "retirement-writer", *([] if windows else ["stdout-reader", "stderr-reader"]),
              "packet-reader", "stderr", "stdout", "bundle", "capture_directory", "home", "directory"]
    transcript = SimpleNamespace(failed=False, worker_exit_code=0, provider_return=SimpleNamespace(kind="success"),
                                 observed_ns=150 * NS, closed_resources=tuple(closes))
    ack = OUTER.acknowledge(raw, TRANSPORT._json({**request, "schema": 1}), transcript, refs)
    def observation(phase, minimum, observed):
        return I.encoded({"schema": "P2PKIT_PROVIDER_" + phase + "_CLOCK_OBSERVATION_V1",
            "invocationSha256": H.digest(raw), "role": role, "frequency": str(request["frequency"]),
            "minimumNs": str(minimum), "hardEndNs": request["hardEndNs"], "domain": B._clocks().DOMAINS[role],
            "observedNs": str(observed)}).decode("ascii")
    result = {"schema": 1, "scope": "P2PKIT_" + ("INITIAL_ORDINARY_" if initial else "ORDINARY_") + "RESTORE_SERVICE_RETURN_V1",
        "controllerRequestSha256": H.digest(frame), "supervisorRequestSha256": H.digest(raw), "acknowledgement": ack.decode("ascii"),
        "prelaunchClock": observation("PRELAUNCH", 101 * NS, 110 * NS), "postCloseClock": observation("POST_CLOSE", 150 * NS, 151 * NS),
        "enclosingNodeReturn": "NOT_OBSERVED", "providerAcceptance": "NOT_ESTABLISHED"}
    return raw, frame, result


class ServiceDataControls(unittest.TestCase):
    def test_two_service_origins_have_closed_frames_without_lending_native_acceptance(self):
        for initial in (False, True):
            for role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64"):
                with self.subTest(initial=initial, role=role):
                    request, frame, result = service_fixture(initial, role)
                    self.assertFalse(request.endswith(b"\n"))
                    self.assertTrue(frame.endswith(b"\n"))
                    value, ack = H.service_return(I.encoded(result), frame, request, initial_ordinary=initial)
                    self.assertEqual(ack.kind, "success")
                    self.assertEqual(value["providerAcceptance"], "NOT_ESTABLISHED")
                    with self.assertRaises(I.AdmissionError):
                        H.service_request_data(frame, request, initial_ordinary=not initial)

    def test_service_frame_refuses_noncanonical_relabelled_missing_or_wrong_source_rosters(self):
        request, frame, _result = service_fixture()
        value = I.parse(frame, 16384)
        changes = ({"schema": True}, {"python": "/model/bash"}, {"python": "python3"}, {"extra": True},
                   {"request": value["request"] + "\n"}, {"bindings": {}}, {"clockBindings": {}})
        for change in changes:
            with self.assertRaises((I.AdmissionError, ValueError)):
                H.service_request_data(I.encoded({**value, **change}), request, initial_ordinary=True)
        for raw in (frame + b"\n", b" " + frame, frame * 2, b"x" * 16385):
            with self.assertRaises((I.AdmissionError, ValueError)):
                H.service_request_data(raw, request, initial_ordinary=True)

    def test_service_return_refuses_success_before_original_clock_ack_and_close_bindings(self):
        request, frame, result = service_fixture()
        for change in ({"controllerRequestSha256": "f" * 64}, {"supervisorRequestSha256": "f" * 64},
                {"enclosingNodeReturn": "KNOWN"}, {"providerAcceptance": "PASS"}, {"schema": True}, {"extra": True}):
            with self.assertRaises(I.AdmissionError):
                H.service_return(I.encoded({**result, **change}), frame, request, initial_ordinary=True)
        for field, observed in (("postCloseClock", str(149 * NS)), ("prelaunchClock", str(151 * NS)),
                                 ("postCloseClock", str(280 * NS))):
            clock = I.parse(result[field].encode("ascii"), 1024)
            clock["observedNs"] = observed
            with self.assertRaises(I.AdmissionError):
                H.service_return(I.encoded({**result, field: I.encoded(clock).decode("ascii")}), frame, request,
                                 initial_ordinary=True)


class MemoryFile:
    """Synthetic file lifetime only; no descriptor or native acceptance."""
    def __init__(self, entry, maximum, writable=False):
        self.entry, self.maximum, self.writable = entry, maximum, writable
        self.offset, self.closed, self.close_calls = 0, False, 0
        self.read_sizes, self.close_error, self.read_error = [], None, None
        self.extra_eof = b""
        self._pins = [SimpleNamespace(fd=12345)]  # Borrowed DATA, never used by an OS API.

    def verify(self):
        if self.closed or len(self.entry["raw"]) > self.maximum:
            raise RuntimeError("MODEL_FILE_NOT_LIVE")
        return SEED.PosixInfo(self.entry["identity"], False, len(self.entry["raw"]), 0o100600, 1000, 1, 1, 1)

    def read(self, size):
        if self.read_error is not None:
            raise self.read_error
        if self.closed or self.writable or not 0 <= size <= C.MIB:
            raise AssertionError("MODEL_BOUNDED_READ")
        self.read_sizes.append(size)
        if self.offset == len(self.entry["raw"]):
            return self.extra_eof
        raw = self.entry["raw"][self.offset:self.offset + size]
        self.offset += len(raw)
        return raw

    def write(self, raw):
        if self.closed or not self.writable or not 0 < len(raw) <= C.MIB or len(self.entry["raw"]) + len(raw) > self.maximum:
            raise AssertionError("MODEL_BOUNDED_WRITE")
        self.entry["raw"] += raw
        return len(raw)

    def seek(self, offset):
        if offset != 0 or self.writable or self.closed:
            raise AssertionError("MODEL_REWIND_ONLY")
        self.offset = 0
        return 0

    def sync(self):
        self.verify()

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class MemoryRoot:
    def __init__(self, state):
        self.state, self.path, self.identity = state, state["path"], state["identity"]
        self.closed = False

    def open_file(self, name, *, max_bytes, deadline):
        entry = self.state["files"][name]
        if len(entry["raw"]) > max_bytes:
            raise RuntimeError("MODEL_FILE_OVERSIZED")
        reader = MemoryFile(entry, max_bytes)
        self.state["readers"].append(reader)
        self.state["on_reader"](reader)
        return reader

    def create_file(self, name, *, max_bytes, deadline):
        if name in self.state["files"]:
            raise RuntimeError("MODEL_NO_OVERWRITE")
        self.state["next"] += 1
        entry = {"raw": b"", "identity": (1, self.state["next"])}
        self.state["files"][name] = entry
        writer = MemoryFile(entry, max_bytes, writable=True)
        self.state["writers"].append(writer)
        return writer

    def read_bytes(self, name, *, max_bytes, deadline):
        raw = self.state["files"][name]["raw"]
        if len(raw) > max_bytes:
            raise RuntimeError("MODEL_READ_BOUND")
        return raw

    def names(self, *, max_names, deadline):
        if len(self.state["files"]) > max_names:
            raise RuntimeError("MODEL_NAME_BOUND")
        return list(self.state["files"])

    def close(self):
        self.closed = True


class MemoryOwner(C.PrivateOwner):
    """Only a focused copy model. It cannot satisfy production episode registry."""
    mode, local_end = "readback", 1000.0

    def end(self):
        if self.unknown or self.original is not None:
            raise RuntimeError("MODEL_OWNER_FAILED")
        return self.local_end


def memory_state(path="/model/raw4", first=20):
    return {"path": Path(path), "identity": (1, first), "next": first,
        "files": {}, "readers": [], "writers": [], "on_reader": lambda _reader: None}


class RawOriginalControls(unittest.TestCase):
    def test_six_mib_packet_streaming_keeps_eof_identity_reread_and_known_close(self):
        state = memory_state()
        raw = b"s" * (6 * C.MIB)
        state["files"]["worker-return.json"] = {"raw": raw, "identity": (1, 21)}
        owner, directory = MemoryOwner(), MemoryRoot(state)
        with patch.object(C.seed, "private_root", side_effect=lambda _path: MemoryRoot(state)):
            returned, binding = C.provider_file_bytes(owner, directory, "worker-return.json", 6 * C.MIB, 1000.0, owner.end)
        self.assertEqual(returned, raw)
        reader = state["readers"][0]
        self.assertEqual(reader.read_sizes, [C.MIB] * 6 + [1])
        self.assertEqual(binding, SEED._info_binding(SEED.PosixInfo((1, 21), False, len(raw), 0o100600, 1000, 1, 1, 1)))
        self.assertTrue(all(row["closed"] for row in owner.resources))

    def test_raw_reader_refuses_extra_eof_oversize_and_unknown_close(self):
        for failure_kind in ("extra", "oversize", "close"):
            state = memory_state()
            state["files"]["worker-return.json"] = {"raw": b"abc", "identity": (1, 21)}
            if failure_kind == "extra":
                state["on_reader"] = lambda reader: setattr(reader, "extra_eof", b"unexpected")
            if failure_kind == "close":
                state["on_reader"] = lambda reader: setattr(reader, "close_error", RuntimeError("MODEL_CLOSE_FAILED"))
            owner = MemoryOwner()
            with patch.object(C.seed, "private_root", side_effect=lambda _path: MemoryRoot(state)):
                with self.assertRaises((C.ControllerError, RuntimeError)):
                    C.provider_file_bytes(owner, MemoryRoot(state), "worker-return.json",
                        2 if failure_kind == "oversize" else 3, 1000.0, owner.end)
            if failure_kind == "close":
                self.assertTrue(owner.unknown)
                self.assertEqual(state["readers"][0].close_calls, 1)

    def test_raw_reader_preserves_first_error_when_its_close_also_fails(self):
        state, first, second = memory_state(), RuntimeError("MODEL_READ_FAILED"), RuntimeError("MODEL_CLOSE_FAILED")
        state["files"]["worker-return.json"] = {"raw": b"abc", "identity": (1, 21)}
        def change(reader):
            reader.read_error, reader.close_error = first, second
        state["on_reader"] = change
        owner = MemoryOwner()
        with patch.object(C.seed, "private_root", side_effect=lambda _path: MemoryRoot(state)):
            with self.assertRaises(RuntimeError) as caught:
                C.provider_file_bytes(owner, MemoryRoot(state), "worker-return.json", 3, 1000.0, owner.end)
        self.assertIs(caught.exception, first)
        self.assertTrue(owner.unknown)
        self.assertEqual(state["readers"][0].close_calls, 1)

    def test_raw4_copy_retains_all_bytes_separate_identities_and_copy_rereads(self):
        source, target = memory_state("/model/source4", 10), memory_state("/model/copy4", 30)
        refs, raws = [], []
        for number, (slot, name, _maximum) in enumerate(READBACK.ORIGINAL_FILES, 11):
            raw = b"p" * (C.MIB + 1) if slot == "packet" else b"" if slot == "stderr" else slot.encode("ascii")
            source["files"][name] = {"raw": raw, "identity": (1, number)}
            refs.append((slot, OUTER.FileReference(len(raw), H.digest(raw), (1, number))))
            raws.append((slot, raw))
        # DATA-only synthetic acknowledgement. No decoder/native acceptance is
        # claimed by this copy test; those prerequisites are caller obligations.
        result = READBACK.ProviderReadback(None, SimpleNamespace(files=tuple(refs)), b"MODEL", tuple(raws), 150 * NS)
        states = {str(state["path"]): state for state in (source, target)}
        owner = MemoryOwner()
        with patch.object(C, "ProviderEpisode", MemoryOwner), patch.object(C.seed, "private_root",
                side_effect=lambda path: MemoryRoot(states[str(path)])):
            copied = C.copy_provider_originals(owner, MemoryRoot(source), MemoryRoot(target), result)
        self.assertEqual([row["slot"] for row in copied], [row[0] for row in READBACK.ORIGINAL_FILES])
        self.assertEqual(len({tuple(row["originalIdentity"]) for row in copied} |
            {tuple(row["copyIdentity"]["identity"]) for row in copied}), 8)
        self.assertEqual({name: row["raw"] for name, row in source["files"].items()},
                         {name: row["raw"] for name, row in target["files"].items()})
        self.assertEqual(len(source["readers"]), 4)
        self.assertEqual(len(target["readers"]), 4)
        self.assertTrue(all(stream.closed for stream in source["readers"] + target["readers"] + target["writers"]))

    def test_raw4_receipt_rejects_cross_slot_original_to_copy_alias(self):
        state, declarations = memory_state(), []
        for index, (slot, name, _maximum) in enumerate(READBACK.ORIGINAL_FILES):
            entry = {"raw": slot.encode("ascii"), "identity": (1, 30 + index)}
            state["files"][name] = entry
            info = SEED.PosixInfo(entry["identity"], False, len(entry["raw"]), 0o100600, 1000, 1, 1, 1)
            declarations.append({"slot": slot, "name": name, "bytes": len(entry["raw"]), "sha256": H.digest(entry["raw"]),
                "originalIdentity": [1, 10 + index], "copyIdentity": SEED._info_binding(info)})
        declarations[1]["originalIdentity"] = declarations[0]["copyIdentity"]["identity"]
        owner = MemoryOwner()
        with patch.object(C.seed, "private_root", side_effect=lambda _path: MemoryRoot(state)), \
                patch.object(C, "seed_names", return_value=list(state["files"])):
            with self.assertRaisesRegex(C.ControllerError, "ORIGINAL_ALIAS"):
                C.read_native_provider_originals(owner, MemoryRoot(state), declarations, 1000.0, owner.end)

    def test_owned_stdin_has_distinct_known_writer_close_readback_and_retained_position_zero(self):
        state, owner, raw = memory_state(), MemoryOwner(), b'{"model":"not authority"}\n'
        with patch.object(C.time, "monotonic", return_value=1.0), patch.object(C.seed, "private_root",
                side_effect=lambda _path: MemoryRoot(state)):
            reader, borrowed, binding = C.provider_input(owner, MemoryRoot(state), raw)
        if C.os.name == "nt":
            self.assertIs(borrowed, reader)
        else:
            self.assertEqual(borrowed, 12345)
        self.assertEqual(reader.offset, 0)
        self.assertFalse(reader.closed)
        self.assertEqual(reader.read_sizes, [len(raw), 1])
        self.assertEqual(binding, SEED._info_binding(reader.verify()))
        self.assertTrue(state["writers"][0].closed)
        self.assertIsNot(reader, state["writers"][0])
        owner.close_one(reader)
        owner.close()
        self.assertFalse(owner.unknown)


class ModelEpisode:
    def __init__(self):
        self.resources, self.errors = [], []
        self.unknown, self.original, self.calls = False, None, 0
        self.after_end = lambda: None

    def end(self):
        self.calls += 1
        self.after_end()
        if self.unknown or self.original is not None:
            raise RuntimeError("MODEL_EPISODE_FAILED")
        return 1000.0

    def hold(self, label, value):
        if any(row[1] is value for row in self.resources):
            raise AssertionError("DUPLICATE_MODEL_RESOURCE")
        self.resources.append([label, value, False])
        return value

    def acquire(self, label, factory):
        return self.hold(label, factory())

    def error(self, label, error, unknown=False):
        self.errors.append((label, error))
        self.unknown |= unknown
        if self.original is None:
            self.original = error

    def close_one(self, value):
        row = next(row for row in self.resources if row[1] is value)
        if row[2]:
            return
        row[2] = True
        try:
            value.close()
        except BaseException as error:
            self.error(row[0] + "-close", error, unknown=True)


class ModelStream(io.BytesIO):
    def __init__(self, raw, close_error=None):
        super().__init__(raw)
        self.close_calls, self.close_error = 0, close_error

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        super().close()


@contextmanager
def public_transport(raw, *, stream_close=None, connection_close=None, makefile_error=None):
    """Real stdlib HTTP parser over memory, with no socket/native side effects."""
    state = SimpleNamespace(stream=ModelStream(raw, stream_close), closes=0, requests=[], timeouts=[])

    class Socket:
        def makefile(self, mode):
            if makefile_error is not None:
                raise makefile_error
            if mode != "rb":
                raise AssertionError("MODEL_BINARY_SOCKET_ONLY")
            return state.stream

        def settimeout(self, timeout):
            state.timeouts.append(timeout)

    class Connection:
        def __init__(self, host, *, timeout, context):
            if (host, timeout, context) != ("raw.githubusercontent.com", 5, "MODEL_TLS"):
                raise AssertionError("MODEL_FIXED_PUBLIC_ORIGIN")
            self.sock = Socket()

        def request(self, method, path, *, headers):
            state.requests.append((method, path, headers))

        def getresponse(self):
            response = self.response_class(self.sock, method="GET")
            try:
                response.begin()
                if response.will_close:
                    self.close()
                return response
            except BaseException:
                response.close()
                raise

        def close(self):
            state.closes += 1
            if connection_close is not None:
                raise connection_close

    body = b"MODEL_PUBLIC_BUNDLE"
    contract = {"bundle": {"url": "https://raw.githubusercontent.com/actions/cache/" + "a" * 40 + "/dist/restore-only/index.js",
        "bytes": len(body), "sha256": H.digest(body), "basename": "provider.cjs"}}
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {}, clear=True))
        stack.enter_context(patch.object(H.http.client, "HTTPSConnection", Connection))
        stack.enter_context(patch.object(H.ssl, "create_default_context", return_value="MODEL_TLS"))
        stack.enter_context(patch.object(H.time, "monotonic", return_value=1.0))
        stack.enter_context(patch.object(CACHE, "restore_provider_contract", return_value=contract))
        yield state, body


def public_reply(body=b"MODEL_PUBLIC_BUNDLE", status=200, fields=None):
    fields = fields if fields is not None else [("Content-Length", str(len(body)))]
    return ("HTTP/1.1 " + str(status) + " MODEL\r\n" + "".join(name + ": " + value + "\r\n"
        for name, value in [*fields, ("Connection", "close")]) + "\r\n").encode("ascii") + body


class PublicBundleControls(unittest.TestCase):
    def test_fixed_public_get_hash_parser_eof_and_all_real_model_closes(self):
        episode = ModelEpisode()
        with public_transport(public_reply()) as (state, body):
            self.assertEqual(H.acquire_provider_bundle(episode, {}), body)
            self.assertEqual(state.closes, 1)
            self.assertEqual(state.stream.close_calls, 1)
            self.assertEqual(len(state.requests), 1)
            self.assertEqual(state.requests[0][0], "GET")
            self.assertEqual(state.requests[0][2], {"Accept": "application/octet-stream", "Accept-Encoding": "identity",
                                                   "Connection": "close"})
            self.assertTrue(all(row[2] for row in episode.resources))
            self.assertFalse(episode.unknown)

    def test_fixed_public_chunked_parser_and_eof_are_supported_without_retry(self):
        body = b"MODEL_PUBLIC_BUNDLE"
        wire = (format(len(body), "x").encode() + b"\r\n" + body + b"\r\n0\r\n\r\n")
        with public_transport(public_reply(wire, fields=[("Transfer-Encoding", "chunked")])) as (state, _body):
            self.assertEqual(H.acquire_provider_bundle(ModelEpisode(), {}), body)
            self.assertEqual((state.closes, state.stream.close_calls, len(state.requests)), (1, 1, 1))

    def test_public_redirect_duplicate_folded_encoding_and_length_fields_fail_closed(self):
        replies = [public_reply(status=302), public_reply(fields=[("Content-Length", "18"), ("content-length", "18")]),
            public_reply(fields=[("Content-Length", "18"), ("Transfer-Encoding", "chunked")]),
            public_reply(fields=[("Content-Length", "18"), ("Content-Encoding", "gzip")]),
            public_reply(fields=[("Content-Length", "20")]), public_reply(fields=[("Location", "https://other.invalid/")]),
            b"HTTP/1.1 200 MODEL\r\nContent-Length: 18\r\n folded\r\n\r\nMODEL_PUBLIC_BUNDLE"]
        for raw in replies:
            with self.subTest(size=len(raw)), public_transport(raw) as (state, _body):
                with self.assertRaises((I.AdmissionError, B.BudgetError, H.http.client.HTTPException)):
                    H.acquire_provider_bundle(ModelEpisode(), {})
                self.assertEqual(len(state.requests), 1)

    def test_public_short_excess_and_changed_body_fail_instead_of_hash_substitution(self):
        for body in (b"MODEL", b"MODEL_PUBLIC_BUNDLf", b"MODEL_PUBLIC_BUNDLEextra"):
            with public_transport(public_reply(body, fields=[])) as (state, _body):
                with self.assertRaises(I.AdmissionError):
                    H.acquire_provider_bundle(ModelEpisode(), {})
                self.assertEqual(len(state.requests), 1)

    def test_implicit_parser_or_connection_close_failure_is_preserved_without_raw_retry(self):
        for field in ("stream_close", "connection_close"):
            failure = RuntimeError("MODEL_IMPLICIT_CLOSE_FAILED")
            episode = ModelEpisode()
            with public_transport(public_reply(), **{field: failure}) as (state, _body):
                with self.assertRaises(RuntimeError) as caught:
                    H.acquire_provider_bundle(episode, {})
                self.assertIs(caught.exception, failure)
                self.assertTrue(episode.unknown)
                self.assertEqual(state.closes, 1)
                self.assertEqual(state.stream.close_calls, 1)

    def test_partially_constructed_response_is_owned_and_not_returned(self):
        failure = RuntimeError("MODEL_MAKEFILE_FAILED")
        episode = ModelEpisode()
        with public_transport(public_reply(), makefile_error=failure) as (state, _body):
            with self.assertRaises(RuntimeError) as caught:
                H.acquire_provider_bundle(episode, {})
            self.assertIs(caught.exception, failure)
            self.assertTrue(episode.unknown)
            self.assertEqual([row[0] for row in episode.resources], ["public-bundle-connection", "public-bundle-response"])
            self.assertTrue(all(row[2] for row in episode.resources))
            self.assertEqual(state.closes, 1)

    def test_public_acquisition_refuses_ambient_service_and_api_credentials(self):
        for name in (*H.provider_environment.SERVICE_FIELDS, B.TOKEN_ENV):
            with public_transport(public_reply()) as (state, _body), patch.dict(os.environ, {name: "SYNTHETIC"}):
                with self.assertRaises(I.AdmissionError):
                    H.acquire_provider_bundle(ModelEpisode(), {})
                self.assertEqual(state.requests, [])

    def test_public_late_result_is_not_returned_even_after_exact_bytes(self):
        episode = ModelEpisode()
        failure = RuntimeError("MODEL_ORIGINAL_DEADLINE")
        with public_transport(public_reply()) as (state, _body):
            def late():
                if state.stream.closed:
                    raise failure
            episode.after_end = late
            with self.assertRaises(RuntimeError) as caught:
                H.acquire_provider_bundle(episode, {})
            self.assertIs(caught.exception, failure)
            self.assertEqual((state.closes, state.stream.close_calls), (1, 1))


@contextmanager
def local_source_model(bound, *, checker_error=None, close_error=None, unknown_close=False):
    """Only the fixed runtime dispatch/retirement seam; no native owner is made."""
    trace, owner = [], ModelEpisode()
    supplier = SimpleNamespace(closed=False, unknown=False)
    check = Mock(side_effect=lambda: trace.append("check"))
    supplier.native_host_matches_actions = Mock(side_effect=lambda: trace.append("host"))

    def finalize(_original):
        trace.append("close")
        supplier.unknown = unknown_close or close_error is not None
        supplier.closed = not supplier.unknown
        if close_error is not None:
            raise close_error

    def checked(_root, _bound, *, query_runner, check):
        trace.append("checker")
        if checker_error is not None:
            raise checker_error
        return bound

    supplier._finalize = Mock(side_effect=finalize)
    with patch.object(H.query, "NativeGitQueries", return_value=supplier) as factory, \
            patch.object(M.A, "check_local_worker", side_effect=checked) as checker:
        yield SimpleNamespace(owner=owner, supplier=supplier, factory=factory, checker=checker, check=check,
            trace=trace, destination=Path("/model/local-source"), end=1000.0)


def bound_manifest_fixture(values):
    """Reuse DATA builders, never earlier tests or a crypto/current entrypoint."""
    bound = values["bound"]
    budget = B.derive_initial_retained(bound, originals(values), "a" * 32)
    raw, context, start = crypto_fixture(values, budget)
    request = H.crypto_request_data(I.encoded(raw), bound, context, budget, start, "export")
    recipient = SimpleNamespace(fingerprint=bound.fingerprint, key_sha256=bound.key_sha256,
                                expires_at=bound.expires_at)
    return request, recipient


class LazyImportBoundaryControls(unittest.TestCase):
    def test_local_source_calls_original_checker_and_closes_once(self):
        with fixture() as values, local_source_model(values["bound"]) as model:
            self.assertNotIn("originals", vars(H))
            returned = H.check_local(model.owner, values["bound"], model.destination, model.check, end=model.end)
            self.assertIs(returned, values["bound"])
            model.factory.assert_called_once_with(H.ROOT, model.destination, check_cancel=model.check,
                                                 owner_deadlines=(model.end, model.end))
            model.supplier.native_host_matches_actions.assert_called_once_with()
            model.checker.assert_called_once_with(H.ROOT, values["bound"], query_runner=model.supplier, check=model.check)
            model.supplier._finalize.assert_called_once_with(None)
            self.assertEqual(model.trace, ["check", "host", "checker", "check", "close", "check"])
            self.assertTrue(model.supplier.closed)
            self.assertFalse(model.supplier.unknown or model.owner.unknown)
            self.assertEqual(model.owner.errors, [])
            self.assertNotIn("originals", vars(H))

    def test_lazy_import_failure_keeps_original_error_and_retires_supplier(self):
        with fixture() as values:
            for close_fails in (False, True):
                first, second = ImportError("MODEL_FIXED_IMPORT_REFUSED"), RuntimeError("MODEL_FINALIZER_REFUSED")
                with self.subTest(close_fails=close_fails), local_source_model(values["bound"],
                        close_error=second if close_fails else None) as model:
                    real_import, imports = builtins.__import__, []

                    def refused(name, globals=None, locals=None, fromlist=(), level=0):
                        if name == "hosted_initial_ordinary_originals":
                            imports.append(name)
                            model.trace.append("import-refused")
                            raise first
                        return real_import(name, globals, locals, fromlist, level)

                    with patch.object(builtins, "__import__", refused), self.assertRaises(ImportError) as caught:
                        H.check_local(model.owner, values["bound"], model.destination, model.check, end=model.end)
                    self.assertIs(caught.exception, first)
                    self.assertEqual(imports, ["hosted_initial_ordinary_originals"])
                    model.supplier.native_host_matches_actions.assert_called_once_with()
                    model.checker.assert_not_called()
                    model.supplier._finalize.assert_called_once_with(first)
                    self.assertEqual(model.trace, ["check", "host", "import-refused", "close"])
                    self.assertEqual(model.owner.unknown, close_fails)
                    self.assertEqual(model.supplier.closed, not close_fails)
                    self.assertEqual(model.owner.errors, [("initial-local-source-close", first)] if close_fails else [])

    def test_local_checker_failure_remains_failure_after_close(self):
        with fixture() as values:
            for unknown_close in (False, True):
                failure = RuntimeError("MODEL_LOCAL_SOURCE_REFUSED")
                with self.subTest(unknown_close=unknown_close), local_source_model(values["bound"],
                        checker_error=failure, unknown_close=unknown_close) as model:
                    with self.assertRaises(RuntimeError) as caught:
                        H.check_local(model.owner, values["bound"], model.destination, model.check, end=model.end)
                    self.assertIs(caught.exception, failure)
                    model.checker.assert_called_once_with(H.ROOT, values["bound"], query_runner=model.supplier,
                                                         check=model.check)
                    model.supplier._finalize.assert_called_once_with(failure)
                    self.assertEqual(model.trace, ["check", "host", "checker", "close"])
                    self.assertEqual(model.owner.unknown, unknown_close)
                    self.assertEqual(model.supplier.closed, not unknown_close)
                    self.assertEqual(model.owner.errors,
                        [("initial-local-source-close", failure)] if unknown_close else [])

    def test_manifest_uses_direct_original_checker_and_preserves_binding(self):
        with fixture() as values:
            request, recipient = bound_manifest_fixture(values)
            query_runner, check = object(), Mock()
            expected = H.manifest_data(request)
            self.assertNotIn("originals", vars(H))
            with patch.object(M.A, "check_local_worker", return_value=values["bound"]) as checker, \
                    patch.object(H, "manifest_data", wraps=H.manifest_data) as manifest:
                result = C.ordinary._bound_initial_ordinary_manifest(recipient, root=ROOT, request=request,
                    query_runner=query_runner, check=check)
            checker.assert_called_once_with(ROOT, values["bound"], query_runner=query_runner, check=check)
            check.assert_called_once_with()
            manifest.assert_called_once_with(request)
            self.assertEqual(result, expected)
            self.assertEqual(result["schema"], 5)
            self.assertEqual(result["initialOrdinary"]["identitySha256"], H.digest(values["bound"].record))
            self.assertIs(result["initialOrdinary"]["samplePackagingRequired"], False)
            self.assertEqual(result["initialOrdinary"]["privateOwnerInspection"], "NOT_PERFORMED_BY_WORKFLOW")

    def test_manifest_checker_refusal_and_recipient_mismatch_fail_closed(self):
        with fixture() as values:
            request, recipient = bound_manifest_fixture(values)
            query_runner, check = object(), Mock()
            original = RuntimeError("MODEL_MANIFEST_SOURCE_REFUSED")
            with patch.object(M.A, "check_local_worker", side_effect=original) as checker, \
                    patch.object(H, "manifest_data", wraps=H.manifest_data) as manifest:
                with self.assertRaises(RuntimeError) as caught:
                    C.ordinary._bound_initial_ordinary_manifest(recipient, root=ROOT, request=request,
                        query_runner=query_runner, check=check)
            self.assertIs(caught.exception, original)
            checker.assert_called_once_with(ROOT, values["bound"], query_runner=query_runner, check=check)
            manifest.assert_not_called()
            check.assert_not_called()
            for changes in ({"fingerprint": "F" * 40}, {"key_sha256": "f" * 64},
                    {"expires_at": recipient.expires_at - 1}):
                changed = SimpleNamespace(**{**vars(recipient), **changes})
                with self.subTest(changes=changes), \
                        patch.object(M.A, "check_local_worker", return_value=values["bound"]) as checker, \
                        patch.object(H, "manifest_data", wraps=H.manifest_data) as manifest:
                    with self.assertRaises(C.ordinary.hosted_evidence.EvidenceError):
                        C.ordinary._bound_initial_ordinary_manifest(changed, root=ROOT, request=request,
                            query_runner=query_runner, check=check)
                checker.assert_called_once_with(ROOT, values["bound"], query_runner=query_runner, check=check)
                manifest.assert_not_called()
                check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
