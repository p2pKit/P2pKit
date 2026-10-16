#!/usr/bin/env python3
"""Bounded in-memory framing controls; no native/hosted/artifact qualification."""
from __future__ import annotations

import copy
import hashlib
import io
from pathlib import Path
import struct
import sys
import unittest
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_artifact_zip as Z


def declarations(payloads):
    return [{"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in zip(Z.MEMBERS, payloads)]


def collect(stream):
    chunks = []
    while True:
        try:
            chunks.append(next(stream))
        except StopIteration as completed:
            return b"".join(chunks), completed.value, chunks


class ByteControls(unittest.TestCase):
    def setUp(self):
        self.payloads = [b"ciphertext-zero", b'{"schema":4}', b"ciphertext-tail", b'{"schema":1}']
        self.members = declarations(self.payloads)

    def stream(self, payloads=None, members=None):
        selected = self.payloads if payloads is None else payloads
        return Z.stored_zip(self.members if members is None else members, lambda index: iter((selected[index],)))

    def test_exact_literal_roster_and_prediction(self):
        expected = 22 + sum(92 + 2 * len(name) + len(raw) for name, raw in zip(Z.MEMBERS, self.payloads))
        self.assertEqual(Z.zip_bytes(self.members), expected)
        self.assertEqual(Z.checked_members(self.members), tuple((row["name"], row["bytes"], row["sha256"])
                                                              for row in self.members))

    def test_zipfile_independent_reader_observes_all_four_exact_payloads(self):
        raw, result, chunks = collect(self.stream())
        self.assertTrue(all(0 < len(chunk) <= Z.CHUNK_BYTES for chunk in chunks))
        self.assertEqual(len(raw), Z.zip_bytes(self.members))
        self.assertEqual(result["zipSha256"], hashlib.sha256(raw).hexdigest())
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(archive.namelist(), list(Z.MEMBERS))
            self.assertIsNone(archive.testzip())
            for index, name in enumerate(Z.MEMBERS):
                info = archive.getinfo(name)
                self.assertEqual(archive.read(name), self.payloads[index])
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.flag_bits, 8)
                self.assertEqual(info.extra, b"")
                self.assertEqual(info.comment, b"")
                self.assertEqual(info.CRC, result["members"][index]["crc32"])
            self.assertEqual(archive.comment, b"")

    def test_exact_classic_headers_descriptors_offsets_and_no_zip64(self):
        raw, result, _chunks = collect(self.stream())
        offsets, cursor = [], 0
        for index, (name, data) in enumerate(zip(Z.MEMBERS, self.payloads)):
            offsets.append(cursor)
            fields = struct.unpack_from("<IHHHHHIIIHH", raw, cursor)
            self.assertEqual(fields, (0x04034B50, 20, 8, 0, 0, 33, 0, 0, 0, len(name), 0))
            self.assertEqual(raw[cursor + 30:cursor + 30 + len(name)], name.encode("ascii"))
            cursor += 30 + len(name) + len(data)
            self.assertEqual(struct.unpack_from("<IIII", raw, cursor),
                             (0x08074B50, result["members"][index]["crc32"], len(data), len(data)))
            cursor += 16
        beginning = cursor
        for index, name in enumerate(Z.MEMBERS):
            fields = struct.unpack_from("<IHHHHHHIIIHHHHHII", raw, cursor)
            self.assertEqual(fields, (0x02014B50, 0x0314, 20, 8, 0, 0, 33,
                                      result["members"][index]["crc32"], len(self.payloads[index]),
                                      len(self.payloads[index]), len(name), 0, 0, 0, 0,
                                      0o100600 << 16, offsets[index]))
            cursor += 46 + len(name)
        self.assertEqual(struct.unpack_from("<IHHHHIIH", raw, cursor),
                         (0x06054B50, 0, 0, 4, 4, cursor - beginning, beginning, 0))
        self.assertEqual(cursor + 22, len(raw))

    def test_preparation_and_header_do_not_invoke_payload_supplier(self):
        called = []
        def supplier(index):
            called.append(index)
            return iter((self.payloads[index],))
        stream = Z.stored_zip(self.members, supplier)
        self.assertEqual(called, [])
        next(stream)
        self.assertEqual(called, [])
        next(stream)
        self.assertEqual(called, [0])
        stream.close()
        self.assertEqual(called, [0])

    def test_every_supplier_is_exhausted_before_its_descriptor(self):
        calls = []
        def supplier(index):
            calls.append((index, "start"))
            yield self.payloads[index]
            calls.append((index, "end"))
        raw, result, _chunks = collect(Z.stored_zip(self.members, supplier))
        self.assertEqual(calls, [(index, phase) for index in range(4) for phase in ("start", "end")])
        self.assertEqual(result["zipBytes"], len(raw))

    def test_multi_chunk_crc_hash_and_bounded_demand(self):
        self.payloads[0] = b"a" * Z.CHUNK_BYTES + b"b" * 15
        self.members = declarations(self.payloads)
        calls = []
        def supplier(index):
            raw = self.payloads[index]
            for offset in range(0, len(raw), Z.CHUNK_BYTES):
                calls.append((index, offset))
                yield raw[offset:offset + Z.CHUNK_BYTES]
        raw, result, chunks = collect(Z.stored_zip(self.members, supplier))
        self.assertEqual(calls, [(0, 0), (0, Z.CHUNK_BYTES), (1, 0), (2, 0), (3, 0)])
        self.assertLessEqual(max(map(len, chunks)), Z.CHUNK_BYTES)
        self.assertEqual(result["zipSha256"], hashlib.sha256(raw).hexdigest())

    def test_result_does_not_claim_native_eof_close_host_or_qualification(self):
        _raw, result, _chunks = collect(self.stream())
        self.assertEqual(set(result), {"schema", "scope", "members", "zipBytes", "zipSha256",
                                       "nativeFileRetirement", "originalRunnerOutcome", "qualification"})
        self.assertEqual(result["scope"], Z.SCOPE)
        self.assertEqual(result["nativeFileRetirement"], "NOT_ESTABLISHED")
        self.assertEqual(result["originalRunnerOutcome"], "NOT_OBSERVED")
        self.assertEqual(result["qualification"], "NOT_ESTABLISHED")

    def test_input_declarations_are_captured_before_any_demand(self):
        stream = self.stream()
        self.members[0]["name"] = "substitution"
        self.members[0]["sha256"] = "0" * 64
        raw, result, _chunks = collect(stream)
        self.assertEqual(result["members"][0]["name"], Z.MEMBERS[0])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(archive.namelist(), list(Z.MEMBERS))

    def test_declared_cap_boundary_is_checked_without_allocating_payload(self):
        changed = copy.deepcopy(self.members)
        others = sum(row["bytes"] for row in changed[1:])
        changed[0]["bytes"] = Z.MAX_ZIP_BYTES - Z.OVERHEAD - others
        self.assertEqual(Z.zip_bytes(changed), Z.MAX_ZIP_BYTES)
        changed[0]["bytes"] += 1
        with self.assertRaisesRegex(Z.ZipError, "COMPLETE_ZIP_LIMIT"):
            Z.zip_bytes(changed)

    def test_wrong_roster_order_or_unexpected_field_refuses_before_supplier(self):
        mutations = [self.members[:-1], self.members + [self.members[0]], list(reversed(self.members))]
        for key, value in (("name", "../manifest.json"), ("extra", False)):
            changed = copy.deepcopy(self.members)
            changed[0][key] = value
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=mutations.index(changed)), self.assertRaises(Z.ZipError):
                Z.stored_zip(changed, lambda _index: self.fail("supplier invoked"))

    def test_types_sizes_and_hashes_are_strict(self):
        for key, values in (("bytes", (True, False, 0, -1, 1.0, "1", Z.CIPHERTEXT_BYTES + 1)),
                            ("sha256", ("A" * 64, "g" * 64, "f" * 63, None, b"f" * 64))):
            for value in values:
                changed = copy.deepcopy(self.members)
                changed[0][key] = value
                with self.subTest(field=key, value=type(value).__name__), self.assertRaises(Z.ZipError):
                    Z.zip_bytes(changed)

    def test_manifest_capacity_is_not_ciphertext_capacity(self):
        for index in (1, 3):
            changed = copy.deepcopy(self.members)
            changed[index]["bytes"] = Z.MANIFEST_BYTES + 1
            with self.assertRaisesRegex(Z.ZipError, "MEMBER_SIZE"):
                Z.zip_bytes(changed)

    def test_payload_truncation_corruption_and_overrun_never_return_success(self):
        for replacement in (b"x" * (len(self.payloads[0]) - 1), b"x" * len(self.payloads[0]),
                            self.payloads[0] + b"x"):
            changed = list(self.payloads)
            changed[0] = replacement
            with self.assertRaises(Z.ZipError):
                collect(self.stream(payloads=changed))

    def test_empty_nonbyte_mutable_or_oversized_chunks_refuse(self):
        for chunk in (b"", "x", bytearray(b"x"), memoryview(b"x"), b"x" * (Z.CHUNK_BYTES + 1)):
            with self.subTest(kind=type(chunk).__name__), self.assertRaisesRegex(Z.ZipError, "INPUT_CHUNK"):
                collect(Z.stored_zip(self.members, lambda _index: iter((chunk,))))

    def test_supplier_error_propagates_without_descriptor_or_success_result(self):
        failure = RuntimeError("bounded test fixture")
        def supplier(_index):
            yield self.payloads[0]
            raise failure
        stream = Z.stored_zip(self.members, supplier)
        next(stream)  # Local header only.
        next(stream)  # Exact bytes, but not yet supplier exhaustion/native EOF.
        with self.assertRaises(RuntimeError) as raised:
            next(stream)
        self.assertIs(raised.exception, failure)

    def test_no_extra_empty_tail_is_tolerated_after_exact_bytes(self):
        def supplier(index):
            yield self.payloads[index]
            yield b""
        with self.assertRaisesRegex(Z.ZipError, "INPUT_CHUNK"):
            collect(Z.stored_zip(self.members, supplier))


if __name__ == "__main__":
    unittest.main(failfast=True)
