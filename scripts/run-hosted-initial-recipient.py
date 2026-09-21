#!/usr/bin/env python3
"""Dormant Stage1 native original acquisition; no Admission or execution grant.

The gate and populate worker use their actual identities. This fixed parent
owns the HTTP child and its nested read-only Git queries, reuses the maintained
native phase/finalization, and retains originals before returning a provisional
digest. No workflow invokes it. A successful command is not provider, recipient
crypto, budget, export or Stage2 qualification; original step outcome is still
required by any future caller. Both ordinary HOLDs remain separate.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import importlib.util
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import hosted_initial_recipient_originals as acquisition

# One fixed maintained controller, not a caller-selected plugin/command.
_spec = importlib.util.spec_from_file_location("_initial_recipient_native_owner", SCRIPTS / "run-hosted-cache-bootstrap.py")
native = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = native
_spec.loader.exec_module(native)

I, O, Q = acquisition.identity, acquisition.origin, native.query
SOURCE_KEYS = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
HTTP_KEYS = ("attempt", "jobs", "approvals", "comment", "environment", "branches", "main", "reviewed_ref")
ORIGINAL_KEYS = ("event", *SOURCE_KEYS, *HTTP_KEYS, "observation", "match")
CONTEXT_FIELDS = {"schema", "scope", "prelude", "observed", "eventSha256", "root", "session", "job",
                  "inheritedContext", "sourceReturnSha256", "sourceReturnedNs", "budgetAcceptance", "exportSaveAuthority"}
SOURCE_SCOPE = "INITIAL_RECIPIENT_SOURCE_QUERIES_RETURNED_V1"
CHILD_SCOPE = "INITIAL_RECIPIENT_ACQUISITION_PENDING_CHILD_CLOSE_V1"
RESULT_SCOPE = "INITIAL_RECIPIENT_ORIGINALS_PENDING_OWNER_CLOSE_V1"
OUTPUT_SCOPE = "INITIAL_RECIPIENT_ORIGINALS_PENDING_STEP_RETURN_V1"


@dataclass(frozen=True)
class SourceReturn:
    """Registered original call only; never populated from a disk receipt."""
    records: tuple
    session: bytes
    raw: bytes


def require(value, code):
    I.require(value, "INITIAL_NATIVE_" + code)


def location():
    job = os.environ.get("GITHUB_JOB")
    require(job in (acquisition.gate.JOB, acquisition.stages.bootstrap.JOB), "ACTUAL_JOB")
    kind = "gate" if job == acquisition.gate.JOB else "worker"
    run, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    acquisition.stages.joint.run({"runId": run, "runAttempt": attempt})
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(parent.is_absolute() and ".." not in parent.parts and parent == parent.resolve(strict=True) and
            parent.is_dir() and parent != ROOT and ROOT not in parent.parents and parent not in ROOT.parents,
            "PRIVATE_PARENT")
    for path in (parent, *parent.parents):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "PARENT_ALIAS")
    return kind, parent / ("p2pkit-initial-recipient-" + run + "-" + attempt + "-" + kind)


def host_context(first_use_at):
    kind, path = location()
    env = dict(os.environ)
    require(env.get("GITHUB_WORKSPACE") == str(ROOT) and ROOT == ROOT.resolve(strict=True), "WORKSPACE")
    event = I.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    return acquisition._context(env, event, kind, first_use_at), path, event


def query_owner(owner, fence, path):
    owner.end()
    require(owner.fence is fence, "QUERY_ORIGINAL_FENCE")
    work = min(owner.local_end, fence.deadline(O.WORK_SECONDS, limit=owner.work_limit))
    final = min(owner.local_end, fence.deadline(O.PRELUDE_SECONDS, final=True, limit=owner.final_limit))
    return Q.NativeGitQueries(ROOT, path, check_cancel=lambda: fence.now(limit=owner.work_limit),
                              owner_deadlines=(min(work, final), final))


def finish_queries(owner, supplier, failure):
    """Preserve actual finalizer failure; a provisional session is insufficient."""
    if supplier is not None:
        try:
            supplier._finalize(failure)
        except BaseException as error:
            failure = failure or error
    if (supplier is not None and supplier.unknown) or Q.QUARANTINE or native.diagnostics._QUARANTINE:
        error = failure or O.OriginError("INITIAL_NATIVE_QUERY_UNKNOWN")
        owner.error("initial-query", error, unknown=True)
        failure = failure or error
    if failure is not None:
        raise failure


def query_session(owner, directory):
    raw = owner.read(directory, "session-result.json")
    value = O.parse(raw)
    require(set(value) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"}
            and type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == "ORDINARY_GIT_QUERIES_ONLY"
            and value["result"] == "READY_FOR_CALLER_SEAL" and value["retirement"] == "KNOWN" and
            value["firstError"] is None and value["errors"] == [] and type(value["queries"]) is list and
            type(value["readbacks"]) is list and type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]),
            "QUERY_SESSION")
    return raw


def source_queries(owner, fence, context, path):
    """Actual closed native Git call, before/after the separate HTTP phase."""
    supplier = result = None
    failure = None
    try:
        supplier = query_owner(owner, fence, path)
        supplier.native_host_matches_actions()
        result = acquisition._source(I.GitView(ROOT, dict(os.environ), supplier), context, owner.end)
        for name in SOURCE_KEYS:
            # The maintained query writer supports the genuine empty ls-tree
            # stdout, without replacing absence by invented nonempty JSON.
            supplier._write(supplier.private, name + ".bin", result[name])
        owner.end()
    except BaseException as error:
        failure = error
    finally:
        finish_queries(owner, supplier, failure)
    owner.end()
    directory = owner.open(path)
    session = query_session(owner, directory)
    require(set(result) == set(SOURCE_KEYS) and all(owner.read(directory, name + ".bin") == result[name]
            for name in SOURCE_KEYS), "SOURCE_ORIGINALS_CHANGED")
    raw = owner.write(directory, "source-return.json", {"schema": 1, "scope": SOURCE_SCOPE,
        "originalsSha256": {name: O.digest(result[name]) for name in SOURCE_KEYS}, "sessionSha256": O.digest(session),
        "clock": O.clock_value(fence.clock), "returnedNs": fence.now(limit=owner.work_limit)})
    owner.end()
    returned = SourceReturn(tuple((name, result[name]) for name in SOURCE_KEYS), session, raw)
    require(str(path) not in owner.initial_sources, "SOURCE_QUERY_REUSE")
    owner.initial_sources[str(path)] = returned
    return returned


def source_readback(owner, path, original):
    require(type(original) is SourceReturn and owner.initial_sources.get(str(path)) is original, "NOT_ORIGINAL_SOURCE_RETURN")
    directory = owner.open(path)
    require(owner.read(directory, "source-return.json") == original.raw and
            query_session(owner, directory) == original.session and all(owner.read(directory, name + ".bin") == raw
            for name, raw in original.records), "SOURCE_RETURN_CHANGED")
    owner.end()
    return dict(original.records)


def context_record(raw, path, fence):
    value = O.parse(raw)
    require(set(value) == CONTEXT_FIELDS and raw == O.encoded(value) and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == native.INITIAL_CONTEXT_SCOPE and
            value["prelude"] == O.parse(fence.raw) and value["root"] == str(ROOT) and value["session"] == str(path)
            and value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "CONTEXT")
    require(type(value["observed"]) is dict, "CONTEXT_OBSERVATION")
    observed, actual_path, event = host_context(value["observed"].get("firstUseAt"))
    require(value["observed"] == observed and observed["role"] == fence.clock.role and actual_path == path and
            value["eventSha256"] == O.digest(event), "ACTUAL_CONTEXT_CHANGED")
    require(type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
            type(value["sourceReturnSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sourceReturnSha256"]),
            "CONTEXT_BINDINGS")
    require(fence.first <= O.integer(value["sourceReturnedNs"]) < fence.work, "SOURCE_RETURN_TIME")
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and all(type(x) is str for x in inherited.values()) and
            (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "PARENT_CONTEXT")
    return value, event


def start_record(raw, context_raw, context, path, fence):
    value = O.parse(raw)
    require(set(value) == native.START_FIELDS and raw == O.encoded(value) and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == native.PHASE_SCOPE and
            value["contextSha256"] == O.digest(context_raw) and
            value["argv"] == native.initial_command(O.digest(context_raw)) and value["cwd"] == str(ROOT) and
            value["role"] == fence.clock.role and value["job"] == context["job"] and value["state"] == str(path) and
            value["home"] == str(path / "control-home") and value["exitCode"] is None and value["launchAttempted"] is False and
            value["scopeAttempted"] is False and value["retirement"] == "UNKNOWN" and
            type(value["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["invocation"]), "PRELAUNCH")
    native.history.phase_start(native.history.snapshot(fence), context["sourceReturnedNs"], value)
    env = native.processes.ownership_environment(context["inheritedContext"], context["job"], value["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(value["inheritedContext"] == {name: env[name] for name in Q._CONTEXT}, "ORIGINAL_ANCESTORS")
    return value


def service_child(context_hash, minimum, cancelled):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    local_end = time.monotonic() + O.wire.ACQUIRE_SECONDS
    first = O.clocks.validate_reading(O.clocks.observe())
    require(first.nanoseconds >= O.integer(minimum), "CHILD_PRECEDES_LAUNCH")
    owner = native.Owner(local_end, first=first, cancelled=lambda: native.cancellation(cancelled))
    fence = directory = result_raw = None
    supplier = None
    try:
        _, path = location()
        private = owner.open(path)
        context_raw = owner.read(private, "context.json")
        require(O.digest(context_raw) == context_hash, "CHILD_CONTEXT_CHANGED")
        context = O.parse(context_raw)
        fence = O.Fence(context["prelude"], minimum=first.nanoseconds, cancelled=lambda: native.cancellation(cancelled))
        require(first.clock == fence.clock, "CHILD_CLOCK_CHANGED")
        context, event = context_record(context_raw, path, fence)
        directory = owner.child(private, "service")
        start_raw = owner.read(directory, "start.json")
        start = start_record(start_raw, context_raw, context, path, fence)
        inherited = Q._inherited_context()
        require(set(inherited) == set(Q._CONTEXT) and inherited == start["inheritedContext"], "CHILD_NATIVE_CONTEXT")
        domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
            inherited[native.processes.DOMAINS_ENV])[-1]
        require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]}
                and start["startedNs"] <= minimum <= first.nanoseconds < start["workEndNs"], "CHILD_ORIGINAL_LAUNCH")
        owner.bind(fence, work_limit=start["workEndNs"], final_limit=start["finalEndNs"])
        failure = None
        try:
            supplier = query_owner(owner, fence, path / "acquisition-queries")
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in ORIGINAL_KEYS and type(raw) is bytes, "ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = acquisition.acquire_bootstrap(ROOT, kind=context["observed"]["kind"],
                query_runner=supplier, invocation=domain["id"], token=token, retain=retain, fence=fence,
                original_work_end=start["workEndNs"], first_use_at=context["observed"]["firstUseAt"])
            token = None
            acquired = fence.now(limit=start["workEndNs"])
            require(dict(originals)["event"] == event, "CHILD_EVENT_CHANGED")
        except BaseException as error:
            failure = error
        finally:
            token = None
            finish_queries(owner, supplier, failure)
        # Only this actual successful finalizer return precedes the readback.
        returned = fence.now(limit=start["workEndNs"])
        queries = owner.open(path / "acquisition-queries")
        session = query_session(owner, queries)
        require(set(dict(originals)) == set(ORIGINAL_KEYS) and len(originals) == len(ORIGINAL_KEYS) and
                all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "CHILD_ORIGINALS_CHANGED")
        result_raw = owner.write(directory, "child-result.json", {"schema": 1, "scope": CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(fence.clock), "launchMinimumNs": minimum, "beganNs": first.nanoseconds,
            "metadataLastNs": owner.early_last, "acquiredNs": acquired, "queryReturnedNs": returned,
            "querySessionSha256": O.digest(session), "originalsSha256": {name: O.digest(raw) for name, raw in originals},
            "matchSha256": O.digest(match.record), "completedNs": fence.now(limit=start["workEndNs"]),
            "retirement": "KNOWN", "errors": []})
    except BaseException as error:
        owner.error("initial-service-child", error)
        if directory is not None and not owner.unknown:
            try:
                owner.write(directory, "child-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("initial-child-failure-retention", secondary)
    finally:
        token = None
        try:
            owner.close()
        except BaseException as error:
            owner.error("initial-child-close", error)
    if owner.original is not None:
        raise owner.original
    require(fence is not None and result_raw is not None and not owner.unknown, "CHILD_NO_ORIGINALS")
    native.posix._deadline(owner.local_end)
    closed = fence.now(limit=start["workEndNs"])
    return {"schema": 1, "scope": native.INITIAL_ACK_SCOPE, "invocation": domain["id"],
            "terminalSha256": O.digest(result_raw), "clock": O.clock_value(fence.clock), "closedNs": closed}, fence, start["workEndNs"]


def retained_match(context, raw, invocation, clock, work_start, work_end):
    """Recheck exact retained originals; only the native parent supplies origin."""
    observed = context["observed"]
    github = observed["github"]
    base = acquisition.API + "/actions/runs/" + github["runId"]
    attempt_path = base + "/attempts/" + github["runAttempt"]
    bodies, times, dates = {}, [], []
    def body(name, path):
        response, data, date = O.response_bytes(raw[name], path, invocation, clock)
        _, headers = O.wire.headers(base64.b64decode(response["headersBase64"], validate=True))
        require("link" not in headers and work_start <= response["startedNs"] <= response["finishedNs"] < work_end and
                (not times or times[-1] <= response["startedNs"]), "HTTP_ORIGINAL_INTERVAL")
        require(not dates or dates[-1] <= date and 0 <= date - dates[0] <=
                math.ceil((response["finishedNs"] - work_start) / O.NS) + O.wire.CACHE_SECONDS + 1, "HTTP_SERVICE_DATE")
        times.extend((response["startedNs"], response["finishedNs"]))
        dates.append(date)
        bodies[name] = data
        return data
    attempt = I.parse(body("attempt", attempt_path), O.wire.BODY_LIMIT)
    jobs = I.parse(body("jobs", attempt_path + "/jobs?per_page=100&page=1"), O.wire.BODY_LIMIT)
    acquisition._run(observed, attempt, jobs, dates[-1])
    approval = body("approvals", base + "/approvals")
    selected = acquisition.gate.select(stage="stage1", run_id=github["runId"], attempt=github["runAttempt"], approvals_raw=approval)
    selector = I.parse(selected.record, acquisition.stages.LIMIT)
    comment = body("comment", acquisition.API + "/issues/comments/" + str(selector["commentId"]))
    declaration, _, _ = acquisition.stages.statement(acquisition.stages.STAGE1, comment,
        selector["commentId"], selector["bodySha256"])
    require(selector["environmentId"] == declaration["environment"]["id"], "ENVIRONMENT_CHANGED")
    env_path = acquisition.API + "/environments/" + acquisition.stages.ENVIRONMENT
    env_raw = body("environment", env_path)
    branches = body("branches", env_path + "/deployment-branch-policies?per_page=100&page=1")
    acquisition.gate.check_environment(declaration["environment"], env_raw, branches)
    for name, branch, commit in (("main", "main", acquisition.stages.BASE["commit"]),
            ("reviewed_ref", acquisition.stages.SOURCE_REF.removeprefix("refs/heads/"), observed["source"]["commit"])):
        acquisition._ref(I.parse(body(name, acquisition.API + "/git/ref/heads/" + branch), acquisition.stages.LIMIT), branch, commit)
    observation = {"repository": I.REPOSITORY, "base": dict(acquisition.stages.BASE), "reviewed": observed["source"],
        "source": observed["source"], "firstUseAt": observed["firstUseAt"], "github": dict(github)}
    args = {name: raw[name] for name in SOURCE_KEYS}
    if observed["kind"] == "gate":
        observation["inputs"] = observed["inputs"]
        result = acquisition.gate.eligible(stage="stage1", approvals_raw=approval, comment_raw=comment,
            environment_raw=env_raw, branches_raw=branches, observation_raw=I.encoded(observation), now=int(time.time()),
            expected=acquisition.gate.GateEligibility(raw["match"]), **args)
    else:
        observation["github"].update(profile=acquisition.stages.bootstrap.PROFILE, selection=observed["inputs"]["selection"])
        result = acquisition.stages.match_bootstrap(comment_raw=comment, comment_id=selector["commentId"],
            body_sha256=selector["bodySha256"], observation_raw=I.encoded(observation), now=int(time.time()),
            expected=acquisition.stages.BootstrapMatch(raw["match"]), **args)
    require(raw["observation"] == I.encoded(observation), "OBSERVATION_CHANGED")
    return result, {"firstNs": times[0], "lastNs": times[-1]}


def read_phase(owner, private, context_raw, source, phase, fence):
    require(type(phase) is native.OriginalPhase and owner.phase_originals is phase and phase.context == context_raw and
            owner.fence is fence and any(x["owner"] is private and not x["attempted"] for x in owner.resources),
            "NOT_ORIGINAL_PHASE_RETURN")
    require(owner.read(private, "context.json") == context_raw and owner.read(private, "prelude.json") == fence.raw,
            "ORIGINAL_CONTEXT_CHANGED")
    context, event = context_record(context_raw, private.path, fence)
    policy = source_readback(owner, private.path / "source-before", source)
    require(context["sourceReturnSha256"] == O.digest(source.raw) and
            context["sourceReturnedNs"] == O.parse(source.raw)["returnedNs"], "SOURCE_CONTEXT_CHANGED")
    records = dict(phase.records)
    require(len(phase.records) == len(native.PHASE_FILES) and set(records) == native.PHASE_FILES, "PHASE_FILES")
    directory = owner.child(private, "service")
    for name, raw in records.items():
        require(type(raw) is bytes and owner.read(directory, name) == raw, "PHASE_FILE_CHANGED")
    start = start_record(records["start.json"], context_raw, context, private.path, fence)
    row, birth = (O.parse(records[name]) for name in ("result.json", "native-start.json"))
    native.baseline_record(records["baseline.json"], fence.clock.role)
    require(set(row) == native.TERMINAL_FIELDS and set(birth) == {"ownership", "leader", "preparerIdentity", "observedNs"},
            "NATIVE_FIELDS")
    preparer = native.closed_lifetime(row["preparerIdentity"], fence.clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], fence.clock.role) and
            preparer["pid"] != row["leader"]["pid"], "PREPARER_CHANGED")
    require(all(row.get(name) == start[name] for name in set(start) - {"exitCode", "launchAttempted", "scopeAttempted", "retirement"})
            and type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
            row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
            row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b""
            and row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
            row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"], "NATIVE_RETURN")
    argv = native.initial_command(O.digest(context_raw), O.integer(row["launchMinimumNs"], start["startedNs"]))
    require(row["launchArgv"] == argv, "EXECUTED_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    require(birth["ownership"]["launches"] == row["ownership"]["launches"], "NATIVE_BIRTH_CHANGED")
    require(row["captureOutcomes"] == {name: {"synced": True, "verified": True, "closeAttempted": True, "closed": True,
            "readback": True} for name in ("stdout", "stderr")} and all(type(x) is bool for value in row["captureOutcomes"].values()
            for x in value.values()) and row["captures"] == {name: {"sha256": O.digest(records[name + ".log"]),
            "bytes": len(records[name + ".log"])} for name in ("stdout", "stderr")}, "CAPTURE_RETIREMENT")
    child_raw = owner.read(directory, "child-result.json")
    child, ack = O.parse(child_raw), O.parse(records["stdout.log"])
    require(records["stdout.log"] == O.encoded(ack) and set(ack) == {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs"}
            and type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == native.INITIAL_ACK_SCOPE and
            ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
            ack["clock"] == O.clock_value(fence.clock), "CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "invocation", "clock", "launchMinimumNs", "beganNs",
            "metadataLastNs", "acquiredNs", "queryReturnedNs", "querySessionSha256", "originalsSha256", "matchSha256", "completedNs",
            "retirement", "errors"} and type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == CHILD_SCOPE and
            child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
            child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(fence.clock) and
            child["launchMinimumNs"] == row["launchMinimumNs"] and child["retirement"] == "KNOWN" and child["errors"] == [], "CHILD_RESULT")
    queries = owner.open(private.path / "acquisition-queries")
    session = query_session(owner, queries)
    raw = {name: owner.read(queries, name + ".bin") for name in ORIGINAL_KEYS}
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
            {name: O.digest(data) for name, data in raw.items()} and child["matchSha256"] == O.digest(raw["match"])
            and raw["event"] == event and {name: raw[name] for name in SOURCE_KEYS} == policy, "ORIGINAL_BYTES_CHANGED")
    match, service = retained_match(context, raw, start["invocation"], fence.clock, start["startedNs"], start["workEndNs"])
    require(child["acquiredNs"] <= O.integer(child["queryReturnedNs"]) <= child["completedNs"], "QUERY_RETURN_TIME")
    minimum = native.history.chain_minimum(native.history.snapshot(fence), context["sourceReturnedNs"],
        start, row, birth, child, service, ack)
    checked = fence.now(minimum=minimum)
    return match, {"phaseSha256": {name: O.digest(data) for name, data in records.items()},
        "childSha256": O.digest(child_raw), "querySessionSha256": O.digest(session), "originalsSha256": child["originalsSha256"],
        "checkedNs": checked}


def prepare_originals(cancelled):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    first = O.clocks.validate_reading(O.clocks.observe())
    fence = O.Fence(O.prelude(first), minimum=first.nanoseconds, cancelled=lambda: native.cancellation(cancelled))
    owner = native.Owner(fence.deadline(O.PRELUDE_SECONDS, final=True), fence)
    owner.initial_sources = {}
    private = result_raw = None
    try:
        require(not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "PRIOR_UNKNOWN")
        observed, path, event = host_context(int(time.time()))
        require(observed["role"] == first.clock.role, "ACTUAL_NATIVE_ROLE")
        inherited = Q._inherited_context()
        native.child_environment(path)  # Reject ambient execution overrides before allocation.
        private = owner.new(path)
        owner.write(private, "prelude.json", fence.raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = source_queries(owner, fence, observed, path / "source-before")
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": native.INITIAL_CONTEXT_SCOPE,
            "prelude": O.parse(fence.raw), "observed": observed, "eventSha256": O.digest(event), "root": str(ROOT),
            "session": str(path), "job": uuid.uuid4().hex, "inheritedContext": inherited,
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": O.parse(before.raw)["returnedNs"],
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = native.phase(owner, private, context_raw, token, fence)
        token = None
        match, chain = read_phase(owner, private, context_raw, before, phase, fence)
        after = source_queries(owner, fence, observed, path / "source-after")
        require(source_readback(owner, path / "source-after", after) == dict(before.records), "SOURCE_CHANGED_AFTER_CHILD")
        match, chain = read_phase(owner, private, context_raw, before, phase, fence)
        result_raw = owner.write(private, "initial-result.json", {"schema": 1, "scope": RESULT_SCOPE,
            "contextSha256": O.digest(context_raw), "sourceBeforeSha256": O.digest(before.raw), "sourceAfterSha256": O.digest(after.raw),
            "matchSha256": O.digest(match.record), "originalChain": chain, "retainedNs": fence.now(),
            "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "workerAdmission": "NOT_PERFORMED",
            "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False})
    except BaseException as error:
        owner.error("initial-originals", error)
        if private is not None and not owner.unknown:
            try:
                owner.write(private, "initial-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("initial-failure-retention", secondary)
    finally:
        token = None
        try:
            owner.close()
        except BaseException as error:
            owner.error("initial-owner-close", error)
    if owner.original is not None:
        raise owner.original
    require(result_raw is not None and not owner.unknown, "MISSING_ORIGINALS")
    fence.now(final=True)
    native.cancellation(cancelled)
    return native.public_result(OUTPUT_SCOPE, "initialOriginalsSha256", result_raw), fence, fence.final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("prepare-originals")
    child = commands.add_parser("_service")
    child.add_argument("--context-sha256", required=True)
    child.add_argument("--minimum-ns", required=True)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode, "ISOLATED_INTERPRETER")
        if args.operation == "prepare-originals":
            native.guarded(prepare_originals)
        else:
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "LAUNCH_MINIMUM")
            minimum = O.integer(int(args.minimum_ns))
            native.initial_command(args.context_sha256, minimum)
            native.guarded(lambda cancelled: service_child(args.context_sha256, minimum, cancelled))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_ORIGINALS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
