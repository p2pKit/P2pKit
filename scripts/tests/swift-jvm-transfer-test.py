#!/usr/bin/env python3
"""Small modeled admission/result/cleanup checks; never native transfer evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("swift_jvm_transfer_under_test", ROOT / "scripts/run-swift-jvm-transfer.py")
TRANSFER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSFER)


def prepared():
    return {"TestConfigurations": [{"TestTargets": [{"BlueprintName": TRANSFER.TARGET, "IsUITestBundle": True,
            "TestBundlePath": "__TESTROOT__/runner.app/PlugIns/tests.xctest", "TestHostPath": "__TESTROOT__/runner.app",
            "UITargetAppPath": "__TESTROOT__/Debug-iphonesimulator/p2pkit-sample.app",
            "EnvironmentVariables": {"UNCHANGED": "retain-original-target-environment"}}]}]}


def xcresult(status="Success", identifier=TRANSFER.CASE):
    return [{"_type": {"_name": "ActionTestableSummary"}, "targetName": {"_value": TRANSFER.TARGET}, "tests": [
        {"_type": {"_name": "ActionTestMetadata"}, "identifier": {"_value": identifier},
         "testStatus": {"_value": status}}]}]


def diagnostic_rows(*, swift, receiver):
    owner = {"sdkSessionId": "anon-local-owner", "connectionId": "conn-local-endpoint",
             "peerId": "anon-peer", "protocolVersion": "secure-v2"}
    connected = {**owner, "eventName": "connection.state.changed", "currentState": "Connected",
                 "previousState": None, "outcome": None if swift else "SUCCESS"}
    negotiated = {**owner, "eventName": "protocol.secure_v2.negotiated", "currentState": "secure-v2",
                  "outcome": "SUCCESS" if swift else None,
                  "details": {} if swift else {"feature": "file-commit-sha256-v1"}}
    rows = [connected, negotiated]
    if not swift:
        # Real CLI: initial registerConnection, then initial StateFlow emission.
        rows += [{**connected, "previousState": "Connected"}, copy.deepcopy(negotiated)]
    names = ["file.receiver.sha256" if receiver else "file.sender.sha256"]
    if swift or not receiver:
        names.append("transfer.completed")
    if receiver:
        names += ["transfer.offer.received", "transfer.offer.accepted", "transfer.durable.committed"]
    for name in names:
        row = {**owner, "eventName": name, "transferId": "synthetic-transfer", "payloadSizeBytes": TRANSFER.SIZE,
               "protocolVersion": "secure-v2", "direction": "RECEIVED" if receiver else "SENT"}
        if name.endswith(".sha256"):
            row["details"] = {"sha256": "a" * 64}
        if name in ("transfer.completed", "transfer.durable.committed"):
            row.update(outcome="SUCCESS", currentState="durably-persisted" if swift and
                       name == "transfer.durable.committed" else "Completed")
        if not swift and name == "transfer.completed":
            row["direction"] = "LOCAL"  # Real CLI sender terminal observer contract.
        rows.append(row)
    if not swift:
        rows.append({**owner, "eventName": "connection.state.changed", "currentState": "Closed",
                     "previousState": "Connected", "outcome": "CANCELLATION"})
    return rows


class SwiftJvmTransferControls(unittest.TestCase):
    def test_fixture_targets_exact_ui_bundle_and_preserves_ownership_and_original_environment(self):
        environment = {name: "synthetic-" + name for name in TRANSFER.OWNERSHIP}
        fixture = {"P2PKIT_JVM_NONCE": "1" * 32}
        document = prepared()
        target = TRANSFER.inject_fixture(document, fixture, environment)
        self.assertEqual({**environment, **fixture, "UNCHANGED": "retain-original-target-environment"},
                         target["EnvironmentVariables"])
        self.assertIs(target, TRANSFER.peer_target({TRANSFER.TARGET: target, "__xctestrun_metadata__": {}}))
        for mutation in ("ambiguous", "wrong-target", "disabled", "skip", "environment-conflict"):
            with self.subTest(mutation=mutation):
                invalid = prepared()
                config = invalid["TestConfigurations"][0]
                target = config["TestTargets"][0]
                if mutation == "ambiguous":
                    config["TestTargets"].append(copy.deepcopy(target))
                elif mutation == "wrong-target":
                    target["BlueprintName"] = "ordinary-ui-target"
                elif mutation == "disabled":
                    config["IsEnabled"] = False
                elif mutation == "skip":
                    target["SkipTestIdentifiers"] = [TRANSFER.CASE]
                else:
                    target["EnvironmentVariables"][TRANSFER.OWNERSHIP[0]] = "foreign-job"
                with self.assertRaises(ValueError):
                    TRANSFER.inject_fixture(invalid, fixture, environment)

    def test_native_case_must_be_exact_nonempty_unique_and_successful(self):
        self.assertEqual("Success", TRANSFER.assess_case(xcresult())["status"])
        for objects in ([], xcresult("Skipped"), xcresult("Failure"), xcresult(identifier="Other/testCase()"),
                        xcresult() + xcresult()):
            with self.subTest(objects=objects), self.assertRaises(ValueError):
                TRANSFER.assess_case(objects)

    def test_integrity_and_terminal_evidence_respect_actual_endpoint_contracts(self):
        for swift, receiver in ((True, True), (True, False), (False, True), (False, False)):
            with self.subTest(swift=swift, receiver=receiver):
                rows = diagnostic_rows(swift=swift, receiver=receiver)
                evidence = TRANSFER.transfer_evidence(rows, "synthetic-transfer", "a" * 64,
                                                     swift=swift, receiver=receiver)
                self.assertEqual("anon-local-owner", evidence["sdkSessionId"])
                faults = ("wrong-owner", "wrong-hash", "wrong-size", "missing-terminal", "contradictory-failure",
                          "extra-connected-owner", "reconnect")
                if not swift:
                    faults += ("rearmed-snapshot", "contradictory-negotiation")
                for fault in faults:
                    with self.subTest(fault=fault):
                        broken = copy.deepcopy(rows)
                        transfers = [row for row in broken if row.get("transferId") == "synthetic-transfer"]
                        connections = TRANSFER.selected(broken, "connection.state.changed", currentState="Connected")
                        if fault == "wrong-owner":
                            transfers[-1]["sdkSessionId"] = "foreign-owner"
                        elif fault == "wrong-hash":
                            transfers[0]["details"]["sha256"] = "b" * 64
                        elif fault == "wrong-size":
                            transfers[0]["payloadSizeBytes"] = TRANSFER.SIZE - 1
                        elif fault == "missing-terminal":
                            broken = [row for row in broken if row["eventName"] not in
                                      ("transfer.completed", "transfer.durable.committed")]
                        elif fault == "contradictory-failure":
                            broken.append({"eventName": "transfer.failed", "transferId": "synthetic-transfer"})
                        elif fault == "extra-connected-owner":
                            connections[-1]["sdkSessionId"] = "foreign-owner"
                        elif fault == "reconnect":
                            broken.insert(2, {**connections[0], "previousState": "Connected",
                                              "currentState": "Reconnecting", "outcome": "INTERRUPTION"})
                        elif fault == "rearmed-snapshot":
                            connections[-1]["previousState"] = None
                        else:
                            TRANSFER.selected(broken, "protocol.secure_v2.negotiated")[-1]["details"]["feature"] = "other"
                        with self.assertRaises(ValueError):
                            TRANSFER.transfer_evidence(broken, "synthetic-transfer", "a" * 64,
                                                       swift=swift, receiver=receiver)

    def test_exact_committed_file_read_and_unresolved_child_refuse_success_without_signaling(self):
        with tempfile.TemporaryDirectory(prefix="swift-jvm-controls-") as temporary:
            directory = Path(temporary).resolve()
            experiment = object.__new__(TRANSFER.Experiment)
            experiment.directory = directory
            experiment.identity = directory.stat().st_dev, directory.stat().st_ino
            experiment.home = directory / "home"
            experiment.home.mkdir()
            sentinel = experiment.home / "retain-until-owned-drain.txt"
            sentinel.write_text("still belongs to the live invocation\n")
            experiment.audit = types.SimpleNamespace(
                reject_symlinks=lambda path: None, source_snapshot=lambda root: {"fixture": "source"},
                write_new_json=lambda path, value: path.write_text(json.dumps(value)))
            experiment.context = {"source": {"fixture": "source"}}
            experiment.cli = None
            experiment.xctestrun = None
            experiment.received_identity = None
            experiment.name = "synthetic.bin"
            experiment.record = {"result": "PASS", "cleanupErrors": [], "unresolvedChildren": []}
            payload = directory / experiment.name
            raw = TRANSFER.pattern(17, 11)
            payload.write_bytes(raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), experiment.verify_file(payload, raw)["sha256"])
            payload.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            with self.assertRaises(ValueError):
                experiment.verify_file(payload, raw)
            experiment.xcode = mock.Mock(pid=9999)
            experiment.xcode.poll.return_value = None
            experiment.xcode.wait.side_effect = subprocess.TimeoutExpired("synthetic-xcode", 10)
            with mock.patch.object(TRANSFER.signal, "signal") as handlers, mock.patch("builtins.print"):
                self.assertEqual(1, experiment.finish())
            self.assertEqual([mock.call(signal.SIGINT, signal.SIG_IGN), mock.call(signal.SIGTERM, signal.SIG_IGN)],
                             handlers.call_args_list)
            experiment.xcode.terminate.assert_not_called()
            experiment.xcode.kill.assert_not_called()
            self.assertTrue(sentinel.is_file())
            result = json.loads((directory / "result.json").read_text())
            self.assertEqual("FAIL", result["result"])
            self.assertEqual([{"kind": "xcodebuild", "pid": 9999}], result["unresolvedChildren"])
            self.assertTrue(result["cleanupErrors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
