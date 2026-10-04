"""Private wired developer-control files only. Never an RPC transport or a LAN-admission exception.

All subprocesses must remain inside the caller's admitted native ownership scope.
No global ADB server, arbitrary remote shell, forwarding, pairing-store read or PID-based
cleanup is used. Phone-local approval is still required before importing RPC pins.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time

import rpc_mobile_capacity as protocol

ANDROID_PACKAGE = 'dev.p2pkit.sample.android'
IOS_PACKAGE = 'dev.p2pkit.rpc.phonelab'
need = protocol.need
ANDROID_SHELL_STAGES = (
    'entry', 'classpath', 'uid', 'home', 'base-create', 'directory-type', 'directory-owner', 'directory-mode',
    'run-create', 'absence', 'data-open', 'data-descriptor', 'data-input', 'data-close',
    'data-type', 'data-identity', 'data-mode', 'data-owner', 'data-links', 'data-size', 'seal-create',
    'seal-presence', 'seal-type', 'seal-owner', 'seal-mode', 'seal-links', 'seal-size',
    'seal-metadata', 'seal-open', 'seal-descriptor', 'read-presence', 'read-type', 'read-owner',
    'read-mode', 'read-links', 'read-size', 'read-metadata', 'read-open', 'read-descriptor',
    'read-data', 'read-after', 'seal-after',
)


def android_shell_failure_stage(raw):
    """Closed EXIT-trap markers only; never expose stderr, values, paths or input data."""
    need(type(raw) is bytes and len(raw) <= 262144)
    prefix = b'P2PKIT_RPC_USB_STAGE='
    markers = [line[len(prefix):] for line in raw.splitlines() if line.startswith(prefix)]
    need(len(markers) <= 4 and all(value in {n.encode() for n in ANDROID_SHELL_STAGES} for value in markers))
    return markers[-1].decode('ascii') if markers else None


def android_shell_v2_supported(raw):
    """Parse `adb features` CLI lines, not its different comma-delimited wire reply.

    The CLI intersects client/device support and prints one name per line.
    Reject malformed, duplicate or oversized output; a substring is not support.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= protocol.RECORD_LIMIT:
        return False
    features = raw.split(b'\n')
    if features[-1] == b'':
        features.pop()
    return (1 <= len(features) <= 256 and len(set(features)) == len(features) and
            all(re.fullmatch(rb'[a-z0-9_]{1,128}', name) is not None for name in features) and
            b'shell_v2' in features)


