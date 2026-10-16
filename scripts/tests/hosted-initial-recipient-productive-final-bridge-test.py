#!/usr/bin/env python3
"""NEW narrow bridge/ACK/stream models; no native route or hosted qualification.

All native phase and close suppliers are explicit in-memory models. The fixed
wrappers are exercised with their private native bodies replaced, never with
a process, credential, provider, private evidence file or public key. BytesIO
checks hashing/forward consumption only, not GPG or an encrypted artifact.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import hashlib
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_FINAL_BRIDGE_MODEL_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_custody as PC

C, N, B, O, CD, NS = PC.C, PC.N, PC.B, PC.O, PC.CD, PC.NS
H = "a" * 64
REFUSALS = (ValueError, RuntimeError)
C_SOURCE = (ROOT / "scripts/run-hosted-initial-recipient-custody.py").read_text(encoding="utf-8")
PC_SOURCE = (ROOT / "scripts/hosted_initial_recipient_productive_custody.py").read_text(encoding="utf-8")


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_FINAL_BRIDGE_MODEL_EFFECT")


class ModelCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("_PINS", "_PIN_FAILURES", "_FAILURES", "_ACKS", "_NATIVE_SEEDS", "_CIPHER_STREAMS", "_OWNER_CLOSES"):
            self.install(PC, name, {})
        self.install(PC, "_QUARANTINE", [])

    def install(self, module, name, value):
        self.stack.enter_context(patch.object(module, name, value))
        return value

    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(REFUSALS) as caught:
            self.check(function, *args, **kwargs)
        return caught.exception


class CommandModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.raw, self.python = b"tiny-model-context", "/model/python3"
        self.authority = tuple(value * NS for value in (100, 235, 280, 110, 155, 200))
        self.crypto = tuple(value * NS for value in (220, 520, 565, 595, 110, 320, 365))
        self.install(B, "initial_command", lambda *_args: self.fail("historical command attempted interpreter resolution"))

    def command(self, operation, caps, minimum=None):
        return self.check(PC._command, operation, self.raw, caps, self.clock, H, minimum, interpreter=self.python)

    def test_fixed_separate_pre_post_argv_six_caps(self):
        for operation in ("_final-authority-pre", "_final-authority-post"):
            argv = self.command(operation, self.authority)
            expected = [self.python, "-I", "-B", "-S", str(PC.P.SCRIPTS / "run-hosted-initial-recipient-productive.py"),
                operation, "--context-sha256", O.digest(self.raw)]
            for name, value in zip(CD.FINAL_AUTHORITY_CAP_FLAGS, self.authority):
                expected += [name, str(value)]
            expected += ["--original-boot-digest", H, "--clock-role", self.clock.role,
                "--clock-domain", self.clock.domain, "--clock-ticks-per-second", str(NS)]
            self.assertEqual(argv, expected)

    def test_crypto_has_seven_caps_and_separate_actual_minimum(self):
        argv = self.command("_final-crypto", self.crypto, 120 * NS)
        self.assertEqual(argv[8:10], ["--minimum-ns", str(120 * NS)])
        flags = argv[10:-8:2]
        self.assertEqual(tuple(flags), CD.FINAL_CRYPTO_CAP_FLAGS)
        self.assertEqual(tuple(map(int, argv[11:-8:2])), self.crypto)

    def test_old_operation_name_is_not_productive_alias(self):
        self.refuses(self.command, "_custody-crypto", self.crypto)
        self.refuses(self.command, "_authority", self.authority)

    def test_bool_caps_or_minimum_are_not_integer_data(self):
        self.refuses(self.command, "_final-crypto", (True, *self.crypto[1:]))
        self.refuses(self.command, "_final-authority-pre", self.authority, True)

    def test_noncanonical_interpreter_path_refuses_without_resolver(self):
        self.python = "/model/../python3"
        self.refuses(self.command, "_final-crypto", self.crypto)

    def test_actual_command_path_selects_maintained_interpreter(self):
        calls = []
        self.install(B, "initial_command", lambda digest: calls.append(digest) or [self.python])
        argv = self.check(PC._command, "_final-crypto", self.raw, self.crypto, self.clock, H)
        self.assertEqual(argv[0], self.python)
        self.assertEqual(calls, [O.digest(self.raw)])


class DispatcherModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.seed, self.owner, self.private, self.fence, self.before = (object() for _number in range(5))
        self.raw, self.token, self.result = b"model-context", "model-token-not-a-credential", object()
        self.calls = []

    def test_canonical_graph_is_p_graph_not_before_module(self):
        self.assertIs(PC.P.C, C)
        self.assertIs(PC.P.N, N)
        self.assertIs(PC.P.B, B)
        self.assertIs(C.N, N)
        self.assertIs(C.native, B)
        self.assertIsNot(C.B, B)

    def test_n_distinct_pre_post_dispatchers_retain_original_arguments(self):
        def verify(*args, post):
            self.calls.append(("checked", args, post))
        def native(*args, **kwargs):
            self.calls.append(("body", args, kwargs))
            return self.result
        self.install(PC, "_checked_authority_phase", verify)
        self.install(N, "_service_phase_owned", native)
        for function, post in ((N._productive_authority_pre_phase, False), (N._productive_authority_post_phase, True)):
            args = (self.seed, self.owner, self.private, self.raw, self.token, self.fence, self.before)
            self.assertIs(self.check(function, *args), self.result)
            self.assertEqual(self.calls[-2], ("checked", (self.seed, self.owner, self.private, self.raw,
                self.fence, self.before), post))
            self.assertEqual(self.calls[-1], ("body", args[1:], {"final_seed": self.seed}))

    def test_native_b_distinct_pre_post_dispatchers_retain_git_selection(self):
        def verify(*args, post):
            self.calls.append(("checked", args, post))
        def native(*args, **kwargs):
            self.calls.append(("body", args, kwargs))
            return self.result
        self.install(PC, "_checked_native_authority_bridge", verify)
        self.install(B, "_phase_owned", native)
        for function, post in ((B.productive_pre_authority_phase, False), (B.productive_post_authority_phase, True)):
            args = (self.seed, self.owner, self.private, self.raw, self.token, self.fence)
            self.assertIs(self.check(function, *args, initial_git="/model/git"), self.result)
            self.assertEqual(self.calls[-2], ("checked", (self.seed, self.owner, self.private, self.raw, self.fence), post))
            self.assertEqual(self.calls[-1], ("body", args[1:], {"initial_git": "/model/git", "final_seed": self.seed}))

    def test_bridge_refusal_precedes_native_body(self):
        error = O.OriginError("MODEL_FOREIGN_SEED")
        def refuse(*_args, **_kwargs):
            raise error
        self.install(PC, "_checked_authority_phase", refuse)
        self.install(N, "_service_phase_owned", lambda *_args, **_kwargs: self.fail("native body after refusal"))
        self.assertIs(self.refuses(N._productive_authority_pre_phase, self.seed, self.owner, self.private,
            self.raw, self.token, self.fence, self.before), error)

    def test_old_n_route_refuses_both_new_context_scopes(self):
        self.install(N, "_service_phase_owned", lambda *_args, **_kwargs: self.fail("new scope used old route"))
        for scope in (CD.AUTHORITY_PRE_CONTEXT_SCOPE, CD.AUTHORITY_POST_CONTEXT_SCOPE):
            self.refuses(N._initial_service_phase, self.owner, self.private, O.encoded({"scope": scope}),
                self.token, self.fence, self.before)

    def test_old_b_wrapper_does_not_supply_productive_seed(self):
        def body(*args, **kwargs):
            self.calls.append((args, kwargs))
            return self.result
        self.install(B, "_phase_owned", body)
        self.assertIs(self.check(B.phase, self.owner, self.private, self.raw, self.token, self.fence,
            initial_git="/model/git"), self.result)
        self.assertEqual(self.calls[0][1], {"initial_git": "/model/git"})

    def test_crypto_wrapper_uses_exact_seed_and_same_native_body(self):
        # Uninitialized exact type solely for the wrapper's type check. The
        # PC binding and native body are replaced, so this mints NO real owner.
        owner = object.__new__(C._ProductiveNativeOwner)
        check = lambda: None
        self.install(PC, "_native_crypto_binding", lambda seed: (owner, self.private, self.raw, self.fence, check))
        def body(*args, **kwargs):
            self.calls.append((args, kwargs))
            return self.result
        self.install(C, "_crypto_native_owned", body)
        self.assertIs(self.check(C.productive_crypto_native, self.seed), self.result)
        self.assertEqual(self.calls, [((owner, self.private, self.raw, self.fence, check), {"final_seed": self.seed})])

    def test_crypto_wrapper_refuses_foreign_graph_and_owner(self):
        self.install(PC, "_native_crypto_binding", lambda seed: (self.owner, self.private, self.raw, self.fence, lambda: None))
        self.install(C, "_crypto_native_owned", lambda *_args, **_kwargs: self.fail("foreign native body"))
        self.refuses(C.productive_crypto_native, self.seed)
        self.install(PC, "C", object())
        self.refuses(C.productive_crypto_native, self.seed)


class NativeTransitionModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.identity = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.reading = O.clocks.Reading(self.identity, 150 * NS)
        self.parent, self.clock, self.scope = object(), object(), object()
        self.child = SimpleNamespace(pid=17)
        self.raw = b"model-native-context"
        self.calls = []
        self.fence = SimpleNamespace(work=520 * NS, final=565 * NS, last=150 * NS, now=self.now)
        self.anchor = SimpleNamespace(rows=(({}, "native-scope", self.scope, False, False),))
        self.owner = SimpleNamespace(fence=self.fence, _anchor=lambda: self.anchor)
        self.seed = PC._track(PC._NativeSeed())
        self.saved = PC._track(PC._NativeState(self.seed, self.parent, "crypto-native", self.fence, self.reading,
            lambda: None, 1265.0, owner=self.owner, context_raw=self.raw))
        PC._NATIVE_SEEDS[id(self.seed)] = self.saved
        self.state = SimpleNamespace(handle=self.parent, clock=self.clock, crypto_seed=self.seed, native_return=None,
            phase_caps=tuple(value * NS for value in (220, 520, 565, 595)))
        self.basis = SimpleNamespace(phase=1, reading=self.reading, last_local=1001.0, ends=self.state.phase_caps)
        self.install(PC, "_state", self.state_of)
        self.install(PC, "_clock", self.clock_of)
        self.install(PC, "_advance", self.advance)

    def state_of(self, parent):
        self.assertIs(parent, self.parent)
        return self.state

    def clock_of(self, clock):
        self.assertIs(clock, self.clock)
        return self.basis

    def now(self, *, limit):
        self.assertEqual(limit, self.saved.phase[1])
        self.calls.append(("work-check", limit))
        return self.fence.last

    def advance(self, clock, name):
        self.assertIs(clock, self.clock)
        self.calls.append(("advance", name))
        self.basis.phase = 1 if name == "custody-encrypt" else 2

    def phase(self):
        PC._update(self.saved, phase=tuple(value * NS for value in (110, 320, 365)))

    def launch(self):
        self.phase()
        self.check(PC._native_crypto_child_return, self.seed, self.scope, self.child)

    def test_constructor_native_seed_is_not_authority(self):
        self.refuses(PC._checked_native_owner_seed, PC._NativeSeed())

    def test_parent_native_start_only_changes_wait_envelope(self):
        self.basis.phase = 0
        self.fence.last = 110 * NS
        end, first = self.saved.end, self.saved.first
        self.check(PC._check_native_phase_entry, self.seed, self.owner, self.raw, 110 * NS, 320 * NS, 365 * NS)
        self.assertEqual(self.saved.phase, (110 * NS, 320 * NS, 365 * NS))
        self.assertEqual(self.calls, [("advance", "custody-encrypt")])
        self.assertEqual(self.saved.end, end)
        self.assertIs(self.saved.first, first)
        self.assertEqual(self.saved.completion, ())

    def test_phase_entry_requires_original_context_reference(self):
        self.fence.last = 110 * NS
        equal_raw = bytes(bytearray(self.raw))
        self.assertIsNot(equal_raw, self.raw)
        self.refuses(PC._check_native_phase_entry, self.seed, self.owner, equal_raw, 110 * NS, 320 * NS, 365 * NS)
        self.assertEqual(self.saved.phase, ())

    def test_phase_entry_cannot_extend_native210_or_final45(self):
        self.fence.last = 110 * NS
        self.refuses(PC._check_native_phase_entry, self.seed, self.owner, self.raw, 110 * NS, 321 * NS, 366 * NS)

    def test_actual_spawn_return_retains_original_scope_child_and_pid(self):
        self.launch()
        self.assertIs(self.saved.launch[0], self.scope)
        self.assertIs(self.saved.launch[1], self.child)
        self.assertEqual(self.saved.launch[2], 17)
        self.refuses(PC._native_crypto_child_return, self.seed, self.scope, self.child)

    def test_unowned_or_retired_scope_is_not_spawn_return(self):
        self.phase()
        self.refuses(PC._native_crypto_child_return, self.seed, object(), self.child)
        self.anchor.rows = (({}, "native-scope", self.scope, True, True),)
        self.refuses(PC._native_crypto_child_return, self.seed, self.scope, self.child)

    def test_success_only_final_keeps_actual_reading_and_original_phase(self):
        self.launch()
        phase = self.saved.phase
        self.check(PC._native_crypto_final, self.seed, self.scope, self.child, 0, 150 * NS)
        self.assertIs(self.saved.completion[4], self.reading)
        self.assertIs(self.saved.phase, phase)
        self.assertEqual(self.calls, [("work-check", 320 * NS), ("advance", "custody-encrypt-final")])
        self.refuses(PC._native_crypto_final, self.seed, self.scope, self.child, 0, 150 * NS)

    def test_nonzero_or_bool_code_cannot_enter_final(self):
        self.launch()
        for code in (1, -1, False):
            self.refuses(PC._native_crypto_final, self.seed, self.scope, self.child, code, 150 * NS)
        self.assertEqual(self.saved.completion, ())
        self.assertEqual(self.calls, [])

    def test_foreign_child_or_changed_pid_cannot_complete(self):
        self.launch()
        self.refuses(PC._native_crypto_final, self.seed, self.scope, SimpleNamespace(pid=17), 0, 150 * NS)
        self.child.pid = 18
        self.refuses(PC._native_crypto_final, self.seed, self.scope, self.child, 0, 150 * NS)

    def test_expired_work_or_future_completed_ns_cannot_enter_final(self):
        self.launch()
        self.refuses(PC._native_crypto_final, self.seed, self.scope, self.child, 0, 151 * NS)
        self.fence.last = 320 * NS
        self.refuses(PC._native_crypto_final, self.seed, self.scope, self.child, 0, 150 * NS)

    def test_actual_native_source_hooks_are_not_failure_finally_hooks(self):
        block = C_SOURCE.split("def _crypto_native_owned(", 1)[1].split("\ndef ", 1)[0]
        spawn = block.index("child = scope.spawn(")
        retain = block.index("PC._native_crypto_child_return(final_seed, scope, child)")
        first_check = block.index("require(child.stdout is None")
        self.assertLess(spawn, retain)
        self.assertLess(retain, first_check)
        final = block.index("PC._native_crypto_final(final_seed, scope, child, code, row[\"completedNs\"])")
        self.assertLess(block.index('require(type(code) is int and code == 0'), final)
        self.assertLess(block.index('require(not scope.discover()'), final)
        self.assertLess(final, block.index('\n    finally:'))


class AckFenceModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.hard, self.close, self.calls = 200 * NS, object(), []
        self.action = lambda: None
        self.fence = PC._ChildAckFence()
        self.saved = PC._track(PC._AckState(object(), self.fence, self.hard, self.close))
        PC._ACKS[id(self.fence)] = self.saved
        self.state = SimpleNamespace(clock=SimpleNamespace(now=self.now), closed=self.close)
        self.install(PC, "_ack_passive", self.passive)

    def passive(self, saved):
        O.require(saved is self.saved and self.state.closed is self.close and saved.close is self.close,
            "MODEL_ORIGINAL_CLOSE_CHANGED")
        self.calls.append("passive")
        return self.state

    def now(self, *, final, limit):
        self.assertIs(final, True)
        self.assertEqual(limit, self.hard)
        self.calls.append("clock")
        self.action()
        return 150 * NS

    def test_exact_two_late_checks_each_recheck_passive_currency(self):
        for _number in range(2):
            self.assertEqual(self.check(self.fence.now, final=True, limit=self.hard), 150 * NS)
        self.assertEqual(self.calls, ["passive", "clock", "passive"] * 2)
        self.assertEqual(self.saved.calls, 2)
        self.refuses(self.fence.now, final=True, limit=self.hard)

    def test_wrong_limit_burns_ack_with_same_first_failure(self):
        first = self.refuses(self.fence.now, final=True, limit=self.hard + 1)
        self.assertIs(self.refuses(self.fence.now, final=True, limit=self.hard), first)

    def test_caught_ack_reentry_poison_is_checked_after_clock_callback(self):
        errors = []
        def nested():
            try:
                self.fence.now(final=True, limit=self.hard)
            except REFUSALS as error:
                errors.append(error)
        self.action = nested
        first = self.refuses(self.fence.now, final=True, limit=self.hard)
        self.assertIs(first, errors[0])
        self.action = lambda: None
        self.assertIs(self.refuses(self.fence.now, final=True, limit=self.hard), first)

    def test_post_callback_original_close_currency_is_not_skipped(self):
        self.action = lambda: setattr(self.state, "closed", object())
        first = self.refuses(self.fence.now, final=True, limit=self.hard)
        self.state.closed = self.close
        self.action = lambda: None
        self.assertIs(self.refuses(self.fence.now, final=True, limit=self.hard), first)

    def test_arbitrary_closed_flag_cannot_register_real_ack(self):
        self.refuses(PC._child_ack_fence, SimpleNamespace(handle=object(), closed=True), self.hard)


class CipherStreamModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.charges, self.guards = [], 0
        self.owner = SimpleNamespace(guard=self.guard)
        self.install(PC, "_charge", lambda owner, count=0, **_kwargs: self.charges.append((owner, count)))

    def guard(self):
        self.guards += 1
        return 2000.0

    def stream(self, raw=b"abcdef", *, size=None):
        self.reader = io.BytesIO(raw)
        self.addCleanup(self.reader.close)
        stream = PC._CipherStream()
        self.binding = PC._track(PC._CipherInput(stream, self.owner, self.reader,
            len(raw) if size is None else size, hashlib.sha256()))
        PC._CIPHER_STREAMS[id(stream)] = self.binding
        return stream

    def test_forward_seek_consumes_and_hashes_original_bytes(self):
        stream = self.stream()
        self.assertEqual(self.check(stream.read, 2), b"ab")
        self.assertEqual(self.check(stream.seek, 3, os.SEEK_CUR), 5)
        self.assertEqual(self.check(stream.read, 1), b"f")
        self.assertEqual(self.check(stream.read, 1), b"")
        self.assertEqual(self.binding.total, 6)
        self.assertEqual(self.binding.checksum.hexdigest(), O.digest(b"abcdef"))
        self.assertEqual(sum(count for _owner, count in self.charges), 6)
        self.assertTrue(all(owner is self.owner for owner, _count in self.charges))

    def test_seek_is_not_underlying_random_access(self):
        stream = self.stream()
        self.refuses(stream.seek, -1, os.SEEK_CUR)
        self.refuses(stream.seek, 1, os.SEEK_SET)
        self.refuses(stream.seek, 7, os.SEEK_CUR)
        self.assertEqual(self.reader.tell(), 0)

    def test_truncated_forward_skip_refuses(self):
        stream = self.stream(b"abc", size=6)
        self.refuses(stream.seek, 6, os.SEEK_CUR)
        self.assertEqual(self.binding.total, 3)

    def test_extra_ciphertext_refuses_even_at_declared_eof(self):
        stream = self.stream(b"abcdef", size=5)
        self.assertEqual(self.check(stream.read, 5), b"abcde")
        self.refuses(stream.read, 1)

    def test_read_count_is_strict_and_bounded(self):
        stream = self.stream()
        for count in (True, -1, C.COPY_CHUNK + 1):
            self.refuses(stream.read, count)

    def test_foreign_stream_constructor_has_no_original_reader(self):
        self.refuses(PC._CipherStream().read, 1)

    def test_original_binding_dictionary_substitution_is_not_adopted(self):
        stream = self.stream()
        dictionary = self.binding.__dict__
        object.__setattr__(self.binding, "__dict__", dict(dictionary))
        first = self.refuses(stream.read, 1)
        object.__setattr__(self.binding, "__dict__", dictionary)
        self.assertIs(self.refuses(stream.read, 1), first)

    def test_outer_packet_limit_is576_not_plaintext512(self):
        self.assertEqual(B.posix.MAX_CIPHERTEXT_BYTES, 576 * 1024 * 1024)
        block = PC_SOURCE.split("def _ciphertext_read(", 1)[1].split("\ndef _check_ciphertext_read(", 1)[0]
        self.assertIn("B.posix._ciphertext_stream(stream,", block)
        self.assertIn('stream.read(1) == b""', block)
        self.assertIn("OUTER_PACKET_ONLY_NOT_DECRYPTED", block)
        self.assertNotIn("Snapshot(", block)


class AbortModels(ModelCase):
    def test_abort_keeps_first_failure_unknown_and_original_owner_once(self):
        first, later = O.OriginError("MODEL_FIRST"), O.OriginError("MODEL_LATER")
        anchor = SimpleNamespace(unknown=True, failure=None)
        calls = []
        def error(stage, value):
            calls.append((stage, value))
            if anchor.failure is None:
                anchor.failure = value
        def close():
            calls.append(("close", None))
            raise O.OriginError("MODEL_CLOSE_FAILED")
        owner = SimpleNamespace(error=error, close=close, _anchor=lambda: anchor)
        state = PC._track(PC._State(object(), "model-abort", object(), b"{}\n", b"", (),
            owner=owner, owners=(owner, owner)))
        self.check(PC._abort_state, state, first)
        self.check(PC._abort_state, state, later)
        self.assertIs(state.failure, first)
        self.assertIs(anchor.failure, first)
        self.assertTrue(anchor.unknown)
        self.assertEqual([name for name, _value in calls].count("close"), 1)
        self.assertEqual(PC._QUARANTINE, [owner])
        self.assertEqual(PC._OWNER_CLOSES, {})
        self.assertIsNone(state.closed)


class OwnerCloseHistoryModels(ModelCase):
    """Original PC/N code with an explicit in-memory owner, NOT native custody.

    The fixture models one successful close return and its retained row roster.
    It never calls actual C allocation/close, reads a file, or observes a clock.
    Spies delegate unchanged N graph behavior; they grant no acceptance seam.
    """

    class Resource:
        def forbidden(self, *_args, **_kwargs):
            raise AssertionError("OWNER_CLOSE_MODEL_LIVE_RESOURCE_EFFECT")

        read = write = open = reopen = close = verify = sync = forbidden

    class Owner:
        def __init__(self, pairs, *, outcome="known", raw=None, throws=None):
            rows = tuple(({"label": label, "owner": resource, "attempted": False, "closed": False},
                label, resource, False, False) for label, resource in pairs)
            self.anchor = self.original_anchor = SimpleNamespace(rows=rows)
            self.original_rows = rows
            self.owner = self.original_native = SimpleNamespace(closed=False, unknown=False, original=None)
            self.errors = self.original_errors = []
            self.finished, self.returned = False, False
            self.failure, self.returned_raw = None, None
            self.finish_calls, self.structural_calls = 0, 0
            self.outcome, self.raw_override, self.throws = outcome, raw, throws

        def _anchor(self):
            return self.anchor

        def structural(self):
            self.structural_calls += 1
            O.require(self.anchor is self.original_anchor and self.anchor.rows is self.original_rows and
                type(self.anchor.rows) is tuple and self.owner is self.original_native and
                self.errors is self.original_errors, "OWNER_CLOSE_MODEL_ORIGINAL_ROSTER")
            for row, label, resource, attempted, ended in self.anchor.rows:
                O.require(type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                    row["label"] == label and row["owner"] is resource and
                    type(attempted) is bool and type(ended) is bool and
                    row["attempted"] is attempted and row["closed"] is ended and (not ended or attempted),
                    "OWNER_CLOSE_MODEL_ROW")
            O.require(len({id(row) for row, *_rest in self.anchor.rows}) == len(self.anchor.rows) ==
                len({id(resource) for _row, _label, resource, _a, _c in self.anchor.rows}),
                "OWNER_CLOSE_MODEL_ALIAS")

        def guard(self, *_args, **_kwargs):
            raise AssertionError("OWNER_CLOSE_MODEL_LIVE_GUARD")

        acquire = close_one = guard

        def finish(self):
            O.require(not self.finished, "OWNER_CLOSE_MODEL_FINISH_ONCE")
            self.finish_calls += 1
            self.structural()
            if self.throws is not None:
                raise self.throws
            complete = self.outcome != "incomplete"
            for row, _label, _resource, _a, _c in self.anchor.rows:
                row["attempted"] = row["closed"] = complete
            self.anchor.rows = tuple((row, label, resource, complete, complete)
                for row, label, resource, _a, _c in self.anchor.rows)
            self.original_rows = self.anchor.rows
            self.finished = self.outcome != "not-finished"
            self.owner.closed = self.outcome != "not-closed"
            self.owner.unknown = self.outcome == "unknown"
            if self.outcome == "failure":
                self.failure = O.OriginError("OWNER_CLOSE_MODEL_FAILED")
            if self.outcome == "original":
                self.owner.original = O.OriginError("OWNER_CLOSE_MODEL_NATIVE_FAILED")
            if self.outcome == "errors":
                self.errors.append("OWNER_CLOSE_MODEL_ERROR")
            self.structural()
            self.returned_raw = self.raw_override if self.raw_override is not None else O.encoded({
                "schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
                "resources": [{"ordinal": number, "label": label, "closeAttempted": attempted, "closed": ended}
                    for number, (_row, label, _resource, attempted, ended) in enumerate(self.anchor.rows)],
                "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
            self.returned = True
            return self.returned_raw

    def setUp(self):
        super().setUp()
        self.original_graph, self.original_check = N._history_graph, N._check_history
        self.install(C, "_PrimaryOwner", self.Owner)
        def effect(*_args, **_kwargs):
            self.fail("OWNER_CLOSE_MODEL_CALLED_ACTUAL_LIVE_SUPPLIER")
        for module, names in ((PC.time, ("time", "monotonic")), (O.clocks, ("observe",)),
                (C, ("_private", "_snapshot", "_snapshot_reader", "_consume")),
                (B.Owner, ("end", "close_one", "close")), (B.posix, ("_deadline",)),
                (B, ("cancellation",))):
            for name in names:
                self.install(module, name, effect)

    def fixture(self, count=3, *, labels=None, resources=None, **kwargs):
        labels = ("reader",) * count if labels is None else labels
        resources = tuple(self.Resource() for _label in labels) if resources is None else resources
        self.assertEqual(len(labels), len(resources))
        return self.Owner(tuple(zip(labels, resources)), **kwargs)

    def watch(self, owner):
        calls = SimpleNamespace(roots=[], graphs=[], checks=[])
        def graph(*roots):
            self.assertTrue(owner.returned, "history must follow modeled normal finish return")
            self.assertEqual(owner.finish_calls, 1)
            calls.roots.append(roots)
            result = self.original_graph(*roots)
            calls.graphs.append(result)
            return result
        def check(nodes):
            calls.checks.append(nodes)
            return self.original_check(nodes)
        self.install(N, "_history_graph", graph)
        self.install(N, "_check_history", check)
        return calls

    def close(self, owner):
        return self.check(PC._close_owner, owner)

    def changed_graph(self, change):
        owner = self.fixture()
        closed = self.close(owner)
        graph = closed.graph
        object.__setattr__(closed, "graph", change(graph))
        first = self.refuses(PC._check_owner_close, closed)
        object.__setattr__(closed, "graph", graph)
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        self.assertIs(PC._OWNER_CLOSES[id(owner)], closed)
        self.assertEqual(owner.finish_calls, 1)

    def test_mandatory4121_rows_keep_every_original_after_one_model_close(self):
        labels = ("directory", "directory") + ("reader", "writer", "reader") * 1373
        owner = self.fixture(labels=labels)
        calls = self.watch(owner)
        closed = self.close(owner)
        self.assertIs(closed.owner, owner)
        self.assertIs(closed.anchor, owner.original_anchor)
        self.assertIs(closed.rows, owner.original_rows)
        self.assertIs(closed.raw, owner.returned_raw)
        self.assertIs(PC._OWNER_CLOSES[id(owner)], closed)
        self.assertEqual(len(closed.rows), 4121)
        self.assertEqual(1 + len({id(value) for row in closed.rows for value in (row, row[0], row[2])}), 12364)
        self.assertIs(type(closed.graph), tuple)
        self.assertEqual(len(closed.graph), 4121)
        self.assertEqual((len(calls.roots), len(calls.graphs), len(calls.checks)), (4121, 4121, 4121))
        for row, history, roots, graph, checked in zip(closed.rows, closed.graph,
                calls.roots, calls.graphs, calls.checks):
            self.assertIs(history[0], row)
            self.assertEqual(len(roots), 1)
            self.assertIs(roots[0], row)
            self.assertIs(history[1], graph)
            self.assertIs(checked, graph)
            # The exact immutable row tuple is visited/counted, not emitted;
            # its mutable ledger and original resource remain separate pins.
            self.assertEqual(len(graph), 2)
            self.assertEqual({id(node[0]) for node in graph}, {id(row[0]), id(row[2])})
        error = self.refuses(self.original_graph, closed.rows)
        self.assertIn("RECIPIENT_HISTORY_LIMIT", str(error))
        self.assertIs(self.check(PC._check_owner_close, closed), closed)
        self.assertEqual(len(calls.checks), 8242)
        self.assertTrue(all(checked is history[1] for checked, history in zip(calls.checks[4121:], closed.graph)))
        self.assertEqual(owner.finish_calls, 1)

    def test_unchanged_whole_graph3333_boundary_not_an_increased_limit(self):
        rows = self.fixture(3333).anchor.rows
        # Original root +3333 tuples +6666 mutable/opaque nodes =10000 visits.
        self.assertEqual(len(self.check(self.original_graph, rows)), 6666)
        rows = self.fixture(3334).anchor.rows
        self.assertIn("RECIPIENT_HISTORY_LIMIT", str(self.refuses(self.original_graph, rows)))

    def test_original_nonempty10000_row_bound_precedes_any_graph(self):
        self.assertEqual(CD.MAX_NODES, 10000)
        for count in (0, CD.MAX_NODES + 1):
            with self.subTest(count=count):
                owner = self.fixture(count)
                calls = self.watch(owner)
                self.assertIn("OWNER_CLOSE_BOUND", str(self.refuses(PC._close_owner, owner)))
                self.assertTrue(owner.returned)
                self.assertEqual(owner.finish_calls, 1)
                self.assertEqual(calls.roots, [])
                self.assertNotIn(id(owner), PC._OWNER_CLOSES)

    def test_original_two_mib_raw_bound_precedes_any_graph(self):
        self.assertEqual(CD.LIMIT, 2 * 1024 * 1024)
        owner = self.fixture(raw=b"x" * (CD.LIMIT + 1))
        calls = self.watch(owner)
        self.assertIn("OWNER_CLOSE_BOUND", str(self.refuses(PC._close_owner, owner)))
        self.assertEqual(calls.roots, [])
        self.assertTrue(owner.returned)
        self.assertNotIn(id(owner), PC._OWNER_CLOSES)

    def test_first_middle_old_cutoff_last_row_mutations_are_all_checked(self):
        for index in (0, 2060, 3333, 4120):
            with self.subTest(index=index):
                owner = self.fixture(4121)
                calls = self.watch(owner)
                closed = self.close(owner)
                calls.checks.clear()
                closed.rows[index][0]["label"] = "changed-retired-row"
                self.assertIn("RECIPIENT_HISTORY_CHANGED", str(self.refuses(PC._check_owner_close, closed)))
                self.assertEqual(len(calls.checks), index + 1)
                self.assertTrue(all(checked is history[1]
                    for checked, history in zip(calls.checks, closed.graph[:index + 1])))
                self.assertEqual(owner.finish_calls, 1)

    def test_original_resource_substitution_is_not_matching_row_data(self):
        owner = self.fixture()
        closed = self.close(owner)
        closed.rows[-1][0]["owner"] = self.Resource()
        self.assertIn("RECIPIENT_HISTORY_CHANGED", str(self.refuses(PC._check_owner_close, closed)))
        self.assertEqual(owner.finish_calls, 1)

    def test_original_resource_alias_after_close_is_not_adopted(self):
        owner = self.fixture()
        closed = self.close(owner)
        closed.rows[-1][0]["owner"] = closed.rows[0][2]
        self.refuses(PC._check_owner_close, closed)
        self.assertEqual(owner.finish_calls, 1)

    def test_model_full_owner_alias_check_still_precedes_graph_registration(self):
        resource = self.Resource()
        owner = self.fixture(2, resources=(resource, resource))
        calls = self.watch(owner)
        self.assertIn("OWNER_CLOSE_MODEL_ALIAS", str(self.refuses(PC._close_owner, owner)))
        self.assertEqual(calls.roots, [])
        self.assertFalse(owner.returned)
        self.assertNotIn(id(owner), PC._OWNER_CLOSES)

    def test_value_equal_row_dictionary_substitution_is_not_original(self):
        owner = self.fixture()
        closed = self.close(owner)
        row = closed.rows[0]
        replacement = (dict(row[0]), *row[1:])
        owner.anchor.rows = (replacement, *closed.rows[1:])
        self.assertEqual(owner.anchor.rows, closed.rows)
        self.assertIsNot(owner.anchor.rows[0][0], row[0])
        self.refuses(PC._check_owner_close, closed)

    def test_false_attempted_or_closed_flags_are_not_repaired_from_saved_data(self):
        for name in ("attempted", "closed"):
            with self.subTest(name=name):
                owner = self.fixture()
                closed = self.close(owner)
                closed.rows[-1][0][name] = False
                self.refuses(PC._check_owner_close, closed)
                self.assertIs(closed.rows[-1][0][name], False)
                self.assertEqual(owner.finish_calls, 1)

    def test_replacement_anchor_with_same_rows_is_not_original(self):
        owner = self.fixture()
        closed = self.close(owner)
        owner.anchor = SimpleNamespace(rows=closed.rows)
        self.assertIn("ORIGINAL_CLOSE_ROWS", str(self.refuses(PC._check_owner_close, closed)))

    def test_value_equal_whole_rows_tuple_is_not_original(self):
        owner = self.fixture()
        closed = self.close(owner)
        owner.anchor.rows = tuple(list(closed.rows))
        self.assertEqual(owner.anchor.rows, closed.rows)
        self.assertIsNot(owner.anchor.rows, closed.rows)
        self.refuses(PC._check_owner_close, closed)

    def test_value_equal_row_tuple_is_not_original(self):
        owner = self.fixture()
        closed = self.close(owner)
        replacement = tuple(list(closed.rows[0]))
        owner.anchor.rows = (replacement, *closed.rows[1:])
        self.assertEqual(owner.anchor.rows, closed.rows)
        self.assertIsNot(replacement, closed.rows[0])
        self.refuses(PC._check_owner_close, closed)

    def test_reordered_whole_rows_cannot_repair_retained_correspondence(self):
        owner = self.fixture()
        closed = self.close(owner)
        owner.anchor.rows = tuple(reversed(closed.rows))
        first = self.refuses(PC._check_owner_close, closed)
        owner.anchor.rows = closed.rows
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)

    def test_truncated_histories_are_refused_and_sticky_after_repair(self):
        self.changed_graph(lambda graph: graph[:-1])

    def test_reordered_or_duplicated_history_rows_are_not_adopted(self):
        self.changed_graph(lambda graph: (graph[1], graph[0], *graph[2:]))
        self.changed_graph(lambda graph: (graph[0], graph[0], *graph[2:]))

    def test_missing_foreign_or_mutable_inner_graph_is_not_adopted(self):
        self.changed_graph(lambda graph: ((graph[0][0], ()), *graph[1:]))
        self.changed_graph(lambda graph: ((graph[0][0], graph[1][1]), *graph[1:]))
        self.changed_graph(lambda graph: ((graph[0][0], list(graph[0][1])), *graph[1:]))

    def test_foreign_equal_close_has_no_original_pin_or_registration(self):
        owner = self.fixture()
        closed = self.close(owner)
        foreign = PC._OwnerClose(closed.owner, closed.anchor, closed.rows, closed.raw, closed.graph, closed.methods)
        self.assertEqual(foreign, closed)
        self.refuses(PC._check_owner_close, foreign)
        self.assertNotIn(id(foreign), PC._PINS)
        self.assertNotIn(id(foreign), PC._PIN_FAILURES)
        self.assertIs(PC._OWNER_CLOSES[id(owner)], closed)
        self.assertIs(self.check(PC._check_owner_close, closed), closed)

    def test_replacement_close_dictionary_keeps_first_failure_after_repair(self):
        owner = self.fixture()
        closed = self.close(owner)
        dictionary = closed.__dict__
        object.__setattr__(closed, "__dict__", dict(dictionary))
        first = self.refuses(PC._check_owner_close, closed)
        object.__setattr__(closed, "__dict__", dictionary)
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)

    def test_unknown_failed_error_incomplete_close_mints_no_graph_or_currency(self):
        for outcome in ("unknown", "failure", "original", "errors", "incomplete", "not-closed", "not-finished"):
            with self.subTest(outcome=outcome):
                owner = self.fixture(outcome=outcome)
                calls = self.watch(owner)
                self.refuses(PC._close_owner, owner)
                self.assertTrue(owner.returned)
                self.assertEqual(owner.finish_calls, 1)
                self.assertEqual(calls.roots, [])
                self.assertNotIn(id(owner), PC._OWNER_CLOSES)
                self.assertEqual(PC._PINS, {})

    def test_throwing_finish_never_creates_a_graph_or_registered_close(self):
        error = O.OriginError("OWNER_CLOSE_MODEL_THROWN_FIRST")
        owner = self.fixture(throws=error)
        calls = self.watch(owner)
        self.assertIs(self.refuses(PC._close_owner, owner), error)
        self.assertFalse(owner.returned)
        self.assertEqual(owner.finish_calls, 1)
        self.assertEqual(calls.roots, [])
        self.assertNotIn(id(owner), PC._OWNER_CLOSES)

    def test_nested_mutation_repair_rethrows_same_first_error_before_later_checks(self):
        owner = self.fixture()
        calls = self.watch(owner)
        closed = self.close(owner)
        row = closed.rows[-1][0]
        label = row["label"]
        row["label"] = "detected-change"
        first = self.refuses(PC._check_owner_close, closed)
        row["label"] = label
        calls.checks.clear()
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        row["closed"] = False
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        self.assertIs(PC._PIN_FAILURES[id(closed)][0], closed)
        self.assertIs(PC._PIN_FAILURES[id(closed)][1], first)
        self.assertEqual(calls.checks, [])
        self.assertEqual(owner.finish_calls, 1)

    def test_repaired_original_close_registry_stays_failed(self):
        owner = self.fixture()
        closed = self.close(owner)
        PC._OWNER_CLOSES[id(owner)] = object()
        first = self.refuses(PC._check_owner_close, closed)
        PC._OWNER_CLOSES[id(owner)] = closed
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)

    def test_late_unknown_is_never_cleared_and_repair_cannot_revive_close(self):
        owner = self.fixture()
        closed = self.close(owner)
        owner.owner.unknown = True
        first = self.refuses(PC._check_owner_close, closed)
        self.assertTrue(owner.owner.unknown)
        owner.owner.unknown = False
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        self.assertEqual(owner.finish_calls, 1)

    def test_late_owner_failure_remains_same_close_failure_after_repair(self):
        owner = self.fixture()
        closed = self.close(owner)
        owner.failure = O.OriginError("OWNER_CLOSE_MODEL_LATE_FAILURE")
        first = self.refuses(PC._check_owner_close, closed)
        self.assertIsNotNone(owner.failure)
        owner.failure = None
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        self.assertEqual(owner.finish_calls, 1)

    def test_owner_field_substitution_latches_against_original_close_pin(self):
        owner = self.fixture()
        closed = self.close(owner)
        foreign = object()
        object.__setattr__(closed, "owner", foreign)
        first = self.refuses(PC._check_owner_close, closed)
        object.__setattr__(closed, "owner", owner)
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        self.assertIs(PC._OWNER_CLOSES[id(owner)], closed)
        self.assertNotIn(id(foreign), PC._OWNER_CLOSES)
        self.assertEqual(owner.finish_calls, 1)

    def test_method_replacement_refuses_without_invoking_it_or_reclosing(self):
        owner = self.fixture()
        closed = self.close(owner)
        def forbidden(_owner):
            self.fail("REPLACED_STRUCTURAL_METHOD_WAS_INVOKED")
        with patch.object(self.Owner, "structural", forbidden):
            first = self.refuses(PC._check_owner_close, closed)
        self.assertIs(self.refuses(PC._check_owner_close, closed), first)
        self.assertEqual(owner.finish_calls, 1)

    def test_later_validation_is_passive_with_all_live_suppliers_trapped(self):
        owner = self.fixture()
        calls = self.watch(owner)
        closed = self.close(owner)
        structural = owner.structural_calls
        calls.checks.clear()
        for _repeat in range(3):
            self.assertIs(self.check(PC._check_owner_close, closed), closed)
        self.assertEqual(len(calls.checks), 9)
        self.assertEqual(len(calls.roots), 3)
        self.assertEqual(owner.structural_calls, structural + 3)
        self.assertEqual(owner.finish_calls, 1)

    def test_second_close_registration_never_calls_modeled_finish_again(self):
        owner = self.fixture()
        closed = self.close(owner)
        self.assertIn("OWNER_CLOSE_ONCE", str(self.refuses(PC._close_owner, owner)))
        self.assertEqual(owner.finish_calls, 1)
        self.assertIs(PC._OWNER_CLOSES[id(owner)], closed)
        self.assertIs(self.check(PC._check_owner_close, closed), closed)

    def test_single_overlarge_row_still_obeys_original_n_graph_limit(self):
        expanded = tuple(object() for _number in range(10000))
        owner = self.fixture(1, resources=(expanded,))
        calls = self.watch(owner)
        self.assertIn("RECIPIENT_HISTORY_LIMIT", str(self.refuses(PC._close_owner, owner)))
        self.assertTrue(owner.returned)
        self.assertEqual(owner.finish_calls, 1)
        self.assertEqual(len(calls.roots), 1)
        self.assertEqual(calls.graphs, [])
        self.assertEqual(calls.checks, [])
        self.assertNotIn(id(owner), PC._OWNER_CLOSES)
        self.assertEqual(PC._PINS, {})


if __name__ == "__main__":
    unittest.main(failfast=True)
