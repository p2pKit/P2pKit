#!/usr/bin/env python3
"""Focused carrier-close DATA controls; no K/native/U capability or execution.

Every supplied positive record is synthetic history, never a successful Step,
original file/owner/close or hosted artifact. No older test/fixture is imported.
File/clock/environment/process/native/provider operations are forbidden inside
the codec boundary. These controls do not qualify the actual copy/close route.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("TAIL_CARRIER_DATA_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_recipient_tail_carrier as R


NAMES = ("evidence.tar.gz.gpg", "manifest.json", "custody-tail.tar.gz.gpg", "custody-tail-manifest.json")
SOURCES = ("export-output/evidence.tar.gz.gpg", "export-output/manifest.json",
    "tail-export-output/evidence.tar.gz.gpg", "tail-export-output/manifest.json")
PHASES = ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")
DOMAINS = {"linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns"}
NS = 1_000_000_000


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def copied(value):
    return json.loads(wire(value))


def pin(role, number):
    return [1, f"{number:032x}" if role == "windows-x64" else number]


def metadata(role, number, count=1):
    if role == "windows-x64":
        return {"identity": pin(role, number), "is_directory": False, "size": count, "links": 1,
            "attributes": 0x80, "creation_100ns": 10, "modified_100ns": 20, "change_100ns": 30,
            "owner_sid": "S-1-5-21-1", "protected_dacl": True}
    return {"device": 1, "inode": number, "size": count, "mtime_ns": 20, "ctime_ns": 30}


def resources(labels):
    return [{"ordinal": ordinal, "label": label, "closeAttempted": True, "closed": True}
        for ordinal, label in enumerate(labels)]


def fixture(role="linux-x64", kind="worker"):
    actual = "linux-x64" if kind == "gate" else role
    clock = {"role": actual, "domain": DOMAINS[actual],
        "ticksPerSecond": 7_000_003 if actual == "windows-x64" else NS}
    work, job_end = (180 * NS, 360 * NS) if kind == "gate" else (241 * NS, 1200 * NS)
    window = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1", "clock": clock,
        "originalBootDigest": "a" * 64, "kind": kind, "originalJobBasisNs": 0, "jobEndNs": job_end, "startNs": NS,
        "workEndNs": work, "nativeFinalEndNs": work + 45 * NS, "readEndNs": work + 75 * NS,
        "sealEndNs": work + 105 * NS, "uploadEndNs": work + 165 * NS, "afterEndNs": work + 180 * NS}
    seed = {"initialSealSha256": "b" * 64, "initialSealEndNs": str(window["sealEndNs"]),
        "initialSealClockRole": actual, "initialSealClockDomain": clock["domain"],
        "initialSealClockTicksPerSecond": str(clock["ticksPerSecond"]), "initialSealBootSha256": "a" * 64}
    files = []
    for number, (name, source, digit) in enumerate(zip(NAMES, SOURCES, "cdef")):
        written = metadata(actual, 101 + 10 * number)
        readback = copied(written)
        if actual == "windows-x64":
            readback["modified_100ns"], readback["change_100ns"] = 21, 32
        files.append({"name": name, "bytes": 1, "sha256": digit * 64,
            "sourceRelative": source, "sourceDirectoryIdentity": pin(actual, 10 if number < 2 else 11),
            "sourceRead": {"metadata": metadata(actual, 100 + 10 * number), "readerOrdinal": 4 + number * 3},
            "write": {"metadata": written, "writerOrdinal": 5 + number * 3},
            "readback": {"metadata": readback, "readerOrdinal": 6 + number * 3},
            "metadataPolicy": "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY" if actual == "windows-x64" else
                "POSIX_FULL_METADATA_EQUAL"})
    return {"schema": 1, "scope": "INITIAL_RECIPIENT_K_CARRIER_KNOWN_CLOSE_V1", "kind": kind,
        "selection": "desktop-" + role, "source": {"commit": "1" * 40, "tree": "2" * 40},
        "github": {"repository": "p2pKit/P2pKit", "runId": "9001", "runAttempt": "2",
            "job": "initial-recipient-gate" if kind == "gate" else "populate", "jobId": 9002, "role": actual},
        "originalWindow": window, "deadline": seed,
        "predecessors": {"cryptoStepSha256": "3" * 64, "collectSha256": "4" * 64, "sealSha256": "b" * 64,
            "beforeAuthoritySha256": "5" * 64, "originalWindowSha256": hashlib.sha256(wire(window)).hexdigest()},
        "manifests": {"p0Sha256": "d" * 64, "tailSha256": "f" * 64}, "cutMapSha256": "6" * 64,
        "carrier": {"relative": "upload-output", "identity": pin(actual, 12)}, "files": files,
        "totalBytes": 4, "zipBytes": 556,
        "nativeClose": {"contextSha256": "7" * 64, "resultSha256": "8" * 64, "ackSha256": "9" * 64,
            "phaseSha256": {name: "9" * 64 for name in PHASES}},
        # DATA-only ledger rows. No actual native owner is created or restored.
        "ownerCloses": {"native": {"schema": 1, "scope": "INITIAL_K_NATIVE_PARENT_KNOWN_CLOSE_V1",
            "resources": resources(("directory",)), "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False},
            "carrier": {"schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
                "resources": resources(("directory",) * 4 + ("reader", "writer", "reader") * 4),
                "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}},
        "times": {"beforeClosedNs": 2 * NS, "tailChildClosedNs": 3 * NS, "carrierClosedNs": 4 * NS},
        "writerReturn": "PENDING_SEPARATE_RECORD_WRITER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
        "upload": "NOT_PERFORMED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False,
        "cacheAuthority": False, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous


class CarrierDataControls(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(R.parse_close, wire(value))

    def test_exact_literal_contract_and_four_roles(self):
        self.assertEqual(R.SOURCE_NAMES, SOURCES)
        self.assertEqual(R.PHASE_NAMES, PHASES)
        self.assertEqual((R.LIMIT, R.H.MAX_ZIP_BYTES), (65536, 512 * 1024 * 1024))
        for role in DOMAINS:
            for kind in ("gate", "worker"):
                with self.subTest(role=role, kind=kind):
                    value = fixture(role, kind)
                    self.assertEqual(guarded(R.encode_close, value), wire(value))
                    self.assertEqual(guarded(R.parse_close, wire(value)), value)

    def test_no_file_clock_native_process_or_output_effects(self):
        value = fixture()
        with ExitStack() as stack:
            for module, names in ((R.H.B.clocks, ("observe", "checked_now")),
                    (R.H.B.continuity, ("boot_digest", "append_outputs")), (R.H.T.time, ("time", "monotonic"))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_LIVE_CALL")))
            self.assertEqual(guarded(R.parse_close, wire(value)), value)

    def test_scope_top_fields_and_boolean_schema_are_exact(self):
        for field, bad in (("schema", True), ("schema", 2), ("scope", R.H.SCOPE),
                ("kind", "productive"), ("ownWriterClose", "KNOWN")):
            value = fixture()
            value[field] = bad
            self.reject(value)
        value = fixture()
        del value["nativeClose"]
        self.reject(value)

    def test_bound_source_github_role_job_and_ids(self):
        for field, bad in (("repository", "other/repository"), ("role", "windows-x64"), ("job", "other"),
                ("jobId", True), ("jobId", 0), ("runId", 9001), ("runAttempt", "02")):
            value = fixture()
            value["github"][field] = bad
            self.reject(value)
        for field, bad in (("commit", "A" * 40), ("tree", "2" * 39)):
            value = fixture()
            value["source"][field] = bad
            self.reject(value)

    def test_window_arithmetic_stays_original_after_rehash(self):
        for name in ("jobEndNs", "workEndNs", "nativeFinalEndNs", "readEndNs", "sealEndNs", "uploadEndNs", "afterEndNs"):
            value = fixture()
            value["originalWindow"][name] += 1
            value["predecessors"]["originalWindowSha256"] = hashlib.sha256(wire(value["originalWindow"])).hexdigest()
            self.reject(value)

    def test_seal_clock_boot_and_predecessor_hashes_must_link(self):
        for field, bad in (("initialSealSha256", "0" * 64), ("initialSealEndNs", "1"),
                ("initialSealClockTicksPerSecond", "1"), ("initialSealBootSha256", "0" * 64)):
            value = fixture()
            value["deadline"][field] = bad
            self.reject(value)
        for field in ("sealSha256", "originalWindowSha256"):
            value = fixture()
            value["predecessors"][field] = "0" * 64
            self.reject(value)

    def test_carrier_path_and_identity_are_fixed_typed(self):
        for bad in ({"relative": "../upload-output", "identity": [1, 12]},
                {"relative": "upload-output", "identity": [1, True]},
                {"relative": "upload-output", "identity": [1, 0]},
                {"relative": "upload-output", "identity": [True, 12]}):
            value = fixture()
            value["carrier"] = bad
            self.reject(value)

    def test_exact_member_order_names_sources_and_roster(self):
        for change in ("reverse", "path", "case", "source", "missing", "extra"):
            value = fixture()
            if change == "reverse":
                value["files"].reverse()
            elif change == "missing":
                value["files"].pop()
            elif change == "extra":
                value["files"].append(copied(value["files"][0]))
            elif change == "source":
                value["files"][2]["sourceRelative"] = SOURCES[0]
            else:
                value["files"][0]["name"] = "dir/" + NAMES[0] if change == "path" else NAMES[0].upper()
            self.reject(value)

    def test_file_row_fields_cannot_admit_private_extra_or_missing(self):
        for extra in (True, False):
            value = fixture()
            if extra:
                value["files"][0]["completedStep"] = "success"
            else:
                del value["files"][0]["metadataPolicy"]
            self.reject(value)

    def test_sixteen_ordered_carrier_resources_are_required(self):
        for change in ("missing", "extra", "label", "ordinal", "boolean"):
            value = fixture()
            rows = value["ownerCloses"]["carrier"]["resources"]
            if change == "missing":
                rows.pop()
            elif change == "extra":
                rows.append({"ordinal": 16, "label": "reader", "closeAttempted": True, "closed": True})
            elif change == "label":
                rows[5]["label"] = "reader"
            elif change == "ordinal":
                rows[5]["ordinal"] = 6
            else:
                rows[1]["ordinal"] = True
            self.reject(value)

    def test_all_three_observation_ordinals_are_exact(self):
        for number in range(4):
            for name, field in (("sourceRead", "readerOrdinal"), ("write", "writerOrdinal"), ("readback", "readerOrdinal")):
                value = fixture()
                value["files"][number][name][field] += 1
                self.reject(value)

    def test_native_and_carrier_known_close_flags_are_not_receipts(self):
        for side in ("native", "carrier"):
            for field, bad in (("closeAttempted", False), ("closed", False), ("closed", 1)):
                value = fixture()
                value["ownerCloses"][side]["resources"][0][field] = bad
                self.reject(value)

    def test_owner_close_scope_retirement_schema_and_extra_fields(self):
        for side in ("native", "carrier"):
            for field, bad in (("scope", "receipt"), ("schema", True), ("retirement", "UNKNOWN"),
                    ("exportSaveAuthority", 0), ("successfulStep", True)):
                value = fixture()
                value["ownerCloses"][side][field] = bad
                self.reject(value)

    def test_source_and_destination_file_identity_cannot_alias(self):
        for role in DOMAINS:
            value = fixture(role)
            value["files"][0]["sourceRead"]["metadata"] = copied(value["files"][0]["write"]["metadata"])
            self.reject(value)
            value = fixture(role)
            value["files"][1]["sourceRead"]["metadata"] = copied(value["files"][0]["sourceRead"]["metadata"])
            self.reject(value)

    def test_distinct_destination_files_cannot_alias_each_other(self):
        value = fixture()
        for name in ("write", "readback"):
            value["files"][1][name]["metadata"] = copied(value["files"][0][name]["metadata"])
        self.reject(value)

    def test_source_directory_pairs_and_disjoint_carrier_are_required(self):
        for which, identity in ((1, [1, 19]), (2, [1, 10]), (0, [1, 12]), (0, [1, 100])):
            value = fixture()
            value["files"][which]["sourceDirectoryIdentity"] = identity
            self.reject(value)

    def test_file_must_not_alias_any_source_or_carrier_directory(self):
        for inode in (10, 11, 12):
            value = fixture()
            value["files"][0]["sourceRead"]["metadata"]["inode"] = inode
            self.reject(value)

    def test_posix_writer_close_requires_full_metadata_equality(self):
        for name in ("device", "inode", "size", "mtime_ns", "ctime_ns"):
            value = fixture()
            value["files"][0]["readback"]["metadata"][name] += 1
            self.reject(value)

    def test_windows_only_write_close_times_may_differ_without_direction_claim(self):
        before = metadata("windows-x64", 100)
        after = copied(before)
        after["modified_100ns"], after["change_100ns"] = 1, 2
        self.assertEqual(guarded(R.write_close_metadata, "windows-x64", before, after, 1),
            "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY")
        for name, bad in (("creation_100ns", 11), ("owner_sid", "S-1-5-21-2"), ("attributes", 0),
                ("identity", [2, "1" * 32])):
            changed = copied(after)
            changed[name] = bad
            with self.assertRaises((ValueError, RuntimeError)):
                guarded(R.write_close_metadata, "windows-x64", before, changed, 1)

    def test_windows_regular_private_single_link_and_no_reparse_are_mandatory(self):
        for name, bad in (("is_directory", True), ("is_directory", 0), ("links", 2), ("links", True),
                ("attributes", 0x400), ("attributes", 0x10), ("protected_dacl", False), ("protected_dacl", 1),
                ("owner_sid", "unbound"), ("identity", [1, "G" * 32])):
            value = fixture("windows-x64")
            value["files"][0]["sourceRead"]["metadata"][name] = bad
            self.reject(value)

    def test_metadata_fields_and_integer_types_are_exact(self):
        for role in DOMAINS:
            for name, bad in (("size", True), ("extra", "unbound")):
                value = fixture(role)
                value["files"][0]["sourceRead"]["metadata"][name] = bad
                self.reject(value)
        for name, bad in (("inode", True), ("device", -1), ("mtime_ns", 1.0), ("ctime_ns", "30")):
            value = fixture()
            value["files"][0]["sourceRead"]["metadata"][name] = bad
            self.reject(value)

    def test_write_close_policy_cannot_weaken_per_reader_metadata(self):
        for role in DOMAINS:
            value = fixture(role)
            value["files"][0]["metadataPolicy"] = "IGNORE_TIMESTAMPS"
            self.reject(value)

    def test_native_phase_roster_and_ack_stdout_hash_link(self):
        for change in ("missing", "extra", "ack", "bad"):
            value = fixture()
            if change == "missing":
                del value["nativeClose"]["phaseSha256"]["stderr.log"]
            elif change == "extra":
                value["nativeClose"]["phaseSha256"]["receipt.json"] = "9" * 64
            elif change == "ack":
                value["nativeClose"]["ackSha256"] = "0" * 64
            else:
                value["nativeClose"]["resultSha256"] = "G" * 64
            self.reject(value)

    def test_manifest_hashes_and_size_equations_cannot_be_relabelled(self):
        for field, bad in (("totalBytes", True), ("totalBytes", 5), ("zipBytes", 557)):
            value = fixture()
            value[field] = bad
            self.reject(value)
        value = fixture()
        value["files"][1]["sha256"] = "0" * 64
        self.reject(value)

    def test_zip_ceiling_includes_all_framing_before_any_io(self):
        value = fixture()
        count = 512 * 1024 * 1024 - 552 - 3
        value["files"][0]["bytes"] = count
        for name in ("sourceRead", "write", "readback"):
            value["files"][0][name]["metadata"]["size"] = count
        value["totalBytes"], value["zipBytes"] = count + 3, count + 3 + 552
        self.assertEqual(guarded(R.parse_close, wire(value)), value)
        value["files"][0]["bytes"] += 1
        for name in ("sourceRead", "write", "readback"):
            value["files"][0][name]["metadata"]["size"] += 1
        value["totalBytes"] += 1
        value["zipBytes"] += 1
        self.reject(value)

    def test_chronology_and_exclusive_original_seal_ceiling(self):
        for name, bad in (("beforeClosedNs", True), ("tailChildClosedNs", NS), ("carrierClosedNs", 2 * NS),
                ("carrierClosedNs", fixture()["originalWindow"]["sealEndNs"])):
            value = fixture()
            value["times"][name] = bad
            self.reject(value)

    def test_no_self_step_writer_upload_test_budget_or_productive_success(self):
        for name, bad in (("writerReturn", "KNOWN"), ("originalStepOutcome", "success"), ("upload", "success"),
                ("testAcceptance", "PASS"), ("productiveAuthority", True), ("cacheAuthority", 0),
                ("exportSaveAuthority", True), ("budgetAcceptance", "ADMITTED")):
            value = fixture()
            value[name] = bad
            self.reject(value)

    def test_canonical_bounded_wire_and_duplicate_keys(self):
        raw = wire(fixture())
        for bad in (raw[:-1], raw + b"\n", b" " + raw, b'{"schema":1,' + raw[1:], b"{}\n", b"x" * 65537):
            with self.assertRaises((ValueError, RuntimeError)):
                guarded(R.parse_close, bad)

    def test_supplied_mutable_graph_alias_is_not_a_second_observation(self):
        value = fixture()
        value["files"][0]["readback"]["metadata"] = value["files"][0]["write"]["metadata"]
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(R.close_value, value)


if __name__ == "__main__":
    unittest.main()
