#!/usr/bin/env python3
"""New bounded productive-final DATA models; no custody or hosted qualification.

The full281/279 rosters below are tiny in-memory DECLARATIONS. They are not
native files, actual query returns, source admission or an executed archive.
No historical test module, successful reader suite or public key is selected.
"""
from __future__ import annotations

import copy
import ctypes
from pathlib import Path
import stat
import sys
import unittest


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_CUSTODY_DATA_MODEL_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_custody_data as CD

O, D, NS = CD.O, CD.D, CD.NS
H, EMPTY = "a" * 64, O.digest(b"")
REFUSALS = (ValueError, RuntimeError)


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_CUSTODY_DATA_MODEL_EFFECT")


def clock():
    return {"role": "linux-x64", "domain": O.clocks.DOMAINS["linux-x64"], "ticksPerSecond": NS}


def closed(*, native=False):
    return {"schema": 1, "scope": "INITIAL_PRODUCTIVE_FINAL_NATIVE_OWNER_CLOSE_V1" if native else
        "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1", "resources": [
            {"ordinal": 0, "label": "directory", "closeAttempted": True, "closed": True}],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


def claims():
    return {name: "success" if name.endswith("OUTCOME") else H for name in CD.FINAL_CLAIMS}


def groups(count=30):
    rows = []
    for ordinal, group in enumerate(CD.GROUPS[:count], 1):
        files = 281 if ordinal <= 21 or ordinal in (24, 28) else {
            22: 1374, 23: 6, 25: 122, 26: 3, 27: 7, 29: 9, 30: 13}[ordinal]
        rows.append({"ordinal": ordinal, "group": group,
            "map": {"name": "map-" + group + ".json", "bytes": 10, "sha256": H},
            "dataFiles": files, "dataBytes": files})
    return rows


def index_value():
    rows = groups()
    files, size = sum(row["dataFiles"] for row in rows), sum(row["dataBytes"] for row in rows)
    return {"schema": 1, "scope": CD.INDEX_SCOPE, "kind": "worker", "groups": rows,
        "dataFiles": files, "dataBytes": size, "mapFiles": 30, "mapBytes": 300, "indexFiles": 0,
        "archiveFilesBeforeIndex": files + 30, "archiveNativeNodesBeforeIndex": files + 61,
        "plaintextBytesBeforeIndex": size + 300, "contextSha256": H, "startSha256": H, "parent28Sha256": H,
        "reads": [{"ordinal": number, "mapSha256": H, "readCloseSha256": H, "returnedNs": number}
            for number in range(1, 31)], "writerReturn": CD.PENDING, "budgetAcceptance": "NOT_ADMITTED",
        "exportSaveAuthority": False}


def native(number, size, *, directory=False):
    return ("posix", 7, number, (stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o600),
        0, 2 if directory else 1, size, 1, 1)


def map_value():
    group = CD.GROUPS[28]
    target = {"relative": group + "/member-00000.bin", "kind": "file", "bytes": 3,
        "sha256": O.digest(b"abc"), "native": list(native(3, 3))}
    return {"schema": 1, "scope": CD.MAP_SCOPE, "ordinal": 29, "group": group,
        "root": {"relative": group, "kind": "directory", "bytes": None, "sha256": None,
            "native": list(native(1, 4096, directory=True))},
        "members": [{"ordinal": 0, "source": "/model/source", "sourceKind": "native-file", "maximum": 3,
            "bytes": 3, "sha256": target["sha256"], "sourceNative": list(native(2, 3)), "writerNative": {},
            "destination": target, "provenance": "SYNTHETIC_DATA_ONLY"}],
        "sourceDirectories": [], "dataBytes": 3, "dataFiles": 1, "dataOwnerClose": closed(),
        "writerReturn": CD.PENDING, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def authority_index(*, post=False):
    originals = CD._authority_original_names(post=post)
    pinned = (".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")
    directories = {name: {"relative": name, "identity": [7, number], "provenance": "ORIGINAL_NATIVE_PIN"}
        for number, name in enumerate(pinned, 1)}
    files, counter = set(originals), 1
    for section, count in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
        directories[section + "/query-home"] = {"relative": section + "/query-home", "identity": None,
            "provenance": "ORIGINAL_QUERY_DECLARATION"}
        files.add(section + "/owner.json")
        for _number in range(count):
            path = section + "/query-" + format(counter, "032x")
            counter += 1
            directories[path] = {"relative": path, "identity": None, "provenance": "ORIGINAL_QUERY_DECLARATION"}
            files.update(path + "/" + name for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"))
    rows = []
    for name in sorted(files):
        if name == "service/stdout.log":
            maximum = 16384
        elif name == "service/stderr.log":
            maximum = 65536
        elif "/query-" in name and name.endswith("/stderr.log"):
            maximum = 4096
        elif name.startswith(("source-before/", "source-after/", "acquisition-queries/")) and not name.endswith(
                ("/session-result.json", "/source-return.json", "/stdout.log")):
            maximum = 1
        else:
            maximum = CD.LIMIT
        rows.append({"relative": name, "maximum": maximum, "bytes": 0, "sha256": EMPTY,
            "provenance": "ACTUAL_RETAINED_BYTES" if name in originals else "ORIGINAL_QUERY_DECLARATION"})
    return {"schema": 1, "scope": CD.POST_AUTHORITY_INDEX_SCOPE if post else CD.PRE_AUTHORITY_INDEX_SCOPE,
        "edge": "POST_EXPORT" if post else "PRE_EXPORT", "root": "/model/authority", "clock": clock(),
        "contextSha256": H, "pendingSha256": None if post else H, "files": rows,
        "directories": [directories[name] for name in sorted(directories)], "fileCount": len(rows),
        "directoryCount": 58, "retainedOriginalCount": len(originals), "totalBytes": 0,
        "copyState": "ORIGINAL_BYTES_NOT_COPIED", "writerReturn": CD.PENDING,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def final_inputs():
    observed = {"kind": "worker", "role": "linux-x64", "firstUseAt": 1}
    history = {name: None for name in D.HISTORY_FIELDS.split()}
    history.update(kind="worker", observed=observed, currentAuthority="NOT_ACQUIRED", matchSha256=H,
        budgetAcceptance="NOT_ADMITTED", exportSaveAuthority=False)
    value = {name: H for name in CD.FINAL_INPUT_FIELDS.split() if name.endswith("Sha256")}
    value.update(schema=1, scope=CD.FINAL_INPUTS_SCOPE, kind="worker", observed=observed, history=history,
        originalProposal={}, claims=claims(), workerIdentity={}, sourceRecordsSha256={name: H for name in D.SOURCE_KEYS},
        inputProvenance="ORIGINAL_FINAL_READER_AND_NEW_PRE_AUTHORITY", budgetAcceptance="NOT_ADMITTED", exportSaveAuthority=False)
    return value


class CustodyDataModels(unittest.TestCase):
    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(REFUSALS):
            self.check(function, *args, **kwargs)

    def test_canonical_data_is_not_admission(self):
        raw = O.encoded(final_inputs())
        self.assertEqual(self.check(CD.final_inputs, raw)["sourceRecordsSha256"], {name: H for name in D.SOURCE_KEYS})
        self.assertFalse(hasattr(CD, "ParentFinal"))
        self.assertFalse(hasattr(CD, "prepare_final_export"))

    def test_canonical_spelling_and_size_are_exact(self):
        self.assertEqual(self.check(CD.canonical, b"{}\n"), {})
        self.refuses(CD.canonical, b"{}")
        self.refuses(CD.canonical, bytearray(b"{}\n"))
        self.refuses(CD.canonical, b"{}\n", 2)

    def test_final_inputs_require_the_original_compatibility_digest(self):
        value = final_inputs()
        raw = O.encoded(value)
        self.assertEqual(self.check(CD.final_inputs, raw)["compatibilityInputsSha256"], H)
        self.assertLess(len(raw), CD.LIMIT)
        without = copy.deepcopy(value); del without["compatibilityInputsSha256"]
        self.assertEqual(len(raw) - len(O.encoded(without)), 95)
        self.refuses(CD.final_inputs, O.encoded(without))
        for wrong in (True, "", H[:-1], "A" * 64, {"sha256": H}):
            changed = copy.deepcopy(value); changed["compatibilityInputsSha256"] = wrong
            self.refuses(CD.final_inputs, O.encoded(changed))

    def test_non_bool_integer_and_digest_grammar(self):
        for value in (True, -1, 1.0, 1 << 64):
            self.refuses(CD.integer, value)
        for value in (H.upper(), H[:-1], bytes(H, "ascii")):
            self.refuses(CD.sha, value)

    def test_raw_local_deadlines_are_not_interchangeable(self):
        self.assertEqual(self.check(CD.local, 1.0), 1.0)
        for value in (1, True, float("nan"), float("inf"), -0.1):
            self.refuses(CD.local, value)

    def test_exact_group30_order_and_accounting(self):
        rows = groups()
        self.assertIs(self.check(CD.group_references, rows, 30), rows)
        self.assertEqual(sum(row["dataFiles"] for row in rows), 7962 + 10 + 10 + 7 + 8)
        self.assertEqual(sum(row["dataFiles"] for row in rows[:28]), 7950 + 10 + 7 + 8)

    def test_productive_group_requires_all114_originals_plus_exact_raw8(self):
        for count in (28, 30):
            rows = groups(count)
            self.assertEqual(self.check(CD.group_references, rows, count)[24]["dataFiles"], 122)
            for incomplete in (114, 121, 123, True):
                changed = copy.deepcopy(rows); changed[24]["dataFiles"] = incomplete
                self.refuses(CD.group_references, changed, count)
        self.assertEqual((CD.MAX_BYTES, CD.MAX_NODES), (512 * 1024 * 1024, 10000))

    def test_group28_cannot_be_group30(self):
        self.refuses(CD.group_references, groups(28), 30)
        rows = groups()
        rows[0], rows[1] = rows[1], rows[0]
        self.refuses(CD.group_references, rows, 30)

    def test_fixed_group_counts_do_not_accept38_as281(self):
        for ordinal in (1, 21, 24, 28):
            rows = groups()
            rows[ordinal - 1]["dataFiles"] = 38
            self.refuses(CD.group_references, rows, 30)

    def test_final_index_excludes_its_future_writer_return(self):
        value = index_value()
        parsed = self.check(CD.final_index, O.encoded(value))
        self.assertEqual(parsed["indexFiles"], 0)
        self.assertEqual(parsed["writerReturn"], CD.PENDING)
        value["indexFiles"] = 1
        self.refuses(CD.final_index, O.encoded(value))

    def test_final_index_includes_own_bytes_and62_native_nodes(self):
        value = index_value()
        value["plaintextBytesBeforeIndex"] += 1
        self.refuses(CD.final_index, O.encoded(value))
        value = index_value()
        value["archiveNativeNodesBeforeIndex"] += 1
        self.refuses(CD.final_index, O.encoded(value))

    def test_final_index_has_exact30_original_read_hashes(self):
        value = index_value()
        value["reads"][29]["mapSha256"] = "b" * 64
        self.refuses(CD.final_index, O.encoded(value))
        value = index_value()
        value["reads"].pop()
        self.refuses(CD.final_index, O.encoded(value))

    def test_map_data_owner_close_is_distinct_from_pending_map_writer(self):
        value = map_value()
        self.assertEqual(self.check(CD.map_record, O.encoded(value), 29)["writerReturn"], CD.PENDING)
        value["dataOwnerClose"]["resources"][0]["closed"] = False
        self.refuses(CD.map_record, O.encoded(value), 29)

    def test_map_directory_sentinels_are_exact(self):
        value = map_value()
        value["root"]["bytes"] = 0
        self.refuses(CD.map_record, O.encoded(value), 29)
        value = map_value()
        value["root"]["sha256"] = EMPTY
        self.refuses(CD.map_record, O.encoded(value), 29)

    def test_map_embedded_return_is_never_a_native_file(self):
        value = map_value()
        member = value["members"][0]
        member.update(source="recipient-return.json", sourceKind="embedded-not-disk", sourceNative=None)
        self.check(CD.map_record, O.encoded(value), 29)
        member["sourceNative"] = list(native(2, 3))
        self.refuses(CD.map_record, O.encoded(value), 29)

    def test_native_hardlink_reparse_and_bool_identity_refuse(self):
        stamp = list(native(2, 3))
        stamp[5] = 2
        self.refuses(CD.native, tuple(stamp), directory=False)
        stamp = list(native(2, 3))
        stamp[1] = True
        self.refuses(CD.native, tuple(stamp), directory=False)
        windows = ("windows", 7, "1" * 32, False, 3, 1, 0x400, 1, 1, 1, "S-1-5-21", True)
        self.refuses(CD.native, windows, directory=False)

    def test_pre_and_post_indices_keep_actual38_36_separate(self):
        for post, originals, files in ((False, 38, 281), (True, 36, 279)):
            value = self.check(CD.authority_index, O.encoded(authority_index(post=post)), post=post)
            self.assertEqual(value["retainedOriginalCount"], originals)
            self.assertEqual(value["fileCount"], files)
            self.assertEqual(sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in value["files"]), originals)

    def test_declarations_cannot_claim_actual281(self):
        value = authority_index()
        value["retainedOriginalCount"] = 281
        self.refuses(CD.authority_index, O.encoded(value), post=False)
        value = authority_index()
        next(row for row in value["files"] if row["provenance"] == "ORIGINAL_QUERY_DECLARATION")["provenance"] = "ACTUAL_RETAINED_BYTES"
        self.refuses(CD.authority_index, O.encoded(value), post=False)

    def test_authority_exact_query_roster_not_just_counts(self):
        value = authority_index()
        row = next(row for row in value["directories"] if "/query-" in row["relative"] and not row["relative"].endswith("query-home"))
        row["relative"] = "source-before/query-" + "f" * 31 + "g"
        value["directories"].sort(key=lambda item: item["relative"])
        self.refuses(CD.authority_index, O.encoded(value), post=False)

    def test_authority_declared_cap_and_empty_hash_are_original(self):
        value = authority_index()
        next(row for row in value["files"] if row["relative"] == "service/stdout.log")["maximum"] = CD.LIMIT
        self.refuses(CD.authority_index, O.encoded(value), post=False)
        value = authority_index()
        value["files"][0]["sha256"] = H
        self.refuses(CD.authority_index, O.encoded(value), post=False)

    def test_authority_pre_post_scope_not_aliases(self):
        self.refuses(CD.authority_index, O.encoded(authority_index()), post=True)
        self.refuses(CD.authority_index, O.encoded(authority_index(post=True)), post=False)

    def test_authority_caps_are_exact_six_with_one45(self):
        caps = tuple(value * NS for value in (100, 280, 280, 110, 155, 200))
        self.assertEqual(self.check(CD.authority_caps, caps), caps)
        self.refuses(CD.authority_caps, (*caps[:4], 156 * NS, caps[5]))
        self.refuses(CD.authority_caps, (*caps, 0))

    def test_crypto_transmits_original_first4_and_native210_45(self):
        caps = tuple(value * NS for value in (180, 420, 465, 495, 100, 310, 355))
        self.assertEqual(self.check(CD.crypto_caps, caps), caps)
        self.refuses(CD.crypto_caps, (*caps[:5], 311 * NS, 356 * NS))
        self.refuses(CD.crypto_caps, (*caps[:4], 180 * NS, 390 * NS, 435 * NS))

    def test_final_inputs_reject_pending_original_step(self):
        value = final_inputs()
        value["claims"]["AFTER_PROBE_OUTCOME"] = "pending"
        self.refuses(CD.final_inputs, O.encoded(value))
        value = final_inputs()
        value["probeSha256"] = "b" * 64
        self.refuses(CD.final_inputs, O.encoded(value))

    def test_exact_two_output_sets_never_old_aliases(self):
        for collect, fields in ((False, CD.EXPORT_OUTPUT_FIELDS), (True, CD.COLLECT_OUTPUT_FIELDS)):
            value = tuple((name, H) for name in fields)
            self.assertIs(self.check(CD.output_values, value, collect=collect), value)
            self.refuses(CD.output_values, value[::-1], collect=collect)
            self.refuses(CD.output_values, list(value), collect=collect)
            self.refuses(CD.output_values, value, collect=not collect)

    def test_owner_close_data_cannot_attest_pending_or_unknown(self):
        value = closed(native=True)
        self.check(CD.owner_close, value, native_owner=True)
        for marker in ("UNKNOWN", "PENDING_OWNER_CLOSE"):
            changed = copy.deepcopy(value)
            changed["retirement"] = marker
            self.refuses(CD.owner_close, changed, native_owner=True)
        self.refuses(CD.owner_close, value, native_owner=False)


if __name__ == "__main__":
    unittest.main(failfast=True)
