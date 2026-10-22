#!/usr/bin/env python3
"""Offline identity/completion and install-shell controls; never Android execution evidence."""
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


def synthetic_png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(b"\0\0\0\0")) + chunk(b"IEND", b""))


def fixture(api=24):
    captures = []
    for name in legacy.CAPTURES:
        item = dict(name=name, file=name + ".png", width=1, height=1)
        if name != "actual-recents-original":
            visible = name == "synthetic-unprotected-positive-control"
            item.update(sampleMatches=[visible] * 4, secureFlag=not visible)
        captures.append(item)
    report = dict(case="479", token=TOKEN, sourceCommit=SOURCE, declaredSourceTree=TREE,
        api=api, targetSdk=37, outcome=legacy.owner.PASS, syntheticOnly=True, recentsReviewRequired=True,
        cleanup="OWNED_ACTIVITIES_DESTROYED", taskId=7, captures=captures,
        lifecycle=[dict(event=event, activity=activity, taskId=7) for event, activity in
                   (("created", 1), ("stopped", 1), ("created", 2), ("destroyed", 1), ("destroyed", 2))])
    # Clearly synthetic parser inputs, not captured images or proof of visual privacy.
    files = {name + ".png": synthetic_png() for name in legacy.CAPTURES}
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
            report, files = fixture(api)
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

    def test_missing_duplicate_reordered_captures_refused(self):
        for change in (lambda c: c.pop(), lambda c: c.append(c[0]), lambda c: c.reverse()):
            report, files = fixture()
            change(report["captures"])
            with self.assertRaises(ValueError):
                self.validate(report, files)

    def test_secure_leak_and_nonworking_positive_control_refused(self):
        for index in (0, 2, 3, 4, 5):
            for key in ("sampleMatches", "secureFlag"):
                report, files = fixture()
                item = report["captures"][index]
                item[key] = [not item[key][0]] * 4 if key == "sampleMatches" else not item[key]
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    self.validate(report, files)

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
                legacy.validate_png(raw, 1, 1)
        with self.assertRaises(ValueError):
            legacy.validate_png(valid, 2, 1)

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
