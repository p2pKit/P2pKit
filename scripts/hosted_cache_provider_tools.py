"""Bounded native provider-tool observation and its historical DATA codec.

The fixed worker owns this observer, under its original RAW/LOCAL window. No
controller/current/HTTP import, service credential, arbitrary command callback,
installation or tool download exists here. A decoded record is not a live owner
and cannot authenticate a runner or qualify a provider by itself.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import sys
import threading
import time
import uuid

import audit_processes as processes
import hosted_dependency_cache as cache
import hosted_dependency_seed_files as public_files
import hosted_job_clock as clocks
import hosted_test_query as private_files


MAX_BYTES = 262144
FILE_BYTES, TOTAL_BYTES, BLOCK = 256 * 1024 * 1024, 512 * 1024 * 1024, 1024 * 1024
OUTPUT_BYTES, NATIVE_BYTES = 4096, 16384
SCOPE = "P2PKIT_PROVIDER_TOOL_OBSERVATIONS_V1"
OBSERVATION = "CREDENTIAL_FREE_PREFLIGHT_NOT_SUPPLIER_CHILD_OBSERVATION"
TRIM = b"\x09\x0a\x0b\x0c\x0d\x20"
TOOLS = ("python", "node", "zstd", "tar", "compressor")
PROBE_RESOURCES = ("directory", "stdoutWriter", "stderrWriter", "scope", "stdoutReader", "stderrReader")
MARKERS = (processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV, processes.STATE_ENV, "GRADLE_USER_HOME")
SCRIPTS = Path(__file__).absolute().parent
QUARANTINE = []


class ProviderToolsError(RuntimeError):
    """Only fixed safe reason codes; originals and environment are private."""


def require(value, reason):
    if not value:
        raise ProviderToolsError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _record(raw, maximum, *, newline=True):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "PROVIDER_TOOLS_RECORD_BOUND")
    def unique(pairs):
        result = {}
        for name, value in pairs:
            require(name not in result, "PROVIDER_TOOLS_DUPLICATE")
            result[name] = value
        return result
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "PROVIDER_TOOLS_JSON"))
    except (ValueError, UnicodeError, RecursionError):
        raise ProviderToolsError("PROVIDER_TOOLS_JSON") from None
    require(type(value) is dict and canonical(value) + (b"\n" if newline else b"") == raw,
            "PROVIDER_TOOLS_CANONICAL")
    return value


def _keys(value, expected):
    require(type(value) is dict and set(value) == set(expected.split()), "PROVIDER_TOOLS_FIELDS")


def _integer(value, minimum=0, maximum=(1 << 64) - 1):
    require(type(value) is int and minimum <= value <= maximum, "PROVIDER_TOOLS_INTEGER")
    return value


def _ns(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value), "PROVIDER_TOOLS_RAW")
    return _integer(int(value))


def _hex(value, size=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", value), "PROVIDER_TOOLS_HASH")
    return value


def _path(value, role):
    require(type(value) is str and 0 < len(value) <= 4096 and
            all(32 <= ord(char) < 127 for char in value), "PROVIDER_TOOLS_PATH")
    kind = PureWindowsPath if role == "windows-x64" else PurePosixPath
    path = kind(value)
    require(path.is_absolute() and str(path) == value and ".." not in path.parts and
            (role != "windows-x64" or re.fullmatch(r"[A-Za-z]:", path.drive)), "PROVIDER_TOOLS_PATH")
    return path


def _raw(text, maximum):
    require(type(text) is str and len(text) <= 4 * ((maximum + 2) // 3), "PROVIDER_TOOLS_RAW_BOUND")
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, UnicodeError):
        raise ProviderToolsError("PROVIDER_TOOLS_BASE64") from None
    require(len(raw) <= maximum and base64.b64encode(raw).decode("ascii") == text, "PROVIDER_TOOLS_BASE64")
    return raw


def compression_from_streams(stdout, stderr):
    """Exact pin's two-stream getVersion trim-emptiness, NOT its guessed order."""
    require(type(stdout) is bytes and type(stderr) is bytes and
            len(stdout) <= OUTPUT_BYTES and len(stderr) <= OUTPUT_BYTES and stdout.isascii() and stderr.isascii(),
            "PROVIDER_TOOLS_VERSION_ASCII")
    return "zstd-without-long" if any(byte not in TRIM for raw in (stdout, stderr) for byte in raw) else "gzip"


def windows_gnu_tar(stdout, stderr):
    """One actual nonempty stream; never invent cross-stream listener interleave."""
    compression_from_streams(stdout, stderr)  # Same ASCII/byte bounds, not the selector.
    require(bool(stdout) != bool(stderr), "PROVIDER_TOOLS_WINDOWS_TAR_AMBIGUOUS")
    return b"gnu tar" in (stdout or stderr).strip(TRIM).lower()


def _native(value, role, *, directory=False, symlink=False):
    if role == "windows-x64":
        _keys(value, "identity is_directory size links attributes creation_100ns modified_100ns change_100ns owner_sid protected_dacl")
        require(not symlink and type(value["identity"]) is list and len(value["identity"]) == 2,
                "PROVIDER_TOOLS_NATIVE_IDENTITY")
        _integer(value["identity"][0]); _hex(value["identity"][1], 32)
        for name in ("size", "links", "attributes", "creation_100ns", "modified_100ns", "change_100ns"):
            _integer(value[name])
        require(value["owner_sid"] is None and value["protected_dacl"] is None and
                not value["attributes"] & (0x400 | 0x40) and bool(value["attributes"] & 0x10) == directory,
                "PROVIDER_TOOLS_NATIVE_KIND")
    else:
        _keys(value, "identity is_directory size mode uid links mtime_ns ctime_ns")
        require(type(value["identity"]) is list and len(value["identity"]) == 2, "PROVIDER_TOOLS_NATIVE_IDENTITY")
        _integer(value["identity"][0]); _integer(value["identity"][1], 1)
        for name in ("size", "mode", "uid", "links", "mtime_ns", "ctime_ns"):
            _integer(value[name])
        kind = stat.S_ISLNK if symlink else stat.S_ISDIR if directory else stat.S_ISREG
        require(kind(value["mode"]) and (symlink or not value["mode"] & 0o022), "PROVIDER_TOOLS_NATIVE_KIND")
    require(type(value["is_directory"]) is bool and value["is_directory"] == directory and
            (directory or value["links"] == 1), "PROVIDER_TOOLS_NATIVE_KIND")
    return tuple(value["identity"])


def _public_environment(frame):
    result = {"PATH": frame["toolPath"], "GITHUB_WORKSPACE": str(SCRIPTS.parent), "LANG": "C", "LC_ALL": "C"}
    if frame["role"] == "windows-x64":
        result.update(SYSTEMROOT=frame["systemRoot"], USERPROFILE=frame["home"], TEMP=frame["home"], TMP=frame["home"], PATHEXT=".EXE")
    else:
        result.update(HOME=frame["home"], TMPDIR=frame["home"])
    return result


def _context(request, bindings):
    frame = _record(request, 16384, newline=False)
    _keys(frame, "schema role frequency issuedNs hardEndNs workerCutoffNs phase job outerId innerId directory directoryIdentity "
                 "home homeIdentity captureIdentity node toolPath systemRoot plan prefix")
    require(type(frame["schema"]) is int and frame["schema"] == 1 and frame["role"] in clocks.DOMAINS,
            "PROVIDER_TOOLS_REQUEST")
    role = frame["role"]
    identity = clocks.validate_identity(clocks.ClockIdentity(role, clocks.DOMAINS[role], frame["frequency"]))
    issued, end, cut = (_ns(frame[key]) for key in ("issuedNs", "hardEndNs", "workerCutoffNs"))
    require(issued + 45 * clocks.NS < cut < end <= issued + 180 * clocks.NS,
            "PROVIDER_TOOLS_WINDOW")
    for name in ("job", "outerId", "innerId"):
        _hex(frame[name], 32)
    require(frame["outerId"] != frame["innerId"], "PROVIDER_TOOLS_INVOCATION_ALIAS")
    for name in ("node", "directory", "home"):
        _path(frame[name], role)
    roots = []
    for name in ("directoryIdentity", "homeIdentity", "captureIdentity"):
        row = frame[name]
        require(type(row) is list and len(row) == 2, "PROVIDER_TOOLS_DIRECTORY_IDENTITY")
        _integer(row[0])
        _hex(row[1], 32) if role == "windows-x64" else _integer(row[1], 1)
        roots.append(tuple(row))
    require(len(set(roots)) == 3 and frame["directory"] != frame["home"], "PROVIDER_TOOLS_DIRECTORY_ALIAS")
    prefix = frame["prefix"]
    require(type(prefix) is list and prefix and all(type(row) is list and len(row) == 4 for row in prefix),
            "PROVIDER_TOOLS_OWNERSHIP_PREFIX")
    domains = [dict(zip(("id", "job", "state", "home"), row)) for row in prefix]
    require(processes.ownership_domains(":".join(row[0] for row in prefix), canonical(domains).decode("ascii")) == domains and
            prefix[-1] == [frame["outerId"], frame["job"], frame["directory"], frame["home"]] and
            frame["innerId"] not in [row[0] for row in prefix], "PROVIDER_TOOLS_OWNERSHIP_PREFIX")
    require(type(frame["toolPath"]) is str, "PROVIDER_TOOLS_PATH")
    paths = frame["toolPath"].split(";" if role == "windows-x64" else ":")
    require(0 < len(paths) <= 64, "PROVIDER_TOOLS_PATH_BOUND")
    for path in paths:
        _path(path, role)
    if role == "windows-x64":
        _path(frame["systemRoot"], role)
    else:
        require(frame["systemRoot"] is None, "PROVIDER_TOOLS_SYSTEMROOT")
    contract = cache._native_provider_contract(frame["plan"], frame["phase"])
    require(frame["plan"]["role"] == role and type(bindings) is dict and 1 <= len(bindings) <= 32 and
            {"hosted_cache_provider_tools", "hosted_cache_provider_worker", "hosted_cache_provider_launch"} <= set(bindings),
            "PROVIDER_TOOLS_SOURCE_MAP")
    for name, value in bindings.items():
        require(type(name) is str and re.fullmatch(r"audit_processes|hosted_[a-z0-9_]+", name), "PROVIDER_TOOLS_SOURCE_MAP")
        _hex(value)
    context = {"requestSha256": hashlib.sha256(request).hexdigest(),
        "sourceMapSha256": hashlib.sha256(canonical(bindings)).hexdigest(),
        "providerBundleSha256": contract["bundle"]["sha256"],
        **{name: frame[name] for name in ("role", "phase", "job", "outerId", "innerId", "issuedNs", "hardEndNs", "workerCutoffNs")},
        "clock": {"role": role, "domain": identity.domain, "frequency": identity.ticks_per_second},
        "literalPath": frame["plan"]["path"], "key": frame["plan"]["key"], "observation": OBSERVATION}
    return frame, context


