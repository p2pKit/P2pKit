#!/usr/bin/env python3
"""Closed FULL ABI byte/task assessment; no filesystem, process or build entrypoint.

The caller must acquire generated originals independently of immutable Git
references and bind this assessment to the original canonical producer. Matching
bytes alone are not execution, native qualification, or a passing FULL gate.
"""
from __future__ import annotations

import hashlib
import re

MIB = 1024 * 1024
FILE_LIMIT, TOTAL_LIMIT, LOG_LIMIT, LINE_LIMIT = MIB, 8 * MIB, 64 * MIB, 64 * 1024
# (module, generated below build/kotlin, reference below api, producer, compare)
ROUTES = (
    ("p2p-core", "androidAbi/p2p-core.api", "android/p2p-core.api", "buildAndroidAbi", "checkAndroidAbi"),
    ("p2p-core", "abi/jvm/p2p-core.api", "jvm/p2p-core.api", "internalDumpKotlinAbi", "checkKotlinAbi"),
    ("p2p-core", "abi/p2p-core.klib.api", "p2p-core.klib.api", "internalDumpKotlinAbi", "checkKotlinAbi"),
    ("p2p-network-provisioning-android", "androidAbi/p2p-network-provisioning-android.api",
     "android/p2p-network-provisioning-android.api", "buildAndroidAbi", "checkAndroidAbi"),
    ("p2p-network-provisioning-desktop", "abi/p2p-network-provisioning-desktop.api",
     "p2p-network-provisioning-desktop.api", "internalDumpKotlinAbi", "checkKotlinAbi"),
    ("p2p-transport-lan", "androidAbi/p2p-transport-lan.api", "android/p2p-transport-lan.api",
     "buildAndroidAbi", "checkAndroidAbi"),
    ("p2p-transport-lan", "abi/jvm/p2p-transport-lan.api", "jvm/p2p-transport-lan.api",
     "internalDumpKotlinAbi", "checkKotlinAbi"),
    ("p2p-transport-lan", "abi/p2p-transport-lan.klib.api", "p2p-transport-lan.klib.api",
     "internalDumpKotlinAbi", "checkKotlinAbi"),
)
BASELINES = tuple("library/" + module + "/api/" + baseline for module, _generated, baseline, *_rest in ROUTES)
GENERATED = tuple("library/" + module + "/build/kotlin/" + generated for module, generated, *_rest in ROUTES)
FRESH_TASKS = tuple(
    ":" + module + ":" + task
    for modules, tasks in (
        (("p2p-core", "p2p-network-provisioning-android", "p2p-transport-lan"),
         ("compileAndroidMain", "buildAndroidAbi", "checkAndroidPublicConstants", "checkAndroidAbi")),
        (("p2p-core",), ("compileKotlinJvm", "internalDumpKotlinAbi", "checkJvmPublicConstants", "checkKotlinAbi")),
        (("p2p-network-provisioning-desktop",),
         ("compileKotlin", "internalDumpKotlinAbi", "checkJvmPublicConstants", "checkKotlinAbi")),
        (("p2p-transport-lan",),
         ("compileKotlinJvm", "internalDumpKotlinAbi", "checkJvmPublicConstants", "checkKotlinAbi")),
        (("p2p-core", "p2p-transport-lan"),
         ("iosArm64MainKlibrary", "iosSimulatorArm64MainKlibrary", "iosX64MainKlibrary")),
        (("p2p-network-provisioning-android",), ("internalDumpKotlinAbi", "checkKotlinAbi")),
    ) for module in modules for task in tasks
)
FLAGS = ("--no-daemon", "--no-build-cache", "--no-configuration-cache", "--rerun-tasks",
         "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain")
FACTORY_LINE = (
    b"final fun dev.p2pkit.transport.lan/createIosOwnedFlowCollection(kotlinx.coroutines.flow/Flow<kotlin/Any?>, "
    b"kotlinx.coroutines.flow/FlowCollector<kotlin/Any?>): kotlinx.coroutines/Job // "
    b"dev.p2pkit.transport.lan/createIosOwnedFlowCollection|createIosOwnedFlowCollection("
    b"kotlinx.coroutines.flow.Flow<kotlin.Any?>;kotlinx.coroutines.flow.FlowCollector<kotlin.Any?>){}[0]\n"
)
ADDITIVE_SIZE = 6176
ADDITIVE_SHA256 = "b65028bae83c1046bc4a145000ed1b0dae6aa9dd5d9a615ea03b60e5963579a0"
PREIMAGE_SHA256 = "4d849ded7bfa892236706c499b0692d8fde6f243e91469f4745b840d2692c77c"


class AbiError(ValueError):
    """Finite private-assessment reason, not a platform/runtime verdict."""


def require(value, reason):
    if not value:
        raise AbiError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def member(index, role):
    require(type(index) is int and 0 <= index < len(ROUTES) and role in ("generated", "baseline"), "ABI_CLOSED_ROLE")
    return role + "-" + str(index).zfill(2) + ".bin"


