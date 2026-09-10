#!/usr/bin/env python3
"""Policy mutations and fake-Gradle lifecycle tests; these do not execute Kotlin tests."""

import contextlib
import copy
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("platform_gate", ROOT / "scripts/run-platform-tests.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
POLICY = GATE.read_json(ROOT / "gradle/platform-test-policy.json")
TOKEN = "a" * 32


def example_report(profile="full", arch="arm64"):
    required = GATE.required_tasks(POLICY, profile, arch)
    tasks = {name for entry in POLICY["model"].values() for name in entry["tests"]}
    unavailable = "iosX64Test" if arch == "arm64" else "iosSimulatorArm64Test"
    return {
        "schema": 1, "token": TOKEN, "buildFailed": False, "dryRun": False,
        "host": {"os": "Mac OS X", "arch": "aarch64" if arch == "arm64" else "x86_64"},
        "model": copy.deepcopy(POLICY["model"]),
        "tests": {name: {
            "outcome": "EXECUTED" if name in required else "SKIPPED" if profile == "full" else "NOT_REQUESTED",
            "enabled": not name.endswith(":" + unavailable), "inGraph": profile == "full" or name in required,
            "passed": 1 if name in required else 0, "failed": 0, "skipped": 0,
        } for name in tasks},
    }


class CoveragePolicyTest(unittest.TestCase):
    def assess(self, report, profile="full", arch="arm64"):
        return GATE.assess(report, POLICY, profile, arch, TOKEN)

    def test_current_executed_set_is_not_empty_or_sample_only(self):
        arm = self.assess(example_report())
        intel = self.assess(example_report(arch="x64"), arch="x64")
        x64_only = self.assess(example_report("ios-x64", "x64"), "ios-x64", "x64")
        self.assertEqual(14, len(arm))
        self.assertEqual(14, len(intel))
        self.assertEqual({":p2p-core:iosX64Test", ":p2p-transport-lan:iosX64Test"}, x64_only)
        native_arm = [":p2p-core:iosSimulatorArm64Test", ":p2p-transport-lan:iosSimulatorArm64Test"]
        self.assertEqual(native_arm, GATE.PROFILES["ios-arm64"])
        arm_only = example_report("ios-arm64", "arm64")
        self.assertEqual(set(native_arm), self.assess(arm_only, "ios-arm64", "arm64"))
        with self.assertRaises(ValueError):
            self.assess(arm_only, "full", "arm64")
        self.assertIn(":sample-kmp-shared:testAndroidHostTest", arm)
        self.assertIn(":p2p-core:testAndroidHostTest", arm)
        self.assertIn(":p2p-core:iosSimulatorArm64Test", arm)
        self.assertNotIn(":p2p-core:iosX64Test", arm)
        self.assertNotIn(":p2p-core:iosSimulatorArm64Test", intel)

    def test_every_expected_task_must_execute_fresh_successful_cases(self):
        for profile, arch in (("full", "arm64"), ("full", "x64"), ("ios-x64", "x64"), ("ios-arm64", "arm64")):
            baseline = example_report(profile, arch)
            for name in GATE.required_tasks(POLICY, profile, arch):
                changes = [("outcome", outcome) for outcome in (
                    "SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NO_SOURCE", "NOT_COMPLETED", "NOT_REQUESTED", "FAILED")]
                changes += [("enabled", False), ("inGraph", False), ("passed", 0), ("failed", 1)]
                for key, value in changes:
                    with self.subTest(profile=profile, arch=arch, task=name, field=key, value=value):
                        report = copy.deepcopy(baseline)
                        report["tests"][name][key] = value
                        with self.assertRaises(ValueError):
                            self.assess(report, profile, arch)
                report = copy.deepcopy(baseline)
                del report["tests"][name]
                with self.assertRaises(ValueError):
                    self.assess(report, profile, arch)

    def test_every_target_and_task_is_guarded_against_model_drift(self):
        for project, entry in POLICY["model"].items():
            for target in entry["targets"]:
                report = example_report()
                del report["model"][project]["targets"][target]
                with self.subTest(project=project, missing_target=target), self.assertRaises(ValueError):
                    self.assess(report)
            for task in entry["tests"]:
                report = example_report()
                report["model"][project]["tests"].remove(task)
                del report["tests"][task]
                with self.subTest(missing_task=task), self.assertRaises(ValueError):
                    self.assess(report)
        report = example_report()
        report["model"][":p2p-core"]["targets"]["newNative"] = "native"
        with self.assertRaises(ValueError):
            self.assess(report)

    def test_stale_failed_dry_run_wrong_host_and_malformed_reports_fail(self):
        for key, value in (
            ("schema", 2), ("schema", True), ("token", "b" * 32), ("dryRun", True), ("buildFailed", True),
            ("host", []), ("host", {"os": "Linux", "arch": "aarch64"}),
            ("host", {"os": "Mac OS X", "arch": "amd64"}), ("host", {"os": "Mac OS X", "arch": 1}),
            ("tests", []), ("tests", {}), ("model", None),
        ):
            report = example_report()
            report[key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.assess(report)
        for report in (None, [], 1, "invalid"):
            with self.assertRaises(ValueError):
                self.assess(report)

    def test_malformed_task_states_and_counts_fail(self):
        name = ":p2p-core:jvmTest"
        for key, value in (
            ("enabled", 1), ("inGraph", "true"), ("outcome", "INVENTED"),
            ("passed", -1), ("passed", True), ("passed", "1"), ("passed", 1.5),
            ("failed", None), ("skipped", -1),
        ):
            report = example_report()
            report["tests"][name][key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.assess(report)
        report = example_report()
        report["tests"][name] = None
        with self.assertRaises(ValueError):
            self.assess(report)

    def test_skip_counts_and_all_nonexecution_limits_are_visible(self):
        report = example_report()
        report["tests"][":p2p-transport-lan:iosSimulatorArm64Test"]["skipped"] = 1
        self.assess(report)
        rows = {row["target"]: row for row in GATE.target_rows(report)}
        self.assertEqual(1, rows[":p2p-transport-lan/iosSimulatorArm64"]["skipped"])
        self.assertEqual("SKIPPED", rows[":p2p-core/iosX64"]["status"])
        self.assertIn("architecture disabled", rows[":p2p-core/iosX64"]["reason"])
        self.assertEqual("NOT_CONFIGURED", rows[":p2p-core/iosArm64"]["status"])
        self.assertEqual("COMPILATION_ONLY", rows[":p2p-core/metadata"]["status"])
        self.assertIn("no ART/instrumented", rows[":p2p-core/android"]["reason"])
        self.assertIn("commonTest is excluded", rows[":p2p-core/android"]["reason"])
        self.assertEqual("OUTSIDE_THIS_INVOCATION", rows[":iosApp/Swift"]["status"])
        # An unclassified future target must not disappear from failure evidence.
        report["model"][":p2p-core"]["targets"]["newTarget"] = "native"
        self.assertIn("NO_TEST_TASK", [row["status"] for row in GATE.target_rows(report)])

    def test_bounded_json_reader_rejects_duplicates_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-coverage-json-") as temp:
            path = Path(temp) / "input.json"
            for content in (b"", b"{}" * (512 * 1024 + 1), b'{"schema":1,"schema":1}', b'{"v":NaN}', b"\xff"):
                path.write_bytes(content)
                with self.subTest(size=len(content)), self.assertRaises(ValueError):
                    GATE.read_json(path)
            path.write_text('{"schema":1}')
            self.assertEqual({"schema": 1}, GATE.read_json(path))

    def test_malformed_policy_and_wrong_profile_fail_before_build(self):
        for policy in (None, [], {"schema": True}, {"schema": 1, "model": {}},
                       {"schema": 1, "model": {":bad": {"targets": {}, "tests": [False]}}}):
            with self.assertRaises(ValueError):
                GATE.required_tasks(policy, "full", "arm64")
        for profile, arch in (("ios-x64", "arm64"), ("ios-arm64", "x64"), ("ios-arm64", "unknown"),
                              ("full", "unknown"), ("other", "x64")):
            with self.assertRaises(ValueError):
                GATE.required_tasks(POLICY, profile, arch)


FAKE_GRADLE = r'''
import json, os, pathlib, signal, subprocess, sys, time
root = pathlib.Path.cwd()
with (root / "trace.jsonl").open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\n")
mode = os.environ.get("P2PKIT_FAKE_PLATFORM_MODE", "pass")
if sys.argv[1:] == ["--stop"]:
    sys.exit(7 if mode == "stop-failure" else 0)
if mode == "wait":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"])
    def terminated(signum, frame):
        child.wait(timeout=10)
        sys.exit(143)
    signal.signal(signal.SIGTERM, terminated)
    (root / "worker.pid").write_text(str(child.pid))
    time.sleep(90)
    sys.exit(8)
token = next(arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("-Pp2pkit.testCoverageToken="))
if mode == "no-report":
    sys.exit(0)
report = json.loads((root / "fixture.json").read_text())
report["token"] = "0" * 32 if mode == "stale-token" else token
if mode == "build-failure":
    report["buildFailed"] = True
if mode == "source-change":
    (root / "tracked.txt").write_text("changed during execution\n")
path = root / "build/reports/platform-tests" / token / "execution.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("[]" if mode == "malformed" else json.dumps(report))
sys.exit(9 if mode in ("exit-failure", "build-failure") else 0)
'''


class DriverLifecycleTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-platform-driver-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "gradle").mkdir()
        shutil.copy2(ROOT / "gradle/platform-test-policy.json", self.root / "gradle/platform-test-policy.json")
        (self.root / "gradlew").write_text("#!" + sys.executable + "\n" + FAKE_GRADLE)
        (self.root / "gradlew").chmod(0o755)
        (self.root / "fixture.json").write_text(json.dumps(example_report()))
        (self.root / "tracked.txt").write_text("unchanged\n")
        (self.root / ".gitignore").write_text("build/\ntrace.jsonl\nworker.pid\n")
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid",
                      "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic input")):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(GATE, "ROOT", self.root).start()
        mock.patch.object(GATE, "POLICY", self.root / "gradle/platform-test-policy.json").start()
        mock.patch.object(GATE.platform, "system", return_value="Darwin").start()
        mock.patch.object(GATE.platform, "machine", return_value="arm64").start()

    def invoke(self, mode):
        with mock.patch.dict(os.environ, {"P2PKIT_FAKE_PLATFORM_MODE": mode}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return GATE.run("full")

    def summaries(self):
        return [json.loads(path.read_text()) for path in self.root.glob("build/reports/platform-tests/*/summary.json")]

    def calls(self):
        return [json.loads(line) for line in (self.root / "trace.jsonl").read_text().splitlines()]

    def test_success_uses_strict_fresh_bounded_command_and_stops(self):
        self.assertEqual(0, self.invoke("pass"))
        calls = self.calls()
        self.assertEqual(2, len(calls))
        self.assertEqual(["--stop"], calls[-1])
        self.assertEqual(["check", "--no-daemon", "--no-build-cache", "--no-configuration-cache", "--rerun-tasks",
                          "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain"],
                         calls[0][:10])
        self.assertIn("--init-script", calls[0])
        summary = self.summaries()[0]
        self.assertEqual("PASS", summary["result"])
        self.assertEqual([], summary["errors"])
        self.assertEqual(summary["commit"], summary["sourceAfter"]["commit"])
        self.assertEqual(summary["diffSha256"], summary["sourceAfter"]["diffSha256"])

    def test_failure_modes_cannot_pass_and_always_stop(self):
        for mode in ("no-report", "stale-token", "malformed", "exit-failure", "build-failure", "stop-failure"):
            with self.subTest(mode=mode):
                self.assertNotEqual(0, self.invoke(mode))
                self.assertEqual(["--stop"], self.calls()[-1])
        self.assertEqual(6, len(self.summaries()))
        self.assertTrue(all(report["result"] == "FAIL" and report["errors"] for report in self.summaries()))

    def test_previous_success_report_cannot_mask_missing_current_execution(self):
        self.assertEqual(0, self.invoke("pass"))
        self.assertNotEqual(0, self.invoke("no-report"))
        summaries = self.summaries()
        self.assertEqual({"PASS", "FAIL"}, {report["result"] for report in summaries})
        self.assertEqual(2, len({report["token"] for report in summaries}))

    def test_source_mutation_fails_despite_successful_tests(self):
        self.assertNotEqual(0, self.invoke("source-change"))
        self.assertIn("Source state changed", " ".join(self.summaries()[0]["errors"]))
        self.assertEqual(["--stop"], self.calls()[-1])

    def test_untracked_input_is_rejected_before_starting_gradle(self):
        (self.root / "untracked.kt").write_text("// not evidence-bound\n")
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.invoke("pass")
        self.assertFalse((self.root / "trace.jsonl").exists())

    def test_missing_wrapper_still_records_failure_and_cleanup_attempt(self):
        (self.root / "gradlew").unlink()
        self.assertNotEqual(0, self.invoke("pass"))
        summary = self.summaries()[0]
        self.assertEqual("FAIL", summary["result"])
        self.assertNotEqual(0, summary["stopExitCode"])

    def test_undrained_owned_group_fails_gate_but_still_attempts_gradle_stop(self):
        with mock.patch.object(GATE, "terminate_process", return_value=False):
            self.assertNotEqual(0, self.invoke("pass"))
        self.assertEqual("FAIL", self.summaries()[0]["result"])
        self.assertEqual(["--stop"], self.calls()[-1])

    def test_stop_timeout_is_failure_and_terminates_its_owned_process(self):
        process = mock.Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("gradlew --stop", 90), 0]
        with mock.patch.object(GATE.subprocess, "Popen", return_value=process), \
                mock.patch.object(GATE.os, "killpg", side_effect=[None, ProcessLookupError]) as kill, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(124, GATE.stop_gradle())
        self.assertEqual([mock.call(123, signal.SIGTERM), mock.call(123, 0)], kill.call_args_list)

    def test_cancellation_signals_owned_gradle_group_stops_and_reports_failure(self):
        # A separate Python driver plus a real fake-wrapper/worker process tests
        # signal propagation. No Gradle, Kotlin, simulator or device is launched.
        bootstrap = (
            "import importlib.util, pathlib, sys; sys.dont_write_bytecode=True; "
            f"s=importlib.util.spec_from_file_location('gate', {str(ROOT / 'scripts/run-platform-tests.py')!r}); "
            "g=importlib.util.module_from_spec(s); s.loader.exec_module(g); "
            f"g.ROOT=pathlib.Path({str(self.root)!r}); g.POLICY=g.ROOT/'gradle/platform-test-policy.json'; "
            "g.platform.system=lambda:'Darwin'; g.platform.machine=lambda:'arm64'; sys.exit(g.run('full'))"
        )
        process = subprocess.Popen([sys.executable, "-c", bootstrap], cwd=self.root,
                                   env={**os.environ, "P2PKIT_FAKE_PLATFORM_MODE": "wait"},
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        worker = None
        try:
            deadline = time.monotonic() + 10
            while not (self.root / "worker.pid").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue((self.root / "worker.pid").exists(), "Fake build never reached worker start")
            worker = int((self.root / "worker.pid").read_text())
            process.send_signal(signal.SIGTERM)
            output = process.communicate(timeout=20)[0].decode()
            self.assertEqual(130, process.returncode, output)
            self.assertEqual(["--stop"], self.calls()[-1])
            self.assertEqual("FAIL", self.summaries()[0]["result"])
            with self.assertRaises(ProcessLookupError):
                os.kill(worker, 0)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
            if worker is not None:
                try:
                    os.kill(worker, signal.SIGKILL)
                except ProcessLookupError:
                    pass


@contextlib.contextmanager
def darwin_group_diagnostic(leader_exits_first):
    """Adjacent raw worker observations for #157; never a new cleanup authority."""
    if sys.platform != "darwin":
        yield None
        return

    def emit(record):
        try:
            print("P2PKIT_DARWIN_GROUP " + json.dumps({"leaderExitsFirst": leader_exits_first, **record}),
                  file=sys.stderr, flush=True)
        except Exception:
            pass  # Diagnostic output cannot replace a syscall result or prevent fixture cleanup.

    try:
        spec = importlib.util.spec_from_file_location("group_diagnostic_processes", ROOT / "scripts/audit_processes.py")
        processes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(processes)
        domains = processes.ownership_domains(os.environ.get(processes.CHAIN_ENV, ""),
                                              os.environ.get(processes.DOMAINS_ENV, ""))
        if not domains:
            raise processes.OwnershipError("Diagnostic has no current audit ownership domain")
        domain = domains[-1]
        if (os.environ.get(processes.JOB_ENV), os.environ.get(processes.STATE_ENV),
                os.environ.get("GRADLE_USER_HOME")) != (domain["job"], domain["state"], domain["home"]):
            raise processes.OwnershipError("Diagnostic ownership domain is not current")
        observer = processes.DarwinScope(domain["job"], domain["id"], domain["state"], domain["home"])
    except Exception as error:
        emit({"event": "unavailable", "errorType": type(error).__name__})
        yield None
        return

    group = worker = initial_key = None

    def snapshot():
        try:
            at = time.monotonic_ns()
            current = observer._identity(worker, required=True)
            state = ("ABSENT" if current is None else "UNBOUND" if initial_key is None else
                     "SAME_LIFETIME" if observer._key(current) == initial_key else "REPLACED")
            return {"monotonicNs": at, "state": state, "identity": current}
        except Exception as error:
            # Raw required reads retain zombie/replacement state and do not reconcile/retry.
            return {"state": "UNKNOWN", "errorType": type(error).__name__, "error": str(error)}

    def bind_worker(group_pid, worker_pid):
        nonlocal group, worker, initial_key
        group, worker = group_pid, worker_pid
        try:
            observed = snapshot()
            current = observed.get("identity")
            if current is not None:
                initial_key = observer._key(current)
                observed["state"] = "INITIAL"
            matches = (current is not None and current["live"] and current["group"] == group and
                       current["uid"] == os.geteuid() and current["realUid"] == os.getuid())
            emit({"event": "worker-ready", "group": group, "worker": worker, "initialKey": initial_key,
                  "readyMatchesFixture": matches, "snapshotsAreNonAtomic": True, "observation": observed})
        except Exception as error:
            emit({"event": "bind-failed", "errorType": type(error).__name__})

    bind_worker.phase = "drain"
    killpg, kill = os.killpg, os.kill

    def traced_call(name, original, pid, signum):
        if group is None or not ((name == "killpg" and pid == group) or
                                 (name == "kill" and pid == worker and signum == 0)):
            return original(pid, signum)
        before = snapshot()
        failure = None
        result = None
        started = None
        try:
            started = time.monotonic_ns()
        except Exception:
            pass  # An unavailable diagnostic clock must not prevent the original syscall.
        try:
            result = original(pid, signum)
            return result
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                finished = time.monotonic_ns()
                # Only existing TERM/KILL, failed group calls and the worker's zero probe.
                # Successful drain polls emit nothing; no extra probes, sleeps or retries.
                if failure is not None or signum != 0 or name == "kill":
                    emit({"event": "call", "phase": bind_worker.phase,
                          "operation": name, "pid": pid, "signal": int(signum),
                          "syscallStartedMonotonicNs": started, "syscallFinishedMonotonicNs": finished,
                          "returned": failure is None, "result": result,
                          "errorType": None if failure is None else type(failure).__name__,
                          "errno": 0 if failure is None else getattr(failure, "errno", None),
                          "before": before, "after": snapshot()})
            except Exception as error:
                emit({"event": "capture-failed", "errorType": type(error).__name__})

    try:
        with mock.patch.object(os, "killpg", lambda pid, sig: traced_call("killpg", killpg, pid, sig)), \
                mock.patch.object(os, "kill", lambda pid, sig: traced_call("kill", kill, pid, sig)):
            yield bind_worker
    finally:
        try:
            observer.close()
        except Exception as error:
            emit({"event": "close-failed", "errorType": type(error).__name__})


class OwnedProcessGroupTest(unittest.TestCase):
    def test_fixture_attempts_remaining_retirements_after_cleanup_failure(self):
        # Exercise the actual fixture finalizer, without creating any processes.
        for failing_operation in ("group", "leader"):
            with self.subTest(failing_operation=failing_operation):
                failure = (PermissionError(1, "injected group EPERM") if failing_operation == "group"
                           else subprocess.TimeoutExpired("fixture leader", 10))
                leader = mock.Mock(pid=123)
                unrelated = mock.Mock(pid=124)
                unrelated.poll.return_value = None
                if failing_operation == "leader":
                    leader.wait.side_effect = failure

                def signal_group(pid, signum):
                    if signum == 0:
                        raise ProcessLookupError(pid)
                    if failing_operation == "group":
                        raise failure

                group_kill = mock.Mock(side_effect=signal_group)
                retirements = mock.Mock()
                for name, operation in (("group_kill", group_kill), ("leader_wait", leader.wait),
                                        ("unrelated_terminate", unrelated.terminate),
                                        ("unrelated_wait", unrelated.wait)):
                    retirements.attach_mock(operation, name)
                with mock.patch.object(tempfile, "TemporaryDirectory") as directory, \
                        mock.patch.object(Path, "exists", return_value=True), \
                        mock.patch.object(Path, "read_text", return_value="125"), \
                        mock.patch.object(subprocess, "Popen", side_effect=[leader, unrelated]), \
                        mock.patch.object(GATE, "terminate_process", return_value=True), \
                        mock.patch.object(os, "kill", side_effect=ProcessLookupError), \
                        mock.patch.object(os, "killpg", group_kill):
                    directory.return_value.__enter__.return_value = "/synthetic-owned-group"
                    with self.assertRaises(type(failure)) as raised:
                        self.resistant_worker_control(leader_exits_first=False)
                self.assertIs(failure, raised.exception, "cleanup must not swallow the original failure")
                self.assertEqual([
                    mock.call.group_kill(123, 0),
                    mock.call.group_kill(123, signal.SIGKILL),
                    mock.call.leader_wait(timeout=10),
                    mock.call.unrelated_terminate(),
                    mock.call.unrelated_wait(timeout=10),
                ], retirements.mock_calls)

    def test_unterminated_group_fails_after_both_bounded_deadlines(self):
        for probe_denied in (False, True):
            with self.subTest(probe_denied=probe_denied):
                def signal_group(pid, signum):
                    if signum == 0 and probe_denied:
                        raise PermissionError(errno.EPERM, "group remains uncertain")

                process = mock.Mock(pid=123)
                with mock.patch.object(GATE, "TERMINATION_GRACE_SECONDS", 0), \
                        mock.patch.object(GATE, "TERMINATION_KILL_SECONDS", 0), \
                        mock.patch.object(GATE.os, "killpg", side_effect=signal_group) as kill, \
                        contextlib.redirect_stderr(io.StringIO()):
                    self.assertFalse(GATE.terminate_process(process))
                self.assertEqual([mock.call(123, signal.SIGTERM), mock.call(123, 0),
                                  mock.call(123, signal.SIGKILL), mock.call(123, 0)], kill.call_args_list)

    def test_exit_transition_probe_denial_requires_later_group_absence(self):
        process = mock.Mock(pid=123)
        with mock.patch.object(GATE, "TERMINATION_GRACE_SECONDS", 0), \
                mock.patch.object(GATE.time, "monotonic", side_effect=[0, 0, 1, 1.01]), \
                mock.patch.object(GATE.time, "sleep") as sleep, \
                mock.patch.object(GATE.os, "killpg", side_effect=[
                    None, None, None, PermissionError(errno.EPERM, "exiting group"),
                    ProcessLookupError(errno.ESRCH, "group absent"),
                ]) as kill:
            self.assertTrue(GATE.terminate_process(process))
        self.assertEqual([mock.call(123, signal.SIGTERM), mock.call(123, 0),
                          mock.call(123, signal.SIGKILL), mock.call(123, 0),
                          mock.call(123, 0)], kill.call_args_list)
        sleep.assert_called_once_with(0.05)

    def test_signal_denial_and_non_permission_probe_error_remain_fatal(self):
        for side_effect in ([PermissionError(errno.EPERM, "TERM denied")],
                            [None, None, PermissionError(errno.EPERM, "KILL denied")],
                            [None, OSError(errno.EIO, "probe failed")]):
            with self.subTest(side_effect=side_effect), \
                    mock.patch.object(GATE, "TERMINATION_GRACE_SECONDS", 0), \
                    mock.patch.object(GATE.os, "killpg", side_effect=side_effect) as kill, \
                    mock.patch.object(GATE.time, "sleep") as sleep, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(GATE.terminate_process(mock.Mock(pid=123)))
                self.assertEqual(len(side_effect), kill.call_count)
                sleep.assert_not_called()

    def resistant_worker_control(self, leader_exits_first, bind_worker=None):
        with tempfile.TemporaryDirectory(prefix="p2pkit-owned-group-") as temporary:
            ready = Path(temporary) / "worker.pid"
            worker_code = (
                "import os,pathlib,signal,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(90)"
            )
            leader_code = (
                "import pathlib,subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{worker_code!r},sys.argv[1]]); "
                "ready=pathlib.Path(sys.argv[1]); "
                "\nwhile not ready.exists(): time.sleep(0.01)\n"
                + ("sys.exit(0)" if leader_exits_first else "time.sleep(90)")
            )
            leader = subprocess.Popen([sys.executable, "-c", leader_code, str(ready)], start_new_session=True)
            unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"], start_new_session=True)
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "TERM-resistant worker never reached ready state")
                worker = int(ready.read_text())
                if bind_worker is not None:
                    bind_worker(leader.pid, worker)
                if leader_exits_first:
                    self.assertEqual(0, leader.wait(timeout=10))
                # Bound a deterministic control's grace period without lengthening
                # production timeouts or changing assertions. R1 has no constant.
                with mock.patch.object(GATE, "TERMINATION_GRACE_SECONDS", 0.2, create=True):
                    drained = GATE.terminate_process(leader)
                if bind_worker is not None:
                    bind_worker.phase = "worker-zero"
                with self.assertRaises(ProcessLookupError, msg="Owned resistant worker survived cleanup"):
                    os.kill(worker, 0)
                if bind_worker is not None:
                    bind_worker.phase = "group-zero"
                with self.assertRaises(ProcessLookupError, msg="Owned process group was not drained"):
                    os.killpg(leader.pid, 0)
                self.assertTrue(drained)
                self.assertIsNone(unrelated.poll(), "Cleanup touched an unrelated process group")
            finally:
                if bind_worker is not None:
                    bind_worker.phase = "finalizer-kill"
                # A red control must not leave its intentionally resistant child.
                try:
                    try:
                        os.killpg(leader.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                finally:
                    try:
                        leader.wait(timeout=10)
                    finally:
                        try:
                            unrelated.terminate()
                        finally:
                            unrelated.wait(timeout=10)

    def test_term_resistant_worker_is_killed_after_leader_exits_on_term(self):
        with darwin_group_diagnostic(leader_exits_first=False) as bind_worker:
            self.resistant_worker_control(leader_exits_first=False, bind_worker=bind_worker)

    def test_surviving_group_is_drained_even_when_leader_already_exited(self):
        with darwin_group_diagnostic(leader_exits_first=True) as bind_worker:
            self.resistant_worker_control(leader_exits_first=True, bind_worker=bind_worker)


if __name__ == "__main__":
    unittest.main(verbosity=2)
