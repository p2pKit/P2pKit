#!/usr/bin/env python3
"""Passive parser/file-fixture controls only; no Android, image review or Parcel decoding."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "android_ui_evidence", Path(__file__).resolve().parents[1] / "verify-android-ui-evidence.py")
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)

TOKEN, COMMIT, TREE = "0123456789abcdef0123456789abcdef", "a" * 40, "b" * 40
PENDING = "HARNESS_PASS_PENDING_REVIEW"
PACKAGE = "dev.p2pkit.sample.android"
CAPTURES = """
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
""".split()
CELLS = """
default-mask-and-explicit-reveal-hide real-fifteen-second-expiry pre-clear-parcel-save
disposal-of-original-owner actual-registry-restoration stop-reentry fakegrant-true-resumed
explicit-protected-join-success fakegrant-false-resumed fakegrant-true-stopped
join-success-then-failure failure-without-success-control final-card-disposal
""".split()
CLEANUP = """
modeled-pending-result test-compositions frame-and-window-observers fake-kit-stop
test-viewmodel-store owned-activity lifecycle-observer retain-diagnostics
""".split()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n").encode()


def terminal_fields(case, failure=False):
    component, test = (("UiAcceptanceInstrumentation", "diagnosticEventAppearsWithoutInput") if case == "317"
                       else ("CredentialUiInstrumentation", "productionCredentialRestorationAndLifecycle"))
    result = {"class": PACKAGE + ".runtime." + component, "test": test, "numtests": "1", "current": "1",
              "p2pkitCompleted": "1", "p2pkitToken": TOKEN, "p2pkitEvidence": f"no_backup/ui-{case}-{TOKEN}",
              "p2pkitOutcome": "FAIL" if failure else PENDING}
    if case == "317":
        result["p2pkitCleanup"] = "RETIRED_OWNED_OBSERVERS"
    if failure:
        result["p2pkitFailureStage"] = "body"
        if case == "317":
            result["p2pkitFailureType"] = "IllegalStateException"
    return result


def terminal(case, failure=False, fields=None):
    fields = terminal_fields(case, failure) if fields is None else fields
    lines = ["INSTRUMENTATION_STATUS: " + key + "=" + value for key, value in fields.items()]
    lines += ["INSTRUMENTATION_STATUS_CODE: " + ("-2" if failure else "0")]
    lines += ["INSTRUMENTATION_RESULT: " + key + "=" + value for key, value in fields.items()]
    lines += ["INSTRUMENTATION_CODE: " + ("0" if failure else "-1")]
    return ("\n".join(lines) + "\n").encode()


def png_bytes(seed):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    # Complete tiny synthetic PNG; no real UI pixels or provenance is implied.
    header = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    row = b"\0" + bytes((seed, 0, 0, 255, 255, 255))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(row * 2)) + chunk(b"IEND", b"")


def record(index, name, session=None):
    return {"schemaVersion": 1, "index": index, "timestamp": f"2026-09-15T00:00:{index:02d}Z",
            "platform": "android", "operatingSystem": "fixture", "applicationVersion": "fixture",
            "buildNumber": "1", "gitCommitSha": COMMIT, "safeDeviceId": "synthetic-only",
            "testSessionId": session or "ui317-" + TOKEN, "testId": "UI317", "role": "observer",
            "category": "ui", "eventName": name, "severity": "INFO", "direction": "LOCAL",
            "details": {}, "redactedFields": []}


def common_report(case):
    result = {"case": case, "sourceCommit": COMMIT, "declaredSourceTree": TREE, "api": 35,
              "targetSdk": 37, "abis": ["arm64-v8a"], "pid": 123, "processStartElapsedMillis": 100,
              "outcome": PENDING}
    if case == "317":
        result.update(schemaVersion=1, token=TOKEN, uid=10123,
                      treeBinding="host must verify source tree and both APK hashes; not independently readable in ART",
                      cleanupScope="owned Activities and observers; host must retire the owned test process",
                      boundsMillis={"body": 60000, "setup": 25000, "handsOffRefresh": 5000,
                                    "mainCall": 5000, "cleanupAction": 10000})
    else:
        result.update(treeBinding="outer controller must independently bind clean source and both APK hashes",
                      cleanupScope="owned UI/fake resources; host must retire exact ART process/guest",
                      boundsMillis={"body": 150000, "setup": 20000, "mainCall": 5000, "observation": 5000,
                                    "cleanupAction": 10000, "outer": 240000})
    return result


class Fixture:
    def __init__(self, parent, case):
        self.case = case
        parent.mkdir()
        self.root = parent / f"ui-{case}-{TOKEN}"
        self.root.mkdir()
        self.stdout = parent / "instrumentation.stdout"
        self.stdout.write_bytes(terminal(case))
        self.report = common_report(case)
        (self.prepare317 if case == "317" else self.prepare324)()
        self.save()

    def write_json(self, name, value):
        (self.root / name).write_bytes(encoded(value))

    def save(self):
        self.write_json("result.json", self.report)

    def prepare317(self):
        prior = record(1, "application.foreground", "session-unassigned")
        created, baseline, added = record(2, "test.session.created"), record(3, "probe317_a"), record(4, "probe317_b")
        self.report.update(
            baselineRecord=baseline, recorderBefore=[prior, created, baseline], recorderAfter=[prior, created, baseline, added],
            droppedBefore=0, droppedAfter=0, handsOffStart={"elapsedNanos": 1000}, handsOffEnd={"elapsedNanos": 3000},
            injection={"beginElapsedNanos": 1500, "endElapsedNanos": 1501, "revisionBefore": 9,
                       "revisionAfter": 10, "record": added}, renderedWitnessObservedElapsedNanos=2100,
            observedCounts=[1, 2], cleanupFailures=[], overflow=False, unexpectedActivity=False,
            independentVisualAndMutationReview="REQUIRED_NOT_PERFORMED_BY_RUNNER",
            lifecycle=[{"elapsedNanos": 100, "kind": "created"}, {"elapsedNanos": 200, "kind": "resumed"},
                       {"elapsedNanos": 6000, "kind": "destroyed"}],
            inputs=[{"elapsedNanos": 350, "kind": "accessibility-16"}],
            windowEvents=[{"elapsedNanos": 400, "kind": "focus-true"}],
            actions=[{"elapsedNanos": 500, "action": 16, "label": "open-diagnostics", "success": True}],
            identity={"session": "ui317-" + TOKEN, "testId": "UI317", "role": "observer", "screenWidthDp": 900,
                      "screenHeightDp": 1500, "lifecycleCount": 2, "inputCount": 1, "windowCount": 1, "actionCount": 1},
            frames=[{"label": "setup-render", "armedElapsedNanos": 600, "committedElapsedNanos": 700,
                     "removedBeforeCommit": False},
                    {"label": "event-only", "armedElapsedNanos": 1501, "committedElapsedNanos": 2000,
                     "removedBeforeCommit": False}])
        for label, selected, seed, begin in (("before", [baseline], 1, 750), ("after", [baseline, added], 2, 2200)):
            image = png_bytes(seed)
            (self.root / (label + ".png")).write_bytes(image)
            self.report[label + "Screenshot"] = {
                "file": label + ".png", "sha256": sha(image), "width": 2, "height": 2,
                "beginElapsedNanos": begin, "endElapsedNanos": begin + 50,
                "windows": [{"id": 1, "type": 1, "layer": 0, "bounds": [0, 0, 2, 2]}],
                "targets": [[0, 0, 2, 2] for _ in range(len(selected) + 1)],
                "pixelOracle": "nonblank in-bounds display crops; exact visible text requires independent review"}
            texts = [f"{len(selected)} event(s); tap rows to select", "Pause live logs"] + [
                f"{event['timestamp']} INFO {event['eventName']}\nLOCAL" for event in selected]
            self.write_json(label + "-tree.json", {"captured": {"elapsedNanos": begin - 1}, "windowId": 1,
                                                   "nodes": [{"text": text, "visible": True} for text in texts]})
        # The real writer exports the active session, not prior unassigned setup records.
        (self.root / "events.jsonl").write_bytes(b"".join(encoded(event) for event in
                                                       (created, baseline, added, record(5, "application.shutdown"))))

    def prepare324(self):
        secret, ssid = "Ui324-" + TOKEN[-10:], "ui324-" + TOKEN[:8]
        times = [1, 2, 3, 4, 5.05, 20.15, 21, 22, 23, 23.1] + list(range(24, 46))
        frame_labels = {"expired-mask": "expiry-natural-frame", "restored-empty-secret": "actual-registry-restoration",
                        "restored-ssid": "actual-registry-restoration", "stop-reentry-reentered-empty": "stop-reentry",
                        "fakegrant-true-resumed-cleared": "fakegrant-true-resumed", "dismiss-joined-empty": "dismiss-joined",
                        "fakegrant-false-resumed-cleared": "fakegrant-false-resumed",
                        "fakegrant-true-stopped-reentered-empty": "fakegrant-true-stopped",
                        "join-success-then-failure-cleared": "join-success-then-failure"}
        status = {"initial-card", "disposal-of-original-owner", "explicit-protected-join-success", "final-card-disposal"}
        revealed = {"explicit-reveal", "expiry-start", "before-save-revealed", "before-stop-revealed",
                    "fakegrant-true-resumed-revealed", "explicit-protected-join-success-revealed",
                    "fakegrant-false-resumed-revealed", "fakegrant-true-stopped-revealed", "join-success-then-failure-revealed"}
        empty = {"restored-empty-secret", "stop-reentry-reentered-empty", "fakegrant-true-resumed-cleared",
                 "dismiss-joined-empty", "fakegrant-false-resumed-cleared", "fakegrant-true-stopped-reentered-empty",
                 "join-success-then-failure-cleared"}
        frames, captures = {}, []
        for index, (label, seconds) in enumerate(zip(CAPTURES, times)):
            now = int(seconds * 1_000_000_000)
            name = frame_labels.get(label, label)
            witness = frames.setdefault(name, {"label": name, "armedElapsedNanos": now - 20_000_000,
                                               "committedElapsedNanos": now - 10_000_000, "armCount": 1})
            image = png_bytes(index)
            (self.root / (label + ".png")).write_bytes(image)
            capture = {"label": label, "elapsedNanos": now, "frame": copy.deepcopy(witness), "pngSha256": sha(image),
                       "width": 2, "height": 2,
                       "targets": [] if label in ("disposal-of-original-owner", "final-card-disposal") else ["[0,0][2,2]"]}
            if label not in status:
                text, password, length = ((ssid, False, len(ssid)) if label == "restored-ssid" else
                                          ("", True, 0) if label in empty else
                                          (secret, False, len(secret)) if label in revealed else
                                          ("\u2022" * len(secret), True, len(secret)))
                capture.update(layoutText=text, password=password, inputLength=length, drawnLength=len(text),
                               layoutSha256=sha(text.encode()),
                               oracle="actual GetTextLayoutResult; raw InputText is not a pixel-exposure assertion")
            captures.append(capture)
            # Raw editable semantics may contain the synthetic input while the drawn layout is masked.
            self.write_json(label + "-tree.json", [{"text": secret, "editable": True, "password": True,
                                                    "visible": True, "bounds": "[0,0][2,2]"}])
        self.report.update(
            lifecycleViolation=False, permissionModel="fakegrant; no OS permission or network acceptance",
            cells=[{"cell": name, "outcome": "OBSERVED_PENDING_REVIEW"} for name in CELLS],
            cleanup=[{"step": name, "outcome": "RETIRED"} for name in CLEANUP],
            captures=captures, frames=list(frames.values()),
            revealExpiry={"showBeginElapsedNanos": 5_000_000_000, "lastRevealedObservedElapsedNanos": 19_950_000_000,
                          "concealedObservedElapsedNanos": 20_100_000_000, "unchangedInputAndLifecycle": True},
            actions=[{"label": label, "action": 16, "beginElapsedNanos": start,
                      "endElapsedNanos": start + 1_000_000, "success": True}
                     for label, start in (("SSID", 1_500_000_000), ("Show", 5_000_000_000), ("Show", 20_500_000_000))],
            lifecycle=[{"event": event, "activity": 100, "elapsedNanos": now} for event, now in
                       (("resumed", 500_000_000), ("stopped", 25_500_000_000), ("resumed", 25_700_000_000),
                        ("destroyed", 60_000_000_000))],
            compositionObservations=[{"elapsedNanos": now, "credentialIdentity": identity, "length": 0,
                                      "revealed": False, "joinSuccessCount": 0} for identity, now in
                                     ((101, 1_000_000_000), (102, 23_000_000_000))],
            permissionTrace=[], provisioningCalls=[])
        for index, granted in enumerate((True, False, True)):
            now = (28, 35, 38)[index] * 1_000_000_000
            self.report["permissionTrace"] += [
                {"kind": "fakegrant-request", "requestCode": 65537, "elapsedNanos": now + 100_000_000},
                {"kind": "fakegrant-result", "requestCode": 65537, "elapsedNanos": now + 200_000_000, "granted": granted}]
        for mode, returned, signals in (("JOINED", "Joined", ["NetworkJoined"]),
                                        ("JOINED_THEN_FAILED", "Joined", ["NetworkJoined", "JoinFailed"]),
                                        ("FAILED_ONLY", "Failed", ["JoinFailed"])):
            self.report["provisioningCalls"].append({"mode": mode, "returned": returned, "signals": signals,
                                                    "protected": True, "ssidMatches": True, "secretMatches": True})
        parcel = b"synthetic byte fixture, NOT an Android Parcel: " + ssid.encode()
        (self.root / "saved-state.parcel").write_bytes(parcel)
        self.write_json("saved-state.json", {
            "bytes": len(parcel), "sha256": sha(parcel), "entryCount": 1, "keys": ["fixture-ssid-provider"],
            "payloadTypes": ["java.util.LinkedHashMap", "java.lang.String", "java.util.ArrayList", "java.lang.String"],
            "fullyInspected": True, "ssidPresent": True, "secretPresent": False,
            "beginElapsedNanos": 21_500_000_000, "decodedElapsedNanos": 21_600_000_000})
        for name in ("fixture/no-backup/test-diagnostics", "fixture/cache"):
            (self.root / name).mkdir(parents=True)
        event = encoded(record(1, "test.session.created", "ui324-synthetic-recorder-session"))
        (self.root / "events.jsonl").write_bytes(event)
        (self.root / "fixture/no-backup/test-diagnostics/diagnostic-events.jsonl").write_bytes(event)
        (self.root / "fixture/no-backup/test-diagnostics/.diagnostic-events.jsonl.lock").write_bytes(b"")

    def check(self, **expectations):
        return subject.verify(self.root, self.stdout, expectations.get("case", self.case),
                              expectations.get("token", TOKEN), expectations.get("commit", COMMIT),
                              expectations.get("tree", TREE))

    def fail(self):
        self.report["outcome"] = "FAIL"
        self.report["failure"] = {"stage": "body", "type": "java.lang.IllegalStateException"}
        self.stdout.write_bytes(terminal(self.case, failure=True))
        self.save()


class TerminalTests(unittest.TestCase):
    def test_named_one_bundle_forms_remain_distinct(self):
        for case in ("317", "324"):
            with self.subTest(case=case):
                parsed = subject.parse_terminal(terminal(case), case, TOKEN)
                self.assertEqual(parsed, terminal_fields(case))
                self.assertEqual("p2pkitCleanup" in parsed, case == "317")
                failed = terminal_fields(case, True)
                del failed["p2pkitEvidence"], failed["p2pkitToken"]
                self.assertEqual(subject.parse_terminal(terminal(case, True, failed), case, TOKEN)["p2pkitOutcome"], "FAIL")

    def test_duplicate_reordered_unknown_and_nonterminal_bundles_rejected(self):
        raw = terminal("317")
        controls = [raw.replace(b"INSTRUMENTATION_STATUS_CODE: 0", b"INSTRUMENTATION_STATUS_CODE: 1"),
                    raw + b"INSTRUMENTATION_CODE: -1\n", raw + b"unrelated output\n",
                    b"INSTRUMENTATION_RESULT: current=1\n" + raw,
                    b"INSTRUMENTATION_STATUS: current=1\n" + raw,
                    raw.replace(b"INSTRUMENTATION_RESULT: current=1", b"INSTRUMENTATION_RESULT: current=2"),
                    raw.replace(b"p2pkitCompleted=1", b"p2pkitCompleted=0"),
                    raw.replace(b"HARNESS_PASS_PENDING_REVIEW", b"PASS"),
                    raw.replace(b"INSTRUMENTATION_CODE: -1", b"INSTRUMENTATION_CODE: 0"),
                    b"\xff\n"]
        for index, value in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(subject.Rejected):
                subject.parse_terminal(value, "317", TOKEN)

    def test_wrong_case_token_or_success_with_failure_fields_rejected(self):
        with self.assertRaises(subject.Rejected):
            subject.parse_terminal(terminal("317"), "324", TOKEN)
        with self.assertRaises(subject.Rejected):
            subject.parse_terminal(terminal("317"), "317", "c" * 32)
        for case, field in (("317", "p2pkitFailureType"), ("324", "p2pkitFailureStage"),
                            ("324", "p2pkitRetention"), ("324", "p2pkitCleanup"), ("317", "installed")):
            fields = terminal_fields(case)
            fields[field] = "FAIL"
            with self.subTest(case=case, field=field), self.assertRaises(subject.Rejected):
                subject.parse_terminal(terminal(case, fields=fields), case, TOKEN)

    def test_truncated_empty_aborted_streams_are_incomplete(self):
        for raw in (b"", terminal("317")[:-1], b"INSTRUMENTATION_STATUS: current=1\n",
                    b"INSTRUMENTATION_FAILED: no component\n", b"INSTRUMENTATION_ABORTED: killed\n"):
            with self.subTest(raw=raw[:60]), self.assertRaises(subject.Incomplete):
                subject.parse_terminal(raw, "317", TOKEN)

    def test_duplicate_nonfinite_unbounded_and_malformed_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b"NaN", b"Infinity", b"-Infinity", b"1e999", b"\xff",
                    b"9" * 100, b"9223372036854775808", b"{", b'[{"a":1,"a":2}]'):
            with self.subTest(raw=raw[:40]), self.assertRaises(subject.Rejected):
                subject.strict_json(raw)
        self.assertEqual(subject.strict_json(b"-9223372036854775808"), -(1 << 63))


class RetainedEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="android-ui-verifier-fixture-")
        self.addCleanup(temporary.cleanup)
        self.root, self.serial = Path(temporary.name).resolve(), 0

    def fixture(self, case="317"):
        self.serial += 1
        return Fixture(self.root / str(self.serial), case)

    def assert_status(self, fixture, expected, **expectations):
        result = fixture.check(**expectations)
        self.assertEqual(result["contentStatus"], expected, result["errors"])
        self.assertEqual(result["provenance"], "UNPROVEN")
        self.assertEqual(result["runtimeAcceptance"], "NOT_ACCEPTED")
        self.assertEqual(result["visualReview"], "NOT_PERFORMED")
        self.assertEqual(result["mutationReview"], "NOT_PERFORMED")
        return result

    def test_positive_graphs_hash_originals_without_runtime_or_image_promotion(self):
        for case, count in (("317", 6), ("324", 70)):
            fixture = self.fixture(case)
            paths = [fixture.stdout] + sorted(path for path in fixture.root.rglob("*") if path.is_file())
            originals = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
            result = self.assert_status(fixture, "CONSISTENT")
            self.assertEqual(result["harnessOutcome"], PENDING)
            self.assertEqual(len(result["files"]), count)
            self.assertEqual({row["path"]: row["sha256"] for row in result["files"]},
                             {path.relative_to(fixture.root).as_posix(): sha(raw) for path, (raw, _) in originals.items()
                              if path != fixture.stdout})
            self.assertEqual(originals, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
            if case == "324":
                self.assertEqual(len(fixture.report["captures"]), 32)
                lock = next(row for row in result["files"] if row["path"].endswith(".lock"))
                self.assertEqual(lock["bytes"], 0)
                self.assertNotIn("uid", fixture.report)
                self.assertNotIn("token", fixture.report)

    def test_source_case_token_tree_and_report_identity_swaps_fail(self):
        for change in ({"commit": "c" * 40}, {"tree": "c" * 40}, {"token": "c" * 32}, {"case": "324"}):
            with self.subTest(change=change):
                self.assert_status(self.fixture(), "REJECTED", **change)
        for field, value in (("schemaVersion", True), ("sourceCommit", "c" * 40), ("declaredSourceTree", "c" * 40),
                             ("api", 34), ("targetSdk", 36), ("pid", 0), ("uid", 0), ("abis", []),
                             ("treeBinding", "SOURCE_PROVEN"), ("token", "c" * 32)):
            fixture = self.fixture()
            fixture.report[field] = value
            fixture.save()
            with self.subTest(field=field):
                self.assert_status(fixture, "REJECTED")

    def test_caller_trust_flags_and_invented_324_fields_never_admit(self):
        for case, field, value in (("317", "installed", True), ("317", "runtimeAcceptance", "PASS"),
                                   ("324", "schemaVersion", 1), ("324", "uid", 10123), ("324", "token", TOKEN)):
            fixture = self.fixture(case)
            fixture.report[field] = value
            fixture.save()
            with self.subTest(case=case, field=field):
                self.assert_status(fixture, "REJECTED")

    def test_missing_fields_or_originals_are_incomplete_not_pass(self):
        for case, name in (("317", "before.png"), ("317", "result.json"), ("324", "saved-state.parcel"),
                            ("324", "final-card-disposal-tree.json")):
            fixture = self.fixture(case)
            (fixture.root / name).unlink()
            with self.subTest(case=case, name=name):
                self.assert_status(fixture, "INCOMPLETE")
        fixture = self.fixture()
        del fixture.report["identity"]
        fixture.save()
        self.assert_status(fixture, "INCOMPLETE")

    def test_317_recorder_revision_and_hands_off_claims_are_cross_checked(self):
        changes = [lambda r: r["injection"].update(revisionAfter=11),
                   lambda r: r["injection"].update(record=record(9, "wrong")),
                   lambda r: r["recorderAfter"].insert(0, record(8, "extra")),
                   lambda r: r.update(droppedAfter=1), lambda r: r.update(observedCounts=[True, 2]),
                   lambda r: r.update(overflow=True), lambda r: r.update(unexpectedActivity=True),
                   lambda r: r.update(cleanupFailures=[{"stage": "owned-activities"}]),
                   lambda r: r["frames"][1].update(removedBeforeCommit=True),
                   lambda r: r["frames"][1].update(armedElapsedNanos=1500),
                   lambda r: r.update(renderedWitnessObservedElapsedNanos=5_000_001_502)]
        for index, change in enumerate(changes):
            fixture = self.fixture()
            change(fixture.report)
            fixture.save()
            with self.subTest(change=index):
                self.assert_status(fixture, "REJECTED")
        for name in ("lifecycle", "inputs", "windowEvents", "actions"):
            fixture = self.fixture()
            fixture.report[name].append({"elapsedNanos": 1600})
            fixture.save()
            with self.subTest(observer=name):
                self.assert_status(fixture, "REJECTED")

    def test_317_callback_append_order_is_not_a_guaranteed_clock_order(self):
        fixture = self.fixture()
        fixture.report["inputs"] = [{"elapsedNanos": 450}, {"elapsedNanos": 350}]
        fixture.report["identity"]["inputCount"] = 2
        fixture.save()
        self.assert_status(fixture, "CONSISTENT")

    def test_317_visible_tree_and_exported_session_prefix_checked(self):
        fixture = self.fixture()
        tree = json.loads((fixture.root / "after-tree.json").read_bytes())
        tree["nodes"][-1]["visible"] = False
        fixture.write_json("after-tree.json", tree)
        self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        (fixture.root / "events.jsonl").write_bytes(encoded(record(99, "unrelated", "another-session")))
        self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        event = record(99, "unknown-version")
        event["schemaVersion"] = 2
        (fixture.root / "events.jsonl").write_bytes(encoded(event))
        self.assert_status(fixture, "REJECTED")

    def test_png_header_hash_dimensions_targets_and_distinct_images_checked(self):
        changes = [lambda r: r["beforeScreenshot"].update(sha256="c" * 64),
                   lambda r: r["beforeScreenshot"].update(width=3),
                   lambda r: r["beforeScreenshot"].update(targets=[[0, 0, 3, 2], [0, 0, 2, 2]]),
                   lambda r: r["beforeScreenshot"].update(file="../before.png")]
        for index, change in enumerate(changes):
            fixture = self.fixture()
            change(fixture.report)
            fixture.save()
            with self.subTest(change=index):
                self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        raw = bytearray((fixture.root / "before.png").read_bytes())
        raw[29] ^= 1
        (fixture.root / "before.png").write_bytes(raw)
        fixture.report["beforeScreenshot"]["sha256"] = sha(raw)
        fixture.save()
        self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        raw = bytearray((fixture.root / "before.png").read_bytes())
        raw[16:29] = struct.pack(">IIBBBBB", 4097, 4096, 8, 2, 0, 0, 0)
        raw[29:33] = struct.pack(">I", zlib.crc32(raw[12:29]))
        (fixture.root / "before.png").write_bytes(raw)
        fixture.report["beforeScreenshot"].update(sha256=sha(raw), width=4097, height=4096)
        fixture.save()
        self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        raw = (fixture.root / "before.png").read_bytes()
        (fixture.root / "after.png").write_bytes(raw)
        fixture.report["afterScreenshot"]["sha256"] = sha(raw)
        fixture.save()
        self.assert_status(fixture, "REJECTED")

    def test_324_cells_cleanup_scope_and_captures_remain_exact(self):
        changes = [lambda r: r["cells"].pop(), lambda r: r["cells"].reverse(),
                   lambda r: r["cells"][0].update(outcome="PASS"), lambda r: r["cleanup"].reverse(),
                   lambda r: r["cleanup"][0].update(outcome="FAILED"), lambda r: r.update(lifecycleViolation=True),
                   lambda r: r.update(permissionModel="real OS grant"), lambda r: r["captures"].reverse(),
                   lambda r: r["frames"].append(copy.deepcopy(r["frames"][0])),
                   lambda r: r["captures"][0]["frame"].update(armCount=2),
                   lambda r: r["captures"][0].update(targets=["[0,0][3,2]"])]
        for index, change in enumerate(changes):
            fixture = self.fixture("324")
            change(fixture.report)
            fixture.save()
            with self.subTest(change=index):
                self.assert_status(fixture, "REJECTED")

    def test_324_layout_checks_do_not_search_raw_input_for_leaks(self):
        for field, value in (("layoutText", "Ui324-" + TOKEN[-10:]), ("password", False), ("inputLength", 0),
                             ("drawnLength", 0), ("layoutSha256", "c" * 64), ("oracle", "VISUAL_PASS")):
            fixture = self.fixture("324")
            fixture.report["captures"][1][field] = value  # Default-masking capture.
            fixture.save()
            with self.subTest(field=field):
                self.assert_status(fixture, "REJECTED")
        self.assert_status(self.fixture("324"), "CONSISTENT")  # Secret in fixture tree is deliberately allowed.

    def test_324_expiry_needs_fixed_time_explicit_show_and_no_interference(self):
        changes = [lambda r: r["revealExpiry"].update(concealedObservedElapsedNanos=19_000_000_000),
                   lambda r: r["revealExpiry"].update(concealedObservedElapsedNanos=23_000_000_000),
                   lambda r: r["revealExpiry"].update(unchangedInputAndLifecycle=False),
                   lambda r: r["actions"][1].update(label="not-Show"),
                   lambda r: r["actions"][0].update(endElapsedNanos=6_000_000_000),
                   lambda r: r["actions"][2].update(beginElapsedNanos=10_000_000_000),
                   lambda r: r["lifecycle"][1].update(elapsedNanos=10_000_000_000)]
        for index, change in enumerate(changes):
            fixture = self.fixture("324")
            change(fixture.report)
            fixture.save()
            with self.subTest(change=index):
                self.assert_status(fixture, "REJECTED")
        fixture = self.fixture("324")
        fixture.report["revealExpiry"]["lastRevealedObservedElapsedNanos"] = 0  # Source-defined absence, not proof.
        fixture.save()
        self.assert_status(fixture, "CONSISTENT")

    def test_324_parcel_bytes_inspection_claims_and_pre_clear_order_checked(self):
        for field, value in (("bytes", 1), ("sha256", "c" * 64), ("fullyInspected", False), ("ssidPresent", False),
                             ("secretPresent", True), ("keys", ["same", "same"]), ("entryCount", 2),
                             ("payloadTypes", []), ("beginElapsedNanos", 24_000_000_000)):
            fixture = self.fixture("324")
            saved = json.loads((fixture.root / "saved-state.json").read_bytes())
            saved[field] = value
            fixture.write_json("saved-state.json", saved)
            with self.subTest(field=field):
                self.assert_status(fixture, "REJECTED")
        fixture = self.fixture("324")
        (fixture.root / "saved-state.parcel").write_bytes(b"changed original")
        self.assert_status(fixture, "REJECTED")

    def test_324_expiry_observations_must_fit_reported_capture_interval(self):
        def show_after_capture(report):
            report["revealExpiry"]["showBeginElapsedNanos"] = 5_060_000_000
            report["actions"][1].update(beginElapsedNanos=5_060_000_000, endElapsedNanos=5_061_000_000)

        changes = [lambda r: r["revealExpiry"].update(concealedObservedElapsedNanos=20_200_000_000),
                   lambda r: r["revealExpiry"].update(lastRevealedObservedElapsedNanos=5_020_000_000),
                   lambda r: r["captures"][4].update(elapsedNanos=20_110_000_000),
                   show_after_capture]
        for index, change in enumerate(changes):
            fixture = self.fixture("324")
            change(fixture.report)
            fixture.save()
            with self.subTest(change=index):
                self.assert_status(fixture, "REJECTED")
        for last in (0, 5_050_000_000):
            fixture = self.fixture("324")
            fixture.report["revealExpiry"]["lastRevealedObservedElapsedNanos"] = last
            fixture.save()
            with self.subTest(last=last):
                self.assert_status(fixture, "CONSISTENT")  # Zero remains absence, not duration evidence.

    def test_324_retained_generations_require_coordination_lock_even_on_failure(self):
        for failed in (False, True):
            for suffix in ("", ".1"):
                fixture = self.fixture("324")
                if failed:
                    fixture.fail()
                directory = fixture.root / "fixture/no-backup/test-diagnostics"
                active = directory / "diagnostic-events.jsonl"
                if suffix:
                    active.rename(directory / (active.name + suffix))
                lock = directory / ".diagnostic-events.jsonl.lock"
                lock.unlink()
                with self.subTest(failed=failed, suffix=suffix):
                    self.assert_status(fixture, "INCOMPLETE")
                    self.assertFalse(lock.exists())

    def test_324_positive_minimum_fixture_does_not_promote_early_failure(self):
        for failed in (False, True):
            for missing in ("active-log", "diagnostic-subtree", "cache-dir"):
                fixture = self.fixture("324")
                if failed:
                    fixture.fail()
                directory = fixture.root / "fixture/no-backup/test-diagnostics"
                removed = directory / "diagnostic-events.jsonl"
                if missing == "active-log":
                    removed.unlink()
                elif missing == "diagnostic-subtree":
                    removed.unlink()
                    (directory / ".diagnostic-events.jsonl.lock").unlink()
                    directory.rmdir()
                    removed = directory
                else:
                    removed = fixture.root / "fixture/cache"
                    removed.rmdir()
                with self.subTest(failed=failed, missing=missing):
                    self.assert_status(fixture, "HARNESS_FAILED" if failed else "INCOMPLETE")
                    self.assertFalse(removed.exists())

    def test_324_permission_and_provisioning_claims_cannot_add_replay_or_open_join(self):
        changes = [lambda r: r["permissionTrace"][1].update(granted=False),
                   lambda r: r["permissionTrace"][1].update(requestCode=123),
                   lambda r: r["provisioningCalls"].append(copy.deepcopy(r["provisioningCalls"][0])),
                   lambda r: r["provisioningCalls"][0].update(protected=False),
                   lambda r: r["provisioningCalls"][1].update(signals=["JoinFailed", "NetworkJoined"])]
        for index, change in enumerate(changes):
            fixture = self.fixture("324")
            change(fixture.report)
            fixture.save()
            with self.subTest(change=index):
                self.assert_status(fixture, "REJECTED")

    def test_unexpected_files_empty_lock_corruption_and_jsonl_truncation_rejected_without_import(self):
        fixture = self.fixture()
        marker = fixture.root.parent / "should-not-exist"
        (fixture.root / "collector.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        self.assert_status(fixture, "REJECTED")
        self.assertFalse(marker.exists())
        fixture = self.fixture("324")
        (fixture.root / "fixture/no-backup/test-diagnostics/.diagnostic-events.jsonl.lock").write_bytes(b"not empty")
        self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        file = fixture.root / "events.jsonl"
        file.write_bytes(file.read_bytes().rstrip(b"\n"))
        self.assert_status(fixture, "REJECTED")

    def test_links_aliases_traversal_and_nonregular_files_rejected(self):
        for kind in ("symlink", "hardlink", "fifo"):
            fixture = self.fixture()
            file = fixture.root / "before.png"
            original = fixture.root.parent / "original.png"
            file.rename(original)
            if kind == "symlink":
                file.symlink_to(original)
            elif kind == "hardlink":
                os.link(original, file)
            else:
                os.mkfifo(file)
            with self.subTest(kind=kind):
                self.assert_status(fixture, "REJECTED")
        fixture = self.fixture("324")
        cache = fixture.root / "fixture/cache"
        cache.rmdir()
        cache.symlink_to(fixture.root.parent, target_is_directory=True)
        self.assert_status(fixture, "REJECTED")
        fixture = self.fixture()
        with self.assertRaises(subject.Rejected):
            subject.checked_path(fixture.root / ".." / fixture.root.name)

    def test_changed_input_and_host_resource_bounds_fail_closed(self):
        file = self.root / "small"
        file.write_bytes(b"first")
        snapshot = subject.Snapshot("317")
        snapshot.read(file, 5)
        stamp = file.stat()
        os.utime(file, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        with self.assertRaises(subject.Rejected):
            snapshot.unchanged()
        for name, bound, case in (("PNG_LIMIT", 32, "317"), ("STREAM_LIMIT", 1, "317"),
                                  ("TEXT_LIMIT", 1, "324"), ("PARCEL_LIMIT", 1, "324"), ("FILE_LIMIT", 1, "317"),
                                  ("DIRECTORY_LIMIT", 1, "324"), ("DEPTH_LIMIT", 0, "324"),
                                  ("TOTAL_LIMITS", {"317": 1, "324": 1}, "317")):
            fixture = self.fixture(case)
            with self.subTest(bound=name), mock.patch.object(subject, name, bound):
                self.assert_status(fixture, "REJECTED")
        with mock.patch.object(subject.time, "monotonic", return_value=snapshot.deadline + 1):
            with self.assertRaises(subject.Rejected):
                snapshot.bound()

    def test_failed_partial_and_missing_results_stay_distinct_and_unchanged(self):
        for case in ("317", "324"):
            fixture = self.fixture(case)
            fixture.fail()
            originals = {path: path.read_bytes() for path in fixture.root.rglob("*") if path.is_file()}
            result = self.assert_status(fixture, "HARNESS_FAILED")
            self.assertEqual(result["harnessOutcome"], "FAIL")
            self.assertEqual(originals, {path: path.read_bytes() for path in originals})
            name = "before.png" if case == "317" else "initial-card.png"
            (fixture.root / name).unlink()
            self.assert_status(fixture, "INCOMPLETE")
            (fixture.root / "result.json").unlink()
            self.assert_status(fixture, "INCOMPLETE")
        fixture = self.fixture()
        fixture.fail()
        fixture.report["failure"]["stage"] = "another-stage"
        fixture.save()
        self.assert_status(fixture, "REJECTED")

    def test_failed_empty_export_and_317_failure_capture_are_preserved(self):
        fixture = self.fixture("324")
        fixture.fail()
        (fixture.root / "events.jsonl").write_bytes(b"")
        self.assert_status(fixture, "HARNESS_FAILED")
        fixture = self.fixture()
        fixture.fail()
        del fixture.report["afterScreenshot"]
        (fixture.root / "after.png").rename(fixture.root / "failed.png")
        (fixture.root / "after-tree.json").rename(fixture.root / "failed-tree.json")
        fixture.report["failedScreenshot"] = {"file": "failed.png", "width": 2, "height": 2,
                                               "sha256": sha((fixture.root / "failed.png").read_bytes()), "targets": []}
        fixture.save()
        result = self.assert_status(fixture, "HARNESS_FAILED")
        self.assertIn("failed.png", [row["path"] for row in result["files"]])

    def test_cli_exit_codes_do_not_grant_acceptance(self):
        for expected, code in (("CONSISTENT", 0), ("HARNESS_FAILED", 1), ("INCOMPLETE", 2), ("REJECTED", 3)):
            fixture = self.fixture()
            if expected == "HARNESS_FAILED":
                fixture.fail()
            elif expected == "INCOMPLETE":
                (fixture.root / "result.json").unlink()
            elif expected == "REJECTED":
                fixture.report["targetSdk"] = 36
                fixture.save()
            argv = ["verify-android-ui-evidence.py", "--case", "317", "--token", TOKEN, "--source-commit", COMMIT,
                    "--source-tree", TREE, "--evidence-dir", str(fixture.root), "--instrumentation-stdout", str(fixture.stdout)]
            output = io.StringIO()
            with self.subTest(status=expected), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
                self.assertEqual(subject.main(), code)
            result = json.loads(output.getvalue())
            self.assertEqual(result["contentStatus"], expected)
            self.assertEqual(result["runtimeAcceptance"], "NOT_ACCEPTED")


if __name__ == "__main__":
    unittest.main()
