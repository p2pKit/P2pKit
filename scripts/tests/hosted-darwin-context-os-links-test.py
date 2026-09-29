#!/usr/bin/env python3
"""Six offline OS-tool link controls; no installed-OS or native qualification.

All metadata/admin returns are synthetic. The selected AST prefixes execute only
the actual observation/join blocks with fake boundaries, not prepare or a case.
"""
import ast
import copy
import ctypes  # Loaded before the explicit no-native audit boundary.
import hashlib
import importlib.util
from pathlib import Path
import stat
import sys
import types
import unittest
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
BASE_RUNTIME_SHA256 = "f56c579fcaf6d3593b15743f89bcb976d7246d63373ed55862317218ccdb0610"
# Six complete contextual hunks, seven logical edits. Reversal must reproduce
# ec3fc90f byte-for-byte, not erase arbitrary AST or guard changes.
REVIEWED_RUNTIME_PATCH = (('        channel.close()\n'
  '\n'
  '\n'
  'def parse_admin_metadata(raw, acl_raw, path, kind, *, mode=None, previous=None, size=None):\n'
  '    """Prospective BSD stat/ls parser; only an actual supported return qualifies."""\n'
  '    require(type(raw) is bytes and type(acl_raw) is bytes and type(path) is str and\n'
  '            0 < len(raw) <= 1024 and 0 < len(acl_raw) <= 4096, "ADMIN_CREATE", "BOUND")\n',
  '        channel.close()\n'
  '\n'
  '\n'
  'def parse_admin_metadata(raw, acl_raw, path, kind, *, mode=None, previous=None, size=None, '
  'expected_os_links=None):\n'
  '    """Prospective BSD stat/ls parser; only an actual supported return qualifies."""\n'
  '    require(type(raw) is bytes and type(acl_raw) is bytes and type(path) is str and\n'
  '            0 < len(raw) <= 1024 and 0 < len(acl_raw) <= 4096, "ADMIN_CREATE", "BOUND")\n'),
 ('            admin_site="META_INODE", admin_item=admin_object_item(path, kind))\n'
  '    require(not value["mode"] & 0o022, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_WRITE_MODE", admin_item=admin_object_item(path, kind))\n'
  '    require(kind == "directory" or value["nlink"] == 1, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_LINKS", admin_item=admin_object_item(path, kind))\n'
  '    require(mode is None or stat.S_IMODE(value["mode"]) == mode, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_EXACT_MODE", admin_item=admin_object_item(path, kind))\n',
  '            admin_site="META_INODE", admin_item=admin_object_item(path, kind))\n'
  '    require(not value["mode"] & 0o022, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_WRITE_MODE", admin_item=admin_object_item(path, kind))\n'
  '    require((kind == "directory" and expected_os_links is None) or (\n'
  '                kind == "file" and (\n'
  '                    (expected_os_links is None and value["nlink"] == 1) or (\n'
  '                        path in OS_TOOLS and type(expected_os_links) is int and\n'
  '                        expected_os_links > 0 and value["nlink"] == expected_os_links\n'
  '                    )\n'
  '                )\n'
  '            ), "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_LINKS", admin_item=admin_object_item(path, kind))\n'
  '    require(mode is None or stat.S_IMODE(value["mode"]) == mode, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_EXACT_MODE", admin_item=admin_object_item(path, kind))\n'),
 ('        return result\n'
  '\n'
  '    def metadata(self, path, kind, *, mode=None, previous=None, size=None):\n'
  '        first = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]\n'
  '        acl = self._run(["/bin/ls", "-lde", path], "ADMIN_CREATE")["stdout"]\n'
  '        second = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]\n'
  '        require(first == second, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '                admin_site="META_STABLE", admin_item=admin_object_item(path, kind))\n'
  '        return parse_admin_metadata(first, acl, path, kind, mode=mode, previous=previous, size=size)\n'
  '\n'
  '    def create(self):\n'
  '        require(self.root is None and self.path is None, "ADMIN_CREATE", "REFUSED")\n',
  '        return result\n'
  '\n'
  '    def metadata(self, path, kind, *, mode=None, previous=None, size=None):\n'
  '        expected_os_links = None\n'
  '        if type(path) is str and path in OS_TOOLS:\n'
  '            original = getattr(self.context, "os_files", None)\n'
  '            require(type(original) is dict and path in original, "ADMIN_CREATE", "REFUSED")\n'
  '            original = original[path]\n'
  '            require(type(original) is list and len(original) == 6 and\n'
  '                    all(type(value) is int for value in original) and original[5] > 0, "ADMIN_CREATE", '
  '"REFUSED")\n'
  '            expected_os_links = original[5]\n'
  '        first = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]\n'
  '        acl = self._run(["/bin/ls", "-lde", path], "ADMIN_CREATE")["stdout"]\n'
  '        second = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]\n'
  '        require(first == second, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '                admin_site="META_STABLE", admin_item=admin_object_item(path, kind))\n'
  '        return parse_admin_metadata(first, acl, path, kind, mode=mode, previous=previous, size=size,\n'
  '                                    expected_os_links=expected_os_links)\n'
  '\n'
  '    def create(self):\n'
  '        require(self.root is None and self.path is None, "ADMIN_CREATE", "REFUSED")\n'),
 ('                        source_site="OS_MODE", source_item=source_os_item(name))\n'
  '                require(stat.S_ISDIR(info.st_mode) if name in OS_PARENTS else stat.S_ISREG(info.st_mode),\n'
  '                        "SOURCE", "IDENTITY_CHANGED", source_site="OS_TYPE", '
  'source_item=source_os_item(name))\n'
  '                context.os_files[name] = [info.st_dev, info.st_ino, info.st_mode, info.st_uid, '
  'info.st_gid]\n'
  '            version = capture_fixed(["/usr/bin/sw_vers", "-productVersion"], end, context.os_env)\n'
  '            require(version["code"] == 0 and version["stderr"] == b"" and\n'
  '                    re.fullmatch(rb"26\\.[0-9]+(?:\\.[0-9]+)?\\n", version["stdout"]), "SOURCE", '
  '"UNSUPPORTED")\n',
  '                        source_site="OS_MODE", source_item=source_os_item(name))\n'
  '                require(stat.S_ISDIR(info.st_mode) if name in OS_PARENTS else stat.S_ISREG(info.st_mode),\n'
  '                        "SOURCE", "IDENTITY_CHANGED", source_site="OS_TYPE", '
  'source_item=source_os_item(name))\n'
  '                # Installed OS tools retain their original link count; private\n'
  '                # files still require one link. Directory child counts may change.\n'
  '                context.os_files[name] = ([info.st_dev, info.st_ino, info.st_mode, info.st_uid, '
  'info.st_gid] +\n'
  '                                          ([info.st_nlink] if name in OS_TOOLS else []))\n'
  '            version = capture_fixed(["/usr/bin/sw_vers", "-productVersion"], end, context.os_env)\n'
  '            require(version["code"] == 0 and version["stderr"] == b"" and\n'
  '                    re.fullmatch(rb"26\\.[0-9]+(?:\\.[0-9]+)?\\n", version["stdout"]), "SOURCE", '
  '"UNSUPPORTED")\n'),
 ('                  "github": context.github, "allocation": context.allocation, "account": context.account,\n'
  '                  "foreground": context.foreground, "boot": context.boot, "source": context.source,\n'
  '                  "interpreter": context.interpreter, "pythonVersion": sys.version, "osVersion": '
  'context.os_version,\n'
  '                  "policySha256": POLICY_SHA256, "policyExpires": POLICY_EXPIRES,\n'
  '                  "recipientValidationReturned": True, "startedMonotonicNs": context.started,\n'
  '                  "preparedMonotonicNs": time.monotonic_ns(), "stepEndNs": context.step_end, "jobEndNs": '
  'context.job_end}))\n',
  '                  "github": context.github, "allocation": context.allocation, "account": context.account,\n'
  '                  "foreground": context.foreground, "boot": context.boot, "source": context.source,\n'
  '                  "interpreter": context.interpreter, "pythonVersion": sys.version, "osVersion": '
  'context.os_version,\n'
  '                  "osFiles": context.os_files,\n'
  '                  "policySha256": POLICY_SHA256, "policyExpires": POLICY_EXPIRES,\n'
  '                  "recipientValidationReturned": True, "startedMonotonicNs": context.started,\n'
  '                  "preparedMonotonicNs": time.monotonic_ns(), "stepEndNs": context.step_end, "jobEndNs": '
  'context.job_end}))\n'),
 ('    if case == "N1":\n'
  '        for name in (*OS_PARENTS, *OS_TOOLS):\n'
  '            observed = admin.metadata(name, "directory" if name in OS_PARENTS else "file")\n'
  '            require([observed[key] for key in ("dev", "ino", "mode", "uid", "gid")] == '
  'context.os_files[name],\n'
  '                    "SOURCE", "IDENTITY_CHANGED", source_site="OS_FIRST_IDENTITY", '
  'source_item=source_os_item(name))\n'
  '    else:\n'
  '        for name, original in context.os_files.items():\n'
  '            info = physical(name).lstat()\n'
  '            require([info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] == original,\n'
  '                    "SOURCE", "IDENTITY_CHANGED", source_site="OS_NEXT_IDENTITY", '
  'source_item=source_os_item(name))\n'
  '    control_path = directory / "control.sock"\n'
  '    require(len(str(control_path).encode("utf-8")) + 1 <= 104, "IDENTITY", "BOUND")\n',
  '    if case == "N1":\n'
  '        for name in (*OS_PARENTS, *OS_TOOLS):\n'
  '            observed = admin.metadata(name, "directory" if name in OS_PARENTS else "file")\n'
  '            require([observed[key] for key in ("dev", "ino", "mode", "uid", "gid")] +\n'
  '                    ([observed["nlink"]] if name in OS_TOOLS else []) == context.os_files[name],\n'
  '                    "SOURCE", "IDENTITY_CHANGED", source_site="OS_FIRST_IDENTITY", '
  'source_item=source_os_item(name))\n'
  '    else:\n'
  '        for name, original in context.os_files.items():\n'
  '            info = physical(name).lstat()\n'
  '            require([info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] +\n'
  '                    ([info.st_nlink] if name in OS_TOOLS else []) == original,\n'
  '                    "SOURCE", "IDENTITY_CHANGED", source_site="OS_NEXT_IDENTITY", '
  'source_item=source_os_item(name))\n'
  '    control_path = directory / "control.sock"\n'
  '    require(len(str(control_path).encode("utf-8")) + 1 <= 104, "IDENTITY", "BOUND")\n'))


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("OFFLINE_OS_LINK_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_OS_LINK_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_os_link_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
TOOL = "/usr/bin/stat"
PRIVATE = "/private/var/db/p2pkit-context.ABCDEFGHIJ/job.KLMNOPQRST"
FIELDS = ("dev", "ino", "mode", "uid", "gid", "nlink")


def expression(source):
    return ast.dump(ast.parse(source, mode="eval").body, include_attributes=False)


def restore_reviewed_preimage(source):
    if len(REVIEWED_RUNTIME_PATCH) != 6:
        raise AssertionError("EXACT_SIX_REVIEWED_HUNKS_REQUIRED")
    for before, after in reversed(REVIEWED_RUNTIME_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_OS_LINK_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_REVIEWED_OS_LINK_DELTA_CHANGED")
    return source


def inputs(path, *, kind="file", links=1, **changes):
    value = dict(dev=1, ino=2, mode=(stat.S_IFDIR | 0o700) if kind == "directory" else
                 (stat.S_IFREG | 0o755), uid=0, gid=0, nlink=links, size=7, mtime=100, ctime=100)
    value.update(changes)
    raw = (":".join(format(value[key], "o") if key == "mode" else str(value[key])
                   for key in (*FIELDS, "size", "mtime", "ctime")) + "\n").encode("ascii")
    listing = (stat.filemode(value["mode"]) + " 1 root wheel 7 Sep 29 00:00 " + path + "\n").encode("ascii")
    return raw, listing, value


def info_for(name, *, links=3, **changes):
    value = dict(st_dev=1, st_ino=2, st_mode=(stat.S_IFDIR if name in M.OS_PARENTS else stat.S_IFREG) | 0o755,
                 st_uid=0, st_gid=0, st_nlink=links)
    value.update(changes)
    return types.SimpleNamespace(**value)


def identity(info, name):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] + (
        [info.st_nlink] if name in M.OS_TOOLS else [])


def as_metadata(info):
    return {key: getattr(info, "st_" + key) for key in FIELDS}


def execute_prefix(nodes, namespace):
    # Source's two fixed observation blocks only, under fake acquisition.
    module = ast.fix_missing_locations(ast.Module(body=copy.deepcopy(nodes), type_ignores=[]))
    exec(compile(module, "SYNTHETIC_OS_OBSERVATION_PREFIX_ONLY", "exec"), namespace)


class OsLinks(unittest.TestCase):
    def _failure(self, callback, *, reason="IDENTITY_CHANGED", site=None):
        with self.assertRaises(M.ExperimentError) as raised:
            callback()
        self.assertEqual(raised.exception.reason, reason)
        if site is not None:
            self.assertEqual(raised.exception.admin_site, site)
        return raised.exception

    def test_01_complete_reviewed_delta_and_mutation_containment(self):
        source = SOURCE.read_text(encoding="utf-8")
        restore_reviewed_preimage(source)
        for before, after in (
            ('value["nlink"] == expected_os_links', 'value["nlink"] >= 1'),
            ('expected_os_links = original[5]', 'expected_os_links = 1'),
            ('path in OS_TOOLS and type(expected_os_links) is int', 'True'),
            ('([info.st_nlink] if name in OS_TOOLS else []) == original',
             '([] if name in OS_TOOLS else []) == original'),
            ('"osFiles": context.os_files', '"osFiles": {}'),
            ('before.st_nlink == 1', 'before.st_nlink >= 1'),
            ('require(info.st_uid == 0, "SOURCE"', 'require(True, "SOURCE"'),
            ('require(error.errno == errno.ENOENT, "RETIRE"', 'require(True, "RETIRE"'),
            ('CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
            ('context.recipient_original', 'context.replacement_recipient'),
            ('        first = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]',
             '        self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")\n'
             '        first = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]'),
        ):
            changed = source.replace(before, after, 1)
            self.assertNotEqual(changed, source)
            with self.assertRaises(AssertionError):
                restore_reviewed_preimage(changed)

    def test_02_default_singleton_and_exact_os_override(self):
        for path in M.OS_TOOLS:
            raw, listing, value = inputs(path)
            self.assertEqual(M.parse_admin_metadata(raw, listing, path, "file"), value)
            for count in (1, 3, 7):  # Synthetic choices, not installed counts.
                raw, listing, value = inputs(path, links=count)
                self.assertEqual(M.parse_admin_metadata(raw, listing, path, "file",
                                                       expected_os_links=count), value)
            raw, listing, _ = inputs(path, links=3)
            self._failure(lambda: M.parse_admin_metadata(raw, listing, path, "file"), site="META_LINKS")
            self._failure(lambda: M.parse_admin_metadata(raw, listing, path, "file",
                                                        expected_os_links=1), site="META_LINKS")
        class IntegerSubclass(int):
            pass
        for baseline in (True, False, 0, -1, 1.0, "3", [], {}, (3,), IntegerSubclass(3)):
            raw, listing, _ = inputs(TOOL, links=3)
            self._failure(lambda: M.parse_admin_metadata(raw, listing, TOOL, "file",
                                                        expected_os_links=baseline), site="META_LINKS")
        for path in (PRIVATE, "/tmp/usr/bin/stat", "/usr/bin/stat.extra", "/usr/bin/../bin/stat", "/usr/bin/stat/"):
            raw, listing, _ = inputs(path, links=2)
            self._failure(lambda: M.parse_admin_metadata(raw, listing, path, "file",
                                                        expected_os_links=2), site="META_LINKS")
            self._failure(lambda: M.parse_admin_metadata(raw, listing, path, "file"), site="META_LINKS")
            raw, listing, value = inputs(path)
            self.assertEqual(M.parse_admin_metadata(raw, listing, path, "file"), value)
            self._failure(lambda: M.parse_admin_metadata(raw, listing, path, "file",
                                                        expected_os_links=1), site="META_LINKS")
        path = "/private/var/db"
        raw, listing, value = inputs(path, kind="directory", links=3)
        self.assertEqual(M.parse_admin_metadata(raw, listing, path, "directory"), value)
        self._failure(lambda: M.parse_admin_metadata(raw, listing, path, "directory",
                                                    expected_os_links=3), site="META_LINKS")

    def test_03_original_single_observation_and_private_baseline_record(self):
        tree = ast.parse(SOURCE.read_text(), feature_version=(3, 9))
        prepare = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "prepare")
        initial = [node for node in ast.walk(prepare) if isinstance(node, ast.Assign) and
                   any(ast.dump(target, include_attributes=False) ==
                       ast.dump(ast.parse("context.os_files = {}").body[0].targets[0], include_attributes=False)
                       for target in node.targets)]
        self.assertEqual(len(initial), 1)
        self.assertEqual(ast.dump(initial[0].value, include_attributes=False), expression("{}"))
        loops = [node for node in ast.walk(prepare) if isinstance(node, ast.For) and
                 ast.dump(node.iter, include_attributes=False) == expression("(*OS_PARENTS, *OS_TOOLS)")]
        self.assertEqual(len(loops), 1)
        names = (*M.OS_PARENTS, *M.OS_TOOLS)
        infos = {name: info_for(name, links=index + 2) for index, name in enumerate(names)}
        observations = []
        def physical(name):
            def lstat():
                observations.append(name)
                return infos[name]
            return types.SimpleNamespace(lstat=lstat)
        context = types.SimpleNamespace()
        execute_prefix([initial[0], loops[0]], dict(context=context, physical=physical, stat=stat,
                       require=M.require, source_os_item=M.source_os_item, OS_PARENTS=M.OS_PARENTS, OS_TOOLS=M.OS_TOOLS))
        self.assertEqual(observations, list(names))
        self.assertEqual(context.os_files, {name: identity(infos[name], name) for name in names})
        held = copy.deepcopy(context.os_files)
        for value in infos.values():
            value.st_nlink = 999
        self.assertEqual(context.os_files, held)
        self.assertTrue(all(len(context.os_files[name]) == 6 for name in M.OS_TOOLS))
        self.assertTrue(all(len(context.os_files[name]) == 5 for name in M.OS_PARENTS))
        records = [node for node in ast.walk(prepare) if isinstance(node, ast.Call) and
                   isinstance(node.func, ast.Name) and node.func.id == "write_new" and node.args and
                   isinstance(node.args[0], ast.BinOp) and isinstance(node.args[0].right, ast.Constant) and
                   node.args[0].right.value == "original-foreground.json"]
        self.assertEqual(len(records), 1)
        data = records[0].args[1].args[0]
        entries = [value for key, value in zip(data.keys, data.values)
                   if isinstance(key, ast.Constant) and key.value == "osFiles"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(ast.dump(entries[0], include_attributes=False), expression("context.os_files"))
        self.assertEqual(SOURCE.read_text().count('"osFiles"'), 1)
        self.assertNotIn("osFiles", M.PREPARED_KEYS)

    def test_04_metadata_uses_only_original_validated_count(self):
        raw, listing, value = inputs(TOOL, links=3)
        held = [value[key] for key in FIELDS]
        baseline = {TOOL: list(held)}
        admin = M.Admin.__new__(M.Admin)
        admin.context = types.SimpleNamespace(os_files=baseline)
        admin._run = Mock(side_effect=[{"stdout": raw}, {"stdout": listing}, {"stdout": raw}])
        with patch.object(M, "parse_admin_metadata", wraps=M.parse_admin_metadata) as parser:
            self.assertEqual(admin.metadata(TOOL, "file"), value)
            self.assertEqual(parser.call_args.kwargs["expected_os_links"], 3)
        self.assertEqual(admin._run.call_args_list, [
            call(["/usr/bin/stat", "-f", M.STAT_FORMAT, TOOL], "ADMIN_CREATE"),
            call(["/bin/ls", "-lde", TOOL], "ADMIN_CREATE"),
            call(["/usr/bin/stat", "-f", M.STAT_FORMAT, TOOL], "ADMIN_CREATE")])
        self.assertEqual(baseline, {TOOL: held})
        for data in (None, {}, [], {TOOL: None}, {TOOL: held[:5]}, {TOOL: [*held, 3]},
                     {TOOL: tuple(held)}, *({TOOL: [*held[:5], bad]} for bad in (0, -1, True, "3", 3.0)),
                     {TOOL: [False, *held[1:]]}):
            admin = M.Admin.__new__(M.Admin)
            admin.context = types.SimpleNamespace(os_files=data)
            admin._run = Mock(side_effect=AssertionError("INVALID_BASELINE_MUST_PRECEDE_IO"))
            self._failure(lambda: admin.metadata(TOOL, "file"), reason="REFUSED")
            admin._run.assert_not_called()
        admin = M.Admin.__new__(M.Admin)
        admin.context = types.SimpleNamespace()
        admin._run = Mock(side_effect=AssertionError("MISSING_BASELINE_MUST_PRECEDE_IO"))
        self._failure(lambda: admin.metadata(TOOL, "file"), reason="REFUSED")
        admin._run.assert_not_called()
        # Returned metadata cannot replace the held original link count.
        wrong_raw, wrong_listing, _ = inputs(TOOL, links=4)
        admin.context = types.SimpleNamespace(os_files={TOOL: held})
        admin._run = Mock(side_effect=[{"stdout": wrong_raw}, {"stdout": wrong_listing}, {"stdout": wrong_raw}])
        self._failure(lambda: admin.metadata(TOOL, "file"), site="META_LINKS")
        self.assertEqual(admin.context.os_files[TOOL], held)
        admin._run = Mock(side_effect=[{"stdout": raw}, {"stdout": listing}, {"stdout": wrong_raw}])
        with patch.object(M, "parse_admin_metadata") as parser:
            self._failure(lambda: admin.metadata(TOOL, "file"), site="META_STABLE")
            parser.assert_not_called()
        raw, listing, _ = inputs(PRIVATE, links=2)
        admin.context = types.SimpleNamespace(os_files={PRIVATE: [1, 2, stat.S_IFREG | 0o755, 0, 0, 2]})
        admin._run = Mock(side_effect=[{"stdout": raw}, {"stdout": listing}, {"stdout": raw}])
        self._failure(lambda: admin.metadata(PRIVATE, "file"), site="META_LINKS")

    def test_05_first_and_later_identity_joins(self):
        tree = ast.parse(SOURCE.read_text(), feature_version=(3, 9))
        case = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "perform_case")
        prefixes = [node for node in case.body if isinstance(node, ast.If) and
                    ast.dump(node.test, include_attributes=False) == expression('case == "N1"')]
        self.assertEqual(len(prefixes), 1)
        names = (*M.OS_PARENTS, *M.OS_TOOLS)
        original = {name: info_for(name) for name in names}
        held = {name: identity(info, name) for name, info in original.items()}
        def invoke(selected, changes):
            current = {name: types.SimpleNamespace(**vars(info)) for name, info in original.items()}
            for name, change in changes.items():
                for key, value in change.items():
                    setattr(current[name], "st_" + key, value)
            observations = []
            def metadata(name, kind):
                observations.append(name)
                self.assertEqual(kind, "directory" if name in M.OS_PARENTS else "file")
                return as_metadata(current[name])
            def physical(name):
                def lstat():
                    observations.append(name)
                    return current[name]
                return types.SimpleNamespace(lstat=lstat)
            context = types.SimpleNamespace(os_files=copy.deepcopy(held))
            execute_prefix(prefixes, dict(case=selected, admin=types.SimpleNamespace(metadata=metadata),
                           context=context, physical=physical, require=M.require, source_os_item=M.source_os_item,
                           OS_PARENTS=M.OS_PARENTS, OS_TOOLS=M.OS_TOOLS))
            self.assertEqual(observations, list(names))
            self.assertEqual(context.os_files, held)
        for selected in ("N1", "N2", "N3", "N4"):
            invoke(selected, {})
            invoke(selected, {"/private/var/db": {"nlink": 999}})
            for field in FIELDS:
                with self.assertRaises(M.ExperimentError) as raised:
                    invoke(selected, {TOOL: {field: getattr(original[TOOL], "st_" + field) + 1}})
                self.assertEqual(raised.exception.stage, "SOURCE")
                self.assertEqual(raised.exception.source_site,
                                 "OS_FIRST_IDENTITY" if selected == "N1" else "OS_NEXT_IDENTITY")
            for field in FIELDS[:5]:
                with self.assertRaises(M.ExperimentError):
                    invoke(selected, {"/private/var/db": {field: getattr(original["/private/var/db"], "st_" + field) + 1}})

    def test_06_original_ownership_acl_and_private_checks_remain(self):
        raw, listing, value = inputs(TOOL, links=3)
        self.assertEqual(M.parse_admin_metadata(raw, listing, TOOL, "file", expected_os_links=3), value)
        for change, site in (
            ({"mode": stat.S_IFDIR | 0o755}, "META_TYPE"), ({"uid": 501}, "META_OWNER"),
            ({"gid": 2 ** 32}, "META_GROUP"), ({"ino": 0}, "META_INODE"),
            ({"mode": stat.S_IFREG | 0o775}, "META_WRITE_MODE")):
            changed, acl, _ = inputs(TOOL, links=3, **change)
            self._failure(lambda: M.parse_admin_metadata(changed, acl, TOOL, "file",
                                                        expected_os_links=3), site=site)
        for options, site in (({"mode": 0o600}, "META_EXACT_MODE"), ({"size": 8}, "META_SIZE"),
                              ({"previous": {**value, "nlink": 2}}, "META_PREVIOUS"),
                              ({"previous": {**value, "dev": 8}}, "META_PREVIOUS")):
            self._failure(lambda: M.parse_admin_metadata(raw, listing, TOOL, "file",
                                                        expected_os_links=3, **options), site=site)
        for acl in (listing.replace(b"-rwxr-xr-x", b"-rwxr-xr-x+"),
                    listing + b" 0: user:synthetic allow read\n"):
            self._failure(lambda: M.parse_admin_metadata(raw, acl, TOOL, "file",
                                                        expected_os_links=3), reason="UNSUPPORTED")
        raw, listing, value = inputs(PRIVATE, mode=stat.S_IFREG | 0o600)
        self.assertEqual(M.parse_admin_metadata(raw, listing, PRIVATE, "file", mode=0o600), value)
        changed, listing, _ = inputs(PRIVATE, mode=stat.S_IFREG | 0o600, links=2)
        self._failure(lambda: M.parse_admin_metadata(changed, listing, PRIVATE, "file", mode=0o600), site="META_LINKS")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OsLinks)
    if suite.countTestCases() != 6:
        raise SystemExit("FIXED_SIX_OS_LINK_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
