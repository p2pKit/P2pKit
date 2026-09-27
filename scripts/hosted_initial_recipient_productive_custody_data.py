"""Closed productive-final DATA. No owner, clock reader or admission factory.

Only the separately registered controller joins these predicates to actual
native returns. A digest, consistent record or declared corpus is not custody.
"""
from __future__ import annotations

import math
import re

import hosted_initial_recipient_productive_data as D


O = D.O
NS = O.NS
LIMIT = 2 * 1024 * 1024
PUBLIC_LIMIT = 64 * 1024
MAX_BYTES = 512 * 1024 * 1024
MAX_NODES = 10000
PENDING = "PENDING_NOT_OBSERVABLE_BY_THIS_FILE"
GROUPS = (
    "use-01-dependency-stage-readmission", "use-02-empty-seed-readmission",
    "use-03-custody-prepare-readmission", "use-04-configuration-prelaunch",
    "use-05-custody-collect-readmission", "use-06-custody-uninstall-observation",
    "use-07-dependency-export-copy", "use-08-save-set-before-observation",
    "use-09-producer-handoff-retention", "use-10-prepare-save-begin",
    "use-11-prepare-save-final", "use-12-after-save-begin", "use-13-after-save-final",
    "use-14-prepare-probe-begin", "use-15-prepare-probe-final", "use-16-after-probe-begin",
    "use-17-after-probe-final", "use-18-provider-save-native-prepare-begin",
    "use-19-provider-save-native-prepare-final", "use-20-provider-probe-native-prepare-begin",
    "use-21-provider-probe-native-prepare-final", "primary-retained", "prefix-packet",
    "authority-history", "productive-packets", "configuration-source-metadata",
    "configuration-retained", "authority-pre-export", "crypto-inputs", "recipient-validation",
)
USE_SITES = (
    "dependency-stage/readmission", "empty-seed/readmission", "custody-prepare/readmission",
    "configuration/prelaunch", "custody-collect/readmission", "custody-uninstall/observation",
    "dependency-export/copy", "save-set-before/observation", "producer-handoff/retention",
    "prepare-save/begin", "prepare-save/final", "after-save/begin", "after-save/final",
    "prepare-probe/begin", "prepare-probe/final", "after-probe/begin", "after-probe/final",
    "provider-save/native-prepare/begin", "provider-save/native-prepare/final",
    "provider-probe/native-prepare/begin", "provider-probe/native-prepare/final",
)
FINAL_AUTHORITY_CAP_FIELDS = (
    "authorityFirstNs", "authorityWorkEndNs", "authorityFinalEndNs",
    "phaseStartedNs", "phaseWorkEndNs", "phaseFinalEndNs",
)
FINAL_AUTHORITY_CAP_FLAGS = (
    "--authority-first-ns", "--authority-work-end-ns", "--authority-final-end-ns",
    "--phase-started-ns", "--phase-work-end-ns", "--phase-final-end-ns",
)
FINAL_CRYPTO_CAP_FIELDS = (
    "freezeEndNs", "encryptWorkEndNs", "encryptFinalEndNs", "encryptReadEndNs",
    "nativeStartedNs", "nativeWorkEndNs", "nativeFinalEndNs",
)
FINAL_CRYPTO_CAP_FLAGS = (
    "--freeze-end-ns", "--encrypt-work-end-ns", "--encrypt-final-end-ns", "--encrypt-read-end-ns",
    "--native-started-ns", "--native-work-end-ns", "--native-final-end-ns",
)
FINAL_AUTHORITY_CONTEXT_FIELDS = (
    "schema scope edge kind root session job observed history originalProposal expectedMatch eventSha256 "
    "authorityWindow sourceReturnSha256 sourceReturnedNs inheritedContext directoryIdentity predecessor "
    "budgetAcceptance exportSaveAuthority"
)
FINAL_AUTHORITY_WINDOW_FIELDS = (
    "schema scope clock originalBootDigest originalJobBasisNs originalProposalSha256 phase phaseFirstNs "
    "phaseEndNs authorityFirstNs authorityWorkEndNs authorityFinalEndNs budgetAcceptance exportSaveAuthority"
)
AUTHORITY_PRE_CONTEXT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_CONTEXT_V1"
AUTHORITY_POST_CONTEXT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_POST_EXPORT_AUTHORITY_CONTEXT_V1"
AUTHORITY_PRE_WINDOW_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_WINDOW_V1"
AUTHORITY_POST_WINDOW_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_POST_EXPORT_AUTHORITY_WINDOW_V1"
AUTHORITY_PRE_CHILD_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_PENDING_CHILD_CLOSE_V1"
AUTHORITY_POST_CHILD_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_POST_EXPORT_AUTHORITY_PENDING_CHILD_CLOSE_V1"
CRYPTO_CHILD_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_CRYPTO_PENDING_CHILD_CLOSE_V1"
AUTHORITY_PRE_ACK_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_POST_CLOSE_ACK_V1"
AUTHORITY_POST_ACK_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_POST_EXPORT_AUTHORITY_POST_CLOSE_ACK_V1"
CRYPTO_ACK_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_CRYPTO_POST_CLOSE_ACK_V1"
CRYPTO_CONTEXT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_FINAL_CRYPTO_CONTEXT_V1"
EXPORT_OUTPUT_FIELDS = ("initialProductiveExportTransferSha256", "initialProductiveManifestSha256")
COLLECT_OUTPUT_FIELDS = ("initialProductiveCollectCloseSha256", "initialProductiveManifestSha256")
EXPORT_OUTPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_EXPORT_PENDING_ORIGINAL_STEP_RETURN_V1"
COLLECT_OUTPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_COLLECT_PENDING_ORIGINAL_STEP_RETURN_V1"
CUSTODY_RETURN_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_CUSTODY_RETURN_PENDING_WRITER_CLOSE_V1"
EXPORT_TRANSFER_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_EXPORT_TRANSFER_PENDING_ORIGINAL_STEP_RETURN_V1"
POST_AUTHORITY_RETURN_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_POST_AUTHORITY_RETURN_PENDING_WRITER_CLOSE_V1"
POST_AUTHORITY_INDEX_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_POST_AUTHORITY_INDEX_PENDING_WRITER_CLOSE_V1"
COLLECT_CLOSE_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_COLLECT_CLOSE_PENDING_ORIGINAL_STEP_RETURN_V1"
PRE_AUTHORITY_RETURN_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_CLOSED_HISTORY_V1"
PRE_AUTHORITY_INDEX_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_INDEX_V1"
AUTHORITY_PENDING_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PRE_EXPORT_AUTHORITY_PENDING_OWNER_CLOSE_V1"
FINAL_INPUTS_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_FINAL_INPUTS_BINDING_V1"
MAP_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_GROUP_PENDING_MAP_WRITER_CLOSE_V1"
INDEX_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_FIXED30_INDEX_PENDING_WRITER_CLOSE_V1"
PRE_INDEX_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_PARENT28_INDEX_PENDING_WRITER_CLOSE_V1"
CRYPTO_INPUTS = (
    ("final-inputs.json", LIMIT), ("pre-export-copy-index.json", PUBLIC_LIMIT),
    ("authority-return.json", LIMIT), ("authority-index.json", LIMIT),
    ("original-match.json", PUBLIC_LIMIT), ("fresh-match.json", PUBLIC_LIMIT),
    ("event.json", LIMIT), ("candidate-policy.json", 96 * 1024), ("recipient-public.asc", PUBLIC_LIMIT),
)
LATER_FILES = (
    "productive-custody-return.json", "productive-export-transfer.json",
    "productive-post-authority-return.json", "productive-post-authority-index.json",
    "productive-collect-close.json",
)
FINAL_CLAIMS = (*D.SAVE_CLAIMS, "AFTER_SAVE_OUTCOME", "AFTER_SAVE_SHA256", "PROBE_PREPARE_OUTCOME",
    "PROBE_PREPARATION_SHA256", "PROBE_OUTCOME", "PROBE_READBACK_SHA256", "AFTER_PROBE_OUTCOME", "PROBE_SHA256")
