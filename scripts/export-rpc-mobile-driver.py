#!/usr/bin/env python3
"""Deliver an already produced, source-bound JVM test driver after the complete Android handoff.

No build, installation, native process or device execution occurs here. A
separate test artifact, never Maven/release publication or mobile qualification.
All six original receipts, ten real app controls and APK bytes remain required.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_capacity_evidence as evidence

SCOPE = 'SOURCE_BOUND_JVM_TEST_DRIVER_NOT_MOBILE_EXECUTION_CAPACITY_OR_RELEASE'
LIMIT = 256 * 1024 * 1024


def need(value):
    if not value:
        raise ValueError('Driver handoff requires complete unchanged source/native/app/distribution evidence')


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def regular_bytes(path, limit):
    need(path.is_absolute() and all(not item.is_symlink() for item in (path, *path.parents)))
    def identity(value):
        return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_nlink,
                value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
         stat.S_IMODE(before.st_mode) & 0o022 == 0 and 0 < before.st_size <= limit)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        opened = os.fstat(source.fileno())
        need(identity(opened) == identity(before))
        raw = source.read(limit + 1)
        after = os.fstat(source.fileno())
        need(len(raw) == opened.st_size and identity(after) == identity(opened) == identity(path.lstat()))
    return raw


def inventory(directory, source):
    need(directory.is_dir() and not directory.is_symlink())
    raw = regular_bytes(directory / 'manifest.json', 262144)
    manifest = json.loads(raw, object_pairs_hook=evidence.unique)
    need(type(manifest) is dict and set(manifest) == {'schema', 'scope', 'sourceSha', 'entries'} and
         type(manifest['schema']) is int and manifest['schema'] == 1 and manifest['sourceSha'] == source and
         manifest['scope'] == 'SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION' and
         type(manifest['entries']) is list and 1 <= len(manifest['entries']) <= 128)
    names, total, files = [], len(raw), {'manifest.json': raw}
    for item in manifest['entries']:
        need(type(item) is dict and set(item) == {'name', 'sha256'} and type(item['name']) is str and
             re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,191}\.jar', item['name']) and
             type(item['sha256']) is str and re.fullmatch('[a-f0-9]{64}', item['sha256']))
        names.append(item['name'])
        data = regular_bytes(directory / item['name'], LIMIT)
        total += len(data)
        need(total <= LIMIT and hashlib.sha256(data).hexdigest() == item['sha256'])
        files[item['name']] = data
    need(names == sorted(set(names)) and {p.name for p in directory.iterdir()} == {'manifest.json', *names})
    return files


def export(directory, parent, source, app_manifest, producer_hash, unchanged):
    """Fresh private staging; a failed copy/hash/source check exposes no distribution."""
    before = inventory(directory, source['commit'])
    staging, public = parent / 'runtime-export-staging', parent / 'runtime-public'
    need(not staging.exists() and not staging.is_symlink() and not public.exists() and not public.is_symlink())
    staging.mkdir(mode=0o700)
    archive = staging / 'p2pkit-rpc-jvm-capacity-driver.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_STORED) as output:
        for name, raw in before.items():
            output.writestr(name, raw)
    os.chmod(archive, 0o600)
    with archive.open('rb') as stream:
        os.fsync(stream.fileno())
    with zipfile.ZipFile(archive) as check:
        need(check.namelist() == list(before) and check.testzip() is None)
        need(all(check.read(name) == raw for name, raw in before.items()))
    need(inventory(directory, source['commit']) == before and unchanged())
    data = regular_bytes(archive, LIMIT + 262144)
    result = dict(schema=1, scope=SCOPE, source=source, foundationStatus='NOT_READY',
        status='PREPARED_DRIVER_NOT_MOBILE_RUNTIME_QUALIFICATION', mobileCapacityQualified=False,
        physicalLanQualified=False, originalAndroidHandoffSha256=hashlib.sha256(app_manifest).hexdigest(),
        producerReceiptSha256=producer_hash, distributionManifestSha256=hashlib.sha256(before['manifest.json']).hexdigest(),
        jarCount=len(before) - 1, artifact=dict(file=archive.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()),
        entries={name: dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) for name, raw in before.items()})
    with (staging / 'manifest.json').open('x') as stream:
        os.chmod(staging / 'manifest.json', 0o600)
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    need(unchanged())
    staging.rename(public)
    return result


def main():
    os.umask(0o077)
    h = load('mobile_driver_handoff', 'run-rpc-android-handoff.py')
    h.admit(os.environ)
    runner = load('mobile_driver_native', 'run-audit-command.py')
    checker = load('mobile_driver_receipts', 'check-audit-receipt.py')
    policy = load('mobile_driver_inventory', 'run-rpc-qualification.py')
    phone = load('mobile_driver_app_controls', 'run-rpc-android-controls.py')
    lab = load('mobile_driver_files', 'run-rpc-capacity-lab.py')
    parent = runner.absolute_path(os.environ['RPC_ANDROID_HANDOFF_PARENT'])
    lab.private_directory(parent)
    need(parent.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve(strict=True)))
    state, context = runner.context_at(str(parent / 'state'))
    need(runner.source_snapshot(ROOT) == context['source'])
    public_raw = regular_bytes(parent / 'public/manifest.json', 262144)
    public = json.loads(public_raw, object_pairs_hook=evidence.unique)
    source = {k: context['source'][k] for k in ('commit', 'tree')}
    count = policy.control_inventory('linux-x64')
    h.validate_public(public, source, count)
    need(public['result'] == 'PASS')
    original = runner.read_json(state / 'private/result.json')
    need(original['source'] == context['source'] and original['result'] == 'PASS' and
         original['sourceUnchanged'] is True and original['nativeControlTests'] == count and
         len(original['commands']) == len(h.PURPOSES))
    for purpose, row in zip(h.PURPOSES, original['commands']):
        need(row['purpose'] == purpose and row['exitCode'] == 0 and row['verified'] is True)
        proof = h.receipt(runner, checker, state, context, purpose, row['argv'], 0)
        need(row['receiptSha256'] == runner.file_digest(state / 'private' / (purpose + '.json')))
        if purpose == 'native-controls':
            log = evidence.bounded(state / 'evidence' / proof['id'] / 'product.stderr.log')
            need(policy.unittest_count(log.decode()) == count)
    files = {name: h.apk_metadata(ROOT / relative, runner) for name, relative in h.APKS.items()}
    need(files == original['artifacts'] == public['artifacts'])
    for name in files:
        need(h.apk_metadata(parent / 'public' / name, runner) == files[name])
    values = list(files.values())
    producer_hash = runner.file_digest(state / 'private/android-apk-producer.json')
    controls = h.assess_controls(runner.read_json(state / 'work/api24-controls/result.json'), context,
        producer_hash, values[0]['sha256'], values[1]['sha256'], phone)
    need(controls == original['controls'] == public['controls'])
    lab.classpath(source['commit'])
    export(ROOT / 'samples/p2p-sample-rpc/build/capacity-lab', parent, source, public_raw, producer_hash,
           lambda: runner.source_snapshot(ROOT) == context['source'])
    print('SOURCE_BOUND_TEST_DRIVER_EXPORTED; no mobile, LAN or release qualification')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('MOBILE_DRIVER_HANDOFF_FAILED: ' + type(error).__name__ + '; no distribution export', file=sys.stderr)
        raise SystemExit(1)
