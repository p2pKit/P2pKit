#!/usr/bin/env python3
"""Two existing build-image module probes, not installation or productive native loading.

Port the bounded observations from check-hosted-runtime-readback.ps1 without
activating its retired workflow guards or process helper. Ordinary hosted workflow
trust applies; inventory continuity is not protection against a hostile launcher
owner, and these short commands do not qualify the installed application's life.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_evidence as E


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load("rpc_runtime_samples", "package-sample-apps.py")
A = load("rpc_runtime_image", "verify-rpc-windows-app-image.py")
SCOPE = "EXISTING_BUILD_IMAGE_MODULE_PROBES_NOT_INSTALLED_DLL_PROFILE_OR_RELEASE"
WORKFLOWS = {"p2pKit/P2pKit/.github/workflows/ci.yml",
             "p2pKit/P2pKit/.github/workflows/desktop-cross-host.yml"}
OVERRIDES = ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "JPACKAGE_DEBUG")
MEMBERS = ("P2pKit Sample.exe", "app/P2pKit Sample.cfg", "runtime/release", "runtime/lib/modules",
           "runtime/bin/server/jvm.dll", "runtime/bin/jli.dll", A.ADAPTER_PATH)
PROBES = (("runtime-module-readback", "--rpc-windows-runtime-readback"),
          ("runtime-loader-preview-readback", "--rpc-windows-loader-readback"))
VERSION = r"21(?:[.+-][0-9A-Za-z.+_-]+)?"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def context(root, environment):
    source = P.context(root, environment)
    workflow, separator, _ = source["workflow_ref"].partition("@")
    require(source["platform"] == "windows" and source["architecture"] == "x64" and
            source["job"] == "run" and separator == "@" and workflow in WORKFLOWS and
            source["workflow_sha"] == source["commit"] and environment.get("COMPONENT") == "desktop-windows",
            "Unexpected runtime component context")
    require(all(not environment.get(name) for name in OVERRIDES), "Ambient Java/launcher override")
    return source


def read(path, maximum):
    P.physical_directory(path.parent)
    before = P.file_hash(path, maximum)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) == before["bytes"] and hashlib.sha256(raw).hexdigest() == before["sha256"] and
            P.file_hash(path, maximum) == before, "Read input changed")
    return raw


def parse_json(raw):
    def reject_constant(_):
        raise ValueError("Nonfinite JSON")
    return json.loads(raw, object_pairs_hook=P.unique_pairs, parse_constant=reject_constant)


def write_json(path, record):
    raw = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
    require(len(raw) <= 1024 * 1024, "Oversized runtime record")
    with path.open("xb") as stream:
        stream.write(raw)


def inventory(image, application_jar):
    P.physical_directory(image)
    P.physical_directory(image / "app")
    jars = sorted((image / "app").glob("*.jar"))
    require(0 < len(jars) <= 512 and application_jar in {path.name for path in jars},
            "Missing or oversized application classpath")
    result, total = {}, 0
    for member in (*MEMBERS, *("app/" + path.name for path in jars)):
        path = image / member
        P.physical_directory(path.parent)
        value = P.file_hash(path, 512 * 1024 ** 2)
        require(value["bytes"] > 0, "Empty runtime member")
        total += value["bytes"]
        require(total <= 1024 ** 3, "Runtime inventory exceeds existing bound")
        result[member] = value
    return result


def inspection_inputs(record, source, members):
    require(isinstance(record, dict) and record.get("source") == source["commit"] and
            record.get("tree") == source["tree"] and record.get("result") == "PASS" and
            record.get("scope") == A.SCOPE and record.get("declaredUnsupportedModule") is True,
            "No current successful static image inspection")
    adapter = record.get("adapter")
    require(isinstance(adapter, dict) and adapter.get("scope") == A.ADAPTER_SCOPE and
            adapter.get("file") == A.ADAPTER_PATH and adapter.get("module") == A.ADAPTER_MODULE and
            members[A.ADAPTER_PATH] == {"bytes": adapter.get("jarBytes"), "sha256": adapter.get("jarSha256")},
            "Static adapter binding mismatch")
    launcher = adapter.get("launcher")
    require(isinstance(launcher, dict) and launcher.get("file") == "app/P2pKit Sample.cfg" and
            launcher.get("sha256") == members["app/P2pKit Sample.cfg"]["sha256"] and
            launcher.get("requiredOptions") == list(A.ADAPTER_OPTIONS), "Static launcher binding mismatch")
    jars = record.get("requiredClassJars")
    require(isinstance(jars, list) and 0 < len(jars) <= 512, "Missing static class bindings")
    for jar in [record.get("parentPin"), *jars]:
        require(isinstance(jar, dict) and isinstance(jar.get("file"), str) and
                re.fullmatch(r"[A-Za-z0-9_.-]+\.jar", jar["file"]) and
                members.get("app/" + jar["file"]) == {"bytes": jar.get("jarBytes"),
                                                     "sha256": jar.get("jarSha256")},
                "Static application/pin JAR binding mismatch")
    msi = record.get("msi")
    require(isinstance(msi, dict) and isinstance(msi.get("file"), str) and
            Path(msi["file"]).name == msi["file"] and msi["file"].lower().endswith(".msi") and
            type(msi.get("bytes")) is int and 8 <= msi["bytes"] <= 1024 ** 3 and
            isinstance(msi.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", msi["sha256"]),
            "Invalid static MSI binding")


def validate_observation(observation, source, declared_version, preview):
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source) and
            isinstance(declared_version, str) and len(declared_version) <= 128 and
            re.fullmatch(VERSION, declared_version) and isinstance(observation, dict), "Invalid observation inputs")
    if preview:
        require(set(observation) == {"source", "adapter"} and observation["source"] == source and
                isinstance(observation["adapter"], dict), "Unexpected preview source/fields")
        value = observation["adapter"]
        booleans = {"previewEnabled": True, "namedNativeAccess": True, "unnamedNativeAccess": False,
                    "ffmFromJavaBase": True, "windowsX64Hint": True, "productionAvailable": False}
        strings = {"scope": "JDK21_PREVIEW_MODULE_DIAGNOSTIC_NOT_DLL_OR_PROFILE",
                   "module": "dev.p2pkit.rpc.windows.loader", "nativeLoad": "NOT_PERFORMED",
                   "profileAccess": "NOT_PERFORMED"}
        require(set(value) == {"schema", "javaFeature", "javaVersion", "javaVendor", "javaRuntimeVersion",
                               "javaVmVersion", *booleans, *strings} and
                type(value["schema"]) is int and value["schema"] == 1 and
                type(value["javaFeature"]) is int and value["javaFeature"] == 21,
                "Unexpected preview schema/runtime fields")
        require(all(value[name] is expected for name, expected in booleans.items()) and
                all(value[name] == expected for name, expected in strings.items()), "Unexpected preview authority")
        require(all(isinstance(value[name], str) and 1 <= len(value[name]) <= 128 and
                    re.fullmatch(r"[\x20-\x7e]+", value[name])
                    for name in ("javaVendor", "javaRuntimeVersion", "javaVmVersion")),
                "Invalid runtime supplier metadata")
    else:
        value = observation
        require(set(value) == {"scope", "source", "javaFeature", "javaVersion", "module", "options",
                               "nativeLoad", "profileAccess"} and value["source"] == source and
                value["scope"] == "WINDOWS_RUNTIME_MODULE_RESOLUTION_ONLY_NOT_PROFILE_OR_RELEASE" and
                type(value["javaFeature"]) is int and value["javaFeature"] == 21 and
                value["module"] == "jdk.unsupported" and
                value["options"] == ["NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_DELETE"] and
                value["nativeLoad"] == "NOT_PERFORMED" and value["profileAccess"] == "NOT_PERFORMED",
                "Unexpected module-resolution observation")
    require(isinstance(value["javaVersion"], str) and len(value["javaVersion"]) <= 128 and
            re.fullmatch(VERSION, value["javaVersion"]) and
            value["javaVersion"].split("+")[0] == declared_version.split("+")[0], "Runtime version mismatch")


def probe(root, image, name, argument, reports, environment, source, declared_version, preview):
    deadline = environment.get("P2PKIT_CI_COMMAND_DEADLINE_NS", "")
    require(re.fullmatch(r"[1-9][0-9]{0,19}", deadline), "Missing enclosing command deadline")
    remaining = int(deadline) / 1_000_000_000 - time.monotonic() - 15
    require(remaining > 0, "No remaining runtime probe budget")
    private = reports / name
    outcome = E.run_command([str(image / "P2pKit Sample.exe"), argument], cwd=root, environment=environment,
                            private=private, timeout=min(15.0, remaining), log_limit=4096, cleanup_seconds=15.0)
    write_json(private / "outcome.json", {"source": source, "scope": SCOPE, "outcome": outcome})
    require(outcome.get("code") == "PASS" and type(outcome.get("exitCode")) is int and
            outcome["exitCode"] == 0 and outcome.get("timedOut") is False and
            outcome.get("cleanupKnown") is True and outcome.get("capturesClosed") is True,
            "Runtime command did not complete safely")
    # Never inspect unclosed/uncertain captures, including when the launcher exits zero.
    stdout, stderr = read(private / "stdout.log", 2048), read(private / "stderr.log", 2048)
    require(not stderr and re.fullmatch(rb"\{[^\r\n]+\}\r?\n", stdout), "Unexpected runtime output framing")
    observation = parse_json(stdout)
    validate_observation(observation, source["commit"], declared_version, preview)
    return {"argument": argument, "observation": observation, "execution": outcome}


def check_runtime(root, environment):
    source = context(root, environment)
    image = root / P.INSTALLER_ROOT / "app/P2pKit Sample"
    inspection = root / "build/reports/rpc-windows-package/app-image-inspection.json"
    inspection_raw = read(inspection, 65536)
    record = parse_json(inspection_raw)
    require(isinstance(record, dict) and isinstance(record.get("applicationJar"), str) and
            re.fullmatch(r"[A-Za-z0-9_.-]+\.jar", record["applicationJar"]), "Invalid static application JAR")
    before = inventory(image, record["applicationJar"])
    inspection_inputs(record, source, before)
    msi = root / P.INSTALLER_ROOT / "msi" / record["msi"]["file"]
    P.physical_directory(msi.parent)
    msi_bytes = {name: record["msi"][name] for name in ("bytes", "sha256")}
    require(P.file_hash(msi, 1024 ** 3) == msi_bytes, "MSI differs from static inspection")
    release = read(image / "runtime/release", 65536).decode("utf-8")
    versions = re.findall(r'^JAVA_VERSION="([0-9][0-9A-Za-z.+_-]*)"\r?$', release, re.MULTILINE)
    require(len(versions) == 1 and len(versions[0]) <= 128 and re.fullmatch(VERSION, versions[0]),
            "Missing unique linked JDK21 version")
    reports = root / "build/reports/rpc-windows-runtime-readback"
    P.physical_directory(reports.parent)
    reports.mkdir(mode=0o700)
    results = []
    for index, (name, argument) in enumerate(PROBES):
        results.append(probe(root, image, name, argument, reports, environment, source, versions[0], index == 1))
        require(P.file_hash(msi, 1024 ** 3) == msi_bytes and
                read(inspection, 65536) == inspection_raw and inventory(image, record["applicationJar"]) == before and
                context(root, environment) == source, "Source, static receipt or runtime member changed")
    result = {"schema": 1, "scope": SCOPE, "result": "PASS", "source": source,
              "imageInspectionSha256": hashlib.sha256(inspection_raw).hexdigest(), "msi": record["msi"],
              "inputs": before, "probes": results, "installedRuntime": "NOT_PERFORMED",
              "nativeProvider": "NOT_PERFORMED", "wholeLifetimeSupervision": "NOT_PERFORMED"}
    write_json(reports / "result.json", result)
    return result


def main():
    try:
        require(len(sys.argv) == 1, "No path, context or command overrides accepted")
        check_runtime(ROOT, dict(os.environ))
        print(SCOPE + ": PASS")
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        print("RPC_WINDOWS_IMAGE_RUNTIME_READBACK_REFUSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