def blob(raw):
    require(type(raw) is bytes and 0 < len(raw) <= FILE_LIMIT, "ABI_BYTE_BOUND")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def observe_log(stream, size, check):
    """Stream original bytes once; exact unsuffixed task records only.

    An echoed task is not independent trust from same-user candidate code. The
    original canonical receipt, native ownership, report token and source checks
    are mandatory caller boundaries, never inferred from this parser.
    """
    require(type(size) is int and 0 <= size <= LOG_LIMIT and callable(check), "ABI_LOG_BOUND")
    pending, total, number, count, hashed = b"", 0, 0, 0, hashlib.sha256()
    observations = {task: [] for task in FRESH_TASKS}

    def line(raw, complete=True):
        nonlocal number, count
        number += 1
        require(len(raw) <= LINE_LIMIT, "ABI_LOG_LINE_BOUND")
        # Accept normal LF/CRLF framing, never trim the task record itself.
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        matched = re.fullmatch(rb"\s*>\s*Task\s+(:[A-Za-z0-9:_-]+)(.*)", raw)
        if matched is None:
            return
        task = matched[1].decode("ascii")
        if task in observations:
            count += 1
            require(count <= 4 * len(FRESH_TASKS), "ABI_TASK_OBSERVATION_BOUND")
            observations[task].append({"line": number,
                "outcome": "EXECUTED" if complete and raw == b"> Task " + matched[1] else "NOT_FRESH_OR_MALFORMED"})

    while True:
        check()
        block = stream.read(64 * 1024)
        require(type(block) is bytes and len(block) <= 64 * 1024, "ABI_LOG_READER_BYTES")
        if not block:
            break
        total += len(block)
        require(total <= size, "ABI_LOG_GREW")
        hashed.update(block)
        parts = (pending + block).split(b"\n")
        pending = parts.pop()
        for part in parts:
            line(part)
        require(len(pending) <= LINE_LIMIT, "ABI_LOG_LINE_BOUND")
    if pending:
        line(pending, complete=False)  # EOF text is not a complete LF/CRLF task event.
    check()
    require(total == size, "ABI_LOG_TRUNCATED")
    return {"name": "product.stdout.log", "bytes": total, "sha256": hashed.hexdigest(),
            "tasks": [{"task": task, "observations": observations[task]} for task in FRESH_TASKS]}


def additive(raw):
    if raw is None:
        return {"status": "HOLD", "generatedBytes": None, "generatedSha256": None,
                "factoryLineSha256": digest(FACTORY_LINE), "completeLineOccurrences": 0, "preimageSha256": None}
    require(type(raw) is bytes and len(raw) <= FILE_LIMIT, "ABI_BYTE_BOUND")
    lines = raw.splitlines(keepends=True)
    occurrences = lines.count(FACTORY_LINE)
    preimage = digest(b"".join(line for line in lines if line != FACTORY_LINE)) if occurrences == 1 else None
    passed = len(raw) == ADDITIVE_SIZE and digest(raw) == ADDITIVE_SHA256 and preimage == PREIMAGE_SHA256
    return {"status": "PASS" if passed else "HOLD", "generatedBytes": len(raw), "generatedSha256": digest(raw),
            "factoryLineSha256": digest(FACTORY_LINE), "completeLineOccurrences": occurrences, "preimageSha256": preimage}


def assess(generated, references, log):
    """Recompute all eight byte comparisons; missing originals remain explicit."""
    require(type(generated) is dict and type(references) is dict and set(generated) == set(references) == set(range(8)),
            "ABI_ROLE_SET")
    require(type(log) is dict and set(log) == {"name", "bytes", "sha256", "tasks"} and
            log["name"] == "product.stdout.log" and type(log["bytes"]) is int and 0 <= log["bytes"] <= LOG_LIMIT and
            type(log["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", log["sha256"]) and
            type(log["tasks"]) is list and all(type(row) is dict and set(row) == {"task", "observations"}
                for row in log["tasks"]) and [row["task"] for row in log["tasks"]] == list(FRESH_TASKS), "ABI_TASK_SET")
    errors, rows, total = [], [], 0
    for task in log["tasks"]:
        seen = task.get("observations")
        if not (type(seen) is list and len(seen) == 1 and type(seen[0]) is dict and set(seen[0]) == {"line", "outcome"} and
                type(seen[0].get("line")) is int and
                seen[0]["line"] > 0 and seen[0].get("outcome") == "EXECUTED"):
            errors.append("ABI_TASK_NOT_FRESH:" + task["task"])
    for index, (_module, _generated, _baseline, producer, comparison) in enumerate(ROUTES):
        git_blob, reference = references[index]
        require(blob(reference) == git_blob, "ABI_REFERENCE_BLOB")
        original = generated[index]
        require(original is None or type(original) is bytes and 0 < len(original) <= FILE_LIMIT, "ABI_BYTE_BOUND")
        total += 0 if original is None else len(original)
        equal = original == reference
        if not equal:
            errors.append(("ABI_ORIGINAL_MISSING:" if original is None else "ABI_BYTES_DIFFER:") + str(index))
        rows.append({"index": index, "generatedPath": GENERATED[index], "baselinePath": BASELINES[index],
            "producer": producer, "comparison": comparison, "equal": equal,
            "generated": None if original is None else {"member": member(index, "generated"), "bytes": len(original),
                                                        "sha256": digest(original)},
            "baseline": {"member": member(index, "baseline"), "bytes": len(reference), "sha256": digest(reference),
                         "gitBlob": git_blob}})
    require(total <= TOTAL_LIMIT, "ABI_TOTAL_BOUND")
    delta = additive(generated[7])
    if delta["status"] != "PASS":
        errors.append("ABI_ADDITIVE_PROOF_MISSING")
    return {"status": "HOLD" if errors else "PASS", "errors": errors, "routes": rows, "log": log, "additive": delta,
            "androidOnlyBuiltIn": {"classification": "NO_SUPPORTED_DUMP", "tasks": list(FRESH_TASKS[-2:]),
                                    "replacesCustomAndroidChecks": False}}
