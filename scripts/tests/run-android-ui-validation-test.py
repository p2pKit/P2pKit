#!/usr/bin/env python3
"""Offline admission fixtures only; no Gradle, Android runtime, device or network."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("android_ui", Path(__file__).resolve().parents[1] /
                                            "run-android-ui-validation.py")
ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui)
TOKEN = "a" * 32
SOURCE = "b" * 40
TREE = "c" * 40


def result(case="317", changes=None):
    fields = {"p2pkitToken": TOKEN, "p2pkitCompleted": "1", "p2pkitOutcome": ui.PASS,
              "p2pkitEvidence": f"no_backup/ui-{case}-{TOKEN}", "class": ui.CASES[case][0],
              "test": ui.CASES[case][1], "numtests": "1", "current": "1"}
    if case == "317":
        fields["p2pkitCleanup"] = "RETIRED_OWNED_OBSERVERS"
    fields.update(changes or {})
    status = "".join(f"INSTRUMENTATION_STATUS: {key}={value}\n" for key, value in fields.items())
    final = "".join(f"INSTRUMENTATION_RESULT: {key}={value}\n" for key, value in fields.items())
    return (status + "INSTRUMENTATION_STATUS_CODE: 0\n" + final + "INSTRUMENTATION_CODE: -1\n").encode()


def report(case="317", changes=None):
    value = {"case": case, "sourceCommit": SOURCE, "declaredSourceTree": TREE, "api": 35,
             "targetSdk": 37, "outcome": ui.PASS}
    if case == "317":
        value.update(token=TOKEN, cleanupFailures=[],
                     independentVisualAndMutationReview="REQUIRED_NOT_PERFORMED_BY_RUNNER")
    else:
        value.update(cleanup=[{"step": "fixture only", "outcome": "RETIRED"}], lifecycleViolation=False)
    value.update(changes or {})
    return json.dumps(value).encode()


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as target:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(content) if kind == tarfile.REGTYPE else 0
            info.linkname = "result.json" if kind == tarfile.SYMTYPE else ""
            target.addfile(info, io.BytesIO(content) if kind == tarfile.REGTYPE else None)
    return out.getvalue()


class GuestFixture:
    """Synthetic command/clock control, never an adb or runtime witness."""
    def __init__(self):
        self.now = 0.0
        self.calls = []
        self.responses = {}
        self.delay = 0.25
        self.emulator = Mock()
        self.emulator.poll.return_value = None

    def sleep(self, seconds):
        self.now += seconds

    def run(self, command, *, timeout, check):
        self.calls.append((tuple(command), timeout, self.now))
        if self.delay > timeout:
            self.now += timeout
            raise ValueError("synthetic command deadline")
        self.now += self.delay
        key = tuple(command[1:])
        if key in self.responses:
            value = self.responses[key]
            if isinstance(value, Exception):
                raise value
            if callable(value):
                return value()
            return value
        if key == ("shell", "getprop", "sys.boot_completed"):
            return 0, b"1\n"
        if key[:3] == ("shell", "service", "check"):
            return 0, f"Service {key[3]}: found\n".encode()
        if key == ("emu", "avd", "name"):
            return 0, b"owned-fixture\nOK\n"
        if key == ("shell", "getprop", "ro.build.version.sdk"):
            return 0, b"37\n"
        if key == ("shell", "getprop"):
            return 0, b"synthetic properties\n"
        if key == ("shell", "df", "-k", "/data", "/data/local/tmp"):
            return 0, b"synthetic data filesystem observation\n"
        if key == ("shell", "input", "keyevent", "82"):
            return 0, b""
        raise AssertionError("Unexpected synthetic command")

    def admit(self, report):
        ui.admit_android_guest(self.run, ["owned-adb"], self.emulator, "owned-fixture", 37,
                               report, clock=lambda: self.now, sleep=self.sleep)

    def unlocks(self):
        return [item for item in self.calls if item[0][1:] == ("shell", "input", "keyevent", "82")]


class AndroidBootAdmissionTests(unittest.TestCase):
    def test_boot_flag_and_all_real_services_then_one_unlock(self):
        guest = GuestFixture()
        with tempfile.TemporaryDirectory() as directory:
            guest.admit(Path(directory))
            self.assertEqual((Path(directory) / "runtime-properties.txt").read_bytes(), b"synthetic properties\n")
            self.assertEqual((Path(directory) / "runtime-data-space.txt").read_bytes(),
                             b"synthetic data filesystem observation\n")
        self.assertEqual(len(guest.unlocks()), 1)
        self.assertEqual([item[0][-1] for item in guest.calls if item[0][1:4] == ("shell", "service", "check")],
                         ["input", "activity", "package", "settings"])
        for _, timeout, start in guest.calls:
            self.assertLessEqual(timeout, min(15, 180 - start))

    def test_boot_flag_without_any_one_service_never_unlocks(self):
        for service in ui.BOOT_SERVICES:
            for invalid in ((0, f"Service {service}: not found\n".encode()), (0, b"found\n"),
                            (0, b"Service foreign: found\n"), (1, f"Service {service}: found\n".encode()),
                            (0, (f"Service {service}: found\n" * 2).encode())):
                with self.subTest(service=service, invalid=invalid), tempfile.TemporaryDirectory() as directory:
                    guest = GuestFixture()
                    guest.responses[("shell", "service", "check", service)] = invalid
                    with self.assertRaises(ValueError):
                        guest.admit(Path(directory))
                    self.assertFalse(guest.unlocks())
                    self.assertLessEqual(guest.now, 180)
                    for _, timeout, start in guest.calls:
                        self.assertLessEqual(timeout, min(15, 180 - start))

    def test_real_service_readiness_may_follow_boot_flag_within_same_bound(self):
        guest = GuestFixture()
        guest.responses[("shell", "service", "check", "input")] = lambda: (
            (0, b"Service input: not found\n") if guest.now < 12 else (0, b"Service input: found\n"))
        with tempfile.TemporaryDirectory() as directory:
            guest.admit(Path(directory))
        self.assertEqual(len(guest.unlocks()), 1)
        self.assertGreaterEqual(guest.unlocks()[0][2], 12)
        self.assertLess(guest.now, 180)

    def test_absent_boot_flag_or_dead_owned_emulator_never_unlocks(self):
        for dead in (False, True):
            guest = GuestFixture()
            guest.responses[("shell", "getprop", "sys.boot_completed")] = (0, b"0\n")
            if dead:
                guest.emulator.poll.return_value = 1
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                guest.admit(Path(directory))
            self.assertFalse(guest.unlocks())
            self.assertLessEqual(guest.now, 180)
            if dead:
                self.assertFalse(guest.calls)

    def test_identity_or_unlock_failure_is_not_retried(self):
        for command, failure, unlocks in (
            (("emu", "avd", "name"), (0, b"foreign\nOK\n"), 0),
            (("shell", "getprop", "ro.build.version.sdk"), (0, b"35\n"), 0),
            (("shell", "input", "keyevent", "82"), ValueError("synthetic missing input"), 1),
        ):
            guest = GuestFixture()
            guest.responses[command] = failure
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                guest.admit(Path(directory))
            self.assertEqual(len(guest.unlocks()), unlocks)
            self.assertEqual(sum(item[0][1:] == command for item in guest.calls), 1)

    def test_command_time_counts_toward_original_deadline(self):
        guest = GuestFixture()
        guest.delay = 14
        guest.responses[("shell", "service", "check", "settings")] = (0, b"Service settings: not found\n")
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            guest.admit(Path(directory))
        self.assertFalse(guest.unlocks())
        self.assertEqual(guest.now, 180)
        self.assertLess(guest.calls[-1][1], 15)

    def test_private_failure_capture_is_fixed_read_only_bounded_and_best_effort(self):
        now, calls = [0.0], []
        emulator = Mock()
        emulator.poll.return_value = None

        def run(command, *, timeout, check):
            calls.append(command)
            self.assertFalse(check)
            self.assertLessEqual(timeout, min(5, 20 - now[0]))
            if len(calls) == 1:
                now[0] += 0.25
                return 0, b"owned-fixture\nOK\n"
            now[0] += timeout
            if len(calls) == 2:
                raise ValueError("synthetic diagnostic timeout")
            return 1, b"synthetic diagnostic failure\n"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ui.capture_boot_failure(run, ["owned-adb"], emulator, "owned-fixture", path, clock=lambda: now[0])
            failure = json.loads((path / "boot-failure.json").read_text())
            self.assertEqual(failure["admission"], "FAILED")
            self.assertEqual(failure["guestDiagnostics"], "ATTEMPTED")
            self.assertEqual(failure["captures"][0]["failureType"], "ValueError")
            self.assertEqual([item.get("exitCode") for item in failure["captures"][1:]], [1, 1, 1])
        self.assertEqual(calls, [
            ["owned-adb", "emu", "avd", "name"],
            ["owned-adb", "shell", "service", "list"],
            ["owned-adb", "shell", "pidof", "system_server"],
            ["owned-adb", "shell", "getprop"],
            ["owned-adb", "shell", "logcat", "-d", "-t", "200", "-v", "brief", "-s",
             "SystemServer:E", "AndroidRuntime:E", "ActivityManager:W"],
        ])
        self.assertEqual(now[0], 20)

    def test_diagnostics_refuse_dead_foreign_partial_duplicate_failed_or_timed_out_identity(self):
        for identity in (None, (0, b"foreign\nOK\n"), (0, b"owned-fixture\n"),
                         (0, b"owned-fixture\nOK\nOK\n"), (1, b"owned-fixture\nOK\n"),
                         ValueError("synthetic identity timeout")):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as directory:
                emulator, run = Mock(), Mock()
                emulator.poll.return_value = 1 if identity is None else None
                if isinstance(identity, Exception):
                    run.side_effect = identity
                else:
                    run.return_value = identity
                path = Path(directory)
                ui.capture_boot_failure(run, ["owned-adb"], emulator, "owned-fixture", path)
                failure = json.loads((path / "boot-failure.json").read_text())
                self.assertEqual(failure["guestDiagnostics"], "NOT_CAPTURED")
                self.assertEqual(failure["captures"], [])
                self.assertEqual(list(path.iterdir()), [path / "boot-failure.json"])
                self.assertEqual(run.call_count, 0 if identity is None else 1)
                if identity is not None:
                    self.assertEqual(run.call_args.args[0], ["owned-adb", "emu", "avd", "name"])

    def test_diagnostics_stop_if_original_emulator_exits_after_identity(self):
        emulator, run = Mock(), Mock()
        emulator.poll.side_effect = [None, None, 1, 1, 1, 1]
        run.return_value = (0, b"owned-fixture\nOK\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ui.capture_boot_failure(run, ["owned-adb"], emulator, "owned-fixture", path)
            failure = json.loads((path / "boot-failure.json").read_text())
            self.assertTrue(all(item.get("failureType") == "ValueError" for item in failure["captures"]))
            self.assertEqual(run.call_count, 1)

    def test_permission_failure_observations_share_20s_and_never_repeat_instrumentation(self):
        now, calls = [0.0], []
        emulator = Mock()
        emulator.poll.return_value = None

        def run(command, *, timeout, check):
            calls.append(command)
            self.assertFalse(check)
            self.assertEqual(timeout, 5 if len(calls) == 1 else 2.5)
            now[0] += timeout
            if len(calls) == 1:
                return 0, b"owned-fixture\nOK\n"
            if len(calls) == 2:
                raise ValueError("synthetic crash-buffer timeout")
            return 1, b"synthetic unavailable observer\n"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ui.capture_guest_failure(run, ["owned-adb"], emulator, "owned-fixture", path,
                                     phase="permission", clock=lambda: now[0])
            failure = json.loads((path / "permission-failure.json").read_text())
            self.assertEqual(failure["admission"], "PREVIOUSLY_COMPLETED")
            self.assertEqual(failure["outcome"], "FAILED")
            self.assertEqual(failure["captures"][0]["failureType"], "ValueError")
            self.assertEqual(failure["captures"][0]["capture"], "crash-buffer")
            self.assertEqual(len(failure["captures"]), 6)
        self.assertEqual(calls, [
            ["owned-adb", "emu", "avd", "name"],
            ["owned-adb", "shell", "logcat", "-b", "crash", "-d", "-t", "200", "-v", "brief"],
            ["owned-adb", "shell", "logcat", "-d", "-t", "200", "-v", "brief", "-s",
             "SystemServer:E", "AndroidRuntime:E", "ActivityManager:W", "ServiceManager:W", "servicemanager:W",
             "lmkd:I", "lowmemorykiller:I", "libprocessgroup:W", "auditd:I"],
            ["owned-adb", "shell", "service", "list"],
            ["owned-adb", "shell", "pidof", "system_server"],
            ["owned-adb", "shell", "cmd", "activity", "get-current-user"],
            ["owned-adb", "shell", "cat", "/proc/meminfo", "/proc/pressure/memory", "/proc/self/cgroup",
             "/sys/fs/cgroup/memory.events", "/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max"],
        ])
        self.assertEqual(now[0], 20)

    def test_permission_diagnostics_require_original_live_generated_avd_and_known_phase(self):
        for dead, identity in ((True, b"owned-fixture\nOK\n"), (False, b"foreign\nOK\n"),
                               (False, b"owned-fixture\n")):
            with self.subTest(dead=dead, identity=identity), tempfile.TemporaryDirectory() as directory:
                emulator, run = Mock(), Mock(return_value=(0, identity))
                emulator.poll.return_value = 1 if dead else None
                path = Path(directory)
                ui.capture_guest_failure(run, ["owned-adb"], emulator, "owned-fixture", path, phase="permission")
                failure = json.loads((path / "permission-failure.json").read_text())
                self.assertEqual(failure["guestDiagnostics"], "NOT_CAPTURED")
                self.assertEqual(failure["captures"], [])
                self.assertEqual(run.call_count, 0 if dead else 1)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            ui.capture_guest_failure(Mock(), [], Mock(), "owned-fixture", Path(directory), phase="arbitrary")


class AndroidUiAdmissionTests(unittest.TestCase):
    def test_new_userdata_size_is_bounded_and_does_not_change_selected_image(self):
        image = "image.sysdir.1=system-images/android-37.0/google_apis/x86_64/\n"
        for old in ("", "disk.dataPartition.size=800M\n", "disk.dataPartition.size=10G\n",
                    "disk.dataPartition.size=6442450944\n"):
            with self.subTest(old=old):
                text = "AvdId=owned-fixture\n" + image + old + "hw.cpu.arch=x86_64\n"
                result = ui.configure_new_avd_userdata(text)
                self.assertEqual(result.count("disk.dataPartition.size="), 1)
                self.assertIn("disk.dataPartition.size=2G\n", result)
                self.assertEqual(result.replace("disk.dataPartition.size=2G\n", ""), text.replace(old, "") if old else text)
                self.assertIn(image, result)
        self.assertTrue(ui.configure_new_avd_userdata(image.rstrip()).endswith("\ndisk.dataPartition.size=2G\n"))

    def test_missing_duplicate_or_malformed_fresh_avd_properties_fail_closed(self):
        image = "image.sysdir.1=system-images/android-37.0/google_apis/x86_64/\n"
        size = "disk.dataPartition.size=800M\n"
        invalid = ["", size, image + image + size, "image.sysdir.1=\n" + size,
                   image + size + size, image + "disk.dataPartition.size\n",
                   image + "disk.dataPartition.size=\n", image + "disk.dataPartition.size=-1\n",
                   image + " disk.dataPartition.size=800M\n", image + "disk.dataPartition.size =800M\n",
                   image + size + " disk.dataPartition.size=2G\n"]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                ui.configure_new_avd_userdata(text)

    def test_userdata_configuration_is_only_after_fresh_avd_creation_before_launch(self):
        # Integration tripwire, not a real allocation/storage acceptance result.
        source = (ui.ROOT / "scripts/run-android-ui-validation.py").read_text()
        create = source.index('"create", "avd", "--name", avd')
        configure = source.index("config.write_text(configure_new_avd_userdata(config.read_text()))")
        launch = source.index("emulator = subprocess.Popen(")
        self.assertLess(create, configure)
        self.assertLess(configure, launch)
        self.assertIn('config = private / "avd" / avd / "config.ini"', source)
        self.assertIn('need(not (config.parent / "userdata-qemu.img").exists()', source)
        self.assertNotIn('"-wipe-data"', source)
        self.assertNotIn('"--force"', source)

    def test_both_explicit_synthetic_completed_bundles(self):
        for case in ui.CASES:
            self.assertEqual(ui.instrumentation_result(result(case), case, TOKEN)["p2pkitOutcome"], ui.PASS)

    def test_crash_partial_duplicate_wrong_token_and_scope_fail_closed(self):
        raw = result()
        invalid = [b"INSTRUMENTATION_CODE: 0\n", raw.rsplit(b"INSTRUMENTATION_CODE:", 1)[0],
                   raw.replace(b"INSTRUMENTATION_STATUS_CODE: 0", b"INSTRUMENTATION_STATUS_CODE: -2"),
                   raw + b"INSTRUMENTATION_CODE: -1\n", raw + b"INSTRUMENTATION_RESULT: p2pkitCompleted=1\n",
                   raw + b"INSTRUMENTATION_FAILED: crashed\n",
                   raw.replace(b"INSTRUMENTATION_RESULT: p2pkitCompleted=1", b"INSTRUMENTATION_RESULT: p2pkitCompleted=0")]
        invalid += [result(changes=change) for change in (
            {"p2pkitToken": "d" * 32}, {"p2pkitCompleted": "0"}, {"p2pkitOutcome": "PASS"},
            {"p2pkitCleanup": "FAIL"}, {"p2pkitEvidence": "no_backup/unowned"},
            {"class": "some.OtherRunner"}, {"p2pkitRetention": "FAIL"}, {"p2pkitFailureStage": "render"})]
        for malformed in invalid:
            with self.subTest(raw=malformed[-100:]), self.assertRaises(ValueError):
                ui.instrumentation_result(malformed, "317", TOKEN)

    def test_retained_reports_match_exact_source_and_do_not_promote_review(self):
        for case in ui.CASES:
            self.assertEqual(ui.validate_report(report(case), case, TOKEN, SOURCE, TREE)["outcome"], ui.PASS)
            for change in ({"case": "372"}, {"sourceCommit": "e" * 40}, {"declaredSourceTree": "f" * 40},
                           {"api": 37}, {"targetSdk": 36}, {"outcome": "PASS"}, {"outcome": "FAIL"}):
                with self.subTest(case=case, change=change), self.assertRaises(ValueError):
                    ui.validate_report(report(case, change), case, TOKEN, SOURCE, TREE)
        for change in ({"token": "d" * 32}, {"cleanupFailures": ["failed"]},
                       {"independentVisualAndMutationReview": "PASS"}):
            with self.assertRaises(ValueError):
                ui.validate_report(report(changes=change), "317", TOKEN, SOURCE, TREE)
        for change in ({"cleanup": []}, {"cleanup": [{"outcome": "FAIL"}]}, {"lifecycleViolation": True}):
            with self.assertRaises(ValueError):
                ui.validate_report(report("324", change), "324", TOKEN, SOURCE, TREE)

    def test_json_duplicate_cannot_override_fail(self):
        with self.assertRaises(ValueError):
            ui.decode_json(b'{"outcome":"FAIL","outcome":"HARNESS_PASS_PENDING_REVIEW"}')

    def test_only_flat_bounded_synthetic_evidence_files(self):
        raw = archive([("./", b"", tarfile.DIRTYPE), ("./result.json", report(), tarfile.REGTYPE),
                       ("./after.png", b"fixture, not an image", tarfile.REGTYPE)])
        self.assertEqual(set(ui.evidence_members(raw)), {"result.json", "after.png"})

    def test_traversal_symlink_duplicate_directory_or_missing_result_rejected(self):
        baseline = [("./result.json", report(), tarfile.REGTYPE)]
        for name, kind in (("../private", tarfile.REGTYPE), ("/private", tarfile.REGTYPE),
                           ("nested/private", tarfile.REGTYPE), ("private", tarfile.SYMTYPE),
                           ("private", tarfile.DIRTYPE), ("result.json", tarfile.REGTYPE)):
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                ui.evidence_members(archive(baseline + [(name, b"fixture", kind)]))
        with self.assertRaises(ValueError):
            ui.evidence_members(archive([]))

    def test_archive_expansion_member_size_is_bounded_before_read(self):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w") as target:
            info = tarfile.TarInfo("huge.png")
            info.size = 16 * 1024 * 1024 + 1
            # Header-only malicious declaration, not a large allocation fixture.
            target.fileobj.write(info.tobuf())
        with self.assertRaises(ValueError):
            ui.evidence_members(out.getvalue())

    def test_modeled_credential_storage_stays_outside_flat_export(self):
        # Source-integration tripwire, not a Compose/device result: nested fixture
        # storage would always make the intentional flat-only tar admission fail.
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        source = (path / "CredentialUiInstrumentation.kt").read_text()
        self.assertIn('File(app.cacheDir.canonicalFile, "ui-324-fixture-$token")', source)
        self.assertNotIn('File(directory, "fixture")', source)
        self.assertIn("check(!it.exists() && it.mkdir() && it.canonicalFile == it)", source)

    def test_setup_failure_retains_observation_without_extending_deadlines(self):
        # Source integration guard only; the encrypted owned-guest image is not
        # available to this host fixture and must still be reviewed after ART.
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        source = (path / "UiAcceptanceInstrumentation.kt").read_text()
        self.assertIn('stage = "setup-diagnostics-entry"', source)
        self.assertIn('await(5_000) { currentAppTree()?.text("Diagnostics") != null }', source)
        self.assertIn('withTimeout(25_000)', source)
        self.assertIn('val deadline = injection.end + 5_000_000_000L', source)
        self.assertIn('retainFailureObservation()', source)
        self.assertIn('newFile("failure-context.png")', source)
        self.assertIn('currentAppTree()?.let { write("failure-context-tree.json"', source)
        failure = source[source.index('private fun retainFailureObservation()'):source.index('private fun screenshot(')]
        for forbidden in ('performAction(', 'invalidate(', 'requestLayout(', 'startActivity(', 'sendStatus('):
            self.assertNotIn(forbidden, failure)

    def test_reveal_checks_plaintext_layout_separately_from_password_classification(self):
        # Pinned Compose 1.11.4 retains its initial classification after reveal.
        # Guard the corrected expectation without substituting it for pixels,
        # layout text, owner state or the original frame/deadline assertions.
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        source = (path / "CredentialUiInstrumentation.kt").read_text()
        reveal = source[source.index("private suspend fun reveal("):source.index("private suspend fun mount(")]
        self.assertIn('ui().field(label, secret, secret, true, frame)', reveal)
        self.assertIn('credential().passphrase == secret && credential().isRevealed', reveal)
        self.assertIn('ui().field(label, secret, mask(), true, frame)', source)
        self.assertIn('ui().field("restored-empty-secret", "", "", true, restoredFrame)', source)
        probe = (path / "CredentialUiProbe.kt").read_text()
        self.assertIn('it.text == visibleText && it.password == password', probe)
        self.assertIn('frame.committed.get() >= minimumFrameNanos', probe)
        self.assertIn('val targets = mutableListOf(witness.bounds)', probe)
        self.assertIn('capture(label, targets, frame, deadline)', probe)

    def test_accessibility_snapshots_clear_only_the_observer_cache(self):
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        for filename, start, end in (
            ("UiAcceptanceInstrumentation.kt", "private fun currentAppTree()", "private fun retainFailureObservation()"),
            ("CredentialUiProbe.kt", "private fun nodes()", "fun retainFailure("),
        ):
            source = (path / filename).read_text()
            reader = source[source.index(start):source.index(end)]
            self.assertEqual(reader.count(".clearCache()"), 1)
            self.assertLess(reader.index(".clearCache()"), reader.index(".rootInActiveWindow"))
            self.assertIn('check(', reader[:reader.index(".clearCache()")])
            for forbidden in ('performAction(', 'invalidate(', 'requestLayout(', 'sendPointerSync(', 'delay('):
                self.assertNotIn(forbidden, reader)

    def test_failed_only_control_changes_and_observes_the_actual_status(self):
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        fixture = (path / "CredentialUiFakes.kt").read_text()
        self.assertIn('if (outcome == Outcome.FAILED_ONLY) FAILED_ONLY_REASON else "synthetic UI324 release"', fixture)
        self.assertIn('const val FAILED_ONLY_REASON = "synthetic UI324 failed-only control"', fixture)
        source = (path / "CredentialUiInstrumentation.kt").read_text()
        control = source[source.index("private suspend fun failedJoinKeepsEditableCredential("):
                         source.index("private suspend fun typeSecret(")]
        self.assertIn('requiredStatus = "Failed: JoinFailed — ${CredentialNetworkFixture.FAILED_ONLY_REASON}"', control)
        self.assertIn('ui().field(stage, secret, mask(), true, frame,', control)
        self.assertNotIn('ui().status(', control)
        self.assertIn('vm.joinSuccessCount.value == successes && credential() === old && old.passphrase == secret', control)
        for forbidden in ('invalidate(', 'requestLayout(', 'sendPointerSync(', 'delay('):
            self.assertNotIn(forbidden, control)
        probe = (path / "CredentialUiProbe.kt").read_text()
        field = probe[probe.index("suspend fun field("):probe.index("suspend fun status(")]
        self.assertEqual(field.count('credentialAwait(deadline) {'), 1)
        self.assertIn('(requiredStatus == null || textPresent(requiredStatus))', field)
        self.assertIn('targets += Rect().also { status.getBoundsInScreen(it) }', field)

    def test_three_window_diagnostics_preserve_first_display_and_one_deadline(self):
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        source = (path / "CredentialUiProbe.kt").read_text()
        field = source[source.index("suspend fun field("):source.index("suspend fun status(")]
        self.assertEqual(field.count("+ 5_000_000_000L"), 1)
        self.assertIn("credentialAwait(deadline)", field)
        self.assertIn("credentialMain(deadline)", field)
        self.assertIn("capture(label, targets, frame, deadline)", field)
        self.assertIn("credentialRemaining(deadline)", field)
        capture = source[source.index("private fun capture("):source.index("private fun writePixels(")]
        self.assertLess(capture.index("takeScreenshot()"), capture.index("copyOwnedWindow("))
        self.assertEqual(source.count("takeScreenshot()"), 1)
        self.assertNotIn("takeScreenshot(activity.window)", source)
        self.assertIn("appWindow.id == owned.windowId && appWindow.displayId == owned.displayId", capture)
        self.assertIn("check(afterDisplay == owned)", capture)
        self.assertIn("check(afterCopy == owned)", capture)
        self.assertIn('"stop-reentry-reentered-empty", "fakegrant-true-resumed-cleared"', source)
        self.assertIn('"fakegrant-true-stopped-reentered-empty"', source)
        self.assertIn("check(windowCopies.size < 3)", source)
        copy = source[source.index("private fun copyOwnedWindow("):source.index("private data class WindowCopy(")]
        self.assertLess(copy.index("if (owner.start())"), copy.index("PixelCopy.request(owned.window"))
        self.assertIn("result.get(credentialRemaining(deadline), TimeUnit.NANOSECONDS)", copy)
        self.assertIn("check(status == PixelCopy.SUCCESS)", copy)
        self.assertIn("check(ownedWindowOnMain() == owned)", copy)
        pixels = source[source.index("private fun writePixels("):source.index("private fun ownedWindow(")]
        self.assertLess(pixels.index("bitmap.compress("), pixels.index("targets.forEach"))
        display = capture[capture.index("takeScreenshot()"):capture.index("row.put(\"pngSha256\"")]
        self.assertLess(display.index("writePixels("), display.index("credentialRemaining(deadline)"))
        self.assertIn("owner.release()", copy)
        self.assertIn("windowCopies.all { it.owner.retired() }", source)
        self.assertIn("windowCopies.forEach(WindowCopy::report)", source)
        for forbidden in ("invalidate(", "requestLayout(", "Thread.sleep(", "waitForIdleSync(",
                          "clearWindowContentFrameStats(", "SurfaceControl.Transaction", "FLAG_SECURE"):
            self.assertNotIn(forbidden, source)

    def test_task_preview_opt_out_is_api_guarded_before_first_content_not_foreground_blackout(self):
        path = ui.ROOT / "samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/MainActivity.kt"
        source = path.read_text()
        create = source[source.index("override fun onCreate("):source.index("override fun onStart(")]
        guard = "if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {"
        self.assertLess(create.index("super.onCreate("), create.index(guard))
        self.assertLess(create.index(guard), create.index("setRecentsScreenshotEnabled(false)"))
        self.assertIn(guard + "\n            setRecentsScreenshotEnabled(false)\n        }", create)
        self.assertLess(create.index("setRecentsScreenshotEnabled(false)"), create.index("setContent {"))
        self.assertEqual(source.count("setRecentsScreenshotEnabled("), 1)
        self.assertNotIn("setRecentsScreenshotEnabled(true)", source)
        self.assertNotIn("override fun onPause(", source)
        self.assertNotIn("WindowManager.LayoutParams.FLAG_SECURE", source)
        for forbidden in ("addFlags(", "setFlags(", "override fun onPause(", "setDisablePreviewScreenshots("):
            self.assertNotIn(forbidden, create)

    def test_shared_manifest_consumer_does_not_change_default_runner(self):
        source = (ui.ROOT / "scripts/run-android-art-smoke.py").read_text()
        self.assertIn('INSTRUMENTATION = PACKAGE + ".runtime.LanPermissionRuntimeInstrumentation"', source)
        self.assertNotIn("372", ui.CASES)

    def test_frame_retirement_waits_off_main_and_preserves_cleanup_failures(self):
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        probe = (path / "CredentialUiProbe.kt").read_text()
        retire = probe[probe.index("suspend fun retire()"):probe.index("class Frame(")]
        self.assertLess(retire.index("credentialAwait {"), retire.index("credentialMain {"))
        self.assertIn('frames.map { frame -> runCatching { frame.retire() } }', retire)
        self.assertIn('attempts.firstOrNull { it.isFailure }?.getOrThrow()', retire)
        self.assertIn('attempts.all { it.getOrThrow() }', retire)
        self.assertLess(retire.index('failure = error'), retire.index('activity.window.callback = originalCallback'))
        self.assertIn('failure?.let { throw it }', retire)
        self.assertIn('if (retired) registered = false', probe)
        self.assertIn('withTimeout(5_000)', probe)
        source = (path / "CredentialUiInstrumentation.kt").read_text()
        self.assertIn('withTimeout(10_000) { block() }', source)
        for forbidden in ('invalidate(', 'requestLayout(', 'Thread.sleep(', 'waitForIdleSync('):
            self.assertNotIn(forbidden, retire)


if __name__ == "__main__":
    unittest.main()
