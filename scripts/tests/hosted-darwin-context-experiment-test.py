#!/usr/bin/env python3
"""Eleven focused offline families. No native, hosted, key or export acceptance.

All requests/events/accounts below are explicit synthetic DATA. Process, socket,
privileged and crypto behavior must be faked; the audit hook prevents real use.
This source is authored without running/importing it or the new experiment.
"""
import ast
import contextlib
import copy
import ctypes  # Standard module loaded before forbidding any native-library acquisition.
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
WORKFLOW = ROOT / ".github/workflows/darwin-native-context-experiment.yml"
SHA, TREE, BINDING = "a" * 40, "b" * 40, "c" * 64
CANARY = "SYNTHETIC_PRIVATE_CANARY"


def offline(event, _args):
    if event.startswith("socket.") or event in {
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.kill", "os.killpg",
        "ctypes.dlopen", "os.putenv", "os.unsetenv", "os.setuid", "os.setgid", "os.setgroups",
    }:
        raise AssertionError("OFFLINE_CONTROL_FORBIDDEN_OPERATION")


sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_experiment_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)


def request_fixture():
    request = dict(source_sha=SHA, source_tree=TREE)
    ref = "refs/heads/work/release-foundation-context-synthetic"
    env = dict(GITHUB_ACTIONS="true", GITHUB_REPOSITORY=M.REPOSITORY, GITHUB_EVENT_NAME="workflow_dispatch",
        GITHUB_JOB="context_experiment", GITHUB_ACTOR=M.OWNER, GITHUB_ACTOR_ID=M.OWNER_ID,
        GITHUB_TRIGGERING_ACTOR=M.OWNER, GITHUB_SHA=SHA, GITHUB_WORKFLOW_SHA=SHA, GITHUB_REF=ref,
        GITHUB_WORKFLOW_REF=M.REPOSITORY + "/" + M.WORKFLOW + "@" + ref,
        GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1", RUNNER_ENVIRONMENT="github-hosted",
        RUNNER_OS="macOS", RUNNER_ARCH="ARM64")
    return request, env


def account_fixture():
    return dict(uid=501, euid=501, gid=20, egid=20, groups=[12, 20, 61])


def event_fixture(raw=0, pid=123):
    if isinstance(raw, signal.Signals):
        raw = int(raw)  # A native wait word is an int, not Python's signal-name enum.
    return dict(ident=pid, filter=M.EVFILT_PROC, flags=M.EV_EOF,
                fflags=M.NOTE_EXIT | M.NOTE_EXITSTATUS, data=raw)


def status(raw=0):
    return M.decode_exit_event(event_fixture(raw), 123)


def probe_fixture():
    return dict(stage="SEND", result="KERNEL_ACCEPTED", errno="NONE", sent=42,
                socketCreated=True, closed=True, closeError="NONE")


def frames(case):
    return [M.frame_record(M.frame_value(serial, BINDING, {}))
            for serial, _direction, _kind in M.FRAME_ROSTER if not (case == "N3" and serial == 7)]


def native_identity(pid=123, parent=100):
    return dict(pid=pid, parentPid=parent, uniqueId=pid + 1000, parentUniqueId=parent + 1000,
                pidVersion=2, startSeconds=1700000000, startMicroseconds=123,
                uid=501, realUid=501, gid=20, realGid=20, status=3)


class NativeModel(M.Darwin):
    """Fake observation endpoints only; inherited methods remain actual code."""
    def __init__(self):
        self.identities = {123: native_identity(), 124: native_identity(124, 123)}
        self.watched, self.events, self.closed = {}, {}, False
        self.registrations, self.attach_attempts, self.signals = {}, [], []
        self.observations = []

    def identity(self, pid):
        self.observations.append(("identity", pid))
        return dict(self.identities[pid])

    def token(self, identity):
        self.same(identity)
        self.observations.append(("fake-token", identity["pid"]))
        return b"SYNTHETIC_TOKEN_NOT_NATIVE".ljust(32, b"_")


class ByteChannel:
    def __init__(self, raw=b""):
        self.raw, self.sent = bytearray(raw), bytearray()

    def recv(self, maximum):
        result = bytes(self.raw[:maximum])
        del self.raw[:maximum]
        return result

    def send(self, raw):
        count = min(len(raw), 3)
        self.sent.extend(raw[:count])
        return count

    def recvmsg(self, maximum, _ancillary_size):
        return self.recv(maximum), [], 0, None


def workflow_conditions(values, cancelled=False):
    """Evaluate only actual three fixed Boolean guards, not an Actions emulator."""
    expressions = re.findall(r"^        if: \$\{\{ (.+) \}\}$", WORKFLOW.read_text(), re.MULTILINE)
    if len(expressions) != 3:
        raise AssertionError("FIXED_THREE_UPLOAD_GUARDS")
    allowed = (ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Constant,
               ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq)
    result = []
    for expression in expressions:
        text = re.sub(r"steps\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
                      lambda match: repr(values[match[0]]), expression)
        text = text.replace("cancelled()", repr(cancelled)).replace("&&", " and ").replace("||", " or ")
        text = re.sub(r"!(?!=)", " not ", text).strip()
        node = ast.parse(text, mode="eval")
        if any(not isinstance(item, allowed) for item in ast.walk(node)):
            raise AssertionError("ONLY_FIXED_BOOLEAN_GUARD_DATA")
        result.append(eval(compile(node, "<fixed-workflow-guard>", "eval"), {"__builtins__": {}}, {}))
    return result


