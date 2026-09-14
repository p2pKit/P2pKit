#!/usr/bin/env python3
"""Pure policy/file/mock controls, NOT native Windows or Gradle execution.

Only three bounded read-only Git queries obtain the immutable reviewed preimages.
All controller process, tool and native operations below are fake; no wrapper,
native fixture suite, SDK installer, host impersonation or network is executed.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("windows_control_fixture", ROOT / "scripts/run-windows-directory-control.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
BAD = (C.audit.AuditError, ValueError)
FIXTURE_SPEC = importlib.util.spec_from_file_location("native_fixture_definitions", ROOT / "scripts/tests/run-audit-command-test.py")
F = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(F)  # Definitions only; native suites are never run by these controls.


def dispatch():
    sha, tree, ref = "a" * 40, "b" * 40, "refs/heads/work/control-fixture"
    env = {"P2PKIT_EXPECTED_SHA": sha, "P2PKIT_EXPECTED_TREE": tree, "P2PKIT_OPERATION": C.OPERATION,
        "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": C.REPOSITORY,
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com", "GITHUB_JOB": C.JOB,
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows", "RUNNER_ARCH": "X64", "GITHUB_SHA": sha,
        "GITHUB_WORKFLOW_SHA": sha, "GITHUB_REF": ref, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_WORKFLOW_REF": C.REPOSITORY + "/" + C.WORKFLOW + "@" + ref}
    event = {"repository": {"full_name": C.REPOSITORY}, "ref": ref,
        "inputs": {"operation": C.OPERATION, "expected_sha": sha, "expected_tree": tree}}
    source = {"commit": sha, "tree": tree, "status": "", "diffSha256": C.digest(b"")}
    return env, event, source


def request(negative=False):
    return {"caseName": "preimage" if negative else "current", "nonce": "c" * 32, "source": dispatch()[2],
        "identity": {"scope": "MODEL_ONLY_NOT_HOSTED"}, "root": r"C:\control\source", "state": r"C:\control\state",
        "outputDirectory": r"C:\control\state\evidence\directory-control-model",
        "testTemporary": r"C:\control\state\fixtures\jvm-tmp", "java17": r"C:\jdk17", "java21": r"C:\jdk21"}


def arguments(req):
    return ["-Djava.io.tmpdir=" + req["testTemporary"], "-Dp2pkit.windowsDirectoryNonce=" + req["nonce"],
            "-Xmx512m", "-Xms128m", "-XX:ActiveProcessorCount=2", "-XX:-UsePerfData"]


def execution(req, scope="root"):
    negative = req["caseName"] == "preimage" and scope == "root"
    paths = sorted(C.REQUIRED_TASKS) if scope == "root" else [":compileJava", ":jar"]
    admission = {"task": C.TASK, "commandFilters": [C.SELECTOR], "includePatterns": [], "excludePatterns": [],
        "enabled": True, "ignoreFailures": False, "failOnNoMatchingTests": True, "maxParallelForks": 1, "forkEvery": 0,
        "temporaryEmpty": True, "temporaryFileKey": "MODEL_FILE_KEY", "observedMillis": 10,
        "temporary": req["testTemporary"], "jvmArgs": arguments(req),
        "launcher": {"version": 17, "home": req["java17"], "executable": req["java17"] + r"\bin\java.exe"}}
    return {"schema": 1, "scope": scope, "nonce": req["nonce"], "caseName": req["caseName"], "source": req["source"],
        "identity": req["identity"], "requestSha256": "d" * 64, "host": {"os": "Windows 2025", "arch": "amd64",
            "javaVersion": "21.0.1", "javaHome": req["java21"]}, "dryRun": False, "excludedTasks": [],
        "graph": [{"path": name, "test": name == C.TASK} for name in paths],
        "tasks": {name: {"outcome": "FAILED" if negative and name == C.TASK else "EXECUTED", "didWork": True,
                         "failureType": "MODEL_FAILURE" if negative and name == C.TASK else None} for name in paths},
        "buildFailed": negative, "root": req["root"] + (r"\buildSrc" if scope == "buildSrc" else ""),
        "binding": {"authority": "self" if scope == "root" else "direct-root-parent",
            "parentRoot": None if scope == "root" else req["root"], "parentHasParent": False,
            "localProperties": {"p2pkit.windowsDirectoryRoot": req["root"],
                "p2pkit.windowsDirectoryRequest": req["outputDirectory"] + r"\request.json",
                "p2pkit.windowsDirectoryRequestSha256": "d" * 64} if scope == "root" else {}},
        "requestedTasks": [C.TASK], "admission": admission, "finishedMillis": 30,
        "events": [] if scope == "buildSrc" else [{"className": C.CLASS, "name": C.METHOD,
            "result": "FAILURE" if negative else "SUCCESS", "testCount": 1, "passed": int(not negative),
            "failed": int(negative), "skipped": 0, "startMillis": 11, "endMillis": 20}]}


def xml(req):
    negative = req["caseName"] == "preimage"
    suite = ET.Element("testsuite", name=C.CLASS, tests="1", failures=str(int(negative)), errors="0", skipped="0")
    case = ET.SubElement(suite, "testcase", classname=C.CLASS, name=C.METHOD)
    if negative:
        path = req["testTemporary"] + r"\p2pkit-durable-destination-1234"
        failure = ET.SubElement(case, "failure", type="java.nio.file.AccessDeniedException", message=path)
        frames = ["java.base/sun.nio.fs.WindowsFileSystemProvider.newFileChannel", "java.base/java.nio.channels.FileChannel.open",
            "app//dev.p2pkit.core.transfer.JvmDurableFileDestination.syncParentDirectory",
            "app//dev.p2pkit.core.transfer.JvmDurableFileDestination.commit",
            C.CLASS + "$" + C.METHOD + "$1.invokeSuspend", C.CLASS + "." + C.METHOD]
        failure.text = "java.nio.file.AccessDeniedException: " + path + "\n" + "".join(
            "\tat " + frame + "(MODEL_SOURCE.java:1)\n" for frame in frames)
    return suite


def raw_xml(suite):
    return ET.tostring(suite, encoding="utf-8")


class PureWindowsControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def git(*args):
            result = subprocess.run(["git", "--no-replace-objects", "-C", str(ROOT), *args],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
            if result.returncode:
                raise RuntimeError("Full-history reviewed preimage query failed: " + result.stderr.decode(errors="replace"))
            return result.stdout
        cls.current = (ROOT / C.SOURCE).read_bytes()
        cls.test = (ROOT / C.TEST_SOURCE).read_bytes()
        cls.historical = git("show", C.PRE_FIX + ":" + C.SOURCE)
        cls.old_test = git("show", C.PRE_FIX + ":" + C.TEST_SOURCE)
        cls.parent = git("rev-parse", C.FIX + "^").decode().strip()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-windows-policy-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        # Any accidental invocation added to a pure fixture must fail immediately.
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("PURE fixture cannot launch a process")).start()
        mock.patch.object(C.processes, "make_scope", side_effect=AssertionError("PURE fixture cannot create native scope")).start()
        mock.patch.object(C, "native_memory", side_effect=AssertionError("PURE fixture cannot inspect native host")).start()

    def rejects(self, action):
        with self.assertRaises(BAD):
            action()

    def native_model(self):
        """Owned local metadata fixtures, never a hosted/native execution receipt."""
        directory = Path(tempfile.mkdtemp(prefix="native-metadata-model-", dir=self.base))
        controller = C.Controller.__new__(C.Controller)
        controller.public = directory / "public"
        for name in ("admission", "current"):
            (controller.public / name).mkdir(parents=True)
        controller.identity = {"sourceSha": "a" * 40, "sourceTree": "b" * 40,
                               "runId": "123", "runAttempt": "2", "scope": "MODEL_ONLY_NOT_HOSTED"}
        controller.deadline = controller.final_deadline = time.monotonic() + 30
        state = directory / "state"
        temporary = state / "fixtures/native-tmp"
        temporary.mkdir(parents=True)
        case = {"name": "current", "root": ROOT, "state": state, "public": controller.public / "current",
                "context": {"id": "c" * 32, "source": dispatch()[2]}, "leaves": [], "retentionErrors": [],
                "nativeStarted": False, "nativeAccepted": False,
                "nativeTemporaryIdentity": C.native_temporary_identity(temporary.lstat())}
        return controller, case, temporary

    def fixture_parent_paths(self):
        directory = Path(tempfile.mkdtemp(prefix="fixture-parent-model-", dir=self.base))
        state = directory / "state"
        parent = state / "fixtures/native-tmp"
        parent.mkdir(parents=True)
        process = state / "fixtures/process-tmp"
        process.mkdir()
        evidence = state / "evidence/native-controls"
        evidence.parent.mkdir()
        return state, parent, process, evidence

    def test_fixture_parent_cli_routes_all_actual_allocations_without_environment_changes(self):
        # Execute the eight actual allocation expressions, not any native test body.
        # The CLI's suite loader/runner are mocked; only local directories are real.
        tree = ast.parse((ROOT / "scripts/tests/run-audit-command-test.py").read_bytes())
        allocations = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and
                       node.func.value.id == "tempfile" and node.func.attr == "TemporaryDirectory"]
        self.assertEqual(len(allocations), 8)
        for node in allocations:
            self.assertEqual(node.args, [])
            self.assertEqual([item.arg for item in node.keywords], ["prefix", "dir"])
            self.assertIsInstance(node.keywords[0].value, ast.Constant)
            self.assertIsInstance(node.keywords[0].value.value, str)
            self.assertEqual(ast.dump(node.keywords[1].value), "Name(id='FIXTURE_PARENT', ctx=Load())")
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                state, parent, process, evidence = self.fixture_parent_paths()
                argv = ["run-audit-command-test.py", "--evidence-dir", str(evidence)]
                if explicit:
                    argv += ["--fixture-parent", str(parent)]
                environment = {F.processes.STATE_ENV: str(state),
                               **{name: str(process) for name in ("TEMP", "TMP", "TMPDIR")}}
                with mock.patch.dict(os.environ, environment), mock.patch.object(sys, "argv", argv), \
                        mock.patch.object(sys, "stdout", io.StringIO()), \
                        mock.patch.object(F, "FIXTURE_PARENT", "must be replaced by CLI selection"), \
                        mock.patch.object(F, "EVIDENCE_ROOT", None), \
                        mock.patch.object(tempfile, "tempdir", str(process)), \
                        mock.patch.object(F.unittest.defaultTestLoader, "loadTestsFromTestCase",
                                          return_value=unittest.TestSuite()) as loader, \
                        mock.patch.object(F.unittest, "TextTestRunner") as suite_runner:
                    original_environment = dict(os.environ)
                    suite_runner.return_value.run.return_value.wasSuccessful.return_value = True
                    self.assertEqual(F.main(), 0)
                    self.assertEqual(loader.call_count, 3)
                    self.assertEqual(F.FIXTURE_PARENT, parent if explicit else None)
                    self.assertEqual(F.EVIDENCE_ROOT, evidence)
                    self.assertTrue(evidence.is_dir())
                    for node in allocations:
                        expression = compile(ast.Expression(body=node), "actual-fixture-allocation", "eval")
                        with eval(expression, {"__builtins__": {}, "tempfile": tempfile,
                                               "FIXTURE_PARENT": F.FIXTURE_PARENT}) as temporary:
                            self.assertEqual(Path(temporary).parent, parent if explicit else process)
                            self.assertTrue(Path(temporary).is_dir())
                    self.assertEqual(list(parent.iterdir()), [])
                    self.assertEqual(list(process.iterdir()), [])
                    self.assertEqual(dict(os.environ), original_environment)
                    self.assertEqual(tempfile.tempdir, str(process))
        self.assertIsNone(F.validated_fixture_parent(None, None))

    def test_fixture_parent_rejects_invalid_unowned_and_nonempty_roots(self):
        for kind in ("relative", "dotdot", "missing", "file", "foreign", "no-state", "nonempty"):
            with self.subTest(kind=kind):
                state, parent, _, evidence = self.fixture_parent_paths()
                value, state_value = str(parent), str(state)
                if kind == "relative":
                    value = "fixtures/native-tmp"
                elif kind == "dotdot":
                    value = str(parent / ".." / "native-tmp")
                elif kind == "missing":
                    value = str(parent.parent / "missing")
                elif kind == "file":
                    parent.rmdir()  # Only the empty directory this model just created.
                    parent.write_bytes(b"MODEL must remain a regular file\n")
                elif kind == "foreign":
                    foreign = parent.parent / "foreign"
                    foreign.mkdir()
                    value = str(foreign)
                elif kind == "no-state":
                    state_value = ""
                elif kind == "nonempty":
                    (parent / "retain-me").write_bytes(b"MODEL unaccepted residue\n")
                with mock.patch.dict(os.environ, {F.processes.STATE_ENV: state_value}), \
                        self.assertRaises((F.runner.AuditError, FileNotFoundError, NotADirectoryError)):
                    F.validated_fixture_parent(value, str(evidence))
                self.assertFalse(evidence.exists())
                if kind == "file":
                    self.assertEqual(parent.read_bytes(), b"MODEL must remain a regular file\n")
                if kind == "nonempty":
                    self.assertEqual((parent / "retain-me").read_bytes(), b"MODEL unaccepted residue\n")

    def test_fixture_parent_rejects_link_and_reparse_metadata_without_following(self):
        # Portable no-follow metadata controls; not native link/junction creation.
        for location, field in (("parent", "symlink"), ("parent", "reparse"),
                                ("state", "reparse"), ("evidence", "symlink")):
            with self.subTest(location=location, field=field):
                state, parent, _, evidence = self.fixture_parent_paths()
                target = {"parent": parent, "state": state, "evidence": evidence.parent}[location]
                real_lstat = Path.lstat

                def lstat(path, *args, **kwargs):
                    actual = real_lstat(path, *args, **kwargs)
                    if path != target:
                        return actual
                    fields = ({"st_mode": stat.S_IFLNK | 0o700} if field == "symlink" else
                              {"st_file_attributes": getattr(actual, "st_file_attributes", 0) | 0x400})
                    return F.StatFields(actual, **fields)

                with mock.patch.dict(os.environ, {F.processes.STATE_ENV: str(state)}), \
                        mock.patch.object(Path, "lstat", new=lstat), \
                        self.assertRaisesRegex(F.runner.AuditError, "Symlink/reparse-point"):
                    F.validated_fixture_parent(str(parent), str(evidence))
                self.assertFalse(evidence.exists())
                self.assertEqual(list(parent.iterdir()), [])

    def test_fixture_parent_requires_separate_evidence_and_readable_empty_parent(self):
        state, parent, _, evidence = self.fixture_parent_paths()
        with mock.patch.dict(os.environ, {F.processes.STATE_ENV: str(state)}):
            for destination in (None, str(parent), str(parent / "retained"), str(parent.parent), str(state)):
                with self.subTest(destination=destination), self.assertRaises(F.runner.AuditError):
                    F.validated_fixture_parent(str(parent), destination)
            with mock.patch.object(os, "scandir", side_effect=PermissionError("MODEL unreadable parent")), \
                    self.assertRaisesRegex(PermissionError, "MODEL unreadable parent"):
                F.validated_fixture_parent(str(parent), str(evidence))
        self.assertFalse(evidence.exists())
        self.assertEqual(list(parent.iterdir()), [])

    def test_native_leaf_keeps_outer_environment_and_passes_fixture_parent_only_in_product_argv(self):
        controller, case, temporary = self.native_model()
        process = case["state"] / "fixtures/process-tmp"
        process.mkdir()
        case["env"] = {C.processes.STATE_ENV: str(case["state"]),
                       "GRADLE_USER_HOME": str(case["state"] / "gradle-home"),
                       "MODEL_UNCHANGED": "outer environment", **{name: str(process) for name in ("TEMP", "TMP", "TMPDIR")}}
        case["scope"] = object()
        controller.resources = mock.Mock()
        boundary = RuntimeError("MODEL stopped before launching the immutable executor")
        arguments = [sys.executable, "-B", "scripts/tests/run-audit-command-test.py", "--expected-host", "windows-x64",
                     "--evidence-dir", str(case["state"] / "evidence/native-controls"), "--fixture-parent", str(temporary)]
        original_environment = dict(case["env"])

        def command(argv, cwd, environment, purpose, **options):
            identifier = case["leaves"][-1]["id"]
            self.assertEqual(argv, [sys.executable, "-B", str(ROOT / "scripts/run-audit-command.py"),
                "--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew.bat"), "--id", identifier,
                "--purpose", "executor-native-controls", "--kind", "command", "--timeout", "1800",
                "--stop-timeout", "120", "--receipt", str(case["state"] / "host-executor-native-controls.json"),
                "--", *arguments])
            self.assertEqual((cwd, purpose), (ROOT, "executor-native-controls"))
            self.assertEqual(environment, original_environment)
            self.assertIsNot(environment, case["env"])
            self.assertEqual(options["timeout"], 1950)
            self.assertIs(options["scope"], case["scope"])
            self.assertTrue(callable(options["cancellation"]))
            raise boundary

        controller.command = mock.Mock(side_effect=command)
        with self.assertRaises(RuntimeError) as raised:
            controller.native_controls(case)
        self.assertIs(raised.exception, boundary)
        controller.command.assert_called_once()
        controller.resources.assert_called_once_with(starting=True)
        self.assertEqual(case["env"], original_environment)
        self.assertFalse(case["nativeAccepted"])
        with self.assertRaises(TypeError):
            controller.leaf(case, "executor-native-controls", arguments, kind="command", extra_env={"TEMP": str(temporary)})

    def sdk_admission(self, *, install_fails=False, after="unchanged"):
        """Real caller/formatter and local file reads; Windows paths/processes are modeled."""
        controller, case, _ = self.native_model()
        directory = case["state"].parent
        local_sdk = directory / "sdk"
        raw = {"cmdline-tools/latest/bin/sdkmanager.bat": b"MODEL_ONLY_NOT_AN_EXECUTABLE\n",
               "cmdline-tools/latest/source.properties": b"Pkg.Revision=19.0\nPRIVATE_MODEL_VALUE=do-not-publish\n",
               "platforms/android-36/source.properties": b"AndroidVersion.ApiLevel=36\n",
               "platforms/android-37.0/source.properties": b"AndroidVersion.ApiLevel=37.0\n"}
        for name, value in raw.items():
            path = local_sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)

        class SdkPath(C.PureWindowsPath):
            def resolve(self, *, strict):
                self_test.assertTrue(strict)
                self_test.assertTrue(local(self).exists())
                return self

            def is_dir(self):
                return local(self).is_dir()

            def is_file(self):
                return local(self).is_file()

        self_test = self
        sdk = SdkPath(r"C:\Program Files (x86)\Android\android-sdk")

        def local(path):
            return local_sdk.joinpath(*path.relative_to(sdk).parts) if isinstance(path, SdkPath) else path

        case["env"] = {"ANDROID_HOME": str(sdk)}
        calls, commands = [], []
        original_install = C.CommandFailure("MODEL SDK install failed", directory / "capture", 23)
        native_boundary = RuntimeError("MODEL native suite deliberately not executed")
        expected = [r"C:\Program Files (x86)\Android\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat",
                    r"--sdk_root=C:\Program Files (x86)\Android\android-sdk",
                    "platforms;android-36", "platforms;android-37.0"]

        def leaf(actual_case, purpose, arguments, **options):
            self.assertIs(actual_case, case)
            calls.append((purpose, arguments, options))
            if purpose == "wrapper-version":
                self.assertEqual((arguments, options), (["--version"], {"timeout": 600}))
            elif purpose == "sdk-install":
                self.assertEqual((arguments, options), (expected, {"kind": "command", "timeout": 900}))
                command = C.processes.batch_command_line(r"C:\Windows\System32\cmd.exe", arguments)
                commands.append(command)
                self.assertEqual(command, 'C:\\Windows\\System32\\cmd.exe /d /s /v:off /c "'
                    '"C:\\Program Files (x86)\\Android\\android-sdk\\cmdline-tools\\latest\\bin\\sdkmanager.bat" '
                    '"--sdk_root=C:\\Program Files (x86)\\Android\\android-sdk" '
                    '"platforms;android-36" "platforms;android-37.0""')
                properties = local_sdk / "cmdline-tools/latest/source.properties"
                if after == "drift":
                    properties.write_bytes(b"MODEL changed package bytes\n")
                elif after == "missing":
                    properties.unlink()
                if install_fails:
                    raise original_install
            else:
                self.assertEqual(purpose, "executor-native-controls")
                raise native_boundary

        controller.leaf = mock.Mock(side_effect=leaf)
        original_regular, original_json = C.regular, C.new_json

        def write_json(path, value):
            if after == "write-failed" and path.name == "sdk-tool-after.json":
                raise OSError("MODEL snapshot storage failure")
            return original_json(path, value)

        with mock.patch.object(C, "Path", side_effect=SdkPath), \
                mock.patch.dict(os.environ, {"ANDROID_SDK_ROOT": ""}), \
                mock.patch.object(C, "regular", side_effect=lambda path, limit=C.MAX_FILE: original_regular(local(path), limit)), \
                mock.patch.object(C, "new_json", side_effect=write_json):
            try:
                controller.sdk_and_native(case)
            except Exception as error:
                outcome = error
            else:
                self.fail("Modeled SDK caller unexpectedly ran past its native boundary")
        return {"error": outcome, "installError": original_install, "nativeBoundary": native_boundary,
                "public": controller.public / "admission", "case": case, "calls": calls, "commands": commands,
                "expectedBefore": {"schema": 1, "files": {name: {"bytes": len(raw[name]), "sha256": C.digest(raw[name])}
                    for name in raw if name.startswith("cmdline-tools/")}}}

    def test_sdk_caller_formats_actual_parenthesized_location_before_native_boundary(self):
        result = self.sdk_admission()
        self.assertIs(result["error"], result["nativeBoundary"])
        self.assertEqual([call[0] for call in result["calls"]], ["wrapper-version", "sdk-install", "executor-native-controls"])
        self.assertEqual(len(result["commands"]), 1)
        before = C.read_json(result["public"] / "sdk-tool-before.json")
        after = C.read_json(result["public"] / "sdk-tool-after.json")
        self.assertEqual(before, result["expectedBefore"])
        self.assertEqual(after, {**before, "unchanged": True, "errors": []})
        self.assertNotIn("PRIVATE_MODEL_VALUE", json.dumps([before, after]))
        self.assertEqual(C.read_json(result["public"] / "sdk.json")["android-37.0"]["api"], "37.0")
        self.assertEqual(result["case"]["retentionErrors"], [])

    def test_sdk_post_binding_failure_blocks_native_and_keeps_original_install_error(self):
        for install_fails in (False, True):
            for after in ("drift", "missing", "write-failed"):
                with self.subTest(install_fails=install_fails, after=after):
                    result = self.sdk_admission(install_fails=install_fails, after=after)
                    if install_fails:
                        self.assertIs(result["error"], result["installError"])
                        self.assertEqual(result["error"].status, 23)
                    else:
                        self.assertIsInstance(result["error"], C.audit.AuditError)
                        self.assertIn("SDK tool binding/retention failed", str(result["error"]))
                    self.assertEqual([call[0] for call in result["calls"]], ["wrapper-version", "sdk-install"])
                    self.assertFalse(result["case"]["nativeStarted"])
                    self.assertTrue(result["case"]["retentionErrors"])
                    self.assertEqual(C.read_json(result["public"] / "sdk-tool-before.json"), result["expectedBefore"])
                    if after != "write-failed":
                        record = C.read_json(result["public"] / "sdk-tool-after.json")
                        self.assertFalse(record["unchanged"])
                        self.assertEqual(record["errors"], ["AuditError" if after == "drift" else "FileNotFoundError"])
                    else:
                        self.assertFalse((result["public"] / "sdk-tool-after.json").exists())

    def test_sdk_install_failure_retains_hash_snapshots_without_becoming_success(self):
        result = self.sdk_admission(install_fails=True)
        self.assertIs(result["error"], result["installError"])
        self.assertEqual(result["error"].status, 23)
        self.assertEqual([call[0] for call in result["calls"]], ["wrapper-version", "sdk-install"])
        self.assertFalse(result["case"]["nativeStarted"])
        self.assertEqual(C.read_json(result["public"] / "sdk-tool-after.json"),
                         {**result["expectedBefore"], "unchanged": True, "errors": []})

    def test_sdk_tool_fingerprint_is_bounded_and_never_copies_raw_launcher(self):
        sdk = self.base / "sdk"
        values = {"cmdline-tools/latest/bin/sdkmanager.bat": b"PRIVATE_MODEL_LAUNCHER\x00\xff\n",
                  "cmdline-tools/latest/source.properties": b"Pkg.Revision=19.0\n"}
        for name, value in values.items():
            path = sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        self.assertEqual(C.sdk_tool_snapshot(sdk), {"schema": 1, "files": {
            name: {"bytes": len(value), "sha256": C.digest(value)} for name, value in values.items()}})
        launcher = sdk / "cmdline-tools/latest/bin/sdkmanager.bat"
        launcher.write_bytes(b"x" * (256 * 1024 + 1))
        self.rejects(lambda: C.sdk_tool_snapshot(sdk))
        self.assertTrue(C.public_path("sdk-tool-before.json"))
        self.assertTrue(C.public_path("sdk-tool-after.json"))
        self.assertFalse(C.public_path("sdkmanager.bat"))
        self.assertFalse(C.public_path("source.properties"))

    def java_admission(self, captures, *, failed=None, error=C.audit.AuditError):
        """Exercise the real admission caller; only native/process boundaries are fake."""
        with tempfile.TemporaryDirectory(prefix="java-admission-", dir=self.base) as temporary:
            directory = Path(temporary).resolve()
            controller = C.Controller.__new__(C.Controller)
            controller.root, controller.public = directory, directory / "public"
            (controller.public / "admission").mkdir(parents=True)
            controller.resources = mock.Mock(return_value={"scope": "MODEL_ONLY_NOT_NATIVE"})
            controller.env = {}
            originals, homes, outputs = {}, {}, {}
            for label, variable in (("java17", "JAVA_HOME"), ("java21", "P2PKIT_AUDIT_JDK21")):
                home = directory / label
                (home / "bin").mkdir(parents=True)
                for name in ("bin/java.exe", "bin/javac.exe", "release"):
                    (home / name).write_bytes(b"MODEL_ONLY_NOT_AN_EXECUTABLE\n")
                homes[label] = home
                controller.env[variable] = str(home)
                output = directory / (label + "-capture")
                output.mkdir()
                code, stdout, stderr = captures[label]
                outputs[label] = (code, output)
                for name, raw in (("stdout.log", stdout), ("stderr.log", stderr),
                                  ("command.json", b'{"scope":"MODEL_ONLY_NOT_HOSTED"}\n')):
                    path = output / name
                    path.write_bytes(raw)
                    originals[path] = (raw, C.digest(raw))

            def command(argv, root, env, label):
                self.assertEqual(argv, [str(homes[label] / "bin/java.exe"), "-XshowSettings:properties", "-version"])
                self.assertEqual(root, controller.root)
                self.assertIs(env, controller.env)
                return outputs[label]

            controller.command = mock.Mock(side_effect=command)
            with mock.patch.object(C.processes, "host_role", return_value="windows-x64"), \
                    mock.patch.object(C.sys, "platform", "win32"), \
                    mock.patch.object(C.struct, "calcsize", return_value=8), \
                    mock.patch.object(C, "pe_amd64") as pe:
                if failed is None:
                    controller.admit_tools()
                else:
                    with self.assertRaises(error):
                        controller.admit_tools()
                attempted = ["java17"] if failed == "java17" else ["java17", "java21"]
                self.assertEqual([call.args[3] for call in controller.command.call_args_list], attempted)
                self.assertEqual(pe.call_args_list, [mock.call(homes[label] / "bin" / name)
                    for label in attempted for name in ("java.exe", "javac.exe")])

            for path, (raw, sha256) in originals.items():
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(C.digest(path.read_bytes()), sha256)
                label = path.parent.name.removesuffix("-capture")
                copied = controller.public / "admission" / label / path.name
                accepted = failed is None or failed == "java21" and label == "java17"
                self.assertEqual(copied.exists(), accepted)
                if accepted:
                    self.assertEqual(copied.read_bytes(), raw)
                    self.assertEqual(C.digest(copied.read_bytes()), sha256)
            tools = controller.public / "admission/tools.json"
            self.assertEqual(tools.exists(), failed is None)
            if failed is None:
                evidence = C.read_json(tools)
                self.assertEqual(set(evidence["java"]), {"java17", "java21"})
                for label in homes:
                    self.assertEqual(evidence["java"][label]["home"], str(homes[label]))
                    self.assertEqual(evidence["java"][label]["javaSha256"], C.digest(b"MODEL_ONLY_NOT_AN_EXECUTABLE\n"))

    @staticmethod
    def java_properties(version, ending=b"\n"):
        return ending.join((b"Property settings:", b"    java.version = " + version + b".0.1",
                            b"    os.arch = amd64", b"    os.name = Windows Server 2025", b""))

    def test_java_admission_accepts_lf_and_crlf_without_rewriting_evidence(self):
        for ending in (b"\n", b"\r\n"):
            for channel in ("stdout", "stderr"):
                with self.subTest(ending=ending, channel=channel):
                    captures = {"java" + version.decode(): (0,
                        self.java_properties(version, ending) if channel == "stdout" else b"",
                        self.java_properties(version, ending) if channel == "stderr" else b"")
                        for version in (b"17", b"21")}
                    self.java_admission(captures)

    def test_java_admission_rejects_bad_fields_exits_and_encoding_in_each_jdk(self):
        for label, version in (("java17", b"17"), ("java21", b"21")):
            good = self.java_properties(version)
            cases = {
                "wrong-major": good.replace(version + b".0.1", b"11.0.1"),
                "other-admitted-major": good.replace(version + b".0.1", (b"21" if version == b"17" else b"17") + b".0.1"),
                "wrong-architecture": good.replace(b"amd64", b"aarch64"),
                "wrong-os": good.replace(b"Windows Server 2025", b"Linux"),
                "missing-version": good.replace(b"    java.version = " + version + b".0.1\n", b""),
                "missing-architecture": good.replace(b"    os.arch = amd64\n", b""),
                "missing-os": good.replace(b"    os.name = Windows Server 2025\n", b""),
                "missing-dot": good.replace(version + b".0.1", version),
                "empty-version-suffix": good.replace(version + b".0.1", version + b"."),
                "embedded-version-cr": good.replace(version + b".0.1", version + b".0\r.1"),
                "embedded-architecture-cr": good.replace(b"amd64", b"am\rd64"),
                "embedded-os-cr": good.replace(b"Windows Server", b"Windows\rServer"),
                "bare-cr-delimiters": good.replace(b"\n", b"\r"),
                "invalid-utf8": good + b"\xff",
                "nonzero-exit": good,
            }
            for name, raw in cases.items():
                with self.subTest(jdk=label, case=name):
                    captures = {"java" + major.decode(): (0, b"", self.java_properties(major)) for major in (b"17", b"21")}
                    captures[label] = (1 if name == "nonzero-exit" else 0, b"", raw)
                    self.java_admission(captures, failed=label,
                                        error=UnicodeDecodeError if name == "invalid-utf8" else C.audit.AuditError)

    def test_exact_method_preimage_and_unchanged_historical_witness(self):
        changed = C.transform(self.current, self.historical, self.test, self.old_test)
        self.assertEqual(C.digest(changed), C.PREIMAGE_SHA)
        self.assertEqual(changed.replace(C.OLD_METHOD, C.CURRENT_METHOD), self.current)
        self.assertEqual(self.parent, C.PRE_FIX)
        for index, replacement in ((0, self.current.replace(b"\n", b"\r\n")), (0, self.current + b"\n"),
                (1, self.historical + b"\n"), (2, self.test.replace(b"\n", b"\r\n")),
                (3, self.old_test.replace(C.METHOD.encode(), b"differentMethod"))):
            values = [self.current, self.historical, self.test, self.old_test]
            values[index] = replacement
            with self.subTest(index=index):
                self.rejects(lambda: C.transform(*values))

    def test_only_one_method_file_tree_delta_is_admitted(self):
        before = {C.SOURCE: {"mode": "100644", "sha256": C.CURRENT_SHA}, "lockfile": {"sha256": "fixed"}}
        after = copy.deepcopy(before)
        after[C.SOURCE]["sha256"] = C.PREIMAGE_SHA
        C.tree_delta(before, after)
        for mutate in (lambda v: v.update(extra={}), lambda v: v["lockfile"].update(sha256="changed"),
                       lambda v: v[C.SOURCE].update(mode="100755"), lambda v: v[C.SOURCE].update(sha256=C.CURRENT_SHA)):
            changed = copy.deepcopy(after)
            mutate(changed)
            self.rejects(lambda: C.tree_delta(before, changed))

    def materialization(self, inherited, failure=None, *, source_admission=False, case_name="current"):
        """Real producer caller/consumer; Git configuration lookup is only modeled."""
        with tempfile.TemporaryDirectory(prefix="materialize-", dir=self.base) as temporary:
            directory = Path(temporary)
            controller = C.Controller.__new__(C.Controller)
            controller.root, controller.state = directory / "campaign", directory / "state"
            controller.root.mkdir()
            controller.state.mkdir()
            controller.identity = {"sourceSha": "a" * 40, "scope": "MODEL_ONLY_NOT_HOSTED"}
            controller.env = {"SCOPE": "MODEL_ONLY_NOT_HOSTED"}
            parent = directory / case_name
            root = parent / "source"
            root.mkdir(parents=True)
            case = {"parent": parent, "root": root, "public": directory / "public"}
            case["public"].mkdir()
            archive = parent / "source.tar"
            receipt = case["public"] / "source-materialization.json"
            value = b"source\n"
            name = "/".join(["nested" * 10] * 4 + ["source.kt"]) if source_admission else "dir/source.kt"
            if source_admission:
                self.assertGreaterEqual(len(str(root / name)), 260)
            blob = hashlib.sha1(b"blob 7\0" + value).hexdigest()
            listing = ("100644 blob " + blob + " 7\t" + name + "\0").encode()
            trace, captures, produced, plain_queries = [], {}, {}, []
            # Persisted repository-local policy is modeled separately from any
            # command-local -c option. The campaign repository must stay unchanged.
            policies = {str(controller.root): "false", str(root): "false"}
            command_failure = []
            if failure == "existing":
                archive.write_bytes(b"existing transport sentinel\n")
            git_prefix = ["git", "--no-replace-objects", "-c", "core.autocrlf=false", "-c", "core.fsmonitor=false",
                          "-c", "commit.gpgSign=false", "-c", "core.hooksPath=" + str(controller.state), "-C", str(root)]
            git_commands = [["config", "--local", "core.longpaths", "true"],
                            ["config", "--bool", "--get", "core.longpaths"],
                            ["update-ref", "--no-deref", "HEAD", "a" * 40], ["read-tree", "a" * 40],
                            ["ls-tree", "-rlz", "a" * 40]]

            def source_query(cwd, args):
                self.assertEqual(cwd, root)
                dirty = source_admission and policies[str(cwd)] != "true"
                if args == ["rev-parse", "--show-toplevel"]:
                    return os.fsencode(root) + b"\n"
                if args == ["rev-parse", "HEAD"]:
                    return b"a" * 40 + b"\n"
                if args == ["rev-parse", "HEAD^{tree}"]:
                    return b"b" * 40 + b"\n"
                if args == ["rev-parse", "--is-shallow-repository"]:
                    return b"false\n"
                if args in (["status", "--porcelain=v1", "--untracked-files=all"],
                            ["status", "--porcelain=v1", "--untracked-files=all", "--ignored"]):
                    return (" M " + name + "\n").encode() if dirty else b""
                if args == ["diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD"]:
                    return b"MODEL long path inaccessible\n" if dirty else b""
                if args in (["ls-tree", "-rlz", "a" * 40], ["ls-tree", "-rlz", "HEAD"]):
                    return listing
                self.fail("Unexpected modeled source query: " + repr(args))

            def command(argv, cwd, env, label, timeout, finalizing=False):
                trace.append({"argv": argv, "cwd": str(cwd), "env": env, "label": label,
                              "timeout": timeout, "finalizing": finalizing})
                self.assertEqual(env, controller.env)
                self.assertFalse(finalizing)
                stdout, code = b"model stdout sentinel\n", 0
                if label == "source-clone":
                    self.assertEqual(argv, ["git", "-c", "core.autocrlf=false", "clone", "--no-local", "--no-hardlinks",
                                          "--no-checkout", "--", str(controller.root), str(root)])
                    self.assertEqual((cwd, timeout), (controller.root, 180))
                    code = 17 if failure == "clone" else 0
                elif label == "git":
                    self.assertEqual(argv[:len(git_prefix)], git_prefix)
                    self.assertEqual((cwd, timeout), (root, 120))
                    args = argv[len(git_prefix):]
                    stdout = b""
                    if args == git_commands[0]:
                        code = 23 if failure == "config-write" else 0
                        if code == 0 and failure != "config-not-persisted":
                            policies[str(cwd)] = "true"
                    elif args == git_commands[1]:
                        code = 29 if failure == "config-read" else 0
                        stdout = {"config-empty": b"", "config-false": b"false\n",
                                  "config-multiple": b"true\nfalse\n"}.get(
                                      failure, policies[str(cwd)].encode() + b"\n")
                    elif args not in git_commands[2:4]:
                        stdout = source_query(cwd, args)
                    trace[-1]["modeledPersistedLongpaths"] = policies[str(cwd)]
                elif label == "source-archive":
                    self.assertEqual((cwd, timeout), (root, 120))
                    index = argv.index("archive")
                    self.assertEqual(argv[index:], ["archive", "--format=tar", "--output=" + str(archive), "a" * 40])
                    options = [argv[i + 1].split("=", 1)[1] for i in range(index) if argv[i] == "-c"
                               and argv[i + 1].startswith("core.autocrlf=")]
                    effective = options[-1] if options else inherited
                    trace[-1].update(modeledInheritedAutocrlf=inherited, archiveOverrides=options,
                                     modeledEffectiveAutocrlf=effective)
                    payload = value.replace(b"\n", b"\r\n") if effective == "true" or failure == "bytes" else value
                    buffer = io.BytesIO()
                    with tarfile.open(fileobj=buffer, mode="w") as stream:
                        member = tarfile.TarInfo(name)
                        member.size = len(payload)
                        stream.addfile(member, io.BytesIO(payload))
                    produced["raw"] = buffer.getvalue()
                    archive.write_bytes(produced["raw"])
                    code = 19 if failure in ("archive", "infrastructure") else 0
                else:
                    self.fail("Unexpected materialization command: " + label)
                output = directory / ("capture-" + str(len(trace)))
                output.mkdir()
                trace[-1]["exitCode"] = code
                for filename, raw in (("stdout.log", stdout), ("stderr.log", b"model stderr sentinel\n"),
                                      ("command.json", json.dumps(trace[-1], sort_keys=True).encode())):
                    path = output / filename
                    path.write_bytes(raw)
                    captures[path] = raw
                if failure == "infrastructure" and label == "source-archive":
                    error = C.CommandFailure("MODEL command infrastructure failed", output, code)
                    command_failure.append(error)
                    raise error
                return code, output

            controller.command = mock.Mock(side_effect=command)
            expected_error = {"clone": "Fresh full-history source clone failed", "archive": "Source archive command failed",
                              "infrastructure": "MODEL command infrastructure failed", "existing": "Source transport path already exists",
                              "bytes": "Linked, missing, extra, duplicate or oversized archive member",
                              "config-write": "Source-binding Git command failed; retained original output",
                              "config-read": "Source-binding Git command failed; retained original output",
                              **{name: "Owned source Git long-path policy was not established" for name in
                                 ("config-empty", "config-false", "config-multiple", "config-not-persisted")}}
            try:
                with mock.patch.object(C, "export_archive", wraps=C.export_archive) as export:
                    if failure:
                        with self.assertRaisesRegex(C.audit.AuditError, "^" + expected_error[failure] + "$") as raised:
                            controller.materialize(case)
                        if failure == "infrastructure":
                            self.assertIs(raised.exception, command_failure[0])
                            self.assertEqual(raised.exception.status, 19)
                    else:
                        controller.materialize(case)
                    preparation = list(trace)
                    if source_admission and failure is None:
                        # Reach the real clean-source guard before testing argv
                        # structure, so the pre-repair red is not a mock error.
                        admitted = controller.source(root, "a" * 40, initial=True)
                        self.assertEqual(set(admitted["files"]), {name})

                        def ordinary_git(cwd, *args):
                            plain_queries.append({"root": str(cwd), "args": args})
                            return source_query(cwd, list(args))

                        # The immutable executor does not use Controller.git or
                        # its -c overrides; it must inherit the persisted policy.
                        with mock.patch.object(C.audit, "git", side_effect=ordinary_git):
                            self.assertEqual(C.audit.source_snapshot(root), admitted["source"])
                        self.assertEqual(len(plain_queries), 5)
                    config_failure = failure is not None and failure.startswith("config-")
                    count = 0 if failure == "clone" else 1 if failure == "config-write" else 2 if config_failure else 5
                    attempted = ["source-clone"] + ["git"] * count
                    if failure not in ("clone", "existing") and not config_failure:
                        attempted.append("source-archive")
                    self.assertEqual([row["label"] for row in preparation], attempted)
                    self.assertEqual([row["argv"][len(git_prefix):] for row in preparation if row["label"] == "git"],
                                     git_commands[:count])
                    self.assertEqual(policies[str(controller.root)], "false")
                    if failure is None or failure == "bytes":
                        export.assert_called_once()
                        self.assertEqual(export.call_args.args, (produced["raw"], C.tree_entries(listing), root))
                    else:
                        export.assert_not_called()
                for path, raw in captures.items():
                    self.assertEqual(path.read_bytes(), raw, "Original command capture changed")
                self.assertEqual(receipt.exists(), failure is None)
                if failure is None:
                    self.assertEqual((root / name).read_bytes(), value)
                    self.assertEqual(preparation[-1]["archiveOverrides"], ["false"])
                    self.assertEqual(preparation[-1]["argv"], ["git", "--no-replace-objects", "-c", "core.autocrlf=false",
                        "-C", str(root), "archive", "--format=tar", "--output=" + str(archive), "a" * 40])
                    self.assertEqual(C.read_json(receipt), {"schema": 1, "commit": "a" * 40,
                        "archiveSha256": C.digest(produced["raw"]), "archiveBytes": len(produced["raw"]),
                        "fileCount": 1, "sourceBytes": len(value), "everyBlobVerified": True})
                    self.assertFalse(archive.exists())
                elif failure == "existing":
                    self.assertEqual(archive.read_bytes(), b"existing transport sentinel\n")
                elif failure == "clone" or config_failure:
                    self.assertFalse(archive.exists())
                else:
                    self.assertEqual(archive.read_bytes(), produced["raw"])
            finally:
                # Optional private retention never changes the production caller
                # or turns these modeled Git boundaries into real host evidence.
                destination = os.environ.get("P2PKIT_TEST_WINDOWS_MATERIALIZE_EVIDENCE")
                if destination:
                    retained = Path(destination) / directory.name
                    retained.mkdir(parents=True)
                    record = {"scope": "MODEL_ONLY_NOT_GIT_CONFIG_OR_HOSTED_EXECUTION", "test": self.id(),
                              "inherited": inherited, "failure": failure, "commands": trace,
                              "plainGitQueries": plain_queries, "modeledPolicies": policies,
                              "sourceAdmission": source_admission, "caseName": case_name,
                              "controllerSha256": C.digest(Path(C.__file__).read_bytes())}
                    (retained / "trace.json").write_text(json.dumps(record, indent=2) + "\n")
                    for path in (*captures, archive, receipt, root / name):
                        if path.is_file():
                            target = retained / path.relative_to(directory)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(path.read_bytes())

    def test_materialize_preserves_blobs_under_modeled_inherited_git_policy(self):
        for inherited in ("true", "false"):
            with self.subTest(inherited=inherited):
                self.materialization(inherited)

    def test_materialize_preserves_failures_and_original_transport(self):
        for failure in ("clone", "archive", "infrastructure", "bytes", "existing"):
            with self.subTest(failure=failure):
                self.materialization("false", failure)

    def test_materialize_persists_longpaths_for_source_and_immutable_callers(self):
        for case_name in ("current", "preimage"):
            with self.subTest(case_name=case_name):
                self.materialization("true", source_admission=True, case_name=case_name)

    def test_materialize_rejects_failed_or_unestablished_owned_longpath_policy(self):
        for failure in ("config-write", "config-read", "config-empty", "config-false", "config-multiple",
                        "config-not-persisted"):
            with self.subTest(failure=failure):
                self.materialization("true", failure)

    def test_windows_tree_paths_and_archive_blob_bytes(self):
        def row(name, value=b"source\n", mode=b"100644"):
            blob = hashlib.sha1(b"blob " + str(len(value)).encode() + b"\0" + value).hexdigest().encode()
            return mode + b" blob " + blob + b" " + str(len(value)).encode() + b"\t" + name.encode() + b"\0"
        entries = C.tree_entries(row("dir/source.kt"))
        def archive(names):
            output = io.BytesIO()
            with tarfile.open(fileobj=output, mode="w") as stream:
                for name, value, kind in names:
                    info = tarfile.TarInfo(name)
                    info.size, info.type = len(value), kind
                    stream.addfile(info, io.BytesIO(value))
            return output.getvalue()
        root = self.base / "source"
        root.mkdir()
        C.export_archive(archive([("dir/source.kt", b"source\n", tarfile.REGTYPE)]), entries, root)
        self.assertEqual((root / "dir/source.kt").read_bytes(), b"source\n")
        for name in ("../source.kt", "C:/source.kt", ".git/config", "dir\\source.kt", "dir./file", "con.txt", "a:stream"):
            with self.subTest(name=name):
                self.rejects(lambda: C.tree_entries(row(name)))
        for raw in (row("dir/A") + row("DIR/b"), row("a") + row("a/b"), row("A") + row("a"),
                    row("link", mode=b"120000"), row("a")[:-1]):
            self.rejects(lambda: C.tree_entries(raw))
        valid = ("dir/source.kt", b"source\n", tarfile.REGTYPE)
        guard = "Linked, missing, extra, duplicate or oversized archive member"
        cases = [([], "Archive omitted a tracked source"),
                 ([("dir/source.kt", b"source\r\n", tarfile.REGTYPE)], guard),
                 ([("../source.kt", b"source\n", tarfile.REGTYPE)], "Unsafe or ambiguous Windows source pathname"),
                 ([("dir/source.kt", b"", tarfile.SYMTYPE)], guard),
                 ([valid, ("extra.kt", b"extra\n", tarfile.REGTYPE)], guard),
                 ([valid, valid], guard),
                 ([("dir/source.kt", b"wrong!\n", tarfile.REGTYPE)], "Archive bytes differ from Git blob")]
        for index, (members, message) in enumerate(cases):
            with self.subTest(archive_case=index), self.assertRaisesRegex(C.audit.AuditError, message):
                C.export_archive(archive(members), entries, self.base / ("unused-" + str(index)))

    def test_dispatch_rejects_forged_or_incomplete_identity_models(self):
        env, event, source = dispatch()
        self.assertEqual(C.dispatch_identity(env, event, source)["runAttempt"], "2")
        for key, value in (("P2PKIT_EXPECTED_SHA", "main"), ("P2PKIT_EXPECTED_TREE", ""),
                ("GITHUB_SHA", "e" * 40), ("GITHUB_WORKFLOW_SHA", "e" * 40), ("GITHUB_EVENT_NAME", "push"),
                ("GITHUB_REF", "refs/heads/audit/complete-2026-09-04"), ("GITHUB_RUN_ATTEMPT", "0"),
                ("RUNNER_ARCH", "ARM64"), ("RUNNER_ENVIRONMENT", "self-hosted"), ("P2PKIT_OPERATION", "unknown")):
            changed = dict(env, **{key: value})
            self.rejects(lambda: C.dispatch_identity(changed, event, source))
        for changed in (dict(source, status=" M source"), dict(source, diffSha256="f" * 64), dict(source, tree="f" * 40)):
            self.rejects(lambda: C.dispatch_identity(env, event, changed))
        event["inputs"]["extra"] = "arbitrary command"
        self.rejects(lambda: C.dispatch_identity(env, event, source))

    def test_environment_preserves_domains_but_not_credentials_or_ambient_options(self):
        base = C.processes.ownership_environment({"PATH": "model", "GH_TOKEN": "never retain", "MAVEN_PASSWORD": "never retain"},
                                                "a" * 32, "b" * 32, "state", "home", allow_new_context=True)
        selected = C.controlled_environment(base)
        self.assertNotIn("GH_TOKEN", selected)
        self.assertNotIn("MAVEN_PASSWORD", selected)
        for key in (C.processes.CHAIN_ENV, C.processes.DOMAINS_ENV, C.processes.STATE_ENV, C.processes.JOB_ENV):
            self.assertEqual(selected[key], base[key])
        for key in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "GIT_DIR"):
            self.rejects(lambda: C.controlled_environment(dict(base, **{key: "injected"})))

    def test_context_reuse_and_incomplete_retention_block_disposal(self):
        case = {"root": self.base / "source", "state": self.base / "state", "before": {"source": dispatch()[2]},
            "initialized": True, "leaves": [{"valid": True, "retained": True}], "retentionErrors": [],
            "productPrepared": True, "productRetained": True, "nativeStarted": True, "nativeAccepted": True}
        env = {"JAVA_HOME": "jdk17", "P2PKIT_AUDIT_JDK21": "jdk21"}
        context = {"root": str(case["root"]), "gradleHome": str(case["state"] / "gradle-home"), "host": "windows-x64",
            "source": case["before"]["source"], "expectedCommit": "a" * 40, "tree": "b" * 40,
            "preexistingOutputPaths": [], "javaHomes": ["jdk17", "jdk21"]}
        C.prepared_context(case["state"], context, case, env)
        C.require_disposal_evidence(case)
        for key, value in (("root", "foreign"), ("gradleHome", "reused"), ("preexistingOutputPaths", ["build"]),
                           ("expectedCommit", "e" * 40), ("javaHomes", ["jdk21", "jdk17"])):
            self.rejects(lambda: C.prepared_context(case["state"], dict(context, **{key: value}), case, env))
        for key, value in (("initialized", False), ("leaves", [{"valid": False, "retained": True}]),
                ("leaves", [{"valid": True, "retained": False}]), ("retentionErrors", ["lost XML"]),
                ("productRetained", False), ("nativeAccepted", False)):
            self.rejects(lambda: C.require_disposal_evidence(dict(case, **{key: value})))

    def test_exact_selected_junit_and_native_failure_path(self):
        for negative in (False, True):
            req = request(negative)
            original = xml(req)
            self.assertEqual(C.assess_xml(raw_xml(original), req),
                             req["testTemporary"] + r"\p2pkit-durable-destination-1234" if negative else None)
            mutations = [lambda s: s.set("tests", "0"), lambda s: s.set("skipped", "1"),
                lambda s: s.append(copy.deepcopy(s.find("testcase"))), lambda s: s.find("testcase").set("name", "other"),
                lambda s: ET.SubElement(s.find("testcase"), "error")]
            if negative:
                mutations += [lambda s: s.find("testcase/failure").set("type", "java.io.IOException"),
                    lambda s: setattr(s.find("testcase/failure"), "text", "compilation failure"),
                    lambda s: setattr(s.find("testcase/failure"), "text", s.find("testcase/failure").text.replace(
                        "syncParentDirectory", "unrelatedMethod")),
                    lambda s: setattr(s.find("testcase/failure"), "text", s.find("testcase/failure").text.replace(
                        "p2pkit-durable-destination-1234", "received.bin"))]
            for mutate in mutations:
                changed = copy.deepcopy(original)
                mutate(changed)
                self.rejects(lambda: C.assess_xml(raw_xml(changed), req))
        self.rejects(lambda: C.assess_xml(b'<!DOCTYPE fake [<!ENTITY x "y">]><testsuite/>', request()))

    def test_execution_requires_exact_root_or_direct_parent_binding(self):
        # Report/assessor models, not actual Gradle parent or hosted observations.
        for scope in ("root", "buildSrc"):
            req, original = request(), execution(request(), scope)
            C.assess_execution(original, req, "d" * 64, scope)
            complete = execution(req)["binding"]["localProperties"]
            if scope == "buildSrc":
                copied = copy.deepcopy(original)
                copied["binding"]["localProperties"] = complete
                C.assess_execution(copied, req, "d" * 64, scope)
            mutations = [lambda v: v.pop("binding"), lambda v: v.update(binding=None),
                lambda v: v["binding"].update(authority="ancestor"),
                lambda v: v["binding"].update(parentHasParent=True),
                lambda v: v["binding"].update(parentHasParent=0),
                lambda v: v["binding"].update(parentRoot=r"C:\foreign\source"),
                lambda v: v["binding"].update(extra="unrecorded authority"),
                lambda v: v["binding"].update(localProperties=None),
                lambda v: v["binding"].update(localProperties={"p2pkit.windowsDirectoryRoot": req["root"]}),
                lambda v: v["binding"].update(localProperties={**complete, "p2pkit.windowsDirectoryRequestSha256": "e" * 64}),
                lambda v: v["binding"].update(localProperties={**complete, "p2pkit.windowsDirectoryRequest": ""}),
                lambda v: v["binding"].update(localProperties={**complete, "unrelated": "must not be dumped"}),
                lambda v: v.update(nonce="e" * 32), lambda v: v.update(source={**req["source"], "commit": "f" * 40}),
                lambda v: v.update(identity={"runId": "stale-valid-run"})]
            if scope == "root":
                mutations += [lambda v: v["binding"].update(localProperties={})]
            else:
                mutations += [lambda v: v["binding"].update(parentRoot=None),
                    lambda v: v["binding"].update(authority="self")]
            for index, mutate in enumerate(mutations):
                with self.subTest(scope=scope, mutation=index):
                    changed = copy.deepcopy(original)
                    mutate(changed)
                    self.rejects(lambda: C.assess_execution(changed, req, "d" * 64, scope))

    def binding_report(self, hashes):
        self.assertEqual(len(C.BINDING_CASES), 24)
        return {"schema": 1, "scope": "MODELED_NEGATIVE_INPUTS_WHOLE_PRODUCTION_OBSERVER", "gradleVersion": "9.7.0",
            "hashes": hashes, "cases": [{"id": name, "passed": True, "expectedMessage": message,
                "exceptionType": "org.gradle.api.GradleException", "message": message}
                for name, message in C.BINDING_CASES.items()]}

    def test_binding_model_report_rejects_omitted_stale_and_wrong_failure_results(self):
        hashes = {name: "e" * 64 for name in ("observer", "settings.gradle", "build.gradle", "gradle/gradle-daemon-jvm.properties")}
        original = self.binding_report(hashes)
        C.assess_binding_controls(original, hashes, require_pass=True)
        mutations = [lambda v: v.update(schema=True), lambda v: v.update(scope="NATIVE_WINDOWS"),
            lambda v: v.update(gradleVersion="9.8.0"), lambda v: v.update(hashes={}),
            lambda v: v["cases"].pop(), lambda v: v["cases"].reverse(),
            lambda v: v["cases"].__setitem__(1, v["cases"][0]), lambda v: v["cases"][0].update(passed=1),
            lambda v: v["cases"][0].update(exceptionType="java.lang.NullPointerException"),
            lambda v: v["cases"][0].update(message="Directory control requires the admitted native Windows JDK21 daemon"),
            lambda v: v["cases"][0].update(expectedMessage="a different error"),
            lambda v: v["cases"][0].update(unboundedRawData="not admitted")]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(original)
                mutate(changed)
                self.rejects(lambda: C.assess_binding_controls(changed, hashes, require_pass=True))
        failed = copy.deepcopy(original)
        failed["cases"][0].update(passed=False, exceptionType="java.lang.NullPointerException", message="MODEL wrong failure")
        C.assess_binding_controls(failed, hashes, require_pass=False)  # Retain the original failed model, never a pass.
        self.rejects(lambda: C.assess_binding_controls(failed, hashes, require_pass=True))

    def binding_adapter(self, variant="pass"):
        controller, case, _ = self.native_model()
        case["nativeAccepted"] = True  # Explicit fake prerequisite; no native suite runs here.
        primary = C.audit.AuditError("MODEL binding leaf failed")

        def leaf(observed_case, purpose, argv, **options):
            self.assertIs(observed_case, case)
            self.assertEqual(purpose, "binding-controls")
            self.assertEqual(options, {"timeout": 300})
            fixture = case["state"] / "fixtures/directory-binding"
            self.assertEqual(argv, ["--project-dir", str(fixture), "verifyWindowsDirectoryBinding", "--console=plain",
                                   "-Pp2pkit.windowsDirectoryObserver=" + str(ROOT / C.OBSERVER)])
            hashes = {"observer": C.digest(C.regular(ROOT / C.OBSERVER))}
            for name in ("settings.gradle", "build.gradle", "gradle/gradle-daemon-jvm.properties"):
                source = ROOT / name if name.startswith("gradle/") else ROOT / C.BINDING_FIXTURE / name
                self.assertEqual((fixture / name).read_bytes(), source.read_bytes())
                hashes[name] = C.digest(source.read_bytes())
            case["leaves"].append({"id": "a" * 32, "purpose": purpose, "arguments": argv})
            if variant == "missing":
                return {"id": "a" * 32, "reports": []}
            original = fixture / "build/reports/windows-directory-binding/result.json"
            original.parent.mkdir(parents=True)
            C.new_json(original, self.binding_report(hashes))
            raw = C.regular(original)
            if variant in ("leaf-failure", "retention-failure"):
                raise primary
            canonical = case["state"] / "evidence" / ("a" * 32) / "reports" / C.BINDING_REPORT
            canonical.parent.mkdir(parents=True)
            canonical.write_bytes(raw + (b"\n" if variant == "tampered" else b""))
            return {"id": "a" * 32, "reports": [{"source": C.BINDING_REPORT, "retained": "reports/" + C.BINDING_REPORT,
                "classification": "preexisting-unchanged" if variant == "stale" else "changed-since-admission",
                "sha256": C.digest(raw), "bytes": len(raw)}]}

        controller.leaf = mock.Mock(side_effect=leaf)
        try:
            if variant == "retention-failure":
                with mock.patch.object(C, "retain_available", side_effect=OSError("MODEL original copy failed")):
                    controller.binding_controls(case)
            else:
                controller.binding_controls(case)
            error = None
        except Exception as caught:
            error = caught
        controller.leaf.assert_called_once()
        return case, primary, error

    def test_binding_adapter_uses_exact_owned_fixture_and_original_canonical_report(self):
        case, _, error = self.binding_adapter()
        self.assertIsNone(error)
        self.assertTrue(case["bindingPrepared"] and case["bindingRetained"])
        self.assertEqual(case["retentionErrors"], [])
        self.assertTrue((case["public"] / "binding-controls.json").is_file())
        self.assertFalse((case["public"] / "binding-controls-unbound.json").exists())
        for variant in ("missing", "stale", "tampered"):
            with self.subTest(variant=variant):
                case, _, error = self.binding_adapter(variant)
                self.assertIsInstance(error, C.audit.AuditError)
                self.assertTrue(case["bindingRetained"])
                self.assertEqual(case["retentionErrors"], [])

    def test_binding_adapter_retains_failed_originals_without_replacing_primary_error(self):
        for variant in ("leaf-failure", "retention-failure"):
            with self.subTest(variant=variant):
                case, primary, error = self.binding_adapter(variant)
                self.assertIs(error, primary)
                self.assertFalse((case["public"] / "binding-controls.json").exists())
                if variant == "leaf-failure":
                    self.assertTrue(case["bindingRetained"])
                    self.assertTrue((case["public"] / "binding-controls-unbound.json").is_file())
                else:
                    self.assertFalse(case["bindingRetained"])
                    self.assertEqual(len(case["retentionErrors"]), 1)
        controller, case, _ = self.native_model()
        self.rejects(lambda: controller.binding_controls(case))
        self.assertFalse((case["state"] / "fixtures/directory-binding").exists())
        case["nativeAccepted"] = True
        fixture = case["state"] / "fixtures/directory-binding"
        fixture.mkdir()
        (fixture / "preserve-me").write_bytes(b"MODEL preexisting content")
        with self.assertRaises(FileExistsError):
            controller.binding_controls(case)
        self.assertEqual((fixture / "preserve-me").read_bytes(), b"MODEL preexisting content")
        for name in ("binding-controls.json", "binding-controls-unbound.json", "binding-controls/receipt.json",
                     "commands/17-binding-controls/stdout.log"):
            self.assertTrue(C.public_path(name))
        for name in ("binding-controls/unknown.json", "binding-controls/payload.bin", "binding-models/request.json"):
            self.assertFalse(C.public_path(name))

    def test_actual_graph_filter_launcher_nonce_and_event_predicates(self):
        for negative in (False, True):
            req, report = request(negative), execution(request(negative))
            C.assess_execution(report, req, "d" * 64)
            C.assess_execution(execution(req, "buildSrc"), req, "d" * 64, "buildSrc")
            mutations = [lambda v: v.update(nonce="stale"), lambda v: v.update(dryRun=True),
                lambda v: v.update(events=[]), lambda v: v["events"].append(copy.deepcopy(v["events"][0])),
                lambda v: v["events"][0].update(skipped=1), lambda v: v["events"][0].update(startMillis=1),
                lambda v: v["admission"].update(commandFilters=["*"]), lambda v: v["admission"].update(ignoreFailures=True),
                lambda v: v["admission"]["launcher"].update(version=21), lambda v: v["admission"].update(maxParallelForks=True),
                lambda v: v["admission"]["jvmArgs"].append("-Dos.name=Windows"),
                lambda v: v["admission"]["jvmArgs"].append(arguments(req)[0]),
                lambda v: v["tasks"][":p2p-core:compileKotlinJvm"].update(outcome="FROM-CACHE"),
                lambda v: v["tasks"][":p2p-core:compileKotlinJvm"].update(outcome="FAILED", failureType="CompilerException")]
            for mutate in mutations:
                changed = copy.deepcopy(report)
                mutate(changed)
                self.rejects(lambda: C.assess_execution(changed, req, "d" * 64))
        req = request()
        command = req["java17"] + r"\bin\java.exe " + " ".join(arguments(req)) + " worker.Main"
        log = ("Starting process 'Gradle Test Executor 1'. Command: " + command +
               "\nSuccessfully started process 'Gradle Test Executor 1'\n").encode()
        C.assess_worker_log(log, req)
        for changed in (log + log, log.replace(b"jdk17", b"jdk21"), log.replace(b"-Xmx512m", b"-Xmx512m -Xmx2g"),
                        log.replace(b" worker.Main", b" -Dos.name=Windows worker.Main")):
            self.rejects(lambda: C.assess_worker_log(changed, req))

    def test_receipt_requires_original_status_stop_context_and_native_launches(self):
        root, state, identifier = self.base / "source", self.base / "state", "e" * 32
        context = {"id": "f" * 32, "gradleHome": str(state / "gradle-home"), "source": dispatch()[2]}
        argv = [C.TASK, "--tests", C.SELECTOR, "--console=plain"]
        executed = [str(root / "gradlew.bat"), *C.audit.gradle_arguments(argv)]
        launches = [{"requestedArgv": args, "cwd": str(root), "created": True, "resumed": True,
                     "jobAssignedBeforeResume": True, "api": "CreateProcessW", "pid": 100 + index}
                    for index, args in enumerate((executed, C.stop_arguments(root)))]
        receipt = {"schema": 1, "id": identifier, "kind": "gradle", "purpose": "product", "host": "windows-x64",
            "cwd": str(root), "wrapper": str(root / "gradlew.bat"), "requestedArgv": argv, "executedArgv": executed,
            "jobId": context["id"], "gradleHome": context["gradleHome"], "evidenceDirectory": str(state / "evidence" / identifier),
            "sourceBefore": context["source"], "sourceAfter": context["source"], "sourceUnchanged": True,
            "productExitCode": 1, "finalExitCode": 1, "stopExitCode": 0, "stopArgv": C.stop_arguments(root),
            "productLaunchIndex": 0, "stopLaunchIndex": 1, "productPid": 100, "errors": [], "ownedSurvivors": [],
            "ownership": {"backend": "windows-job-list-suspended", "scope": "kernel-job-no-breakaway-kill-on-close",
                "job": context["id"], "invocation": identifier, "discoveryErrors": [], "launches": launches,
                "startedIdentities": [{"pid": 100 + i, "creationFileTime": 1000 + i, "jobAssignedBeforeResume": True} for i in range(2)]}}
        check = lambda value, status=1: C.native_receipt(value, context, root, argv, "product", status, identifier, "gradle")
        check(receipt)
        for key, value in (("kind", "command"), ("id", "d" * 32), ("productExitCode", 0), ("stopExitCode", 1),
                ("stopArgv", ["other", "--stop"]), ("cancelRequested", True), ("cancelledSignals", [15]),
                ("ownedSurvivors", [{"pid": 1}]), ("errors", ["failed finalization"]), ("productPid", True),
                ("stopLaunchIndex", 0), ("evidenceDirectory", "another invocation")):
            self.rejects(lambda: check(dict(receipt, **{key: value})))
        for mutate in (lambda v: v["ownership"].update(invocation="wrong"),
                       lambda v: v["ownership"]["launches"][0].update(jobAssignedBeforeResume=False),
                       lambda v: v["ownership"].update(startedIdentities=[])):
            changed = copy.deepcopy(receipt)
            mutate(changed)
            self.rejects(lambda: check(changed))
        self.rejects(lambda: check(receipt, 125))
        row = {"source": "build/test-results/test.xml", "retained": "reports/build/test-results/test.xml",
               "classification": "changed-since-admission", "bytes": 1, "sha256": "a" * 64}
        receipt["reports"] = [row]
        C.assess_report_manifest(receipt, {"schema": 1, "records": [row]})
        self.rejects(lambda: C.assess_report_manifest(receipt, {"schema": 1, "records": [dict(row, bytes=True)]}))

    def test_public_retention_is_allowlisted_canonical_and_tamper_evident(self):
        directory = self.base / "public"
        directory.mkdir()
        C.write(directory / "source.kt", b"reviewed fixture\n")
        identity = {"scope": "MODEL_ONLY_NOT_HOSTED"}
        retained = C.retain_before_disposal(directory, identity, "current")
        C.verify_before_disposal(directory, retained)
        path = directory / "retained-before-disposal.json"
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"schema": 1', b'"schema": true'))
        self.rejects(lambda: C.verify_before_disposal(directory, retained))
        path.write_bytes(original)
        C.seal_public(directory, identity, "current")
        C.verify_public(directory, identity, "current")
        (directory / "source.kt").write_bytes(b"changed\n")
        self.rejects(lambda: C.verify_public(directory, identity, "current"))
        for name in ("../secret", "payload.bin", ".git/config", "native-controls/test_model/arbitrary.json", "state/context.json"):
            try:
                accepted = C.public_path(name)
            except C.audit.AuditError:
                accepted = False
            self.assertFalse(accepted, name)
        self.assertTrue(C.native_public_path("test_model/teardown-" + "a" * 32 + "/invocations/" + "b" * 32 +
                                           "/reports/build/test-results/fixture/result.xml"))
        for kind in ("symlink", "hardlink"):
            target = self.base / (kind + "-target")
            target.write_bytes(b"private sentinel")
            link = self.base / (kind + "-link")
            link.symlink_to(target) if kind == "symlink" else os.link(target, link)
            self.rejects(lambda: C.regular(link))

    def test_native_temporary_observation_is_direct_metadata_only(self):
        controller, case, temporary = self.native_model()
        before = controller.native_temporary(case, "before")
        self.assertTrue(before["complete"] and before["empty"])
        (temporary / "directory").mkdir()
        (temporary / "directory/private.bin").write_bytes(b"PRIVATE_NESTED_CONTENT")
        (temporary / "file.bin").write_bytes(b"PRIVATE_DIRECT_CONTENT")
        original_lstat = Path.lstat
        visited = []

        def lstat(path):
            self.assertNotEqual(path, temporary / "directory/private.bin")
            visited.append(path)
            return original_lstat(path)

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=lstat), \
                mock.patch.object(Path, "read_bytes", side_effect=AssertionError("No content reads")), \
                mock.patch.object(Path, "readlink", side_effect=AssertionError("No target reads")), \
                mock.patch.object(C, "regular", side_effect=AssertionError("No content inventory")):
            after = C.observe_native_temporary(temporary, case["nativeTemporaryIdentity"], time.monotonic() + 5)
        self.assertTrue(after["complete"])
        self.assertFalse(after["empty"])
        self.assertEqual([(row["name"], row["metadata"]["kind"]) for row in after["entries"]],
                         [("directory", "directory"), ("file.bin", "file")])
        self.assertEqual(after["rootBefore"]["inode"], before["expectedRootIdentity"]["inode"])
        self.assertNotIn("PRIVATE_", json.dumps(after))
        self.assertIn(temporary / "file.bin", visited)

    def test_native_temporary_errors_bounds_and_replaced_root_fail_closed(self):
        for failure in ("scandir", "lstat", "entry-lstat", "deadline", "count", "replaced", "path"):
            with self.subTest(failure=failure):
                _, case, temporary = self.native_model()
                original_lstat = Path.lstat
                visited = []
                target = temporary
                if failure == "count":
                    for name in ("one", "two"):
                        (temporary / name).mkdir()
                elif failure == "entry-lstat":
                    (temporary / "entry").mkdir()
                elif failure == "replaced":
                    temporary.rename(temporary.with_name("original-native-tmp"))
                    temporary.mkdir()
                elif failure == "path":
                    target = temporary / ".." / "native-tmp"

                def lstat(path):
                    visited.append(path)
                    if (failure == "lstat" and path == temporary or
                            failure == "entry-lstat" and path == temporary / "entry"):
                        raise PermissionError(13, "PRIVATE_ERROR_TEXT")
                    if failure == "path":
                        self.fail("Rejected lexical path must not be inspected, even in finally")
                    return original_lstat(path)

                with mock.patch.object(Path, "lstat", autospec=True, side_effect=lstat), \
                        mock.patch.object(C.os, "scandir", side_effect=PermissionError(13, "PRIVATE_ERROR_TEXT")
                                          if failure == "scandir" else C.os.scandir) as scan, \
                        mock.patch.object(C, "NATIVE_TEMP_ENTRIES", 1):
                    value = C.observe_native_temporary(target, case["nativeTemporaryIdentity"],
                                                       0 if failure == "deadline" else time.monotonic() + 5)
                self.assertFalse(value["complete"])
                self.assertIsNone(value["empty"])
                self.assertTrue(value["errors"])
                self.assertNotIn("PRIVATE_ERROR_TEXT", json.dumps(value))
                if failure in ("deadline", "replaced", "path", "lstat"):
                    scan.assert_not_called()
                if failure in ("deadline", "path"):
                    self.assertEqual(visited, [])
                if failure == "entry-lstat":
                    self.assertIsNone(value["entries"][0]["metadata"])
                    self.assertEqual(value["errors"][0]["step"], "entry-metadata")

    def test_native_temporary_initial_nonempty_or_unknown_root_blocks_leaf(self):
        for mode in ("nonempty", "deadline"):
            controller, case, temporary = self.native_model()
            controller.leaf = mock.Mock(side_effect=AssertionError("Rejected root cannot launch a leaf"))
            if mode == "nonempty":
                (temporary / "unexplained").mkdir()
            else:
                controller.deadline = controller.final_deadline = 0
            self.rejects(lambda: controller.native_controls(case))
            controller.leaf.assert_not_called()
            self.assertFalse(case["nativeStarted"])
            self.assertFalse(case["nativeAccepted"])
            self.assertTrue(case["retentionErrors"])
            value = C.read_json(controller.public / "admission/native-temporary-before.json")
            self.assertFalse(value["empty"])
            self.assertEqual(value["complete"], mode == "nonempty")

    def test_native_temporary_unsafe_ancestors_roots_and_children_are_never_followed(self):
        for location in ("ancestor", "root", "child"):
            for kind in ("symlink", "reparse-point"):
                with self.subTest(location=location, kind=kind):
                    _, case, temporary = self.native_model()
                    child = temporary / "entry"
                    child.mkdir()
                    unsafe = {"ancestor": temporary.parent, "root": temporary, "child": child}[location]
                    original_lstat, original_scan = Path.lstat, C.os.scandir
                    info = original_lstat(unsafe)
                    fields = {name: getattr(info, name, None) for name in ("st_dev", "st_ino", "st_birthtime_ns",
                        "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_file_attributes", "st_reparse_tag")}
                    fields.update(st_mode=C.stat.S_IFLNK | 0o700 if kind == "symlink" else C.stat.S_IFDIR | 0o700,
                                  st_file_attributes=0x400 if kind == "reparse-point" else None)
                    visited = []

                    def lstat(path):
                        visited.append(path)
                        return SimpleNamespace(**fields) if path == unsafe else original_lstat(path)

                    with mock.patch.object(Path, "lstat", autospec=True, side_effect=lstat), \
                            mock.patch.object(C.os, "scandir", side_effect=original_scan) as scan, \
                            mock.patch.object(Path, "readlink", side_effect=AssertionError("No link target observation")):
                        value = C.observe_native_temporary(temporary, case["nativeTemporaryIdentity"], time.monotonic() + 5)
                    if location == "child":
                        self.assertTrue(value["complete"])
                        self.assertFalse(value["empty"])
                        self.assertEqual(value["entries"][0]["metadata"]["kind"], kind)
                        scan.assert_called_once_with(temporary)
                    else:
                        self.assertFalse(value["complete"])
                        self.assertIsNone(value["empty"])
                        scan.assert_not_called()
                        self.assertNotIn(child, visited)
                        if location == "ancestor":
                            self.assertNotIn(temporary, visited)

    def native_admission(self, *, failed=False, residue=False, write_failed=False, inventory_failed=False, cleanup_failed=False):
        controller, case, temporary = self.native_model()
        original = RuntimeError("MODEL original native failure")
        native = case["state"] / "evidence/native-controls"
        (native / "test_model").mkdir(parents=True)
        C.new_json(native / "test_model/case.json", {"scope": "MODEL_ONLY_NOT_NATIVE"})
        source = (ROOT / "scripts/tests/run-audit-command-test.py").read_bytes()
        text = "Running current-host real executor fixtures: windows-x64; MODEL_ONLY\n\nRan " + str(
            C.expected_native_count(source)) + " tests in 0.1s\n\nOK\n"
        logs = case["public"] / "executor-native-controls"
        logs.mkdir()
        (logs / "product.stdout.log").write_bytes(b"")
        (logs / "product.stderr.log").write_text(text)

        def leaf(actual_case, purpose, arguments, **options):
            self.assertIs(actual_case, case)
            self.assertEqual((purpose, options), ("executor-native-controls", {"kind": "command", "timeout": 1800}))
            self.assertEqual(arguments, [sys.executable, "-B", "scripts/tests/run-audit-command-test.py",
                                        "--expected-host", "windows-x64", "--evidence-dir", str(native),
                                        "--fixture-parent", str(temporary)])
            self.assertTrue((controller.public / "admission/native-temporary-before.json").is_file())
            record = {"id": "d" * 32, "purpose": purpose, "arguments": arguments,
                      "status": 1 if failed else 0, "valid": not failed, "retained": True}
            case["leaves"].append(record)
            try:
                if failed:
                    raise original
            finally:
                # Models the leaf's stop boundary, not execution/retirement proof.
                if residue:
                    (temporary / "model-stop-residue").mkdir()

        original_json, original_inventory = C.new_json, C.inventory

        def write_json(path, value):
            if write_failed and path.name == "native-temporary-after.json":
                raise OSError("MODEL post retention failure")
            return original_json(path, value)

        def inventory(path, **options):
            if inventory_failed and path == native:
                raise OSError("MODEL fixture retention failure")
            return original_inventory(path, **options)

        controller.leaf = mock.Mock(side_effect=leaf)
        with mock.patch.object(C, "new_json", side_effect=write_json), \
                mock.patch.object(C, "inventory", side_effect=inventory), \
                mock.patch.object(C, "assess_native_cleanup", return_value=[{"scope": "MODEL_ONLY"}],
                    side_effect=C.audit.AuditError("MODEL unresolved cleanup") if cleanup_failed else None) as cleanup:
            error = None
            try:
                controller.native_controls(case)
            except Exception as caught:
                error = caught
        return controller, case, error, original, cleanup

    def test_native_caller_retains_before_and_after_original_leaf_failure(self):
        controller, case, error, original, cleanup = self.native_admission(failed=True, residue=True)
        self.assertIs(error, original)
        before = C.read_json(controller.public / "admission/native-temporary-before.json")
        after = C.read_json(controller.public / "admission/native-temporary-after.json")
        self.assertTrue(before["empty"])
        self.assertIsNone(before["leaf"])
        self.assertEqual(after["leaf"]["id"], "d" * 32)
        self.assertEqual(after["leaf"]["status"], 1)
        self.assertEqual(after["entries"][0]["name"], "model-stop-residue")
        self.assertFalse(case["nativeAccepted"])
        self.assertTrue((controller.public / "admission/native-controls/test_model/case.json").is_file())
        cleanup.assert_not_called()

    def test_native_diagnostic_failures_never_replace_original_or_allow_acceptance(self):
        for failed in (False, True):
            controller, case, error, original, cleanup = self.native_admission(
                failed=failed, write_failed=True, inventory_failed=True)
            if failed:
                self.assertIs(error, original)
            else:
                self.assertIsInstance(error, C.audit.AuditError)
            self.assertEqual(len(case["retentionErrors"]), 2)
            self.assertFalse(case["nativeAccepted"])
            self.assertTrue((controller.public / "admission/native-temporary-before.json").is_file())
            self.assertFalse((controller.public / "admission/native-temporary-after.json").exists())
            cleanup.assert_not_called()

    def test_native_four_predicates_and_cleanup_assessment_remain_required(self):
        text = "Running current-host real executor fixtures: windows-x64;\n\nRan 96 tests in 1.0s\n\nOK\n"
        empty = {"complete": True, "empty": True}
        self.assertTrue(all(C.native_predicates(text, 96, empty).values()))
        for name, actual, root in (("expected-test-count-and-OK", text.replace("96", "95"), empty),
                ("expected-test-count-and-OK", text.replace("OK", "FAILED"), empty),
                ("current-Windows-marker", text.replace("windows-x64", "linux-x64"), empty),
                ("no-skipped-marker", text + "skipped=1", empty),
                ("native-temporary-root-empty", text, {"complete": True, "empty": False}),
                ("native-temporary-root-empty", text, {"complete": False, "empty": None})):
            self.assertEqual([key for key, passed in C.native_predicates(actual, 96, root).items() if not passed], [name])
        for residue, cleanup_failed in ((False, False), (True, False), (False, True)):
            controller, case, error, _, cleanup = self.native_admission(residue=residue, cleanup_failed=cleanup_failed)
            self.assertEqual(case["nativeAccepted"], not residue and not cleanup_failed)
            if residue:
                self.assertIn("native-temporary-root-empty", str(error))
                cleanup.assert_not_called()
            else:
                cleanup.assert_called_once_with(case["state"] / "evidence/native-controls",
                                               (ROOT / "scripts/tests/run-audit-command-test.py").read_bytes())
                if not cleanup_failed:
                    self.assertIsNone(error)
                    self.assertTrue(all(C.read_json(controller.public / "admission/native-controls.json")["predicates"].values()))

    def test_native_temporary_public_schema_is_finite_and_pair_bound(self):
        controller, case, temporary = self.native_model()
        before = controller.native_temporary(case, "before")
        (temporary / "entry").mkdir()
        after = controller.native_temporary(case, "after")
        directory, identity = controller.public / "admission", controller.identity
        C.seal_public(directory, identity, "admission")
        C.verify_public(directory, identity, "admission")
        for mutate in (lambda v: v.update(raw="PRIVATE_CONTENT"),
                       lambda v: v["entries"][0].update(contents="PRIVATE_CONTENT"),
                       lambda v: v["rootBefore"].update(target="PRIVATE_TARGET"),
                       lambda v: v["expectedRootIdentity"].update(device=-1),
                       lambda v: v.update(source={**v["source"], "tree": "f" * 40}),
                       lambda v: v.update(complete=False),
                       lambda v: v.update(errors=[{"step": "entries", "entry": None, "exceptionType": "OSError",
                                                   "errno": 13, "winerror": None, "raw": "PRIVATE_ERROR"}])):
            value = copy.deepcopy(after)
            mutate(value)
            self.rejects(lambda: C.validate_native_temporary(value, identity, "after"))
        # Even a self-consistent forged manifest cannot admit a raw extra key.
        after["raw"] = "PRIVATE_CONTENT"
        (directory / "native-temporary-after.json").write_bytes(C.audit.json_bytes(after))
        rows = [row for row in C.inventory(directory) if row["path"] != "manifest.json"]
        (directory / "manifest.json").write_bytes(C.audit.json_bytes(C.public_manifest(identity, "admission", rows)))
        self.rejects(lambda: C.verify_public(directory, identity, "admission"))
        for name in ("native-temporary-before.json", "native-temporary-after.json"):
            self.assertTrue(C.public_path(name))
        for name in ("native-temporary-raw.json", "native-tmp/raw.bin", "arbitrary.json"):
            self.assertFalse(C.public_path(name))
        for bad in ("raw-key", "wrong-owner", "wrong-case"):
            stage = self.base / bad
            stage.mkdir()
            C.new_json(stage / "native-temporary-before.json", before)
            value = copy.deepcopy(after)
            value.pop("raw")
            if bad == "raw-key":
                value["raw"] = "PRIVATE_CONTENT"
            elif bad == "wrong-owner":
                value["jobId"] = "e" * 32
            C.new_json(stage / "native-temporary-after.json", value)
            self.rejects(lambda: C.seal_public(stage, identity, "current" if bad == "wrong-case" else "admission"))

    def test_native_count_and_failed_then_recovered_cleanup_history(self):
        recovery = "test_cleanup_failures_still_archive_authentic_receipts_and_preserve_unresolved_fixture"
        source = ("class PurePolicyTests:\n def test_pure(self): pass\n"
                  "class DarwinObservationTests:\n def test_observation(self): pass\n"
                  "class ExecutorFixtureTests:\n def test_regular(self): pass\n def " + recovery + "(self): pass\n"
                  "class WindowsNativeTests(ExecutorFixtureTests):\n def test_native(self): pass\n").encode()
        self.assertEqual(C.expected_native_count(source), 5)
        directory = self.base / "native-model"
        directory.mkdir()
        last = None
        for name in ("test_regular", recovery, "test_native"):
            case = directory / name
            case.mkdir()
            binding = {"source": "C:\\" + name + "\\source", "state": "C:\\" + name + "\\state"}
            C.new_json(case / "case.json", binding)
            C.new_json(case / "init.json", dict(binding, exitCode=0))
            for index in range(2 if name == recovery else 1):
                identifier = str(index + 1) * 32
                attempt = case / ("teardown-" + identifier)
                attempt.mkdir()
                final = name != recovery or index == 1
                C.new_json(attempt / "cleanup.json", {"schema": 1, "kind": "executor-fixture-cleanup", "id": identifier,
                    "state": binding["state"], "fixtureBase": "C:\\" + name,
                    "startedUtc": "MODEL_ORDER_" + str(index), "endedUtc": "MODEL_END",
                    "cleanupComplete": final, "fixtureDataRemoved": final, "errors": [] if final else ["MODEL injected"],
                    "guardSurvivors": [], "sentinels": []})
                C.new_json(attempt / "guard.json", {"backend": "windows-job-list-suspended", "discoveryErrors": []})
                last = attempt / "cleanup.json"
        rows = C.assess_native_cleanup(directory, source)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(next(row for row in rows if row["test"] == recovery)["attemptIds"]), 2)
        value = C.read_json(last)
        value["cleanupComplete"] = False
        last.write_bytes(C.audit.json_bytes(value))
        self.rejects(lambda: C.assess_native_cleanup(directory, source))

    def test_readonly_diagnostic_failures_keep_original_exception_authoritative(self):
        original = PermissionError("MODEL original unlink failure")
        exception = (PermissionError, original, None)
        for stage in ("detail", "retry", "journal"):
            directory = self.base / stage
            record = {}
            handler = C.readonly_handler(self.base, {"device": 1, "inode": 1}, directory, record)
            with mock.patch.object(C.audit, "removal_failure_detail", side_effect=RuntimeError("MODEL diagnostic") if stage == "detail" else None,
                                   return_value={"model": True}), \
                    mock.patch.object(C.audit, "retry_windows_readonly_unlink", side_effect=RuntimeError("MODEL retry") if stage == "retry" else None,
                                      return_value=False), \
                    mock.patch.object(C, "new_json", side_effect=OSError("MODEL journal") if stage == "journal" else C.new_json):
                with self.assertRaises(PermissionError) as caught:
                    handler(os.unlink, str(self.base / "leaf"), exception)
                self.assertIs(caught.exception, original)

    def controller(self):
        controller = C.Controller.__new__(C.Controller)
        controller.root, controller.public = self.base / "source", self.base / "public"
        controller.public.mkdir()
        for name in ("admission", "current", "preimage"):
            (controller.public / name).mkdir()
        controller.raw = self.base / "raw"
        controller.raw.mkdir()
        controller.active_public = controller.public / "admission"
        controller.scope = mock.Mock()
        controller.scope.discover.return_value = controller.scope.drain.return_value = []
        controller.scope.description.return_value = {"discoveryErrors": []}
        controller.counter, controller.safe = 0, False
        controller.cancelled, controller.cases, controller.handlers = [], [], {}
        controller.identity = {"sourceSha": "a" * 40, "scope": "MODEL_ONLY_NOT_HOSTED"}
        controller.deadline = controller.final_deadline = time.monotonic() + 10
        controller.resources = mock.Mock(return_value={})
        return controller

    def test_partial_tee_and_ownership_failure_still_retain_command_record(self):
        controller = self.controller()
        child = mock.Mock(stdout=io.BytesIO(b"model stdout"), stderr=io.BytesIO(b"model stderr"))
        child.poll.return_value = child.wait.return_value = 0
        controller.scope.spawn.return_value = child
        first = mock.Mock(source=child.stdout)
        controller.scope.description.side_effect = RuntimeError("MODEL missing ownership")
        with mock.patch.object(C.audit, "Tee", side_effect=[first, OSError("MODEL second Tee failed")]):
            with self.assertRaises(C.CommandFailure) as caught:
                controller.command(["NOT_EXECUTED"], self.base, {}, "git")
        first.finish.assert_called_once()
        self.assertTrue(child.stderr.closed)
        record = C.read_json(caught.exception.capture / "command.json")
        self.assertEqual(record["exitCode"], 0)
        self.assertTrue(any("second Tee failed" in error for error in record["errors"]))
        self.assertTrue(any("missing ownership" in error for error in record["errors"]))

    def test_signals_restore_even_when_finalization_or_sealing_fails(self):
        base = self.base
        for stage in ("finalization", "sealing"):
            self.base = base / stage
            self.base.mkdir()
            controller = self.controller()
            controller.admit_tools = mock.Mock(side_effect=C.audit.AuditError("MODEL admission refused"))
            controller.finalize_resources = mock.Mock(side_effect=OSError("MODEL finalization failed") if stage == "finalization" else None)
            controller.seal_results = mock.Mock(side_effect=OSError("MODEL sealing failed"))
            with mock.patch.object(C.signal, "getsignal", return_value="ORIGINAL_HANDLER"), \
                    mock.patch.object(C.signal, "signal") as setter:
                with self.assertRaisesRegex(OSError, "MODEL " + stage + " failed"):
                    controller.run()
            for number in controller.handlers:
                self.assertIn(mock.call(number, "ORIGINAL_HANDLER"), setter.call_args_list)
            controller.scope.spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