def _command(purpose, executable, compression):
    if purpose in ("NODE_VERSION", "TAR_VERSION") or (purpose == "COMPRESSOR_VERSION" and compression == "gzip"):
        return [executable, "--version"]
    require(purpose in ("ZSTD_VERSION", "COMPRESSOR_VERSION"), "PROVIDER_TOOLS_PROBE_PURPOSE")
    return [executable, "--quiet", "--version"]


def _native_process(value, role):
    if role == "windows-x64":
        require(type(value) is dict and set(value) in ({"pid", "creationFileTime"},
                {"pid", "creationFileTime", "jobAssignedBeforeResume"}), "PROVIDER_TOOLS_PROCESS_IDENTITY")
        _integer(value["creationFileTime"], 1)
        require("jobAssignedBeforeResume" not in value or value["jobAssignedBeforeResume"] is True,
                "PROVIDER_TOOLS_PROCESS_IDENTITY")
    else:
        names = ("pid uid parentPid group session startTicks live" if role == "linux-x64" else
                 "pid uid parentPid group uniqueId parentUniqueId pidVersion startSeconds startMicroseconds realUid status flags live")
        _keys(value, names)
        for key in value:
            if key == "live":
                require(type(value[key]) is bool, "PROVIDER_TOOLS_PROCESS_IDENTITY")
            else:
                _integer(value[key])
    _integer(value["pid"], 1)


def _retirement(raw, frame, invocation, argv, *, maximum=NATIVE_BYTES):
    """Exact retained native description, never a new retirement observation.

    Probe callers keep their 16KiB ceiling. The worker and outer original-file
    codecs use their existing 2MiB ceiling for the supplier/supervisor records.
    """
    require(maximum in (NATIVE_BYTES, 2 * 1024 * 1024), "PROVIDER_TOOLS_NATIVE_BOUND")
    value = _record(raw, maximum)
    role = frame["role"]
    windows = role == "windows-x64"
    extra = "" if windows else " discoveryReconciliations" + (
        " observationReconciliations drainReconciliations" if role.startswith("macos-") else "")
    _keys(value, "backend scope invocation job launches startedIdentities discoveryErrors" + extra)
    require(value["backend"] == ("windows-job-list-suspended" if windows else
        "linux-proc-pidfd" if role == "linux-x64" else "darwin-libproc-audit-token") and
        value["scope"] == ("kernel-job-no-breakaway-kill-on-close" if windows else "controlled-marker-inheriting-descendants") and
        value["invocation"] == invocation and value["job"] == frame["job"] and value["discoveryErrors"] == [] and
        type(value["launches"]) is list and len(value["launches"]) == 1, "PROVIDER_TOOLS_NATIVE_RETIREMENT")
    launch = value["launches"][0]
    common = "api requestedArgv resolvedArgv cwd created pid outputMode"
    _keys(launch, common + (" resumed applicationName commandLine batch jobAssignedBeforeResume resourceCleanup" if windows else
                           " shell executable"))
    require(launch["requestedArgv"] == argv == launch["resolvedArgv"] and launch["cwd"] == str(SCRIPTS.parent) and
            launch["created"] is True and launch["api"] == ("CreateProcessW" if windows else "subprocess.Popen") and
            launch["outputMode"] == ("caller-owned-native-files" if windows else "caller-owned-files"),
            "PROVIDER_TOOLS_NATIVE_LAUNCH")
    _integer(launch["pid"], 1)
    if windows:
        require(launch["resumed"] is True and launch["batch"] is False and launch["jobAssignedBeforeResume"] is True and
                launch["applicationName"] == argv[0] and launch["commandLine"] == subprocess.list2cmdline(argv) and
                type(launch["resourceCleanup"]) is list and 1 <= len(launch["resourceCleanup"]) <= 16,
                "PROVIDER_TOOLS_NATIVE_FRAMING")
        for row in launch["resourceCleanup"]:
            _keys(row, "phase resource status")
            require(row["phase"] == "launch-temporary" and row["status"] == "RETIRED" and
                    type(row["resource"]) is str and re.fullmatch(r"startup-attributes|launch-handle-[0-9]+|primary-thread", row["resource"]),
                    "PROVIDER_TOOLS_NATIVE_CLOSE")
    else:
        require(launch["shell"] is False and launch["executable"] == argv[0], "PROVIDER_TOOLS_NATIVE_FRAMING")
        # A native observer refuses unresolved reconciliation. The maintained
        # process backend still owns its reconciliation algorithms/deadlines;
        # these bounded supplied rows never prove a fresh process census.
        require(type(value["discoveryReconciliations"]) is list, "PROVIDER_TOOLS_NATIVE_RECONCILIATION")
        for row in value["discoveryReconciliations"]:
            _keys(row, "identity message firstFailure lastFailure failures outcome lastIdentity")
            _native_process(row["identity"], role)
            _integer(row["failures"], 1, 1024)
            require(type(row["message"]) is str and len(row["message"]) <= 2048 and
                    all(type(row[key]) is str and len(row[key]) <= 2048 for key in ("firstFailure", "lastFailure")) and
                    row["outcome"] in ("lifetime-ended", "nonrunning", "replaced", "unmarked", "owned"),
                    "PROVIDER_TOOLS_NATIVE_RECONCILIATION")
            if row["lastIdentity"] is not None:
                _native_process(row["lastIdentity"], role)
        if role.startswith("macos-"):
            for key in ("observationReconciliations", "drainReconciliations"):
                require(type(value[key]) is list, "PROVIDER_TOOLS_NATIVE_RECONCILIATION")
            for row in value["observationReconciliations"]:
                _keys(row, "operation identity lastIdentity attempts firstFailure lastFailure outcome")
                _native_process(row["identity"], role)
                if row["lastIdentity"] is not None:
                    _native_process(row["lastIdentity"], role)
                _integer(row["attempts"], 0, 26)
                require(row["operation"] in ("environment", "task token", "identity") and
                        row["outcome"] in ("recovered", "absent", "nonrunning", "replaced") and
                        all(type(row[key]) is str and len(row[key]) <= 2048 for key in ("firstFailure", "lastFailure")),
                        "PROVIDER_TOOLS_NATIVE_RECONCILIATION")
            # Drain reconciliation has no synthetic success substitution. Its
            # closed exact codec is below; no arbitrary dictionary is admitted.
            for row in value["drainReconciliations"]:
                _drain_reconciliation(row, role)
    require(type(value["startedIdentities"]) is list and len(value["startedIdentities"]) <= 1024,
            "PROVIDER_TOOLS_NATIVE_IDENTITIES")
    for row in value["startedIdentities"]:
        _native_process(row, role)
    require([row["pid"] for row in value["startedIdentities"]] == sorted(row["pid"] for row in value["startedIdentities"]),
            "PROVIDER_TOOLS_NATIVE_IDENTITIES")
    if windows:
        require(any(row["pid"] == launch["pid"] and row.get("jobAssignedBeforeResume") is True
                    for row in value["startedIdentities"]), "PROVIDER_TOOLS_ORIGINAL_JOB_ASSIGNMENT")


