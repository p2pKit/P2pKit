#!/usr/bin/env python3
"""Pure policy/file/mock controls, NOT native Windows or Gradle execution.

Only three bounded read-only Git queries obtain the immutable reviewed preimages.
All controller process, tool and native operations below are fake; no wrapper,
native fixture suite, SDK installer, host impersonation or network is executed.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("windows_control_fixture", ROOT / "scripts/run-windows-directory-control.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
BAD = (C.audit.AuditError, ValueError)


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

    def materialization(self, inherited, failure=None):
        """Real producer caller/consumer; Git configuration lookup is only modeled."""
        with tempfile.TemporaryDirectory(prefix="materialize-", dir=self.base) as temporary:
            directory = Path(temporary)
            controller = C.Controller.__new__(C.Controller)
            controller.root, controller.state = directory / "campaign", directory / "state"
            controller.root.mkdir()
            controller.state.mkdir()
            controller.identity = {"sourceSha": "a" * 40, "scope": "MODEL_ONLY_NOT_HOSTED"}
            controller.env = {"SCOPE": "MODEL_ONLY_NOT_HOSTED"}
            parent = directory / "current"
            root = parent / "source"
            root.mkdir(parents=True)
            case = {"parent": parent, "root": root, "public": directory / "public"}
            case["public"].mkdir()
            archive = parent / "source.tar"
            receipt = case["public"] / "source-materialization.json"
            value, name = b"source\n", "dir/source.kt"
            blob = hashlib.sha1(b"blob 7\0" + value).hexdigest()
            listing = ("100644 blob " + blob + " 7\t" + name + "\0").encode()
            trace, captures, produced = [], {}, {}
            command_failure = []
            if failure == "existing":
                archive.write_bytes(b"existing transport sentinel\n")
            git_prefix = ["git", "--no-replace-objects", "-c", "core.autocrlf=false", "-c", "core.fsmonitor=false",
                          "-c", "commit.gpgSign=false", "-c", "core.hooksPath=" + str(controller.state), "-C", str(root)]
            git_commands = [["update-ref", "--no-deref", "HEAD", "a" * 40], ["read-tree", "a" * 40],
                            ["ls-tree", "-rlz", "a" * 40]]

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
                    self.assertEqual(argv, git_prefix + git_commands[len(trace) - 2])
                    self.assertEqual((cwd, timeout), (root, 120))
                    stdout = listing if len(trace) == 4 else b""
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
                              "bytes": "Linked, missing, extra, duplicate or oversized archive member"}
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
                    attempted = ["source-clone"] + ([] if failure == "clone" else ["git"] * 3)
                    if failure not in ("clone", "existing"):
                        attempted.append("source-archive")
                    self.assertEqual([row["label"] for row in trace], attempted)
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
                    self.assertEqual(trace[-1]["archiveOverrides"], ["false"])
                    self.assertEqual(trace[-1]["argv"], ["git", "--no-replace-objects", "-c", "core.autocrlf=false",
                        "-C", str(root), "archive", "--format=tar", "--output=" + str(archive), "a" * 40])
                    self.assertEqual(C.read_json(receipt), {"schema": 1, "commit": "a" * 40,
                        "archiveSha256": C.digest(produced["raw"]), "archiveBytes": len(produced["raw"]),
                        "fileCount": 1, "sourceBytes": len(value), "everyBlobVerified": True})
                    self.assertFalse(archive.exists())
                elif failure == "existing":
                    self.assertEqual(archive.read_bytes(), b"existing transport sentinel\n")
                elif failure == "clone":
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
