#!/usr/bin/env python3
"""Offline driver DATA/source/flow models; no Java or native execution evidence."""
import ast
import copy
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import FunctionType, ModuleType, SimpleNamespace, TracebackType
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

        def literal_frozenset(node):
            self.assertIsInstance(node, ast.Call)
            self.assertIsInstance(node.func, ast.Name)
            self.assertEqual(node.func.id, "frozenset")
            self.assertEqual(len(node.args), 1)
            self.assertEqual(node.keywords, [])
            self.assertIsInstance(node.args[0], ast.Set)
            literals = ast.literal_eval(node.args[0])
            self.assertEqual(len(literals), len(node.args[0].elts))
            self.assertTrue(all(type(value) is str for value in literals))
            return literals

        union = values["DRIVER_CODES"]
        self.assertIsInstance(union, ast.BinOp)
        self.assertIsInstance(union.op, ast.BitOr)
        self.assertIsInstance(union.right, ast.Name)
        self.assertEqual(union.right.id, "POLICY_FILE_OWNER_LINK_CODES")
        union = union.left
        self.assertIsInstance(union, ast.BinOp)
        self.assertIsInstance(union.op, ast.BitOr)
        self.assertIsInstance(union.right, ast.Name)
        self.assertEqual(union.right.id, "POLICY_FILE_CODES")
        driver_literals = literal_frozenset(union.left)
        roles = {"SOURCE", "CLANG", "JNI_HEADER", "JNI_PLATFORM_HEADER", "DNS_SD_HEADER",
                 "LINKER_STUB", "JAVA_RELEASE", "DYLIB"}
        predicates = {"TYPE", "LINKS", "OWNER", "WRITE", "NONPOSITIVE", "STAT_LIMIT", "READ_LIMIT"}
        self.assertEqual(len(roles), 8)
        self.assertEqual(len(predicates), 7)
        self.assertEqual(literal_frozenset(values["POLICY_FILE_ROLES"]), roles)
        self.assertEqual(literal_frozenset(values["POLICY_FILE_PREDICATES"]), predicates)
        expected_product = ast.parse(
            'frozenset(f"JMDNS_POLICY_FILE_{role}_{predicate}" '
            'for role in POLICY_FILE_ROLES for predicate in POLICY_FILE_PREDICATES)', mode="eval").body
        self.assertEqual(ast.dump(values["POLICY_FILE_CODES"]), ast.dump(expected_product))
        policy_codes = {f"JMDNS_POLICY_FILE_{role}_{predicate}" for role in roles for predicate in predicates}
        self.assertEqual(len(policy_codes), 56)
        owner_link_codes = {"JMDNS_POLICY_FILE_DNS_SD_HEADER_OWNER_LINKS",
                            "JMDNS_POLICY_FILE_LINKER_STUB_OWNER_LINKS"}
        self.assertEqual(literal_frozenset(values["POLICY_FILE_OWNER_LINK_CODES"]), owner_link_codes)
        self.assertTrue(owner_link_codes.isdisjoint(driver_literals | policy_codes))
        self.assertEqual(len(policy_codes | owner_link_codes), 58)
        driver_codes = driver_literals | policy_codes | owner_link_codes
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
            prepare_policy_native=Mock(return_value={"synthetic": "prepared"}), verify_policy_native=Mock(),
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


class SyntheticPolicyFrame:
    """Temp DATA plus a mocked admitted frame, never an admission/native assessor.

    The selected-Xcode literal is mapped only to this temporary tree. No installed
    tool, repository source, real owner state, compiler or Gradle is read/run here.
    The artifact deliberately is plain text, not a loadable native library.
    """

    SOURCE = "library/p2p-transport-lan/src/jvmTest/native/JmdnsStartupPolicy.c"
    REPORTS = "library/p2p-transport-lan/build/reports/jmdns-policy-native"
    LIBRARY = "libp2pkit-jmdns-policy.dylib"
    DEVELOPER = "/Applications/Xcode_26.5.app/Contents/Developer"

    def __init__(self, case, *, compile_code=0):
        self.case, self.compile_code = case, compile_code
        self.stack = ExitStack()

    def __enter__(self):
        try:
            self.base = Path(self.stack.enter_context(
                tempfile.TemporaryDirectory(prefix="jmdns-driver-controls-"))).resolve(strict=True)
            self.clock = 101 * M.NS
            self.stack.enter_context(patch.object(M.time, "monotonic_ns", side_effect=lambda: self.clock))
            self.unexpected_launch = self.stack.enter_context(patch.object(M.subprocess, "Popen",
                side_effect=AssertionError("synthetic frame attempted an unmocked command")))
            self.root, self.candidate, self.state = (self.base / name for name in ("controller", "candidate", "state"))
            self.records = self.state / "evidence/maintenance"
            self.directory = self.candidate / self.REPORTS
            self.library = self.directory / self.LIBRARY
            self.original_record = self.records / "jmdns-policy-compile.json"
            self.consumer_record = self.directory / "compile-record.json"
            self.request_path = self.records / "jmdns-request.json"
            self.target_record = self.records / "jmdns-target.json"
            self.developer = self.base / "installed/Xcode_26.5.app/Contents/Developer"
            self.java_home = self.base / "installed/jdk17"
            self.clang = self.developer / "Toolchains/XcodeDefault.xctoolchain/usr/bin/clang"
            self.sdk = self.developer / "Platforms/MacOSX.platform/Developer/SDKs/MacOSX26.5.sdk"
            self.system_stub = self.sdk / "usr/lib/libSystem.tbd"
            self.paths = {"source": self.candidate / self.SOURCE, "clang": self.clang,
                "jniHeader": self.java_home / "include/jni.h",
                "jniPlatformHeader": self.java_home / "include/darwin/jni_md.h",
                "dnsSdHeader": self.sdk / "usr/include/dns_sd.h",
                "linkerStub": self.sdk / "usr/lib/libSystem.B.tbd", "javaRelease": self.java_home / "release"}
            self.input_bytes = {name: ("SYNTHETIC INPUT DATA ONLY: " + name + "\n").encode("ascii")
                                for name in self.paths}
            self.input_bytes["source"] = b"/* SYNTHETIC INPUT ONLY; not a native program. */\n"
            self.input_bytes["javaRelease"] = b'JAVA_VERSION="17.0.16"\nIMPLEMENTOR="synthetic"\n'
            for name, path in self.paths.items():
                self.file(path, self.input_bytes[name])
            self.system_stub.symlink_to("libSystem.B.tbd")  # SDK logical alias, canonical regular input retained.
            self.root.mkdir(mode=0o700)
            (self.records / "jmdns-target").mkdir(parents=True, mode=0o700)
            source_raw = self.input_bytes["source"]
            self.blob = hashlib.sha1(b"blob " + str(len(source_raw)).encode("ascii") + b"\0" + source_raw).hexdigest()
            self.staged = ("100644 " + self.blob + " 0\t" + self.SOURCE + "\n").encode("ascii")
            self.request = {"schema": 1, "scope": SCOPE,
                "request": {"operation": "diagnose-jmdns", "controller_sha": "c" * 40,
                    "controller_tree": "d" * 40, "candidate_sha": "e" * 40,
                    "candidate_tree": "f" * 40, "dependency_base_sha": "1" * 40},
                "github": {"repository": "synthetic-owner/synthetic-repository", "ref": "refs/heads/main",
                    "runId": "101", "runAttempt": "1", "workflow": ".github/workflows/dependency-update-candidate.yml"},
                "startedMonotonicNs": 100 * M.NS, "deadlineMonotonicNs": 1300 * M.NS,
                "observationBudgetNs": 120 * M.NS}
            self.file(self.request_path, encoded(self.request), 0o600)
            self.env = {"JAVA_HOME": str(self.java_home), "DEVELOPER_DIR": self.DEVELOPER,
                "P2PKIT_AUDIT_OWNERSHIP_CHAIN": "a" * 32, "P2PKIT_AUDIT_JOB_ID": "b" * 32,
                "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "synthetic-domains", "P2PKIT_AUDIT_STATE_DIR": str(self.state)}
            self.c = SimpleNamespace(ROOT=self.root, DIAGNOSTIC_SCOPE=SCOPE,
                physical=Mock(side_effect=self.physical), clean_source=Mock(), digest=digest, parsed=json.loads,
                encoded=Mock(side_effect=encoded), read_file=Mock(side_effect=self.read_file),
                write_new=Mock(side_effect=self.write_new))
            self.driver = M.Driver.__new__(M.Driver)
            self.driver.c, self.driver.phase = self.c, "target"
            self.driver.root, self.driver.candidate, self.driver.state = self.root, self.candidate, self.state
            self.driver.records, self.driver.directory = self.records, self.records / "jmdns-target"
            self.driver.env, self.driver.request = self.env, self.request
            self.driver.request_hash = digest(encoded(self.request))
            self.driver.invocation, self.driver.context = "a" * 32, {"id": "b" * 32}
            self.driver.product_deadline, self.driver.observation_deadline = 1000 * M.NS, 220 * M.NS
            self.driver.runner = SimpleNamespace(git=Mock(return_value=self.staged),
                gradle_arguments=Mock(side_effect=lambda argv: [*argv, "--source-owned-policy"]),
                MAX_STREAM_BYTES=64 * 1024 * 1024)
            self.driver.data = SimpleNamespace(GRADLE_ARGUMENTS=tuple(SELECTOR), HASH_SECONDS=5,
                diagnostic_gradle_arguments=Mock(side_effect=diagnostic_arguments))
            self.driver.java_metadata = Mock(return_value={"signature": {"status": "RETURNED", "exitCode": 1}})
            self.real_observe = self.driver.observe_command
            self.driver.observe_command = Mock(side_effect=self.observe)
            self.driver.policy_file = Mock(wraps=self.driver.policy_file)
            self.prepare_impl = self.driver.prepare_policy_native
            self.driver.prepare_policy_native = Mock(side_effect=self.prepare)
            self.driver.verify_policy_native = Mock(wraps=self.driver.verify_policy_native)
            self.driver.record = Mock(wraps=self.driver.record)
            self.outputs = {"policy-find-clang": ((str(self.clang) + "\n").encode("utf-8"), b""),
                "policy-find-sdk": ((str(self.sdk) + "\n").encode("utf-8"), b""),
                "policy-clang-version": (b"Apple clang version SYNTHETIC\nTarget: arm64-apple-darwin\n", b""),
                "policy-native-compile": (b"SYNTHETIC compiler stdout\n", b"SYNTHETIC compiler stderr\n"),
                "policy-dylibSignature": (b"SYNTHETIC signature observation\n", b""),
                "policy-dylibUuid": (b"SYNTHETIC UUID observation\n", b"")}
            self.codes = {"policy-native-compile": self.compile_code}
            self.not_returned, self.cost_seconds, self.after_observation = {}, {}, {}
            self.started_commands, self.writes = [], []
            self.record_write_seconds = 0
            self.artifact_bytes = b"SYNTHETIC NON-DYLIB; offline driver flow DATA only\n"
            self.prepared = None
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)

    def file(self, path, raw, mode=0o644):
        self.case.assertTrue(path.is_relative_to(self.base))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw)
        path.chmod(mode)

    def physical(self, value):
        path = Path(value)
        if str(path) == self.DEVELOPER:
            return self.developer  # Sole installed-path substitution; all bytes remain synthetic.
        self.case.assertTrue(path.is_absolute() and path.is_relative_to(self.base) and ".." not in path.parts)
        for item in (path, *path.parents):
            if item.is_symlink():
                raise M.DriverError("MODEL_PATH_SYMLINK")
        return path

    def read_file(self, path, limit=64 * 1024 * 1024):
        path = self.physical(path)
        info = path.lstat()
        self.case.assertTrue(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                             info.st_uid == os.getuid() and not info.st_mode & 0o022)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        self.case.assertLessEqual(len(raw), limit)
        self.case.assertEqual(len(raw), info.st_size)
        return raw, {"identity": [info.st_dev, info.st_ino], "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid, "size": len(raw), "sha256": digest(raw),
            "mtimeNs": info.st_mtime_ns, "ctimeNs": info.st_ctime_ns}

    def write_new(self, path, raw):
        path = self.physical(path)
        self.case.assertIs(type(raw), bytes)
        started = self.clock
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
            self.case.assertEqual(stream.write(raw), len(raw))
        self.case.assertEqual(self.read_file(path, max(256 * 1024, len(raw)))[0], raw)
        if path in (self.original_record, self.consumer_record):
            self.clock += self.record_write_seconds * M.NS
        self.writes.append((path, started, self.clock))

    def policy_info(self, path, raw):
        info = path.lstat()
        return {"path": str(path), "identity": [info.st_dev, info.st_ino], "mode": info.st_mode,
            "uid": info.st_uid, "nlink": info.st_nlink, "size": len(raw), "sha256": digest(raw),
            "mtimeNs": info.st_mtime_ns, "ctimeNs": info.st_ctime_ns}

    def compiler_argv(self):
        return [str(self.clang), "-dynamiclib", "-arch", "arm64", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-isysroot", str(self.sdk), "-I", str(self.java_home / "include"),
            "-I", str(self.java_home / "include/darwin"), str(self.paths["source"]), "-o", str(self.library)]

    def observe(self, name, argv, seconds, interpretation_limit):
        self.case.assertIn(name, self.outputs)
        window = self.driver.observation_window(seconds)
        if window is None:
            return {"status": "INCONCLUSIVE", "reason": "OBSERVATION_BUDGET_NOT_ADMITTED"}, None, None
        if name in self.not_returned:
            return {"status": "INCONCLUSIVE", "reason": self.not_returned[name]}, None, None
        started, deadline = window
        self.started_commands.append(name)  # Synthetic starts, not native lifecycle evidence.
        self.clock += self.cost_seconds.get(name, 0) * M.NS
        self.case.assertLessEqual(self.clock, deadline)
        code = self.codes.get(name, 0)
        stdout, stderr = self.outputs[name]
        outputs = {}
        for suffix, raw in (("stdout", stdout), ("stderr", stderr)):
            path = self.driver.directory / (name + "." + suffix + ".log")
            self.file(path, raw, 0o600)
            outputs[suffix] = {"file": path.relative_to(self.records).as_posix(), **self.read_file(path)[1]}
        result = {"status": "RETURNED", "argv": argv, "exitCode": code,
            "startedMonotonicNs": started, "endedMonotonicNs": self.clock, **outputs,
            "interpretation": "INCONCLUSIVE" if code or len(stdout) + len(stderr) > interpretation_limit else
                              "NATIVE_ORIGINAL_REVIEW_REQUIRED"}
        if name == "policy-native-compile":
            result["process"] = {"pid": 4321, "parentPid": 1234,
                "popenReturnedMonotonicNs": started, "popenReturnedEpochNs": 1700000000000000000,
                "waitReturnedMonotonicNs": self.clock, "waitReturnedEpochNs": 1700000000000000001}
            if code == 0:
                self.file(self.library, self.artifact_bytes, 0o600)
        if name in self.after_observation:
            self.after_observation[name]()
        return result, stdout, stderr

    def prepare(self):
        self.prepared = self.prepare_impl()
        return self.prepared

    def run_target(self, code, *, duration_seconds=1, after_wait=None):
        self.gradle_child = Mock()

        def wait(*, timeout):
            self.case.assertGreater(timeout, 0)
            self.clock += duration_seconds * M.NS
            if after_wait is not None:
                after_wait()
            return code

        self.gradle_child.wait.side_effect = wait
        self.target_launch = Mock(return_value=self.gradle_child)
        with patch.object(M, "Driver", return_value=self.driver) as constructor, \
                patch.object(M.subprocess, "Popen", self.target_launch):
            self.constructor = constructor
            return M.target(self.c)


