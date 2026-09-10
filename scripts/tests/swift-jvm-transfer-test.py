#!/usr/bin/env python3
"""Small modeled admission/result/cleanup checks; never native transfer evidence."""
import copy
import hashlib
import importlib.util
import json
import os
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

    def test_quit_timeout_dump_binds_the_unreaped_child_and_bounds_only_one_diagnostic(self):
        for fault in (None, "reaped", "parent", "domain", "exec-version", "attach-failed", "attach-timeout"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix="swift-jvm-dump-") as temporary:
                directory = Path(temporary).resolve()
                java_home = directory / "jdk17"
                (java_home / "bin").mkdir(parents=True)
                jcmd = java_home / "bin/jcmd"
                jcmd.write_text("synthetic tool; never execute\n")
                jcmd.chmod(0o700)
                experiment = object.__new__(TRANSFER.Experiment)
                experiment.directory = directory
                experiment.context = {"javaHomes": [str(java_home)]}
                experiment.ownership_domain = {"job": "a" * 32, "id": "b" * 32,
                                               "state": str(directory), "home": str(directory / "home")}
                experiment.record = {"result": "FAIL", "unresolvedChildren": []}
                experiment.audit = types.SimpleNamespace(utc=lambda: "synthetic-clock",
                    reject_symlinks=lambda path: None, new_file=lambda path: path.open("xb"))
                cli = mock.Mock(pid=9000, returncode=0 if fault == "reaped" else None,
                                args=[str(java_home / "bin/java")])
                cli.poll.side_effect = AssertionError("Do not reap the target during attach")
                cli.wait.side_effect = AssertionError("The natural30s wait has already failed")
                experiment.cli = cli
                owner = {"pid": os.getpid(), "uid": os.getuid(), "uniqueId": 41}
                target = {"pid": cli.pid, "uid": owner["uid"], "uniqueId": 42, "startSeconds": 10,
                          "startMicroseconds": 20, "pidVersion": 1, "live": True,
                          "parentPid": os.getpid(), "parentUniqueId": 99 if fault == "parent" else 41}
                identities = 0
                def identity(pid, *, required):
                    nonlocal identities
                    self.assertTrue(required)
                    if pid == os.getpid():
                        return dict(owner)
                    self.assertEqual(cli.pid, pid)
                    identities += 1
                    return dict(target, pidVersion=2 if fault == "exec-version" and identities > 1 else 1)
                observer = mock.Mock()
                observer._identity.side_effect = identity
                observer._key.side_effect = lambda value: tuple(value[key] for key in
                    ("pid", "uniqueId", "startSeconds", "startMicroseconds"))
                observer._ours.return_value = fault != "domain"
                factory = mock.Mock(return_value=observer)
                child = mock.Mock(pid=9001, returncode=None if fault == "attach-timeout" else 7 if fault == "attach-failed" else 0)
                if fault == "attach-timeout":
                    child.wait.side_effect = subprocess.TimeoutExpired("synthetic-jcmd", 10)
                else:
                    child.wait.return_value = child.returncode
                def launch(command, **options):
                    self.assertEqual([str(jcmd), "-J-Xmx64m", "-J-XX:MaxMetaspaceSize=128m",
                        "-J-XX:ActiveProcessorCount=2", str(cli.pid), "Thread.print", "-l"], command)
                    self.assertEqual(subprocess.DEVNULL, options["stdin"])
                    options["preexec_fn"]()  # Modeled only; setrlimit below is intercepted.
                    options["stdout"].write(b"synthetic thread observation, not native evidence\n")
                    return child
                with mock.patch.dict(sys.modules, {"audit_processes": types.SimpleNamespace(DarwinScope=factory)}), \
                        mock.patch.object(TRANSFER.subprocess, "Popen", side_effect=launch) as popen, \
                        mock.patch.object(TRANSFER.resource, "setrlimit") as limit:
                    experiment.observe_cli_quit_timeout()
                observed = experiment.record["cliQuitThreadDump"]
                self.assertEqual("FAIL", experiment.record["result"])
                rejected = fault in ("reaped", "parent", "domain", "exec-version")
                self.assertEqual(int(not rejected), popen.call_count)
                self.assertEqual(rejected, "error" in observed)
                if not rejected:
                    child.wait.assert_called_once_with(timeout=10)
                    limit.assert_called_once_with(TRANSFER.resource.RLIMIT_FSIZE, (2 * TRANSFER.MIB, 2 * TRANSFER.MIB))
                    self.assertTrue(observed["auditTokenAcquired"])
                    self.assertEqual(10, observed["toolTimeoutSeconds"])
                    self.assertFalse(observed["outputLimitReached"])
                    self.assertEqual(fault == "attach-timeout", observed.get("timedOut", False))
                    self.assertEqual([] if fault != "attach-timeout" else
                                     [{"kind": "cli-quit-thread-dump", "pid": child.pid}],
                                     experiment.record["unresolvedChildren"])
                    if fault != "attach-timeout":
                        self.assertEqual(child.returncode, observed["exitCode"])
                cli.poll.assert_not_called()
                cli.wait.assert_not_called()
                cli.terminate.assert_not_called()
                cli.kill.assert_not_called()
                child.terminate.assert_not_called()
                child.kill.assert_not_called()
                observer.signal_all.assert_not_called()
                observer.drain.assert_not_called()
                if fault != "reaped":
                    observer.close.assert_called_once_with()

    def test_only_natural_quit_timeout_observes_threads_and_original_failure_is_preserved(self):
        for timed_out in (False, True):
            with self.subTest(timed_out=timed_out), tempfile.TemporaryDirectory(prefix="swift-jvm-quit-") as temporary:
                directory = Path(temporary).resolve()
                experiment = object.__new__(TRANSFER.Experiment)
                experiment.directory = directory
                experiment.identity = directory.stat().st_dev, directory.stat().st_ino
                experiment.home = directory / "home"
                experiment.home.mkdir()
                experiment.name = "synthetic.bin"
                (directory / experiment.name).write_bytes(b"synthetic fixture")
                (directory / "cli.stdout.log").write_text("Stopping…\n")
                (directory / "cli.stderr.log").write_bytes(b"")
                experiment.audit = types.SimpleNamespace(utc=lambda: "synthetic-clock", reject_symlinks=lambda path: None,
                    source_snapshot=lambda root: {"fixture": "source"},
                    write_new_json=lambda path, value: path.write_text(json.dumps(value)))
                experiment.context = {"source": {"fixture": "source"}}
                experiment.xcode = experiment.xctestrun = experiment.received_identity = None
                experiment.record = {"result": "PASS", "cleanupErrors": [], "unresolvedChildren": []}
                cli = mock.Mock(pid=9000, returncode=None)
                cli.stdin.closed = False
                cli.stdin.close.side_effect = lambda: setattr(cli.stdin, "closed", True)
                cli.poll.side_effect = lambda: cli.returncode
                def wait(*, timeout):
                    self.assertEqual(30, timeout)
                    if timed_out:
                        raise subprocess.TimeoutExpired("synthetic-cli", 30)
                    cli.returncode = 0
                    return 0
                cli.wait.side_effect = wait
                experiment.cli = cli
                experiment.events = mock.Mock(return_value=[{"eventName": "application.shutdown"}])
                with mock.patch.object(TRANSFER.signal, "signal"), mock.patch("builtins.print"), \
                        mock.patch.object(experiment, "observe_cli_quit_timeout") as observe:
                    self.assertEqual(int(timed_out), experiment.finish())
                self.assertEqual(int(timed_out), observe.call_count)
                cli.stdin.write.assert_called_once_with(b"quit\n")
                cli.stdin.flush.assert_called_once_with()
                result = json.loads((directory / "result.json").read_text())
                self.assertEqual("FAIL" if timed_out else "PASS", result["result"])
                self.assertEqual(timed_out, "cliQuitTimeoutUtc" in result)
                self.assertEqual(timed_out, experiment.home.exists())
                if timed_out:
                    self.assertTrue(any("timed out after 30 seconds" in error for error in result["cleanupErrors"]))
                    self.assertEqual([{"kind": "cli", "pid": cli.pid}], result["unresolvedChildren"])

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
