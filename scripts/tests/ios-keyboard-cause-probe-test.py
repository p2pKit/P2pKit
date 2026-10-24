#!/usr/bin/env python3
"""Portable closed-metadata/owned-fixture controls, not iOS causal evidence."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import ios_keyboard_cause_probe as probe

OWNED = "11111111-1111-1111-1111-111111111111"
BORROWED = "22222222-2222-2222-2222-222222222222"


def environment():
    return dict(os.environ, GITHUB_ACTIONS="true", RUNNER_ENVIRONMENT="github-hosted",
        GITHUB_REPOSITORY="p2pKit/P2pKit", GITHUB_WORKFLOW_REF="p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/test",
        GITHUB_SHA="a" * 40, GITHUB_WORKFLOW_SHA="a" * 40,
        P2PKIT_CI_COMMAND_DEADLINE_NS=str(time.monotonic_ns() + 3600 * 10**9),
        P2PKIT_KEYBOARD_CAUSE_ISOLATED_HOST="1")


class Preference:
    def __init__(self, original=None, inherited=None):
        self.value, self.inherited = original, inherited
        self.writes = []
        self.closed = False

    def explicit(self):
        return self.value

    def effective(self):
        return self.inherited if self.value is None else self.value

    def write(self, value):
        self.writes.append(value)
        self.value = value

    def close(self):
        self.closed = True


class PreferenceTests(unittest.TestCase):
    def test_absence_and_boolean_originals_are_restored_for_both_conditions(self):
        for original in (None, False, True):
            for inherited in (None, False, True):
                for requested in (False, True):
                    with self.subTest(original=original, inherited=inherited, requested=requested):
                        backend = Preference(original, inherited)
                        transaction = probe.PreferenceTransaction(backend, requested)
                        effective = backend.effective()
                        transaction.apply()
                        self.assertIs(backend.effective(), requested)
                        transaction.restore()
                        self.assertIs(backend.explicit(), original)
                        self.assertIs(backend.effective(), effective)
                        self.assertTrue(transaction.restored)
                        self.assertFalse(transaction.summary()["hardwareConnectionIndependentlyAttested"])

    def test_unsupported_original_values_refuse_before_mutation(self):
        for value in (1, "false", [], {}):
            backend = Preference(value)
            with self.assertRaisesRegex(probe.ProbeError, "UNSUPPORTED_ORIGINAL_PREFERENCE_TYPE"):
                probe.PreferenceTransaction(backend, False)
            self.assertEqual([], backend.writes)

    def test_failed_synchronize_after_write_still_restores_original(self):
        backend = Preference()
        transaction = probe.PreferenceTransaction(backend, False)
        original_write = backend.write
        def failing_write(value):
            original_write(value)
            if value is False:
                raise probe.ProbeError("PREFERENCE_SYNCHRONIZE")
        backend.write = failing_write
        with self.assertRaises(probe.ProbeError):
            transaction.apply()
        transaction.restore()
        self.assertEqual([False, None], backend.writes)
        self.assertTrue(transaction.restored)

    def test_failed_write_before_mutation_does_not_clobber_original(self):
        backend = Preference(True)
        transaction = probe.PreferenceTransaction(backend, False)
        backend.write = lambda _: (_ for _ in ()).throw(OSError())
        with self.assertRaises(OSError):
            transaction.apply()
        transaction.restore()
        self.assertTrue(transaction.restored)
        self.assertIs(backend.value, True)

    def test_effective_readback_mismatch_is_not_connection_evidence(self):
        backend = Preference(None)
        backend.effective = lambda: True  # Synthetic managed/inherited override.
        transaction = probe.PreferenceTransaction(backend, False)
        with self.assertRaisesRegex(probe.ProbeError, "PREFERENCE_READBACK_MISMATCH"):
            transaction.apply()
        transaction.restore()
        self.assertTrue(transaction.restored)
        self.assertIsNone(backend.value)

    def test_unrelated_intervening_preference_change_is_not_overwritten(self):
        backend = Preference(None)
        transaction = probe.PreferenceTransaction(backend, False)
        transaction.apply()
        backend.value = True
        with self.assertRaisesRegex(probe.ProbeError, "PREFERENCE_CHANGED_DURING_PROBE"):
            transaction.restore()
        self.assertEqual([False], backend.writes)
        self.assertIs(backend.value, True)
        self.assertFalse(transaction.restored)

    def test_failed_restore_is_not_marked_verified(self):
        backend = Preference(None)
        transaction = probe.PreferenceTransaction(backend, False)
        transaction.apply()
        backend.write = lambda _: None
        with self.assertRaisesRegex(probe.ProbeError, "PREFERENCE_RESTORE_MISMATCH"):
            transaction.restore()
        self.assertFalse(transaction.restored)

    def test_not_applied_transaction_does_not_restore_or_mutate(self):
        backend = Preference(None)
        transaction = probe.PreferenceTransaction(backend, False)
        transaction.restore()
        self.assertEqual([], backend.writes)
        self.assertFalse(transaction.restored)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.environment = environment()
        for key in (probe.MODE_ENV, probe.BUILD_ENV, "SIM_UDID", "IOS_RUN_DIR", "SIM_RUNTIME"):
            self.environment.pop(key, None)

    def test_only_two_conditions_in_reviewed_host_context_are_accepted(self):
        with patch.object(probe.ci_evidence.platform, "system", return_value="Darwin"):
            for mode in ("hardware-off", "hardware-on"):
                probe.admit(self.environment, mode)
            for mode in ("", "off", "on", "hardware-off ", "unknown"):
                with self.assertRaises(probe.ProbeError):
                    probe.admit(self.environment, mode)

    def test_admission_refuses_ambient_borrowed_nested_and_expired_inputs(self):
        cases = [{probe.ISOLATED_ENV: ""}, {"GITHUB_ACTIONS": "false"}, {"RUNNER_ENVIRONMENT": "self-hosted"},
            {"GITHUB_WORKFLOW_SHA": "b" * 40}, {"SIM_UDID": BORROWED}, {"IOS_RUN_DIR": "/borrowed"},
            {probe.BUILD_ENV: "1"}, {"SIM_RUNTIME": "com.apple.CoreSimulator.SimRuntime.iOS-26-2"},
            {"P2PKIT_CI_COMMAND_DEADLINE_NS": ""}, {"P2PKIT_CI_COMMAND_DEADLINE_NS": str(time.monotonic_ns())}]
        with patch.object(probe.ci_evidence.platform, "system", return_value="Darwin"):
            for updates in cases:
                with self.subTest(updates=updates), self.assertRaises(probe.ProbeError):
                    probe.admit({**self.environment, **updates}, "hardware-off")

    def test_non_darwin_is_refused_even_with_hosted_environment_strings(self):
        with patch.object(probe.ci_evidence.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(probe.ProbeError, "HOSTED_DARWIN_CONTEXT_REQUIRED"):
                probe.admit(self.environment, "hardware-off")


def device(udid, name, state="Shutdown"):
    return dict(udid=udid, name=name, state=state, isAvailable=True,
                deviceTypeIdentifier=probe.DEVICE_TYPE, runtime=probe.RUNTIME)


def inventory(rows):
    return json.dumps({"devices": {probe.RUNTIME: rows}}).encode()


class BindingTests(unittest.TestCase):
    def test_only_fresh_exact_created_device_grants_cleanup_authority(self):
        before = [device(BORROWED, "unrelated")]
        after = before + [device(OWNED, "controlled")]
        self.assertEqual(OWNED, probe.created_device(OWNED, "controlled", before, after))
        bad = [dict(after[-1], name="unrelated"), dict(after[-1], state="Booted"),
               dict(after[-1], runtime="different"), dict(after[-1], deviceTypeIdentifier="different"),
               dict(after[-1], isAvailable=False)]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(probe.ProbeError):
                probe.created_device(OWNED, "controlled", before, before + [row])
        with self.assertRaisesRegex(probe.ProbeError, "CREATED_DEVICE_WAS_PREEXISTING"):
            probe.created_device(BORROWED.lower(), "unrelated", before, after)

    def test_inventory_refuses_nonobjects_duplicates_and_malformed_identifiers(self):
        for value in ({}, {"devices": []}, {"devices": {probe.RUNTIME: None}},
                      {"devices": {probe.RUNTIME: [{"udid": True}]}},
                      {"devices": {probe.RUNTIME: [device(OWNED, "a"), device(OWNED, "b")]}}):
            with self.subTest(value=value), self.assertRaises(probe.ProbeError):
                probe.devices(json.dumps(value))


class FakeRunner:
    """Synthetic external boundaries; executes the real orchestration/finalizers."""
    def __init__(self, root, environment, cancelled, *, options):
        self.root, self.environment, self.cancelled, self.options = root, environment, cancelled, options
        self.end = int(environment["P2PKIT_CI_COMMAND_DEADLINE_NS"]) / 1e9
        self.commands, self.calls = [], []
        self.cleanup_known = False
        self.finalization_end = None
        self.rows = [device(BORROWED, "unrelated", options.get("initialState", "Shutdown"))]
        self.name = None
        self.developer = root / "Xcode.app/Contents/Developer"
        simulator = self.developer / "Applications/Simulator.app/Contents/MacOS/Simulator"
        simulator.parent.mkdir(parents=True)
        simulator.touch()

    def run(self, name, argv, seconds=120, **kwargs):
        self.calls.append((name, argv, seconds, kwargs))
        row = {"name": name, "exitCode": None}
        self.commands.append(row)
        if name == self.options.get("failure"):
            row["exitCode"] = self.options.get("observedExit")
            raise probe.ProbeError("SYNTHETIC_BOUNDARY_FAILURE")
        code, out = 0, b""
        if name in ("initial-devices", "created-device-readback", "owned-finalization-state", "shutdown-readback", "deletion-readback"):
            out = inventory(self.rows)
        elif name == "ambient-simulator-refusal":
            code = self.options.get("ambientCode", 1)
        elif name == "runtime-inventory":
            out = json.dumps({"runtimes": [{"identifier": probe.RUNTIME, "isAvailable": True}]}).encode()
        elif name == "create-device":
            self.name = argv[3]
            self.rows.append(device(OWNED, self.name))
            if self.options.get("mismatchedCreated"):
                self.rows[-1]["name"] = "unrelated"
            out = self.options.get("createdId", OWNED).encode() + b"\n"
        elif name == "boot-owned-device":
            self.rows[-1]["state"] = "Booted"
        elif name == "developer-directory":
            out = str(self.developer).encode()
        elif name == "original-ui-tests":
            code = self.options.get("uiCode", 0)
            bundle = self.root / "ios-run/DerivedData/Logs/Test/swift-keyboard-readiness.xcresult"
            bundle.mkdir(parents=True)
            (bundle / "original-data").write_bytes(b"synthetic original result\n")
        elif name == "keyboard-events":
            out = self.options.get("events", b'{"eventMessage":"KEYBOARD_CAUSE_EVENT sequence=1 event=armed"}\n')
        elif name == "shutdown-owned-device":
            code = self.options.get("shutdownCode", 0)
            self.rows[-1]["state"] = "Shutdown"
        elif name == "delete-owned-device":
            code = self.options.get("deleteCode", 0)
            if not self.options.get("deleteStays"):
                self.rows = [row for row in self.rows if row["udid"] != OWNED]
        row["exitCode"] = code
        return code, out, b""

    checked = probe.Runner.checked

    def start_simulator(self, executable, device):
        self.calls.append(("simulator-application", [str(executable), "-CurrentDeviceUDID", device], 0, {}))

    def begin_finalization(self):
        self.finalization_end = min(self.end, time.monotonic() + probe.FINALIZATION_SECONDS)

    def drain(self):
        self.cleanup_known = True

    def close(self):
        self.drain()
        return []

    def retain_captures(self, destination):
        destination.mkdir(mode=0o700)
        return []


class OrchestrationTests(unittest.TestCase):
    def execute(self, options=None, mode="hardware-off"):
        temp = tempfile.TemporaryDirectory(prefix="p2pkit-keyboard-cause-control-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        backend = Preference(None)
        environment_value = environment()
        for key in (probe.BUILD_ENV, "SIM_UDID", "IOS_RUN_DIR", "SIM_RUNTIME"):
            environment_value.pop(key, None)
        environment_value[probe.MODE_ENV] = mode
        made = []
        def make_runner(*args):
            runner = FakeRunner(*args, options=options or {})
            made.append(runner)
            return runner
        with patch.object(probe, "ROOT", root), patch.object(probe, "Runner", side_effect=make_runner), \
             patch.object(probe, "CoreFoundationPreference", return_value=backend), \
             patch.object(probe.ci_evidence.platform, "system", return_value="Darwin"), \
             contextlib.redirect_stdout(io.StringIO()):
            code = probe.run_probe(mode, environment_value)
        report = root / "build/reports/keyboard-cause-probe"
        summary = json.loads((report / "summary.json").read_bytes())
        return code, summary, made[0], backend, report

    def test_both_conditions_use_one_exact_original_ui_run_and_preserve_nonzero_original(self):
        for mode, expected in (("hardware-off", 0), ("hardware-on", 65)):
            with self.subTest(mode=mode):
                code, summary, runner, backend, report = self.execute({"uiCode": expected}, mode)
                self.assertEqual(expected, code)
                self.assertEqual(expected, summary["originalUiExitCode"])
                self.assertEqual([], summary["errors"])
                self.assertFalse(summary["underlyingHistoricalCauseEstablished"])
                self.assertTrue(summary["nativeRetirementKnown"])
                self.assertTrue(summary["ownedShutdownObserved"])
                self.assertTrue(summary["ownedDeletionObserved"])
                self.assertTrue(summary["originalXcresult"]["retained"])
                self.assertTrue(summary["preference"]["restorationVerified"])
                self.assertEqual([mode == "hardware-on", None], backend.writes)
                self.assertTrue(backend.closed)
                self.assertFalse(runner.root.is_relative_to(report))
                ui = [row for row in runner.calls if row[0] == "original-ui-tests"]
                self.assertEqual(1, len(ui))
                self.assertEqual(["scripts/run-ios-ui-tests.sh", "run-keyboard-readiness"], ui[0][1][-2:])
                self.assertEqual(2700, ui[0][2])
                child = ui[0][3]["environment"]
                self.assertNotIn(probe.MODE_ENV, child)
                self.assertEqual("1", child[probe.BUILD_ENV])
                self.assertEqual(OWNED, child["SIM_UDID"])
                self.assertEqual(runner.environment["P2PKIT_CI_COMMAND_DEADLINE_NS"], child["P2PKIT_CI_COMMAND_DEADLINE_NS"])
                self.assertEqual(0o700, report.stat().st_mode & 0o777)
                self.assertEqual(0o600, (report / "summary.json").stat().st_mode & 0o777)
                collector = next(row for row in runner.calls if row[0] == "keyboard-events")
                self.assertEqual(["/usr/bin/xcrun", "simctl", "spawn", OWNED, "log", "show", "--style", "ndjson",
                    "--info", "--last", "1h", "--predicate", 'subsystem == "' + probe.SUBSYSTEM + '"'], collector[1])
                self.assertEqual(probe.MAX_EVENTS_BYTES, collector[3]["limit"])
                for name in ("shutdown-owned-device", "delete-owned-device"):
                    calls = [row for row in runner.calls if row[0] == name]
                    self.assertEqual(1, len(calls))
                    self.assertEqual(OWNED, calls[0][1][-1])

    def test_ambient_fixture_refusals_happen_before_preference_changes(self):
        for options in ({"initialState": "Booted"}, {"ambientCode": 0}, {"ambientCode": 2}):
            code, summary, runner, backend, _ = self.execute(options)
            self.assertEqual(125, code)
            self.assertEqual([], backend.writes)
            self.assertIsNone(summary["ownedDevice"])
            self.assertFalse(any(row[0] == "create-device" for row in runner.calls))

    def test_malformed_preexisting_and_unbound_create_responses_never_authorize_delete(self):
        for options in ({"createdId": "not-a-device"}, {"createdId": BORROWED}, {"mismatchedCreated": True}):
            code, summary, runner, backend, _ = self.execute(options)
            self.assertEqual(125, code)
            self.assertIsNone(summary["ownedDevice"])
            self.assertFalse(any(row[0] in ("delete-owned-device", "shutdown-owned-device", "original-ui-tests") for row in runner.calls))
            self.assertIsNone(backend.value)
            self.assertTrue(summary["preference"]["restorationVerified"])

    def test_failed_boot_finalizes_only_positively_owned_shutdown_fixture(self):
        code, summary, runner, backend, _ = self.execute({"failure": "boot-owned-device"})
        self.assertEqual(125, code)
        self.assertIsNone(summary["originalUiExitCode"])
        self.assertEqual(OWNED, summary["ownedDevice"])
        self.assertTrue(summary["ownedShutdownObserved"])
        self.assertTrue(summary["ownedDeletionObserved"])
        self.assertFalse(any(row[0] == "shutdown-owned-device" for row in runner.calls))
        self.assertIsNone(backend.value)

    def test_missing_telemetry_is_failure_with_unchanged_original_ui_status(self):
        code, summary, _, _, report = self.execute({"events": b""})
        self.assertEqual(125, code)
        self.assertEqual(0, summary["originalUiExitCode"])
        self.assertIn("APP_TELEMETRY_NOT_OBSERVED", summary["errors"])
        self.assertEqual(b"", (report / "events.ndjson").read_bytes())
        self.assertTrue(summary["ownedDeletionObserved"])

    def test_capture_failure_does_not_erase_observed_exit_or_skip_restoration(self):
        code, summary, _, backend, _ = self.execute({"failure": "original-ui-tests", "observedExit": 65})
        self.assertEqual(125, code)
        self.assertEqual(65, summary["originalUiExitCode"])
        self.assertIn("SYNTHETIC_BOUNDARY_FAILURE", summary["errors"])
        self.assertTrue(summary["ownedDeletionObserved"])
        self.assertIsNone(backend.value)

    def test_log_capture_failure_still_finalizes_owned_device_and_preference(self):
        code, summary, _, backend, _ = self.execute({"failure": "keyboard-events", "uiCode": 65})
        self.assertEqual(125, code)
        self.assertEqual(65, summary["originalUiExitCode"])
        self.assertTrue(summary["ownedDeletionObserved"])
        self.assertIsNone(backend.value)

    def test_cleanup_tool_errors_and_failed_deletion_readback_are_not_passes_or_retries(self):
        for options in ({"shutdownCode": 1}, {"deleteCode": 1}, {"deleteStays": True}):
            code, summary, runner, backend, _ = self.execute(options)
            self.assertEqual(125, code)
            self.assertEqual(0, summary["originalUiExitCode"])
            self.assertTrue(summary["errors"])
            self.assertEqual(1, len([row for row in runner.calls if row[0] == "delete-owned-device"]))
            self.assertIsNone(backend.value)


class FakeScope:
    def __init__(self):
        self.leaders, self.discovery_errors = [], []
        self.after_spawn = self.after_poll = lambda: None
        self.output = b""
        self.spawn_error = self.close_error = False
        self.deadlines = []

    def spawn(self, argv, cwd, environment):
        def poll():
            self.after_poll()
            return 0
        child = SimpleNamespace(pid=123, stdout=io.BytesIO(self.output), stderr=io.BytesIO(), poll=poll)
        self.leaders.append(child)
        self.after_spawn()
        if self.spawn_error:
            raise RuntimeError("synthetic post-registration error")
        return child

    def discover(self):
        return []

    def drain(self, **kwargs):
        self.deadlines.append(kwargs["deadline"])
        return []

    def close(self):
        self.leaders.clear()
        if self.close_error:
            raise RuntimeError("synthetic close error")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="keyboard-native-boundary-control-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = FakeScope()
        self.clock = [10.0]
        self.cancelled = [False]
        self.patches = [patch.object(probe.ci_evidence, "local_command_scope", return_value=self.scope),
                       patch.object(probe.time, "monotonic", side_effect=lambda: self.clock[0])]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        env = environment()
        env["P2PKIT_CI_COMMAND_DEADLINE_NS"] = str(1000 * 10**9)
        self.runner = probe.Runner(self.root, env, lambda: self.cancelled[0])

    def close_runner(self):
        self.runner.begin_finalization()
        return self.runner.close()

    def test_native_spawn_time_counts_and_late_fast_exit_cannot_pass(self):
        self.scope.after_spawn = lambda: self.clock.__setitem__(0, 13.0)
        with self.assertRaisesRegex(probe.ProbeError, "COMMAND_DEADLINE"):
            self.runner.run("spawn-time", ["synthetic"], 2)
        self.assertFalse(self.runner.commands[0]["completedWithinDeadline"])
        self.assertEqual([], self.close_runner())

    def test_fast_poll_past_original_stage_end_retains_code_but_fails(self):
        self.scope.after_poll = lambda: self.clock.__setitem__(0, 13.0)
        with self.assertRaisesRegex(probe.ProbeError, "COMMAND_DEADLINE"):
            self.runner.run("poll-time", ["synthetic"], 2)
        self.assertEqual(0, self.runner.commands[0]["exitCode"])
        self.assertFalse(self.runner.commands[0]["completedWithinDeadline"])
        self.assertEqual([], self.close_runner())

    def test_cancellation_after_spawn_is_not_bypassed_by_already_exited_child(self):
        self.scope.after_spawn = lambda: self.cancelled.__setitem__(0, True)
        with self.assertRaisesRegex(probe.ProbeError, "CANCELLED"):
            self.runner.run("cancelled", ["synthetic"])
        self.assertEqual([], self.close_runner())

    def test_one_cleanup_end_is_clamped_to_original_outer_deadline(self):
        self.clock[0] = 970.0
        self.runner.begin_finalization()
        self.assertEqual(1000, self.runner.finalization_end)
        self.runner.drain()
        self.clock[0] = 990.0
        self.runner.drain()
        self.assertEqual([1000, 1000], self.scope.deadlines)
        self.assertEqual(1000, self.runner.end)
        with self.assertRaisesRegex(probe.ProbeError, "FINALIZATION_ALREADY_STARTED"):
            self.runner.begin_finalization()
        self.assertEqual([], self.runner.close())

    def test_bounded_capture_failure_retains_closed_partial_and_allows_cleanup_commands(self):
        self.scope.output = b"synthetic bounded original\n"
        with self.assertRaisesRegex(probe.ProbeError, "CAPTURE_FAILED|CAPTURE_NOT_CLOSED"):
            self.runner.run("over-limit", ["synthetic"], limit=4)
        self.runner.begin_finalization()
        self.scope.output = b""
        self.assertEqual(b"", self.runner.checked("cleanup-tool", ["synthetic"]))
        self.assertIn("FINAL_CAPTURE_NOT_CLOSED", self.runner.close())
        records = self.runner.retain_captures(self.root / "reports")
        original = next(row for row in records if row["name"] == "over-limit.stdout")
        self.assertTrue(original["retained"])
        self.assertTrue(original["eof"])
        self.assertEqual("OUTPUT_LIMIT", original["error"])
        self.assertEqual(b"synt", (self.root / "reports/over-limit.stdout").read_bytes())

    def test_post_registration_spawn_failure_closes_unadopted_original_pipes(self):
        self.scope.spawn_error = True
        with self.assertRaises(RuntimeError):
            self.runner.run("spawn-failed", ["synthetic"])
        child = self.scope.leaders[0]
        self.assertEqual([], self.close_runner())
        self.assertTrue(child.stdout.closed)
        self.assertTrue(child.stderr.closed)

    def test_second_capture_acquisition_failure_closes_both_original_pipes(self):
        original = probe.ci_evidence.Capture
        calls = [0]
        def capture(*args):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError("synthetic allocation failure")
            return original(*args)
        with patch.object(probe.ci_evidence, "Capture", side_effect=capture):
            with self.assertRaises(OSError):
                self.runner.run("capture-failed", ["synthetic"])
        child = self.scope.leaders[0]
        self.assertEqual([], self.close_runner())
        self.assertTrue(child.stdout.closed)
        self.assertTrue(child.stderr.closed)

    def test_scope_close_failure_is_not_known_retirement(self):
        self.runner.run("complete", ["synthetic"])
        self.scope.close_error = True
        self.assertIn("RuntimeError", self.close_runner())
        self.assertFalse(self.runner.cleanup_known)

    def test_exited_simulator_application_is_not_a_started_controlled_treatment(self):
        with self.assertRaisesRegex(probe.ProbeError, "SIMULATOR_APPLICATION_EXITED"):
            self.runner.start_simulator(Path("/synthetic/Simulator"), OWNED)
        self.assertEqual(0, self.runner.commands[0]["exitCodeAtStart"])
        self.assertEqual([], self.close_runner())


class RetentionAndSourceTests(unittest.TestCase):
    def test_original_xcresult_retention_refuses_links_without_traversing_other_derived_data(self):
        with tempfile.TemporaryDirectory() as name:
            private = Path(name) / "private"
            bundle = private / "ios-run/DerivedData/Logs/Test/swift-keyboard-readiness.xcresult"
            bundle.mkdir(parents=True)
            (bundle / "data").write_bytes(b"synthetic result")
            (private / "ios-run/DerivedData/ignored-large-product").write_bytes(b"not a report")
            reports = Path(name) / "reports"
            reports.mkdir()
            result = probe.retain_xcresult(private, reports)
            self.assertTrue(result["retained"])
            self.assertEqual(["data"], [path.name for path in reports.rglob("*") if path.is_file()])
            (bundle / "link").symlink_to(private / "ios-run/DerivedData/ignored-large-product")
            with self.assertRaisesRegex(probe.ProbeError, "UNSUPPORTED_XCRESULT_ENTRY"):
                probe.retain_xcresult(private, Path(name) / "different-reports")

    def test_telemetry_contains_no_field_values_input_or_accessibility_queries(self):
        source = (ROOT / "samples/iosApp/KeyboardCauseProbe.swift").read_text()
        self.assertTrue(source.startswith("#if DEBUG\n"))
        self.assertIn('arguments.contains("--p2pkit-ui-test-keyboard-cause-probe")', source)
        self.assertIn(".isFirstResponder", source)
        self.assertIn("keyboardFrameEndUserInfoKey", source)
        self.assertIn("textField", source)
        for forbidden in (".text\n", ".text,", ".text)", ".value", ".typeText", "becomeFirstResponder",
                          "resignFirstResponder", "XCUIApplication", "isHittable", ".exists", "UIPasteboard"):
            self.assertNotIn(forbidden, source)
        tests = (ROOT / "samples/iosApp/UITests/ContentViewPresentationUITests.swift").read_text()
        self.assertEqual(1, tests.count("#if P2PKIT_KEYBOARD_CAUSE_PROBE"))
        self.assertEqual(1, tests.count('app.launchArguments.append("--p2pkit-ui-test-keyboard-cause-probe")'))


if __name__ == "__main__":
    unittest.main()
