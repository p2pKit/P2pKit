#!/usr/bin/env python3
"""Six bounded offline SOURCE-site controls; no native or custody acceptance.

All observations below are synthetic DATA. Real process, socket, native-library,
ownership and environment actions are forbidden. Authored without execution.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-source-sites-test.py
"""
import ast
import contextlib
import copy
import ctypes  # Load the standard module before forbidding native acquisition.
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
SHA, TREE, CANARY = "a" * 40, "b" * 40, "SYNTHETIC_PRIVATE_CANARY"
FAILURE = "P2PKIT_CONTEXT_FAILURE|SOURCE|IDENTITY_CHANGED|NONE"
PREFIX = "P2PKIT_CONTEXT_SOURCE_SITE|"


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid", "os.chown",
    }:
        raise AssertionError("OFFLINE_SOURCE_SITE_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_SOURCE_SITE_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_source_site_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)

# Independent transcription of the sixteen original 3d7786c6 guard groups.
# Only four groups are split. This table is not derived from the new constants.
GROUPS = (
    ("validate_request", ("REQUEST_EVENT",)),
    ("validate_request", ("REQUEST_SOURCE",)),
    ("source_snapshot", ("SOURCE_STATUS",)),
    ("source_snapshot", ("SOURCE_OBJECTS",)),
    ("file_pin", ("PIN_TYPE", "PIN_OWNER", "PIN_NLINK", "PIN_MODE", "PIN_SIZE", "PIN_EXECUTABLE")),
    ("file_pin", ("PIN_READ_SIZE", "PIN_FD_STABLE", "PIN_PATH_STABLE")),
    ("checked_interpreter", ("PYTHON_PARENT_TYPE", "PYTHON_PARENT_OWNER", "PYTHON_PARENT_MODE")),
    ("validate_prepared", ("PREPARED_SOURCE",)),
    ("validate_prepared", ("PREPARED_RUN",)),
    ("original_request", ("ORIGINAL_SOURCE_PATHS",)),
    ("prepare", ("CHECKOUT_SOURCE",)),
    ("prepare", ("OS_OWNER", "OS_MODE", "OS_TYPE")),
    ("perform_case", ("OS_FIRST_IDENTITY",)),
    ("perform_case", ("OS_NEXT_IDENTITY",)),
    ("finish_export", ("FREEZE_SOURCE",)),
    ("upload_guard", ("UPLOAD_SOURCE",)),
)
OS_ITEMS = {
    "/": "ROOT", "/private": "PRIVATE", "/private/var": "PRIVATE_VAR", "/private/var/db": "PRIVATE_VAR_DB",
    "/usr": "USR", "/usr/bin": "USR_BIN", "/bin": "BIN",
    "/usr/bin/sudo": "SUDO", "/usr/bin/mktemp": "MKTEMP", "/usr/bin/stat": "STAT", "/usr/bin/tee": "TEE",
    "/bin/cat": "CAT", "/bin/ls": "LS", "/bin/rm": "RM", "/bin/rmdir": "RMDIR",
    "/bin/launchctl": "LAUNCHCTL", "/usr/bin/git": "GIT", "/usr/bin/sw_vers": "SW_VERS",
}
OS_SITES = {"OS_OWNER", "OS_MODE", "OS_TYPE", "OS_FIRST_IDENTITY", "OS_NEXT_IDENTITY"}
CONDITIONS = {
    "REQUEST_EVENT": 'type(event_inputs) is dict and event_inputs == request',
    "REQUEST_SOURCE": 'env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == request["source_sha"] and '
                      'env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref',
    "SOURCE_STATUS": 'not rows[2]',
    "SOURCE_OBJECTS": 'SHA.fullmatch(commit) and SHA.fullmatch(tree)',
    "PIN_TYPE": 'stat.S_ISREG(before.st_mode)',
    "PIN_OWNER": 'before.st_uid in allowed_owners',
    "PIN_NLINK": 'before.st_nlink == 1',
    "PIN_MODE": 'not before.st_mode & 0o022',
    "PIN_SIZE": '0 <= before.st_size <= maximum',
    "PIN_EXECUTABLE": 'not executable or os.access(path, os.X_OK)',
    "PIN_READ_SIZE": 'size == before.st_size',
    "PIN_FD_STABLE": 'before_stamp == handle_stamp',
    "PIN_PATH_STABLE": 'handle_stamp == stamp(path.lstat())',
    "PYTHON_PARENT_TYPE": 'stat.S_ISDIR(info.st_mode)',
    "PYTHON_PARENT_OWNER": 'info.st_uid in (0, os.getuid())',
    "PYTHON_PARENT_MODE": 'not info.st_mode & 0o022',
    "PREPARED_SOURCE": 'type(source) is dict and set(source) == {"commit", "tree", "files"} and '
                       'source["commit"] == value["github"]["source"] and '
                       'source["tree"] == value["github"]["sourceTree"] and '
                       'source["files"][SCRIPT] == digest(read_file(ROOT / SCRIPT, EVIDENCE_BYTES))',
    "PREPARED_RUN": 'value["github"]["workflow"] == WORKFLOW and value["github"]["job"] == "context_experiment" and '
                    'value["github"]["repository"] == REPOSITORY and '
                    'value["allocation"]["runId"] == value["github"]["runId"] and '
                    'value["allocation"]["runAttempt"] == value["github"]["runAttempt"]',
    "ORIGINAL_SOURCE_PATHS": 'physical(Path(__file__)) == ROOT / SCRIPT and '
                             'physical(env["GITHUB_WORKSPACE"]) / "controller" == ROOT',
    "CHECKOUT_SOURCE": 'context.source["commit"] == context.request["source_sha"] and '
                       'context.source["tree"] == context.request["source_tree"]',
    "OS_OWNER": 'info.st_uid == 0',
    "OS_MODE": 'not info.st_mode & 0o022',
    "OS_TYPE": 'stat.S_ISDIR(info.st_mode) if name in OS_PARENTS else stat.S_ISREG(info.st_mode)',
    "OS_FIRST_IDENTITY": '[observed[key] for key in ("dev", "ino", "mode", "uid", "gid")] == context.os_files[name]',
    "OS_NEXT_IDENTITY": '[info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] == original',
    "FREEZE_SOURCE": 'request == context.request and github == context.github and account() == context.account and '
                     'private_directory(context.parent) == context.parent_identity and '
                     'source_snapshot(freeze_end, context.environment) == context.source and '
                     'checked_interpreter(freeze_end) == context.interpreter',
    "UPLOAD_SOURCE": 'account() == seal["account"] and '
                     'source_snapshot(end, child_environment(parent)) == seal["source"]',
}
OTHER_SOURCE = (
    ("validate_request", "REFUSED", 'type(request) is dict and set(request) == REQUEST_KEYS and '
     'all(type(value) is str and SHA.fullmatch(value) for value in request.values())'),
    ("validate_request", "REFUSED", 'env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and '
     'env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and '
     'env.get("GITHUB_JOB") == "context_experiment" and env.get("GITHUB_ACTOR") == OWNER and '
     'env.get("GITHUB_ACTOR_ID") == OWNER_ID and env.get("GITHUB_TRIGGERING_ACTOR") == OWNER'),
    ("validate_request", "REFUSED", 'type(ref) is str and REF.fullmatch(ref)'),
    ("validate_request", "REFUSED", 'all(type(env.get(key)) is str and NUMBER.fullmatch(env[key]) '
     'for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"))'),
    ("source_snapshot", "RETURN_FAILED", 'result["code"] == 0 and not result["stderr"]'),
    ("file_pin", "BOUND", 'size <= maximum'),
    ("original_request", "UNSUPPORTED", 'sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and '
     'platform.system() == "Darwin" and platform.machine() == "arm64" and '
     'env.get("RUNNER_OS") == "macOS" and env.get("RUNNER_ARCH") == "ARM64"'),
    ("original_request", "REFUSED", 'not any(key.startswith("DYLD_") or key in '
     '("PYTHONPATH", "PYTHONHOME", "LD_PRELOAD") for key in env)'),
    ("original_request", "REFUSED", 'type(event) is dict and "inputs" in event'),
    ("prepare", "UNSUPPORTED", 'version["code"] == 0 and version["stderr"] == b"" and '
     r're.fullmatch(rb"26\.[0-9]+(?:\.[0-9]+)?\n", version["stdout"])'),
)


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


def stat_fixture(**changes):
    return types.SimpleNamespace(**{
        "st_dev": 1, "st_ino": 2, "st_mode": stat.S_IFREG | 0o600, "st_uid": 501, "st_gid": 20,
        "st_nlink": 1, "st_size": 4, "st_mtime_ns": 10, "st_ctime_ns": 20, **changes,
    })


def expression(value):
    return ast.dump(ast.parse(value, mode="eval").body, include_attributes=False)


def function_text(source, name):
    lines = source.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith("def " + name + "("))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(("def ", "class ", "@"))), len(lines))
    return "".join(lines[start:end]).rstrip() + "\n"


