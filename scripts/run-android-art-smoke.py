#!/usr/bin/env python3
"""One APK; sequential API37 permission/lifecycle and API37/24/25 repeated-export smokes.

Run only beneath run-audit-command.py's Linux ownership scope. It owns every helper,
including emulator/adb descendants, and performs the same-home Gradle stop on all exits.
Each AVD has a nested command scope; terminal ownership admission precedes the next.
The separate finalize mode runs only after that scope has returned its terminal receipt.
This includes one API37 instrumentation case, not physical or independent-peer qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dev.p2pkit.sample.android"
TEST_PACKAGE = PACKAGE + ".test"
INSTRUMENTATION = PACKAGE + ".runtime.LanPermissionRuntimeInstrumentation"
PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK"
IMAGE = "system-images;android-37.0;google_apis;x86_64"
IMAGE_PIN = (6, 0, 0, 2234615040, "629e507fd5b737c2c836b12b52c81cd0e3b12399", "x86_64-37.0_r06.zip")
EMULATOR_PIN = (37, 1, 11, 334378080, "1b1f78891abf8ec268264356e1365c25519e8379", "emulator-linux_x64-15917651.zip")
IMAGES = {37: IMAGE, 24: "system-images;android-24;default;x86_64", 25: "system-images;android-25;default;x86_64"}
PINS = {IMAGE: IMAGE_PIN, "emulator": EMULATOR_PIN,
        IMAGES[24]: (8, 0, 0, 419261998, "f6559e1949a5879f31a9662f4f0e50ad60181684", "x86_64-24_r08.zip"),
        IMAGES[25]: (1, 0, 0, 422702097, "7093d7b39216020226ff430a3b7b81c94d31ad37", "x86_64-25_r01.zip")}
CACHE_ROOTS = (".gradle", ".kotlin", "buildSrc/.gradle", "buildSrc/.kotlin")
MISSING = "LAN access is missing. Grant access, then tap the intended action again."
AVAILABLE = "LAN access is available. Tap the intended action again."
LIMIT = 8 * 1024 * 1024
ZIP_LIMIT = 4 * 1024 * 1024
EXPORT_DIRECTORY = "cache/test-evidence"


def instrumentation_result(raw, token, fingerprint):
    """Require a completed, source-specific test, never adb exit zero or a crash's partial output."""
    result, pending, frames, codes = {}, {}, [], []
    for line in raw.decode("utf-8", errors="strict").splitlines():
        if line.startswith("INSTRUMENTATION_STATUS: ") or line.startswith("INSTRUMENTATION_RESULT: "):
            prefix, field = line.split(": ", 1)
            key, separator, value = field.partition("=")
            need(separator and key, "Malformed instrumentation field")
            target = pending if prefix == "INSTRUMENTATION_STATUS" else result
            need(key not in target, "Duplicate instrumentation field")
            target[key] = value
        elif line.startswith("INSTRUMENTATION_STATUS_CODE: "):
            frames.append((int(line.split(": ", 1)[1]), pending))
            pending = {}
        elif line.startswith("INSTRUMENTATION_CODE: "):
            codes.append(int(line.split(": ", 1)[1]))
    need(not pending and codes == [-1] and len(frames) == 10 and
         [code for code, _ in frames] == [1] + [2] * 8 + [0], "Incomplete/failed instrumentation case")
    for _, fields in frames:
        need(fields.get("class") == INSTRUMENTATION and fields.get("test") == "permissionRecreationAndPinnedTcp" and
             fields.get("numtests") == fields.get("current") == "1" and fields.get("p2pkitToken") == token,
             "Wrong instrumentation test identity/count")
    phases = [fields.get("p2pkitPhase") for _, fields in frames[1:-1]]
    need(phases == ["default-manager-denied", "raw-denied", "request-outstanding", "recreated-still-outstanding",
                    "same-manager-granted-no-replay", "raw-granted", "message-sent", "bidirectional-delivery"],
         "Missing/out-of-order real runtime phases")
    expected = {"p2pkitToken": token, "p2pkitOutcome": "PASS", "p2pkitCompleted": "1",
                "p2pkitRecreation": "PASS", "p2pkitRequestSettled": "true",
                "p2pkitManager": "PASS", "p2pkitTraffic": "PASS",
                "p2pkitCleanup": "PASS", "p2pkitRawPregrant": "DENIED", "p2pkitRawRoute": "DENIED_THEN_ADMITTED",
                "p2pkitSameInstanceRevocation": "NOT_EXECUTED", "p2pkitRetainedVm": "true",
                "p2pkitActivities": "2", "p2pkitDestroyed": "1", "p2pkitPeerFingerprint": fingerprint,
                "p2pkitSentBytes": str(len("android-" + token)), "p2pkitReceivedBytes": str(len("jvm-" + token))}
    need(all(result.get(key) == value for key, value in expected.items()), "Runtime witness did not pass every scope")
    need(result.get("p2pkitRawDenialType") in ("TCP_TIMEOUT", "PERMISSION_ERRNO") and
         re.fullmatch(r"anon-[0-9a-f]{16}", result.get("p2pkitLocalAlias", "")) and
         all(result.get(key, "").isdigit() and int(result[key]) > 0 for key in
             ("p2pkitPid", "p2pkitProcessStart", "p2pkitUid", "p2pkitNetwork")), "Missing process/route/delivery identity")
    need(all(frames[-1][1].get(key) == value for key, value in result.items()), "Terminal status/result mismatch")
    return result


