#!/usr/bin/env python3
"""Prefix-only controls, AUTHORED FOR REVIEW; not executed as source evidence.

Only the new compatibility fixture builders are imported; no test methods are
selected. DATA fixtures are deliberately synthetic; they are not authenticated C
prefixes, complete native custody, or successful Steps. The isolated owner/reader
models run the actual A machinery against memory resources and synthetic clocks,
with C's passive proof boundary explicitly substituted. They do not execute
produce/productive9, a native backend, a policy query, a key operation, provider,
archive, build or workflow.
38 original records +281 declarations remain distinct from281 native reads.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes  # Initialize before denying native loads, as in the existing model harness.
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED, SIDE_EFFECTS = False, []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        SIDE_EFFECTS.append(event)
        raise AssertionError("PREFIX_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_adapter as A

COMPAT_SPEC = importlib.util.spec_from_file_location("prefix_compatibility_fixtures",
    Path(__file__).with_name("hosted-cache-compatibility-test.py"))
COMPAT = importlib.util.module_from_spec(COMPAT_SPEC)
sys.modules[COMPAT_SPEC.name] = COMPAT
COMPAT_SPEC.loader.exec_module(COMPAT)

D, C, N, B, O, F = A.D, A.C, A.N, A.B, A.O, A.F
NS, BOOT = O.NS, "b" * 64
REFUSALS = (ValueError, RuntimeError)  # Never accept an audit AssertionError as a refusal.
SOURCE_NAMES = ("hosted_initial_recipient_productive_adapter.py", "hosted_initial_recipient_productive_data.py",
    "hosted_initial_recipient_productive.py", "run-hosted-initial-recipient-custody.py", "hosted_cache_provider_native.py")
TEXT = {name: (ROOT / "scripts" / name).read_text(encoding="utf-8") for name in SOURCE_NAMES}


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    count = len(SIDE_EFFECTS)
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous
        if len(SIDE_EFFECTS) != count:
            raise AssertionError("PREFIX_MODEL_SIDE_EFFECT")


def section(filename, start, end):
    raw = TEXT[filename]
    return raw[raw.index(start):raw.index(end, raw.index(start) + len(start))]


def clock():
    return O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)


def binding(number):
    return {"identity": [7, number], "stampSha256": "d" * 64}


def close_data(labels):
    return {"schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
        "resources": [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
            for number, label in enumerate(labels)],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


def data_fixture():
    """Shape-only DATA and MODEL source bytes, never a native or source-query call."""
    source_tree = COMPAT.ModelTree()
    # Separate MODEL public-source volume; original private pins stay unchanged.
    source_tree.identities = {name: (8, pin[1]) for name, pin in source_tree.identities.items()}
    compiled = F.authority.parse_allowlist(source_tree.raw[F.INPUTS[0]])
    seed = {"files": {name: O.digest(source_tree.raw[name]) for name in F.INPUTS},
        "allowlistSha256": compiled.authority_sha256, "artifacts": len(compiled.artifacts),
        "components": compiled.component_count, "policy": F.policy()}
    selected = {"seed": seed, "provider": {name: O.digest(source_tree.raw[name]) for name in
        A.compatibility.PROVIDER_INPUTS}}
    source = dict(COMPAT.SOURCE)
    compatibility_raw = A.compatibility.encoded(A.compatibility.envelope(source, selected))
    session, custody = Path("/model/initial"), Path("/model/primary-custody")
    initializer = tuple((name, (7, 10 + number), "ORIGINAL_INITIALIZER_NATIVE_PIN")
        for number, name in enumerate(D.INITIALIZER_DIRECTORIES))
    initial_raws = tuple((name, b"" if name.endswith(".log") else O.encoded({"original": name}))
        for name in D.INITIALIZER_FILES)
    primary_handoff, primary_inventory = b"synthetic-original-handoff", b"synthetic-original-inventory"
    members = []
    for number in range(1371):  # 1361 fixed disk originals +10 POSIX crypto declarations.
        members.append({"member": "member-" + str(number).zfill(5) + ".bin", "bytes": 1, "sha256": O.digest(b"x"),
            "origin": "PRIMARY", "original": "P/model-" + str(number), "originalMaximum": D.LIMIT,
            "provenance": "AUTHENTICATED_CRYPTO_DECLARATION" if number < 10 else "ACTUAL_RETAINED_BYTES",
            "carrier": "INDEXED_DISK_ORIGINAL", "destinationWriteMetadata": {"model": number}})
    for name, raw, carrier, provenance in (
        ("worker-originals.json", primary_handoff, "HANDOFF", "ACTUAL_PRIMARY_HANDOFF_DISK_BYTES"),
        ("receiving-authority-return.json", b"embedded-one", "EMBEDDED_NOT_DISK_ORIGINAL",
            "ORIGINAL_EMBEDDED_BYTES_FROM_EXACT_HANDOFF"),
        ("initialization-history.json", b"embedded-two", "EMBEDDED_NOT_DISK_ORIGINAL",
            "ORIGINAL_EMBEDDED_BYTES_FROM_EXACT_HANDOFF")):
        number = len(members)
        members.append({"member": "member-" + str(number).zfill(5) + ".bin", "bytes": len(raw), "sha256": O.digest(raw),
            "origin": "PRIMARY", "original": name, "provenance": provenance, "carrier": carrier,
            "destinationWriteMetadata": {"model": number}})
    copied = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_PRIMARY_COPY_V1", "origin": "PRIMARY", "members": members,
        "sourceMetadata": [[name, [True, list(pin), 0, {"model": name}]] for name, pin, _provenance in initializer],
        "originalDirectories": [{"relative": name, "identity": list(pin), "provenance": provenance}
            for name, pin, provenance in initializer],
        "handoffMetadata": [["", True, [7, 400], 0, {"model": "handoff"}],
            ["worker-originals.json", False, [7, 401], len(primary_handoff), {"model": "handoff-file"}]],
        "destination": str(custody / "copied-evidence"), "destinationIdentity": [7, 402],
        "destinationMetadata": [["", True, [7, 402], 0, {"model": "copy-root"}],
            *[[row["member"], False, [7, 500 + number], row["bytes"], {"model": number}]
                for number, row in enumerate(members)]],
        "memberCount": 1374, "nextOrdinal": 1374, "totalBytes": sum(row["bytes"] for row in members),
        "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE", "remainingOrigins": ["AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT"],
        "productiveAuthority": False, "currentAuthority": "NOT_ACQUIRED", "exportSaveAuthority": False}
    # Deliberately synthetic metadata makes this exact canonical map exceed
    # the maintained 1MiB caller block without changing any supplier limit.
    # All five-original/retirement/index hashes are constructed AFTER padding.
    target = F.BLOCK + 4096
    members[0]["destinationWriteMetadata"]["modelPadding"] = ""
    padding = target - len(O.encoded(copied))
    if padding <= 0:
        raise AssertionError("MODEL_MULTIBLOCK_PADDING_UNAVAILABLE")
    members[0]["destinationWriteMetadata"]["modelPadding"] = "p" * padding
    map_raw = O.encoded(copied)
    if len(map_raw) != target or not F.BLOCK < len(map_raw) <= D.LIMIT:
        raise AssertionError("MODEL_MULTIBLOCK_INPUT_BOUND")
    match = {"model": "not-an-authenticated-match"}
    pinned = (".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")
    authority = {"schema": 1, "scope": "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_INDEX_V1", "origin": "AUTHORITY_PRE_EXPORT",
        "root": str(custody / "authority-1"), "clock": O.clock_value(clock()), "contextSha256": "c" * 64,
        "matchSha256": O.digest(O.encoded(match)), "pendingSha256": "a" * 64,
        "files": [{"relative": "model-" + str(number), "maximum": D.LIMIT, "bytes": 1, "sha256": O.digest(b"x"),
            "provenance": "ACTUAL_RETAINED_BYTES" if number < 38 else "ORIGINAL_QUERY_DECLARATION"}
            for number in range(281)],
        "directories": [{"relative": name, "identity": [7, 3000 + number], "provenance": "ORIGINAL_NATIVE_PIN"}
            for number, name in enumerate(pinned)] + [{"relative": "declared-" + str(number), "identity": None,
                "provenance": "ORIGINAL_QUERY_DECLARATION"} for number in range(51)],
        "fileCount": 281, "directoryCount": 58, "totalBytes": 281, "copyState": "ORIGINAL_BYTES_NOT_COPIED",
        "exportSaveAuthority": False}
    original = {"primary-map.json": map_raw, "primary-preliminary-close.json": O.encoded(close_data(["reader"])),
        "primary-native-close.json": O.encoded(close_data(["writer", "reader"])), "authority-index.json": O.encoded(authority)}
    closed = {"schema": 1, "scope": "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_CLOSED_HISTORY_V1", "windowSha256": "e" * 64,
        "primaryResultSha256": "f" * 64, "primaryCopySha256": O.digest(original["primary-map.json"]),
        "matchSha256": authority["matchSha256"], "inventorySha256": O.digest(original["authority-index.json"]),
        "pendingSha256": authority["pendingSha256"], "originalChain": {}, "preCloseNs": 80 * NS, "closedNs": 85 * NS,
        "resourceCount": 38, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED",
        "exportSaveAuthority": False}
    original["authority-return.json"] = O.encoded(closed)
    input_close = close_data(["directory", *("reader",) * 3, "directory", *("reader",) * 7,
        "directory", "reader", "directory", "reader"])
    retired = {"schema": 1, "scope": D.RETIRED_SCOPE, "clock": O.clock_value(clock()), "originalBootDigest": BOOT,
        "primaryResultSha256": closed["primaryResultSha256"], "primaryCopySha256": closed["primaryCopySha256"],
        "authoritySha256": O.digest(original["authority-return.json"]), "authorityInventorySha256": closed["inventorySha256"],
        "workerIdentitySha256": "1" * 64, "originalProposalSha256": "2" * 64, "initializer": str(session),
        "initializerFilesSha256": {name: O.digest(raw) for name, raw in initial_raws}, "inputOwnerClose": input_close,
        "inputsClosedNs": 90 * NS, "originalPrepWorkEndNs": 99 * NS, "prepDisposition": "TERMINALLY_RETIRED",
        "receivingDisposition": "HISTORICAL_NOT_REVIVED", "currentAuthority": "NEW_PER_USE_REQUIRED",
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    inputs = SimpleNamespace(role="linux-x64", clock=clock(), session=session, initializer_directories=initializer,
        initializer_originals=initial_raws, closed_raw=O.encoded(retired), previous_ns=95 * NS,
        previous_local=995.0, root=Path("/model/source"),
        history={"originalBootDigest": BOOT}, admission={"initialRecipient": match, "source": source, "github": {},
            "selection": "model", "cacheCohort": "model"},
        directories={name: dict((key, pin) for key, pin, _provenance in initializer)[key]
            for name, key in zip(D.DIRECTORY_NAMES, D.DIRECTORY_KEYS)},
        stage={"containerIdentity": [7, 4000], "sourceIdentity": [7, 4001]},
        stage_value={"inputs": seed, "bootstrapInputs": {}},
        proposal={"phaseFencesNs": {"producer-owner-return": 200 * NS}, "proposedJobEndNs": 200 * NS},
        binding=lambda: {"scope": D.INPUT_SCOPE, "model": "closed-input-binding"})
    index = D.prefix_retention_value(original, inputs, custody, O.digest(primary_inventory))
    raws = {name: original[name] for name in D.PREFIX_FILES[:-1]}
    raws["retention-index.json"] = O.encoded(index)
    reference = {"schema": 1, "scope": D.PREFIX_REFERENCE_SCOPE, "directory": str(custody / "productive-prefix"),
        "directoryIdentity": [7, 20000], "directoryBinding": binding(20000), "custodyDirectoryIdentity": [7, 20001],
        "retiredPrefixSha256": O.digest(inputs.closed_raw), "files": {name: {"bytes": len(raws[name]),
            "sha256": O.digest(raws[name]), "fileBinding": binding(21000 + number)}
            for number, name in enumerate(D.PREFIX_FILES)}}
    return SimpleNamespace(inputs=inputs, original=original, raws=raws, reference=reference, index=index, custody=custody,
        primary_handoff=primary_handoff, primary_inventory=primary_inventory,
        roots={"P": Path("/model/primary"), "I": session}, source_tree=source_tree, compatibility_raw=compatibility_raw)


def handoff_fixture(data, reference=None, directory_identity=(7, 22000)):
    inputs = data.inputs
    blobs = {name: b"" if name == "ancestry_raw.bin" else O.encoded({"model": name}) for name in D.BLOB_NAMES}
    blobs["initial-inputs.json"] = O.encoded({"schema": 2, "scope": D.OUTER_INPUT_SCOPE,
        "binding": inputs.binding(), "initializerCheckedLocal": inputs.previous_local,
        "compatibilityInputs": D.canonical(data.compatibility_raw)})
    returns = {}
    for phase, label in zip(D.PRODUCTIVE_PHASES, ("stage", "seed", "custody", "producer", "collection", "no-loader", "export", "before")):
        leaf_name = "producer-observation.json" if phase == "configuration" else label + "-leaf.json"
        returns[phase] = {"rawSha256": O.digest(blobs[label + "-parent.json"]), "checkedNs": 99 * NS,
            "checkedLocal": 999.0, "leaf": {"rawSha256": O.digest(blobs[leaf_name]), "checkedNs": 98 * NS,
                "localStarted": 998.0, "checkedLocal": 998.5}}
    returns["before"] = returns["save-set-before"]
    value = {"schema": 2, "scope": D.HANDOFF_SCOPE, "binding": inputs.binding(),
        **{name: inputs.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
        "plan": {}, "planSha256": O.digest(O.encoded({})), "directory": str(inputs.session / "dependency-save-handoff"),
        "directoryIdentity": list(directory_identity), "blobs": {name: {"bytes": len(raw), "sha256": O.digest(raw)}
            for name, raw in blobs.items()}, "references": {"initializerFiles": {}, "staging": {}, "phaseOriginals": {},
            "prefixRetention": data.reference if reference is None else reference},
        "chain": {"scope": "INITIAL_RECIPIENT_ORIGINAL_PRODUCTIVE_CLOSED_CHAIN_V1", "returns": returns,
            "referenceScope": "RETAINED_ORIGINAL_BINDINGS_NOT_PROVIDER_OR_STEP_RESULT"},
        "window": {"phase": "producer-owner-return", "clock": O.clock_value(inputs.clock), "originalBootDigest": BOOT,
            "firstNs": 100 * NS, "localStarted": 1000.0, "hardEndNs": 145 * NS, "predecessorCheckedNs": 99 * NS,
            "predecessorSha256": O.digest(blobs["before-parent.json"])}, "writerReturn": D.PENDING,
        "providerExecution": "NOT_PERFORMED", "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    return value, blobs


def relink_originals(data, originals):
    """Keep synthetic DATA hashes coherent so a negative reaches its predicate.

    This never supplies an original C return or its actual known-close proof.
    """
    inputs = copy.copy(data.inputs)
    retired, closed = D.canonical(inputs.closed_raw), D.canonical(originals["authority-return.json"])
    closed["primaryCopySha256"] = retired["primaryCopySha256"] = O.digest(originals["primary-map.json"])
    closed["inventorySha256"] = retired["authorityInventorySha256"] = O.digest(originals["authority-index.json"])
    originals["authority-return.json"] = O.encoded(closed)
    retired["authoritySha256"] = O.digest(originals["authority-return.json"])
    inputs.closed_raw = O.encoded(retired)
    return inputs


class PrefixDataControls(unittest.TestCase):
    def setUp(self):
        self.data = guarded(data_fixture)

    def record(self, raws=None, reference=None):
        data = self.data
        return guarded(D.prefix_retention_record, data.raws if raws is None else raws,
            data.reference if reference is None else reference, data.inputs, data.custody)

    def changed_index(self, change):
        raws, reference = dict(self.data.raws), copy.deepcopy(self.data.reference)
        value = copy.deepcopy(self.data.index)
        change(value)
        raws["retention-index.json"] = O.encoded(value)
        reference["files"]["retention-index.json"].update(bytes=len(raws["retention-index.json"]),
            sha256=O.digest(raws["retention-index.json"]))
        return raws, reference

    def test_fixed_six_records_remain_pending_not_native_custody(self):
        result = self.record()
        self.assertEqual(tuple(self.data.raws), D.PREFIX_FILES)
        self.assertEqual(result["primary"]["memberCount"], 1364 + 10)
        self.assertEqual(result["authority"]["fileCount"], 281)
        self.assertEqual(result["authority"]["retainedOriginalCount"], 38)
        self.assertEqual(result["custodyScope"], "RECORD_RETENTION_ONLY_NOT_NATIVE_CUSTODY")
        self.assertEqual(result["writerReturn"], D.PENDING)

    def test_missing_extra_and_oversize_sidecars_are_not_optional(self):
        for name in D.PREFIX_FILES:
            with self.subTest(name=name):
                missing = dict(self.data.raws)
                missing.pop(name)
                with self.assertRaises(REFUSALS):
                    self.record(missing)
                maximum = D.PREFIX_INDEX_LIMIT if name == "retention-index.json" else D.LIMIT
                oversized = {**self.data.raws, name: b"x" * (maximum + 1)}
                with self.assertRaises(REFUSALS):
                    self.record(oversized)
        with self.assertRaises(REFUSALS):
            self.record({**self.data.raws, "extra.json": b"{}"})

    def test_a_hash_string_cannot_replace_any_original_raw(self):
        for name in D.PREFIX_FILES[:-1]:
            with self.subTest(name=name), self.assertRaises(REFUSALS):
                self.record({**self.data.raws, name: O.encoded({"sha256": O.digest(self.data.raws[name])})})

    def test_reference_path_fields_aliases_and_role_are_strict(self):
        changes = (lambda value: value.update(directory="/model/elsewhere"),
            lambda value: value.update(extra=True), lambda value: value["files"].pop(D.PREFIX_FILES[0]),
            lambda value: value["files"][D.PREFIX_FILES[0]].update(bytes=True),
            lambda value: value.update(directoryIdentity=[7, 10], directoryBinding=binding(10)),
            lambda value: value["files"][D.PREFIX_FILES[0]].update(fileBinding=binding(20000)),
            lambda value: value["files"][D.PREFIX_FILES[0]]["fileBinding"].update(identity=[7, "1" * 32]))
        for number, change in enumerate(changes):
            reference = copy.deepcopy(self.data.reference)
            change(reference)
            with self.subTest(number=number), self.assertRaises(REFUSALS):
                self.record(reference=reference)

    def test_retention_index_cannot_attest_writer_step_or_export_success(self):
        changes = (lambda value: value.update(writerReturn="success"),
            lambda value: value.update(producerStepOutcome="success"),
            lambda value: value.update(exportSaveAuthority=True),
            lambda value: value.update(custodyScope="281_NATIVE_READS"),
            lambda value: value["retirement"].update(currentAuthority="RESTORED"))
        for number, change in enumerate(changes):
            with self.subTest(number=number), self.assertRaises(REFUSALS):
                self.record(*self.changed_index(change))

    def test_both_original_primary_close_rosters_are_required(self):
        for name in ("primary-preliminary-close.json", "primary-native-close.json"):
            originals = dict(self.data.original)
            value = D.canonical(originals[name])
            value["resources"][0]["closed"] = False
            originals[name] = O.encoded(value)
            with self.subTest(name=name), self.assertRaises(REFUSALS):
                guarded(D.prefix_retention_value, originals, self.data.inputs, self.data.custody, "a" * 64)

    def test_absent_or_wrong_authentic_primary_copy_root_is_refused(self):
        for change, reason in ((lambda value: value.pop("destinationMetadata"), "FIELDS"),
            (lambda value: value.update(destination="/model/other-copy"), "PREFIX_PRIMARY_MAP"),
            (lambda value: value["destinationMetadata"].__setitem__(0, ["", True, [7, 999], 0, {}]),
                "PREFIX_AUTHENTIC_COPY_ROOT")):
            originals = dict(self.data.original)
            value = D.canonical(originals["primary-map.json"])
            change(value)
            originals["primary-map.json"] = O.encoded(value)
            inputs = guarded(relink_originals, self.data, originals)
            with self.subTest(reason=reason), self.assertRaisesRegex(REFUSALS, reason):
                guarded(D.prefix_retention_value, originals, inputs, self.data.custody, "a" * 64)

    def test_malformed_primary_rows_fail_as_data_not_incidental_type_errors(self):
        for field, reason in (("members", "PREFIX_PRIMARY_MEMBER_ROW"),
            ("destinationMetadata", "PREFIX_AUTHENTIC_COPY_ROOT")):
            originals = dict(self.data.original)
            value = D.canonical(originals["primary-map.json"])
            value[field][0] = 17
            originals["primary-map.json"] = O.encoded(value)
            inputs = guarded(relink_originals, self.data, originals)
            with self.subTest(field=field), self.assertRaisesRegex(REFUSALS, reason):
                guarded(D.prefix_retention_value, originals, inputs, self.data.custody, "a" * 64)

    def test_authority_original38_never_becomes_a_claim_of281_native_reads(self):
        originals = dict(self.data.original)
        value = D.canonical(originals["authority-index.json"])
        for row in value["files"]:
            row["provenance"] = "ACTUAL_RETAINED_BYTES"
        originals["authority-index.json"] = O.encoded(value)
        inputs = guarded(relink_originals, self.data, originals)
        with self.assertRaisesRegex(REFUSALS, "PREFIX_AUTHORITY_DECLARATIONS_NOT_CUSTODY"):
            guarded(D.prefix_retention_value, originals, inputs, self.data.custody, "a" * 64)

    def test_authority_directory_declarations_do_not_create_additional_native_pins(self):
        for change, reason in ((lambda rows: rows[7].update(identity=[7, 99999]), "PREFIX_AUTHORITY_DIRECTORY"),
            (lambda rows: rows[7].update(relative=rows[8]["relative"]), "PREFIX_AUTHORITY_DIRECTORY_ROSTER")):
            originals = dict(self.data.original)
            value = D.canonical(originals["authority-index.json"])
            change(value["directories"])
            originals["authority-index.json"] = O.encoded(value)
            inputs = guarded(relink_originals, self.data, originals)
            with self.subTest(reason=reason), self.assertRaisesRegex(REFUSALS, reason):
                guarded(D.prefix_retention_value, originals, inputs, self.data.custody, "a" * 64)

    def test_v2_handoff_requires_sidecar_and_rejects_old_schema(self):
        value, blobs = guarded(handoff_fixture, self.data)
        first = O.clocks.Reading(clock(), 150 * NS)
        def check(value):
            raw = O.encoded(value)
            return guarded(D.handoff_record, raw, blobs, self.data.inputs, first,
                {"PRODUCER_OUTCOME": "success", "HANDOFF_SHA256": O.digest(raw)},
                self.data.inputs.session / "dependency-save-handoff", (7, 22000), custody=self.data.custody)
        self.assertEqual(check(value)["schema"], 2)
        for change in (lambda row: row.update(schema=1,
                scope="INITIAL_RECIPIENT_SAVE_HANDOFF_PENDING_ORIGINAL_STEP_RETURN_V1"),
            lambda row: row["references"].pop("prefixRetention"),
            lambda row: row["references"]["prefixRetention"]["files"].pop("retention-index.json")):
            bad = copy.deepcopy(value)
            change(bad)
            with self.assertRaises(REFUSALS):
                check(bad)


@dataclass(frozen=True)
class Info:
    identity: tuple
    is_directory: bool
    size: int
    generation: int

    def as_dict(self):
        return {"identity": list(self.identity), "is_directory": self.is_directory,
            "size": self.size, "generation": self.generation}


class Node:
    def __init__(self, path, identity, directory, raw=b""):
        self.path, self.identity, self.directory, self.raw = path, identity, directory, raw
        self.generation = 0

    def info(self):
        return Info(self.identity, self.directory, 0 if self.directory else len(self.raw), self.generation)


class MemoryResource:
    def __init__(self, fs, node):
        self.fs, self.node, self.path, self.identity = fs, node, node.path, node.identity
        self.closed, self.closes = False, 0
        fs.handles.append(self)

    def verify(self):
        if self.closed or self.fs.nodes.get(self.path) is not self.node:
            raise RuntimeError("MODEL_ORIGINAL_RESOURCE_CHANGED")
        return self.node.info()

    def close(self):
        self.closes += 1
        self.fs.on_close(self)
        self.closed = True


class MemoryFile(MemoryResource):
    def __init__(self, fs, node, maximum, writable):
        super().__init__(fs, node)
        self.maximum, self.writable, self.position = maximum, writable, 0
        self.initial_info = node.info()

    def verify(self):
        info = super().verify()
        if info.size > self.maximum or not self.writable and info != self.initial_info:
            raise RuntimeError("MODEL_FILE_CHANGED")
        return info

    def read(self, size):
        if self.writable or not 0 <= size <= F.BLOCK:
            raise RuntimeError("MODEL_READ_MODE")
        self.verify()
        part = self.node.raw[self.position:self.position + size]
        self.position += len(part)
        return part

    def write(self, raw):
        if not self.writable or not 0 < len(raw) <= F.BLOCK or len(self.node.raw) + len(raw) > self.maximum:
            raise RuntimeError("MODEL_WRITE_BLOCK_OR_LIMIT")
        self.fs.on_write(self, raw)
        self.node.raw += raw
        self.node.generation += 1
        self.fs.write_blocks.append((self.path, len(raw)))
        return len(raw)

    def sync(self):
        self.verify()
        self.fs.on_sync(self)


class MemoryDirectory(MemoryResource):
    def names(self, *, max_names, deadline):
        self.verify()
        names = tuple(sorted(path.name for path in self.fs.nodes if path.parent == self.path))
        if len(names) > max_names:
            raise RuntimeError("MODEL_DIRECTORY_LIMIT")
        return names

    def create_directory(self, name, *, deadline):
        self.verify()
        node = self.fs.add(self.path / name, directory=True)
        return MemoryDirectory(self.fs, node)

    def open_directory(self, name, *, deadline):
        self.verify()
        return self.fs.private_root(self.path / name)

    def create_file(self, name, *, max_bytes, deadline):
        self.verify()
        self.fs.before_create(self.path / name)
        node = self.fs.add(self.path / name, directory=False)
        stream = MemoryFile(self.fs, node, max_bytes, True)
        self.fs.on_create(stream)
        return stream

    def open_file(self, name, *, max_bytes, deadline):
        self.verify()
        path = self.path / name
        node = self.fs.nodes.get(path)
        if node is None or node.directory or len(node.raw) > max_bytes:
            raise RuntimeError("MODEL_FILE_NOT_BOUNDED")
        self.fs.reads.append((path, max_bytes))
        return MemoryFile(self.fs, node, max_bytes, False)


class MemoryFiles:
    def __init__(self):
        self.nodes, self.handles, self.reads, self.write_blocks = {}, [], [], []
        self.serial = 30000
        self.before_create = lambda _path: None
        self.on_create = lambda _stream: None
        self.on_write = lambda _stream, _raw: None
        self.on_sync = lambda _stream: None
        self.on_close = lambda _resource: None

    def add(self, path, *, directory, raw=b"", identity=None):
        if path in self.nodes:
            raise RuntimeError("MODEL_EXCLUSIVE_CREATE")
        self.serial += 1
        node = Node(path, (7, self.serial) if identity is None else identity, directory, raw)
        self.nodes[path] = node
        if path.parent in self.nodes:
            self.nodes[path.parent].generation += 1
        return node

    def private_root(self, path, *, create=False):
        if create:
            self.add(path, directory=True)
        node = self.nodes.get(path)
        if node is None or not node.directory:
            raise RuntimeError("MODEL_FIXED_DIRECTORY_REQUIRED")
        return MemoryDirectory(self, node)

    def replace_file(self, path, *, preserve_parent_stamp=False):
        old, generation = self.nodes[path], self.nodes[path.parent].generation
        del self.nodes[path]
        self.add(path, directory=False, raw=old.raw)
        if preserve_parent_stamp:
            # Stronger adversarial model: unchanged directory stamp still
            # cannot excuse changed file identity with equal file bytes.
            self.nodes[path.parent].generation = generation


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class EqualityMethodImpostor:
    """Callable that would lie to a tuple's equality comparison."""
    def __init__(self):
        self.equal_calls, self.call_calls = 0, 0

    def __eq__(self, _other):
        self.equal_calls += 1
        return True

    def __call__(self, *_args, **_kwargs):
        self.call_calls += 1
        raise AssertionError("MODEL_IMPOSTOR_METHOD_INVOKED")


