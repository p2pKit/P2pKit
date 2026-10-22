#!/usr/bin/env python3
"""Real API24/32 secure-window/Recents witness; reuse the maintained owned UI runner.

No personal device, credential, RPC or physical/OEM qualification. Original
Recents images still require independent task-card/privacy review.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys
import uuid
import zlib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("legacy_ui_owner", ROOT / "scripts/run-android-ui-validation.py")
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
need = owner.need
PACKAGE = owner.PACKAGE
RUNNER = PACKAGE + ".runtime.LegacyTaskPreviewInstrumentation"
DEFINITIONS = {"479": (RUNNER, "legacyTaskPreviewPolicy", 150)}
IMAGES = {24: "system-images;android-24;default;x86_64",
          32: "system-images;android-32;google_apis;x86_64"}
CAPTURES = ("initial-secure-foreground", "actual-recents-original", "same-task-reentry",
            "real-activity-recreation", "synthetic-unprotected-positive-control",
            "reapplied-production-secure-policy", "synthetic-unprotected-closing-control")


def validate_png(raw, width, height):
    """Validate the retained PNG container; independent visual decoding is still required."""
    need(8 < len(raw) <= owner.LIMIT and raw[:8] == b"\x89PNG\r\n\x1a\n", "Not a bounded original PNG")
    offset, chunks, image_data = 8, 0, False
    while offset < len(raw):
        need(offset + 12 <= len(raw), "Truncated PNG chunk")
        length, kind = struct.unpack_from(">I4s", raw, offset)
        end = offset + length + 12
        need(end <= len(raw), "Truncated PNG payload")
        body = raw[offset + 8:end - 4]
        checksum = struct.unpack_from(">I", raw, end - 4)[0]
        need(zlib.crc32(kind + body) == checksum, "Corrupt PNG chunk")
        if chunks == 0:
            need(kind == b"IHDR" and length == 13 and
                 struct.unpack_from(">II", body) == (width, height), "Wrong PNG geometry")
        else:
            need(kind != b"IHDR", "Duplicate PNG header")
        image_data = image_data or (kind == b"IDAT" and length > 0)
        if kind == b"IEND":
            need(length == 0 and image_data and end == len(raw), "Incomplete or trailing PNG")
            return
        chunks += 1
        offset = end
    raise ValueError("Missing PNG end")


STATE_KEYS = {"activity", "window", "view", "taskId", "viewWidth", "viewHeight", "viewDraws",
              "samplePoints", "owned", "viewAttached", "windowFocused", "secureFlag"}
POSITIVE = {"synthetic-unprotected-positive-control", "synthetic-unprotected-closing-control"}


def state_binding(state):
    return tuple(state[key] for key in ("activity", "window", "view", "taskId", "viewWidth", "viewHeight", "samplePoints"))


def validate_state(state, *, secure, activity, task):
    need(isinstance(state, dict) and set(state) == STATE_KEYS, "Missing exact capture state")
    for key in ("activity", "window", "view", "taskId", "viewWidth", "viewHeight", "viewDraws"):
        need(type(state[key]) is int, "Invalid capture state scalar")
    need(state["activity"] == activity and state["taskId"] == task and task >= 0 and
         state["viewWidth"] > 0 and state["viewHeight"] > 0 and state["viewDraws"] > 0 and
         state["owned"] is True and state["viewAttached"] is True and state["windowFocused"] is True and
         state["secureFlag"] is secure, "Capture window ownership or state changed")
    points = state["samplePoints"]
    need(isinstance(points, list) and len(points) == 4 and
         all(isinstance(point, list) and len(point) == 2 and
             all(type(coordinate) is int and coordinate >= 0 for coordinate in point) for point in points) and
         len({tuple(point) for point in points}) == 4, "Invalid synthetic sample geometry")



def validate_presentation(item, state):
    receipt = item.get("presentation")
    need(isinstance(receipt, dict) and set(receipt) ==
         {"startedElapsedMillis", "deadlineElapsedMillis", "completedElapsedMillis", "budgetMillis", "operation",
          "root", "baselineDraws", "clearReturned", "invalidatedNano", "polls", "frameCount", "observedDraws",
          "queriedNano", "frameIndex", "postedNano", "readyNano", "presentedNano", "lastRootGuard", "eventIdle"},
         "Missing exact bounded presentation observation")
    for key in set(receipt) - {"operation", "root", "clearReturned", "lastRootGuard", "eventIdle"}:
        need(type(receipt[key]) is int, "Invalid presentation scalar")
    need(receipt["operation"] == receipt["lastRootGuard"] == "READY" and receipt["clearReturned"] is True and
         receipt["budgetMillis"] == 5000 and
         0 <= receipt["startedElapsedMillis"] <= receipt["completedElapsedMillis"] <= receipt["deadlineElapsedMillis"] <=
         receipt["startedElapsedMillis"] + 5000 and receipt["completedElapsedMillis"] <= item["elapsedMillis"] and
         0 < receipt["invalidatedNano"] <= receipt["presentedNano"] <= receipt["queriedNano"] < 2**63 - 1 and
         0 <= receipt["frameIndex"] < receipt["frameCount"] <= 1024 and receipt["polls"] > 0 and
         0 < receipt["baselineDraws"] < receipt["observedDraws"] == state["viewDraws"],
         "Presentation was missing, stale, undefined, late or only a CPU draw")
    idle = receipt["eventIdle"]
    need(isinstance(idle, dict) and set(idle) ==
         {"quietMillis", "startedElapsedMillis", "maximumWaitMillis", "completedElapsedMillis", "returned"} and
         all(type(idle[key]) is int for key in set(idle) - {"returned"}) and
         idle["quietMillis"] == 500 and idle["returned"] is True and idle["maximumWaitMillis"] > 0 and
         receipt["startedElapsedMillis"] <= idle["startedElapsedMillis"] <= idle["completedElapsedMillis"] <=
         receipt["completedElapsedMillis"] <= receipt["deadlineElapsedMillis"] and
         idle["maximumWaitMillis"] == receipt["deadlineElapsedMillis"] - idle["startedElapsedMillis"],
         "Missing or late accessibility-event-idle precondition in original presentation budget")
    root = receipt["root"]
    need(isinstance(root, dict) and set(root) == {"windowId", "package", "bounds", "viewBounds", "interactiveWindow"} and
         root == item.get("activeRootAfter") and type(root["windowId"]) is int and root["windowId"] >= 0 and
         root["package"] == PACKAGE, "Wrong or changed active owned presentation window")
    bounds, view = root["bounds"], root["viewBounds"]
    need(all(isinstance(rect, list) and len(rect) == 4 and all(type(x) is int for x in rect)
             for rect in (bounds, view)), "Invalid presentation rectangles")
    need(bounds[0] <= view[0] < view[2] <= bounds[2] and bounds[1] <= view[1] < view[3] <= bounds[3] and
         view[2] - view[0] == state["viewWidth"] and view[3] - view[1] == state["viewHeight"] and
         all(view[0] <= x < view[2] and view[1] <= y < view[3] for x, y in state["samplePoints"]),
         "Presentation window does not contain the actual synthetic view and sample points")

    window = root["interactiveWindow"]
    need(isinstance(window, dict) and set(window) ==
         {"windowId", "type", "active", "focused", "uniqueMatch", "bounds"} and
         type(window["windowId"]) is int and window["windowId"] == root["windowId"] and
         type(window["type"]) is int and window["type"] == 1 and window["active"] is True and
         window["focused"] is True and window["uniqueMatch"] is True,
         "Missing unique active/focused application inventory entry for the actual View window")
    rect = window["bounds"]
    need(isinstance(rect, list) and len(rect) == 4 and all(type(x) is int for x in rect) and
         rect[0] <= view[0] < view[2] <= rect[2] and rect[1] <= view[1] < view[3] <= rect[3] and
         all(rect[0] <= x < rect[2] and rect[1] <= y < rect[3] for x, y in state["samplePoints"]),
         "Interactive window does not contain actual View/samples")


def validate_recents_education(value, api, admission, system):
    """Optional API32 setup input, never an alternative to the original task-card/image oracles."""
    ledger = value.get("recentsEducation")
    if api == 24:
        need("recentsEducation" not in value, "API24 must not run education actions")
        return
    need(isinstance(ledger, dict) and ledger.get("schema") == 1 and type(ledger["schema"]) is int and
         ledger.get("api") == 32 and type(ledger["api"]) is int and
         ledger.get("operation") in ("NONE_REQUIRED", "DISMISSED") and
         type(ledger.get("observations")) is int and 0 < ledger["observations"] <= admission["attempts"],
         "Missing completed API32 education precondition")
    dismissed = ledger["operation"] == "DISMISSED"
    need(set(ledger) == {"schema", "api", "operation", "observations", "after"} |
         ({"before", "request"} if dismissed else set()), "Unexpected education action ledger")
    after = ledger["after"]
    need(isinstance(after, dict) and set(after) ==
         {"attempt", "observedElapsedMillis", "popupAbsent", "absence", "systemWindow"} and
         type(after["attempt"]) is int and after["attempt"] == admission["attempts"] and
         type(after["observedElapsedMillis"]) is int and
         admission["startedElapsedMillis"] <= after["observedElapsedMillis"] <= admission["completedElapsedMillis"] and
         after["popupAbsent"] is True and isinstance(system, dict) and after["systemWindow"] == system,
         "Education acknowledgement lacks later complete popup-absent real-card admission")
    absence = after["absence"]
    need(isinstance(absence, dict) and set(absence) == {"complete", "textIds", "arrowIds", "exactTexts"} and
         absence["complete"] is True and
         all(type(absence[key]) is int and absence[key] == 0 for key in ("textIds", "arrowIds", "exactTexts")),
         "Refused or ambiguous known-popup markers are not observed absence")
    if not dismissed:
        return
    before, request = ledger["before"], ledger["request"]
    need(isinstance(before, dict) and set(before) == {"attempt", "observedElapsedMillis", "owner", "popup"} and
         type(before["attempt"]) is int and 0 < before["attempt"] < after["attempt"] and
         type(before["observedElapsedMillis"]) is int and
         before["owner"] == {key: val for key, val in system.items() if key != "taskCard"},
         "Education BACK lacks the same actual owned task/root before and after")
    popup = before["popup"]
    need(isinstance(popup, dict) and set(popup) ==
         {"parentBounds", "textBounds", "arrowBounds", "exactText", "exactIds", "expectedClasses", "unique",
          "rootContained", "complete", "parentProjection", "dragLayerResourceMatch", "markerCounts"} and
         all(popup[key] is True for key in ("exactText", "exactIds", "expectedClasses", "unique", "rootContained", "complete")),
         "Education action was not positively admitted by the exact complete structured selector")
    need((popup["parentProjection"] == "DIRECT_LINEAR_LAYOUT" and popup["dragLayerResourceMatch"] is False) or
         (popup["parentProjection"] == "DRAG_LAYER_ACCESSIBILITY" and popup["dragLayerResourceMatch"] is True),
         "Education parent is not an exact supported accessibility projection")
    counts = popup["markerCounts"]
    need(isinstance(counts, dict) and set(counts) == {"textIds", "arrowIds", "exactTexts"} and
         all(type(counts[key]) is int and counts[key] == 1 for key in counts),
         "Education input requires globally unique associated markers")
    bounds = system.get("bounds")
    need(isinstance(bounds, list) and len(bounds) == 4 and all(type(x) is int for x in bounds),
         "Missing education root geometry")
    for key in ("parentBounds", "textBounds", "arrowBounds"):
        rect = popup[key]
        need(isinstance(rect, list) and len(rect) == 4 and all(type(x) is int for x in rect) and
             rect[0] < rect[2] and rect[1] < rect[3], "Invalid education geometry")
        if key != "parentBounds":
            need(bounds[0] <= rect[0] < rect[2] <= bounds[2] and bounds[1] <= rect[1] < rect[3] <= bounds[3],
                 "Education text/arrow not contained in the actual root")
    need(isinstance(request, dict) and set(request) ==
         {"action", "platformAction", "requestedElapsedMillis", "returnedElapsedMillis", "returned", "accepted"} and
         request["action"] == "BACK" and type(request["platformAction"]) is int and request["platformAction"] == 1 and
         request["returned"] is True and request["accepted"] is True and
         all(type(request[key]) is int for key in ("requestedElapsedMillis", "returnedElapsedMillis")) and
         admission["startedElapsedMillis"] <= before["observedElapsedMillis"] <= request["requestedElapsedMillis"] <=
         request["returnedElapsedMillis"] <= after["observedElapsedMillis"] <= admission["deadlineElapsedMillis"] and
         admission["guardCounts"].get("CARD_NOT_IDENTIFIED", 0) > 0,
         "Wrong, repeated, failed or late education BACK request")


def validate_report(raw, token, source, tree, api, files):
    value = owner.decode_json(raw)
    need(not any(key in value for key in ("failureScene", "failureSceneErrorType")) and
         not any(name in files for name in ("failure-recents-scene.png", "failure-recents-scene.part")),
         "Failure-only scene diagnostics cannot qualify a successful witness")
    need(api in IMAGES and value.get("api") == api and value.get("case") == "479" and
         value.get("token") == token and value.get("sourceCommit") == source and
         value.get("declaredSourceTree") == tree and value.get("targetSdk") == 37 and
         value.get("captureObservationSchema") == 5 and value.get("outcome") == owner.PASS and
         value.get("syntheticOnly") is True and value.get("recentsReviewRequired") is True and
         value.get("cleanup") == "OWNED_ACTIVITIES_DESTROYED" and
         not any(key in value for key in ("failure", "cleanupFailureType", "observerCleanupFailureType")),
         "Legacy witness identity, lifecycle or cleanup failed")
    flags = value.get("interactiveWindowObserver")
    need(isinstance(flags, dict) and set(flags) == {"original", "requested", "readback", "restored", "operation"} and
         all(type(flags[key]) is int and 0 <= flags[key] < 2**31
             for key in ("original", "requested", "readback", "restored")) and
         flags["requested"] == flags["readback"] == (flags["original"] | 64) and
         flags["restored"] == flags["original"] and flags["operation"] == "RESTORED",
         "Interactive-window observer flags were not exactly admitted and restored")
    events = value.get("lifecycle")
    need(isinstance(events, list) and events and type(value.get("taskId")) is int,
         "Missing actual task/lifecycle observations")
    created = [event.get("activity") for event in events if event.get("event") == "created"]
    destroyed = [event.get("activity") for event in events if event.get("event") == "destroyed"]
    need(all(type(identity) is int for identity in created + destroyed) and
         len(created) == len(set(created)) == 2 and sorted(created) == sorted(destroyed) and
         all(event.get("taskId") == value["taskId"] for event in events) and
         all(event.get("secureFlag") is True for event in events if event.get("event") == "destroyed") and
         any(event.get("event") == "stopped" and event.get("activity") == created[0] for event in events),
         "Task replacement or protected owned Activity retirement was not observed")
    captures = value.get("captures")
    need(isinstance(captures, list) and all(isinstance(item, dict) for item in captures) and
         [item.get("name") for item in captures] == list(CAPTURES), "Missing, duplicate or reordered observations")
    navigation = value.get("navigationRequests")
    need(isinstance(navigation, list) and len(navigation) == 2, "Missing or duplicate navigation requests")
    previous = captures[0].get("elapsedMillis")
    need(type(previous) is int and previous >= 0, "Missing initial capture timestamp")
    for request, (action, platform) in zip(navigation, (("HOME", 2), ("RECENTS", 3))):
        need(isinstance(request, dict) and set(request) ==
             {"action", "platformAction", "requestedElapsedMillis", "returnedElapsedMillis",
              "returned", "accepted", "operation"} and
             request["action"] == action and type(request["platformAction"]) is int and
             request["platformAction"] == platform and request["returned"] is True and
             request["accepted"] is True and request["operation"] == "GLOBAL_ACTION_RETURNED",
             "Navigation request failed, threw or used an unexpected action")
        start, finish = request["requestedElapsedMillis"], request["returnedElapsedMillis"]
        need(type(start) is int and type(finish) is int and previous <= start <= finish,
             "Missing or reordered navigation timestamps")
        previous = finish
    need(type(captures[1].get("elapsedMillis")) is int and previous <= captures[1]["elapsedMillis"],
         "Recents capture did not follow the actual navigation requests")
    observer = value.get("recentsObserver")
    provider = "com.android.systemui" if api == 24 else "com.google.android.apps.nexuslauncher"
    need(isinstance(observer, dict) and set(observer) ==
         {"provider", "publicAppLabel", "requiredFlagsPresent", "serviceFlags", "closeActionId", "maxNodes", "maxDepth"} and
         observer["provider"] == provider and observer["publicAppLabel"] == "P2pKit Sample" and
         observer["requiredFlagsPresent"] is True and type(observer["serviceFlags"]) is int and
         observer["serviceFlags"] == flags["requested"] and observer["serviceFlags"] & 18 == 18 and
         type(observer["closeActionId"]) is int and
         (observer["closeActionId"] == 0 if api == 24 else observer["closeActionId"] > 0) and
         observer["maxNodes"] == 256 and observer["maxDepth"] == 24, "Unbound Recents semantic observer")
    lookup = value.get("recentsProviderLookup")
    need((lookup == {"operation": "COMPLETE", "packageMatches": True, "distinctUid": True} and
          type(lookup["packageMatches"]) is bool and type(lookup["distinctUid"]) is bool)
         if api == 32 else lookup is None, "Actual provider identity/resources were not admitted")
    admission = value.get("recentsAdmission")
    need(isinstance(admission, dict) and set(admission) ==
         {"startedElapsedMillis", "deadlineElapsedMillis", "completedElapsedMillis", "budgetMillis",
          "attempts", "operation", "lastRootGuard", "lastCompletedGuard", "lastCompletedAttempt", "guardCounts"} and
         admission["operation"] == admission["lastRootGuard"] == admission["lastCompletedGuard"] == "READY" and
         type(admission["lastCompletedAttempt"]) is int and admission["lastCompletedAttempt"] == admission["attempts"] and
         type(admission["attempts"]) is int and admission["attempts"] > 0 and admission["budgetMillis"] == 5000,
         "Missing complete bounded Recents admission")
    guard_counts = admission["guardCounts"]
    need(isinstance(guard_counts, dict) and set(guard_counts) <=
         {"ROOT_MISSING", "ROOT_REFRESH_FAILED", "ROOT_NOT_VISIBLE", "ROOT_PACKAGE_INVALID", "ROOT_GEOMETRY_INVALID",
          "TREE_INCOMPLETE", "CARD_NOT_IDENTIFIED", "READY"} and
         all(type(count) is int and count > 0 for count in guard_counts.values()) and
         guard_counts.get("READY") == 1 and sum(guard_counts.values()) == admission["attempts"],
         "Completed Recents guard history is missing, stale or inconsistent")
    start, finish, deadline = (admission[key] for key in
        ("startedElapsedMillis", "completedElapsedMillis", "deadlineElapsedMillis"))
    need(all(type(x) is int for x in (start, finish, deadline)) and
         previous <= start <= finish <= deadline <= start + 5000 and finish <= captures[1]["elapsedMillis"],
         "Recents root admission exceeded its original bound or was reordered")
    validate_recents_education(value, api, admission, captures[1].get("systemWindowBefore"))
    # Accepted system requests are not proof: all actual lifecycle/window/image checks below still apply.
    expected_files = {"result.json"}
    for index, item in enumerate(captures):
        name, kind = item["name"], item.get("observation")
        need(kind in ("BITMAP", "UNAVAILABLE"), "Unknown capture observation")
        need(type(item.get("elapsedMillis")) is int and item["elapsedMillis"] >= 0 and
             (index == 0 or item["elapsedMillis"] >= captures[index - 1]["elapsedMillis"]),
             "Missing or reordered capture timestamps")
        if name != "actual-recents-original":
            visible = name in POSITIVE
            activity = created[0 if index in (0, 2) else 1]
            for key in ("stateBefore", "stateAfter"):
                validate_state(item.get(key), secure=not visible, activity=activity, task=value["taskId"])
            need(state_binding(item["stateBefore"]) == state_binding(item["stateAfter"]),
                 "Owner/window/view or geometry changed during capture")
            validate_presentation(item, item["stateBefore"])
        else:
            visible = None
            need("stateBefore" not in item and "stateAfter" not in item and item.get("pixelVariation") is True,
                 "Recents must be a nonuniform original system screenshot, not an app rendering")
            system = item.get("systemWindowBefore")
            need(isinstance(system, dict) and set(system) ==
                 {"activity", "taskId", "secureFlag", "stopped", "windowFocused", "package", "windowId", "bounds",
                  "ownedTaskCount", "baseActivityMatches", "topActivityMatches", "taskCard"} and
                 system == item.get("systemWindowAfter") and type(system.get("activity")) is int and
                 system["activity"] == created[0] and type(system.get("taskId")) is int and
                 system["taskId"] == value["taskId"] and system["secureFlag"] is True and
                 system["stopped"] is True and system["windowFocused"] is False and
                 system["package"] == provider and type(system["ownedTaskCount"]) is int and
                 system["ownedTaskCount"] == 1 and system["baseActivityMatches"] is True and
                 system["topActivityMatches"] is True and
                 type(system["windowId"]) is int and system["windowId"] >= 0,
                 "Unbound or changed system window during Recents capture")
            bounds = system["bounds"]
            need(isinstance(bounds, list) and len(bounds) == 4 and all(type(x) is int for x in bounds) and
                 bounds[2] > bounds[0] and bounds[3] > bounds[1], "Missing actual system window bounds")
            card = system["taskCard"]
            need(isinstance(card, dict) and set(card) ==
                 {"kind", "exactPublicLabelMatch", "uniqueStructuredCard", "cardBounds", "labelBounds", "snapshotBounds"}
                 and card["kind"] == ("SYSTEM_UI_TASK_TITLE" if api == 24 else "QUICKSTEP_TASK_DESCRIPTION") and
                 card["exactPublicLabelMatch"] is True and card["uniqueStructuredCard"] is True,
                 "Missing unique structured intended-task correlation")
            for key, outer in (("cardBounds", bounds), ("labelBounds", card["cardBounds"]),
                               ("snapshotBounds", card["cardBounds"])):
                rectangle = card[key]
                need(isinstance(rectangle, list) and len(rectangle) == 4 and
                     all(type(x) is int for x in rectangle) and
                     outer[0] <= rectangle[0] < rectangle[2] <= outer[2] and
                     outer[1] <= rectangle[1] < rectangle[3] <= outer[3], "Task-card anchor is hidden or out of bounds")
        if kind == "UNAVAILABLE":
            need(visible is False and set(item) ==
                 {"name", "elapsedMillis", "observation", "stateBefore", "stateAfter", "presentation", "activeRootAfter"},
                 "Unavailable observation cannot invent pixels or replace required images")
            continue
        need(item.get("file") == name + ".png" and type(item.get("width")) is int and item["width"] > 0 and
             type(item.get("height")) is int and item["height"] > 0 and
             item.get("pixelReadback") == "ARGB_8888_COPY" and
             isinstance(item.get("sourceBitmapConfig"), str) and item["sourceBitmapConfig"] and
             item.get("sourceBitmapWidth") == item["width"] and item.get("sourceBitmapHeight") == item["height"],
             "Missing original screenshot/readback geometry")
        expected_files.add(item["file"])
        need(item["file"] in files, "Missing original PNG")
        validate_png(files[item["file"]], item["width"], item["height"])
        if visible is not None:
            need(isinstance(item.get("sampleMatches"), list) and
                 all(type(match) is bool for match in item["sampleMatches"]) and
                 item["sampleMatches"] == [visible] * 4 and
                 all(x < item["width"] and y < item["height"] for x, y in item["stateBefore"]["samplePoints"]),
                 "Secure or positive captured pixel control failed")
    need(set(files) == expected_files, "Wrong actual legacy evidence inventory")
    first, protected, closing = captures[4:7]
    need(first["observation"] == closing["observation"] == "BITMAP" and
         state_binding(first["stateBefore"]) == state_binding(protected["stateBefore"]) ==
         state_binding(closing["stateBefore"]) and
         first["presentation"]["root"] == protected["presentation"]["root"] == closing["presentation"]["root"] and
         (first["width"], first["height"]) == (closing["width"], closing["height"]) and
         (protected["observation"] == "UNAVAILABLE" or
          (first["width"], first["height"]) == (protected["width"], protected["height"])),
         "Missing same-window positive/protected/positive transport bracket")
    need(all(captures[0]["stateBefore"][key] == captures[2]["stateBefore"][key]
             for key in ("activity", "window", "view", "taskId")), "Reentry did not retain the original window/view")
    return value


class LegacyCampaign:
    CASE = "479"
    BUILD_TASKS = ()
    SCOPE = "API24/32 secure-window and system Recents; synthetic MainActivity content only"
    REVIEW = "REQUIRED: independently inspect original Recents task card and synthetic-only control images"
    NOT_QUALIFIED = ["natural revealed credential UI", "physical/OEM devices", "RPC", "Wi-Fi", "API37 permissions"]

    def __init__(self, api):
        need(api in IMAGES, "Unsupported legacy witness API")
        self.API = api
        self.IMAGE = IMAGES[api]
        self.LABEL = f"android-legacy-task-preview-api{api}"

    def prepare_emulator(self, *, run, sdk, report):
        # sdkmanager obtains this explicit package from its maintained Google SDK
        # repository. Retain the installed package revision, not a guessed binary pin.
        raw = (sdk / self.IMAGE.replace(";", "/") / "source.properties").read_text()
        fields = {}
        for line in raw.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, separator, value = line.partition("=")
            need(separator and key.strip() not in fields, "Ambiguous installed image properties")
            fields[key.strip()] = value.strip()
        need(fields.get("AndroidVersion.ApiLevel") == str(self.API) and
             fields.get("SystemImage.Abi") == "x86_64" and fields.get("Pkg.Revision"),
             "Wrong installed legacy system image")
        owner.write_json(report / "selected-sdk-image.json", {"package": self.IMAGE, "properties": fields})
        return ()

    @staticmethod
    def validate_emulator_boot(raw):
        need(raw, "Missing original emulator startup output")

    def run(self, *, run, device, report, source, tree, app_apk, test_apk, **_unused):
        case_dir = report / self.CASE
        case_dir.mkdir(mode=0o700)
        run([*device, "install", "--no-streaming", app_apk], timeout=90)
        run([*device, "install", "--no-streaming", test_apk], timeout=90)
        token = uuid.uuid4().hex
        owner.write_json(case_dir / "request.json", {"case": self.CASE, "token": token,
                         "sourceCommit": source, "sourceTree": tree, "api": self.API, "runner": RUNNER})
        code, output = run([*device, "shell", "am", "instrument", "-w", "-r",
            "-e", "case", self.CASE, "-e", "token", token, "-e", "sourceCommit", source,
            "-e", "sourceTree", tree, PACKAGE + ".test/" + RUNNER], timeout=150, check=False)
        (case_dir / "instrumentation.txt").write_bytes(output)
        archive_code, raw = run([*device, "exec-out", "run-as", PACKAGE, "tar", "-C",
            f"no_backup/ui-479-{token}", "-cf", "-", "."], timeout=30, check=False)
        files = owner.evidence_members(raw) if archive_code == 0 else {}
        for name, content in files.items():
            (case_dir / name).write_bytes(content)
        need(code == 0 and archive_code == 0, "Legacy instrumentation or evidence capture failed")
        owner.instrumentation_result(output, self.CASE, token, definitions=DEFINITIONS)
        validate_report(files["result.json"], token, source, tree, self.API, files)
        return {self.CASE: owner.PASS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, type=int, choices=tuple(IMAGES))
    args = parser.parse_args(argv)
    return owner.main([], campaign=LegacyCampaign(args.api))


if __name__ == "__main__":
    raise SystemExit(main())
