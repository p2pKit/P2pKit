#!/usr/bin/env python3
"""Offline finite-hint/file/caller models; never native closure or qualification."""
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HINT_SOURCE = ROOT / "scripts/hosted_command_failure_hint.py"
CALLER_SOURCE = ROOT / "scripts/run-hosted-dependency-update.py"


def offline(event, _args):
    if event.startswith("socket.") or event in (
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "ctypes.dlopen",
        "os.putenv", "os.unsetenv",
    ):
        raise AssertionError("offline hint controls attempted execution: " + event)


sys.addaudithook(offline)


def load(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


H = load("command_failure_hint_controls", HINT_SOURCE)
C = load("command_failure_caller_controls", CALLER_SOURCE)
INVOCATION, JOB = "a" * 32, "b" * 32
UNAVAILABLE = "UNAVAILABLE"
UPDATE_CODE = "PREREQUISITE_OWNER"
DRIVER_CODE = "JMDNS_ORIGINAL_OWNER"
PURPOSES = {
    "PREREQUISITES": "dependency-maintenance-prerequisites",
    "TARGET": "dependency-maintenance-jmdns-target",
    "OBSERVER": "dependency-maintenance-jmdns-observer",
    "GENERATOR": "dependency-maintenance-generator",
}
CHILDREN = {"PREREQUISITES": "_prerequisites", "TARGET": "_diagnostic-target", "OBSERVER": "_diagnostic-observer"}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def public_bytes(invocation=INVOCATION, phase="TARGET", code=DRIVER_CODE):
    return ("UNTRUSTED_V1 " + invocation + " " + phase + " " + code + "\n").encode("ascii")


def altered_stat(info, **changes):
    fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
    fields.update(changes)
    return SimpleNamespace(**fields)


class HintFixture:
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.base = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="p2pkit-hint-model-"))).resolve()
        self.root = self.base / "controller"
        self.state = self.base / "operation/state"
        self.home = self.state / "gradle-home"
        self.directory = self.state / "evidence" / INVOCATION
        for directory in (self.root, self.state.parent, self.state, self.home,
                          self.directory.parent, self.directory):
            directory.mkdir(mode=0o700)
        self.path = self.directory / "public-failure-hint.txt"
        self.start_path = self.directory / "start.json"
        self.env = {
            "P2PKIT_AUDIT_JOB_ID": JOB,
            "P2PKIT_AUDIT_OWNERSHIP_CHAIN": INVOCATION,
            "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": json.dumps([
                {"id": INVOCATION, "job": JOB, "state": str(self.state), "home": str(self.home)}
            ], separators=(",", ":")),
            "P2PKIT_AUDIT_STATE_DIR": str(self.state),
            "GRADLE_USER_HOME": str(self.home),
        }

    def write(self, path, raw):
        with path.open("xb") as stream:
            stream.write(raw)
        path.chmod(0o600)

    def start(self, phase="TARGET", **changes):
        value = {
            "schema": 1, "id": INVOCATION, "purpose": PURPOSES[phase], "kind": "command",
            "requestedArgv": [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                              str(self.root / "scripts/run-hosted-dependency-update.py"), CHILDREN[phase]],
            "cwd": str(self.root), "wrapper": str(self.root / "gradlew"), "host": "macos-arm64",
            "jobId": JOB, "gradleHome": str(self.home), "startedUtc": "2026-09-28T00:00:00+00:00",
            "ancestorInvocationIds": [], "controllerPid": os.getppid(),
            "sourceBefore": None, "sourceAfter": None, "productExitCode": None, "stopExitCode": None,
            "finalExitCode": 125, "sourceUnchanged": False, "ownedSurvivors": [], "errors": [],
            "evidenceDirectory": str(self.directory),
        }
        value.update(changes)
        self.write(self.start_path, encoded(value))
        return value