def _drain_reconciliation(row, role):
    _keys(row, "startedMonotonic graceSeconds killWaitSeconds phases signalReconciliations outcome "
               "absoluteDeadlineMonotonic finishedMonotonic")
    for name in ("startedMonotonic", "graceSeconds", "killWaitSeconds", "absoluteDeadlineMonotonic", "finishedMonotonic"):
        require(type(row[name]) in (int, float) and math.isfinite(row[name]) and row[name] >= 0,
                "PROVIDER_TOOLS_NATIVE_LOCAL_TIME")
    require(row["outcome"] == "retired" and 0 < row["graceSeconds"] <= 5 and 0 <= row["killWaitSeconds"] <= 5 and
            row["startedMonotonic"] <= row["finishedMonotonic"] < row["absoluteDeadlineMonotonic"] and
            type(row["phases"]) is list and 1 <= len(row["phases"]) <= 2 and
            type(row["signalReconciliations"]) is list and len(row["signalReconciliations"]) <= 1024,
            "PROVIDER_TOOLS_NATIVE_DRAIN")
    previous = row["startedMonotonic"]
    for index, phase in enumerate(row["phases"]):
        require(type(phase) is dict and set(phase) in ({"signal", "deadlineMonotonic"},
                {"signal", "deadlineMonotonic", "outcome"}) and type(phase["signal"]) is int and
                phase["signal"] == (15 if index == 0 else 9) and
                type(phase["deadlineMonotonic"]) in (int, float) and math.isfinite(phase["deadlineMonotonic"]) and
                previous <= phase["deadlineMonotonic"] <= row["absoluteDeadlineMonotonic"] and
                ("outcome" not in phase or phase["outcome"] == "deadline-exhausted"), "PROVIDER_TOOLS_NATIVE_DRAIN_PHASE")
        previous = phase["deadlineMonotonic"]
    require(row["finishedMonotonic"] < previous and "outcome" not in row["phases"][-1], "PROVIDER_TOOLS_NATIVE_DRAIN_RETURN")
    for signal in row["signalReconciliations"]:
        _keys(signal, "identity firstFailure failures firstSignal firstObservation outcome lastIdentity lastFailure lastSignal lastObservation")
        _native_process(signal["identity"], role)
        if signal["lastIdentity"] is not None:
            _native_process(signal["lastIdentity"], role)
        for name in ("firstSignal", "lastSignal"):
            require(type(signal[name]) is int and signal[name] in (15, 9), "PROVIDER_TOOLS_NATIVE_DRAIN_SIGNAL")
        for name in ("firstObservation", "lastObservation"):
            _integer(signal[name], 0, 1023)
        _integer(signal["failures"], 1, 1024)
        require(signal["outcome"] in ("signal-succeeded", "absent", "nonrunning", "replaced") and
                all(type(signal[name]) is str and len(signal[name]) <= 2048 for name in ("firstFailure", "lastFailure")),
                "PROVIDER_TOOLS_NATIVE_DRAIN_SIGNAL")


def _expected_mode(role, phase, compression, flavor):
    if phase == "lookup":
        require(flavor is None, "PROVIDER_TOOLS_LOOKUP_TAR")
        return "LOOKUP_ONLY"
    require(flavor in ("GNU", "BSD"), "PROVIDER_TOOLS_TAR_FLAVOR")
    if compression == "gzip":
        return "BSD_TAR_GZIP" if flavor == "BSD" else "GNU_GZIP"
    return (("WINDOWS_ZSTD_CREATE" if phase == "save" else "WINDOWS_ZSTD_EXTRACT") if role == "windows-x64" else
            "POSIX_ZSTDMT" if phase == "save" else "POSIX_UNZSTD")


def decode(raw, request, *, bindings, python):
    """Strict historical DATA only. No clock/native call or owner is created.

    POSIX PosixInfo intentionally omits gid: actual fd-relative gid/primary-GID
    execution selection is checked by the live owner on all three passes, not
    independently reconstructed by this codec from an omitted field.
    """
    value = _record(raw, MAX_BYTES)
    _keys(value, "schema scope context resolution executables probes chronology")
    frame, context = _context(request, bindings)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and value["context"] == context,
            "PROVIDER_TOOLS_CONTEXT")
    for key, maximum in (("context", 16384), ("resolution", 65536), ("executables", 32768), ("chronology", 4096)):
        require(len(canonical(value[key])) <= maximum, "PROVIDER_TOOLS_COMPARTMENT_BOUND")
    role, phase = context["role"], context["phase"]
    resolution, executables, probes, chronology = (value[key] for key in ("resolution", "executables", "probes", "chronology"))
    _keys(resolution, "environment pathEntries candidates symlinks selected compression tarFlavor compressorMode")
    require(resolution["environment"] == _public_environment(frame), "PROVIDER_TOOLS_ENVIRONMENT")
    paths = frame["toolPath"].split(";" if role == "windows-x64" else ":")
    require(type(resolution["pathEntries"]) is list and len(resolution["pathEntries"]) == len(paths),
            "PROVIDER_TOOLS_PATH_ENTRIES")
    for path, entry in zip(paths, resolution["pathEntries"]):
        _keys(entry, "path native")
        require(entry["path"] == path, "PROVIDER_TOOLS_PATH_ORDER")
        _native(entry["native"], role, directory=True)
    _keys(resolution["selected"], "python node zstd tar compressor")
    selected = resolution["selected"]
    require(type(executables) is list and 2 <= len(executables) <= 6, "PROVIDER_TOOLS_EXECUTABLES")
    public_bytes, identities, pass_times = 0, set(), {name: [] for name in ("initial", "prelaunch", "postProvider")}
    for index, row in enumerate(executables):
        _keys(row, "id tools requestedPath resolvedPath aliasFamily initial prelaunch postProvider")
        require(type(row["id"]) is int and row["id"] == index and type(row["tools"]) is list and
                bool(row["tools"]) and row["tools"] == sorted(set(row["tools"])) and set(row["tools"]) <= set(TOOLS),
                "PROVIDER_TOOLS_EXECUTABLE_ID")
        _path(row["requestedPath"], role); _path(row["resolvedPath"], role)
        require(row["aliasFamily"] == ("ZSTD_ALIASES" if len(row["tools"]) > 1 else "NONE") and
                (len(row["tools"]) == 1 or set(row["tools"]) == {"zstd", "compressor"}), "PROVIDER_TOOLS_ALIAS")
        baseline = None
        for name in pass_times:
            record = row[name]
            _keys(record, "startedNs endedNs native bytes sha256")
            start, end = _ns(record["startedNs"]), _ns(record["endedNs"])
            require(_ns(context["issuedNs"]) <= start <= end < _ns(context["workerCutoffNs"]), "PROVIDER_TOOLS_EXECUTABLE_TIME")
            _integer(record["bytes"], 1, FILE_BYTES); _hex(record["sha256"])
            native_id = _native(record["native"], role)
            require(record["bytes"] == record["native"]["size"], "PROVIDER_TOOLS_EXECUTABLE_SIZE")
            pin = (record["native"], record["bytes"], record["sha256"])
            require(baseline is None or pin == baseline, "PROVIDER_TOOLS_EXECUTABLE_CHANGED")
            baseline = pin
            public_bytes += record["bytes"]
            pass_times[name].append((start, end))
        require(native_id not in identities, "PROVIDER_TOOLS_EXECUTABLE_ALIAS")
        identities.add(native_id)
        require(all(type(selected[tool]) is int and selected[tool] == index for tool in row["tools"]), "PROVIDER_TOOLS_SELECTED")
    require(public_bytes <= TOTAL_BYTES, "PROVIDER_TOOLS_PUBLIC_BYTES")
    for tool in TOOLS:
        index = selected[tool]
        require(index is None or type(index) is int and 0 <= index < len(executables) and tool in executables[index]["tools"],
                "PROVIDER_TOOLS_SELECTED")
    require(selected["python"] is not None and selected["node"] is not None and
            executables[selected["python"]]["requestedPath"] == str(_path(python, role)) and
            executables[selected["node"]]["requestedPath"] == frame["node"], "PROVIDER_TOOLS_RUNTIME")
    compression = resolution["compression"]
    require(compression in ("gzip", "zstd-without-long"), "PROVIDER_TOOLS_COMPRESSION")
    mode = _expected_mode(role, phase, compression, resolution["tarFlavor"])
    require(resolution["compressorMode"] == mode and ((selected["tar"] is None) == (phase == "lookup")) and
            ((selected["compressor"] is None) == (mode in ("LOOKUP_ONLY", "BSD_TAR_GZIP"))), "PROVIDER_TOOLS_MODE")
    require(type(resolution["symlinks"]) is list and len(resolution["symlinks"]) <= 32 and
            (role != "windows-x64" or resolution["symlinks"] == []), "PROVIDER_TOOLS_SYMLINKS")
    links = set()
    for row in resolution["symlinks"]:
        _keys(row, "path target native")
        _path(row["path"], role)
        require(row["path"] not in links and type(row["target"]) is str and 0 < len(row["target"]) <= 4096 and
                all(32 <= ord(char) < 127 for char in row["target"]), "PROVIDER_TOOLS_SYMLINK")
        _native(row["native"], role, symlink=True)
        links.add(row["path"])
    _candidate_data(resolution, executables, frame)
    roster = [("NODE_VERSION", selected["node"])]
    if selected["zstd"] is not None:
        roster.append(("ZSTD_VERSION", selected["zstd"]))
    if selected["tar"] is not None:
        roster.append(("TAR_VERSION", selected["tar"]))
    if selected["compressor"] is not None and selected["compressor"] != selected["zstd"]:
        roster.append(("COMPRESSOR_VERSION", selected["compressor"]))
    require(type(probes) is list and len(probes) == len(roster) <= 4, "PROVIDER_TOOLS_PROBE_ROSTER")
    previous = _ns(context["issuedNs"])
    invocation_ids = {context["innerId"], *(row[0] for row in frame["prefix"])}
    for row, (purpose, index) in zip(probes, roster):
        _keys(row, "purpose executable invocation firstNs returnedNs closedNs exitCode stdout stderr nativeRetirement closedResources")
        require(row["purpose"] == purpose and type(row["executable"]) is int and row["executable"] == index,
                "PROVIDER_TOOLS_PROBE_ROSTER")
        _hex(row["invocation"], 32)
        require(row["invocation"] not in invocation_ids, "PROVIDER_TOOLS_INVOCATION_ALIAS")
        invocation_ids.add(row["invocation"])
        first, returned, closed = (_ns(row[name]) for name in ("firstNs", "returnedNs", "closedNs"))
        require(previous <= first <= returned <= closed < _ns(context["workerCutoffNs"]) and
                _ns(executables[index]["initial"]["endedNs"]) <= first, "PROVIDER_TOOLS_PROBE_TIME")
        previous = closed
        _integer(row["exitCode"], -(1 << 31), (1 << 32) - 1)
        require(row["closedResources"] == list(PROBE_RESOURCES), "PROVIDER_TOOLS_PROBE_CLOSES")
        stdout, stderr = _raw(row["stdout"], OUTPUT_BYTES), _raw(row["stderr"], OUTPUT_BYTES)
        native = _raw(row["nativeRetirement"], NATIVE_BYTES)
        require(len(canonical({key: data for key, data in row.items() if key not in ("stdout", "stderr", "nativeRetirement")})) <= 1024,
                "PROVIDER_TOOLS_PROBE_METADATA_BOUND")
        _retirement(native, frame, row["invocation"], _command(purpose, executables[index]["requestedPath"], compression))
        _version(purpose, stdout, stderr, row["exitCode"], compression, resolution["tarFlavor"], role)
    require(selected["zstd"] is not None or compression == "gzip", "PROVIDER_TOOLS_ABSENT_ZSTD")
    _keys(chronology, "firstNs prelaunchNs providerClosedNs postCheckNs closedNs publicBytes resourceCount state")
    first, prelaunch, provider_closed, postcheck, closed = (_ns(chronology[name]) for name in
        ("firstNs", "prelaunchNs", "providerClosedNs", "postCheckNs", "closedNs"))
    require(_ns(context["issuedNs"]) <= first <= prelaunch <= provider_closed <= postcheck <= closed < _ns(context["workerCutoffNs"]) and
            previous <= prelaunch and chronology["publicBytes"] == public_bytes and type(chronology["publicBytes"]) is int and
            chronology["state"] == "TOOLS_KNOWN_CLOSED_PENDING_WORKER_RETURN", "PROVIDER_TOOLS_CHRONOLOGY")
    _integer(chronology["resourceCount"], 6 * len(probes) + 3 * len(executables), 10000)
    require(all(first <= start <= end <= prelaunch for start, end in pass_times["initial"]) and
            all(previous <= start <= end <= prelaunch for start, end in pass_times["prelaunch"]) and
            all(provider_closed <= start <= end <= postcheck for start, end in pass_times["postProvider"]),
            "PROVIDER_TOOLS_PASS_CHRONOLOGY")
    return value


