#!/usr/bin/env python3
"""Focused genuine subprocess/public-key evidence tests; no Gradle or service."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import ci_evidence as E

PUBLIC_FINGERPRINT = "0A996D2BC19518FB50071A95D3FDADA57CFB7E1F"


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-evidence-test-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, program, **options):
        return E.run_command([sys.executable, "-I", "-B", "-c", program], cwd=self.root,
            environment=dict(os.environ), private=self.root / "command", timeout=options.pop("timeout", 5),
            **options)

    def test_real_success_captures_both_private_streams_and_known_close(self):
        public = io.StringIO()
        with contextlib.redirect_stdout(public), contextlib.redirect_stderr(public):
            # Exact binary fixture bytes on Windows too; print() adds CRLF there.
            result = self.command("import sys; sys.stdout.buffer.write(b'PRIVATE_OUTPUT\\n'); "
                                  "sys.stderr.buffer.write(b'PRIVATE_ERROR\\n')")
        self.assertEqual(result["code"], "PASS")
        self.assertEqual(result["exitCode"], 0)
        self.assertTrue(result["cleanupKnown"])
        self.assertTrue(result["capturesClosed"])
        self.assertFalse(result["timedOut"])
        self.assertEqual(public.getvalue(), "")
        self.assertEqual((self.root / "command/stdout.log").read_bytes(), b"PRIVATE_OUTPUT\n")
        self.assertEqual((self.root / "command/stderr.log").read_bytes(), b"PRIVATE_ERROR\n")

    def test_real_nonzero_is_preserved_and_not_relabelled_pass(self):
        result = self.command("import sys; print('original failure',file=sys.stderr); sys.exit(7)")
        self.assertEqual((result["code"], result["exitCode"]), ("COMMAND_FAILED", 7))
        self.assertTrue(result["cleanupKnown"])

    def test_real_timeout_retires_original_child(self):
        result = self.command("import time; time.sleep(30)", timeout=0.3)
        self.assertEqual(result["code"], "TIMEOUT")
        self.assertTrue(result["timedOut"])
        self.assertTrue(result["cleanupKnown"])
        self.assertIsNotNone(result["exitCode"])
        self.assertLess(result["elapsedSeconds"], 10)

    def test_real_leader_exit_does_not_leave_child_writing(self):
        # Descendant inherits the actual supervisor marker/Job Object and pipes.
        result = self.command("import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])")
        self.assertEqual(result["exitCode"], 0)
        self.assertTrue(result["cleanupKnown"])
        self.assertEqual(result["code"], "PASS")
        self.assertLess(result["elapsedSeconds"], 10)

    def test_real_output_limit_is_enforced_during_capture(self):
        result = self.command("import sys,time; sys.stdout.buffer.write(b'x'*200000); sys.stdout.flush(); time.sleep(30)",
                              log_limit=1024)
        self.assertEqual(result["code"], "OUTPUT_LIMIT")
        self.assertLessEqual((self.root / "command/stdout.log").stat().st_size, 1024)
        self.assertTrue(result["cleanupKnown"])

    def test_actual_scope_failed_postspawn_still_closes_original_pipes(self):
        real = E.audit_processes.make_scope
        retained = []
        def supplier(*args):
            scope = real(*args)
            original = scope.spawn
            def failed(*args, **kwargs):
                child = original(*args, **kwargs)
                retained.extend((child.stdout, child.stderr))
                raise RuntimeError("PRIVATE_EXCEPTION")
            scope.spawn = failed
            return scope
        with mock.patch.object(E.audit_processes, "make_scope", supplier):
            result = self.command("import time; time.sleep(30)")
        self.assertEqual(result["code"], "SPAWN")
        self.assertTrue(result["cleanupKnown"])
        self.assertTrue(all(pipe.closed for pipe in retained))

    def test_real_cancellation_is_not_pass(self):
        result = self.command("import time; time.sleep(30)", cancelled=lambda: True)
        self.assertEqual(result["code"], "CANCELLED")
        self.assertTrue(result["cleanupKnown"])

    def test_pending_context_records_closed_counts_without_native_calls_or_authority(self):
        scope = object.__new__(E.audit_processes.DarwinScope)
        parent = {"pid": 10, "uniqueId": 100, "parentUniqueId": 1,
                  "startSeconds": 1, "startMicroseconds": 0, "flags": 0}
        identity = {"pid": 11, "uniqueId": 101, "parentUniqueId": 100,
                    "startSeconds": 2, "startMicroseconds": 0, "flags": 0}
        scope.identity_history = {100: parent}
        scope.known, scope.handles = {}, {}
        scope.baseline = {scope._key(parent)}
        scope.diagnostic_roles = {scope._key(identity): "xcodebuild"}
        record = {"identity": identity, "lastIdentity": identity, "auditSessionExclusion": "NOT_RECORDED",
                  "lastFailure": "Darwin environment unresolved after bounded observation: private detail"}
        scope.pending_discoveries = {11: record}
        scope.discovery_errors = {"PRIVATE_PID_11"}
        with mock.patch.object(scope, "_identity", side_effect=AssertionError("new native query")), \
                mock.patch.object(scope, "_audit_session", side_effect=AssertionError("new native query")), \
                mock.patch.object(scope, "_has_pipe", side_effect=AssertionError("new native query")):
            actual = E.pending_context_diagnostic(scope)
        self.assertEqual(actual, {"scope": E.PENDING_CONTEXT_SCOPE, "pendingCount": 1,
            "roles": {"xcodebuild": 1}, "parentage": {"BASELINE": 1},
            "sessionExclusions": {"NOT_RECORDED": 1}, "failureKinds": {"ENVIRONMENT": 1}})
        self.assertEqual(scope.pending_discoveries, {11: record})
        self.assertEqual(scope.discovery_errors, {"PRIVATE_PID_11"})
        self.assertEqual(scope.known, {})
        self.assertEqual(scope.handles, {})
        self.assertNotIn("private", json.dumps(actual).lower())

    def test_pending_context_finite_causes_and_sessions_do_not_export_input_text(self):
        causes = [(message, label) for message, label in E.PENDING_FAILURES.items()]
        causes += [("Darwin " + operation + " unresolved after bounded observation: PRIVATE", label)
                   for operation, label in E.PENDING_OPERATIONS.items()]
        causes += [("PRIVATE", "OTHER"), ("x" * 4097, "OTHER"), (False, "OTHER")]
        for message, expected in causes:
            scope = mock.Mock(pending_discoveries={1: {"lastFailure": message,
                                                       "auditSessionExclusion": "PRIVATE"}})
            scope._pending_context.return_value = {"scope": E.PENDING_CONTEXT_SCOPE,
                "roles": {"OTHER": 1}, "parentage": {"UNOBSERVED": 1}}
            actual = E.pending_context_diagnostic(scope)
            self.assertEqual(actual["failureKinds"], {expected: 1})
            self.assertEqual(actual["sessionExclusions"], {"NOT_RECORDED": 1})
            self.assertNotIn("PRIVATE", json.dumps(actual))
        for session in E.audit_processes.DARWIN_SESSION_EXCLUSIONS:
            scope.pending_discoveries[1]["auditSessionExclusion"] = session
            self.assertEqual(E.pending_context_diagnostic(scope)["sessionExclusions"], {session: 1})
        scope._pending_context.side_effect = RuntimeError("PRIVATE")
        self.assertIsNone(E.pending_context_diagnostic(scope))

    def test_pending_context_projection_refuses_private_or_inconsistent_records(self):
        valid = {"scope": E.PENDING_CONTEXT_SCOPE, "pendingCount": 1, "roles": {"java": 1},
                 "parentage": {"UNOBSERVED": 1}, "sessionExclusions": {"SAME_VALID_SESSION": 1},
                 "failureKinds": {"PARENT_UNOBSERVED": 1}}
        base = {"code": "CLEANUP", "exitCode": 1, "cleanupKnown": False, "timedOut": False}
        self.assertEqual(E.public_outcome({**base, "pendingContext": valid})["pendingContext"], valid)
        invalid = [{**valid, "pid": 123}, {**valid, "pendingCount": True}, {**valid, "pendingCount": 1025},
                   {**valid, "scope": "PRIVATE"}]
        for field in ("roles", "parentage", "sessionExclusions", "failureKinds"):
            label = next(iter(valid[field]))
            invalid.extend({**valid, field: counts} for counts in
                           ({"PRIVATE": 1}, {label: True}, {label: 0}, {label: 1025}, {label: 2}, {}))
        for value in invalid:
            with self.subTest(value=value):
                self.assertNotIn("pendingContext", E.public_outcome({**base, "pendingContext": value}))
        for pending in ({}, {index: {} for index in range(1025)}, [], None):
            scope = mock.Mock(pending_discoveries=pending)
            self.assertIsNone(E.pending_context_diagnostic(scope))
            scope._pending_context.assert_not_called()

    def test_failed_darwin_drain_retains_context_and_still_closes_scope(self):
        child = mock.Mock(stdout=io.BytesIO(b""), stderr=io.BytesIO(b""), returncode=1)
        child.poll.return_value = 1
        scope = mock.Mock(spec=E.audit_processes.DarwinScope)
        scope.leaders, scope.discovery_errors = [child], {"PRIVATE"}
        scope.spawn.return_value = child
        scope.drain.side_effect = E.audit_processes.OwnershipError(
            "Unclassified Darwin lifetimes remain; cleanup is not proven")
        scope.pending_discoveries = {11: {"lastFailure": "Darwin non-reaper original-parent lifetime was not observed",
                                        "auditSessionExclusion": "SAME_VALID_SESSION"}}
        scope._pending_context.return_value = {"scope": E.PENDING_CONTEXT_SCOPE,
            "roles": {"java": 1}, "parentage": {"UNOBSERVED": 1}}
        with mock.patch.object(E.audit_processes, "make_scope", return_value=scope):
            actual = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                private=self.root / "darwin-context", timeout=5)
        self.assertFalse(actual["cleanupKnown"])
        self.assertEqual(actual["code"], "COMMAND_FAILED")
        self.assertEqual(actual["cleanupReasons"], ["DRAIN_UNCLASSIFIED"])
        self.assertEqual(actual["pendingContext"]["failureKinds"], {"PARENT_UNOBSERVED": 1})
        scope.close.assert_called_once()
        scope._pending_context.assert_called_once()

    def test_cleanup_reasons_distinguish_drain_wait_and_close_without_private_text(self):
        cases = (
            ("deadline", "DRAIN_DEADLINE"), ("unknown", "DRAIN_UNCLASSIFIED"),
            ("quiet", "DRAIN_NOT_QUIET"), ("signal", "DRAIN_SIGNAL_UNRESOLVED"),
            ("other", "DRAIN_ERROR"), ("live", "LIVE_PROCESSES"),
            ("discovery", "DISCOVERY_ERRORS"), ("wait", "LEADER_WAIT"),
            ("close", "SCOPE_CLOSE"), ("okay", None),
        )
        errors = {
            "deadline": E.audit_processes.DrainDeadlineExceeded("PRIVATE_DEADLINE"),
            "unknown": E.audit_processes.OwnershipError("Unclassified Darwin lifetimes remain; cleanup is not proven"),
            "quiet": E.audit_processes.OwnershipError("Darwin drain did not establish three quiet censuses within its phase bounds"),
            "signal": E.audit_processes.DarwinObservationExhausted("Darwin known-token drain remains unresolved within its phase bounds"),
            "other": RuntimeError("PRIVATE_NATIVE_ERROR"),
        }
        for case, reason in cases:
            with self.subTest(case=case):
                child = mock.Mock(stdout=io.BytesIO(b"PRIVATE_OUTPUT"), stderr=io.BytesIO(b""), returncode=0)
                child.poll.return_value = 0
                scope = mock.Mock(leaders=[child], discovery_errors=set())
                scope.spawn.return_value = child
                scope.drain.return_value = []
                if case in errors:
                    scope.drain.side_effect = errors[case]
                elif case == "live":
                    scope.drain.return_value = [{"PRIVATE_PID": 123}]
                elif case == "discovery":
                    scope.discovery_errors.add("PRIVATE_DISCOVERY")
                elif case == "wait":
                    child.wait.side_effect = subprocess.TimeoutExpired("PRIVATE_COMMAND", 1)
                elif case == "close":
                    scope.close.side_effect = OSError("PRIVATE_CLOSE")
                public = io.StringIO()
                with mock.patch.object(E.audit_processes, "make_scope", return_value=scope), \
                        contextlib.redirect_stdout(public), contextlib.redirect_stderr(public):
                    outcome = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                        private=self.root / case, timeout=5)
                self.assertEqual(outcome["cleanupKnown"], reason is None)
                self.assertEqual(outcome["code"], "PASS" if reason is None else "CLEANUP")
                self.assertEqual(outcome["cleanupReasons"], [] if reason is None else [reason])
                self.assertNotIn("PRIVATE", json.dumps(E.public_outcome(outcome)))
                self.assertEqual(public.getvalue(), "")
                scope.close.assert_called_once()
                self.assertTrue(child.stdout.closed and child.stderr.closed)

    def test_cleanup_capture_reasons_do_not_accept_open_or_active_pipes(self):
        for field, reason in (("active", "CAPTURE_ACTIVE"), ("eof", "PIPE_NO_EOF"), ("closed", "PIPE_NOT_CLOSED")):
            with self.subTest(field=field):
                child = mock.Mock(returncode=7)
                child.poll.return_value = 7
                scope = mock.Mock(leaders=[child], discovery_errors=set())
                scope.spawn.return_value = child
                scope.drain.return_value = []
                capture = mock.Mock(eof=field != "eof", closed=field != "closed", error=None)
                capture.thread.is_alive.return_value = field == "active"
                with mock.patch.object(E.audit_processes, "make_scope", return_value=scope), \
                        mock.patch.object(E, "Capture", return_value=capture):
                    outcome = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                        private=self.root / field, timeout=5)
                self.assertFalse(outcome["cleanupKnown"])
                self.assertEqual(outcome["code"], "COMMAND_FAILED")  # Do not replace original failure.
                self.assertEqual(outcome["exitCode"], 7)
                self.assertEqual(outcome["cleanupReasons"], [reason])

    def test_cleanup_reason_projection_rejects_unbounded_or_private_values(self):
        base = {"code": "CLEANUP", "exitCode": 0, "cleanupKnown": False, "timedOut": False}
        for reasons in (["PRIVATE_TEXT"], [False], {"DRAIN_ERROR": True}, ["DRAIN_ERROR"] * 100, "DRAIN_ERROR"):
            with self.subTest(reasons=reasons):
                self.assertNotIn("cleanupReasons", E.public_outcome({**base, "cleanupReasons": reasons}))
        self.assertEqual(E.public_outcome({**base, "cleanupReasons": ["DRAIN_ERROR"]})["cleanupReasons"], ["DRAIN_ERROR"])
        self.assertEqual(E.cleanup_error_reason(RuntimeError("Unclassified Darwin lifetimes remain; cleanup is not proven")),
                         "DRAIN_ERROR")  # Wrong exception type cannot acquire a specific backend diagnosis.

    def test_main_cleanup_failure_retains_only_safe_receipt_and_never_reads_live_logs(self):
        private = self.root / "private"; private.mkdir()
        repo = self.root / "repo"; repo.mkdir()
        output = self.root / "output"
        outcome = {"code": "CLEANUP", "exitCode": 0, "cleanupKnown": False, "timedOut": False,
                   "cleanupReasons": ["DRAIN_UNCLASSIFIED"]}
        public = io.StringIO()
        source = {"commit": "a" * 40, "tree": "b" * 40, "version": "0.8.0-rc1"}
        with mock.patch.object(E, "source_identity", return_value=source), \
                mock.patch.object(E, "github_identity", return_value={"runId": "123", "runAttempt": "1"}), \
                mock.patch.object(E, "run_command", return_value=outcome), \
                mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                mock.patch.object(E, "encrypt_archive") as encrypt, \
                mock.patch.object(E, "failure_diagnostics") as read_logs, contextlib.redirect_stderr(public):
            result = E.main(["--component", "dependency-update", "--timeout-seconds", "5", "--output-dir", str(output),
                             "--source-root", str(repo), "--", "synthetic"])
        self.assertEqual(result, 1)
        self.assertEqual(public.getvalue(), "CI_EVIDENCE FAIL COMMAND CLEANUP\n")
        self.assertEqual([p.name for p in output.iterdir()], ["failure.json"])
        failure = json.loads((output / "failure.json").read_text())
        self.assertEqual(failure["outcome"], outcome)
        self.assertIsNone(failure["failureDiagnostics"])
        self.assertTrue(private.is_dir())
        encrypt.assert_not_called()
        read_logs.assert_not_called()

    def test_cleanup_failure_can_classify_closed_captures_but_not_mutable_reports(self):
        repo = self.root / "repo"; repo.mkdir()
        private = self.root / "private"; private.mkdir()
        command = private / "command"; command.mkdir()
        (command / "stdout.log").write_text(
            "> Task :p2p-core:jvmTest FAILED\nPRIVATE_PAYLOAD\n")
        (command / "stderr.log").write_text(
            "FATAL: disposable-key bundle test failed during: signed bundle build\nPRIVATE_SECRET\n")
        outcome = {"code": "COMMAND_FAILED", "exitCode": 1, "cleanupKnown": False,
                   "capturesClosed": True, "timedOut": False, "cleanupReasons": ["DRAIN_UNCLASSIFIED"]}
        output = self.root / "output"
        source = {"commit": "a" * 40, "tree": "b" * 40, "version": "0.8.0-rc1"}
        with mock.patch.object(E, "source_identity", return_value=source), \
                mock.patch.object(E, "github_identity", return_value={"runId": "123", "runAttempt": "1"}), \
                mock.patch.object(E, "run_command", return_value=outcome), \
                mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                mock.patch.object(E, "encrypt_archive") as encrypt, \
                mock.patch.object(E, "junit_failures", side_effect=AssertionError("live report read")), \
                mock.patch.object(E, "component_tasks", side_effect=AssertionError("live task read")), \
                contextlib.redirect_stderr(io.StringIO()):
            result = E.main(["--component", "dependency-update", "--timeout-seconds", "5", "--output-dir", str(output),
                             "--source-root", str(repo), "--", "synthetic"])
        self.assertEqual(result, 1)
        self.assertEqual([p.name for p in output.iterdir()], ["failure.json"])
        raw = (output / "failure.json").read_text()
        failure = json.loads(raw)
        self.assertFalse(failure["outcome"]["cleanupKnown"])
        self.assertIsNone(failure["taskResults"])
        self.assertEqual(failure["failureDiagnostics"]["categories"], ["BUNDLE_TEST_SIGNED_BUILD"])
        self.assertEqual(failure["failureDiagnostics"]["failedGradleTasks"], [":p2p-core:jvmTest"])
        self.assertEqual(failure["failureDiagnostics"]["failedSourceTests"], [])
        self.assertNotIn("PRIVATE", raw)
        self.assertTrue(private.is_dir())
        encrypt.assert_not_called()

    def test_closed_failure_archive_encrypts_only_original_logs_and_never_qualifies(self):
        repo = self.root / "repo"; repo.mkdir()
        (repo / ".github").mkdir()
        key = b"PUBLIC_RECIPIENT_MODEL_NOT_A_KEY"
        (repo / ".github/ci-evidence-recipient.asc").write_bytes(key)
        private = self.root / "private"; private.mkdir()
        command = private / "command"; command.mkdir()
        logs = {"stdout.log": b"PRIVATE_SYNTHETIC_CAUSE", "stderr.log": b"PRIVATE_SYNTHETIC_ERROR"}
        for name, raw in logs.items():
            (command / name).write_bytes(raw)
        (command / "mutable-report.xml").write_text("MUTABLE_NOT_ALLOWED")
        outcome = {"code": "COMMAND_FAILED", "exitCode": 7, "cleanupKnown": False,
                   "capturesClosed": True, "timedOut": False, "cleanupReasons": ["DRAIN_UNCLASSIFIED"]}
        source = {"commit": "a" * 40, "tree": "b" * 40, "version": "0.8.0-rc1"}
        output = self.root / "output"
        fingerprint = "A" * 40
        cipher_bytes = b"SYNTHETIC_CIPHERTEXT_NOT_REAL_ENCRYPTION"
        def encrypt(archive, target, key_raw, expected_sha, expected_fingerprint, work, environment):
            initial = json.loads((output / "failure.json").read_text())
            self.assertFalse(initial["outcome"]["cleanupKnown"])
            self.assertNotIn("closedCaptureArchive", initial)
            self.assertTrue(target.is_relative_to(private))
            self.assertFalse((output / "evidence.tar.gz.gpg").exists())
            self.assertEqual(key_raw, key)
            self.assertEqual(expected_sha, hashlib.sha256(key).hexdigest())
            self.assertEqual(expected_fingerprint, fingerprint)
            with tarfile.open(archive) as saved:
                self.assertEqual(saved.getnames(), ["stderr.log", "stdout.log"])
                for name in saved.getnames():
                    self.assertEqual(saved.extractfile(name).read(), logs[name])
            target.write_bytes(cipher_bytes)
            return {**E.digest_file(target), "recipientFingerprint": fingerprint}
        with mock.patch.object(E, "source_identity", return_value=source), \
                mock.patch.object(E, "github_identity", return_value={"runId": "123", "runAttempt": "1"}), \
                mock.patch.object(E, "run_command", return_value=outcome), \
                mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                mock.patch.object(E, "encrypt_archive", side_effect=encrypt) as encryption, \
                mock.patch.object(E, "collect_reports", side_effect=AssertionError("mutable report read")), \
                mock.patch.object(E, "junit_failures", side_effect=AssertionError("mutable JUnit read")), \
                mock.patch.object(E, "component_tasks", side_effect=AssertionError("mutable task read")), \
                mock.patch.dict(os.environ, {"CI_EVIDENCE_RECIPIENT_SHA256": hashlib.sha256(key).hexdigest(),
                                            "CI_EVIDENCE_RECIPIENT_FINGERPRINT": fingerprint}), \
                contextlib.redirect_stderr(io.StringIO()) as public:
            result = E.main(["--component", "compatibility", "--timeout-seconds", "5", "--output-dir", str(output),
                             "--source-root", str(repo), "--", "synthetic"])
        self.assertEqual(result, 1)
        encryption.assert_called_once()
        self.assertEqual({p.name for p in output.iterdir()}, {"failure.json", "evidence.tar.gz.gpg"})
        failure = json.loads((output / "failure.json").read_text())
        self.assertEqual(failure["outcome"], outcome)
        self.assertEqual((failure["stage"], failure["code"]), ("COMMAND", "CLEANUP"))
        self.assertIsNone(failure["taskResults"])
        attached = failure["closedCaptureArchive"]
        self.assertEqual(attached["kind"], "CLOSED_CAPTURES_ONLY_NOT_QUALIFICATION")
        self.assertEqual(attached["sourceValidation"], "INITIAL_ONLY")
        self.assertEqual(attached["members"], ["stderr.log", "stdout.log"])
        self.assertEqual(attached["privateArchive"], E.digest_file(private / "failure-encryption/evidence.tar.gz"))
        self.assertEqual(attached["ciphertext"]["sha256"], hashlib.sha256(cipher_bytes).hexdigest())
        self.assertTrue(private.is_dir())
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(failure) + public.getvalue())
        # The real maintained qualification consumer rejects this diagnostic ZIP.
        import ci_qualification as Q
        import zipfile
        packed = io.BytesIO()
        with zipfile.ZipFile(packed, "w") as archive:
            for name in ("failure.json", "evidence.tar.gz.gpg"):
                archive.writestr(name, (output / name).read_bytes())
        raw = packed.getvalue()
        api = mock.Mock()
        api.download.side_effect = lambda _artifact, path: path.write_bytes(raw)
        artifact = {"size_in_bytes": len(raw), "digest": "sha256:" + hashlib.sha256(raw).hexdigest()}
        with self.assertRaisesRegex(Q.AdmissionError, "Unexpected record ZIP members"):
            Q.read_archive(api, artifact, evidence=True)

    def test_failed_diagnostic_encryption_or_receipt_replacement_preserves_original_failure(self):
        for problem in ("encryption", "receipt-replace"):
            with self.subTest(problem=problem):
                case = self.root / problem; case.mkdir()
                repo = case / "repo"; repo.mkdir()
                private = case / "private"; private.mkdir()
                command = private / "command"; command.mkdir()
                for name in ("stdout.log", "stderr.log"):
                    (command / name).write_text("PRIVATE_SYNTHETIC")
                output = case / "output"
                outcome = {"code": "COMMAND_FAILED", "exitCode": 9, "cleanupKnown": False,
                           "capturesClosed": True, "timedOut": False}
                def diagnostic(_root, _private, _output, _env):
                    self.assertTrue((output / "failure.json").exists())
                    (private / "partial-ciphertext").write_bytes(b"PRIVATE_PARTIAL_CIPHER")
                    if problem == "encryption":
                        raise E.EvidenceError("ENCRYPTION")
                    (output / "evidence.tar.gz.gpg").write_bytes(b"SYNTHETIC_COMPLETE_CIPHER")
                    return {"kind": "CLOSED_CAPTURES_ONLY_NOT_QUALIFICATION"}
                with mock.patch.object(E, "source_identity", return_value={"commit": "a" * 40}), \
                        mock.patch.object(E, "github_identity", return_value={}), \
                        mock.patch.object(E, "run_command", return_value=outcome), \
                        mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                        mock.patch.object(E, "encrypt_closed_failure_captures", side_effect=diagnostic), \
                        mock.patch.object(E.os, "replace", side_effect=OSError("PRIVATE_ERROR")), \
                        contextlib.redirect_stderr(io.StringIO()) as public:
                    result = E.main(["--component", "compatibility", "--timeout-seconds", "5", "--output-dir", str(output),
                                     "--source-root", str(repo), "--", "synthetic"])
                self.assertEqual(result, 1)
                self.assertEqual({p.name for p in output.iterdir()}, {"failure.json"})
                failure = json.loads((output / "failure.json").read_text())
                self.assertEqual(failure["outcome"], outcome)
                self.assertNotIn("closedCaptureArchive", failure)
                self.assertTrue((private / "partial-ciphertext").is_file())
                self.assertNotIn("PRIVATE", public.getvalue())
                self.assertIn("DIAGNOSTIC_ENCRYPTION_FAILED", public.getvalue())

    def test_unknown_capture_proof_never_encrypts_failed_cleanup(self):
        for closed in (False, None, 1, "true"):
            case = self.root / str(closed); case.mkdir()
            repo = case / "repo"; repo.mkdir()
            private = case / "private"; private.mkdir()
            outcome = {"code": "CLEANUP", "exitCode": 0, "cleanupKnown": False,
                       "capturesClosed": closed, "timedOut": False}
            with mock.patch.object(E, "source_identity", return_value={"commit": "a" * 40}), \
                    mock.patch.object(E, "github_identity", return_value={}), \
                    mock.patch.object(E, "run_command", return_value=outcome), \
                    mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                    mock.patch.object(E, "encrypt_closed_failure_captures") as encrypt, \
                    mock.patch.object(E, "failure_diagnostics") as diagnostics, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(E.main(["--component", "compatibility", "--timeout-seconds", "5",
                    "--output-dir", str(case / "output"), "--source-root", str(repo), "--", "synthetic"]), 1)
            encrypt.assert_not_called()
            diagnostics.assert_not_called()

    def test_failure_archive_rejects_linked_or_oversized_capture_before_encryption(self):
        for kind in ("hardlink", "oversized"):
            case = self.root / kind; case.mkdir()
            private = case / "private"; private.mkdir()
            command = private / "command"; command.mkdir()
            (command / "stdout.log").write_bytes(b"synthetic")
            if kind == "hardlink":
                os.link(command / "stdout.log", command / "stderr.log")
            else:
                (command / "stderr.log").write_bytes(b"too large for modeled bound")
            with mock.patch.object(E, "MAX_LOG_BYTES", 16), \
                    mock.patch.object(E, "encrypt_archive") as encrypt, self.assertRaises(E.EvidenceError):
                E.encrypt_closed_failure_captures(case, private, case / "output", {})
            encrypt.assert_not_called()

    def test_capture_admission_requires_both_started_eof_closed_joined_error_free_streams(self):
        for defect in ("unstarted", "active", "no-eof", "open", "io-error"):
            with self.subTest(defect=defect):
                child = mock.Mock(returncode=0)
                child.poll.return_value = 0
                scope = mock.Mock(leaders=[child], discovery_errors=set())
                scope.spawn.return_value = child
                scope.drain.return_value = []
                good = mock.Mock(eof=True, closed=True, error=None)
                good.thread.ident = 1
                good.thread.is_alive.return_value = False
                bad = mock.Mock(eof=defect != "no-eof", closed=defect != "open",
                                error="OUTPUT_IO" if defect == "io-error" else None)
                bad.thread.ident = None if defect == "unstarted" else 2
                bad.thread.is_alive.return_value = defect == "active"
                with mock.patch.object(E.audit_processes, "make_scope", return_value=scope), \
                        mock.patch.object(E, "Capture", side_effect=[good, bad]):
                    result = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                        private=self.root / defect, timeout=5)
                self.assertFalse(result["capturesClosed"])

    def test_unknown_capture_boolean_is_not_public_closed_capture_authority(self):
        base = {"code": "CLEANUP", "exitCode": 1, "cleanupKnown": False, "timedOut": False}
        for value in (1, "true", {}, None):
            self.assertNotIn("capturesClosed", E.public_outcome({**base, "capturesClosed": value}))

    def test_command_observes_owned_descendants_before_final_drain(self):
        child = mock.Mock(stdout=io.BytesIO(b""), stderr=io.BytesIO(b""), returncode=0)
        child.poll.side_effect = [None, 0]
        scope = mock.Mock(leaders=[child], discovery_errors=set())
        scope.spawn.return_value = child
        observed = []
        scope.discover.side_effect = lambda: observed.append("during-work")
        def drain(**kwargs):
            self.assertEqual(observed, ["during-work"])
            observed.append("final-drain")
            return []
        scope.drain.side_effect = drain
        with mock.patch.object(E.audit_processes, "make_scope", return_value=scope):
            outcome = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                private=self.root / "observed", timeout=5)
        self.assertEqual(outcome["code"], "PASS")
        self.assertTrue(outcome["cleanupKnown"])
        self.assertEqual(observed, ["during-work", "final-drain"])

    def test_work_discovery_error_stays_failed_even_after_successful_drain(self):
        child = mock.Mock(stdout=io.BytesIO(b""), stderr=io.BytesIO(b""), returncode=0)
        scope = mock.Mock(leaders=[child], discovery_errors=set())
        scope.spawn.return_value = child
        scope.discover.side_effect = E.audit_processes.OwnershipError("PRIVATE_OBSERVATION_ERROR")
        scope.drain.return_value = []
        with mock.patch.object(E.audit_processes, "make_scope", return_value=scope):
            outcome = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                private=self.root / "discovery-error", timeout=5)
        self.assertEqual(outcome["code"], "CLEANUP")
        self.assertTrue(outcome["cleanupKnown"])
        scope.drain.assert_called_once()
        self.assertNotIn("PRIVATE", json.dumps(E.public_outcome(outcome)))

    def test_late_discovery_cannot_hide_timeout_cancel_or_capture_failure(self):
        for case, expected in (("timeout", "TIMEOUT"), ("cancel", "CANCELLED"), ("capture", "OUTPUT_LIMIT")):
            with self.subTest(case=case):
                state = {"now": 0.0, "cancelled": False}
                child = mock.Mock(returncode=0)
                child.poll.return_value = 0
                scope = mock.Mock(leaders=[child], discovery_errors=set())
                scope.spawn.return_value = child
                scope.drain.return_value = []
                capture = mock.Mock(eof=True, closed=True, error=None)
                capture.thread.is_alive.return_value = False
                def discover():
                    if case == "timeout":
                        state["now"] = 6.0
                    elif case == "cancel":
                        state["cancelled"] = True
                    else:
                        capture.error = "OUTPUT_LIMIT"
                scope.discover.side_effect = discover
                with mock.patch.object(E.audit_processes, "make_scope", return_value=scope), \
                        mock.patch.object(E.time, "monotonic", side_effect=lambda: state["now"]), \
                        mock.patch.object(E, "Capture", return_value=capture):
                    outcome = E.run_command(["synthetic"], cwd=self.root, environment=dict(os.environ),
                        private=self.root / case, timeout=5, cancelled=lambda: state["cancelled"])
                self.assertEqual(outcome["code"], expected)
                self.assertEqual(outcome["timedOut"], case == "timeout")
                self.assertTrue(outcome["cleanupKnown"])
                scope.drain.assert_called_once()

    def test_reports_archive_hashes_and_rejects_links(self):
        source = self.root / "repo"
        source.mkdir()
        (source / "result.xml").write_bytes(b"<testsuite tests='1'/>\n")
        bundle = self.root / "bundle"
        bundle.mkdir()
        E.collect_reports(source, ["*.xml"], bundle / "reports")
        destination = self.root / "bundle.tar.gz"
        rows = E.archive_private(bundle, destination)
        self.assertEqual(rows, [{"path": "reports/result.xml", **E.digest_file(source / "result.xml")}])
        with tarfile.open(destination) as archive:
            self.assertEqual(archive.extractfile("reports/result.xml").read(), (source / "result.xml").read_bytes())
        # A real hard link is portable and must not silently include aliased data.
        os.link(source / "result.xml", source / "alias.xml")
        with self.assertRaises(E.EvidenceError):
            E.collect_reports(source, ["*.xml"], self.root / "rejected")

    def test_recipient_trusted_pin_checked_before_any_command(self):
        with mock.patch.object(E, "run_command", side_effect=AssertionError("must not launch")):
            with self.assertRaises(E.EvidenceError):
                E.encrypt_archive(self.root / "none", self.root / "cipher", b"NOT A KEY", "0" * 64,
                                  "1" * 40, self.root, dict(os.environ))

    def test_public_failure_diagnostics_keep_identifiers_not_private_messages(self):
        command = self.root / "command"
        command.mkdir()
        (command / "stdout.log").write_text(
            "> Task :p2p-core:jvmTest FAILED\n"
            "> Task :p2p-private:secret FAILED\n"
            "> Task :p2p-core:secret FAILED\n"
            "host_not_announced private-payload-123\n"
            "PUBLICATION_EMBEDDED_CHECK_LINES 321,99,15\n"
            "PUBLICATION_EMBEDDED_CHECK_LINES private-secret\n"
            "Dependency verification failed credential-never-public\n" +
            "a" * 5000 + "private-long-line\n")
        (command / "stderr.log").write_text("private URL or environment must not appear\n")
        phase = self.root / "build/reports/platform-tests/token/intel-simulator/simulator-first-launch"
        phase.mkdir(parents=True)
        (phase / "result.json").write_text(json.dumps({"label": "simulator-first-launch", "exitCode": 1,
            "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True,
            "argv": ["private-path"], "cwd": "private-directory"}))
        result = E.failure_diagnostics(self.root, command)
        self.assertEqual(result["categories"], ["DEPENDENCY_INTEGRITY", "LAN_HOST_NOT_ANNOUNCED"])
        self.assertEqual(result["failedGradleTasks"], [":p2p-core:jvmTest"])
        self.assertEqual(result["embeddedPublicationCheckLines"], [321,99,15])
        self.assertEqual(result["simulatorPhases"], [{"label": "simulator-first-launch", "exitCode": 1,
            "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True}])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("credential", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))
        row = json.loads((phase / "result.json").read_text())
        row["label"] = "simulator-private-secret"
        (phase / "result.json").write_text(json.dumps(row))
        self.assertEqual(E.failure_diagnostics(self.root, command)["simulatorPhases"], [])
        row["label"] = "simulator-first-launch"
        row.pop("exitCode")
        (phase / "result.json").write_text(json.dumps(row))
        self.assertEqual(E.failure_diagnostics(self.root, command)["simulatorPhases"], [])
        row["exitCode"] = True
        (phase / "result.json").write_text(json.dumps(row))
        self.assertEqual(E.failure_diagnostics(self.root, command)["simulatorPhases"], [])

    def test_bundle_diagnostic_phases_are_closed_labels_not_private_messages(self):
        command = self.root / "bundle-command"
        command.mkdir()
        log = command / "stderr.log"
        cases = {
            "initialization": "BUNDLE_TEST_INITIALIZATION",
            "snapshot rejection": "BUNDLE_TEST_SNAPSHOT_REJECTION",
            "release fixture checkout": "BUNDLE_TEST_RELEASE_FIXTURE_CHECKOUT",
            "signature-status parser regression": "BUNDLE_TEST_SIGNATURE_STATUS_PARSER",
            "missing-key rejection": "BUNDLE_TEST_MISSING_KEY_REJECTION",
            "disposable key generation": "BUNDLE_TEST_DISPOSABLE_KEY_GENERATION",
            "disposable key export": "BUNDLE_TEST_DISPOSABLE_KEY_EXPORT",
            "signed bundle build": "BUNDLE_TEST_SIGNED_BUILD",
            "bundle verification": "BUNDLE_TEST_VERIFICATION",
        }
        for phase, category in cases.items():
            with self.subTest(phase=phase):
                log.write_text("FATAL: disposable-key bundle test failed during: " + phase + "\n")
                self.assertEqual(E.failure_diagnostics(self.root, command)["categories"], [category])
        for text in ("private-secret", "signed bundle build private-payload", "/private/key.asc", "a" * 5000):
            log.write_text("FATAL: disposable-key bundle test failed during: " + text + "\n")
            result = E.failure_diagnostics(self.root, command)
            self.assertEqual(result["categories"], [])
            self.assertNotIn("private", json.dumps(result))
        log.write_text("FATAL: disposable-key bundle test failed during: signed bundle build\r\n")
        self.assertEqual(E.failure_diagnostics(self.root, command)["categories"], ["BUNDLE_TEST_SIGNED_BUILD"])

    def test_junit_failure_diagnostics_only_reveal_existing_source_identifiers(self):
        source = self.root / "library/p2p-core/src/commonTest/kotlin/dev/p2pkit/ExampleTest.kt"
        source.parent.mkdir(parents=True)
        source.write_text("package dev.p2pkit\nclass ExampleTest { fun actualCase() {} }\n")
        report = self.root / "library/p2p-core/build/test-results/jvmTest/TEST-example.xml"
        report.parent.mkdir(parents=True)
        report.write_text('<testsuite><testcase classname="dev.p2pkit.ExampleTest" name="actualCase[jvm]">'
                          '<failure type="java.lang.AssertionError" message="PRIVATE_MESSAGE">PRIVATE_STACK</failure>'
                          '</testcase><testcase classname="dev.p2pkit.ExampleTest" name="PRIVATE_PAYLOAD">'
                          '<failure>PRIVATE_TEXT</failure></testcase>'
                          '<testcase classname="private.SecretTest" name="actualCase"><error/></testcase></testsuite>')
        expected = [{"source": source.relative_to(self.root).as_posix(), "test": "actualCase", "kinds": ["ASSERTION"]}]
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)
        git("init", "--quiet")
        self.assertEqual(E.junit_failures(self.root), [])  # No original committed source.
        git("add", source.relative_to(self.root).as_posix())
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Public test source fixture")
        original = git("rev-parse", "HEAD").decode().strip()
        saved = source.read_bytes()
        source.write_bytes(saved + b"// modified source is not authority\n")
        self.assertEqual(E.junit_failures(self.root, original), [])
        git("add", source.relative_to(self.root).as_posix())
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Different test source fixture")
        self.assertEqual(E.junit_failures(self.root, original), [])
        source.write_bytes(saved)
        self.assertEqual(E.junit_failures(self.root, original), expected)
        git("checkout", original, "--", source.relative_to(self.root).as_posix())
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Restore public test source fixture")
        self.assertEqual(E.junit_failures(self.root), expected)
        self.assertNotIn("PRIVATE", json.dumps(E.junit_failures(self.root)))
        report.write_text(report.read_text().replace('type="java.lang.AssertionError"', 'type="PRIVATE_TYPE"'))
        self.assertEqual(E.junit_failures(self.root)[0]["kinds"], ["OTHER"])
        report.write_text('<testsuite><testcase classname="dev.p2pkit.ExampleTest" name="actualCase"/></testsuite>')
        self.assertEqual(E.junit_failures(self.root), [])

    def test_junit_diagnostic_refuses_entities_malformed_and_linked_reports(self):
        directory = self.root / "library/p2p-core/build/test-results/jvmTest"
        directory.mkdir(parents=True)
        report = directory / "TEST-example.xml"
        source = self.root / "library/p2p-core/src/commonTest/kotlin/dev/p2pkit/ExampleTest.kt"
        source.parent.mkdir(parents=True)
        source.write_text("package dev.p2pkit\nclass ExampleTest { fun actualCase() {} }\n")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)
        git("init", "--quiet")
        git("add", source.relative_to(self.root).as_posix())
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Public negative-parser fixture")
        valid = b'<testsuite><testcase classname="dev.p2pkit.ExampleTest" name="actualCase"><failure/></testcase></testsuite>'
        report.write_bytes(valid)
        self.assertEqual(len(E.junit_failures(self.root)), 1)
        untracked = source.with_name("UntrackedTest.kt")
        untracked.write_text("package dev.p2pkit\nclass UntrackedTest { fun actualCase() {} }\n")
        report.write_bytes(valid.replace(b'ExampleTest', b'UntrackedTest'))
        self.assertEqual(E.junit_failures(self.root), [])
        for raw in (b'<!DOCTYPE testsuite [<!ENTITY a "private">]>' + valid, b'<broken>', b'x' * (4 * 1024 * 1024 + 1)):
            report.write_bytes(raw)
            self.assertEqual(E.junit_failures(self.root), [])
        report.unlink()
        outside = self.root / "private.xml"
        outside.write_bytes(valid)
        os.link(outside, report)
        self.assertEqual(E.junit_failures(self.root), [])

    def test_embedded_publication_emits_source_lines_without_changing_failure(self):
        import ast
        import struct
        import xml.etree.ElementTree as ET
        import zipfile
        shell = (SCRIPTS / "check-publish-artifacts.sh").read_text()
        script = shell.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        tree = ast.parse(script)
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "require")
        guard = next(node for node in tree.body if isinstance(node, ast.Try))
        namespace = {"sys": sys, "ET": ET, "zipfile": zipfile, "struct": struct}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "<stdin>", "exec"), namespace)
        namespace["inspect"] = lambda: namespace["require"](False, "PRIVATE_TEST_INPUT")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured), self.assertRaises(SystemExit) as caught:
            exec(compile(ast.Module(body=[guard], type_ignores=[]), "<stdin>", "exec"), namespace)
        self.assertEqual(caught.exception.code, 1)
        self.assertRegex(captured.getvalue(), r"PUBLICATION_EMBEDDED_CHECK_LINES [0-9]+,[0-9]+\n")
        public_line = captured.getvalue().splitlines()[0]
        self.assertNotIn("PRIVATE", public_line)

    def test_platform_failure_diagnostics_project_only_known_tasks_and_counts(self):
        command = self.root / "command"
        command.mkdir()
        (command / "stdout.log").write_text("> Task :p2p-transport-lan:allTests FAILED\nPLATFORM_CHECK_LINES 831,134,58\n"
                                           "PLATFORM_CHECK_LINES private-secret\n")
        directory = self.root / "build/reports/platform-tests/current"
        directory.mkdir(parents=True)
        valid = {"outcome": "FAILED", "passed": 3, "failed": 1, "skipped": 0, "failure": "private-secret"}
        report = {"buildFailed": True, "private": "private-secret", "tests": {
            ":p2p-transport-lan:iosSimulatorArm64Test": valid,
            ":private:secret": valid,
            ":p2p-core:jvmTest": {**valid, "failed": True},
            ":p2p-core:iosX64Test": {**valid, "outcome": "private-secret"}}}
        (directory / "execution.json").write_text(json.dumps(report))
        result = E.failure_diagnostics(self.root, command)
        self.assertEqual(result["platformTests"], [{"buildFailed": True, "tests": [{
            "task": ":p2p-transport-lan:iosSimulatorArm64Test", "outcome": "FAILED", "passed": 3, "failed": 1, "skipped": 0}]}])
        self.assertEqual(result["failedGradleTasks"], [":p2p-transport-lan:allTests"])
        self.assertEqual(result["platformCheckLines"], [831,134,58])
        self.assertNotIn("private", json.dumps(result))
        (directory / "execution.json").write_text('{"tests":[]}')
        self.assertEqual(E.failure_diagnostics(self.root, command)["platformTests"], [])

    def test_platform_actual_failure_locator_preserves_private_exception(self):
        spec = importlib.util.spec_from_file_location("platform_locator_test", SCRIPTS / "run-platform-tests.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        try:
            module.require(False, "PRIVATE_FAILURE")
        except ValueError as error:
            with contextlib.redirect_stderr(output):
                module.report_failure_location(error)
            self.assertEqual(str(error), "PRIVATE_FAILURE")
        else:
            self.fail("Original failure was not preserved")
        self.assertRegex(output.getvalue(), r"^PLATFORM_CHECK_LINES [0-9]+\n$")
        self.assertNotIn("PRIVATE", output.getvalue())

    def test_windows_autocrlf_checkout_preserves_exact_public_recipient_blob(self):
        # Actual Git checkout conversion, not a mocked newline transform. The
        # original public blob is unchanged; no private key or GPG invocation.
        original = subprocess.check_output([
            "git", "-C", str(SCRIPTS.parent), "show", "HEAD:.github/ci-evidence-recipient.asc"])
        attributes = (SCRIPTS.parent / ".gitattributes").read_bytes()
        rule = b".github/ci-evidence-recipient.asc text eol=lf\n"
        self.assertEqual(attributes.count(rule), 1)
        self.assertNotIn(b"\r", original)
        for protected in (False, True):
            with self.subTest(protected=protected):
                repo = self.root / ("protected" if protected else "old-autocrlf")
                repo.mkdir()
                def git(*args, raw=None):
                    return subprocess.check_output(["git", "-C", str(repo), *args],
                                                   input=raw, stderr=subprocess.PIPE)
                git("init", "--quiet")
                git("config", "core.autocrlf", "true")
                for name, raw in ((".gitattributes", attributes if protected else attributes.replace(rule, b"")),
                                  (".github/ci-evidence-recipient.asc", original)):
                    blob = git("hash-object", "-w", "--stdin", raw=raw).decode().strip()
                    git("update-index", "--add", "--cacheinfo", "100644", blob, name)
                git("checkout-index", "--all", "--force")
                actual = (repo / ".github/ci-evidence-recipient.asc").read_bytes()
                if protected:
                    self.assertEqual(actual, original)
                    self.assertEqual(hashlib.sha256(actual).digest(), hashlib.sha256(original).digest())
                else:
                    self.assertIn(b"\r\n", actual)
                    self.assertNotEqual(hashlib.sha256(actual).digest(), hashlib.sha256(original).digest())

    def test_gpg_uses_cwd_relative_paths_for_native_and_msys_interoperation(self):
        work = self.root / 'private work'; work.mkdir()
        source = self.root / 'input archive.tar.gz'; source.write_bytes(b'public fixture')
        output = self.root / 'public output' / 'evidence.tar.gz.gpg'; output.parent.mkdir()
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        calls = []
        def invoke(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(kwargs['cwd'], work)
            self.assertEqual(argv[argv.index('--homedir') + 1], 'gnupg')
            self.assertIn('--no-autostart', argv)
            self.assertIn('--no-auto-key-retrieve', argv)
            expected = {'--import': work / 'recipient.asc', '--output': output, '--encrypt': source}
            for flag, path in expected.items():
                if flag in argv:
                    argument = argv[argv.index(flag) + 1]
                    self.assertFalse(os.path.isabs(argument))
                    self.assertNotIn('\\', argument)
                    self.assertEqual((work / argument).resolve(), path.resolve())
            directory = kwargs['private']; directory.mkdir()
            (directory / 'stdout.log').write_bytes(b'public-key-listing-model')
            (directory / 'stderr.log').write_bytes(b'')
            if '--encrypt' in argv:
                output.write_bytes(b'public-ciphertext-model' * 4)
            return {'code': 'PASS', 'exitCode': 0, 'timedOut': False, 'cleanupKnown': True}
        with mock.patch.object(E, 'run_command', side_effect=invoke), \
                mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                mock.patch.object(E, '_key_identity', return_value=(PUBLIC_FINGERPRINT, 0)):
            E.encrypt_archive(source, output, key, hashlib.sha256(key).hexdigest(),
                              PUBLIC_FINGERPRINT, work, dict(os.environ))
        self.assertEqual(len(calls), 4)
        other = self.root / 'different-drive-model'; other.mkdir()
        with mock.patch.object(E.os.path, 'relpath', side_effect=ValueError('PRIVATE_DRIVE')), \
                mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                mock.patch.object(E, 'run_command') as unused:
            with self.assertRaises(E.EvidenceError) as caught:
                E.encrypt_archive(source, output, key, hashlib.sha256(key).hexdigest(),
                                  PUBLIC_FINGERPRINT, other, dict(os.environ))
        self.assertEqual(caught.exception.code, 'ENCRYPTION')
        unused.assert_not_called()

    def test_actual_public_key_encrypts_without_private_key_or_agent(self):
        key = (SCRIPTS.parent / ".github/ci-evidence-recipient.asc").read_bytes()
        source = self.root / "evidence.tar.gz"
        source.write_bytes(b"PUBLIC_SYNTHETIC_TEST_ONLY" * 100)
        result = E.encrypt_archive(source, self.root / "evidence.tar.gz.gpg", key,
            hashlib.sha256(key).hexdigest(), PUBLIC_FINGERPRINT, self.root, dict(os.environ))
        self.assertEqual(result["recipientFingerprint"], PUBLIC_FINGERPRINT)
        self.assertEqual(result["sha256"], E.digest_file(self.root / "evidence.tar.gz.gpg")["sha256"])
        self.assertGreater(result["bytes"], 32)
        secret_dir = self.root / "gnupg/private-keys-v1.d"
        self.assertFalse(list(secret_dir.iterdir()) if secret_dir.exists() else [])

    def test_actual_git_identity_detects_tracked_mutation(self):
        # Tiny synthetic repository, no project build/source mutation.
        subprocess.run(["git", "init", "-q", str(self.root / "repo")], check=True)
        repo = self.root / "repo"
        (repo / "gradle.properties").write_text("VERSION_NAME=0.8.0-rc1\n")
        subprocess.run(["git", "-C", str(repo), "add", "gradle.properties"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                        "commit", "-qm", "synthetic"], check=True)
        self.assertEqual(E.source_identity(repo)["version"], "0.8.0-rc1")
        (repo / "gradle.properties").write_text("VERSION_NAME=changed\n")
        with self.assertRaises(E.EvidenceError):
            E.source_identity(repo)

    def test_real_complete_runner_binds_source_and_encrypts_private_failure(self):
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".github").mkdir()
        (repo / "gradle.properties").write_text("VERSION_NAME=0.8.0-rc1\n")
        key_raw = (SCRIPTS.parent / ".github/ci-evidence-recipient.asc").read_bytes()
        (repo / ".github/ci-evidence-recipient.asc").write_bytes(key_raw)
        for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Synthetic", "-c",
                     "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True)
        identity = E.source_identity(repo)
        environment = {"GITHUB_REPOSITORY": "example/project", "GITHUB_SHA": identity["commit"],
            "GITHUB_WORKFLOW_REF": "example/project/.github/workflows/ci.yml@refs/heads/main",
            "GITHUB_WORKFLOW_SHA": identity["commit"], "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_JOB": "test", "RUNNER_ENVIRONMENT": "github-hosted",
            "CI_EVIDENCE_RECIPIENT_SHA256": hashlib.sha256(key_raw).hexdigest(),
            "CI_EVIDENCE_RECIPIENT_FINGERPRINT": PUBLIC_FINGERPRINT}
        for exit_code in (0, 9):
            with self.subTest(exit_code=exit_code), mock.patch.dict(os.environ, environment):
                output = self.root / ("public-" + str(exit_code))
                public = io.StringIO()
                with contextlib.redirect_stdout(public), contextlib.redirect_stderr(public):
                    result = E.main(["--component", "source", "--timeout-seconds", "5", "--output-dir", str(output),
                        "--source-root", str(repo), "--", sys.executable, "-c",
                        "import sys; print('PRIVATE_FULL_COMPOSITION'); sys.exit(" + str(exit_code) + ")"])
                self.assertEqual(result, 0 if exit_code == 0 else 1)
                self.assertNotIn("PRIVATE_FULL_COMPOSITION", public.getvalue())
                self.assertEqual({p.name for p in output.iterdir()}, {"manifest.json", "evidence.tar.gz.gpg"})
                manifest = json.loads((output / "manifest.json").read_bytes())
                self.assertEqual(manifest["source"], identity)
                self.assertEqual(manifest["outcome"]["exitCode"], exit_code)
                self.assertTrue(manifest["outcome"]["cleanupKnown"])
                self.assertEqual(manifest["github"]["runAttempt"], "1")
                self.assertEqual(manifest["ciphertext"]["sha256"], E.digest_file(output / "evidence.tar.gz.gpg")["sha256"])
                self.assertNotIn(b"PRIVATE_FULL_COMPOSITION", (output / "manifest.json").read_bytes())

    def test_main_failure_never_echoes_exception_or_partial_artifact(self):
        with mock.patch.object(E, "source_identity", side_effect=RuntimeError("PRIVATE_FAILURE_DATA")):
            output = self.root / "public"
            diagnostic = io.StringIO()
            with contextlib.redirect_stderr(diagnostic):
                result = E.main(["--component", "source", "--timeout-seconds", "5", "--output-dir", str(output),
                                 "--source-root", str(self.root / "not-output"), "--", sys.executable, "-c", "pass"])
        self.assertEqual(result, 1)
        self.assertEqual(diagnostic.getvalue(), "CI_EVIDENCE FAIL SOURCE INPUT\n")
        self.assertEqual([path.name for path in output.iterdir()], ["failure.json"])
        failure = json.loads((output / "failure.json").read_text())
        self.assertEqual(failure["kind"], "CI_EVIDENCE_FAILURE")
        self.assertIsNone(failure["source"])
        self.assertNotIn("PRIVATE", json.dumps(failure))

    def test_gpg_failure_keeps_only_fixed_phase_outcome_and_closed_error_categories(self):
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        for failed_phase in ('key-show', 'key-import', 'key-list', 'encrypt'):
            for cleanup in (True, False):
                with self.subTest(phase=failed_phase, cleanup=cleanup):
                    work = self.root / (failed_phase + str(cleanup)); work.mkdir()
                    calls = []
                    def invoke(argv, **kwargs):
                        directory = kwargs['private']; directory.mkdir()
                        calls.append(directory.name)
                        (directory / 'stdout.log').write_bytes(b'PRIVATE_LISTING')
                        (directory / 'stderr.log').write_bytes(b'gpg: Permission denied PRIVATE_PATH\n')
                        failed = directory.name == failed_phase
                        return {'code': 'COMMAND_FAILED' if failed else 'PASS', 'exitCode': 2 if failed else 0,
                                'cleanupKnown': cleanup if failed else True, 'timedOut': False}
                    with mock.patch.object(E, 'run_command', side_effect=invoke), \
                            mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                            mock.patch.object(E, '_key_identity', return_value=(PUBLIC_FINGERPRINT, 0)):
                        with self.assertRaises(E.EvidenceError) as caught:
                            E.encrypt_archive(work / 'archive', work / 'output', key,
                                hashlib.sha256(key).hexdigest(), PUBLIC_FINGERPRINT, work, dict(os.environ))
                    diagnostic = caught.exception.encryption_diagnostic
                    self.assertEqual(diagnostic['phase'], failed_phase)
                    self.assertEqual(calls[-1], failed_phase)
                    self.assertEqual(diagnostic['outcome'], {'code': 'COMMAND_FAILED', 'exitCode': 2,
                                                            'cleanupKnown': cleanup, 'timedOut': False})
                    self.assertEqual(diagnostic['categories'], ['ACCESS_DENIED'] if cleanup else [])
                    self.assertNotIn('PRIVATE', json.dumps(diagnostic))

    def test_native_spawn_error_diagnostic_exposes_only_fixed_operation_and_numbers(self):
        os_error = OSError(13, 'PRIVATE_OS_MESSAGE', 'PRIVATE_PATH')
        os_error.winerror = 5
        cases = [(os_error, 'OS', None, 13, 5),
            (E.audit_processes.OwnershipError('Windows CreateProcessW (atomic job assignment) failed: error 87'),
             'WIN32', 'CreateProcessW (atomic job assignment)', None, 87),
            (E.audit_processes.OwnershipError('Unsupported Windows Job Object ABI layout'),
             'OWNERSHIP', 'WINDOWS_ABI', None, None),
            (E.audit_processes.OwnershipError('Windows PRIVATE_OPERATION failed: error 87'),
             'UNKNOWN', None, None, None),
            (RuntimeError('PRIVATE_UNKNOWN_ERROR'), 'UNKNOWN', None, None, None)]
        for index, (error, kind, operation, errno, winerror) in enumerate(cases):
            with self.subTest(index=index), mock.patch.object(E.audit_processes, 'make_scope', side_effect=error):
                result = E.run_command(['no-command-executed'], cwd=self.root, environment=dict(os.environ),
                    private=self.root / ('spawn-' + str(index)), timeout=1)
            self.assertEqual(result['code'], 'SPAWN')
            self.assertEqual(result['nativeError'], {'kind': kind, 'operation': operation,
                                                   'errno': errno, 'winerror': winerror})
            self.assertEqual(E.public_outcome(result)['nativeError'], result['nativeError'])
            self.assertNotIn('PRIVATE', json.dumps(E.public_outcome(result)))

    def test_encryption_failure_public_record_is_not_qualification_and_keeps_unknown_writers(self):
        source = {'commit': 'a' * 40, 'tree': 'b' * 40, 'version': '0.7.0-SNAPSHOT'}
        for cleanup in (True, False):
            with self.subTest(cleanup=cleanup):
                root = self.root / ('repo-' + str(cleanup)); root.mkdir()
                (root / '.github').mkdir()
                (root / '.github/ci-evidence-recipient.asc').write_bytes(b'public-key-model')
                output = self.root / ('output-' + str(cleanup))
                private = self.root / ('private-' + str(cleanup)); private.mkdir()
                report = root / 'build/reports/ci-component'; report.mkdir(parents=True)
                (report / 'jvm-windows.json').write_text(json.dumps({'component': 'jvm-windows',
                    'tasks': [{'task': 'component-setup', 'exitCode': 125}], 'exitCode': 125}))
                def command(argv, **kwargs):
                    directory = kwargs['private']; directory.mkdir()
                    (directory / 'stdout.log').write_bytes(b'PRIVATE_BODY\n')
                    (directory / 'stderr.log').write_bytes(b'PRIVATE_ERROR\n')
                    return {'code': 'COMMAND_FAILED', 'exitCode': 125, 'timedOut': False, 'cleanupKnown': True}
                error = E.EvidenceError('ENCRYPTION')
                error.encryption_diagnostic = {'phase': 'key-show', 'categories': [], 'outcome':
                    {'code': 'SPAWN', 'exitCode': None, 'timedOut': False, 'cleanupKnown': cleanup}}
                captured = io.StringIO()
                with mock.patch.object(E, 'source_identity', return_value=source), \
                        mock.patch.object(E, 'github_identity', return_value={'runId': '123', 'runAttempt': '1'}), \
                        mock.patch.object(E, 'run_command', side_effect=command), \
                        mock.patch.object(E.tempfile, 'mkdtemp', return_value=str(private)), \
                        mock.patch.object(E, 'encrypt_archive', side_effect=error), contextlib.redirect_stderr(captured):
                    result = E.main(['--component', 'jvm-windows', '--timeout-seconds', '5',
                        '--output-dir', str(output), '--source-root', str(root), '--', 'model-command'])
                self.assertEqual(result, 1)
                self.assertEqual([p.name for p in output.iterdir()], ['failure.json'])
                failure = json.loads((output / 'failure.json').read_text())
                self.assertEqual(failure['kind'], 'CI_EVIDENCE_FAILURE')
                self.assertEqual(failure['source'], source)
                self.assertEqual(failure['taskResults'], [{'task': 'component-setup', 'exitCode': 125}])
                self.assertEqual(failure['encryptionDiagnostic'], error.encryption_diagnostic)
                self.assertNotIn('PRIVATE', json.dumps(failure))
                self.assertNotIn('PRIVATE', captured.getvalue())
                self.assertEqual(private.exists(), not cleanup)
                # Exercise the actual existing consumer: even a correctly hashed
                # immutable archive of this diagnostic cannot qualify a component.
                import ci_qualification as Q
                import zipfile
                archive = self.root / ('failure-' + str(cleanup) + '.zip')
                with zipfile.ZipFile(archive, 'x') as zipped:
                    zipped.write(output / 'failure.json', 'failure.json')
                artifact = {'size_in_bytes': archive.stat().st_size,
                            'digest': 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()}
                api = mock.Mock()
                api.download.side_effect = lambda _artifact, destination: destination.write_bytes(archive.read_bytes())
                with self.assertRaisesRegex(Q.AdmissionError, '^Unexpected record ZIP members$'):
                    Q.read_archive(api, artifact, evidence=True)

    def test_cleanup_exception_cannot_escape_finite_failure_diagnostic(self):
        diagnostic = io.StringIO()
        output = self.root / "public"
        with mock.patch.object(E, "source_identity", side_effect=RuntimeError("PRIVATE_SOURCE")), \
                mock.patch.object(Path, "unlink", side_effect=OSError("PRIVATE_CLEANUP_PATH")), \
                contextlib.redirect_stderr(diagnostic):
            result = E.main(["--component", "source", "--timeout-seconds", "5", "--output-dir", str(output),
                             "--source-root", str(self.root / "not-output"), "--", sys.executable, "-c", "pass"])
        self.assertEqual(result, 1)
        self.assertEqual(diagnostic.getvalue(), "CI_EVIDENCE FAIL SOURCE INPUT\nCI_EVIDENCE CLEANUP UNKNOWN\n")

    def test_task_diagnostic_admits_only_fixed_names_and_integral_exit_codes(self):
        directory = self.root / "build/reports/ci-component"
        directory.mkdir(parents=True)
        target = directory / "source.json"
        self.assertIsNone(E.component_tasks(self.root, "source"))
        record = {"component": "source", "tasks": [{"task": "wrapper", "exitCode": 7}], "exitCode": 7}
        target.write_text(json.dumps(record))
        self.assertEqual(E.component_tasks(self.root, "source"), [{"task": "wrapper", "exitCode": 7}])
        for row in ({"task": "PRIVATE_TEXT", "exitCode": 7}, {"task": "wrapper", "exitCode": True},
                    {"task": "wrapper", "exitCode": "PRIVATE_TEXT"}, {"task": "wrapper", "exitCode": 2**40},
                    {"task": "wrapper", "exitCode": 7, "private": "NEVER_PUBLIC"}):
            with self.subTest(row=row):
                target.write_text(json.dumps({**record, "tasks": [row]}))
                self.assertIsNone(E.component_tasks(self.root, "source"))
        target.write_text("PRIVATE_NOT_JSON")
        self.assertIsNone(E.component_tasks(self.root, "source"))

    def test_task_diagnostic_names_cover_every_actual_component_route(self):
        import ci_component
        observed = {name for component in ci_component.COMPONENTS
                    for name, _argv in ci_component.commands(component)}
        self.assertEqual(set(), observed - E.TASK_NAMES)
        self.assertTrue({"prepare-android", "prepare-desktop", "inspect-android", "inspect-desktop",
                         "component-setup", "gradle-stop"} <= E.TASK_NAMES)


if __name__ == "__main__":
    unittest.main(failfast=True)
