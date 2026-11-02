"""Private local UI mailbox for the existing Mac campaign, never an RPC transport.

The caller supplies a prepared Session in its original ordinary-user audit
session. The UI cannot supply commands, endpoints, keys or product paths.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import stat
import time
from types import SimpleNamespace

MODES = ("large", "correctness", "churn", "steady")
PLATFORMS = ("android", "ios")
ID = re.compile(r"[a-f0-9]{32}")


def request(value, source_sha):
    if (type(value) is not dict or set(value) != {"schema", "id", "sourceSha", "platform", "clients", "mode", "action"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or type(value["id"]) is not str or not ID.fullmatch(value["id"])
            or value["sourceSha"] != source_sha or value["platform"] not in PLATFORMS
            or type(value["clients"]) is not int or value["clients"] not in (128, 256)
            or value["mode"] not in MODES or value["action"] not in ("run", "recover")):
        raise ValueError("Invalid or foreign Test Center request")
    return value


def ready_marker(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != 0):
        raise ValueError("Original private ready marker required")


def safe_summary(value, campaign):
    summary = campaign.result_summary(value)
    # Only selected observations cross the UI boundary; no device/path/pin/log fields.
    keys = ("status", "clientCount", "mode", "physicalQualified", "peakResidentBytes", "peakNativeThreads",
            "peakObservedCpuPercentOfOneCore", "cleanup", "observedBatteryStates", "observedThermalStates")
    result = {key: summary[key] for key in keys}
    measurement = value.get("measurement")
    if type(measurement) is dict:
        result["measurement"] = {key: measurement[key] for key in
            ("status", "measurements", "latencyBucketUpperMs", "throughputResponsesPerSecond", "rpcFailuresByKind")
            if key in measurement}
    return result


def prepare_profiles(session, campaign, settings):
    manifest = campaign.verify_manifest(campaign.private_json(session.state / "private/preparation.json"),
                                        session.source, session.state)
    files = campaign.module("test_center_settings", "run-rpc-capacity-lab.py")
    profiles = {}
    for path in settings:
        values = files.parse(files.read_private(path))
        platform = "android" if "androidUsbSerial" in values else "ios"
        clients = int(values.get("clientCount", "0"))
        key = (platform, clients)
        if key in profiles or values.get("schema") != "2" or clients not in (128, 256):
            raise ValueError("Distinct schema2 128/256 settings required")
        product = "android-apk" if platform == "android" else "ios-executable"
        if (values.get("sourceSha") != session.source["commit"] or product not in manifest["artifacts"]
                or values.get("hostArtifactSha256") != manifest["artifacts"][product]["sha256"]):
            raise ValueError("Settings and installed product must bind the prepared source")
        coordinator = "run-rpc-mobile-capacity.py" if platform == "android" else "run-rpc-ios-mobile-capacity.py"
        campaign.module("test_center_preflight_" + platform, coordinator).settings(
            values, session.source["commit"], "ui-preflight", files)
        profiles[key] = (path, campaign.artifact(path))
    if not profiles:
        raise ValueError("Prepare at least one physical phone profile")
    return profiles


def serve(session, campaign, settings, *, lifetime_seconds=43_200):
    profiles = prepare_profiles(session, campaign, settings)
    directory = session.state / "private/test-center"
    directory.mkdir(mode=0o700, exist_ok=True)
    campaign.private(directory)
    for name in ("requests", "results", "cancel", "ready", "cancel-ready"):
        (directory / name).mkdir(mode=0o700, exist_ok=True)
        campaign.private(directory / name)
    descriptor = os.open(directory / "worker.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError("Original private worker lock required")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        context = dict(schema=1, sourceSha=session.source["commit"],
                       profiles=[dict(platform=p, clients=c) for p, c in sorted(profiles)],
                       settings=[dict(platform=p, clients=c, sha256=a["sha256"]) for (p, c), (_, a) in sorted(profiles.items())])
        if (directory / "context.json").exists():
            if campaign.private_json(directory / "context.json") != context:
                raise ValueError("This mailbox belongs to other prepared settings; retain it")
        else:
            campaign.new_json(directory / "context.json", context)
        writer = campaign.module("test_center_status_writer", "run-rpc-capacity-lab.py")

        def status(value):
            raw = (json.dumps(dict(schema=1, sourceSha=session.source["commit"],
                                   updatedAtEpochMillis=int(time.time() * 1000), **value)) + "\n").encode()
            path = directory / "status.json"
            writer.write_private(path, raw, replace=path.exists())

        seen = set()
        deadline = time.monotonic() + lifetime_seconds
        status(dict(state="Idle"))
        while time.monotonic() < deadline:
            for marker in sorted((directory / "ready").iterdir()):
                ready_marker(marker)
                path = directory / "requests" / marker.name
                if path.name in seen:
                    continue
                if not re.fullmatch(r"[a-f0-9]{32}\.json", path.name):
                    raise ValueError("Unexpected mailbox file; no request dispatched")
                seen.add(path.name)
                if len(seen) > 256:
                    raise ValueError("Mailbox limit reached; retain original requests and results")
                output = directory / "results" / path.name
                if output.exists():
                    continue  # A worker restart never replays a terminal request.
                if (directory / (path.stem + ".started.json")).exists():
                    campaign.new_json(output, dict(schema=1, sourceSha=session.source["commit"], id=path.stem,
                        state="RecoveryRequired", cleanupVerified=False,
                        reason="InterruptedWorker; original attempt must be recovered before another run"))
                    continue
                started = time.monotonic()
                try:
                    value = request(campaign.private_json(path), session.source["commit"])
                    if value["id"] != path.stem or (value["platform"], value["clients"]) not in profiles:
                        raise ValueError("Unprepared profile")
                    settings_path, settings_artifact = profiles[value["platform"], value["clients"]]
                    if campaign.artifact(settings_path) != settings_artifact:
                        raise ValueError("Prepared settings changed")
                    cancel_path = directory / "cancel" / path.name

                    def cancelled():
                        status(dict(state="Running", id=value["id"], platform=value["platform"],
                                    clients=value["clients"], mode=value["mode"],
                                    elapsedSeconds=int(time.monotonic() - started)))
                        marker = directory / "cancel-ready" / path.name
                        if not marker.exists():
                            return False
                        ready_marker(marker)
                        cancel = campaign.private_json(cancel_path)
                        if cancel != dict(schema=1, id=value["id"], sourceSha=session.source["commit"]):
                            raise ValueError("Foreign cancellation; ownership retained")
                        return True

                    if cancelled():
                        raise ValueError("CancelledBeforeDispatch")
                    campaign.new_json(directory / (path.stem + ".started.json"), value)
                    session.cancel_requested = cancelled
                    label = "ui-" + value["id"][:20]
                    error = None
                    try:
                        if value["action"] == "recover":
                            pending = campaign.private_json(session.state / "private" / (value["platform"] + "-pending.json"))
                            original = campaign.private_json(Path(pending["attempt"]))
                            if original["clients"] != value["clients"] or original["mode"] != value["mode"]:
                                raise ValueError("Select the original phone, capacity and phase to recover")
                            label = original["runLabel"]
                            session.recover(value["platform"])
                        else:
                            session.run(SimpleNamespace(platform=value["platform"], clients=value["clients"],
                                mode=value["mode"], settings=settings_path, run_label=label))
                    except Exception as failure:
                        error = type(failure).__name__  # Never publish a local exception's private message.
                    finally:
                        session.cancel_requested = None
                    result_path = session.state / "work" / ("mobile-control-" + label) / "result.json"
                    summary = safe_summary(campaign.private_json(result_path), campaign) if result_path.exists() else None
                    pending = session.state / "private" / (value["platform"] + "-pending.json")
                    cleanup = not pending.exists() and summary is not None and summary.get("cleanup") == dict(
                        runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True)
                    outcome = dict(schema=1, sourceSha=session.source["commit"], id=value["id"],
                        state="NeedsReview" if error is None and cleanup and value["action"] == "run"
                            else ("Failed" if cleanup else "RecoveryRequired"),
                        platform=value["platform"], clients=value["clients"], mode=value["mode"], runLabel=label,
                        elapsedSeconds=int(time.monotonic() - started), cleanupVerified=cleanup,
                        reason="OriginalFailureRetained" if value["action"] == "recover" and error is None else error,
                        summary=summary, physicalQualified=False)
                except Exception as failure:
                    touched = (directory / (path.stem + ".started.json")).exists()
                    outcome = dict(schema=1, sourceSha=session.source["commit"], id=path.stem,
                        state="RecoveryRequired" if touched else "Rejected", cleanupVerified=False,
                        reason=type(failure).__name__, physicalQualified=False)
                campaign.new_json(output, outcome)
            status(dict(state="Idle"))
            time.sleep(1)
        status(dict(state="Offline"))
    finally:
        session.cancel_requested = None
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
