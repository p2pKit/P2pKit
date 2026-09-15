#!/usr/bin/env python3
"""Sample the hosted writer's resource limits; not a network/filesystem quota.

The established native command scope owns this helper and its bounded system-tool
children. Two independent lanes emit completed samples, not speculative heartbeats.
Original command bytes go only to private stderr; stdout is a finite JSONL schema.
No downloads, recursive disk walks, native ABI definitions or process-name kills.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_processes

GIB = 1024 ** 3
START_FREE, FREE_FLOOR, SWAP_LIMIT, INBOUND_LIMIT = 16 * GIB, 7 * GIB, GIB, 8 * GIB
QUERY_SECONDS, TOOL_BYTES = 2.0, 1024 * 1024
INTERVALS = {"fast": 2.0, "network": 5.0}
STALE = {"fast": 5.0, "network": 8.0}
UINT64 = (1 << 64) - 1
SCHEMA, NS_PER_SECOND = 2, 1_000_000_000
RAW_CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
NET_HEADER = "Name Mtu Network Address Ipkts Ierrs Ibytes Opkts Oerrs Obytes Coll".split()


class ResourceError(ValueError):
    def __init__(self, code, sample=None):
        super().__init__(code)
        self.code, self.sample = code, sample


def require(condition, code, sample=None):
    if not condition:
        raise ResourceError(code, sample)


def shared_raw_ns():
    # Python 3.9/macOS time.monotonic() has a process-local epoch. Only this
    # explicitly shared kernel clock may cross the observer/controller boundary.
    require(sys.platform == "darwin" and callable(getattr(time, "clock_gettime_ns", None)) and
            type(getattr(time, "CLOCK_MONOTONIC_RAW", None)) is int, "RAW_CLOCK_UNAVAILABLE")
    value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    require(type(value) is int and 0 <= value <= UINT64, "RAW_CLOCK_VALUE")
    return value


def check_shared_freshness(samples):
    require(type(samples) is dict and set(samples) == set(STALE), "RESOURCE_LANES")
    now = shared_raw_ns()
    for lane, seconds in STALE.items():
        row = samples[lane]
        require(type(row) is dict and type(row.get("schema")) is int and row["schema"] == SCHEMA and
                row.get("kind") == "resource-sample" and row.get("lane") == lane and
                row.get("clockDomain") == RAW_CLOCK_DOMAIN, "SAMPLE_CLOCK")
        observed = row.get("observedRawNs")
        require(type(observed) is int and 0 <= observed <= UINT64, "SAMPLE_RAW_TIME")
        age = now - observed
        require(0 <= age <= int(seconds * NS_PER_SECOND), "LANE_STALE",
                {"staleLane": lane, "ageNanoseconds": age, "limitNanoseconds": int(seconds * NS_PER_SECOND)})


def unsigned(value, code):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value), code)
    result = int(value)
    require(result <= UINT64, code)
    return result


def parse_pressure(raw):
    require(re.fullmatch(r"[124]\n?", raw), "PRESSURE_FORMAT")
    return int(raw.strip())


def parse_vm(raw):
    pages = re.findall(r"^Mach Virtual Memory Statistics: \(page size of ([0-9]+) bytes\)$", raw, re.M)
    swaps = re.findall(r"^Swapouts:\s+([0-9]+)\.\s*$", raw, re.M)
    require(len(pages) == len(swaps) == 1, "VM_FIELDS")
    page, count = unsigned(pages[0], "VM_PAGE"), unsigned(swaps[0], "VM_COUNTER")
    require(0 < page <= 1024 * 1024 and page & (page - 1) == 0, "VM_PAGE")
    require(count * page <= UINT64, "VM_COUNTER")
    return {"pageSize": page, "swapoutBytes": count * page}


def parse_netstat(raw):
    """Use link rows only; address-family rows duplicate the same Ibytes counter."""
    lines = [line.split() for line in raw.splitlines() if line.strip()]
    require(1 < len(lines) <= 8192 and lines[0] == NET_HEADER and
            sum(row == NET_HEADER for row in lines) == 1, "NETWORK_HEADER")
    counters, names = {}, set()
    for row in lines[1:]:
        if not any("<Link#" in item for item in row):
            continue
        require(len(row) in (10, 11) and re.fullmatch(r"<Link#[1-9][0-9]{0,19}>", row[2]),
                "NETWORK_LINK_ROW")
        name = row[0].removesuffix("*")
        require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}", name), "NETWORK_NAME")
        unsigned(row[1], "NETWORK_MTU")
        unsigned(row[2][6:-1], "NETWORK_LINK_ID")
        require(name not in names, "NETWORK_DUPLICATE_LINK")
        names.add(name)
        tail = row[-7:]
        require(all(value == "-" or re.fullmatch(r"[0-9]{1,20}", value) for value in tail),
                "NETWORK_COLUMNS")
        received = unsigned(tail[2], "NETWORK_COUNTER")
        if not re.fullmatch(r"lo[0-9]+", name):
            counters[(name, row[2])] = received
    require(counters, "NETWORK_NO_NONLO_LINK")
    return counters


class Streams:
    def __init__(self, output=None, errors=None):
        self.output = output if output is not None else sys.stdout
        self.errors = errors if errors is not None else sys.stderr
        self.lock = threading.Lock()

    def sample(self, row):
        with self.lock:
            print(json.dumps({"schema": SCHEMA, **row}, sort_keys=True, allow_nan=False), file=self.output, flush=True)

    def original(self, label, argv, code, out, err, timed_out):
        stdout, stderr = out if out is not None else b"", err if err is not None else b""
        require(isinstance(stdout, bytes) and isinstance(stderr, bytes), "QUERY_BYTES")
        kept_out, kept_err = stdout[:TOOL_BYTES], stderr[:max(0, TOOL_BYTES - len(stdout))]
        truncated = len(kept_out) != len(stdout) or len(kept_err) != len(stderr)
        packet = {"nativeQuery": {"label": label, "argv": argv, "exitCode": code, "timedOut": timed_out,
                  "stdoutPresent": out is not None, "stderrPresent": err is not None,
                  "stdoutBytes": len(stdout), "stderrBytes": len(stderr), "truncated": truncated,
                  "stdoutBase64": base64.b64encode(kept_out).decode("ascii"),
                  "stderrBase64": base64.b64encode(kept_err).decode("ascii")}}
        with self.lock:
            print(json.dumps(packet, sort_keys=True), file=self.errors, flush=True)
        require(not truncated, "QUERY_SIZE")


def query(label, argv, deadline, streams, call=subprocess.run, clock=time.monotonic):
    remaining = deadline - clock()
    require(remaining > 0, "QUERY_DEADLINE")
    try:
        # Inherit the genuine native ownership markers unchanged. System utilities
        # are fixed argv, never a shell or an arbitrary user-supplied command.
        result = call(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      timeout=remaining, check=False)
    except subprocess.TimeoutExpired as error:
        streams.original(label, argv, None, error.stdout, error.stderr, True)
        raise ResourceError("QUERY_TIMEOUT") from error
    streams.original(label, argv, result.returncode, result.stdout, result.stderr, False)
    require(clock() <= deadline, "QUERY_DEADLINE")
    require(result.returncode == 0, "QUERY_EXIT")
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ResourceError("QUERY_ENCODING") from error


def physical_directory(path):
    require(path.is_absolute() and ".." not in path.parts, "PATH_ABSOLUTE")
    for candidate in (path, *path.parents):
        require(not stat.S_ISLNK(candidate.lstat().st_mode), "PATH_LINK")
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), "PATH_OWNER")
    return info.st_dev, info.st_ino


def validate_paths(root, state, stop_file, env):
    roots = {path: physical_directory(path) for path in (root, state)}
    require(root != state and root not in state.parents and state not in root.parents, "PATH_OVERLAP")
    require(stop_file == state / "resource-stop" and not os.path.lexists(stop_file), "STOP_PATH")
    home = state / "gradle-home"
    physical_directory(home)
    domains = audit_processes.ownership_domains(env.get(audit_processes.CHAIN_ENV, ""),
                                                env.get(audit_processes.DOMAINS_ENV, ""))
    require(domains and domains[-1]["job"] == env.get(audit_processes.JOB_ENV) and
            domains[-1]["state"] == env.get(audit_processes.STATE_ENV) == str(state) and
            domains[-1]["home"] == env.get("GRADLE_USER_HOME") == str(home), "OWNERSHIP_DOMAIN")
    return roots


def stop_requested(stop_file):
    try:
        info = stop_file.lstat()
    except FileNotFoundError:
        return False
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
            info.st_size == 0 and info.st_mode & 0o077 == 0, "STOP_FILE")
    return True


def fast_frame(roots, streams, call=subprocess.run, statvfs=os.statvfs, clock=time.monotonic):
    started = clock()
    deadline = started + QUERY_SECONDS
    pressure = parse_pressure(query("pressure", ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
                                    deadline, streams, call, clock))
    vm = parse_vm(query("vm", ["/usr/bin/vm_stat"], deadline, streams, call, clock))
    available = []
    for path, identity in roots.items():
        require(physical_directory(path) == identity, "RESOURCE_ROOT_CHANGED")
        value = statvfs(path)
        require(value.f_frsize > 0 and value.f_bavail >= 0, "FILESYSTEM_COUNTER")
        available.append(value.f_frsize * value.f_bavail)
        require(clock() <= deadline, "QUERY_DEADLINE")
    observed = clock()
    require(observed <= deadline, "QUERY_DEADLINE")
    return {"startedLocalMonotonic": started, "observedLocalMonotonic": observed, "pressure": pressure,
            "clockDomain": RAW_CLOCK_DOMAIN, "observedRawNs": shared_raw_ns(),
            "availableBytes": min(available), **vm}


def network_frame(streams, call=subprocess.run, clock=time.monotonic):
    started = clock()
    counters = parse_netstat(query("network", ["/usr/sbin/netstat", "-ibn"], started + QUERY_SECONDS,
                                   streams, call, clock))
    observed = clock()
    require(observed <= started + QUERY_SECONDS, "QUERY_DEADLINE")
    return {"startedLocalMonotonic": started, "observedLocalMonotonic": observed, "counters": counters,
            "clockDomain": RAW_CLOCK_DOMAIN, "observedRawNs": shared_raw_ns()}


class FastPolicy:
    def __init__(self):
        self.first = self.previous = None

    def accept(self, frame):
        row = {**frame, "admitted": self.first is None,
               "swapoutIncreaseBytes": 0 if self.first is None else frame["swapoutBytes"] - self.first["swapoutBytes"]}
        require(frame["pressure"] == 1 if self.first is None else frame["pressure"] in (1, 2), "MEMORY_PRESSURE", row)
        require(frame["availableBytes"] >= (START_FREE if self.first is None else FREE_FLOOR), "DISK_FLOOR", row)
        require(self.previous is None or frame["pageSize"] == self.previous["pageSize"] and
                frame["swapoutBytes"] >= self.previous["swapoutBytes"], "SWAP_COUNTER_RESET", row)
        require(row["swapoutIncreaseBytes"] < SWAP_LIMIT, "SWAP_LIMIT", row)
        self.first, self.previous = self.first if self.first is not None else dict(frame), dict(frame)
        return row


class NetworkPolicy:
    def __init__(self):
        self.previous, self.increase = None, 0

    def accept(self, frame):
        counters = frame["counters"]
        row = {key: value for key, value in frame.items() if key != "counters"}
        row.update(admitted=self.previous is None, interfaceCount=len(counters),
                   inboundBytes=sum(counters.values()), inboundIncreaseBytes=self.increase, newInterfaceCount=0)
        if self.previous is not None:
            require(self.previous.keys() <= counters.keys(), "NETWORK_INTERFACE_DISAPPEARED", row)
            require(all(counters[key] >= value for key, value in self.previous.items()), "NETWORK_COUNTER_RESET", row)
            # A new interface's entire first counter counts, never a free zero baseline.
            # This can overcount host traffic; it cannot excuse acquisition as unrelated.
            row["newInterfaceCount"] = len(counters.keys() - self.previous.keys())
            row["inboundIncreaseBytes"] += sum(value - self.previous.get(key, 0) for key, value in counters.items())
        require(row["inboundIncreaseBytes"] < INBOUND_LIMIT, "NETWORK_LIMIT", row)
        self.previous, self.increase = dict(counters), row["inboundIncreaseBytes"]
        return row


def check_stale(last, started, now):
    for name, limit in STALE.items():
        age = now - last.get(name, started)
        require(0 <= age <= limit, "LANE_STALE",
                {"staleLane": name, "ageSeconds": age, "limitSeconds": limit})


def observe(roots, stop_file, streams, cancelled=None, samplers=None, clock=time.monotonic):
    """Independent bounded lanes; root controller also enforces sample staleness.

    Deadlines around statvfs/stream writes are cooperative, not kernel-call
    preemption. An unretired lane never produces a successful terminal record;
    the established parent scope remains responsible for forced retirement.
    """
    cancelled = cancelled if cancelled is not None else []
    samplers = samplers if samplers is not None else {
        "fast": lambda: fast_frame(roots, streams), "network": lambda: network_frame(streams)}
    done, lock = threading.Event(), threading.Lock()
    last, errors, ready = {}, [], [False]
    started = clock()

    def fail(lane, error):
        row = {"kind": "resource-error", "lane": lane, "code": getattr(error, "code", "OBSERVATION_ERROR"),
               "observedLocalMonotonic": clock()}
        if getattr(error, "sample", None) is not None:
            row["sample"] = error.sample
        with lock:
            errors.append(row)
        done.set()
        streams.sample(row)

    def lane(name, policy):
        try:
            while not done.is_set():
                frame = samplers[name]()
                row = policy.accept(frame)
                streams.sample({"kind": "resource-sample", "lane": name, **row})
                with lock:
                    last[name] = frame["observedLocalMonotonic"]
                    if len(last) == 2 and not ready[0]:
                        ready[0] = True
                        streams.sample({"kind": "resource-ready", "observedLocalMonotonic": clock()})
                done.wait(max(0.0, frame["startedLocalMonotonic"] + INTERVALS[name] - clock()))
        except BaseException as error:
            fail(name, error)

    threads = [threading.Thread(target=lane, args=("fast", FastPolicy()), name="hosted-resource-fast"),
               threading.Thread(target=lane, args=("network", NetworkPolicy()), name="hosted-resource-network")]
    stopped = False
    try:
        for thread in threads:
            thread.start()
        while not done.is_set():
            require(not cancelled, "OBSERVER_SIGNAL")
            for path, identity in roots.items():
                require(physical_directory(path) == identity, "RESOURCE_ROOT_CHANGED")
            if stop_requested(stop_file):
                require(ready[0], "STOP_BEFORE_ADMISSION")
                stopped = True
                break
            with lock:
                check_stale(last, started, clock())
            done.wait(0.1)
    except BaseException as error:
        fail("controller", error)
    finally:
        done.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(QUERY_SECONDS + 1.0)
                if thread.is_alive():
                    fail(thread.name, ResourceError("LANE_RETIREMENT_UNKNOWN"))
        if cancelled:
            fail("controller", ResourceError("OBSERVER_SIGNAL"))
    if errors or not stopped:
        return 125
    streams.sample({"kind": "resource-stopped", "observedLocalMonotonic": clock()})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("observe",))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    args = parser.parse_args(argv)
    streams, cancelled = Streams(), []
    try:
        require(audit_processes.host_role() == "macos-arm64" and os.geteuid() != 0, "HOST_ROLE")
        roots = validate_paths(args.root, args.state, args.stop_file, os.environ)
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        return observe(roots, args.stop_file, streams, cancelled)
    except Exception as error:
        streams.sample({"kind": "resource-error", "lane": "admission", "code": getattr(error, "code", "ADMISSION_ERROR"),
                        "observedLocalMonotonic": time.monotonic()})
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
