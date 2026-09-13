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
        for members in ([], [("dir/source.kt", b"source\r\n", tarfile.REGTYPE)],
                        [("../source.kt", b"source\n", tarfile.REGTYPE)], [("dir/source.kt", b"", tarfile.SYMTYPE)]):
            self.rejects(lambda: C.export_archive(archive(members), entries, self.base / "unused"))

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
