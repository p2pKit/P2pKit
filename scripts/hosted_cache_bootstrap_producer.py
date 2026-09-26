"""Dormant bootstrap request and original canonical-receipt consistency checks.

Pure declarations only: no launcher, file/clock reader, budget, native owner,
provider or workflow. A caller must retain the real originals and observed exit;
mutually consistent supplied records cannot authenticate themselves. A successful
canonical report is NOT enclosing-owner retirement, export/save authority,
dependency population or ordinary test acceptance. Failed originals still need
custody even when this helper refuses to produce a positive observation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
from pathlib import PurePosixPath, PureWindowsPath
import re
import subprocess

import hosted_cache_bootstrap_identity as bootstrap


LIMIT = 4 * 1024 * 1024
REQUEST_SCOPE = "CACHE_BOOTSTRAP_PRODUCER_REQUEST_V1"
OBSERVATION_SCOPE = "CACHE_BOOTSTRAP_CANONICAL_OBSERVATION_V1"
PURPOSE = "cache-bootstrap-configuration"
# An independent closed counterpart of the immutable canonical supplier's
# gradle_arguments(COMMAND), not arbitrary caller flags or ordinary FULL tasks.
JVM_ARGUMENTS = "-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8"
ENFORCED = ("--no-daemon", "--dependency-verification", "strict", "--rerun-tasks",
            "--no-build-cache", "--no-configuration-cache", "--no-parallel", "--max-workers=2",
            "-Pkotlin.compiler.execution.strategy=in-process", "-Dorg.gradle.jvmargs=" + JVM_ARGUMENTS)
SEMANTICS = "logical-command; exact platform launch is ownership.launches[productLaunchIndex]"
CONTEXT_FIELDS = {"schema", "root", "expectedCommit", "tree", "source", "host", "gradleHome",
                  "createdUtc", "id", "gradlePropertiesSha256", "javaHomes", "preexistingOutputPaths"}
START_FIELDS = {"schema", "id", "purpose", "kind", "requestedArgv", "cwd", "wrapper", "host", "jobId",
                "gradleHome", "startedUtc", "ancestorInvocationIds", "controllerPid", "sourceBefore",
                "sourceAfter", "productExitCode", "stopExitCode", "finalExitCode", "sourceUnchanged",
                "ownedSurvivors", "errors", "evidenceDirectory"}
TERMINAL_FIELDS = START_FIELDS | {"executedArgv", "executedArgvSemantics", "productLaunchIndex",
    "productStartedUtc", "productPid", "productEndedUtc", "stopArgv", "stopLaunchIndex", "stopStartedUtc",
    "stopEndedUtc", "ownership", "reports", "endedUtc", "durationSeconds"}
BACKENDS = {"linux-x64": "linux-proc-pidfd", "windows-x64": "windows-job-list-suspended",
            "macos-arm64": "darwin-libproc-audit-token", "macos-x64": "darwin-libproc-audit-token"}


class ProducerError(ValueError):
    """Fixed public-safe reason; never echo private paths, argv or receipts."""


def require(value, reason):
    if not value:
        raise ProducerError(reason)


def parse(raw):
    try:
        return bootstrap.ordinary.parse(raw, LIMIT)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ProducerError("BOOTSTRAP_PRODUCER_RECORD") from None


def encoded(value):
    try:
        raw = bootstrap.ordinary.encoded(value)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ProducerError("BOOTSTRAP_PRODUCER_RECORD") from None
    require(len(raw) <= LIMIT, "BOOTSTRAP_PRODUCER_RECORD")
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value), "BOOTSTRAP_PRODUCER_INVOCATION")
    return value


def _path(value, role):
    require(type(value) is str and 0 < len(value) <= 4096 and
            not any(ord(char) < 32 or ord(char) == 127 for char in value), "BOOTSTRAP_PRODUCER_PATH")
    path = PureWindowsPath(value) if role == "windows-x64" else PurePosixPath(value)
    require(path.is_absolute() and ".." not in path.parts and str(path) == value and len(path.parts) > 1,
            "BOOTSTRAP_PRODUCER_PATH")
    if role == "windows-x64":
        require(re.fullmatch(r"[A-Za-z]:", path.drive), "BOOTSTRAP_PRODUCER_PATH")
    return path


def _utc(value):
    require(type(value) is str and len(value) <= 40, "BOOTSTRAP_PRODUCER_UTC")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(stamp.tzinfo == timezone.utc, "BOOTSTRAP_PRODUCER_UTC")
    except ValueError:
        raise ProducerError("BOOTSTRAP_PRODUCER_UTC") from None
    # Wall timestamps are labels only. Never derive a budget or order RAW phases
    # from them: the original shared-clock/service envelope is still missing.


def make_request(admitted_raw, canonical_raw, *, invocation, ancestor_invocations):
    """Bind a proposed canonical invocation, without permission to launch it."""
    try:
        cohort = bootstrap.cache_cohort(admitted_raw)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ProducerError("BOOTSTRAP_PRODUCER_ADMISSION") from None
    require(cohort is not None, "BOOTSTRAP_PRODUCER_ADMISSION")
    admitted, canonical = parse(admitted_raw), parse(canonical_raw)
    profile, role = cohort
    require(set(canonical) == CONTEXT_FIELDS and type(canonical["schema"]) is int and canonical["schema"] == 1,
            "BOOTSTRAP_PRODUCER_CONTEXT")
    source = {**admitted["source"], "status": "", "diffSha256": digest(b"")}
    require(canonical["source"] == source and canonical["expectedCommit"] == source["commit"] and
            canonical["tree"] == source["tree"] and canonical["host"] == role,
            "BOOTSTRAP_PRODUCER_SOURCE_OR_HOST")
    root, home = (_path(canonical[name], role) for name in ("root", "gradleHome"))
    state = home.parent
    require(home.name == "gradle-home" and state != root and state not in root.parents and root not in state.parents,
            "BOOTSTRAP_PRODUCER_HOME")
    _uuid(canonical["id"])
    _uuid(invocation)
    require(type(ancestor_invocations) in (tuple, list) and 1 <= len(ancestor_invocations) <= 31 and
            all(_uuid(value) for value in ancestor_invocations) and
            len(set(ancestor_invocations)) == len(ancestor_invocations) and invocation not in ancestor_invocations,
            "BOOTSTRAP_PRODUCER_ANCESTORS")
    require(type(canonical["gradlePropertiesSha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", canonical["gradlePropertiesSha256"]), "BOOTSTRAP_PRODUCER_PROPERTIES")
    for key in ("javaHomes", "preexistingOutputPaths"):
        require(type(canonical[key]) is list and len(canonical[key]) <= 20000 and
                all(type(value) is str and _path(value, role) for value in canonical[key]),
                "BOOTSTRAP_PRODUCER_CONTEXT_PATHS")
    _utc(canonical["createdUtc"])
    wrapper = str(root / ("gradlew.bat" if role == "windows-x64" else "gradlew"))
    return parse(encoded({
        "schema": 1, "scope": REQUEST_SCOPE, "profile": bootstrap.PROFILE, "selection": admitted["selection"],
        "cacheCohort": {"profile": profile, "role": role}, "source": admitted["source"], "github": admitted["github"],
        "admissionSha256": digest(admitted_raw), "canonicalContextSha256": digest(canonical_raw),
        "id": invocation, "jobId": canonical["id"], "ancestorInvocationIds": list(ancestor_invocations),
        "purpose": PURPOSE, "kind": "gradle", "cwd": str(root), "wrapper": wrapper, "gradleHome": str(home),
        "evidenceDirectory": str(state / "evidence" / invocation), "host": role,
        "requestedArgv": list(bootstrap.COMMAND), "executedArgv": [wrapper, *bootstrap.COMMAND, *ENFORCED],
        "stopArgv": [wrapper, "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
                     "-Dorg.gradle.jvmargs=" + JVM_ARGUMENTS],
        "producerScope": bootstrap.PRODUCER_SCOPE, "testAcceptance": "NOT_PERFORMED"}))


def _integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= (1 << 32) - 1, "BOOTSTRAP_PRODUCER_INTEGER")
    return value


def _batch_line(cmd, argv):
    # Counterpart of audit_processes.batch_command_line; no executable lookup.
    forbidden = re.compile(r'[\x00-\x1f"%!&|<>^]')
    require(not any(char in cmd for char in "()") and not any(forbidden.search(arg) for arg in [cmd, *argv]),
            "BOOTSTRAP_PRODUCER_BATCH_GRAMMAR")
    quoted = ['"' + arg + "\\" * (len(arg) - len(arg.rstrip("\\"))) + '"' for arg in argv]
    return subprocess.list2cmdline([cmd]) + ' /d /s /v:off /c "' + " ".join(quoted) + '"'


def _launch(value, argv, request):
    require(type(value) is dict, "BOOTSTRAP_PRODUCER_LAUNCH")
    common = {"api", "requestedArgv", "cwd", "created", "resolvedArgv", "pid"}
    extra = ({"resumed", "applicationName", "commandLine", "batch", "jobAssignedBeforeResume", "resourceCleanup"}
             if request["host"] == "windows-x64" else {"shell", "executable"})
    require(set(value) == common | extra and value["requestedArgv"] == argv == value["resolvedArgv"] and
            value["cwd"] == request["cwd"] and value["created"] is True, "BOOTSTRAP_PRODUCER_LAUNCH")
    _integer(value["pid"], 1)
    if request["host"] != "windows-x64":
        require(value["api"] == "subprocess.Popen" and value["shell"] is False and value["executable"] == argv[0],
                "BOOTSTRAP_PRODUCER_POSIX_LAUNCH")
        return None
    cmd = _path(value["applicationName"], "windows-x64")
    require(cmd.name.lower() == "cmd.exe" and cmd.parent.name.lower() == "system32" and
            value["api"] == "CreateProcessW" and value["batch"] is True and value["resumed"] is True and
            value["jobAssignedBeforeResume"] is True and value["commandLine"] == _batch_line(str(cmd), argv),
            "BOOTSTRAP_PRODUCER_WINDOWS_LAUNCH")
    cleanup = value["resourceCleanup"]
    # Canonical executor uses the unchanged pipe path: two adopted readers,
    # two write handles, NUL stdin, startup attributes and the primary thread.
    names = {"startup-attributes", "launch-handle-1", "launch-handle-3", "launch-handle-4", "primary-thread"}
    require(type(cleanup) is list and len(cleanup) == len(names) and all(type(row) is dict and
            set(row) == {"phase", "resource", "status"} and row["phase"] == "launch-temporary" and
            row["status"] == "RETIRED" and type(row["resource"]) is str for row in cleanup) and
            {row["resource"] for row in cleanup} == names, "BOOTSTRAP_PRODUCER_WINDOWS_TEMPORARIES")
    # This only cross-checks the declared path/framing. Its real System32 identity
    # must come from the canonical native supplier, never from this JSON record.
    return str(cmd)


def _ownership(value, request, receipt):
    require(type(value) is dict and value.get("backend") == BACKENDS[request["host"]] and
            value.get("job") == request["jobId"] and value.get("invocation") == request["id"] and
            value.get("discoveryErrors") == [] and type(value.get("startedIdentities")) is list,
            "BOOTSTRAP_PRODUCER_NATIVE_BINDING")
    windows = request["host"] == "windows-x64"
    scope = "kernel-job-no-breakaway-kill-on-close" if windows else "controlled-marker-inheriting-descendants"
    require(value.get("scope") == scope and type(value.get("launches")) is list and len(value["launches"]) == 2,
            "BOOTSTRAP_PRODUCER_NATIVE_BINDING")
    if not windows:
        require(type(value.get("discoveryReconciliations")) is list, "BOOTSTRAP_PRODUCER_NATIVE_BINDING")
    if request["host"].startswith("macos-"):
        # Clearing discoveryErrors also resolves each original pending record.
        # Earlier observationReconciliations may honestly retain the exhausted
        # access attempt; only these terminal dispositions must be resolved.
        require(all(type(row) is dict and row.get("outcome") in
                ("lifetime-ended", "nonrunning", "replaced", "unmarked", "owned")
                for row in value["discoveryReconciliations"]), "BOOTSTRAP_PRODUCER_DARWIN_DISCOVERY")
        drains = value.get("drainReconciliations")
        require(type(value.get("observationReconciliations")) is list and type(drains) is list and drains and
                all(type(row) is dict and row.get("outcome") == "retired" and "error" not in row for row in drains),
                "BOOTSTRAP_PRODUCER_DARWIN_DRAIN")
        for drain in drains:
            # A later quiet drain cannot reconcile an earlier drain's pending
            # signals. Native drain() cannot report retired while any remain.
            signals = drain.get("signalReconciliations")
            require(type(signals) is list and all(type(row) is dict and row.get("outcome") in
                    ("absent", "nonrunning", "replaced", "signal-succeeded") for row in signals),
                    "BOOTSTRAP_PRODUCER_DARWIN_SIGNALS")
    product, stop = value["launches"]
    first = _launch(product, request["executedArgv"], request)
    second = _launch(stop, request["stopArgv"], request)
    require(first == second and _integer(receipt["productLaunchIndex"]) == 0 and
            _integer(receipt["stopLaunchIndex"]) == 1 and _integer(receipt["productPid"], 1) == product["pid"],
            "BOOTSTRAP_PRODUCER_LAUNCH_BINDING")


def observe_canonical(request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw, *, original_exit_code):
    """Inspect supplied original reports, NOT enclosing-owner/clock retirement."""
    request, start, receipt = map(parse, (request_raw, start_raw, receipt_raw))
    expected = make_request(admitted_raw, canonical_raw, invocation=request.get("id"),
                            ancestor_invocations=request.get("ancestorInvocationIds"))
    require(request_raw == encoded(expected), "BOOTSTRAP_PRODUCER_REQUEST_CHANGED")
    require(type(original_exit_code) is int and original_exit_code == 0, "BOOTSTRAP_PRODUCER_ORIGINAL_EXIT")
    require(set(start) == START_FIELDS and set(receipt) == TERMINAL_FIELDS and
            type(start["schema"]) is int and start["schema"] == 1 and
            type(receipt["schema"]) is int and receipt["schema"] == 1, "BOOTSTRAP_PRODUCER_ORIGINAL_SHAPE")
    for key in ("id", "purpose", "kind", "requestedArgv", "cwd", "wrapper", "host", "jobId", "gradleHome",
                "ancestorInvocationIds", "evidenceDirectory"):
        require(start[key] == receipt[key] == expected[key], "BOOTSTRAP_PRODUCER_START_OR_IDENTITY_CHANGED")
    require(_integer(start["controllerPid"], 1) == _integer(receipt["controllerPid"], 1) and
            start["startedUtc"] == receipt["startedUtc"], "BOOTSTRAP_PRODUCER_START_OR_IDENTITY_CHANGED")
    require(all(start[key] is None for key in ("sourceBefore", "sourceAfter", "productExitCode", "stopExitCode")) and
            _integer(start["finalExitCode"]) == 125 and start["sourceUnchanged"] is False and
            start["ownedSurvivors"] == [] and start["errors"] == [], "BOOTSTRAP_PRODUCER_START_NOT_ORIGINAL")
    source = parse(canonical_raw)["source"]
    require(receipt["sourceBefore"] == receipt["sourceAfter"] == source and receipt["sourceUnchanged"] is True and
            all(_integer(receipt[key]) == 0 for key in ("productExitCode", "stopExitCode", "finalExitCode")) and
            receipt["errors"] == [] and receipt["ownedSurvivors"] == [], "BOOTSTRAP_PRODUCER_CANONICAL_FAILED")
    require(receipt["executedArgv"] == expected["executedArgv"] and receipt["stopArgv"] == expected["stopArgv"] and
            receipt["executedArgvSemantics"] == SEMANTICS, "BOOTSTRAP_PRODUCER_EXECUTED_COMMAND_CHANGED")
    for key in ("startedUtc", "productStartedUtc", "productEndedUtc", "stopStartedUtc", "stopEndedUtc", "endedUtc"):
        _utc(receipt[key])
    duration = receipt["durationSeconds"]
    require(type(duration) in (int, float) and 0 <= duration <= (1 << 64) - 1 and math.isfinite(duration) and
            type(receipt["reports"]) is list, "BOOTSTRAP_PRODUCER_TERMINAL_METADATA")
    _ownership(receipt["ownership"], expected, receipt)
    return {"schema": 1, "scope": OBSERVATION_SCOPE, "requestSha256": digest(request_raw),
            "admissionSha256": digest(admitted_raw), "canonicalContextSha256": digest(canonical_raw),
            "startSha256": digest(start_raw), "receiptSha256": digest(receipt_raw), "originalExitCode": 0,
            "status": "CANONICAL_CONFIGURATION_REPORTED_SUCCESS", "producerScope": bootstrap.PRODUCER_SCOPE,
            "testAcceptance": "NOT_PERFORMED", "enclosingNativeRetirement": "NOT_OBSERVED_HERE",
            "budgetAcceptance": "NOT_ADMITTED_HERE", "exportSaveAuthority": False}


def validate_observation(value, request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw, *, original_exit_code):
    expected = observe_canonical(request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw,
                                 original_exit_code=original_exit_code)
    require(type(value) is dict and encoded(value) == encoded(expected), "BOOTSTRAP_PRODUCER_OBSERVATION_CHANGED")
    return value
