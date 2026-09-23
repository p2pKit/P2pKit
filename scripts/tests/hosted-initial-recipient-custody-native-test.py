#!/usr/bin/env python3
"""Focused custody-only native routing/drain models; no hosted qualification.

AST-select the maintained full phase, command/environment/ACK functions and
Owner.error/close_fence/close_one. Neither controller nor an earlier suite is
imported. Native resources, original registration, clocks, paths, signals and
captures are explicit in-memory models: no process, Git, HTTP, private file or
real signal operation occurs. The N dispatcher control selects ONLY its actual
scope predicate, not a recreated SourceReturn or successful authority episode.

Missing/invalid saved ceilings use the exact existing phase scope-finalizer
subtree. They are malformed-state refusal probes, NOT a claim those states can
be produced by a valid prelaunch allocation. All other phase controls select
the complete unmodified function. These controls cannot establish genuine
ownership, retirement, original custody, timing fit or native acceptance.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from types import MethodType, SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
B_PATH = ROOT / "scripts/run-hosted-cache-bootstrap.py"
N_PATH = ROOT / "scripts/run-hosted-initial-recipient.py"
B_TREE = ast.parse(B_PATH.read_text())
N_TREE = ast.parse(N_PATH.read_text())
NS = 1_000_000_000
TOKEN_ENV = "P2PKIT_ACTIONS_READ_TOKEN"
TOKEN = "SYNTHETIC_CUSTODY_NATIVE_NONCREDENTIAL"
CONTEXTS = ("CONTEXT_SCOPE", "INITIAL_CONTEXT_SCOPE", "INITIAL_ENTRY_CONTEXT_SCOPE",
            "INITIAL_AUTHORITY_CONTEXT_SCOPE", "INITIAL_RECEIVING_CONTEXT_SCOPE",
            "INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE")
ACKS = ("ACK_SCOPE", "RECIPIENT_ACK_SCOPE", "INITIAL_ACK_SCOPE", "INITIAL_ENTRY_ACK_SCOPE",
        "INITIAL_AUTHORITY_ACK_SCOPE", "INITIAL_RECIPIENT_ACK_SCOPE", "INITIAL_RECEIVING_ACK_SCOPE",
        "INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE")
MANAGED = {"INITIAL_ENTRY_CONTEXT_SCOPE", "INITIAL_AUTHORITY_CONTEXT_SCOPE", "INITIAL_RECEIVING_CONTEXT_SCOPE"}


class Refusal(ValueError):
    pass


class FalseyRefusal(Refusal):
    def __bool__(self):
        return False


def require(value, reason):
    if not value:
        raise Refusal(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def integer(value):
    require(type(value) is int and value >= 0, "MODEL_INTEGER")
    return value


def definition(tree, name):
    matches = [value for value in tree.body if isinstance(value, (ast.FunctionDef, ast.ClassDef)) and value.name == name]
    require(len(matches) == 1, "MODEL_UNIQUE_SOURCE_DEFINITION")
    return matches[0]


def selected(nodes, namespace, filename=B_PATH):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(filename), "exec", dont_inherit=True), namespace)


def target_names(target):
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(target_names(value) for value in target.elts))
    return set()


class PosixPathModel(PurePosixPath):
    """Fixed synthetic installation metadata, never a filesystem resolver."""
    def resolve(self, *, strict=False):
        return self

    def is_file(self):
        return self.name == "git"


class WindowsPathModel(PureWindowsPath):
    def resolve(self, *, strict=False):
        return self

    def is_file(self):
        return self.name == "git.exe"


def namespace():
    root = PosixPathModel("/SYNTHETIC/P2pKit")
    result = {"__name__": __name__, "__file__": str(root / "scripts/run-hosted-cache-bootstrap.py"),
        "dataclass": dataclass, "require": require, "math": math, "re": re, "Path": PosixPathModel,
        "ROOT": root, "SCRIPTS": root / "scripts", "sys": SimpleNamespace(executable="/SYNTHETIC/python"),
        "os": SimpleNamespace(name="posix", pathsep=":", defpath="/SYNTHETIC/system-bin",
            environ={"PATH": "/AMBIENT/bin", TOKEN_ENV: TOKEN, "GH_TOKEN": TOKEN, "ACTIONS_RUNTIME_TOKEN": TOKEN}),
        "origin": SimpleNamespace(parse=json.loads, encoded=encoded, digest=digest, integer=integer,
            OriginError=Refusal, NS=NS, wire=SimpleNamespace(ACQUIRE_SECONDS=45, TOKEN_ENV=TOKEN_ENV)),
        "query": SimpleNamespace(_CONTEXT=("MODEL_JOB", "MODEL_INVOCATION", "MODEL_STATE", "MODEL_HOME"),
            _inherited_context=lambda: {}),
        "diagnostics": SimpleNamespace(_exception_detail=lambda error: {
            "message": str(error), "retirementUnknown": False})}
    wanted = {*CONTEXTS, *ACKS, "PHASE_SCOPE", "ACK_LIMIT", "STDERR_LIMIT", "IDENTITY_ENV"}
    constants = [value for value in B_TREE.body if isinstance(value, ast.Assign) and
        any(target_names(target) & wanted for target in value.targets)]
    selected(constants, result)
    require(wanted <= result.keys(), "MODEL_MISSING_SOURCE_CONSTANT")
    names = ("OriginalPhase", "command", "initial_command", "initial_entry_command", "initial_authority_command",
        "initial_receiving_command", "initial_custody_authority_command", "phase_command", "child_environment",
        "_initial_service_environment", "phase", "cancellation", "guarded")
    selected([definition(B_TREE, name) for name in names], result)
    owner = definition(B_TREE, "Owner")
    selected([definition(owner, name) for name in ("error", "close_fence", "close_one")], result)
    return result


class FileModel:
    def __init__(self, rig, name, end):
        self.rig, self.name, self.end = rig, name, end
        self.data = b"SYNTHETIC_ACK\n" if name == "stdout.log" else b""
        self.closed = False

    def verify(self):
        require(not self.closed, "MODEL_CAPTURE_ALREADY_CLOSED")

    def sync(self):
        self.verify()

    def observe_live_output(self):
        self.verify()

    def close(self):
        require(not self.closed, "MODEL_CAPTURE_DOUBLE_CLOSE")
        self.closed = True


class DirectoryModel:
    def __init__(self, rig, path):
        self.rig, self.path, self.files = rig, path, {}

    def create_file(self, name, *, max_bytes, deadline):
        require(name not in self.files and max_bytes > 0, "MODEL_CAPTURE_DUPLICATE")
        value = FileModel(self.rig, name, deadline)
        self.files[name] = value
        return value


class FenceModel:
    def __init__(self, rig):
        self.rig, self.failure, self.deadline_failure = rig, None, None
        self.clock = SimpleNamespace(role="linux-x64")
        self.work, self.final = 1240 * NS, 1420 * NS
        self.deadlines, self.managed = [], []

    def now(self, *, final=False, limit=None):
        if self.failure is not None:
            raise self.failure
        ceiling = self.final if final else self.work
        if self.rig.raw >= min(ceiling, limit if limit is not None else ceiling):
            self.failure = Refusal("MODEL_FINAL_EXHAUSTED" if final else "MODEL_WORK_EXHAUSTED")
            raise self.failure
        return self.rig.raw

    def deadline(self, maximum, *, final=False, limit=None):
        self.deadlines.append((maximum, final, limit))
        if self.deadline_failure is not None:
            raise self.deadline_failure
        now = self.now(final=final, limit=limit)
        ceiling = self.final if final else self.work
        return self.rig.local + min(maximum, (min(ceiling, limit if limit is not None else ceiling) - now) / NS)

    def enter_phase(self, owner, started):
        self.managed.append("enter")
        self.saved = owner.work_limit, owner.final_limit
        work = min(self.work, started + 45 * NS)
        final = min(self.final, work + 45 * NS)
        owner.work_limit, owner.final_limit = work, final
        return work, final

    def leave_phase(self, owner):
        self.managed.append("leave")
        owner.work_limit, owner.final_limit = self.saved


class ScopeModel:
    def __init__(self, rig):
        self.rig, self.baseline, self.drains = rig, [], []
        self.spawn_calls, self.close_calls, self.retired = [], 0, False
        self.drain_error, self.close_error = None, None
        self.child = SimpleNamespace(stdout=None, stderr=None, pid=701, poll=self.poll)

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.spawn_calls.append((argv, cwd, dict(env), stdout, stderr))
        self.environment = env  # Preserve the actual modeled object for token-clearing assertions.
        return self.child

    def poll(self):
        if self.rig.after_poll is not None:
            self.rig.after_poll()
        return 0

    def description(self):
        return {"startedIdentities": [{"pid": self.child.pid, "startTicks": 9}] if self.spawn_calls else [],
            "discoveryErrors": []}

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait, deadline):
        self.drains.append({"grace": grace, "kill_wait": kill_wait, "deadline": deadline, "local": self.rig.local})
        self.rig.events.append("drain")
        require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline > self.rig.local,
            "MODEL_EXPIRED_OR_INVALID_DRAIN")
        if self.drain_error is not None:
            raise self.drain_error
        self.retired = True
        return []

    def close(self):
        self.close_calls += 1
        self.rig.events.append("close")
        if self.close_error is not None:
            raise self.close_error


class OwnerModel:
    def __init__(self, rig):
        self.rig, self.fence, self.local_end = rig, rig.fence, 200.0
        self.work_limit, self.final_limit = self.fence.work, self.fence.final
        self.resources, self.errors, self.writes, self.reads = [], [], {}, []
        self.original, self.unknown, self.phase_originals = None, False, None
        for name in ("error", "close_fence", "close_one"):
            setattr(self, name, MethodType(rig.ns[name], self))

    def acquire(self, label, factory):
        value = factory()
        self.resources.append({"label": label, "owner": value, "attempted": False, "closed": False})
        if label == "native-scope" and self.rig.after_acquire is not None:
            self.rig.after_acquire()
        return value

    def child(self, private, name, *, create=False):
        require(create and name == "service", "MODEL_FIXED_SERVICE_DIRECTORY")
        self.directory = self.acquire("directory", lambda: DirectoryModel(self.rig, private.path / name))
        return self.directory

    def write(self, directory, name, value, *, final=False):
        raw = encoded(value)
        self.writes[name] = raw
        return raw

    def read(self, directory, name, maximum, *, final=False):
        value = directory.files[name]
        require(final and value.closed and len(value.data) <= maximum, "MODEL_READ_BEFORE_CLOSE")
        self.reads.append(name)
        return value.data


class Rig:
    def __init__(self, scope_name=CONTEXTS[-1]):
        self.ns = namespace()
        self.local, self.raw = 10.0, 1000 * NS
        self.after_poll = self.after_acquire = None
        self.events, self.allocations = [], []
        self.fence = FenceModel(self)
        self.owner = OwnerModel(self)
        self.scope = ScopeModel(self)
        self.private = SimpleNamespace(path=PosixPathModel("/SYNTHETIC/originals"))
        self.context = {"scope": self.ns[scope_name], "job": "a" * 32}
        self.old_limits = self.owner.work_limit, self.owner.final_limit
        self.ns.update(time=SimpleNamespace(monotonic=lambda: self.local, sleep=self.unexpected_sleep),
            uuid=SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="b" * 32)),
            processes=SimpleNamespace(ownership_environment=self.environment, make_scope=self.make_scope),
            preparer_identity=lambda *_: {"pid": 700, "startTicks": 8}, lifetime=lambda *_: None,
            posix=SimpleNamespace(_deadline=self.local_deadline))

    def environment(self, base, job, invocation, state, home, *, allow_new_context):
        require(allow_new_context, "MODEL_OWNED_ENVIRONMENT")
        return dict(base, **dict(zip(self.ns["query"]._CONTEXT, (job, invocation, state, home))))

    def make_scope(self, *args):
        require(not self.allocations, "MODEL_SCOPE_REALLOCATION")
        self.allocations.append(self.scope)
        return self.scope

    def unexpected_sleep(self, _seconds):
        raise AssertionError("The bounded model must never start a wait loop")

    def local_deadline(self, end):
        require(type(end) in (int, float) and math.isfinite(end) and self.local < end, "MODEL_LOCAL_DEADLINE")

    def advance(self, seconds):
        self.local, self.raw = 10.0 + seconds, (1000 + seconds) * NS

    def fail(self, error, *, seconds=84):
        self.advance(seconds)
        self.fence.failure = error

    def run(self):
        git = None if self.context["scope"] == self.ns["CONTEXT_SCOPE"] else "/SYNTHETIC/git/bin/git"
        return self.ns["phase"](self.owner, self.private, encoded(self.context), TOKEN, self.fence, initial_git=git)


class CustodyNativeControls(unittest.TestCase):
    def assert_failed_resources(self, rig, first, *, closed=True):
        self.assertIs(rig.owner.original, first)
        self.assertIsNone(rig.owner.phase_originals)
        self.assertTrue(rig.owner.unknown)
        self.assertEqual(rig.owner.reads, [])
        self.assertEqual((rig.owner.work_limit, rig.owner.final_limit), rig.old_limits)
        scopes = [row for row in rig.owner.resources if row["label"] == "native-scope"]
        self.assertEqual(len(scopes), 1)
        self.assertIs(scopes[0]["owner"], rig.scope)
        self.assertTrue(scopes[0]["attempted"])
        self.assertIs(scopes[0]["closed"], closed)
        self.assertEqual(rig.scope.close_calls, 1)
        captures = [row for row in rig.owner.resources if row["label"] in ("stdout", "stderr")]
        self.assertEqual(len(captures), 2)
        self.assertTrue(all(not row["attempted"] and not row["closed"] for row in captures))
        self.assertTrue(all(row["owner"] is rig.owner.directory.files[row["label"] + ".log"] for row in captures))
        if rig.scope.spawn_calls:
            self.assertNotIn(TOKEN_ENV, rig.scope.environment)

    def test_fixed_custody_command_is_distinct_and_old_routes_unchanged(self):
        ns = namespace()
        expected = (("run-hosted-cache-bootstrap.py", "_service"), ("run-hosted-initial-recipient.py", "_service"),
            ("run-hosted-initial-recipient.py", "_service-entry"), ("run-hosted-initial-recipient.py", "_service-authority"),
            ("run-hosted-initial-recipient.py", "_service-receiving-authority"),
            ("run-hosted-initial-recipient-custody.py", "_authority"))
        self.assertEqual(ns[CONTEXTS[-1]], "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_CONTEXT_V1")
        self.assertEqual(len({ns[name] for name in CONTEXTS}), len(CONTEXTS))
        for name, (filename, operation) in zip(CONTEXTS, expected):
            with self.subTest(scope=name):
                raw = encoded({"scope": ns[name]})
                argv = ns["phase_command"](raw, 17)
                self.assertEqual(argv, ["/SYNTHETIC/python", "-I", "-B", "-S", str(ns["SCRIPTS"] / filename),
                    operation, "--context-sha256", digest(raw), "--minimum-ns", "17"])
                self.assertEqual(ns["phase_command"](raw), argv[:-2])
        for scope in (None, "_authority", ns[CONTEXTS[-1]] + "_LOOKALIKE"):
            with self.assertRaisesRegex(Refusal, "SERVICE_CONTEXT_SCOPE"):
                ns["phase_command"](encoded({"scope": scope}))
        with self.assertRaisesRegex(Refusal, "CONTEXT_HASH"):
            ns["initial_custody_authority_command"]("not-a-context-hash")

    def test_custody_git_route_and_n_dispatcher_keep_closed_original_scopes(self):
        ns = namespace()
        predicates = [value for value in ast.walk(definition(N_TREE, "_initial_service_phase")) if
            isinstance(value, ast.Compare) and isinstance(value.left, ast.Subscript) and
            isinstance(value.left.value, ast.Name) and value.left.value.id == "context" and
            isinstance(value.left.slice, ast.Constant) and value.left.slice.value == "scope"]
        self.assertEqual(len(predicates), 1)
        predicate = predicates[0]
        self.assertEqual([value.attr for value in predicate.comparators[0].elts], list(CONTEXTS[1:]))
        compiled = compile(ast.Expression(body=predicate), str(N_PATH), "eval", dont_inherit=True)
        native = SimpleNamespace(**{name: ns[name] for name in CONTEXTS})
        for name in CONTEXTS:
            self.assertIs(eval(compiled, {"context": {"scope": ns[name]}, "native": native}), name != CONTEXTS[0])
        self.assertFalse(eval(compiled, {"context": {"scope": "UNKNOWN"}, "native": native}))
        for platform, path_type, root, git in (("posix", PosixPathModel, "/SYNTHETIC/originals", "/SYNTHETIC/git/bin/git"),
                ("nt", WindowsPathModel, "C:/SYNTHETIC/originals", "C:/SYNTHETIC/git/bin/git.exe")):
            with self.subTest(platform=platform):
                ns["Path"], ns["os"].name, ns["os"].pathsep = path_type, platform, ";" if platform == "nt" else ":"
                path, installed = path_type(root), str(path_type(git))
                for name in CONTEXTS[1:]:
                    env = ns["_initial_service_environment"](path, {"scope": ns[name]}, installed)
                    self.assertEqual(env["PATH"], str(path_type(git).parent))
                    self.assertFalse(set(env) & {TOKEN_ENV, "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN"})
                    if platform == "nt":
                        self.assertEqual((env["PATHEXT"], env["NoDefaultCurrentDirectoryInExePath"]), (".EXE", "1"))
                for bad in (None, "", "relative/git", installed + "\n"):
                    with self.assertRaises(Refusal):
                        ns["_initial_service_environment"](path, {"scope": ns[CONTEXTS[-1]]}, bad)
                ordinary = {"scope": ns[CONTEXTS[0]]}
                self.assertEqual(ns["_initial_service_environment"](path, ordinary, None), ns["child_environment"](path))
                with self.assertRaisesRegex(Refusal, "ON_ORDINARY_ROUTE"):
                    ns["_initial_service_environment"](path, ordinary, installed)

    def test_ack_scope_stamps_only_closed_routes_and_late_failure_still_refuses(self):
        ns = namespace()
        self.assertEqual(ns[ACKS[-1]], "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_POST_CLOSE_ACK_V1")
        self.assertEqual(len({ns[name] for name in ACKS}), len(ACKS))
        for name in (*ACKS, CONTEXTS[-1]):
            for late in ((False, True) if name == ACKS[-1] else (False,)):
                with self.subTest(scope=name, late=late):
                    output, signal_calls, observations = io.BytesIO(), [], []
                    first, saved = Refusal("MODEL_AFTER_OUTPUT_FAILURE"), object()
                    def now(**kwargs):
                        observations.append(kwargs)
                        if late and len(observations) == 2:
                            raise first
                        return 52
                    ns["sys"].stdout = SimpleNamespace(buffer=output)
                    ns["signal"] = SimpleNamespace(SIGINT=2, SIGTERM=15, getsignal=lambda _number: saved,
                        signal=lambda number, handler: signal_calls.append((number, handler)))
                    fence = SimpleNamespace(now=now)
                    operation = lambda _cancelled: ({"scope": ns[name]}, fence, 91)
                    if late:
                        with self.assertRaises(Refusal) as caught:
                            ns["guarded"](operation)
                        self.assertIs(caught.exception, first)
                    else:
                        ns["guarded"](operation)
                    value = json.loads(output.getvalue())
                    self.assertEqual(value, {"scope": ns[name], **({"closedNs": 52} if name in ACKS else {})})
                    self.assertEqual(observations, [{"final": True, "limit": 91}] * 2)
                    self.assertEqual(signal_calls[-2:], [(2, saved), (15, saved)])

    def test_success_never_uses_saved_fallback_and_custody_stays_unmanaged(self):
        for name in CONTEXTS:
            with self.subTest(scope=name):
                rig = Rig(name)
                directory, original = rig.run()
                self.assertIs(directory, rig.owner.directory)
                self.assertIs(original, rig.owner.phase_originals)
                self.assertIsNone(rig.owner.original)
                self.assertFalse(rig.owner.unknown)
                self.assertEqual([call[0] for call in rig.fence.deadlines], [90, 45])
                self.assertEqual({value.end for value in directory.files.values()}, {100.0})
                self.assertEqual(rig.scope.drains, [{"grace": 5, "kill_wait": 5, "deadline": 55.0, "local": 10.0}])
                self.assertEqual(rig.fence.managed, ["enter", "leave"] if name in MANAGED else [])
                self.assertEqual((rig.owner.work_limit, rig.owner.final_limit), rig.old_limits)
                self.assertEqual(rig.events, ["drain", "close"])
                self.assertEqual(rig.owner.reads, ["stdout.log", "stderr.log"])
                self.assertEqual(json.loads(dict(original.records)["result.json"])["retirement"], "KNOWN")
                self.assertEqual(rig.scope.spawn_calls[0][2][TOKEN_ENV], TOKEN)
                self.assertNotIn(TOKEN_ENV, rig.scope.environment)

    def test_work_expiry_drains_original_ceiling_but_remains_unknown(self):
        rig = Rig()
        rig.after_poll = lambda: rig.advance(84)
        with self.assertRaisesRegex(Refusal, "MODEL_WORK_EXHAUSTED") as caught:
            rig.run()
        self.assertIs(caught.exception, rig.fence.failure)
        self.assert_failed_resources(rig, caught.exception)
        self.assertEqual(rig.scope.drains, [{"grace": 5, "kill_wait": 1, "deadline": 100.0, "local": 94.0}])
        self.assertEqual(rig.events, ["drain", "close"])
        self.assertTrue(rig.scope.retired)  # A model backend return is NOT native acceptance.
        self.assertEqual([call[0] for call in rig.fence.deadlines], [90, 45])
        self.assertNotIn("result.json", rig.owner.writes)

    def test_cancellation_and_falsey_first_failure_still_drain_and_close(self):
        for first in (KeyboardInterrupt("MODEL_CANCELLED"), FalseyRefusal("MODEL_FALSEY_FIRST")):
            with self.subTest(error=type(first).__name__):
                rig = Rig()
                rig.after_poll = lambda: rig.fail(first)
                with self.assertRaises(type(first)) as caught:
                    rig.run()
                self.assertIs(caught.exception, first)
                self.assert_failed_resources(rig, first)
                self.assertEqual([row["stage"] for row in rig.owner.errors][:3], ["service", "drain-fence", "service-drain"])
                self.assertEqual(rig.scope.drains[0]["deadline"], 100.0)
                self.assertEqual(rig.events, ["drain", "close"])

    def test_fallback_can_shorten_but_cannot_renew_original_cap(self):
        for current, expected in ((97.0, 97.0), (500.0, 100.0)):
            with self.subTest(current=current):
                rig, first = Rig(), Refusal("MODEL_FIRST")
                def failed():
                    rig.fail(first)
                    rig.owner.local_end = current
                rig.after_poll = failed
                with self.assertRaises(Refusal) as caught:
                    rig.run()
                self.assertIs(caught.exception, first)
                self.assert_failed_resources(rig, first)
                self.assertEqual({value.end for value in rig.owner.directory.files.values()}, {100.0})
                self.assertEqual(rig.scope.drains[0]["deadline"], expected)
                self.assertLess(expected, rig.local + 45)

    def test_every_old_scope_refuses_fallback_but_closes_original_scope(self):
        for name in CONTEXTS[:-1]:
            with self.subTest(scope=name):
                rig, first = Rig(name), Refusal("MODEL_OLD_SCOPE_FAILURE")
                rig.after_poll = lambda: rig.fail(first)
                with self.assertRaises(Refusal) as caught:
                    rig.run()
                self.assertIs(caught.exception, first)
                self.assert_failed_resources(rig, first)
                self.assertEqual(rig.scope.drains, [])
                self.assertEqual(rig.events, ["close"])
                self.assertEqual(rig.fence.managed, ["enter", "leave"] if name in MANAGED else [])

    def test_post_return_failure_recovers_same_registered_native_scope(self):
        rig, first = Rig(), Refusal("MODEL_AFTER_NATIVE_RETURN")
        def after_return():
            rig.fail(first)
            rig.fence.now()
        rig.after_acquire = after_return
        with self.assertRaises(Refusal) as caught:
            rig.run()
        self.assertIs(caught.exception, first)
        self.assert_failed_resources(rig, first)
        self.assertEqual(rig.allocations, [rig.scope])
        self.assertEqual(rig.scope.spawn_calls, [])
        self.assertEqual(len(rig.scope.drains), 1)
        self.assertEqual(rig.scope.drains[0]["deadline"], 100.0)
        self.assertEqual(rig.events, ["drain", "close"])

    def test_secondary_drain_and_close_errors_preserve_first_and_resources(self):
        rig, first = Rig(), FalseyRefusal("MODEL_ORIGINAL_FALSEY")
        rig.after_poll = lambda: rig.fail(first)
        rig.scope.drain_error, rig.scope.close_error = Refusal("MODEL_DRAIN_SECOND"), Refusal("MODEL_CLOSE_THIRD")
        with self.assertRaises(FalseyRefusal) as caught:
            rig.run()
        self.assertIs(caught.exception, first)
        self.assert_failed_resources(rig, first, closed=False)
        self.assertEqual(rig.events, ["drain", "close"])
        self.assertFalse(rig.scope.retired)
        self.assertIn("native-scope-close", [row["stage"] for row in rig.owner.errors])

    def test_missing_or_invalid_saved_cap_refuses_without_new_deadline(self):
        phase = definition(B_TREE, "phase")
        fragments = [value for value in ast.walk(phase) if isinstance(value, ast.If) and
            isinstance(value.test, ast.Compare) and isinstance(value.test.left, ast.Name) and
            value.test.left.id == "scope" and len(value.test.ops) == 1 and isinstance(value.test.ops[0], ast.IsNot)]
        self.assertEqual(len(fragments), 1)
        invalid = (None, True, 0, -1, float("nan"), float("inf"), "100.0")
        for field in ("capture_end", "local_end"):
            for value in invalid:
                with self.subTest(field=field, value=repr(value)):
                    rig, first = Rig(), Refusal("MODEL_DRAIN_CONVERSION_FAILED")
                    rig.owner.acquire("native-scope", lambda: rig.scope)
                    rig.fence.deadline_failure = first
                    if field == "local_end":
                        rig.owner.local_end = value
                    frame = dict(rig.ns, scope=rig.scope, owner=rig.owner, context=rig.context, fence=rig.fence,
                        capture_end=value if field == "capture_end" else 100.0, final_end=1090 * NS,
                        native_known=False, row={"preparerIdentity": {"pid": 700, "startTicks": 8}})
                    selected(fragments, frame)
                    self.assertIs(rig.owner.original, first)
                    self.assertTrue(rig.owner.unknown)
                    self.assertFalse(frame["native_known"])
                    self.assertEqual(rig.scope.drains, [])
                    self.assertEqual(rig.scope.close_calls, 1)
                    self.assertTrue(frame["row"]["scopeCloseAttempted"])
                    self.assertEqual(rig.fence.deadlines, [(45, True, 1090 * NS)])
                    self.assertTrue(any("NO_ORIGINAL_CLEANUP_CEILING" in row["detail"]["message"] for row in rig.owner.errors))

    def test_expired_original_cap_gets_zero_allowance_not_renewal_or_acceptance(self):
        rig = Rig()
        rig.after_poll = lambda: rig.advance(90)
        with self.assertRaisesRegex(Refusal, "MODEL_WORK_EXHAUSTED") as caught:
            rig.run()
        self.assert_failed_resources(rig, caught.exception)
        self.assertEqual(rig.scope.drains, [{"grace": 0, "kill_wait": 0, "deadline": 100.0, "local": 100.0}])
        self.assertFalse(rig.scope.retired)
        self.assertEqual(rig.events, ["drain", "close"])
        self.assertTrue(any(row["detail"]["message"] == "MODEL_EXPIRED_OR_INVALID_DRAIN" for row in rig.owner.errors))


if __name__ == "__main__":
    unittest.main()
