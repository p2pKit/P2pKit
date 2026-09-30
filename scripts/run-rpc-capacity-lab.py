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
import re
import selectors
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 262_144
AUTHORIZATION = "synthetic-private-network-only"
CONTROL_NAMES = {"client-pins.txt", "host-ready.txt", "host-telemetry.txt", "host-failed.txt", "stop.txt"}
FIELDS = {"schema", "role", "runLabel", "sourceSha", "endpointAddress", "port", "subnets", "interface", "localAddress"}
CORRECTNESS_CASES = ("concurrent-correlation", "application-error", "procedure-authorization",
                     "sent-deadline", "sent-cancellation", "close-during-call")


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


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
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        actual = os.fstat(stream.fileno())
        need((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino), "Control file lifetime changed")
        data = stream.read(LIMIT + 1)
    need(len(data) <= LIMIT, "Oversized control file")
    return data


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
    need(values.keys() == FIELDS and values["schema"] == "1", "Exact configuration schema required")
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


def classpath(source: str) -> str:
    directory = ROOT / "samples/p2p-sample-rpc/build/capacity-lab"
    need(directory.is_dir() and not directory.is_symlink(), "Run prepareRpcCapacityLab in the admitted candidate first")
    manifest_file = directory / "manifest.json"
    need(manifest_file.is_file() and not manifest_file.is_symlink() and manifest_file.stat().st_size <= LIMIT,
         "Missing bounded distribution provenance")
    manifest = json.loads(manifest_file.read_bytes())
    need(manifest["schema"] == 1 and manifest["sourceSha"] == source and
         manifest["scope"] == "SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION", "Wrong distribution source/scope")
    jars = sorted(path for path in directory.iterdir() if path != manifest_file)
    need(1 <= len(jars) <= 128 and all(path.suffix == ".jar" and path.is_file() and not path.is_symlink()
                                    for path in jars), "Unexpected prepared runtime entry")
    need(sum(path.stat().st_size for path in jars) <= 256 * 1024 * 1024, "Runtime exceeds bounded distribution size")
    actual = [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in jars]
    need(actual == manifest["entries"], "Prepared runtime bytes/order changed")
    return os.pathsep.join(str(path) for path in jars)


def workload_entrypoint(role, mode):
    need(role in ("host", "client") and mode in ("steady", "large", "correctness"), "Unknown lab workload/role")
    if mode == "correctness":
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


def execute(directory: Path, role: str, mode: str, source: str) -> int:
    values = configuration(parse(read_private(directory / "config.txt")), source)
    need(values["role"] == role, "Role mismatch")
    java = Path(os.environ["JAVA_HOME"]) / "bin/java"
    main, arguments = workload_entrypoint(role, mode)
    # Bounded GC/safepoint observations only: no GC, heap, priority or deadline tuning.
    # Raw runtime logs remain private and are never hosted-artifact inputs.
    trace = directory / "jvm-timing.log"
    need(not trace.exists(), "Fresh JVM timing evidence required")
    argv = [str(java), "-Xms128m", "-Xmx2048m",
            "-Xlog:gc*,safepoint:file=" + str(trace) + ":time,uptimenanos,level,tags:filecount=4,filesize=8M",
            "-cp", classpath(source), main, *arguments]
    env = {**os.environ, "RPC_CAPACITY_LAB_CONFIG": str(directory / "config.txt")}
    report = {"schema": 1, "scope": "SYNTHETIC_CAPACITY_NOT_QUALIFICATION", "role": role, "mode": mode,
              "sourceSha": source, "runLabel": values["runLabel"], "status": "FAIL", "capacityQualified": False,
              "launcherSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    started = time.monotonic()
    try:
        with (directory / "jvm.log").open("xb") as log:
            # Native executor owns all subprocess lifetimes. Never replace that with PID/group signaling.
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            selector = selectors.DefaultSelector()
            need(child.stdout is not None, "Missing JVM output pipe")
            selector.register(child.stdout, selectors.EVENT_READ)
            total, partial = 0, b""
            try:
                while selector.get_map():
                    need(time.monotonic() - started < 2450, "Launcher deadline; native executor must drain")
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
                            for prefix, field in ((b"RPC_CAPACITY_RESULT_JSON:", "measurement"),
                                                  (b"RPC_CAPACITY_FINAL_JSON:", "cleanup")):
                                if line.startswith(prefix):
                                    need(field not in report and len(line) <= LIMIT, "Duplicate/oversized result record")
                                    report[field] = json.loads(line[len(prefix):])
                        need(len(partial) <= LIMIT, "Unbounded JVM output line")
                report["exitCode"] = child.wait(timeout=10)
                report["elapsedSeconds"] = round(time.monotonic() - started, 3)
                if role == "host":
                    complete = report["exitCode"] == 0 and parse(read_private(directory / "host-closed.txt")) == {
                        "closed": "true", "fixturesRemoved": "true"}
                else:
                    cleanup = report.get("cleanup", {})
                    complete = (report["exitCode"] == 0 and cleanup.get("cleanupVerified") is True and
                                cleanup.get("mechanicalChecksPassed") is True and
                                report.get("measurement", {}).get("status") == "PENDING_RESOURCE_AND_NETWORK_REVIEW")
                    if mode == "correctness":
                        complete = complete and correctness_result(report.get("measurement"))
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
    parser.add_argument("--mode", choices=("steady", "large", "correctness"), default="steady")
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
        return execute(directory, args.role, args.mode, source)
    if args.operation == "stop":
        write_private(directory / "stop.txt", b"stop=true\n")
        return 0
    need(args.name is not None, "Explicit non-secret control file name required")
    data = sys.stdin.buffer.read(LIMIT + 1)
    need(len(data) <= LIMIT, "Control transfer exceeds bound")
    if args.name == "client-pins.txt":
        pins = data.decode("ascii").splitlines()
        need(len(pins) == len(set(pins)) == 128 and
             all(re.fullmatch(r"p2f1-[a-z2-7]{52}", pin) for pin in pins), "Exactly 128 distinct public test pins required")
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