class Commands:
    """Bounded direct children; on a timeout the native owner, not a raw PID kill, drains them."""
    def __init__(self, directory, env, files):
        need(os.environ.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'))
        self.directory, self.env, self.files = directory, dict(env), files
        files.private_directory(directory)
        self.count, self.unsafe, self.rows = 0, False, []

    def run(self, label, argv, timeout=30, data=None, allowed=(0,)):
        need(not self.unsafe and re.fullmatch('[a-z0-9-]{1,64}', label) and self.count < 15000)
        need(type(timeout) in (int, float) and 0 < timeout <= 150 and
             (data is None or type(data) is bytes and len(data) <= protocol.RECORD_LIMIT))
        started = time.monotonic()
        deadline = started + timeout
        self.count += 1
        stem = self.directory / (str(self.count).zfill(5) + '-' + label)
        row = dict(label=label, timeoutSeconds=timeout, exitCode=None)
        self.rows.append(row)
        source = None
        if data is not None:
            path = stem.with_suffix('.input')
            self.files.write_private(path, data)
            source = path.open('rb')  # A bounded regular input cannot block the coordinator's write to a pipe.
        try:
            # Permissions must be private at creation, not inherited from a
            # particular entry point's umask or repaired after child output.
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            with os.fdopen(os.open(stem.with_suffix('.stdout'), flags, 0o600), 'wb') as out, \
                    os.fdopen(os.open(stem.with_suffix('.stderr'), flags, 0o600), 'wb') as err:
                need(time.monotonic() < deadline, 'USB setup consumed the original command deadline; do not launch')
                child = subprocess.Popen(list(map(str, argv)), env=self.env,
                    stdin=source if source is not None else subprocess.DEVNULL, stdout=out, stderr=err)
                while child.poll() is None:
                    if time.monotonic() >= deadline or max(out.tell(), err.tell()) > 262144:
                        self.unsafe = True
                        raise RuntimeError('USB command deadline or output bound; native ownership must finalize')
                    time.sleep(.05)
                elapsed = time.monotonic() - started
                row.update(exitCode=child.returncode, elapsedMillis=round(elapsed * 1000))
                need(elapsed < timeout, 'A late USB command exit is not a timely observation')
                need(max(out.tell(), err.tell()) <= 262144, 'USB command output exceeded its private bound')
            need(row['exitCode'] in allowed, 'Wired developer command failed; inspect private evidence')
            return row['exitCode'], self.files.read_private(stem.with_suffix('.stdout'))
        finally:
            if source is not None:
                source.close()


def android_script(run_label, operation, name=None):
    """Fixed shell grammar; no field, address, pin or payload is interpolated into executable text."""
    need(re.fullmatch('[a-z0-9-]{1,64}', run_label) and operation in ('prepare', 'read', 'stop'))
    need(name in protocol.FILES if operation == 'read' else name is None)
    base = 'no_backup/rpc-capacity'
    run = base + '/' + run_label
    # `run-as` is restricted by Android to this debuggable package. No shared
    # storage, chmod of an existing foreign directory, root or shell permission grant.
    common = '''rpc_stage=entry
trap 'rpc_exit=$?; trap - 0; if test "$rpc_exit" -ne 0; then printf "P2PKIT_RPC_USB_STAGE=%s\\n" "$rpc_stage" >&2; fi; exit "$rpc_exit"' 0
set -eu
umask 077
rpc_stage=classpath
test -f "$CLASSPATH"
test ! -L "$CLASSPATH"
rpc_fd_metadata() {
    /system/bin/app_process /system/bin dev.p2pkit.sample.android.rpclab.RpcLabFdStat "$1"
}
rpc_stage=uid
uid=$(id -u)
private_dir() {
    rpc_stage=directory-type
    test -d "$1"
    test ! -L "$1"
    rpc_stage=directory-owner
    test "$(stat -c %u "$1")" = "$uid"
    rpc_stage=directory-mode
    test "$(stat -c %a "$1")" = 700
}
rpc_stage=home
test -d no_backup
test ! -L no_backup
'''
    if operation == 'prepare':
        common += f'''rpc_stage=base-create
if test ! -e {base}; then mkdir {base}; fi
private_dir {base}
rpc_stage=run-create
mkdir {run}
private_dir {run}
'''
    else:
        common += f'private_dir {base}\nprivate_dir {run}\n'
    if operation in ('prepare', 'stop'):
        name = 'inbox.txt' if operation == 'prepare' else 'stop.txt'
        target, marker = run + '/' + name, run + '/.complete-' + name
        # Android's app sandbox forbids hard links, even through run-as. The
        # data and empty completion marker are BOTH create-only. Readers never
        # admit data before the completion syscall. Interrupted data is retained
        # unsealed; it is not overwritten, reclaimed or treated as a publication.
        return common + f'''set -C
rpc_stage=absence
test ! -e {target}
test ! -L {target}
test ! -e {marker}
test ! -L {marker}
rpc_stage=data-open
exec 3> {target}
rpc_stage=data-descriptor
identity=$(rpc_fd_metadata identity 5>&3)
rpc_stage=data-input
cat >&3
rpc_stage=data-close
exec 3>&-
rpc_stage=data-type
test -f {target}
test ! -L {target}
rpc_stage=data-identity
test "$(stat -c %d:%i {target})" = "$identity"
rpc_stage=data-mode
test "$(stat -c %a {target})" = 600
rpc_stage=data-owner
test "$(stat -c %u {target})" = "$uid"
rpc_stage=data-links
test "$(stat -c %h {target})" = 1
rpc_stage=data-size
size=$(stat -c %s {target})
test "$size" -gt 0
test "$size" -le 16384
rpc_stage=seal-create
: > {marker}
'''
    path = run + '/' + name
    if name != 'telemetry.txt':
        marker = run + '/.complete-' + name
        common += f'''rpc_stage=seal-presence
if test ! -e {marker} && test ! -L {marker}; then exit 44; fi
rpc_stage=seal-type
test -f {marker}
test ! -L {marker}
rpc_stage=seal-owner
test "$(stat -c %u {marker})" = "$uid"
rpc_stage=seal-mode
test "$(stat -c %a {marker})" = 600
rpc_stage=seal-links
test "$(stat -c %h {marker})" = 1
rpc_stage=seal-size
test "$(stat -c %s {marker})" = 0
rpc_stage=seal-metadata
seal=$(stat -c %d:%i:%s:%Y:%a:%u:%h {marker})
rpc_stage=seal-open
exec 4< {marker}
rpc_stage=seal-descriptor
opened_seal=$(rpc_fd_metadata record 5<&4)
test "$seal" = "$opened_seal"
'''
    else:
        common += f'rpc_stage=read-presence\nif test ! -e {path} && test ! -L {path}; then exit 44; fi\n'
    common += f'''rpc_stage=read-type
test -f {path}
test ! -L {path}
rpc_stage=read-owner
test "$(stat -c %u {path})" = "$uid"
rpc_stage=read-mode
test "$(stat -c %a {path})" = 600
rpc_stage=read-links
test "$(stat -c %h {path})" = 1
rpc_stage=read-size
size=$(stat -c %s {path})
test "$size" -gt 0
test "$size" -le 16384
rpc_stage=read-metadata
identity=$(stat -c %d:%i:%s:%Y:%a:%u:%h {path})
rpc_stage=read-open
exec 3< {path}
rpc_stage=read-descriptor
opened_record=$(rpc_fd_metadata record 5<&3)
test "$identity" = "$opened_record" || exit 45
rpc_stage=read-data
cat <&3
rpc_stage=read-after
after_record=$(rpc_fd_metadata record 5<&3)
test "$identity" = "$after_record"
'''
    if name != 'telemetry.txt':
        common += f'''rpc_stage=seal-after
test "$seal" = "$(stat -c %d:%i:%s:%Y:%a:%u:%h {marker})"
after_seal=$(rpc_fd_metadata record 5<&4)
test "$seal" = "$after_seal"
'''
    return common


def android_shell(run_label, operation, name=None):
    # ADB exec-out reads output only: it neither forwards stdin nor reports the
    # remote exit code. Shell v2 does both; -T prevents PTY newline rewriting and
    # -e none disables client escape processing. ADB shell joins argv, so quote
    # the one fixed inner script as a whole. Never interpolate imported records.
    # Resolve only the explicitly installed debug package, never caller-supplied
    # executable text. Split/adopted-storage APKs are not this test distribution.
    # The trusted package manager selects the APK; run-as retains its app UID.
    # The class uses real fstat, not readlink + pathname stat or assumed stat -L.
    command = f'''set -eu
apk=$(pm path {ANDROID_PACKAGE})
case "$apk" in package:/data/app/*/base.apk) ;; *) exit 1;; esac
apk=${{apk#package:}}
case "$apk" in *[!A-Za-z0-9_./+=~-]*|*/../*|*/./*) exit 1;; esac
export CLASSPATH="$apk"
exec run-as {ANDROID_PACKAGE} sh -c {shlex.quote(android_script(run_label, operation, name))}
'''
    return ['shell', '-T', '-e', 'none', 'sh -c ' + shlex.quote(command)]


class AndroidUsb:
    def __init__(self, commands, directory, adb, selected, run_label):
        need(re.fullmatch('[A-Za-z0-9_-]{1,128}', selected) and not selected.startswith('emulator-'))
        self.commands, self.directory, self.adb = commands, directory, adb
        self.selected, self.run_label = selected, run_label
        self.server, self.log, self.socket_identity = None, None, None
        self.key_identities = {}
        self.provisioned = False
        self.closed = False
        self.authorized = False
        self.started = False
        # ADB uses HOME/.android, not the SDK's ANDROID_USER_HOME alone.
        self.home = self.directory / 'adb-home/.android'
        self.socket = self.directory / 'adb.sock'

    def start(self):
        need(not self.started and not self.closed)
        self.started = True
        for name in ('adb-home', 'adb-home/.android'):
            (self.directory / name).mkdir(mode=0o700)
        need(len(os.fsencode(self.socket)) < 100, 'Private ADB Unix-socket path exceeds the portable bound')
        for name in ('ADB_VENDOR_KEYS', 'ADB_SERVER_PORT', 'ANDROID_ADB_SERVER_PORT', 'ANDROID_SDK_HOME'):
            self.commands.env.pop(name, None)
        self.commands.env.update(HOME=str(self.directory / 'adb-home'), ANDROID_USER_HOME=str(self.home),
                                 ADB_SERVER_SOCKET='localfilesystem:' + str(self.socket), ADB_MDNS_AUTO_CONNECT='0')
        self.log = (self.directory / 'adb-server.log').open('xb')
        self.server = subprocess.Popen([str(self.adb), '-L', self.commands.env['ADB_SERVER_SOCKET'], 'nodaemon', 'server'],
            env=self.commands.env, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT, umask=0o077)
        deadline = time.monotonic() + 20
        while not self.socket.exists():
            need(self.server.poll() is None and time.monotonic() < deadline, 'Private ADB did not become ready')
            time.sleep(.1)
        info = self.socket.lstat()
        need(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid())
        self.socket_identity = info.st_dev, info.st_ino
        # Only our new server's key metadata is observed; no existing/custodian
        # key is opened, copied or reused. Auth on the phone is an explicit owner action.
        for path in self.home.iterdir():
            need(path.name in ('adbkey', 'adbkey.pub'), 'Unexpected file in the new private ADB key directory')
            info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                 stat.S_IMODE(info.st_mode) & 0o077 == 0)
            self.key_identities[path] = info.st_dev, info.st_ino
        need({p.name for p in self.key_identities} == {'adbkey', 'adbkey.pub'}, 'New private ADB keys were not established')

    def await_authorization(self, timeout=120):
        """Owner approval of the fresh ADB key is BEFORE the RPC readiness window."""
        need(self.started and not self.closed and not self.authorized and type(timeout) in (int, float) and 0 < timeout <= 120)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            need(remaining > 0, 'Explicit selected-device USB authorization did not complete')
            _, raw = self.adb_command('android-authorization-inventory', ['devices', '-l'], timeout=min(4, remaining))
            state = protocol.android_usb_state(raw.decode('utf-8'), self.selected)
            if state == 'device':
                self.verify(deadline=deadline)
                need(time.monotonic() < deadline, 'USB authorization exceeded its original bound')
                self.authorized = True
                return
            time.sleep(min(.5, max(0, deadline - time.monotonic())))

    def alive(self):
        need(self.server is not None and self.server.poll() is None and self.log.tell() <= 1048576,
             'The owned private ADB server exited or exceeded its log bound')
        info = self.socket.lstat()
        need(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and
             (info.st_dev, info.st_ino) == self.socket_identity, 'The private ADB socket lifetime changed')

    def adb_command(self, label, arguments, **options):
        self.alive()
        result = self.commands.run(label, [self.adb, *arguments], **options)
        self.alive()
        return result

    def verify(self, deadline=None):
        def remaining():
            value = 30 if deadline is None else min(30, deadline - time.monotonic())
            need(value > 0, 'Selected-device verification exceeded its single authorization bound')
            return value
        _, raw = self.adb_command('android-wired-inventory', ['devices', '-l'], timeout=remaining())
        protocol.android_usb_inventory(raw.decode('utf-8'), self.selected)
        _, raw = self.adb_command('android-shell-v2', ['-s', self.selected, 'features'], timeout=remaining())
        need(android_shell_v2_supported(raw), 'Actual shell v2 is required; legacy exec-in/out are not substitutes')
        _, raw = self.adb_command('android-physical-device', ['-s', self.selected, 'shell', 'getprop', 'ro.kernel.qemu'], timeout=remaining())
        need(raw.strip() in (b'', b'0'), 'An emulator cannot supply physical phone evidence')

    def provision(self, raw):
        need(self.authorized and not self.provisioned)
        protocol.parse(raw)
        # The sealed inbox may already be visible when the command reports a
        # failure. Retain the exact-run Stop obligation and forbid another
        # publication attempt; this flag is not a successful USB-copy receipt.
        self.provisioned = True
        self.adb_command('android-provision-private', ['-s', self.selected, *android_shell(self.run_label, 'prepare')], data=raw)

    def read(self, name, timeout=4):
        need(self.provisioned and name in protocol.FILES and type(timeout) in (int, float) and 0 < timeout <= 4)
        # Only an immutable telemetry publication race can be reobserved. No
        # failed RPC, stale sample, different identity or command error is retried.
        deadline = time.monotonic() + timeout
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            need(remaining > 0, 'USB observation exceeded the single original read budget')
            code, raw = self.adb_command('android-read-' + name.removesuffix('.txt'),
                ['-s', self.selected, *android_shell(self.run_label, 'read', name)], timeout=remaining,
                allowed=(0, 44, 45) if name == 'telemetry.txt' else (0, 44))
            if code == 44:
                need(not raw)
                return None
            if code == 0:
                return protocol.parse(raw)
            need(attempt < 2 and not raw, 'Repeated telemetry lifetime change')
        raise AssertionError('unreachable')

    def stop(self, raw):
        need(self.provisioned)
        protocol.parse(raw)
        self.adb_command('android-stop-private', ['-s', self.selected, *android_shell(self.run_label, 'stop')], data=raw)

    def close(self):
        need(not self.closed)
        if self.server is not None:
            if self.server.poll() is None:
                self.alive()
                # Address only the Unix socket created above. Never the global server.
                self.commands.run('private-adb-stop', [self.adb, 'kill-server'], timeout=15)
            need(self.server.wait(timeout=20) == 0, 'Private ADB did not exit cleanly')
        if self.log is not None:
            self.log.close()
        for path, identity in self.key_identities.items():
            info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                 stat.S_IMODE(info.st_mode) == 0o600 and (info.st_dev, info.st_ino) == identity,
                 'Private test-key lifetime changed; preserve for review')
        for path in self.key_identities:
            path.unlink()
        need(not self.home.exists() or not list(self.home.iterdir()), 'Unrecognized private ADB state remains')
        self.closed = True
        return dict(privateServerExited=True, testHostKeysRetired=True,
                    deviceUsbAuthorizationRevoked=False)



from rpc_ios_usb import IosUsb  # Candidate sealed app-owned publication; never a raw-copy qualification claim.
