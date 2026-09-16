"""Pure primary ordinary-FULL simulator policy; no I/O or execution suppliers.

These receipts select no device by themselves. The ordinary controller must
obtain each original with its existing native owner, and the platform driver
must bind the actual KGP Property. A model/receipt is not native acceptance.
"""
from __future__ import annotations

import hashlib
import json
import re

LIMIT = 4 * 1024 * 1024
SECONDS = 120
PATH_ENV = "P2PKIT_ORDINARY_FULL_SIMULATOR"
HASH_ENV = "P2PKIT_ORDINARY_FULL_SIMULATOR_SHA256"
RELATIVE = "evidence/simulator/binding.json"
SCOPE = "RESERVED_PRIMARY_ORDINARY_FULL_SIMULATOR"
TYPE = "org.jetbrains.kotlin.gradle.targets.native.tasks.KotlinNativeSimulatorTest"
TASKS = (":p2p-core:iosSimulatorArm64Test", ":p2p-core:iosX64Test",
         ":p2p-transport-lan:iosSimulatorArm64Test", ":p2p-transport-lan:iosX64Test")
HOSTS = {
    "macos-arm64": {"osMajor": "26", "xcode": "Xcode 26.5\nBuild version 17F42\n",
                    "runtime": "com.apple.CoreSimulator.SimRuntime.iOS-26-5", "version": "26.5"},
    "macos-x64": {"osMajor": "15", "xcode": "Xcode 26.3\nBuild version 17C529\n",
                  "runtime": "com.apple.CoreSimulator.SimRuntime.iOS-26-2", "version": "26.2"},
}
COMMANDS = {
    "simulator-macos-version": ("/usr/bin/sw_vers", "-productVersion"),
    "simulator-xcode-version": ("/usr/bin/xcodebuild", "-version"),
    "simulator-first-launch": ("/usr/bin/xcodebuild", "-checkFirstLaunchStatus"),
    "simulator-runtimes": ("/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"),
    "simulator-devices": ("/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"),
}
PREPARE = tuple(COMMANDS)
PRELAUNCH = "simulator-prelaunch"
BEFORE, SHUTDOWN, AFTER = "simulator-retire-before", "simulator-shutdown", "simulator-retire-after"
RETIRE = (BEFORE, SHUTDOWN, AFTER)
UUID = re.compile(r"[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}")


class SimulatorError(ValueError):
    """Finite reason only; raw device identities remain in private originals."""


def require(value, reason):
    if not value:
        raise SimulatorError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= LIMIT, "SIMULATOR_RECORD_LIMIT")
    return raw


def parse(raw):
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "SIMULATOR_RECORD_LIMIT")
    def unique(pairs):
        result = {}
        for name, value in pairs:
            require(name not in result, "SIMULATOR_DUPLICATE_KEY")
            result[name] = value
        return result
    def nonfinite(_value):
        raise SimulatorError("SIMULATOR_NONFINITE_JSON")
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SimulatorError("SIMULATOR_JSON") from error


def policy(role):
    require(type(role) is str and role in HOSTS, "SIMULATOR_NATIVE_MAC_ROLE_REQUIRED")
    return HOSTS[role]


def uuid(value):
    require(type(value) is str and UUID.fullmatch(value), "SIMULATOR_UUID")
    return value


def descriptor(row):
    require(type(row) is dict and row.get("name") == "iPhone 17" and
            row.get("deviceTypeIdentifier") == "com.apple.CoreSimulator.SimDeviceType.iPhone-17" and
            row.get("isAvailable") is True and row.get("state") in
            ("Shutdown", "Booted", "Booting", "Shutting Down"), "SIMULATOR_DEVICE_UNAVAILABLE_OR_CHANGED")
    return {"udid": uuid(row.get("udid")), "name": row["name"], "deviceTypeIdentifier": row["deviceTypeIdentifier"],
            "isAvailable": True, "state": row["state"]}