class HintControls(HintFixture, unittest.TestCase):
    def test_fixed_public_format_and_purpose_mapping(self):
        self.assertEqual(H.BASENAME, "public-failure-hint.txt")
        self.assertEqual(H.MAX_BYTES, 128)
        self.assertEqual(H.DISCLAIMER, "HINT_NOT_CLOSURE_OR_ACCEPTANCE")
        for phase, purpose in PURPOSES.items():
            with self.subTest(phase=phase):
                self.assertEqual(H.phase_for_purpose(purpose), phase)
        for other in (None, 0, "", "TARGET", "dependency-maintenance-unknown"):
            with self.subTest(other=other):
                self.assertIsNone(H.phase_for_purpose(other))

    def test_projection_uses_exact_types_and_one_literal_argument_without_stringifying(self):
        class KnownUpdate(Exception):
            def __str__(self):
                raise AssertionError("exception must never be stringified")

        class KnownDriver(KnownUpdate):
            pass

        class UnknownSubtype(KnownUpdate):
            pass

        class UnsafeString(str):
            def __str__(self):
                raise AssertionError("argument must never be coerced")

        class UnsafeArgument:
            def __str__(self):
                raise AssertionError("private argument must never be stringified")

            def __repr__(self):
                raise AssertionError("private argument must never be represented")

        options = {"update_error_type": KnownUpdate, "driver_error_type": KnownDriver}
        self.assertIn(UPDATE_CODE, H.UPDATE_CODES)
        self.assertIn(DRIVER_CODE, H.DRIVER_CODES)
        for kind, codes in ((KnownUpdate, H.UPDATE_CODES), (KnownDriver, H.DRIVER_CODES)):
            for code in codes:
                self.assertEqual(H.failure_code(kind(code), **options), code)
        for error in (KnownUpdate(), KnownUpdate(UPDATE_CODE, "extra"),
                      KnownUpdate("PRIVATE_MODEL_TEXT_NOT_FOR_PUBLIC_OUTPUT"),
                      KnownUpdate(UnsafeString(UPDATE_CODE)), KnownUpdate(UnsafeArgument()),
                      KnownUpdate(DRIVER_CODE), KnownDriver(UPDATE_CODE), UnknownSubtype(UPDATE_CODE),
                      ValueError(UPDATE_CODE), KeyboardInterrupt()):
            self.assertEqual(H.failure_code(error, **options), "PRIVATE_FAILURE")
        self.assertEqual(H.failure_code(KnownUpdate(UPDATE_CODE)), "PRIVATE_FAILURE")

    def test_exact_public_bytes_are_only_an_untrusted_hint(self):
        self.write(self.path, public_bytes())
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)
        self.assertEqual(self.path.read_bytes(), public_bytes())
        self.assertFalse((self.directory / "receipt.json").exists())

    def test_missing_malformed_partial_foreign_or_oversized_hint_is_unavailable(self):
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        samples = (
            b"", b"UNTRUSTED_V1 ", public_bytes()[:-1], public_bytes() + b"\n", public_bytes() + b"extra",
            public_bytes(invocation="c" * 32), public_bytes(phase="OBSERVER"),
            public_bytes(code="NON_ALLOWLISTED_PRIVATE_MODEL_TEXT"),
            public_bytes().replace(b"UNTRUSTED_V1", b"UNTRUSTED_V2"),
            public_bytes().replace(b" ", b"  ", 1), b"\xff", b"x" * 129,
        )
        for number, raw in enumerate(samples):
            with self.subTest(case=number):
                self.write(self.path, raw)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
                self.assertEqual(self.path.read_bytes(), raw)
                self.path.unlink()

    def test_parent_selectors_cannot_redirect_hint_reads(self):
        self.write(self.path, public_bytes())
        for invocation, phase in (("../" + INVOCATION, "TARGET"), (INVOCATION.upper(), "TARGET"),
                                  (INVOCATION, "../TARGET"), (INVOCATION, "UNKNOWN"), (None, "TARGET")):
            with self.subTest(invocation=invocation, phase=phase):
                self.assertEqual(H.read_hint(self.state, invocation, phase), UNAVAILABLE)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)

    def test_symlink_and_hardlink_hints_are_unavailable(self):
        original = self.base / "foreign-public-hint"
        self.write(original, public_bytes())
        self.path.symlink_to(original)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.path.unlink()
        os.link(original, self.path)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertEqual(original.read_bytes(), public_bytes())

    def test_symlinked_ancestor_is_not_followed(self):
        self.write(self.path, public_bytes())
        alias = self.base / "state-alias"
        alias.symlink_to(self.state, target_is_directory=True)
        self.assertEqual(H.read_hint(alias, INVOCATION, "TARGET"), UNAVAILABLE)
        evidence_alias = self.state / "evidence-alias"
        self.directory.rename(evidence_alias)
        self.directory.symlink_to(evidence_alias, target_is_directory=True)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)

    def test_read_open_is_nonblocking_nofollow_and_fifo_cannot_block(self):
        real_open = os.open
        seen = []

        def checked_open(path, flags, *args, **kwargs):
            if Path(path).name == self.path.name:
                self.assertTrue(flags & os.O_NONBLOCK)
                self.assertTrue(flags & os.O_NOFOLLOW)
                seen.append(flags)
            return real_open(path, flags, *args, **kwargs)

        self.write(self.path, public_bytes())
        with patch.object(H.os, "open", side_effect=checked_open):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)
            self.assertTrue(seen)
            self.path.unlink()
            os.mkfifo(self.path, 0o600)
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)

    def test_wrong_owner_or_nonprivate_modes_are_unavailable(self):
        self.write(self.path, public_bytes())
        with patch.object(H.os, "getuid", return_value=os.getuid() + 1):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        inode, real_fstat = self.path.stat().st_ino, os.fstat

        def foreign_file(descriptor):
            info = real_fstat(descriptor)
            return altered_stat(info, st_uid=info.st_uid + 1) if info.st_ino == inode else info

        with patch.object(H.os, "fstat", side_effect=foreign_file):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        for mode in (0o644, 0o660, 0o666):
            with self.subTest(mode=mode):
                self.path.chmod(mode)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.path.chmod(0o600)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)

    def test_replaced_file_during_open_is_unavailable(self):
        self.write(self.path, public_bytes())
        original_inode = self.path.stat().st_ino
        real_fstat = os.fstat
        replaced = False

        def replace_after_open(descriptor):
            nonlocal replaced
            info = real_fstat(descriptor)
            if info.st_ino == original_inode and not replaced:
                replaced = True
                self.path.rename(self.base / "original-open-hint")
                self.write(self.path, public_bytes())
            return info

        with patch.object(H.os, "fstat", side_effect=replace_after_open):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertTrue(replaced)

    def test_unstable_open_file_metadata_is_unavailable(self):
        self.write(self.path, public_bytes())
        original_inode = self.path.stat().st_ino
        real_fstat = os.fstat
        reads = 0

        def unstable(descriptor):
            nonlocal reads
            info = real_fstat(descriptor)
            if info.st_ino == original_inode:
                reads += 1
                if reads > 1:
                    return altered_stat(info, st_mtime_ns=info.st_mtime_ns + 1)
            return info

        with patch.object(H.os, "fstat", side_effect=unstable):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertGreaterEqual(reads, 2)

    def test_writer_uses_fixed_child_original_and_only_creates_bounded_public_hint(self):
        for phase in CHILDREN:
            with self.subTest(phase=phase):
                self.start(phase)
                before = set(self.base.rglob("*"))
                code = UPDATE_CODE if phase == "PREREQUISITES" else DRIVER_CODE
                self.assertIs(H.publish_child(self.root, self.env, phase, code), True)
                self.assertEqual(set(self.base.rglob("*")), before | {self.path})
                self.assertEqual(self.path.read_bytes(), public_bytes(phase=phase, code=code))
                self.assertLessEqual(self.path.stat().st_size, 128)
                self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
                self.assertEqual(H.read_hint(self.state, INVOCATION, phase), code)
                self.path.unlink()
                self.start_path.unlink()

    def test_writer_requires_complete_single_original_domain(self):
        self.start()
        cases = [{key: value for key, value in self.env.items() if key != missing} for missing in self.env]
        cases += [
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_CHAIN": INVOCATION + ":" + "c" * 32},
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "[]"},
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "{"},
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": self.env["P2PKIT_AUDIT_OWNERSHIP_DOMAINS"].replace(JOB, "c" * 32)},
            {**self.env, "GRADLE_USER_HOME": str(self.base / "foreign-home")},
        ]
        for number, env in enumerate(cases):
            with self.subTest(case=number):
                self.assertIs(H.publish_child(self.root, env, "TARGET", DRIVER_CODE), False)
                self.assertFalse(self.path.exists())

    def test_writer_rejects_missing_malformed_foreign_or_changed_original_start(self):
        self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        changes = (
            {"schema": True}, {"id": "c" * 32}, {"jobId": "c" * 32}, {"kind": "gradle"},
            {"purpose": PURPOSES["OBSERVER"]}, {"requestedArgv": ["help"]},
            {"cwd": str(self.base / "foreign")}, {"wrapper": str(self.base / "gradlew")},
            {"gradleHome": str(self.base / "foreign-home")}, {"controllerPid": os.getppid() + 1},
            {"controllerPid": True}, {"ancestorInvocationIds": ["c" * 32]},
        )
        for number, changed in enumerate(changes):
            with self.subTest(case=number):
                self.start(**changed)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
                self.assertFalse(self.path.exists())
                self.start_path.unlink()
        raw = encoded(self.start())
        self.start_path.unlink()
        for data in (raw.replace(b'"schema":1', b'"schema":1,"schema":1'), b"{", b"x" * 65537):
            self.write(self.start_path, data)
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
            self.assertFalse(self.path.exists())
            self.start_path.unlink()

    def test_writer_does_not_read_terminal_receipt_or_publish_for_nonchild_phase(self):
        self.start()
        receipt = self.directory / "receipt.json"
        self.write(receipt, b"SYNTHETIC_PRIVATE_RECEIPT_MUST_NOT_BE_READ\n")
        real_open = os.open

        def no_receipt_read(path, flags, *args, **kwargs):
            self.assertNotEqual(Path(path).name, "receipt.json")
            return real_open(path, flags, *args, **kwargs)

        with patch.object(H.os, "open", side_effect=no_receipt_read):
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertFalse(self.path.exists())
        receipt.unlink()
        for phase, code in (("GENERATOR", DRIVER_CODE), ("UNKNOWN", DRIVER_CODE), ("TARGET", "UNKNOWN")):
            self.assertIs(H.publish_child(self.root, self.env, phase, code), False)
            self.assertFalse(self.path.exists())

    def test_writer_never_clobbers_or_repairs_preexisting_hint(self):
        self.start()
        raw = b"unfinished prior public hint"
        self.write(self.path, raw)
        self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)

    def test_short_write_is_unavailable_without_retry_or_rewrite(self):
        self.start()
        real_write = os.write
        writes = []

        def short_write(descriptor, raw):
            writes.append(raw)
            return real_write(descriptor, raw[:7])

        with patch.object(H.os, "write", side_effect=short_write):
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(writes, [public_bytes()])
        self.assertEqual(self.path.read_bytes(), public_bytes()[:7])
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(self.path.read_bytes(), public_bytes()[:7])

    def test_io_or_close_failure_is_unavailable_and_retirement_continues(self):
        self.start()
        self.write(self.path, public_bytes())
        real_close = os.close
        closed = []

        def close_then_fail(descriptor):
            real_close(descriptor)  # Do not leak fixture descriptors while modeling failed close.
            closed.append(descriptor)
            if len(closed) == 1:
                raise OSError("PRIVATE_MODEL_CLOSE_DETAIL")

        with patch.object(H.os, "close", side_effect=close_then_fail):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertGreater(len(closed), 1)
        with patch.object(H.os, "read", side_effect=OSError("PRIVATE_MODEL_READ_DETAIL")):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        with patch.object(H.os, "read", return_value=public_bytes()[:7]):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.path.unlink()
        with patch.object(H.os, "write", side_effect=OSError("PRIVATE_MODEL_WRITE_DETAIL")):
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)


