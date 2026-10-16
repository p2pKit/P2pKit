#!/usr/bin/env python3
"""Focused new receiver lifecycle/CLI controls, with synthetic clocks/resources.

The actual C file-owner and R state/close/output machinery are exercised with
small BytesIO resources and explicitly supplied clocks. No test executes a
native process, Git/HTTP, cryptography, directory read or productive initializer.
This is not native custody, reader1066 reexecution or seal120 qualification.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes
import dataclasses
import importlib.util
import io
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in (
            "open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_RECEIVER_MODEL_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_receiver as R

spec = importlib.util.spec_from_file_location("productive_receiver_cli_models",
    ROOT / "scripts/run-hosted-initial-recipient-productive-receiver.py")
CLI = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = CLI
spec.loader.exec_module(CLI)
O, CD, RD, NS = R.O, R.CD, R.RD, R.NS
REGISTRIES = ("_ENTRIES", "_STATES", "_PINS", "_CLOSES", "_NATIVE_SEEDS", "_NATIVE_OWNERS", "_RETURNS", "_OUTPUTS")
ERRORS = (ValueError, RuntimeError)


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_RECEIVER_MODEL_EFFECT")


class ModelCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in REGISTRIES:
            self.install(R, name, {})
        self.install(R, "_REGISTRIES", tuple(getattr(R, name) for name in REGISTRIES))
        self.install(R, "_QUARANTINE", [])
        # Every model owns a fresh isolated quarantine. A model's intentional
        # unknown close must not contaminate a later independent test case.
        for module, name in ((R.C, "_PRIMARY_QUARANTINE"), (R.B, "QUARANTINE"), (R.Q, "QUARANTINE"),
                (R.B.diagnostics, "_QUARANTINE"), (R.N.continuity, "QUARANTINE")):
            self.install(module, name, [])
        self.local, self.raw, self.boot = 1000.0, 100 * NS, "b" * 64
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.action = lambda: None
        self.observed, self.raw_calls, self.callbacks = [], [], 0
        self.install(time, "monotonic", lambda: self.local)
        self.install(O.clocks, "observe", self.observe)
        self.install(O.clocks, "checked_now", self.checked_now)
        self.install(R.N.continuity, "boot_digest", lambda _role: self.boot)
        self.install(R.B.processes, "host_role", lambda: self.clock.role)
        # Explicit model seams only: no process identity/policy is claimed.
        self.install(R.P, "_credential_free", lambda: None)
        self.install(R, "_claims", lambda before: {})

    def install(self, module, name, value):
        self.stack.enter_context(patch.object(module, name, value))
        return value

    def observe(self):
        value = O.clocks.Reading(self.clock, self.raw)
        self.observed.append(value)
        return value

    def checked_now(self, identity, *, minimum_ns=0):
        self.assertEqual(identity, self.clock)
        self.raw_calls.append((identity, minimum_ns))
        O.require(self.raw >= minimum_ns, "MODEL_RAW_BACKWARDS")
        return self.raw

    def cancelled(self):
        self.callbacks += 1
        self.action()

    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(ERRORS) as failure:
            self.check(function, *args, **kwargs)
        return failure.exception

    def state(self, edge="seal"):
        entry = self.check(R._begin, edge)
        if edge.endswith("-child"):
            caps = (100 * NS, 220 * NS, 220 * NS, 100 * NS, 145 * NS, 190 * NS)
            state = self.check(R._new_state, entry, self.cancelled, caps=caps, declared_clock=self.clock,
                boot=self.boot, minimum=100 * NS)
            self.check(R._update, state.clock, phase="AUTHORITY_CHILD", seal_first=100 * NS, seal_end=220 * NS)
            return state
        return self.check(R._new_state, entry, self.cancelled)

    def file_owner(self, state, raw=b"model-ciphertext"):
        owner = self.check(R._file_owner, state)
        reader = self.check(owner.acquire, "reader", lambda: io.BytesIO(raw))
        return owner, reader

    def closed_child(self):
        state = self.state("seal-child")
        owner, reader = self.file_owner(state)
        close = self.check(R._close_owner, owner)
        self.assertTrue(reader.closed)
        expected = R.N.acquisition.stages.BootstrapMatch(b"model-expected-not-admitted")
        actual = R.N.acquisition.stages.BootstrapMatch(b"model-expected-not-admitted")
        pins = tuple(R.C._custody_match_pin(value, "worker") for value in (expected, actual))
        result = self.check(R._track, R._ChildReturn(b"model-terminal-not-native", "c" * 32))
        self.check(R._register, state, result, match_pins=pins)
        self.check(state.entry.latch.complete, state.entry.table, state.entry.attempt, result)
        return state, result, close


class EntryAndFenceModels(ModelCase):
    def test_job_slot_or_unregistered_acquisition_cannot_supply_receiver_authority(self):
        data = (b"supplied-proposal", b"supplied-worker", self.clock, self.boot,
            (1, "supplied-start", "supplied-runner", 2), 0, 5400 * NS)
        admission = R.N._OriginalServiceJobAdmission(object(), data)
        unregistered = R._Acquired(**{field.name: None for field in dataclasses.fields(R._Acquired)})
        for value in (admission, (admission, data), unregistered):
            with self.subTest(kind=type(value).__name__):
                self.refuses(R._acquired_passive, value)
        self.assertEqual(R._NATIVE_SEEDS, {})
        self.assertEqual(self.observed, [])

    def test_actual_same_first_and_two_raw_observations_per_guard(self):
        state = self.state()
        self.assertIs(state.clock.first, self.observed[0])
        before = len(self.raw_calls), self.callbacks
        self.assertEqual(self.check(state.fence.now), self.raw)
        self.assertEqual((len(self.raw_calls) - before[0], self.callbacks - before[1]), (2, 1))
        self.assertEqual((state.fence.work, state.fence.final), (130 * NS, 130 * NS))

    def test_duplicate_entry_poisons_original_even_when_caught(self):
        state = self.state()
        first = self.refuses(R._begin, "seal")
        self.assertIs(self.refuses(state.fence.now), first)

    def test_reentrant_guard_cannot_be_caught_then_repaired(self):
        state = self.state()
        caught = []
        def nested():
            try:
                state.fence.now()
            except ERRORS as error:
                caught.append(error)
        self.action = nested
        first = self.refuses(state.fence.now)
        self.assertIs(first, caught[0])
        self.action = lambda: None
        self.assertIs(self.refuses(state.fence.now), first)

    def test_raw_local_and_boot_limits_fail_closed_without_renewal(self):
        state = self.state()
        self.raw = state.fence.work
        first = self.refuses(state.fence.now)
        self.raw = state.clock.first.nanoseconds
        self.assertIs(self.refuses(state.fence.now, final=True), first)

    def test_local_expiry_sticks_when_raw_still_before_cap(self):
        state = self.state()
        self.local = state.fence.local_end
        first = self.refuses(state.fence.now)
        self.local = 1000.0
        self.assertIs(self.refuses(state.fence.now), first)

    def test_changed_boot_is_not_a_fresh_job_basis(self):
        state = self.state()
        self.boot = "c" * 64
        self.refuses(state.fence.now)

    def test_changed_clock_slot_and_equal_state_replacement_refuse(self):
        state = self.state()
        state.clock.work += NS
        self.refuses(state.fence.now)

    def test_original_registry_reference_cannot_be_replaced(self):
        state = self.state()
        self.install(R, "_STATES", dict(R._STATES))
        self.refuses(state.fence.now)

    def test_source_owned_guard_supplier_replacement_refuses(self):
        state = self.state()
        self.install(R, "_read_inputs", lambda _state: None)
        self.refuses(state.fence.now)

    def test_existing_primary_unknown_close_quarantine_blocks_new_receiver(self):
        R.C._PRIMARY_QUARANTINE.append(object())
        self.refuses(self.state)

    def test_delayed_child_uses_original_helper45_not_first_plus45(self):
        self.raw = 140 * NS
        state = self.state("seal-child")
        self.assertEqual((state.fence.work, state.fence.final), (145 * NS, 145 * NS))
        self.assertLessEqual(state.fence.local_end, 1005.0)
        self.raw = 145 * NS
        self.refuses(state.fence.now)

    def test_cancellation_cannot_move_local_or_raw_last_unnoticed(self):
        state = self.state()
        self.action = lambda: setattr(state.clock, "last", state.clock.last + 1)
        self.refuses(state.fence.now)

    def test_metadata_to_seal_transition_requires_real_close_and_is_once(self):
        state = self.state()
        owner, _reader = self.file_owner(state)
        closed = self.check(R._close_owner, owner)
        final = ({}, {"originalProposal": {"phaseFencesNs": {"separate-seal": 210 * NS}}}, {}, {}, {}, {}, {},
            {"returnedNs": 90 * NS})
        self.check(R._update, state, input_close=closed, final=final)
        self.check(R._enter_seal, state)
        self.assertEqual((state.clock.seal_first, state.clock.seal_end), (100 * NS, 210 * NS))
        self.assertEqual((state.fence.work, state.fence.final), (210 * NS, 210 * NS))
        self.assertLessEqual(state.fence.local_end, 1110.0)
        self.refuses(R._enter_seal, state)


class CloseAndStreamModels(ModelCase):
    def test_actual_memory_reader_close_is_not_ledger_inference(self):
        state = self.state()
        owner, reader = self.file_owner(state)
        closed = self.check(R._close_owner, owner)
        self.assertTrue(reader.closed)
        before = len(self.raw_calls)
        self.assertIs(self.check(R._checked_close, closed), closed)
        self.assertEqual(before, len(self.raw_calls))
        self.refuses(R._close_owner, owner)

    def test_equal_reconstructed_close_is_not_original(self):
        state = self.state()
        owner, _reader = self.file_owner(state)
        closed = self.check(R._close_owner, owner)
        self.refuses(R._checked_close, dataclasses.replace(closed))

    def test_relabelled_original_closed_resource_is_rejected(self):
        state = self.state()
        owner, _reader = self.file_owner(state)
        closed = self.check(R._close_owner, owner)
        owner.ledger[0]["label"] = "writer"
        self.refuses(R._checked_close, closed)

    def test_unknown_reader_close_never_registers_success(self):
        class Broken(io.BytesIO):
            def close(self):
                super().close()
                raise O.OriginError("MODEL_UNKNOWN_CLOSE")
        state = self.state()
        owner = self.check(R._file_owner, state)
        self.check(owner.acquire, "reader", lambda: Broken(b"small"))
        self.refuses(R._close_owner, owner)
        self.assertNotIn(id(owner), R._CLOSES)
        self.assertTrue(owner.owner.unknown)

    def test_ciphertext_complete_bytes_hash_eof_and_real_close(self):
        state = self.state()
        raw = b"ciphertext-model" * 13
        owner, reader = self.file_owner(state, raw)
        verifies = []
        checksum = self.check(R._stream_ciphertext, owner, reader, len(raw), O.digest(raw), lambda: verifies.append(True))
        self.assertEqual(checksum, O.digest(raw))
        self.assertEqual(verifies, [True])
        self.assertTrue(reader.closed)
        self.check(R._close_owner, owner)

    def test_ciphertext_extra_tail_refuses_and_still_closes(self):
        state = self.state()
        owner, reader = self.file_owner(state, b"abcd")
        self.refuses(R._stream_ciphertext, owner, reader, 3, O.digest(b"abc"), lambda: None)
        self.assertTrue(reader.closed)
        self.assertIsNotNone(owner.failure)

    def test_ciphertext_individual576_is_not_plaintext_or_whole_zip512(self):
        self.assertEqual(R.B.posix.MAX_CIPHERTEXT_BYTES, 576 * 1024 * 1024)
        self.assertEqual(CD.MAX_BYTES, 512 * 1024 * 1024)
        state = self.state()
        owner, reader = self.file_owner(state, b"x")
        self.refuses(R._stream_ciphertext, owner, reader, 576 * 1024 * 1024 + 1, O.digest(b"x"), lambda: None)
        self.check(R._close_owner, owner)


class ChildMetadataReadbackModels(ModelCase):
    """Synthetic retained pairs only, not a native parent/child execution."""

    def pair(self, *, windows=False, relative="service/start.json"):
        raw, sid = b'{"model":"unchanged-start-file"}\n', "S-1-5-21-1001"
        if windows:
            native = ("windows", 7, "1" * 32, False, len(raw), 1, 0x80, 10, 11, 12, sid, True)
            directory = ("windows", 7, "2" * 32, True, 0, 1, 0x10, 7, 8, 9, sid, True)
        else:
            native = ("posix", 7, 31, stat.S_IFREG | 0o600, 42, 1, len(raw), 11, 12)
            directory = ("posix", 7, 21, stat.S_IFDIR | 0o700, 42, 2, 4096, 9, 10)
        ordinals = (2, 4) if relative == "context.json" else (3, 5)
        first = {"relative": relative, "maximum": CD.LIMIT, "bytes": len(raw), "sha256": O.digest(raw),
            "native": list(native), "directoryNative": list(directory), "provenance": RD.PROVENANCE,
            "readerOrdinal": ordinals[0], "retirement": "KNOWN_READER_CLOSE"}
        readback = copy.deepcopy(first)
        readback["readerOrdinal"] = ordinals[1]
        return first, readback, raw, relative, directory[1:3]

    def test_unchanged_context_and_start_both_native_shapes(self):
        for windows in (False, True):
            for relative in ("context.json", "service/start.json"):
                self.assertIsNone(self.check(R._child_metadata_readback, *self.pair(windows=windows, relative=relative)))

    def test_posix_parent_entry_delta_keeps_both_original_observations(self):
        pair = self.pair()
        pair[1]["directoryNative"][6:9] = [8192, 40, 41]
        saved = copy.deepcopy(pair)
        first, readback = pair[0]["directoryNative"], pair[1]["directoryNative"]
        self.check(R._child_metadata_readback, *pair)
        self.assertEqual(pair, saved)
        self.assertIs(pair[0]["directoryNative"], first)
        self.assertIs(pair[1]["directoryNative"], readback)
        self.assertNotEqual(first, readback)

    def test_windows_parent_entry_delta_keeps_both_original_observations(self):
        pair = self.pair(windows=True)
        pair[1]["directoryNative"][8:10] = [40, 41]
        saved = copy.deepcopy(pair)
        first, readback = pair[0]["directoryNative"], pair[1]["directoryNative"]
        self.check(R._child_metadata_readback, *pair)
        self.assertEqual(pair, saved)
        self.assertIs(pair[0]["directoryNative"], first)
        self.assertIs(pair[1]["directoryNative"], readback)
        self.assertNotEqual(first, readback)

    def test_context_directory_remains_full_native_equal(self):
        for windows in (False, True):
            for index in ((8, 9) if windows else (6, 7, 8)):
                pair = self.pair(windows=windows, relative="context.json")
                pair[1]["directoryNative"][index] += 1
                self.refuses(R._child_metadata_readback, *pair)

    def test_changed_or_jointly_replaced_directory_identity_refuses(self):
        for windows in (False, True):
            for index in (1, 2):
                for both in (False, True):
                    pair = self.pair(windows=windows)
                    for observed in pair[:2] if both else pair[1:2]:
                        value = observed["directoryNative"][index]
                        observed["directoryNative"][index] = "3" * 32 if type(value) is str else value + 10
                    self.refuses(R._child_metadata_readback, *pair)

    def test_posix_owner_mode_and_equal_unsafe_private_bits_refuse(self):
        for index, value in ((4, 43), (3, stat.S_IFDIR | 0o500)):
            pair = self.pair()
            pair[1]["directoryNative"][index] = value
            self.refuses(R._child_metadata_readback, *pair)
        for mode in (0o710, 0o701, 0o770):
            pair = self.pair()
            for observed in pair[:2]:
                observed["directoryNative"][3] = stat.S_IFDIR | mode
            self.refuses(R._child_metadata_readback, *pair)

    def test_windows_owner_and_equal_unsafe_acl_shape_refuse(self):
        pair = self.pair(windows=True)
        pair[1]["directoryNative"][10] = "S-1-5-21-1002"
        self.refuses(R._child_metadata_readback, *pair)
        for index, value in ((10, None), (10, ""), (10, "model-not-a-sid"), (11, False), (6, 0x80)):
            for both in (False, True):
                pair = self.pair(windows=True)
                for observed in pair[:2] if both else pair[1:2]:
                    observed["directoryNative"][index] = value
                self.refuses(R._child_metadata_readback, *pair)

    def test_other_stable_directory_fields_and_malformed_native_refuse(self):
        for windows in (False, True):
            for index in ((4, 5, 6, 7) if windows else (5,)):
                pair = self.pair(windows=windows)
                pair[1]["directoryNative"][index] += 1
                self.refuses(R._child_metadata_readback, *pair)
            pair = self.pair(windows=windows)
            pair[1]["directoryNative"].pop()
            self.refuses(R._child_metadata_readback, *pair)
            pair = self.pair(windows=windows)
            pair[1]["directoryNative"][3] = False if windows else stat.S_IFREG | 0o700
            self.refuses(R._child_metadata_readback, *pair)
        pair = self.pair(windows=True)
        pair[1]["directoryNative"][6] |= 0x400
        self.refuses(R._child_metadata_readback, *pair)

    def test_full_file_native_change_refuses_despite_identical_bytes(self):
        for windows in (False, True):
            for index in ((1, 2, 5, 6, 7, 8, 9, 10, 11) if windows else (1, 2, 3, 4, 5, 7, 8)):
                pair = self.pair(windows=windows)
                native = pair[1]["native"]
                native[index] = ("4" * 32 if index == 2 else "S-1-5-21-1002") if type(native[index]) is str else (
                    False if type(native[index]) is bool else native[index] + 1)
                self.refuses(R._child_metadata_readback, *pair)

    def test_byte_hash_limit_provenance_and_retirement_substitutions_refuse(self):
        for windows in (False, True):
            for replacement in (b"other", b"x" * len(self.pair()[2]), bytearray(self.pair()[2])):
                pair = self.pair(windows=windows)
                self.refuses(R._child_metadata_readback, *pair[:2], replacement, *pair[3:])
            for key, value in (("sha256", "a" * 64), ("bytes", 1), ("maximum", CD.LIMIT - 1),
                    ("provenance", "ORIGINAL_PRODUCER_PIN"), ("retirement", "UNKNOWN")):
                pair = self.pair(windows=windows)
                for observed in pair[:2]:
                    observed[key] = value
                self.refuses(R._child_metadata_readback, *pair)

    def test_closed_routes_ordinals_and_observation_shape_refuse(self):
        for windows in (False, True):
            for relative in ("start.json", "service/other.json", "other/start.json", "../start.json", "context.json"):
                pair = self.pair(windows=windows)
                self.refuses(R._child_metadata_readback, *pair[:3], relative, pair[4])
            for first, second in ((3, 3), (5, 3), (2, 4), (True, 5)):
                pair = self.pair(windows=windows)
                pair[0]["readerOrdinal"], pair[1]["readerOrdinal"] = first, second
                self.refuses(R._child_metadata_readback, *pair)
            pair = self.pair(windows=windows)
            pair[1]["extra"] = "not-admitted"
            self.refuses(R._child_metadata_readback, *pair)
            pair = self.pair(windows=windows)
            del pair[1]["native"]
            self.refuses(R._child_metadata_readback, *pair)
            pair = self.pair(windows=windows)
            pair[1]["directoryNative"] = tuple(pair[1]["directoryNative"])
            self.refuses(R._child_metadata_readback, *pair)
            pair = self.pair(windows=windows)
            self.refuses(R._child_metadata_readback, *pair[:4], (True, pair[4][1]))

    def test_metadata_helper_supplier_replacement_poisons_original_entry(self):
        state = self.state("seal-child")
        original = R._child_metadata_readback
        self.install(R, "_child_metadata_readback", lambda *_args: None)
        first = self.refuses(state.fence.now)
        self.install(R, "_child_metadata_readback", original)
        self.assertIs(self.refuses(state.fence.now), first)


class RegisteredReturnAndOutputModels(ModelCase):
    def test_exact12_before_interface_without_disk_constructor(self):
        self.assertEqual(tuple(field.name for field in dataclasses.fields(R.ProductiveBefore)),
            ("first", "first_local", "boot", "deadline_raw", "inputs", "input_closes", "authority_raw", "authority_index_raw",
             "authority_files", "authority_closes", "authority_close_originals", "fence"))
        fabricated = R.ProductiveBefore(O.clocks.Reading(self.clock, self.raw), self.local, self.boot,
            b"{}\n", (), (), b"{}\n", b"{}\n", (), (), (), object())
        self.refuses(R.checked_productive_before, fabricated)

    def test_registered_return_check_is_passive_and_reconstruction_refuses(self):
        _state, result, _close = self.closed_child()
        before = len(self.raw_calls), self.callbacks
        self.assertIs(self.check(R._registered, result, complete=True).result, result)
        self.assertEqual(before, (len(self.raw_calls), self.callbacks))
        self.refuses(R._registered, dataclasses.replace(result), complete=True)

    def test_original_return_mutation_poisons_even_after_value_restored(self):
        _state, result, _close = self.closed_child()
        original = result.raw
        object.__setattr__(result, "raw", b"changed")
        first = self.refuses(R._registered, result, complete=True)
        object.__setattr__(result, "raw", original)
        self.assertIs(self.refuses(R._registered, result, complete=True), first)

    def output(self):
        state, result, _close = self.closed_child()
        value = {"schema": 1, "scope": RD.SEAL_ACK_SCOPE, "invocation": result.invocation,
            "terminalSha256": O.digest(result.raw), "clock": O.clock_value(state.clock.first.clock), "closedNs": self.raw}
        fence = self.check(R._output_fence, result, value, child=True)
        return state, result, value, fence

    def test_two_actual_late_checks_only_and_no_third_check(self):
        state, _result, value, fence = self.output()
        self.raw += NS
        value["closedNs"] = self.check(fence.now, final=True, limit=state.fence.work)
        self.raw += NS
        self.check(fence.now, final=True, limit=state.fence.work)
        self.refuses(fence.now, final=True, limit=state.fence.work)

    def test_late_observation_cannot_be_invented_or_skipped(self):
        state, _result, value, fence = self.output()
        self.raw += NS
        self.check(fence.now, final=True, limit=state.fence.work)
        # The shared output path must replace pending closedNs with THAT return.
        self.refuses(fence.now, final=True, limit=state.fence.work)
        self.assertEqual(value["closedNs"], 100 * NS)

    def test_output_mutation_and_reentry_remain_first_failure(self):
        state, _result, value, fence = self.output()
        work = state.fence.work
        value["terminalSha256"] = "a" * 64
        first = self.refuses(fence.now, final=True, limit=work)
        self.assertIs(self.refuses(fence.now, final=True, limit=work), first)
        self.assertIs(self.refuses(lambda: state.fence.work), first)

    def test_output_deadline_cannot_advance_to_later_seal_end(self):
        state, _result, _value, fence = self.output()
        self.assertLess(state.fence.work, state.clock.seal_end)
        self.refuses(fence.now, final=True, limit=state.clock.seal_end)


class CliAndCommandModels(ModelCase):
    def arguments(self):
        caps = (100 * NS, 220 * NS, 220 * NS, 100 * NS, 145 * NS, 190 * NS)
        return ["_seal-authority", "--context-sha256", "a" * 64, "--minimum-ns", str(101 * NS),
            *(item for flag, cap in zip(RD.AUTHORITY_CAP_FLAGS, caps) for item in (flag, str(cap))),
            "--original-boot-digest", self.boot, "--clock-role", self.clock.role, "--clock-domain", self.clock.domain,
            "--clock-ticks-per-second", str(NS)]

    def test_closed_cli_only_seal_and_two_native_children(self):
        self.assertEqual(self.check(CLI._arguments, ["seal"]), ("seal", None))
        args = self.arguments()
        operation, values = self.check(CLI._arguments, args)
        self.assertEqual(operation, "_seal-authority")
        self.assertEqual(values[0], "a" * 64)
        self.refuses(CLI._arguments, ["before"])
        self.refuses(CLI._arguments, ["seal", "--override", "bad"])
        self.refuses(CLI._arguments, ["_before", *args[1:]])

    def test_duplicate_equals_reordered_or_abbreviated_argv_refuse(self):
        args = self.arguments()
        changed = (args + args[1:3], [args[0], args[1] + "=" + args[2], *args[3:]],
            [args[0], *args[3:5], *args[1:3], *args[5:]], [args[0], "--context-sha", *args[2:]],
            [*args[:4], "0" + args[4], *args[5:]])
        for argv in changed:
            self.refuses(CLI._arguments, argv)

    def test_fixed_child_command_has_all6_caps_but_no_token(self):
        caps = (100 * NS, 220 * NS, 220 * NS, 100 * NS, 145 * NS, 190 * NS)
        raw = b"model-context"
        command = self.check(R._command, "before", raw, caps, self.clock, self.boot, 101 * NS,
            interpreter="/model/python")
        self.assertEqual(command[:4], ["/model/python", "-I", "-B", "-S"])
        self.assertEqual(command[4:6], [str(R.SCRIPTS / "run-hosted-initial-recipient-productive-receiver.py"), "_before-authority"])
        for flag in RD.AUTHORITY_CAP_FLAGS:
            self.assertEqual(command.count(flag), 1)
        self.assertNotIn("--token", command)
        self.refuses(R._command, "arbitrary", raw, caps, self.clock, self.boot, interpreter="/model/python")


if __name__ == "__main__":
    unittest.main(failfast=True)