def device_rows(raw):
    value = parse(raw)
    require(type(value) is dict and type(value.get("devices")) is dict and len(value["devices"]) <= 256,
            "SIMULATOR_DEVICE_INVENTORY")
    groups = value["devices"]
    require(all(type(key) is str and type(rows) is list and all(type(row) is dict for row in rows)
                for key, rows in groups.items()), "SIMULATOR_DEVICE_INVENTORY")
    all_rows = [row for rows in groups.values() for row in rows]
    require(len(all_rows) <= 4096 and all(type(row.get("udid")) is str for row in all_rows) and
            len({row["udid"] for row in all_rows}) == len(all_rows), "SIMULATOR_DUPLICATE_OR_EXCESSIVE_DEVICE")
    return groups


def original(label, role, raw):
    """Fail early on each fixed observation; never start a product to probe it."""
    expected = policy(role)
    require(type(raw) is bytes and len(raw) <= LIMIT, "SIMULATOR_ORIGINAL_BYTES")
    if label == "simulator-macos-version":
        version = raw.decode("ascii").strip()
        require(re.fullmatch(re.escape(expected["osMajor"]) + r"\.[0-9]+(?:\.[0-9]+)?", version),
                "SIMULATOR_UNADMITTED_MACOS")
        return version
    if label == "simulator-xcode-version":
        require(raw == expected["xcode"].encode("ascii"), "SIMULATOR_UNADMITTED_XCODE")
        return expected["xcode"]
    if label == "simulator-first-launch":
        return None  # Its actual zero exit/native retirement, not output text, is required by the caller.
    if label == "simulator-runtimes":
        value = parse(raw)
        require(type(value) is dict and type(value.get("runtimes")) is list and len(value["runtimes"]) <= 256 and
                all(type(row) is dict for row in value["runtimes"]), "SIMULATOR_RUNTIME_INVENTORY")
        matches = [row for row in value["runtimes"] if row.get("identifier") == expected["runtime"]]
        require(len(matches) == 1 and matches[0].get("isAvailable") is True and
                matches[0].get("version") == expected["version"], "SIMULATOR_RUNTIME_UNAVAILABLE_OR_CHANGED")
        return {"identifier": expected["runtime"], "version": expected["version"], "isAvailable": True}
    require(label == "simulator-devices", "SIMULATOR_CLOSED_OBSERVATION")
    rows = device_rows(raw).get(expected["runtime"], [])
    matches = [row for row in rows if row.get("name") == "iPhone 17" and row.get("state") == "Shutdown" and
               row.get("isAvailable") is True]
    require(len(matches) == 1, "SIMULATOR_ONE_ORIGINALLY_SHUTDOWN_IPHONE17_REQUIRED")
    return descriptor(matches[0])


def terminal_device(raw, admitted):
    rows = device_rows(raw).get(admitted["runtime"]["identifier"], [])
    matches = [row for row in rows if row.get("udid") == admitted["device"]["udid"]]
    require(len(matches) == 1, "SIMULATOR_OWNED_DEVICE_MISSING")
    actual = descriptor(matches[0])
    require(all(actual[key] == value for key, value in admitted["device"].items() if key != "state"),
            "SIMULATOR_OWNED_DEVICE_CHANGED")
    return actual


def command(label, selected=None):
    if label in COMMANDS:
        return list(COMMANDS[label])
    if label in (PRELAUNCH, BEFORE, AFTER):
        return list(COMMANDS["simulator-devices"])
    require(label == SHUTDOWN and type(selected) is dict, "SIMULATOR_CLOSED_COMMAND")
    return ["/usr/bin/xcrun", "simctl", "shutdown", uuid(selected["device"]["udid"])]


def phase_reference(row, stdout, stderr):
    return {"phaseSha256": digest(encoded(row)), "stdoutSha256": digest(stdout), "stderrSha256": digest(stderr)}


