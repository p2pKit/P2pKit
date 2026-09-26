#!/usr/bin/env python3
"""Bind original Portal PUBLISHED evidence; never upload, retry, sign or decrypt.

This public receipt is not publication authority by itself. Recovery must also
verify the original successful upload step, immutable retained artifacts,
signatures, remote bytes, consumers and its own protected owner approval.
"""

import argparse
import datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("frozen_applications", ROOT / "scripts/release_application_set.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)
P = F.P
FILES = ("bundle.sha256", "commit-sha.txt", "deployment-id.txt", "portal-events.jsonl", "status.json")
SCOPE = "ORIGINAL_CENTRAL_PUBLISHED_DEPLOYMENT"
UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


def read(path, limit=P.JSON_LIMIT):
    info = path.lstat()
    P.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= limit,
           "Original publication file is missing, linked or outside its bound")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        P.need((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino), "Original file replaced before read")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size,
                              value.st_mtime_ns, value.st_ctime_ns)
    P.need(len(raw) == info.st_size and identity(info) == identity(after) == identity(current),
           "Original publication file or path changed")
    return raw


def descriptor(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def event_time(value):
    P.need(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.000Z", value),
           "Portal event lacks its original UTC timestamp")
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.000Z").replace(
        tzinfo=datetime.timezone.utc).timestamp()


def validate_originals(originals, source, version, bundle_sha256):
    P.need(set(originals) == set(FILES), "Incomplete Portal original roster")
    P.need(originals["commit-sha.txt"] == (source + "\n").encode() and
           originals["bundle.sha256"] == (bundle_sha256 + "\n").encode(), "Portal source or bundle hash differs")
    identifier = originals["deployment-id.txt"].decode("ascii").removesuffix("\n")
    P.need(UUID.fullmatch(identifier) and originals["deployment-id.txt"] == (identifier + "\n").encode(),
           "Portal deployment ID is malformed")
    status = P.parsed(originals["status.json"])
    P.need(type(status) is dict and status.get("deploymentState") == "PUBLISHED" and
           ("deploymentId" not in status or status["deploymentId"] == identifier),
           "Original Portal status is not this completed publication")
    lines = originals["portal-events.jsonl"].splitlines()
    P.need(3 <= len(lines) <= 256, "Original Portal event count is outside its bound")
    events = [P.parsed(line) for line in lines]
    allowed = {"upload_started", "upload_accepted", "deployment_state", "status_retry", "publication_completed"}
    P.need(all(type(x) is dict and set(x) == {"timestamp", "event", "state", "detail"} and
               x["event"] in allowed and type(x["state"]) is type(x["detail"]) is str for x in events),
           "Portal originals contain failed, ambiguous or unknown events")
    times = [event_time(x["timestamp"]) for x in events]
    P.need(times == sorted(times), "Portal original events are not chronological")
    name = f"p2pkit-{version}-{source[:12]}"
    for kind, state, detail, index in (("upload_started", "LOCAL", name, 0),
                                      ("upload_accepted", "PENDING", identifier, 1),
                                      ("publication_completed", "PUBLISHED", identifier, len(events) - 1)):
        found = [i for i, x in enumerate(events) if x["event"] == kind]
        P.need(found == [index] and events[index]["state"] == state and events[index]["detail"] == detail,
               "Portal originals do not contain the unique original upload/completion join")
    valid_states = {"PENDING", "VALIDATING", "VALIDATED", "PUBLISHING", "PUBLISHED"}
    observed, poll_floor = "", 0
    for index, event in enumerate(events[2:-1], start=2):
        if event["event"] == "deployment_state":
            poll = re.fullmatch(r"poll_([1-9][0-9]{0,2})", event["detail"])
            P.need(poll and poll_floor < int(poll[1]) <= 120 and event["state"] in valid_states and
                   event["state"] != observed and observed != "PUBLISHED", "Impossible original Portal state transition")
            observed, poll_floor = event["state"], int(poll[1])
            P.need(observed != "PUBLISHED" or index == len(events) - 2,
                   "PUBLISHED must be the last observation before immediate uploader return")
        else:
            retry = re.fullmatch(r"curl_exit_([1-9][0-9]{0,2})", event["detail"])
            P.need(event["event"] == "status_retry" and event["state"] == observed and observed != "PUBLISHED" and
                   ((retry and int(retry[1]) <= 255) or re.fullmatch(r"http_(429|5[0-9]{2})", event["detail"])),
                   "Original Portal retry does not preserve the observed state")
            poll_floor += 1
            P.need(poll_floor <= 120, "Portal retries exceed the original poll bound")
    P.need(observed == "PUBLISHED" and events[-2]["event"] == "deployment_state",
           "Missing unique terminal PUBLISHED observation")
    return {"id": identifier, "name": name, "state": "PUBLISHED", "startedAt": events[0]["timestamp"],
            "completedAt": events[-1]["timestamp"]}


