#!/usr/bin/env python3
"""Reuse static app/MSI inspectors in ordinary modular CI; never install or launch the application.

WiX runs in the maintained owned-command executor. Only bounded metadata and closed
tool logs enter build/reports; extracted payloads stay in the ephemeral runner temp.
The hosted context is a consistency check under ordinary workflow/runner trust.
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


P = load("rpc_package_samples", "package-sample-apps.py")
A = load("rpc_package_image", "verify-rpc-windows-app-image.py")
M = load("rpc_package_msi", "verify-rpc-windows-msi-payload.py")
SCOPE = "STATIC_RPC_WINDOWS_PACKAGE_NOT_INSTALLED_OR_RUNTIME_QUALIFIED"
WORKFLOWS = {"p2pKit/P2pKit/.github/workflows/ci.yml",
             "p2pKit/P2pKit/.github/workflows/desktop-cross-host.yml"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def context(root, environment):
    result = P.context(root, environment)
    workflow, separator, _ = result["workflow_ref"].partition("@")
    require(result["platform"] == "windows" and result["architecture"] == "x64" and
            result["job"] == "run" and separator == "@" and workflow in WORKFLOWS and
            result["workflow_sha"] == result["commit"] and environment.get("COMPONENT") == "desktop-windows",
            "Unexpected Windows package component context")
    return result


def new_reports(root):
    parent = root
    for part in ("build", "reports"):
        parent /= part
        parent.mkdir(exist_ok=True)
        P.physical_directory(parent)
    reports = parent / "rpc-windows-package"
    reports.mkdir()
    P.physical_directory(reports)
    return reports


def write_json(path, document, maximum=65536):
    raw = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    require(len(raw) <= maximum, "Package metadata exceeds bound")
    with path.open("xb") as stream:
        stream.write(raw)


def run_tool(argv, name, root, reports, environment, source, limit):
    raw_deadline = environment.get("P2PKIT_CI_COMMAND_DEADLINE_NS", "")
    require(re.fullmatch(r"[1-9][0-9]{0,19}", raw_deadline), "Missing enclosing command deadline")
    # Keep the existing outer command deadline; reserve the native executor's cleanup.
    remaining = int(raw_deadline) / 1_000_000_000 - time.monotonic() - 15
    require(remaining > 0, "Enclosing command has no tool budget")
    private = reports / name
    outcome = E.run_command(argv, cwd=root, environment=environment, private=private,
                            timeout=min(limit, remaining), log_limit=1024 * 1024, cleanup_seconds=15.0)
    write_json(private / "outcome.json", {"scope": "STATIC_MSI_TOOL_NOT_INSTALLATION", "source": source,
               "commandSha256": hashlib.sha256(json.dumps(argv, separators=(",", ":")).encode()).hexdigest(),
               "outcome": outcome})
    require(outcome.get("exitCode") == 0 and outcome.get("code") == "PASS" and
            outcome.get("timedOut") is False and outcome.get("cleanupKnown") is True and
            outcome.get("capturesClosed") is True, "Static package tool did not complete safely")
    return private, outcome


def inspect_package(root, environment):
    source = context(root, environment)
    base = root / P.INSTALLER_ROOT
    image = base / "app/P2pKit Sample"
    P.physical_directory(image)
    msi_directory = base / "msi"
    P.physical_directory(msi_directory)
    members = list(msi_directory.iterdir())
    require(len(members) <= 64, "Unexpected installer directory size")
    installers = [path for path in members if path.suffix.lower() == ".msi"]
    require(len(installers) == 1, "Expected exactly one produced MSI")
    msi = installers[0]
    compiler = root / ("samples/p2p-sample-desktop-ui/build/rpc-windows-profile/" + source["commit"] +
                       "/compiler/compiler.properties")
    P.physical_directory(compiler.parent)
    compiler_before = P.file_hash(compiler, 512)
    msi_before = P.file_hash(msi, 1024 ** 3)
    wix = environment.get("WIX", "")
    require(wix and Path(wix).is_absolute(), "Missing absolute installed WiX location")
    dark = Path(wix) / "bin/dark.exe"
    P.physical_directory(dark.parent)
    dark_before = P.file_hash(dark, 32 * 1024 ** 2)
    require(dark_before["bytes"] > 0, "Empty installed WiX tool")
    temporary = Path(environment.get("RUNNER_TEMP", ""))
    P.physical_directory(temporary)
    require(not temporary.is_relative_to(root) and not root.is_relative_to(temporary),
            "Extraction must remain outside the checkout and reports")
    reports = new_reports(root)
    work = temporary / ("p2pkit-rpc-msi-" + source["run_id"] + "-" + source["run_attempt"])
    work.mkdir()
    P.physical_directory(work)
    wix_temp = work / "temp"
    wix_temp.mkdir()
    extracted, wxs = work / "payload", work / "product.wxs"
    child_environment = dict(environment, WIX_TEMP=str(wix_temp))

    # Reuse the maintained strict inspector, including the staged JDK21 adapter.
    image_record = A.inspect(image, compiler, msi, source["commit"], source["tree"], preview_adapter=True)
    inspection = reports / "app-image-inspection.json"
    write_json(inspection, image_record)

    version_logs, version_outcome = run_tool([str(dark), "-?"], "dark-version", root, reports,
                                            child_environment, source, 10)
    version_output = M.read(version_logs / "stdout.log", 65536).decode("utf-8-sig")
    versions = re.findall(r"^Windows Installer XML Toolset Decompiler version (3\.[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5})\r?$",
                          version_output, re.MULTILINE)
    require(len(versions) == 1, "Unexpected installed WiX version output")
    require(P.file_hash(dark, 32 * 1024 ** 2) == dark_before, "WiX tool changed during version inspection")
    write_json(reports / "tool.json", {"scope": "INSTALLED_WIX_OBSERVATION_NOT_SUPPLIER_ATTESTATION",
               "source": source, "file": "dark.exe", **dark_before, "version": versions[0],
               "versionOutcome": version_outcome})

    _, extraction_outcome = run_tool([str(dark), "-nologo", "-x", str(extracted), str(msi), str(wxs)],
                                     "dark-extraction", root, reports, child_environment, source, 60)
    require(P.file_hash(dark, 32 * 1024 ** 2) == dark_before, "WiX tool changed during extraction")
    P.physical_directory(extracted)
    xml = M.read(wxs, M.XML_LIMIT)
    with (reports / "decompiled-product.wxs").open("xb") as stream:
        stream.write(xml)
    require(M.read(reports / "decompiled-product.wxs", M.XML_LIMIT) == xml, "Retained MSI metadata differs")
    try:
        payload = M.inspect(wxs, extracted, image, inspection, msi)
    except M.PayloadPathMismatch as error:
        try:
            diagnostic = E.rpc_package_path_mismatch(error.diagnostic)
            require(type(error) is M.PayloadPathMismatch and diagnostic is not None,
                    "Invalid finite MSI path-mismatch observation")
            write_json(reports / "msi-payload-refusal.json", {
                "scope": M.SCOPE, "result": "REFUSED", "reason": "RPC_MSI_PAYLOAD_PATHS",
                "source": source, "msi": msi_before,
                "imageInspectionSha256": P.file_hash(inspection, 65536)["sha256"],
                "wxsSha256": hashlib.sha256(xml).hexdigest(),
                "comparedFiles": error.compared_files, "pathMismatch": diagnostic,
                "installation": "NOT_PERFORMED", "nativeExecution": "NOT_PERFORMED",
            })
        except (OSError, ValueError, RuntimeError):
            # Supplemental evidence cannot replace the original payload refusal.
            print("RPC_WINDOWS_PACKAGE_REFUSAL_RECORD_FAILED", file=sys.stderr)
        raise
    require(payload["source"] == source["commit"] and payload["tree"] == source["tree"] and
            payload["scope"] == M.SCOPE and payload["result"] == "PASS" and
            len(payload["comparedFiles"]) == 4, "Incomplete source-bound MSI adapter inspection")
    write_json(reports / "msi-payload-inspection.json", payload)
    require(A.inspect(image, compiler, msi, source["commit"], source["tree"], preview_adapter=True) == image_record and
            P.file_hash(compiler, 512) == compiler_before and P.file_hash(msi, 1024 ** 3) == msi_before and
            P.file_hash(dark, 32 * 1024 ** 2) == dark_before and context(root, environment) == source,
            "Source or package inputs changed during inspection")
    result = {"schema": 1, "scope": SCOPE, "result": "PASS", "source": source,
              "msi": msi_before, "tool": {**dark_before, "version": versions[0]},
              "wxsSha256": hashlib.sha256(xml).hexdigest(), "comparedPayloads": 4,
              "extractionOutcome": extraction_outcome,
              "extractedPayloads": "EPHEMERAL_RUNNER_TEMP_OUTSIDE_REPORTS",
              "installation": "NOT_PERFORMED", "runtimeReadback": "NOT_PERFORMED",
              "nativeProvider": "NOT_PERFORMED", "wholeLifetimeSupervision": "NOT_PERFORMED"}
    write_json(reports / "result.json", result)
    return result


def failure_diagnostic(error):
    """Return only reviewed source error labels/line numbers, never a raw path or exception."""
    lines = []
    frame = error.__traceback__
    while frame is not None and len(lines) < 16:
        if frame.tb_frame.f_code.co_filename == M.__file__ and 0 < frame.tb_lineno <= 99999:
            lines.append(frame.tb_lineno)
        frame = frame.tb_next
    category = None
    # Only a real MSI-checker frame admits its finite message. An unrelated
    # package/tool exception cannot lend the MSI inspector its identity.
    if lines and type(error) in (ValueError, M.PayloadPathMismatch) and len(error.args) == 1 and type(error.args[0]) is str:
        category = E.RPC_PACKAGE_ERRORS.get(error.args[0])
    return category, lines


def main():
    try:
        require(len(sys.argv) == 1, "No path, context or command overrides accepted")
        inspect_package(ROOT, dict(os.environ))
        print(SCOPE + ": PASS")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        category, lines = failure_diagnostic(error)
        if category is not None:
            print("RPC_WINDOWS_PACKAGE_FAILURE " + category, file=sys.stderr)
        if lines:
            print("RPC_WINDOWS_PACKAGE_CHECK_LINES " + ",".join(map(str, lines)), file=sys.stderr)
        if category == "RPC_MSI_PAYLOAD_PATHS" and type(error) is M.PayloadPathMismatch:
            diagnostic = E.rpc_package_path_mismatch(error.diagnostic)
            if diagnostic is not None:
                print("RPC_WINDOWS_PACKAGE_PATHS " + json.dumps(diagnostic, sort_keys=True,
                      separators=(",", ":")), file=sys.stderr)
        print("RPC_WINDOWS_PACKAGE_INSPECTION_REFUSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