def contexts(run_raw, canonical_raw):
    run, canonical = parse(run_raw), parse(canonical_raw)
    require(type(run) is dict and type(canonical) is dict, "SIMULATOR_CONTEXT_JSON")
    require(type(run.get("schema")) is int and run["schema"] == 1 and run.get("scope") == "CLOSED_ORDINARY_TEST_CONTROLLER" and
            run.get("profile") == "full" and run.get("command") == ["python3", "scripts/run-platform-tests.py", "full"] and
            run.get("kind") == "command" and run.get("role") in HOSTS and run.get("primarySimulatorRequired") is True and
            type(run.get("source")) is dict and type(run.get("job")) is str and re.fullmatch(r"[0-9a-f]{32}", run["job"]) and
            all(type(run.get(key)) is str and run[key].startswith("/") and "\0" not in run[key] and
                ".." not in run[key].split("/") for key in ("root", "session")), "SIMULATOR_ORDINARY_CONTEXT")
    source = canonical.get("source", {})
    require(type(canonical.get("schema")) is int and canonical["schema"] == 1 and canonical.get("root") == run.get("root") and
            canonical.get("host") == run["role"] and canonical.get("preexistingOutputPaths") == [] and
            canonical.get("gradleHome") == run["session"] + "/state/gradle-home" and
            type(canonical.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", canonical["id"]) and
            source == {**run["source"], "status": "", "diffSha256": digest(b"")} and
            all(type(source.get(key)) is str and re.fullmatch(r"[0-9a-f]{40}", source[key]) for key in ("commit", "tree")) and
            type(run.get("jobBudgetSha256")) is str and re.fullmatch(r"[0-9a-f]{64}", run["jobBudgetSha256"]),
            "SIMULATOR_CANONICAL_CONTEXT")
    return run, canonical


def admission_record(run_raw, canonical_raw, observations, developer_dir):
    run, canonical = contexts(run_raw, canonical_raw)
    require(set(observations) == set(PREPARE), "SIMULATOR_ORIGINAL_SET")
    values, references = {}, {}
    for label in PREPARE:
        row, stdout, stderr = observations[label]
        require(row["phase"] == label and row["argv"] == command(label) and type(row["exitCode"]) is int and
                row["exitCode"] == 0 and row["launchAttempted"] is True and row["scopeAttempted"] is True and
                row["retirement"] == "KNOWN" and row["errors"] == [] and row.get("survivors") == [] and
                row.get("ownership", {}).get("discoveryErrors") == [] and row["job"] == run["job"] and
                row["state"] == run["session"] and row["home"] == run["session"] + "/control-home" and
                row["jobBudgetSha256"] == run["jobBudgetSha256"] and row.get("developerDir") == developer_dir,
                "SIMULATOR_ORIGINAL_PHASE")
        values[label] = original(label, run["role"], stdout)
        references[label] = phase_reference(row, stdout, stderr)
    require(developer_dir == run.get("developerDir") and (developer_dir is None or type(developer_dir) is str and
            developer_dir.startswith("/") and "\0" not in developer_dir), "SIMULATOR_DEVELOPER_DIR")
    return encoded({"schema": 1, "scope": "ORIGINAL_SHUTDOWN_ORDINARY_FULL_SIMULATOR", "role": run["role"],
        "contextSha256": digest(run_raw), "canonicalContextSha256": digest(canonical_raw),
        "source": canonical["source"], "jobBudgetSha256": run["jobBudgetSha256"], "developerDir": developer_dir,
        "selected": {"macosVersion": values["simulator-macos-version"], "xcodeVersion": values["simulator-xcode-version"],
                     "runtime": values["simulator-runtimes"], "device": values["simulator-devices"]},
        "originals": references})


def binding_record(run_raw, canonical_raw, request_raw, admission_raw):
    run, canonical = contexts(run_raw, canonical_raw)
    request, admitted = parse(request_raw), parse(admission_raw)
    require(type(request) is dict and type(admitted) is dict, "SIMULATOR_BINDING_JSON")
    require(set(admitted) == {"schema", "scope", "role", "contextSha256", "canonicalContextSha256", "source",
                            "jobBudgetSha256", "developerDir", "selected", "originals"} and
            type(admitted["schema"]) is int and admitted["schema"] == 1 and
            admitted["scope"] == "ORIGINAL_SHUTDOWN_ORDINARY_FULL_SIMULATOR" and
            admitted["role"] == run["role"] and admitted["contextSha256"] == digest(run_raw) and
            admitted["canonicalContextSha256"] == digest(canonical_raw) and admitted["source"] == canonical["source"] and
            admitted["jobBudgetSha256"] == run["jobBudgetSha256"] and admitted["developerDir"] == run.get("developerDir") and
            type(admitted["originals"]) is dict and set(admitted["originals"]) == set(PREPARE) and
            all(type(row) is dict and set(row) == {"phaseSha256", "stdoutSha256", "stderrSha256"} and
                all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) for value in row.values())
                for row in admitted["originals"].values()),
            "SIMULATOR_ORIGINAL_ADMISSION_CHANGED")
    selected = admitted["selected"]
    require(type(selected) is dict and set(selected) == {"macosVersion", "xcodeVersion", "runtime", "device"} and
            all(type(selected[key]) is str for key in ("macosVersion", "xcodeVersion")) and
            selected["device"] == descriptor(selected["device"]) and selected["device"]["state"] == "Shutdown" and
            selected["runtime"] == {"identifier": policy(run["role"])["runtime"],
                                    "version": policy(run["role"])["version"], "isAvailable": True},
            "SIMULATOR_ORIGINAL_SELECTION_CHANGED")
    original("simulator-macos-version", run["role"], selected["macosVersion"].encode("ascii"))
    original("simulator-xcode-version", run["role"], selected["xcodeVersion"].encode("ascii"))
    owner = request.get("owner", {})
    require(request.get("ownerKind") == "audit" and request.get("ownerState") == run["session"] + "/state" and
            request.get("home") == canonical["gradleHome"] and request.get("root") == run["root"] and
            request.get("source") == canonical["source"] and request.get("command") == run["command"] and
            type(owner) is dict and set(owner) == {"job", "productInvocation", "stopInvocation"} and owner["job"] == canonical["id"] and
            owner["stopInvocation"] is None and type(owner["productInvocation"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", owner["productInvocation"]), "SIMULATOR_PRIMARY_RESERVATION_CHANGED")
    return encoded({"schema": 1, "scope": SCOPE, "profile": "full", "role": run["role"],
        "root": run["root"], "session": run["session"], "state": request["ownerState"], "home": request["home"],
        "source": canonical["source"], "job": canonical["id"], "productInvocation": owner["productInvocation"],
        "contextSha256": digest(run_raw), "canonicalContextSha256": digest(canonical_raw),
        "custodyRequestSha256": digest(request_raw), "admissionSha256": digest(admission_raw),
        "jobBudgetSha256": run["jobBudgetSha256"], "developerDir": admitted["developerDir"],
        "selected": selected})


def prelaunch_record(run_raw, binding_raw, row, stdout, stderr):
    run, binding = parse(run_raw), parse(binding_raw)
    require(binding["contextSha256"] == digest(run_raw) and row.get("phase") == PRELAUNCH and
            row.get("argv") == command(PRELAUNCH) and row.get("job") == run["job"] and
            row.get("state") == run["session"] and row.get("home") == run["session"] + "/control-home" and
            row.get("developerDir") == binding["developerDir"] and
            row.get("simulatorBindingSha256") == digest(binding_raw) and
            row.get("jobBudgetSha256") == binding["jobBudgetSha256"] and type(row.get("exitCode")) is int and
            row["exitCode"] == 0 and row.get("retirement") == "KNOWN" and row.get("launchAttempted") is True and
            row.get("scopeAttempted") is True and row.get("survivors") == [] and row.get("errors") == [] and
            row.get("ownership", {}).get("discoveryErrors") == [], "SIMULATOR_PRELAUNCH_ORIGINAL_CHANGED")
    device = terminal_device(stdout, binding["selected"])
    require(device["state"] == "Shutdown", "SIMULATOR_PRELAUNCH_EXTERNAL_STATE_CHANGE")
    return encoded({"schema": 1, "scope": "CURRENT_SHUTDOWN_BEFORE_PRIMARY_LAUNCH", "bindingSha256": digest(binding_raw),
                    "device": device, "original": phase_reference(row, stdout, stderr)})


def canonical_start(binding_raw, raw, ancestors, controller_pid=None):
    """The real initial start precedes source admission; its outcome fields are unset."""
    binding, start = parse(binding_raw), parse(raw)
    expected = {"schema": 1, "id": binding["productInvocation"], "purpose": "ordinary-full", "kind": "command",
        "requestedArgv": ["python3", "scripts/run-platform-tests.py", "full"], "cwd": binding["root"],
        "wrapper": binding["root"] + "/gradlew", "host": binding["role"], "jobId": binding["job"],
        "gradleHome": binding["home"], "ancestorInvocationIds": ancestors, "sourceBefore": None, "sourceAfter": None,
        "productExitCode": None, "stopExitCode": None, "finalExitCode": 125, "sourceUnchanged": False,
        "ownedSurvivors": [], "errors": [], "evidenceDirectory": binding["state"] + "/evidence/" + binding["productInvocation"]}
    require(type(start) is dict and set(start) == set(expected) | {"controllerPid", "startedUtc"} and
            all(type(start[key]) is type(value) and start[key] == value for key, value in expected.items()) and
            type(ancestors) is list and ancestors and len(ancestors) < 32 and len(set(ancestors)) == len(ancestors) and
            all(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) for value in ancestors) and
            binding["productInvocation"] not in ancestors and type(start["controllerPid"]) is int and start["controllerPid"] > 0 and
            (controller_pid is None or start["controllerPid"] == controller_pid) and type(start["startedUtc"]) is str and
            re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)",
                         start["startedUtc"]), "SIMULATOR_ACTUAL_CANONICAL_START_CHANGED")
    return start


