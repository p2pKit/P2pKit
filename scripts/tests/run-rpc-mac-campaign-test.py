#!/usr/bin/env python3
"""Offline Mac preparation controls; never signed-installation or physical-device evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mac_campaign_test", ROOT / "scripts/run-rpc-mac-campaign.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Preparation(unittest.TestCase):
    def test_apk_identity_rejects_canonical_foreign_duplicate_or_non_debuggable_products(self):
        good = b"package: name='dev.p2pkit.sample.android.rpclab' versionCode='1'\napplication-debuggable\n"
        m.verify_android_campaign_identity(good)
        for wrong in (good.replace(b'.rpclab', b''), good.replace(b'.rpclab', b'.other'),
                      good.replace(b'application-debuggable\n', b''), good + good,
                      good + b'application-debuggable\n', b'', b'\xff', None):
            with self.subTest(raw=wrong), self.assertRaises((ValueError, UnicodeDecodeError)):
                m.verify_android_campaign_identity(wrong)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = dict(commit="1" * 40, tree="2" * 40, status="", diffSha256="3" * 64)

    def file(self, relative, content=b"OFFLINE_CONTROL_NOT_AN_APPLICATION"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o600)
        return path

    def manifest(self):
        apk = self.file("samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk")
        driver = self.file("samples/p2p-sample-rpc/build/capacity-lab/manifest.json")
        return dict(schema=1, scope=m.SCOPE, source=self.source, iosApp=None,
                    artifacts={"android-apk": m.artifact(apk), "jvm-manifest": m.artifact(driver)})

    def wrapper_cache(self, checksum=None, url="https\\://services.gradle.org/distributions/gradle-9.7.0-bin.zip"):
        for helper in ("run-rpc-capacity-lab.py", "run-audit-command.py"):
            self.file("scripts/" + helper, (ROOT / "scripts" / helper).read_bytes())
        data = b"OFFLINE_SYNTHETIC_ARCHIVE; THE_REAL_WRAPPER_MUST_VALIDATE_ZIP_FORMAT"
        archive = self.file("tool-cache/gradle-distribution.zip", data)
        archive.parent.chmod(0o700)
        checksum = checksum or hashlib.sha256(data).hexdigest()
        self.file("gradle/wrapper/gradle-wrapper.properties", (
            "distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\n" +
            "zipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n" +
            "validateDistributionUrl=true\ndistributionUrl=" + url + "\ndistributionSha256Sum=" + checksum + "\n"
        ).encode())
        return archive

    def test_wrapper_archive_cache_keeps_original_verification_without_completion_markers(self):
        archive = self.wrapper_cache()
        state = self.root / "state"
        state.mkdir(mode=0o700)
        (state / "private").mkdir(mode=0o700)
        with patch.object(m, "ROOT", self.root):
            m.stage_pinned_wrapper_archive(state)
        copies = list((state / "gradle-home").rglob("*.zip"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), archive.read_bytes())
        self.assertEqual(list(state.rglob("*.ok")), [])
        proof = m.private_json(state / "private/wrapper-cache.json")
        self.assertTrue(proof["wrapperVerificationRequired"])
        self.assertFalse(proof["completionMarkerCreated"])
        with patch.object(m, "ROOT", self.root), self.assertRaises(FileExistsError):
            m.stage_pinned_wrapper_archive(state)

    def test_wrapper_cache_checksum_failure_retains_input_and_stages_nothing(self):
        archive = self.wrapper_cache(checksum="f" * 64)
        before = archive.read_bytes()
        with patch.object(m, "ROOT", self.root), self.assertRaises(ValueError):
            m.stage_pinned_wrapper_archive(self.root / "state")
        self.assertEqual(archive.read_bytes(), before)
        self.assertFalse((self.root / "state").exists())

    def test_wrapper_cache_refuses_linked_archive_and_unsupported_distribution_origin(self):
        archive = self.wrapper_cache(url="https\\://unapproved.invalid/gradle-9.7.0-bin.zip")
        with patch.object(m, "ROOT", self.root), self.assertRaises(ValueError):
            m.stage_pinned_wrapper_archive(self.root / "state")
        self.wrapper_cache()
        original = archive.with_suffix(".original")
        archive.rename(original)
        archive.symlink_to(original)
        with patch.object(m, "ROOT", self.root), self.assertRaises(ValueError):
            m.stage_pinned_wrapper_archive(self.root / "state")

    def test_absent_wrapper_archive_retains_normal_bootstrap_path(self):
        with patch.object(m, "ROOT", self.root):
            m.stage_pinned_wrapper_archive(self.root / "state")
        self.assertFalse((self.root / "state").exists())

    def dependency_cache(self, data=b"OFFLINE_EXTERNAL_DEPENDENCY_NOT_REAL_BYTECODE"):
        for helper in ("run-rpc-capacity-lab.py", "run-audit-command.py", "check-audit-receipt.py"):
            self.file("scripts/" + helper, (ROOT / "scripts" / helper).read_bytes())
        slot = format(int(hashlib.sha1(data).hexdigest(), 16), "x")
        cache = self.root / "tool-cache/gradle-ro-dependencies"
        relative = "files-2.1/test.vendor/example/1/" + slot + "/example-1.jar"
        dependency = self.file("tool-cache/gradle-ro-dependencies/modules-2/" + relative, data)
        metadata = self.file("tool-cache/gradle-ro-dependencies/modules-2/metadata-2.107/module-metadata.bin",
                             b"OFFLINE_OPAQUE_METADATA_NOT_GRADLE_EXECUTION_EVIDENCE")
        for path in (cache, cache / "modules-2"):
            path.chmod(0o700)
        for path in (dependency, metadata):
            path.chmod(0o400)
        policies = {}
        xml = ('<verification-metadata xmlns="https://schema.gradle.org/dependency-verification"><components>'
               '<component group="test.vendor" name="example" version="1"><artifact name="example-1.jar">'
               '<sha256 value="' + hashlib.sha256(data).hexdigest() + '"/></artifact></component>'
               '</components></verification-metadata>')
        for name, raw in (("gradle/verification-metadata.xml", xml.encode()),
                          ("gradle/plugin-provenance-policy.txt", b"OFFLINE_POLICY"),
                          ("gradle/wrapper/gradle-wrapper.properties", b"OFFLINE_WRAPPER_POLICY")):
            policies[name] = m.artifact(self.file(name, raw))["sha256"]
        source = self.source | dict(status="", diffSha256=hashlib.sha256(b"").hexdigest())
        proof = dict(schema=1, id="offline", purpose="prepare-products", kind="gradle", cwd=str(self.root),
                     wrapper=str(self.root / "gradlew"), requestedArgv=["OFFLINE_NOT_A_BUILD"],
                     productExitCode=0, finalExitCode=0, stopExitCode=0, errors=[], ownedSurvivors=[],
                     sourceUnchanged=True, sourceBefore=source, sourceAfter=source)
        producer = self.file("s-old/commands/prepare-products-aabbccdd.json", json.dumps(proof).encode())
        producer.parent.chmod(0o700)
        manifest = dict(schema=1, scope="SEALED_LOCAL_EXTERNAL_DEPENDENCIES_NOT_CAMPAIGN_PRODUCTS", policies=policies,
                        producerReceipt=m.artifact(producer), artifacts={relative: m.artifact(dependency),
                        "metadata-2.107/module-metadata.bin": m.artifact(metadata)})
        self.file("tool-cache/gradle-ro-dependencies/manifest.json", json.dumps(manifest).encode())
        return cache, dependency, producer, manifest

    def cache_git(self, argv, **kwargs):
        return (self.root / argv[2].split(":", 1)[1]).read_bytes()

    def validate_cache(self):
        with patch.object(m, "ROOT", self.root), patch.object(m.subprocess, "run"), \
                patch.object(m.subprocess, "check_output", side_effect=self.cache_git):
            return m.read_only_dependency_cache(self.root / "state")

    def test_absent_dependency_cache_keeps_normal_resolution(self):
        self.assertIsNone(self.validate_cache())

    def test_sealed_external_cache_has_a_separate_manifest_binding(self):
        cache, _, _, _ = self.dependency_cache()
        selected = self.validate_cache()
        self.assertEqual(selected["path"], str(cache))
        self.assertEqual(selected["manifest"], m.artifact(cache / "manifest.json"))

    def test_gradle_slot_omits_leading_zeroes_without_relaxing_integrity(self):
        data = next(str(n).encode() for n in range(1000) if hashlib.sha1(str(n).encode()).hexdigest().startswith("0"))
        _, dependency, _, _ = self.dependency_cache(data)
        self.assertLess(len(dependency.parent.name), 40)
        self.assertIsNotNone(self.validate_cache())

    def test_failed_native_producer_cannot_seed_a_qualified_cache(self):
        cache, _, producer, manifest = self.dependency_cache()
        proof = json.loads(producer.read_text())
        proof.update(productExitCode=1, finalExitCode=1)
        producer.write_text(json.dumps(proof))
        manifest["producerReceipt"] = m.artifact(producer)
        (cache / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.validate_cache()

    def test_cache_requires_current_policy_and_original_source_pins(self):
        cache, dependency, _, manifest = self.dependency_cache()
        original = dependency.read_bytes()
        dependency.chmod(0o600)
        dependency.write_bytes(b"UNPINNED_REPLACEMENT")
        dependency.chmod(0o400)
        relative = dependency.relative_to(cache / "modules-2").as_posix()
        manifest["artifacts"][relative] = m.artifact(dependency)
        (cache / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.validate_cache()
        dependency.chmod(0o600)
        dependency.write_bytes(original)
        dependency.chmod(0o400)
        manifest["artifacts"][relative] = m.artifact(dependency)
        manifest["policies"]["gradle/verification-metadata.xml"] = "f" * 64
        (cache / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.validate_cache()

    def test_cache_rejects_writable_and_additional_inputs(self):
        cache, dependency, _, _ = self.dependency_cache()
        dependency.chmod(0o600)
        with self.assertRaises(ValueError):
            self.validate_cache()
        dependency.chmod(0o400)
        extra = self.file("tool-cache/gradle-ro-dependencies/modules-2/extra.bin")
        extra.chmod(0o400)
        with self.assertRaises(ValueError):
            self.validate_cache()

    def test_cache_rejects_an_invented_gradle_content_slot(self):
        cache, dependency, _, manifest = self.dependency_cache()
        relative = dependency.relative_to(cache / "modules-2").as_posix()
        moved = dependency.parent.parent / ("0" * 40) / dependency.name
        moved.parent.mkdir()
        dependency.rename(moved)
        manifest["artifacts"].pop(relative)
        manifest["artifacts"][moved.relative_to(cache / "modules-2").as_posix()] = m.artifact(moved)
        (cache / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.validate_cache()

    def test_cache_cannot_admit_a_link_even_with_an_inventory_entry(self):
        _, dependency, _, _ = self.dependency_cache()
        original = dependency.with_suffix(".original")
        dependency.rename(original)
        dependency.symlink_to(original)
        with self.assertRaises(ValueError):
            self.validate_cache()

    def test_p2pkit_products_cannot_enter_the_external_cache(self):
        cache, dependency, _, manifest = self.dependency_cache()
        files = cache / "modules-2/files-2.1"
        (files / "test.vendor").rename(files / "dev.p2pkit")
        moved = files / "dev.p2pkit" / dependency.relative_to(files / "test.vendor")
        relative = dependency.relative_to(cache / "modules-2").as_posix()
        manifest["artifacts"].pop(relative)
        manifest["artifacts"][moved.relative_to(cache / "modules-2").as_posix()] = m.artifact(moved)
        xml = self.root / "gradle/verification-metadata.xml"
        xml.write_text(xml.read_text().replace("test.vendor", "dev.p2pkit"))
        manifest["policies"]["gradle/verification-metadata.xml"] = m.artifact(xml)["sha256"]
        (cache / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.validate_cache()

    def test_hash_binds_actual_owned_file_and_detects_mutation(self):
        path = self.file("owned.bin")
        row = m.artifact(path)
        self.assertEqual(row["bytes"], path.stat().st_size)
        path.write_bytes(b"CHANGED")
        self.assertNotEqual(row, m.artifact(path))

    def test_links_hardlinks_fifo_and_writable_artifacts_are_not_admitted(self):
        target = self.file("target")
        link = self.root / "link"
        link.symlink_to(target)
        with self.assertRaises((ValueError, RuntimeError)):
            m.artifact(link)
        shared = self.root / "shared"
        os.link(target, shared)
        with self.assertRaises(ValueError):
            m.artifact(target)
        shared.unlink()
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            m.artifact(fifo)
        target.chmod(0o666)
        with self.assertRaises(ValueError):
            m.artifact(target)

    def test_manifest_rejects_stale_source_missing_wrong_producer_and_changed_bytes(self):
        good = self.manifest()
        with patch.object(m, "ROOT", self.root):
            self.assertIs(m.verify_manifest(good, self.source), good)
            for change in (dict(schema=True), dict(scope="QUALIFIED"), dict(source=self.source | {"commit": "4" * 40}),
                           dict(artifacts={}), dict(iosApp="/UNTESTED/APP")):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    m.verify_manifest(good | change, self.source)
            wrong = copy.deepcopy(good)
            wrong["artifacts"]["android-apk"] = m.artifact(self.file("other.apk"))
            with self.assertRaises(ValueError):
                m.verify_manifest(wrong, self.source)
            Path(good["artifacts"]["android-apk"]["path"]).write_bytes(b"CHANGED")
            with self.assertRaises(ValueError):
                m.verify_manifest(good, self.source)

    def test_template_has_exact_hashes_and_invalid_network_placeholders_for_each_profile(self):
        manifest = self.manifest()
        for count in (128, 256):
            values = m.protocol.parse(m.settings_template(manifest, "android", count, Path("/SELECTED/adb")))
            self.assertEqual(values["clientCount"], str(count))
            self.assertEqual(values["hostArtifactSha256"], manifest["artifacts"]["android-apk"]["sha256"])
            self.assertEqual(values["sourceSha"], self.source["commit"])
            self.assertEqual(values["schema"], "2")
            self.assertEqual(values["localAddress"], "SELECT_MAC_LAN_ADDRESS")
        for count in (True, 127, 255, 257, 512):
            with self.assertRaises(ValueError):
                m.settings_template(manifest, "android", count, Path("/SELECTED/adb"))
        with self.assertRaises(ValueError):
            m.settings_template(manifest, "ios", 256, Path("/SELECTED/adb"))

    def test_signed_app_inventory_cannot_gain_extra_or_linked_files(self):
        manifest = self.manifest()
        executable = self.file("session/ios-derived/Build/Products/Debug-iphoneos/p2pkit-rpc-phone.app/p2pkit-rpc-phone")
        app = executable.parent
        manifest["iosApp"] = str(app)
        manifest["artifacts"]["ios-executable"] = m.artifact(executable)
        with patch.object(m, "ROOT", self.root):
            self.assertIs(m.verify_manifest(manifest, self.source, self.root / "session"), manifest)
            extra = app / "added.bin"
            extra.write_bytes(b"ADDED")
            with self.assertRaises(ValueError):
                m.verify_manifest(manifest, self.source, self.root / "session")
            extra.unlink()
            extra.symlink_to(executable)
            with self.assertRaises(ValueError):
                m.verify_manifest(manifest, self.source, self.root / "session")

    def test_duplicate_json_and_overwriting_an_original_summary_are_refused(self):
        with self.assertRaises(ValueError):
            json.loads('{"schema":1,"schema":2}', object_pairs_hook=m.unique)
        path = self.root / "summary.json"
        m.new_json(path, dict(physicalQualified=False))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            m.new_json(path, dict(physicalQualified=True))

    def test_create_only_record_syncs_file_and_parent_before_returning(self):
        observed = []
        original = os.fsync

        def fsync(descriptor):
            observed.append("directory" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file")
            original(descriptor)

        with patch.object(m.os, "fsync", side_effect=fsync):
            m.new_json(self.root / "original-lease.json", dict(physicalQualified=False))
        self.assertEqual(observed, ["file", "directory"])

    def test_full_duration_private_json_uses_report_bound_not_small_control_record_bound(self):
        path = self.root / "full-series.json"
        value = dict(physicalQualified=False, samples=["x" * 1000] * 600)
        m.new_json(path, value)
        self.assertGreater(path.stat().st_size, 262_144)
        self.assertEqual(m.private_json(path), value)
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            m.private_json(path)
        path.chmod(0o600)
        path.write_text('{"measurement":NaN}')
        with self.assertRaises(ValueError):
            m.private_json(path)


class Toolchain(unittest.TestCase):
    def doctor_fixture(self, root, *, download_fails=False):
        sdk = root / "sdk"
        for item in ("platforms/android-36", "platforms/android-37.0", "ndk/29.0.14206865", "platform-tools/adb"):
            (sdk / item).mkdir(parents=True)
        environment = {"ANDROID_HOME": str(sdk)}
        for major, key in ((17, "JAVA_HOME"), (21, "P2PKIT_AUDIT_JDK21")):
            home = root / ("jdk" + str(major))
            (home / "bin").mkdir(parents=True)
            for binary in ("java", "javac"):
                (home / "bin" / binary).touch()
            environment[key] = str(home)
        session = object.__new__(m.Session)
        session.state = root / "session"
        calls = []
        ready = False

        def command(label, argv, timeout=120, *, gradle=False):
            nonlocal ready
            calls.append((label, list(argv), timeout, gradle))
            if list(argv) == ["--version"] and gradle:
                if download_fails:
                    raise ValueError("OFFLINE_WRAPPER_DOWNLOAD_FAILURE")
                ready = True
            # Model the actual finalizer dependency: a cold wrapper cannot
            # finalize a plain tool command within the Stop-only budget.
            if not ready:
                raise ValueError("OFFLINE_COLD_WRAPPER_STOP_FAILURE")
            directory = session.state / "evidence" / label
            directory.mkdir(parents=True)
            major = label.removeprefix("doctor-jdk")
            (directory / "product.stderr.log").write_text(
                "    java.specification.version = " + major + "\n    os.arch = aarch64\n")
            return {"id": label}

        session.command = command
        return session, environment, calls

    def test_new_home_downloads_wrapper_before_plain_tools_need_its_finalizer(self):
        with tempfile.TemporaryDirectory() as temporary:
            session, environment, calls = self.doctor_fixture(Path(temporary).resolve())
            with patch.dict(m.os.environ, environment), patch.object(m.shutil, "which", return_value="/tools/xcodegen"):
                session.doctor()
            self.assertTrue(any(label == "doctor-jdk21" for label, *_ in calls))
            self.assertEqual(calls[0][:2], ("doctor-wrapper", ["--version"]))
            self.assertTrue(calls[0][3])
            self.assertGreater(calls[0][2], 120)
            self.assertTrue(all(timeout == 120 and not gradle for _, _, timeout, gradle in calls[1:]))

    def test_failed_wrapper_download_does_not_dispatch_tool_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            session, environment, calls = self.doctor_fixture(Path(temporary).resolve(), download_fails=True)
            with patch.dict(m.os.environ, environment), patch.object(m.shutil, "which", return_value="/tools/xcodegen"):
                with self.assertRaisesRegex(ValueError, "OFFLINE_WRAPPER_DOWNLOAD_FAILURE"):
                    session.doctor()
            self.assertEqual(len(calls), 1)

    def test_doctor_requires_actual_native_17_and_21_reports(self):
        for major in (17, 21):
            good = ("Property settings:\n    java.specification.version = " + str(major) +
                    "\n    os.arch = aarch64\n").encode()
            m.verify_native_jdk(good, major)
            for raw in (b"", good.replace(b"aarch64", b"x86_64"), good + good,
                        good.replace(str(major).encode(), b"99"), good.decode()):
                with self.subTest(major=major, raw=raw), self.assertRaises(ValueError):
                    m.verify_native_jdk(raw, major)
        for major in (True, "21", 8, 25):
            with self.subTest(major=major), self.assertRaises(ValueError):
                m.verify_native_jdk(b"java.specification.version = 21\nos.arch = aarch64\n", major)

    def test_nested_provenance_is_bound_to_this_executor_without_modifying_owner_environment(self):
        original = dict(PATH="/approved/tools", JAVA_HOME="/approved/jdk17", P2PKIT_AUDIT_JDK21="/approved/jdk21",
                        P2PKIT_GRADLE_EXECUTOR="/different/source/executor", P2PKIT_PYTHON3="/different/python",
                        GRADLE_USER_HOME="/owner/home", GH_TOKEN="OFFLINE_SENTINEL_NOT_A_CREDENTIAL",
                        SIGNING_KEY="OFFLINE_SENTINEL_NOT_A_CREDENTIAL",
                        MAVEN_CENTRAL_USERNAME="OFFLINE_SENTINEL_NOT_A_CREDENTIAL")
        before = dict(original)
        state = Path("/private/test-session")
        value = m.campaign_environment(original, state)
        self.assertEqual(original, before)
        self.assertEqual(value["P2PKIT_GRADLE_EXECUTOR"], str(m.ROOT / "scripts/run-audit-command.py"))
        self.assertEqual(value["P2PKIT_PYTHON3"], sys.executable)
        self.assertEqual(value["GRADLE_USER_HOME"], str(state / "gradle-home"))
        self.assertEqual(value["P2PKIT_AUDIT_STATE_DIR"], str(state))
        self.assertEqual(value["JAVA_HOME"], before["JAVA_HOME"])
        self.assertEqual(value["P2PKIT_AUDIT_JDK21"], before["P2PKIT_AUDIT_JDK21"])
        self.assertTrue({"GH_TOKEN", "SIGNING_KEY", "MAVEN_CENTRAL_USERNAME"}.isdisjoint(value))
        for key in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.campaign_environment(original | {key: "-Dunreviewed=true"}, state)


class Measurement(unittest.TestCase):
    def record(self):
        return dict(schema=2, clientCount=256, status="FAIL", mode="steady", errors=[dict(phase="thermal")],
                    phoneSamples=[dict(uptimeMillis=1000, cpuNanos=0, residentBytes=100, nativeThreads=20,
                                       batteryState="charging", thermalState="nominal"),
                                  dict(uptimeMillis=2000, cpuNanos=2_000_000_000, residentBytes=200, nativeThreads=21,
                                       batteryState="charging", thermalState="serious")],
                    thermalAbort=dict(status="ABORTED"))

    def test_cpu_uses_phone_clock_delta_and_may_exceed_one_core_without_faking_battery_drain(self):
        value = m.result_summary(self.record())
        self.assertEqual(value["peakObservedCpuPercentOfOneCore"], 200)
        self.assertEqual(value["peakResidentBytes"], 200)
        self.assertEqual(value["peakNativeThreads"], 21)
        self.assertEqual(value["status"], "FAIL")
        self.assertFalse(value["physicalQualified"])
        self.assertFalse(value["batteryDrainQualified"])
        self.assertEqual(value["observedBatteryStates"], ["charging"])
        self.assertEqual(value["observedThermalStates"], ["nominal", "serious"])

    def test_bad_profiles_or_regressed_clocks_cannot_be_combined(self):
        good = self.record()
        for change in (dict(schema=True), dict(schema=3), dict(clientCount=True), dict(clientCount=255),
                       dict(status="PASS")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.result_summary(good | change)
        missing = {k: v for k, v in good.items() if k != "clientCount"}
        with self.assertRaises(ValueError):
            m.result_summary(missing)
        for key, value in (("uptimeMillis", 1000), ("cpuNanos", -1)):
            changed = copy.deepcopy(good)
            changed["phoneSamples"][1][key] = value
            with self.assertRaises(ValueError):
                m.result_summary(changed)

    def test_schema1_is_still_only_128_and_missing_sensors_are_not_invented(self):
        record = self.record()
        record["schema"] = 1
        record.pop("clientCount")
        record["phoneSamples"] = []
        value = m.result_summary(record)
        self.assertEqual(value["clientCount"], 128)
        self.assertIsNone(value["peakObservedCpuPercentOfOneCore"])
        self.assertEqual(value["observedThermalStates"], [])
        with self.assertRaises(ValueError):
            m.result_summary(record | dict(clientCount=256))

    def test_idle_and_generator_observations_remain_distinct_from_phone_peaks(self):
        idle = dict(status="PASS", physicalQualified=False)
        generator = dict(cpuNanos=999999999, nativeThreads=999)
        record = self.record() | dict(connectedIdle=idle, generatorAfter=generator)
        result = m.result_summary(record)
        self.assertEqual(result["connectedIdle"], idle)
        self.assertEqual(result["generatorAfter"], generator)
        self.assertEqual(result["peakNativeThreads"], 21)
        self.assertFalse(result["physicalQualified"])


class Recovery(unittest.TestCase):
    def records(self, phone="ios"):
        source = dict(commit="1" * 40, tree="2" * 40, status="", diffSha256="3" * 64)
        attempt = dict(source=source, platform=phone, clients=256, mode="steady", runLabel="failed-01",
                       hostArtifactSha256="4" * 64, deviceSha256="5" * 64, settingsSha256="6" * 64)
        bound = dict(schema="2", scope=m.protocol.SCOPE, clientCount="256", runLabel="failed-01", runNonce="7" * 64,
                     hostPlatform="Ios" if phone == "ios" else "Android", hostSourceSha=source["commit"],
                     hostArtifactSha256=attempt["hostArtifactSha256"])
        result = dict(schema=2, clientCount=256, mode="steady", source=source, harnessSource=source,
                      settingsSha256=attempt["settingsSha256"], sourceUnchanged=True, harnessUnchanged=True,
                      status="FAIL", errors=[dict(phase="execution", error="ValueError")], mobileBinding=bound,
                      inboxSha256="8" * 64,
                      phoneCleanup=dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True),
                      usbCleanup=(dict(runtimeClosed=True, clientPinsRemoved=True, requiresOuterNativeFinalization=True)
                                  if phone == "ios" else dict(privateServerExited=True, copiedHostKeysRetired=True)))
        return attempt, result

    def test_failed_but_actual_healthy_closed_attempt_grants_reuse_without_promoting_result(self):
        for phone in ("android", "ios"):
            attempt, result = self.records(phone)
            original = copy.deepcopy(result)
            authority = m.retired_attempt(attempt, result)
            self.assertEqual(authority["originalStatus"], "FAIL")
            self.assertEqual(authority["runLabel"], attempt["runLabel"])
            self.assertEqual(authority["deviceSha256"], attempt["deviceSha256"])
            self.assertFalse(authority["physicalQualified"])
            self.assertEqual(result, original)

    def test_uncertain_cleanup_thermal_or_foreign_attempt_cannot_authorize_reinstallation_or_next_slot(self):
        attempt, result = self.records()
        changes = [dict(schema=True), dict(clientCount=128), dict(mode="churn"), dict(source={}),
                   dict(harnessSource={}), dict(settingsSha256="9" * 64), dict(sourceUnchanged=False),
                   dict(harnessUnchanged=False), dict(status="PASS"), dict(phoneCleanup={}), dict(inboxSha256=""),
                   dict(errors=[dict(phase="phone-retirement")]), dict(thermalAbort=dict(status="ABORTED")),
                   dict(usbCleanup={}), dict(mobileBinding=result["mobileBinding"] | {"runLabel": "another-run"}),
                   dict(mobileBinding=result["mobileBinding"] | {"hostArtifactSha256": "9" * 64})]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.retired_attempt(attempt, result | change)
        android_attempt, android_result = self.records("android")
        for key in ("privateServerExited", "copiedHostKeysRetired"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.retired_attempt(android_attempt, android_result | {"usbCleanup": android_result["usbCleanup"] | {key: False}})

    def test_pending_attempt_is_an_atomic_preinstallation_interlock_and_retains_original_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "state"
            (state / "private").mkdir(parents=True, mode=0o700)
            original = dict(attempt=str(state / "private/attempt-ios-failed-01.json"), sha256="1" * 64)
            m.new_json(state / "private/ios-pending.json", original)
            session = object.__new__(m.Session)
            session.state = state
            session.source = dict(commit="1" * 40)
            product = dict(artifacts={"ios-executable": dict(sha256="4" * 64)}, iosApp="/not/reinstalled.app")
            settings = dict(schema="2", clientCount="256", sourceSha="1" * 40, hostArtifactSha256="4" * 64)
            session.command = lambda *args, **kwargs: self.fail("Must not install, launch or execute another command")
            files = SimpleNamespace(parse=lambda raw: settings, read_private=lambda path: b"synthetic")
            original_module = m.module

            def modules(name, path):
                return files if name == "mac_campaign_settings" else original_module(name, path)

            with patch.object(m, "verify_manifest", return_value=product), patch.object(m, "private_json", return_value={}), \
                    patch.object(m, "module", side_effect=modules), self.assertRaisesRegex(ValueError, "remains unresolved"):
                session.run(SimpleNamespace(platform="ios", clients=256, settings=root / "settings.txt",
                                            run_label="new-02", mode="steady"))
            self.assertEqual(json.loads((state / "private/ios-pending.json").read_text()), original)
            with self.assertRaises(FileExistsError):
                m.new_json(state / "private/ios-pending.json", dict(attempt="another"))

    def session(self, root):
        state = root / "state"
        for name in ("private", "commands", "evidence"):
            (state / name).mkdir(parents=True, mode=0o700)
        attempt, result = self.records()
        job, invocation = "a" * 32, "b" * 32
        purpose = "campaign-ios-failed-01"
        argv = [sys.executable, "OFFLINE_COORDINATOR_FIXTURE_NOT_DEVICE_EXECUTION"]
        receipt_path = state / "commands" / (purpose + "-aabbccdd.json")
        attempt |= dict(schema=1, purpose=purpose, argv=argv, receipt=str(receipt_path))
        proof = dict(schema=1, id=invocation, jobId=job, purpose=purpose, cwd=str(m.ROOT),
                     host="macos-arm64", kind="command", gradleHome=str(state / "gradle-home"),
                     wrapper=str(m.ROOT / "gradlew"), requestedArgv=argv, productExitCode=1, finalExitCode=1,
                     stopExitCode=0, sourceUnchanged=True, errors=[], ownedSurvivors=[],
                     sourceBefore=attempt["source"], sourceAfter=attempt["source"])
        (state / "evidence" / invocation).mkdir(mode=0o700)
        m.new_json(state / "evidence" / invocation / "receipt.json", proof)
        m.new_json(receipt_path, proof)
        attempt_path = state / "private/attempt-ios-failed-01.json"
        m.new_json(attempt_path, attempt)
        m.new_json(state / "private/ios-pending.json",
                   dict(attempt=str(attempt_path), sha256=m.artifact(attempt_path)["sha256"]))
        session = object.__new__(m.Session)
        session.state = state
        session.source = attempt["source"]
        session.runner = SimpleNamespace(read_json=lambda path: json.loads(path.read_text()),
                                         context_at=lambda path: (state, {"id": job}))
        session.checker = m.module("mac_recovery_receipt_test", "check-audit-receipt.py")
        return session, attempt, result, proof

    def test_recovery_releases_only_original_lease_after_native_receipt_and_phone_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            session, attempt, result, proof = self.session(Path(directory).resolve())
            original_attempt = (session.state / "private/attempt-ios-failed-01.json").read_bytes()
            original_receipt = Path(attempt["receipt"]).read_bytes()
            with session.phone_lock("ios"):
                session.retire_pending("ios", attempt, result, proof)
            self.assertFalse((session.state / "private/ios-pending.json").exists())
            latest = json.loads((session.state / "private/ios-latest.json").read_text())
            self.assertEqual(latest["originalStatus"], "FAIL")
            self.assertEqual(latest["inboxSha256"], result["inboxSha256"])
            self.assertEqual((session.state / "private/attempt-ios-failed-01.json").read_bytes(), original_attempt)
            self.assertEqual(Path(attempt["receipt"]).read_bytes(), original_receipt)

    def test_failed_or_foreign_native_finalization_keeps_interlock_and_all_original_evidence(self):
        for change in (dict(jobId="c" * 32), dict(host="linux-x64"), dict(kind="gradle"), dict(gradleHome="/another/home"),
                       dict(errors=["unknown cleanup"]), dict(ownedSurvivors=[dict(pid=1)]),
                       dict(stopExitCode=1), dict(requestedArgv=["another-command"]), dict(finalExitCode=125)):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                session, attempt, result, proof = self.session(Path(directory).resolve())
                changed = proof | change
                # Match both saved copies: acceptance must still depend on the
                # original job, argv and genuine finalization, not copy equality.
                Path(attempt["receipt"]).write_text(json.dumps(changed))
                (session.state / "evidence" / proof["id"] / "receipt.json").write_text(json.dumps(changed))
                with session.phone_lock("ios"), self.assertRaises(ValueError):
                    session.retire_pending("ios", attempt, result, changed)
                self.assertTrue((session.state / "private/ios-pending.json").exists())
                self.assertFalse((session.state / "private/ios-latest.json").exists())

    def untouched(self, root):
        session, attempt, result, proof = self.session(root)
        for key in ("inboxSha256", "phoneCleanup"):
            result.pop(key)
        result.update(deviceControlStarted=False, usbCommands=[], phoneSamples=[])
        control = session.state / "work/mobile-control-failed-01"
        control.mkdir(parents=True, mode=0o700)
        for directory in (control / "usb", control / "commands", session.state / "work/mobile-client-failed-01"):
            directory.mkdir(parents=True, mode=0o700)
        return session, attempt, result, proof, control

    def test_untouched_prerequisite_failure_releases_lease_without_inventing_installed_continuation(self):
        for previous in (False, True):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as directory:
                session, attempt, result, proof, _ = self.untouched(Path(directory).resolve())
                latest = session.state / "private/ios-latest.json"
                if previous:
                    m.new_json(latest, dict(scope="ORIGINAL_CLOSED_INSTALLATION"))
                saved = latest.read_bytes() if previous else None
                with session.phone_lock("ios"):
                    session.retire_pending("ios", attempt, result, proof)
                self.assertFalse((session.state / "private/ios-pending.json").exists())
                if previous:
                    self.assertEqual(latest.read_bytes(), saved)
                else:
                    self.assertFalse(latest.exists())
                retained = m.private_json(session.state / "private/undispatched-ios-failed-01.json")
                self.assertEqual(retained["originalStatus"], "FAIL")
                self.assertFalse(retained["physicalQualified"])

    def test_flag_alone_cannot_erase_device_dispatch_or_unqualified_native_cleanup(self):
        for mutation in ("marker", "linked-marker", "command", "phone-file", "client-file", "inbox", "installation",
                         "phone-sample", "command-series", "native-failure", "thermal"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                session, attempt, result, proof, control = self.untouched(Path(directory).resolve())
                if mutation == "marker":
                    m.new_json(control / "device-control-started.json", {})
                elif mutation == "linked-marker":
                    (control / "device-control-started.json").symlink_to(control / "absent")
                elif mutation in ("command", "phone-file", "client-file"):
                    path = {"command": control / "commands/original.json", "phone-file": control / "usb/original.json",
                            "client-file": session.state / "work/mobile-client-failed-01/config.txt"}[mutation]
                    path.write_text("ORIGINAL_DISPATCH_EVIDENCE")
                elif mutation == "inbox":
                    result["inboxSha256"] = "8" * 64
                elif mutation == "installation":
                    result["installationAccepted"] = False
                elif mutation == "phone-sample":
                    result["phoneSamples"] = [{}]
                elif mutation == "command-series":
                    result["usbCommands"] = [{}]
                elif mutation == "thermal":
                    result["thermalAbort"] = {}
                else:
                    proof = proof | dict(stopExitCode=1)
                    Path(attempt["receipt"]).write_text(json.dumps(proof))
                    (session.state / "evidence" / proof["id"] / "receipt.json").write_text(json.dumps(proof))
                with session.phone_lock("ios"), self.assertRaises(ValueError):
                    session.retire_pending("ios", attempt, result, proof)
                self.assertTrue((session.state / "private/ios-pending.json").exists())
                self.assertFalse((session.state / "private/ios-latest.json").exists())

    def test_run_and_recover_are_serialized_until_original_retirement_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            session, attempt, result, proof = self.session(Path(directory).resolve())
            competitor = object.__new__(m.Session)
            competitor.state = session.state
            pending = session.state / "private/ios-pending.json"
            original_artifact = m.artifact
            observations = []

            def artifact(path):
                value = original_artifact(path)
                if path == pending:
                    observations.append(value)
                    if len(observations) == 2:
                        # The former hash-to-unlink window allowed a concurrent
                        # recovery to remove this lease and a run to create a
                        # new one, which the old recovery then deleted.
                        with self.assertRaisesRegex(ValueError, "Another run/recover"):
                            competitor.recover("ios")
                        with self.assertRaisesRegex(ValueError, "Another run/recover"):
                            competitor.run(SimpleNamespace(platform="ios"))
                return value

            with session.phone_lock("ios"), patch.object(m, "artifact", side_effect=artifact):
                session.retire_pending("ios", attempt, result, proof)
            self.assertEqual(len(observations), 2)
            self.assertFalse(pending.exists())
            with competitor.phone_lock("ios"):
                m.new_json(pending, dict(attempt="NEW_OFFLINE_ATTEMPT"))
            self.assertEqual(m.private_json(pending), dict(attempt="NEW_OFFLINE_ATTEMPT"))

    def test_stable_phone_locks_are_independent_never_unlinked_and_release_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            session, _, _, _ = self.session(Path(directory).resolve())
            other = object.__new__(m.Session)
            other.state = session.state
            path = session.state / "private/ios-owner.lock"
            with session.phone_lock("ios"):
                original = path.lstat().st_ino
                self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o600)
                with self.assertRaisesRegex(ValueError, "Another run/recover"):
                    other.recover("ios")
                with other.phone_lock("android"):
                    self.assertTrue((session.state / "private/android-owner.lock").is_file())
            with self.assertRaisesRegex(RuntimeError, "OFFLINE_FAILURE"), session.phone_lock("ios"):
                raise RuntimeError("OFFLINE_FAILURE")
            with other.phone_lock("ios"):
                self.assertEqual(path.lstat().st_ino, original)
            self.assertEqual(path.lstat().st_ino, original)

    def test_linked_shared_or_nonprivate_lock_is_refused_before_any_operation(self):
        for kind in ("symlink", "hardlink", "nonprivate"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                session, _, _, _ = self.session(Path(directory).resolve())
                path = session.state / "private/ios-owner.lock"
                target = session.state / "private/foreign.lock"
                target.write_bytes(b"")
                target.chmod(0o600)
                if kind == "symlink":
                    path.symlink_to(target)
                elif kind == "hardlink":
                    os.link(target, path)
                else:
                    path.write_bytes(b"")
                    path.chmod(0o644)
                with self.assertRaises((OSError, ValueError)), session.phone_lock("ios"):
                    self.fail("An unsafe lock cannot admit run or recover")

    def test_invalid_generated_settings_fail_before_attempt_lease_or_device_command(self):
        for phone in ("android", "ios"):
            with self.subTest(phone=phone), tempfile.TemporaryDirectory() as directory:
                session, _, _, _ = self.session(Path(directory).resolve())
                (session.state / "private/ios-pending.json").unlink()
                product = dict(source=session.source, iosApp="/OFFLINE/NOT_INSTALLED.app", artifacts={
                    "android-apk": dict(sha256="4" * 64), "ios-executable": dict(sha256="4" * 64)})
                settings = session.state / "private/settings.txt"
                settings.write_bytes(m.settings_template(product, phone, 256, Path("/OFFLINE/adb")))
                settings.chmod(0o600)
                session.command = lambda *args, **kwargs: self.fail("Invalid settings must not dispatch a device command")
                with patch.object(m, "verify_manifest", return_value=product), \
                        patch.object(m, "private_json", return_value={}), self.assertRaises(ValueError):
                    session.run(SimpleNamespace(platform=phone, clients=256, settings=settings,
                                                run_label="new-02", mode="steady"))
                self.assertFalse((session.state / "private" / (phone + "-pending.json")).exists())
                self.assertFalse((session.state / "private" / ("attempt-" + phone + "-new-02.json")).exists())

    def test_both_original_attempt_and_lease_are_durable_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            session, _, _, _ = self.session(Path(directory).resolve())
            (session.state / "private/ios-pending.json").unlink()
            product = dict(source=session.source, iosApp="/OFFLINE/NOT_INSTALLED.app",
                           artifacts={"ios-executable": dict(sha256="4" * 64)})
            settings = session.state / "private/settings.txt"
            values = m.protocol.parse(m.settings_template(product, "ios", 256, Path("/OFFLINE/adb")))
            values.update(endpointAddress="192.168.10.2", localAddress="192.168.10.1", subnets="192.168.10.0/24",
                          interface="en0", hostInterface="en0", iosDeviceIdentifier="aabbccdd-1122-3344-5566-aabbccddeeff")
            settings.write_bytes(m.protocol.encode(values))
            settings.chmod(0o600)
            m.new_json(session.state / "private/preparation.json", product)
            observed = []
            original_fsync = os.fsync

            def fsync(descriptor):
                observed.append("directory" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file")
                original_fsync(descriptor)

            def dispatch(*args, **kwargs):
                self.assertEqual(observed[-4:], ["file", "directory", "file", "directory"])
                self.assertTrue((session.state / "private/attempt-ios-new-02.json").is_file())
                self.assertTrue((session.state / "private/ios-pending.json").is_file())
                self.assertEqual(session._locked_phone, "ios")
                raise RuntimeError("OFFLINE_STOP_BEFORE_DEVICE_EXECUTION")

            session.command = dispatch
            with patch.object(m, "verify_manifest", return_value=product), patch.object(m.os, "fsync", side_effect=fsync), \
                    self.assertRaisesRegex(RuntimeError, "OFFLINE_STOP_BEFORE_DEVICE_EXECUTION"):
                session.run(SimpleNamespace(platform="ios", clients=256, settings=settings,
                                            run_label="new-02", mode="steady"))
            self.assertTrue((session.state / "private/ios-pending.json").exists())


if __name__ == "__main__":
    unittest.main()
