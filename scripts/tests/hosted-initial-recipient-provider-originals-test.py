#!/usr/bin/env python3
"""Focused raw8 receiving-owner/selected-copy models, NOT provider qualification.

Only the existing adapter fixture SETUP is reused, never an old test method or
the1,066-file reader. Native directories/reads and the pure provider decoder are
explicit memory models. The real A reader registry, alias checks, immutable
retention, reread argument bindings and PC selected-copy specifications run.
The B decoder's original-byte controls and actual native/provider/hosted timing
remain separate. No filesystem effect, process, network, key or build is used.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import ctypes  # Initialize stdlib before the fixture's native-loader prohibition.
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("initial_provider_originals_adapter_fixture",
    Path(__file__).with_name("hosted-initial-recipient-productive-adapter-test.py"))
AF = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = AF
spec.loader.exec_module(AF)
import hosted_cache_provider_readback as R
import hosted_initial_recipient_productive_custody as PC

A, D, O = AF.A, AF.D, AF.O
SLOTS = (("native", "supervisor-retirement.json", 2097152), ("stdout", "provider-stdout.log", 1048576),
    ("stderr", "provider-stderr.log", 1048576), ("packet", "worker-return.json", 6291456))
TEXT = {name: (ROOT / "scripts" / name).read_text(encoding="utf-8") for name in
    ("hosted_initial_recipient_productive_adapter.py", "hosted_initial_recipient_productive_custody.py")}


class RawModel:
    def __init__(self, model):
        self.model, self.stack = model, model.stack
        self.owner = model.owner()
        self.reader, _handoff = model.handoff(self.owner)
        self.path = Path("/model/prepare-save")
        self.root = self.path / "provider"
        self.native_path = self.path / "native-preparation"
        self.directory_ids = {self.path: (7, 40), self.root: (7, 41), self.native_path: (7, 42)}
        self.raws, self.bindings, self.reads, self.decodes = {}, {}, [], []
        for number, (slot, name, _maximum) in enumerate(SLOTS, 100):
            raw = b"SYNTHETIC_" + slot.encode("ascii") if slot != "packet" else b"x" * (D.LIMIT + 1)
            self.add(self.root, name, raw, number)
        self.preparation_raw = b"{}\n"
        self.add(self.path, "save-preparation.json", self.preparation_raw, 200)
        self.worker_request = b"SYNTHETIC_ORIGINAL_WORKER_ARGV_NOT_NATIVE"
        self.original = {
            "provider-prepared.json": O.encoded({"request": "SYNTHETIC_SUPERVISOR_REQUEST", "bindings": {"model": "1" * 64}}),
            "provider-readback.json": O.encoded({"acknowledgement": "SYNTHETIC_ACK", "python": "/model/python",
                "outputs": {}, "workerRequestSha256": O.digest(self.worker_request)})}
        for number, (name, raw) in enumerate(self.original.items(), 201):
            self.add(self.path, name, raw, number)
        self.native = {name: b"SYNTHETIC_USE_" + name.encode("ascii") for name in R.INITIAL_USE_FILES}
        for number, (name, raw) in enumerate(self.native.items(), 210):
            self.add(self.native_path, name, raw, number)
        self.context = {"phase": "save", "role": "linux-x64", "directory": str(self.root), "directoryIdentity": [7, 41]}
        self.references = tuple((slot, R.outer.FileReference(len(self.raws[self.root, name]),
            O.digest(self.raws[self.root, name]), tuple(self.bindings[self.root, name]["identity"]))) for slot, name, _ in SLOTS)
        self.returned_provider = SimpleNamespace(phase="save", outputs=())
        instance = self

        class Directory(AF.Resource):
            def __init__(self, path):
                super().__init__()
                self.path, self.identity = path, instance.directory_ids[path]

            def verify(self):
                return SimpleNamespace(identity=instance.directory_ids[self.path])

        self.stack.enter_context(patch.object(A.F, "private_root", side_effect=Directory))
        self.stack.enter_context(patch.object(A.staging, "_read", side_effect=self.read))
        self.stack.enter_context(patch.object(R.outer, "_context", side_effect=lambda raw:
            (self.context, O.digest(raw))))
        self.stack.enter_context(patch.object(R, "decode_originals", side_effect=self.decode))
        self.stack.enter_context(patch.object(R, "read_success", side_effect=AssertionError("OLD_PROVIDER_OWNER_FORBIDDEN")))
        self.stack.enter_context(patch.object(A, "_step_path", side_effect=lambda operation:
            self.path if operation == "prepare-save" else Path("/model/prepare-probe")))

    def add(self, path, name, raw, number):
        self.raws[path, name], self.bindings[path, name] = raw, AF.binding(number)

    def read(self, _owner, directory, name, *, maximum, expected=None, binding=None):
        key = directory.path, name
        if key not in self.raws:
            raise FileNotFoundError("SYNTHETIC_MISSING_FILE")
        raw, actual = bytes(bytearray(self.raws[key])), copy.deepcopy(self.bindings[key])
        self.reads.append((key, maximum, expected, binding))
        A.require(len(raw) <= maximum, "MODEL_FILE_CAP")
        A.require(expected is None or expected == raw, "MODEL_ORIGINAL_BYTES")
        A.require(binding is None or binding == actual, "MODEL_FULL_BINDING")
        return raw, actual

    def decode(self, files, request, acknowledgement, exit_code, *, python, bindings):
        self.decodes.append((files, request, acknowledgement, exit_code, python, bindings))
        ack = R.outer.Acknowledgement(O.digest(request), O.digest(self.worker_request), "success", 0, "success",
            1, (), self.references)
        return R.HistoricalProviderOriginals(self.returned_provider, ack, self.worker_request)

    def capture(self):
        return AF.guarded(A._provider_originals, self.reader, self.path, self.original, "save")

    def later(self):
        AF.guarded(self.owner.close)
        AF.guarded(A._known, self.owner)
        self.model.synthetic_phase("save-observation")  # Explicit memory window, not a new admission.
        owner = self.model.owner()
        reader, _handoff = self.model.handoff(owner)
        return reader

    def reread(self, reader, original):
        return AF.guarded(A._reread_action_files, reader, "save", self.preparation_raw,
            self.original, self.native, original)


@contextmanager
def fixture():
    model = AF.AdapterMemoryModels("runTest")
    model.setUp()  # Setup only; no existing method is selected.
    try:
        yield RawModel(model)
    finally:
        model.stack.close()


class ProviderOriginalModels(unittest.TestCase):
    def test_fixed_four_complete_bytes_caps_and_immutable_retention_use_current_reader(self):
        self.assertEqual(R.ORIGINAL_FILES, SLOTS)
        with fixture() as f:
            original = f.capture()
            self.assertEqual(original[:2], (str(f.root), (7, 41)))
            self.assertIs(type(original), tuple)
            self.assertIs(type(original[0]), str)
            self.assertIs(type(original[1]), tuple)
            self.assertTrue(all(type(part) is int for part in original[1]))
            self.assertIs(type(original[2]), tuple)
            self.assertEqual([(row[0], row[3]) for row in original[2]], [(name, maximum) for _, name, maximum in SLOTS])
            files = f.reader.files
            pin = A._PINS[id(f.reader)]
            self.assertIs(A._READERS[id(f.owner)], f.reader)
            self.assertIs(pin[0], f.reader)
            self.assertIs(dict(pin[2])["files"], files)
            pinned_files = dict(pin[3][0][0])
            self.assertEqual(tuple(pinned_files), tuple(files))
            for row in original[2]:
                self.assertIs(type(row), tuple)
                self.assertEqual(len(row), 4)
                name, raw, binding, maximum = row
                self.assertIs(type(name), str)
                self.assertIs(type(raw), bytes)
                self.assertIs(type(binding), bytes)
                self.assertIs(type(maximum), int)
                saved = files[f.root, name]
                self.assertIs(pinned_files[f.root, name], saved)
                self.assertIs(raw, saved[0])
                self.assertEqual(raw, f.raws[f.root, name])
                self.assertEqual(D.canonical(binding), f.bindings[f.root, name])
                self.assertEqual(D.canonical(binding), saved[1])
                self.assertEqual(f.reader.files[f.root, name][2], maximum)
                self.assertTrue(any(node[0] is saved[1] and node[1] is dict and node[2] == "mapping"
                    for node in pin[3][2]))
            self.assertGreater(len(original[2][-1][1]), D.LIMIT)
            self.assertFalse(f.owner.closed)
            self.assertEqual(f.decodes[0], ({slot: f.raws[f.root, name] for slot, name, _ in SLOTS},
                b"SYNTHETIC_SUPERVISOR_REQUEST", b"SYNTHETIC_ACK", 0, "/model/python", {"model": "1" * 64}))
            # Immutable tuples need no redundant nodes. Original mapping rows,
            # complete bytes and mutable binding dictionaries remain pinned.
            self.assertEqual(AF.guarded(A.N._history_graph, original), ())
            self.assertEqual(f.reader.graph, ())
            self.assertIs(AF.guarded(A._reader_passive, f.reader, allow_closed=False), f.reader)
            repeated = f.capture()
            self.assertEqual(repeated, original)
            self.assertIs(f.reader.files, files)
            self.assertEqual(len(f.reads), 8)
            self.assertEqual([(key, maximum) for key, maximum, _expected, _binding in f.reads],
                [((f.root, name), maximum) for _slot, name, maximum in SLOTS] * 2)
            for row, fresh, read in zip(original[2], repeated[2], f.reads[4:]):
                name, raw, _binding, maximum = row
                key, actual_maximum, expected, binding = read
                self.assertEqual((key, actual_maximum), ((f.root, name), maximum))
                self.assertIsNot(fresh[1], raw)
                self.assertIs(files[key], pinned_files[key])
                self.assertIs(files[key][0], raw)
                self.assertIs(expected, raw)
                self.assertIs(binding, files[key][1])
            self.assertIs(AF.guarded(A._reader_passive, f.reader, allow_closed=False), f.reader)

        for changed in ("equal-row", "stamp"):
            for _slot, name, _maximum in SLOTS:
                with self.subTest(changed=changed, name=name), fixture() as f:
                    f.capture()
                    self.assertEqual(f.reader.graph, ())
                    key = f.root, name
                    row = f.reader.files[key]
                    if changed == "equal-row":
                        f.reader.files[key] = (row[0], row[1], row[2])
                        self.assertEqual(f.reader.files[key], row)
                        self.assertIsNot(f.reader.files[key], row)
                        refusal = "ORIGINAL_READ_MAP_CHANGED"
                    else:
                        stamp = row[1]
                        stamp["stampSha256"] = "e" * 64
                        self.assertIs(f.reader.files[key], row)
                        self.assertIs(f.reader.files[key][1], stamp)
                        refusal = "RECIPIENT_HISTORY_CHANGED"
                    with self.assertRaisesRegex(AF.REFUSALS, refusal):
                        AF.guarded(A._reader_passive, f.reader, allow_closed=False)
                    self.assertEqual((len(f.reads), len(f.decodes)), (4, 1))

    def test_request_path_phase_role_and_native_directory_identity_are_not_templates(self):
        for field, wrong in (("directory", "/model/elsewhere"), ("phase", "lookup"),
                ("role", "windows-x64"), ("directoryIdentity", [7, 999])):
            with self.subTest(field=field), fixture() as f:
                f.context[field] = wrong
                with self.assertRaises(AF.REFUSALS): f.capture()
                self.assertEqual(f.decodes, [])

    def test_actual_ack_identity_length_and_hash_must_match_each_current_file(self):
        for field, wrong in (("identity", (7, 999)), ("size", 1), ("sha256", "0" * 64)):
            for index in range(4):
                with self.subTest(field=field, slot=index), fixture() as f:
                    rows = list(f.references)
                    slot, reference = rows[index]
                    rows[index] = slot, replace(reference, **{field: wrong})
                    f.references = tuple(rows)
                    with self.assertRaisesRegex(AF.REFUSALS, "ORIGINAL_PROVIDER_ACK_FILE_BINDING"):
                        f.capture()

    def test_original_packet_missing_or_over_fixed_six_mib_cannot_be_accepted(self):
        with fixture() as f:
            del f.raws[f.root, "worker-return.json"]
            with self.assertRaises(FileNotFoundError): f.capture()
            self.assertEqual(f.decodes, [])
        with fixture() as f:
            f.raws[f.root, "worker-return.json"] = b"x" * (6291456 + 1)
            with self.assertRaisesRegex(AF.REFUSALS, "MODEL_FILE_CAP"): f.capture()
            self.assertEqual(f.decodes, [])

    def test_raw_files_join_existing_file_directory_and_large_capture_alias_union(self):
        for kind in ("file", "directory", "large"):
            with self.subTest(kind=kind), fixture() as f:
                other = Path("/model/existing")
                f.directory_ids[other] = (7, 51)
                if kind == "file":
                    f.add(other, "prior.json", b"{}\n", 52)
                    AF.guarded(A._read_file, f.reader, other, "prior.json")
                    identity = [7, 52]
                elif kind == "directory":
                    identity = [7, 41]
                else:
                    raw = b"SYNTHETIC_LARGE_ORIGINAL"
                    AF.guarded(A._progress, f.reader, large=((other, "stdout.log", len(raw), O.digest(raw),
                        O.encoded(AF.binding(53))),))
                    identity = [7, 53]
                f.bindings[f.root, "supervisor-retirement.json"]["identity"] = identity
                with self.assertRaisesRegex(AF.REFUSALS, "ORIGINAL_READ_FILE_ALIAS"): f.capture()
                self.assertEqual(f.decodes, [])

    def test_decoder_data_must_join_actual_action_phase_outputs_and_request_hash(self):
        for field, wrong in (("phase", "lookup"), ("outputs", (("cache-hit", "true"),)), ("worker", b"other-request")):
            with self.subTest(field=field), fixture() as f:
                if field == "worker": f.worker_request = wrong
                else: setattr(f.returned_provider, field, wrong)
                with self.assertRaisesRegex(AF.REFUSALS, "ORIGINAL_PROVIDER_DATA_JOIN"): f.capture()

    def test_later_owner_rereads_all_old_files_plus_original_raw4_and_full_bindings(self):
        with fixture() as f:
            original = f.capture()
            later = f.later()
            f.reads.clear()
            f.reread(later, original)
            self.assertEqual(len(f.reads), 12)  # Preparation1 + Action2 + native-use5 + raw4.
            self.assertEqual(len(f.decodes), 1)  # No replay of even the historical decoder in a later reread.
            for name, raw, binding, maximum in original[2]:
                self.assertIn(((f.root, name), maximum, raw, D.canonical(binding)), f.reads)
            self.assertTrue(f.owner.closed)
            self.assertFalse(later.owner.closed)

    def test_later_equal_bytes_cannot_replace_full_file_binding_or_original_directory(self):
        for changed in ("binding", "directory", "bytes", "roster", "maximum"):
            with self.subTest(changed=changed), fixture() as f:
                original = f.capture()
                later = f.later()
                if changed == "binding": f.bindings[f.root, "worker-return.json"]["stampSha256"] = "e" * 64
                elif changed == "directory": f.directory_ids[f.root] = (7, 999)
                elif changed == "bytes": f.raws[f.root, "worker-return.json"] += b"changed"
                elif changed == "roster": original = (*original[:2], original[2][:-1])
                else:
                    rows = list(original[2]); rows[-1] = (*rows[-1][:3], 6291457)
                    original = (*original[:2], tuple(rows))
                with self.assertRaises(AF.REFUSALS): f.reread(later, original)

    def test_raw8_selected_copy_specs_retain_full_binding_maxima_and_never_embed_large_packets(self):
        roots = (Path("/model/save/provider"), Path("/model/probe/provider"))
        reader = SimpleNamespace(large=(), files={}, directories={})
        maxima, keys = {}, []
        for index, path in enumerate(roots):
            reader.directories[path] = (None, None, (7, 10 + index), None, None)
            for number, (_slot, name, maximum) in enumerate(SLOTS):
                key = path, name
                raw = b"x" * (D.LIMIT + 1) if name == "worker-return.json" else b"raw"
                reader.files[key] = (raw, AF.binding(100 + 10 * index + number), maximum)
                keys.append(key); maxima[key] = maximum
        with patch.object(PC, "_PINS", {}), patch.object(PC.B.processes, "host_role", return_value="linux-x64"):
            trees = AF.guarded(PC._selected_from_reader, reader, tuple(keys), maxima)
            self.assertEqual(len(trees), 2)
            self.assertEqual(sum(row.maximum for tree in trees for row in tree.files), 20 * 1024 * 1024)
            for tree in trees:
                self.assertFalse(tree.exact)
                self.assertEqual(tree.directories, (("", reader.directories[tree.path][2]),))
                for row in tree.files:
                    raw, binding, maximum = reader.files[tree.path, row.relative]
                    self.assertEqual((row.count, row.checksum, row.maximum), (len(raw), O.digest(raw), maximum))
                    self.assertEqual(D.canonical(row.binding_raw), binding)
                    self.assertIsNone(row.embedded)

    def test_all_four_callers_and_fixed114_plus8_keep_original_native_streaming_routes(self):
        adapter = TEXT["hosted_initial_recipient_productive_adapter.py"]
        custody = TEXT["hosted_initial_recipient_productive_custody.py"]
        for start, end in (("_after_save_history", "_step_window"), ("after_save", "after_probe"),
                ("after_probe", "_final_reader_owner"), ("_final_probe_history", "read_final_productive_inputs")):
            body = adapter.split("def " + start + "(", 1)[1].split("def " + end + "(", 1)[0]
            self.assertIn("provider_originals = ", body)
            self.assertIn("_action_originals(", body)
        self.assertEqual(adapter.count("provider_originals = _provider_originals(reader, path, original,"), 2)
        self.assertIn("action, native, provider_originals, prepared", adapter)
        self.assertIn("prepared, action, native, provider_originals", adapter)
        helper = adapter.split("def _provider_originals(", 1)[1].split("def _action_originals(", 1)[0]
        self.assertIn("readback.decode_originals(", helper)
        self.assertNotIn("read_success(", helper)
        self.assertNotIn("O.clocks.Reading(", helper)
        self.assertNotIn("D.canonical(raw_files", helper)
        parent = custody.split("def _parent_specs(", 1)[1].split("def _selected_reader(", 1)[0]
        self.assertLess(parent.index('"EXACT114_PRODUCTIVE_NATIVE_FILES"'), parent.index("for _slot, name, maximum in readback.ORIGINAL_FILES"))
        self.assertLess(parent.index("for _slot, name, maximum in readback.ORIGINAL_FILES"), parent.index('"EXACT122_PRODUCTIVE_NATIVE_FILES"'))
        self.assertIn("_selected_from_reader(reader, tuple(keys), maxima, extra)", parent)
        self.assertNotIn("_write_fixed(", parent)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
