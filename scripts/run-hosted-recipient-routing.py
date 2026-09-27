#!/usr/bin/env python3
"""Fixed nonproductive recipient routing and real Stage2 predecessor acquisition.

Routing is DATA, never an Admission/current/approval. The gate acquires its own
original current; workers must independently reacquire theirs. Both ordinary
activation HOLDs and all C1/C2/native/provider/custody qualifications remain.
No product, key operation, cache restore, upload or publication occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import signal
import stat
import sys
import threading
import time

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).absolute().parent
ROOT = SCRIPTS.parent
if __name__ == "__main__":
    sys.path.insert(0, str(SCRIPTS))

import hosted_initial_ordinary_adapter as initial
import hosted_initial_recipient_stages as stages
import hosted_job_clock as clocks
import hosted_test_identity as I
import hosted_test_query as queries

ROUTE_SCOPE = "HOSTED_RECIPIENT_ROUTE_DATA_V1"
SOURCE_SECONDS, FINAL_SECONDS = 75, 120
CONTEXT_FIELDS = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL",
    "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "RUNNER_TEMP",
    "GITHUB_JOB", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_REF",
    "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH",
)
TOKEN = "P2PKIT_ACTIONS_READ_TOKEN"


def require(value, code):
    I.require(value, "RECIPIENT_ROUTING_" + code)


def digest(raw):
    require(type(raw) is bytes, "DIGEST_BYTES")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, repr=False)
class RouteDecision:
    """Immutable private route inputs, not native or provider authority."""

    record: bytes
    original_event: bytes
    original_policy: bytes


def _context(profile, environment, job):
    require(type(profile) is str and profile in I.PROFILES and type(environment) is dict, "PROFILE")
    env = environment
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == I.REPOSITORY and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and
            env.get("GITHUB_API_URL") == "https://api.github.com" and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted" and env.get("GITHUB_JOB") == job and
            (env.get("RUNNER_OS"), env.get("RUNNER_ARCH")) == ("Linux", "X64"), "HOSTED_CONTEXT")
    runner = env.get("RUNNER_NAME")
    require(type(runner) is str and 0 < len(runner) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in runner), "RUNNER_NAME")
    require(not any(name.startswith("GIT_") and name != "GIT_TERMINAL_PROMPT" for name in env), "GIT_OVERRIDE")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(type(env.get(name)) is str and I.ID.fullmatch(env[name]), "RUN")
    event_name, ref = env.get("GITHUB_EVENT_NAME"), env.get("GITHUB_REF")
    require(event_name in ("push", "pull_request", "schedule", "workflow_dispatch") and
            type(ref) is str and 0 < len(ref) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in ref), "EVENT_REF")
    source = I.sha(env.get("GITHUB_SHA"))
    workflow = I.PROFILES[profile][0]
    require(env.get("GITHUB_WORKFLOW_SHA") == source and
            env.get("GITHUB_WORKFLOW_REF") == I.REPOSITORY + "/" + workflow + "@" + ref, "WORKFLOW")
    return source, workflow, event_name, ref


def decide_source_mode(profile, environment, event_raw, git, now):
    """Pure DATA seam using maintained GitView/policy contracts, not _admit.

    Only a successful exactly empty original-base ls-tree may select the narrow
    initial path. Present malformed policy and every query failure fail closed.
    Ordinary fork PRs continue to use their genuine trusted original-base policy.
    """
    source, workflow, event_name, ref = _context(profile, environment, "recipient-route")
    workspace = environment.get("GITHUB_WORKSPACE")
    require(type(workspace) is str and Path(workspace).is_absolute() and ".." not in Path(workspace).parts and
            str(git.root) == workspace, "WORKSPACE")
    require(git.root_matches() and git.clean() and git.commit("HEAD") == source, "SOURCE")
    require(git.query("rev-parse", "--is-shallow-repository") in (b"false\n", b"false\r\n"), "FULL_HISTORY")
    tree = I.sha(git.tree(source))
    event = I.parse(event_raw, I.EVENT_LIMIT)
    repository = I.mapping(event.get("repository"))
    require(repository.get("full_name") == I.REPOSITORY and repository.get("default_branch") == "main",
            "REPOSITORY")
    detail = {}
    if event_name == "pull_request":
        pr = I.mapping(event.get("pull_request"))
        number = event.get("number")
        require(type(number) is int and 0 < number <= 10 ** 10 and type(pr.get("number")) is int and
                pr["number"] == number and ref == f"refs/pull/{number}/merge" and pr.get("state") == "open" and
                pr.get("merged") is False and event.get("action") in ("opened", "reopened", "synchronize"), "PR")
        base, head = I.mapping(pr.get("base")), I.mapping(pr.get("head"))
        require(I.mapping(base.get("repo")).get("full_name") == I.REPOSITORY and base.get("ref") == "main", "PR_BASE")
        head_repository = I.mapping(head.get("repo")).get("full_name")
        require(type(head_repository) is str and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", head_repository),
                "PR_HEAD")
        base_sha, head_sha = I.sha(base.get("sha")), I.sha(head.get("sha"))
        require(git.parents(source) == [base_sha, head_sha], "PR_PARENTS")
        policy_commit = base_sha
        detail = {"number": number, "base": base_sha, "head": head_sha, "headRepository": head_repository}
    elif event_name == "push":
        require(ref == event.get("ref") == "refs/heads/main" and event.get("after") == source and
                event.get("deleted") is False, "PUSH")
        policy_commit, detail = source, {"before": I.sha(event.get("before"))}
    elif event_name == "schedule":
        require(profile == "full" and ref == "refs/heads/main" and event.get("schedule") == "17 4 * * 1", "SCHEDULE")
        policy_commit, detail = source, {"schedule": event["schedule"]}
    else:
        require(ref.startswith("refs/heads/") and ref != "refs/heads/audit/complete-2026-09-04" and
                event.get("ref") in (ref, ref.removeprefix("refs/heads/")), "MANUAL_REF")
        require(event.get("inputs") is None or event.get("inputs") == {}, "MANUAL_INPUTS")
        policy_commit = I.sha(git.commit("refs/remotes/origin/main"))
        detail = {"policyMain": policy_commit}

    entry = git.query("ls-tree", "-z", policy_commit, "--", I.POLICY_PATH)
    require(type(entry) is bytes, "POLICY_ENTRY")
    origin = "ordinary"
    if entry == b"":
        require(event_name == "pull_request", "ABSENCE_REQUIRES_INITIAL_PR")
        require(base_sha == stages.BASE["commit"] and head_repository == I.REPOSITORY and
                head.get("ref") == stages.SOURCE_REF.removeprefix("refs/heads/") and
                source not in (base_sha, head_sha) and head_sha != base_sha, "INITIAL_PR_SOURCE")
        require(git.commit("refs/remotes/origin/main") == stages.BASE["commit"] and
                git.tree(stages.BASE["commit"]) == stages.BASE["tree"] and git.tree(head_sha) == tree,
                "INITIAL_MAIN_AND_MERGE")
        require(git.query("merge-base", base_sha, head_sha) in
                (base_sha.encode("ascii") + b"\n", base_sha.encode("ascii") + b"\r\n"), "INITIAL_ANCESTRY")
        origin, policy_commit = "initial", head_sha
        blob, policy_raw = git.policy(policy_commit)
        require(digest(policy_raw) == stages.POLICY_SHA256, "INITIAL_POLICY_HASH")
    else:
        match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(I.POLICY_PATH.encode("ascii")) + rb"\x00", entry)
        require(match is not None, "TRUSTED_POLICY_ENTRY")
        blob, policy_raw = git.policy(policy_commit)
        require(blob == match.group(1).decode("ascii"), "TRUSTED_POLICY_CHANGED")
    policy, _key = I._policy(policy_raw, now)
    require(git.root_matches() and git.clean() and git.commit("HEAD") == source and git.tree(source) == tree and
            git.query("rev-parse", "--is-shallow-repository") in (b"false\n", b"false\r\n"), "SOURCE_CHANGED")
    if origin == "initial":
        require(git.query("ls-tree", "-z", stages.BASE["commit"], "--", I.POLICY_PATH) == b"", "BASE_POLICY_CHANGED")
    require(git.policy(policy_commit) == (blob, policy_raw), "POLICY_CHANGED")
    recipient = policy["recipient"]
    record = {"schema": 1, "scope": ROUTE_SCOPE, "origin": origin, "profile": profile,
        "source": {"commit": source, "tree": tree},
        "github": {"repository": I.REPOSITORY, "event": event_name, "ref": ref, "workflow": workflow,
            "workflowSha": source, "job": "recipient-route", "runId": environment["GITHUB_RUN_ID"],
            "runAttempt": environment["GITHUB_RUN_ATTEMPT"], "eventSha256": digest(event_raw),
            "eventBinding": detail, "runnerOS": "Linux", "runnerArch": "X64"},
        "policy": {"commit": policy_commit, "blob": I.sha(blob), "path": I.POLICY_PATH,
            "sha256": digest(policy_raw), "fingerprint": recipient["fingerprint"], "keySha256": recipient["sha256"],
            "expiresAt": policy["expiresAt"], "retentionDays": 14}, "authority": "NOT_ACQUIRED"}
    return RouteDecision(I.encoded(record), event_raw, policy_raw)


def _environment():
    return dict(os.environ)


def _route_inputs(environment):
    root = Path(environment.get("GITHUB_WORKSPACE", ""))
    temporary = Path(environment.get("RUNNER_TEMP", ""))
    require(root == ROOT and root.is_absolute() and root == root.resolve(strict=True) and root.is_dir(), "ACTUAL_WORKSPACE")
    require(temporary.is_absolute() and temporary == temporary.resolve(strict=True) and temporary.is_dir() and
            temporary != root and root not in temporary.parents and temporary not in root.parents, "ACTUAL_TEMP")
    raw = I.read_regular(Path(environment.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    return root, temporary, raw


class _Scope:
    """Same-process local query caps and separate original Linux RAW fences."""

    def __init__(self):
        self.handlers, self.cancelled = {}, []
        self.cancellation = None
        self.first = None
        self.last = 0
        self.restored = False

    def start(self):
        require(threading.current_thread() is threading.main_thread(), "SIGNAL_OWNER")
        for number in (signal.SIGINT, signal.SIGTERM):
            self.handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: self.cancelled.append(signum))
        self.check_cancel()
        self.first = clocks.observe()
        require(self.first.clock.role == "linux-x64", "ACTUAL_LINUX_CLOCK")
        self.last = self.first.nanoseconds
        self.work_end_ns = self.last + SOURCE_SECONDS * clocks.NS
        self.final_end_ns = self.last + FINAL_SECONDS * clocks.NS
        self.local_deadlines = (
            clocks.local_deadline(self.first.clock, self.work_end_ns, SOURCE_SECONDS, minimum_ns=self.last),
            clocks.local_deadline(self.first.clock, self.final_end_ns, FINAL_SECONDS, minimum_ns=self.last),
        )
        self.check()

    def check_cancel(self):
        if self.cancelled:
            if self.cancellation is None:
                self.cancellation = KeyboardInterrupt("RECIPIENT_ROUTING_CANCELLED")
            raise self.cancellation

    def check(self, *, final=False):
        self.check_cancel()
        require(self.first is not None, "ORIGINAL_CLOCK_REQUIRED")
        self.last = clocks.checked_now(self.first.clock, minimum_ns=self.last)
        require(self.last < (self.final_end_ns if final else self.work_end_ns), "ORIGINAL_FENCE_EXPIRED")

    def restore(self):
        original = None
        for number, handler in self.handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                if original is None:
                    original = error
        self.restored = original is None
        if original is not None:
            raise original
        self.check_cancel()


def _retain_route(owner, decision):
    require(type(decision) is RouteDecision, "DECISION_REQUIRED")
    owner._check()
    for name, raw in (("recipient-route.json", decision.record), ("original-event.json", decision.original_event),
                      ("original-policy.json", decision.original_policy)):
        owner._write(owner.private, name, raw)
    owner._check()


def append_output(values):
    """Only two fixed public result sets; actual enclosing step success required."""
    require(type(values) is dict, "OUTPUT_FIELDS")
    if set(values) == {"origin", "route_sha256"}:
        require(values["origin"] in ("ordinary", "initial") and type(values["route_sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", values["route_sha256"]), "OUTPUT_ROUTE")
        names = ("origin", "route_sha256")
    else:
        require(set(values) == {"initial_gate_ready", "initial_gate_sha256"} and
                values["initial_gate_ready"] == "true" and type(values["initial_gate_sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", values["initial_gate_sha256"]), "OUTPUT_GATE")
        names = ("initial_gate_ready", "initial_gate_sha256")
    raw = "".join(name + "=" + values[name] + "\n" for name in names).encode("ascii")
    target = Path(os.environ.get("GITHUB_OUTPUT", ""))
    require(target.is_absolute() and target == target.resolve(strict=True), "OUTPUT_PATH")
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid(), "OUTPUT_FILE")
    descriptor = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    try:
        require(os.path.samestat(before, os.fstat(descriptor)), "OUTPUT_CHANGED")
        require(os.write(descriptor, raw) == len(raw), "OUTPUT_SHORT_WRITE")
        os.fsync(descriptor)
        require(os.path.samestat(before, target.lstat()), "OUTPUT_CHANGED")
    finally:
        os.close(descriptor)


def source_mode(profile):
    scope, owner, original, result = _Scope(), None, None, None
    try:
        scope.start()
        initial.forbid_service_environment()
        env = _environment()
        require(TOKEN not in env, "ROUTE_HAS_NO_CREDENTIAL")
        _context(profile, env, "recipient-route")
        root, temporary, event = _route_inputs(env)
        scope.check()
        directory = temporary / ("p2pkit-recipient-route-" + profile + "-" + env["GITHUB_RUN_ID"] + "-" +
                                 env["GITHUB_RUN_ATTEMPT"])
        owner = queries.NativeGitQueries(root, directory, check_cancel=scope.check_cancel,
                                        owner_deadlines=scope.local_deadlines)
        owner.native_host_matches_actions()
        git = I.GitView(root, env, owner)
        result = decide_source_mode(profile, env, event, git, int(time.time()))
        scope.check()
        _retain_route(owner, result)
        require(_environment() == env and _route_inputs(env) == (root, temporary, event), "INPUTS_CHANGED")
        require(decide_source_mode(profile, env, event, git, int(time.time())) == result, "DECISION_CHANGED")
        scope.check()
    except BaseException as error:
        original = error
    finally:
        if owner is not None:
            try:
                owner._finalize(original)
            except BaseException as error:
                if original is None:
                    original = error
        try:
            scope.restore()
        except BaseException as error:
            if original is None:
                original = error
    if original is not None:
        raise original
    require(owner is not None and owner.closed and not owner.failed and not owner.unknown and scope.restored and
            type(result) is RouteDecision, "CLOSED_ROUTE_REQUIRED")
    scope.check()
    require(_environment() == env and _route_inputs(env) == (root, temporary, event), "INPUTS_CHANGED_AFTER_CLOSE")
    initial.forbid_service_environment()
    I._policy(result.original_policy, int(time.time()))
    append_output({"origin": I.parse(result.record, I.EVENT_LIMIT)["origin"], "route_sha256": digest(result.record)})
    scope.check()
    initial.forbid_service_environment()
    require(_environment() == env and _route_inputs(env) == (root, temporary, event), "INPUTS_CHANGED_AFTER_OUTPUT")
    return result


def _gate_binding(native, current, profile, environment):
    require(native.checked_initial_ordinary(current) is current, "CHECKED_CURRENT_REQUIRED")
    eligible = native.initial_ordinary_eligibility(current)
    require(type(eligible) is initial.originals.gate.GateEligibility, "ACTUAL_GATE_ELIGIBILITY")
    value = I.parse(eligible.record, I.EVENT_LIMIT)
    raw = native.initial_ordinary_record(current)
    record = I.parse(raw, I.EVENT_LIMIT)
    source, workflow, event_name, ref = _context(profile, environment, "initial-recipient-gate")
    require(event_name == "pull_request" and value["scope"] == "NONPRODUCTIVE_ELIGIBILITY" and
            value["stage"] == "stage2" and record["scope"] == native.RETURN_SCOPE and
            record["kind"] == "gate" and record["profile"] == profile and record["role"] == "linux-x64" and
            record["identitySha256"] is None and record["matchSha256"] == digest(eligible.record) and
            record["source"] == value["source"] and value["source"]["commit"] == source and
            record["reviewed"] == value["reviewed"], "CURRENT_GATE_BINDING")
    require(value["github"] == {"event": event_name, "ref": ref, "workflow": workflow, "workflowSha": source,
            "job": "initial-recipient-gate", "runId": environment["GITHUB_RUN_ID"],
            "runAttempt": environment["GITHUB_RUN_ATTEMPT"], "runnerOS": "Linux", "runnerArch": "X64"},
            "CURRENT_GATE_CONTEXT")
    return raw


def initial_gate(profile):
    scope, original, native, current = _Scope(), None, None, None
    raw = None
    try:
        scope.start()
        initial.forbid_service_environment()
        env = _environment()
        _context(profile, env, "initial-recipient-gate")
        # No alternate loader, worker-fixed acquire_first or serialized current.
        native = initial.current_module()
        current = native.acquire_initial_ordinary(kind="gate", cancelled=scope.check_cancel,
            original_work_end_ns=scope.work_end_ns, original_final_end_ns=scope.final_end_ns)
        scope.check()
        require(TOKEN not in os.environ, "CURRENT_TOKEN_NOT_CONSUMED")
        raw = _gate_binding(native, current, profile, env)
        require(native.claim_initial_ordinary(current, "gate") is current, "ORIGINAL_GATE_CLAIM")
        require(_gate_binding(native, current, profile, env) == raw, "CURRENT_CHANGED_AFTER_CLAIM")
        scope.check()
    except BaseException as error:
        original = error
    finally:
        try:
            scope.restore()
        except BaseException as error:
            if original is None:
                original = error
    if original is not None:
        raise original
    require(scope.restored and native is not None and current is not None and type(raw) is bytes,
            "CLOSED_GATE_REQUIRED")
    scope.check()
    initial.forbid_service_environment()
    current_env = _environment()
    require(TOKEN not in current_env and all(current_env.get(name) == env.get(name) for name in CONTEXT_FIELDS),
            "GATE_CONTEXT_CHANGED")
    require(_gate_binding(native, current, profile, current_env) == raw, "CURRENT_CHANGED_AFTER_RESTORE")
    append_output({"initial_gate_ready": "true", "initial_gate_sha256": digest(raw)})
    scope.check()
    initial.forbid_service_environment()
    final_env = _environment()
    require(TOKEN not in final_env and all(final_env.get(name) == env.get(name) for name in CONTEXT_FIELDS),
            "GATE_CONTEXT_CHANGED_AFTER_OUTPUT")
    require(_gate_binding(native, current, profile, final_env) == raw, "CURRENT_CHANGED_AFTER_OUTPUT")
    return raw


def main():
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode and
                len(sys.argv) == 4 and sys.argv[1] in ("source-mode", "initial-gate") and
                sys.argv[2] == "--profile" and sys.argv[3] in I.PROFILES, "FIXED_COMMAND")
        (source_mode if sys.argv[1] == "source-mode" else initial_gate)(sys.argv[3])
        return 0
    except BaseException:
        # Original event, paths, tokens and native diagnostics never reach logs.
        os.write(2, b"RECIPIENT_ROUTING=HOLD; NO_WORKER_AUTHORITY\n")
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
