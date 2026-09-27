"""Closed initial productive/Step DATA, never an original owner or authority.

No native controller is loaded here. Supplied identities, histories, paths and
consistent records cannot supply a current use, producer, Step or provider.
The fixed adapter separately owns original reads/returns and irreversible use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re

import hosted_cache_bootstrap_allocation as allocation
import hosted_cache_bootstrap_initialization as initialization
import hosted_cache_compatibility as compatibility
import hosted_dependency_seed_files as files
import hosted_initial_recipient_bootstrap_identity as identity


O = allocation.origin
ROOT = Path(__file__).resolve().parents[1]
LIMIT = 2 * 1024 * 1024
SOURCE_KEYS = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
INITIALIZER_DIRECTORIES = ("I", "I/canonical-init", "I/control-home", "I/temporary", "I/state",
    "I/state/gradle-home", "I/state/evidence", "I/state/cancellations")
INITIALIZER_FILES = ("I/receiving-window.json", "I/initializer-context.json", "I/initialization-pending.json",
    *("I/canonical-init/" + name for name in
      ("baseline.json", "native-start.json", "request.json", "result.json", "start.json", "stderr.log", "stdout.log")),
    "I/state/context.json", "I/state/gradle-home/gradle.properties")
DIRECTORY_NAMES = ("session", "state", "gradle-home", "evidence", "cancellations")
DIRECTORY_KEYS = ("I", "I/state", "I/state/gradle-home", "I/state/evidence", "I/state/cancellations")
HISTORY_FIELDS = "schema scope kind observed clock originalBootDigest originalPreviousNs originalJobBasisNs " \
    "serviceArithmetic serviceJob firstUseAt matchSha256 originalLocalScope primaryStepScope currentAuthority " \
    "budgetAcceptance exportSaveAuthority"
RETIRED_SCOPE = "INITIAL_RECIPIENT_PRIMARY_RETIRED_FOR_PRODUCTIVE_V1"
INITIAL_CONTEXT_SCOPE = "INITIAL_RECIPIENT_CANONICAL_INITIALIZER_CONTEXT_V1"
INPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_ORIGINAL_INPUT_BINDING_V1"
OUTER_INPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_ORIGINAL_INPUTS_WITH_COMPATIBILITY_V2"
STAGING_PARENT_SCOPE = "INITIAL_RECIPIENT_STAGING_PARENT_CLOSED_NO_EXECUTION_V1"
PARENT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PARENT_CLOSED_OBSERVATIONS_V1"
HANDOFF_SCOPE = "INITIAL_RECIPIENT_SAVE_HANDOFF_PENDING_ORIGINAL_STEP_RETURN_V2"
RETURN_SCOPE = "INITIAL_RECIPIENT_HANDOFF_FUNCTION_RETURN_PENDING_COMMAND_V2"
PREFIX_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PREFIX_PENDING_WRITER_RETURN_V1"
PREFIX_REFERENCE_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PREFIX_NATIVE_REFERENCE_V1"
PREFIX_WRITER_CLOSE_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRIOR_WRITER_CLOSE_V1"
PREFIX_FILES = ("primary-map.json", "primary-preliminary-close.json", "primary-native-close.json",
    "authority-return.json", "authority-index.json", "retention-index.json")
PREFIX_INDEX_LIMIT = 64 * 1024
OUTPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCER_PENDING_ORIGINAL_STEP_RETURN_V1"
SAVE_PREPARATION_SCOPE = "INITIAL_RECIPIENT_BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"
PROBE_PREPARATION_SCOPE = "INITIAL_RECIPIENT_BOOTSTRAP_PROBE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"
STEP_CLOSE_SCOPE = "INITIAL_RECIPIENT_STEP_ORIGINAL_OWNER_CLOSE_V1"
STEP_CHAIN_SCOPE = "INITIAL_RECIPIENT_STEP_PRIVATE_USE_CHAIN_PENDING_OWNER_CLOSE_V1"
AFTER_SAVE_SCOPE = "INITIAL_RECIPIENT_AFTER_SAVE_PENDING_ORIGINAL_STEP_RETURN_V1"
SAVE_OBSERVATIONS_SCOPE = "INITIAL_RECIPIENT_AFTER_SAVE_OBSERVATIONS_PENDING_WRITER_RETURN_V1"
PROBE_RESULT_SCOPE = "INITIAL_RECIPIENT_PROBE_PENDING_ORIGINAL_STEP_RETURN_V1"
STEP_USE_FILES = ("private-use-chain.json", "begin-use.json", "begin-use-index.json",
                  "final-use.json", "final-use-index.json")
AFTER_SAVE_FILES = (*STEP_USE_FILES, "after-leaf.json", "save-preparation.json", "provider-save.json",
                    "readmission-close.json", "after-parent-close.json", "provider-prepared.json", "provider-readback.json")
SAVE_CLAIMS = ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARE_OUTCOME",
               "SAVE_PREPARATION_SHA256", "SAVE_OUTCOME", "SAVE_READBACK_SHA256")
STEP_CAPS = {"save-transition": (30, 30), "probe-transition": (30, 30),
    "save-readmission": (120, 120), "custody-readmission": (120, 120), "save-set-after": (120, 90),
    "save-observation": (30, 30), "save-owner-return": (45, 45), "provider-observation": (30, 30)}
STEP_PHASES = {"prepare-save": "save-transition", "after-save": "save-readmission",
               "prepare-probe": "probe-transition", "after-probe": "custody-readmission"}
BLOB_NAMES = tuple(name + ".json" for name in (
    "stage-parent", "stage-leaf", "seed-parent", "seed-leaf", "custody-parent", "custody-leaf", "custody-request",
    "producer-parent", "producer-request", "producer-observation", "producer-command", "producer-native",
    "collection-parent", "collection-leaf", "collection-inventory", "no-loader-parent", "no-loader-leaf",
    "export-parent", "export-leaf", "before-parent", "before-leaf", "retired-prefix", "worker-identity",
    "history", "allocation-proposal")) + tuple(name + ".bin" for name in SOURCE_KEYS) + (
    "initial-inputs.json", "productive-use-index.json")
PENDING = "PENDING_NOT_OBSERVABLE_BY_THIS_FILE"
# Additional initial-origin provenance only. The ordinary source roster and
# dependency/provider keys are untouched; these hashes grant no current use.
INITIAL_SOURCE_INPUTS = tuple("scripts/" + name for name in (
    "hosted_initial_recipient_productive.py", "hosted_initial_recipient_use.py",
    "hosted_initial_recipient_productive_adapter.py", "hosted_initial_recipient_productive_data.py",
    "run-hosted-initial-recipient.py", "run-hosted-initial-recipient-custody.py",
    "hosted_initial_recipient_before.py", "hosted_initial_recipient_continuity.py",
    "hosted_initial_recipient_public_origin.py", "hosted_cache_provider_native.py",
    "hosted_cache_provider_prepare.py", "hosted_cache_provider_readback.py",
    "hosted_initial_recipient_productive_custody.py", "hosted_initial_recipient_productive_custody_data.py",
    "hosted_initial_recipient_evidence.py", "hosted_evidence.py", "hosted_windows_evidence.py",
    "run-hosted-initial-recipient-productive.py", "run-hosted-cache-bootstrap.py"))
PRODUCTIVE_PHASES = ("dependency-stage", "empty-seed", "custody-prepare", "configuration", "custody-collect",
                    "custody-uninstall", "dependency-export", "save-set-before")
PREPARATION_FIELDS = "schema scope source github selection cacheCohort directory directoryIdentity handoffSha256 " \
    "producerReturnSha256 producerOriginalOutcome workerIdentitySha256 privateUseChainSha256 proposalSha256 plan " \
    "planSha256 clock originalBootDigest firstNs hardEndNs producerObservedAfterReturnNs providerWindow providerRequest " \
    "writerReturn providerExecution budgetAcceptance testAcceptance exportSaveAuthority"


def nonacceptance(value):
    require(value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
        value["exportSaveAuthority"] is False, "NONACCEPTANCE")


def prefix_reference(value, inputs, custody):
    """Fixed historical DATA reference. A separately opens the derived path."""
    fields(value, "schema scope directory directoryIdentity directoryBinding custodyDirectoryIdentity "
        "retiredPrefixSha256 files")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == PREFIX_REFERENCE_SCOPE and
        value["directory"] == str(custody / "productive-prefix") and
        value["retiredPrefixSha256"] == O.digest(inputs.closed_raw) and
        files._file_binding(value["directoryBinding"]) and type(value["files"]) is dict and
        set(value["files"]) == set(PREFIX_FILES), "PREFIX_REFERENCE")
    pin = native_identity(value["directoryIdentity"], inputs.role)
    require(pin == native_identity(value["directoryBinding"]["identity"], inputs.role), "PREFIX_ROOT_BINDING")
    pins = [pin, native_identity(value["custodyDirectoryIdentity"], inputs.role)]
    for name in PREFIX_FILES:
        row = fields(value["files"][name], "bytes sha256 fileBinding")
        maximum = PREFIX_INDEX_LIMIT if name == "retention-index.json" else LIMIT
        require(type(row["bytes"]) is int and 0 < row["bytes"] <= maximum and
            files._file_binding(row["fileBinding"]), "PREFIX_FILE_REFERENCE")
        sha(row["sha256"])
        pins.append(native_identity(row["fileBinding"]["identity"], inputs.role))
    require(len(set(pins)) == 8 and not set(pins).intersection(
        pin for _name, pin, _provenance in inputs.initializer_directories), "PREFIX_NATIVE_ALIAS")
    return value


def prefix_directory_pins(originals, role):
    """Original map metadata only, not a filesystem snapshot or C capability."""
    copied, authority = canonical(originals["primary-map.json"]), canonical(originals["authority-index.json"])
    source = copied["sourceMetadata"]
    require(type(source) is list and 0 < len(source) <= 10000 and all(type(row) is list and len(row) == 2 and
        type(row[0]) is str and type(row[1]) is list and len(row[1]) == 4 for row in source), "PREFIX_SOURCE_METADATA")
    rows = [[name, *metadata] for name, metadata in source]
    for name in ("handoffMetadata", "destinationMetadata"):
        require(type(copied[name]) is list and 0 < len(copied[name]) <= 10000, "PREFIX_COPY_METADATA")
        rows.extend(copied[name])
    pins = []
    for row in rows:
        require(type(row) is list and len(row) == 5 and type(row[0]) is str and type(row[1]) is bool and
            type(row[3]) is int and row[3] >= 0 and type(row[4]) is dict, "PREFIX_METADATA_ROW")
        pin = native_identity(row[2], role)
        if row[1]:
            pins.append(pin)
    for row in authority["directories"]:
        fields(row, "relative identity provenance")
        if row["identity"] is not None:
            pins.append(native_identity(row["identity"], role))
    return tuple(pins)


def _prefix_close(raw):
    value = fields(canonical(raw), "schema scope resources retirement exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1" and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["exportSaveAuthority"] is False and
        type(value["resources"]) is list and 0 < len(value["resources"]) <= 10000, "PREFIX_PRIMARY_CLOSE")
    for ordinal, row in enumerate(value["resources"]):
        fields(row, "ordinal label closeAttempted closed")
        require(type(row["ordinal"]) is int and row["ordinal"] == ordinal and
            row["label"] in ("directory", "reader", "writer", "snapshot", "embedded-reader") and
            row["closeAttempted"] is True and row["closed"] is True, "PREFIX_PRIMARY_CLOSE_ROW")


def prefix_retention_value(originals, inputs, custody, primary_inventory_sha256):
    """Bind the five supplied ORIGINAL records, never reconstruct native custody.

    Only A's same registered C prefix can supply these bytes to the writer.
    Readers authenticate this DATA through the handoff/function/Step chain;
    they do not recreate C owners, reread the changed PRIMARY source tree, or
    promote the authority index's 281 declarations to 281 native reads.
    """
    require(type(originals) is dict and set(originals) == set(PREFIX_FILES[:-1]), "PREFIX_ORIGINAL_ROSTER")
    hashes = {name: {"bytes": len(raw_bytes(originals[name])), "sha256": O.digest(originals[name])}
        for name in PREFIX_FILES[:-1]}
    retired = canonical(inputs.closed_raw)
    copied = fields(canonical(originals["primary-map.json"]), "schema scope origin members sourceMetadata "
        "originalDirectories handoffMetadata destination destinationIdentity destinationMetadata memberCount totalBytes "
        "nextOrdinal freeze remainingOrigins productiveAuthority currentAuthority exportSaveAuthority")
    require(type(copied["schema"]) is int and copied["schema"] == 1 and
        copied["scope"] == "INITIAL_RECIPIENT_CUSTODY_PRIMARY_COPY_V1" and copied["origin"] == "PRIMARY" and
        copied["destination"] == str(custody / "copied-evidence") and
        copied["freeze"] == "NOT_FINAL_THREE_ORIGIN_FREEZE" and
        copied["remainingOrigins"] == ["AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT"] and
        copied["productiveAuthority"] is False and copied["currentAuthority"] == "NOT_ACQUIRED" and
        copied["exportSaveAuthority"] is False and type(copied["members"]) is list and
        type(copied["memberCount"]) is type(copied["nextOrdinal"]) is int and
        copied["memberCount"] == copied["nextOrdinal"] == len(copied["members"]) and
        hashes["primary-map.json"]["sha256"] == retired["primaryCopySha256"], "PREFIX_PRIMARY_MAP")
    native_identity(copied["destinationIdentity"], inputs.role)
    crypto_count = 0
    for ordinal, row in enumerate(copied["members"]):
        require(type(row) is dict, "PREFIX_PRIMARY_MEMBER_ROW")
        fields(row, "member bytes sha256 origin original provenance carrier destinationWriteMetadata" +
            (" originalMaximum" if row.get("carrier") == "INDEXED_DISK_ORIGINAL" else ""))
        require(row["member"] == "member-" + str(ordinal).zfill(5) + ".bin" and row["origin"] == "PRIMARY" and
            type(row["bytes"]) is int and 0 <= row["bytes"] <= 512 * 1024 * 1024 and
            type(row["original"]) is str and type(row["destinationWriteMetadata"]) is dict, "PREFIX_PRIMARY_MEMBER")
        sha(row["sha256"])
        crypto_count += row["provenance"] == "AUTHENTICATED_CRYPTO_DECLARATION"
    require((crypto_count == 9 if inputs.role == "windows-x64" else 10 <= crypto_count <= 74) and
        copied["memberCount"] == 1364 + crypto_count and type(copied["totalBytes"]) is int and
        copied["totalBytes"] == sum(row["bytes"] for row in copied["members"]) <= 512 * 1024 * 1024,
        "PREFIX_PRIMARY_COUNTS")
    handoff = copied["members"][-3]
    require(all(row["carrier"] == "INDEXED_DISK_ORIGINAL" for row in copied["members"][:-3]) and
        handoff["carrier"] == "HANDOFF" and handoff["original"] == "worker-originals.json" and
        handoff["provenance"] == "ACTUAL_PRIMARY_HANDOFF_DISK_BYTES" and
        [row["original"] for row in copied["members"][-2:]] ==
        ["receiving-authority-return.json", "initialization-history.json"] and
        all(row["carrier"] == "EMBEDDED_NOT_DISK_ORIGINAL" for row in copied["members"][-2:]), "PREFIX_PRIMARY_CARRIERS")
    destination = copied["destinationMetadata"]
    require(type(destination) is list and len(destination) == copied["memberCount"] + 1 and
        all(type(row) is list and len(row) == 5 for row in destination) and
        destination[0][:3] == ["", True, copied["destinationIdentity"]] and
        [row[:2] for row in destination[1:]] == [[row["member"], False] for row in copied["members"]],
        "PREFIX_AUTHENTIC_COPY_ROOT")
    for name in ("primary-preliminary-close.json", "primary-native-close.json"):
        _prefix_close(originals[name])
    retired_input_close(retired["inputOwnerClose"])
    authority = fields(canonical(originals["authority-index.json"]), "schema scope origin root clock contextSha256 "
        "matchSha256 pendingSha256 files directories fileCount directoryCount totalBytes copyState exportSaveAuthority")
    require(type(authority["schema"]) is int and authority["schema"] == 1 and
        authority["scope"] == "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_INDEX_V1" and
        authority["origin"] == "AUTHORITY_PRE_EXPORT" and authority["root"] == str(custody / "authority-1") and
        authority["clock"] == O.clock_value(inputs.clock) and authority["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and
        authority["exportSaveAuthority"] is False and type(authority["fileCount"]) is int and authority["fileCount"] == 281 and
        type(authority["files"]) is list and len(authority["files"]) == 281 and
        type(authority["directoryCount"]) is int and authority["directoryCount"] == 58 and
        type(authority["directories"]) is list and len(authority["directories"]) == 58, "PREFIX_AUTHORITY_INDEX")
    for row in authority["files"]:
        fields(row, "relative maximum bytes sha256 provenance")
        require(type(row["relative"]) is str and type(row["maximum"]) is type(row["bytes"]) is int and
            0 <= row["bytes"] <= row["maximum"] <= LIMIT and row["maximum"] > 0 and
            row["provenance"] in ("ACTUAL_RETAINED_BYTES", "ORIGINAL_QUERY_DECLARATION"), "PREFIX_AUTHORITY_FILE")
        sha(row["sha256"])
    require(len({row["relative"] for row in authority["files"]}) == 281 and
        sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in authority["files"]) == 38 and
        type(authority["totalBytes"]) is int and authority["totalBytes"] ==
        sum(row["bytes"] for row in authority["files"]) <= 512 * 1024 * 1024, "PREFIX_AUTHORITY_DECLARATIONS_NOT_CUSTODY")
    for row in authority["directories"]:
        fields(row, "relative identity provenance")
        require(type(row["relative"]) is str and row["provenance"] ==
            ("ORIGINAL_NATIVE_PIN" if row["identity"] is not None else "ORIGINAL_QUERY_DECLARATION"),
            "PREFIX_AUTHORITY_DIRECTORY")
    require(len({row["relative"] for row in authority["directories"]}) == 58, "PREFIX_AUTHORITY_DIRECTORY_ROSTER")
    pins = {row["relative"]: row["identity"] for row in authority["directories"] if row["identity"] is not None}
    require(set(pins) == {".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"},
        "PREFIX_AUTHORITY_ORIGINAL_PINS")
    prefix_directory_pins(originals, inputs.role)
    closed = fields(canonical(originals["authority-return.json"]), "schema scope windowSha256 primaryResultSha256 "
        "primaryCopySha256 matchSha256 inventorySha256 pendingSha256 originalChain preCloseNs closedNs resourceCount "
        "retirement budgetAcceptance exportSaveAuthority")
    require(type(closed["schema"]) is int and closed["schema"] == 1 and
        closed["scope"] == "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_CLOSED_HISTORY_V1" and
        closed["primaryResultSha256"] == retired["primaryResultSha256"] and
        closed["primaryCopySha256"] == retired["primaryCopySha256"] and
        closed["inventorySha256"] == hashes["authority-index.json"]["sha256"] == retired["authorityInventorySha256"] and
        hashes["authority-return.json"]["sha256"] == retired["authoritySha256"] and
        closed["matchSha256"] == authority["matchSha256"] == O.digest(O.encoded(inputs.admission["initialRecipient"])) and
        closed["pendingSha256"] == authority["pendingSha256"] and
        closed["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and closed["budgetAcceptance"] == "NOT_ADMITTED" and
        closed["exportSaveAuthority"] is False and 0 < O.integer(closed["resourceCount"]) <= 10000 and
        O.integer(closed["preCloseNs"]) <= O.integer(closed["closedNs"]) <= O.integer(retired["inputsClosedNs"]),
        "PREFIX_AUTHORITY_RETURN")
    return {"schema": 1, "scope": PREFIX_SCOPE, "retiredPrefixSha256": O.digest(inputs.closed_raw), "files": hashes,
        "primary": {"step": "canonical-initialization", "outcome": "success",
            "resultSha256": retired["primaryResultSha256"], "handoffSha256": handoff["sha256"],
            "inventorySha256": sha(primary_inventory_sha256), "directory": copied["destination"],
            "directoryIdentity": copied["destinationIdentity"], "memberCount": copied["memberCount"],
            "totalBytes": copied["totalBytes"]},
        "authority": {"directory": authority["root"], "directoryIdentity": pins["."],
            "fileCount": 281, "directoryCount": 58, "retainedOriginalCount": 38,
            "copyState": "ORIGINAL_BYTES_NOT_COPIED"},
        "retirement": {"inputOwnerCloseSha256": O.digest(O.encoded(retired["inputOwnerClose"])),
            "inputsClosedNs": retired["inputsClosedNs"], "retiredNs": inputs.previous_ns,
            "prepDisposition": "TERMINALLY_RETIRED", "receivingDisposition": "HISTORICAL_NOT_REVIVED",
            "currentAuthority": "NEW_PER_USE_REQUIRED"},
        "custodyScope": "RECORD_RETENTION_ONLY_NOT_NATIVE_CUSTODY", "writerReturn": PENDING,
        "producerStepOutcome": PENDING, "providerExecution": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def prefix_retention_record(raws, reference, inputs, custody):
    require(type(raws) is dict and set(raws) == set(PREFIX_FILES), "PREFIX_SIX_ORIGINAL_FILES")
    prefix_reference(reference, inputs, custody)
    for name in PREFIX_FILES:
        raw = raw_bytes(raws[name], PREFIX_INDEX_LIMIT if name == "retention-index.json" else LIMIT)
        row = reference["files"][name]
        require(row["bytes"] == len(raw) and row["sha256"] == O.digest(raw), "PREFIX_ACTUAL_BYTES_CHANGED")
    value = fields(canonical(raws["retention-index.json"], PREFIX_INDEX_LIMIT), "schema scope retiredPrefixSha256 "
        "files primary authority retirement custodyScope writerReturn producerStepOutcome providerExecution "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    fields(value["primary"], "step outcome resultSha256 handoffSha256 inventorySha256 directory directoryIdentity memberCount totalBytes")
    originals = {name: raws[name] for name in PREFIX_FILES[:-1]}
    expected = prefix_retention_value(originals, inputs, custody, value["primary"]["inventorySha256"])
    same(value, expected, "PREFIX_PENDING_INDEX_CHANGED")
    pins = {native_identity(reference["directoryIdentity"], inputs.role),
        native_identity(reference["custodyDirectoryIdentity"], inputs.role),
        *(native_identity(row["fileBinding"]["identity"], inputs.role) for row in reference["files"].values())}
    require(not pins.intersection(prefix_directory_pins(originals, inputs.role)), "PREFIX_ORIGINAL_DIRECTORY_ALIAS")
    return value


def prefix_writer_close(value, handoff_raw):
    """Historical observation of the PRIOR first owner, never its replacement."""
    fields(value, "schema scope phase ownerOrdinal firstNs localStarted hardEndNs handoffSha256 prefixRetentionSha256 "
        "resourceCount resources retirement observationScope")
    index = canonical(handoff_raw)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == PREFIX_WRITER_CLOSE_SCOPE and
        value["phase"] == "producer-owner-return" and type(value["ownerOrdinal"]) is int and value["ownerOrdinal"] == 0 and
        value["handoffSha256"] == O.digest(handoff_raw) and value["prefixRetentionSha256"] ==
        O.digest(O.encoded(index["references"]["prefixRetention"])) and value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
        value["observationScope"] == "PRIOR_FIRST_OWNER_ONLY", "PREFIX_PRIOR_WRITER_CLOSE")
    for name in ("firstNs", "localStarted", "hardEndNs"):
        same(value[name], index["window"][name], "PREFIX_PRIOR_WRITER_ORIGINAL45")
    # Preserve every original144 allocation, inserting149 real source reads
    # after its first46 and149 after its last. This is an exact ledger grammar,
    # NOT permission to fabricate rows or enlarge the original owner's limits.
    source_labels = compatibility.source_read_labels()
    labels = [*("directory",) * 8, *("reader",) * 12, "directory", "directory",
        *("writer", "reader", "reader") * 6, *("reader",) * 6,
        *source_labels, "directory", "directory"]
    for name in (*BLOB_NAMES, "save-handoff.json"):
        labels.extend(("empty-original-writer" if name.endswith(".bin") and index["blobs"][name]["bytes"] == 0
            else "writer", "reader"))
    labels.extend(("reader",) * 32)
    labels.extend(source_labels)
    require(type(value["resourceCount"]) is int and value["resourceCount"] == len(labels) == 442, "PREFIX_PRIOR_WRITER_ROWS")
    same(value["resources"], [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
        for number, label in enumerate(labels)], "PREFIX_PRIOR_WRITER_LEDGER")
    raw_bytes(O.encoded(value))
    return value


def handoff_record(raw, blobs, inputs, first, claims, directory, directory_identity, *, custody):
    value = fields(canonical(raw), "schema scope binding source github selection cacheCohort plan planSha256 directory "
        "directoryIdentity blobs references chain window writerReturn providerExecution nextPhaseAuthority "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 2 and value["scope"] == HANDOFF_SCOPE and
        value["writerReturn"] == PENDING and value["providerExecution"] == "NOT_PERFORMED" and
        value["nextPhaseAuthority"] is False and claims["PRODUCER_OUTCOME"] == "success" and
        O.digest(raw) == sha(claims["HANDOFF_SHA256"]), "HANDOFF_SCOPE_OR_CLAIMS")
    nonacceptance(value)
    fields(value["references"], "initializerFiles staging phaseOriginals prefixRetention")
    prefix_reference(value["references"]["prefixRetention"], inputs, custody)
    require(type(blobs) is dict and set(blobs) == set(BLOB_NAMES) and len(blobs) == 31 < 32, "HANDOFF_ORIGINAL_BLOBS")
    same(value["blobs"], {name: {"bytes": len(raw_bytes(blob, empty=name.endswith(".bin"))), "sha256": O.digest(blob)}
        for name, blob in blobs.items()}, "HANDOFF_ORIGINAL_BLOBS")
    same(value["binding"], inputs.binding(), "HANDOFF_INITIAL_BINDING")
    original = initial_inputs_record(blobs["initial-inputs.json"], inputs.admission["source"])
    same(original["binding"], inputs.binding(), "HANDOFF_OUTER_INITIAL_BINDING")
    same(original["initializerCheckedLocal"], inputs.previous_local, "HANDOFF_OUTER_INITIAL_LOCAL")
    for name in ("source", "github", "selection", "cacheCohort"):
        same(value[name], inputs.admission[name], "HANDOFF_IDENTITY")
    require(value["directory"] == str(directory) and native_identity(value["directoryIdentity"], inputs.role) ==
        tuple(directory_identity) and value["planSha256"] == O.digest(O.encoded(value["plan"])), "HANDOFF_DIRECTORY_OR_PLAN")
    window = fields(value["window"], "phase clock originalBootDigest firstNs localStarted hardEndNs "
        "predecessorCheckedNs predecessorSha256")
    began, hard, prior = (O.integer(window[name]) for name in ("firstNs", "hardEndNs", "predecessorCheckedNs"))
    require(window["phase"] == "producer-owner-return" and window["clock"] == O.clock_value(first.clock) ==
        O.clock_value(inputs.clock) and window["originalBootDigest"] == inputs.history["originalBootDigest"] and
        window["predecessorSha256"] == O.digest(blobs["before-parent.json"]) and prior <= began < hard == min(
        began + 45 * O.NS, inputs.proposal["phaseFencesNs"]["producer-owner-return"], inputs.proposal["proposedJobEndNs"]),
        "HANDOFF_ORIGINAL45")
    require(type(window["localStarted"]) is float, "HANDOFF_ORIGINAL_LOCAL")
    local(window["localStarted"])
    chain = fields(value["chain"], "scope returns referenceScope")
    require(chain["scope"] == "INITIAL_RECIPIENT_ORIGINAL_PRODUCTIVE_CLOSED_CHAIN_V1" and
        chain["referenceScope"] == "RETAINED_ORIGINAL_BINDINGS_NOT_PROVIDER_OR_STEP_RESULT" and
        type(chain["returns"]) is dict and set(chain["returns"]) == {*PRODUCTIVE_PHASES, "before"} and
        chain["returns"]["before"]["checkedNs"] == prior, "HANDOFF_ORIGINAL_CHAIN")
    same(chain["returns"]["before"], chain["returns"]["save-set-before"], "HANDOFF_BEFORE_ALIAS")
    for name, leaf in (("dependency-stage", "stage"), ("empty-seed", "seed"), ("custody-prepare", "custody"),
                       ("configuration", "producer"), ("custody-collect", "collection"),
                       ("custody-uninstall", "no-loader"), ("dependency-export", "export"), ("save-set-before", "before")):
        row = fields(chain["returns"][name], "rawSha256 checkedNs checkedLocal leaf")
        require(row["rawSha256"] == O.digest(blobs[leaf + "-parent.json"]) and O.integer(row["checkedNs"]) <= prior,
                "HANDOFF_PHASE_RETURN")
        require(type(row["checkedLocal"]) is float, "HANDOFF_RETURN_LOCAL")
        local(row["checkedLocal"])
        fields(row["leaf"], "rawSha256 checkedNs localStarted checkedLocal")
        leaf_name = "producer-observation.json" if name == "configuration" else leaf + "-leaf.json"
        require(row["leaf"]["rawSha256"] == O.digest(blobs[leaf_name]) and
            O.integer(row["leaf"]["checkedNs"]) <= row["checkedNs"] and
            type(row["leaf"]["localStarted"]) is type(row["leaf"]["checkedLocal"]) is float and
            local(row["leaf"]["localStarted"]) <= local(row["leaf"]["checkedLocal"]) <= row["checkedLocal"],
            "HANDOFF_LEAF_RETURN")
    return value


def producer_return_record(raw, index_raw, inputs, first, expected_hash, directory_identity):
    value = fields(canonical(raw), "schema scope handoffSha256 handoffDirectory handoffDirectoryIdentity initializerIdentity "
        "clock originalBootDigest firstNs hardEndNs handoffReturnedNs handoffReturnedLocal observedAfterReturnNs "
        "observedAfterReturnLocal prefixRetention priorWriterClose observationScope recordWriterReturn producerStepOutcome providerExecution "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    index = canonical(index_raw)
    require(type(value["schema"]) is int and value["schema"] == 2 and value["scope"] == RETURN_SCOPE and
        O.digest(raw) == sha(expected_hash) and value["observationScope"] == "HANDOFF_FUNCTION_RETURN_ONLY" and
        value["recordWriterReturn"] == value["producerStepOutcome"] == PENDING and
        value["providerExecution"] == "NOT_PERFORMED", "FUNCTION_RETURN_MARKERS")
    nonacceptance(value)
    same(value["prefixRetention"], index["references"]["prefixRetention"], "FUNCTION_RETURN_PREFIX_BINDING")
    prefix_writer_close(value["priorWriterClose"], index_raw)
    require(value["handoffSha256"] == O.digest(index_raw) and value["handoffDirectory"] == index["directory"] and
        native_identity(value["handoffDirectoryIdentity"], inputs.role) == tuple(directory_identity) and
        native_identity(value["initializerIdentity"], inputs.role) == inputs.directories["session"] and
        value["clock"] == O.clock_value(first.clock) == index["window"]["clock"] and
        value["originalBootDigest"] == index["window"]["originalBootDigest"], "FUNCTION_RETURN_BINDING")
    began, hard, returned, observed = (O.integer(value[name]) for name in
        ("firstNs", "hardEndNs", "handoffReturnedNs", "observedAfterReturnNs"))
    require(began == index["window"]["firstNs"] and hard == index["window"]["hardEndNs"] and
        began <= returned <= observed < hard and first.nanoseconds >= observed, "FUNCTION_RETURN_CHRONOLOGY")
    local_first = local(index["window"]["localStarted"])
    require(type(value["handoffReturnedLocal"]) is type(value["observedAfterReturnLocal"]) is float and
        local_first <= local(value["handoffReturnedLocal"]) <= local(value["observedAfterReturnLocal"]) <
        O.wire._directed_deadline(local_first, 45, hard, began), "FUNCTION_RETURN_LOCAL45_HISTORY")
    return value


@dataclass(frozen=True, repr=False)
class _HistoricalDataPoint:
    """A hash-joined old timestamp for DATA arithmetic, NEVER an actual Reading."""
    clock: object
    nanoseconds: int


def final_action_records(originals, preparation_raw, claims, point, outputs, use_originals):
    """Final-reader-only historical lookup DATA; no earlier Reading is rebuilt.

    The old maintained provider validator still requires its actual earliest
    post-Action Reading. This separate parser checks the same closed records
    at the timestamp authenticated by the original probe-result/readmission
    bytes. It neither invokes that old live entry nor admits a current owner.
    The caller separately reads all original episodes under its new reader.
    """
    import hosted_cache_provider_readback as R
    require(type(point) is _HistoricalDataPoint, "FINAL_ACTION_HISTORICAL_DATA_POINT")
    clock, first_ns = O.clocks.validate_identity(point.clock), O.integer(point.nanoseconds)
    fields(claims, " ".join((*R.BASE_CLAIMS, *R.LOOKUP_CLAIMS, "PROBE_OUTCOME", "PROBE_READBACK_SHA256")))
    for name, value in claims.items():
        require(type(value) is str and (value == "success" if name.endswith("OUTCOME") else sha(value)),
            "FINAL_ACTION_ORIGINAL_CLAIMS")
    fields(originals, " ".join(R.ACTION_FILES))
    prepared_raw, raw = (originals[name] for name in R.ACTION_FILES)
    require(type(raw) is bytes and type(prepared_raw) is bytes and max(len(raw), len(prepared_raw)) <= 16384,
        "FINAL_ACTION_ORIGINAL_BOUND")
    prepared, value, descriptor = canonical(prepared_raw), canonical(raw), canonical(preparation_raw)
    fields(value, "scope phase preparedSha256 preparationSha256 acknowledgement acknowledgementSha256 python "
        "workerRequestSha256 outputs checkedNs originalClaims enclosingActionReturn providerAcceptance initialUseChainSha256")
    fields(prepared, "scope phase preparationSha256 request bindings clockBindings firstNs originalClaims "
        "providerExecution enclosingActionReturn initialUseChainSha256")
    require(value["scope"] == "INITIAL_RECIPIENT_PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1" and
        prepared["scope"] == "INITIAL_RECIPIENT_PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1" and
        value["phase"] == prepared["phase"] == "lookup" and
        value["enclosingActionReturn"] == prepared["enclosingActionReturn"] == "NOT_OBSERVED" and
        value["providerAcceptance"] == "NOT_ESTABLISHED" and prepared["providerExecution"] == "NOT_PERFORMED" and
        value["preparedSha256"] == O.digest(prepared_raw) and O.digest(raw) == claims["PROBE_READBACK_SHA256"] and
        value["preparationSha256"] == prepared["preparationSha256"] == O.digest(preparation_raw) ==
        claims["PROBE_PREPARATION_SHA256"] and sha(prepared["initialUseChainSha256"]) == value["initialUseChainSha256"],
        "FINAL_ACTION_PENDING_HASHES")
    old_claims = {name: claims[name] for name in (*R.BASE_CLAIMS, *R.LOOKUP_CLAIMS)}
    same(prepared["originalClaims"], old_claims, "FINAL_ACTION_PREPARED_CLAIMS")
    same(value["originalClaims"], old_claims, "FINAL_ACTION_RETURNED_CLAIMS")
    require(type(prepared["request"]) is str and prepared["request"].isascii() and
        type(value["acknowledgement"]) is str and value["acknowledgement"].isascii(), "FINAL_ACTION_ASCII_BYTES")
    request, acknowledgement = prepared["request"].encode("ascii"), value["acknowledgement"].encode("ascii")
    context, _request = R.outer._context(request)
    ack = R.outer.read_ack(acknowledgement, request, 0)
    require(ack.kind == ack.provider_kind == "success" and ack.worker_exit_code == 0 and
        value["acknowledgementSha256"] == O.digest(acknowledgement) and
        value["workerRequestSha256"] == ack.worker_request_sha256 and context["role"] == clock.role and
        context["frequency"] == clock.ticks_per_second, "FINAL_ACTION_ACK_CLOCK_DATA")
    directory = R.launch._path(descriptor["directory"], clock.role)
    R.launch._identity(descriptor["directoryIdentity"], clock.role)
    R.launch._path(value["python"], clock.role)
    require(descriptor["scope"] == PROBE_PREPARATION_SCOPE and descriptor["clock"] == O.clock_value(clock) and
        context["phase"] == "lookup" and context["directory"] == str(directory / "provider") and
        context["home"] == str(directory / "provider-home") and prepared["firstNs"] == context["firstNs"] and
        descriptor["planSha256"] == O.digest(O.encoded(context["plan"])), "FINAL_ACTION_DESCRIPTOR")
    same(context["plan"], descriptor["plan"], "FINAL_ACTION_PLAN")
    window = fields(descriptor["providerWindow"], "issuedNs hardEndNs actualProviderStart")
    require(window["actualProviderStart"] == "NOT_OBSERVED" and
        O.integer(window["issuedNs"]) == R.launch._ns(context["issuedNs"]) and
        O.integer(window["hardEndNs"]) == R.launch._ns(context["hardEndNs"]) and
        R.launch._ns(context["firstNs"]) <= ack.observed_ns <= R.launch._ns(value["checkedNs"]) <= first_ns <
        window["hardEndNs"], "FINAL_ACTION_ORIGINAL_PROVIDER_END")
    for name, names in (("bindings", R.launch.worker_source.outer_names(clock.role)),
            ("clockBindings", R.clock_source.roster(clock.role))):
        fields(prepared[name], " ".join(names))
        for digest in prepared[name].values():
            sha(digest)
    require(all(prepared["bindings"].get(name, digest) == digest for name, digest in prepared["clockBindings"].items()),
        "FINAL_ACTION_SOURCE_BINDINGS")
    fields(outputs, "cache-primary-key cache-matched-key cache-hit")
    require(all(type(item) is str and len(item) <= 512 and all(32 <= ord(char) < 127 for char in item)
        for item in outputs.values()), "FINAL_ACTION_OUTPUT_DATA")
    same(value["outputs"], outputs, "FINAL_ACTION_ORIGINAL_OUTPUTS")
    fields(use_originals, " ".join(R.INITIAL_USE_FILES))
    chain = fields(canonical(use_originals["initial-use-chain.json"]), "schema scope phase clock originalBootDigest "
        "helperFirstNs helperWorkEndNs providerIssuedNs providerHardEndNs handoffSha256 producerReturnSha256 "
        "preparationSha256 workerIdentitySha256 directory directoryIdentity source github materializedNs uses checkedNs "
        "helperOwnerClose providerExecution exportSaveAuthority")
    require(type(chain["schema"]) is int and chain["schema"] == 1 and
        chain["scope"] == "INITIAL_RECIPIENT_PROVIDER_ORIGINAL_USE_CHAIN_V1" and chain["phase"] == "lookup" and
        chain["helperOwnerClose"] == PENDING and chain["providerExecution"] == "NOT_PERFORMED" and
        chain["exportSaveAuthority"] is False and chain["clock"] == descriptor["clock"] and
        O.digest(use_originals["initial-use-chain.json"]) == prepared["initialUseChainSha256"], "FINAL_ACTION_USE_CHAIN")
    for name in ("originalBootDigest", "handoffSha256", "producerReturnSha256", "preparationSha256", "workerIdentitySha256"):
        sha(chain[name])
    R.launch._identity(chain["directoryIdentity"], clock.role)
    require(directory.name.endswith("-probe") and chain["directory"] == str(directory / "native-preparation") and
        chain["handoffSha256"] == old_claims["HANDOFF_SHA256"] and
        chain["producerReturnSha256"] == old_claims["PRODUCER_RETURN_SHA256"] and
        chain["preparationSha256"] == prepared["preparationSha256"] and
        all(chain[name] == descriptor["plan"][name] for name in ("source", "github")), "FINAL_ACTION_USE_BINDING")
    root = directory.with_name(directory.name.removesuffix("-probe"))
    began, work, issued, end, materialized, checked = (O.integer(chain[name]) for name in
        ("helperFirstNs", "helperWorkEndNs", "providerIssuedNs", "providerHardEndNs", "materializedNs", "checkedNs"))
    require(began == R.launch._ns(prepared["firstNs"]) and issued == window["issuedNs"] and end == window["hardEndNs"] and
        issued <= began <= materialized <= checked < work == min(began + 45 * O.NS, end - 45 * O.NS) and
        issued + 45 * O.NS < end <= issued + 180 * O.NS and type(chain["uses"]) is list and len(chain["uses"]) == 2,
        "FINAL_ACTION_ORIGINAL_HELPER45")
    previous = began
    for number, edge in enumerate(("begin", "final")):
        use = fields(chain["uses"][number], "site root window returnSha256 inventorySha256")
        site = "provider-probe/native-prepare/" + edge
        require(use["site"] == site and use["root"] == str(root.with_name(root.name + "-" + R.initial_use.site_leaf(site))) and
            use["returnSha256"] == O.digest(use_originals[edge + "-use.json"]) and
            use["inventorySha256"] == O.digest(use_originals[edge + "-use-index.json"]), "FINAL_ACTION_ORIGINAL_EPISODE")
        actual_clock, frame = R.initial_use.checked_frame(use["window"])
        require(actual_clock == clock and frame["site"] == site and frame["parentFirstNs"] == began and
            frame["parentWorkEndNs"] == work and frame["originalBootDigest"] == chain["originalBootDigest"],
            "FINAL_ACTION_ORIGINAL_USE_PARENT")
        returned = fields(canonical(use_originals[edge + "-use.json"]), "schema scope site windowSha256 workerIdentitySha256 "
            "inventorySha256 pendingSha256 originalChain preCloseNs closedNs resourceCount retirement budgetAcceptance exportSaveAuthority")
        require(type(returned["schema"]) is int and returned["schema"] == 1 and returned["scope"] == R.initial_use.RETURN_SCOPE and
            returned["site"] == site and returned["windowSha256"] == O.digest(O.encoded(use["window"])) and
            returned["workerIdentitySha256"] == chain["workerIdentitySha256"] and
            returned["inventorySha256"] == use["inventorySha256"] and returned["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
            type(returned["resourceCount"]) is int and returned["resourceCount"] > 0, "FINAL_ACTION_ORIGINAL_USE_RETURN")
        require(returned["budgetAcceptance"] == "NOT_ADMITTED" and returned["exportSaveAuthority"] is False,
            "FINAL_ACTION_USE_NONACCEPTANCE")
        index = canonical(use_originals[edge + "-use-index.json"])
        R._initial_use_index(index, R.launch._path(use["root"], clock.role), site, use["window"], returned)
        read, preclose, closed = (O.integer(item) for item in
            (returned["originalChain"]["checkedNs"], returned["preCloseNs"], returned["closedNs"]))
        require(previous <= frame["firstNs"] <= read <= preclose <= closed < frame["workEndNs"] and
            closed <= (materialized if number == 0 else checked), "FINAL_ACTION_USE_ORDER")
        previous = materialized
    return chain


def preparation_record(raw, inputs, handoff_raw, return_raw, first, phase, expected_hash, directory, directory_identity,
                       use_chain_raw, contract, *, after_save_hash=None):
    require(phase in ("save", "lookup"), "PREPARATION_FIXED_PHASE")
    value = fields(canonical(raw), PREPARATION_FIELDS + (" afterSaveSha256" if phase == "lookup" else ""))
    index, produced = canonical(handoff_raw), canonical(return_raw)
    prefix, transition, provider = (("SAVE", "save-transition", "provider-save") if phase == "save" else
                                     ("PROBE", "probe-transition", "provider-probe"))
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        (SAVE_PREPARATION_SCOPE if phase == "save" else PROBE_PREPARATION_SCOPE) and O.digest(raw) == sha(expected_hash) and
        value["producerOriginalOutcome"] == "success" and value["writerReturn"] == PENDING and
        value["providerExecution"] == "NOT_PERFORMED", "PREPARATION_MARKERS")
    nonacceptance(value)
    for name in ("source", "github", "selection", "cacheCohort"):
        same(value[name], inputs.admission[name], "PREPARATION_IDENTITY")
    require(value["directory"] == str(directory) and native_identity(value["directoryIdentity"], inputs.role) ==
        tuple(directory_identity) and value["handoffSha256"] == O.digest(handoff_raw) and
        value["producerReturnSha256"] == O.digest(return_raw) and
        value["workerIdentitySha256"] == O.digest(inputs.admitted.record) and
        value["proposalSha256"] == O.digest(inputs.proposal_raw) and
        value["privateUseChainSha256"] == O.digest(use_chain_raw) and
        value["planSha256"] == index["planSha256"] and value["clock"] == O.clock_value(first.clock) and
        value["originalBootDigest"] == inputs.history["originalBootDigest"], "PREPARATION_BINDING")
    same(value["plan"], index["plan"], "PREPARATION_PLAN")
    began, hard, prior = (O.integer(value[name]) for name in ("firstNs", "hardEndNs", "producerObservedAfterReturnNs"))
    require(prior == produced["observedAfterReturnNs"] and prior <= began < hard == min(began + 30 * O.NS,
        inputs.proposal["phaseFencesNs"][transition], inputs.proposal["proposedJobEndNs"]), "PREPARATION_ORIGINAL30")
    chain = private_chain_record(use_chain_raw, inputs, handoff_raw,
        "prepare-save" if phase == "save" else "prepare-probe", began, hard)
    checked = chain["checkedNs"]
    window = fields(value["providerWindow"], "issuedNs hardEndNs actualProviderStart")
    issued, end = O.integer(window["issuedNs"]), O.integer(window["hardEndNs"])
    require(checked <= issued < hard and issued < end == min(issued + 180 * O.NS,
        inputs.proposal["phaseFencesNs"][provider], inputs.proposal["proposedJobEndNs"]) and
        issued <= first.nanoseconds < end and window["actualProviderStart"] == "NOT_OBSERVED", "PREPARATION_PROVIDER_WINDOW")
    same(value["providerRequest"], contract["request"], "PREPARATION_PROVIDER_REQUEST")
    if phase == "lookup":
        require(value["afterSaveSha256"] == sha(after_save_hash), "PREPARATION_AFTER_SAVE_BINDING")
    return value


def private_chain_record(raw, inputs, handoff_raw, operation, first, work):
    """Historical private begin/final DATA. Actual per-use readers are separate."""
    require(operation in STEP_PHASES, "PRIVATE_CHAIN_OPERATION")
    chain = fields(canonical(raw), "schema scope operation clock originalBootDigest firstNs workEndNs "
        "handoffSha256 uses checkedNs ownerClose providerExecution exportSaveAuthority")
    require(type(chain["schema"]) is int and chain["schema"] == 1 and chain["scope"] == STEP_CHAIN_SCOPE and
        chain["operation"] == operation and O.integer(chain["firstNs"]) == O.integer(first) and
        O.integer(chain["workEndNs"]) == O.integer(work) and chain["clock"] == O.clock_value(inputs.clock) and
        chain["originalBootDigest"] == inputs.history["originalBootDigest"] and
        chain["handoffSha256"] == O.digest(handoff_raw) and chain["ownerClose"] == PENDING and
        chain["providerExecution"] == "NOT_PERFORMED" and chain["exportSaveAuthority"] is False and
        type(chain["uses"]) is list and len(chain["uses"]) == 2, "PRIVATE_CHAIN_BINDING")
    seconds = STEP_CAPS[STEP_PHASES[operation]][0]
    require(first < work == min(first + seconds * O.NS,
        inputs.proposal["phaseFencesNs"][STEP_PHASES[operation]], inputs.proposal["proposedJobEndNs"]),
        "PRIVATE_CHAIN_ORIGINAL_CAP")
    checked, previous = O.integer(chain["checkedNs"]), first
    require(first <= checked < work, "PRIVATE_CHAIN_CHECKED")
    for row, edge in zip(chain["uses"], ("begin", "final")):
        fields(row, "site root return inventory window returnSha256 inventorySha256 originalsSha256")
        returned, window = row["return"], row["window"]
        require(row["site"] == returned["site"] == window["site"] == operation + "/" + edge and
            O.integer(window["parentFirstNs"]) == first and O.integer(window["parentWorkEndNs"]) == work and
            window["clock"] == chain["clock"] and window["originalBootDigest"] == chain["originalBootDigest"] and
            row["returnSha256"] == O.digest(O.encoded(returned)) and
            row["inventorySha256"] == O.digest(O.encoded(row["inventory"])) and
            returned["windowSha256"] == O.digest(O.encoded(window)) and
            returned["workerIdentitySha256"] == O.digest(inputs.admitted.record) and
            previous <= O.integer(window["firstNs"]) <= O.integer(returned["preCloseNs"]) <=
            O.integer(returned["closedNs"]) <= checked and returned["closedNs"] < O.integer(window["workEndNs"]) <= work,
            "PRIVATE_CHAIN_ORIGINAL_USE_ORDER")
        previous = returned["closedNs"]
    return chain


def step_window_record(value, inputs, phase):
    fields(value, "phase clock originalBootDigest firstNs softEndNs hardEndNs localStarted localScope")
    require(phase in STEP_CAPS and value["phase"] == phase and
        value["clock"] == O.clock_value(inputs.clock) and
        value["originalBootDigest"] == inputs.history["originalBootDigest"] and
        value["localScope"] == "THIS_COMMAND_ONLY" and type(value["localStarted"]) is float,
        "STEP_WINDOW_IDENTITY")
    first, soft, hard = (O.integer(value[name]) for name in ("firstNs", "softEndNs", "hardEndNs"))
    seconds, new_seconds = STEP_CAPS[phase]
    require(first < soft == min(hard, first + new_seconds * O.NS) and hard == min(first + seconds * O.NS,
        inputs.proposal["phaseFencesNs"][phase], inputs.proposal["proposedJobEndNs"]), "STEP_WINDOW_ORIGINAL_CAP")
    local(value["localStarted"])
    return value


def step_close_record(raw, inputs, phase):
    value = fields(canonical(raw), "schema scope window predecessorSha256 predecessorCheckedNs privateUseChainSha256 "
        "leafSha256 leafCheckedNs leafCheckedLocal historicalBefore closedNs closedLocal resourceCount parentResourceClose "
        "nextPhaseAuthority budgetAcceptance testAcceptance exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == STEP_CLOSE_SCOPE and
        value["parentResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["nextPhaseAuthority"] is False and
        type(value["resourceCount"]) is int and 0 < value["resourceCount"] <= files.MEMBER_LIMIT,
        "STEP_CLOSE_MARKERS")
    nonacceptance(value)
    window = step_window_record(value["window"], inputs, phase)
    first, hard, began_local = window["firstNs"], window["hardEndNs"], window["localStarted"]
    sha(value["predecessorSha256"])
    require(O.integer(value["predecessorCheckedNs"]) <= first <= O.integer(value["closedNs"]) < hard and
        type(value["closedLocal"]) is float and began_local <= local(value["closedLocal"]) <
        O.wire._directed_deadline(began_local, STEP_CAPS[phase][0], hard, first), "STEP_CLOSE_ORIGINAL_FRONTIER")
    chain = value["privateUseChainSha256"]
    require((chain is None) == (phase not in ("save-readmission", "custody-readmission")), "STEP_CLOSE_USE_POSITION")
    if chain is not None:
        sha(chain)
    if value["leafSha256"] is None:
        require(value["leafCheckedNs"] is value["leafCheckedLocal"] is None, "STEP_CLOSE_NO_LEAF")
    else:
        sha(value["leafSha256"])
        require(first <= O.integer(value["leafCheckedNs"]) <= value["closedNs"] and
            type(value["leafCheckedLocal"]) is float and
            began_local <= local(value["leafCheckedLocal"]) <= value["closedLocal"], "STEP_CLOSE_LEAF_FRONTIER")
    if phase == "save-set-after":
        old = fields(value["historicalBefore"], "rawSha256 checkedNs checkedLocal localScope")
        sha(old["rawSha256"])
        require(O.integer(old["checkedNs"]) <= first and type(old["checkedLocal"]) is float and
            old["localScope"] == "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND",
            "STEP_HISTORICAL_BEFORE")
        local(old["checkedLocal"])  # Deliberately no comparison with this process's LOCAL.
    else:
        require(value["historicalBefore"] is None, "STEP_NO_HISTORICAL_BEFORE")
    return value


def _provider_nonacceptance(value, clock, boot, claims):
    nonacceptance(value)
    require(value["writerReturn"] == PENDING and value["providerStorage"] == "UNPROVEN" and
        value["providerDeadlineEnforcement"] == "NOT_ESTABLISHED" and value["providerRetirement"] == "NOT_OBSERVED" and
        value["clock"] == clock and value["originalBootDigest"] == boot, "STEP_PROVIDER_NONACCEPTANCE")
    same(value["originalClaims"], claims, "STEP_ORIGINAL_CLAIMS")


def after_save_records(raw, observations_raw, retained, inputs, handoff_raw, producer_raw, claims, first,
                       directory, directory_identity):
    """Passive cross-Step chronology, never an expired parent/current callback.

    The new caller separately reads fixed native originals and validates the old
    Action against this genuinely hash-bound earliest post-Action RAW value.
    No old LOCAL is compared with the new command's LOCAL epoch.
    """
    returned = fields(canonical(raw), "schema scope source github selection cacheCohort directory directoryIdentity "
        "originalClaims planSha256 clock originalBootDigest observationsSha256 observationOwnerReturn returnWindow "
        "recordedNs recordedLocal providerStorage providerDeadlineEnforcement providerRetirement writerReturn "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    observed = fields(canonical(observations_raw), "schema scope source github selection cacheCohort originalClaims "
        "planSha256 clock originalBootDigest firstPostProviderNs firstPostProviderLocal providerEndNs providerTimeScope "
        "providerStorage providerDeadlineEnforcement providerRetirement files window writerReturn "
        "budgetAcceptance testAcceptance exportSaveAuthority")
    require(claims["AFTER_SAVE_OUTCOME"] == "success" and O.digest(raw) == sha(claims["AFTER_SAVE_SHA256"]) and
        type(returned["schema"]) is type(observed["schema"]) is int and returned["schema"] == observed["schema"] == 1 and
        returned["scope"] == AFTER_SAVE_SCOPE and observed["scope"] == SAVE_OBSERVATIONS_SCOPE and
        returned["directory"] == str(directory) and native_identity(returned["directoryIdentity"], inputs.role) ==
        tuple(directory_identity) and returned["observationsSha256"] == O.digest(observations_raw), "AFTER_SAVE_ORIGINAL_RETURN")
    old_claims = {name: claims[name] for name in SAVE_CLAIMS}
    require(all(value == "success" if name.endswith("OUTCOME") else sha(value)
                for name, value in old_claims.items()) and old_claims["HANDOFF_SHA256"] == O.digest(handoff_raw) and
        old_claims["PRODUCER_RETURN_SHA256"] == O.digest(producer_raw), "AFTER_SAVE_ORIGINAL_CLAIMS")
    for value in (returned, observed):
        _provider_nonacceptance(value, O.clock_value(first.clock), inputs.history["originalBootDigest"], old_claims)
        require(value["planSha256"] == canonical(handoff_raw)["planSha256"], "AFTER_SAVE_ORIGINAL_PLAN")
        for name in ("source", "github", "selection", "cacheCohort"):
            same(value[name], inputs.admission[name], "AFTER_SAVE_ORIGINAL_IDENTITY")
    require(observed["providerTimeScope"] ==
        "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME" and
        type(retained) is dict and set(retained) == set(AFTER_SAVE_FILES), "AFTER_SAVE_RETAINED_ROSTER")
    same(observed["files"], {name: O.digest(raw_bytes(value)) for name, value in retained.items()},
        "AFTER_SAVE_ORIGINAL_BYTES")
    readmission = step_close_record(retained["readmission-close.json"], inputs, "save-readmission")
    parent = step_close_record(retained["after-parent-close.json"], inputs, "save-set-after")
    observation = step_close_record(O.encoded(returned["observationOwnerReturn"]), inputs, "save-observation")
    return_window = step_window_record(returned["returnWindow"], inputs, "save-owner-return")
    require(readmission["window"]["firstNs"] == O.integer(observed["firstPostProviderNs"]) and
        type(observed["firstPostProviderLocal"]) is float and
        readmission["window"]["localStarted"] == local(observed["firstPostProviderLocal"]) and
        readmission["predecessorSha256"] == O.digest(producer_raw) and
        readmission["predecessorCheckedNs"] == canonical(producer_raw)["observedAfterReturnNs"] and
        readmission["leafSha256"] is None, "AFTER_SAVE_EARLIEST_POST_PROVIDER")
    require(readmission["privateUseChainSha256"] == O.digest(retained["private-use-chain.json"]),
        "AFTER_SAVE_PRIVATE_CHAIN_HASH")
    chain = private_chain_record(retained["private-use-chain.json"], inputs, handoff_raw, "after-save",
        readmission["window"]["firstNs"], readmission["window"]["hardEndNs"])
    require(chain["checkedNs"] <= readmission["closedNs"], "AFTER_SAVE_PRIVATE_CHAIN_RETURN")
    for raw_previous, previous, current in ((retained["readmission-close.json"], readmission, parent),
                                           (retained["after-parent-close.json"], parent, observation)):
        require(current["predecessorSha256"] == O.digest(raw_previous) and
            current["predecessorCheckedNs"] == previous["closedNs"] and
            previous["closedNs"] <= current["window"]["firstNs"] and
            previous["closedLocal"] <= current["window"]["localStarted"], "AFTER_SAVE_PHASE_ORDER")
    same(observed["window"], observation["window"], "AFTER_SAVE_OBSERVATION_WINDOW")
    require(observation["leafSha256"] == O.digest(observations_raw) and
        observation["closedNs"] <= return_window["firstNs"] and
        observation["closedLocal"] <= return_window["localStarted"] and
        return_window["firstNs"] <= O.integer(returned["recordedNs"]) < return_window["hardEndNs"] and
        returned["recordedNs"] <= first.nanoseconds and type(returned["recordedLocal"]) is float and
        return_window["localStarted"] <= local(returned["recordedLocal"]) < O.wire._directed_deadline(
            return_window["localStarted"], 45, return_window["hardEndNs"], return_window["firstNs"]),
        "AFTER_SAVE_ORIGINAL_RETURN45")
    require(observed["firstPostProviderNs"] < O.integer(observed["providerEndNs"]), "AFTER_SAVE_ORIGINAL_PROVIDER_END")
    return returned, observed, readmission, parent


def after_save_leaf(raw, before_raw, before_parent_raw, index, parent, proposal_raw):
    """Compare the actual complete after observation with the original whole set."""
    before, after = canonical(before_raw), canonical(raw)
    require(set(after) == set(before) and after["scope"] == "BOOTSTRAP_SAVE_SET_AFTER_LEAF_V1" and
        after["phase"] == "after-save" and after["status"] == "KNOWN_UNCHANGED" and
        after["beforeSaveSha256"] == O.digest(before_raw), "AFTER_SAVE_LEAF_KIND")
    same(before, {**after, "scope": "BOOTSTRAP_SAVE_SET_BEFORE_LEAF_V1", "phase": "before-save",
        "status": "KNOWN_FROZEN", "beforeSaveSha256": None, "window": before["window"]}, "AFTER_SAVE_WHOLE_SET_CHANGED")
    window = fields(after["window"], "phase clock firstNs hardEndNs softEndNs lastNewWorkNs finishedNs "
        "predecessorSha256 predecessorCheckedNs proposalSha256")
    previous = index["chain"]["returns"]["before"]
    require(window["phase"] == "save-set-after" and window["proposalSha256"] == O.digest(proposal_raw) and
        window["predecessorSha256"] == O.digest(before_parent_raw) and
        O.integer(window["predecessorCheckedNs"]) == previous["checkedNs"] and
        all(O.encoded(window[name]) == O.encoded(parent["window"][name]) for name in
            ("phase", "clock", "firstNs", "softEndNs", "hardEndNs")) and
        previous["checkedNs"] <= window["firstNs"] <= O.integer(window["lastNewWorkNs"]) <=
        O.integer(window["finishedNs"]) <= parent["leafCheckedNs"] <= parent["closedNs"] and
        window["lastNewWorkNs"] < window["softEndNs"] and parent["leafSha256"] == O.digest(raw),
        "AFTER_SAVE_LEAF_WINDOW")
    same(parent["historicalBefore"], {"rawSha256": O.digest(before_parent_raw), "checkedNs": previous["checkedNs"],
        "checkedLocal": previous["checkedLocal"],
        "localScope": "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND"}, "AFTER_SAVE_HISTORICAL_BEFORE")
    return after


def require(value, reason):
    O.require(value, "INITIAL_PRODUCTIVE_DATA_" + reason)


def raw_bytes(raw, maximum=LIMIT, *, empty=False):
    require(type(raw) is bytes and (0 if empty else 1) <= len(raw) <= maximum, "ORIGINAL_BYTES")
    return raw


def canonical(raw, maximum=LIMIT):
    value = O.parse(raw_bytes(raw, maximum))
    require(type(value) is dict and O.encoded(value) == raw, "CANONICAL_RECORD")
    return value


def fields(value, names):
    require(type(value) is dict and set(value) == set(names.split()), "FIELDS")
    return value


def initial_inputs_record(raw, source):
    """Mandatory outer2 DATA; the original inner InitialInputs binding is unchanged."""
    value = fields(canonical(raw), "schema scope binding initializerCheckedLocal compatibilityInputs")
    require(type(value["schema"]) is int and value["schema"] == 2 and value["scope"] == OUTER_INPUT_SCOPE and
            type(value["binding"]) is dict and value["binding"].get("scope") == INPUT_SCOPE, "INITIAL_INPUT_RECORD")
    local(value["initializerCheckedLocal"])
    nested = compatibility.checked_envelope(value["compatibilityInputs"])
    same(nested["source"], source, "INITIAL_COMPATIBILITY_SOURCE")
    return value


def same(actual, expected, reason):
    require(O.encoded(actual) == O.encoded(expected), reason)


def local(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "LOCAL_CLOCK")
    return float(value)


def sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "HASH")
    return value


def native_identity(value, role):
    require(type(value) in (tuple, list) and files._identity(list(value)) and
        type(value[1]) is (str if role == "windows-x64" else int), "NATIVE_IDENTITY")
    return tuple(value)


def worker_values(value):
    require(type(value) is identity.InitialBootstrapIdentity, "INITIAL_IDENTITY_REQUIRED")
    raws = tuple(raw_bytes(getattr(value, name), files.RECEIPT_LIMIT) for name in
        ("record", "original_event", "original_policy", "public_key"))
    require(type(value.fingerprint) is str and type(value.key_sha256) is str and type(value.expires_at) is int,
        "IDENTITY_FIELDS")
    return (*raws, value.fingerprint, value.key_sha256, value.expires_at)


def checked_worker(value):
    snapshot = worker_values(value)
    record = canonical(snapshot[0])
    require(identity.cache_cohort(snapshot[0]) is not None, "INITIAL_IDENTITY_REQUIRED")
    # This is historical supplied-byte consistency, NOT policy currency. A new
    # actual acquisition must separately bind the match using its real now.
    match = identity.stages.BootstrapMatch(O.encoded(record["initialRecipient"]))
    expected = identity.bind_worker_match(match, event_raw=snapshot[1], policy_raw=snapshot[2],
        now=record["initialRecipient"]["firstUseAt"])
    require(worker_values(expected) == snapshot, "IDENTITY_ORIGINALS_CHANGED")
    return record


def original_proposal(raw, worker, history_raw, clock):
    """Original service arithmetic only; never derive a new budget from a recheck."""
    admitted = checked_worker(worker)
    history = fields(canonical(history_raw), HISTORY_FIELDS)
    value = canonical(raw)
    require(type(history["schema"]) is int and history["schema"] == 1 and
        history["scope"] == "INITIAL_CUSTODY_PRIMARY_HISTORICAL_BINDING_V1" and history["kind"] == "worker" and
        history["currentAuthority"] == "NOT_ACQUIRED" and history["budgetAcceptance"] == "NOT_ADMITTED" and
        history["exportSaveAuthority"] is False, "ORIGINAL_HISTORY")
    O.clocks.validate_identity(clock)
    first_use = admitted["initialRecipient"]["firstUseAt"]
    require(history["firstUseAt"] == first_use and
        history["matchSha256"] == O.digest(O.encoded(admitted["initialRecipient"])) and
        history["clock"] == O.clock_value(clock), "HISTORY_IDENTITY")
    sha(history["originalBootDigest"])
    basis = value.get("serviceTimeBasis")
    require(type(basis) is dict and type(basis.get("service")) is dict and
        type(basis.get("invocation")) is str and re.fullmatch(r"[0-9a-f]{32}", basis["invocation"]), "ORIGINAL_SERVICE")
    service = basis["service"]
    shared = {"schema": 1, "profile": admitted["profile"], "selection": admitted["selection"],
        "cacheCohort": admitted["cacheCohort"], "source": admitted["source"], "github": admitted["github"],
        "workerIdentitySha256": O.digest(worker.record), "clock": O.clock_value(clock), "firstUseAt": first_use,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    expected_basis = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1",
        "invocation": basis["invocation"], "service": service, "policy": allocation.service_time.policy(),
        **allocation.service_time.basis_arithmetic(service["jobsRequestStartedNs"],
            O.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])}
    expected = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1",
        "serviceTimeBasis": expected_basis, "serviceTimeBasisSha256": O.digest(O.encoded(expected_basis)),
        "policy": allocation.policy(), **allocation.fence_arithmetic(expected_basis["jobStartBasisNs"]),
        "productiveOwner": "NOT_CREATED"}
    require(raw == O.encoded(expected) and expected_basis["jobStartBasisNs"] == history["originalJobBasisNs"],
        "ORIGINAL_PROPOSAL_CHANGED")
    return value


def retired_input_close(value):
    """Exact DATA roster of C's twelve-reader/four-directory retirement only."""
    fields(value, "schema scope resources retirement exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1" and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["exportSaveAuthority"] is False,
        "RETIRED_INPUT_CLOSE")
    labels, parents = [], set()
    for name in INITIALIZER_FILES:
        parent = name.rsplit("/", 1)[0]
        if parent not in parents:
            parents.add(parent)
            labels.append("directory")
        labels.append("reader")
    same(value["resources"], [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
        for number, label in enumerate(labels)], "RETIRED_INPUT_CLOSE_ROSTER")
    return value