EXPORT_CLAIMS = (
    "P2PKIT_INITIAL_PRODUCTIVE_EXPORT_OUTCOME", "P2PKIT_INITIAL_PRODUCTIVE_EXPORT_TRANSFER_SHA256",
    "P2PKIT_INITIAL_PRODUCTIVE_MANIFEST_SHA256",
)
PREDECESSOR_PRE_FIELDS = (
    "producerStepOutcome producerHandoffSha256 producerReturnSha256 afterSaveStepOutcome afterSaveSha256 "
    "afterProbeStepOutcome probeSha256 prefixRetentionSha256"
)
PREDECESSOR_POST_FIELDS = (
    "step stepOutcome exportTransferSha256 manifestSha256 custodyReturnSha256 copyIndexSha256 "
    "preExportReturnSha256 preExportIndexSha256"
)


def require(value, reason):
    O.require(value, "INITIAL_PRODUCTIVE_FINAL_DATA_" + reason)


def fields(value, names):
    expected = names.split() if type(names) is str else names
    require(type(value) is dict and all(type(key) is str for key in value) and set(value) == set(expected), "FIELDS")
    return value


def integer(value, minimum=0, maximum=None):
    maximum = O.clocks.UINT64 if maximum is None else maximum
    require(type(value) is int and minimum <= value <= maximum, "INTEGER")
    return value


def local(value):
    require(type(value) is float and math.isfinite(value) and value >= 0, "LOCAL")
    return value


def sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "DIGEST")
    return value


def job(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None, "JOB")
    return value


def canonical(raw, maximum=LIMIT):
    require(type(raw) is bytes and len(raw) <= maximum, "RAW_BOUND")
    value = O.parse(raw)
    require(O.encoded(value) == raw, "CANONICAL")
    return value


def nonacceptance(value):
    require(value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "NONACCEPTANCE")


def authority_caps(caps, window=None):
    require(type(caps) is tuple and len(caps) == 6, "AUTHORITY_CAPS")
    first, work, final, began, phase_work, phase_final = tuple(integer(value) for value in caps)
    require(first <= began < phase_work <= work <= final and phase_final == min(final, phase_work + 45 * NS) and
        phase_work == min(work, began + 45 * NS), "AUTHORITY_PHASE_CAPS")
    if window is not None:
        require(caps[:3] == tuple(window[name] for name in FINAL_AUTHORITY_CAP_FIELDS[:3]), "AUTHORITY_WINDOW_CAPS")
    return caps


def crypto_caps(caps):
    require(type(caps) is tuple and len(caps) == 7, "CRYPTO_CAPS")
    freeze, work, final, read, began, native_work, native_final = tuple(integer(value) for value in caps)
    require(began < freeze <= work <= final <= read and began < native_work <= min(work, began + 210 * NS) and
        native_work <= native_final <= min(final, native_work + 45 * NS), "CRYPTO_ORIGINAL_CAPS")
    return caps