class CallerControls(HintFixture, unittest.TestCase):
    @contextmanager
    def caller(self, returned=125, receipt_code=0, *, execute_error=None, read_error=None, receipt_changes=None,
               phase="TARGET"):
        """Real owned_command/validator; only executed owner return and receipt DATA are models."""
        source = {"commit": "c" * 40, "tree": "d" * 40, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
        context = {"id": JOB, "source": source}
        argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                str(self.root / "scripts/run-hosted-dependency-update.py"), CHILDREN.get(phase, "_MODEL_generator")]
        purpose = PURPOSES[phase]
        receipt = {
            "schema": 1, "id": INVOCATION, "jobId": JOB, "kind": "command", "purpose": purpose,
            "requestedArgv": argv, "sourceBefore": source, "sourceAfter": source, "sourceUnchanged": True,
            "productExitCode": receipt_code, "stopExitCode": 0, "finalExitCode": receipt_code,
            "ownedSurvivors": [], "errors": [], "ownership": {"discoveryErrors": []},
            "cancelledSignals": [], "cancelRequested": False,
        }
        receipt.update(receipt_changes or {})
        raw = encoded(receipt)
        events = []

        def execute(args):
            events.append("execute")
            self.assertEqual(args.id, INVOCATION)
            self.assertEqual(args.kind, "command")
            self.assertEqual(args.purpose, purpose)
            self.assertEqual(args.argv, argv)
            self.assertEqual(args.cwd, str(self.root))
            self.assertEqual(args.wrapper, str(self.root / "gradlew"))
            self.assertEqual(args.stop_timeout, 120)
            self.assertEqual(os.environ["P2PKIT_AUDIT_STATE_DIR"], str(self.state))
            if execute_error is not None:
                raise execute_error
            return returned

        def original(path, limit):
            events.append("original-receipt")
            self.assertEqual(path, self.directory / "receipt.json", "raw streams/custody files must never be read")
            self.assertEqual(limit, 4 * C.MIB)
            if read_error is not None:
                raise read_error
            return raw, {}

        def module(name, relative):
            self.assertEqual((name, relative), ("hosted_command_failure_hint", "scripts/hosted_command_failure_hint.py"))
            return H  # Any exporter/native module load is a test failure.

        execute_mock = Mock(side_effect=execute)
        original_mock = Mock(side_effect=original)
        hint_read = H.read_hint

        def read_hint(*args):
            events.append("untrusted-hint")
            return hint_read(*args)

        with ExitStack() as stack:
            stack.enter_context(patch.object(C, "ROOT", self.root))
            stack.enter_context(patch.object(C.os, "environ", {}))
            stack.enter_context(patch.object(C.uuid, "uuid4", return_value=SimpleNamespace(hex=INVOCATION)))
            module_mock = stack.enter_context(patch.object(C, "module", side_effect=module))
            stack.enter_context(patch.object(C, "read_file", original_mock))
            hint_mock = stack.enter_context(patch.object(H, "read_hint", side_effect=read_hint))
            write_mock = stack.enter_context(patch.object(C, "write_new", side_effect=AssertionError("NO_RETURN_MARKERS")))
            custody_mock = stack.enter_context(patch.object(C, "retain_candidate_reports",
                                                         side_effect=AssertionError("NO_CUSTODY_ACCEPTANCE")))
            call = lambda: C.owned_command(SimpleNamespace(execute=execute_mock), self.state.parent, context,
                                          purpose, argv, 1200)
            yield SimpleNamespace(call=call, execute=execute_mock, original=original_mock, hints=hint_mock,
                                  modules=module_mock, write=write_mock, custody=custody_mock,
                                  receipt=receipt, raw=raw, events=events)

    def test_original_acceptance_predicate_bytes_are_unchanged(self):
        # Hash measured from the reviewed pre-repair 2dabecf3 source, not regenerated from this implementation.
        raw = CALLER_SOURCE.read_bytes()
        start = raw.index(b"def command_return_data(")
        end = raw.index(b"def owned_command(", start)
        self.assertEqual(hashlib.sha256(raw[start:end]).hexdigest(),
                         "783e36fa6772a55328001ef9cfff2153d1ee4dbd373b605de1f9fbc06b927f15")

    def test_actual_reserved125_cannot_be_replaced_by_optimistic_receipt_or_hint(self):
        self.write(self.path, public_bytes())
        with self.caller() as model:
            with self.assertRaises(C.OwnedCommandFailure) as failed:
                model.call()
            self.assertNotIsInstance(failed.exception, C.ClosedProductFailure)
            self.assertEqual(failed.exception.args, ("ORIGINAL_COMMAND_FAILED",))
            self.assertEqual(failed.exception.public_detail,
                "; phase=TARGET stage=VALIDATE_RETURN return=125 hint=JMDNS_ORIGINAL_OWNER HINT_NOT_CLOSURE_OR_ACCEPTANCE")
            self.assertEqual(model.events, ["execute", "original-receipt", "untrusted-hint"])
            model.execute.assert_called_once()
            model.original.assert_called_once()
            model.hints.assert_called_once_with(self.state, INVOCATION, "TARGET")
            model.modules.assert_called_once()
            model.write.assert_not_called()
            model.custody.assert_not_called()
            self.assertFalse((self.directory / "receipt.json").exists())  # Receipt DATA were modeled, never a real return.

    def test_stage_and_actual_return_diagnostics_are_refusal_only(self):
        class PrivateFailure(Exception):
            def __str__(self):
                raise AssertionError("private failure must not be stringified")

        for options, stage, returned, events in (
            ({"execute_error": PrivateFailure()}, "EXECUTE", "NOT_RETURNED", ["execute", "untrusted-hint"]),
            ({"returned": 0, "read_error": PrivateFailure()}, "READ_ORIGINAL", "0",
             ["execute", "original-receipt", "untrusted-hint"]),
            ({"returned": 0, "receipt_changes": {"stopExitCode": 1}}, "VALIDATE_RETURN", "0",
             ["execute", "original-receipt", "untrusted-hint"]),
        ):
            with self.subTest(stage=stage), self.caller(**options) as model:
                with self.assertRaises(C.OwnedCommandFailure) as failed:
                    model.call()
                self.assertIn("stage=" + stage + " return=" + returned + " hint=UNAVAILABLE", failed.exception.public_detail)
                self.assertEqual(model.events, events)
                model.write.assert_not_called()
                model.custody.assert_not_called()

    def test_ordinary_success_and_failed_product_do_not_consult_hints(self):
        self.write(self.path, public_bytes())
        for code in (0, 1, 7, 123):
            with self.subTest(code=code), self.caller(returned=code, receipt_code=code) as model:
                if code == 0:
                    receipt, checksum = model.call()
                    self.assertEqual(receipt, model.receipt)
                    self.assertEqual(checksum, hashlib.sha256(model.raw).hexdigest())
                else:
                    with self.assertRaises(C.ClosedProductFailure) as failed:
                        model.call()
                    self.assertIs(type(failed.exception), C.ClosedProductFailure)
                    self.assertEqual(failed.exception.code, code)
                    self.assertEqual(failed.exception.receipt, model.receipt)
                    self.assertEqual(failed.exception.receipt_hash, hashlib.sha256(model.raw).hexdigest())
                model.hints.assert_not_called()
                self.assertEqual(model.events, ["execute", "original-receipt"])
                model.write.assert_not_called()

    def test_timeout_signal_and_noninteger_actual_returns_stay_refused(self):
        for code in (124, 125, 130, 255, -15, 256, True, "0", 0.0, None):
            with self.subTest(code=code), self.caller(returned=code) as model:
                with self.assertRaises(C.OwnedCommandFailure) as failed:
                    model.call()
                expected = str(code) if type(code) is int and 0 <= code <= 255 else (
                    "NOT_RETURNED" if code is None else "NONORDINARY")
                self.assertIn("stage=VALIDATE_RETURN return=" + expected + " ", failed.exception.public_detail)
                model.write.assert_not_called()
                model.custody.assert_not_called()

    def test_cancellation_baseexception_is_not_converted_or_followed_by_reads(self):
        cancellation = KeyboardInterrupt()
        with self.caller(execute_error=cancellation) as model:
            with self.assertRaises(KeyboardInterrupt) as failed:
                model.call()
            self.assertIs(failed.exception, cancellation)
            self.assertEqual(model.events, ["execute"])
            model.original.assert_not_called()
            model.hints.assert_not_called()
            model.write.assert_not_called()
            self.assertEqual(os.environ, {})

    def test_optional_hint_failure_cannot_mask_original_refusal(self):
        for hint_error in (OSError("PRIVATE_MODEL_HINT_READ_FAILURE"), KeyboardInterrupt()):
            with self.caller() as model:
                model.hints.side_effect = hint_error
                with self.assertRaises(C.OwnedCommandFailure) as failed:
                    model.call()
                self.assertIn("return=125 hint=UNAVAILABLE", failed.exception.public_detail)
                model.original.assert_called_once()
                model.write.assert_not_called()

    def test_outer_cli_renders_finite_diagnostic_and_still_returns125(self):
        refusal = C.OwnedCommandFailure(H, "TARGET", "VALIDATE_RETURN", 125, DRIVER_CODE)
        output = io.StringIO()
        with patch.object(C.sys, "argv", [str(CALLER_SOURCE), "generate"]), \
                patch.object(C, "generate", side_effect=refusal), patch.object(C.os, "umask"), \
                patch.object(C.sys, "stderr", output), patch.object(C, "module") as module:
            self.assertEqual(C.main(), 125)
        module.assert_not_called()
        self.assertEqual(output.getvalue(), "RESULT: FAIL — ORIGINAL_COMMAND_FAILED" + refusal.public_detail +
                         "; preserve private runner originals; no retry or partial acceptance\n")

    def test_fixed_child_preloads_typed_hint_helper_and_keeps_original_cli_failure(self):
        class FixedDriverError(Exception):
            def __str__(self):
                raise AssertionError("driver failure must never be stringified")

        for phase, child in CHILDREN.items():
            for hint_failure in (None, KeyboardInterrupt()):
                with self.subTest(phase=phase, hint_failure=hint_failure is not None), ExitStack() as stack:
                    events = []
                    code = UPDATE_CODE if phase == "PREREQUISITES" else DRIVER_CODE
                    error = C.UpdateError(code) if phase == "PREREQUISITES" else FixedDriverError(code)

                    def action(*_args):
                        events.append("action")
                        raise error

                    driver = SimpleNamespace(DriverError=FixedDriverError, target=action, observe=action)

                    def module(name, relative):
                        if (name, relative) == ("hosted_command_failure_hint", "scripts/hosted_command_failure_hint.py"):
                            events.append("hint-helper")
                            return H
                        self.assertEqual((name, relative), ("hosted_jmdns_driver", "scripts/hosted_jmdns_driver.py"))
                        events.append("driver")
                        return driver

                    def publish(*args):
                        events.append("finite-hint")
                        self.assertEqual(args, (self.root, self.env, phase, code))
                        if hint_failure is not None:
                            raise hint_failure
                        return True

                    output = io.StringIO()
                    stack.enter_context(patch.object(C, "ROOT", self.root))
                    stack.enter_context(patch.object(C.sys, "argv", [str(CALLER_SOURCE), child]))
                    stack.enter_context(patch.object(C.os, "environ", dict(self.env)))
                    stack.enter_context(patch.object(C.os, "umask"))
                    stack.enter_context(patch.object(C.sys, "stderr", output))
                    stack.enter_context(patch.object(C, "module", side_effect=module))
                    stack.enter_context(patch.object(C, "prerequisites", side_effect=action))
                    publisher = stack.enter_context(patch.object(H, "publish_child", side_effect=publish))
                    self.assertEqual(C.main(), 125)
                    publisher.assert_called_once()
                    self.assertEqual(events, ["hint-helper", *([] if phase == "PREREQUISITES" else ["driver"]),
                                              "action", "finite-hint"])
                    reason = UPDATE_CODE if phase == "PREREQUISITES" else "PRIVATE_FAILURE"
                    self.assertEqual(output.getvalue(), "RESULT: FAIL — " + reason +
                                     "; preserve private runner originals; no retry or partial acceptance\n")


if __name__ == "__main__":
    unittest.main()
