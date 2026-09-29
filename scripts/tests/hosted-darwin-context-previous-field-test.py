#!/usr/bin/env python3
"""Five offline first-unequal-field controls, never native qualification.

The comparison-prefix model executes the actual parser's previous-identity block
under synthetic mappings; it does not acquire metadata or run a native case.
"""
import ast
import contextlib
import copy
import ctypes  # Import before the no-native audit boundary.
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
BASE_RUNTIME_SHA256 = "cf77359b90c783d432bb6b5a02742f4c941895eaf7241d48cb8362b57c42c2af"
REVIEWED_RUNTIME_PATCH = (('    """Only fixed source-owned fields, not raw private exceptions, reach stdout."""\n'
  '\n'
  '    def __init__(self, stage, reason, errno_name="NONE", *, source_site=None, source_item=None,\n'
  '                 admin_site=None, admin_item=None):\n'
  '        self.stage = stage if stage in STAGES else "PREPARE"\n'
  '        self.reason = reason if reason in REASONS else "REFUSED"\n'
  '        self.errno_name = errno_name if errno_name in ERRNOS else "UNKNOWN"\n'
  '        self.source_site, self.source_item = source_site, source_item\n'
  '        self.admin_site, self.admin_item = admin_site, admin_item\n'
  '        super().__init__(self.stage + "/" + self.reason + "/" + self.errno_name)\n'
  '\n'
  '\n'
  'def require(value, stage, reason="REFUSED", errno_name="NONE", *, source_site=None, source_item=None,\n'
  '            admin_site=None, admin_item=None):\n'
  '    if not value:\n'
  '        raise ExperimentError(stage, reason, errno_name, source_site=source_site, '
  'source_item=source_item,\n'
  '                              admin_site=admin_site, admin_item=admin_item)\n'
  '\n'
  '\n'
  'def errno_name(value):\n',
  '    """Only fixed source-owned fields, not raw private exceptions, reach stdout."""\n'
  '\n'
  '    def __init__(self, stage, reason, errno_name="NONE", *, source_site=None, source_item=None,\n'
  '                 admin_site=None, admin_item=None, admin_field=None):\n'
  '        self.stage = stage if stage in STAGES else "PREPARE"\n'
  '        self.reason = reason if reason in REASONS else "REFUSED"\n'
  '        self.errno_name = errno_name if errno_name in ERRNOS else "UNKNOWN"\n'
  '        self.source_site, self.source_item = source_site, source_item\n'
  '        self.admin_site, self.admin_item = admin_site, admin_item\n'
  '        self.admin_field = admin_field\n'
  '        super().__init__(self.stage + "/" + self.reason + "/" + self.errno_name)\n'
  '\n'
  '\n'
  'def require(value, stage, reason="REFUSED", errno_name="NONE", *, source_site=None, source_item=None,\n'
  '            admin_site=None, admin_item=None, admin_field=None):\n'
  '    if not value:\n'
  '        raise ExperimentError(stage, reason, errno_name, source_site=source_site, '
  'source_item=source_item,\n'
  '                              admin_site=admin_site, admin_item=admin_item, admin_field=admin_field)\n'
  '\n'
  '\n'
  'def errno_name(value):\n'),
 ('    site, item = getattr(error, "admin_site", None), getattr(error, "admin_item", None)\n'
  '    site = site if type(site) is str and site in ADMIN_SITES else "UNKNOWN"\n'
  '    item = item if site in ADMIN_SITES and type(item) is str and item in ADMIN_ITEMS else "NONE"\n'
  '    return "P2PKIT_CONTEXT_ADMIN_SITE|" + site + "|" + item\n'
  '\n'
  '\n',
  '    site, item = getattr(error, "admin_site", None), getattr(error, "admin_item", None)\n'
  '    site = site if type(site) is str and site in ADMIN_SITES else "UNKNOWN"\n'
  '    item = item if site in ADMIN_SITES and type(item) is str and item in ADMIN_ITEMS else "NONE"\n'
  '    if site == "META_PREVIOUS":\n'
  '        field = getattr(error, "admin_field", None)\n'
  '        field = field.upper() if type(field) is str and field in ("dev", "ino", "mode", "uid", "gid", '
  '"nlink") else "UNKNOWN"\n'
  '        return "P2PKIT_CONTEXT_ADMIN_SITE|" + site + "|" + item + "|" + field\n'
  '    return "P2PKIT_CONTEXT_ADMIN_SITE|" + site + "|" + item\n'
  '\n'
  '\n'),
 ('    require(size is None or value["size"] == size, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_SIZE", admin_item=admin_object_item(path, kind))\n'
  '    if previous is not None:\n'
  '        require(all(value[key] == previous[key] for key in ("dev", "ino", "mode", "uid", "gid", '
  '"nlink")),\n'
  '                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS", '
  'admin_item=admin_object_item(path, kind))\n'
  '    return value\n'
  '\n'
  '\n',
  '    require(size is None or value["size"] == size, "ADMIN_CREATE", "IDENTITY_CHANGED",\n'
  '            admin_site="META_SIZE", admin_item=admin_object_item(path, kind))\n'
  '    if previous is not None:\n'
  '        previous_field = None\n'
  '\n'
  '        def previous_keys():\n'
  '            nonlocal previous_field\n'
  '            for previous_field in ("dev", "ino", "mode", "uid", "gid", "nlink"):\n'
  '                yield previous_field\n'
  '\n'
  '        require(all(value[key] == previous[key] for key in previous_keys()),\n'
  '                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS", '
  'admin_item=admin_object_item(path, kind),\n'
  '                admin_field=previous_field)\n'
  '    return value\n'
  '\n'
  '\n'))