def _authority_context(raw, *, post):
    value = fields(canonical(raw), FINAL_AUTHORITY_CONTEXT_FIELDS)
    window = fields(value["authorityWindow"], FINAL_AUTHORITY_WINDOW_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and type(window["schema"]) is int and
        window["schema"] == 1 and value["kind"] == "worker" and
        value["scope"] == (AUTHORITY_POST_CONTEXT_SCOPE if post else AUTHORITY_PRE_CONTEXT_SCOPE) and
        value["edge"] == ("POST_EXPORT" if post else "PRE_EXPORT") and
        window["scope"] == (AUTHORITY_POST_WINDOW_SCOPE if post else AUTHORITY_PRE_WINDOW_SCOPE) and
        window["phase"] == ("ciphertext-verify" if post else "custody-freeze"), "AUTHORITY_SCOPE")
    nonacceptance(value)
    nonacceptance(window)
    clock = O.wire.clock_identity(window["clock"])
    job(value["job"])
    for name in ("eventSha256", "sourceReturnSha256"):
        sha(value[name])
    sha(window["originalBootDigest"])
    require(sha(window["originalProposalSha256"]) == O.digest(O.encoded(value["originalProposal"])), "PROPOSAL_HASH")
    for name in ("originalJobBasisNs", "phaseFirstNs", "phaseEndNs", *FINAL_AUTHORITY_CAP_FIELDS[:3]):
        integer(window[name])
    require(window["originalJobBasisNs"] <= window["phaseFirstNs"] <= window["authorityFirstNs"] <=
        integer(value["sourceReturnedNs"]) < window["authorityWorkEndNs"] <= window["authorityFinalEndNs"] <=
        window["phaseEndNs"], "AUTHORITY_WINDOW_ORDER")
    history = fields(value["history"], D.HISTORY_FIELDS)
    require(history["kind"] == "worker" and history["observed"] == value["observed"] and
        history["clock"] == window["clock"] and history["originalBootDigest"] == window["originalBootDigest"] and
        history["originalJobBasisNs"] == window["originalJobBasisNs"] and history["currentAuthority"] == "NOT_ACQUIRED" and
        history["matchSha256"] == O.digest(O.encoded(value["expectedMatch"])) and
        value["observed"]["role"] == clock.role and value["observed"]["kind"] == "worker" and
        len(O.encoded(value["observed"])) <= PUBLIC_LIMIT, "AUTHORITY_ORIGINAL_HISTORY")
    nonacceptance(history)
    predecessor = fields(value["predecessor"], PREDECESSOR_POST_FIELDS if post else PREDECESSOR_PRE_FIELDS)
    for name, item in predecessor.items():
        if name.endswith("Sha256"):
            sha(item)
        elif name == "step":
            require(item == "custody-export", "PREDECESSOR_STEP")
        else:
            require(item == "success", "PREDECESSOR_OUTCOME")
    require(type(value["root"]) is str and type(value["session"]) is str and
        type(value["directoryIdentity"]) is list and type(value["inheritedContext"]) is dict and
        all(type(key) is str and type(item) is str for key, item in value["inheritedContext"].items()), "AUTHORITY_PATH_DATA")
    return value


def authority_pre_context(raw):
    return _authority_context(raw, post=False)


def authority_post_context(raw):
    return _authority_context(raw, post=True)


def _authority_window(value, *, post):
    _record(value, FINAL_AUTHORITY_WINDOW_FIELDS,
        AUTHORITY_POST_WINDOW_SCOPE if post else AUTHORITY_PRE_WINDOW_SCOPE)
    O.wire.clock_identity(value["clock"])
    sha(value["originalBootDigest"])
    sha(value["originalProposalSha256"])
    require(value["phase"] == ("ciphertext-verify" if post else "custody-freeze"), "AUTHORITY_RETURN_PHASE")
    for name in ("originalJobBasisNs", "phaseFirstNs", "phaseEndNs", *FINAL_AUTHORITY_CAP_FIELDS[:3]):
        integer(value[name])
    require(value["originalJobBasisNs"] <= value["phaseFirstNs"] <= value["authorityFirstNs"] <
        value["authorityWorkEndNs"] <= value["authorityFinalEndNs"] <= value["phaseEndNs"],
        "AUTHORITY_RETURN_WINDOW")
    return value


def _predecessor(value, *, post):
    fields(value, PREDECESSOR_POST_FIELDS if post else PREDECESSOR_PRE_FIELDS)
    for name, item in value.items():
        if name.endswith("Sha256"):
            sha(item)
        elif name == "step":
            require(item == "custody-export", "PREDECESSOR_STEP")
        else:
            require(type(item) is str and item == "success", "PREDECESSOR_SUCCESS")
    return value


def owner_close(value, *, native_owner=False):
    fields(value, "schema scope resources retirement exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        ("INITIAL_PRODUCTIVE_FINAL_NATIVE_OWNER_CLOSE_V1" if native_owner else "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1") and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["exportSaveAuthority"] is False and
        type(value["resources"]) is list and 0 < len(value["resources"]) <= MAX_NODES, "OWNER_CLOSE_DATA")
    for index, row in enumerate(value["resources"]):
        fields(row, "ordinal label closeAttempted closed")
        require(type(row["ordinal"]) is int and row["ordinal"] == index and type(row["label"]) is str and
            0 < len(row["label"]) <= 256 and row["closeAttempted"] is row["closed"] is True,
            "OWNER_CLOSE_ROW_DATA")
    return value


_AUTHORITY_ORIGINAL_KEYS = ("event", *D.SOURCE_KEYS, "attempt", "jobs", "approvals", "comment", "environment",
    "branches", "main", "reviewed_ref", "observation", "match")
_NATIVE_FILES = ("start.json", "result.json", "baseline.json", "native-start.json", "stdout.log", "stderr.log")


def _authority_original_names(*, post):
    names = {"context.json", "service/child-result.json", "acquisition-queries/session-result.json",
        *("service/" + name for name in _NATIVE_FILES),
        *("acquisition-queries/" + name + ".bin" for name in _AUTHORITY_ORIGINAL_KEYS),
        *(side + "/" + name for side in ("source-before", "source-after")
          for name in ("session-result.json", "source-return.json", *(key + ".bin" for key in D.SOURCE_KEYS)))}
    if not post:
        names.update(("authority-window.json", "authority-pending.json"))
    require(len(names) == (36 if post else 38), "AUTHORITY_ACTUAL_ORIGINAL_ROSTER")
    return names