@dataclass(frozen=True, repr=False)
class InitialOriginals:
    """Supplied initial leaf DATA. Constructing it grants no original-call rights."""
    worker: object
    history_raw: bytes
    proposal_raw: bytes
    retired_raw: bytes
    source_records: tuple
    initializer: str
    initializer_originals: tuple
    initializer_directories: tuple
    checked_ns: int
    checked_local: float


def capture_originals(value):
    require(type(value) is InitialOriginals, "INITIAL_ORIGINALS_REQUIRED")
    worker = worker_values(value.worker)
    raws = tuple(raw_bytes(getattr(value, name)) for name in ("history_raw", "proposal_raw", "retired_raw"))
    require(type(value.source_records) is tuple and tuple(name for name, _raw in value.source_records) == SOURCE_KEYS and
        all(type(row) is tuple and len(row) == 2 for row in value.source_records), "SOURCE_ROSTER")
    sources = tuple((name, raw_bytes(raw, empty=True)) for name, raw in value.source_records)
    require(type(value.initializer) is str and type(value.initializer_originals) is tuple and
        tuple(name for name, _raw in value.initializer_originals) == INITIALIZER_FILES and
        all(type(row) is tuple and len(row) == 2 for row in value.initializer_originals), "INITIALIZER_ROSTER")
    originals = tuple((name, raw_bytes(raw, empty=name.endswith(".log"))) for name, raw in value.initializer_originals)
    require(type(value.initializer_directories) is tuple and len(value.initializer_directories) == 8 and
        all(type(row) is tuple and len(row) == 3 for row in value.initializer_directories), "INITIALIZER_DIRECTORIES")
    clock = O.wire.clock_identity(canonical(value.history_raw)["clock"])
    directories = tuple((name, native_identity(pin, clock.role), provenance)
        for name, pin, provenance in value.initializer_directories)
    require({name for name, _pin, _provenance in directories} == set(INITIALIZER_DIRECTORIES) and
        all(provenance == "ORIGINAL_INITIALIZER_NATIVE_PIN" for _name, _pin, provenance in directories) and
        len({pin for _name, pin, _provenance in directories}) == 8, "INITIALIZER_DIRECTORY_PINS")
    require(type(value.checked_local) is float, "INITIALIZER_ORIGINAL_LOCAL")
    return (worker, *raws, sources, value.initializer, originals, directories,
        O.integer(value.checked_ns), local(value.checked_local))


