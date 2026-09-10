#!/usr/bin/env python3
"""Exercise the real embedded-license block with small ZIPs; no Gradle/publication."""

from pathlib import Path
import subprocess
import tempfile
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[2]
script = (ROOT / "scripts/check-publish-artifacts.sh").read_text()
start = "    # Embedded-license policy:"
end = "    # End embedded-license policy."
assert script.count(start) == script.count(end) == 1
policy = script[script.index(start):script.index(end) + len(end)]
license_bytes = (ROOT / "LICENSE").read_bytes()

# This executes the block inside check(), including the archive-class dispatch,
# not the surrounding POM/KLIB/publication checks. The real publication gate
# must still inspect candidate artifacts; these fixtures are not build evidence.
cases = [
    ("main-jar", ".jar", None, "valid"),
    ("main-aar", ".aar", None, "valid"),
    ("klib-main-exempt", ".klib", None, "valid"),
    ("klib-interop-exempt", ".klib", None, "valid"),
    ("missing-source-license", ".jar", "sources", "missing"),
    ("changed-dokka-license", ".jar", "javadoc", "changed"),
    ("duplicate-main-license", ".aar", "main", "duplicate"),
    ("klib-source-not-exempt", ".klib", "sources", "missing"),
    ("klib-metadata-not-exempt", ".klib", "metadata", "missing"),
    ("unreadable-dokka", ".jar", "javadoc", "unreadable"),
    ("unknown-main-policy", ".zip", None, "valid"),
]
for name, suffix, damaged, mode in cases:
    with tempfile.TemporaryDirectory(prefix="p2pkit-license-test-") as temporary:
        work = Path(temporary)
        (work / "LICENSE").write_bytes(license_bytes)
        paths = {"main": work / ("fixture" + suffix),
                 "sources": work / "fixture-sources.jar",
                 "javadoc": work / "fixture-javadoc.jar"}
        if suffix == ".klib":
            paths["metadata"] = work / "fixture-metadata.jar"
        has_interop = name == "klib-interop-exempt"
        if has_interop:
            paths["cinterop"] = work / "fixture-cinterop-p2pkit_nw.klib"
        for role, path in paths.items():
            kind = mode if damaged == role else "valid"
            if kind == "unreadable":
                path.write_bytes(b"not a zip")
                continue
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("fixture.txt", "synthetic")
                if kind != "missing" and not (role in ("main", "cinterop") and suffix == ".klib"):
                    archive.writestr("META-INF/LICENSE", b"changed" if kind == "changed" else license_bytes)
                if kind == "duplicate":
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        archive.writestr("META-INF/LICENSE", license_bytes)
        shell = """set -euo pipefail
ROOT="$1"
INSPECTION_DIR="$1"
run_policy() {
    local artifact=fixture main_suffix="$2" invalid=""
    local main="$1/fixture$2" sources="$1/fixture-sources.jar" javadoc="$1/fixture-javadoc.jar"
    local native_metadata="" cinterop=""
    if [[ "$2" == ".klib" ]]; then native_metadata="$1/fixture-metadata.jar"; fi
    if [[ "$3" == "interop" ]]; then cinterop="$1/fixture-cinterop-p2pkit_nw.klib"; fi
""" + policy + """
    [[ -z "$invalid" ]] || { echo "FAIL $invalid"; return 1; }
}
run_policy "$1" "$2" "$3"
"""
        result = subprocess.run(["bash", "-c", shell, "license-test", str(work), suffix,
                                 "interop" if has_interop else "none"],
                                capture_output=True, text=True, timeout=15)
        expected_pass = damaged is None and suffix != ".zip"
        assert (result.returncode == 0) == expected_pass, (name, result.returncode, result.stdout, result.stderr)
        assert ("EXEMPT " in result.stdout) == (suffix == ".klib"), (name, result.stdout)
        if has_interop:
            assert result.stdout.count("EXEMPT ") == 2, result.stdout
        if expected_pass:
            assert result.stdout.count("one canonical META-INF/LICENSE") == 3, result.stdout
        else:
            assert "FAIL " in result.stdout, (name, result.stdout, result.stderr)
        print(f"OK {name}")
print(f"RESULT: PASS — {len(cases)} embedded-license ZIP fixtures (no build/publication)")
