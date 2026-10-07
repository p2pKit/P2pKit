#!/usr/bin/env python3
"""Offline controls for the isolated BARE descriptor pair, not native acceptance."""
import ast
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("lan_host_diagnostic", ROOT / "scripts/diagnostics/intel-lan-host/run.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)

# Synthetic unit inputs only: no hosted run, source, token or simulator claim.
TOKENS = {"BONJOUR": "a" * 32, "WITH_TXT": "b" * 32}
SOURCE = {"commit": "c" * 40, "tree": "d" * 40}
CONTEXT = {"GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "ios-x64"}
UDID = "11111111-2222-3333-4444-555555555555"
CONFIG_BOOLS = {"listenerObserved", "listenerNoDelay", "listenerP2P", "listenerCellBan",
                "browserObserved", "browserP2P", "browserCellBan", "browserIncludesTXT",
                "advertisementAfterReady", "noAutoRename", "configuredServiceTxtPresent",
                "configuredServiceTxtReadbackMatches", "configuredServiceTxtShapeValid"}


def fixture(policy="BONJOUR", discovered=False):
    peer = {key: 0 for key in D.COUNTERS}
    peer.update({key: False for key in D.PEER_BOOLS})
    peer.update(listenerReady=1, browserReady=1, listenerCancelled=True, browserCancelled=True,
                listenerLastState="ready", browserLastState="ready",
                listenerError={"domain": "none", "code": 0}, browserError={"domain": "none", "code": 0})
    peer["configuration"] = {key: True for key in CONFIG_BOOLS}
    peer["configuration"].update(listenerTransport="tcp", browserTransport="none",
                                 browserIncludesTXT=policy == "WITH_TXT")
    if discovered:
        peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=1,
                    ownRegistrationObserved=True, registrationAdded=1)
    return {"schema": 1, "diagnosticOnly": True, "mode": "cli", "browserDescriptor": policy,
            "outcome": "discovered" if discovered else "notDiscovered", "windowMilliseconds": 30000,
            "observationElapsedMilliseconds": 30001, "cleanupElapsedMilliseconds": 10,
            "isSimulatorBuild": True, "isX86_64Build": True, "counterOverflow": False,
            "packaging": {key: False for key in D.PACKAGE_KEYS},
            "peers": [copy.deepcopy(peer), copy.deepcopy(peer)],
            "cleanup": {"listenersCreated": 2, "listenersCancelled": 2, "browsersCreated": 2,
                        "browsersCancelled": 2, "complete": True}}


def streams(probe=None, policy="BONJOUR", token=None, **extra):
    value = {"schema": 1, "token": TOKENS[policy] if token is None else token,
             "browserDescriptor": policy, "probe": fixture(policy) if probe is None else probe}
    value.update(extra)
    return {"stdout": b"P2PKIT_LAN_BROWSER_DESCRIPTOR_V1 " + json.dumps(value).encode() + b"\n", "stderr": b""}


class DiagnosticControls(unittest.TestCase):
    def test_two_policies_use_closed_actual_parameter_readbacks(self):
        self.assertEqual(("BONJOUR", "WITH_TXT"), D.POLICIES)
        self.assertEqual(CONFIG_BOOLS, D.CONFIG_BOOLS)
        self.assertEqual({"listenerTransport", "browserTransport"}, D.CONFIG_TRANSPORTS)
        self.assertEqual({"unobserved", "none", "tcp", "other"}, D.TRANSPORTS)
        self.assertEqual(b"P2PKIT_LAN_BROWSER_DESCRIPTOR_V1 ", D.MARKER)
        for policy, includes_txt in (("BONJOUR", False), ("WITH_TXT", True)):
            with self.subTest(policy=policy):
                result = D.probe_result(streams(policy=policy), policy, TOKENS[policy])
                self.assertEqual("notDiscovered", result["probe"]["outcome"])
                self.assertEqual("none", result["probe"]["peers"][0]["configuration"]["browserTransport"])
                self.assertIs(includes_txt, result["probe"]["peers"][0]["configuration"]["browserIncludesTXT"])
                self.assertNotIn(TOKENS[policy], json.dumps(result))
                self.assertEqual(64, len(result["originals"]["stdoutSha256"]))

    def test_policy_labels_cannot_replace_observed_configuration(self):
        for policy in ("BONJOUR", "WITH_TXT"):
            for key in CONFIG_BOOLS:
                expected = fixture(policy)["peers"][0]["configuration"][key]
                for value in (not expected, int(expected)):
                    bad = fixture(policy)
                    bad["peers"][0]["configuration"][key] = value
                    with self.subTest(policy=policy, key=key, value=value), self.assertRaises(ValueError):
                        D.validate_probe(bad, policy)
            for key in ("listenerTransport", "browserTransport"):
                expected = "none" if key == "browserTransport" else "tcp"
                for value in {"unobserved", "none", "tcp", "other", True} - {expected}:
                    bad = fixture(policy)
                    bad["peers"][0]["configuration"][key] = value
                    with self.subTest(policy=policy, key=key, value=value), self.assertRaises(ValueError):
                        D.validate_probe(bad, policy)

    def test_configured_txt_and_ready_do_not_claim_publication_or_discovery(self):
        for policy in ("BONJOUR", "WITH_TXT"):
            good = fixture(policy)
            D.validate_probe(good, policy)
            peer = good["peers"][0]
            self.assertTrue(peer["configuration"]["configuredServiceTxtReadbackMatches"])
            self.assertFalse(peer["ownRegistrationObserved"])
            self.assertFalse(peer["expectedPeerObserved"])
            self.assertEqual(0, peer["resultCallbacks"])
            bad = copy.deepcopy(good)
            bad["peers"][0]["ownRegistrationObserved"] = True
            with self.subTest(policy=policy, reason="registration"), self.assertRaises(ValueError):
                D.validate_probe(bad, policy)
            bad = copy.deepcopy(good)
            bad["peers"][0]["listenerReady"] = 0
            with self.subTest(policy=policy, reason="advertisement-before-ready"), self.assertRaises(ValueError):
                D.validate_probe(bad, policy)

    def test_discovery_requires_both_owned_other_peers_and_real_cleanup(self):
        for policy in ("BONJOUR", "WITH_TXT"):
            good = fixture(policy, discovered=True)
            self.assertEqual("discovered", D.validate_probe(good, policy)["outcome"])
            good["peers"][1]["expectedPeerObserved"] = False
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                D.validate_probe(good, policy)
        for outcome in ("cleanupUnconfirmed", "counterOverflow", "timingInvalid"):
            bad = fixture()
            bad["outcome"] = outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                D.validate_probe(bad, "BONJOUR")
        for key, value in (("complete", False), ("listenersCancelled", 1), ("browsersCreated", 1)):
            bad = fixture()
            bad["cleanup"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "BONJOUR")

    def test_retired_setup_failure_does_not_invent_parameter_observations(self):
        for policy in ("BONJOUR", "WITH_TXT"):
            good = fixture(policy)
            good["outcome"] = "setupFailed"
            for peer in good["peers"]:
                peer.update(listenerReady=0, browserReady=0, listenerCancelled=False, browserCancelled=False,
                            listenerLastState="none", browserLastState="none")
                peer["configuration"] = {key: False for key in CONFIG_BOOLS}
                peer["configuration"].update(listenerTransport="unobserved", browserTransport="unobserved")
            good["cleanup"] = {"listenersCreated": 0, "listenersCancelled": 0, "browsersCreated": 0,
                               "browsersCancelled": 0, "complete": True}
            self.assertEqual("setupFailed", D.validate_probe(good, policy)["outcome"])
            for key, value in (("browserTransport", "none"), ("browserIncludesTXT", True),
                               ("configuredServiceTxtReadbackMatches", True)):
                bad = copy.deepcopy(good)
                bad["peers"][0]["configuration"][key] = value
                with self.subTest(policy=policy, key=key), self.assertRaises(ValueError):
                    D.validate_probe(bad, policy)

    def test_stale_cross_policy_duplicate_missing_or_unbounded_results_rejected(self):
        for policy in ("BONJOUR", "WITH_TXT"):
            with self.subTest(policy=policy, reason="stale"), self.assertRaises(ValueError):
                D.probe_result(streams(policy=policy, token="e" * 32), policy, TOKENS[policy])
            wrong = "WITH_TXT" if policy == "BONJOUR" else "BONJOUR"
            with self.subTest(policy=policy, reason="envelope-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(policy=wrong, token=TOKENS[policy]), policy, TOKENS[policy])
            with self.subTest(policy=policy, reason="probe-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(fixture(wrong), policy), policy, TOKENS[policy])
        for stdout in (b"", streams()["stdout"] * 2, D.MARKER + b"x" * 8193,
                       b"P2PKIT_LAN_APP_V1 {}\n",
                       streams()["stdout"].replace(D.MARKER, b"P2PKIT_LAN_BROWSER_PARAMETERS_V1 ", 1)):
            with self.subTest(length=len(stdout)), self.assertRaises(ValueError):
                D.probe_result({"stdout": stdout, "stderr": b""}, "BONJOUR", TOKENS["BONJOUR"])
        for old_policy in ("TCP", "BARE"):
            with self.subTest(old=old_policy, reason="policy-argument"), self.assertRaises(ValueError):
                D.probe_result(streams(), old_policy, TOKENS["BONJOUR"])
            with self.subTest(old=old_policy, reason="envelope-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(browserDescriptor=old_policy), "BONJOUR", TOKENS["BONJOUR"])
            bad = fixture()
            bad["browserDescriptor"] = old_policy
            with self.subTest(old=old_policy, reason="probe-policy"), self.assertRaises(ValueError):
                D.validate_probe(bad, "BONJOUR")
        old = {"schema": 1, "token": TOKENS["BONJOUR"], "browserParameters": "BARE", "probe": fixture()}
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": D.MARKER + json.dumps(old).encode() + b"\n", "stderr": b""},
                           "BONJOUR", TOKENS["BONJOUR"])
        bad = fixture()
        bad["browserParameters"] = bad.pop("browserDescriptor")
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "BONJOUR")

    def test_private_fields_duplicate_json_and_boolean_counts_rejected(self):
        bad = streams()["stdout"].replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": bad, "stderr": b""}, "BONJOUR", TOKENS["BONJOUR"])
        with self.assertRaises(ValueError):
            D.probe_result(streams(address="private.invalid"), "BONJOUR", TOKENS["BONJOUR"])
        for owner, key, value in (("peer", "endpoint", "not-for-projection"),
                                  ("configuration", "receivedTxt", "not-for-projection"),
                                  ("peer", "listenerReady", True)):
            bad = fixture()
            target = bad["peers"][0] if owner == "peer" else bad["peers"][0]["configuration"]
            target[key] = value
            with self.subTest(owner=owner, key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "BONJOUR")
        for key, value in (("mode", "app"), ("schema", True), ("windowMilliseconds", 60000),
                           ("observationElapsedMilliseconds", 29999), ("cleanupElapsedMilliseconds", 5001),
                           ("counterOverflow", True)):
            bad = fixture()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "BONJOUR")

    def test_summary_is_bounded_token_free_and_nonqualifying(self):
        for policy in ("BONJOUR", "WITH_TXT"):
            output = io.StringIO()
            with redirect_stdout(output):
                D.emit(policy, D.probe_result(streams(policy=policy), policy, TOKENS[policy]), SOURCE, CONTEXT)
            text = output.getvalue()
            prefix = "P2PKIT_LAN_BROWSER_DESCRIPTOR_SUMMARY_V1 "
            self.assertTrue(text.startswith(prefix))
            self.assertLessEqual(len(text.encode()), 8192 + len(prefix) + 1)
            self.assertEqual(1, len(text.splitlines()))
            self.assertNotIn(TOKENS[policy], text)
            summary = json.loads(text[len(prefix):])
            self.assertIs(summary["qualification"], False)
            self.assertEqual("INTEL_LAN_BROWSER_DESCRIPTOR_DIAGNOSTIC_V1", summary["scope"])
            self.assertEqual(policy, summary["arm"])

    def test_fixed_order_exact_spawn_argv_and_retired_negative_progression(self):
        results = {}
        evidence, binary = Path("/unused-evidence"), Path("/unused-binary")
        events = []
        def captured(directory, label, argv):
            events.append(label)
            policy = "BONJOUR" if label == "cli-bonjour" else "WITH_TXT"
            return streams(policy=policy)
        def emitted(policy, value, source, context):
            events.append("emit-" + policy)
        with mock.patch.object(D, "command", side_effect=captured) as command, \
                mock.patch.object(D, "emit", side_effect=emitted):
            D.run_arms(evidence, binary, UDID, dict(TOKENS), SOURCE, CONTEXT, results)
        self.assertEqual(["cli-bonjour", "emit-BONJOUR", "cli-with_txt", "emit-WITH_TXT"], events)
        self.assertEqual([
            mock.call(evidence, "cli-bonjour", ["/usr/bin/xcrun", "simctl", "spawn", UDID, str(binary),
                      "--token", TOKENS["BONJOUR"], "--browser-descriptor", "BONJOUR"]),
            mock.call(evidence, "cli-with_txt", ["/usr/bin/xcrun", "simctl", "spawn", UDID, str(binary),
                      "--token", TOKENS["WITH_TXT"], "--browser-descriptor", "WITH_TXT"]),
        ], command.call_args_list)
        self.assertEqual(["BONJOUR", "WITH_TXT"], list(results))
        self.assertTrue(all(value["probe"]["outcome"] == "notDiscovered" for value in results.values()))

    def test_reused_invalid_or_incomplete_arm_tokens_refused_before_spawn(self):
        cases = [({"BONJOUR": TOKENS["BONJOUR"], "WITH_TXT": TOKENS["BONJOUR"]}, {}),
                 ({"BONJOUR": "a" * 31, "WITH_TXT": TOKENS["WITH_TXT"]}, {}),
                 ({"BONJOUR": "A" * 32, "WITH_TXT": TOKENS["WITH_TXT"]}, {}),
                 ({"BONJOUR": TOKENS["BONJOUR"]}, {}),
                 ({**TOKENS, "APP": "f" * 32}, {}),
                 (dict(TOKENS), {"BONJOUR": {}}),
                 ({"TCP": TOKENS["BONJOUR"], "BARE": TOKENS["WITH_TXT"]}, {})]
        for index, (tokens, results) in enumerate(cases):
            with self.subTest(index=index), mock.patch.object(D, "command") as command, \
                    mock.patch.object(D, "emit") as emit:
                with self.assertRaises(ValueError):
                    D.run_arms(Path("/unused"), Path("/unused-binary"), UDID, tokens, SOURCE, CONTEXT, results)
                command.assert_not_called()
                emit.assert_not_called()

    def test_invalid_first_arm_stops_next_and_invalid_second_keeps_first(self):
        for fail_index in (0, 1):
            results = {}
            captures = []
            for index, policy in enumerate(("BONJOUR", "WITH_TXT")):
                probe = fixture(policy)
                if index == fail_index:
                    probe["cleanup"]["complete"] = False
                captures.append(streams(probe, policy))
            with self.subTest(index=fail_index), mock.patch.object(D, "command", side_effect=captures) as command, \
                    mock.patch.object(D, "emit") as emit:
                with self.assertRaises(ValueError):
                    D.run_arms(Path("/unused"), Path("/unused-binary"), UDID, dict(TOKENS), SOURCE, CONTEXT, results)
                self.assertEqual(fail_index + 1, command.call_count)
                self.assertEqual(fail_index, emit.call_count)
                self.assertEqual([] if fail_index == 0 else ["BONJOUR"], list(results))
        with mock.patch.object(D, "command", side_effect=ValueError("COMMAND_FAILED")) as command, \
                mock.patch.object(D, "emit") as emit:
            results = {}
            with self.assertRaises(ValueError):
                D.run_arms(Path("/unused"), Path("/unused-binary"), UDID, dict(TOKENS), SOURCE, CONTEXT, results)
            self.assertEqual(1, command.call_count)
            self.assertEqual({}, results)
            emit.assert_not_called()

    def test_lipo_input_order_and_cli_only_source_contract(self):
        source = (ROOT / "scripts/diagnostics/intel-lan-host/run.py").read_text()
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "command"
                 and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                 and node.args[1].value == "cli-architecture"]
        self.assertEqual(1, len(calls))
        self.assertEqual(3, len(calls[0].args))
        self.assertEqual([], calls[0].keywords)
        expected = ast.parse('["/usr/bin/lipo", str(binary), "-verify_arch", "x86_64"]', mode="eval").body
        self.assertEqual(ast.dump(expected, include_attributes=False), ast.dump(calls[0].args[2], include_attributes=False))
        self.assertEqual(("LanProbe.swift", "main.swift"), D.FILES)
        for forbidden in ("gradlew", "xcodebuild", "xcodegen", "TCC.db", "App.swift", "UITests.swift", '"privacy"'):
            self.assertNotIn(forbidden, source)
        self.assertIn('"-warnings-as-errors"', source)
        self.assertIn('"-j", "2"', source)
        probe = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        parameters = probe.split("    private func browserParameters()", 1)[1].split("    private func transport(", 1)[0]
        self.assertIn("let parameters = NWParameters()", parameters)
        self.assertNotIn("NWParameters.tcp", parameters)
        for expression in ("parameters.includePeerToPeer = true", "parameters.prohibitedInterfaceTypes = [.cellular]"):
            self.assertIn(expression, parameters)
        # These are source seams, not an SDK/native execution or received-TXT claim.
        for expression in (
                "descriptor = .bonjour(type: Self.serviceType, domain: nil)",
                "descriptor = .bonjourWithTXTRecord(type: Self.serviceType, domain: nil)",
                "case .bonjour: observed.browserIncludesTXT = false",
                "case .bonjourWithTXTRecord: observed.browserIncludesTXT = true",
                "guard observed.browserTransport == .none",
                "observed.browserIncludesTXT == (policy == .withTXT)",
                "service.noAutoRename = true", "configuredServiceTxtReadbackMatches = raw == expected",
                '"plat=IOS", "caps=LAN", "pv=1"',
                "observationNanoseconds: UInt64 = 30_000_000_000",
                "cancellationNanoseconds: UInt64 = 5_000_000_000"):
            self.assertIn(expression, probe)
        main = (ROOT / "scripts/diagnostics/intel-lan-host/main.swift").read_text()
        self.assertIn('CommandLine.arguments[3] == "--browser-descriptor"', main)
        self.assertNotIn("--browser-parameters", main)

    def test_unchanged_capture_bounds_and_finally_owned_source_joins(self):
        diagnostic_budgets = {"compile-cli": 300, "sdk-path": 120, "cli-architecture": 120,
                              "cli-bonjour": 120, "cli-with_txt": 120, "COMPILE-CLI": 120,
                              "compile-cli-extra": 120, "compile-cli ": 120}
        owner_budgets = {label: 300 if label == "intel-bootstatus" else 120
                         for label in D.GATE.INTEL_PREPARE + D.GATE.INTEL_RETIRE}
        for label, seconds in {**diagnostic_budgets, **owner_budgets}.items():
            with self.subTest(label=label):
                self.assertEqual(seconds, D.GATE._intel_work_seconds(label))
        with self.assertRaisesRegex(ValueError, "INTEL_CLOSED_COMMAND"):
            D.GATE._intel_phase_command("compile-cli")
        for label, seconds in diagnostic_budgets.items():
            required = seconds + 20
            for remaining in (None, required - 1, required):
                with self.subTest(label=label, remaining=remaining), \
                        mock.patch.object(D, "EXECUTION_END", remaining), \
                        mock.patch.object(D.time, "monotonic", return_value=0), \
                        mock.patch.object(D.GATE, "_intel_capture_phase",
                                          side_effect=RuntimeError("capture sentinel")) as capture:
                    if remaining == required:
                        with self.assertRaisesRegex(RuntimeError, "capture sentinel"):
                            D.command(Path("/unused"), label, ["/unused"])
                        capture.assert_called_once_with(Path("/unused"), label, ["/unused"])
                    else:
                        with self.assertRaisesRegex(ValueError, "COMMAND_WINDOW"):
                            D.command(Path("/unused"), label, ["/unused"])
                        capture.assert_not_called()
        self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
        self.assertEqual(120, D.GATE.simulator.SECONDS)
        self.assertEqual((15, 5), (D.GATE.TERMINATION_GRACE_SECONDS, D.GATE.TERMINATION_KILL_SECONDS))
        source = (ROOT / "scripts/diagnostics/intel-lan-host/run.py").read_text()
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "run")
        guarded = [node for node in ast.walk(function) if isinstance(node, ast.Try)
                   and any(isinstance(child, ast.Call) and ast.unparse(child.func) == "owner.retire"
                           for statement in node.finalbody for child in ast.walk(statement))]
        self.assertEqual(1, len(guarded))
        body = ast.Module(body=guarded[0].body, type_ignores=[])
        finally_body = ast.Module(body=guarded[0].finalbody, type_ignores=[])
        calls = {ast.unparse(node.func) for node in ast.walk(body) if isinstance(node, ast.Call)}
        self.assertTrue({"GATE.IntelSimulatorOwner", "owner.prepare", "run_arms"} <= calls)
        final_calls = {ast.unparse(node.func) for node in ast.walk(finally_body) if isinstance(node, ast.Call)}
        self.assertTrue({"owner.retire", "GATE.source_state", "GATE.simulator_original", "read_file"} <= final_calls)
        strings = {node.value for node in ast.walk(finally_body) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertTrue({"RETIREMENT_REJECTED", "ORIGINAL_CHANGED", "BINDING_CHANGED",
                         "SOURCE_OR_CONTEXT_CHANGED", "GENERATED_INPUT_CHANGED"} <= strings)
        self.assertIn('"gradleLaunched": False', source)


if __name__ == "__main__":
    unittest.main(failfast=True)
