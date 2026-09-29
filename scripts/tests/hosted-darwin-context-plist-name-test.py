#!/usr/bin/env python3
"""Three offline exact-plist-name controls, not installed/native qualification.

Only current runtime methods execute. Command returns, ledger, fsync, lstat and
evidence writes are memory-only. No subprocess, network, privileged operation,
key, ciphertext or reconstructed source executes; prior suites are not loaded.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-plist-name-test.py
"""
import contextlib
import ctypes  # Preload the standard module before the no-native audit fence.
import errno
import hashlib
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
INVERSE = ROOT / "scripts/tests/hosted_darwin_context_clock_inverse.py"
LEGACY_TEST = ROOT / "scripts/tests/hosted-darwin-context-admin-return-test.py"
METHODS = (
    "test_01_actual_create_exact_name_and_fail_closed_returns",
    "test_02_actual_file_custody_and_lifecycle_are_preserved",
    "test_03_exact_filename_inverse_and_prior_control_binding",
)
PREIMAGE = "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf"
LEGACY_PREIMAGE = "9e2ea5ad8dfdbd18cd626c5e157f199010c07a7abc55be09f91a547790541726"
HELD_ROOT = "/private/var/db/p2pkit-context.ABCDEFGHIJ"
HELD_FILE = HELD_ROOT + "/job.plist"
OTHER_ROOT = "/private/var/db/p2pkit-context.KLMNOPQRST"
DIRECTORY = Path("/synthetic/plist-name/evidence/N1")
LABEL = "p2pkit.context.synthetic.plist"
ARGUMENTS = ["/synthetic/python", "-I", "-B", "-S", "/synthetic/controller.py", "_service", str(DIRECTORY)]
PLIST = b"SYNTHETIC_PLIST_NAME_BYTES_ONLY\n"
SUDO = ["/usr/bin/sudo", "-n", "--"]
ROOT_CREATE = ["/usr/bin/mktemp", "-d", "/private/var/db/p2pkit-context.XXXXXXXXXX"]
FILE_CREATE = ["/usr/bin/mktemp", HELD_FILE]
PRINT = ["/bin/launchctl", "print", "system/" + LABEL]
RUN_ORDER = ["clock", "capture", "clock", "write", "flush", "fileno", "fsync"]
STAT_FORMAT = "%d:%i:%p:%u:%g:%l:%z:%m:%c"
STAT_KEYS = ("dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime", "ctime")
EMPTY_ROOT = dict(dev=1, ino=100, mode=0o40700, uid=0, gid=0, nlink=2, size=64, mtime=100, ctime=100)
# Deliberately not empty nlink + 1: the runtime must not invent link arithmetic.
POPULATED_ROOT = dict(EMPTY_ROOT, nlink=7, size=160, mtime=101, ctime=101)
REMOVED_ROOT = dict(EMPTY_ROOT, mtime=103, ctime=103)
EMPTY_FILE = dict(dev=1, ino=101, mode=0o100600, uid=0, gid=0, nlink=1, size=0, mtime=101, ctime=101)
FILLED_FILE = dict(EMPTY_FILE, size=len(PLIST), mtime=102, ctime=102)
PEER = dict(pid=123, parentPid=1, uniqueId=1123, parentUniqueId=1001, pidVersion=2,
            startSeconds=1700000000, startMicroseconds=123, uid=501, realUid=501,
            gid=20, realGid=20, status=3)


def offline(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid", "os.chmod",
        "os.mkdir", "os.rmdir", "os.remove", "os.rename", "os.link", "os.symlink", "os.truncate",
    }:
        raise AssertionError("OFFLINE_PLIST_NAME_FORBIDDEN_OPERATION")

if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_PLIST_NAME_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_plist_name_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
clock_spec = importlib.util.spec_from_file_location("darwin_context_clock_inverse", INVERSE)
CLOCK = importlib.util.module_from_spec(clock_spec)
clock_spec.loader.exec_module(CLOCK)


def stat_bytes(value):
    return (":".join(format(value[key], "o") if key == "mode" else str(value[key]) for key in STAT_KEYS) +
            "\n").encode("ascii")


def acl_bytes(path):
    return (("drwx------" if path == HELD_ROOT else "-rw-------") +
            " 1 root wheel 0 Jan 1 00:00 " + path + "\n").encode("ascii")


