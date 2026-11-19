#!/usr/bin/env python3
"""Retire only a verified read-only lab copy before Gradle Sync; never alter the native producer."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capacity_copy_files', ROOT / 'scripts/run-rpc-capacity-lab.py')
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


def prepare(root):
    directory = root / 'samples/p2p-sample-rpc/build/capacity-lab'
    target = directory / files.MAC_MANIFEST_JAR
    if not target.exists() and not target.is_symlink():
        return
    for parent in (directory, *directory.parents):
        info = parent.lstat()
        files.need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and
                   not stat.S_IMODE(info.st_mode) & 0o022, 'Unprotected lab copy ancestry')
    before = target.lstat()
    raw = files.read_distribution_file(target, 65536, private=True)
    if stat.S_IMODE(before.st_mode) & 0o200:
        return  # New Sync copies are owner-writable; no retirement is needed.
    manifest = files.json.loads(files.read_distribution_file(directory / 'manifest.json', files.LIMIT, private=True),
                               object_pairs_hook=files.unique)
    files.need(type(manifest) is dict and type(manifest.get('schema')) is int and manifest['schema'] == 1 and
               manifest.get('scope') == 'SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION' and
               type(manifest.get('sourceSha')) is str and re.fullmatch('[0-9a-f]{40}', manifest['sourceSha']),
               'Read-only copy requires its original distribution provenance')
    native = manifest.get('macosNative')
    relative = 'library/p2p-transport-lan/build/macos-tcp/' + manifest['sourceSha']
    files.need(type(native) is dict and native.get('directory') == relative,
               'Read-only copy requires the fixed original native producer')
    binding = dict(name=files.MAC_MANIFEST_JAR, sha256=hashlib.sha256(raw).hexdigest())
    for entries in (manifest.get('entries'), native.get('entries')):
        files.need(type(entries) is list and
                   [entry for entry in entries if type(entry) is dict and entry.get('name') == binding['name']] ==
                   [binding], 'Read-only copy differs from its original recorded hash')
    original = root / relative / files.MAC_MANIFEST_JAR
    for parent in (original.parent, *original.parent.parents):
        info = parent.lstat()
        files.need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and
                   not stat.S_IMODE(info.st_mode) & 0o022, 'Unprotected original producer ancestry')
    files.need(files.read_distribution_file(original, 65536, private=True) == raw,
               'Read-only copy differs from its retained native producer')
    after = target.lstat()
    files.need((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode, after.st_uid,
                after.st_nlink) == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode,
                                   before.st_uid, before.st_nlink), 'Read-only copy changed before retirement')
    target.unlink()  # Exactly this verified owned copy; no chmod, recursive deletion or original mutation.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root.resolve(strict=True))
