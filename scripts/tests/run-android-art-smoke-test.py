#!/usr/bin/env python3
"""Pure fixture controls for the ART driver's metadata/UI/ZIP admissions.

No SDK download, adb invocation, emulator, Gradle or product execution. The real
native process-ownership implementation is reused, not copied or simulated here.
"""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import warnings
import zipfile

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("android_art", SCRIPTS / "run-android-art-smoke.py")
art = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(art)


def image_manifest():
    return (f'<repository><remotePackage path="{art.IMAGE}"><type-details><api-level>37.0</api-level>'
            '<extension-level>22</extension-level><abi>x86_64</abi></type-details><revision><major>6</major></revision>'
            '<channelRef ref="channel-0"/><dependencies><dependency path="emulator"><min-revision>'
            '<major>36</major><minor>5</minor><micro>11</micro></min-revision></dependency></dependencies>'
            '<archives><archive><complete><size>2234615040</size><checksum type="sha1">'
            '629e507fd5b737c2c836b12b52c81cd0e3b12399</checksum><url>x86_64-37.0_r06.zip</url>'
            '</complete></archive></archives></remotePackage></repository>').encode()


def ui(label="Start", package=art.PACKAGE):
    return (f'<hierarchy rotation="0"><node package="{package}" enabled="true" clickable="true">'
            f'<node package="{package}" enabled="true" clickable="false" text="{label}" '
            'bounds="[20,40][120,80]"/></node></hierarchy>').encode()


COMMIT = "a" * 40
SESSION = "11111111-2222-3333-4444-555555555555"
ZIP_NAME = f"PS-T04_android_2026-09-10T120001_{SESSION}.zip"
OLD_IMAGE_PINS = {
    24: (8, 0, 0, 419261998, "f6559e1949a5879f31a9662f4f0e50ad60181684", "x86_64-24_r08.zip"),
    25: (1, 0, 0, 422702097, "7093d7b39216020226ff430a3b7b81c94d31ad37", "x86_64-25_r01.zip")}


def old_image_manifest(api):
    major, _, _, size, checksum, name = OLD_IMAGE_PINS[api]
    return (f'<repository><remotePackage path="{art.IMAGES[api]}"><type-details><api-level>{api}</api-level>'
            '<tag><id>default</id></tag><abi>x86_64</abi></type-details>'
            f'<revision><major>{major}</major></revision><channelRef ref="channel-0"/>'
            f'<archives><archive><complete><size>{size}</size><checksum type="sha1">{checksum}</checksum>'
            f'<url>{name}</url></complete></archive></archives></remotePackage></repository>').encode()


def event(index, name, details=None):
    return {"schemaVersion": 1, "index": index, "timestamp": f"2026-09-10T12:00:{index:02d}Z",
            "platform": "android", "operatingSystem": "Android 7.0 (API 24)", "gitCommitSha": COMMIT,
            "testSessionId": SESSION, "testId": "PS-T04", "role": "both", "eventName": name,
            "severity": "INFO", "details": details or {}}


def export_bytes(events, extra=None, summary_change=None, manifest_change=None, duplicate=False):
    summary = {key: events[0][key] for key in
               ("schemaVersion", "gitCommitSha", "platform", "operatingSystem", "testId", "testSessionId", "role")}
    summary.update(startTimestamp=events[0]["timestamp"], endTimestamp=events[-1]["timestamp"], eventCount=len(events),
                   warningCount=0, errorCount=0, droppedEventCount=0, finalOutcome=None)
    summary.update(summary_change or {})
    contents = {"events.jsonl": b"".join(json.dumps(e).encode() + b"\n" for e in events),
                "events.txt": b"fixture only\n", "summary.json": json.dumps(summary).encode(),
                "manual-evidence-required.txt": b"No fixture is native evidence.\n", **(extra or {})}
    manifest = b"".join(hashlib.sha256(value).hexdigest().encode() + b"  " + name.encode() + b"\n"
                        for name, value in contents.items())
    contents["checksums.sha256"] = manifest_change(manifest) if manifest_change else manifest
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)  # Deliberately malformed pure fixture.
                archive.writestr("events.txt", contents["events.txt"])
    return output.getvalue()


