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
CANONICAL_PYTHON = str(Path(sys.executable).resolve(strict=True))


def diagnostic_arguments(python_executable):
    # Independent expected DATA, not a replacement for the separately tested helper.
    return [*SELECTOR, "-Pp2pkit.audit.jmdnsStartupPrimitives=true",
            "-Pp2pkit.audit.pythonExecutable=" + python_executable]


def offline(event, _args):
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                                               "ctypes.dlopen", "os.putenv", "os.unsetenv"):
        raise AssertionError("offline driver controls attempted native execution: " + event)


sys.addaudithook(offline)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


class EnvironmentRefusalControls(unittest.TestCase):
    """Synthetic DATA/constructor controls, not runner environment or native evidence."""

    FIXED = (
        ("HOME", "JMDNS_ENV_MISSING_HOME", "JMDNS_ENV_VALUE_HOME"),
        ("TMPDIR", "JMDNS_ENV_MISSING_TMPDIR", "JMDNS_ENV_VALUE_TMPDIR"),
        ("XDG_CONFIG_HOME", "JMDNS_ENV_MISSING_XDG_CONFIG_HOME", "JMDNS_ENV_VALUE_XDG_CONFIG_HOME"),
        ("XDG_CACHE_HOME", "JMDNS_ENV_MISSING_XDG_CACHE_HOME", "JMDNS_ENV_VALUE_XDG_CACHE_HOME"),
        ("GNUPGHOME", "JMDNS_ENV_MISSING_GNUPGHOME", "JMDNS_ENV_VALUE_GNUPGHOME"),
        ("GH_CONFIG_DIR", "JMDNS_ENV_MISSING_GH_CONFIG_DIR", "JMDNS_ENV_VALUE_GH_CONFIG_DIR"),
        ("KONAN_DATA_DIR", "JMDNS_ENV_MISSING_KONAN_DATA_DIR", "JMDNS_ENV_VALUE_KONAN_DATA_DIR"),
        ("ANDROID_USER_HOME", "JMDNS_ENV_MISSING_ANDROID_USER_HOME", "JMDNS_ENV_VALUE_ANDROID_USER_HOME"),
        ("PYTHONDONTWRITEBYTECODE", "JMDNS_ENV_MISSING_PYTHONDONTWRITEBYTECODE",
         "JMDNS_ENV_VALUE_PYTHONDONTWRITEBYTECODE"),
        ("PYTHONUNBUFFERED", "JMDNS_ENV_MISSING_PYTHONUNBUFFERED", "JMDNS_ENV_VALUE_PYTHONUNBUFFERED"),
        ("GIT_CONFIG_NOSYSTEM", "JMDNS_ENV_MISSING_GIT_CONFIG_NOSYSTEM", "JMDNS_ENV_VALUE_GIT_CONFIG_NOSYSTEM"),
        ("GIT_CONFIG_GLOBAL", "JMDNS_ENV_MISSING_GIT_CONFIG_GLOBAL", "JMDNS_ENV_VALUE_GIT_CONFIG_GLOBAL"),
        ("GIT_TERMINAL_PROMPT", "JMDNS_ENV_MISSING_GIT_TERMINAL_PROMPT", "JMDNS_ENV_VALUE_GIT_TERMINAL_PROMPT"),
        ("LC_ALL", "JMDNS_ENV_MISSING_LC_ALL", "JMDNS_ENV_VALUE_LC_ALL"),
        ("TZ", "JMDNS_ENV_MISSING_TZ", "JMDNS_ENV_VALUE_TZ"),
    )
    EXTRAS = (
        ("__CF_USER_TEXT_ENCODING", "JMDNS_ENV_EXTRA_CF_USER_TEXT_ENCODING"),
        ("__PYVENV_LAUNCHER__", "JMDNS_ENV_EXTRA_PYVENV_LAUNCHER"),
        ("LC_CTYPE", "JMDNS_ENV_EXTRA_LC_CTYPE"),
        ("PYTHONEXECUTABLE", "JMDNS_ENV_EXTRA_PYTHONEXECUTABLE"),
        ("SDKROOT", "JMDNS_ENV_EXTRA_SDKROOT"),
        ("DYLD_FRAMEWORK_PATH", "JMDNS_ENV_EXTRA_DYLD_FRAMEWORK_PATH"),
        ("DYLD_LIBRARY_PATH", "JMDNS_ENV_EXTRA_DYLD_LIBRARY_PATH"),
    )
    OTHER = "JMDNS_ENV_OTHER"

    class AfterEnvironment(Exception):
        """Stop the real constructor at its first downstream request read."""

    def environment(self):
        return {"HOME": "/controlled/home", "TMPDIR": "/controlled/tmp",
            "XDG_CONFIG_HOME": "/controlled/home/config", "XDG_CACHE_HOME": "/controlled/home/cache",
            "GNUPGHOME": "/controlled/home/gnupg", "GH_CONFIG_DIR": "/controlled/home/gh",
            "KONAN_DATA_DIR": "/controlled/konan", "ANDROID_USER_HOME": "/controlled/android-user",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "TZ": "UTC",
            "PATH": "/controlled/bin", "GRADLE_USER_HOME": "/controlled/gradle-home",
            "P2PKIT_AUDIT_STATE_DIR": "/controlled/state", "P2PKIT_AUDIT_JOB_ID": "b" * 32,
            "P2PKIT_AUDIT_OWNERSHIP_CHAIN": "a" * 32, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "fixture-domains"}

    def assert_code(self, actual, expected, code):
        before = [(value, tuple(value.items())) for value in (actual, expected) if type(value) is dict]
        with patch.object(M.sys, "stdout") as stdout, patch.object(M.sys, "stderr") as stderr:
            result = M.child_environment_failure_code(actual, expected)
        self.assertIs(type(result), str)
        self.assertEqual(result, code)
        stdout.write.assert_not_called()
        stderr.write.assert_not_called()
        for value, items in before:
            after = tuple(value.items())
            self.assertEqual(len(after), len(items))
            for old, new in zip(items, after):
                self.assertIs(new[0], old[0])
                self.assertIs(new[1], old[1])

    def test_closed_literal_rosters_and_all_public_records_fit_existing_bound(self):
        self.assertEqual(M.CHILD_ENVIRONMENT_FIXED_CODES, self.FIXED)
        self.assertEqual(M.CHILD_ENVIRONMENT_EXTRA_CODES, self.EXTRAS)
        codes = {code for _, missing, changed in self.FIXED for code in (missing, changed)}
        codes.update(code for _, code in self.EXTRAS)
        codes.add(self.OTHER)
        self.assertEqual(len(codes), 38)
        source = (ROOT / "scripts/hosted_command_failure_hint.py").read_text(encoding="utf-8")
        values = {node.targets[0].id: node.value for node in ast.parse(source).body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
        driver_codes = ast.literal_eval(values["DRIVER_CODES"].args[0])
        self.assertEqual({code for code in driver_codes if code.startswith("JMDNS_ENV_")}, codes)
        all_codes = driver_codes | ast.literal_eval(values["UPDATE_CODES"].args[0])
        all_codes.add(ast.literal_eval(values["GENERIC"]))
        self.assertEqual(ast.literal_eval(values["MAX_BYTES"]), 128)
        for phase in ast.literal_eval(values["PHASES"]):
            for code in all_codes:
                with self.subTest(phase=phase, code=code):
                    raw = ("UNTRUSTED_V1 " + "a" * 32 + " " + phase + " " + code + "\n").encode("ascii")
                    self.assertLessEqual(len(raw), 128)

    def test_each_fixed_missing_or_changed_value_has_only_its_literal_code(self):
        expected = self.environment()
        for key, missing, changed in self.FIXED:
            with self.subTest(key=key):
                actual = dict(expected)
                del actual[key]
                self.assert_code(actual, expected, missing)
                self.assert_code({**expected, key: "synthetic-not-for-output"}, expected, changed)
        self.assert_code(dict(expected), expected, self.OTHER)

    def test_each_known_extra_is_value_independent_and_not_a_new_allowance(self):
        expected = self.environment()
        for key, code in self.EXTRAS:
            for value in ("", "synthetic-not-for-output\n" * 100):
                with self.subTest(key=key):
                    self.assert_code({**expected, key: value}, expected, code)
            with_expected_extra = {**expected, key: "already-expected"}
            self.assert_code(dict(with_expected_extra), with_expected_extra, self.OTHER)
            self.assert_code({**with_expected_extra, key: "changed"}, with_expected_extra, self.OTHER)
            self.assert_code(expected, with_expected_extra, self.OTHER)

    def test_first_rank_is_stable_nonexhaustive_and_independent_of_input_order(self):
        expected = self.environment()
        for index, (key, missing, changed) in enumerate(self.FIXED):
            actual = {**expected, **dict(self.EXTRAS), "UNREVIEWED_RUNTIME_MARKER": "fixture"}
            for later, _, _ in self.FIXED[index:]:
                actual[later] = "changed"
            self.assert_code(dict(reversed(tuple(actual.items()))), expected, changed)
            del actual[key]
            self.assert_code(actual, dict(reversed(tuple(expected.items()))), missing)
        for index, (_, code) in enumerate(self.EXTRAS):
            actual = {**expected, **dict(self.EXTRAS[index:]), "UNREVIEWED_RUNTIME_MARKER": "fixture"}
            self.assert_code(dict(reversed(tuple(actual.items()))), expected, code)

    def test_unknown_differences_and_absent_expected_fields_do_not_invent_codes(self):
        expected = self.environment()
        self.assert_code({**expected, "UNREVIEWED_RUNTIME_MARKER": "fixture"}, expected, self.OTHER)
        self.assert_code({**expected, "PATH": "changed"}, expected, self.OTHER)
        actual = dict(expected)
        del actual["PATH"]
        self.assert_code(actual, expected, self.OTHER)
        for key, _, _ in self.FIXED:
            self.assert_code({key: "not-an-expected-field"}, {}, self.OTHER)
        self.assert_code({}, {}, self.OTHER)

    def test_non_builtin_or_poison_inputs_are_never_rendered_hashed_or_compared(self):
        class Poison:
            def forbidden(self, *_args, **_kwargs):
                raise AssertionError("diagnostic inspected poisoned input")
            __str__ = __repr__ = __eq__ = __ne__ = __hash__ = __iter__ = forbidden

        class PoisonString(str):
            __str__ = __repr__ = __eq__ = __ne__ = Poison.forbidden
            __hash__ = str.__hash__

        class PoisonDict(dict):
            items = keys = __iter__ = __eq__ = __ne__ = __str__ = __repr__ = Poison.forbidden

        expected = self.environment()
        malformed = (None, [], Poison(), PoisonDict(expected),
            {**expected, "HOME": Poison()}, {**expected, "HOME": PoisonString("fixture")},
            {**expected, PoisonString("unknown-poison-key"): "fixture"}, {**expected, 7: "fixture"})
        for index, value in enumerate(malformed):
            with self.subTest(case=index):
                self.assert_code(value, expected, self.OTHER)
                self.assert_code(expected, value, self.OTHER)

    def constructor_case(self, phase, actual, expected, code):
        root, state = Path("/controlled/controller"), Path("/controlled/state")
        owner_keys = ("P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN",
                      "P2PKIT_AUDIT_OWNERSHIP_DOMAINS", "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME")
        context = {"host": "macos-arm64", "id": "b" * 32, "gradleHome": expected["GRADLE_USER_HOME"],
                   "root": str(root), "source": {"commit": "c" * 40, "tree": "d" * 40}}
        runner = SimpleNamespace(context_at=Mock(return_value=(state, context)),
                                 source_snapshot=Mock(return_value=context["source"]))
        data = SimpleNamespace(PRODUCT_SECONDS=1200, OBSERVATION_SECONDS=120)
        controller = SimpleNamespace(ROOT=root, STOP_SECONDS=120, NATIVE_HEADROOM=180,
            module=Mock(side_effect=[runner, data]), physical=Mock(return_value=root.parent / "candidate"),
            NATIVE_OWNER_ENV=owner_keys,
            child_environment=Mock(return_value={key: value for key, value in expected.items()
                                                if key not in owner_keys}),
            read_file=Mock(side_effect=self.AfterEnvironment))
        processes = SimpleNamespace(CHAIN_ENV=owner_keys[1], DOMAINS_ENV=owner_keys[2], JOB_ENV=owner_keys[0],
            ownership_domains=Mock(return_value=[{"id": "a" * 32, "job": "b" * 32,
                "state": str(state), "home": expected["GRADLE_USER_HOME"]}]))
        fake_sys = SimpleNamespace(flags=SimpleNamespace(isolated=1, no_site=1), dont_write_bytecode=True,
                                   modules={"audit_processes": processes})
        driver = M.Driver.__new__(M.Driver)
        with patch.object(M, "sys", fake_sys), patch.object(M.os, "environ", actual), \
                patch.object(M.Path, "cwd", return_value=root), \
                patch.object(M.subprocess, "Popen", side_effect=AssertionError("no native launch")) as launch, \
                patch.object(M.Driver, "java_metadata", side_effect=AssertionError("no Java query")) as metadata, \
                patch.object(M, "child_environment_failure_code", wraps=M.child_environment_failure_code) as classify:
            with self.assertRaises(self.AfterEnvironment if code is None else M.DriverError) as caught:
                M.Driver.__init__(driver, controller, phase)
        controller.child_environment.assert_called_once_with(actual, state.parent)
        launch.assert_not_called()
        metadata.assert_not_called()
        if code is None:
            classify.assert_not_called()
            controller.read_file.assert_called_once_with(state / "evidence/maintenance/jmdns-request.json", 16384)
            self.assertEqual(driver.env, expected)
            self.assertIsNot(driver.env, actual)
        else:
            self.assertEqual(caught.exception.args, (code,))
            classify.assert_called_once()
            controller.read_file.assert_not_called()
            self.assertFalse(hasattr(driver, "env"))
        return classify

    def test_real_constructor_requires_full_equality_before_downstream_work_in_both_phases(self):
        expected = self.environment()
        missing = dict(expected)
        del missing["HOME"]
        cases = ((dict(expected), None), (missing, "JMDNS_ENV_MISSING_HOME"),
            ({**expected, "LC_ALL": "changed"}, "JMDNS_ENV_VALUE_LC_ALL"),
            ({**expected, "__CF_USER_TEXT_ENCODING": "fixture"}, "JMDNS_ENV_EXTRA_CF_USER_TEXT_ENCODING"),
            ({**expected, "UNREVIEWED_RUNTIME_MARKER": "fixture"}, self.OTHER),
            ({**expected, "__CF_USER_TEXT_ENCODING": "fixture", "LC_CTYPE": "fixture",
                "UNREVIEWED_RUNTIME_MARKER": "fixture"}, "JMDNS_ENV_EXTRA_CF_USER_TEXT_ENCODING"))
        for phase in ("target", "observer"):
            for index, (actual, code) in enumerate(cases):
                with self.subTest(phase=phase, case=index):
                    self.constructor_case(phase, actual, expected, code)

    def test_equal_second_snapshot_cannot_reverse_constructor_refusal(self):
        expected = self.environment()

        class ChangingSnapshot:
            """Synthetic mapping only: never mutate the real process environment."""
            def __init__(self):
                self.snapshots = 0
                self.first = {**expected, "UNREVIEWED_RUNTIME_MARKER": "fixture"}

            def get(self, key, default=None):
                return self.first.get(key, default)

            def keys(self):
                self.snapshots += 1
                return (self.first if self.snapshots == 1 else expected).keys()

            def __getitem__(self, key):
                return (self.first if self.snapshots < 2 else expected)[key]

        for phase in ("target", "observer"):
            with self.subTest(phase=phase):
                actual = ChangingSnapshot()
                classify = self.constructor_case(phase, actual, expected, self.OTHER)
                self.assertEqual(actual.snapshots, 2)
                classify.assert_called_once_with(expected, expected)


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
            data=SimpleNamespace(GRADLE_ARGUMENTS=tuple(SELECTOR),
                diagnostic_gradle_arguments=Mock(side_effect=diagnostic_arguments)),
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
            expected = diagnostic_arguments(CANONICAL_PYTHON)
            driver.data.diagnostic_gradle_arguments.assert_called_once_with(CANONICAL_PYTHON)
            driver.runner.gradle_arguments.assert_called_once_with(expected)
            argv, = launch.call_args.args
            self.assertEqual(argv, ["/controlled/candidate/gradlew", *expected, "--source-owned-policy"])
            self.assertEqual(launch.call_args.kwargs, {"cwd": driver.candidate, "env": driver.env,
                                                     "stdin": subprocess.DEVNULL, "close_fds": True})
            name, record = driver.record.call_args.args
            self.assertEqual(name, "jmdns-target.json")
            self.assertEqual(record["testExitCode"], code)
            self.assertEqual(record["requestedGradleArgv"], expected)
            self.assertEqual(record["executedGradleArgv"], argv)
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

    def original_target_driver(self, field=None, arguments=None):
        _, driver = self.target_driver()
        driver.root = Path("/controlled/controller")
        driver.state = Path("/controlled/state")
        driver.records = driver.state / "evidence/maintenance"
        driver.invocation = "d" * 32  # The observer is not the original target invocation.
        target = self.target()
        expected = diagnostic_arguments(CANONICAL_PYTHON)
        target["requestedGradleArgv"] = expected
        target["executedGradleArgv"] = [str(driver.candidate / "gradlew"), *expected, "--source-owned-policy"]
        if field is not None:
            target[field] = list(arguments) if field == "requestedGradleArgv" else [
                str(driver.candidate / "gradlew"), *arguments, "--source-owned-policy"]
        target_raw = encoded(target)
        receipt = {"id": target["invocationId"], "productExitCode": target["testExitCode"]}
        receipt_raw = encoded(receipt)
        returned = {"schema": 1, "scope": SCOPE, "requestSha256": driver.request_hash,
                    "targetReceipt": receipt, "targetReceiptSha256": digest(receipt_raw),
                    "targetRecordSha256": digest(target_raw), "returnedMonotonicNs": 710 * M.NS}
        files = {driver.records / "jmdns-target-return.json": encoded(returned),
                 driver.records / "jmdns-target.json": target_raw,
                 driver.state / "evidence" / receipt["id"] / "receipt.json": receipt_raw}
        driver.c = SimpleNamespace(DIAGNOSTIC_SCOPE=SCOPE, MIB=1024 * 1024, parsed=json.loads, digest=digest,
            read_file=Mock(side_effect=lambda path, limit=None: (files[path], {})), command_return_data=Mock())
        return driver, returned, target, receipt

    def test_observer_original_target_binds_exact_interpreter_and_coupled_options(self):
        expected = diagnostic_arguments(CANONICAL_PYTHON)
        driver, returned, target, receipt = self.original_target_driver()
        with patch.object(M.time, "monotonic_ns", return_value=720 * M.NS):
            actual = M.original_target(driver)
        self.assertEqual(actual, (returned, target, receipt, digest(encoded(returned))))
        driver.data.diagnostic_gradle_arguments.assert_called_once_with(CANONICAL_PYTHON)
        driver.c.command_return_data.assert_called_once()
        self.assertEqual(driver.c.command_return_data.call_args.args[:4],
                         (1, receipt, driver.context, target["invocationId"]))
        self.assertEqual(driver.c.command_return_data.call_args.args[4:], (
            "dependency-maintenance-jmdns-target",
            [CANONICAL_PYTHON, "-I", "-B", "-S",
             str(driver.root / "scripts/run-hosted-dependency-update.py"), "_diagnostic-target"],
        ))
        malformed = (list(SELECTOR), expected[:-1], [*SELECTOR, expected[-1]],
                     [*SELECTOR, "-Pp2pkit.audit.jmdnsStartupPrimitives=false", expected[-1]],
                     [*SELECTOR, expected[-2], "-Pp2pkit.audit.pythonExecutable=/different-python/bin/python3.12"],
                     [*SELECTOR, expected[-1], expected[-2]], [*expected, expected[-1]])
        for field in ("requestedGradleArgv", "executedGradleArgv"):
            for index, arguments in enumerate(malformed):
                with self.subTest(field=field, mutation=index):
                    driver, _, _, _ = self.original_target_driver(field, arguments)
                    with patch.object(M.time, "monotonic_ns", return_value=720 * M.NS), \
                            self.assertRaisesRegex(M.DriverError, "^JMDNS_TARGET_IDENTITY$"):
                        M.original_target(driver)
                    driver.c.command_return_data.assert_not_called()

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
