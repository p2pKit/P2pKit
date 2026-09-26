#!/usr/bin/env python3
"""Small authored K/U pending DATA controls; no B/K/U or native execution.

No prior fixture/suite, owner, real/fake Recipient, file copy, output writer,
native/process/provider or live clock is invoked. Supplied positive records
remain historical DATA, not genuine successful BEFORE or custody evidence.
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
        raise AssertionError("TAIL_HANDOFF_DATA_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_recipient_tail_handoff as H


NAMES = ("evidence.tar.gz.gpg", "manifest.json", "custody-tail.tar.gz.gpg", "custody-tail-manifest.json")
SEED_NAMES = {"initialSealSha256", "initialSealEndNs", "initialSealClockRole", "initialSealClockDomain",
    "initialSealClockTicksPerSecond", "initialSealBootSha256"}
DOMAINS = {"linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns"}
NS = 1_000_000_000


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def hashed(value):
    return hashlib.sha256(wire(value)).hexdigest()


def fixture(role="linux-x64", kind="worker"):
    # Deliberately synthetic source/run/close labels, never a hosted result.
    actual_role = "linux-x64" if kind == "gate" else role
    clock = {"role": actual_role, "domain": DOMAINS[actual_role],
        "ticksPerSecond": 7_000_003 if actual_role == "windows-x64" else NS}
    work, job_end = ((180 * NS, 360 * NS) if kind == "gate" else (241 * NS, 1200 * NS))
    window = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1", "clock": clock,
        "originalBootDigest": "a" * 64, "kind": kind, "originalJobBasisNs": 0, "jobEndNs": job_end, "startNs": NS,
        "workEndNs": work, "nativeFinalEndNs": work + 45 * NS, "readEndNs": work + 75 * NS,
        "sealEndNs": work + 105 * NS, "uploadEndNs": work + 165 * NS, "afterEndNs": work + 180 * NS}
    seed = {"initialSealSha256": "b" * 64, "initialSealEndNs": str(window["sealEndNs"]),
        "initialSealClockRole": actual_role, "initialSealClockDomain": clock["domain"],
        "initialSealClockTicksPerSecond": str(clock["ticksPerSecond"]), "initialSealBootSha256": "a" * 64}
    members = [{"name": name, "bytes": 1, "sha256": digit * 64} for name, digit in zip(NAMES, "cdef")]
    return {"schema": 1, "scope": "INITIAL_RECIPIENT_BEFORE_UPLOAD_PENDING_V1", "kind": kind,
        "selection": "desktop-" + role, "source": {"commit": "1" * 40, "tree": "2" * 40},
        "github": {"repository": "p2pKit/P2pKit", "runId": "9001", "runAttempt": "2",
            "job": "initial-recipient-gate" if kind == "gate" else "populate", "jobId": 9002, "role": actual_role},
        "originalWindow": window, "deadline": seed,
        "originals": {"eventSha256": "3" * 64, "policySha256": H.T.S.POLICY_SHA256, "matchSha256": "4" * 64},
        "predecessors": {"cryptoStepSha256": "5" * 64, "collectSha256": "6" * 64, "sealSha256": "b" * 64,
            "beforeAuthoritySha256": "7" * 64, "originalWindowSha256": hashed(window)},
        "manifests": {"p0Sha256": "d" * 64, "tailSha256": "f" * 64}, "cutMapSha256": "8" * 64,
        "members": members, "totalBytes": 4, "zipBytes": 556,
        "knownCloses": {name: "9" * 64 for name in
            ("beforeReadbackSha256", "beforeCloseWriterSha256", "tailChildCloseSha256", "carrierCloseSha256")},
        "times": {"beforeClosedNs": 2 * NS, "tailChildClosedNs": 3 * NS,
            "carrierClosedNs": 4 * NS, "pendingPreparedNs": 5 * NS},
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED",
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def guarded(operation, value):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return operation(value)
    finally:
        GUARDED = previous


class PendingDataControls(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(H.parse_pending, wire(value))

    def test_fixed_four_names_paths_and_downstream_cap(self):
        self.assertEqual(H.T.CARRIER_MEMBERS, NAMES)
        self.assertEqual((H.DIRECTORY, H.FILE, H.PRIVATE_CARRIER_CLOSE),
            ("tail-returned", "before-upload-pending.json", "carrier-close.json"))
        self.assertEqual((H.LIMIT, H.MAX_ZIP_BYTES, H.T.posix.MAX_CIPHERTEXT_BYTES),
            (65536, 512 * 1024 * 1024, 576 * 1024 * 1024))
        self.assertEqual(guarded(H.carrier_bytes, fixture()["members"]), (4, 556))

    def test_four_roles_and_gate_use_only_canonical_data(self):
        for role in DOMAINS:
            for kind in ("gate", "worker"):
                with self.subTest(role=role, kind=kind):
                    value = fixture(role, kind)
                    raw = wire(value)
                    self.assertEqual(guarded(H.encode_pending, value), raw)
                    self.assertEqual(guarded(H.parse_pending, raw), value)
                    self.assertEqual(wire(value), raw)

    def test_seven_output_values_are_hash_and_unchanged_seed_only(self):
        value = fixture()
        raw = wire(value)
        outputs = guarded(H.output_values, raw)
        self.assertEqual(set(outputs), SEED_NAMES | {"initialBeforeSha256"})
        self.assertEqual(outputs, {"initialBeforeSha256": hashlib.sha256(raw).hexdigest(), **value["deadline"]})
        self.assertEqual((H.HASH_ENV, H.OUTCOME_ENV), ("P2PKIT_INITIAL_BEFORE_SHA256", "P2PKIT_INITIAL_BEFORE_OUTCOME"))

    def test_codec_has_no_file_clock_process_or_output_effects(self):
        value = fixture()
        with ExitStack() as stack:
            for module, names in ((H.B.clocks, ("observe", "checked_now")),
                    (H.B.continuity, ("boot_digest", "append_outputs")), (H.T.time, ("time", "monotonic"))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_LIVE_CALL")))
            self.assertEqual(guarded(H.encode_pending, value), wire(value))
            self.assertEqual(guarded(H.parse_pending, wire(value)), value)
            self.assertEqual(len(guarded(H.output_values, wire(value))), 7)

    def test_missing_extra_and_private_top_fields(self):
        for remove in (True, False):
            value = fixture()
            if remove:
                del value["knownCloses"]
            else:
                value["privatePath"] = "/never-a-public-field"
            self.reject(value)

    def test_wrong_schema_scope_and_kind(self):
        for name, bad in (("schema", True), ("schema", 4), ("scope", H.T.SCOPE), ("kind", "productive")):
            value = fixture()
            value[name] = bad
            self.reject(value)

    def test_source_uses_exact_commit_and_tree_only(self):
        for field, bad in (("commit", "A" * 40), ("tree", "1" * 39), ("path", "relative")):
            value = fixture()
            value["source"][field] = bad
            self.reject(value)

    def test_wrong_selection_or_worker_host(self):
        for field, bad in (("selection", "ordinary-full"), ("github", {**fixture()["github"], "role": "macos-arm64"})):
            value = fixture()
            value[field] = bad
            self.reject(value)

    def test_run_job_role_and_service_id_types(self):
        for name, bad in (("runId", 9001), ("runAttempt", "02"), ("jobId", True), ("jobId", 0),
                ("job", "ordinary"), ("repository", "someone/P2pKit"), ("runnerName", "private")):
            value = fixture()
            value["github"][name] = bad
            self.reject(value)

    def test_seed_missing_extra_nondecimal_and_mismatched_clock(self):
        for name, bad in (("initialSealEndNs", 346 * NS), ("initialSealEndNs", "0346000000000"),
                ("initialSealClockRole", "macos-x64"), ("initialSealBootSha256", "0" * 64), ("extra", "1")):
            value = fixture()
            value["deadline"][name] = bad
            self.reject(value)
        value = fixture()
        del value["deadline"]["initialSealSha256"]
        self.reject(value)

    def test_original_window_algebra_even_after_rehash(self):
        for name in ("originalJobBasisNs", "jobEndNs", "startNs", "workEndNs", "nativeFinalEndNs",
                "readEndNs", "sealEndNs", "uploadEndNs", "afterEndNs"):
            value = fixture()
            value["originalWindow"][name] += 1
            value["predecessors"]["originalWindowSha256"] = hashed(value["originalWindow"])
            self.reject(value)

    def test_boolean_nan_and_clock_frequency_are_not_integer_times(self):
        for target, name, bad in (("originalWindow", "workEndNs", True), ("times", "beforeClosedNs", 2.0),
                ("times", "carrierClosedNs", "4000000000")):
            value = fixture()
            value[target][name] = bad
            self.reject(value)
        value = fixture()
        value["times"]["pendingPreparedNs"] = float("nan")
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(H.pending_value, value)
        value = fixture()
        value["originalWindow"]["clock"]["ticksPerSecond"] = True
        self.reject(value)

    def test_predecessor_seal_and_window_hash_must_agree(self):
        for field in ("sealSha256", "originalWindowSha256"):
            value = fixture()
            value["predecessors"][field] = "0" * 64
            self.reject(value)

    def test_hash_rosters_reject_unknown_missing_and_invalid_values(self):
        for name in ("originals", "predecessors", "manifests", "knownCloses"):
            for change in ("extra", "missing", "invalid"):
                value = fixture()
                selected = next(iter(value[name]))
                if change == "extra":
                    value[name]["privatePin"] = "0" * 64
                elif change == "missing":
                    del value[name][selected]
                else:
                    value[name][selected] = "Z" * 64
                self.reject(value)

    def test_policy_hash_is_unchanged_source_pin(self):
        value = fixture()
        value["originals"]["policySha256"] = "0" * 64
        self.reject(value)

    def test_literal_member_order_path_case_and_count(self):
        for change in ("reverse", "path", "case", "extra", "missing", "tuple"):
            value = fixture()
            if change == "reverse":
                value["members"].reverse()
            elif change == "path":
                value["members"][0]["name"] = "upload-output/" + NAMES[0]
            elif change == "case":
                value["members"][0]["name"] = NAMES[0].upper()
            elif change == "extra":
                value["members"].append(dict(value["members"][0]))
            elif change == "missing":
                value["members"].pop()
            else:
                with self.assertRaises((ValueError, RuntimeError)):
                    guarded(H.carrier_bytes, tuple(value["members"]))
                continue
            self.reject(value)

    def test_manifest_maximum_and_member_positive_integer_bounds(self):
        for index, size in ((0, 0), (2, True), (1, 65537), (3, -1), (0, 576 * 1024 * 1024 + 1)):
            value = fixture()
            value["members"][index]["bytes"] = size
            self.reject(value)

    def test_exact_zip_cap_then_one_byte_over_not_a_new_allowance(self):
        value = fixture()
        value["members"][0]["bytes"] = 512 * 1024 * 1024 - 552 - 3
        self.assertEqual(guarded(H.carrier_bytes, value["members"]),
            (512 * 1024 * 1024 - 552, 512 * 1024 * 1024))
        value["members"][0]["bytes"] += 1
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(H.carrier_bytes, value["members"])

    def test_size_equations_and_manifest_links_are_exact(self):
        for name, bad in (("totalBytes", 5), ("zipBytes", 4), ("totalBytes", True),
                ("manifests", {"p0Sha256": "0" * 64, "tailSha256": "f" * 64})):
            value = fixture()
            value[name] = bad
            self.reject(value)

    def test_original_close_order_and_exclusive_seal_end(self):
        for name, bad in (("beforeClosedNs", 0), ("tailChildClosedNs", NS), ("carrierClosedNs", 2 * NS),
                ("pendingPreparedNs", fixture()["originalWindow"]["sealEndNs"])):
            value = fixture()
            value["times"][name] = bad
            self.reject(value)

    def test_each_self_success_or_acceptance_promotion_refused(self):
        for name, bad in (("writerReturn", "KNOWN"), ("originalStepOutcome", "success"), ("upload", "success"),
                ("testAcceptance", "PASS"), ("productiveAuthority", True), ("cacheAuthority", 0),
                ("exportSaveAuthority", True), ("budgetAcceptance", "ADMITTED")):
            value = fixture()
            value[name] = bad
            self.reject(value)

    def test_noncanonical_duplicate_trailing_and_oversized_wire(self):
        raw = wire(fixture())
        for bad in (raw[:-1], raw + b"\n", b" " + raw, b"{\"schema\":1," + raw[1:], b"x" * 65537, b"{}\n"):
            with self.subTest(size=len(bad)), self.assertRaises((ValueError, RuntimeError)):
                guarded(H.parse_pending, bad)


if __name__ == "__main__":
    unittest.main()
