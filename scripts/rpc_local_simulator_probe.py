"""Installed-tool architecture proof for the supplemental local ARM probe only.

No tool is launched here. The caller must bind a fresh private device set, retain
the original deadlines, and use the unchanged native owner and exact simulator
finalizer. This is not an alternative Apple qualification or ownership policy.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import struct

IDENTIFIER = r'[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}'
MAX_TOOL = 64 * 1024 * 1024
MAX_COMMANDS = 256 * 1024


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def runtime_tool(runtime, selected):
    """Bind the actual runtime's thin ARM64/iOS-simulator launchctl, not the host's.

    simctl spawn interprets absolute executable paths from the HOST root. The
    runtimeRoot prefix is consequently essential. Never assume a Unix utility such
    as uname exists in the guest or execute a similarly named host binary instead.
    """
    need(type(selected) is str and
         re.fullmatch(r'com\.apple\.CoreSimulator\.SimRuntime\.iOS-[0-9-]{1,16}', selected),
         'Exact selected iOS runtime required')
    need(type(runtime) is dict and runtime.get('identifier') == selected and
         runtime.get('isAvailable') is True and runtime.get('supportedArchitectures') == ['arm64'],
         'This supplemental probe requires an available ARM64-only runtime')
    root = runtime.get('runtimeRoot')
    need(type(root) is str and root and '\0' not in root, 'Actual runtime root required')
    path = Path(root) / 'bin/launchctl'
    need(path.is_absolute() and str(Path(root)) == root and path.resolve(strict=True) == path,
         'Physical absolute runtime tool required')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_mode & 0o111 and
             not before.st_mode & (stat.S_ISUID | stat.S_ISGID) and 32 <= before.st_size <= MAX_TOOL,
             'Bounded ordinary runtime executable required')
        header = stream.read(32)
        need(len(header) == 32, 'Truncated Mach-O header')
        magic, cpu, _, kind, count, size, _, reserved = struct.unpack('<8I', header)
        need(magic == 0xfeedfacf and cpu == 0x0100000c and kind == 2 and reserved == 0,
             'Thin ARM64 Mach-O executable required; no host or universal fallback')
        need(0 < count <= 1024 and 8 * count <= size <= MAX_COMMANDS and size <= before.st_size - 32,
             'Bounded Mach-O load commands required')
        commands = stream.read(size)
        need(len(commands) == size, 'Truncated Mach-O load commands')
        offset, platforms = 0, []
        for _ in range(count):
            need(offset + 8 <= size, 'Truncated Mach-O command')
            command, length = struct.unpack_from('<II', commands, offset)
            need(length >= 8 and length % 8 == 0 and offset + length <= size, 'Malformed Mach-O command')
            if command == 0x32:  # LC_BUILD_VERSION; platform 7 is PLATFORM_IOSSIMULATOR.
                need(length >= 24, 'Truncated Mach-O build version')
                platform, _, _, tools = struct.unpack_from('<4I', commands, offset + 8)
                need(length == 24 + 8 * tools, 'Malformed Mach-O build tools')
                platforms.append(platform)
            offset += length
        need(offset == size and platforms == [7], 'Exact iOS-simulator platform required')
        digest = hashlib.sha256(header + commands)
        remaining = before.st_size - 32 - size
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            need(bool(chunk), 'Runtime tool changed or truncated during binding')
            digest.update(chunk)
            remaining -= len(chunk)
        need(not stream.read(1), 'Runtime tool grew during binding')
        after = os.fstat(stream.fileno())
        signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        need(signature(before) == signature(after), 'Runtime tool changed during binding')
    return dict(runtime=selected, executable=str(path), sha256=digest.hexdigest(),
                architecture='arm64', platform='IOSSIMULATOR')


def probe_commands(device_set, simulator, tool):
    need(type(simulator) is str and re.fullmatch(IDENTIFIER, simulator), 'Exact fresh simulator ID required')
    need(isinstance(device_set, Path) and device_set.is_absolute() and
         device_set.resolve(strict=True) == device_set and device_set.is_dir(), 'Physical private device set required')
    need(type(tool) is dict and tool.get('architecture') == 'arm64' and tool.get('platform') == 'IOSSIMULATOR' and
         type(tool.get('executable')) is str and Path(tool['executable']).is_absolute() and
         type(tool.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', tool['sha256']),
         'Bound runtime executable required')
    command = ['/usr/bin/xcrun', 'simctl', '--set', str(device_set)]
    # Both operations select native ARM explicitly. manageruid is a read-only
    # query, not a service mutation; the exact runtime binary supplies the
    # independently inspected CPU/platform evidence, not its printed UID.
    return dict(boot=command + ['boot', simulator, '--arch=arm64'],
                architecture=command + ['spawn', '--arch=arm64', simulator, tool['executable'], 'manageruid'])


def verify_probe_output(raw, uid):
    need(type(uid) is int and uid > 0, 'Original nonroot account required')
    need(type(raw) is bytes and raw == (str(uid) + '\n').encode('ascii'),
         'Runtime launch manager must belong to the original nonroot account')
