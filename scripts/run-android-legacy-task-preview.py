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
            "reapplied-production-secure-policy")


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


def validate_report(raw, token, source, tree, api, files):
    value = owner.decode_json(raw)
    need(api in IMAGES and value.get("api") == api and value.get("case") == "479" and
         value.get("token") == token and value.get("sourceCommit") == source and
         value.get("declaredSourceTree") == tree and value.get("targetSdk") == 37 and
         value.get("outcome") == owner.PASS and value.get("syntheticOnly") is True and
         value.get("recentsReviewRequired") is True and
         value.get("cleanup") == "OWNED_ACTIVITIES_DESTROYED" and
         not any(key in value for key in ("failure", "cleanupFailureType")),
         "Legacy witness identity, lifecycle or cleanup failed")
    captures = value.get("captures")
    need(isinstance(captures, list) and [item.get("name") for item in captures] == list(CAPTURES),
         "Missing, duplicate or reordered legacy captures")
    need(set(files) == {"result.json", *(name + ".png" for name in CAPTURES)},
         "Wrong legacy original evidence inventory")
    for item in captures:
        name = item["name"]
        need(item.get("file") == name + ".png" and
             type(item.get("width")) is int and item["width"] > 0 and
             type(item.get("height")) is int and item["height"] > 0,
             "Missing original screenshot or geometry")
        validate_png(files[name + ".png"], item["width"], item["height"])
        if name != "actual-recents-original":
            visible = name == "synthetic-unprotected-positive-control"
            need(item.get("sampleMatches") == [visible] * 4 and
                 item.get("secureFlag") is (not visible), "Secure or positive capture control failed")
    events = value.get("lifecycle")
    need(isinstance(events, list) and events and type(value.get("taskId")) is int,
         "Missing actual task/lifecycle observations")
    created = [event.get("activity") for event in events if event.get("event") == "created"]
    destroyed = [event.get("activity") for event in events if event.get("event") == "destroyed"]
    need(len(created) == len(set(created)) == 2 and sorted(created) == sorted(destroyed) and
         all(event.get("taskId") == value["taskId"] for event in events) and
         any(event.get("event") == "stopped" and event.get("activity") == created[0]
             for event in events), "Task replacement or owned Activity retirement was not observed")
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
