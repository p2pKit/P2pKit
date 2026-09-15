#!/usr/bin/env python3
"""Modeled controller boundaries only; no subprocess, SDK, Android or native admission.

These tests use tiny owned files and substituted command/process/pipe observations.
They do not run the unchanged content/manifest suites or turn fixtures into runtime
evidence. In particular no native launch adapter is supplied by this test module.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("android_ui_controller_test_subject", SCRIPTS / "android_ui_controller.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
runner = core.load_tool("run-audit-command.py")
checker = core.load_tool("check-audit-receipt.py")
artifacts = core.load_tool("verify-android-acceptance-artifacts.py")
manifests = core.load_tool("run-android-art-smoke.py")
verifier = core.load_tool("verify-android-ui-evidence.py")

SOURCE = {"commit": "1" * 40, "tree": "2" * 40, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
TOKEN = "3" * 32


def binding(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write(path, raw):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with runner.new_file(path) as stream:
        stream.write(raw)


def receipt(state, root, context, identifier, kind, purpose, argv):
    return {"schema": 1, "id": identifier, "kind": kind, "purpose": purpose,
            "jobId": context["id"], "host": context["host"], "gradleHome": context["gradleHome"],
            "cwd": str(root), "wrapper": str(root / "gradlew"), "requestedArgv": argv,
            "executedArgv": [str(root / "gradlew"), *runner.gradle_arguments(argv)] if kind == "gradle" else argv,
            "productExitCode": 0, "finalExitCode": 0, "stopExitCode": 0, "sourceUnchanged": True,
            "sourceBefore": SOURCE, "sourceAfter": SOURCE, "errors": [], "ownedSurvivors": [],
            "evidenceDirectory": str(state / "evidence" / identifier)}


def observation(evidence, number, raw=b"", status=0, destination=None):
    path = destination if destination is not None else evidence / f"model-{number}.stdout"
    write(path, raw)
    return {"stdout": str(path), "exitCode": status, "stdoutEof": True, "stderrEof": True,
            "retention": "COMPLETE_STREAMS", "errors": []}


class ModelGuest:
    """Local synthetic tree -> modeled run-as replies; never executes a command."""
    def __init__(self, remote, evidence):
        self.remote, self.evidence = remote, evidence
        self.count, self.calls = 0, []
        self.after_cat = None
        self.short = False
        self.reply = None

    def run_as(self, label, arguments, seconds=40, limit=core.STREAM_LIMIT, destination=None):
        self.calls.append((label, arguments, seconds, limit))
        self.count += 1
        path = self.remote / arguments[-1]
        if self.reply is not None:
            raw = self.reply(arguments)
        elif arguments[0] == "stat":
            if not os.path.lexists(path):
                return observation(self.evidence, self.count, b"", 1)
            info = path.lstat()
            raw = (f"{info.st_dev}|{info.st_ino}|{info.st_mode:x}|{info.st_nlink}|10001|{info.st_size}|"
                   f"{int(info.st_mtime)}|{int(info.st_ctime)}\n").encode()
        elif arguments[0] == "ls":
            raw = (".\n..\n" + "".join(name + "\n" for name in sorted(os.listdir(path)))).encode()
        else:
            raw = path.read_bytes()
            if self.short:
                raw = raw[:-1]
            if self.after_cat is not None:
                action, self.after_cat = self.after_cat, None
                action()
        return observation(self.evidence, self.count, raw, destination=destination)


class ModelPipe:
    def __init__(self, fd, chunks):
        self.fd, self.chunks, self.closed = fd, list(chunks), False

    def fileno(self):
        return self.fd

    def close(self):
        self.closed = True


class ModelSelector:
    def __init__(self):
        self.keys = {}

    def register(self, pipe, _events, data):
        self.keys[pipe.fd] = SimpleNamespace(fileobj=pipe, data=data)

    def unregister(self, pipe):
        del self.keys[pipe.fd]

    def get_map(self):
        return self.keys

    def select(self, _seconds):
        return [(key, None) for key in list(self.keys.values()) if key.fileobj.chunks]

    def close(self):
        self.keys.clear()


class ControllerTests(unittest.TestCase):
    def setUp(self):
        no_processes = mock.patch.object(core.subprocess, "Popen", side_effect=AssertionError("No real subprocess allowed"))
        no_processes.start()
        self.addCleanup(no_processes.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-ui-controller-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root, self.state, self.evidence = (self.base / name for name in ("source", "state", "evidence"))
        for directory in (self.root, self.state, self.evidence):
            directory.mkdir(mode=0o700)
        write(self.root / "gradlew", b"model wrapper; never executed\n")
        self.context = {"id": "4" * 32, "root": str(self.root), "host": "macos-arm64", "source": SOURCE,
                        "gradleHome": str(self.state / "gradle-home"), "preexistingOutputPaths": []}

    def make_intake(self):
        app_xml = (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{core.PACKAGE}">'
                   '<uses-sdk android:minSdkVersion="24" android:targetSdkVersion="37"/>'
                   '<application android:debuggable="true"/>'
                   '<uses-permission android:name="android.permission.ACCESS_LOCAL_NETWORK"/></manifest>').encode()
        test_xml = (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{core.PACKAGE}.test">'
                    '<uses-sdk android:minSdkVersion="24" android:targetSdkVersion="37"/>' + "".join(
                        f'<instrumentation android:name="{name}" android:targetPackage="{core.PACKAGE}"/>'
                        for name in manifests.INSTRUMENTATIONS) + '</manifest>').encode()
        components, reports = {}, []
        producer_id, inspector_id = "5" * 32, "6" * 32
        inspected = self.state / "evidence/android-acceptance-artifacts"
        for role, package, kind, xml in (("app", core.PACKAGE, "APPLICATION", app_xml),
                                         ("test", core.PACKAGE + ".test", "ANDROID_TEST", test_xml)):
            source = artifacts.MODULE_BUILD + "/generated/" + role + "/AndroidManifest.xml"
            retained = artifacts.REPORT_DIRECTORY + "/" + role + "-merged-AndroidManifest.xml"
            provider = artifacts.MODULE_BUILD + "/outputs/" + role
            apk = provider + "/one.apk"
            apk_raw = (role + " tiny model APK").encode()
            tasks = [":p2p-sample-android:assembleDebug" if role == "app" else
                     ":p2p-sample-android:assembleDebugAndroidTest"]
            manifest = {"sourcePath": source, "retainedPath": retained, **binding(xml), "producerTasks": tasks}
            output = {"providerPath": provider, "path": apk, **binding(apk_raw), "producerTasks": tasks,
                      "outputType": "SINGLE", "filters": []}
            components[role] = {"componentKind": kind, "applicationId": package, "variantName": "debug",
                                "manifest": manifest, "apk": output,
                                "metadataProjection": {"kind": "AGP_BUILT_ARTIFACTS_API_PROJECTION", "artifactType": "APK",
                                    "applicationId": package, "variantName": "debug", "elementCount": 1,
                                    "versionCode": 1, "versionName": "model"}}
            for path in (self.root / source, self.root / retained,
                         self.state / "evidence" / producer_id / "reports" / retained,
                         inspected / (role + "-generated.xml"), inspected / (role + "-packaged.xml")):
                write(path, xml)
            write(self.root / apk, apk_raw)
            reports.append({"source": retained, "retained": "reports/" + retained,
                            "classification": "changed-since-admission", **binding(xml)})
        data = {"schemaVersion": 1, "taskPath": artifacts.TASK, "variantName": "debug", "components": components}
        raw_map = runner.json_bytes(data)
        for path in (self.root / artifacts.MAP_PATH, inspected / "producer-map.json",
                     self.state / "evidence" / producer_id / "reports" / artifacts.MAP_PATH):
            write(path, raw_map)
        reports.append({"source": artifacts.MAP_PATH, "retained": "reports/" + artifacts.MAP_PATH,
                        "classification": "changed-since-admission", **binding(raw_map)})
        build_path, inspect_path = self.state / "build.json", self.state / "inspection.json"
        build = receipt(self.state, self.root, self.context, producer_id, "gradle", "ui-build", artifacts.BUILD_ARGUMENTS)
        build["reports"] = reports
        argv = ["python3", "scripts/verify-android-acceptance-artifacts.py", "--build-receipt", str(build_path),
                "--build-purpose", "ui-build"]
        inspected_receipt = receipt(self.state, self.root, self.context, inspector_id, "command", "ui-inspect", argv)
        for path, value in ((build_path, build), (inspect_path, inspected_receipt),
                            (Path(build["evidenceDirectory"]) / "receipt.json", build),
                            (Path(inspected_receipt["evidenceDirectory"]) / "receipt.json", inspected_receipt)):
            write(path, runner.json_bytes(value))
        analyzer = {"path": str(self.base / "model-sdk/apkanalyzer"), **binding(b"model analyzer")}
        result = {"status": "ARTIFACTS_VERIFIED_PENDING_OUTER_RECEIPT", "source": SOURCE, "sourceAfter": SOURCE,
                  "errors": [], "runtime": "NOT_RUN", "producerId": producer_id, "producerPurpose": "ui-build",
                  "producerMapSha256": hashlib.sha256(raw_map).hexdigest(),
                  "apks": {role: components[role]["apk"] for role in ("app", "test")},
                  "manifestIdentities": manifests.matching_manifest_identities(app_xml, test_xml, app_xml, test_xml),
                  "apkanalyzer": analyzer, "commands": [
                      {"argv": [analyzer["path"], "manifest", "print", str(self.root / components[role]["apk"]["path"])],
                       "exitCode": 0, "timeoutSeconds": 60, "startedUtc": "model-start", "endedUtc": "model-end"}
                      for role in ("app", "test")]}
        write(inspected / "result.json", runner.json_bytes(result))
        write(Path(inspected_receipt["evidenceDirectory"]) / "product.stdout.log",
              (str(inspected / "result.json") + "\n").encode())
        return SimpleNamespace(build_receipt=build_path, build_purpose="ui-build", inspection_receipt=inspect_path,
                               inspection_purpose="ui-inspect"), build, inspected_receipt

    def test_intake_composes_existing_validators_without_execution(self):
        args, _, _ = self.make_intake()
        with mock.patch.object(core.subprocess, "Popen", side_effect=AssertionError("No child allowed")):
            result = core.intake(runner, checker, artifacts, manifests, self.state, self.context, self.root, args)
        self.assertEqual(set(result["apks"]), {"app", "test"})
        self.assertEqual(result["bindings"]["producerReceipt"], binding(args.build_receipt.read_bytes()))
        self.assertNotIn("runtimeAcceptance", result)

    def test_intake_refuses_changed_apk_and_wrong_inspector_result(self):
        args, build, _ = self.make_intake()
        bad = self.root / artifacts.MODULE_BUILD / "outputs/app/one.apk"
        original = bad.read_bytes()
        bad.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Artifact content differs"):
            core.intake(runner, checker, artifacts, manifests, self.state, self.context, self.root, args)
        bad.write_bytes(original)
        path = self.state / "evidence/android-acceptance-artifacts/result.json"
        result = json.loads(path.read_bytes())
        result["producerId"] = "0" * 32
        path.write_bytes(runner.json_bytes(result))
        with self.assertRaisesRegex(core.Rejected, "Inspection result"):
            core.intake(runner, checker, artifacts, manifests, self.state, self.context, self.root, args)
        self.assertEqual(build["reports"][0]["classification"], "changed-since-admission")

    def test_canonical_receipt_refuses_pending_copy_and_path_swaps(self):
        args, _, inspection = self.make_intake()
        core.canonical_receipt(runner, artifacts, self.state, args.inspection_receipt)
        args.inspection_receipt.write_bytes(json.dumps(inspection).encode())
        with self.assertRaisesRegex(core.Rejected, "canonical original"):
            core.canonical_receipt(runner, artifacts, self.state, args.inspection_receipt)
        args.inspection_receipt.write_bytes(runner.json_bytes(inspection))
        Path(inspection["evidenceDirectory"], "receipt.json").unlink()
        with self.assertRaises(FileNotFoundError):
            core.canonical_receipt(runner, artifacts, self.state, args.inspection_receipt)
        outside = self.base / "other.json"
        write(outside, runner.json_bytes(inspection))
        with self.assertRaisesRegex(core.Rejected, "outside"):
            core.canonical_receipt(runner, artifacts, self.state, outside)

    def test_inspector_receipt_requires_finalization_and_same_source_state(self):
        args, _, good = self.make_intake()
        core.admit_inspection_receipt(checker, good, self.context, self.root, args.build_receipt, "ui-build", "ui-inspect")
        isolated = copy.deepcopy(good)
        isolated["requestedArgv"] = [good["requestedArgv"][0], "-I", "-B", "-S", *good["requestedArgv"][1:]]
        isolated["executedArgv"] = isolated["requestedArgv"]
        core.admit_inspection_receipt(checker, isolated, self.context, self.root, args.build_receipt, "ui-build", "ui-inspect")
        for key, value in (("productExitCode", None), ("stopExitCode", 1), ("ownedSurvivors", [{"pid": 1}]),
                           ("errors", ["unresolved"]), ("jobId", "0" * 32), ("host", "linux-x64"),
                           ("gradleHome", "/other-home"), ("kind", "gradle"), ("executedArgv", ["different"]),
                           ("sourceBefore", {**SOURCE, "tree": "9" * 40})):
            with self.subTest(key=key):
                changed = copy.deepcopy(good)
                changed[key] = value
                with self.assertRaises(ValueError):
                    core.admit_inspection_receipt(checker, changed, self.context, self.root, args.build_receipt,
                                                  "ui-build", "ui-inspect")
        changed = copy.deepcopy(good)
        changed["requestedArgv"] += ["--trusted"]
        with self.assertRaises(core.Rejected):
            core.admit_inspection_receipt(checker, changed, self.context, self.root, args.build_receipt, "ui-build", "ui-inspect")

    def test_outer_owner_requires_actual_context_and_active_matching_domain(self):
        processes = core.load_tool("audit_processes.py")
        identifier = "7" * 32
        domain = {"id": identifier, "job": self.context["id"], "state": str(self.state),
                  "home": self.context["gradleHome"]}
        environment = {processes.CHAIN_ENV: identifier, processes.DOMAINS_ENV: json.dumps([domain]),
                       processes.JOB_ENV: self.context["id"], processes.STATE_ENV: str(self.state),
                       "GRADLE_USER_HOME": self.context["gradleHome"]}
        owner = receipt(self.state, self.root, self.context, identifier, "command", "model", ["NEVER_EXECUTE"])
        owner["ancestorInvocationIds"] = []
        write(self.state / "evidence" / identifier / "start.json", runner.json_bytes(owner))
        with mock.patch.object(runner, "context_at", return_value=(self.state, self.context)), \
                mock.patch.object(runner, "source_snapshot", return_value=SOURCE):
            self.assertEqual(core.admit_outer(runner, processes, self.state, self.context, self.root, environment), identifier)
            with self.assertRaises(core.Rejected):
                core.admit_outer(runner, processes, self.state, self.context, self.root,
                                 {**environment, "GRADLE_USER_HOME": "/other-home"})
            write(self.state / "evidence" / identifier / "receipt.json", b"{}\n")
            with self.assertRaisesRegex(core.Rejected, "active immutable"):
                core.admit_outer(runner, processes, self.state, self.context, self.root, environment)

    def test_case_deadlines_and_exact_four_instrumentation_arguments(self):
        guest = SimpleNamespace(adb=mock.Mock(return_value="model"))
        for case, seconds in (("317", 180), ("324", 240)):
            core.instrument(guest, case, TOKEN, SOURCE)
            args = guest.adb.call_args.args[1]
            self.assertEqual(guest.adb.call_args.kwargs, {"seconds": seconds, "limit": core.STREAM_LIMIT})
            self.assertEqual(args.count("-e"), 4)
            self.assertEqual(args[-1], core.PACKAGE + ".test/" + core.PACKAGE + ".runtime." + core.CASES[case][0])
            self.assertEqual(args[3:5], ["--user", "0"])
        for case, token in (("372", TOKEN), ("317", "../bad")):
            with self.assertRaises(core.Rejected):
                core.instrument(guest, case, token, SOURCE)

    def test_empty_server_and_exclusive_fixture_do_not_adopt_preexisting_state(self):
        core.require_empty_server(b"List of devices attached\n\n")
        for raw in (b"", b"List of devices attached\nemulator-5554\tdevice\n", b"unauthorized\n"):
            with self.assertRaises(core.Rejected):
                core.require_empty_server(raw)
        directory = core.new_fixture(runner, self.state)
        marker = (directory / "directory-identity.json").read_bytes()
        with self.assertRaises(FileExistsError):
            core.new_fixture(runner, self.state)
        self.assertEqual((directory / "directory-identity.json").read_bytes(), marker)

    def model_command(self, stdout=(b"out", b""), stderr=(b"err", b""), status=0, limit=100):
        pipes = {101: ModelPipe(101, stdout), 102: ModelPipe(102, stderr)}
        child = SimpleNamespace(pid=77, stdout=pipes[101], stderr=pipes[102], poll=lambda: status)
        ticks = iter(index / 100 for index in range(10000))
        command = core.Commands(runner, self.evidence, self.root, {"MODEL_ONLY": "1"})
        with mock.patch.object(core.subprocess, "Popen", return_value=child), \
                mock.patch.object(core.selectors, "DefaultSelector", ModelSelector), \
                mock.patch.object(core.os, "set_blocking"), \
                mock.patch.object(core.os, "read", side_effect=lambda fd, _count: pipes[fd].chunks.pop(0)), \
                mock.patch.object(core.time, "monotonic", side_effect=lambda: next(ticks)):
            try:
                record = command.run("model", ["NEVER_EXECUTE"], seconds=1, limit=limit)
            except BaseException:
                self.assertTrue(all(pipe.closed for pipe in pipes.values()))
                raise
        return command, record

    def test_command_keeps_original_bytes_status_and_actual_eofs(self):
        commands, record = self.model_command()
        core.completed(record)
        self.assertEqual(core.command_bytes(record, 100), b"out")
        self.assertEqual(Path(record["stderr"]).read_bytes(), b"err")
        self.assertEqual(commands.settlement(), [{"pid": 77, "exitCode": 0}])

    def test_exit_zero_without_eof_is_failure_not_complete(self):
        with self.assertRaisesRegex(core.Rejected, "deadline"):
            self.model_command(stdout=(b"prefix",))
        record = json.loads((self.evidence / "0001-model.json").read_bytes())
        self.assertEqual(record["exitCode"], 0)
        self.assertFalse(record["stdoutEof"])
        self.assertEqual(Path(record["stdout"]).read_bytes(), b"prefix")
        with self.assertRaises(core.Rejected):
            core.completed(record)

    def test_bound_violation_keeps_actual_prefix_and_cannot_pass(self):
        with self.assertRaisesRegex(core.Rejected, "output bound"):
            self.model_command(stdout=(b"oversized", b""), limit=2)
        record = json.loads((self.evidence / "0001-model.json").read_bytes())
        self.assertEqual(Path(record["stdout"]).read_bytes(), b"oversized")
        self.assertEqual(record["retention"], "PARTIAL")

    def test_spawn_failure_is_retained_and_outputs_are_never_overwritten(self):
        commands = core.Commands(runner, self.evidence, self.root, {})
        with mock.patch.object(core.subprocess, "Popen", side_effect=FileNotFoundError("modeled missing tool")):
            with self.assertRaises(FileNotFoundError):
                commands.run("missing", ["NEVER_EXECUTE"])
        record = json.loads((self.evidence / "0001-missing.json").read_bytes())
        self.assertIsNone(record["exitCode"])
        self.assertIn("FileNotFoundError", record["errors"][0])
        owned = self.evidence / "owner-original"
        write(owned, b"keep")
        with mock.patch.object(core.subprocess, "Popen", side_effect=AssertionError("Must not launch")):
            with self.assertRaises(FileExistsError):
                commands.run("collision", ["NEVER_EXECUTE"], destination=owned)
            with self.assertRaises(core.Rejected):
                commands.run("escape", ["NEVER_EXECUTE"], destination=self.evidence / ".." / "elsewhere")
        self.assertEqual(owned.read_bytes(), b"keep")

    def test_selector_creation_failure_retains_attempt_without_launching(self):
        commands = core.Commands(runner, self.evidence, self.root, {})
        with mock.patch.object(core.selectors, "DefaultSelector", side_effect=OSError("modeled selector failure")), \
                mock.patch.object(core.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(OSError, "selector failure"):
                commands.run("selector", ["NEVER_EXECUTE"])
        spawn.assert_not_called()
        record = json.loads((self.evidence / "0001-selector.json").read_bytes())
        self.assertIsNone(record["exitCode"])
        self.assertEqual(record["retention"], "PARTIAL")
        self.assertIn("OSError", record["errors"][0])

    def test_first_pipe_setup_failure_still_closes_both_owned_pipes(self):
        pipes = (ModelPipe(101, []), ModelPipe(102, []))
        child = SimpleNamespace(pid=77, stdout=pipes[0], stderr=pipes[1], poll=lambda: 7)
        commands = core.Commands(runner, self.evidence, self.root, {})
        with mock.patch.object(core.subprocess, "Popen", return_value=child), \
                mock.patch.object(core.selectors, "DefaultSelector", ModelSelector), \
                mock.patch.object(core.os, "set_blocking", side_effect=OSError("modeled pipe setup failure")):
            with self.assertRaisesRegex(OSError, "pipe setup failure"):
                commands.run("pipe", ["NEVER_EXECUTE"])
        self.assertTrue(all(pipe.closed for pipe in pipes))
        self.assertEqual(commands.children, [child])
        record = json.loads((self.evidence / "0001-pipe.json").read_bytes())
        self.assertEqual(record["exitCode"], 7)
        with self.assertRaises(core.Rejected):
            core.completed(record)

    def test_private_adb_selects_only_its_server_and_quotes_remote_tokens(self):
        commands = SimpleNamespace(run=mock.Mock(return_value={}))
        server = SimpleNamespace(poll=lambda: None)
        guest = core.PrivateAdb(commands, self.base / "model-sdk", 43210, "emulator-5580", server, object(), "317", TOKEN)
        guest.run_as("ui-stat", ["stat", "-c", core.STAT_FORMAT, "no_backup/ui-317-" + TOKEN])
        argv = commands.run.call_args.args[1]
        self.assertEqual(argv[1:5], ["-P", "43210", "-s", "emulator-5580"])
        self.assertEqual(shlex.split(argv[-1]), ["run-as", core.PACKAGE, "/system/bin/toybox", "stat", "-c",
                                                core.STAT_FORMAT, "no_backup/ui-317-" + TOKEN])
        for arguments in (["cat", "no_backup/owner-data"], ["cat", guest.remote + "/../owner-data"],
                          ["ls", "-1a", "no_backup"], ["stat", "-L", guest.remote]):
            with self.assertRaises(core.Rejected):
                guest.run_as("outside-tree", arguments)
        guest.server = SimpleNamespace(poll=lambda: 0)
        with self.assertRaises(core.Rejected):
            guest.adb("no-adoption", ["devices"])
        self.assertEqual(commands.run.call_count, 1)

    def test_package_path_and_uid_parsers_reject_ambiguous_installs(self):
        self.assertEqual(core.package_paths(b"package:/data/app/~~a/base/base.apk\n"),
                         "/data/app/~~a/base/base.apk")
        for raw in (b"", b"package:/data/app/x/base.apk\npackage:/data/app/x/split.apk\n",
                    b"package:/data/app/../outside/base.apk\n"):
            with self.assertRaises(core.Rejected):
                core.package_paths(raw)
        with self.assertRaises(core.Rejected):
            core.package_uids(b"package:a uid:10001\npackage:a uid:10002\n")

    def installed_model(self, bundle, tamper=False):
        count = [0]
        calls = []
        def adb(label, arguments, seconds=40, limit=core.STREAM_LIMIT, destination=None):
            calls.append((label, arguments, seconds, limit))
            count[0] += 1
            if label == "installed-user":
                raw = b"0\n"
            elif label in ("installed-packages", "installed-packages-after"):
                raw = (f"package:{core.PACKAGE} uid:10001\npackage:{core.PACKAGE}.test uid:10002\n").encode()
            elif label.endswith("-installed-package"):
                raw = b"versionCode=1 minSdk=24 targetSdk=37\n  User 0: installed=true hidden=false\n"
            elif "-installed-path" in label:
                role = label.split("-")[0]
                raw = ("package:/data/app/~~model/" + role + "/base.apk\n").encode()
            else:
                role = label.split("-")[0]
                raw = b"different installed bytes" if tamper else bundle["apks"][role].read_bytes()
                self.assertEqual(arguments[0], "exec-out")
                self.assertEqual(shlex.split(arguments[1])[0], "cat")
                self.assertEqual((seconds, limit), (120, core.APK_LIMIT))
            return observation(self.evidence, count[0], raw, destination=destination)
        return SimpleNamespace(adb=adb), calls

    def test_installed_pair_requires_complete_readback_of_both_apks(self):
        args, _, _ = self.make_intake()
        bundle = core.intake(runner, checker, artifacts, manifests, self.state, self.context, self.root, args)
        guest, calls = self.installed_model(bundle)
        result = core.installed_pair(guest, artifacts, self.root, bundle, self.evidence)
        for role, package in zip(("app", "test"), core.PACKAGES):
            self.assertEqual(Path(result[package]["retained"]).read_bytes(), bundle["apks"][role].read_bytes())
        self.assertEqual(sum(label.endswith("-installed-bytes") for label, *_ in calls), 2)
        self.assertEqual({value["user"] for value in result.values()}, {0})

    def test_installed_hash_mismatch_preserves_readback_and_stops_before_next_apk(self):
        args, _, _ = self.make_intake()
        bundle = core.intake(runner, checker, artifacts, manifests, self.state, self.context, self.root, args)
        guest, calls = self.installed_model(bundle, tamper=True)
        with self.assertRaisesRegex(core.Rejected, "Installed APK differs"):
            core.installed_pair(guest, artifacts, self.root, bundle, self.evidence)
        self.assertEqual((self.evidence / "app-installed.apk").read_bytes(), b"different installed bytes")
        self.assertFalse(any(label == "test-installed-bytes" for label, *_ in calls))

    def collection_fixture(self, case="324"):
        remote = self.base / "model-guest"
        root = remote / ("no_backup/ui-" + case + "-" + TOKEN)
        root.mkdir(mode=0o700, parents=True)
        if case == "324":
            for directory in ("fixture/no-backup/test-diagnostics", "fixture/cache"):
                (root / directory).mkdir(mode=0o700, parents=True, exist_ok=True)
            write(root / "fixture/no-backup/test-diagnostics/.diagnostic-events.jsonl.lock", b"")
        write(root / "result.json", b"{}\n")
        return root, ModelGuest(remote, self.evidence)

    def collect(self, guest, phase="after-retirement", case="324", bounds=verifier):
        return core.Collector(runner, guest, bounds, self.evidence, case, TOKEN, 10001, phase).collect()

    def test_collection_preserves_hidden_zero_file_and_empty_directories(self):
        _, guest = self.collection_fixture()
        result = self.collect(guest)
        self.assertEqual(result["status"], "RETAINED_STABLE_GRAPH")
        self.assertEqual(result["artRetirement"], "NOT_ESTABLISHED_BY_COLLECTOR")
        lock = Path(result["retainedRoot"]) / "fixture/no-backup/test-diagnostics/.diagnostic-events.jsonl.lock"
        self.assertEqual(lock.read_bytes(), b"")
        self.assertIn("fixture/cache", result["directories"])
        self.assertTrue(all(row["readOutcome"] == "COMPLETE" for row in result["files"]))

    def test_collection_keeps_unknown_safe_entries_instead_of_filtering(self):
        root, guest = self.collection_fixture()
        write(root / "unexpected.txt", b"unexpected original")
        (root / "unknown-empty").mkdir()
        result = self.collect(guest)
        self.assertEqual((Path(result["retainedRoot"]) / "unexpected.txt").read_bytes(), b"unexpected original")
        self.assertIn("unknown-empty", result["directories"])
        self.assertNotIn("contentStatus", result)

    def test_collection_rejects_symlinks_without_reading_their_targets(self):
        root, guest = self.collection_fixture()
        outside = self.base / "unrelated"
        write(outside, b"do not read")
        (root / "linked.txt").symlink_to(outside)
        with self.assertRaisesRegex(core.Rejected, "link/special"):
            self.collect(guest)
        self.assertFalse(any(row[1][0] == "cat" for row in guest.calls))
        self.assertEqual(outside.read_bytes(), b"do not read")

    def test_collection_rehash_refuses_linked_local_original(self):
        _, guest = self.collection_fixture(case="317")
        outside = self.base / "unrelated-local"
        write(outside, b"do not read")
        original = guest.run_as
        def run_as(*args, **kwargs):
            record = original(*args, **kwargs)
            destination = kwargs.get("destination")
            if destination is not None:
                destination.unlink()
                destination.symlink_to(outside)
            return record
        guest.run_as = run_as
        with self.assertRaisesRegex(core.Rejected, "Linked original"):
            self.collect(guest, case="317")
        result = json.loads((self.evidence / "after-retirement/collection.json").read_bytes())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["files"][0]["readOutcome"], "INCOMPLETE")
        self.assertEqual(outside.read_bytes(), b"do not read")

    def test_collection_refuses_hardlinks_unsafe_names_and_foreign_uids(self):
        for raw in (b"1|2|81a4|2|10001|1|1|1\n", b"1|2|81a4|1|10002|1|1|1\n",
                    b"1|2|a1ff|1|10001|1|1|1\n"):
            with self.assertRaises(core.Rejected):
                core.guest_stat(raw, 10001)
        for raw in (b".\n..\na\na\n", b".\n..\nspace name\n", b".\n..\n../escape\n", b".\n..\na"):
            with self.assertRaises(core.Rejected):
                core.directory_names(raw)

    def test_short_read_is_retained_as_incomplete_not_later_success(self):
        _, guest = self.collection_fixture(case="317")
        guest.short = True
        with self.assertRaisesRegex(core.Rejected, "Short/changed"):
            self.collect(guest, case="317")
        result = json.loads((self.evidence / "after-retirement/collection.json").read_bytes())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["files"][0]["readOutcome"], "INCOMPLETE")
        self.assertEqual((Path(result["retainedRoot"]) / "result.json").read_bytes(), b"{}")

    def test_changed_membership_remains_failed_with_original_file(self):
        root, guest = self.collection_fixture(case="317")
        guest.after_cat = lambda: write(root / "late.txt", b"late")
        with self.assertRaisesRegex(core.Rejected, "changed during capture"):
            self.collect(guest, case="317")
        result = json.loads((self.evidence / "after-retirement/collection.json").read_bytes())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual((Path(result["retainedRoot"]) / "result.json").read_bytes(), b"{}\n")

    def test_missing_tree_and_exceeded_budget_are_not_empty_success(self):
        _, guest = self.collection_fixture(case="317")
        guest.reply = lambda _arguments: b""
        with self.assertRaises(ValueError):
            self.collect(guest, case="317")
        result = json.loads((self.evidence / "after-retirement/collection.json").read_bytes())
        self.assertEqual(result["status"], "INCOMPLETE")
        guest.reply = None
        bounds = SimpleNamespace(**{key: getattr(verifier, key) for key in
                                  ("DEPTH_LIMIT", "DIRECTORY_LIMIT", "FILE_LIMIT", "PNG_LIMIT", "PARCEL_LIMIT",
                                   "TEXT_LIMIT", "TOTAL_LIMITS")})
        bounds.TEXT_LIMIT = 1
        with self.assertRaisesRegex(core.Rejected, "byte budget"):
            self.collect(guest, phase="before-retirement-partial", case="317", bounds=bounds)

    def test_pre_and_post_retirement_snapshots_remain_distinct(self):
        _, guest = self.collection_fixture()
        before = self.collect(guest, phase="before-retirement-partial")
        after = self.collect(guest)
        self.assertNotEqual(before["retainedRoot"], after["retainedRoot"])
        self.assertEqual(before["phase"], "before-retirement-partial")
        with self.assertRaises(FileExistsError):
            self.collect(guest)

    def test_finally_attempts_every_action_after_failure_interruption_and_write_failure(self):
        called = []
        def action(label, error=None):
            def run():
                called.append(label)
                if error is not None:
                    raise error
                return {"observed": label}
            return run
        actions = [("collect", action("collect", OSError("model read failed"))),
                   ("art", action("art", KeyboardInterrupt())), ("guest", action("guest")), ("adb", action("adb"))]
        rows = core.attempt_all(runner, self.evidence, actions)
        self.assertEqual(called, ["collect", "art", "guest", "adb"])
        self.assertEqual([row["status"] for row in rows], ["FAILED", "FAILED", "RETURNED", "RETURNED"])
        called.clear()
        failing_writer = SimpleNamespace(utc=runner.utc, write_new_json=mock.Mock(side_effect=OSError("model full disk")))
        rows = core.attempt_all(failing_writer, self.evidence, actions)
        self.assertEqual(len(called), 4)
        self.assertTrue(all(row["status"] == "FAILED" for row in rows))

    def test_exact_handle_waits_both_run_and_original_nonzero_is_preserved(self):
        emulator = SimpleNamespace(wait=mock.Mock(return_value=7))
        server = SimpleNamespace(wait=mock.Mock(return_value=0))
        result = core.stop_handles(SimpleNamespace(emulator=emulator, server=server))
        self.assertEqual(result["emulator"]["exitCode"], 7)
        self.assertIn("error", result["emulator"])
        emulator.wait.assert_called_once_with(timeout=20)
        server.wait.assert_called_once_with(timeout=10)
        emulator.wait.side_effect = subprocess.TimeoutExpired("model emulator", 20)
        result = core.stop_handles(SimpleNamespace(emulator=emulator, server=server))
        self.assertIsNone(result["emulator"]["exitCode"])
        self.assertEqual(result["adb"]["exitCode"], 0)

    def test_verifier_result_is_retained_verbatim_without_acceptance_promotion(self):
        expected = {"contentStatus": "CONSISTENT", "provenance": "UNPROVEN", "runtimeAcceptance": "NOT_ACCEPTED",
                    "visualReview": "NOT_PERFORMED", "mutationReview": "NOT_PERFORMED"}
        modeled_verifier = SimpleNamespace(verify=mock.Mock(return_value=copy.deepcopy(expected)))
        result = core.retain_content_result(runner, modeled_verifier, self.evidence, self.base / "model-ui",
                                           self.base / "model-stdout", "317", TOKEN, SOURCE)
        self.assertEqual(result, expected)
        self.assertEqual(json.loads((self.evidence / "content-result.json").read_bytes()), expected)
        with self.assertRaises(FileExistsError):
            core.retain_content_result(runner, modeled_verifier, self.evidence, self.base / "model-ui",
                                       self.base / "model-stdout", "317", TOKEN, SOURCE)


if __name__ == "__main__":
    unittest.main()