def receipt(context, tree, summary_raw, originals):
    summary = P.parsed(summary_raw)
    source, version = context["source"], context["tag"][1:]
    P.need(P.SHA.fullmatch(source) and P.SHA.fullmatch(tree) and context["tag"] == "v" + version and
           P.VERSION.from_properties("VERSION_NAME=" + version + "\n")["canonicalVersion"] == version and
           not version.endswith("-SNAPSHOT"), "Invalid original source/tree/version")
    P.number(context["id"])
    P.number(context["attempt"])
    P.need(summary.get("schemaVersion") == 2 and summary.get("sourceSha") == source and
           summary.get("sourceTree") == tree and summary.get("version") == version and
           summary.get("group") == "io.github.apdelrahman1911" and
           summary.get("bundleFile") == f"p2pkit-{version}-central-bundle.zip" and
           type(summary.get("bundleSizeBytes")) is int and 0 < summary["bundleSizeBytes"] < P.ARCHIVE_LIMIT and
           all(re.fullmatch(r"[0-9a-f]{64}", summary.get(key, "")) for key in
               ("bundleSha256", "manifestSha256", "publicKeySha256")), "Signed bundle summary binding differs")
    deployment = validate_originals(originals, source, version, summary["bundleSha256"])
    return {"schema": 1, "scope": SCOPE, "source": {"commit": source, "tree": tree}, "version": version,
            "tag": context["tag"], "invocation": {"workflowPath": P.MAVEN_WORKFLOW, "workflowSha": source,
                "run": context["id"], "attempt": context["attempt"]},
            "bundle": {"file": summary["bundleFile"], "bytes": summary["bundleSizeBytes"],
                "sha256": summary["bundleSha256"], "summarySha256": hashlib.sha256(summary_raw).hexdigest(),
                "manifestSha256": summary["manifestSha256"], "publicKeySha256": summary["publicKeySha256"]},
            "deployment": deployment, "originals": {name: descriptor(raw) for name, raw in sorted(originals.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        context = F.hosted_context(os.environ, "revalidate")
        P.need(P.PACK.git(ROOT, "rev-parse", "HEAD").decode() == context["source"], "Wrong original Maven checkout")
        tree = P.PACK.git(ROOT, "rev-parse", "HEAD^{tree}").decode()
        version = context["tag"][1:]
        P.need(P.VERSION.from_properties((ROOT / "gradle.properties").read_text())["canonicalVersion"] == version,
               "Canonical version differs from the original Maven tag")
        folder = ROOT / "build/reports/maven-central"
        P.PACK.physical_directory(folder)
        summary = ROOT / f"build/central/p2pkit-{version}-central-bundle.summary.json"
        P.PACK.physical_directory(summary.parent)
        result = receipt(context, tree, read(summary), {name: read(folder / name) for name in FILES})
        with (folder / "deployment-receipt.json").open("xb") as output:
            output.write(P.encoded(result))
        print("ORIGINAL_PUBLISHED_RECEIPT_RECORDED_NOT_RECOVERY_APPROVAL")
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("HOLD: " + (str(error) if isinstance(error, P.Hold) else type(error).__name__))
        return 1  # No backend, credential or original payload is printed.


if __name__ == "__main__":
    sys.exit(main())
