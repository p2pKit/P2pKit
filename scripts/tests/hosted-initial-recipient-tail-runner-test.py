#!/usr/bin/env python3
"""New K DATA/refusal and AST topology controls, NOT native/runtime tests.

No B/Recipient/Admission/native or file owner is manufactured as valid. Positive
cases exercise only supplied cap/process/stamp DATA. Unregistered handles must
fail before I/O. AST assertions inspect this exact runner's call sites; they do
not prove any call executed, any native retirement, actual copy/freeze/export,
the enclosing Step, provider custody or scheduling qualification. No previous
fixture or accepted suite is imported or rerun.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes
import importlib.util
import json
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("TAIL_RUNNER_CONTROL_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
PATH = SCRIPTS / "run-hosted-initial-recipient-tail.py"
SOURCE = PATH.read_text(encoding="utf-8")
if len(SOURCE.encode("utf-8")) > 256 * 1024:
    raise AssertionError("TAIL_RUNNER_SOURCE_CONTROL_BOUND")
TREE = ast.parse(SOURCE, filename=str(PATH))
SPEC = importlib.util.spec_from_file_location("_tail_runner_controls", PATH)
K = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = K
SPEC.loader.exec_module(K)


NS = 1_000_000_000
DOMAINS = {"linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns"}
SEED_FIELDS = {"initialSealSha256", "initialSealEndNs", "initialSealClockRole", "initialSealClockDomain",
    "initialSealClockTicksPerSecond", "initialSealBootSha256"}
PRIVATE_INPUTS = {"before-index.json", "before-readback.json", "before-writer-close.json", "before-match.json",
    "original-match.json", "event.json", "candidate-policy.json", "recipient-public.asc", "p0-manifest.json",
    "seal-pending.json", "crypto-step-pending.json", "custody-return.json", "p0-context.json", "collect-close.json"}


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def seed(role="linux-x64"):
    return {"initialSealSha256": "1" * 64, "initialSealEndNs": str(500 * NS), "initialSealClockRole": role,
        "initialSealClockDomain": DOMAINS[role], "initialSealClockTicksPerSecond": str(7_000_003 if role == "windows-x64" else NS),
        "initialSealBootSha256": "2" * 64}


def process(value=None):
    if value is None:
        value = {"schema": 1, "waitExitCode": 0, "retired": True, "interruption": None}
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("ascii")


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous


def node(name, cls=None):
    parent = TREE if cls is None else next(item for item in TREE.body if isinstance(item, ast.ClassDef) and item.name == cls)
    return next(item for item in parent.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)


def calls(parent, name):
    return sorted((item for item in ast.walk(parent) if isinstance(item, ast.Call) and ast.unparse(item.func) == name),
        key=lambda item: (item.lineno, item.col_offset))


def text_of(parent):
    return ast.get_source_segment(SOURCE, parent)


class RunnerDataRefusalControls(unittest.TestCase):
    def reject(self, function, *args, **kwargs):
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(function, *args, **kwargs)

    def test_one_maintained_import_lineage_and_no_authority_was_acquired(self):
        self.assertIs(K.N, K.C.N)
        self.assertIs(K.native, K.C.native)
        self.assertIs(K.T.original, K.C.E)
        self.assertIs(K.H.B, K.C.B)
        self.assertEqual(K._ATTEMPTS, {})
        self.assertEqual(K.C._BEFORE_ATTEMPTS, {})
        self.assertEqual((len(K._PARENTS), len(K._CHILD_CLOCKS), len(K._NATIVE), len(K._CARRIERS), len(K._PENDING)),
            (0, 0, 0, 0, 0))

    def test_caps_are_original_tuple_data_for_each_role(self):
        full, clipped = (100 * NS, 310 * NS, 355 * NS), (400 * NS, 455 * NS, 500 * NS)
        for role in DOMAINS:
            self.assertIs(guarded(K._caps, seed(role), full), full)
            self.assertIs(guarded(K._caps, seed(role), clipped), clipped)

    def test_caps_have_no_clock_boot_file_or_native_side_effect(self):
        with ExitStack() as stack:
            for module, names in ((K.O.clocks, ("observe", "checked_now")),
                    (K.continuity, ("boot_digest",)), (K.time, ("time", "monotonic"))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_CLOCK_SUPPLIER")))
            self.assertEqual(guarded(K._caps, seed(), (100 * NS, 310 * NS, 355 * NS)),
                (100 * NS, 310 * NS, 355 * NS))

    def test_caps_reject_list_boolean_float_zero_overflow_and_wrong_arity(self):
        for bad in ([100 * NS, 310 * NS, 355 * NS], (True, 310 * NS, 355 * NS),
                (100.0 * NS, 310 * NS, 355 * NS), (0, 210 * NS, 255 * NS),
                (2 ** 64, 2 ** 64 + NS, 2 ** 64 + 2 * NS), (100 * NS, 310 * NS)):
            self.reject(K._caps, seed(), bad)

    def test_caps_cannot_refresh_child_first_or_borrow_retirement_time(self):
        for bad in ((100 * NS, 311 * NS, 356 * NS), (100 * NS, 310 * NS, 356 * NS),
                (400 * NS, 456 * NS, 501 * NS), (455 * NS, 455 * NS, 500 * NS),
                (100 * NS, 300 * NS, 345 * NS)):
            self.reject(K._caps, seed(), bad)

    def test_caps_reject_noncanonical_or_mismatched_seed(self):
        for field, bad in (("initialSealEndNs", 500 * NS), ("initialSealEndNs", "0500000000000"),
                ("initialSealClockDomain", DOMAINS["macos-x64"]), ("initialSealBootSha256", "G" * 64),
                ("extra", "1")):
            supplied = seed()
            supplied[field] = bad
            self.reject(K._caps, supplied, (100 * NS, 310 * NS, 355 * NS))

    def test_posix_process_spelling_is_actual_spaced_json_not_compact(self):
        value = {"schema": 1, "waitExitCode": 0, "retired": True, "interruption": None}
        self.assertEqual(guarded(K._process_record, process(value)), value)
        self.reject(K._process_record, wire(value))
        self.reject(K._process_record, process(value).rstrip())

    def test_process_record_requires_known_success_and_no_invented_argv(self):
        for field, bad in (("schema", True), ("waitExitCode", False), ("waitExitCode", 1), ("waitExitCode", None),
                ("retired", 1), ("retired", False), ("interruption", "operation-interrupted"), ("argv", [])):
            value = {"schema": 1, "waitExitCode": 0, "retired": True, "interruption": None}
            value[field] = bad
            self.reject(K._process_record, process(value))

    def test_process_duplicate_extra_trailing_or_oversized_bytes_refuse(self):
        raw = process()
        for bad in (b'{"schema":1,' + raw[1:], raw + b"\n", b"{}\n", b"x" * (K.native.LIMIT + 1)):
            self.reject(K._process_record, bad)

    def test_encryption_status_data_has_one_begin_one_end_and_no_error(self):
        raw = b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n[GNUPG:] END_ENCRYPTION\n"
        self.assertIsNone(guarded(K._encryption_status, raw))
        for bad in (b"", raw + b"[GNUPG:] END_ENCRYPTION\n", raw + b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n",
                raw + b"[GNUPG:] FAILURE encrypt 1\n", raw + b"[GNUPG:] ERROR encrypt 1\n",
                b"x" * (K.T.posix.MAX_DIAGNOSTIC_BYTES + 1)):
            self.reject(K._encryption_status, bad)

    def test_snapshot_stamp_comparison_is_supplied_posix_data_only(self):
        stamp = [1, 21, stat.S_IFREG | 0o600, 1000, 1, 7, 30, 40]
        row = ("member-00000.bin", False, (1, 21), 7, wire({"posixStamp": stamp}))
        expected = {"device": 1, "inode": 21, "size": 7, "mtime_ns": 30, "ctime_ns": 40}
        for role in ("linux-x64", "macos-x64", "macos-arm64"):
            self.assertEqual(guarded(K._snapshot_file_data, row, role), expected)

    def test_snapshot_stamp_rejects_wrong_identity_size_links_kind_and_writable_mode(self):
        for index, bad in ((0, 2), (1, 22), (2, stat.S_IFDIR | 0o700), (2, stat.S_IFREG | 0o622),
                (3, -1), (4, 2), (4, True), (5, 8), (6, True)):
            stamp = [1, 21, stat.S_IFREG | 0o600, 1000, 1, 7, 30, 40]
            stamp[index] = bad
            row = ("member-00000.bin", False, (1, 21), 7, wire({"posixStamp": stamp}))
            self.reject(K._snapshot_file_data, row, "linux-x64")

    def test_snapshot_row_name_kind_count_and_shape_are_exact(self):
        original = ("member-00000.bin", False, (1, 21), 7,
            wire({"posixStamp": [1, 21, stat.S_IFREG | 0o600, 1000, 1, 7, 30, 40]}))
        for index, bad in ((0, "../member-00000.bin"), (1, 0), (2, [1, 21]), (3, True)):
            row = list(original)
            row[index] = bad
            self.reject(K._snapshot_file_data, tuple(row), "linux-x64")
        self.reject(K._snapshot_file_data, list(original), "linux-x64")

    def test_windows_snapshot_stamp_uses_full_private_metadata(self):
        value = {"identity": [1, "1" * 32], "is_directory": False, "size": 7, "links": 1,
            "attributes": 0x80, "creation_100ns": 10, "modified_100ns": 20, "change_100ns": 30,
            "owner_sid": "S-1-5-21-1", "protected_dacl": True}
        row = ("member-00000.bin", False, (1, "1" * 32), 7, wire(value))
        self.assertEqual(guarded(K._snapshot_file_data, row, "windows-x64"), value)
        value["protected_dacl"] = False
        self.reject(K._snapshot_file_data, (*row[:4], wire(value)), "windows-x64")

    def test_unregistered_parent_clock_capture_terminal_and_output_handles_refuse(self):
        for kind, method in ((K._Parent, "current"), (K._ChildClock, "current"), (K._Capture, "current"),
                (K._TerminalRead, "current"), (K._OutputFence, "append")):
            # An allocated Python shape is deliberately NOT a valid capability.
            value = object.__new__(kind)
            self.reject(getattr(value, method))

    def test_unregistered_file_native_carrier_freeze_and_pending_returns_refuse(self):
        self.reject(K._file_current, object.__new__(K._File))
        self.reject(K._checked_native, object(), object.__new__(K._NativeReturn))
        self.reject(K._checked_carrier, object.__new__(K._Carrier))
        self.reject(K._freeze_current, object.__new__(K._Freeze))
        self.reject(K._checked_pending, object.__new__(K._Pending))

    def test_nonowners_refuse_before_file_or_budget_callbacks(self):
        self.reject(K._open_file, object(), object(), "manifest.json", 65536)
        self.reject(K._closed_files, object())
        self.reject(K._budget, object())

    def test_seven_outputs_reject_bad_fields_or_seed_before_guard_or_io(self):
        def no_guard():
            raise AssertionError("OUTPUT_GUARD_SHOULD_NOT_HAVE_RUN")
        for change in ("missing", "extra", "hash", "clock", "integer", "old-shape"):
            value = {"initialBeforeSha256": "3" * 64, **seed()}
            if change == "missing":
                del value["initialSealBootSha256"]
            elif change == "extra":
                value["initialTailSha256"] = "4" * 64
            elif change == "hash":
                value["initialBeforeSha256"] = "G" * 64
            elif change == "clock":
                value["initialSealClockTicksPerSecond"] = "01"
            elif change == "integer":
                value["initialSealEndNs"] = 500 * NS
            else:
                value = seed()
            self.reject(K._append_seven, value, no_guard)

    def test_fixed_inputs_private_closes_and_output_names(self):
        self.assertEqual(set(K.INPUT_LIMITS), PRIVATE_INPUTS)
        expected = PRIVATE_INPUTS | {"context.json", "tail-child-result.json", "control-home", "temporary", "service"}
        self.assertEqual(K.PRIVATE_INPUT_NAMES, tuple(sorted(expected)))
        self.assertEqual(K.PRIVATE_CLOSED_NAMES, tuple(sorted(expected | {"carrier-close.json", "before-upload-pending.json"})))
        self.assertEqual({name for name, _environment, _flag in K.B.SEED_FIELDS}, SEED_FIELDS)
        self.assertEqual((K.H.OUTPUT, K.H.HASH_ENV, K.H.OUTCOME_ENV),
            ("initialBeforeSha256", "P2PKIT_INITIAL_BEFORE_SHA256", "P2PKIT_INITIAL_BEFORE_OUTCOME"))

    def test_new_custody_rosters_are_finite_and_require_output_before_upload(self):
        before = guarded(K._custody_names, tail_output=False)
        exported = guarded(K._custody_names, tail_output=True)
        carrier = guarded(K._custody_names, tail_output=True, upload=True)
        self.assertEqual(set(before) - set(K.C._before_roster(created=True)),
            {"tail-returned", "tail-public-crypto", "tail-copied-evidence"})
        self.assertEqual(set(exported) - set(before), {"tail-export-output"})
        self.assertEqual(set(carrier) - set(exported), {"upload-output"})
        self.reject(K._custody_names, tail_output=False, upload=True)
        self.reject(K._custody_names, tail_output=1)


class RunnerSourceTopologyControls(unittest.TestCase):
    def line(self, parent, name):
        found = calls(parent, name)
        self.assertTrue(found, name)
        return found[0].lineno

    def test_ast_exact_single_c_loader_and_shared_lineage(self):
        loaders = calls(TREE, "importlib.util.spec_from_file_location")
        self.assertEqual(len(loaders), 1)
        self.assertIn('"run-hosted-initial-recipient-custody.py"', text_of(loaders[0]))
        self.assertEqual(len(calls(TREE, "_spec.loader.exec_module")), 1)
        self.assertEqual(len(calls(TREE, "C.before_authority")), 1)

    def test_ast_parent_order_is_real_b_native_carrier_pending_complete_outputs(self):
        parent = node("before_and_tail")
        order = [self.line(parent, name) for name in ("C.before_authority", "_Parent", "_native_tail", "_copy_carrier",
            "_retain_pending", "original.complete", "_checked_pending", "_OutputFence(pending).append")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(calls(parent, "original.begin")), 1)

    def test_ast_no_reconstructed_b_recipient_or_admission_and_no_phase_widening(self):
        forbidden = {"C._BeforeAuthority", "C._BeforeClock", "C._TailClock", "T.posix.Recipient", "T.windows.Recipient",
            "C.O.Admission", "owner.enter_custody_phase", "owner.enter_crypto_phase", "owner.enter_before_phase",
            "clock.attach_file_owner", "object.__new__", "cache.export_snapshot", "cache.save_set"}
        self.assertFalse(forbidden.intersection(ast.unparse(item.func) for item in ast.walk(TREE) if isinstance(item, ast.Call)))
        for item in ast.walk(TREE):
            if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                for target in targets:
                    self.assertFalse(isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and
                        target.value.id in {"C", "N", "native", "B", "continuity"})

    def test_ast_parent_checks_registry_and_failures_poison_original_b_and_k(self):
        current, failed = text_of(node("current", "_Parent")), text_of(node("fail", "_Parent"))
        self.assertIn("C._BEFORE_AUTHORITIES.get(id(before)) is original", current)
        self.assertIn("self._binding is saved[1]", current)
        self.assertIn("saved[1][1][18][0].fail(error)", failed)
        self.assertIn("saved[1][11].fail(original)", failed)
        self.assertEqual(len(calls(node("currency", "_Parent"), "C._before_currency")), 1)

    def test_ast_child_first_local_raw_boot_precedes_any_metadata_owner_or_reader(self):
        child = node("tail_child")
        order = [self.line(child, name) for name in ("time.monotonic", "O.clocks.observe", "continuity.boot_digest",
            "_ChildClock", "C._PrimaryOwner", "C._private", "_small")]
        self.assertEqual(order, sorted(order))
        self.assertLess(self.line(child, "owner.finish"), self.line(child, "clock.bind"))
        self.assertLess(self.line(child, "clock.bind"), self.line(child, "_child_work"))

    def test_ast_child_has_two_sequential_real_owners_not_a_restored_clock(self):
        attach = text_of(node("attach", "_ChildClock"))
        self.assertIn("len(anchor.owners) < 2", attach)
        self.assertIn("anchor.owners[0][0].finished", attach)
        self.assertIn("owner.owner.first is anchor.binding[0]", attach)
        self.assertEqual(len(calls(node("_child_work"), "C._PrimaryOwner")), 1)
        self.assertEqual(len(calls(node("_child_work"), "clock.attach")), 1)

    def test_ast_native_parent_uses_actual_owner_spawn_drain_known_close(self):
        parent = node("_native_tail")
        order = [self.line(parent, name) for name in ("C._CustodyOwner", "native.processes.make_scope", "scope.spawn",
            "scope.drain", "owner.freeze", "owner.close", "owner.known", "_NativeReturn")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(calls(parent, "scope.spawn")), 1)
        self.assertIn("owner.phase_originals = result", text_of(parent))
        self.assertIn('parent.now(final=True, limit=caps[2])', text_of(parent))

    def test_ast_no_native_context_or_owner_label_allowlist_changes(self):
        source = text_of(node("_native_tail"))
        self.assertNotIn("enter_", source)
        self.assertIn("clock.deadline(900, final=True, limit=caps[2])", source)
        self.assertIn('native._initializer_names(owner, root)', source)
        self.assertIn('C._before_roster(created=True)', source)

    def test_ast_new_validation_precedes_complete_capture_freeze_and_export(self):
        child = node("_child_work")
        validation_lines = [self.line(child, name) for name in ("T.windows.validate_recipient", "T.posix.validate_recipient")]
        capture_line = self.line(child, "_Capture")
        self.assertLess(max(validation_lines), capture_line)
        order = [self.line(child, name) for name in ("_validation_sources", "_existing_declarations", "_p0_diagnostics",
            "_freeze_tail", "T.export_encrypted", "_terminal_check", "owner.finish")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(calls(TREE, "T.export_encrypted")), 1)

    def test_ast_exact_old_and_new_original_groups_not_whole_crypto_snapshot(self):
        self.assertEqual(K.T.GROUPS, ("RETURNED", "CRYPTO_SERVICE", "POST_EXPORT_AUTHORITY", "SEAL_AUTHORITY", "SEAL",
            "P0_EXPORT_DIAGNOSTICS", "P0_VALIDATION_MAP_REFERENCE", "BEFORE_AUTHORITY", "NEW_RECIPIENT_VALIDATION"))
        declared = text_of(node("_existing_declarations"))
        self.assertIn("C._historical_tail_authority_indexes", declared)
        self.assertIn("B.member_grammar(*query_ids)", declared)
        snap = text_of(node("_destination_snapshot"))
        self.assertIn("destination.snapshot", snap)
        self.assertIn("not owner.snapshots", snap)
        self.assertNotIn("work.snapshot", SOURCE)

    def test_ast_map_reservation_precedes_copy_and_map_is_not_recursive(self):
        freeze = node("_freeze_tail")
        source = text_of(freeze)
        self.assertIn("anchor.charged_bytes + copy_bytes + T.MAP_LIMIT <= T.posix.MAX_BYTES", source)
        self.assertLess(source.index("PRECOPY_SHARED_AND_MAP_RESERVATION"), source.index("destination.create_file"))
        self.assertIn('"mapSelfReference": "EXCLUDED_FROM_OWN_HASH_AND_TOTALS"', source)
        self.assertLess(self.line(freeze, "_write_bytes"), self.line(freeze, "_destination_snapshot"))
        self.assertIn("C.canonical(reader.raw) == observed == snapshotted[name]", source)

    def test_ast_reader_owns_directory_and_uses_real_eof_and_bounded_chunks(self):
        opened, streamed = text_of(node("_open_file")), text_of(node("_stream"))
        self.assertIn('label == "directory" and resource is directory', opened)
        self.assertIn("owner.owner.fence.deadline(900)", opened)
        self.assertIn("C.COPY_CHUNK", streamed)
        self.assertIn("value.reader.read(1)", streamed)
        self.assertIn("_file_current(value)", streamed)
        self.assertIn("owner.close_one(resource)", streamed)
        self.assertEqual(K.C.COPY_CHUNK, 64 * 1024)

    def test_ast_exclusive_writer_close_precedes_independent_readback(self):
        function = node("_write_bytes")
        order = [self.line(function, name) for name in ("directory.create_file", "writer.sync", "writer.verify",
            "owner.close_one", "_open_file", "_stream", "R.write_close_metadata")]
        self.assertEqual(order, sorted(order))

    def test_ast_carrier_is_after_native_close_and_pending_after_actual_carrier_close(self):
        copied = node("_copy_carrier")
        self.assertLess(self.line(copied, "_checked_native"), self.line(copied, "C._PrimaryOwner"))
        self.assertLess(self.line(copied, "H.carrier_bytes"), self.line(copied, "_open_file"))
        self.assertLess(self.line(copied, "owner.finish"), self.line(copied, "R.encode_close"))
        pending = node("_retain_pending")
        writes = calls(pending, "_write_bytes")
        self.assertEqual(len(writes), 2)
        self.assertEqual(ast.unparse(writes[0].args[2]), "H.PRIVATE_CARRIER_CLOSE")
        self.assertEqual(ast.unparse(writes[1].args[2]), "H.FILE")
        self.assertLess(writes[1].lineno, self.line(pending, "owner.finish"))

    def test_ast_pending_writer_never_attests_own_original_step(self):
        self.assertEqual(guarded(K._nonacceptance), {"originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED",
            "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
            "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})
        self.assertIn('"writerReturn": "PENDING_OWNER_CLOSE"', text_of(node("_retain_pending")))
        self.assertIn('"writerReturn": "PENDING_SEPARATE_RECORD_WRITER_CLOSE"', text_of(node("_copy_carrier")))
        self.assertIn('"NOT_USED_AS_QUALIFICATION_ORIGINALS"', text_of(node("_child_data")))

    def test_ast_seven_output_writer_is_distinct_with_sync_readback_close(self):
        self.assertEqual(calls(TREE, "continuity.append_outputs"), [])
        appended = node("_append_seven")
        order = [self.line(appended, name) for name in ("os.open", "os.write", "os.fsync", "os.read", "os.close")]
        self.assertEqual(order, sorted(order))
        self.assertIn('parent / "_runner_file_commands"', text_of(appended))
        self.assertIn("before.st_size == 0", text_of(appended))
        self.assertIn("continuity.QUARANTINE.append(descriptor)", text_of(appended))

    def test_ast_output_fence_requires_exactly_two_late_checks_and_poison_on_failure(self):
        source = text_of(node("now", "_OutputFence"))
        # Retrieve the genuine registry lineage before checking the mutable
        # visible binding, so even a late replacement reaches original B/K.
        self.assertNotIn("self._binding", text_of(node("_anchor", "_OutputFence")))
        begun = text_of(node("_begin", "_OutputFence"))
        self.assertLess(begun.index("try:"), begun.index("self._binding is saved[1]"))
        self.assertIn("raise self._fail(saved, error)", begun)
        self.assertIn('0 <= saved[2]["checks"] < 2', source)
        self.assertIn('saved[2]["checks"] += 1', source)
        self.assertIn("final is True", source)
        self.assertIn("raise self._fail(saved, error)", source)
        self.assertEqual(len(calls(node("main"), "native.guarded")), 2)

    def test_ast_cli_is_fixed_isolated_and_has_no_activation_or_productive_entry(self):
        main = text_of(node("main"))
        self.assertIn('"before-and-tail"', main)
        self.assertIn('"_tail-child"', main)
        self.assertIn("allow_abbrev=False", main)
        self.assertIn("sys.flags.isolated == 1 and sys.flags.no_site == 1", main)
        self.assertIn("sys.argv[1:] == _command(args.context_sha256, seed, caps, minimum)[5:]", main)
        self.assertNotIn("workflow_dispatch", main)
        self.assertNotIn("prepare-save", main)


if __name__ == "__main__":
    unittest.main()
