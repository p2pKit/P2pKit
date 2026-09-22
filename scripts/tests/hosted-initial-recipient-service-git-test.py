#!/usr/bin/env python3
"""Focused original-Git routing models; no hosted/Git/native qualification.

Only the three new function bodies, existing child-environment builder,
query prefix guard and existing query-finalizer/inner service try are AST-selected from maintained
source. Neither controller is imported. Tiny POSIX files are nonexecutable
fixtures; Windows paths, original query returns, owners and suppliers are models.
No accepted reader, recipient, initializer or prior test method is executed.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
N_PATH = ROOT / "scripts/run-hosted-initial-recipient.py"
B_PATH = ROOT / "scripts/run-hosted-cache-bootstrap.py"
N_TEXT, B_TEXT = N_PATH.read_text(), B_PATH.read_text()
N_TREE, B_TREE = ast.parse(N_TEXT), ast.parse(B_TEXT)
BASE = "3bc76f956f8f47447b51a62474fc878b9c43173c"
SOURCE = "b" * 40
BLOB = "c" * 40
POLICY = ".github/test-evidence-recipient.json"
SCOPES = ("INITIAL_CONTEXT_SCOPE", "INITIAL_ENTRY_CONTEXT_SCOPE",
          "INITIAL_AUTHORITY_CONTEXT_SCOPE", "INITIAL_RECEIVING_CONTEXT_SCOPE")
KEYS = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
TOKEN = "SYNTHETIC_NONCREDENTIAL_SERVICE_GIT_CONTROL"


class Refusal(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Refusal(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def node(tree, name):
    return next(value for value in tree.body if isinstance(value, (ast.FunctionDef, ast.ClassDef)) and value.name == name)


def selected(tree, names, namespace, filename):
    body = [node(tree, name) for name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), str(filename), "exec", dont_inherit=True), namespace)


class WindowsPathModel(PureWindowsPath):
    """Supplied installed-path metadata, not Windows file/API execution."""
    def resolve(self, *, strict=False):
        return self

    def is_file(self):
        return self.name == "git.exe"


class ServiceGitControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="service-git-model-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.bin = self.base / "installed"
        self.bin.mkdir()
        self.git = self.bin / "git"
        self.git.write_bytes(b"SYNTHETIC NONEXECUTABLE GIT METADATA\n")
        self.private = SimpleNamespace(path=self.base / "originals")
        self.environ = {"PATH": str(self.bin), "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
                        "P2PKIT_ACTIONS_READ_TOKEN": TOKEN, "GH_TOKEN": TOKEN, "ACTIONS_RUNTIME_TOKEN": TOKEN}
        self.os = SimpleNamespace(name="posix", pathsep=":", defpath=os.defpath, environ=self.environ)
        self.native_ns = {"__name__": __name__, "require": require, "os": self.os, "Path": Path,
                          "query": SimpleNamespace(_inherited_context=lambda: {})}
        assignments = [value for value in B_TREE.body if isinstance(value, ast.Assign) and
                       any(isinstance(target, ast.Name) and target.id in (*SCOPES, "IDENTITY_ENV") for target in value.targets)]
        self.assertEqual(len(assignments), 5)
        exec(compile(ast.Module(body=assignments, type_ignores=[]), str(B_PATH), "exec", dont_inherit=True), self.native_ns)
        selected(B_TREE, ("child_environment", "_initial_service_environment"), self.native_ns, B_PATH)
        self.calls = []
        self.returned = object()

        def phase(*args, **kwargs):
            self.calls.append((args, kwargs))
            return self.returned

        self.native = SimpleNamespace(**{name: self.native_ns[name] for name in SCOPES}, phase=phase,
                                      diagnostics=SimpleNamespace(_QUARANTINE=[]))
        self.ns = {"__name__": __name__, "dataclass": dataclass, "Path": Path, "ROOT": ROOT, "re": re,
                   "require": require, "os": self.os, "native": self.native, "SOURCE_KEYS": KEYS,
                   "SOURCE_SCOPE": "INITIAL_RECIPIENT_SOURCE_QUERIES_RETURNED_V1",
                   "I": SimpleNamespace(POLICY_PATH=POLICY, sha=lambda value: require(
                       type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value), "SHA")),
                   "O": SimpleNamespace(parse=json.loads, encoded=encoded, digest=digest, OriginError=Refusal),
                   "Q": SimpleNamespace(encoded=encoded, QUARANTINE=[]),
                   "acquisition": SimpleNamespace(stages=SimpleNamespace(BASE={"commit": BASE}))}
        selected(N_TREE, ("SourceReturn", "_initial_service_phase", "_initial_service_query_git", "finish_queries"), self.ns, N_PATH)
        self.ends = 0
        self.owner = SimpleNamespace(initial_sources={}, end=self.end)
        self.fence = object()
        self.make_original()

    def end(self):
        self.ends += 1

    def make_original(self):
        path = self.private.path / "source-before"
        commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", SOURCE + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            ("rev-parse", "--verify", BASE + "^{tree}"), ("ls-tree", "-z", BASE, "--", POLICY),
            ("merge-base", BASE, SOURCE), ("ls-tree", "-z", SOURCE, "--", POLICY),
            ("cat-file", "-s", BLOB), ("cat-file", "blob", BLOB))
        self.session = {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": "d" * 32,
            "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN", "firstError": None, "errors": [], "readbacks": [],
            "queries": [{"argv": [str(self.git), "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                "-C", str(ROOT), *command], "job": "d" * 32, "state": str(path), "home": str(path / "query-home"),
                "cwd": str(ROOT), "launchAttempted": True, "scopeAttempted": True, "waitExitCode": 0,
                "retirement": "KNOWN", "result": "READY_FOR_CALLER_SEAL", "errors": [], "ownedSurvivors": []}
                for command in commands]}
        self.records = ((KEYS[0], b""), (KEYS[1], (BASE + "\n").encode()),
            (KEYS[2], ("100644 blob " + BLOB + "\t" + POLICY + "\0").encode()), (KEYS[3], b"SYNTHETIC POLICY"))
        self.bind_original()

    def bind_original(self):
        session_raw = encoded(self.session)
        raw = encoded({"schema": 1, "scope": self.ns["SOURCE_SCOPE"], "clock": {"model": True}, "returnedNs": 100,
                       "sessionSha256": digest(session_raw), "originalsSha256": {name: digest(raw) for name, raw in self.records}})
        self.original = self.ns["SourceReturn"](self.records, session_raw, raw)
        self.owner.initial_sources[str(self.private.path / "source-before")] = self.original
        self.context = {"scope": self.native.INITIAL_CONTEXT_SCOPE, "root": str(ROOT), "session": str(self.private.path),
                        "sourceReturnSha256": digest(raw), "sourceReturnedNs": 100, "observed": {"source": {"commit": SOURCE}}}

    def route(self, before=None):
        return self.ns["_initial_service_phase"](self.owner, self.private, encoded(self.context), TOKEN, self.fence,
                                                self.original if before is None else before)

    def environment(self, git=None, scope=None):
        return self.native_ns["_initial_service_environment"](self.private.path,
            {"scope": scope or self.native.INITIAL_CONTEXT_SCOPE}, str(self.git) if git is None else git)

    def service_fragment(self, supplier):
        candidates = [value for value in ast.walk(node(N_TREE, "service_child")) if isinstance(value, ast.Try) and
            value.body and isinstance(value.body[0], ast.Assign) and isinstance(value.body[0].value, ast.Call) and
            isinstance(value.body[0].value.func, ast.Name) and value.body[0].value.func.id == "query_owner"]
        self.assertEqual(len(candidates), 1)
        context = dict(self.ns, query_owner=lambda *_: supplier, owner=self.owner, fence=SimpleNamespace(now=lambda **_: 2),
                       path=self.private.path, context={"observed": {"kind": "worker", "firstUseAt": 1}},
                       domain={"id": "SYNTHETIC"}, start={"workEndNs": 10}, token=TOKEN, event=b"SYNTHETIC",
                       entry=False, authority=False, supplier=None, failure=None)
        context["acquisition"] = SimpleNamespace(acquire_bootstrap=lambda *args, **kwargs: self.fail("Unexpected acquisition"))
        try:
            exec(compile(ast.Module(body=candidates, type_ignores=[]), str(N_PATH), "exec", dont_inherit=True), context)
        finally:
            self.assertIsNone(context["token"])

    def test_all_four_original_contexts_transport_exact_captured_git(self):
        for scope in SCOPES:
            self.context["scope"] = getattr(self.native, scope)
            self.assertIs(self.route(), self.returned)
            args, kwargs = self.calls[-1]
            self.assertIs(args[0], self.owner)
            self.assertIs(args[-1], self.fence)
            self.assertEqual(kwargs, {"initial_git": str(self.git)})
        self.assertEqual(self.ends, 8)

    def test_same_fields_copy_is_not_an_original_return(self):
        copied = self.ns["SourceReturn"](self.original.records, self.original.session, self.original.raw)
        with self.assertRaisesRegex(Refusal, "SERVICE_GIT_ORIGINAL"):
            self.route(copied)
        self.assertEqual(self.calls, [])

    def test_context_return_and_session_hashes_must_match(self):
        for change in (lambda: self.context.update(sourceReturnSha256="0" * 64),
                       lambda: self.context.update(sourceReturnedNs=101),
                       lambda: object.__setattr__(self.original, "session", self.original.session + b" "),
                       lambda: self.context.update(root="/SYNTHETIC_OTHER")):
            self.make_original()
            change()
            with self.assertRaises(Refusal):
                self.route()
        self.assertEqual(self.calls, [])

    def test_fixed_complete_query_roster_and_success_are_required(self):
        for change in (lambda: self.session["queries"].pop(),
                       lambda: self.session["queries"].reverse(),
                       lambda: self.session["queries"][2].update(waitExitCode=False),
                       lambda: self.session["queries"][2].update(retirement="UNKNOWN"),
                       lambda: self.session["queries"][2].update(state="/OTHER"),
                       lambda: self.session.update(errors=["SYNTHETIC"]),
                       lambda: self.session.update(firstError="SYNTHETIC")):
            self.make_original()
            change()
            self.bind_original()
            with self.assertRaises(Refusal):
                self.route()
        self.assertEqual(self.calls, [])

    def test_all_original_query_executables_must_be_unanimous(self):
        self.session["queries"][5]["argv"][0] = str(self.base / "shadow" / "git")
        self.bind_original()
        with self.assertRaisesRegex(Refusal, "SERVICE_GIT_QUERY"):
            self.route()
        self.assertEqual(self.calls, [])

    def test_changed_original_after_owner_check_cannot_launch(self):
        def mutate():
            self.end()
            if self.ends == 2:
                self.owner.initial_sources.clear()
        self.owner.end = mutate
        with self.assertRaisesRegex(Refusal, "SERVICE_GIT_ORIGINAL_CHANGED"):
            self.route()
        self.assertEqual(self.calls, [])

    def test_prelaunch_refusal_clears_helper_token_reference(self):
        self.owner.initial_sources.clear()
        try:
            self.route()
        except Refusal as error:
            frames = []
            traceback = error.__traceback__
            while traceback is not None:
                if traceback.tb_frame.f_code.co_name == "_initial_service_phase":
                    frames.append(traceback.tb_frame.f_locals["token"])
                traceback = traceback.tb_next
            self.assertEqual(frames, [None])
        else:
            self.fail("Expected prelaunch refusal")

    def test_stage1_search_contains_only_original_git_directory_no_credentials(self):
        self.environ["PATH"] = str(self.base / "ambient") + ":" + str(self.bin)
        for scope in SCOPES:
            environment = self.environment(scope=getattr(self.native, scope))
            self.assertEqual(environment["PATH"], str(self.bin))
            self.assertEqual(set(environment) & {"P2PKIT_ACTIONS_READ_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN"}, set())
            self.assertEqual(environment["HOME"], str(self.private.path / "control-home"))

    def test_ordinary_route_is_unchanged_and_refuses_stage1_override(self):
        builder = self.native_ns["_initial_service_environment"]
        expected = self.native_ns["child_environment"](self.private.path)
        self.assertEqual(builder(self.private.path, {"scope": "BOOTSTRAP_ORIGINAL_ACQUISITION_CONTEXT_V1"}, None), expected)
        with self.assertRaisesRegex(Refusal, "ON_ORDINARY_ROUTE"):
            builder(self.private.path, {"scope": "BOOTSTRAP_ORIGINAL_ACQUISITION_CONTEXT_V1"}, str(self.git))

    def test_ambient_override_refusals_are_not_broadened(self):
        for key in ("LD_PRELOAD", "JAVA_TOOL_OPTIONS", "GIT_CONFIG_COUNT", "PYTHONPATH"):
            self.environ[key] = "SYNTHETIC_OVERRIDE"
            with self.assertRaises(Refusal):
                self.environment()
            del self.environ[key]

    def test_missing_relative_alias_or_wrong_tool_path_refuses(self):
        alias = self.base / "alias"
        alias.symlink_to(self.bin, target_is_directory=True)
        separator = self.base / "bad:path"
        separator.mkdir()
        (separator / "git").write_bytes(b"SYNTHETIC")
        for supplied in ("", "git", str(self.bin / "missing"), str(alias / "git"), str(separator / "git"), str(self.git) + "\n"):
            with self.assertRaises((Refusal, FileNotFoundError)):
                self.environment(git=supplied)
        with self.assertRaisesRegex(Refusal, "GIT_REQUIRED"):
            self.native_ns["_initial_service_environment"](self.private.path, {"scope": self.native.INITIAL_CONTEXT_SCOPE}, None)

    def test_windows_path_and_extension_policy_is_narrow_model_only(self):
        windows = SimpleNamespace(name="nt", pathsep=";", defpath=".;C:\\bin", environ={"PATH": "C:\\ambient", "PATHEXT": ".COM;.EXE"})
        self.native_ns.update(os=windows, Path=WindowsPathModel)
        expected = r"C:\Program Files\Git\cmd\git.exe"
        result = self.native_ns["_initial_service_environment"](WindowsPathModel(r"D:\owned"),
            {"scope": self.native.INITIAL_CONTEXT_SCOPE}, expected)
        self.assertEqual(result["PATH"], r"C:\Program Files\Git\cmd")
        self.assertEqual(result["PATHEXT"], ".EXE")
        self.assertEqual(result["NoDefaultCurrentDirectoryInExePath"], "1")
        windows.environ = result
        self.ns.update(os=windows, Path=WindowsPathModel)
        self.ns["_initial_service_query_git"](SimpleNamespace(executable=expected))
        with self.assertRaisesRegex(Refusal, "SELECTION"):
            self.ns["_initial_service_query_git"](SimpleNamespace(executable=r"D:\checkout\git.exe"))
        windows.environ["PATHEXT"] = ".COM;.EXE"
        with self.assertRaisesRegex(Refusal, "WINDOWS_SEARCH"):
            self.ns["_initial_service_query_git"](SimpleNamespace(executable=expected))

    def test_received_path_and_exact_selection_are_required(self):
        supplier = SimpleNamespace(executable=str(self.git))
        self.ns["_initial_service_query_git"](supplier)
        for search in ("", ".", str(self.bin) + ":/usr/bin", str(self.bin) + "/..", str(self.bin) + "\n"):
            self.environ["PATH"] = search
            with self.assertRaises(Refusal):
                self.ns["_initial_service_query_git"](supplier)

    def test_shadow_refuses_before_host_or_acquisition_and_closes_once(self):
        outcomes = []
        supplier = SimpleNamespace(executable=str(self.base / "shadow" / "git"), unknown=False,
            native_host_matches_actions=lambda: self.fail("Host/acquisition reached after shadow selection"),
            _finalize=lambda error: outcomes.append(error))
        with self.assertRaisesRegex(Refusal, "SELECTION") as caught:
            self.service_fragment(supplier)
        self.assertEqual(outcomes, [caught.exception])

    def test_shadow_primary_error_survives_secondary_query_close_failure(self):
        outcomes = []
        def close(error):
            outcomes.append(error)
            raise Refusal("SYNTHETIC_SECONDARY_CLOSE")
        supplier = SimpleNamespace(executable=str(self.base / "shadow" / "git"), unknown=False,
            native_host_matches_actions=lambda: self.fail("Host/acquisition reached after shadow selection"), _finalize=close)
        with self.assertRaisesRegex(Refusal, "SELECTION") as caught:
            self.service_fragment(supplier)
        self.assertEqual(outcomes, [caught.exception])

    def test_later_gitview_selection_drift_refuses_before_query_allocation(self):
        query_path = ROOT / "scripts/hosted_test_query.py"
        query_tree = ast.parse(query_path.read_text())
        query_class = node(query_tree, "NativeGitQueries")
        original_call = node(query_class, "__call__")
        maximum = next(value for value in query_tree.body if isinstance(value, ast.Assign) and
            any(isinstance(target, ast.Name) and target.id == "MAX_QUERIES" for target in value.targets))
        events, errors = [], []

        def blocked(*_args, **_kwargs):
            self.fail("Later GitView mismatch reached query allocation/process work")

        def record(row, phase, error):
            self.assertIsNone(row)
            self.assertEqual(phase, "query-input")
            errors.append(error)

        def fail_original():
            raise errors[0]

        namespace = {"require": require, "Path": Path, "_allowed_suffix": blocked,
                     "uuid": SimpleNamespace(uuid4=blocked), "time": SimpleNamespace(monotonic=blocked)}
        exec(compile(ast.Module(body=[maximum, original_call], type_ignores=[]), str(query_path),
                     "exec", dont_inherit=True), namespace)
        supplier = SimpleNamespace(executable=str(self.git), root=ROOT, active=False, records=[], git_environment={},
            _check=lambda: events.append("checked"), _error=record, _raise_failure=fail_original,
            _acquire=blocked, _hold=blocked, _write=blocked)
        later_argv = (str(self.base / "later-shadow" / "git"), "--no-replace-objects", "--no-pager", "-c",
                      "core.fsmonitor=false", "-C", str(ROOT), "rev-parse", "--show-toplevel")
        with self.assertRaisesRegex(Refusal, "QUERY_NOT_CLOSED_READONLY_GIT") as caught:
            namespace["__call__"](supplier, argv=later_argv, cwd=str(ROOT), environment={},
                                  stdout_limit=4096, stderr_limit=4096, timeout_seconds=1)
        self.assertEqual(events, ["checked"])
        self.assertEqual(errors, [caught.exception])
        self.assertEqual(supplier.records, [])
        self.assertFalse(supplier.active)

    def test_four_routes_and_native_phase_use_only_the_reviewed_hook(self):
        for name in ("_prepare_with_token", "_readmit_worker", "_recipient_authority", "_receiving_authority"):
            calls = [value for value in ast.walk(node(N_TREE, name)) if isinstance(value, ast.Call)]
            routes = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "_initial_service_phase"]
            self.assertEqual(len(routes), 1)
            self.assertEqual(ast.unparse(routes[0].args[-1]), "before")
            self.assertFalse(any(isinstance(call.func, ast.Attribute) and ast.unparse(call.func) == "native.phase" for call in calls))
        body = node(B_TREE, "phase")
        self.assertEqual([value.arg for value in body.args.kwonlyargs], ["initial_git"])
        routed = [value for value in ast.walk(body) if isinstance(value, ast.Call) and
                  isinstance(value.func, ast.Name) and value.func.id == "_initial_service_environment"]
        self.assertEqual(len(routed), 1)
        self.assertEqual([ast.unparse(value) for value in routed[0].args], ["private.path", "context", "initial_git"])

    def test_shared_query_and_identity_sources_are_unchanged(self):
        # Byte preservation, not re-execution/qualification of accepted suppliers.
        for name, expected in (("hosted_test_query.py", "017649cea6464fdc15f7ac732ee0f7b6516c690d43998b2d12e0bf6a0f5b7474"),
                               ("hosted_test_identity.py", "7fb8a7bb457ad7a623f1b82af9db4d4903945f5f900b34772fc4048ff7229178")):
            self.assertEqual(digest((ROOT / "scripts" / name).read_bytes()), expected)


if __name__ == "__main__":
    unittest.main(failfast=True)
