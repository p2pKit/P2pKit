"""Candidate iPhone CoreDevice control plane, never an RPC data tunnel or device qualification.

The application, NOT devicectl, performs create-only publication. Two copied
staging files carry bounded data and its exact seal; only verified complete bytes
can become the app's canonical inbox/Stop. Unknown CoreDevice schemas fail closed.
Physical copy behavior, the explicitly selected transport, 4-second observations, signing and outer
native finalization still require an actual selected owner-authorized iPhone.
"""
from __future__ import annotations

import hashlib
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
MAX_COMMANDS = 20_000
IOS_PACKAGE = 'dev.p2pkit.rpc.phonelab'
DEVICECTL = Path('/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/Resources/bin/devicectl')
COREDEVICE_INFO = DEVICECTL.parents[1] / 'Info.plist'
INPUTS = frozenset(('inbox.txt', 'campaign.txt', 'next.txt', 'stop.txt'))
OUTPUTS = frozenset(('prepared.txt', 'next-ready.txt', 'ready.txt', 'telemetry.txt', 'closed.txt', 'failed.txt'))
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


def selected_details(value, selected, *, control_transport='wired'):
    need(type(value) is dict and type(value.get('result')) is dict)
    # Query ONE explicit device, never enumerate the owner's other devices.
    protocol.ios_device_details(dict(result=dict(devices=[value['result']])), selected,
                                control_transport=control_transport)


def file_properties(row):
    """Read the two observed CoreDevice shapes without converting missing/ambiguous flags."""
    need(type(row) is dict)
    if 'metadata' not in row and 'resources' not in row:
        return row  # Historical flat schema; callers still require exact boolean/integer types.
    need(type(row.get('metadata')) is dict and type(row.get('resources')) is dict and
         not {'fileSize', 'isDirectory', 'isSymbolicLink'} & set(row),
         'Incomplete or ambiguous CoreDevice file metadata; preserve it, do not infer flags')
    return dict(fileSize=row['metadata'].get('size'),
                isDirectory=row['resources'].get('isDirectory'),
                isSymbolicLink=row['resources'].get('isSymbolicLink'))


def file_inventory(value):
    need(type(value) is dict and type(value.get('result')) is dict)
    rows = value['result'].get('files')
    need(type(rows) is list and len(rows) <= len(FILES) + 1)
    result, seen, scratch = {}, set(), 0
    for row in rows:
        properties = file_properties(row)
        need(type(row) is dict and type(row.get('name')) is str and
             (row['name'] in FILES or re.fullmatch(ATOMIC_SCRATCH, row['name'])) and
             row['name'] not in seen and properties.get('isDirectory') is False and
             properties.get('isSymbolicLink') is False and type(properties.get('fileSize')) is int and
             0 <= properties['fileSize'] <= protocol.RECORD_LIMIT,
             'Unknown, foreign, linked or unbounded app-container entry; preserve it, do not guess')
        seen.add(row['name'])
        if row['name'] in FILES:
            result[row['name']] = properties['fileSize']
        else:
            # One serial app-owned atomic publisher can be in flight while
            # telemetry is listed. Never copy, consume or delete its scratch.
            # This is not proof of its retirement: the app's checked unlink,
            # controlHealthy closure and outer finalization remain required.
            scratch += 1
            need(scratch == 1, 'More than one app atomic publication is unproven')
    return result


def inbox_record(raw, bound):
    row = protocol.inbox(raw, bound)
    need(bound['hostPlatform'] == 'Ios', 'Exact iOS signed-executable binding required')
    return row