def _version(purpose, stdout, stderr, code, compression, flavor, role):
    selected = compression_from_streams(stdout, stderr)
    if purpose == "NODE_VERSION":
        require(code == 0 and stderr == b"" and re.fullmatch(rb"v24\.[0-9]+\.[0-9]+\r?\n", stdout), "PROVIDER_TOOLS_NODE24")
    elif purpose == "ZSTD_VERSION":
        require(selected == compression, "PROVIDER_TOOLS_COMPRESSION_CHANGED")
    elif purpose == "TAR_VERSION":
        require(code == 0, "PROVIDER_TOOLS_TAR_EXIT")
        if role == "windows-x64":
            require(flavor == "GNU" and windows_gnu_tar(stdout, stderr), "PROVIDER_TOOLS_WINDOWS_GNU_TAR")
        else:
            require(bool(stdout) != bool(stderr), "PROVIDER_TOOLS_TAR_STREAMS")
            text = (stdout or stderr).strip(TRIM).lower()
            require((b"gnu tar" in text) if flavor == "GNU" else text.startswith(b"bsdtar "), "PROVIDER_TOOLS_TAR_FLAVOR")
    else:
        require(purpose == "COMPRESSOR_VERSION" and code == 0 and selected == "zstd-without-long",
                "PROVIDER_TOOLS_COMPRESSOR_VERSION")
        if compression == "gzip":
            require(b"gzip" in (stdout + stderr).lower(), "PROVIDER_TOOLS_GZIP_VERSION")


def _candidate_data(resolution, executables, frame):
    rows, paths, selected = resolution["candidates"], resolution["pathEntries"], resolution["selected"]
    require(type(rows) is list and 2 <= len(rows) <= 512, "PROVIDER_TOOLS_CANDIDATES")
    for row in rows:
        _keys(row, "tool literal path pathEntry status executable")
        require(row["tool"] in TOOLS and type(row["literal"]) is str and 0 < len(row["literal"]) <= 4096 and
                row["status"] in ("ABSENT", "NOT_EXECUTABLE", "SELECTED"), "PROVIDER_TOOLS_CANDIDATE")
        _path(row["path"], frame["role"])
        require(row["pathEntry"] is None or type(row["pathEntry"]) is int and 0 <= row["pathEntry"] < len(paths),
                "PROVIDER_TOOLS_CANDIDATE_PARENT")
        require((row["executable"] is None) == (row["status"] != "SELECTED"), "PROVIDER_TOOLS_CANDIDATE_SELECTION")
        if row["status"] == "SELECTED":
            index = row["executable"]
            require(type(index) is int and 0 <= index < len(executables) and index == selected[row["tool"]],
                    "PROVIDER_TOOLS_CANDIDATE_SELECTION")
            require(row["path"] == executables[index]["requestedPath"] or
                    (row["tool"] == "compressor" and index == selected["zstd"] and
                     executables[index]["aliasFamily"] == "ZSTD_ALIASES"), "PROVIDER_TOOLS_CANDIDATE_SELECTION")
            resolved = _resolved_data(row["path"], resolution["symlinks"], frame["role"])
            expected = executables[index]["resolvedPath"]
            require((resolved.casefold() == expected.casefold() if frame["role"] == "windows-x64" else resolved == expected),
                    "PROVIDER_TOOLS_CANDIDATE_LINKS")
    for tool in ("python", "node", "zstd", "tar", "compressor"):
        chosen = [row for row in rows if row["tool"] == tool and row["status"] == "SELECTED"]
        require(len(chosen) == int(selected[tool] is not None), "PROVIDER_TOOLS_CANDIDATE_ROSTER")
    cursor = 0
    kind = PureWindowsPath if frame["role"] == "windows-x64" else PurePosixPath
    def take(tool, literal, path, ordinal):
        nonlocal cursor
        require(cursor < len(rows), "PROVIDER_TOOLS_CANDIDATE_ROSTER")
        row = rows[cursor]
        cursor += 1
        expected = path.casefold() if frame["role"] == "windows-x64" else path
        actual = row["path"].casefold() if frame["role"] == "windows-x64" else row["path"]
        require(row["tool"] == tool and row["literal"] == literal and actual == expected and row["pathEntry"] == ordinal,
                "PROVIDER_TOOLS_SEARCH_ORDER")
        return row
    def search(tool, literal):
        name = literal + (".EXE" if frame["role"] == "windows-x64" else "")
        for index, entry in enumerate(paths):
            row = take(tool, literal, str(kind(entry["path"]) / name), index)
            if row["status"] == "SELECTED":
                return True
        return False
    for tool in ("python", "node"):
        path = executables[selected[tool]]["requestedPath"]
        require(take(tool, path, path, None)["status"] == "SELECTED", "PROVIDER_TOOLS_RUNTIME_SELECTION")
    require(search("zstd", "zstd") == (selected["zstd"] is not None), "PROVIDER_TOOLS_ZSTD_SELECTION")
    if frame["phase"] != "lookup":
        if frame["role"] == "windows-x64":
            for literal in (r"undefined\Git\usr\bin\tar.exe", r"undefined\Windows\System32\tar.exe"):
                require(take("tar", literal, str(kind(str(SCRIPTS.parent)) / literal), None)["status"] == "ABSENT",
                        "PROVIDER_TOOLS_WINDOWS_FALLBACK_UNQUALIFIED")
            require(search("tar", "tar") and resolution["tarFlavor"] == "GNU", "PROVIDER_TOOLS_TAR_SELECTION")
        elif frame["role"].startswith("macos-"):
            gnu = search("tar", "gtar")
            require((gnu or search("tar", "tar")) and resolution["tarFlavor"] == ("GNU" if gnu else "BSD"),
                    "PROVIDER_TOOLS_TAR_SELECTION")
        else:
            require(search("tar", "tar") and resolution["tarFlavor"] == "GNU", "PROVIDER_TOOLS_TAR_SELECTION")
    mode = resolution["compressorMode"]
    if mode not in ("LOOKUP_ONLY", "BSD_TAR_GZIP"):
        name = {"GNU_GZIP": "gzip", "POSIX_ZSTDMT": "zstdmt", "POSIX_UNZSTD": "unzstd",
                "WINDOWS_ZSTD_CREATE": "zstd", "WINDOWS_ZSTD_EXTRACT": "zstd"}[mode]
        require(search("compressor", name), "PROVIDER_TOOLS_COMPRESSOR_SELECTION")
    require(cursor == len(rows), "PROVIDER_TOOLS_EXTRA_CANDIDATE")


