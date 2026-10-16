#!/usr/bin/env python3
"""Authored UNRUN productive K controls, not original/native acceptance.

Pure DATA plus actual K guards over explicit in-memory clocks/resources only.
The small supplier test registers a deliberately incomplete MODEL state solely
to exercise the wrapper, never the child/Recipient/archive acquisition path.
No native API, process, GPG, credential, file payload, provider or CI is used.
No accepted prior suite is imported or counted as new execution evidence.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import importlib.util
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_recipient_productive_tail as K

TD, CD, O, NS = K.TD, K.CD, K.O, K.NS
RD = K.RD
_fixture_path = Path(__file__).with_name("hosted-initial-artifact-productive-delivery-test.py")
_spec = importlib.util.spec_from_file_location("_productive_tail_data_fixture", _fixture_path)
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)

# Deliberately retained: no test clears UNKNOWN or pretends failed model close.
MODEL_QUARANTINES = []


def model_native(role, number, size=0, *, directory=False):
    """Explicit observation DATA, never a native handle or acquired identity."""
    if role == "windows-x64":
        return ("windows", 7, format(number, "032x"), directory, size, 1,
            0x10 if directory else 0x80, 100, 200, 300, "S-1-5-21-1", True)
    return ("posix", 7, number, (stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o600),
        0, 2 if directory else 1, size, 200, 300)


def model_close(labels, *, native_owner=False):
    return {"schema": 1, "scope": RD.NATIVE_CLOSE_SCOPE if native_owner else "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
        "resources": [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
            for number, label in enumerate(labels)], "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


def model_projection(row, prefix=""):
    return {"relative": prefix + row["relative"], **{name: deepcopy(row[name]) for name in
        ("bytes", "sha256", "maximum", "native", "directoryNative", "provenance")}}


class BeforeTransportModel:
    """Full585/280/58 DATA with two explicit directory epochs, not valid R custody.

    Real RD index/writer/known-close grammars and K projection/epoch predicates
    are used without replacement. File bodies are symbolic; this fixture does
    NOT qualify RD.authority_bundle, a K context, an owner or any native read.
    rewrap() changes only outer hashes so negative semantic mutations reach the
    real join. It never silently repairs the original row/writer/close links.
    """
    def __init__(self, role="linux-x64"):
        self.role = role
        self.f = F.qualification_fixture(role)
        self.deadline = deepcopy(self.f["deadline"])
        self.base = Path(K.ROOT.anchor) / "MODEL_NOT_NATIVE" / "primary-custody"
        self.root = self.base / "productive-receiver" / "before" / "authority"
        ids = tuple(tuple(format(first + n, "032x") for n in range(count))
            for first, count in ((1, 12), (13, 24), (37, 12)))
        required, names = RD.B.member_grammar(*ids)
        pins = {name: model_native(role, 1000 + number, 0 if role == "windows-x64" else 4096, directory=True)
            for number, name in enumerate(names)}
        self.earlier = pins["."]
        later = list(self.earlier)
        if role != "windows-x64":
            later[6] += 256
        later[-4 if role == "windows-x64" else -2] += 10
        later[-3 if role == "windows-x64" else -1] += 10
        self.later = tuple(later)
        self.raws = {name: b"" if name.endswith(".log") else TD.encoded({"SYNTHETIC_NOT_ORIGINAL": name})
            for name in required}
        observations = []
        for ordinal, name in enumerate(item for item in required if item != "authority-close.json"):
            observations.append({"relative": name, "maximum": CD.LIMIT, "bytes": len(self.raws[name]),
                "sha256": TD.sha(self.raws[name]), "native": list(model_native(role, ordinal + 1, len(self.raws[name]))),
                "directoryNative": list(pins[name.rpartition("/")[0] or "."]), "provenance": RD.PROVENANCE,
                "readerOrdinal": 58 + ordinal, "retirement": "KNOWN_READER_CLOSE"})
        final = {"relative": "authority-close.json", "maximum": CD.LIMIT, "bytes": len(self.raws["authority-close.json"]),
            "sha256": TD.sha(self.raws["authority-close.json"]),
            "native": list(model_native(role, 280, len(self.raws["authority-close.json"]))),
            "directoryNative": list(self.later), "provenance": RD.PROVENANCE,
            "readerOrdinal": 2, "retirement": "KNOWN_READER_CLOSE"}
        self.reader_close = model_close(("directory",) * 58 + ("reader",) * 279)
        self.writer = {"schema": 1, "scope": RD.WRITER_SCOPE, "relative": "authority-close.json",
            "bytes": final["bytes"], "sha256": final["sha256"], "preCloseWrite": {"bytes": final["bytes"],
                "sha256": final["sha256"], "metadata": RD.file_metadata(tuple(final["native"])), "writerOrdinal": 1,
                "observation": "PRE_CLOSE_WRITE_VERIFY", "retirement": "KNOWN_WRITER_CLOSE"},
            "readback": deepcopy(final), "metadataPolicy": "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY" if role == "windows-x64"
                else "POSIX_FULL_METADATA_EQUAL", "ownerClose": model_close(("directory", "writer", "reader")),
            "closedNs": self.deadline["sealFirstNs"] + 2 * NS, "originalStepOutcome": "NOT_OBSERVED",
            "capture": "NOT_K_CAPTURE", "exportSaveAuthority": False}
        self.before = {"schema": 1, "scope": RD.INDEX_SCOPE, "edge": "before", "root": str(self.root),
            "clock": deepcopy(self.deadline["clock"]), "authorityContextSha256": TD.sha(self.raws["context.json"]),
            "requiredFiles": list(required), "files": sorted((*observations, final), key=lambda row: row["relative"]),
            "directories": [{"relative": name, "path": str(self.root if name == "." else self.root / name),
                "originalIdentity": list(pins[name][1:3]) if name in RD.B.DIRECTORY_TARGETS else None,
                "originalProvenance": "ORIGINAL_AUTHORITY_NATIVE_PIN" if name in RD.B.DIRECTORY_TARGETS else "UNPINNED_ORIGINAL_DIRECTORY",
                "readbackNative": list(pins[name])} for name in names], "fileCount": 280, "directoryCount": 58,
            "totalBytes": sum(len(raw) for raw in self.raws.values()),
            "authorityCloseSha256": final["sha256"], "closeWriterReturn": deepcopy(self.writer),
            "originalReadbackClose": deepcopy(self.reader_close), "capture": "NOT_K_CAPTURE", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False}
        prefix = []
        for number, (name, maximum) in enumerate((*RD.FINAL_INPUTS, ("seal/seal-pending.json", CD.LIMIT),
                *(("seal/authority/" + name, CD.LIMIT) for name in required))):
            raw = TD.encoded({"SYNTHETIC_PREFIX_NOT_ORIGINAL": name})
            prefix.append({"relative": name, "maximum": maximum, "bytes": len(raw), "sha256": TD.sha(raw),
                "native": list(model_native(role, 2000 + number, len(raw))),
                "directoryNative": list(model_native(role, 4000, directory=True)), "provenance": RD.PROVENANCE})
        self.source = {"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_R_ORIGINAL_READ_TRANSPORT_V1",
            "files": prefix + [model_projection(row, "before/authority/") for row in self.before["files"]], "fileCount": 585,
            "beforeIndexSha256": F.model_hash("unbound-index"), "beforeAuthoritySha256": final["sha256"],
            "deadlineSha256": TD.sha(TD.encoded(self.deadline)),
            "provenance": "ACTUAL_R_RETURN_REFERENCES_NOT_RECONSTRUCTED_OWNERS", "exportSaveAuthority": False}
        self.context = {"session": str(self.base / "productive-tail" / TD.DIRECTORY), "deadline": deepcopy(self.deadline),
            "beforeClosedNs": self.writer["closedNs"], "parentFirstNs": self.writer["closedNs"] + NS,
            "predecessors": {"collectCloseSha256": self.deadline["collectCloseSha256"], "sealSha256": self.deadline["sealSha256"],
                "beforeAuthoritySha256": final["sha256"], "beforeIndexSha256": F.model_hash("unbound-index"),
                "deadlineSha256": self.source["deadlineSha256"]}, "filesSha256": {}}

    def named(self, name):
        return next(row for row in self.before["files"] if row["relative"] == name)

    def source_named(self, name):
        return next(row for row in self.source["files"] if row["relative"] == "before/authority/" + name)

    def synchronize_changed_final_directory(self):
        """EXPLICIT test mutation: keep final row/index/writer consistent, not historic context."""
        self.writer["readback"] = deepcopy(self.named("authority-close.json"))
        self.before["closeWriterReturn"] = deepcopy(self.writer)
        self.source["files"][305:] = [model_projection(row, "before/authority/") for row in self.before["files"]]

    def rewrap(self):
        index_raw = TD.encoded(self.before)
        self.source["beforeIndexSha256"] = TD.sha(index_raw)
        self.context["predecessors"]["beforeIndexSha256"] = TD.sha(index_raw)
        transport = {"source-index.json": TD.encoded(self.source), "before-index.json": index_raw,
            "before-input-close.json": TD.encoded(model_close(("directory", "reader"))),
            "before-readback-close.json": TD.encoded(self.reader_close),
            "before-native-close.json": TD.encoded(model_close(("directory",), native_owner=True)),
            "before-writer-close.json": TD.encoded(self.writer), "deadline.json": TD.encoded(self.deadline)}
        self.context["filesSha256"] = {name: TD.sha(raw) for name, raw in transport.items()}
        return self.context, transport


class ModelClock:
    """Only the explicitly listed external observations are modeled."""
    def __init__(self, case, role="linux-x64", cancelled=None):
        self.case = case
        self.fixture = F.qualification_fixture(role)
        self.deadline = self.fixture["deadline"]
        self.first_ns = self.deadline["sealFirstNs"] + NS
        self.now_ns = self.first_ns
        self.local = 100.0
        self.boot = self.deadline["originalBootDigest"]
        self.calls = []
        self.cancelled = cancelled or (lambda: self.calls.append("cancel-check"))
        data = self.deadline["clock"]
        self.identity = O.clocks.ClockIdentity(data["role"], data["domain"], data["ticksPerSecond"])
        self.first = O.clocks.Reading(self.identity, self.first_ns)
        work = min(self.first_ns + 210 * NS, self.deadline["sealEndNs"] - 45 * NS)
        self.caps = (self.first_ns, work, work + 45 * NS)
        self.stack = ExitStack()

    def checked_now(self, clock, *, minimum_ns):
        self.case.assertIs(clock, self.identity)
        self.case.assertGreaterEqual(self.now_ns, minimum_ns)
        self.calls.append("raw")
        return self.now_ns

    def boot_digest(self, role):
        self.case.assertEqual(role, self.identity.role)
        self.calls.append("boot")
        return self.boot

    def __enter__(self):
        self.case.assertFalse(K.native.QUARANTINE, "refuse any real existing quarantine")
        self.case.assertFalse(K.Q.QUARANTINE)
        self.case.assertFalse(K.continuity.QUARANTINE)
        self.case.assertFalse(K.E.windows._QUARANTINE)
        self.case.assertFalse(K.native.diagnostics._QUARANTINE)
        self.stack.enter_context(patch.dict(K.os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(K.time, "monotonic", lambda: self.local))
        self.stack.enter_context(patch.object(O.clocks, "checked_now", self.checked_now))
        self.stack.enter_context(patch.object(K.continuity, "boot_digest", self.boot_digest))
        try:
            self.clock = K._Clock(self.first, self.local, self.boot, self.cancelled, self.deadline, self.caps)
        except BaseException:
            self.stack.close()
            raise
        return self

    def __exit__(self, *args):
        self.stack.__exit__(*args)


class ModelResource:
    def __init__(self, error=None):
        self.closes = 0
        self.error = error

    def close(self):
        self.closes += 1
        if self.error is not None:
            raise self.error


class ProductiveTailDataControls(unittest.TestCase):
    def setUp(self):
        self.f = F.qualification_fixture()
        self.assertEqual(len(F.qualify(self.f)), 5)

    def test_real_flat_ten_join_and_map_counted_once(self):
        final, tail = TD.join_manifests(self.f["final_manifest_raw"], self.f["tail_manifest_raw"])
        cut = tail["cut"]
        self.assertEqual(tuple(cut["groups"]), tuple(sorted(TD.GROUPS)))
        self.assertEqual(cut["memberCount"], sum(row["memberCount"] for row in cut["groups"].values()) + 1)
        self.assertEqual(cut["totalBytes"], sum(row["totalBytes"] for row in cut["groups"].values()) + cut["mapBytes"])
        self.assertEqual(tail["final"], TD.final_reference(self.f["final_manifest_raw"]))
        self.assertFalse(final["productiveAuthority"] or tail["productiveAuthority"])

    def test_flat_cut_rejects_missing_group_or_map_double_count(self):
        value = self.f["tail"]
        for change in ("group", "count", "bytes"):
            cut = deepcopy(value["cut"])
            if change == "group":
                del cut["groups"][TD.GROUPS[0]]
            elif change == "count":
                cut["memberCount"] += 1
            else:
                cut["totalBytes"] += cut["mapBytes"]
            with self.subTest(change=change), self.assertRaises(Exception):
                TD.cut(cut, value["final"], False)

    def test_real_shared_native_node_limit_counts_root(self):
        value = self.f["tail"]
        final = deepcopy(value["final"])
        final["archiveNativeNodes"] = CD.MAX_NODES - value["cut"]["memberCount"]
        final["archiveFiles"] = final["archiveNativeNodes"] - 31
        with self.assertRaisesRegex(Exception, "SHARED_CUT_BOUND"):
            TD.cut(value["cut"], final, False)

    def test_final_tail_recipient_equal_fields_not_unrelated_recipient(self):
        tail = deepcopy(self.f["tail"])
        tail["recipient"]["encryptionFingerprint"] = "C" * 40
        with self.assertRaisesRegex(Exception, "COMPLETE_FINAL_TAIL_JOIN"):
            TD.join_manifests(self.f["final_manifest_raw"], F.raw(tail))

    def test_final_tail_require_same_digest_and_complete_public_bounds(self):
        final, tail = TD.join_manifests(self.f["final_manifest_raw"], self.f["tail_manifest_raw"])
        self.assertEqual(final["productive"]["compatibilityInputsSha256"], tail["productive"]["compatibilityInputsSha256"])
        for value in (final, tail):
            raw = F.raw(value)
            self.assertLess(len(raw), CD.PUBLIC_LIMIT)
            old = deepcopy(value); del old["productive"]["compatibilityInputsSha256"]
            self.assertEqual(len(raw) - len(F.raw(old)), 95)
        changed = deepcopy(tail)
        changed["productive"]["compatibilityInputsSha256"] = "c" * 64
        with self.assertRaisesRegex(Exception, "COMPLETE_FINAL_TAIL_JOIN"):
            TD.join_manifests(self.f["final_manifest_raw"], F.raw(changed))
        del changed["productive"]["compatibilityInputsSha256"]
        with self.assertRaises(Exception):
            TD.public_manifest(F.raw(changed))

    def test_public_tail_cannot_claim_runtime_or_cache_acceptance(self):
        for name, replacement in (("productiveAuthority", True), ("cacheAuthority", True),
                ("exportSaveAuthority", True), ("testAcceptance", "PASSED"), ("budgetAcceptance", "ADMITTED")):
            tail = deepcopy(self.f["tail"])
            tail[name] = replacement
            with self.subTest(name=name), self.assertRaises(Exception):
                TD.public_manifest(F.raw(tail))

    def test_exact_nine_outputs_use_actual_pending_and_same_seal(self):
        values = dict(TD.output_values(self.f["pending_raw"]))
        self.assertEqual(set(values), set(TD.OUTPUT_FIELDS))
        self.assertEqual(len(values), 9)
        self.assertEqual(values[TD.OUTPUT], TD.sha(self.f["pending_raw"]))
        self.assertEqual({name: values[name] for name in TD.SEAL_OUTPUT_FIELDS}, TD.seal_outputs(self.f["deadline"]))
        self.assertEqual(TD.decoded_deadline(values["initialProductiveDeadlineBase64"],
            values["initialProductiveDeadlineSha256"]), self.f["deadline"])
        self.assertLessEqual(sum(len(name) + len(value) + 2 for name, value in values.items()), 4096)
        with self.assertRaisesRegex(Exception, "ORIGINAL_PRECEDING_OUTCOMES"):
            TD.deadline_environment({TD.DEADLINE_HASH_ENV: values["initialProductiveDeadlineSha256"],
                TD.DEADLINE_BASE64_ENV: values["initialProductiveDeadlineBase64"]})

    def test_pending_hashes_do_not_claim_original_step_close(self):
        pending = deepcopy(self.f["pending"])
        pending["originalStepOutcome"] = "success"
        with self.assertRaisesRegex(Exception, "PENDING_NOT_ACCEPTANCE"):
            TD.encode_pending(pending)


class ProductiveBeforeEpochControls(unittest.TestCase):
    def model(self, role="linux-x64"):
        m = BeforeTransportModel(role)
        _index, selected = K._original_read_expectations(*m.rewrap())
        self.assertEqual(len(selected), 585)  # Real positive preflight before each negative mutation.
        return m

    def test_named_later_epoch_changes_only_context_and_preserves_every_original_row(self):
        for role in ("linux-x64", "macos-arm64", "macos-x64", "windows-x64"):
            with self.subTest(role=role):
                m = self.model(role)
                context, transport = m.rewrap()
                saved_context, saved_transport = deepcopy(context), dict(transport)
                index, expected = K._original_read_expectations(context, transport)
                self.assertEqual((index, expected), K._original_read_expectations(context, transport))
                self.assertEqual(TD.encoded(index), transport["source-index.json"])
                self.assertEqual(context, saved_context)
                self.assertEqual(transport, saved_transport)
                by_name = dict(zip((row["relative"] for row in index["files"]), expected))
                changed = [row["relative"] for row, pin in zip(index["files"], expected)
                    if tuple(row["directoryNative"]) != pin]
                self.assertEqual(changed, ["before/authority/context.json"])
                self.assertEqual(by_name[changed[0]], m.later)
                self.assertEqual(tuple(m.source_named("context.json")["directoryNative"]), m.earlier)
                self.assertNotEqual(m.earlier, m.later)
                for name in ("before/authority/authority-close.json", "before/authority/service/start.json",
                        "seal/authority/context.json", "returned/context.json"):
                    original = next(row for row in index["files"] if row["relative"] == name)
                    self.assertEqual(by_name[name], tuple(original["directoryNative"]))
                self.assertNotEqual(m.before["files"][-1]["relative"], "authority-close.json")

    def test_equal_observed_directory_epochs_do_not_require_invented_timestamp_movement(self):
        m = self.model("windows-x64")
        m.named("authority-close.json")["directoryNative"] = list(m.earlier)
        m.synchronize_changed_final_directory()
        index, expected = K._original_read_expectations(*m.rewrap())
        self.assertTrue(all(pin == tuple(row["directoryNative"]) for row, pin in zip(index["files"], expected)))

    def test_original_epoch_preflight_is_passive_without_native_path_or_clock_acquisition(self):
        m = self.model()
        context, transport = m.rewrap()
        forbidden = AssertionError("PASSIVE_DATA_MUST_NOT_ACQUIRE")
        with patch.object(K.os, "stat", side_effect=forbidden), patch.object(K.os, "scandir", side_effect=forbidden), \
                patch.object(K.C, "_paths", side_effect=forbidden), patch.object(K.time, "monotonic", side_effect=forbidden), \
                patch.object(O.clocks, "observe", side_effect=forbidden):
            index, expected = K._original_read_expectations(context, transport)
        self.assertEqual(TD.encoded(index), transport["source-index.json"])
        self.assertEqual(len(expected), 585)

    def test_original_transport_bytes_and_predecessor_hashes_are_required(self):
        for kind in ("raw", "missing", "extra", "beforeIndexSha256", "beforeAuthoritySha256", "deadlineSha256"):
            with self.subTest(kind=kind):
                m = self.model()
                context, transport = m.rewrap()
                if kind == "raw":
                    transport["before-writer-close.json"] += b" "
                elif kind == "missing":
                    del transport["before-writer-close.json"]
                elif kind == "extra":
                    transport["invented-close.json"] = b"{}\n"
                else:
                    context["predecessors"][kind] = F.model_hash("UNRELATED_PREDECESSOR")
                with self.assertRaises(Exception):
                    K._original_read_expectations(context, transport)

    def test_all_historical_row_fields_are_verbatim_not_only_identity_or_hash(self):
        for name in ("context.json", "authority-close.json", "service/start.json"):
            for field in ("bytes", "sha256", "maximum", "native", "directoryNative", "provenance", "extra"):
                with self.subTest(name=name, field=field):
                    m = self.model()
                    row = m.source_named(name)
                    if field in ("bytes", "maximum"):
                        row[field] += 1
                    elif field == "sha256":
                        row[field] = F.model_hash("ALTERED_FILE")
                    elif field in ("native", "directoryNative"):
                        row[field][-1] += 1
                    else:
                        row[field] = "INVENTED_ORIGINAL"
                    with self.assertRaises(Exception):
                        K._original_read_expectations(*m.rewrap())

    def test_unique_complete_before_order_and_literal_names_are_required(self):
        for kind in ("missing", "duplicate", "order", "move", "invented-last", "index-missing-close"):
            with self.subTest(kind=kind):
                m = self.model()
                rows = m.source["files"]
                if kind == "missing":
                    rows.pop()
                elif kind == "duplicate":
                    rows[-1] = deepcopy(rows[-2])
                elif kind == "order":
                    rows[-1], rows[-2] = rows[-2], rows[-1]
                elif kind == "move":
                    m.source_named("context.json")["relative"] = "before/other/context.json"
                elif kind == "invented-last":
                    rows[-1]["relative"] = "before/authority/authority-close.json"
                else:
                    m.before["files"].remove(m.named("authority-close.json"))
                with self.assertRaises(Exception):
                    K._original_read_expectations(*m.rewrap())

    def test_named_index_context_and_actual_writer_readback_must_agree(self):
        for kind in ("context-hash", "index-final-directory", "writer-final-directory", "reader-close"):
            with self.subTest(kind=kind):
                m = self.model()
                if kind == "context-hash":
                    m.before["authorityContextSha256"] = F.model_hash("UNRELATED_CONTEXT")
                elif kind == "index-final-directory":
                    m.named("authority-close.json")["directoryNative"][-1] += 1
                elif kind == "writer-final-directory":
                    m.writer["readback"]["directoryNative"][-1] += 1
                else:
                    m.reader_close["resources"][58]["label"] = "writer"
                with self.assertRaises(Exception):
                    K._original_read_expectations(*m.rewrap())

    def test_actual_writer_reader_ordinals_full_metadata_and_known_close_cannot_be_flags(self):
        for kind in ("writer-ordinal", "reader-ordinal", "close-attempt", "close-return", "writer-state",
                "reader-state", "write-metadata", "read-metadata", "hash", "length", "maximum"):
            with self.subTest(kind=kind):
                m = self.model()
                writer = m.writer
                if kind == "writer-ordinal":
                    writer["preCloseWrite"]["writerOrdinal"] = 2
                elif kind == "reader-ordinal":
                    writer["readback"]["readerOrdinal"] = 3
                elif kind in ("close-attempt", "close-return"):
                    writer["ownerClose"]["resources"][1]["closeAttempted" if kind == "close-attempt" else "closed"] = False
                elif kind in ("writer-state", "reader-state"):
                    writer["preCloseWrite" if kind == "writer-state" else "readback"]["retirement"] = "UNKNOWN"
                elif kind == "write-metadata":
                    writer["preCloseWrite"]["metadata"]["ctime_ns"] += 1
                elif kind == "read-metadata":
                    writer["readback"]["native"][-1] += 1
                elif kind == "hash":
                    writer["readback"]["sha256"] = F.model_hash("UNRELATED_CLOSE")
                elif kind == "length":
                    writer["readback"]["bytes"] += 1
                else:
                    writer["readback"]["maximum"] -= 1
                with self.assertRaises(Exception):
                    K._original_read_expectations(*m.rewrap())

    def test_exact_before_scope_path_clock_and_original_closed_floor(self):
        for kind in ("scope", "edge", "root", "session", "clock", "before-floor", "after-end", "parent-floor"):
            with self.subTest(kind=kind):
                m = self.model()
                if kind in ("scope", "edge"):
                    m.before[kind] = "seal" if kind == "edge" else RD.SEAL_SCOPE
                elif kind == "root":
                    m.before["root"] = str(m.root.parent / "unrelated-authority")
                    for row in m.before["directories"]:
                        row["path"] = str(Path(m.before["root"]) if row["relative"] == "." else Path(m.before["root"]) / row["relative"])
                elif kind == "session":
                    m.context["session"] = str(Path(m.context["session"]).with_name("unrelated-private"))
                elif kind == "clock":
                    m.before["clock"] = deepcopy(F.qualification_fixture("macos-arm64")["deadline"]["clock"])
                elif kind == "before-floor":
                    m.context["beforeClosedNs"] -= 1
                elif kind == "after-end":
                    m.context["beforeClosedNs"] = m.deadline["sealEndNs"]
                else:
                    m.context["parentFirstNs"] = m.writer["closedNs"] - 1
                with self.assertRaises(Exception):
                    K._original_read_expectations(*m.rewrap())

    def test_rehashed_final_row_index_writer_still_cannot_change_stable_root_fields(self):
        changes = {
            "linux-x64": ((1, 8), (2, 9999), (3, stat.S_IFDIR | 0o750), (4, 1), (5, 3)),
            "windows-x64": ((1, 8), (2, "f" * 32), (3, False), (4, 1), (5, 2), (6, 0x20),
                (7, 101), (10, "S-1-5-21-2"), (11, False)),
        }
        for role, fields in changes.items():
            for field, replacement in fields:
                with self.subTest(role=role, field=field):
                    m = self.model(role)
                    m.named("authority-close.json")["directoryNative"][field] = replacement
                    m.synchronize_changed_final_directory()
                    with self.assertRaises(Exception):
                        K._original_read_expectations(*m.rewrap())

    def test_unchanged_read_path_refuses_a_later_current_directory_before_any_file_read(self):
        # FAILURE-ONLY seam: model acquisition/stat observations, not their
        # native predicates or a successful file read. The actual full-equality
        # _read_path and _directory_native code must reject before _open_file.
        m = self.model()
        index, expected = K._original_read_expectations(*m.rewrap())
        original = expected[next(n for n, row in enumerate(index["files"]) if row["relative"] == "before/authority/context.json")]
        path, verifies = m.root / "context.json", []
        for field in (3, 4, 5, 6, 7, 8):
            with self.subTest(field=field):
                changed = list(original)
                changed[field] += 1
                info = SimpleNamespace(**dict(zip(("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink", "st_size",
                    "st_mtime_ns", "st_ctime_ns"), changed[1:])))
                directory = SimpleNamespace(path=path.parent, identity=original[1:3], verify=lambda: verifies.append("MODEL_VERIFY"))
                def acquire(_owner, actual):
                    self.assertEqual(actual, path.parent)
                    return directory
                def observed(actual, *, follow_symlinks):
                    self.assertEqual(actual, path.parent)
                    self.assertFalse(follow_symlinks)
                    return info
                with patch.object(K.C, "_private", acquire), patch.object(K.os, "name", "posix"), \
                        patch.object(K.os, "stat", observed):
                    with self.assertRaisesRegex(Exception, "ORIGINAL_DIRECTORY_METADATA"):
                        K._read_path(object(), path, CD.LIMIT, directory_stamp=original)
        self.assertEqual(len(verifies), 6)


class ProductiveTailLayoutControls(unittest.TestCase):
    def test_fixed_birth_placement_and_six_semantic_phase_names(self):
        self.assertEqual(TD.PHASE_NAMES, ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log"))
        self.assertEqual(K._phase_directory("native-start.json"), "native-birth")
        for name in TD.PHASE_NAMES:
            if name != "native-start.json":
                self.assertEqual(K._phase_directory(name), "service")
        self.assertEqual(K._phase_roster("native-birth", ("native-start.json",)), ("native-start.json",))
        K._phase_roster("service", tuple(sorted(set(TD.PHASE_NAMES) - {"native-start.json"})))
        for name in ("../native-start.json", "service/start.json", "unknown.json", None):
            with self.subTest(name=name), self.assertRaises(Exception):
                K._phase_directory(name)

    def test_moved_missing_extra_or_wrong_directory_birth_record_is_rejected(self):
        service = tuple(sorted(set(TD.PHASE_NAMES) - {"native-start.json"}))
        for directory, entries in (("service", tuple(sorted(TD.PHASE_NAMES))), ("native-birth", ()),
                ("native-birth", ("native-start.json", "extra.json")), ("native-birth", ("start.json",)),
                ("other", ("native-start.json",)), ("service", tuple(name for name in service if name != "start.json"))):
            with self.subTest(directory=directory, entries=entries), self.assertRaisesRegex(Exception, "NATIVE_PHASE_DISK_ROSTER"):
                K._phase_roster(directory, entries)

    def test_real_fixed_route_keeps_modeled_birth_insertion_outside_service(self):
        # The approved finite-placement alternative, NOT a successful _read_path
        # or native scheduling test. The insertion really changes this model.
        files = {"service": {name: b"MODEL_" + name.encode("ascii") for name in
            ("start.json", "baseline.json", "stdout.log", "stderr.log")}, "native-birth": {}}
        pins = {name: model_native("linux-x64", number, 4096, directory=True)
            for number, name in enumerate(files, 1)}
        old_files, old_pins = deepcopy(files), dict(pins)
        start_parent = K._phase_directory("start.json")
        start_before = files[start_parent]["start.json"]
        birth_parent = K._phase_directory("native-start.json")
        files[birth_parent]["native-start.json"] = b"MODEL_OBSERVED_BIRTH_NOT_NATIVE"
        changed = list(pins[birth_parent])
        changed[6] += 128
        changed[7] += 1
        changed[8] += 1
        pins[birth_parent] = tuple(changed)
        start_after = files[start_parent]["start.json"]
        self.assertEqual(start_before, start_after)
        self.assertEqual(files[start_parent], old_files[start_parent])
        self.assertEqual(pins[start_parent], old_pins[start_parent])
        self.assertNotEqual(files[birth_parent], old_files[birth_parent])
        self.assertNotEqual(pins[birth_parent], old_pins[birth_parent])
        K._phase_roster("native-birth", tuple(sorted(files[birth_parent])))
        # The final service roster permits result only AFTER the modeled read;
        # this ordering is not a claim of actual process retirement.
        files[start_parent]["result.json"] = b"MODEL_POST_EXIT_RESULT_NOT_PROOF"
        K._phase_roster("service", tuple(sorted(files[start_parent])))

    def test_precreated_paths_context_alias_checks_and_pending_rosters_include_birth(self):
        for role in ("linux-x64", "windows-x64"):
            with self.subTest(role=role):
                f = F.qualification_fixture(role)
                primary = Path(K.ROOT.anchor) / "MODEL_NOT_NATIVE" / "primary"
                with patch.object(K.N, "location", lambda: ("worker", primary)):
                    paths = K._paths()
                    self.assertEqual(tuple(paths), K.DIRECTORIES)
                    self.assertEqual(paths["native-birth"], paths["tail-returned"] / "native-birth")
                    first = f["deadline"]["sealFirstNs"] + 3 * NS
                    work = f["deadline"]["sealEndNs"] - 45 * NS
                    caps = (first, work, work + 45 * NS)
                    clock = O.clocks.ClockIdentity(*(f["deadline"]["clock"][name] for name in ("role", "domain", "ticksPerSecond")))
                    context = {"schema": 1, "scope": TD.CONTEXT_SCOPE, "kind": "worker", "root": str(K.ROOT),
                        "session": str(paths["tail-returned"]), "job": "a" * 32, "observed": {}, "deadline": f["deadline"],
                        "originalProposal": f["proposal"], "caps": dict(zip(TD.CAP_FIELDS, caps)), "parentFirstNs": first,
                        "parentFirstLocal": 100.0, "beforeClosedNs": first - NS,
                        "originalServiceJob": f["context"]["originalServiceJob"], "predecessors": f["tail"]["predecessors"],
                        "filesSha256": {name: F.model_hash(name) for name in K.INPUT_LIMITS},
                        "directories": {name: None if name == "tail-export-output" and role != "windows-x64" else
                            list(model_native(role, 100 + number, directory=True)[1:3]) for number, name in enumerate(K.DIRECTORIES)},
                        "inheritedContext": {}, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
                    self.assertEqual(K._context(TD.encoded(context), f["deadline"], caps, clock), context)
                    for kind in ("missing", "extra", "alias"):
                        value = deepcopy(context)
                        if kind == "missing":
                            del value["directories"]["native-birth"]
                        elif kind == "extra":
                            value["directories"]["extra"] = [7, 999]
                        else:
                            value["directories"]["native-birth"] = value["directories"]["service"]
                        with self.subTest(kind=kind), self.assertRaises(Exception):
                            K._context(TD.encoded(value), f["deadline"], caps, clock)
        self.assertEqual(K.PRIVATE_DIRECTORIES, ("control-home", "temporary", "service", "native-birth"))
        self.assertEqual(K.PRIVATE_INPUT_NAMES, tuple(sorted((*K.INPUT_LIMITS, "context.json", "tail-child-result.json",
            "control-home", "temporary", "service", "native-birth"))))
        self.assertEqual(K.PRIVATE_CLOSED_NAMES, tuple(sorted((*K.PRIVATE_INPUT_NAMES, TD.PRIVATE_CARRIER_CLOSE, TD.FILE))))

    def test_actual_private_listing_predicate_refuses_missing_or_extra_birth_directory(self):
        # Only external directory-list observations are modeled. Both _names
        # and _list_names validation remain real; no native owner is claimed.
        path = Path(K.ROOT.anchor) / "MODEL_NOT_NATIVE" / TD.DIRECTORY
        for expected in (K.PRIVATE_INPUT_NAMES, K.PRIVATE_CLOSED_NAMES):
            for kind in ("exact", "missing", "extra"):
                with self.subTest(roster=len(expected), kind=kind):
                    observed = expected if kind == "exact" else tuple(name for name in expected if name != "native-birth") \
                        if kind == "missing" else (*expected, "unexpected")
                    calls = []
                    class Scan:
                        def __enter__(self):
                            calls.append("MODEL_LIST_BEGIN")
                            return iter(SimpleNamespace(name=name) for name in observed)
                        def __exit__(self, *_args):
                            calls.append("MODEL_LIST_CLOSED")
                    def listing(actual):
                        self.assertEqual(actual, path)
                        return Scan()
                    owner = SimpleNamespace(guard=lambda: 200.0)
                    directory = SimpleNamespace(path=path, verify=lambda: calls.append("MODEL_DIRECTORY_VERIFY"))
                    with patch.object(K.os, "name", "posix"), patch.object(K.os, "scandir", listing):
                        if kind == "exact":
                            K._names(owner, directory, expected)
                        else:
                            with self.assertRaisesRegex(Exception, "DIRECTORY_EXACT_ROSTER|DIRECTORY_LIMIT"):
                                K._names(owner, directory, expected)
                    self.assertEqual(calls.count("MODEL_LIST_BEGIN"), 1)
                    self.assertEqual(calls.count("MODEL_LIST_CLOSED"), 1)


class ProductiveTailGuardControls(unittest.TestCase):
    def test_actual_clock_guard_uses_two_raw_boot_observations_with_cancel(self):
        with ModelClock(self) as m:
            self.assertEqual(m.clock.now(), m.first_ns)
            self.assertEqual(m.calls, ["raw", "boot", "cancel-check", "raw", "boot"])
            self.assertIs(m.clock.reading, m.first)
            self.assertEqual(m.clock.caps, m.caps)
            self.assertLessEqual(m.clock.deadline(900), m.clock.current().binding[6])

    def test_boot_change_is_sticky_after_original_value_restored(self):
        with ModelClock(self) as m:
            m.clock.now()
            m.boot = F.model_hash("CHANGED-MODEL-BOOT")
            with self.assertRaisesRegex(Exception, "BOOT_CHANGED") as first:
                m.clock.now()
            m.boot = m.deadline["originalBootDigest"]
            with self.assertRaises(Exception) as repeated:
                m.clock.now()
            self.assertIs(repeated.exception, first.exception)

    def test_local_regression_and_original_work_end_are_not_new_leases(self):
        for local, field in ((99.0, None), (None, 6)):
            with self.subTest(local=local), ModelClock(self) as m:
                m.clock.now()
                m.local = local if field is None else m.clock.current().binding[field]
                with self.assertRaisesRegex(Exception, "LOCAL_EXPIRED_OR_BACKWARDS"):
                    m.clock.now()

    def test_cancellation_original_error_is_not_restored_by_swallow(self):
        error = RuntimeError("SYNTHETIC_CANCEL_NOT_PRIVATE")
        def cancelled():
            raise error
        with ModelClock(self, cancelled=cancelled) as m:
            with self.assertRaises(RuntimeError) as first:
                m.clock.now()
            self.assertIs(first.exception, error)
            with self.assertRaises(RuntimeError) as repeated:
                m.clock.current()
            self.assertIs(repeated.exception, error)

    def test_late_credential_fails_before_another_clock_or_supplier(self):
        with ModelClock(self) as m:
            m.clock.now()
            before = list(m.calls)
            with patch.dict(K.os.environ, {"GITHUB_TOKEN": "SYNTHETIC_NONCREDENTIAL"}):
                with self.assertRaisesRegex(Exception, "CLOCK_LINEAGE_OR_QUARANTINE"):
                    m.clock.now()
            self.assertEqual(m.calls, before)
            with self.assertRaises(Exception):
                m.clock.current()

    def test_method_replacement_and_restoration_remain_sticky(self):
        with ModelClock(self) as m:
            m.clock.now()
            with patch.object(K._Clock, "deadline", lambda *_args, **_kw: 999999.0):
                with self.assertRaisesRegex(Exception, "ORIGINAL_SOURCE_SUPPLIER_CHANGED") as first:
                    m.clock.current()
            with self.assertRaises(Exception) as repeated:
                m.clock.current()
            self.assertIs(repeated.exception, first.exception)

    def test_unregistered_equal_children_views_and_before_never_acquire(self):
        child, equal_child = K.TailChild(), K.TailChild()
        self.assertEqual(child, equal_child)
        self.assertIsNot(child, equal_child)
        for value in (child, equal_child):
            with self.assertRaisesRegex(Exception, "GENUINE_CHILD_REQUIRED"):
                K.checked_child_validation(value)
        fake = K.R.ProductiveBefore(*([None] * 12))
        with self.assertRaises(Exception):
            K._Parent(fake, None)
        view = K.TailArchiveView(child, K.TailArchiveBinding(), object(), "linux-x64", None, None,
            None, (), None, None, None, b"{}\n")
        with self.assertRaisesRegex(Exception, "ORIGINAL_OBJECT_CHANGED"):
            K.check_child_archive(view)
        with self.assertRaisesRegex(Exception, "ORIGINAL_OBJECT_CHANGED"):
            K.check_retired_child_archive(view)

    def test_actual_supplier_wrapper_swallowed_reentry_is_terminal(self):
        with ModelClock(self) as m:
            child = K._track(K.TailChild())
            # MODEL registry seam only: intentionally insufficient for _state,
            # which is never called or replaced to manufacture valid custody.
            state = K._track(K._State(child, m.clock, b"MODEL", b"MODEL", (), b"MODEL", None, None, (), None))
            K._CHILDREN[id(child)] = state
            calls, observed = [], []
            marker = object()
            armed = False
            def supplier(handle):
                self.assertIs(handle, child)
                calls.append("original-supplier-entered")
                if not armed:
                    return marker
                try:
                    guarded(handle)
                except BaseException as error:
                    observed.append(error)  # Deliberately swallow nested failure.
                self.assertIn(id(state), K._SUPPLIER_BUSY)
                return marker
            guarded = K._guarded_supplier(supplier)
            self.assertIs(guarded(child), marker)  # Same real wrapper positive before triggering reentry.
            self.assertEqual(calls, ["original-supplier-entered"])
            calls.clear()
            armed = True
            with self.assertRaisesRegex(Exception, "SUPPLIER_REENTRY") as outer:
                guarded(child)
            self.assertEqual(calls, ["original-supplier-entered"])
            self.assertEqual(len(observed), 1)
            self.assertIs(outer.exception, observed[0])
            self.assertIs(K._CHILD_FAILURES[id(state)], observed[0])
            self.assertNotIn(id(state), K._SUPPLIER_BUSY)
            with self.assertRaises(Exception) as sticky:
                m.clock.current()
            self.assertIs(sticky.exception, observed[0])

    def test_actual_owner_close_seam_requires_return_not_ledger_declaration(self):
        with ModelClock(self) as m:
            owner = K._TailNativeOwner(140.0, m.clock, first=m.first, cancelled=m.cancelled)
            resource = ModelResource()
            self.assertIs(owner.acquire("writer", lambda: resource), resource)
            self.assertEqual(resource.closes, 0)
            owner.freeze()
            with self.assertRaisesRegex(Exception, "AUTHORITY_OWNER_CLOSE_NOT_KNOWN"):
                owner.known()
            owner.close()
            self.assertTrue(owner.known().closed)
            owner.close()
            self.assertEqual(resource.closes, 1)

    def test_actual_owner_failed_model_close_stays_unknown_without_retry(self):
        with ModelClock(self) as m:
            model_quarantine = []
            MODEL_QUARANTINES.append(model_quarantine)
            with patch.object(K.native, "QUARANTINE", model_quarantine):
                owner = K._TailNativeOwner(140.0, m.clock, first=m.first, cancelled=m.cancelled)
                failure = RuntimeError("SYNTHETIC_MODEL_CLOSE_UNKNOWN")
                resource = ModelResource(failure)
                owner.acquire("writer", lambda: resource)
                owner.freeze()
                with self.assertRaises(RuntimeError) as first:
                    owner.close()
                self.assertIs(first.exception, failure)
                self.assertTrue(owner.unknown)
                self.assertEqual(len(model_quarantine), 1)
                self.assertIs(model_quarantine[0], owner)
                owner.close()
                self.assertEqual(resource.closes, 1)
                with self.assertRaisesRegex(Exception, "AUTHORITY_OWNER_CLOSE_NOT_KNOWN"):
                    owner.known()
                attempts = []
                with self.assertRaises(Exception):
                    owner.acquire("writer", lambda: attempts.append("ILLEGAL_RETRY"))
                self.assertEqual(attempts, [])

    def test_windows_inclusive_sixty_prelaunch_fits_original_sixty_five_remainder(self):
        with ModelClock(self, "windows-x64") as m:
            class ModelParent:
                clock = m.clock
                @staticmethod
                def now(**kwargs):
                    return m.clock.now(**kwargs)
            self.assertLessEqual(m.caps[1] - m.first_ns, 75 * NS)
            original_caps = m.clock.caps
            m.now_ns = m.caps[1] - 65 * NS
            m.local = m.clock.current().binding[6] - 65
            K._prelaunch_budget(ModelParent(), m.caps)
            self.assertIs(m.clock.caps, original_caps)
            self.assertEqual(m.clock.caps, m.caps)

    def test_raw_and_local_prelaunch_boundaries_are_independently_strict(self):
        for dimension in ("raw", "local"):
            for remaining in (60, 59):
                with self.subTest(dimension=dimension, remaining=remaining), ModelClock(self, "windows-x64") as m:
                    parent = SimpleNamespace(clock=m.clock, now=m.clock.now)
                    m.now_ns = m.caps[1] - (remaining if dimension == "raw" else 65) * NS
                    m.local = m.clock.current().binding[6] - (remaining if dimension == "local" else 65)
                    with self.assertRaisesRegex(Exception, "VALIDATION_CANNOT_FIT"):
                        K._prelaunch_budget(parent, m.caps)
                    self.assertIs(m.clock.caps, m.caps)

    def test_both_just_above_sixty_remainders_pass_without_reserving_another_thirty(self):
        with ModelClock(self, "windows-x64") as m:
            parent = SimpleNamespace(clock=m.clock, now=m.clock.now)
            m.now_ns = m.caps[1] - 60 * NS - 1000
            m.local = m.clock.current().binding[6] - 60 - 0.000001
            K._prelaunch_budget(parent, m.caps)
            self.assertIs(m.clock.caps, m.caps)
            self.assertLess(m.clock.work - m.now_ns, 61 * NS)

    def test_same_second_prelaunch_refuses_time_actually_spent_by_modeled_setup(self):
        with ModelClock(self, "windows-x64") as m:
            parent = SimpleNamespace(clock=m.clock, now=m.clock.now)
            original_caps = m.clock.caps
            m.now_ns = m.caps[1] - 65 * NS
            m.local = m.clock.current().binding[6] - 65
            K._prelaunch_budget(parent, m.caps)
            observations = len(m.calls)
            m.now_ns += 5 * NS
            m.local += 5
            with self.assertRaisesRegex(Exception, "VALIDATION_CANNOT_FIT"):
                K._prelaunch_budget(parent, m.caps)
            self.assertGreater(len(m.calls), observations)
            self.assertIs(m.clock.caps, original_caps)

    def test_actual_operation_caps_keep_inclusive_sixty_two_forty_and_internal_windows_thirty(self):
        for role in ("linux-x64", "windows-x64"):
            for kind, seconds in ((K.TailValidationCaps, 60), (K.TailArchiveCaps, 240)):
                with self.subTest(role=role, kind=kind.__name__), ModelClock(self, role) as m:
                    state = SimpleNamespace(clock=m.clock)
                    first = O.clocks.Reading(m.identity, m.now_ns)
                    with patch.object(O.clocks, "observe", lambda: first):
                        caps = K._operation_caps(state, kind)
                    reserve = 30 * NS if role == "windows-x64" else 0
                    self.assertIs(caps.first, first)
                    self.assertIs(caps.clock, m.identity)
                    self.assertEqual(caps.operationLimitNs, seconds * NS)
                    self.assertEqual(caps.finishReserveNs, reserve)
                    self.assertEqual(caps.operationFinishEndNs, min(m.caps[1], first.nanoseconds + seconds * NS))
                    self.assertEqual(caps.workEndNs, caps.operationFinishEndNs - reserve)
                    self.assertLess(caps.first.nanoseconds, caps.workEndNs)
                    self.assertLessEqual(caps.operationFinishEndNs, m.clock.work)
                    self.assertLess(caps.firstLocal, caps.workEndLocal)
                    self.assertLessEqual(caps.workEndLocal, caps.operationFinishEndLocal - reserve / NS)
                    self.assertLessEqual(caps.operationFinishEndLocal, m.clock.current().binding[6])
                    self.assertIs(m.clock.caps, m.caps)

    def test_operation_reserve_requires_positive_raw_and_local_work_not_a_new_finish_lease(self):
        for dimension in ("raw", "local"):
            for remaining in (30, 29):
                with self.subTest(dimension=dimension, remaining=remaining), ModelClock(self, "windows-x64") as m:
                    if dimension == "raw":
                        m.now_ns = m.caps[1] - remaining * NS
                    else:
                        m.local = m.clock.current().binding[6] - remaining
                    state = SimpleNamespace(clock=m.clock)
                    first = O.clocks.Reading(m.identity, m.now_ns)
                    with patch.object(O.clocks, "observe", lambda: first):
                        with self.assertRaisesRegex(Exception, "OPERATION_FITS_OR_REFUSE|OPERATION_LOCAL_INTERVAL"):
                            K._operation_caps(state, K.TailArchiveCaps)
                    self.assertIs(m.clock.caps, m.caps)

    def test_earlier_local_operation_finish_is_retained_and_strict(self):
        with ModelClock(self, "windows-x64") as m:
            state = SimpleNamespace(clock=m.clock)
            m.local = m.clock.current().binding[6] - 40
            first = O.clocks.Reading(m.identity, m.now_ns)
            with patch.object(O.clocks, "observe", lambda: first):
                caps = K._operation_caps(state, K.TailValidationCaps)
            self.assertEqual(caps.operationFinishEndLocal, m.clock.current().binding[6])
            self.assertLessEqual(caps.workEndLocal - caps.firstLocal, 10)
            self.assertEqual(caps.operationFinishEndNs, m.now_ns + 60 * NS)
            m.local = caps.operationFinishEndLocal
            with self.assertRaises(Exception):
                K._operation_current(state, caps, None)

    def test_new_join_placement_and_roster_substitutions_are_source_pinned_and_sticky(self):
        names = ("_original_read_expectations", "_phase_directory", "_phase_roster", "PRIVATE_DIRECTORIES",
            "PHASE_PLACEMENT", "DIRECTORIES", "PRIVATE_INPUT_NAMES", "PRIVATE_CLOSED_NAMES")
        for name in names:
            with self.subTest(name=name), ModelClock(self) as m:
                value = getattr(K, name)
                replacement = (lambda *_args, **_kwargs: None) if callable(value) else tuple(list(value))
                with patch.object(K, name, replacement):
                    with self.assertRaisesRegex(Exception, "ORIGINAL_SOURCE_SUPPLIER_CHANGED") as first:
                        m.clock.current()
                with self.assertRaises(Exception) as repeated:
                    m.clock.current()
                self.assertIs(first.exception, repeated.exception)

    def test_original_index_grammar_phase_labels_and_transport_limits_are_pinned(self):
        for kind in ("index-parser", "phase-labels", "transport-limit"):
            with self.subTest(kind=kind), ModelClock(self) as m:
                substitution = patch.object(RD, "authority_index", lambda *_args, **_kwargs: {}) if kind == "index-parser" else \
                    patch.object(TD, "PHASE_NAMES", tuple(list(TD.PHASE_NAMES))) if kind == "phase-labels" else \
                    patch.dict(K.INPUT_LIMITS, {"deadline.json": K.INPUT_LIMITS["deadline.json"] + 1})
                with substitution:
                    with self.assertRaisesRegex(Exception, "ORIGINAL_SOURCE_SUPPLIER_CHANGED") as first:
                        m.clock.current()
                with self.assertRaises(Exception) as repeated:
                    m.clock.current()
                self.assertIs(first.exception, repeated.exception)


if __name__ == "__main__":
    unittest.main()
