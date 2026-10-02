"""Candidate wired iPhone control plane, never an RPC data tunnel or device qualification.

The application, NOT devicectl, performs create-only publication. Two copied
staging files carry bounded data and its exact seal; only verified complete bytes
can become the app's canonical inbox/Stop. Unknown CoreDevice schemas fail closed.
Physical copy behavior, wired transport, 4-second observations, signing and outer
native finalization still require an actual selected owner-authorized iPhone.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import stat
import time

import rpc_mobile_capacity as protocol

need = protocol.need
IOS_PACKAGE = 'dev.p2pkit.rpc.phonelab'
DEVICECTL = Path('/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/Resources/bin/devicectl')
COREDEVICE_INFO = DEVICECTL.parents[1] / 'Info.plist'
COREDEVICE_VERSION = '642.16'
INPUTS = frozenset(('inbox.txt', 'stop.txt'))
OUTPUTS = frozenset(('prepared.txt', 'ready.txt', 'telemetry.txt', 'closed.txt', 'failed.txt'))
FILES = INPUTS | OUTPUTS | {prefix + name for prefix in ('.incoming-', '.sealed-') for name in INPUTS}
ATOMIC_SCRATCH = r'\.capacity-[A-F0-9]{8}(?:-[A-F0-9]{4}){3}-[A-F0-9]{12}'
INBOX_FIELDS = protocol.BINDINGS | {'hostAddress', 'hostPort', 'hostInterface', 'subnets', 'clientPins'}


def input_seal(name, raw):
    need(name in INPUTS)
    protocol.parse(raw)
    return ('schema=1\nname=' + name + '\nbytes=' + str(len(raw)) + '\nsha256=' +
            hashlib.sha256(raw).hexdigest() + '\n').encode('ascii')


def verify_input(name, raw, seal):
    need(type(seal) is bytes and seal == input_seal(name, raw), 'Incomplete, changed or cross-file USB input')
    return raw


def selected_details(value, selected):
    need(type(value) is dict and type(value.get('result')) is dict)
    # Query ONE explicit device, never enumerate the owner's other devices.
    protocol.ios_usb_details(dict(result=dict(devices=[value['result']])), selected)


def file_inventory(value):
    need(type(value) is dict and type(value.get('result')) is dict)
    rows = value['result'].get('files')
    need(type(rows) is list and len(rows) <= len(FILES) + 1)
    result, seen, scratch = {}, set(), 0
    for row in rows:
        need(type(row) is dict and type(row.get('name')) is str and
             (row['name'] in FILES or re.fullmatch(ATOMIC_SCRATCH, row['name'])) and
             row['name'] not in seen and row.get('isDirectory') is False and row.get('isSymbolicLink') is False and
             type(row.get('fileSize')) is int and 0 <= row['fileSize'] <= protocol.RECORD_LIMIT,
             'Unknown, foreign, linked or unbounded app-container entry; preserve it, do not guess')
        seen.add(row['name'])
        if row['name'] in FILES:
            result[row['name']] = row['fileSize']
        else:
            # One serial app-owned atomic publisher can be in flight while
            # telemetry is listed. Never copy, consume or delete its scratch.
            # This is not proof of its retirement: the app's checked unlink,
            # controlHealthy closure and outer finalization remain required.
            scratch += 1
            need(scratch == 1, 'More than one app atomic publication is unproven')
    return result


def inbox_record(raw, bound):
    row = protocol.parse(raw)
    need(set(row) == INBOX_FIELDS and {k: row[k] for k in protocol.BINDINGS} == protocol.binding(bound) and
         bound['hostPlatform'] == 'Ios', 'Exact source/run/role/signed-executable binding required')
    need(re.fullmatch('[A-Za-z0-9_.:-]{1,32}', row['hostInterface']) and
         re.fullmatch('[1-9][0-9]{3,4}', row['hostPort']) and 1024 <= int(row['hostPort']) <= 65535)
    address = ipaddress.IPv4Address(row['hostAddress'])
    ranges = [ipaddress.IPv4Network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    subnets = row['subnets'].split(',')
    need(1 <= len(subnets) <= 16 and len(set(subnets)) == len(subnets))
    networks = [ipaddress.IPv4Network(n, strict=True) for n in subnets]
    need(all(any(n.subnet_of(r) for r in ranges) for n in networks) and any(address in n for n in networks),
         'Explicit private LAN only; actual production path policy and owner approval remain mandatory')
    pins = row['clientPins'].split(',')
    need(len(pins) == len(set(pins)) == 128 and all(re.fullmatch('p2f1-[a-z2-7]{52}', p) for p in pins),
         'Exactly 128 distinct public synthetic pins required; native peer parsing is not bypassed')
    return row


class IosUsb:
    """One source-bound session. No automatic app start, replay, installation, signing or pairing."""
    def __init__(self, backend, binding, *, owner_authorized=False, now=time.monotonic):
        need(owner_authorized is True, 'Explicit selected-device owner authorization required')
        self.binding = protocol.binding(binding)
        need(self.binding['hostPlatform'] == 'Ios')
        self.backend, self.now = backend, now
        self.started = self.authorized = self.provisioned = self.provision_attempted = False
        self.stop_attempted = self.runtime_closed = self.closed = False
        self.protocol = None
        self.last_sample = None

    def start(self):
        need(not self.started and not self.closed)
        self.started = True
        deadline = self.now() + 30
        self.backend.verify(deadline)
        raw = self.backend.read('prepared.txt', deadline)
        expected = dict(schema='1', scope='ios-usb-slot', runLabel=self.binding['runLabel'],
                        sourceSha=self.binding['hostSourceSha'], artifactSha256=self.binding['hostArtifactSha256'])
        need(raw is not None and protocol.parse(raw) == expected and self.now() < deadline,
             'Owner must first prepare a NEW slot in the source-matched, signed, selected iPhone app')
        self.authorized = True

    def provision(self, raw):
        need(self.authorized and not self.provision_attempted and not self.closed)
        row = inbox_record(raw, self.binding)
        self.protocol = protocol.Protocol(self.binding, row['hostAddress'], int(row['hostPort']))
        # A failed return might follow publication. Preserve ownership and attempt
        # exact Stop on cleanup rather than incorrectly assuming the app never saw it.
        self.provision_attempted = self.provisioned = True
        deadline = self.now() + 30
        self.backend.publish('inbox.txt', raw, deadline)
        need(self.now() < deadline, 'USB provisioning exceeded its original command budget')

    def read(self, name, timeout=4):
        need(self.provisioned and not self.closed and name in OUTPUTS - {'prepared.txt'} and
             type(timeout) in (int, float) and 0 < timeout <= 4)
        deadline = self.now() + timeout
        raw = self.backend.read(name, deadline)
        need(self.now() < deadline, 'USB observation exceeded its single original budget')
        row = protocol.parse(raw) if raw is not None else None
        if row is not None:
            if name == 'failed.txt':
                raise ValueError('Phone reported a failed control session; no retry or capacity claim')
            if name == 'ready.txt':
                self.protocol.ready(row)
            elif name == 'closed.txt':
                need(self.stop_attempted, 'Unrequested/old closure cannot retire this session')
                self.protocol.closed(row)
                self.runtime_closed = True
            elif name == 'telemetry.txt':
                need(self.last_sample is None or self.now() - self.last_sample < 4.5,
                     'New/stale sample arrived after the original freshness deadline')
                if self.protocol.telemetry(row) is not None:
                    self.last_sample = self.now()
        if name == 'telemetry.txt':
            need(self.last_sample is None or self.now() - self.last_sample < 4.5,
                 'An absent/unchanged slot cannot refresh telemetry freshness')
        return row

    def stop(self, raw):
        need(self.provisioned and not self.closed and not self.stop_attempted and
             protocol.parse(raw) == self.protocol.stop(), 'Only this exact run may request Stop once')
        self.stop_attempted = True
        deadline = self.now() + 30
        self.backend.publish('stop.txt', raw, deadline)
        need(self.now() < deadline, 'Stop publication exceeded its original command budget')

    def close(self):
        need(not self.closed)
        self.closed = True
        # Device evidence is intentionally preserved. Do not kill the app, remove
        # its container, revoke global pairing, or claim that a host process exit
        # proved native/runtime retirement.
        return dict(runtimeClosed=self.runtime_closed, clientPinsRemoved=self.runtime_closed,
                    deviceEvidenceRetained=True, devicePairingRevoked=False,
                    requiresOuterNativeFinalization=True, capacityQualified=False)


class DevicectlFiles:
    """Candidate fixed-command backend, usable only within an admitted native owner.

    Exact schema and transport observations must pass on the real selected phone.
    We do not invent missing-file exit codes or treat tool success as publication.
    The Xcode shell launcher is forbidden: it can automatically run first-launch
    installation. Invoke only the already installed, version/hash-bound native tool.
    """
    def __init__(self, commands, directory, selected, run_label, *, now=time.monotonic):
        need(platform.system() == 'Darwin' and os.getuid() == os.geteuid() != 0 and
             os.environ.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'), 'Admitted unprivileged native Mac owner required')
        need(re.fullmatch('[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}', selected) and
             re.fullmatch('[a-z0-9-]{1,64}', run_label), 'Explicit CoreDevice identifier and selected run required')
        self.commands, self.directory, self.selected, self.now = commands, directory, selected, now
        commands.files.private_directory(directory)
        self.remote = 'Library/Application Support/rpc-capacity/' + run_label
        self.count = 0
        self.attempted = set()
        self.tool_sha256 = self.tool_binding()

    def tool_binding(self):
        need(DEVICECTL.resolve(strict=True) == DEVICECTL and COREDEVICE_INFO.resolve(strict=True) == COREDEVICE_INFO,
             'Use the physical installed CoreDevice tool, not a shim or automatic installer')
        info = DEVICECTL.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
             stat.S_IMODE(info.st_mode) & 0o022 == 0 and os.access(DEVICECTL, os.X_OK) and info.st_size <= 64 * 1024 * 1024)
        raw = DEVICECTL.read_bytes()
        need(raw[:4] in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'),
             'Native executable required, never the first-launch shell wrapper')
        need(COREDEVICE_INFO.stat().st_size <= 65536)
        metadata = plistlib.loads(COREDEVICE_INFO.read_bytes())
        need(metadata.get('CFBundleIdentifier') == 'com.apple.CoreDevice' and
             metadata.get('CFBundleVersion') == COREDEVICE_VERSION, 'Unreviewed installed CoreDevice version')
        return hashlib.sha256(raw).hexdigest()

    def remaining(self, deadline):
        remaining = deadline - self.now()
        need(0 < remaining <= 120, 'USB setup/observation consumed its original deadline')
        return remaining

    def read_owned(self, path, limit=protocol.RECORD_LIMIT):
        self.commands.files.private_directory(self.directory)
        need(path.parent == self.directory and not path.is_symlink())
        before = path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
             stat.S_IMODE(before.st_mode) in (0o600, 0o644) and 0 < before.st_size <= limit)
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino))
            os.fchmod(stream.fileno(), 0o600)  # Only this NEW owned local output, never remote/system permissions.
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        need(len(raw) == before.st_size <= limit and
             (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and
             after.st_uid == before.st_uid and after.st_nlink == 1 and stat.S_IMODE(after.st_mode) == 0o600 and
             (path.lstat().st_dev, path.lstat().st_ino) == (before.st_dev, before.st_ino), 'Copied local file changed')
        return raw

    def command(self, label, arguments, deadline):
        need(self.tool_binding() == self.tool_sha256, 'Installed developer tool changed')
        self.count += 1
        need(self.count <= 15000)
        output = self.directory / (f'{self.count:05d}-' + label + '.json')
        need(not output.exists() and not output.is_symlink())
        self.commands.run('ios-' + label, [str(DEVICECTL), *arguments, '--json-output', str(output)],
                          timeout=self.remaining(deadline))
        need(self.now() < deadline and self.tool_binding() == self.tool_sha256, 'Late or changed native tool observation')
        value = json.loads(self.read_owned(output, 262144), object_pairs_hook=unique)
        need(type(value) is dict and type(value.get('info')) is dict and
             value['info'].get('outcome') == 'success' and type(value.get('result')) is dict,
             'A missing/failed native JSON result is not successful transfer or file absence')
        return value

    def verify(self, deadline):
        value = self.command('selected-details', ['device', 'info', 'details', '--device', self.selected], deadline)
        selected_details(value, self.selected)

    def inventory(self, deadline):
        value = self.command('slot-files', ['device', 'info', 'files', '--device', self.selected,
            '--domain-type', 'appDataContainer', '--domain-identifier', IOS_PACKAGE, '--subdirectory', self.remote], deadline)
        return file_inventory(value)

    def copy(self, direction, local, name, deadline):
        need(name in FILES and direction in ('to', 'from') and local.parent == self.directory)
        source, destination = ((str(local), self.remote + '/' + name) if direction == 'to' else
                               (self.remote + '/' + name, str(local)))
        self.command('copy-' + direction, ['device', 'copy', direction, '--device', self.selected,
            '--domain-type', 'appDataContainer', '--domain-identifier', IOS_PACKAGE,
            '--source', source, '--destination', destination], deadline)

    def download(self, name, deadline):
        need(name in FILES)
        local = self.directory / (f'{self.count + 1:05d}-download')
        need(not local.exists() and not local.is_symlink(), 'Copy output must be new, never replace local evidence')
        self.copy('from', local, name, deadline)
        return self.read_owned(local)

    def read(self, name, deadline):
        need(name in OUTPUTS)
        self.verify(deadline)
        rows = self.inventory(deadline)
        raw = self.download(name, deadline) if name in rows else None
        self.verify(deadline)
        return raw

    def publish(self, name, raw, deadline):
        need(name in INPUTS and name not in self.attempted)
        seal = input_seal(name, raw)
        self.attempted.add(name)  # Never repeat even if a tool fails after having copied some/all bytes.
        self.verify(deadline)
        rows = self.inventory(deadline)
        need(not {name, '.incoming-' + name, '.sealed-' + name} & set(rows),
             'Existing canonical/staging input cannot be replaced or adopted')
        data = self.directory / ('outgoing-' + name)
        marker = self.directory / ('seal-' + name)
        self.commands.files.write_private(data, raw)
        self.commands.files.write_private(marker, seal)
        self.copy('to', data, '.incoming-' + name, deadline)
        need(self.download('.incoming-' + name, deadline) == raw, 'Actual device staging bytes differ; never publish seal')
        self.copy('to', marker, '.sealed-' + name, deadline)
        self.verify(deadline)
        # Raw copies are NOT atomic/create-only. Only the app's sealed input
        # import can publish canonical files; ready/closed still must prove it.


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate developer-tool JSON field')
        result[key] = value
    return result
