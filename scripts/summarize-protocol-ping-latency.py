#!/usr/bin/env python3
"""Validate and summarize actual source-bound secure-v2 PING/PONG diagnostic records."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def need(value, reason):
    if not value:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def summarize(raw, commit, tree):
    need(0 < len(raw) <= 262144 and raw.endswith(b"\n"), "Missing, truncated or oversized record")
    records = [json.loads(line, object_pairs_hook=unique_object) for line in raw.decode("utf-8", errors="strict").splitlines()]
    identity = records.pop(0)
    need(identity.get("kind") == "identity" and identity.get("sourceCommit") == commit and
         identity.get("declaredSourceTree") == tree and identity.get("protocol") == "authenticated-v2" and
         identity.get("topology") == "same-process-two-kits-ipv4-loopback" and
         type(identity.get("warmup")) is int and type(identity.get("retained")) is int and
         identity.get("warmup") == 8 and identity.get("retained") == 32, "Wrong source or measurement scope")
    blocks, grouped = [], {False: [], True: []}
    for block, mode in enumerate((False, True, True, False)):
        admission = records.pop(0)
        need(type(admission.get("block")) is int and all(type(admission.get(key)) is bool for key in
             ("tcpNoDelay", "dialReadback", "acceptReadback", "mutualPinsVerified")) and
             admission == {"kind": "block", "block": block, "tcpNoDelay": mode,
                           "dialReadback": mode, "acceptReadback": mode, "mutualPinsVerified": True},
             "Wrong block order, socket option or authentication")
        samples = []
        prior_end = None
        for sample in range(40):
            record = records.pop(0)
            need(record.get("kind") == "sample" and record.get("block") == block and
                 type(record.get("block")) is int and type(record.get("sample")) is int and
                 record.get("sample") == sample and record.get("warmup") is (sample < 8), "Wrong sample ordering")
            times = record.get("timesNanos")
            need(isinstance(times, list) and len(times) == 4 and all(type(t) is int for t in times) and
                 times == sorted(times) and times[-1] > times[0], "Wrong protocol event clock sequence")
            need(prior_end is None or times[0] >= prior_end, "Overlapping clock sequence")
            prior_end = times[-1]
            need(type(record.get("rttNanos")) is int and record["rttNanos"] == times[-1] - times[0],
                 "Wrong PING/PONG boundary duration")
            if sample >= 8:
                samples.append(record["rttNanos"])
        retirement = records.pop(0)
        need(type(retirement.get("block")) is int and type(retirement.get("closed")) is bool and
             type(retirement.get("warningsOrErrors")) is int and
             retirement == {"kind": "retirement", "block": block, "closed": True, "warningsOrErrors": 0},
             "Missing exact-owned retirement or unexpected SDK diagnostic")
        blocks.append({"block": block, "tcpNoDelay": mode, **stats(samples)})
        grouped[mode].extend(samples)
    need(records == [{"kind": "terminal", "outcome": "PASS", "blocks": 4}], "Missing sole completed terminal")
    return {"identity": identity, "rawSha256": hashlib.sha256(raw).hexdigest(), "blocks": blocks,
            "conditions": [{"tcpNoDelay": mode, **stats(grouped[mode])} for mode in (False, True)],
            "scope": "actual shipped secure-v2 PING/PONG; two same-process JVM kits; IPv4 loopback only",
            "boundary": "initiator protocol TX trace before encoding through decoded protocol RX PONG trace",
            "notEstablished": ["speedup causality/statistical significance", "physical or real-LAN latency",
                               "Android/Apple runtime performance", "independent interoperability"]}


def stats(samples):
    ordered = sorted(samples)
    return {"count": len(samples), "minimumNanos": ordered[0], "medianNanos": statistics.median(ordered),
            "p95NanosNearestRank": ordered[math.ceil(0.95 * len(ordered)) - 1], "maximumNanos": ordered[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    need(not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT), "Source tree is dirty")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    report = summarize(args.raw.read_bytes(), commit, tree)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps(report["conditions"]))


if __name__ == "__main__":
    main()
