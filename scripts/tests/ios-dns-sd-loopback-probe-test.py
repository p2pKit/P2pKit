#!/usr/bin/env python3
"""One pure admission control group; no native process, network or simulator is invoked."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("loopback_diagnostic", ROOT / "scripts/run-ios-dns-sd-loopback-probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
GATE, SIM = PROBE.GATE, PROBE.SIM


def fixture():
    source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": SIM.digest(b"")}
    github = {"actions": "true", "repository": "p2pKit/P2pKit", "runId": "123456789",
              "runAttempt": "1", "sha": source["commit"], "ref": "refs/heads/work/loopback-control",
              "job": "loopback-route-probe"}
    selected = {"runtime": {"identifier": SIM.HOSTS["macos-x64"]["runtime"], "version": "26.2", "isAvailable": True},
                "device": {"udid": "11111111-1111-1111-1111-111111111111", "name": "iPhone 17",
                           "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17",
                           "isAvailable": True, "state": "Shutdown"}}
    native = {"schema": 1, "scope": PROBE.NATIVE_SCOPE, "source": source["commit"], "runId": github["runId"],
              "runAttempt": 1, "target": "IOS_SIMULATOR_X86_64", "status": "PASS", "reason": "NONE",
              **{key: True for key in PROBE.BOOLS}, **{key: 1 for key in PROBE.CALLS},
              **{key: 0 for key in PROBE.CODES}, "registerCallbacks": 1, "queryCallbacks": 2,
              "removeCallbacks": 0, "aCallbacks": 1, "bCallbacks": 1,
              "firstScope": "CONCRETE", "updateScope": "CONCRETE", "updateElapsedMs": 12,
              "publisherCleanup": "COMPLETE", "queryCleanup": "COMPLETE"}
    def devices(state):
        return SIM.encoded({"devices": {selected["runtime"]["identifier"]: [{**selected["device"], "state": state}]}})
    outputs = {
        "simulator-macos-version": b"15.7\n", "simulator-xcode-version": SIM.HOSTS["macos-x64"]["xcode"].encode(),
        "simulator-first-launch": b"", "simulator-runtimes": SIM.encoded({"runtimes": [selected["runtime"]]}),
        "intel-bootstatus-help": b"Usage: simctl bootstatus <device>\n", "simulator-devices": devices("Shutdown"),
        "intel-boot": b"", "intel-bootstatus": b"", "intel-prelaunch": devices("Booted"),
        "probe-sdk-path": (PROBE.DEVELOPER + "/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator26.2.sdk\n").encode(),
        "probe-sdk-version": b"26.2\n",
        "probe-clang-path": (PROBE.DEVELOPER + "/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang\n").encode(),
        "probe-spawn-help": b"Usage: simctl spawn <device> <executable>\n", "probe-compile": b"",
        "probe-execute": SIM.encoded(native), "intel-retire-before": devices("Booted"),
        "intel-shutdown": b"", "intel-retire-after": devices("Shutdown"),
    }
    originals = {label + "/stdout.bin": raw for label, raw in outputs.items()}
    originals.update({label + "/stderr.bin": b"" for label in outputs})
    token = "c" * 32
    commands = PROBE.custom_commands(source, github, token, selected, originals, str(ROOT))
    start = datetime(2026, 10, 9, tzinfo=timezone.utc)
    for index, label in enumerate(PROBE.LABELS):
        raw = outputs[label]
        row = {"schema": 1, "label": label, "argv": commands[label] if label in commands else
               GATE._intel_phase_command(label, selected), "cwd": str(ROOT),
               "startedUtc": (start + timedelta(seconds=index * 2)).isoformat(),
               "finishedUtc": (start + timedelta(seconds=index * 2 + 1)).isoformat(),
               "exitCode": 0, "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True,
               "stdoutBytes": len(raw), "stdoutSha256": SIM.digest(raw), "stderrBytes": 0,
               "stderrSha256": SIM.digest(b"")}
        originals[label + "/result.json"] = SIM.encoded(row)
        originals[label + "/stderr.bin"] = b""
    retirement = {"schema": 1, "scope": GATE.INTEL_RETIREMENT_SCOPE, "root": str(ROOT), "token": token,
                  "source": source, "selected": selected, "bindingSha256": None, "shutdownIssued": True,
                  "originals": GATE._intel_references({key: value for key, value in originals.items()
                                if key in GATE._intel_paths(GATE.INTEL_RETIRE)}),
                  "deviceAfter": {**selected["device"], "state": "Shutdown"}, "errors": []}
    receipt = {"schema": 1, "scope": PROBE.SCOPE, "role": "macos-x64", "root": str(ROOT), "token": token,
               "source": source, "sourceAfter": copy.deepcopy(source), "github": github,
               "developerDir": PROBE.DEVELOPER, "selected": selected,
               "binary": {"path": commands["probe-execute"][-2], "bytes": 65536, "sha256": "d" * 64},
               "cSourceSha256": "e" * 64, "originals": GATE._intel_references(originals),
               "retirement": SIM.encoded(retirement)}
    return receipt, originals


def refresh(receipt, originals):
    """Rehash intentional synthetic changes so admission must check meaning, not only custody."""
    for label in PROBE.LABELS:
        row = SIM.parse(originals[label + "/result.json"])
        for stream in ("stdout", "stderr"):
            raw = originals[label + "/" + stream + ".bin"]
            row[stream + "Bytes"], row[stream + "Sha256"] = len(raw), SIM.digest(raw)
        originals[label + "/result.json"] = SIM.encoded(row)
    receipt["originals"] = GATE._intel_references(originals)
    retired = SIM.parse(receipt["retirement"])
    retired["originals"] = GATE._intel_references({key: value for key, value in originals.items()
                            if key in GATE._intel_paths(GATE.INTEL_RETIRE)})
    receipt["retirement"] = SIM.encoded(retired)


class LoopbackRouteControls(unittest.TestCase):
    def test_closed_native_route_and_owned_original_admission(self):
        # Real maintained suppliers and the actual C schema are data dependencies, not executed native fixtures.
        c_source = PROBE.public_source(ROOT / PROBE.C_SOURCE).decode("ascii")
        specs = c_source.split("FIELDS[FIELD_COUNT] = {", 1)[1].split("};", 1)[0]
        self.assertEqual(set(re.findall(r'\{"([A-Za-z]+)",', specs)),
                         {*PROBE.BOOLS, *PROBE.CALLS, *PROBE.CODES, *PROBE.COUNTS,
                          "firstScope", "updateScope", "updateElapsedMs", "publisherCleanup", "queryCleanup"})
        for table, expected in (("REASONS", PROBE.REASONS), ("SCOPES", PROBE.SCOPES),
                                ("CLEANUPS", ("NOT_STARTED", "COMPLETE", "TIMED_OUT"))):
            body = c_source.split(table + "[] = {", 1)[1].split("};", 1)[0]
            self.assertEqual(tuple(re.findall(r'"([A-Z_]+)"', body)), expected)
        self.assertIn("#if !TARGET_OS_SIMULATOR || !TARGET_OS_IOS || !defined(__x86_64__)", c_source)
        for macro in ("P2PKIT_PROBE_SOURCE", "P2PKIT_PROBE_RUN", "P2PKIT_PROBE_ATTEMPT"):
            self.assertIn("#ifndef " + macro, c_source)
        receipt, originals = fixture()
        accepted = PROBE.admit_evidence(receipt, originals)
        self.assertTrue(accepted["routeDemonstrated"])
        self.assertTrue(accepted["selectedSimulatorRetired"])
        self.assertFalse(accepted["nativeQualification"])
        self.assertFalse(accepted["physicalNetworkCoverage"])
        self.assertEqual(GATE.INTEL_BOOTSTATUS_SECONDS, 300)
        self.assertEqual(SIM.SECONDS, 120)
        self.assertEqual((GATE.TERMINATION_GRACE_SECONDS, GATE.TERMINATION_KILL_SECONDS), (15, 5))

        def rejection(name, mutate):
            candidate, records = copy.deepcopy(receipt), originals.copy()
            mutate(candidate, records)
            refresh(candidate, records)
            with self.subTest(name=name), self.assertRaises(ValueError):
                PROBE.admit_evidence(candidate, records)

        def native_change(key, value):
            def mutate(_receipt, records):
                row = SIM.parse(records["probe-execute/stdout.bin"])
                row[key] = value
                records["probe-execute/stdout.bin"] = SIM.encoded(row)
            return mutate

        def phase_change(label, key, value):
            def mutate(_receipt, records):
                row = SIM.parse(records[label + "/result.json"])
                row[key] = value
                records[label + "/result.json"] = SIM.encoded(row)
            return mutate

        for key, bad in (("source", "f" * 40), ("runId", "2"), ("runAttempt", 2), ("target", "MACOS_X86_64"),
                         ("interfaceValidated", False), ("listenerPreserved", False), ("initialA", False),
                         ("updatedB", False), ("publisherRefPreserved", False), ("queryRefPreserved", False),
                         ("contextReleased", False), ("registerCalls", 2), ("queryCalls", 2), ("updateCalls", 2),
                         ("updateElapsedMs", 30000), ("publisherCleanup", "TIMED_OUT"),
                         ("queryCleanup", "NOT_STARTED"), ("firstScope", "NONE"), ("updateScope", "lo0"),
                         ("queryCode", True), ("queryCallbacks", 1025), ("registerCallbackCode", -1),
                         ("queryCallbackCode", -1), ("aCallbacks", 0), ("bCallbacks", 0)):
            rejection("native-" + key, native_change(key, bad))
        rejection("wrong-role", lambda r, _: r.update(role="macos-arm64"))
        rejection("wrong-scope", lambda r, _: r.update(scope=GATE.INTEL_SCOPE))
        rejection("changed-source", lambda r, _: r["sourceAfter"].update(commit="f" * 40))
        rejection("wrong-github", lambda r, _: r["github"].update(sha="f" * 40))
        rejection("changed-binary-path", lambda r, _: r["binary"].update(path="/tmp/another-binary"))
        rejection("wrong-native-command", phase_change("probe-execute", "argv", ["/bin/true"]))
        rejection("nonzero-native-exit", phase_change("probe-execute", "exitCode", 1))
        rejection("not-drained", phase_change("probe-execute", "ownedGroupDrained", False))
        rejection("timed-out", phase_change("probe-execute", "timedOut", True))
        rejection("overflow", phase_change("probe-execute", "outputLimitExceeded", True))
        rejection("bad-order", phase_change("probe-execute", "startedUtc", "2026-10-09T00:00:00+00:00"))
        rejection("late-phase", phase_change("probe-execute", "finishedUtc", "2026-10-09T00:10:00+00:00"))
        rejection("late-boot", phase_change("intel-bootstatus", "finishedUtc", "2026-10-09T00:10:00+00:00"))
        rejection("retirement-order", phase_change("intel-shutdown", "startedUtc", "2026-10-09T00:00:00+00:00"))

        for key, bad in (("shutdownIssued", False), ("errors", ["INTEL_SHUTDOWN_FAILED"]),
                         ("bindingSha256", "f" * 64)):
            def retirement_change(r, _records, key=key, bad=bad):
                value = SIM.parse(r["retirement"])
                value[key] = bad
                r["retirement"] = SIM.encoded(value)
            rejection("retirement-" + key, retirement_change)
        for label, state in (("intel-prelaunch", "Shutdown"), ("intel-retire-before", "Shutdown"),
                             ("intel-retire-after", "Booted")):
            def wrong_state(r, records, label=label, state=state):
                row = {**r["selected"]["device"], "state": state}
                records[label + "/stdout.bin"] = SIM.encoded({"devices": {r["selected"]["runtime"]["identifier"]: [row]}})
            rejection("state-" + label, wrong_state)
        rejection("device-owner", lambda r, _: r["selected"]["device"].update(
            udid="22222222-2222-2222-2222-222222222222"))
        rejection("duplicate-native-field", lambda _, records: records.update({"probe-execute/stdout.bin":
            records["probe-execute/stdout.bin"].replace(b'{', b'{"schema":1,', 1)}))
        rejection("extra-raw-field", native_change("rawInterfaceIndex", 1))
        rejection("oversized-native", lambda _, records: records.update({"probe-execute/stdout.bin": b" " * 8193 + b"\n"}))

        # Any observed scope is context, not an invented interface-equality/physical-network gate.
        for scope in PROBE.SCOPES[1:]:
            candidate, records = copy.deepcopy(receipt), originals.copy()
            native_change("updateScope", scope)(candidate, records)
            native_change("updateElapsedMs", 29999)(candidate, records)
            refresh(candidate, records)
            self.assertTrue(PROBE.admit_evidence(candidate, records)["routeDemonstrated"])
        failed = SIM.parse(originals["probe-execute/stdout.bin"])
        failed.update(status="FAIL", reason="UPDATE_TIMEOUT", updatedB=False, bCallbacks=0,
                      updateScope="NONE", updateElapsedMs=None)
        self.assertEqual(PROBE.native_record(SIM.encoded(failed), receipt["source"], receipt["github"])["reason"],
                         "UPDATE_TIMEOUT")
        self.assertTrue(PROBE.verify_retirement(receipt, originals))


if __name__ == "__main__":
    unittest.main(failfast=True)
