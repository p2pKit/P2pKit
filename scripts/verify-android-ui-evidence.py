#!/usr/bin/env python3
"""Check retained #317/#324 bytes and claims, never execute or admit Android.

This passive verifier has no collector/install/receipt schema. Supplied source and
token expectations are declarations, not provenance. Even a consistent positive
report remains HARNESS_PASS_PENDING_REVIEW / runtimeAcceptance=NOT_ACCEPTED.
Input files are never written, converted, extracted, imported or executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import zlib

PACKAGE = "dev.p2pkit.sample.android"
POSITIVE = "HARNESS_PASS_PENDING_REVIEW"
MIB = 1024 * 1024
# Existing writers: PNG 16 MiB / 16,777,216 pixels; Parcel 1 MiB;
# result/events/#317 trees and each rolling diagnostic generation 2 MiB.
PNG_LIMIT, PIXEL_LIMIT, PARCEL_LIMIT, TEXT_LIMIT = 16 * MIB, 16_777_216, MIB, 2 * MIB
# New passive-host admission limits, NOT guarantees made by the guest writers.
# In particular #324 capture-tree/saved-state JSON have no explicit writer byte cap.
STREAM_LIMIT, FILE_LIMIT, DIRECTORY_LIMIT, DEPTH_LIMIT = 8 * MIB, 256, 64, 6
TOTAL_LIMITS = {"317": 64 * MIB, "324": 1024 * MIB}
READ_CHUNK, VERIFY_SECONDS = 64 * 1024, 60
MAX_INTEGER = (1 << 63) - 1
TESTS = {
    "317": ("UiAcceptanceInstrumentation", "diagnosticEventAppearsWithoutInput"),
    "324": ("CredentialUiInstrumentation", "productionCredentialRestorationAndLifecycle"),
}
BOUNDS = {
    "317": {"body": 60_000, "setup": 25_000, "handsOffRefresh": 5_000,
            "mainCall": 5_000, "cleanupAction": 10_000},
    "324": {"body": 150_000, "setup": 20_000, "mainCall": 5_000, "observation": 5_000,
            "cleanupAction": 10_000, "outer": 240_000},
}
CELLS_324 = (
    "default-mask-and-explicit-reveal-hide", "real-fifteen-second-expiry", "pre-clear-parcel-save",
    "disposal-of-original-owner", "actual-registry-restoration", "stop-reentry", "fakegrant-true-resumed",
    "explicit-protected-join-success", "fakegrant-false-resumed", "fakegrant-true-stopped",
    "join-success-then-failure", "failure-without-success-control", "final-card-disposal",
)
CLEANUP_324 = (
    "modeled-pending-result", "test-compositions", "frame-and-window-observers", "fake-kit-stop",
    "test-viewmodel-store", "owned-activity", "lifecycle-observer", "retain-diagnostics",
)
CAPTURES_324 = tuple("""
initial-card default-masking explicit-reveal explicit-hide expiry-start expired-mask
before-save-revealed disposal-of-original-owner restored-empty-secret restored-ssid
before-stop before-stop-revealed stop-reentry-reentered-empty
fakegrant-true-resumed-input fakegrant-true-resumed-revealed fakegrant-true-resumed-cleared
explicit-protected-join-success-input explicit-protected-join-success-revealed
explicit-protected-join-success dismiss-joined-empty
fakegrant-false-resumed-input fakegrant-false-resumed-revealed fakegrant-false-resumed-cleared
fakegrant-true-stopped-input fakegrant-true-stopped-revealed fakegrant-true-stopped-reentered-empty
join-success-then-failure-input join-success-then-failure-revealed join-success-then-failure-cleared
failure-control-input failure-without-success-control final-card-disposal
""".split())
STATUS_CAPTURES_324 = {"initial-card", "disposal-of-original-owner", "explicit-protected-join-success",
                       "final-card-disposal"}
REVEALED_324 = {"explicit-reveal", "expiry-start", "before-save-revealed", "before-stop-revealed",
                "fakegrant-true-resumed-revealed", "explicit-protected-join-success-revealed",
                "fakegrant-false-resumed-revealed", "fakegrant-true-stopped-revealed",
                "join-success-then-failure-revealed"}
EMPTY_324 = {"restored-empty-secret", "stop-reentry-reentered-empty", "fakegrant-true-resumed-cleared",
             "dismiss-joined-empty", "fakegrant-false-resumed-cleared", "fakegrant-true-stopped-reentered-empty",
             "join-success-then-failure-cleared"}
DIRECTORIES_324 = {"fixture", "fixture/no-backup", "fixture/cache", "fixture/no-backup/test-diagnostics"}
FIXTURE_ACTIVE_324 = "fixture/no-backup/test-diagnostics/diagnostic-events.jsonl"
FIXTURE_LOCK_324 = "fixture/no-backup/test-diagnostics/.diagnostic-events.jsonl.lock"
FIXTURE_LOG = re.compile(r"fixture/no-backup/test-diagnostics/(?:diagnostic-events\.jsonl(?:\.[1-3])?|"
                         r"\.diagnostic-events\.jsonl\.lock)")
BASE_REPORT = {"case", "sourceCommit", "declaredSourceTree", "treeBinding", "api", "targetSdk", "abis", "pid",
               "processStartElapsedMillis", "boundsMillis", "outcome", "lifecycle", "actions", "frames",
               "cleanupScope", "failure"}
REPORT_FIELDS = {
    "317": BASE_REPORT | {"schemaVersion", "token", "uid", "beforeScreenshot", "baselineRecord", "identity",
                          "recorderBefore", "droppedBefore", "handsOffStart", "recorderAfter", "injection",
                          "renderedWitnessObservedElapsedNanos", "afterScreenshot", "handsOffEnd", "observedCounts",
                          "droppedAfter", "cleanupFailures", "inputs", "windowEvents", "overflow",
                          "unexpectedActivity", "independentVisualAndMutationReview", "failedScreenshot"},
    "324": BASE_REPORT | {"cleanup", "cells", "lifecycleViolation", "permissionModel", "permissionTrace",
                          "provisioningCalls", "compositionObservations", "captures", "revealExpiry",
                          "failureDisplayUnavailable"},
}


class Rejected(ValueError):
    pass


class Incomplete(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Rejected(message)


def required(value, name):
    need(type(value) is dict, "Expected an object")
    if name not in value:
        raise Incomplete("Missing field: " + name)
    return value[name]


def integer(value, minimum=0, maximum=MAX_INTEGER):
    need(type(value) is int and minimum <= value <= maximum, "Invalid bounded integer")
    return value


def sequence(value, maximum, minimum=0):
    need(type(value) is list and minimum <= len(value) <= maximum, "Invalid bounded array")
    return value


def exact_keys(value, names):
    need(type(value) is dict and set(value) == set(names), "Unexpected object fields")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate JSON key")
            value[key] = item
        return value

    def finite_float(value):
        number = float(value)
        need(math.isfinite(number), "Nonfinite JSON number")
        return number

    def bounded_integer(value):
        need(len(value) <= 20, "Oversized JSON integer")
        number = int(value)
        need(-MAX_INTEGER - 1 <= number <= MAX_INTEGER, "JSON integer outside signed 64-bit range")
        return number

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: need(False, "Nonfinite JSON number"), parse_float=finite_float,
                          parse_int=bounded_integer)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise Rejected("Malformed/unsupported JSON") from error


def parse_terminal(raw, case, token):
    """Parse only the two current UI terminal bundles, not adb/process success."""
    need(case in TESTS and type(token) is str and re.fullmatch(r"[0-9a-f]{32}", token), "Invalid case/token")
    need(type(raw) is bytes and len(raw) <= STREAM_LIMIT, "Oversized/nonbyte instrumentation stream")
    if not raw or not raw.endswith(b"\n"):
        raise Incomplete("Instrumentation stream is empty or ends in a partial line")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as error:
        raise Rejected("Non-UTF8 instrumentation stream") from error
    status, result, status_code, final_code = {}, {}, None, None
    for line in lines:
        if not line:
            continue
        need(final_code is None, "Output follows the terminal instrumentation code")
        if line.startswith(("INSTRUMENTATION_FAILED:", "INSTRUMENTATION_ABORTED:")):
            raise Incomplete("Framework did not complete the named UI case")
        if line.startswith(("INSTRUMENTATION_STATUS: ", "INSTRUMENTATION_RESULT: ")):
            prefix, field = line.split(": ", 1)
            key, equals, value = field.partition("=")
            need(equals and re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", key), "Malformed instrumentation field")
            is_status = prefix == "INSTRUMENTATION_STATUS"
            need((status_code is None) == is_status, "Out-of-order instrumentation bundle")
            target = status if is_status else result
            need(key not in target, "Duplicate instrumentation field")
            target[key] = value
        elif line.startswith("INSTRUMENTATION_STATUS_CODE: "):
            need(status and status_code is None and not result, "Duplicate/missing terminal status bundle")
            value = line[len("INSTRUMENTATION_STATUS_CODE: "):]
            need(value in ("0", "-2"), "Not a UI terminal status")
            status_code = int(value)
        elif line.startswith("INSTRUMENTATION_CODE: "):
            need(status_code is not None and result, "Missing result bundle")
            value = line[len("INSTRUMENTATION_CODE: "):]
            need(value in ("-1", "0"), "Unexpected UI instrumentation code")
            final_code = int(value)
        else:
            raise Rejected("Unsupported instrumentation output line")
    if final_code is None:
        raise Incomplete("Instrumentation stream has no complete terminal")
    need(status == result, "Terminal status/result bundles differ")
    expected = {"class": PACKAGE + ".runtime." + TESTS[case][0], "test": TESTS[case][1],
                "numtests": "1", "current": "1", "p2pkitCompleted": "1"}
    need(all(result.get(key) == value for key, value in expected.items()), "Wrong UI test identity/count")
    allowed = set(expected) | {"p2pkitToken", "p2pkitEvidence", "p2pkitOutcome", "p2pkitFailureStage",
                               "p2pkitRetention"}
    if case == "317":
        allowed |= {"p2pkitCleanup", "p2pkitFailureType"}
    need(set(result) <= allowed, "Unknown UI result field")
    outcome = required(result, "p2pkitOutcome")
    need((outcome, status_code, final_code) in ((POSITIVE, 0, -1), ("FAIL", -2, 0)),
         "UI outcome and terminal codes disagree")
    for key, value in (("p2pkitToken", token), ("p2pkitEvidence", f"no_backup/ui-{case}-{token}")):
        if outcome == POSITIVE:
            required(result, key)
        if key in result:
            need(result[key] == value, "Wrong token/evidence path")
    if outcome == POSITIVE:
        need(not any(key in result for key in ("p2pkitFailureStage", "p2pkitFailureType", "p2pkitRetention")),
             "Positive terminal contains failure/retention error")
        if case == "317":
            need(result.get("p2pkitCleanup") == "RETIRED_OWNED_OBSERVERS", "Wrong #317 cleanup claim")
    return result


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def checked_path(value):
    path = Path(value).absolute()
    need(".." not in path.parts, "Parent traversal in input path")
    for current in (*reversed(path.parents), path):
        try:
            info = current.lstat()
        except FileNotFoundError as error:
            raise Incomplete("Missing retained input") from error
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Symlink/reparse-point input")
    return path


class Snapshot:
    """Exclusive-retained-input consistency checks, not hostile-filesystem atomicity."""
    def __init__(self, case):
        self.case = case
        self.deadline = time.monotonic() + VERIFY_SECONDS
        self.files, self.directories, self.identities, self.content, self.headers = {}, [], {}, {}, {}
        self.total = 0
        self.inodes = set()

    def bound(self):
        need(time.monotonic() <= self.deadline, "Passive verifier deadline exceeded")

    def read(self, path, limit, keep=True):
        self.bound()
        path = checked_path(path)
        before = path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= limit,
             "Nonregular/aliased/oversized input")
        marker = (before.st_dev, before.st_ino)
        need(marker not in self.inodes, "Aliased retained inputs")
        self.inodes.add(marker)
        chunks, prefix, count, hasher = [], b"", 0, hashlib.sha256()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            need(identity(opened) == identity(before), "Input changed before read")
            while True:
                self.bound()
                block = stream.read(min(READ_CHUNK, limit - count + 1))
                if not block:
                    break
                count += len(block)
                need(count <= limit, "Input grew past its bound")
                hasher.update(block)
                prefix += block[:max(0, 33 - len(prefix))]
                if keep:
                    chunks.append(block)
            need(identity(os.fstat(stream.fileno())) == identity(opened), "Input changed while reading")
        need(identity(path.lstat()) == identity(before) and count == before.st_size, "Input changed after read")
        self.identities[path] = identity(before)
        return {"bytes": count, "sha256": hasher.hexdigest()}, b"".join(chunks), prefix

    def directory(self, root):
        root = checked_path(root)
        need(stat.S_ISDIR(root.lstat().st_mode), "Evidence root is not a directory")

        def visit(path, depth):
            self.bound()
            need(depth <= DEPTH_LIMIT and len(self.directories) < DIRECTORY_LIMIT, "Directory/depth limit")
            before = path.lstat()
            need(stat.S_ISDIR(before.st_mode) and not path.is_symlink() and
                 not getattr(before, "st_file_attributes", 0) & 0x400, "Non-directory/reparse point in retained tree")
            relative = path.relative_to(root).as_posix()
            if relative != ".":
                need(self.case == "324" and relative in DIRECTORIES_324, "Unexpected retained directory")
            self.directories.append(relative)
            self.identities[path] = identity(before)
            children = []
            with os.scandir(path) as entries:
                for entry in entries:
                    need(len(children) < FILE_LIMIT + DIRECTORY_LIMIT, "Directory membership bound")
                    children.append(entry)
            children.sort(key=lambda entry: entry.name)
            for entry in children:
                need(re.fullmatch(r"[A-Za-z0-9._-]{1,200}", entry.name) and entry.name not in (".", ".."),
                     "Unsafe retained filename")
                info = entry.stat(follow_symlinks=False)
                child = path / entry.name
                if stat.S_ISDIR(info.st_mode):
                    visit(child, depth + 1)
                    continue
                name = child.relative_to(root).as_posix()
                need(len(self.files) < FILE_LIMIT, "File count limit")
                limit = allowed_file(self.case, name)
                description, raw, prefix = self.read(child, limit, not name.endswith((".png", ".parcel")))
                self.total += description["bytes"]
                need(self.total <= TOTAL_LIMITS[self.case], "Aggregate retained evidence bound")
                self.files[name], self.content[name], self.headers[name] = description, raw, prefix
            need(identity(path.lstat()) == identity(before), "Directory changed during enumeration")

        visit(root, 0)

    def unchanged(self):
        for path, previous in self.identities.items():
            self.bound()
            need(identity(path.lstat()) == previous, "Retained input changed during verification")


def allowed_file(case, name):
    if case == "317":
        allowed = {"result.json", "events.jsonl", "before-tree.json", "before.png", "after-tree.json", "after.png",
                   "failed-tree.json", "failed.png"}
    else:
        allowed = {"result.json", "events.jsonl", "saved-state.parcel", "saved-state.json", "failure.png",
                   "failure-tree.json"} | {label + suffix for label in CAPTURES_324 for suffix in (".png", "-tree.json")}
        if FIXTURE_LOG.fullmatch(name):
            return 0 if name.endswith(".lock") else TEXT_LIMIT
    need(name in allowed, "Unexpected retained file")
    return PNG_LIMIT if name.endswith(".png") else PARCEL_LIMIT if name.endswith(".parcel") else TEXT_LIMIT


def json_file(snapshot, name):
    if name not in snapshot.files:
        raise Incomplete("Missing retained file: " + name)
    return strict_json(snapshot.content[name])


def png(snapshot, name, claim, hash_key):
    if name not in snapshot.files:
        raise Incomplete("Missing retained PNG: " + name)
    row, header = snapshot.files[name], snapshot.headers[name]
    need(row["bytes"] >= 33 and len(header) == 33 and header[:8] == b"\x89PNG\r\n\x1a\n" and
         header[8:16] == b"\0\0\0\rIHDR", "Missing PNG/IHDR header")
    width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", header[16:29])
    allowed_depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    need(width > 0 and height > 0 and width * height <= PIXEL_LIMIT and depth in allowed_depths.get(color, ()) and
         compression == filtering == 0 and interlace in (0, 1) and
         zlib.crc32(header[12:29]) & 0xffffffff == struct.unpack(">I", header[29:33])[0], "Invalid PNG IHDR")
    need(type(claim) is dict and row["sha256"] == claim.get(hash_key) and
         type(claim.get("width")) is int and type(claim.get("height")) is int and
         (width, height) == (claim["width"], claim["height"]), "PNG hash/dimensions disagree with report")


def ordered_times(rows, name, maximum):
    values = [integer(required(row, name)) for row in sequence(rows, maximum)]
    need(values == sorted(values), "Out-of-order retained timestamps")
    return values


def frame(value, case):
    names = {"label", "armedElapsedNanos", "committedElapsedNanos",
             "removedBeforeCommit" if case == "317" else "armCount"}
    exact_keys(value, names)
    need(type(value["label"]) is str and re.fullmatch(r"[a-z0-9-]{1,100}", value["label"]), "Invalid frame label")
    armed = integer(value["armedElapsedNanos"])
    committed = integer(value["committedElapsedNanos"])
    need(committed >= armed and committed > 0, "Uncommitted/contradictory frame claim")
    if case == "317":
        need(value["removedBeforeCommit"] is False, "Positive frame was removed before commit")
    else:
        integer(value["armCount"], 1, 1000)
    return committed


def common_report(report, terminal, case, token, commit, tree):
    need(type(report) is dict and set(report) <= REPORT_FIELDS[case], "Unknown case report fields")
    positive = terminal["p2pkitOutcome"] == POSITIVE
    expected = {"case": case, "sourceCommit": commit, "declaredSourceTree": tree,
                "outcome": terminal["p2pkitOutcome"], "targetSdk": 37}
    if case == "317":
        expected.update(schemaVersion=1, token=token)
    expected["treeBinding"] = (
        "host must verify source tree and both APK hashes; not independently readable in ART" if case == "317" else
        "outer controller must independently bind clean source and both APK hashes")
    expected["cleanupScope"] = (
        "owned Activities and observers; host must retire the owned test process" if case == "317" else
        "owned UI/fake resources; host must retire exact ART process/guest")
    for key, value in expected.items():
        if positive or key == "outcome":
            required(report, key)
        if key in report:
            need(type(report[key]) is type(value) and report[key] == value, "Report identity/outcome disagreement: " + key)
    if not positive:
        if "failure" in report and "p2pkitFailureStage" in terminal:
            need(type(report["failure"]) is dict and report["failure"].get("stage") == terminal["p2pkitFailureStage"],
                 "Failure stage disagrees with terminal")
        return
    need("failure" not in report and "failureDisplayUnavailable" not in report, "Positive report contains failure")
    integer(required(report, "api"), 35, (1 << 31) - 1)
    integer(required(report, "pid"), 1, (1 << 31) - 1)
    integer(required(report, "processStartElapsedMillis"), 1)
    if case == "317":
        integer(required(report, "uid"), 1, (1 << 31) - 1)
    abis = sequence(required(report, "abis"), 16, 1)
    need(all(type(item) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item) for item in abis) and
         len(set(abis)) == len(abis), "Invalid declared ABI list")
    bounds = required(report, "boundsMillis")
    need(type(bounds) is dict and bounds == BOUNDS[case] and all(type(value) is int for value in bounds.values()),
         "Changed in-guest bounds")


def reported_companions(snapshot, report, case):
    """Check available failed-run references too; never interpret a failure as a mutant pass."""
    if case == "317":
        for label in ("before", "after", "failed"):
            if label + "Screenshot" in report:
                shot = report[label + "Screenshot"]
                need(required(shot, "file") == label + ".png", "Wrong screenshot filename")
                png(snapshot, label + ".png", shot, "sha256")
                json_file(snapshot, label + "-tree.json")
    elif "captures" in report:
        names = set()
        for capture in sequence(report["captures"], len(CAPTURES_324) + 1):
            label = required(capture, "label")
            need(type(label) is str and label in (*CAPTURES_324, "failure") and label not in names,
                 "Unknown/duplicate reported capture")
            names.add(label)
            png(snapshot, label + ".png", capture, "pngSha256")
            sequence(json_file(snapshot, label + "-tree.json"), 1500, 1)
    if "saved-state.json" in snapshot.files:
        saved = json_file(snapshot, "saved-state.json")
        if "saved-state.parcel" not in snapshot.files:
            raise Incomplete("Missing original Parcel")
        need(snapshot.files["saved-state.parcel"] == {"bytes": required(saved, "bytes"),
                                                       "sha256": required(saved, "sha256")},
             "Parcel bytes/hash disagree with payload report")


def verify_317(snapshot, report, commit, token):
    required_files = {"result.json", "events.jsonl", "before-tree.json", "before.png", "after-tree.json", "after.png"}
    if not required_files <= set(snapshot.files):
        raise Incomplete("Missing positive #317 companion files")
    need(set(snapshot.files) == required_files, "Positive #317 file set is not exact")
    need(required(report, "cleanupFailures") == [] and required(report, "overflow") is False and
         required(report, "unexpectedActivity") is False and required(report, "observedCounts") == [1, 2] and
         required(report, "independentVisualAndMutationReview") == "REQUIRED_NOT_PERFORMED_BY_RUNNER",
         "#317 cleanup/observer/count/review claims disagree")
    need(all(type(value) is int for value in report["observedCounts"]), "Noninteger diagnostic counts")
    need(integer(required(report, "droppedBefore")) == integer(required(report, "droppedAfter")) == 0,
         "Diagnostic drops in positive #317")
    start = integer(required(required(report, "handsOffStart"), "elapsedNanos"))
    end = integer(required(required(report, "handsOffEnd"), "elapsedNanos"))
    injection = required(report, "injection")
    begin, finish = (integer(required(injection, key)) for key in ("beginElapsedNanos", "endElapsedNanos"))
    observed = integer(required(report, "renderedWitnessObservedElapsedNanos"))
    need(start < begin <= finish <= observed <= end and observed - finish <= 5_000_000_000,
         "#317 injection/render/interval ordering or five-second bound")
    need(integer(required(injection, "revisionAfter")) == integer(required(injection, "revisionBefore")) + 1,
         "#317 revision did not increment exactly once")
    before = sequence(required(report, "recorderBefore"), 5000, 1)
    after = sequence(required(report, "recorderAfter"), 5000, 1)
    need(after[:-1] == before and after[-1] == required(injection, "record"), "Not exactly one appended recorder event")
    added, baseline = after[-1], required(report, "baselineRecord")
    need(baseline in before and baseline.get("eventName") == "probe317_a" and added.get("eventName") == "probe317_b",
         "Wrong diagnostic record identity")
    for record in (baseline, added):
        need(record.get("gitCommitSha") == commit and record.get("testSessionId") == "ui317-" + token and
             record.get("testId") == "UI317" and record.get("role") == "observer", "Wrong source/session record")
    lease = required(report, "identity")
    need(lease.get("session") == "ui317-" + token and lease.get("testId") == "UI317" and
         lease.get("role") == "observer", "Wrong #317 interval identity")
    integer(required(lease, "screenWidthDp"), 900)
    integer(required(lease, "screenHeightDp"), 1500)
    for name, count in (("lifecycle", "lifecycleCount"), ("inputs", "inputCount"), ("windowEvents", "windowCount"),
                        ("actions", "actionCount")):
        # The accessibility and window callbacks can append on different threads;
        # their list order is not a guaranteed clock order. Inspect every timestamp.
        times = [integer(required(row, "elapsedNanos")) for row in sequence(required(report, name), 1024)]
        need(not any(start <= value <= end for value in times), "Input/lifecycle/window/action inside hands-off interval")
        need(sum(value < start for value in times) == integer(required(lease, count)), "#317 frozen observer count mismatch")
    frames = sequence(required(report, "frames"), 2, 2)
    need([required(value, "label") for value in frames] == ["setup-render", "event-only"], "Wrong #317 frames")
    setup_commit, event_commit = (frame(value, "317") for value in frames)
    need(finish <= frames[1]["armedElapsedNanos"] <= event_commit <= observed,
         "#317 frame is not the post-injection witness")
    for label, records in (("before", [baseline]), ("after", [baseline, added])):
        shot = required(report, label + "Screenshot")
        need(required(shot, "file") == label + ".png", "Wrong screenshot filename")
        png(snapshot, label + ".png", shot, "sha256")
        targets = sequence(required(shot, "targets"), len(records) + 1, len(records) + 1)
        for target in targets:
            sequence(target, 4, 4)
            left, top, right, bottom = (integer(value) for value in target)
            need(left < right <= shot["width"] and top < bottom <= shot["height"] and
                 2 <= (right - left) * (bottom - top) <= 1_048_576, "Contradictory screenshot target bounds")
        capture_begin = integer(required(shot, "beginElapsedNanos"))
        capture_end = integer(required(shot, "endElapsedNanos"))
        need(capture_begin <= capture_end, "Reversed screenshot timestamps")
        need(setup_commit <= capture_begin <= capture_end < start if label == "before" else
             observed <= capture_begin <= capture_end <= end, "Screenshot/interval ordering mismatch")
        tree = json_file(snapshot, label + "-tree.json")
        nodes = sequence(required(tree, "nodes"), 1500, 1)
        texts = [node.get("text") for node in nodes if type(node) is dict and node.get("visible") is True]
        need(texts.count(f"{len(records)} event(s); tap rows to select") == 1 and texts.count("Pause live logs") == 1,
             "Missing/ambiguous diagnostic count/live text")
        for record in records:
            title = f"{required(record, 'timestamp')} {required(record, 'severity')} {record['eventName']}"
            need(sum(value in (title, title + "\nLOCAL") for value in texts) == 1, "Missing/ambiguous diagnostic row")
    need(report["beforeScreenshot"]["sha256"] != report["afterScreenshot"]["sha256"], "Unchanged before/after screenshot")
    events = json_lines(snapshot.content["events.jsonl"])
    # diagnosticEvents() observes every retained session, whereas jsonLines()
    # exports only the active session. Prior setup records need not be exported.
    active = [record for record in after if record.get("testSessionId") == "ui317-" + token]
    need(all(record.get("testSessionId") == "ui317-" + token for record in events) and
         events[:len(active)] == active, "Retained diagnostics lost/changed the observed active-session prefix")


def verify_324(snapshot, report, token):
    need(required(report, "lifecycleViolation") is False and required(report, "permissionModel") ==
         "fakegrant; no OS permission or network acceptance", "#324 lifecycle/model scope disagreement")
    cells = sequence(required(report, "cells"), len(CELLS_324), len(CELLS_324))
    need(cells == [{"cell": name, "outcome": "OBSERVED_PENDING_REVIEW"} for name in CELLS_324],
         "Missing/reordered/changed #324 cells")
    need(required(report, "cleanup") == [{"step": name, "outcome": "RETIRED"} for name in CLEANUP_324],
         "Missing/failed/changed #324 cleanup")
    # The exercised diagnostic sink appends under a retained empty coordination
    # file. Positive content admission needs that active log and complete fixture.
    required_files = {"result.json", "events.jsonl", "saved-state.parcel", "saved-state.json",
                      FIXTURE_ACTIVE_324, FIXTURE_LOCK_324} | {
        name + suffix for name in CAPTURES_324 for suffix in (".png", "-tree.json")}
    if not required_files <= set(snapshot.files):
        raise Incomplete("Missing positive #324 companion files")
    need(all(name in required_files or FIXTURE_LOG.fullmatch(name) for name in snapshot.files),
         "Unexpected positive #324 files")
    if not DIRECTORIES_324 <= set(snapshot.directories):
        raise Incomplete("Missing positive #324 owned fixture directories")
    frames = sequence(required(report, "frames"), 200, 1)
    frame_map = {}
    for value in frames:
        frame(value, "324")
        need(value["label"] not in frame_map, "Duplicate #324 frame label")
        frame_map[value["label"]] = value
    captures = sequence(required(report, "captures"), len(CAPTURES_324), len(CAPTURES_324))
    need([required(value, "label") for value in captures] == list(CAPTURES_324), "Missing/reordered #324 captures")
    ordered_times(captures, "elapsedNanos", len(CAPTURES_324))
    capture_map = {value["label"]: value for value in captures}
    secret, ssid = "Ui324-" + token[-10:], "ui324-" + token[:8]
    for capture in captures:
        label = capture["label"]
        png(snapshot, label + ".png", capture, "pngSha256")
        sequence(json_file(snapshot, label + "-tree.json"), 1500, 1)
        target_count = 0 if label in ("disposal-of-original-owner", "final-card-disposal") else 1
        for target in sequence(required(capture, "targets"), target_count, target_count):
            need(type(target) is str, "Invalid #324 screenshot target")
            match = re.fullmatch(r"\[([0-9]{1,10}),([0-9]{1,10})\]\[([0-9]{1,10}),([0-9]{1,10})\]", target)
            need(match is not None, "Invalid #324 screenshot target rectangle")
            left, top, right, bottom = (int(value) for value in match.groups())
            need(left < right <= capture["width"] and top < bottom <= capture["height"] and
                 2 <= (right - left) * (bottom - top) <= 1_048_576, "Contradictory #324 screenshot target bounds")
        witness = required(capture, "frame")
        committed = frame(witness, "324")
        need(frame_map.get(witness["label"]) == witness and committed <= capture["elapsedNanos"],
             "Capture/final frame claims disagree")
        if label in STATUS_CAPTURES_324:
            continue
        text, password, length = (ssid, False, len(ssid)) if label == "restored-ssid" else (
            ("", True, 0) if label in EMPTY_324 else
            (secret, False, len(secret)) if label in REVEALED_324 else ("\u2022" * len(secret), True, len(secret)))
        need(capture.get("layoutText") == text and capture.get("password") is password and
             type(capture.get("inputLength")) is int and capture["inputLength"] == length and
             type(capture.get("drawnLength")) is int and capture["drawnLength"] == len(text) and
             capture.get("layoutSha256") == digest(text.encode("utf-8")) and capture.get("oracle") ==
             "actual GetTextLayoutResult; raw InputText is not a pixel-exposure assertion",
             "#324 layout/input/mask claim disagreement")
    expiry = required(report, "revealExpiry")
    begin = integer(required(expiry, "showBeginElapsedNanos"))
    last = integer(required(expiry, "lastRevealedObservedElapsedNanos"))
    concealed = integer(required(expiry, "concealedObservedElapsedNanos"))
    expiry_start = capture_map["expiry-start"]["elapsedNanos"]
    expired_mask = capture_map["expired-mask"]["elapsedNanos"]
    # The runner leaves last=0 when no loop poll observed the revealed state.
    # Preserve that absence; it is not an independently witnessed reveal duration.
    need(begin <= expiry_start <= concealed <= expired_mask and (last == 0 or expiry_start <= last <= concealed),
         "#324 expiry observations disagree with capture order")
    need(begin + 15_000_000_000 <= concealed <= begin + 17_000_000_000 and
         required(expiry, "unchangedInputAndLifecycle") is True and
         capture_map["expired-mask"]["frame"]["committedElapsedNanos"] >= begin + 15_000_000_000,
         "#324 expiry claim violates fixed real-time bounds")
    actions = sequence(required(report, "actions"), 100, 1)
    ordered_times(actions, "beginElapsedNanos", 100)
    need(all(action.get("success") is True and integer(required(action, "endElapsedNanos")) >=
             action["beginElapsedNanos"] for action in actions), "Failed/reversed UI action")
    need(all(left["endElapsedNanos"] <= right["beginElapsedNanos"] for left, right in zip(actions, actions[1:])),
         "Overlapping serialized UI actions")
    need(any(action.get("label") == "Show" and action["beginElapsedNanos"] == begin for action in actions),
         "Expiry is not bound to an explicit Show action claim")
    lifecycle_times = ordered_times(required(report, "lifecycle"), "elapsedNanos", 100)
    need(not any(begin < value < concealed for value in lifecycle_times), "Lifecycle transition during expiry")
    need(not any(begin < action["beginElapsedNanos"] < concealed for action in actions), "UI action during expiry")
    sequence(required(report, "compositionObservations"), 2000, 1)  # Two actual mounts, each bounded to1000.
    saved = json_file(snapshot, "saved-state.json")
    need(snapshot.files["saved-state.parcel"] == {"bytes": required(saved, "bytes"), "sha256": required(saved, "sha256")},
         "Parcel bytes/hash disagree with decoded-payload report")
    integer(saved["bytes"], 1, PARCEL_LIMIT)
    keys = sequence(required(saved, "keys"), 1024, 1)
    need(all(type(key) is str for key in keys) and len(set(keys)) == len(keys) and
         integer(required(saved, "entryCount"), 1, 1024) == len(keys), "Incomplete/ambiguous saved keys")
    payload_types = sequence(required(saved, "payloadTypes"), 1024, 1)
    need(all(type(value) is str and 0 < len(value) <= 512 for value in payload_types), "Invalid payload-type claims")
    need(required(saved, "fullyInspected") is True and required(saved, "ssidPresent") is True and
         required(saved, "secretPresent") is False, "Saved-payload inspection/positive control/secret claim failed")
    save_begin, decoded = (integer(required(saved, key)) for key in ("beginElapsedNanos", "decodedElapsedNanos"))
    need(capture_map["before-save-revealed"]["elapsedNanos"] <= save_begin <= decoded <=
         capture_map["disposal-of-original-owner"]["elapsedNanos"] <=
         capture_map["restored-empty-secret"]["elapsedNanos"], "Parcel was not the claimed pre-clear save")
    trace = sequence(required(report, "permissionTrace"), 6, 6)
    ordered_times(trace, "elapsedNanos", 6)
    for index, granted in enumerate((True, False, True)):
        request, answer = trace[2 * index:2 * index + 2]
        need(request.get("kind") == "fakegrant-request" and answer.get("kind") == "fakegrant-result" and
             integer(required(request, "requestCode")) == integer(required(answer, "requestCode")) and
             answer.get("granted") is granted, "Modeled permission trace disagreement")
    calls = sequence(required(report, "provisioningCalls"), 3, 3)
    for call, mode, returned, signals in zip(calls, ("JOINED", "JOINED_THEN_FAILED", "FAILED_ONLY"),
                                            ("Joined", "Joined", "Failed"),
                                            (["NetworkJoined"], ["NetworkJoined", "JoinFailed"], ["JoinFailed"])):
        need(call.get("mode") == mode and call.get("returned") == returned and call.get("signals") == signals and
             all(call.get(key) is True for key in ("protected", "ssidMatches", "secretMatches")),
             "Extra/replayed/incorrect modeled provisioning call")


def json_lines(raw):
    need(raw and raw.endswith(b"\n"), "Empty/incomplete JSONL")
    rows = [strict_json(line) for line in raw.splitlines()]
    sequence(rows, 5000, 1)
    need(all(type(row) is dict and type(row.get("schemaVersion")) is int and row["schemaVersion"] == 1
             for row in rows), "Unknown/nonobject diagnostic JSONL schema")
    return rows


def verify(evidence_dir, stdout_path, case, token, commit, tree):
    """Read originals only. A supplied identity is never upgraded to provenance."""
    result = {"schemaVersion": 1, "contentStatus": "REJECTED", "harnessOutcome": "UNPROVEN",
              "case": case, "declaredExpectations": {"token": token, "sourceCommit": commit, "sourceTree": tree},
              "provenance": "UNPROVEN", "runtimeAcceptance": "NOT_ACCEPTED",
              "visualReview": "NOT_PERFORMED", "mutationReview": "NOT_PERFORMED",
              "limitation": "Byte/claim consistency only; no collector, install, source, EOF/exit, ART or guest admission.",
              "files": [], "directories": [], "errors": []}
    snapshot = None
    try:
        need(case in TESTS and all(type(value) is str and re.fullmatch(pattern, value) for pattern, value in (
            (r"[0-9a-f]{32}", token), (r"[0-9a-f]{40}", commit), (r"[0-9a-f]{40}", tree))),
             "Invalid declared expectations")
        root = Path(evidence_dir).absolute()
        need(root.name == f"ui-{case}-{token}", "Retained directory does not match case/token")
        snapshot = Snapshot(case)
        stdout_binding, raw, _ = snapshot.read(Path(stdout_path), STREAM_LIMIT)
        result["instrumentationStdout"] = stdout_binding
        terminal = parse_terminal(raw, case, token)
        result["harnessOutcome"] = terminal["p2pkitOutcome"]
        snapshot.directory(root)
        if case == "324" and FIXTURE_LOCK_324 not in snapshot.files and any(
                FIXTURE_LOG.fullmatch(name) and name != FIXTURE_LOCK_324 for name in snapshot.files):
            # Even a failed retained generation was written under this companion.
            # Early failures without any generation need not have created it.
            raise Incomplete("Missing retained #324 diagnostic coordination lock")
        # Check syntax of every retained text companion, not just the result.
        for name, contents in snapshot.content.items():
            if name.endswith(".json"):
                strict_json(contents)
            elif re.search(r"\.jsonl(?:\.[1-3])?$", name):
                # An early failed body can legitimately retain an empty recorder
                # export. This is no positive evidence and never a mutant pass.
                if not contents and terminal["p2pkitOutcome"] == "FAIL":
                    continue
                rows = json_lines(contents)
                need(all(row.get("gitCommitSha") == commit for row in rows), "Wrong declared diagnostic source")
        report = json_file(snapshot, "result.json")
        common_report(report, terminal, case, token, commit, tree)
        reported_companions(snapshot, report, case)
        if terminal["p2pkitOutcome"] == POSITIVE:
            (verify_317(snapshot, report, commit, token) if case == "317" else verify_324(snapshot, report, token))
            result["contentStatus"] = "CONSISTENT"
        else:
            result["contentStatus"] = "HARNESS_FAILED"
    except Incomplete as error:
        result["contentStatus"] = "INCOMPLETE"
        result["errors"].append(str(error))
    except (Rejected, OSError, KeyError, TypeError, AttributeError, OverflowError, RecursionError) as error:
        result["contentStatus"] = "REJECTED"
        # Avoid serializing file contents or arbitrary platform exception messages.
        result["errors"].append(str(error) if isinstance(error, Rejected) else "Input read/shape failure: " + type(error).__name__)
    finally:
        if snapshot is not None:
            try:
                snapshot.unchanged()
            except (Rejected, OSError) as error:
                result["contentStatus"] = "REJECTED"
                result["errors"].append(str(error) if isinstance(error, Rejected) else "Input disappeared during verification")
            result["files"] = [{"path": path, **binding} for path, binding in sorted(snapshot.files.items())]
            result["directories"] = sorted(snapshot.directories)
            result["totalFileBytes"] = snapshot.total
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=tuple(TESTS))
    parser.add_argument("--token", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--instrumentation-stdout", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.evidence_dir, args.instrumentation_stdout, args.case, args.token,
                    args.source_commit, args.source_tree)
    print(json.dumps(result, sort_keys=True, indent=2))
    return {"CONSISTENT": 0, "HARNESS_FAILED": 1, "INCOMPLETE": 2, "REJECTED": 3}[result["contentStatus"]]


if __name__ == "__main__":
    raise SystemExit(main())
