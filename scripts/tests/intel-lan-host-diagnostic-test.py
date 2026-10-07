#!/usr/bin/env python3
"""Offline controls for same-live owned TXT scopes/SRV control, not native acceptance."""
import ast
import copy
from contextlib import ExitStack, redirect_stdout
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
TOKENS = {"OWNED_TXT": "a" * 32}
SOURCE = {"commit": "c" * 40, "tree": "d" * 40}
CONTEXT = {"GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "ios-x64"}
UDID = "11111111-2222-3333-4444-555555555555"
CONFIG_BOOLS = {"listenerObserved", "listenerNoDelay", "listenerP2P", "listenerCellBan",
                "browserObserved", "browserP2P", "browserCellBan", "browserIncludesTXT",
                "advertisementAfterReady", "noAutoRename", "configuredServiceTxtPresent",
                "configuredServiceTxtReadbackMatches", "configuredServiceTxtShapeValid"}


def fixture(policy="OWNED_TXT", discovered=False):
    peer = {key: 0 for key in D.COUNTERS}
    peer.update({key: False for key in D.PEER_BOOLS})
    peer.update(listenerReady=1, browserReady=1, listenerCancelled=True, browserCancelled=True,
                listenerLastState="ready", browserLastState="ready",
                listenerError={"domain": "none", "code": 0}, browserError={"domain": "none", "code": 0})
    peer["configuration"] = {key: True for key in CONFIG_BOOLS}
    peer["configuration"].update(listenerTransport="tcp", browserTransport="none",
                                 browserIncludesTXT=False)
    peer.update(selectedInterfaceKind="none", candidateInterfaceCount=0)
    for field in D.QUERY_FIELDS:
        peer[field] = {key: 0 for key in D.TXT_COUNTERS}
        peer[field].update({key: False for key in D.TXT_BOOLS})
        peer[field].update(errorCode=0, retired=True, startMilliseconds=-1, retirementMilliseconds=-1,
                           retirementReason="none", callbackInterfaceClass="none")
    if discovered:
        peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=1,
                    ownRegistrationObserved=True, registrationAdded=1,
                    selectedInterfaceKind="wifi", candidateInterfaceCount=1)
        peer["txtQuery"].update(started=1, callbacks=1, matchingCallbacks=1, bytes=128,
                               received=True, matchesExpected=True, identityMatched=True, interfaceMatched=True,
                               present=True, startMilliseconds=100, retirementMilliseconds=30001,
                               retirementReason="cutoff", callbackInterfaceClass="selectedConcrete")
    return {"schema": 1, "diagnosticOnly": True, "mode": "cli", "browserDescriptor": policy,
            "outcome": "discovered" if discovered else "notDiscovered", "windowMilliseconds": 30000,
            "observationElapsedMilliseconds": 30001, "cleanupElapsedMilliseconds": 10,
            "isSimulatorBuild": True, "isX86_64Build": True, "counterOverflow": False,
            "packaging": {key: False for key in D.PACKAGE_KEYS},
            "peers": [copy.deepcopy(peer), copy.deepcopy(peer)],
            "cleanup": {"listenersCreated": 2, "listenersCancelled": 2, "browsersCreated": 2,
                        "browsersCancelled": 2, "complete": True}}


def streams(probe=None, policy="OWNED_TXT", token=None, **extra):
    value = {"schema": 1, "token": TOKENS[policy] if token is None else token,
             "browserDescriptor": policy, "probe": fixture(policy) if probe is None else probe}
    value.update(extra)
    return {"stdout": b"P2PKIT_LAN_OWNED_TXT_V1 " + json.dumps(value).encode() + b"\n", "stderr": b""}