def created_native_launch(ownership, index, argv, cwd, job, invocation):
    require(type(ownership) is dict and ownership.get("backend") == "darwin-libproc-audit-token" and
            ownership.get("scope") == "controlled-marker-inheriting-descendants" and
            ownership.get("job") == job and ownership.get("invocation") == invocation and
            ownership.get("discoveryErrors") == [] and type(ownership.get("launches")) is list and
            type(index) is int and 0 <= index < len(ownership["launches"]), "SIMULATOR_NATIVE_LAUNCH_REQUIRED")
    launch = ownership["launches"][index]
    require(type(launch) is dict and launch.get("api") == "subprocess.Popen" and launch.get("requestedArgv") == argv and
            launch.get("cwd") == cwd and launch.get("shell") is False and launch.get("created") is True and
            type(launch.get("pid")) is int and launch["pid"] > 0, "SIMULATOR_NATIVE_CHILD_NOT_CREATED")
    identities = ownership.get("startedIdentities")
    require(type(identities) is list, "SIMULATOR_NATIVE_BIRTH_REQUIRED")
    matches = [row for row in identities if type(row) is dict and row.get("pid") == launch["pid"]]
    require(len(matches) == 1 and all(type(matches[0].get(key)) is int and matches[0][key] >= 0
            for key in ("uniqueId", "startSeconds", "startMicroseconds", "pidVersion")) and matches[0]["uniqueId"] > 0,
            "SIMULATOR_NATIVE_BIRTH_REQUIRED")
    return {"launch": launch, "identity": matches[0]}


