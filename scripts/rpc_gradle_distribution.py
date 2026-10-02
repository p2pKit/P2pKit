#!/usr/bin/env python3
"""Data-only, SHA-256-pinned wrapper input for a NEW private local qualification.

No download, archive extraction, executable, cache restoration or native receipt.
The unchanged real wrapper must still verify/extract its ZIP and pass --stop
inside the original 120-second finalizer. Never adopt a failed run's home.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat

MAX_ARCHIVE = 256 * 1024 * 1024
CHUNK = 1024 * 1024
SCOPE = 'VERIFIED_DISTRIBUTION_DATA_ONLY_NOT_NATIVE_ADMISSION'


def need(condition, message='Unadmitted Gradle distribution input'):
    if not condition:
        raise RuntimeError(message)


def physical(path):
    need(path.is_absolute() and path == Path(os.path.normpath(path)), 'Absolute physical path required')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlinked distribution path refused')


def private_directory(path):
    physical(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
         'Private owned distribution directory required')


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def transfer(source, maximum, destination=None, private=True):
    """Read exact owned regular bytes, optionally into one create-only private file.

    Failed partial copies remain evidence; callers must not consume them without
    the complete pin check. No remove, rename, overwrite or speculative retry.
    """
    physical(source)
    before = source.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
         0 < before.st_size <= maximum and not before.st_mode & (stat.S_ISUID | stat.S_ISGID) and
         (not private or stat.S_IMODE(before.st_mode) == 0o600), 'Unsafe or unbounded distribution file')
    if destination is not None:
        private_directory(destination.parent)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    output = None
    raw, size, digest = [], 0, hashlib.sha256()
    try:
        need(identity(os.fstat(fd)) == identity(before), 'Distribution file changed at open')
        if destination is not None:
            output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        while True:
            block = os.read(fd, min(CHUNK, maximum + 1 - size))
            if not block:
                break
            size += len(block)
            need(size <= maximum, 'Distribution file grew beyond its bound')
            digest.update(block)
            if output is not None:
                offset = 0
                while offset < len(block):
                    written = os.write(output, block[offset:])
                    need(written > 0, 'Distribution copy stopped making progress')
                    offset += written
            elif not private:
                raw.append(block)  # Only the separately bounded wrapper properties.
        need(size == before.st_size and identity(os.fstat(fd)) == identity(before) and
             identity(source.lstat()) == identity(before), 'Distribution file changed during read')
        if output is not None:
            os.fsync(output)
            actual = os.fstat(output)
            need(stat.S_ISREG(actual.st_mode) and actual.st_uid == os.getuid() and actual.st_nlink == 1 and
                 actual.st_size == size and stat.S_IMODE(actual.st_mode) == 0o600 and
                 identity(destination.lstat()) == identity(actual), 'Distribution copy changed identity')
    finally:
        try:
            if output is not None:
                os.close(output)
        finally:
            os.close(fd)
    return dict(bytes=size, sha256=digest.hexdigest(), raw=b''.join(raw))


def wrapper_policy(root):
    data = transfer(root / 'gradle/wrapper/gradle-wrapper.properties', 16 * 1024, private=False)
    values = {}
    for line in data['raw'].decode('ascii').splitlines():
        if not line:
            continue
        key, separator, value = line.partition('=')
        need(separator and key not in values, 'Malformed or duplicate wrapper property')
        values[key] = value
    fixed = dict(distributionBase='GRADLE_USER_HOME', distributionPath='wrapper/dists',
                 zipStoreBase='GRADLE_USER_HOME', zipStorePath='wrapper/dists',
                 networkTimeout='10000', validateDistributionUrl='true')
    need(set(values) == {*fixed, 'distributionUrl', 'distributionSha256Sum'} and
         all(values[k] == v for k, v in fixed.items()), 'Unreviewed wrapper storage or validation policy')
    match = re.fullmatch(r'https\\://services\.gradle\.org/distributions/(gradle-[0-9]+\.[0-9]+(?:\.[0-9]+)?-bin)\.zip',
                         values['distributionUrl'])
    need(match and re.fullmatch('[a-f0-9]{64}', values['distributionSha256Sum']), 'Exact HTTPS URL and SHA-256 required')
    url, base = values['distributionUrl'].replace('\\:', ':'), match[1]
    # Gradle PathAssembler's URL-MD5/base36 is only a storage key. SHA-256 above
    # authenticates the bytes; MD5 is never used as an integrity decision.
    number = int.from_bytes(hashlib.md5(url.encode('ascii'), usedforsecurity=False).digest(), 'big')
    alphabet, key = '0123456789abcdefghijklmnopqrstuvwxyz', ''
    while number:
        number, digit = divmod(number, 36)
        key = alphabet[digit] + key
    return dict(url=url, sha256=values['distributionSha256Sum'], filename=base + '.zip',
                zipRelative=f'wrapper/dists/{base}/{key or "0"}/{base}.zip', propertiesSha256=data['sha256'])


def prepare_archive(root, source, parent):
    private_directory(parent)
    policy = wrapper_policy(root)
    archive = parent / policy['filename']
    observed = transfer(source, MAX_ARCHIVE, archive)
    need(observed['sha256'] == policy['sha256'], 'Distribution SHA-256 mismatch; failed bytes retained')
    need(transfer(archive, MAX_ARCHIVE) == observed, 'Prepared copy readback differs; failed bytes retained')
    return dict(schema=1, scope=SCOPE, archive=archive.name, bytes=observed['bytes'], sha256=observed['sha256'], policy=policy)


def admit_archive(root, parent, record):
    private_directory(parent)
    policy = wrapper_policy(root)
    need(type(record) is dict and set(record) == {'schema', 'scope', 'archive', 'bytes', 'sha256', 'policy'} and
         type(record['schema']) is int and record['schema'] == 1 and record['scope'] == SCOPE and
         record['archive'] == policy['filename'] and record['policy'] == policy and
         type(record['bytes']) is int and 0 < record['bytes'] <= MAX_ARCHIVE and record['sha256'] == policy['sha256'],
         'Prepared distribution is not the current exact input')
    archive = parent / policy['filename']
    observed = transfer(archive, MAX_ARCHIVE)
    need((observed['bytes'], observed['sha256']) == (record['bytes'], record['sha256']), 'Prepared distribution changed')
    return archive


def stage_archive(root, parent, record, state, context):
    source = admit_archive(root, parent, record)
    need(state == parent / 'state' and context['root'] == str(root) and
         context['gradleHome'] == str(state / 'gradle-home'), 'Only the new context-bound home is admitted')
    home = state / 'gradle-home'
    private_directory(state)
    private_directory(home)
    need({p.name for p in home.iterdir()} == {'gradle.properties'}, 'Existing wrapper/cache state must not be reused')
    properties = transfer(home / 'gradle.properties', 1024 * 1024)
    need(properties['sha256'] == context['gradlePropertiesSha256'], 'Admitted Gradle-home policy changed')
    target = home / record['policy']['zipRelative']
    directory = home
    for part in target.relative_to(home).parts[:-1]:
        directory /= part
        directory.mkdir(mode=0o700)  # Create-only all the way down; no existing cache adoption.
    observed = transfer(source, MAX_ARCHIVE, target)
    need((observed['bytes'], observed['sha256']) == (record['bytes'], record['sha256']), 'Staged distribution changed')
    need(transfer(target, MAX_ARCHIVE) == observed, 'Staged copy readback differs; failed bytes retained')
    need(wrapper_policy(root) == record['policy'], 'Wrapper policy changed during staging')
    return dict(scope=SCOPE, bytes=observed['bytes'], sha256=observed['sha256'],
                zipRelative=record['policy']['zipRelative'], extracted=False, nativeAdmission=False,
                restoredCaches=False, finalizerTimeoutSeconds=120)
