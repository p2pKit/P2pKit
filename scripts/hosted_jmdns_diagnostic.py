#!/usr/bin/env python3
"""Pure DATA for the fixed JmDNS diagnostic, never an execution/permission token.

The maintenance carrier owns original source/report/receipt custody. This module
does not read files, start processes, query policy, or grant release acceptance.
Existing native logs require review of their actual client/code/time semantics;
an emitter PID, executable signature or NoRouteToHostException is not a denial.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import PurePosixPath
import re

GRADLE_ARGUMENTS = (
    ":p2p-transport-lan:jvmTest", "--tests",
    "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally",
    "--no-configure-on-demand",
)
MODES = ("control", "failed_recovery", "shared_close", "close_wins", "recovery_wins",
         "responder_close", "callback_executor", "cleanup_retry")
FIXTURE_LIMIT, LOG_LIMIT, CODE_LIMIT = 65536, 1048576, 65536
LOG_SECONDS, CODE_SECONDS, HASH_SECONDS = 45, 15, 5
OBSERVATION_SECONDS, PRODUCT_SECONDS = 120, 1200
PATH_PREFIX = b"p2pkit-jmdns-executable-path-v1\0"
PREDICATE = (
    '(process == "nehelper" OR process == "networkd" OR process == "mDNSResponder" '
    'OR subsystem BEGINSWITH "com.apple.network" '
    'OR (process == "kernel" AND eventMessage CONTAINS[c] "necp")) AND '
    '(eventMessage CONTAINS[c] "local network" OR eventMessage CONTAINS[c] "local-network" '
    'OR eventMessage CONTAINS[c] "necp" OR eventMessage CONTAINS[c] "policy" '
    'OR eventMessage CONTAINS[c] "deny" OR eventMessage CONTAINS[c] "denied" '
    'OR eventMessage CONTAINS[c] "responsib")'
)
HASH = re.compile(r"[0-9a-f]{64}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
INTEGER = r"(?:0|-?[1-9][0-9]{0,18})"
POSITIVE = r"[1-9][0-9]{0,18}"
PROCESS_LINE = re.compile(
    r"startup processIdentity schema=1 mode=([a-z_]+) pid=(" + POSITIVE + r"|UNKNOWN) "
    r"birthEpochMillis=(" + POSITIVE + r"|UNKNOWN) birthPrecision=(MILLISECONDS|UNKNOWN) "
    r"executablePathSha256=([0-9a-f]{64}|UNKNOWN)\Z")
SEND_LINE = re.compile(
    r"startup firstSendIdentity schema=1 ordinal=(" + POSITIVE + r") "
    r"utcBeforeMillis=(" + POSITIVE + r") utcAfterMillis=(" + POSITIVE + r") "
    r"monotonicBeforeNanos=(" + INTEGER + r") monotonicAfterNanos=(" + INTEGER + r")\Z")
FAILURE_LINE = re.compile(
    r"startup firstSendFailureClass=([A-Za-z_$][A-Za-z0-9_.$]{0,255}) "
    r"firstSendDestinationIpv4Mdns=(true|false|UNKNOWN)\Z")
TRACE_KEYS = {
    "schema", "status", "reason", "traceSha256", "mode", "pid", "birthEpochMillis", "birthPrecision",
    "executablePathSha256", "ordinal", "utcBeforeMillis", "utcAfterMillis", "monotonicBeforeNanos",
    "monotonicAfterNanos", "failureClass", "destinationIpv4Mdns",
}
NATIVE_KEYS = {
    "pid", "uid", "parentPid", "group", "uniqueId", "parentUniqueId", "pidVersion", "startSeconds",
    "startMicroseconds", "realUid", "status", "flags", "live",
}
BINDING_KEYS = {
    "schema", "status", "reason", "trace", "nativeIdentity", "invocationId", "jobId",
    "productStartedUtc", "productEndedUtc", "queryStartUtc", "queryEndUtc",
}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MAX_MILLIS = 253402300799999  # Last representable UTC millisecond, not an execution deadline.


class DiagnosticError(ValueError):
    """Only fixed, non-secret source-owned reason codes."""


def require(condition, reason):
    if not condition:
        raise DiagnosticError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inconclusive(reason, **metadata):
    return {"schema": 1, "status": "INCONCLUSIVE", "reason": reason, **metadata}


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def hash_value(value):
    return type(value) is str and HASH.fullmatch(value) is not None


def path_identity(real_executable_path):
    require(type(real_executable_path) is str and real_executable_path.startswith("/") and
            not real_executable_path.startswith("//") and
            all(ord(char) >= 32 and ord(char) != 127 for char in real_executable_path), "EXECUTABLE_PATH")
    path = PurePosixPath(real_executable_path)
    require(str(path) == real_executable_path and ".." not in path.parts and path.name == "java",
            "EXECUTABLE_PATH")
    try:
        raw = real_executable_path.encode("utf-8")
    except UnicodeError:
        raise DiagnosticError("EXECUTABLE_PATH") from None
    require(len(raw) <= 16384, "EXECUTABLE_PATH_BOUND")
    return digest(PATH_PREFIX + raw)


def code_argv(real_executable_path):
    path_identity(real_executable_path)
    return {"signature": ["/usr/bin/codesign", "-d", "--verbose=4", real_executable_path],
            "uuid": ["/usr/bin/xcrun", "dwarfdump", "--uuid", real_executable_path]}


def validate_trace(trace):
    require(type(trace) is dict and set(trace) == TRACE_KEYS and type(trace["schema"]) is int and
            trace["schema"] == 1 and trace["status"] == "CAPTURED" and
            trace["reason"] == "ORIGINAL_FAILURE_METADATA", "FIXTURE_TRACE_SCHEMA")
    require(hash_value(trace["traceSha256"]) and hash_value(trace["executablePathSha256"]) and
            trace["mode"] in MODES and integer(trace["pid"], 1, 2**31 - 1) and
            trace["birthPrecision"] == "MILLISECONDS" and
            integer(trace["birthEpochMillis"], 1, MAX_MILLIS) and
            integer(trace["ordinal"], 1, 2**31 - 1), "FIXTURE_IDENTITY")
    require(type(trace["failureClass"]) is str and re.fullmatch(
            r"[A-Za-z_$][A-Za-z0-9_.$]{0,255}", trace["failureClass"]) is not None and
            (type(trace["destinationIpv4Mdns"]) is bool or trace["destinationIpv4Mdns"] is None),
            "FIXTURE_ORIGINAL_FAILURE")
    require(all(integer(trace[key], 1, MAX_MILLIS) for key in ("utcBeforeMillis", "utcAfterMillis")) and
            all(integer(trace[key], -(2**63), 2**63 - 1)
                for key in ("monotonicBeforeNanos", "monotonicAfterNanos")), "FIXTURE_CLOCK_FIELDS")
    before, after = trace["utcBeforeMillis"], trace["utcAfterMillis"]
    # nanoTime has an arbitrary, possibly negative origin and can wrap signed64.
    # The enclosing monotonic reads bracket the two millisecond UTC reads. Only
    # their documented millisecond rounding is allowed, not invented tolerance.
    elapsed = (trace["monotonicAfterNanos"] - trace["monotonicBeforeNanos"]) % (2**64)
    require(trace["birthEpochMillis"] <= before <= after and after - before <= 45000 and
            elapsed <= 45_000_000_000 and (after - before) * 1_000_000 <= elapsed + 999999,
            "FIXTURE_CLOCK_ORDER")


def parse_fixture_trace(raw):
    metadata = {"traceSha256": digest(raw)} if type(raw) is bytes and len(raw) <= FIXTURE_LIMIT else {}
    try:
        require(type(raw) is bytes and 0 < len(raw) <= FIXTURE_LIMIT, "FIXTURE_OUTPUT_BOUND")
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeError:
            raise DiagnosticError("FIXTURE_OUTPUT_ENCODING") from None

        def one(prefix, pattern):
            selected = [line for line in lines if line.startswith(prefix)]
            require(len(selected) == 1, "FIXTURE_METADATA_MISSING_OR_AMBIGUOUS")
            match = pattern.fullmatch(selected[0])
            require(match is not None, "FIXTURE_METADATA_FORMAT")
            return match.groups()

        process = one("startup processIdentity", PROCESS_LINE)
        send = one("startup firstSendIdentity", SEND_LINE)
        failure = one("startup firstSendFailureClass", FAILURE_LINE)
        require([line for line in lines if line.startswith("FAIL mode=")] == ["FAIL mode=" + process[0]] and
                not any(line.startswith("PASS mode=") for line in lines), "FIXTURE_FAILURE_OUTCOME")
        require("UNKNOWN" not in process, "FIXTURE_PROCESS_METADATA_UNAVAILABLE")
        trace = {"schema": 1, "status": "CAPTURED", "reason": "ORIGINAL_FAILURE_METADATA", **metadata,
                 "mode": process[0], "pid": int(process[1]), "birthEpochMillis": int(process[2]),
                 "birthPrecision": process[3], "executablePathSha256": process[4],
                 "failureClass": failure[0],
                 "destinationIpv4Mdns": {"true": True, "false": False, "UNKNOWN": None}[failure[1]]}
        trace.update(zip(("ordinal", "utcBeforeMillis", "utcAfterMillis", "monotonicBeforeNanos",
                          "monotonicAfterNanos"), map(int, send)))
        validate_trace(trace)
        return trace
    except DiagnosticError as error:
        return inconclusive(str(error), **metadata)


def utc_millis(value):
    require(type(value) is str and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)", value),
            "PRODUCT_UTC_FORMAT")
    try:
        delta = datetime.fromisoformat(value.replace("Z", "+00:00")) - EPOCH
    except (ValueError, OverflowError):
        raise DiagnosticError("PRODUCT_UTC_FORMAT") from None
    result = (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000
    require(0 < result <= MAX_MILLIS, "PRODUCT_UTC_BOUND")
    return result


def native_identity(identity, trace):
    require(type(identity) is dict and set(identity) == NATIVE_KEYS, "NATIVE_IDENTITY_FIELDS")
    require(all(integer(identity[key], 1, 2**31 - 1) for key in ("pid", "parentPid", "group")) and
            all(integer(identity[key], 0, 2**32 - 1) for key in ("uid", "realUid", "flags")) and
            integer(identity["uniqueId"], 1, 2**64 - 1) and
            integer(identity["parentUniqueId"], 0, 2**64 - 1) and
            integer(identity["pidVersion"], 0, 2**31 - 1) and
            integer(identity["startSeconds"], 1, MAX_MILLIS // 1000) and
            integer(identity["startMicroseconds"], 0, 999999) and integer(identity["status"], 1, 5) and
            type(identity["live"]) is bool, "NATIVE_IDENTITY_TYPES")
    require(identity["pid"] == trace["pid"] and
            identity["startSeconds"] * 1000 + identity["startMicroseconds"] // 1000 == trace["birthEpochMillis"],
            "NATIVE_FIXTURE_LIFETIME_MISMATCH")


def query_window(trace):
    # Whole-second CLI parsing: rounding + one second is always <2s per edge.
    # Rounding + two seconds would silently exceed the approved edge margin.
    start = trace["utcBeforeMillis"] // 1000 - 1
    end = (trace["utcAfterMillis"] + 999) // 1000 + 1
    require(0 < start < end and end - start <= 50, "LOG_WINDOW_BOUND")
    try:
        return tuple((EPOCH + timedelta(seconds=value)).strftime("%Y-%m-%d %H:%M:%S")
                     for value in (start, end))
    except (ValueError, OverflowError):
        raise DiagnosticError("LOG_WINDOW_BOUND") from None


def validate_binding(binding):
    require(type(binding) is dict and set(binding) == BINDING_KEYS and type(binding["schema"]) is int and
            binding["schema"] == 1 and binding["status"] == "BOUND" and
            binding["reason"] == "ORIGINAL_FIRST_SEND_IDENTITY", "LOG_BINDING_SCHEMA")
    trace = binding["trace"]
    validate_trace(trace)
    require(trace["mode"] == "control" and trace["ordinal"] == 1 and
            trace["failureClass"] == "java.net.NoRouteToHostException" and
            trace["destinationIpv4Mdns"] is True, "ORIGINAL_FIRST_SEND_NOT_CAPTURED")
    require(type(binding["invocationId"]) is str and re.fullmatch(r"[0-9a-f]{32}", binding["invocationId"]) and
            type(binding["jobId"]) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", binding["jobId"]),
            "LOG_BINDING_INVOCATION")
    native_identity(binding["nativeIdentity"], trace)
    require(utc_millis(binding["productStartedUtc"]) <= trace["birthEpochMillis"] <=
            trace["utcBeforeMillis"] <= trace["utcAfterMillis"] <= utc_millis(binding["productEndedUtc"]),
            "FIXTURE_OUTSIDE_PRODUCT_INTERVAL")
    require(query_window(trace) == (binding["queryStartUtc"], binding["queryEndUtc"]), "LOG_WINDOW_MISMATCH")


def bind_native_process(trace, receipt, *, invocation_id, job_id, executable_path_sha256):
    try:
        validate_trace(trace)
        require(hash_value(executable_path_sha256) and
                executable_path_sha256 == trace["executablePathSha256"], "FIXTURE_EXECUTABLE_MISMATCH")
        require(type(receipt) is dict and type(receipt.get("schema")) is int and receipt["schema"] == 1 and
                receipt.get("id") == invocation_id and receipt.get("jobId") == job_id and
                receipt.get("kind") == "command", "TARGET_RECEIPT_IDENTITY")
        require(integer(receipt.get("productExitCode"), 1, 123) and
                type(receipt.get("finalExitCode")) is int and
                receipt["finalExitCode"] == receipt["productExitCode"] and
                type(receipt.get("stopExitCode")) is int and receipt["stopExitCode"] == 0 and
                receipt.get("ownedSurvivors") == [] and receipt.get("errors") == [] and
                not receipt.get("cancelledSignals") and not receipt.get("cancelRequested") and
                receipt.get("sourceUnchanged") is True, "TARGET_NOT_CLOSED_FAILURE")
        source = receipt.get("sourceBefore")
        require(type(source) is dict and set(source) == {"commit", "tree", "status", "diffSha256"} and
                all(type(source[key]) is str and SHA.fullmatch(source[key]) for key in ("commit", "tree")) and
                source["status"] == "" and source["diffSha256"] == digest(b"") and
                receipt.get("sourceAfter") == source, "TARGET_SOURCE_CHANGED")
        ownership = receipt.get("ownership")
        require(type(ownership) is dict and ownership.get("backend") == "darwin-libproc-audit-token" and
                ownership.get("scope") == "controlled-marker-inheriting-descendants" and
                ownership.get("invocation") == invocation_id and ownership.get("job") == job_id and
                ownership.get("discoveryErrors") == [], "NATIVE_OWNER_MISMATCH")
        identities = ownership.get("startedIdentities")
        require(type(identities) is list and 0 < len(identities) <= 65536 and
                all(type(row) is dict and integer(row.get("pid"), 1, 2**31 - 1) for row in identities),
                "NATIVE_IDENTITIES_FORMAT")
        matches = [row for row in identities if row["pid"] == trace["pid"]]
        require(len(matches) == 1, "NATIVE_FIXTURE_LIFETIME_AMBIGUOUS")
        native_identity(matches[0], trace)
        require(integer(receipt.get("productPid"), 1, 2**31 - 1) and receipt["productPid"] != trace["pid"],
                "FIXTURE_IS_NOT_GRADLE_CHILD")
        start, end = query_window(trace)
        binding = {"schema": 1, "status": "BOUND", "reason": "ORIGINAL_FIRST_SEND_IDENTITY",
                   "trace": dict(trace), "nativeIdentity": dict(matches[0]), "invocationId": invocation_id,
                   "jobId": job_id, "productStartedUtc": receipt.get("productStartedUtc"),
                   "productEndedUtc": receipt.get("productEndedUtc"), "queryStartUtc": start, "queryEndUtc": end}
        validate_binding(binding)
        return binding
    except DiagnosticError as error:
        return inconclusive(str(error))


def log_argv(binding):
    validate_binding(binding)
    return ["/usr/bin/log", "show", "--style", "json", "--info", "--debug", "--timezone", "UTC",
            "--start", binding["queryStartUtc"], "--end", binding["queryEndUtc"], "--predicate", PREDICATE]


def log_data(stdout, stderr, exit_code, binding):
    metadata = {}
    try:
        log_argv(binding)
        require(type(stdout) is bytes and type(stderr) is bytes and len(stdout) + len(stderr) <= LOG_LIMIT,
                "NATIVE_OUTPUT_BOUND")
        metadata = {"stdoutSha256": digest(stdout), "stderrSha256": digest(stderr), "exitCode": exit_code}
        require(integer(exit_code, 0, 123), "NATIVE_EXIT_UNKNOWN_OR_RESERVED")
        require(exit_code == 0, "NATIVE_QUERY_NONZERO")
        try:
            text, error_text = stdout.decode("utf-8"), stderr.decode("utf-8")
        except UnicodeError:
            raise DiagnosticError("NATIVE_OUTPUT_ENCODING") from None
        require("<private>" not in text.lower() + error_text.lower(), "NATIVE_OUTPUT_REDACTED")

        def unique(pairs):
            value = {}
            for key, item in pairs:
                require(key not in value, "NATIVE_JSON_DUPLICATE")
                value[key] = item
            return value

        try:
            records = json.loads(text, object_pairs_hook=unique,
                                 parse_constant=lambda _: require(False, "NATIVE_JSON_NONFINITE"))
        except DiagnosticError:
            raise
        except (ValueError, RecursionError):
            raise DiagnosticError("NATIVE_JSON_FORMAT") from None
        require(type(records) is list and all(type(row) is dict for row in records), "NATIVE_JSON_SHAPE")
        metadata["recordCount"] = len(records)
        require(records, "NATIVE_HISTORY_EMPTY")
        # Deliberately no manufactured Apple schema or positive regex classifier.
        # Root must review actual original client/code/lifetime/denial semantics.
        return inconclusive("NATIVE_ORIGINAL_REVIEW_REQUIRED", **metadata)
    except DiagnosticError as error:
        return inconclusive(str(error), **metadata)