def launch_authority(binding_raw, prelaunch_raw, start_raw, canonical_raw, outer):
    """Actual created canonical AND primary product, after known outer native drain.

    This cleanup authority is not a passing product: cancellation/source/receipt
    errors still fail acceptance. An attempt or merely allocated start grants none.
    """
    binding, before, canonical = parse(binding_raw), parse(prelaunch_raw), parse(canonical_raw)
    require(before.get("bindingSha256") == digest(binding_raw) and before.get("device") == binding["selected"]["device"] and
            before.get("scope") == "CURRENT_SHUTDOWN_BEFORE_PRIMARY_LAUNCH" and outer.get("phase") == "product" and
            outer.get("retirement") == "KNOWN" and outer.get("survivors") == [] and outer.get("job") == binding["job"] and
            outer.get("state") == binding["state"] and outer.get("home") == binding["home"] and
            outer.get("simulatorBindingSha256") == digest(binding_raw), "SIMULATOR_LAUNCH_AUTHORITY_REQUIRED")
    native = created_native_launch(outer.get("ownership"), 0, outer["argv"], binding["root"], binding["job"], outer["invocation"])
    start = canonical_start(binding_raw, start_raw, outer["childAncestorInvocationIds"], native["launch"]["pid"])
    immutable = ("schema", "id", "purpose", "kind", "requestedArgv", "cwd", "wrapper", "host", "jobId", "gradleHome",
                 "startedUtc", "controllerPid", "ancestorInvocationIds", "evidenceDirectory")
    require(type(canonical) is dict and all(type(canonical.get(key)) is type(start[key]) and canonical[key] == start[key]
            for key in immutable) and canonical.get("sourceBefore") == binding["source"] and
            canonical.get("executedArgv") == start["requestedArgv"] and canonical.get("ownedSurvivors") == [],
            "SIMULATOR_CANONICAL_PRODUCT_NOT_STARTED")
    product = created_native_launch(canonical.get("ownership"), canonical.get("productLaunchIndex"),
                                   start["requestedArgv"], binding["root"], binding["job"], binding["productInvocation"])
    require(type(canonical.get("productPid")) is int and canonical["productPid"] == product["launch"]["pid"],
            "SIMULATOR_CANONICAL_PRODUCT_NOT_STARTED")
    return encoded({"schema": 1, "scope": "CREATED_PRIMARY_PRODUCT_AFTER_CURRENT_SHUTDOWN",
        "bindingSha256": digest(binding_raw), "prelaunchSha256": digest(prelaunch_raw), "canonicalStartSha256": digest(start_raw),
        "canonicalReceiptSha256": digest(canonical_raw), "outerPhaseSha256": digest(encoded(outer)),
        "canonicalNative": native, "productNative": product, "device": binding["selected"]["device"]})


