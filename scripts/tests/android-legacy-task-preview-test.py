#!/usr/bin/env python3
"""Offline identity/completion and install-shell controls; never Android execution evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("legacy_task", ROOT / "scripts/run-android-legacy-task-preview.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
TOKEN, SOURCE, TREE = "a" * 32, "b" * 40, "c" * 40


def synthetic_png(visible=False):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    colors = (b"\xff\0\xff", b"\0\xff\xff", b"\0\xff\0", b"\xff\xff\0")
    row = b"\0" + (b"".join(color * 4 for color in colors) if visible else b"\0" * 48)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(row * 16)) + chunk(b"IEND", b""))


def fixture(api=24, unavailable=False):
    captures, files = [], {}
    for index, name in enumerate(legacy.CAPTURES):
        item = dict(name=name, observation="BITMAP", file=name + ".png", width=16, height=16,
                    sourceBitmapWidth=16, sourceBitmapHeight=16, sourceBitmapConfig="ARGB_8888",
                    pixelReadback="ARGB_8888_COPY", elapsedMillis=100 + index * 10)
        if name != "actual-recents-original":
            visible = name in legacy.POSITIVE
            identity = 1 if index in (0, 2) else 2
            state = dict(activity=identity, window=identity + 10, view=identity + 20, taskId=7,
                         viewWidth=16, viewHeight=16, viewDraws=1,
                         samplePoints=[[2, 4], [6, 4], [10, 4], [14, 4]],
                         owned=True, viewAttached=True, windowFocused=True, secureFlag=not visible)
            item.update(sampleMatches=[visible] * 4, stateBefore=state, stateAfter=copy.deepcopy(state))
        else:
            visible = True
            system = dict(activity=1, taskId=7, secureFlag=True, stopped=True, windowFocused=False,
                          package="synthetic.system.ui", windowId=10, bounds=[0, 0, 16, 16])
            item.update(pixelVariation=True, systemWindowBefore=system, systemWindowAfter=copy.deepcopy(system))
        if unavailable and name not in legacy.POSITIVE and name != "actual-recents-original":
            item = {key: item[key] for key in ("name", "elapsedMillis", "stateBefore", "stateAfter")}
            item["observation"] = "UNAVAILABLE"
        else:
            files[name + ".png"] = synthetic_png(visible)
        captures.append(item)
    report = dict(case="479", token=TOKEN, sourceCommit=SOURCE, declaredSourceTree=TREE,
        api=api, targetSdk=37, captureObservationSchema=2, outcome=legacy.owner.PASS,
        syntheticOnly=True, recentsReviewRequired=True, cleanup="OWNED_ACTIVITIES_DESTROYED", taskId=7,
        navigationRequests=[dict(action=action, platformAction=platform, requestedElapsedMillis=start,
            returnedElapsedMillis=start + 1, returned=True, accepted=True, operation="GLOBAL_ACTION_RETURNED")
            for action, platform, start in (("HOME", 2, 101), ("RECENTS", 3, 103))],
        captures=captures, lifecycle=[dict(event=event, activity=activity, taskId=7, secureFlag=True)
            for event, activity in (("created", 1), ("stopped", 1), ("created", 2), ("destroyed", 1), ("destroyed", 2))])
    # Clearly synthetic parser inputs, not captured images or proof of visual privacy.
    files["result.json"] = json.dumps(report).encode()
    return report, files


def terminal(changes=None):
    fields = dict(p2pkitToken=TOKEN, p2pkitCompleted="1", p2pkitOutcome=legacy.owner.PASS,
                  p2pkitEvidence="no_backup/ui-479-" + TOKEN, **{"class": legacy.RUNNER},
                  test="legacyTaskPreviewPolicy", numtests="1", current="1")
    fields.update(changes or {})
    return ("".join(f"INSTRUMENTATION_STATUS: {key}={value}\n" for key, value in fields.items()) +
            "INSTRUMENTATION_STATUS_CODE: 0\n" +
            "".join(f"INSTRUMENTATION_RESULT: {key}={value}\n" for key, value in fields.items()) +
            "INSTRUMENTATION_CODE: -1\n").encode()


class LegacyTaskTests(unittest.TestCase):
    def validate(self, report, files, api=24):
        return legacy.validate_report(json.dumps(report).encode(), TOKEN, SOURCE, TREE, api, files)

    def test_both_source_bound_reports_remain_pending_visual_review(self):
        for api in (24, 32):
            for unavailable in (False, True):
                report, files = fixture(api, unavailable)
                self.assertTrue(self.validate(report, files, api)["recentsReviewRequired"])
            self.assertEqual(legacy.LegacyCampaign(api).API, api)

    def test_identity_failure_cleanup_and_false_ready_rejected(self):
        for key, invalid in (("sourceCommit", "d" * 40), ("declaredSourceTree", "d" * 40),
                ("token", "d" * 32), ("api", 35), ("targetSdk", 36), ("case", "324"),
                ("outcome", "PASS"), ("syntheticOnly", False), ("recentsReviewRequired", False),
                ("cleanup", "REQUESTED"), ("failure", {}), ("cleanupFailureType", "Error")):
            report, files = fixture()
            report[key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(report, files)

    def test_null_screenshot_diagnostic_never_substitutes_for_original_images(self):
        report, files = fixture()
        report["failure"] = {"stage": "initial-secure-foreground", "code": "SCREENSHOT_UNAVAILABLE"}
        report["captureAttempts"] = [{"name": "initial-secure-foreground",
            "operation": "GLOBAL_SCREENSHOT_REQUEST", "screenshotReturned": True,
            "screenshotAvailable": False, "secureFlag": True}]
        # Even a forged success outcome plus otherwise complete synthetic files must fail.
        with self.assertRaises(ValueError):
            self.validate(report, files)
        del report["failure"]
        report["captures"] = []
        with self.assertRaises(ValueError):
            self.validate(report, {"result.json": json.dumps(report).encode()})

    def test_instrumentation_preserves_capture_ownership_diagnostics_and_bounds(self):
        base = ROOT / "samples/p2p-sample-android/src"
        source = (base / "androidTest/java/dev/p2pkit/sample/android/runtime/LegacyTaskPreviewInstrumentation.kt").read_text()
        policy = (base / "runtimeValidation/kotlin/dev/p2pkit/sample/android/runtime/LegacyCaptureObservation.kt").read_text()
        capture = source.split("    private fun capture(", 1)[1].split("    private fun recentsState(", 1)[0]
        self.assertLess(capture.index("captureAttempts.put(attempt)"), capture.index("BODY_DEADLINE_EXCEEDED"))
        self.assertLess(capture.index("val before ="), capture.index("takeScreenshot()"))
        self.assertLess(capture.index("takeScreenshot()"), capture.index("val after ="))
        self.assertIn("checkLegacyCaptureObservation(observation", capture)
        self.assertIn("checkLegacyCaptureBracket(", source)
        self.assertIn("if (pixels !== bitmap) pixels.recycle()", capture)
        self.assertIn("finally { bitmap?.recycle() }", capture)
        self.assertIn("bitmap.copy(Bitmap.Config.ARGB_8888, false)", capture)
        self.assertIn("root.refresh() && root.isVisibleToUser", source)
        self.assertIn("checkLegacyCapture(!visible, LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE)", policy)
        self.assertIn("value.matches == null", policy)
        self.assertIn("value.matches.all { it == visible }", policy)
        self.assertNotIn("error.message", source)
        self.assertNotIn("stackTrace", source)
        self.assertIn("deadline = SystemClock.elapsedRealtime() + 90_000", source)
        self.assertIn("task.get(5, TimeUnit.SECONDS)", source)
        self.assertIn("finally { main { secureLegacyTaskWindow(replacement.window) } }", source)
        self.assertLess(source.index('stage = "actual-recents-original"'), source.index("clearFlags("))
        self.assertEqual(source.count("uiAutomation.takeScreenshot()"), 1)

    def test_navigation_requires_exactly_home_then_recents(self):
        for change in (lambda r: r.pop(), lambda r: r.append(r[0]), lambda r: r.reverse()):
            report, files = fixture()
            change(report["navigationRequests"])
            with self.assertRaises(ValueError): self.validate(report, files)
        report, files = fixture()
        report.pop("navigationRequests")
        with self.assertRaises(ValueError): self.validate(report, files)

    def test_navigation_rejects_false_throw_wrong_action_and_incomplete_return(self):
        for index in (0, 1):
            for key, invalid in (("action", "BACK"), ("platformAction", 1), ("platformAction", True),
                    ("returned", False), ("returned", 1), ("accepted", False), ("accepted", 1),
                    ("operation", "GLOBAL_ACTION_THROWN"), ("failureType", "IllegalStateException")):
                report, files = fixture()
                report["navigationRequests"][index][key] = invalid
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    self.validate(report, files)
            for key in tuple(fixture()[0]["navigationRequests"][index]):
                report, files = fixture()
                report["navigationRequests"][index].pop(key)
                with self.subTest(index=index, absent=key), self.assertRaises(ValueError):
                    self.validate(report, files)

    def test_navigation_timestamps_must_follow_initial_and_precede_recents_capture(self):
        for index, key, invalid in ((0, "requestedElapsedMillis", 99), (0, "returnedElapsedMillis", 100),
                (0, "returnedElapsedMillis", 104), (1, "requestedElapsedMillis", 101),
                (1, "returnedElapsedMillis", 111), (0, "requestedElapsedMillis", True),
                (1, "returnedElapsedMillis", "104")):
            report, files = fixture()
            report["navigationRequests"][index][key] = invalid
            with self.subTest(index=index, key=key), self.assertRaises(ValueError): self.validate(report, files)

    def test_navigation_uses_public_closed_actions_without_raw_keys_or_fallback(self):
        base = ROOT / "samples/p2p-sample-android/src"
        source = (base / "androidTest/java/dev/p2pkit/sample/android/runtime/LegacyTaskPreviewInstrumentation.kt").read_text()
        helper = (base / "runtimeValidation/kotlin/dev/p2pkit/sample/android/runtime/LegacyNavigation.kt").read_text()
        self.assertIn("HOME(AccessibilityService.GLOBAL_ACTION_HOME)", helper)
        self.assertIn("RECENTS(AccessibilityService.GLOBAL_ACTION_RECENTS)", helper)
        self.assertEqual(helper.count("perform(action.platformAction)"), 1)
        self.assertLess(helper.index("returned(accepted)"), helper.index("checkLegacyCapture(accepted"))
        self.assertEqual(source.count("uiAutomation.performGlobalAction(it)"), 1)
        for forbidden in ("KeyEvent", "injectInputEvent", "executeShellCommand", "moveTaskToBack", "ACTION_MAIN"):
            self.assertNotIn(forbidden, source)
        navigation = source.split("    private fun navigate(", 1)[1].split("    private fun <T> main(", 1)[0]
        self.assertLess(navigation.index("navigationRequests.put(request)"), navigation.index("requestLegacyNavigation("))
        self.assertIn('if (!request.has("returned"))', navigation)
        self.assertIn('"GLOBAL_ACTION_THROWN"', navigation)
        self.assertIn("throw error", navigation)
        self.assertIn('.put("navigationRequests", navigationRequests)', source)
        expected = ('stage = "home-request"', 'navigate(LegacyNavigationAction.HOME)', 'stage = "home-stopped"',
                    'await { main { first in stopped && !first.hasWindowFocus() } }', 'stage = "home-secure"',
                    'check(main { secure(first) })', 'stage = "recents-request"',
                    'navigate(LegacyNavigationAction.RECENTS)', 'stage = "actual-recents-original"')
        start = source.index(expected[0])
        for marker in expected:
            start = source.index(marker, start) + len(marker)
        self.assertIn("task.moveToFront()", source)
        self.assertIn("first.taskId == firstTask", source)
        self.assertIn("first.recreate()", source)
        self.assertIn("check(captures.length() == 7 && appObservations.size == 6)", source)
        self.assertEqual(legacy.DEFINITIONS["479"][2], 150)

    def test_successful_navigation_does_not_substitute_for_actual_outcomes(self):
        for missing in ("captures", "lifecycle", "cleanup"):
            report, files = fixture()
            report.pop(missing)
            with self.subTest(missing=missing), self.assertRaises(ValueError): self.validate(report, files)
        report, files = fixture()
        report["captures"][1]["pixelVariation"] = False
        with self.assertRaises(ValueError): self.validate(report, files)

    def test_missing_duplicate_reordered_captures_refused(self):
        for change in (lambda c: c.pop(), lambda c: c.append(c[0]), lambda c: c.reverse()):
            report, files = fixture()
            change(report["captures"])
            with self.assertRaises(ValueError):
                self.validate(report, files)

    def test_secure_leak_and_nonworking_positive_control_refused(self):
        for index in (0, 2, 3, 4, 5, 6):
            for key in ("sampleMatches", "secureFlag"):
                report, files = fixture()
                item = report["captures"][index]
                if key == "sampleMatches": item[key] = [not item[key][0]] * 4
                else: item["stateAfter"][key] = not item["stateAfter"][key]
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    self.validate(report, files)

    def test_unavailable_cannot_replace_required_images_or_invent_pixels(self):
        for index in (1, 4, 6):
            report, files = fixture(unavailable=True)
            item = report["captures"][index]
            files.pop(item["file"])
            for key in ("file", "width", "height", "sampleMatches", "sourceBitmapWidth",
                        "sourceBitmapHeight", "sourceBitmapConfig", "pixelReadback"):
                item.pop(key, None)
            item["observation"] = "UNAVAILABLE"
            with self.subTest(index=index), self.assertRaises(ValueError): self.validate(report, files)
        for key, value in (("file", "invented.png"), ("width", 16), ("sampleMatches", [False] * 4)):
            report, files = fixture(unavailable=True)
            report["captures"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(report, files)

    def test_before_after_owned_state_and_complete_bracket_required(self):
        for unavailable in (False, True):
            for index in (0, 2, 3, 4, 5, 6):
                for side in ("stateBefore", "stateAfter"):
                    for key, value in (("owned", False), ("viewAttached", False), ("windowFocused", False),
                                       ("viewDraws", 0), ("window", 999), ("view", 999),
                                       ("activity", 999), ("taskId", 999), ("viewWidth", 17),
                                       ("samplePoints", [[1, 1], [2, 2], [3, 3], [4, 4]])):
                        report, files = fixture(unavailable=unavailable)
                        report["captures"][index][side][key] = value
                        with self.subTest(index=index, side=side, key=key), self.assertRaises(ValueError):
                            self.validate(report, files)
        for key in ("window", "view", "viewWidth"):
            report, files = fixture(unavailable=True)
            for side in ("stateBefore", "stateAfter"): report["captures"][6][side][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(report, files)

    def test_blank_or_changed_system_window_and_unprotected_cleanup_fail(self):
        for change in ("uniform", "system-root", "app-focused", "wrong-task", "cleanup"):
            report, files = fixture(unavailable=True)
            recents = report["captures"][1]
            if change == "uniform": recents["pixelVariation"] = False
            elif change == "system-root": recents["systemWindowAfter"]["windowId"] += 1
            elif change == "app-focused": recents["systemWindowBefore"]["windowFocused"] = True
            elif change == "wrong-task": recents["systemWindowBefore"]["taskId"] += 1
            else: report["lifecycle"][-1]["secureFlag"] = False
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate(report, files)

    def test_original_png_inventory_required(self):
        for variant in ("absent", "unknown", "not-png"):
            report, files = fixture()
            if variant == "absent":
                files.pop("actual-recents-original.png")
            elif variant == "unknown":
                files["unknown.txt"] = b"not admitted"
            else:
                files["actual-recents-original.png"] = b"not an image"
            with self.assertRaises(ValueError):
                self.validate(report, files)

    def test_corrupt_truncated_wrong_geometry_and_trailing_png_refused(self):
        valid = synthetic_png()
        for raw in (valid[:8], valid[:-1], valid + b"trailing", valid[:45] + bytes([valid[45] ^ 1]) + valid[46:]):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                legacy.validate_png(raw, 16, 16)
        with self.assertRaises(ValueError):
            legacy.validate_png(valid, 17, 16)

    def test_wrong_task_unretired_or_no_recreation_refused(self):
        for variant in ("wrong-task", "missing-destroy", "foreign-destroy", "no-stop"):
            report, files = fixture()
            if variant == "wrong-task":
                report["lifecycle"][1]["taskId"] = 8
            elif variant == "missing-destroy":
                report["lifecycle"].pop()
            elif variant == "foreign-destroy":
                report["lifecycle"][-1]["activity"] = 9
            else:
                report["lifecycle"] = [x for x in report["lifecycle"] if x["event"] != "stopped"]
            with self.assertRaises(ValueError):
                self.validate(report, files)

    def test_exact_completed_terminal_and_unchanged_modern_selection(self):
        legacy.owner.instrumentation_result(terminal(), "479", TOKEN, definitions=legacy.DEFINITIONS)
        self.assertEqual(set(legacy.owner.CASES), {"317", "324"})
        for key, value in (("p2pkitOutcome", "FAIL"), ("p2pkitToken", "d" * 32),
                           ("test", "foreign"), ("p2pkitEvidence", "foreign")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                legacy.owner.instrumentation_result(terminal({key: value}), "479", TOKEN,
                                                   definitions=legacy.DEFINITIONS)
        for raw in (b"", terminal() + terminal(), terminal().replace(b"INSTRUMENTATION_CODE: -1", b"")):
            with self.assertRaises(ValueError):
                legacy.owner.instrumentation_result(raw, "479", TOKEN, definitions=legacy.DEFINITIONS)

    def test_explicit_installed_image_api_abi_revision(self):
        for api in (24, 32):
            campaign = legacy.LegacyCampaign(api)
            for invalid in (None, "api", "abi", "revision", "duplicate"):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    image = root / campaign.IMAGE.replace(";", "/")
                    image.mkdir(parents=True)
                    fields = {"AndroidVersion.ApiLevel": str(api), "SystemImage.Abi": "x86_64", "Pkg.Revision": "8"}
                    if invalid == "api": fields["AndroidVersion.ApiLevel"] = "35"
                    if invalid == "abi": fields["SystemImage.Abi"] = "arm64-v8a"
                    if invalid == "revision": fields.pop("Pkg.Revision")
                    raw = "\n".join(f"{k}={v}" for k, v in fields.items())
                    if invalid == "duplicate": raw += "\nPkg.Revision=8"
                    (image / "source.properties").write_text(raw)
                    if invalid:
                        with self.assertRaises(ValueError):
                            campaign.prepare_emulator(run=None, sdk=root, report=root)
                    else:
                        self.assertEqual(campaign.prepare_emulator(run=None, sdk=root, report=root), ())
        with self.assertRaises(ValueError): legacy.LegacyCampaign(35)

    def test_manual_only_workflow_reuses_exact_caller_and_does_not_qualify(self):
        workflow = (ROOT / ".github/workflows/android-legacy-task-preview.yml").read_text()
        main = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("workflow_call:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("  push:", workflow)
        for api, image in legacy.IMAGES.items():
            self.assertIn(f"api: {api}", workflow)
            self.assertIn(f"image: {image}", workflow)
        self.assertIn("retention-days: 14", workflow)
        self.assertIn("--report-glob 'build/reports/android-legacy-task-preview-api*/**/*'", workflow)
        self.assertIn("uses: ./.github/workflows/android-legacy-task-preview.yml", main)
        self.assertEqual(main.count("inputs.component != 'android-legacy-task-preview'"), 4)


class LegacySdkInstallTests(unittest.TestCase):
    def install_body(self):
        workflow = (ROOT / ".github/workflows/android-legacy-task-preview.yml").read_text()
        parts = workflow.split("      - name: Install producer NDK and explicit legacy witness image\n")
        self.assertEqual(len(parts), 2)
        step = parts[1].split("      - name:", 1)[0]
        self.assertIn("timeout-minutes: 12", [line.strip() for line in step.splitlines()])
        self.assertIn("WITNESS_IMAGE: ${{ matrix.image }}", step)
        _, body = step.split("        run: |\n")
        return textwrap.dedent(body)

    def run_install(self, *, api=32, sdk_status=0, prompts=3):
        # Exercise the checked-in Bash body, not a reimplementation. Only the
        # SDK command is synthetic; the feeder runs the real yes and records
        # its exit so a genuine SIGPIPE cannot be mistaken for SDK failure.
        bash, yes = shutil.which("bash"), shutil.which("yes")
        self.assertIsNotNone(bash)
        self.assertIsNotNone(yes)
        body = self.install_body()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "android sdk"
            manager = sdk / "cmdline-tools/latest/bin/sdkmanager"
            manager.parent.mkdir(parents=True)
            manager.write_text(f"#!{sys.executable}\n" + textwrap.dedent("""\
                import json, os, sys
                answers = [sys.stdin.readline() for _ in range(int(os.environ["SDK_PROMPTS"]))]
                with open(os.environ["SDK_CALLS"], "a") as output:
                    output.write(json.dumps({"argv": sys.argv[1:], "answers": answers}) + "\\n")
                sys.exit(int(os.environ["SDK_STATUS"]) if all(a == "y\\n" for a in answers) else 66)
                """))
            manager.chmod(0o700)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            feeder = bin_dir / "yes"
            feeder.write_text(f"#!{bash}\n" + textwrap.dedent("""\
                "$REAL_YES" "$@"
                status=$?
                printf '%s\\n' "$status" > "$FEEDER_STATUS"
                exit "$status"
                """))
            feeder.chmod(0o700)
            calls, feeder_status = root / "sdk-calls.jsonl", root / "feeder-status"
            env = dict(PATH=str(bin_dir), ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk),
                       WITNESS_IMAGE=legacy.IMAGES[api], REAL_YES=yes, FEEDER_STATUS=str(feeder_status),
                       SDK_CALLS=str(calls), SDK_STATUS=str(sdk_status), SDK_PROMPTS=str(prompts))
            process = subprocess.Popen([bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", body],
                                       env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = process.communicate(b"", timeout=5)
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate(timeout=5)
                raise
            self.assertEqual(process.returncode, sdk_status, (stdout, stderr))
            self.assertEqual(int(feeder_status.read_text()), 128 + signal.SIGPIPE)
            self.assertEqual([json.loads(line) for line in calls.read_text().splitlines()], [dict(
                argv=["platforms;android-36", "platforms;android-37.0", "ndk;29.0.14206865",
                      "platform-tools", "emulator", legacy.IMAGES[api]],
                answers=["y\n"] * prompts)])

    def test_license_prompts_accept_only_the_exact_requested_installation(self):
        for api in (24, 32):
            with self.subTest(api=api):
                self.run_install(api=api)

    def test_sdk_failure_is_not_hidden_by_feeder_sigpipe(self):
        for status in (1, 37, 124):
            with self.subTest(status=status):
                self.run_install(sdk_status=status)

    def test_success_without_prompts_survives_real_yes_sigpipe(self):
        self.run_install(prompts=0)


if __name__ == "__main__":
    unittest.main(failfast=True)
