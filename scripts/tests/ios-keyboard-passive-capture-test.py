#!/usr/bin/env python3
"""Portable post-Xcode capture controls; not native keyboard causal evidence."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import ios_keyboard_passive_capture as capture

DEVICE = "11111111-1111-1111-1111-111111111111"
EVENT = b'{"eventMessage":"KEYBOARD_CAUSE_EVENT sequence=1 event=armed"}\n'


def environment(root):
    return capture.audit_processes.ownership_environment(dict(
        COMPONENT="compatibility", GITHUB_ACTIONS="true", RUNNER_ENVIRONMENT="github-hosted",
        GITHUB_REPOSITORY="p2pKit/P2pKit", GITHUB_SHA="a" * 40, GITHUB_WORKFLOW_SHA="a" * 40,
        GITHUB_WORKFLOW_REF="p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/fixture",
        P2PKIT_CI_COMMAND_DEADLINE_NS=str(time.monotonic_ns() + 3600 * 10**9)),
        "b" * 32, "c" * 32, str(root / "outer-state"), str(root / "outer-home"))


class Child:
    def __init__(self, options):
        self.options = options
        self.stdout = io.BytesIO(options.get("stdout", EVENT))
        self.stderr = io.BytesIO(options.get("stderr", b""))
        self.returncode = options.get("exit", 0)
        self.waits = []

    def poll(self):
        if "afterPoll" in self.options:
            self.options["afterPoll"]()
        return self.returncode

    def wait(self, timeout):
        self.waits.append(timeout)
        return self.returncode


class Scope:
    def __init__(self, options):
        self.options = options
        self.leaders, self.calls, self.drains = [], [], []
        self.discovery_errors = []
        self.closed = False

    def spawn(self, argv, cwd, environment):
        self.calls.append((argv, cwd, environment))
        self.child = Child(self.options)
        self.leaders.append(self.child)
        if self.options.get("spawnAfterRegistration"):
            raise capture.audit_processes.OwnershipError("not a public diagnostic")
        return self.child

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait, deadline):
        self.drains.append(deadline)
        if "afterDrain" in self.options:
            self.options["afterDrain"]()
        if self.options.get("drainFailure"):
            raise capture.audit_processes.OwnershipError("private native failure")
        return [object()] if self.options.get("live") else []

    def close(self):
        self.closed = True
        self.leaders.clear()
        if self.options.get("closeFailure"):
            raise capture.audit_processes.OwnershipError("private native close failure")


class AdmissionTests(unittest.TestCase):
    def test_hosted_compatibility_and_exact_device_are_required(self):
        env = environment(Path("/fixture"))
        with patch.object(capture.ci_evidence.platform, "system", return_value="Darwin"):
            self.assertGreater(capture.admit(env, DEVICE), time.monotonic())
            self.assertGreater(capture.admit({**env, "COMPONENT": "apple-keyboard-query-diagnostic"}, DEVICE), time.monotonic())
            for updates in ({"COMPONENT": "source"}, {"COMPONENT": "apple-keyboard-diagnostic"}, {"GITHUB_ACTIONS": "false"},
                            {"GITHUB_WORKFLOW_SHA": "d" * 40}, {"RUNNER_ENVIRONMENT": "self-hosted"},
                            {capture.DEADLINE_ENV: ""}, {capture.audit_processes.STATE_ENV: "/other"}):
                with self.subTest(updates=updates), self.assertRaises(capture.CaptureError):
                    capture.admit({**env, **updates}, DEVICE)
            for device in ("booted", "iPhone 17", "", DEVICE + " extra"):
                with self.subTest(device=device), self.assertRaises(capture.CaptureError):
                    capture.admit(env, device)
        with patch.object(capture.ci_evidence.platform, "system", return_value="Linux"):
            with self.assertRaises(capture.CaptureError):
                capture.admit(env, DEVICE)

    def test_missing_or_incoherent_canonical_domain_is_not_replaced(self):
        env = environment(Path("/fixture"))
        with patch.object(capture.ci_evidence, "_hosted_darwin_context", return_value=True):
            for keys in ((capture.audit_processes.CHAIN_ENV, capture.audit_processes.DOMAINS_ENV),
                         (capture.audit_processes.JOB_ENV,), ("GRADLE_USER_HOME",)):
                changed = {key: value for key, value in env.items() if key not in keys}
                with self.subTest(keys=keys), self.assertRaises(capture.CaptureError):
                    capture.admit(changed, DEVICE)


class CaptureTests(unittest.TestCase):
    def run_capture(self, options=None, *, command=0, launcher=0, clock=None, deadline=None, cancelled=False):
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="passive-keyboard-controls-")))
        env = environment(root)
        if deadline is not None:
            env[capture.DEADLINE_ENV] = str(int(deadline * 1e9))
        scope = Scope(options or {})
        with patch.object(capture.ci_evidence, "_hosted_darwin_context", return_value=True), \
             patch.object(capture.ci_evidence, "local_command_scope", return_value=scope) as factory:
            if clock is not None:
                self.enterContext(patch.object(capture.time, "monotonic", side_effect=lambda: clock[0]))
            result, summary = capture.collect(DEVICE, command, launcher, env, root=root,
                                              cancelled=lambda: cancelled)
        report = root / "build/reports/keyboard-passive-probe"
        self.assertEqual(summary, json.loads((report / "summary.json").read_text()))
        self.assertEqual(env[capture.DEADLINE_ENV], summary["inheritedDeadlineNs"])
        self.assertEqual(command, summary["originalCommandExitCode"])
        self.assertEqual(launcher, summary["originalLauncherExitCode"])
        self.assertFalse(summary["deviceMutationAuthority"])
        self.assertFalse(summary["underlyingHistoricalCauseEstablished"])
        return result, summary, scope, report, env, factory

    def test_one_read_only_exact_uuid_command_retains_both_closed_private_streams(self):
        code, summary, scope, report, env, factory = self.run_capture({"stderr": b"synthetic diagnostic\n"})
        self.assertEqual(0, code)
        self.assertEqual([], summary["errors"])
        self.assertTrue(summary["nativeRetirementKnown"])
        self.assertTrue(summary["capturesClosed"])
        self.assertTrue(summary["logCompletedWithinDeadline"])
        self.assertEqual(1, len(scope.calls))
        self.assertEqual(["/usr/bin/xcrun", "simctl", "spawn", DEVICE, "log", "show", "--style", "ndjson",
            "--info", "--last", "3h", "--predicate", 'subsystem == "' + capture.SUBSYSTEM + '"'], scope.calls[0][0])
        self.assertEqual(EVENT, (report / "stdout.log").read_bytes())
        self.assertEqual(b"synthetic diagnostic\n", (report / "stderr.log").read_bytes())
        self.assertTrue(scope.closed)
        for path in report.iterdir():
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual(0o700, report.stat().st_mode & 0o777)
        child_env = scope.calls[0][2]
        for key, value in env.items():
            self.assertEqual(value, child_env[key], key)
        self.assertEqual({capture.audit_processes.LOCAL_CHAIN_ENV}, set(child_env) - set(env))
        self.assertEqual(env, factory.call_args.args[-1])
        for row in summary["captures"]:
            raw = (report / row["name"]).read_bytes()
            self.assertEqual(len(raw), row["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])

    def test_original_test_failure_is_not_a_capture_failure_or_pass_override(self):
        code, summary, *_ = self.run_capture(command=65, launcher=65)
        self.assertEqual(0, code)  # Caller must retain its original65, not this diagnostic exit.
        self.assertEqual([], summary["errors"])

    def test_capture_nonzero_remains_failure_with_original_status_separate(self):
        code, summary, *_ = self.run_capture({"exit": 17}, command=65, launcher=65)
        self.assertEqual(125, code)
        self.assertEqual(17, summary["logExitCode"])
        self.assertIn("LOG_COMMAND_FAILED", summary["errors"])

    def test_output_bound_is_enforced_and_closed_partial_is_not_complete(self):
        code, summary, _, report, *_ = self.run_capture({"stdout": EVENT + b"x" * capture.MAX_BYTES})
        self.assertEqual(125, code)
        self.assertFalse(summary["capturesClosed"])
        self.assertIn("CAPTURE_NOT_CLOSED", summary["errors"])
        self.assertEqual(capture.MAX_BYTES, (report / "stdout.log").stat().st_size)
        self.assertEqual("OUTPUT_LIMIT", summary["captures"][0]["error"])

    def test_native_spawn_exception_still_retires_registered_leader_and_original_pipes(self):
        code, summary, scope, *_ = self.run_capture({"spawnAfterRegistration": True})
        self.assertEqual(125, code)
        self.assertTrue(scope.drains)
        self.assertTrue(scope.closed)
        self.assertTrue(scope.child.stdout.closed)
        self.assertTrue(scope.child.stderr.closed)
        self.assertFalse(summary["capturesClosed"])
        self.assertNotIn("not a public diagnostic", json.dumps(summary))

    def test_active_capture_writer_is_never_read_or_retained(self):
        class ActiveCapture:
            def __init__(self, pipe, path, limit):
                self.pipe, self.path = pipe, path
                self.eof, self.closed, self.error = False, False, None
                self.thread = SimpleNamespace(ident=1, start=lambda: None, is_alive=lambda: True,
                                              join=lambda timeout: None)
        with patch.object(capture.ci_evidence, "Capture", ActiveCapture):
            code, summary, scope, report, *_ = self.run_capture()
        self.assertEqual(125, code)
        self.assertFalse(summary["capturesClosed"])
        self.assertTrue(all(not row["retained"] for row in summary["captures"]))
        self.assertFalse((report / "stdout.log").exists())
        self.assertFalse((report / "stderr.log").exists())
        # These are synthetic pipes, not real active capture threads.
        scope.child.stdout.close()
        scope.child.stderr.close()

    def test_unknown_native_retirement_or_close_is_never_success(self):
        for option in ("live", "drainFailure", "closeFailure"):
            with self.subTest(option=option):
                code, summary, scope, *_ = self.run_capture({option: True})
                self.assertEqual(125, code)
                self.assertFalse(summary["nativeRetirementKnown"])
                self.assertTrue(scope.closed)
                self.assertNotIn("private native", json.dumps(summary))

    def test_no_app_event_cannot_claim_observation(self):
        code, summary, *_ = self.run_capture({"stdout": b""})
        self.assertEqual(125, code)
        self.assertIn("APP_TELEMETRY_NOT_OBSERVED", summary["errors"])

    def test_expired_or_insufficient_outer_deadline_spawns_nothing(self):
        for end in (99, 120):
            with self.subTest(end=end):
                code, summary, scope, _, _, factory = self.run_capture(clock=[100], deadline=end)
                self.assertEqual(125, code)
                self.assertIn("CAPTURE_DEADLINE", summary["errors"])
                self.assertEqual([], scope.calls)
                factory.assert_not_called()

    def test_late_zero_exit_is_preserved_but_cannot_pass(self):
        clock = [100]
        code, summary, scope, *_ = self.run_capture(
            {"afterPoll": lambda: clock.__setitem__(0, 131)}, clock=clock, deadline=1000)
        self.assertEqual(125, code)
        self.assertEqual(0, summary["logExitCode"])
        self.assertFalse(summary["logCompletedWithinDeadline"])
        self.assertIn("CAPTURE_DEADLINE", summary["errors"])
        self.assertEqual([160], scope.drains)  # No later cleanup-budget restart.

    def test_close_and_work_end_stay_inside_original_outer_deadline(self):
        code, summary, scope, *_ = self.run_capture(clock=[100], deadline=150)
        self.assertEqual(0, code)
        self.assertEqual([150], scope.drains)

    def test_late_close_never_starts_a_new_budget_or_claims_success(self):
        clock = [100]
        code, summary, scope, *_ = self.run_capture(
            {"afterDrain": lambda: clock.__setitem__(0, 161)}, clock=clock, deadline=1000)
        self.assertEqual(125, code)
        self.assertEqual([160], scope.drains)
        self.assertIn("CAPTURE_CLOSE_DEADLINE", summary["errors"])

    def test_cancellation_or_signal_does_not_start_new_native_read(self):
        for options in ({"cancelled": True}, {"launcher": 143, "command": None},
                        {"launcher": 130, "command": 0}):
            with self.subTest(options=options):
                code, summary, scope, _, _, factory = self.run_capture(**options)
                self.assertEqual(125, code)
                self.assertIn("CANCELLED", summary["errors"])
                self.assertEqual([], scope.calls)
                factory.assert_not_called()


class SourceContractTests(unittest.TestCase):
    def test_original_ui_inputs_deadlines_and_all_method_bodies_are_unchanged(self):
        text = (ROOT / "samples/iosApp/UITests/ContentViewPresentationUITests.swift").read_text()
        original, substitutions = re.subn(r"        #if P2PKIT_KEYBOARD_CAUSE_PROBE\n.*?        #endif\n",
                                           "", text, flags=re.S)
        self.assertEqual(1, substitutions)
        self.assertEqual("05182cfd3780c447a6039d4640a2d32d938ed605e1c71adac34160e2f47cf89c",
                         hashlib.sha256(original.encode()).hexdigest())

    def test_existing_component_commands_and_shared_launcher_are_unchanged(self):
        for name, digest in {
            # Actual main69fd925d: retains PR523's API-candidate control.
            "scripts/ci_component.py": "0a07b3ce30b297d274dfd4fc524ebcb80f57a8bdfc1fd00edbb7c32fd575e2bc",
            "scripts/run-ios-app.sh": "80e34e317f14fe6fb17f8d17ea2fa7edb9b80bfa26e6a21d344f5d68d2b4cd5e",
        }.items():
            with self.subTest(name=name):
                text = (ROOT / name).read_text()
                if name == "scripts/ci_component.py":
                    text = text.replace(
                        "'apple-keyboard-diagnostic': ('macos-26', 60),\n               "
                        "'apple-keyboard-query-diagnostic': ('macos-26', 60)}",
                        "'apple-keyboard-diagnostic': ('macos-26', 60)}")
                    text, count = re.subn(
                        r"    if component == 'apple-keyboard-query-diagnostic':\n.*?(?=    if component)",
                        "", text, flags=re.S)
                    self.assertEqual(1, count)
                self.assertEqual(digest, hashlib.sha256(text.encode()).hexdigest())

    def test_original_project_and_full_test_targets_are_unchanged_outside_diagnostics(self):
        text = (ROOT / "samples/iosApp/project.yml").read_text()
        for source in ("KeyboardCauseProbe.swift", "KeyboardQueryGate.swift",
                       "KeyboardCauseProbeControls/Sources/KeyboardCauseProbeRecord/KeyboardCauseProbeRecord.swift"):
            line = "      - " + source + "\n"
            self.assertEqual(1, text.count(line))
            text = text.replace(line, "")
        text, count = re.subn(
            r"  # Delayed native-key query investigation, excluded from ordinary acceptance.\n"
            r"  p2pkit-sample-keyboard-query-tests:.*?(?=  # The real JVM peer)", "", text, flags=re.S)
        self.assertEqual(1, count)
        text, count = re.subn(r"  p2pkit-sample-keyboard-query:\n.*\Z", "", text, flags=re.S)
        self.assertEqual(1, count)
        self.assertEqual("18682366898ae7afbfd21e4f16764ee9fb494bf4f0262dfc748776b3ea51bcc4",
                         hashlib.sha256(text.encode()).hexdigest())

    def test_passive_native_sources_are_exact_native_verified_e027b7a9_sources(self):
        for name, digest in {
            "KeyboardCauseProbe.swift": "bb1c534535c6b12d49773f21af35b5375b7f0678928f4fe04f59801a63ea12aa",
            "KeyboardCauseProbeControls/Sources/KeyboardCauseProbeRecord/KeyboardCauseProbeRecord.swift":
                "e5b2d9b9217058c52c793c858c02fd03e6786306bf04cbc120e487e80695abd3",
            "KeyboardCauseProbeControls/Tests/KeyboardCauseProbeRecordTests/KeyboardCauseProbeContractTests.swift":
                "ebd2efc995f3b13b66cabaf13ee4653bce83da909d4b6002850d2af007a8d856",
        }.items():
            with self.subTest(name=name):
                self.assertEqual(digest, hashlib.sha256((ROOT / "samples/iosApp" / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
