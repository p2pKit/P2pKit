#!/usr/bin/env python3
"""Pure synthetic canonical-record controls; never a producer/native execution.

The real supplier's pure argv/JSON/batch formatters are checked, not its init,
executor, processes, file readers or clocks. No cache or private original exists
in these fixtures. A passing model cannot supply missing budget/outer retirement.
"""
from contextlib import ExitStack
import copy
import importlib.util
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_processes as N
import hosted_cache_bootstrap_producer as P
import hosted_dependency_seed_files as S


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


I = module("bootstrap_producer_identity_models", "scripts/tests/hosted-cache-bootstrap-identity-test.py")
A = module("bootstrap_producer_canonical_supplier", "scripts/run-audit-command.py")
JVM = "-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8"
COMMAND = ["help", "--console=plain", "--no-configure-on-demand"]
FLAGS = ["--no-daemon", "--dependency-verification", "strict", "--rerun-tasks", "--no-build-cache",
         "--no-configuration-cache", "--no-parallel", "--max-workers=2",
         "-Pkotlin.compiler.execution.strategy=in-process", "-Dorg.gradle.jvmargs=" + JVM]


class ProducerModels(I.OfflineCase):
    def setUp(self):
        super().setUp()
        self.configure(I.SELECTIONS[0])

    def configure(self, row):
        name, _profile, role, system, arch = row
        self.env.update(RUNNER_OS=system, RUNNER_ARCH=arch)
        self.event["inputs"]["selection"] = name
        self.admitted_raw = self.admit().record
        self.role = role
        path = PureWindowsPath if role == "windows-x64" else PurePosixPath
        root = path(r"D:\a\P2pKit\P2pKit" if role == "windows-x64" else "/home/runner/work/P2pKit/P2pKit")
        state = path(r"D:\a\_temp\synthetic-bootstrap\state" if role == "windows-x64" else
                     "/home/runner/work/_temp/synthetic-bootstrap/state")
        self.context = {"schema": 1, "root": str(root), "expectedCommit": I.SOURCE, "tree": I.TREE,
            "source": {"commit": I.SOURCE, "tree": I.TREE, "status": "", "diffSha256": P.digest(b"")},
            "host": role, "gradleHome": str(state / "gradle-home"), "createdUtc": "2026-09-17T00:00:00+00:00",
            "id": "a" * 32, "gradlePropertiesSha256": "d" * 64, "javaHomes": [], "preexistingOutputPaths": []}
        self.canonical_raw = A.json_bytes(self.context)
        self.request = P.make_request(self.admitted_raw, self.canonical_raw,
                                      invocation="b" * 32, ancestor_invocations=["c" * 32])
        self.request_raw = P.encoded(self.request)
        self.start = {key: copy.deepcopy(self.request[key]) for key in (
            "id", "purpose", "kind", "requestedArgv", "cwd", "wrapper", "host", "jobId", "gradleHome",
            "ancestorInvocationIds", "evidenceDirectory")}
        self.start.update(schema=1, startedUtc="2026-09-17T00:00:00+00:00", controllerPid=100,
            sourceBefore=None, sourceAfter=None, productExitCode=None, stopExitCode=None, finalExitCode=125,
            sourceUnchanged=False, ownedSurvivors=[], errors=[])
        executed = [self.request["wrapper"], *A.gradle_arguments(COMMAND)]
        stop = [self.request["wrapper"], "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
                "-Dorg.gradle.jvmargs=" + JVM]
        ownership = {"backend": {"linux-x64": "linux-proc-pidfd", "windows-x64": "windows-job-list-suspended",
            "macos-arm64": "darwin-libproc-audit-token", "macos-x64": "darwin-libproc-audit-token"}[role],
            "scope": "kernel-job-no-breakaway-kill-on-close" if role == "windows-x64" else
                     "controlled-marker-inheriting-descendants", "job": "a" * 32, "invocation": "b" * 32,
            "startedIdentities": [], "discoveryErrors": [],
            "launches": [self.launch(executed, 101), self.launch(stop, 102)]}
        if role != "windows-x64":
            ownership["discoveryReconciliations"] = []
        if role.startswith("macos-"):
            ownership.update(observationReconciliations=[], drainReconciliations=[{
                "startedMonotonic": 10.0, "graceSeconds": 5.0, "killWaitSeconds": 5.0,
                "phases": [{"signal": 15, "deadlineMonotonic": 15.0}], "signalReconciliations": [],
                "outcome": "retired", "finishedMonotonic": 10.2}])
        self.receipt = {**copy.deepcopy(self.start), "executedArgv": executed,
            "executedArgvSemantics": "logical-command; exact platform launch is ownership.launches[productLaunchIndex]",
            "productLaunchIndex": 0, "productPid": 101, "productStartedUtc": "2026-09-17T00:00:01+00:00",
            "productEndedUtc": "2026-09-17T00:00:02+00:00", "stopArgv": stop, "stopLaunchIndex": 1,
            "stopStartedUtc": "2026-09-17T00:00:02+00:00", "stopEndedUtc": "2026-09-17T00:00:03+00:00",
            "sourceBefore": copy.deepcopy(self.context["source"]), "sourceAfter": copy.deepcopy(self.context["source"]),
            "sourceUnchanged": True, "productExitCode": 0, "stopExitCode": 0, "finalExitCode": 0,
            "ownership": ownership, "reports": [], "endedUtc": "2026-09-17T00:00:04+00:00", "durationSeconds": 4.0}
        self.start_raw, self.receipt_raw = map(A.json_bytes, (self.start, self.receipt))

    def launch(self, argv, pid):
        value = {"requestedArgv": list(argv), "resolvedArgv": list(argv), "cwd": self.context["root"],
                 "created": True, "pid": pid}
        if self.role != "windows-x64":
            return {**value, "api": "subprocess.Popen", "shell": False, "executable": argv[0]}
        cmd = r"C:\Windows\System32\cmd.exe"
        return {**value, "api": "CreateProcessW", "resumed": True, "jobAssignedBeforeResume": True,
            "batch": True, "applicationName": cmd, "commandLine": N.batch_command_line(cmd, argv),
            "resourceCleanup": [{"phase": "launch-temporary", "resource": name, "status": "RETIRED"} for name in
                ("startup-attributes", "launch-handle-1", "launch-handle-3", "launch-handle-4", "primary-thread")]}

    def observe(self, **changed):
        values = dict(request_raw=self.request_raw, admitted_raw=self.admitted_raw, canonical_raw=self.canonical_raw,
                      start_raw=self.start_raw, receipt_raw=self.receipt_raw, original_exit_code=0)
        values.update(changed)
        return P.observe_canonical(**values)

    def test_six_request_cohorts_use_canonical_configuration_recipe_not_ordinary_tasks(self):
        self.assertEqual(A.gradle_arguments(COMMAND), COMMAND + FLAGS)
        for row in I.SELECTIONS:
            self.configure(row)
            with self.subTest(selection=row[0]):
                self.assertEqual(self.request["profile"], "cache-bootstrap")
                self.assertEqual(self.request["cacheCohort"], {"profile": row[1], "role": row[2]})
                self.assertEqual(self.request["requestedArgv"], COMMAND)
                self.assertEqual(self.request["executedArgv"], [self.request["wrapper"], *COMMAND, *FLAGS])
                self.assertEqual(self.request["purpose"], "cache-bootstrap-configuration")
                self.assertNotIn("timeout", self.request)
                self.assertNotIn("jobBudgetSha256", self.request)
                self.assertNotIn("primaryAbiAccounting", self.request)

    def test_all_six_canonical_models_withhold_budget_outer_retirement_save_and_tests(self):
        for row in I.SELECTIONS:
            self.configure(row)
            with self.subTest(selection=row[0]):
                observed = self.observe()
                self.assertEqual(observed["status"], "CANONICAL_CONFIGURATION_REPORTED_SUCCESS")
                self.assertEqual(observed["enclosingNativeRetirement"], "NOT_OBSERVED_HERE")
                self.assertEqual(observed["budgetAcceptance"], "NOT_ADMITTED_HERE")
                self.assertEqual(observed["testAcceptance"], "NOT_PERFORMED")
                self.assertIs(observed["exportSaveAuthority"], False)
                self.assertEqual(P.validate_observation(observed, self.request_raw, self.admitted_raw,
                    self.canonical_raw, self.start_raw, self.receipt_raw, original_exit_code=0), observed)
                with self.assertRaisesRegex(S.SeedError, "BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
                    S.require_connected_execution(self.admitted_raw)

    def test_only_original_bootstrap_identity_and_canonical_source_are_eligible(self):
        changes = ({"host": "windows-x64"}, {"expectedCommit": "f" * 40}, {"tree": "f" * 40},
                   {"source": {**self.context["source"], "status": " M source"}},
                   {"source": {**self.context["source"], "diffSha256": "f" * 64}}, {"schema": True})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(P.ProducerError):
                P.make_request(self.admitted_raw, A.json_bytes({**self.context, **change}),
                               invocation="b" * 32, ancestor_invocations=["c" * 32])
        with self.assertRaisesRegex(P.ProducerError, "ADMISSION"):
            P.make_request(b'{}', self.canonical_raw, invocation="b" * 32, ancestor_invocations=["c" * 32])

    def test_original_canonical_context_replacement_cannot_match_retained_request(self):
        for key, value in (("id", "e" * 32), ("gradlePropertiesSha256", "f" * 64),
                           ("createdUtc", "2026-09-17T01:00:00+00:00")):
            with self.subTest(key=key), self.assertRaisesRegex(P.ProducerError, "REQUEST_CHANGED"):
                self.observe(canonical_raw=A.json_bytes({**self.context, key: value}))

    def test_home_paths_are_lexical_separate_from_source_not_host_resolution(self):
        for home in ("relative/gradle-home", self.context["root"] + "/gradle-home",
                     self.context["root"] + "/../gradle-home", "/gradle-home", "/tmp/not-the-home"):
            with self.subTest(home=home), self.assertRaises(P.ProducerError):
                P.make_request(self.admitted_raw, A.json_bytes({**self.context, "gradleHome": home}),
                               invocation="b" * 32, ancestor_invocations=["c" * 32])

    def test_invocation_and_nonempty_bounded_unique_original_ancestors(self):
        for invocation, ancestors in ((True, ["c" * 32]), ("short", ["c" * 32]), ("b" * 32, []),
            ("b" * 32, ["b" * 32]), ("b" * 32, ["c" * 32, "c" * 32]), ("b" * 32, [None]),
            ("b" * 32, [format(i, "032x") for i in range(32)])):
            with self.subTest(invocation=invocation, ancestors=ancestors), self.assertRaises(P.ProducerError):
                P.make_request(self.admitted_raw, self.canonical_raw,
                               invocation=invocation, ancestor_invocations=ancestors)

    def test_request_cannot_add_budget_command_or_change_cohort(self):
        for changes in ({"requestedArgv": ["check"]}, {"kind": "command"}, {"timeout": 5400},
                        {"testAcceptance": "PASS"}, {"cacheCohort": {"profile": "full", "role": "macos-arm64"}}):
            with self.subTest(changes=changes), self.assertRaisesRegex(P.ProducerError, "REQUEST_CHANGED"):
                self.observe(request_raw=P.encoded({**self.request, **changes}))

    def test_original_exit_cannot_be_inferred_from_a_passing_receipt(self):
        for code in (None, False, True, "0", -1, 1, 125, 255):
            with self.subTest(code=code), self.assertRaisesRegex(P.ProducerError, "ORIGINAL_EXIT"):
                self.observe(original_exit_code=code)

    def test_canonical_product_stop_and_final_failure_remain_distinct_from_exit(self):
        for key in ("productExitCode", "stopExitCode", "finalExitCode"):
            for value in (None, False, "0", 1, 125):
                with self.subTest(key=key, value=value), self.assertRaises(P.ProducerError):
                    self.observe(receipt_raw=A.json_bytes({**self.receipt, key: value}))
        for key, value in (("errors", ["synthetic close uncertainty"]), ("ownedSurvivors", [{"pid": 101}]),
                           ("sourceUnchanged", False)):
            with self.subTest(key=key), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes({**self.receipt, key: value}))

    def test_start_is_the_original_prelaunch_state_not_a_terminal_receipt(self):
        for changes in ({"sourceBefore": self.context["source"]}, {"productExitCode": 0}, {"finalExitCode": 0},
                        {"sourceUnchanged": True}, {"errors": ["synthetic error"]}, {"retirement": "KNOWN"}):
            with self.subTest(changes=changes), self.assertRaises(P.ProducerError):
                self.observe(start_raw=A.json_bytes({**self.start, **changes}))

    def test_terminal_cannot_relabel_original_start_job_pid_home_or_source(self):
        for key, value in (("id", "d" * 32), ("jobId", "d" * 32), ("controllerPid", 101),
            ("startedUtc", "2026-09-17T00:00:01+00:00"), ("gradleHome", "/tmp/other/gradle-home"),
            ("ancestorInvocationIds", ["d" * 32]), ("sourceAfter", {**self.context["source"], "tree": "f" * 40})):
            with self.subTest(key=key), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes({**self.receipt, key: value}))

    def test_requested_executed_and_stop_vectors_are_independently_exact(self):
        for key in ("requestedArgv", "executedArgv", "stopArgv"):
            for value in ([], self.receipt[key] + ["--offline"], self.receipt[key][:-1]):
                with self.subTest(key=key, value=value), self.assertRaises(P.ProducerError):
                    self.observe(receipt_raw=A.json_bytes({**self.receipt, key: value}))

    def test_native_launch_indices_are_exact_typed_and_pid_is_bound(self):
        for key, value in (("productLaunchIndex", False), ("productLaunchIndex", 1), ("stopLaunchIndex", True),
                           ("stopLaunchIndex", 0), ("productPid", False), ("productPid", 999)):
            with self.subTest(key=key, value=value), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes({**self.receipt, key: value}))

    def test_native_scope_declarations_cannot_be_swapped_or_incomplete(self):
        for key, value in (("backend", "windows-job-list-suspended"), ("job", "d" * 32),
            ("invocation", "d" * 32), ("scope", "process-group"), ("discoveryErrors", ["synthetic uncertainty"]),
            ("startedIdentities", None), ("launches", []), ("launches", self.receipt["ownership"]["launches"] * 2)):
            changed = copy.deepcopy(self.receipt)
            changed["ownership"][key] = value
            with self.subTest(key=key), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes(changed))

    def test_posix_native_logical_and_resolved_launch_must_agree(self):
        for key, value in (("requestedArgv", ["other"]), ("resolvedArgv", ["other"]), ("created", False),
            ("shell", True), ("api", "os.system"), ("executable", "/tmp/other"), ("cwd", "/tmp/other")):
            for index in (0, 1):
                changed = copy.deepcopy(self.receipt)
                changed["ownership"]["launches"][index][key] = value
                with self.subTest(key=key, index=index), self.assertRaises(P.ProducerError):
                    self.observe(receipt_raw=A.json_bytes(changed))

    def test_windows_batch_framing_suspended_membership_and_temporary_retirement(self):
        self.configure(I.SELECTIONS[1])
        for key, value in (("commandLine", "cmd.exe /c other"), ("batch", False), ("resumed", False),
            ("jobAssignedBeforeResume", False), ("applicationName", r"C:\Windows\cmd.exe"),
            ("resourceCleanup", []), ("resourceCleanup", [{"status": "UNKNOWN"}])):
            for index in (0, 1):
                changed = copy.deepcopy(self.receipt)
                changed["ownership"]["launches"][index][key] = value
                with self.subTest(key=key, index=index), self.assertRaises(P.ProducerError):
                    self.observe(receipt_raw=A.json_bytes(changed))

    def test_windows_batch_counterpart_preserves_exact_supplier_quoting(self):
        cmd = r"C:\Windows\System32\cmd.exe"
        for root in (r"D:\a\P2pKit", r"D:\a\space and (parentheses)", "D:\\a\\unicode-\u03bb"):
            argv = [root + "\\gradlew.bat", *COMMAND, *FLAGS]
            with self.subTest(root=root):
                self.assertEqual(P._batch_line(cmd, argv), N.batch_command_line(cmd, argv))
        for raw in ("D:\\percent%\\gradlew.bat", 'D:\\quoted"\\gradlew.bat', "D:\\amp&\\gradlew.bat"):
            with self.subTest(raw=raw), self.assertRaises(P.ProducerError):
                P._batch_line(cmd, [raw, *COMMAND, *FLAGS])

    def test_observation_never_acquires_a_path_clock_native_library_or_process(self):
        for row in I.SELECTIONS:
            self.configure(row)
            with self.subTest(selection=row[0]), ExitStack() as guards:
                for target in ("builtins.open", "os.open", "os.stat", "os.lstat", "time.time", "time.monotonic",
                               "ctypes.CDLL", "subprocess.run", "subprocess.Popen"):
                    guards.enter_context(patch(target, side_effect=AssertionError("PURE_REPORTS_ONLY")))
                self.observe()

    def test_darwin_original_drain_uncertainty_cannot_be_hidden_by_later_quiet(self):
        self.configure(I.SELECTIONS[2])
        for value in ([], [{"outcome": "unresolved"}], [{"outcome": "last-observed-live"}],
                      [{"outcome": "retired", "error": "synthetic uncertainty"}],
                      [{"outcome": "failed"}, {"outcome": "retired"}]):
            changed = copy.deepcopy(self.receipt)
            changed["ownership"]["drainReconciliations"] = value
            with self.subTest(value=value), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes(changed))

    def darwin_histories(self):
        identity = {"pid": 101, "uid": 1000, "uniqueId": 201, "startSeconds": 1,
                    "startMicroseconds": 0, "pidVersion": 1, "live": True}
        discovery = {"identity": identity, "message": "synthetic original discovery failure",
            "firstFailure": "synthetic original discovery failure", "failures": 1, "outcome": "unresolved",
            "lastIdentity": identity, "lastFailure": "synthetic original discovery failure"}
        signal = {"identity": identity, "firstFailure": "synthetic original token failure", "failures": 1,
            "firstSignal": 15, "firstObservation": 0, "outcome": "unresolved", "lastIdentity": identity,
            "lastFailure": "synthetic original token failure", "lastSignal": 15, "lastObservation": 0}
        return discovery, signal

    def test_darwin_empty_error_label_cannot_hide_unresolved_terminal_discovery(self):
        for row in I.SELECTIONS[2:]:
            self.configure(row)
            discovery, _signal = self.darwin_histories()
            for outcome in ("unresolved", "recovered", "signal-succeeded", "retired", None, False, {}):
                changed = copy.deepcopy(self.receipt)
                changed["ownership"]["discoveryReconciliations"] = [{**discovery, "outcome": outcome}]
                with self.subTest(selection=row[0], outcome=outcome), self.assertRaises(P.ProducerError):
                    self.observe(receipt_raw=A.json_bytes(changed))

    def test_darwin_retired_label_cannot_hide_unresolved_signal_in_any_drain(self):
        for row in I.SELECTIONS[2:]:
            self.configure(row)
            _discovery, signal = self.darwin_histories()
            for outcome in ("unresolved", "recovered", "owned", "retired", None, False, {}):
                changed = copy.deepcopy(self.receipt)
                drain = changed["ownership"]["drainReconciliations"][0]
                drain["signalReconciliations"] = [{**signal, "outcome": outcome}]
                # A later quiet drain cannot rewrite the prior drain's pending
                # terminal disposition, even under a positive outer label.
                changed["ownership"]["drainReconciliations"].append(
                    copy.deepcopy(self.receipt["ownership"]["drainReconciliations"][0]))
                with self.subTest(selection=row[0], outcome=outcome), self.assertRaises(P.ProducerError):
                    self.observe(receipt_raw=A.json_bytes(changed))

    def test_darwin_discovery_and_signal_terminal_rosters_cannot_be_malformed(self):
        self.configure(I.SELECTIONS[2])
        for value in ([None], ["unresolved"], [{}], [{"outcome": []}]):
            changed = copy.deepcopy(self.receipt)
            changed["ownership"]["discoveryReconciliations"] = value
            with self.subTest(discovery=value), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes(changed))
        for value in (None, {}, "", [None], ["unresolved"], [{}], [{"outcome": []}]):
            changed = copy.deepcopy(self.receipt)
            changed["ownership"]["drainReconciliations"][0]["signalReconciliations"] = value
            with self.subTest(signals=value), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes(changed))
        changed = copy.deepcopy(self.receipt)
        del changed["ownership"]["drainReconciliations"][0]["signalReconciliations"]
        with self.assertRaises(P.ProducerError):
            self.observe(receipt_raw=A.json_bytes(changed))

    def test_resolved_darwin_histories_keep_first_failures_without_becoming_retirement_authority(self):
        for row in I.SELECTIONS[2:]:
            self.configure(row)
            discovery, signal = self.darwin_histories()
            for discovery_outcome in ("lifetime-ended", "nonrunning", "replaced", "unmarked", "owned"):
                for signal_outcome in ("absent", "nonrunning", "replaced", "signal-succeeded"):
                    changed = copy.deepcopy(self.receipt)
                    native = changed["ownership"]
                    native["discoveryReconciliations"] = [{**discovery, "outcome": discovery_outcome}]
                    native["drainReconciliations"][0]["signalReconciliations"] = [{**signal, "outcome": signal_outcome}]
                    native["observationReconciliations"] = [{"operation": "task token", "identity": signal["identity"],
                        "lastIdentity": signal["identity"], "attempts": 26,
                        "firstFailure": signal["firstFailure"], "lastFailure": signal["lastFailure"],
                        "outcome": "unresolved"}]
                    with self.subTest(selection=row[0], discovery=discovery_outcome, signal=signal_outcome):
                        observed = self.observe(receipt_raw=A.json_bytes(changed))
                        self.assertEqual(observed["status"], "CANONICAL_CONFIGURATION_REPORTED_SUCCESS")
                        self.assertEqual(observed["enclosingNativeRetirement"], "NOT_OBSERVED_HERE")
                        self.assertIs(observed["exportSaveAuthority"], False)

    def test_observation_binds_exact_original_bytes_not_only_semantic_receipts(self):
        observed = self.observe()
        changed = P.encoded(self.receipt)
        self.assertNotEqual(changed, self.receipt_raw)
        self.assertEqual(self.observe(receipt_raw=changed)["status"], observed["status"])
        with self.assertRaisesRegex(P.ProducerError, "OBSERVATION_CHANGED"):
            P.validate_observation(observed, self.request_raw, self.admitted_raw, self.canonical_raw,
                                   self.start_raw, changed, original_exit_code=0)
        for key, value in (("exportSaveAuthority", True), ("enclosingNativeRetirement", "KNOWN"),
                           ("budgetAcceptance", "PASS"), ("testAcceptance", "PASS")):
            with self.subTest(key=key), self.assertRaisesRegex(P.ProducerError, "OBSERVATION_CHANGED"):
                P.validate_observation({**observed, key: value}, self.request_raw, self.admitted_raw,
                    self.canonical_raw, self.start_raw, self.receipt_raw, original_exit_code=0)

    def test_wall_labels_and_empty_reports_never_supply_budget_or_product_acceptance(self):
        changed = {**self.receipt, "endedUtc": "2026-09-16T00:00:00+00:00", "reports": []}
        observed = self.observe(receipt_raw=A.json_bytes(changed))
        self.assertEqual(observed["budgetAcceptance"], "NOT_ADMITTED_HERE")
        self.assertEqual(observed["testAcceptance"], "NOT_PERFORMED")

    def test_malformed_duplicate_and_oversized_inputs_fail_without_echoing_originals(self):
        for raw in (b"", b"[]", b"{", b'{"private-marker":1,"private-marker":2}',
                    b'{"durationSeconds":NaN}', b"x" * (P.LIMIT + 1)):
            with self.subTest(length=len(raw)), self.assertRaisesRegex(P.ProducerError, "^BOOTSTRAP_PRODUCER_RECORD$"):
                self.observe(receipt_raw=raw)
        for value in (True, "4", -1, None, 10 ** 400):
            with self.subTest(value_type=type(value)), self.assertRaises(P.ProducerError):
                self.observe(receipt_raw=A.json_bytes({**self.receipt, "durationSeconds": value}))


if __name__ == "__main__":
    unittest.main()