def runtime_host_result(lines, alias, control, output_eof, unresolved_clients):
    """Admit only final drained CLI output and settled controls, never a pre-quit snapshot."""
    incoming = [line for line in lines if line.startswith("incoming from ")]
    outgoing = [line for line in lines if line.startswith("sending ")]
    problems = [line for line in lines if re.search(
        r"\[p2pkit (?:W|WARN|E|ERROR)\]|CLI failed:|Exception in thread|"
        r"^kit\.stop\(\) failed:|^send to anon-[0-9a-f]{16} failed:", line)]
    passed = (output_eof and alias is not None and not problems and
              incoming == [f"incoming from {alias}: <text 40B>"] and
              outgoing == ["sending <text 36B> to 1 peer(s) (local send, not remote processing)"] and
              control["controlAccepts"] == control["controlChallenges"] == 1 and
              control["controlEmptyConnections"] == unresolved_clients == 0)
    return {"status": "PASS" if passed else "FAIL", "outputEof": output_eof,
            "cliIncomingReceipts": incoming, "cliOutgoingReceipts": outgoing,
            "cliProblems": problems, "unresolvedControlClients": unresolved_clients}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def load_runner():
    spec = importlib.util.spec_from_file_location("android_art_executor", ROOT / "scripts/run-audit-command.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def tag(node):
    return node.tag.rsplit("}", 1)[-1]


def xml(raw):
    need(0 < len(raw) <= LIMIT and b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(),
         "Invalid/oversized XML evidence")
    return ET.fromstring(raw)


def package_pin(raw, package):
    """Admit only the reviewed stable artifact, independent of unrelated manifest changes."""
    need(package in PINS, "Unreviewed SDK package")
    wanted = PINS[package]
    entries = [p for p in xml(raw) if tag(p) == "remotePackage" and p.get("path") == package
               and p.find("channelRef") is not None and p.find("channelRef").get("ref") == "channel-0"]
    need(len(entries) == 1, "Missing/ambiguous stable SDK package")
    entry = entries[0]
    revision = tuple(int(entry.findtext("revision/" + field, "0")) for field in ("major", "minor", "micro"))
    need(revision == wanted[:3], "SDK package revision changed; review new bytes before another run")
    archives = [a for a in entry.findall("archives/archive")
                if a.findtext("host-os") in (None, "linux") and a.findtext("host-arch") in (None, "x64")]
    need(len(archives) == 1, "Ambiguous Linux SDK archive")
    complete = archives[0].find("complete")
    checksum = complete.find("checksum")
    actual = (int(complete.findtext("size")), checksum.text, complete.findtext("url"))
    need(checksum.get("type") == "sha1" and actual == wanted[3:], "SDK archive pin changed")
    if package == IMAGE:
        need(entry.findtext("type-details/api-level") == "37.0" and
             entry.findtext("type-details/extension-level") == "22" and
             entry.findtext("type-details/abi") == "x86_64", "Not the selected API37.0 extension22 x86_64 image")
        dependency = entry.find("dependencies/dependency[@path='emulator']/min-revision")
        need(dependency is not None and tuple(int(dependency.findtext(k, "0")) for k in
             ("major", "minor", "micro")) == (36, 5, 11), "Image emulator prerequisite changed")
    elif package in (IMAGES[24], IMAGES[25]):
        api = next(api for api, image in IMAGES.items() if image == package)
        need(entry.findtext("type-details/api-level") == str(api) and
             entry.findtext("type-details/abi") == "x86_64" and
             entry.findtext("type-details/tag/id") == "default" and
             entry.find("type-details/extension-level") is None,
             "Not the selected old-API default x86_64 image")
        need(entry.find("dependencies/dependency[@path='emulator']") is None,
             "Old-image emulator prerequisite changed; absence is not boot compatibility proof")
    return {"package": package, "revision": revision, "archiveBytes": actual[0],
            "publisherSha1": actual[1], "archiveName": actual[2], "manifestSha256": hashlib.sha256(raw).hexdigest(),
            "archiveSha256": None, "archiveHashScope": "SDK Manager download; no separately computed archive SHA256"}


def grant_from_dump(text, permission):
    users = re.findall(r"(?ms)^\s*User 0:.*?(?=^\s*User [1-9][0-9]*:|\Z)", text)
    need(len(users) == 1, "Missing/ambiguous installed User0 package state")
    grants = re.findall(r"(?m)^\s*" + re.escape(permission) + r": granted=(true|false)(?:,|\s|$)", users[0])
    need(len(grants) == 1, "Missing/ambiguous live runtime grant")
    return grants[0] == "true"


def ui_nodes(raw):
    root = xml(raw)
    need(tag(root) == "hierarchy", "UI dump has no hierarchy")
    nodes = list(root.iter("node"))
    need(len(nodes) <= 3000, "UI node bound exceeded")
    return root, nodes


def select_node(raw, label, system=False):
    root, nodes = ui_nodes(raw)
    matches = []
    for node in nodes:
        package = node.get("package", "")
        if system:
            allowed = package in ("com.android.permissioncontroller", "com.google.android.permissioncontroller")
            matched = node.get("resource-id", "") == package + ":id/" + label
        else:
            allowed = package == PACKAGE
            matched = node.get("text") == label or node.get("content-desc") == label
        if allowed and matched:
            matches.append(node)
    need(matches, "Missing visible UI control: " + label)
    need(len(matches) == 1, "Ambiguous visible UI control: " + label)
    node = matches[0]
    parents = {child: parent for parent in root.iter() for child in parent}
    current = node
    while current is not None and current.get("clickable") != "true":
        need(current.get("package") == node.get("package") and current.get("enabled", "true") == "true",
             "Disabled/foreign UI control: " + label)
        current = parents.get(current)
    need(current is not None and current.get("package") == node.get("package") and
         current.get("enabled") == "true", "Control has no enabled app/system click owner")
    x1, y1, x2, y2 = node_bounds(node)
    return [(x1 + x2) // 2, (y1 + y2) // 2]


def node_bounds(node):
    bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    need(bounds is not None, "Malformed UI bounds")
    x1, y1, x2, y2 = map(int, bounds.groups())
    need(0 <= x1 < x2 <= 4096 and 0 <= y1 < y2 <= 4096, "Invalid/offscreen UI control bounds")
    return x1, y1, x2, y2


def scroll_points(raw):
    areas = [node_bounds(n) for n in ui_nodes(raw)[1] if n.get("package") == PACKAGE and
             n.get("scrollable") == n.get("enabled") == "true"]
    need(areas, "No app-owned scroll container")
    areas.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    need(len(areas) == 1 or (areas[0][2] - areas[0][0]) * (areas[0][3] - areas[0][1]) >
         (areas[1][2] - areas[1][0]) * (areas[1][3] - areas[1][1]), "Ambiguous app scroll container")
    x1, y1, x2, y2 = areas[0]
    need(y2 - y1 >= 80, "App viewport too small to scroll safely")
    x = (x1 + x2) // 2
    return [x, y1 + (y2 - y1) * 3 // 4, x, y1 + (y2 - y1) // 4, 250]


def has_text(raw, text):
    return any(n.get("package") == PACKAGE and n.get("text") == text for n in ui_nodes(raw)[1])


def foreground_chooser(text):
    components = set(re.findall(r"\b(?:mResumedActivity|topResumedActivity)[=:]\s*ActivityRecord\{[^}\r\n]*"
                                r"\bu0\s+([A-Za-z0-9_.$/]+)\s+t\d+", text))
    need(len(components) <= 1, "Ambiguous foreground activity")
    if not components:
        return None
    component = components.pop()
    for owner in ("android", "com.android.intentresolver", "com.google.android.intentresolver"):
        activity = "com.android.internal.app.ChooserActivity" if owner == "android" else owner + ".ChooserActivity"
        if component in (owner + "/" + activity, owner + "/.ChooserActivity"):
            return owner
    return None


def diagnostic_time(value):
    need(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", value),
         "Missing/non-UTC diagnostic timestamp")
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    need(parsed > datetime(1970, 1, 1, tzinfo=timezone.utc), "Epoch/uninitialized diagnostic clock")
    return parsed


def checked_session(events, commit, api, session):
    selected = [e for e in events if e.get("testSessionId") == session]
    need(selected, "Missing active export-session records")
    indexes = [e.get("index") for e in selected]
    need(all(type(index) is int and index > 0 for index in indexes) and
         all(a < b for a, b in zip(indexes, indexes[1:])), "Lost/restarted/reordered diagnostic session")
    for event in selected:
        need(event.get("schemaVersion") == 1 and event.get("gitCommitSha") == commit and
             event.get("platform") == "android" and
             re.fullmatch(r"Android .+ \(API " + str(api) + r"\)", event.get("operatingSystem", "")) and
             event.get("testId") == "PS-T04" and event.get("role") == "both", "Wrong export source/API/session context")
        diagnostic_time(event.get("timestamp"))
        need(event.get("severity") in ("DEBUG", "INFO") and event.get("eventName") != "test.session.completed",
             "Unexpected diagnostic failure or fabricated catalog completion")
    need(selected[0]["eventName"] == "test.session.created" and
         sum(e["eventName"] == "test.session.created" for e in selected) == 1 and
         any(e["eventName"] == "test.mode.activated" for e in selected), "Export session was not created through the UI")
    return selected


def inspect_export(raw, name, commit, api, session):
    """Inspect bounded actual ZIP bytes without extraction; this never generates product evidence."""
    need(0 < len(raw) <= ZIP_LIMIT, "Export ZIP exceeds its byte bound")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        need(5 <= len(entries) <= 16 and len(set(names)) == len(names), "Missing/duplicate/excessive ZIP entries")
        for entry in entries:
            need(re.fullmatch(r"[A-Za-z0-9._-]{1,96}", entry.filename) and entry.filename not in (".", "..") and
                 not entry.is_dir() and stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG) and
                 not entry.flag_bits & 1 and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                 "Unsafe/nonregular/encrypted ZIP entry")
            need(0 <= entry.file_size <= 2 * 1024 * 1024, "ZIP entry inflated-byte bound")
        need(sum(entry.file_size for entry in entries) <= LIMIT, "ZIP total inflated-byte bound")
        required = {"events.jsonl", "events.txt", "summary.json", "manual-evidence-required.txt", "checksums.sha256"}
        need(required <= set(names), "Missing required ZIP evidence")
        contents = {entry.filename: archive.read(entry) for entry in entries}  # Also checks each entry's CRC.
    manifest = contents.pop("checksums.sha256")
    need(manifest.endswith(b"\n"), "Incomplete checksum manifest")
    checksums = {}
    for line in manifest.decode("ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]{1,96})", line)
        need(match is not None and match[2] not in checksums, "Malformed/duplicate checksum row")
        checksums[match[2]] = match[1]
    need(set(checksums) == set(contents) and all(hashlib.sha256(value).hexdigest() == checksums[key]
         for key, value in contents.items()), "ZIP checksum/name-set mismatch")
    stream = contents["events.jsonl"]
    need(stream.endswith(b"\n"), "Incomplete exported event stream")
    events = [json.loads(line) for line in stream.splitlines()]
    need(all(isinstance(event, dict) and event.get("testSessionId") == session for event in events), "Mixed-session ZIP")
    events = checked_session(events, commit, api, session)
    summary = json.loads(contents["summary.json"])
    for key in ("schemaVersion", "gitCommitSha", "platform", "operatingSystem", "testId", "testSessionId", "role"):
        need(summary.get(key) == events[0][key], "Summary/event context mismatch: " + key)
    need(type(summary.get("eventCount")) is int and summary["eventCount"] == len(events) and
         all(type(summary.get(key)) is int and summary[key] == 0 for key in
             ("warningCount", "errorCount", "droppedEventCount")) and summary.get("finalOutcome") is None,
         "Summary lost events, reported failures, or claims a catalog outcome")
    need(summary.get("startTimestamp") == events[0]["timestamp"] and
         summary.get("endTimestamp") == events[-1]["timestamp"], "Summary/event timestamp mismatch")
    stamp = diagnostic_time(summary["startTimestamp"]).strftime("%Y-%m-%dT%H%M%S")
    need(name == f"PS-T04_android_{stamp}_{session}.zip", "Export name changed or used an epoch timestamp fallback")
    return {"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "events": events, "summary": summary,
            "entrySha256": checksums}


def verify_repeated(first, second, live, marker_index):
    need(first["name"] == second["name"] and first["sha256"] != second["sha256"], "Export did not replace the same target")
    before, after = first["events"], second["events"]
    need(after[:len(before)] == before and live[:len(after)] == after, "Repeated export lost or changed earlier events")
    exported = lambda events: [e for e in events if e["eventName"] == "evidence.exported"]
    need(not exported(before) and len(exported(after)) == 1 and len(exported(live)) == 2,
         "Wrong export record ordering/count")
    need(exported(after)[0]["details"].get("packageSha256") == first["sha256"] and
         [e["details"].get("packageSha256") for e in exported(live)] == [first["sha256"], second["sha256"]],
         "Actual ZIP bytes do not match their live export records")
    need(marker_index > before[-1]["index"] and
         any(e["index"] == marker_index and e["eventName"] == "application.foregrounded" for e in after),
         "Second export lacks the new real foreground event")


OLD_API_JMDNS_STATES = (("discovery.started", "advertising"), ("discovery.started", "discovering"),
                       ("application.shutdown", "stopping"), ("discovery.stopped", "stopping"))


def old_api_jmdns_transitions(events):
    names = {name for name, _ in OLD_API_JMDNS_STATES}
    return [event for event in events if event.get("eventName") in names]


def old_api_stop_returned(raw):
    labels = {node.get(field) for node in ui_nodes(raw)[1] if node.get("package") == PACKAGE
              for field in ("text", "content-desc")}
    need("Retry cleanup" not in labels, "JmDNS Stop failed; cleanup ownership is retained")
    if labels & {"Starting…", "Stopping previous run…", "Stopping…", "state: Running", "Kit options"}:
        return False
    try:
        select_node(raw, "Start")
    except ValueError as error:
        # A separately collected admission Flow may still disable the restored
        # label. Keep waiting, never accept its enabled Text child as the owner.
        if str(error).startswith(("Missing visible UI control:", "Disabled/foreign UI control:")) or (
                str(error) == "Control has no enabled app/system click owner"):
            return False
        raise
    return True


def verify_old_api_jmdns(observed, commit, api, session):
    """Admit actual UI/event/log observations; shutdown alone is not Stop return."""
    need(type(api) is int and api in (24, 25), "JmDNS old-API observation has the wrong API")
    keys = ("baseline", "before", "started", "beforeStop", "stopped")
    need(isinstance(observed, dict) and all(key in observed for key in
         (*keys, "runningUi", "stoppedUi", "logcat")), "Incomplete JmDNS lifecycle observations")
    snapshots = [observed[key] for key in keys]
    need(all(isinstance(events, list) and events and all(isinstance(e, dict) for e in events)
             for events in snapshots), "Missing/malformed JmDNS diagnostic observations")
    selected = [checked_session(events, commit, api, session) for events in snapshots]
    for before, after in zip(snapshots, snapshots[1:]):
        need(after[:len(before)] == before, "JmDNS lifecycle lost/replaced/reordered the full event prefix")
    need(all(e.get("gitCommitSha") == commit and e.get("severity") in ("DEBUG", "INFO")
             for e in snapshots[-1]), "Unexpected JmDNS diagnostic source/warning/error")
    fresh = snapshots[-1][len(snapshots[0]):]
    need(all(e.get("testSessionId") == session and e.get("eventName") not in
             ("application.started", "test.session.created") for e in fresh),
         "Application/session restarted during JmDNS lifecycle")
    need(not any(old_api_jmdns_transitions(events) for events in snapshots[:2]),
         "JmDNS started/stopped before the fresh Start action")
    transitions = [old_api_jmdns_transitions(events) for events in selected]
    for position, count in ((2, 2), (3, 2), (4, 4)):
        actual = tuple((e["eventName"], e.get("currentState")) for e in transitions[position])
        need(actual == OLD_API_JMDNS_STATES[:count], "Missing/repeated/reordered JmDNS lifecycle transition")
    need(transitions[2][0]["index"] > selected[1][-1]["index"] and
         transitions[4][2]["index"] > selected[3][-1]["index"], "JmDNS transition predates its UI action")
    need(has_text(observed["runningUi"], "state: Running") and has_text(observed["runningUi"], "online"),
         "JmDNS Start lacks the actual Running/online UI witness")
    need(old_api_stop_returned(observed["stoppedUi"]), "JmDNS Stop lacks an enabled restored Start")
    problems = re.findall(r"(?m)^([WEF])/([^\s(]+)\s*\(\s*\d+\):[ \t]*(.*)$", observed["logcat"])
    need(not problems, "Unexpected diagnostic/native failure during JmDNS lifecycle; inspect logcat")
    return {"runningOnlineObserved": True, "stopReturnedViaEnabledStart": True,
            "preStartIndex": selected[1][-1]["index"], "preStopIndex": selected[3][-1]["index"],
            "transitionIndexes": [e["index"] for e in transitions[4]],
            "eventCounts": [len(events) for events in snapshots]}


def old_api_jmdns_status(scenarios):
    if not isinstance(scenarios, list) or len(scenarios) != 3 or not all(
            isinstance(s, dict) and type(s.get("api")) is int for s in scenarios):
        return "FAIL"
    if [s["api"] for s in scenarios] != [37, 24, 25]:
        return "FAIL"
    expected = ("NOT_APPLICABLE", "PASS", "PASS")
    return "PASS" if all(s.get("status") == "PASS" and s.get("oldApiJmdnsLifecycle") == wanted
                         for s, wanted in zip(scenarios, expected)) else "FAIL"


class Smoke:
    def __init__(self, api=None):
        self.runner = load_runner()
        self.state, self.context = self.runner.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
        need(os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN"), "Use the existing outer audit ownership scope")
        need(platform.system() == "Linux" and platform.machine() == "x86_64", "Native Linux x64 only")
        need(api is None or api in IMAGES, "Unreviewed ART scenario")
        self.api = api
        self.sdk = self.state / "fixtures/sdk"
        self.work = self.state / "fixtures" if api is None else self.state / "fixtures" / f"api{api}"
        self.work.mkdir(mode=0o700)  # Never adopt/reuse another run's SDK/AVD or user data.
        self.evidence = self.state / "evidence" / ("android-art" if api is None else f"android-art-api{api}")
        self.evidence.mkdir(mode=0o700)
        self.counter = 0
        self.env = dict(os.environ)
        self.adb_server = self.emulator = None
        self.device_admitted = False
        self.result = {"scope": "ART/tablet viewport and one API37 instrumentation case; not physical/independent peers",
                       "api": api, "permissionLifecycle": "NOT_RUN" if api == 37 else "NOT_APPLICABLE",
                       "permissionRecreationAndPeer": "NOT_RUN" if api == 37 else "NOT_APPLICABLE",
                       "oldApiJmdnsLifecycle": "NOT_APPLICABLE" if api == 37 else "NOT_RUN",
                       "repeatedExport": "NOT_RUN", "scenarios": [],
                       "source": self.context["source"], "phases": [], "errors": [], "status": "FAIL"}

    def write(self, name, value):
        self.runner.write_new_json(self.evidence / name, value)

    def resources(self, label, disk_gib=2, ram_gib=4):
        memory = dict(re.findall(r"^(\w+):\s+(\d+) kB$", Path("/proc/meminfo").read_text(), re.M))
        available = int(memory["MemAvailable"]) * 1024
        free = shutil.disk_usage(self.work).free
        self.write("resources-" + label + ".json", {"freeDiskBytes": free, "availableRamBytes": available})
        need(free >= disk_gib * 1024 ** 3 and available >= ram_gib * 1024 ** 3, "Insufficient bounded-task disk/RAM")

    def runtime_bounds(self):
        for name in ("server_log", "emulator_log"):
            if hasattr(self, name):
                need(Path(getattr(self, name).name).stat().st_size <= LIMIT, "Background log bound: " + name)
        need(shutil.disk_usage(self.work).free >= 2 * 1024 ** 3, "Disk reserve exhausted")

    def command(self, label, args, timeout=40, check=True, input_bytes=None):
        self.counter += 1
        stem = f"{self.counter:04d}-{label}"
        record = {"argv": args, "startedUtc": self.runner.utc(), "timeoutSeconds": timeout}
        out, err = self.evidence / (stem + ".stdout.log"), self.evidence / (stem + ".stderr.log")
        try:
            with out.open("xb") as stdout, err.open("xb") as stderr:
                child = subprocess.Popen(args, cwd=ROOT, env=self.env, stdin=subprocess.PIPE if input_bytes else subprocess.DEVNULL,
                                         stdout=stdout, stderr=stderr)
                if input_bytes:
                    child.stdin.write(input_bytes)
                    child.stdin.close()
                deadline = time.monotonic() + timeout
                while child.poll() is None:
                    need(time.monotonic() < deadline, "Command deadline: " + label)
                    need(out.stat().st_size <= LIMIT and err.stat().st_size <= LIMIT, "Command log bound: " + label)
                    self.runtime_bounds()
                    time.sleep(0.2)
                record["exitCode"] = child.returncode
            need(out.stat().st_size <= LIMIT and err.stat().st_size <= LIMIT, "Command output exceeds bound")
            if check:
                need(child.returncode == 0, "Command failed: " + label)
            return out.read_bytes()
        finally:
            record["endedUtc"] = self.runner.utc()
            self.write(stem + ".json", record)
            # A timeout/failed spawn propagates. The outer identity-owned executor
            # drains any child still alive; do not run a process-name kill sweep.

    def private_environment(self):
        for name in ("android-user", "avd", "tmp", "home", "xdg-cache", "konan"):
            (self.work / name).mkdir()
        self.env.pop("ANDROID_SDK_ROOT", None)
        self.env.update(ANDROID_HOME=str(self.sdk), ANDROID_USER_HOME=str(self.work / "android-user"),
                        ANDROID_EMULATOR_HOME=str(self.work / "android-user"),
                        ANDROID_AVD_HOME=str(self.work / "avd"), TMPDIR=str(self.work / "tmp"),
                        HOME=str(self.work / "home"), XDG_CACHE_HOME=str(self.work / "xdg-cache"),
                        KONAN_DATA_DIR=str(self.work / "konan"))

    def admit_receipt(self, path, kind, purpose, success=True):
        receipt = self.runner.read_json(path)
        need(receipt["jobId"] == self.context["id"] and receipt["kind"] == kind and receipt["purpose"] == purpose and
             receipt["ancestorInvocationIds"] == self.env["P2PKIT_AUDIT_OWNERSHIP_CHAIN"].split(":"),
             "Wrong nested ownership receipt")
        need(re.fullmatch(r"[0-9a-f]{32}", receipt["id"]) and
             receipt == self.runner.read_json(self.state / "evidence" / receipt["id"] / "receipt.json"),
             "Missing/different terminal canonical receipt")
        need(receipt["sourceBefore"] == receipt["sourceAfter"] == self.context["source"] and
             receipt["sourceUnchanged"] is True and receipt["ownedSurvivors"] == [] and
             receipt["errors"] == [] and receipt["stopExitCode"] == 0, "Nested source/worker/Gradle stop unresolved")
        need(type(receipt["productExitCode"]) is int and receipt["productExitCode"] == receipt["finalExitCode"] and
             0 <= receipt["productExitCode"] < 255, "Nested invocation did not reach a terminal product result")
        if success:
            need(receipt["finalExitCode"] == 0, "Nested product command failed")
        return receipt

    def prepare(self):
        self.resources("initial", 20, 8)
        with open("/dev/kvm", "rb+", buffering=0):
            pass
        need(all(not (ROOT / name).exists() for name in CACHE_ROOTS), "Fresh checkout cache baseline required")
        self.write("cache-baseline.json", {"absentRoots": list(CACHE_ROOTS)})
        base = Path(self.env["ANDROID_HOME"]).resolve(strict=True)
        sdk = self.sdk
        sdk.mkdir()
        # Read the hosted installation; never install into or clean the shared SDK.
        for source, destination in ((base / "cmdline-tools/latest", sdk / "cmdline-tools/latest"),
                                    (base / "licenses", sdk / "licenses")):
            need(source.is_dir(), "Missing hosted command-line tools/previously accepted SDK licenses")
            shutil.copytree(source, destination)
        self.private_environment()
        for label, url, packages in (
                ("google-images", "https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-4.xml", [IMAGE]),
                ("aosp-images", "https://dl.google.com/android/repository/sys-img/android/sys-img2-4.xml", [IMAGES[24], IMAGES[25]]),
                ("emulator", "https://dl.google.com/android/repository/repository2-3.xml", ["emulator"])):
            with urllib.request.urlopen(url, timeout=30) as response:
                need(response.status == 200 and response.url == url, "SDK metadata redirect/failure")
                raw = response.read(LIMIT + 1)
                (self.evidence / (label + "-repository.xml")).write_bytes(raw)
                self.write(label + "-pins.json", {"packages": [package_pin(raw, package) for package in packages],
                           "url": url, "headers": dict(response.headers), "observedUtc": self.runner.utc()})
        self.command("sdk-install", [str(sdk / "cmdline-tools/latest/bin/sdkmanager"), "--channel=0", "--sdk_root=" + str(sdk),
                                     "platforms;android-36", "platforms;android-37.0", "platform-tools", "emulator",
                                     *IMAGES.values()], 1200)
        installed = [(f"image{api}", sdk.joinpath(*package.split(";")), str(PINS[package][0]))
                     for api, package in IMAGES.items()] + [("emulator", sdk / "emulator", "37.1.11")]
        for label, directory, revision in installed:
            props = (directory / "source.properties").read_text()
            found = re.findall(r"^Pkg.Revision\s*=\s*([^\r\n]+)", props, re.M)
            need(len(found) == 1 and found[0].strip() == revision, "Installed SDK revision does not match admitted metadata")
            self.write(label + "-installed.json", {"sourceProperties": props,
                       "sourcePropertiesSha256": hashlib.sha256(props.encode()).hexdigest()})
        self.resources("after-sdk", 8)
        self.command("sample-build", [sys.executable, str(ROOT / "scripts/run-audit-command.py"),
                     "--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew"), "--purpose", "android-art-sample-build",
                     "--timeout", "1500", "--receipt", str(self.evidence / "sample-build-receipt.json"), "--",
                     ":p2p-sample-android:assembleDebug", ":p2p-sample-android:assembleDebugAndroidTest",
                     ":p2p-sample-desktop:installDist"], 1800)
        self.admit_receipt(self.evidence / "sample-build-receipt.json", "gradle", "android-art-sample-build")
        apk = list((ROOT / "samples/p2p-sample-android/build/outputs/apk/debug").glob("*.apk"))
        need(len(apk) == 1, "Missing/ambiguous freshly built sample APK")
        self.apk = apk[0]
        self.apk_hash = self.runner.file_digest(self.apk)
        manifest = self.command("apk-manifest", [str(sdk / "cmdline-tools/latest/bin/apkanalyzer"), "manifest", "print", str(self.apk)])
        parsed = xml(manifest)
        ns = "{http://schemas.android.com/apk/res/android}"
        need(parsed.get("package") == PACKAGE and parsed.find("uses-sdk").get(ns + "minSdkVersion") == "24" and
             parsed.find("application").get(ns + "debuggable") == "true", "APK must be the normal debuggable minSdk24 sample")
        need(parsed.find("uses-sdk").get(ns + "targetSdkVersion") == "37", "APK target is not37")
        need(any(p.get(ns + "name") == PERMISSION for p in parsed.findall("uses-permission")), "APK omits local-network permission")
        self.write("apk.json", {"sha256": self.apk_hash, "bytes": self.apk.stat().st_size,
                                "relativePath": self.apk.relative_to(ROOT).as_posix(), "minSdk": 24, "targetSdk": 37,
                                "debuggable": True, "source": self.context["source"]})
        tests = list((ROOT / "samples/p2p-sample-android/build/outputs/apk/androidTest/debug").glob("*.apk"))
        need(len(tests) == 1, "Missing/ambiguous test APK")
        test = tests[0]
        test_manifest = xml(self.command("test-apk-manifest", [str(sdk / "cmdline-tools/latest/bin/apkanalyzer"),
                            "manifest", "print", str(test)]))
        instruments = test_manifest.findall("instrumentation")
        need(test_manifest.get("package") == TEST_PACKAGE and len(instruments) == 1 and
             instruments[0].get(ns + "name") == INSTRUMENTATION and
             instruments[0].get(ns + "targetPackage") == PACKAGE and
             test_manifest.find("uses-sdk").get(ns + "targetSdkVersion") == "37", "Wrong instrumentation APK")
        self.write("test-apk.json", {"source": self.context["source"], "sha256": self.runner.file_digest(test),
                   "relativePath": test.relative_to(ROOT).as_posix(), "bytes": test.stat().st_size})
        distribution = ROOT / "samples/p2p-sample-desktop/build/install/p2p-sample-desktop"
        need((distribution / "lib").is_dir(), "Missing maintained CLI distribution")
        files = []
        for path in sorted(distribution.rglob("*")):
            need(not path.is_symlink(), "CLI distribution contains a link")
            if path.is_file():
                files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": self.runner.file_digest(path)})
        need(files, "Empty CLI distribution")
        self.write("cli.json", {"source": self.context["source"], "files": files})

    def admit_prepared_apk(self):
        self.private_environment()
        prepared = self.runner.read_json(self.state / "evidence/android-art/apk.json")
        apk = list((ROOT / "samples/p2p-sample-android/build/outputs/apk/debug").glob("*.apk"))
        need(len(apk) == 1 and prepared["source"] == self.context["source"] and prepared["minSdk"] == 24 and
             prepared["targetSdk"] == 37 and prepared["debuggable"] is True, "No shared source-bound Debug APK")
        self.apk = apk[0]
        self.apk_hash = self.runner.file_digest(self.apk)
        need(self.apk.relative_to(ROOT).as_posix() == prepared["relativePath"] and self.apk_hash == prepared["sha256"] and
             self.apk.stat().st_size == prepared["bytes"], "Shared APK changed between scenarios")
        self.write("apk-admitted.json", prepared)
        props = self.sdk.joinpath(*IMAGES[self.api].split(";"), "source.properties").read_text()
        original = self.runner.read_json(self.state / "evidence/android-art" / f"image{self.api}-installed.json")
        need(hashlib.sha256(props.encode()).hexdigest() == original["sourcePropertiesSha256"], "Installed image changed")
        self.write("image-admitted.json", {"package": IMAGES[self.api], **original})

    def adb(self, label, *args, timeout=40, check=True):
        need(self.adb_server is not None and self.adb_server.poll() is None, "Owned foreground adb server exited")
        return self.command(label, [str(self.sdk / "platform-tools/adb"), "-P", str(self.adb_port),
                                   "-s", self.serial, *args], timeout, check)

    def boot(self):
        self.resources("before-boot", 5)
        self.avd_name = f"p2pkit-art-api{self.api}-" + self.context["id"][:12]
        self.ui_path = "/data/local/tmp/" + self.avd_name + ".xml"
        self.command("avd-create", [str(self.sdk / "cmdline-tools/latest/bin/avdmanager"), "create", "avd", "--name", self.avd_name,
                     "--package", IMAGES[self.api], "--device", "pixel_2", "--path", str(self.work / "avd" / (self.avd_name + ".avd"))],
                     90, input_bytes=b"no\n")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.adb_port = reservation.getsockname()[1]
        self.env.update(ANDROID_ADB_SERVER_PORT=str(self.adb_port), ADB_SERVER_SOCKET=f"tcp:127.0.0.1:{self.adb_port}")
        self.serial = "emulator-5580"
        for port in (5580, 5581):
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", port))  # Fail rather than interact with an unrelated emulator.
        self.server_log = (self.evidence / "adb-server.log").open("xb")
        self.adb_server = subprocess.Popen([str(self.sdk / "platform-tools/adb"), "-L",
                              f"tcp:127.0.0.1:{self.adb_port}", "nodaemon", "server"],
                              env=self.env, stdin=subprocess.DEVNULL, stdout=self.server_log, stderr=subprocess.STDOUT)
        time.sleep(0.5)
        devices = self.adb("initial-adb-devices", "devices").decode().splitlines()
        need(not [line for line in devices if "\t" in line], "Private adb server already has a device")
        self.emulator_log = (self.evidence / "emulator.log").open("xb")
        self.emulator = subprocess.Popen([str(self.sdk / "emulator/emulator"), "-avd", self.avd_name, "-port", "5580",
                         "-accel", "on", "-memory", "2048", "-cores", "2", "-gpu", "swiftshader", "-no-window",
                         "-skin", "1600x2560", "-dpi-device", "200", "-no-audio", "-no-boot-anim", "-no-snapshot", "-no-metrics"],
                         env=self.env, stdin=subprocess.DEVNULL, stdout=self.emulator_log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 180
        while True:
            need(self.emulator.poll() is None, "Owned emulator exited before boot")
            need(time.monotonic() < deadline, f"API{self.api} emulator boot deadline")
            if self.adb("boot-observation", "shell", "getprop", "sys.boot_completed", check=False).strip() == b"1":
                break
            time.sleep(2)
        need(self.emulator.poll() is None and
             self.adb("avd-name", "emu", "avd", "name").decode().splitlines()[0] == self.avd_name, "Wrong AVD")
        self.device_admitted = True
        need(self.adb("runtime-sdk", "shell", "getprop", "ro.build.version.sdk").strip() == str(self.api).encode(), "Wrong real ART API")
        need(self.adb("runtime-abi", "shell", "getprop", "ro.product.cpu.abi").strip() == b"x86_64", "Wrong ART ABI")
        need(self.adb("runtime-emulated", "shell", "getprop", "ro.kernel.qemu").strip() == b"1", "Not an emulator")
        self.adb("image-fingerprint", "shell", "getprop", "ro.build.fingerprint")
        self.adb("emulated-lan-routes", "shell", "ip", "route", "show", "table", "all")
        self.adb("unlock", "shell", "input", "keyevent", "KEYCODE_WAKEUP")
        if self.api == 37:
            self.adb("unlock-keyguard", "shell", "wm", "dismiss-keyguard")
        else:
            self.adb("unlock-keyguard", "shell", "input", "keyevent", "KEYCODE_MENU")
        need(self.adb("viewport-size", "shell", "wm", "size").decode().strip() == "Physical size: 1600x2560" and
             self.adb("viewport-density", "shell", "wm", "density").decode().strip() == "Physical density: 200",
             "Actual tablet viewport differs from the selected size/density")
        self.write("viewport.json", {"size": [1600, 2560], "densityDpi": 200,
                   "scope": "explicit tablet viewport; narrow-phone clipping remains unconfirmed"})
        self.adb("install", "install", str(self.apk), timeout=120)  # No -g and no pre-granted Nearby permission.
        installed = self.adb("installed-apk-path", "shell", "pm", "path", PACKAGE).decode().strip()
        need(re.fullmatch(r"package:/data/app/[^\r\n]+/base\.apk", installed), "Ambiguous installed APK")
        installed_hash = self.adb("installed-apk-hash", "shell", "sha256sum", installed.removeprefix("package:")).decode().split()[0]
        need(installed_hash == self.apk_hash, "Installed APK differs from built artifact")
        if self.api == 37:
            self.adb("reset-compat", "shell", "am", "compat", "reset-all", PACKAGE)
        self.adb("clear-logcat", "logcat", "-c")

    def dump(self):
        self.adb("remove-old-ui", "shell", "rm", "-f", self.ui_path)
        self.adb("ui-dump", "shell", "uiautomator", "dump", "--compressed", self.ui_path, timeout=20)
        return self.adb("ui-xml", "shell", "cat", self.ui_path)

    def wait_ui(self, predicate, label, seconds=20, scroll=False):
        deadline = time.monotonic() + seconds
        swipes = 0
        while True:
            raw = self.dump()
            if predicate(raw):
                return raw
            need(time.monotonic() < deadline, "UI state deadline: " + label)
            # Setup uses one verticalScroll column; the permission bottom bar
            # can put Start below the fold. Never swipe a system dialog.
            can_scroll = any(n.get("package") == PACKAGE and n.get("scrollable") == n.get("enabled") == "true"
                             for n in ui_nodes(raw)[1])
            if scroll and can_scroll and swipes < 4 and not any(has_text(raw, t) for t in
                    ("Starting…", "Stopping previous run…", "Retry cleanup")):
                self.adb("scroll-setup", "shell", "input", "swipe", *map(str, scroll_points(raw)))
                swipes += 1
            time.sleep(0.3)

    def control(self, label, system=False, scroll=False):
        # Text nodes may delegate clicks to their enabled Compose parent. Never
        # use fixed button coordinates or silently choose duplicate controls.
        def visible(raw):
            try:
                select_node(raw, label, system)
                return True
            except ValueError as error:
                if not str(error).startswith("Missing visible UI control:"):
                    raise
                return False
        return self.wait_ui(visible, label, scroll=scroll)

    def tap(self, label, system=False):
        raw = self.control(label, system, scroll=(label == "Start" and not system))
        self.adb("tap", "shell", "input", "tap", *map(str, select_node(raw, label, system)))

    def grants(self, local, initial=False):
        dump = self.adb("package-permissions", "shell", "dumpsys", "package", PACKAGE).decode()
        need(re.search(r"\btargetSdk=37\b", dump), "Installed target37 missing")
        need(grant_from_dump(dump, PERMISSION) == local, "Unexpected actual local-network grant")
        if initial:
            need(not grant_from_dump(dump, "android.permission.NEARBY_WIFI_DEVICES"), "Fresh image already grants Nearby")

    def events(self):
        # Exact safe diagnostic file only: never pull no_backup itself, Keystore
        # records, AVD userdata, adb keys, credentials or an arbitrary app tree.
        raw = self.adb("diagnostic-events", "exec-out", "run-as", PACKAGE, "cat",
                       "no_backup/test-diagnostics/diagnostic-events.jsonl")
        need(raw.endswith(b"\n") and len(raw) <= 2 * 1024 * 1024, "Incomplete/oversized diagnostic stream")
        events = [json.loads(line) for line in raw.splitlines()]
        need(events and all(e["gitCommitSha"] == self.context["expectedCommit"] for e in events), "Wrong diagnostic source")
        return events

    def wait_events(self, predicate, label, seconds=15):
        deadline = time.monotonic() + seconds
        while True:
            events = self.events()
            if predicate(events):
                return events
            need(time.monotonic() < deadline, "Diagnostic state deadline: " + label)
            time.sleep(0.3)

    def no_start(self):
        raw = self.control("Start", scroll=True)
        need(not any(n.get("content-desc") == "Kit options" for n in ui_nodes(raw)[1]), "Room started without fresh intent")
        need(not any(e["eventName"] == "discovery.started" for e in self.events()), "Discovery replayed without a fresh Start")

    def denied_start(self, count):
        self.tap("Start")
        deadline = time.monotonic() + 20
        expected = "kit startup failed; errorType=PermissionMissing"
        while True:
            logs = self.adb("denial-result", "logcat", "-d", "-v", "brief", "p2pkit:E", "*:S").decode()
            if sum(line.endswith(expected) for line in logs.splitlines()) == count:
                break
            need(time.monotonic() < deadline, "Missing typed denial after actual Start")
            time.sleep(0.3)
        self.control("Start", scroll=True)

    def phase(self, name):
        png = self.adb("screenshot-" + name, "exec-out", "screencap", "-p")
        need(png.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid screenshot evidence")
        (self.evidence / (name + ".png")).write_bytes(png)
        self.result["phases"].append(name)
        self.write("phase-" + name + ".json", {"completedUtc": self.runner.utc(), "source": self.context["source"]})
        self.resources(name)

    def exercise(self):
        self.grants(False, initial=True)
        self.adb("launch", "shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
        self.wait_ui(lambda u: has_text(u, MISSING), "initial denied status")
        self.denied_start(1)
        self.no_start()
        self.tap("Grant LAN access")
        self.tap("permission_deny_button", system=True)
        self.wait_ui(lambda u: has_text(u, MISSING), "real denial callback")
        self.grants(False)
        self.no_start()
        self.phase("denied")
        self.tap("Grant LAN access")
        self.tap("permission_allow_button", system=True)
        self.wait_ui(lambda u: has_text(u, AVAILABLE), "real grant callback")
        self.grants(True)
        self.no_start()
        self.phase("granted-no-replay")
        # A real background/foreground episode, not a synthetic ViewModel call.
        before = self.events()
        self.adb("background", "shell", "input", "keyevent", "KEYCODE_HOME")
        self.wait_events(lambda events: sum(e["eventName"] == "application.backgrounded" for e in events) >
                         sum(e["eventName"] == "application.backgrounded" for e in before), "real background callback")
        self.adb("foreground", "shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
        self.no_start()
        after = self.events()
        for name in ("application.backgrounded", "application.foregrounded"):
            need(sum(e["eventName"] == name for e in after) > sum(e["eventName"] == name for e in before),
                 "Missing actual lifecycle event: " + name)
        self.phase("foreground-no-replay")
        self.tap("Start")
        self.wait_ui(lambda u: has_text(u, "state: Running") and has_text(u, "online"),
                     "real running room and Wi-Fi/Ethernet callback", seconds=30)
        starts = [e.get("currentState") for e in self.events() if e["eventName"] == "discovery.started"]
        need(starts == ["advertising", "discovering"], "Unexpected/missing real service-start sequence")
        self.phase("started")
        self.tap("Kit options")
        self.tap("Stop kit")
        self.control("Start", scroll=True)
        need(any(e["eventName"] == "application.shutdown" for e in self.events()), "No shutdown diagnostic")
        self.phase("stopped")
        self.adb("revoke", "shell", "pm", "revoke", PACKAGE, PERMISSION)
        self.adb("launch-after-revoke", "shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
        self.wait_ui(lambda u: has_text(u, MISSING), "live denied re-entry")
        self.grants(False)
        self.denied_start(2)
        final_events = self.events()
        starts = [e.get("currentState") for e in final_events if e["eventName"] == "discovery.started"]
        need(starts == ["advertising", "discovering"], "Revocation permitted another feature start")
        need(all(e["severity"] not in ("WARNING", "ERROR") for e in final_events),
             "Unexpected structured SDK/transport warning or error")
        logs = self.adb("sample-logcat", "logcat", "-d", "-v", "brief", "p2pkit:V", "P2pKitLAN:V", "P2pKitFrame:V", "AndroidRuntime:E", "*:S").decode()
        problems = re.findall(r"(?m)^([WEF])/([^\s(]+)\s*\(\s*\d+\):[ \t]*(.*)$", logs)
        need(problems == [("E", "p2pkit", "kit startup failed; errorType=PermissionMissing")] * 2,
             "Unexpected diagnostic failure or missing typed denial; inspect retained logcat")
        self.phase("revoked")

    def export_events(self, events=None):
        return checked_session(self.events() if events is None else events,
                               self.context["expectedCommit"], self.api, self.export_session)

    def wait_chooser(self):
        def observed(raw):
            owner = foreground_chooser(self.adb("chooser-activity", "shell", "dumpsys", "activity", "activities").decode())
            return owner is not None and any(n.get("package") == owner for n in ui_nodes(raw)[1])
        self.wait_ui(observed, "actual foreground system share chooser")

    def capture_export(self, label, expected_name=None):
        def metadata(path):
            value = self.adb("export-stat", "exec-out", "run-as", PACKAGE, "stat", "-c", "%f:%s", path).decode().strip()
            match = re.fullmatch(r"([0-9a-fA-F]+):(\d+)", value)
            need(match is not None, "Export lstat is unavailable/ambiguous")
            return int(match[1], 16), int(match[2])
        need(stat.S_ISDIR(metadata(EXPORT_DIRECTORY)[0]), "Export directory is not a real owned directory")
        # Do not trust the redacted filename event detail, glob the app tree, or follow a link.
        listing = self.adb("export-directory", "exec-out", "run-as", PACKAGE, "ls", "-1a", EXPORT_DIRECTORY).decode().splitlines()
        names = [name for name in listing if name not in (".", "..")]
        need(len(names) == 1 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.zip", names[0]),
             "Export directory must contain exactly one ZIP and no staging file")
        name = names[0]
        need(expected_name is None or name == expected_name, "Second export used a different target name")
        path = EXPORT_DIRECTORY + "/" + name
        mode, size = metadata(path)
        need(stat.S_ISREG(mode) and 0 < size <= ZIP_LIMIT, "Export is not a bounded regular file")
        raw = self.adb("export-" + label + "-bytes", "exec-out", "run-as", PACKAGE, "cat", path)
        with (self.evidence / (label + ".zip")).open("xb") as output:
            output.write(raw)
        need(len(raw) == size, "Incomplete/changing installed ZIP bytes")
        verified = inspect_export(raw, name, self.context["expectedCommit"], self.api, self.export_session)
        self.write(label + "-verified.json", {key: value for key, value in verified.items() if key != "events"})
        return verified

    def repeated_export(self):
        if self.api != 37:
            self.adb("export-launch", "shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
        self.tap("Diagnostics")
        previous_sessions = {e["testSessionId"] for e in self.events()}
        self.tap("Begin test session")
        begun = self.wait_events(lambda events: any(e["eventName"] == "test.mode.activated" and
                                 e["testSessionId"] not in previous_sessions for e in events), "new real test session")
        created = [e for e in begun if e["eventName"] == "test.session.created" and e["testSessionId"] not in previous_sessions]
        need(len(created) == 1 and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", created[0]["testSessionId"]),
             "Did not observe one freshly generated diagnostic session")
        self.export_session = created[0]["testSessionId"]
        self.export_events(begun)
        self.tap("Export Test Evidence")
        self.wait_events(lambda events: any(e["eventName"] == "evidence.exported" for e in self.export_events(events)),
                         "first actual export")
        self.wait_chooser()
        first = self.capture_export("first")  # The first file stays on-device for real replacement.
        self.adb("first-chooser-back", "shell", "input", "keyevent", "KEYCODE_BACK")
        self.control("Export Test Evidence")
        before_home = self.export_events()
        self.adb("export-background", "shell", "input", "keyevent", "KEYCODE_HOME")
        backgrounded = self.wait_events(lambda events: any(e["eventName"] == "application.backgrounded" and
                                        e["index"] > before_home[-1]["index"] for e in self.export_events(events)),
                                        "new real export-session background callback")
        background = self.export_events(backgrounded)[-1]["index"]
        # Reuse the existing task/recorder; a new Activity/session cannot stand in for replacement.
        self.adb("export-foreground", "shell", "am", "start", "-W", "--activity-reorder-to-front", "-n", PACKAGE + "/.MainActivity")
        foregrounded = self.wait_events(lambda events: any(e["eventName"] == "application.foregrounded" and
                                        e["index"] > background for e in self.export_events(events)),
                                        "new real export-session foreground callback")
        after_home = self.export_events(foregrounded)
        need(after_home[:len(before_home)] == before_home, "Lifecycle re-entry replaced/lost the original recorder")
        markers = [e["index"] for e in after_home if e["eventName"] == "application.foregrounded" and e["index"] > background]
        need(len(markers) == 1, "Ambiguous real foreground marker")
        self.wait_ui(lambda raw: has_text(raw, f"test=PS-T04  session={self.export_session}  role=both"), "same active session")
        self.tap("Export Test Evidence")
        self.wait_events(lambda events: sum(e["eventName"] == "evidence.exported" for e in self.export_events(events)) >= 2,
                         "second actual export")
        self.wait_chooser()
        second = self.capture_export("second", first["name"])
        live = self.export_events()
        verify_repeated(first, second, live, markers[0])
        self.write("repeated-export.json", {"source": self.context["source"], "api": self.api,
                   "session": self.export_session, "basename": first["name"], "firstSha256": first["sha256"],
                   "secondSha256": second["sha256"], "foregroundIndex": markers[0],
                   "eventCounts": [len(first["events"]), len(second["events"]), len(live)], "status": "PASS",
                   "catalogAcceptance": False, "scope": "same-name replacement and actual ZIP checksums/events only"})
        self.adb("second-chooser-back", "shell", "input", "keyevent", "KEYCODE_BACK")
        self.control("Export Test Evidence")
        logs = self.adb("export-logcat", "logcat", "-d", "-v", "brief", "p2pkit:V", "P2pKitLAN:V", "P2pKitFrame:V", "AndroidRuntime:E", "*:S").decode()
        problems = re.findall(r"(?m)^([WEF])/([^\s(]+)\s*\(\s*\d+\):[ \t]*(.*)$", logs)
        expected = [("E", "p2pkit", "kit startup failed; errorType=PermissionMissing")] * (2 if self.api == 37 else 0)
        need(problems == expected, "Unexpected diagnostic/native failure during repeated export; inspect logcat")
        self.phase("repeated-export")

    def old_api_jmdns_lifecycle(self):
        need(self.api in (24, 25), "Only API24/25 use this JmDNS lifecycle phase")
        observed = {}
        summary = {"source": self.context["source"], "api": self.api, "apkSha256": self.apk_hash,
                   "session": self.export_session, "status": "FAIL", "catalogAcceptance": False,
                   "runningOnlineObserved": False, "stopReturnedViaEnabledStart": False,
                   "scope": "normal JmDNS start/stop; not thread-termination or physical qualification"}
        try:
            baseline = self.events()
            observed["baseline"] = baseline
            self.export_events(baseline)
            need(not old_api_jmdns_transitions(baseline), "JmDNS ran before the old-API lifecycle phase")
            self.tap("Room")  # repeated_export ends in Diagnostics, with its real session still active.
            self.control("Start", scroll=True)
            observed["before"] = self.events()
            need(observed["before"][:len(baseline)] == baseline, "Navigation replaced the original recorder")
            self.export_events(observed["before"])
            need(not old_api_jmdns_transitions(observed["before"]), "Discovery replayed before fresh Start")
            self.tap("Start")
            observed["runningUi"] = self.wait_ui(
                lambda raw: has_text(raw, "state: Running") and has_text(raw, "online"),
                "old-API JmDNS Running and online", seconds=30)
            summary["runningOnlineObserved"] = True
            observed["started"] = self.events()
            starts = old_api_jmdns_transitions(self.export_events(observed["started"]))
            need(tuple((e["eventName"], e.get("currentState")) for e in starts) == OLD_API_JMDNS_STATES[:2],
                 "Missing actual old-API advertising/discovery")
            self.phase("jmdns-started")
            observed["beforeStop"] = self.events()
            need(observed["beforeStop"][:len(observed["started"])] == observed["started"],
                 "JmDNS recorder changed before Stop")
            starts = old_api_jmdns_transitions(self.export_events(observed["beforeStop"]))
            need(tuple((e["eventName"], e.get("currentState")) for e in starts) == OLD_API_JMDNS_STATES[:2],
                 "JmDNS started/stopped again before Stop intent")
            self.tap("Kit options")
            self.tap("Stop kit")
            observed["stoppedUi"] = self.wait_ui(
                old_api_stop_returned, "old-API Stop returned with enabled Start and no cleanup retry", scroll=True)
            summary["stopReturnedViaEnabledStart"] = True
            observed["stopped"] = self.events()
            # No logcat clear: errors after good exports/start/stop must still fail.
            observed["logcat"] = self.adb(
                "old-api-jmdns-logcat", "logcat", "-d", "-v", "brief", "p2pkit:V", "P2pKitLAN:V",
                "P2pKitFrame:V", "AndroidRuntime:E", "*:S").decode()
            summary.update(verify_old_api_jmdns(
                observed, self.context["expectedCommit"], self.api, self.export_session))
            self.phase("jmdns-stopped")
            summary["status"] = "PASS"
        finally:
            self.write("old-api-jmdns-lifecycle.json", summary)

    def runtime_instrumentation(self):
        """One target-UID case and maintained JVM peer; no adb forwarding or concurrent UI dump helper."""
        self.resources("before-instrumentation")
        shared = self.state / "evidence/android-art"
        prepared = self.runner.read_json(shared / "test-apk.json")
        test_apk = ROOT / prepared["relativePath"]
        tests = list((ROOT / "samples/p2p-sample-android/build/outputs/apk/androidTest/debug").glob("*.apk"))
        need(tests == [test_apk] and not test_apk.is_symlink() and
             prepared["source"] == self.context["source"] and test_apk.stat().st_size == prepared["bytes"] and
             self.runner.file_digest(test_apk) == prepared["sha256"], "Test APK changed after the shared build")
        cli = self.runner.read_json(shared / "cli.json")
        distribution = ROOT / "samples/p2p-sample-desktop/build/install/p2p-sample-desktop"
        entries = sorted(distribution.rglob("*"))
        need(not distribution.is_symlink() and not any(path.is_symlink() for path in entries), "CLI artifact link")
        actual = [{"path": path.relative_to(ROOT).as_posix(), "sha256": self.runner.file_digest(path)}
                  for path in entries if path.is_file()]
        need(cli["source"] == self.context["source"] and actual == cli["files"], "Maintained CLI distribution changed")
        # Earlier export bytes/logs were already retained. Only this owned installed sample is reset.
        self.adb("runtime-uninstall-sample", "uninstall", PACKAGE)
        for package, apk, digest in ((PACKAGE, self.apk, self.apk_hash), (TEST_PACKAGE, test_apk, prepared["sha256"])):
            self.adb("runtime-install-" + package, "install", str(apk), timeout=120)
            installed = self.adb("runtime-package-path", "shell", "pm", "path", package).decode().strip()
            need(re.fullmatch(r"package:/data/app/[^\r\n]+/base\.apk", installed), "Ambiguous runtime installed APK")
            found = self.adb("runtime-installed-hash", "shell", "sha256sum",
                             installed.removeprefix("package:")).decode().split()[0]
            need(found == digest, "Runtime installed APK hash mismatch")
        self.grants(False, initial=True)
        self.adb("runtime-clear-logcat", "logcat", "-c")
        token = uuid.uuid4().hex
        summary = {"status": "FAIL", "token": token, "source": self.context["source"],
                   "topology": "target-UID guest10.0.2.2 to ready host-loopback listener; no adb forwarding",
                   "controlAccepts": 0, "controlEmptyConnections": 0, "controlChallenges": 0, "processes": {}}
        selector = selectors.DefaultSelector()
        listener = socket.socket()
        clients, streams, processes = {}, {}, {}
        parsed_lines = {"cli": [], "instrumentation": []}

        def spawn(label, argv):
            child = subprocess.Popen(argv, cwd=self.work, env=self.env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            processes[label] = child
            summary["processes"][label] = {"argv": argv, "pid": child.pid, "forced": False}
            os.set_blocking(child.stdout.fileno(), False)
            log = (self.evidence / ("runtime-" + label + ".log")).open("xb", buffering=0)
            streams[label] = (log, bytearray())
            selector.register(child.stdout, selectors.EVENT_READ, ("stream", label))
            return child

        def send(child, command):
            need(child.poll() is None, "Runtime child exited before its command")
            child.stdin.write((command + "\n").encode())
            child.stdin.flush()

        def pump():
            self.runtime_bounds()
            journal = self.evidence / "runtime-cli-events.jsonl"
            need(not journal.exists() or journal.stat().st_size <= LIMIT, "Runtime CLI journal bound")
            for key, _ in selector.select(0.2):
                kind, label = key.data
                if kind == "listener":
                    client, _ = listener.accept()
                    client.setblocking(False)
                    summary["controlAccepts"] += 1
                    need(summary["controlAccepts"] <= 2, "Unexpected extra raw probe connection")
                    clients[client] = bytearray()
                    selector.register(client, selectors.EVENT_READ, ("control", None))
                elif kind == "control":
                    client = key.fileobj
                    part = client.recv(128)
                    clients[client].extend(part)
                    data = bytes(clients[client])
                    need(len(data) <= 33, "Raw listener input bound")
                    if not part or data.endswith(b"\n"):
                        selector.unregister(client)
                        if not data:
                            # Preserve a bypass witness, allowing independent UI/traffic evidence to finish.
                            summary["controlEmptyConnections"] += 1
                        else:
                            need(data == (token + "\n").encode(), "Wrong raw positive-control nonce")
                            client.settimeout(2)
                            client.sendall(("ack-" + token + "\n").encode())
                            summary["controlChallenges"] += 1
                        client.close()
                        del clients[client]
                else:
                    part = os.read(key.fileobj.fileno(), 65536)
                    log, pending = streams[label]
                    if not part:
                        selector.unregister(key.fileobj)
                        need(not pending or pending == b"> ", "Unterminated runtime child output")
                        continue
                    log.write(part)
                    need(log.tell() <= LIMIT, "Runtime child log bound")
                    pending.extend(part)
                    while b"\n" in pending:
                        line, _, tail = pending.partition(b"\n")
                        pending[:] = tail
                        parsed_lines[label].append(line.decode("utf-8", errors="strict").lstrip("> ").strip())
                    need(len(pending) <= 16384, "Runtime child line bound")

        def until(predicate, seconds, label):
            deadline = time.monotonic() + seconds
            while not predicate():
                need(time.monotonic() < deadline, "Runtime deadline: " + label)
                pump()

        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(2)
            listener.setblocking(False)
            port = listener.getsockname()[1]
            summary["readyControlPort"] = port
            selector.register(listener, selectors.EVENT_READ, ("listener", None))
            java = Path(self.env["JAVA_HOME"]) / "bin/java"
            peer = spawn("cli", [str(java), "-Xmx384m", "-XX:ActiveProcessorCount=2",
                         "-Duser.home=" + str(self.work / "home"), "-Djava.io.tmpdir=" + str(self.work / "tmp"),
                         "-cp", str(distribution / "lib/*"), "dev.p2pkit.sample.desktop.MainKt",
                         "JVM ART permission peer", "p2pkit-art-" + token, "trace=off", "test=ART-372",
                         "session=" + token, "role=both", "evidence=" + str(self.work / "cli-export"),
                         "log=" + str(self.evidence / "runtime-cli-events.jsonl")])
            until(lambda: "Ready. Type 'help' for commands." in parsed_lines["cli"], 30, "maintained CLI ready")
            send(peer, "mesh off")
            send(peer, "info")
            until(lambda: "auto-mesh off" in parsed_lines["cli"] and
                  any(re.fullmatch(r"manual port\s+[0-9]+", line) for line in parsed_lines["cli"]) and
                  any(re.fullmatch(r"fingerprint\s+p2f1-[a-z2-7]{52}", line) for line in parsed_lines["cli"]),
                  10, "actual CLI endpoint and identity")
            pins = [line.split()[-1] for line in parsed_lines["cli"] if re.fullmatch(r"fingerprint\s+p2f1-[a-z2-7]{52}", line)]
            ports = [int(line.split()[-1]) for line in parsed_lines["cli"] if re.fullmatch(r"manual port\s+[0-9]+", line)]
            need(len(pins) == len(ports) == 1 and ports[0] != port and 1024 <= ports[0] <= 65535,
                 "Ambiguous CLI identity/port")
            summary.update(cliFingerprint=pins[0], cliPort=ports[0])
            argv = [str(self.sdk / "platform-tools/adb"), "-P", str(self.adb_port), "-s", self.serial,
                    "shell", "am", "instrument", "-w", "-r"]
            for name, value in (("token", token), ("host", "10.0.2.2"), ("controlPort", str(port)),
                                ("cliPort", str(ports[0])), ("fingerprint", pins[0])):
                argv.extend(["-e", name, value])
            argv.append(TEST_PACKAGE + "/" + INSTRUMENTATION)
            instrument = spawn("instrumentation", argv)
            deadline = time.monotonic() + 120
            responded = False
            while instrument.poll() is None:
                need(time.monotonic() < deadline and peer.poll() is None, "Runtime test timed out or peer exited")
                pump()
                received = [line for line in parsed_lines["cli"] if re.fullmatch(r"incoming from anon-[0-9a-f]{16}: <text 40B>", line)]
                if not responded and received and "INSTRUMENTATION_STATUS: p2pkitPhase=message-sent" in parsed_lines["instrumentation"]:
                    need(len(received) == 1, "Duplicate CLI text delivery")
                    send(peer, "send jvm-" + token)
                    responded = True
            instrument.wait()
            until(lambda: not any(key.data == ("stream", "instrumentation") for key in selector.get_map().values()),
                  3, "instrumentation output EOF")
            need(instrument.returncode == 0 and responded, "No completed instrumentation/peer exchange")
            raw = (self.evidence / "runtime-instrumentation.log").read_bytes()
            # Preserve partial/failed raw output even when the strict completed-case oracle rejects it.
            summary["instrumentationFinalFields"] = [line for line in parsed_lines["instrumentation"]
                                                     if line.startswith("INSTRUMENTATION_RESULT:")]
            witness = instrumentation_result(raw, token, pins[0])
            summary["witness"] = witness
            summary["status"] = "PASS"  # Provisional until post-quit EOF, receipts and cleanup are admitted below.
        finally:
            # Only these exact Popen handles are touched. The enclosing executor remains the descendant owner.
            peer = processes.get("cli")
            if peer is not None and peer.poll() is None:
                try:
                    send(peer, "quit")
                    until(lambda: peer.poll() is not None, 20, "graceful CLI stop")
                except Exception as error:
                    summary["peerStopError"] = type(error).__name__
                    summary["status"] = "FAIL"
            for label, child in processes.items():
                try:
                    if child.poll() is None:
                        summary["status"] = "FAIL"
                        summary["processes"][label]["forced"] = True
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=5)
                    summary["processes"][label]["exitCode"] = child.wait()
                    if child.returncode != 0:
                        summary["status"] = "FAIL"
                    until(lambda: not any(key.data == ("stream", label) for key in selector.get_map().values()),
                          3, "runtime output EOF: " + label)
                except Exception as error:
                    summary["status"] = "FAIL"
                    summary["processes"][label]["cleanupError"] = type(error).__name__
                child.stdin.close()
                child.stdout.close()
            # pump() can append receipts or accept controls during quit/drain; admit only these final values.
            host = runtime_host_result(parsed_lines["cli"], summary.get("witness", {}).get("p2pkitLocalAlias"), summary,
                                       not any(key.data[0] == "stream" for key in selector.get_map().values()), len(clients))
            summary["hostFinalAdmission"] = host
            if host["status"] != "PASS":
                summary["status"] = "FAIL"  # Never overwrite an earlier forced-exit/cleanup failure with PASS.
            for client in clients:
                client.close()
            listener.close()
            selector.close()
            for log, _ in streams.values():
                log.close()
            self.write("runtime-instrumentation.json", summary)
            self.adb("runtime-final-logcat", "logcat", "-d", "-v", "brief", "p2pkit:V", "P2pKitLAN:V", "AndroidRuntime:E", "*:S")
        need(summary["status"] == "PASS", "Runtime behavior or owned-process shutdown failed")
        self.phase("instrumentation-runtime")

    def cleanup_scenario(self, api, receipt):
        # Not global cleanup(): the enclosing manager is intentionally still active.
        # Only this exact, now terminal child fixture and its no-longer-used image
        # are retired. The canonical child receipt already proves stop/drain/source.
        paths = [self.work / f"api{api}", self.sdk.joinpath(*IMAGES[api].split(";"))]
        record = {"api": api, "receiptId": receipt["id"], "source": self.context["source"],
                  "inspections": [self.runner.inspect_disposable_tree(path) for path in paths], "removed": []}
        self.write(f"api{api}-cleanup-start.json", record)
        try:
            for path in paths:
                shutil.rmtree(path)
                need(not path.exists(), "Owned API fixture/image removal failed")
                record["removed"].append(str(path))
        finally:
            self.write(f"api{api}-cleanup-final.json", record)
        self.resources(f"after-api{api}")

    def run(self):
        try:
            self.prepare()
            for api in IMAGES:  # One APK; never overlap AVDs or rebuild between APIs.
                purpose = f"android-art-api{api}"
                path = self.evidence / f"api{api}-receipt.json"
                self.command(purpose, [sys.executable, str(ROOT / "scripts/run-audit-command.py"),
                             "--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew"), "--kind", "command",
                             "--purpose", purpose, "--timeout", "900", "--receipt", str(path), "--",
                             sys.executable, str(ROOT / "scripts/run-android-art-smoke.py"), "scenario", "--api", str(api)],
                             1200, check=False)
                receipt = self.admit_receipt(path, "command", purpose, success=False)
                scenario = self.runner.read_json(self.state / "evidence" / f"android-art-api{api}/result.json")
                need(scenario["source"] == self.context["source"] and scenario["api"] == api and
                     scenario["status"] in ("PASS", "FAIL") and
                     (scenario["status"] == "PASS") == (receipt["finalExitCode"] == 0), "Scenario result/receipt mismatch")
                self.result["scenarios"].append(scenario)
                self.cleanup_scenario(api, receipt)
                if scenario["status"] != "PASS":
                    self.result["errors"].append(f"API{api} failed; retained its result/logs and continued only after terminal cleanup")
            self.result["permissionLifecycle"] = self.result["scenarios"][0]["permissionLifecycle"]
            self.result["permissionRecreationAndPeer"] = self.result["scenarios"][0]["permissionRecreationAndPeer"]
            self.result["repeatedExport"] = "PASS" if all(s["repeatedExport"] == "PASS" for s in self.result["scenarios"]) else "FAIL"
            self.result["oldApiJmdnsLifecycle"] = old_api_jmdns_status(self.result["scenarios"])
            need(self.result["oldApiJmdnsLifecycle"] == "PASS", "API24/25 JmDNS lifecycle admission failed")
            if not self.result["errors"]:
                self.result["status"] = "PASS"
        except Exception as error:
            self.result["errors"].append(type(error).__name__ + ": " + str(error))
        finally:
            self.write("result.json", self.result)
        return 0 if self.result["status"] == "PASS" else 1

    def run_scenario(self):
        try:
            self.admit_prepared_apk()
            self.boot()
            if self.api == 37:
                self.result["permissionLifecycle"] = "RUNNING"
                self.exercise()
                self.result["permissionLifecycle"] = "PASS"
            self.result["repeatedExport"] = "RUNNING"
            self.repeated_export()
            self.result["repeatedExport"] = "PASS"
            if self.api in (24, 25):
                self.result["oldApiJmdnsLifecycle"] = "RUNNING"
                self.old_api_jmdns_lifecycle()
                self.result["oldApiJmdnsLifecycle"] = "PASS"
            if self.api == 37:
                self.result["permissionRecreationAndPeer"] = "RUNNING"
                self.runtime_instrumentation()
                self.result["permissionRecreationAndPeer"] = "PASS"
            self.result["status"] = "PASS"
        except Exception as error:
            self.result["errors"].append(type(error).__name__ + ": " + str(error))
            for key in ("permissionLifecycle", "repeatedExport", "permissionRecreationAndPeer",
                        "oldApiJmdnsLifecycle"):
                if self.result[key] == "RUNNING":
                    self.result[key] = "FAIL"
        finally:
            # Graceful resource retirement is part of acceptance. A failure is
            # retained; outer pidfd/domain ownership still drains all descendants.
            if self.adb_server is not None:
                for label, command in (("force-stop", ("shell", "am", "force-stop", PACKAGE)),
                                       ("remove-ui", ("shell", "rm", "-f", getattr(self, "ui_path", ""))),
                                       ("emulator-stop", ("emu", "kill"))):
                    if self.device_admitted:
                        try:
                            self.adb(label, *command)
                        except Exception as error:
                            self.result["errors"].append(label + ": " + str(error))
                if self.emulator is not None:
                    try:
                        need(self.emulator.wait(timeout=20) == 0, "Emulator did not exit cleanly")
                    except Exception as error:
                        self.result["errors"].append("emulator-exit: " + str(error))
                try:
                    self.adb("adb-stop", "kill-server")
                    need(self.adb_server.wait(timeout=10) == 0, "adb server did not exit cleanly")
                except Exception as error:
                    self.result["errors"].append("adb-exit: " + str(error))
                for name in ("server_log", "emulator_log"):
                    if hasattr(self, name):
                        getattr(self, name).close()
            if self.result["errors"]:
                self.result["status"] = "FAIL"
            self.write("result.json", self.result)
        return 0 if self.result["status"] == "PASS" else 1


def finalize():
    runner = load_runner()
    state, context = runner.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    bootstrap = runner.absolute_path(os.environ["P2PKIT_AUDIT_BOOTSTRAP_DIR"])
    result = {"status": "FAIL", "cleanup": "NOT_PROVEN", "cacheCleanup": [], "errors": [], "physicalAcceptance": False}
    try:
        receipt = runner.read_json(bootstrap / "command-receipt.json")
        need(receipt["sourceBefore"] == receipt["sourceAfter"] == context["source"] and receipt["sourceUnchanged"] is True,
             "Source changed or was not admitted")
        need(receipt["ownedSurvivors"] == [] and receipt["errors"] == [] and receipt["stopExitCode"] == 0,
             "Outer ownership/Gradle stop unresolved; keep disposable state for inspection")
        targets = [p for p in runner.disposable_roots(ROOT) if p.exists() and str(p) not in context["preexistingOutputPaths"]]
        if (state / "fixtures").exists():
            targets.append(state / "fixtures")
        need(runner.cleanup(argparse.Namespace(state=str(state), path=[str(p) for p in targets])) == 0, "Owned output removal failed")
        baseline = runner.read_json(state / "evidence/android-art/cache-baseline.json")
        need(baseline == {"absentRoots": list(CACHE_ROOTS)}, "Unknown project-cache ownership")
        # The executor has finalized all receipts; these exact fresh-run caches
        # have no next consumer. Never traverse/delete arbitrary directories named build.
        for path in [state / "gradle-home", *[ROOT / name for name in CACHE_ROOTS]]:
            if path.exists():
                runner.reject_symlinks(path)
                if runner.within(path, ROOT):
                    need(not runner.git(ROOT, "ls-files", "-z", "--", path.relative_to(ROOT).as_posix()),
                         "Refuse tracked cache cleanup")
                record = {"path": str(path), "inspection": runner.inspect_disposable_tree(path), "removed": False}
                result["cacheCleanup"].append(record)
                runner.write_new_json(bootstrap / f"cache-cleanup-{len(result['cacheCleanup'])}-start.json", record)
                shutil.rmtree(path)
                record["removed"] = not path.exists()
        result["cleanup"] = "OWNED_PROCESSES_STOPPED_AND_DISPOSABLE_OUTPUTS_REMOVED"
        smoke = runner.read_json(state / "evidence/android-art/result.json")
        need(receipt["productExitCode"] == receipt["finalExitCode"] == 0 and smoke["status"] == "PASS", "Smoke did not pass")
        need((bootstrap / "kvm-restored").is_file(), "Hosted KVM access restoration not proved")
        result["status"] = "PASS"
    except Exception as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
    runner.write_new_json(bootstrap / "android-art-final.json", result)
    # Upload only regular, bounded evidence, never fixtures/SDK/AVD/adb keys or APKs.
    files = runner.regular_report_files(state / "evidence", [0]) + runner.regular_report_files(bootstrap, [0])
    need(sum(p.stat().st_size for p in files) <= 64 * 1024 * 1024, "Public evidence bound exceeded")
    runner.write_new_json(bootstrap / "evidence-sha256.json", [
        {"path": str(p.relative_to(state.parent)), "bytes": p.stat().st_size, "sha256": runner.file_digest(p)} for p in files])
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("bootstrap=" + str(bootstrap) + "\nevidence=" + str(state / "evidence") + "\n")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "scenario", "finalize"))
    parser.add_argument("--api", type=int, choices=tuple(IMAGES))
    args = parser.parse_args()
    need((args.mode == "scenario") == (args.api is not None), "Only a scenario accepts/requires --api")
    raise SystemExit(finalize() if args.mode == "finalize" else
                     Smoke(args.api).run_scenario() if args.mode == "scenario" else Smoke().run())
