#!/usr/bin/env python3
"""Five offline administrative-return controls, not native qualification.

Only current runtime methods execute, with synthetic command returns and a
memory-only ledger. No subprocess, socket, native library, privileged operation,
key, ciphertext, workflow or reconstructed source may execute. Prior accepted
test families are not loaded or rerun by this suite.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-admin-return-test.py
"""
import ast
import contextlib
import ctypes  # Load the standard module before the no-native audit fence.
import hashlib
import importlib.util
import io
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
INVERSE = ROOT / "scripts/tests/hosted_darwin_context_clock_inverse.py"
CANARY = "SYNTHETIC_ADMIN_RETURN_CANARY"
FAILURE = "P2PKIT_CONTEXT_FAILURE|BOOTSTRAP|RETURN_FAILED|NONE"
PREFIX = "P2PKIT_CONTEXT_ADMIN_RETURN|"
SITES = ("BOOTSTRAP_PRECHECK_PRINT", "BOOTSTRAP_COMMAND", "INSPECT_RUNNING_PRINT", "INSPECT_STOPPED_PRINT")
HELD_ROOT = "/private/var/db/p2pkit-context.ABCDEFGHIJ"
HELD_FILE = HELD_ROOT + "/job.KLMNOPQRST"
LABEL = "p2pkit.context.synthetic.return"
PRINT = ["/bin/launchctl", "print", "system/" + LABEL]
BOOTSTRAP = ["/bin/launchctl", "bootstrap", "system", HELD_FILE]
FULL_ORDER = ["clock", "capture", "clock", "write", "flush", "fileno", "fsync"]
PREIMAGE = "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b"
PEER = dict(pid=123, parentPid=1, uniqueId=1123, parentUniqueId=1001, pidVersion=2,
            startSeconds=1700000000, startMicroseconds=123, uid=501, realUid=501,
            gid=20, realGid=20, status=3)


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("OFFLINE_ADMIN_RETURN_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_ADMIN_RETURN_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_admin_return_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
clock_spec = importlib.util.spec_from_file_location("darwin_context_clock_inverse", INVERSE)
CLOCK = importlib.util.module_from_spec(clock_spec)
clock_spec.loader.exec_module(CLOCK)


def absent():
    return dict(code=64, stdout=b"", stderr=("Bad request.\nCould not find service \"" + LABEL +
                "\" in domain for system\n").encode("ascii"))


def printed(admin, running):
    return ("system/" + LABEL + " = {\n\tpath = " + HELD_FILE +
            "\n\ttype = LaunchDaemon\n\tstate = " + ("running" if running else "not running") +
            "\n\tprogram = " + admin.arguments[0] + "\n\tpid = 123\n\targuments = {\n" +
            "".join("\t\t" + value + "\n" for value in admin.arguments) + "\t}\n}\n").encode("ascii")


class AdminReturn(unittest.TestCase):
    @contextlib.contextmanager
    def _model(self, replies, *, short_writes=(), case="N2"):
        """Actual Admin methods; fake capture/clock/fsync and no file descriptor."""
        state = types.SimpleNamespace(order=[], calls=[], records=[], clocks=[], errors=[], returned=[])

        class Ledger:
            def write(self, raw):
                state.order.append("write")
                state.records.append(raw)
                return len(raw) - 1 if len(state.records) in short_writes else len(raw)

            def flush(self):
                state.order.append("flush")

            def fileno(self):
                state.order.append("fileno")
                return 197  # Synthetic descriptor DATA; fsync is replaced below.

        admin = state.admin = M.Admin.__new__(M.Admin)
        admin.context = types.SimpleNamespace(os_env={"PATH": "/usr/bin:/bin", "LANG": "C"})
        admin.directory = Path("/synthetic") / CANARY / "evidence" / case
        admin.root, admin.path, admin.label = HELD_ROOT, HELD_FILE, LABEL
        admin.arguments = ["/synthetic/python", "-I", "-B", "-S", "/synthetic/controller.py", "_service",
                           str(admin.directory)]
        admin.plist, admin.file_meta, admin.service = b"SYNTHETIC_NOT_A_PLIST", None, None
        admin.bootstrapped = admin.retired = admin.removed = admin.closed = False
        admin.calls = admin.written = 0
        admin.end_ns, admin.record = 40 * M.NS, Ledger()

        def clock():
            state.order.append("clock")
            state.clocks.append((len(state.clocks) + 1) * M.NS)
            return state.clocks[-1]

        def capture(argv, end, env, *, input_raw, stage):
            state.order.append("capture")
            self.assertEqual(argv[:3], ["/usr/bin/sudo", "-n", "--"])
            self.assertEqual(end, 40 * M.NS)
            self.assertIs(env, admin.context.os_env)
            self.assertEqual(input_raw, b"")
            state.calls.append((list(argv), stage))
            self.assertLessEqual(len(state.calls), len(replies), "NO_EXTRA_SYNTHETIC_COMMAND")
            reply = replies[len(state.calls) - 1]
            if isinstance(reply, BaseException):
                raise reply
            result = dict(argv=list(argv), code=0, stdout=CANARY.encode("ascii"), stderr=b"",
                          waited=True, eof=True, closed=True)
            result.update(reply)
            state.returned.append(result)
            return result

        def fsync(descriptor):
            self.assertEqual(descriptor, 197)
            state.order.append("fsync")

        original_require = M.require

        def observed_require(*args, **kwargs):
            try:
                return original_require(*args, **kwargs)
            except M.ExperimentError as error:
                state.errors.append(error)
                raise

        with patch.object(M, "shared_raw_ns", side_effect=clock), \
                patch.object(M, "capture_fixed", side_effect=capture), patch.object(M.os, "fsync", side_effect=fsync), \
                patch.object(M, "require", side_effect=observed_require), patch.object(M, "_UNCLOSED_COMMANDS", []):
            yield state

    def _failure(self, state, error, site, guard, code, stderr, *, case="N2"):
        self.assertIs(error, state.errors[-1])  # The original require exception, not a replacement.
        self.assertEqual(error.args, ("BOOTSTRAP/RETURN_FAILED/NONE",))
        self.assertEqual(error.admin_return, (site, case, guard, code, stderr))
        self.assertEqual(M.public_error(error), FAILURE)
        self.assertEqual(M.public_admin_return(error), PREFIX + "|".join((site, case, guard, str(code), stderr)))
        self.assertIsNone(M.public_source_site(error))
        self.assertIsNone(M.public_admin_site(error))

    def test_01_actual_run_refusals_preserve_order_and_guard_priority(self):
        scenarios = (
            ({}, (1,), True, ("LEDGER_WRITE", 0, "EMPTY")),
            ({"code": 5, "stderr": CANARY.encode()}, (1,), True, ("LEDGER_WRITE", 5, "NONEMPTY")),
            ({"code": 5, "stderr": CANARY.encode()}, (), True, ("RETURN_CODE", 5, "NONEMPTY")),
            ({"stderr": CANARY.encode()}, (), True, ("STDERR", 0, "NONEMPTY")),
            ({"code": 256}, (), True, ("UNKNOWN", "UNKNOWN", "EMPTY")),
            ({}, (), True, None),
            ({"code": 5, "stderr": CANARY.encode()}, (), False, None),
            ({"code": False}, (), True, None),  # Diagnostic typing must not add a success guard.
        )
        for reply, short, success, expected in scenarios:
            with self._model([reply], short_writes=short) as state, \
                    patch.object(M, "annotate_admin_return", wraps=M.annotate_admin_return) as annotate:
                if expected is None:
                    result = state.admin._run(BOOTSTRAP, "BOOTSTRAP", success=success, return_site=SITES[1])
                    self.assertIs(result, state.returned[0])
                    annotate.assert_not_called()
                    self.assertFalse(state.errors)
                else:
                    with self.assertRaises(M.ExperimentError) as raised:
                        state.admin._run(BOOTSTRAP, "BOOTSTRAP", success=success, return_site=SITES[1])
                    self._failure(state, raised.exception, SITES[1], *expected)
                    annotate.assert_called_once()
                    self.assertIs(annotate.call_args.args[0], raised.exception)
                    self.assertIs(annotate.call_args.args[3], state.returned[0])
                self.assertEqual(state.order, FULL_ORDER[:4] if short else FULL_ORDER)
                self.assertEqual(state.admin.calls, 1)
                self.assertEqual(len(state.records), 1)
                self.assertEqual(state.admin.written, len(state.records[0]))
                row = M.parsed(state.records[0])
                self.assertEqual(row, dict(schema=1, ordinal=1, argv=state.calls[0][0], code=state.returned[0]["code"],
                    stdoutHex=state.returned[0]["stdout"].hex(), stderrHex=state.returned[0]["stderr"].hex(),
                    stdinSha256=M.digest(b""), stdinSize=0, startedMonotonicNs=M.NS, returnedMonotonicNs=2 * M.NS,
                    waited=True, eof=True, closed=True))
                self.assertFalse(state.admin.bootstrapped or state.admin.retired or state.admin.removed)

        for key in ("waited", "eof", "closed"):
            with self._model([{key: False, "code": 5, "stderr": CANARY.encode()}]) as state, \
                    patch.object(M, "annotate_admin_return", wraps=M.annotate_admin_return) as annotate:
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin._run(BOOTSTRAP, "BOOTSTRAP", return_site=SITES[1])
                self.assertEqual(raised.exception.reason, "RESOURCE_UNKNOWN")
                self.assertEqual(state.order, FULL_ORDER)
                self.assertIsNone(M.public_admin_return(raised.exception))
                annotate.assert_not_called()

        for attribute, value, reason, order in (
            ("closed", True, "RESOURCE_UNKNOWN", []), ("calls", 96, "RESOURCE_UNKNOWN", []),
            ("written", M.EVIDENCE_BYTES // 4, "BOUND", FULL_ORDER[:3]),
        ):
            with self._model([{}]) as state, patch.object(M, "annotate_admin_return") as annotate:
                setattr(state.admin, attribute, value)
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin._run(BOOTSTRAP, "BOOTSTRAP", return_site=SITES[1])
                self.assertEqual(raised.exception.reason, reason)
                self.assertEqual(state.order, order)
                annotate.assert_not_called()
        original = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
        with self._model([original]) as state, patch.object(M, "annotate_admin_return") as annotate:
            with self.assertRaises(M.ExperimentError) as raised:
                state.admin._run(BOOTSTRAP, "BOOTSTRAP", return_site=SITES[1])
            self.assertIs(raised.exception, original)
            self.assertEqual(state.order, ["clock", "capture"])
            self.assertIsNone(M.public_admin_return(original))
            annotate.assert_not_called()  # Capture failures are outside the two new catches.

    def test_02_actual_bootstrap_and_inspect_fixed_call_attribution(self):
        for site in SITES:
            guards = ("LEDGER_WRITE",) if site == SITES[0] else ("LEDGER_WRITE", "RETURN_CODE", "STDERR")
            for guard in guards:
                fault = {"code": 5 if guard == "RETURN_CODE" else 0,
                         "stderr": CANARY.encode() if guard != "LEDGER_WRITE" else b""}
                replies = [absent()] if site == SITES[0] else [absent(), fault] if site == SITES[1] else [fault]
                short = (len(replies),) if guard == "LEDGER_WRITE" else ()
                with self._model(replies, short_writes=short, case="N3") as state, \
                        patch.object(M, "parse_service_print", wraps=M.parse_service_print) as parser:
                    if site in SITES[2:]:
                        state.admin.bootstrapped = True
                    with self.assertRaises(M.ExperimentError) as raised:
                        if site in SITES[:2]:
                            state.admin.bootstrap()
                        else:
                            state.admin.inspect(dict(PEER), running=site == SITES[2])
                    last = replies[-1]
                    self._failure(state, raised.exception, site, guard, last["code"],
                                  "NONEMPTY" if last["stderr"] else "EMPTY", case="N3")
                    expected = [PRINT, BOOTSTRAP] if site == SITES[1] else [PRINT]
                    self.assertEqual([argv[3:] for argv, _stage in state.calls], expected)
                    self.assertTrue(all(stage == "BOOTSTRAP" for _argv, stage in state.calls))
                    self.assertEqual(state.admin.calls, len(expected))
                    self.assertEqual(len(state.records), len(expected))
                    self.assertEqual(state.admin.bootstrapped, site in SITES[2:])
                    self.assertIsNone(state.admin.service)
                    self.assertFalse(state.admin.retired or state.admin.removed)
                    parser.assert_not_called()

        replies = [absent(), {}, {}, {}]
        with self._model(replies) as state, patch.object(M, "annotate_admin_return") as annotate:
            replies[2]["stdout"], replies[3]["stdout"] = printed(state.admin, True), printed(state.admin, False)
            state.admin.bootstrap()
            self.assertTrue(state.admin.bootstrapped)
            for running, expected in ((True, "running"), (False, "not running")):
                identity = dict(PEER)
                result = state.admin.inspect(identity, running=running)
                self.assertEqual((result["state"], result["pid"]), (expected, 123))
                self.assertEqual(state.admin.service, identity)
                self.assertIsNot(state.admin.service, identity)
            self.assertEqual([argv[3:] for argv, _stage in state.calls], [PRINT, BOOTSTRAP, PRINT, PRINT])
            self.assertTrue(all(stage == "BOOTSTRAP" for _argv, stage in state.calls))
            self.assertEqual(state.order, FULL_ORDER * 4)
            annotate.assert_not_called()  # Expected absence is still accepted only by service_absent.
        for inspection in (False, True):
            with self._model([{"code": 0 if inspection else 5, "stdout": CANARY.encode(), "stderr": b""}]) as state, \
                    patch.object(M, "annotate_admin_return") as annotate:
                state.admin.bootstrapped = inspection
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin.inspect(dict(PEER)) if inspection else state.admin.bootstrap()
                self.assertEqual(raised.exception.reason, "UNSUPPORTED")
                self.assertIsNone(M.public_admin_return(raised.exception))
                self.assertIsNone(state.admin.service)
                self.assertEqual(len(state.calls), 1)
                annotate.assert_not_called()  # Parser/absence failures are not returned-command guards.

    def test_03_strict_metadata_and_public_containment(self):
        class Hostile:
            def forbidden(self, *_args):
                raise AssertionError("UNTRUSTED_DIAGNOSTIC_OPERATION")
            __str__ = __repr__ = __bool__ = __len__ = __hash__ = __eq__ = forbidden

        class StringSubclass(str):
            pass

        class IntegerSubclass(int):
            pass

        class BytesSubclass(bytes):
            pass

        class MappingSubclass(dict):
            def get(self, *_args):
                raise AssertionError("UNTRUSTED_MAPPING_ACCESS")

        class TupleSubclass(tuple):
            pass

        self.assertEqual(M.ADMIN_RETURN_SITES, frozenset(SITES))
        self.assertEqual(M.ADMIN_RETURN_GUARDS, frozenset(("LEDGER_WRITE", "RETURN_CODE", "STDERR")))
        with patch.object(M, "errno_name", side_effect=AssertionError("RETURN_CODE_IS_NOT_ERRNO")):
            for code in (-127, -1, 0, 1, 255):
                for ledger in (False, True):
                    error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                    result = {"code": code, "stderr": (CANARY + "\n::error::" + CANARY).encode()}
                    M.annotate_admin_return(error, SITES[1], "N4", result, ledger=ledger)
                    guard = "LEDGER_WRITE" if ledger else "RETURN_CODE" if code else "STDERR"
                    self.assertEqual(error.admin_return, (SITES[1], "N4", guard, code, "NONEMPTY"))
                    self.assertEqual(M.public_admin_return(error), PREFIX + SITES[1] + "|N4|" + guard + "|" + str(code) + "|NONEMPTY")
                    self.assertEqual(M.public_error(error), FAILURE)
            for code in (-128, 256, -(1 << 64), 1 << 64, True, False, None, 1.0, "5", IntegerSubclass(5), Hostile()):
                for ledger in (False, True):
                    error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                    M.annotate_admin_return(error, SITES[1], "N1", {"code": code, "stderr": b""}, ledger=ledger)
                    self.assertEqual(error.admin_return, (SITES[1], "N1", "LEDGER_WRITE" if ledger else "UNKNOWN", "UNKNOWN", "EMPTY"))
            for stderr in (None, True, CANARY, bytearray(b"x"), BytesSubclass(b"x"), Hostile()):
                error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                M.annotate_admin_return(error, SITES[1], "N1", {"code": 0, "stderr": stderr})
                self.assertEqual(error.admin_return, (SITES[1], "N1", "UNKNOWN", 0, "UNKNOWN"))
            for result in (None, [], MappingSubclass(code=5, stderr=b"x"), Hostile()):
                error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                M.annotate_admin_return(error, Hostile(), Hostile(), result, ledger=True)
                self.assertEqual(error.admin_return, ("UNKNOWN", "UNKNOWN", "LEDGER_WRITE", "UNKNOWN", "UNKNOWN"))

        valid = (SITES[1], "N1", "RETURN_CODE", 5, "NONEMPTY")
        bad = (None, True, False, -128, 256, 1.5, [], {}, CANARY, "N1\n" + CANARY, Hostile(),
               StringSubclass("NONEMPTY"), IntegerSubclass(5), BytesSubclass(b"x"))
        for index in range(5):
            for value in bad:
                error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                fields = list(valid)
                fields[index] = value
                error.admin_return = tuple(fields)
                expected = [SITES[1], "N1", "RETURN_CODE", "5", "NONEMPTY"]
                expected[index] = "UNKNOWN"
                public = M.public_admin_return(error)
                self.assertEqual(public, PREFIX + "|".join(expected))
                self.assertLessEqual(len(public), 128)
                self.assertNotIn(CANARY, public)
                self.assertNotIn("\n", public)
        for site in SITES:
            for case in ("N1", "N2", "N3", "N4"):
                error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                M.annotate_admin_return(error, site, case, {"code": 5, "stderr": b""})
                self.assertEqual(error.admin_return, (site, case, "RETURN_CODE", 5, "EMPTY"))
        for fields in (None, (), valid[:-1], valid + (0,), list(valid), TupleSubclass(valid), Hostile()):
            error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
            error.admin_return = fields
            self.assertIsNone(M.public_admin_return(error))
        self.assertIsNone(M.public_admin_return(M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")))
        for attribute in ("stage", "reason"):
            for value in bad:
                error = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
                error.admin_return = valid
                setattr(error, attribute, value)
                self.assertIsNone(M.public_admin_return(error))
        for stage in M.STAGES:
            for reason in M.REASONS:
                if (stage, reason) != ("BOOTSTRAP", "RETURN_FAILED"):
                    error = M.ExperimentError(stage, reason)
                    error.admin_return = valid
                    self.assertIsNone(M.public_admin_return(error))
        for error in (RuntimeError(CANARY), OSError(CANARY), SystemExit(CANARY)):
            error.admin_return = valid
            self.assertIsNone(M.public_admin_return(error))

    def test_04_actual_main_keeps_failure_and_cannot_activate_export(self):
        with self._model([{"code": 5, "stderr": CANARY.encode()}], case="N3") as state:
            with self.assertRaises(M.ExperimentError) as raised:
                state.admin._run(BOOTSTRAP, "BOOTSTRAP", return_site=SITES[1])
            annotated = raised.exception
        primary = M.ExperimentError("BOOTSTRAP", "RETURN_FAILED")
        unrelated = M.ExperimentError("RETIRE", "RETURN_FAILED")
        unrelated.admin_return = annotated.admin_return
        for error, expected in (
            (annotated, FAILURE + "\n" + PREFIX + SITES[1] + "|N3|RETURN_CODE|5|NONEMPTY\n"),
            (primary, FAILURE + "\n"),
            (unrelated, "P2PKIT_CONTEXT_FAILURE|RETIRE|RETURN_FAILED|NONE\n"),
            (RuntimeError(CANARY), "P2PKIT_CONTEXT_FAILURE|PREPARE|REFUSED|UNKNOWN\n"),
        ):
            output = io.StringIO()
            context = types.SimpleNamespace(output=types.SimpleNamespace(close=Mock()))
            with patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), patch.object(M.os, "umask") as umask, \
                    patch.object(M, "prepare", return_value=context) as prepare, patch.object(M, "run_cases", side_effect=error) as cases, \
                    patch.object(M, "finish_export") as export, patch.object(M, "upload_guard") as upload, \
                    patch.object(M, "write_new") as write, patch.object(M, "capture_fixed") as capture, \
                    patch.object(M, "Darwin") as native, patch.object(M, "Admin") as admin, \
                    patch.object(M, "CommandFile") as command, patch.object(M, "load_module") as loader, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(M.main(), 2)  # Actual main and experiment; only their acquisition boundary is fake.
                prepare.assert_called_once_with()
                cases.assert_called_once_with(context)
                context.output.close.assert_called_once_with()
                umask.assert_called_once_with(0o077)
                for endpoint in (export, upload, write, capture, native, admin, command, loader):
                    endpoint.assert_not_called()
            self.assertEqual(output.getvalue(), expected)
            self.assertNotIn(CANARY, output.getvalue())
        for result in (0, 1):
            output = io.StringIO()
            with patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), patch.object(M.os, "umask"), \
                    patch.object(M, "experiment", return_value=result), patch.object(M, "public_admin_return") as formatter, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(M.main(), result)
                formatter.assert_not_called()
            self.assertEqual(output.getvalue(), "")

    def test_05_exact_runtime_inverse_and_mutation_containment(self):
        source = SOURCE.read_text(encoding="utf-8")
        restored = CLOCK.restore_admin_return_runtime(source)
        self.assertEqual(CLOCK.ADMIN_RETURN_BASE_RUNTIME_SHA256, PREIMAGE)
        self.assertEqual(hashlib.sha256(restored.encode("utf-8")).hexdigest(), PREIMAGE)
        self.assertEqual((CLOCK.BASE_RUNTIME_SHA256, CLOCK.BASE_WORKFLOW_SHA256, CLOCK.BASE_EXPERIMENT_TEST_SHA256),
            ("a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
             "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40",
             "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768"))
        self.assertEqual(hashlib.sha256(CLOCK.restore_runtime(source).encode("utf-8")).hexdigest(), CLOCK.BASE_RUNTIME_SHA256)
        self.assertEqual(len(CLOCK.ADMIN_RETURN_PATCH), 8)
        # Only source data is reconstructed, hashed and parsed; never executed.
        for text in (source, restored):
            tree = ast.parse(text, feature_version=(3, 9))
            reads = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Name) and node.func.id == "shared_raw_ns"]
            self.assertEqual(len(reads), 33)
            admin = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Admin")
            run = next(node for node in admin.body if isinstance(node, ast.FunctionDef) and node.name == "_run")
            self.assertEqual(sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                                 node.func.id == "shared_raw_ns" for node in ast.walk(run)), 2)
        helper = ast.parse(INVERSE.read_text(encoding="utf-8"), feature_version=(3, 9))
        imports = [node for node in helper.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertEqual(len(imports), 1)
        self.assertIsInstance(imports[0], ast.Import)
        self.assertEqual([(item.name, item.asname) for item in imports[0].names], [("hashlib", None)])
        for node in ast.walk(helper):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
                self.assertNotIn(name, {"open", "read_text", "read_bytes", "write_text", "write_bytes", "exec", "eval", "compile", "__import__"})
        for before, after in CLOCK.ADMIN_RETURN_PATCH:
            self.assertEqual(source.count(after), 1)
            for changed in (source.replace(after, before, 1), source + after, source.replace(after, after + "# SYNTHETIC_MUTATION\n", 1)):
                with self.assertRaises(AssertionError):
                    CLOCK.restore_admin_return_runtime(changed)
        for before, after in (
            ('return_site="BOOTSTRAP_COMMAND"', 'return_site="BOOTSTRAP_PRECHECK_PRINT"'),
            ('ledger=True)', 'ledger=False)'),
            ('type(code) is int and -127 <= code <= 255', 'isinstance(code, int)'),
            ('"INSPECT_RUNNING_PRINT" if running else "INSPECT_STOPPED_PRINT"', '"INSPECT_STOPPED_PRINT"'),
            ('result["code"] == 0 and result["stderr"] == b""', 'result["code"] == 0'),
            ('self.record.write(raw) == len(raw)', 'self.record.write(raw) <= len(raw)'),
            ('self.record.flush()', 'pass'),
            ('self.calls < 96', 'self.calls < 97'),
            ('self.inspect(identity, running=False)', 'self.inspect(identity, running=True)'),
            ('root + "/job.plist"', 'root + "/job.invalid"'),
            ('CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
            ('(end_ns - shared_raw_ns())', '(end_ns - time.monotonic_ns())'),
            ('native.boot() == value["boot"]', 'True'),
        ):
            changed = source.replace(before, after, 1)
            self.assertNotEqual(changed, source)
            with self.assertRaises(AssertionError):
                CLOCK.restore_runtime(changed)
        for bad in (None, b"", restored):
            with self.assertRaises(AssertionError):
                CLOCK.restore_admin_return_runtime(bad)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AdminReturn)
    if suite.countTestCases() != 5:
        raise SystemExit("FIXED_FIVE_ADMIN_RETURN_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
