#!/usr/bin/env python3
"""Finite recipient-route DATA/caller controls, not hosted qualification.

No older fixture or test suite is loaded. The only policy fixture is the existing
committed PUBLIC recipient document. Git, native current, clocks, signals and
output descriptors below are explicit models, never live authority or originals.
These controls do not lift an interlock/HOLD, grant approval, run a product, or
qualify native retirement, cache/provider behavior, cryptography or delivery.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import copy
import ctypes  # Initialize stdlib before installing the native-load prohibition.
import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
_IMPORTING = False
_CALLING = False
_DENIED = []


class ModelViolation(BaseException):
    """A model contract failure must not become an expected Git query rejection."""

    def __init__(self, code):
        _DENIED.append("MODEL_" + code)
        super().__init__("OFFLINE_MODEL_CONTRACT_" + code)


def denied_effect(*_args, **_kwargs):
    _DENIED.append("UNMODELED_FILE_OR_NATIVE_SUPPLIER")
    raise AssertionError("OFFLINE_UNMODELED_EFFECT")


def offline(event, args):
    prohibited = event.startswith(("subprocess.", "socket.", "ctypes.")) or event in (
        "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn",
        "os.putenv", "os.unsetenv", "os.kill", "os.killpg", "os.chdir", "os.fchdir")
    filesystem = event == "open" or event in (
        "os.listdir", "os.scandir", "os.mkdir", "os.rmdir", "os.remove", "os.rename",
        "os.link", "os.symlink", "os.chmod", "os.chown", "os.truncate", "os.utime")
    if _CALLING and filesystem:
        prohibited = True
    if _IMPORTING and filesystem:
        if event == "open":
            name, mode, flags = args
            safe_name = isinstance(name, (str, bytes))
            name = os.fsdecode(name) if safe_name else ""
            allowed_root = name.startswith(str(SCRIPTS) + os.sep) or name.startswith(sys.base_prefix + os.sep)
            readonly = (mode is None or not any(char in mode for char in "wax+")) and not (
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            prohibited = prohibited or not (safe_name and allowed_root and readonly and
                                             name.endswith((".py", ".pyc")))
        elif event not in ("os.listdir", "os.scandir"):
            prohibited = True
    if prohibited:
        _DENIED.append(event)
        raise AssertionError("OFFLINE_UNMODELED_EFFECT")


sys.addaudithook(offline)
_IMPORTING = True
try:
    spec = importlib.util.spec_from_file_location("recipient_routing_control_subject",
                                                SCRIPTS / "run-hosted-recipient-routing.py")
    R = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = R
    spec.loader.exec_module(R)
finally:
    _IMPORTING = False
if _DENIED:
    raise AssertionError("ROUTING_IMPORT_ATTEMPTED_EFFECT")

I, STAGES = R.I, R.stages
# Read exactly this already committed PUBLIC document, never a keyring/backup.
PUBLIC_POLICY = (ROOT / ".github/test-evidence-recipient.json").read_bytes()
PUBLIC_VALUE = json.loads(PUBLIC_POLICY)
NOW = PUBLIC_VALUE["notBefore"] + 3600  # Historical model time, not live validity.
MODEL_ROOT, MODEL_TEMP, MODEL_GIT = Path("/model/source"), Path("/model/temporary"), Path("/model/bin/git")
BASE, HEAD, MERGE, TREE = STAGES.BASE["commit"], "b" * 40, "c" * 40, "d" * 40
OTHER = "e" * 40
MODEL_TOKEN = "SYNTHETIC_API_TOKEN_NOT_A_CREDENTIAL"
RAW_START = 987654 * R.clocks.NS
LOCAL_START = 23.125  # Deliberately incompatible with the RAW epoch.


@contextmanager
def candidate_call():
    """Deny unmodeled effects, including attempts swallowed by candidate code."""
    global _CALLING
    if _CALLING:
        raise AssertionError("NESTED_CANDIDATE_GUARD")
    start = len(_DENIED)
    with ExitStack() as stack:
        for name in ("stat", "lstat", "open", "read_bytes", "read_text", "iterdir", "glob", "rglob",
                     "mkdir", "unlink", "rename", "replace", "chmod", "touch"):
            stack.enter_context(patch.object(Path, name, denied_effect))
        _CALLING = True
        try:
            yield
        finally:
            _CALLING = False
            if len(_DENIED) != start:
                raise AssertionError("CANDIDATE_ATTEMPTED_UNMODELED_EFFECT")


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def put(value, path, replacement):
    target = value
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = replacement


class GitModel:
    """Exact finite native-query replies; the real maintained GitView parses them."""

    def __init__(self, profile="desktop", event="pull_request", *, initial=False, fork=False):
        self.profile, self.initial, self.calls, self.counts, self.overrides = profile, initial, [], {}, {}
        ref = "refs/pull/701/merge" if event == "pull_request" else "refs/heads/main"
        self.environment = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "RUNNER_NAME": "synthetic-route-runner", "RUNNER_TEMP": str(MODEL_TEMP),
            "GITHUB_JOB": "recipient-route", "GITHUB_RUN_ID": "7001", "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_EVENT_NAME": event, "GITHUB_REF": ref, "GITHUB_SHA": MERGE,
            "GITHUB_WORKFLOW_SHA": MERGE,
            "GITHUB_WORKFLOW_REF": I.REPOSITORY + "/" + I.PROFILES[profile][0] + "@" + ref,
            "GITHUB_WORKSPACE": str(MODEL_ROOT), "GITHUB_EVENT_PATH": "/model/inputs/event.json",
        }
        self.event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"}}
        if event == "pull_request":
            self.event.update(action="synchronize", number=701, pull_request={
                "number": 701, "state": "open", "merged": False,
                "base": {"sha": BASE, "ref": "main", "repo": {"full_name": I.REPOSITORY}},
                "head": {"sha": HEAD, "ref": STAGES.SOURCE_REF.removeprefix("refs/heads/"),
                         "repo": {"full_name": "synthetic-fork/P2pKit" if fork else I.REPOSITORY}},
            })
        elif event == "push":
            self.event.update(ref=ref, after=MERGE, before=BASE, deleted=False)
        elif event == "schedule":
            self.event["schedule"] = "17 4 * * 1"
        elif event == "workflow_dispatch":
            self.set_ref("refs/heads/model-feature")
            self.event.update(ref="model-feature", inputs={})
        else:
            raise ModelViolation("UNMODELED_EVENT_FIXTURE")
        self.policies = {BASE: None if initial else PUBLIC_POLICY, HEAD: PUBLIC_POLICY, MERGE: PUBLIC_POLICY}
        self.trees = {BASE: STAGES.BASE["tree"], HEAD: TREE, MERGE: TREE}

    def set_ref(self, ref):
        self.environment["GITHUB_REF"] = ref
        self.environment["GITHUB_WORKFLOW_REF"] = I.REPOSITORY + "/" + I.PROFILES[self.profile][0] + "@" + ref

    def entry(self, commit):
        raw = self.policies[commit]
        return b"" if raw is None else ("100644 blob " + blob(raw) + "\t" + I.POLICY_PATH + "\0").encode()

    def default(self, args):
        fixed = {
            ("rev-parse", "--show-toplevel"): str(MODEL_ROOT).encode() + b"\n",
            ("status", "--porcelain=v1", "--untracked-files=all"): b"",
            ("rev-parse", "--is-shallow-repository"): b"false\n",
            ("rev-parse", "--verify", "HEAD^{commit}"): MERGE.encode() + b"\n",
            ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"): BASE.encode() + b"\n",
            ("show", "-s", "--format=%P", MERGE): (BASE + " " + HEAD + "\n").encode(),
            ("merge-base", BASE, HEAD): BASE.encode() + b"\n",
        }
        if args in fixed:
            return fixed[args]
        for commit, tree in self.trees.items():
            if args == ("rev-parse", "--verify", commit + "^{tree}"):
                return tree.encode() + b"\n"
            if args == ("ls-tree", "-z", commit, "--", I.POLICY_PATH):
                return self.entry(commit)
        for raw in self.policies.values():
            if raw is not None:
                if args == ("cat-file", "-s", blob(raw)):
                    return str(len(raw)).encode() + b"\n"
                if args == ("cat-file", "blob", blob(raw)):
                    return raw
        raise ModelViolation("UNMODELED_GIT_QUERY")

    def __call__(self, *, argv, cwd, environment, stdout_limit, stderr_limit, timeout_seconds):
        prefix = (str(MODEL_GIT), "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                  "-C", str(MODEL_ROOT))
        if argv[:len(prefix)] != prefix or cwd != MODEL_ROOT:
            raise ModelViolation("QUERY_CALL_SHAPE")
        expected = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
        if environment != expected or stderr_limit != 4096 or timeout_seconds != 15:
            raise ModelViolation("QUERY_CREDENTIAL_OR_BOUND_CHANGE")
        args = tuple(argv[len(prefix):])
        limit = I.POLICY_LIMIT if args[:2] == ("cat-file", "blob") else (
            I.EVENT_LIMIT if args[:1] == ("status",) else 4096)
        if stdout_limit != limit:
            raise ModelViolation("QUERY_OUTPUT_BOUND_CHANGE")
        self.calls.append(args)
        self.counts[args] = self.counts.get(args, 0) + 1
        value = self.overrides.get(args, self.default)
        if callable(value):
            value = value(args)
        if isinstance(value, BaseException):
            raise value
        return value

    @contextmanager
    def suppliers(self):
        def executable(name):
            if name != "git":
                raise ModelViolation("UNMODELED_TOOL_LOOKUP")
            return str(MODEL_GIT)

        def resolve(path, *, strict=False):
            if path != MODEL_GIT or strict is not True:
                raise ModelViolation("UNMODELED_PATH_RESOLUTION")
            return path

        with patch.object(I.shutil, "which", executable), patch.object(Path, "resolve", resolve), patch.object(
                I, "_admit", denied_effect), patch.object(I, "os", SimpleNamespace(
                    name="posix", defpath=os.defpath, devnull=os.devnull, fsdecode=os.fsdecode)):
            yield

    def decide(self, *, raw=None, now=NOW):
        with self.suppliers(), candidate_call():
            view = I.GitView(MODEL_ROOT, self.environment, self)
            return R.decide_source_mode(self.profile, self.environment,
                                        encoded(self.event) if raw is None else raw, view, now)


class CallerModel:
    """Real wrappers/_Scope, fixed modeled suppliers, no native owner acquisition."""

    def __init__(self, *, profile="desktop", initial=False, gate=False):
        self.git = GitModel(profile, initial=initial)
        self.environment = self.git.environment
        self.profile, self.gate = profile, gate
        if gate:
            self.environment["GITHUB_JOB"] = "initial-recipient-gate"
            self.environment[R.TOKEN] = MODEL_TOKEN
        self.log, self.fail, self.receipts, self.outputs = [], {}, [], []
        self.handlers = {signal.SIGINT: object(), signal.SIGTERM: object()}
        self.installed = {}
        self.clock = R.clocks.ClockIdentity("linux-x64", R.clocks.LINUX_DOMAIN, R.clocks.NS)
        self.ns, self.cancelled, self.scope = RAW_START, None, None
        self.closed, self.failed, self.unknown = False, False, False
        self.close_flags = (True, False, False)
        self.private = MODEL_TEMP / "modeled-private-originals"
        self.current, self.claimed = object(), False
        self.current_closed, self.current_valid = True, True
        self.consume_token, self.claim_count = True, 0
        self.query_owner = self
        self.environment_reads, self.input_reads, self.checked_reads = 0, 0, 0
        self.mutate_environment = None
        self.mutate_inputs = None
        self.mutate_current = None
        self.eligible = {
            "scope": "NONPRODUCTIVE_ELIGIBILITY", "stage": "stage2",
            "source": {"commit": MERGE, "tree": TREE}, "reviewed": {"commit": HEAD, "tree": TREE},
            "github": {"event": "pull_request", "ref": self.environment["GITHUB_REF"],
                "workflow": I.PROFILES[profile][0], "workflowSha": MERGE, "job": "initial-recipient-gate",
                "runId": "7001", "runAttempt": "2", "runnerOS": "Linux", "runnerArch": "X64"},
        }
        self.current_value = {
            "scope": "INITIAL_ORDINARY_ORIGINAL_CURRENT_SOURCE_V1", "kind": "gate", "profile": profile,
            "role": "linux-x64", "source": copy.deepcopy(self.eligible["source"]),
            "reviewed": copy.deepcopy(self.eligible["reviewed"]), "identitySha256": None,
            "matchSha256": hashlib.sha256(encoded(self.eligible)).hexdigest(),
        }
        self.native = SimpleNamespace(RETURN_SCOPE="INITIAL_ORDINARY_ORIGINAL_CURRENT_SOURCE_V1",
            acquire_initial_ordinary=self.acquire, checked_initial_ordinary=self.checked,
            initial_ordinary_eligibility=self.eligibility, initial_ordinary_record=self.record,
            claim_initial_ordinary=self.claim)

    def step(self, name):
        self.log.append(name)
        failure = self.fail.get(name)
        if failure is not None:
            raise failure

    def observe(self):
        self.step("clock.observe")
        return R.clocks.Reading(self.clock, self.ns)

    def checked_now(self, expected, *, minimum_ns=0):
        self.step("clock.checked")
        if expected != self.clock or minimum_ns > self.ns:
            raise ModelViolation("CLOCK_IDENTITY_OR_DIRECTION")
        return self.ns

    def local(self):
        self.step("clock.local")
        return LOCAL_START

    def wall_time(self):
        self.step("clock.utc")
        return NOW

    def getsignal(self, number):
        self.step("signal.get")
        return self.handlers[number]

    def setsignal(self, number, handler):
        restoring = handler is self.handlers[number]
        self.step("signal.restore" if restoring else "signal.install")
        if not restoring:
            self.installed[number] = handler
        return self.handlers[number]

    def environment_value(self):
        self.step("environment")
        self.environment_reads += 1
        if self.mutate_environment:
            self.mutate_environment(self.environment_reads)
        return dict(self.environment)

    def route_inputs(self, env):
        self.step("inputs")
        self.input_reads += 1
        if self.mutate_inputs:
            return self.mutate_inputs(self.input_reads)
        return MODEL_ROOT, MODEL_TEMP, encoded(self.git.event)

    def owner(self, root, directory, *, check_cancel, owner_deadlines):
        self.step("owner.allocate")
        self.cancelled, self.scope = check_cancel, check_cancel.__self__
        if root != MODEL_ROOT or directory != MODEL_TEMP / (
                "p2pkit-recipient-route-" + self.profile + "-7001-2"):
            raise ModelViolation("OWNER_ORIGINAL_PATH")
        expected = (self.scope.work_end_ns, self.scope.final_end_ns)
        if expected != (RAW_START + 75 * R.clocks.NS, RAW_START + 120 * R.clocks.NS):
            raise ModelViolation("ORIGINAL_RAW_BOUNDS_CHANGED")
        if not (LOCAL_START < owner_deadlines[0] < LOCAL_START + 75 and
                owner_deadlines[0] < owner_deadlines[1] < LOCAL_START + 120):
            raise ModelViolation("RAW_NOT_LOCAL_OR_LOCAL_LIMIT_EXTENDED")
        if self.log.count("clock.observe") != 1 or len(self.installed) != 2:
            raise ModelViolation("OWNERSHIP_NOT_FIRST")
        check_cancel()
        return self.query_owner

    def __call__(self, **kwargs):
        self.step("owner.query")
        return self.git(**kwargs)

    def native_host_matches_actions(self):
        self.step("owner.host")

    def _check(self):
        self.step("owner.check")

    def _write(self, directory, name, raw):
        self.step("receipt." + name)
        if directory != self.private or name not in (
                "recipient-route.json", "original-event.json", "original-policy.json") or type(raw) is not bytes:
            raise ModelViolation("UNMODELED_PRIVATE_RECEIPT")
        self.receipts.append((name, raw))

    def _finalize(self, original):
        self.finalized_original = original
        self.step("owner.finalize")
        self.closed, self.failed, self.unknown = self.close_flags

    def load_current(self):
        self.step("current.loader")
        return self.native

    def acquire(self, *, kind, cancelled, original_work_end_ns, original_final_end_ns):
        self.step("current.acquire")
        self.cancelled, self.scope = cancelled, cancelled.__self__
        if kind != "gate" or (original_work_end_ns, original_final_end_ns) != (
                RAW_START + 75 * R.clocks.NS, RAW_START + 120 * R.clocks.NS):
            raise ModelViolation("GATE_KIND_ORIGINAL_FENCES")
        cancelled()
        if self.consume_token:
            self.environment.pop(R.TOKEN, None)
        return self.current

    def checked(self, current):
        self.step("current.checked")
        self.checked_reads += 1
        if self.mutate_current:
            self.mutate_current(self.checked_reads)
        if current is not self.current or not self.current_closed or not self.current_valid:
            raise I.AdmissionError("MODEL_CURRENT_CURRENCY_OR_CLOSE")
        return current

    def eligibility(self, current):
        self.step("current.eligibility")
        if current is not self.current:
            raise ModelViolation("REPLAYED_CURRENT_MODEL")
        return R.initial.originals.gate.GateEligibility(encoded(self.eligible))

    def record(self, current):
        self.step("current.record")
        if current is not self.current:
            raise ModelViolation("REPLAYED_CURRENT_MODEL")
        return encoded(self.current_value)

    def claim(self, current, purpose):
        self.step("current.claim")
        if current is not self.current or purpose != "gate" or self.claimed:
            raise I.AdmissionError("MODEL_SINGLE_GATE_CLAIM")
        self.claimed, self.claim_count = True, self.claim_count + 1
        return current

    def output(self, values):
        self.step("output")
        if self.log.count("signal.restore") != 2:
            raise ModelViolation("OUTPUT_BEFORE_SIGNAL_RESTORATION")
        if not self.gate and not (self.closed and not self.failed and not self.unknown):
            raise ModelViolation("OUTPUT_BEFORE_KNOWN_CLOSE")
        self.outputs.append(dict(values))

    @contextmanager
    def suppliers(self):
        # Replacing module references does not read/mutate the real environment.
        with self.git.suppliers(), ExitStack() as stack:
            for target, name, replacement in (
                (R, "os", SimpleNamespace(environ=self.environment)),
                (R.initial, "os", SimpleNamespace(environ=self.environment)),
                (R, "_environment", self.environment_value), (R, "_route_inputs", self.route_inputs),
                (R, "append_output", self.output), (R, "time", SimpleNamespace(time=self.wall_time)),
                (R.queries, "NativeGitQueries", self.owner), (R.clocks, "observe", self.observe),
                (R.clocks, "checked_now", self.checked_now),
                (R.clocks, "time", SimpleNamespace(monotonic=self.local)),
                (R, "signal", SimpleNamespace(SIGINT=signal.SIGINT, SIGTERM=signal.SIGTERM,
                    getsignal=self.getsignal, signal=self.setsignal)),
                (R.initial, "current_module", self.load_current), (R.initial, "acquire_first", denied_effect),
            ):
                stack.enter_context(patch.object(target, name, replacement))
            yield

    def run(self):
        with self.suppliers(), candidate_call():
            return R.initial_gate(self.profile) if self.gate else R.source_mode(self.profile)


class OutputModel:
    """Fixed synthetic output descriptor; no file is opened or written."""

    def __init__(self):
        self.path, self.resolved = "/model/github-output", True
        self.info = os.stat_result((stat.S_IFREG | 0o600, 17, 3, 1, 42, 42, 0, 0, 0, 0))
        self.opened = self.after = self.info
        self.calls, self.writes, self.fail = [], [], {}
        self.reads, self.short = 0, False

    def step(self, name):
        self.calls.append(name)
        if name in self.fail:
            raise self.fail[name]

    def path_value(self, name):
        self.step("path")
        if name != self.path:
            raise ModelViolation("OUTPUT_PATH_MODEL")
        return self

    def is_absolute(self):
        return self.path.startswith("/")

    def resolve(self, *, strict):
        self.step("resolve")
        if strict is not True:
            raise ModelViolation("OUTPUT_RESOLVE_NOT_STRICT")
        return self if self.resolved else object()

    def lstat(self):
        self.step("lstat")
        self.reads += 1
        return self.info if self.reads == 1 else self.after

    def open(self, target, flags):
        self.step("open")
        if target is not self or flags != (os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW):
            raise ModelViolation("OUTPUT_OPEN_MODE")
        return 37

    def fstat(self, fd):
        self.step("fstat")
        if fd != 37:
            raise ModelViolation("UNMODELED_DESCRIPTOR")
        return self.opened

    def write(self, fd, raw):
        self.step("write")
        if fd != 37 or type(raw) is not bytes:
            raise ModelViolation("UNMODELED_OUTPUT_WRITE")
        self.writes.append(raw)
        return len(raw) - 1 if self.short else len(raw)

    def fsync(self, fd):
        self.step("fsync")
        if fd != 37:
            raise ModelViolation("UNMODELED_DESCRIPTOR")

    def close(self, fd):
        self.step("close")
        if fd != 37:
            raise ModelViolation("UNMODELED_DESCRIPTOR")

    def append(self, values):
        model_os = SimpleNamespace(environ={"GITHUB_OUTPUT": self.path}, getuid=lambda: 42,
            open=self.open, fstat=self.fstat, write=self.write, fsync=self.fsync, close=self.close,
            path=SimpleNamespace(samestat=os.path.samestat),
            O_WRONLY=os.O_WRONLY, O_APPEND=os.O_APPEND, O_NOFOLLOW=os.O_NOFOLLOW)
        with patch.object(R, "os", model_os), patch.object(R, "Path", self.path_value), candidate_call():
            return R.append_output(values)


class RouteDataControls(unittest.TestCase):
    def assert_rejected(self, model, *, raw=None, now=NOW):
        with self.assertRaises((I.AdmissionError, UnicodeError)) as caught:
            model.decide(raw=raw, now=now)
        self.assertNotIn(MODEL_TOKEN, str(caught.exception))
        return caught.exception

    def test_ordinary_pr_keeps_original_base_policy_including_forks_both_profiles(self):
        for profile, fork in (("full", False), ("full", True), ("desktop", False), ("desktop", True)):
            with self.subTest(profile=profile, fork=fork):
                model = GitModel(profile, fork=fork)
                model.policies[HEAD] = b"CANDIDATE_POLICY_MUST_NOT_BE_READ"
                result = model.decide()
                value = json.loads(result.record)
                self.assertEqual((value["origin"], value["policy"]["commit"]), ("ordinary", BASE))
                self.assertEqual(value["source"], {"commit": MERGE, "tree": TREE})
                self.assertEqual(value["github"]["eventSha256"], hashlib.sha256(encoded(model.event)).hexdigest())
                self.assertEqual(result.original_event, encoded(model.event))
                self.assertEqual(result.original_policy, PUBLIC_POLICY)
                self.assertNotIn(("ls-tree", "-z", HEAD, "--", I.POLICY_PATH), model.calls)

    def test_ordinary_push_weekly_full_and_input_free_manual_select_correct_policy(self):
        for profile, event, policy in (("full", "push", MERGE), ("desktop", "push", MERGE),
                ("full", "schedule", MERGE), ("full", "workflow_dispatch", BASE),
                ("desktop", "workflow_dispatch", BASE)):
            with self.subTest(profile=profile, event=event):
                model = GitModel(profile, event)
                value = json.loads(model.decide().record)
                self.assertEqual((value["origin"], value["policy"]["commit"]), ("ordinary", policy))
                self.assertEqual(value["github"]["job"], "recipient-route")
                self.assertEqual(value["github"]["workflow"], I.PROFILES[profile][0])
                self.assertEqual(value["policy"]["retentionDays"], 14)
                self.assertEqual((value["github"]["runId"], value["github"]["runAttempt"]), ("7001", "2"))

    def test_initial_requires_successful_absent_base_and_exact_same_repository_pr(self):
        for profile in ("full", "desktop"):
            with self.subTest(profile=profile):
                model = GitModel(profile, initial=True)
                result = model.decide()
                value = json.loads(result.record)
                self.assertEqual((value["origin"], value["policy"]["commit"]), ("initial", HEAD))
                self.assertEqual(value["policy"]["sha256"], STAGES.POLICY_SHA256)
                self.assertEqual(model.counts[("ls-tree", "-z", BASE, "--", I.POLICY_PATH)], 2)
                self.assertIn(("merge-base", BASE, HEAD), model.calls)
                self.assertEqual(result.original_policy, PUBLIC_POLICY)

    def test_route_is_immutable_canonical_data_and_never_admission_or_authority(self):
        model = GitModel(initial=True)
        result = model.decide()
        value = json.loads(result.record)
        self.assertIs(type(result), R.RouteDecision)
        self.assertNotIsInstance(result, I.Admission)
        self.assertEqual(value["scope"], "HOSTED_RECIPIENT_ROUTE_DATA_V1")
        self.assertEqual(value["authority"], "NOT_ACQUIRED")
        self.assertEqual(result.record, encoded(value))
        self.assertEqual(set(value), {"schema", "scope", "origin", "profile", "source", "github", "policy", "authority"})
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.record = b"CHANGED"
        model.event["number"] = 702
        self.assertEqual(json.loads(result.original_event)["number"], 701)

    def test_equivalent_trusted_policy_format_is_valid_but_initial_hash_still_exact(self):
        # Leading JSON whitespace changes bytes without changing policy contents.
        alternate = b" " + PUBLIC_POLICY
        self.assertEqual(json.loads(alternate), PUBLIC_VALUE)
        self.assertNotEqual(alternate, PUBLIC_POLICY)
        ordinary = GitModel()
        ordinary.policies[BASE] = alternate
        self.assertEqual(ordinary.decide().original_policy, alternate)
        initial = GitModel(initial=True)
        initial.policies[HEAD] = alternate
        self.assert_rejected(initial)

    def test_invalid_event_bytes_fail_without_policy_fallback(self):
        vectors = (b"", b"{", b"[]", b"null", b'{"repository":{},"repository":{}}',
                   b'{"repository":NaN}', b'{"repository":Infinity}', b"\xff", b" " * (I.EVENT_LIMIT + 1))
        for raw in vectors:
            with self.subTest(vector=vectors.index(raw)):
                model = GitModel(initial=True)
                self.assert_rejected(model, raw=raw)
                self.assertFalse(any(args[:1] == ("ls-tree",) for args in model.calls))

    def test_environment_is_closed_to_wrong_job_host_workflow_run_and_overrides(self):
        vectors = (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/P2pKit"),
            ("GITHUB_SERVER_URL", "http://github.com"), ("GITHUB_API_URL", "https://invalid.example"),
            ("RUNNER_ENVIRONMENT", "self-hosted"), ("RUNNER_OS", "macOS"), ("RUNNER_ARCH", "ARM64"),
            ("GITHUB_JOB", "complete-gate"), ("RUNNER_NAME", ""), ("RUNNER_NAME", "bad\nrunner"),
            ("RUNNER_NAME", "x" * 257), ("GITHUB_RUN_ID", 7001), ("GITHUB_RUN_ID", "0"),
            ("GITHUB_RUN_ATTEMPT", "02"), ("GITHUB_EVENT_NAME", "pull_request_target"),
            ("GITHUB_REF", None), ("GITHUB_REF", "bad\rref"), ("GITHUB_SHA", OTHER),
            ("GITHUB_WORKFLOW_SHA", OTHER), ("GITHUB_WORKFLOW_REF", "wrong"),
            ("GITHUB_WORKSPACE", "relative"), ("GITHUB_WORKSPACE", "/model/../source"),
            ("GITHUB_WORKSPACE", "/other/source"), ("GIT_CONFIG_COUNT", "1"))
        for name, value in vectors:
            with self.subTest(name=name, value=value):
                model = GitModel()
                model.environment[name] = value
                self.assert_rejected(model)

    def test_source_requires_clean_root_exact_head_tree_and_full_history(self):
        vectors = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", MERGE + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"))
        outputs = (b"/elsewhere\n", b" M file\n", OTHER.encode() + b"\n", b"short\n", b"true\n")
        for args, response in zip(vectors, outputs):
            with self.subTest(args=args):
                model = GitModel()
                model.overrides[args] = response
                self.assert_rejected(model)

    def test_pr_fields_and_ordered_parents_are_not_inferred(self):
        vectors = ((('repository', 'full_name'), 'other/P2pKit'), (('repository', 'default_branch'), 'trunk'),
            (('number',), True), (('pull_request', 'number'), 702), (('pull_request', 'state'), 'closed'),
            (('pull_request', 'merged'), True), (('action',), 'edited'),
            (('pull_request', 'base', 'ref'), 'feature'), (('pull_request', 'base', 'repo', 'full_name'), 'other/P2pKit'),
            (('pull_request', 'base', 'sha'), OTHER), (('pull_request', 'head', 'sha'), OTHER),
            (('pull_request', 'head', 'repo', 'full_name'), 'not a repository'), (('pull_request', 'head'), None))
        for path, replacement in vectors:
            with self.subTest(path=path):
                model = GitModel()
                put(model.event, path, replacement)
                self.assert_rejected(model)
        for parents in ((HEAD + " " + BASE + "\n").encode(), (BASE + "\n").encode(),
                        (BASE + " " + HEAD + " " + OTHER + "\n").encode()):
            model = GitModel()
            model.overrides[("show", "-s", "--format=%P", MERGE)] = parents
            self.assert_rejected(model)

    def test_push_schedule_manual_mismatches_and_inputs_fail_closed(self):
        for name, value in (("ref", "refs/heads/feature"), ("after", OTHER), ("deleted", True), ("before", "short")):
            model = GitModel(event="push")
            model.event[name] = value
            self.assert_rejected(model)
        for profile, ref, cron in (("desktop", "refs/heads/main", "17 4 * * 1"),
                ("full", "refs/heads/feature", "17 4 * * 1"), ("full", "refs/heads/main", "18 4 * * 1")):
            model = GitModel(profile, "schedule")
            model.set_ref(ref)
            model.event["schedule"] = cron
            self.assert_rejected(model)
        for ref, event_ref, inputs in (("refs/tags/v1", "v1", {}),
                ("refs/heads/audit/complete-2026-09-04", "audit/complete-2026-09-04", {}),
                ("refs/heads/model-feature", "different", {}),
                ("refs/heads/model-feature", "model-feature", {"override": "true"})):
            model = GitModel(event="workflow_dispatch")
            model.set_ref(ref)
            model.event.update(ref=event_ref, inputs=inputs)
            self.assert_rejected(model)

    def test_policy_absence_for_non_pr_never_selects_initial(self):
        for profile, event in (("desktop", "push"), ("full", "push"), ("full", "schedule"),
                               ("desktop", "workflow_dispatch"), ("full", "workflow_dispatch")):
            with self.subTest(profile=profile, event=event):
                model = GitModel(profile, event)
                model.policies[BASE] = model.policies[MERGE] = None
                self.assert_rejected(model)
                self.assertNotIn(("ls-tree", "-z", HEAD, "--", I.POLICY_PATH), model.calls)

    def test_failed_short_nonbyte_wrong_mode_queries_are_not_successful_absence(self):
        valid = GitModel().entry(BASE)
        vectors = (RuntimeError(MODEL_TOKEN), None, "", b"\0", valid[:-1], valid.replace(b"100644", b"100755"),
            valid.replace(b"100644", b"120000"), valid.replace(b"blob", b"tree"), b"x" * 4097,
            valid.replace(I.POLICY_PATH.encode(), b"other-policy"), valid + valid)
        for number, reply in enumerate(vectors):
            with self.subTest(vector=number):
                model = GitModel(initial=True)
                model.overrides[("ls-tree", "-z", BASE, "--", I.POLICY_PATH)] = reply
                self.assert_rejected(model)
                self.assertNotIn(("ls-tree", "-z", HEAD, "--", I.POLICY_PATH), model.calls)

    def test_policy_size_complete_bytes_blob_hash_and_requeried_entry_are_mandatory(self):
        key = blob(PUBLIC_POLICY)
        vectors = ((('cat-file', '-s', key), b"0\n"), (('cat-file', '-s', key), b"-1\n"),
            (('cat-file', '-s', key), str(I.POLICY_LIMIT + 1).encode()),
            (('cat-file', 'blob', key), PUBLIC_POLICY[:-1]),
            (('cat-file', 'blob', key), b"x" * len(PUBLIC_POLICY)),
            (('cat-file', 'blob', key), b"x" * (I.POLICY_LIMIT + 1)))
        for args, reply in vectors:
            with self.subTest(args=args, size=len(reply)):
                model = GitModel()
                model.overrides[args] = reply
                self.assert_rejected(model)
        model = GitModel()
        entry = ("ls-tree", "-z", BASE, "--", I.POLICY_PATH)
        model.overrides[entry] = lambda args: model.default(args) if model.counts[args] == 1 else b""
        self.assert_rejected(model)

    def test_present_malformed_policy_and_expired_policy_never_fall_back(self):
        raw_vectors = (b"{", b"[]", b'{"schema":1,"schema":1}', b'{"schema":NaN}')
        for raw in raw_vectors:
            model = GitModel()
            model.policies[BASE] = raw
            self.assert_rejected(model)
            self.assertNotIn(("ls-tree", "-z", HEAD, "--", I.POLICY_PATH), model.calls)
        vectors = ((('schema',), True), (('repository',), 'other/P2pKit'), (('purpose',), 'other'),
            (('retentionDays',), 15), (('retentionDays',), True), (('retrievalOwner',), ''),
            (('recipient', 'sha256'), '0' * 64), (('recipient', 'fingerprint'), 'lowercase'),
            (('notBefore',), NOW + 1), (('expiresAt',), NOW))
        for path, replacement in vectors:
            with self.subTest(path=path):
                model = GitModel()
                value = copy.deepcopy(PUBLIC_VALUE)
                put(value, path, replacement)
                model.policies[BASE] = encoded(value)
                self.assert_rejected(model)
        for now in (PUBLIC_VALUE["notBefore"] - 1, PUBLIC_VALUE["expiresAt"], True):
            self.assert_rejected(GitModel(), now=now)

    def test_initial_foreign_ref_base_main_merge_tree_ancestry_and_policy_changes_fail(self):
        foreign = GitModel(initial=True, fork=True)
        self.assert_rejected(foreign)
        model = GitModel(initial=True)
        model.event["pull_request"]["head"]["ref"] = "other-foundation"
        self.assert_rejected(model)
        changed_base = GitModel(initial=True)
        changed_base.event["pull_request"]["base"]["sha"] = OTHER
        changed_base.trees[OTHER], changed_base.policies[OTHER] = TREE, None
        changed_base.overrides[("show", "-s", "--format=%P", MERGE)] = (OTHER + " " + HEAD + "\n").encode()
        self.assert_rejected(changed_base)
        for alias in (BASE, HEAD):
            model = GitModel(initial=True)
            if alias == HEAD:
                model.environment.update(GITHUB_SHA=HEAD, GITHUB_WORKFLOW_SHA=HEAD)
                model.overrides[("rev-parse", "--verify", "HEAD^{commit}")] = HEAD.encode() + b"\n"
                model.overrides[("show", "-s", "--format=%P", HEAD)] = (BASE + " " + HEAD + "\n").encode()
            else:
                model.event["pull_request"]["head"]["sha"] = BASE
                model.overrides[("show", "-s", "--format=%P", MERGE)] = (BASE + " " + BASE + "\n").encode()
            self.assert_rejected(model)
        vectors = ((('rev-parse', '--verify', 'refs/remotes/origin/main^{commit}'), OTHER.encode() + b'\n'),
            (('rev-parse', '--verify', BASE + '^{tree}'), OTHER.encode() + b'\n'),
            (('rev-parse', '--verify', HEAD + '^{tree}'), OTHER.encode() + b'\n'),
            (('merge-base', BASE, HEAD), OTHER.encode() + b'\n'),
            (('merge-base', BASE, HEAD), RuntimeError(MODEL_TOKEN)),
            (('ls-tree', '-z', HEAD, '--', I.POLICY_PATH), b''))
        for args, reply in vectors:
            with self.subTest(args=args):
                model = GitModel(initial=True)
                model.overrides[args] = reply
                self.assert_rejected(model)
        model = GitModel(initial=True)
        model.policies[HEAD] = PUBLIC_POLICY + b"\n"
        self.assert_rejected(model)

    def test_second_source_policy_and_initial_absence_observations_must_match(self):
        vectors = ((('rev-parse', '--verify', 'HEAD^{commit}'), OTHER.encode() + b'\n'),
            (('rev-parse', '--verify', MERGE + '^{tree}'), OTHER.encode() + b'\n'),
            (('status', '--porcelain=v1', '--untracked-files=all'), b'?? changed\n'),
            (('rev-parse', '--is-shallow-repository'), b'true\n'),
            (('cat-file', 'blob', blob(PUBLIC_POLICY)), PUBLIC_POLICY[:-1]))
        for args, changed in vectors:
            with self.subTest(args=args):
                model = GitModel()
                model.overrides[args] = lambda key, changed=changed: (
                    model.default(key) if model.counts[key] == 1 else changed)
                self.assert_rejected(model)
        model = GitModel(initial=True)
        args = ("ls-tree", "-z", BASE, "--", I.POLICY_PATH)
        model.overrides[args] = lambda key: b"" if model.counts[key] == 1 else GitModel().entry(BASE)
        self.assert_rejected(model)


class CallerControls(unittest.TestCase):
    def test_route_real_wrapper_retains_originals_rechecks_and_closes_before_output(self):
        for profile, initial in (("full", False), ("desktop", False), ("full", True), ("desktop", True)):
            with self.subTest(profile=profile, initial=initial):
                model = CallerModel(profile=profile, initial=initial)
                result = model.run()
                self.assertEqual(model.receipts, [("recipient-route.json", result.record),
                    ("original-event.json", result.original_event), ("original-policy.json", result.original_policy)])
                self.assertEqual(model.outputs, [{"origin": "initial" if initial else "ordinary",
                    "route_sha256": hashlib.sha256(result.record).hexdigest()}])
                self.assertIsNone(model.finalized_original)
                self.assertLess(model.log.index("signal.install"), model.log.index("clock.observe"))
                self.assertLess(model.log.index("clock.observe"), model.log.index("owner.allocate"))
                self.assertLess(model.log.index("owner.host"), model.log.index("owner.query"))
                self.assertLess(model.log.index("owner.finalize"), model.log.index("signal.restore"))
                self.assertLess(model.log.index("signal.restore"), model.log.index("output"))
                self.assertEqual((model.environment_reads, model.input_reads), (4, 4))
                self.assertEqual(model.log.count("clock.observe"), 1)
                self.assertEqual(model.log.count("clock.local"), 2)
                self.assertEqual(model.git.counts[("rev-parse", "--verify", "HEAD^{commit}")], 4)
                self.assertEqual(model.log[-3:], ["clock.checked", "environment", "inputs"])

    def test_route_fixed_supplier_failures_preserve_failure_and_prevent_output(self):
        for seam in ("signal.get", "signal.install", "clock.observe", "clock.local", "clock.checked",
                     "environment", "inputs", "owner.allocate", "owner.host", "owner.query", "owner.check",
                     "receipt.recipient-route.json", "receipt.original-event.json", "receipt.original-policy.json",
                     "owner.finalize", "signal.restore", "output"):
            with self.subTest(seam=seam):
                model = CallerModel()
                failure = KeyboardInterrupt("SYNTHETIC_CANCEL") if seam == "owner.query" else RuntimeError("MODEL_FAILURE")
                model.fail[seam] = failure
                with self.assertRaises(BaseException) as caught:
                    model.run()
                if seam == "clock.local":
                    # The maintained converter deliberately publishes a fixed
                    # safe code rather than the local sampler's private error.
                    self.assertIsInstance(caught.exception, R.clocks.ClockError)
                    self.assertEqual(str(caught.exception), "JOB_CLOCK_LOCAL_SAMPLE")
                else:
                    self.assertIs(caught.exception, failure)
                self.assertEqual(model.outputs, [])
                if "owner.host" in model.log and seam != "owner.finalize":
                    self.assertIn("owner.finalize", model.log)

    def test_route_unknown_failed_incomplete_close_or_restoration_never_succeeds(self):
        for flags in ((False, False, False), (True, True, False), (True, False, True)):
            model = CallerModel()
            model.close_flags = flags
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(model.outputs, [])
        model = CallerModel()
        first, close = RuntimeError("ORIGINAL_MODEL_FAILURE"), RuntimeError("MODEL_CLOSE_FAILURE")
        model.fail.update({"owner.host": first, "owner.finalize": close, "signal.restore": close})
        with self.assertRaises(RuntimeError) as caught:
            model.run()
        self.assertIs(caught.exception, first)
        self.assertEqual(model.log.count("signal.restore"), 2)
        self.assertEqual(model.outputs, [])

    def test_route_changed_environment_event_and_second_decision_are_rejected(self):
        for read in (2, 3, 4):
            model = CallerModel()
            model.mutate_environment = lambda count: (
                model.environment.update(GITHUB_RUN_ATTEMPT="3") if count == read else None)
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(len(model.outputs), 1 if read == 4 else 0)
        for read in (2, 3, 4):
            model = CallerModel()
            model.mutate_inputs = lambda count: (MODEL_ROOT, MODEL_TEMP,
                encoded({**model.git.event, "number": 702}) if count == read else encoded(model.git.event))
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(len(model.outputs), 1 if read == 4 else 0)
        model = CallerModel()
        args = ("rev-parse", "--verify", MERGE + "^{tree}")
        model.git.overrides[args] = lambda key: model.git.default(key) if model.git.counts[key] <= 2 else OTHER.encode() + b"\n"
        with self.assertRaises(I.AdmissionError):
            model.run()
        self.assertEqual(model.outputs, [])
        model = CallerModel()
        times = iter((NOW, NOW, PUBLIC_VALUE["expiresAt"]))
        model.wall_time = lambda: next(times)
        with self.assertRaises(I.AdmissionError) as caught:
            model.run()
        self.assertEqual(str(caught.exception), "RECIPIENT_POLICY_VALIDITY")
        self.assertEqual(model.outputs, [])

    def test_real_scope_uses_distinct_raw_and_local_epochs_without_resetting(self):
        model = CallerModel()
        with model.suppliers(), candidate_call():
            scope = R._Scope()
            scope.start()
            first_bounds = (scope.work_end_ns, scope.final_end_ns, scope.local_deadlines)
            self.assertEqual(first_bounds[:2], (RAW_START + 75 * R.clocks.NS, RAW_START + 120 * R.clocks.NS))
            self.assertLess(scope.local_deadlines[0], LOCAL_START + 75)
            self.assertLess(scope.local_deadlines[1], LOCAL_START + 120)
            model.ns = scope.work_end_ns - 1
            scope.check()
            model.ns = scope.work_end_ns
            with self.assertRaises(I.AdmissionError):
                scope.check()
            scope.check(final=True)
            model.ns = scope.final_end_ns
            with self.assertRaises(I.AdmissionError):
                scope.check(final=True)
            self.assertEqual(first_bounds, (scope.work_end_ns, scope.final_end_ns, scope.local_deadlines))
            scope.restore()

    def test_cancellation_is_sticky_and_restores_both_original_handlers(self):
        model = CallerModel()
        with model.suppliers(), candidate_call():
            scope = R._Scope()
            scope.start()
            model.installed[signal.SIGTERM](signal.SIGTERM, None)
            with self.assertRaises(KeyboardInterrupt) as first:
                scope.check()
            with self.assertRaises(KeyboardInterrupt) as second:
                scope.check_cancel()
            with self.assertRaises(KeyboardInterrupt) as final:
                scope.restore()
            self.assertIs(first.exception, second.exception)
            self.assertIs(first.exception, final.exception)
            self.assertTrue(scope.restored)
            self.assertEqual(model.log.count("signal.restore"), 2)

    def test_route_credential_domain_is_rejected_without_real_environment_access(self):
        for name in (R.TOKEN, *R.initial.provider_environment.SERVICE_FIELDS, "ACTIONS_CACHE_URL",
                     "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "GH_TOKEN", "GITHUB_TOKEN"):
            with self.subTest(name=name):
                model = CallerModel()
                model.environment[name] = MODEL_TOKEN
                with self.assertRaises(I.AdmissionError) as caught:
                    model.run()
                self.assertNotIn(MODEL_TOKEN, str(caught.exception))
                self.assertNotIn("owner.allocate", model.log)
                self.assertEqual(model.outputs, [])
        for name in (R.TOKEN, "ACTIONS_RUNTIME_TOKEN", "GH_TOKEN"):
            model = CallerModel()
            original_output = model.output

            def reinsert(values):
                original_output(values)
                model.environment[name] = MODEL_TOKEN

            model.output = reinsert
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(len(model.outputs), 1)

    def test_gate_uses_canonical_loader_real_gate_type_single_claim_and_fresh_checks(self):
        for profile in ("full", "desktop"):
            model = CallerModel(profile=profile, gate=True)
            result = model.run()
            self.assertEqual(result, encoded(model.current_value))
            self.assertEqual(model.outputs, [{"initial_gate_ready": "true",
                "initial_gate_sha256": hashlib.sha256(result).hexdigest()}])
            self.assertEqual((model.log.count("current.loader"), model.log.count("current.acquire"), model.claim_count), (1, 1, 1))
            self.assertEqual(model.checked_reads, 4)
            self.assertLess(model.log.index("current.checked"), model.log.index("current.claim"))
            self.assertLess(model.log.index("current.claim"), model.log.index("signal.restore"))
            self.assertLess(model.log.index("signal.restore"), model.log.index("output"))
            self.assertEqual(model.log[-3:], ["current.checked", "current.eligibility", "current.record"])
            self.assertNotIn(R.TOKEN, model.environment)
            self.assertEqual(model.receipts, [])  # Gate originals belong to its modeled current owner, not route receipts.

    def test_gate_supplier_failures_and_unknown_current_close_prevent_ready_output(self):
        for seam in ("current.loader", "current.acquire", "current.checked", "current.eligibility",
                     "current.record", "current.claim", "signal.restore", "output"):
            with self.subTest(seam=seam):
                model = CallerModel(gate=True)
                failure = RuntimeError("MODEL_PRIVATE_FAILURE")
                model.fail[seam] = failure
                with self.assertRaises(RuntimeError) as caught:
                    model.run()
                self.assertIs(caught.exception, failure)
                self.assertEqual(model.outputs, [])
        model = CallerModel(gate=True)
        model.current_closed = False
        with self.assertRaises(I.AdmissionError):
            model.run()
        self.assertEqual(model.outputs, [])

    def test_gate_rejects_wrong_eligibility_type_scope_role_source_profile_and_context(self):
        vectors = (("current", ("scope",), "wrong"), ("current", ("kind",), "worker"),
            ("current", ("profile",), "full"), ("current", ("role",), "macos-arm64"),
            ("current", ("identitySha256",), "a" * 64), ("current", ("matchSha256",), "a" * 64),
            ("current", ("source", "tree"), OTHER), ("current", ("reviewed", "commit"), OTHER),
            ("eligibility", ("scope",), "WORKER_AUTHORITY"), ("eligibility", ("stage",), "stage1"),
            ("eligibility", ("source", "commit"), OTHER), ("eligibility", ("github", "job"), "verify"),
            ("eligibility", ("github", "runAttempt"), "1"), ("eligibility", ("github", "workflow"), I.PROFILES["full"][0]),
            ("eligibility", ("github", "workflowSha"), OTHER), ("eligibility", ("github", "runnerArch"), "ARM64"))
        for target, path, replacement in vectors:
            with self.subTest(target=target, path=path):
                model = CallerModel(gate=True)
                put(model.current_value if target == "current" else model.eligible, path, replacement)
                if target == "eligibility":
                    model.current_value["matchSha256"] = hashlib.sha256(encoded(model.eligible)).hexdigest()
                    if path == ("source", "commit"):
                        model.current_value["source"] = copy.deepcopy(model.eligible["source"])
                with self.assertRaises(I.AdmissionError):
                    model.run()
                self.assertEqual(model.outputs, [])
        model = CallerModel(gate=True)
        model.native.initial_ordinary_eligibility = lambda _current: SimpleNamespace(record=encoded(model.eligible))
        with self.assertRaises(I.AdmissionError):
            model.run()
        self.assertEqual(model.outputs, [])

    def test_gate_refuses_replayed_claim_wrong_checked_handle_and_claim_substitution(self):
        for mutation in ("replay", "checked", "claim"):
            model = CallerModel(gate=True)
            if mutation == "replay":
                model.claimed = True
            elif mutation == "checked":
                model.native.checked_initial_ordinary = lambda _current: object()
            else:
                model.native.claim_initial_ordinary = lambda _current, _purpose: object()
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(model.outputs, [])

    def test_gate_unconsumed_reinserted_service_or_changed_context_never_succeeds(self):
        model = CallerModel(gate=True)
        model.consume_token = False
        with self.assertRaises(I.AdmissionError):
            model.run()
        self.assertEqual(model.outputs, [])
        for name in (R.TOKEN, "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_EVENT_PATH"):
            for read in (2, 3):
                model = CallerModel(gate=True)
                model.mutate_environment = lambda count: model.environment.update(
                    {name: MODEL_TOKEN if name == R.TOKEN else "changed"}) if count == read else None
                with self.assertRaises(I.AdmissionError):
                    model.run()
                self.assertEqual(len(model.outputs), 1 if read == 3 else 0)
        for name in (*R.initial.provider_environment.SERVICE_FIELDS, "GITHUB_TOKEN"):
            model = CallerModel(gate=True)
            model.environment[name] = MODEL_TOKEN
            with self.assertRaises(I.AdmissionError) as caught:
                model.run()
            self.assertNotIn(MODEL_TOKEN, str(caught.exception))
            self.assertNotIn("current.acquire", model.log)
        for name in ("ACTIONS_RUNTIME_TOKEN", "GITHUB_TOKEN"):
            model = CallerModel(gate=True)
            original_output = model.output

            def reinsert(values):
                original_output(values)
                model.environment[name] = MODEL_TOKEN

            model.output = reinsert
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(len(model.outputs), 1)

    def test_late_cancelled_changed_currency_and_postoutput_failures_do_not_return_success(self):
        model = CallerModel()
        original_finalize = model._finalize

        def expire_at_close(original):
            original_finalize(original)
            model.ns = model.scope.work_end_ns

        model._finalize = expire_at_close
        with self.assertRaises(I.AdmissionError):
            model.run()
        self.assertEqual(model.outputs, [])
        for read in (2, 3, 4):
            model = CallerModel(gate=True)
            model.mutate_current = lambda count: setattr(model, "current_valid", False) if count == read else None
            with self.assertRaises(I.AdmissionError):
                model.run()
            self.assertEqual(len(model.outputs), 1 if read == 4 else 0)
        for gate, cancellation in ((False, False), (False, True), (True, False), (True, True)):
            model = CallerModel(gate=gate)
            original_output = model.output

            def expire_after_output(values):
                original_output(values)
                if cancellation:
                    model.scope.cancelled.append(signal.SIGTERM)
                else:
                    model.ns = model.scope.work_end_ns

            model.output = expire_after_output
            with self.assertRaises(KeyboardInterrupt if cancellation else I.AdmissionError):
                model.run()
            # Bytes alone are not ready: wrapper/step success is also mandatory.
            self.assertEqual(len(model.outputs), 1)


class OutputControls(unittest.TestCase):
    def test_two_closed_output_sets_are_exact_and_follow_known_file_close(self):
        vectors = (({"origin": "ordinary", "route_sha256": "a" * 64},
                    b"origin=ordinary\nroute_sha256=" + b"a" * 64 + b"\n"),
                   ({"origin": "initial", "route_sha256": "b" * 64},
                    b"origin=initial\nroute_sha256=" + b"b" * 64 + b"\n"),
                   ({"initial_gate_ready": "true", "initial_gate_sha256": "c" * 64},
                    b"initial_gate_ready=true\ninitial_gate_sha256=" + b"c" * 64 + b"\n"))
        for values, expected in vectors:
            model = OutputModel()
            self.assertIsNone(model.append(values))
            self.assertEqual(model.writes, [expected])
            self.assertEqual(model.calls, ["path", "resolve", "lstat", "open", "fstat", "write", "fsync", "lstat", "close"])

    def test_output_field_names_types_values_and_control_characters_are_closed(self):
        vectors = (None, {}, {"origin": "ordinary"}, {"origin": "ordinary", "route_sha256": "A" * 64},
            {"origin": "ordinary\ninitial_gate_ready=true", "route_sha256": "a" * 64},
            {"origin": "ordinary", "route_sha256": "a" * 64 + "\n"},
            {"origin": "ordinary", "route_sha256": "a" * 64, "initial_gate_ready": "true"},
            {"origin": "ordinary", "route_sha256": 1},
            {"initial_gate_ready": True, "initial_gate_sha256": "a" * 64},
            {"initial_gate_ready": "false", "initial_gate_sha256": "a" * 64},
            {"initial_gate_ready": "true", "initial_gate_sha256": "short"},
            {"other\nname": "true", "initial_gate_sha256": "a" * 64})
        for number, values in enumerate(vectors):
            with self.subTest(vector=number):
                model = OutputModel()
                with self.assertRaises(I.AdmissionError):
                    model.append(values)
                self.assertEqual(model.calls, [])
                self.assertEqual(model.writes, [])

    def test_output_missing_linked_wrong_owner_and_changed_files_fail(self):
        values = {"origin": "ordinary", "route_sha256": "a" * 64}
        for mutation in ("missing", "relative", "resolved", "directory", "links", "owner", "opened", "after"):
            model = OutputModel()
            if mutation == "missing":
                model.path = ""
            elif mutation == "relative":
                model.path = "relative-output"
            elif mutation == "resolved":
                model.resolved = False
            else:
                fields = list(model.info)
                if mutation == "directory":
                    fields[0] = stat.S_IFDIR | 0o700
                elif mutation == "links":
                    fields[3] = 2
                elif mutation == "owner":
                    fields[4] = 43
                else:
                    fields[1] += 1
                changed = os.stat_result(fields)
                if mutation == "opened":
                    model.opened = changed
                elif mutation == "after":
                    model.after = changed
                else:
                    model.info = changed
            with self.subTest(mutation=mutation), self.assertRaises(I.AdmissionError):
                model.append(values)
            self.assertEqual(len(model.writes), 1 if mutation == "after" else 0)
            if "open" in model.calls:
                self.assertEqual(model.calls[-1], "close")

    def test_short_write_io_failure_and_failed_close_never_report_success(self):
        values = {"initial_gate_ready": "true", "initial_gate_sha256": "a" * 64}
        model = OutputModel()
        model.short = True
        with self.assertRaises(I.AdmissionError):
            model.append(values)
        self.assertEqual(model.calls[-1], "close")
        self.assertNotIn("fsync", model.calls)
        for seam in ("resolve", "open", "fstat", "write", "fsync", "close"):
            model = OutputModel()
            failure = OSError("MODEL_PRIVATE_DETAIL")
            model.fail[seam] = failure
            with self.subTest(seam=seam), self.assertRaises(OSError) as caught:
                model.append(values)
            self.assertIs(caught.exception, failure)
            if "fstat" in model.calls:
                self.assertEqual(model.calls[-1], "close")

    def test_main_command_is_fixed_and_failure_logs_no_original_or_token(self):
        vectors = (["route", "source-mode", "--profile", "desktop"],
                   ["route", "initial-gate", "--profile", "full"],
                   ["route", "source-mode", "--profile", "unknown"],
                   ["route", "source-mode", "--profile", "desktop", "extra"])
        for argv in vectors:
            outputs, calls = [], []

            def fail(profile):
                calls.append(profile)
                raise RuntimeError(MODEL_TOKEN)

            def write(fd, raw):
                self.assertEqual(fd, 2)
                outputs.append(raw)
                return len(raw)

            model_sys = SimpleNamespace(flags=SimpleNamespace(isolated=1, no_site=1),
                                        dont_write_bytecode=True, argv=argv)
            with patch.object(R, "sys", model_sys), patch.object(R, "os", SimpleNamespace(write=write)), \
                    patch.object(R, "source_mode", fail), patch.object(R, "initial_gate", fail), candidate_call():
                self.assertEqual(R.main(), 125)
            self.assertEqual(outputs, [b"RECIPIENT_ROUTING=HOLD; NO_WORKER_AUTHORITY\n"])
            self.assertEqual(calls, [argv[3]] if len(argv) == 4 and argv[3] in ("full", "desktop") else [])
            self.assertNotIn(MODEL_TOKEN.encode(), b"".join(outputs))


if __name__ == "__main__":
    unittest.main()