def authority_index(raw, *, post):
    require(type(post) is bool, "AUTHORITY_EDGE_BOOL")
    value = _record(canonical(raw), "schema scope edge root clock contextSha256 pendingSha256 files directories "
        "fileCount directoryCount retainedOriginalCount totalBytes copyState writerReturn budgetAcceptance exportSaveAuthority",
        POST_AUTHORITY_INDEX_SCOPE if post else PRE_AUTHORITY_INDEX_SCOPE)
    clock = O.wire.clock_identity(value["clock"])
    require(value["edge"] == ("POST_EXPORT" if post else "PRE_EXPORT") and type(value["root"]) is str and
        value["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and value["writerReturn"] == PENDING,
        "AUTHORITY_INDEX_STATE")
    sha(value["contextSha256"])
    require(value["pendingSha256"] is None if post else sha(value["pendingSha256"]), "AUTHORITY_INDEX_PENDING")
    require(type(value["files"]) is list and len(value["files"]) == (279 if post else 281) and
        type(value["directories"]) is list and len(value["directories"]) == 58,
        "AUTHORITY_DECLARED_ROSTER")
    originals = _authority_original_names(post=post)
    names, total = [], 0
    for row in value["files"]:
        fields(row, "relative maximum bytes sha256 provenance")
        name = relative(row["relative"])
        integer(row["maximum"], 1, LIMIT)
        total += integer(row["bytes"], 0, row["maximum"])
        sha(row["sha256"])
        require(row["bytes"] != 0 or row["sha256"] == O.digest(b""), "AUTHORITY_EMPTY_HASH")
        if name == "service/stdout.log":
            maximum = 16384
        elif name == "service/stderr.log":
            maximum = 65536
        elif "/query-" in name and name.endswith("/stderr.log"):
            maximum = 4096
        elif name.startswith(("source-before/", "source-after/", "acquisition-queries/")) and not name.endswith(
                ("/session-result.json", "/source-return.json", "/stdout.log")):
            maximum = max(1, row["bytes"])
        elif name in originals:
            maximum = LIMIT
        else:
            maximum = row["maximum"]  # Exact per-query stdout cap is joined to its original session by PC/N.
        require(row["maximum"] == maximum, "AUTHORITY_ORIGINAL_FILE_MAXIMUM")
        require(row["provenance"] == ("ACTUAL_RETAINED_BYTES" if name in originals else "ORIGINAL_QUERY_DECLARATION"),
            "AUTHORITY_DECLARATION_IS_NOT_NATIVE_CUSTODY")
        names.append(name)
    require(names == sorted(names) and len(set(names)) == len({name.casefold() for name in names}) == len(names) and
        originals.issubset(names) and type(value["totalBytes"]) is int and value["totalBytes"] == total <= MAX_BYTES,
        "AUTHORITY_FILE_ROSTER")
    pinned = {".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"}
    directories, identities = [], []
    for row in value["directories"]:
        fields(row, "relative identity provenance")
        name = row["relative"]
        require(name == "." or relative(name) == name, "AUTHORITY_DIRECTORY_NAME")
        if name in pinned:
            identities.append(D.native_identity(row["identity"], clock.role))
            require(row["provenance"] == "ORIGINAL_NATIVE_PIN", "AUTHORITY_DIRECTORY_PIN")
        else:
            require(row["identity"] is None and row["provenance"] == "ORIGINAL_QUERY_DECLARATION",
                "AUTHORITY_UNOBSERVED_DIRECTORY")
        directories.append(name)
    require(directories == sorted(directories) and len(set(directories)) == 58 and pinned.issubset(directories) and
        len(identities) == len(set(identities)) == 7 and type(value["fileCount"]) is int and
        value["fileCount"] == len(names) and type(value["directoryCount"]) is int and value["directoryCount"] == 58 and
        type(value["retainedOriginalCount"]) is int and value["retainedOriginalCount"] == len(originals),
        "AUTHORITY_COUNTS_DISTINCT_FROM_OBSERVATIONS")
    expected_directories, query_files = set(pinned), set()
    for section, count in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
        expected_directories.add(section + "/query-home")
        children = {name for name in directories if re.fullmatch(section + r"/query-[0-9a-f]{32}", name)}
        require(len(children) == count, "AUTHORITY_EXACT12_24_12_QUERY_ROSTER")
        expected_directories.update(children)
        query_files.update(child + "/" + name for child in children for name in
            ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"))
        query_files.add(section + "/owner.json")
    require(set(directories) == expected_directories and set(names) == originals | query_files,
        "AUTHORITY_COMPLETE_DECLARATIONS_NOT_ARBITRARY_COUNTS")
    return value


def authority_return(raw, *, post):
    require(type(post) is bool, "AUTHORITY_EDGE_BOOL")
    value = _record(canonical(raw), "schema scope edge contextSha256 authorityWindow predecessor workerIdentitySha256 "
        "matchSha256 inventorySha256 filesSha256 originalChain preCloseNs closedNs ownerClose retirement writerReturn "
        "budgetAcceptance exportSaveAuthority", POST_AUTHORITY_RETURN_SCOPE if post else PRE_AUTHORITY_RETURN_SCOPE)
    require(value["edge"] == ("POST_EXPORT" if post else "PRE_EXPORT") and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["writerReturn"] == PENDING,
        "AUTHORITY_RETURN_STATE")
    window = _authority_window(value["authorityWindow"], post=post)
    _predecessor(value["predecessor"], post=post)
    for name in ("contextSha256", "workerIdentitySha256", "matchSha256", "inventorySha256"):
        sha(value[name])
    fields(value["filesSha256"], _authority_original_names(post=post))
    for checksum in value["filesSha256"].values():
        sha(checksum)
    chain = fields(value["originalChain"], "phaseSha256 childSha256 querySessionSha256 originalsSha256 checkedNs sourceAfterSha256")
    fields(chain["phaseSha256"], _NATIVE_FILES)
    fields(chain["originalsSha256"], _AUTHORITY_ORIGINAL_KEYS)
    for checksum in (*chain["phaseSha256"].values(), *chain["originalsSha256"].values(), chain["childSha256"],
            chain["querySessionSha256"], chain["sourceAfterSha256"]):
        sha(checksum)
    require(value["contextSha256"] == value["filesSha256"]["context.json"] and
        value["matchSha256"] == chain["originalsSha256"]["match"] == value["filesSha256"]["acquisition-queries/match.bin"] and
        all(value["filesSha256"]["service/" + name] == checksum for name, checksum in chain["phaseSha256"].items()) and
        value["filesSha256"]["service/child-result.json"] == chain["childSha256"] and
        value["filesSha256"]["acquisition-queries/session-result.json"] == chain["querySessionSha256"] and
        value["filesSha256"]["source-after/source-return.json"] == chain["sourceAfterSha256"],
        "AUTHORITY_RETURN_ORIGINAL_HASHES")
    require(window["authorityFirstNs"] <= integer(chain["checkedNs"]) <= integer(value["preCloseNs"]) <=
        integer(value["closedNs"]) < window["authorityFinalEndNs"], "AUTHORITY_RETURN_CHRONOLOGY")
    owner_close(value["ownerClose"], native_owner=True)
    return value


def output_values(value, *, collect=False):
    names = COLLECT_OUTPUT_FIELDS if collect else EXPORT_OUTPUT_FIELDS
    require(type(value) is tuple and len(value) == 2, "OUTPUT_TUPLE")
    for row, name in zip(value, names):
        require(type(row) is tuple and len(row) == 2 and type(row[0]) is str and row[0] == name, "OUTPUT_SLOT")
        sha(row[1])
    return value


def native(value, *, directory):
    require(type(directory) is bool and type(value) is tuple and value, "NATIVE_TUPLE")
    if value[0] == "posix":
        require(len(value) == 9 and all(type(item) is int for item in value[1:]) and
            value[1] >= 0 and value[2] > 0 and value[4] >= 0 and value[5] >= 1 and value[6] >= 0 and
            (value[3] & 0o170000) == (0o040000 if directory else 0o100000) and
            (directory or value[5] == 1), "POSIX_NATIVE")
    else:
        require(value[0] == "windows" and len(value) == 12 and type(value[3]) is bool and value[3] is directory and
            type(value[2]) is str and re.fullmatch(r"[0-9a-f]{32}", value[2]) is not None and
            all(type(value[index]) is int and value[index] >= 0 for index in (1, 4, 5, 6, 7, 8, 9)) and
            value[5] >= 1 and (directory or value[5] == 1) and not value[6] & 0x400 and
            (value[10] is None or type(value[10]) is str) and (value[11] is None or type(value[11]) is bool),
            "WINDOWS_NATIVE")
    return value


def native_key(value):
    require(type(value) is tuple and value[0] in ("posix", "windows"), "NATIVE_KEY")
    return value[:3]


def member_name(ordinal):
    integer(ordinal, 0, MAX_NODES - 1)
    return "member-" + str(ordinal).zfill(5) + ".bin"


def relative(value, *, empty=False):
    require(type(value) is str and (empty and value == "" or value and len(value) <= 4096 and
        all(part not in ("", ".", "..") and len(part) <= 64 and
            re.fullmatch(r"[A-Za-z0-9_.-]+", part) is not None for part in value.split("/")) and
        len(value.split("/")) <= 64), "RELATIVE")
    return value


def node_data(node):
    fields(node, "relative kind bytes sha256 native")
    relative(node["relative"], empty=True)
    require(node["kind"] in ("file", "directory") and type(node["native"]) is list, "NODE")
    directory = node["kind"] == "directory"
    stamp = native(tuple(node["native"]), directory=directory)
    if directory:
        require(node["bytes"] is None and node["sha256"] is None, "DIRECTORY_SENTINELS")
    else:
        integer(node["bytes"], 0, MAX_BYTES)
        sha(node["sha256"])
        require(node["bytes"] == stamp[6 if stamp[0] == "posix" else 4], "NODE_SIZE")
    return node


def map_record(raw, ordinal):
    integer(ordinal, 1, 30)
    value = fields(canonical(raw), "schema scope ordinal group root members sourceDirectories dataBytes dataFiles "
        "dataOwnerClose writerReturn budgetAcceptance exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == MAP_SCOPE and
        type(value["ordinal"]) is int and value["ordinal"] == ordinal and value["group"] == GROUPS[ordinal - 1] and
        value["writerReturn"] == PENDING and type(value["members"]) is list and
        0 < len(value["members"]) < MAX_NODES and type(value["sourceDirectories"]) is list, "MAP_SCOPE")
    nonacceptance(value)
    root = node_data(value["root"])
    require(root["relative"] == GROUPS[ordinal - 1] and root["kind"] == "directory", "MAP_ROOT")
    count = 0
    for index, row in enumerate(value["members"]):
        fields(row, "ordinal source sourceKind maximum bytes sha256 sourceNative writerNative destination provenance")
        require(type(row["ordinal"]) is int and row["ordinal"] == index and
            row["sourceKind"] in ("native-file", "embedded-not-disk") and type(row["source"]) is str and
            type(row["provenance"]) is str, "MAP_MEMBER")
        integer(row["maximum"], 1, MAX_BYTES)
        integer(row["bytes"], 0, row["maximum"])
        sha(row["sha256"])
        target = node_data(row["destination"])
        require(target["relative"] == GROUPS[ordinal - 1] + "/" + member_name(index) and
            target["kind"] == "file" and target["bytes"] == row["bytes"] and target["sha256"] == row["sha256"], "MAP_TARGET")
        if row["sourceKind"] == "native-file":
            require(type(row["sourceNative"]) is list, "MAP_SOURCE_NATIVE")
            native(tuple(row["sourceNative"]), directory=False)
        else:
            require(row["sourceNative"] is None, "EMBEDDED_NOT_DISK")
        require(type(row["writerNative"]) is dict, "ORIGINAL_WRITER_METADATA")
        count += row["bytes"]
    require(type(value["dataBytes"]) is int and value["dataBytes"] == count <= MAX_BYTES and
        type(value["dataFiles"]) is int and value["dataFiles"] == len(value["members"]), "MAP_TOTAL")
    for row in value["sourceDirectories"]:
        fields(row, "path native provenance")
        require(type(row["path"]) is str and type(row["provenance"]) is str and type(row["native"]) is list,
            "MAP_DIRECTORY")
        native(tuple(row["native"]), directory=True)
    close = owner_close(value["dataOwnerClose"])
    require(close["scope"] == "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False and
        type(close["resources"]) is list and 0 < len(close["resources"]) <= MAX_NODES, "MAP_DATA_CLOSE")
    for index, row in enumerate(close["resources"]):
        fields(row, "ordinal label closeAttempted closed")
        require(type(row["ordinal"]) is int and row["ordinal"] == index and row["closeAttempted"] is True and
            row["closed"] is True and row["label"] in ("directory", "reader", "writer", "snapshot", "embedded-reader"),
            "MAP_DATA_CLOSE_ROW")
    return value


FINAL_INPUT_FIELDS = (
    "schema scope kind observed history originalProposal claims workerIdentity originalMatchSha256 freshMatchSha256 "
    "producerHandoffSha256 producerReturnSha256 afterSaveSha256 probeSha256 prefixRetentionSha256 compatibilityInputsSha256 "
    "preExportReturnSha256 preExportIndexSha256 preExportCopyIndexSha256 sourceRecordsSha256 "
    "inputProvenance budgetAcceptance exportSaveAuthority"
)
CRYPTO_CONTEXT_FIELDS = (
    "schema scope kind root session job observed history originalProposal clock originalBootDigest originalJobBasisNs "
    "phaseFirstNs phaseEndsNs inputs directories inheritedContext parent28Sha256 finalInputsSha256 "
    "budgetAcceptance exportSaveAuthority"
)
GROUP_REFERENCE_FIELDS = "ordinal group map dataFiles dataBytes"
INDEX_FIELDS = (
    "schema scope kind groups dataFiles dataBytes mapFiles mapBytes indexFiles archiveFilesBeforeIndex "
    "archiveNativeNodesBeforeIndex plaintextBytesBeforeIndex contextSha256 startSha256 parent28Sha256 "
    "reads writerReturn budgetAcceptance exportSaveAuthority"
)
PRE_INDEX_FIELDS = (
    "schema scope kind groups dataFiles dataBytes mapFiles mapBytes prefixRetentionSha256 "
    "preExportReturnSha256 preExportIndexSha256 writerReturn budgetAcceptance exportSaveAuthority"
)
MANIFEST_INPUT_FIELDS = "schema scope kind selection source github policy initialRecipient productive copy"
MANIFEST_FIELDS = (MANIFEST_INPUT_FIELDS + " recipient artifact testAcceptance productiveAuthority cacheAuthority "
    "exportSaveAuthority budgetAcceptance")
CUSTODY_RETURN_FIELDS = (
    "schema scope operation contextSha256 startSha256 childSha256 nativeRecordsSha256 nativePhase "
    "nativeOwnerClose manifestSha256 copyIndexSha256 preExportReturnSha256 preExportIndexSha256 "
    "parent28Sha256 claims authorityClosedNs returnedNs writerReturn originalStepOutcome "
    "budgetAcceptance exportSaveAuthority"
)
TRANSFER_FIELDS = (
    "schema scope operation custodyReturnSha256 manifestSha256 copyIndexSha256 preExportReturnSha256 "
    "preExportIndexSha256 contextSha256 parent28Sha256 custodyWriterCloseSha256 returnedNs "
    "originalStepOutcome writerReturn budgetAcceptance exportSaveAuthority"
)
COLLECT_FIELDS = (
    "schema scope operation originalExportStepOutcome exportTransferSha256 manifestSha256 custodyReturnSha256 "
    "copyIndexSha256 preExportReturnSha256 preExportIndexSha256 postExportReturnSha256 postExportIndexSha256 "
    "postWriterCloseSha256 originalReadsSha256 finalRead30Sha256 ciphertextReadSha256 "
    "ownerClosesSha256 returnedNs originalStepOutcome writerReturn budgetAcceptance exportSaveAuthority"
)


def _record(value, names, scope):
    fields(value, names)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope, "RECORD_SCOPE")
    nonacceptance(value)
    return value


def file_reference(value, name, maximum=LIMIT):
    fields(value, "name bytes sha256")
    require(value["name"] == name, "FILE_REFERENCE_NAME")
    integer(value["bytes"], 1, maximum)
    sha(value["sha256"])
    return value


def group_references(values, count):
    require(type(values) is list and len(values) == count and count in (28, 30), "GROUP_REFERENCE_ROSTER")
    for ordinal, value in enumerate(values, 1):
        fields(value, GROUP_REFERENCE_FIELDS)
        require(type(value["ordinal"]) is int and value["ordinal"] == ordinal and
            value["group"] == GROUPS[ordinal - 1], "GROUP_REFERENCE_ORDER")
        file_reference(value["map"], "map-" + value["group"] + ".json")
        files = integer(value["dataFiles"], 1, MAX_NODES)
        integer(value["dataBytes"], 0, MAX_BYTES)
        if ordinal <= 21 or ordinal in (24, 28):
            require(files == 281, "GROUP281")
        elif ordinal == 22:
            require(1373 <= files <= 1438, "PRIMARY1364_PLUS_C0")
        elif ordinal in (23, 25, 26, 29):
            require(files == {23: 6, 25: 114, 26: 3, 29: 9}[ordinal], "FIXED_GROUP_COUNT")
        elif ordinal == 27:
            require(7 <= files <= 813, "RETAINED_CONFIGURATION_COUNT")
        else:
            require(12 <= files <= 77, "VALIDATION_C1_PLUS3")
    return values


def pre_index(raw):
    value = _record(canonical(raw, PUBLIC_LIMIT), PRE_INDEX_FIELDS, PRE_INDEX_SCOPE)
    require(value["kind"] == "worker" and value["writerReturn"] == PENDING, "PRE_INDEX_STATE")
    groups = group_references(value["groups"], 28)
    expected = {"dataFiles": sum(row["dataFiles"] for row in groups), "dataBytes": sum(row["dataBytes"] for row in groups),
        "mapFiles": 28, "mapBytes": sum(row["map"]["bytes"] for row in groups)}
    require(all(type(value[name]) is int and value[name] == number for name, number in expected.items()) and
        value["dataBytes"] + value["mapBytes"] <= MAX_BYTES and value["dataFiles"] + 57 <= MAX_NODES,
        "PARENT28_TOTAL")
    for name in ("prefixRetentionSha256", "preExportReturnSha256", "preExportIndexSha256"):
        sha(value[name])
    return value


def final_index(raw):
    value = _record(canonical(raw), INDEX_FIELDS, INDEX_SCOPE)
    require(value["kind"] == "worker" and value["writerReturn"] == PENDING and type(value["reads"]) is list and
        len(value["reads"]) == 30, "INDEX_STATE")
    groups = group_references(value["groups"], 30)
    data_files = sum(row["dataFiles"] for row in groups)
    data_bytes = sum(row["dataBytes"] for row in groups)
    map_bytes = sum(row["map"]["bytes"] for row in groups)
    expected = {"dataFiles": data_files, "dataBytes": data_bytes, "mapFiles": 30, "mapBytes": map_bytes,
        "indexFiles": 0, "archiveFilesBeforeIndex": data_files + 30, "archiveNativeNodesBeforeIndex": data_files + 61,
        "plaintextBytesBeforeIndex": data_bytes + map_bytes}
    require(all(type(value[name]) is int and value[name] == number for name, number in expected.items()) and
        data_bytes + map_bytes + len(raw) <= MAX_BYTES and data_files + 62 <= MAX_NODES, "INDEX_TOTALS")
    for ordinal, read in enumerate(value["reads"], 1):
        fields(read, "ordinal mapSha256 readCloseSha256 returnedNs")
        require(type(read["ordinal"]) is int and read["ordinal"] == ordinal and
            read["mapSha256"] == groups[ordinal - 1]["map"]["sha256"], "INDEX_ORIGINAL_READ")
        sha(read["readCloseSha256"])
        integer(read["returnedNs"])
    for name in ("contextSha256", "startSha256", "parent28Sha256"):
        sha(value[name])
    return value


def _claims(value):
    fields(value, FINAL_CLAIMS)
    for name, item in value.items():
        if name.endswith("OUTCOME"):
            require(type(item) is str and item == "success", "ORIGINAL_STEP_SUCCESS")
        else:
            sha(item)
    return value


def final_inputs(raw):
    value = _record(canonical(raw), FINAL_INPUT_FIELDS, FINAL_INPUTS_SCOPE)
    require(value["kind"] == "worker" and value["inputProvenance"] == "ORIGINAL_FINAL_READER_AND_NEW_PRE_AUTHORITY" and
        type(value["observed"]) is dict and len(O.encoded(value["observed"])) <= PUBLIC_LIMIT,
        "FINAL_INPUT_STATE")
    claims = _claims(value["claims"])
    history = fields(value["history"], D.HISTORY_FIELDS)
    require(history["observed"] == value["observed"] and history["kind"] == value["observed"]["kind"] == "worker" and
        history["currentAuthority"] == "NOT_ACQUIRED", "FINAL_INPUT_HISTORY")
    nonacceptance(history)
    for name, item in value.items():
        if name.endswith("Sha256") and name != "sourceRecordsSha256":
            sha(item)
    expected = {"producerHandoffSha256": claims["HANDOFF_SHA256"], "producerReturnSha256": claims["PRODUCER_RETURN_SHA256"],
        "afterSaveSha256": claims["AFTER_SAVE_SHA256"], "probeSha256": claims["PROBE_SHA256"]}
    require(all(value[name] == item for name, item in expected.items()) and
        value["originalMatchSha256"] == history["matchSha256"] == value["freshMatchSha256"] and
        type(value["workerIdentity"]) is dict and type(value["originalProposal"]) is dict,
        "FINAL_INPUT_ORIGINAL_DIGESTS")
    fields(value["sourceRecordsSha256"], D.SOURCE_KEYS)
    for checksum in value["sourceRecordsSha256"].values():
        sha(checksum)
    return value


def crypto_context(raw):
    value = _record(canonical(raw, PUBLIC_LIMIT), CRYPTO_CONTEXT_FIELDS, CRYPTO_CONTEXT_SCOPE)
    job(value["job"])
    clock = O.wire.clock_identity(value["clock"])
    require(value["kind"] == "worker" and type(value["root"]) is str and type(value["session"]) is str and
        value["observed"]["kind"] == "worker" and value["observed"]["role"] == clock.role and
        len(O.encoded(value["observed"])) <= PUBLIC_LIMIT, "CRYPTO_CONTEXT_HOST")
    history = fields(value["history"], D.HISTORY_FIELDS)
    require(history["observed"] == value["observed"] and history["clock"] == value["clock"] and
        history["originalBootDigest"] == sha(value["originalBootDigest"]) and
        history["originalJobBasisNs"] == integer(value["originalJobBasisNs"]) and
        history["currentAuthority"] == "NOT_ACQUIRED", "CRYPTO_HISTORY_BINDING")
    nonacceptance(history)
    ends = fields(value["phaseEndsNs"], FINAL_CRYPTO_CAP_FIELDS[:4])
    numbers = [integer(ends[name]) for name in FINAL_CRYPTO_CAP_FIELDS[:4]]
    require(integer(value["originalJobBasisNs"]) <= integer(value["phaseFirstNs"]) < numbers[0] and
        numbers == sorted(numbers), "CRYPTO_PHASE_ENDS")
    fields(value["inputs"], tuple(name for name, _maximum in CRYPTO_INPUTS))
    for name, maximum in CRYPTO_INPUTS:
        file_reference(value["inputs"][name], name, maximum)
    require(value["inputs"]["final-inputs.json"]["sha256"] == sha(value["finalInputsSha256"]) and
        value["inputs"]["pre-export-copy-index.json"]["sha256"] == sha(value["parent28Sha256"]),
        "CRYPTO_PARENT_INPUT_HASHES")
    names = ("root", "returned", "control-home", "temporary", "crypto-service", "payload", "public-crypto")
    if clock.role == "windows-x64":
        names += ("export-output",)
    fields(value["directories"], names)
    pins = [D.native_identity(pin, clock.role) for pin in value["directories"].values()]
    require(len(set(pins)) == len(pins), "CRYPTO_DIRECTORY_ALIASES")
    require(type(value["inheritedContext"]) is dict and all(type(key) is type(item) is str
        for key, item in value["inheritedContext"].items()), "CRYPTO_ANCESTOR_DATA")
    return value


def public_manifest(raw):
    value = _record(canonical(raw, PUBLIC_LIMIT), MANIFEST_FIELDS,
        "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_EVIDENCE_V1")
    require(value["kind"] == "worker" and value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is value["cacheAuthority"] is False, "MANIFEST_NONACCEPTANCE")
    fields(value["source"], "commit tree")
    for item in value["source"].values():
        require(type(item) is str and re.fullmatch(r"[0-9a-f]{40}", item) is not None, "SOURCE_DIGEST")
    initial = fields(value["initialRecipient"], "authority environment originalBase reviewed firstUseAt notBefore expiresAt "
        "matchSha256 preExportReturnSha256 preExportIndexSha256")
    for name in ("matchSha256", "preExportReturnSha256", "preExportIndexSha256"):
        sha(initial[name])
    for name in ("firstUseAt", "notBefore", "expiresAt"):
        integer(initial[name])
    require(initial["notBefore"] <= initial["firstUseAt"] < initial["expiresAt"], "MANIFEST_POLICY_WINDOW")
    productive = fields(value["productive"], "originalProposalSha256 producerHandoffSha256 producerReturnSha256 "
        "producerStepOutcome afterSaveSha256 afterSaveStepOutcome probeSha256 afterProbeStepOutcome prefixRetentionSha256 "
        "compatibilityInputsSha256")
    for name, item in productive.items():
        if name.endswith("StepOutcome"):
            require(type(item) is str and item == "success", "MANIFEST_PRIOR_STEP")
        else:
            sha(item)
    copy = fields(value["copy"], "scope groups index dataFiles mapFiles indexFiles archiveFiles archiveNativeNodes plaintextBytes")
    require(copy["scope"] == "INITIAL_RECIPIENT_PRODUCTIVE_FIXED30_ARCHIVE_BINDING_V1", "MANIFEST_COPY_SCOPE")
    groups = group_references(copy["groups"], 30)
    file_reference(copy["index"], "copy-index.json")
    data_files = sum(row["dataFiles"] for row in groups)
    expected = {"dataFiles": data_files, "mapFiles": 30, "indexFiles": 1, "archiveFiles": data_files + 31,
        "archiveNativeNodes": data_files + 62,
        "plaintextBytes": sum(row["dataBytes"] + row["map"]["bytes"] for row in groups) + copy["index"]["bytes"]}
    require(all(type(copy[name]) is int and copy[name] == number for name, number in expected.items()) and
        copy["archiveNativeNodes"] <= MAX_NODES and copy["plaintextBytes"] <= MAX_BYTES, "MANIFEST_TOTALS")
    recipient = fields(value["recipient"], "fingerprint encryptionFingerprint keySha256 expiresAt")
    for name in ("fingerprint", "encryptionFingerprint"):
        require(type(recipient[name]) is str and re.fullmatch(r"[0-9A-F]{40}", recipient[name]) is not None,
            "RECIPIENT_FINGERPRINT")
    sha(recipient["keySha256"])
    integer(recipient["expiresAt"])
    require(initial["expiresAt"] <= recipient["expiresAt"], "RECIPIENT_LIFETIME")
    artifact = fields(value["artifact"], "name sha256 size")
    require(artifact["name"] == "evidence.tar.gz.gpg", "FIXED_ARTIFACT")
    sha(artifact["sha256"])
    integer(artifact["size"], 33, 576 * 1024 * 1024)
    return value


def custody_return(raw):
    value = _record(canonical(raw), CUSTODY_RETURN_FIELDS, CUSTODY_RETURN_SCOPE)
    require(value["operation"] == "custody-export" and value["writerReturn"] == PENDING and
        value["originalStepOutcome"] == "NOT_OBSERVED", "CUSTODY_PENDING_STEP")
    _claims(value["claims"])
    for name, item in value.items():
        if name.endswith("Sha256") and name != "nativeRecordsSha256":
            sha(item)
    for name in ("authorityClosedNs", "returnedNs"):
        integer(value[name])
    require(type(value["nativePhase"]) is list and len(value["nativePhase"]) == 3, "CUSTODY_NATIVE_PHASE")
    phase = tuple(integer(number) for number in value["nativePhase"])
    require(phase[0] < phase[1] <= phase[2] and value["authorityClosedNs"] <= phase[0] < value["returnedNs"],
        "CUSTODY_PRIOR_FACTS")
    fields(value["nativeRecordsSha256"], "start.json result.json baseline.json native-start.json stdout.log stderr.log")
    for checksum in value["nativeRecordsSha256"].values():
        sha(checksum)
    owner_close(value["nativeOwnerClose"], native_owner=True)
    return value


def export_transfer(raw):
    value = _record(canonical(raw), TRANSFER_FIELDS, EXPORT_TRANSFER_SCOPE)
    require(value["operation"] == "custody-export" and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["writerReturn"] == PENDING, "TRANSFER_PENDING_STEP")
    for name, item in value.items():
        if name.endswith("Sha256"):
            sha(item)
    integer(value["returnedNs"])
    return value


def collect_close(raw):
    value = _record(canonical(raw), COLLECT_FIELDS, COLLECT_CLOSE_SCOPE)
    require(value["operation"] == "custody-collect" and value["originalExportStepOutcome"] == "success" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["writerReturn"] == PENDING, "COLLECT_PENDING_STEP")
    for name, item in value.items():
        if name.endswith("Sha256"):
            sha(item)
    integer(value["returnedNs"])
    return value
