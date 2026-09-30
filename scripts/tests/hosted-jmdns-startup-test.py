#!/usr/bin/env python3
"""Offline direct-Java controller controls, never Java/native qualification.

All execution, upload, account and private-file observations below are synthetic.
The audit fence forbids processes, networking, native loading and filesystem
writes. No old test suite, private evidence, key, Gradle or Java is executed.
"""
import argparse
import ast
import contextlib
import copy
import ctypes
import errno
import grp
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import pwd
import re
import select
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch
import uuid
import xml.etree.ElementTree as ET


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "scripts/run-hosted-jmdns-startup.py"
ACCOUNT = {"uid": 501, "euid": 501, "gid": 20, "egid": 20, "groups": [20, 80]}
MODES = ("control", "failed_recovery", "shared_close", "close_wins", "recovery_wins",
         "responder_close", "callback_executor", "cleanup_retry")
NS = 1_000_000_000


def offline(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "os.kill", "os.killpg",
        "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv", "os.mkdir", "os.remove", "os.rmdir",
        "os.rename", "os.link", "os.symlink", "os.chmod", "os.chown", "os.setuid", "os.seteuid", "os.setgid",
        "os.setegid", "os.setgroups", "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    } or (event == "open" and type(args[2]) is int and args[2] &
          (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
        raise AssertionError("offline controller control attempted an external operation: " + event)


sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("startup_controller_controls", ROOT / SCRIPT)
S = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = S
spec.loader.exec_module(S)
M = S.maintenance


def request_fixture():
    request = {"source_sha": "a" * 40, "source_tree": "b" * 40}
    ref = "refs/heads/work/release-foundation-dependency-context-startup-controls"
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_EVENT_NAME": "workflow_dispatch",
           "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_JOB": "jmdns_startup", "GITHUB_ACTOR": "Apdelrahman1911",
           "GITHUB_ACTOR_ID": "104788132", "GITHUB_TRIGGERING_ACTOR": "Apdelrahman1911", "GITHUB_REF": ref,
           "GITHUB_SHA": request["source_sha"], "GITHUB_WORKFLOW_SHA": request["source_sha"],
           "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/" + S.WORKFLOW + "@" + ref,
           "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
    return request, env, S.request_data(request, env, request)


def seal_fixture(failed=False):
    request, env, github = request_fixture()
    allocation = {"schema": 2, "clockDomain": S.bridge.CLOCK_DOMAIN, "scope": S.SCOPE,
                  "source": request["source_sha"], "sourceTree": request["source_tree"], "runId": "123", "runAttempt": "1",
                  "startedMonotonicNs": 100 * NS, "startedEpochNs": (S.bridge.POLICY_EXPIRES - 20000) * NS}
    group, key = ("failed-encrypted", "FAILED_SHA256") if failed else ("encrypted", "SUCCESS_SHA256")
    manifest = S.encoded({"schema": 1, "synthetic": True})
    source_roster = {"fixture.java": {"sha256": "a" * 64}}
    prepared_raw = S.encoded({"sourceRoster": source_roster})
    files = {group + "/" + name: {"sha256": "d" * 64, "bytes": 7} for name in M.ENCRYPTED_FILES}
    seal = {"schema": 1, "scope": S.FAILED_SCOPE if failed else S.SCOPE, "request": request, "github": github,
            "allocation": allocation, "operationIdentity": [11, 22], "account": ACCOUNT, "policySha256": M.POLICY_SHA256,
            "startupInputsSha256": S.digest(prepared_raw),
            "result": "CLOSED_FAILED_PRODUCT" if failed else "DIRECT_JAVA_MODES_PASSED", "files": files,
            "exportManifestSha256": S.digest(manifest), "producerReturn":
            "FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN" if failed else "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN",
            "productExitCode": 1 if failed else 0, "purpose": S.PURPOSES[4] if failed else S.PURPOSES[-1],
            "receiptSha256": "e" * 64, "stepStartedRawNs": 110 * NS, "commandReturnedRawNs": 200 * NS,
            "exportReturnedRawNs": 250 * NS, "uploadEndRawNs": (250 + S.UPLOAD_SECONDS) * NS}
    seal_hash = S.digest(S.encoded(seal))
    output = (("failedProductSha256" if failed else "successSha256") + "=" + seal_hash + "\n").encode("ascii")
    step = {"schema": 1, "scope": S.SCOPE, "sealSha256": seal_hash, "intendedExitCode": seal["productExitCode"],
            "returnedRawNs": 255 * NS, "commandFile": {"stat": [1, 2, 33152, 501, 20, 1, len(output), 3, 4],
                                                       "sha256": S.digest(output), "closed": True}}
    env.update({S.PREFIX + "OUTCOME": "failure" if failed else "success", S.PREFIX + key: seal_hash,
                S.PREFIX + "UPLOAD_OUTCOME": "success", S.PREFIX + "ARTIFACT_ID": "567",
                S.PREFIX + "ARTIFACT_DIGEST": "8" * 64})
    return types.SimpleNamespace(request=request, env=env, github=github, allocation=allocation, seal=seal,
                                 seal_hash=seal_hash, step=step, manifest=manifest, group=group,
                                 source_roster=source_roster, prepared_raw=prepared_raw)


class ControllerControls(unittest.TestCase):
    def test_request_binds_original_event_workflow_account_source_and_attempt(self):
        request, env, github = request_fixture()
        self.assertEqual((github["source"], github["sourceTree"], github["runAttempt"]), ("a" * 40, "b" * 40, "1"))
        changes = {"GITHUB_EVENT_NAME": "push", "RUNNER_ENVIRONMENT": "self-hosted", "GITHUB_JOB": "generate",
                   "GITHUB_ACTOR": "other", "GITHUB_ACTOR_ID": "1", "GITHUB_TRIGGERING_ACTOR": "other",
                   "GITHUB_REF": "refs/heads/main", "GITHUB_WORKFLOW_REF": "other", "GITHUB_WORKFLOW_SHA": "c" * 40,
                   "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "0", "GITHUB_RUN_ATTEMPT": "01"}
        for name, value in changes.items():
            with self.subTest(name=name), self.assertRaises(S.StartupError):
                S.request_data(request, {**env, name: value}, request)
        for changed in ({**request, "candidate_sha": "a" * 40}, {**request, "source_sha": "A" * 40}, {}, None):
            with self.subTest(request=changed), self.assertRaises(S.StartupError):
                S.request_data(changed, env, changed)
        for event in ({**request, "source_tree": "c" * 40}, {}, None):
            with self.assertRaises(S.StartupError):
                S.request_data(request, env, event)

    def test_original_request_reads_actual_event_not_environment_copy_only(self):
        request, env, _ = request_fixture()
        env.update({S.PREFIX + "REQUEST": S.encoded(request).decode(), "GITHUB_EVENT_PATH": "/controlled/event.json"})
        with patch.object(S.bridge, "physical", side_effect=Path), patch.object(S, "read_file") as read:
            read.return_value = (S.encoded({"inputs": request}), {})
            self.assertEqual(S.original_request(env)[0], request)
            read.return_value = (S.encoded({"inputs": {**request, "source_tree": "c" * 40}}), {})
            with self.assertRaises(S.StartupError):
                S.original_request(env)

    def test_fixed_commands_use_all_sources_exact_runtime_classpath_and_limits(self):
        runtime, java = Path("/controlled/runtime"), Path("/admitted/jdk17/bin")
        sources = [S.VENDOR + "/src/main/java/Fixture%02d.java" % index for index in range(60)]
        commands = S.fixed_commands(java, runtime, sources)
        self.assertEqual((S.MODES, len(commands), S.PURPOSES), (MODES, 12, S.bridge.STARTUP_PURPOSES))
        self.assertEqual(S.COMMAND_SECONDS, (300, 90, 90, 90, *(45 for _ in MODES)))
        self.assertEqual((S.JOB_SECONDS, S.STEP_SECONDS, S.STOP_SECONDS, S.UPLOAD_SECONDS), (12600, 9900, 120, 1320))
        self.assertEqual(commands[0], [M.PYTHON, "-I", "-B", "-S", str(ROOT / SCRIPT), "_prerequisites"])
        self.assertEqual(commands[1], ["/usr/bin/curl", "--disable", "--fail", "--silent", "--show-error", "--proto", "=https",
            "--tlsv1.2", "--connect-timeout", "15", "--max-time", "60", "--max-filesize", "1048576", "--output",
            str(runtime / "slf4j-api-2.0.7.jar"), S.DEPENDENCY_URL])
        compiler = [str(java / "javac"), "-J-Xmx256m", "-J-XX:ActiveProcessorCount=2"]
        self.assertEqual(commands[2], [*compiler, "--release", "8", "-encoding", "UTF-8", "-classpath",
            str(runtime / "slf4j-api-2.0.7.jar"), "-d", str(runtime / "vendor"), *(str(ROOT / name) for name in sources)])
        self.assertEqual(commands[3], [*compiler, "--release", "17", "-encoding", "UTF-8", "-classpath",
            os.pathsep.join(map(str, (runtime / "vendor", runtime / "slf4j-api-2.0.7.jar"))), "-d",
            str(runtime / "fixture"), str(ROOT / S.FIXTURE)])
        arguments = ["-Xms16m", "-Xmx128m", "-XX:MaxMetaspaceSize=128m", "-XX:ActiveProcessorCount=2",
                     "-XX:+UseSerialGC", "-Dorg.slf4j.simpleLogger.defaultLogLevel=off"]
        classpath = os.pathsep.join(str(runtime / name) for name in ("fixture", "vendor", "resources", "slf4j-api-2.0.7.jar"))
        self.assertEqual(commands[4:], [[str(java / "java"), *arguments, "-cp", classpath, S.FIXTURE_CLASS, mode] for mode in MODES])
        self.assertEqual(S.RESOURCE, "dev/p2pkit/transport/lan/internal/jmdns/version.properties")
        for changed in (sources[:-1], sources + sources[:1], list(reversed(sources)), sources[:59] + sources[:1]):
            with self.assertRaises(S.StartupError):
                S.fixed_commands(java, runtime, changed)
        for changed in (ROOT, ROOT / "output", Path("relative"), Path("/controlled/../output")):
            with self.assertRaises(S.StartupError):
                S.fixed_commands(java, changed, sources)
        for index in range(12):
            self.assertEqual(S.command_reserve(index), sum(S.COMMAND_SECONDS[index:]) +
                             (12 - index) * (120 + M.NATIVE_HEADROOM) + M.FINAL_RESERVE)
        for index in (-1, 12, True, "0"):
            with self.assertRaises(S.StartupError):
                S.command_reserve(index)

    def test_reviewed_fixture_and_exact_slf4j_pin_are_not_substituted(self):
        self.assertEqual(S.digest((ROOT / S.FIXTURE).read_bytes()), S.FIXTURE_SHA256)
        self.assertEqual(S.DEPENDENCY_SHA256, "5d6298b93a1905c32cda6478808ac14c2d4a47e91535e53c41f7feeb85d946f4")
        raw = (ROOT / "gradle/verification-metadata.xml").read_bytes()
        S.validate_dependency_pin(raw)
        pin = S.DEPENDENCY_SHA256.encode()
        for changed in (raw.replace(pin, b"0" * 64), raw.replace(b'slf4j-api-2.0.7.jar', b'slf4j-api-2.0.8.jar')):
            with self.assertRaises(S.StartupError):
                S.validate_dependency_pin(changed)

    def test_each_mode_requires_exact_one_natural_pass_and_combined_output_bound(self):
        for mode in MODES:
            passed = ("PASS mode=" + mode + "\n").encode()
            S.validate_transcript(mode, passed, b"")
            S.validate_transcript(mode, passed, b"x" * (65536 - len(passed)))
            for stdout, stderr in ((b"", b""), (passed, passed), (b"prefix " + passed, b""),
                                   (passed, b"FAIL mode=other"), (passed, b"phase=fixture_rescue_begin"),
                                   (passed, b"x" * (65537 - len(passed))), (passed.decode(), b"")):
                with self.subTest(mode=mode), self.assertRaises(S.StartupError):
                    S.validate_transcript(mode, stdout, stderr)
        with self.assertRaises(S.StartupError):
            S.validate_transcript("unknown", b"PASS mode=unknown\n", b"")

    def test_first_failure_keeps_suffix_not_run_and_never_acquires_success(self):
        self.assertEqual(S.expected_modes(12, failed=False), dict.fromkeys(MODES, "PASS"))
        for count in range(1, 13):
            expected = {mode: "PASS" if index + 5 < count else "FAIL" if index + 5 == count else "NOT_RUN"
                        for index, mode in enumerate(MODES)}
            self.assertEqual(S.expected_modes(count, failed=True), expected)
        for count in (0, 1, 11, 13, True):
            with self.assertRaises(S.StartupError):
                S.expected_modes(count, failed=False)

    def test_source_retention_detects_bytes_before_copy_and_runtime_roster_rejects_drift(self):
        raw, root = b"synthetic source", Path("/controlled/runtime")
        expected = {"sha256": S.digest(raw), "bytes": len(raw)}
        with patch.object(Path, "mkdir"), patch.object(S, "read_file", return_value=(raw, expected)) as read, \
                patch.object(S, "write_new") as write:
            S.retain_inputs(root, {"files": {"fixture.java": expected}})
            write.assert_called_once_with(root / "inputs/fixture.java", raw)
            read.return_value = (b"different", {"sha256": S.digest(b"different"), "bytes": 9})
            write.reset_mock()
            with self.assertRaises(S.StartupError):
                S.retain_inputs(root, {"files": {"fixture.java": expected}})
            write.assert_not_called()
        path = root / "sample.class"
        with patch.object(Path, "iterdir", return_value=iter([path])), \
                patch.object(Path, "lstat", return_value=types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600)), \
                patch.object(Path, "is_symlink", return_value=False), patch.object(S.bridge, "private_directory", return_value=[1, 2]), \
                patch.object(S, "read_file", return_value=(raw, expected)):
            original = S.inventory(root)
        with patch.object(Path, "iterdir", side_effect=lambda: iter([path])), \
                patch.object(Path, "lstat", return_value=types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600)), \
                patch.object(Path, "is_symlink", return_value=False) as link, patch.object(S.bridge, "private_directory", return_value=[1, 2]), \
                patch.object(S, "read_file", return_value=(b"different", {"sha256": "f" * 64, "bytes": 9})):
            self.assertNotEqual(S.inventory(root), original)
            link.return_value = True
            with self.assertRaises(S.StartupError):
                S.inventory(root)

    def test_new_commands_use_real_executor_seam_and_only_known_closed_failures(self):
        source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": S.digest(b"")}
        context, invocation, purpose = {"id": "c" * 32, "source": source}, "d" * 32, "startup-control"
        argv = ["/admitted/java", S.FIXTURE_CLASS, "control"]
        receipt = {"schema": 1, "id": invocation, "jobId": context["id"], "kind": "command", "purpose": purpose,
            "requestedArgv": argv, "sourceBefore": source, "sourceAfter": source, "sourceUnchanged": True,
            "productExitCode": 1, "finalExitCode": 1, "stopExitCode": 0, "ownedSurvivors": [], "errors": [],
            "ownership": {"discoveryErrors": []}}
        runner, returns = types.SimpleNamespace(execute=Mock(return_value=1)), []
        with patch.object(M.uuid, "uuid4", return_value=types.SimpleNamespace(hex=invocation)), \
                patch.object(M, "environment", side_effect=lambda _: contextlib.nullcontext()), \
                patch.object(M, "shared_raw_ns", return_value=200 * NS), \
                patch.object(M, "read_file", return_value=(S.encoded(receipt), {})):
            with self.assertRaises(M.ClosedProductFailure) as failure:
                M.owned_command(runner, Path("/controlled"), context, purpose, argv, 45, command_returns=returns)
        args = runner.execute.call_args.args[0]
        self.assertEqual((args.timeout, args.stop_timeout, args.argv, args.purpose), (45, 120, argv, purpose))
        self.assertEqual((failure.exception.code, len(returns), returns[0]["returnedRawNs"]), (1, 1, 200 * NS))
        for name, value in (("stopExitCode", 1), ("sourceAfter", {}), ("ownedSurvivors", [7]),
                            ("errors", ["timeout"]), ("ownership", {"discoveryErrors": ["unknown"]}),
                            ("cancelRequested", True), ("finalExitCode", 0)):
            with self.subTest(name=name), self.assertRaises(M.UpdateError):
                M.command_return_data(1, {**receipt, name: value}, context, invocation, purpose, argv)
        for code in (-9, 124, 125, 137, True):
            with self.assertRaises(M.UpdateError):
                M.command_return_data(code, receipt, context, invocation, purpose, argv)

    def test_nonzero_launch_record_requires_exact_argv_and_positive_nonboolean_pid(self):
        argv = ["/admitted/java", S.FIXTURE_CLASS, "control"]
        receipt = {"productExitCode": 1, "executedArgv": argv, "productPid": 71}
        S.validate_launch_record(receipt, argv)
        changed = [None, {key: value for key, value in receipt.items() if key != "executedArgv"},
                   {key: value for key, value in receipt.items() if key != "productPid"},
                   {**receipt, "executedArgv": [*argv[:-1], "failed_recovery"]}]
        changed += [{**receipt, "productPid": value} for value in (None, -1, 0, True, False, "71", 71.0)]
        for value in changed:
            with self.subTest(receipt=value), self.assertRaises(S.StartupError):
                S.validate_launch_record(value, argv)

    def test_production_loop_connects_pure_checks_without_catching_generic_failures(self):
        source = (ROOT / SCRIPT).read_text(encoding="utf-8")
        tree = ast.parse(source)
        producer = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "produce")
        calls = [node for node in ast.walk(producer) if isinstance(node, ast.Call)]
        owned = [node for node in calls if ast.unparse(node.func) == "maintenance.owned_command"]
        self.assertEqual(len(owned), 1)
        self.assertEqual(ast.unparse(owned[0].args[-1]), "seconds")
        self.assertEqual([(key.arg, ast.unparse(key.value)) for key in owned[0].keywords], [("command_returns", "returns")])
        handlers = [node for node in ast.walk(producer) if isinstance(node, ast.ExceptHandler)]
        self.assertEqual([ast.unparse(node.type) for node in handlers], ["maintenance.ClosedProductFailure"])
        launch = [node for node in calls if ast.unparse(node.func) == "validate_launch_record"]
        self.assertEqual(sorted([ast.unparse(arg) for arg in node.args] for node in launch),
                         [["original.receipt", "commands[len(returns) - 1]"], ["receipt", "argv"]])
        caught = [node for node in ast.walk(handlers[0]) if isinstance(node, ast.Call) and
                  ast.unparse(node.func) == "validate_launch_record"]
        self.assertEqual(len(caught), 1)
        accepted = next(node for node in handlers[0].body if isinstance(node, ast.Assign) and
                        any(isinstance(target, ast.Name) and target.id == "failed" for target in node.targets))
        self.assertLess(caught[0].lineno, accepted.lineno)
        names = [ast.unparse(node.func) for node in calls]
        for name in ("fixed_commands", "validate_transcript", "expected_modes", "inventory", "tool_snapshot",
                     "source_inputs", "maintenance.clean_source", "maintenance.source_roster", "endpoint.complete"):
            self.assertIn(name, names)
        text = ast.get_source_segment(source, producer)
        for predicate in ("inventory(runtime) == frozen", "tool_snapshot(context) == tools",
                          'digest(data) == DEPENDENCY_SHA256'):
            self.assertIn(predicate, text)

    def validate_seal(self, packet, failed, value=None, now=260 * NS):
        return S.validate_return_data(packet.seal if value is None else value, packet.env, packet.request,
            packet.github, packet.allocation, [11, 22], ACCOUNT, now, failed=failed)

    def test_seal_keeps_exact_identity_scope_outcome_code_hash_roster_and_clock(self):
        for failed in (False, True):
            q = seal_fixture(failed)
            self.assertEqual(self.validate_seal(q, failed), q.seal)
            changes = {"schema": True, "scope": S.SCOPE if failed else S.FAILED_SCOPE,
                       "request": {**q.request, "source_tree": "c" * 40}, "github": {**q.github, "runAttempt": "2"},
                       "account": {**ACCOUNT, "uid": 0}, "policySha256": "0" * 64, "productExitCode": 124,
                       "purpose": "startup-other", "receiptSha256": "bad", "startupInputsSha256": "bad", "files": {},
                       "commandReturnedRawNs": 251 * NS, "exportReturnedRawNs": 199 * NS,
                       "uploadEndRawNs": 260 * NS}
            for name, value in changes.items():
                with self.subTest(failed=failed, name=name), self.assertRaises(S.StartupError):
                    self.validate_seal(q, failed, {**q.seal, name: value})
            for outcome in ("cancelled", "skipped", "success" if failed else "failure"):
                q.env[S.PREFIX + "OUTCOME"] = outcome
                with self.assertRaises(S.StartupError):
                    self.validate_seal(q, failed)
            q = seal_fixture(failed)
            q.env[S.PREFIX + ("SUCCESS_SHA256" if failed else "FAILED_SHA256")] = "e" * 64
            with self.assertRaises(S.StartupError):
                self.validate_seal(q, failed)

    def test_original_output_descriptor_return_is_closed_and_exact_seal_bound(self):
        for failed in (False, True):
            q = seal_fixture(failed)
            S.validate_step_return(q.step, q.seal, q.seal_hash, failed=failed)
            for changed in ({**q.step, "sealSha256": "0" * 64}, {**q.step, "intendedExitCode": 125},
                            {**q.step, "returnedRawNs": 249 * NS},
                            {**q.step, "commandFile": {**q.step["commandFile"], "closed": False}},
                            {**q.step, "commandFile": {**q.step["commandFile"], "sha256": "0" * 64}}):
                with self.assertRaises(S.StartupError):
                    S.validate_step_return(changed, q.seal, q.seal_hash, failed=failed)

    @contextlib.contextmanager
    def guard(self, failed):
        q, parent = seal_fixture(failed), Path("/controlled/p2pkit-jmdns-startup-unit")
        name = "startup-failed-product.json" if failed else "startup-success.json"
        before = "before-failed-upload.json" if failed else "before-upload.json"
        roster = q.source_roster
        contents = {parent / name: S.encoded(q.seal), parent / "step-return.json": S.encoded(q.step),
                    parent / "startup-inputs.json": q.prepared_raw,
                    parent / "outputs" / q.group / "manifest.json": q.manifest,
                    parent / before: S.encoded({"schema": 1, "scope": q.seal["scope"], "sealSha256": q.seal_hash,
                        "filesSha256": S.digest(S.encoded(q.seal["files"])), "returnedRawNs": 258 * NS})}
        q.writes, q.contents = {}, contents
        with contextlib.ExitStack() as stack:
            for target, name, value in ((S.os, "environ", q.env), (S.sys, "stdout", io.StringIO())):
                stack.enter_context(patch.object(target, name, value))
            for target, name, options in (
                (S, "original_request", {"return_value": (q.request, q.github)}),
                (S, "operation", {"return_value": (parent, q.allocation, [11, 22])}),
                (S.bridge, "account", {"return_value": ACCOUNT}),
                (M, "shared_raw_ns", {"return_value": 260 * NS}), (M, "budget", {}),
                (M, "environment", {"side_effect": lambda _: contextlib.nullcontext()}),
                (M, "child_environment", {"return_value": {}}), (S, "module", {"return_value": Mock()}),
                (M, "clean_source", {}), (S, "read_file", {"side_effect": lambda path, *args: (contents[path], {})}),
                (S, "write_new", {"side_effect": lambda path, raw: q.writes.__setitem__(path.name, S.parsed(raw))}),
            ):
                stack.enter_context(patch.object(target, name, **options))
            q.opposite = stack.enter_context(patch.object(S.os.path, "lexists", return_value=False))
            q.roster = stack.enter_context(patch.object(M, "source_roster", return_value=roster))
            q.outputs = stack.enter_context(patch.object(S, "output_snapshot", return_value=q.seal["files"]))
            yield q

    def test_upload_guards_separate_both_outcomes_and_require_actual_upload_return(self):
        for failed in (False, True):
            for after in (False, True):
                with self.subTest(failed=failed, after=after), self.guard(failed) as q:
                    self.assertEqual(S.guard_upload(after=after, failed=failed), 0)
                    self.assertEqual(len(q.writes), 1)
                    value = next(iter(q.writes.values()))
                    self.assertEqual(value["scope"], q.seal["scope"])
                    if after:
                        self.assertEqual((value["artifactId"], value["retentionDays"], value["remoteReadbackRequired"]),
                                         ("567", 14, True))
            for failure in ("hash", "opposite", "inputs", "source", "files", "manifest", "upload", "id", "digest"):
                with self.subTest(failed=failed, failure=failure), self.guard(failed) as q:
                    if failure == "hash":
                        q.env[S.PREFIX + ("FAILED_SHA256" if failed else "SUCCESS_SHA256")] = "f" * 64
                    elif failure == "opposite":
                        q.opposite.return_value = True
                    elif failure == "inputs":
                        path = next(path for path in q.contents if path.name == "startup-inputs.json")
                        q.contents[path] = S.encoded({"sourceRoster": {}})
                    elif failure == "source":
                        q.roster.return_value = {}
                    elif failure == "files":
                        q.outputs.return_value = {}
                    elif failure == "manifest":
                        path = next(path for path in q.contents if path.name == "manifest.json")
                        q.contents[path] = b"different manifest"
                    else:
                        field = {"upload": "UPLOAD_OUTCOME", "id": "ARTIFACT_ID", "digest": "ARTIFACT_DIGEST"}[failure]
                        q.env[S.PREFIX + field] = "failed"
                    with self.assertRaises(S.StartupError):
                        S.guard_upload(after=True, failed=failed)
                    self.assertFalse(q.writes)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
