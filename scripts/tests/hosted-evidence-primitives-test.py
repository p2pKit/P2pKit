#!/usr/bin/env python3
"""Shared-primitives source and finite memory controls, NOT custody qualification.

Only maintained public source is read. Path/owner/clock inputs below are explicit
in-memory models; no native owner, provider, key, archive, subprocess or network
is used. Exact body hashes bind the pre-extraction originals, not generated
expectations from the candidate. A moved-body pass is not a hosted result.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes  # Initialize stdlib before refusing any subsequent native load.
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


NO_IO = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or NO_IO and event in (
            "open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        raise AssertionError("EVIDENCE_PRIMITIVES_MODEL_FORBIDDEN_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SOURCE = (ROOT / "scripts/hosted_evidence_primitives.py").read_text(encoding="utf-8")
import hosted_evidence_primitives as P
import hosted_evidence as H
import hosted_windows_evidence as W
import hosted_test_query as Q
import hosted_cache_provider_lifecycle as L


# Original spans in effective input tree9eb42ccfe583804653af1d6f7afaa2ba6e35ef77:
# H's class/five functions and W's diagnostic; only trailing whitespace/LF is
# normalized. Never refresh these expected values from a modified leaf.
ORIGINAL_BODIES = {
    "EvidenceError": "1f32c86ce0b53e069933465b941e13d7e4495afe4af39c8eed3e37ee4f666531",
    "_fail": "e43fb5c3ce88df2005779a5535e806da852a818936bc71e26aec834e52d3eb90",
    "_deadline": "09b66468d814c007d422fa37359fa02ff089afe4dbe1df574b338c1829bb6de6",
    "_path": "a79b895db7c1b0b953ffb7cb6c490b61d641a7749e36de57251c707797ebb04e",
    "_private_directory": "2c7e753936d76dd38624f860c7c705392bc054ff85f84ada54e65ae5bf8cbe1d",
    "_identity": "2160708ac71e66cb716629edffb2b47499492981c0efff7e8fee46406024bcfd",
    "_exception_detail": "29f6722cf78fe2a8cc35bbf36334716d62cb808e3dcac2c43d8cc19e019d2f99",
}


class SharedSourceControls(unittest.TestCase):
    def test_original_class_and_function_bodies_are_moved_without_semantic_changes(self):
        nodes = [node for node in ast.parse(SOURCE).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
        self.assertEqual([node.name for node in nodes], list(ORIGINAL_BODIES))
        lines = SOURCE.splitlines()
        for node in nodes:
            with self.subTest(name=node.name):
                raw = ("\n".join(lines[node.lineno - 1:node.end_lineno]).rstrip() + "\n").encode("utf-8")
                self.assertEqual(hashlib.sha256(raw).hexdigest(), ORIGINAL_BODIES[node.name])

    def test_same_objects_reach_portable_windows_query_and_provider_callers(self):
        self.assertIs(H.primitives, P)
        self.assertIs(W.primitives, P)
        self.assertIs(Q.posix_files, P)
        self.assertIs(L.diagnostics, P)
        for name in ("EvidenceError", "_fail", "_deadline", "_path", "_private_directory", "_identity"):
            with self.subTest(name=name):
                self.assertIs(getattr(H, name), getattr(P, name))
                self.assertIs(getattr(W.portable, name), getattr(P, name))
                self.assertIs(getattr(Q.posix_files, name), getattr(P, name))
        self.assertIs(W._exception_detail, P._exception_detail)
        self.assertIs(W.WindowsEvidenceError.__bases__[0], P.EvidenceError)
        for name in tuple(ORIGINAL_BODIES)[1:]:
            self.assertIs(getattr(P, name).__globals__, vars(P))
        self.assertFalse(hasattr(P, "_QUARANTINE"))
        self.assertFalse(hasattr(P, "_PRODUCTIVE_QUARANTINE"))

    def test_leaf_is_stdlib_definition_only_and_import_has_no_effects_or_path_widening(self):
        tree = ast.parse(SOURCE)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imports.append(node.module)
        self.assertEqual(sorted(imports), ["__future__", "os", "pathlib", "stat", "time"])
        for node in tree.body:
            if isinstance(node, ast.Expr):
                self.assertIsInstance(node.value, ast.Constant)
                self.assertIs(type(node.value.value), str)
            else:
                self.assertIsInstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef))
        module = ModuleType("MODEL_LEAF_IMPORT_ONLY")
        module.__file__ = str(ROOT / "scripts/hosted_evidence_primitives.py")
        code = compile(SOURCE, module.__file__, "exec", dont_inherit=True)
        original_path, path_values, modules = sys.path, tuple(sys.path), dict(sys.modules)
        global NO_IO
        previous, NO_IO = NO_IO, True
        try:
            with ExitStack() as stack:
                for owner, name in ((time, "monotonic"), (time, "time"), (time, "sleep"),
                        (os, "getuid"), (os, "getpid"), (Path, "lstat")):
                    stack.enter_context(patch.object(owner, name,
                        side_effect=AssertionError("MODEL_IMPORT_SAMPLED_SUPPLIER"), create=True))
                exec(code, vars(module))
        finally:
            NO_IO = previous
        self.assertIs(sys.path, original_path)
        self.assertEqual(tuple(sys.path), path_values)
        self.assertEqual(set(sys.modules), set(modules))
        self.assertTrue(all(sys.modules[name] is value for name, value in modules.items()))


class PrimitiveMemoryControls(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.infos = {"/model": self.info(0o700, 7), "/model/private": self.info(0o700, 8)}
        self.children, self.seen, self.samples = {}, [], []
        self.local = 99.0
        case = self

        class ModelPath(PurePosixPath):
            def lstat(self):
                case.seen.append(str(self))
                if str(self) not in case.infos:
                    raise FileNotFoundError("MODEL_MISSING_PATH")
                return case.infos[str(self)]

            def iterdir(self):
                return iter(case.children.get(str(self), ()))

        self.path = ModelPath
        self.stack.enter_context(patch.object(P, "Path", ModelPath))
        self.stack.enter_context(patch.object(P, "os", SimpleNamespace(getuid=lambda: 1000)))
        self.stack.enter_context(patch.object(P, "time", SimpleNamespace(monotonic=self.now)))

    @staticmethod
    def info(mode, inode, *, uid=1000, kind=stat.S_IFDIR):
        return SimpleNamespace(st_mode=kind | mode, st_uid=uid, st_dev=7, st_ino=inode)

    def now(self):
        self.samples.append(self.local)
        return self.local

    def test_deadline_uses_original_clock_and_exact_closed_boundary(self):
        self.assertIsNone(P._deadline(100.0))
        self.local = 100.0
        with self.assertRaisesRegex(P.EvidenceError, "^Encrypted evidence operation exceeded its deadline$"):
            P._deadline(100.0)
        self.local = 100.1
        with self.assertRaises(P.EvidenceError):
            P._deadline(100.0)
        self.assertEqual(self.samples, [99.0, 100.0, 100.1])

    def test_normalized_absolute_paths_allow_only_missing_final_component(self):
        self.assertEqual(P._path("/model/private/new"), self.path("/model/private/new"))
        self.assertEqual(self.seen, ["/model", "/model/private", "/model/private/new"])
        for path, reason in (("relative", "absolute and normalized"),
                ("/model/../private", "absolute and normalized"),
                ("/absent/child", "parent is absent")):
            with self.subTest(path=path), self.assertRaisesRegex(P.EvidenceError, reason):
                P._path(path)

    def test_path_refuses_symbolic_link_at_final_or_ancestor_component(self):
        self.infos["/model/link"] = self.info(0o777, 9, kind=stat.S_IFLNK)
        for path in ("/model/link", "/model/link/child"):
            with self.subTest(path=path), self.assertRaisesRegex(P.EvidenceError, "symbolic links"):
                P._path(path)

    def test_private_directory_checks_type_uid_mode_and_required_emptiness(self):
        self.assertEqual(P._private_directory("/model/private", empty=True), self.path("/model/private"))
        for info in (self.info(0o700, 8, kind=stat.S_IFREG), self.info(0o750, 8), self.info(0o700, 8, uid=1001)):
            self.infos["/model/private"] = info
            with self.assertRaisesRegex(P.EvidenceError, "exclusively owned mode-0700"):
                P._private_directory("/model/private")
        self.infos["/model/private"] = self.info(0o700, 8)
        self.children["/model/private"] = (self.path("/model/private/occupied"),)
        self.assertEqual(P._private_directory("/model/private"), self.path("/model/private"))
        with self.assertRaisesRegex(P.EvidenceError, "new and empty"):
            P._private_directory("/model/private", empty=True)

    def test_identity_is_original_device_inode_and_public_fail_keeps_exact_message(self):
        self.assertEqual(P._identity(self.path("/model/private")), (7, 8))
        self.assertEqual(self.seen, ["/model/private"])
        with self.assertRaises(P.EvidenceError) as caught:
            P._fail("MODEL_PUBLIC_REASON")
        self.assertEqual(str(caught.exception), "MODEL_PUBLIC_REASON")
        self.assertIs(P.EvidenceError.__bases__[0], RuntimeError)


class FiniteDiagnosticControls(unittest.TestCase):
    def unknown(self, error):
        result = P._exception_detail(error)
        self.assertTrue(result["incomplete"])
        self.assertTrue(result["retirementUnknown"])
        self.assertLessEqual(len(result["nodes"]), 64)
        return result

    @staticmethod
    def carrier(resources=(), omitted=0):
        return {"status": "UNKNOWN", "resources": list(resources), "omitted": omitted}

    @staticmethod
    def resource():
        return {"phase": "MODEL", "resource": "memory", "status": "UNKNOWN", "error": "model close"}

    def test_clean_message_note_and_explicit_retirement_carrier_have_distinct_knownness(self):
        error = RuntimeError("MODEL original")
        result = P._exception_detail(error)
        self.assertEqual(result, {"nodes": [{"edge": "original", "type": "RuntimeError",
            "message": "MODEL original", "notes": []}], "incomplete": False, "retirementUnknown": False})
        error.__notes__ = ["MODEL retirement UNKNOWN"]
        noted = P._exception_detail(error)
        self.assertFalse(noted["incomplete"])
        self.assertTrue(noted["retirementUnknown"])
        error.__notes__ = []
        error._p2pkit_retirement = self.carrier([self.resource()])
        carried = P._exception_detail(error)
        self.assertFalse(carried["incomplete"])
        self.assertTrue(carried["retirementUnknown"])
        self.assertEqual(carried["nodes"][0]["retirement"], [self.resource()])

    def test_cause_context_group_and_cycles_preserve_links_without_unbounded_recursion(self):
        first, second, grouped = RuntimeError("first"), RuntimeError("second"), RuntimeError("grouped")
        first.__cause__, second.__context__ = second, first
        first.exceptions = (grouped,)
        grouped.__notes__ = ["MODEL retirement UNKNOWN"]
        result = P._exception_detail(first)
        self.assertFalse(result["incomplete"])
        self.assertTrue(result["retirementUnknown"])
        self.assertEqual(result["nodes"][-1], {"edge": "1.__context__", "reference": 0})
        self.assertEqual([row["edge"] for row in result["nodes"]],
            ["original", "0.__cause__", "0.group[0]", "1.__context__"])

    def test_message_type_and_each_graph_accessor_failure_remain_incomplete(self):
        class BadMessage(RuntimeError):
            def __str__(self):
                raise KeyboardInterrupt("MODEL_MESSAGE_FAILURE")

        class BadType(type):
            def __getattribute__(self, name):
                if name == "__name__":
                    raise RuntimeError("MODEL_TYPE_FAILURE")
                return super().__getattribute__(name)

        class BadTypeError(RuntimeError, metaclass=BadType):
            pass

        self.assertEqual(self.unknown(BadMessage())["nodes"][0]["message"], "<exception message unavailable>")
        self.assertEqual(self.unknown(BadTypeError())["nodes"][0]["type"], "<exception type unavailable>")
        for attribute in ("__notes__", "_p2pkit_retirement", "__cause__", "__context__", "exceptions"):
            class BadAccessor(RuntimeError):
                def __getattribute__(self, name):
                    if name == attribute:
                        raise RuntimeError("MODEL_ACCESSOR_FAILURE")
                    return super().__getattribute__(name)
            with self.subTest(attribute=attribute):
                self.unknown(BadAccessor("original"))

    def test_nonexception_or_malformed_group_and_notes_cannot_imply_known_retirement(self):
        self.unknown(object())
        for attribute, value in (("exceptions", "not-a-list"), ("exceptions", (object(),)),
                ("__notes__", "not-a-list"), ("__notes__", [object()])):
            error = RuntimeError("original")
            setattr(error, attribute, value)
            with self.subTest(attribute=attribute, kind=type(value).__name__):
                self.unknown(error)

    def test_carrier_shape_status_resource_and_omission_validation_fail_closed(self):
        bad = ([], {"status": "KNOWN", "resources": [], "omitted": 0},
            {1: "UNKNOWN", "resources": [], "omitted": 0},
            {**self.carrier(), "extra": 1}, {"status": "UNKNOWN", "resources": (), "omitted": 0},
            self.carrier(omitted=True), self.carrier(omitted=-1), self.carrier(omitted=1),
            self.carrier([{}]), self.carrier([{**self.resource(), "error": object()}]))
        for ordinal, carrier in enumerate(bad):
            error = RuntimeError("original")
            error._p2pkit_retirement = carrier
            with self.subTest(ordinal=ordinal):
                self.unknown(error)

    def test_individual_text_bounds_keep_unknown_when_message_or_type_is_truncated(self):
        for size in (2048, 2049):
            error = RuntimeError("m" * size)
            result = P._exception_detail(error)
            self.assertEqual(len(result["nodes"][0]["message"]), 2048)
            self.assertEqual((result["incomplete"], result["retirementUnknown"]), (size > 2048,) * 2)
        for size in (128, 129):
            error = type("T" * size, (RuntimeError,), {})("model")
            result = P._exception_detail(error)
            self.assertEqual(len(result["nodes"][0]["type"]), 128)
            self.assertEqual((result["incomplete"], result["retirementUnknown"]), (size > 128,) * 2)

    def test_note_count_and_note_text_bounds_have_no_silent_omission(self):
        for count, size in ((16, 512), (17, 512), (1, 513)):
            error = RuntimeError("original")
            error.__notes__ = ["n" * size] * count
            result = P._exception_detail(error)
            self.assertEqual(len(result["nodes"][0]["notes"]), min(count, 16))
            self.assertTrue(all(len(note) == min(size, 512) for note in result["nodes"][0]["notes"]))
            self.assertEqual((result["incomplete"], result["retirementUnknown"]), (count > 16 or size > 512,) * 2)

    def test_carrier_resource_count_and_field_text_bounds_preserve_unknown(self):
        for count, size in ((32, 512), (33, 512), (1, 513)):
            # Only one field is long, so this case does not also exhaust32KiB.
            error = RuntimeError("original")
            resources = [{**self.resource(), "error": "r" * size} for _ in range(count)]
            error._p2pkit_retirement = self.carrier(resources)
            result = P._exception_detail(error)
            self.assertTrue(result["retirementUnknown"])
            self.assertEqual(result["incomplete"], count > 32 or size > 512)
            self.assertEqual(len(result["nodes"][0]["retirement"]), min(count, 32))
            self.assertTrue(all(len(row["error"]) == min(size, 512) for row in result["nodes"][0]["retirement"]))

    def test_whole_graph_text_budget_is_32768_characters_not_per_node(self):
        error = RuntimeError("m" * 2048)
        error.exceptions = tuple(RuntimeError("m" * 2048) for _ in range(20))
        result = self.unknown(error)
        total = sum(len(row.get("type", "")) + len(row.get("message", "")) +
            sum(map(len, row.get("notes", ()))) for row in result["nodes"])
        self.assertEqual(total, 32 * 1024)
        self.assertEqual(len(result["nodes"]), 21)

    def test_node_pending_and_group_bounds_are_finite_and_incomplete(self):
        first = current = RuntimeError("chain")
        for _ in range(64):
            current.__cause__ = RuntimeError("next")
            current = current.__cause__
        self.assertEqual(len(self.unknown(first)["nodes"]), 64)
        grouped = RuntimeError("group")
        grouped.exceptions = tuple(RuntimeError("child") for _ in range(65))
        self.assertEqual(len(self.unknown(grouped)["nodes"]), 64)
        pending = RuntimeError("pending")
        pending.__cause__, pending.__context__ = RuntimeError("cause"), RuntimeError("context")
        pending.exceptions = tuple(RuntimeError("child") for _ in range(64))
        pending.__cause__.exceptions = tuple(RuntimeError("next") for _ in range(64))
        # Processing cause produces129 pending entries: the preserved128 queue
        # bound truncates before the separate64-node ceiling is reached.
        self.assertEqual(len(self.unknown(pending)["nodes"]), 64)


if __name__ == "__main__":
    unittest.main()