def instrumentation_output(changes=None):
    token, pin = "1" * 32, "p2f1-" + "a" * 52
    result = {"p2pkitToken": token, "p2pkitOutcome": "PASS", "p2pkitCompleted": "1",
              "p2pkitRecreation": "PASS", "p2pkitRequestSettled": "true",
              "p2pkitManager": "PASS", "p2pkitTraffic": "PASS", "p2pkitCleanup": "PASS",
              "p2pkitRawPregrant": "DENIED", "p2pkitRawRoute": "DENIED_THEN_ADMITTED",
              "p2pkitRawDenialType": "TCP_TIMEOUT", "p2pkitSameInstanceRevocation": "NOT_EXECUTED",
              "p2pkitRetainedVm": "true", "p2pkitActivities": "2", "p2pkitDestroyed": "1",
              "p2pkitPeerFingerprint": pin, "p2pkitLocalAlias": "anon-" + "c" * 16,
              "p2pkitSentBytes": "40", "p2pkitReceivedBytes": "36", "p2pkitPid": "123",
              "p2pkitProcessStart": "456", "p2pkitUid": "10101", "p2pkitNetwork": "4294967296"}
    result.update(changes or {})
    identity = {"class": art.INSTRUMENTATION, "test": "permissionRecreationAndPinnedTcp", "numtests": "1", "current": "1"}
    lines = []

    def status(code, fields):
        lines.extend("INSTRUMENTATION_STATUS: " + key + "=" + value for key, value in fields.items())
        lines.append("INSTRUMENTATION_STATUS_CODE: " + str(code))

    status(1, {**identity, "p2pkitToken": token})
    for phase in ("default-manager-denied", "raw-denied", "request-outstanding", "recreated-still-outstanding",
                  "same-manager-granted-no-replay", "raw-granted", "message-sent", "bidirectional-delivery"):
        status(2, {**identity, "p2pkitToken": token, "p2pkitPhase": phase})
    status(0, {**identity, **result})
    lines.extend("INSTRUMENTATION_RESULT: " + key + "=" + value for key, value in result.items())
    lines.append("INSTRUMENTATION_CODE: -1")
    return ("\n".join(lines) + "\n").encode(), token, pin


