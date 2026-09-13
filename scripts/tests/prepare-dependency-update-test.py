#!/usr/bin/env python3
"""Hermetic real-caller sequencing; no Gradle, downloads, credentials or GPG.

Only expensive phases are stubs. The caller, XML/input classifier, metadata
validator and disposable Git repository are real. The curator suite separately
exercises the actual empty-input guard and cryptographic rejection controls.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
NS = "https://schema.gradle.org/dependency-verification"
STUB = r'''
import json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ["FIXTURE"])
control = json.loads(pathlib.Path(os.environ["CONTROL"]).read_text())
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == "gradlew":
    if args == ["resolveAndLockAll", "--write-locks", "--write-verification-metadata", "sha256",
                "--no-configure-on-demand", "--no-daemon", "--console=plain"]:
        phase = "writer"
    elif args == ["verifyBuildPluginSecurityFloors", "help", "--dependency-verification=strict",
                  "--no-daemon", "--console=plain"]:
        phase = "strict"
    else:
        raise AssertionError("changed or partial Gradle command: " + repr(args))
else:
    phase = {"check-gradle-wrapper.sh": "wrapper", "check-dependency-verification.sh": "metadata",
             "review-dependency-verification.sh": "curator"}[name]
with open(os.environ["TRACE"], "a") as output:
    output.write(json.dumps({"phase": phase, "args": args}) + "\n")
if control.get("failPhase") == phase:
    if phase == "writer":
        (root / "gradle.lockfile").write_text("partial unpromoted writer output\n")
    print("injected " + phase + " failure", file=sys.stderr)
    sys.exit(control["exitCode"])
if phase == "writer":
    suffix = " \n" if control.get("trailingWhitespace") else "\n"
    (root / "gradle.lockfile").write_text("example:library:1.0=runtimeClasspath" + suffix)
    if "writeMetadata" in control:
        (root / "gradle/verification-metadata.xml").write_text(control["writeMetadata"])
    if control.get("moveBaseRef"):
        subprocess.run(["git", "-C", str(root), "update-ref", "refs/heads/reviewed-base",
                        control["moveBaseRef"]], check=True)
elif phase == "metadata":
    sys.exit(subprocess.run(["bash", str(root / "scripts/check-dependency-state-real.sh")]).returncode)
elif phase == "curator":
    assert len(args) == 1 and args[0] == os.environ["EXPECTED_BASE"]
    old = subprocess.check_output(["git", "-C", str(root), "show", args[0] + ":gradle/verification-metadata.xml"])
    if old == (root / "gradle/verification-metadata.xml").read_bytes():
        print("no new verified artifacts (curator phase stub)", file=sys.stderr)
        sys.exit(31)
if control.get("moveSourcePhase") == phase:
    subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-qm", "injected source change"], check=True)
'''


def xml(versions=("1.0",)):
    entries = ""
    for index, version in enumerate(versions):
        checksum = ("a" if index == 0 else "b") * 64
        entries += f'''      <component group="example" name="library" version="{version}">
         <artifact name="library-{version}.jar">
            <sha256 value="{checksum}" origin="Synthetic fixture"/>
         </artifact>
      </component>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<verification-metadata xmlns="{NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="{NS} {NS}/dependency-verification-1.4.xsd">
   <configuration>
      <verify-metadata>true</verify-metadata>
      <verify-signatures>false</verify-signatures>
   </configuration>
   <components>
{entries}   </components>
</verification-metadata>
'''


class PrepareDependencyUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-prepare-test.")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name).resolve()
        self.root = self.work / "source"
        for name in ("scripts", "gradle/wrapper", "library/p2p-core"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        for name in ("home", "tmp"):
            (self.work / name).mkdir()
        self.environment = dict(os.environ, HOME=str(self.work / "home"), GIT_CONFIG_NOSYSTEM="1",
                                GIT_CONFIG_GLOBAL=os.devnull, P2PKIT_PYTHON3=sys.executable,
                                PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(self.work / "tmp"),
                                FIXTURE=str(self.root), CONTROL=str(self.work / "control.json"),
                                TRACE=str(self.work / "trace.jsonl"))
        for key in list(self.environment):
            if key.startswith("GIT_") and key not in ("GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL"):
                del self.environment[key]
        self.environment.pop("P2PKIT_ROOT_OVERRIDE", None)
        # An explicit test-only preimage input permits retained red/green proof;
        # production execution has no root/script substitution mechanism.
        caller = Path(os.environ.get("P2PKIT_TEST_PREPARE_CALLER", ROOT / "scripts/prepare-dependency-update.sh"))
        shutil.copy2(caller, self.root / "scripts/prepare-dependency-update.sh")
        shutil.copy2(ROOT / "scripts/classify-dependency-provenance.py", self.root / "scripts")
        shutil.copy2(ROOT / "scripts/check-dependency-verification.sh",
                     self.root / "scripts/check-dependency-state-real.sh")
        for name in ("gradlew", "scripts/check-gradle-wrapper.sh", "scripts/check-dependency-verification.sh",
                     "scripts/review-dependency-verification.sh"):
            path = self.root / name
            path.write_text("#!" + sys.executable + "\n" + STUB)
            path.chmod(0o755)
        self.metadata = self.root / "gradle/verification-metadata.xml"
        self.metadata.write_text(xml())
        for name, content in {
            "gradle/plugin-provenance-policy.txt": "# No unsigned synthetic exceptions\n",
            "gradle/libs.versions.toml": '[versions]\nfixture = "1.0"\n',
            "gradle/wrapper/gradle-wrapper.properties": "synthetic-wrapper-policy\n",
            "buildscript-gradle.lockfile": "example:plugin:1.0=classpath\n",
            "settings-gradle.lockfile": "example:settings:1.0=classpath\n",
            "gradle.lockfile": "example:removed:1.0=runtimeClasspath\n",
            "library/p2p-core/gradle.lockfile": "example:library:1.0=runtimeClasspath\n",
            "build.gradle.kts": "buildscript {\n resolutionStrategy.activateDependencyLocking()\n}\n",
        }.items():
            (self.root / name).write_text(content)
        self.git("init", "-q")
        for key, value in (("user.name", "P2pKit Test"), ("user.email", "test@p2pkit.invalid"),
                           ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull), ("core.autocrlf", "false")):
            self.git("config", key, value)
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], env=self.environment,
                                       stderr=subprocess.PIPE, timeout=10).decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic reviewed baseline")
        self.base = self.git("rev-parse", "HEAD")

    def run_caller(self, control=None, base=None):
        Path(self.environment["CONTROL"]).write_text(json.dumps(control or {}))
        trace = Path(self.environment["TRACE"])
        trace.write_text("")
        environment = dict(self.environment, EXPECTED_BASE=self.base)
        result = subprocess.run(["bash", str(self.root / "scripts/prepare-dependency-update.sh"), base or self.base],
                                env=environment, capture_output=True, text=True, timeout=30)
        self.events = [json.loads(line) for line in trace.read_text().splitlines()]
        self.output = result.stdout + result.stderr
        self.records = [json.loads(line.removeprefix("DEPENDENCY-PROVENANCE "))
                        for line in result.stderr.splitlines() if line.startswith("DEPENDENCY-PROVENANCE ")]
        if os.environ.get("P2PKIT_TEST_EVIDENCE_DIR"):
            directory = Path(os.environ["P2PKIT_TEST_EVIDENCE_DIR"])
            directory.mkdir(parents=True, exist_ok=True)
            record = {"test": self.id(), "baseArgument": base or self.base, "baseCommit": self.base,
                      "exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                      "events": self.events, "control": control or {}, "scope": "HERMETIC_PHASE_STUBS_NOT_GRADLE",
                      "sourceSha256": {name: hashlib.sha256((self.root / "scripts" / name).read_bytes()).hexdigest()
                                       for name in ("prepare-dependency-update.sh", "classify-dependency-provenance.py")}}
            with (directory / (uuid.uuid4().hex + ".json")).open("x") as output:
                json.dump(record, output, indent=2)
                output.write("\n")
        return result

    def assert_phases(self, *expected):
        self.assertEqual(list(expected), [event["phase"] for event in self.events], self.output)

    def test_unchanged_metadata_lock_refresh(self):
        result = self.run_caller()
        self.assertEqual(0, result.returncode, self.output)
        self.assert_phases("wrapper", "writer", "metadata", "strict")
        self.assertIn("provenance=REUSE", result.stdout)
        self.assertIn("no fresh remote artifact review", result.stdout)
        self.assertEqual(1, len(self.records))
        record = self.records[0]
        self.assertEqual(self.base, record["baseCommit"])
        self.assertEqual(self.base, record["sourceCommit"])
        self.assertEqual(1, record["artifactCount"])
        self.assertEqual(0, record["addedArtifactCount"])
        self.assertEqual(record["baseMetadataSha256"], record["candidateMetadataSha256"])
        self.assertFalse(record["freshRemoteArtifactReview"])
        self.assertEqual(["gradle.lockfile"], [item["path"] for item in record["projectLockChanges"]])

    def test_earlier_failures_keep_original_status_and_stop_later_phases(self):
        phases = ["wrapper", "writer", "metadata", "strict"]
        for index, phase in enumerate(phases):
            with self.subTest(phase=phase):
                result = self.run_caller({"failPhase": phase, "exitCode": 17 + index})
                self.assertEqual(17 + index, result.returncode, self.output)
                self.assert_phases(*phases[:index + 1])
                self.assertNotIn("RESULT: PASS — complete dependency", result.stdout)
                self.assertEqual([], self.records)
                if phase == "writer":
                    self.assertEqual("partial unpromoted writer output\n", (self.root / "gradle.lockfile").read_text())
                    self.assertEqual(xml(), self.metadata.read_text())

    def test_unavailable_and_unrelated_bases_fail_before_writer(self):
        unrelated = self.git("commit-tree", "HEAD^{tree}", "-m", "unrelated synthetic root")
        for base in ("f" * 40, "--not-a-ref", unrelated):
            with self.subTest(base=base):
                result = self.run_caller(base=base)
                self.assertNotEqual(0, result.returncode)
                self.assert_phases()

    def test_base_without_metadata_cannot_reuse_a_writer_replacement(self):
        self.metadata.unlink()
        self.commit()
        result = self.run_caller({"writeMetadata": xml()})
        self.assertNotEqual(0, result.returncode)
        self.assertIn("base metadata is missing", self.output)
        self.assert_phases("wrapper", "writer", "metadata", "strict")

    def test_identical_malformed_xml_is_not_validated_by_empty_diff(self):
        self.metadata.write_text(xml().replace("</verification-metadata>", ""))
        self.commit()
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("classification failed", self.output)
        self.assert_phases("wrapper", "writer", "metadata", "strict")

    def test_empty_and_missing_current_metadata_fail(self):
        for value in ("", xml(())):
            with self.subTest(value=value):
                result = self.run_caller({"writeMetadata": value})
                self.assertNotEqual(0, result.returncode)
                self.assert_phases("wrapper", "writer", "metadata")
        self.metadata.unlink()
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assert_phases("wrapper", "writer", "metadata")

    def test_identical_unsupported_text_and_encoding_are_not_reusable(self):
        candidates = (
            xml().replace("<components>", "<components>unexpected"),
            xml().replace("</artifact>", "</artifact>unexpected"),
            xml().replace('origin="Synthetic fixture"/>', 'origin="Synthetic fixture">unexpected</sha256>'),
            xml().replace('encoding="UTF-8"', 'encoding="ISO-8859-1"'),
        )
        for value in candidates:
            with self.subTest(value=value):
                self.metadata.write_text(value)
                self.commit()
                result = self.run_caller()
                self.assertNotEqual(0, result.returncode)
                self.assertIn("classification failed", self.output)
                self.assert_phases("wrapper", "writer", "metadata", "strict")

    def test_duplicate_identities_foreign_namespace_and_dtd_cannot_pass(self):
        component = xml().split("   <components>\n", 1)[1].split("   </components>", 1)[0]
        artifact = component.split('      <component group="example" name="library" version="1.0">\n', 1)[1]
        artifact = artifact.split("      </component>", 1)[0].replace("a" * 64, "b" * 64)
        candidates = (
            xml().replace("   </components>", component.replace("a" * 64, "b" * 64) + "   </components>"),
            xml().replace("      </component>", artifact + "      </component>"),
            xml().replace(NS, "https://untrusted.invalid/verification"),
            xml().replace("?>", '?><!DOCTYPE verification-metadata [<!ENTITY unexpected "value">]>'),
        )
        for value in candidates:
            with self.subTest(value=value):
                result = self.run_caller({"writeMetadata": value})
                self.assertNotEqual(0, result.returncode)
                self.assertIn("classification failed", self.output)
                self.assert_phases("wrapper", "writer", "metadata", "strict")

    def test_history_removal_and_existing_hash_changes_fail(self):
        self.metadata.write_text(xml(("1.0", "1.1")))
        self.commit()
        for value in (xml(), xml(("1.0", "1.1")).replace("a" * 64, "c" * 64)):
            with self.subTest(value=value):
                result = self.run_caller({"writeMetadata": value})
                self.assertNotEqual(0, result.returncode)
                self.assertIn("removed verified history or changed an existing SHA-256", self.output)
                self.assert_phases("wrapper", "writer", "metadata", "strict")

    def test_changed_trust_configuration_fails(self):
        result = self.run_caller({"writeMetadata": xml().replace("<verify-signatures>false", "<verify-signatures>true")})
        self.assertNotEqual(0, result.returncode)
        self.assert_phases("wrapper", "writer", "metadata")

    def test_tool_policy_source_and_untracked_changes_prevent_reuse(self):
        for name in ("gradle/plugin-provenance-policy.txt", "gradle/libs.versions.toml",
                     "gradle/wrapper/gradle-wrapper.properties", "buildscript-gradle.lockfile",
                     "settings-gradle.lockfile", "build.gradle.kts"):
            with self.subTest(path=name):
                path = self.root / name
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b"# unreviewed change\n")
                    result = self.run_caller()
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("non-project-lock input changes: " + name, self.output)
                    self.assert_phases("wrapper", "writer", "metadata", "strict")
                finally:
                    path.write_bytes(original)
        (self.root / "new-input.txt").write_text("unreviewed input\n")
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("untracked inputs", self.output)

    def test_project_lock_deletion_addition_and_type_change_do_not_reuse(self):
        path = self.root / "library/p2p-core/gradle.lockfile"
        original = path.read_bytes()
        path.unlink()
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("non-project-lock input changes", self.output)
        path.write_bytes(original)
        added = self.root / "library/new/gradle.lockfile"
        added.parent.mkdir()
        added.write_bytes(original)
        self.git("add", "library/new")
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("non-project-lock input changes", self.output)
        self.git("rm", "--cached", "library/new/gradle.lockfile")
        added.unlink()
        target = self.work / "unrelated-sentinel"
        target.write_bytes(original)
        path.unlink()
        path.symlink_to(target)
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("non-project-lock input changes", self.output)
        self.assertEqual(original, target.read_bytes())

    def test_staged_policy_change_prevents_reuse(self):
        path = self.root / "gradle/plugin-provenance-policy.txt"
        original = path.read_text()
        path.write_text(original + "# changed policy\n")
        self.git("add", "gradle/plugin-provenance-policy.txt")
        path.write_text(original)
        self.assertEqual("", self.git("diff", "--name-only", self.base))
        self.assertIn("gradle/plugin-provenance-policy.txt", self.git("diff", "--cached", "--name-only", self.base))
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("non-project-lock input changes: gradle/plugin-provenance-policy.txt", self.output)

    def test_assume_unchanged_cannot_hide_changed_policy_bytes(self):
        name = "gradle/plugin-provenance-policy.txt"
        self.git("update-index", "--assume-unchanged", name)
        path = self.root / name
        path.write_text(path.read_text() + "# actual bytes changed\n")
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("non-project-lock input bytes differ from base: " + name, self.output)

    def test_staged_lock_mode_change_cannot_hide_behind_regular_worktree(self):
        self.git("update-index", "--chmod=+x", "gradle.lockfile")
        result = self.run_caller()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("index mode/type", self.output)

    def test_nonidentical_metadata_with_no_new_artifacts_does_not_reuse(self):
        result = self.run_caller({"writeMetadata": xml() + "<!-- descriptive-only change -->\n"})
        self.assertNotEqual(0, result.returncode)
        self.assertIn("nonidentical metadata without added artifacts", self.output)
        self.assert_phases("wrapper", "writer", "metadata", "strict")

    def test_added_artifacts_reach_curator_and_its_failure_is_not_reuse(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                control = {"writeMetadata": xml(("1.0", "1.1"))}
                if failure:
                    control.update(failPhase="curator", exitCode=37)
                result = self.run_caller(control)
                self.assertEqual(37 if failure else 0, result.returncode, self.output)
                self.assert_phases("wrapper", "writer", "metadata", "strict", "curator")
                self.assertEqual("REVIEW", self.records[0]["mode"])
                self.assertNotIn("provenance=REUSE", result.stdout)
                if failure:
                    self.assertNotIn("RESULT: PASS — complete dependency", result.stdout)

    def test_moving_base_ref_does_not_change_frozen_curator_base(self):
        self.git("branch", "reviewed-base", self.base)
        self.git("commit", "--allow-empty", "-qm", "reviewed source-only change")
        current = self.git("rev-parse", "HEAD")
        result = self.run_caller({"writeMetadata": xml(("1.0", "1.1")), "moveBaseRef": current}, base="reviewed-base")
        self.assertEqual(0, result.returncode, self.output)
        self.assertEqual(self.base, self.events[-1]["args"][0])
        self.assertEqual(current, self.records[0]["sourceCommit"])

    def test_changed_source_during_writer_is_rejected(self):
        for phase in ("writer", "curator"):
            with self.subTest(phase=phase):
                result = self.run_caller({"moveSourcePhase": phase, "writeMetadata": xml(("1.0", "1.1"))})
                self.assertNotEqual(0, result.returncode)
                self.assertIn("source changed during dependency update", self.output)
                expected = ["wrapper", "writer", "metadata", "strict"]
                self.assert_phases(*(expected + ["curator"] if phase == "curator" else expected))
                self.assertNotIn("RESULT: PASS — complete dependency", result.stdout)

    def test_final_whitespace_gate_still_rejects_otherwise_valid_reuse(self):
        result = self.run_caller({"trailingWhitespace": True})
        self.assertNotEqual(0, result.returncode)
        self.assertIn("trailing whitespace", self.output)
        self.assertEqual("REUSE", self.records[0]["mode"])
        self.assertNotIn("RESULT: PASS — complete dependency", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
