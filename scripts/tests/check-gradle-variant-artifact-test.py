#!/usr/bin/python3
"""Bounded locator parsing and path-aware, offline curator contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("variant_locator", ROOT / "scripts/resolve-gradle-variant-artifact.py")
LOCATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOCATOR)
GROUP, MODULE, VERSION = "example.variant", "variant", "1.0-jre"
ARTIFACT = "variant-1.0-android.jar"
FINGERPRINT = "41CD49B4EF5876F9E9F691DABAC30622339994C4"
SHA = "a" * 64
PREFIX = "https://repo.maven.apache.org/maven2/"
COMPONENT_PATH = "example/variant/variant"


def document(artifact: str = ARTIFACT) -> dict:
    return {
        "formatVersion": "1.1",
        "component": {"group": GROUP, "module": MODULE, "version": VERSION},
        "variants": [
            {"name": name, "files": [{"name": artifact, "url": f"../1.0-android/{artifact}"}]}
            for name in ("androidApiElements", "androidRuntimeElements")
        ],
    }


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-variant-parser.")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "variant.module"

    def locate(self, value: dict) -> str:
        self.path.write_text(json.dumps(value), encoding="utf-8")
        return LOCATOR.artifact_path([str(self.path), GROUP, MODULE, VERSION, ARTIFACT, SHA])

    def test_equivalent_sibling_records_without_optional_hashes(self):
        self.assertEqual(self.locate(document()), f"{COMPONENT_PATH}/1.0-android/{ARTIFACT}")

    def test_local_and_equivalent_normalized_records(self):
        value = document()
        value["variants"][0]["files"][0]["url"] = ARTIFACT
        value["variants"][1]["files"][0]["url"] = f"../{VERSION}/{ARTIFACT}"
        self.assertEqual(self.locate(value), f"{COMPONENT_PATH}/{VERSION}/{ARTIFACT}")

    def test_hash_when_present_must_match_external_verification(self):
        value = document()
        value["variants"][0]["files"][0]["sha256"] = SHA
        self.locate(value)
        for sha in ("b" * 64, None, 1, [SHA]):
            with self.subTest(sha=sha), self.assertRaisesRegex(ValueError, "SHA-256 disagrees"):
                value["variants"][0]["files"][0]["sha256"] = sha
                self.locate(value)

    def test_unsafe_and_ambiguous_paths(self):
        urls = [
            f"https://attacker.invalid/{ARTIFACT}", f"//attacker.invalid/{ARTIFACT}",
            f"/{ARTIFACT}", f"../../other/{ARTIFACT}", f"../..//{ARTIFACT}",
            f".././{ARTIFACT}", f"../%2e%2e/{ARTIFACT}", f"../1.0-android/{ARTIFACT}?x=1",
            f"../1.0-android/{ARTIFACT}#x", f"..\\1.0-android\\{ARTIFACT}",
            f"../1.0-android/other.jar", f"../1.0-android/sub/{ARTIFACT}", "", None,
        ]
        for url in urls:
            value = document()
            value["variants"][0]["files"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.locate(value)
        value = document()
        value["variants"][0]["files"][0]["url"] = ARTIFACT
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.locate(value)

    def test_component_and_format_identity(self):
        for key in ("group", "module", "version"):
            value = document()
            value["component"][key] = "other"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "identity mismatch"):
                self.locate(value)
        for version in ("1.0", None, 1.1):
            value = document()
            value["formatVersion"] = version
            with self.subTest(format=version), self.assertRaisesRegex(ValueError, "unsupported"):
                self.locate(value)

    def test_redirects_and_malformed_records(self):
        cases = []
        value = document()
        value["component"]["url"] = "../other/module"
        cases.append(value)
        value = document()
        value["variants"][0]["available-at"] = {"url": "../other/module"}
        cases.append(value)
        for variants in (None, {}, [], [None], [{"files": {}}], [{"files": [None]}], [{"files": []}]):
            value = document()
            value["variants"] = variants
            cases.append(value)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.locate(value)

    def test_invalid_json_duplicate_keys_encoding_and_size(self):
        raw = json.dumps(document()).encode()
        for invalid in (
            b"", b"[]", b"null", b"\xff", b"{", b"[" * 2000,
            raw.replace(b'"formatVersion": "1.1"', b'"formatVersion": "1.1", "formatVersion": "1.1"'),
            raw.replace(b'"formatVersion": "1.1"', b'"formatVersion": NaN'),
            raw + b" " * LOCATOR.MAX_METADATA_BYTES,
        ):
            with self.subTest(prefix=invalid[:50], size=len(invalid)), self.assertRaises((ValueError, RecursionError)):
                self.path.write_bytes(invalid)
                LOCATOR.artifact_path([str(self.path), GROUP, MODULE, VERSION, ARTIFACT, SHA])
        self.path.write_bytes(raw + b" " * (LOCATOR.MAX_METADATA_BYTES - len(raw)))
        self.assertEqual(LOCATOR.artifact_path([str(self.path), GROUP, MODULE, VERSION, ARTIFACT, SHA]),
                         f"{COMPONENT_PATH}/1.0-android/{ARTIFACT}")

    def test_invalid_coordinates_never_become_repository_paths(self):
        arguments = [str(self.path), GROUP, MODULE, VERSION, ARTIFACT, SHA]
        for index, value in ((1, "a..b"), (2, ".."), (3, "../other"), (4, "/evil.jar"), (5, "bad")):
            args = arguments.copy()
            args[index] = value
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "invalid"):
                LOCATOR.artifact_path(args)


class CuratorTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-variant-curator.")
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Path(self.temporary.name)
        for directory in ("scripts", "gradle", "mock-bin", "repository"):
            (self.fixture / directory).mkdir()
        for name in ("review-dependency-verification.sh", "resolve-gradle-variant-artifact.py",
                     "validate-gradle-plugin-marker.sh", "validate-gradle-plugin-metadata.py"):
            shutil.copy2(ROOT / "scripts" / name, self.fixture / "scripts" / name)
        (self.fixture / "gradle/plugin-provenance-policy.txt").write_text("# No unsigned locator exception\n")
        self.artifact = ARTIFACT
        self.value = document()
        self.bytes = b"synthetic independently signed variant bytes"
        self.jar_sha = hashlib.sha256(self.bytes).hexdigest()
        self.metadata = self.fixture / "gradle/verification-metadata.xml"
        self.repository = self.fixture / "repository"
        self.module_relative = f"{COMPONENT_PATH}/{VERSION}/{MODULE}-{VERSION}.module"
        self.module = self.repository / self.module_relative
        self.module.parent.mkdir(parents=True)
        self.module.write_text(json.dumps(self.value), encoding="utf-8")
        Path(str(self.module) + ".asc").write_text("synthetic signature")
        self.write_artifact()
        self.write_metadata(include_artifact=False)
        self.git("init", "-q")
        for key, value in (("user.name", "P2pKit Test"), ("user.email", "test@p2pkit.invalid"),
                           ("commit.gpgsign", "false"), ("core.hooksPath", "/dev/null")):
            self.git("config", key, value)
        self.git("add", "gradle/verification-metadata.xml")
        self.git("commit", "-qm", "existing checksum-listed locator")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.write_metadata()
        self.trace = self.fixture / "trace"
        self.trace.write_text("")
        self.env = dict(os.environ, PATH=f"{self.fixture / 'mock-bin'}:{os.environ['PATH']}",
                        MOCK_REPOSITORY=str(self.repository), MOCK_TRACE=str(self.trace), LC_ALL="C.UTF-8")
        self.mock("curl", r'''
output=""; url=""; maximum=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o) output="$2"; shift 2 ;;
        --max-filesize) maximum="$2"; shift 2 ;;
        http*) url="$1"; shift ;;
        *) shift ;;
    esac
done
printf 'curl %s\n' "$url" >>"$MOCK_TRACE"
prefix='https://repo.maven.apache.org/maven2/'
[[ "$url" == "$prefix"* && -n "$output" ]] || exit 22
source="$MOCK_REPOSITORY/${url#"$prefix"}"
[[ -f "$source" ]] || exit 22
[[ "$maximum" == 0 || "$(wc -c <"$source")" -le "$maximum" ]] || exit 63
cp "$source" "$output"
''')
        self.mock("gh", 'echo "unexpected attestation fallback" >&2; exit 91')
        self.mock("gpg", r'''
arguments=" $* "
fingerprint=41CD49B4EF5876F9E9F691DABAC30622339994C4
if [[ "$arguments" == *' --list-packets '* ]]; then
    printf ':signature packet: algo 1, keyid BAC30622339994C4\n'
    printf ' hashed subpkt 33 len 21 (issuer fpr v4 %s)\n' "$fingerprint"
elif [[ "$arguments" == *' --list-keys '* ]]; then
    printf 'pub:-:2048:1:BAC30622339994C4:0:0::-:::scESC::::::23::0:\n'
    printf 'fpr:::::::::%s:\n' "$fingerprint"
elif [[ "$arguments" == *' --verify '* ]]; then
    data="${!#}"
    printf 'verify %s\n' "${data##*/}" >>"$MOCK_TRACE"
    [[ "${MOCK_FAIL_SIGNATURE:-}" != "${data##*/}" ]] || exit 1
    if [[ "${MOCK_WRONG_SIGNER:-}" == "${data##*/}" ]]; then fingerprint=BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB; fi
    printf '[GNUPG:] VALIDSIG %s 2026-09-05 0 0 4 0 1 10 00 %s\n' "$fingerprint" "$fingerprint"
else
    echo "unexpected gpg invocation: $*" >&2; exit 2
fi
''')

    def git(self, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(self.fixture), *args], text=True)

    def mock(self, name: str, body: str):
        path = self.fixture / "mock-bin" / name
        path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n")
        path.chmod(0o755)

    def write_artifact(self):
        self.jar_relative = f"{COMPONENT_PATH}/1.0-android/{self.artifact}"
        self.jar = self.repository / self.jar_relative
        self.jar.parent.mkdir(exist_ok=True)
        self.jar.write_bytes(self.bytes)
        Path(str(self.jar) + ".asc").write_text("synthetic signature")

    def write_metadata(self, include_artifact: bool = True, include_module: bool = True, duplicate_hash: bool = False):
        entries = []
        if include_module:
            entries.append((f"{MODULE}-{VERSION}.module", hashlib.sha256(self.module.read_bytes()).hexdigest()))
            if duplicate_hash:
                entries.append((f"{MODULE}-{VERSION}.module", "b" * 64))
        if include_artifact:
            entries.append((self.artifact, self.jar_sha))
        artifacts = "\n".join(f'         <artifact name="{name}">\n'
                              f'            <sha256 value="{sha}"/>\n         </artifact>' for name, sha in entries)
        self.metadata.write_text(f'''<verification-metadata>
   <components>
      <component group="{GROUP}" name="{MODULE}" version="{VERSION}">
{artifacts}
      </component>
   </components>
</verification-metadata>
''')

    def curate(self, error: str | None = None, no_variant_fetch: bool = False) -> str:
        result = subprocess.run([str(self.fixture / "scripts/review-dependency-verification.sh"), self.base],
                                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if error is None:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn(error, result.stdout)
        if no_variant_fetch:
            self.assertNotIn(f"curl {PREFIX}{self.jar_relative}\n", self.trace.read_text())
        return result.stdout

    def test_signed_sibling_is_verified_before_use_even_when_locator_is_not_new(self):
        output = self.curate()
        self.assertIn("RESULT: PASS — reviewed 1 newly admitted artifacts", output)
        self.assertIn(f"VERIFIED-LOCATOR {GROUP}:{MODULE}:{VERSION}", output)
        self.assertIn(f"signer={FINGERPRINT}", output)
        trace = self.trace.read_text().splitlines()
        self.assertLess(trace.index("verify variant.module"), trace.index(f"curl {PREFIX}{self.jar_relative}"))
        self.assertLess(trace.index(f"curl {PREFIX}{self.jar_relative}"), trace.index("verify artifact"))
        self.assertEqual([line for line in trace if line.endswith("/" + self.artifact)], [
            f"curl {PREFIX}{COMPONENT_PATH}/{VERSION}/{self.artifact}",
            f"curl https://plugins.gradle.org/m2/{COMPONENT_PATH}/{VERSION}/{self.artifact}",
            f"curl https://dl.google.com/dl/android/maven2/{COMPONENT_PATH}/{VERSION}/{self.artifact}",
            f"curl {PREFIX}{self.jar_relative}",
        ])

    def test_missing_or_ambiguous_locator_checksum(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                self.write_metadata(include_module=duplicate, duplicate_hash=duplicate)
                self.curate("no unique checksum-listed module metadata", no_variant_fetch=True)
        self.assertNotIn(self.module_relative, self.trace.read_text())

    def test_missing_locator(self):
        self.module.unlink()
        self.curate("no repository module metadata", no_variant_fetch=True)

    def test_oversized_locator_download_is_bounded(self):
        self.module.write_bytes(self.module.read_bytes() + b" " * LOCATOR.MAX_METADATA_BYTES)
        self.write_metadata()
        self.curate("no repository module metadata", no_variant_fetch=True)
        self.assertNotIn("verify variant.module", self.trace.read_text())

    def test_locator_checksum_failure_precedes_use(self):
        self.module.write_bytes(self.module.read_bytes() + b" ")
        self.curate("downloaded bytes disagree with metadata", no_variant_fetch=True)
        self.assertNotIn("verify variant.module", self.trace.read_text())

    def test_locator_sidecar_failure_precedes_use(self):
        Path(str(self.module) + ".sha256").write_text("b" * 64)
        self.curate("repository checksum disagrees", no_variant_fetch=True)

    def test_unsigned_locator_never_uses_plugin_exception(self):
        Path(str(self.module) + ".asc").unlink()
        (self.fixture / "gradle/plugin-provenance-policy.txt").write_text(
            f"{GROUP}|{MODULE}|{VERSION}|example/upstream|example/upstream/.github/workflows/release.yml|"
            "refs/tags/v1.0|" + "a" * 40 + "\n")
        self.curate("no detached signature for variant metadata", no_variant_fetch=True)

    def test_invalid_locator_signature_and_signer_precede_use(self):
        for key, error in (("MOCK_FAIL_SIGNATURE", "invalid detached signature"),
                           ("MOCK_WRONG_SIGNER", "signature fingerprint mismatch")):
            with self.subTest(key=key):
                self.env[key] = "variant.module"
                self.curate(error, no_variant_fetch=True)
                del self.env[key]

    def test_authenticated_unsafe_locator_still_fails_before_use(self):
        self.value["variants"][0]["files"][0]["url"] = f"https://attacker.invalid/{ARTIFACT}"
        self.module.write_text(json.dumps(self.value))
        self.write_metadata()
        self.curate("variant artifact URL is not a same-module", no_variant_fetch=True)
        self.assertNotIn("curl https://attacker.invalid", self.trace.read_text())

    def test_missing_relocated_artifact_does_not_switch_repository(self):
        self.jar.unlink()
        self.curate("no artifact at verified variant location")
        self.assertEqual([line for line in self.trace.read_text().splitlines() if self.jar_relative in line],
                         [f"curl {PREFIX}{self.jar_relative}"])

    def test_relocated_artifact_checksum_and_signature_remain_required(self):
        self.jar.write_bytes(b"tampered")
        self.curate("downloaded bytes disagree with metadata")
        self.jar.write_bytes(self.bytes)
        self.env["MOCK_FAIL_SIGNATURE"] = "artifact"
        self.curate("invalid detached signature")

    def test_relocated_canonical_name_cannot_use_unsigned_plugin_exception(self):
        self.artifact = f"{MODULE}-{VERSION}.jar"
        self.value = document(self.artifact)
        self.module.write_text(json.dumps(self.value))
        self.write_artifact()
        self.write_metadata()
        Path(str(self.jar) + ".asc").unlink()
        (self.fixture / "gradle/plugin-provenance-policy.txt").write_text(
            f"{GROUP}|{MODULE}|{VERSION}|example/upstream|example/upstream/.github/workflows/release.yml|"
            "refs/tags/v1.0|" + "a" * 40 + "\n")
        self.curate("no detached signature for relocated artifact")

    def test_canonical_checksum_or_signature_failure_never_tries_locator(self):
        canonical = self.module.parent / ARTIFACT
        canonical.write_bytes(b"tampered canonical bytes")
        self.curate("downloaded bytes disagree with metadata", no_variant_fetch=True)
        canonical.write_bytes(self.bytes)
        Path(str(canonical) + ".asc").write_text("synthetic signature")
        self.env["MOCK_FAIL_SIGNATURE"] = "artifact"
        self.curate("invalid detached signature", no_variant_fetch=True)
        self.assertNotIn(self.module_relative, self.trace.read_text())

    def test_valid_sidecars_and_artifact_sidecar_failure(self):
        Path(str(self.module) + ".sha256").write_text(hashlib.sha256(self.module.read_bytes()).hexdigest())
        Path(str(self.jar) + ".sha256").write_text(self.jar_sha)
        self.assertIn("evidence=sha256-sidecar+signature", self.curate())
        Path(str(self.jar) + ".sha256").write_text("b" * 64)
        self.curate("repository checksum disagrees")


if __name__ == "__main__":
    unittest.main(verbosity=2)