def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("OFFLINE_PREVIOUS_FIELD_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_PREVIOUS_FIELD_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_previous_field_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
FIELDS = ("dev", "ino", "mode", "uid", "gid", "nlink")
PREFIX = "P2PKIT_CONTEXT_ADMIN_SITE|META_PREVIOUS|PRIVATE_DIRECTORY|"
PATH = "/private/var/db/p2pkit-context.ABCDEFGHIJ"
RAW = b"1:2:40700:0:0:2:0:170:170\n"
ACL = ("drwx------ 2 root wheel 0 Sep 29 00:00 " + PATH + "\n").encode("ascii")
ORIGINAL_BLOCK = 'if previous is not None:\n    require(all(value[key] == previous[key] for key in ("dev", "ino", "mode", "uid", "gid", "nlink")),\n            "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS", admin_item=admin_object_item(path, kind))\n'


def restore_preimage(source):
    if len(REVIEWED_RUNTIME_PATCH) != 3:
        raise AssertionError("EXACT_THREE_DIAGNOSTIC_HUNKS_REQUIRED")
    for before, after in reversed(REVIEWED_RUNTIME_PATCH):
        if source.count(after) != 1:
            raise AssertionError("REVIEWED_PREVIOUS_FIELD_DELTA_CHANGED")
        source = source.replace(after, before, 1)
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != BASE_RUNTIME_SHA256:
        raise AssertionError("OUTSIDE_PREVIOUS_FIELD_DELTA_CHANGED")
    return source


def comparison_prefix(*, original=False):
    if original:
        block = ast.parse(ORIGINAL_BLOCK).body[0]
    else:
        parser = next(node for node in ast.parse(SOURCE.read_text(), feature_version=(3, 9)).body
                      if isinstance(node, ast.FunctionDef) and node.name == "parse_admin_metadata")
        blocks = [node for node in parser.body if isinstance(node, ast.If) and
                  ast.dump(node.test, include_attributes=False) ==
                  ast.dump(ast.parse("previous is not None", mode="eval").body, include_attributes=False)]
        if len(blocks) != 1:
            raise AssertionError("EXACT_PREVIOUS_IDENTITY_BLOCK_REQUIRED")
        block = blocks[0]
    function = ast.parse("def compare(value, previous, path, kind): pass").body[0]
    function.body = [copy.deepcopy(block), ast.Return(value=ast.Constant(value=None))]
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {"require": M.require, "admin_object_item": M.admin_object_item}
    exec(compile(module, "SYNTHETIC_PREVIOUS_IDENTITY_PREFIX_ONLY", "exec"), namespace)
    return namespace["compare"]


class PreviousField(unittest.TestCase):
    def test_01_complete_delta_preserves_original_runtime(self):
        source = SOURCE.read_text(encoding="utf-8")
        restored = restore_preimage(source)
        self.assertIn(ORIGINAL_BLOCK.replace("\n", "\n    ").rstrip(), restored)
        for before, after in (
            ('for previous_field in ("dev", "ino", "mode", "uid", "gid", "nlink"):',
             'for previous_field in ("ino", "dev", "mode", "uid", "gid", "nlink"):'),
            ('all(value[key] == previous[key] for key in previous_keys())',
             'all(value[key] == previous[key] for key in previous_keys() if key != "nlink")'),
            ('admin_field=previous_field)', 'admin_field="nlink")'),
            ('field = field.upper() if type(field) is str', 'field = str(field).upper() if True'),
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

    def test_02_actual_parser_first_unequal_field_only(self):
        original = M.parse_admin_metadata(RAW, ACL, PATH, "directory", mode=0o700)
        self.assertEqual(M.parse_admin_metadata(RAW, ACL, PATH, "directory", mode=0o700,
                                               previous=dict(original)), original)
        for index, field in enumerate(FIELDS):
            previous = dict(original)
            for later in FIELDS[index:]:
                previous[later] += 1
            with self.assertRaises(M.ExperimentError) as caught:
                M.parse_admin_metadata(RAW, ACL, PATH, "directory", mode=0o700, previous=previous)
            error = caught.exception
            self.assertEqual(error.admin_field, field)
            self.assertEqual(M.public_admin_site(error), PREFIX + field.upper())
            self.assertEqual(M.public_error(error), "P2PKIT_CONTEXT_FAILURE|ADMIN_CREATE|IDENTITY_CHANGED|NONE")
            self.assertEqual(str(error), "ADMIN_CREATE/IDENTITY_CHANGED/NONE")
        # A false earlier singleton/ownership guard cannot acquire this suffix.
        raw = RAW.replace(b"40700", b"100600")
        acl = ACL.replace(b"drwx------", b"-rw-------")
        with self.assertRaises(M.ExperimentError) as caught:
            M.parse_admin_metadata(raw, acl, PATH, "file", previous=original)
        self.assertEqual(caught.exception.admin_site, "META_LINKS")
        self.assertIsNone(caught.exception.admin_field)

    def test_03_exact_single_evaluation_short_circuit_and_exceptions(self):
        current, original = comparison_prefix(), comparison_prefix(original=True)
        marker = RuntimeError("SYNTHETIC_LOOKUP_COMPARISON_OR_BOOL_FAILURE")

        def observe(function, mismatch=None, fault=None, absent=False):
            trace = []

            def visit(operation, key):
                trace.append((operation, key))
                if fault == (operation, key):
                    raise marker

            class Truth:
                def __init__(self, key):
                    self.key = key

                def __bool__(self):
                    visit("bool", self.key)
                    return self.key != mismatch

            class Left:
                def __init__(self, key):
                    self.key = key

                def __eq__(self, _other):
                    visit("equal", self.key)
                    return Truth(self.key)

            class Mapping:
                def __init__(self, side):
                    self.side = side

                def __getitem__(self, key):
                    visit(self.side, key)
                    return Left(key) if self.side == "left" else 7

            try:
                value = function(Mapping("left"), None if absent else Mapping("right"), PATH, "directory")
                outcome = ("returned", value)
            except BaseException as error:
                outcome = ("raised", error)
            return trace, outcome

        for mismatch in (None, *FIELDS):
            old_trace, old = observe(original, mismatch)
            trace, result = observe(current, mismatch)
            self.assertEqual(trace, old_trace)
            reached = FIELDS if mismatch is None else FIELDS[:FIELDS.index(mismatch) + 1]
            self.assertEqual(trace, [(operation, key) for key in reached for operation in ("left", "right", "equal", "bool")])
            self.assertEqual(result[0], old[0])
            if mismatch is None:
                self.assertEqual(result, ("returned", None))
            else:
                self.assertIsInstance(result[1], M.ExperimentError)
                self.assertEqual(result[1].args, old[1].args)
                self.assertEqual(result[1].admin_field, mismatch)
                self.assertIsNone(old[1].admin_field)
        for key in FIELDS:
            for operation in ("left", "right", "equal", "bool"):
                old_trace, old = observe(original, fault=(operation, key))
                trace, result = observe(current, fault=(operation, key))
                self.assertEqual(trace, old_trace)
                self.assertIs(result[1], marker)
                self.assertIs(old[1], marker)
        for function in (current, original):
            self.assertEqual(observe(function, absent=True), ([], ("returned", None)))

    def test_04_public_field_cannot_expose_untrusted_values(self):
        class Hostile:
            def __str__(self):
                raise AssertionError("DO_NOT_STRINGIFY_DIAGNOSTIC_DATA")
            __repr__ = __str__
            def __hash__(self):
                raise AssertionError("DO_NOT_HASH_DIAGNOSTIC_DATA")
            def __eq__(self, _other):
                raise AssertionError("DO_NOT_COMPARE_DIAGNOSTIC_DATA")

        class StringSubclass(str):
            pass

        for field in FIELDS:
            error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS",
                                      admin_item="PRIVATE_DIRECTORY", admin_field=field)
            self.assertEqual(M.public_admin_site(error), PREFIX + field.upper())
        bad = (None, True, 7, [], {}, b"nlink", "NLINK", "private/SYNTHETIC_CANARY",
               "nlink\nSYNTHETIC_CANARY", StringSubclass("nlink"), Hostile())
        for field in bad:
            error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS",
                                      admin_item="PRIVATE_DIRECTORY", admin_field=field)
            self.assertEqual(M.public_admin_site(error), PREFIX + "UNKNOWN")
            for site in M.ADMIN_SITES - {"META_PREVIOUS"}:
                error.admin_site = site
                self.assertEqual(M.public_admin_site(error), "P2PKIT_CONTEXT_ADMIN_SITE|" + site + "|PRIVATE_DIRECTORY")
        error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS",
                                  admin_item="PRIVATE_DIRECTORY")
        del error.admin_field
        self.assertEqual(M.public_admin_site(error), PREFIX + "UNKNOWN")
        with patch.object(M, "ExperimentError", side_effect=AssertionError("TRUE_GUARD_MUST_NOT_CONSTRUCT_ERROR")):
            self.assertIsNone(M.require(True, "ADMIN_CREATE", admin_field=Hostile()))

    def test_05_actual_main_keeps_original_refusal_and_no_export(self):
        error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS",
                                  admin_item="PRIVATE_DIRECTORY", admin_field="nlink")
        output = io.StringIO()
        with patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), \
                patch.object(M.os, "umask"), patch.object(M, "experiment", side_effect=error), \
                patch.object(M, "finish_export") as export, patch.object(M, "upload_guard") as upload, \
                patch.object(M, "Darwin") as native, patch.object(M, "capture_fixed") as capture, \
                patch.object(M, "write_new") as write, contextlib.redirect_stdout(output):
            self.assertEqual(M.main(), 2)
            for boundary in (export, upload, native, capture, write):
                boundary.assert_not_called()
        self.assertEqual(output.getvalue(), "P2PKIT_CONTEXT_FAILURE|ADMIN_CREATE|IDENTITY_CHANGED|NONE\n" + PREFIX + "NLINK\n")
        with self.assertRaises(M.ExperimentError) as caught:
            with M.at_stage("RETIRE"):
                raise error
        self.assertIs(caught.exception, error)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PreviousField)
    if suite.countTestCases() != 5:
        raise SystemExit("FIXED_FIVE_PREVIOUS_FIELD_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
