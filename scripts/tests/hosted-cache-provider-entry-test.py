#!/usr/bin/env python3
"""Offline actual-entry controls: native/service/signal models, no child launch.

Cold-loader methods execute definitions only, rejecting the frame before native
acquisition. Real files are tiny source fixtures, never provider or key material.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("entry_outer_fixtures",
    Path(__file__).with_name("hosted-cache-provider-supervisor-return-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
import hosted_cache_provider_entry as E
import hosted_cache_provider_worker as W

L, S, T, clocks, caught = F.L, F.S, F.T, F.clocks, F.caught


class Signals:
    SIGINT, SIGTERM, SIGBREAK = 2, 15, 21

    def __init__(self):
        self.original = {number: object() for number in (2, 15, 21)}
        self.current = self.original.copy()
        self.sets = []
        self.receiver = None
        self.before_set = self.after_set = lambda number, value: None

    def getsignal(self, number):
        return self.current[number]

    def signal(self, number, value):
        self.before_set(number, value)
        old = self.current[number]
        self.current[number] = value
        self.sets.append((number, value))
        if value is not self.original[number]:
            self.receiver = value
        self.after_set(number, value)
        return old

    def emit(self):
        self.receiver(self.SIGTERM, None)


class EntryModels(unittest.TestCase):
    def setUp(self):
        self.base = F.SendModels()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.model, self.fixture = self.base.model, self.base.base.fixture
        self.signals = Signals()
        self.patch(E, "signal", self.signals)
        self.context = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": self.model.clock.role,
            "frequency": self.model.clock.ticks_per_second, "firstNs": str(self.model.raw),
            "issuedNs": str(100 * clocks.NS), "hardEndNs": str(280 * clocks.NS), "workerCutoffNs": str(250 * clocks.NS),
            "phase": "save", "job": "1" * 32, "outerId": "2" * 32, "innerId": "4" * 32,
            "directory": str(self.fixture.root.path), "directoryIdentity": list(self.fixture.root.identity),
            "home": str(self.fixture.home.path), "homeIdentity": list(self.fixture.home.identity),
            "node": r"C:\tools\node.exe", "toolPath": r"C:\tools;C:\Windows\System32", "plan": self.fixture.plan}
        self.raw = L._json(self.context).encode("ascii")
        # Borrow the existing native/pipe fixture's original supervisor, not a
        # fabricated return/receipt. Actual entry/run/send/classifier code runs.
        with patch.object(S, "ProviderSupervisor", return_value=self.base.owner):
            self.entry = E._SupervisorEntry(self.raw)
        self.opens = []
        original = L._open_directory
        def opened(path, role):
            value = original(path, role)
            self.opens.append(value)
            return value
        self.open_directory = self.patch(L, "_open_directory", Mock(side_effect=opened))

    def patch(self, obj, name, value):
        binding = patch.object(obj, name, value)
        result = binding.start()
        self.addCleanup(binding.stop)
        return result

    def tearDown(self):
        self.fixture.extra.extend(self.opens)  # Model disposal only, after assertions.
        self.base.tearDown()
        E.QUARANTINE.clear()

    def call(self):
        with patch.object(W, "bootstrap", return_value=self.entry), \
                patch.object(sys, "argv", ["fixed", "--supervisor", "{}", self.raw.decode("ascii")]):
            return W.main()

    def incomplete(self, *, pinned=False):
        self.assertEqual(self.call(), 66)
        self.assertIsNone(self.entry._completed)
        if pinned:
            self.assertTrue(self.entry._unknown or self.entry.owner.unknown)
            self.assertFalse(self.entry.roots["directory"]._closed)
        return self.entry._primary

    def test_constructor_is_inert_and_does_not_install_handlers_or_open_roots(self):
        self.assertEqual(self.signals.sets, [])
        self.open_directory.assert_not_called()
        self.fixture.scope_factory.assert_not_called()

    def test_success_owns_original_roots_handlers_and_matching_ack_then_classifies_once(self):
        self.assertEqual(self.call(), 0)
        self.assertEqual(self.signals.current, self.signals.original)
        self.assertEqual([n for n, _ in self.signals.sets], [2, 15, 21, 21, 15, 2])
        self.assertTrue(all(root._closed for root in self.entry.roots.values()))
        self.assertEqual(len(self.base.sink.writes), 1)
        ack = T.read_ack(self.base.sink.writes[0], self.raw, 0)
        self.assertEqual(ack.provider_acceptance, "NOT_ESTABLISHED")
        self.assertIs(self.entry.owner.launch.window, self.entry.window)
        self.assertIs(self.entry.window.first, self.entry.first)
        self.assertIsNotNone(caught(lambda: self.entry.exit_code(self.entry._completed.result, None)))

    def test_root_acquisition_time_cannot_reconstruct_or_renew_original_window(self):
        original_init, instances = L._Window.__init__, []
        def init(window, *args):
            original_init(window, *args)
            instances.append((window, window.local_end))
        original_open = self.open_directory.side_effect
        def opened(*args):
            value = original_open(*args)
            self.model.local += 2
            self.model.raw += 2 * clocks.NS
            return value
        self.open_directory.side_effect = opened
        with patch.object(L._Window, "__init__", init):
            self.assertEqual(self.call(), 0)
        self.assertEqual(len(instances), 1)
        self.assertIs(instances[0][0], self.entry.owner.launch.window)
        self.assertEqual(instances[0][1], self.entry.window.local_end)

    def test_expired_initial_window_refuses_before_signals_and_roots(self):
        self.model.raw = 280 * clocks.NS
        self.incomplete()
        self.assertEqual(self.signals.sets, [])
        self.open_directory.assert_not_called()

    def test_mismatching_actual_clock_refuses_before_roots(self):
        self.model.clock = clocks.ClockIdentity("linux-x64", clocks.LINUX_DOMAIN, clocks.NS)
        self.incomplete()
        self.open_directory.assert_not_called()

    def test_expiry_after_first_root_return_retains_that_original_and_refuses_next_open(self):
        original = self.open_directory.side_effect
        def opened(*args):
            value = original(*args)
            self.model.raw = 280 * clocks.NS
            return value
        self.open_directory.side_effect = opened
        self.incomplete(pinned=True)
        self.assertIs(self.entry.roots["directory"], self.opens[0])
        self.assertEqual(len(self.opens), 1)
        self.fixture.scope_factory.assert_not_called()

    def test_lost_home_acquisition_pins_the_distinct_returned_root(self):
        original = self.open_directory.side_effect
        failure = F.Failure("MODEL_UNRETURNED_HOME")
        def opened(*args):
            value = original(*args)
            if args[0] == self.context["home"]:
                raise failure
            return value
        self.open_directory.side_effect = opened
        self.assertIs(self.incomplete(pinned=True), failure)
        self.assertIsNone(self.entry.roots["home"])
        self.assertEqual(self.base.sink.writes, [])

    def test_none_home_return_is_unknown_not_permission_to_close_the_distinct_root(self):
        original = self.open_directory.side_effect
        self.open_directory.side_effect = lambda *args: None if args[0] == self.context["home"] else original(*args)
        self.incomplete(pinned=True)
        self.assertIsNone(self.entry.roots["home"])

    def test_wrong_original_root_identity_never_launches(self):
        self.entry.context["directoryIdentity"] = [1, "f" * 32]
        self.incomplete()
        self.fixture.scope_factory.assert_not_called()
        self.open_directory.assert_not_called()  # Canonical request binding already differs.

    def test_replaced_returned_root_cannot_be_transferred(self):
        original = self.open_directory.side_effect
        def opened(*args):
            value = original(*args)
            self.model.on_raw = lambda: self.entry.roots.update(directory=SimpleNamespace(close=Mock()))
            return value
        self.open_directory.side_effect = opened
        self.incomplete()
        self.assertTrue(self.entry._unknown)
        self.assertFalse(self.opens[0]._closed)
        self.fixture.scope_factory.assert_not_called()

    def test_signal_install_after_effect_failure_restores_all_attempted_originals(self):
        failure = F.Failure("MODEL_INSTALL_AFTER_EFFECT")
        self.signals.after_set = lambda number, value: (_ for _ in ()).throw(failure) if (
            number == 15 and value is not self.signals.original[number]) else None
        self.assertIs(self.incomplete(), failure)
        self.assertEqual(self.signals.current, self.signals.original)
        self.open_directory.assert_not_called()

    def test_cancellation_before_roots_is_cooperative_and_restores_handlers(self):
        self.signals.after_set = lambda number, value: self.signals.emit() if (
            value is not self.signals.original[number]) else None
        self.assertIs(self.incomplete(), self.entry._cancellation)
        self.open_directory.assert_not_called()
        self.assertEqual(self.signals.current, self.signals.original)

    def test_cancellation_after_launch_still_drains_and_returns_known_failed_transport(self):
        original = self.fixture.outer.spawn.side_effect
        def spawn(*args, **values):
            child = original(*args, **values)
            self.signals.emit()
            return child
        self.fixture.outer.spawn.side_effect = spawn
        self.assertEqual(self.call(), 65)
        self.assertIs(self.entry._primary, self.entry._cancellation)
        self.fixture.outer.drain.assert_called_once()
        self.assertTrue(all(root._closed for root in self.entry.roots.values()))
        self.assertEqual(self.signals.current, self.signals.original)
        self.assertEqual(T.read_ack(self.base.sink.writes[0], self.raw, 65).kind, "failed")

    def test_known_nonzero_worker_remains_failed_not_success(self):
        self.fixture.worker_code = 29
        self.assertEqual(self.call(), 65)
        self.assertIs(self.entry._primary, self.entry.owner._completion.error)
        self.model.never_classifier.assert_not_called()

    def test_late_signal_during_ack_flush_requires66_even_if_success_ack_escaped(self):
        self.base.sink.on_flush = self.signals.emit
        self.incomplete()
        self.assertEqual(len(self.base.sink.writes), 1)
        self.assertEqual(self.signals.current, self.signals.original)

    def test_signal_during_original_handler_restore_refuses_completed_wrapper(self):
        self.signals.after_set = lambda number, value: self.signals.emit() if (
            value is self.signals.original[number]) else None
        self.incomplete()
        self.assertEqual(len(self.base.sink.writes), 1)
        self.assertEqual(self.signals.current, self.signals.original)

    def test_handler_restore_failure_cannot_relabel_ack_as_completed_entry(self):
        failure = F.Failure("MODEL_RESTORE")
        self.signals.before_set = lambda number, value: (_ for _ in ()).throw(failure) if (
            number == 15 and value is self.signals.original[number]) else None
        self.assertIs(self.incomplete(), failure)
        self.assertTrue(self.entry._unknown)
        self.assertIs(self.signals.current[2], self.signals.original[2])

    def test_failed_worker_keeps_first_error_when_handler_restore_also_fails(self):
        self.fixture.worker_code = 29
        self.signals.before_set = lambda number, value: (_ for _ in ()).throw(F.Failure("MODEL_RESTORE")) if (
            value is self.signals.original[number]) else None
        self.assertIs(self.incomplete(), self.entry.owner._completion.error)

    def test_changed_handler_is_refused_but_original_restoration_is_still_attempted(self):
        self.base.sink.on_flush = lambda: self.signals.current.update({15: object()})
        self.incomplete()
        self.assertTrue(self.entry._unknown)
        self.assertEqual(self.signals.current, self.signals.original)

    def test_successfully_installed_handler_replaced_by_previous_is_not_an_unfinished_install(self):
        self.base.sink.on_flush = lambda: self.signals.current.update({15: self.signals.original[15]})
        self.incomplete()
        self.assertTrue(self.entry._unknown)
        self.assertEqual(self.signals.current, self.signals.original)
        self.assertEqual([n for n, _ in self.signals.sets], [2, 15, 21, 21, 15, 2])

    def test_restore_checks_the_actual_displaced_handler_not_only_the_final_value(self):
        self.signals.before_set = lambda number, value: self.signals.current.update({number: object()}) if (
            number == 15 and value is self.signals.original[number]) else None
        self.incomplete()
        self.assertTrue(self.entry._unknown)
        self.assertEqual(self.signals.current, self.signals.original)
        self.assertEqual([n for n, _ in self.signals.sets], [2, 15, 21, 21, 15, 2])

    def late_final_handler_query(self, effect):
        classify, query = self.entry.owner.exit_code, self.signals.getsignal
        counts = {"armed": False, "reads": 0, "effects": 0}
        def classified(*args):
            value = classify(*args)
            counts["armed"] = True
            return value
        def queried(number):
            value = query(number)
            if counts["armed"]:
                counts["reads"] += 1
                if counts["reads"] == 6:
                    counts["effects"] += 1
                    effect()
            return value
        with patch.object(self.entry.owner, "exit_code", classified), \
                patch.object(self.signals, "getsignal", queried):
            self.assertEqual(self.call(), 66)
        self.assertEqual(counts["effects"], 1)
        self.assertEqual(len(self.base.sink.writes), 1)
        self.assertIsNotNone(self.entry._primary)
        # A now-invalid completed wrapper cannot be retried as an exit receipt.
        self.assertIsNotNone(caught(lambda: self.entry.exit_code(self.entry._completed.result, None)))

    def test_cancellation_in_last_post_classification_handler_getter_requires66(self):
        self.late_final_handler_query(self.signals.emit)
        self.assertTrue(self.entry._signalled)

    def test_local_expiry_in_last_post_classification_handler_getter_requires66(self):
        self.late_final_handler_query(lambda: setattr(self.model, "local", 280.0))
        self.assertGreaterEqual(self.model.local, self.entry.window.local_end)

    def test_expiry_during_last_handler_restore_prevents_completed_entry(self):
        self.signals.after_set = lambda number, value: setattr(self.model, "local", 280.0) if (
            number == 2 and value is self.signals.original[number]) else None
        self.incomplete()
        self.assertEqual(len(self.base.sink.writes), 1)

    def test_equal_replacement_first_reading_cannot_replace_transferred_window_origin(self):
        original = self.open_directory.side_effect
        def opened(*args):
            value = original(*args)
            self.entry.window.first = replace(self.entry.first)
            return value
        self.open_directory.side_effect = opened
        self.incomplete()
        self.fixture.scope_factory.assert_not_called()

    def test_swallowed_entry_reentry_is_sticky_before_any_next_acquisition(self):
        nested = []
        def reenter():
            if self.entry.window is not None and not nested:
                nested.append(caught(self.entry.run))
        self.model.on_raw = reenter
        self.assertIs(self.incomplete(), nested[0])
        self.open_directory.assert_not_called()

    def test_late_completion_constructor_cannot_publish_completed_wrapper(self):
        original = E._EntryReturn
        def late(*args):
            value = original(*args)
            self.model.raw = 280 * clocks.NS
            return value
        with patch.object(E, "_EntryReturn", side_effect=late):
            self.incomplete()

    def test_wrong_actual_return_is_not_replayable_as_original_success(self):
        result = self.entry.run()
        self.assertIsNotNone(caught(lambda: self.entry.exit_code(replace(result), None)))
        self.assertIsNotNone(caught(lambda: self.entry.exit_code(result, None)))

    def test_late_exit_cannot_be_retried_after_clock_restore(self):
        result = self.entry.run()
        self.model.raw = 280 * clocks.NS
        error = caught(lambda: self.entry.exit_code(result, None))
        self.model.raw = 100 * clocks.NS
        self.assertIs(caught(lambda: self.entry.exit_code(result, None)), error)

    def test_system_exit0_without_original_completed_run_cannot_mint_success(self):
        with patch.object(self.entry.owner, "run_and_send", side_effect=SystemExit(0)):
            self.assertEqual(self.call(), 66)
        self.assertEqual(self.base.sink.writes, [])

    def test_normal_return_without_original_send_receipt_cannot_mint_success(self):
        with patch.object(self.entry.owner, "run_and_send", return_value=None):
            self.assertEqual(self.call(), 66)
        self.assertEqual(self.base.sink.writes, [])


class FixedOuterLoader(unittest.TestCase):
    def cold(self, role, *, mutate_argv=False):
        with tempfile.TemporaryDirectory() as path:
            root, bindings = Path(path), {}
            for name in W.outer_names(role):
                raw = (SCRIPTS / (name + ".py")).read_bytes()
                if mutate_argv and name == "hosted_primary_abi":
                    raw += b"\nimport sys\nsys.argv[-1] = '{}'\n"
                (root / (name + ".py")).write_bytes(raw)
                bindings[name] = hashlib.sha256(raw).hexdigest()
            (root / "uuid.py").write_text("raise AssertionError('MODEL_UNHASHED_IMPORT')\n")
            argv = [str(root / "hosted_cache_provider_worker.py"), "--supervisor", json.dumps(bindings),
                    L._json({"role": role})]
            original_path, path_values = sys.path, tuple(sys.path)
            with patch.dict(sys.modules), patch.object(W, "__file__", argv[0]), patch.object(sys, "argv", argv), \
                    patch.object(sys, "path", list(path_values)):
                saved_path = sys.path
                for name in (*W.NAMES, *W.OUTER_NAMES, "uuid"):
                    sys.modules.pop(name, None)
                expected = "^PROVIDER_WORKER_SOURCE_REFUSED$" if mutate_argv else "^PROVIDER_RETURN_CONTEXT$"
                with self.assertRaisesRegex(RuntimeError, expected):
                    W.bootstrap()  # Never run(): invalid frame stops before native clocks/roots.
                self.assertIs(sys.path, saved_path)
                self.assertEqual(tuple(sys.path), path_values)
                if not mutate_argv:
                    for name in W.outer_names(role):
                        self.assertEqual(Path(sys.modules[name].__file__).parent, root)
                    self.assertNotEqual(Path(sys.modules["uuid"].__file__).parent, root)
            self.assertIs(sys.path, original_path)

    def test_fixed_linux_outer_roster_cold_loads_without_native_execution(self):
        self.cold("linux-x64")

    def test_fixed_windows_outer_roster_omits_unix_helper_without_native_execution(self):
        self.cold("windows-x64")

    def test_fixed_darwin_outer_roster_cold_loads_without_native_execution(self):
        self.cold("macos-arm64")

    def test_loader_argv_mutation_cannot_select_a_different_postload_request(self):
        self.cold("linux-x64", mutate_argv=True)

    def test_outer_roster_is_separate_and_worker_roster_remains_fixed(self):
        self.assertEqual(W.outer_names("linux-x64"), W.names("linux-x64") + W.OUTER_NAMES)
        self.assertTrue(set(W.names("linux-x64")).isdisjoint(W.OUTER_NAMES))
        self.assertNotIn("run-hosted-initial-recipient", W.outer_names("linux-x64"))
        self.assertNotIn("hosted_lock_resources", W.outer_names("windows-x64"))

    def test_unknown_mode_or_roster_refuses_before_source_read(self):
        for mode in ("--Supervisor", "--entry", "--supervisor=1"):
            with self.subTest(mode=mode), patch.object(sys, "argv", ["fixed", mode, "{}", '{"role":"linux-x64"}']), \
                    patch.object(W, "read_source", side_effect=AssertionError("MODEL_NO_SOURCE_READ")):
                self.assertEqual(W.main(), 66)
        with patch.object(sys, "argv", ["fixed", "--supervisor", "{}", '{"role":"linux-x64"}']), \
                patch.object(W, "read_source", side_effect=AssertionError("MODEL_NO_SOURCE_READ")):
            self.assertEqual(W.main(), 66)


if __name__ == "__main__":
    unittest.main()
