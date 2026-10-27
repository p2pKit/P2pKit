#!/usr/bin/env python3
"""Parser/fixture controls only, never raw socket, authenticated RPC or device capacity credit."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rpc = load("run-rpc-io-benchmark")
android = load("run-android-readiness")
ios = load("run-rpc-io-phone-controls")


class ReceiptTest(unittest.TestCase):
    def test_phone_route_uses_original_full_simulator_suite_and_no_device_signing_or_test_filter(self):
        simulator = "AB123456-1234-1234-1234-123456789012"
        command = ios.xctest_command(Path("phone.xcodeproj"), simulator, Path("derived"), Path("tests.xcresult"))
        self.assertIn("platform=iOS Simulator,id=" + simulator, command)
        self.assertIn("iphonesimulator", command)
        self.assertIn("SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", command)
        self.assertEqual(command[-1], "test")
        self.assertFalse(any("-only-testing" in item or "-skip-testing" in item for item in command))
        expected = ios.phone.inventory(ROOT)
        self.assertEqual({target: len(tests) for target, tests in expected.items()},
                         {"p2pkit-rpc-phone-tests": 89, "p2pkit-rpc-phone-uitests": 7})
        self.assertIn("RpcPhoneRunOwnerTests/testActualKeychainRoundTripNamespacesRevocationAndFixtureRetirement()",
                      expected["p2pkit-rpc-phone-tests"])
        owner = {case for case in expected["p2pkit-rpc-phone-tests"]
                 if case.startswith("RpcPhoneRunOwnerTests/")}
        self.assertEqual(len(owner), 79)  # Preserve the original77 plus2 used-slot/sealed-input regressions.
        self.assertTrue({"RpcPhoneRunOwnerTests/" + name + "()" for name in (
            "testUsedOrInterruptedRuntimeOutputsAreRefusedBeforeReusingAUsbRun",
            "testDebugCampaignAndNextInputsRequireSealsAndCannotBeReplayedIntoANewFileOwner",
        )} <= owner)
        self.assertEqual({case for case in expected["p2pkit-rpc-phone-tests"]
                          if case.startswith("RpcPhoneEnvironmentSamplerTests/")},
                         {"RpcPhoneEnvironmentSamplerTests/" + name + "()" for name in (
                             "testPlatformDefaultsReadAndRestoreActualMainActorDeviceMonitoring",
                             "testAcquiringAndRetiringBatteryMonitoringIsIdempotentAndRestoresItsPriorSetting",
                             "testUnknownBatteryLevelNeverBecomesAnInventedZeroOrAnEnergyMeasurement",
                             "testSeriousAndCriticalThermalObservationsAbortTheCampaign",
                         )})
        self.assertEqual({case for case in expected["p2pkit-rpc-phone-tests"]
                          if case.startswith("RpcPhoneUsbDeveloperCommandTests/")},
                         {"RpcPhoneUsbDeveloperCommandTests/" + name + "()" for name in (
                             "testInitialDeveloperPrepareRequiresTheExactSourceArtifactCountAndNewSafeLabel",
                             "testExact256SourceArtifactInboxBindingVerifiesWithoutCreatingAnOwnerOrTrustImport",
                             "testChangedSourceArtifactCapacityAndInboxCannotAuthorizeStart",
                             "testMalformedDuplicateUnexpectedNonAsciiAndUnsafeLabelsCannotBecomeCommands",
                             "testNextRunIsBoundToPreviousInboxAndCannotReuseTheSlotOrRequestUnsupportedCapacity",
                             "testNextRunRequiresCompleteMatchingHealthyStopReceiptRatherThanOnlyAnExistingFile",
                         )})
        for invalid in ("booted", "", "--another-device", simulator + "\n"):
            with self.assertRaises(RuntimeError):
                ios.xctest_command(Path("phone"), invalid, Path("derived"), Path("result"))

    def test_manual_phone_inputs_fit_both_profiles_without_reclassifying_usb_campaign(self):
        # Wiring only: actual parsing is covered by RpcPhoneLabTest, stores by ART/Keychain controls.
        android_ui = (ROOT / "samples/p2p-sample-android/src/debug/java/dev/p2pkit/sample/android/rpclab/"
                      "RpcLabActivity.kt").read_text()
        apple_ui = (ROOT / "samples/p2p-sample-rpc/phone-ios/Sources/RpcPhoneApp.swift").read_text()
        for source, pattern in ((android_ui, r'Field\("Optional: exactly 128 or 256[^"\n]*",\s*capacityPins, ([0-9_]+)'),
                                (apple_ui, r'field\("Exactly 128 or 256[^"\n]*", \$model.capacityPins,\s*limit: ([0-9_]+)')):
            match = re.search(pattern, source)
            self.assertIsNotNone(match)
            limit = int(match[1].replace("_", ""))
            self.assertEqual(limit, 16_384)
            # Canonical fingerprints are 57 ASCII bytes each, plus one line separator.
            self.assertLessEqual(256 * 58, limit)
        contract = (ROOT / "samples/p2p-sample-rpc/src/commonMain/kotlin/dev/p2pkit/sample/rpc/"
                    "RpcCapacityContract.kt").read_text()
        self.assertIn("public const val CLIENTS: Int = 128", contract)
        self.assertIn("public const val STEADY_SECONDS: Int = 30 * 60", contract)

    def test_android_installed_digest_does_not_require_guest_hash_utility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "source.apk"
            payload = b"synthetic source APK bytes"
            apk.write_bytes(payload)
            observed = []

            def pull(command, **kwargs):
                if command[3] == "shell":
                    self.assertEqual(command[4:6], ["ls", "-ldn"])
                    self.assertFalse(kwargs["check"])
                    return
                self.assertEqual(command[:5], ["adb", "-s", "emulator-5556", "exec-out", "cat"])
                self.assertEqual(command[5], "/data/app/~~fixture==/dev.p2pkit.transport.lan.test-1/base.apk")
                destination = kwargs["stdout_file"]
                self.assertFalse(destination.exists())
                self.assertNotEqual(destination, apk)
                observed.append(destination)
                destination.write_bytes(payload)

            actual = android.verify_installed_apk(["adb", "-s", "emulator-5556"],
                "package:/data/app/~~fixture==/dev.p2pkit.transport.lan.test-1/base.apk", apk, root, pull)
            self.assertEqual(actual, hashlib.sha256(payload).hexdigest())
            self.assertEqual(len(observed), 1)
            self.assertFalse(observed[0].exists())
            self.assertEqual(apk.read_bytes(), payload)

            # API24 uses the dotted package directly beneath /data/app, without the newer random parent.
            def old_layout_pull(command, **kwargs):
                if command[1] == "shell":
                    return
                self.assertEqual(command[1:4], ["exec-out", "cat", "/data/app/dev.p2pkit.transport.lan.test-1/base.apk"])
                kwargs["stdout_file"].write_bytes(payload)
            self.assertEqual(actual, android.verify_installed_apk(["adb"],
                "package:/data/app/dev.p2pkit.transport.lan.test-1/base.apk", apk, root, old_layout_pull))

    def test_android_installed_digest_rejects_mismatch_incomplete_and_ambiguous_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "source.apk"
            apk.write_bytes(b"original")
            for payload in (b"modified", b"short", None):
                def pull(command, **kwargs):
                    if payload is not None and "stdout_file" in kwargs:
                        kwargs["stdout_file"].write_bytes(payload)
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    android.verify_installed_apk(["adb"], "package:/data/app/fixture/base.apk", apk, root, pull)
            with self.assertRaises(ValueError):
                android.verify_installed_apk(["adb"], "package:/data/app/a/base.apk\npackage:/data/app/b/base.apk",
                                             apk, root, lambda *args, **kwargs: self.fail("Must not pull"))

    def test_android_installed_byte_reader_failure_is_not_an_integrity_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "source.apk"
            apk.write_bytes(b"original")
            def failed_cat(command, **kwargs):
                if "stdout_file" in kwargs:
                    kwargs["stdout_file"].write_bytes(b"original")
                    raise RuntimeError("synthetic nonzero byte-reader exit")
            with self.assertRaisesRegex(RuntimeError, "nonzero"):
                android.verify_installed_apk(["adb"], "package:/data/app/fixture/base.apk",
                                             apk, root, failed_cat)

    def rpc_result(self, count):
        return dict(schema=2, source="a" * 40, cleanup=True,
                    scope="AUTHENTICATED_RPC_LAB_NOT_PHYSICAL_OR_MOBILE_QUALIFICATION",
                    measurements=dict(clients=count, seconds=120, responses=count * 120 * 10,
                        activeWallNs=120_000_000_000, late100msSlots=0, hostThreadsBeforeConnections=20,
                        hostThreadsIdle=30, hostThreadsAfter=30, hostRssBeforeBytes=100_000_000,
                        hostRssIdleBytes=110_000_000, hostRssAfterBytes=200_000_000, hostIdleWallMs=5_000,
                        hostSteadyIdleStartMs=40_000, hostSteadyIdleWallMs=30_000, hostSteadyIdleCpuNs=50_000_000,
                        hostSteadyIdleThreads=30, hostSteadyIdleRssBytes=110_000_000,
                        hostIdleCpuNs=1_000_000, hostActiveCpuNs=50_000_000_000, hostActiveWallMs=120_000,
                        hostRetainedRecords=count * 600, hostPayloadBytes=count * 600 * 1024),
                    latencyUpperMs=dict(p50=5, p95=10, p99=20, max=30))

    def encode(self, value):
        return rpc.PREFIX + json.dumps(value).encode() + b"\n"

    def test_both_rpc_profiles_are_exact_source_bound(self):
        for count in (128, 256):
            value = self.rpc_result(count)
            self.assertEqual(value, rpc.validate_result(self.encode(value), "a" * 40, count, 120))
            with self.assertRaises(RuntimeError):
                rpc.validate_result(self.encode(value), "b" * 40, count, 120)

    def test_missing_duplicate_incomplete_failed_rpc_is_not_success(self):
        value = self.rpc_result(256)
        invalid = [b"", self.encode(value) * 2]
        for field, replacement in (("cleanup", False), ("scope", "physical")):
            changed = copy.deepcopy(value)
            changed[field] = replacement
            invalid.append(self.encode(changed))
        for field, replacement in (("clients", 128), ("seconds", 60), ("responses", 0)):
            changed = copy.deepcopy(value)
            changed["measurements"][field] = replacement
            invalid.append(self.encode(changed))
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                rpc.validate_result(raw, "a" * 40, 256, 120)

    def test_rpc_requires_actual_resources_durations_and_ordered_percentiles(self):
        value = self.rpc_result(256)
        for field in value["measurements"]:
            changed = copy.deepcopy(value)
            del changed["measurements"][field]
            with self.subTest(field=field), self.assertRaises((RuntimeError, KeyError)):
                rpc.validate_result(self.encode(changed), "a" * 40, 256, 120)
        for latency in ({}, dict(p50=1, p95=20, p99=10, max=30), dict(p50=1, p95=True, p99=20, max=30)):
            with self.subTest(latency=latency), self.assertRaises(RuntimeError):
                rpc.validate_result(self.encode({**value, "latencyUpperMs": latency}), "a" * 40, 256, 120)
        changed = copy.deepcopy(value)
        changed["measurements"]["hostSteadyIdleWallMs"] = 29_999
        with self.assertRaises(RuntimeError):
            rpc.validate_result(self.encode(changed), "a" * 40, 256, 120)

    def android_result(self):
        measurements = [dict(backend=backend, clients=count, responses=count * 300, bytesPerResponse=1024,
                             readinessThreads=1 if backend == "nio-selector" else 2,
                             threadsBefore=20, threadsIdle=30, idleWallNs=5_100_000_000, activeWallNs=30_000_000_000)
                        for backend in ("nio-selector", "native-os-poll") for count in (128, 256)]
        return {"scope": android.SCOPE, "outcome": "PASS", "completed": "4",
                "measurements": json.dumps(measurements)}

    def android_encode(self, value):
        return ("".join(f"INSTRUMENTATION_RESULT: {key}={item}\n" for key, item in value.items()) +
                "INSTRUMENTATION_CODE: -1\n").encode()

    def test_android_requires_four_actual_backend_population_combinations(self):
        value = self.android_result()
        self.assertEqual(4, len(android.result(self.android_encode(value))))
        for key, item in (("completed", "3"), ("scope", "rpc-qualified"), ("outcome", "FAIL"),
                          ("failurePhase", "cleanup")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                android.result(self.android_encode({**value, key: item}))

    def test_android_rejects_missing_response_counts_and_per_client_threads(self):
        value = self.android_result()
        for key, item in (("responses", 0), ("threadsIdle", 324), ("readinessThreads", 256)):
            changed = json.loads(value["measurements"])
            changed[0][key] = item
            with self.subTest(key=key), self.assertRaises(ValueError):
                android.result(self.android_encode({**value, "measurements": json.dumps(changed)}))


if __name__ == "__main__":
    unittest.main()
