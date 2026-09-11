#!/usr/bin/env python3
"""Run the admitted scanner once; reporting must never turn its failure green."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

MAX_SARIF_BYTES = 16 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
SBOM_ARGUMENT = "--sbom=./library/p2p-transport-lan/vendor/jmdns/upstream.cdx.json"
sys.dont_write_bytecode = True
SBOM_SPEC = importlib.util.spec_from_file_location("p2pkit_sbom_validation", ROOT / "scripts/validate-sbom.py")
SBOM = importlib.util.module_from_spec(SBOM_SPEC)
SBOM_SPEC.loader.exec_module(SBOM)


def set_output(name, value):
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"{name}={value}\n")


def require_sarif(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_SARIF_BYTES + 1)
    if not raw or len(raw) > MAX_SARIF_BYTES:
        raise ValueError("SARIF must be nonempty and at most 16 MiB")
    report = json.loads(raw)
    if not isinstance(report, dict) or report.get("version") != "2.1.0":
        raise ValueError("scanner did not emit a SARIF 2.1.0 report")
    runs = report.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or not isinstance(runs[0], dict):
        raise ValueError("SARIF must contain exactly one scanner run")
    try:
        driver = runs[0]["tool"]["driver"]
        valid = driver["name"] == "osv-scanner" and isinstance(runs[0].get("results", []), list)
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise ValueError("SARIF is missing the scanner identity or has invalid results")


def scan(scanner, directory, argument_text):
    arguments = [line.strip() for line in argument_text.splitlines() if line.strip()]
    config = "--config=./osv-scanner.toml"
    if (arguments.count(config) != 1 or arguments.count(SBOM_ARGUMENT) != 1 or len(arguments) < 3 or
            len(set(arguments)) != len(arguments) or
            any(arg not in (config, SBOM_ARGUMENT) and not arg.startswith("--lockfile=") for arg in arguments)):
        raise ValueError("scan arguments must be one repository config, the exact upstream SBOM and unique lockfiles")
    # This advisory inventory records true upstream ancestry, not a fake Maven
    # identity for modified embedded bytes. Stale/missing provenance blocks scan.
    SBOM.validate_upstream_inventory(ROOT / SBOM.VENDOR_RELATIVE / "upstream.cdx.json", ROOT / SBOM.VENDOR_RELATIVE)
    # Never admit an existing output directory: a stale report is not fresh scanning.
    directory = directory.resolve()
    directory.mkdir(mode=0o700)
    set_output("report_dir", directory)
    sarif = directory / "results.sarif"
    log = directory / "scanner.log"
    # --all-vulns preserves strict advisory handling for locks and upstream input.
    # The expiring repository exceptions are still applied by the scanner first.
    command = [scanner, "scan", "source", "--all-vulns", "--format=sarif", f"--output-file={sarif}", *arguments]
    (directory / "scan-command.json").write_text(json.dumps(command) + "\n", encoding="utf-8")
    with log.open("xb") as output:
        # Relative admitted inputs must resolve to the same checkout preflight validated.
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=False)
    code = result.returncode if result.returncode >= 0 else 128 - result.returncode
    (directory / "scanner-exit-code.txt").write_text(f"{code}\n", encoding="utf-8")
    set_output("scan_exit", code)
    with log.open("rb") as output:
        shutil.copyfileobj(output, sys.stdout.buffer)
    print(f"Original OSV scanner exit code: {code}", flush=True)
    # Operational failures must not upload an empty/partial report as clean.
    if code not in (0, 1):
        return code
    try:
        require_sarif(sarif)
    except (OSError, ValueError) as error:
        print(f"FATAL: invalid scanner report: {error}", file=sys.stderr)
        return code or 1
    set_output("sarif_ready", "true")
    # No continue-on-error: GitHub preserves this failing step even if uploads pass.
    return code


def main():
    if len(sys.argv) != 3:
        print("Usage: run-osv-scan.py SCANNER NEW_REPORT_DIRECTORY", file=sys.stderr)
        return 2
    try:
        return scan(sys.argv[1], Path(sys.argv[2]), os.environ.get("OSV_SCAN_ARGS", ""))
    except (OSError, ValueError) as error:
        print(f"FATAL: OSV scan could not complete: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
