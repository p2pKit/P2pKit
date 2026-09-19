"""Dormant configuration report-inventory grammar, NOT a file collector.

Only supplied immutable records are inspected. No path is opened, clock sampled,
loader inspected, owner adopted, or producer/provider executed. Consistent data
cannot authenticate original execution, retirement, file bytes or single use.
The future same-call collector must own those observations and its original cap.
"""
from __future__ import annotations

import re

import hosted_cache_bootstrap_producer as producer


SCOPE = "BOOTSTRAP_CONFIGURATION_REPORT_INVENTORY_V1"
METADATA_BYTES = 4 * 1024 * 1024
REPORT_BYTES = 512 * 1024 * 1024
REPORT_ENTRIES = 20000
LOG_BYTES = 64 * 1024 * 1024
LOGS = ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log")
LIMITATION = "Changed bytes are not proof of test execution; use the unchanged product assessor."
# A deliberately narrower portable label grammar, not native path admission.
# Canonical inventories with unsupported names or too much metadata fail closed.
SOURCE_BYTES = 4096
COMPONENT_BYTES = 255
REPORT_DIRECTORY_DEPTH = 256
_DEVICES = frozenset(("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$")) | frozenset(
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
)


class CollectionError(ValueError):
    """Finite inventory refusal; never include supplied paths or record text."""


def require(condition, reason):
    if not condition:
        raise CollectionError(reason)


def _bytes(raw):
    require(type(raw) is bytes and 0 < len(raw) <= METADATA_BYTES, "BOOTSTRAP_COLLECTION_METADATA_BYTES")
    return raw


def _encoded(value):
    try:
        raw = producer.encoded(value)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise CollectionError("BOOTSTRAP_COLLECTION_METADATA_ENCODING") from None
    return _bytes(raw)


def _manifest(raw):
    # json.loads(bytes) can auto-detect UTF-16/32. The actual canonical writer
    # emits UTF-8; do not reinterpret NUL-bearing or BOM-prefixed originals.
    try:
        text = raw.decode("utf-8")
        require("\0" not in text and not text.startswith("\ufeff"), "BOOTSTRAP_COLLECTION_MANIFEST_ENCODING")
        value = producer.parse(raw)
    except (UnicodeError, producer.ProducerError):
        raise CollectionError("BOOTSTRAP_COLLECTION_MANIFEST_JSON") from None
    require(set(value) == {"schema", "records", "limitation"} and type(value["schema"]) is int and
            value["schema"] == 1 and value["limitation"] == LIMITATION, "BOOTSTRAP_COLLECTION_MANIFEST_FIELDS")
    require(type(value["records"]) is list and len(value["records"]) <= REPORT_ENTRIES,
            "BOOTSTRAP_COLLECTION_REPORT_ROSTER")
    return value


def _component(value):
    # Keep dependency-artifact names and their suppliers unchanged. Reports may
    # include spaces/$, but no normalization, shell or URL decoding is performed.
    require(0 < len(value) <= COMPONENT_BYTES and value not in (".", "..") and value[-1] not in " ." and
            all(32 <= ord(char) <= 126 and char not in '<>:"/\\|?*' for char in value),
            "BOOTSTRAP_COLLECTION_REPORT_COMPONENT")
    # Reserve device stems even with spaces before an extension. This lookup
    # does not normalize or replace the original report label.
    require(value.split(".", 1)[0].rstrip(" ").upper() not in _DEVICES, "BOOTSTRAP_COLLECTION_REPORT_DEVICE")


def _source(value):
    require(type(value) is str and 0 < len(value) <= SOURCE_BYTES, "BOOTSTRAP_COLLECTION_REPORT_SOURCE")
    parts = value.split("/")
    for part in parts:
        _component(part)
    # Fixed help has no -p/--project-dir and therefore no external fixture roots.
    if parts[:1] == ["build"]:
        report_index = 1
    elif parts[:2] == ["buildSrc", "build"]:
        report_index = 2
    elif len(parts) >= 3 and parts[0] in ("library", "samples") and parts[2] == "build":
        report_index = 3
    else:
        raise CollectionError("BOOTSTRAP_COLLECTION_REPORT_ROOT")
    require(len(parts) >= report_index + 2 and parts[report_index] in ("reports", "test-results"),
            "BOOTSTRAP_COLLECTION_REPORT_ROOT")
    require(len(parts) - report_index - 2 <= REPORT_DIRECTORY_DEPTH, "BOOTSTRAP_COLLECTION_REPORT_DEPTH")
    return parts, report_index


def _insert(tree, parts, report_index):
    """Linear-size trie: reject component aliases and file/directory conflicts.

    Count only newly declared report-tree nodes, not source-root ancestors.
    Unreported empty directories and removed outputs cannot be inferred here.
    """
    added = 0
    for index, part in enumerate(parts):
        key, terminal = part.casefold(), index == len(parts) - 1
        if key in tree:
            spelling, children = tree[key]
            require(spelling == part, "BOOTSTRAP_COLLECTION_REPORT_ALIAS")
            require(not terminal and children is not None, "BOOTSTRAP_COLLECTION_REPORT_PREFIX")
        else:
            children = None if terminal else {}
            tree[key] = (part, children)
            added += int(index >= report_index)
        tree = children
    return added


