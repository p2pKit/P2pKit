#!/usr/bin/env python3
"""Real authenticated RPC 128/256 comparison on a private virtual link, not mobile/physical qualification.

Prepare :p2p-sample-rpc:prepareRpcCapacityLab from clean source first. Run this opt-in
tool with namespace-setup privilege; the two JVMs run with all capabilities dropped.
No host interfaces, routes, firewall, DNS, credentials or production profiles are changed.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import selectors
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rpc_virtual_link", ROOT / "scripts/run-rpc-same-host-lab.py")
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)
need = link.need
LIMIT = 8 * 1024 * 1024
PREFIX = b"RPC_IO_BENCHMARK_JSON:"


def run(command, **kwargs):
    return subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=20, **kwargs).stdout


def verified_distribution(directory):
    source = run(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    need(not run(["git", "status", "--porcelain=v1"], cwd=ROOT), "Clean exact source required")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    need(manifest.get("schema") == 1 and manifest.get("sourceSha") == source and
         manifest.get("scope") == "SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION", "Wrong lab source manifest")
    files = sorted(directory.glob("*.jar"))
    need(0 < len(files) <= 128 and len(manifest["entries"]) == len(files), "Wrong lab JAR inventory")
    for file, entry in zip(files, manifest["entries"]):
        need(file.is_file() and not file.is_symlink() and file.name == entry["name"] and
             hashlib.sha256(file.read_bytes()).hexdigest() == entry["sha256"], "Lab JAR integrity mismatch")
    return source, os.pathsep.join(str(file) for file in files)


@contextlib.contextmanager
def namespace(fd):
    original = os.open("/proc/self/ns/net", os.O_RDONLY | os.O_CLOEXEC)
    try:
        os.setns(fd, os.CLONE_NEWNET)
        yield
    finally:
        try:
            os.setns(original, os.CLONE_NEWNET)
        finally:
            os.close(original)


@contextlib.contextmanager
def virtual_link():
    link.namespace_runtime_admission()
    descriptors = {}
    original = os.open("/proc/self/ns/net", os.O_RDONLY | os.O_CLOEXEC)
    try:
        for role in ("host", "client"):
            os.unshare(os.CLONE_NEWNET)
            descriptors[role] = os.open("/proc/self/ns/net", os.O_RDONLY | os.O_CLOEXEC)
            need(os.fstat(descriptors[role]).st_ino != os.fstat(original).st_ino, "Network namespace not isolated")
            os.setns(original, os.CLONE_NEWNET)
        with namespace(descriptors["host"]):
            run(["ip", "link", "add", link.INTERFACE, "type", "veth", "peer", "name", "rpc-peer"])
            target = descriptors["client"]
            run(["ip", "link", "set", "rpc-peer", "netns", f"/proc/self/fd/{target}"], pass_fds=(target,))
        observations = {}
        for role, fd in descriptors.items():
            with namespace(fd):
                if role == "client":
                    run(["ip", "link", "set", "rpc-peer", "name", link.INTERFACE])
                run(["ip", "addr", "add", link.ADDRESSES[role] + "/30", "dev", link.INTERFACE])
                run(["ip", "link", "set", "lo", "up"])
                run(["ip", "link", "set", link.INTERFACE, "up"])
        for role, fd in descriptors.items():
            with namespace(fd):
                values = [json.loads(run(["ip", "-d", "-j", kind])) for kind in ("link", "route", "addr")]
                link.topology_admission(*values, role)
                observations[role] = values
        yield descriptors, observations
    finally:
        try:
            os.setns(original, os.CLONE_NEWNET)
        finally:
            for fd in descriptors.values():
                os.close(fd)
            os.close(original)  # Anonymous namespaces/veth disappear after the last original owner closes.


def private_write(path, data, uid, gid):
    temporary = path.with_name(path.name + ".next")
    with temporary.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        os.fchown(stream.fileno(), uid, gid)
        stream.write(data)
    temporary.replace(path)


def fields(data):
    lines = data.decode("ascii").splitlines()
    values = dict(line.split("=", 1) for line in lines)
    need(len(values) == len(lines), "Duplicate host telemetry fields")
    return values


def validate_result(raw, source, clients, seconds):
    lines = [line[len(PREFIX):] for line in raw.splitlines() if line.startswith(PREFIX)]
    need(len(lines) == 1, "Exactly one completed RPC benchmark is required")
    result = json.loads(lines[0])
    need(result.get("schema") == 2 and result.get("source") == source and result.get("cleanup") is True and
         result.get("scope") == "AUTHENTICATED_RPC_LAB_NOT_PHYSICAL_OR_MOBILE_QUALIFICATION", "Wrong benchmark scope")
    values = result["measurements"]
    need(values["clients"] == clients and values["seconds"] == seconds and
         values["responses"] == clients * seconds * 10, "Incomplete authenticated workload")
    required = {"clients", "seconds", "responses", "activeWallNs", "late100msSlots",
                "hostThreadsBeforeConnections", "hostThreadsIdle", "hostThreadsAfter",
                "hostRssBeforeBytes", "hostRssIdleBytes", "hostRssAfterBytes", "hostIdleWallMs",
                "hostSteadyIdleStartMs", "hostSteadyIdleWallMs", "hostSteadyIdleCpuNs",
                "hostSteadyIdleThreads", "hostSteadyIdleRssBytes",
                "hostIdleCpuNs", "hostActiveCpuNs", "hostActiveWallMs", "hostRetainedRecords", "hostPayloadBytes"}
    need(set(values) == required and all(type(value) is int and value >= 0 for value in values.values()),
         "Invalid/missing benchmark measurement")
    need(values["activeWallNs"] > 0 and values["hostActiveWallMs"] > 0 and values["hostIdleWallMs"] >= 5_000 and
         values["hostSteadyIdleStartMs"] > 0 and values["hostSteadyIdleWallMs"] >= 30_000,
         "Missing observed idle/active duration")
    latency = result["latencyUpperMs"]
    need(set(latency) == {"p50", "p95", "p99", "max"} and
         all(type(value) is int and 0 <= value <= 30_001 for value in latency.values()) and
         latency["p50"] <= latency["p95"] <= latency["p99"] <= latency["max"],
         "Missing actual latency measurements")
    return result


class Jvm:
    def __init__(self, role, net, directory, java, classpath, arguments, uid, gid, profile):
        self.output = bytearray()
        self.log = (directory / "process.log").open("xb")
        os.fchmod(self.log.fileno(), 0o600)
        os.fchown(self.log.fileno(), uid, gid)
        main = "LabHostKt" if role == "host" else "LabIoBenchmarkKt"
        environment = {"PATH": "/usr/bin:/bin", "HOME": pwd.getpwuid(uid).pw_dir,
                       "RPC_CAPACITY_LAB_AUTHORIZED": "synthetic-private-network-only",
                       "RPC_CAPACITY_LAB_CONFIG": str(directory / "config.txt")}
        self.process = None
        self.selector = selectors.DefaultSelector()
        try:
            diagnostic = []
            if profile and role == "host":
                # Existing reviewed sampling-only configuration: no payload, exception, environment,
                # network address or file-content events. Raw JFR never leaves the private output.
                diagnostic = ["-XX:StartFlightRecording=name=rpc-io,settings=" +
                    str(ROOT / "scripts/rpc-capacity-profile.jfc") + ",filename=" +
                    str(directory / "cpu-profile.jfr") + ",maxsize=32m,dumponexit=true"]
            with namespace(net):
                self.process = subprocess.Popen([
                    *link.drop_command(uid, gid), str(java), "-Xms128m", "-Xmx768m",
                    *diagnostic,
                    "-cp", classpath, "dev.p2pkit.sample.rpc.lab." + main, *arguments,
                ], env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
        except BaseException:
            self.close()
            raise

    def pump(self):
        for key, _ in self.selector.select(0):
            block = os.read(key.fileobj.fileno(), 65_536)
            if not block:
                self.selector.unregister(key.fileobj)
            else:
                self.output.extend(block)
                self.log.write(block)
                need(len(self.output) <= LIMIT, "Bounded synthetic JVM log exceeded")

    def close(self):
        # Popen retains original child ownership; no borrowed/reconstructed PID is signaling authority.
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.pump()
            self.process.stdout.close()
        self.selector.close()
        self.log.close()


def experiment(output, source, classpath, java, clients, seconds, uid, gid, profile):
    directory = output / f"clients-{clients}"
    directory.mkdir(mode=0o700)
    os.chown(directory, uid, gid)
    roles = {}
    for role in ("host", "client"):
        path = directory / role
        path.mkdir(mode=0o700)
        os.chown(path, uid, gid)
        roles[role] = path
        config = dict(schema="2", clientCount=str(clients), role=role, runLabel=f"io-{clients}", sourceSha=source,
                      endpointAddress=link.ADDRESSES["host"], port="29872", subnets=link.SUBNET,
                      interface=link.INTERFACE, localAddress=link.ADDRESSES[role])
        private_write(path / "config.txt", "".join(f"{key}={value}\n" for key, value in config.items()).encode(), uid, gid)
    with virtual_link() as (networks, topology), contextlib.ExitStack() as owners:
        private_write(directory / "topology.json", json.dumps(topology).encode(), uid, gid)
        driver = Jvm("client", networks["client"], roles["client"], java, classpath,
                     ["--owner-authorized-io-benchmark", str(seconds)], uid, gid, profile)
        owners.callback(driver.close)
        host = None
        deadline = time.monotonic() + seconds + 420

        def tick():
            need(time.monotonic() < deadline, "Bounded RPC experiment deadline expired")
            driver.pump()
            if host:
                host.pump()
            time.sleep(0.025)

        pins = roles["client"] / "client-pins.txt"
        while not pins.is_file():
            need(driver.process.poll() is None, "Client fixture preparation failed; inspect private process.log")
            tick()
        private_write(roles["host"] / pins.name, pins.read_bytes(), uid, gid)
        host = Jvm("host", networks["host"], roles["host"], java, classpath,
                   ["--owner-authorized-capacity-host"], uid, gid, profile)
        owners.callback(host.close)
        copied = {}
        while driver.process.poll() is None:
            need(host.process.poll() is None, "Host failed; inspect private process.log")
            for name in ("host-ready.txt", "host-telemetry.txt"):
                file = roles["host"] / name
                if file.is_file():
                    content = file.read_bytes()
                    if content != copied.get(name):
                        private_write(roles["client"] / name, content, uid, gid)
                        copied[name] = content
            tick()
        driver.pump()
        need(driver.process.returncode == 0, "RPC benchmark failed; inspect private process.log")
        result = validate_result(driver.output, source, clients, seconds)
        need(fields((roles["client"] / "clients-closed.txt").read_bytes()) ==
             {"closed": "true", "fixturesRemoved": "true"}, "Client ownership not retired")

        def sample():
            values = fields((roles["host"] / "host-telemetry.txt").read_bytes())
            need(values.pop("schema") == "1" and values.pop("runLabel") == f"io-{clients}", "Wrong telemetry owner")
            return {key: int(value) for key, value in values.items()}

        before = sample()
        while any(before[key] for key in ("connected", "running", "queued")):
            need(host.process.poll() is None, "Host failed during retirement")
            tick()
            before = sample()
        after = before
        while after["uptimeMillis"] - before["uptimeMillis"] < link.COOLDOWN_MILLIS:
            need(host.process.poll() is None, "Host failed during retention observation")
            tick()
            after = sample()
        result["retention"] = link.retention_admission(before, after)
        private_write(roles["host"] / "stop.txt", b"stop=true\n", uid, gid)
        while host.process.poll() is None:
            tick()
        host.pump()
        need(host.process.returncode == 0 and fields((roles["host"] / "host-closed.txt").read_bytes()) ==
             {"closed": "true", "fixturesRemoved": "true"}, "Host cleanup or final exit failed")
        result["hostExit"] = host.process.returncode
        result["driverExit"] = driver.process.returncode
        result["jvmUidMode"] = "root-uid-no-capabilities" if uid == 0 else "ordinary-user-no-capabilities"
        result["hostSamplingProfile"] = profile
        private_write(directory / "result.json", (json.dumps(result, indent=2) + "\n").encode(), uid, gid)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution", type=Path,
                        default=ROOT / "samples/p2p-sample-rpc/build/capacity-lab")
    parser.add_argument("--output", type=Path, required=True, help="New private output directory (must not exist)")
    parser.add_argument("--seconds", type=int, default=120, choices=range(60, 301), metavar="60..300")
    parser.add_argument("--clients", choices=("128", "256", "both"), default="both")
    parser.add_argument("--profile", action="store_true", help="Opt-in private bounded host JFR CPU sampling")
    args = parser.parse_args()
    need(sys.platform == "linux" and os.geteuid() == 0, "Linux namespace setup privilege required")
    uid, gid = int(os.environ.get("SUDO_UID", "0")), int(os.environ.get("SUDO_GID", "0"))
    need(pwd.getpwuid(uid).pw_gid == gid, "Original invoking account required")
    java = Path(os.environ["JAVA_HOME"]) / "bin/java"
    need(java.is_file(), "Explicit reviewed JAVA_HOME required")
    source, classpath = verified_distribution(args.distribution.resolve(strict=True))
    output = args.output.absolute()
    need(output == output.resolve() and not output.exists(), "New canonical output directory required")
    output.mkdir(mode=0o700)
    os.chown(output, uid, gid)
    results = [experiment(output, source, classpath, java, count, args.seconds, uid, gid, args.profile)
               for count in ((128, 256) if args.clients == "both" else (int(args.clients),))]
    manifest = {"schema": 1, "source": source, "scope": link.SCOPE, "results": results,
                "platform": os.uname().sysname + " " + os.uname().release + " " + os.uname().machine,
                "logicalProcessors": os.cpu_count(), "java": str(java),
                "files": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(output.rglob("*")) if path.is_file()}}
    private_write(output / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), uid, gid)
    print(f"RPC_IO_COMPARISON_COMPLETE source={source} output={output}; virtual link, not mobile qualification")


if __name__ == "__main__":
    main()