def _resolved_data(path, links, role):
    """Lexical replay of the retained link texts; not a native path lookup."""
    if role == "windows-x64":
        return path  # Reparse points are refused by the actual native supplier.
    link_map = {row["path"]: row["target"] for row in links}
    pending, current, seen = list(PurePosixPath(path).parts[1:]), [], set()
    while pending:
        name = pending.pop(0)
        if name in ("", "."):
            continue
        if name == "..":
            require(current, "PROVIDER_TOOLS_LINK_ESCAPE")
            current.pop()
            continue
        candidate = "/" + "/".join([*current, name])
        if candidate in link_map:
            require(candidate not in seen and len(seen) < 32, "PROVIDER_TOOLS_LINK_CYCLE")
            seen.add(candidate)
            target = PurePosixPath(link_map[candidate])
            if target.is_absolute():
                current = []
                pending = list(target.parts[1:]) + pending
            else:
                pending = list(target.parts) + pending
        else:
            current.append(name)
    return "/" + "/".join(current)


@dataclass(frozen=True, repr=False)
class ToolObservation:
    raw: bytes = field(repr=False)
    scope: str = field(default="ORIGINAL_TOOLS_CLOSED_RETURN_ONLY_V1", init=False)


@dataclass(repr=False)
class _Resource:
    name: str
    owner: object = None
    attempted: bool = False
    closed: bool = False


class _Descriptor:
    def __init__(self, descriptor):
        self.fd, self.closed = descriptor, False

    def close(self):
        require(not self.closed, "PROVIDER_TOOLS_DESCRIPTOR_CLOSED")
        self.closed = True
        os.close(self.fd)


