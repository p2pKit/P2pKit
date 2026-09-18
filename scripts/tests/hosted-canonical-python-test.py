#!/usr/bin/env python3
"""Source-loader/argv controls, never execution of a generated init command.

Tiny ordinary-UID POSIX fixtures exercise file reads; native/process/network/
clock suppliers are blocked or modeled. No hosted, Windows, initializer, cache,
recipient, provider, scheduling or product acceptance follows from these tests.
"""
from __future__ import annotations

import ast
import builtins
from contextlib import ExitStack, contextmanager
import ctypes
import hashlib
import http.client
import importlib.machinery
import importlib.util
import json
import marshal
import os
from pathlib import Path
import shutil
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
NAMES = ("audit_processes.py", "run-audit-command.py")
HELPER = "hosted_canonical_python.py"
# Exact accepted pre-extraction literal at1fc4d4f2, not a hash obtained from the
# implementation under test. Independent review must check this expectation.
LOADER_SHA256 = "b6d6ec850d03fa6ecc5df4d096813df568514aa442c049520120dd9ea929045d"


@contextmanager
def no_execution():
    with ExitStack() as stack:
        for module, names in (
            (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
            (os, ("system", "popen", "fork", "posix_spawn", "posix_spawnp")),
            (ctypes, ("CDLL", "PyDLL", "WinDLL")),
            (socket, ("socket", "create_connection", "getaddrinfo")),
            (http.client, ("HTTPConnection", "HTTPSConnection")),
            (ssl, ("create_default_context",)),
            (time, ("time", "monotonic", "perf_counter", "clock_gettime_ns")),
        ):
            for name in names:
                stack.enter_context(patch.object(module, name,
                    side_effect=AssertionError("NATIVE_NETWORK_CLOCK_OR_CHILD_FORBIDDEN"), create=True))
        yield


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CanonicalModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not hasattr(os, "geteuid") or os.geteuid() == 0:
            raise AssertionError("these POSIX source-file controls require an actual ordinary UID")
        if (sys.flags.isolated, sys.flags.no_site, sys.dont_write_bytecode) != (1, 1, True):
            raise AssertionError("run in isolated Python -I -B -S")
        with no_execution():
            cls.B = load("bootstrap_canonical_source_models", SCRIPTS / "hosted_cache_bootstrap_canonical.py")
            # The bootstrap adapter did not import the ordinary controller.
            if any(getattr(value, "__file__", None) == str(SCRIPTS / "run-hosted-test-custody.py")
                   for value in sys.modules.values() if value is not None):
                raise AssertionError("bootstrap descriptor imported the ordinary controller")
            cls.C = load("ordinary_canonical_source_models", SCRIPTS / "run-hosted-test-custody.py")

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(no_execution())
        for name in ("Controller", "main"):
            self.stack.enter_context(patch.object(self.C, name,
                side_effect=AssertionError("ORDINARY_CONTROLLER_FORBIDDEN")))
        for name in ("main", "initialize", "execute"):
            self.stack.enter_context(patch.object(self.C.audit, name,
                side_effect=AssertionError("CANONICAL_EXECUTION_FORBIDDEN")))
        self.temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="p2pkit-canonical-model-")))

    @contextmanager
    def fixture(self):
        directory = self.temp / "scripts"
        directory.mkdir()
        for name in (HELPER, *NAMES):
            (directory / name).write_bytes((SCRIPTS / name).read_bytes())
        with patch.object(self.B, "SCRIPTS", directory), patch.object(self.C, "SCRIPTS", directory):
            yield directory

    def expect_both(self, expression="CANONICAL_HELPER_SOURCE"):
        for module in (self.C, self.B):
            with self.subTest(caller=module.__name__), self.assertRaisesRegex(RuntimeError, expression):
                module._load_canonical_helper()

    def descriptor(self, **changes):
        args = {"state": str(self.temp / "uncreated-state"), "expected_commit": "a" * 40, "role": "linux-x64"}
        args.update(changes)
        return json.loads(self.B.init_request(**args))

    def test_exact_old_literal_and_two_child_suppliers_survive_extraction(self):
        raw = (SCRIPTS / HELPER).read_bytes()
        self.assertEqual(self.C._CANONICAL_HELPER_SHA256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.B._CANONICAL_HELPER_SHA256, self.C._CANONICAL_HELPER_SHA256)
        for module in (self.C, self.B):
            helper = module._load_canonical_helper()
            self.assertEqual(hashlib.sha256(helper["CANONICAL_BOOTSTRAP"].encode()).hexdigest(), LOADER_SHA256)
            self.assertEqual(helper["CANONICAL_NAMES"], NAMES)
            self.assertEqual(helper["CANONICAL_SOURCE_LIMIT"], 512 * 1024)
        self.assertEqual(self.C.CANONICAL_NAMES, NAMES)
        self.assertEqual(self.C.CANONICAL_SOURCE_LIMIT, 512 * 1024)
        self.assertEqual(hashlib.sha256(self.C.CANONICAL_BOOTSTRAP.encode()).hexdigest(), LOADER_SHA256)
        tree = ast.parse(raw)
        self.assertFalse(any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)))

    def test_ordinary_argv_conversion_order_and_uncoerced_executable_are_unchanged(self):
        bindings = {NAMES[1]: "b" * 64, NAMES[0]: "a" * 64}
        executable = object()
        converted = []
        class Argument:
            def __str__(self):
                converted.append("once")
                return "argument with spaces"
        args = ("init", Argument(), None, False, 17, Path("relative"), b"bytes")
        actual = self.C.canonical_python(executable, bindings, *args)
        expected = [executable, "-I", "-B", "-S", "-c", self.C.CANONICAL_BOOTSTRAP, str(SCRIPTS),
                    '{"audit_processes.py":"' + "a" * 64 + '","run-audit-command.py":"' + "b" * 64 + '"}',
                    "init", "argument with spaces", "None", "False", "17", "relative", "b'bytes'"]
        self.assertEqual(actual, expected)
        self.assertIs(actual[0], executable)
        self.assertEqual(converted, ["once"])

    def test_ordinary_binding_error_identity_and_code_are_preserved(self):
        class Map(dict):
            pass
        good = {name: "a" * 64 for name in NAMES}
        bad = [None, [], {}, Map(good), {**good, "extra.py": "a" * 64}]
        for value in (True, 1, None, "a" * 63, "a" * 65, "A" * 64, "g" * 64):
            bad.append({**good, NAMES[0]: value})
        for value in bad:
            with self.subTest(value=value), self.assertRaises(self.C.ControllerError) as caught:
                self.C.canonical_python("not-executed", value, "init")
            self.assertEqual(str(caught.exception), "CANONICAL_SOURCE_BINDINGS")

    def test_ordinary_canonical_bindings_still_reads_exactly_two_suppliers(self):
        self.assertEqual(self.C.canonical_bindings(),
                         {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest() for name in NAMES})

    def test_reader_counterparts_are_exact_not_unreviewed_semantic_duplicates(self):
        source = [ast.parse((SCRIPTS / name).read_bytes())
                  for name in ("run-hosted-test-custody.py", "hosted_cache_bootstrap_canonical.py")]
        for name in ("_canonical_source", "_load_canonical_helper"):
            nodes = [next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
                     for tree in source]
            self.assertEqual(ast.dump(nodes[0], include_attributes=False), ast.dump(nodes[1], include_attributes=False))

    def test_cold_helper_load_has_no_import_cache_path_or_controller_side_effect(self):
        original_modules, original_path = dict(sys.modules), list(sys.path)
        def no_helper_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Python 3.12 pathlib internally requests its already-loaded ntpath
            # while constructing a Path. That stdlib operation is not an import
            # by captured helper code and must not mask this boundary's oracle.
            if name == "ntpath" and level == 0 and globals is not None and globals.get("__name__") == "pathlib":
                return original_modules["ntpath"]
            raise AssertionError("HELPER_IMPORT_FORBIDDEN")
        with patch.object(builtins, "__import__", side_effect=no_helper_import):
            for module in (self.C, self.B):
                helper = module._load_canonical_helper()
                self.assertEqual(helper["assemble"]("python", "scripts", "{}", "init")[-1], "init")
        self.assertEqual(sys.modules, original_modules)
        self.assertEqual(sys.path, original_path)

    def test_poisoned_module_aliases_and_ambient_path_are_not_used_or_removed(self):
        poison = SimpleNamespace(assemble=Mock(side_effect=AssertionError("AMBIENT_ALIAS_USED")))
        with patch.dict(sys.modules, {"hosted_canonical_python": poison, "p2pkit_canonical_helpers": poison}), \
                patch.object(sys, "path", [str(self.temp), *sys.path]):
            (self.temp / HELPER).write_text('raise AssertionError("AMBIENT_PATH_USED")\n')
            before_modules, before_path = dict(sys.modules), list(sys.path)
            for module in (self.C, self.B):
                self.assertEqual(module._load_canonical_helper()["CANONICAL_NAMES"], NAMES)
            self.assertEqual(sys.modules, before_modules)
            self.assertEqual(sys.path, before_path)
            poison.assemble.assert_not_called()

    def test_valid_poisoned_pyc_is_ignored_on_both_source_loading_paths(self):
        with self.fixture() as directory:
            path = directory / HELPER
            info = path.stat()
            pyc = Path(importlib.util.cache_from_source(str(path)))
            pyc.parent.mkdir()
            code = compile('raise AssertionError("POISONED_PYC_EXECUTED")\n', str(path), "exec")
            pyc.write_bytes(importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, int(info.st_mtime) & 0xffffffff,
                            info.st_size & 0xffffffff) + marshal.dumps(code))
            # Sanity: the synthetic cached program is actually loadable under -B.
            # It only raises a marker; no product/initializer/native call exists.
            loader = importlib.machinery.SourceFileLoader("pyc_poison_sanity", str(path))
            with self.assertRaisesRegex(AssertionError, "POISONED_PYC_EXECUTED"):
                exec(loader.get_code("pyc_poison_sanity"), {})
            for module in (self.C, self.B):
                self.assertEqual(module._load_canonical_helper()["CANONICAL_NAMES"], NAMES)

    def test_missing_helper_has_no_ambient_fallback(self):
        with self.fixture() as directory:
            (directory / HELPER).unlink()
            for module in (self.C, self.B):
                with self.subTest(caller=module.__name__), self.assertRaises(FileNotFoundError):
                    module._load_canonical_helper()

    def test_empty_helper_refuses_before_compile(self):
        with self.fixture() as directory, patch.object(builtins, "compile") as compiler:
            (directory / HELPER).write_bytes(b"")
            self.expect_both()
            compiler.assert_not_called()

    def test_oversized_helper_refuses_before_open(self):
        with self.fixture() as directory:
            (directory / HELPER).write_bytes(b"#" * (self.C._CANONICAL_HELPER_LIMIT + 1))
            with patch.object(os, "open") as opened:
                self.expect_both()
                opened.assert_not_called()

    def test_digest_mismatch_refuses_before_compiling_untrusted_code(self):
        with self.fixture() as directory, patch.object(builtins, "compile") as compiler:
            (directory / HELPER).write_text('raise AssertionError("MUST_NOT_EXECUTE")\n')
            self.expect_both("CANONICAL_HELPER_SOURCE_BINDING")
            compiler.assert_not_called()

    def test_helper_symlink_refuses_before_open(self):
        with self.fixture() as directory:
            path = directory / HELPER
            path.rename(directory / "original.py")
            path.symlink_to(directory / "original.py")
            with patch.object(os, "open") as opened:
                self.expect_both()
                opened.assert_not_called()

    def test_helper_hardlink_refuses_before_open(self):
        with self.fixture() as directory:
            os.link(directory / HELPER, directory / "other-link.py")
            with patch.object(os, "open") as opened:
                self.expect_both()
                opened.assert_not_called()

    def test_nonregular_helper_refuses_without_opening_fifo(self):
        with self.fixture() as directory:
            (directory / HELPER).unlink()
            os.mkfifo(directory / HELPER)
            with patch.object(os, "open") as opened:
                self.expect_both()
                opened.assert_not_called()

    def test_symlinked_source_ancestor_refuses_before_open(self):
        with self.fixture() as directory:
            moved = directory.with_name("actual-scripts")
            directory.rename(moved)
            directory.symlink_to(moved, target_is_directory=True)
            with patch.object(os, "open") as opened:
                self.expect_both()
                opened.assert_not_called()

    def test_modeled_reparse_file_and_ancestor_refuse_before_open(self):
        original = Path.lstat
        for selected in (SCRIPTS / HELPER, SCRIPTS):
            def lstat(path, *args, **kwargs):
                info = original(path, *args, **kwargs)
                if path == selected:
                    fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
                    return SimpleNamespace(**{**fields, "st_file_attributes": 0x400})
                return info
            with self.subTest(path=selected), patch.object(Path, "lstat", lstat), patch.object(os, "open") as opened:
                self.expect_both()
                opened.assert_not_called()

    def test_replacement_after_open_cannot_publish_matching_old_descriptor_bytes(self):
        with self.fixture() as directory:
            path = directory / HELPER
            original_read = os.read
            for module in (self.C, self.B):
                raw = path.read_bytes()
                done = []
                def read(fd, count):
                    block = original_read(fd, count)
                    if not done:
                        done.append(True)
                        replacement = directory / "replacement.py"
                        replacement.write_bytes(raw)
                        replacement.replace(path)
                    return block
                with self.subTest(caller=module.__name__), patch.object(os, "read", read), \
                        self.assertRaisesRegex(RuntimeError, "CANONICAL_HELPER_SOURCE"):
                    module._load_canonical_helper()
                self.assertEqual(done, [True])

    def test_descriptor_stamp_change_refuses_before_any_code_executes(self):
        original = os.fstat
        def changed(fd):
            info = original(fd)
            fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
            return SimpleNamespace(**{**fields, "st_ino": info.st_ino + 1})
        with patch.object(os, "fstat", changed), patch.object(builtins, "compile") as compiler:
            self.expect_both()
            compiler.assert_not_called()

    def test_first_read_exception_survives_one_failed_close_without_retry(self):
        class FalseError(RuntimeError):
            def __bool__(self):
                return False
        original_close = os.close
        for module in (self.C, self.B):
            first, secondary, closed = FalseError("first-read"), OSError("modeled-close"), []
            def close(fd):
                closed.append(fd)
                original_close(fd)
                raise secondary
            with self.subTest(caller=module.__name__), patch.object(os, "read", side_effect=first), \
                    patch.object(os, "close", close), patch.object(builtins, "compile") as compiler, \
                    self.assertRaises(FalseError) as caught:
                module._load_canonical_helper()
            self.assertIs(caught.exception, first)
            self.assertIs(caught.exception.__cause__, secondary)
            self.assertEqual(len(closed), 1)
            compiler.assert_not_called()

    def test_cancellation_closes_once_and_does_not_publish_a_helper(self):
        for module in (self.C, self.B):
            first = KeyboardInterrupt("synthetic-cancellation")
            with self.subTest(caller=module.__name__), patch.object(os, "read", side_effect=first), \
                    patch.object(os, "close", wraps=os.close) as close, patch.object(builtins, "compile") as compiler, \
                    self.assertRaises(KeyboardInterrupt) as caught:
                module._load_canonical_helper()
            self.assertIs(caught.exception, first)
            self.assertEqual(close.call_count, 1)
            compiler.assert_not_called()

    def test_successful_read_followed_by_failed_close_never_compiles(self):
        original_close = os.close
        for module in (self.C, self.B):
            first = OSError("modeled-close-only")
            def close(fd):
                original_close(fd)
                raise first
            with self.subTest(caller=module.__name__), patch.object(os, "close", close), \
                    patch.object(builtins, "compile") as compiler, self.assertRaises(OSError) as caught:
                module._load_canonical_helper()
            self.assertIs(caught.exception, first)
            compiler.assert_not_called()

    def test_closed_source_name_and_read_limits_have_no_override_route(self):
        for module in (self.C, self.B):
            for name, maximum in (("../" + HELPER, 100), ("foreign.py", 100), (HELPER, True),
                                  (HELPER, 0), (HELPER, 512 * 1024 + 1)):
                with self.subTest(caller=module.__name__, name=name, maximum=maximum), \
                        patch.object(os, "open") as opened, self.assertRaisesRegex(RuntimeError, "CANONICAL_HELPER_SOURCE"):
                    module._canonical_source(name, maximum)
                opened.assert_not_called()

    def test_descriptor_has_only_current_interpreter_and_fixed_init_argv_without_execution(self):
        with patch.object(importlib.util, "spec_from_file_location", side_effect=AssertionError("LAZY_CONTROLLER_IMPORT")):
            result = self.descriptor()
        self.assertEqual(result["python"], str(Path(sys.executable).resolve(strict=True)))
        self.assertEqual(result["argv"][:7], [result["python"], "-I", "-B", "-S", "-c",
                                            self.C.CANONICAL_BOOTSTRAP, str(SCRIPTS)])
        self.assertEqual(json.loads(result["argv"][7]), result["canonicalSources"])
        self.assertEqual(set(result["canonicalSources"]), set(NAMES))
        self.assertEqual(result["argv"][8:], ["init", "--root", str(ROOT), "--state", result["state"],
                                              "--expected-commit", "a" * 40, "--host", "linux-x64"])
        self.assertFalse(Path(result["state"]).exists())
        self.assertFalse(result["nextPhaseAuthority"])
        self.assertFalse(result["exportSaveAuthority"])
        self.assertEqual(result["sourceAdmission"], "NOT_ATTESTED_HERE")
        self.assertEqual(result["stateOwnership"], "NOT_ACQUIRED_OR_ATTESTED")
        self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(result["testAcceptance"], "NOT_PERFORMED")

    def test_existing_state_and_foreign_role_labels_are_not_promoted_to_admission(self):
        state = self.temp / "existing-state"
        state.mkdir()
        (state / "marker").write_bytes(b"preserve")
        for role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64"):
            result = self.descriptor(state=str(state), role=role)
            self.assertEqual(result["role"], role)
            self.assertEqual(result["sourceAdmission"], "NOT_ATTESTED_HERE")
            self.assertFalse(result["nextPhaseAuthority"])
        self.assertEqual((state / "marker").read_bytes(), b"preserve")
        self.assertEqual(list(state.iterdir()), [state / "marker"])

    def test_bad_source_role_or_state_refuses_before_loading_any_helper(self):
        bad = ({"expected_commit": "A" * 40}, {"expected_commit": "a" * 39}, {"expected_commit": True},
               {"role": "desktop"}, {"role": True}, {"state": "relative"}, {"state": str(ROOT)},
               {"state": str(ROOT / "state")}, {"state": str(ROOT.parent)},
               {"state": str(self.temp) + "/../state"}, {"state": str(self.temp) + "/bad\npath"},
               {"state": None})
        for change in bad:
            with self.subTest(change=change), patch.object(self.B, "_load_canonical_helper") as loaded, \
                    self.assertRaises(self.B.CanonicalError):
                self.descriptor(**change)
            loaded.assert_not_called()

    def test_no_arbitrary_executable_root_command_budget_or_binding_arguments(self):
        for key in ("executable", "root", "command", "timeout", "bindings", "recipient", "profile"):
            with self.subTest(key=key), patch.object(self.B, "_load_canonical_helper") as loaded, self.assertRaises(TypeError):
                self.descriptor(**{key: "not-authority"})
            loaded.assert_not_called()

    def test_interpreter_change_before_descriptor_return_refuses(self):
        original = self.B._interpreter()
        changed = (*original[:-1], original[-1] + 1)
        with patch.object(self.B, "_interpreter", side_effect=[original, changed]), \
                self.assertRaisesRegex(self.B.CanonicalError, "BOOTSTRAP_CANONICAL_BINDING_CHANGED"):
            self.descriptor()

    def test_canonical_source_change_before_descriptor_return_refuses(self):
        original = self.B._canonical_source
        for selected in NAMES:
            calls = []
            def source(name, maximum):
                raw = original(name, maximum)
                if name == selected:
                    calls.append(name)
                    if len(calls) > 1:
                        return raw + b"\n# synthetic changed bytes\n"
                return raw
            with self.subTest(supplier=selected), patch.object(self.B, "_canonical_source", source), \
                    self.assertRaisesRegex(self.B.CanonicalError, "BOOTSTRAP_CANONICAL_SOURCE_CHANGED"):
                self.descriptor()

    def test_helper_change_before_descriptor_return_refuses(self):
        original = self.B._canonical_source
        calls = []
        def source(name, maximum):
            raw = original(name, maximum)
            if name == HELPER:
                calls.append(name)
                if len(calls) > 1:
                    return raw + b"\n# synthetic changed helper\n"
            return raw
        with patch.object(self.B, "_canonical_source", source), \
                self.assertRaisesRegex(self.B.CanonicalError, "BOOTSTRAP_CANONICAL_BINDING_CHANGED"):
            self.descriptor()

    def test_isolation_flags_refuse_before_source_loading(self):
        for isolated, no_site, no_bytecode in ((0, 1, True), (1, 0, True), (1, 1, False)):
            with patch.object(sys, "flags", SimpleNamespace(isolated=isolated, no_site=no_site)), \
                    patch.object(sys, "dont_write_bytecode", no_bytecode), patch.object(self.B, "_load_canonical_helper") as loaded, \
                    self.assertRaisesRegex(self.B.CanonicalError, "BOOTSTRAP_CANONICAL_ISOLATION"):
                self.descriptor()
            loaded.assert_not_called()

    def test_shared_helper_is_separate_seed_provenance_not_a_third_child_input(self):
        self.assertIn("scripts/" + HELPER, self.C.seed.INPUTS)
        self.assertNotIn(HELPER, self.C.canonical_bindings())
        self.assertEqual(self.C.cache.cache_key("desktop", "linux-x64", "a" * 64, "b" * 64),
                         "p2pkit-dependency-files-v1-desktop-linux-x64-" + "a" * 64 + "-" + "b" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
