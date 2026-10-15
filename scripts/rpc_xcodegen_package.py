"""Bind and privately stage an already installed XcodeGen package, without executing it.

The binary alone is not the tool: XcodeGen resolves SettingPresets relative to
its install prefix. Missing presets can still yield exit 0 and an unusable
Xcode project. Preserve that layout, hash every input, and verify the copy.
No download, installation, extraction, overwrite or automatic cleanup occurs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

SCOPE = 'INSTALLED_XCODEGEN_PACKAGE_INPUT_NOT_NATIVE_ADMISSION'
PRESETS = Path('share/xcodegen/SettingPresets')
REQUIRED_PRESETS = ('base.yml', 'Configs/debug.yml', 'Configs/release.yml', 'Platforms/iOS.yml',
                    'Products/bundle.unit-test.yml', 'Products/bundle.ui-testing.yml',
                    'Product_Platform/application_iOS.yml')
PRESET_DIRECTORIES = frozenset(('Configs', 'Platforms', 'Products', 'Product_Platform', 'SupportedDestinations'))
MAX_PRESET_BYTES = 64 * 1024
MAX_BINARY_BYTES = 128 * 1024 * 1024


def need(condition, message='Invalid installed XcodeGen package'):
    if not condition:
        raise RuntimeError(message)


def physical(path):
    need(path.is_absolute() and path == Path(os.path.normpath(path)), 'Absolute normalized package path required')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlinked package path refused')


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def measure(path, executable, consume=None):
    physical(path)
    before = path.lstat()
    limit = MAX_BINARY_BYTES if executable else MAX_PRESET_BYTES
    need(stat.S_ISREG(before.st_mode) and before.st_uid in (0, os.getuid()) and before.st_nlink == 1 and
         not before.st_mode & (stat.S_ISUID | stat.S_ISGID | 0o022) and
         bool(before.st_mode & 0o111) is executable and 0 < before.st_size <= limit,
         'Package input must be bounded, regular, single-linked and non-writable by other accounts')
    digest, size = hashlib.sha256(), 0
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as source:
        need(identity(os.fstat(source.fileno())) == identity(before), 'Package input changed before opening')
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            need(size <= limit, 'Package input exceeded its bound')
            digest.update(chunk)
            if consume is not None:
                consume(chunk)
        need(identity(os.fstat(source.fileno())) == identity(before) == identity(path.lstat()) and
             size == before.st_size, 'Package input changed during observation')
    return dict(bytes=size, sha256=digest.hexdigest())


def inventory(binary):
    physical(binary)
    need(binary.name == 'xcodegen' and binary.parent.name == 'bin', 'Installed bin/xcodegen layout required')
    prefix = binary.parent.parent
    directory = prefix / PRESETS
    physical(directory)
    need(directory.is_dir(), 'Installed SettingPresets directory is missing')
    resources = []
    for folder, directories, names in os.walk(directory, followlinks=False):
        folder = Path(folder)
        physical(folder)
        info = folder.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and not info.st_mode & 0o022,
             'Untrusted package resource directory')
        relative = folder.relative_to(directory)
        need(relative == Path('.') or len(relative.parts) == 1 and relative.name in PRESET_DIRECTORIES,
             'Unexpected package resource directory')
        need(not directories or relative == Path('.') and set(directories) <= PRESET_DIRECTORIES,
             'Unexpected nested package resources')
        for name in directories:
            physical(folder / name)  # os.walk otherwise silently skips symlinked directories.
        for name in sorted(names):
            need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\.yml', name) and
                 (relative != Path('.') or name == 'base.yml'), 'Unexpected non-preset package file')
            path = folder / name
            resources.append(dict(path=str(path.relative_to(prefix)), **measure(path, False)))
            need(len(resources) <= 64, 'Too many package resources')
    need({str(PRESETS / name) for name in REQUIRED_PRESETS} <= {row['path'] for row in resources},
         'Required XcodeGen settings are missing')
    rows = [dict(path='bin/xcodegen', **measure(binary, True)), *resources]
    return dict(schema=1, scope=SCOPE, prefix=str(prefix), files=sorted(rows, key=lambda row: row['path']))


def admit(manifest):
    need(type(manifest) is dict and set(manifest) == {'schema', 'scope', 'prefix', 'files'} and
         type(manifest['schema']) is int and manifest['schema'] == 1 and manifest['scope'] == SCOPE and
         type(manifest['prefix']) is str and type(manifest['files']) is list, 'Invalid package manifest')
    need(1 <= len(manifest['files']) <= 65 and all(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and
         type(row['path']) is str and type(row['bytes']) is int and 0 < row['bytes'] <= MAX_BINARY_BYTES and
         type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}', row['sha256']) for row in manifest['files']),
         'Invalid package file record')
    prefix = Path(manifest['prefix'])
    need(inventory(prefix / 'bin/xcodegen') == manifest, 'Installed XcodeGen package changed after preparation')
    return prefix


def copy_verified(source, target, row):
    executable = row['path'] == 'bin/xcodegen'
    mode = 0o700 if executable else 0o600
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as output:
        def consume(chunk):
            need(output.write(chunk) == len(chunk), 'Incomplete package write')
        observed = measure(source, executable, consume)
        output.flush()
        os.fsync(output.fileno())
        need(stat.S_IMODE(os.fstat(output.fileno()).st_mode) == mode, 'Private package mode differs')
    need(observed == {k: row[k] for k in ('bytes', 'sha256')}, 'Package input changed during staging')


def stage(manifest, destination):
    prefix = admit(manifest)  # Complete reobservation before creating anything.
    physical(destination)
    parent = destination.parent.lstat()
    need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and not parent.st_mode & 0o077,
         'Private owned staging parent required')
    destination.mkdir(mode=0o700)
    for row in manifest['files']:
        relative = Path(row['path'])  # Already compared to the closed, physically observed inventory.
        target = destination / relative
        for directory in reversed(target.parent.parents):
            if directory.is_relative_to(destination) and directory != destination:
                directory.mkdir(mode=0o700, exist_ok=True)
        target.parent.mkdir(mode=0o700, exist_ok=True)
        copy_verified(prefix / relative, target, row)
    # Independent readback, not just a hash of bytes offered to write().
    copied = inventory(destination / 'bin/xcodegen')
    need(copied['files'] == manifest['files'], 'Staged XcodeGen package readback differs')
    return dict(executable=str(destination / 'bin/xcodegen'), resourceFiles=len(manifest['files']) - 1,
        packageSha256=hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        globalInstallation=False, restoredCaches=False)
