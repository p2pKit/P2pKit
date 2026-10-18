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
import uuid
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import ci_evidence as E

PUBLIC_FINGERPRINT = "0A996D2BC19518FB50071A95D3FDADA57CFB7E1F"


class EvidenceTests(unittest.TestCase):
    def test_rpc_msi_path_mismatch_projection_accepts_only_original_bounded_metadata(self):
        value = {"imageFiles": 50, "msiFiles": 45, "missingFiles": 35, "extraFiles": 30,
                 "caseFoldEqual": False,
                 "missingNameSha256": [format(i, "064x") for i in range(16)],
                 "extraNameSha256": [format(i, "064x") for i in range(16, 32)]}
        line = "RPC_WINDOWS_PACKAGE_PATHS " + json.dumps(value, sort_keys=True, separators=(",", ":")) + "\r\n"
        self.assertLess(len(line), 4096)
        for reports in (False, True):
            (self.root / "stderr.log").write_bytes(line.encode())
            result = E.failure_diagnostics(self.root, self.root, include_reports=reports)
            self.assertEqual(result["rpcWindowsPackagePathMismatch"], value)
            self.assertEqual(result["categories"], [])  # Observations cannot fabricate success/failure authority.
        (self.root / "stderr.log").write_text(line + line)
        self.assertNotIn("rpcWindowsPackagePathMismatch", E.failure_diagnostics(self.root, self.root))
        (self.root / "stderr.log").write_text("RPC_WINDOWS_PACKAGE_REFUSAL_RECORD_FAILED\n" + line)
        result = E.failure_diagnostics(self.root, self.root)
        self.assertEqual(result["categories"], ["RPC_MSI_REFUSAL_RECORD_FAILED"])
        self.assertEqual(result["rpcWindowsPackagePathMismatch"], value)

    def test_rpc_msi_path_mismatch_projection_rejects_private_incoherent_or_duplicate_fields(self):
        value = {"imageFiles": 2, "msiFiles": 2, "missingFiles": 1, "extraFiles": 1,
                 "caseFoldEqual": False, "missingNameSha256": ["a" * 64], "extraNameSha256": ["b" * 64]}
        mutations = (("PRIVATE", "PRIVATE_INPUT"), ("imageFiles", True), ("imageFiles", 50001),
                     ("msiFiles", 3), ("missingFiles", -1), ("caseFoldEqual", 1),
                     ("missingNameSha256", []), ("missingNameSha256", ["PRIVATE"]),
                     ("extraNameSha256", ["a" * 64]), ("extraNameSha256", ["A" * 64]),
                     ("missingNameSha256", ["a" * 64] * 17))
        raws = [json.dumps({**value, key: other}, sort_keys=True, separators=(",", ":"))
                for key, other in mutations]
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        raws.extend([canonical.replace('"imageFiles":2', '"imageFiles":1,"imageFiles":2'),
                     " " + canonical, canonical + " PRIVATE", canonical + "x" * 4096])
        for raw in raws:
            with self.subTest(raw=raw[:100]):
                (self.root / "stderr.log").write_text("RPC_WINDOWS_PACKAGE_PATHS " + raw + "\n")
                result = E.failure_diagnostics(self.root, self.root, include_reports=False)
                self.assertNotIn("rpcWindowsPackagePathMismatch", result)
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_rpc_msi_diagnostics_parse_finite_producer_codes_and_locations(self):
        for category in E.RPC_PACKAGE_ERRORS.values():
            for include_reports in (False, True):
                with self.subTest(category=category, reports=include_reports):
                    (self.root / "stderr.log").write_bytes((
                        "RPC_WINDOWS_PACKAGE_FAILURE " + category + "\r\n"
                        "RPC_WINDOWS_PACKAGE_CHECK_LINES 389,257,39\r\n"
                        "RPC_WINDOWS_PACKAGE_INSPECTION_REFUSED\r\n").encode())
                    result = E.failure_diagnostics(self.root, self.root, include_reports=include_reports)
                    self.assertEqual(result["categories"], [category])
                    self.assertEqual(result["rpcWindowsPackageCheckLines"], [389, 257, 39])

    def test_rpc_msi_diagnostics_reject_unknown_private_and_unbounded_fields(self):
        rows = (
            "RPC_WINDOWS_PACKAGE_FAILURE PRIVATE", "RPC_WINDOWS_PACKAGE_FAILURE RPC_MSI_PAYLOAD_BYTES PRIVATE",
            " RPC_WINDOWS_PACKAGE_FAILURE RPC_MSI_PAYLOAD_BYTES", "RPC_WINDOWS_PACKAGE_FAILURE RPC_MSI_PAYLOAD_BYTES ",
            "ValueError: MSI application payload differs from completed image", "raise ValueError('PRIVATE')",
            '  File "PRIVATE/another.py", line 39, in main',
            "RPC_WINDOWS_PACKAGE_CHECK_LINES 39,0", "RPC_WINDOWS_PACKAGE_CHECK_LINES 100000",
            "RPC_WINDOWS_PACKAGE_CHECK_LINES -1", "RPC_WINDOWS_PACKAGE_CHECK_LINES 39 PRIVATE",
            "RPC_WINDOWS_PACKAGE_CHECK_LINES " + ",".join("39" for _ in range(17)),
            "RPC_WINDOWS_PACKAGE_CHECK_LINES 39" + "x" * 4096,
        )
        for row in rows:
            with self.subTest(row=row[:90]):
                (self.root / "stderr.log").write_text(row + "\n")
                result = E.failure_diagnostics(self.root, self.root, include_reports=False)
                self.assertEqual(result["categories"], [])
                self.assertNotIn("rpcWindowsPackageCheckLines", result)
                self.assertNotIn("PRIVATE", json.dumps(result))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-evidence-test-")
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, program, **options):
        return E.run_command([sys.executable, "-I", "-B", "-c", program], cwd=self.root,
            environment=dict(os.environ), private=self.root / "command", timeout=options.pop("timeout", 5),
            **options)

    def test_consumer_discovery_diagnostics_retain_only_finite_passive_observations(self):
        row = ("CONSUMER_DISCOVERY_SNAPSHOT INDEX 0 LISTENERS 2 ADDED 4 RESOLVED 3 "
               "OTHER_ADDED 2 OTHER_RESOLVED 1 REMOTE_SRV 1 REMOTE_TXT 1 PEERS 0 SEES_OTHER 0\n")
        (self.root / "stdout.log").write_text(row + row.replace("INDEX 0", "INDEX 1") +
            "consumer-lan failedPhase=await-peer-0 errorType=TimeoutCancellationException\n" +
            "> Task :lanJvm:runEmbeddedJmdnsPomSmoke FAILED\n")
        result = E.failure_diagnostics(self.root, self.root, include_reports=False)
        self.assertEqual(result["consumerDiscoverySnapshots"], [dict(index=index, listeners=2, added=4, resolved=3,
            other_added=2, other_resolved=1, remote_srv=1, remote_txt=1, peers=0, sees_other=0) for index in (0, 1)])
        self.assertEqual(result["categories"], ["CONSUMER_TIMEOUT_AWAIT_PEER_0"])
        self.assertEqual(result["failedGradleTasks"], [":lanJvm:runEmbeddedJmdnsPomSmoke"])
        self.assertLess(len(json.dumps(result)), 1200)

    def test_consumer_diagnostics_refuse_duplicates_malformed_counts_and_private_suffixes(self):
        row = ("CONSUMER_DISCOVERY_SNAPSHOT INDEX 0 LISTENERS 2 ADDED 4 RESOLVED 3 "
               "OTHER_ADDED 2 OTHER_RESOLVED 1 REMOTE_SRV 1 REMOTE_TXT 1 PEERS 0 SEES_OTHER 0\n")
        for bad in (row.replace("INDEX 0", "INDEX 2"), row.replace("ADDED 4", "ADDED 4097", 1),
                    row.replace("OTHER_RESOLVED 1", "OTHER_RESOLVED 3"), row.replace("REMOTE_SRV 1", "REMOTE_SRV 2"),
                    row.rstrip() + " PRIVATE_ID\n", row.replace("LISTENERS 2", "LISTENERS 33")):
            with self.subTest(bad=bad):
                (self.root / "stdout.log").write_text(bad +
                    "consumer-lan failedPhase=PRIVATE_ID errorType=TimeoutCancellationException\n" +
                    "CONSUMER_DISCOVERY_SNAPSHOT_UNAVAILABLE PRIVATE_ID\n")
                result = E.failure_diagnostics(self.root, self.root, include_reports=False)
                self.assertNotIn("consumerDiscoverySnapshots", result)
                self.assertNotIn("PRIVATE_ID", json.dumps(result))
                self.assertEqual(result["categories"], [])
        (self.root / "stdout.log").write_text(row + row.replace("PEERS 0", "PEERS 1") +
            "CONSUMER_DISCOVERY_SNAPSHOT_UNAVAILABLE\n")
        result = E.failure_diagnostics(self.root, self.root, include_reports=False)
        self.assertEqual(result["consumerDiscoverySnapshots"], [])
        self.assertEqual(result["categories"], ["CONSUMER_DISCOVERY_SNAPSHOT_UNAVAILABLE"])

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
        real = E._command_scope
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
        with mock.patch.object(E, "_command_scope", supplier):
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
        with mock.patch.object(E, "_command_scope", return_value=scope):
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
                with mock.patch.object(E, "_command_scope", return_value=scope), \
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
                with mock.patch.object(E, "_command_scope", return_value=scope), \
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
        def encrypt(archive, target, key_raw, expected_sha, expected_fingerprint, work, environment, *, cancelled):
            self.assertTrue(callable(cancelled))
            self.assertFalse(cancelled())
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
                def diagnostic(_root, _private, _output, _env, **_kwargs):
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

    def test_nested_failure_keeps_finite_encryption_phase_and_original_failure(self):
        class PrivateExceptionName(RuntimeError):
            pass
        for problem in ("import", "encrypt-cleanup", "filesystem", "unknown"):
            with self.subTest(problem=problem):
                case = self.root / problem; case.mkdir()
                repo = case / "repo"; repo.mkdir()
                private = case / "private"; private.mkdir()
                outcome = {"code": "COMMAND_FAILED", "exitCode": 1, "cleanupKnown": False,
                           "capturesClosed": True, "timedOut": False}
                error = (OSError("PRIVATE_PATH") if problem == "filesystem" else
                         PrivateExceptionName("PRIVATE_SECRET") if problem == "unknown" else E.EvidenceError("ENCRYPTION"))
                nested = None
                if type(error) is E.EvidenceError:
                    nested = {"phase": "key-import" if problem == "import" else "encrypt",
                              "outcome": {"code": "COMMAND_FAILED", "exitCode": 2, "timedOut": False,
                                          "cleanupKnown": problem == "import", "capturesClosed": True},
                              "categories": ["AGENT_UNAVAILABLE"] if problem == "import" else []}
                    error.encryption_diagnostic = nested
                else:
                    error.encryption_diagnostic = {"PRIVATE_NOT_SOURCE_OWNED": "PRIVATE_SECRET"}
                output = case / "output"
                with mock.patch.object(E, "source_identity", return_value={"commit": "a" * 40}), \
                        mock.patch.object(E, "github_identity", return_value={}), \
                        mock.patch.object(E, "run_command", return_value=outcome), \
                        mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                        mock.patch.object(E, "encrypt_closed_failure_captures", side_effect=error), \
                        mock.patch.object(E, "failure_diagnostics", return_value={}), \
                        contextlib.redirect_stderr(io.StringIO()) as public:
                    result = E.main(["--component", "bundle-diagnostic", "--timeout-seconds", "5",
                                     "--output-dir", str(output), "--source-root", str(repo), "--", "synthetic"])
                failure = json.loads((output / "failure.json").read_text())
                self.assertEqual(result, 1)
                self.assertEqual(failure["outcome"], outcome)
                self.assertEqual((failure["stage"], failure["code"]), ("COMMAND", "CLEANUP"))
                self.assertIsNone(failure["encryptionDiagnostic"])
                self.assertIsNone(failure["taskResults"])
                self.assertEqual(failure["closedCaptureFailure"], {
                    "code": "ENCRYPTION" if nested is not None else "INPUT",
                    "exception": "EvidenceError" if nested is not None else "OSError" if problem == "filesystem" else "UNKNOWN",
                    "encryptionDiagnostic": nested})
                self.assertEqual({p.name for p in output.iterdir()}, {"failure.json"})
                self.assertTrue(private.is_dir())
                self.assertNotIn("PRIVATE", json.dumps(failure) + public.getvalue())
                self.assertNotIn("PrivateExceptionName", json.dumps(failure) + public.getvalue())
                self.assertIn("DIAGNOSTIC_ENCRYPTION_FAILED", public.getvalue())

    def test_nested_receipt_failure_preserves_first_receipt_without_cipher_attachment(self):
        for replacement_fails in (1, 2):
            with self.subTest(replacement_fails=replacement_fails):
                case = self.root / str(replacement_fails); case.mkdir()
                repo = case / "repo"; repo.mkdir()
                private = case / "private"; private.mkdir()
                output = case / "output"
                outcome = {"code": "COMMAND_FAILED", "exitCode": 1, "cleanupKnown": False,
                           "capturesClosed": True, "timedOut": False}
                def encrypted(*_args, **_kwargs):
                    (output / "evidence.tar.gz.gpg").write_bytes(b"SYNTHETIC_CIPHER")
                    return {"kind": "CLOSED_CAPTURES_ONLY_NOT_QUALIFICATION"}
                original_replace = E.os.replace
                calls = []
                def replace(source, target):
                    calls.append((source, target))
                    if len(calls) <= replacement_fails:
                        raise OSError("PRIVATE_REPLACEMENT_PATH")
                    original_replace(source, target)
                with mock.patch.object(E, "source_identity", return_value={"commit": "a" * 40}), \
                        mock.patch.object(E, "github_identity", return_value={}), \
                        mock.patch.object(E, "run_command", return_value=outcome), \
                        mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                        mock.patch.object(E, "encrypt_closed_failure_captures", side_effect=encrypted), \
                        mock.patch.object(E, "failure_diagnostics", return_value={}), \
                        mock.patch.object(E.os, "replace", side_effect=replace), \
                        contextlib.redirect_stderr(io.StringIO()) as public:
                    result = E.main(["--component", "bundle-diagnostic", "--timeout-seconds", "5",
                                     "--output-dir", str(output), "--source-root", str(repo), "--", "synthetic"])
                failure = json.loads((output / "failure.json").read_text())
                self.assertEqual(result, 1)
                self.assertEqual(len(calls), 2)
                self.assertEqual(failure["outcome"], outcome)
                self.assertNotIn("closedCaptureArchive", failure)
                self.assertEqual({p.name for p in output.iterdir()}, {"failure.json"})
                if replacement_fails == 1:
                    self.assertEqual(failure["closedCaptureFailure"],
                                     {"code": "INPUT", "exception": "OSError", "encryptionDiagnostic": None})
                else:
                    self.assertNotIn("closedCaptureFailure", failure)
                    self.assertIn("DIAGNOSTIC_RECEIPT_UPDATE_FAILED", public.getvalue())
                self.assertTrue(private.is_dir())
                self.assertNotIn("PRIVATE", json.dumps(failure) + public.getvalue())

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
                with mock.patch.object(E, "_command_scope", return_value=scope), \
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
        with mock.patch.object(E, "_command_scope", return_value=scope):
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
        with mock.patch.object(E, "_command_scope", return_value=scope):
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
                with mock.patch.object(E, "_command_scope", return_value=scope), \
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

    def test_dependency_terminal_errors_project_only_exact_maintained_labels(self):
        command = self.root / "dependency-markers"; command.mkdir()
        stdout = command / "stdout.log"
        for label in E.DEPENDENCY_UPDATE_ERRORS | E.DEPENDENCY_UPDATE_EXCEPTIONS:
            stdout.write_text("DEPENDENCY_UPDATE_FAILED: " + label + "\n")
            result = E.failure_diagnostics(self.root, command, include_reports=False)
            prefix = "DEPENDENCY_UPDATE_" if label in E.DEPENDENCY_UPDATE_ERRORS else "DEPENDENCY_UPDATE_EXCEPTION_"
            self.assertEqual(result['categories'], [prefix + label])
            self.assertNotIn('dependencyUpdateExits', result)
        for line in ("DEPENDENCY_UPDATE_FAILED: PRIVATE", "DEPENDENCY_UPDATE_FAILED: SOURCE_DIRTY PRIVATE",
                     "PRIVATE PREFIX DEPENDENCY_UPDATE_FAILED: SOURCE_DIRTY", "DEPENDENCY_UPDATE_FAILED: " + "x" * 4096):
            stdout.write_text(line + "\n")
            self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)['categories'], [])

    def test_dependency_returned_exits_survive_closed_capture_only_diagnosis(self):
        command = self.root / "dependency-steps"; command.mkdir()
        stdout = command / "stdout.log"
        for newline in ("\n", "\r\n"):
            stdout.write_bytes(("DEPENDENCY_UPDATE_STEP GENERATOR EXIT 7" + newline +
                                "DEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT 0" + newline +
                                "DEPENDENCY_UPDATE_FAILED: GENERATION_OR_GRADLE_STOP_FAILED" + newline).encode())
            with mock.patch.object(E, 'junit_failures', side_effect=AssertionError('live report read')):
                result = E.failure_diagnostics(self.root, command, include_reports=False)
            self.assertEqual(result['dependencyUpdateExits'], {'GENERATOR': 7, 'GRADLE_STOP': 0})
            self.assertEqual(result['categories'], ['DEPENDENCY_UPDATE_GENERATION_OR_GRADLE_STOP_FAILED'])
            self.assertEqual(result['platformTests'], [])
            with mock.patch.object(E, 'junit_failures', return_value=[]):
                self.assertEqual(E.failure_diagnostics(self.root, command)['dependencyUpdateExits'],
                                 result['dependencyUpdateExits'])
        stdout.write_text('DEPENDENCY_UPDATE_STEP GENERATOR EXIT -2147483648\nDEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT 4294967295\n')
        self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)['dependencyUpdateExits'],
                         {'GENERATOR': -(2**31), 'GRADLE_STOP': 2**32-1})

    def test_dependency_exit_projection_refuses_private_noncanonical_duplicate_and_oversize(self):
        command = self.root / "dependency-invalid"; command.mkdir()
        stdout = command / "stdout.log"
        for line in ('DEPENDENCY_UPDATE_STEP PRIVATE EXIT 0',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT PRIVATE',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT 0 PRIVATE',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT True',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT +1',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT 01',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT -0',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT -2147483649',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT 4294967296',
                     'DEPENDENCY_UPDATE_STEP GENERATOR EXIT ' + '9' * 4096):
            stdout.write_text(line + '\n')
            result = E.failure_diagnostics(self.root, command, include_reports=False)
            self.assertNotIn('dependencyUpdateExits', result)
            self.assertNotIn('PRIVATE', json.dumps(result))
        stdout.write_text('DEPENDENCY_UPDATE_STEP GENERATOR EXIT 0\nDEPENDENCY_UPDATE_STEP GENERATOR EXIT 0\n')
        self.assertNotIn('dependencyUpdateExits', E.failure_diagnostics(self.root, command, include_reports=False))
        stdout.write_text('DEPENDENCY_UPDATE_STEP GENERATOR EXIT 7\nDEPENDENCY_UPDATE_STEP GENERATOR EXIT 4294967296\nDEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT 0\n')
        self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)['dependencyUpdateExits'],
                         {'GRADLE_STOP': 0})

    def test_fixed_generator_phases_and_root_tasks_are_diagnostic_only(self):
        command = self.root / "generator-phases"; command.mkdir()
        stdout = command / "stdout.log"
        expected = {"WRAPPER", "GENERATE", "INTEGRITY", "STRICT", "PROVENANCE", "DIFF"}
        self.assertEqual(set(E.DEPENDENCY_GENERATOR_PHASES), expected)
        for code in (0, 1, 143, 255):
            for newline in ("\n", "\r\n"):
                stdout.write_bytes((newline.join(f"DEPENDENCY_GENERATOR_PHASE {phase} EXIT {code}"
                                                for phase in sorted(expected)) + newline +
                                    "> Task :resolveAndLockAll FAILED" + newline +
                                    "> Task :verifyBuildPluginSecurityFloors FAILED" + newline +
                                    "> Task :help FAILED" + newline).encode())
                with mock.patch.object(E, "junit_failures", side_effect=AssertionError("private report read")):
                    result = E.failure_diagnostics(self.root, command, include_reports=False)
                self.assertEqual(result["dependencyGeneratorPhases"], {phase: code for phase in expected})
                self.assertEqual(result["failedGradleTasks"], [":help", ":resolveAndLockAll", ":verifyBuildPluginSecurityFloors"])
                self.assertEqual(result["failedSourceTests"], [])
                self.assertNotIn("outcome", result)

    def test_generator_phase_projection_rejects_unknown_private_duplicate_and_invalid_exit(self):
        command = self.root / "bad-generator-phases"; command.mkdir()
        stdout = command / "stdout.log"
        for line in ("DEPENDENCY_GENERATOR_PHASE PRIVATE EXIT 0",
                     "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT 0 PRIVATE",
                     "PRIVATE DEPENDENCY_GENERATOR_PHASE GENERATE EXIT 0",
                     "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT 01",
                     "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT -1",
                     "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT 256",
                     "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT " + "9" * 4096,
                     "> Task :PRIVATE FAILED", "> Task :resolveAndLockAll FAILED PRIVATE"):
            stdout.write_text(line + "\n")
            result = E.failure_diagnostics(self.root, command, include_reports=False)
            self.assertNotIn("dependencyGeneratorPhases", result)
            self.assertEqual(result["failedGradleTasks"], [])
            self.assertNotIn("PRIVATE", json.dumps(result))
        stdout.write_text("DEPENDENCY_GENERATOR_PHASE WRAPPER EXIT 0\n"
                          "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT 7\n"
                          "DEPENDENCY_GENERATOR_PHASE GENERATE EXIT 0\n")
        self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)["dependencyGeneratorPhases"],
                         {"WRAPPER": 0})

    def test_static_dependency_failure_catalog_is_exact_source_owned_not_private_text(self):
        command = self.root / "dependency-fatal"; command.mkdir()
        stdout = command / "stdout.log"
        scripts = Path(__file__).resolve().parents[1]
        sources = "\n".join((scripts / name).read_text() for name in
                            ("review-dependency-verification.sh", "check-dependency-verification.sh"))
        for text, category in E.DEPENDENCY_FATAL_MESSAGES.items():
            self.assertIn('fail "' + text + '"', sources)
            stdout.write_text("FATAL: " + text + "\n")
            self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)["categories"], [category])
            for changed in ("FATAL: " + text + " PRIVATE\n", "PRIVATE FATAL: " + text + "\n"):
                stdout.write_text(changed)
                result = E.failure_diagnostics(self.root, command, include_reports=False)
                self.assertEqual(result["categories"], [])
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_dependency_error_allowlist_covers_literal_adapter_refusals(self):
        import ast
        source = ast.parse((Path(__file__).resolve().parents[1] / 'dependency_update.py').read_text())
        labels = {node.args[1].value for node in ast.walk(source) if isinstance(node, ast.Call) and
                  isinstance(node.func, ast.Name) and node.func.id == 'need' and len(node.args) == 2 and
                  isinstance(node.args[1], ast.Constant)}
        self.assertEqual(labels, set(E.DEPENDENCY_UPDATE_ERRORS))

    def test_closed_phase_diagnostics_preserve_finite_values_without_report_reads(self):
        command = self.root / "phase-command"
        command.mkdir()
        labels = ("simulator-macos-version", "simulator-xcode-version", "simulator-first-launch",
                  "simulator-runtimes", "intel-bootstatus-help", "simulator-devices", "intel-boot",
                  "intel-bootstatus", "intel-prelaunch", "intel-retire-before", "intel-shutdown", "intel-retire-after")
        for code in (None, -255, -15, 0, 1, 255):
            for ending in ("\n", "\r\n", ""):
                for label in labels:
                    line = f"INTEL_PHASE_RESULT {label} EXIT " + ("null" if code is None else str(code))
                    (command / "stdout.log").write_text(line + " TIMEOUT 1 OVERFLOW 0 DRAINED 1" + ending)
                    with self.subTest(code=code, ending=ending, label=label), \
                            mock.patch.object(E, "read_json", side_effect=AssertionError("NO_MUTABLE_REPORT_READ")):
                        result = E.failure_diagnostics(self.root, command, include_reports=False)
                    self.assertEqual(result["simulatorPhases"], [{"label": label, "exitCode": code,
                        "timedOut": True, "outputLimitExceeded": False, "ownedGroupDrained": True}])

    def test_closed_phase_diagnostics_reject_malformed_private_suffixes_and_duplicates(self):
        command = self.root / "phase-negative-command"
        command.mkdir()
        good = "INTEL_PHASE_RESULT intel-boot EXIT 1 TIMEOUT 0 OVERFLOW 0 DRAINED 1"
        mutations = [good + " private-secret", good + " ", "prefix " + good,
                     good.replace("intel-boot", "private-label"), good.replace("EXIT 1", "EXIT true"),
                     good.replace("EXIT 1", "EXIT 01"), good.replace("EXIT 1", "EXIT -0"),
                     good.replace("EXIT 1", "EXIT 256"), good.replace("EXIT 1", "EXIT -256"),
                     good.replace("EXIT 1", "EXIT 1000000"), good.replace("TIMEOUT 0", "TIMEOUT 2"),
                     good.replace("OVERFLOW 0", "OVERFLOW false"), good.replace("DRAINED 1", "DRAINED true")]
        for line in mutations:
            (command / "stdout.log").write_text(line + "\n")
            with self.subTest(line=line):
                result = E.failure_diagnostics(self.root, command, include_reports=False)
                self.assertEqual(result["simulatorPhases"], [])
                self.assertNotIn("private", json.dumps(result))
        other = good.replace("intel-boot", "intel-shutdown")
        for repeated in (good, good.replace("EXIT 1", "EXIT 2")):
            (command / "stdout.log").write_text(good + "\n" + other + "\n")
            (command / "stderr.log").write_text(repeated + "\n")
            for include_reports in (False, True):
                with self.subTest(repeated=repeated, include_reports=include_reports):
                    result = E.failure_diagnostics(self.root, command, include_reports=include_reports)
                    self.assertEqual([row["label"] for row in result["simulatorPhases"]], ["intel-shutdown"])

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

    def test_bundle_fatal_diagnostics_only_admit_exact_existing_source_literals(self):
        command = self.root / "bundle-fatal-command"
        command.mkdir()
        log = command / "stderr.log"
        maintained = ((SCRIPTS / "build-central-portal-bundle.sh").read_text() +
                      (SCRIPTS / "tests/build-central-portal-bundle-test.sh").read_text())
        self.assertEqual(len(E.BUNDLE_FATAL_MESSAGES), 20)
        for message, category in E.BUNDLE_FATAL_MESSAGES.items():
            self.assertIn(message, maintained)
            for ending in ("\n", "\r\n", ""):
                with self.subTest(message=message, ending=repr(ending)):
                    log.write_bytes(("FATAL: " + message + ending).encode())
                    result = E.failure_diagnostics(self.root, command, include_reports=False)
                    self.assertEqual(result["categories"], [category])
                    self.assertNotIn(message, json.dumps(result))

    def test_bundle_fatal_diagnostics_reject_private_or_variable_extensions(self):
        command = self.root / "bundle-fatal-negative"
        command.mkdir()
        log = command / "stderr.log"
        for message in E.BUNDLE_FATAL_MESSAGES:
            for changed in (message + " PRIVATE_SECRET", "PRIVATE_SECRET " + message,
                            message + " ", message.lower() if message.lower() != message else message.upper()):
                log.write_text("FATAL: " + changed + "\n")
                result = E.failure_diagnostics(self.root, command, include_reports=False)
                self.assertEqual(result["categories"], [])
                self.assertNotIn("PRIVATE_SECRET", json.dumps(result))
        for message in ("refusing to overwrite existing output: /private/PRIVATE_SECRET",
                        "expected published group directory is missing: /private/PRIVATE_SECRET",
                        "1 of 117 publication files lack PGP signatures", "x" * 5000):
            log.write_text("FATAL: " + message + "\n")
            self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)["categories"], [])

    def test_current_central_inventory_retains_exact_121_with_tooling_sidecars(self):
        command = self.root / "current-inventory"
        command.mkdir()
        (command / "stderr.log").write_text(
            "CENTRAL_INVENTORY EXPECTED 121 OBSERVED 121 MISSING 0 EXTRA 0 JAR 0 AAR 0 KLIB 0 POM 0 "
            "MODULE 0 MAVEN_METADATA 0 RESOLVER_METADATA 0 OTHER 0\n")
        result = E.failure_diagnostics(self.root, command, include_reports=False)["centralInventory"]
        self.assertEqual((result["expected"], result["observed"], result["missing"], result["extra"]), (121, 121, 0, 0))

    def test_central_signature_counts_report_actual_loop_not_inventory_reconstruction(self):
        command = self.root / "signature-counts"
        command.mkdir()
        log = command / "stderr.log"
        line = "CENTRAL_SIGNATURE_COUNTS CHECKED 116 UNSIGNED 1 INVALID 2"
        log.write_text(line + "\n")
        self.assertEqual(E.failure_diagnostics(self.root, command, include_reports=False)["centralSignatureCounts"],
                         {"checked": 116, "unsigned": 1, "invalid": 2})
        for bad in (line + " PRIVATE", line.replace("116", "2"), line.replace("116", "9999"), line + "\n" + line):
            log.write_text(bad + "\n")
            self.assertNotIn("centralSignatureCounts", E.failure_diagnostics(self.root, command, include_reports=False))

    def test_central_inventory_diagnostic_is_finite_and_arithmetically_consistent(self):
        command = self.root / "inventory-command"
        command.mkdir()
        log = command / "stderr.log"
        line = ("CENTRAL_INVENTORY EXPECTED 117 OBSERVED 118 MISSING 0 EXTRA 1 JAR 0 AAR 0 KLIB 0 POM 0 "
                "MODULE 0 MAVEN_METADATA 0 RESOLVER_METADATA 1 OTHER 0")
        log.write_text(line + "\n")
        result = E.failure_diagnostics(self.root, command, include_reports=False)["centralInventory"]
        self.assertEqual(result["observed"], 118)
        self.assertEqual(result["resolver_metadata"], 1)
        for bad in (line + " PRIVATE", line.replace("118", "119"), line.replace("118", "9999"),
                    line.replace("117", "116"), line.replace("OTHER 0", "OTHER 1"),
                    line.replace("MISSING 0", "MISSING 118"), line.replace("JAR 0", "JAR -1")):
            with self.subTest(bad=bad):
                log.write_text(bad + "\n")
                self.assertNotIn("centralInventory", E.failure_diagnostics(self.root, command, include_reports=False))
        log.write_text(line + "\n" + line + "\n")
        self.assertNotIn("centralInventory", E.failure_diagnostics(self.root, command, include_reports=False))

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

    def test_junit_standard_jvm_test_sources_retain_source_binding_and_privacy(self):
        relative_sources = (
            "samples/p2p-sample-desktop/src/test/kotlin/dev/p2pkit/StandardTest.kt",
            "library/p2p-network-provisioning-desktop/src/test/kotlin/dev/p2pkit/StandardTest.kt",
        )
        main_source = "samples/p2p-sample-desktop/src/main/kotlin/dev/p2pkit/StandardTest.kt"
        content = "package dev.p2pkit\nclass StandardTest { fun actualCase() {} }\n"
        for relative in (*relative_sources, main_source):
            source = self.root / relative
            source.parent.mkdir(parents=True)
            source.write_text(content)
        report = self.root / "samples/p2p-sample-desktop/build/test-results/test/TEST-standard.xml"
        report.parent.mkdir(parents=True)
        xml = ('<testsuite><testcase classname="dev.p2pkit.StandardTest" name="actualCase">'
               '<failure type="kotlinx.coroutines.TimeoutCancellationException" message="PRIVATE_MESSAGE">'
               'PRIVATE_STACK</failure></testcase></testsuite>')
        report.write_text(xml)

        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

        git("init", "--quiet")
        self.assertEqual(E.junit_failures(self.root), [])
        git("add", *relative_sources, main_source)
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Standard JVM source-set fixture")
        original = git("rev-parse", "HEAD").decode().strip()
        expected = [{"source": relative, "test": "actualCase", "kinds": ["TIMEOUT"]}
                    for relative in sorted(relative_sources)]
        result = E.junit_failures(self.root, original)
        self.assertEqual(sorted(result, key=lambda row: row["source"]), expected)
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("src/main", json.dumps(result))
        for before, after in (("actualCase", "private_case"), ("dev.p2pkit.StandardTest", "private.StandardTest"),
                              ("StandardTest", "PrivateTest")):
            with self.subTest(invalid=after):
                report.write_text(xml.replace(before, after))
                self.assertEqual(E.junit_failures(self.root, original), [])
        untracked = self.root / relative_sources[0].replace("StandardTest", "UntrackedTest")
        untracked.write_text(content.replace("StandardTest", "UntrackedTest"))
        report.write_text(xml.replace("StandardTest", "UntrackedTest"))
        self.assertEqual(E.junit_failures(self.root, original), [])
        report.write_text(xml)
        for relative in relative_sources:
            (self.root / relative).write_text(content + "// modified source is not authority\n")
        self.assertEqual(E.junit_failures(self.root, original), [])
        for relative in relative_sources:
            (self.root / relative).write_text(content)
        self.assertEqual(sorted(E.junit_failures(self.root, original), key=lambda row: row["source"]), expected)
        for relative in relative_sources:
            (self.root / relative).unlink()
        # A still-tracked, byte-exact src/main match is not a test-source fallback.
        self.assertEqual(E.junit_failures(self.root, original), [])

    def test_jmdns_junit_details_are_finite_and_bound_to_original_fixture_source(self):
        source = self.root / "library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsCloseLifecycleTest.kt"
        fixture = self.root / "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/JmdnsCloseLifecycleFixture.java"
        source.parent.mkdir(parents=True)
        fixture.parent.mkdir(parents=True)
        source.write_text('package dev.p2pkit.transport.lan\nclass JmdnsCloseLifecycleTest { '
                          'fun realResourceCloseRegressionsExitNaturally() {} '
                          'fun failedSendsCannotMultiplyTheSdkCleanupBudget() {} }\n'
                          '// The real-resource close fixture requires JDK 17\n')
        fixture.write_text('class JmdnsCloseLifecycleFixture { String a="host_not_announced"; '
                           'String b="jdk17_required"; }\n')
        report = self.root / "library/p2p-transport-lan/build/test-results/jvmTest/TEST-close.xml"
        report.parent.mkdir(parents=True)
        def write_failure(message, method="realResourceCloseRegressionsExitNaturally[jvm]"):
            report.write_text('<testsuite><testcase classname="dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest" '
                              'name="' + method + '"><failure type="java.lang.AssertionError">' + message +
                              '</failure></testcase></testsuite>')
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)
        git("init", "--quiet")
        git("add", source.relative_to(self.root).as_posix())
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Public test source")
        write_failure('host_not_announced: java.net.NoRouteToHostException PRIVATE_PAYLOAD /private/path')
        self.assertNotIn('jmdnsFixture', E.junit_failures(self.root)[0])  # Untracked Java is not authority.
        git("add", fixture.relative_to(self.root).as_posix())
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Public fixture source")
        original = git("rev-parse", "HEAD").decode().strip()
        expected = {'sourceDefinedCodes': ['host_not_announced'],
                    'exceptionClasses': ['java.lang.AssertionError', 'java.net.NoRouteToHostException']}
        self.assertEqual(E.junit_failures(self.root, original)[0]['jmdnsFixture'], expected)
        self.assertNotIn('PRIVATE', json.dumps(E.junit_failures(self.root, original)))
        self.assertNotIn('/private/path', json.dumps(E.junit_failures(self.root, original)))
        saved = fixture.read_bytes()
        fixture.write_bytes(saved + b'// changed authority\n')
        self.assertNotIn('jmdnsFixture', E.junit_failures(self.root, original)[0])
        fixture.write_bytes(saved)
        write_failure('host_not_announced_PRIVATE java.net.NoRouteToHostExceptionPRIVATE PRIVATE_CODE')
        self.assertEqual(E.junit_failures(self.root, original)[0]['jmdnsFixture'],
                         {'sourceDefinedCodes': [], 'exceptionClasses': ['java.lang.AssertionError']})
        write_failure('The real-resource close fixture requires JDK 17',
                      'failedSendsCannotMultiplyTheSdkCleanupBudget()')
        self.assertEqual(E.junit_failures(self.root, original)[0]['jmdnsFixture']['sourceDefinedCodes'],
                         ['jdk17_required'])
        fixture.unlink()
        self.assertNotIn('jmdnsFixture', E.junit_failures(self.root, original)[0])

    def jmdns_startup_report(self):
        import xml.etree.ElementTree as ET
        paths = (
            "library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsCloseLifecycleTest.kt",
            "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/JmdnsCloseLifecycleFixture.java",
        )
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True)
            target.write_bytes((SCRIPTS.parent / relative).read_bytes())
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)
        git("init", "--quiet")
        git("add", *paths)
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "--quiet", "-m", "Original public JmDNS test sources")
        original = git("rev-parse", "HEAD").decode().strip()
        report = self.root / "library/p2p-transport-lan/build/test-results/jvmTest/TEST-close.xml"
        report.parent.mkdir(parents=True)
        def observe(text, *, message="", method="realResourceCloseRegressionsExitNaturally[jvm]", failed=True):
            suite = ET.Element("testsuite")
            case = ET.SubElement(suite, "testcase", classname="dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest",
                                 name=method)
            if failed:
                ET.SubElement(case, "failure", type="java.lang.AssertionError", message=message).text = text
            else:
                ET.SubElement(case, "system-out").text = text
            report.write_bytes(ET.tostring(suite))
            return E.junit_failures(self.root, original)
        return observe, paths

    def test_jmdns_startup_markers_preserve_original_finite_observations(self):
        observe, _paths = self.jmdns_startup_report()
        markers = [
            "startup firstSendFailureClass=java.net.NoRouteToHostException firstSendDestinationIpv4Mdns=true",
            "startup interfaceSnapshot=BEFORE_WAIT selectedKnown=true hostKnown=true socketKnown=false "
            "selectedHostMatch=true selectedSocketMatch=UNKNOWN hostSocketMatch=UNKNOWN",
            "startup route observation=POST_FAILURE scope=SELECTED_IPV4_MDNS queryStarted=true "
            "queryCompleted=false exitZero=UNKNOWN",
            "startup route outputWithinBound=false",
            "startup route processReaped=true",
            "startup route queryFailureClass=java.io.IOException",
            "startup route interfaceParsed=false selectedInterfaceMatch=UNKNOWN flagsParsed=true",
            *("startup routeFlag=" + flag + " present=" + value for flag, value in (
                ("UP", "true"), ("REJECT", "true"), ("BLACKHOLE", "false"),
                ("GATEWAY", "false"), ("IFSCOPE", "true"))),
            "startup explicitAddress=false linkLocal=true virtualInterface=false pointToPoint=true",
        ]
        for method in ("realResourceCloseRegressionsExitNaturally[jvm]",
                       "failedSendsCannotMultiplyTheSdkCleanupBudget()"):
            with self.subTest(method=method):
                text = "host_not_announced\n" + "\r\n".join(markers) + "\r\n"
                row = observe(text, message=text, method=method)[0]
                self.assertEqual(row["kinds"], ["ASSERTION"])
                details = row["jmdnsFixture"]
                self.assertEqual(details["sourceDefinedCodes"], ["host_not_announced"])
                self.assertEqual(details["exceptionClasses"],
                                 ["java.io.IOException", "java.lang.AssertionError", "java.net.NoRouteToHostException"])
                self.assertEqual(details["startupMarkers"], sorted(markers))  # Not duplicated by XML message.
                self.assertEqual(set(details), {"sourceDefinedCodes", "exceptionClasses", "startupMarkers"})
        for marker in (
                "startup route queryStarted=false reason=FIRST_SEND_DESTINATION_NOT_MATCHED",
                "startup route queryStarted=false reason=SELECTED_INTERFACE_UNKNOWN"):
            self.assertEqual(observe(marker)[0]["jmdnsFixture"]["startupMarkers"], [marker])
        for value in ("true", "false", "UNKNOWN"):
            marker = "startup firstSendFailureClass=java.net.NoRouteToHostException firstSendDestinationIpv4Mdns=" + value
            self.assertEqual(observe("", message=marker)[0]["jmdnsFixture"]["startupMarkers"], [marker])

    def test_jmdns_startup_markers_refuse_dynamic_text_without_erasing_old_details(self):
        observe, _paths = self.jmdns_startup_report()
        safe = "startup route processReaped=true"
        private = "PRIVATE_PAYLOAD_192.0.2.19"
        invalid = [
            private + safe, safe + private, " " + safe, safe + " ", "\t" + safe,
            private + "\u0085" + safe, private + "\u2028" + safe,
            safe + "\u0085" + private, safe + "\u2029" + private,
            safe + " interface=en999", safe + " address=192.0.2.19", "startup route interface=en999",
            "startup route processReaped=TRUE", "startup route processReaped=trueish",
            "startup route processReaped=UNKNOWN", "startup routeFlag=PRIVATE present=true",
            "startup routeFlag=UP present=true reason=" + private,
            "startup route queryStarted=false reason=" + private,
            "startup route observation=BEFORE_FAILURE scope=SELECTED_IPV4_MDNS queryStarted=true "
            "queryCompleted=true exitZero=true",
            "startup firstSendFailureClass=private.DynamicException firstSendDestinationIpv4Mdns=true",
            "startup firstSendFailureClass=java.net.NoRouteToHostExceptionPrivate firstSendDestinationIpv4Mdns=true",
            "startup diagnosticFailureClass=java.io.IOException",
            "startup route processReaped=" + "t" * 513,
            "startup primitive=PYTHON_IPV4 stage=SEND result=KERNEL_ACCEPTED",
        ]
        for line in invalid:
            with self.subTest(line=line):
                details = observe("host_not_announced\n" + line)[0]["jmdnsFixture"]
                self.assertEqual(details["sourceDefinedCodes"], ["host_not_announced"])
                self.assertNotIn("startupMarkers", details)
                self.assertNotIn(private, json.dumps(details))
                self.assertEqual(observe(line + "\n" + safe)[0]["jmdnsFixture"]["startupMarkers"], [safe])

    def test_jmdns_startup_markers_refuse_oversize_and_conflicting_observations(self):
        observe, _paths = self.jmdns_startup_report()
        safe = "startup route processReaped=true"
        for text in (
                (safe + "\n") * 33,
                "x" * (128 * 1024) + "\n" + safe,
                safe + "\nstartup route processReaped=false",
                "startup route queryStarted=false reason=SELECTED_INTERFACE_UNKNOWN\n"
                "startup route observation=POST_FAILURE scope=SELECTED_IPV4_MDNS queryStarted=true "
                "queryCompleted=true exitZero=true",
                "startup routeFlag=REJECT present=false\nstartup routeFlag=REJECT present=true"):
            with self.subTest(length=len(text)):
                details = observe("host_not_announced\n" + text)[0]["jmdnsFixture"]
                self.assertEqual(details["sourceDefinedCodes"], ["host_not_announced"])
                self.assertEqual(details["exceptionClasses"], ["java.lang.AssertionError"])
                self.assertNotIn("startupMarkers", details)
        self.assertEqual(observe((safe + "\n") * 32)[0]["jmdnsFixture"]["startupMarkers"], [safe])
        self.assertNotIn("startupMarkers", observe(safe, message="x" * (128 * 1024 + 1))[0]["jmdnsFixture"])
        self.assertNotIn("startupMarkers", observe(safe, message=safe.replace("true", "false"))[0]["jmdnsFixture"])

    def test_jmdns_startup_markers_require_original_source_and_actual_failed_case(self):
        observe, paths = self.jmdns_startup_report()
        marker = "startup route processReaped=true"
        self.assertEqual(observe(marker, failed=False), [])
        self.assertEqual(observe(marker, method="privateUntrackedMethod"), [])
        self.assertEqual(observe("host_not_announced")[0]["jmdnsFixture"],
                         {"sourceDefinedCodes": ["host_not_announced"], "exceptionClasses": ["java.lang.AssertionError"]})
        source, fixture = (self.root / relative for relative in paths)
        original = fixture.read_bytes()
        fixture.write_bytes(original + b'\n// startup route processReaped=true\n')
        self.assertNotIn("jmdnsFixture", observe(marker)[0])
        fixture.write_bytes(original)
        self.assertEqual(observe(marker)[0]["jmdnsFixture"]["startupMarkers"], [marker])
        fixture.unlink()
        self.assertNotIn("jmdnsFixture", observe(marker)[0])
        fixture.write_bytes(original)
        source.write_bytes(source.read_bytes() + b'\n// changed original source\n')
        self.assertEqual(observe(marker), [])

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

    def test_hosted_darwin_factory_routes_real_run_command_and_records_boundary(self):
        env = {**dict(os.environ), "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
               "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40,
               "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/fixture"}
        child = mock.Mock(stdout=io.BytesIO(b""), stderr=io.BytesIO(b""), returncode=0)
        child.poll.return_value = 0; child.wait.return_value = 0
        selected = []
        def initialize(scope, *_args):
            selected.append(scope)
            scope.leaders, scope.discovery_errors, scope.pending_discoveries = [child], set(), {}
            scope.outside_domain_observations = 52
            scope.spawn = mock.Mock(return_value=child)
            scope.discover = mock.Mock(return_value=[])
            scope.drain = mock.Mock(return_value=[])
            scope.close = mock.Mock()
        with mock.patch.object(E.platform, "system", return_value="Darwin"), \
                mock.patch.object(E._HostedDarwinScope, "__init__", initialize), \
                mock.patch.object(E.audit_processes, "make_scope", side_effect=AssertionError("WRONG_FACTORY")):
            outcome = E.run_command(["synthetic"], cwd=self.root, environment=env,
                                    private=self.root / "selected-domain", timeout=5)
        self.assertEqual(len(selected), 1)
        self.assertIsInstance(selected[0], E._HostedDarwinScope)
        self.assertEqual(outcome["code"], "PASS")
        self.assertTrue(outcome["cleanupKnown"])
        self.assertTrue(outcome["capturesClosed"])
        self.assertEqual(outcome["ownershipBoundary"], E.HOSTED_DARWIN_BOUNDARY)
        self.assertEqual(outcome["outsideDomainObservations"], 52)
        selected[0].drain.assert_called_once(); selected[0].close.assert_called_once()
        child.wait.assert_called_once()
        with mock.patch.object(E.platform, "system", return_value="Darwin"), \
                mock.patch.object(E.audit_processes, "make_scope", return_value="existing-strict-backend") as original:
            self.assertEqual(E._command_scope("job", "invocation", "private", "home",
                {**env, "RUNNER_ENVIRONMENT": "self-hosted"}), "existing-strict-backend")
        original.assert_called_once_with("job", "invocation", "private", "home")

    def test_hosted_darwin_context_is_fixed_source_workflow_and_host_not_an_optout(self):
        env = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
               "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/fixture",
               "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40}
        with mock.patch.object(E.platform, "system", return_value="Darwin"):
            self.assertTrue(E._hosted_darwin_context(env))
            self.assertTrue(E._hosted_darwin_context({**env, "GITHUB_WORKFLOW_REF":
                "p2pKit/P2pKit/.github/workflows/dependency-update-candidate.yml@refs/heads/fixture"}))
            for change in ({"GITHUB_ACTIONS": "false"}, {"RUNNER_ENVIRONMENT": "self-hosted"},
                           {"GITHUB_REPOSITORY": "other/repository"}, {"GITHUB_WORKFLOW_SHA": "b" * 40},
                           {"GITHUB_SHA": "not-a-sha"}, {"GITHUB_WORKFLOW_REF": "ci.yml"},
                           {"GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/ci.yml@"},
                           {"GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/other.yml@refs/heads/fixture"}):
                with self.subTest(change=change):
                    self.assertFalse(E._hosted_darwin_context({**env, **change}))
        with mock.patch.object(E.platform, "system", return_value="Linux"):
            self.assertFalse(E._hosted_darwin_context(env))

    def test_hosted_darwin_release_context_keeps_fixed_source_and_job_boundary(self):
        env = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', GITHUB_REPOSITORY='p2pKit/P2pKit',
                   GITHUB_SHA='a' * 40, GITHUB_WORKFLOW_SHA='a' * 40)
        with mock.patch.object(E.platform, 'system', return_value='Darwin'):
            for workflow, job in (('publish-maven-central.yml', 'publish-release'), ('recover-maven-central.yml', 'verify-recovery')):
                actual = {**env, 'GITHUB_JOB': job,
                          'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/' + workflow + '@refs/heads/fixture'}
                self.assertTrue(E._hosted_darwin_context(actual))
                for change in ({'GITHUB_JOB': 'other'}, {'GITHUB_WORKFLOW_SHA': 'b' * 40}, {'RUNNER_ENVIRONMENT': 'self-hosted'}):
                    self.assertFalse(E._hosted_darwin_context({**actual, **change}))

    def test_hosted_darwin_domain_retains_positive_proofs_and_revisits_unobserved_parent(self):
        scope = object.__new__(E._HostedDarwinScope)
        scope.known, scope.foreign_sessions, scope.outside_domain_observations, scope.controller_session = {}, {}, 0, 17
        identity = {"pid": 123, "uniqueId": 456, "startSeconds": 1, "startMicroseconds": 2}
        missing = E.audit_processes.DiscoveryUncertain("Darwin non-reaper original-parent lifetime was not observed")
        with mock.patch.object(scope, "_ours", return_value=False) as ours, \
                mock.patch.object(scope, "_has_pipe", return_value=False) as pipe, \
                mock.patch.object(scope, "_parent_proof", side_effect=missing) as parent, \
                mock.patch.object(scope, "_audit_session", return_value=17):
            self.assertIsNone(scope._ownership_proof(identity, {}))
            self.assertEqual(scope.outside_domain_observations, 1)
            self.assertEqual(scope.foreign_sessions, {})
            self.assertEqual(scope.known, {})
            ours.return_value = True
            self.assertEqual(scope._ownership_proof(identity, {}), {"kind": "inherited-domain"})
            ours.return_value = False; pipe.return_value = True
            self.assertEqual(scope._ownership_proof(identity, {}), {"kind": "inherited-pipe-capability"})
            pipe.return_value = False; parent.side_effect = None; parent.return_value = {"kind": "kernel-original-parent"}
            self.assertEqual(scope._ownership_proof(identity, {}), {"kind": "kernel-original-parent"})
            self.assertEqual(scope.outside_domain_observations, 1)
            parent.side_effect = missing
            scope.outside_domain_observations = E.MAX_OUTSIDE_DOMAIN_OBSERVATIONS
            self.assertIsNone(scope._ownership_proof(identity, {}))
            self.assertEqual(scope.outside_domain_observations, E.MAX_OUTSIDE_DOMAIN_OBSERVATIONS)
        for name in ("discover", "spawn", "drain", "_send", "_acquire", "close"):
            self.assertIs(getattr(E._HostedDarwinScope, name), getattr(E.audit_processes.DarwinScope, name))

    def test_hosted_darwin_domain_does_not_relax_real_observation_or_known_owner_failures(self):
        for case in ("traced", "environment", "pipe", "known", "unadmitted-session", "rights"):
            with self.subTest(case=case):
                scope = object.__new__(E._HostedDarwinScope)
                scope.known, scope.foreign_sessions, scope.outside_domain_observations, scope.controller_session = {}, {}, 0, 17
                identity = {"pid": 123, "uniqueId": 456, "startSeconds": 1, "startMicroseconds": 2}
                missing = E.audit_processes.DiscoveryUncertain("Darwin non-reaper original-parent lifetime was not observed")
                if case == "rights":
                    missing._p2pkit_retirement = {"resources": [], "omitted": 1}
                if case == "known":
                    scope.known[scope._key(identity)] = identity
                with mock.patch.object(scope, "_ours", return_value=False) as ours, \
                        mock.patch.object(scope, "_has_pipe", return_value=False) as pipe, \
                        mock.patch.object(scope, "_parent_proof", side_effect=missing) as parent, \
                        mock.patch.object(scope, "_audit_session", return_value=0 if case == "unadmitted-session" else 17):
                    if case == "traced":
                        parent.side_effect = E.audit_processes.DiscoveryUncertain("Darwin traced parentage is not an ownership proof")
                    if case == "environment":
                        ours.side_effect = E.audit_processes.OwnershipError("Owned invocation marker lacks its ancestor domain bindings")
                    if case == "pipe":
                        pipe.side_effect = E.audit_processes.DarwinObservationExhausted("Darwin inherited pipe unresolved")
                    with self.assertRaises(E.audit_processes.OwnershipError):
                        scope._ownership_proof(identity, {})
                self.assertEqual(scope.outside_domain_observations, 0)

    def test_hosted_darwin_boundary_public_projection_has_only_finite_fields(self):
        outcome = {"code": "PASS", "exitCode": 0, "timedOut": False, "cleanupKnown": True,
                   "ownershipBoundary": E.HOSTED_DARWIN_BOUNDARY, "outsideDomainObservations": 52}
        self.assertEqual(E.public_outcome(outcome), outcome)
        for value in (True, -1, E.MAX_OUTSIDE_DOMAIN_OBSERVATIONS + 1, "PRIVATE_PROCESS"):
            with self.subTest(value=value):
                projected = E.public_outcome({**outcome, "outsideDomainObservations": value})
                self.assertNotIn("outsideDomainObservations", projected)
                self.assertNotIn("ownershipBoundary", projected)
        self.assertNotIn("ownershipBoundary", E.public_outcome({**outcome, "ownershipBoundary": "PRIVATE_SCOPE"}))

    def test_public_gpg_boundary_rejects_other_operations_before_spawn(self):
        good = [str(self.root / "gpg"), *E._PUBLIC_GPG_OPTIONS, "--with-colons", "--with-fingerprint",
                "--with-subkey-fingerprint", "--list-keys"]
        cases = [good + ["--decrypt"], ["gpg", *good[1:]],
                 [arg for arg in good if arg != "--no-autostart"],
                 [arg if arg != "--list-keys" else "--sign" for arg in good],
                 good[:1 + len(E._PUBLIC_GPG_OPTIONS)] + ["--import", "recipient.asc"],
                 good[:1 + len(E._PUBLIC_GPG_OPTIONS)] + ["--exec-path", "/untrusted"],
                 good[:1 + len(E._PUBLIC_GPG_OPTIONS)] + ["--trust-model", "always", "--compress-algo", "none",
                     "--recipient", "A" * 40 + "!", "--output", "--bad-option", "--encrypt", "input"]]
        with mock.patch.object(E.subprocess, "Popen") as spawned, mock.patch.object(E, "run_command") as generic:
            for argv in cases:
                with self.subTest(argv=argv), self.assertRaises(E.EvidenceError):
                    E._run_public_gpg(argv, cwd=self.root, environment={}, private=self.root / "absent", timeout=60)
            for timeout in (59, 300):
                with self.subTest(timeout=timeout), self.assertRaises(E.EvidenceError):
                    E._run_public_gpg(good, cwd=self.root, environment={}, private=self.root / "absent", timeout=timeout)
        spawned.assert_not_called(); generic.assert_not_called()
        self.assertFalse((self.root / "absent").exists())

    def test_public_gpg_nondarwin_keeps_existing_supervisor(self):
        argv = [str(self.root / "gpg"), *E._PUBLIC_GPG_OPTIONS, "--with-colons", "--with-fingerprint",
                "--with-subkey-fingerprint", "--list-keys"]
        cancelled = lambda: False
        for system in ("Linux", "Windows"):
            with self.subTest(system=system), mock.patch.object(E.platform, "system", return_value=system), \
                    mock.patch.object(E, "run_command", return_value={"unchanged": True}) as generic, \
                    mock.patch.object(E.subprocess, "Popen") as direct:
                self.assertEqual(E._run_public_gpg(argv, cwd=self.root, environment={}, private=self.root / "none",
                    timeout=60, cancelled=cancelled), {"unchanged": True})
                self.assertIs(generic.call_args.kwargs["cancelled"], cancelled)
                direct.assert_not_called()

    def test_darwin_public_gpg_original_child_and_closed_pipe_lifecycle(self):
        argv = [str(self.root / "gpg"), *E._PUBLIC_GPG_OPTIONS, "--with-colons", "--with-fingerprint",
                "--with-subkey-fingerprint", "--list-keys"]
        cases = ("success", "command-failure", "timeout-term", "timeout-kill", "cancel-before", "cancel-after",
                 "wait-failure", "no-eof", "not-closed", "active", "output-limit", "spawn-failure", "start-failure",
                 "late-poll", "cancel-during-join")
        for case in cases:
            with self.subTest(case=case):
                private = self.root / case
                child = mock.Mock()
                child.stdout, child.stderr = io.BytesIO(), io.BytesIO()
                state = {"returncode": 0 if case in {"success", "no-eof", "not-closed", "active", "output-limit", "wait-failure", "late-poll", "cancel-during-join"}
                         else 2 if case == "command-failure" else None}
                observation = {"late": False, "joined": False}
                def poll():
                    if case == "late-poll":
                        observation["late"] = True
                    return state["returncode"]
                child.poll.side_effect = poll
                def terminate():
                    self.assertIsNone(state["returncode"])
                    if case != "timeout-kill":
                        state["returncode"] = -15
                def kill():
                    self.assertIsNone(state["returncode"])
                    state["returncode"] = -9
                def wait(**_kwargs):
                    if case == "wait-failure":
                        raise OSError("PRIVATE_WAIT_FAILURE")
                    if state["returncode"] is None:
                        raise subprocess.TimeoutExpired("PRIVATE_COMMAND", 3)
                    return state["returncode"]
                child.terminate.side_effect = terminate
                child.kill.side_effect = kill
                child.wait.side_effect = wait
                captures = []
                def capture(pipe, _path, limit):
                    self.assertEqual(limit, E.MAX_JSON_BYTES)
                    item = mock.Mock(pipe=pipe, eof=case != "no-eof", closed=case != "not-closed", error=None)
                    item.thread.ident = None
                    item.thread.is_alive.return_value = case == "active"
                    def start():
                        if case == "start-failure":
                            raise RuntimeError("PRIVATE_START_FAILURE")
                        item.thread.ident = 123
                    item.thread.start.side_effect = start
                    item.thread.join.side_effect = lambda **_kwargs: observation.update(joined=True)
                    if case == "output-limit":
                        item.error = "OUTPUT_LIMIT"
                    captures.append(item)
                    return item
                ticks = iter(range(0, 1000, 31))
                clock = (lambda: next(ticks)) if case.startswith("timeout") else \
                    (lambda: 61.0 if observation["late"] else 0.0)
                cancel_calls = []
                def cancelled():
                    cancel_calls.append(True)
                    return (case == "cancel-before" or (case == "cancel-after" and len(cancel_calls) >= 2) or
                            (case == "cancel-during-join" and observation["joined"]))
                with mock.patch.object(E.platform, "system", return_value="Darwin"), \
                        mock.patch.object(E.subprocess, "Popen", return_value=child) as spawn, \
                        mock.patch.object(E, "Capture", side_effect=capture), \
                        mock.patch.object(E.time, "monotonic", side_effect=clock), mock.patch.object(E.time, "sleep"), \
                        mock.patch.object(E.audit_processes, "make_scope", side_effect=AssertionError("NO_CENSUS")), \
                        mock.patch.object(E.os, "kill", side_effect=AssertionError("NO_BARE_PID_SIGNAL")), \
                        mock.patch.object(E.os, "killpg", create=True, side_effect=AssertionError("NO_GROUP_SIGNAL")):
                    if case == "spawn-failure":
                        spawn.side_effect = OSError("PRIVATE_SPAWN")
                    result = E._run_public_gpg(argv, cwd=self.root, environment={}, private=private,
                                              timeout=60, cancelled=cancelled)
                expected = {"success": "PASS", "command-failure": "COMMAND_FAILED", "timeout-term": "TIMEOUT",
                            "timeout-kill": "TIMEOUT", "cancel-before": "CANCELLED", "cancel-after": "CANCELLED",
                            "output-limit": "OUTPUT_LIMIT", "spawn-failure": "SPAWN", "late-poll": "TIMEOUT",
                            "cancel-during-join": "CANCELLED"}.get(case, "CLEANUP")
                self.assertEqual(result["code"], expected)
                self.assertEqual(result["timedOut"], case.startswith("timeout") or case == "late-poll")
                self.assertEqual(result["cleanupKnown"], case in {
                    "success", "command-failure", "timeout-term", "timeout-kill", "cancel-after", "late-poll", "cancel-during-join"})
                self.assertIsNone(result["pendingContext"])
                if case == "cancel-before":
                    spawn.assert_not_called()
                elif case != "spawn-failure":
                    self.assertTrue(spawn.call_args.kwargs["close_fds"])
                    self.assertTrue(spawn.call_args.kwargs["start_new_session"])
                    self.assertIs(spawn.call_args.kwargs["stdin"], subprocess.DEVNULL)
                    child.wait.assert_called()
                if case in {"success", "command-failure", "no-eof", "not-closed", "active", "output-limit", "late-poll", "cancel-during-join"}:
                    child.terminate.assert_not_called(); child.kill.assert_not_called()
                if case == "timeout-kill":
                    child.terminate.assert_called_once(); child.kill.assert_called_once()
                else:
                    child.kill.assert_not_called()
                child.stdout.close(); child.stderr.close()

    def test_failure_archive_cancellation_is_forwarded_without_upgrading_original_failure(self):
        repo = self.root / "repo"; repo.mkdir()
        private = self.root / "private"; private.mkdir()
        output = self.root / "output"
        outcome = {"code": "COMMAND_FAILED", "exitCode": 9, "cleanupKnown": False,
                   "capturesClosed": True, "timedOut": False}
        handlers = {}
        def signal_handler(sig, handler):
            if callable(handler):
                handlers[sig] = handler
            return signal.SIG_DFL
        def diagnostic(_root, _private, _output, _env, *, cancelled):
            self.assertTrue((output / "failure.json").exists())
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            self.assertTrue(cancelled())
            error = E.EvidenceError("ENCRYPTION")
            error.encryption_diagnostic = {"phase": "key-show", "outcome": {"code": "CANCELLED", "exitCode": -15,
                "timedOut": False, "cleanupKnown": True, "capturesClosed": True}, "categories": []}
            raise error
        with mock.patch.object(E, "source_identity", return_value={"commit": "a" * 40}), \
                mock.patch.object(E, "github_identity", return_value={}), \
                mock.patch.object(E, "run_command", return_value=outcome), \
                mock.patch.object(E.tempfile, "mkdtemp", return_value=str(private)), \
                mock.patch.object(E.signal, "signal", side_effect=signal_handler), \
                mock.patch.object(E, "encrypt_closed_failure_captures", side_effect=diagnostic), \
                mock.patch.object(E, "failure_diagnostics", return_value={}), contextlib.redirect_stderr(io.StringIO()):
            result = E.main(["--component", "bundle-diagnostic", "--timeout-seconds", "5", "--output-dir", str(output),
                             "--source-root", str(repo), "--", "synthetic"])
        failure = json.loads((output / "failure.json").read_text())
        self.assertEqual(result, 1)
        self.assertEqual(failure["outcome"], outcome)
        self.assertEqual(failure["code"], "CLEANUP")
        self.assertEqual(failure["closedCaptureFailure"]["encryptionDiagnostic"]["outcome"]["code"], "CANCELLED")
        self.assertEqual({p.name for p in output.iterdir()}, {"failure.json"})
        self.assertTrue(private.is_dir())

    def test_gpg_uses_cwd_relative_paths_for_native_and_msys_interoperation(self):
        work = self.root / 'private work'; work.mkdir()
        source = self.root / 'input archive.tar.gz'; source.write_bytes(b'public fixture')
        output = self.root / 'public output' / 'evidence.tar.gz.gpg'; output.parent.mkdir()
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        calls = []
        encryption_fingerprint = '4D7CF63A16AFC0BDDC82F3E686D7D3D9A7B44350'
        def invoke(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(kwargs['cwd'], work)
            self.assertEqual(argv[argv.index('--homedir') + 1], 'gnupg')
            self.assertIn('--no-autostart', argv)
            self.assertIn('--no-auto-key-retrieve', argv)
            for flag in ('--no-default-keyring', '--no-auto-key-import', '--disable-dirmngr', '--no-random-seed-file'):
                self.assertIn(flag, argv)
            self.assertEqual(argv[argv.index('--auto-key-locate') + 1], 'clear')
            self.assertEqual(argv[argv.index('--keyring') + 1], './recipient.gpg')
            self.assertEqual((work / 'recipient.gpg').read_bytes(), E._public_armor(key))
            if os.name == 'posix':
                self.assertEqual((work / 'recipient.gpg').stat().st_mode & 0o777, 0o600)
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
                self.assertEqual(argv[argv.index('--recipient') + 1], encryption_fingerprint + '!')
                output.write_bytes(b'public-ciphertext-model' * 4)
            return {'code': 'PASS', 'exitCode': 0, 'timedOut': False, 'cleanupKnown': True}
        with mock.patch.object(E, '_run_public_gpg', side_effect=invoke), \
                mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                mock.patch.object(E, '_key_identity', return_value=(encryption_fingerprint, 1821484800)):
            E.encrypt_archive(source, output, key, hashlib.sha256(key).hexdigest(),
                              PUBLIC_FINGERPRINT, work, dict(os.environ))
        self.assertEqual(len(calls), 3)
        self.assertEqual([argv[argv.index('--import-options') + 1] for argv in calls if '--import' in argv], ['show-only'])
        other = self.root / 'different-drive-model'; other.mkdir()
        with mock.patch.object(E.os.path, 'relpath', side_effect=ValueError('PRIVATE_DRIVE')), \
                mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                mock.patch.object(E, '_run_public_gpg') as unused:
            with self.assertRaises(E.EvidenceError) as caught:
                E.encrypt_archive(source, output, key, hashlib.sha256(key).hexdigest(),
                                  PUBLIC_FINGERPRINT, other, dict(os.environ))
        self.assertEqual(caught.exception.code, 'ENCRYPTION')
        unused.assert_not_called()

    def test_public_keyring_selected_identity_or_expiry_mismatch_stops_before_encryption(self):
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        chosen = '4D7CF63A16AFC0BDDC82F3E686D7D3D9A7B44350'
        for index, selected in enumerate((('F' * 40, 1821484800), (chosen, 1821484801))):
            with self.subTest(selected=selected):
                work = self.root / ('mismatch-' + str(index)); work.mkdir()
                calls = []
                def invoke(argv, **kwargs):
                    calls.append(kwargs['private'].name)
                    kwargs['private'].mkdir()
                    (kwargs['private'] / 'stdout.log').write_bytes(b'PUBLIC_LISTING_MODEL')
                    return {'code': 'PASS', 'exitCode': 0, 'cleanupKnown': True}
                with mock.patch.object(E, '_run_public_gpg', side_effect=invoke), \
                        mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                        mock.patch.object(E, '_key_identity', side_effect=[(chosen, 1821484800), selected]) as identity:
                    with self.assertRaises(E.EvidenceError) as caught:
                        E.encrypt_archive(work / 'archive', work / 'cipher', key, hashlib.sha256(key).hexdigest(),
                                          PUBLIC_FINGERPRINT, work, dict(os.environ))
                self.assertEqual(caught.exception.code, 'RECIPIENT')
                self.assertEqual(calls, ['key-show', 'key-list'])
                self.assertEqual([call.args[1] for call in identity.call_args_list], [PUBLIC_FINGERPRINT] * 2)
                self.assertFalse((work / 'cipher').exists())

    def test_public_keyring_is_exclusive_and_never_overwrites_existing_input(self):
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        ring = self.root / 'recipient.gpg'
        ring.write_bytes(b'EXISTING_PUBLIC_FIXTURE')
        with mock.patch.object(E, '_run_public_gpg') as unused:
            with self.assertRaises(FileExistsError):
                E.encrypt_archive(self.root / 'archive', self.root / 'cipher', key, hashlib.sha256(key).hexdigest(),
                                  PUBLIC_FINGERPRINT, self.root, dict(os.environ))
        unused.assert_not_called()
        self.assertEqual(ring.read_bytes(), b'EXISTING_PUBLIC_FIXTURE')
        self.assertFalse((self.root / 'cipher').exists())

    @unittest.skipUnless(sys.platform == "linux", "portable direct-child exercise uses the Linux public GPG tool")
    def test_actual_public_encryption_direct_child_boundary_on_linux_not_native_darwin(self):
        # Select the Darwin direct-child path but execute genuine Linux public
        # GPG/Capture/Popen/wait. This is not native macOS qualification.
        key = (SCRIPTS.parent / ".github/ci-evidence-recipient.asc").read_bytes()
        work = self.root / "direct-public-gpg"; work.mkdir()
        archive = self.root / "public-synthetic.tar.gz"
        archive.write_bytes(b"PUBLIC_SYNTHETIC_DIRECT_CHILD" * 100)
        cipher = self.root / "public-synthetic.tar.gz.gpg"
        with mock.patch.object(E.platform, "system", return_value="Darwin"), \
                mock.patch.object(E.audit_processes, "make_scope", side_effect=AssertionError("NO_GLOBAL_CENSUS")):
            result = E.encrypt_archive(archive, cipher, key, hashlib.sha256(key).hexdigest(),
                                       PUBLIC_FINGERPRINT, work, dict(os.environ))
        self.assertEqual(result["sha256"], E.digest_file(cipher)["sha256"])
        self.assertEqual(result["recipientFingerprint"], PUBLIC_FINGERPRINT)
        self.assertGreater(result["bytes"], 32)
        for phase in ("key-show", "key-list", "encrypt"):
            self.assertTrue((work / phase / "stdout.log").is_file())
            self.assertTrue((work / phase / "stderr.log").is_file())
        secrets = work / "gnupg/private-keys-v1.d"
        self.assertFalse(list(secrets.iterdir()) if secrets.exists() else [])

    def test_actual_public_key_encrypts_without_private_key_or_agent(self):
        key = (SCRIPTS.parent / ".github/ci-evidence-recipient.asc").read_bytes()
        # Public-only encryption must not depend on an agent socket fitting a
        # short homedir. Target 136 characters without inflating Windows paths.
        padding = max(1, 136 - len(str(self.root / "public-only-" / "gnupg")))
        work = self.root / ("public-only-" + "x" * padding)
        work.mkdir()
        self.assertGreater(len(str(work / "gnupg")), 128)
        source = self.root / "evidence.tar.gz"
        source.write_bytes(b"PUBLIC_SYNTHETIC_TEST_ONLY" * 100)
        result = E.encrypt_archive(source, self.root / "evidence.tar.gz.gpg", key,
            hashlib.sha256(key).hexdigest(), PUBLIC_FINGERPRINT, work, dict(os.environ))
        self.assertEqual(result["recipientFingerprint"], PUBLIC_FINGERPRINT)
        self.assertEqual(result["sha256"], E.digest_file(self.root / "evidence.tar.gz.gpg")["sha256"])
        self.assertGreater(result["bytes"], 32)
        secret_dir = work / "gnupg/private-keys-v1.d"
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
            "GITHUB_JOB": "test", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_TEMP": str(self.root),
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
        for failed_phase in ('key-show', 'key-list', 'encrypt'):
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
                    with mock.patch.object(E, '_run_public_gpg', side_effect=invoke), \
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

    def test_deferred_gradle_home_keeps_actual_remote_subprocess_domain_coherent(self):
        work = self.root / 'consumer'
        home = work / 'gradle-home'
        program = """import json, os, pathlib, subprocess, sys
work = pathlib.Path(os.environ['P2PKIT_CONSUMER_WORK_DIR'])
home = pathlib.Path(os.environ['GRADLE_USER_HOME'])
assert not work.exists() and not home.exists()
assert json.loads(os.environ['P2PKIT_AUDIT_OWNERSHIP_DOMAINS'])[-1]['home'] == str(home)
work.mkdir(mode=0o700)
home.mkdir(mode=0o700)
# Same assignment made by the immutable remote consumer, now already bound.
env = dict(os.environ, GRADLE_USER_HOME=str(work / 'gradle-home'))
subprocess.run([sys.executable, '-I', '-B', '-c',
    'import os,json; assert json.loads(os.environ["P2PKIT_AUDIT_OWNERSHIP_DOMAINS"])[-1]["home"] == os.environ["GRADLE_USER_HOME"]'],
    env=env, check=True)
print('DEFERRED_HOME_DOMAIN_PASS')
"""
        # Validate the inherited owner before changing this fixture's home.
        # Rebinding only GRADLE_USER_HOME corrupts an actual CI parent domain.
        inherited = dict(os.environ)
        fixture = E.audit_processes.ownership_environment(inherited, uuid.uuid4().hex, uuid.uuid4().hex,
            str(self.root / 'remote-fixture-state'), str(home), allow_new_context=True)
        inherited_domains = E.audit_processes.ownership_domains(
            inherited.get(E.audit_processes.CHAIN_ENV, ''), inherited.get(E.audit_processes.DOMAINS_ENV, ''))
        fixture_domains = E.audit_processes.ownership_domains(
            fixture[E.audit_processes.CHAIN_ENV], fixture[E.audit_processes.DOMAINS_ENV])
        self.assertEqual(fixture_domains[:-1], inherited_domains)
        self.assertEqual(fixture[E.audit_processes.CHAIN_ENV].split(':')[:-1],
                         inherited.get(E.audit_processes.CHAIN_ENV, '').split(':') if inherited_domains else [])
        fixture['P2PKIT_CONSUMER_WORK_DIR'] = str(work)
        outcome = E.run_command([sys.executable, '-I', '-B', '-c', program], cwd=self.root,
            environment=fixture, private=self.root / 'deferred-capture', timeout=15, create_gradle_home=False)
        self.assertEqual(outcome['code'], 'PASS')
        self.assertEqual(outcome['exitCode'], 0)
        self.assertTrue(outcome['cleanupKnown'])
        self.assertTrue(outcome['capturesClosed'])
        self.assertFalse(outcome['timedOut'])
        self.assertEqual(outcome['cleanupReasons'], [])
        self.assertEqual((self.root / 'deferred-capture/stdout.log').read_text(), 'DEFERRED_HOME_DOMAIN_PASS\n')

    def test_deferred_home_fixture_preserves_actual_enclosing_command_ownership(self):
        # CI runs this suite inside E's real ownership domain; exercise that
        # nesting locally too rather than passing only with an empty parent.
        outcome = E.run_command([sys.executable, '-I', '-B', '-S', '-W', 'error::ResourceWarning',
            str(Path(__file__).resolve()),
            'EvidenceTests.test_deferred_gradle_home_keeps_actual_remote_subprocess_domain_coherent', '-v'],
            cwd=self.root, environment=dict(os.environ), private=self.root / 'nested-deferred', timeout=30)
        self.assertEqual(outcome['code'], 'PASS')
        self.assertEqual(outcome['exitCode'], 0)
        self.assertFalse(outcome['timedOut'])
        self.assertTrue(outcome['cleanupKnown'])
        self.assertTrue(outcome['capturesClosed'])
        self.assertEqual(outcome['cleanupReasons'], [])
        report = (self.root / 'nested-deferred/stderr.log').read_text()
        self.assertIn('Ran 1 test in ', report)
        self.assertIn('test_deferred_gradle_home_keeps_actual_remote_subprocess_domain_coherent', report)
        self.assertTrue(report.rstrip().endswith('OK'))

    def test_deferred_home_option_is_typed_and_default_still_creates_home(self):
        for value in (None, 0, 1, 'false'):
            with self.subTest(value=value), self.assertRaises(E.EvidenceError):
                E.run_command(['not-executed'], cwd=self.root, environment={},
                              private=self.root / 'invalid-option', timeout=5, create_gradle_home=value)
        self.assertFalse((self.root / 'invalid-option').exists())
        child = mock.Mock(stdout=io.BytesIO(b''), stderr=io.BytesIO(b''), returncode=0)
        child.poll.return_value = 0
        scope = mock.Mock(leaders=[child], discovery_errors=set())
        scope.spawn.return_value = child
        scope.drain.return_value = []
        with mock.patch.object(E, '_command_scope', return_value=scope):
            outcome = E.run_command(['synthetic'], cwd=self.root, environment=dict(os.environ),
                private=self.root / 'eager-capture', timeout=5)
        self.assertEqual(outcome['code'], 'PASS')
        self.assertTrue(Path(scope.spawn.call_args.args[2]['GRADLE_USER_HOME']).is_dir())

    def test_deferred_remote_home_accepts_only_fixed_physical_fresh_private_layout(self):
        parent = self.root.resolve() / 'ci-terminal-synthetic'; parent.mkdir(mode=0o700)
        for name in ('home', 'tmp'): (parent / name).mkdir(mode=0o700)
        env = dict(RUNNER_TEMP=str(self.root.resolve()), HOME=str(parent / 'home'), TMPDIR=str(parent / 'tmp'),
                   P2PKIT_CONSUMER_WORK_DIR=str(parent / 'consumer'), GRADLE_USER_HOME=str(parent / 'consumer/gradle-home'))
        self.assertTrue(E.deferred_remote_consumer_home('published-consumers-diagnostic', env))
        self.assertFalse(E.deferred_remote_consumer_home('consumers', env))
        for changed in ({'GRADLE_USER_HOME': str(parent / 'other')}, {'HOME': str(self.root)},
                        {'TMPDIR': '/PRIVATE'}, {'P2PKIT_CONSUMER_WORK_DIR': '../PRIVATE'},
                        {'P2PKIT_CONSUMER_WORK_DIR': str(parent / 'other')}):
            with self.subTest(changed=changed), self.assertRaises(E.EvidenceError):
                E.deferred_remote_consumer_home('published-consumers-diagnostic', {**env, **changed})
        (parent / 'consumer').mkdir()
        with self.assertRaises(E.EvidenceError): E.deferred_remote_consumer_home('published-consumers-diagnostic', env)
        (parent / 'consumer').rmdir()
        (parent / 'home').chmod(0o755)
        with self.assertRaises(E.EvidenceError): E.deferred_remote_consumer_home('published-consumers-diagnostic', env)
        (parent / 'home').chmod(0o700)
        (parent / 'home').rmdir(); (parent / 'home').symlink_to(parent / 'tmp')
        with self.assertRaises(E.EvidenceError): E.deferred_remote_consumer_home('published-consumers-diagnostic', env)

    def test_remote_main_passes_deferred_home_only_after_layout_admission(self):
        parent = self.root.resolve() / 'ci-terminal-main'; parent.mkdir(mode=0o700)
        for name in ('home', 'tmp'): (parent / name).mkdir(mode=0o700)
        source_root = self.root / 'source'; source_root.mkdir()
        env = dict(RUNNER_TEMP=str(self.root.resolve()), HOME=str(parent / 'home'), TMPDIR=str(parent / 'tmp'),
                   P2PKIT_CONSUMER_WORK_DIR=str(parent / 'consumer'), GRADLE_USER_HOME=str(parent / 'consumer/gradle-home'))
        outcome = dict(code='CLEANUP', exitCode=None, timedOut=False, cleanupKnown=False, capturesClosed=False)
        with mock.patch.dict(E.os.environ, env), \
             mock.patch.object(E, 'source_identity', return_value=dict(commit='a' * 40, tree='b' * 40, version='0.8.0-SNAPSHOT')), \
             mock.patch.object(E, 'github_identity', return_value={}), \
             mock.patch.object(E, 'run_command', return_value=outcome) as command, contextlib.redirect_stderr(io.StringIO()):
            code = E.main(['--component', 'published-consumers-diagnostic', '--timeout-seconds', '5',
                '--source-root', str(source_root), '--output-dir', str(self.root / 'public'), '--', 'synthetic'])
        self.assertEqual(code, 1)
        self.assertIs(command.call_args.kwargs['create_gradle_home'], False)
        self.assertEqual(command.call_args.kwargs['environment']['GRADLE_USER_HOME'], env['GRADLE_USER_HOME'])
        self.assertFalse((parent / 'consumer').exists())
        failure = json.loads((self.root / 'public/failure.json').read_text())
        self.assertEqual(failure['code'], 'CLEANUP')
        self.assertFalse(failure['outcome']['cleanupKnown'])

    def test_unknown_native_error_retains_only_exact_allowlisted_exception_type(self):
        hostile = type('PRIVATE_CLASS_NAME', (RuntimeError,), {})
        cases = [(E.audit_processes.OwnershipError('PRIVATE_PATH'), 'OWNERSHIP_ERROR'),
                 (E.audit_processes.DiscoveryUncertain('PRIVATE_STATE'), 'DISCOVERY_UNCERTAIN'),
                 (subprocess.TimeoutExpired(['PRIVATE_COMMAND'], 8, output=b'PRIVATE_PAYLOAD'), 'TIMEOUT_EXPIRED'),
                 (TypeError('PRIVATE_TYPE'), 'TYPE_ERROR'), (KeyError('PRIVATE_KEY'), 'KEY_ERROR'),
                 (ValueError('PRIVATE_VALUE'), 'VALUE_ERROR'), (AttributeError('PRIVATE_ATTR'), 'ATTRIBUTE_ERROR'),
                 (hostile('PRIVATE_MESSAGE'), 'UNKNOWN')]
        for error, label in cases:
            with self.subTest(label=label):
                result = E.native_error_diagnostic(error)
                expected = dict(kind='UNKNOWN', operation=None, errno=None, winerror=None, exceptionType=label)
                if type(error) is E.audit_processes.DiscoveryUncertain:
                    expected['failureKind'] = 'OTHER'
                self.assertEqual(result, expected)
                public = E.public_outcome(dict(code='CLEANUP', exitCode=None, timedOut=False,
                                               cleanupKnown=False, nativeError=result))
                self.assertEqual(public['nativeError'], result)
                self.assertNotIn('PRIVATE', json.dumps(public))
                self.assertLess(len(json.dumps(result)), 160)

    def test_unknown_native_darwin_cause_reuses_only_finite_source_owned_labels(self):
        causes = [*E.PENDING_FAILURES.items(),
                  *(("Darwin " + operation + " unresolved after bounded observation: PRIVATE_DETAILS", label)
                    for operation, label in E.PENDING_OPERATIONS.items())]
        for error_type in (E.audit_processes.DiscoveryUncertain, E.audit_processes.DarwinObservationExhausted):
            for message, label in [*causes, ("PRIVATE_UNKNOWN", "OTHER"),
                                   (next(iter(E.PENDING_FAILURES)) + " PRIVATE_SUFFIX", "OTHER"),
                                   ("Darwin PRIVATE_OPERATION unresolved after bounded observation: PRIVATE", "OTHER"),
                                   ("Darwin environment unresolved after bounded observation: " + "x" * 4096, "OTHER"),
                                   (object(), "OTHER")]:
                with self.subTest(error_type=error_type.__name__, label=label):
                    result = E.native_error_diagnostic(error_type(message))
                    self.assertEqual(result['kind'], 'UNKNOWN')
                    self.assertEqual(result['failureKind'], label)
                    self.assertNotIn('PRIVATE', json.dumps(result))
                    self.assertLess(len(json.dumps(result)), 220)
        hostile = type('PRIVATE_ERROR_CLASS', (E.audit_processes.DiscoveryUncertain,), {})
        for error in (hostile(next(iter(E.PENDING_FAILURES))), RuntimeError(next(iter(E.PENDING_FAILURES)))):
            result = E.native_error_diagnostic(error)
            self.assertNotIn('failureKind', result)
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_unknown_native_frames_are_bounded_to_exact_own_sources_without_private_data(self):
        # Synthetic source bindings, not source execution or a native ownership claim.
        namespace = {}
        source = "def frame(n):\n    if n: return frame(n - 1)\n    raise ValueError('PRIVATE_MESSAGE')\n"
        exec(compile(source, str(SCRIPTS / 'audit_processes.py'), 'exec'), namespace)
        try:
            namespace['frame'](8)
        except ValueError as error:
            result = E.native_error_diagnostic(error)
        self.assertEqual(result['kind'], 'UNKNOWN')
        self.assertEqual(result['exceptionType'], 'VALUE_ERROR')
        self.assertEqual(result['sourceFrames'], [dict(source='OWNERSHIP', line=2),
                         dict(source='OWNERSHIP', line=2), dict(source='OWNERSHIP', line=3)])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn(str(SCRIPTS), json.dumps(result))
        for path in ('/PRIVATE/audit_processes.py', str(SCRIPTS / 'audit_processes.py') + '.PRIVATE'):
            try:
                exec(compile("raise TypeError('PRIVATE_DETAILS')", path, 'exec'), {})
            except TypeError as error:
                result = E.native_error_diagnostic(error)
            self.assertNotIn('sourceFrames', result)
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_nested_command_deadline_is_assigned_from_original_timeout_not_caller(self):
        child = mock.Mock(stdout=io.BytesIO(b''), stderr=io.BytesIO(b''), returncode=0)
        child.poll.return_value = 0
        scope = mock.Mock(leaders=[child], discovery_errors=set())
        scope.spawn.return_value = child
        scope.drain.return_value = []
        environment = {**os.environ, 'P2PKIT_CI_COMMAND_DEADLINE_NS': '99999999999999999999'}
        with mock.patch.object(E, '_command_scope', return_value=scope), mock.patch.object(E.time, 'monotonic', return_value=100):
            result = E.run_command(['synthetic'], cwd=self.root, environment=environment,
                                   private=self.root / 'deadline', timeout=5)
        self.assertEqual(result['code'], 'PASS')
        self.assertTrue(result['cleanupKnown'])
        self.assertTrue(result['capturesClosed'])
        self.assertEqual(scope.spawn.call_args.args[2]['P2PKIT_CI_COMMAND_DEADLINE_NS'], '105000000000')
        self.assertEqual(environment['P2PKIT_CI_COMMAND_DEADLINE_NS'], '99999999999999999999')

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
            with self.subTest(index=index), mock.patch.object(E, '_command_scope', side_effect=error):
                result = E.run_command(['no-command-executed'], cwd=self.root, environment=dict(os.environ),
                    private=self.root / ('spawn-' + str(index)), timeout=1)
            self.assertEqual(result['code'], 'SPAWN')
            expected = {'kind': kind, 'operation': operation, 'errno': errno, 'winerror': winerror}
            if kind == 'UNKNOWN':
                expected['exceptionType'] = 'OWNERSHIP_ERROR' if type(error) is E.audit_processes.OwnershipError else 'RUNTIME_ERROR'
                frames = result['nativeError']['sourceFrames']
                self.assertEqual(len(frames), 1)
                self.assertEqual(frames[0]['source'], 'EVIDENCE')
                self.assertGreater(frames[0]['line'], 0)
                expected['sourceFrames'] = frames
            self.assertEqual(result['nativeError'], expected)
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
        observed = {name for component in (*ci_component.COMPONENTS, *ci_component.DIAGNOSTICS)
                    for name, _argv in ci_component.commands(component)}
        self.assertEqual(set(), observed - E.TASK_NAMES)
        self.assertTrue({"prepare-android", "prepare-desktop", "inspect-android", "inspect-desktop",
                         "component-setup", "gradle-stop"} <= E.TASK_NAMES)


if __name__ == "__main__":
    unittest.main(failfast=True)
