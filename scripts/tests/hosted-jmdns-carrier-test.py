#!/usr/bin/env python3
"""Offline carrier DATA/source controls; no real receipts or hosted qualification.

Every report and canonical return in this file is synthetic. Process/native,
crypto, dependency and network execution are forbidden even if a mock is missed.
The actual owner, runner and original custody still require hosted qualification.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-dependency-update.py"
SHA_FIELDS = {"controller_sha", "controller_tree", "candidate_sha", "candidate_tree", "dependency_base_sha"}
TASKS = (
    ":p2p-transport-lan:jvmTest", "--tests",
    "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally",
    "--no-configure-on-demand",
)
MODES = (
    "control", "failed_recovery", "shared_close", "close_wins", "recovery_wins",
    "responder_close", "callback_executor", "cleanup_retry",
)
CLASS = "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest"
SUITE = "JmdnsCloseLifecycleTest[jvm]"
METHOD = "realResourceCloseRegressionsExitNaturally[jvm]"
XML_PATH = f"library/p2p-transport-lan/build/test-results/jvmTest/TEST-{CLASS}.xml"
LOG_ROOT = "library/p2p-transport-lan/build/reports/jmdns-close/run-synthetic/"
START_NS = 100_000_000_000


def offline(event, _args):
    if event.startswith("socket.") or event in (
            "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv"):
        raise AssertionError("synthetic carrier control attempted execution: " + event)


sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("synthetic_jmdns_carrier", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)


def request_and_environment(operation="diagnose-jmdns"):
    request = {name: chr(97 + index) * 40 for index, name in enumerate(sorted(SHA_FIELDS))}
    request["operation"] = operation
    env = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": M.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_JOB": "generate", "GITHUB_ACTOR": M.OWNER, "GITHUB_ACTOR_ID": M.OWNER_ID,
        "GITHUB_TRIGGERING_ACTOR": M.OWNER, "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": request["controller_sha"], "GITHUB_WORKFLOW_SHA": request["controller_sha"],
        "GITHUB_WORKFLOW_REF": M.REPOSITORY + "/" + M.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
    }
    return request, env


def xml_report(*, child="", tests="1", failures="0", errors="0", skipped="0", name=METHOD, classname=CLASS,
               suite=SUITE):
    return (
        f'<testsuite name="{suite}" tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">'
        f'<testcase name="{name}" classname="{classname}">{child}</testcase></testsuite>'
    ).encode("utf-8")


class RetainedReports:
    """Private newly allocated synthetic files, never copied production evidence."""
    def __init__(self, parent, *, xml=None, modes=MODES):
        self.anchor = parent / "candidate-reports"
        self.anchor.mkdir(mode=0o700)
        self.rows = []
        self.add(XML_PATH, xml if xml is not None else xml_report())
        for index, mode in enumerate(modes):
            self.add(LOG_ROOT + mode + f"-{index + 1}.log", f"PASS mode={mode}\n".encode())
        self.write_manifest()

    def add(self, name, raw):
        path = self.anchor / "reports" / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        M.write_new(path, raw)
        self.rows.append({"source": name, "retained": "reports/" + name,
                          "classification": "changed-since-admission", "bytes": len(raw), "sha256": M.digest(raw)})

    def write_manifest(self):
        path = self.anchor / "report-manifest.json"
        # Only this test's own synthetic manifest is rewritten between mutations.
        path.write_bytes(M.encoded({"records": self.rows}))
        path.chmod(0o600)

    def rewrite(self, row, raw, *, rebind=True):
        path = self.anchor / row["retained"]
        path.write_bytes(raw)
        if rebind:
            row.update(bytes=len(raw), sha256=M.digest(raw))
            self.write_manifest()


class SelectedCaseIdentityControls(unittest.TestCase):
    def test_suite_requires_exact_target_qualified_display_name(self):
        for suite in (CLASS, CLASS + "[jvm]", "JmdnsCloseLifecycleTest", "JmdnsCloseLifecycleTest[jvmTest]",
                      "JmdnsCloseLifecycleTest[js]", " " + SUITE, SUITE + " "):
            for code in (0, 1):
                with self.subTest(suite=suite, code=code), \
                        tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                    reports = RetainedReports(Path(temporary).resolve(strict=True), xml=xml_report(suite=suite))
                    with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_SELECTED_CASE$"):
                        M.diagnostic_test_data(reports.anchor, code)

    def test_classname_requires_independent_fully_qualified_class_name(self):
        for classname in (SUITE, "JmdnsCloseLifecycleTest", CLASS + "[jvm]"):
            for code in (0, 1):
                with self.subTest(classname=classname, code=code), \
                        tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                    reports = RetainedReports(Path(temporary).resolve(strict=True), xml=xml_report(classname=classname))
                    with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_SELECTED_CASE$"):
                        M.diagnostic_test_data(reports.anchor, code)

    def test_method_requires_unchanged_exact_target_qualified_name(self):
        for name in ("realResourceCloseRegressionsExitNaturally", "realResourceCloseRegressionsExitNaturally[jvmTest]",
                     "realResourceCloseRegressionsExitNaturally[js]", " " + METHOD, METHOD + " "):
            for code in (0, 1):
                with self.subTest(name=name, code=code), \
                        tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                    reports = RetainedReports(Path(temporary).resolve(strict=True), xml=xml_report(name=name))
                    with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_SELECTED_CASE$"):
                        M.diagnostic_test_data(reports.anchor, code)


class CarrierSimulation:
    """Executes carrier control flow only with blocked real execution and mocks.

    This model cannot exercise/native-qualify owned_command. It merely checks
    that the carrier uses its genuine return path and keeps separate outcomes.
    """
    def __init__(self, parent, *, target_code=1, observer_code=0):
        self.parent = parent
        self.records = parent / "records"
        self.records.mkdir(mode=0o700)
        self.candidate = parent / "candidate"
        self.candidate.mkdir(mode=0o700)
        self.request, self.env = request_and_environment()
        self.github = M.request_data(self.request, self.env)
        self.context = {"id": "2" * 32}
        self.candidate_source = {"commit": self.request["candidate_sha"], "tree": self.request["candidate_tree"],
                                 "status": "", "diffSha256": M.digest(b"")}
        self.target_code, self.observer_code = target_code, observer_code
        self.runner = SimpleNamespace(gradle_arguments=lambda args: [*args, "--synthetic-canonical-policy"])
        self.events = []
        self.command_seconds = []
        self.target_mutation = lambda _value: None
        self.observer_mutation = lambda _value: None
        self.after_observer = lambda: None
        self.receipts = {}
        self.receipt_hashes = {}
        self.hard_target_error = False
        self.change_source = False
        self.clock = [START_NS, START_NS + 1_000_000_000, START_NS + 200_000_000_000,
                      START_NS + 201_000_000_000, START_NS + 220_000_000_000]

    def owned_command(self, runner, parent, context, purpose, argv, seconds):
        assert runner is self.runner and parent == self.parent and context == self.context
        phase = purpose.removeprefix("dependency-maintenance-jmdns-")
        assert phase in ("target", "observer")
        assert argv[-1] == "_diagnostic-" + phase and argv[1:4] == ["-I", "-B", "-S"]
        assert Path(argv[4]) == M.ROOT / "scripts/run-hosted-dependency-update.py"
        self.events.append(phase)
        self.command_seconds.append(seconds)
        if phase == "target" and self.hard_target_error:
            raise M.UpdateError("ORIGINAL_COMMAND_FAILED")
        declaration = M.parsed((self.records / "jmdns-request.json").read_bytes())
        declaration_hash = M.digest(M.encoded(declaration))
        receipt = {"id": ("a" if phase == "target" else "b") * 32,
                   "purpose": purpose, "productExitCode": self.target_code if phase == "target" else self.observer_code}
        receipt_raw = M.encoded(receipt)
        receipt_hash = M.digest(receipt_raw)
        receipt_path = self.parent / "state/evidence" / receipt["id"] / "receipt.json"
        receipt_path.parent.mkdir(mode=0o700, parents=True)
        M.write_new(receipt_path, receipt_raw)
        self.receipts[phase], self.receipt_hashes[phase] = receipt, receipt_hash
        if phase == "target":
            target = {
                "schema": 1, "scope": M.DIAGNOSTIC_SCOPE, "requestSha256": declaration_hash,
                "invocationId": receipt["id"], "jobId": self.context["id"], "beforeJava": {},
                "requestedGradleArgv": list(TASKS),
                "executedGradleArgv": [str(self.candidate / "gradlew"), *self.runner.gradle_arguments(list(TASKS))],
                "testExitCode": self.target_code, "beforeObservationElapsedNs": 10_000_000_000,
                "startedTestMonotonicNs": START_NS + 10_000_000_000,
                "endTestMonotonicNs": START_NS + 190_000_000_000,
            }
            self.target_mutation(target)
            M.write_new(self.records / "jmdns-target.json", M.encoded(target))
        else:
            returned_raw = (self.records / "jmdns-target-return.json").read_bytes()
            returned = M.parsed(returned_raw)
            assert self.events[:3] == ["target", "retained-reports", "selected-test-data"]
            assert set(returned) == {"schema", "scope", "requestSha256", "targetReceipt", "targetReceiptSha256",
                                     "targetRecordSha256", "returnedMonotonicNs"}
            assert returned["targetReceiptSha256"] == self.receipt_hashes["target"]
            assert returned["targetReceipt"] == self.receipts["target"]
            observer = {
                "schema": 1, "scope": M.DIAGNOSTIC_SCOPE, "requestSha256": declaration_hash,
                "invocationId": receipt["id"], "jobId": self.context["id"],
                "targetRecordSha256": M.digest((self.records / "jmdns-target.json").read_bytes()),
                "targetReturnSha256": M.digest(returned_raw), "afterJava": {}, "binding": {},
                "logObservation": {}, "logInterpretation": {},
                "observationDeadlineMonotonicNs": START_NS + 300_000_000_000,
                "observationElapsedNs": 39_000_000_000, "endedMonotonicNs": START_NS + 219_000_000_000,
                "observerExitCode": self.observer_code,
            }
            self.observer_mutation(observer)
            M.write_new(self.records / "jmdns-observer.json", M.encoded(observer))
            self.after_observer()
        if receipt["productExitCode"]:
            raise M.ClosedProductFailure(receipt["productExitCode"], receipt, receipt_hash)
        return receipt, receipt_hash

    def retain(self, *args):
        assert args[0] is self.runner and args[1] == self.candidate
        assert args[4] == self.request and args[-2] == self.receipts["target"]
        assert args[-1] == self.receipt_hashes["target"]
        self.events.append("retained-reports")

    def test_data(self, anchor, code):
        assert anchor == self.records / "candidate-reports" and code == self.target_code
        self.events.append("selected-test-data")
        return {"status": "FAILED" if code else "PASSED_SELECTED_TEST_ONLY",
                "reportedCases": 1, "modePasses": 0 if code else 8}

    def run(self, *, baseline=None):
        def clean(*args):
            assert args == (self.runner, self.candidate, self.request["candidate_sha"], self.request["candidate_tree"])
            return {**self.candidate_source, "status": " M synthetic"} if self.change_source else self.candidate_source

        def helper(name, relative):
            assert (name, relative) == ("hosted_jmdns_diagnostic", "scripts/hosted_jmdns_diagnostic.py")
            return SimpleNamespace(GRADLE_ARGUMENTS=TASKS)

        with mock.patch.object(M, "owned_command", self.owned_command), \
                mock.patch.object(M, "retain_candidate_reports", self.retain), \
                mock.patch.object(M, "diagnostic_test_data", self.test_data), \
                mock.patch.object(M, "module", helper), mock.patch.object(M, "clean_source", clean), \
                mock.patch.object(M.time, "monotonic_ns", side_effect=self.clock):
            return M.run_diagnostic(self.runner, self.parent, self.context, self.candidate, self.records,
                                    self.request, self.github, self.candidate_source, [] if baseline is None else baseline)


def diagnostic_return(code=1):
    """Envelope DATA only; the upload controls below supply real synthetic files."""
    request, env = request_and_environment()
    env.update(P2PKIT_DEPENDENCY_GENERATOR_OUTCOME="failure" if code else "success",
               P2PKIT_DEPENDENCY_SUCCESS_SHA256="", P2PKIT_DEPENDENCY_FAILED_SHA256="")
    value = {"schema": 1, "scope": M.DIAGNOSTIC_SCOPE, "request": request,
             "github": M.request_data(request, env), "policySha256": M.POLICY_SHA256,
             "files": {"diagnostic-encrypted/" + name: {} for name in M.ENCRYPTED_FILES},
             "exportManifestSha256": "1" * 64, "diagnosticResultSha256": "2" * 64,
             "producerReturn": "DIAGNOSTIC_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN", "exitCode": code}
    return value, env


class UploadSimulation:
    """Real file-identity guards over fake data; no crypto/provider/native claims."""
    def __init__(self, root, *, code=1):
        self.parent = root / "operation"
        self.controller, self.candidate = root / "workspace/controller", root / "workspace/candidate"
        self.records = self.parent / "state/evidence/maintenance"
        self.encrypted = self.parent / "outputs/diagnostic-encrypted"
        for path in (self.controller, self.candidate, self.records, self.encrypted):
            path.mkdir(mode=0o700, parents=True)
        self.value, self.env = diagnostic_return(code)
        self.rosters = {self.controller: {"synthetic-controller-source": {"sha256": "c" * 64}},
                        self.candidate: {"synthetic-candidate-source": {"sha256": "d" * 64}}}
        for name, value in (("controller-inputs.json", self.rosters[self.controller]),
                            ("candidate-inputs-before.json", self.rosters[self.candidate]),
                            ("candidate-inputs-after.json", self.rosters[self.candidate])):
            M.write_new(self.records / name, M.encoded(value))
        result_raw = M.encoded({"scope": M.DIAGNOSTIC_SCOPE, "data": "SYNTHETIC_NOT_QUALIFICATION", "exitCode": code})
        M.write_new(self.records / "jmdns-diagnostic-result.json", result_raw)
        # This text is deliberately NOT ciphertext and is never uploaded. The
        # producer's cryptography is not exercised by these guard-only controls.
        M.write_new(self.encrypted / "evidence.tar.gz.gpg", b"SYNTHETIC_NOT_OPENPGP_OR_EVIDENCE\n")
        manifest_raw = M.encoded({"data": "SYNTHETIC_MANIFEST_ONLY"})
        M.write_new(self.encrypted / "manifest.json", manifest_raw)
        self.value.update(diagnosticResultSha256=M.digest(result_raw), exportManifestSha256=M.digest(manifest_raw),
                          files={"diagnostic-encrypted/" + name: M.read_file(self.encrypted / name)[1]
                                 for name in M.ENCRYPTED_FILES})
        self.return_path = self.parent / "jmdns-diagnostic-return.json"
        self.bind_synthetic_return()
        self.env.update(P2PKIT_DIAGNOSTIC_ENCRYPTED_OUTCOME="success",
                        P2PKIT_DIAGNOSTIC_ENCRYPTED_ARTIFACT_ID="456",
                        P2PKIT_DIAGNOSTIC_ENCRYPTED_ARTIFACT_DIGEST="e" * 64)
        self.runner = SimpleNamespace()
        self.clean_calls, self.reserves = [], []
        self.allocation = {"data": "SYNTHETIC_ALLOCATION_NOT_AUTHORITY"}
        self.clean_error = None

    def bind_synthetic_return(self):
        """Rebind only freshly authored negative-case DATA, not stored evidence."""
        raw = M.encoded(self.value)
        if self.return_path.exists():
            self.return_path.write_bytes(raw)
        else:
            M.write_new(self.return_path, raw)
        self.env["P2PKIT_DEPENDENCY_DIAGNOSTIC_SHA256"] = M.digest(raw)

    def run(self, *, after=False):
        def clean(runner, root, sha, tree):
            assert runner is self.runner and root in (self.controller, self.candidate)
            prefix = "controller" if root == self.controller else "candidate"
            assert (sha, tree) == (self.value["request"][prefix + "_sha"], self.value["request"][prefix + "_tree"])
            self.clean_calls.append(prefix)
            if self.clean_error:
                raise self.clean_error

        def roster(runner, root):
            assert runner is self.runner and root in self.rosters
            return self.rosters[root]

        def helper(name, relative):
            assert (name, relative) == ("dependency_update_executor", "scripts/run-audit-command.py")
            return self.runner

        def budget(allocation, reserve):
            assert allocation is self.allocation
            self.reserves.append(reserve)

        output = io.StringIO()
        # Substitute a plain mapping, never mutate the actual process environment.
        # Genuine host admission, source Git inspection and native execution are
        # deliberately mocked, so this model cannot award any hosted acceptance.
        with mock.patch.object(M, "ROOT", self.controller), \
                mock.patch.object(M.os, "environ", self.env), \
                mock.patch.object(M, "operation", return_value=(self.parent, self.allocation)), \
                mock.patch.object(M, "environment", lambda _values: contextlib.nullcontext()), \
                mock.patch.object(M, "module", helper), mock.patch.object(M, "clean_source", clean), \
                mock.patch.object(M, "source_roster", roster), mock.patch.object(M, "budget", budget), \
                contextlib.redirect_stdout(output):
            M.guard_diagnostic_upload(after=after)
        return output.getvalue()


class CarrierControls(unittest.TestCase):
    def test_01_closed_six_input_request_preserves_both_operations(self):
        self.assertEqual(M.SHA_REQUEST_KEYS, SHA_FIELDS)
        self.assertEqual(M.REQUEST_KEYS, SHA_FIELDS | {"operation"})
        for operation in ("generate", "diagnose-jmdns"):
            request, env = request_and_environment(operation)
            self.assertEqual(M.request_data(request, env)["runAttempt"], "2")
            env["GITHUB_REF"] = "refs/heads/work/release-foundation-synthetic"
            env["GITHUB_WORKFLOW_REF"] = M.REPOSITORY + "/" + M.WORKFLOW + "@" + env["GITHUB_REF"]
            self.assertEqual(M.request_data(request, env)["ref"], env["GITHUB_REF"])

    def test_02_old_records_unknown_operations_and_extra_options_are_not_reinterpreted(self):
        request, env = request_and_environment()
        for value in (None, True, "", "diagnose", "diagnose-jmdns ", "GENERATE", "help", "a" * 40):
            with self.subTest(value=value), self.assertRaises(M.UpdateError):
                M.request_data({**request, "operation": value}, env)
        for changed in ({key: value for key, value in request.items() if key != "operation"},
                        {**request, "task": "help"}, {**request, "cpu": 999}, {**request, "recipient": "other"}):
            with self.assertRaises(M.UpdateError):
                M.request_data(changed, env)

    def test_03_each_sha_field_remains_an_exact_lowercase_commit_or_tree(self):
        request, env = request_and_environment()
        for name in SHA_FIELDS:
            for value in ("main", "A" * 40, "a" * 39, "a" * 41, True, None):
                with self.subTest(field=name, value=value), self.assertRaises(M.UpdateError):
                    M.request_data({**request, name: value}, env)

    def test_04_diagnostic_does_not_weaken_real_owner_event_ref_or_attempt_selection(self):
        request, env = request_and_environment()
        changes = (("GITHUB_EVENT_NAME", "push"), ("GITHUB_EVENT_NAME", "pull_request"),
                   ("GITHUB_ACTOR", "other"), ("GITHUB_TRIGGERING_ACTOR", "other"), ("GITHUB_ACTOR_ID", "1"),
                   ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_REPOSITORY", "fork/P2pKit"),
                   ("GITHUB_SHA", "f" * 40), ("GITHUB_WORKFLOW_SHA", "f" * 40),
                   ("GITHUB_RUN_ATTEMPT", "0"), ("GITHUB_RUN_ID", "01"))
        for key, value in changes:
            with self.subTest(key=key), self.assertRaises(M.UpdateError):
                M.request_data(request, {**env, key: value})
        for ref in ("refs/tags/v1.0.0", "refs/pull/1/merge", "refs/heads/work/nonphysical-integration-example"):
            changed = {**env, "GITHUB_REF": ref, "GITHUB_WORKFLOW_REF": M.REPOSITORY + "/" + M.WORKFLOW + "@" + ref}
            with self.assertRaises(M.UpdateError):
                M.request_data(request, changed)

    def test_05_diagnostic_budgets_are_shared_without_changing_generator_or_native_limits(self):
        self.assertEqual((M.DIAGNOSTIC_SECONDS, M.OBSERVATION_SECONDS), (1200, 120))
        self.assertEqual((M.PRODUCT_SECONDS, M.STOP_SECONDS, M.NATIVE_HEADROOM, M.JOB_SECONDS), (7200, 120, 180, 12600))
        self.assertEqual((M.EXPORT_SECONDS, M.UPLOAD_SECONDS), (120, 1320))
        declaration = {"startedMonotonicNs": START_NS, "deadlineMonotonicNs": START_NS + 1_200_000_000_000}
        first = M.diagnostic_command_seconds(declaration, START_NS)
        second = M.diagnostic_command_seconds(declaration, START_NS + 200_000_000_000)
        self.assertEqual((first, second), (900, 700))
        self.assertEqual(declaration["deadlineMonotonicNs"], START_NS + 1_200_000_000_000)
        for now in (True, START_NS - 1, START_NS + 900_000_000_000, START_NS + 1_200_000_000_000):
            with self.subTest(now=now), self.assertRaises(M.UpdateError):
                M.diagnostic_command_seconds(declaration, now)

    def test_06_actual_selected_case_plus_all_eight_original_mode_logs_required_for_pass(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True))
            result = M.diagnostic_test_data(reports.anchor, 0)
            self.assertEqual(result["status"], "PASSED_SELECTED_TEST_ONLY")
            self.assertEqual((result["reportedCases"], result["modePasses"]), (1, 8))
            self.assertEqual(result["reportSha256"], M.digest(xml_report()))

    def test_07_zero_selected_case_is_never_pass_even_with_zero_gradle_exit(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True))
            reports.rows = [row for row in reports.rows if row["source"] != XML_PATH]
            reports.write_manifest()
            with self.assertRaises(M.UpdateError):
                M.diagnostic_test_data(reports.anchor, 0)
            result = M.diagnostic_test_data(reports.anchor, 1)
            self.assertEqual(result["status"], "NOT_COMPLETED")
            self.assertEqual(result["reportedCases"], 0)

    def test_08_duplicate_or_wrong_method_xml_cannot_replace_exact_case(self):
        testcase = f'<testcase name="{METHOD}" classname="{CLASS}"></testcase>'.encode("utf-8")
        for raw in (xml_report(name="someOtherTest[jvm]"), xml_report(classname="other.Class"),
                    xml_report(tests="0").replace(testcase, b""),
                    xml_report(tests="2").replace(testcase, testcase + testcase),
                    xml_report().replace(b"</testsuite>", b'<testcase name="extra"/></testsuite>')):
            for code in (0, 1):
                with self.subTest(raw=raw, code=code), \
                        tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                    reports = RetainedReports(Path(temporary).resolve(strict=True), xml=raw)
                    with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_SELECTED_CASE$"):
                        M.diagnostic_test_data(reports.anchor, code)
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True))
            reports.rows.append(copy.deepcopy(reports.rows[0]))
            reports.write_manifest()
            with self.assertRaises(M.UpdateError):
                M.diagnostic_test_data(reports.anchor, 0)

    def test_09_failed_skipped_or_inconsistent_test_reports_cannot_be_green(self):
        raws = (xml_report(child="<failure/>", failures="1"), xml_report(child="<error/>", errors="1"),
                xml_report(child="<skipped/>", skipped="1"), xml_report(tests="0"), xml_report(errors="1"))
        for raw in raws:
            with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                reports = RetainedReports(Path(temporary).resolve(strict=True), xml=raw)
                with self.assertRaises(M.UpdateError):
                    M.diagnostic_test_data(reports.anchor, 0)
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True), xml=raws[0], modes=("control",))
            self.assertEqual(M.diagnostic_test_data(reports.anchor, 1)["status"], "FAILED")

    def test_10_failed_gradle_cannot_be_promoted_from_success_xml_or_logs(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True))
            result = M.diagnostic_test_data(reports.anchor, 1)
            self.assertEqual(result["status"], "NOT_COMPLETED")
            self.assertEqual(result["modePasses"], 0)

    def test_11_preexisting_alias_or_changed_report_bytes_are_not_original(self):
        changes = (("classification", "preexisting"), ("retained", "reports/other.xml"),
                   ("sha256", "a" * 64), ("bytes", 1))
        for field, value in changes:
            with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                reports = RetainedReports(Path(temporary).resolve(strict=True))
                reports.rows[0][field] = value
                reports.write_manifest()
                with self.assertRaises(M.UpdateError):
                    M.diagnostic_test_data(reports.anchor, 0)
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True))
            reports.rewrite(reports.rows[0], xml_report() + b"\n", rebind=False)
            with self.assertRaises(M.UpdateError):
                M.diagnostic_test_data(reports.anchor, 0)

    def test_12_incomplete_mixed_run_or_rescued_mode_roster_is_not_natural_pass(self):
        for text in ("PASS mode=control\nPASS mode=control\n", "PASS mode=other\n",
                     "FAIL mode=control\nPASS mode=control\n",
                     "phase=fixture_rescue_begin mode=control\nPASS mode=control\n"):
            with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                reports = RetainedReports(Path(temporary).resolve(strict=True))
                reports.rewrite(reports.rows[1], text.encode())
                with self.assertRaises(M.UpdateError):
                    M.diagnostic_test_data(reports.anchor, 0)
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True), modes=MODES[:-1])
            with self.assertRaises(M.UpdateError):
                M.diagnostic_test_data(reports.anchor, 0)
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            reports = RetainedReports(Path(temporary).resolve(strict=True))
            reports.rows[-1]["source"] = reports.rows[-1]["source"].replace("run-synthetic", "run-different")
            reports.write_manifest()
            with self.assertRaises(M.UpdateError):
                M.diagnostic_test_data(reports.anchor, 0)

    def test_13_xml_entities_and_malformed_documents_cannot_supply_a_case(self):
        for raw in (b"<broken", b'<!DOCTYPE testsuite [<!ENTITY x "synthetic">]>' + xml_report()):
            with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                reports = RetainedReports(Path(temporary).resolve(strict=True), xml=raw)
                with self.assertRaises(M.UpdateError):
                    M.diagnostic_test_data(reports.anchor, 0)

    def test_14_target_is_closed_and_reports_bound_before_observer_with_shared_clocks(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
            result = simulation.run()
            self.assertEqual(simulation.events, ["target", "retained-reports", "selected-test-data", "observer"])
            self.assertEqual(simulation.command_seconds, [899, 699])
            self.assertEqual(result["elapsedNs"], 220_000_000_000)
            self.assertEqual(result["observationElapsedNs"], 40_000_000_000)
            self.assertEqual(result["targetReceiptSha256"], simulation.receipt_hashes["target"])
            self.assertEqual(result["observerReceiptSha256"], simulation.receipt_hashes["observer"])
            self.assertEqual(result["dependencyAcceptance"], "NOT_PERFORMED")
            self.assertEqual(result["ordinaryQualification"], "NOT_PERFORMED")

    def test_15_actual_nonzero_target_is_preserved_even_if_observer_succeeds_or_fails(self):
        for target, observer, expected in ((1, 0, 1), (1, 3, 1), (0, 3, 3), (0, 0, 0)):
            with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                result = CarrierSimulation(Path(temporary).resolve(strict=True), target_code=target, observer_code=observer).run()
                self.assertEqual((result["exitCode"], result["targetExitCode"], result["observerExitCode"]),
                                 (expected, target, observer))
                self.assertEqual(result["cause"], "NOT_REPRODUCED" if target == 0 else "INDEPENDENT_ORIGINAL_REVIEW_REQUIRED")
                self.assertEqual(result["dependencyAcceptance"], "NOT_PERFORMED")

    def test_16_unknown_native_failure_or_preexisting_baseline_stops_before_observer(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
            simulation.hard_target_error = True
            with self.assertRaises(M.UpdateError):
                simulation.run()
            self.assertEqual(simulation.events, ["target"])
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
            with self.assertRaises(M.UpdateError):
                simulation.run(baseline=[{"preexisting": "synthetic"}])
            self.assertEqual(simulation.events, [])

    def test_17_wrong_target_source_record_argv_or_timing_stops_before_observer(self):
        changes = (
            ("requestSha256", "e" * 64), ("invocationId", "f" * 32), ("jobId", "wrong"),
            ("testExitCode", 0), ("requestedGradleArgv", ["help"]), ("executedGradleArgv", ["java"]),
            ("beforeObservationElapsedNs", 0), ("startedTestMonotonicNs", START_NS - 1),
            ("endTestMonotonicNs", START_NS + 300_000_000_000),
        )
        for field, value in changes:
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
                simulation.target_mutation = lambda row, key=field, item=value: row.update({key: item})
                with self.assertRaises(M.UpdateError):
                    simulation.run()
                self.assertEqual(simulation.events, ["target"])

    def test_18_observer_cannot_substitute_target_request_original_receipt_or_exit(self):
        for field, value in (("scope", M.SCOPE), ("requestSha256", "e" * 64),
                             ("invocationId", "e" * 32), ("jobId", "wrong"),
                             ("targetRecordSha256", "e" * 64), ("targetReturnSha256", "e" * 64),
                             ("observerExitCode", 1), ("observerExitCode", False),
                             ("observationDeadlineMonotonicNs", START_NS + 301_000_000_000),
                             ("observationElapsedNs", 0), ("endedMonotonicNs", START_NS + 221_000_000_000),
                             ("endedMonotonicNs", True), ("targetReceiptSha256", "e" * 64)):
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
                simulation.observer_mutation = lambda row, key=field, item=value: row.update({key: item})
                with self.assertRaises(M.UpdateError):
                    simulation.run()

    def test_19_total_deadline_is_not_renewed_and_observation_time_is_not_test_time(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
            simulation.clock[-1] = START_NS + 301_000_000_000
            result = simulation.run()
            self.assertEqual(result["observationElapsedNs"], 121_000_000_000)
            self.assertEqual(result["cause"], "INCONCLUSIVE_OBSERVATION_DEADLINE")
            self.assertEqual(result["exitCode"], 1)
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
            simulation.clock[2] = START_NS + 1_200_000_000_000
            with self.assertRaises(M.UpdateError):
                simulation.run()
            self.assertEqual(simulation.events, ["target"])

    def test_20_candidate_source_change_after_closed_observation_stays_fatal(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
            simulation.change_source = True
            with self.assertRaises(M.UpdateError):
                simulation.run()

    def retained_binding(self, parent, *, purpose="dependency-maintenance-jmdns-target", bad_hash=False,
                         baseline_changed=False, candidate_changed=False):
        request, _env = request_and_environment()
        state, records, candidate = (parent / name for name in ("state", "records", "candidate"))
        for path in (state, records, candidate):
            path.mkdir(mode=0o700)
        receipt = {"id": "a" * 32, "purpose": purpose, "productExitCode": 1}
        receipt_raw = M.encoded(receipt)
        receipt_path = state / "evidence" / receipt["id"] / "receipt.json"
        receipt_path.parent.mkdir(mode=0o700, parents=True)
        M.write_new(receipt_path, receipt_raw)
        baseline = []
        M.write_new(records / "candidate-report-baseline.json", M.encoded(baseline) + (b"\n" if baseline_changed else b""))
        source = {"commit": request["candidate_sha"], "tree": request["candidate_tree"],
                  "status": "", "diffSha256": M.digest(b"")}
        after = {**source, "status": " M synthetic-lock"} if candidate_changed else source

        def retain(actual_candidate, actual_state, arguments, actual_baseline, anchor):
            self.assertEqual((actual_candidate, actual_state, arguments, actual_baseline),
                             (candidate, state, [], baseline))
            rows = [{"source": "synthetic-report-only", "classification": "changed-since-admission"}]
            M.write_new(anchor / "report-manifest.json", M.encoded({"records": rows}))
            return rows

        runner = SimpleNamespace(source_snapshot=lambda actual: after if actual == candidate else None,
                                 retain_reports=retain)
        receipt_hash = "f" * 64 if bad_hash else M.digest(receipt_raw)
        result = M.retain_candidate_reports(runner, candidate, state, records, request, source, baseline,
                                             receipt, receipt_hash)
        return result, receipt_hash

    def test_21_diagnostic_report_custody_uses_original_target_receipt_and_distinct_scope(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
            result, receipt_hash = self.retained_binding(Path(temporary).resolve(strict=True))
            self.assertEqual(result["scope"], "MANUAL_JMDNS_REPORT_CUSTODY_V1")
            self.assertEqual(result["request"]["operation"], "diagnose-jmdns")
            self.assertEqual(result["purpose"], "dependency-maintenance-jmdns-target")
            self.assertEqual(result["receiptSha256"], receipt_hash)
            self.assertEqual(result["candidateBefore"], result["candidateAfter"])
            self.assertEqual(result["productExitCode"], 1)

    def test_22_generator_receipt_changed_baseline_or_changed_candidate_cannot_stand_in_for_target(self):
        for change in ({"purpose": "dependency-maintenance-generator"}, {"bad_hash": True},
                       {"baseline_changed": True}, {"candidate_changed": True}):
            with self.subTest(change=change), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                with self.assertRaises(M.UpdateError):
                    self.retained_binding(Path(temporary).resolve(strict=True), **change)

    def test_23_observer_cannot_rewrite_any_original_request_target_or_receipt(self):
        for relative in ("records/jmdns-request.json", "records/jmdns-target.json",
                         "records/jmdns-target-return.json", "state/evidence/" + "a" * 32 + "/receipt.json",
                         "state/evidence/" + "b" * 32 + "/receipt.json"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = CarrierSimulation(Path(temporary).resolve(strict=True))
                path = simulation.parent / relative

                def change_original():
                    path.write_bytes(path.read_bytes() + b"\n")

                simulation.after_observer = change_original
                with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_INPUT_CHANGED$"):
                    simulation.run()

    def test_24_diagnostic_return_is_separate_for_each_known_closed_ordinary_exit(self):
        for code in (0, 1, 3, 123):
            value, env = diagnostic_return(code)
            before = copy.deepcopy(value)
            self.assertEqual(M.diagnostic_return_data(value, env), before)
            self.assertEqual(value, before)
            self.assertEqual(set(value["files"]), {"diagnostic-encrypted/" + name for name in M.ENCRYPTED_FILES})
        self.assertNotEqual(M.DIAGNOSTIC_SCOPE, M.SCOPE)
        self.assertNotEqual(M.DIAGNOSTIC_SCOPE, M.FAILED_SCOPE)

    def test_25_diagnostic_envelope_cannot_claim_generation_or_another_binding(self):
        value, env = diagnostic_return()
        changes = (
            ("schema", True), ("scope", M.SCOPE), ("scope", M.FAILED_SCOPE), ("policySha256", "f" * 64),
            ("exportManifestSha256", "A" * 64), ("diagnosticResultSha256", "2" * 63),
            ("producerReturn", "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN"),
            ("producerReturn", "FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN"),
            ("github", {**value["github"], "runAttempt": "3"}),
            ("request", {**value["request"], "controller_sha": "f" * 40}),
            ("request", {**value["request"], "operation": "generate"}),
            ("files", {"failed-encrypted/" + name: {} for name in M.ENCRYPTED_FILES}),
            ("files", {**value["files"], "public/generated-dependencies.patch": {}}),
        )
        for field, changed in changes:
            with self.subTest(field=field), self.assertRaises(M.UpdateError):
                M.diagnostic_return_data({**value, field: changed}, env)
        for field in value:
            with self.subTest(missing=field), self.assertRaises(M.UpdateError):
                M.diagnostic_return_data({name: item for name, item in value.items() if name != field}, env)
        with self.assertRaises(M.UpdateError):
            M.diagnostic_return_data({**value, "candidateAcceptance": "PASS"}, env)

    def test_26_real_outcome_and_exclusive_token_cannot_be_cancelled_reserved_or_promoted(self):
        for code in (0, 1):
            value, env = diagnostic_return(code)
            for outcome in ("failure" if code == 0 else "success", "cancelled", "skipped", "", None):
                with self.subTest(code=code, outcome=outcome), self.assertRaises(M.UpdateError):
                    M.diagnostic_return_data(value, {**env, "P2PKIT_DEPENDENCY_GENERATOR_OUTCOME": outcome})
            for key in ("P2PKIT_DEPENDENCY_SUCCESS_SHA256", "P2PKIT_DEPENDENCY_FAILED_SHA256"):
                with self.subTest(key=key), self.assertRaises(M.UpdateError):
                    M.diagnostic_return_data(value, {**env, key: "a" * 64})
        for code in (True, -1, 1.0, 124, 125, 137, 143, 255, None):
            value, env = diagnostic_return(code)
            with self.subTest(code=code), self.assertRaises(M.UpdateError):
                M.diagnostic_return_data(value, env)

    def test_27_both_upload_guards_reread_same_objects_source_and_deadline_without_crypto(self):
        for code in (0, 1):
            with tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = UploadSimulation(Path(temporary).resolve(strict=True), code=code)
                before = simulation.run()
                after = simulation.run(after=True)
                self.assertEqual(simulation.clean_calls, ["controller", "candidate", "controller", "candidate"])
                self.assertEqual(simulation.reserves, [M.UPLOAD_SECONDS, 0])
                self.assertIn("no dependency, ordinary or Release qualification", before)
                self.assertIn("actual test/observer outcomes remain separate", after)
                self.assertNotIn("RESULT: PASS", before + after)
                self.assertNotIn("SYNTHETIC", before + after)
                for name in M.ENCRYPTED_FILES:
                    self.assertEqual(M.read_file(simulation.encrypted / name)[1],
                                     simulation.value["files"]["diagnostic-encrypted/" + name])

    def test_28_original_return_result_and_export_manifest_hashes_must_all_agree(self):
        for part in ("return", "result", "result-hash", "manifest-hash", "missing-output-hash"):
            with self.subTest(part=part), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = UploadSimulation(Path(temporary).resolve(strict=True))
                if part in ("return", "result"):
                    path = simulation.return_path if part == "return" else simulation.records / "jmdns-diagnostic-result.json"
                    path.write_bytes(path.read_bytes() + b"\n")
                elif part == "missing-output-hash":
                    simulation.env["P2PKIT_DEPENDENCY_DIAGNOSTIC_SHA256"] = ""
                else:
                    field = "diagnosticResultSha256" if part == "result-hash" else "exportManifestSha256"
                    simulation.value[field] = "f" * 64
                    simulation.bind_synthetic_return()
                with self.assertRaises(M.UpdateError):
                    simulation.run()

    def test_29_diagnostic_export_cannot_coexist_with_generation_plaintext_or_extra_objects(self):
        for extra in ("generator-success.json", "generator-failed-product.json", "outputs/public",
                      "outputs/encrypted", "outputs/failed-encrypted", "outputs/diagnostic-encrypted/extra.log"):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = UploadSimulation(Path(temporary).resolve(strict=True))
                path = simulation.parent / extra
                if extra in ("outputs/public", "outputs/encrypted", "outputs/failed-encrypted"):
                    path.mkdir(mode=0o700)
                else:
                    M.write_new(path, b"SYNTHETIC_EXTRA_NOT_EVIDENCE\n")
                with self.assertRaises(M.UpdateError):
                    simulation.run()

    def test_30_upload_rechecks_both_clean_sources_and_before_after_byte_rosters(self):
        for part in ("controller", "candidate", "controller-inputs.json", "candidate-inputs-before.json",
                     "candidate-inputs-after.json", "clean-source"):
            with self.subTest(part=part), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                simulation = UploadSimulation(Path(temporary).resolve(strict=True))
                if part in ("controller", "candidate"):
                    simulation.rosters[getattr(simulation, part)] = {"changed-synthetic-source": {"sha256": "f" * 64}}
                elif part == "clean-source":
                    simulation.clean_error = M.UpdateError("CLEAN_SOURCE")
                else:
                    path = simulation.records / part
                    path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaises(M.UpdateError):
                    simulation.run(after=True)

    def test_31_same_content_is_not_the_same_original_export_object(self):
        for name in M.ENCRYPTED_FILES:
            for change in ("replace", "mode", "bytes"):
                with self.subTest(name=name, change=change), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                    simulation = UploadSimulation(Path(temporary).resolve(strict=True))
                    path = simulation.encrypted / name
                    raw = path.read_bytes()
                    if change == "replace":
                        # Keep the original inode live so the OS cannot recycle
                        # it for the intentionally substituted synthetic object.
                        path.rename(simulation.parent / "synthetic-held-original")
                        M.write_new(path, raw)
                    elif change == "mode":
                        path.chmod(0o640)
                    else:
                        path.write_bytes(raw + b"changed\n")
                    with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_UPLOAD_BYTES_CHANGED$"):
                        simulation.run(after=True)

    def test_32_after_upload_requires_actual_success_id_and_digest_not_a_claimed_file(self):
        for field, values in (("OUTCOME", ("failure", "cancelled", "skipped", "", None)),
                              ("ARTIFACT_ID", ("", "0", "01", "-1", "1.0")),
                              ("ARTIFACT_DIGEST", ("", "A" * 64, "a" * 63, "a" * 64 + "\n"))):
            for value in values:
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory(prefix="p2pkit-jmdns-carrier-synthetic-") as temporary:
                    simulation = UploadSimulation(Path(temporary).resolve(strict=True))
                    simulation.env["P2PKIT_DIAGNOSTIC_ENCRYPTED_" + field] = value
                    with self.assertRaisesRegex(M.UpdateError, "^DIAGNOSTIC_UPLOAD_RETURN$"):
                        simulation.run(after=True)

    def test_33_source_keeps_diagnostic_tokens_and_outputs_outside_generation_success(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        generate = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "generate")
        assignments = {target.id: node.value for node in ast.walk(generate) if isinstance(node, ast.Assign)
                       for target in node.targets if isinstance(target, ast.Name)}
        self.assertEqual(ast.unparse(assignments["generation_success"]), "not diagnostic_mode and failed is None")
        self.assertEqual(ast.unparse(assignments["encrypted_group"]),
                         "'diagnostic-encrypted' if diagnostic_mode else 'failed-encrypted' if failed is not None else 'encrypted'")
        self.assertEqual(ast.unparse(assignments["record_name"]),
                         "'jmdns-diagnostic-return.json' if diagnostic_mode else 'generator-success.json' if failed is None else 'generator-failed-product.json'")
        tokens = [node for node in ast.walk(generate) if isinstance(node, ast.IfExp) and
                  isinstance(node.body, ast.Constant) and node.body.value == "diagnosticSha256="]
        self.assertEqual(len(tokens), 1)
        self.assertEqual(ast.unparse(tokens[0]),
                         "'diagnosticSha256=' if diagnostic_mode else 'successSha256=' if failed is None else 'failedProductSha256='")
        publication = next(node for node in ast.walk(generate) if isinstance(node, ast.If) and
                           isinstance(node.test, ast.Name) and node.test.id == "generation_success")
        self.assertIn("public = parent / 'outputs/public'", ast.unparse(publication))
        self.assertEqual(len(publication.orelse), 1)
        self.assertIn("'FAILED_OUTPUT_NOT_EXCLUSIVE'", ast.unparse(publication.orelse[0]))
        diagnostic_return_branch = next(node for node in generate.body if isinstance(node, ast.If) and
                                        isinstance(node.test, ast.Name) and node.test.id == "diagnostic_mode")
        self.assertEqual(ast.unparse(diagnostic_return_branch.body[-1]), "return diagnostic['exitCode']")

    def test_34_source_keeps_prerequisite_failure_diagnostic_only_and_no_partial_writer(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        generate = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "generate")
        guarded = next(node for node in ast.walk(generate) if isinstance(node, ast.Try))
        self.assertEqual(len(guarded.handlers), 1)
        handler = guarded.handlers[0]
        self.assertEqual(ast.unparse(handler.type), "ClosedProductFailure")
        diagnostic_failure = next(node for node in handler.body if isinstance(node, ast.If) and
                                  isinstance(node.test, ast.Name) and node.test.id == "diagnostic_mode")
        self.assertEqual(ast.unparse(diagnostic_failure.body[0]),
                         "require(failed.receipt['purpose'] == 'dependency-maintenance-prerequisites', 'DIAGNOSTIC_UNEXPECTED_FAILURE')")
        fields = diagnostic_failure.body[1].value
        self.assertIsInstance(fields, ast.Dict)
        data = {key.value: ast.unparse(value) for key, value in zip(fields.keys, fields.values)}
        self.assertEqual(data["phase"], "'PREREQUISITES'")
        self.assertEqual(data["test"], "{'status': 'NOT_RUN'}")
        self.assertEqual(data["exitCode"], "failed.code")
        route = next(node for node in guarded.body if isinstance(node, ast.If) and
                     isinstance(node.test, ast.Name) and node.test.id == "diagnostic_mode")
        self.assertEqual([ast.unparse(node) for node in route.body], [
            "budget(allocation, DIAGNOSTIC_SECONDS + FINAL_RESERVE)",
            "diagnostic = run_diagnostic(runner, parent, context, candidate, records, request, github, candidate_source, candidate_reports_before)",
        ])
        # Only the original else branch may invoke the full sanctioned writer;
        # the diagnostic is not a reduced writer, a help task, or lock generation.
        writer = [node for node in ast.walk(route) if isinstance(node, ast.Call) and
                  isinstance(node.func, ast.Name) and node.func.id == "owned_command"]
        self.assertEqual(len(writer), 1)
        self.assertEqual(writer[0].args[3].value, "dependency-maintenance-generator")
        self.assertEqual(ast.unparse(writer[0].args[-1]), "PRODUCT_SECONDS")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(
        unittest.TestSuite((
            unittest.defaultTestLoader.loadTestsFromTestCase(CarrierControls),
            unittest.defaultTestLoader.loadTestsFromTestCase(SelectedCaseIdentityControls),
        )))
    if result.wasSuccessful():
        print(f"RESULT: PASS — {result.testsRun} focused carrier DATA/source controls; "
              "no native execution, encryption, upload or hosted qualification")
    raise SystemExit(0 if result.wasSuccessful() else 1)