class DiagnosticControls(unittest.TestCase):
    def _run_preboot_controller(self, failure=None):
        """Mock controller effects only: no files, processes, simulator, or native evidence."""
        events, written, originals = [], {}, {}
        source = {**SOURCE, "status": "", "diffSha256": D.digest(b"")}
        developer = "/Applications/Xcode_26.3.app/Contents/Developer"
        sdk = developer + "/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk"
        environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
            "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": source["commit"],
            "GITHUB_REF": "refs/heads/work/foundation-native-frontier-20261007-CC4DEkbv",
            "GITHUB_JOB": "ios-x64", "GITHUB_WORKSPACE": str(D.ROOT), "DEVELOPER_DIR": developer,
            "GITHUB_EVENT_NAME": "workflow_dispatch", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "macOS", "RUNNER_ARCH": "X64", "ImageOS": "macos15", "ImageVersion": "synthetic"}
        owner = mock.Mock()
        owner.selected = {"device": {"udid": UDID}}
        owner.originals = {"intel-prelaunch/result.json": b"synthetic-owner-original"}
        owner.binding_raw, owner.retirement_raw = b"synthetic-binding", b"synthetic-retirement"
        binary_reads = 0

        def create_owner(directory, captured_source):
            events.append("owner-create")
            self.assertEqual({**source, "token": "b" * 32}, captured_source)
            owner.directory = directory / "intel-simulator"
            for name, raw in {**owner.originals, "binding.json": owner.binding_raw,
                              "retirement.json": owner.retirement_raw}.items():
                originals[owner.directory / name] = raw
            return owner

        def prepare():
            events.append("owner-prepare")
            if failure == "prepare":
                raise ValueError("synthetic preparation failure")

        def retire():
            events.append("owner-retire")
            return []

        def read(path, limit):
            nonlocal binary_reads
            if path.name == "P2pKitLanHostCLI":
                self.assertEqual(64 * 1024 * 1024, limit)
                binary_reads += 1
                events.append("binary-initial" if binary_reads == 1 else "binary-recheck")
                if binary_reads == 2 and failure == "binary-hash":
                    return b"compiled-two"  # same length, different hash
                if binary_reads == 2 and failure == "binary-length":
                    return b"different-compiled-length"
                if binary_reads == 2 and failure == "binary-read":
                    raise OSError("synthetic bounded read failure")
                return b"compiled-one"
            self.assertIn(path.name, D.FILES)
            self.assertEqual(128 * 1024, limit)
            return ("synthetic-" + path.name).encode()

        def captured(directory, label, argv):
            events.append(label)
            if failure == label:
                raise ValueError("synthetic captured command failure")
            if failure == "sdk-interrupted" and label == "sdk-path":
                raise KeyboardInterrupt()
            if label == "sdk-path":
                self.assertEqual(["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-path"], argv)
                return {"stdout": sdk.encode(), "stderr": b""}
            return streams() if label == "cli-owned_txt" else {"stdout": b"", "stderr": b""}

        owner.prepare.side_effect, owner.retire.side_effect = prepare, retire
        with ExitStack() as stack:
            for target, name, values in (
                (D.GATE.platform, "system", {"return_value": "Darwin"}),
                (D.GATE, "architecture", {"return_value": "x64"}),
                (D.GATE, "ordinary_simulator_binding", {"return_value": None}),
                (D.GATE, "IntelSimulatorOwner", {"side_effect": create_owner}),
                (D.GATE, "_intel_write", {}),
                (D.GATE, "simulator_original", {"side_effect": lambda path, **kwargs: originals[path]}),
                (D, "private_dir", {"side_effect": lambda path: path}),
                (D, "read_file", {"side_effect": read}),
                (D, "command", {"side_effect": captured}),
                (D, "write", {"side_effect": lambda path, value: written.__setitem__(path.name, copy.deepcopy(value))}),
                (D.os, "umask", {}),
                (D.signal, "signal", {"return_value": None}),
                (D.time, "monotonic", {"return_value": 0}),
                (D.uuid, "uuid4", {"side_effect": [mock.Mock(hex="b" * 32), mock.Mock(hex="a" * 32)]}),
                (Path, "mkdir", {}),
                (Path, "resolve", {"autospec": True, "side_effect": lambda path, **kwargs: path}),
                (Path, "stat", {"return_value": mock.Mock(st_uid=D.os.geteuid())}),
                (Path, "is_dir", {"return_value": True}),
            ):
                stack.enter_context(mock.patch.object(target, name, **values))
            state = stack.enter_context(mock.patch.object(D.GATE, "source_state", return_value=source))
            stack.enter_context(mock.patch.dict(D.os.environ, environment, clear=True))
            stack.enter_context(mock.patch.object(D, "EXECUTION_END", None))
            stack.enter_context(redirect_stdout(io.StringIO()))
            code = D.run()
            self.assertEqual(2, state.call_count)  # initial source and unchanged finally recheck
        return code, events, written, owner

    def test_preboot_build_order_keeps_binary_identity_and_owned_retirement(self):
        code, events, written, owner = self._run_preboot_controller()
        self.assertEqual(0, code)
        self.assertEqual(["sdk-path", "compile-cli", "cli-architecture", "binary-initial",
                          "owner-create", "owner-prepare", "binary-recheck", "cli-owned_txt", "owner-retire"], events)
        self.assertEqual({"bytes": len(b"compiled-one"), "sha256": D.digest(b"compiled-one")}, written["cli-binary.json"])
        comparison = written["comparison.json"]
        self.assertEqual([], comparison["errors"])
        self.assertIs(comparison["simulatorRetired"], True)
        self.assertEqual({"OWNED_TXT"}, set(comparison["results"]))
        self.assertEqual("notDiscovered", comparison["results"]["OWNED_TXT"]["probe"]["outcome"])
        owner.prepare.assert_called_once_with()
        owner.retire.assert_called_once_with()

    def test_preboot_build_failures_never_create_or_retire_a_simulator(self):
        labels = ["sdk-path", "compile-cli", "cli-architecture"]
        for failure in (*labels, "sdk-interrupted"):
            with self.subTest(failure=failure):
                code, events, written, owner = self._run_preboot_controller(failure)
                self.assertEqual(1, code)
                expected = labels[:1 if failure == "sdk-interrupted" else labels.index(failure) + 1]
                self.assertEqual(expected, events)
                comparison = written["comparison.json"]
                self.assertEqual(["BUILD_INTERRUPTED" if failure == "sdk-interrupted" else "BUILD_FAILED"], comparison["errors"])
                self.assertEqual({}, comparison["results"])
                self.assertIs(comparison["simulatorRetired"], False)
                self.assertNotIn("cli-binary.json", written)
                owner.prepare.assert_not_called()
                owner.retire.assert_not_called()

    def test_preboot_prepare_or_binary_recheck_failure_still_retires_owned_simulator(self):
        for failure in ("prepare", "binary-hash", "binary-length", "binary-read"):
            with self.subTest(failure=failure):
                code, events, written, owner = self._run_preboot_controller(failure)
                self.assertEqual(1, code)
                expected = ["sdk-path", "compile-cli", "cli-architecture", "binary-initial", "owner-create", "owner-prepare"]
                if failure != "prepare":
                    expected.append("binary-recheck")
                self.assertEqual(expected + ["owner-retire"], events)
                comparison = written["comparison.json"]
                self.assertEqual(["PREPARE_FAILED" if failure == "prepare" else "CLI_OWNED_TXT_FAILED"], comparison["errors"])
                self.assertEqual({}, comparison["results"])
                self.assertIs(comparison["simulatorRetired"], True)  # only this mocked owner's successful retire report
                owner.prepare.assert_called_once_with()
                owner.retire.assert_called_once_with()

    def test_local_txt_and_srv_control_do_not_replace_concrete_discovery(self):
        value = fixture()
        positive = fixture(discovered=True)["peers"][0]
        for peer in value["peers"]:
            peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=1,
                        selectedInterfaceKind="loopback", candidateInterfaceCount=2)
            peer["localTxtQuery"] = copy.deepcopy(positive["txtQuery"])
            peer["localTxtQuery"].update(interfaceMatched=False, callbackInterfaceClass="localOnly")
            peer["localSrvQuery"] = copy.deepcopy(peer["localTxtQuery"])
            peer["localSrvQuery"].update(matchingCallbacks=0, matchesExpected=False, bytes=7)
        self.assertEqual("notDiscovered", D.validate_probe(value, "OWNED_TXT")["outcome"])
        bad = copy.deepcopy(value)
        bad["outcome"] = "discovered"
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "OWNED_TXT")
        for field in ("txtQuery", "localSrvQuery"):
            bad = copy.deepcopy(value)
            bad["peers"][0][field] = copy.deepcopy(bad["peers"][0]["localTxtQuery"])
            with self.subTest(role=field), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        bad = copy.deepcopy(value)
        bad["peers"][0]["localSrvQuery"]["bytes"] = 6
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "OWNED_TXT")

    def test_absence_is_not_fatal_but_cannot_leave_a_current_match(self):
        value = fixture()
        peer = value["peers"][0]
        peer.update(expectedPeerObserved=True, resultCallbacks=1, selectedInterfaceKind="wifi",
                    candidateInterfaceCount=1)
        query = peer["localTxtQuery"]
        query.update(started=1, callbacks=1, absenceCallbacks=1, startMilliseconds=100,
                     retirementMilliseconds=30001, retirementReason="cutoff")
        D.validate_probe(value, "OWNED_TXT")
        # A subsequent actual add may be positive, without pretending its interface is concrete.
        query.update(callbacks=2, received=True, bytes=128, matchingCallbacks=1, matchesExpected=True,
                     present=True, identityMatched=True, callbackInterfaceClass="localOnly")
        D.validate_probe(value, "OWNED_TXT")
        for key, bad_value in (("present", False), ("identityMatched", False), ("errorCode", -65563),
                                ("absenceCallbacks", 2), ("callbackInterfaceClass", "none")):
            bad = copy.deepcopy(value)
            bad["peers"][0]["localTxtQuery"][key] = bad_value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        query.update(callbacks=3, absenceCallbacks=2, present=False, matchesExpected=False,
                     identityMatched=False, callbackInterfaceClass="none")
        D.validate_probe(value, "OWNED_TXT")  # historical bytes/match do not imply current presence

    def test_query_lifetimes_partial_scheduling_and_retirement_scope(self):
        value = fixture(discovered=True)
        for field in D.QUERY_FIELDS:
            query = value["peers"][0][field]
            if field != "txtQuery":
                query.update(started=1, startMilliseconds=30000, retirementMilliseconds=30002,
                             retirementReason="cutoff")
        D.validate_probe(value, "OWNED_TXT")  # late start is measured, not promoted to 30s coverage
        for key, bad_value in (("startMilliseconds", True), ("startMilliseconds", -1),
                                ("retirementMilliseconds", 99), ("retirementMilliseconds", 30012),
                                ("retirementMilliseconds", 125001), ("retirementReason", "none"),
                                ("retirementReason", "unknown")):
            bad = copy.deepcopy(value)
            bad["peers"][0]["txtQuery"][key] = bad_value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        for field in ("localTxtQuery", "localSrvQuery"):
            bad = copy.deepcopy(value)
            bad["peers"][0][field]["retirementReason"] = "interfaceRemoved"
            with self.subTest(field=field), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        value["peers"][0]["txtQuery"]["retirementReason"] = "interfaceRemoved"
        # The last-live match must already be cleared when the interface disappears.
        value["peers"][0]["txtQuery"].update(matchesExpected=False, present=False)
        value["outcome"] = "notDiscovered"
        D.validate_probe(value, "OWNED_TXT")
        query = value["peers"][0]["localTxtQuery"]
        query.update(startMilliseconds=-1, retirementMilliseconds=103, retirementReason="queueFailed",
                     errorCode=-65563)
        D.validate_probe(value, "OWNED_TXT")
        for key, bad_value in (("errorCode", 0), ("startMilliseconds", 0), ("callbacks", 1)):
            bad = copy.deepcopy(value)
            bad["peers"][0]["localTxtQuery"][key] = bad_value
            with self.subTest(queue_failure=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")

    def test_three_roles_and_interface_snapshot_are_closed(self):
        self.assertEqual(("txtQuery", "localTxtQuery", "localSrvQuery"), D.QUERY_FIELDS)
        for field in D.QUERY_FIELDS:
            bad = fixture()
            del bad["peers"][0][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
            for key, bad_value in (("absenceCallbacks", True), ("present", 1), ("rawSrv", "private"),
                                    ("callbackInterfaceClass", "en0"), ("interfaceIndex", 1)):
                bad = fixture()
                bad["peers"][0][field][key] = bad_value
                with self.subTest(field=field, key=key), self.assertRaises(ValueError):
                    D.validate_probe(bad, "OWNED_TXT")
        for key, bad_value in (("selectedInterfaceKind", "cellular"), ("selectedInterfaceKind", "none"),
                                ("candidateInterfaceCount", 0), ("candidateInterfaceCount", 129),
                                ("candidateInterfaceCount", True)):
            bad = fixture(discovered=True)
            bad["peers"][0][key] = bad_value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")

    def test_three_role_records_fit_unchanged_serialization_caps(self):
        probe = fixture(discovered=True)
        for peer in probe["peers"]:
            for field in ("localTxtQuery", "localSrvQuery"):
                peer[field] = copy.deepcopy(peer["txtQuery"])
            peer["localSrvQuery"].update(matchingCallbacks=0, matchesExpected=False)
            for field in D.QUERY_FIELDS:
                query = peer[field]
                query.update(callbacks=65535, removedCallbacks=32767, absenceCallbacks=32767,
                             bytes=65535, retirementMilliseconds=30001)
        D.validate_probe(probe, "OWNED_TXT")
        self.assertLessEqual(len(D.encoded(probe)), 6144)
        self.assertLessEqual(len(streams(probe)["stdout"]) - len(D.MARKER), 8192)
        with redirect_stdout(io.StringIO()) as output:
            D.emit("OWNED_TXT", D.probe_result(streams(probe), "OWNED_TXT", TOKENS["OWNED_TXT"]), SOURCE, CONTEXT)
        self.assertLessEqual(len(output.getvalue().encode()), 8192 + len("P2PKIT_LAN_OWNED_TXT_SUMMARY_V1 ") + 1)

    def test_txt_requires_received_owned_matching_bytes_not_only_browse_or_configuration(self):
        for key, value in (("received", False), ("matchingCallbacks", 0), ("bytes", 0),
                           ("identityMatched", False), ("interfaceMatched", False), ("malformed", True),
                           ("errorCode", -65563), ("retired", False), ("started", 0)):
            bad = fixture(discovered=True)
            bad["peers"][0]["txtQuery"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        only_browse = fixture()
        for peer in only_browse["peers"]:
            peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=2)
        self.assertEqual("notDiscovered", D.validate_probe(only_browse, "OWNED_TXT")["outcome"])
        only_browse["outcome"] = "discovered"
        with self.assertRaises(ValueError):
            D.validate_probe(only_browse, "OWNED_TXT")

    def test_txt_removal_or_mismatch_cannot_use_historical_match_for_discovery(self):
        for removed, malformed in ((1, False), (0, False), (0, True)):
            value = fixture(discovered=True)
            value["outcome"] = "notDiscovered"
            value["peers"][1]["txtQuery"].update(callbacks=2, removedCallbacks=removed,
                                                 matchesExpected=False, malformed=malformed)
            self.assertEqual("notDiscovered", D.validate_probe(value, "OWNED_TXT")["outcome"])
            value["outcome"] = "discovered"
            with self.subTest(removed=removed, malformed=malformed), self.assertRaises(ValueError):
                D.validate_probe(value, "OWNED_TXT")

    def test_txt_query_closed_bounds_and_no_unstarted_or_private_observations(self):
        for key, val in (("started", 2), ("callbacks", True), ("bytes", 65536), ("bytes", -1),
                         ("removedCallbacks", 2), ("errorCode", 2 ** 31), ("errorCode", True),
                         ("received", 1), ("rawTxt", "private"), ("hostname", "private")):
            bad = fixture(discovered=True)
            bad["peers"][0]["txtQuery"][key] = val
            with self.subTest(key=key, value=val), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        for key, val in (("callbacks", 1), ("received", True), ("identityMatched", True),
                         ("bytes", 1), ("retired", False)):
            bad = fixture()
            bad["peers"][0]["txtQuery"][key] = val
            with self.subTest(unstarted=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        absent = fixture()
        absent["peers"][0]["txtQuery"]["errorCode"] = -65563
        self.assertEqual("notDiscovered", D.validate_probe(absent, "OWNED_TXT")["outcome"])

    def test_owned_txt_uses_closed_actual_parameter_readbacks(self):
        self.assertEqual(("OWNED_TXT",), D.POLICIES)
        self.assertEqual(CONFIG_BOOLS, D.CONFIG_BOOLS)
        self.assertEqual({"listenerTransport", "browserTransport"}, D.CONFIG_TRANSPORTS)
        self.assertEqual({"unobserved", "none", "tcp", "other"}, D.TRANSPORTS)
        self.assertEqual(b"P2PKIT_LAN_OWNED_TXT_V1 ", D.MARKER)
        for policy, includes_txt in (("OWNED_TXT", False),):
            with self.subTest(policy=policy):
                result = D.probe_result(streams(policy=policy), policy, TOKENS[policy])
                self.assertEqual("notDiscovered", result["probe"]["outcome"])
                self.assertEqual("none", result["probe"]["peers"][0]["configuration"]["browserTransport"])
                self.assertIs(includes_txt, result["probe"]["peers"][0]["configuration"]["browserIncludesTXT"])
                self.assertNotIn(TOKENS[policy], json.dumps(result))
                self.assertEqual(64, len(result["originals"]["stdoutSha256"]))

    def test_policy_labels_cannot_replace_observed_configuration(self):
        for policy in ("OWNED_TXT",):
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
        for policy in ("OWNED_TXT",):
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
        for policy in ("OWNED_TXT",):
            good = fixture(policy, discovered=True)
            self.assertEqual("discovered", D.validate_probe(good, policy)["outcome"])
            good["peers"][1]["expectedPeerObserved"] = False
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                D.validate_probe(good, policy)
        for outcome in ("cleanupUnconfirmed", "counterOverflow", "timingInvalid"):
            bad = fixture()
            bad["outcome"] = outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        for key, value in (("complete", False), ("listenersCancelled", 1), ("browsersCreated", 1)):
            bad = fixture()
            bad["cleanup"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")

    def test_retired_setup_failure_does_not_invent_parameter_observations(self):
        for policy in ("OWNED_TXT",):
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
        for policy in ("OWNED_TXT",):
            with self.subTest(policy=policy, reason="stale"), self.assertRaises(ValueError):
                D.probe_result(streams(policy=policy, token="e" * 32), policy, TOKENS[policy])
            wrong = "WITH_TXT"
            with self.subTest(policy=policy, reason="envelope-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(policy=wrong, token=TOKENS[policy]), policy, TOKENS[policy])
            with self.subTest(policy=policy, reason="probe-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(fixture(wrong), policy), policy, TOKENS[policy])
        for stdout in (b"", streams()["stdout"] * 2, D.MARKER + b"x" * 8193,
                       b"P2PKIT_LAN_APP_V1 {}\n",
                       streams()["stdout"].replace(D.MARKER, b"P2PKIT_LAN_BROWSER_PARAMETERS_V1 ", 1)):
            with self.subTest(length=len(stdout)), self.assertRaises(ValueError):
                D.probe_result({"stdout": stdout, "stderr": b""}, "OWNED_TXT", TOKENS["OWNED_TXT"])
        for old_policy in ("TCP", "BARE", "BONJOUR", "WITH_TXT"):
            with self.subTest(old=old_policy, reason="policy-argument"), self.assertRaises(ValueError):
                D.probe_result(streams(), old_policy, TOKENS["OWNED_TXT"])
            with self.subTest(old=old_policy, reason="envelope-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(browserDescriptor=old_policy), "OWNED_TXT", TOKENS["OWNED_TXT"])
            bad = fixture()
            bad["browserDescriptor"] = old_policy
            with self.subTest(old=old_policy, reason="probe-policy"), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        old = {"schema": 1, "token": TOKENS["OWNED_TXT"], "browserParameters": "BARE", "probe": fixture()}
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": D.MARKER + json.dumps(old).encode() + b"\n", "stderr": b""},
                           "OWNED_TXT", TOKENS["OWNED_TXT"])
        bad = fixture()
        bad["browserParameters"] = bad.pop("browserDescriptor")
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "OWNED_TXT")

    def test_private_fields_duplicate_json_and_boolean_counts_rejected(self):
        bad = streams()["stdout"].replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": bad, "stderr": b""}, "OWNED_TXT", TOKENS["OWNED_TXT"])
        with self.assertRaises(ValueError):
            D.probe_result(streams(address="private.invalid"), "OWNED_TXT", TOKENS["OWNED_TXT"])
        for owner, key, value in (("peer", "endpoint", "not-for-projection"),
                                  ("configuration", "receivedTxt", "not-for-projection"),
                                  ("peer", "listenerReady", True)):
            bad = fixture()
            target = bad["peers"][0] if owner == "peer" else bad["peers"][0]["configuration"]
            target[key] = value
            with self.subTest(owner=owner, key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")
        for key, value in (("mode", "app"), ("schema", True), ("windowMilliseconds", 60000),
                           ("observationElapsedMilliseconds", 29999), ("cleanupElapsedMilliseconds", 5001),
                           ("counterOverflow", True)):
            bad = fixture()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "OWNED_TXT")

    def test_summary_is_bounded_token_free_and_nonqualifying(self):
        for policy in ("OWNED_TXT",):
            output = io.StringIO()
            with redirect_stdout(output):
                D.emit(policy, D.probe_result(streams(policy=policy), policy, TOKENS[policy]), SOURCE, CONTEXT)
            text = output.getvalue()
            prefix = "P2PKIT_LAN_OWNED_TXT_SUMMARY_V1 "
            self.assertTrue(text.startswith(prefix))
            self.assertLessEqual(len(text.encode()), 8192 + len(prefix) + 1)
            self.assertEqual(1, len(text.splitlines()))
            self.assertNotIn(TOKENS[policy], text)
            summary = json.loads(text[len(prefix):])
            self.assertIs(summary["qualification"], False)
            self.assertEqual("INTEL_LAN_OWNED_TXT_DIAGNOSTIC_V1", summary["scope"])
            self.assertEqual(policy, summary["arm"])

    def test_single_owned_txt_spawn_and_retired_negative_is_not_a_retry(self):
        results = {}
        evidence, binary = Path("/unused-evidence"), Path("/unused-binary")
        events = []
        def captured(directory, label, argv):
            events.append(label)
            return streams()
        def emitted(policy, value, source, context):
            events.append("emit-" + policy)
        with mock.patch.object(D, "command", side_effect=captured) as command, \
                mock.patch.object(D, "emit", side_effect=emitted):
            D.run_arms(evidence, binary, UDID, dict(TOKENS), SOURCE, CONTEXT, results)
        self.assertEqual(["cli-owned_txt", "emit-OWNED_TXT"], events)
        command.assert_called_once_with(evidence, "cli-owned_txt", ["/usr/bin/xcrun", "simctl", "spawn", UDID,
                      str(binary), "--token", TOKENS["OWNED_TXT"], "--browser-descriptor", "OWNED_TXT"])
        self.assertEqual(["OWNED_TXT"], list(results))
        self.assertEqual("notDiscovered", results["OWNED_TXT"]["probe"]["outcome"])

    def test_reused_invalid_or_incomplete_arm_tokens_refused_before_spawn(self):
        cases = [({}, {}), ({"OWNED_TXT": "a" * 31}, {}), ({"OWNED_TXT": "A" * 32}, {}),
                 ({**TOKENS, "APP": "f" * 32}, {}), (dict(TOKENS), {"OWNED_TXT": {}}),
                 ({"BONJOUR": "a" * 32, "WITH_TXT": "b" * 32}, {})]
        for index, (tokens, results) in enumerate(cases):
            with self.subTest(index=index), mock.patch.object(D, "command") as command, \
                    mock.patch.object(D, "emit") as emit:
                with self.assertRaises(ValueError):
                    D.run_arms(Path("/unused"), Path("/unused-binary"), UDID, tokens, SOURCE, CONTEXT, results)
                command.assert_not_called()
                emit.assert_not_called()

    def test_invalid_observation_stops_without_retry_or_partial_success(self):
        probe = fixture()
        probe["cleanup"]["complete"] = False
        for failure in (streams(probe), ValueError("COMMAND_FAILED")):
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(D, "command", side_effect=[failure]) as command, \
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
                "let descriptor = NWBrowser.Descriptor.bonjour(type: Self.serviceType, domain: nil)",
                "case .bonjour: observed.browserIncludesTXT = false",
                "guard observed.browserTransport == .none",
                "!observed.browserIncludesTXT",
                "service.noAutoRename = true", "configuredServiceTxtReadbackMatches = raw == expected",
                '"plat=IOS", "caps=LAN", "pv=1"',
                "observationNanoseconds: UInt64 = 30_000_000_000",
                "cancellationNanoseconds: UInt64 = 5_000_000_000"):
            self.assertIn(expression, probe)
        main = (ROOT / "scripts/diagnostics/intel-lan-host/main.swift").read_text()
        self.assertIn('CommandLine.arguments[3] == "--browser-descriptor"', main)
        self.assertNotIn("--browser-parameters", main)
        self.assertIn('P2PKIT_LAN_OWNED_TXT_V1 ', main)

    def test_callback_any_interface_pattern_is_explicitly_uint32(self):
        probe = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        signature = ("    private func callbackInterface(_ value: UInt32, selected: UInt32)"
                     " -> CallbackInterfaceClass {")
        self.assertEqual(1, probe.count(signature))
        classifier = probe.split(signature, 1)[1].split("    private func txtQueryResult(", 1)[0]
        self.assertIn("switch value {", classifier)
        self.assertEqual(1, classifier.count("case UInt32(kDNSServiceInterfaceIndexAny): return .any"))
        self.assertNotIn("case kDNSServiceInterfaceIndexAny:", classifier)

    def test_txt_callback_owner_error_copy_and_retirement_source_seams(self):
        probe = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        callback = probe.split("    private static let txtReply:", 1)[1].split("    private func startTXTQuery", 1)[0]
        self.assertLess(callback.index("if errorCode != kDNSServiceErr_NoError"),
                        callback.index("owner.txtQueryResult("))
        self.assertIn("owner.txtQueryFailed(context, errorCode: errorCode)", callback)
        for expression in (
                "import dnssd", "DNSServiceConstructFullName(buffer.baseAddress, n, t, d)",
                "DNSServiceSetDispatchQueue(reference, queue)",
                "context.active && slot.context === context && slot.reference != nil",
                "guard currentTXTQuery(context), acceptingObservation() else { return }",
                "reference == peers[index].queries[context.role.rawValue].reference",
                "interfaceIndex == context.interfaceIndex",
                "(context.role != .concreteTXT || observed.interfaceMatched)",
                "UInt16(kDNSServiceType_TXT)", "UInt16(kDNSServiceClass_IN)",
                "Data(bytes: rdata!, count: Int(rdlen))", "received == context.expected",
                "context.fullName.indices.allSatisfy", "interfaceCount <= 128",
                "value > 0, value <= 0x7fff_ffff", "case .cellular: return nil",
                "!peers[index].queriesAttempted", "!slot.attempted", "DNSServiceRefDeallocate(reference)",
                "slot.reference = nil", "let queries = [QuerySlot(), QuerySlot(), QuerySlot()]",
                "peer.queries[role.rawValue].reference == nil && queryObservation(index: index, role: role).retired",
                "for role in QueryRole.allCases where queryObservation(index: index, role: role).retired",
                "peer.queries[role.rawValue].context = nil"):
            self.assertIn(expression, probe)
        retire = probe.split("    private func retireTXTQuery(index: Int, role: QueryRole, reason: RetirementReason)", 1)[1].split(
            "    private func cancellationCallbackInTime", 1)[0]
        self.assertLess(retire.index("slot.context?.active = false"), retire.index("slot.reference = nil"))
        self.assertLess(retire.index("slot.reference = nil"), retire.index("queue.async"))
        self.assertLess(retire.index("queue.async"), retire.index("DNSServiceRefDeallocate(reference)"))
        self.assertEqual(2, retire.count("queue.async"))
        self.assertLess(retire.index("DNSServiceRefDeallocate(reference)"), retire.index("observed.retired = true"))
        self.assertNotIn("DNSServiceProcessResult(", probe)
        creation = probe.split("    private func startTXTQuery(", 1)[1].split("    private func currentTXTQuery", 1)[0]
        self.assertIn("role == .concreteTXT ? interfaceIndex : kDNSServiceInterfaceIndexLocalOnly", creation)
        self.assertIn("role == .localSRV ? UInt16(kDNSServiceType_SRV) : UInt16(kDNSServiceType_TXT)", creation)
        self.assertIn("kDNSServiceFlagsIncludeP2P | kDNSServiceFlagsReturnIntermediates", creation)
        self.assertNotIn("kDNSServiceInterfaceIndexAny", creation)  # classification elsewhere is not an Any query
        self.assertLess(creation.index("DNSServiceSetDispatchQueue(reference, queue)"),
                        creation.index("observed.startMilliseconds = elapsedMilliseconds()"))
        errors = probe.split("    private func txtQueryFailed(", 1)[1].split("    private func callbackInterface", 1)[0]
        absence = errors.split("if errorCode == kDNSServiceErr_NoSuchRecord", 1)[1].split(
            "if observed.errorCode == 0", 1)[0]
        self.assertIn("bumpTXT(\\.absenceCallbacks", absence)
        self.assertIn("return", absence)
        self.assertNotIn("retireTXTQuery", absence)
        self.assertNotIn("observed.errorCode =", absence)
        self.assertNotIn("rdata", errors)  # DNS-SD error fields remain undefined
        result = probe.split("    private func txtQueryResult(", 1)[1].split("    private func clearCurrent", 1)[0]
        srv = result.split("if context.role == .localSRV", 1)[1].split("guard rdlen == 0", 1)[0]
        self.assertIn("guard rdlen >= 7, rdata != nil", srv)
        self.assertIn("return", srv)
        self.assertNotIn("Data(", srv)
        self.assertNotIn("matchesExpected =", srv)
        self.assertIn("if !serviceStillPresent", probe)
        self.assertIn("retireQueries(index: index, reason: .serviceRemoved)", probe)
        self.assertIn("retireTXTQuery(index: index, role: .concreteTXT, reason: .interfaceRemoved)", probe)
        self.assertIn("Int((now - startedAt) / 1_000_000) - observationElapsed", probe)
        self.assertIn("now <= cancellationDeadline", probe)

    def test_unchanged_capture_bounds_and_finally_owned_source_joins(self):
        diagnostic_budgets = {"compile-cli": 300, "sdk-path": 120, "cli-architecture": 120,
                              "cli-owned_txt": 120, "COMPILE-CLI": 120,
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
