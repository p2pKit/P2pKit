"""Closed JVM-library original-report adapter, not a process or crypto owner.

Only the existing hosted Controller calls these file/data operations. The
unchanged canonical executor owns Gradle, stop, report capture and retirement.
This adapter never copies reports, runs a command, obtains a credential or
converts retained DATA into admission/current/native execution authority.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import stat
import uuid

import hosted_test_identity as identity

PROFILE = "jvm-library"
REQUEST_SCOPE = "JVM_LIBRARY_FIXED_REQUEST_V1"
RESULT_SCOPE = "JVM_LIBRARY_REPORT_CUSTODY_V1"
FROZEN_SCOPE = "JVM_LIBRARY_FROZEN_ORIGINALS_V1"
FILE_ONLY = "FILE_ONLY_NOT_NATIVE_PHASE"
TASKS = (":p2p-core:jvmTest", ":p2p-transport-lan:jvmTest", ":p2p-network-provisioning-desktop:test")
ROOTS = (
    "library/p2p-core/build/test-results/jvmTest/", "library/p2p-core/build/reports/tests/jvmTest/",
    "library/p2p-transport-lan/build/test-results/jvmTest/", "library/p2p-transport-lan/build/reports/tests/jvmTest/",
    "library/p2p-network-provisioning-desktop/build/test-results/test/",
    "library/p2p-network-provisioning-desktop/build/reports/tests/test/",
)
JSON_LIMIT, STREAM_LIMIT, REPORT_LIMIT, MEMBER_LIMIT = 4 * 1024**2, 64 * 1024**2, 512 * 1024**2, 20000
FIXED = ("start.json", "receipt.json", "report-manifest.json", "product.stdout.log", "product.stderr.log",
         "stop.stdout.log", "stop.stderr.log")
BACKENDS = {"linux-x64": "linux-proc-pidfd", "windows-x64": "windows-job-list-suspended"}


class JvmCustodyError(ValueError):
    """Fixed nonsecret reason; original exceptions remain with the real owner."""


def require(value, reason):
    if not value:
        raise JvmCustodyError("JVM_LIBRARY_" + reason)


def digest(raw):
    require(type(raw) is bytes, "ORIGINAL_BYTES")
    return hashlib.sha256(raw).hexdigest()


def record(raw):
    value = identity.parse(raw, JSON_LIMIT)
    require(raw == identity.encoded(value), "CANONICAL_DATA_ENCODING")
    return value


def command(role):
    require(role in BACKENDS, "HOST")
    return "gradle", [*TASKS, "--continue", "--console=plain"]


def operation_data(value, budget_sha):
    require(type(value) is dict and set(value) == {"scope", "startedRawNs", "finishedRawNs", "jobBudgetSha256"} and
            value["scope"] == FILE_ONLY and value["jobBudgetSha256"] == budget_sha and
            all(type(value[name]) is int for name in ("startedRawNs", "finishedRawNs")) and
            0 <= value["startedRawNs"] <= value["finishedRawNs"] < 2**64, "FILE_OPERATION")
    return value


def request_data(raw, context_raw, canonical_raw):
    value, context = map(record, (raw, context_raw))
    canonical = identity.parse(canonical_raw, JSON_LIMIT)
    keys = {"schema", "scope", "profile", "role", "source", "contextSha256", "canonicalContextSha256", "root",
            "ownerKind", "ownerState", "home", "owner", "kind", "purpose", "wrapper", "command", "tasks",
            "reportRoots", "operation"}
    role = context["role"]
    require(set(value) == keys and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == REQUEST_SCOPE and value["profile"] == context["profile"] == PROFILE and
            value["role"] == role and value["contextSha256"] == digest(context_raw) and
            value["canonicalContextSha256"] == digest(canonical_raw), "REQUEST_BINDING")
    require(value["ownerKind"] == "audit" and value["root"] == context["root"] == canonical["root"] and
            value["ownerState"] == str(Path(context["session"]) / "state") and
            value["home"] == canonical["gradleHome"] == str(Path(value["ownerState"]) / "gradle-home") and
            canonical["host"] == role and canonical["preexistingOutputPaths"] == [] and
            value["source"] == canonical["source"] == {**context["source"], "status": "", "diffSha256": digest(b"")},
            "REQUEST_SOURCE_OR_HOME")
    owner = value["owner"]
    require(type(owner) is dict and set(owner) == {"job", "productInvocation"} and owner["job"] == canonical["id"] and
            all(type(item) is str and re.fullmatch(r"[0-9a-f]{32}", item) for item in owner.values()) and
            owner["job"] != owner["productInvocation"], "REQUEST_CANONICAL_OWNER")
    require((value["kind"], value["command"]) == (context["kind"], context["command"]) == command(role) and
            value["purpose"] == "ordinary-jvm-library" and value["tasks"] == list(TASKS) and
            value["reportRoots"] == list(ROOTS) and value["wrapper"] ==
            str(Path(value["root"]) / ("gradlew.bat" if role == "windows-x64" else "gradlew")) and
            "samplePackagingRequired" not in context, "REQUEST_EXACT_WORKLOAD")
    operation_data(value["operation"], context["jobBudgetSha256"])
    return value


def reserve(controller, api):
    require(controller.profile == PROFILE and controller.budget is not None and controller.request is None,
            "RESERVATION_ONCE")
    end = controller.window("productive", 30)
    started = controller.now_raw()
    controller.check()
    canonical = identity.parse(controller.canonical_context_raw, JSON_LIMIT)
    state = controller.child(controller.private, "state", end)
    evidence = controller.child(state, "evidence", end)
    require(api["seed_names"](controller, evidence.path, end) == [], "PREEXISTING_CANONICAL_INVOCATION")
    invocation = uuid.uuid4().hex
    directory = controller.child(controller.evidence, PROFILE, end, create=True)
    value = {"schema": 1, "scope": REQUEST_SCOPE, "profile": PROFILE, "role": controller.role,
        "source": canonical["source"], "contextSha256": digest(controller.run_context_raw),
        "canonicalContextSha256": digest(controller.canonical_context_raw), "root": canonical["root"],
        "ownerKind": "audit", "ownerState": str(controller.state_path), "home": canonical["gradleHome"],
        "owner": {"job": canonical["id"], "productInvocation": invocation}, "kind": "gradle",
        "purpose": "ordinary-jvm-library", "wrapper": str(Path(canonical["root"]) /
            ("gradlew.bat" if controller.role == "windows-x64" else "gradlew")),
        "command": command(controller.role)[1], "tasks": list(TASKS), "reportRoots": list(ROOTS),
        "operation": {"scope": FILE_ONLY, "startedRawNs": started, "finishedRawNs": controller.now_raw(),
                      "jobBudgetSha256": controller.budget.sha256}}
    raw = identity.encoded(value)
    request_data(raw, controller.run_context_raw, controller.canonical_context_raw)
    controller.write(directory, "request.json", raw, end)
    require(controller.read(directory, "request.json", end) == raw, "RESERVATION_READBACK")
    controller.check_window("productive", end)
    return raw


def _path(value):
    require(type(value) is str and 0 < len(value.encode("utf-8")) <= 1024 and "\\" not in value and
            len(value.split("/")) <= 65 and all(piece not in ("", ".", "..") for piece in value.split("/")) and
            all(ord(char) >= 32 and ord(char) != 127 for char in value), "REPORT_PATH")
    return value


def report_data(raw, receipt, files):
    manifest = record(raw)
    require(set(manifest) == {"schema", "records", "limitation"} and type(manifest["schema"]) is int and
            manifest["schema"] == 1 and manifest["limitation"] ==
            "Changed bytes are not proof of test execution; use the unchanged product assessor." and
            type(manifest["records"]) is list and len(manifest["records"]) <= MEMBER_LIMIT and
            identity.encoded(manifest["records"]) == identity.encoded(receipt.get("reports")), "REPORT_MANIFEST")
    require(type(files) is list and len(files) <= MEMBER_LIMIT, "ORIGINAL_FILE_ROSTER")
    observed = {}
    for item in files:
        require(type(item) is dict and set(item) == {"path", "size", "sha256"}, "ORIGINAL_FILE_FIELDS")
        name = _path(item["path"])
        require(name not in observed and type(item["size"]) is int and 0 <= item["size"] <= REPORT_LIMIT and
                type(item["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), "ORIGINAL_FILE_METADATA")
        observed[name] = item
    expected, names, total = set(FIXED), set(), 0
    inventories = {name: [] for name in ROOTS}
    for row in manifest["records"]:
        require(type(row) is dict and row.get("classification") in
                ("changed-since-admission", "preexisting-unchanged"), "REPORT_CLASSIFICATION")
        fresh = row["classification"] == "changed-since-admission"
        require(set(row) == {"source", "sha256", "bytes", "classification"} | ({"retained"} if fresh else set()),
                "REPORT_FIELDS")
        name = _path(row["source"])
        require(name.casefold() not in names and type(row["bytes"]) is int and 0 <= row["bytes"] <= REPORT_LIMIT and
                type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "REPORT_METADATA")
        names.add(name.casefold())
        total += row["bytes"]
        require(total <= REPORT_LIMIT, "REPORT_AGGREGATE_BOUND")
        if fresh:
            retained = "reports/" + name
            require(row["retained"] == retained and observed.get(retained) ==
                    {"path": retained, "size": row["bytes"], "sha256": row["sha256"]}, "RETAINED_REPORT_BYTES")
            expected.add(retained)
            for root in ROOTS:
                if name.startswith(root):
                    inventories[root].append({"path": name, "retained": retained, "size": row["bytes"],
                                              "sha256": row["sha256"]})
    require(set(observed) == expected, "COMPLETE_ORIGINAL_FILE_ROSTER")
    require(all(observed[name]["size"] <= (JSON_LIMIT if name.endswith(".json") else STREAM_LIMIT)
                for name in FIXED), "ORIGINAL_LOG_OR_JSON_BOUND")
    return [{"root": name, "fresh": sorted(inventories[name], key=lambda row: row["path"])} for name in ROOTS]


def _launch(api, launch, argv, root, role, *, product_pid=None, batch=True):
    require(type(launch) is dict and launch.get("requestedArgv") == argv and launch.get("cwd") == root and
            launch.get("created") is True and type(launch.get("pid")) is int and launch["pid"] > 0 and
            (product_pid is None or launch["pid"] == product_pid), "CREATED_NATIVE_LAUNCH")
    if role == "windows-x64":
        require(launch.get("api") == "CreateProcessW" and launch.get("resolvedArgv") == argv and
                launch.get("resumed") is True and launch.get("jobAssignedBeforeResume") is True and
                launch.get("batch") is batch and type(launch.get("applicationName")) is str,
                "WINDOWS_ORIGINAL_LAUNCH")
        if batch:
            require(re.search(r"(?i)(?:^|[\\/])cmd\.exe$", launch["applicationName"]) and
                    launch.get("commandLine") == api["processes"].batch_command_line(launch["applicationName"], argv),
                    "WINDOWS_ORIGINAL_BATCH_LAUNCH")
        else:
            require(launch["applicationName"] == argv[0] and
                    launch.get("commandLine") == api["processes"].subprocess.list2cmdline(argv),
                    "WINDOWS_ORIGINAL_PYTHON_LAUNCH")
    else:
        require(launch.get("api") == "subprocess.Popen" and launch.get("shell") is False and
                launch.get("resolvedArgv") == argv and launch.get("executable") == argv[0],
                "LINUX_ORIGINAL_LAUNCH")


def _owner(value, role, job, invocation, count):
    require(type(value) is dict and value.get("backend") == BACKENDS[role] and
            value.get("scope") == ("kernel-job-no-breakaway-kill-on-close" if role == "windows-x64" else
                                    "controlled-marker-inheriting-descendants") and
            value.get("job") == job and value.get("invocation") == invocation and value.get("discoveryErrors") == [] and
            type(value.get("launches")) is list and len(value["launches"]) == count and
            type(value.get("startedIdentities")) is list and value["startedIdentities"], "ORIGINAL_NATIVE_OWNER")


def _birth(owner, pid, role):
    matches = [row for row in owner["startedIdentities"] if type(row) is dict and row.get("pid") == pid]
    key = "creationFileTime" if role == "windows-x64" else "startTicks"
    require(len(matches) == 1 and type(matches[0].get(key)) is int and matches[0][key] > 0,
            "ORIGINAL_CREATED_NATIVE_IDENTITY")


def canonical_data(api, request, context, start_raw, receipt_raw, phase, phase_start, baseline):
    # Canonical JSON is pretty printed by the unchanged helper, not encoded by
    # identity. Parse original bytes without requiring this module's encoder.
    start, receipt = (identity.parse(raw, JSON_LIMIT) for raw in (start_raw, receipt_raw))
    fixed = {"schema": 1, "id": request["owner"]["productInvocation"], "purpose": request["purpose"], "kind": "gradle",
        "requestedArgv": request["command"], "cwd": request["root"], "wrapper": request["wrapper"], "host": request["role"],
        "jobId": request["owner"]["job"], "gradleHome": request["home"],
        "evidenceDirectory": str(Path(request["ownerState"]) / "evidence" / request["owner"]["productInvocation"])}
    require(all(start.get(key) == value == receipt.get(key) for key, value in fixed.items()) and
            type(start["schema"]) is int and type(receipt["schema"]) is int and
            type(start.get("controllerPid")) is int and start["controllerPid"] > 0 and
            start["controllerPid"] == receipt.get("controllerPid") and start["startedUtc"] == receipt.get("startedUtc") and
            start.get("sourceBefore") is start.get("sourceAfter") is start.get("productExitCode") is
            start.get("stopExitCode") is None and start.get("finalExitCode") == 125 and
            start.get("errors") == [] and start.get("sourceUnchanged") is False, "CANONICAL_ORIGINAL_START")
    require(receipt.get("sourceBefore") == receipt.get("sourceAfter") == request["source"] and
            receipt.get("sourceUnchanged") is True and receipt.get("errors") == [] and
            receipt.get("ownedSurvivors") == [] and not receipt.get("cancelledSignals") and
            receipt.get("cancelRequested", False) is False and
            all(type(receipt.get(key)) is int for key in ("productExitCode", "stopExitCode", "finalExitCode")) and
            0 <= receipt["productExitCode"] <= 255 and receipt["productExitCode"] != 125 and
            receipt["finalExitCode"] == receipt["productExitCode"] and receipt["stopExitCode"] == 0,
            "CANONICAL_STOP_SOURCE_OR_RETIREMENT")
    executed = [request["wrapper"], *api["audit"].gradle_arguments(request["command"])]
    stop = [request["wrapper"], "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
            "-Dorg.gradle.jvmargs=" + api["audit"].JVM_ARGUMENTS]
    require(receipt.get("executedArgv") == executed and receipt.get("stopArgv") == stop and
            type(receipt.get("productLaunchIndex")) is int and receipt["productLaunchIndex"] == 0 and
            type(receipt.get("stopLaunchIndex")) is int and receipt["stopLaunchIndex"] == 1 and
            receipt.get("executedArgvSemantics") ==
            "logical-command; exact platform launch is ownership.launches[productLaunchIndex]", "CANONICAL_EFFECTIVE_COMMAND")
    ownership = receipt.get("ownership", {})
    _owner(ownership, request["role"], fixed["jobId"], fixed["id"], 2)
    _launch(api, ownership["launches"][0], executed, request["root"], request["role"], product_pid=receipt.get("productPid"))
    _launch(api, ownership["launches"][1], stop, request["root"], request["role"])
    _birth(ownership, receipt["productPid"], request["role"])
    expected = api["canonical_python"](context["python"], context["canonicalSources"], "--cwd", request["root"],
        "--wrapper", request["wrapper"], "--kind", "gradle", "--purpose", request["purpose"], "--id", fixed["id"],
        "--timeout", "600", "--stop-timeout", "120", "--", *request["command"])
    require(type(phase) is dict and phase.get("phase") == "product" and phase.get("argv") == expected and
            phase.get("job") == fixed["jobId"] and phase.get("state") == request["ownerState"] and
            phase.get("home") == request["home"] and phase.get("cwd") == request["root"] and
            phase.get("canonicalInvocation") == fixed["id"] and phase.get("launchAttempted") is True and
            phase.get("scopeAttempted") is True and phase.get("retirement") == "KNOWN" and phase.get("errors") == [] and
            phase.get("survivors") == [] and type(phase.get("exitCode")) is int and
            phase["exitCode"] == receipt["finalExitCode"] and phase.get("cooperativeCancellation") is None and
            phase.get("ownership", {}).get("discoveryErrors") == [] and
            phase.get("childAncestorInvocationIds") == start.get("ancestorInvocationIds") ==
            receipt.get("ancestorInvocationIds"), "ORIGINAL_OUTER_PRODUCT")
    outer = phase["ownership"]
    _owner(outer, request["role"], fixed["jobId"], phase["invocation"], 1)
    _launch(api, outer["launches"][0], expected, request["root"], request["role"],
            product_pid=start["controllerPid"], batch=False)
    _birth(outer, start["controllerPid"], request["role"])
    require(outer["launches"][0].get("outputMode") ==
            ("caller-owned-native-files" if request["role"] == "windows-x64" else "caller-owned-files") and
            all(type(phase.get(name)) is int for name in ("startedRawNs", "completedRawNs", "finalizedRawNs")) and
            request["operation"]["finishedRawNs"] <= phase["startedRawNs"] <= phase["completedRawNs"] <=
            phase["finalizedRawNs"] < phase["startedRawNs"] + 870 * 10**9 and
            phase["completedRawNs"] < phase["startedRawNs"] + 825 * 10**9, "ORIGINAL_OUTER_WINDOW_OR_OUTPUTS")
    require(type(phase_start) is dict and all(phase_start.get(name) == phase.get(name) for name in
            ("phase", "argv", "cwd", "job", "invocation", "state", "home", "canonicalInvocation", "startedRawNs")) and
            phase_start.get("launchAttempted") is phase_start.get("scopeAttempted") is False and
            phase_start.get("exitCode") is None and type(baseline) is dict and
            set(baseline) == {"role", "baseline", "kernelJob"} and baseline["role"] == request["role"] and
            baseline["kernelJob"] is (request["role"] == "windows-x64"), "ORIGINAL_NATIVE_PHASE_START")
    return receipt


def inventory(owner, api, directory, end, check):
    """Read every original member using the maintained protected snapshot owner."""
    snapshot, result = None, []
    try:
        check()
        directory.verify()
        if api["os"].name == "nt":
            snapshot = owner.acquire("jvm-original-snapshot", lambda: directory.snapshot(
                max_bytes=REPORT_LIMIT, max_members=MEMBER_LIMIT, deadline=end))
            entries = snapshot.entries
            files = [(name, info.size) for name, info in entries.items() if not info.is_directory]
            opener = snapshot.open_file
        else:
            entries = api["posix_snapshot"](owner, directory.path, REPORT_LIMIT, MEMBER_LIMIT, end)
            files = [(name, info[5]) for name, info in entries.items() if stat.S_ISREG(info[2])]
            opener = lambda name: api["posix"]._open_member(directory.path, name, entries)
        require(len(files) <= MEMBER_LIMIT, "ORIGINAL_MEMBER_BOUND")
        for name, size in sorted(files):
            check()
            _path(name)
            stream = owner.acquire("jvm-original-reader", lambda: opener(name))
            try:
                hashed = api["hash_stream"](stream, size, end)
            except BaseException as error:
                # Preserve a failed read before a separately failed close can
                # become the owner's first error. Never retry either operation.
                owner.error("jvm-original-read", error)
                raise
            finally:
                owner.close_one(stream)
            require(not owner.unknown, "ORIGINAL_READER_CLOSE_UNKNOWN")
            result.append({"path": name, "size": size, "sha256": hashed})
        if snapshot is not None:
            snapshot.verify()
        else:
            require(api["posix_snapshot"](owner, directory.path, REPORT_LIMIT, MEMBER_LIMIT, end) == entries,
                    "ORIGINAL_TREE_CHANGED")
        directory.verify()
    except BaseException as error:
        owner.error("jvm-original-inventory", error)
        raise
    finally:
        if snapshot is not None:
            owner.close_one(snapshot)
    require(not owner.unknown, "ORIGINAL_SNAPSHOT_CLOSE_UNKNOWN")
    check()
    return result


def collection_data(api, request_raw, context_raw, canonical_raw, operation, *, phase=None, phase_start_raw=None,
                    baseline_raw=None, start_raw=None, receipt_raw=None, manifest_raw=None, files=None):
    request = request_data(request_raw, context_raw, canonical_raw)
    context = record(context_raw)
    operation_data(operation, context["jobBudgetSha256"])
    require(operation["startedRawNs"] >= request["operation"]["finishedRawNs"], "COLLECTION_BEFORE_RESERVATION")
    result = {"schema": 1, "scope": RESULT_SCOPE, "profile": PROFILE, "role": request["role"],
        "source": request["source"], "job": request["owner"]["job"], "invocation": request["owner"]["productInvocation"],
        "requestSha256": digest(request_raw), "contextSha256": digest(context_raw),
        "canonicalContextSha256": digest(canonical_raw), "canonicalStartSha256": None,
        "canonicalReceiptSha256": None, "reportManifestSha256": None, "productPhaseSha256": None,
        "productPhaseStartSha256": None, "productPhaseBaselineSha256": None, "operation": operation,
        "roots": [{"root": root, "fresh": []} for root in ROOTS], "missingRoots": list(ROOTS),
        "retainedFiles": [], "productExitCode": None, "stopExitCode": None, "ownerFinalExitCode": None,
        "result": "NOT_STARTED", "retirement": "KNOWN", "errors": []}
    if phase is None:
        require(all(value is None for value in (phase_start_raw, baseline_raw, start_raw, receipt_raw, manifest_raw)) and
                files == [], "NOT_STARTED_HAS_NO_CANONICAL_ORIGINALS")
        return result
    require(all(type(raw) is bytes for raw in (phase_start_raw, baseline_raw, start_raw, receipt_raw, manifest_raw)),
            "LAUNCHED_PRODUCT_REQUIRES_ORIGINALS")
    receipt = canonical_data(api, request, context, start_raw, receipt_raw, phase,
                             record(phase_start_raw), record(baseline_raw))
    # Canonical JSON encoding is retained byte-for-byte, not normalized into a
    # new manifest before hashing or comparison with its receipt.
    original_manifest = identity.parse(manifest_raw, JSON_LIMIT)
    roots = report_data(identity.encoded(original_manifest), receipt, files)
    originals = {row["path"]: row for row in files}
    for name, raw in (("start.json", start_raw), ("receipt.json", receipt_raw), ("report-manifest.json", manifest_raw)):
        require(originals.get(name) == {"path": name, "size": len(raw), "sha256": digest(raw)}, "ORIGINAL_JSON_CHANGED")
    require(type(phase.get("finalizedRawNs")) is int and phase["finalizedRawNs"] <= operation["startedRawNs"],
            "COLLECTION_PRECEDES_NATIVE_RETURN")
    missing = [row["root"] for row in roots if not row["fresh"]]
    result.update(canonicalStartSha256=digest(start_raw), canonicalReceiptSha256=digest(receipt_raw),
        reportManifestSha256=digest(manifest_raw), productPhaseSha256=digest(identity.encoded(phase)),
        productPhaseStartSha256=digest(phase_start_raw), productPhaseBaselineSha256=digest(baseline_raw),
        roots=roots, missingRoots=missing, retainedFiles=files, productExitCode=receipt["productExitCode"],
        stopExitCode=receipt["stopExitCode"], ownerFinalExitCode=receipt["finalExitCode"],
        result="RETAINED" if receipt["finalExitCode"] == 0 and not missing and
            all(row["classification"] == "changed-since-admission" for row in original_manifest["records"]) else
            "FAILED_TEST_OR_REPORTS")
    return result


def _originals(owner, api, private, context_raw, end, check, operation):
    evidence = owner.child(private, "evidence", end)
    directory = owner.child(evidence, PROFILE, end)
    request_raw = owner.read(directory, "request.json", end)
    state = owner.child(private, "state", end)
    canonical_raw = owner.read(state, "context.json", end)
    request = request_data(request_raw, context_raw, canonical_raw)
    names = api["seed_names"](owner, owner.child(state, "evidence", end).path, end)
    commands = owner.child(evidence, "commands", end)
    phases = api["seed_names"](owner, commands.path, end)
    invocation = request["owner"]["productInvocation"]
    inputs = {"files": []}
    if "product" in phases:
        # A created phase without a proven launch is deliberately HOLD, not an
        # adopted setup-failure receipt. NOT_STARTED below requires its absence.
        require(names == [invocation], "EXACT_SINGLE_CANONICAL_INVOCATION")
        native = owner.child(commands, "product", end)
        phase_raw = owner.read(native, "result.json", end)
        inputs.update(phase=record(phase_raw), phase_start_raw=owner.read(native, "start.json", end),
                      baseline_raw=owner.read(native, "baseline.json", end))
        original = owner.child(owner.child(state, "evidence", end), invocation, end)
        inputs.update(start_raw=owner.read(original, "start.json", end),
                      receipt_raw=owner.read(original, "receipt.json", end),
                      manifest_raw=owner.read(original, "report-manifest.json", end),
                      files=inventory(owner, api, original, end, check))
    else:
        require(names == [], "UNLAUNCHED_CANONICAL_EVIDENCE_EXISTS")
    return collection_data(api, request_raw, context_raw, canonical_raw, operation, **inputs), request_raw, canonical_raw


def collect(controller, api):
    require(controller.profile == PROFILE and controller.request is not None and controller.budget is not None,
            "COLLECTION_REQUIRES_RESERVATION")
    end = controller.window("collect", 120)
    check = lambda: (controller.check(finalizing=True), controller.check_window("collect", end))
    started = controller.now_raw()
    # Retain one operation's original interval, not a synthetic native phase.
    operation = {"scope": FILE_ONLY, "startedRawNs": started, "finishedRawNs": started,
                 "jobBudgetSha256": controller.budget.sha256}
    value, _, _ = _originals(controller, api, controller.private, controller.run_context_raw, end, check, operation)
    value["operation"]["finishedRawNs"] = controller.now_raw()
    check()
    directory = controller.child(controller.evidence, PROFILE, end)
    controller.write(directory, "result.json", value, end)
    require(controller.read(directory, "result.json", end) == identity.encoded(value), "COLLECTION_READBACK")
    check()
    return value


def verify(owner, api, private, context_raw, result, end, check):
    directory = owner.child(owner.child(private, "evidence", end), PROFILE, end)
    raw = owner.read(directory, "result.json", end)
    value = record(raw)
    expected, request_raw, canonical_raw = _originals(owner, api, private, context_raw, end, check, value["operation"])
    require(raw == identity.encoded(expected) and value == result["custody"] and
            result["profile"] == PROFILE and result["role"] == value["role"] and
            result["contextSha256"] == value["contextSha256"] and
            result["productAttempted"] is (value["result"] != "NOT_STARTED"), "COLLECTION_RESULT_CHANGED")
    return value, raw, request_raw, canonical_raw


def profile_passed(value):
    custody = value.get("custody")
    return (type(custody) is dict and custody.get("scope") == RESULT_SCOPE and custody.get("profile") == PROFILE and
            custody.get("role") == value.get("role") and custody.get("result") == "RETAINED" and
            custody.get("missingRoots") == [] and custody.get("retirement") == "KNOWN" and custody.get("errors") == [] and
            custody.get("contextSha256") == value.get("contextSha256") and
            custody.get("productPhaseSha256") == value.get("phaseSha256", {}).get("product") and
            all(type(custody.get(key)) is int and custody[key] == 0 for key in
                ("productExitCode", "stopExitCode", "ownerFinalExitCode")) and
            type(custody.get("roots")) is list and len(custody["roots"]) == len(ROOTS) and
            all(type(row) is dict and set(row) == {"root", "fresh"} and row["root"] == root and
                type(row["fresh"]) is list and row["fresh"] for root, row in zip(ROOTS, custody["roots"])))


def frozen_binding(owner, api, private, end, check):
    """Re-read original bytes and both existing reversible copies, no new copier."""
    context_raw = owner.read(private, "run-context.json", end)
    evidence = owner.child(private, "evidence", end)
    result = record(owner.read(evidence, "profile-result-before-export.json", end))
    value, collection_raw, request_raw, canonical_raw = verify(owner, api, private, context_raw, result, end, check)
    frozen = owner.child(private, "frozen-evidence", end)
    outer_raw = owner.read(frozen, "original-path-map.json", end)
    outer = {row["original"]: row for row in api["seed_copy_map"](outer_raw, evidence.path)["files"]}
    frozen_files = {row["path"]: row for row in inventory(owner, api, frozen, end, check)}

    def copied(name, original, maximum):
        require(name in outer, "FROZEN_MEMBER_MISSING")
        row = outer[name]
        metadata = frozen_files.get(row["member"])
        require(original["size"] <= maximum and metadata ==
                {"path": row["member"], "size": original["size"], "sha256": original["sha256"]} and
                row["size"] == original["size"] and row["sha256"] == original["sha256"], "FROZEN_ORIGINAL_BYTES_CHANGED")
        check()

    for name, raw in ((PROFILE + "/request.json", request_raw), (PROFILE + "/result.json", collection_raw),
                      ("canonical-context.json", canonical_raw)):
        copied(name, {"size": len(raw), "sha256": digest(raw)}, JSON_LIMIT)
    canonical_copy = owner.child(evidence, "canonical-audit", end)
    map_raw = owner.read(canonical_copy, "original-path-map.json", end)
    mapping = {row["original"]: row for row in
               api["seed_copy_map"](map_raw, private.path / "state/evidence")["files"]}
    copy_files = {row["path"]: row for row in inventory(owner, api, canonical_copy, end, check)}
    copied("canonical-audit/original-path-map.json", {"size": len(map_raw), "sha256": digest(map_raw)}, JSON_LIMIT)
    prefix = value["invocation"] + "/"
    require(set(mapping) == {prefix + row["path"] for row in value["retainedFiles"]}, "CANONICAL_COPY_COMPLETE_ROSTER")
    for item in value["retainedFiles"]:
        row = mapping[prefix + item["path"]]
        actual = copy_files.get(row["member"])
        require(actual == {"path": row["member"], "size": item["size"], "sha256": item["sha256"]} and
                row["size"] == item["size"] and row["sha256"] == item["sha256"], "CANONICAL_COPY_BYTES_CHANGED")
        copied("canonical-audit/" + row["member"], item, REPORT_LIMIT)
    if value["result"] != "NOT_STARTED":
        phase = owner.child(owner.child(evidence, "commands", end), "product", end)
        for name, field in (("start.json", "productPhaseStartSha256"), ("result.json", "productPhaseSha256"),
                            ("baseline.json", "productPhaseBaselineSha256")):
            raw = owner.read(phase, name, end)
            require(digest(raw) == value[field], "PRODUCT_ORIGINAL_CHANGED")
            copied("commands/product/" + name, {"size": len(raw), "sha256": digest(raw)}, JSON_LIMIT)
    check()
    return {"schema": 1, "scope": FROZEN_SCOPE, "source": record(context_raw)["source"],
        "contextSha256": digest(context_raw), "requestSha256": digest(request_raw), "collectionSha256": digest(collection_raw),
        "canonicalContextSha256": digest(canonical_raw), **{name: value[name] for name in
            ("canonicalStartSha256", "canonicalReceiptSha256", "reportManifestSha256", "productPhaseSha256",
             "productPhaseStartSha256", "productPhaseBaselineSha256", "retainedFiles")},
        "disposition": value["result"]}
