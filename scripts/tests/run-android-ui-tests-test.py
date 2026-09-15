#!/usr/bin/env python3
"""Modeled native-adapter policy, NOT native command-format or UI admission.

Tiny owned files and substituted clock/pipe/process/guest observations only.
No SDK command, subprocess, socket, emulator, Android or archive download runs.
The unchanged artifact, collector and content suites remain separate coverage.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("android_ui_native_adapter_subject", SCRIPTS / "run-android-ui-tests.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
core = adapter.core
runner = core.load_tool("run-audit-command.py")
artifacts = core.load_tool("verify-android-acceptance-artifacts.py")

SOURCE = {"commit": "1" * 40, "tree": "2" * 40, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
TOKEN, OWNER = "3" * 32, "4" * 32
INSTALLED = {core.PACKAGE: {"uid": 10001}, core.PACKAGE + ".test": {"uid": 10002}}
IDENTITY = {"pid": 42, "uid": 10001, "package": core.PACKAGE, "startTicks": 123,
            "comm": core.PACKAGE, "state": "S", "parentPid": 1}
ACTIVITIES = ("ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n"
              "Display #0 (activities from top to bottom):\n"
              "  * Task{abc #1}\n    * Hist #0: ActivityRecord{aa u0 com.model.launcher/.Home t1}\n").encode()


def write(path, raw):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with runner.new_file(path) as stream:
        stream.write(raw)


def observation(evidence, label, raw=b"", status=0):
    out, err = evidence / (label + ".stdout"), evidence / (label + ".stderr")
    write(out, raw)
    write(err, b"")
    return {"stdout": str(out), "stderr": str(err), "exitCode": status,
            "stdoutEof": True, "stderrEof": True, "retention": "COMPLETE_STREAMS", "errors": []}


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Pipe:
    def __init__(self, descriptor, chunks):
        self.descriptor, self.chunks, self.closed = descriptor, list(chunks), False

    def fileno(self):
        return self.descriptor

    def close(self):
        self.closed = True


class Selector:
    def __init__(self):
        self.keys = {}

    def register(self, pipe, _events, data):
        self.keys[pipe.descriptor] = SimpleNamespace(fileobj=pipe, data=data)

    def unregister(self, pipe):
        del self.keys[pipe.descriptor]

    def get_map(self):
        return self.keys

    def select(self, _timeout):
        return [(key, None) for key in list(self.keys.values()) if key.fileobj.chunks]

    def close(self):
        self.keys.clear()


class InlineThread:
    """Execute only the substituted pipe/command body; creates no host thread."""
    def __init__(self, target, **_kwargs):
        self.target, self.started = target, False

    def start(self):
        self.started = True
        self.target()

    def is_alive(self):
        return False

    def join(self, _seconds):
        pass


class Modeled(unittest.TestCase):
    def patch(self, object_, name, **kwargs):
        patched = mock.patch.object(object_, name, **kwargs)
        value = patched.start()
        self.addCleanup(patched.stop)
        return value

    def setUp(self):
        self.patch(adapter.subprocess, "Popen", side_effect=AssertionError("No real subprocess allowed"))
        self.patch(adapter.subprocess, "run", side_effect=AssertionError("No real subprocess allowed"))
        self.patch(adapter.socket, "socket", side_effect=AssertionError("No real socket allowed"))
        self.clock = Clock()
        self.patch(adapter.time, "monotonic", new=self.clock)
        self.patch(adapter.time, "sleep", side_effect=self.clock.advance)
        self.patch(adapter.shutil, "disk_usage", return_value=SimpleNamespace(free=10 * adapter.GIB))
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-ui-native-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root, self.state, self.evidence = (self.base / name for name in ("source", "state", "evidence"))
        for path in (self.root, self.state, self.evidence):
            path.mkdir(mode=0o700)
        self.patch(adapter, "ROOT", new=self.root)
        self.context = {"source": SOURCE, "id": "5" * 32, "host": "macos-arm64", "root": str(self.root),
                        "gradleHome": str(self.state / "gradle-home")}

    def bare(self):
        value = object.__new__(adapter.Adapter)
        value.runner, value.state, value.evidence = runner, self.state, self.evidence
        value.context, value.owner, value.environment = self.context, OWNER, {}
        value.budget, value.artifacts = adapter.Budget(self.state), artifacts
        value.sdk, value.port, value.serial = self.base / "sdk", 45678, "emulator-5580"
        value.server = SimpleNamespace(handle=SimpleNamespace(poll=lambda: None), healthy=lambda: None)
        value.emulator = SimpleNamespace(handle=SimpleNamespace(poll=lambda: None), healthy=lambda: None)
        value.case_results, value.tools = [], {}
        value.commands = core.Commands(runner, self.evidence, self.root, {})
        value.result = {"status": "INCOMPLETE", "errors": [], "cases": value.case_results}
        value.args = SimpleNamespace(cases="317")
        value.guest, value.device_admitted = None, False
        return value

    def guest(self):
        commands = SimpleNamespace(run=mock.Mock(return_value={"model": "record"}))
        server = SimpleNamespace(poll=mock.Mock(return_value=None))
        emulator = SimpleNamespace(poll=mock.Mock(return_value=None))
        guest = adapter.Guest(commands, self.base / "sdk", 45678, "emulator-5580", server, emulator,
                              "317", TOKEN, adapter.Budget(self.state))
        return guest


class ParserTests(Modeled):
    def test_exact_selection_and_ordinary_environment(self):
        self.assertEqual(adapter.selected_cases("317+324"), ("317", "324"))
        for value in ("372", "all", "324+317", "317,324", "317+317", ""):
            with self.subTest(value=value), self.assertRaises(core.Rejected):
                adapter.selected_cases(value)
        fixture, sdk = self.base / "fixture", self.base / "sdk"
        result = adapter.private_environment({"HOME": "model-old", "ANDROID_USER_HOME": "model-old"}, fixture, sdk)
        self.assertEqual(result["HOME"], str(fixture / "home"))
        self.assertEqual(result["ANDROID_AVD_HOME"], str(fixture / "avd"))
        self.assertEqual(result["ANDROID_USER_HOME"], str(fixture / "android-user"))
        for key in ("ADB_SERVER_SOCKET", "ANDROID_SERIAL", "ADB_VENDOR_KEYS", "ANDROID_SDK_ROOT",
                    "ANDROID_SDK_HOME", "ANDROID_PREFS_ROOT", "ANDROID_LOG_TAGS", "QT_PLUGIN_PATH"):
            with self.subTest(key=key), self.assertRaisesRegex(core.Rejected, key):
                adapter.private_environment({key: "unowned"}, fixture, sdk)

    def test_properties_reject_ambiguous_or_escaped_metadata(self):
        self.assertEqual(adapter.properties(b"# model\nPkg.Revision = 1.2.3\n"), {"Pkg.Revision": "1.2.3"})
        for raw in (b"x=1\nx=1\n", b"x:a\n", b"x=\\u0041\n", b"\0x=1\n", b"# only comment\n", b""):
            with self.subTest(raw=raw), self.assertRaises(core.Rejected):
                adapter.properties(raw)

    def test_process_inventory_requires_numeric_unique_rows_and_system_witnesses(self):
        raw = ("  PID UID NAME\n 1 0 init\n 2 2000 sh\n 42 10001 " + core.PACKAGE + "\n").encode()
        self.assertEqual(adapter.process_rows(raw)[42], {"uid": 10001, "name": core.PACKAGE})
        for broken in (raw[:-1], raw.replace(b"2000", b"shell"), raw + b"42 10001 duplicate\n",
                       b"PID UID NAME\n42 10001 only-app\n", raw.replace(b"1 0", b"0 0"), b""):
            with self.subTest(raw=broken), self.assertRaises(core.Rejected):
                adapter.process_rows(broken)

    def test_proc_start_ticks_stay_separate_from_java_elapsed_start(self):
        fields = ["S"] + ["0"] * 49
        fields[1], fields[19] = "1", "12345"
        raw = ("42 (model (name)) " + " ".join(fields) + "\n").encode()
        result = adapter.proc_stat(raw, 42)
        self.assertEqual(result["startTicks"], 12345)
        self.assertEqual(result["comm"], "model (name)")
        self.assertNotIn("processStartElapsedMillis", result)
        for broken in (raw.replace(b"42 (", b"43 ("), raw[:-1], raw.replace(b"12345", b"0"),
                       raw.replace(b") S ", b") Q "), raw + b"extra\n"):
            with self.subTest(raw=broken), self.assertRaises(core.Rejected):
                adapter.proc_stat(broken, 42)
        good = b"Name:\tmodel\nUid:\t10001\t10001\t10001\t10001\n"
        self.assertEqual(adapter.proc_uid(good, 10001), 10001)
        for broken in (good + good, good[:-1], good.replace(b"10001\n", b"10002\n"), good + b"\0\n"):
            with self.subTest(raw=broken), self.assertRaises(core.Rejected):
                adapter.proc_uid(broken, 10001)

    def test_activity_absence_requires_supported_complete_nonempty_profile(self):
        result = adapter.activity_records(ACTIVITIES)
        self.assertEqual(result, [{"user": 0, "package": "com.model.launcher", "component": ".Home", "task": 1}])
        for raw in (ACTIVITIES[:-1], ACTIVITIES.replace(b"ActivityRecord{", b"ActivityRecord {"),
                    ACTIVITIES.replace(b" t1}", b" t1 unknown}"), ACTIVITIES + b"Permission Denial\n",
                    b"ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\nDisplay #0\n",
                    ACTIVITIES.split(b"  * Task")[0], b"Can't find service: activity\n"):
            with self.subTest(raw=raw), self.assertRaises(core.Rejected):
                adapter.activity_records(raw)

    def test_listener_and_memory_profiles_are_not_generic_text_success(self):
        self.assertEqual(adapter.listener_identity(b"p42\nf7\nn127.0.0.1:45678\n", 42, 45678)["descriptor"], 7)
        for raw in (b"p43\nf7\nn127.0.0.1:45678\n", b"p42\nf7\nn*:45678\n",
                    b"p42\nf7\nn127.0.0.1:45678\np43\nf8\nn127.0.0.1:45678\n", b""):
            with self.subTest(raw=raw), self.assertRaises(core.Rejected):
                adapter.listener_identity(raw, 42, 45678)
        pages = b"Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100.\nPages inactive: 200.\n"
        self.assertEqual(adapter.vm_available(pages), 300 * 16384)
        for raw in (pages + b"Pages free: 5.\n", pages.replace(b"16384", b"1024"), b"MemAvailable: 6000000 kB\n"):
            with self.subTest(raw=raw), self.assertRaises(core.Rejected):
                adapter.vm_available(raw)

    def test_owner_binds_exact_isolated_request_not_a_fictitious_timeout_field(self):
        args = SimpleNamespace(cases="317+324")
        request = ["/usr/bin/python3", "-I", "-B", "-S", "scripts/run-android-ui-tests.py", "--cases", args.cases]
        for name in ("build", "inspection", "archive"):
            setattr(args, name + "_receipt", self.state / (name + ".json"))
            setattr(args, name + "_purpose", "model-" + name)
            request += ["--" + name + "-receipt", str(getattr(args, name + "_receipt")),
                        "--" + name + "-purpose", getattr(args, name + "_purpose")]
        start = {"requestedArgv": request}  # Deliberately NO timeoutSeconds.
        with mock.patch.object(runner, "read_json", return_value=start):
            result = adapter.admit_request(runner, self.state, OWNER, args)
            self.assertEqual(result["requiredOuterSeconds"], 2100)
            self.assertIn("NOT_RECORDED", result["outerTimeoutAuthority"])
            for changed in (request + ["--trusted"], ["bash", "-c", "model"],
                            [request[0], "-B", "-I", "-S", *request[4:]]):
                start["requestedArgv"] = changed
                with self.subTest(request=changed), self.assertRaises(core.Rejected):
                    adapter.admit_request(runner, self.state, OWNER, args)


class BudgetAndOwnershipTests(Modeled):
    def test_one_episode_reserve_cancellation_and_final_deadline(self):
        budget = adapter.Budget(self.state)
        budget.room(240)
        self.clock.advance(adapter.TOTAL_SECONDS - adapter.FINAL_SECONDS)
        with self.assertRaisesRegex(core.Rejected, "body reserve"):
            budget()
        budget.finalizing = True
        budget.cancelled.append(15)
        budget.room(20)  # Cancellation cannot suppress cleanup attempts.
        self.clock.advance(adapter.FINAL_SECONDS)
        with self.assertRaisesRegex(core.Rejected, "Whole Android"):
            budget()
        budget = adapter.Budget(self.state)
        budget.cancelled.append(2)
        with self.assertRaisesRegex(core.Rejected, "cancelled"):
            budget.room(10)

    def test_disk_floor_is_checked_and_not_renewed_by_room(self):
        budget = adapter.Budget(self.state)
        with mock.patch.object(adapter.shutil, "disk_usage", return_value=SimpleNamespace(free=adapter.FREE_DISK - 1)):
            with self.assertRaisesRegex(core.Rejected, "disk reserve"):
                budget()
        self.clock.advance(adapter.TOTAL_SECONDS - adapter.FINAL_SECONDS - 5)
        with self.assertRaisesRegex(core.Rejected, "Insufficient"):
            budget.room(10)

    def test_guest_whole_phase_reduces_command_time_and_restores_after_failure(self):
        guest = self.guest()
        with guest.phase(20):
            self.clock.advance(15)
            guest.adb("model", ["shell", "model"], seconds=10)
            self.assertEqual(guest.commands.run.call_args.args[2], 5)
        self.assertIsNone(guest.phase_deadline)
        with self.assertRaisesRegex(core.Rejected, "whole-phase"):
            with guest.phase(20):
                guest.commands.run.side_effect = lambda *_args: self.clock.advance(21)
                guest.adb("model", ["shell", "model"], seconds=10)
        self.assertIsNone(guest.phase_deadline)

    def test_absolute_worker_deadline_caps_each_observer_command_without_renewal(self):
        guest = self.guest()
        deadline = self.clock() + 243
        self.clock.advance(242)
        with self.assertRaisesRegex(core.Rejected, "whole-phase"):
            with guest.until(deadline):
                self.clock.advance(0.75)
                guest.adb("art-stat", ["exec-out", "model"], seconds=10)
                self.assertEqual(guest.commands.run.call_args.args[2], 0.25)
                self.assertEqual(guest.phase_deadline, deadline)
                guest.commands.run.side_effect = lambda *_args: self.clock.advance(0.5)
                guest.adb("art-status", ["exec-out", "model"], seconds=10)
        self.assertIsNone(guest.phase_deadline)
        with self.assertRaisesRegex(core.Rejected, "no time remaining"):
            with guest.until(deadline):
                self.fail("Expired worker phase entered")

    def test_guest_refuses_dead_emulator_or_changed_server_without_querying_replacement(self):
        guest = self.guest()
        guest.emulator.poll.return_value = 0
        with self.assertRaisesRegex(core.Rejected, "emulator handle"):
            guest.adb("model", ["shell", "model"])
        guest.commands.run.assert_not_called()
        guest.emulator.poll.return_value = None
        guest.server.poll.side_effect = [None, 0]
        with self.assertRaisesRegex(core.Rejected, "replacement"):
            guest.adb("model", ["shell", "model"])

    def test_tool_inventory_bounds_hashes_empty_files_and_rejects_mutable_members(self):
        value = self.bare()
        for name in ("platform-tools/adb", "cmdline-tools/latest/bin/avdmanager"):
            write(value.sdk / name, b"model never executed")
        write(value.sdk / "platform-tools/empty", b"")
        first = value.tool_inventory()
        self.assertEqual(first["platform-tools/empty"]["bytes"], 0)
        path = value.sdk / "platform-tools/adb"
        path.write_bytes(b"changed model")
        self.assertNotEqual(first, value.tool_inventory())
        path.chmod(0o666)
        with self.assertRaisesRegex(core.Rejected, "writable"):
            value.tool_inventory()
        path.chmod(0o600)
        with mock.patch.object(adapter, "TOOL_ENTRIES", 3), self.assertRaisesRegex(core.Rejected, "bound"):
            value.tool_inventory()
        with mock.patch.object(adapter, "TOOL_BYTES", 1), self.assertRaisesRegex(core.Rejected, "byte inventory"):
            value.tool_inventory()

    def test_startup_listener_empty_exit_one_is_only_a_retry_not_ownership(self):
        value = self.bare()
        record = observation(self.evidence, "not-listening", b"", 1)
        value.commands.run = mock.Mock(return_value=record)
        process = SimpleNamespace(handle=SimpleNamespace(pid=42), healthy=mock.Mock())
        self.assertIsNone(value.listener(process, 45678, "listener", starting=True))
        with self.assertRaises(core.Rejected):
            value.listener(process, 45678, "listener")
        record["stdoutEof"] = False
        with self.assertRaisesRegex(core.Rejected, "observation"):
            value.listener(process, 45678, "listener", starting=True)

    def background(self, stdout=b"model-out", stderr=b"model-err"):
        pipes = [Pipe(7101, [stdout, b""]), Pipe(7102, [stderr, b""])]
        handle = SimpleNamespace(pid=42, stdout=pipes[0], stderr=pipes[1], exit=None)
        handle.poll = lambda: handle.exit
        self.patch(adapter.subprocess, "Popen", return_value=handle)
        self.patch(adapter.threading, "Thread", new=InlineThread)
        self.patch(adapter.selectors, "DefaultSelector", new=Selector)
        self.patch(adapter.os, "set_blocking", return_value=None)
        self.patch(adapter.os, "read", side_effect=lambda descriptor, _count:
                   next(pipe for pipe in pipes if pipe.descriptor == descriptor).chunks.pop(0))
        process = adapter.OwnedProcess(runner, self.evidence, "model", ["model-not-executed"], {}, adapter.Budget(self.state))
        return process, handle, pipes

    def test_foreground_handle_is_owned_before_start_and_needs_exit_plus_both_eof(self):
        process, handle, pipes = self.background()
        self.assertIsNone(process.handle)
        process.start()
        process.healthy()
        self.assertIs(process.handle, handle)
        self.assertTrue(all(pipe.closed for pipe in pipes))
        handle.exit = 0
        result = process.finish()
        self.assertEqual(result["retention"], "COMPLETE_STREAMS")
        self.assertTrue(result["stdoutEof"] and result["stderrEof"] and result["pumpRetired"])
        self.assertEqual(Path(result["stdout"]).read_bytes(), b"model-out")
        with self.assertRaisesRegex(core.Rejected, "already"):
            process.start()

    def test_background_overflow_keeps_original_prefix_and_cannot_become_pass(self):
        process, handle, _pipes = self.background(b"abcdef")
        with mock.patch.object(adapter, "BACKGROUND_LIMIT", 3):
            process.start()
        self.assertEqual(Path(process.record["stdout"]).read_bytes(), b"abcdef")
        handle.exit = 0
        with self.assertRaisesRegex(core.Rejected, "retire completely"):
            process.finish()
        self.assertFalse(process.record["stdoutEof"])
        self.assertEqual(process.record["retention"], "PARTIAL")

    def test_pipe_setup_failure_is_retained_and_closes_both_original_outputs(self):
        process, handle, pipes = self.background()
        with mock.patch.object(adapter.selectors, "DefaultSelector", side_effect=core.Rejected("selector-failure")):
            process.start()
        self.assertEqual(process.record["errors"][0], "Rejected: selector-failure")
        self.assertTrue(all(pipe.closed for pipe in pipes))
        self.assertTrue(all(stream.closed for stream in process.outputs.values()))
        handle.exit = 0
        with self.assertRaises(core.Rejected):
            process.finish()

    def test_failed_start_retains_original_error_and_known_handle_for_finalization(self):
        process, handle, _pipes = self.background()
        with mock.patch.object(InlineThread, "start", side_effect=core.Rejected("model-first-error")):
            with self.assertRaisesRegex(core.Rejected, "model-first-error"):
                process.start()
        self.assertIs(process.handle, handle)
        self.assertEqual(process.record["errors"][0], "Rejected: model-first-error")
        self.assertTrue((self.evidence / "model-failed-start.json").is_file())
        handle.exit = 0
        with self.assertRaisesRegex(core.Rejected, "retire completely"):
            process.finish()

    def test_startup_record_failure_does_not_mask_original_spawn_failure(self):
        process = adapter.OwnedProcess(runner, self.evidence, "model", ["model"], {}, adapter.Budget(self.state))
        with mock.patch.object(adapter.subprocess, "Popen", side_effect=core.Rejected("first")), \
                mock.patch.object(runner, "write_new_json", side_effect=OSError("second")):
            with self.assertRaisesRegex(core.Rejected, "first"):
                process.start()
        self.assertIsNone(process.handle)
        self.assertEqual(process.record["errors"], ["Rejected: first", "Failed-start retention: OSError"])

    def test_worker_invokes_exact_existing_component_and_records_command_failure(self):
        guest = self.guest()
        record = observation(self.evidence, "instrumentation", b"model")
        self.patch(adapter.threading, "Thread", new=InlineThread)
        with mock.patch.object(core, "instrument", return_value=record) as instrument:
            worker = adapter.InstrumentWorker(guest, "317", TOKEN, SOURCE)
            worker.start()
            self.assertIs(worker.finish(), record)
            instrument.assert_called_once_with(guest, "317", TOKEN, SOURCE)
        with mock.patch.object(core, "instrument", side_effect=core.Rejected("original")):
            worker = adapter.InstrumentWorker(guest, "324", TOKEN, SOURCE)
            worker.start()
            with self.assertRaisesRegex(core.Rejected, "incomplete"):
                worker.finish()
            self.assertEqual(worker.error, "Rejected: original")

    def test_worker_finish_uses_only_remaining_original_deadline(self):
        guest = self.guest()
        guest.budget.finalizing = True
        worker = adapter.InstrumentWorker(guest, "324", TOKEN, SOURCE)
        worker.deadline = self.clock() + 0.2
        worker.thread = SimpleNamespace(is_alive=lambda: True, join=self.clock.advance)
        before = self.clock()
        with self.assertRaisesRegex(core.Rejected, "unresolved"):
            worker.finish()
        self.assertLessEqual(self.clock() - before, 0.21)


class OrchestrationTests(Modeled):
    def test_failed_archive_recheck_stops_before_sdk_execution_or_guest_allocation(self):
        value = self.bare()
        value.resources = mock.Mock()
        value.args.archive_receipt, value.args.archive_purpose = self.state / "capture.json", "model-capture"
        value.tool_inventory, value.create_avd = mock.Mock(), mock.Mock()
        with mock.patch.object(core, "load_tool", return_value=SimpleNamespace()), \
                mock.patch.object(core, "intake", return_value={"bindings": {"model": "bound"}}), \
                mock.patch.object(adapter.archives, "admit_retained", side_effect=core.Rejected("changed-archive")):
            with self.assertRaisesRegex(core.Rejected, "changed-archive"):
                value.prepare()
        value.tool_inventory.assert_not_called()
        value.create_avd.assert_not_called()
        self.assertEqual(runner.read_json(self.evidence / "archive-recheck/result.json")["status"], "INCOMPLETE")

    def test_fresh_installs_without_grant_use_existing_full_installed_byte_comparator(self):
        value, guest = self.bare(), self.guest()
        value.packages = mock.Mock(return_value={"com.model.system": 1000})
        value.bundle = {"map": {"components": {role: {"apk": {"path": "model-" + role + ".apk"}}
                       for role in ("app", "test")}},
                       "apks": {role: self.root / (role + ".apk") for role in ("app", "test")}}
        value.artifacts = SimpleNamespace(verified_file=mock.Mock())
        guest.commands.run.return_value = observation(self.evidence, "install", b"Performing Streamed Install\nSuccess\n")
        with mock.patch.object(core, "installed_pair", return_value=INSTALLED) as compare:
            self.assertIs(value.install(guest, self.evidence), INSTALLED)
            compare.assert_called_once_with(guest, value.artifacts, self.root, value.bundle, self.evidence)
        self.assertEqual(guest.commands.run.call_count, 2)
        for call in guest.commands.run.call_args_list:
            argv = call.args[1]
            self.assertNotIn("-g", argv)
            self.assertEqual(argv[5:8], ["install", "--user", "0"])
        value.packages.return_value[core.PACKAGE] = 10001
        guest.commands.run.reset_mock()
        with self.assertRaisesRegex(core.Rejected, "not fresh"):
            value.install(guest, self.evidence)
        guest.commands.run.assert_not_called()

    def modeled_boot(self, failing_listener=None):
        value = self.bare()
        value.fixture = self.state / "fixtures"
        value.avd_name = "p2pkit-ui-" + OWNER
        value.resources = mock.Mock()
        calls, background = [], []

        class Reservation:
            def __enter__(this):
                return this

            def __exit__(this, *_args):
                pass

            def bind(this, address):
                calls.append(("reserve", address))

            def getsockname(this):
                return "127.0.0.1", 45678

        class Foreground:
            def __init__(this, _runner, _evidence, label, argv, environment, _budget):
                this.handle = SimpleNamespace(pid=201 + len(background), poll=lambda: None)
                this.label = label
                background.append((label, argv, dict(environment)))

            def start(this):
                calls.append(("start", this.label))

            def healthy(this):
                pass

        def listener(process, port, label, **_kwargs):
            calls.append(("listener", process.label, port))
            if label == failing_listener:
                raise core.Rejected("unsupported-listener-owner")
            return {"pid": process.handle.pid, "port": port}

        def raw(label, _argv, *_args):
            calls.append(("raw", label))
            return (b"List of devices attached\n" if label == "private-empty-server" else
                    b"List of devices attached\nemulator-5580\tdevice\n\n")

        properties = {"ro.build.version.sdk": "37", "ro.build.version.sdk_full": "37.0",
            "ro.build.version.codename": "REL", "ro.build.version.preview_sdk": "0",
            "ro.product.cpu.abi": "arm64-v8a", "ro.kernel.qemu": "1",
            "ro.system.build.fingerprint": adapter.IMAGE_FINGERPRINT,
            "ro.build.fingerprint": "model-live-fingerprint", "ro.build.version.security_patch": "2026-05-05"}

        def command(label, argv, *_args):
            calls.append(("adb", label, argv))
            raw = {"boot-state": b"1\n", "actual-avd-name": (value.avd_name + "\nOK\n").encode(),
                "guest-page-size": b"16384\n", "physical-size": b"Physical size: 1600x2560\n",
                "physical-density": b"Physical density: 200\n"}.get(label, b"")
            if label == "guest-property":
                raw = (properties[argv[-1]] + "\n").encode()
            return observation(self.evidence, "boot-" + str(len(calls)), raw)

        value.listener, value.raw = listener, raw
        value.commands.run = command
        self.patch(adapter.socket, "socket", new=Reservation)
        self.patch(adapter, "OwnedProcess", new=Foreground)
        return value, calls, background

    def test_boot_private_server_precedes_clients_and_exact_guest_identity_precedes_admission(self):
        value, calls, background = self.modeled_boot()
        value.boot()
        self.assertTrue(value.device_admitted)
        self.assertLess(calls.index(("start", "adb-server")), calls.index(("listener", "adb-server", 45678)))
        self.assertLess(calls.index(("listener", "adb-server", 45678)), calls.index(("raw", "private-empty-server")))
        self.assertEqual(background[0][1][-3:], ["tcp:127.0.0.1:45678", "nodaemon", "server"])
        self.assertEqual(background[1][0], "emulator")
        for flag in ("-no-snapshot", "-no-window", "-no-audio", "-no-metrics"):
            self.assertIn(flag, background[1][1])
        self.assertEqual(background[1][2]["ANDROID_ADB_SERVER_PORT"], "45678")
        self.assertEqual(value.serial, "emulator-5580")
        self.assertTrue((self.evidence / "guest-profile.json").is_file())

    def test_unobserved_emulator_listener_prevents_serial_admission_and_kill(self):
        value, calls, _background = self.modeled_boot("emulator-owned-console")
        with self.assertRaisesRegex(core.Rejected, "unsupported-listener"):
            value.boot()
        self.assertFalse(value.device_admitted)
        with self.assertRaisesRegex(core.Rejected, "No admitted owned"):
            value.stop_emulator()
        self.assertFalse(any(row[0:2] == ("adb", "stop-owned-emulator") for row in calls))

    def model_case(self, case="317", failure=None):
        value = self.bare()
        value.resources = mock.Mock()
        value.verifier = SimpleNamespace(POSITIVE="HARNESS_PASS_PENDING_REVIEW",
            parse_terminal=mock.Mock(return_value={"p2pkitOutcome": "HARNESS_PASS_PENDING_REVIEW"}))
        observed = []

        def install(guest, evidence):
            # Exercise the real caller's destination choice, not a copied
            # installed-byte comparator. /commands would reject these originals.
            self.assertTrue(runner.within(evidence / "app-installed.apk", guest.commands.evidence))
            return copy.deepcopy(INSTALLED)

        value.install = mock.Mock(side_effect=install)
        value.observe_art = mock.Mock(return_value=copy.deepcopy(IDENTITY))
        value.retire_art = mock.Mock(return_value={"status": "RETIRED"})
        contents = {"contentStatus": "CONSISTENT", "executionStatus": "UNPROVEN",
                    "issueAcceptance": "NOT_ACCEPTED", "visualReview": "REQUIRED"}
        self.patch(core, "retain_content_result", return_value=contents)
        original_worker_finish = adapter.InstrumentWorker.finish

        class Worker:
            def __init__(this, guest, selected, token, source):
                self.assertIsNot(guest.commands, value.commands)
                this.guest, this.record, this.done_flag, this.error = guest, None, False, None
                this.case, this.deadline = selected, None
                this.done = SimpleNamespace(is_set=lambda: this.done_flag, wait=this.wait)
                this.thread = SimpleNamespace(is_alive=lambda: failure == "worker-stalled", join=self.clock.advance)
                observed.append((selected, token, source, guest.commands.evidence))

            def start(this):
                this.deadline = self.clock() + core.CASES[this.case][1] + adapter.THREAD_SECONDS
                if failure == "worker-stalled":
                    this.guest.commands.children.append(SimpleNamespace(pid=401, poll=lambda: None))
                else:
                    this.record = observation(this.guest.commands.evidence, "model-terminal", b"model terminal\n")

            def wait(this, seconds):
                if failure == "worker-stalled":
                    self.clock.advance(seconds)
                else:
                    this.done_flag = True

            def finish(this):
                return original_worker_finish(this)

        class Collector:
            def __init__(this, _runner, guest, _verifier, evidence, selected, token, uid, phase):
                this.evidence, this.selected, this.token, this.phase = evidence, selected, token, phase
                self.assertEqual(guest.commands.evidence, evidence)
                self.assertEqual(uid, 10001)

            def collect(this):
                if failure == this.phase:
                    raise core.Rejected("model-" + this.phase)
                retained = this.evidence / this.phase / ("ui-" + this.selected + "-" + this.token)
                report = {"pid": 42, "uid": 10001, "processStartElapsedMillis": 9999}
                write(retained / "result.json", runner.json_bytes(report))
                return {"retainedRoot": str(retained), "phase": this.phase, "status": "RETAINED_STABLE_GRAPH"}

        self.patch(adapter, "InstrumentWorker", new=Worker)
        self.patch(core, "Collector", new=Collector)
        self.patch(adapter.Guest, "adb", side_effect=lambda label, _arguments, **_kwargs:
                   observation(self.evidence, "model-" + label, b"logcat\n"))
        self.patch(adapter.uuid, "uuid4", return_value=SimpleNamespace(hex=TOKEN))
        if failure == "instrument":
            value.verifier.parse_terminal.side_effect = core.Rejected("first-instrumentation-error")
        if failure == "install":
            value.install.side_effect = core.Rejected("first-install-error")
        if failure == "worker-stalled":
            def observation_near_deadline(*_args):
                self.clock.advance(core.CASES[case][1] + adapter.THREAD_SECONDS - 0.125)
                return copy.deepcopy(IDENTITY)
            value.observe_art.side_effect = observation_near_deadline
        return value, observed, contents

    def test_case_separates_worker_commands_preserves_clock_meanings_and_provisional_verdict(self):
        value, observed, contents = self.model_case()
        _guest, installed, row = value.run_case("317")
        self.assertEqual(installed, INSTALLED)
        self.assertEqual(observed, [("317", TOKEN, SOURCE, Path(row["evidence"]) / "instrumentation")])
        self.assertEqual(row["status"], "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW")
        self.assertEqual(row["processBinding"]["observedKernelIdentity"]["startTicks"], 123)
        self.assertEqual(row["processBinding"]["reportedProcessStartElapsedMillis"], 9999)
        self.assertIs(row["content"], contents)
        self.assertEqual(row["content"]["issueAcceptance"], "NOT_ACCEPTED")
        self.assertEqual([step["step"] for step in row["finally"]], ["partial-originals", "exact-art-retirement",
            "instrumentation-worker", "stable-final-originals", "guest-logcat"])
        self.assertTrue((Path(row["evidence"]) / "live-art-observations.json").is_file())

    def test_earlier_failure_cannot_be_repaired_by_successful_collection_and_teardown(self):
        value, _observed, _contents = self.model_case(failure="instrument")
        with self.assertRaisesRegex(core.Rejected, "stop before another"):
            value.run_case("317")
        row = value.case_results[0]
        self.assertEqual(row["errors"][0], "Rejected: first-instrumentation-error")
        self.assertEqual(row["artRetirement"], {"status": "RETIRED"})
        self.assertEqual(row["content"]["contentStatus"], "CONSISTENT")
        self.assertEqual(row["status"], "INCOMPLETE")
        self.assertEqual(len(row["finally"]), 5)

    def test_partial_collection_failure_still_attempts_retirement_final_capture_and_logcat(self):
        value, _observed, _contents = self.model_case(failure="before-retirement-partial")
        with self.assertRaises(core.Rejected):
            value.run_case("324")
        row = value.case_results[0]
        self.assertEqual([step["status"] for step in row["finally"]], ["FAILED", "RETURNED", "RETURNED", "RETURNED", "RETURNED"])
        self.assertEqual(row["status"], "INCOMPLETE")
        self.assertIn("Finally failed: partial-originals", row["errors"])

    def test_partial_install_never_claims_art_retirement_but_retains_failure_and_logcat(self):
        value, _observed, _contents = self.model_case(failure="install")
        with self.assertRaises(core.Rejected):
            value.run_case("317")
        row = value.case_results[0]
        self.assertEqual(row["errors"][0], "Rejected: first-install-error")
        self.assertEqual(row["artRetirement"], "UNKNOWN")
        self.assertEqual(row["finally"][-1]["status"], "RETURNED")
        value.retire_art.assert_not_called()

    def test_stalled_worker_leaves_body_at_original_deadline_retains_hold_and_stops_batch(self):
        value, _observed, _contents = self.model_case(failure="worker-stalled")
        value.args.cases = "317+324"
        value.prepare = value.boot = lambda: None
        value.between_cases = mock.Mock()
        value.stop_emulator, value.stop_server = mock.Mock(return_value=None), mock.Mock(return_value=None)
        value.emulator.finish, value.server.finish = mock.Mock(return_value=None), mock.Mock(return_value=None)
        self.patch(core, "stop_handles", return_value={"emulator": {"exitCode": 0}, "adb": {"exitCode": 0}})
        self.patch(runner, "source_snapshot", return_value=SOURCE)
        self.patch(adapter.signal, "getsignal", return_value="model-handler")
        self.patch(adapter.signal, "signal", return_value=None)
        before = self.clock()
        self.assertEqual(value.run(), 1)
        self.assertEqual(self.clock() - before, 183)
        self.assertEqual(len(value.case_results), 1)
        row = value.case_results[0]
        self.assertEqual(row["errors"][0], "Rejected: Instrumentation worker observation deadline")
        self.assertEqual(row["status"], "INCOMPLETE")
        self.assertFalse(row["instrumentationWorkerRetired"])
        self.assertEqual(row["instrumentationCommandSettlement"], [{"pid": 401, "exitCode": None}])
        self.assertEqual([step["step"] for step in row["finally"]], ["partial-originals", "exact-art-retirement",
            "instrumentation-worker", "stable-final-originals", "guest-logcat"])
        self.assertEqual(row["finally"][2]["status"], "FAILED")
        value.between_cases.assert_not_called()
        for action in (value.stop_emulator, value.stop_server, value.emulator.finish, value.server.finish):
            action.assert_called_once()

    def test_retirement_never_turns_failed_inventory_or_unsupported_activity_into_absence(self):
        value, guest = self.bare(), self.guest()
        value.installed_uids = mock.Mock()
        value.inventory = mock.Mock(side_effect=core.Rejected("query failed"))
        with self.assertRaisesRegex(core.Rejected, "query failed"):
            value.retire_art(guest, INSTALLED, IDENTITY)
        guest.commands.run.assert_not_called()
        value.inventory.side_effect = None
        value.inventory.return_value = {1: {"uid": 0}, 2: {"uid": 2000}}
        response = observation(self.evidence, "bad-activities", b"unknown service format\n")
        with mock.patch.object(guest, "adb", return_value=response):
            with self.assertRaisesRegex(core.Rejected, "Activity inventory"):
                value.retire_art(guest, INSTALLED, None)

    def test_retirement_two_supported_absence_observations_and_whole_phase_cap(self):
        value, guest = self.bare(), self.guest()
        value.installed_uids = mock.Mock()
        value.inventory = mock.Mock(return_value={1: {"uid": 0}, 2: {"uid": 2000}})
        response = observation(self.evidence, "activities", ACTIVITIES)
        guest.commands.run.return_value = response
        result = value.retire_art(guest, INSTALLED, None)
        self.assertEqual(result["status"], "RETIRED")
        self.assertEqual(len(result["snapshots"]), 2)
        self.assertIsNone(guest.phase_deadline)
        value.installed_uids.side_effect = lambda *_args: self.clock.advance(21)
        with self.assertRaisesRegex(core.Rejected, "phase"):
            value.retire_art(guest, INSTALLED, None)

    def test_live_art_identity_changes_are_failures_not_process_adoption(self):
        value, guest = self.bare(), self.guest()
        value.inventory = mock.Mock(return_value={42: {"uid": 10001, "name": core.PACKAGE}})
        fields = ["S"] + ["0"] * 49
        fields[1], fields[19] = "1", "123"
        raws = [("42 (model) " + " ".join(fields) + "\n").encode(),
                b"Uid:\t10001\t10001\t10001\t10001\n", core.PACKAGE.encode() + b"\0"]
        raws.append(raws[0])
        responses = [observation(self.evidence, "proc-" + str(index), raw) for index, raw in enumerate(raws)]
        guest.commands.run.side_effect = responses
        actual = value.observe_art(guest, INSTALLED, IDENTITY)
        self.assertEqual(actual["startTicks"], 123)
        guest.commands.run.side_effect = responses
        with self.assertRaisesRegex(core.Rejected, "identity changed"):
            value.observe_art(guest, INSTALLED, {**IDENTITY, "startTicks": 124})
        value.inventory.return_value[43] = {"uid": 10002, "name": "unexpected-test"}
        with self.assertRaisesRegex(core.Rejected, "Unexpected process"):
            value.observe_art(guest, INSTALLED, None)

    def test_between_cases_requires_retained_retired_success_then_actual_uninstall_absence(self):
        value, guest = self.bare(), self.guest()
        row = {"case": "317", "evidence": str(self.evidence), "status": "INCOMPLETE"}
        with self.assertRaisesRegex(core.Rejected, "shared-guest reuse"):
            value.between_cases(guest, INSTALLED, row)
        guest.commands.run.assert_not_called()
        row.update(status="CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW", artRetirement={"status": "RETIRED"},
                   content={"contentStatus": "CONSISTENT"})
        value.installed_uids = mock.Mock()
        value.packages = mock.Mock(return_value={"com.model.system": 1000})
        value.inventory = mock.Mock(return_value={1: {"uid": 0}})
        guest.commands.run.return_value = observation(self.evidence, "uninstall", b"Success\n")
        value.between_cases(guest, INSTALLED, row)
        self.assertEqual(guest.commands.run.call_count, 2)
        self.assertEqual(value.packages.call_count, 1)
        value.packages.return_value[core.PACKAGE] = 10001
        with self.assertRaisesRegex(core.Rejected, "Packages remain"):
            value.between_cases(guest, INSTALLED, row)

    def test_unadmitted_serial_is_never_sent_emulator_kill(self):
        value = self.bare()
        value.guest = SimpleNamespace(adb=mock.Mock())
        with self.assertRaisesRegex(core.Rejected, "No admitted owned"):
            value.stop_emulator()
        value.guest.adb.assert_not_called()

    def model_run(self, failure=None):
        value = self.bare()
        order = []
        value.args.cases = "317+324"
        value.prepare = lambda: order.append("prepare")
        value.boot = lambda: order.append("boot")
        value.tool_inventory = lambda: {}
        value.resources = lambda label: order.append(label)

        def run_case(case):
            order.append("case-" + case)
            if failure == case:
                raise core.Rejected("original-case-" + case)
            row = {"case": case, "status": "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW"}
            value.case_results.append(row)
            return None, None, row

        value.run_case = run_case
        value.between_cases = lambda *_args: order.append("fresh-install-fence")
        value.stop_emulator = lambda: order.append("stop-emulator")
        value.stop_server = lambda: order.append("stop-server")
        value.emulator.finish = lambda: order.append("emulator-streams")
        value.server.finish = lambda: order.append("server-streams")
        self.patch(core, "stop_handles", side_effect=lambda _handles: order.append("both-handle-waits") or
                   {"emulator": {"exitCode": 0}, "adb": {"exitCode": 0}})
        self.patch(runner, "source_snapshot", return_value=SOURCE)
        self.patch(adapter.signal, "getsignal", return_value="model-handler")
        self.patch(adapter.signal, "signal", side_effect=lambda number, handler: order.append((number, handler)))
        return value, order

    def test_one_guest_batch_stops_before_next_install_after_failure_and_attempts_all_shutdowns(self):
        value, order = self.model_run(failure="317")
        value.stop_emulator = lambda: (_ for _ in ()).throw(core.Rejected("shutdown-error"))
        self.assertEqual(value.run(), 1)
        self.assertEqual(value.result["errors"][0], "Rejected: original-case-317")
        self.assertNotIn("case-324", order)
        self.assertNotIn("fresh-install-fence", order)
        self.assertTrue(all(item in order for item in ("stop-server", "both-handle-waits", "emulator-streams", "server-streams")))
        self.assertIn("Finally failed: emulator-shutdown", value.result["errors"])

    def test_positive_batch_requires_all_cases_fence_and_keeps_provisional_label(self):
        value, order = self.model_run()
        self.assertEqual(value.run(), 0)
        self.assertEqual(value.result["status"], "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW")
        self.assertLess(order.index("case-317"), order.index("fresh-install-fence"))
        self.assertLess(order.index("fresh-install-fence"), order.index("case-324"))
        self.assertLess(order.index("stop-server"), order.index("both-handle-waits"))
        self.assertEqual(value.result["sourceAfter"], SOURCE)

    def test_prepare_failure_with_no_owned_handles_does_not_touch_unrelated_processes(self):
        value, order = self.model_run()
        value.server = value.emulator = None
        value.prepare = lambda: (_ for _ in ()).throw(core.Rejected("original-admission-error"))
        self.assertEqual(value.run(), 1)
        self.assertEqual(value.result["errors"][0], "Rejected: original-admission-error")
        self.assertEqual(value.result["finally"], [])
        self.assertTrue(all(item not in order for item in ("stop-server", "stop-emulator", "both-handle-waits")))

    def test_cancellation_final_deadline_and_unknown_handle_each_prevent_success(self):
        value, _order = self.model_run()
        value.resources = lambda _label: value.budget.cancelled.append(15)
        self.assertEqual(value.run(), 1)
        self.assertEqual(value.result["cancelledSignals"], [15])
        # A new evidence namespace is required for a second modeled episode.
        self.evidence = self.base / "second-evidence"
        self.evidence.mkdir(mode=0o700)
        value, _order = self.model_run()
        value.server.finish = lambda: self.clock.advance(adapter.TOTAL_SECONDS + 1)
        self.assertEqual(value.run(), 1)
        self.assertTrue(any("episode deadline" in error for error in value.result["errors"]))
        self.evidence = self.base / "third-evidence"
        self.evidence.mkdir(mode=0o700)
        value, _order = self.model_run()
        with mock.patch.object(core, "stop_handles", return_value={"emulator": {"error": "not retired"}, "adb": {"exitCode": 0}}):
            self.assertEqual(value.run(), 1)
        self.assertIn("Finally failed: foreground-handle-waits", value.result["errors"])

    def modeled_signals(self):
        normal = {adapter.signal.SIGINT: adapter.signal.default_int_handler, adapter.signal.SIGTERM: adapter.signal.SIG_DFL}
        handlers = dict(normal)

        def replace(number, handler):
            previous, handlers[number] = handlers[number], handler
            return previous

        self.patch(adapter.signal, "getsignal", side_effect=lambda number: handlers[number])
        self.patch(adapter.signal, "signal", side_effect=replace)
        return handlers, normal, replace

    def test_signal_during_final_disk_observation_cannot_commit_captured_or_exit_zero(self):
        value, order = self.model_run()
        handlers, normal, _replace = self.modeled_signals()
        injected = []

        def disk(_path):
            self.assertTrue(value.budget.finalizing)
            self.assertFalse(injected)
            injected.append(adapter.signal.SIGTERM)
            handlers[adapter.signal.SIGTERM](adapter.signal.SIGTERM, None)
            return SimpleNamespace(free=10 * adapter.GIB)

        with mock.patch.object(adapter.shutil, "disk_usage", side_effect=disk):
            self.assertEqual(value.run(), 1)
        self.assertEqual(injected, [adapter.signal.SIGTERM])
        self.assertEqual(handlers, normal)
        self.assertEqual(value.result["cancelledSignals"], [adapter.signal.SIGTERM])
        self.assertEqual(value.result["status"], "INCOMPLETE")
        self.assertIn("Android UI episode cancelled before result commit", value.result["errors"])
        self.assertTrue(all(item in order for item in ("stop-emulator", "stop-server", "both-handle-waits")))

    def test_signal_during_handler_restoration_is_retained_before_success_decision(self):
        value, _order = self.model_run()
        handlers, normal, replace = self.modeled_signals()

        def restore(number, handler):
            if number == adapter.signal.SIGINT and handler is normal[number]:
                handlers[adapter.signal.SIGTERM](adapter.signal.SIGTERM, None)
            return replace(number, handler)

        with mock.patch.object(adapter.signal, "signal", side_effect=restore):
            self.assertEqual(value.run(), 1)
        self.assertEqual(handlers, normal)
        self.assertEqual(value.result["cancelledSignals"], [adapter.signal.SIGTERM])
        self.assertEqual(value.result["status"], "INCOMPLETE")

    def test_restored_normal_interrupt_propagates_during_result_retention(self):
        value, _order = self.model_run()
        handlers, normal, _replace = self.modeled_signals()

        def interrupted_write(_path, _result):
            self.assertEqual(handlers, normal)
            handlers[adapter.signal.SIGINT](adapter.signal.SIGINT, None)
            self.fail("Normal interrupt was swallowed")

        value.write = interrupted_write
        with self.assertRaises(KeyboardInterrupt):
            value.run()

    def test_finally_report_failure_does_not_skip_later_native_shutdown_attempts(self):
        value, order = self.model_run()
        original = runner.write_new_json

        def fail_once(path, content):
            if path.name == "finally-emulator-shutdown.json":
                raise OSError("model unavailable evidence file")
            return original(path, content)

        with mock.patch.object(runner, "write_new_json", side_effect=fail_once):
            self.assertEqual(value.run(), 1)
        self.assertTrue(all(item in order for item in ("stop-server", "both-handle-waits", "server-streams")))
        self.assertIn("Finally failed: emulator-shutdown", value.result["errors"])


if __name__ == "__main__":
    unittest.main()
