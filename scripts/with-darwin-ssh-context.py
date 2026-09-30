#!/usr/bin/env python3
"""Disposable authenticated loopback SSH *control* context for Apple CI diagnostics.

Apple TN3179 documents SSH-launched command-line tools as an automatically
permitted local-network context. Test that supported context, not a TCC edit or
root product execution. This is NOT an RPC tunnel or evidence of physical LAN.
One inetd-mode system sshd accepts one loopback socket using two fresh test keys.
It cannot forward, allocate a terminal, execute user RCs or accept other users.
The fixed nonroot child still runs the unchanged audit-session/native executor.
Only sshd authentication uses privilege; no privileged product/observer runs.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shlex
import socket
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REF = "refs/heads/work/rpc-lan-20260927-054728-8b1b11da"
SCOPE = "DISPOSABLE_LOOPBACK_SSH_CONTROL_NOT_RPC_LAN"
LIMIT = 128 * 1024
ENVIRONMENT = frozenset((
    "PATH", "LANG", "LC_ALL", "TMPDIR", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "ANDROID_HOME", "ANDROID_SDK_ROOT",
    "DEVELOPER_DIR", "GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_EVENT_NAME",
    "GITHUB_SHA", "GITHUB_WORKSPACE", "RUNNER_TEMP", "RPC_QUALIFICATION_PARENT", "RPC_QUALIFY_REQUESTED",
    "RPC_ADMISSION_ONLY", "RPC_APPLE_SSH_CONTEXT",
))
PROOF_FLAGS = frozenset(("authenticatedInvokingUser", "unrecoverableRootInChild", "exactCommandFinished",
                         "listenerClosed", "clientReaped", "serverReaped", "credentialsRemoved", "sourceUnchanged"))
STAGES = ("SETUP", "KEYS", "CONFIG", "ACCEPT", "CHILD", "REAP", "RECORDS", "FINALIZED")
FINALIZATION_ERRORS = frozenset(("SOCKET_CLOSE", "CLIENT_REAP", "SERVER_REAP", "CREDENTIAL_REMOVE",
                                 "SOURCE_RECHECK", "LOG_BOUND"))
ERROR_PATTERNS = {
    "CONFIG_OPTION": r"[Bb]ad configuration|[Uu]nsupported option|[Bb]adly formatted|[Mm]issing argument|[Bb]ad.*[Oo]ption",
    "AUTHENTICATION": r"[Aa]uthentication|[Pp]ermission denied|[Pp]ublickey",
    "PAM_ACCOUNT": r"PAM|[Aa]ccount.*[Ll]ocked|[Aa]ccount.*[Ee]xpired|[Nn]ot allowed",
    "KEY_OR_MODE": r"[Hh]ost key|[Pp]rivate key|[Aa]uthorized.keys|[Bb]ad ownership|[Bb]ad modes",
    "SUDO": r"sudo:|[Aa] password is required", "PRIVSEP": r"privsep|privilege separation|sandbox",
    "NETWORK": r"[Cc]onnection.*(?:closed|refused|reset)|[Tt]imed out|[Bb]roken pipe",
    "CHILD": r"Disposable Apple SSH control failed|Private Apple audit-session setup failed",
}
SSH_POLICY = {
    "AddressFamily": "inet", "ListenAddress": "127.0.0.1", "PidFile": "none",
    "AuthorizedKeysCommand": "none", "AuthenticationMethods": "publickey", "PubkeyAuthentication": "yes",
    "PubkeyAcceptedAlgorithms": "ssh-ed25519", "HostKeyAlgorithms": "ssh-ed25519",
    "PermitRootLogin": "no", "PasswordAuthentication": "no", "KbdInteractiveAuthentication": "no",
    "PermitEmptyPasswords": "no", "HostbasedAuthentication": "no", "GSSAPIAuthentication": "no",
    "UsePAM": "yes", "StrictModes": "yes", "PermitUserRC": "no", "PermitUserEnvironment": "no",
    "PermitTTY": "no", "DisableForwarding": "yes", "AllowAgentForwarding": "no", "AllowTcpForwarding": "no",
    "AllowStreamLocalForwarding": "no", "X11Forwarding": "no", "PermitTunnel": "no", "GatewayPorts": "no",
    "MaxSessions": "1", "MaxAuthTries": "1", "LoginGraceTime": "30", "ClientAliveInterval": "15",
    "ClientAliveCountMax": "3", "PrintMotd": "no", "PrintLastLog": "no", "LogLevel": "ERROR",
}


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def physical(path):
    need(path.is_absolute() and path == Path(os.path.normpath(path)) and
         not any(ord(c) < 32 for c in str(path)), "Canonical physical path required")
    for item in (path, *path.parents):
        need(not item.is_symlink(), "Symlinked path refused")


def private_parent(path):
    physical(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
         "Private invoking-user directory required")


def write_new(path, data):
    private_parent(path.parent)
    need(type(data) is bytes and len(data) <= LIMIT, "Bounded bytes required")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(data)


def write_json(path, value):
    write_new(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def read_private(path):
    private_parent(path.parent)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
         "Private invoking-user file required")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        actual = os.fstat(stream.fileno())
        need((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino), "File identity changed")
        value = stream.read(LIMIT + 1)
    need(len(value) <= LIMIT, "File exceeds bound")
    return value


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "Duplicate configuration key")
            result[key] = value
        return result
    return json.loads(read_private(path), object_pairs_hook=unique)


def source_snapshot():
    def git(*args):
        return subprocess.check_output(["/usr/bin/git", *args], cwd=ROOT, stderr=subprocess.PIPE, timeout=15).decode().strip()
    need(git("status", "--porcelain=v1") == "", "Immutable clean source required")
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}


def admit_environment(env):
    need(platform.system() == "Darwin" and os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0,
         "Nonroot native Apple account required")
    need(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
         env.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and env.get("GITHUB_REF") == REF and
         env.get("GITHUB_EVENT_NAME") == "push" and env.get("RPC_QUALIFY_REQUESTED") == "true" and
         env.get("RPC_APPLE_SSH_CONTEXT") == "true" and re.fullmatch("[0-9a-f]{40}", env.get("GITHUB_SHA", "")),
         "Explicit feature-only disposable hosted context required")
    need(Path(env["GITHUB_WORKSPACE"]).resolve(strict=True) == ROOT, "Wrong source checkout")


def config_validate(config):
    need(type(config) is dict and set(config) == {"uid", "gid", "groups", "source", "argv", "environment", "ports"},
         "Unexpected child configuration")
    need(type(config["uid"]) is int and config["uid"] == os.getuid() != 0 and
         type(config["gid"]) is int and config["gid"] == os.getgid() != 0 and
         type(config["groups"]) is list and all(type(g) is int and g >= 0 for g in config["groups"]) and
         config["groups"] == sorted(set(os.getgroups())), "Invoking credentials changed")
    env = config["environment"]
    need(type(env) is dict and set(env) <= ENVIRONMENT and "PATH" in env and
         all(type(value) is str and "\0" not in value for value in env.values()), "Unadmitted environment")
    admit_environment(env)
    argv = config["argv"]
    # The SSH child cannot substitute an arbitrary product launcher or bypass admission.
    prefix = [str(Path(sys.executable).resolve()), str(ROOT / "scripts/with-darwin-audit-session.py"), "--parent",
              env["RPC_QUALIFICATION_PARENT"], "--", str(Path(sys.executable).resolve()),
              str(ROOT / "scripts/run-rpc-qualification.py"), "run", "--lane"]
    need(type(argv) is list and argv[:len(prefix)] == prefix and len(argv) in (10, 11, 12) and
         argv[9] in ("apple-x64", "apple-arm64") and
         (argv[10:] in ([], ["--admission-only"]) or
          argv[9] == "apple-x64" and argv[10:] in (["--intel-investigation", "network"],
                                                  ["--intel-investigation", "native"],
                                                  ["--intel-investigation", "cold-boot"])),
         "Only the original audit-session qualification command is admitted")
    need(type(config["ports"]) is list and len(config["ports"]) == 2 and
         all(type(p) is int and 1024 <= p <= 65535 for p in config["ports"]), "Unprivileged loopback ports required")
    source = config["source"]
    need(type(source) is dict and set(source) == {"commit", "tree"} and
         all(type(v) is str and re.fullmatch("[0-9a-f]{40}", v) for v in source.values()) and
         source["commit"] == env["GITHUB_SHA"], "Exact source binding required")


def quoted_path(path):
    physical(path)
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'


def server_config(directory, account, forced):
    need(re.fullmatch("[a-z_][a-z0-9_-]{0,31}", account), "Unambiguous invoking account required")
    return ("\n".join(key + " " + value for key, value in SSH_POLICY.items()) + "\n" +
            "AllowUsers " + account + "\nHostKey " + quoted_path(directory / "host-key") +
            "\nAuthorizedKeysFile " + quoted_path(directory / "authorized_keys") +
            "\nForceCommand " + shlex.join(forced) + "\n").encode()


def public_key(path):
    # ssh-keygen's .pub is initially 0644; its enclosing 0700 directory is private.
    path.chmod(0o600)
    parts = read_private(path).decode("ascii").split()
    need(len(parts) == 3 and parts[0] == "ssh-ed25519" and parts[2] == "p2pkit-ephemeral-control" and
         len(base64.b64decode(parts[1], validate=True)) == 51, "Unexpected fresh synthetic public key")
    return " ".join(parts[:2])


def client_command(directory, port, account):
    options = {"BatchMode": "yes", "IdentitiesOnly": "yes", "IdentityAgent": "none",
               "StrictHostKeyChecking": "yes", "UserKnownHostsFile": str(directory / "known_hosts"),
               "GlobalKnownHostsFile": "/dev/null", "UpdateHostKeys": "no", "VerifyHostKeyDNS": "no",
               "PreferredAuthentications": "publickey", "PasswordAuthentication": "no", "KbdInteractiveAuthentication": "no",
               "HostKeyAlgorithms": "ssh-ed25519", "ForwardAgent": "no", "ClearAllForwardings": "yes",
               "ControlMaster": "no", "ControlPath": "none", "ProxyCommand": "none", "ProxyJump": "none",
               "CanonicalizeHostname": "no", "ConnectTimeout": "20", "ConnectionAttempts": "1",
               "ServerAliveInterval": "15", "ServerAliveCountMax": "3", "LogLevel": "ERROR"}
    return ["/usr/bin/ssh", "-4", "-T", "-F", "/dev/null", "-i", str(directory / "client-key"),
            "-p", str(port), *[item for k, v in options.items() for item in ("-o", k + "=" + v)],
            account + "@127.0.0.1", "p2pkit-fixed-command"]


def child(path):
    config = read_json(path)
    config_validate(config)
    connection = os.environ.get("SSH_CONNECTION", "").split()
    client_port, server_port = config["ports"]
    need(connection == ["127.0.0.1", str(client_port), "127.0.0.1", str(server_port)] and
         os.environ.get("SSH_ORIGINAL_COMMAND") == "p2pkit-fixed-command" and "SSH_TTY" not in os.environ,
         "Authenticated fixed loopback session required")
    need(source_snapshot() == config["source"], "Source changed before SSH child")
    try:
        os.setuid(0)
    except PermissionError:
        pass
    else:
        raise RuntimeError("SSH child retained recoverable root authority")
    write_json(path.parent / "child-admission.json", {"source": config["source"],
               "authenticatedInvokingUser": True, "unrecoverableRootInChild": True})
    account = pwd.getpwuid(os.getuid())
    env = {**config["environment"], "HOME": account.pw_dir, "USER": account.pw_name, "LOGNAME": account.pw_name,
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    # This child is nonroot. The original, separate audit bootstrap still allocates
    # and verifies a fresh audit session BEFORE any native ownership/product work.
    code = subprocess.call(config["argv"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    need(source_snapshot() == config["source"], "Source changed during SSH child")
    write_json(path.parent / "child-result.json", {"source": config["source"], "exitCode": code})
    return code


def validate_proof(value, source, complete=True):
    need(type(value) is dict and set(value) == {"schema", "scope", "source", "exitCode", "serverExitCode", "stage", "diagnostics", "finalizationErrors", *PROOF_FLAGS},
         "Incomplete SSH control proof")
    need(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
         value["source"] == source and type(value["exitCode"]) is int and -255 <= value["exitCode"] <= 255 and
         (value["serverExitCode"] is None or type(value["serverExitCode"]) is int and -255 <= value["serverExitCode"] <= 255) and
         value["stage"] in STAGES and all(type(value[k]) is bool for k in PROOF_FLAGS), "Invalid SSH control observation")
    need(type(value["diagnostics"]) is dict and set(value["diagnostics"]) <= {"setup", "ssh-client", "ssh-server"},
         "Invalid SSH diagnostic labels")
    need(type(value["finalizationErrors"]) is list and value["finalizationErrors"] == sorted(set(value["finalizationErrors"])) and
         all(e in FINALIZATION_ERRORS for e in value["finalizationErrors"]), "Invalid SSH cleanup errors")
    for row in value["diagnostics"].values():
        need(type(row) is dict and set(row) == {"sha256", "bytes", "categories"} and
             type(row["bytes"]) is int and 0 <= row["bytes"] <= LIMIT and
             type(row["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", row["sha256"]) and
             type(row["categories"]) is list and row["categories"] == sorted(set(row["categories"])) and
             all(c in ERROR_PATTERNS for c in row["categories"]), "Invalid SSH diagnostic observation")
    if complete:
        need(all(value[k] is True for k in PROOF_FLAGS) and value["stage"] == "FINALIZED" and
             0 <= value["exitCode"] < 255 and value["serverExitCode"] == 0 and not value["finalizationErrors"],
             "SSH control finalization failed")
    return value


def run(parent, lane, admission_only, investigation):
    admit_environment(os.environ)
    private_parent(parent)
    need(parent.is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)) and
         str(parent) == os.environ["RPC_QUALIFICATION_PARENT"], "Task-local private state required")
    directory = parent / "ssh-context"
    directory.mkdir(mode=0o700)
    source = source_snapshot()
    need(source["commit"] == os.environ["GITHUB_SHA"], "Wrong source")
    python = str(Path(sys.executable).resolve())
    argv = [python, str(ROOT / "scripts/with-darwin-audit-session.py"), "--parent", str(parent), "--", python,
            str(ROOT / "scripts/run-rpc-qualification.py"), "run", "--lane", lane]
    if admission_only:
        argv.append("--admission-only")
    if investigation:
        argv += ["--intel-investigation", investigation]
    account = pwd.getpwuid(os.getuid()).pw_name
    proof = {"schema": 1, "scope": SCOPE, "source": source, "exitCode": 255, "serverExitCode": None,
             "stage": "SETUP", "diagnostics": {}, "finalizationErrors": [],
             **dict.fromkeys(PROOF_FLAGS, False)}
    credentials = [directory / name for name in ("host-key", "host-key.pub", "client-key", "client-key.pub",
                                                "authorized_keys", "known_hosts", "child-config.json", "sshd_config")]
    client_process = server_process = None
    listener = connection = None
    try:
        with (directory / "setup.log").open("xb") as setup_log:
            for key in ("host-key", "client-key"):
                subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C",
                                "p2pkit-ephemeral-control", "-f", str(directory / key)],
                               check=True, timeout=30, stdin=subprocess.DEVNULL, stdout=setup_log, stderr=setup_log)
                read_private(directory / key)
            host_key = public_key(directory / "host-key.pub")
            client_key = public_key(directory / "client-key.pub")
            proof["stage"] = "KEYS"
            write_new(directory / "authorized_keys", ('restrict,from="127.0.0.1" ' + client_key + "\n").encode())
            forced = [python, "-I", "-S", str(Path(__file__).resolve()), "--child", str(directory / "child-config.json")]
            write_new(directory / "sshd_config", server_config(directory, account, forced))
            # System OpenSSH validates its exact private config; no global sshd/keys/settings are changed.
            subprocess.run(["/usr/bin/sudo", "-n", "/usr/sbin/sshd", "-t", "-f", str(directory / "sshd_config")],
                           check=True, timeout=30, stdin=subprocess.DEVNULL, stdout=setup_log, stderr=setup_log)
        proof["stage"] = "CONFIG"
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(30)
        port = listener.getsockname()[1]
        write_new(directory / "known_hosts", ("[127.0.0.1]:" + str(port) + " " + host_key + "\n").encode())
        with (directory / "ssh-client.log").open("xb") as client_log, (directory / "ssh-server.log").open("xb") as server_log:
            client_process = subprocess.Popen(client_command(directory, port, account), stdin=subprocess.DEVNULL,
                                              stdout=sys.stdout, stderr=client_log)
            connection, peer = listener.accept()
            proof["stage"] = "ACCEPT"
            listener.close()
            proof["listenerClosed"] = True
            need(peer[0] == "127.0.0.1" and connection.getsockname() == ("127.0.0.1", port), "Nonlocal peer rejected")
            config = {"uid": os.getuid(), "gid": os.getgid(), "groups": sorted(set(os.getgroups())), "source": source,
                      "argv": argv, "environment": {k: v for k, v in os.environ.items() if k in ENVIRONMENT},
                      "ports": [peer[1], port]}
            config_validate(config)
            write_json(directory / "child-config.json", config)
            server_process = subprocess.Popen(["/usr/bin/sudo", "-n", "/usr/sbin/sshd", "-i", "-e", "-f",
                                               str(directory / "sshd_config")], stdin=connection, stdout=connection,
                                              stderr=server_log)
            proof["stage"] = "CHILD"
            # The unchanged native product bounds and job deadline remain the
            # execution authority. Do not kill product descendants by raw PIDs.
            proof["exitCode"] = client_process.wait()
            proof["clientReaped"] = True
            proof["serverExitCode"] = server_process.wait(timeout=30)
            proof["serverReaped"] = True
            proof["stage"] = "REAP"
        admitted = read_json(directory / "child-admission.json")
        finished = read_json(directory / "child-result.json")
        need(admitted == {"source": source, "authenticatedInvokingUser": True, "unrecoverableRootInChild": True} and
             finished == {"source": source, "exitCode": proof["exitCode"]}, "Missing exact authenticated child result")
        proof.update(authenticatedInvokingUser=True, unrecoverableRootInChild=True, exactCommandFinished=True)
        proof["stage"] = "RECORDS"
    finally:
        errors = set()
        if listener is not None:
            listener.close()
            proof["listenerClosed"] = True
        if connection is not None:
            # Close only this owned control socket, never signal or adopt a product PID.
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError as error:
                import errno
                if error.errno != errno.ENOTCONN:  # Already closed by the exact reaped SSH server is normal.
                    errors.add("SOCKET_CLOSE")
            connection.close()
        for process, field in ((client_process, "clientReaped"), (server_process, "serverReaped")):
            if process is not None and not proof[field]:
                try:
                    process.wait(timeout=30)
                    proof[field] = True
                except subprocess.TimeoutExpired:
                    errors.add("CLIENT_REAP" if field == "clientReaped" else "SERVER_REAP")
        for path in credentials:
            if path.exists() or path.is_symlink():
                try:
                    if path.suffix == ".pub":
                        info = path.lstat()
                        need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid(), "Unexpected generated public-key file")
                        path.chmod(0o600)  # A failed key-generation step may precede public_key().
                    read_private(path)  # Delete only privately owned, regular task files.
                    path.unlink()
                except Exception:
                    errors.add("CREDENTIAL_REMOVE")
        proof["credentialsRemoved"] = all(not p.exists() and not p.is_symlink() for p in credentials)
        try:
            proof["sourceUnchanged"] = source_snapshot() == source
        except Exception:
            errors.add("SOURCE_RECHECK")
        for label in ("setup", "ssh-client", "ssh-server"):
            log = directory / (label + ".log")
            if log.is_file():
                if log.stat().st_size > LIMIT:
                    errors.add("LOG_BOUND")
                else:
                    raw = log.read_bytes()
                    proof["diagnostics"][label] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                        "categories": sorted(k for k, p in ERROR_PATTERNS.items() if re.search(p, raw.decode(errors="replace")))}
        proof["finalizationErrors"] = sorted(errors)
        if all(proof[k] is True for k in PROOF_FLAGS) and not errors:
            proof["stage"] = "FINALIZED"
        write_json(directory / "result.json", proof)
    validate_proof(proof, source)
    return proof["exitCode"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--lane", choices=("apple-x64", "apple-arm64"))
    parser.add_argument("--admission-only", action="store_true")
    parser.add_argument("--intel-investigation", choices=("network", "native", "cold-boot"))
    args = parser.parse_args()
    if args.child:
        need(args.parent is None and args.lane is None and not args.admission_only and args.intel_investigation is None,
             "Only fixed child arguments admitted")
        return child(args.child)
    need(args.parent is not None and args.lane is not None, "Explicit task context required")
    return run(args.parent, args.lane, args.admission_only, args.intel_investigation)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Disposable Apple SSH control failed: " + type(error).__name__ + "; no admission claim", file=sys.stderr)
        raise SystemExit(125)