def _reports(rows):
    tree, previous, entries, total, retained_bytes = {}, None, 0, 0, 0
    retained = []
    for row in rows:
        require(type(row) is dict, "BOOTSTRAP_COLLECTION_REPORT_ROW")
        classification = row.get("classification")
        require(type(classification) is str and classification in ("changed-since-admission", "preexisting-unchanged"),
                "BOOTSTRAP_COLLECTION_REPORT_CLASSIFICATION")
        changed = classification == "changed-since-admission"
        require(set(row) == {"source", "sha256", "bytes", "classification"} | ({"retained"} if changed else set()),
                "BOOTSTRAP_COLLECTION_REPORT_FIELDS")
        source = row["source"]
        parts, report_index = _source(source)
        require(previous is None or previous < source, "BOOTSTRAP_COLLECTION_REPORT_ORDER")
        previous = source
        entries += _insert(tree, parts, report_index)
        require(entries <= REPORT_ENTRIES, "BOOTSTRAP_COLLECTION_REPORT_ENTRIES")
        size, sha = row["bytes"], row["sha256"]
        require(type(size) is int and 0 <= size <= REPORT_BYTES, "BOOTSTRAP_COLLECTION_REPORT_SIZE")
        require(type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha), "BOOTSTRAP_COLLECTION_REPORT_SHA256")
        require(size != 0 or sha == producer.digest(b""), "BOOTSTRAP_COLLECTION_EMPTY_REPORT_DIGEST")
        total += size  # The canonical snapshot includes unchanged rows too.
        require(total <= REPORT_BYTES, "BOOTSTRAP_COLLECTION_REPORT_BYTES")
        if changed:
            require(type(row["retained"]) is str and row["retained"] == "reports/" + source,
                    "BOOTSTRAP_COLLECTION_RETAINED_PATH")
            retained.append({"path": row["retained"], "bytes": size, "sha256": sha})
            retained_bytes += size
    return retained, {"reports": len(rows), "changedReports": len(retained),
        "preexistingReports": len(rows) - len(retained), "declaredReportBytes": total,
        "declaredRetainedReportBytes": retained_bytes, "minimumDeclaredArchiveEntries": entries}


def describe_inventory(request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw, manifest_raw, *, original_exit_code):
    """Return private data only, including requirements for NOT-YET-READ files.

    This accepts only a supplied successful configuration report. A failed
    producer still needs original failure custody; this positive grammar neither
    discards those originals nor supplies that separate failed-custody path.
    """
    for raw in (request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw, manifest_raw):
        _bytes(raw)
    observed = producer.observe_canonical(request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw,
                                         original_exit_code=original_exit_code)
    manifest = _manifest(manifest_raw)
    retained, counts = _reports(manifest["records"])
    # Comparing encoded values distinguishes true/1 and int/float while keeping
    # the original pretty manifest/receipt bytes, order and hashes intact.
    require(_encoded(manifest["records"]) == _encoded(producer.parse(receipt_raw)["reports"]),
            "BOOTSTRAP_COLLECTION_RECEIPT_REPORTS_CHANGED")
    bindings = {name: observed[name] for name in ("requestSha256", "admissionSha256", "canonicalContextSha256",
                                                "startSha256", "receiptSha256")}
    bindings.update(manifestSha256=producer.digest(manifest_raw), canonicalObservationSha256=producer.digest(
        producer.encoded(observed)))
    return _encoded({"schema": 1, "scope": SCOPE, "binding": bindings, "counts": counts,
        "requiredMetadata": [{"path": name, "bytes": len(raw), "sha256": producer.digest(raw)} for name, raw in
                             (("start.json", start_raw), ("receipt.json", receipt_raw), ("report-manifest.json", manifest_raw))],
        "requiredLogs": [{"path": name, "maximumBytes": LOG_BYTES, "observation": "NOT_READ"} for name in LOGS],
        "retainedReports": retained, "declaredReports": manifest["records"],
        "payloadByteCeilingExcludingMetadata": len(LOGS) * LOG_BYTES + counts["declaredRetainedReportBytes"],
        "limitation": LIMITATION, "inputProvenance": "SUPPLIED_RECORDS_ONLY",
        "collectionState": "NOT_PERFORMED", "noLoaderObservation": "NOT_OBSERVED",
        "actualArchiveEntryCount": "NOT_OBSERVED", "enclosingNativeRetirement": "NOT_OBSERVED_HERE",
        "producerScope": observed["producerScope"], "dependencyPopulation": "NOT_ATTESTED",
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "nextPhaseAuthority": False, "exportSaveAuthority": False})


def validate_inventory(value_raw, request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw, manifest_raw,
                       *, original_exit_code):
    """Exact rederivation of supplied data; no live-file or return authentication."""
    _bytes(value_raw)
    expected = describe_inventory(request_raw, admitted_raw, canonical_raw, start_raw, receipt_raw, manifest_raw,
                                  original_exit_code=original_exit_code)
    require(value_raw == expected, "BOOTSTRAP_COLLECTION_INVENTORY_CHANGED")
    return value_raw