class InitialInputs:
    """Detached supplied-data view for shared leaves, deliberately not ordinary _Inputs."""
    def __init__(self, published, snapshot):
        self.published, self.snapshot = published, snapshot
        (worker, self.history_raw, self.proposal_raw, self.closed_raw, self.source_records, initializer,
         self.initializer_originals, self.initializer_directories, self.previous_ns, self.previous_local) = snapshot
        self.admitted = identity.InitialBootstrapIdentity(*worker)
        self.admission = checked_worker(self.admitted)
        self.history = canonical(self.history_raw)
        self.clock = O.wire.clock_identity(self.history["clock"])
        self.proposal = original_proposal(self.proposal_raw, self.admitted, self.history_raw, self.clock)
        self.profile, self.role = identity.cache_cohort(self.admitted.record)
        self.invocation = self.proposal["serviceTimeBasis"]["invocation"]
        require(self.source_records[-1][1] == self.admitted.original_policy, "SOURCE_POLICY_CHANGED")
        self.session = Path(initialization.producer._path(initializer, self.role))
        self.state, self.home, self.root = self.session / "state", self.session / "state/gradle-home", str(ROOT)
        self.container = files.stage_path(self.session, self.profile, self.role, admitted_raw=self.admitted.record)
        self.restore = self.container / "restore-home"
        pins = {name: pin for name, pin, _provenance in self.initializer_directories}
        self.directories = {name: pins[key] for name, key in zip(DIRECTORY_NAMES, DIRECTORY_KEYS)}
        originals = dict(self.initializer_originals)
        self.context_raw, self.canonical_raw, self.properties_raw = (originals[name] for name in
            ("I/initializer-context.json", "I/state/context.json", "I/state/gradle-home/gradle.properties"))
        context = fields(canonical(self.context_raw), "schema scope job receivingWindowSha256 authoritySha256 "
            "senderSha256 stepSha256 requestSha256 workerIdentitySha256 budgetAcceptance testAcceptance exportSaveAuthority")
        require(type(context["schema"]) is int and context["schema"] == 1 and context["scope"] == INITIAL_CONTEXT_SCOPE and
            context["workerIdentitySha256"] == O.digest(self.admitted.record) and
            context["receivingWindowSha256"] == O.digest(originals["I/receiving-window.json"]) and
            context["requestSha256"] == O.digest(originals["I/canonical-init/request.json"]) and
            context["budgetAcceptance"] == "NOT_ADMITTED" and context["testAcceptance"] == "NOT_PERFORMED" and
            context["exportSaveAuthority"] is False, "INITIAL_CONTEXT")
        for name in ("authoritySha256", "senderSha256", "stepSha256"):
            sha(context[name])
        canonical_context = initialization.producer.parse(self.canonical_raw)
        require(type(canonical_context.get("javaHomes")) is list, "CANONICAL_HOMES")
        self.canonical = initialization.initial_recipient_context_record(self.canonical_raw,
            worker_raw=self.admitted.record, root=self.root, state=str(self.state), role=self.role,
            outer_job=context["job"], homes=tuple(canonical_context["javaHomes"]), policy_raw=self.properties_raw)
        retired = fields(canonical(self.closed_raw), "schema scope clock originalBootDigest primaryResultSha256 "
            "primaryCopySha256 authoritySha256 authorityInventorySha256 workerIdentitySha256 originalProposalSha256 "
            "initializer initializerFilesSha256 inputOwnerClose inputsClosedNs originalPrepWorkEndNs prepDisposition "
            "receivingDisposition currentAuthority budgetAcceptance testAcceptance exportSaveAuthority")
        require(type(retired["schema"]) is int and retired["schema"] == 1 and retired["scope"] == RETIRED_SCOPE and
            retired["clock"] == O.clock_value(self.clock) and retired["originalBootDigest"] == self.history["originalBootDigest"] and
            retired["workerIdentitySha256"] == O.digest(self.admitted.record) and
            retired["originalProposalSha256"] == O.digest(self.proposal_raw) and retired["initializer"] == initializer and
            retired["initializerFilesSha256"] == {name: O.digest(raw) for name, raw in self.initializer_originals} and
            retired["prepDisposition"] == "TERMINALLY_RETIRED" and retired["receivingDisposition"] == "HISTORICAL_NOT_REVIVED" and
            retired["currentAuthority"] == "NEW_PER_USE_REQUIRED" and retired["budgetAcceptance"] == "NOT_ADMITTED" and
            retired["testAcceptance"] == "NOT_PERFORMED" and retired["exportSaveAuthority"] is False and
            O.integer(self.history["originalPreviousNs"]) <= O.integer(retired["inputsClosedNs"]) <= self.previous_ns <
            O.integer(retired["originalPrepWorkEndNs"]), "RETIRED_PREFIX")
        for name in ("primaryResultSha256", "primaryCopySha256", "authoritySha256", "authorityInventorySha256"):
            sha(retired[name])
        retired_input_close(retired["inputOwnerClose"])
        self.parent_scope = STAGING_PARENT_SCOPE

    def unchanged(self):
        require(capture_originals(self.published) == self.snapshot, "INITIAL_INPUT_CHANGED")

    def binding(self):
        return {"scope": INPUT_SCOPE, "workerIdentitySha256": O.digest(self.admitted.record),
            "proposalSha256": O.digest(self.proposal_raw), "historySha256": O.digest(self.history_raw),
            "retiredPrefixSha256": O.digest(self.closed_raw), "clock": O.clock_value(self.clock),
            "originalBootDigest": self.history["originalBootDigest"], "invocation": self.invocation,
            "sourceRecordsSha256": {name: O.digest(raw) for name, raw in self.source_records},
            "initializerContextSha256": O.digest(self.context_raw), "canonicalContextSha256": O.digest(self.canonical_raw),
            "propertiesSha256": O.digest(self.properties_raw), "initializerCheckedNs": self.previous_ns,
            "initializerDirectories": {name: list(pin) for name, pin in self.directories.items()},
            "allInitializerDirectories": {name: {"identity": list(pin), "provenance": provenance}
                for name, pin, provenance in self.initializer_directories},
            "initializerFilesSha256": {name: O.digest(raw) for name, raw in self.initializer_originals},
            "session": str(self.session), "state": str(self.state), "home": str(self.home),
            "container": str(self.container), "restoreHome": str(self.restore)}
