#!/usr/bin/env python3
"""Closed JVM worker models/source controls, NOT hosted execution acceptance.

All service, native, current and canonical originals below are explicitly
synthetic. Only committed public policy, tiny private fixture files and supplied
byte graphs are read. Existing fixture BUILDERS are reused, never their tests.
No resolver, Gradle, process, GPG, network, native API or 1,066-file reader runs.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import copy
import ctypes  # Initialize stdlib before forbidding native-loader audit events.
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_test_identity as I
import hosted_initial_ordinary_identity as INITIAL
import hosted_jvm_library_custody as JVM
import hosted_job_clock as CLOCK
import hosted_dependency_seed_files as SEED
import hosted_dependency_cache as CACHE


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AF = load("jvm_adapter_fixture", Path(__file__).with_name("hosted-initial-ordinary-adapter-test.py"))
BF = load("jvm_job_time_fixture", Path(__file__).with_name("hosted-full-job-budget-test.py"))
N = load("jvm_initial_registry_subject", ROOT / "scripts/run-hosted-initial-ordinary.py")
C, H, F, A, B = AF.C, AF.H, AF.F, AF.M.A, AF.B
NS = B.NS
SOURCE, TREE, BASE, HEAD = (char * 40 for char in "1234")
HOSTS = {"linux-x64": ("Linux", "X64", "ubuntu-latest"),
         "windows-x64": ("Windows", "X64", "windows-latest")}
# Independent expected producer cohorts, not new JVM hosts or execution rights.
BOOTSTRAP_SELECTIONS = (
    ("desktop-linux-x64", "desktop", "linux-x64", "Linux", "X64"),
    ("desktop-windows-x64", "desktop", "windows-x64", "Windows", "X64"),
    ("desktop-macos-arm64", "desktop", "macos-arm64", "macOS", "ARM64"),
    ("desktop-macos-x64", "desktop", "macos-x64", "macOS", "X64"),
    ("full-macos-arm64", "full", "macos-arm64", "macOS", "ARM64"),
    ("full-macos-x64", "full", "macos-x64", "macOS", "X64"),
)
ERRORS = (I.AdmissionError, C.ControllerError, B.BudgetError, SEED.SeedError,
          JVM.JvmCustodyError, CLOCK.ClockError)


def decoded(raw):
    return I.parse(raw, 4 * 1024 * 1024)


def pretty(value):
    # The canonical executor deliberately does not use identity.encoded.
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


class ModelGit:
    def __init__(self):
        self.head, self.main, self.tree_value = SOURCE, BASE, TREE
        self.parents_value, self.dirty, self.root_correct = [BASE, HEAD], False, True
        self.message_value = b"Synthetic merge, not a release request\n"
        self.policies = {SOURCE: F.POLICY, BASE: F.POLICY}
        self.requested = []

    def root_matches(self): return self.root_correct
    def clean(self): return not self.dirty
    def commit(self, ref): return self.head if ref == "HEAD" else self.main
    def tree(self, _commit): return self.tree_value
    def parents(self, _commit): return list(self.parents_value)
    def message(self, _commit): return self.message_value

    def policy(self, commit):
        self.requested.append(commit)
        I.require(commit in self.policies, "MISSING_TRUSTED_RECIPIENT_POLICY")
        raw = self.policies[commit]
        return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest(), raw


class OrdinaryModel:
    def __init__(self, role="linux-x64", event="push"):
        self.role, self.git = role, ModelGit()
        system, arch, _ = HOSTS[role]
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": system, "RUNNER_ARCH": arch,
            "GITHUB_JOB": "jvm-library-checks", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_NAME": event, "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE,
            "GITHUB_WORKFLOW_SHA": SOURCE, "GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": "/model/event.json"}
        self.event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"}}
        if event == "push":
            self.event.update(ref="refs/heads/main", after=SOURCE, before=BASE, deleted=False)
        elif event == "pull_request":
            self.env["GITHUB_REF"] = "refs/pull/17/merge"
            self.event.update(number=17, action="synchronize", pull_request={"number": 17, "state": "open",
                "merged": False, "base": {"sha": BASE, "ref": "main", "repo": {"full_name": I.REPOSITORY}},
                "head": {"sha": HEAD, "ref": "work/jvm-model", "repo": {"full_name": "fixture-fork/P2pKit"}}})
        elif event == "workflow_dispatch":
            self.env["GITHUB_REF"] = "refs/heads/work/jvm-model"
            self.event.update(ref="work/jvm-model", inputs={})
        elif event == "schedule":
            self.event["schedule"] = "17 4 * * 1"
        else:
            raise AssertionError("CLOSED_MODEL_EVENT")
        self.env["GITHUB_WORKFLOW_REF"] = I.REPOSITORY + "/" + I.JVM_WORKER[0] + "@" + self.env["GITHUB_REF"]

    def admit(self):
        return I._admit(JVM.PROFILE, self.env, I.encoded(self.event), self.git, F.NOW)


def bound_clock(role):
    return CLOCK.ClockIdentity(role, CLOCK.DOMAINS[role], 10_000_000 if role == "windows-x64" else NS)


def responses(admitted, role, *, elapsed=120):
    values = BF.model_responses(admitted, elapsed=elapsed)
    selector = HOSTS[role][2]
    values["jobs"] = BF.replace_body(values["jobs"], lambda body:
        body["jobs"][0].update(name="JVM libraries (" + selector + ")", labels=[selector]))
    for name, raw in values.items():
        value = decoded(raw)
        value.update(schema=2, profile=JVM.PROFILE, clock=B.clock_value(bound_clock(role)),
                     clockDomain=bound_clock(role).domain)
        values[name] = I.encoded(value)
    return values


def ordinary_budget(role="linux-x64", *, elapsed=120):
    admitted = OrdinaryModel(role).admit()
    return B.derive(admitted, responses(admitted, role, elapsed=elapsed), BF.provenance(), clock=bound_clock(role))


@contextmanager
def initial_fixture(role="linux-x64"):
    # Reuse only the FULL fixture's same CI run402 and its four histories, then
    # explicitly select the actual JVM job through the new C2 matcher.
    with AF.fixture("full", "macos-arm64") as values:
        model = values["model"]
        system, arch, selector = HOSTS[role]
        model.env.update(GITHUB_JOB="jvm-library-checks", RUNNER_OS=system, RUNNER_ARCH=arch)
        model.clock = bound_clock(role)
        model.ns = 1000 * NS
        model.fence = AF.M.O.Fence(AF.M.O.prelude(CLOCK.Reading(model.clock, model.ns)),
            minimum=model.ns, cancelled=lambda: None)
        model.context = A._context(model.env, I.encoded(model.event), "worker", F.FIRST2)
        model.bodies["jobs"]["jobs"][0].update(name="JVM libraries (" + selector + ")", labels=[selector])
        match = F.check_jvm(model.declaration, F.jvm_observation(model.declaration, role), model.histories)
        bound = INITIAL.bind_jvm_worker_match(match, comment_raw=I.encoded(model.comment),
            event_raw=I.encoded(model.event), policy_raw=F.POLICY, now=F.NOW)
        values.update(bound=bound, match=match)
        values["context"].update(observed=copy.deepcopy(model.context), eventSha256=H.digest(bound.original_event),
            session=r"C:\model\source" if role == "windows-x64" else "/model/source")
        values["context"]["window"]["clock"] = B.clock_value(model.clock)
        values["start"]["clock"] = B.clock_value(model.clock)
        yield values


def retained(bound, *, raw=None, event=None, policy=None, key=None, now=F.NOW):
    return INITIAL.retained_jvm_identity(bound.record if raw is None else raw,
        bound.original_event if event is None else event, bound.original_policy if policy is None else policy,
        bound.public_key if key is None else key, now=now)


def cache_inputs():
    # One harmless modeled artifact hash, not a real dependency or cache cohort.
    xml = ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' + SEED.authority.NAMESPACE +
        '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="' + SEED.authority.SCHEMA_LOCATION +
        '"><configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures>' +
        '</configuration><components><component group="org.fixture" name="model" version="1.0">' +
        '<artifact name="model.jar"><sha256 value="' + H.digest(b"MODEL_NOT_A_DEPENDENCY") +
        '"/></artifact></component></components></verification-metadata>').encode("ascii")
    compiled = SEED.authority.parse_allowlist(xml)
    inputs = {"files": {name: H.digest(xml if index == 0 else name.encode("ascii"))
        for index, name in enumerate(SEED.INPUTS)}, "allowlistSha256": compiled.authority_sha256,
        "artifacts": len(compiled.artifacts), "components": compiled.component_count, "policy": SEED.policy()}
    return compiled, inputs


def cohort_fixture(bound, role):
    session = Path("/model/runner-temp/p2pkit-test-jvm-library-123-1-" + role)
    path = SEED.stage_path(session, JVM.PROFILE, role, admitted_raw=bound.record)
    compiled, inputs = cache_inputs()
    stage = SEED.stage_record(bound.record, JVM.PROFILE, role, path,
        SimpleNamespace(identity=(1, 2)), SimpleNamespace(identity=(1, 3)), inputs)
    raw = I.encoded(stage)
    intent = SEED.seed_intent(bound.record, JVM.PROFILE, role, path, raw, inputs)
    plan = CACHE.make_plan(bound.record, raw, compiled, inputs, session=session, profile="desktop", role=role, mode="consume")
    return SimpleNamespace(session=session, path=path, compiled=compiled, inputs=inputs, stage=stage,
                           staging_raw=raw, intent=intent, plan=plan)


class BootstrapModelGit(ModelGit):
    """Only two additional fixed Git answers; never a query subprocess."""
    def query(self, *args):
        if args == ("rev-parse", "--is-shallow-repository"):
            return b"false\n"
        if args == ("merge-base", BASE, SOURCE):
            return BASE.encode("ascii") + b"\n"
        raise AssertionError("UNEXPECTED_BOOTSTRAP_MODEL_QUERY")


def bootstrap_identity_fixture(row, *, initial):
    """Use real pure binders on synthetic inputs, never earlier test methods."""
    name, _profile, _role, system, arch = row
    if initial:
        declaration = F.stage1()
        observed = F.observation1(declaration, name)
        match = F.check1(declaration, observed)
        event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
            "ref": SEED.initial_bootstrap.stages.SOURCE_REF,
            "inputs": {"selection": name, "expected_sha": F.H1, "expected_tree": F.T1}}
        return SEED.initial_bootstrap.bind_worker_match(match, event_raw=I.encoded(event),
            policy_raw=F.POLICY, now=F.DONE1)
    ref = "refs/heads/work/bootstrap-model"
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY,
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": system, "RUNNER_ARCH": arch,
        "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": ref, "GITHUB_SHA": SOURCE,
        "GITHUB_WORKFLOW_SHA": SOURCE,
        "GITHUB_WORKFLOW_REF": I.REPOSITORY + "/.github/workflows/dependency-cache-bootstrap.yml@" + ref}
    event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
        "ref": ref, "inputs": {"selection": name, "expected_sha": SOURCE, "expected_tree": TREE}}
    return SEED.bootstrap._admit(env, I.encoded(event), BootstrapModelGit(), F.NOW)


def bootstrap_cohort_fixture(bound, profile, role):
    """Pure stage/plan DATA only; no directories, producer or provider owner."""
    value = decoded(bound.record)
    run, attempt = value["github"]["runId"], value["github"]["runAttempt"]
    root = Path("/model/runner-temp")
    if type(bound) is SEED.initial_bootstrap.InitialBootstrapIdentity:
        session = root / ("p2pkit-initial-recipient-" + run + "-" + attempt + "-worker-recipient-initializer")
    else:
        session = root / ("p2pkit-cache-originals-" + run + "-" + attempt + "-" +
                          value["selection"] + "-productive") / "initializer"
    path = SEED.stage_path(session, profile, role, admitted_raw=bound.record)
    compiled, inputs = cache_inputs()
    stage = SEED.stage_record(bound.record, profile, role, path,
        SimpleNamespace(identity=(1, 2)), SimpleNamespace(identity=(1, 3)), inputs)
    raw = I.encoded(stage)
    intent = SEED.seed_intent(bound.record, profile, role, path, raw, inputs)
    plan = CACHE.make_plan(bound.record, raw, compiled, inputs, session=session,
                          profile=profile, role=role, mode="bootstrap")
    return SimpleNamespace(session=session, path=path, compiled=compiled, inputs=inputs, stage=stage,
                           staging_raw=raw, intent=intent, plan=plan)


@contextmanager
def registry_model(values, **changes):
    """Explicit registry DATA model; native close/return validators are not run."""
    current = N.InitialOrdinaryCurrent()
    owner, closed = SimpleNamespace(), SimpleNamespace(raw=b"MODEL_CLOSED_OWNER")
    first_raw = I.encoded({"model": "original first session"})
    child_raw = I.encoded({"firstSessionSha256": H.digest(first_raw)})
    native = SimpleNamespace(result_raw=b"MODEL_NATIVE_RETURN",
        stdout_raw=I.encoded({"terminalSha256": H.digest(child_raw)}))
    context_raw = I.encoded(values["context"])
    qualifications = tuple(N.qualification.ProductiveQualification(I.encoded({"model": n}), history)
                           for n, history in enumerate(values["model"].histories))
    record = AF.current_data(values["bound"], values["model"].clock.role)
    record.update(contextSha256=H.digest(context_raw), ownerCloseSha256=H.digest(closed.raw),
        nativeReturnSha256=H.digest(native.result_raw), qualifications=[H.digest(q.record) for q in qualifications])
    state = N._CurrentState(current, owner, closed, native, context_raw, I.encoded(record), values["match"],
        values["bound"], qualifications, b"MODEL_PACKET_LOCATORS", (), (),
        tuple((name, ("MODEL_" + name).encode("ascii")) for name in N.CURRENT_KEYS), first_raw, child_raw,
        "SYNTHETIC_UNUSED_TOKEN", None, {"failed": False, "latest": current, "claims": set()})
    state = replace(state, **changes)
    frozen = tuple(getattr(state, name) for name in state.__dataclass_fields__)
    with patch.dict(N._RETURNS, {id(current): (state, frozen)}, clear=True), \
            patch.object(N, "_checked_close", return_value=owner), \
            patch.object(N, "_checked_native", return_value=native):
        yield current, state


class MemoryDirectory:
    """Explicit supplied file/owner model; no native directory authority."""
    def __init__(self, owner, path):
        self.owner, self.path = owner, Path(path)
        self.identity = (1, len(owner.directories) + 1)

    def verify(self):
        assert self.owner.directories[self.path] is self
        return SimpleNamespace(identity=self.identity)

    def snapshot(self, **_bounds):
        self.owner.snapshots.append(self.path)
        before = self.owner.members(self.path)
        class Snapshot:
            entries = {name: SimpleNamespace(size=len(raw), is_directory=False) for name, raw in before.items()}
            def open_file(_self, name): return io.BytesIO(before[name])
            def verify(_self):
                if self.owner.members(self.path) != before:
                    raise JVM.JvmCustodyError("MODEL_SNAPSHOT_CHANGED")
            def close(_self): pass
        return Snapshot()

    def close(self): pass


class MemoryOwner(C.PrivateOwner):
    def __init__(self):
        super().__init__()
        self.files, self.directories, self.reads, self.snapshots = {}, {}, [], []

    def mkdir(self, path):
        path = Path(path)
        if path not in self.directories:
            self.directories[path] = MemoryDirectory(self, path)
        return self.directories[path]

    def put(self, path, raw):
        path = Path(path)
        for parent in reversed(path.parents):
            self.mkdir(parent)
        self.files[path] = raw if type(raw) is bytes else I.encoded(raw)
        return self.files[path]

    def child(self, parent, name, _end, create=False):
        parent.verify()
        path = parent.path / name
        if create:
            assert path not in self.directories
            self.mkdir(path)
        return self.directories[path]

    def open(self, path): return self.directories[Path(path)]

    def read(self, parent, name, _end, maximum=4 * 1024 * 1024):
        parent.verify()
        raw = self.files[parent.path / name]
        assert len(raw) <= maximum
        self.reads.append(parent.path / name)
        return raw

    def write(self, parent, name, raw, _end):
        assert parent.path / name not in self.files
        return self.put(parent.path / name, raw)

    def members(self, root):
        return {path.relative_to(root).as_posix(): raw for path, raw in self.files.items() if root in path.parents}

    def names(self, _owner, path, _end):
        return sorted({member.split("/", 1)[0] for member in self.members(path)} |
                      {p.name for p in self.directories if p.parent == path and p != path})


class ReportFixture(MemoryOwner):
    """Synthetic canonical/native graph consumed by the REAL JVM leaf parser."""
    def __init__(self, role="linux-x64", *, reserve=True):
        super().__init__()
        self.profile, self.role, self.request = JVM.PROFILE, role, None
        self.budget = ordinary_budget(role)
        self.raw_ns = 10010 * NS
        self.end = time.monotonic() + 60
        self.path = Path("/model/runner-temp/jvm-session")
        self.state_path = self.path / "state"
        self.private = self.mkdir(self.path)
        self.evidence = self.mkdir(self.path / "evidence")
        self.commands = self.mkdir(self.evidence.path / "commands")
        self.mkdir(self.state_path)
        self.mkdir(self.state_path / "evidence")
        self.context = {"schema": 1, "scope": "CLOSED_ORDINARY_TEST_CONTROLLER", "profile": JVM.PROFILE,
            "role": role, "root": str(ROOT), "session": str(self.path), "job": "f" * 32,
            "source": {"commit": SOURCE, "tree": TREE}, "jobBudgetSha256": self.budget.sha256,
            "python": "/model/python.exe" if role == "windows-x64" else "/model/python3",
            "canonicalSources": {name: "a" * 64 for name in C.CANONICAL_NAMES},
            "kind": "gradle", "command": [*JVM.TASKS, "--continue", "--console=plain"]}
        self.canonical = {"id": "a" * 32, "root": str(ROOT), "host": role,
            "gradleHome": str(self.state_path / "gradle-home"), "preexistingOutputPaths": [],
            "source": {**self.context["source"], "status": "", "diffSha256": H.digest(b"")}}
        self.run_context_raw, self.canonical_context_raw = I.encoded(self.context), pretty(self.canonical)
        self.put(self.path / "run-context.json", self.run_context_raw)
        self.put(self.state_path / "context.json", self.canonical_context_raw)
        self.api = {**vars(C), "os": SimpleNamespace(name="nt"), "seed_names": self.names}
        self.inputs = None
        if reserve:
            with patch.object(JVM.uuid, "uuid4", return_value=SimpleNamespace(hex="b" * 32)):
                self.request_raw = JVM.reserve(self, self.api)
            self.request = JVM.request_data(self.request_raw, self.run_context_raw, self.canonical_context_raw)

    def now_raw(self):
        self.raw_ns += 1000
        return self.raw_ns

    def window(self, stage, seconds):
        assert stage in ("productive", "collect") and seconds in (30, 120)
        return self.end

    def check(self, finalizing=False):
        assert not self.unknown

    def check_window(self, stage, _end):
        assert self.now_raw() < self.budget.fence(stage)

    def launch(self, argv, pid, *, outer=False):
        value = {"requestedArgv": argv, "resolvedArgv": argv, "cwd": str(ROOT), "created": True, "pid": pid}
        if self.role == "windows-x64":
            app = "C:\\Windows\\System32\\cmd.exe" if not outer else argv[0]
            value.update(api="CreateProcessW", resumed=True, jobAssignedBeforeResume=True, batch=not outer,
                applicationName=app, commandLine=C.processes.subprocess.list2cmdline(argv) if outer else
                C.processes.batch_command_line(app, argv))
        else:
            value.update(api="subprocess.Popen", shell=False, executable=argv[0])
        if outer:
            value["outputMode"] = "caller-owned-native-files" if self.role == "windows-x64" else "caller-owned-files"
        return value

    def native_owner(self, invocation, launches):
        return {"backend": JVM.BACKENDS[self.role], "scope": "kernel-job-no-breakaway-kill-on-close" if
            self.role == "windows-x64" else "controlled-marker-inheriting-descendants",
            "job": self.canonical["id"], "invocation": invocation, "discoveryErrors": [], "launches": launches,
            "startedIdentities": [{"pid": row["pid"], "creationFileTime" if self.role == "windows-x64" else
                                   "startTicks": 100 + row["pid"]} for row in launches]}

    def originals(self, *, exit_code=0, roots=6, stale=False):
        request, context = self.request, self.context
        invocation = request["owner"]["productInvocation"]
        prefix = self.state_path / "evidence" / invocation
        self.mkdir(prefix)
        start = {"schema": 1, "id": invocation, "purpose": "ordinary-jvm-library", "kind": "gradle",
            "requestedArgv": list(request["command"]), "cwd": str(ROOT), "wrapper": request["wrapper"],
            "host": self.role, "jobId": self.canonical["id"], "gradleHome": request["home"],
            "evidenceDirectory": str(prefix), "controllerPid": 101, "startedUtc": "2026-09-27T00:00:00Z",
            "sourceBefore": None, "sourceAfter": None, "productExitCode": None, "stopExitCode": None,
            "finalExitCode": 125, "errors": [], "sourceUnchanged": False, "ancestorInvocationIds": ["c" * 32]}
        executed = [request["wrapper"], *C.audit.gradle_arguments(request["command"])]
        stop = [request["wrapper"], "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
                "-Dorg.gradle.jvmargs=" + C.audit.JVM_ARGUMENTS]
        reports, content = [], {}
        for root in JVM.ROOTS[:roots]:
            name, raw = root + "synthetic.txt", ("MODEL REPORT " + root).encode("ascii")
            row = {"source": name, "sha256": H.digest(raw), "bytes": len(raw),
                "classification": "preexisting-unchanged" if stale else "changed-since-admission"}
            if not stale:
                row["retained"] = "reports/" + name
                content[row["retained"]] = raw
            reports.append(row)
        receipt = {**start, "sourceBefore": request["source"], "sourceAfter": request["source"],
            "sourceUnchanged": True, "productExitCode": exit_code, "stopExitCode": 0, "finalExitCode": exit_code,
            "ownedSurvivors": [], "cancelledSignals": [], "executedArgv": executed, "stopArgv": stop,
            "productPid": 102, "productLaunchIndex": 0, "stopLaunchIndex": 1, "executedArgvSemantics":
            "logical-command; exact platform launch is ownership.launches[productLaunchIndex]",
            "ownership": self.native_owner(invocation, [self.launch(executed, 102), self.launch(stop, 103)]),
            "reports": reports}
        manifest = {"schema": 1, "records": reports,
            "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."}
        argv = C.canonical_python(context["python"], context["canonicalSources"], "--cwd", str(ROOT), "--wrapper",
            request["wrapper"], "--kind", "gradle", "--purpose", request["purpose"], "--id", invocation,
            "--timeout", "600", "--stop-timeout", "120", "--", *request["command"])
        phase = {"phase": "product", "argv": argv, "job": self.canonical["id"], "invocation": "c" * 32,
            "state": str(self.state_path), "home": request["home"], "cwd": str(ROOT), "canonicalInvocation": invocation,
            "launchAttempted": True, "scopeAttempted": True, "retirement": "KNOWN", "errors": [], "survivors": [],
            "exitCode": exit_code, "cooperativeCancellation": None, "childAncestorInvocationIds": ["c" * 32],
            "ownership": self.native_owner("c" * 32, [self.launch(argv, 101, outer=True)]),
            "startedRawNs": 10012 * NS, "completedRawNs": 10018 * NS, "finalizedRawNs": 10019 * NS,
            "jobBudgetSha256": self.budget.sha256}
        phase_start = {**phase, "launchAttempted": False, "scopeAttempted": False, "exitCode": None}
        baseline = {"role": self.role, "baseline": [], "kernelJob": self.role == "windows-x64"}
        content.update({"start.json": pretty(start), "receipt.json": pretty(receipt), "report-manifest.json": pretty(manifest),
            **{name: b"MODEL LOG\n" for name in JVM.FIXED if name.endswith(".log")}})
        for name, raw in content.items():
            self.put(prefix / name, raw)
        for name, value in (("start.json", phase_start), ("result.json", phase), ("baseline.json", baseline)):
            self.put(self.commands.path / "product" / name, value)
        self.inputs = {"phase": phase, "phase_start_raw": I.encoded(phase_start), "baseline_raw": I.encoded(baseline),
            "start_raw": content["start.json"], "receipt_raw": content["receipt.json"],
            "manifest_raw": content["report-manifest.json"], "files": sorted(
                [{"path": name, "size": len(raw), "sha256": H.digest(raw)} for name, raw in content.items()],
                key=lambda row: row["path"])}
        self.raw_ns = 10020 * NS
        return self.inputs

    def operation(self):
        return {"scope": JVM.FILE_ONLY, "startedRawNs": 10020 * NS, "finishedRawNs": 10021 * NS,
                "jobBudgetSha256": self.budget.sha256}

    def change_original(self, name, change):
        """Update a modeled producer byte AND its inventory to reach semantics."""
        key = {"start.json": "start_raw", "receipt.json": "receipt_raw",
               "report-manifest.json": "manifest_raw"}[name]
        value = decoded(self.inputs[key])
        change(value)
        raw = pretty(value)
        self.inputs[key] = raw
        self.put(self.state_path / "evidence" / self.request["owner"]["productInvocation"] / name, raw)
        for row in self.inputs["files"]:
            if row["path"] == name:
                row.update(size=len(raw), sha256=H.digest(raw))

    def collection(self, **changes):
        values = copy.deepcopy(self.inputs or {"files": []})
        values.update(changes)
        return JVM.collection_data(self.api, self.request_raw, self.run_context_raw, self.canonical_context_raw,
                                   self.operation(), **values)

    def result(self, custody=None):
        custody = self.collection() if custody is None else custody
        phases = [{"phase": name, "exitCode": 0, "launchAttempted": True, "scopeAttempted": True,
            "retirement": "KNOWN", "errors": [], "survivors": [], "ownership": {"discoveryErrors": []},
            "completedRawNs": 10011 * NS, "jobBudgetSha256": self.budget.sha256}
            for name in ("job-time", "recipient-validation", "audit-init")]
        if self.inputs is not None:
            phases.append(self.inputs["phase"])
        return {"schema": 1, "scope": "ORDINARY_PROFILE_CUSTODY_ONLY", "profile": JVM.PROFILE, "role": self.role,
            "source": self.context["source"], "contextSha256": H.digest(self.run_context_raw), "phases": phases,
            "phaseSha256": {row["phase"]: H.digest(I.encoded(row)) for row in phases}, "custody": custody,
            "productAttempted": self.inputs is not None, "cancelled": False, "retirement": "KNOWN", "errors": [],
            "encrypted": False, "dependencyCache": {"scope": "ORDINARY_NATIVE_CONSUME_ORIGINALS"},
            "dependencySeed": {"required": True, "status": "KNOWN_SEEDED", "manifestSha256": "a" * 64,
                "intentSha256": "b" * 64, "contextSha256": H.digest(self.run_context_raw), "completed": True,
                "retirement": "KNOWN", "admittedCount": 1, "admittedBytes": 10, "wrapper": SEED.WRAPPER},
            "jobBudget": {"sha256": self.budget.sha256, "exhausted": False, "cutoffObservation": None,
                "cooperativeCancellation": None, "productiveCutoffRawNs": self.budget.fence("productive")}}

    def copy_model(self, source, destination):
        # Supplied reversible byte copies, not a new production copier.
        values = self.members(source)
        rows, directories = [], {""}
        self.mkdir(destination)
        for index, (name, raw) in enumerate(sorted(values.items())):
            parts = name.split("/")
            directories.update("/".join(parts[:n]) for n in range(1, len(parts)))
            member = "member-" + str(index).zfill(5) + ".bin"
            rows.append({"original": name, "member": member, "size": len(raw), "sha256": H.digest(raw)})
            self.put(destination / member, raw)
        self.put(destination / "original-path-map.json", {"schema": 1, "scope": "REVERSIBLE_PRIVATE_BYTE_COPY",
            "originalRoot": str(source), "directories": sorted(directories), "files": rows})

    def freeze(self):
        custody = JVM.collect(self, self.api)
        self.put(self.evidence.path / "profile-result-before-export.json", self.result(custody))
        self.put(self.evidence.path / "canonical-context.json", self.canonical_context_raw)
        self.copy_model(self.state_path / "evidence", self.evidence.path / "canonical-audit")
        self.copy_model(self.evidence.path, self.path / "frozen-evidence")
        return JVM.frozen_binding(self, self.api, self.private, self.end, lambda: None)


class OrdinaryJvmIdentityControls(unittest.TestCase):
    def test_two_actual_jvm_hosts_keep_ci_job_source_and_desktop_byte_cohort(self):
        self.assertEqual(set(I.PROFILES), {"full", "desktop"})
        for role in HOSTS:
            model = OrdinaryModel(role)
            bound = model.admit()
            value = decoded(bound.record)
            self.assertIs(type(bound), I.Admission)
            self.assertEqual(value["profile"], JVM.PROFILE)
            self.assertEqual(value["suites"], [JVM.PROFILE])
            self.assertEqual(value["source"], {"commit": SOURCE, "tree": TREE})
            self.assertEqual((value["github"]["workflow"], value["github"]["job"]), I.JVM_WORKER[:2])
            self.assertEqual(I.jvm_library_cohort(bound.record), ("desktop", role))
            self.assertNotIn("samplePackagingRequired", value)

    def test_pr_uses_only_original_base_policy_and_ordered_merge_parents(self):
        model = OrdinaryModel(event="pull_request")
        model.git.policies[SOURCE] = b"CANDIDATE_POLICY_MUST_NOT_BE_READ"
        self.assertEqual(decoded(model.admit().record)["policy"]["commit"], BASE)
        self.assertEqual(model.git.requested, [BASE])
        for parents in ([HEAD, BASE], [HEAD], [BASE, HEAD, TREE]):
            model.git.parents_value = parents
            with self.assertRaises(I.AdmissionError): model.admit()
        model.git.parents_value = [BASE, HEAD]
        del model.git.policies[BASE]
        with self.assertRaisesRegex(I.AdmissionError, "MISSING_TRUSTED_RECIPIENT_POLICY"): model.admit()

    def test_main_push_manual_and_exact_ci_schedule_keep_original_policy_rules(self):
        for event, policy in (("push", SOURCE), ("workflow_dispatch", BASE), ("schedule", SOURCE)):
            model = OrdinaryModel(event=event)
            self.assertEqual(decoded(model.admit().record)["policy"]["commit"], policy)
            self.assertEqual(model.git.requested, [policy])
            self.assertEqual(I.jvm_library_cohort(model.admit().record), ("desktop", "linux-x64"))
        model = OrdinaryModel(event="schedule")
        for bad in ("18 4 * * 1", None, ""):
            model.event["schedule"] = bad
            with self.assertRaises(I.AdmissionError): model.admit()

    def test_full_desktop_and_wrong_host_job_workflow_cannot_alias_jvm(self):
        mutations = ({"GITHUB_JOB": "complete-gate"}, {"GITHUB_JOB": "verify"}, {"RUNNER_ARCH": "ARM64"},
            {"RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64"}, {"RUNNER_ENVIRONMENT": "self-hosted"},
            {"GITHUB_WORKFLOW_SHA": HEAD}, {"GITHUB_WORKFLOW_REF": I.REPOSITORY + "/" + I.PROFILES["desktop"][0] +
             "@refs/heads/main"})
        for change in mutations:
            model = OrdinaryModel()
            model.env.update(change)
            with self.subTest(change=change), self.assertRaises(I.AdmissionError): model.admit()
        for profile in ("full", "desktop"):
            model = OrdinaryModel()
            with self.assertRaises(I.AdmissionError):
                I._admit(profile, model.env, I.encoded(model.event), model.git, F.NOW)

    def test_jvm_marker_or_inputs_cannot_request_application_packaging(self):
        for event in ("push", "pull_request", "workflow_dispatch", "schedule"):
            model = OrdinaryModel(event=event)
            model.git.message_value = b"[release ci]\n"
            model.event["head_commit"] = {"message": "[release ci]"}
            bound = model.admit()
            self.assertFalse(I.sample_packaging_required(bound))
            self.assertNotIn("samplePackagingRequired", decoded(bound.record))
            forged = decoded(bound.record)
            forged["samplePackagingRequired"] = True
            with self.assertRaises(I.AdmissionError): I.jvm_library_cohort(I.encoded(forged))
        model = OrdinaryModel(event="workflow_dispatch")
        model.event["inputs"] = {"package": "true"}
        with self.assertRaises(I.AdmissionError): model.admit()
        with self.assertRaises(C.ControllerError): C.profile_command(JVM.PROFILE, "linux-x64", package_samples=True)

    def test_readmit_and_native_query_entry_reject_changed_source_or_identity(self):
        model = OrdinaryModel()
        original = model.admit()
        with patch.dict(os.environ, model.env, clear=True), patch.object(I, "read_regular", return_value=original.original_event), \
                patch.object(I, "GitView", return_value=model.git), patch.object(I.time, "time", return_value=F.NOW):
            self.assertEqual(I.admit(JVM.PROFILE, ROOT, query_runner=object(), expected=original), original)
            for field, value in (("tree_value", "f" * 40), ("head", HEAD), ("dirty", True)):
                before = getattr(model.git, field)
                setattr(model.git, field, value)
                with self.assertRaises(I.AdmissionError): I.admit(JVM.PROFILE, ROOT, query_runner=object(), expected=original)
                setattr(model.git, field, before)
        query_owner = SimpleNamespace(native_host_matches_actions=Mock(), retain_admission=Mock(), _finalize=Mock())
        failure = I.AdmissionError("MODEL_CHANGED_IDENTITY")
        with patch.object(C.query, "NativeGitQueries", return_value=query_owner), \
                patch.object(C.query.signal, "getsignal", return_value=None), patch.object(C.query.signal, "signal"), \
                patch.object(I, "admit", return_value=original) as admitted:
            self.assertIs(C.query.admit_hosted(JVM.PROFILE, ROOT, "/model/query", expected=original), original)
            self.assertEqual(admitted.call_args.args[0], JVM.PROFILE)
            query_owner.retain_admission.assert_called_once_with(original)
            admitted.side_effect = failure
            with self.assertRaises(I.AdmissionError) as caught:
                C.query.admit_hosted(JVM.PROFILE, ROOT, "/model/query2", expected=original)
            self.assertIs(caught.exception, failure)
            query_owner._finalize.assert_called_with(failure)


class InitialJvmIdentityControls(unittest.TestCase):
    def test_both_v2_jvm_slots_bind_distinct_identity_with_original_full_run_attempt(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                bound, match = values["bound"], values["match"]
                self.assertIs(type(match), INITIAL.stages.JvmLibraryMatch)
                self.assertIs(type(bound), INITIAL.InitialJvmLibraryIdentity)
                self.assertNotIsInstance(bound, (I.Admission, INITIAL.InitialOrdinaryIdentity))
                self.assertEqual(retained(bound), bound)
                record = decoded(bound.record)
                full = next(row for row in record["firstPullRequest"]["runs"] if row["profile"] == "full")
                self.assertEqual((record["github"]["runId"], record["github"]["runAttempt"]),
                                 (full["runId"], full["runAttempt"]))
                self.assertEqual(INITIAL.jvm_cache_cohort(bound.record), ("desktop", role))
                self.assertEqual(len(record["initialRecipient"]["historicalRecords"]), 4)

    def test_old_ordinary_binder_rejects_jvm_type_and_wrapped_jvm_record(self):
        with initial_fixture() as values:
            for match in (values["match"], INITIAL.stages.OrdinaryMatch(values["match"].record)):
                with self.assertRaises(I.AdmissionError):
                    INITIAL.bind_worker_match(match, comment_raw=I.encoded(values["model"].comment),
                        event_raw=values["bound"].original_event, policy_raw=F.POLICY, now=F.NOW)
            bound = values["bound"]
            with self.assertRaises(I.AdmissionError):
                INITIAL.retained_identity(bound.record, bound.original_event, bound.original_policy, bound.public_key, now=F.NOW)
            with self.assertRaises(I.AdmissionError): INITIAL.cache_cohort(bound.record)

    def test_jvm_binder_rejects_ordinary_gate_bootstrap_and_v1_records(self):
        with initial_fixture() as values, AF.fixture() as old:
            kwargs = {"comment_raw": I.encoded(values["model"].comment), "event_raw": values["bound"].original_event,
                      "policy_raw": F.POLICY, "now": F.NOW}
            for match in (INITIAL.stages.OrdinaryMatch(values["match"].record),
                          A.gate.GateEligibility(values["match"].record), old["bound"]):
                with self.assertRaises(I.AdmissionError): INITIAL.bind_jvm_worker_match(match, **kwargs)
            raw = decoded(values["match"].record)
            raw["scope"] = INITIAL.MATCH_SCOPE
            with self.assertRaises(I.AdmissionError):
                INITIAL.bind_jvm_worker_match(INITIAL.stages.JvmLibraryMatch(I.encoded(raw)), **kwargs)
            declaration = copy.deepcopy(values["model"].declaration)
            del declaration["firstPullRequest"]["jvmRuns"]
            with self.assertRaises(I.AdmissionError):
                F.check_jvm(declaration, F.jvm_observation(values["model"].declaration), values["model"].histories)
            self.assertIsNone(INITIAL.jvm_cache_cohort(old["bound"].record))

    def test_original_comment_event_policy_key_and_merge_tree_are_exact(self):
        with initial_fixture() as values:
            bound = values["bound"]
            for field, bad in (("event", bound.original_event + b"\n"), ("policy", F.POLICY + b"\n"),
                               ("key", bound.public_key + b"\n")):
                with self.subTest(field=field), self.assertRaises(I.AdmissionError): retained(bound, **{field: bad})
            comment = copy.deepcopy(values["model"].comment)
            comment["user"]["id"] += 1
            with self.assertRaises(I.AdmissionError):
                INITIAL.bind_jvm_worker_match(values["match"], comment_raw=I.encoded(comment),
                    event_raw=bound.original_event, policy_raw=F.POLICY, now=F.NOW)
            for change in (lambda v: v["source"].update(tree="f" * 40),
                           lambda v: v["mergeParents"].reverse()):
                observed = F.jvm_observation(values["model"].declaration)
                change(observed)
                with self.assertRaises(I.AdmissionError):
                    F.check_jvm(values["model"].declaration, observed, values["model"].histories)

    def test_retained_jvm_reader_rejects_changed_scope_types_window_or_extra_fields(self):
        with initial_fixture() as values:
            bound = values["bound"]
            for change in ({"scope": INITIAL.SCOPE}, {"schema": True}, {"profile": "desktop"},
                           {"extra": True}, {"samplePackagingRequired": False}, {"cacheCohort": {"profile": "full", "role": "linux-x64"}}):
                with self.subTest(change=change), self.assertRaises(I.AdmissionError):
                    retained(bound, raw=I.encoded({**decoded(bound.record), **change}))
            for now in (True, F.START - 1, decoded(bound.record)["initialRecipient"]["expiresAt"]):
                with self.assertRaises(I.AdmissionError): retained(bound, now=now)
            with self.assertRaises(I.AdmissionError): retained(bound, raw=bound.record + b"\n")

    def test_initial_jvm_byte_cohort_never_hydrates_admission_or_live_current(self):
        with initial_fixture() as values:
            bound = values["bound"]
            self.assertEqual(INITIAL.worker_cohort(bound.record), ("desktop", "linux-x64"))
            self.assertIs(type(INITIAL.retained_worker_identity(bound.record, bound.original_event,
                bound.original_policy, bound.public_key, now=F.NOW)), INITIAL.InitialJvmLibraryIdentity)
            with self.assertRaises(I.AdmissionError): I.jvm_library_cohort(bound.record)
            with self.assertRaises(I.AdmissionError): N.checked_initial_ordinary(N.InitialOrdinaryCurrent())
            with self.assertRaises(I.AdmissionError): H.CurrentSession.check(object.__new__(H.CurrentSession), current=False)
            current = AF.current_data(bound, "linux-x64")
            self.assertEqual(INITIAL.retained_jvm_current(I.encoded(current), bound, "linux-x64"), current)
            with self.assertRaises(I.AdmissionError): INITIAL.retained_current(I.encoded(current), bound, "linux-x64")

    def test_four_h1_histories_and_current_original_checks_cannot_be_omitted(self):
        with initial_fixture() as values:
            model, bound = values["model"], values["bound"]
            for histories in ((), model.histories[:3], (model.histories[0],) * 4):
                with self.assertRaises(I.AdmissionError):
                    # Pass histories exactly once, positionally: no helper-level
                    # duplicate-key failure may masquerade as a matcher rejection.
                    F.check_jvm(model.declaration, F.jvm_observation(model.declaration), histories)
            current = AF.current_data(bound, "linux-x64")
            for change in ({"qualifications": []}, {"ordinaryAcceptance": "PASS"},
                           {"publicationAuthority": True}, {"ownerCloseSha256": ""}, {"kind": "gate"}):
                with self.assertRaises(I.AdmissionError):
                    INITIAL.retained_jvm_current(I.encoded({**current, **change}), bound, "linux-x64")


class JvmCurrentControls(unittest.TestCase):
    def test_worker_dispatch_uses_real_job_while_ci_gate_stays_full(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                model = values["model"]
                worker = A._context(model.env, I.encoded(model.event), "worker", F.FIRST2)
                self.assertEqual((worker["profile"], worker["role"], worker["github"]["job"]),
                                 (JVM.PROFILE, role, "jvm-library-checks"))
                env = {**model.env, "GITHUB_JOB": A.gate.JOB, "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64"}
                self.assertEqual(A._context(env, I.encoded(model.event), "gate", F.FIRST2)["profile"], "full")
                for kind, wrong in (("worker", env), ("gate", model.env)):
                    with self.assertRaises(I.AdmissionError): A._context(wrong, I.encoded(model.event), kind, F.FIRST2)
        self.assertEqual(set(I.PROFILES), {"full", "desktop"})

    def test_service_names_labels_runner_id_and_predecessor_are_exact(self):
        for role, (_system, _arch, selector) in HOSTS.items():
            with initial_fixture(role) as values:
                model = values["model"]
                matched, originals = model.acquire()
                self.assertIs(type(matched), INITIAL.stages.JvmLibraryMatch)
                self.assertEqual(matched.record, values["match"].record)
                self.assertEqual(dict(originals)["match"], matched.record)
                job = A._run(model.context, model.bodies["attempt"], model.bodies["jobs"], model.service_date)
                self.assertEqual((job["name"], job["labels"]), ("JVM libraries (" + selector + ")", [selector]))
                for index, change in ((0, {"name": selector}), (0, {"labels": [selector, "self-hosted"]}),
                        (0, {"runner_id": True}), (0, {"runner_name": "other"}), (0, {"runner_group_id": 1}),
                        (0, {"run_attempt": 2}), (1, {"conclusion": "failure"}),
                        (1, {"completed_at": F.utc(F.START + 211)})):
                    jobs = copy.deepcopy(model.bodies["jobs"])
                    jobs["jobs"][index].update(change)
                    with self.subTest(role=role, change=change), self.assertRaises(I.AdmissionError):
                        A._run(model.context, model.bodies["attempt"], jobs, model.service_date)

    def test_native_registry_retains_only_exact_jvm_match_and_identity_types(self):
        with initial_fixture() as values:
            with registry_model(values) as (current, state):
                self.assertIs(N._history(current), state)
                self.assertIs(type(state.identity), INITIAL.InitialJvmLibraryIdentity)
                self.assertEqual(len(state.qualifications), 4)
            for changes in ({"match": INITIAL.stages.OrdinaryMatch(values["match"].record)},
                    {"identity": SimpleNamespace(record=values["bound"].record)},
                    {"identity": INITIAL.InitialOrdinaryIdentity(**vars(values["bound"]))}):
                with registry_model(values, **changes) as (current, _state), self.assertRaises(I.AdmissionError):
                    N._history(current)
            with registry_model(values) as (current, state):
                # Replacing even an equal-looking field after factory storage
                # is not the original frozen object binding.
                N._RETURNS[id(current)] = (replace(state, first_originals=tuple(list(state.first_originals))),
                                          N._RETURNS[id(current)][1])
                with self.assertRaises(I.AdmissionError): N._history(current)

    def test_history_reacquisition_cannot_substitute_other_profile_source_or_run(self):
        for field, wrong in (("profile", "desktop"), ("source", {"commit": "f" * 40, "tree": F.T2}),
                             ("github", None)):
            with initial_fixture() as values:
                record = decoded(values["bound"].record)
                record[field] = {**record["github"], "runAttempt": "2"} if field == "github" else wrong
                with self.assertRaises(I.AdmissionError): retained(values["bound"], raw=I.encoded(record))
        for change in (lambda m: setattr(m.git, "source_tree", "f" * 40),
                       lambda m: m.bodies["attempt"].update(run_attempt=2),
                       lambda m: m.bodies["reviewed_ref"]["object"].update(sha="f" * 40)):
            with initial_fixture() as values:
                change(values["model"])
                with self.assertRaises(I.AdmissionError): values["model"].acquire(expected=values["match"])
        with initial_fixture() as values, registry_model(values) as (current, state):
            with patch.object(N, "_checked_close", side_effect=I.AdmissionError("MODEL_UNKNOWN_CLOSE")):
                with self.assertRaisesRegex(I.AdmissionError, "MODEL_UNKNOWN_CLOSE"): N._history(current)
            state.lineage["failed"] = True
            with self.assertRaisesRegex(I.AdmissionError, "LINEAGE_FAILED"): N._history(current)

    def test_initial_adapter_and_schema5_keep_real_jvm_scope_without_sample_intent(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                bound = values["bound"]
                budget = B.derive_initial_retained(bound, AF.originals(values), "a" * 32)
                value, context_raw, started = AF.crypto_fixture(values, budget)
                request = H.crypto_request_data(I.encoded(value), bound, context_raw, budget, started, "export")
                manifest = H.manifest_data(request)
                self.assertEqual(manifest["schema"], 5)
                self.assertEqual(manifest["custody"], {"profile": JVM.PROFILE, "suites": [JVM.PROFILE]})
                self.assertEqual(manifest["source"], decoded(bound.record)["source"])
                self.assertEqual(manifest["github"]["job"], "jvm-library-checks")
                self.assertIs(manifest["initialOrdinary"]["samplePackagingRequired"], False)
                self.assertNotIn("samplePackagingRequired", decoded(context_raw))
                for change in ({"scope": "CLOSED_ORDINARY_TEST_CONTROLLER"}, {"samplePackagingRequired": True}):
                    bad = I.encoded({**decoded(context_raw), **change})
                    with self.assertRaises(I.AdmissionError):
                        H.crypto_request_data(I.encoded(value), bound, bad, budget, started, "export")

    def test_source_failure_unknown_close_or_unregistered_current_cannot_prepare_provider(self):
        with self.assertRaises(I.AdmissionError): N._history(N.InitialOrdinaryCurrent())
        failure = I.AdmissionError("MODEL_SOURCE_FAILURE")
        with initial_fixture() as values:
            values["model"].git.failure = failure
            with self.assertRaises(I.AdmissionError) as caught: values["model"].acquire()
            self.assertIs(caught.exception, failure)
        with initial_fixture() as values, registry_model(values) as (current, _state):
            with patch.object(N, "_checked_close", side_effect=I.AdmissionError("MODEL_UNKNOWN_CLOSE")), \
                    patch.object(H, "current_module", return_value=N), patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(I.AdmissionError): H.CurrentSession(H._KEY, current, lambda: None)
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(H, "current_module", return_value=SimpleNamespace(
                    acquire_initial_ordinary=Mock(side_effect=failure))) as module:
            with self.assertRaises(I.AdmissionError) as caught:
                H.acquire_first(cancelled=lambda: None, original_work_end_ns=1075 * NS, original_final_end_ns=1120 * NS)
            self.assertIs(caught.exception, failure)
            module.return_value.acquire_initial_ordinary.assert_called_once()


class JvmBudgetControls(unittest.TestCase):
    def test_ordinary_and_initial_linux_windows_budgets_use_actual_original_job(self):
        for role in HOSTS:
            ordinary = ordinary_budget(role)
            self.assertEqual((ordinary.profile, ordinary.clock), (JVM.PROFILE, bound_clock(role)))
            self.assertEqual(ordinary.value["github"]["job"], "jvm-library-checks")
            self.assertEqual(ordinary.value["runner"]["labels"], [HOSTS[role][2]])
            with initial_fixture(role) as values:
                originals = AF.originals(values)
                initial = B.derive_initial_retained(values["bound"], originals, "a" * 32)
                self.assertEqual((ordinary.value["schema"], initial.value["schema"]), (2, 3))
                self.assertEqual(initial.profile, JVM.PROFILE)
                self.assertEqual(initial.value["numericJobId"], values["model"].bodies["jobs"]["jobs"][0]["id"])
                self.assertEqual(initial.value["originalsSha256"],
                    {name: H.digest(originals[name + "_raw"]) for name in ("attempt", "jobs")})
                self.assertNotIn("phaseResultSha256", initial.value["provenance"])
                self.assertEqual(B.Budget(initial.record).value, initial.value)

    def test_job1800_product600_outer825_final45_and_native900_remain_exact(self):
        self.assertEqual((C.TOTAL_SECONDS[JVM.PROFILE], C.PRODUCT_SECONDS[JVM.PROFILE],
                          C.OUTER_SECONDS[JVM.PROFILE], C.FINAL_SECONDS), (1500, 600, 825, 45))
        for role in HOSTS:
            policy = B.policy(JVM.PROFILE, clock=bound_clock(role))
            self.assertEqual(tuple(policy[key] for key in ("jobSeconds", "controllerSeconds", "productSeconds",
                "outerSeconds", "productReturnSeconds", "productFinalSeconds", "deliverySeconds")),
                (1800, 1500, 600, 825, 225, 45, 600))
            self.assertNotIn("packageSeconds", policy)
        # This is a source invariant, not a measured native-file lifetime.
        native_source = (ROOT / "scripts/hosted_windows_files.py").read_text()
        self.assertIn("MAX_SECONDS = 900\n", native_source)
        self.assertLess(C.OUTER_SECONDS[JVM.PROFILE] + C.FINAL_SECONDS, 900)
        self.assertIn("-Xmx2048m", C.audit.JVM_ARGUMENTS)
        self.assertIn("-XX:MaxMetaspaceSize=768m", C.audit.JVM_ARGUMENTS)

    def test_productive_and_delivery_fences_are_original_shared_envelopes(self):
        budget = ordinary_budget()
        end = (10000 + 1800 - 120 - 66) * NS
        self.assertEqual(budget.fence("upload"), end)
        self.assertEqual(budget.fence("controller-return"), end - 600 * NS)
        self.assertEqual(budget.fence("productive"), end - (600 + 225 + 45) * NS)
        self.assertEqual(budget.fence("product-return"), end - (600 + 45) * NS)
        self.assertEqual({budget.fence(stage) for stage in B.JVM_CONTROLLER_STAGES}, {end - 600 * NS})
        self.assertEqual({budget.fence(stage) for stage in B.JVM_DELIVERY_STAGES}, {end})
        with patch.object(CLOCK, "observe", return_value=CLOCK.Reading(budget.clock, end - NS)), \
                patch.object(B.time, "monotonic", return_value=100.0):
            self.assertLessEqual(budget.deadline("upload", 180), 101.0)
        with patch.object(CLOCK, "observe", return_value=CLOCK.Reading(budget.clock, end)):
            with self.assertRaisesRegex(B.BudgetError, "FENCE_EXPIRED"): budget.check("upload")

    def test_current_refresh_or_seal_cannot_renew_original_job_start_or_date(self):
        budget = ordinary_budget()
        for field in ("requestStartRawNs", "jobStartedEpochSeconds", "originDateEpochSeconds"):
            changed = budget.value
            changed[field] += NS if field.endswith("Ns") else 1
            with self.assertRaisesRegex(B.BudgetError, "FENCES_CHANGED"): B.Budget(I.encoded(changed)).value
        for field, value in (("previous", []), ("expectedMatch", "f" * 64)):
            with initial_fixture() as values:
                values["context"][field] = value
                with self.assertRaisesRegex(B.BudgetError, "FIRST_WORKER_CONTEXT"):
                    B.derive_initial_retained(values["bound"], AF.originals(values), "a" * 32)
        for role in HOSTS:
            original = ordinary_budget(role)
            with patch.object(CLOCK, "observe", return_value=CLOCK.Reading(original.clock, original.fence("seal") - NS)):
                original.check("seal")
            self.assertEqual(original.record, ordinary_budget(role).record)

    def test_wrong_selector_clock_qpc_frequency_or_native_source_return_fails(self):
        admitted = OrdinaryModel("windows-x64").admit()
        raw = responses(admitted, "windows-x64")
        for change in ({"name": "windows-latest"}, {"labels": ["ubuntu-latest"]}, {"runner_id": 0}):
            changed = {**raw, "jobs": BF.replace_body(raw["jobs"], lambda body: body["jobs"][0].update(change))}
            with self.assertRaises(B.BudgetError): B.derive(admitted, changed, BF.provenance(), clock=bound_clock("windows-x64"))
        wrong_clock = CLOCK.ClockIdentity("windows-x64", CLOCK.DOMAINS["windows-x64"], 1_000_000)
        with self.assertRaises(B.BudgetError): B.derive(admitted, raw, BF.provenance(), clock=wrong_clock)
        for part, change in (("native", {"retirement": "UNKNOWN"}), ("native", {"exitCode": True}),
                             ("close", {"errors": ["MODEL_CLOSE"]}), ("ack", {"retirement": "UNKNOWN"})):
            with initial_fixture("windows-x64") as values:
                values[part].update(change)
                with self.assertRaisesRegex(B.BudgetError, "INITIAL_NATIVE_ORIGINALS"):
                    B.derive_initial_retained(values["bound"], AF.originals(values), "a" * 32)

    def test_jvm_budget_rejects_desktop_full_uninstall_package_and_late_stage_aliases(self):
        budget = ordinary_budget()
        for stage in ("uninstall", "uninstall-final", "collect-final", "package", "samples", "simulator-retire-after"):
            with self.assertRaisesRegex(B.BudgetError, "CLOSED_STAGE"): budget.fence(stage)
        for profile in ("desktop", "full"):
            value = budget.value
            value["profile"] = profile
            with self.assertRaises(ERRORS): B.Budget(I.encoded(value)).value
        for name in ("productive", "collect", "seal", "upload"):
            with patch.object(CLOCK, "observe", return_value=CLOCK.Reading(budget.clock, budget.fence(name))):
                with self.assertRaisesRegex(B.BudgetError, "FENCE_EXPIRED"): budget.check(name)


class JvmCohortControls(unittest.TestCase):
    def test_both_origins_map_only_validated_jvm_identity_to_desktop_same_role_bytes(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                for bound in (OrdinaryModel(role).admit(), values["bound"]):
                    for profile in (JVM.PROFILE, "desktop"):
                        self.assertEqual(SEED.byte_cohort(bound.record, profile, role), ("desktop", role))
                        self.assertIsNone(SEED.validate_cohort(bound.record, profile, role))
                    self.assertIsNone(SEED.require_connected_execution(bound.record))
                    self.assertEqual(decoded(bound.record)["profile"], JVM.PROFILE)
                    with self.assertRaises(ERRORS): SEED.byte_cohort(bound.record, "full", role)
                    with self.assertRaises(ERRORS): SEED.byte_cohort(bound.record, JVM.PROFILE, "macos-arm64")

    def test_plan_staging_and_intent_keep_actual_jvm_source_and_github_identity(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                for bound in (OrdinaryModel(role).admit(), values["bound"]):
                    model, record = cohort_fixture(bound, role), decoded(bound.record)
                    self.assertEqual(model.path.name, "p2pkit-dependency-seed-desktop-" + role)
                    self.assertEqual(model.path.parent, model.session.parent)
                    for row in (model.stage, model.plan):
                        self.assertEqual((row["profile"], row["role"]), ("desktop", role))
                        self.assertEqual(row["source"], record["source"])
                        self.assertEqual(row["github"], record["github"])
                        self.assertEqual(row["admissionSha256"], H.digest(bound.record))
                        self.assertEqual(row["github"]["job"], "jvm-library-checks")
                    self.assertEqual(model.intent["admissionSha256"], H.digest(bound.record))
                    self.assertEqual(model.plan["key"], CACHE.cache_key("desktop", role,
                        model.compiled.authority_sha256, model.inputs["files"][SEED.INPUTS[1]]))
                    self.assertEqual(CACHE.validate_plan(model.plan, bound.record, model.staging_raw,
                        model.compiled, model.inputs, session=model.session, profile="desktop", role=role,
                        mode="consume"), model.plan)

    def test_jvm_execution_profile_cannot_replace_byte_cohort_or_bootstrap_mode(self):
        bound = OrdinaryModel().admit()
        model = cohort_fixture(bound, "linux-x64")
        with self.assertRaises(SEED.SeedError):
            CACHE.make_plan(bound.record, model.staging_raw, model.compiled, model.inputs,
                session=model.session, profile=JVM.PROFILE, role="linux-x64", mode="consume")
        for changes in ({"profile": JVM.PROFILE}, {"mode": "bootstrap"}, {"key": model.plan["key"] + "-fallback"}):
            with self.assertRaises(SEED.SeedError): CACHE.restore_provider_contract({**model.plan, **changes})
        # The generic engine can express bootstrap DATA. The actual restore
        # caller, not an invented global engine restriction, rejects that mode.
        bootstrap = CACHE.make_plan(bound.record, model.staging_raw, model.compiled, model.inputs,
            session=model.session, profile="desktop", role="linux-x64", mode="bootstrap")
        with self.assertRaises(SEED.SeedError): CACHE.restore_provider_contract(bootstrap)
        request = CACHE.restore_provider_contract(model.plan)["request"]
        self.assertEqual(request["action"], model.plan["provider"]["restore"])
        self.assertIs(request["lookupOnly"], False)
        self.assertEqual(request["restoreKeys"], [])

    def test_forged_scope_role_path_key_or_partial_initial_marker_fails_closed(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                for bound in (OrdinaryModel(role).admit(), values["bound"]):
                    for change in ({"scope": "ORDINARY_INITIAL_RECIPIENT_IDENTITY_V1"},
                            {"initialRecipient": {}}, {"cacheCohort": {"profile": "desktop", "role": "macos-arm64"}}):
                        with self.assertRaises(ERRORS):
                            SEED.byte_cohort(I.encoded({**decoded(bound.record), **change}), JVM.PROFILE, role)
                    model = cohort_fixture(bound, role)
                    for change in ({"container": str(model.path / "alternate")}, {"role": "macos-arm64"},
                                   {"source": {"commit": HEAD, "tree": TREE}}, {"admissionSha256": "f" * 64}):
                        with self.assertRaises(ERRORS):
                            SEED.validate_retained_stage({**model.stage, **change}, bound.record,
                                {"session": str(model.session), "profile": JVM.PROFILE, "role": role}, model.inputs)
                    for change in ({"key": "wrong"}, {"path": model.plan["path"] + "/**"},
                                   {"role": "macos-arm64"}, {"stagingSha256": "f" * 64}):
                        with self.assertRaises(ERRORS):
                            CACHE.validate_plan({**model.plan, **change}, bound.record, model.staging_raw,
                                model.compiled, model.inputs, session=model.session, profile="desktop", role=role, mode="consume")

    def test_native_preparation_adoption_and_frozen_seed_recompute_same_cohort(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                initial_budget = B.derive_initial_retained(values["bound"], AF.originals(values), "a" * 32)
                for bound, budget in ((OrdinaryModel(role).admit(), ordinary_budget(role)), (values["bound"], initial_budget)):
                    model, owner = cohort_fixture(bound, role), MemoryOwner()
                    private = owner.mkdir(model.session)
                    dirs = {name: owner.mkdir(model.session / name) for name in C.PREPARATION_DIRECTORIES}
                    directory = owner.mkdir(dirs["evidence"].path / "dependency-cache")
                    provider = owner.mkdir(dirs["runtime"].path / "cache-provider")
                    plan_raw = owner.put(directory.path / "plan.json", model.plan)
                    owner.put(directory.path / "staging.json", model.staging_raw)
                    began = budget.value["responseFinishedRawNs"] + NS
                    limit = min(budget.fence("productive"), began + 180 * NS)
                    index = C.native_origin(bound)
                    disposition = H.current_budget_disposition(budget, "c" * 64) if index else None
                    with patch.object(C, "initial_budget_originals", return_value=(budget, {}, "c" * 64, disposition)):
                        origin = C.native_budget_origin(owner, private, bound, budget, 1)
                    record = decoded(bound.record)
                    descriptor = {"schema": 1, "scope": "P2PKIT_" + ("INITIAL_" if index else "") +
                        "ORDINARY_RESTORE_NATIVE_DESCRIPTOR_V1", "phase": "restore", "source": record["source"],
                        "github": record["github"], "planSha256": H.digest(plan_raw), "directory": str(provider.path),
                        "directoryIdentity": list(provider.identity), "clock": B.clock_value(budget.clock),
                        "providerWindow": {"issuedNs": began, "hardEndNs": limit, "actualProviderStart": "NOT_OBSERVED"},
                        "providerRequest": CACHE.restore_provider_contract(model.plan)["request"],
                        "providerExecution": "NOT_PERFORMED", "enclosingOwnerClose": "NOT_OBSERVED",
                        "providerAcceptance": "NOT_ESTABLISHED"}
                    prepared = {"schema": 1, "scope": C.NATIVE_PREPARATION_SCOPES[index], "profile": JVM.PROFILE,
                        "role": role, "session": str(model.session), "sessionIdentity": list(private.identity),
                        "directories": {name: list(value.identity) for name, value in dirs.items()},
                        "source": record["source"], "github": record["github"], "admissionSha256": H.digest(bound.record),
                        "job": budget.value["provenance"]["controllerJob"], "jobBudgetSha256": budget.sha256,
                        "planSha256": H.digest(plan_raw), "stagingSha256": H.digest(model.staging_raw),
                        "restoreWindow": {"beganRawNs": began, "endRawNs": limit,
                                          "timeoutMinutes": (limit - began) // (60 * NS)},
                        "completedRawNs": began, "pid": 321, "budgetOrigin": origin,
                        "nativeProvider": I.encoded(descriptor).decode("ascii"), "enclosingOwnerClose": "NOT_OBSERVED",
                        "providerAcceptance": "NOT_ESTABLISHED"}
                    with patch.object(C, "session_path", return_value=model.session), \
                            patch.object(C.processes, "host_role", return_value=role), \
                            patch.object(C, "initial_budget_originals", return_value=(budget, {}, "c" * 64, disposition)):
                        raw = I.encoded(prepared)
                        self.assertEqual(C.read_native_preparation(owner, private, bound, budget, raw, 1), raw)
                        for changes in ({"profile": "desktop"}, {"jobBudgetSha256": "f" * 64},
                                        {"enclosingOwnerClose": "KNOWN"}, {"planSha256": "f" * 64}):
                            with self.assertRaises(ERRORS):
                                C.read_native_preparation(owner, private, bound, budget,
                                    I.encoded({**prepared, **changes}), 1)
        # Downstream callers must recompute; these are source binding checks,
        # not a successful native restore/adoption/frozen cache claim.
        source = (ROOT / "scripts/run-hosted-test-custody.py").read_text()
        self.assertIn('profile=seed.byte_cohort(admitted.record, prepared["profile"], prepared["role"])[0]', source)
        self.assertIn('controller.cache_binding = consume_binding(controller, controller.private, controller.admitted, budget, end)', source)
        self.assertIn('seed.validate_receipt(parse(originals["manifest.json"]), context["dependencySeed"], staging_raw, context_raw,', source)


    def test_legacy_bootstrap_all_six_cohorts_preserve_stage_path_plan_and_intent(self):
        self.assertEqual(SEED.bootstrap.SELECTIONS, BOOTSTRAP_SELECTIONS)
        for row in BOOTSTRAP_SELECTIONS:
            name, profile, role, system, arch = row
            with self.subTest(selection=name):
                bound = bootstrap_identity_fixture(row, initial=False)
                original, value = bound.record, decoded(bound.record)
                self.assertIs(type(bound), I.Admission)
                self.assertEqual(value["scope"], "CACHE_BOOTSTRAP_HOSTED_IDENTITY_V1")
                self.assertEqual(value["profile"], "cache-bootstrap")
                self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
                self.assertNotIn("suites", value)
                self.assertEqual(value["source"], {"commit": SOURCE, "tree": TREE})
                self.assertEqual((value["github"]["runnerOS"], value["github"]["runnerArch"]), (system, arch))
                model = bootstrap_cohort_fixture(bound, profile, role)
                expected = Path("/model/runner-temp/p2pkit-dependency-seed-" + profile + "-" + role)
                self.assertEqual(model.path, expected)
                self.assertEqual(model.session.parent.parent, expected.parent)
                self.assertEqual(model.session.name, "initializer")
                self.assertEqual(model.session.parent.name, "p2pkit-cache-originals-123-1-" + name + "-productive")
                self.assertEqual(SEED.byte_cohort(original, profile, role), (profile, role))
                self.assertEqual(SEED.validate_cohort(original, profile, role), (profile, role))
                self.assertEqual(SEED._bootstrap_cohort(original), (profile, role))
                for retained in (model.stage, model.plan):
                    self.assertEqual((retained["profile"], retained["role"]), (profile, role))
                    self.assertEqual(retained["source"], value["source"])
                    self.assertEqual(retained["github"], value["github"])
                    self.assertEqual(retained["admissionSha256"], H.digest(original))
                self.assertEqual(model.intent["admissionSha256"], H.digest(original))
                self.assertEqual(model.intent["stagingSha256"], H.digest(model.staging_raw))
                self.assertEqual(model.intent["container"], str(expected))
                self.assertEqual((model.intent["profile"], model.intent["role"]), (profile, role))
                self.assertEqual(model.plan["mode"], "bootstrap")
                self.assertNotIn("jobBudgetSha256", model.plan)
                self.assertNotIn("primaryAbiAccounting", model.plan)
                self.assertEqual(model.plan["path"], str(expected / "restore-home/caches/modules-2/files-2.1"))
                self.assertEqual(model.plan["key"], "p2pkit-dependency-files-v1-" + profile + "-" + role + "-" +
                    model.compiled.authority_sha256 + "-" + model.inputs["files"]["gradle/wrapper/gradle-wrapper.properties"])
                self.assertEqual(SEED.validate_retained_stage(model.stage, original,
                    {"session": str(model.session), "profile": profile, "role": role}, model.inputs), model.stage)
                self.assertEqual(CACHE.validate_plan(model.plan, original, model.staging_raw, model.compiled,
                    model.inputs, session=model.session, profile=profile, role=role, mode="bootstrap"), model.plan)
                with self.assertRaisesRegex(SEED.SeedError, "^SEED_BOOTSTRAP_EXECUTION_NOT_CONNECTED$"):
                    SEED.require_connected_execution(original)
                with self.assertRaisesRegex(SEED.SeedError, "^CACHE_BOOTSTRAP_CANNOT_CONSUME$"):
                    CACHE.make_plan(original, model.staging_raw, model.compiled, model.inputs,
                        session=model.session, profile=profile, role=role, mode="consume")
                self.assertEqual(bound.record, original)

    def test_initial_bootstrap_all_six_cohorts_preserve_stage_path_plan_and_intent(self):
        for row in BOOTSTRAP_SELECTIONS:
            name, profile, role, system, arch = row
            with self.subTest(selection=name):
                bound = bootstrap_identity_fixture(row, initial=True)
                original, value = bound.record, decoded(bound.record)
                self.assertIs(type(bound), SEED.initial_bootstrap.InitialBootstrapIdentity)
                self.assertNotIsInstance(bound, I.Admission)
                self.assertEqual(value["scope"], "CACHE_BOOTSTRAP_INITIAL_RECIPIENT_IDENTITY_V1")
                self.assertEqual(value["profile"], "cache-bootstrap")
                self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
                self.assertNotIn("suites", value)
                self.assertEqual(value["source"], {"commit": F.H1, "tree": F.T1})
                self.assertEqual(value["policy"]["origin"], "reviewed-head")
                self.assertNotIn("policyMain", value["github"]["eventBinding"])
                self.assertEqual((value["github"]["runnerOS"], value["github"]["runnerArch"]), (system, arch))
                model = bootstrap_cohort_fixture(bound, profile, role)
                expected = Path("/model/runner-temp/p2pkit-dependency-seed-" + profile + "-" + role)
                self.assertEqual(model.path, expected)
                self.assertEqual(model.session.parent, expected.parent)
                self.assertEqual(model.session.name, "p2pkit-initial-recipient-" + value["github"]["runId"] + "-" +
                                 value["github"]["runAttempt"] + "-worker-recipient-initializer")
                self.assertEqual(SEED.byte_cohort(original, profile, role), (profile, role))
                self.assertEqual(SEED.validate_cohort(original, profile, role), (profile, role))
                self.assertEqual(SEED._bootstrap_cohort(original), (profile, role))
                for retained in (model.stage, model.plan):
                    self.assertEqual((retained["profile"], retained["role"]), (profile, role))
                    self.assertEqual(retained["source"], value["source"])
                    self.assertEqual(retained["github"], value["github"])
                    self.assertEqual(retained["admissionSha256"], H.digest(original))
                self.assertEqual(model.intent["admissionSha256"], H.digest(original))
                self.assertEqual(model.intent["stagingSha256"], H.digest(model.staging_raw))
                self.assertEqual(model.intent["container"], str(expected))
                self.assertEqual((model.intent["profile"], model.intent["role"]), (profile, role))
                self.assertEqual(model.plan["mode"], "bootstrap")
                self.assertNotIn("jobBudgetSha256", model.plan)
                self.assertNotIn("primaryAbiAccounting", model.plan)
                self.assertEqual(model.plan["path"], str(expected / "restore-home/caches/modules-2/files-2.1"))
                self.assertEqual(model.plan["key"], "p2pkit-dependency-files-v1-" + profile + "-" + role + "-" +
                    model.compiled.authority_sha256 + "-" + model.inputs["files"]["gradle/wrapper/gradle-wrapper.properties"])
                self.assertEqual(SEED.validate_retained_stage(model.stage, original,
                    {"session": str(model.session), "profile": profile, "role": role}, model.inputs), model.stage)
                self.assertEqual(CACHE.validate_plan(model.plan, original, model.staging_raw, model.compiled,
                    model.inputs, session=model.session, profile=profile, role=role, mode="bootstrap"), model.plan)
                with self.assertRaisesRegex(SEED.SeedError, "^SEED_BOOTSTRAP_EXECUTION_NOT_CONNECTED$"):
                    SEED.require_connected_execution(original)
                with self.assertRaisesRegex(SEED.SeedError, "^CACHE_BOOTSTRAP_CANNOT_CONSUME$"):
                    CACHE.make_plan(original, model.staging_raw, model.compiled, model.inputs,
                        session=model.session, profile=profile, role=role, mode="consume")
                self.assertEqual(bound.record, original)

    def test_bootstrap_shaped_partial_jvm_markers_never_bypass_validation(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                for bound in (OrdinaryModel(role).admit(), values["bound"]):
                    base = decoded(bound.record)
                    variants = []
                    for field in ("profile", "scope"):
                        changed = copy.deepcopy(base)
                        del changed[field]
                        variants.append(("missing-" + field, changed))
                    for profile in ("desktop", "full", "cache-bootstrap"):
                        variants.append(("profile-" + profile, {**base, "profile": profile}))
                    for scope in ("ORDINARY_INITIAL_RECIPIENT_IDENTITY_V1",
                            "CACHE_BOOTSTRAP_HOSTED_IDENTITY_V1", "CACHE_BOOTSTRAP_INITIAL_RECIPIENT_IDENTITY_V1"):
                        variants.append(("scope-" + scope, {**base, "scope": scope}))
                        changed = copy.deepcopy(base)
                        changed.update(scope=scope, profile="cache-bootstrap", selection="desktop-" + role,
                            producerCommand=["help", "--console=plain", "--no-configure-on-demand"],
                            producerScope="CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS",
                            testAcceptance="NOT_PERFORMED")
                        for field in ("suites", "initialRecipient", "firstPullRequest"):
                            changed.pop(field, None)
                        variants.append(("bootstrap-shaped-" + scope, changed))
                    variants.append(("cacheCohort-only", {"cacheCohort": copy.deepcopy(base["cacheCohort"])}))
                    for cohort in ({"profile": "full", "role": role},
                            {"profile": "desktop", "role": "windows-x64" if role == "linux-x64" else "linux-x64"}):
                        variants.append(("wrong-cohort-" + cohort["profile"] + "-" + cohort["role"],
                                         {**base, "cacheCohort": cohort}))
                    for label, changed in variants:
                        raw = I.encoded(changed)
                        for profile in (JVM.PROFILE, "desktop"):
                            for call in (lambda: SEED.byte_cohort(raw, profile, role),
                                         lambda: SEED.validate_cohort(raw, profile, role)):
                                with self.subTest(origin=base["scope"], role=role, variant=label, caller=profile), \
                                        self.assertRaisesRegex(SEED.SeedError, "^SEED_"):
                                    call()
                        with self.subTest(origin=base["scope"], role=role, variant=label, caller="bootstrap-reader"), \
                                self.assertRaisesRegex(SEED.SeedError, "^SEED_"):
                            SEED._bootstrap_cohort(raw, profile="desktop", role=role)
                    self.assertEqual(bound.record, I.encoded(base))

    def test_bootstrap_dispatch_rejects_mixed_markers_without_fallback(self):
        for initial in (False, True):
            for row in BOOTSTRAP_SELECTIONS:
                name, profile, role, _system, _arch = row
                bound = bootstrap_identity_fixture(row, initial=initial)
                base = decoded(bound.record)
                variants = []
                for field in ("selection", "cacheCohort", "producerCommand"):
                    changed = copy.deepcopy(base)
                    del changed[field]
                    variants.append(changed)
                variants.extend(({**base, "schema": True}, {**base, "extra": True},
                    {**base, "cacheCohort": {"profile": profile, "role": "not-a-role"}}))
                for changed in variants:
                    raw = I.encoded(changed)
                    for call in (lambda: SEED.byte_cohort(raw, profile, role),
                                 lambda: SEED.validate_cohort(raw, profile, role),
                                 lambda: SEED._bootstrap_cohort(raw, profile=profile, role=role)):
                        with self.subTest(initial=initial, selection=name, malformed=sorted(changed)), \
                                patch.object(I, "jvm_library_cohort", side_effect=AssertionError("NO_JVM_FALLBACK")), \
                                patch.object(SEED.bootstrap, "cache_cohort", wraps=SEED.bootstrap.cache_cohort) as legacy:
                            with self.assertRaisesRegex(SEED.SeedError, "^SEED_BOOTSTRAP_IDENTITY_CHANGED$"):
                                call()
                            self.assertLessEqual(legacy.call_count, 1)
                for supplied_profile, supplied_role in ((JVM.PROFILE, role),
                        ("full" if profile == "desktop" else "desktop", role), (profile, "not-a-role")):
                    for call in (lambda: SEED.byte_cohort(bound.record, supplied_profile, supplied_role),
                                 lambda: SEED.validate_cohort(bound.record, supplied_profile, supplied_role),
                                 lambda: SEED._bootstrap_cohort(bound.record, profile=supplied_profile, role=supplied_role)):
                        with self.subTest(initial=initial, selection=name, caller=(supplied_profile, supplied_role)), \
                                self.assertRaisesRegex(SEED.SeedError, "^SEED_BOOTSTRAP_COHORT_CHANGED$"):
                            call()
        base = decoded(bootstrap_identity_fixture(BOOTSTRAP_SELECTIONS[0], initial=False).record)
        for marker in ("origin", "originalMain", "policyHead", "initialRecipient"):
            changed = copy.deepcopy(base)
            if marker == "origin":
                changed["policy"]["origin"] = "reviewed-head"
            elif marker == "initialRecipient":
                changed[marker] = {}
            else:
                changed["github"]["eventBinding"][marker] = BASE
            raw = I.encoded(changed)
            for call in (lambda: SEED.byte_cohort(raw, "desktop", "linux-x64"),
                         lambda: SEED.validate_cohort(raw, "desktop", "linux-x64"),
                         lambda: SEED._bootstrap_cohort(raw, profile="desktop", role="linux-x64")):
                with self.subTest(marker=marker), \
                        patch.object(SEED.bootstrap, "cache_cohort", side_effect=AssertionError("NO_LEGACY_FALLBACK")) as legacy, \
                        patch.object(I, "jvm_library_cohort", side_effect=AssertionError("NO_JVM_FALLBACK")) as jvm:
                    with self.assertRaisesRegex(SEED.SeedError, "^SEED_BOOTSTRAP_IDENTITY_CHANGED$"):
                        call()
                    legacy.assert_not_called()
                    jvm.assert_not_called()
        for initial_origin in (False, True):
            bound = bootstrap_identity_fixture(BOOTSTRAP_SELECTIONS[0], initial=initial_origin)
            for error in (RuntimeError("MODEL_UNKNOWN"), KeyboardInterrupt("MODEL_CANCELLED")):
                for call in (lambda: SEED.byte_cohort(bound.record, "desktop", "linux-x64"),
                             lambda: SEED.validate_cohort(bound.record, "desktop", "linux-x64"),
                             lambda: SEED._bootstrap_cohort(bound.record, profile="desktop", role="linux-x64")):
                    with self.subTest(initial=initial_origin, error=type(error).__name__), \
                            patch.object(SEED.initial_bootstrap, "cache_cohort", side_effect=error) as selected, \
                            patch.object(SEED.bootstrap, "cache_cohort", side_effect=AssertionError("NO_LEGACY_FALLBACK")) as legacy, \
                            patch.object(I, "jvm_library_cohort", side_effect=AssertionError("NO_JVM_FALLBACK")) as jvm:
                        with self.assertRaises(type(error)) as raised:
                            call()
                        self.assertIs(raised.exception, error)
                        selected.assert_called_once_with(bound.record)
                        legacy.assert_not_called()
                        jvm.assert_not_called()
        for role in HOSTS:
            with initial_fixture(role) as values:
                for bound in (OrdinaryModel(role).admit(), values["bound"]):
                    with patch.object(SEED.initial_bootstrap, "cache_cohort", side_effect=AssertionError("NOT_BOOTSTRAP")) as initial, \
                            patch.object(SEED.bootstrap, "cache_cohort", side_effect=AssertionError("NOT_BOOTSTRAP")) as legacy:
                        self.assertEqual(SEED.byte_cohort(bound.record, JVM.PROFILE, role), ("desktop", role))
                        self.assertIsNone(SEED.validate_cohort(bound.record, JVM.PROFILE, role))
                        self.assertIsNone(SEED.require_connected_execution(bound.record))
                        initial.assert_not_called()
                        legacy.assert_not_called()


class JvmReportCustodyControls(unittest.TestCase):
    def test_one_exact_three_task_six_root_request_reserves_original_canonical_id(self):
        for role in HOSTS:
            model = ReportFixture(role)
            request = model.request
            self.assertEqual(request["scope"], JVM.REQUEST_SCOPE)
            self.assertEqual(request["tasks"], [":p2p-core:jvmTest", ":p2p-transport-lan:jvmTest",
                                               ":p2p-network-provisioning-desktop:test"])
            self.assertEqual(request["reportRoots"], list(JVM.ROOTS))
            self.assertEqual(len(request["reportRoots"]), 6)
            self.assertEqual(request["command"], [*request["tasks"], "--continue", "--console=plain"])
            self.assertEqual(request["owner"], {"job": "a" * 32, "productInvocation": "b" * 32})
            self.assertEqual(request["operation"]["scope"], JVM.FILE_ONLY)
            self.assertEqual(model.names(model, model.commands.path, model.end), [])
            with self.assertRaises(JVM.JvmCustodyError): JVM.reserve(model, model.api)
        model = ReportFixture(reserve=False)
        model.mkdir(model.state_path / "evidence" / ("c" * 32))
        with self.assertRaisesRegex(JVM.JvmCustodyError, "PREEXISTING_CANONICAL"): JVM.reserve(model, model.api)

    def test_complete_passing_original_receipt_reports_and_native_close_are_retained(self):
        for role in HOSTS:
            model = ReportFixture(role)
            inputs = model.originals()
            self.assertNotEqual(inputs["receipt_raw"], I.encoded(decoded(inputs["receipt_raw"])))
            result = JVM.collect(model, model.api)
            self.assertEqual(result["result"], "RETAINED")
            self.assertEqual(result["missingRoots"], [])
            self.assertEqual(len(result["retainedFiles"]), len(JVM.FIXED) + 6)
            self.assertEqual(result["canonicalReceiptSha256"], H.digest(inputs["receipt_raw"]))
            self.assertTrue(JVM.profile_passed(model.result(result)))
            checked, raw, request, canonical = JVM.verify(model, model.api, model.private,
                model.run_context_raw, model.result(result), model.end, lambda: None)
            self.assertEqual((checked, raw, request, canonical),
                             (result, I.encoded(result), model.request_raw, model.canonical_context_raw))
            self.assertTrue(all(row["attempted"] and row["closed"] for row in model.resources))

    def test_known_nonzero_product_with_stop_zero_retains_partial_or_absent_reports_as_failure(self):
        for exit_code, roots in ((1, 0), (2, 3), (7, 6)):
            model = ReportFixture()
            model.originals(exit_code=exit_code, roots=roots)
            custody = JVM.collect(model, model.api)
            self.assertEqual(custody["result"], "FAILED_TEST_OR_REPORTS")
            self.assertEqual(custody["productExitCode"], exit_code)
            self.assertEqual(custody["ownerFinalExitCode"], exit_code)
            self.assertEqual(custody["stopExitCode"], 0)
            self.assertEqual(len(custody["missingRoots"]), 6 - roots)
            self.assertEqual(len(custody["retainedFiles"]), len(JVM.FIXED) + roots)
            self.assertFalse(JVM.profile_passed(model.result(custody)))
            self.assertEqual(JVM.verify(model, model.api, model.private, model.run_context_raw,
                model.result(custody), model.end, lambda: None)[0], custody)

    def test_not_started_has_no_invented_receipt_stop_report_or_success(self):
        model = ReportFixture()
        custody = JVM.collect(model, model.api)
        self.assertEqual(custody["result"], "NOT_STARTED")
        self.assertEqual(custody["retainedFiles"], [])
        self.assertEqual(custody["missingRoots"], list(JVM.ROOTS))
        for name in ("canonicalStartSha256", "canonicalReceiptSha256", "reportManifestSha256", "productPhaseSha256",
                     "productExitCode", "stopExitCode", "ownerFinalExitCode"):
            self.assertIsNone(custody[name])
        self.assertFalse(JVM.profile_passed(model.result(custody)))
        for changes in ({"receipt_raw": b"{}"}, {"files": [{"path": "receipt.json", "size": 2, "sha256": H.digest(b"{}")}]}):
            with self.assertRaisesRegex(JVM.JvmCustodyError, "NOT_STARTED_HAS_NO_CANONICAL_ORIGINALS"):
                model.collection(**changes)

    def test_attempted_product_without_original_receipt_or_known_stop_is_unknown_hold(self):
        for key in ("receipt_raw", "start_raw", "manifest_raw", "baseline_raw", "phase_start_raw"):
            model = ReportFixture()
            model.originals()
            with self.assertRaisesRegex(JVM.JvmCustodyError, "LAUNCHED_PRODUCT_REQUIRES_ORIGINALS"):
                model.collection(**{key: None})
        for stop in (None, 1, 125, True):
            model = ReportFixture()
            model.originals()
            model.change_original("receipt.json", lambda value: value.update(stopExitCode=stop))
            with self.assertRaisesRegex(JVM.JvmCustodyError, "CANONICAL_STOP_SOURCE_OR_RETIREMENT"): model.collection()
        model = ReportFixture()
        model.mkdir(model.commands.path / "product")
        model.collect_attempted, model.custody = False, None
        with patch.object(C, "seed_names", side_effect=model.names), \
                self.assertRaisesRegex(JVM.JvmCustodyError, "EXACT_SINGLE_CANONICAL_INVOCATION"):
            C.Controller.collect(model)
        self.assertTrue(model.unknown)
        self.assertIsNone(model.custody)
        self.assertTrue(model.collect_attempted)

    def test_zero_exit_with_missing_or_preexisting_reports_is_not_profile_pass(self):
        for roots, stale in ((0, False), (5, False), (6, True)):
            model = ReportFixture()
            model.originals(roots=roots, stale=stale)
            custody = model.collection()
            self.assertEqual(custody["productExitCode"], 0)
            self.assertEqual(custody["result"], "FAILED_TEST_OR_REPORTS")
            self.assertFalse(JVM.profile_passed(model.result(custody)))
        model = ReportFixture()
        model.originals()
        # Extra unchanged output is explicitly stale even with all six fresh roots.
        stale = {"source": "other/report.txt", "sha256": "a" * 64, "bytes": 1,
                 "classification": "preexisting-unchanged"}
        model.change_original("receipt.json", lambda v: v["reports"].append(stale))
        model.change_original("report-manifest.json", lambda v: v["records"].append(stale))
        self.assertEqual(model.collection()["missingRoots"], [])
        self.assertEqual(model.collection()["result"], "FAILED_TEST_OR_REPORTS")

    def test_report_manifest_records_and_every_retained_copy_must_match_originals(self):
        report_path = "reports/" + JVM.ROOTS[0] + "synthetic.txt"
        for label, target, field, replacement, reason in (
                ("missing-original", "stop.stdout.log", None, None, "COMPLETE_ORIGINAL_FILE_ROSTER"),
                ("duplicate-original", "stop.stdout.log", None, None, "ORIGINAL_FILE_METADATA"),
                ("report-hash", report_path, "sha256", "f" * 64, "RETAINED_REPORT_BYTES"),
                ("report-size", report_path, "size", 1, "RETAINED_REPORT_BYTES")):
            with self.subTest(boundary="collection", mutation=label):
                model = ReportFixture()
                model.originals()
                files = copy.deepcopy(model.inputs["files"])
                selected = [row for row in files if row["path"] == target]
                self.assertEqual(len(selected), 1)
                row = selected[0]
                if label == "missing-original":
                    files.remove(row)
                elif label == "duplicate-original":
                    files.append(dict(row))
                else:
                    records = [item for item in decoded(model.inputs["manifest_raw"])["records"]
                               if item.get("retained") == target]
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0]["classification"], "changed-since-admission")
                    self.assertEqual(row, {"path": target, "size": records[0]["bytes"],
                                           "sha256": records[0]["sha256"]})
                    self.assertNotEqual(row[field], replacement)
                    row[field] = replacement
                self.assertNotEqual(files, model.inputs["files"])
                with self.assertRaisesRegex(JVM.JvmCustodyError, "^JVM_LIBRARY_" + reason + "$"):
                    model.collection(files=files)
        model = ReportFixture()
        model.originals()
        model.change_original("report-manifest.json", lambda value: value["records"].pop())
        with self.assertRaisesRegex(JVM.JvmCustodyError, "REPORT_MANIFEST"): model.collection()
        model = ReportFixture()
        model.originals()
        for key in ("start_raw", "receipt_raw", "manifest_raw"):
            with self.assertRaisesRegex(JVM.JvmCustodyError, "ORIGINAL_JSON_CHANGED"):
                model.collection(**{key: model.inputs[key] + b"\n"})
        # Fixed-log metadata has no independent digest in the DATA-only parser.
        # Verify must reread the actual originals even if stored and outer claims agree.
        for field, replacement in (("sha256", "f" * 64), ("size", 1)):
            with self.subTest(boundary="verify-originals", field=field):
                model = ReportFixture()
                model.originals()
                custody = JVM.collect(model, model.api)
                original_directory = model.state_path / "evidence" / model.request["owner"]["productInvocation"]
                log_path = original_directory / "stop.stdout.log"
                original_log = model.files[log_path]
                changed = copy.deepcopy(custody)
                selected = [row for row in changed["retainedFiles"] if row["path"] == "stop.stdout.log"]
                self.assertEqual(len(selected), 1)
                row = selected[0]
                self.assertEqual(row, {"path": "stop.stdout.log", "size": len(original_log),
                                       "sha256": H.digest(original_log)})
                self.assertNotEqual(row[field], replacement)
                row[field] = replacement
                self.assertNotEqual(changed, custody)
                result_path = model.evidence.path / JVM.PROFILE / "result.json"
                model.put(result_path, changed)
                outer = model.result(changed)
                self.assertEqual(model.files[result_path], I.encoded(outer["custody"]))
                before_snapshots, before_resources = len(model.snapshots), len(model.resources)
                with self.assertRaisesRegex(JVM.JvmCustodyError, "^JVM_LIBRARY_COLLECTION_RESULT_CHANGED$"):
                    JVM.verify(model, model.api, model.private, model.run_context_raw, outer, model.end, lambda: None)
                self.assertEqual(model.files[log_path], original_log)
                self.assertEqual(model.snapshots[before_snapshots:], [original_directory])
                acquired = model.resources[before_resources:]
                self.assertEqual([item["label"] for item in acquired],
                    ["jvm-original-snapshot"] + ["jvm-original-reader"] * len(custody["retainedFiles"]))
                self.assertTrue(all(item["attempted"] and item["closed"] for item in model.resources))
                self.assertFalse(model.unknown)

    def test_wrong_tasks_effective_flags_source_context_home_or_invocation_fails(self):
        for change in (lambda r: r["requestedArgv"].append("help"),
                lambda r: r["executedArgv"].remove("--rerun-tasks"),
                lambda r: r["sourceAfter"].update(commit=HEAD), lambda r: r.update(gradleHome="/other/home"),
                lambda r: r.update(id="d" * 32), lambda r: r.update(productPid=999),
                lambda r: r["ownership"].update(invocation="d" * 32)):
            model = ReportFixture()
            model.originals()
            model.change_original("receipt.json", change)
            with self.assertRaises(JVM.JvmCustodyError): model.collection()
        for field, wrong in (("contextSha256", "f" * 64), ("tasks", ["help"]), ("reportRoots", list(JVM.ROOTS[:5])),
                             ("home", "/other/home"), ("scope", "CLI_CUSTODY")):
            model = ReportFixture()
            value = {**model.request, field: wrong}
            with self.assertRaises(JVM.JvmCustodyError):
                JVM.request_data(I.encoded(value), model.run_context_raw, model.canonical_context_raw)
        for role in HOSTS:
            model = ReportFixture(role)
            model.originals()
            phase = copy.deepcopy(model.inputs["phase"])
            phase["ownership"]["startedIdentities"] = []
            with self.assertRaises(JVM.JvmCustodyError): model.collection(phase=phase)

    def test_links_aliases_extra_eof_oversize_and_failed_read_or_close_preserve_original_failure(self):
        # Exercise the maintained POSIX snapshot's link checks with supplied
        # stat/descriptor DATA; no real links or native descriptors are created.
        for mode, links in ((stat.S_IFLNK | 0o600, 1), (stat.S_IFREG | 0o600, 2)):
            before = SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFDIR | 0o700, st_uid=1,
                                     st_nlink=1, st_size=0, st_mtime_ns=1, st_ctime_ns=1)
            info = SimpleNamespace(**{**vars(before), "st_ino": 3, "st_mode": mode, "st_nlink": links})
            @contextmanager
            def entries(_fd):
                yield [SimpleNamespace(name="report", stat=lambda **_kwargs: info)]
            system = SimpleNamespace(open=Mock(return_value=9), close=Mock(), fstat=Mock(return_value=before),
                scandir=entries, getuid=lambda: 1, O_RDONLY=0, O_DIRECTORY=1, O_NOFOLLOW=2)
            with patch.object(C.posix, "os", system), self.assertRaises(C.posix.EvidenceError):
                C.posix_snapshot(C.PrivateOwner(), Path("/model"), JVM.REPORT_LIMIT, JVM.MEMBER_LIMIT,
                                 time.monotonic() + 60)
            system.close.assert_called_once_with(9)
        for unsafe in ("../x", "a//b", "a\\b", "/absolute", "a/./b"):
            with self.assertRaises(JVM.JvmCustodyError): JVM._path(unsafe)
        with self.assertRaisesRegex(C.ControllerError, "HASH_MEMBER_GREW"):
            C.hash_stream(io.BytesIO(b"xx"), 1, time.monotonic() + 60)
        with self.assertRaisesRegex(C.ControllerError, "HASH_MEMBER_TRUNCATED"):
            C.hash_stream(io.BytesIO(b"x"), 2, time.monotonic() + 60)
        model = ReportFixture()
        model.originals()
        manifest, receipt = decoded(model.inputs["manifest_raw"]), decoded(model.inputs["receipt_raw"])
        manifest["records"][0]["bytes"] = JVM.REPORT_LIMIT + 1
        receipt["reports"] = manifest["records"]
        with self.assertRaises(JVM.JvmCustodyError):
            JVM.report_data(I.encoded(manifest), receipt, model.inputs["files"])
        manifest = decoded(model.inputs["manifest_raw"])
        alias = {**manifest["records"][0], "source": manifest["records"][0]["source"].upper()}
        manifest["records"].append(alias)
        with self.assertRaisesRegex(JVM.JvmCustodyError, "REPORT_METADATA"):
            JVM.report_data(I.encoded(manifest), {"reports": manifest["records"]}, model.inputs["files"])
        for read_fails in (True, False):
            owner = MemoryOwner()
            directory = owner.mkdir(Path("/model/originals"))
            read_error, close_error = OSError("MODEL_READ_FAILED"), OSError("MODEL_CLOSE_FAILED")
            stream = SimpleNamespace(read=Mock(side_effect=read_error if read_fails else [b"x", b""]),
                                     close=Mock(side_effect=close_error))
            snapshot = SimpleNamespace(entries={"report": SimpleNamespace(size=1, is_directory=False)},
                open_file=Mock(return_value=stream), verify=Mock(), close=Mock())
            directory.snapshot = Mock(return_value=snapshot)
            api = {**vars(C), "os": SimpleNamespace(name="nt")}
            with self.assertRaises((OSError, JVM.JvmCustodyError)):
                JVM.inventory(owner, api, directory, time.monotonic() + 60, lambda: None)
            self.assertIs(owner.original, read_error if read_fails else close_error)
            self.assertTrue(owner.unknown)
            stream.close.assert_called_once()
            snapshot.close.assert_called_once()

    def test_cancellation_infrastructure_exit_failed_stop_and_native_survivors_never_pass(self):
        changes = ({"cancelledSignals": [15]}, {"cancelRequested": True}, {"productExitCode": 125, "finalExitCode": 125},
            {"stopExitCode": 1}, {"errors": ["MODEL_INFRASTRUCTURE"]}, {"ownedSurvivors": [{"pid": 102}]})
        for change in changes:
            model = ReportFixture()
            model.originals()
            model.change_original("receipt.json", lambda value: value.update(change))
            with self.assertRaisesRegex(JVM.JvmCustodyError, "CANONICAL_STOP_SOURCE_OR_RETIREMENT"): model.collection()
        for change in ({"retirement": "UNKNOWN"}, {"survivors": [{"pid": 101}]}, {"cooperativeCancellation": 15},
                       {"launchAttempted": False}, {"finalizedRawNs": (10012 + 870) * NS},
                       {"completedRawNs": (10012 + 825) * NS}):
            model = ReportFixture()
            model.originals()
            with self.assertRaises(JVM.JvmCustodyError): model.collection(phase={**model.inputs["phase"], **change})


class JvmControllerControls(unittest.TestCase):
    def test_jvm_uses_file_only_reservation_collection_and_no_cli_loader_or_uninstall(self):
        model = ReportFixture()
        model.originals()
        model.collect_attempted, model.uninstall_attempted, model.custody = False, False, None
        model.phase = Mock(side_effect=AssertionError("FILE_ONLY_COLLECTION_MUST_NOT_LAUNCH"))
        collect = JVM.collect
        # Only substitute the file graph. The real controller's dispatch,
        # one-shot latch, real collector and first-error owner remain in use.
        with patch.object(JVM, "collect", side_effect=lambda owner, _api: collect(owner, model.api)) as entered:
            C.Controller.collect(model)
            C.Controller.collect(model)
            self.assertEqual(entered.call_count, 1)
        self.assertEqual(model.custody["operation"]["scope"], JVM.FILE_ONLY)
        self.assertFalse(model.uninstall_attempted)
        model.phase.assert_not_called()
        self.assertEqual(C.JVM_ORDER, ("job-time", "recipient-validation", "audit-init", "product", "export"))
        stub = SimpleNamespace(profile=JVM.PROFILE, check=Mock())
        for label in ("custody-prepare", "custody-collect", "custody-uninstall", "sample-packaging"):
            with self.assertRaisesRegex(C.ControllerError, "JVM_CLOSED_NATIVE_PHASE"):
                C.Controller.phase(stub, label, ["NEVER_EXECUTED"], 1)
        failure = OSError("MODEL_COLLECTION_ORIGINAL_FAILURE")
        failed = ReportFixture()
        failed.collect_attempted, failed.custody = False, None
        with patch.object(JVM, "collect", side_effect=failure) as entered:
            with self.assertRaises(OSError) as caught: C.Controller.collect(failed)
            self.assertIs(caught.exception, failure)
            C.Controller.collect(failed)
            self.assertEqual(entered.call_count, 1)
        self.assertIs(failed.original, failure)
        self.assertTrue(failed.unknown)

    def test_product_calls_unchanged_canonical_executor_exactly_once_with_original_bounds(self):
        for role in HOSTS:
            model = ReportFixture(role)
            model.originals()
            subject = SimpleNamespace(profile=JVM.PROFILE, role=role, request=model.request, kind="gradle",
                command=list(model.request["command"]), unknown=False, product=None)
            subject.python = Mock(side_effect=lambda _path, *args:
                C.canonical_python(model.context["python"], model.context["canonicalSources"], *args))
            subject.phase = Mock(return_value=model.inputs["phase"])
            C.Controller.product_run(subject)
            self.assertEqual(subject.python.call_count, 1)
            self.assertEqual(subject.python.call_args.args[0], ROOT / "scripts/run-audit-command.py")
            args = list(subject.python.call_args.args)
            self.assertEqual(args[args.index("--timeout") + 1], 600)
            self.assertEqual(args[args.index("--stop-timeout") + 1], 120)
            self.assertEqual(args[args.index("--id") + 1], model.request["owner"]["productInvocation"])
            self.assertEqual(args[args.index("--") + 1:], [*JVM.TASKS, "--continue", "--console=plain"])
            subject.phase.assert_called_once_with("product", model.inputs["phase"]["argv"], 825, product=True)
            self.assertIs(subject.product, model.inputs["phase"])
        self.assertEqual(C.audit.gradle_arguments([*JVM.TASKS, "--continue", "--console=plain"]),
                         C.audit.gradle_arguments(JVM.command("linux-x64")[1]))

    def test_provider_gate_precedes_jdks_init_seed_and_product_without_service_credentials(self):
        source = (ROOT / ".github/workflows/ci.yml").read_text()
        body = source.split("  jvm-library-checks:\n", 1)[1].split("  complete-gate:\n", 1)[0]
        ids = ['id: "ordinary-admission"', 'id: "dependency-stage"', 'id: "initial-dependency-stage"',
               'id: "dependency-ready"', 'id: "java"', 'id: "ordinary-jdk21"', 'id: "ordinary-run"',
               'id: "initial-run"']
        self.assertEqual([body.index(value) for value in ids], sorted(body.index(value) for value in ids))
        self.assertIn("java-version: |\n            21\n            17", body)
        self.assertIn("steps.dependency-ready.outcome == 'success'", body)
        self.assertNotIn("setup-gradle", body)
        self.assertNotIn("retention-days: 7", body)
        self.assertNotIn("--stop --console", body)
        before_run = body.split('id: "ordinary-run"', 1)[1].split("      - name:", 1)[0]
        self.assertNotIn("P2PKIT_ACTIONS_READ_TOKEN", before_run)
        supplied = {"JAVA_HOME": "/model/jdk17", "P2PKIT_AUDIT_JDK21": "/model/jdk21", "PATH": "/model/bin",
            "GITHUB_JOB": "jvm-library-checks", "GITHUB_OUTPUT": "/model/outputs", "GITHUB_ENV": "/model/environment",
            **{name: "SYNTHETIC_NOT_A_CREDENTIAL" for name in
               (B.TOKEN_ENV, "GH_TOKEN", "GITHUB_TOKEN", *H.provider_environment.SERVICE_FIELDS)}}
        with patch.object(C.query, "_inherited_context", return_value={}):
            child = C.child_environment(supplied, Path("/model/session"), Path("/model/session/state"))
        self.assertEqual(child["GITHUB_JOB"], "jvm-library-checks")
        for name in (B.TOKEN_ENV, "GH_TOKEN", "GITHUB_TOKEN", "GITHUB_OUTPUT", "GITHUB_ENV",
                     *H.provider_environment.SERVICE_FIELDS):
            self.assertNotIn(name, child)
        controller = (ROOT / "scripts/run-hosted-test-custody.py").read_text()
        setup = controller.split("    def setup(self):\n", 1)[1].split("    def prepare_seed_intent", 1)[0]
        self.assertLess(setup.index("self.prepare_identity()"), setup.index('self.crypto_operation("validate")'))
        self.assertLess(setup.index('self.phase("audit-init"'), setup.index("self.seed_dependencies()"))
        self.assertLess(setup.index("self.seed_dependencies()"), setup.index("self.request_raw = jvm.reserve"))

    def test_profile_success_requires_original_native_custody_cache_and_job_budget(self):
        for role in HOSTS:
            model = ReportFixture(role)
            model.originals()
            result = model.result()
            self.assertTrue(C.profile_passed(result))
            changes = (lambda v: v.update(productAttempted=False), lambda v: v.update(cancelled=True),
                lambda v: v.update(retirement="UNKNOWN"), lambda v: v.update(errors=["MODEL_ERROR"]),
                lambda v: v["phases"].pop(0), lambda v: v["phases"][1].update(launchAttempted=False),
                lambda v: v["phases"][1].update(exitCode=True),
                lambda v: v["phases"][1]["ownership"].update(discoveryErrors=["MODEL_DISCOVERY"]),
                lambda v: v.update(dependencyCache=None), lambda v: v["dependencyCache"].update(scope="DESKTOP_ALIAS"),
                lambda v: v.update(dependencySeed=None), lambda v: v["dependencySeed"].update(admittedBytes=0),
                lambda v: v["dependencySeed"].update(admittedCount=True),
                lambda v: v["jobBudget"].update(exhausted=True), lambda v: v["jobBudget"].update(sha256="f" * 64),
                lambda v: v["custody"].update(productPhaseSha256="f" * 64),
                lambda v: v["custody"].update(missingRoots=[JVM.ROOTS[0]]),
                lambda v: v.update(samplePackaging={"required": True, "status": "PASS", "manifestSha256": "a" * 64}))
            for change in changes:
                value = copy.deepcopy(result)
                change(value)
                self.assertFalse(C.profile_passed(value))
            # An ordinary result cannot simply relabel itself as initial.
            self.assertFalse(C.profile_passed({**result, "scope": H.INITIAL_RESULT_SCOPE}))

    def test_frozen_jvm_originals_bind_crypto_return_and_post_return_seal(self):
        for role in HOSTS:
            model = ReportFixture(role)
            model.originals()
            frozen = model.freeze()
            self.assertEqual(frozen["scope"], JVM.FROZEN_SCOPE)
            self.assertEqual(frozen["source"], model.context["source"])
            self.assertEqual(frozen["requestSha256"], H.digest(model.request_raw))
            self.assertEqual(frozen["canonicalReceiptSha256"], H.digest(model.inputs["receipt_raw"]))
            self.assertEqual(frozen["retainedFiles"], model.inputs["files"])
            self.assertEqual(model.snapshots.count(model.path / "frozen-evidence"), 1)
            self.assertEqual(model.snapshots.count(model.evidence.path / "canonical-audit"), 1)
            outer = decoded(model.files[model.path / "frozen-evidence/original-path-map.json"])
            row = next(row for row in outer["files"] if row["original"] == "jvm-library/request.json")
            model.files[model.path / "frozen-evidence" / row["member"]] += b"\n"
            with self.assertRaisesRegex(JVM.JvmCustodyError, "FROZEN_ORIGINAL_BYTES_CHANGED"):
                JVM.frozen_binding(model, model.api, model.private, model.end, lambda: None)
        source = (ROOT / "scripts/run-hosted-test-custody.py").read_text()
        for literal in ('self.export_return["result"].get("jvmLibraryFrozen") ==',
                'exported["jvmLibraryFrozen"] = jvm_frozen',
                '(profile == jvm.PROFILE) == ("jvmLibraryFrozen" in returned)',
                'jvm_frozen == returned["jvmLibraryFrozen"]', 'JVM_CHANGED_DURING_ORIGINAL_EXPORT',
                'JVM_POST_RETURN_INPUT_CHANGED'):
            self.assertIn(literal, source)

    def test_known_failed_test_evidence_can_be_encrypted_without_turning_profile_green(self):
        for roots in (0, 3, 6):
            model = ReportFixture()
            model.originals(exit_code=1, roots=roots)
            frozen = model.freeze()
            self.assertEqual(frozen["disposition"], "FAILED_TEST_OR_REPORTS")
            value = decoded(model.files[model.evidence.path / "profile-result-before-export.json"])
            self.assertFalse(C.profile_passed(value))
            value["encrypted"] = True  # Supplied label only; no crypto invocation.
            value["phases"].append({**value["phases"][1], "phase": "export"})
            self.assertFalse(C.profile_passed(value))
            self.assertEqual(len(frozen["retainedFiles"]), len(JVM.FIXED) + roots)
        source = (ROOT / ".github/workflows/ci.yml").read_text()
        body = source.split("  jvm-library-checks:\n", 1)[1].split("  complete-gate:\n", 1)[0]
        self.assertEqual(body.count('test "$PROFILE_PASSED" = true'), 2)
        for origin in ("ordinary", "initial"):
            upload = body.split('id: "' + origin + '-evidence"', 1)[1].split("      - name:", 1)[0]
            self.assertIn(".outputs.artifacts_ready == 'true'", upload)
            self.assertNotIn(".outputs.profile_passed == 'true'", upload)
            self.assertIn("retention-days: 14", upload)

    def test_unknown_or_changed_originals_never_become_upload_ready_or_boolean_success(self):
        model = ReportFixture()
        model.originals()
        model.freeze()
        model.change_original("receipt.json", lambda value: value.update(stopExitCode=1))
        with self.assertRaises(JVM.JvmCustodyError):
            JVM.frozen_binding(model, model.api, model.private, model.end, lambda: None)
        not_started = ReportFixture()
        result = not_started.result()
        result.update(profilePassed=True, readyForPostReturnSeal=True, encrypted=True)
        self.assertFalse(C.profile_passed(result))
        for field in ("RUN", "SEAL"):
            for outcome in ("failure", "cancelled", "skipped", ""):
                env = {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "success", "P2PKIT_HOSTED_TEST_SEAL_OUTCOME": "success",
                       "P2PKIT_HOSTED_TEST_" + field + "_OUTCOME": outcome}
                with patch.dict(os.environ, env, clear=True), \
                        self.assertRaisesRegex(C.ControllerError, "DELIVERY_REQUIRES_ORIGINAL_SUCCESS"):
                    C.delivery_inputs(MemoryOwner(), time.monotonic() + 60, profile=JVM.PROFILE)
        with patch.dict(os.environ, {"P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME": "failure"}, clear=True), \
                self.assertRaisesRegex(C.ControllerError, "UPLOAD_ORIGINAL_ACTION_FAILED"):
            C._desktop_upload_guard("after", JVM.PROFILE, initial_kind=False, cancelled=[])

    def test_jvm_upload_before_after_use_original_deadline_scope_hash_and_source(self):
        for role in HOSTS:
            with initial_fixture(role) as values:
                initial_budget = B.derive_initial_retained(values["bound"], AF.originals(values), "a" * 32)
                for origin, budget in (("ordinary", ordinary_budget(role)), ("initial", initial_budget)):
                    if origin == "initial":
                        _request, context_raw, _started = AF.crypto_fixture(values, budget)
                        context = decoded(context_raw)
                    else:
                        context = ReportFixture(role).context
                        context_raw = I.encoded(context)
                    terminal = budget.value["responseFinishedRawNs"] + 30 * NS
                    result = {"profile": JVM.PROFILE, "jobBudget": {"terminalRawNs": terminal}}
                    end_raw = C.desktop_delivery_end(budget, result)
                    seal = {"sealedAtRawNs": terminal + NS}
                    if origin == "initial":
                        seal["initialOrdinary"] = {"currentSha256": "1" * 64}
                    owner = MemoryOwner()
                    data = {"context": context, "contextRaw": context_raw, "resultRaw": I.encoded(result),
                        "seal": seal, "sealRaw": I.encoded(seal), "budget": budget, "endRawNs": end_raw,
                        "clock": SimpleNamespace(last=terminal), "private": owner.mkdir(Path("/model/upload"))}
                    scope = "CLOSED_" + ("INITIAL_ORDINARY_" if origin == "initial" else "") + \
                            "JVM_LIBRARY_UPLOAD_SCHEDULING_CAP"
                    self.assertEqual(C.desktop_upload_scope(data), scope)
                    began, observed = terminal + 2 * NS, terminal + 3 * NS
                    limit = min(end_raw, began + 180 * NS)
                    before = {**C.delivery_binding(data, scope), "beganRawNs": began, "endRawNs": limit,
                        "timeoutObservedRawNs": observed, "timeoutMinutes": (limit - observed) // (60 * NS)}
                    if origin == "initial":
                        before["initialSource"] = {"identitySha256": context["admissionSha256"],
                            "historySha256": context["initialOrdinary"]["historySha256"], "currentSha256": "2" * 64,
                            "lateSourceOriginals": "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD"}
                    before_raw = I.encoded(before)
                    self.assertEqual(C.desktop_upload_before(data, before_raw), before)
                    after = {**C.delivery_binding(data, scope), "beforeSha256": H.digest(before_raw),
                             "observedRawNs": observed + NS, "stepOutcome": "success"}
                    if origin == "initial":
                        after["initialSource"] = {**before["initialSource"], "currentSha256": "3" * 64}
                    owner.put(data["private"].path / "upload-before.json", before_raw)
                    owner.put(data["private"].path / "upload-after.json", after)
                    self.assertEqual(C.desktop_upload_pair(owner, data, 1), (before_raw, I.encoded(after)))
                    for change in ({"scope": "CLOSED_DESKTOP_UPLOAD_SCHEDULING_CAP"}, {"jobBudgetSha256": "f" * 64},
                            {"source": {"commit": HEAD, "tree": TREE}}, {"endRawNs": limit + NS},
                            {"timeoutMinutes": 4}, {"sealSha256": "f" * 64}):
                        with self.assertRaises(C.ControllerError):
                            C.desktop_upload_before(data, I.encoded({**before, **change}))
                    for change in ({"observedRawNs": limit}, {"stepOutcome": "failure"}, {"beforeSha256": "f" * 64}):
                        owner.put(data["private"].path / "upload-after.json", {**after, **change})
                        with self.assertRaises(C.ControllerError): C.desktop_upload_pair(owner, data, 1)
                    if origin == "initial":
                        for reused in ("1" * 64, "2" * 64):
                            owner.put(data["private"].path / "upload-after.json",
                                {**after, "initialSource": {**after["initialSource"], "currentSha256": reused}})
                            with self.assertRaisesRegex(C.ControllerError, "SOURCE_REUSED"):
                                C.desktop_upload_pair(owner, data, 1)


if __name__ == "__main__":
    unittest.main(failfast=True)