class PrefixMemoryControls(unittest.TestCase):
    """Isolated final-phase model, NOT a substitute for productive9 or C proof."""
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.data = guarded(data_fixture)
        self.fs = MemoryFiles()
        self.raw, self.local = 100 * NS, 1000.0
        self.proofs = {name: True for name in ("primary", "authority", "inputs", "retired")}
        self.proof_calls = 0
        primary = SimpleNamespace(roots=tuple(self.data.roots.items()), inventory_raw=self.data.primary_inventory,
            handoff_raw=self.data.primary_handoff, result_sha256="f" * 64)
        self.prefix = SimpleNamespace(raw=self.data.inputs.closed_raw, initializer=self.data.inputs.session,
            history=O.encoded(self.data.inputs.history), primary=SimpleNamespace(primary=primary,
                copy=self.data.original["primary-map.json"], preliminary_close=self.data.original["primary-preliminary-close.json"],
                native_close=self.data.original["primary-native-close.json"]),
            authority=SimpleNamespace(raw=self.data.original["authority-return.json"],
                inventory=self.data.original["authority-index.json"]))
        for name in ("_RUNS", "_PARENTS", "_WINDOWS", "_OWNERS", "_RETURNS", "_HANDOFFS", "_READERS", "_INPUTS",
            "_DERIVES", "_OUTPUTS", "_PINS", "_RUN_LATCHES", "_FAILURES", "_CHILD_RETURNS", "_OWNER_RETURNS", "_LEAF_RETURNS"):
            self.stack.enter_context(patch.object(A, name, {}))
        self.stack.enter_context(patch.object(A, "_environment", lambda _run: None))
        self.stack.enter_context(patch.object(time, "monotonic", lambda: self.local))
        self.stack.enter_context(patch.object(O.clocks, "observe", lambda: O.clocks.Reading(clock(), self.raw)))
        self.stack.enter_context(patch.object(N.continuity, "boot_digest", lambda _role: BOOT))
        self.stack.enter_context(patch.object(B, "QUARANTINE", []))
        self.stack.enter_context(patch.object(C, "checked_retired_primary", self.passive_prefix))
        self.stack.enter_context(patch.object(C, "checked_primary", side_effect=AssertionError("RETIRED_PRIMARY_REVIVAL")))
        self.stack.enter_context(patch.object(C, "checked_custody_authority", side_effect=AssertionError("RETIRED_AUTHORITY_REVIVAL")))
        self.stack.enter_context(patch.object(C, "_paths", lambda _kind: (self.data.roots,
            self.data.inputs.session.with_name("initial-handoff"), self.data.custody)))
        self.stack.enter_context(patch.object(F, "private_root", self.fs.private_root))
        self.stack.enter_context(patch.object(F, "PosixFile", COMPAT.ModelFile))
        self.stack.enter_context(patch.object(F, "PosixSourceDirectory", COMPAT.ModelDirectory))
        self.stack.enter_context(patch.object(F, "public_root", side_effect=lambda _root:
            COMPAT.ModelDirectory(self.data.source_tree, ())))
        for name, identity, _provenance in self.data.inputs.initializer_directories:
            self.fs.add(self.data.inputs.session.joinpath(*name.split("/")[1:]), directory=True, identity=identity)
        for number, (name, raw) in enumerate(self.data.inputs.initializer_originals):
            self.fs.add(self.data.inputs.session.joinpath(*name.split("/")[1:]), directory=False,
                raw=raw, identity=(7, 4100 + number))
        self.fs.add(self.data.custody, directory=True, identity=(7, 20001))
        self.run = guarded(A._new_run, "produce", lambda: None, self.prefix)
        self.state = guarded(self.synthetic_phase)

    def passive_prefix(self, value):
        self.proof_calls += 1
        if value is not self.prefix or not all(self.proofs.values()):
            raise RuntimeError("MODEL_C_PASSIVE_ORIGINAL_CLOSE_REFUSED")
        return value

    def synthetic_phase(self):
        # Only the existing producer-owner-return interval is modeled. No
        # productive use/phase, original C return, or remote Step is fabricated.
        first, parent, window = O.clocks.Reading(clock(), self.raw), A._Parent(), A._Window()
        hard = self.raw + 45 * NS
        end = O.wire._directed_deadline(self.local, 45, hard, self.raw)
        state = A._track(A._ParentState(parent, self.run, "producer-owner-return", first, self.local, BOOT,
            None, None, N._history_graph(first), (hard,), (end,), window,
            starts=((self.raw, self.local, hard, end),), last=self.raw, last_reading=first,
            local_last=self.local, issued=end))
        A._PARENTS[id(parent)], A._WINDOWS[id(window)] = state, state
        A._progress(self.run, current=state)
        return state

    def pending(self):
        owner = A._new_owner(self.state)
        methods = A._prefix_writer_methods(owner)
        A._read_initializer(self.state, self.data.inputs)
        retained, reference_raw = A._retain_prefix(self.state, self.prefix, self.data.inputs)
        compatibility_raw = A._capture_compatibility(owner, self.data.inputs)
        if compatibility_raw != self.data.compatibility_raw:
            raise AssertionError("MODEL_ORIGINAL_SOURCE_INVENTORY")
        initial = A._directory(owner, self.data.inputs.session, self.data.inputs.directories["session"])
        directory = owner.child(initial, "dependency-save-handoff", create=True)
        value, blobs = handoff_fixture(self.data, D.canonical(reference_raw), tuple(directory.identity))
        raw = O.encoded(value)
        for name, blob in (*blobs.items(), ("save-handoff.json", raw)):
            A._write_blob(owner, directory, name, blob)
        A._names(owner, directory, (*D.BLOB_NAMES, "save-handoff.json"))
        for name, blob in (*blobs.items(), ("save-handoff.json", raw)):
            if owner.read(directory, name) != blob:
                raise AssertionError("MODEL_ORIGINAL_HANDOFF_READBACK")
        A._names(owner, directory, (*D.BLOB_NAMES, "save-handoff.json"))
        if (tuple(directory.verify().identity) != tuple(value["directoryIdentity"]) or
                tuple(initial.verify().identity) != self.data.inputs.directories["session"]):
            raise AssertionError("MODEL_ORIGINAL_HANDOFF_DIRECTORIES")
        if A._capture_compatibility(owner, self.data.inputs) != compatibility_raw:
            raise AssertionError("MODEL_ORIGINAL_SOURCE_CHANGED")
        A._prefix_writer_methods_current(owner, methods)
        if A._prefix_raws(self.prefix) != tuple((name, raw) for name, raw, _binding in retained[:-1]):
            raise AssertionError("MODEL_ORIGINAL_PREFIX_CHANGED")
        owner.close()
        A._known(owner)
        self.state.window.now()
        result = A.PendingHandoff(raw, self.state.last, self.state.local_last)
        saved = A._track(A._HandoffState(result, self.state, self.prefix, directory.path,
            tuple(directory.identity), self.data.inputs.directories["session"],
            N._history_graph(result.__dict__, self.run.initial_files), tuple(blobs.items()),
            retained, reference_raw, owner, methods))
        A._HANDOFFS[id(result)] = saved
        return result, saved  # Actual model function return; not A.produce/native acceptance.

    def reader(self):
        pending, saved = self.pending()
        owner = A._new_owner(self.state)
        reader = A._reader_state(owner, self.state.first, {name: "MODEL" for name in A._BASE_CLAIMS})
        A._READERS[id(owner)] = reader
        handoff = A.HandoffInputs(pending.raw, None, b"{}", b"{}", (), self.data.inputs.session,
            self.data.inputs.directories["session"], b"{}", saved.blobs, None)
        A._progress(reader, handoff=handoff)
        A._read_prefix_retention(reader, D.canonical(saved.prefix_reference), self.data.inputs)
        inputs = SimpleNamespace(inputs=self.data.inputs, source_inputs=self.data.inputs.stage_value["inputs"],
            compatibility_raw=self.data.compatibility_raw)
        return reader, inputs

    def test_original_first448_preserves_private144_second21_same45_and_prior_close_only(self):
        pending, saved = guarded(self.pending)
        resources = guarded(A._known, saved.writer).resources
        self.assertEqual(len(resources), 448)
        private = (*resources[:46], *resources[198:296])
        # These are the original private objects, not fabricated ledger rows;
        # compare before completion adds its separate21 private handles.
        self.assertEqual((len(private), len(self.fs.handles)), (144, 144))
        self.assertTrue(all(pin.value is handle for pin, handle in zip(private, self.fs.handles)))
        labels = list(A.compatibility.source_read_labels())
        self.assertEqual(len(labels), 152)
        self.assertEqual([pin.label for pin in resources[46:198]], labels)
        self.assertEqual([pin.label for pin in resources[296:448]], labels)
        self.assertTrue(all(pin.value.close_calls == 1 for pin in (*resources[46:198], *resources[296:448])))
        self.assertFalse(any(first.value is second.value for first in resources[46:198] for second in resources[296:448]))
        self.assertEqual(self.data.source_tree.opened, [*F.INPUTS, *A.compatibility.PROVIDER_INPUTS] * 2)
        self.assertGreater(len(self.data.original["primary-map.json"]), F.BLOCK)
        self.assertLessEqual(len(self.data.original["primary-map.json"]), D.LIMIT)
        self.assertEqual(len(self.data.original["primary-map.json"]), F.BLOCK + 4096)
        blocks = [size for path, size in self.fs.write_blocks if path.name == "primary-map.json"]
        self.assertGreater(len(blocks), 1)
        self.assertTrue(all(0 < size <= F.BLOCK for size in blocks))
        self.assertEqual(blocks, [F.BLOCK, 4096])
        self.assertEqual(sum(blocks), len(self.data.original["primary-map.json"]))
        frame = self.state.first, self.state.local, self.state.ends, self.state.local_ends
        result = guarded(A.complete_productive_handoff, pending, self.prefix)
        first_owner, second_owner = self.state.owners
        self.assertIs(first_owner, saved.writer)
        self.assertEqual(len(guarded(A._known, second_owner).resources), 21)
        self.assertIs(first_owner.first, second_owner.first)
        self.assertEqual((self.state.first, self.state.local, self.state.ends, self.state.local_ends), frame)
        self.assertEqual(result.hard_end_ns, frame[2][0])
        returned = guarded(D.producer_return_record, saved.return_raw, pending.raw, self.data.inputs,
            O.clocks.Reading(clock(), 150 * NS), O.digest(saved.return_raw), saved.identity)
        self.assertEqual(returned["priorWriterClose"]["resourceCount"], 448)
        self.assertEqual(returned["priorWriterClose"]["observationScope"], "PRIOR_FIRST_OWNER_ONLY")
        self.assertEqual(returned["recordWriterReturn"], D.PENDING)
        self.assertEqual(returned["producerStepOutcome"], D.PENDING)
        self.assertTrue(all(handle.closes == 1 for handle in self.fs.handles))

    def test_completed_model_record_cannot_self_attest_current_writer_or_step(self):
        pending, saved = guarded(self.pending)
        guarded(A.complete_productive_handoff, pending, self.prefix)
        original = D.canonical(saved.return_raw)
        changes = (lambda value: value.update(recordWriterReturn="success"),
            lambda value: value.update(producerStepOutcome="success"),
            lambda value: value.update(observationScope="CURRENT_COMMAND_RETURNED"),
            lambda value: value.update(exportSaveAuthority=True),
            lambda value: value.update(currentWriterClose=value["priorWriterClose"]),
            lambda value: value.update(schema=1, scope="INITIAL_RECIPIENT_HANDOFF_FUNCTION_RETURN_PENDING_COMMAND_V1"),
            lambda value: value.pop("priorWriterClose"), lambda value: value.pop("prefixRetention"))
        for number, change in enumerate(changes):
            value = copy.deepcopy(original)
            change(value)
            raw = O.encoded(value)
            with self.subTest(number=number), self.assertRaises(REFUSALS):
                guarded(D.producer_return_record, raw, pending.raw, self.data.inputs,
                    O.clocks.Reading(clock(), 150 * NS), O.digest(raw), saved.identity)

    def test_current_second21_close_cannot_replace_the_prior_first448_close(self):
        pending, saved = guarded(self.pending)
        guarded(A.complete_productive_handoff, pending, self.prefix)
        second = guarded(A._known, self.state.owners[1])
        value = D.canonical(saved.return_raw)
        value["priorWriterClose"].update(resourceCount=len(second.resources),
            resources=[{"ordinal": number, "label": pin.label, "closeAttempted": pin.attempted, "closed": pin.closed}
                for number, pin in enumerate(second.resources)])
        raw = O.encoded(value)
        with self.assertRaisesRegex(REFUSALS, "PREFIX_PRIOR_WRITER_ROWS"):
            guarded(D.producer_return_record, raw, pending.raw, self.data.inputs,
                O.clocks.Reading(clock(), 150 * NS), O.digest(raw), saved.identity)

    def test_prior_first_close_keeps_exact_owner_frame_roster_and_known_flags(self):
        pending, saved = guarded(self.pending)
        guarded(A.complete_productive_handoff, pending, self.prefix)
        original = D.canonical(saved.return_raw)
        changes = (lambda row: row.update(ownerOrdinal=1), lambda row: row.update(firstNs=101 * NS),
            lambda row: row.update(localStarted=1001.0), lambda row: row.update(hardEndNs=146 * NS),
            lambda row: row.update(observationScope="CURRENT_COMPLETION_OWNER"),
            lambda row: row.update(prefixRetentionSha256="0" * 64),
            lambda row: row["resources"][0].update(closed=False),
            lambda row: row["resources"][0].update(closeAttempted=False),
            lambda row: row["resources"][0].update(ordinal=1),
            lambda row: row["resources"][0].update(label="invented-close"))
        for number, change in enumerate(changes):
            value = copy.deepcopy(original)
            change(value["priorWriterClose"])
            raw = O.encoded(value)
            with self.subTest(number=number), self.assertRaises(REFUSALS):
                guarded(D.producer_return_record, raw, pending.raw, self.data.inputs,
                    O.clocks.Reading(clock(), 150 * NS), O.digest(raw), saved.identity)
        value = copy.deepcopy(original)
        value["priorWriterClose"]["resourceCount"] = 446
        raw = O.encoded(value)
        with self.assertRaisesRegex(REFUSALS, "PREFIX_PRIOR_WRITER_ROWS"):
            guarded(D.producer_return_record, raw, pending.raw, self.data.inputs,
                O.clocks.Reading(clock(), 150 * NS), O.digest(raw), saved.identity)

    def test_function_return_cannot_substitute_an_equal_shaped_sidecar_reference(self):
        pending, saved = guarded(self.pending)
        guarded(A.complete_productive_handoff, pending, self.prefix)
        value = D.canonical(saved.return_raw)
        value["prefixRetention"]["files"]["primary-map.json"]["fileBinding"] = binding(99999)
        raw = O.encoded(value)
        with self.assertRaisesRegex(REFUSALS, "FUNCTION_RETURN_PREFIX_BINDING"):
            guarded(D.producer_return_record, raw, pending.raw, self.data.inputs,
                O.clocks.Reading(clock(), 150 * NS), O.digest(raw), saved.identity)

    def test_c_passive_primary_authority_input_and_retirement_refusals_precede_writes(self):
        owner = guarded(A._new_owner, self.state)
        for name in self.proofs:
            self.proofs[name] = False
            with self.subTest(name=name), self.assertRaises(REFUSALS):
                guarded(A._retain_prefix, self.state, self.prefix, self.data.inputs)
            self.proofs[name] = True
        self.assertEqual(A._OWNER_RETURNS[id(owner)], ())
        self.assertEqual(self.fs.write_blocks, [])

    def test_wrong_pending_or_prefix_cannot_supply_the_registered_handoff(self):
        pending, _saved = guarded(self.pending)
        with self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, copy.copy(pending), self.prefix)
        with self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, pending, copy.copy(self.prefix))
        self.assertEqual(len(self.state.owners), 1)

    def test_first_writer_owner_replacement_is_not_an_equal_known_close(self):
        pending, saved = guarded(self.pending)
        owner = saved.writer
        saved.writer = copy.copy(owner)
        with self.assertRaises(REFUSALS) as first:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        saved.writer = owner
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIs(first.exception, repeated.exception)

    def test_first_writer_ledger_change_and_restoration_cannot_erase_refusal(self):
        pending, saved = guarded(self.pending)
        ledger = saved.writer.resources
        saved.writer.resources = list(ledger)
        with self.assertRaises(REFUSALS) as first:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        saved.writer.resources = ledger
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIs(first.exception, repeated.exception)

    def test_first_writer_method_is_pinned_across_its_actual_return(self):
        pending, saved = guarded(self.pending)
        with patch.object(A._Owner, "close", lambda _owner: None), self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIsNone(saved.result)
        self.assertEqual(len(self.state.owners), 1)

    def test_writer_methods_require_fixed_tuple_identity_before_first_close(self):
        owner = guarded(A._new_owner, self.state)
        methods = guarded(A._prefix_writer_methods, owner)
        for malformed in (list(methods), methods[:-1], (*methods, methods[-1])):
            with self.subTest(shape=type(malformed), size=len(malformed)), self.assertRaisesRegex(
                    REFUSALS, "PREFIX_ORIGINAL_WRITER_METHODS_CHANGED"):
                guarded(A._prefix_writer_methods_current, owner, malformed)
        for target, name in (*((A._Owner, name) for name in ("acquire", "read", "write", "end", "close_one", "close")),
                (A, "_known")):
            impostor = EqualityMethodImpostor()
            with self.subTest(method=name), patch.object(target, name, impostor), self.assertRaisesRegex(
                    REFUSALS, "PREFIX_ORIGINAL_WRITER_METHODS_CHANGED"):
                guarded(A._prefix_writer_methods_current, owner, methods)
            self.assertEqual((impostor.equal_calls, impostor.call_calls), (0, 0))
            self.assertFalse(owner.closed)
        guarded(A._prefix_writer_methods_current, owner, methods)
        guarded(owner.close)
        self.assertEqual(len(guarded(A._known, owner).resources), 0)

    def test_callable_equality_cannot_impersonate_first_writer_during_completion(self):
        pending, saved = guarded(self.pending)
        impostor = EqualityMethodImpostor()
        with patch.object(A._Owner, "close", impostor), self.assertRaisesRegex(
                REFUSALS, "PREFIX_ORIGINAL_WRITER_METHODS_CHANGED") as first:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertEqual((impostor.equal_calls, impostor.call_calls), (0, 0))
        self.assertIsNone(saved.result)
        self.assertEqual(len(self.state.owners), 1)
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIs(first.exception, repeated.exception)

    def test_sidecar_replacement_between_completion_reads_refuses_equal_bytes(self):
        pending, saved = guarded(self.pending)
        path = self.data.custody / "productive-prefix" / "primary-map.json"
        before = len(self.fs.reads)
        def replace_on_return_write(stream):
            if stream.path.name == "producer-function-return.json":
                self.fs.replace_file(path, preserve_parent_stamp=True)
        self.fs.on_sync = replace_on_return_write
        with self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, pending, self.prefix)
        prefix_reads = [target.name for target, _maximum in self.fs.reads[before:] if target.parent == path.parent]
        self.assertEqual(prefix_reads[:6], list(D.PREFIX_FILES))
        self.assertEqual(prefix_reads[6:], ["primary-map.json"])
        self.assertIsNone(saved.result)
        self.assertTrue(saved.writer.closed)

    def test_missing_sidecar_file_is_not_recreated_by_completion(self):
        pending, saved = guarded(self.pending)
        path = self.data.custody / "productive-prefix" / "authority-return.json"
        del self.fs.nodes[path]
        with self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertNotIn(path, self.fs.nodes)
        self.assertIsNone(saved.result)

    def test_extra_sidecar_file_is_not_a_new_accepted_roster(self):
        pending, saved = guarded(self.pending)
        self.fs.add(self.data.custody / "productive-prefix" / "extra.json", directory=False, raw=b"{}")
        with self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIsNone(saved.result)

    def test_extra_handoff_file_cannot_be_the_six_file_sidecar(self):
        pending, saved = guarded(self.pending)
        owner = guarded(A._new_owner, self.state)
        directory = guarded(A._directory, owner, saved.path, saved.identity)
        self.fs.add(saved.path / "retention-index.json", directory=False, raw=b"{}")
        with self.assertRaises(REFUSALS):
            guarded(A._names, owner, directory, (*D.BLOB_NAMES, "save-handoff.json"))
        self.assertEqual(len(D.BLOB_NAMES) + 1, 32)
        self.assertIsNone(saved.result)

    def test_raw_expiry_cannot_start_a_new_completion45(self):
        pending, saved = guarded(self.pending)
        self.raw = self.state.ends[0]
        with self.assertRaises(REFUSALS) as first:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.raw = 100 * NS
        with self.assertRaises(REFUSALS) as repeated:
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIs(first.exception, repeated.exception)
        self.assertIsNone(saved.result)

    def test_local_expiry_cannot_restart_local_after_the_handoff_return(self):
        pending, saved = guarded(self.pending)
        self.local = self.state.local_ends[0]
        with self.assertRaises(REFUSALS):
            guarded(A.complete_productive_handoff, pending, self.prefix)
        self.assertIsNone(saved.result)
        self.assertEqual(len(self.state.owners), 1)

    def test_first_falsey_write_error_survives_unknown_actual_writer_close(self):
        owner = guarded(A._new_owner, self.state)
        root = guarded(A._directory, owner, self.data.custody)
        directory = guarded(owner.child, root, "productive-prefix", create=True)
        first, close_error = FalseyFailure("FIRST_WRITE"), RuntimeError("UNKNOWN_CLOSE")
        def fail_write(_stream, _raw):
            raise first
        def fail_close(resource):
            if type(resource) is MemoryFile and resource.writable:
                raise close_error
        self.fs.on_write, self.fs.on_close = fail_write, fail_close
        with self.assertRaises(REFUSALS) as failed:
            guarded(A._write_prefix_file, owner, directory, "primary-map.json", b"x")
        self.assertIs(failed.exception, first)
        self.assertIs(owner.original, first)
        self.assertTrue(owner.unknown)
        self.assertEqual(owner.resources[-1]["owner"].closes, 1)
        self.assertTrue(owner.resources[-1]["attempted"])
        self.assertFalse(owner.resources[-1]["closed"])
        with self.assertRaises(REFUSALS):
            guarded(A._known, owner)

    def test_late_actual_writer_return_stays_retained_for_abort_cleanup(self):
        owner = guarded(A._new_owner, self.state)
        root = guarded(A._directory, owner, self.data.custody)
        directory = guarded(owner.child, root, "productive-prefix", create=True)
        self.fs.on_create = lambda _stream: setattr(self, "raw", self.state.ends[0])
        with self.assertRaises(REFUSALS) as failed:
            guarded(A._write_prefix_file, owner, directory, "primary-map.json", b"x")
        stream = self.fs.handles[-1]
        self.assertIs(A._OWNER_RETURNS[id(owner)][-1][1], stream)
        self.assertFalse(owner.unknown)
        self.assertIs(guarded(A._abort, self.state, failed.exception), failed.exception)
        self.assertEqual(stream.closes, 1)
        self.assertIsNone(self.run.terminal)

    def test_allocation_exception_without_actual_return_stays_unknown(self):
        owner = guarded(A._new_owner, self.state)
        root = guarded(A._directory, owner, self.data.custody)
        directory = guarded(owner.child, root, "productive-prefix", create=True)
        original = RuntimeError("MODEL_ALLOCATION_DID_NOT_RETURN")
        def fail_before_return(_path):
            raise original
        self.fs.before_create = fail_before_return
        with self.assertRaises(REFUSALS) as failed:
            guarded(A._write_prefix_file, owner, directory, "primary-map.json", b"x")
        self.assertIs(failed.exception, original)
        self.assertTrue(owner.unknown)
        self.assertEqual(len(A._OWNER_RETURNS[id(owner)]), 2)
        self.assertEqual([row["label"] for row in owner.resources], ["directory", "directory"])
        self.assertIs(guarded(A._abort, self.state, original), original)
        self.assertTrue(any(value is owner for value in B.QUARANTINE))
        with self.assertRaises(REFUSALS):
            guarded(A._known, owner)

    def test_every_recheck_really_rereads_all_six_original_native_files(self):
        reader, inputs = guarded(self.reader)
        path = self.data.custody / "productive-prefix"
        self.assertEqual(set(reader.files), {(path, name) for name in D.PREFIX_FILES})
        self.assertEqual(set(reader.directories), {self.data.custody, path})
        before = len(self.fs.reads)
        # Deliberate prefix-only source DATA seam, not source/native acceptance.
        with patch.object(A, "_current_source_inputs", return_value=(inputs.source_inputs, {},
                inputs.inputs.stage_value["bootstrapInputs"], inputs.compatibility_raw)):
            guarded(A._recheck_inputs, reader, inputs, ())
            guarded(A._recheck_inputs, reader, inputs, ())
        self.assertEqual([target.name for target, _maximum in self.fs.reads[before:]], list(D.PREFIX_FILES) * 2)
        self.assertEqual([maximum for _target, maximum in self.fs.reads[before:]],
            [D.LIMIT] * 5 + [D.PREFIX_INDEX_LIMIT] + [D.LIMIT] * 5 + [D.PREFIX_INDEX_LIMIT])

    def test_a_source_owned_read_map_update_cannot_omit_a_sidecar(self):
        reader, inputs = guarded(self.reader)
        path = self.data.custody / "productive-prefix"
        omitted = dict(reader.files)
        omitted.pop((path, "primary-map.json"))
        guarded(A._progress, reader, files=omitted)
        with patch.object(A, "_current_source_inputs", return_value=(inputs.source_inputs, {},
                inputs.inputs.stage_value["bootstrapInputs"], inputs.compatibility_raw)), self.assertRaises(REFUSALS):
            guarded(A._recheck_inputs, reader, inputs, ())

    def test_same_bytes_with_a_new_native_file_binding_fail_recheck(self):
        reader, inputs = guarded(self.reader)
        self.fs.replace_file(self.data.custody / "productive-prefix" / "primary-map.json", preserve_parent_stamp=True)
        with patch.object(A, "_current_source_inputs", return_value=(inputs.source_inputs, {},
                inputs.inputs.stage_value["bootstrapInputs"], inputs.compatibility_raw)), self.assertRaises(REFUSALS):
            guarded(A._recheck_inputs, reader, inputs, ())

    def test_same_identity_with_changed_sidecar_root_stamp_fails_recheck(self):
        reader, inputs = guarded(self.reader)
        self.fs.nodes[self.data.custody / "productive-prefix"].generation += 1
        with patch.object(A, "_current_source_inputs", return_value=(inputs.source_inputs, {},
                inputs.inputs.stage_value["bootstrapInputs"], inputs.compatibility_raw)), self.assertRaises(REFUSALS):
            guarded(A._recheck_inputs, reader, inputs, ())


