#!/usr/bin/env python3
"""Recipient CHILD offline controls, not hosted/GPG/parent qualification.

Tiny actual ordinary-UID POSIX files; native/Git/GPG/host/clock suppliers are
explicit models. No key operation, child launch, network, download or build.
Existing original-input fixture builders are reused, not their test methods.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import importlib.util
import io
import os
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bootstrap_recipient_original_models",
    Path(__file__).with_name("hosted-cache-bootstrap-origin-test.py"))
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)
S, O = C.S, C.O


class RecipientModels(C.OfflineCase):
    def setUp(self):
        super().setUp()
        self.assertNotEqual(os.geteuid(), 0, "Tiny file controls require an actual ordinary UID")
        self.stack.enter_context(patch.object(S, "QUARANTINE", []))
        self.stack.enter_context(patch.object(S.query, "QUARANTINE", []))
        self.stack.enter_context(patch.object(S.diagnostics, "_QUARANTINE", []))
        for module, name in ((S.posix, "_gpg"), (S.diagnostics, "_gpg"), (S.diagnostics, "validate_recipient")):
            self.stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_REAL_GPG")))
        self.temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="bootstrap-recipient-offline-"))
        self.parent = Path(self.temporary)
        self.path = self.parent / "p2pkit-cache-originals-123-1-desktop-linux-x64"
        self.session = self.path.with_name(self.path.name + "-productive")
        for base in (self.path, self.session):
            base.mkdir(mode=0o700)
        for name in ("admission", "service"):
            (self.path / name).mkdir(mode=0o700)
        for name in S.RECIPIENT_DIRECTORIES:
            (self.session / name).mkdir(mode=0o700)
        self.phase = self.session / "recipient-validation"
        self.event = self.parent / "event.json"
        self.put(self.event, self.admitted.original_event)
        self.put_admission(self.path / "admission", self.admitted)
        self.original = {"schema": 1, "scope": S.CONTEXT_SCOPE,
            "prelude": O.prelude(O.clocks.Reading(self.clock, 1000 * O.NS)),
            "selection": "desktop-linux-x64", "cacheCohort": O.parse(self.admitted.record)["cacheCohort"],
            "source": O.parse(self.admitted.record)["source"], "github": O.parse(self.admitted.record)["github"],
            "root": str(ROOT), "session": str(self.path), "job": "a" * 32, "inheritedContext": {},
            "runnerName": C.RUNNER, "admissionSha256": O.digest(self.admitted.record),
            "admissionReturnSha256": "b" * 64, "admissionReturnedNs": 1000 * O.NS + 1,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        original_raw = O.encoded(self.original)
        self.put(self.path / "context.json", original_raw)
        service_start = self.start_record(S.PHASE_SCOPE, original_raw, self.original, self.path,
            "e" * 32, 1000 * O.NS + 2, 1045 * O.NS + 2, 1090 * O.NS + 2, S.command)
        self.put(self.path / "service/start.json", O.encoded(service_start))
        responses = {name: C.response(self.admitted, self.clock, name, body, start=(1001 + index) * O.NS)
                     for index, (name, body) in enumerate(C.service_bodies(self.admitted, self.clock).items())}
        for name, raw in responses.items():
            self.put(self.path / "service" / (name + ".json"), raw)
        self.proposal = S.allocation.derive(self.admitted, responses, "e" * 32, self.clock, C.RUNNER)
        proposal_raw = O.encoded(self.proposal)
        self.put(self.session / "allocation.json", proposal_raw)
        self.identities = {name: list(S.posix._identity(path)) for name, path in {
            "original": self.path, "session": self.session,
            **{name: self.session / name for name in S.RECIPIENT_DIRECTORIES}}.items()}
        record = O.parse(self.admitted.record)
        self.context = {"schema": 1, "scope": S.RECIPIENT_CONTEXT_SCOPE, "profile": "cache-bootstrap",
            **{name: record[name] for name in ("selection", "cacheCohort", "source", "github")},
            "root": str(ROOT), "session": str(self.session), "originalSession": str(self.path),
            "originalContextSha256": O.digest(original_raw), "admissionSha256": O.digest(self.admitted.record),
            "proposalSha256": O.digest(proposal_raw), "clock": O.clock_value(self.clock), "job": "c" * 32,
            "inheritedContext": {}, "runnerName": C.RUNNER, "previousTransitionSha256": "d" * 64,
            "previousCheckedNs": 1180 * O.NS, "directories": self.identities,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.minimum = 1191 * O.NS
        self.reset_context()
        env = {**self.env, "GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": str(self.event),
               "RUNNER_TEMP": str(self.parent), "PATH": os.defpath, **self.start["inheritedContext"]}
        with patch.dict(os.environ, env, clear=True):
            environment = S.recipient_environment(self.session)
        self.stack.enter_context(patch.dict(os.environ, environment, clear=True))
        self.nanoseconds = 1200 * O.NS
        self.queries, self.validations, self.owners = [], [], []
        self.query_failure = self.query_finalize_failure = self.gpg_failure = None
        self.gpg_after = lambda result: result
        case = self

        class NativeQueryModel:
            def __init__(self, root, directory, *, check_cancel, owner_deadlines):
                case.assertEqual(root, ROOT)
                self.path, self.check, self.deadlines = Path(directory), check_cancel, owner_deadlines
                self.work_ns, self.final_ns = case.owners[-1].work_limit, case.owners[-1].final_limit
                self.unknown, self.closed = False, False
                case.queries.append(self)
                self.calls = ["construct"]
                self.path.mkdir(mode=0o700)
                self.check()

            def native_host_matches_actions(self):
                self.calls.append("native-model")
                self.check()
                if case.query_failure is not None:
                    raise case.query_failure

            def retain_admission(self, admitted):
                self.calls.append("retain")
                self.check()
                case.put_admission(self.path, admitted)

            def _finalize(self, original):
                self.calls.append("finalize")
                S.posix._deadline(self.deadlines[1])
                self.closed = True
                case.put(self.path / "session-result.json", O.encoded({"schema": 1,
                    "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": "f" * 32, "queries": [],
                    "result": "READY_FOR_CALLER_SEAL" if original is None else "FAILED",
                    "retirement": "KNOWN", "firstError": None, "errors": [], "readbacks": []}))
                if case.query_finalize_failure is not None:
                    raise case.query_finalize_failure

        def admission(root, *, query_runner, expected):
            self.assertEqual(root, ROOT)
            self.assertIs(query_runner, self.queries[-1])
            self.assertEqual(expected, self.admitted)
            query_runner.calls.append("identity-model")
            return replace(self.admitted)

        original_init = S.Owner.__init__
        def owner_init(owner, *args, **kwargs):
            original_init(owner, *args, **kwargs)
            self.owners.append(owner)

        self.stack.enter_context(patch.object(S.Owner, "__init__", owner_init))
        self.stack.enter_context(patch.object(S.query, "NativeGitQueries", NativeQueryModel))
        self.stack.enter_context(patch.object(S.bootstrap, "admit", side_effect=admission))
        self.stack.enter_context(patch.object(S.posix, "validate_recipient", side_effect=self.validate))

    @staticmethod
    def put(path, raw):
        path.write_bytes(raw)
        path.chmod(0o600)

    def put_admission(self, path, admitted):
        for name, raw in (("admission.json", admitted.record), ("original-event.json", admitted.original_event),
                          ("original-policy.json", admitted.original_policy), ("recipient-public.asc", admitted.public_key)):
            self.put(path / name, raw)

    @staticmethod
    def start_record(scope, context_raw, context, path, invocation, began, work, final, command):
        inherited = S.processes.ownership_environment(context["inheritedContext"], context["job"], invocation,
            str(path), str(path / "control-home"), allow_new_context=True)
        return {"schema": 1, "scope": scope, "contextSha256": O.digest(context_raw),
            "argv": command(O.digest(context_raw)), "cwd": str(ROOT), "role": context["cacheCohort"]["role"],
            "job": context["job"], "invocation": invocation, "state": str(path), "home": str(path / "control-home"),
            "inheritedContext": {name: inherited[name] for name in S.query._CONTEXT}, "startedNs": began,
            "workEndNs": work, "finalEndNs": final, "exitCode": None, "launchAttempted": False,
            "scopeAttempted": False, "retirement": "UNKNOWN"}

    def reset_context(self):
        raw = O.encoded(self.context)
        self.hash = O.digest(raw)
        self.start = self.start_record(S.RECIPIENT_START_SCOPE, raw, self.context, self.session, "9" * 32,
            1190 * O.NS, min(1430 * O.NS, self.proposal["phaseFencesNs"]["recipient-validation"]),
            min(1475 * O.NS, self.proposal["phaseFencesNs"]["recipient-final"]), S.recipient_command)
        self.put(self.session / "recipient-context.json", raw)
        self.put(self.phase / "start.json", O.encoded(self.start))

    def validate(self, key, fingerprint, work):
        self.assertEqual(key, self.session / "recipient-admission/recipient-public.asc")
        self.assertEqual(fingerprint, self.admitted.fingerprint)
        self.assertEqual(work, self.session / "crypto")
        self.assertTrue(self.queries[-1].closed)
        self.assertEqual(S.query._inherited_context(), self.start["inheritedContext"])
        self.validations.append((key, fingerprint, work))
        (work / "gnupg").mkdir(mode=0o700)
        (work / "tmp").mkdir(mode=0o700)
        self.put(work / "model-original.txt", b"SYNTHETIC SUPPLIER ORIGINAL; NOT GPG EXECUTION\n")
        if self.gpg_failure is not None:
            raise self.gpg_failure
        recipient = S.posix.Recipient(work, work / "gnupg", Path(sys.executable), fingerprint.upper(),
            "AB" * 20, self.admitted.expires_at + 1000, O.digest(key.read_bytes()), S.posix._identity(work))
        return self.gpg_after(recipient)

    def run_child(self, cancelled=None):
        return S.recipient_child(self.hash, self.minimum, [] if cancelled is None else cancelled)

    def assert_closed(self):
        self.assertTrue(self.owners)
        for owner in self.owners:
            self.assertTrue(owner.closed)
            self.assertFalse(owner.unknown)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))

    def reject_before_supplier(self, reason=None):
        with self.assertRaisesRegex(Exception, reason or "BOOTSTRAP"):
            self.run_child()
        self.assertEqual(self.validations, [])
        self.assert_closed()

    def test_actual_child_wrapper_calls_modeled_query_and_validator_then_closes_before_ack(self):
        originals = {str(path): path.read_bytes() for base in (self.path, self.session)
                     for path in base.rglob("*") if path.is_file()}
        ack, window, end = self.run_child()
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(self.queries[0].calls, ["construct", "native-model", "identity-model", "retain", "finalize"])
        self.assertEqual(len(self.validations), 1)
        self.assertEqual(len(self.owners), 2)
        self.assertTrue(self.owners[0].fence.metadata)
        self.assertFalse(self.owners[1].fence.metadata)
        self.assertIs(self.owners[0].first, self.owners[1].first)
        self.assertIsNot(self.owners[0], self.owners[1])
        self.assertLessEqual(self.owners[0].local_end, window.local_start + 45)
        self.assertLessEqual(self.owners[1].local_end, window.local_start + 210)
        self.assertEqual(window.final, min(window.first + 210 * O.NS, self.start["workEndNs"]))
        self.assertEqual(end, window.final)
        self.assert_closed()
        terminal_raw = (self.phase / "child-result.json").read_bytes()
        terminal = O.parse(terminal_raw)
        self.assertEqual(terminal["childResourceClose"], "PENDING_CLOSE")
        self.assertNotIn("closedNs", terminal)
        self.assertEqual(ack["terminalSha256"], O.digest(terminal_raw))
        self.assertGreaterEqual(ack["closedNs"], terminal["completedNs"])
        self.assertEqual(ack["childResourceClose"], "KNOWN_RESOURCE_CLOSE_ONLY")
        for value in (terminal, ack):
            self.assertEqual(value["parentRetirement"], "NOT_OBSERVED_HERE")
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
            self.assertIs(value["exportSaveAuthority"], False)
        self.assertEqual(originals, {name: Path(name).read_bytes() for name in originals})
        self.assertEqual((self.phase / "child-result.json").stat().st_mode & 0o777, 0o600)

    def test_query_pair_remains_inside_original_child_and_fixed_query_bounds(self):
        _, window, _ = self.run_child()
        work, final = self.queries[0].deadlines
        self.assertLess(work, final)
        self.assertEqual(self.queries[0].final_ns - self.queries[0].work_ns, 45 * O.NS)
        self.assertLessEqual(work, self.queries[0].work_ns / O.NS)
        self.assertLessEqual(final, self.queries[0].final_ns / O.NS)
        self.assertLessEqual(final, window.local_end)

    def test_metadata_raw45_expiry_cannot_be_repaired_by_good_local_clock(self):
        original = S.Owner.read
        def read(owner, *args, **kwargs):
            value = original(owner, *args, **kwargs)
            self.nanoseconds = owner.first.nanoseconds + 45 * O.NS
            return value
        with patch.object(S.time, "monotonic", return_value=1200.0), patch.object(S.Owner, "read", read):
            self.reject_before_supplier("RECIPIENT_CHILD_EXPIRED")
        self.assertEqual(len(self.owners), 1)
        self.assertGreaterEqual(self.owners[0].fence.last, self.owners[0].first.nanoseconds + 45 * O.NS)

    def test_metadata_local45_expiry_cannot_be_repaired_by_good_raw_clock(self):
        self.stack.enter_context(patch.object(S.time, "monotonic", return_value=1200.0))
        original = S.Owner.read
        def read(owner, *args, **kwargs):
            value = original(owner, *args, **kwargs)
            S.time.monotonic.return_value = 1245.0
            return value
        with patch.object(S.Owner, "read", read):
            self.reject_before_supplier("deadline")
        self.assertEqual(len(self.owners), 1)

    def test_original_launch_floor_rejects_first_reading_before_later_recovery(self):
        self.minimum = 1200 * O.NS + 2000
        with self.assertRaisesRegex(O.OriginError, "PRECEDES_LAUNCH"):
            self.run_child()
        self.assertEqual(self.owners, [])

    def test_child210_rejects_late_supplier_zero_without_renewal(self):
        def late(result):
            self.nanoseconds = self.owners[1].fence.final
            return result
        self.gpg_after = late
        with self.assertRaisesRegex(O.OriginError, "RECIPIENT_CHILD_EXPIRED"):
            self.run_child()
        self.assertEqual(len(self.validations), 1)
        self.assertFalse((self.phase / "child-result.json").exists())
        self.assert_closed()
        self.assertGreaterEqual(self.owners[1].fence.last, self.owners[1].fence.final)

    def test_original_parent_work_end_only_shortens_child_never_uses_final45(self):
        self.nanoseconds = 1420 * O.NS
        ack, window, _ = self.run_child()
        self.assertEqual(window.final, 1430 * O.NS)
        self.assertLess(window.final, window.first + 210 * O.NS)
        self.assertLess(ack["closedNs"], self.start["workEndNs"])

    def test_first_reading_at_original_parent_work_end_refuses_before_validator(self):
        self.nanoseconds = self.start["workEndNs"]
        self.reject_before_supplier("PARENT_FENCES")

    def test_mismatched_context_hash_stops_before_query_or_gpg(self):
        self.hash = "1" * 64
        self.reject_before_supplier("CONTEXT_HASH_CHANGED")
        self.assertEqual(self.queries, [])

    def test_changed_allocation_cannot_renew_service_job_end(self):
        value = copy.deepcopy(self.proposal)
        value["proposedJobEndNs"] += O.NS
        raw = O.encoded(value)
        self.put(self.session / "allocation.json", raw)
        self.context["proposalSha256"] = O.digest(raw)
        self.reset_context()
        self.reject_before_supplier("ALLOCATION_PROPOSAL_CHANGED")

    def test_changed_original_response_even_reserialization_refuses(self):
        path = self.path / "service/jobs.json"
        self.put(path, path.read_bytes() + b" ")
        self.reject_before_supplier("ALLOCATION_PROPOSAL_CHANGED")

    def test_supplied_directory_identity_boolean_is_not_an_integer(self):
        self.context["directories"]["session"][0] = True
        self.reset_context()
        self.reject_before_supplier("RECIPIENT_CONTEXT")

    def test_predecessor_highwater_cannot_move_before_original_service_response(self):
        self.context["previousCheckedNs"] = 1000 * O.NS
        self.reset_context()
        self.reject_before_supplier("ORIGIN_INTEGER")

    def test_ordinary_desktop_identity_is_not_configuration_bootstrap(self):
        self.context["profile"] = "desktop"
        self.reset_context()
        self.reject_before_supplier("RECIPIENT_CONTEXT")

    def test_parent_argv_cannot_select_help_or_arbitrary_commands(self):
        self.start["argv"] = ["help"]
        self.put(self.phase / "start.json", O.encoded(self.start))
        self.reject_before_supplier("RECIPIENT_PRELAUNCH")

    def test_original_start_cannot_claim_success_or_retirement(self):
        self.start["exitCode"] = 0
        self.start["retirement"] = "KNOWN"
        self.put(self.phase / "start.json", O.encoded(self.start))
        self.reject_before_supplier("RECIPIENT_PRELAUNCH")

    def test_changed_native_invocation_with_consistent_current_domain_is_not_original_start(self):
        changed = S.processes.ownership_environment({}, self.context["job"], "8" * 32,
            str(self.session), str(self.session / "control-home"), allow_new_context=True)
        with patch.dict(os.environ, changed):
            self.reject_before_supplier("ORIGINAL_NATIVE_CONTEXT")

    def test_partial_native_domain_and_acquisition_token_are_refused(self):
        with patch.dict(os.environ):
            del os.environ[S.processes.DOMAINS_ENV]
            self.reject_before_supplier("PARTIAL_ANCESTOR_CONTEXT")

    def test_acquisition_token_never_reaches_validator(self):
        with patch.dict(os.environ, {O.wire.TOKEN_ENV: C.TOKEN}):
            self.reject_before_supplier("TOKEN_FORBIDDEN")

    def test_ambient_credential_is_not_tolerated_in_child(self):
        with patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC_NOT_A_CREDENTIAL"}):
            self.reject_before_supplier("CHILD_ENVIRONMENT")

    def test_environment_preserves_only_installed_lookup_and_real_domain_not_credentials(self):
        search = os.defpath + os.pathsep + "/opt/synthetic-installed-tools"
        with patch.dict(os.environ, {"PATH": search, "GH_TOKEN": "SYNTHETIC", "JAVA_HOME": "/never-inherited",
                                     "GNUPGHOME": "/never-inherited"}):
            sanitized = S.recipient_environment(self.session)
            service = S.child_environment(self.session)
        self.assertEqual(service["PATH"], os.defpath)
        self.assertEqual(sanitized["PATH"], search)
        self.assertEqual({name: sanitized[name] for name in S.query._CONTEXT}, self.start["inheritedContext"])
        self.assertTrue(all(name not in sanitized for name in ("GH_TOKEN", "JAVA_HOME", "GNUPGHOME")))

    def test_environment_refuses_relative_lookup_and_execution_hooks(self):
        for name, value in (("PATH", ".:/usr/bin"), ("PATH", ":/usr/bin"), ("PYTHONPATH", "/override"),
                            ("JAVA_TOOL_OPTIONS", "-override"), ("GIT_CONFIG_COUNT", "1")):
            with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}), self.assertRaises(Exception):
                S.recipient_environment(self.session)

    def test_query_failure_remains_first_when_query_finalizer_also_fails(self):
        first, second = RuntimeError("SYNTHETIC_QUERY_FIRST"), RuntimeError("SYNTHETIC_QUERY_FINAL")
        self.query_failure, self.query_finalize_failure = first, second
        with self.assertRaises(RuntimeError) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertEqual(self.validations, [])
        self.assert_closed()

    def test_falsey_query_failure_remains_first_when_query_finalizer_also_fails(self):
        class First(RuntimeError):
            def __bool__(self):
                return False
        first = First("SYNTHETIC_FALSEY_QUERY_FIRST")
        self.query_failure, self.query_finalize_failure = first, RuntimeError("SYNTHETIC_QUERY_FINAL")
        with self.assertRaises(First) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertEqual(self.validations, [])
        self.assert_closed()

    def test_success_looking_query_session_cannot_replace_failed_actual_return(self):
        self.query_finalize_failure = RuntimeError("SYNTHETIC_LATE_QUERY_CLOSE")
        with self.assertRaises(RuntimeError) as result:
            self.run_child()
        self.assertIs(result.exception, self.query_finalize_failure)
        self.assertEqual(O.parse((self.session / "recipient-admission/session-result.json").read_bytes())["result"],
                         "READY_FOR_CALLER_SEAL")
        self.assertEqual(self.validations, [])
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_supplier_failure_retains_private_partial_original_and_exact_exception(self):
        first = RuntimeError("SYNTHETIC_PRIVATE_SUPPLIER_FAILURE")
        self.gpg_failure = first
        with self.assertRaises(RuntimeError) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertTrue((self.session / "crypto/model-original.txt").is_file())
        self.assertTrue((self.phase / "child-failure.json").is_file())
        self.assertFalse((self.phase / "child-result.json").exists())
        self.assert_closed()

    def test_supplier_unknown_quarantines_owner_without_new_failure_file(self):
        first = S.diagnostics.WindowsEvidenceError(RuntimeError("SYNTHETIC_NATIVE_FAILURE"), {}, True)
        self.gpg_failure = first
        with self.assertRaises(S.diagnostics.WindowsEvidenceError) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertTrue(self.owners[1].unknown)
        self.assertIn(self.owners[1], S.QUARANTINE)
        self.assertFalse((self.phase / "child-failure.json").exists())
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_unknown_supplier_global_cannot_be_repaired_by_successful_return_object(self):
        def unknown(result):
            S.diagnostics._QUARANTINE.append(object())
            return result
        self.gpg_after = unknown
        with self.assertRaisesRegex(O.OriginError, "RECIPIENT_SUPPLIER_UNKNOWN"):
            self.run_child()
        self.assertTrue(self.owners[1].unknown)
        self.assertIn(self.owners[1], S.QUARANTINE)
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_changed_returned_key_hash_is_not_validated_recipient(self):
        self.gpg_after = lambda result: replace(result, key_sha256="0" * 64)
        with self.assertRaisesRegex(O.OriginError, "KEY_OR_POLICY_CHANGED"):
            self.run_child()
        self.assert_closed()

    def test_returned_key_must_cover_original_policy_expiry(self):
        self.gpg_after = lambda result: replace(result, expires_at=self.admitted.expires_at - 1)
        with self.assertRaisesRegex(O.OriginError, "KEY_OR_POLICY_CHANGED"):
            self.run_child()

    def test_returned_fingerprint_cannot_select_another_key(self):
        self.gpg_after = lambda result: replace(result, fingerprint="CC" * 20)
        with self.assertRaisesRegex(O.OriginError, "KEY_OR_POLICY_CHANGED"):
            self.run_child()

    def test_changed_original_context_after_supplier_return_cannot_rehabilitate(self):
        def change(result):
            path = self.session / "recipient-context.json"
            self.put(path, path.read_bytes() + b" ")
            return result
        self.gpg_after = change
        with self.assertRaisesRegex(O.OriginError, "CONTEXT_HASH_CHANGED"):
            self.run_child()
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_cancellation_after_supplier_return_is_not_success(self):
        cancelled = []
        def cancel(result):
            cancelled.append(signal.SIGTERM)
            return result
        self.gpg_after = cancel
        with self.assertRaises(KeyboardInterrupt):
            self.run_child(cancelled)
        self.assert_closed()

    def test_failed_failure_retention_does_not_replace_supplier_exception(self):
        first = RuntimeError("SYNTHETIC_FIRST_SUPPLIER")
        self.gpg_failure = first
        original = S.Owner.write
        def write(owner, parent, name, *args, **kwargs):
            if name == "child-failure.json":
                raise RuntimeError("SYNTHETIC_FAILED_RETENTION")
            return original(owner, parent, name, *args, **kwargs)
        with patch.object(S.Owner, "write", write), self.assertRaises(RuntimeError) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertTrue(any(row["stage"] == "recipient-failure-retention" for row in self.owners[1].errors))

    def test_post_terminal_resource_close_failure_forbids_ack(self):
        first = OSError("SYNTHETIC_CLOSE_FAILURE")
        original = S.query._PosixDirectory.close
        def close(directory):
            if directory.path == self.session / "crypto" and (self.phase / "child-result.json").exists():
                raise first
            return original(directory)
        with patch.object(S.query._PosixDirectory, "close", close), self.assertRaises(OSError) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertIs(self.owners[1].original, first)
        self.assertTrue((self.phase / "child-result.json").exists())
        self.assertTrue(self.owners[1].unknown)
        self.assertIn(self.owners[1], S.QUARANTINE)
        self.assertFalse((self.phase / "child-failure.json").exists())

    def test_first_metadata_close_failure_stops_handover_and_retains_exact_exception(self):
        first = OSError("SYNTHETIC_METADATA_CLOSE_FAILURE")
        original = S.query._PosixDirectory.close
        def close(directory):
            if directory.path == self.session / "crypto":
                raise first
            return original(directory)
        with patch.object(S.query._PosixDirectory, "close", close), self.assertRaises(OSError) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertEqual(len(self.owners), 1)
        self.assertIs(self.owners[0].original, first)
        self.assertTrue(self.owners[0].closed)
        self.assertTrue(self.owners[0].unknown)
        self.assertIn(self.owners[0], S.QUARANTINE)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.validations, [])
        self.assertFalse((self.phase / "child-failure.json").exists())
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_falsey_supplier_error_precedes_secondary_close_error(self):
        class First(RuntimeError):
            def __bool__(self):
                return False
        first = First("SYNTHETIC_FALSEY_SUPPLIER_FIRST")
        self.gpg_failure = first
        original = S.query._PosixDirectory.close
        def close(directory):
            if directory.path == self.session / "crypto" and (self.phase / "child-failure.json").exists():
                raise OSError("SYNTHETIC_SECONDARY_CLOSE")
            return original(directory)
        with patch.object(S.query._PosixDirectory, "close", close), self.assertRaises(First) as result:
            self.run_child()
        self.assertIs(result.exception, first)
        self.assertIs(self.owners[1].original, first)
        self.assertTrue(self.owners[1].unknown)
        self.assertIn(self.owners[1], S.QUARANTINE)
        self.assertTrue((self.phase / "child-failure.json").exists())
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_guarded_ack_is_after_handler_restoration_but_provisional_until_flush_and_return(self):
        restored, output = [], io.BytesIO()
        signals = (signal.SIGINT, signal.SIGTERM)
        def install(number, handler):
            if handler == "OLD":
                restored.append(number)
        class Output:
            def write(inner, raw):
                self.assertEqual(restored, list(signals))
                self.assert_closed()
                return output.write(raw)
            def flush(inner):
                raise RuntimeError("SYNTHETIC_FLUSH_FAILURE")
        with patch.object(S.signal, "getsignal", return_value="OLD"), patch.object(S.signal, "signal", install), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=Output())), \
                self.assertRaisesRegex(RuntimeError, "FLUSH_FAILURE"):
            S.guarded(lambda cancelled: self.run_child(cancelled))
        ack = O.parse(output.getvalue())
        self.assertEqual(ack["scope"], S.RECIPIENT_ACK_SCOPE)
        self.assertEqual(ack["parentRetirement"], "NOT_OBSERVED_HERE")

    def test_failed_handler_restoration_emits_no_ack_even_after_child_resource_close(self):
        output = io.BytesIO()
        def install(number, handler):
            if handler == "OLD":
                raise RuntimeError("SYNTHETIC_RESTORE_FAILURE")
        with patch.object(S.signal, "getsignal", return_value="OLD"), patch.object(S.signal, "signal", install), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), self.assertRaisesRegex(RuntimeError, "RESTORE_FAILURE"):
            S.guarded(lambda cancelled: self.run_child(cancelled))
        self.assert_closed()
        self.assertEqual(output.getvalue(), b"")
        self.assertTrue((self.phase / "child-result.json").exists())

    def test_falsey_supplier_error_precedes_failed_handler_restoration(self):
        class First(RuntimeError):
            def __bool__(self):
                return False
        first = First("SYNTHETIC_FALSEY_SUPPLIER_FIRST")
        self.gpg_failure = first
        output, restored = io.BytesIO(), []
        def install(number, handler):
            if handler == "OLD":
                restored.append(number)
                raise RuntimeError("SYNTHETIC_RESTORE_FAILURE")
        with patch.object(S.signal, "getsignal", return_value="OLD"), patch.object(S.signal, "signal", install), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), self.assertRaises(First) as result:
            S.guarded(lambda cancelled: self.run_child(cancelled))
        self.assertIs(result.exception, first)
        self.assertEqual(restored, [signal.SIGINT, signal.SIGTERM])
        self.assert_closed()
        self.assertEqual(output.getvalue(), b"")
        self.assertTrue((self.phase / "child-failure.json").exists())
        self.assertFalse((self.phase / "child-result.json").exists())

    def test_first_falsey_handler_restore_error_precedes_later_restore_error(self):
        class First(RuntimeError):
            def __bool__(self):
                return False
        first = First("SYNTHETIC_FALSEY_FIRST_RESTORE")
        output, restored = io.BytesIO(), []
        def install(number, handler):
            if handler == "OLD":
                restored.append(number)
                raise first if len(restored) == 1 else RuntimeError("SYNTHETIC_SECOND_RESTORE")
        with patch.object(S.signal, "getsignal", return_value="OLD"), patch.object(S.signal, "signal", install), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), self.assertRaises(First) as result:
            S.guarded(lambda cancelled: self.run_child(cancelled))
        self.assertIs(result.exception, first)
        self.assertEqual(restored, [signal.SIGINT, signal.SIGTERM])
        self.assert_closed()
        self.assertEqual(output.getvalue(), b"")
        self.assertTrue((self.phase / "child-result.json").exists())

    def test_late_ack_flush_checks_original210_not_a_new_output_allowance(self):
        output = io.BytesIO()
        case = self
        class Output:
            def write(inner, raw):
                return output.write(raw)
            def flush(inner):
                case.nanoseconds = case.owners[1].fence.final
        with patch.object(S.signal, "getsignal", return_value="OLD"), patch.object(S.signal, "signal"), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=Output())), \
                self.assertRaisesRegex(O.OriginError, "RECIPIENT_CHILD_EXPIRED"):
            S.guarded(lambda cancelled: self.run_child(cancelled))
        self.assertTrue(output.getvalue())
        self.assertGreaterEqual(self.owners[1].fence.last, self.owners[1].fence.final)

    def test_windows_return_requires_actual_work_object_and_job_not_equal_copy(self):
        work = SimpleNamespace(path=self.session / "crypto", identity=(7, "a" * 32), verify=lambda: None)
        recipient = S.diagnostics.Recipient(work, Path("/synthetic/gpg.exe"), "b" * 64, work.identity,
            self.admitted.fingerprint.upper(), "CC" * 20, self.admitted.expires_at + 1,
            self.admitted.key_sha256, self.context["job"])
        with patch.object(S, "os", SimpleNamespace(name="nt")):
            record = S._recipient_supplier_record(recipient, work, self.admitted, self.context["job"])
            self.assertEqual(record["job_id"], self.context["job"])
            for changed in (replace(recipient, work=copy.copy(work)), replace(recipient, job_id="0" * 32)):
                with self.assertRaisesRegex(O.OriginError, "NATIVE_RETURN"):
                    S._recipient_supplier_record(changed, work, self.admitted, self.context["job"])


def load_tests(_loader, _tests, _pattern):
    return unittest.defaultTestLoader.loadTestsFromTestCase(RecipientModels)


if __name__ == "__main__":
    unittest.main()
