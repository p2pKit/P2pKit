#!/usr/bin/env python3
"""Six offline directory-phase controls, not installed-OS/native qualification.

Actual Admin methods use synthetic capture/lstat returns and a tiny owned ledger.
No native case, subprocess, key, export or workflow is executed.
"""
import ast
import contextlib
import ctypes  # Import before the explicit no-native audit boundary.
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
BASE_RUNTIME_SHA256 = "9451bc102f7564b378eb313ddf72d85917f521974ba541fd084372ee252fde80"
# Five contextual hunks; only Admin.__init__, _allowed, create and retire change.
REVIEWED_RUNTIME_PATCH = (('        self.arguments = service_arguments(context.interpreter["path"], directory)\n'
  '        self.plist = service_plist(label, context.interpreter["path"], directory, context.username, '
  'context.groupname)\n'
  '        self.root, self.path, self.root_meta, self.file_meta, self.service = None, None, None, None, None\n'
  '        self.bootstrapped, self.retired, self.removed, self.closed = False, False, False, False\n'
  '        self.calls, self.written = 0, 0\n'
  '        self.record = os.fdopen(os.open(directory / "admin.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | '
  'os.O_NOFOLLOW,\n',
  '        self.arguments = service_arguments(context.interpreter["path"], directory)\n'
  '        self.plist = service_plist(label, context.interpreter["path"], directory, context.username, '
  'context.groupname)\n'
  '        self.root, self.path, self.root_meta, self.file_meta, self.service = None, None, None, None, None\n'
  '        self.root_populated_meta = None\n'
  '        self.bootstrapped, self.retired, self.removed, self.closed = False, False, False, False\n'
  '        self.calls, self.written = 0, 0\n'
  '        self.record = os.fdopen(os.open(directory / "admin.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | '
  'os.O_NOFOLLOW,\n'),
 ('                          ["/bin/launchctl", "bootstrap", "system", self.path], ["/bin/rm", self.path]))\n'
  '        if self.root is not None:\n'
  '            exact.append(["/bin/rmdir", self.root])\n'
  '        exact.append(["/bin/launchctl", "print", "system/" + self.label])\n'
  '        if self.service is not None:\n'
  '            exact.append(["/bin/launchctl", "bootout", "system/" + self.label])\n',
  '                          ["/bin/launchctl", "bootstrap", "system", self.path], ["/bin/rm", self.path]))\n'
  '        if self.root is not None:\n'
  '            exact.append(["/bin/rmdir", self.root])\n'
  '            if self.path is not None:\n'
  '                exact.append(["/bin/ls", "-1A", self.root])\n'
  '        exact.append(["/bin/launchctl", "print", "system/" + self.label])\n'
  '        if self.service is not None:\n'
  '            exact.append(["/bin/launchctl", "bootout", "system/" + self.label])\n'),
 ('                                    expected_os_links=expected_os_links)\n'
  '\n'
  '    def create(self):\n'
  '        require(self.root is None and self.path is None, "ADMIN_CREATE", "REFUSED")\n'
  '        raw = self._run(["/usr/bin/mktemp", "-d", ROOT_TEMPLATE], "ADMIN_CREATE")["stdout"]\n'
  '        require(re.fullmatch(rb"/private/var/db/p2pkit-context\\.[A-Za-z0-9]{10}\\n", raw), "ADMIN_CREATE", '
  '"UNSUPPORTED")\n'
  '        self.root = raw[:-1].decode("ascii")\n'
  '        self.root_meta = self.metadata(self.root, "directory", mode=0o700)\n'
  '        raw = self._run(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"], "ADMIN_CREATE")["stdout"]\n'
  '        require(re.fullmatch(re.escape(self.root.encode("ascii")) + rb"/job\\.[A-Za-z0-9]{10}\\n", raw),\n'
  '                "ADMIN_CREATE", "UNSUPPORTED")\n'
  '        self.path = raw[:-1].decode("ascii")\n'
  '        self.file_meta = self.metadata(self.path, "file", mode=0o600, size=0)\n'
  '        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)\n'
  '        # mktemp was exclusive. tee is intentionally NOT described as exclusive:\n'
  '        # only the checked root0700 original parent protects its truncating open.\n'
  '        returned = self._run(["/usr/bin/tee", self.path], "ADMIN_CREATE", input_raw=self.plist)\n',
  '                                    expected_os_links=expected_os_links)\n'
  '\n'
  '    def create(self):\n'
  '        require(self.root is None and self.path is None and self.root_populated_meta is None, "ADMIN_CREATE", '
  '"REFUSED")\n'
  '        raw = self._run(["/usr/bin/mktemp", "-d", ROOT_TEMPLATE], "ADMIN_CREATE")["stdout"]\n'
  '        require(re.fullmatch(rb"/private/var/db/p2pkit-context\\.[A-Za-z0-9]{10}\\n", raw), "ADMIN_CREATE", '
  '"UNSUPPORTED")\n'
  '        self.root = raw[:-1].decode("ascii")\n'
  '        self.root_meta = self.metadata(self.root, "directory", mode=0o700)\n'
  '        require(self.root_meta["nlink"] > 0, "ADMIN_CREATE", "IDENTITY_CHANGED")\n'
  '        raw = self._run(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"], "ADMIN_CREATE")["stdout"]\n'
  '        require(re.fullmatch(re.escape(self.root.encode("ascii")) + rb"/job\\.[A-Za-z0-9]{10}\\n", raw),\n'
  '                "ADMIN_CREATE", "UNSUPPORTED")\n'
  '        self.path = raw[:-1].decode("ascii")\n'
  '        self.file_meta = self.metadata(self.path, "file", mode=0o600, size=0)\n'
  '        # Keep the empty original. Only this owned insertion may establish a\n'
  '        # populated observation; no directory-link arithmetic is presumed.\n'
  '        populated = self.metadata(self.root, "directory", mode=0o700)\n'
  '        require(populated["nlink"] > 0 and\n'
  '                all(populated[key] == self.root_meta[key] for key in ("dev", "ino", "mode", "uid", "gid")),\n'
  '                "ADMIN_CREATE", "IDENTITY_CHANGED")\n'
  '        require(self._run(["/bin/ls", "-1A", self.root], "ADMIN_CREATE")["stdout"] ==\n'
  '                self.path.rsplit("/", 1)[1].encode("ascii") + b"\\n", "ADMIN_CREATE", "IDENTITY_CHANGED")\n'
  '        self.root_populated_meta = populated\n'
  '        # mktemp was exclusive. tee is intentionally NOT described as exclusive:\n'
  '        # only the checked root0700 original parent protects its truncating open.\n'
  '        returned = self._run(["/usr/bin/tee", self.path], "ADMIN_CREATE", input_raw=self.plist)\n'),
 ('        require(self._run(["/bin/cat", self.path], "ADMIN_CREATE")["stdout"] == self.plist,\n'
  '                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="PLIST_CAT", admin_item="PRIVATE_FILE")\n'
  '        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))\n'
  '        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)\n'
  '        write_new(self.directory / "launch.plist", self.plist)\n'
  '\n'
  '    def bootstrap(self):\n',
  '        require(self._run(["/bin/cat", self.path], "ADMIN_CREATE")["stdout"] == self.plist,\n'
  '                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="PLIST_CAT", admin_item="PRIVATE_FILE")\n'
  '        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))\n'
  '        self.metadata(self.root, "directory", mode=0o700, previous=self.root_populated_meta)\n'
  '        write_new(self.directory / "launch.plist", self.plist)\n'
  '\n'
  '    def bootstrap(self):\n'),
 ('        return result\n'
  '\n'
  '    def retire(self, identity):\n'
  '        require(self.service is not None and not self.retired and not self.removed, "RETIRE", '
  '"RESOURCE_UNKNOWN")\n'
  '        self.inspect(identity, running=False)\n'
  '        self._run(["/bin/launchctl", "bootout", "system/" + self.label], "RETIRE")\n'
  '        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "RETIRE", '
  'success=False), self.label)\n'
  '        self.retired = True\n'
  '        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)\n'
  '        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))\n'
  '        require(self._run(["/bin/cat", self.path], "RETIRE")["stdout"] == self.plist, "RETIRE", '
  '"IDENTITY_CHANGED")\n'
  '        self._run(["/bin/rm", self.path], "RETIRE")\n',
  '        return result\n'
  '\n'
  '    def retire(self, identity):\n'
  '        require(self.service is not None and not self.retired and not self.removed and\n'
  '                self.root_meta is not None and self.root_populated_meta is not None, "RETIRE", '
  '"RESOURCE_UNKNOWN")\n'
  '        self.inspect(identity, running=False)\n'
  '        self._run(["/bin/launchctl", "bootout", "system/" + self.label], "RETIRE")\n'
  '        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "RETIRE", '
  'success=False), self.label)\n'
  '        self.retired = True\n'
  '        self.metadata(self.root, "directory", mode=0o700, previous=self.root_populated_meta)\n'
  '        require(self._run(["/bin/ls", "-1A", self.root], "RETIRE")["stdout"] ==\n'
  '                self.path.rsplit("/", 1)[1].encode("ascii") + b"\\n", "RETIRE", "IDENTITY_CHANGED")\n'
  '        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))\n'
  '        require(self._run(["/bin/cat", self.path], "RETIRE")["stdout"] == self.plist, "RETIRE", '
  '"IDENTITY_CHANGED")\n'
  '        self._run(["/bin/rm", self.path], "RETIRE")\n'))


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("OFFLINE_DIRECTORY_PHASE_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_DIRECTORY_PHASE_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_directory_phase_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
HELD_ROOT = "/private/var/db/p2pkit-context.ABCDEFGHIJ"
HELD_FILE = HELD_ROOT + "/job.KLMNOPQRST"
LABEL = "p2pkit.context.synthetic.phase"
SINGLETON = b"job.KLMNOPQRST\n"
FIELDS = ("dev", "ino", "mode", "uid", "gid", "nlink")
PEER = dict(pid=123, parentPid=100, uniqueId=1123, parentUniqueId=1100,
            pidVersion=2, startSeconds=1700000000, startMicroseconds=123,
            uid=501, realUid=501, gid=20, realGid=20, status=3)


def restore_preimage(source):
    if len(REVIEWED_RUNTIME_PATCH) != 5:
        raise AssertionError("EXACT_FIVE_DIRECTORY_PHASE_HUNKS_REQUIRED")
    for before, after in reversed(REVIEWED_RUNTIME_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_DIRECTORY_PHASE_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_DIRECTORY_PHASE_DELTA_CHANGED")
    return source


def metadata_commands(path):
    return [["/usr/bin/stat", "-f", M.STAT_FORMAT, path], ["/bin/ls", "-lde", path],
            ["/usr/bin/stat", "-f", M.STAT_FORMAT, path]]


class DirectoryPhase(unittest.TestCase):
    @contextlib.contextmanager
    def _model(self, *, empty_links=2, populated_links=5, root_changes=None, listing_returns=None):
        """Capture/lstat are fake; Admin's parser, commands and ledger are actual."""
        root_changes, listing_returns = root_changes or {}, listing_returns or {}
        with tempfile.TemporaryDirectory(prefix="p2pkit-directory-phase-") as temporary:
            directory = Path(temporary).resolve()
            context = types.SimpleNamespace(interpreter={"path": "/usr/bin/python3"}, username="synthetic",
                groupname="staff", os_env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}, os_files={})
            os_metadata = {}
            for index, path in enumerate((*M.OS_PARENTS, *M.OS_TOOLS)):
                parent = path in M.OS_PARENTS
                value = dict(dev=1, ino=200 + index, mode=(stat.S_IFDIR if parent else stat.S_IFREG) | 0o755,
                             uid=0, gid=0, nlink=2 if parent else 3, size=0, mtime=170, ctime=170)
                os_metadata[path] = value
                context.os_files[path] = [value[key] for key in FIELDS[:5 if parent else 6]]
            with patch.object(M.os, "environ", {}):
                admin = M.Admin(context, directory, LABEL, 40 * M.NS)
            calls = []
            state = dict(directory=directory, root_exists=False, present=False, written=False,
                         registered=False, running=True, root_stat_reads=0, root_observation=-1,
                         listing_count=0, listing_present=[], fixture_error=False)

            def metadata(path, *, stat_call=False):
                if path == HELD_ROOT:
                    if stat_call:
                        if state["root_stat_reads"] % 2 == 0:
                            state["root_observation"] += 1
                            value = dict(dev=1, ino=100, mode=0o40700, uid=0, gid=0,
                                         nlink=populated_links if state["present"] else empty_links,
                                         size=0, mtime=170, ctime=170)
                            value.update(root_changes.get(state["root_observation"], {}))
                            state["root_value"] = value
                        state["root_stat_reads"] += 1
                    value = state["root_value"]
                elif path == HELD_FILE:
                    value = dict(dev=1, ino=101, mode=0o100600, uid=0, gid=0, nlink=1,
                                 size=len(admin.plist) if state["written"] else 0, mtime=170, ctime=170)
                else:
                    value = os_metadata[path]
                raw = (":".join(format(value[key], "o") if key == "mode" else str(value[key])
                                for key in (*FIELDS, "size", "mtime", "ctime")) + "\n").encode("ascii")
                acl = (stat.filemode(value["mode"]) + " " + str(value["nlink"]) + " root wheel " +
                       str(value["size"]) + " Sep 29 00:00 " + path + "\n").encode("ascii")
                return raw, acl

            def service_print():
                return ("system/" + LABEL + " = {\n\tpath = " + HELD_FILE +
                        "\n\ttype = LaunchDaemon\n\tstate = " + ("running" if state["running"] else "not running") +
                        "\n\tprogram = " + admin.arguments[0] + "\n\tpid = 123\n\targuments = {\n" +
                        "".join("\t\t" + value + "\n" for value in admin.arguments) + "\t}\n}\n").encode("ascii")

            def returned(argv, end_ns, env, *, input_raw=b"", stage="SOURCE"):
                try:
                    self.assertEqual(argv[:3], ["/usr/bin/sudo", "-n", "--"])
                    self.assertEqual(end_ns, 40 * M.NS)
                    self.assertIs(env, context.os_env)
                    command = argv[3:]
                    self.assertEqual(input_raw, admin.plist if command == ["/usr/bin/tee", HELD_FILE] else b"")
                    calls.append((command, stage, input_raw))
                    result = dict(argv=list(argv), code=0, stdout=b"", stderr=b"", waited=True, eof=True, closed=True)
                    if command == ["/usr/bin/mktemp", "-d", M.ROOT_TEMPLATE]:
                        self.assertFalse(state["root_exists"])
                        state["root_exists"] = True
                        result["stdout"] = (HELD_ROOT + "\n").encode("ascii")
                    elif command == ["/usr/bin/mktemp", HELD_ROOT + "/job.XXXXXXXXXX"]:
                        self.assertTrue(state["root_exists"])
                        self.assertFalse(state["present"])
                        state["empty_original"], state["empty_copy"] = admin.root_meta, dict(admin.root_meta)
                        state["present"] = True
                        result["stdout"] = (HELD_FILE + "\n").encode("ascii")
                    elif command[:3] == ["/usr/bin/stat", "-f", M.STAT_FORMAT]:
                        result["stdout"] = metadata(command[3], stat_call=True)[0]
                    elif command[:2] == ["/bin/ls", "-lde"]:
                        result["stdout"] = metadata(command[2])[1]
                    elif command == ["/bin/ls", "-1A", HELD_ROOT]:
                        self.assertTrue(state["root_exists"] and state["present"])
                        state["listing_count"] += 1
                        state["listing_present"].append(state["present"])
                        if state["listing_count"] == 1:
                            self.assertIsNone(admin.root_populated_meta)
                        result["stdout"] = SINGLETON
                        for key, value in listing_returns.get(state["listing_count"], {}).items():
                            if value is None:
                                result.pop(key)
                            else:
                                result[key] = value
                    elif command == ["/usr/bin/tee", HELD_FILE]:
                        self.assertIsNotNone(admin.file_meta)
                        self.assertIsNotNone(admin.root_populated_meta)
                        state["populated_original"] = admin.root_populated_meta
                        state["populated_copy"] = dict(admin.root_populated_meta)
                        state["written"], result["stdout"] = True, input_raw
                    elif command == ["/bin/cat", HELD_FILE]:
                        self.assertTrue(state["written"])
                        result["stdout"] = admin.plist
                    elif command == ["/bin/launchctl", "print", "system/" + LABEL]:
                        if state["registered"]:
                            result["stdout"] = service_print()
                        else:
                            result.update(code=1, stderr=('Could not find service "' + LABEL +
                                                        '" in domain for system\n').encode("ascii"))
                    elif command == ["/bin/launchctl", "bootstrap", "system", HELD_FILE]:
                        self.assertTrue(state["written"])
                        self.assertFalse(state["registered"])
                        state["registered"] = True
                    elif command == ["/bin/launchctl", "bootout", "system/" + LABEL]:
                        self.assertTrue(state["registered"])
                        state["registered"] = False
                    elif command == ["/bin/rm", HELD_FILE]:
                        self.assertTrue(state["present"])
                        state["present"], state["written"] = False, False
                    elif command == ["/bin/rmdir", HELD_ROOT]:
                        self.assertTrue(state["root_exists"])
                        self.assertFalse(state["present"])
                        state["root_exists"] = False
                    else:
                        self.fail("UNEXPECTED_SYNTHETIC_DIRECTORY_COMMAND")
                    return result
                except AssertionError:
                    # at_stage must not hide a malformed test fixture as an
                    # expected production refusal, including missing-key cases.
                    state["fixture_error"] = True
                    raise

            original_lstat = M.os.lstat

            def absence(path, *args, **kwargs):
                name = os.fspath(path)
                if name in (HELD_ROOT, HELD_FILE):
                    if state["root_exists" if name == HELD_ROOT else "present"]:
                        return types.SimpleNamespace(st_mode=0o40700 if name == HELD_ROOT else 0o100600)
                    raise FileNotFoundError(M.errno.ENOENT, "SYNTHETIC_ABSENT")
                return original_lstat(path, *args, **kwargs)

            try:
                with patch.object(M, "capture_fixed", side_effect=returned), patch.object(M.os, "lstat", side_effect=absence):
                    yield admin, state, calls
            finally:
                if not admin.closed:
                    admin.close()
                self.assertTrue(admin.closed and admin.record.closed)
                self.assertFalse(state["fixture_error"])

    def _originals(self, admin, state):
        for attribute, prefix in (("root_meta", "empty"), ("root_populated_meta", "populated")):
            self.assertIs(getattr(admin, attribute), state[prefix + "_original"])
            self.assertEqual(getattr(admin, attribute), state[prefix + "_copy"])
        self.assertIsNot(admin.root_meta, admin.root_populated_meta)

    def _running(self, admin):
        admin.bootstrap()
        self.assertEqual(admin.inspect(dict(PEER))["pid"], 123)

    def test_01_complete_delta_and_mutation_containment(self):
        source = SOURCE.read_text(encoding="utf-8")
        restored = restore_preimage(source)
        self.assertNotIn("root_populated_meta", restored)
        ast.parse(source, filename=str(SOURCE), feature_version=(3, 9))
        for before, after in (
            ('self.root_populated_meta = None', 'self.root_populated_meta = {}'),
            ('exact.append(["/bin/ls", "-1A", self.root])', 'exact.append(["/bin/ls", "-1A", self.path])'),
            ('self.root_meta["nlink"] > 0', 'self.root_meta["nlink"] >= 0'),
            ('populated["nlink"] > 0', 'populated["nlink"] >= 0'),
            ('for key in ("dev", "ino", "mode", "uid", "gid"))', 'for key in ("dev", "ino", "mode", "uid"))'),
            ('self.root_populated_meta = populated', 'self.root_meta = populated'),
            ('previous=self.root_populated_meta)', 'previous=self.root_meta)'),
            ('self.calls < 96', 'self.calls < 97'),
            ('value["nlink"] == 1', 'value["nlink"] >= 1'),
            ('expected_os_links = original[5]', 'expected_os_links = 1'),
            ('require(error.errno == errno.ENOENT, "RETIRE"', 'require(True, "RETIRE"'),
            ('CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
            ('context.recipient_original', 'context.changed_recipient_original'),
        ):
            changed = source.replace(before, after, 1)
            self.assertNotEqual(changed, source)
            with self.assertRaises(AssertionError):
                restore_preimage(changed)

    def test_02_actual_lifecycle_originals_exact_42_and_96_calls(self):
        target = "system/" + LABEL
        expected = ([['/usr/bin/mktemp', '-d', M.ROOT_TEMPLATE]] + metadata_commands(HELD_ROOT) +
            [["/usr/bin/mktemp", HELD_ROOT + "/job.XXXXXXXXXX"]] + metadata_commands(HELD_FILE) +
            metadata_commands(HELD_ROOT) + [["/bin/ls", "-1A", HELD_ROOT], ["/usr/bin/tee", HELD_FILE]] +
            metadata_commands(HELD_FILE) + [["/bin/cat", HELD_FILE]] + metadata_commands(HELD_FILE) +
            metadata_commands(HELD_ROOT) + [["/bin/launchctl", "print", target],
            ["/bin/launchctl", "bootstrap", "system", HELD_FILE], ["/bin/launchctl", "print", target],
            ["/bin/launchctl", "print", target], ["/bin/launchctl", "bootout", target],
            ["/bin/launchctl", "print", target]] + metadata_commands(HELD_ROOT) +
            [["/bin/ls", "-1A", HELD_ROOT]] + metadata_commands(HELD_FILE) +
            [["/bin/cat", HELD_FILE], ["/bin/rm", HELD_FILE]] + metadata_commands(HELD_ROOT) +
            [["/bin/rmdir", HELD_ROOT]])
        self.assertEqual(len(expected), 42)
        for empty, populated, preflight in ((2, 2, False), (2, 5, False), (5, 2, False), (2, 5, True)):
            with self.subTest(empty=empty, populated=populated, preflight=preflight):
                with self._model(empty_links=empty, populated_links=populated) as (admin, state, calls):
                    prefix = []
                    if preflight:
                        # Model only, not actual N1: acquire the fixed18 synthetic
                        # metadata returns through the real Admin metadata method.
                        self.assertEqual((len(M.OS_PARENTS), len(M.OS_TOOLS)), (7, 11))
                        for path in (*M.OS_PARENTS, *M.OS_TOOLS):
                            parent = path in M.OS_PARENTS
                            value = admin.metadata(path, "directory" if parent else "file")
                            self.assertEqual([value[key] for key in FIELDS[:5 if parent else 6]], admin.context.os_files[path])
                            prefix.extend(metadata_commands(path))
                        self.assertEqual(len(prefix), 54)
                    admin.create()
                    self._originals(admin, state)
                    self.assertEqual((admin.root_meta["nlink"], admin.root_populated_meta["nlink"]), (empty, populated))
                    before = len(calls)
                    with self.assertRaises(M.ExperimentError):
                        admin.create()
                    self.assertEqual(len(calls), before)
                    self._running(admin)
                    state["running"] = False
                    admin.retire(dict(PEER))
                    self._originals(admin, state)
                    self.assertTrue(admin.retired and admin.removed)
                    self.assertFalse(state["registered"] or state["present"] or state["root_exists"])
                    self.assertEqual([command for command, _stage, _input in calls], prefix + expected)
                    self.assertEqual(admin.calls, 96 if preflight else 42)
                    self.assertEqual(state["listing_present"], [True, True])
                    self.assertEqual(state["root_observation"], 4)
                    for ordinal, stage in ((12, "ADMIN_CREATE"), (33, "RETIRE")):
                        self.assertEqual(calls[len(prefix) + ordinal - 1], (["/bin/ls", "-1A", HELD_ROOT], stage, b""))
                    if preflight:
                        self.assertFalse(admin.closed)
                        with self.assertRaises(M.ExperimentError) as raised:
                            admin._run(["/bin/ls", "-1A", HELD_ROOT], "RETIRE")
                        self.assertEqual(raised.exception.reason, "RESOURCE_UNKNOWN")
                        self.assertEqual((admin.calls, len(calls)), (96, 96))  #97 refused before capture.
                    admin.close()
                    rows = [json.loads(line) for line in (state["directory"] / "admin.jsonl").read_text().splitlines()]
                    self.assertEqual([row["ordinal"] for row in rows], list(range(1, len(calls) + 1)))
                    self.assertEqual([row["argv"][3:] for row in rows], prefix + expected)
                    for row, (_command, _stage, stdin) in zip(rows, calls):
                        self.assertEqual(row["argv"][:3], ["/usr/bin/sudo", "-n", "--"])
                        self.assertEqual((row["waited"], row["eof"], row["closed"]), (True, True, True))
                        self.assertEqual((row["stdinSize"], row["stdinSha256"]), (len(stdin), hashlib.sha256(stdin).hexdigest()))
                    root_rows = [row for row in rows if row["argv"][3:] == ["/usr/bin/stat", "-f", M.STAT_FORMAT, HELD_ROOT]]
                    self.assertEqual([int(bytes.fromhex(row["stdoutHex"]).split(b":")[5]) for row in root_rows],
                                     [empty] * 2 + [populated] * 6 + [empty] * 2)

    def test_03_phase_entry_five_field_and_positive_link_refusals(self):
        cases = [(1, {field: value}) for field, value in
                 (("dev", 2), ("ino", 101), ("mode", 0o40500), ("uid", 1), ("gid", 1))]
        cases += [(0, {"nlink": 0}), (1, {"nlink": 0})]
        for observation, changes in cases:
            with self.subTest(observation=observation, changes=changes):
                with self._model(root_changes={observation: changes}) as (admin, state, calls):
                    with self.assertRaises(M.ExperimentError) as raised:
                        admin.create()
                    self.assertEqual((raised.exception.stage, raised.exception.reason), ("ADMIN_CREATE", "IDENTITY_CHANGED"))
                    self.assertIsNone(admin.root_populated_meta)
                    self.assertFalse(state["written"] or admin.bootstrapped or admin.retired or admin.removed)
                    self.assertFalse((state["directory"] / "launch.plist").exists())
                    self.assertEqual(state["listing_count"], 0)
                    self.assertNotIn(["/usr/bin/tee", HELD_FILE], [command for command, _stage, _input in calls])
                    if observation:
                        self.assertIs(admin.root_meta, state["empty_original"])
                        self.assertEqual(admin.root_meta, state["empty_copy"])
                    before = len(calls)
                    with self.assertRaises(M.ExperimentError) as repeated:
                        admin.create()
                    self.assertEqual(repeated.exception.reason, "REFUSED")
                    self.assertEqual(len(calls), before)

    def test_04_all_six_populated_and_original_empty_comparisons(self):
        for observation in (2, 3, 4):
            changes = dict(dev=2, ino=101, mode=0o40500, uid=1, gid=1, nlink=5 if observation == 4 else 2)
            for field, value in changes.items():
                with self.subTest(observation=observation, field=field):
                    with self._model(root_changes={observation: {field: value}}) as (admin, state, calls):
                        with self.assertRaises(M.ExperimentError) as raised:
                            admin.create()
                            self._running(admin)
                            state["running"] = False
                            admin.retire(dict(PEER))
                        self.assertEqual(raised.exception.reason, "IDENTITY_CHANGED")
                        self.assertEqual(raised.exception.admin_field, None if field in ("mode", "uid") else field)
                        self._originals(admin, state)
                        self.assertFalse(admin.removed)
                        self.assertEqual(admin.calls, {2: 23, 3: 32, 4: 41}[observation])
                        commands = [command for command, _stage, _input in calls]
                        self.assertNotIn(["/bin/rmdir", HELD_ROOT], commands)
                        self.assertEqual(["/bin/rm", HELD_FILE] in commands, observation == 4)
                        self.assertEqual(admin.root_meta["nlink"], 2)
                        self.assertEqual(admin.root_populated_meta["nlink"], 5)

    def test_05_both_singleton_namespaces_and_original_return_guards(self):
        outputs = (b"", b"other\n", SINGLETON + b"extra\n", b".\n" + SINGLETON,
                   SINGLETON * 2, b"job.KLMNO\nPQRST\n")
        faults = [({"stdout": output}, "IDENTITY_CHANGED") for output in outputs]
        faults += [({"code": 1}, "RETURN_FAILED"), ({"stderr": b"SYNTHETIC_ERROR\n"}, "RETURN_FAILED")]
        faults += [({key: value}, "REFUSED" if value is None else "RESOURCE_UNKNOWN")
                   for key in ("waited", "eof", "closed") for value in (False, None)]
        for listing in (1, 2):
            for fault, reason in faults:
                with self.subTest(listing=listing, fault=fault):
                    with self._model(listing_returns={listing: fault}) as (admin, state, calls):
                        with self.assertRaises(M.ExperimentError) as raised:
                            with M.at_stage("ADMIN_CREATE" if listing == 1 else "RETIRE"):
                                admin.create()
                                self._running(admin)
                                state["running"] = False
                                admin.retire(dict(PEER))
                        self.assertEqual((raised.exception.stage, raised.exception.reason),
                                         ("ADMIN_CREATE" if listing == 1 else "RETIRE", reason))
                        self.assertEqual(admin.calls, 12 if listing == 1 else 33)
                        self.assertEqual(calls[-1][0], ["/bin/ls", "-1A", HELD_ROOT])
                        self.assertFalse(admin.removed)
                        self.assertIs(admin.root_meta, state["empty_original"])
                        self.assertEqual(admin.root_meta, state["empty_copy"])
                        if listing == 1:
                            self.assertIsNone(admin.root_populated_meta)
                            self.assertFalse(state["written"])
                        else:
                            self._originals(admin, state)
                            self.assertTrue(state["present"])

    def test_06_exact_listing_input_and_original_phase_state_guards(self):
        with self._model() as (admin, _state, calls):
            for root, path in ((None, None), (HELD_ROOT, None), (None, HELD_FILE)):
                admin.root, admin.path = root, path
                with self.assertRaises(M.ExperimentError):
                    admin._run(["/bin/ls", "-1A", HELD_ROOT], "ADMIN_CREATE")
                self.assertEqual(calls, [])
            admin.root, admin.path = HELD_ROOT, HELD_FILE
            self.assertIsNone(admin._allowed(["/bin/ls", "-1A", HELD_ROOT], b""))
            for command, stdin in (
                (["/bin/ls", "-1A", HELD_ROOT], b"NONEMPTY"),
                (["/bin/ls", "-1A", HELD_FILE], b""),
                (["/bin/ls", "-1A", HELD_ROOT + "/"], b""),
                (["/bin/ls", "-1A", "/different"], b""),
                (["/bin/ls", "-1A", HELD_ROOT, HELD_FILE], b""),
                (["/bin/ls", "-1a", HELD_ROOT], b""),
                (["/bin/ls", "-1", HELD_ROOT], b""),
                (["/bin/ls", "-A", HELD_ROOT], b""),
                (["/bin/ls", "-1A", "--", HELD_ROOT], b""),
            ):
                with self.assertRaises(M.ExperimentError):
                    admin._run(command, "ADMIN_CREATE", input_raw=stdin)
                self.assertEqual(calls, [])
            admin.root, admin.path = None, None
            admin.root_populated_meta = {"nlink": 5}  # Synthetic stale state, never an admitted baseline.
            with self.assertRaises(M.ExperimentError) as raised:
                admin.create()
            self.assertEqual(raised.exception.reason, "REFUSED")
            self.assertEqual(calls, [])
        for missing in ("root_meta", "root_populated_meta"):
            with self.subTest(missing=missing):
                with self._model() as (admin, state, calls):
                    admin.create()
                    self._running(admin)
                    original = getattr(admin, missing)
                    setattr(admin, missing, None)
                    before = len(calls)
                    with self.assertRaises(M.ExperimentError) as raised:
                        admin.retire(dict(PEER))
                    self.assertEqual((raised.exception.stage, raised.exception.reason), ("RETIRE", "RESOURCE_UNKNOWN"))
                    self.assertEqual(len(calls), before)
                    self.assertFalse(admin.retired or admin.removed)
                    setattr(admin, missing, original)
                    self._originals(admin, state)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DirectoryPhase)
    if suite.countTestCases() != 6:
        raise SystemExit("FIXED_SIX_DIRECTORY_PHASE_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