class SourceSites(unittest.TestCase):
    def _assert_site(self, error, site, item="NONE"):
        self.assertIsInstance(error, M.ExperimentError)
        self.assertEqual(M.public_error(error), FAILURE)
        self.assertEqual(M.public_source_site(error), PREFIX + site + "|" + item)

    def _refusal(self, callback, site, item="NONE"):
        with self.assertRaises(M.ExperimentError) as raised:
            callback()
        self._assert_site(raised.exception, site, item)
        return raised.exception

    def _pin_model(self, *, before=None, final_fd=None, final_path=None, raw=b"DATA", maximum=8,
                   executable=False, access=True):
        initial = stat_fixture(**({} if before is None else before))
        held = stat_fixture(**{**vars(initial), **({} if final_fd is None else final_fd)})
        named = stat_fixture(**{**vars(held), **({} if final_path is None else final_path)})
        observations = []

        class Handle:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                observations.append("close")

            def fileno(self):
                return 41

            def read(self, size):
                self_test.assertEqual(size, 64 * 1024)
                observations.append("read")
                return next(chunks)

        class Named:
            def __str__(self):
                return "/synthetic/" + CANARY

            def lstat(self):
                observations.append("lstat")
                return named

        self_test, chunks, stats = self, iter([raw, b""] if raw else [b""]), iter((initial, held))
        handle, path = Handle(), Named()

        def fstat(fd):
            self.assertEqual(fd, 41)
            observations.append("fstat")
            return next(stats)

        def accessible(actual, mode):
            self.assertIs(actual, path)
            self.assertEqual(mode, os.X_OK)
            observations.append("access")
            return access

        value, error = None, None
        with patch.object(M, "physical", return_value=path), patch.object(M.os, "open", return_value=41), \
                patch.object(M.os, "fdopen", return_value=handle), patch.object(M.os, "fstat", side_effect=fstat), \
                patch.object(M.os, "access", side_effect=accessible), patch.object(M.time, "monotonic_ns", return_value=0):
            try:
                value = M.file_pin("/synthetic/input", maximum, M.NS, owners=(501,), executable=executable)
            except M.ExperimentError as caught:
                error = caught
        return value, error, observations

    def _interpreter_model(self, changed=None):
        observations = []
        parents = ("/synthetic/parent", "/synthetic")
        resolved = types.SimpleNamespace(parents=parents)
        original = types.SimpleNamespace(resolve=Mock(return_value=resolved))
        value, error, pinned = None, None, object()

        def physical(parent):
            def lstat():
                observations.append(parent)
                return stat_fixture(**{"st_mode": stat.S_IFDIR | 0o755, "st_uid": 0,
                                       **({} if changed is None else changed)})
            return types.SimpleNamespace(lstat=lstat)

        with patch.object(M, "Path", return_value=original), patch.object(M, "safe_component_path"), \
                patch.object(M, "physical", side_effect=physical), patch.object(M.os, "getuid", return_value=501) as uid, \
                patch.object(M, "file_pin", return_value=pinned) as pin:
            try:
                value = M.checked_interpreter(M.NS)
            except M.ExperimentError as caught:
                error = caught
            uid_count = uid.call_count
        original.resolve.assert_called_once_with(strict=True)
        return value, error, observations, uid_count, pin, resolved, pinned

    def _prepare_source_model(self, *, changed=None, source=None):
        """Real tiny owned preparation files; fake only observation boundaries.

        The valid SOURCE path stops at a fake Darwin-constructor boundary, before
        any native identity, recipient, policy/key helper or export operation.
        """
        request, env = request_fixture()
        github = M.validate_request(request, env, request)
        epoch = (M.POLICY_EXPIRES - 86400) * M.NS
        allocation = dict(schema=1, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",
                          startedMonotonicNs=M.NS, startedEpochNs=epoch)
        observed, boundary = [], M.ExperimentError("IDENTITY", "REFUSED")
        with tempfile.TemporaryDirectory(prefix="cs-") as temporary:
            parent = Path(temporary).resolve()
            parent.chmod(0o700)
            (parent / "allocation.json").write_bytes(M.encoded(allocation))
            identity, real_physical = M.private_directory(parent), M.physical

            def physical(value):
                if type(value) is str and value in OS_ITEMS:
                    def lstat():
                        observed.append(value)
                        mode = (stat.S_IFDIR if value in M.OS_PARENTS else stat.S_IFREG) | 0o755
                        return stat_fixture(**{"st_mode": mode, "st_uid": 0,
                                               **({} if changed is None else changed.get(value, {}))})
                    return types.SimpleNamespace(lstat=lstat)
                return real_physical(value)

            output = types.SimpleNamespace(close=Mock())
            with patch.object(M.os, "environ", env), patch.object(M.time, "monotonic_ns", return_value=10 * M.NS), \
                    patch.object(M.time, "time_ns", return_value=epoch + 9 * M.NS), \
                    patch.object(M, "original_request", return_value=(request, github)), \
                    patch.object(M, "account", side_effect=account_fixture), \
                    patch.object(M, "operation_paths", return_value=(parent, identity)), \
                    patch.object(M, "CommandFile", return_value=output), \
                    patch.object(M, "child_environment", return_value={"PATH": "/usr/bin:/bin"}), \
                    patch.object(M, "source_snapshot", return_value=source if source is not None else
                                 {"commit": SHA, "tree": TREE, "files": {}}), \
                    patch.object(M, "checked_interpreter", return_value={"synthetic": True}) as interpreter, \
                    patch.object(M, "physical", side_effect=physical), \
                    patch.object(M, "capture_fixed", return_value={"code": 0, "stderr": b"", "stdout": b"26.1\n"}) as version, \
                    patch.object(M, "Darwin", side_effect=boundary) as native, \
                    patch.object(M, "load_module") as loader, patch.object(M, "write_new") as write:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.prepare()
                loader.assert_not_called()
                write.assert_not_called()
                output.close.assert_called_once_with()
                counts = (interpreter.call_count, version.call_count, native.call_count)
        return raised.exception, observed, counts, boundary

    def test_01_original_guard_coverage_and_conditions(self):
        source = SOURCE.read_text()
        tree = ast.parse(source)
        sites = [site for _name, group in GROUPS for site in group]
        self.assertEqual((len(GROUPS), len(sites), len(set(sites))), (16, 27, 27))
        self.assertEqual(M.SOURCE_SITES, frozenset(sites))
        self.assertEqual(M.SOURCE_OS_SITES, frozenset(OS_SITES))
        self.assertEqual(M.SOURCE_OS_ITEMS, OS_ITEMS)
        self.assertEqual(tuple(OS_ITEMS), (*M.OS_PARENTS, *M.OS_TOOLS))
        self.assertEqual(len(set(OS_ITEMS.values())), 18)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        found, other = {}, []
        for name, function in functions.items():
            for node in sorted(ast.walk(function), key=lambda item: getattr(item, "lineno", 0)):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "require":
                    continue
                if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant) or node.args[1].value != "SOURCE":
                    continue
                reason = node.args[2].value if len(node.args) > 2 else "REFUSED"
                keywords = {item.arg: item.value for item in node.keywords}
                if reason != "IDENTITY_CHANGED":
                    self.assertFalse(keywords)
                    other.append((name, reason, ast.dump(node.args[0], include_attributes=False)))
                    continue
                self.assertEqual(len(node.args), 3)
                site = keywords["source_site"].value
                self.assertNotIn(site, found)
                self.assertEqual(set(keywords), {"source_site", "source_item"} if site in OS_SITES else {"source_site"})
                if site in OS_SITES:
                    self.assertEqual(ast.dump(keywords["source_item"], include_attributes=False), expression("source_os_item(name)"))
                self.assertEqual(ast.dump(node.args[0], include_attributes=False), expression(CONDITIONS[site]))
                found[site] = (name, node.lineno)
        self.assertEqual(set(found), set(sites))
        self.assertEqual(other, [(name, reason, expression(condition)) for name, reason, condition in OTHER_SOURCE])
        for name in {name for name, _group in GROUPS}:
            self.assertEqual([site for site, location in sorted(found.items(), key=lambda pair: pair[1][1]) if location[0] == name],
                             [site for function, group in GROUPS if function == name for site in group])
        assignments = {node.targets[0].id: node for node in ast.walk(functions["file_pin"])
                       if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
        for name, value in (("before_stamp", "stamp(before)"), ("handle_stamp", "stamp(os.fstat(handle.fileno()))")):
            self.assertEqual(ast.dump(assignments[name].value, include_attributes=False), expression(value))
        self.assertLess(found["PIN_READ_SIZE"][1], assignments["before_stamp"].lineno)
        self.assertLess(assignments["before_stamp"].lineno, assignments["handle_stamp"].lineno)
        self.assertLess(assignments["handle_stamp"].lineno, found["PIN_FD_STABLE"][1])
        self.assertLess(found["PIN_FD_STABLE"][1], found["PIN_PATH_STABLE"][1])
        request, env = request_fixture()
        original = copy.deepcopy((request, env))
        github = M.validate_request(request, env, request)
        self.assertEqual((github["source"], github["sourceTree"]), (SHA, TREE))
        self._refusal(lambda: M.validate_request(request, env, {}), "REQUEST_EVENT")
        self._refusal(lambda: M.validate_request(request, {**env, "GITHUB_WORKFLOW_SHA": "d" * 40}, request), "REQUEST_SOURCE")
        self.assertEqual((request, env), original)
        for site, rows in ((None, [SHA.encode() + b"\n", TREE.encode() + b"\n", b""]),
                           ("SOURCE_STATUS", [SHA.encode(), TREE.encode(), CANARY.encode()]),
                           ("SOURCE_OBJECTS", [b"not-an-object", TREE.encode(), b""])):
            with patch.object(M, "capture_fixed", side_effect=[{"code": 0, "stderr": b"", "stdout": row} for row in rows]) as capture, \
                    patch.object(M, "read_file", return_value=b"SYNTHETIC_SOURCE") as read:
                if site is None:
                    result = M.source_snapshot(M.NS, {})
                    self.assertEqual((result["commit"], result["tree"], len(result["files"])), (SHA, TREE, 8))
                    self.assertEqual(read.call_count, 8)
                else:
                    self._refusal(lambda: M.source_snapshot(M.NS, {}), site)
                    read.assert_not_called()
                self.assertEqual(capture.call_count, 3)
        with patch.object(M.platform, "system", return_value="Darwin"), patch.object(M.platform, "machine", return_value="arm64"), \
                patch.object(M, "physical", return_value=Path("/synthetic/foreign")) as physical, \
                patch.object(M, "parsed") as parsed, patch.object(M, "read_file") as read:
            self._refusal(lambda: M.original_request({**env, "GITHUB_WORKSPACE": "/synthetic"}), "ORIGINAL_SOURCE_PATHS")
            self.assertEqual(physical.call_count, 1)
            parsed.assert_not_called()
            read.assert_not_called()
        raw, interpreter = b"SYNTHETIC_SCRIPT", {"path": "/synthetic/python"}
        prepared = {key: None for key in M.PREPARED_KEYS}
        prepared.update(schema=1, binding="c" * 64, case="N1", github=github,
                        allocation={"runId": "123", "runAttempt": "1"}, account=account_fixture(), boot=1,
                        directoryIdentity=[11, 12], operationIdentity=[11, 12], interpreter=interpreter,
                        caseEndNs=30 * M.NS, stepEndNs=50 * M.NS, jobEndNs=60 * M.NS,
                        source={"commit": SHA, "tree": TREE, "files": {M.SCRIPT: hashlib.sha256(raw).hexdigest()}})
        with patch.object(M, "account", side_effect=account_fixture), patch.object(M, "private_directory", return_value=[11, 12]), \
                patch.object(M.time, "monotonic_ns", return_value=10 * M.NS), patch.object(M, "read_file", return_value=raw) as read:
            native, directory = types.SimpleNamespace(boot=Mock(return_value=1)), Path("/synthetic/evidence/N1")
            self.assertIs(M.validate_prepared(prepared, directory, native, interpreter), prepared)
            changed = copy.deepcopy(prepared)
            changed["source"]["tree"] = "d" * 40
            read.reset_mock()
            self._refusal(lambda: M.validate_prepared(changed, directory, native, interpreter), "PREPARED_SOURCE")
            read.assert_not_called()
            changed = copy.deepcopy(prepared)
            changed["github"]["workflow"] = "SYNTHETIC_OTHER"
            self._refusal(lambda: M.validate_prepared(changed, directory, native, interpreter), "PREPARED_RUN")
            read.assert_called_once_with(M.ROOT / M.SCRIPT, M.EVIDENCE_BYTES)
        error, observed, counts, _boundary = self._prepare_source_model(source={"commit": "d" * 40, "tree": TREE, "files": {}})
        self._assert_site(error, "CHECKOUT_SOURCE")
        self.assertEqual((observed, counts), ([], (0, 0, 0)))

    def test_02_split_metadata_and_original_observation_order(self):
        initial_cases = (
            ("PIN_TYPE", {"st_mode": stat.S_IFDIR | 0o620, "st_uid": 999}, False),
            ("PIN_OWNER", {"st_uid": 999, "st_nlink": 2}, False),
            ("PIN_NLINK", {"st_nlink": 2, "st_mode": stat.S_IFREG | 0o620}, False),
            ("PIN_MODE", {"st_mode": stat.S_IFREG | 0o620, "st_size": 9}, False),
            ("PIN_MODE", {"st_mode": stat.S_IFREG | 0o602}, False),
            ("PIN_SIZE", {"st_size": -1}, False),
            ("PIN_SIZE", {"st_size": 9}, True),
            ("PIN_EXECUTABLE", {}, True),
        )
        for site, before, executable in initial_cases:
            value, error, observed = self._pin_model(before=before, executable=executable, access=False)
            self.assertIsNone(value)
            self._assert_site(error, site)
            self.assertEqual(observed, ["fstat", "access", "close"] if site == "PIN_EXECUTABLE" else ["fstat", "close"])
        for site, arguments, expected in (
            ("PIN_READ_SIZE", {"before": {"st_size": 5}}, ["fstat", "read", "read", "close"]),
            ("PIN_FD_STABLE", {"final_fd": {"st_ino": 3}}, ["fstat", "read", "read", "fstat", "close"]),
            ("PIN_PATH_STABLE", {"final_path": {"st_ino": 3}}, ["fstat", "read", "read", "fstat", "lstat", "close"]),
        ):
            value, error, observed = self._pin_model(**arguments)
            self.assertIsNone(value)
            self._assert_site(error, site)
            self.assertEqual(observed, expected)
        for raw, maximum, executable in ((b"", 0, False), (b"DATA", 8, False), (b"12345678", 8, True)):
            value, error, observed = self._pin_model(before={"st_size": len(raw)}, raw=raw, maximum=maximum, executable=executable)
            self.assertIsNone(error)
            self.assertEqual((value["size"], value["sha256"]), (len(raw), hashlib.sha256(raw).hexdigest()))
            self.assertEqual(observed, ["fstat"] + (["access"] if executable else []) +
                             ["read"] * (2 if raw else 1) + ["fstat", "lstat", "close"])
        with tempfile.TemporaryDirectory(prefix="cs-") as temporary:
            path = Path(temporary).resolve() / "synthetic.bin"
            path.write_bytes(b"DATA")
            path.chmod(0o600)
            with patch.object(M.time, "monotonic_ns", return_value=0):
                pin = M.file_pin(path, 4, M.NS)
            self.assertEqual((pin["size"], pin["sha256"]), (4, hashlib.sha256(b"DATA").hexdigest()))
        for site, changed, uid_count in (
            ("PYTHON_PARENT_TYPE", {"st_mode": stat.S_IFREG | 0o755, "st_uid": 999}, 0),
            ("PYTHON_PARENT_OWNER", {"st_uid": 999}, 1),
            ("PYTHON_PARENT_MODE", {"st_mode": stat.S_IFDIR | 0o777}, 1),
        ):
            _value, error, observed, actual_uid, pin, _resolved, _pinned = self._interpreter_model(changed)
            self._assert_site(error, site)
            self.assertEqual((observed, actual_uid), (["/synthetic/parent"], uid_count))
            pin.assert_not_called()
        for owner in (0, 501):
            value, error, observed, uid_count, pin, resolved, pinned = self._interpreter_model({"st_uid": owner})
            self.assertIsNone(error)
            self.assertIs(value, pinned)
            self.assertEqual((observed, uid_count), (["/synthetic/parent", "/synthetic"], 3))
            pin.assert_called_once_with(resolved, 64 * 1024 * 1024, M.NS, owners=(0, 501), executable=True)
        for name in ("/", "/usr/bin/git"):
            normal_type = stat.S_IFDIR if name in M.OS_PARENTS else stat.S_IFREG
            wrong_type = stat.S_IFREG if name in M.OS_PARENTS else stat.S_IFDIR
            for site, changed in (("OS_OWNER", {"st_uid": 999, "st_mode": normal_type | 0o777}),
                                  ("OS_MODE", {"st_mode": wrong_type | 0o777}),
                                  ("OS_TYPE", {"st_mode": wrong_type | 0o755})):
                error, observed, counts, _boundary = self._prepare_source_model(changed={name: changed})
                self._assert_site(error, site, OS_ITEMS[name])
                self.assertEqual(observed, list(OS_ITEMS)[:list(OS_ITEMS).index(name) + 1])
                self.assertEqual(counts, (1, 0, 0))
        error, observed, counts, boundary = self._prepare_source_model()
        self.assertIs(error, boundary)
        self.assertIsNone(M.public_source_site(error))
        self.assertEqual((observed, counts), (list(OS_ITEMS), (1, 1, 1)))

    def test_03_fixed_public_containment_and_new_field_mutation(self):
        class Hostile:
            def __str__(self):
                raise AssertionError("DIAGNOSTIC_MUST_NOT_STRINGIFY_DATA")

            __repr__ = __str__

            def __hash__(self):
                raise AssertionError("DIAGNOSTIC_MUST_NOT_HASH_DATA")

            def __eq__(self, _other):
                raise AssertionError("DIAGNOSTIC_MUST_NOT_COMPARE_DATA")

        class StringSubclass(str):
            pass

        for _name, group in GROUPS:
            for site in group:
                error = M.ExperimentError("SOURCE", "IDENTITY_CHANGED", source_site=site)
                self._assert_site(error, site)
                self.assertEqual(str(error), "SOURCE/IDENTITY_CHANGED/NONE")
                if site in OS_SITES:
                    for item in OS_ITEMS.values():
                        error.source_item = item
                        self._assert_site(error, site, item)
                else:
                    error.source_item = "ROOT"
                    self._assert_site(error, site)
        bad_values = (None, True, 123, [], {}, b"OS_OWNER", CANARY, "/synthetic/" + CANARY,
                      "OS_OWNER\n" + CANARY, Hostile())
        for bad in bad_values:
            self._assert_site(M.ExperimentError("SOURCE", "IDENTITY_CHANGED", source_site=bad, source_item=bad), "UNKNOWN")
        for attribute in ("source_site", "source_item"):
            for bad in (*bad_values, StringSubclass("OS_OWNER" if attribute == "source_site" else "ROOT")):
                error = M.ExperimentError("SOURCE", "IDENTITY_CHANGED", source_site="OS_OWNER", source_item="ROOT")
                setattr(error, attribute, bad)
                self._assert_site(error, "UNKNOWN" if attribute == "source_site" else "OS_OWNER")
                self.assertNotIn(CANARY, M.public_source_site(error))
        error = M.ExperimentError("SOURCE", "IDENTITY_CHANGED")
        del error.source_site
        del error.source_item
        self._assert_site(error, "UNKNOWN")
        for value in (*bad_values, StringSubclass("/"), "/synthetic/unlisted"):
            self.assertEqual(M.source_os_item(value), "NONE")
        for path, item in OS_ITEMS.items():
            self.assertEqual(M.source_os_item(path), item)
        for stage in M.STAGES:
            for reason in M.REASONS:
                if (stage, reason) == ("SOURCE", "IDENTITY_CHANGED"):
                    continue
                error = M.ExperimentError(stage, reason, source_site="OS_OWNER", source_item="ROOT")
                self.assertIsNone(M.public_source_site(error))
                self.assertEqual(M.public_error(error), "P2PKIT_CONTEXT_FAILURE|" + stage + "|" + reason + "|NONE")
        for error in (RuntimeError(CANARY), OSError(CANARY), SystemExit(CANARY),
                      M.ExperimentError(CANARY, CANARY, CANARY)):
            self.assertIsNone(M.public_source_site(error))
            self.assertEqual(M.public_error(error), "P2PKIT_CONTEXT_FAILURE|PREPARE|REFUSED|UNKNOWN")
        with patch.object(M, "ExperimentError", side_effect=AssertionError("SUCCESS_MUST_NOT_CREATE_ERROR")) as constructor:
            self.assertIsNone(M.require(True, "SOURCE", "IDENTITY_CHANGED", source_site=Hostile(), source_item=Hostile()))
            constructor.assert_not_called()
        error = self._refusal(lambda: M.require(False, "SOURCE", "IDENTITY_CHANGED", source_site="REQUEST_EVENT"), "REQUEST_EVENT")
        with self.assertRaises(M.ExperimentError) as preserved:
            with M.at_stage("PREPARE"):
                raise error
        self.assertIs(preserved.exception, error)
        self._assert_site(preserved.exception, "REQUEST_EVENT")
        with self.assertRaises(M.ExperimentError) as generic:
            with M.at_stage("SOURCE"):
                raise RuntimeError(CANARY)
        self.assertIsNone(M.public_source_site(generic.exception))
        self.assertEqual(M.public_error(generic.exception), "P2PKIT_CONTEXT_FAILURE|SOURCE|REFUSED|UNKNOWN")
        self._assert_site(M.ExperimentError("SOURCE", "IDENTITY_CHANGED"), "UNKNOWN")

    def test_04_existing_main_outcome_and_nonactivation(self):
        request, env = request_fixture()
        for result, raised, expected in (
            (0, None, ""), (1, None, ""),
            (None, lambda: M.validate_request(request, env, {}), FAILURE + "\n" + PREFIX + "REQUEST_EVENT|NONE\n"),
            (None, M.ExperimentError("NATIVE_SEND", "RETURN_FAILED", "EHOSTUNREACH"),
             "P2PKIT_CONTEXT_FAILURE|NATIVE_SEND|RETURN_FAILED|EHOSTUNREACH\n"),
            (None, M.ExperimentError("SOURCE", "BOUND"), "P2PKIT_CONTEXT_FAILURE|SOURCE|BOUND|NONE\n"),
            (None, RuntimeError(CANARY), "P2PKIT_CONTEXT_FAILURE|PREPARE|REFUSED|UNKNOWN\n"),
        ):
            output = io.StringIO()
            with patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), patch.object(M.os, "umask") as umask, \
                    patch.object(M, "experiment", return_value=result, side_effect=raised) as experiment, \
                    patch.object(M, "finish_export") as finish, patch.object(M, "upload_guard") as upload, \
                    patch.object(M, "write_new") as write, patch.object(M, "CommandFile") as command, \
                    patch.object(M, "Darwin") as native, patch.object(M, "load_module") as loader, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(M.main(), result if raised is None else 2)
                experiment.assert_called_once_with()
                umask.assert_called_once_with(0o077)
                for endpoint in (finish, upload, write, command, native, loader):
                    endpoint.assert_not_called()
            self.assertEqual(output.getvalue(), expected)
            self.assertNotIn(CANARY, output.getvalue())
        source = SOURCE.read_text()
        # Exact unmodified functions include all four generic SOURCE-capable
        # clock/capture checks and the existing closed-failure/success handling.
        for name, expected in {
            "public_error": "d36958b9aae0eeb7b3222cc7b810756cc39f2c3016091f0770fd36e415ed7803",
            "at_stage": "a7577363ecf3b00c70e4a64e499cc650dcdeb4e97dc1fb181f50be04fe672dfa",
            "left": "c029c610216f1cb8898933324fcf4cb99ce3d26a0ff79aa2da11e5627f6f3c7a",
            "capture_fixed": "c6ad3edb46529d0a0f9624b8b0c8589a6d232d2d24cb9799a708fc78c40acba5",
            "experiment": "d1bcce8eb564ece5d01364bbfb063c63fd307c7f36277d7591f87991bc8f049b",
        }.items():
            self.assertEqual(hashlib.sha256(function_text(source, name).encode()).hexdigest(), expected)
        for name, expected in {
            "AGENTS.md": "3ca3ef11f49ba90152754fb9d884ed353a5bc549b0ab648e182d889d4283d84b",
            "CLAUDE.md": "0fd0e8bdd297e16caabc40e87411c377f674769a40b73a35f43818bf9f97a71d",
            ".github/workflows/darwin-native-context-experiment.yml": "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40",
            "scripts/tests/hosted-darwin-context-experiment-test.py": "58caa9f5a8a43eeabf11c5c7547390bdf5869444040c3f268c1400b611066229",
            ".github/workflows/dependency-update-candidate.yml": "0d01d62e7693a6f6d13ac469400aacfcce13ce6aa68cc86378fde2870b34cc1a",
            ".github/workflows/release-foundation-checks.yml": "6d45a5ea496f25847ce261d8f0d67af0d87c8573bb8d05456839701f20e185cc",
            ".github/test-evidence-recipient.json": "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521",
            "scripts/run-hosted-dependency-update.py": "32373f3cce722d2e9932e1b5ce2375dd734ec699ca2d6c55c70724682cbea6ce",
            "scripts/audit_processes.py": "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13",
            "scripts/run-audit-command.py": "04e921eb5ba1e715078d9b315e366cc8f970151c9c1e5e0a4e5dfae0f0ed1ccc",
            "scripts/hosted_evidence.py": "fb45dd548474a003e5aaec0a3a3391c7e06034ab51e74688292ff2f583978ea8",
            "scripts/check-heavy-job-queue-policy.rb": "be1bd3defe99c71242f0360f88c012382ea973a03028d82b616483ed8c0c1430",
            "scripts/tests/check-heavy-job-queue-policy-test.rb": "f7d674c41fe0b0d67ce212eb93d0c80de8f0ec20b6529f1603b8911200c33f1f",
        }.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        self.assertEqual((M.JOB_SECONDS, M.STEP_SECONDS, M.PREPARE_SECONDS, M.NATIVE_SECONDS, M.CASE_SECONDS,
                          M.ABORT_SECONDS, M.FREEZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS, M.ADMIN_SECONDS),
                         (1440, 720, 120, 180, 40, 120, 60, 120, 420, 10))
        self.assertEqual((M.FRAME_BYTES, M.STREAM_BYTES, M.EVIDENCE_BYTES, M.EVIDENCE_MEMBERS,
                          M.JSON_DEPTH, M.JSON_NODES, M.MAX_CIPHERTEXT_BYTES),
                         (16384, 65536, 2 * 1024 * 1024, 128, 32, 4096, 576 * 1024 * 1024))
        self.assertEqual((M.REQUEST_KEYS, M.CASES, M.POLICY_EXPIRES, M.LATEST_ENTRY),
                         ({"source_sha", "source_tree"}, ("N1", "N2", "N3", "N4"), 1791158400, "2026-10-04T20:30:00Z"))

    def test_05_fixed_installed_entry_and_python39_source_grammar(self):
        workflow = (ROOT / ".github/workflows/darwin-native-context-experiment.yml").read_text(encoding="utf-8")
        entry = "/Library/Developer/CommandLineTools/usr/bin/python3"
        lines = (
            ("shell", "-I -B -S {0}"),
            ("run", "-I -B -S controller/scripts/run-hosted-darwin-context-experiment.py experiment"),
            ("run", "-I -B -S controller/scripts/run-hosted-darwin-context-experiment.py before-upload"),
            ("run", "-I -B -S controller/scripts/run-hosted-darwin-context-experiment.py after-upload"),
        )

        def original_workflow(text):
            self.assertEqual(text.count(entry), 4)
            for key, arguments in lines:
                selected = "        " + key + ": " + entry + " " + arguments + "\n"
                original = "        " + key + ": python3 " + arguments + "\n"
                self.assertEqual(text.count(selected), 1)
                text = text.replace(selected, original, 1)
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(),
                             "2e6d8d1ac525e28205424941c215d63f5554744e538efa1c7c783ac319293135")

        original_workflow(workflow)
        for old, replacement in (
            (entry, "/usr/bin/python3"), (entry, "python3"),
            (" experiment\n", " experiment || true\n"),
            ("contents: read", "contents: write"), ("timeout-minutes: 24", "timeout-minutes: 25"),
            ("source_sha:\n", "source_revision:\n"), ("overwrite: false", "overwrite: true"),
        ):
            changed = workflow.replace(old, replacement, 1)
            self.assertNotEqual(changed, workflow)
            with self.assertRaises(AssertionError):
                original_workflow(changed)

        # Grammar checking does not execute these sources or qualify an actual
        # Apple interpreter, vendor patch level, resolved path or native API.
        for name in ("scripts/run-hosted-darwin-context-experiment.py", "scripts/audit_processes.py",
                     "scripts/hosted_evidence.py", "scripts/hosted_evidence_primitives.py"):
            ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name, feature_version=(3, 9))
        allocation = workflow.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
        allocation = "\n".join(line[10:] if line.startswith(" " * 10) else line for line in allocation.splitlines())
        ast.parse(allocation, filename="allocation-source-only", feature_version=(3, 9))

    def test_06_exact_root_state_parent_and_original_retirement(self):
        source = SOURCE.read_text(encoding="utf-8")
        revised_lines = (
            'ROOT_TEMPLATE = "/private/var/db/p2pkit-context.XXXXXXXXXX"\n',
            'OS_PARENTS = ("/", "/private", "/private/var", "/private/var/db", "/usr", "/usr/bin", "/bin")\n',
            '    "/": "ROOT", "/private": "PRIVATE", "/private/var": "PRIVATE_VAR", '
            '"/private/var/db": "PRIVATE_VAR_DB",\n',
            r'        require(re.fullmatch(rb"/private/var/db/p2pkit-context\.[A-Za-z0-9]{10}\n", raw), '
            '"ADMIN_CREATE", "UNSUPPORTED")\n',
        )

        def original_runtime(text):
            self.assertEqual(text.count("/private/var/db"), 4)
            self.assertEqual(text.count("PRIVATE_VAR_DB"), 1)
            for revised in revised_lines:
                original = revised.replace("/private/var/db", "/private/var/run").replace(
                    "PRIVATE_VAR_DB", "PRIVATE_VAR_RUN")
                self.assertEqual(text.count(revised), 1)
                text = text.replace(revised, original, 1)
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(),
                             "4b9a6af99f5520c8689d629bebb3c814e1f97ab71e50c9db7b3003bdefeaed6c")

        original_runtime(source)
        mutations = [(line, line.replace("/private/var/db", "/private/var/run").replace(
            "PRIVATE_VAR_DB", "PRIVATE_VAR_RUN")) for line in revised_lines]
        mutations.extend((
            ("/private/var/db/p2pkit-context.XXXXXXXXXX", "/private/var/root/p2pkit-context.XXXXXXXXXX"),
            ('require(info.st_uid == 0, "SOURCE"', 'require(info.st_uid in (0, os.getuid()), "SOURCE"'),
            ('require(not info.st_mode & 0o022, "SOURCE"', 'require(not info.st_mode & 0o002, "SOURCE"'),
            ('require(error.errno == errno.ENOENT, "RETIRE"',
             'require(error.errno in (errno.ENOENT, errno.EACCES), "RETIRE"'),
        ))
        for old, replacement in mutations:
            changed = source.replace(old, replacement, 1)
            self.assertNotEqual(changed, source)
            with self.assertRaises(AssertionError):
                original_runtime(changed)

        # The changed legacy suite pin is justified by this one fixture line,
        # not regenerated to admit unrelated changes to its original assertions.
        legacy = (ROOT / "scripts/tests/hosted-darwin-context-experiment-test.py").read_text(encoding="utf-8")
        revised = '        root = "/private/var/db/p2pkit-context.ABCDEFGHIJ"\n'
        self.assertEqual(legacy.count(revised), 1)
        original = legacy.replace(revised, revised.replace("/private/var/db", "/private/var/run"), 1)
        self.assertEqual(hashlib.sha256(original.encode("utf-8")).hexdigest(),
                         "560a5f3d765eca955dd67e3529f111a82bfe9cfe81dd58b6948d5f6508939964")

        self.assertEqual(M.ROOT_TEMPLATE, "/private/var/db/p2pkit-context.XXXXXXXXXX")
        admin = M.Admin.__new__(M.Admin)
        admin.root, admin.path, admin.service = None, None, None
        admin.label = "p2pkit.context.synthetic.parent"
        for command in (
            ["/usr/bin/mktemp", "-d", M.ROOT_TEMPLATE],
            ["/usr/bin/stat", "-f", M.STAT_FORMAT, "/private/var/db"],
            ["/bin/ls", "-lde", "/private/var/db"],
        ):
            admin._allowed(command, b"")
        for parent in ("/private/var/run", "/private/var/root", "/var/db", "/private/var/db/.."):
            for command in (
                ["/usr/bin/mktemp", "-d", parent + "/p2pkit-context.XXXXXXXXXX"],
                ["/usr/bin/stat", "-f", M.STAT_FORMAT, parent],
                ["/bin/ls", "-lde", parent],
            ):
                with self.assertRaises(M.ExperimentError):
                    admin._allowed(command, b"")

        # Only synthetic command returns: no sudo, mktemp, native call or state
        # directory is acquired. The affected original test_03 covers success
        # through all40 real Admin-method model calls and unchanged retirement.
        for returned in (
            b"/private/var/run/p2pkit-context.ABCDEFGHIJ\n",
            b"/private/var/root/p2pkit-context.ABCDEFGHIJ\n",
            b"/var/db/p2pkit-context.ABCDEFGHIJ\n",
            b"/private/var/db/p2pkit-context.ABCDEFGHI\n",
            b"/private/var/db/p2pkit-context.ABCDEFGHIJK\n",
            b"/private/var/db/p2pkit-context.ABCDEFGHIJ/../other\n",
            b"/private/var/db/p2pkit-context.ABCDEFGHIJ\nextra\n",
        ):
            admin._run = Mock(return_value={"stdout": returned})
            admin.metadata = Mock(side_effect=AssertionError("INVALID_ROOT_MUST_NOT_BE_ADOPTED"))
            with self.assertRaises(M.ExperimentError):
                admin.create()
            admin._run.assert_called_once_with(["/usr/bin/mktemp", "-d", M.ROOT_TEMPLATE], "ADMIN_CREATE")
            admin.metadata.assert_not_called()
            self.assertIsNone(admin.root)
            self.assertIsNone(admin.path)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SourceSites)
    if suite.countTestCases() != 6:
        raise SystemExit("FIXED_SIX_SOURCE_SITE_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