class ToolObserver:
    """One original worker's tools owner; no caller-supplied native backend.

    Unknown acquisition/read/close is terminal. The separate original enclosing
    supervisor must retire the worker and its inherited descendants; quarantine
    here is preservation, not retirement or permission to retry/clean up.
    """
    def __init__(self, frame, request, bindings, python, directory, window):
        frame_copy, context = _context(request, bindings)
        require(frame == frame_copy and python == sys.executable and
                canonical(frame) == request and _path(python, frame["role"]), "PROVIDER_TOOLS_ORIGINAL_FRAME")
        self.frame, self.request, self.bindings, self.python = frame_copy, request, tuple(sorted(bindings.items())), python
        self.context, self.directory, self.window = context, directory, window
        self._original = (request, canonical(frame_copy), self.bindings, python, directory, window,
                          sys.version_info, sys.implementation.name)
        self._thread, self._error, self._state = threading.get_ident(), None, "NEW"
        self._resources, self._public_dirs, self._public_pin_gids = [], {}, {}
        self._resource_roster = self._resources
        self._closed_resources = None
        self._links, self._candidates, self._observations = {}, [], []
        self._rows, self._probes, self._path_entries = [], [], []
        self._selected = dict.fromkeys(TOOLS)
        self._compression = self._tar_flavor = self._mode = None
        self._public_bytes = 0
        self._first = self._prelaunch = self._provider_closed = None
        self._result = self._result_bytes = None
        self._alias_paths = {}
        self._uid = os.getuid() if frame["role"] != "windows-x64" else None
        self._gid = os.getgid() if frame["role"] != "windows-x64" else None

    def _failed(self, error):
        if self._error is None:
            self._error = error
        if not any(item is self for item in QUARANTINE):
            QUARANTINE.append(self)
        return self._error

    def _check(self, *, work=False):
        if self._error is not None:
            raise self._error
        saved = self._original
        require(threading.get_ident() == self._thread and self.request is saved[0] and canonical(self.frame) == saved[1] and
                self.bindings is saved[2] and self.python == saved[3] == sys.executable and self.directory is saved[4] and
                self.window is saved[5] and sys.version_info == saved[6] and sys.implementation.name == saved[7] and
                self._resources is self._resource_roster,
                "PROVIDER_TOOLS_OWNER_CHANGED")
        require(self.frame["role"] == "windows-x64" or (os.getuid(), os.getgid()) == (self._uid, self._gid),
                "PROVIDER_TOOLS_NATIVE_USER_CHANGED")
        now = self.window.check(work=work)
        require(self._error is None and self.window is saved[5] and canonical(self.frame) == saved[1],
                "PROVIDER_TOOLS_OWNER_CHANGED")
        return now

    def _take(self, name, factory):
        self._check()
        require(len(self._resources) < 10000 and all(slot.name != name for slot in self._resources),
                "PROVIDER_TOOLS_RESOURCE_ROSTER")
        slot = _Resource(name)
        self._resources.append(slot)  # Register attempted obligation BEFORE native call.
        slot.attempted = True
        try:
            slot.owner = factory()  # First action after actual return.
            require(slot.owner is not None and all(other is slot or other.owner is not slot.owner for other in self._resources),
                    "PROVIDER_TOOLS_UNRETURNED_OR_ALIASED_OWNER")
            self._check()
            return slot.owner
        except BaseException as error:
            raise self._failed(error)

    def _close(self, owner):
        self._check()
        slots = [slot for slot in self._resources if slot.owner is owner]
        require(len(slots) == 1 and not slots[0].closed, "PROVIDER_TOOLS_ORIGINAL_CLOSE")
        slot = slots[0]
        try:
            owner.close()
            slot.closed = True  # Actual known return, never an intended close.
            self._check()
        except BaseException as error:
            raise self._failed(error)

    def _public_safe(self, info, gid):
        # Root-owned installed tools and the actual runner's private tools are
        # valid public inputs; do not misuse seed's current-UID-only root API.
        # This is an explicit public no-write contract, not private file access.
        require(info.uid in (0, self._uid) and not info.mode & 0o022 and type(gid) is int and gid >= 0,
                "PROVIDER_TOOLS_PUBLIC_OWNER_OR_MODE")

    def _posix_directory(self, path, parent=None):
        key = str(path)
        if key in self._public_dirs:
            pin = self._public_dirs[key]
            current = pin.observe()
            gid = os.fstat(pin.fd).st_gid
            require(gid == self._public_pin_gids[key], "PROVIDER_TOOLS_PUBLIC_GROUP_CHANGED")
            self._public_safe(current, gid)
            return pin
        require(self._state == "PREPARING", "PROVIDER_TOOLS_NEW_PATH_AFTER_PREPARE")
        native = self._take("public-directory:" + str(len(self._public_dirs)), lambda: _Descriptor(os.open(
            "/" if parent is None else path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            **({} if parent is None else {"dir_fd": parent.fd}))))
        pin = public_files._PosixPin(native.fd, path, parent, None if parent is None else path.name,
                                     directory=True, private=None, immutable=True)
        self._public_dirs[key] = pin
        self._public_pin_gids[key] = os.fstat(native.fd).st_gid
        self._public_safe(pin.observe(), self._public_pin_gids[key])
        self._check()
        return pin

    def _posix_inspect(self, requested):
        """Descriptor-relative walk, explicitly pin every traversed symlink."""
        pending = list(PurePosixPath(requested).parts[1:])
        parent = self._posix_directory(Path("/"))
        seen = set()
        while pending:
            self._check()
            name = pending.pop(0)
            if name in ("", "."):
                continue
            if name == "..":
                require(parent.path != Path("/"), "PROVIDER_TOOLS_LINK_ESCAPE")
                parent = self._public_dirs[str(parent.path.parent)]
                continue
            parent.observe()
            path = parent.path / name
            try:
                native = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
            except FileNotFoundError:
                parent.observe()
                return None
            self._check()
            info = public_files._info(native)
            if stat.S_ISLNK(native.st_mode):
                require(str(path) not in seen, "PROVIDER_TOOLS_LINK_CYCLE")
                require(info.uid in (0, self._uid) and native.st_gid >= 0, "PROVIDER_TOOLS_PUBLIC_LINK_OWNER")
                seen.add(str(path))
                target = os.readlink(name, dir_fd=parent.fd)
                require(type(target) is str and 0 < len(target) <= 4096 and
                        all(32 <= ord(char) < 127 for char in target), "PROVIDER_TOOLS_LINK_TEXT")
                again = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
                require(public_files._info(again) == info and again.st_gid == native.st_gid,
                        "PROVIDER_TOOLS_LINK_CHANGED")
                parent.observe()
                row = {"path": str(path), "target": target, "native": json.loads(canonical(info.as_dict()))}
                _native(row["native"], self.frame["role"], symlink=True)
                if str(path) in self._links:
                    require(self._links[str(path)] == (row, native.st_gid), "PROVIDER_TOOLS_LINK_CHANGED")
                else:
                    require(self._state == "PREPARING" and len(self._links) < 32, "PROVIDER_TOOLS_LINK_BOUND")
                    self._links[str(path)] = (row, native.st_gid)
                target_path = PurePosixPath(target)
                if target_path.is_absolute():
                    parent = self._public_dirs["/"]
                    parts = list(target_path.parts[1:])
                else:
                    parts = list(target_path.parts)
                pending = parts + pending
                continue
            self._public_safe(info, native.st_gid)
            if pending:
                require(stat.S_ISDIR(native.st_mode), "PROVIDER_TOOLS_SELECTED_PARENT_KIND")
                parent = self._posix_directory(path, parent)
                require(parent.observe() == info and self._public_pin_gids[str(path)] == native.st_gid,
                        "PROVIDER_TOOLS_SELECTED_PARENT_CHANGED")
            else:
                parent.observe()
                return path, info, native.st_gid, parent
        return parent.path, parent.observe(), self._public_pin_gids[str(parent.path)], parent

    def _windows_directory(self, path):
        key = str(path)
        if key not in self._public_dirs:
            require(self._state == "PREPARING", "PROVIDER_TOOLS_NEW_PATH_AFTER_PREPARE")
            owner = self._take("public-directory:" + str(len(self._public_dirs)),
                lambda: public_files.windows.open_dependency_source(key))
            self._public_dirs[key] = owner
        result = self._public_dirs[key]
        result.verify()
        self._check()
        return result

    def _windows_inspect(self, requested):
        path = PureWindowsPath(requested)
        # The maintained public-root API requires at least one path component;
        # passing a bare volume root cannot work and must not relax that API.
        # PATH directories and the source workspace are already pinned with
        # their complete native ancestry. Start from the deepest such original
        # owner, then enumerate each remaining name under its native pin. A
        # runtime outside those roots uses its real existing parent through the
        # same maintained API. Bare-volume runtime parents remain unsupported.
        folded = tuple(part.casefold() for part in path.parts)
        candidates = [(PureWindowsPath(str(owner.path)), owner) for owner in self._public_dirs.values()]
        candidates = [(parent, owner) for parent, owner in candidates
                      if tuple(part.casefold() for part in parent.parts) == folded[:len(parent.parts)]]
        if candidates:
            parent, owner = max(candidates, key=lambda item: len(item[0].parts))
        else:
            require(path.parent != PureWindowsPath(path.anchor), "PROVIDER_TOOLS_WINDOWS_VOLUME_ROOT_UNQUALIFIED")
            owner = self._windows_directory(path.parent)
            parent = PureWindowsPath(str(owner.path))
        parts = list(path.parts[len(parent.parts):])
        for index, name in enumerate(parts):
            self._check()
            prior = owner.verify()
            names = owner.names(max_names=10000, deadline=self.window.local_end)
            matches = [entry for entry in names if entry.casefold() == name.casefold()]
            require(len(matches) <= 1 and owner.verify() == prior, "PROVIDER_TOOLS_WINDOWS_NAME_ALIAS")
            if not matches:
                return None
            actual = PureWindowsPath(str(owner.path)) / matches[0]
            if index < len(parts) - 1:
                owner = self._windows_directory(actual)
            else:
                # The maintained public supplier rejects reparse/ADS/directory
                # ambiguity and keeps all parent pins. No ACL fallback is used.
                reader = self._take("public-inspect:" + str(len(self._resources)), lambda: owner.open_file(
                    matches[0], max_bytes=FILE_BYTES, deadline=self.window.local_end))
                info = reader.verify()
                require(info == reader.initial_info and not info.is_directory, "PROVIDER_TOOLS_WINDOWS_EXECUTABLE")
                self._close(reader)
                return Path(str(actual)), info, None, owner
        return Path(str(path)), owner.verify(), None, owner

    def _inspect(self, requested):
        self._check()
        result = (self._windows_inspect(requested) if self.frame["role"] == "windows-x64" else
                  self._posix_inspect(requested))
        self._check()
        return result

    def _executable(self, observed):
        if observed is None:
            return False
        path, info, gid, _parent = observed
        if self.frame["role"] == "windows-x64":
            return not info.is_directory and path.suffix.casefold() == ".exe"
        # Exact @actions/io tryGetExecutablePath predicate at this pin. Neither
        # os.access, supplementary groups nor root's special X semantics apply.
        return stat.S_ISREG(info.mode) and bool(info.mode & stat.S_IXOTH or
            gid == self._gid and info.mode & stat.S_IXGRP or self._uid == info.uid and info.mode & stat.S_IXUSR)

    def _candidate(self, tool, literal, requested, ordinal, *, require_absent=False):
        require(len(self._candidates) < 512, "PROVIDER_TOOLS_CANDIDATE_BOUND")
        observed = self._inspect(requested)
        status = "ABSENT" if observed is None else "SELECTED" if self._executable(observed) else "NOT_EXECUTABLE"
        require(not require_absent or status == "ABSENT", "PROVIDER_TOOLS_WINDOWS_FALLBACK_UNQUALIFIED")
        index = None
        selected_path = requested
        if observed is not None and self.frame["role"] == "windows-x64" and tool not in ("python", "node"):
            selected_path = str(observed[0])  # Actual PATH filename, not a rewritten runtime argv.
        if status == "SELECTED":
            index = self._select(tool, selected_path, observed)
        row = {"tool": tool, "literal": literal, "path": selected_path, "pathEntry": ordinal,
               "status": status, "executable": index}
        self._candidates.append(row)
        self._observations.append((requested, observed, status))
        return index

    def _which(self, tool, literal):
        for ordinal, entry in enumerate(self._path_entries):
            kind = PureWindowsPath if self.frame["role"] == "windows-x64" else PurePosixPath
            name = literal + (".EXE" if self.frame["role"] == "windows-x64" and not literal.lower().endswith(".exe") else "")
            requested = str(kind(entry["path"]) / name)
            found = self._candidate(tool, literal, requested, ordinal)
            if found is not None:
                return found
        return None

    def _select(self, tool, requested, observed):
        path, info, _gid, _parent = observed
        require(self._selected[tool] is None, "PROVIDER_TOOLS_DUPLICATE_SELECTION")
        same = [row for row in self._rows if tuple(row["initial"]["native"]["identity"]) == tuple(info.identity)]
        if same:
            require(len(same) == 1 and tool == "compressor" and same[0]["tools"] == ["zstd"] and
                    Path(requested).name.casefold() in ("zstd", "zstd.exe", "zstdmt", "unzstd"), "PROVIDER_TOOLS_EXECUTABLE_ALIAS")
            row = same[0]
            require(str(path) == row["resolvedPath"], "PROVIDER_TOOLS_HARDLINK_ALIAS_REFUSED")
            row["tools"] = ["compressor", "zstd"]
            row["aliasFamily"] = "ZSTD_ALIASES"
            self._alias_paths[tool] = (requested, observed)
        else:
            require(len(self._rows) < 6 and info.size > 0, "PROVIDER_TOOLS_EXECUTABLE_BOUND")
            row = {"id": len(self._rows), "tools": [tool], "requestedPath": requested, "resolvedPath": str(path),
                   "aliasFamily": "NONE", "initial": None, "prelaunch": None, "postProvider": None}
            self._rows.append(row)
            row["initial"] = self._read(row, observed)
        self._selected[tool] = row["id"]
        return row["id"]

    def _read(self, row, observed):
        start = self._check()
        path, info, gid, parent = observed
        require(self._executable(observed) and 0 < info.size <= FILE_BYTES and
                self._public_bytes + info.size <= TOTAL_BYTES, "PROVIDER_TOOLS_PUBLIC_READ_BOUND")
        windows = self.frame["role"] == "windows-x64"
        if windows:
            reader = self._take("public-reader:" + str(len(self._resources)), lambda: parent.open_file(
                path.name, max_bytes=FILE_BYTES, deadline=self.window.local_end))
            before = reader.verify()
            read = reader.read
        else:
            reader = self._take("public-reader:" + str(len(self._resources)), lambda: _Descriptor(os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent.fd)))
            pin = public_files._PosixPin(reader.fd, path, parent, path.name,
                                         directory=False, private=None, immutable=True)
            before = pin.observe()
            require(os.fstat(reader.fd).st_gid == gid, "PROVIDER_TOOLS_PUBLIC_GROUP_CHANGED")
            read = lambda count: os.read(reader.fd, count)
        require(before == info, "PROVIDER_TOOLS_PUBLIC_REPLACED")
        digest, size = hashlib.sha256(), 0
        while size < info.size:
            self._check()
            part = read(min(BLOCK, info.size - size))
            require(type(part) is bytes and 0 < len(part) <= info.size - size, "PROVIDER_TOOLS_PUBLIC_SHORT_READ")
            size += len(part)
            self._public_bytes += len(part)  # Charge actual bytes, including any eventual failed pass.
            require(self._public_bytes <= TOTAL_BYTES, "PROVIDER_TOOLS_PUBLIC_READ_BOUND")
            digest.update(part)
        require(read(1) == b"", "PROVIDER_TOOLS_PUBLIC_EOF")
        require((reader.verify() if windows else pin.observe()) == before, "PROVIDER_TOOLS_PUBLIC_CHANGED")
        if not windows:
            require(os.fstat(reader.fd).st_gid == gid, "PROVIDER_TOOLS_PUBLIC_GROUP_CHANGED")
        parent.verify() if windows else parent.observe()
        self._close(reader)
        result = {"startedNs": str(start), "endedNs": str(self._check()),
                  "native": json.loads(canonical(before.as_dict())), "bytes": size, "sha256": digest.hexdigest()}
        _native(result["native"], self.frame["role"])
        return result

    def _recheck_graph(self):
        self._check()
        windows = self.frame["role"] == "windows-x64"
        for key, owner in tuple(self._public_dirs.items()):
            if windows:
                owner.verify()
            else:
                info = owner.observe()
                require(os.fstat(owner.fd).st_gid == self._public_pin_gids[key], "PROVIDER_TOOLS_PUBLIC_GROUP_CHANGED")
                self._public_safe(info, self._public_pin_gids[key])
            self._check()
        for requested, old, status in self._observations:
            current = self._inspect(requested)
            actual = "ABSENT" if current is None else "SELECTED" if self._executable(current) else "NOT_EXECUTABLE"
            require(actual == status and ((old is None and current is None) or
                    old is not None and current is not None and old[:3] == current[:3]), "PROVIDER_TOOLS_RESOLUTION_CHANGED")
        # Every recorded symlink, including one in an earlier absent candidate,
        # has just been encountered again through the exact original traversal.
        self._check()

    def _pass(self, name):
        self._recheck_graph()
        for row in self._rows:
            current = self._inspect(row["requestedPath"])
            require(current is not None and str(current[0]) == row["resolvedPath"], "PROVIDER_TOOLS_EXECUTABLE_CHANGED")
            data = self._read(row, current)
            require(all(data[key] == row["initial"][key] for key in ("native", "bytes", "sha256")),
                    "PROVIDER_TOOLS_EXECUTABLE_CHANGED")
            require(row[name] is None, "PROVIDER_TOOLS_DUPLICATE_PASS")
            row[name] = data
        self._recheck_graph()

    def _probe_environment(self, invocation, state):
        frame = self.frame
        domains = [dict(zip(("id", "job", "state", "home"), row)) for row in frame["prefix"]]
        original = {processes.JOB_ENV: frame["job"], processes.CHAIN_ENV: ":".join(row["id"] for row in domains),
                    processes.DOMAINS_ENV: canonical(domains).decode("ascii"), processes.STATE_ENV: frame["directory"],
                    "GRADLE_USER_HOME": frame["home"]}
        require(domains and domains[-1] == {"id": frame["outerId"], "job": frame["job"],
                "state": frame["directory"], "home": frame["home"]}, "PROVIDER_TOOLS_PARENT_MARKERS")
        env = processes.ownership_environment({**_public_environment(frame), **original}, frame["job"], invocation, state, frame["home"])
        require(set(env) == set(_public_environment(frame)) | set(MARKERS) and
                processes.ownership_domains(env[processes.CHAIN_ENV], env[processes.DOMAINS_ENV]) ==
                domains + [{"id": invocation, "job": frame["job"], "state": state, "home": frame["home"]}],
                "PROVIDER_TOOLS_CREDENTIAL_FREE_HANDOFF")
        return env

    def _probe(self, purpose, index):
        first = self._check(work=True)
        require(len(self._probes) < 4, "PROVIDER_TOOLS_PROBE_BOUND")
        number = len(self._probes)
        prefix = "probe:" + str(number) + ":"
        directory = self._take(prefix + "directory", lambda: self.directory.create_directory(
            "tool-probe-" + str(number), deadline=self.window.local_end))
        stdout = self._take(prefix + "stdoutWriter", lambda: directory.create_file(
            "stdout.log", max_bytes=OUTPUT_BYTES, deadline=self.window.local_end))
        stderr = self._take(prefix + "stderrWriter", lambda: directory.create_file(
            "stderr.log", max_bytes=OUTPUT_BYTES, deadline=self.window.local_end))
        invocation = uuid.uuid4().hex
        require(invocation not in {self.frame["innerId"], *(row[0] for row in self.frame["prefix"]),
                                   *(row["invocation"] for row in self._probes)},
                "PROVIDER_TOOLS_INVOCATION_ALIAS")
        scope = self._take(prefix + "scope", lambda: processes.make_scope(
            self.frame["job"], invocation, str(directory.path), self.frame["home"]))
        expected_scope = (processes.WindowsScope if self.frame["role"] == "windows-x64" else
                          processes.LinuxScope if self.frame["role"] == "linux-x64" else processes.DarwinScope)
        require(type(scope) is expected_scope and scope.invocation == invocation and
                (scope.job_id if self.frame["role"] == "windows-x64" else scope.job) == self.frame["job"],
                "PROVIDER_TOOLS_ORIGINAL_SCOPE")
        require(self.frame["role"] == "windows-x64" or
                (scope.state, scope.home) == (str(directory.path), self.frame["home"]), "PROVIDER_TOOLS_ORIGINAL_SCOPE")
        argv = tuple(_command(purpose, self._rows[index]["requestedPath"], self._compression))
        env = self._probe_environment(invocation, str(directory.path))
        self._recheck_graph()
        self._check(work=True)
        # Original child is retained on the actual native scope immediately;
        # that scope, not the supplier's one-leader scope, owns this probe.
        child = scope.spawn(argv, str(SCRIPTS.parent), env, stdout=stdout, stderr=stderr)
        child_type = processes.WindowsProcess if self.frame["role"] == "windows-x64" else processes.PosixProcess
        require(type(child) is child_type and scope.leaders == [child] and len(scope.launches) == 1 and
                child.stdout is None and child.stderr is None, "PROVIDER_TOOLS_ORIGINAL_CHILD")
        while True:
            self._check(work=True)
            for writer in (stdout, stderr):
                writer.observe_live_output() if self.frame["role"] == "windows-x64" else writer.verify()
                self._check(work=True)
            code = child.poll()
            if code is not None:
                _integer(code, -(1 << 31), (1 << 32) - 1)
                returned = self._check()
                break
            scope.discover()
            remaining = self.window.local_end - self.window.local()
            require(remaining > 0, "PROVIDER_TOOLS_EXPIRED")
            time.sleep(min(.025, remaining))
        remaining = self.window.local_end - self.window.local()
        require(remaining > 0, "PROVIDER_TOOLS_EXPIRED")
        survivors = scope.drain(grace=min(5.0, remaining), kill_wait=min(5.0, max(0.0, remaining - 5.0)),
                                deadline=self.window.local_end)
        require(type(survivors) is list and survivors == [] and not getattr(scope, "pending_discoveries", {}),
                "PROVIDER_TOOLS_RETIREMENT_UNKNOWN")
        native = canonical(scope.description()) + b"\n"
        _retirement(native, self.frame, invocation, list(argv))
        self._close(scope)
        original = {}
        for name, writer in (("stdout", stdout), ("stderr", stderr)):
            self._check()
            writer.sync()
            info = writer.verify()
            original[name] = info
            self._close(writer)
        captures = {}
        for name in ("stdout", "stderr"):
            path = directory.path / (name + ".log")
            reader = self._take(prefix + name + "Reader", lambda name=name, path=path:
                directory.open_file(name + ".log", max_bytes=OUTPUT_BYTES, deadline=self.window.local_end)
                if self.frame["role"] == "windows-x64" else private_files._posix_stream(
                    path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb"))
            before = reader.verify() if self.frame["role"] == "windows-x64" else private_files._file_info(path, reader, OUTPUT_BYTES)
            prior = original[name]
            # Windows final write timestamps settle at writer close. Bind the
            # same original file/owner/size, then keep the fresh reader's FULL
            # immutable stamp across complete read/EOF/known reader close.
            same_file = (all(getattr(before, key) == getattr(prior, key) for key in
                ("identity", "size", "links", "attributes", "creation_100ns", "owner_sid", "protected_dacl"))
                if self.frame["role"] == "windows-x64" else before == prior)
            require(same_file,
                    "PROVIDER_TOOLS_PROBE_FILE_REPLACED")
            raw = reader.read(OUTPUT_BYTES + 1)
            self._check()
            require(type(raw) is bytes and len(raw) == before.size <= OUTPUT_BYTES and reader.read(1) == b"" and
                    (reader.verify() if self.frame["role"] == "windows-x64" else private_files._file_info(path, reader, OUTPUT_BYTES)) == before,
                    "PROVIDER_TOOLS_PROBE_BYTES_CHANGED")
            directory.verify()
            self._close(reader)
            captures[name] = raw
        self._close(directory)
        require(all(slot.closed for slot in self._resources if slot.name.startswith(prefix)) and
                [slot.name[len(prefix):] for slot in self._resources if slot.name.startswith(prefix)] == list(PROBE_RESOURCES),
                "PROVIDER_TOOLS_PROBE_OWNER_CLOSES")
        row = {"purpose": purpose, "executable": index, "invocation": invocation, "firstNs": str(first),
               "returnedNs": str(returned), "closedNs": str(self._check()), "exitCode": code,
               "stdout": base64.b64encode(captures["stdout"]).decode("ascii"),
               "stderr": base64.b64encode(captures["stderr"]).decode("ascii"),
               "nativeRetirement": base64.b64encode(native).decode("ascii"), "closedResources": list(PROBE_RESOURCES)}
        self._probes.append(row)
        return captures["stdout"], captures["stderr"], code

    def prepare(self):
        try:
            require(self._state == "NEW", "PROVIDER_TOOLS_ONE_PREPARE")
            self._state = "PREPARING"
            self._first = self._check(work=True)
            require(self.directory.path == Path(self.frame["directory"]) and
                    tuple(self.directory.identity) == tuple(self.frame["directoryIdentity"]), "PROVIDER_TOOLS_BORROWED_ROOT")
            self.directory.verify()
            if self.frame["role"] == "windows-x64":
                # Required native base for the two literal undefined\\...
                # fallback absence walks; do not invent PROGRAMFILES/DRIVE.
                self._windows_directory(str(SCRIPTS.parent))
            for path in self.frame["toolPath"].split(";" if self.frame["role"] == "windows-x64" else ":"):
                if self.frame["role"] == "windows-x64":
                    info = self._windows_directory(path).verify()
                else:
                    actual = self._posix_inspect(path)
                    require(actual is not None and actual[1].is_directory, "PROVIDER_TOOLS_MISSING_PATH_DIRECTORY")
                    resolved, info, gid, parent = actual
                    pinned = self._posix_directory(resolved, parent if parent.path != resolved else parent.parent)
                    require(pinned.observe() == info and self._public_pin_gids[str(resolved)] == gid,
                            "PROVIDER_TOOLS_PATH_DIRECTORY_CHANGED")
                native = json.loads(canonical(info.as_dict()))
                _native(native, self.frame["role"], directory=True)
                self._path_entries.append({"path": path, "native": native})
            for tool, path in (("python", self.python), ("node", self.frame["node"])):
                require(self._candidate(tool, path, path, None) is not None, "PROVIDER_TOOLS_RUNTIME_MISSING")
            zstd = self._which("zstd", "zstd")
            out, err, code = self._probe("NODE_VERSION", self._selected["node"])
            _version("NODE_VERSION", out, err, code, "gzip", None, self.frame["role"])
            if zstd is None:
                self._compression = "gzip"
            else:
                out, err, code = self._probe("ZSTD_VERSION", zstd)
                self._compression = compression_from_streams(out, err)
            if self.frame["phase"] != "lookup":
                if self.frame["role"] == "windows-x64":
                    for literal in (r"undefined\Git\usr\bin\tar.exe", r"undefined\Windows\System32\tar.exe"):
                        self._candidate("tar", literal, str(PureWindowsPath(str(SCRIPTS.parent)) / literal), None,
                                        require_absent=True)
                    tar = self._which("tar", "tar")
                    self._tar_flavor = "GNU"
                elif self.frame["role"].startswith("macos-"):
                    tar = self._which("tar", "gtar")
                    self._tar_flavor = "GNU" if tar is not None else "BSD"
                    if tar is None:
                        tar = self._which("tar", "tar")
                else:
                    tar = self._which("tar", "tar")
                    self._tar_flavor = "GNU"
                require(tar is not None, "PROVIDER_TOOLS_TAR_MISSING")
                out, err, code = self._probe("TAR_VERSION", tar)
                _version("TAR_VERSION", out, err, code, self._compression, self._tar_flavor, self.frame["role"])
            self._mode = _expected_mode(self.frame["role"], self.frame["phase"], self._compression, self._tar_flavor)
            if self._mode not in ("LOOKUP_ONLY", "BSD_TAR_GZIP"):
                name = {"GNU_GZIP": "gzip", "POSIX_ZSTDMT": "zstdmt", "POSIX_UNZSTD": "unzstd",
                        "WINDOWS_ZSTD_CREATE": "zstd", "WINDOWS_ZSTD_EXTRACT": "zstd"}[self._mode]
                compressor = self._which("compressor", name)
                require(compressor is not None, "PROVIDER_TOOLS_COMPRESSOR_MISSING")
                if compressor != self._selected["zstd"]:
                    out, err, code = self._probe("COMPRESSOR_VERSION", compressor)
                    _version("COMPRESSOR_VERSION", out, err, code, self._compression, self._tar_flavor, self.frame["role"])
            self._check(work=True)
            self._state = "PREPARED"
        except BaseException as error:
            raise self._failed(error)

    def before_provider(self):
        try:
            require(self._state == "PREPARED", "PROVIDER_TOOLS_PRELAUNCH_STATE")
            self._pass("prelaunch")
            self._prelaunch = self._check(work=True)
            self._state = "PROVIDER_PENDING"
        except BaseException as error:
            raise self._failed(error)

    def finish(self, provider_closed_ns):
        """Caller supplies its actual original capture-close observation, not DATA."""
        try:
            require(self._state == "PROVIDER_PENDING" and type(provider_closed_ns) is int and
                    self._prelaunch <= provider_closed_ns <= self._check(), "PROVIDER_TOOLS_PROVIDER_CLOSE")
            self._provider_closed = provider_closed_ns
            self._pass("postProvider")
            postcheck = self._check()
            for slot in reversed(self._resources):
                if not slot.closed:
                    require(slot.owner is not None, "PROVIDER_TOOLS_UNRETURNED_OWNER")
                    self._close(slot.owner)
            require(all(slot.closed for slot in self._resources), "PROVIDER_TOOLS_OWNERS_NOT_CLOSED")
            value = {"schema": 1, "scope": SCOPE, "context": self.context,
                "resolution": {"environment": _public_environment(self.frame), "pathEntries": self._path_entries,
                    "candidates": self._candidates, "symlinks": [row for row, _gid in self._links.values()],
                    "selected": self._selected, "compression": self._compression, "tarFlavor": self._tar_flavor,
                    "compressorMode": self._mode}, "executables": self._rows, "probes": self._probes,
                "chronology": {"firstNs": str(self._first), "prelaunchNs": str(self._prelaunch),
                    "providerClosedNs": str(provider_closed_ns), "postCheckNs": str(postcheck),
                    "closedNs": str(self._check()), "publicBytes": self._public_bytes,
                    "resourceCount": len(self._resources), "state": "TOOLS_KNOWN_CLOSED_PENDING_WORKER_RETURN"}}
            raw = canonical(value) + b"\n"
            decode(raw, self.request, bindings=dict(self.bindings), python=self.python)
            self._check()
            self._result_bytes = raw
            self._closed_resources = tuple((slot, slot.name, slot.owner) for slot in self._resources)
            self._result = ToolObservation(raw)
            self._state = "CLOSED"
            return self._result
        except BaseException as error:
            raise self._failed(error)

    def check_result(self, result):
        self._check()
        require(self._state == "CLOSED" and type(result) is ToolObservation and result is self._result and
                result.raw is self._result_bytes and type(self._closed_resources) is tuple and
                len(self._resources) == len(self._closed_resources) and
                all(slot is original and slot.name == name and slot.owner is owner and slot.attempted and slot.closed
                    for slot, (original, name, owner) in zip(self._resources, self._closed_resources)),
                "PROVIDER_TOOLS_ORIGINAL_RETURN_CHANGED")
        # The immutable exact bytes were decoded once at their original return.
        # Revalidate identity/ledger/window here, not a repeated DATA parse in
        # lieu of that actual registered return or new native observation.
        self._check()
        require(result is self._result and result.raw is self._result_bytes, "PROVIDER_TOOLS_ORIGINAL_RETURN_CHANGED")
        return result.raw