class IosUsb:
    """One source-bound session. Only sealed development activation; no replay, signing or pairing."""
    def __init__(self, backend, binding, *, owner_authorized=False, now=time.monotonic):
        need(owner_authorized is True, 'Explicit selected-device owner authorization required')
        self.binding = protocol.binding(binding)
        need(self.binding['hostPlatform'] == 'Ios')
        self.backend, self.now = backend, now
        self.started = self.authorized = self.provisioned = self.provision_attempted = False
        self.stop_attempted = self.runtime_closed = self.closed = False
        self.activation_attempted = False
        self.inbox_sha256 = None
        self.protocol = None
        self.last_sample = None

    def start(self):
        need(not self.started and not self.closed)
        self.started = True
        deadline = self.now() + 30
        self.backend.verify(deadline)
        expected = dict(schema=self.binding['schema'], scope='ios-usb-slot', runLabel=self.binding['runLabel'],
                        sourceSha=self.binding['hostSourceSha'], artifactSha256=self.binding['hostArtifactSha256'])
        if self.binding['schema'] == '2':
            expected['clientCount'] = self.binding['clientCount']
        while True:
            need(self.now() < deadline, 'Selected development app did not prepare its new slot inside the setup bound')
            present = getattr(self.backend, 'slot_present', None)
            if present is not None and not present(deadline):
                time.sleep(.1)
                continue
            raw = self.backend.read('prepared.txt', deadline)
            if raw is not None:
                need(protocol.parse(raw) == expected and self.now() < deadline,
                     'Prepared slot differs from the selected source, signed executable, run or profile')
                break
            time.sleep(.1)
        self.authorized = True

    def provision(self, raw):
        need(self.authorized and not self.provision_attempted and not self.closed)
        row = inbox_record(raw, self.binding)
        self.protocol = protocol.Protocol(self.binding, row['hostAddress'], int(row['hostPort']))
        # A failed return might follow publication. Preserve ownership and attempt
        # exact Stop on cleanup rather than incorrectly assuming the app never saw it.
        self.provision_attempted = self.provisioned = True
        self.inbox_sha256 = hashlib.sha256(raw).hexdigest()
        deadline = self.now() + 30
        self.backend.publish('inbox.txt', raw, deadline)
        need(self.now() < deadline, 'USB provisioning exceeded its original command budget')

    def activate(self, raw):
        """Start only a DEBUG/development slot explicitly prepared for this campaign."""
        need(self.provisioned and not self.closed and not self.activation_attempted)
        inbox_record(raw, self.binding)
        need(hashlib.sha256(raw).hexdigest() == self.inbox_sha256, 'Campaign must bind the exact published inbox')
        command = dict(schema='1', scope='mobile-usb-start', runLabel=self.binding['runLabel'],
                       hostSourceSha=self.binding['hostSourceSha'],
                       hostArtifactSha256=self.binding['hostArtifactSha256'], inboxSha256=self.inbox_sha256)
        self.activation_attempted = True
        deadline = self.now() + 30
        self.backend.publish('campaign.txt', protocol.encode(command), deadline)
        need(self.now() < deadline, 'Campaign publication exceeded its original command budget')

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
    def __init__(self, commands, directory, selected, run_label, *, control_transport='wired', now=time.monotonic):
        need(platform.system() == 'Darwin' and os.getuid() == os.geteuid() != 0 and
             os.environ.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'), 'Admitted unprivileged native Mac owner required')
        need(re.fullmatch('[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}', selected) and
             re.fullmatch('[a-z0-9-]{1,64}', run_label), 'Explicit CoreDevice identifier and selected run required')
        self.commands, self.directory, self.selected, self.now = commands, directory, selected, now
        need(control_transport in ('wired', 'wireless'), 'Unknown Apple device control transport')
        self.control_transport = control_transport
        commands.files.private_directory(directory)
        self.remote = 'Library/Application Support/rpc-capacity/' + run_label
        self.count = 0
        self.attempted = set()
        self.tool_version = self.metadata_sha256 = None
        self.tool_sha256 = self.tool_binding()

    def tool_binding(self):
        need(DEVICECTL.resolve(strict=True) == DEVICECTL and COREDEVICE_INFO.resolve(strict=True) == COREDEVICE_INFO,
             'Use the physical installed CoreDevice tool, not a shim or automatic installer')
        info = DEVICECTL.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
             not info.st_mode & (stat.S_ISUID | stat.S_ISGID) and
             stat.S_IMODE(info.st_mode) & 0o022 == 0 and os.access(DEVICECTL, os.X_OK) and info.st_size <= 64 * 1024 * 1024)
        raw = DEVICECTL.read_bytes()
        need(raw[:4] in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'),
             'Native executable required, never the first-launch shell wrapper')
        metadata_info = COREDEVICE_INFO.lstat()
        need(stat.S_ISREG(metadata_info.st_mode) and metadata_info.st_uid == 0 and metadata_info.st_nlink == 1 and
             not stat.S_IMODE(metadata_info.st_mode) & 0o022 and 0 < metadata_info.st_size <= 65536,
             'Bounded root-owned regular developer metadata required, never a device/FIFO')
        metadata_raw = COREDEVICE_INFO.read_bytes()
        metadata = plistlib.loads(metadata_raw)
        version = metadata.get('CFBundleVersion')
        need(metadata.get('CFBundleIdentifier') == 'com.apple.CoreDevice' and type(version) is str and
             re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,6}){0,3}', version), 'Invalid installed CoreDevice identity/version')
        digest = hashlib.sha256(metadata_raw).hexdigest()
        if getattr(self, 'tool_version', None) is not None:
            need(version == self.tool_version and digest == self.metadata_sha256, 'Installed developer metadata changed')
        else:
            self.tool_version, self.metadata_sha256 = version, digest
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
        need(self.count <= MAX_COMMANDS)
        output = self.directory / (f'{self.count:05d}-' + label + '.json')
        need(not output.exists() and not output.is_symlink())
        arguments = list(arguments)
        need(arguments.count('--') <= 1, 'Ambiguous application argument delimiter')
        split = arguments.index('--') if '--' in arguments else len(arguments)
        argv = [str(DEVICECTL), *arguments[:split], '--json-output', str(output), *arguments[split:]]
        self.commands.run('ios-' + label, argv,
                          timeout=self.remaining(deadline))
        need(self.now() < deadline and self.tool_binding() == self.tool_sha256, 'Late or changed native tool observation')
        value = json.loads(self.read_owned(output, 262144), object_pairs_hook=unique)
        need(type(value) is dict and type(value.get('info')) is dict and
             value['info'].get('outcome') == 'success' and type(value.get('result')) is dict,
             'A missing/failed native JSON result is not successful transfer or file absence')
        return value

    def verify(self, deadline):
        value = self.command('selected-details', ['device', 'info', 'details', '--device', self.selected], deadline)
        selected_details(value, self.selected, control_transport=getattr(self, 'control_transport', 'wired'))

    def install_app(self, app, bound, deadline):
        """Install the selected signed development bundle; actual executable readback is still required at ready."""
        checked = protocol.binding(bound)
        need(checked['hostPlatform'] == 'Ios' and isinstance(app, Path) and app.is_absolute() and
             app == app.resolve(strict=True) and app.suffix == '.app' and app.is_dir())
        metadata = app / 'Info.plist'
        need(not metadata.is_symlink())
        info = metadata.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
             0 < info.st_size <= 65536 and not stat.S_IMODE(info.st_mode) & 0o022)
        values = plistlib.loads(metadata.read_bytes())
        name = values.get('CFBundleExecutable')
        need(values.get('CFBundleIdentifier') == IOS_PACKAGE and type(name) is str and
             re.fullmatch('[A-Za-z0-9_-]{1,128}', name), 'Only the fixed development phone app may be installed')
        executable = app / name
        info = executable.lstat()
        need(not executable.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
             info.st_nlink == 1 and 0 < info.st_size <= 256 * 1024 * 1024 and not stat.S_IMODE(info.st_mode) & 0o022)
        with os.fdopen(os.open(executable, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            need((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                 (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns))
            hasher, remaining = hashlib.sha256(), info.st_size
            while remaining:
                block = stream.read(min(1048576, remaining))
                need(block, 'Executable ended before its declared size')
                hasher.update(block)
                remaining -= len(block)
            need(not stream.read(1), 'Executable grew during verification')
            digest = hasher.hexdigest()
            after = os.fstat(stream.fileno())
        need((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) ==
             (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) and
             digest == checked['hostArtifactSha256'], 'Selected executable differs from the bound signed artifact')
        self.verify(deadline)
        self.command('install-bound-app', ['device', 'install', 'app', '--device', self.selected, str(app)], deadline)
        self.verify(deadline)
        return dict(installerSucceeded=True, artifactSha256=digest, requiresInstalledReadyHash=True)

    def launch_prepare(self, bound, deadline):
        """Prepare one development slot in a stopped app; never terminate or relaunch an active runtime."""
        checked = protocol.binding(bound)
        need(checked['hostPlatform'] == 'Ios' and checked['schema'] == '2')
        self.verify(deadline)
        self.command('launch-bound-prepare', ['device', 'process', 'launch', '--device', self.selected, IOS_PACKAGE, '--',
            '--rpc-usb-prepare', checked['runLabel'], '--rpc-usb-source-sha', checked['hostSourceSha'],
            '--rpc-usb-artifact-sha256', checked['hostArtifactSha256'], '--rpc-usb-client-count', checked['clientCount']], deadline)
        self.verify(deadline)

    def prepare_next(self, bound, previous_label, previous_inbox_sha256, deadline):
        """Request a new DEBUG slot only after the same installed app proves the prior exact run retired."""
        checked = protocol.binding(bound)
        need(checked['hostPlatform'] == 'Ios' and checked['schema'] == '2' and
             re.fullmatch('[a-z0-9-]{1,64}', previous_label) and previous_label != checked['runLabel'] and
             re.fullmatch('[a-f0-9]{64}', previous_inbox_sha256))
        original = self.remote
        self.remote = 'Library/Application Support/rpc-capacity/' + previous_label
        try:
            self.verify(deadline)
            rows = self.inventory(deadline)
            need({'inbox.txt', 'closed.txt'} <= set(rows), 'Prior iOS run must have actual inbox and healthy closure')
            raw = self.download('inbox.txt', deadline)
            need(hashlib.sha256(raw).hexdigest() == previous_inbox_sha256, 'Previous iOS inbox hash mismatch')
            parsed = protocol.parse(raw)
            old = protocol.binding({key: parsed[key] for key in protocol.binding_fields(parsed)})
            protocol.inbox(raw, old)
            need(old['schema'] == '2' and old['runLabel'] == previous_label and old['hostPlatform'] == 'Ios' and
                 old['hostSourceSha'] == checked['hostSourceSha'] and
                 old['hostArtifactSha256'] == checked['hostArtifactSha256'],
                 'Cannot prepare a new slot from a different source, app, role or run')
            closure = self.read('closed.txt', deadline)
            need(closure is not None, 'Prior runtime closure is missing')
            protocol.Protocol(old, parsed['hostAddress'], int(parsed['hostPort'])).closed(protocol.parse(closure))
            request = dict(schema='1', scope='mobile-usb-prepare-next', runLabel=previous_label,
                           nextRunLabel=checked['runLabel'], hostSourceSha=checked['hostSourceSha'],
                           hostArtifactSha256=checked['hostArtifactSha256'], inboxSha256=previous_inbox_sha256,
                           clientCount=checked['clientCount'])
            self.publish('next.txt', protocol.encode(request), deadline)
            expected = dict(schema='2', clientCount=checked['clientCount'], scope='ios-usb-slot',
                runLabel=checked['runLabel'], sourceSha=checked['hostSourceSha'], artifactSha256=checked['hostArtifactSha256'])
            while True:
                self.remaining(deadline)
                acknowledgement = self.read('next-ready.txt', deadline)
                if acknowledgement is not None:
                    need(protocol.parse(acknowledgement) == expected, 'Next iOS slot acknowledgement differs from the selected source/profile')
                    break
                time.sleep(min(.1, self.remaining(deadline)))
        finally:
            self.remote = original

    def inventory(self, deadline):
        value = self.command('slot-files', ['device', 'info', 'files', '--device', self.selected,
            '--domain-type', 'appDataContainer', '--domain-identifier', IOS_PACKAGE, '--subdirectory', self.remote], deadline)
        return file_inventory(value)

    def slot_present(self, deadline):
        """Observe named child directories from an existing Library; never infer missing-directory exit codes."""
        parent = 'Library'
        for name in ('Application Support', 'rpc-capacity', self.remote.rsplit('/', 1)[1]):
            value = self.command('slot-parent', ['device', 'info', 'files', '--device', self.selected,
                '--domain-type', 'appDataContainer', '--domain-identifier', IOS_PACKAGE, '--subdirectory', parent], deadline)
            rows = value['result'].get('files')
            need(type(rows) is list and len(rows) <= 4096 and
                 all(type(row) is dict and type(row.get('name')) is str for row in rows),
                 'Invalid selected app directory inventory')
            matches = [row for row in rows if row['name'] == name]
            if not matches:
                return False
            need(len(matches) == 1, 'Selected app control directory is ambiguous')
            properties = file_properties(matches[0])
            need(properties.get('isDirectory') is True and properties.get('isSymbolicLink') is False,
                 'Selected app control directory is linked, ambiguous or not a directory')
            parent += '/' + name
        return True

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
