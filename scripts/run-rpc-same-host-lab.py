#!/usr/bin/env python3
"""Explicit Linux-only SAME-HOST virtual-Ethernet RPC experiment, never physical LAN qualification.

Run as PID 1 in NEW mount/PID/network namespaces, with a prepared source-bound lab
distribution. Setup creates only two anonymous network namespaces and a veth pair.
Every controller/worker drops ALL capabilities before native admission or JVM work.
No interface/policy override, loopback exception, tunnel, mock, firewall rule or
host-network attachment is used. The production JVM factory checks its real OS
snapshots and the remote endpoint; Java's isVirtual flag denotes subinterfaces,
not proof of physical hardware. The virtual link type is recorded, not concealed.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = ROOT
INTERFACE = "rpc-local"
SUBNET = "192.168.252.0/30"
ADDRESSES = {"host": "192.168.252.1", "client": "192.168.252.2"}
DROP = ["/usr/bin/setpriv", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs"]
SCOPE = "SAME_HOST_VIRTUAL_ETHERNET_NOT_PHYSICAL_LAN_OR_DEVICE_QUALIFICATION"
COOLDOWN_MILLIS = 65_000  # Observe beyond the unchanged 60-second record-retention window.


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def mode_label(args):
    need(type(args.attempt) is int and 1 <= args.attempt <= 99, "Bounded positive attempt number required")
    return args.mode if args.attempt == 1 else args.mode + "-" + str(args.attempt)


def retention_admission(before, after):
    fields = ("sequence", "uptimeMillis", "cpuNanos", "residentBytes", "nativeThreads", "jvmThreads",
              "connected", "accepted", "completed", "refused", "duplicates", "droppedNotifications",
              "protocolFailures", "connectionFailures", "running", "queued", "records", "payloadBytes")
    for row in (before, after):
        need(set(row) == set(fields) and all(type(row[key]) is int and 0 <= row[key] < 2**63 for key in fields),
             "Exact nonnegative host telemetry required for retention review")
        need(all(row[key] > 0 for key in ("residentBytes", "nativeThreads", "jvmThreads")),
             "Missing actual host resource measurements")
    need(after["sequence"] > before["sequence"] and after["uptimeMillis"] - before["uptimeMillis"] >= COOLDOWN_MILLIS and
         after["cpuNanos"] >= before["cpuNanos"], "Full post-retention host observation required")
    need(all(before[key] == 0 for key in ("connected", "running", "queued")), "Clients have not retired before cooldown")
    need(all(after[key] == before[key] for key in ("accepted", "completed", "refused", "duplicates",
                                                  "droppedNotifications", "protocolFailures", "connectionFailures")),
         "Unexpected RPC activity/errors after client retirement")
    need(all(after[key] == 0 for key in ("connected", "running", "queued", "records", "payloadBytes")),
         "RPC resources did not return after the original retention window")
    return {"status": "PASS", "scope": "IDLE_HOST_RETENTION_NOT_PROCESS_RSS_RESET", "before": before, "after": after,
            "observedHostMillis": after["uptimeMillis"] - before["uptimeMillis"]}


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def command(argv):
    return subprocess.check_output(argv, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)


def json_command(*argv):
    return json.loads(command(list(argv)))


def capability_admission(text):
    values = dict(line.split(":", 1) for line in text.splitlines() if ":" in line)
    need(all(int(values[name].strip(), 16) == 0 for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"))
         and values["NoNewPrivs"].strip() == "1", "Setup privilege remains: no observer or product may run")


def inactive_kernel_fallback(link):
    # Some Linux kernels instantiate sit0 in every new namespace. It is not a
    # selected/usable path: require the exact inactive, unaddressed fallback.
    return (link.get("ifname") == "sit0" and link.get("link_type") == "sit" and
            link.get("linkinfo", {}).get("info_kind") == "sit" and link.get("operstate") == "DOWN" and
            set(link.get("flags", [])) == {"NOARP"} and link.get("address") == "0.0.0.0")


def topology_admission(links, routes, addresses, role):
    extra = [item for item in links if item["ifname"] not in ("lo", INTERFACE)]
    need(role in ADDRESSES and len(extra) <= 1 and all(inactive_kernel_fallback(item) for item in extra) and
         len(links) == 2 + len(extra) and {item["ifname"] for item in links} == {"lo", INTERFACE, *[item["ifname"] for item in extra]},
         "Unexpected interface in the isolated virtual network")
    link = next(item for item in links if item["ifname"] == INTERFACE)
    need(link.get("linkinfo", {}).get("info_kind") == "veth" and
         {"UP", "LOWER_UP", "MULTICAST"} <= set(link["flags"]), "Actual connected virtual Ethernet required")
    need(len(routes) == 1 and routes[0].get("dst") == SUBNET and routes[0].get("dev") == INTERFACE and
         "gateway" not in routes[0], "Only the directly connected synthetic subnet is permitted; no egress")
    observed = [(entry["local"], entry["prefixlen"]) for item in addresses if item["ifname"] == INTERFACE
                for entry in item["addr_info"] if entry["family"] == "inet"]
    need(observed == [(ADDRESSES[role], 30)], "Unexpected synthetic IPv4 configuration")
    need(len(addresses) == len(links) and {item["ifname"] for item in addresses} == {item["ifname"] for item in links},
         "Unexpected address-bearing interface")
    for item in addresses:
        for entry in item["addr_info"]:
            address = ipaddress.ip_address(entry["local"])
            need((item["ifname"] == "lo" and address.is_loopback) or
                 (item["ifname"] == INTERFACE and (str(address) == ADDRESSES[role] or
                  address.version == 6 and address.is_link_local)), "Unexpected routable address")


def isolated_controller_admission(pid, links, routes):
    need(sys.platform == "linux" and pid == 1, "Start inside new private PID/mount/network namespaces")
    need(len(links) in (1, 2) and sum(item["ifname"] == "lo" for item in links) == 1 and
         all(item["ifname"] == "lo" or inactive_kernel_fallback(item) for item in links) and not routes,
         "Setup must never run in the host's network namespace")


def private_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def setup(args):
    isolated_controller_admission(os.getpid(), json_command("ip", "-d", "-j", "link"), json_command("ip", "-j", "route"))
    state = args.state.resolve(strict=True)
    need(state == args.state and not state.is_symlink() and state.stat().st_uid == os.getuid() and
         stat.S_IMODE(state.stat().st_mode) == 0o700 and (state / "context.json").is_file(),
         "Explicit canonical privately owned native state required")
    control = state / "work" / ("same-host-" + mode_label(args))
    control.mkdir(mode=0o700)
    temporary = control / "tmp"
    temporary.mkdir(mode=0o700)
    # This mount exists only in the already-private mount namespace. Nothing is
    # mounted over existing evidence; failed fixture data is archived before exit.
    command(["mount", "-t", "tmpfs", "-o", "size=2g,mode=700,nodev,nosuid", "rpc-local-fixtures", str(temporary)])
    original = os.open("/proc/self/ns/net", os.O_RDONLY)
    workers = {}
    descriptors = set()
    try:
        command(["ip", "link", "set", "lo", "up"])
        for role in ADDRESSES:
            gate_read, gate_write = os.pipe()
            ready_read, ready_write = os.pipe()
            descriptors.update((gate_read, gate_write, ready_read, ready_write))
            invocation = uuid.uuid4().hex
            with (control / (role + "-worker.log")).open("xb") as log:
                child = subprocess.Popen([
                    "/usr/bin/unshare", "--net", "--", *DROP, sys.executable, "-I", "-S", str(Path(__file__).resolve()),
                    "--owner-authorized-same-host", "--worker", role, "--source", str(ROOT),
                    "--state", str(state), "--mode", args.mode,
                    "--attempt", str(args.attempt),
                    "--gate", str(gate_read), "--ready", str(ready_write), "--invocation", invocation,
                ], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, pass_fds=(gate_read, ready_write))
            os.close(gate_read)
            os.close(ready_write)
            descriptors.difference_update((gate_read, ready_write))
            descriptor = os.pidfd_open(child.pid)
            descriptors.add(descriptor)
            workers[role] = {"pid": child.pid, "pidfd": descriptor, "gate": gate_write, "id": invocation}
            need(select.select([ready_read], [], [], 15)[0] and os.read(ready_read, 1) == b"N",
                 "Unprivileged network worker did not become ready")
            os.close(ready_read)
            descriptors.remove(ready_read)
        namespaces = {role: os.open(f"/proc/{worker['pid']}/ns/net", os.O_RDONLY) for role, worker in workers.items()}
        try:
            need(len({os.fstat(fd).st_ino for fd in (original, *namespaces.values())}) == 3,
                 "Controller/host/client must have three distinct anonymous network namespaces")
            os.setns(namespaces["host"], os.CLONE_NEWNET)
            command(["ip", "link", "add", INTERFACE, "type", "veth", "peer", "name", INTERFACE,
                     "netns", f"/proc/{workers['client']['pid']}/ns/net"])
            topology = {}
            for role, namespace in namespaces.items():
                os.setns(namespace, os.CLONE_NEWNET)
                command(["ip", "address", "add", ADDRESSES[role] + "/30", "dev", INTERFACE])
                command(["ip", "link", "set", "lo", "up"])
                command(["ip", "link", "set", INTERFACE, "up"])
            for role, namespace in namespaces.items():
                os.setns(namespace, os.CLONE_NEWNET)
                observed = {"links": json_command("ip", "-d", "-j", "link"),
                            "routes": json_command("ip", "-j", "route"),
                            "addresses": json_command("ip", "-j", "address")}
                topology_admission(**observed, role=role)
                topology[role] = {**observed, "allIpv4Routes": json_command("ip", "-j", "-4", "route", "show", "table", "all"),
                                 "allIpv6Routes": json_command("ip", "-j", "-6", "route", "show", "table", "all"),
                                 "rules": json_command("ip", "-j", "rule")}
        finally:
            os.setns(original, os.CLONE_NEWNET)
            for descriptor in namespaces.values():
                os.close(descriptor)
        private_json(control / "network-setup.json", {"scope": SCOPE, "workers": workers, "topology": topology})
        for worker in workers.values():
            for field in ("pidfd", "gate"):
                os.set_inheritable(worker[field], True)
        os.close(original)
        original = None
        os.execv(DROP[0], [*DROP, sys.executable, "-I", "-S", str(Path(__file__).resolve()),
                           "--owner-authorized-same-host", "--coordinate", "--source", str(ROOT),
                           "--state", str(state), "--mode", args.mode, "--attempt", str(args.attempt)])
    except BaseException as error:
        # EOF refuses workload execution. Namespace PID 1 exit is a final safety
        # boundary, never evidence that native cleanup or a workload passed.
        for descriptor in descriptors:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if original is not None:
            os.close(original)
        private_json(control / "setup-failed.json", {"scope": SCOPE, "status": "FAIL", "error": type(error).__name__,
                                                    "workloadStarted": False})
        raise


def source_binding_admission(context, product_source, harness_source):
    need(context["root"] == str(ROOT) and context["source"] == product_source and product_source["status"] == "",
         "Same-host runtime requires the unchanged admitted source")
    need(harness_source["status"] == "", "Harness must also be a clean source-bound checkout")


def configure(args):
    capability_admission(Path("/proc/self/status").read_text())
    sys.path.insert(0, str(ROOT / "scripts"))
    runner = module("local_lab_leaf", "run-audit-command.py")
    checker = module("local_lab_checker", "check-audit-receipt.py")
    lab = module("local_lab_transport", "run-rpc-capacity-lab.py")
    state, context = runner.context_at(str(args.state))
    source_binding_admission(context, runner.source_snapshot(ROOT), runner.source_snapshot(HARNESS_ROOT))
    control = state / "work" / ("same-host-" + mode_label(args))
    os.environ.update(P2PKIT_AUDIT_STATE_DIR=str(state), GRADLE_USER_HOME=context["gradleHome"],
                      TMPDIR=str(control / "tmp"), RPC_CAPACITY_LAB_AUTHORIZED=lab.AUTHORIZATION,
                      P2PKIT_GRADLE_EXECUTOR=str(ROOT / "scripts/run-audit-command.py"),
                      PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    for key in list(os.environ):
        if key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN") or \
                key.upper().startswith(("SIGNING_", "ORG_GRADLE_PROJECT_SIGNING", "MAVEN_CENTRAL_", "SONATYPE_")):
            os.environ.pop(key)
    lab.classpath(context["source"]["commit"])  # Verify every prepared JAR, not a caller-supplied classpath.
    return runner, checker, lab, state, context, control


def invoke(runner, checker, context, control, purpose, argv, timeout, invocation=None):
    alias = control / (purpose + ".json")
    options = ["--id", invocation] if invocation else []
    with (control / (purpose + ".driver.log")).open("x") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        code = runner.main([*options, "--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew"), "--kind", "command",
                            "--purpose", purpose, "--timeout", str(timeout), "--receipt", str(alias), "--", *argv])
    proof = runner.read_json(alias)
    checker.validate(proof, code, purpose, ROOT, ROOT / "gradlew", argv)
    need(proof["sourceBefore"] == proof["sourceAfter"] == context["source"] and
         proof["ownership"]["discoveryErrors"] == [] and proof["ownedSurvivors"] == [] and
         proof["errors"] == [] and proof["stopExitCode"] == 0, "Native finalization is unproven")
    return code, proof


def worker(args):
    capability_admission(Path("/proc/self/status").read_text())
    os.write(args.ready, b"N")
    os.close(args.ready)
    # The controller runs the FULL native admission first. EOF never starts Java.
    need(select.select([args.gate], [], [], 1900)[0] and os.read(args.gate, 1) == b"G", "Worker was not released")
    os.close(args.gate)
    runner, checker, _lab, state, context, control = configure(args)
    topology_admission(json_command("ip", "-d", "-j", "link"), json_command("ip", "-j", "route"),
                       json_command("ip", "-j", "address"), args.worker)
    directory = state / "work" / f"local-{mode_label(args)}-{args.worker}"
    argv = [sys.executable, str(ROOT / "scripts/run-rpc-capacity-lab.py"), "run", "--directory", str(directory),
            "--role", args.worker, "--mode", args.mode]
    code, proof = invoke(runner, checker, context, control, "local-" + args.worker, argv, 2500, args.invocation)
    private_json(control / (args.worker + "-final.json"), {
        "scope": SCOPE, "source": context["source"], "exitCode": code, "nativeFinalizationVerified": True,
        "receiptSha256": runner.file_digest(control / ("local-" + args.worker + ".json")),
    })
    return code


def coordinate(args):
    isolated_controller_admission(os.getpid(), json_command("ip", "-d", "-j", "link"), json_command("ip", "-j", "route"))
    runner, checker, lab, state, context, control = configure(args)
    setup_record = runner.read_json(control / "network-setup.json")
    need(setup_record["scope"] == SCOPE and set(setup_record["workers"]) == set(ADDRESSES), "Wrong network setup")
    workers = setup_record["workers"]
    for worker in workers.values():
        info = Path(f"/proc/self/fdinfo/{worker['pidfd']}").read_text()
        need(f"Pid:\t{worker['pid']}\n" in info, "Inherited pidfd does not identify its directly created worker")
    result = {"schema": 1, "scope": SCOPE, "source": context["source"], "mode": args.mode, "status": "FAIL",
              "physicalLanQualified": False, "deviceCapacityQualified": False, "workersReaped": False,
              "cleanupErrors": [], "attempt": args.attempt, "harnessSource": runner.source_snapshot(HARNESS_ROOT),
              "harnessSha256": runner.file_digest(Path(__file__))}
    released, codes = set(), {}
    directories = {role: state / "work" / f"local-{mode_label(args)}-{role}" for role in workers}

    def reap(role):
        if role not in codes:
            pid, status = os.waitpid(workers[role]["pid"], os.WNOHANG)
            if pid:
                codes[role] = os.waitstatus_to_exitcode(status)
        return role in codes

    def release(role):
        need(not select.select([workers[role]["pidfd"]], [], [], 0)[0], "Worker exited before release")
        os.write(workers[role]["gate"], b"G")
        os.close(workers[role]["gate"])
        released.add(role)

    def copy_control(name, source, target, replace=False):
        path = directories[source] / name
        if path.exists():
            lab.write_private(directories[target] / name, lab.read_private(path), replace=replace)
            return True
        return False

    def fresh_host_sample(previous):
        deadline = time.monotonic() + 5
        while True:
            need(not reap("host"), "Host exited before post-retention review")
            values = lab.parse(lab.read_private(directories["host"] / "host-telemetry.txt"))
            need(values.pop("schema") == "1" and values.pop("runLabel") == "same-host-" + mode_label(args),
                 "Host retention telemetry belongs to another run")
            need(all(value.isascii() and value.isdecimal() for value in values.values()), "Non-numeric host telemetry")
            sample = {key: int(value) for key, value in values.items()}
            need(sample["sequence"] >= previous, "Host telemetry sequence regressed")
            if sample["sequence"] > previous:
                return sample
            need(time.monotonic() < deadline, "Host stopped producing bounded fresh telemetry")
            time.sleep(.1)

    def review_retention():
        # A sample taken before the client exited cannot establish quiescence.
        before = fresh_host_sample(fresh_host_sample(-1)["sequence"])
        after = before
        deadline = time.monotonic() + 75
        while after["uptimeMillis"] - before["uptimeMillis"] < COOLDOWN_MILLIS:
            need(time.monotonic() < deadline, "Post-retention observation did not complete")
            after = fresh_host_sample(after["sequence"])
        return retention_admission(before, after)

    try:
        evidence = state / "evidence" / ("local-" + mode_label(args) + "-native-controls")
        argv = [sys.executable, str(ROOT / "scripts/tests/run-audit-command-test.py"), "--expected-host", "linux-x64",
                "--evidence-dir", str(evidence)]
        code, proof = invoke(runner, checker, context, control, "local-native-controls", argv, 1800)
        policy = module("local_native_inventory", "run-rpc-qualification.py")
        raw = (state / "evidence" / proof["id"] / "product.stderr.log").read_text()
        need(code == 0 and policy.unittest_count(raw) == policy.control_inventory("linux-x64"),
             "Complete fresh native admission failed; no workloads may start")
        result["nativeControlTests"] = policy.unittest_count(raw)
        result["nativeReceiptSha256"] = runner.file_digest(control / "local-native-controls.json")
        for role, directory in directories.items():
            directory.mkdir(mode=0o700)
            values = {"schema": "1", "role": role, "runLabel": "same-host-" + mode_label(args),
                      "sourceSha": context["source"]["commit"], "endpointAddress": ADDRESSES["host"], "port": "28473",
                      "subnets": SUBNET, "interface": INTERFACE, "localAddress": ADDRESSES[role]}
            lab.configuration(values, context["source"]["commit"])
            lab.write_private(directory / "config.txt", lab.encode(values))
        release("client")
        started = time.monotonic()
        while not copy_control("client-pins.txt", "client", "host"):
            need(not reap("client") and time.monotonic() - started < 120, "Client provisioning failed or timed out")
            time.sleep(.1)
        release("host")
        while not copy_control("host-ready.txt", "host", "client"):
            need(not reap("host") and not reap("client") and time.monotonic() - started < 150,
                 "Host readiness failed or timed out")
            time.sleep(.1)
        while not reap("client"):
            need(not reap("host") and time.monotonic() - started < 2600, "Workload lost its host or outer deadline")
            copy_control("host-telemetry.txt", "host", "client", replace=True)
            time.sleep(.25)
        try:
            result["postRetention"] = review_retention()
        except Exception as error:
            result["postRetention"] = {"status": "FAIL", "error": type(error).__name__}
        # Request ordinary host close and await native finalization even when a
        # resource assertion fails. The failure is propagated below, never waived.
        lab.write_private(directories["host"] / "stop.txt", b"stop=true\n")
        end = time.monotonic() + 150
        while not reap("host"):
            need(time.monotonic() < end, "Host native finalization did not finish")
            time.sleep(.1)
        result["elapsedIncludingProvisioningSeconds"] = round(time.monotonic() - started, 3)
        for role in workers:
            final = runner.read_json(control / (role + "-final.json"))
            need(codes[role] == 0 and final["nativeFinalizationVerified"] is True and
                 final["source"] == context["source"] and final["exitCode"] == 0, "A workload/cleanup failed")
        need(result["postRetention"]["status"] == "PASS", "Post-retention RPC resource review failed")
        result["status"] = "COMPLETED_PENDING_RESOURCE_REVIEW_SAME_HOST_ONLY"
    finally:
        for role, worker in workers.items():
            try:
                if role not in released:
                    os.close(worker["gate"])
                elif not reap(role):
                    # Signal only the retained kernel handle of our own bootstrap.
                    # The normal native executor handles cancellation and drains descendants.
                    with contextlib.suppress(ProcessLookupError):
                        signal.pidfd_send_signal(worker["pidfd"], signal.SIGTERM)
            except Exception as error:
                result["cleanupErrors"].append(role + ":" + type(error).__name__)
        end = time.monotonic() + 150
        while not all(reap(role) for role in workers) and time.monotonic() < end:
            time.sleep(.1)
        result["workerExitCodes"] = codes
        result["workersReaped"] = len(codes) == 2
        try:
            result["sourceUnchanged"] = runner.source_snapshot(ROOT) == context["source"]
            result["harnessUnchanged"] = (runner.source_snapshot(HARNESS_ROOT) == result["harnessSource"] and
                                          runner.file_digest(Path(__file__)) == result["harnessSha256"])
        except Exception as error:
            result["sourceUnchanged"] = False
            result["harnessUnchanged"] = False
            result["cleanupErrors"].append("source:" + type(error).__name__)
        for worker in workers.values():
            os.close(worker["pidfd"])
        if result["status"] == "FAIL":
            try:
                with (control / "failed-native-fixtures.tar.gz").open("xb") as archive:
                    archived = subprocess.run(["tar", "-czf", "-", "--one-file-system", "-C", str(control / "tmp"), "."],
                                              stdout=archive, stderr=subprocess.PIPE, timeout=120, check=False)
                    result["failedFixtureArchiveExitCode"] = archived.returncode
                    need(archived.returncode == 0, "Failure evidence archive was not preserved")
            except Exception as error:
                result["cleanupErrors"].append("archive:" + type(error).__name__)
        private_json(control / "result.json", result)
        print(json.dumps(result), flush=True)
    return 0 if (result["status"].startswith("COMPLETED_") and result["workersReaped"] and result["sourceUnchanged"] and
                 result["harnessUnchanged"] and not result["cleanupErrors"]) else 1


def main():
    global ROOT
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-authorized-same-host", action="store_true")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT,
                        help="Immutable prepared product checkout, separately bound from an immutable harness checkout")
    parser.add_argument("--mode", choices=("steady", "large", "correctness"), required=True)
    parser.add_argument("--attempt", type=int, default=1, help="Create-only attempt number; never replace prior evidence")
    parser.add_argument("--worker", choices=tuple(ADDRESSES), help=argparse.SUPPRESS)
    parser.add_argument("--coordinate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gate", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--ready", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--invocation", help=argparse.SUPPRESS)
    args = parser.parse_args()
    need(args.owner_authorized_same_host, "Explicit owner authorization acknowledgement required at every stage")
    need(not (args.worker and args.coordinate), "Conflicting internal stages")
    mode_label(args)
    need(args.source.is_absolute() and args.source.resolve(strict=True) == args.source, "Canonical source checkout required")
    ROOT = args.source
    if args.worker:
        return worker(args)
    if args.coordinate:
        return coordinate(args)
    setup(args)
    return 125


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Same-host virtual-network experiment failed: " + str(error), file=sys.stderr)
        raise SystemExit(125)
