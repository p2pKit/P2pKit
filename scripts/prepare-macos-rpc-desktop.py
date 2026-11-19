#!/usr/bin/env python3
"""Create-only local Desktop package with exact classpath/native source and hash verification; never starts RPC."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

NATIVE_MANIFEST_JAR = 'p2pkit-macos-tcp-manifest.jar'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_classpath_entries(directory, entries, native):
    """Verify every distribution row; keep only the original native manifest at native/."""
    assert isinstance(entries, list) and 1 <= len(entries) <= 128
    retained, seen = [], set()
    for entry in entries:
        name = entry['name']
        assert Path(name).name == name and name.endswith('.jar') and name not in seen
        seen.add(name)
        original = directory / name
        assert original.is_file() and not original.is_symlink() and sha(original) == entry['sha256']
        if name == NATIVE_MANIFEST_JAR:
            authority = native / name
            assert authority.is_file() and not authority.is_symlink() and sha(authority) == entry['sha256']
            # MacLanNativeLoader requires one trusted resource, even if two copies have identical bytes.
            continue
        retained.append(entry)
    return retained


def launcher_source(manifest_digest, source, java, java_digest):
    """The reviewed launch script, not a mutable adjacent manifest, pins launch authority."""
    constants = repr((manifest_digest, source, java, java_digest))
    return "#!/usr/bin/env python3\nEXPECTED = " + constants + "\n" + r'''import argparse, hashlib, json, os, pathlib, subprocess, tempfile
parser = argparse.ArgumentParser(description='Open the source-matched RPC test app.')
parser.add_argument('--new-test-profile', action='store_true', help='Create a separate private test profile.')
args = parser.parse_args()
base = pathlib.Path(__file__).resolve().parent
manifest = base / 'manifest.json'
assert not manifest.is_symlink() and manifest.is_file()
raw = manifest.read_bytes()
assert len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == EXPECTED[0]
m = json.loads(raw)
assert m['schema'] == 1 and m['sourceSha'] == EXPECTED[1]
assert m['scope'] == 'LOCAL_APPLICATION_BUILD_NOT_NETWORK_OR_RELEASE_QUALIFICATION'
assert m['java'] == EXPECTED[2]
java = pathlib.Path(EXPECTED[2])
assert java.is_absolute() and java.is_file() and not java.is_symlink()
assert java.resolve(strict=True) == java and hashlib.sha256(java.read_bytes()).hexdigest() == EXPECTED[3]
assert isinstance(m['entries'], list) and 1 <= len(m['entries']) <= 128
paths = []
seen = set()
for entry in m['entries']:
    name = entry['name']
    assert isinstance(name, str) and name not in seen
    assert name == 'native/p2pkit-macos-tcp-manifest.jar' or (pathlib.Path(name).name == name and name.endswith('.jar'))
    seen.add(name)
    path = base / name
    assert path.is_file() and not path.is_symlink() and path.resolve(strict=True).is_relative_to(base)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    paths.append(str(path))
assert 'native/p2pkit-macos-tcp-manifest.jar' in seen
assert m['native']['file'] == 'libp2pkit_lan_socket.dylib' and m['native']['source'] == EXPECTED[1]
assert m['native']['arch'] == 'arm64' and m['native']['abi'] == '1'
native = base / 'native' / m['native']['file']
assert not native.is_symlink() and native.resolve(strict=True).is_relative_to(base)
assert hashlib.sha256(native.read_bytes()).hexdigest() == m['native']['sha256']
subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(native)], check=True)
env = dict(os.environ)
for key in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'CLASSPATH'):
    env.pop(key, None)
jvm_options = []
if args.new_test_profile:
    profile_home = pathlib.Path.home().resolve(strict=True)
    profile = pathlib.Path(tempfile.mkdtemp(prefix='.p2pkit-rpc-test-', dir=profile_home))
    assert profile.is_dir() and not profile.is_symlink() and profile.stat().st_uid == os.getuid()
    assert profile.stat().st_mode & 0o777 == 0o700
    jvm_options.append('-Ddev.p2pkit.rpc.profileDir=' + str(profile))
    print('New private test profile. Choose a new passphrase in the RPC app.', flush=True)
os.execve(str(java), [str(java), *jvm_options, '-Ddev.p2pkit.lan.macos.nativeDir=' + str(base / 'native'),
    '-cp', os.pathsep.join(paths), 'dev.p2pkit.sample.rpc.desktop.RpcDesktopMainKt'], env)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'jars', 'native', 'output', 'java'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()
    jars = json.loads((args.jars / 'manifest.json').read_text())
    assert jars['sourceSha'] == source
    native = dict(line.split('=', 1) for line in (args.native / 'macos-tcp.properties').read_text().splitlines())
    assert native['source'] == source and native['abi'] == '1' and native['arch'] == 'arm64'
    assert args.output.is_absolute() and args.output == args.output.resolve(strict=False)
    if args.output.exists():
        assert args.output.is_dir() and not args.output.is_symlink() and args.output.stat().st_uid == os.getuid()
        args.output.rmdir()  # Only an empty Gradle-created output directory; no artifact is overwritten.
    args.output.mkdir(mode=0o700, parents=True)
    stage = args.output / 'native'; stage.mkdir(mode=0o700)
    entries = []
    for entry in checked_classpath_entries(args.jars, jars['entries'], args.native):
        name = entry['name']; assert Path(name).name == name and name.endswith('.jar')
        original = args.jars / name
        assert not original.is_symlink() and sha(original) == entry['sha256']
        destination = args.output / name; shutil.copyfile(original, destination); destination.chmod(0o400)
        assert sha(destination) == entry['sha256']
        entries.append(dict(name=name, sha256=entry['sha256']))
    for name in ['libp2pkit_lan_socket.dylib', 'macos-tcp.properties', 'p2pkit-macos-tcp-manifest.jar']:
        original = args.native / name; assert not original.is_symlink()
        target = stage / name; shutil.copyfile(original, target); target.chmod(0o500 if name.endswith('.dylib') else 0o400)
        assert sha(original) == sha(target)
    assert sha(stage / native['file']) == native['sha256']
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(stage / native['file'])], check=True)
    entries.append(dict(name='native/p2pkit-macos-tcp-manifest.jar',
                        sha256=sha(stage / 'p2pkit-macos-tcp-manifest.jar')))
    result = dict(schema=1, sourceSha=source, scope='LOCAL_APPLICATION_BUILD_NOT_NETWORK_OR_RELEASE_QUALIFICATION',
                  entries=entries, native=native, java=str(args.java.resolve(strict=True)))
    (args.output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest_digest = sha(args.output / 'manifest.json')
    launcher = launcher_source(manifest_digest, source, result['java'], sha(Path(result['java'])))
    (args.output / 'run-desktop.py').write_text(launcher)
    (args.output / 'run-desktop.py').chmod(0o500)
    (args.output / 'manifest.json').chmod(0o400)
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == source
    print(json.dumps(dict(source=source, output=str(args.output), manifestSha256=sha(args.output / 'manifest.json'))))


if __name__ == '__main__':
    main()
