#!/usr/bin/env python3
"""Offline supplied-result controls for DNS-SD CLI and retained APP helpers, not native acceptance."""
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
POLICY = "WITH_TXT"
TOKENS = {"CLI": "a" * 32, "APP": "e" * 32}
ACTIVE_TOKENS = {"CLI": TOKENS["CLI"]}
TXT_HISTORY = {"observations", "matchingObservations", "malformedObservations"}
TXT_FLAGS = {"received", "present", "identityMatched", "matchesExpected", "rawMatchesExpected", "malformed"}
TXT_FIELDS = TXT_HISTORY | TXT_FLAGS | {"ownedResults", "maximumBytes", "kind"}
INTERFACE_KINDS = {"cellular", "loopback", "other", "unknown", "wifi", "wiredEthernet"}
SOURCE = {"commit": "c" * 40, "tree": "d" * 40}
CONTEXT = {"GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "ios-x64"}
UDID = "11111111-2222-3333-4444-555555555555"
CONFIG_BOOLS = {"listenerObserved", "listenerNoDelay", "listenerP2P", "listenerCellBan",
                "browserObserved", "browserP2P", "browserCellBan", "browserIncludesTXT",
                "advertisementAfterReady", "noAutoRename", "configuredServiceTxtPresent",
                "configuredServiceTxtReadbackMatches", "configuredServiceTxtShapeValid"}
DNS_BROWSE_FLAGS = {"attempted", "created", "started", "retired", "ambiguous", "unsupportedScope"}
DNS_BROWSE_COUNTS = {"callbacks", "ownedAdds", "ownedRemoves", "batches"}
DNS_RESOLVE_FLAGS = {"attempted", "created", "started", "retired", "invalidated", "scopeMatches",
                     "scopeValid", "identityMatched", "received", "matchesExpected", "portMatches"}
DNS_RESOLVE_COUNTS = {"callbacks", "matchingCallbacks"}
DNS_SCOPES = {"none", "concrete", "localOnly", "p2p", "any", "otherSpecial"}


def dns_browse_fixture(started=True):
    value = {key: False for key in DNS_BROWSE_FLAGS}
    value.update({key: 0 for key in DNS_BROWSE_COUNTS})
    value.update(errorCode=0, startMilliseconds=-1, retirementMilliseconds=-1)
    if started:
        value.update(attempted=True, created=True, started=True, retired=True,
                     startMilliseconds=0, retirementMilliseconds=30000)
    return value


def dns_resolve_fixture(success=False, requested_scope="concrete", returned_scope=None):
    value = {key: False for key in DNS_RESOLVE_FLAGS}
    value.update({key: 0 for key in DNS_RESOLVE_COUNTS})
    value.update(errorCode=0, requestedScope="none", returnedScope="none", bytes=0,
                 startMilliseconds=-1, resultMilliseconds=-1, retirementMilliseconds=-1)
    if success:
        returned_scope = requested_scope if returned_scope is None else returned_scope
        value.update(attempted=True, created=True, started=True, retired=True, callbacks=1,
                     matchingCallbacks=1, requestedScope=requested_scope, returnedScope=returned_scope,
                     scopeMatches=requested_scope == returned_scope, scopeValid=True, identityMatched=True,
                     received=True, matchesExpected=True, portMatches=True, bytes=130,
                     startMilliseconds=100, resultMilliseconds=200, retirementMilliseconds=200)
    return value


def fixture(policy="WITH_TXT", discovered=False, mode="cli"):
    peer = {key: 0 for key in D.COUNTERS}
    peer.update({key: False for key in D.PEER_BOOLS})
    peer.update(listenerReady=1, browserReady=1, listenerCancelled=True, browserCancelled=True,
                listenerLastState="ready", browserLastState="ready",
                listenerError={"domain": "none", "code": 0}, browserError={"domain": "none", "code": 0})
    peer["configuration"] = {key: True for key in CONFIG_BOOLS}
    peer["configuration"].update(listenerTransport="tcp", browserTransport="none")
    peer["interfaces"] = {"observed": False, "count": 0, "kinds": []}
    peer["txtMetadata"] = {key: 0 for key in TXT_HISTORY}
    peer["txtMetadata"].update({key: False for key in TXT_FLAGS})
    peer["txtMetadata"].update(ownedResults=0, maximumBytes=0, kind="none")
    if discovered:
        peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=1,
                    ownRegistrationObserved=True, registrationAdded=1)
        peer["interfaces"] = {"observed": True, "count": 1, "kinds": ["wifi"]}
        peer["txtMetadata"].update(observations=1, matchingObservations=1, ownedResults=1,
                                   maximumBytes=130, kind="bonjour", received=True, present=True,
                                   identityMatched=True, matchesExpected=True, rawMatchesExpected=True)
    if mode == "cli":
        peer["firstResultMilliseconds"] = 0 if discovered else -1
        peer["dnsResolve"] = dns_resolve_fixture()
    value = {"schema": 1, "diagnosticOnly": True, "mode": mode, "browserDescriptor": policy,
            "outcome": "discovered" if discovered else "notDiscovered", "windowMilliseconds": 30000,
            "observationElapsedMilliseconds": 30001, "cleanupElapsedMilliseconds": 10,
            "isSimulatorBuild": True, "isX86_64Build": True, "counterOverflow": False,
            "packaging": {key: mode == "app" for key in D.PACKAGE_KEYS},
            "peers": [copy.deepcopy(peer), copy.deepcopy(peer)],
            "cleanup": {"listenersCreated": 2, "listenersCancelled": 2, "browsersCreated": 2,
                        "browsersCancelled": 2, "complete": True}}
    if mode == "cli":
        value["dnsBrowse"] = dns_browse_fixture()
    return value


def dns_fixture(requested_scope="concrete", returned_scope=None):
    value = fixture()
    value["dnsBrowse"].update(callbacks=2, ownedAdds=2, batches=1)
    for peer in value["peers"]:
        peer.update(ownRegistrationObserved=True, registrationAdded=1)
        peer["dnsResolve"] = dns_resolve_fixture(True, requested_scope, returned_scope)
    return value


def maximum_cli_layout():
    """Independent-field encoding upper bound, deliberately NOT an admissible native observation."""
    value = dns_fixture("otherSpecial", "otherSpecial")
    value.update(observationElapsedMilliseconds=120000, cleanupElapsedMilliseconds=5000)
    for field in ("diagnosticOnly", "isSimulatorBuild", "isX86_64Build", "counterOverflow"):
        value[field] = False  # `false` is longer than `true`.
    value["cleanup"]["complete"] = False
    for peer in value["peers"]:
        peer.update({field: 65535 for field in D.COUNTERS})
        peer.update({field: False for field in D.PEER_BOOLS})
        peer["firstResultMilliseconds"] = 120000
        for kind in ("listener", "browser"):
            peer[kind + "LastState"] = max(D.STATES, key=len)
            peer[kind + "Error"] = {"domain": "other", "code": -(2 ** 31)}
        peer["configuration"].update({field: False for field in CONFIG_BOOLS})
        peer["configuration"].update(listenerTransport=max(D.TRANSPORTS, key=len),
                                     browserTransport=max(D.TRANSPORTS, key=len))
        peer["interfaces"] = {"observed": False, "count": 128, "kinds": sorted(INTERFACE_KINDS)}
        peer["txtMetadata"].update({field: 65535 for field in TXT_HISTORY})
        peer["txtMetadata"].update({field: False for field in TXT_FLAGS})
        peer["txtMetadata"].update(ownedResults=128, maximumBytes=65535, kind="bonjour")
        peer["dnsResolve"].update({field: False for field in DNS_RESOLVE_FLAGS})
        peer["dnsResolve"].update(callbacks=1, matchingCallbacks=1, errorCode=-(2 ** 31), bytes=65535,
                                  startMilliseconds=125000, resultMilliseconds=125000,
                                  retirementMilliseconds=125000)
    value["dnsBrowse"].update({field: False for field in DNS_BROWSE_FLAGS})
    value["dnsBrowse"].update({field: 256 for field in DNS_BROWSE_COUNTS})
    value["dnsBrowse"].update(errorCode=-(2 ** 31), startMilliseconds=125000, retirementMilliseconds=125000)
    return value


def streams(probe=None, policy="WITH_TXT", token=None, **extra):
    value = {"schema": 1, "token": TOKENS["CLI"] if token is None else token,
             "browserDescriptor": policy, "probe": fixture(policy) if probe is None else probe}
    value.update(extra)
    return {"stdout": b"P2PKIT_LAN_DNS_SD_RESOLVE_V1 " + json.dumps(value).encode() + b"\n", "stderr": b""}