class Focused(unittest.TestCase):
    @contextlib.contextmanager
    def _export_model(self, directory, outcome="SUCCESS"):
        """One tiny owned filesystem, fake native/key returns, real F composition.

        No keyring or GPG process exists. The labelled non-ciphertext bytes only
        exercise file/hash custody; they provide no encryption/native evidence.
        """
        directory.mkdir(mode=0o700)
        for name in ("evidence", "outputs"):
            (directory / name).mkdir(mode=0o700)
        with patch.object(M.os, "environ", {}):
            context = M.Context()
        request, env = request_fixture()
        context.request, context.github = request, M.validate_request(request, env, dict(request))
        context.parent, context.evidence = directory, directory / "evidence"
        context.parent_identity = M.private_directory(directory)
        context.account, context.environment = account_fixture(), {"PATH": "/usr/bin:/bin"}
        context.source = {"commit": SHA, "tree": TREE, "files": {M.SCRIPT: "d" * 64}}
        context.interpreter = {"path": "/synthetic/python", "sha256": "e" * 64}
        epoch = (M.POLICY_EXPIRES - 86400) * M.NS
        context.allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",
                                  startedMonotonicNs=M.NS, startedEpochNs=epoch)
        context.started, context.step_end, context.job_end = 2 * M.NS, 722 * M.NS, 1441 * M.NS
        context.policy_end = 86401 * M.NS
        context.native, context.sentinel_pipes = types.SimpleNamespace(closed=True), types.SimpleNamespace(closed=True)
        context.sentinel_closed, context.finished = True, True
        no_network = dict(stage="NO_NETWORK", result="EXPECTED_FAILURE", errno="NONE", sent=0,
                          socketCreated=False, closed=False, closeError="NONE")
        cases = (("N1", 0, status(), probe_fixture()), ("N2", 23, status(23 << 8), no_network),
                 ("N3", -signal.SIGTERM, status(24 << 8), None),
                 ("N4", 0, status(signal.SIGTERM), dict(no_network, result="NO_NETWORK")))
        for case, code, service_status, probe in cases:
            passed = outcome == "SUCCESS" or case != "N1"
            if not passed:
                code, service_status = 23, status(23 << 8)
                probe = dict(probe_fixture(), result="FAIL", errno="EHOSTUNREACH", sent=0)
            context.case_results.append({"case": case, "passed": passed, "probe": probe,
                "closure": {key: True for key in M.CLOSURE_KEYS}, "originalServiceFinalData": {"producerCode": code},
                "serviceNative": {"status": service_status}})
        context.result = {"cases": context.case_results, "outcome": outcome}
        recipient = types.SimpleNamespace(work_dir=directory / "synthetic-public-work", home=directory / "synthetic-public-home")
        context.recipient_work, context.recipient_home = [301, 302], [303, 304]
        context.recipient_files = {name: {"path": str(recipient.work_dir / name), "size": 1, "sha256": "f" * 64}
                                   for name in ("recipient.asc", "recipient.gpg")}
        context.gpg = {"path": "/synthetic/not-an-executable", "size": 1, "sha256": "f" * 64}
        fake_pins = {value["path"]: copy.deepcopy(value) for value in (*context.recipient_files.values(), context.gpg)}
        fake_directories = {str(recipient.work_dir): list(context.recipient_work), str(recipient.home): list(context.recipient_home)}
        command = directory / "original-command"
        M.write_new(command, b"")
        M.write_new(directory / "allocation.json", M.encoded(context.allocation))
        env.update(GITHUB_OUTPUT=str(command), RUNNER_TEMP=str(directory.parent))
        context.output = M.CommandFile(env)
        original_close, original_emit = context.output.close, context.output.emit
        ledger, clock = [], {"ns": 10 * M.NS}
        real_pin, real_directory, real_write, real_freeze = M.file_pin, M.private_directory, M.write_new, M.freeze_evidence

        def write(path, raw):
            ledger.append("write:" + str(Path(path).relative_to(directory)))
            return real_write(path, raw)

        def pinned(path, *args, **kwargs):
            key = os.fspath(path)
            return copy.deepcopy(fake_pins[key]) if key in fake_pins else real_pin(path, *args, **kwargs)

        def checked_directory(path, **kwargs):
            key = os.fspath(path)
            return list(fake_directories[key]) if key in fake_directories else real_directory(path, **kwargs)

        def freeze(path, end):
            ledger.append("freeze-enter")
            result = real_freeze(path, end)
            ledger.append("freeze-return")
            return result

        def emit(values):
            ledger.append("output-enter")
            result = original_emit(values)
            self.assertTrue(context.output.closed)
            ledger.append("output-close-return")
            return result

        def public_export(evidence, output, original_recipient, **bindings):
            ledger.append("export-enter")
            self.assertEqual((evidence, output), (context.evidence, directory / "outputs/encrypted"))
            self.assertIs(original_recipient, context.recipient_original)
            self.assertEqual(bindings, dict(source_commit=SHA, source_tree=TREE, run_id="123", run_attempt="1",
                                           max_bytes=2 * 1024 * 1024, max_members=128, timeout_seconds=110))
            raw = b"SYNTHETIC_NOT_ENCRYPTED_OFFLINE_DATA"
            manifest = dict(schema=1, scope="ENCRYPTED_PRIVATE_TEST_EVIDENCE", source={"commit": SHA, "tree": TREE},
                            github={"repository": M.REPOSITORY, "runId": "123", "runAttempt": "1"},
                            artifact={"name": "evidence.tar.gz.gpg", "size": len(raw), "sha256": M.digest(raw)})
            output.mkdir(mode=0o700)
            M.write_new(output / "evidence.tar.gz.gpg", raw)
            M.write_new(output / "manifest.json", M.encoded(manifest))
            ledger.append("export-return")
            return manifest

        context.exporter = types.SimpleNamespace(export_encrypted=unittest.mock.Mock(side_effect=public_export),
                                                validate_recipient=unittest.mock.Mock(return_value=recipient))
        # Explicit fake validation return for this fixture; actual prepare's
        # single validation call is separately source-checked below.
        context.recipient = context.exporter.validate_recipient()
        context.recipient_original = context.recipient
        with contextlib.ExitStack() as stack:
            for manager in (
                patch.object(M.os, "environ", env), patch.object(M.time, "monotonic_ns", side_effect=lambda: clock["ns"]),
                patch.object(M.time, "time_ns", side_effect=lambda: epoch + clock["ns"] - M.NS),
                patch.object(M, "original_request", side_effect=lambda actual: (request, M.validate_request(request, actual, request))),
                patch.object(M, "operation_paths", return_value=(directory, context.parent_identity)),
                patch.object(M, "account", side_effect=account_fixture),
                patch.object(M, "source_snapshot", side_effect=lambda *_args: copy.deepcopy(context.source)),
                patch.object(M, "checked_interpreter", side_effect=lambda *_args: copy.deepcopy(context.interpreter)),
                patch.object(M, "private_directory", side_effect=checked_directory),
                patch.object(M, "file_pin", side_effect=pinned), patch.object(M, "write_new", side_effect=write),
                patch.object(M, "freeze_evidence", side_effect=freeze), patch.object(context.output, "emit", side_effect=emit),
            ):
                stack.enter_context(manager)
            try:
                yield context, ledger, env, clock
            finally:
                original_close()
                # Only this fixture's own synthetic tree, never repository or
                # private originals. Restore traversal for temporary cleanup.
                for current, _children, _names in os.walk(directory):
                    os.chmod(current, 0o700)

    def test_01_exact_manual_request_and_original_source_identity(self):
        request, env = request_fixture()
        original_request, original_env = copy.deepcopy(request), dict(env)
        github = M.validate_request(request, env, dict(request))
        self.assertEqual(github["source"], SHA)
        self.assertEqual(github["sourceTree"], TREE)
        self.assertEqual(github["runId"], "123")
        self.assertEqual(github["runAttempt"], "1")
        self.assertEqual(github["workflow"], M.WORKFLOW)
        self.assertEqual(request, original_request)
        self.assertEqual(env, original_env)
        for bad in ({}, dict(request, operation="generate"), dict(request, source_sha=True),
                    dict(request, source_tree=123), dict(request, source_sha=SHA.upper()),
                    dict(request, source_tree=TREE[:-1]),
                    dict(controller_sha=SHA, controller_tree=TREE, candidate_sha=SHA,
                         candidate_tree=TREE, dependency_base_sha=SHA),
                    dict(controller_sha=SHA, controller_tree=TREE, candidate_sha=SHA,
                         candidate_tree=TREE, dependency_base_sha=SHA, operation="diagnose-jmdns")):
            with self.assertRaises(M.ExperimentError):
                M.validate_request(bad, env, bad)
        for key, bad in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "fork/P2pKit"),
                         ("GITHUB_EVENT_NAME", "push"), ("GITHUB_JOB", "generate"),
                         ("GITHUB_ACTOR", "OTHER"), ("GITHUB_ACTOR_ID", "1"),
                         ("GITHUB_TRIGGERING_ACTOR", "OTHER"), ("GITHUB_SHA", "d" * 40),
                         ("GITHUB_WORKFLOW_SHA", "d" * 40), ("GITHUB_WORKFLOW_REF", "OTHER"),
                         ("GITHUB_REF", "refs/heads/main"), ("GITHUB_RUN_ID", "0"),
                         ("GITHUB_RUN_ATTEMPT", "0"), ("GITHUB_RUN_ATTEMPT", True),
                         ("RUNNER_ENVIRONMENT", "self-hosted")):
            with self.assertRaises(M.ExperimentError):
                M.validate_request(request, {**env, key: bad}, dict(request))
        for original_event in ({}, dict(request, extra=True), dict(request, source_tree="d" * 40)):
            with self.assertRaises(M.ExperimentError):
                M.validate_request(request, env, original_event)
        with self.assertRaises(M.ExperimentError):
            M.parsed(b'{"source_sha":"a","source_sha":"b","source_tree":"c"}')
        with tempfile.TemporaryDirectory(prefix="p2pkit-context-entry-controls-") as temporary:
            workspace = Path(temporary).resolve()
            controller = workspace / "controller"
            controller.mkdir(mode=0o700)
            event = workspace / "event.json"
            M.write_new(event, M.encoded({"inputs": request}))
            entry = {**env, "GITHUB_WORKSPACE": str(workspace), "GITHUB_EVENT_PATH": str(event),
                     "P2PKIT_CONTEXT_REQUEST": M.encoded(request).decode("ascii")}
            with patch.object(M, "ROOT", controller), patch.object(M, "__file__", str(controller / M.SCRIPT)), \
                    patch.object(M.platform, "system", return_value="Darwin"), \
                    patch.object(M.platform, "machine", return_value="arm64"):
                self.assertEqual(M.original_request(entry), (request, github))
                for key, value in (("RUNNER_OS", "Linux"), ("RUNNER_ARCH", "X64"),
                                   ("GITHUB_JOB", "generate"), ("GITHUB_WORKFLOW_SHA", "d" * 40),
                                   ("GITHUB_EVENT_NAME", "push"), ("GITHUB_RUN_ATTEMPT", "0"),
                                   ("PYTHONPATH", CANARY), ("DYLD_INSERT_LIBRARIES", CANARY),
                                   ("P2PKIT_AUDIT_JOB_ID", CANARY)):
                    with patch.object(M.os, "environ", {**entry, key: value}), \
                            patch.object(M, "Admin") as admin, patch.object(M, "Darwin") as native, \
                            patch.object(M, "CommandFile") as output, patch.object(M, "load_module") as loader:
                        with self.assertRaises(M.ExperimentError):
                            M.prepare()
                        admin.assert_not_called()
                        native.assert_not_called()
                        output.assert_not_called()
                        loader.assert_not_called()
                with patch.object(M.os, "environ", entry), patch.object(M.os, "getuid", return_value=0), \
                        patch.object(M.os, "geteuid", return_value=0), patch.object(M, "Admin") as admin, \
                        patch.object(M, "CommandFile") as output:
                    with self.assertRaises(M.ExperimentError):
                        M.prepare()
                    admin.assert_not_called()
                    output.assert_not_called()

    def test_02_original_input_account_and_clock_preservation(self):
        request, env = request_fixture()
        github = M.validate_request(request, env, dict(request))
        allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",
                          startedMonotonicNs=M.NS, startedEpochNs=1790000000 * M.NS)
        now, wall = 100 * M.NS, allocation["startedEpochNs"] + 99 * M.NS
        self.assertEqual(M.validate_allocation(allocation, request, github, now, wall),
                         allocation["startedMonotonicNs"] + 1440 * M.NS)
        for key, value in (("runAttempt", "2"), ("source", "d" * 40), ("sourceTree", "d" * 40),
                           ("schema", True), ("startedMonotonicNs", True),
                           ("startedEpochNs", float("nan")), ("startedMonotonicNs", now + 1)):
            with self.assertRaises(M.ExperimentError):
                M.validate_allocation({**allocation, key: value}, request, github, now, wall)
        for instant, epoch in ((True, wall), (now, float("inf")), (now, wall + 11 * M.NS),
                               (allocation["startedMonotonicNs"] + 1440 * M.NS,
                                allocation["startedEpochNs"] + 1440 * M.NS)):
            with self.assertRaises(M.ExperimentError):
                M.validate_allocation(allocation, request, github, instant, epoch)
        for marker in M.OWNER_ENV:
            with self.assertRaises(M.ExperimentError):
                M.validate_request(request, {**env, marker: CANARY}, dict(request))
        original = account_fixture()
        self.assertIs(M.validate_account(original), original)
        self.assertEqual(M.validate_account(dict(original), original), original)
        for key, value in (("uid", 0), ("euid", 0), ("uid", True), ("egid", 21),
                           ("groups", [61, 20, 12]), ("groups", [12, 20, 20, 61]),
                           ("groups", [12, True]), ("groups", [12, 20])):
            with self.assertRaises(M.ExperimentError):
                M.validate_account({**original, key: value}, original)
        self.assertEqual(original, account_fixture())
        for bad in (b"\xff", b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{"x":1,"x":2}'):
            with self.assertRaises(M.ExperimentError):
                M.parsed(bad)
        with self.assertRaises(M.ExperimentError):
            M.parsed(b"x" * (M.FRAME_BYTES + 1))
        policy_raw = (ROOT / M.POLICY_PATH).read_bytes()
        original_policy = M.validate_policy(policy_raw, M.POLICY_EXPIRES - 86400)
        self.assertEqual(original_policy["retentionDays"], 14)
        self.assertEqual(original_policy["recipient"]["fingerprint"], M.FINGERPRINT)
        for now in (True, float("nan"), float("inf"), M.POLICY_EXPIRES - 12600,
                    M.POLICY_EXPIRES - M.JOB_SECONDS, M.POLICY_EXPIRES):
            with self.assertRaises(M.ExperimentError):
                M.validate_policy(policy_raw, now)
        with self.assertRaises(M.ExperimentError):
            M.validate_policy(policy_raw + b" ", M.POLICY_EXPIRES - 86400)
        with tempfile.TemporaryDirectory(prefix="p2pkit-context-controls-") as temporary:
            directory = Path(temporary).resolve()
            identity = M.private_directory(directory, empty=True)
            self.assertEqual(identity, [directory.stat().st_dev, directory.stat().st_ino])
            path = directory / "synthetic-original"
            M.write_new(path, CANARY.encode())
            self.assertEqual(M.read_file(path), CANARY.encode())
            with self.assertRaises(FileExistsError):
                M.write_new(path, b"different")
            with self.assertRaises(M.ExperimentError):
                M.private_directory(directory, empty=True)
            path.chmod(0o622)
            with self.assertRaises(M.ExperimentError):
                M.read_file(path)
            path.chmod(0o600)
            alias = directory / "symlink"
            alias.symlink_to(path)
            with self.assertRaises(M.ExperimentError):
                M.read_file(alias)
            os.link(path, directory / "hardlink")
            with self.assertRaises(M.ExperimentError):
                M.read_file(path)

    def test_03_root_os_exclusivity_exact_target_and_original_retirement(self):
        label = "p2pkit.context.synthetic.n1"
        root = "/private/var/db/p2pkit-context.ABCDEFGHIJ"
        plist_path = root + "/job.KLMNOPQRST"

        def metadata(path, size=0):
            is_root = path == root
            mode, inode, links = (0o40700, 100, 2) if is_root else (0o100600, 101, 1)
            raw = f"1:{inode}:{mode:o}:0:0:{links}:{size}:170:170\n".encode("ascii")
            permissions = "drwx------" if is_root else "-rw-------"
            acl = f"{permissions} {links} root wheel {size} Sep 29 00:00 {path}\n".encode("ascii")
            return raw, acl

        raw, acl = metadata(plist_path)
        original = M.parse_admin_metadata(raw, acl, plist_path, "file", mode=0o600, size=0)
        for index, value in ((0, "2"), (1, "102"), (2, "100622"), (2, "120600"),
                             (3, "501"), (4, "20"), (5, "2"), (6, "1")):
            fields = raw.decode("ascii").strip().split(":")
            fields[index] = value
            with self.assertRaises(M.ExperimentError):
                M.parse_admin_metadata(":".join(fields).encode(), acl, plist_path, "file",
                                       mode=0o600, previous=original, size=0)
        for bad in (acl.replace(b"-rw------- ", b"-rw-------+ "), acl + b" 0: user:synthetic allow read\n",
                    acl.replace(plist_path.encode(), b"/different"), b"", b"\xff"):
            with self.assertRaises(M.ExperimentError):
                M.parse_admin_metadata(raw, bad, plist_path, "file", mode=0o600)
        for alias in ("//private/var/run", "/private/var/../run", "/private//var/run", "/private/./var/run",
                      "/private/var/run\n", "relative/path", "/private/has space", "/private/$name", "/private/`name`"):
            with self.assertRaises(M.ExperimentError):
                M.safe_component_path(alias)
        homebrew = "/opt/homebrew/Cellar/python@3.14/3.14.0/bin/python3.14"
        self.assertEqual(M.safe_component_path(homebrew), homebrew)  # String grammar only, no installed-path claim.

        absent_text = ('Could not find service "' + label + '" in domain for system\n').encode("ascii")
        absent = dict(code=1, stdout=b"", stderr=absent_text, waited=True, eof=True, closed=True)
        self.assertTrue(M.service_absent(absent, label))
        self.assertTrue(M.service_absent({**absent, "code": 64, "stderr": b"Bad request.\n" + absent_text}, label))
        for key, value in (("code", 0), ("code", True), ("code", -9), ("code", 256),
                           ("stdout", b"not empty"), ("stderr", b"permission denied\n"),
                           ("stderr", absent_text.replace(label.encode(), b"p2pkit.context.other")),
                           ("waited", False), ("eof", False), ("closed", False)):
            with self.assertRaises(M.ExperimentError):
                M.service_absent({**absent, key: value}, label)

        with tempfile.TemporaryDirectory(prefix="p2pkit-context-admin-controls-") as temporary:
            directory = Path(temporary).resolve()
            context = types.SimpleNamespace(interpreter={"path": "/usr/bin/python3"}, username="synthetic",
                                            groupname="staff", os_env={"PATH": "/usr/bin:/bin", "LANG": "C"})
            with patch.object(M.os, "environ", {}):
                admin = M.Admin(context, directory, label, 40 * M.NS)
            plist = M.plistlib.loads(admin.plist)
            self.assertEqual(plist["UserName"], "synthetic")
            self.assertEqual(plist["GroupName"], "staff")
            self.assertTrue(plist["InitGroups"] and plist["RunAtLoad"])
            self.assertFalse(plist["KeepAlive"] or plist["AbandonProcessGroup"])
            self.assertEqual([plist[key] for key in ("StandardInPath", "StandardOutPath", "StandardErrorPath")],
                             ["/dev/null"] * 3)
            self.assertEqual(plist["ProgramArguments"], admin.arguments)
            calls, state = [], dict(written=False, registered=False, running=True)

            def service_print():
                state_text = "running" if state["running"] else "not running"
                return ("system/" + label + " = {\n\tpath = " + plist_path +
                        "\n\ttype = LaunchDaemon\n\tstate = " + state_text + "\n\tprogram = " + admin.arguments[0] +
                        "\n\tpid = 123\n\targuments = {\n" + "".join("\t\t" + item + "\n" for item in admin.arguments) +
                        "\t}\n}\n").encode("ascii")

            def returned(argv, end_ns, env, *, input_raw=b"", stage="SOURCE"):
                # Synthetic exact OS responses exercise the real Admin methods.
                # They are not installed launchctl/stat observations.
                self.assertEqual(argv[:3], ["/usr/bin/sudo", "-n", "--"])
                self.assertEqual(end_ns, 40 * M.NS)
                self.assertIs(env, context.os_env)
                command = argv[3:]
                calls.append(command)
                result = dict(argv=list(argv), code=0, stdout=b"", stderr=b"", waited=True, eof=True, closed=True)
                if command == ["/usr/bin/mktemp", "-d", M.ROOT_TEMPLATE]:
                    result["stdout"] = (root + "\n").encode()
                elif command == ["/usr/bin/mktemp", root + "/job.XXXXXXXXXX"]:
                    result["stdout"] = (plist_path + "\n").encode()
                elif command[:3] == ["/usr/bin/stat", "-f", M.STAT_FORMAT]:
                    result["stdout"] = metadata(command[3], len(admin.plist) if state["written"] and command[3] == plist_path else 0)[0]
                elif command[:2] == ["/bin/ls", "-lde"]:
                    result["stdout"] = metadata(command[2], len(admin.plist) if state["written"] and command[2] == plist_path else 0)[1]
                elif command == ["/usr/bin/tee", plist_path]:
                    self.assertIsNotNone(admin.file_meta)
                    self.assertEqual(input_raw, admin.plist)
                    state["written"], result["stdout"] = True, input_raw
                elif command == ["/bin/cat", plist_path]:
                    result["stdout"] = admin.plist
                elif command == ["/bin/launchctl", "print", "system/" + label]:
                    if state["registered"]:
                        result["stdout"] = service_print()
                    else:
                        result.update(absent)
                elif command == ["/bin/launchctl", "bootstrap", "system", plist_path]:
                    state["registered"] = True
                elif command == ["/bin/launchctl", "bootout", "system/" + label]:
                    state["registered"] = False
                elif command not in (["/bin/rm", plist_path], ["/bin/rmdir", root]):
                    self.fail("UNEXPECTED_SYNTHETIC_ADMIN_COMMAND")
                return result

            original_lstat = M.os.lstat

            def absent_original(path, *args, **kwargs):
                if os.fspath(path) in (root, plist_path):
                    raise FileNotFoundError(M.errno.ENOENT, "SYNTHETIC_ABSENT")
                return original_lstat(path, *args, **kwargs)

            try:
                with patch.object(M, "capture_fixed", side_effect=returned), patch.object(M.os, "lstat", side_effect=absent_original):
                    admin.create()
                    for command, input_raw in ((["/bin/sh", "-c", CANARY], b""),
                                               (["/usr/bin/mktemp", "-u", root + "/job.XXXXXXXXXX"], b""),
                                               (["/usr/bin/tee", plist_path], b"changed"),
                                               (["/bin/rm", "-rf", root], b""),
                                               (["/bin/launchctl", "bootout", "system/" + label], b""),
                                               (["/bin/launchctl", "bootstrap", "system", "/different"], b"")):
                        with self.assertRaises(M.ExperimentError):
                            admin._allowed(command, input_raw)
                    admin.bootstrap()
                    self.assertEqual(admin.inspect(native_identity())["pid"], 123)
                    valid_print = service_print()
                    for bad in (valid_print.replace(b"pid = 123", b"pid = 124"),
                                valid_print.replace(b"pid = 123", b"pid = 123\n\tpid = 123"),
                                valid_print.replace(b"type = LaunchDaemon", b"type = LaunchAgent"),
                                valid_print.replace(b"_service", b"_probe"),
                                valid_print.replace(plist_path.encode(), b"/different")):
                        with self.assertRaises(M.ExperimentError):
                            M.parse_service_print(bad, label, plist_path, admin.arguments, 123)
                    state["running"] = False
                    admin.retire(native_identity())
                self.assertTrue(admin.retired and admin.removed and not state["registered"])
                self.assertEqual(len(calls), 40)
                self.assertLess(calls.index(["/usr/bin/mktemp", root + "/job.XXXXXXXXXX"]),
                                calls.index(["/usr/bin/tee", plist_path]))
                self.assertLess(calls.index(["/bin/launchctl", "bootout", "system/" + label]),
                                calls.index(["/bin/rm", plist_path]))
                self.assertLess(calls.index(["/bin/rm", plist_path]), calls.index(["/bin/rmdir", root]))
            finally:
                admin.close()
            self.assertTrue(admin.closed and admin.record.closed)

            for index, change in enumerate(({"code": 1}, {"stderr": CANARY.encode()}, {"waited": False},
                                             {"eof": False}, {"closed": False})):
                child = directory / str(index)
                child.mkdir(mode=0o700)
                with patch.object(M.os, "environ", {}):
                    failed = M.Admin(context, child, label, 40 * M.NS)
                result = dict(argv=["/usr/bin/sudo", "-n", "--", "/usr/bin/mktemp", "-d", M.ROOT_TEMPLATE],
                              code=0, stdout=(root + "\n").encode(), stderr=b"", waited=True, eof=True, closed=True)
                try:
                    with patch.object(M, "capture_fixed", return_value={**result, **change}) as capture:
                        with self.assertRaises(M.ExperimentError):
                            failed.create()
                        capture.assert_called_once()
                    self.assertIsNone(failed.root)
                    self.assertFalse(failed.bootstrapped or failed.retired or failed.removed)
                    with patch.object(M, "_UNCLOSED_COMMANDS", [object()]), patch.object(M, "capture_fixed") as capture:
                        with self.assertRaises(M.ExperimentError):
                            failed.create()
                        capture.assert_not_called()
                finally:
                    failed.close()

    def test_04_original_lifetime_account_and_fresh_peer_not_inherited_fd(self):
        native, expected = NativeModel(), native_identity()
        self.assertEqual(native.same(expected), expected)
        for key, changed in (("pidVersion", 3), ("uniqueId", 9999), ("parentPid", 99),
                             ("parentUniqueId", 99), ("startMicroseconds", 124), ("uid", 502),
                             ("realUid", 502), ("gid", 21), ("realGid", 21), ("status", 5)):
            native.identities[123] = {**expected, key: changed}
            with self.assertRaises(M.ExperimentError):
                native.same(expected)
        native.identities[123] = dict(expected)
        calls = []

        class Peer:
            token = b"SYNTHETIC_TOKEN_NOT_NATIVE".ljust(32, b"_")
            def getsockopt(self, level, option, size):
                calls.append((level, option, size))
                return M.struct.pack("=i", 123) if option == M.LOCAL_PEERPID else self.token

        peer = Peer()
        self.assertEqual(native.peer(peer), expected)
        self.assertEqual(calls, [(M.SOL_LOCAL, M.LOCAL_PEERPID, 4), (M.SOL_LOCAL, M.LOCAL_PEERTOKEN, 32)])
        for token in (b"", b"x" * 32):
            peer.token = token
            with self.assertRaises(M.ExperimentError):
                native.peer(peer)
        inherited = {"GH_TOKEN": CANARY, "GITHUB_OUTPUT": CANARY, "PYTHONPATH": CANARY,
                     "DYLD_INSERT_LIBRARIES": CANARY, "__CF_USER_TEXT_ENCODING": CANARY}
        with patch.object(M.os, "environ", inherited), patch.object(M.os, "getuid", return_value=501):
            child = M.child_environment(Path("/synthetic/operation"))
        self.assertFalse(set(inherited) - {"__CF_USER_TEXT_ENCODING"} & set(child))
        self.assertNotIn(CANARY, str(child))
        self.assertEqual(inherited["GH_TOKEN"], CANARY)
        for marker in M.OWNER_ENV:
            with patch.object(M.os, "environ", {**inherited, marker: CANARY}):
                with self.assertRaises(M.ExperimentError):
                    M.child_environment(Path("/synthetic/operation"))
        prepared = dict(binding=BINDING, account=account_fixture(), source={"files": {M.SCRIPT: "d" * 64}},
                        boot="SYNTHETIC_BOOT_NOT_NATIVE", interpreter={"path": "/synthetic/python"})
        service, child = native_identity(), native_identity(124, 123)
        payload = dict(producer=child, parent=service, account=account_fixture(), sigtermDefault=True,
                       sigtermBlocked=False, sourceSha256="d" * 64, boot=prepared["boot"],
                       interpreter=prepared["interpreter"]["path"])
        ready = M.frame_value(3, BINDING, payload)
        self.assertEqual(M.validate_ready(ready, prepared, service, child), payload)
        for key, value in (("producer", dict(child, parentUniqueId=9)), ("parent", dict(service, uniqueId=9)),
                           ("account", dict(account_fixture(), groups=[12, 20])), ("sigtermDefault", False),
                           ("sigtermBlocked", True), ("sourceSha256", "e" * 64), ("boot", "OTHER"),
                           ("interpreter", "/different/python")):
            with self.assertRaises(M.ExperimentError):
                M.validate_ready(M.frame_value(3, BINDING, {**payload, key: value}), prepared, service, child)
        producer = next(node for node in ast.parse(SOURCE.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == "producer")
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                             node.func.attr == "peer" for node in ast.walk(producer)))

    def test_05_actual_returned_nonchild_wait_status_is_required(self):
        for raw, kind, value, code in ((0, "EXITED", 0, 0), (23 << 8, "EXITED", 23, 23),
                                       (24 << 8, "EXITED", 24, 24),
                                       (signal.SIGTERM, "SIGNALED", signal.SIGTERM, -signal.SIGTERM)):
            self.assertEqual(status(raw), dict(rawStatus=raw, kind=kind, value=value, popenCode=code))
        self.assertNotEqual(status(23)["popenCode"], 23)  # Raw wait data is not a direct Popen return.
        for key, value in (("ident", 124), ("filter", -1), ("flags", M.EV_ERROR),
                           ("fflags", M.NOTE_EXIT), ("fflags", M.NOTE_EXITSTATUS), ("fflags", 0),
                           ("data", None), ("data", True), ("data", -1), ("data", 65536),
                           ("data", 0x7f), ("data", 0xffff)):
            with self.assertRaises(M.ExperimentError):
                M.decode_exit_event({**event_fixture(), key: value}, 123)
        for bad in ({}, {key: value for key, value in event_fixture().items() if key != "data"},
                    {**event_fixture(), "finalFrame": True}):
            with self.assertRaises(M.ExperimentError):
                M.decode_exit_event(bad, 123)
        native = NativeModel()
        returned = types.SimpleNamespace(ident=123, filter=M.EVFILT_PROC, flags=M.EV_ERROR, fflags=0, data=0)
        queue = types.SimpleNamespace(control=lambda *_args: [returned])
        native.kqueue = queue
        with patch.object(M.select, "kevent", create=True, side_effect=lambda ident, **kw: (ident, kw)) as kevent:
            native.watch(native_identity())
            self.assertEqual(native.watched, {123: native_identity()})
            self.assertEqual(native.registrations[123]["receipts"][0],
                             dict(ident=123, filter=M.EVFILT_PROC, flags=M.EV_ERROR, fflags=0, data=0))
            self.assertEqual(kevent.call_args.kwargs["fflags"], M.NOTE_EXIT | M.NOTE_EXITSTATUS)
            with self.assertRaises(M.ExperimentError):
                native.watch(native_identity())
        for code in (1, 3, 13):
            native = NativeModel()
            native.kqueue = types.SimpleNamespace(control=lambda *_args, code=code:
                [types.SimpleNamespace(ident=123, filter=M.EVFILT_PROC, flags=M.EV_ERROR, fflags=0, data=code)])
            with patch.object(M.select, "kevent", create=True, return_value=object()):
                with self.assertRaises(M.ExperimentError):
                    native.watch(native_identity())
            self.assertFalse(native.watched)
        native = NativeModel()
        with self.assertRaises(M.ExperimentError):
            native.wait([native_identity()], 100 * M.NS)  # No observation without original registration.
        native.watched = {123: native_identity()}
        native.kqueue = types.SimpleNamespace(control=lambda *_args: [types.SimpleNamespace(**event_fixture(23 << 8))])
        with patch.object(M, "left", return_value=1):
            observed = native.wait([native_identity()], 100 * M.NS)
        self.assertEqual(observed[123]["status"]["popenCode"], 23)
        with tempfile.TemporaryDirectory(prefix="p2pkit-ctx-o5-") as temporary:
            root = Path(temporary).resolve()
            for failed_pid in (None, 123, 124):
                parent = root / str(failed_pid)
                parent.mkdir(mode=0o700)
                evidence = parent / "evidence"
                evidence.mkdir(mode=0o700)
                with patch.object(M.os, "environ", {}):
                    context = M.Context()
                request, env = request_fixture()
                context.github = M.validate_request(request, env, dict(request))
                context.evidence, context.account = evidence, account_fixture()
                context.parent_identity = M.private_directory(parent)
                context.allocation = {"syntheticEarlierCase": True}
                context.source = {"commit": SHA, "tree": TREE, "files": {M.SCRIPT: "d" * 64}}
                context.interpreter = {"path": "/synthetic/python", "sha256": "e" * 64}
                context.foreground, context.boot = native_identity(100, 1), "SYNTHETIC_BOOT"
                context.step_end = context.job_end = context.policy_end = 1000 * M.NS
                context.case_results = [{"case": "N1", "syntheticPriorCaseOnly": True}]
                context.os_files = {}  # N2 prefix model, not qualification of N1's real OS inspections.
                native = context.native = NativeModel()
                service, child = native_identity(123, 1), native_identity(124, 123)
                native.identities = {100: context.foreground, 123: service, 124: child}
                order = []

                class Channel:
                    def __init__(self, descriptor):
                        self.descriptor = descriptor
                    def fileno(self):
                        return self.descriptor
                    def setblocking(self, value):
                        self.blocking = value
                    def close(self):
                        self.descriptor = -1

                channel, listener = Channel(71), Channel(72)
                listener.bind = lambda path: Path(path).write_bytes(b"SYNTHETIC_SOCKET_PATH_NOT_SOCKET")
                listener.listen = lambda _backlog: None
                listener.accept = lambda: (channel, None)
                administrator = types.SimpleNamespace(create=lambda: order.append("admin-create"),
                    bootstrap=lambda: order.append("bootstrap"), inspect=lambda identity: order.append("service-join") or {"pid": identity["pid"]})

                def receipt(changes, _maximum, _timeout):
                    pid = changes[0][0]
                    order.append("watch:" + str(pid))
                    return [types.SimpleNamespace(ident=pid, filter=M.EVFILT_PROC, flags=M.EV_ERROR, fflags=0,
                                                  data=13 if pid == failed_pid else 0)]

                native.kqueue = types.SimpleNamespace(control=receipt)
                original_same = native.same

                def same(identity):
                    order.append("same:" + str(identity["pid"]))
                    return original_same(identity)

                def receive(_channel, serial, binding, trace, _end, *args):
                    prepared = M.parsed((evidence / "N2/prepared.json").read_bytes())
                    if serial == 1:
                        payload = dict(service=service, account=context.account, foregroundPeer=context.foreground,
                            boot=context.boot, sourceSha256=context.source["files"][M.SCRIPT], interpreter=context.interpreter,
                            directoryIdentity=prepared["directoryIdentity"])
                    elif serial == 4:
                        payload = {"readyFrame": M.frame_value(3, binding, dict(producer=child, parent=service,
                            account=context.account, sigtermDefault=True, sigtermBlocked=False, boot=context.boot,
                            sourceSha256=context.source["files"][M.SCRIPT], interpreter=context.interpreter["path"]))}
                    else:
                        self.assertEqual(serial, 8)
                        raise M.ExperimentError("CHILD_WAIT", "STATUS_MISSING")  # Stop the exact prefix, no model acceptance.
                    value = M.frame_value(serial, binding, payload)
                    trace.append(M.frame_record(value))
                    return value

                def send(_channel, serial, binding, payload, trace, _end):
                    order.append("send:" + str(serial))
                    value = M.frame_value(serial, binding, payload)
                    trace.append(M.frame_record(value))
                    return value

                with patch.object(M, "Admin", return_value=administrator), \
                        patch.object(M.socket, "socket", return_value=listener), \
                        patch.object(M, "socket_identity", return_value=[401, 402]), \
                        patch.object(M.select, "select", side_effect=lambda readers, *_args: (readers, [], [])), \
                        patch.object(M.select, "kevent", create=True, side_effect=lambda pid, **kw: (pid, kw)), \
                        patch.object(M.time, "monotonic_ns", return_value=10 * M.NS), \
                        patch.object(native, "peer", return_value=service), patch.object(native, "same", side_effect=same), \
                        patch.object(M, "read_frame", side_effect=receive), patch.object(M, "send_frame", side_effect=send), \
                        patch.object(M, "interface_ipv4", side_effect=AssertionError("NO_N2_NETWORK")):
                    with self.assertRaises(M.ExperimentError) as raised:
                        M.perform_case(context, "N2", 180 * M.NS)
                if failed_pid is None:
                    self.assertEqual(raised.exception.stage, "CHILD_WAIT")
                    self.assertLess(order.index("watch:123"), order.index("send:2"))
                    self.assertLess(order.index("watch:124"), order.index("send:5"))
                    self.assertEqual(order[order.index("send:5") - 2:order.index("send:5")], ["same:123", "same:124"])
                    self.assertEqual(set(native.registrations), {123, 124})
                else:
                    self.assertEqual(raised.exception.stage, "ATTACH")
                    self.assertNotIn("send:5", order)
                    self.assertEqual("send:2" in order, failed_pid == 124)
                self.assertEqual(len(context.case_results), 1)
                self.assertFalse(context.finished or context.export_called)
                self.assertIsNone(context.result)

    def test_06_exact_eight_frame_total_and_seven_frame_n3_protocol(self):
        expected = ((1, "D>F", "HELLO"), (2, "F>D", "PREPARE"), (3, "P>D", "CHILD_READY"),
                    (4, "D>F", "CHILD_READY"), (5, "F>D", "START"), (6, "D>P", "START"),
                    (7, "P>D", "RESULT"), (8, "D>F", "CHILD_RESULT_AND_EXIT_READY"))
        self.assertEqual(M.FRAME_ROSTER, expected)
        for case in M.CASES:
            trace = frames(case)
            self.assertEqual(M.validate_frame_trace(case, trace), trace)
            self.assertEqual(len(trace), 7 if case == "N3" else 8)
            for bad in (trace[:-1], trace + [trace[-1]], trace[:1] + trace,
                        trace[:2] + list(reversed(trace[2:4])) + trace[4:]):
                with self.assertRaises(M.ExperimentError):
                    M.validate_frame_trace(case, bad)
        with self.assertRaises(M.ExperimentError):
            M.validate_frame_trace("N3", frames("N1"))  # No invented P RESULT for killed N3.
        for serial, _direction, _kind in expected:
            value = M.frame_value(serial, BINDING, {})
            self.assertEqual(M.validate_frame(value, serial, BINDING), {})
            for key, wrong in (("schema", True), ("serial", 9), ("binding", "d" * 64),
                               ("kind", "RETIRE"), ("payload", [])):
                with self.assertRaises(M.ExperimentError):
                    M.validate_frame({**value, key: wrong}, serial, BINDING)
            with self.assertRaises(M.ExperimentError):
                M.validate_frame({**value, "extra": True}, serial, BINDING)
        with self.assertRaises(M.ExperimentError):
            M.frame_value(1, BINDING, dict(value="x" * M.FRAME_BYTES))
        deep = None
        for _ in range(M.JSON_DEPTH + 1):
            deep = [deep]
        with self.assertRaises(M.ExperimentError):
            M.frame_value(1, BINDING, dict(value=deep))
        value = M.frame_value(1, BINDING, {})
        wire = M.struct.pack("!I", len(M.encoded(value))) + M.encoded(value)
        with patch.object(M.select, "select", side_effect=lambda readers, writers, *_: (readers, writers, [])), \
                patch.object(M, "left", return_value=1):
            outgoing, trace = ByteChannel(), []
            M.send_frame(outgoing, 1, BINDING, {}, trace, M.NS)
            self.assertEqual(bytes(outgoing.sent), wire)
            self.assertEqual(trace, [M.frame_record(value)])
            incoming, trace = ByteChannel(wire), []
            self.assertEqual(M.read_frame(incoming, 1, BINDING, trace, M.NS), value)
            M.wait_eof(incoming, M.NS)
            for malformed in (b"", wire[:2], wire[:-1], M.struct.pack("!I", M.FRAME_BYTES + 1),
                              M.struct.pack("!I", 1) + b"x"):
                with self.assertRaises(M.ExperimentError):
                    M.read_frame(ByteChannel(malformed), 1, BINDING, [], M.NS)
            with self.assertRaises(M.ExperimentError):
                M.read_frame(ByteChannel(wire), 2, BINDING, [], M.NS)
            with self.assertRaises(M.ExperimentError):
                M.wait_eof(ByteChannel(b"trailing"), M.NS)
            with self.assertRaises(M.ExperimentError):
                M.send_frame(ByteChannel(), 8, BINDING, {}, frames("N1"), M.NS)
        for ancillary, flags in (([(M.socket.SOL_SOCKET, M.socket.SCM_RIGHTS, M.struct.pack("=i", 98))], 0),
                                  ([(999, 999, b"unexpected")], 0), ([], M.socket.MSG_CTRUNC)):
            channel = types.SimpleNamespace(recvmsg=lambda *_args: (b"", ancillary, flags, None))
            with patch.object(M.os, "close") as close:
                with self.assertRaises(M.ExperimentError):
                    M.receive_bytes(channel, 1, "START")
                if ancillary and ancillary[0][1] == M.socket.SCM_RIGHTS:
                    close.assert_called_once_with(98)
                else:
                    close.assert_not_called()

    def test_07_fixed_probe_and_distinct_negative_control_outcomes(self):
        self.assertEqual(M.QUERY.hex(), "000000000001000000000000127032706b69742d61756469742d70726f6265056c6f63616c0000010001")
        self.assertEqual(len(M.QUERY), 42)
        self.assertTrue(M.validate_case_result("N1", 0, status(), probe_fixture()))
        failed = dict(probe_fixture(), result="FAIL", errno="EHOSTUNREACH", sent=0)
        self.assertFalse(M.validate_case_result("N1", 23, status(23 << 8), failed))
        no_network = dict(stage="NO_NETWORK", result="EXPECTED_FAILURE", errno="NONE", sent=0,
                          socketCreated=False, closed=False, closeError="NONE")
        self.assertTrue(M.validate_case_result("N2", 23, status(23 << 8), no_network))
        self.assertTrue(M.validate_case_result("N3", -signal.SIGTERM, status(24 << 8), None))
        self.assertTrue(M.validate_case_result("N4", 0, status(signal.SIGTERM), dict(no_network, result="NO_NETWORK")))
        self.assertFalse(all((M.validate_case_result("N1", 23, status(23 << 8), failed),
                              M.validate_case_result("N2", 23, status(23 << 8), no_network),
                              M.validate_case_result("N3", -signal.SIGTERM, status(24 << 8), None),
                              M.validate_case_result("N4", 0, status(signal.SIGTERM), dict(no_network, result="NO_NETWORK")))))
        for bad in (dict(probe_fixture(), sent=41), dict(probe_fixture(), closed=False),
                    dict(probe_fixture(), closeError="UNKNOWN"), dict(probe_fixture(), sent=True),
                    dict(probe_fixture(), errno="EHOSTUNREACH")):
            with self.assertRaises(M.ExperimentError):
                M.validate_case_result("N1", 0, status(), bad)
        for args in (("N1", 0, status(), failed), ("N2", 0, status(), no_network),
                     ("N3", 0, status(24 << 8), None), ("N3", -signal.SIGTERM, status(24 << 8), no_network),
                     ("N4", 0, status(), dict(no_network, result="NO_NETWORK"))):
            with self.assertRaises(M.ExperimentError):
                M.validate_case_result(*args)
        selected = dict(index=4, name="synthetic0", address="192.0.2.1")
        calls = []

        class Datagram:
            code, error, close_error = 42, None, None
            def __init__(self):
                self.options, self.fd = {}, 7
            def setblocking(self, value):
                calls.append(("blocking", value))
            def setsockopt(self, level, option, value):
                calls.append(("set", level, option, value))
                self.options[level, option] = value
            def getsockopt(self, level, option, *_size):
                calls.append(("get", level, option))
                return self.options[level, option]
            def bind(self, address):
                calls.append(("bind", address))
            def sendto(self, payload, address):
                calls.append(("send", payload, address))
                if self.error is not None:
                    raise self.error
                return self.code
            def close(self):
                calls.append(("close",))
                if self.close_error is not None:
                    raise self.close_error
                self.fd = -1
            def fileno(self):
                return self.fd

        with patch.object(M, "interface_ipv4", side_effect=lambda value: calls.append(("interface", value)) or value), \
                patch.object(M, "left", return_value=1), \
                patch.object(M.time, "monotonic_ns", return_value=10 * M.NS), \
                patch.object(M.socket, "inet_aton", side_effect=lambda value: M.ipaddress.IPv4Address(value).packed):
            datagram = Datagram()
            observation = {}
            with patch.object(M.socket, "socket", return_value=datagram) as factory:
                self.assertEqual(M.native_probe("N1", selected, 20 * M.NS, observation=observation), probe_fixture())
                factory.assert_called_once_with(M.socket.AF_INET, M.socket.SOCK_DGRAM)
            self.assertIs(M.validate_probe_observation(observation, probe_fixture(), "N1", 20 * M.NS), observation)
            self.assertEqual((observation["socketFd"], observation["closedFd"], observation["sendReturn"]), (7, -1, 42))
            for key, value in (("socketFd", None), ("closedFd", 7), ("sendReturn", 41),
                               ("sendFinishedMonotonicNs", 21 * M.NS), ("closeReturnedMonotonicNs", None),
                               ("finishedMonotonicNs", 20 * M.NS)):
                with self.assertRaises(M.ExperimentError):
                    M.validate_probe_observation({**observation, key: value}, probe_fixture(), "N1", 20 * M.NS)
            address = M.ipaddress.IPv4Address(selected["address"]).packed
            self.assertEqual(calls, [
                ("interface", selected), ("blocking", False),
                ("set", M.socket.SOL_SOCKET, M.socket.SO_REUSEADDR, 1),
                ("get", M.socket.SOL_SOCKET, M.socket.SO_REUSEADDR),
                ("set", M.socket.SOL_SOCKET, M.socket.SO_REUSEPORT, 1),
                ("get", M.socket.SOL_SOCKET, M.socket.SO_REUSEPORT),
                ("bind", ("0.0.0.0", 5353)),
                ("set", M.socket.IPPROTO_IP, M.socket.IP_MULTICAST_IF, address),
                ("get", M.socket.IPPROTO_IP, M.socket.IP_MULTICAST_IF),
                ("set", M.socket.IPPROTO_IP, M.socket.IP_ADD_MEMBERSHIP,
                 M.ipaddress.IPv4Address("224.0.0.251").packed + address),
                ("set", M.socket.IPPROTO_IP, M.socket.IP_MULTICAST_TTL, 255),
                ("send", M.QUERY, ("224.0.0.251", 5353)), ("close",),
            ])
            for code, error in ((41, None), (42, OSError(M.errno.EHOSTUNREACH, CANARY))):
                datagram, calls = Datagram(), []
                datagram.code, datagram.error = code, error
                with patch.object(M.socket, "socket", return_value=datagram):
                    value = M.native_probe("N1", selected, M.NS)
                self.assertEqual(value["result"], "FAIL")
                self.assertTrue(value["closed"])
                self.assertEqual(sum(row[0] == "send" for row in calls), 1)
                self.assertNotIn(CANARY, str(value))
            datagram = Datagram()
            datagram.close_error = OSError(M.errno.EINVAL, CANARY)
            with patch.object(M.socket, "socket", return_value=datagram):
                with self.assertRaises(M.ExperimentError):
                    M.native_probe("N1", selected, M.NS)
        with patch.object(M.socket, "socket", side_effect=AssertionError("NO_NEGATIVE_CASE_UDP")), \
                patch.object(M, "interface_ipv4", side_effect=AssertionError("NO_NEGATIVE_CASE_INTERFACE")):
            for case in ("N2", "N4"):
                self.assertFalse(M.native_probe(case, None, M.NS)["socketCreated"])
            with self.assertRaises(M.ExperimentError):
                M.native_probe("N3", None, M.NS)
        with patch.object(M, "interface_ipv4", side_effect=M.ExperimentError("NATIVE_SEND", "IDENTITY_CHANGED")), \
                patch.object(M.socket, "socket") as factory:
            with self.assertRaises(M.ExperimentError):
                M.native_probe("N1", selected, M.NS)
            factory.assert_not_called()

    def test_08_original_only_signal_bounds_and_unknown_closure_refusal(self):
        native, original = NativeModel(), native_identity()
        token = (ctypes.c_uint32 * 8)(*range(8))  # Explicit fake opaque observation; not native authority.
        signals = []

        def held_token(identity):
            native.same(identity)
            return token

        def observed_signal(pointer, signum):
            self.assertIs(pointer._obj, token)
            signals.append(signum)
            return 0

        native.proc = types.SimpleNamespace(proc_signal_with_audittoken=observed_signal)
        with patch.object(native, "token", side_effect=held_token), patch.object(M.time, "monotonic_ns", return_value=M.NS):
            native.signal(original, signal.SIGTERM, 40 * M.NS)
            self.assertEqual(signals, [signal.SIGTERM])
            native.identities[123] = dict(original, uniqueId=9999)
            with self.assertRaises(M.ExperimentError):
                native.signal(original, signal.SIGTERM, 40 * M.NS)
            self.assertEqual(signals, [signal.SIGTERM])
            native.identities[123] = dict(original)
            for signum, end in ((signal.SIGINT, 40 * M.NS), (signal.SIGTERM, M.NS)):
                with self.assertRaises(M.ExperimentError):
                    native.signal(original, signum, end)
            self.assertEqual(signals, [signal.SIGTERM])
            with patch.object(native.proc, "proc_signal_with_audittoken", return_value=M.errno.ESRCH) as observed:
                with self.assertRaises(M.ExperimentError):
                    native.signal(original, signal.SIGTERM, 40 * M.NS)
                observed.assert_called_once()  # No PID-only fallback or second signal on refusal.
        closed = {key: True for key in M.CLOSURE_KEYS}
        self.assertIs(M.validate_closure(closed), closed)
        for key in M.CLOSURE_KEYS:
            for value in (False, None, 1, "closed"):
                with self.assertRaises(M.ExperimentError):
                    M.validate_closure({**closed, key: value})
            with self.assertRaises(M.ExperimentError):
                M.validate_closure({name: value for name, value in closed.items() if name != key})

        class Pipe:
            def __init__(self, fd):
                self.fd, self.closed = fd, False
            def fileno(self):
                return self.fd
            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory(prefix="p2pkit-context-pipe-controls-") as temporary:
            directory = Path(temporary).resolve()
            output, error = Pipe(100), Pipe(101)
            waited = []
            process = types.SimpleNamespace(stdout=output, stderr=error, poll=lambda: 23,
                wait=lambda timeout: waited.append(timeout) or 23)
            chunks = {100: [b"synthetic child output\n", b""], 101: [b""]}
            with patch.object(M.os, "set_blocking") as blocking, \
                    patch.object(M.os, "read", side_effect=lambda fd, _size: chunks[fd].pop(0)), \
                    patch.object(M.select, "select", return_value=([], [], [])), \
                    patch.object(M, "left", return_value=1):
                pipes = M.ProbePipes(process)
                code, rows = pipes.finish(40 * M.NS, directory)
            self.assertEqual(code, 23)
            self.assertEqual(waited, [1])
            self.assertEqual(blocking.call_args_list, [unittest.mock.call(100, False), unittest.mock.call(101, False)])
            self.assertTrue(pipes.closed and output.closed and error.closed)
            self.assertEqual([row["name"] for row in rows], ["producer.stdout", "producer.stderr"])
            self.assertTrue(all(row["closed"] and row["eof"] for row in rows))
            self.assertEqual((directory / "producer.stdout").read_bytes(), b"synthetic child output\n")

            for failure in ("EOF", "WAIT", "CLOSE", "FSYNC"):
                target = directory / failure
                target.mkdir(mode=0o700)
                output, error = Pipe(100), Pipe(101)
                process = types.SimpleNamespace(stdout=output, stderr=error, poll=lambda: 23,
                                                wait=lambda timeout: 23)
                if failure == "WAIT":
                    process.wait = lambda timeout: (_ for _ in ()).throw(subprocess.TimeoutExpired("SYNTHETIC", timeout))
                if failure == "CLOSE":
                    output.close = lambda: (_ for _ in ()).throw(OSError(M.errno.EIO, CANARY))
                read = (lambda *_args: b"still open") if failure == "EOF" else (lambda *_args: b"")
                limit = [1, M.ExperimentError("CHILD_WAIT", "TIMEOUT")] if failure == "EOF" else None
                with patch.object(M.os, "set_blocking"), patch.object(M.os, "read", side_effect=read), \
                        patch.object(M.select, "select", return_value=([], [], [])), \
                        patch.object(M, "left", side_effect=limit, return_value=1), \
                        patch.object(M.os, "fsync", side_effect=OSError(M.errno.EIO, CANARY)), \
                        patch.object(M, "write_new", wraps=M.write_new) as write:
                    pipes = M.ProbePipes(process)
                    with self.assertRaises((M.ExperimentError, OSError, subprocess.TimeoutExpired)):
                        pipes.finish(40 * M.NS, target)
                self.assertFalse(pipes.closed)
                if failure != "FSYNC":
                    write.assert_not_called()
                else:
                    write.assert_called_once()

        def controlled_context(directory):
            with patch.object(M.os, "environ", {}):
                context = M.Context()
            context.evidence, context.environment = directory, {"PATH": "/usr/bin:/bin"}
            context.step_end, context.job_end, context.policy_end = 240 * M.NS, 1440 * M.NS, 1440 * M.NS
            context.account, context.foreground = account_fixture(), native_identity(os.getpid(), 1)
            context.native = NativeModel()
            sentinel_identity = native_identity(999, os.getpid())
            context.native.identities.update({os.getpid(): context.foreground, 999: sentinel_identity})
            queue = types.SimpleNamespace(closed=False, control=lambda *_args: [])
            queue.close = lambda: setattr(queue, "closed", True)
            context.native.kqueue = queue
            context.output = types.SimpleNamespace(closed=False)
            context.output.close = lambda: setattr(context.output, "closed", True)
            sentinel = types.SimpleNamespace(pid=999, stdin=Pipe(102), poll=lambda: None)
            pipes = types.SimpleNamespace(closed=False)
            pipes.finish = lambda _end, _directory: setattr(pipes, "closed", True) or (0, [])
            return context, sentinel, pipes

        with tempfile.TemporaryDirectory(prefix="p2pkit-context-suite-controls-") as temporary:
            root = Path(temporary).resolve()
            for fails in (True, False):
                directory = root / ("aborted" if fails else "closed-failure")
                directory.mkdir(mode=0o700)
                context, sentinel, pipes = controlled_context(directory)
                primary = M.ExperimentError("START", "REFUSED")
                cases = []

                def case_result(original_context, case, end_ns):
                    self.assertIs(original_context, context)
                    cases.append((case, end_ns))
                    if fails:
                        raise primary
                    (directory / case).mkdir(mode=0o700)
                    row = {"case": case, "passed": case != "N1", "closure": dict(closed, nativeClosed=False),
                           "originalServiceFinalData": {"nativeClosed": True}}
                    context.case_results.append(row)
                    return row

                with patch.object(M.time, "monotonic_ns", return_value=M.NS), \
                        patch.object(M.subprocess, "Popen", return_value=sentinel) as popen, \
                        patch.object(M, "ProbePipes", return_value=pipes), \
                        patch.object(M, "perform_case", side_effect=case_result), \
                        patch.object(context, "limit", wraps=context.limit) as limit:
                    if fails:
                        with self.assertRaises(M.ExperimentError) as raised:
                            M.run_cases(context)
                        self.assertIs(raised.exception, primary)
                        self.assertEqual(cases, [("N1", 181 * M.NS)])
                        self.assertEqual(context.abort_end, 121 * M.NS)
                        self.assertFalse(context.finished or context.export_called)
                        self.assertIsNone(context.result)
                        self.assertTrue(context.sentinel_closed and context.native.closed and context.output.closed)
                        self.assertFalse(M.parsed((directory / "aborted-no-export.json").read_bytes())["exportAllowed"])
                        M.abort_suite(context)
                        self.assertEqual(context.abort_end, 121 * M.NS)
                        self.assertEqual(limit.call_args_list, [unittest.mock.call(180), unittest.mock.call(120)])
                    else:
                        result = M.run_cases(context)
                        self.assertIs(result, context.result)
                        self.assertEqual(cases, [(case, 181 * M.NS) for case in M.CASES])
                        self.assertEqual(result["outcome"], "CLOSED_FAILURE")
                        self.assertEqual(result["originalCause"], "UNKNOWN")
                        self.assertEqual(result["releaseReadiness"], "NOT_READY")
                        self.assertFalse(result["productiveIntegrationAccepted"] or result["holdsChanged"])
                        self.assertTrue(context.finished and context.sentinel_closed and context.native.closed)
                        self.assertIsNone(context.abort_end)
                        self.assertFalse(context.export_called)
                    popen.assert_called_once()
                    self.assertEqual(popen.call_args.args[0], ["/bin/cat"])
                    self.assertEqual(popen.call_args.kwargs["env"], context.environment)

            directory = root / "owned-abort"
            directory.mkdir(mode=0o700)
            context, sentinel, pipes = controlled_context(directory)
            context.sentinel, context.sentinel_pipes = sentinel, pipes
            context.sentinel_identity = context.native.identity(999)
            service, producer = native_identity(), native_identity(124, 123)
            context.native.watched = {123: service, 124: producer}
            event_returns = iter(([], [types.SimpleNamespace(**event_fixture(signal.SIGTERM, 124)),
                                      types.SimpleNamespace(**event_fixture(24 << 8, 123))]))
            context.native.kqueue.control = lambda *_args: next(event_returns)
            administrator = types.SimpleNamespace(service=service, retired=False, removed=False, closed=False, end_ns=0)
            retirement = []
            administrator.retire = lambda identity: retirement.append(identity) or setattr(administrator, "retired", True)
            administrator.close = lambda: setattr(administrator, "closed", True)
            context.current = dict(channel=None, listener=None, producer=producer, service=service,
                                   prepareSent=True, admin=administrator, socket=None, directory=directory)
            signals = []
            with patch.object(M.time, "monotonic_ns", return_value=M.NS), \
                    patch.object(context.native, "signal", side_effect=lambda identity, signum, end:
                                 signals.append((identity, signum, end))):
                M.abort_suite(context)
            self.assertEqual(signals, [(producer, signal.SIGTERM, 121 * M.NS),
                                      (service, signal.SIGTERM, 121 * M.NS)])
            self.assertTrue(all(identity["pid"] != 999 for identity, _signal, _end in signals))
            self.assertEqual(retirement, [service])
            self.assertEqual(administrator.end_ns, context.abort_end)
            self.assertTrue(administrator.closed and context.sentinel_closed and context.native.closed)
            self.assertFalse(context.finished or context.export_called)
            self.assertIsNone(context.result)

    def test_09_one_original_recipient_export_return_and_command_close(self):
        module = ast.parse(SOURCE.read_text())
        validations = [node for node in ast.walk(module) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Attribute) and node.func.attr == "validate_recipient"]
        self.assertEqual(len(validations), 1)  # Only original prepare; no worker/guard revalidation.
        with tempfile.TemporaryDirectory(prefix="p2pkit-context-export-controls-") as temporary:
            root = Path(temporary).resolve()
            for outcome in ("SUCCESS", "CLOSED_FAILURE"):
                with self._export_model(root / outcome, outcome) as (context, ledger, _env, _clock):
                    seal = M.finish_export(context, context.result)
                    self.assertEqual(seal["outcome"], outcome)
                    self.assertTrue(context.export_called and context.output.closed)
                    context.exporter.export_encrypted.assert_called_once()
                    context.exporter.validate_recipient.assert_called_once()
                    self.assertIs(context.exporter.export_encrypted.call_args.args[2], context.recipient_original)
                    self.assertLess(ledger.index("freeze-return"), ledger.index("export-enter"))
                    self.assertLess(ledger.index("export-return"), ledger.index("write:export-return.json"))
                    self.assertLess(ledger.index("write:export-return.json"), ledger.index("output-enter"))
                    self.assertLess(ledger.index("output-close-return"), ledger.index("write:step-return.json"))
                    original_seal = M.parsed((context.parent / "export-return.json").read_bytes())
                    self.assertEqual(original_seal, seal)
                    step = M.parsed((context.parent / "step-return.json").read_bytes())
                    self.assertTrue(step["outputCloseReturned"] and step["commandFile"]["closed"])
                    self.assertEqual(step["intendedExitCode"], 0 if outcome == "SUCCESS" else 1)
                    self.assertEqual(step["sealSha256"], M.digest(M.encoded(seal)))
                    self.assertEqual({path.name for path in (context.parent / "outputs/encrypted").iterdir()},
                                     {"manifest.json", "evidence.tar.gz.gpg"})
                    with self.assertRaises(M.ExperimentError):
                        M.finish_export(context, context.result)
                    context.exporter.export_encrypted.assert_called_once()

            with self._export_model(root / "early-refusals") as (context, _ledger, _env, _clock):
                for target, attribute, changed in (
                    (context, "finished", False), (context, "current", object()), (context, "abort_end", M.NS),
                    (context, "sentinel_closed", False), (context.sentinel_pipes, "closed", False),
                    (context.native, "closed", False), (context, "export_called", True),
                    (context, "recipient", copy.copy(context.recipient)),
                ):
                    original = getattr(target, attribute)
                    setattr(target, attribute, changed)
                    with self.assertRaises(M.ExperimentError):
                        M.finish_export(context, context.result)
                    setattr(target, attribute, original)
                with self.assertRaises(M.ExperimentError):
                    M.finish_export(context, dict(context.result))
                for key in M.CLOSURE_KEYS:
                    context.case_results[0]["closure"][key] = False
                    with self.assertRaises(M.ExperimentError):
                        M.finish_export(context, context.result)
                    context.case_results[0]["closure"][key] = True
                context.result["cases"] = list(context.case_results)
                with self.assertRaises(M.ExperimentError):
                    M.finish_export(context, context.result)
                context.result["cases"] = context.case_results
                with patch.object(M, "_UNCLOSED_COMMANDS", [object()]):
                    with self.assertRaises(M.ExperimentError):
                        M.finish_export(context, context.result)
                context.exporter.export_encrypted.assert_not_called()
                self.assertFalse((context.parent / "export-return.json").exists())
                self.assertFalse((context.parent / "step-return.json").exists())

            with self._export_model(root / "recheck-refusals") as (context, _ledger, _env, _clock):
                for manager in (
                    patch.object(M, "source_snapshot", return_value={"changed": True}),
                    patch.object(M, "checked_interpreter", return_value={"changed": True}),
                    patch.object(M, "original_request", side_effect=M.ExperimentError("SOURCE", "REFUSED")),
                    patch.object(M, "validate_policy", side_effect=M.ExperimentError("POLICY", "IDENTITY_CHANGED")),
                    patch.object(M.time, "time_ns", return_value=M.POLICY_EXPIRES * M.NS),
                ):
                    with manager:
                        with self.assertRaises(M.ExperimentError):
                            M.finish_export(context, context.result)
                context.recipient_files["recipient.asc"]["sha256"] = "a" * 64
                with self.assertRaises(M.ExperimentError):
                    M.finish_export(context, context.result)
                context.exporter.export_encrypted.assert_not_called()
                self.assertFalse((context.parent / "export-return.json").exists())

            with self._export_model(root / "export-cleanup-failure") as (context, _ledger, _env, _clock):
                original = context.exporter.export_encrypted.side_effect

                def failed_cleanup(*args, **kwargs):
                    original(*args, **kwargs)  # Output files can exist before actual public-call cleanup.
                    raise OSError(M.errno.EIO, CANARY)

                context.exporter.export_encrypted.side_effect = failed_cleanup
                with self.assertRaises(M.ExperimentError):
                    M.finish_export(context, context.result)
                self.assertTrue((context.parent / "outputs/encrypted/manifest.json").is_file())
                self.assertTrue(context.export_called)
                self.assertFalse((context.parent / "export-return.json").exists())
                self.assertFalse((context.parent / "step-return.json").exists())
                self.assertEqual((context.parent / "original-command").read_bytes(), b"")
                with self.assertRaises(M.ExperimentError):
                    M.finish_export(context, context.result)
                context.exporter.export_encrypted.assert_called_once()

            for kind in ("replaced-command", "command-close-failure"):
                with self._export_model(root / kind, "CLOSED_FAILURE") as (context, _ledger, _env, _clock):
                    if kind == "replaced-command":
                        context.output.path.rename(context.parent / "held-original-command")
                        M.write_new(context.output.path, b"")
                        manager = contextlib.nullcontext()
                    else:
                        manager = patch.object(context.output, "close", side_effect=OSError(M.errno.EIO, CANARY))
                    with manager:
                        with self.assertRaises(M.ExperimentError):
                            M.finish_export(context, context.result)
                    self.assertTrue((context.parent / "export-return.json").is_file())
                    self.assertFalse((context.parent / "step-return.json").exists())
                    context.exporter.export_encrypted.assert_called_once()

    def test_10_exclusive_original_outcome_seal_and_public_error_containment(self):
        for outcome, step in (("SUCCESS", "success"), ("CLOSED_FAILURE", "failure")):
            seal = dict(scope=M.SCOPE, outcome=outcome, source=SHA, sourceTree=TREE, runId="123", runAttempt="1")
            digest = M.digest(M.encoded(seal))
            env = dict(P2PKIT_CONTEXT_STEP_OUTCOME=step,
                       P2PKIT_CONTEXT_SUCCESS_SHA256=digest if outcome == "SUCCESS" else "",
                       P2PKIT_CONTEXT_CLOSED_FAILURE_SHA256=digest if outcome == "CLOSED_FAILURE" else "")
            self.assertEqual(M.validate_upload_binding(seal, env), digest)
            for changed in ({**env, "P2PKIT_CONTEXT_STEP_OUTCOME": "skipped"},
                            {**env, "P2PKIT_CONTEXT_STEP_OUTCOME": "failure" if step == "success" else "success"},
                            {**env, "P2PKIT_CONTEXT_SUCCESS_SHA256": digest, "P2PKIT_CONTEXT_CLOSED_FAILURE_SHA256": digest},
                            {**env, "P2PKIT_CONTEXT_SUCCESS_SHA256": "", "P2PKIT_CONTEXT_CLOSED_FAILURE_SHA256": ""}):
                with self.assertRaises(M.ExperimentError):
                    M.validate_upload_binding(seal, changed)
            with self.assertRaises(M.ExperimentError):
                M.validate_upload_binding({**seal, "runAttempt": "2"}, env)
        for outcome, step in (("SUCCESS", "success"), ("CLOSED_FAILURE", "failure")):
            values = {
                "steps.experiment.outcome": step, "steps.experiment.outputs.outcome": outcome,
                "steps.experiment.outputs.successSha256": BINDING if outcome == "SUCCESS" else "",
                "steps.experiment.outputs.closedFailureSha256": BINDING if outcome == "CLOSED_FAILURE" else "",
                "steps.before_upload.outcome": "success", "steps.before_upload.outputs.uploadAllowed": BINDING,
                "steps.encrypted.outcome": "success",
            }
            self.assertEqual(workflow_conditions(values), [True, True, True])
            self.assertEqual(workflow_conditions(values, cancelled=True), [False, False, False])
            for changed in ({**values, "steps.experiment.outcome": "skipped"},
                            {**values, "steps.experiment.outputs.outcome": "OTHER"},
                            {**values, "steps.experiment.outputs.successSha256": BINDING,
                             "steps.experiment.outputs.closedFailureSha256": BINDING},
                            {**values, "steps.experiment.outputs.successSha256": "",
                             "steps.experiment.outputs.closedFailureSha256": ""}):
                self.assertEqual(workflow_conditions(changed), [False, False, False])
            for guard in ("failure", "skipped", "cancelled"):
                self.assertEqual(workflow_conditions({**values, "steps.before_upload.outcome": guard}),
                                 [True, False, False])
            for changed in ({**values, "steps.before_upload.outputs.uploadAllowed": ""},
                            {**values, "steps.before_upload.outputs.uploadAllowed": "d" * 64}):
                self.assertEqual(workflow_conditions(changed), [True, False, False])
            self.assertEqual(workflow_conditions({**values, "steps.encrypted.outcome": "failure"}),
                             [True, True, False])
        for error in (RuntimeError(CANARY), M.ExperimentError(CANARY, CANARY, CANARY),
                      M.ExperimentError("NATIVE_SEND", "RETURN_FAILED", "EHOSTUNREACH")):
            public = M.public_error(error)
            self.assertNotIn(CANARY, public)
            fields = public.split("|")
            self.assertEqual(len(fields), 4)
            self.assertEqual(fields[0], "P2PKIT_CONTEXT_FAILURE")
            self.assertIn(fields[1], M.STAGES)
            self.assertIn(fields[2], M.REASONS)
            self.assertIn(fields[3], M.ERRNOS)
        with tempfile.TemporaryDirectory(prefix="p2pkit-context-upload-controls-") as temporary:
            root = Path(temporary).resolve()
            for outcome, step_outcome in (("SUCCESS", "success"), ("CLOSED_FAILURE", "failure")):
                with self._export_model(root / outcome, outcome) as (context, _ledger, env, clock):
                    seal = M.finish_export(context, context.result)
                    seal_hash = M.digest(M.encoded(seal))
                    env.update(P2PKIT_CONTEXT_STEP_OUTCOME=step_outcome,
                               P2PKIT_CONTEXT_SUCCESS_SHA256=seal_hash if outcome == "SUCCESS" else "",
                               P2PKIT_CONTEXT_CLOSED_FAILURE_SHA256=seal_hash if outcome == "CLOSED_FAILURE" else "")
                    before_command = context.parent / "before-command"
                    M.write_new(before_command, b"")
                    env["GITHUB_OUTPUT"] = str(before_command)
                    clock["ns"] = 11 * M.NS
                    self.assertEqual(M.upload_guard(), 0)
                    self.assertEqual(before_command.read_bytes(), ("uploadAllowed=" + seal_hash + "\n").encode("ascii"))
                    before = M.parsed((context.parent / "before-upload.json").read_bytes())
                    self.assertTrue(before["outsideCiphertext"] and before["commandFile"]["closed"])
                    env.update(P2PKIT_CONTEXT_UPLOAD_ALLOWED=seal_hash, P2PKIT_CONTEXT_UPLOAD_OUTCOME="success",
                               P2PKIT_CONTEXT_ARTIFACT_ID="456", P2PKIT_CONTEXT_ARTIFACT_DIGEST="f" * 64)
                    clock["ns"] = 12 * M.NS
                    self.assertEqual(M.upload_guard(after=True), 0)
                    after = M.parsed((context.parent / "after-upload.json").read_bytes())
                    self.assertEqual(after["retentionDays"], 14)
                    self.assertEqual(after["github"], context.github)
                    self.assertTrue(after["outsideCiphertext"] and after["remoteReadbackRequired"])
                    self.assertEqual(after["artifact"], {"artifactId": "456", "artifactDigest": "f" * 64})
                    context.exporter.validate_recipient.assert_called_once()
                    context.exporter.export_encrypted.assert_called_once()

                    for key, changed in (("P2PKIT_CONTEXT_STEP_OUTCOME", "skipped"),
                                         ("P2PKIT_CONTEXT_UPLOAD_ALLOWED", "d" * 64),
                                         ("P2PKIT_CONTEXT_UPLOAD_OUTCOME", "failure"),
                                         ("P2PKIT_CONTEXT_ARTIFACT_ID", ""), ("P2PKIT_CONTEXT_ARTIFACT_ID", "0"),
                                         ("P2PKIT_CONTEXT_ARTIFACT_ID", True),
                                         ("P2PKIT_CONTEXT_ARTIFACT_DIGEST", "F" * 64),
                                         ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_SHA", "d" * 40)):
                        original = env[key]
                        env[key] = changed
                        with patch.object(M, "write_new") as write:
                            with self.assertRaises(M.ExperimentError):
                                M.upload_guard(after=True)
                            write.assert_not_called()
                        env[key] = original
                    # Numeric DATA alone is intentionally NOT remote attestation.
                    self.assertEqual(M.validate_artifact_return({**env, "P2PKIT_CONTEXT_ARTIFACT_ID": "99999999999"}, seal_hash)
                                     ["artifactId"], "99999999999")
                    self.assertTrue(after["remoteReadbackRequired"])
                    step_path = context.parent / "step-return.json"
                    original_step = step_path.read_bytes()
                    changed = M.parsed(original_step)
                    changed["outputCloseReturned"] = False
                    step_path.write_bytes(M.encoded(changed))
                    with patch.object(M, "write_new") as write:
                        with self.assertRaises(M.ExperimentError):
                            M.upload_guard(after=True)
                        write.assert_not_called()
                    step_path.write_bytes(original_step)
                    extra = context.parent / "outputs/encrypted/unauthorized-plaintext.txt"
                    M.write_new(extra, CANARY.encode("ascii"))
                    with patch.object(M, "write_new") as write:
                        with self.assertRaises(M.ExperimentError):
                            M.upload_guard(after=True)
                        write.assert_not_called()
                    extra.unlink()
                    cipher = context.parent / "outputs/encrypted/evidence.tar.gz.gpg"
                    cipher.write_bytes(b"changed synthetic bytes")
                    with patch.object(M, "write_new") as write:
                        with self.assertRaises(M.ExperimentError):
                            M.upload_guard(after=True)
                        write.assert_not_called()

    def test_11_scope_original_source_policy_and_unexpanded_budgets(self):
        unchanged = {
            "AGENTS.md": "3ca3ef11f49ba90152754fb9d884ed353a5bc549b0ab648e182d889d4283d84b",
            "CLAUDE.md": "0fd0e8bdd297e16caabc40e87411c377f674769a40b73a35f43818bf9f97a71d",
            ".github/workflows/dependency-update-candidate.yml": "0d01d62e7693a6f6d13ac469400aacfcce13ce6aa68cc86378fde2870b34cc1a",
            ".github/workflows/release-foundation-checks.yml": "6d45a5ea496f25847ce261d8f0d67af0d87c8573bb8d05456839701f20e185cc",
            ".github/test-evidence-recipient.json": "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521",
            "scripts/run-hosted-dependency-update.py": "32373f3cce722d2e9932e1b5ce2375dd734ec699ca2d6c55c70724682cbea6ce",
            "scripts/audit_processes.py": "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13",
            "scripts/run-audit-command.py": "04e921eb5ba1e715078d9b315e366cc8f970151c9c1e5e0a4e5dfae0f0ed1ccc",
            "scripts/hosted_evidence.py": "fb45dd548474a003e5aaec0a3a3391c7e06034ab51e74688292ff2f583978ea8",
        }
        for name, expected in unchanged.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        old = ast.parse((ROOT / "scripts/run-hosted-dependency-update.py").read_text())
        old_keys = [node.value for node in old.body if isinstance(node, ast.Assign) and
                    any(isinstance(target, ast.Name) and target.id == "REQUEST_KEYS" for target in node.targets)]
        self.assertEqual(ast.literal_eval(old_keys[0]),
                         {"controller_sha", "controller_tree", "candidate_sha", "candidate_tree", "dependency_base_sha"})
        self.assertEqual(M.REQUEST_KEYS, {"source_sha", "source_tree"})
        self.assertEqual((M.JOB_SECONDS, M.STEP_SECONDS, M.PREPARE_SECONDS, M.NATIVE_SECONDS, M.CASE_SECONDS,
                          M.ABORT_SECONDS, M.FREEZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS, M.ADMIN_SECONDS),
                         (1440, 720, 120, 180, 40, 120, 60, 120, 420, 10))
        self.assertEqual((M.FRAME_BYTES, M.STREAM_BYTES, M.EVIDENCE_BYTES, M.EVIDENCE_MEMBERS),
                         (16384, 65536, 2 * 1024 * 1024, 128))
        self.assertEqual(M.POLICY_SHA256, unchanged[".github/test-evidence-recipient.json"])
        self.assertEqual(M.POLICY_EXPIRES, 1791158400)
        self.assertEqual(M.LATEST_ENTRY, "2026-10-04T20:30:00Z")
        workflow = WORKFLOW.read_text()
        jobs = workflow.split("\njobs:\n", 1)[1]
        self.assertEqual(re.findall(r"^  ([a-z][a-z0-9_]*):$", jobs, re.MULTILINE), ["context_experiment"])
        self.assertIn("github.event_name == 'workflow_dispatch'", jobs)
        self.assertIn("github.repository == 'p2pKit/P2pKit'", jobs)
        self.assertIn("github.actor_id == '104788132'", jobs)
        self.assertIn("runs-on: macos-26", jobs)
        self.assertIn("timeout-minutes: 24", jobs)
        self.assertIn("group: p2pkit-nonphysical-heavy", jobs)
        self.assertIn("cancel-in-progress: false", jobs)
        self.assertEqual(workflow.count("uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"), 1)
        self.assertEqual(workflow.count("uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"), 1)
        self.assertIn("retention-days: 14", workflow)
        self.assertIn("overwrite: false", workflow)
        self.assertIn("include-hidden-files: false", workflow)
        self.assertIn("steps.before_upload.outcome == 'success'", workflow)
        self.assertIn("steps.experiment.outputs.closedFailureSha256 == ''", workflow)
        self.assertIn("steps.experiment.outputs.successSha256 == ''", workflow)
        self.assertNotIn("always()", workflow)
        for forbidden in ("setup-java", "setup-node", "gradlew", "xcodebuild", "sdkmanager", "brew install", "pip install",
                          "secrets.", "environment:", "contents: write", "pull_request_target", "workflow_run"):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise SystemExit("FIXED_OFFLINE_CONTROL_INVOCATION_REQUIRED")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Focused)
    if suite.countTestCases() != 11:
        raise SystemExit("FIXED_ELEVEN_FAMILY_ROSTER_REQUIRED")
    run = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if run.wasSuccessful() else 1)
