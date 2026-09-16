#!/usr/bin/env python3
"""Pure policy/file/mock controls, NOT native Windows or Gradle execution.

Only three bounded read-only Git queries obtain the immutable reviewed preimages.
All controller process, tool and native operations below are fake; no wrapper,
native fixture suite, SDK installer, host impersonation or network is executed.
"""
from __future__ import annotations

import ast
import copy
from contextlib import contextmanager
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
NATIVE_SPEC = importlib.util.spec_from_file_location("native_controller_directory_definitions",
                                                  ROOT / "scripts/tests/windows-helper-native-test.py")
N = importlib.util.module_from_spec(NATIVE_SPEC)
NATIVE_SPEC.loader.exec_module(N)  # Definitions only; calls below replace every native/process boundary.


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
        "temporaryOwnerSha256": "e" * 64,
        "testTemporary": r"C:\control\state\fixtures\jvm-tmp", "java17": r"C:\jdk17", "java21": r"C:\jdk21"}


def arguments(req):
    return ["-Dp2pkit.windowsDirectoryNonce=" + req["nonce"], "-XX:ActiveProcessorCount=2", "-XX:-UsePerfData",
            "-Xms128m", "-Xmx512m", "-Dfile.encoding=UTF-8", "-Djava.io.tmpdir=" + req["testTemporary"],
            "-Duser.country=US", "-Duser.language=en", "-Duser.variant", "-ea"]


# Independent literal expected bytes. No production renderer creates this fixture.
WORKER_LITERAL = (b'-cp\r\nC:\\\\control\\\\state\\\\gradle-home\\\\caches\\\\9.7.0\\\\workerMain\\\\gradle-worker.jar;'
    b'C:\\\\control\\\\source\\\\library\\\\p2p-core\\\\build\\\\classes\\\\kotlin\\\\jvm\\\\test;'
    b'C:\\\\control\\\\state\\\\gradle-home\\\\caches\\\\modules-2\\\\files-2.1\\\\g\\\\a\\\\1\\\\hash\\\\a.jar\r\n')
WORKER_BOOTSTRAP = b'MODEL_BOOTSTRAP_NOT_AN_EXECUTABLE\n'
COMPILER_FILE = "gradle-worker-classpath7019133862698902102txt"
SELECTED_FILE = "gradle-worker-classpath7481741643250717400txt"


def worker_authority():
    return {"gradleVersion": "9.7.0", "gradleHome": r"C:\control\state\gradle-home", "testIsModule": False,
        "modulePath": [], "nativeCharset": "UTF-8", "nativeEncodedSha256": C.digest(WORKER_LITERAL),
        "bootstrap": {"path": r"C:\control\state\gradle-home\caches\9.7.0\workerMain\gradle-worker.jar",
                      "bytes": len(WORKER_BOOTSTRAP), "sha256": C.digest(WORKER_BOOTSTRAP)},
        "applicationClasspath": [
            {"path": r"C:\control\source\library\p2p-core\build\classes\kotlin\jvm\test", "kind": "directory"},
            {"path": r"C:\control\state\gradle-home\caches\modules-2\files-2.1\g\a\1\hash\a.jar", "kind": "file"},
            {"path": r"C:\control\source\library\p2p-core\build\resources\jvm\test", "kind": "missing"}],
        "beforeFiles": {"exists": True, "names": [COMPILER_FILE]}}


def worker_log(req):
    # Actual pinned representation, including the DISTINCT compiler decoy. This
    # is a synthetic model, not R10's absent original argument-file contents.
    argfile = req["state"] + "\\gradle-home\\.tmp\\" + SELECTED_FILE
    command = (req["java17"] + r"\bin\java.exe -Dorg.gradle.internal.worker.tmpdir=" + req["root"] +
        r"\library\p2p-core\build\tmp\jvmTest\work -Dp2pkit.windowsDirectoryNonce=" + req["nonce"] +
        " -XX:ActiveProcessorCount=2 -XX:-UsePerfData @" + argfile +
        " -Xms128m -Xmx512m -Dfile.encoding=UTF-8 -Djava.io.tmpdir=" + req["testTemporary"] +
        " -Duser.country=US -Duser.language=en -Duser.variant -ea " +
        "worker.org.gradle.process.internal.worker.GradleWorkerMain 'Gradle Test Executor 2'")
    return ("Starting process 'Gradle Worker Daemon 1'. Working directory: " + req["state"] +
        "\\gradle-home\\workers Command: " + req["java17"] + "\\bin\\java.exe @" + req["state"] +
        "\\gradle-home\\.tmp\\" + COMPILER_FILE +
        " worker.org.gradle.process.internal.worker.GradleWorkerMain 'Gradle Worker Daemon 1'\r\n" +
        "Successfully started process 'Gradle Worker Daemon 1'\r\n" +
        "Starting process 'Gradle Test Executor 2'. Working directory: " + req["root"] +
        "\\library\\p2p-core Command: " + command + "\r\nSuccessfully started process 'Gradle Test Executor 2'\r\n").encode()


def worker_capture(req, admission_hash, request_hash="d" * 64):
    return {"schema": 1, "requestSha256": request_hash, "admissionSha256": admission_hash,
        "phase": "selected-afterTask", "observedMillis": 25, "status": "CAPTURED", "reason": None,
        "afterFiles": {"exists": True, "names": [COMPILER_FILE, SELECTED_FILE]},
        "original": {"path": req["state"] + "\\gradle-home\\.tmp\\" + SELECTED_FILE,
                     "bytes": len(WORKER_LITERAL), "sha256": C.digest(WORKER_LITERAL)}}


def execution(req, scope="root"):
    negative = req["caseName"] == "preimage" and scope == "root"
    paths = sorted(C.REQUIRED_TASKS) if scope == "root" else [":compileJava", ":jar"]
    admission = {"task": C.TASK, "commandFilters": [C.SELECTOR], "includePatterns": [], "excludePatterns": [],
        "enabled": True, "ignoreFailures": False, "failOnNoMatchingTests": True, "maxParallelForks": 1, "forkEvery": 0,
        "temporaryEmpty": True, "temporaryFileKey": None, "temporaryOwnerSha256": req["temporaryOwnerSha256"], "observedMillis": 10,
        "temporary": req["testTemporary"], "jvmArgs": arguments(req), "workerExpansion": worker_authority(),
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
        "requestedTasks": [C.TASK, "--tests", C.SELECTOR] if scope == "root" else [],
        "admission": admission, "finishedMillis": 30,
        "events": [] if scope == "buildSrc" else [{"className": C.CLASS, "name": C.METHOD,
            "result": "FAILURE" if negative else "SUCCESS", "testCount": 1, "passed": int(not negative),
            "failed": int(negative), "skipped": 0, "startMillis": 11, "endMillis": 20}]}