def app_streams(probe=None, token=None, permission="notObserved", **extra):
    value = {"schema": 1, "token": TOKENS["APP"] if token is None else token,
             "probe": fixture(mode="app") if probe is None else probe,
             "permission": permission, "appNotRunning": True}
    value.update(extra)
    return {"stdout": b"P2PKIT_LAN_APP_V1 " + json.dumps(value).encode() + b"\n", "stderr": b""}


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
            "RUNNER_OS": "macOS", "RUNNER_ARCH": "X64", "ImageOS": "macos15", "ImageVersion": "synthetic",
            "P2PKIT_DIAGNOSTIC_MODE": "owned-txt"}
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
            self.assertIsNot(original_phase, owner.phase)
            self.assertEqual(1200, D.EXECUTION_END)
            if failure == "prepare":
                raise ValueError("synthetic preparation failure")
            for label in D.GATE.INTEL_PREPARE:
                owner.phase(label)

        def phase(label):
            self.assertEqual(600 if label == "intel-bootstatus" else 300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
            if label == "intel-bootstatus":
                if failure == "bootstatus-error":
                    raise ValueError("synthetic bootstatus failure")
                if failure == "bootstatus-interrupted":
                    raise KeyboardInterrupt()
            return b"synthetic-phase-only"

        original_phase = mock.Mock(side_effect=phase)
        owner.phase = original_phase

        def retire():
            events.append("owner-retire")
            self.assertIs(original_phase, vars(owner)["phase"])
            self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
            self.assertEqual(2480, D.EXECUTION_END)
            self.assertIs(D.MAINTAINED_INTEL_WORK_SECONDS, D.GATE._intel_work_seconds)
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
            if label == "cli-probe":
                probe = fixture()
                if failure == "cli-setup":
                    probe["outcome"] = "setupFailed"
                return streams(probe)
            return {"stdout": b"", "stderr": b""}

        def checked_sdk(selected, evidence):
            events.append("sdk-contract")
            self.assertEqual(sdk, selected)
            if failure == "sdk-contract":
                raise ValueError("synthetic incompatible SDK declaration")
            if failure == "sdk-contract-interrupted":
                raise KeyboardInterrupt()
            written["dns-sd-sdk.json"] = {"schema": 1, "compatibleDeclarations": True}

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
                (D, "sdk_contract", {"side_effect": checked_sdk}),
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
            app_stage = stack.enter_context(mock.patch.object(D, "run_app", side_effect=AssertionError("no APP stage")))
            app_retire = stack.enter_context(mock.patch.object(D, "retire_apps", side_effect=AssertionError("no APP cleanup")))
            stack.enter_context(mock.patch.dict(D.os.environ, environment, clear=True))
            stack.enter_context(mock.patch.object(D, "EXECUTION_END", None))
            stack.enter_context(redirect_stdout(io.StringIO()))
            code = D.run()
            app_stage.assert_not_called()
            app_retire.assert_not_called()
            self.assertEqual(2, state.call_count)  # initial source and unchanged finally recheck
            self.assertEqual({"workSeconds": 600, "maintainedWorkSeconds": 300,
                              "elapsedCeilingSeconds": 620, "productiveSeconds": 1200},
                             written["source.json"]["bootstatusMeasurement"])
            self.assertNotIn("appProbeMeasurement", written["source.json"])
            self.assertEqual({"CLI": TOKENS["CLI"]}, written["source.json"]["armTokens"])
            self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
            self.assertIs(original_phase, vars(owner)["phase"])
        return code, events, written, owner

    def test_diagnostic_app_probe_exact_selector_reservation_and_success_restoration(self):
        original = D.MAINTAINED_INTEL_WORK_SECONDS
        self.assertIs(original, D.GATE._intel_work_seconds)
        self.assertEqual({"workSeconds": 300, "maintainedWorkSeconds": 120,
                          "elapsedCeilingSeconds": 320, "requiredStartRoomSeconds": 460,
                          "productiveSeconds": 1200, "cleanupAbsoluteSeconds": 2480}, D.APP_PROBE_MEASUREMENT)
        self.assertEqual(1280, 2480 - 1200)
        self.assertEqual(460, 320 + 140)
        self.assertLessEqual((6 + 3) * 140, 1280)

        class Label(str):
            pass

        labels = ("app-probe ", "APP-PROBE", "app-probe-extra", "cli-probe", "compile-cli", "build-app",
                  "installed-app-after", *D.GATE.INTEL_PREPARE, *D.GATE.INTEL_RETIRE,
                  None, 300, ["app-probe"], Label("app-probe"))
        with D.diagnostic_app_probe_budget():
            measured = D.GATE._intel_work_seconds
            self.assertIsNot(original, measured)
            self.assertEqual(300, measured("app-probe"))
            for label in labels:
                with self.subTest(label=label):
                    self.assertEqual(original(label), measured(label))
            with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_APP_PROBE_BASELINE"):
                with D.diagnostic_app_probe_budget():
                    self.fail("nested APP scope entered")
            self.assertIs(measured, D.GATE._intel_work_seconds)
        self.assertIs(original, D.GATE._intel_work_seconds)
        self.assertEqual(120, original("app-probe"))

        replacement = mock.Mock(return_value=120)
        with mock.patch.object(D.GATE, "_intel_work_seconds", replacement):
            with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_APP_PROBE_BASELINE"):
                with D.diagnostic_app_probe_budget():
                    self.fail("replaced maintained selector admitted")
            self.assertIs(replacement, D.GATE._intel_work_seconds)
            replacement.assert_not_called()
        for target, name, invalid in ((D.GATE.simulator, "SECONDS", 120.0),
                                      (D.GATE, "INTEL_BOOTSTATUS_SECONDS", 600),
                                      (D.GATE, "TERMINATION_GRACE_SECONDS", 16),
                                      (D.GATE, "TERMINATION_KILL_SECONDS", True)):
            with self.subTest(baseline=name), mock.patch.object(target, name, invalid):
                with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_APP_PROBE_BASELINE"):
                    with D.diagnostic_app_probe_budget():
                        self.fail("changed maintained baseline admitted")
                self.assertIs(original, D.GATE._intel_work_seconds)

        for remaining in (None, 319.999, 320):
            with self.subTest(capture_room=remaining), mock.patch.object(D, "EXECUTION_END", remaining), \
                    mock.patch.object(D.time, "monotonic", return_value=0), \
                    mock.patch.object(D.GATE, "_intel_capture_phase",
                                      side_effect=RuntimeError("capture sentinel")) as capture:
                with D.diagnostic_app_probe_budget():
                    if remaining == 320:
                        with self.assertRaisesRegex(RuntimeError, "capture sentinel"):
                            D.command(Path("/unused"), "app-probe", ["/unused"])
                        capture.assert_called_once_with(Path("/unused"), "app-probe", ["/unused"])
                    else:
                        with self.assertRaisesRegex(ValueError, "COMMAND_WINDOW"):
                            D.command(Path("/unused"), "app-probe", ["/unused"])
                        capture.assert_not_called()
                self.assertEqual(remaining, D.EXECUTION_END)
                self.assertIs(original, D.GATE._intel_work_seconds)

        for remaining in (None, 459.999, 460):
            with self.subTest(app_and_post_room=remaining):
                events, identities, emitted, attempts, results, error = self._run_mock_app_stage(remaining=remaining)
                labels = [label for label, _ in events]
                self.assertTrue(attempts["installed"])
                if remaining == 460:
                    self.assertIsNone(error)
                    self.assertEqual(1, labels.count("app-probe"))
                    self.assertEqual("installed-app-after", labels[-1])
                    self.assertEqual("installed-after", identities[-1])
                    self.assertEqual(["APP"], emitted)
                    self.assertEqual({"CLI", "APP"}, set(results))
                    self.assertTrue(attempts["runnerAttempted"])
                else:
                    self.assertEqual("DIAGNOSTIC_APP_PROBE_WINDOW", error)
                    self.assertFalse(attempts["runnerAttempted"])
                    self.assertNotIn("app-probe", labels)
                    self.assertNotIn("installed-app-after", labels)
                    self.assertEqual([], emitted)
                    self.assertEqual({"CLI"}, set(results))

    def test_diagnostic_app_probe_failure_interrupt_and_scope_drift_restore(self):
        original = D.MAINTAINED_INTEL_WORK_SECONDS
        for use_after_drift in (False, True):
            with self.subTest(use_after_drift=use_after_drift):
                with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_APP_PROBE_BINDING"):
                    with D.diagnostic_app_probe_budget():
                        measured = D.GATE._intel_work_seconds
                        D.GATE._intel_work_seconds = lambda _label: 999
                        if use_after_drift:
                            measured("app-probe")
                self.assertIs(original, D.GATE._intel_work_seconds)

        # Exercise the real command's original-result validation, not just a mock exception.
        row = {"stdoutBytes": 0, "stderrBytes": 0, "stdoutSha256": D.digest(b""),
               "stderrSha256": D.digest(b""), "exitCode": 0, "timedOut": False,
               "outputLimitExceeded": False, "ownedGroupDrained": True}
        for defect, reason in (("changed", "COMMAND_RESULT_CHANGED"), ("failed", "COMMAND_FAILED")):
            supplied = {**row, "exitCode": 1 if defect == "failed" else 0}
            originals = [b"changed" if defect == "changed" else D.encoded(supplied), b"", b""]
            with self.subTest(result=defect), mock.patch.object(D, "EXECUTION_END", 320), \
                    mock.patch.object(D.time, "monotonic", return_value=0), \
                    mock.patch.object(D.GATE, "_intel_capture_phase", return_value=supplied) as capture, \
                    mock.patch.object(D.GATE, "simulator_original", side_effect=originals):
                with self.assertRaisesRegex(ValueError, reason):
                    with D.diagnostic_app_probe_budget():
                        D.command(Path("/unused"), "app-probe", ["/unused"])
                capture.assert_called_once_with(Path("/unused"), "app-probe", ["/unused"])
                self.assertIs(original, D.GATE._intel_work_seconds)

        cases = (("app-probe", None, False), ("app-result", None, False), ("app-setup", None, False),
                 (None, ValueError("primary APP failure"), False), (None, KeyboardInterrupt(), False),
                 (None, None, True), (None, ValueError("primary with binding drift"), True),
                 (None, KeyboardInterrupt(), True))
        for failure, primary, drift in cases:
            with self.subTest(failure=failure, primary=type(primary).__name__, drift=drift):
                events, identities, emitted, attempts, results, error = self._run_mock_app_stage(
                    failure, primary=primary, drift=drift, retire=True)
                self.assertIsNotNone(error)
                if primary is not None:
                    self.assertIs(primary, error)
                elif drift:
                    self.assertEqual("DIAGNOSTIC_APP_PROBE_BINDING", error)
                labels = [label for label, _ in events]
                self.assertEqual(1, labels.count("app-probe"))
                self.assertEqual(len(labels), len(set(labels)))
                self.assertNotIn("installed-app-after", labels)
                self.assertNotIn("installed-after", identities)
                self.assertEqual(["uninstall-0", "uninstall-1"], labels[-2:])
                self.assertEqual({"installed": True, "runnerAttempted": True}, attempts)
                self.assertEqual([], emitted)
                self.assertEqual({"CLI"}, set(results))
                self.assertIs(original, D.GATE._intel_work_seconds)
                self.assertEqual(120, original("app-probe"))

    def test_diagnostic_bootstatus_exact_labels_residual_windows_and_success_restoration(self):
        self.assertEqual({"workSeconds": 600, "maintainedWorkSeconds": 300,
                          "elapsedCeilingSeconds": 620, "productiveSeconds": 1200}, D.BOOTSTATUS_MEASUREMENT)
        self.assertEqual(("simulator-macos-version", "simulator-xcode-version", "simulator-first-launch",
                          "simulator-runtimes", "intel-bootstatus-help", "simulator-devices",
                          "intel-boot", "intel-bootstatus", "intel-prelaunch"), D.GATE.INTEL_PREPARE)

        class Owner:
            def phase(owner, label):
                return delegate(label, D.GATE.INTEL_BOOTSTATUS_SECONDS, D.GATE._intel_work_seconds(label))

        delegate = mock.Mock(return_value=b"synthetic-phase")
        for label in D.GATE.INTEL_PREPARE:
            work = 600 if label == "intel-bootstatus" else 120
            required = work + 20
            for remaining in (None, required - 0.001, required):
                with self.subTest(label=label, remaining=remaining), \
                        mock.patch.object(D, "EXECUTION_END", remaining), \
                        mock.patch.object(D.time, "monotonic", return_value=0):
                    owner = Owner()
                    delegate.reset_mock()
                    with D.diagnostic_bootstatus_budget(owner):
                        if remaining == required:
                            self.assertEqual(b"synthetic-phase", owner.phase(label))
                            delegate.assert_called_once_with(label, 600 if work == 600 else 300, work)
                        else:
                            with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_PREPARE_WINDOW"):
                                owner.phase(label)
                            delegate.assert_not_called()
                        self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                    self.assertNotIn("phase", vars(owner))
                    self.assertIs(Owner.phase, owner.phase.__func__)
                    self.assertEqual(remaining, D.EXECUTION_END)

        for label in ("intel-bootstatus ", "INTEL-BOOTSTATUS", "intel-bootstatus-extra", "bootstatus",
                      "compile-cli", *D.GATE.INTEL_RETIRE, None, 600, ["intel-bootstatus"]):
            with self.subTest(rejected_label=label), mock.patch.object(D, "EXECUTION_END", 900), \
                    mock.patch.object(D.time, "monotonic", return_value=0):
                owner = Owner()
                delegate.reset_mock()
                with D.diagnostic_bootstatus_budget(owner):
                    with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_OWNER_PHASE"):
                        owner.phase(label)
                delegate.assert_not_called()
                self.assertNotIn("phase", vars(owner))
                self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)

        for inherited in (600, 120, 300.0, True, None):
            with self.subTest(inherited=inherited), \
                    mock.patch.object(D.GATE, "INTEL_BOOTSTATUS_SECONDS", inherited):
                owner = Owner()
                delegate.reset_mock()
                with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_BOOTSTATUS_BASELINE"):
                    with D.diagnostic_bootstatus_budget(owner):
                        self.fail("invalid maintained budget entered scope")
                self.assertEqual(inherited, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                self.assertNotIn("phase", vars(owner))
                delegate.assert_not_called()

        with mock.patch.object(D, "EXECUTION_END", 900), \
                mock.patch.object(D.time, "monotonic", return_value=0):
            owner = Owner()
            instance_phase = mock.Mock(return_value=b"instance-phase")
            owner.phase = instance_phase
            with D.diagnostic_bootstatus_budget(owner):
                self.assertEqual(b"instance-phase", owner.phase("intel-bootstatus"))
            instance_phase.assert_called_once_with("intel-bootstatus")
            self.assertIs(instance_phase, vars(owner)["phase"])
            self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
            instance_phase.reset_mock()
            with D.diagnostic_bootstatus_budget(owner):
                D.GATE.INTEL_BOOTSTATUS_SECONDS = 600  # reject unexpected in-scope module drift
                with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_BOOTSTATUS_BASELINE"):
                    owner.phase("intel-bootstatus")
            instance_phase.assert_not_called()
            self.assertIs(instance_phase, vars(owner)["phase"])
            self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)

        # Readiness does not replenish this supplied absolute deadline or alter ordinary command budgets.
        with mock.patch.object(D, "EXECUTION_END", 900), \
                mock.patch.object(D.time, "monotonic", return_value=0) as clock:
            owner = Owner()
            delegate.reset_mock()
            with D.diagnostic_bootstatus_budget(owner):
                owner.phase("intel-bootstatus")
            delegate.assert_called_once_with("intel-bootstatus", 600, 600)
            for label, last_start in (("build-app", 580), ("cli-probe", 760), ("app-probe", 760)):
                for now in (last_start, last_start + 0.001):
                    with self.subTest(command=label, elapsed=now), \
                            mock.patch.object(D.GATE, "_intel_capture_phase",
                                              side_effect=RuntimeError("capture sentinel")) as capture:
                        clock.return_value = now
                        if now == last_start:
                            with self.assertRaisesRegex(RuntimeError, "capture sentinel"):
                                D.command(Path("/unused"), label, ["/unused"])
                            capture.assert_called_once_with(Path("/unused"), label, ["/unused"])
                        else:
                            with self.assertRaisesRegex(ValueError, "COMMAND_WINDOW"):
                                D.command(Path("/unused"), label, ["/unused"])
                            capture.assert_not_called()
                        self.assertEqual(900, D.EXECUTION_END)
                        self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)

    def test_diagnostic_bootstatus_failure_and_interrupt_restore_without_readiness_bypass(self):
        class Owner:
            def phase(owner, label):
                return delegate(label)

        for instance_attribute in (False, True):
            for error in (ValueError("synthetic phase failure"), KeyboardInterrupt()):
                for location in ("delegate", "body"):
                    with self.subTest(instance_attribute=instance_attribute, error=type(error).__name__,
                                      location=location), \
                            mock.patch.object(D, "EXECUTION_END", 900), \
                            mock.patch.object(D.time, "monotonic", return_value=0):
                        owner = Owner()

                        def delegated(label):
                            self.assertEqual("intel-bootstatus", label)
                            self.assertEqual(600, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                            if location == "delegate":
                                raise error
                            return b"synthetic-ready"

                        delegate = mock.Mock(side_effect=delegated)
                        if instance_attribute:
                            owner.phase = delegate
                        with self.assertRaises(type(error)) as caught:
                            with D.diagnostic_bootstatus_budget(owner):
                                owner.phase("intel-bootstatus")
                                self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                                raise error
                        self.assertIs(error, caught.exception)
                        delegate.assert_called_once_with("intel-bootstatus")
                        self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                        self.assertEqual(900, D.EXECUTION_END)
                        if instance_attribute:
                            self.assertIs(delegate, vars(owner)["phase"])
                        else:
                            self.assertNotIn("phase", vars(owner))
                            self.assertIs(Owner.phase, owner.phase.__func__)

        for failure, reason in (("bootstatus-error", "PREPARE_FAILED"),
                                ("bootstatus-interrupted", "PREPARE_INTERRUPTED")):
            with self.subTest(controller_failure=failure):
                code, events, written, owner = self._run_preboot_controller(failure)
                self.assertEqual(1, code)
                self.assertEqual([mock.call(label) for label in D.GATE.INTEL_PREPARE[:-1]], owner.phase.call_args_list)
                self.assertNotIn("binary-recheck", events)
                self.assertNotIn("cli-probe", events)
                self.assertNotIn("app-stage", events)
                self.assertEqual("owner-retire", events[-1])
                self.assertEqual([reason], written["comparison.json"]["errors"])
                self.assertEqual({}, written["comparison.json"]["results"])
                owner.prepare.assert_called_once_with()
                owner.retire.assert_called_once_with()
                self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)

    def test_diagnostic_bootstatus_strict_620_edge_preserves_original_failure_predicates(self):
        selected, root = {"device": {"udid": UDID}}, "/synthetic-source"

        def originals(label, end, **changes):
            row = {"schema": 1, "label": label, "argv": D.GATE._intel_phase_command(label, selected),
                   "cwd": root, "startedUtc": "2026-10-07T00:00:00+00:00", "finishedUtc": end,
                   "exitCode": 0, "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True,
                   "stdoutBytes": 0, "stdoutSha256": D.digest(b""), "stderrBytes": 0, "stderrSha256": D.digest(b"")}
            row.update(changes)
            return {label + "/result.json": D.GATE.simulator.encoded(row),
                    label + "/stdout.bin": b"", label + "/stderr.bin": b""}

        owner = mock.Mock()
        raw = originals("intel-bootstatus", "2026-10-07T00:10:20+00:00")
        owner.phase = mock.Mock(side_effect=lambda label: D.GATE._intel_phase(raw, label, root, selected))
        previous = owner.phase
        with self.assertRaisesRegex(ValueError, "INTEL_PHASE_DEADLINE"):
            D.GATE._intel_phase(raw, "intel-bootstatus", root, selected)
        with mock.patch.object(D, "EXECUTION_END", 900), \
                mock.patch.object(D.time, "monotonic", return_value=0):
            with D.diagnostic_bootstatus_budget(owner):
                self.assertEqual(0, owner.phase("intel-bootstatus")["exitCode"])
                self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                for changes, reason in (({"exitCode": 1}, "INTEL_PHASE_FAILED"),
                                        ({"exitCode": False}, "INTEL_PHASE_FAILED"),
                                        ({"timedOut": True}, "INTEL_PHASE_FAILED"),
                                        ({"outputLimitExceeded": True}, "INTEL_PHASE_FAILED"),
                                        ({"ownedGroupDrained": False}, "INTEL_PHASE_FAILED"),
                                        ({"stdoutBytes": 1}, "INTEL_PHASE_STREAM_HASH"),
                                        ({"stderrSha256": "0" * 64}, "INTEL_PHASE_STREAM_HASH"),
                                        ({"argv": ["/unused"]}, "INTEL_PHASE_COMMAND"),
                                        ({"finishedUtc": "2026-10-07T00:10:20.000001+00:00"}, "INTEL_PHASE_DEADLINE"),
                                        ({"finishedUtc": "2026-10-06T23:59:59+00:00"}, "INTEL_PHASE_DEADLINE")):
                    with self.subTest(changes=changes):
                        raw = originals("intel-bootstatus", "2026-10-07T00:10:20+00:00", **changes)
                        with self.assertRaisesRegex(ValueError, reason):
                            owner.phase("intel-bootstatus")
                        self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
                for end, accepted in (("2026-10-07T00:02:20+00:00", True),
                                      ("2026-10-07T00:02:20.000001+00:00", False)):
                    raw = originals("intel-prelaunch", end)
                    if accepted:
                        self.assertEqual(0, owner.phase("intel-prelaunch")["exitCode"])
                    else:
                        with self.assertRaisesRegex(ValueError, "INTEL_PHASE_DEADLINE"):
                            owner.phase("intel-prelaunch")
            self.assertIs(previous, vars(owner)["phase"])
            self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
        raw = originals("intel-bootstatus", "2026-10-07T00:10:20+00:00")
        with self.assertRaisesRegex(ValueError, "INTEL_PHASE_DEADLINE"):
            D.GATE._intel_phase(raw, "intel-bootstatus", root, selected)

    def test_preboot_build_order_keeps_binary_identity_and_owned_retirement(self):
        code, events, written, owner = self._run_preboot_controller()
        self.assertEqual(0, code)
        self.assertEqual(["sdk-path", "sdk-contract", "compile-cli", "cli-architecture", "binary-initial",
                          "owner-create", "owner-prepare", "binary-recheck", "cli-probe", "owner-retire"], events)
        self.assertEqual({"bytes": len(b"compiled-one"), "sha256": D.digest(b"compiled-one")}, written["cli-binary.json"])
        comparison = written["comparison.json"]
        self.assertEqual([], comparison["errors"])
        self.assertIs(comparison["simulatorRetired"], True)
        self.assertEqual({"CLI"}, set(comparison["results"]))
        self.assertEqual({"schema": 1, "compatibleDeclarations": True}, written["dns-sd-sdk.json"])
        self.assertEqual("notDiscovered", comparison["results"]["CLI"]["probe"]["outcome"])
        owner.prepare.assert_called_once_with()
        owner.retire.assert_called_once_with()

    def test_preboot_build_failures_never_create_or_retire_a_simulator(self):
        labels = ["sdk-path", "sdk-contract", "compile-cli", "cli-architecture"]
        for failure in (*labels, "sdk-interrupted", "sdk-contract-interrupted"):
            with self.subTest(failure=failure):
                code, events, written, owner = self._run_preboot_controller(failure)
                self.assertEqual(1, code)
                count = 1 if failure == "sdk-interrupted" else 2 if failure == "sdk-contract-interrupted" else labels.index(failure) + 1
                expected = labels[:count]
                self.assertEqual(expected, events)
                comparison = written["comparison.json"]
                self.assertEqual(["BUILD_INTERRUPTED" if failure.endswith("interrupted") else "BUILD_FAILED"], comparison["errors"])
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
                expected = ["sdk-path", "sdk-contract", "compile-cli", "cli-architecture", "binary-initial",
                            "owner-create", "owner-prepare"]
                if failure != "prepare":
                    expected.append("binary-recheck")
                self.assertEqual(expected + ["owner-retire"], events)
                comparison = written["comparison.json"]
                self.assertEqual(["PREPARE_FAILED" if failure == "prepare" else "CLI_FAILED"], comparison["errors"])
                self.assertEqual({}, comparison["results"])
                self.assertIs(comparison["simulatorRetired"], True)  # only this mocked owner's successful retire report
                owner.prepare.assert_called_once_with()
                owner.retire.assert_called_once_with()

    def test_cli_or_app_failure_still_retires_owned_resources_without_retry(self):
        # Retained APP helpers have separate controls; the active controller must never call them.
        for failure in ("cli-probe", "cli-setup"):
            with self.subTest(failure=failure):
                code, events, written, owner = self._run_preboot_controller(failure)
                self.assertEqual(1, code)
                self.assertEqual(1, events.count("cli-probe"))
                self.assertNotIn("app-stage", events)
                self.assertNotIn("app-retire", events)
                self.assertEqual("owner-retire", events[-1])
                self.assertEqual(["CLI_FAILED"], written["comparison.json"]["errors"])
                self.assertEqual({}, written["comparison.json"]["results"])
                owner.retire.assert_called_once_with()

    def test_dns_sd_resolution_is_separate_from_native_browser_admission(self):
        value = dns_fixture()
        D.validate_probe(value, POLICY)
        self.assertEqual("notDiscovered", value["outcome"])
        self.assertTrue(all(peer["dnsResolve"]["matchesExpected"] for peer in value["peers"]))
        self.assertTrue(all(peer["resultCallbacks"] == 0 and not peer["expectedPeerObserved"]
                            for peer in value["peers"]))
        bad = copy.deepcopy(value)
        bad["outcome"] = "discovered"
        with self.assertRaises(ValueError):
            D.validate_probe(bad, POLICY)
        absent = fixture()
        absent["dnsBrowse"] = dns_browse_fixture(False)
        D.validate_probe(absent, POLICY)
        for peer in absent["peers"]:
            peer.update(ownRegistrationObserved=True, registrationAdded=1)
        with self.assertRaises(ValueError):
            D.validate_probe(absent, POLICY)
        setup = copy.deepcopy(absent)
        setup["outcome"] = "setupFailed"
        D.validate_probe(setup, POLICY)

    def test_dns_sd_scope_mapping_never_substitutes_local_only_for_concrete(self):
        for requested, returned in (("concrete", "concrete"), ("localOnly", "localOnly"),
                                    ("p2p", "concrete")):
            with self.subTest(requested=requested, returned=returned):
                value = dns_fixture(requested, returned)
                D.validate_probe(value, POLICY)
                resolved = value["peers"][0]["dnsResolve"]
                self.assertEqual(requested, resolved["requestedScope"])
                self.assertEqual(returned, resolved["returnedScope"])
                self.assertEqual(requested == returned, resolved["scopeMatches"])
        for requested, returned in (("concrete", "localOnly"), ("localOnly", "concrete"),
                                    ("p2p", "localOnly"), ("any", "concrete"),
                                    ("otherSpecial", "concrete"), ("none", "none")):
            with self.subTest(invalid=(requested, returned)), self.assertRaises(ValueError):
                D.validate_probe(dns_fixture(requested, returned), POLICY)
        different_concrete_indices = dns_fixture()
        different_concrete_indices["peers"][0]["dnsResolve"]["scopeMatches"] = False
        with self.assertRaises(ValueError):
            D.validate_probe(different_concrete_indices, POLICY)
        unsupported = fixture()
        unsupported["dnsBrowse"].update(callbacks=1, ownedAdds=1, batches=1, unsupportedScope=True)
        D.validate_probe(unsupported, POLICY)
        self.assertTrue(all(not peer["dnsResolve"]["attempted"] for peer in unsupported["peers"]))

    def test_dns_sd_invalidated_resolution_retains_history_not_current_match(self):
        for mutation in ("removal", "ambiguity", "browse-error", "unsupported", "invalidated"):
            with self.subTest(mutation=mutation):
                value = dns_fixture()
                if mutation == "removal":
                    value["dnsBrowse"].update(callbacks=3, ownedRemoves=1)
                    value["peers"][0]["dnsResolve"]["invalidated"] = True
                elif mutation == "ambiguity":
                    value["dnsBrowse"]["ambiguous"] = True
                elif mutation == "browse-error":
                    value["dnsBrowse"]["errorCode"] = -65537
                elif mutation == "unsupported":
                    value["dnsBrowse"]["unsupportedScope"] = True
                else:
                    value["peers"][0]["dnsResolve"]["invalidated"] = True
                with self.assertRaises(ValueError):
                    D.validate_probe(value, POLICY)
                affected = value["peers"][:1] if mutation in {"removal", "invalidated"} else value["peers"]
                for peer in affected:
                    peer["dnsResolve"].update(invalidated=True, matchesExpected=False, portMatches=False)
                D.validate_probe(value, POLICY)
                if mutation == "removal":
                    self.assertIs(value["peers"][1]["dnsResolve"]["matchesExpected"], True)
                self.assertTrue(all(peer["dnsResolve"]["matchingCallbacks"] == 1 and
                                    peer["dnsResolve"]["retired"] for peer in value["peers"]))
                self.assertEqual("notDiscovered", value["outcome"])
        error = dns_fixture()
        failed = error["peers"][0]["dnsResolve"]
        failed["errorCode"] = -65537
        with self.assertRaises(ValueError):
            D.validate_probe(error, POLICY)
        # On an API error the callback's other output fields are undefined, never historical success data.
        failed.update(returnedScope="none", scopeMatches=False, scopeValid=False, identityMatched=False,
                      received=False, matchesExpected=False, portMatches=False, bytes=0, matchingCallbacks=0)
        D.validate_probe(error, POLICY)

    def test_dns_sd_schema_is_closed_typed_bounded_and_payload_free(self):
        self.assertEqual(DNS_SCOPES, D.DNS_SCOPES)
        for field in DNS_BROWSE_FLAGS:
            value = dns_fixture()
            value["dnsBrowse"][field] = 1
            with self.subTest(browse_flag=field), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)
        for field in DNS_RESOLVE_FLAGS:
            value = dns_fixture()
            value["peers"][0]["dnsResolve"][field] = 1
            with self.subTest(resolve_flag=field), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)
        for section, fields in (("dnsBrowse", DNS_BROWSE_COUNTS), ("dnsResolve", DNS_RESOLVE_COUNTS)):
            for field in fields:
                for invalid in ((True, -1, 257) if section == "dnsBrowse" else (True, -1, 2, 257)):
                    value = dns_fixture()
                    target = value[section] if section == "dnsBrowse" else value["peers"][0][section]
                    target[field] = invalid
                    with self.subTest(section=section, field=field, invalid=invalid), self.assertRaises(ValueError):
                        D.validate_probe(value, POLICY)
        for section in ("dnsBrowse", "dnsResolve"):
            for invalid in (True, -(2 ** 31) - 1, 2 ** 31):
                value = dns_fixture()
                target = value[section] if section == "dnsBrowse" else value["peers"][0][section]
                target["errorCode"] = invalid
                with self.subTest(section=section, error=invalid), self.assertRaises(ValueError):
                    D.validate_probe(value, POLICY)
        for field, invalid in (("bytes", 65536), ("bytes", True), ("requestedScope", "wifi"),
                               ("returnedScope", 1), ("hostTarget", "synthetic-private-host"),
                               ("port", 12345), ("txt", "synthetic-private-txt"), ("interfaceIndex", 1)):
            value = dns_fixture()
            value["peers"][0]["dnsResolve"][field] = invalid
            with self.subTest(resolve_field=field), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)
        for field in ("serviceName", "regtype", "domain", "interfaceIndex"):
            value = dns_fixture()
            value["dnsBrowse"][field] = "synthetic-private-value"
            with self.subTest(browse_extra=field), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)
        for section in ("dnsBrowse", "dnsResolve"):
            sample = dns_fixture()
            keys = sample[section] if section == "dnsBrowse" else sample["peers"][0][section]
            for field in keys:
                value = dns_fixture()
                target = value[section] if section == "dnsBrowse" else value["peers"][0][section]
                del target[field]
                with self.subTest(section=section, missing=field), self.assertRaises(ValueError):
                    D.validate_probe(value, POLICY)

    def test_dns_sd_ref_lifecycle_and_observation_offsets_are_consistent(self):
        for section, field, invalid in (("dnsBrowse", "attempted", False),
                                        ("dnsBrowse", "created", False),
                                        ("dnsBrowse", "retired", False),
                                        ("dnsResolve", "attempted", False),
                                        ("dnsResolve", "created", False),
                                        ("dnsResolve", "retired", False),
                                        ("dnsResolve", "resultMilliseconds", -1),
                                        ("dnsResolve", "retirementMilliseconds", 99),
                                        ("dnsResolve", "startMilliseconds", 201)):
            value = dns_fixture()
            target = value[section] if section == "dnsBrowse" else value["peers"][0][section]
            target[field] = invalid
            with self.subTest(section=section, field=field, invalid=invalid), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)
        for section, fields in (("dnsBrowse", ("startMilliseconds", "retirementMilliseconds")),
                                ("dnsResolve", ("startMilliseconds", "resultMilliseconds",
                                                "retirementMilliseconds"))):
            for field in fields:
                for invalid in (True, -2, 120001):
                    value = dns_fixture()
                    target = value[section] if section == "dnsBrowse" else value["peers"][0][section]
                    target[field] = invalid
                    with self.subTest(section=section, field=field, invalid=invalid), self.assertRaises(ValueError):
                        D.validate_probe(value, POLICY)
        for observed, invalid in ((False, 0), (True, -1), (True, 30002), (True, True)):
            value = fixture(discovered=observed)
            value["peers"][0]["firstResultMilliseconds"] = invalid
            with self.subTest(observed=observed, first=invalid), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)

    def test_dns_sd_selected_sdk_declaration_check_is_bounded_and_fail_closed(self):
        sdk = "/Applications/Xcode_26.3.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk"
        # Deliberately tiny recognizer inputs, not a compiled SDK, implementation, or native availability proof.
        declarations = {
            "browse": "DNSServiceBrowse(DNSServiceRef *ref);",
            "resolve": "DNSServiceResolve(DNSServiceRef *ref);",
            "browseReply": "DNSServiceBrowseReply)(DNSServiceRef ref);",
            "resolveReply": "DNSServiceResolveReply)(DNSServiceRef ref);",
            "dispatchQueue": "DNSServiceSetDispatchQueue(DNSServiceRef ref);",
            "deallocate": "DNSServiceRefDeallocate(DNSServiceRef ref);",
            "constructFullName": "DNSServiceConstructFullName(char *name);",
            "interfaceConstants": "kDNSServiceInterfaceIndexAny kDNSServiceInterfaceIndexLocalOnly "
                                  "kDNSServiceInterfaceIndexP2P kDNSServiceFlagsIncludeP2P "
                                  "kDNSServiceFlagsAdd kDNSServiceFlagsMoreComing",
        }
        evidence = Path("/unused-evidence")
        for missing in (None, *declarations):
            raw = "\n".join(value for key, value in declarations.items() if key != missing).encode()
            captured = io.BytesIO(raw)
            with self.subTest(missing=missing), \
                    mock.patch.object(Path, "resolve", autospec=True, side_effect=lambda path, **kwargs: path), \
                    mock.patch.object(Path, "lstat", return_value=mock.Mock(st_mode=D.stat.S_IFREG, st_size=len(raw))), \
                    mock.patch.object(Path, "open", return_value=captured) as opened, \
                    mock.patch.object(D, "write") as written, mock.patch.object(D, "command") as command:
                if missing is None:
                    D.sdk_contract(sdk, evidence)
                else:
                    with self.assertRaisesRegex(ValueError, "DNS_SDK_CONTRACT"):
                        D.sdk_contract(sdk, evidence)
                opened.assert_called_once_with("rb")
                command.assert_not_called()
                written.assert_called_once()
                path, record = written.call_args.args
                self.assertEqual(evidence / "dns-sd-sdk.json", path)
                self.assertEqual({"schema", "sdkPath", "headerRelativePath", "headerBytes", "headerSha256",
                                  "publicContractSha256", "checks", "compatibleDeclarations"}, set(record))
                self.assertEqual(sdk, record["sdkPath"])
                self.assertEqual("usr/include/dns_sd.h", record["headerRelativePath"])
                self.assertEqual(len(raw), record["headerBytes"])
                self.assertEqual(D.digest(raw), record["headerSha256"])
                self.assertEqual("5d0ca50f207f6eb02e09d743f9b65d2ade65e8f81862dcd3703845b4fe87a9c1",
                                 record["publicContractSha256"])
                self.assertEqual({name: name != missing for name in declarations}, record["checks"])
                self.assertIs(record["compatibleDeclarations"], missing is None)
            self.assertTrue(captured.closed)
        for mode, length in ((D.stat.S_IFREG, 0), (D.stat.S_IFREG, 262145), (D.stat.S_IFLNK, 100)):
            with self.subTest(mode=mode, length=length), \
                    mock.patch.object(Path, "resolve", autospec=True, side_effect=lambda path, **kwargs: path), \
                    mock.patch.object(Path, "lstat", return_value=mock.Mock(st_mode=mode, st_size=length)), \
                    mock.patch.object(Path, "open") as opened, mock.patch.object(D, "write") as written:
                with self.assertRaisesRegex(ValueError, "DNS_SDK_HEADER_IDENTITY"):
                    D.sdk_contract(sdk, evidence)
                opened.assert_not_called()
                written.assert_not_called()

    def test_dns_sd_source_keeps_browse_tuple_error_first_and_one_shot_retirement(self):
        source = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        self.assertIn("import dnssd", source)
        for forbidden in ("DNSServiceQueryRecord", "DNSServiceProcessResult", "kDNSServiceFlagsForceMulticast",
                          "kDNSServiceFlagsReturnIntermediates", "kDNSServiceFlagsShareConnection"):
            self.assertNotIn(forbidden, source)
        start = source.split("    private func maybeStartDNSBrowse()", 1)[1].split(
            "    private func dnsBrowseResult(", 1)[0]
        self.assertLess(start.index("!dnsBrowse.attempted"), start.index("DNSServiceBrowse(&reference"))
        self.assertLess(start.index("dnsBrowse.attempted = true"), start.index("DNSServiceBrowse(&reference"))
        for expression in ("listenerLastState == .ready", "browserLastState == .ready",
                           "ownRegistrationObserved", "kDNSServiceFlagsIncludeP2P",
                           "UInt32(kDNSServiceInterfaceIndexAny)", '"local."',
                           "DNSServiceSetDispatchQueue(reference, queue)"):
            self.assertIn(expression, start)
        self.assertEqual(1, source.count("DNSServiceBrowse(&reference"))
        browse = source.split("    private func dnsBrowseResult(", 1)[1].split(
            "    private func startDNSResolve(", 1)[0]
        error_first = browse.index("guard errorCode == kDNSServiceErr_NoError")
        for expression in ("guard reference == dnsBrowseReference", "let allowed = DNSServiceFlags",
                           "dnsEquals(name, names[$0]", "let scope = dnsScope(interfaceIndex)"):
            self.assertLess(error_first, browse.index(expression))
        self.assertLess(browse.index("dnsEquals(name, names[$0]"), browse.index("dnsEquals(type,"))
        for expression in ("previous.interface != interfaceIndex", "previous.type != actualType",
                           "previous.domain != actualDomain", "kDNSServiceFlagsMoreComing",
                           "!peers[index].observation.dnsResolve.invalidated",
                           "startDNSResolve(index, interface: candidate.interface, type: candidate.type",
                           "domain: candidate.domain"):
            self.assertIn(expression, browse)
        resolve = source.split("    private func startDNSResolve(", 1)[1].split(
            "    private func dnsResolveResult(", 1)[0]
        self.assertLess(resolve.index("!peers[index].observation.dnsResolve.attempted"),
                        resolve.index("DNSServiceResolve(&reference, 0, interface, name, t, d"))
        self.assertIn("DNSServiceSetDispatchQueue(reference, queue)", resolve)
        self.assertEqual(1, source.count("DNSServiceResolve(&reference"))
        callback = source.split("    private func dnsResolveResult(", 1)[1].split(
            "    private func invalidateDNSResolve(", 1)[0]
        for expression in ("guard context.active", "peers[index].dnsContext === context", "acceptingObservation()",
                           "defer { retireDNSResolve(index) }", "interfaceIndex == context.interfaceIndex",
                           "UInt16(bigEndian: port)", "received == $0"):
            self.assertIn(expression, callback)
        error_first = callback.index("guard errorCode == kDNSServiceErr_NoError")
        for expression in ("guard reference == peers[index].dnsReference", "dnsScope(interfaceIndex)",
                           "dnsEquals(fullName, context.fullName)", "UInt16(bigEndian: port)",
                           "Data(bytes: txt!, count: Int(txtLength))"):
            self.assertLess(error_first, callback.index(expression))
        self.assertLess(callback.index("observed.identityMatched && observed.scopeValid"),
                        callback.index("Data(bytes: txt!, count: Int(txtLength))"))
        invalidation = source.split("    private func invalidateDNSResolve(", 1)[1].split(
            "    private func retireDNSBrowse()", 1)[0]
        for expression in ("dnsResolve.invalidated = true", "dnsResolve.matchesExpected = false",
                           "dnsResolve.portMatches = false", "dnsContext?.active = false",
                           "DNSServiceRefDeallocate(reference)", "dnsResolve.retired = true"):
            self.assertIn(expression, invalidation)
        registration = source.split("    private func registration(", 1)[1].split(
            "    private func clearCurrent(", 1)[0]
        renamed = registration.split("registrationNameChanged = true", 1)[1].split("case .remove:", 1)[0]
        self.assertIn("invalidateDNSResolve(index)", renamed)
        listener = source.split("    private func listenerState(", 1)[1].split(
            "    private func browserState(", 1)[0]
        initial = listener.split("case .setup:", 1)[1].split("case .waiting(", 1)[0]
        self.assertIn("if peers[index].observation.ownRegistrationObserved { invalidateDNSResolve(index) }", initial)
        self.assertIn("dnsBrowse.created == dnsBrowse.retired", source)
        self.assertIn("dnsResolve.created == $0.observation.dnsResolve.retired", source)
        self.assertLess(source.index("queue.async { [weak self] in self?.finish() }"),
                        source.index("peer.dnsContext = nil"))

    def test_include_txt_browse_uses_actual_metadata_without_query_fallback(self):
        probe = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        self.assertIn('withTXT = "WITH_TXT"', probe)
        self.assertIn("NWBrowser.Descriptor.bonjourWithTXTRecord(type: Self.serviceType, domain: nil)", probe)
        self.assertIn("#available(iOS 16.0, *)", probe)
        self.assertIn(".metadata", probe)
        self.assertIn(".bonjour(let record)", probe)
        self.assertIn("record.data", probe)
        for obsolete in ("DNSServiceQueryRecord", "QuerySlot", "anyTxtQuery",
                         "localSrvQuery", "localTxtQuery", "selectedInterfaceKind", "candidateInterfaceCount"):
            self.assertNotIn(obsolete, probe)
        self.assertNotIn(".bonjour(type:", probe)

    def test_cli_and_app_use_the_same_strict_received_txt_schema(self):
        for mode in ("cli", "app"):
            value = fixture(discovered=True, mode=mode)
            self.assertEqual("discovered", D.validate_probe(value, POLICY, mode)["outcome"])
            self.assertEqual(TXT_FIELDS, set(value["peers"][0]["txtMetadata"]))
            for old in ("txtQuery", "anyTxtQuery", "localTxtQuery", "localSrvQuery",
                        "selectedInterfaceKind", "candidateInterfaceCount"):
                bad = copy.deepcopy(value)
                bad["peers"][0][old] = {}
                with self.subTest(mode=mode, obsolete=old), self.assertRaises(ValueError):
                    D.validate_probe(bad, POLICY, mode)
            bad = copy.deepcopy(value)
            bad["mode"] = "app" if mode == "cli" else "cli"
            with self.subTest(mode=mode, wrong_host=True), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY, mode)

    def test_every_current_owned_result_must_match_for_discovery(self):
        value = fixture(discovered=True)
        for peer in value["peers"]:
            peer["maximumResultCount"] = 2
            peer["interfaces"].update(count=2)
            peer["txtMetadata"].update(observations=2, matchingObservations=2, ownedResults=2)
        self.assertEqual("discovered", D.validate_probe(value, POLICY)["outcome"])
        # A current invalid sibling clears the aggregate match despite a historical valid entry.
        value["outcome"] = "notDiscovered"
        value["peers"][0]["txtMetadata"].update(matchesExpected=False, rawMatchesExpected=False)
        self.assertEqual("notDiscovered", D.validate_probe(value, POLICY)["outcome"])
        value["outcome"] = "discovered"
        with self.assertRaises(ValueError):
            D.validate_probe(value, POLICY)
        for key, val in (("kind", "mixed"), ("ownedResults", 0), ("received", False),
                         ("present", False), ("identityMatched", False), ("malformed", True)):
            bad = fixture(discovered=True)
            bad["peers"][0]["txtMetadata"][key] = val
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)

    def test_mixed_or_missing_metadata_is_a_valid_nonpositive_current_snapshot(self):
        for kind, received, present, maximum in (("none", False, False, 0),
                                                ("other", False, False, 0),
                                                ("mixed", True, True, 130)):
            value = fixture(discovered=True)
            value["outcome"] = "notDiscovered"
            peer = value["peers"][0]
            peer["maximumResultCount"] = 2
            peer["interfaces"].update(count=2)
            peer["txtMetadata"].update(observations=2, ownedResults=2, kind=kind, received=received,
                present=present, maximumBytes=maximum, identityMatched=False,
                matchesExpected=False, rawMatchesExpected=False)
            self.assertEqual("notDiscovered", D.validate_probe(value, POLICY)["outcome"])
            value["outcome"] = "discovered"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)

    def test_metadata_can_recover_without_erasing_invalid_history(self):
        value = fixture(discovered=True)
        value["outcome"] = "notDiscovered"
        metadata = value["peers"][0]["txtMetadata"]
        metadata.update(observations=2, malformedObservations=1, malformed=True, identityMatched=False,
                        matchesExpected=False, rawMatchesExpected=False)
        self.assertEqual("notDiscovered", D.validate_probe(value, POLICY)["outcome"])
        metadata.update(observations=3, matchingObservations=2, malformed=False, identityMatched=True,
                        matchesExpected=True, rawMatchesExpected=True)
        value["outcome"] = "discovered"
        self.assertEqual("discovered", D.validate_probe(value, POLICY)["outcome"])
        self.assertEqual(1, metadata["malformedObservations"])

    def test_removed_snapshot_cannot_reuse_historical_txt_match(self):
        value = fixture(discovered=True)
        value["outcome"] = "notDiscovered"
        peer = value["peers"][0]
        peer["expectedPeerObserved"] = False
        peer["interfaces"] = {"observed": False, "count": 0, "kinds": []}
        peer["txtMetadata"] = copy.deepcopy(fixture()["peers"][0]["txtMetadata"])
        peer["txtMetadata"].update(observations=3, matchingObservations=1, malformedObservations=1)
        self.assertEqual("notDiscovered", D.validate_probe(value, POLICY)["outcome"])
        for field, val in (("received", True), ("present", True), ("identityMatched", True),
                           ("matchesExpected", True), ("rawMatchesExpected", True), ("maximumBytes", 130)):
            bad = copy.deepcopy(value)
            bad["peers"][0]["txtMetadata"][field] = val
            with self.subTest(field=field), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)
        value["outcome"] = "discovered"
        with self.assertRaises(ValueError):
            D.validate_probe(value, POLICY)

    def test_current_metadata_requires_live_browser_and_both_listeners(self):
        for mode in ("cli", "app"):
            for index, field in ((0, "browserLastState"), (0, "listenerLastState"), (1, "listenerLastState")):
                for state in ("setup", "waiting", "failed", "cancelled", "unknown", "none"):
                    value = fixture(discovered=True, mode=mode)
                    value["outcome"] = "notDiscovered"
                    value["peers"][index][field] = state
                    with self.subTest(mode=mode, field=field, state=state), self.assertRaises(ValueError):
                        D.validate_probe(value, POLICY, mode)
            # Error history alone is not a current-state failure or a reason to invent withdrawal.
            value = fixture(discovered=True, mode=mode)
            value["peers"][0].update(browserWaiting=1, browserError={"domain": "dns", "code": -65537})
            self.assertEqual("discovered", D.validate_probe(value, POLICY, mode)["outcome"])
            # A failed current state can report a truthful cleared negative, retaining prior counters.
            value["outcome"] = "notDiscovered"
            for peer in value["peers"]:
                peer["listenerLastState"] = "failed"
                peer["interfaces"] = {"observed": False, "count": 0, "kinds": []}
                peer["txtMetadata"] = copy.deepcopy(fixture()["peers"][0]["txtMetadata"])
                peer["txtMetadata"].update(observations=3, matchingObservations=1, malformedObservations=1)
            self.assertEqual("notDiscovered", D.validate_probe(value, POLICY, mode)["outcome"])

    def test_actual_interface_snapshot_is_bounded_and_contains_only_categories(self):
        empty_interfaces = fixture(discovered=True)
        empty_interfaces["peers"][0]["interfaces"].update(count=0, kinds=[])
        D.validate_probe(empty_interfaces, POLICY)  # Observed result need not expose an interface entry.
        for kind in sorted(INTERFACE_KINDS):
            value = fixture(discovered=True)
            value["peers"][0]["interfaces"]["kinds"] = [kind]
            D.validate_probe(value, POLICY)
        for key, val in (("observed", 1), ("observed", False), ("count", True), ("count", 0),
                         ("count", 129), ("kinds", []), ("kinds", ["wifi", "wifi"]),
                         ("kinds", ["wifi", "loopback"]), ("kinds", ["en0"]),
                         ("kinds", "wifi"), ("interfaceIndex", 1), ("address", "private")):
            bad = fixture(discovered=True)
            bad["peers"][0]["interfaces"][key] = val
            with self.subTest(key=key, value=val), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)
        for field in ("interfaces", "txtMetadata"):
            bad = fixture()
            del bad["peers"][0][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)

    def test_metadata_records_fit_unchanged_serialization_caps(self):
        for mode in ("cli", "app"):
            probe = fixture(discovered=True, mode=mode)
            for peer in probe["peers"]:
                peer["maximumResultCount"] = 128
                peer["interfaces"].update(count=128, kinds=sorted(INTERFACE_KINDS))
                peer["txtMetadata"].update(observations=65535, matchingObservations=65535,
                                           malformedObservations=65535, ownedResults=128, maximumBytes=65535)
            D.validate_probe(probe, POLICY, mode)
            self.assertLessEqual(len(D.encoded(probe)), 6144)
            raw = streams(probe)["stdout"] if mode == "cli" else app_streams(probe)["stdout"]
            self.assertLessEqual(len(raw), 8192)
        maximum = maximum_cli_layout()
        self.assertLessEqual(len(D.encoded(maximum)), 6144)
        self.assertLessEqual(len(streams(maximum)["stdout"]), 8192)

    def test_txt_requires_received_owned_current_metadata_not_only_configuration(self):
        for key, val in (("received", False), ("matchingObservations", 0), ("maximumBytes", 0),
                         ("identityMatched", False), ("present", False), ("malformed", True),
                         ("ownedResults", 0), ("kind", "none"), ("matchesExpected", False)):
            bad = fixture(discovered=True)
            bad["peers"][0]["txtMetadata"][key] = val
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)
        only_browse = fixture()
        for peer in only_browse["peers"]:
            peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=1, firstResultMilliseconds=0)
            peer["interfaces"] = {"observed": True, "count": 1, "kinds": ["loopback"]}
            peer["txtMetadata"].update(observations=1, ownedResults=1)
        self.assertEqual("notDiscovered", D.validate_probe(only_browse, POLICY)["outcome"])
        only_browse["outcome"] = "discovered"
        with self.assertRaises(ValueError):
            D.validate_probe(only_browse, POLICY)

    def test_txt_mismatch_or_malformed_snapshot_cannot_use_historical_success(self):
        for malformed in (False, True):
            value = fixture(discovered=True)
            value["outcome"] = "notDiscovered"
            value["peers"][1]["txtMetadata"].update(observations=2, matchesExpected=False,
                rawMatchesExpected=False, malformed=malformed, identityMatched=not malformed,
                malformedObservations=int(malformed))
            self.assertEqual("notDiscovered", D.validate_probe(value, POLICY)["outcome"])
            value["outcome"] = "discovered"
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                D.validate_probe(value, POLICY)

        empty = fixture(discovered=True)
        empty["outcome"] = "notDiscovered"
        empty["peers"][0]["txtMetadata"].update(received=True, present=False, maximumBytes=0,
            identityMatched=False, matchesExpected=False, rawMatchesExpected=False,
            malformed=True, malformedObservations=1)
        self.assertEqual("notDiscovered", D.validate_probe(empty, POLICY)["outcome"])

    def test_metadata_closed_types_bounds_and_private_fields(self):
        for key in TXT_HISTORY | {"ownedResults", "maximumBytes"}:
            maximum = 128 if key == "ownedResults" else 65535
            for val in (True, -1, maximum + 1, 1.0, "1"):
                bad = fixture(discovered=True)
                bad["peers"][0]["txtMetadata"][key] = val
                with self.subTest(key=key, value=val), self.assertRaises(ValueError):
                    D.validate_probe(bad, POLICY)
        for key, val in [(key, 1) for key in TXT_FLAGS] + [
                ("kind", "private-kind"), ("rawTxt", "private"), ("hostname", "private"),
                ("data", [1, 2]), ("endpoint", "private"), ("interfaceIndex", 1)]:
            bad = fixture(discovered=True)
            bad["peers"][0]["txtMetadata"][key] = val
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)
        for field in TXT_FIELDS:
            bad = fixture()
            del bad["peers"][0]["txtMetadata"][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)

    def test_owned_txt_uses_closed_actual_parameter_readbacks(self):
        self.assertEqual(("WITH_TXT",), D.POLICIES)
        self.assertEqual(CONFIG_BOOLS, D.CONFIG_BOOLS)
        self.assertEqual({"listenerTransport", "browserTransport"}, D.CONFIG_TRANSPORTS)
        self.assertEqual({"unobserved", "none", "tcp", "other"}, D.TRANSPORTS)
        self.assertEqual(b"P2PKIT_LAN_DNS_SD_RESOLVE_V1 ", D.MARKER)
        for policy, includes_txt in (("WITH_TXT", True),):
            with self.subTest(policy=policy):
                result = D.probe_result(streams(policy=policy), policy, TOKENS["CLI"])
                self.assertEqual("notDiscovered", result["probe"]["outcome"])
                self.assertEqual("none", result["probe"]["peers"][0]["configuration"]["browserTransport"])
                self.assertIs(includes_txt, result["probe"]["peers"][0]["configuration"]["browserIncludesTXT"])
                self.assertNotIn(TOKENS["CLI"], json.dumps(result))
                self.assertEqual(64, len(result["originals"]["stdoutSha256"]))

    def test_policy_labels_cannot_replace_observed_configuration(self):
        for policy in ("WITH_TXT",):
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
        for policy in ("WITH_TXT",):
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
        for policy in ("WITH_TXT",):
            good = fixture(policy, discovered=True)
            self.assertEqual("discovered", D.validate_probe(good, policy)["outcome"])
            good["peers"][1]["expectedPeerObserved"] = False
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                D.validate_probe(good, policy)
        for field, value in (("ownRegistrationObserved", False), ("registrationNameChanged", True),
                             ("browserReady", 0), ("browserLastState", "failed"),
                             ("listenerLastState", "waiting")):
            bad = fixture(discovered=True)
            bad["peers"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                D.validate_probe(bad, POLICY)
        for outcome in ("cleanupUnconfirmed", "counterOverflow", "timingInvalid"):
            bad = fixture()
            bad["outcome"] = outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                D.validate_probe(bad, "WITH_TXT")
        for key, value in (("complete", False), ("listenersCancelled", 1), ("browsersCreated", 1)):
            bad = fixture()
            bad["cleanup"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "WITH_TXT")

    def test_retired_setup_failure_does_not_invent_parameter_observations(self):
        for policy in ("WITH_TXT",):
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
        for policy in ("WITH_TXT",):
            with self.subTest(policy=policy, reason="stale"), self.assertRaises(ValueError):
                D.probe_result(streams(policy=policy, token="e" * 32), policy, TOKENS["CLI"])
            wrong = "OWNED_TXT"
            with self.subTest(policy=policy, reason="envelope-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(policy=wrong, token=TOKENS["CLI"]), policy, TOKENS["CLI"])
            with self.subTest(policy=policy, reason="probe-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(fixture(wrong), policy), policy, TOKENS["CLI"])
        for stdout in (b"", streams()["stdout"] * 2, D.MARKER + b"x" * 8193,
                       b"P2PKIT_LAN_APP_V1 {}\n",
                       streams()["stdout"].replace(D.MARKER, b"P2PKIT_LAN_BROWSER_PARAMETERS_V1 ", 1)):
            with self.subTest(length=len(stdout)), self.assertRaises(ValueError):
                D.probe_result({"stdout": stdout, "stderr": b""}, "WITH_TXT", TOKENS["CLI"])
        for old_policy in ("TCP", "BARE", "BONJOUR", "OWNED_TXT"):
            with self.subTest(old=old_policy, reason="policy-argument"), self.assertRaises(ValueError):
                D.probe_result(streams(), old_policy, TOKENS["CLI"])
            with self.subTest(old=old_policy, reason="envelope-policy"), self.assertRaises(ValueError):
                D.probe_result(streams(browserDescriptor=old_policy), "WITH_TXT", TOKENS["CLI"])
            bad = fixture()
            bad["browserDescriptor"] = old_policy
            with self.subTest(old=old_policy, reason="probe-policy"), self.assertRaises(ValueError):
                D.validate_probe(bad, "WITH_TXT")
        old = {"schema": 1, "token": TOKENS["CLI"], "browserParameters": "BARE", "probe": fixture()}
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": D.MARKER + json.dumps(old).encode() + b"\n", "stderr": b""},
                           "WITH_TXT", TOKENS["CLI"])
        bad = fixture()
        bad["browserParameters"] = bad.pop("browserDescriptor")
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "WITH_TXT")

    def test_private_fields_duplicate_json_and_boolean_counts_rejected(self):
        bad = streams()["stdout"].replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": bad, "stderr": b""}, "WITH_TXT", TOKENS["CLI"])
        with self.assertRaises(ValueError):
            D.probe_result(streams(address="private.invalid"), "WITH_TXT", TOKENS["CLI"])
        for owner, key, value in (("peer", "endpoint", "not-for-projection"),
                                  ("configuration", "receivedTxt", "not-for-projection"),
                                  ("peer", "listenerReady", True)):
            bad = fixture()
            target = bad["peers"][0] if owner == "peer" else bad["peers"][0]["configuration"]
            target[key] = value
            with self.subTest(owner=owner, key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "WITH_TXT")
        for key, value in (("mode", "app"), ("schema", True), ("windowMilliseconds", 60000),
                           ("observationElapsedMilliseconds", 29999), ("cleanupElapsedMilliseconds", 5001),
                           ("counterOverflow", True)):
            bad = fixture()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "WITH_TXT")

    def test_summary_is_bounded_token_free_and_nonqualifying(self):
        for arm, mode in (("CLI", "cli"), ("APP", "app")):
            probe = fixture(discovered=True, mode=mode)
            for peer in probe["peers"]:
                peer["maximumResultCount"] = 128
                peer["interfaces"].update(count=128, kinds=sorted(INTERFACE_KINDS))
                peer["txtMetadata"].update(observations=65535, matchingObservations=65535,
                    malformedObservations=65535, ownedResults=128, maximumBytes=65535)
            observed = D.probe_result(streams(probe) if mode == "cli" else app_streams(probe),
                                      POLICY, TOKENS[arm], mode)
            output = io.StringIO()
            with redirect_stdout(output):
                D.emit(arm, observed, SOURCE, CONTEXT)
            text = output.getvalue()
            prefix = "P2PKIT_LAN_DNS_SD_BROWSE_RESOLVE_SUMMARY_V1 "
            self.assertTrue(text.startswith(prefix))
            self.assertLessEqual(len(text.encode()), 8192 + len(prefix) + 1)
            self.assertEqual(1, len(text.splitlines()))
            for token in TOKENS.values():
                self.assertNotIn(token, text)
            summary = json.loads(text[len(prefix):])
            self.assertIs(summary["qualification"], False)
            self.assertEqual("INTEL_LAN_DNS_SD_BROWSE_RESOLVE_DIAGNOSTIC_V1", summary["scope"])
            self.assertEqual(arm, summary["arm"])
        output = io.StringIO()
        with redirect_stdout(output):
            D.emit("CLI", {"probe": maximum_cli_layout(),
                           "originals": {"stdoutSha256": "f" * 64, "stderrSha256": "e" * 64}}, SOURCE, CONTEXT)
        raw = output.getvalue().split(" ", 1)[1].encode()
        self.assertLessEqual(len(raw), 8192 + 1)
        self.assertNotIn(TOKENS["CLI"], output.getvalue())

    def test_single_cli_spawn_and_retired_negative_permits_only_the_app_stage(self):
        results = {}
        evidence, binary = Path("/unused-evidence"), Path("/unused-binary")
        events = []
        def captured(directory, label, argv):
            events.append(label)
            return streams()
        def emitted(arm, value, source, context):
            events.append("emit-" + arm)
        with mock.patch.object(D, "command", side_effect=captured) as command, \
                mock.patch.object(D, "emit", side_effect=emitted):
            D.run_arms(evidence, binary, UDID, dict(ACTIVE_TOKENS), SOURCE, CONTEXT, results)
        self.assertEqual(["cli-probe", "emit-CLI"], events)
        command.assert_called_once_with(evidence, "cli-probe", ["/usr/bin/xcrun", "simctl", "spawn", UDID,
                      str(binary), "--token", TOKENS["CLI"], "--browser-descriptor", "WITH_TXT"])
        self.assertEqual(["CLI"], list(results))
        self.assertEqual(("CLI",), D.ARMS)
        self.assertEqual("notDiscovered", results["CLI"]["probe"]["outcome"])

    def test_reused_invalid_or_incomplete_arm_tokens_refused_before_spawn(self):
        cases = [({}, {}), ({"CLI": "a" * 31}, {}), ({"CLI": "A" * 32}, {}),
                 ({"CLI": "a" * 32, "APP": "a" * 32}, {}), (dict(TOKENS), {}),
                 ({**ACTIVE_TOKENS, "WITH_TXT": "f" * 32}, {}),
                 (dict(ACTIVE_TOKENS), {"CLI": {}}), ({"OWNED_TXT": "a" * 32}, {})]
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
                    D.run_arms(Path("/unused"), Path("/unused-binary"), UDID, dict(ACTIVE_TOKENS), SOURCE, CONTEXT, results)
                self.assertEqual(1, command.call_count)
                self.assertEqual({}, results)
                emit.assert_not_called()

    def test_retired_setup_failure_is_reportable_but_not_an_executable_comparison_arm(self):
        for mode in ("cli", "app"):
            value = fixture(mode=mode)
            value["outcome"] = "setupFailed"
            observed = D.probe_result(streams(value) if mode == "cli" else app_streams(value),
                                      POLICY, TOKENS[mode.upper()], mode)
            self.assertEqual("setupFailed", observed["probe"]["outcome"])
        value = fixture()
        value["outcome"] = "setupFailed"
        results = {}
        with mock.patch.object(D, "command", return_value=streams(value)) as command, \
                mock.patch.object(D, "emit") as emit:
            with self.assertRaises(ValueError):
                D.run_arms(Path("/unused"), Path("/unused-bin"), UDID, dict(ACTIVE_TOKENS), SOURCE, CONTEXT, results)
            command.assert_called_once()
            emit.assert_not_called()
            self.assertEqual({}, results)

    def test_app_requires_real_packaging_closed_permission_and_not_running(self):
        for permission in ("notObserved", "handled"):
            value = D.probe_result(app_streams(permission=permission), POLICY, TOKENS["APP"], mode="app")
            self.assertEqual(permission, value["permission"])
            self.assertIs(value["appNotRunning"], True)
            self.assertEqual("app", value["probe"]["mode"])
        for field in D.PACKAGE_KEYS:
            bad = fixture(mode="app")
            bad["packaging"][field] = False
            with self.subTest(package=field), self.assertRaises(ValueError):
                D.probe_result(app_streams(bad), POLICY, TOKENS["APP"], mode="app")
        for args in ({"permission": "unhandled"}, {"permission": "granted"},
                     {"appNotRunning": False}, {"appNotRunning": 1}, {"token": TOKENS["CLI"]},
                     {"hierarchy": "private"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                D.probe_result(app_streams(**args), POLICY, TOKENS["APP"], mode="app")
        for raw in (b"", app_streams()["stdout"] * 2, streams()["stdout"],
                    b"P2PKIT_LAN_APP_V1 " + b"x" * 8193):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                D.probe_result({"stdout": raw, "stderr": b""}, POLICY, TOKENS["APP"], mode="app")
        for missing in ("permission", "appNotRunning"):
            value = json.loads(app_streams()["stdout"].split(b" ", 1)[1])
            del value[missing]
            raw = b"P2PKIT_LAN_APP_V1 " + json.dumps(value).encode() + b"\n"
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                D.probe_result({"stdout": raw, "stderr": b""}, POLICY, TOKENS["APP"], mode="app")

    def test_application_identity_binds_actual_plist_and_executable_bytes(self):
        plist = {"CFBundleIdentifier": D.BUNDLE, "CFBundleExecutable": D.APP,
                 "CFBundlePackageType": "APPL", "NSLocalNetworkUsageDescription": "Synthetic local probe",
                 "NSBonjourServices": ["_p2pkit._tcp"]}
        raw = D.plistlib.dumps(plist)
        executable = b"synthetic executable bytes, not a native build"
        app, evidence = Path("/unused/app"), Path("/unused/evidence")
        with mock.patch.object(D, "read_file", side_effect=[raw, executable]) as read, \
                mock.patch.object(D.GATE, "_intel_write") as original, mock.patch.object(D, "write") as write:
            identity = D.application_identity(app, evidence, "built")
        self.assertEqual([mock.call(app / "Info.plist", 65536),
                          mock.call(app / D.APP, 64 * 1024 * 1024)], read.call_args_list)
        self.assertEqual({"bundle": D.BUNDLE, "executable": D.APP, "executableBytes": len(executable),
                          "executableSha256": D.digest(executable), "plistSha256": D.digest(raw)}, identity)
        original.assert_called_once_with(evidence / "built-Info.plist", raw)
        write.assert_called_once_with(evidence / "built-identity.json", identity)
        for key, value in (("CFBundleIdentifier", "wrong.bundle"), ("CFBundleExecutable", "Wrong"),
                           ("CFBundlePackageType", "BNDL"), ("NSLocalNetworkUsageDescription", " "),
                           ("NSLocalNetworkUsageDescription", True), ("NSBonjourServices", []),
                           ("NSBonjourServices", ["_p2pkit._tcp", "_ambient._tcp"])):
            bad = {**plist, key: value}
            with self.subTest(field=key), mock.patch.object(D, "read_file", return_value=D.plistlib.dumps(bad)), \
                    mock.patch.object(D.GATE, "_intel_write") as original, mock.patch.object(D, "write") as write:
                with self.assertRaises(ValueError):
                    D.application_identity(app, evidence, "built")
                original.assert_not_called()
                write.assert_not_called()

    def test_installed_container_is_scoped_to_the_owned_device_and_exact_app(self):
        container = "22222222-2222-3333-4444-555555555555"
        base = Path.home() / "Library/Developer/CoreSimulator/Devices" / UDID / "data/Containers/Bundle/Application"
        actual = base / container / (D.APP + ".app")
        with mock.patch.object(Path, "resolve", autospec=True, side_effect=lambda path, **kwargs: path):
            self.assertEqual(actual, D.installed_path(str(actual).encode(), UDID))
            for raw in (b"relative/path", (str(actual) + "\n/private").encode(),
                        str(actual.with_name("Other.app")).encode(),
                        str(base / "not-a-container" / (D.APP + ".app")).encode(),
                        str(actual).replace(UDID, "99999999-2222-3333-4444-555555555555").encode()):
                with self.subTest(raw_length=len(raw)), self.assertRaises(ValueError):
                    D.installed_path(raw, UDID)
        with mock.patch.object(Path, "resolve", return_value=Path("/different")), self.assertRaises(ValueError):
            D.installed_path(str(actual).encode(), UDID)

    def test_installed_bundle_inventory_uses_actual_closed_plutil_result(self):
        evidence = Path("/unused")
        for raw, expected in ((b"{}", set()), (json.dumps({D.BUNDLE: {}, "unrelated.app": {}}).encode(),
                                               {D.BUNDLE, "unrelated.app"})):
            with mock.patch.object(D, "command", side_effect=[{"stdout": b"synthetic plist", "stderr": b""},
                    {"stdout": raw, "stderr": b""}]) as command:
                self.assertEqual(expected, D.installed_bundles(evidence, "apps-before", UDID))
                self.assertEqual([mock.call(evidence, "apps-before", ["/usr/bin/xcrun", "simctl", "listapps", UDID]),
                    mock.call(evidence, "apps-before-json", ["/usr/bin/plutil", "-convert", "json", "-o", "-",
                              str(evidence / "apps-before/stdout.bin")])], command.call_args_list)
        for raw in (b"[]", b"null", b'{"duplicate":{},"duplicate":{}}'):
            with mock.patch.object(D, "command", side_effect=[{"stdout": b"", "stderr": b""},
                    {"stdout": raw, "stderr": b""}]), self.assertRaises(ValueError):
                D.installed_bundles(evidence, "apps-before", UDID)

    def _run_mock_app_stage(self, failure=None, *, remaining=460, primary=None, drift=False, retire=False):
        """Run controller branches against synthetic identity/command values, never native tools."""
        evidence, work, generated = Path("/unused/evidence"), Path("/unused/work"), Path("/unused/generated")
        events, identities, emitted = [], [], []
        attempts = {"installed": False, "runnerAttempted": False}
        results = {"CLI": D.probe_result(streams(), POLICY, TOKENS["CLI"])}
        identity = {"bundle": D.BUNDLE, "executable": D.APP, "executableBytes": 3,
                    "executableSha256": "c" * 64, "plistSha256": "d" * 64}

        def captured(directory, label, argv):
            self.assertEqual(evidence, directory)
            events.append((label, argv))
            if label == "install-app":
                self.assertTrue(attempts["installed"])
                self.assertFalse(attempts["runnerAttempted"])
            if label != "app-probe":
                self.assertIs(D.MAINTAINED_INTEL_WORK_SECONDS, D.GATE._intel_work_seconds)
                self.assertEqual(environment, dict(D.os.environ))
            if label == "app-probe":
                self.assertEqual(300, D.GATE._intel_work_seconds(label))
                self.assertTrue(attempts["runnerAttempted"])
                self.assertEqual(TOKENS["APP"], D.os.environ["TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN"])
                if drift:
                    D.GATE._intel_work_seconds = lambda _label: 999
                if primary is not None:
                    raise primary
            if label == failure:
                raise ValueError("synthetic command failure")
            if label == "app-probe":
                if failure == "app-result":
                    return {"stdout": b"missing APP envelope", "stderr": b""}
                probe = fixture(mode="app")
                if failure == "app-setup":
                    probe["outcome"] = "setupFailed"
                return app_streams(probe)
            return {"stdout": b"synthetic container", "stderr": b""}

        def identify(path, directory, label):
            self.assertEqual(evidence, directory)
            identities.append(label)
            if failure == label + "-identity":
                return {**identity, "executableSha256": "f" * 64}
            return dict(identity)

        environment = {} if failure != "existing-token" else {"TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN": "keep"}
        runner = "wrong.runner" if failure == "runner-identity" else D.RUNNER_BUNDLE
        error = None
        with mock.patch.dict(D.os.environ, environment, clear=True), \
                mock.patch.object(D, "EXECUTION_END", remaining), \
                mock.patch.object(D.time, "monotonic", return_value=0), \
                mock.patch.object(D, "command", side_effect=captured), \
                mock.patch.object(D, "application_identity", side_effect=identify), \
                mock.patch.object(D, "installed_bundles", return_value={D.BUNDLE} if failure == "existing-app" else set()), \
                mock.patch.object(D, "installed_path", return_value=Path("/unused/installed")), \
                mock.patch.object(D, "read_file", return_value=D.plistlib.dumps({"CFBundleIdentifier": runner})), \
                mock.patch.object(D.GATE, "_intel_write"), \
                mock.patch.object(D, "emit", side_effect=lambda arm, *args: emitted.append(arm)):
            try:
                D.run_app(evidence, work, generated, UDID, TOKENS["APP"], SOURCE, CONTEXT, results, attempts)
            except (ValueError, KeyboardInterrupt) as exc:
                if primary is not None:
                    self.assertIs(primary, exc)
                error = exc if primary is not None else str(exc)
            self.assertEqual(environment, dict(D.os.environ))  # Never retain/replace the owned runner token.
            self.assertIs(D.MAINTAINED_INTEL_WORK_SECONDS, D.GATE._intel_work_seconds)
            if retire:
                with mock.patch.object(D, "installed_bundles", side_effect=[{D.BUNDLE, D.RUNNER_BUNDLE}, set()]):
                    D.retire_apps(evidence, UDID, attempts)
        return events, identities, emitted, attempts, results, error

    def test_app_stage_is_once_same_device_and_preserves_pre_post_identity(self):
        events, identities, emitted, attempts, results, error = self._run_mock_app_stage()
        self.assertIsNone(error)
        self.assertEqual(["install-xcodegen", "generate-app", "build-app", "app-architecture", "install-app",
                          "installed-app", "app-probe", "installed-app-after"], [label for label, _ in events])
        self.assertEqual(["built", "installed", "installed-after"], identities)
        self.assertEqual(["APP"], emitted)
        self.assertEqual({"CLI", "APP"}, set(results))
        self.assertEqual({"installed": True, "runnerAttempted": True}, attempts)
        for label, argv in events:
            if label in {"install-app", "installed-app", "installed-app-after"}:
                self.assertIn(UDID, argv)
            if label in {"build-app", "app-probe"}:
                self.assertIn("id=" + UDID, argv)
                self.assertEqual("2", argv[argv.index("-jobs") + 1])
                self.assertEqual("NO", argv[argv.index("-parallel-testing-enabled") + 1])
                self.assertEqual("1", argv[argv.index("-maximum-concurrent-test-simulator-destinations") + 1])
            if label == "app-probe":
                selected_test = "-only-testing:P2pKitLanHostProbeUITests/LanHostProbeUITests/testApplicationHostProbe"
                build_argv = next(args for phase, args in events if phase == "build-app")
                self.assertEqual(build_argv[:-1] + [selected_test, "test-without-building"], argv)
                self.assertEqual([selected_test], [arg for arg in argv if arg.startswith("-only-testing")])
                self.assertFalse({arg.split("=", 1)[0] for arg in argv} & {
                    "-test-iterations", "-retry-tests-on-failure", "-run-tests-until-failure",
                    "-test-repetition-relaunch-enabled"})
        self.assertTrue(results["APP"]["appNotRunning"])
        self.assertEqual("notObserved", results["APP"]["permission"])

    def test_partial_app_failures_reserve_cleanup_and_never_emit_partial_success(self):
        cases = (("build-app", False, False), ("runner-identity", False, False),
                 ("existing-app", False, False), ("install-app", True, False),
                 ("installed-identity", True, False), ("existing-token", True, False),
                 ("app-probe", True, True), ("app-setup", True, True), ("installed-after-identity", True, True))
        for failure, installed, runner in cases:
            with self.subTest(failure=failure):
                events, identities, emitted, attempts, results, error = self._run_mock_app_stage(failure)
                self.assertIsNotNone(error)
                self.assertEqual({"installed": installed, "runnerAttempted": runner}, attempts)
                self.assertEqual({"CLI"}, set(results))
                self.assertEqual([], emitted)
                labels = [label for label, _ in events]
                self.assertEqual(len(labels), len(set(labels)))  # No build/install/test retry.
                if not runner:
                    self.assertNotIn("app-probe", labels)
                if failure in {"app-probe", "app-setup"}:
                    self.assertNotIn("installed-after", identities)

    def test_app_stage_rejects_missing_cli_invalid_token_or_reused_attempt_before_commands(self):
        for results, token, attempts in (({}, TOKENS["APP"], {"installed": False, "runnerAttempted": False}),
                ({"CLI": {}}, "bad", {"installed": False, "runnerAttempted": False}),
                ({"CLI": {}, "APP": {}}, TOKENS["APP"], {"installed": False, "runnerAttempted": False}),
                ({"CLI": {}}, TOKENS["APP"], {"installed": True, "runnerAttempted": False}),
                ({"CLI": {}}, TOKENS["APP"], {"installed": False, "runnerAttempted": True})):
            with self.subTest(results=set(results), attempts=attempts), mock.patch.object(D, "command") as command:
                with self.assertRaises(ValueError):
                    D.run_app(Path("/unused"), Path("/unused"), Path("/unused"), UDID, token,
                              SOURCE, CONTEXT, results, attempts)
                command.assert_not_called()

    def test_app_retirement_is_reserved_scoped_and_requires_observed_absence(self):
        evidence = Path("/unused")
        with mock.patch.object(D, "installed_bundles") as inventory, mock.patch.object(D, "command") as command:
            D.retire_apps(evidence, UDID, {"installed": False, "runnerAttempted": False})
            inventory.assert_not_called()
            command.assert_not_called()
        for runner in (False, True):
            targets = (D.BUNDLE, D.RUNNER_BUNDLE) if runner else (D.BUNDLE,)
            with self.subTest(runner=runner), \
                    mock.patch.object(D, "installed_bundles", side_effect=[set(targets) | {"unrelated.app"}, {"unrelated.app"}]) as inventory, \
                    mock.patch.object(D, "command") as command:
                D.retire_apps(evidence, UDID, {"installed": True, "runnerAttempted": runner})
                self.assertEqual([mock.call(evidence, "uninstall-" + str(i),
                    ["/usr/bin/xcrun", "simctl", "uninstall", UDID, bundle]) for i, bundle in enumerate(targets)],
                    command.call_args_list)
                self.assertEqual([mock.call(evidence, "apps-retire-before", UDID),
                                  mock.call(evidence, "apps-retire-after", UDID)], inventory.call_args_list)
            with mock.patch.object(D, "installed_bundles", side_effect=[set(targets), set(targets)]), \
                    mock.patch.object(D, "command"), self.assertRaisesRegex(ValueError, "INSTALL_RETIREMENT_NOT_OBSERVED"):
                D.retire_apps(evidence, UDID, {"installed": True, "runnerAttempted": runner})
        with mock.patch.object(D, "installed_bundles", return_value={D.BUNDLE, D.RUNNER_BUNDLE}) as inventory, \
                mock.patch.object(D, "command", side_effect=ValueError("capture failed")) as command:
            with self.assertRaises(ValueError):
                D.retire_apps(evidence, UDID, {"installed": True, "runnerAttempted": True})
            self.assertEqual(1, command.call_count)
            self.assertEqual(1, inventory.call_count)  # No invented post-failure absence.

    def test_app_ui_is_one_acknowledged_scoped_permission_action_and_bounded_projection(self):
        base = ROOT / "scripts/diagnostics/intel-lan-host"
        app, ui = (base / "App.swift").read_text(), (base / "UITests.swift").read_text()
        for expression in ("guard !startAttempted else", "startAttempted = true", "begin.isEnabled = false",
                           "LanProbe(policy: .withTXT, token: token, mode: .app)", "json.utf8.count <= 6144"):
            self.assertIn(expression, app)
        self.assertLess(app.index("startAttempted = true"), app.index("let owned = LanProbe("))
        self.assertEqual(1, ui.count("begin.tap()"))
        self.assertEqual(1, ui.count("app.launch()"))
        for expression in ("isLocalNetworkAlert(alert), !actionAttempted", "actionAttempted = true",
                           'permission = "unhandled"', 'if permission != "unhandled"',
                           "alert.staticTexts[self.usageDescription].exists", "self.displayName",
                           "allow.count == 1 && okay.count == 0", "okay.count == 1 && allow.count == 0",
                           "removeUIInterruptionMonitor(monitor)", "app.terminate()",
                           "app.wait(for: .notRunning, timeout: 5)", "P2PKIT_LAN_APP_V1 ",
                           "data.count <= 6144", "$0.count <= 8192", "CFBooleanGetTypeID()",
                           "Set(value.keys) == keys", '"WITH_TXT"', '"txtMetadata"', '"interfaces"'):
            self.assertIn(expression, ui)
        self.assertLess(ui.index("actionAttempted = true"), ui.index("? allow.element : okay.element).tap()"))
        for forbidden in ("debugDescription", "screenshot(", "TCC.db", "simctl privacy", "DNSServiceQueryRecord"):
            self.assertNotIn(forbidden, app + ui)

    def test_lipo_and_same_shared_source_contract_for_cli_and_application(self):
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
        for forbidden in ("gradlew", "TCC.db", '"privacy"', "simctl erase"):
            self.assertNotIn(forbidden, source)
        for expression in ('"-warnings-as-errors"', '"-j", "2"', '"x86_64-apple-ios15.0-simulator"',
                           '"ARCHS=x86_64"', '"-jobs", "2"',
                           '"-parallel-testing-enabled", "NO"'):
            self.assertIn(expression, source)
        for option in ("-test-iterations", "-retry-tests-on-failure", "-run-tests-until-failure",
                       "-test-repetition-relaunch-enabled"):
            self.assertNotIn(option, source)
        probe = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        parameters = probe.split("    private func browserParameters()", 1)[1].split("    private func transport(", 1)[0]
        self.assertIn("let parameters = NWParameters()", parameters)
        self.assertNotIn("NWParameters.tcp", parameters)
        for expression in ("parameters.includePeerToPeer = true", "parameters.prohibitedInterfaceTypes = [.cellular]"):
            self.assertIn(expression, parameters)
        # Source seams only, not an SDK/native execution or received-TXT claim.
        for expression in (
                "let descriptor = NWBrowser.Descriptor.bonjourWithTXTRecord(type: Self.serviceType, domain: nil)",
                "case .bonjourWithTXTRecord: observed.browserIncludesTXT = true",
                "guard observed.browserTransport == .none",
                "observed.browserIncludesTXT else", "mode: Mode = .cli",
                "service.noAutoRename = true", "configuredServiceTxtReadbackMatches = raw == expected",
                '"plat=IOS", "caps=LAN", "pv=1"',
                "observationNanoseconds: UInt64 = 30_000_000_000",
                "cancellationNanoseconds: UInt64 = 5_000_000_000"):
            self.assertIn(expression, probe)
        main = (ROOT / "scripts/diagnostics/intel-lan-host/main.swift").read_text()
        self.assertIn('CommandLine.arguments[3] == "--browser-descriptor"', main)
        self.assertNotIn("--browser-parameters", main)
        self.assertIn('P2PKIT_LAN_DNS_SD_RESOLVE_V1 ', main)
        project = (ROOT / "scripts/diagnostics/intel-lan-host/project.yml").read_text()
        for expression in ('iOS: "15.0"', 'IPHONEOS_DEPLOYMENT_TARGET: "15.0"', '- LanProbe.swift',
                           '- App.swift', '- UITests.swift', 'ARCHS: x86_64',
                           'SWIFT_TREAT_WARNINGS_AS_ERRORS: YES', '"_p2pkit._tcp"'):
            self.assertIn(expression, project)
        self.assertNotIn('- main.swift', project)

    def test_semantic_txt_match_does_not_require_original_byte_order(self):
        value = fixture(discovered=True)
        for peer in value["peers"]:
            peer["txtMetadata"]["rawMatchesExpected"] = False
        self.assertEqual("discovered", D.validate_probe(value, POLICY)["outcome"])
        value["outcome"] = "notDiscovered"
        value["peers"][0]["txtMetadata"].update(matchesExpected=False, rawMatchesExpected=True)
        with self.assertRaises(ValueError):
            D.validate_probe(value, POLICY)

    def test_txt_callback_current_owner_decoder_and_retirement_source_seams(self):
        probe = (ROOT / "scripts/diagnostics/intel-lan-host/LanProbe.swift").read_text()
        decode = probe.split("    private func decodeOwnedTXT(", 1)[1].split("    private func configure", 1)[0]
        self.assertLess(decode.index("data.count <= 2048"), decode.index("Array(data)"))
        for expression in ('["pid", "app", "name", "plat", "caps", "pv"]',
                           "length > 0, cursor + length <= bytes.count", "equal + 1 < entry.count",
                           "allowed.contains(key), values[key] == nil", "encoding: .utf8",
                           "Set(values.keys) == allowed"):
            self.assertIn(expression, decode)
        callback = probe.split("    private func results(_ results:", 1)[1].split(
            "    private func cancellationCallbackInTime", 1)[0]
        self.assertLess(callback.index("peers[index].browser === browser, acceptingObservation()"),
                        callback.index("clearCurrent(index: index)"))
        self.assertLess(callback.index("clearCurrent(index: index)"), callback.index("for result in results"))
        self.assertLess(callback.index("name == names[1 - index]"), callback.index("result.interfaces"))
        self.assertLess(callback.index('domain == "local." || domain == "local"'), callback.index("result.metadata"))
        self.assertLess(callback.index("received.count <= 65_535"), callback.index("decodeOwnedTXT(received)"))
        for expression in ("results.count <= 128", "interfaces.count + result.interfaces.count <= 128",
                           "peers[index].observation.browserLastState == .ready",
                           "peers[index].observation.listenerLastState == .ready",
                           "peers[1 - index].observation.listenerLastState == .ready",
                           "case .bonjour(let record)", "let received = record.data",
                           'values["pid"] == expectedValues["pid"]', "let matches = values == expectedValues",
                           "allSemantic = allSemantic && matches", "allRaw = allRaw && received == expected",
                           "metadata.rawMatchesExpected = metadata.matchesExpected && allRaw",
                           "metadataKinds.count > 1 ? .mixed", "metadata.ownedResults > 0 && allIdentity",
                           "allSemantic && !metadata.malformed && !counterOverflow"):
            self.assertIn(expression, callback)
        self.assertLess(callback.index("for result in results"), callback.index("metadata.matchesExpected ="))
        self.assertNotIn("return true", callback)  # No first-positive short-circuit over sibling results.
        clearing = probe.split("    private func clearCurrent(index:", 1)[1].split("    private func bumpMetadata", 1)[0]
        for field in TXT_HISTORY:
            self.assertIn("current." + field + " = previous." + field, clearing)
        self.assertIn("var current = TXTMetadataObservation()", clearing)
        self.assertIn("peers[index].observation.interfaces = InterfaceObservation()", clearing)
        state = probe.split("    private func browserState(", 1)[1].split("    private func serviceName", 1)[0]
        self.assertIn("peers[index].browser === browser", state)
        self.assertGreaterEqual(state.count("clearCurrent(index: index)"), 5)
        registration = probe.split("    private func registration(", 1)[1].split("    private func clearCurrent", 1)[0]
        self.assertIn("case .remove:", registration)
        self.assertIn("clearCurrent(index: 1 - index)", registration)
        cutoff = probe.split("    private func beginCancellation()", 1)[1].split("    private func allCancelled", 1)[0]
        self.assertLess(cutoff.index("cutoffMetadata ="), cutoff.index("clearCurrent(index: index)"))
        self.assertLess(cutoff.index("clearCurrent(index: index)"), cutoff.index("browser?.cancel()"))
        self.assertIn("cutoffInterfaces =", cutoff)
        self.assertIn("peer.cutoffMetadata?.matchesExpected == true", probe)
        self.assertIn("observed.txtMetadata = peer.cutoffMetadata", probe)
        self.assertIn("now <= cancellationDeadline", probe)
        self.assertIn("Int((now - startedAt) / 1_000_000) - observationElapsed", probe)
        self.assertIn("guard #available(iOS 16.0, *) else { setupFailed = true; return }", probe)

    def test_unchanged_capture_bounds_and_finally_owned_source_joins(self):
        diagnostic_budgets = {"compile-cli": 300, "sdk-path": 120, "cli-architecture": 120,
                              "build-app": 300, "cli-probe": 120, "app-probe": 120, "COMPILE-CLI": 120,
                              "build-app-extra": 120, "BUILD-APP": 120, "build-app ": 120,
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
        self.assertTrue({"GATE.IntelSimulatorOwner", "owner.prepare", "sdk_contract", "run_arms"} <= calls)
        self.assertNotIn("run_app", calls)
        final_calls = {ast.unparse(node.func) for node in ast.walk(finally_body) if isinstance(node, ast.Call)}
        self.assertTrue({"owner.retire", "GATE.source_state", "GATE.simulator_original", "read_file"} <= final_calls)
        self.assertNotIn("retire_apps", final_calls)
        strings = {node.value for node in ast.walk(finally_body) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertTrue({"RETIREMENT_REJECTED", "ORIGINAL_CHANGED", "BINDING_CHANGED",
                         "SOURCE_OR_CONTEXT_CHANGED", "GENERATED_INPUT_CHANGED"} <= strings)
        self.assertIn('"gradleLaunched": False', source)


if __name__ == "__main__":
    unittest.main(failfast=True)
