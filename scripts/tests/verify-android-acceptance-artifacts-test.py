#!/usr/bin/env python3
"""Pure map/receipt and small file-fixture controls; no Gradle/SDK/APK execution."""

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("android_artifacts", SCRIPTS / "verify-android-acceptance-artifacts.py")
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)
CHECKER = subject.load_tool("check-audit-receipt.py")


def description(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def fixture():
    result = {"schemaVersion": 1, "taskPath": subject.TASK, "variantName": "debug", "components": {}}
    for role in ("app", "test"):
        variant = "debug" if role == "app" else "debugAndroidTest"
        package = subject.PACKAGE + (".test" if role == "test" else "")
        directory = subject.MODULE_BUILD + "/fixture/" + role
        result["components"][role] = {
            "componentKind": "APPLICATION" if role == "app" else "ANDROID_TEST",
            "applicationId": package, "variantName": variant,
            "manifest": {"sourcePath": directory + "/AndroidManifest.xml",
                         "retainedPath": subject.REPORT_DIRECTORY + "/" + role + "-merged-AndroidManifest.xml",
                         "producerTasks": [":p2p-sample-android:fixture" + role.title() + "Manifest"],
                         **description(("fixture-" + role + "-manifest").encode())},
            "apk": {"providerPath": directory, "path": directory + "/fixture.apk", "outputType": "SINGLE",
                    "filters": [], "producerTasks": [":p2p-sample-android:fixture" + role.title() + "Apk"],
                    **description(("fixture-" + role + "-apk").encode())},
            "metadataProjection": {"kind": "AGP_BUILT_ARTIFACTS_API_PROJECTION", "artifactType": "APK",
                                   "applicationId": package, "variantName": variant, "elementCount": 1,
                                   "versionCode": 1, "versionName": "fixture"}}
    return result


class ArtifactMapTests(unittest.TestCase):
    def test_exact_structural_map_only(self):
        value = fixture()
        self.assertIs(subject.validate_map(value), value)
        # The test component name is actual producer data, not a guessed task name.
        value["components"]["test"]["variantName"] = "actualTestComponent"
        value["components"]["test"]["metadataProjection"]["variantName"] = "actualTestComponent"
        self.assertIs(subject.validate_map(value), value)
        for version in (None, "", "x" * 4096, "\U0001f600" * 2048):
            value["components"]["test"]["metadataProjection"]["versionName"] = version
            self.assertIs(subject.validate_map(value), value)

    def test_root_and_component_identity_fail_closed(self):
        for location, field, invalid in (
                ((), "schemaVersion", True), ((), "taskPath", ":unrelated"), ((), "variantName", "release"),
                (("components", "app"), "componentKind", "ANDROID_TEST"),
                (("components", "test"), "applicationId", subject.PACKAGE),
                (("components", "app"), "variantName", "release"),
                (("components", "test"), "variantName", "")):
            value = fixture()
            target = value
            for part in location:
                target = target[part]
            target[field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                subject.validate_map(value)
        for key in ("missing", "unexpected"):
            value = fixture()
            if key == "missing":
                del value["components"]["test"]
            else:
                value["components"][key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError):
                subject.validate_map(value)

    def test_all_nested_shapes_are_exact(self):
        for path in ((), ("components", "app"), ("components", "test", "manifest"),
                     ("components", "app", "apk"), ("components", "test", "metadataProjection")):
            for operation in ("missing", "extra"):
                value = fixture()
                target = value
                for part in path:
                    target = target[part]
                if operation == "missing":
                    del target[next(iter(target))]
                else:
                    target["unexpected"] = "unqualified"
                with self.subTest(path=path, operation=operation), self.assertRaises(ValueError):
                    subject.validate_map(value)

    def test_paths_are_owned_canonical_and_distinct(self):
        for invalid in ("/tmp/x", "../x", subject.MODULE_BUILD + "/../x", subject.MODULE_BUILD + "//x",
                        subject.MODULE_BUILD + "/./x", subject.MODULE_BUILD + "/x\\y", "library/p2p-core/build/x",
                        subject.MODULE_BUILD + "/x\0y", subject.MODULE_BUILD + "/x\ny", subject.MODULE_BUILD, 5):
            with self.subTest(path=invalid), self.assertRaises(ValueError):
                subject.relative_build_path(invalid)
        for field in ("sourcePath", "retainedPath"):
            value = fixture()
            value["components"]["app"]["manifest"][field] = value["components"]["test"]["manifest"][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                subject.validate_map(value)
        value = fixture()
        manifest = value["components"]["app"]["manifest"]
        manifest["sourcePath"] = manifest["retainedPath"]
        with self.assertRaises(ValueError):
            subject.validate_map(value)

    def test_output_metadata_and_provider_must_match(self):
        cases = (("apk", "providerPath", subject.MODULE_BUILD + "/wrong"), ("apk", "outputType", "UNIVERSAL"),
                 ("apk", "filters", ["arm64"]), ("apk", "filters", ()),
                 ("metadataProjection", "kind", "ORIGINAL_METADATA"), ("metadataProjection", "artifactType", "AAR"),
                 ("metadataProjection", "applicationId", "wrong.package"),
                 ("metadataProjection", "variantName", "wrongVariant"),
                 ("metadataProjection", "elementCount", True), ("metadataProjection", "elementCount", 2),
                 ("metadataProjection", "versionCode", True), ("metadataProjection", "versionCode", -1),
                 ("metadataProjection", "versionCode", 2147483648),
                 ("metadataProjection", "versionName", "x\ny"),
                 ("metadataProjection", "versionName", "x" * 4097),
                 ("metadataProjection", "versionName", "\U0001f600" * 2049))
        for location, field, invalid in cases:
            value = fixture()
            value["components"]["app"][location][field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                subject.validate_map(value)

    def test_content_bounds_and_provider_tasks(self):
        for role in ("app", "test"):
            for kind, limit in (("manifest", subject.MANIFEST_LIMIT), ("apk", subject.APK_LIMIT)):
                for field, invalid in (("bytes", True), ("bytes", 0), ("bytes", limit + 1), ("sha256", "A" * 64),
                                       ("producerTasks", []), ("producerTasks", ["relative"]),
                                       ("producerTasks", [subject.TASK]), ("producerTasks", [":z", ":a"]),
                                       ("producerTasks", [":a", ":a"])):
                    value = fixture()
                    value["components"][role][kind][field] = invalid
                    with self.subTest(role=role, kind=kind, field=field), self.assertRaises(ValueError):
                        subject.validate_map(value)


class FileAndReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="android-artifact-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_small_regular_file_bytes_and_streaming_hash(self):
        relative = subject.MODULE_BUILD + "/fixture/input"
        path = self.root / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(b"fixture")
        expected = description(b"fixture")
        self.assertEqual(subject.fingerprint(path, 7), (expected, None))
        self.assertEqual(subject.verified_file(self.root, relative, expected, 7, True), b"fixture")
        with self.assertRaises(ValueError):
            subject.fingerprint(path, 6)
        with self.assertRaises(ValueError):
            subject.verified_file(self.root, relative, description(b"changed"), 8)
        path.write_bytes(b"")
        with self.assertRaises(ValueError):
            subject.fingerprint(path, 7)

    def test_links_and_nonregular_files_are_not_outputs(self):
        directory = self.root / "physical"
        directory.mkdir()
        file = directory / "file"
        file.write_bytes(b"fixture")
        link = self.root / "link"
        link.symlink_to(directory, target_is_directory=True)
        direct_link = self.root / "file-link"
        direct_link.symlink_to(file)
        for path in (directory, link / "file", direct_link):
            with self.subTest(path=path), self.assertRaises(ValueError):
                subject.fingerprint(path, 7)

    def receipt(self):
        source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
        context = {"id": "c" * 32, "host": "macos-arm64", "gradleHome": str(self.root / "home"),
                   "source": source, "preexistingOutputPaths": []}
        receipt = {"schema": 1, "id": "d" * 32, "purpose": "fixture-build", "kind": "gradle",
                   "requestedArgv": list(subject.BUILD_ARGUMENTS), "cwd": str(self.root),
                   "wrapper": str(self.root / ("gradlew.bat" if subject.os.name == "nt" else "gradlew")),
                   "productExitCode": 0, "finalExitCode": 0,
                   "stopExitCode": 0, "sourceBefore": source, "sourceAfter": source, "sourceUnchanged": True,
                   "errors": [], "ownedSurvivors": [], "jobId": context["id"], "host": context["host"],
                   "gradleHome": context["gradleHome"]}
        return receipt, context

    def test_receipt_identity_and_complete_request(self):
        receipt, context = self.receipt()
        subject.admit_build_receipt(CHECKER, receipt, copy.deepcopy(receipt), context, self.root, "fixture-build")
        receipt["requestedArgv"].append("--console=plain")
        subject.admit_build_receipt(CHECKER, receipt, copy.deepcopy(receipt), context, self.root, "fixture-build")
        for key, invalid in (("kind", "command"), ("jobId", "e" * 32), ("host", "linux-x64"),
                             ("gradleHome", str(self.root / "other-home")), ("productExitCode", 1),
                             ("stopExitCode", 1), ("ownedSurvivors", [{"unknown": True}]),
                             ("requestedArgv", subject.BUILD_ARGUMENTS[:-1]), ("id", "../escape")):
            receipt, context = self.receipt()
            receipt[key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                subject.admit_build_receipt(
                    CHECKER, receipt, copy.deepcopy(receipt), context, self.root, "fixture-build")
        receipt, context = self.receipt()
        context["preexistingOutputPaths"] = [str(self.root / subject.MODULE_BUILD)]
        with self.assertRaises(ValueError):
            subject.admit_build_receipt(CHECKER, receipt, copy.deepcopy(receipt), context, self.root, "fixture-build")
        receipt, context = self.receipt()
        different = copy.deepcopy(receipt)
        different["extra"] = True
        with self.assertRaises(ValueError):
            subject.admit_build_receipt(CHECKER, receipt, different, context, self.root, "fixture-build")

    def test_retention_requires_one_new_hash_bound_canonical_copy(self):
        state, invocation = self.root / "state", "a" * 32
        relative = subject.MAP_PATH
        retained = "reports/" + relative
        path = state / "evidence" / invocation / retained
        path.parent.mkdir(parents=True)
        path.write_bytes(b"fixture-report")
        row = {"source": relative, "classification": "changed-since-admission", "retained": retained,
               **description(b"fixture-report")}
        receipt = {"id": invocation, "reports": [row]}
        self.assertEqual(subject.retained_report(state, receipt, relative, 100), b"fixture-report")
        for rows in ([], [row, row], [{**row, "classification": "preexisting-unchanged"}],
                     [{**row, "retained": "../escape"}], [{**row, "sha256": "0" * 64}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                subject.retained_report(state, {"id": invocation, "reports": rows}, relative, 100)


if __name__ == "__main__":
    unittest.main()