class AndroidArtAdmissionTest(unittest.TestCase):
    def test_instrumentation_requires_completed_real_scopes_and_matching_delivery(self):
        raw, token, pin = instrumentation_output()
        self.assertEqual(art.instrumentation_result(raw, token, pin)["p2pkitOutcome"], "PASS")
        for changes in ({"p2pkitCompleted": "0"}, {"p2pkitOutcome": "FAIL"}, {"p2pkitCleanup": "FAIL"},
                        {"p2pkitRawRoute": "PREGRANT_BYPASS"}, {"p2pkitRetainedVm": "false"},
                        {"p2pkitManager": "NOT_RUN"}, {"p2pkitRequestSettled": "false"},
                        {"p2pkitActivities": "1"}, {"p2pkitReceivedBytes": "35"},
                        {"p2pkitPeerFingerprint": "p2f1-" + "b" * 52}, {"p2pkitSameInstanceRevocation": "PASS"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                art.instrumentation_result(instrumentation_output(changes)[0], token, pin)

    def test_instrumentation_exit_zero_partial_crash_duplicate_or_impostor_are_not_success(self):
        raw, token, pin = instrumentation_output()
        for bad in (b"INSTRUMENTATION_CODE: 0\n", raw.rsplit(b"INSTRUMENTATION_CODE:", 1)[0],
                    raw.replace(b"INSTRUMENTATION_STATUS_CODE: 0", b"INSTRUMENTATION_STATUS_CODE: -2"),
                    raw.replace(b"p2pkitPhase=request-outstanding", b"p2pkitPhase=already-granted"),
                    raw.replace(b"INSTRUMENTATION_RESULT: p2pkitRequestSettled=true\n", b""),
                    raw.replace(art.INSTRUMENTATION.encode(), b"unrelated.Runner"),
                    raw + b"INSTRUMENTATION_RESULT: p2pkitCompleted=1\n",
                    raw.replace(b"INSTRUMENTATION_CODE: -1", b"INSTRUMENTATION_CODE: 0")):
            with self.subTest(malformed=bad[-100:]), self.assertRaises(ValueError):
                art.instrumentation_result(bad, token, pin)

    def test_final_runtime_host_admission_rejects_late_output_control_and_cli_failures(self):
        alias = "anon-" + "c" * 16
        lines = [f"incoming from {alias}: <text 40B>",
                 "sending <text 36B> to 1 peer(s) (local send, not remote processing)"]
        control = {"controlAccepts": 1, "controlChallenges": 1, "controlEmptyConnections": 0}
        good = {"lines": lines, "alias": alias, "control": control, "output_eof": True, "unresolved_clients": 0}
        self.assertEqual(art.runtime_host_result(**good)["status"], "PASS")
        for changes in ({"lines": lines + [lines[0]]}, {"lines": lines + [lines[1]]}, {"lines": lines[:1]},
                        {"output_eof": False}, {"unresolved_clients": 1}, {"alias": None},
                        {"control": {**control, "controlAccepts": 2}},
                        {"control": {**control, "controlChallenges": 0}},
                        {"control": {**control, "controlEmptyConnections": 1}}):
            with self.subTest(changes=changes):
                self.assertEqual(art.runtime_host_result(**{**good, **changes})["status"], "FAIL")
        for problem in ("kit.stop() failed: IOException", f"send to {alias} failed: IOException",
                        f"[p2pkit WARN] auto-mesh connect to {alias} failed: IOException", "[p2pkit W] SDK event",
                        "[p2pkit E] SDK event", "[p2pkit ERROR] invalid option", "CLI failed: IOException",
                        'Exception in thread "main" java.lang.IllegalStateException'):
            with self.subTest(problem=problem):
                final = art.runtime_host_result(**{**good, "lines": lines + [problem]})
                self.assertEqual(final["status"], "FAIL")
                self.assertEqual(final["cliProblems"], [problem])

    def test_old_api_stop_return_requires_enabled_start_without_cleanup_or_room(self):
        good = ui()
        self.assertTrue(art.old_api_stop_returned(good))
        for pending in (b"<hierarchy/>", ui(package="unrelated.app"),
                        good.replace(b'enabled="true"', b'enabled="false"', 1),
                        good.replace(b'package="dev.p2pkit.sample.android"', b'package="unrelated.app"', 1)):
            with self.subTest(pending=pending):
                self.assertFalse(art.old_api_stop_returned(pending))
        for label in ("Starting…", "Stopping previous run…", "Stopping…", "state: Running", "Kit options"):
            extra = ui(label).split(b">", 1)[1]
            with self.subTest(label=label):
                self.assertFalse(art.old_api_stop_returned(good.replace(b"</hierarchy>", extra)))
        options = ui("Kit options").replace(b'text=', b'content-desc=').split(b">", 1)[1]
        self.assertFalse(art.old_api_stop_returned(good.replace(b"</hierarchy>", options)))
        for invalid in (good.replace(b"</hierarchy>", ui("Retry cleanup").split(b">", 1)[1]),
                        good.replace(b"</hierarchy>", good.split(b">", 1)[1]),
                        good.replace(b"[120,80]", b"[5000,80]")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                art.old_api_stop_returned(invalid)

    def test_old_api_jmdns_requires_ordered_same_session_observations_and_clean_logs(self):
        for api in (24, 25):
            def record(index, name, state=None):
                value = event(index, name)
                value["operatingSystem"] = f"Android 7.{int(api == 25)} (API {api})"
                if state is not None:
                    value["currentState"] = state
                return value

            before = [record(1, "application.started"), record(2, "test.session.created"),
                      record(3, "test.mode.activated"), record(4, "evidence.exported"),
                      record(5, "application.backgrounded"), record(6, "application.foregrounded"),
                      record(7, "evidence.exported")]
            before[0].update(testSessionId="session-unassigned", testId="UNASSIGNED", role="unspecified")
            started = before + [record(8, "discovery.started", "advertising"),
                                record(9, "discovery.started", "discovering")]
            before_stop = started + [record(10, "network.path.changed")]
            stopped = before_stop + [record(11, "application.shutdown", "stopping"),
                                     record(12, "discovery.stopped", "stopping")]
            running = ui("state: Running").replace(b"</hierarchy>", ui("online").split(b">", 1)[1])
            good = {"baseline": before, "before": before, "started": started,
                    "beforeStop": before_stop, "stopped": stopped,
                    "runningUi": running, "stoppedUi": ui(), "logcat": "D/P2pKitLAN( 123): closed\n"}
            admitted = art.verify_old_api_jmdns(good, COMMIT, api, SESSION)
            self.assertTrue(admitted["runningOnlineObserved"])
            self.assertTrue(admitted["stopReturnedViaEnabledStart"])
            self.assertEqual(admitted["transitionIndexes"], [8, 9, 11, 12])

            def reject(label, bad):
                with self.subTest(api=api, malformed=label), self.assertRaises(ValueError):
                    art.verify_old_api_jmdns(bad, COMMIT, api, SESSION)

            for label, changes in (
                    ("missing-running", {"runningUi": ui("online")}),
                    ("missing-online", {"runningUi": ui("state: Running")}),
                    ("missing-start", {"stoppedUi": b"<hierarchy/>"}),
                    ("disabled-start", {"stoppedUi": ui().replace(b'enabled="true"', b'enabled="false"', 1)}),
                    ("retry-cleanup", {"stoppedUi": ui("Retry cleanup")}),
                    ("shutdown-only", {"stopped": stopped[:-1]}),
                    ("no-stop", {"stopped": before_stop}),
                    ("missing-discovery", {"started": started[:-1]}),
                    ("early-stop", {"beforeStop": stopped}),
                    ("lost-unassigned-prefix", {"stopped": stopped[1:]}),
                    ("duplicate-stop", {"stopped": stopped + [record(13, "discovery.stopped", "stopping")]}),
                    ("extra-start", {"stopped": stopped + [record(13, "discovery.started", "advertising")]})):
                reject(label, {**good, **changes})
            bad = copy.deepcopy(good)
            bad["stopped"][0] = {**bad["stopped"][0], "details": {"changed": "true"}}
            reject("changed-unassigned-prefix", bad)
            for label, position, changes in (
                    ("duplicate-start", 7, {"currentState": "discovering"}),
                    ("missing-advertising", 7, {"eventName": "network.path.changed"}),
                    ("start-before-marker", 7, {"index": 7}),
                    ("reset-index", 10, {"index": 1}),
                    ("duplicate-stop-name", 10, {"eventName": "discovery.stopped"}),
                    ("wrong-state", 11, {"currentState": "advertising"}),
                    ("wrong-source", 10, {"gitCommitSha": "b" * 40}),
                    ("wrong-api", 10, {"operatingSystem": "Android 8.0 (API 26)"}),
                    ("wrong-session", 10, {"testSessionId": "different-session"}),
                    ("unassigned-warning", 0, {"severity": "WARNING"}),
                    ("late-warning", 11, {"severity": "WARNING"}),
                    ("late-error", 11, {"severity": "ERROR"})):
                bad = copy.deepcopy(good)
                bad["stopped"][position].update(changes)
                reject(label, bad)
            for first, second, field in ((7, 8, "currentState"), (10, 11, "eventName")):
                bad = copy.deepcopy(good)
                a, b = bad["stopped"][first], bad["stopped"][second]
                a[field], b[field] = b[field], a[field]
                reject("reversed-transition-order", bad)
            bad = copy.deepcopy(good)
            bad["baseline"] = bad["baseline"][:4]
            bad["before"][4].update(eventName="application.started", testSessionId="session-unassigned",
                                    testId="UNASSIGNED", role="unspecified")
            reject("unassigned-restart-during-Room-navigation", bad)
            for key in ("runningUi", "stoppedUi", "logcat"):
                bad = {**good}
                del bad[key]
                reject("missing-" + key, bad)
            for name in ("application.started", "test.session.created"):
                for session in (SESSION, "session-unassigned"):
                    restart = record(13, name)
                    restart["testSessionId"] = session
                    reject(name + "/" + session, {**good, "stopped": stopped + [restart]})
            for line in ("W/P2pKitLAN( 123): native cleanup warning",
                         "E/p2pkit( 123): kit.stop failed; ownership retained",
                         "E/AndroidRuntime( 123): FATAL EXCEPTION: main",
                         "F/AndroidRuntime( 123): native failure"):
                reject(line, {**good, "logcat": good["logcat"] + line + "\n"})
            for wrong_api in (26, 37):
                with self.subTest(wrong_api=wrong_api), self.assertRaises(ValueError):
                    art.verify_old_api_jmdns(good, COMMIT, wrong_api, SESSION)

    def test_old_api_jmdns_result_requires_both_expected_old_apis_and_completed_scopes(self):
        good = [{"api": api, "status": "PASS",
                 "oldApiJmdnsLifecycle": "NOT_APPLICABLE" if api == 37 else "PASS"} for api in (37, 24, 25)]
        self.assertEqual(art.old_api_jmdns_status(good), "PASS")
        for bad in ([], good[:1], good[:2], good[1:], good + [good[-1]],
                    [good[0], good[1], good[1]], [good[0], good[2], good[1]], None):
            with self.subTest(scenarios=bad):
                self.assertEqual(art.old_api_jmdns_status(bad), "FAIL")
        for index in (0, 1, 2):
            bad = copy.deepcopy(good)
            del bad[index]["oldApiJmdnsLifecycle"]
            self.assertEqual(art.old_api_jmdns_status(bad), "FAIL")
            for status in ("NOT_RUN", "RUNNING", "FAIL", None, False,
                           "PASS" if index == 0 else "NOT_APPLICABLE"):
                bad = copy.deepcopy(good)
                bad[index]["oldApiJmdnsLifecycle"] = status
                with self.subTest(index=index, status=status):
                    self.assertEqual(art.old_api_jmdns_status(bad), "FAIL")
            bad = copy.deepcopy(good)
            bad[index]["status"] = "FAIL"  # Cleanup failure cannot be rescued by the phase field.
            self.assertEqual(art.old_api_jmdns_status(bad), "FAIL")
        for value in (26, 24.0, "24", True):
            bad = copy.deepcopy(good)
            bad[1]["api"] = value
            with self.subTest(api=value):
                self.assertEqual(art.old_api_jmdns_status(bad), "FAIL")

    def test_exact_stable_api37_pin_accepts_and_changed_artifact_or_platform_fails(self):
        good = image_manifest()
        self.assertEqual(art.package_pin(good, art.IMAGE)["archiveBytes"], 2234615040)
        for before, after in ((b"37.0</api", b"36.0</api"), (b"x86_64</abi", b"arm64-v8a</abi"),
                              (b"<major>6</major>", b"<major>7</major>"), (b"channel-0", b"channel-1"),
                              (b"2234615040", b"2234615041"), (b"629e507f", b"629e5070"),
                              (b"r06.zip", b"r07.zip"), (b"<micro>11", b"<micro>12"),
                              (b"<extension-level>22", b"<extension-level>21")):
            with self.subTest(change=(before, after)), self.assertRaises(ValueError):
                art.package_pin(good.replace(before, after), art.IMAGE)

    def test_real_user0_runtime_grant_is_not_manifest_presence_or_other_user_grant(self):
        text = (f' requested permissions:\n  {art.PERMISSION}\n User 0: installed=true\n'
                f'  runtime permissions:\n   {art.PERMISSION}: granted=false, flags=[]\n'
                f' User 10: installed=true\n   {art.PERMISSION}: granted=true, flags=[]\n')
        self.assertFalse(art.grant_from_dump(text, art.PERMISSION))
        self.assertTrue(art.grant_from_dump(text.replace("granted=false", "granted=true"), art.PERMISSION))
        for malformed in (text.replace("User 0:", "User 1:"), text.replace("granted=false", "granted=unknown"),
                          text.replace("  runtime permissions:", f"   {art.PERMISSION}: granted=true, flags=[]")):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                art.grant_from_dump(malformed, art.PERMISSION)

    def test_only_one_enabled_app_owned_click_target_is_admitted(self):
        good = ui()
        self.assertEqual(art.select_node(good, "Start"), [70, 60])
        child = b'<node package="dev.p2pkit.sample.android" enabled="true" text="Start" bounds="[20,40][120,80]"/>'
        for malformed in (ui(package="unrelated.app"), good.replace(b'enabled="true"', b'enabled="false"', 1),
                          good.replace(b'[120,80]', b'[5000,80]'), good.replace(b'</hierarchy>', child + b'</hierarchy>'),
                          b'<!DOCTYPE hierarchy><hierarchy/>'):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                art.select_node(malformed, "Start")

    def test_scroll_stays_inside_unique_enabled_app_container(self):
        good = (b'<hierarchy><node package="dev.p2pkit.sample.android" enabled="true" scrollable="true" '
                b'bounds="[0,100][1080,900]"/></hierarchy>')
        self.assertEqual(art.scroll_points(good), [540, 700, 540, 300, 250])
        for malformed in (good.replace(art.PACKAGE.encode(), b"unrelated.app"),
                          good.replace(b'enabled="true"', b'enabled="false"'),
                          good.replace(b'[1080,900]', b'[1080,9000]'),
                          good.replace(b'</hierarchy>', good.split(b'<hierarchy>')[1])):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                art.scroll_points(malformed)

    def test_system_permission_button_cannot_be_spoofed_by_sample_text(self):
        good = (b'<hierarchy><node package="com.google.android.permissioncontroller" enabled="true" clickable="true" '
                b'resource-id="com.google.android.permissioncontroller:id/permission_allow_button" '
                b'bounds="[20,40][120,80]"/></hierarchy>')
        self.assertEqual(art.select_node(good, "permission_allow_button", system=True), [70, 60])
        with self.assertRaises(ValueError):
            art.select_node(ui(label="permission_allow_button"), "permission_allow_button", system=True)

    def test_old_api_pins_admit_both_exact_archives_and_reject_platform_or_artifact_drift(self):
        for api in (24, 25):
            good = old_image_manifest(api)
            pin = OLD_IMAGE_PINS[api]
            self.assertEqual(art.package_pin(good, art.IMAGES[api])["publisherSha1"], pin[4])
            for before, after in ((f"{api}</api".encode(), b"26</api"), (b"x86_64</abi", b"x86</abi"),
                                  (b"default</id", b"google_apis</id"), (b"channel-0", b"channel-1"),
                                  (str(pin[3]).encode(), b"1"), (pin[4].encode(), b"0" * 40),
                                  (pin[5].encode(), b"different.zip"),
                                  (f"<major>{pin[0]}</major>".encode(), b"<major>99</major>")):
                with self.subTest(api=api, change=before), self.assertRaises(ValueError):
                    art.package_pin(good.replace(before, after), art.IMAGES[api])

    def test_zip_names_manifest_correspondence_and_inflated_byte_bounds_fail_closed(self):
        events = [event(1, "test.session.created"), event(2, "test.mode.activated")]
        inspected = art.inspect_export(export_bytes(events), ZIP_NAME, COMMIT, 24, SESSION)
        self.assertEqual(inspected["events"], events)
        for parameters in ({"extra": {"../outside": b"x"}}, {"extra": {"directory/": b""}}, {"duplicate": True},
                           {"extra": {"oversized.log": b"x" * (2 * 1024 * 1024 + 1)}},
                           {"manifest_change": lambda raw: raw + raw.splitlines(keepends=True)[0]},
                           {"manifest_change": lambda raw: raw.replace(b"events.txt", b"absent.txt")},
                           {"manifest_change": lambda raw: b"0" * 64 + raw[64:]},
                           {"manifest_change": lambda raw: raw.replace(b"  ", b" ", 1)},
                           {"summary_change": {"droppedEventCount": 1}}, {"summary_change": {"eventCount": 3}}):
            with self.subTest(parameters=list(parameters)), self.assertRaises(ValueError):
                art.inspect_export(export_bytes(events, **parameters), ZIP_NAME, COMMIT, 24, SESSION)
        for commit, api, session, name in (("b" * 40, 24, SESSION, ZIP_NAME), (COMMIT, 25, SESSION, ZIP_NAME),
                                           (COMMIT, 24, "other-session", ZIP_NAME),
                                           (COMMIT, 24, SESSION, ZIP_NAME.replace("2026-09-10T120001", "1970-01-01T000000"))):
            with self.subTest(context=(commit, api, session, name)), self.assertRaises(ValueError):
                art.inspect_export(export_bytes(events), name, commit, api, session)

    def test_repeated_export_requires_preserved_events_new_lifecycle_and_both_actual_zip_hashes(self):
        before = [event(1, "test.session.created"), event(2, "test.mode.activated")]
        first = art.inspect_export(export_bytes(before), ZIP_NAME, COMMIT, 24, SESSION)
        after = before + [event(3, "evidence.exported", {"packageSha256": first["sha256"]}),
                          event(4, "application.backgrounded"), event(5, "application.foregrounded")]
        second = art.inspect_export(export_bytes(after), ZIP_NAME, COMMIT, 24, SESSION)
        live = after + [event(6, "evidence.exported", {"packageSha256": second["sha256"]})]
        art.verify_repeated(first, second, live, 5)
        for fault in ("same-hash", "different-name", "lost-prefix", "wrong-first-hash", "wrong-second-hash", "wrong-marker"):
            changed, current, marker = copy.deepcopy(second), copy.deepcopy(live), 5
            if fault == "same-hash":
                changed["sha256"] = first["sha256"]
            elif fault == "different-name":
                changed["name"] = "different.zip"
            elif fault == "lost-prefix":
                changed["events"] = changed["events"][1:]
            elif fault == "wrong-first-hash":
                changed["events"][2]["details"]["packageSha256"] = "0" * 64
                current[2]["details"]["packageSha256"] = "0" * 64
            elif fault == "wrong-second-hash":
                current[-1]["details"]["packageSha256"] = "0" * 64
            else:
                marker = 4
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                art.verify_repeated(first, changed, current, marker)
        restarted = after + [event(1, "application.foregrounded")]
        with self.assertRaises(ValueError):
            art.checked_session(restarted, COMMIT, 24, SESSION)

    def test_back_requires_an_observed_system_chooser_not_sample_or_unrelated_activity(self):
        old = "mResumedActivity: ActivityRecord{123 u0 android/com.android.internal.app.ChooserActivity t1}"
        modern = "topResumedActivity=ActivityRecord{123 u0 com.android.intentresolver/.ChooserActivity t1}"
        self.assertEqual(art.foreground_chooser(old), "android")
        self.assertEqual(art.foreground_chooser(modern), "com.android.intentresolver")
        self.assertIsNone(art.foreground_chooser("mResumedActivity: ActivityRecord{123 u0 " + art.PACKAGE + "/.MainActivity t1}"))
        self.assertIsNone(art.foreground_chooser(old.replace("android/com.android.internal.app", "unrelated.app")))
        with self.assertRaises(ValueError):
            art.foreground_chooser(old + "\n" + modern)


if __name__ == "__main__":
    unittest.main()
