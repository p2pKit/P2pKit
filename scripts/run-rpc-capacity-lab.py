#!/usr/bin/env python3
"""Opt-in per-machine synthetic capacity launcher. Requires admitted native ownership.

Run on each machine inside its own run-audit-command.py scope. Only public synthetic
pins/readiness/telemetry cross the already approved, pinned SSH control channel;
the RPC endpoint is always a direct numeric organization-LAN address. This launcher
never creates a tunnel, changes interfaces/firewalls, pairs unknown clients, or
signals a PID. A mechanical result is not LAN, resource or physical qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import selectors
import stat
import struct
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rpc_capacity_cpu as cpu
import rpc_capacity_evidence as evidence

LIMIT = 262_144
AUTHORIZATION = "synthetic-private-network-only"
CONTROL_NAMES = {"client-pins.txt", "host-ready.txt", "host-telemetry.txt", "host-failed.txt", "stop.txt"}
FIELDS = {"schema", "role", "runLabel", "sourceSha", "endpointAddress", "port", "subnets", "interface", "localAddress"}
CORRECTNESS_CASES = ("concurrent-correlation", "application-error", "procedure-authorization",
                     "sent-deadline", "sent-cancellation", "close-during-call")


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


class ControlFileLifetimeChanged(RuntimeError):
    """No bytes were consumed: lstat and the opened descriptor identify different files."""


def private_directory(path: Path) -> Path:
    need(path.is_absolute() and path == Path(os.path.normpath(path)), "Absolute normalized private directory required")
    for item in (path, *path.parents):
        need(not item.is_symlink(), "Symlinked path refused")
    info = path.stat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
         "Directory must be owned and mode 0700")
    return path


def read_private(path: Path) -> bytes:
    private_directory(path.parent)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
         "Control file must be owned, regular and mode 0600")
    # NONBLOCK prevents a regular-file-to-FIFO replacement from hanging before
    # the descriptor's type/owner/mode can be checked. It does not affect files.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        actual = os.fstat(stream.fileno())
        need(stat.S_ISREG(actual.st_mode) and actual.st_uid == os.getuid() and
             stat.S_IMODE(actual.st_mode) == 0o600, "Opened control file must be owned, regular and mode 0600")
        if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
            raise ControlFileLifetimeChanged("Control file lifetime changed")
        data = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
        need((actual.st_size, actual.st_mtime_ns, actual.st_mode, actual.st_uid) ==
             (after.st_size, after.st_mtime_ns, after.st_mode, after.st_uid), "Control file changed during read")
    need(len(data) <= LIMIT, "Oversized control file")
    return data


def read_telemetry(path: Path) -> bytes:
    """Reobserve only the explicitly rotating telemetry publication, at most three times.

    Its writer publishes immutable snapshots by atomic rename. A rename between
    lstat/open invalidates that observation, not the next snapshot. Every attempt
    retains the complete private-file/lifetime checks; no mismatched descriptor's
    bytes are returned. Permission, symlink, mutation, size and other errors fail
    immediately. Immutable configuration, pins, readiness and receipts never retry.
    This is neither an RPC retry nor an extension of a workload/cleanup deadline.
    """
    need(path.name == "host-telemetry.txt", "Only host telemetry may be reobserved")
    for attempt in range(3):
        try:
            return read_private(path)
        except ControlFileLifetimeChanged:
            if attempt == 2:
                raise


def parse(data: bytes) -> dict[str, str]:
    need(len(data) <= LIMIT and all(byte == 10 or 32 <= byte <= 126 for byte in data), "ASCII control file required")
    result = {}
    for line in data.decode("ascii").splitlines():
        if not line:
            continue
        key, separator, value = line.partition("=")
        need(separator and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9]{0,63}", key) and value and key not in result,
             "Malformed or duplicated control field")
        result[key] = value
    return result


def encode(values: dict[str, str]) -> bytes:
    data = "".join(f"{key}={value}\n" for key, value in values.items()).encode("ascii")
    need(parse(data) == values, "Unrepresentable configuration")
    return data


def write_private(path: Path, data: bytes, replace=False):
    private_directory(path.parent)
    need(len(data) <= LIMIT and not path.is_symlink(), "Invalid bounded output")
    temporary = path.parent / (".control-" + os.urandom(16).hex())
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            if path.exists():
                read_private(path)
            os.replace(temporary, path)
        else:
            os.link(temporary, path)  # Atomic create-only; no racy absent-check/replace.
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def numeric_private(value):
    address = ipaddress.IPv4Address(value)
    need(any(address in ipaddress.IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")),
         "Explicit organization-private IPv4 LAN address required")
    return address


def configuration(values: dict[str, str], source: str):
    schema = values.get("schema")
    expected = FIELDS | ({"clientCount"} if schema == "2" else set())
    need(values.keys() == expected and schema in ("1", "2"), "Exact configuration schema required")
    if schema == "2":
        need(values["clientCount"] in ("128", "256"), "Explicit128 or256 client profile required")
    need(values["role"] in ("host", "client") and values["sourceSha"] == source and
         re.fullmatch(r"[a-f0-9]{40}", source), "Wrong role/source")
    need(re.fullmatch(r"[a-z0-9-]{1,64}", values["runLabel"]), "Invalid non-secret run label")
    need(re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}", values["interface"]), "Explicit interface required")
    need(re.fullmatch(r"[1-9][0-9]{3,4}", values["port"]) and 1024 <= int(values["port"]) <= 65535,
         "Unprivileged fixed test port required")
    local, peer = numeric_private(values["localAddress"]), numeric_private(values["endpointAddress"])
    networks = [ipaddress.IPv4Network(value, strict=True) for value in values["subnets"].split(",")]
    need(1 <= len(networks) <= 16 and len(set(networks)) == len(networks), "Bounded distinct explicit subnets required")
    for network in networks:
        numeric_private(str(network.network_address))
        numeric_private(str(network.broadcast_address))
    need(any(local in network for network in networks) and any(peer in network for network in networks),
         "Local and remote addresses must be in approved subnets")
    # The library's stricter OS/path checks still run; this validation does not replace them.
    return values


def owned_context():
    need(os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN"), "Admitted native command ownership required")
    need(os.environ.get("RPC_CAPACITY_LAB_AUTHORIZED") == AUTHORIZATION, "Owner-scoped lab authorization required")
    state = Path(os.environ["P2PKIT_AUDIT_STATE_DIR"]).resolve(strict=True)
    context = json.loads(read_private(state / "context.json"))
    need(context["source"]["status"] == "", "Clean source required")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10).decode().strip()
    need(source == context["source"]["commit"] and
         not subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, timeout=10).strip(),
         "Source differs from admitted candidate")
    return state, source


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "Duplicate distribution field")
        result[key] = value
    return result


def read_distribution_file(path, limit, *, private=False):
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and not stat.S_ISLNK(before.st_mode) and
         0 < before.st_size <= limit and (not private or before.st_uid == os.getuid() and
         before.st_nlink == 1 and not stat.S_IMODE(before.st_mode) & 0o077),
         "Distribution entry must remain bounded, regular and retain its admitted owner")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        opened = os.fstat(stream.fileno())
        need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "Distribution lifetime changed")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) == before.st_size and (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
         after.st_mode, after.st_uid, after.st_nlink) == (before.st_dev, before.st_ino, before.st_size,
         before.st_mtime_ns, before.st_mode, before.st_uid, before.st_nlink) and
         (path.lstat().st_dev, path.lstat().st_ino) == (before.st_dev, before.st_ino),
         "Distribution changed during its bounded descriptor read")
    return raw


def distribution(source: str):
    directory = ROOT / "samples/p2p-sample-rpc/build/capacity-lab"
    need(directory.is_dir() and not directory.is_symlink(), "Run prepareRpcCapacityLab in the admitted candidate first")
    manifest_file = directory / "manifest.json"
    need(manifest_file.is_file() and not manifest_file.is_symlink() and manifest_file.stat().st_size <= LIMIT,
         "Missing bounded distribution provenance")
    manifest = json.loads(read_distribution_file(manifest_file, LIMIT), object_pairs_hook=unique)
    need(type(manifest) is dict and set(manifest) in (
        {"schema", "sourceSha", "scope", "entries"}, {"schema", "sourceSha", "scope", "entries", "macosNative"}) and
         type(manifest["schema"]) is int and manifest["schema"] == 1 and manifest["sourceSha"] == source and
         manifest["scope"] == "SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION", "Wrong distribution source/scope")
    jars = sorted(path for path in directory.iterdir() if path != manifest_file)
    need(1 <= len(jars) <= 128 and all(path.suffix == ".jar" and path.is_file() and not path.is_symlink()
                                    for path in jars), "Unexpected prepared runtime entry")
    actual, total = [], 0
    for path in jars:
        raw = read_distribution_file(path, 256 * 1024 * 1024 - total)
        total += len(raw)
        actual.append({"name": path.name, "sha256": hashlib.sha256(raw).hexdigest()})
    need(actual == manifest["entries"], "Prepared runtime bytes/order changed")
    return directory, manifest, os.pathsep.join(str(path) for path in jars)


MAC_MANIFEST_JAR = "p2pkit-macos-tcp-manifest.jar"
MAC_NATIVE_FILES = ("libp2pkit_lan_socket.dylib", "macos-tcp.properties", MAC_MANIFEST_JAR, "producer.json")


def macos_native_binding(source: str, directory, manifest):
    """Preflight the original private native stage; Java independently verifies it before System.load.

    Only the fixed current-source stage is admissible. No arbitrary native path,
    extracted library, classpath fallback or guessed multi-interface exemption.
    """
    native = manifest.get("macosNative")
    need(type(native) is dict and set(native) == {"directory", "entries"} and
         native["directory"] == "library/p2p-transport-lan/build/macos-tcp/" + source,
         "Mac capacity requires the source-matched scoped native stage")
    stage = ROOT / native["directory"]
    for parent in (stage, *stage.parents):
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
             info.st_uid in (0, os.getuid()) and not stat.S_IMODE(info.st_mode) & 0o022,
             "Native stage ancestry must retain its original protected owner")
    need({path.name for path in stage.iterdir()} == set(MAC_NATIVE_FILES), "Unexpected native stage entry")
    snapshots = {}
    bounds = dict(zip(MAC_NATIVE_FILES, (4_194_304, 4096, 65536, LIMIT)))
    for name in MAC_NATIVE_FILES:
        snapshots[name] = read_distribution_file(stage / name, bounds[name], private=True)
    actual = [{"name": name, "sha256": hashlib.sha256(snapshots[name]).hexdigest()} for name in MAC_NATIVE_FILES]
    need(actual == native["entries"], "Native stage bytes changed after distribution preparation")
    properties = parse(snapshots["macos-tcp.properties"])
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, timeout=10).decode().strip()
    library = snapshots["libp2pkit_lan_socket.dylib"]
    need(properties == dict(abi="1", platform="macos", arch="arm64", source=source, tree=tree,
         file="libp2pkit_lan_socket.dylib", bytes=str(len(library)), sha256=actual[0]["sha256"]) and
         len(library) >= 32 and struct.unpack("<II", library[:8]) == (0xFEEDFACF, 0x0100000C) and
         struct.unpack("<I", library[12:16])[0] == 6, "Native source/tree/ABI/header differs from the prepared driver")
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(snapshots[MAC_MANIFEST_JAR])) as jar:
        entries = jar.infolist()
        need(len(entries) == 1 and entries[0].filename == "META-INF/p2pkit/macos-tcp.properties" and
             entries[0].file_size == len(snapshots["macos-tcp.properties"]) and
             jar.read(entries[0]) == snapshots["macos-tcp.properties"], "Original classpath manifest is not exact")
    copied = directory / MAC_MANIFEST_JAR
    need(read_distribution_file(copied, bounds[MAC_MANIFEST_JAR]) == snapshots[MAC_MANIFEST_JAR],
         "Copied native manifest JAR differs from its original owner")
    return {"directory": str(stage), "sourceSha": source, "treeSha": tree, "entries": actual}


def native_options(source: str):
    directory, manifest, _ = distribution(source)
    if platform.system() != "Darwin":
        need("macosNative" not in manifest, "Do not mix a Mac native distribution with another platform")
        return [], None
    need(platform.machine() == "arm64", "Mac capacity requires the native ARM64 generator")
    bound = macos_native_binding(source, directory, manifest)
    return ["-Ddev.p2pkit.lan.macos.nativeDir=" + bound["directory"]], bound


def classpath(source: str) -> str:
    directory, manifest, value = distribution(source)
    if "macosNative" in manifest or platform.system() == "Darwin":
        native_options(source)
    return value


def workload_entrypoint(role, mode, schema_version=1):
    need(role in ("host", "client") and mode in ("steady", "large", "correctness", "churn") and
         type(schema_version) is int and schema_version in (1, 2), "Unknown lab workload/role/schema")
    need(mode != "churn" or schema_version == 2, "Churn controls require explicit schema2 configuration")
    if mode == "correctness" and schema_version == 1:
        return (("dev.p2pkit.sample.rpc.lab.LabHostKt", ["--owner-authorized-correctness-host"]) if role == "host" else
                ("dev.p2pkit.sample.rpc.lab.LabRpcChecksKt", ["--owner-authorized-correctness-run"]))
    return (("dev.p2pkit.sample.rpc.lab.LabHostKt", ["--owner-authorized-capacity-host"]) if role == "host" else
            ("dev.p2pkit.sample.rpc.RpcCapacityMainKt", ["--owner-authorized-capacity-run", "--" + mode]))


def correctness_result(measurement):
    return (type(measurement) is dict and type(measurement.get("schema")) is int and
            type(measurement.get("expectedCases")) is int and measurement.get("capacityQualified") is False and
            measurement == {
                "schema": 1, "mode": "correctness", "scope": "REAL_SOCKET_CORRECTNESS_NOT_CAPACITY",
                "status": "PENDING_RESOURCE_AND_NETWORK_REVIEW", "capacityQualified": False,
                "expectedCases": len(CORRECTNESS_CASES), "passedCases": list(CORRECTNESS_CASES),
            })


def capture_capacity_record(report, line, schema_version, role, mode):
    prefixes = ((b"RPC_CAPACITY_INITIALIZATION_JSON:", "initialization"),
                (b"RPC_CAPACITY_IDLE_JSON:", "connectedIdle"),
                (b"RPC_CAPACITY_RESULT_JSON:", "measurement"),
                (b"RPC_CAPACITY_FINAL_JSON:", "cleanup"))
    order = (["initialization"] if mode == "steady" else []) + (
        ["connectedIdle"] if mode == "steady" and schema_version == 2 else []) + ["measurement", "cleanup"]
    for prefix, field in prefixes:
        if line.startswith(prefix):
            need(role == "client" and field in order and field not in report and len(line) <= LIMIT,
                 "Unexpected, duplicate or oversized capacity result record")
            prior = [key for key in order if key in report]
            need(not prior or order.index(field) > order.index(prior[-1]), "Capacity result records are out of order")
            report[field] = json.loads(line[len(prefix):], object_pairs_hook=evidence.unique)
            return


def completed_client_results(report, values, mode):
    """A zero JVM exit cannot replace completed source/profile-bound outcomes and owned retirement."""
    schema, clients = int(values["schema"]), int(values.get("clientCount", "128"))
    need(report.get("schema") == schema and type(report.get("schema")) is int and report.get("role") == "client" and
         report.get("mode") == mode and report.get("sourceSha") == values["sourceSha"] and
         report.get("runLabel") == values["runLabel"], "Launcher source, role or workload mismatch")
    need((schema == 1 and "clientCount" not in report) or (schema == 2 and
         type(report.get("clientCount")) is int and report["clientCount"] == clients), "Launcher cohort mismatch")
    cleanup = report.get("cleanup", {})
    if not (report.get("exitCode") == 0 and cleanup.get("cleanupVerified") is True and
            cleanup.get("mechanicalChecksPassed") is True and
            report.get("measurement", {}).get("status") == "PENDING_RESOURCE_AND_NETWORK_REVIEW"):
        return False
    evidence.record_profile(cleanup, {'schema', 'cleanupVerified', 'mechanicalChecksPassed', 'capacityQualified'}, clients)
    need(cleanup["schema"] == schema and cleanup["capacityQualified"] is False, "Cleanup source profile mismatch")
    if mode in ("steady", "large"):
        evidence.measurement(report["measurement"], mode, client_count=clients)
        need(report["measurement"]["schema"] == schema, "Measurement schema mismatch")
        if mode == "steady":
            initialized = evidence.initialization(report.get("initialization"), client_count=clients)
            need(initialized["schema"] == schema and initialized["status"] == "INITIALIZED_NOT_CAPACITY",
                 "Fixed initialization did not complete")
            if schema == 2:
                idle = evidence.connected_idle(report.get("connectedIdle"), client_count=clients)
                need(idle["sourceSha"] == values["sourceSha"] and idle["runLabel"] == values["runLabel"],
                     "Connected-idle source or run mismatch")
                if idle["status"] != "OBSERVED_CONNECTED_IDLE_NOT_CAPACITY":
                    return False
    elif schema == 2:
        evidence.exercise(report["measurement"], mode, client_count=clients)
    else:
        return mode == "correctness" and correctness_result(report.get("measurement"))
    return True


def profile_options(directory: Path, mode: str) -> list[str]:
    need(mode in ("steady", "large", "correctness", "churn"), "Invalid profile workload")
    if mode != "steady":
        return []
    # A short CPU/wait sample inside the original full workload, NOT a shorter
    # capacity mode. No attach, GC/heap/priority tuning or payload events.
    # Parsing occurs only after the measured JVM has exited. Raw JFR stays private.
    need(all(c not in str(directory) and c not in str(ROOT) for c in (",", "\n", "\r")),
         "Profile paths must not contain JVM option separators")
    for name in ("runtime-profile.jfr", "runtime-profile.json", "profile-analysis.log", "jfr-repository"):
        need(not (directory / name).exists() and not (directory / name).is_symlink(), "Fresh profiling evidence required")
    return ["-XX:FlightRecorderOptions=repository=" + str(directory / "jfr-repository"),
            "-XX:StartFlightRecording=settings=" + str(ROOT / "scripts/rpc-capacity-profile.jfc") +
            ",filename=" + str(directory / "runtime-profile.jfr") +
            ",delay=120s,duration=180s,maxsize=32m,disk=true,dumponexit=true"]


def execute(directory: Path, role: str, mode: str, source: str, cpu_placement: str = cpu.INHERITED) -> int:
    values = configuration(parse(read_private(directory / "config.txt")), source)
    need(values["role"] == role, "Role mismatch")
    java = Path(os.environ["JAVA_HOME"]) / "bin/java"
    main, arguments = workload_entrypoint(role, mode, int(values["schema"]))
    scoped_options, scoped_binding = native_options(source)
    # Bounded GC/safepoint observations only: no GC, heap, priority or deadline tuning.
    # Raw runtime logs remain private and are never hosted-artifact inputs.
    trace = directory / "jvm-timing.log"
    need(not trace.exists(), "Fresh JVM timing evidence required")
    argv = [str(java), "-Xms128m", "-Xmx2048m",
            "-Xlog:gc*,safepoint:file=" + str(trace) + ":time,uptimenanos,level,tags:filecount=4,filesize=8M",
            *profile_options(directory, mode), *scoped_options, "-cp", classpath(source), main, *arguments]
    env = {**os.environ, "RPC_CAPACITY_LAB_CONFIG": str(directory / "config.txt")}
    report = {"schema": 1, "scope": "SYNTHETIC_CAPACITY_NOT_QUALIFICATION", "role": role, "mode": mode,
              "sourceSha": source, "runLabel": values["runLabel"], "status": "FAIL", "capacityQualified": False,
              "launcherSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if scoped_binding is not None:
        report["macosNative"] = scoped_binding
    if values["schema"] == "2":
        report.update(schema=2, clientCount=int(values["clientCount"]))
    started = time.monotonic()
    try:
        placement = cpu.begin(cpu_placement, role)
        if placement is not None:
            report["cpuPlacement"] = placement
        with (directory / "jvm.log").open("xb") as log:
            # Native executor owns all subprocess lifetimes. Never replace that with PID/group signaling.
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            selector = selectors.DefaultSelector()
            need(child.stdout is not None, "Missing JVM output pipe")
            selector.register(child.stdout, selectors.EVENT_READ)
            total, partial = 0, b""
            next_cpu_observation = 0.0
            try:
                while selector.get_map():
                    need(time.monotonic() - started < 2450, "Launcher deadline; native executor must drain")
                    if time.monotonic() >= next_cpu_observation:
                        cpu.observe_child(placement, child)
                        next_cpu_observation = time.monotonic() + 1
                    for key, _ in selector.select(1):
                        block = os.read(key.fileobj.fileno(), 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        total += len(block)
                        need(total <= 8 * 1024 * 1024, "JVM log bound exceeded")
                        log.write(block)
                        partial += block
                        while b"\n" in partial:
                            line, partial = partial.split(b"\n", 1)
                            capture_capacity_record(report, line, int(values["schema"]), role, mode)
                        need(len(partial) <= LIMIT, "Unbounded JVM output line")
                report["exitCode"] = child.wait(timeout=10)
                report["elapsedSeconds"] = round(time.monotonic() - started, 3)
                cpu.finish(placement)
                if mode == "steady":
                    # This child is inside the SAME native-owned invocation; do
                    # not use jcmd/attach, PID-based selection or unowned cleanup.
                    # Preserve failed workload exit codes; profiling cannot turn
                    # a failed full-rate workload into a pass.
                    with (directory / "profile-analysis.log").open("xb") as profile_log:
                        profile = subprocess.Popen([str(java), "-Xms32m", "-Xmx256m", "-cp", classpath(source),
                            "dev.p2pkit.sample.rpc.lab.LabJfrProfileKt", "--owner-authorized-capacity-profile", role],
                            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=profile_log,
                            stderr=subprocess.STDOUT)
                        profile_code = profile.wait(timeout=60)  # Native owner drains on timeout; no raw-PID kill.
                    need(profile_code == 0 and (directory / "profile-analysis.log").stat().st_size <= LIMIT,
                         "Incomplete bounded runtime profile")
                    report["profileSha256"] = hashlib.sha256(read_private(directory / "runtime-profile.json")).hexdigest()
                if role == "host":
                    complete = report["exitCode"] == 0 and parse(read_private(directory / "host-closed.txt")) == {
                        "closed": "true", "fixturesRemoved": "true"}
                else:
                    complete = completed_client_results(report, values, mode)
                    if complete and values["schema"] == "2" and mode == "steady":
                        idle = report["connectedIdle"]
                        ready = parse(read_private(directory / "host-ready.txt"))
                        need(idle["driverArtifactSha256"] ==
                             hashlib.sha256(read_private(directory / "artifact-manifest.txt")).hexdigest() and
                             idle["hostArtifactSha256"] == ready.get("hostArtifactSha256", ready.get("artifactSha256")),
                             "Connected-idle bytes differ from the prepared driver or admitted host artifact")
                if complete:
                    report["status"] = "PENDING_RESOURCE_AND_NETWORK_REVIEW"
                return 0 if complete else 1
            finally:
                selector.close()
                child.stdout.close()
    finally:
        write_private(directory / "launcher-result.json", (json.dumps(report, indent=2) + "\n").encode())
        print(json.dumps({key: report[key] for key in ("role", "mode", "status", "sourceSha", "capacityQualified")}))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "run", "import-control", "stop"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--role", choices=("host", "client"))
    parser.add_argument("--mode", choices=("steady", "large", "correctness", "churn"), default="steady")
    parser.add_argument("--cpu-placement", choices=cpu.POLICIES, default=cpu.INHERITED,
                        help="Explicit same-host resource experiment; never a production dispatcher override")
    parser.add_argument("--settings", type=Path, help="Private control-format config for prepare; sourceSha must match")
    parser.add_argument("--name", choices=sorted(CONTROL_NAMES))
    args = parser.parse_args()
    state, source = owned_context()
    work = private_directory(state / "work")
    need(args.directory.parent == work and re.fullmatch(r"[a-z0-9-]{1,64}", args.directory.name),
         "Only a named direct child of this invocation's private work directory is allowed")
    if args.operation == "prepare":
        need(args.settings is not None, "Explicit private machine configuration required")
        values = configuration(parse(read_private(args.settings)), source)
        args.directory.mkdir(mode=0o700)
        write_private(args.directory / "config.txt", encode(values))
        return 0
    directory = private_directory(args.directory)
    if args.operation == "run":
        need(args.role is not None, "Explicit host/client role required")
        return execute(directory, args.role, args.mode, source, args.cpu_placement)
    if args.operation == "stop":
        write_private(directory / "stop.txt", b"stop=true\n")
        return 0
    need(args.name is not None, "Explicit non-secret control file name required")
    data = sys.stdin.buffer.read(LIMIT + 1)
    need(len(data) <= LIMIT, "Control transfer exceeds bound")
    if args.name == "client-pins.txt":
        values = configuration(parse(read_private(directory / "config.txt")), source)
        count = int(values.get("clientCount", "128"))
        pins = data.decode("ascii").splitlines()
        need(len(pins) == len(set(pins)) == count and
             all(re.fullmatch(r"p2f1-[a-z2-7]{52}", pin) for pin in pins),
             "Exactly the configured cohort of distinct public test pins is required")
    else:
        parse(data)
    write_private(directory / args.name, data, replace=args.name == "host-telemetry.txt")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Never print raw configurations, arbitrary subprocess errors or security material.
        print("CAPACITY_LAB_ABORTED: " + type(error).__name__ + "; inspect owned evidence", file=sys.stderr)
        raise SystemExit(1)
