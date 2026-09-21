#!/usr/bin/env python3
"""Fixed outer-call controls; native/service boundaries are models, never CI."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("supervisor_launch_fixtures",
    Path(__file__).with_name("hosted-cache-provider-launch-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
import hosted_cache_provider_supervisor as S

L, clocks, files = S.launch, S.launch.clocks, S.launch.files.windows_files
caught, Failure, Cancel = F.F.caught, F.F.FalseyFailure, F.F.FalseyCancellation


class SupervisorModels(unittest.TestCase):
    def setUp(self):
        self.fixture = F.LaunchSites()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.model = self.fixture.model
        self.owner = S.ProviderSupervisor()
        self.fixture.parents.append(self.owner.launch)
        self.on_wait = None
        self.model_stdout, self.model_stderr = b"MODEL_WORKER_STDOUT\x00", b"MODEL_WORKER_STDERR\r\n"
        self.fixture.outer.spawn.side_effect = self.spawn

    def tearDown(self):
        # Model-only disposal, after assertions. Not a recovery procedure for
        # UNKNOWN live providers. Earlier fixture TestCase methods never run.
        self.fixture.tearDown()
        S.QUARANTINE.clear()

    def spawn(self, *args, **kwargs):
        child = self.fixture.spawn(self.fixture.outer, *args, **kwargs)
        self.model.api.write(kwargs["stdout"].native_handle, self.model_stdout)
        self.model.api.write(kwargs["stderr"].native_handle, self.model_stderr)
        return child

    def values(self, **changes):
        result = dict(issued_ns=100 * clocks.NS, hard_end_ns=280 * clocks.NS, worker_cutoff_ns=250 * clocks.NS,
            phase="save", job="1" * 32, invocation="2" * 32, inner_invocation="4" * 32,
            plan=self.fixture.plan, node=r"C:\tools\node.exe", tool_path=r"C:\tools;C:\Windows\System32",
            cancelled=self.cancelled)
        result.update(changes)
        return result

    def cancelled(self):
        if self.owner._wait_started and self.on_wait is not None:
            self.on_wait()

    def run_owner(self, **changes):
        self.owner.take_directories(self.fixture.root, self.fixture.home)
        return self.owner.run(clocks.Reading(self.model.clock, self.model.raw), **self.values(**changes))

    def no_transcript(self):
        self.assertRegex(str(caught(lambda: self.owner.transcript)), "SUPERVISOR_TRANSCRIPT_PENDING")
        self.fixture.model.never_classifier.assert_not_called()

    def pinned(self):
        self.no_transcript()
        self.assertTrue(self.owner.unknown)
        self.assertIn(self.owner, S.QUARANTINE)
        self.assertFalse(self.owner.launch.directory._closed)
        for name in ("stdout", "stderr", "bundle", "capture_directory", "home", "directory"):
            self.assertNotIn(name, self.owner._attempted)

    def test_constructor_and_root_transfer_do_not_allocate_or_sample(self):
        before = list(self.model.events)
        self.owner.take_directories(self.fixture.root, self.fixture.home)
        self.assertEqual(self.model.events, before)
        self.fixture.scope_factory.assert_not_called()
        self.assertFalse(self.owner._started)
        self.no_transcript()

    def test_actual_launch_wait_retirement_readback_and_close_return_opaque_bytes(self):
        result = self.run_owner()
        self.assertIs(self.owner.transcript, result)
        self.assertEqual((result.worker_exit_code, result.failed), (0, False))
        self.assertEqual((result.stdout, result.stderr), (self.model_stdout, self.model_stderr))
        self.assertEqual(json.loads(result.request), self.owner.launch.frame)
        self.assertEqual(json.loads(result.native_retirement)["invocation"], "2" * 32)
        self.assertEqual(set(result.closed_resources), set(S._NAMES) - {"child"})
        self.assertEqual(result.closed_resources[0], "scope")
        self.assertEqual(result.provider_control_return, "NOT_OBSERVED")
        self.assertEqual(result.enclosing_step_outcome, "NOT_OBSERVED")
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")
        self.assertNotIn("MODEL_WORKER", repr(result))
        with self.assertRaises(FrozenInstanceError):
            result.failed = True
        self.fixture.outer.drain.assert_called_once_with(grace=5.0, kill_wait=5.0,
                                                        deadline=self.owner.launch.window.local_end)
        self.assertLess(self.owner.launch.window.local_end, 280.0)
        self.assertEqual(self.fixture.outer.job, None)
        self.assertEqual([row[1] for row in self.model.events if row[0] == "native-close"], [77, 92])

    def test_outer_and_inner_use_same_fixed_names_in_distinct_original_directories(self):
        workers = []
        self.on_wait = lambda: workers.append(self.fixture.worker(self.owner.launch)) if not workers else None
        result = self.run_owner()
        worker = workers[0]
        self.assertEqual(PureWindowsPath(self.owner.launch.stdout.path).name, "provider-stdout.log")
        self.assertNotEqual(self.owner.launch.stdout.path, worker.capture._slots["stdout"].owner.path)
        self.assertEqual(result.stdout, self.model_stdout)
        self.assertEqual(worker.capture_return.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assertEqual(result.provider_control_return, "NOT_OBSERVED")

    def test_zero_exit_and_plausible_command_text_do_not_run_provider_parser(self):
        self.model_stdout = b'{"cache-hit":"true","success":true}\n'
        with patch.object(L.cache, "provider_command_outputs", side_effect=AssertionError("MODEL_NO_PARSER")) as parser:
            result = self.run_owner(phase="lookup")
        self.assertEqual(result.stdout, self.model_stdout)
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")
        parser.assert_not_called()

    def test_windows_readback_keeps_original_writer_pinned_until_temporary_reader_closes(self):
        open_reader, closes, pairs = self.model.api.provider_log_reader, self.model.api.close, []
        def opened(parent, name):
            self.assertIn("scope", self.owner._closed)
            writer = self.owner.launch.stdout if name == "provider-stdout.log" else self.owner.launch.stderr
            original = writer.native_handle
            self.assertEqual(self.model.api.modes[original], (2, 1))
            with self.assertRaisesRegex(files.FilesystemError, "sharing"):
                self.model.api.shared_open(self.model.api.nodes[str(writer.path)], 2, 7)
            reader = open_reader(parent, name)
            pairs.append((original, reader))
            return reader
        def close(handle):
            for original, reader in pairs:
                if handle == reader:
                    self.assertIn(original, self.model.api.handles)
                elif handle == original:
                    self.assertNotIn(reader, self.model.api.handles)
            return closes(handle)
        with patch.object(self.model.api, "provider_log_reader", opened), patch.object(self.model.api, "close", close):
            self.run_owner()
        self.assertEqual(len(pairs), 2)

    def test_nonzero_worker_retains_failed_transcript_and_original_exception(self):
        self.fixture.worker_code = 19
        error = caught(self.run_owner)
        self.assertRegex(str(error), "SUPERVISOR_WORKER_FAILED")
        self.assertIs(error, self.owner._primary)
        result = self.owner.transcript
        self.assertTrue(result.failed)
        self.assertEqual((result.worker_exit_code, result.stdout), (19, self.model_stdout))
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")

    def test_cancelled_wait_keeps_original_even_with_no_exit_observation(self):
        error = Cancel("MODEL_PRIVATE_CANCEL")
        self.on_wait = lambda: (_ for _ in ()).throw(error)
        self.assertIs(caught(self.run_owner), error)
        self.owner.launch.child.poll.assert_not_called()
        result = self.owner.transcript
        self.assertEqual((result.worker_exit_code, result.failed), (None, True))
        self.assertEqual(result.stderr, self.model_stderr)
        self.fixture.outer.drain.assert_called_once()

    def test_pending_worker_is_observed_again_without_resetting_deadline(self):
        configured = []
        def setup():
            if not configured:
                configured.append(True)
                self.owner.launch.child.poll.side_effect = [None, 0]
        self.on_wait = setup
        result = self.run_owner()
        self.assertEqual(result.worker_exit_code, 0)
        self.assertEqual(self.owner.launch.child.poll.call_count, 2)
        self.assertEqual([row[1] for row in self.model.events if row[0] == "sleep"], [.025])
        self.assertLess(self.owner._worker_local_end, 250.0)
        self.assertLess(self.owner.launch.window.local_end, 280.0)

    def test_raw_cutoff_after_poll_retains_exit_but_cannot_return_success(self):
        def late():
            self.model.raw = 250 * clocks.NS
            return 0
        self.on_wait = lambda: setattr(self.owner.launch.child.poll, "side_effect", late)
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_WORKER_CUTOFF")
        self.assertEqual(self.owner.transcript.worker_exit_code, 0)
        self.assertTrue(self.owner.transcript.failed)

    def test_local_cutoff_after_cancel_callback_stops_poll_and_keeps_original_end(self):
        self.on_wait = lambda: setattr(self.model, "local", 250.0)
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_WORKER_CUTOFF")
        self.owner.launch.child.poll.assert_not_called()
        self.assertTrue(self.owner.transcript.failed)
        self.assertLess(self.fixture.outer.drain.call_args.kwargs["deadline"], 280.0)

    def test_raw_cutoff_changed_in_late_launch_frame_cannot_extend_wait(self):
        spawned = self.spawn
        def mutate(*args, **kwargs):
            child = spawned(*args, **kwargs)
            self.owner.launch.frame["workerCutoffNs"] = str(270 * clocks.NS)
            return child
        self.fixture.outer.spawn.side_effect = mutate
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_ORIGINAL_CUTOFF_CHANGED")
        self.no_transcript()
        self.owner.launch.child.poll.assert_not_called()

    def test_partial_spawn_return_failure_drains_original_scope_without_claiming_wait(self):
        error = self.fixture.fail_outer = Failure("MODEL_NATIVE_RETURN_LOST")
        self.assertIs(caught(self.run_owner), error)
        self.assertIsNone(self.owner.launch.child)
        self.assertFalse(self.owner._wait_started)
        self.fixture.outer.drain.assert_called_once()
        self.assertEqual(self.fixture.outer.job, None)
        self.assertTrue(self.owner.launch.directory._closed)
        self.no_transcript()

    def test_unreturned_scope_constructor_keeps_enclosing_owners_unknown(self):
        error = Failure("MODEL_SCOPE_CONSTRUCTOR_LOST")
        self.fixture.scope_factory.side_effect = error
        self.assertIs(caught(self.run_owner), error)
        self.fixture.outer.drain.assert_not_called()
        self.pinned()

    def unreturned_acquisition(self, name, supplier, method, wanted=None):
        acquire, error, lost = getattr(supplier, method), Failure("MODEL_UNRETURNED_" + name.upper()), []
        def opened(*args, **kwargs):
            owner = acquire(*args, **kwargs)
            if wanted is None or args[0] == wanted:
                lost.append(owner)
                self.fixture.extra.append(owner)  # Model disposal only, after assertions.
                raise error
            return owner
        with patch.object(supplier, method, side_effect=opened):
            self.assertIs(caught(self.run_owner), error)
        self.assertEqual(len(lost), 1)
        self.assertIn(name, self.owner.launch.attempted)
        self.assertIsNone(self.owner.launch._owners[name])
        self.assertEqual(self.fixture.outer.drain.call_count, int(name != "capture_directory"))
        self.pinned()

    def test_unreturned_capture_directory_keeps_root_pins(self):
        self.unreturned_acquisition("capture_directory", self.fixture.root, "create_directory")

    def test_unreturned_bundle_keeps_distinct_pins_after_original_scope_close(self):
        self.unreturned_acquisition("bundle", L, "_open_bundle")

    def test_unreturned_stdout_keeps_distinct_pins(self):
        self.unreturned_acquisition("stdout", self.fixture.root, "create_file", "provider-stdout.log")

    def test_unreturned_stderr_keeps_distinct_pins(self):
        self.unreturned_acquisition("stderr", self.fixture.root, "create_file", "provider-stderr.log")

    def test_returned_bundle_then_callback_failure_can_close_known_owners(self):
        acquire, error, returned = L._open_bundle, Failure("MODEL_KNOWN_BUNDLE_RETURN"), []
        def fail_once():
            self.model.on_raw = None
            raise error
        def opened(*args, **kwargs):
            owner = acquire(*args, **kwargs)
            returned.append(owner)
            self.model.on_raw = fail_once
            return owner
        with patch.object(L, "_open_bundle", side_effect=opened):
            self.assertIs(caught(self.run_owner), error)
        self.assertEqual(len(returned), 1)
        self.assertIs(self.owner.launch.bundle, returned[0])
        self.assertFalse(self.owner.unknown)
        self.assertIn("bundle", self.owner._closed)
        self.assertTrue(self.fixture.root._closed)
        self.no_transcript()

    def test_actual_spawn_request_is_not_reread_from_mutable_diagnostic_argv(self):
        spawn, requests = self.spawn, []
        def mutated(argv, *args, **kwargs):
            self.assertIs(type(argv), tuple)
            requests.append(argv[-1].encode("ascii"))
            child = spawn(argv, *args, **kwargs)
            self.owner.launch.worker_argv[-1] = '{"model":"not_the_invoked_request"}'
            return child
        self.fixture.outer.spawn.side_effect = mutated
        result = self.run_owner()
        self.assertEqual(requests, [result.request])
        self.assertNotEqual(result.request, self.owner.launch.worker_argv[-1].encode("ascii"))
        returned = self.owner._returned_launch
        self.assertIs(returned.child, self.owner.launch.child)
        self.assertIs(returned.request, result.request)
        with self.assertRaises(FrozenInstanceError):
            returned.request = b"MODEL_REPLACEMENT"

    def test_launch_carrier_replacement_after_wait_refuses_transcript(self):
        def mutate():
            returned = self.owner.launch._launch_return
            self.owner.launch._launch_return = L.WorkerLaunch(returned.child, returned.request)
        self.on_wait = mutate
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_ORIGINAL_OWNERS_CHANGED")
        self.pinned()

    def test_cleared_success_carrier_cannot_admit_replacement_request_before_wait(self):
        def mutate():
            if self.owner._launch_receipt is not None and not self.owner._wait_started:
                self.owner._returned_launch = None
                self.owner._request = b"MODEL_NOT_THE_ACTUAL_SPAWN_REQUEST"
        self.model.on_raw = mutate
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_ORIGINAL_LAUNCH_RETURN_CHANGED")
        self.owner.launch.child.poll.assert_not_called()
        self.pinned()

    def test_erased_unreturned_attempt_cannot_release_distinct_pins(self):
        acquire, error, lost = self.fixture.root.create_file, Failure("MODEL_ERASED_UNRETURNED_ATTEMPT"), []
        def opened(name, **kwargs):
            owner = acquire(name, **kwargs)
            if name == "provider-stderr.log":
                lost.append(owner)
                self.fixture.extra.append(owner)  # Only fixture disposal after assertions.
                self.owner.launch.attempted.remove("stderr")
                raise error
            return owner
        with patch.object(self.fixture.root, "create_file", side_effect=opened):
            self.assertIs(caught(self.run_owner), error)
        self.assertEqual(len(lost), 1)
        self.assertNotIn("stderr", self.owner.launch.attempted)
        self.assertEqual(self.owner.launch._unreturned_acquisition, "stderr")
        self.assertIsNone(self.owner.launch.stderr)
        self.fixture.outer.drain.assert_called_once()
        self.pinned()

    def test_initial_log_sync_failure_keeps_all_distinct_original_pins(self):
        sync, error = files.NativeFile.sync, Failure("MODEL_INITIAL_SYNC_FAILURE")
        def fail(writer):
            if writer is self.owner.launch.stdout and "scope" in self.owner._closed:
                raise error
            return sync(writer)
        with patch.object(files.NativeFile, "sync", fail):
            self.assertIs(caught(self.run_owner), error)
        self.pinned()

    def test_initial_log_verify_failure_keeps_all_distinct_original_pins(self):
        sync, verify, synced = files.NativeFile.sync, files.NativeFile.verify, []
        error = Failure("MODEL_INITIAL_VERIFY_FAILURE")
        def synchronized(writer):
            result = sync(writer)
            if writer is self.owner.launch.stdout and "scope" in self.owner._closed:
                synced.append(writer)
            return result
        def fail(writer):
            if any(writer is original for original in synced):
                raise error
            return verify(writer)
        with patch.object(files.NativeFile, "sync", synchronized), patch.object(files.NativeFile, "verify", fail):
            self.assertIs(caught(self.run_owner), error)
        self.assertEqual(len(synced), 1)
        self.pinned()

    def test_drain_failure_keeps_first_worker_failure_and_only_closes_original_scope(self):
        self.fixture.worker_code = 19
        self.fixture.outer.drain.side_effect = Failure("MODEL_DRAIN_UNKNOWN")
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_WORKER_FAILED")
        self.assertEqual(self.fixture.outer.job, None)
        self.pinned()

    def test_survivors_are_not_retirement(self):
        self.fixture.outer.drain.return_value = [{"pid": 41}]
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_SURVIVORS")
        self.pinned()

    def test_pending_discovery_refuses_capture_even_with_empty_survivors(self):
        self.fixture.outer.pending_discoveries = {41: {"unresolved": True}}
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_DISCOVERY_UNKNOWN")
        self.pinned()

    def test_recorded_discovery_error_refuses_capture_even_with_empty_survivors(self):
        self.fixture.outer.discovery_errors.add("MODEL_LOST_DISCOVERY")
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_DISCOVERY_UNKNOWN")
        self.pinned()

    def test_ambiguous_scope_close_attempts_once_and_does_not_release_files(self):
        error = Cancel("MODEL_JOB_CLOSE_UNKNOWN")
        def fail(handle):
            if handle == 92:
                raise error
        self.model.on_native_close = fail
        self.assertIs(caught(self.run_owner), error)
        self.assertEqual([row[1] for row in self.model.events if row == ("native-close", 92)], [92])
        self.pinned()

    def test_scope_close_raw_expiry_preserves_files_and_cannot_claim_retirement(self):
        self.model.on_native_close = lambda handle: setattr(self.model, "raw", 280 * clocks.NS) if handle == 92 else None
        self.assertRegex(str(caught(self.run_owner)), "PROVIDER_LAUNCH_EXPIRED")
        self.pinned()

    def test_scope_close_local_expiry_preserves_files_and_cannot_claim_retirement(self):
        self.model.on_native_close = lambda handle: setattr(self.model, "local", 280.0) if handle == 92 else None
        self.assertRegex(str(caught(self.run_owner)), "PROVIDER_LAUNCH_EXPIRED")
        self.pinned()

    def test_unreturned_log_reader_is_unknown_without_retry_or_distinct_closes(self):
        error = Failure("MODEL_UNRETURNED_READER")
        with patch.object(self.model.api, "provider_log_reader", side_effect=error) as opener:
            self.assertIs(caught(self.run_owner), error)
        opener.assert_called_once()
        self.pinned()

    def test_wrong_readback_size_is_staged_but_not_accepted(self):
        with patch.object(files.NativeFile, "read_provider_log", return_value=b"x"):
            self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_TRANSCRIPT_CHANGED")
        self.assertEqual(self.owner._raw["stdout"], b"x")
        self.pinned()

    def test_readback_return_crossing_raw_end_keeps_staging_unqualified(self):
        read = files.NativeFile.read_provider_log
        def late(writer):
            raw = read(writer)
            self.model.raw = 280 * clocks.NS
            return raw
        with patch.object(files.NativeFile, "read_provider_log", late):
            self.assertRegex(str(caught(self.run_owner)), "PROVIDER_LAUNCH_EXPIRED")
        self.assertEqual(self.owner._raw["stdout"], self.model_stdout)
        self.pinned()

    def test_unknown_final_writer_close_stops_remaining_distinct_owners(self):
        close, error = files.NativeFile.close, Failure("MODEL_WRITER_CLOSE_UNKNOWN")
        def fail(writer):
            if str(writer.path).endswith("provider-stderr.log"):
                raise error
            return close(writer)
        with patch.object(files.NativeFile, "close", fail):
            self.assertIs(caught(self.run_owner), error)
        self.assertIn("stderr", self.owner._attempted)
        self.assertNotIn("stdout", self.owner._attempted)
        self.assertNotIn("directory", self.owner._attempted)
        self.assertTrue(self.owner.unknown)
        self.no_transcript()

    def test_late_transcript_construction_cannot_publish_a_result(self):
        original = S.WorkerTranscript
        def late(*args):
            value = original(*args)
            self.model.raw = 280 * clocks.NS
            return value
        with patch.object(S, "WorkerTranscript", side_effect=late):
            self.assertRegex(str(caught(self.run_owner)), "PROVIDER_LAUNCH_EXPIRED")
        self.assertTrue(self.owner.launch.directory._closed)
        self.no_transcript()

    def test_mutable_staging_is_not_the_completed_return_authority(self):
        def mutate():
            if "stdout" in self.owner._raw:
                self.owner._raw["stdout"] = b"MODEL_REPLACEMENT_NOT_ORIGINAL"
        self.model.on_raw = mutate
        result = self.run_owner()
        self.assertEqual(result.stdout, self.model_stdout)
        self.assertNotEqual(result.stdout, self.owner._raw["stdout"])

    def test_late_exit_slot_substitution_cannot_replace_actual_poll_return(self):
        def mutate():
            child = self.owner.launch.child
            if child is not None and child.poll.called:
                self.owner._exit_code = 73
        self.model.on_raw = mutate
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_OBSERVATION_CHANGED")
        self.no_transcript()

    def test_late_request_substitution_cannot_replace_original_wait_input(self):
        def mutate():
            child = self.owner.launch.child
            if child is not None and child.poll.called:
                self.owner._request = b"MODEL_NOT_THE_ORIGINAL_REQUEST"
        self.model.on_raw = mutate
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_ORIGINAL_LAUNCH_RETURN_CHANGED")
        self.pinned()

    def test_live_cutoff_slot_substitution_cannot_extend_the_wait(self):
        def mutate():
            self.owner._cutoff = 275 * clocks.NS
            self.owner._worker_local_end = 275.0
            self.model.raw = 251 * clocks.NS
        self.on_wait = mutate
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_ORIGINAL_WAIT_CHANGED")
        self.owner.launch.child.poll.assert_not_called()
        self.no_transcript()

    def test_owner_substitution_does_not_close_substitute_or_accept_original(self):
        substitute = SimpleNamespace(close=Mock())
        self.on_wait = lambda: setattr(self.owner.launch, "directory", substitute)
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_ORIGINAL_OWNERS_CHANGED")
        self.assertTrue(self.owner.unknown)
        self.assertFalse(self.fixture.root._closed)
        substitute.close.assert_not_called()
        self.no_transcript()

    def test_caught_reentry_is_sticky_and_does_not_start_a_second_worker(self):
        nested = []
        def attempt():
            if not nested:
                nested.append(caught(lambda: self.owner.run(clocks.Reading(self.model.clock, self.model.raw), **self.values())))
        self.on_wait = attempt
        self.assertIs(caught(self.run_owner), nested[0])
        self.assertRegex(str(nested[0]), "SUPERVISOR_ONE_USE")
        self.fixture.outer.spawn.assert_called_once()
        self.assertTrue(self.owner.transcript.failed)

    def test_second_use_does_not_repeat_any_native_or_file_operation(self):
        self.run_owner()
        before = list(self.model.api.events), list(self.model.events)
        self.assertRegex(str(caught(lambda: self.owner.run(clocks.Reading(self.model.clock, self.model.raw),
            **self.values()))), "SUPERVISOR_ONE_USE")
        self.assertEqual((self.model.api.events, self.model.events), before)


class PosixTranscriptModels(unittest.TestCase):
    """Tiny actual file read/close; upstream launch, native scopes/clocks modeled."""
    def setUp(self):
        self.model = F.F.ProviderPosixLifecycleModels()
        self.model.setUp()
        self.owner = S.ProviderSupervisor()
        self.owner.take_directories(self.model.root, self.model.root.create_directory("home", deadline=280.0))
        self.code, self.extra = 0, []
        patch.object(L, "time", self.model.time).start()
        self.model_launch = patch.object(self.owner.launch, "start", side_effect=self.start).start()

    def tearDown(self):
        # Actual tiny fixture descriptors only; no process ever ran. Dispose
        # quarantined test objects after inspecting UNKNOWN, not as acceptance.
        self.model.raw, self.model.local = 100 * clocks.NS, 100.0
        for reader in self.owner._readers.values():
            if reader is not None:
                try:
                    reader.close()
                except BaseException:
                    pass
        for owner in self.owner.launch._owners.values():
            if owner is not None and not isinstance(owner, L.processes.PosixProcess):
                try:
                    owner.close()
                except BaseException:
                    pass
        self.model.tearDown()
        S.QUARANTINE.clear()

    def start(self, first, **values):
        # Explicit upstream model, NOT an original provider launch. Windows
        # controls above execute the actual fixed launch under supplier models.
        original = self.owner.launch
        original.window = L._Window(first, values["issued_ns"], values["hard_end_ns"], values["hard_end_ns"])
        original.frame = {"workerCutoffNs": str(values["worker_cutoff_ns"])}
        original.worker_argv = ["MODEL_LAUNCH", json.dumps(original.frame)]
        for name, value in (("capture_directory", self.model.root.create_directory("capture", deadline=280.0)),
                            ("scope", self.model.scope)):
            original._owners[name] = value
            setattr(original, name, value)
            original.attempted.add(name)
        for name in ("stdout", "stderr"):
            writer = self.model.root.create_file("provider-" + name + ".log", max_bytes=L.lifecycle.LOG_BYTES, deadline=280.0)
            original._owners[name] = writer
            setattr(original, name, writer)
            os.write(writer.fileno(), ("MODEL_POSIX_WORKER_" + name).encode())
        process = SimpleNamespace(pid=41, stdout=None, stderr=None, poll=lambda: self.code)
        child = L.processes.PosixProcess(process)
        original._owners["child"] = original.child = child
        self.model.scope.leaders.append(child)
        self.model.scope.launches.append({"api": "MODEL_NO_PROCESS", "created": True, "pid": 41})
        original.spawn_returned = True
        original._launch_return = L.WorkerLaunch(child, original.worker_argv[-1].encode("ascii"))
        return original._launch_return

    def run_owner(self):
        return self.owner.run(clocks.Reading(self.model.clock, self.model.raw), issued_ns=100 * clocks.NS,
            hard_end_ns=280 * clocks.NS, worker_cutoff_ns=250 * clocks.NS, phase="save", job="1" * 32,
            invocation="2" * 32, inner_invocation="4" * 32, plan={}, node="MODEL_NOT_EXECUTED",
            tool_path="MODEL_NOT_EXECUTED", cancelled=lambda: None)

    def test_actual_tiny_posix_transcript_readers_are_bounded_no_follow_and_closed(self):
        result = self.run_owner()
        self.assertEqual((result.stdout, result.stderr), (b"MODEL_POSIX_WORKER_stdout", b"MODEL_POSIX_WORKER_stderr"))
        readers = [row for row in self.model.opens if row[2] == "rb"]
        self.assertEqual([row[0] for row in readers], ["provider-stdout.log", "provider-stderr.log"])
        self.assertTrue(all(row[1] == os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK for row in readers))
        self.assertTrue(all(stream.closed for stream in self.model.streams))
        self.assertIn("stdout-reader", result.closed_resources)
        self.assertEqual(result.provider_control_return, "NOT_OBSERVED")
        self.assertFalse(self.owner.unknown)

    def test_nonzero_posix_worker_retains_failure_bytes_without_parser(self):
        self.code = 29
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_WORKER_FAILED")
        self.assertEqual(self.owner.transcript.worker_exit_code, 29)
        self.assertTrue(self.owner.transcript.failed)
        self.assertEqual(self.owner.transcript.stdout, b"MODEL_POSIX_WORKER_stdout")
        self.model.never_classifier.assert_not_called()

    def test_darwin_selection_uses_posix_files_without_native_execution(self):
        self.model.clock = clocks.ClockIdentity("macos-arm64", clocks.DARWIN_DOMAIN, clocks.NS)
        self.model.scope = self.model.new_scope(L.processes.DarwinScope)
        result = self.run_owner()
        self.assertIn(b'"backend":"darwin-libproc-audit-token"', result.native_retirement)
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")

    def test_symlink_replacement_refuses_without_reading_target_or_releasing_writers(self):
        target = self.model.base / "unrelated"
        target.write_bytes(b"MODEL_NEVER_READ")
        def replace(path, mode):
            if mode == "rb":
                path.unlink()
                path.symlink_to(target)
        self.model.before_open = replace
        caught(self.run_owner)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(target.read_bytes(), b"MODEL_NEVER_READ")
        self.assertNotIn("stdout", self.owner._raw)
        self.assertNotIn("stdout", self.owner._attempted)

    def test_reader_return_then_clock_failure_retains_actual_reader(self):
        def wrap(path, stream):
            self.model.raw = 280 * clocks.NS
            return stream
        self.model.reader_wrap = wrap
        self.assertRegex(str(caught(self.run_owner)), "PROVIDER_LAUNCH_EXPIRED")
        reader = self.owner._readers["stdout-reader"]
        self.assertIsNotNone(reader)
        self.assertFalse(reader.closed)
        self.assertTrue(self.owner.unknown)
        self.assertNotIn("stdout", self.owner._attempted)

    def test_truncated_posix_read_is_not_completed_evidence(self):
        self.model.reader_wrap = lambda path, stream: SimpleNamespace(fileno=stream.fileno,
            read=lambda maximum: b"", close=stream.close)
        self.assertRegex(str(caught(self.run_owner)), "SUPERVISOR_TRANSCRIPT_CHANGED")
        self.assertEqual(self.owner._raw["stdout"], b"")
        self.assertTrue(self.owner.unknown)
        self.assertRegex(str(caught(lambda: self.owner.transcript)), "SUPERVISOR_TRANSCRIPT_PENDING")

    def test_reader_close_unknown_keeps_distinct_original_writers_and_roots(self):
        error = Cancel("MODEL_READER_CLOSE_UNKNOWN")
        self.model.reader_wrap = lambda path, stream: SimpleNamespace(fileno=stream.fileno, read=stream.read,
            close=lambda: (_ for _ in ()).throw(error))
        self.assertIs(caught(self.run_owner), error)
        self.assertTrue(self.owner.unknown)
        self.assertIn("stdout-reader", self.owner._attempted)
        self.assertNotIn("stdout", self.owner._attempted)
        self.assertFalse(self.model.root.closed)


if __name__ == "__main__":
    unittest.main()