def xml(req):
    negative = req["caseName"] == "preimage"
    # Pinned KotlinJvmTest report labels, not canonical selector/listener names.
    # Keep these literals independent of the assessor's expected-label constants.
    suite = ET.Element("testsuite", name="FileTransferJvmTest[jvm]", tests="1",
                       failures=str(int(negative)), errors="0", skipped="0")
    case = ET.SubElement(suite, "testcase", classname=C.CLASS,
                        name="durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent[jvm]")
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
        # Execute the nine actual allocation expressions, not any native test body.
        # The CLI's suite loader/runner and custody policy are modeled; only local
        # directories are real, including when this pure model runs on Windows.
        tree = ast.parse((ROOT / "scripts/tests/run-audit-command-test.py").read_bytes())
        allocations = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and
                       node.func.value.id == "tempfile" and node.func.attr == "TemporaryDirectory"]
        self.assertEqual(len(allocations), 9)
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
                        mock.patch.object(F, "WINDOWS_RETAINED_STORAGE", False), \
                        mock.patch.object(F.windows_files, "_WinApi",
                                          side_effect=AssertionError("PURE routing model cannot enter native custody")), \
                        mock.patch.object(F.windows_files, "create_private_directory",
                                          side_effect=AssertionError("PURE routing model cannot create native custody")), \
                        mock.patch.object(F.windows_files, "open_private_directory",
                                          side_effect=AssertionError("PURE routing model cannot open native custody")), \
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

    def test_shared_writer_inputs_are_only_empty_defaults_for_windows_witness(self):
        names = ("reviewed_base", "evidence_public_key", "evidence_fingerprint")
        env, original, source = dispatch()
        expected = C.dispatch_identity(env, original, source)
        for bits in range(1 << len(names)):
            event = copy.deepcopy(original)
            event["inputs"].update({name: "" for index, name in enumerate(names) if bits & (1 << index)})
            with self.subTest(empty_defaults=bits):
                self.assertEqual(C.dispatch_identity(env, event, source), expected)
        for name in names:
            for value in ("a" * 40, " ", "\n", None, False, 0, [], {}):
                event = copy.deepcopy(original)
                event["inputs"][name] = value
                with self.subTest(name=name, value=value):
                    self.rejects(lambda: C.dispatch_identity(env, event, source))
        for name in original["inputs"]:
            event = copy.deepcopy(original)
            event["inputs"].update(dict.fromkeys(names, ""))
            del event["inputs"][name]
            with self.subTest(missing=name):
                self.rejects(lambda: C.dispatch_identity(env, event, source))
        self.assertEqual(original, dispatch()[1])

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
            "productPrepared": True, "productRetained": True, "testTemporaryRetired": True,
            "nativeStarted": True, "nativeAccepted": True}
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
                ("productRetained", False), ("testTemporaryRetired", False), ("testTemporaryRetired", None), ("nativeAccepted", False)):
            self.rejects(lambda: C.require_disposal_evidence(dict(case, **{key: value})))

    def test_junit_accepts_pinned_kotlin_jvm_display_labels(self):
        # Public literal counterpart of R10's actual report dialect, not a new
        # native result or a fixture derived from implementation constants.
        raw = b'''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="FileTransferJvmTest[jvm]" tests="1" skipped="0" failures="0" errors="0" time="0.144">
  <properties/>
  <testcase name="durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent[jvm]"
            classname="dev.p2pkit.core.transfer.FileTransferJvmTest" time="0.144"/>
  <system-out><![CDATA[]]></system-out>
  <system-err><![CDATA[]]></system-err>
</testsuite>
'''
        self.assertIsNone(C.assess_xml(raw, request()))
        self.assertIsNone(C.assess_xml(raw.replace(b"\n", b"\r\n"), request()))

    def test_junit_rejects_wrong_display_labels_and_canonical_class(self):
        invalid = [
            (".", "name", "FileTransferJvmTest"),
            (".", "name", C.CLASS),
            (".", "name", C.CLASS + "[jvm]"),
            (".", "name", "OtherTest[jvm]"),
            (".", "name", "FileTransferJvmTest[android]"),
            (".", "name", "FileTransferJvmTest[jvm][jvm]"),
            (".", "name", "FileTransferJvmTest[jvm]extra"),
            ("testcase", "name", C.METHOD),
            ("testcase", "name", C.METHOD + "[android]"),
            ("testcase", "name", C.METHOD + "[jvm][jvm]"),
            ("testcase", "name", C.METHOD + "[jvm]extra"),
            ("testcase", "name", "other[jvm]"),
            ("testcase", "classname", "FileTransferJvmTest"),
            ("testcase", "classname", "other.package.FileTransferJvmTest"),
            ("testcase", "classname", C.CLASS + "[jvm]"),
        ]
        for negative in (False, True):
            req = request(negative)
            for path, attribute, value in invalid:
                with self.subTest(negative=negative, path=path, attribute=attribute, value=value):
                    suite = xml(req)
                    suite.find(path).set(attribute, value)
                    self.rejects(lambda: C.assess_xml(raw_xml(suite), req))

    def test_listener_identity_remains_canonical_not_junit_display_labels(self):
        for negative in (False, True):
            req = request(negative)
            C.assess_execution(execution(req), req, "d" * 64)
            for field, value in (("className", "FileTransferJvmTest[jvm]"),
                                 ("className", C.CLASS + "[jvm]"),
                                 ("className", "other.package.FileTransferJvmTest"),
                                 ("name", C.METHOD + "[jvm]"), ("name", "other")):
                with self.subTest(negative=negative, field=field, value=value):
                    report = execution(req)
                    report["events"][0][field] = value
                    self.rejects(lambda: C.assess_execution(report, req, "d" * 64))

    def test_exact_selected_junit_and_native_failure_path(self):
        for negative in (False, True):
            req = request(negative)
            original = xml(req)
            self.assertEqual(C.assess_xml(raw_xml(original), req),
                             req["testTemporary"] + r"\p2pkit-durable-destination-1234" if negative else None)
            mutations = [lambda s: s.set("tests", "0"), lambda s: s.set("tests", "2"),
                lambda s: s.set("skipped", "1"), lambda s: s.set("errors", "1"),
                lambda s: s.set("failures", str(int(not negative))),
                lambda s: s.append(copy.deepcopy(s.find("testcase"))), lambda s: s.find("testcase").set("name", "other"),
                lambda s: s.remove(s.find("testcase")), lambda s: ET.SubElement(s.find("testcase"), "error"),
                lambda s: ET.SubElement(s.find("testcase"), "skipped")]
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
        self.assertEqual(len(C.TASK_POLICY_INPUTS), 21)
        self.assertEqual(len(C.TEMPORARY_POLICY_INPUTS), 8)
        policy_rows = []
        for name, inputs in C.TASK_POLICY_INPUTS.items():
            fields = {"buildSrc": False, "dryRun": False, "excludedTasks": [], "accepted": False, **copy.deepcopy(inputs)}
            policy_rows.append({"id": name, "passed": True, **fields,
                "exceptionType": None if fields["accepted"] else "org.gradle.api.GradleException",
                "message": None if fields["accepted"] else C.TASK_POLICY_MESSAGE})
        temporary_rows = []
        for name, inputs in C.TEMPORARY_POLICY_INPUTS.items():
            fields = {"directory": True, "other": False, "symbolicLink": False, "hasEntries": False,
                      "fileKey": None, "accepted": False, **copy.deepcopy(inputs)}
            message = fields.pop("message", C.TEMPORARY_POLICY_MESSAGE)
            temporary_rows.append({"id": name, "passed": True, **fields,
                "observedFileKey": fields["fileKey"] if fields["accepted"] else None,
                "exceptionType": None if fields["accepted"] else "org.gradle.api.GradleException",
                "message": None if fields["accepted"] else message})
        self.assertEqual(len(C.WORKER_POLICY_CASES), 25)
        return {"schema": 5, "scope": "MODELED_POLICIES_AND_LIVE_GRADLE_SERVICE_LOOKUPS_NOT_NATIVE_PRODUCT",
            "gradleVersion": "9.7.0", "taskPolicyCases": policy_rows, "temporaryPolicyCases": temporary_rows,
            "workerPolicyCases": [{"id": name, "passed": True, "value": value, "message": message,
                "exceptionType": "org.gradle.api.GradleException" if message else None}
                for name, (value, message) in C.WORKER_POLICY_CASES.items()],
            # Report models only; no live Gradle service is called by Python.
            "workerServiceCases": [
                {"id": "generic_registry_unknown", "passed": True, "bootstrap": None,
                 "exceptionType": "java.lang.IllegalArgumentException", "message": "unknown classpath 'WORKER_MAIN' requested."},
                {"id": "concrete_provider_bootstrap", "passed": True,
                 "bootstrap": {"relativePath": "caches/9.7.0/workerMain/gradle-worker.jar", "bytes": 123, "sha256": "f" * 64},
                 "exceptionType": None, "message": None}],
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

    def test_task_policy_report_requires_actual_inputs_precise_outcomes_and_complete_rows(self):
        # Tampered-report models only, not execution of the Groovy predicate.
        hashes = {name: "e" * 64 for name in ("observer", "settings.gradle", "build.gradle", "gradle/gradle-daemon-jvm.properties")}
        original = self.binding_report(hashes)
        C.assess_binding_controls(original, hashes, require_pass=True)
        mutations = [lambda v: v.pop("taskPolicyCases"), lambda v: v.update(taskPolicyCases=None),
            lambda v: v["taskPolicyCases"].pop(), lambda v: v["taskPolicyCases"].reverse(),
            lambda v: v["taskPolicyCases"].__setitem__(1, v["taskPolicyCases"][0]),
            lambda v: v["taskPolicyCases"][0].update(requestedTasks=[C.TASK]),
            lambda v: v["taskPolicyCases"][0].update(excludedTasks=[":compileJava"]),
            lambda v: v["taskPolicyCases"][0].update(dryRun=0),
            lambda v: v["taskPolicyCases"][0].update(buildSrc=True),
            lambda v: v["taskPolicyCases"][0].update(accepted=1),
            lambda v: v["taskPolicyCases"][0].update(exceptionType="org.gradle.api.GradleException"),
            lambda v: v["taskPolicyCases"][3].update(exceptionType="java.lang.NullPointerException"),
            lambda v: v["taskPolicyCases"][3].update(message="a different failure"),
            lambda v: v["taskPolicyCases"][3].update(accepted=True, exceptionType=None, message=None),
            lambda v: v["taskPolicyCases"][3].update(passed=1),
            lambda v: v["taskPolicyCases"][3].update(unknown="unbounded data")]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(original)
                mutate(changed)
                self.rejects(lambda: C.assess_binding_controls(changed, hashes, require_pass=True))
        for index, outcome in ((0, {"accepted": False, "exceptionType": "java.lang.IllegalStateException", "message": "wrong failure"}),
                               (3, {"accepted": True, "exceptionType": None, "message": None})):
            changed = copy.deepcopy(original)
            changed["taskPolicyCases"][index].update(passed=False, **outcome)
            C.assess_binding_controls(changed, hashes, require_pass=False)
            self.rejects(lambda: C.assess_binding_controls(changed, hashes, require_pass=True))

    def test_temporary_policy_report_requires_actual_inputs_complete_rows_and_precise_outcomes(self):
        # This assesses modeled reports; the hosted Groovy fixture runs the shared predicate.
        hashes = {"scope": "MODEL_ONLY"}
        original = self.binding_report(hashes)
        C.assess_binding_controls(original, hashes, require_pass=True)
        mutations = [lambda v: v.update(schema=2), lambda v: v.pop("temporaryPolicyCases"),
            lambda v: v["temporaryPolicyCases"].pop(), lambda v: v["temporaryPolicyCases"].reverse(),
            lambda v: v["temporaryPolicyCases"].__setitem__(1, v["temporaryPolicyCases"][0]),
            lambda v: v["temporaryPolicyCases"][0].update(directory=False),
            lambda v: v["temporaryPolicyCases"][0].update(hasEntries=0),
            lambda v: v["temporaryPolicyCases"][0].update(observedFileKey="null"),
            lambda v: v["temporaryPolicyCases"][1].update(observedFileKey=None),
            lambda v: v["temporaryPolicyCases"][2].update(message="different error"),
            lambda v: v["temporaryPolicyCases"][2].update(exceptionType="java.lang.NullPointerException"),
            lambda v: v["temporaryPolicyCases"][2].update(passed=1),
            lambda v: v["temporaryPolicyCases"][2].update(raw="not allowed")]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(original)
                mutate(changed)
                self.rejects(lambda: C.assess_binding_controls(changed, hashes, require_pass=True))
        failed = copy.deepcopy(original)
        failed["temporaryPolicyCases"][0].update(passed=False, accepted=False,
            exceptionType="org.gradle.api.GradleException", message=C.TEMPORARY_POLICY_MESSAGE)
        C.assess_binding_controls(failed, hashes, require_pass=False)
        self.rejects(lambda: C.assess_binding_controls(failed, hashes, require_pass=True))

    def test_java_key_is_a_present_nullable_diagnostic_bound_to_exact_owner(self):
        for negative in (False, True):
            req = request(negative)
            for key in (None, "MODEL_FILE_KEY", "k" * 1024):
                value = execution(req)
                value["admission"]["temporaryFileKey"] = key
                C.assess_execution(value, req, "d" * 64)
            mutations = [lambda v: v["admission"].pop("temporaryFileKey"),
                lambda v: v["admission"].pop("temporaryOwnerSha256"),
                lambda v: v["admission"].update(temporaryOwnerSha256="f" * 64),
                lambda v: v["admission"].update(temporaryEmpty=False)]
            mutations += [lambda v, key=key: v["admission"].update(temporaryFileKey=key)
                          for key in ("", "k" * 1025, 1, True, [], {})]
            for index, mutate in enumerate(mutations):
                with self.subTest(negative=negative, mutation=index):
                    value = execution(req)
                    mutate(value)
                    self.rejects(lambda: C.assess_execution(value, req, "d" * 64))

    def jvm_temporary_model(self):
        # Real tiny local directories/metadata, but explicitly fake context/leaf.
        base = Path(tempfile.mkdtemp(prefix="test-temporary-", dir=self.base)).resolve()
        state, root, public = base / "state", base / "source", base / "public"
        for path in (state / "fixtures", state / "evidence", root, public):
            path.mkdir(parents=True)
        controller = C.Controller.__new__(C.Controller)
        controller.identity = C.dispatch_identity(*dispatch())  # Pure model, not os.environ.
        controller.deadline = controller.final_deadline = time.monotonic() + 30
        case = {"name": "current", "state": state, "root": root, "public": public, "leaves": [],
            "context": {"id": "b" * 32, "source": dispatch()[2]}, "env": {"JAVA_HOME": "MODEL_JDK17", "P2PKIT_AUDIT_JDK21": "MODEL_JDK21"},
            "initialized": True, "retentionErrors": [], "productPrepared": False, "productRetained": False,
            "nativeStarted": False, "nativeAccepted": False}
        C.create_test_temporary(case, controller.identity)
        return controller, case, state / "fixtures/jvm-tmp"

    def test_temporary_creation_uses_positive_full_lstat_and_rejects_links_reparse_and_bad_ids(self):
        _, case, temporary = self.jvm_temporary_model()
        expected = C.identified_test_temporary(temporary)
        self.assertEqual(expected, case["testTemporaryOwner"]["nativeIdentity"])
        for key in ("device", "inode"):
            for invalid in (None, 0, -1, True, "1", 1.0, 2 ** 128):
                with self.subTest(key=key, value=invalid), mock.patch.object(C, "native_temporary_identity",
                        return_value={**expected, key: invalid}):
                    self.rejects(lambda: C.identified_test_temporary(temporary))
        original_lstat = Path.lstat
        for unsafe in ("file", "link", "ancestor-link", "reparse"):
            with self.subTest(unsafe=unsafe):
                candidate = self.base / unsafe
                if unsafe == "file":
                    candidate.write_bytes(b"OWNED_TEST_DATA")
                elif unsafe in ("link", "ancestor-link"):
                    candidate.symlink_to(temporary if unsafe == "link" else temporary.parent, target_is_directory=True)
                    if unsafe == "ancestor-link":
                        candidate = candidate / "jvm-tmp"
                else:
                    candidate = temporary
                seen = []
                def lstat(path):
                    seen.append(path)
                    info = original_lstat(path)
                    if unsafe == "reparse" and path == temporary.parent:
                        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                    return info
                with mock.patch.object(Path, "lstat", autospec=True, side_effect=lstat):
                    self.rejects(lambda: C.identified_test_temporary(candidate))
                if unsafe in ("ancestor-link", "reparse"):
                    self.assertNotIn(candidate, seen)  # Reject parent before traversing it.
        with self.assertRaises(FileExistsError):
            C.create_test_temporary(case, {})

    def test_temporary_snapshots_bind_creation_before_after_owner_and_public_schema(self):
        controller, case, _ = self.jvm_temporary_model()
        owner, owner_hash = case["testTemporaryOwner"], case["testTemporaryOwnerSha256"]
        for phase in ("before", "after"):
            value = controller.test_temporary(case, phase)
            self.assertTrue(C.test_temporary_ok(value))
            self.assertEqual(value["expectedRootIdentity"], owner["nativeIdentity"])
            self.assertEqual(value["temporaryOwnerSha256"], C.digest((case["public"] / "temporary-owner.json").read_bytes()))
            mutations = [lambda v: v.update(source={**v["source"], "commit": "f" * 40}),
                lambda v: v.update(identity={"scope": "DIFFERENT_MODEL"}), lambda v: v.update(caseName="preimage"),
                lambda v: v.update(nonce="f" * 32), lambda v: v.update(jobId="f" * 32),
                lambda v: v.update(directory=v["directory"] + "-different"),
                lambda v: v.update(temporaryOwnerSha256="f" * 64),
                lambda v: v.update(observedOwnerSha256=None), lambda v: v.update(ownerUnchanged=1),
                lambda v: v["expectedRootIdentity"].update(inode=0),
                lambda v: v["rootBefore"].update(inode=v["rootBefore"]["inode"] + 1),
                lambda v: v.update(unknown="PRIVATE_DATA"), lambda v: v.pop("ownerError")]
            for index, mutate in enumerate(mutations):
                with self.subTest(phase=phase, mutation=index):
                    changed = copy.deepcopy(value)
                    mutate(changed)
                    self.rejects(lambda: C.validate_test_temporary(changed, owner, owner_hash, phase))
        C.validate_public_test_temporary(case["public"], controller.identity, "current", C.inventory(case["public"]))
        self.rejects(lambda: C.validate_public_test_temporary(case["public"], controller.identity, "admission", C.inventory(case["public"])))
        (case["public"] / "temporary-owner.json").unlink()
        self.rejects(lambda: C.validate_public_test_temporary(case["public"], controller.identity, "current", C.inventory(case["public"])))

    def test_product_failure_preserves_primary_and_post_stop_metadata_before_blocking_disposal(self):
        for failure in ("none", "owner", "owner-missing", "replaced", "residue", "metadata", "retention"):
            with self.subTest(failure=failure):
                controller, case, temporary = self.jvm_temporary_model()
                primary = C.audit.AuditError("MODEL original product/stop failure")
                original_lstat, original_write = Path.lstat, C.new_json
                stopped = False
                def leaf(observed, purpose, arguments, **options):
                    nonlocal stopped
                    self.assertIs(observed, case)
                    self.assertEqual(purpose, "product")
                    self.assertEqual(options, {"expected": 0, "timeout": 1500})
                    self.assertTrue(C.test_temporary_ok(C.read_json(case["public"] / "temporary-before.json")))
                    case["leaves"].append({"id": "a" * 32, "purpose": purpose, "status": 1, "valid": True, "retained": True})
                    if failure == "owner":
                        (temporary.parent / "jvm-tmp-owner.json").write_bytes(b"CHANGED_MODEL_OWNER")
                    elif failure == "owner-missing":
                        (temporary.parent / "jvm-tmp-owner.json").unlink()
                    elif failure == "replaced":
                        temporary.rename(temporary.with_name("displaced-owned-test"))
                        temporary.mkdir()
                    elif failure == "residue":
                        (temporary / "private-test.bin").write_bytes(b"PRIVATE_TEST_PAYLOAD")
                    stopped = True  # Only a modeled leaf completion, not a real wrapper stop.
                    raise primary
                def lstat(path):
                    if stopped and failure == "metadata" and path == temporary:
                        raise OSError(5, "MODEL metadata failure")
                    return original_lstat(path)
                def write(path, value):
                    if failure == "retention" and path.name == "temporary-after.json":
                        raise OSError("MODEL evidence write failure")
                    return original_write(path, value)
                controller.leaf = mock.Mock(side_effect=leaf)
                with mock.patch.object(Path, "lstat", autospec=True, side_effect=lstat), \
                        mock.patch.object(C, "new_json", side_effect=write):
                    with self.assertRaises(C.audit.AuditError) as caught:
                        controller.product(case)
                self.assertIs(caught.exception, primary)
                controller.leaf.assert_called_once()
                self.assertEqual(case["testTemporaryRetired"], failure == "none")
                self.assertEqual(case["productRetained"], failure == "none")
                after_path = case["public"] / "temporary-after.json"
                self.assertEqual(after_path.exists(), failure != "retention")
                if failure != "retention":
                    after = C.read_json(after_path)
                    self.assertEqual(C.test_temporary_ok(after), failure == "none")
                    self.assertEqual(after["leaf"]["status"], 1)
                    self.assertNotIn("PRIVATE_TEST_PAYLOAD", json.dumps(after))
                    if failure in ("replaced", "metadata"):
                        self.assertFalse(after["complete"])
                    if failure in ("owner", "owner-missing"):
                        self.assertFalse(after["ownerUnchanged"])
                if failure == "none":
                    C.require_disposal_evidence(case)  # Policy only; no controller deletion runs.
                else:
                    self.rejects(lambda: C.require_disposal_evidence(case))

    def test_changed_creation_owner_before_product_never_launches_and_still_retains_after(self):
        controller, case, temporary = self.jvm_temporary_model()
        (temporary.parent / "jvm-tmp-owner.json").write_bytes(b"CHANGED_MODEL_OWNER")
        controller.leaf = mock.Mock(side_effect=AssertionError("Must not launch"))
        self.rejects(lambda: controller.product(case))
        controller.leaf.assert_not_called()
        for phase in ("before", "after"):
            value = C.read_json(case["public"] / ("temporary-" + phase + ".json"))
            self.assertFalse(value["ownerUnchanged"])
            self.assertIsNone(value["leaf"])
        self.rejects(lambda: C.require_disposal_evidence(case))

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

    def test_root_requested_tasks_preserve_exact_tests_argument_triple(self):
        # Report/assessor models only. Real Gradle parsing and the shared
        # observer still require the genuine current/preimage Windows witness.
        for negative in (False, True):
            with self.subTest(negative=negative):
                req = request(negative)
                report = execution(req)
                self.assertEqual(report["requestedTasks"], [C.TASK, "--tests", C.SELECTOR])
                C.assess_execution(report, req, "d" * 64)
                self.assertEqual(report["requestedTasks"], [C.TASK, "--tests", C.SELECTOR])

    def test_root_requested_tasks_reject_incomplete_or_broadened_command(self):
        exact = [C.TASK, "--tests", C.SELECTOR]
        invalid = [[], [C.TASK], [C.TASK, C.SELECTOR], [C.TASK, "--tests"],
            [C.TASK, "--tests", "other.Test.method"], [C.TASK, "--tests", C.CLASS + ".*"],
            [C.TASK, "--tests", "*"], [C.TASK, "--tests=" + C.SELECTOR],
            [C.TASK, "--tests", "--tests", C.SELECTOR], exact + ["--tests", C.SELECTOR],
            [":p2p-core:jT", "--tests", C.SELECTOR], exact + [":p2p-core:jvmJar"],
            exact + ["--fail-fast"], ["--tests", C.SELECTOR, C.TASK], None, " ".join(exact)]
        for negative in (False, True):
            req = request(negative)
            for index, task_arguments in enumerate(invalid):
                with self.subTest(negative=negative, mutation=index):
                    changed = execution(req)
                    changed["requestedTasks"] = task_arguments
                    self.rejects(lambda: C.assess_execution(changed, req, "d" * 64))
        # buildSrc is governed by its own graph, not the root command tokens.
        req = request()
        child = execution(req, "buildSrc")
        C.assess_execution(child, req, "d" * 64, "buildSrc")
        for scope in ("root", "buildSrc"):
            for key, value in (("dryRun", True), ("excludedTasks", [":compileJava"])):
                changed = execution(req, scope)
                changed[key] = value
                self.rejects(lambda: C.assess_execution(changed, req, "d" * 64, scope))

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
        log, admission = worker_log(req), execution(req)["admission"]
        selected = req["state"] + "\\gradle-home\\.tmp\\" + SELECTED_FILE
        C.assess_worker_log(log, req, admission, selected)
        for changed in (log + log, log.replace(b"jdk17", b"jdk21"), log.replace(b"-Xmx512m", b"-Xmx512m -Xmx2g"),
                        log.replace(b" -ea ", b" -ea -Dos.name=Windows ")):
            self.rejects(lambda: C.assess_worker_log(changed, req, admission, selected))

    def test_worker_literal_encoding_order_and_missing_classpath_filter(self):
        authority, req = worker_authority(), request()
        for charset in ("UTF-8", "windows-1252", "US-ASCII"):
            authority["nativeCharset"] = charset
            self.assertEqual(C.worker_expected(authority, req), WORKER_LITERAL)
        self.assertNotIn(b"resources", WORKER_LITERAL)  # Recorded absent output is filtered, not invented.
        spaced = copy.deepcopy(authority)
        spaced["applicationClasspath"][0]["path"] += " space#"
        expected = b'-cp\r\n"' + WORKER_LITERAL[len(b"-cp\r\n"):-2].replace(b"test;", b"test space#;") + b'"\r\n'
        spaced["nativeEncodedSha256"] = C.digest(expected)
        self.assertEqual(C.worker_expected(spaced, req), expected)
        for charset in ("UTF-16", "UTF-16LE", "utf-8-sig", "cp037", "unsupported-charset", ""):
            changed = dict(authority, nativeCharset=charset)
            self.rejects(lambda: C.worker_expected(changed, req))
        for mutate in (lambda v: v["applicationClasspath"].reverse(),
                       lambda v: v["applicationClasspath"][2].update(kind="directory"),
                       lambda v: v.update(nativeEncodedSha256="f" * 64)):
            changed = copy.deepcopy(authority)
            mutate(changed)
            self.rejects(lambda: C.worker_expected(changed, req))

    def test_worker_authority_rejects_foreign_alias_modular_and_injected_paths(self):
        original, req = worker_authority(), request()
        mutations = [lambda v: v.update(gradleVersion="9.8.0"), lambda v: v.update(testIsModule=0),
            lambda v: v.update(modulePath=["C:\\module.jar"]), lambda v: v.update(gradleHome=r"C:\other\gradle-home"),
            lambda v: v["bootstrap"].update(bytes=True), lambda v: v["bootstrap"].update(sha256="unknown"),
            lambda v: v["bootstrap"].update(path=r"C:\control\state\other\gradle-worker.jar"),
            lambda v: v["bootstrap"].update(path=r"C:\control\state\gradle-home\caches\other.jar"),
            lambda v: v["applicationClasspath"].append(copy.deepcopy(v["applicationClasspath"][0])),
            lambda v: v["applicationClasspath"][1].update(kind="directory"),
            lambda v: v["applicationClasspath"][1].update(kind="missing"),
            lambda v: v["applicationClasspath"][0].update(path=r"C:\sibling\source\library\p2p-core\build\classes"),
            lambda v: v["applicationClasspath"][1].update(path=r"C:\control\state\gradle-home\caches\unknown\a.jar"),
            lambda v: v.update(applicationClasspath=v["applicationClasspath"] * 200),
            lambda v: v.update(unbounded="UNKNOWN_PRIVATE_FIELD"), lambda v: v.pop("beforeFiles")]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(changed)
            self.rejects(lambda: C.worker_expected(changed, req))
        for suffix in (";C:\\x", '"', "'", "*", "?", ":stream", "\\..\\other", "\\.\\other", "\\nul.jar",
                       "\\CON", "\\path.\\other", "\\path \\other", "\\\\other", "/other", "\n", "\0", "\u00e9"):
            changed = copy.deepcopy(original)
            changed["applicationClasspath"][0]["path"] += suffix
            self.rejects(lambda: C.worker_expected(changed, req))
        for path in (r"\\server\share\a", r"\\?\C:\a", "C:/a", r"C:relative", "C:\\x " + "a" * 4096,
                     "C:\\" + "a\\" * 64 + "a"):
            self.rejects(lambda: C.worker_path(path))

    def test_worker_capture_requires_single_new_file_hashes_and_finite_refusals(self):
        req, authority = request(), worker_authority()
        original = worker_capture(req, "a" * 64)
        check = lambda value: C.assess_worker_capture(value, req, "d" * 64, "a" * 64, authority)
        check(original)
        for mutate in (lambda v: v.update(schema=True), lambda v: v.update(requestSha256="a" * 64),
            lambda v: v.update(admissionSha256=None), lambda v: v.update(phase="after-stop"),
            lambda v: v.update(observedMillis=True), lambda v: v.update(original=None),
            lambda v: v.update(afterFiles=None), lambda v: v["afterFiles"].update(exists=1),
            lambda v: v["afterFiles"].update(exists=False), lambda v: v["afterFiles"]["names"].reverse(),
            lambda v: v["afterFiles"]["names"].append(SELECTED_FILE),
            lambda v: v["afterFiles"].update(names=[SELECTED_FILE]),
            lambda v: v["afterFiles"]["names"].append("gradle-worker-classpath999txt"),
            lambda v: v["original"].update(path=req["state"] + "\\gradle-home\\.tmp\\" + COMPILER_FILE),
            lambda v: v["original"].update(path=v["original"]["path"] + ".txt"),
            lambda v: v["original"].update(path=v["original"]["path"].replace("control", "other")),
            lambda v: v["original"].update(bytes=0), lambda v: v["original"].update(bytes=True),
            lambda v: v["original"].update(bytes=C.WORKER_BYTES + 1), lambda v: v["original"].update(sha256="unknown"),
            lambda v: v.update(reason="FAILED_SECRET_BYTES"), lambda v: v.update(secret="UNKNOWN_PRIVATE_CONTENT")):
            changed = copy.deepcopy(original)
            mutate(changed)
            self.rejects(lambda: check(changed))
        for reason in sorted(C.WORKER_CAPTURE_REASONS):
            check(dict(original, status="REFUSED", reason=reason, original=None, afterFiles=None))
        C.assess_worker_capture(dict(original, admissionSha256=None, status="REFUSED", reason="BINDING_CHANGED",
            original=None, afterFiles=None), req, "d" * 64)  # Honest absent-admission failure metadata.

    def test_worker_launch_exact_main_start_id_options_and_only_generated_expansion(self):
        for negative in (False, True):
            req, report = request(negative), execution(request(negative))
            log = worker_log(req)
            path = req["state"] + "\\gradle-home\\.tmp\\" + SELECTED_FILE
            check = lambda value: C.assess_worker_log(value, req, report["admission"], path)
            self.assertEqual(check(log), "2")
            replacements = [(b"Successfully started process 'Gradle Test Executor 2'", b"Successfully started process 'Gradle Test Executor 3'"),
                (b"Gradle Test Executor 2'\r\nSuccessfully", b"Gradle Test Executor 3'\r\nSuccessfully"),
                (C.WORKER_MAIN.encode(), b"worker.Main"), (b" -ea ", b" -ea -javaagent:C:\\inject.jar "),
                (b" -ea ", b" -ea -agentlib:jdwp=transport=dt_socket "), (b" -ea ", b" -ea -Dos.arch=amd64 "),
                (b" -ea ", b" -ea -cp C:\\other "), (b" -ea ", b" -ea --module-path C:\\other "),
                (b" -ea ", b" -ea --class-path C:\\other "), (b" -ea ", b" -ea @C:\\caller "),
                (SELECTED_FILE.encode(), COMPILER_FILE.encode()), (SELECTED_FILE.encode(), SELECTED_FILE.encode() + b".txt"),
                (b"-XX:ActiveProcessorCount=2", b"-XX:ActiveProcessorCount=4"), (b"-Xmx512m", b"-Xmx512m -Xmx1g"),
                (b" -Duser.variant ", b" -Duser.variant=bad option "),
                (b"\\library\\p2p-core Command", b"\\other Command")]
            for before, after in replacements:
                self.rejects(lambda: check(log.replace(before, after)))
            self.rejects(lambda: check(log + log))
            for injected in ("@C:\\user", "-javaagent:C:\\agent.jar", "-Dos.name=Windows", "-Dos.arch=amd64",
                             "-cp", "--class-path=C:\\foreign", "--module-path=C:\\foreign", "-Xmx2g"):
                changed = copy.deepcopy(report)
                changed["admission"]["jvmArgs"].append(injected)
                self.rejects(lambda: C.assess_execution(changed, req, "d" * 64))

    def worker_retention_model(self, negative=False):
        """Tiny local files + fake Windows/leaf identity. No native or Gradle run."""
        base = Path(tempfile.mkdtemp(prefix="worker-retention-model-", dir=self.base))
        output, public = base / "output", base / "public"
        output.mkdir()
        (public / "product").mkdir(parents=True)
        req = request(negative)
        C.new_json(public / "request.json", req)
        request_hash = C.digest(C.regular(public / "request.json"))
        report = execution(req)
        report["requestSha256"] = request_hash
        report["binding"]["localProperties"]["p2pkit.windowsDirectoryRequestSha256"] = request_hash
        envelope = {"schema": 1, "nonce": req["nonce"], "caseName": req["caseName"],
                    "requestSha256": request_hash, "admission": report["admission"]}
        for name, value in (("test-admission.json", envelope), ("execution.json", report)):
            C.new_json(public / name, value)
        capture = worker_capture(req, C.digest(C.regular(public / "test-admission.json")), request_hash)
        C.new_json(output / "worker-classpath.json", capture)
        (output / "worker-classpath.raw").write_bytes(WORKER_LITERAL)
        original, boot = base / "original", base / "bootstrap"
        original.write_bytes(WORKER_LITERAL)
        boot.write_bytes(WORKER_BOOTSTRAP)
        (public / "product/product.stdout.log").write_bytes(worker_log(req))
        leaf = {"id": "f" * 32, "purpose": "product", "valid": True, "retained": True, "status": int(negative)}
        receipt = {"id": leaf["id"], "purpose": "product", "host": "windows-x64", "sourceBefore": req["source"],
            "sourceAfter": req["source"], "sourceUnchanged": True, "stopExitCode": 0, "errors": [], "ownedSurvivors": [],
            "productStartedUtc": "1970-01-01T00:00:00.005000+00:00", "productEndedUtc": "1970-01-01T00:00:00.035000+00:00",
            "stopStartedUtc": "1970-01-01T00:00:00.035000+00:00", "stopEndedUtc": "1970-01-01T00:00:00.040000+00:00",
            "endedUtc": "1970-01-01T00:00:00.045000+00:00"}
        C.new_json(public / "product/receipt.json", receipt)
        snapshot_name = req["outputDirectory"] + "\\worker-classpath.raw"
        files = {str(output / "worker-classpath.raw"): (output / "worker-classpath.raw", snapshot_name),
            snapshot_name: (output / "worker-classpath.raw", snapshot_name),
            capture["original"]["path"]: (original, capture["original"]["path"]),
            report["admission"]["workerExpansion"]["bootstrap"]["path"]: (boot, report["admission"]["workerExpansion"]["bootstrap"]["path"])}
        native_read = C.native_worker_file
        def modeled_file(path, limit):
            actual, spelling = files[str(path)]
            raw, row = native_read(actual, limit)
            row["path"] = spelling  # Explicit finite model mapping; not a Windows filesystem observation.
            return raw, row
        return SimpleNamespace(output=output, public=public, request=req, request_hash=request_hash, report=report,
            envelope=envelope, capture=capture, original=original, boot=boot, leaf=leaf, native=modeled_file)

    def retain_worker_model(self, model):
        with mock.patch.object(C, "native_worker_file", side_effect=model.native):
            return C.retain_worker_expansion(model.output, model.public, model.request, model.request_hash, model.leaf)

    def test_worker_retention_keeps_exact_originals_and_red_green_ordering(self):
        for negative in (False, True):
            model = self.worker_retention_model(negative)
            original_capture = C.regular(model.output / "worker-classpath.json")
            result = self.retain_worker_model(model)
            self.assertEqual(result["status"], "QUALIFIED")
            self.assertEqual(C.regular(model.public / "worker-classpath.json"), original_capture)
            self.assertEqual(C.regular(model.public / "worker-classpath.args"), WORKER_LITERAL)
            self.assertEqual(result, self.retain_worker_model(model))  # Idempotent, not overwritten or retried.
            for key in ("original", "snapshot"):
                self.assertEqual(result[key]["sha256"], C.digest(WORKER_LITERAL))
                self.assertEqual(result[key]["stat"]["links"], 1)
            C.seal_public(model.public, model.request["identity"], model.request["caseName"])
            C.verify_public(model.public, model.request["identity"], model.request["caseName"])

    def test_worker_report_preflight_keeps_unsupported_classpath_metadata_private(self):
        req = request()
        for name in ("test-admission.json", "execution.json", "buildsrc-execution.json"):
            for mutate in (None, lambda v: v["admission"]["workerExpansion"].update(unknown="PRIVATE_METADATA"),
                           lambda v: v["admission"]["workerExpansion"]["applicationClasspath"][0].update(path=r"C:\private\data"),
                           lambda v: v.update(admission=["PRIVATE_METADATA"])):
                base = Path(tempfile.mkdtemp(prefix="worker-report-preflight-", dir=self.base))
                source, destination = base / name, base / ("retained-" + name)
                value = execution(req)
                if mutate:
                    mutate(value)
                C.new_json(source, value)
                original = source.read_bytes()
                if mutate:
                    self.rejects(lambda: C.retain_worker_report(source, destination, req))
                    self.assertFalse(destination.exists())
                else:
                    C.retain_worker_report(source, destination, req)
                    self.assertEqual(destination.read_bytes(), original)
                self.assertEqual(source.read_bytes(), original)

    def test_worker_observation_binds_event_capture_build_and_stop_times_to_original_leaf(self):
        m = self.worker_retention_model()
        check = lambda report, envelope, capture: C.worker_observation(report, envelope, capture, m.request, m.request_hash)
        self.assertEqual(check(m.report, m.envelope, m.capture), WORKER_LITERAL)
        for mutate in (lambda v: v.update(source={}), lambda v: v.update(identity={}),
                       lambda v: v.update(caseName="preimage"), lambda v: v.update(events=[]),
                       lambda v: v["events"][0].update(name="other"), lambda v: v["events"][0].update(endMillis=26),
                       lambda v: v["events"][0].update(startMillis=True), lambda v: v.update(finishedMillis=24),
                       lambda v: v["admission"].update(temporaryFileKey="changed")):
            report = copy.deepcopy(m.report)
            mutate(report)
            self.rejects(lambda: check(report, m.envelope, m.capture))
        for observed in (19, 31):
            self.rejects(lambda: check(m.report, m.envelope, dict(m.capture, observedMillis=observed)))
        receipt = C.read_json(m.public / "product/receipt.json")
        retained = {"leafId": m.leaf["id"], "observedMillis": 50}
        C.worker_leaf_binding(receipt, m.request, retained, m.envelope, m.capture, m.report)
        for key, value in (("host", "linux-x64"), ("sourceAfter", {}), ("stopExitCode", True),
            ("stopExitCode", 1), ("ownedSurvivors", ["MODEL_SURVIVOR"]), ("id", "e" * 32),
            ("productStartedUtc", "1970-01-01T00:00:00.011000+00:00"),
            ("productEndedUtc", "1970-01-01T00:00:00.029000+00:00"),
            ("stopStartedUtc", "1970-01-01T00:00:00.001000+00:00"),
            ("stopEndedUtc", "1970-01-01T00:00:00.034000+00:00"),
            ("endedUtc", "1970-01-01T00:00:00.051000+00:00")):
            self.rejects(lambda: C.worker_leaf_binding(dict(receipt, **{key: value}), m.request, retained,
                                                       m.envelope, m.capture, m.report))

    def test_worker_public_copy_failure_keeps_original_capture_and_native_refusal(self):
        m = self.worker_retention_model()
        original_capture = (m.output / "worker-classpath.json").read_bytes()
        original_write = C.write
        def fail(path, raw):
            if path == m.public / "worker-classpath.args":
                raise OSError("MODELED_PUBLIC_COPY_FAILURE")
            return original_write(path, raw)
        with mock.patch.object(C, "write", side_effect=fail):
            self.rejects(lambda: self.retain_worker_model(m))
        value = C.read_json(m.public / "worker-classpath-retention.json")
        self.assertEqual((value["status"], value["reason"]), ("REFUSED", "PUBLIC_COPY_FAILED"))
        self.assertEqual((m.public / "worker-classpath.json").read_bytes(), original_capture)
        self.assertEqual(C.read_json(m.public / "worker-classpath.json")["status"], "CAPTURED")
        self.assertFalse((m.public / "worker-classpath.args").exists())
        self.assertIsNotNone(value["original"])
        self.assertIsNotNone(value["snapshot"])
        C.seal_public(m.public, m.request["identity"], "current")

    def test_worker_retention_refuses_missing_changed_unbound_or_unsafe_raw_without_public_upload(self):
        mutations = {
            "missing-original": lambda m: m.original.unlink(),
            "missing-snapshot": lambda m: (m.output / "worker-classpath.raw").unlink(),
            "changed-original": lambda m: m.original.write_bytes(b"UNKNOWN_ORIGINAL"),
            "changed-bootstrap": lambda m: m.boot.write_bytes(b"OTHER_MODEL_BOOTSTRAP"),
            "unfinalized": lambda m: m.leaf.update(valid=False),
            "missing-capture": lambda m: (m.output / "worker-classpath.json").unlink(),
            "wrong-worker": lambda m: (m.public / "product/product.stdout.log").write_bytes(b"NOT_A_WORKER_LAUNCH"),
        }
        for label, change in mutations.items():
            with self.subTest(label=label):
                model = self.worker_retention_model()
                change(model)
                self.rejects(lambda: self.retain_worker_model(model))
                self.assertFalse((model.public / "worker-classpath.args").exists())
                self.assertEqual(C.read_json(model.public / "worker-classpath-retention.json")["status"], "REFUSED")
                if (model.public / "worker-classpath.json").exists():
                    self.assertEqual(C.regular(model.public / "worker-classpath.json"), C.regular(model.output / "worker-classpath.json"))
                C.seal_public(model.public, model.request["identity"], "current")  # Safe failure metadata only.
                C.verify_public(model.public, model.request["identity"], "current")
        variants = [b"\xef\xbb\xbf" + WORKER_LITERAL, WORKER_LITERAL.replace(b"\r\n", b"\n"), WORKER_LITERAL + b"\0",
            WORKER_LITERAL.replace(b"\\\\", b"\\"), WORKER_LITERAL + b"# comment\r\n", WORKER_LITERAL + b"-Dfoo=bar\r\n",
            WORKER_LITERAL + b"-javaagent:C:\\injected.jar\r\n", WORKER_LITERAL + b"@C:\\nested\r\n",
            WORKER_LITERAL + b"-cp\r\nC:\\other\r\n", WORKER_LITERAL + b"--module-path\r\nC:\\other\r\n"]
        for raw in variants:
            model = self.worker_retention_model()
            (model.output / "worker-classpath.raw").write_bytes(raw)
            model.original.write_bytes(raw)
            model.capture["original"].update(bytes=len(raw), sha256=C.digest(raw))
            (model.output / "worker-classpath.json").write_bytes(C.audit.json_bytes(model.capture))
            self.rejects(lambda: self.retain_worker_model(model))
            self.assertEqual(C.read_json(model.public / "worker-classpath-retention.json")["reason"], "EXPANSION_MISMATCH")
            self.assertFalse((model.public / "worker-classpath.args").exists())
            self.assertEqual((model.output / "worker-classpath.raw").read_bytes(), raw)
            self.assertFalse(C.public_path("worker-classpath.raw"))

    def test_worker_native_reader_rejects_links_reparse_changes_and_bounds(self):
        path = self.base / "ordinary-worker-model"
        path.write_bytes(WORKER_LITERAL)
        self.assertEqual(C.native_worker_file(path, C.WORKER_BYTES)[0], WORKER_LITERAL)
        self.rejects(lambda: C.native_worker_file(path, 1))
        link = self.base / "worker-hardlink-model"
        os.link(path, link)
        self.rejects(lambda: C.native_worker_file(path, C.WORKER_BYTES))
        link.unlink()
        link.symlink_to(path)
        self.rejects(lambda: C.native_worker_file(link, C.WORKER_BYTES))
        with mock.patch.object(C, "regular", side_effect=lambda file, limit: (file.write_bytes(b"CHANGED"), WORKER_LITERAL)[1]):
            self.rejects(lambda: C.native_worker_file(path, C.WORKER_BYTES))
        with mock.patch.object(C.audit, "reject_symlinks", side_effect=C.audit.AuditError("MODELED_REPARSE")):
            self.rejects(lambda: C.native_worker_file(path, C.WORKER_BYTES))

    def test_worker_public_all_four_entrypoints_reject_malformed_rebound_and_mutated_evidence(self):
        for entry in ("seal", "verify", "retain", "verify-before-disposal"):
            for mutation in ("bytes", "capture", "native-links", "native-missing", "time", "worker", "foreign-classpath", "private-raw"):
                with self.subTest(entry=entry, mutation=mutation):
                    m = self.worker_retention_model()
                    self.retain_worker_model(m)
                    if mutation == "bytes":
                        (m.public / "worker-classpath.args").write_bytes(WORKER_LITERAL + b"\n")
                    elif mutation in ("capture", "native-links", "native-missing", "time"):
                        name = "worker-classpath.json" if mutation == "capture" else "worker-classpath-retention.json"
                        value = C.read_json(m.public / name)
                        if mutation == "capture":
                            value["unknown"] = "UNAPPROVED_RAW_FIELD"
                        elif mutation == "native-links":
                            value["original"]["stat"]["links"] = 2
                        elif mutation == "native-missing":
                            value["snapshot"] = None
                        else:
                            value["observedMillis"] = 24
                        (m.public / name).write_bytes(C.audit.json_bytes(value))
                    elif mutation == "worker":
                        (m.public / "product/product.stdout.log").write_bytes(worker_log(m.request).replace(b"Test Executor 2", b"Test Executor 3", 1))
                    elif mutation == "foreign-classpath":
                        value = C.read_json(m.public / "test-admission.json")
                        value["admission"]["workerExpansion"]["applicationClasspath"][0]["path"] = r"C:\other\private"
                        (m.public / "test-admission.json").write_bytes(C.audit.json_bytes(value))
                    else:
                        (m.public / "worker-classpath.raw").write_bytes(b"UNKNOWN_PRIVATE_CONTENT")
                    identity = m.request["identity"]
                    rows = C.inventory(m.public)
                    if entry == "seal":
                        action = lambda: C.seal_public(m.public, identity, "current")
                    elif entry == "verify":
                        C.new_json(m.public / "manifest.json", C.public_manifest(identity, "current", rows))
                        action = lambda: C.verify_public(m.public, identity, "current")
                    elif entry == "retain":
                        action = lambda: C.retain_before_disposal(m.public, identity, "current")
                    else:
                        # An expected retention ledger cannot authorize malformed worker evidence either.
                        expected = {"schema": 1, "identity": identity, "caseName": "current", "files": rows}
                        C.new_json(m.public / "retained-before-disposal.json", expected)
                        action = lambda: C.verify_before_disposal(m.public, expected)
                    self.rejects(action)

    def test_worker_retention_failure_never_replaces_existing_product_failure(self):
        controller, case, _ = self.jvm_temporary_model()
        primary = C.audit.AuditError("MODEL_PRIMARY_PRODUCT_FAILURE")
        with mock.patch.object(controller, "leaf", side_effect=primary), \
                mock.patch.object(C, "retain_worker_expansion", side_effect=OSError("MODEL_CAPTURE_COPY_FAILURE")):
            with self.assertRaises(C.audit.AuditError) as caught:
                controller.product(case)
        self.assertIs(caught.exception, primary)
        self.assertFalse(case["productRetained"])
        self.assertTrue(case["retentionErrors"])
        self.assertTrue((case["public"] / "temporary-after.json").is_file())
        self.rejects(lambda: C.require_disposal_evidence(case))

    def test_worker_policy_report_requires_complete_actual_results_without_self_approval(self):
        hashes = {"scope": "MODELED_REPORT_ONLY"}
        report = self.binding_report(hashes)
        C.assess_binding_controls(report, hashes, require_pass=True)
        for mutate in (lambda v: v.update(schema=3), lambda v: v.pop("workerPolicyCases"),
                       lambda v: v["workerPolicyCases"].pop(), lambda v: v["workerPolicyCases"].reverse(),
                       lambda v: v["workerPolicyCases"][0].update(value="same-name-wrong-bytes"),
                       lambda v: v["workerPolicyCases"][0].update(passed=1),
                       lambda v: v["workerPolicyCases"][0].update(raw="UNAPPROVED")):
            changed = copy.deepcopy(report)
            mutate(changed)
            self.rejects(lambda: C.assess_binding_controls(changed, hashes, require_pass=True))
        report["workerPolicyCases"][0].update(passed=False, value="ACTUAL_WRONG_MODEL_RESULT")
        C.assess_binding_controls(report, hashes, require_pass=False)
        self.rejects(lambda: C.assess_binding_controls(report, hashes, require_pass=True))

    def test_live_service_report_rejects_modeled_stale_or_falsely_passing_results(self):
        hashes = {"scope": "MODELED_REPORT_ONLY"}
        original = self.binding_report(hashes)
        C.assess_binding_controls(original, hashes, require_pass=True)
        mutations = [lambda v: v.update(schema=4), lambda v: v.pop("workerServiceCases"),
            lambda v: v.update(workerServiceCases=None), lambda v: v["workerServiceCases"].pop(),
            lambda v: v["workerServiceCases"].reverse(),
            lambda v: v["workerServiceCases"].__setitem__(1, copy.deepcopy(v["workerServiceCases"][0])),
            lambda v: v["workerServiceCases"][0].update(exceptionType="org.gradle.api.GradleException"),
            lambda v: v["workerServiceCases"][0].update(message="unknown classpath 'OTHER' requested."),
            lambda v: v["workerServiceCases"][0].update(passed=1),
            lambda v: v["workerServiceCases"][1].update(bootstrap=None),
            lambda v: v["workerServiceCases"][1].update(exceptionType="java.lang.IllegalStateException"),
            lambda v: v["workerServiceCases"][1].update(message="wrong failure"),
            lambda v: v["workerServiceCases"][1].update(raw="UNAPPROVED")]
        for field, value in (("relativePath", "../gradle-worker.jar"), ("relativePath", "caches/../gradle-worker.jar"),
                             ("relativePath", "caches/./gradle-worker.jar"), ("relativePath", "caches//gradle-worker.jar"),
                             ("relativePath", "C:/foreign/gradle-worker.jar"), ("relativePath", "caches/x/wrong.jar"),
                             ("bytes", True), ("bytes", 0), ("bytes", 4 * 1024 ** 2 + 1),
                             ("sha256", "INVALID"), ("extra", "UNAPPROVED")):
            mutations.append(lambda v, field=field, value=value: v["workerServiceCases"][1]["bootstrap"].update({field: value}))
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(original)
                mutate(changed)
                self.rejects(lambda: C.assess_binding_controls(changed, hashes, require_pass=True))
        # Preserve real wrong outcomes with false verdicts; never call them a pass.
        for index in (0, 1):
            failed = copy.deepcopy(original)
            failed["workerServiceCases"][index].update(passed=False, bootstrap=None,
                exceptionType="java.lang.IllegalStateException", message="MODEL wrong live lookup outcome")
            C.assess_binding_controls(failed, hashes, require_pass=False)
            self.rejects(lambda: C.assess_binding_controls(failed, hashes, require_pass=True))

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

    def test_native_directory_policy_public_path_is_one_exact_reviewed_marker(self):
        name = C.NATIVE_DIRECTORY_POLICY_MARKER
        self.assertTrue(C.native_public_path(name))
        self.assertTrue(C.public_path("native-controls/" + name))
        for wrong in (name.replace(name.split("/")[0], "test_other"), name.replace("marker.txt", "private.json"),
                      name + ".extra", name + "/private", "./" + name, name.replace("/nested/", "//nested/"),
                      name.replace("/before/", "/before/../before/"), name.upper()):
            self.assertFalse(C.native_public_path(wrong), wrong)
        # The actual native fixture must still produce exactly these synthetic
        # bytes; no arbitrary data/JSON allowance or public SID dump is added.
        native = next(node for node in ast.parse((ROOT / "scripts/tests/run-audit-command-test.py").read_bytes()).body
                      if isinstance(node, ast.ClassDef) and node.name == "WindowsNativeTests")
        method = next(node for node in native.body if isinstance(node, ast.FunctionDef) and
                      node.name == name.split("/")[0])
        raw = [node.value.value for node in ast.walk(method) if isinstance(node, ast.Assign) and
               any(isinstance(target, ast.Name) and target.id == "raw" for target in node.targets)]
        self.assertEqual(raw, [C.NATIVE_DIRECTORY_POLICY_BYTES])

    def test_synthetic_public_copy_rejects_changed_bytes_before_creating_destination(self):
        source = self.base / "original-marker.txt"
        expected = C.NATIVE_DIRECTORY_POLICY_BYTES
        source.write_bytes(expected)
        destination = self.base / "accepted/marker.txt"
        C.copy_public(source, destination, expected=expected)
        self.assertEqual(destination.read_bytes(), expected)
        for index, wrong in enumerate((expected[:-1], expected + b"X", b"PRIVATE-MODEL-SENTINEL")):
            source.write_bytes(wrong)
            target = self.base / f"rejected-{index}/marker.txt"
            self.rejects(lambda: C.copy_public(source, target, expected=expected))
            self.assertFalse(target.parent.exists())
            self.assertEqual(source.read_bytes(), wrong)

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

    def native_admission(self, *, failed=False, residue=False, write_failed=False, inventory_failed=False,
                         cleanup_failed=False, directory_marker=None):
        controller, case, temporary = self.native_model()
        original = RuntimeError("MODEL original native failure")
        native = case["state"] / "evidence/native-controls"
        (native / "test_model").mkdir(parents=True)
        C.new_json(native / "test_model/case.json", {"scope": "MODEL_ONLY_NOT_NATIVE"})
        if directory_marker is not None:
            marker = native / C.NATIVE_DIRECTORY_POLICY_MARKER
            marker.parent.mkdir(parents=True)
            marker.write_bytes(directory_marker)
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

    def test_native_caller_retains_only_exact_synthetic_directory_policy_marker(self):
        controller, case, error, _, cleanup = self.native_admission(directory_marker=C.NATIVE_DIRECTORY_POLICY_BYTES)
        self.assertIsNone(error)
        self.assertTrue(case["nativeAccepted"])
        cleanup.assert_called_once()
        retained = controller.public / "admission/native-controls" / C.NATIVE_DIRECTORY_POLICY_MARKER
        self.assertEqual(retained.read_bytes(), C.NATIVE_DIRECTORY_POLICY_BYTES)
        controller, case, error, _, cleanup = self.native_admission(directory_marker=b"PRIVATE-MODEL-SENTINEL")
        self.assertIsInstance(error, C.audit.AuditError)
        self.assertTrue(case["retentionErrors"])
        self.assertFalse(case["nativeAccepted"])
        cleanup.assert_not_called()
        self.assertFalse((controller.public / "admission/native-controls" / C.NATIVE_DIRECTORY_POLICY_MARKER).exists())
        self.assertEqual((case["state"] / "evidence/native-controls" / C.NATIVE_DIRECTORY_POLICY_MARKER).read_bytes(),
                         b"PRIVATE-MODEL-SENTINEL")

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


class RetainedControllerDirectoryTests(unittest.TestCase):
    """Actual tiny caller bodies with modeled ACLs/Jobs/Tee; never native proof."""

    @contextmanager
    def fixture(self):
        with F.modeled_retained_directories() as model:
            model.errors, model.opened, model.scopes, model.records = {}, [], [], {}
            model.writes = []

            def fail(operation, path):
                error = model.errors.get((operation, path), model.errors.get((operation, path.name)))
                if error is not None:
                    raise error

            class Directory:
                def __init__(self, path, original):
                    self.path, self.original, self._closed = path, original, False
                    info = path.lstat()
                    self.identity = (info.st_dev, format(info.st_ino, "032x"))
                    model.opened.append(self)

                def verify(self):
                    fail("verify", self.path)
                    if self._closed:
                        raise AssertionError("MODEL closed native capability used")
                    model.check(self.path)
                    return F.windows_files.FileInfo(self.identity, True, 0, 1, 16, 1, 1, 1,
                                                   "S-1-5-21-1-2-3-1001", True)

                def create_directory(self, relative, **kwargs):
                    path = self.path.joinpath(*F.windows_files.relative_parts(relative))
                    fail("create", path)
                    return Directory(path, F.windows_files.create_private_directory(path))

                def open_directory(self, relative, **kwargs):
                    path = self.path.joinpath(*F.windows_files.relative_parts(relative))
                    fail("open", path)
                    return Directory(path, F.windows_files.open_private_directory(path))

                @contextmanager
                def snapshot(self, **kwargs):
                    fail("snapshot", self.path)
                    if list(self.path.iterdir()):
                        raise AssertionError("MODEL new directory is not empty before payload")
                    yield SimpleNamespace(entries={"": self.verify()})

                def close(self):
                    model.events.append(("transient-close", self.path))
                    fail("close", self.path)
                    self.original.__exit__(None, None, None)
                    self._closed = True

            root = F.retained_directory(model.base / "retained")
            fixture = N.Fixture.__new__(N.Fixture)
            fixture.root = Directory(root, F.windows_files.open_private_directory(root))
            fixture.owners, fixture.observations = [fixture.root], []
            fixture.unknown, fixture.expected_hold = False, False
            fixture.job = "MODEL_JOB_NOT_NATIVE"
            fixture.name = "native-controller-command"

            def scope_factory(*args, **kwargs):
                scope = SimpleNamespace(job="MODEL_JOB_NOT_NATIVE")
                def spawn(argv, cwd, env):
                    # These explicit bytes model the two reviewed emitters;
                    # no subprocess, arbitrary argv interpreter or thread runs.
                    partial = scope.spawn.call_count == 2
                    return SimpleNamespace(stdout=io.BytesIO(b"partial-original" if partial else b"controller-native\x00\xff\r\n"),
                        stderr=io.BytesIO(b"sibling-original" if partial else b"original-stderr"),
                        poll=lambda: 0, wait=lambda **_: 0)
                scope.spawn = mock.Mock(side_effect=spawn)
                scope.discover, scope.drain = mock.Mock(return_value=[]), mock.Mock(return_value=[])
                scope.description = mock.Mock(return_value={"discoveryErrors": []})
                scope.close = mock.Mock(side_effect=lambda: setattr(scope, "job", None))
                model.scopes.append(scope)
                return scope

            original_new_file, original_open = C.audit.new_file, Path.open

            def before_write(path):
                model.check(path.parent)
                fail("write", path)
                model.writes.append(path)

            def new_file(path):
                before_write(path)
                return original_new_file(path)

            def open_file(path, mode="r", *args, **kwargs):
                if any(flag in mode for flag in "wax") and model.base in path.parents:
                    before_write(path)
                return original_open(path, mode, *args, **kwargs)

            class Tee:
                def __init__(self, source, target, *unused):
                    self.source, self.target = source, target
                    self.errors, self._start_attempted = [], False
                    self._complete = SimpleNamespace(is_set=lambda: self.source.closed)
                    self.thread = SimpleNamespace(is_alive=lambda: False)
                def start(self):
                    self._start_attempted = True
                    with C.audit.new_file(self.target) as stream:
                        stream.write(self.source.read())
                def finish(self):
                    self.source.close()

            def record(name, value):
                model.records[name] = value
                C.new_json(root / (name + ".json"), value)
            fixture.record = record
            model.fixture = fixture
            environment = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
            with mock.patch.object(N, "C", C), mock.patch.object(N, "A", C.audit), \
                    mock.patch.object(C, "controlled_environment", return_value={}), \
                    mock.patch.object(C.processes, "ownership_environment", return_value={"GRADLE_USER_HOME": "MODEL"}), \
                    mock.patch.object(C.processes, "make_scope", side_effect=scope_factory), \
                    mock.patch.object(C, "native_memory", side_effect=AssertionError("MODEL cannot inspect native host")), \
                    mock.patch.object(subprocess, "Popen", side_effect=AssertionError("MODEL cannot launch")), \
                    mock.patch.object(C.audit, "Tee", Tee), mock.patch.object(C.audit, "new_file", side_effect=new_file), \
                    mock.patch.object(Path, "open", new=open_file), mock.patch.dict(os.environ, environment), \
                    mock.patch.object(N, "_RETAIN_TO_EXIT", []):
                yield model

    def test_native_controller_command_directories_are_private_before_actual_writers(self):
        with self.fixture() as model:
            model.fixture.native_controller_command()
            row = model.records["controller-command-observed"]
            self.assertFalse(row["productGradleExecuted"])
            self.assertTrue(row["cases"][0]["firstTeeRetired"])
            self.assertTrue(model.writes)
            self.assertTrue(all(scope.job is None for scope in model.scopes))
            for owner in model.opened:
                self.assertEqual(owner._closed, owner not in model.fixture.owners)

    def test_native_controller_retirement_roots_are_private_before_actual_sentinels(self):
        with self.fixture() as model:
            model.fixture.name = "native-controller-retirement"
            model.fixture.native_controller_retirement()
            row = model.records["controller-native-retirement"]
            self.assertTrue(row["allFiveRootsPreservedPerCase"])
            sentinels = [path for path in model.writes if path.name == "unstarted-sentinel"]
            self.assertEqual(len(sentinels), 10)
            self.assertTrue(all(path.read_bytes() == b"UNSTARTED_FIXTURE_NOT_PRODUCT" for path in sentinels))
            self.assertEqual(len(model.scopes), 3)
            self.assertTrue(all(scope.job is None for scope in model.scopes))

    def test_ordinary_witness_default_and_hand_built_callers_keep_original_flags(self):
        path = mock.Mock()
        controller = C.Controller.__new__(C.Controller)
        self.assertIs(controller.directory_creator, C.witness_directory)
        self.assertIs(controller.directory_creator(path, parents=True, exist_ok=True), path)
        path.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)

    def test_constructor_native_refusal_does_not_write_spawn_retry_or_fall_back(self):
        with self.fixture() as model:
            original = OSError("MODEL native directory creation refused")
            model.errors[("create", "public")] = original
            with self.assertRaises(OSError) as caught:
                model.fixture.actual_controller()
            self.assertIs(caught.exception, original)
            self.assertTrue(model.fixture.controller_directories.failed)
            self.assertFalse(model.fixture.unknown)
            self.assertEqual(model.writes, [])
            self.assertEqual(model.scopes, [])
            self.assertFalse(any(kind == "python-mkdir" for kind, _ in model.events))

    def test_transient_close_failure_latches_unknown_and_blocks_next_writer(self):
        with self.fixture() as model:
            controller = model.fixture.actual_controller()
            storage, path = model.fixture.controller_directories, controller.base / "close-fault"
            original = OSError("MODEL native close did not complete")
            model.errors[("close", path)] = original
            with self.assertRaises(OSError) as caught:
                storage(path)
            self.assertIs(caught.exception, original)
            self.assertTrue(model.fixture.unknown)
            self.assertTrue(storage.failed)
            self.assertEqual(len(storage.active), 1)
            self.assertIn(storage, N._RETAIN_TO_EXIT)
            events = list(model.events)
            with self.assertRaisesRegex(N.H.HelperError, "CUSTODY_HELD"):
                storage(controller.base / "must-not-create")
            self.assertEqual(model.events, events)
            self.assertEqual(model.writes, [])

    def test_verification_cancellation_preserves_original_and_secondary_close_error(self):
        with self.fixture() as model:
            controller = model.fixture.actual_controller()
            path, storage = controller.base / "combined", model.fixture.controller_directories
            original, secondary = KeyboardInterrupt("MODEL verify cancellation"), OSError("MODEL secondary close")
            model.errors[("verify", path)], model.errors[("close", path)] = original, secondary
            with self.assertRaises(KeyboardInterrupt) as caught:
                storage(path)
            self.assertIs(caught.exception, original)
            self.assertIn("MODEL secondary close", str(getattr(original, "__notes__", [])))
            self.assertTrue(model.fixture.unknown)
            self.assertEqual(model.events.count(("transient-close", path)), 1)
            self.assertEqual(model.writes, [])

    def test_acquisition_parent_close_unknown_is_not_lost_without_a_returned_owner(self):
        with self.fixture() as model:
            controller = model.fixture.actual_controller()
            path, storage = controller.base / "acquisition-fault", model.fixture.controller_directories
            original = OSError("MODEL acquisition parent close")
            F.windows_files._note(original, "Native handle retirement UNKNOWN: 17")
            model.errors[("create", path)] = original
            with self.assertRaises(OSError) as caught:
                storage(path)
            self.assertIs(caught.exception, original)
            self.assertEqual(storage.active, [])
            self.assertTrue(model.fixture.unknown)
            self.assertIn(storage, N._RETAIN_TO_EXIT)
            self.assertFalse(path.exists())
            self.assertEqual(model.writes, [])

    def test_recursive_native_parents_existing_readmission_and_exclusive_creation(self):
        with self.fixture() as model:
            controller = model.fixture.actual_controller()
            path, storage = controller.base / "nested/leaf", model.fixture.controller_directories
            self.assertEqual(storage(path, parents=True), path)
            self.assertEqual(storage(path, parents=True, exist_ok=True), path)
            self.assertEqual([row["created"] for row in storage.rows[-3:]], [True, True, False])
            with self.assertRaises(FileExistsError):
                storage(path)
            self.assertFalse(model.fixture.unknown)
            self.assertEqual(model.writes, [])

    def test_broad_file_and_reparse_refuse_without_repair_or_unsafe_parent_creation(self):
        for kind in ("broad", "file", "reparse"):
            with self.subTest(kind=kind), self.fixture() as model:
                controller = model.fixture.actual_controller()
                path, storage = controller.base / kind, model.fixture.controller_directories
                if kind == "broad":
                    path.mkdir(mode=0o700)  # Deliberate documented three-ACE model.
                elif kind == "file":
                    path.write_bytes(b"MODEL regular file, not a directory")
                events = list(model.events)
                if kind == "reparse":
                    with mock.patch.object(N.A, "reject_symlinks", side_effect=C.audit.AuditError("MODEL reparse refused")), \
                            self.assertRaisesRegex(C.audit.AuditError, "reparse"):
                        storage(path, parents=True, exist_ok=True)
                    self.assertEqual(model.events, events)
                else:
                    with self.assertRaises(F.windows_files.FilesystemError):
                        storage(path, exist_ok=True)
                    self.assertEqual(model.events[len(events):], [("native-open", path)])
                self.assertFalse(model.fixture.unknown)

    def test_outside_parent_parent_components_and_devices_refuse_before_lookup(self):
        for suffix in ("outside", "..", "CON", "file:ads", "trailing."):
            with self.subTest(suffix=suffix), self.fixture() as model:
                controller = model.fixture.actual_controller()
                path = model.base / "outside" if suffix == "outside" else controller.base / suffix
                with mock.patch.object(N.A, "existing_lstat", side_effect=AssertionError("Unsafe path reached lookup")), \
                        self.assertRaises((ValueError, F.windows_files.FilesystemError)):
                    model.fixture.controller_directories(path, parents=True, exist_ok=True)
                self.assertFalse(model.fixture.unknown)

    def test_missing_changed_or_unretired_native_directory_observations_cannot_pass(self):
        for name in ("native-controller-command", "native-controller-retirement"):
            with self.subTest(name=name), self.fixture() as model:
                fixture = model.fixture
                fixture.name = name
                getattr(fixture, name.replace("-", "_"))()
                label = N.H.NATIVE_OBSERVATIONS[name][0]
                observed = json.loads(N.H.encoded(model.records[label]))
                admitted = {"sourceSha": "a" * 40, "sourceTree": "b" * 40, "runId": "123", "runAttempt": "1"}

                def accept(row):
                    raw = N.H.encoded(row)
                    value = {"schema": 1, "case": name, "native": True, "passed": True,
                        "source": {"commit": "a" * 40, "tree": "b" * 40}, "run": {"id": "123", "attempt": "1"},
                        "observations": [{"path": label + ".json", "sha256": N.H.digest(raw)}],
                        "privateDecryption": "NOT_RUN", "expectedPinHoldToInterpreterExit": False,
                        "retirement": "KNOWN", "acceptanceAuthority": "PARENT_ZERO_EXIT_AND_NATIVE_JOB_RETIREMENT"}
                    N.H.assert_native_result(name, value, admitted, lambda _: raw)

                accept(observed)  # A source-owned model of the whole strict record, NOT native acceptance.
                changes = [lambda row: row.pop("directoryCustody"),
                    lambda row: row["directoryCustody"].update(retirement="UNKNOWN"),
                    lambda row: row["directoryCustody"]["directories"].pop(6),
                    lambda row: row["directoryCustody"]["directories"].append(row["directoryCustody"]["directories"][0])]
                changes += [lambda row, key=key, value=value: row["directoryCustody"]["directories"][0].update({key: value})
                            for key, value in (("path", "outside"), ("created", 1), ("emptyBeforeWrite", False),
                                               ("transientClosedBeforeWrite", False))]
                changes += [lambda row, key=key, value=value: row["directoryCustody"]["directories"][0]["beforeWrite"].update({key: value})
                            for key, value in (("identity", [True, "a" * 32]), ("is_directory", False),
                                               ("protected_dacl", False), ("attributes", 0x410), ("owner_sid", None))]
                if name == "native-controller-command":
                    changes.append(lambda row: row["directoryCustody"]["directories"][-1]["beforeWrite"].update(
                        identity=[row["directoryCustody"]["parentIdentity"][0], "a" * 32]))
                for number, change in enumerate(changes):
                    with self.subTest(mutation=number):
                        altered = copy.deepcopy(observed)
                        change(altered)
                        with self.assertRaises(N.H.HelperError):
                            accept(altered)


def load_tests(loader, tests, pattern):
    # The existing unconditional CI/release entry owns this added pure/model
    # suite exactly once. It does not select or execute any native helper case.
    spec = importlib.util.spec_from_file_location("windows_helper_models",
                                                 ROOT / "scripts/tests/windows-helper-controls-test.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    tests.addTests(loader.loadTestsFromModule(module))
    return tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