class PolicyNativeDriverControls(unittest.TestCase):
    """Offline flow, byte custody and bounds only; no compiler/owner/native qualification."""

    FILE_KEYS = {"path", "identity", "mode", "uid", "nlink", "size", "sha256", "mtimeNs", "ctimeNs"}
    RECORD_KEYS = {"schema", "scope", "requestSha256", "request", "github", "invocationId", "jobId",
        "candidateRoot", "controllerRoot", "javaHome", "architecture", "developerDir", "sdk", "sourceGitBlob",
        "startedMonotonicNs", "endedMonotonicNs", "status", "reason", "inputs", "observations", "compiler", "artifact"}
    INPUT_LIMITS = {"source": 256 * 1024, "clang": 512 * 1024 * 1024, "jniHeader": 1024 * 1024,
        "jniPlatformHeader": 1024 * 1024, "dnsSdHeader": 1024 * 1024, "linkerStub": 1024 * 1024, "javaRelease": 16384}
    FILE_ROLES = {"source": "SOURCE", "clang": "CLANG", "jniHeader": "JNI_HEADER",
        "jniPlatformHeader": "JNI_PLATFORM_HEADER", "dnsSdHeader": "DNS_SD_HEADER",
        "linkerStub": "LINKER_STUB", "javaRelease": "JAVA_RELEASE", "dylib": "DYLIB"}
    FILE_PREDICATES = frozenset({"TYPE", "LINKS", "OWNER", "WRITE", "NONPOSITIVE", "STAT_LIMIT", "READ_LIMIT"})
    OWNER_LINK_CODES = {"dnsSdHeader": "JMDNS_POLICY_FILE_DNS_SD_HEADER_OWNER_LINKS",
                        "linkerStub": "JMDNS_POLICY_FILE_LINKER_STUB_OWNER_LINKS"}
    SDK_INPUTS = frozenset({"dnsSdHeader", "linkerStub"})
    PROCESS_KEYS = {"pid", "parentPid", "popenReturnedMonotonicNs", "popenReturnedEpochNs",
                    "waitReturnedMonotonicNs", "waitReturnedEpochNs"}

    def changed_stat(self, info, **changed):
        fields = {name: getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink",
                                                       "st_size", "st_mtime_ns", "st_ctime_ns")}
        return SimpleNamespace(**{**fields, **changed})

    @contextmanager
    def policy_owner_frame(self, model, owners):
        """Real tiny fixture bytes/links; synthetic root versus distinct job UID only."""
        real_fstat, real_lstat = os.fstat, Path.lstat
        by_inode = {}
        for path, owner in owners.items():
            self.assertTrue(path.is_relative_to(model.base))
            info = real_lstat(path)
            by_inode[(info.st_dev, info.st_ino)] = owner

        def owned(info):
            return self.changed_stat(info, st_uid=by_inode.get((info.st_dev, info.st_ino), 1001))

        def owned_lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            return owned(info) if path.is_relative_to(model.base) else info

        with patch.object(M.os, "getuid", return_value=1001), \
                patch.object(M.os, "fstat", side_effect=lambda fd: owned(real_fstat(fd))), \
                patch.object(M.Path, "lstat", owned_lstat):
            yield

    def assert_no_target_record(self, model):
        model.driver.record.assert_not_called()
        self.assertFalse(model.target_record.exists())

    def policy_stream_probe(self, calls, streams, before_read=None):
        real_fdopen = os.fdopen

        class Probe:
            def __init__(self, fd, mode):
                self.stream = real_fdopen(fd, mode)
                streams.append(self.stream)

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                calls.append("close")
                self.stream.close()

            def fileno(self):
                calls.append("fileno")
                return self.stream.fileno()

            def read(self, size):
                calls.append(("read", size))
                if before_read is not None:
                    before_read()
                return self.stream.read(size)

        return Probe

    def test_policy_file_role_predicate_map_is_closed_and_spoof_resistant(self):
        self.assertIs(type(M.POLICY_FILE_ROLES), dict)
        self.assertEqual(M.POLICY_FILE_ROLES, self.FILE_ROLES)
        self.assertIs(type(M.POLICY_FILE_PREDICATES), frozenset)
        self.assertEqual(M.POLICY_FILE_PREDICATES, self.FILE_PREDICATES)
        codes = set()
        for role, label in self.FILE_ROLES.items():
            for predicate in self.FILE_PREDICATES:
                expected = "JMDNS_POLICY_FILE_" + label + "_" + predicate
                actual = M.policy_file_failure_code(role, predicate)
                self.assertIs(type(actual), str)
                self.assertEqual(actual, expected)
                codes.add(actual)
        self.assertEqual(len(codes), 56)
        for role, expected in self.OWNER_LINK_CODES.items():
            actual = M.policy_file_failure_code(role, "OWNER_LINKS")
            self.assertIs(type(actual), str)
            self.assertEqual(actual, expected)
            self.assertNotIn(actual, codes)
            codes.add(actual)
        self.assertEqual(len(codes), 58)
        for role in self.FILE_ROLES.keys() - self.OWNER_LINK_CODES.keys():
            self.assertEqual(M.policy_file_failure_code(role, "OWNER_LINKS"), "JMDNS_POLICY_FILE_TYPE_OR_BOUND")
        attempts = []

        def forbidden(*_args, **_kwargs):
            attempts.append("untrusted diagnostic hook")
            raise AssertionError("synthetic forbidden role or predicate inspection")

        class Poison:
            __str__ = __repr__ = __hash__ = __eq__ = __ne__ = __bool__ = forbidden

        class PoisonString(str):
            __str__ = __repr__ = __hash__ = __eq__ = __ne__ = __bool__ = forbidden

        bad = (None, 1, [], {}, Poison(), PoisonString("source"), PoisonString("TYPE"),
               PoisonString("dnsSdHeader"), PoisonString("linkerStub"), PoisonString("OWNER_LINKS"),
               "SOURCE", "source\n", "write", "TYPE\n", "OWNER_LINKS\n", "owner_links",
               "JMDNS_POLICY_FILE_SOURCE_TYPE", "/synthetic/private")
        for index, value in enumerate(bad):
            with self.subTest(case=index):
                self.assertEqual(M.policy_file_failure_code(value, "TYPE"), "JMDNS_POLICY_FILE_TYPE_OR_BOUND")
                self.assertEqual(M.policy_file_failure_code("source", value), "JMDNS_POLICY_FILE_TYPE_OR_BOUND")
                self.assertEqual(M.policy_file_failure_code(value, "OWNER_LINKS"), "JMDNS_POLICY_FILE_TYPE_OR_BOUND")
                for role in self.OWNER_LINK_CODES:
                    self.assertEqual(M.policy_file_failure_code(role, value), "JMDNS_POLICY_FILE_TYPE_OR_BOUND")
        self.assertEqual(attempts, [])

    def test_policy_file_first_failure_preserves_guard_uid_and_io_order(self):
        order = ["st_mode", "st_nlink", "st_uid", "getuid", "st_mode", "st_size"]
        cases = (("TYPE", {"st_mode": stat.S_IFDIR | 0o666, "st_nlink": 2, "st_uid": 3003, "st_size": 0}, 1),
                 ("LINKS", {"st_mode": stat.S_IFREG | 0o666, "st_nlink": 2, "st_uid": 3003, "st_size": 0}, 2),
                 ("OWNER", {"st_mode": stat.S_IFREG | 0o666, "st_uid": 3003, "st_size": 0}, 4),
                 ("WRITE", {"st_mode": stat.S_IFREG | 0o666, "st_size": 0}, 5),
                 ("NONPOSITIVE", {"st_size": 0}, 6), ("STAT_LIMIT", {"st_size": 9}, 6))
        original_classifier = M.policy_file_failure_code
        with SyntheticPolicyFrame(self) as model:
            path = model.paths["source"]
            for role, label in self.FILE_ROLES.items():
                role_cases = [(False, *case) for case in cases]
                if role in self.SDK_INPUTS:
                    role_cases += [
                        (True, "TYPE", {"st_mode": stat.S_IFDIR | 0o666, "st_nlink": 2,
                                        "st_uid": 1001, "st_size": 0}, 1),
                        (True, "LINKS", {"st_mode": stat.S_IFREG | 0o666, "st_nlink": 0,
                                         "st_uid": 1001, "st_size": 0}, 2),
                        (True, "OWNER", {"st_mode": stat.S_IFREG | 0o666, "st_nlink": 2,
                                         "st_uid": 3003, "st_size": 0}, 4),
                        (True, "WRITE", {"st_mode": stat.S_IFREG | 0o666, "st_nlink": 2,
                                         "st_uid": 1001, "st_size": 0}, 5),
                        (True, "NONPOSITIVE", {"st_nlink": 2, "st_uid": 1001, "st_size": 0}, 6),
                        (True, "STAT_LIMIT", {"st_nlink": 2, "st_uid": 1001, "st_size": 9}, 6),
                    ]
                for sdk_input, predicate, changed, seen in role_cases:
                    with self.subTest(role=role, sdk_input=sdk_input, predicate=predicate):
                        events, calls, streams = [], [], []
                        values = {"st_mode": stat.S_IFREG | 0o644, "st_nlink": 1, "st_uid": 1001,
                                  "st_size": 1, **changed}

                        class LazyGuardStat:
                            def __getattr__(self, name):
                                events.append(name)
                                return values[name]

                        def current_uid():
                            events.append("getuid")
                            return 1001

                        def classify(actual_role, actual_predicate):
                            events.append("classify")
                            return original_classifier(actual_role, actual_predicate)

                        probe = self.policy_stream_probe(calls, streams)
                        with patch.object(M.os, "fstat", return_value=LazyGuardStat()) as fstat, \
                                patch.object(M.os, "getuid", side_effect=current_uid) as uid, \
                                patch.object(M.os, "open", wraps=os.open) as opened, \
                                patch.object(M.os, "fdopen", probe), \
                                patch.object(M, "policy_file_failure_code", side_effect=classify) as classifier, \
                                self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_" + label + "_" + predicate + "$"):
                            model.driver.policy_file(path, 8, installed=True, sdk_input=sdk_input, role=role)
                        self.assertEqual(events, order[:seen] + ["classify"])
                        self.assertEqual(uid.call_count, int(seen >= 4))
                        self.assertEqual(fstat.call_count, 1)
                        self.assertEqual(calls, ["fileno", "close"])
                        self.assertEqual(len(streams), 1)
                        self.assertTrue(streams[0].closed)
                        opened.assert_called_once_with(path, os.O_RDONLY | os.O_NOFOLLOW)
                        classifier.assert_called_once_with(role, predicate)
            model.unexpected_launch.assert_not_called()

    def test_policy_file_owner_allowance_and_success_bytes_do_not_invoke_classifier(self):
        for installed, owner, allowed in ((False, 1001, True), (True, 1001, True), (True, 0, True),
                                           (False, 0, False), (True, 3003, False), (False, 3003, False)):
            with self.subTest(installed=installed, owner=owner), SyntheticPolicyFrame(self) as model:
                path, raw = model.paths["source"], model.input_bytes["source"]
                expected = {**model.policy_info(path, raw), "uid": owner}
                real_fstat, real_lstat = os.fstat, Path.lstat

                def owned_lstat(value, *args, **kwargs):
                    info = real_lstat(value, *args, **kwargs)
                    return self.changed_stat(info, st_uid=owner) if value == path else info

                with patch.object(M.os, "getuid", return_value=1001) as uid, \
                        patch.object(M.os, "fstat", side_effect=lambda fd: self.changed_stat(
                            real_fstat(fd), st_uid=owner)) as fstat, \
                        patch.object(M.Path, "lstat", owned_lstat), \
                        patch.object(M, "policy_file_failure_code", wraps=M.policy_file_failure_code) as classifier:
                    role = "clang" if installed else "source"
                    if allowed:
                        plain = model.driver.policy_file(path, 256 * 1024, installed=installed, capture=True)
                        annotated = model.driver.policy_file(path, 256 * 1024, installed=installed,
                                                             capture=True, role=role)
                        self.assertEqual(plain, (expected, raw))
                        self.assertEqual(annotated, plain)
                        self.assertEqual(set(annotated[0]), self.FILE_KEYS)
                        classifier.assert_not_called()
                        self.assertEqual((uid.call_count, fstat.call_count), (2, 4))
                    else:
                        with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_" + self.FILE_ROLES[role] + "_OWNER$"):
                            model.driver.policy_file(path, 256 * 1024, installed=installed, role=role)
                        classifier.assert_called_once_with(role, "OWNER")
                        self.assertEqual((uid.call_count, fstat.call_count), (1, 1))
                model.unexpected_launch.assert_not_called()

    def test_policy_file_actual_synthetic_growth_reaches_read_limit_without_extra_reads(self):
        cases = (("source", None), (None, None)) + tuple(
            (name, owner) for name in sorted(self.SDK_INPUTS) for owner in (0, 1001))
        for role, owner in cases:
            with self.subTest(role=role, owner=owner), SyntheticPolicyFrame(self) as model:
                path, initial, growth, limit = model.base / "growing-input", b"seed", b"growth", 8
                sdk_input = role in self.SDK_INPUTS
                if sdk_input:
                    path = model.paths[role]
                model.file(path, initial)
                if sdk_input:
                    os.link(path, model.base / "sdk-alias")
                    model.stack.enter_context(self.policy_owner_frame(model, {path: owner}))
                self.assertEqual(path.lstat().st_nlink, 2 if sdk_input else 1)
                # Isolate explicit reader I/O from the controller's separately
                # covered physical-path walk; this is still a real tiny temp file.
                model.c.physical.side_effect = lambda value: Path(value)
                calls, streams, sizes, lstats, growth_calls = [], [], [], [], []
                real_fstat, real_lstat = os.fstat, Path.lstat
                checksum = Mock(wraps=hashlib.sha256())

                def grow():
                    self.assertEqual(growth_calls, [])
                    growth_calls.append("append")
                    with path.open("ab") as writer:
                        self.assertEqual(writer.write(growth), len(growth))

                def original_stat(fd):
                    info = real_fstat(fd)
                    sizes.append(info.st_size)
                    return info

                def final_lstat(value, *args, **kwargs):
                    lstats.append(value)
                    return real_lstat(value, *args, **kwargs)

                probe = self.policy_stream_probe(calls, streams, grow)
                expected = ("JMDNS_POLICY_FILE_" + self.FILE_ROLES[role] + "_READ_LIMIT"
                            if role else "JMDNS_POLICY_FILE_TYPE_OR_BOUND")
                with patch.object(M.os, "fstat", side_effect=original_stat), \
                        patch.object(M.os, "open", wraps=os.open) as opened, \
                        patch.object(M.os, "fdopen", probe), patch.object(M.Path, "lstat", final_lstat), \
                        patch.object(M.hashlib, "sha256", return_value=checksum), \
                        patch.object(M, "policy_file_failure_code", wraps=M.policy_file_failure_code) as classifier, \
                        self.assertRaisesRegex(M.DriverError, "^" + expected + "$"):
                    model.driver.policy_file(path, limit, installed=sdk_input, sdk_input=sdk_input,
                                             capture=True, role=role)
                self.assertEqual(sizes, [len(initial)])
                self.assertLessEqual(sizes[0], limit)  # STAT_LIMIT was genuinely admitted.
                self.assertEqual(path.read_bytes(), initial + growth)
                self.assertEqual(calls, ["fileno", ("read", limit + 1), "close"])
                self.assertEqual(growth_calls, ["append"])
                self.assertEqual(lstats, [])  # No final identity query after overflow.
                self.assertEqual(len(streams), 1)
                self.assertTrue(streams[0].closed)
                opened.assert_called_once_with(path, os.O_RDONLY | os.O_NOFOLLOW)
                classifier.assert_called_once_with(role, "READ_LIMIT")
                checksum.update.assert_not_called()
                checksum.hexdigest.assert_not_called()
                model.unexpected_launch.assert_not_called()

    def test_policy_file_roles_cover_all_initial_reread_artifact_and_verification_calls(self):
        cases = ((code, owner) for code in (0, 7) for owner in (None, 0, 1001))
        for compile_code, sdk_owner in cases:
            with self.subTest(compile_code=compile_code, sdk_owner=sdk_owner), \
                    SyntheticPolicyFrame(self, compile_code=compile_code) as model:
                if sdk_owner is not None:
                    owners = {model.paths[name]: sdk_owner for name in self.SDK_INPUTS}
                    for name in self.SDK_INPUTS:
                        os.link(model.paths[name], model.base / (name + "-alias"))
                    model.stack.enter_context(self.policy_owner_frame(model, owners))
                prepared = model.driver.prepare_policy_native()
                inputs = [(model.paths[name], limit) for name, limit in self.INPUT_LIMITS.items()]
                calls = model.driver.policy_file.call_args_list
                self.assertEqual([call.args for call in calls], inputs * 2 +
                                 ([(model.library, 1024 * 1024)] if compile_code == 0 else []))
                before = [{"installed": name != "source", "capture": name in ("source", "javaRelease"),
                           "sdk_input": name in self.SDK_INPUTS, "role": name} for name in self.INPUT_LIMITS]
                after = [{"installed": name != "source", "sdk_input": name in self.SDK_INPUTS,
                          "role": name} for name in self.INPUT_LIMITS]
                self.assertEqual([call.kwargs for call in calls], before + after +
                                 ([{"role": "dylib"}] if compile_code == 0 else []))
                prepared_count = len(calls)
                model.driver.verify_policy_native(prepared, 19)
                verified = model.driver.policy_file.call_args_list[prepared_count:]
                self.assertEqual([call.args for call in verified], [(model.paths["source"], 256 * 1024)] +
                                 ([(model.library, 1024 * 1024)] if compile_code == 0 else []))
                self.assertEqual([call.kwargs for call in verified], [{"role": "source"}] +
                                 ([{"role": "dylib"}] if compile_code == 0 else []))
                self.assertEqual(set(prepared["record"]), self.RECORD_KEYS)
                for name, info in prepared["record"]["inputs"].items():
                    self.assertEqual(set(info), self.FILE_KEYS)
                    self.assertEqual(info, model.policy_info(model.paths[name], model.input_bytes[name]))
                    if sdk_owner is not None:
                        self.assertEqual((info["uid"], info["nlink"]),
                            (sdk_owner, 2) if name in self.SDK_INPUTS else (1001, 1))
                self.assertEqual(prepared["raw"], encoded(prepared["record"]))
                self.assertEqual(model.original_record.read_bytes(), prepared["raw"])
                self.assertEqual(model.consumer_record.read_bytes(), prepared["raw"])
                model.unexpected_launch.assert_not_called()

    def test_sdk_root_hardlinks_preserve_bounded_bytes_and_single_link_behavior(self):
        for name in sorted(self.SDK_INPUTS):
            for links, owner in ((2, 0), (2, 1001), (1, 0), (1, 1001)):
                with self.subTest(input=name, links=links, owner=owner), SyntheticPolicyFrame(self) as model:
                    path, raw = model.paths[name], model.input_bytes[name]
                    if links == 2:
                        os.link(path, model.base / "sdk-alias")
                    self.assertEqual(path.lstat().st_nlink, links)
                    with self.policy_owner_frame(model, {path: owner}):
                        expected = model.policy_info(path, raw)
                        calls, streams = [], []
                        probe = self.policy_stream_probe(calls, streams)
                        with patch.object(M.os, "fdopen", probe), \
                                patch.object(M.os, "getuid", return_value=1001) as uid, \
                                patch.object(M, "policy_file_failure_code", wraps=M.policy_file_failure_code) as classifier:
                            info, captured = model.driver.policy_file(path, len(raw) + 4,
                                installed=True, sdk_input=True, capture=True, role=name)
                        self.assertEqual((info, captured), (expected, raw))
                        self.assertEqual((info["uid"], info["nlink"]), (owner, links))
                        self.assertEqual(calls, ["fileno", ("read", len(raw) + 5), ("read", 5), "fileno", "close"])
                        self.assertEqual(len(streams), 1)
                        self.assertTrue(streams[0].closed)
                        uid.assert_called_once_with()
                        classifier.assert_not_called()
                        if links == 1:
                            self.assertEqual(model.driver.policy_file(path, len(raw) + 4,
                                installed=True, capture=True, role=name), (info, captured))
                    model.unexpected_launch.assert_not_called()

    def test_sdk_hardlink_refusals_preserve_guards_before_byte_reads(self):
        cases = (("installed-only", True, False, 0, {}, "LINKS"),
                 ("sdk-without-installed", False, True, 0, {}, "LINKS"),
                 ("zero-links", True, True, 0, {"st_nlink": 0}, "LINKS"),
                 ("negative-links", True, True, 0, {"st_nlink": -1}, "LINKS"),
                 ("other-owner", True, True, 3003, {}, "OWNER"),
                 ("other-owner-single", True, True, 3003, {}, "OWNER"),
                 ("type", True, True, 0, {"st_mode": stat.S_IFDIR | 0o644}, "TYPE"),
                 ("group-write", True, True, 0, {"st_mode": stat.S_IFREG | 0o664}, "WRITE"),
                 ("world-write", True, True, 0, {"st_mode": stat.S_IFREG | 0o646}, "WRITE"),
                 ("empty", True, True, 0, {"st_size": 0}, "NONPOSITIVE"),
                 ("oversize", True, True, 0, {"st_size": 257}, "STAT_LIMIT"))
        # Both admitted owners must still reach every later refusal, while
        # either missing capability must reject the multilink before ownership.
        cases += tuple((case, installed, sdk_input, 1001, changed, predicate)
                       for case, installed, sdk_input, owner, changed, predicate in cases if owner == 0)
        for name in sorted(self.SDK_INPUTS):
            for case, installed, sdk_input, owner, changed, predicate in cases:
                with self.subTest(input=name, case=case, owner=owner), SyntheticPolicyFrame(self) as model:
                    path = model.paths[name]
                    if case != "other-owner-single":
                        os.link(path, model.base / "sdk-alias")
                    self.assertEqual(path.lstat().st_nlink, 1 if case == "other-owner-single" else 2)
                    with self.policy_owner_frame(model, {path: owner}):
                        owned_fstat = os.fstat
                        calls, streams = [], []
                        probe = self.policy_stream_probe(calls, streams)
                        with patch.object(M.os, "fstat", side_effect=lambda fd: self.changed_stat(
                                owned_fstat(fd), **changed)) as fstat, patch.object(M.os, "fdopen", probe), \
                                patch.object(M.os, "getuid", return_value=1001) as uid, \
                                patch.object(M, "policy_file_failure_code", wraps=M.policy_file_failure_code) as classifier, \
                                self.assertRaisesRegex(M.DriverError,
                                    "^JMDNS_POLICY_FILE_" + self.FILE_ROLES[name] + "_" + predicate + "$"):
                            model.driver.policy_file(path, 256, installed=installed, sdk_input=sdk_input, role=name)
                        self.assertEqual(fstat.call_count, 1)
                        self.assertEqual(uid.call_count, int(predicate not in ("TYPE", "LINKS")))
                        classifier.assert_called_once_with(name, predicate)
                        self.assertEqual(calls, ["fileno", "close"])
                        self.assertEqual(len(streams), 1)
                        self.assertTrue(streams[0].closed)
                    model.unexpected_launch.assert_not_called()
            for owner in (0, 1001):
                with self.subTest(input=name, case="deadline", owner=owner), SyntheticPolicyFrame(self) as model:
                    path = model.paths[name]
                    os.link(path, model.base / "sdk-alias")
                    with self.policy_owner_frame(model, {path: owner}):
                        calls, streams = [], []
                        with patch.object(M.os, "fdopen", self.policy_stream_probe(calls, streams)), \
                                patch.object(M.os, "fstat", wraps=os.fstat) as fstat, \
                                patch.object(M.os, "getuid", return_value=1001) as uid, \
                                patch.object(M, "policy_file_failure_code", wraps=M.policy_file_failure_code) as classifier, \
                                patch.object(M.time, "monotonic_ns", side_effect=[101 * M.NS, 106 * M.NS]), \
                                self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_HASH_TIMEOUT$"):
                            model.driver.policy_file(path, 256, installed=True, sdk_input=True, role=name)
                        self.assertEqual(calls, ["fileno", "close"])
                        self.assertEqual(len(streams), 1)
                        self.assertTrue(streams[0].closed)
                        self.assertEqual(fstat.call_count, 1)
                        uid.assert_called_once_with()
                        classifier.assert_not_called()
                        model.clock = 216 * M.NS + 1
                        with patch.object(M.os, "open") as opened:
                            self.assertEqual(model.driver.policy_file(path, 256,
                                installed=True, sdk_input=True, role=name), (None, None))
                        opened.assert_not_called()

    def test_sdk_hardlinks_retain_full_stat_and_canonical_path_stability(self):
        cases = ((name, owner) for name in sorted(self.SDK_INPUTS) for owner in (0, 1001))
        for name, owner in cases:
            for field in ("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"):
                with self.subTest(input=name, owner=owner, field=field), SyntheticPolicyFrame(self) as model:
                    path = model.paths[name]
                    os.link(path, model.base / "sdk-alias")
                    with self.policy_owner_frame(model, {path: owner}):
                        before = path.lstat()
                        after = self.changed_stat(before, **{field: getattr(before, field) + 1})
                        with patch.object(M.os, "fstat", side_effect=[before, after]), \
                                self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_CHANGED$"):
                            model.driver.policy_file(path, 256, installed=True, sdk_input=True, role=name)
            for change in ("path-inode", "canonical-path"):
                with self.subTest(input=name, owner=owner, changed=change), SyntheticPolicyFrame(self) as model:
                    path = model.paths[name]
                    os.link(path, model.base / "sdk-alias")
                    with self.policy_owner_frame(model, {path: owner}), ExitStack() as stack:
                        real_lstat, real_resolve = Path.lstat, Path.resolve
                        if change == "path-inode":
                            def replaced_lstat(value, *args, **kwargs):
                                info = real_lstat(value, *args, **kwargs)
                                return self.changed_stat(info, st_ino=info.st_ino + 1) if value == path else info
                            stack.enter_context(patch.object(M.Path, "lstat", replaced_lstat))
                        else:
                            resolutions = iter((path, model.base / "different-canonical-input"))

                            def changed_resolution(value, *args, **kwargs):
                                return next(resolutions) if value == path else real_resolve(value, *args, **kwargs)
                            stack.enter_context(patch.object(M.Path, "resolve", changed_resolution))
                        with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_CHANGED$"):
                            model.driver.policy_file(path, 256, installed=True, sdk_input=True, role=name)

    def test_sdk_capability_is_closed_to_two_admitted_paths_on_both_passes(self):
        with SyntheticPolicyFrame(self) as model:
            owners = {model.paths[name]: 0 for name in self.SDK_INPUTS}
            for name in self.SDK_INPUTS:
                os.link(model.paths[name], model.base / (name + "-alias"))
            with self.policy_owner_frame(model, owners):
                prepared = model.driver.prepare_policy_native()
                for name, info in prepared["record"]["inputs"].items():
                    self.assertEqual(info, model.policy_info(model.paths[name], model.input_bytes[name]))
                    self.assertEqual((info["uid"], info["nlink"]), (0, 2) if name in self.SDK_INPUTS else (1001, 1))
                model.driver.verify_policy_native(prepared, 19)
                calls = model.driver.policy_file.call_args_list
                self.assertEqual(len(calls), 17)
                admitted = [call for call in calls if call.kwargs.get("sdk_input", False)]
                self.assertEqual([call.args[0] for call in admitted],
                    [model.paths["dnsSdHeader"], model.paths["linkerStub"]] * 2)
                self.assertTrue(all(call.kwargs["installed"] is True for call in admitted))
                self.assertEqual(prepared["record"]["artifact"]["nlink"], 1)
                self.assertEqual(model.original_record.read_bytes(), prepared["raw"])
                self.assertEqual(model.consumer_record.read_bytes(), prepared["raw"])
            model.unexpected_launch.assert_not_called()
        for name in sorted(self.SDK_INPUTS):
            for location in ("outside-sdk", "sibling-sdk"):
                with self.subTest(input=name, location=location), SyntheticPolicyFrame(self) as model:
                    root = model.base if location == "outside-sdk" else model.sdk.parent / "Sibling.sdk"
                    outside = root / "unadmitted-input"
                    model.file(outside, model.input_bytes[name])
                    os.link(outside, model.base / "outside-alias")
                    logical = model.paths[name] if name == "dnsSdHeader" else model.system_stub
                    logical.unlink()
                    logical.symlink_to(outside)
                    with self.policy_owner_frame(model, {outside: 0}), \
                            self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_SELECTED_TOOLCHAIN$"):
                        model.driver.prepare_policy_native()
                    model.driver.policy_file.assert_not_called()
                    self.assertNotIn("policy-native-compile", model.started_commands)
                    model.unexpected_launch.assert_not_called()
        for name in sorted(set(self.FILE_ROLES) - self.SDK_INPUTS):
            with self.subTest(strict_input=name), SyntheticPolicyFrame(self) as model:
                path = model.library if name == "dylib" else model.paths[name]
                if name == "dylib":
                    model.after_observation["policy-native-compile"] = lambda: os.link(path, model.base / "strict-alias")
                    owners = {}
                else:
                    os.link(path, model.base / "strict-alias")
                    owners = {path: 0}
                with self.policy_owner_frame(model, owners), self.assertRaisesRegex(M.DriverError,
                        "^JMDNS_POLICY_FILE_" + self.FILE_ROLES[name] + "_LINKS$"):
                    model.driver.prepare_policy_native()
                refused = model.driver.policy_file.call_args_list[-1]
                self.assertEqual(refused.args[0], path)
                self.assertFalse(refused.kwargs.get("sdk_input", False))
                self.assertFalse(model.original_record.exists())
                self.assertFalse(model.consumer_record.exists())
                model.unexpected_launch.assert_not_called()

    def test_sdk_hardlinks_recheck_real_count_and_content_after_any_compiler_return(self):
        cases = tuple((name, owner) for name in sorted(self.SDK_INPUTS) for owner in (0, 1001))
        for code in (0, 7):
            for name, owner in cases:
                for change in ("links", "content"):
                    with self.subTest(code=code, input=name, owner=owner, change=change), \
                            SyntheticPolicyFrame(self, compile_code=code) as model:
                        path = model.paths[name]
                        os.link(path, model.base / "sdk-alias")

                        def mutate():
                            if change == "links":
                                os.link(path, model.base / "extra-sdk-alias")
                            else:
                                path.write_bytes(path.read_bytes() + b"synthetic changed input\n")

                        model.after_observation["policy-native-compile"] = mutate
                        with self.policy_owner_frame(model, {path: owner}), \
                                self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_COMPILER_INPUT_CHANGED$"):
                            model.driver.prepare_policy_native()
                        self.assertEqual(path.lstat().st_nlink, 3 if change == "links" else 2)
                        self.assertEqual(model.started_commands.count("policy-native-compile"), 1)
                        reread = model.driver.policy_file.call_args_list[-1]
                        self.assertEqual(reread.args[0], path)
                        self.assertTrue(reread.kwargs["installed"] and reread.kwargs["sdk_input"])
                        self.assertFalse(model.original_record.exists())
                        self.assertFalse(model.consumer_record.exists())
                        model.unexpected_launch.assert_not_called()

    def test_bounded_reader_streams_exact_stat_hash_capture_and_installed_root_data(self):
        with SyntheticPolicyFrame(self) as model:
            path = model.base / "stream-input"
            raw = b"s" * (1024 * 1024 + 7)
            model.file(path, raw)
            expected = model.policy_info(path, raw)
            reads = []
            real_fdopen = os.fdopen

            class Probe:
                def __init__(self, fd, mode):
                    self.stream = real_fdopen(fd, mode)

                def __enter__(self):
                    return self

                def __exit__(self, *_exc):
                    self.stream.close()

                def fileno(self):
                    return self.stream.fileno()

                def read(self, size):
                    reads.append(size)
                    return self.stream.read(size)

            with patch.object(M.os, "open", wraps=os.open) as opened, patch.object(M.os, "fdopen", Probe):
                info, captured = model.driver.policy_file(path, 512 * 1024 * 1024, installed=True)
            self.assertEqual(info, expected)
            self.assertEqual(set(info), self.FILE_KEYS)
            self.assertEqual(info["mode"], stat.S_IFREG | 0o644)
            self.assertIsNone(captured)
            self.assertGreaterEqual(len(reads), 3)
            self.assertTrue(all(0 < size <= 1024 * 1024 for size in reads))
            opened.assert_called_once_with(path, os.O_RDONLY | os.O_NOFOLLOW)
            source = model.paths["source"]
            info, captured = model.driver.policy_file(source, 256 * 1024, capture=True)
            self.assertEqual(captured, model.input_bytes["source"])
            self.assertEqual(info, model.policy_info(source, captured))

            # Root-owned installed input allowance is tested without chown or any
            # installed read, including when these controls themselves run as root.
            real_fstat, real_lstat = os.fstat, Path.lstat

            def root_lstat(path, *args, **kwargs):
                value = real_lstat(path, *args, **kwargs)
                return self.changed_stat(value, st_uid=0) if path == source else value

            with patch.object(M.os, "getuid", return_value=1001), \
                    patch.object(M.os, "fstat", side_effect=lambda fd: self.changed_stat(real_fstat(fd), st_uid=0)), \
                    patch.object(M.Path, "lstat", root_lstat):
                installed, _ = model.driver.policy_file(source, 256 * 1024, installed=True)
                self.assertEqual(installed["uid"], 0)
                with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_TYPE_OR_BOUND$"):
                    model.driver.policy_file(source, 256 * 1024)
            model.unexpected_launch.assert_not_called()

    def test_reader_refuses_nonphysical_unstable_unbounded_or_out_of_window_inputs(self):
        for change in ("symlink", "hardlink", "group-write", "world-write", "empty", "oversized", "type", "owner"):
            with self.subTest(change=change), SyntheticPolicyFrame(self) as model:
                path, limit = model.paths["source"], 256 * 1024
                with ExitStack() as stack:
                    reason = "JMDNS_POLICY_FILE_TYPE_OR_BOUND"
                    if change == "symlink":
                        alias = model.base / "alias"
                        alias.symlink_to(path)
                        path = alias
                        # Isolate the driver's canonical/nofollow guard from the
                        # separately mocked controller physical-path check.
                        model.c.physical.side_effect = lambda value: Path(value)
                        reason = "JMDNS_POLICY_FILE_CANONICAL"
                    elif change == "hardlink":
                        os.link(path, model.base / "hardlink")
                    elif change in ("group-write", "world-write"):
                        path.chmod(0o664 if change == "group-write" else 0o646)
                    elif change == "empty":
                        path.write_bytes(b"")
                    elif change == "oversized":
                        limit = len(model.input_bytes["source"]) - 1
                    else:
                        original = path.lstat()
                        altered = (self.changed_stat(original, st_mode=stat.S_IFDIR | 0o700) if change == "type"
                                   else self.changed_stat(original, st_uid=os.getuid() + 1))
                        stack.enter_context(patch.object(M.os, "fstat", return_value=altered))
                    with self.assertRaisesRegex(M.DriverError, "^" + reason + "$"):
                        model.driver.policy_file(path, limit, installed=True)
        for field in ("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"):
            with self.subTest(changed_fstat=field), SyntheticPolicyFrame(self) as model:
                path = model.paths["source"]
                original = path.lstat()
                after = self.changed_stat(original, **{field: getattr(original, field) + 1})
                with patch.object(M.os, "fstat", side_effect=[original, after]), \
                        self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_CHANGED$"):
                    model.driver.policy_file(path, 256 * 1024)
        with SyntheticPolicyFrame(self) as model:
            path = model.paths["source"]
            real_lstat, real_resolve = Path.lstat, Path.resolve
            model.c.physical.side_effect = lambda value: Path(value)

            def replaced_lstat(value, *args, **kwargs):
                info = real_lstat(value, *args, **kwargs)
                return self.changed_stat(info, st_ino=info.st_ino + 1) if value == path else info

            with patch.object(M.Path, "lstat", replaced_lstat), \
                    self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_CHANGED$"):
                model.driver.policy_file(path, 256 * 1024)
            resolutions = iter((path, model.base / "different-identity"))

            def changed_resolution(value, *args, **kwargs):
                return next(resolutions) if value == path else real_resolve(value, *args, **kwargs)

            with patch.object(M.Path, "resolve", changed_resolution), \
                    self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_FILE_CHANGED$"):
                model.driver.policy_file(path, 256 * 1024)
            with patch.object(M.os, "open") as opened, \
                    self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_CAPTURE_BOUND$"):
                model.driver.policy_file(path, 1024 * 1024 + 1, capture=True)
            opened.assert_not_called()
            model.c.physical.reset_mock()
            model.clock = 216 * M.NS + 1  # Not even one whole fixed hash5 remains.
            with patch.object(M.os, "open") as opened:
                self.assertEqual(model.driver.policy_file(path, 256 * 1024), (None, None))
            opened.assert_not_called()
            model.c.physical.assert_not_called()
        for stage, ticks in (("before-read", [101, 106]), ("after-read", [101, 101, 106]),
                             ("final-check", [101, 101, 101, 101, 101, 106])):
            with self.subTest(deadline=stage), SyntheticPolicyFrame(self) as model, \
                    patch.object(M.time, "monotonic_ns", side_effect=[tick * M.NS for tick in ticks]), \
                    self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_HASH_TIMEOUT$"):
                model.driver.policy_file(model.paths["source"], 256 * 1024)

    def test_preparation_binds_fixed_commands_all_inputs_and_identical_original_copies(self):
        self.assertEqual((M.POLICY_SCOPE, M.POLICY_SOURCE, M.POLICY_REPORTS, M.POLICY_LIBRARY, M.POLICY_DEVELOPER),
            ("MANUAL_JMDNS_POLICY_COMPILE_V1", SyntheticPolicyFrame.SOURCE, SyntheticPolicyFrame.REPORTS,
             SyntheticPolicyFrame.LIBRARY, SyntheticPolicyFrame.DEVELOPER))
        self.assertEqual(M.POLICY_INPUT_LIMITS, self.INPUT_LIMITS)
        self.assertEqual((M.POLICY_LIBRARY_LIMIT, M.POLICY_RECORD_LIMIT), (1024 * 1024, 256 * 1024))
        self.assertEqual((M.POLICY_COMPILE_SECONDS, M.POLICY_QUERY_SECONDS, M.POLICY_HASH_SECONDS), (30, 5, 5))
        for optional_absent in (False, True):
            with self.subTest(optional_absent=optional_absent), SyntheticPolicyFrame(self) as model:
                if optional_absent:
                    model.not_returned.update({"policy-dylibSignature": "NATIVE_COMMAND_UNAVAILABLE",
                                               "policy-dylibUuid": "OBSERVATION_BUDGET_NOT_ADMITTED"})
                prepared = model.driver.prepare_policy_native()
                record, raw = prepared["record"], prepared["raw"]
                self.assertEqual(set(prepared), {"record", "raw", "copies"})
                self.assertEqual(set(record), self.RECORD_KEYS)
                self.assertEqual((record["schema"], record["scope"], record["architecture"]),
                                 (1, "MANUAL_JMDNS_POLICY_COMPILE_V1", "arm64"))
                self.assertEqual((record["status"], record["reason"]),
                                 ("COMPILED", "READY_FOR_FAILURE_ONLY_DIAGNOSTIC"))
                self.assertEqual((record["request"], record["github"], record["requestSha256"]),
                                 (model.request["request"], model.request["github"], digest(model.request_path.read_bytes())))
                self.assertEqual((record["invocationId"], record["jobId"]), ("a" * 32, "b" * 32))
                self.assertEqual((record["candidateRoot"], record["controllerRoot"], record["javaHome"], record["sdk"]),
                                 tuple(map(str, (model.candidate, model.root, model.java_home, model.sdk))))
                self.assertEqual(record["developerDir"], "/Applications/Xcode_26.5.app/Contents/Developer")
                self.assertEqual(record["sourceGitBlob"], model.blob)
                self.assertEqual(set(record["inputs"]), set(self.INPUT_LIMITS))
                for name, path in model.paths.items():
                    self.assertEqual(set(record["inputs"][name]), self.FILE_KEYS)
                    self.assertEqual(record["inputs"][name], model.policy_info(path, model.input_bytes[name]))
                self.assertEqual(set(record["artifact"]), self.FILE_KEYS)
                self.assertEqual(record["artifact"], model.policy_info(model.library, model.artifact_bytes))
                self.assertEqual(model.library.read_bytes(), b"SYNTHETIC NON-DYLIB; offline driver flow DATA only\n")
                self.assertEqual((record["startedMonotonicNs"], record["endedMonotonicNs"]), (101 * M.NS, 101 * M.NS))
                self.assertEqual(set(record["observations"]), {"findClang", "findSdk", "clangVersion", "dylibSignature", "dylibUuid"})
                if optional_absent:
                    self.assertEqual(record["observations"]["dylibSignature"]["status"], "INCONCLUSIVE")
                    self.assertEqual(record["observations"]["dylibUuid"]["status"], "INCONCLUSIVE")
                self.assertEqual(set(record["compiler"]["process"]), self.PROCESS_KEYS)
                expected_commands = [
                    ("policy-find-clang", ["/usr/bin/xcrun", "--sdk", "macosx", "--find", "clang"], 5, 16384),
                    ("policy-find-sdk", ["/usr/bin/xcrun", "--sdk", "macosx", "--show-sdk-path"], 5, 16384),
                    ("policy-clang-version", [str(model.clang), "--version"], 5, 16384),
                    ("policy-native-compile", model.compiler_argv(), 30, 1024 * 1024),
                    ("policy-dylibSignature", ["/usr/bin/codesign", "-d", "--verbose=4", str(model.library)], 5, 65536),
                    ("policy-dylibUuid", ["/usr/bin/xcrun", "dwarfdump", "--uuid", str(model.library)], 5, 65536)]
                self.assertEqual([call.args for call in model.driver.observe_command.call_args_list], expected_commands)
                self.assertEqual(model.started_commands.count("policy-native-compile"), 1)
                model.driver.runner.git.assert_called_once_with(model.candidate, "ls-files", "--stage", "--", SyntheticPolicyFrame.SOURCE)
                self.assertEqual(len(model.driver.policy_file.call_args_list), 15)  # Seven before + seven after + artifact.
                for call in model.driver.policy_file.call_args_list[:7]:
                    name = next(key for key, path in model.paths.items() if path == call.args[0])
                    self.assertEqual(call.args[1], self.INPUT_LIMITS[name])
                    self.assertEqual(call.kwargs, {"installed": name != "source",
                        "sdk_input": name in self.SDK_INPUTS, "capture": name in ("source", "javaRelease"), "role": name})
                self.assertEqual(raw, encoded(record))
                self.assertLessEqual(len(raw), 256 * 1024)
                self.assertEqual(model.original_record.read_bytes(), raw)
                self.assertEqual(model.consumer_record.read_bytes(), raw)
                copies = {str(model.directory / ("compiler." + suffix + ".log")) for suffix in ("stdout", "stderr")}
                self.assertEqual(set(prepared["copies"]), copies)
                for suffix, expected_raw in zip(("stdout", "stderr"), model.outputs["policy-native-compile"]):
                    original = model.records / record["compiler"][suffix]["file"]
                    copied = model.directory / ("compiler." + suffix + ".log")
                    self.assertEqual(original.read_bytes(), expected_raw)
                    self.assertEqual(copied.read_bytes(), expected_raw)
                    self.assertEqual(prepared["copies"][str(copied)], model.read_file(copied)[1])
                    self.assertNotEqual(original.lstat().st_ino, copied.lstat().st_ino)
                for path in (model.directory.parent.parent, model.directory.parent, model.directory):
                    self.assertEqual((stat.S_IMODE(path.lstat().st_mode), path.lstat().st_uid, path.resolve(strict=True)),
                                     (0o700, os.getuid(), path))
                self.assertEqual([call.args[0] for call in model.c.write_new.call_args_list],
                    [model.directory / "compiler.stdout.log", model.directory / "compiler.stderr.log",
                     model.original_record, model.consumer_record])
                self.assertEqual(model.c.clean_source.call_count, 2)
                for call in model.c.clean_source.call_args_list:
                    self.assertEqual(call.args, (model.driver.runner, model.candidate, "e" * 40, "f" * 40))
                model.driver.verify_policy_native(prepared, 19)
                with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_OUTPUT_ALREADY_EXISTS$"):
                    model.driver.prepare_policy_native()
                self.assertEqual(model.started_commands.count("policy-native-compile"), 1)
                model.unexpected_launch.assert_not_called()

    def test_system_sdk_alias_retains_canonical_input_without_legacy_link_override(self):
        for legacy_decoy in (False, True):
            with self.subTest(legacy_decoy=legacy_decoy), SyntheticPolicyFrame(self) as model:
                canonical = model.paths["linkerStub"]
                legacy = model.sdk / "usr/lib/libdns_sd.tbd"
                self.assertTrue(model.system_stub.is_symlink())
                self.assertEqual(model.system_stub.readlink(), Path("libSystem.B.tbd"))
                self.assertEqual(model.system_stub.resolve(strict=True), canonical)
                self.assertTrue(canonical.is_file())
                self.assertFalse(canonical.is_symlink())
                self.assertFalse(os.path.lexists(legacy))
                if legacy_decoy:
                    model.file(legacy, b"SYNTHETIC legacy decoy, not the required linker input\n")
                prepared = model.driver.prepare_policy_native()
                record = prepared["record"]
                self.assertEqual(record["inputs"]["linkerStub"],
                                 model.policy_info(canonical, model.input_bytes["linkerStub"]))
                self.assertEqual(record["compiler"]["argv"], model.compiler_argv())
                self.assertNotIn("-ldns_sd", record["compiler"]["argv"])
                self.assertNotIn("-lSystem", record["compiler"]["argv"])
                reads = [call.args for call in model.driver.policy_file.call_args_list if call.args[0] == canonical]
                self.assertEqual(reads, [(canonical, 1024 * 1024), (canonical, 1024 * 1024)])
                self.assertFalse(any(call.args[0] in (model.system_stub, legacy)
                                     for call in model.driver.policy_file.call_args_list))
                self.assertEqual(model.original_record.read_bytes(), prepared["raw"])
                self.assertEqual(model.consumer_record.read_bytes(), prepared["raw"])
                model.unexpected_launch.assert_not_called()

    def test_required_system_input_missing_or_escaped_never_falls_back_to_legacy_decoy(self):
        for change in ("missing-logical", "missing-canonical", "sibling-sdk", "outside-sdk"):
            with self.subTest(change=change), SyntheticPolicyFrame(self) as model:
                legacy = model.sdk / "usr/lib/libdns_sd.tbd"
                model.file(legacy, b"SYNTHETIC legacy decoy, never an accepted fallback\n")
                if change == "missing-logical":
                    model.system_stub.unlink()
                elif change == "missing-canonical":
                    model.paths["linkerStub"].unlink()
                else:
                    other = ((model.sdk.parent / "Sibling.sdk") if change == "sibling-sdk" else
                             (model.base / "outside-sdk")) / "usr/lib/libSystem.B.tbd"
                    model.file(other, model.input_bytes["linkerStub"])
                    model.system_stub.unlink()
                    model.system_stub.symlink_to(other)
                if change.startswith("missing-"):
                    with self.assertRaises(FileNotFoundError):
                        model.driver.prepare_policy_native()
                else:
                    with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_SELECTED_TOOLCHAIN$"):
                        model.driver.prepare_policy_native()
                self.assertNotIn("policy-native-compile", model.started_commands)
                model.driver.policy_file.assert_not_called()
                self.assertFalse(model.original_record.exists())
                self.assertFalse(model.consumer_record.exists())
                self.assertFalse(model.library.exists())
                self.assertTrue(legacy.is_file())
                model.unexpected_launch.assert_not_called()

    def test_preparation_refuses_wrong_inputs_paths_source_stage_and_preexisting_namespace(self):
        cases = ("observer", "developer-env", "developer-canonical", "clang-outside", "sdk-outside", "sdk-file",
                 "dns-header-escape", "linker-stub-escape", "source-mode", "source-bytes", "stage-mode", "stage-blob",
                 "stage-index", "stage-duplicate", "version-vendor", "version-arch", "native-exists", "build-mode",
                 "reports-mode", "artifact-preexists", "record-bound", "compiler-output-bound", "artifact-bound")
        for change in cases:
            with self.subTest(change=change), SyntheticPolicyFrame(self) as model:
                reason, compiled = "JMDNS_POLICY_SELECTED_TOOLCHAIN", False
                if change == "observer":
                    model.driver.phase, reason = "observer", "JMDNS_POLICY_TARGET_ONLY"
                elif change == "developer-env":
                    model.env["DEVELOPER_DIR"] = "/not-selected-developer"
                elif change == "developer-canonical":
                    original_physical = model.physical
                    model.c.physical.side_effect = lambda path: (model.developer / "Toolchains/.."
                        if str(path) == model.DEVELOPER else original_physical(path))
                elif change in ("clang-outside", "sdk-outside", "sdk-file"):
                    if change == "clang-outside":
                        other, query = model.base / "other-clang", "policy-find-clang"
                        model.file(other, b"SYNTHETIC outside clang\n")
                    elif change == "sdk-outside":
                        other, query = model.base / "other-sdk", "policy-find-sdk"
                        other.mkdir(mode=0o700)
                    else:
                        other, query = model.sdk.parent / "not-a-directory.sdk", "policy-find-sdk"
                        model.file(other, b"SYNTHETIC SDK file\n")
                    model.outputs[query] = ((str(other) + "\n").encode("utf-8"), b"")
                elif change in ("dns-header-escape", "linker-stub-escape"):
                    path = model.paths["dnsSdHeader" if change == "dns-header-escape" else "linkerStub"]
                    other = model.base / "outside-sdk-input"
                    model.file(other, b"SYNTHETIC outside SDK\n")
                    path.unlink()
                    path.symlink_to(other)
                elif change in ("source-mode", "source-bytes", "stage-mode", "stage-blob", "stage-index", "stage-duplicate"):
                    reason = "JMDNS_POLICY_TRACKED_SOURCE"
                    if change == "source-mode":
                        model.paths["source"].chmod(0o600)
                    elif change == "source-bytes":
                        model.paths["source"].write_bytes(b"different source DATA\n")
                    else:
                        model.driver.runner.git.return_value = {
                            "stage-mode": model.staged.replace(b"100644 ", b"100755 ", 1),
                            "stage-blob": model.staged.replace(model.blob.encode("ascii"), b"0" * 40, 1),
                            "stage-index": model.staged.replace(b" 0\t", b" 1\t", 1),
                            "stage-duplicate": model.staged + model.staged}[change]
                elif change in ("version-vendor", "version-arch"):
                    reason = "JMDNS_POLICY_COMPILER_IDENTITY"
                    model.outputs["policy-clang-version"] = (
                        b"clang version SYNTHETIC\nTarget: arm64-apple-darwin\n" if change == "version-vendor" else
                        b"Apple clang version SYNTHETIC\nTarget: x86_64-apple-darwin\n", b"")
                elif change == "native-exists":
                    model.directory.mkdir(parents=True, mode=0o700)
                    reason = "JMDNS_POLICY_OUTPUT_ALREADY_EXISTS"
                elif change in ("build-mode", "reports-mode"):
                    model.directory.parent.parent.mkdir(mode=0o700)
                    bad_parent = model.directory.parent.parent
                    if change == "reports-mode":
                        model.directory.parent.mkdir(mode=0o700)
                        bad_parent = model.directory.parent
                    bad_parent.chmod(0o755)
                    reason = "JMDNS_POLICY_OUTPUT_DIRECTORY"
                elif change == "artifact-preexists":
                    model.after_observation["policy-clang-version"] = lambda: model.file(model.library, b"stale output\n")
                    reason = "JMDNS_POLICY_OUTPUT_ALREADY_EXISTS"
                elif change == "record-bound":
                    model.c.encoded.side_effect = lambda _value: b"x" * (256 * 1024 + 1)
                    reason, compiled = "JMDNS_POLICY_RECORD_BOUND", True
                elif change == "compiler-output-bound":
                    model.outputs["policy-native-compile"] = (b"x" * (1024 * 1024 + 1), b"")
                    reason, compiled = "JMDNS_POLICY_COMPILER_OUTPUT_BOUND", True
                elif change == "artifact-bound":
                    model.artifact_bytes = b"x" * (1024 * 1024 + 1)
                    reason, compiled = "JMDNS_POLICY_FILE_DYLIB_STAT_LIMIT", True
                with self.assertRaisesRegex(M.DriverError, "^" + reason + "$"):
                    model.driver.prepare_policy_native()
                self.assertEqual(model.started_commands.count("policy-native-compile"), int(compiled))
                self.assertFalse(model.original_record.exists())
                self.assertFalse(model.consumer_record.exists())
                if change == "observer":
                    self.assertFalse(model.directory.exists())
                    model.c.clean_source.assert_not_called()
                    model.driver.observe_command.assert_not_called()
                if change in ("build-mode", "reports-mode"):
                    self.assertEqual(stat.S_IMODE(bad_parent.lstat().st_mode), 0o755)  # No repair/adoption.
                model.unexpected_launch.assert_not_called()
        malformed_paths = (b"", b"/synthetic/no-newline", b"/one\n/two\n", b"relative\n", b"//absolute\n",
                           b"/control\r\n", b"/control\t\n", b"/control\x7f\n", b"/" + b"x" * 16384 + b"\n")
        for raw in malformed_paths:
            with self.subTest(tool_path=raw[:24]), SyntheticPolicyFrame(self) as model:
                model.outputs["policy-find-clang"] = (raw, b"")
                with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_TOOL_PATH$"):
                    model.driver.prepare_policy_native()
                self.assertNotIn("policy-native-compile", model.started_commands)
                self.assertFalse(model.original_record.exists())
        with SyntheticPolicyFrame(self) as model:
            model.outputs["policy-find-clang"] = (b"/\xff\n", b"")
            with self.assertRaises(UnicodeDecodeError):
                model.driver.prepare_policy_native()
            self.assertFalse(model.original_record.exists())
        releases = (b'JAVA_VERSION="21.0.1"\n', b'JAVA_VERSION="17.0.1"\nJAVA_VERSION="21.0.1"\n',
                    b'JAVA_VERSION="17"\nJAVA_VERSION="17"\n', b'JAVA_VERSION="17"\nJAVA_VERSION=21\n',
                    b"JAVA_VERSION=17\n", b'JAVA_VERSION="17\n', b'IMPLEMENTOR="synthetic"\n')
        for raw in releases:
            with self.subTest(release=raw), SyntheticPolicyFrame(self) as model:
                model.paths["javaRelease"].write_bytes(raw)
                with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_JDK17_HEADERS$"):
                    model.driver.prepare_policy_native()
                self.assertNotIn("policy-native-compile", model.started_commands)
                self.assertFalse(model.original_record.exists())
        for code in (0, 7):
            for name in self.INPUT_LIMITS:
                with self.subTest(after_compile=code, input=name), SyntheticPolicyFrame(self, compile_code=code) as model:
                    path = model.paths[name]
                    model.after_observation["policy-native-compile"] = lambda: path.write_bytes(path.read_bytes() + b"changed\n")
                    with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_COMPILER_INPUT_CHANGED$"):
                        model.driver.prepare_policy_native()
                    self.assertEqual(model.started_commands.count("policy-native-compile"), 1)
                    self.assertFalse(model.original_record.exists())
                    self.assertFalse(model.consumer_record.exists())

    def test_ordinary_compile_nonzero_still_returns_only_the_one_unchanged_gradle_exit(self):
        for gradle_code in (19, 123):
            with self.subTest(gradle_code=gradle_code), SyntheticPolicyFrame(self, compile_code=7) as model:
                before_request, before_env = copy.deepcopy(model.request), dict(model.env)
                self.assertEqual(model.run_target(gradle_code), gradle_code)
                prepared = model.prepared
                self.assertEqual((prepared["record"]["status"], prepared["record"]["reason"],
                                  prepared["record"]["compiler"]["exitCode"]), ("NOT_COMPILED", "COMPILER_NONZERO", 7))
                self.assertIsNone(prepared["record"]["artifact"])
                self.assertFalse(model.library.exists())
                self.assertEqual(set(prepared["record"]["inputs"]), set(self.INPUT_LIMITS))
                self.assertEqual(set(prepared["record"]["observations"]), {"findClang", "findSdk", "clangVersion"})
                expected = diagnostic_arguments(CANONICAL_PYTHON)
                argv = [str(model.candidate / "gradlew"), *expected, "--source-owned-policy"]
                model.constructor.assert_called_once_with(model.c, "target")
                model.target_launch.assert_called_once_with(argv, cwd=model.candidate, env=model.env,
                                                            stdin=subprocess.DEVNULL, close_fds=True)
                model.driver.data.diagnostic_gradle_arguments.assert_called_once_with(CANONICAL_PYTHON)
                model.driver.runner.gradle_arguments.assert_called_once_with(expected)
                model.driver.java_metadata.assert_called_once_with()
                model.driver.prepare_policy_native.assert_called_once_with()
                model.driver.verify_policy_native.assert_called_once_with(prepared, gradle_code)
                model.gradle_child.wait.assert_called_once_with(timeout=899.0)
                name, target = model.driver.record.call_args.args
                self.assertEqual(name, "jmdns-target.json")
                self.assertEqual(target["testExitCode"], gradle_code)
                self.assertEqual(target["requestedGradleArgv"], expected)
                self.assertEqual(target["executedGradleArgv"], argv)
                self.assertEqual(model.target_record.read_bytes(), encoded(target))
                self.assertEqual(model.original_record.read_bytes(), model.consumer_record.read_bytes())
                self.assertEqual((model.request, model.env), (before_request, before_env))
                self.assertEqual(model.started_commands.count("policy-native-compile"), 1)
                model.unexpected_launch.assert_not_called()

    def test_unavailable_preparation_records_finite_refusal_and_cannot_accept_gradle_zero(self):
        with SyntheticPolicyFrame(self, compile_code=7) as model:
            with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_PREFLIGHT_BYPASSED$"):
                model.run_target(0)
            self.assertEqual(model.prepared["record"]["reason"], "COMPILER_NONZERO")
            model.target_launch.assert_called_once()
            model.driver.verify_policy_native.assert_called_once_with(model.prepared, 0)
            self.assert_no_target_record(model)
        cases = [(name, kind) for name in ("policy-find-clang", "policy-find-sdk", "policy-clang-version")
                 for kind in ("unavailable", "nonzero")]
        cases += [("policy-native-compile", "unavailable"), ("first-query", "budget"),
                  ("first-input", "budget"), ("policy-native-compile", "budget")]
        for where, kind in cases:
            for gradle_code in (19, 0):
                with self.subTest(where=where, kind=kind, gradle_code=gradle_code), SyntheticPolicyFrame(self) as model:
                    if kind == "unavailable":
                        model.not_returned[where] = "NATIVE_COMMAND_UNAVAILABLE"
                        reason = "COMPILER_NOT_RETURNED" if where == "policy-native-compile" else "TOOL_QUERY_NOT_RETURNED"
                    elif kind == "nonzero":
                        model.codes[where], reason = 7, "TOOL_QUERY_NONZERO"
                    else:
                        reason = "OBSERVATION_BUDGET_NOT_ADMITTED"
                        if where == "first-query":
                            model.clock = 216 * M.NS
                        elif where == "first-input":
                            model.after_observation["policy-find-sdk"] = lambda: setattr(model, "clock", 216 * M.NS)
                        else:
                            model.after_observation["policy-clang-version"] = lambda: setattr(model, "clock", 191 * M.NS)
                    if gradle_code:
                        self.assertEqual(model.run_target(gradle_code), gradle_code)
                        self.assertEqual(model.driver.record.call_args.args[1]["testExitCode"], 19)
                    else:
                        with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_PREFLIGHT_BYPASSED$"):
                            model.run_target(gradle_code)
                        self.assert_no_target_record(model)
                    record = model.prepared["record"]
                    self.assertEqual(set(record), self.RECORD_KEYS)
                    self.assertEqual((record["status"], record["reason"], record["artifact"]), ("NOT_COMPILED", reason, None))
                    self.assertNotEqual(record["compiler"]["status"], "RETURNED")
                    self.assertNotIn("policy-native-compile", model.started_commands)
                    self.assertFalse(model.library.exists())
                    self.assertEqual(model.original_record.read_bytes(), model.consumer_record.read_bytes())
                    model.target_launch.assert_called_once()
                    expected = diagnostic_arguments(CANONICAL_PYTHON)
                    self.assertEqual(model.target_launch.call_args.args[0],
                                     [str(model.candidate / "gradlew"), *expected, "--source-owned-policy"])
                    model.driver.verify_policy_native.assert_called_once_with(model.prepared, gradle_code)
        # Constructor refusal remains ahead of both compilation and Gradle. This
        # is a flow stub; the real environment constructor negatives remain above.
        with patch.object(M, "Driver", side_effect=M.DriverError("JMDNS_ORIGINAL_OWNER")), \
                patch.object(M.subprocess, "Popen") as launch, \
                self.assertRaisesRegex(M.DriverError, "^JMDNS_ORIGINAL_OWNER$"):
            M.target(SimpleNamespace(DIAGNOSTIC_SCOPE=SCOPE))
        launch.assert_not_called()

    def test_real_observer_adds_only_compiler_api_return_clocks_and_preserves_other_shapes(self):
        argv = ["/synthetic/selected/clang", "-dynamiclib", "-o", "/synthetic/fixed-output"]
        for code in (0, 7, 123):
            driver, streams = DriverControls.observation_driver(self)
            driver.observation_window.return_value = (100 * M.NS, 130 * M.NS)
            child = Mock(pid=4321)
            child.wait.return_value = code
            epochs = [1700000000000000001, 1700000000000000003]
            with self.subTest(code=code), patch.object(M.subprocess, "Popen", return_value=child) as launch, \
                    patch.object(M.os, "getpid", return_value=1234), \
                    patch.object(M.time, "monotonic_ns", side_effect=[tick * M.NS for tick in range(101, 107)]), \
                    patch.object(M.time, "time_ns", side_effect=epochs):
                result, stdout, stderr = driver.observe_command("policy-native-compile", argv, 30, 1024 * 1024)
            driver.observation_window.assert_called_once_with(30)
            self.assertEqual(set(result), {"status", "argv", "exitCode", "startedMonotonicNs", "endedMonotonicNs",
                                           "stdout", "stderr", "interpretation", "process"})
            self.assertEqual(result["process"], {"pid": 4321, "parentPid": 1234,
                "popenReturnedMonotonicNs": 101 * M.NS, "popenReturnedEpochNs": epochs[0],
                "waitReturnedMonotonicNs": 103 * M.NS, "waitReturnedEpochNs": epochs[1]})
            self.assertEqual(set(result["process"]), self.PROCESS_KEYS)
            self.assertEqual((result["status"], result["exitCode"], result["startedMonotonicNs"], result["endedMonotonicNs"]),
                             ("RETURNED", code, 100 * M.NS, 106 * M.NS))
            self.assertEqual((stdout, stderr), (b"retained original", b"retained original"))
            launch.assert_called_once_with(argv, cwd=driver.root, env=driver.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, bufsize=0)
            child.wait.assert_called_once_with(timeout=28.0)
            self.assertEqual(len(streams), 2)
            for stream in streams:
                stream.start.assert_called_once()
                stream.finish.assert_called_once()
            self.assertEqual([call.args[1] for call in driver.c.read_file.call_args_list], [64 * 1024 * 1024] * 2)
        driver, _ = DriverControls.observation_driver(self)
        child = Mock()
        child.wait.return_value = 7
        with patch.object(M.subprocess, "Popen", return_value=child), \
                patch.object(M.time, "monotonic_ns", return_value=100 * M.NS), patch.object(M.time, "time_ns") as epoch:
            result, _, _ = driver.observe_command("policy-dylibSignature", ["/usr/bin/codesign"], 5, 65536)
        self.assertEqual(set(result), {"status", "argv", "exitCode", "startedMonotonicNs", "endedMonotonicNs",
                                      "stdout", "stderr", "interpretation"})
        epoch.assert_not_called()
        for failure in (FileNotFoundError("synthetic absent compiler"), PermissionError("synthetic unavailable compiler")):
            driver, streams = DriverControls.observation_driver(self)
            with self.subTest(unavailable=type(failure).__name__), patch.object(M.subprocess, "Popen", side_effect=failure):
                result = driver.observe_command("policy-native-compile", argv, 30, 1024 * 1024)
            self.assertEqual(result, ({"status": "INCONCLUSIVE", "reason": "NATIVE_COMMAND_UNAVAILABLE"}, None, None))
            self.assertEqual(streams, [])
            driver.c.read_file.assert_not_called()

    def test_real_compiler_timeout_reserved_cancellation_and_stream_uncertainty_never_reach_gradle(self):
        failures = (("timeout", subprocess.TimeoutExpired("synthetic fixed compiler", 30), subprocess.TimeoutExpired),
                    ("reserved124", 124, M.DriverError), ("reserved125", 125, M.DriverError),
                    ("signalled", -15, M.DriverError), ("cancel-code", 130, M.DriverError),
                    ("boolean-code", True, M.DriverError), ("cancelled", KeyboardInterrupt(), KeyboardInterrupt),
                    ("system-exit", SystemExit(125), SystemExit), ("streams", 0, M.DriverError))
        for name, failure, error_type in failures:
            with self.subTest(failure=name), SyntheticPolicyFrame(self) as model:
                observer, streams = DriverControls.observation_driver(self, stream_error=name == "streams")
                model.driver.runner.Tee = observer.runner.Tee

                def dispatch(command, *args):
                    return model.real_observe(command, *args) if command == "policy-native-compile" else model.observe(command, *args)

                model.driver.observe_command.side_effect = dispatch
                child = Mock(pid=4321)
                if isinstance(failure, BaseException):
                    child.wait.side_effect = failure
                else:
                    child.wait.return_value = failure
                with patch.object(M, "Driver", return_value=model.driver), \
                        patch.object(M.subprocess, "Popen", return_value=child) as launch, \
                        patch.object(M.os, "getpid", return_value=1234), \
                        patch.object(M.time, "time_ns", return_value=1700000000000000000), \
                        self.assertRaises(error_type) as caught:
                    M.target(model.c)
                if isinstance(failure, BaseException):
                    self.assertIs(caught.exception, failure)
                self.assertEqual(launch.call_count, 1)  # Only the mocked compiler, never Gradle.
                self.assertEqual(launch.call_args.args[0], model.compiler_argv())
                self.assertEqual(len(streams), 2)
                for stream in streams:
                    stream.start.assert_called_once()
                    stream.finish.assert_called_once()
                model.driver.verify_policy_native.assert_not_called()
                self.assert_no_target_record(model)
                self.assertFalse(model.original_record.exists())
                self.assertFalse(model.consumer_record.exists())

    def test_post_gradle_byte_identity_source_stream_and_directory_mutations_refuse_target_record(self):
        cases = (("original-record", "JMDNS_POLICY_RECORD_CHANGED"), ("consumer-record", "JMDNS_POLICY_RECORD_CHANGED"),
                 ("request", "JMDNS_POLICY_REQUEST_CHANGED"), ("source", "JMDNS_POLICY_COMPILER_INPUT_CHANGED"),
                 ("artifact-bytes", "JMDNS_POLICY_ARTIFACT_CHANGED"), ("artifact-inode", "JMDNS_POLICY_ARTIFACT_CHANGED"),
                 ("stream-bytes", "JMDNS_POLICY_STREAM_COPY_CHANGED"), ("stream-mode", "JMDNS_POLICY_STREAM_COPY_CHANGED"),
                 ("source-check", "SYNTHETIC_SOURCE_CHANGED"), ("build-mode", "JMDNS_POLICY_OUTPUT_DIRECTORY"),
                 ("reports-mode", "JMDNS_POLICY_OUTPUT_DIRECTORY"), ("native-mode", "JMDNS_POLICY_OUTPUT_DIRECTORY"),
                 ("directory-owner", "JMDNS_POLICY_OUTPUT_DIRECTORY"), ("directory-symlink", "JMDNS_POLICY_OUTPUT_DIRECTORY"))
        for change, reason in cases:
            with self.subTest(change=change), SyntheticPolicyFrame(self) as model:
                def mutate():
                    paths = {"original-record": model.original_record, "consumer-record": model.consumer_record,
                        "request": model.request_path, "source": model.paths["source"], "artifact-bytes": model.library,
                        "stream-bytes": model.directory / "compiler.stdout.log"}
                    if change in paths:
                        path = paths[change]
                        path.write_bytes(path.read_bytes() + b" ")
                    elif change == "artifact-inode":
                        before, raw = model.library.lstat(), model.library.read_bytes()
                        replacement = model.directory / "synthetic-replacement"
                        model.file(replacement, raw, stat.S_IMODE(before.st_mode))
                        replacement.replace(model.library)  # Allocate before unlink, avoiding inode-reuse ambiguity.
                        self.assertNotEqual(model.library.lstat().st_ino, before.st_ino)
                        self.assertEqual(digest(model.library.read_bytes()), model.prepared["record"]["artifact"]["sha256"])
                    elif change == "stream-mode":
                        path = model.directory / "compiler.stdout.log"
                        path.chmod(0o400)
                        self.assertEqual(path.read_bytes(), model.outputs["policy-native-compile"][0])
                    elif change == "source-check":
                        model.c.clean_source.side_effect = M.DriverError("SYNTHETIC_SOURCE_CHANGED")
                    elif change in ("build-mode", "reports-mode", "native-mode"):
                        {"build-mode": model.directory.parent.parent, "reports-mode": model.directory.parent,
                         "native-mode": model.directory}[change].chmod(0o750)
                    elif change == "directory-owner":
                        model.stack.enter_context(patch.object(M.os, "getuid", return_value=os.getuid() + 1))
                    elif change == "directory-symlink":
                        moved = model.base / "moved-native-directory"
                        model.directory.rename(moved)
                        model.directory.symlink_to(moved, target_is_directory=True)
                        model.c.physical.side_effect = lambda value: Path(value)

                with self.assertRaisesRegex(M.DriverError, "^" + reason + "$"):
                    model.run_target(19, after_wait=mutate)
                model.target_launch.assert_called_once()
                model.gradle_child.wait.assert_called_once()
                model.driver.verify_policy_native.assert_called_once_with(model.prepared, 19)
                self.assert_no_target_record(model)
        # Original/consumer record custody is byte equality, not a promise of
        # record-inode continuity. Do not confuse that with the artifact identity.
        with SyntheticPolicyFrame(self) as model:
            def replace_same_records():
                for path in (model.original_record, model.consumer_record):
                    old_inode = path.lstat().st_ino
                    replacement = path.with_name("same-bytes-" + path.name)
                    model.file(replacement, path.read_bytes(), 0o600)
                    replacement.replace(path)
                    self.assertNotEqual(path.lstat().st_ino, old_inode)
            self.assertEqual(model.run_target(19, after_wait=replace_same_records), 19)
            self.assertEqual(model.original_record.read_bytes(), model.consumer_record.read_bytes())
            self.assertEqual(model.driver.record.call_args.args[1]["testExitCode"], 19)

    def test_all_preparation_and_record_finalization_charge_original_observation_not_gradle_time(self):
        with SyntheticPolicyFrame(self) as model:
            original_request = copy.deepcopy(model.request)
            model.cost_seconds = {"policy-find-clang": 5, "policy-find-sdk": 5, "policy-clang-version": 5,
                "policy-native-compile": 30, "policy-dylibSignature": 5, "policy-dylibUuid": 5}
            model.record_write_seconds = 2
            self.assertEqual(model.run_target(19, duration_seconds=600), 19)
            compile_record = model.prepared["record"]
            target = model.driver.record.call_args.args[1]
            self.assertEqual((compile_record["startedMonotonicNs"], compile_record["endedMonotonicNs"]),
                             (101 * M.NS, 156 * M.NS))
            # The record's end clock is before serialization/write/readback. The
            # actual target start must additionally charge both final writes.
            self.assertEqual([row for row in model.writes if row[0] in (model.original_record, model.consumer_record)],
                [(model.original_record, 156 * M.NS, 158 * M.NS), (model.consumer_record, 158 * M.NS, 160 * M.NS)])
            self.assertEqual((target["beforeObservationElapsedNs"], target["startedTestMonotonicNs"], target["endTestMonotonicNs"]),
                             (60 * M.NS, 160 * M.NS, 760 * M.NS))
            self.assertEqual((model.driver.observation_deadline, model.driver.observation_deadline - model.clock),
                             (820 * M.NS, 60 * M.NS))
            model.gradle_child.wait.assert_called_once_with(timeout=840.0)
            self.assertEqual(model.driver.product_deadline, 1000 * M.NS)
            self.assertEqual(model.request, original_request)
            self.assertEqual(model.request["deadlineMonotonicNs"], 1300 * M.NS)
            self.assertEqual((M.PRODUCT_NS, M.OBSERVATION_NS, M.RESERVED_CLOSE_NS),
                             (1200 * M.NS, 120 * M.NS, 300 * M.NS))
        with SyntheticPolicyFrame(self) as model:
            model.clock, model.record_write_seconds = 216 * M.NS, 2
            with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_PREPARATION_TIMEOUT$"):
                model.run_target(19)
            # Even completed bytes with a predeadline end field do not authorize
            # Gradle once their finalization reaches the original observation end.
            self.assertEqual(json.loads(model.original_record.read_bytes())["endedMonotonicNs"], 216 * M.NS)
            self.assertEqual(model.clock, 220 * M.NS)
            model.target_launch.assert_not_called()
            model.driver.verify_policy_native.assert_not_called()
            self.assert_no_target_record(model)
        with SyntheticPolicyFrame(self) as model:
            model.clock = 216 * M.NS  # No input acquired, so final recheck owns the last deadline test.

            def delay_post_gradle_request_read():
                def read(path, limit=64 * 1024 * 1024):
                    result = model.read_file(path, limit)
                    if path == model.request_path:
                        model.clock = model.driver.observation_deadline
                    return result
                model.c.read_file.side_effect = read

            with self.assertRaisesRegex(M.DriverError, "^JMDNS_POLICY_RECHECK_TIMEOUT$"):
                model.run_target(19, duration_seconds=600, after_wait=delay_post_gradle_request_read)
            self.assertEqual((model.driver.observation_deadline, model.clock), (820 * M.NS, 820 * M.NS))
            self.assertEqual(model.driver.product_deadline, 1000 * M.NS)
            model.target_launch.assert_called_once()
            self.assert_no_target_record(model)