def coverage_identity(binding_raw, start_raw, prelaunch_raw):
    binding = parse(binding_raw)
    return {"bindingSha256": digest(binding_raw), "admissionSha256": binding["admissionSha256"],
            "canonicalContextSha256": binding["canonicalContextSha256"], "job": binding["job"],
            "productInvocation": binding["productInvocation"], "device": binding["selected"]["device"]["udid"],
            "runtime": binding["selected"]["runtime"]["identifier"], "canonicalStartSha256": digest(start_raw),
            "prelaunchSha256": digest(prelaunch_raw)}


def assess_coverage(report, binding_raw, start_raw, prelaunch_raw):
    expected = coverage_identity(binding_raw, start_raw, prelaunch_raw)
    actual = report.get("ordinarySimulator")
    require(type(actual) is dict and set(actual) == set(expected) | {"configured", "inGraph", "unchanged"} and
            all(actual[key] == value for key, value in expected.items()) and actual["unchanged"] is True,
            "SIMULATOR_COVERAGE_BINDING")
    configured, graph = actual["configured"], actual["inGraph"]
    require(type(configured) is dict and set(configured) == set(TASKS) and type(graph) is dict,
            "SIMULATOR_KGP_TASK_MODEL_CHANGED")
    for records in (configured, graph):
        require(all(value == {"device": expected["device"], "type": TYPE} for value in records.values()),
                "SIMULATOR_KGP_PROPERTY_CHANGED")
    tests = report.get("tests", {})
    require(all(type(tests.get(path)) is dict and type(tests[path].get("inGraph")) is bool for path in TASKS) and
            set(graph) == {path for path in TASKS if tests[path]["inGraph"]}, "SIMULATOR_KGP_GRAPH_CHANGED")
    suffix = ":iosSimulatorArm64Test" if parse(binding_raw)["role"] == "macos-arm64" else ":iosX64Test"
    require(all(path in graph for path in TASKS if path.endswith(suffix)), "SIMULATOR_APPLICABLE_GRAPH_MISSING")
    return expected
