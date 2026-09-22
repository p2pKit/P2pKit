#!/usr/bin/env python3
"""Disjoint boot/Steps/output controls; native identities and sender are MODELS.

No old sender, receiver, complete reader, fixture generator or accepted test
method runs. Only the new sidecar/file-command code uses tiny ordinary-UID
files. Fixed native API calls are mocked; no real boot/provider/hosted result.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid


spec = importlib.util.spec_from_file_location("continuity_receiver_models",
    Path(__file__).with_name("hosted-initial-recipient-receiving-test.py"))
R = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = R
spec.loader.exec_module(R)  # Pre-project process/network/native audit guard.
N, S, O, I, Q = R.N, R.S, R.O, R.I, R.Q
C = N.continuity
UUID = b"00112233-4455-6677-8899-aabbccddeeff"
BOOT = "b" * 64
OUTPUT_NAME = "set_output_00112233-4455-6677-8899-aabbccddeeff"


class ContinuityControls(unittest.TestCase):
    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "file controls require an actual ordinary UID")
        self.addCleanup(C.QUARANTINE.clear)  # Fake close failures below actually close their tiny test fd first.

    def test_exact_uuid_grammar_and_domain_separated_digest_only(self):
        raw = uuid.UUID(UUID.decode()).bytes
        self.assertEqual(C._uuid_bytes(UUID + b"\n", b"\n"), raw)
        for value in (UUID, UUID + b"\0", UUID + b"\nextra", b"0" * 36 + b"\n",
                b"00000000-0000-0000-0000-000000000000\n"):
            with self.subTest(value=value), self.assertRaises(C.ContinuityError):
                C._uuid_bytes(value, b"\n")
        with patch.object(C.clocks.processes, "host_role", return_value="linux-x64"), patch.object(C, "_linux_boot", return_value=raw):
            self.assertEqual(C.boot_digest("linux-x64"), C.hashlib.sha256(b"P2pKit hosted boot v1\0linux-x64\0" + raw).hexdigest())
            with self.assertRaisesRegex(C.ContinuityError, "BOOT_NATIVE_ROLE"):
                C.boot_digest("macos-arm64")

    def test_linux_fixed_kernel_file_bounded_read_and_known_close(self):
        info = SimpleNamespace(st_mode=stat.S_IFREG | 0o444, st_uid=0, st_dev=1, st_ino=2)
        with patch.object(C.sys, "platform", "linux"), patch.object(C.Path, "lstat", return_value=info), \
                patch.object(C.os, "open", return_value=90) as opened, patch.object(C.os, "fstat", return_value=info), \
                patch.object(C.os, "read", side_effect=[UUID + b"\n", b""]) as read, patch.object(C.os, "close") as close:
            self.assertEqual(C._linux_boot(), uuid.UUID(UUID.decode()).bytes)
            self.assertEqual(opened.call_args.args[0], Path("/proc/sys/kernel/random/boot_id"))
            self.assertEqual(read.call_args_list[0].args, (90, 64))
            self.assertEqual(read.call_args_list[1].args, (90, 1))
            close.assert_called_once_with(90)

    def test_linux_mutation_or_failed_close_cannot_produce_boot_identity(self):
        info = SimpleNamespace(st_mode=stat.S_IFREG | 0o444, st_uid=0, st_dev=1, st_ino=2)
        changed = SimpleNamespace(st_mode=stat.S_IFREG | 0o444, st_uid=0, st_dev=1, st_ino=3)
        with patch.object(C.sys, "platform", "linux"), patch.object(C.Path, "lstat", return_value=info), \
                patch.object(C.os, "open", return_value=90), patch.object(C.os, "fstat", return_value=changed), \
                patch.object(C.os, "close") as close:
            with self.assertRaisesRegex(C.ContinuityError, "BOOT_KERNEL_FILE_CHANGED"):
                C._linux_boot()
            close.assert_called_once_with(90)
        first = R.FirstFailure("SYNTHETIC_BOOT_READ")
        with patch.object(C.sys, "platform", "linux"), patch.object(C.Path, "lstat", return_value=info), \
                patch.object(C.os, "open", return_value=91), patch.object(C.os, "fstat", return_value=info), \
                patch.object(C.os, "read", side_effect=first), patch.object(C.os, "close", side_effect=OSError("SYNTHETIC_CLOSE")):
            with self.assertRaises(R.FirstFailure) as caught:
                C._linux_boot()
            self.assertIs(caught.exception, first)
            self.assertEqual(C.QUARANTINE, [91])
            with self.assertRaisesRegex(C.ContinuityError, "BOOT_NATIVE_ROLE"):
                C.boot_digest("linux-x64")

    def test_darwin_fixed_sysctl_status_size_and_nul_abi(self):
        case = self
        class Query:
            status, size, ending = 0, 37, b"\0"
            def __call__(self, name, data, size, write, write_size):
                case.assertEqual((name, write, write_size), (b"kern.bootsessionuuid", None, 0))
                case.assertEqual(size._obj.value, 37)
                data.raw = UUID + self.ending
                size._obj.value = self.size
                return self.status
        query = Query()
        with patch.object(C.sys, "platform", "darwin"), patch.object(C.ctypes, "CDLL",
                return_value=SimpleNamespace(sysctlbyname=query)) as library:
            self.assertEqual(C._darwin_boot(), uuid.UUID(UUID.decode()).bytes)
            self.assertEqual(library.call_args.args, ("/usr/lib/libSystem.B.dylib",))
            for status, size, ending in ((-1, 37, b"\0"), (0, 36, b"\0"), (0, 37, b"\n")):
                query.status, query.size, query.ending = status, size, ending
                with self.subTest(status=status, size=size, ending=ending), self.assertRaises(C.ContinuityError):
                    C._darwin_boot()

    def test_windows_fixed_nt_status_struct_size_firmware_and_guid_abi(self):
        case = self
        class Query:
            status, size, firmware = 0, 32, 2
            raw = uuid.UUID(UUID.decode()).bytes_le
            def __call__(self, number, data, size, returned):
                case.assertEqual((number, size), (90, 32))
                data._obj.identifier[:] = self.raw
                data._obj.firmware = self.firmware
                returned._obj.value = self.size
                return self.status
        query = Query()
        with patch.object(C.sys, "platform", "win32"), patch.object(C.ctypes, "WinDLL", create=True,
                return_value=SimpleNamespace(NtQuerySystemInformation=query)) as library:
            self.assertEqual(C._windows_boot(), uuid.UUID(UUID.decode()).bytes)
            library.assert_called_once_with("ntdll.dll", use_last_error=True, winmode=0x00000800)
            for status, size, firmware, raw in ((1, 32, 2, query.raw), (0, 24, 2, query.raw),
                    (0, 32, 3, query.raw), (0, 32, 2, bytes(16))):
                query.status, query.size, query.firmware, query.raw = status, size, firmware, raw
                with self.subTest(status=status, size=size, firmware=firmware), self.assertRaises(C.ContinuityError):
                    C._windows_boot()

    def output_fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="continuity-output-model-")
        self.addCleanup(temp.cleanup)
        parent = Path(temp.name)
        directory = parent / "_runner_file_commands"
        directory.mkdir(mode=0o700)
        output = directory / OUTPUT_NAME
        output.touch(mode=0o600)
        environment = patch.dict(os.environ, {"RUNNER_TEMP": str(parent), "GITHUB_OUTPUT": str(output)}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        return parent, output

    def test_runner_file_command_contains_only_exact_named_hashes_and_readback(self):
        _parent, output = self.output_fixture()
        checks = []
        C.append_outputs({"recipientSenderSha256": "a" * 64, "recipientStepSha256": "b" * 64}, lambda: checks.append(True))
        self.assertEqual(output.read_text(), "recipientSenderSha256=" + "a" * 64 + "\nrecipientStepSha256=" + "b" * 64 + "\n")
        self.assertGreaterEqual(len(checks), 4)
        self.assertEqual(C.QUARANTINE, [])

    def test_nonempty_wrong_path_or_nonhash_file_commands_are_refused(self):
        parent, output = self.output_fixture()
        output.write_bytes(b"preserved\n")
        with self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_FILE"):
            C.append_outputs({"initializationSha256": "a" * 64}, lambda: None)
        self.assertEqual(output.read_bytes(), b"preserved\n")
        os.environ["GITHUB_OUTPUT"] = str(parent / OUTPUT_NAME)
        with self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_PATH"):
            C.append_outputs({"initializationSha256": "a" * 64}, lambda: None)
        with self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_FIELDS"):
            C.append_outputs({"initializationSha256": "SYNTHETIC_NOT_A_HASH"}, lambda: None)
        with self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_FIELDS"):
            C.append_outputs({"rawBootId": UUID.decode()}, lambda: None)

    def test_failed_actual_output_close_is_quarantined_not_success(self):
        self.output_fixture()
        closed, original = [], os.close
        def fail(descriptor):
            original(descriptor)  # Actual test handle is closed; the reported outcome is deliberately UNKNOWN.
            closed.append(descriptor)
            raise OSError("SYNTHETIC_CLOSE_RETURN_UNKNOWN")
        with patch.object(C.os, "close", fail), self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_CLOSE_UNKNOWN"):
            C.append_outputs({"initializationSha256": "a" * 64}, lambda: None)
        self.assertEqual(C.QUARANTINE, closed)
        self.assertEqual(len(closed), 1)
        with self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_FIELDS"):
            C.append_outputs({"initializationSha256": "a" * 64}, lambda: None)


class SenderStepControls(unittest.TestCase):
    def setUp(self):
        self.rx = R.ReceivingControls("runTest")
        self.addCleanup(self.rx.doCleanups)
        self.rx.setUp()
        self.fx, self.stack = self.rx.fx, self.rx.fx.stack
        self.addCleanup(N._SENDER_STEP_ATTEMPTS.clear)
        self.addCleanup(C.QUARANTINE.clear)
        rows = dict(self.rx.graph)
        clock, ns = self.rx.clock, self.fx.fixture.ns
        self.cancelled = self.fx.cancelled
        state = SimpleNamespace(clock=clock, read_end=ns + 30 * O.NS, read_local=ns / O.NS + 30,
            local_last=ns / O.NS, claim=object(), cancelled=lambda: S.cancellation(self.cancelled))
        start = O.parse(rows["P/service/start.json"])
        captured = (rows["P/context.json"], tuple((name, rows["P/acquisition-queries/" + name + ".bin"])
            for name in N.ORIGINAL_KEYS), start["invocation"], start["startedNs"], start["workEndNs"])
        match = N.acquisition.stages.BootstrapMatch(rows["P/acquisition-queries/match.bin"])
        worker = N.initial_identity.bind_worker_match(match, event_raw=rows["P/acquisition-queries/event.bin"],
            policy_raw=rows["P/acquisition-queries/candidate_policy_raw.bin"], now=R.F.F.F.FIRST1)
        original = SimpleNamespace(match_raw=match.record, identity_fields=N._worker_fields(worker),
            worker_originals=captured, proposal_raw=rows["P/worker-allocation-proposal.json"])
        result = N._RecipientValidationReturn(b"EXPLICIT_ORIGINAL_SENDER_MODEL_NOT_EVIDENCE\n")
        self.calls, case = [], self
        class Sender:
            def __init__(self):
                self.clock, self.last, self.local_end = clock, ns, state.read_local
                self.bad_return = False
            def now(self, *, final=False, minimum=0, limit=None):
                case.assertTrue(final)
                case.assertLess(len(case.calls), 2, "accepted sender has exactly two final calls")
                case.calls.append((minimum, limit))
                case.assertLessEqual(limit, state.read_end)
                self.last = minimum - 1 if self.bad_return else O.clocks.checked_now(clock, minimum_ns=minimum)
                return self.last
            def deadline(self, *_args, **_kwargs):
                raise AssertionError("ORIGINAL_SENDER_DEADLINE_MUST_NOT_RUN")
        self.sender = Sender()
        saved = (result, result.raw, None, state, None, None, None)
        self.stack.enter_context(patch.object(N, "_RECIPIENT_RETURNS", {id(result): saved}))
        self.stack.enter_context(patch.object(N, "_RECIPIENT_SENDERS", {id(result): (result, saved, self.sender)}))
        def checked(value):
            self.assertIs(value, result)
            return value
        self.stack.enter_context(patch.object(N, "check_recipient_validation_return", side_effect=checked))
        self.stack.enter_context(patch.object(N, "_recipient_claim", return_value=(None, original)))
        self.stack.enter_context(patch.object(C, "boot_digest", return_value=BOOT))
        self.value = S.public_result(N.RECIPIENT_OUTPUT_SCOPE, "recipientSenderSha256", b"EXPLICIT_SENDER_MANIFEST_MODEL\n")
        self.returned = self.value, self.sender, state.read_end
        os.environ.pop(O.wire.TOKEN_ENV, None)  # Models the ORIGINAL successful sender's credential disposal.
        directory = self.fx.base / "_runner_file_commands"
        directory.mkdir(mode=0o700)
        self.output = directory / OUTPUT_NAME
        self.output.touch(mode=0o600)
        os.environ["GITHUB_OUTPUT"] = str(self.output)

    def retain(self):
        return N._retain_sender_step(self.returned, self.cancelled, BOOT)

    def test_sidecar_closes_before_exactly_two_original_guarded_sender_calls(self):
        returned = self.retain()
        self.assertIs(returned[0], self.value)
        self.assertEqual(self.calls, [])
        self.assertEqual(returned[2], self.returned[2])
        raw = (N._step_path() / C.STEP_FILE).read_bytes()
        sidecar = N._step_record(raw)
        self.assertEqual(sidecar["writerReturn"], "PENDING_OWNER_CLOSE")
        self.assertEqual(sidecar["originalStepOutcome"], "NOT_OBSERVED")
        self.assertEqual(sidecar["sample"], "AFTER_SENDER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN")
        minimum = returned[1].last
        out = SimpleNamespace(buffer=SimpleNamespace(write=lambda data: len(data), flush=lambda: None))
        with patch.object(S.sys, "stdout", out):
            S.guarded(lambda _cancelled: returned)
        self.assertEqual(len(self.calls), 2)
        self.assertGreaterEqual(self.calls[0][0], minimum)
        self.assertGreaterEqual(self.calls[1][0], self.calls[0][0])
        with self.assertRaises(I.AdmissionError):
            returned[1].now(final=True)
        self.assertEqual(len(self.calls), 2)
        lines = dict(line.split("=", 1) for line in self.output.read_text().splitlines())
        self.assertEqual(lines, {"recipientSenderSha256": self.value["recipientSenderSha256"], "recipientStepSha256": O.digest(raw)})

    def test_failed_final_highwater_cannot_be_restored_or_call_sender_again(self):
        returned = self.retain()
        self.sender.bad_return = True
        with self.assertRaisesRegex(I.AdmissionError, "STEP_SENDER_HIGHWATER"):
            returned[1].now(final=True)
        self.sender.bad_return = False
        with self.assertRaises(I.AdmissionError):
            returned[1].now(final=True)
        self.assertEqual(len(self.calls), 1)

    def test_failed_deadline_cannot_restore_original_sender_handoff(self):
        returned = self.retain()
        with self.assertRaisesRegex(I.AdmissionError, "STEP_METADATA_IO_ONLY"):
            returned[1].deadline(1)
        self.fx.fixture.ns += O.NS  # Valid advancing clocks do not restore a failed original.
        with self.assertRaisesRegex(I.AdmissionError, "STEP_METADATA_NOT_LIVE"):
            returned[1].now(final=True, limit=returned[2])
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(I.AdmissionError, "STEP_SENDER_ALREADY_CLAIMED"):
            self.retain()

    def test_local_rollback_between_metadata_and_guarded_never_reopens_sender(self):
        returned = self.retain()
        previous = self.fx.fixture.ns
        self.fx.fixture.ns -= O.NS
        with self.assertRaisesRegex(I.AdmissionError, "STEP_LOCAL_BACKWARDS"):
            returned[1].now(final=True)
        self.fx.fixture.ns = previous
        with self.assertRaises(I.AdmissionError):
            returned[1].now(final=True)
        self.assertEqual(self.calls, [])

    def test_metadata_scope_cannot_borrow_past_original_sender_read_end(self):
        def late(_values, check):
            self.fx.fixture.ns = self.returned[2]
            check()
        with patch.object(C, "append_outputs", side_effect=late), self.assertRaisesRegex(I.AdmissionError, "STEP_ORIGINAL_READ_EXPIRED"):
            self.retain()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.output.read_bytes(), b"")

    def test_unknown_metadata_owner_close_blocks_outputs_and_retains_owner(self):
        original, first, owners = S.Owner.close, R.FirstFailure("SYNTHETIC_METADATA_CLOSE"), []
        def close(owner):
            original(owner)
            owners.append(owner)
            raise first
        with patch.object(S.Owner, "close", close), self.assertRaises(R.FirstFailure) as caught:
            self.retain()
        self.assertIs(caught.exception, first)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertEqual(len(owners), 1)
        self.assertTrue(any(owner is owners[0] for owner in S.QUARANTINE))

    def test_changed_boot_before_sidecar_never_reaches_original_output_fence(self):
        with patch.object(C, "boot_digest", return_value="c" * 64), self.assertRaisesRegex(I.AdmissionError, "STEP_SENDER_BOOT_CHANGED"):
            self.retain()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.output.read_bytes(), b"")
        with self.assertRaisesRegex(I.AdmissionError, "STEP_SENDER_ALREADY_CLAIMED"):
            self.retain()


if __name__ == "__main__":
    unittest.main(failfast=True)