class PrefixSourceControls(unittest.TestCase):
    """Textual attachment guards, not execution of private/public native sites."""
    def ordered(self, body, *needles):
        previous = -1
        for needle in needles:
            at = body.index(needle, previous + 1)
            self.assertGreater(at, previous)
            previous = at

    def adapter(self, start, end):
        return section("hosted_initial_recipient_productive_adapter.py", start, end)

    def test_prefix_supplier_is_only_the_passive_original_c_close_boundary(self):
        supplier = self.adapter("def _prefix_raws(", "def _prefix_writer_methods(")
        self.assertIn("C.checked_retired_primary(prefix) is prefix", supplier)
        for raw in ("prefix.primary.copy", "prefix.primary.preliminary_close", "prefix.primary.native_close",
            "prefix.authority.raw", "prefix.authority.inventory"):
            self.assertIn(raw, supplier)
        for forbidden in ("C.checked_primary(", "C.checked_custody_authority(", ".now(", ".current("):
            self.assertNotIn(forbidden, supplier)
        passive = section("run-hosted-initial-recipient-custody.py", "def checked_retired_primary(", "def _copy_authority(")
        for required in ("_PRODUCTIVE_PREFIX_RETURNS.get(id(result))", "_RETIRED_PRODUCTIVE_WINDOWS.get(id(window)) is result",
            "wrapper.structural()", "authority_saved[7].known()", "primary_saved[9]", "owner.structural()",
            'original_attempt["state"] == "RETURNED"', "entry.returned(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt, result)"):
            self.assertIn(required, passive)
        self.assertNotIn("window.now(", passive)
        self.assertNotIn("window.current(", passive)

    def test_real_produce_persists_after_original_use_and_before_unchanged_handoff_roster(self):
        body = self.adapter("def produce(", "def _names(")
        self.ordered(body, '_new_phase(run, "producer-owner-return",', "owner = _new_owner(state)",
            "writer_methods = _prefix_writer_methods(owner)", '_use(state, "producer-handoff/retention", token)',
            "_read_initializer(state, inputs)", "_retain_prefix(state, prefix, inputs)",
            "compatibility_raw = _capture_compatibility(owner, inputs)",
            "_handoff_blobs(state, inputs, prefix_reference, compatibility_raw)",
            '"HANDOFF_ORIGINAL_READBACK_CHANGED"', '"HANDOFF_DIRECTORY_CHANGED"',
            "require(_capture_compatibility(owner, inputs) == compatibility_raw",
            "_prefix_writer_methods_current(owner, writer_methods)",
            "owner.close()", "_known(owner)",
            "result = PendingHandoff(", "_prefix_writer(saved)", "return result")
        self.assertEqual(body.count("_capture_compatibility("), 2)
        writer = self.adapter("def _prefix_writer_methods_current(", "def _prefix_writer_close(")
        self.assertIn("type(current) is tuple and type(original) is tuple", writer)
        self.assertIn("len(current) == len(original) == 8", writer)
        self.assertIn("all(actual is saved for actual, saved in zip(current, original))", writer)
        self.assertIn("_prefix_writer_methods_current(owner, saved.writer_methods)", writer)
        self.assertIn('(*D.BLOB_NAMES, "save-handoff.json")', body)
        names = self.adapter("def _names(", "def _write_blob(")
        self.assertIn("directory.names(max_names=32, deadline=end)", names)
        self.assertEqual(len(D.BLOB_NAMES), 31)
        self.assertFalse(set(D.PREFIX_FILES).intersection((*D.BLOB_NAMES, "save-handoff.json")))

    def test_real_completion_keeps_two_original_native_read_passes_and_same_first45(self):
        body = self.adapter("def complete_productive_handoff(", "def checked_productive_handoff(")
        self.ordered(body, "saved = _pending(pending, prefix)", "prior_close = O.encoded(_prefix_writer_close(saved))",
            "state.window.now(minimum=pending.checked_ns)", "owner = _new_owner(state)",
            "_reread_prefix(owner, root, sidecar, saved.prefix_files, saved.prefix_reference)",
            'owner.write(initial, "producer-function-return.json", raw)',
            "_reread_prefix(owner, root, sidecar, saved.prefix_files, saved.prefix_reference)",
            "owner.close()", "_known(owner)", "_pending(pending, prefix)", "_register_output(state, result, raw)", "return result")
        self.assertEqual(body.count("_reread_prefix("), 2)
        self.assertEqual(body.count("_new_owner(state)"), 1)
        self.assertNotIn("_new_phase(", body)
        self.assertNotIn("time.monotonic(", body)
        self.assertIn('"recordWriterReturn": D.PENDING', body)
        self.assertIn('"producerStepOutcome": D.PENDING', body)
        productive = TEXT["hosted_initial_recipient_productive.py"]
        self.ordered(productive, "pending = adapter.produce(prefix, token, cancelled)",
            "completed = adapter.complete_productive_handoff(pending, prefix)",
            "result = adapter.checked_productive_handoff(completed, prefix)")

    def test_shared_handoff_graph_and_every_repeat_require_six_actual_file_reads(self):
        graph = self.adapter("def _read_productive_graph(", "def read_productive_handoff(")
        self.assertIn('"initializerFiles staging phaseOriginals prefixRetention"', graph)
        self.assertIn('_read_prefix_retention(reader, refs["prefixRetention"], inputs)', graph)
        actual = self.adapter("def _read_prefix_retention(", "def _prefix_reader_check(")
        self.assertIn('_read_root(reader, custody_path, reference["custodyDirectoryIdentity"])', actual)
        self.assertIn('_read_root(reader, path, reference["directoryIdentity"])', actual)
        self.assertIn("_read_file(reader, path, name,", actual)
        self.assertIn("for name in D.PREFIX_FILES", actual)
        self.assertIn("D.prefix_retention_record(raws, reference, inputs, custody_path)", actual)
        shared = self.adapter("def read_productive_handoff(", "def _checked_handoff(")
        self.ordered(shared, "D.handoff_record(", "D.producer_return_record(", "_read_productive_graph(",
            "_prefix_reader_check(reader)", "checked_handoff_inputs(owner, result)")
        self.assertIn('custody=C._paths("worker")[2]', shared)
        repeat = self.adapter("def _recheck_inputs(", "def _step_path(")
        self.ordered(repeat, "_prefix_reader_check(reader)", "in tuple(reader.files.items()):",
            "_read_file(reader, path, name, maximum, expected=raw, binding=binding)", "_prefix_reader_check(reader)")
        mandatory = self.adapter("def _prefix_reader_check(", "def _read_productive_graph(")
        self.assertIn("custody_path in reader.directories and path in reader.directories", mandatory)
        self.assertIn("key in reader.files", mandatory)
        self.assertIn("_prefix_directory_check(", mandatory)

    def test_all_four_private_steps_remain_attached_to_the_shared_reader_and_fresh_begin(self):
        private = self.adapter("def _start_step(", "def _write_private_chain(")
        self.assertIn("handoff = read_productive_handoff(owner, state.first, run.claims)", private)
        self.ordered(private, 'identity = _use(state, state.run.operation + "/begin", token)',
            "rederive_provider_inputs(state.owner, state.run.prefix, identity)",
            'identity = _use(state, state.run.operation + "/final", token)', "recheck_provider_inputs(state.owner, inputs)")
        prepared = self.adapter("def _prepare_step(", "def after_save(")
        saved = self.adapter("def after_save(", "def after_probe(")
        probed = TEXT["hosted_initial_recipient_productive_adapter.py"].split("def after_probe(", 1)[1]
        for name, body in (("prepare-save/prepare-probe", prepared), ("after-save", saved), ("after-probe", probed)):
            with self.subTest(name=name):
                self.ordered(body, "_start_step(run)", "_step_inputs(state, token)", "_step_final_use(state, inputs, token)")
        self.assertEqual(set(D.STEP_PHASES), {"prepare-save", "after-save", "prepare-probe", "after-probe"})
        derive = self.adapter("def rederive_provider_inputs(", "def _reader_failure(")
        self.ordered(derive, "_DERIVES[id(handoff)] =", "_fresh_begin(reader, fresh_identity)",
            "return _rederive_inputs(reader, fresh_identity)")
        fresh = self.adapter("def _fresh_begin(", "def _rederive_inputs(")
        for required in ("ACTUAL_STEP_BEGIN_REQUIRED", "ACTUAL_PROVIDER_BEGIN_REQUIRED",
            "SAME_AUTHENTIC_CONSUMED_BEGIN_REQUIRED", "P.checked_consumed_use(result, parent, site) is result"):
            self.assertIn(required, fresh)
        rederive = self.adapter("def _rederive_inputs(", "def recheck_provider_inputs(")
        self.assertIn("recheck_provider_inputs(owner, result)", rederive)

    def test_both_public_provider_sites_keep_actual_begin_materializer_final_and_shared_recheck(self):
        provider = section("hosted_cache_provider_native.py", "def _initial_graph(", "def operate(")
        self.ordered(provider, "adapter.read_productive_handoff(owner, first, claims)",
            'admitted = _initial_use(parent, "begin")', "adapter.rederive_provider_inputs(owner, handoff, admitted)",
            "def final_readback(materialized):", 'final = _initial_use(parent, "final")',
            "adapter.recheck_provider_inputs(owner, inputs)")
        self.assertIn('"provider-save" if phase == "save" else "provider-probe"', provider)
        self.assertIn("adapter.validate_provider_preparation(owner, handoff, inputs, phase, claims,", provider)
        actions = self.adapter("def _action_originals(", "def _after_save_history(")
        for required in ("readback.ACTION_FILES", "readback.INITIAL_USE_FILES", "readback.validate_initial_action_return(",
            "_read_use("):
            self.assertIn(required, actions)


if __name__ == "__main__":
    unittest.main()