def printed(running, *, path=HELD_FILE):
    return ("system/" + LABEL + " = {\n\tpath = " + path + "\n\ttype = LaunchDaemon\n\tstate = " +
            ("running" if running else "not running") + "\n\tprogram = " + ARGUMENTS[0] +
            "\n\tpid = 123\n\targuments = {\n" +
            "".join("\t\t" + value + "\n" for value in ARGUMENTS) + "\t}\n}\n").encode("ascii")


class PlistName(unittest.TestCase):
    @contextlib.contextmanager
    def _model(self, overrides=None, *, short_writes=(), lstat_replies=None):
        """Fixed 42-command data script; no actual validator/method is replaced."""
        state = types.SimpleNamespace(calls=[], records=[], copies=[], lstats=[], order=[], ticks=0)
        overrides, lstat_replies = overrides or {}, lstat_replies or {}

        class Ledger:
            closed = False

            def write(self, raw):
                state.order.append("write")
                state.records.append(raw)
                return len(raw) - 1 if len(state.records) in short_writes else len(raw)

            def flush(self):
                state.order.append("flush")

            def fileno(self):
                state.order.append("fileno")
                return 197  # Synthetic descriptor DATA; fsync is replaced below.

            def close(self):
                state.order.append("close")
                self.closed = True

        admin = state.admin = M.Admin.__new__(M.Admin)
        admin.context = types.SimpleNamespace(os_env={"PATH": "/usr/bin:/bin", "LANG": "C"})
        admin.directory, admin.label, admin.end_ns = DIRECTORY, LABEL, 40 * M.NS
        admin.arguments, admin.plist = list(ARGUMENTS), PLIST
        admin.root = admin.path = admin.root_meta = admin.root_populated_meta = admin.file_meta = admin.service = None
        admin.bootstrapped = admin.retired = admin.removed = admin.closed = False
        admin.calls = admin.written = 0
        admin.record = Ledger()

        def command(argv, stdout=b"", stage="ADMIN_CREATE", *, input_raw=b"", code=0, stderr=b""):
            return (argv, stage, input_raw, dict(code=code, stdout=stdout, stderr=stderr))

        def metadata(path, value):
            stat = command(["/usr/bin/stat", "-f", STAT_FORMAT, path], stat_bytes(value))
            return [stat, command(["/bin/ls", "-lde", path], acl_bytes(path)), stat]

        absent = ("Bad request.\nCould not find service \"" + LABEL + "\" in domain for system\n").encode("ascii")
        state.script = [
            command(ROOT_CREATE, (HELD_ROOT + "\n").encode("ascii")),                       # 1
            *metadata(HELD_ROOT, EMPTY_ROOT),                                              # 2-4
            command(FILE_CREATE, (HELD_FILE + "\n").encode("ascii")),                       # 5
            *metadata(HELD_FILE, EMPTY_FILE),                                              # 6-8
            *metadata(HELD_ROOT, POPULATED_ROOT),                                          # 9-11
            command(["/bin/ls", "-1A", HELD_ROOT], b"job.plist\n"),                          # 12
            command(["/usr/bin/tee", HELD_FILE], PLIST, input_raw=PLIST),                   # 13
            *metadata(HELD_FILE, FILLED_FILE),                                             # 14-16
            command(["/bin/cat", HELD_FILE], PLIST),                                       # 17
            *metadata(HELD_FILE, FILLED_FILE),                                             # 18-20
            *metadata(HELD_ROOT, POPULATED_ROOT),                                          # 21-23
            command(PRINT, stage="BOOTSTRAP", code=64, stderr=absent),                      # 24
            command(["/bin/launchctl", "bootstrap", "system", HELD_FILE], stage="BOOTSTRAP"), # 25
            command(PRINT, printed(True), "BOOTSTRAP"),                                    # 26
            command(PRINT, printed(False), "BOOTSTRAP"),                                   # 27
            command(["/bin/launchctl", "bootout", "system/" + LABEL], stage="RETIRE"),       # 28
            command(PRINT, stage="RETIRE", code=64, stderr=absent),                         # 29
            *metadata(HELD_ROOT, POPULATED_ROOT),                                          # 30-32
            command(["/bin/ls", "-1A", HELD_ROOT], b"job.plist\n", "RETIRE"),                # 33
            *metadata(HELD_FILE, FILLED_FILE),                                             # 34-36
            command(["/bin/cat", HELD_FILE], PLIST, "RETIRE"),                              # 37
            command(["/bin/rm", HELD_FILE], stage="RETIRE"),                               # 38
            *metadata(HELD_ROOT, REMOVED_ROOT),                                            # 39-41
            command(["/bin/rmdir", HELD_ROOT], stage="RETIRE"),                            # 42
        ]

        def clock():
            state.order.append("clock")
            state.ticks += 1
            return M.NS + state.ticks

        def capture(argv, end_ns, env, *, input_raw, stage):
            state.order.append("capture")
            state.calls.append((list(argv), stage, input_raw))
            self.assertEqual(end_ns, 40 * M.NS)
            self.assertIs(env, admin.context.os_env)
            self.assertLessEqual(len(state.calls), len(state.script), "NO_EXTRA_SYNTHETIC_COMMAND")
            expected, expected_stage, expected_input, reply = state.script[len(state.calls) - 1]
            self.assertEqual((argv, stage, input_raw), (SUDO + expected, expected_stage, expected_input))
            result = dict(argv=list(argv), waited=True, eof=True, closed=True, **reply)
            result.update(overrides.get(len(state.calls), {}))
            return result

        def fsync(descriptor):
            self.assertEqual(descriptor, 197)
            state.order.append("fsync")

        def write_new(path, raw):
            state.order.append("copy")
            state.copies.append((path, raw))

        def lstat(path):
            self.assertIn(path, (HELD_ROOT, HELD_FILE))
            state.order.append("lstat")
            state.lstats.append(path)
            reply = lstat_replies.get(path, FileNotFoundError(errno.ENOENT, "SYNTHETIC_ABSENCE"))
            if isinstance(reply, BaseException):
                raise reply
            return reply

        with patch.object(M, "shared_raw_ns", side_effect=clock), \
                patch.object(M, "capture_fixed", side_effect=capture), patch.object(M.os, "fsync", side_effect=fsync), \
                patch.object(M.os, "lstat", side_effect=lstat), patch.object(M, "write_new", side_effect=write_new), \
                patch.object(M, "_UNCLOSED_COMMANDS", []):
            yield state

    def test_01_actual_create_exact_name_and_fail_closed_returns(self):
        with self._model() as state:
            admin = state.admin
            self.assertIsNone(admin._allowed(ROOT_CREATE, b""))
            with self.assertRaises(M.ExperimentError):
                admin._allowed(FILE_CREATE, b"")
            admin.root = HELD_ROOT
            self.assertIsNone(admin._allowed(FILE_CREATE, b""))
            for argv, raw in (
                (ROOT_CREATE, b""), (FILE_CREATE, b"unexpected input"),
                (["/usr/bin/mktemp", HELD_ROOT + "/job.XXXXXXXXXX"], b""),
                (["/usr/bin/mktemp", HELD_ROOT + "/job.KLMNOPQRST"], b""),
                (["/usr/bin/mktemp", OTHER_ROOT + "/job.plist"], b""),
                (["/usr/bin/mktemp", HELD_ROOT + "/other.plist"], b""),
                (["/usr/bin/mktemp", "--suffix=.plist", HELD_ROOT + "/job.XXXXXXXXXX"], b""),
                (["/usr/bin/mktemp", "-u", HELD_FILE], b""),
                (["/usr/bin/mktemp", "-d", HELD_FILE], b""),
                (FILE_CREATE + ["extra"], b""),
                (["/bin/mv", HELD_ROOT + "/job.KLMNOPQRST", HELD_FILE], b""),
                (["/bin/launchctl", "bootstrap", "system", HELD_FILE], b""),
            ):
                with self.subTest(argv=argv, input=raw), self.assertRaises(M.ExperimentError) as raised:
                    admin._allowed(argv, raw)
                self.assertEqual((raised.exception.stage, raised.exception.reason), ("ADMIN_CREATE", "REFUSED"))
            admin.path = HELD_FILE
            with self.assertRaises(M.ExperimentError):
                admin._allowed(FILE_CREATE, b"")
            with self.assertRaises(M.ExperimentError):
                admin._allowed(["/usr/bin/tee", HELD_FILE], PLIST)
            admin.file_meta = dict(EMPTY_FILE)
            self.assertIsNone(admin._allowed(["/usr/bin/tee", HELD_FILE], PLIST))
            with self.assertRaises(M.ExperimentError):
                admin._allowed(["/usr/bin/tee", HELD_FILE], PLIST + b"x")
            self.assertEqual(state.calls, [])

        with self._model() as state:
            state.admin.create()
            self.assertEqual((state.admin.root, state.admin.path), (HELD_ROOT, HELD_FILE))
            self.assertEqual(state.admin.calls, 23)
            self.assertEqual(state.copies, [(DIRECTORY / "launch.plist", PLIST)])
            with self.assertRaises(M.ExperimentError) as raised:
                state.admin.create()
            self.assertEqual((raised.exception.stage, raised.exception.reason), ("ADMIN_CREATE", "REFUSED"))
            self.assertEqual(state.admin.calls, 23)  # Never create/adopt a second name.

        exact = (HELD_FILE + "\n").encode("ascii")
        invalid = (
            b"", exact[:-1], exact + b"\n", exact + b"extra", exact + exact,
            exact[:-1] + b"\r\n", b" " + exact, b"\xff\n", exact[:-1] + b"\x00\n",
            (OTHER_ROOT + "/job.plist\n").encode("ascii"),
            (HELD_ROOT + "/job.KLMNOPQRST\n").encode("ascii"),
            (HELD_ROOT + "/job.XXXXXXXXXX\n").encode("ascii"),
            (HELD_ROOT + "/other.plist\n").encode("ascii"),
            (HELD_ROOT + "/job.plist.extra\n").encode("ascii"),
            (HELD_ROOT + "/../job.plist\n").encode("ascii"),
        )
        refusals = [({"stdout": raw}, (), "UNSUPPORTED") for raw in invalid]
        refusals.extend((
            ({"code": 1, "stderr": b"SYNTHETIC_EXISTING_NAME_REFUSAL"}, (), "RETURN_FAILED"),
            ({"code": 5}, (), "RETURN_FAILED"),
            ({"stderr": b"SYNTHETIC_UNEXPECTED_STDERR"}, (), "RETURN_FAILED"),
            ({}, (5,), "RETURN_FAILED"),
        ))
        for reply, short, reason in refusals:
            with self.subTest(reply=reply, short=short), self._model({5: reply}, short_writes=short) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin.create()
                self.assertEqual((raised.exception.stage, raised.exception.reason), ("ADMIN_CREATE", reason))
                self.assertEqual(state.admin.root, HELD_ROOT)
                self.assertIsNone(state.admin.path)
                self.assertIsNone(state.admin.file_meta)
                self.assertIsNone(state.admin.root_populated_meta)
                self.assertFalse(state.admin.bootstrapped or state.admin.retired or state.admin.removed)
                self.assertEqual((state.admin.calls, len(state.calls), len(state.records)), (5, 5, 5))
                self.assertEqual((state.copies, state.lstats), ([], []))  # No tee, bootstrap, adoption or fallback.

        for raw in ((HELD_ROOT + "X\n").encode("ascii"), HELD_ROOT.encode("ascii"), b"/tmp/other\n"):
            with self._model({1: {"stdout": raw}}) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin.create()
                self.assertEqual((raised.exception.stage, raised.exception.reason), ("ADMIN_CREATE", "UNSUPPORTED"))
                self.assertIsNone(state.admin.root)
                self.assertIsNone(state.admin.path)
                self.assertEqual(state.admin.calls, 1)
                self.assertEqual(state.copies, [])

    def test_02_actual_file_custody_and_lifecycle_are_preserved(self):
        with self._model() as state:
            admin = state.admin
            admin.create()
            self.assertEqual((admin.root_meta, admin.root_populated_meta, admin.file_meta),
                             (EMPTY_ROOT, POPULATED_ROOT, FILLED_FILE))
            self.assertFalse(admin.bootstrapped or admin.retired or admin.removed or admin.closed)
            admin.bootstrap()
            identity = dict(PEER)
            result = admin.inspect(identity)
            self.assertEqual(result, dict(target="system/" + LABEL, path=HELD_FILE, program=ARGUMENTS[0],
                                          arguments=ARGUMENTS, state="running", pid=123))
            self.assertEqual(admin.service, identity)
            self.assertIsNot(admin.service, identity)
            admin.retire(dict(PEER))
            admin.close()
            self.assertTrue(admin.bootstrapped and admin.retired and admin.removed and admin.closed and admin.record.closed)
            self.assertEqual((admin.root, admin.path), (HELD_ROOT, HELD_FILE))
            self.assertEqual((admin.root_meta, admin.root_populated_meta, admin.file_meta),
                             (EMPTY_ROOT, POPULATED_ROOT, FILLED_FILE))
            self.assertEqual((admin.calls, len(state.script), len(state.records), state.ticks), (42, 42, 42, 84))
            self.assertEqual(state.calls, [(SUDO + argv, stage, raw) for argv, stage, raw, _reply in state.script])
            self.assertEqual(state.order, RUN_ORDER * 23 + ["copy"] + RUN_ORDER * 19 +
                             ["lstat", "lstat", "flush", "fileno", "fsync", "close"])
            self.assertEqual(state.copies, [(DIRECTORY / "launch.plist", PLIST)])
            self.assertEqual(state.lstats, [HELD_ROOT, HELD_FILE])
            self.assertEqual(admin.written, sum(map(len, state.records)))
            for index, raw in enumerate(state.records, 1):
                row = M.parsed(raw)
                self.assertEqual((row["ordinal"], row["argv"]), (index, state.calls[index - 1][0]))
                self.assertEqual((row["stdinSha256"], row["stdinSize"]),
                                 (M.digest(state.calls[index - 1][2]), len(state.calls[index - 1][2])))
                self.assertEqual((row["startedMonotonicNs"], row["returnedMonotonicNs"]),
                                 (M.NS + 2 * index - 1, M.NS + 2 * index))

        refusals = []
        for first, value, changes, site in (
            (2, EMPTY_ROOT, {"uid": 501}, "META_OWNER"),
            (2, EMPTY_ROOT, {"mode": 0o40750}, "META_EXACT_MODE"),
            (2, EMPTY_ROOT, {"mode": 0o100700}, "META_TYPE"),
            (2, EMPTY_ROOT, {"nlink": 0}, None),
            (6, EMPTY_FILE, {"uid": 501}, "META_OWNER"),
            (6, EMPTY_FILE, {"mode": 0o100640}, "META_EXACT_MODE"),
            (6, EMPTY_FILE, {"mode": 0o120600}, "META_TYPE"),
            (6, EMPTY_FILE, {"nlink": 2}, "META_LINKS"),
            (6, EMPTY_FILE, {"size": 1}, "META_SIZE"),
            (9, POPULATED_ROOT, {"ino": 999}, None),
            (9, POPULATED_ROOT, {"gid": 1}, None),
            (9, POPULATED_ROOT, {"nlink": 0}, None),
            (14, FILLED_FILE, {"ino": 999}, "META_PREVIOUS"),
            (14, FILLED_FILE, {"size": len(PLIST) - 1}, "META_SIZE"),
            (18, FILLED_FILE, {"ino": 999}, "META_PREVIOUS"),
            (21, POPULATED_ROOT, {"nlink": 8}, "META_PREVIOUS"),
        ):
            raw = stat_bytes(dict(value, **changes))
            refusals.append(({first: {"stdout": raw}, first + 2: {"stdout": raw}}, first + 2, "IDENTITY_CHANGED", site))
        refusals.extend((
            ({8: {"stdout": stat_bytes(dict(EMPTY_FILE, mtime=999))}}, 8, "IDENTITY_CHANGED", "META_STABLE"),
            ({7: {"stdout": acl_bytes(HELD_FILE).replace(b"-rw------- ", b"-rw-------+ ") +
                  b" 0: synthetic allow read\n"}}, 8, "UNSUPPORTED", None),
            ({7: {"stdout": acl_bytes(HELD_FILE).replace(b"job.plist", b"other.plist")}}, 8, "UNSUPPORTED", None),
            ({7: {"stdout": acl_bytes(HELD_FILE).replace(b"-rw-------", b"drwx------")}},
             8, "IDENTITY_CHANGED", "META_LIST_TYPE"),
            ({12: {"stdout": b"job.plist\nother.plist\n"}}, 12, "IDENTITY_CHANGED", None),
            ({13: {"stdout": PLIST + b"x"}}, 13, "IDENTITY_CHANGED", "PLIST_TEE"),
            ({17: {"stdout": PLIST + b"x"}}, 17, "IDENTITY_CHANGED", "PLIST_CAT"),
        ))
        for override, stop, reason, site in refusals:
            with self.subTest(stop=stop, override=override), self._model(override) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin.create()
                self.assertEqual((raised.exception.stage, raised.exception.reason, raised.exception.admin_site),
                                 ("ADMIN_CREATE", reason, site))
                self.assertEqual((state.admin.calls, len(state.calls), len(state.records)), (stop, stop, stop))
                self.assertFalse(state.admin.bootstrapped or state.admin.retired or state.admin.removed)
                self.assertEqual((state.copies, state.lstats), ([], []))

        changed_parent = stat_bytes(dict(POPULATED_ROOT, nlink=8))
        changed_file = stat_bytes(dict(FILLED_FILE, ino=999))
        wrong_empty = stat_bytes(dict(REMOVED_ROOT, nlink=POPULATED_ROOT["nlink"]))
        for override, stop, stage, reason, retired in (
            ({27: {"stdout": printed(False, path=HELD_ROOT + "/other.plist")}}, 27, "BOOTSTRAP", "IDENTITY_CHANGED", False),
            ({28: {"code": 5}}, 28, "RETIRE", "RETURN_FAILED", False),
            ({29: {"stderr": b"SYNTHETIC_NOT_ABSENCE"}}, 29, "BOOTSTRAP", "UNSUPPORTED", False),
            ({30: {"stdout": changed_parent}, 32: {"stdout": changed_parent}}, 32, "ADMIN_CREATE", "IDENTITY_CHANGED", True),
            ({33: {"stdout": b"job.plist\nother.plist\n"}}, 33, "RETIRE", "IDENTITY_CHANGED", True),
            ({34: {"stdout": changed_file}, 36: {"stdout": changed_file}}, 36, "ADMIN_CREATE", "IDENTITY_CHANGED", True),
            ({37: {"stdout": PLIST + b"x"}}, 37, "RETIRE", "IDENTITY_CHANGED", True),
            ({38: {"code": 5}}, 38, "RETIRE", "RETURN_FAILED", True),
            ({39: {"stdout": wrong_empty}, 41: {"stdout": wrong_empty}}, 41, "ADMIN_CREATE", "IDENTITY_CHANGED", True),
            ({42: {"code": 5}}, 42, "RETIRE", "RETURN_FAILED", True),
        ):
            with self.subTest(stop=stop), self._model(override) as state:
                state.admin.create()
                state.admin.bootstrap()
                state.admin.inspect(dict(PEER))
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin.retire(dict(PEER))
                self.assertEqual((raised.exception.stage, raised.exception.reason), (stage, reason))
                self.assertEqual((state.admin.calls, len(state.calls), len(state.records)), (stop, stop, stop))
                self.assertEqual(state.admin.retired, retired)
                self.assertFalse(state.admin.removed or state.admin.closed)
                self.assertEqual(state.lstats, [])

        for path, reply in (
            (HELD_ROOT, object()), (HELD_FILE, object()),
            (HELD_ROOT, FileNotFoundError(errno.EACCES, "SYNTHETIC_NOT_ENOENT")),
        ):
            with self._model(lstat_replies={path: reply}) as state:
                state.admin.create()
                state.admin.bootstrap()
                state.admin.inspect(dict(PEER))
                with self.assertRaises(M.ExperimentError) as raised:
                    state.admin.retire(dict(PEER))
                self.assertEqual((raised.exception.stage, raised.exception.reason), ("RETIRE", "RESOURCE_UNKNOWN"))
                self.assertEqual(state.admin.calls, 42)
                self.assertTrue(state.admin.retired)
                self.assertFalse(state.admin.removed)
                self.assertEqual(state.lstats, [HELD_ROOT] if path == HELD_ROOT else [HELD_ROOT, HELD_FILE])

    def test_03_exact_filename_inverse_and_prior_control_binding(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(CLOCK.PLIST_NAME_BASE_RUNTIME_SHA256, PREIMAGE)
        self.assertEqual((CLOCK.ADMIN_RETURN_BASE_RUNTIME_SHA256, CLOCK.BASE_RUNTIME_SHA256,
                          CLOCK.BASE_WORKFLOW_SHA256, CLOCK.BASE_EXPERIMENT_TEST_SHA256), (
            "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b",
            "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
            "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40",
            "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768",
        ))
        restores = (CLOCK.restore_plist_name_runtime, CLOCK.restore_admin_return_runtime, CLOCK.restore_runtime)
        hashes = (PREIMAGE, CLOCK.ADMIN_RETURN_BASE_RUNTIME_SHA256, CLOCK.BASE_RUNTIME_SHA256)
        for restore, expected in zip(restores, hashes):
            self.assertEqual(hashlib.sha256(restore(source).encode("utf-8")).hexdigest(), expected)
        restored = CLOCK.restore_plist_name_runtime(source)
        self.assertEqual((len(CLOCK.PLIST_NAME_PATCH), len(CLOCK.ADMIN_RETURN_PATCH)), (3, 8))
        for before, after in CLOCK.PLIST_NAME_PATCH:
            self.assertEqual(source.count(after), 1)
            self.assertEqual(source.count(before), 0)
            for changed in (
                source.replace(after, before, 1), source + after,
                source.replace(after, after.replace("job.plist", "job.invalid"), 1),
            ):
                self.assertNotEqual(changed, source)
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(changed)
        for bad in (None, b"", "", restored, source + "\n# SYNTHETIC_UNRELATED_MUTATION\n"):
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(bad)
        for patches in (CLOCK.PLIST_NAME_PATCH[:-1], CLOCK.PLIST_NAME_PATCH + CLOCK.PLIST_NAME_PATCH[:1]):
            with patch.object(CLOCK, "PLIST_NAME_PATCH", patches), self.assertRaises(AssertionError):
                CLOCK.restore_plist_name_runtime(source)
        for before, after in (
            ("self.calls < 96", "self.calls < 97"),
            ("mode=0o600, size=0", "mode=0o644, size=0"),
            ('value["nlink"] == 1', 'value["nlink"] >= 1'),
            ("self.inspect(identity, running=False)", "self.inspect(identity, running=True)"),
            ('return_site="BOOTSTRAP_COMMAND"', 'return_site="BOOTSTRAP_PRECHECK_PRINT"'),
            ("CASE_SECONDS = 120, 180, 40", "CASE_SECONDS = 120, 180, 41"),
            ("(end_ns - shared_raw_ns())", "(end_ns - time.monotonic_ns())"),
        ):
            changed = source.replace(before, after, 1)
            self.assertNotEqual(changed, source)
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(changed)

        # Read old controls only as source DATA: one exact selector reversal must
        # recover all five original methods/assertions, without running any one.
        before = "            ('root + \"/job.XXXXXXXXXX\"', 'root + \"/job.XXXXXXXXXX.plist\"'),\n"
        after = "            ('root + \"/job.plist\"', 'root + \"/job.invalid\"'),\n"

        def legacy_preimage(text):
            if type(text) is not str or text.count(after) != 1:
                raise AssertionError("EXACT_ONE_LEGACY_SELECTOR_REQUIRED")
            original = text.replace(after, before, 1)
            if hashlib.sha256(original.encode("utf-8")).hexdigest() != LEGACY_PREIMAGE:
                raise AssertionError("OUTSIDE_LEGACY_SELECTOR_CHANGED")
            return original

        legacy = LEGACY_TEST.read_text(encoding="utf-8")
        original = legacy_preimage(legacy)
        self.assertEqual(hashlib.sha256(original.encode("utf-8")).hexdigest(), LEGACY_PREIMAGE)
        for changed in (None, original, legacy + after, legacy + "\n# SYNTHETIC_MUTATION\n",
                        legacy.replace("self.assertEqual", "self.assertNotEqual", 1)):
            with self.assertRaises(AssertionError):
                legacy_preimage(changed)


if __name__ == "__main__":
    if tuple(unittest.defaultTestLoader.getTestCaseNames(PlistName)) != METHODS:
        raise SystemExit("FIXED_THREE_PLIST_NAME_METHODS_REQUIRED")
    suite = unittest.TestSuite(PlistName(name) for name in METHODS)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
