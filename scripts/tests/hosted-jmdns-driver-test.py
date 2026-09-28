#!/usr/bin/env python3
"""Offline driver DATA/source/flow models; no Java or native execution evidence."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/hosted_jmdns_driver.py"
spec = importlib.util.spec_from_file_location("jmdns_driver_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
SCOPE = "MANUAL_JMDNS_NATIVE_DIAGNOSTIC_ONLY_V1"
SELECTOR = [":p2p-transport-lan:jvmTest", "--tests",
            "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally",
            "--no-configure-on-demand"]


def offline(event, _args):
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                                               "ctypes.dlopen", "os.putenv", "os.unsetenv"):
        raise AssertionError("offline driver controls attempted native execution: " + event)


sys.addaudithook(offline)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


class DriverControls(unittest.TestCase):
    def request(self):
        return {"schema": 1, "scope": SCOPE, "request": {"operation": "diagnose-jmdns"}, "github": {},
                "startedMonotonicNs": 100 * M.NS, "deadlineMonotonicNs": 1300 * M.NS,
                "observationBudgetNs": 120 * M.NS}

    def target(self):
        return {"schema": 1, "scope": SCOPE, "requestSha256": "c" * 64, "invocationId": "a" * 32,
                "jobId": "b" * 32, "beforeJava": {}, "requestedGradleArgv": SELECTOR,
                "executedGradleArgv": ["/controlled/candidate/gradlew", *SELECTOR], "testExitCode": 1,
                "beforeObservationElapsedNs": 5 * M.NS, "startedTestMonotonicNs": 105 * M.NS,
                "endTestMonotonicNs": 705 * M.NS}

    def test_closed_request_and_unchanged_fixed_limits(self):
        request = self.request()
        self.assertIs(M.request_data(request, SCOPE), request)
        self.assertEqual((M.PRODUCT_NS, M.OBSERVATION_NS, M.RESERVED_CLOSE_NS),
                         (1200 * M.NS, 120 * M.NS, 300 * M.NS))
        for key, value in (("schema", True), ("scope", "GENERATION"), ("startedMonotonicNs", True),
                           ("deadlineMonotonicNs", 1400 * M.NS), ("observationBudgetNs", 121 * M.NS),
                           ("request", {"operation": "generate"}), ("timeout", 2400)):
            with self.subTest(key=key), self.assertRaises(M.DriverError):
                M.request_data({**request, key: value}, SCOPE)

    def test_target_hash_scope_result_and_clock_fields_are_bound(self):
        value, request = self.target(), self.request()
        self.assertIs(M.target_data(value, request, "c" * 64, SCOPE), value)
        for key, replacement in (("requestSha256", "d" * 64), ("schema", True), ("scope", "GENERATION"),
                                 ("invocationId", "0"), ("jobId", True), ("testExitCode", 125),
                                 ("beforeObservationElapsedNs", 0), ("startedTestMonotonicNs", True),
                                 ("endTestMonotonicNs", 104 * M.NS), ("endTestMonotonicNs", 1300 * M.NS)):
            with self.subTest(key=key), self.assertRaises(M.DriverError):
                M.target_data({**value, key: replacement}, request, "c" * 64, SCOPE)

    def test_observation_clock_excludes_only_actual_test_not_normal_close(self):
        request, target = self.request(), self.target()
        self.assertEqual(M.observation_deadline(request), 220 * M.NS)
        self.assertEqual(M.observation_deadline(request, target), 820 * M.NS)
        # A target canonical return at710s has consumed10s of observation time:
        # 5s before-test plus5s normal return/stop overhead, not600s of test time.
        self.assertEqual(M.observation_deadline(request, target) - 710 * M.NS, 110 * M.NS)
        changed = {**target, "endTestMonotonicNs": 715 * M.NS}
        self.assertEqual(M.observation_deadline(request, changed), 830 * M.NS)
        self.assertEqual(request["deadlineMonotonicNs"], 1300 * M.NS)

    def test_action_needs_entire_fixed_allowance_and_never_refills_it(self):
        self.assertTrue(M.can_start(100 * M.NS, 115 * M.NS, 15))
        self.assertFalse(M.can_start(100 * M.NS + 1, 115 * M.NS, 15))
        self.assertFalse(M.can_start(115 * M.NS, 115 * M.NS, 15))
        for args in ((True, 100, 1), (0, 100, 0), (0, 100, 1.0), (0, float("inf"), 1)):
            with self.subTest(args=args), self.assertRaises(M.DriverError):
                M.can_start(*args)

    def test_only_real_ordinary_return_codes_are_eligible(self):
        for code in (0, 1, 7, 123):
            self.assertEqual(M.ordinary_exit(code), code)
        for code in (True, False, None, "1", 1.0, -15, 124, 125, 130, 255):
            with self.subTest(code=code), self.assertRaises(M.DriverError):
                M.ordinary_exit(code)

    def target_driver(self):
        controller = SimpleNamespace(DIAGNOSTIC_SCOPE=SCOPE)
        driver = SimpleNamespace(c=controller, candidate=Path("/controlled/candidate"),
            data=SimpleNamespace(GRADLE_ARGUMENTS=tuple(SELECTOR)),
            runner=SimpleNamespace(gradle_arguments=Mock(side_effect=lambda argv: [*argv, "--source-owned-policy"])),
            env={"P2PKIT_AUDIT_OWNERSHIP_CHAIN": "a" * 32}, product_deadline=1000 * M.NS,
            request=self.request(), request_hash="c" * 64, invocation="a" * 32,
            context={"id": "b" * 32}, record=Mock(),
            java_metadata=Mock(return_value={"signature": {"status": "RETURNED", "exitCode": 1}}))
        return controller, driver

    def test_target_preserves_test_exit_even_when_before_code_display_failed(self):
        for code in (0, 7, 123):
            controller, driver = self.target_driver()
            child = Mock()
            child.wait.return_value = code
            with self.subTest(code=code), patch.object(M, "Driver", return_value=driver), \
                    patch.object(M.subprocess, "Popen", return_value=child) as launch, \
                    patch.object(M.time, "monotonic_ns", side_effect=[105 * M.NS, 105 * M.NS, 111 * M.NS]):
                self.assertEqual(M.target(controller), code)
            driver.runner.gradle_arguments.assert_called_once_with(SELECTOR)
            argv, = launch.call_args.args
            self.assertEqual(argv, ["/controlled/candidate/gradlew", *SELECTOR, "--source-owned-policy"])
            self.assertEqual(launch.call_args.kwargs, {"cwd": driver.candidate, "env": driver.env,
                                                     "stdin": subprocess.DEVNULL, "close_fds": True})
            name, record = driver.record.call_args.args
            self.assertEqual(name, "jmdns-target.json")
            self.assertEqual(record["testExitCode"], code)
            self.assertEqual(record["beforeObservationElapsedNs"], 5 * M.NS)

    def test_target_reserved_or_timeout_does_not_write_accepted_record(self):
        for failure in (124, 125, -15, subprocess.TimeoutExpired("fixed", 1)):
            controller, driver = self.target_driver()
            child = Mock()
            if isinstance(failure, Exception):
                child.wait.side_effect = failure
            else:
                child.wait.return_value = failure
            with self.subTest(failure=type(failure).__name__), patch.object(M, "Driver", return_value=driver), \
                    patch.object(M.subprocess, "Popen", return_value=child), \
                    patch.object(M.time, "monotonic_ns", return_value=105 * M.NS), \
                    self.assertRaises((M.DriverError, subprocess.TimeoutExpired)):
                M.target(controller)
            driver.record.assert_not_called()

    def observation_driver(self, *, stream_error=False):
        driver = M.Driver.__new__(M.Driver)
        driver.root = Path("/controlled/controller")
        driver.records = Path("/controlled/maintenance")
        driver.directory = driver.records / "jmdns-observer"
        driver.env = {"P2PKIT_AUDIT_OWNERSHIP_CHAIN": "a" * 32}
        driver.observation_window = Mock(return_value=(100 * M.NS, 115 * M.NS))
        streams = []

        def tee(source, destination, live, errors, start):
            self.assertIsNone(live)
            self.assertIs(start, False)
            stream = SimpleNamespace(source=source, start=Mock(), finish=Mock())
            if stream_error:
                stream.finish.side_effect = lambda: errors.append("MODEL_UNKNOWN_STREAM_CLOSE")
            streams.append(stream)
            return stream

        driver.runner = SimpleNamespace(Tee=Mock(side_effect=tee), MAX_STREAM_BYTES=64 * 1024 * 1024)
        driver.c = SimpleNamespace(read_file=Mock(side_effect=lambda path, limit:
            (b"retained original", {"size": 17, "sha256": digest(b"retained original")})))
        driver.data = SimpleNamespace(HASH_SECONDS=5)
        return driver, streams

    def test_observation_retains_nonzero_and_original_bounded_private_streams(self):
        driver, streams = self.observation_driver()
        child = Mock()
        child.wait.return_value = 7
        argv = ["/usr/bin/codesign", "-d", "--verbose=4", "/installed/bin/java"]
        with patch.object(M.subprocess, "Popen", return_value=child) as launch, \
                patch.object(M.time, "monotonic_ns", return_value=100 * M.NS):
            result, stdout, stderr = driver.observe_command("signature", argv, 15, 65536)
        self.assertEqual((result["status"], result["exitCode"], result["interpretation"]),
                         ("RETURNED", 7, "INCONCLUSIVE"))
        self.assertEqual(stdout, stderr)
        self.assertEqual(launch.call_args.args, (argv,))
        self.assertIs(launch.call_args.kwargs["env"], driver.env)
        self.assertNotIn("shell", launch.call_args.kwargs)
        self.assertNotIn("start_new_session", launch.call_args.kwargs)
        self.assertEqual(len(streams), 2)
        for stream in streams:
            stream.start.assert_called_once()
            stream.finish.assert_called_once()
        self.assertTrue(all(call.args[1] == 64 * 1024 * 1024 for call in driver.c.read_file.call_args_list))

    def test_observation_budget_refusal_launches_nothing(self):
        driver, _ = self.observation_driver()
        driver.observation_window.return_value = None
        with patch.object(M.subprocess, "Popen") as launch:
            result, stdout, stderr = driver.observe_command("native-log", ["/usr/bin/log"], 45, 1048576)
            checksum = driver.hash_java(Path("/not-read/bin/java"))
        self.assertEqual(result["reason"], "OBSERVATION_BUDGET_NOT_ADMITTED")
        self.assertEqual(checksum["reason"], "OBSERVATION_BUDGET_NOT_ADMITTED")
        self.assertIsNone(stdout)
        self.assertIsNone(stderr)
        launch.assert_not_called()
        driver.c.read_file.assert_not_called()

    def test_stream_uncertainty_cannot_become_returned_observation(self):
        driver, streams = self.observation_driver(stream_error=True)
        child = Mock()
        child.wait.return_value = 0
        with patch.object(M.subprocess, "Popen", return_value=child), \
                patch.object(M.time, "monotonic_ns", return_value=100 * M.NS), self.assertRaises(M.DriverError):
            driver.observe_command("signature", ["/usr/bin/codesign"], 15, 65536)
        self.assertEqual(len(streams), 2)
        for stream in streams:
            stream.finish.assert_called_once()
        driver.c.read_file.assert_not_called()

    def retained_driver(self, *, report_count=1, byte_count=None):
        raw = b"synthetic original fixture trace\n"
        source = "library/p2p-transport-lan/build/reports/jmdns-close/run-123/control-456.log"
        row = {"source": source, "retained": "reports/" + source, "sha256": digest(raw),
               "bytes": len(raw) if byte_count is None else byte_count, "classification": "changed-since-admission"}
        manifest = encoded({"schema": 1, "records": [row] * report_count, "limitation": "MODEL"})
        baseline = encoded({})
        request = {"operation": "diagnose-jmdns", "candidate_sha": "a" * 40, "candidate_tree": "b" * 40}
        source_binding = {"commit": request["candidate_sha"], "tree": request["candidate_tree"],
                          "status": "", "diffSha256": digest(b"")}
        receipt = {"id": "d" * 32, "productExitCode": 1}
        returned = {"targetReceiptSha256": "e" * 64}
        binding = {"schema": 1, "scope": "MANUAL_JMDNS_REPORT_CUSTODY_V1", "request": request,
            "invocationId": receipt["id"], "purpose": M.PURPOSES["target"], "productExitCode": 1,
            "receiptSha256": returned["targetReceiptSha256"], "beforeManifestSha256": digest(baseline),
            "afterManifestSha256": digest(manifest), "candidateBefore": source_binding, "candidateAfter": source_binding}
        records = Path("/controlled/maintenance")
        files = {records / "candidate-reports/binding.json": encoded(binding),
            records / "candidate-reports/report-manifest.json": manifest,
            records / "candidate-report-baseline.json": baseline,
            records / "candidate-reports" / row["retained"]: raw}
        c = SimpleNamespace(parsed=json.loads, digest=digest, FILE_COUNT=20000,
                            read_file=Mock(side_effect=lambda path, *_args: (files[path], {})))
        driver = SimpleNamespace(c=c, records=records, request={"request": request},
            data=SimpleNamespace(FIXTURE_LIMIT=65536, parse_fixture_trace=Mock(return_value={"status": "CAPTURED"})))
        return driver, returned, receipt, files

    def test_only_one_original_retained_control_copy_is_parsed(self):
        driver, returned, receipt, files = self.retained_driver()
        self.assertEqual(M.retained_control(driver, returned, receipt)["status"], "CAPTURED")
        driver.data.parse_fixture_trace.assert_called_once_with(b"synthetic original fixture trace\n")
        self.assertTrue(all(call.args[0].is_relative_to(driver.records) for call in driver.c.read_file.call_args_list))
        for count in (0, 2):
            driver, returned, receipt, _ = self.retained_driver(report_count=count)
            self.assertEqual(M.retained_control(driver, returned, receipt)["status"], "INCONCLUSIVE")
            driver.data.parse_fixture_trace.assert_not_called()

    def test_oversized_control_is_inconclusive_not_truncated_for_parsing(self):
        driver, returned, receipt, _ = self.retained_driver(byte_count=65537)
        self.assertEqual(M.retained_control(driver, returned, receipt)["reason"], "ORIGINAL_CONTROL_REPORT_OVERSIZED")
        driver.data.parse_fixture_trace.assert_not_called()

    def test_generator_report_scope_cannot_authorize_diagnostic_query(self):
        driver, returned, receipt, files = self.retained_driver()
        path = driver.records / "candidate-reports/binding.json"
        binding = json.loads(files[path])
        binding["scope"] = "MANUAL_DEPENDENCY_CANDIDATE_REPORT_CUSTODY_V1"
        files[path] = encoded(binding)
        with self.assertRaises(M.DriverError):
            M.retained_control(driver, returned, receipt)
        driver.data.parse_fixture_trace.assert_not_called()

    def test_changed_report_receipt_or_manifest_cannot_authorize_query(self):
        driver, returned, receipt, files = self.retained_driver()
        changed = {**returned, "targetReceiptSha256": "f" * 64}
        with self.assertRaises(M.DriverError):
            M.retained_control(driver, changed, receipt)
        manifest = driver.records / "candidate-reports/report-manifest.json"
        files[manifest] += b" "
        with self.assertRaises(M.DriverError):
            M.retained_control(driver, returned, receipt)
        driver.data.parse_fixture_trace.assert_not_called()

    def test_source_has_only_fixed_children_and_original_parent_boundary(self):
        raw = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(raw)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        spawns = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"]
        self.assertEqual(len(spawns), 2)
        forbidden = {"make_scope", "spawn", "execute", "initialize", "kill", "terminate", "system", "execve", "setsid"}
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr in forbidden for node in calls))
        self.assertIn('start.get("kind") == "command"', raw)
        self.assertIn('start.get("controllerPid") == os.getppid()', raw)
        self.assertIn('dict(os.environ) == expected_env', raw)
        self.assertIn('driver.runner.gradle_arguments(original)', raw)
        self.assertNotIn('"--write-locks"', raw)
        self.assertNotIn('"--write-verification-metadata"', raw)
        functions = {node.name: ast.get_source_segment(raw, node) for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertLess(functions["observe"].index("original_target(driver)"),
                        functions["observe"].index("driver.java_metadata()"))
        self.assertLess(functions["observe"].index("bind_native_process("), functions["observe"].index("log_argv("))
        self.assertNotIn("log_argv", functions["target"])
        self.assertIn("c.command_return_data(", functions["original_target"])


if __name__ == "__main__":
    unittest.main()