class FailureLocationControls(unittest.TestCase):
    """Synthetic Python frames only; no driver body, owner or native execution."""

    ROLES = (
        (M.Driver.__init__, "INIT"), (M.Driver.hash_java, "JAVA_HASH"),
        (M.Driver.observe_command, "COMMAND"), (M.Driver.policy_file, "POLICY_FILE"),
        (M.Driver.policy_directory, "POLICY_DIR"), (M.Driver.policy_query_path, "POLICY_PATH"),
        (M.Driver.prepare_policy_native, "POLICY_PREP"), (M.Driver.verify_policy_native, "POLICY_CHECK"),
        (M.Driver.java_metadata, "JAVA_META"), (M.Driver.record, "RECORD"),
        (M.target, "TARGET"), (M.original_target, "TARGET_JOIN"), (M.observe, "OBSERVER"),
    )
    BUILTINS = (
        (FileNotFoundError, "MISSING"), (PermissionError, "PERMISSION"), (OSError, "OS"),
        (FileExistsError, "OS"), (NotADirectoryError, "OS"), (IsADirectoryError, "OS"),
        (BlockingIOError, "OS"), (InterruptedError, "OS"), (ProcessLookupError, "OS"),
        (BrokenPipeError, "OS"), (TimeoutError, "OS"), (UnicodeError, "UNICODE"),
        (UnicodeDecodeError, "UNICODE"), (UnicodeEncodeError, "UNICODE"),
        (UnicodeTranslateError, "UNICODE"), (KeyError, "KEY"), (TypeError, "TYPE"),
        (AttributeError, "ATTRIBUTE"), (ValueError, "VALUE"), (subprocess.TimeoutExpired, "TIMEOUT"),
    )
    HELPERS = (("jmdns_driver_executor", "AuditError", "AUDIT"),
               ("audit_processes", "OwnershipError", "OWNER"),
               ("jmdns_driver_data", "DiagnosticError", "DATA"))

    def frame_for(self, function, code=None):
        # The CALL trace event precedes all body bytecodes. The synthetic
        # function also has empty globals/builtins and None arguments: it has
        # no real controller/owner/tool access even if interception is broken.
        code = function.__code__ if code is None else code
        synthetic = FunctionType(code, {"__builtins__": {}})
        synthetic.__kwdefaults__ = dict(function.__kwdefaults__ or {})
        frames, marker, previous = [], RuntimeError("synthetic call boundary"), sys.gettrace()

        def intercept(frame, event, _arg):
            if event == "call" and frame.f_code is code:
                frames.append(frame)
                raise marker
            return intercept

        try:
            sys.settrace(intercept)
            try:
                synthetic(*(None,) * code.co_argcount)
            except RuntimeError as caught:
                self.assertIs(caught, marker)
            else:
                self.fail("synthetic call was not intercepted before its body")
        finally:
            sys.settrace(previous)
        self.assertEqual(len(frames), 1)
        self.assertIs(sys.gettrace(), previous)
        return frames[0]

    @staticmethod
    def with_frames(error, frames):
        node = None
        for frame in reversed(frames):
            node = TracebackType(node, frame, 0, 1)  # Synthetic fields, never extracted originals.
        BaseException.__traceback__.__set__(error, node)
        return error

    def assert_projection(self, error, expected):
        kind = type(error)
        args = BaseException.args.__get__(error)
        traceback = BaseException.__traceback__.__get__(error)
        result = M.failure_hint(error)
        self.assertIs(type(result), str)
        self.assertEqual(result, expected)
        self.assertIs(type(error), kind)
        self.assertIs(BaseException.args.__get__(error), args)
        self.assertIs(BaseException.__traceback__.__get__(error), traceback)

    def test_fixed_role_and_family_tables_are_independent_immutable_rosters(self):
        self.assertIs(type(M.FAILURE_HINT_ROLES), tuple)
        self.assertEqual(len(M.FAILURE_HINT_ROLES), 13)
        for actual, (function, label) in zip(M.FAILURE_HINT_ROLES, self.ROLES):
            self.assertIs(type(actual), tuple)
            self.assertEqual(len(actual), 2)
            self.assertIs(actual[0], function.__code__)
            self.assertEqual(actual[1], label)
        self.assertIs(type(M.FAILURE_HINT_BUILTIN_FAMILIES), tuple)
        self.assertEqual(len(M.FAILURE_HINT_BUILTIN_FAMILIES), 20)
        for actual, expected in zip(M.FAILURE_HINT_BUILTIN_FAMILIES, self.BUILTINS):
            self.assertIs(type(actual), tuple)
            self.assertEqual(len(actual), 2)
            self.assertIs(actual[0], expected[0])
            self.assertEqual(actual[1], expected[1])
        self.assertEqual(M.FAILURE_HINT_MODULE_FAMILIES, self.HELPERS)
        self.assertIs(type(M.FAILURE_HINT_MODULE_FAMILIES), tuple)
        self.assertIs(type(M.FAILURE_HINT_TRACEBACK_LIMIT), int)
        self.assertEqual(M.FAILURE_HINT_TRACEBACK_LIMIT, 64)

    def test_original_code_identity_and_deepest_role_never_accept_equal_code_clones(self):
        for function, role in self.ROLES:
            with self.subTest(role=role):
                error = self.with_frames(FileNotFoundError(), [self.frame_for(function)])
                self.assert_projection(error, "JMDNS_AT_" + role + "_MISSING")
        outer, inner = self.frame_for(M.target), self.frame_for(M.Driver.policy_file)
        clone = M.target.__code__.replace()
        self.assertIsNot(clone, M.target.__code__)
        self.assertEqual(clone, M.target.__code__)
        foreign = self.frame_for(M.target, clone)
        for frames, role in (([outer, inner, foreign], "POLICY_FILE"),
                             ([inner, outer, foreign], "TARGET"), ([foreign], "UNKNOWN")):
            self.assert_projection(self.with_frames(KeyError(), frames), "JMDNS_AT_" + role + "_KEY")

    def test_unknown_or_incomplete_traceback_never_reports_a_partial_deepest_role(self):
        self.assert_projection(ValueError(), "JMDNS_AT_UNKNOWN_VALUE")
        try:
            raise ValueError("synthetic unrecognized raised frame")
        except ValueError as error:
            self.assert_projection(error, "JMDNS_AT_UNKNOWN_VALUE")
        unknown = self.frame_for(M.target, M.target.__code__.replace())
        outer, inner = self.frame_for(M.target), self.frame_for(M.Driver.hash_java)
        cases = (([unknown], "UNKNOWN"), ([outer] + [unknown] * 62 + [inner], "JAVA_HASH"),
                 ([outer] + [unknown] * 62 + [inner, unknown], "UNKNOWN"),
                 ([outer] + [unknown] * 63 + [inner], "UNKNOWN"))
        self.assertEqual([len(frames) for frames, _ in cases], [1, 64, 65, 65])
        for frames, role in cases:
            with self.subTest(nodes=len(frames), role=role):
                self.assert_projection(self.with_frames(TypeError(), frames), "JMDNS_AT_" + role + "_TYPE")

    def test_exact_builtin_families_leave_subclasses_and_private_driver_text_other(self):
        special = {UnicodeDecodeError: ("ascii", b"\xff", 0, 1, "synthetic"),
                   UnicodeEncodeError: ("ascii", "\u00e9", 0, 1, "synthetic"),
                   UnicodeTranslateError: ("\u00e9", 0, 1, "synthetic"),
                   subprocess.TimeoutExpired: ("synthetic command", 1)}
        for kind, family in self.BUILTINS:
            with self.subTest(family=family, kind=kind.__name__):
                args = special.get(kind, ())
                self.assert_projection(kind(*args), "JMDNS_AT_UNKNOWN_" + family)
                subclass = type("SyntheticSubclass", (kind,), {})
                self.assert_projection(subclass(*args), "JMDNS_AT_UNKNOWN_OTHER")
        for error in (Exception(), RuntimeError(), M.DriverError("unreviewed private literal"),
                      KeyboardInterrupt(), SystemExit(125)):
            self.assert_projection(error, "JMDNS_AT_UNKNOWN_OTHER")

    def test_helper_families_use_only_fixed_loaded_exact_modules_without_hooks_or_imports(self):
        attempts = []

        def forbidden(*_args, **_kwargs):
            attempts.append("helper hook or import")
            raise AssertionError("synthetic forbidden helper discovery")

        class ModuleSubclass(ModuleType):
            __getattribute__ = forbidden

        for module_name, type_name, family in self.HELPERS:
            kind = type(type_name, (Exception,), {})
            loaded = ModuleType(module_name)
            loaded.__dict__.update({type_name: kind, "__getattr__": forbidden})
            child = type("SyntheticSubclass", (kind,), {})
            foreign = ModuleType("unreviewed_helper")
            foreign.__dict__[type_name] = kind
            cases = (({module_name: loaded}, kind(), family),
                     ({module_name: loaded}, child(), "OTHER"), ({}, kind(), "OTHER"),
                     ({"unreviewed_helper": foreign}, kind(), "OTHER"),
                     ({module_name: SimpleNamespace(**{type_name: kind})}, kind(), "OTHER"),
                     ({module_name: ModuleSubclass(module_name)}, kind(), "OTHER"))
            for modules, error, expected in cases:
                with patch.object(M, "sys", SimpleNamespace(modules=modules)), \
                        patch("builtins.__import__", side_effect=forbidden):
                    self.assert_projection(error, "JMDNS_AT_UNKNOWN_" + expected)
            del loaded.__dict__[type_name]
            with patch.object(M, "sys", SimpleNamespace(modules={module_name: loaded})), \
                    patch("builtins.__import__", side_effect=forbidden):
                self.assert_projection(kind(), "JMDNS_AT_UNKNOWN_OTHER")
        self.assertEqual(attempts, [])

    def test_hostile_error_type_payload_and_render_hooks_are_never_consulted(self):
        attempts = []

        def forbidden(*_args, **_kwargs):
            attempts.append("private read, rendering, mutation or I/O")
            raise AssertionError("synthetic forbidden diagnostic access")

        class HostileType(type):
            __getattribute__ = __str__ = __repr__ = __eq__ = __hash__ = forbidden

        class HostileError(Exception, metaclass=HostileType):
            __getattribute__ = __setattr__ = __str__ = __repr__ = forbidden

        class Payload:
            __str__ = __repr__ = __eq__ = __hash__ = forbidden

        error = self.with_frames(HostileError(Payload()), [self.frame_for(M.observe)])
        with patch.object(sys, "stdout") as stdout, patch.object(sys, "stderr") as stderr, \
                patch.object(M.subprocess, "Popen", side_effect=forbidden), \
                patch.object(M.os, "open", side_effect=forbidden), \
                patch.object(Path, "open", side_effect=forbidden), \
                patch("builtins.open", side_effect=forbidden), \
                patch("builtins.__import__", side_effect=forbidden):
            self.assert_projection(error, "JMDNS_AT_OBSERVER_OTHER")
        self.assertEqual(attempts, [])
        stdout.write.assert_not_called()
        stderr.write.assert_not_called()

    def test_unexpected_bookkeeping_failure_keeps_original_error_and_generic_refusal(self):
        attempts = []

        class BrokenModules(dict):
            def get(self, _name):
                attempts.append("lookup")
                raise RuntimeError("synthetic bookkeeping refusal")

        error = self.with_frames(RuntimeError(object()), [self.frame_for(M.target)])
        with patch.object(M, "sys", SimpleNamespace(modules=BrokenModules())):
            self.assert_projection(error, "PRIVATE_FAILURE")
        self.assertEqual(attempts, ["lookup"])
        for nonexception in (None, object(), "synthetic-not-an-exception"):
            self.assertEqual(M.failure_hint(nonexception), "PRIVATE_FAILURE")

    def test_mapper_source_is_descriptor_only_without_private_data_or_discovery(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        mapper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "failure_hint")
        nodes = tuple(ast.walk(mapper))
        private = {"f_locals", "f_globals", "f_back", "tb_lineno", "tb_lasti", "co_filename", "co_name",
                   "co_qualname", "co_consts", "args", "errno", "__cause__", "__context__"}
        self.assertFalse({node.attr for node in nodes if isinstance(node, ast.Attribute)} & private)
        calls = [node.func for node in nodes if isinstance(node, ast.Call)]
        self.assertEqual({node.id for node in calls if isinstance(node, ast.Name)}, {"type", "range"})
        self.assertEqual({node.attr for node in calls if isinstance(node, ast.Attribute)}, {"get", "__get__"})
        descriptors = [ast.unparse(node.value) for node in calls
                       if isinstance(node, ast.Attribute) and node.attr == "__get__"]
        self.assertCountEqual(descriptors, ["BaseException.__traceback__", "TracebackType.tb_frame",
                                            "FrameType.f_code", "TracebackType.tb_next"])


if __name__ == "__main__":
    unittest.main()
