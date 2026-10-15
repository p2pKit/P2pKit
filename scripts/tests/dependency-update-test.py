#!/usr/bin/env python3
"""Tiny real Git checkouts + modeled generator; no Gradle/network/private key."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location("dependency_update", Path(__file__).resolve().parents[1] / "dependency_update.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)


def xml(extra=False):
    component = lambda name: ('<component group="org.example" name="' + name + '" version="1">'
                              '<artifact name="' + name + '.jar"><sha256 value="' + 'a' * 64 + '"/></artifact></component>')
    return ('<verification-metadata xmlns="https://schema.gradle.org/dependency-verification">'
            '<configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures></configuration>'
            '<components>' + component('old') + (component('new') if extra else '') + '</components></verification-metadata>').encode()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dependency-update-model-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.controller, self.candidate = self.parent / "controller", self.parent / "candidate"
        self.controller.mkdir()
        self.command(self.controller, "init", "--quiet")
        for name in (*D.HELPERS, D.XML, "gradle.lockfile", "product.txt", ".gitignore"):
            path = self.controller / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(xml() if name == D.XML else b"build/\n" if name == ".gitignore" else b"original\n")
        self.command(self.controller, "add", ".")
        self.command(self.controller, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                     "commit", "--quiet", "-m", "Synthetic initial source")
        self.command(self.parent, "clone", "--quiet", "--no-hardlinks", str(self.controller), str(self.candidate))
        commit = D.git(self.controller, "rev-parse", "HEAD").decode().strip()
        tree = D.git(self.controller, "rev-parse", "HEAD^{tree}").decode().strip()
        self.request = {"controller_sha": commit, "controller_tree": tree, "candidate_sha": commit,
                        "candidate_tree": tree, "dependency_base_sha": commit}
        self.output = self.parent / "public"
        self.calls = []
        self.reports = Mock()

    @staticmethod
    def command(root, *arguments):
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def generator(self, argv, **options):
        self.calls.append((argv, options))
        if argv[-1] != "--stop":
            (self.candidate / D.XML).write_bytes(xml(True))
            (self.candidate / "gradle.lockfile").write_text("new lock\n")
        return Mock(returncode=0)

    def execute(self, **options):
        return D.execute(self.controller, self.candidate, self.request, self.output,
                         run=options.get("run", self.generator), reports=self.reports)

    def test_actual_git_delta_invokes_unchanged_generator_and_is_not_qualification(self):
        result = self.execute()
        self.assertEqual("DEPENDENCY_UPDATE_CANDIDATE_NOT_QUALIFICATION", result["scope"])
        self.assertFalse(result["releaseQualified"])
        self.assertTrue(result["requiresReviewBeforeApply"])
        self.assertEqual(1, result["addedVerifiedArtifacts"])
        self.assertEqual(["gradle.lockfile", D.XML], [row["path"] for row in result["changes"]])
        self.assertEqual([str(self.candidate / "scripts/prepare-dependency-update.sh"), self.request["dependency_base_sha"]], self.calls[0][0])
        self.assertEqual(([str(self.candidate / "gradlew"), "--stop"], 90), (self.calls[1][0], self.calls[1][1]["timeout"]))
        self.assertEqual({"generated-dependencies.patch", "generated-dependencies.json"}, {p.name for p in self.output.iterdir()})
        self.assertEqual(result, json.loads((self.output / "generated-dependencies.json").read_text()))
        self.assertEqual(b"", D.git(self.controller, "status", "--porcelain=v1"))

    def test_stale_source_or_base_never_executes_generator(self):
        for key in self.request:
            with self.subTest(key=key):
                request = {**self.request, key: "0" * 40}
                with self.assertRaises(D.UpdateError):
                    D.execute(self.controller, self.candidate, request, self.output, run=self.generator)
        self.assertFalse(self.calls)

    def test_changed_or_dirty_maintained_helper_refuses(self):
        (self.candidate / D.HELPERS[0]).write_text("changed wrapper")
        with self.assertRaisesRegex(D.UpdateError, "SOURCE_DIRTY"):
            self.execute()
        self.assertFalse(self.calls)

    def test_committed_helper_difference_and_malformed_request_refuse(self):
        for request in (None, [], {**self.request, "extra": "a" * 40}, {**self.request, "candidate_sha": True}):
            with self.subTest(request=request), self.assertRaisesRegex(D.UpdateError, "REQUEST_IDENTITY"):
                D.execute(self.controller, self.candidate, request, self.output, run=self.generator)
        (self.candidate / D.HELPERS[0]).write_text("different committed wrapper")
        self.command(self.candidate, "add", D.HELPERS[0])
        self.command(self.candidate, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                     "commit", "--quiet", "-m", "Different generator")
        self.request.update(candidate_sha=D.git(self.candidate, "rev-parse", "HEAD").decode().strip(),
                            candidate_tree=D.git(self.candidate, "rev-parse", "HEAD^{tree}").decode().strip())
        with self.assertRaisesRegex(D.UpdateError, "MAINTAINED_GENERATOR_CHANGED"):
            self.execute()
        self.assertFalse(self.calls)

    def test_current_public_verification_schema_and_nested_policy_refusal(self):
        _, entries = D.verification((Path(__file__).resolve().parents[2] / D.XML).read_bytes())
        self.assertGreater(len(entries), 0)
        for raw in (xml().replace(b'<components>', b'<components trust="all">'),
                    xml().replace(b'/></artifact>', b'><trusted/></sha256></artifact>'),
                    xml().replace(b'</components>', b'not-checksums</components>')):
            with self.subTest(raw=raw[:30]), self.assertRaises(D.UpdateError):
                D.verification(raw)

    def test_non_dependency_or_untracked_or_staged_changes_refuse(self):
        for change in ("product", "untracked", "staged", "mode", "link"):
            with self.subTest(change=change):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                self.command(self.candidate, "clean", "-fd")
                def altered(argv, **kwargs):
                    result = self.generator(argv, **kwargs)
                    if argv[-1] != "--stop":
                        if change == "product":
                            (self.candidate / "product.txt").write_text("bad change")
                        elif change == "untracked":
                            (self.candidate / "unknown.lockfile").write_text("unapproved new path")
                        elif change == "staged":
                            self.command(self.candidate, "add", "gradle.lockfile")
                        elif change == "mode":
                            (self.candidate / "gradle.lockfile").chmod(0o755)
                        else:
                            path = self.candidate / "gradle.lockfile"
                            path.unlink(); path.symlink_to(self.controller / "gradle.lockfile")
                    return result
                with self.assertRaises(D.UpdateError):
                    self.execute(run=altered)
                self.assertFalse(self.output.exists())

    def test_removed_hash_or_changed_trust_is_not_an_update(self):
        for raw in (xml(True).replace(b'name="old"', b'name="replaced"'),
                    xml(True).replace(b'<verify-metadata>true', b'<verify-metadata>false')):
            with self.subTest(raw=raw[:25]):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                def altered(argv, **kwargs):
                    result = self.generator(argv, **kwargs)
                    if argv[-1] != "--stop":
                        (self.candidate / D.XML).write_bytes(raw)
                    return result
                with self.assertRaises(D.UpdateError):
                    self.execute(run=altered)
                self.assertFalse(self.output.exists())

    def test_generator_failure_and_stop_failure_never_publish_candidate(self):
        for codes in ((9, 0), (0, 7)):
            with self.subTest(codes=codes):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                returns = iter(codes)
                def failed(argv, **kwargs):
                    self.generator(argv, **kwargs)
                    return Mock(returncode=next(returns))
                with self.assertRaisesRegex(D.UpdateError, "GENERATION_OR_GRADLE_STOP_FAILED"):
                    self.execute(run=failed)
                self.assertFalse(self.output.exists())
                self.assertEqual("--stop", self.calls[-1][0][-1])
        self.assertEqual(2, self.reports.call_count)

    def test_spawn_failure_still_attempts_original_gradle_stop(self):
        calls = []
        def failed(argv, **kwargs):
            calls.append(argv)
            if argv[-1] != "--stop":
                raise OSError("modeled spawn failure")
            return Mock(returncode=0)
        with self.assertRaises(OSError):
            self.execute(run=failed)
        self.assertEqual("--stop", calls[-1][-1])
        self.reports.assert_called_once()
        self.assertFalse(self.output.exists())

    def test_immutable_controller_changes_block_output(self):
        def changed(argv, **kwargs):
            result = self.generator(argv, **kwargs)
            (self.controller / "product.txt").write_text("changed controller")
            return result
        with self.assertRaisesRegex(D.UpdateError, "SOURCE_DIRTY"):
            self.execute(run=changed)
        self.assertFalse(self.output.exists())

    def test_existing_internal_and_linked_outputs_refuse_before_execution(self):
        existing = self.parent / "existing"
        existing.mkdir()
        linked = self.parent / "link"
        linked.symlink_to(self.controller, target_is_directory=True)
        for output in (existing, self.controller / "output", self.candidate / "output", linked / "output"):
            with self.subTest(output=output), self.assertRaises(D.UpdateError):
                D.execute(self.controller, self.candidate, self.request, output, run=self.generator)
        self.assertFalse(self.calls)

    def test_xml_dtd_duplicate_and_weak_checksums_refuse(self):
        for raw in (b'<!DOCTYPE verification-metadata []>' + xml(), xml().replace(b"sha256", b"sha1"),
                    xml().replace(b'</components>', xml().split(b'<components>')[1].split(b'</components>')[0] + b'</components>')):
            with self.subTest(raw=raw[:20]), self.assertRaises(D.UpdateError):
                D.verification(raw)


if __name__ == "__main__":
    unittest.main(failfast=True)
