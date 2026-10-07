#!/usr/bin/env python3
"""Explicit clean-source ARM64 scoped TCP/Bonjour JNI producer; no network, dependencies, or system mutation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import zipfile


def run(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jdk', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    assert not run(['git', 'status', '--porcelain', '--untracked-files=all'], root), 'Clean source required'
    source = run(['git', 'rev-parse', 'HEAD'], root)
    tree = run(['git', 'rev-parse', 'HEAD^{tree}'], root)
    output = args.output.absolute()
    assert output == output.resolve(strict=False), 'No symlink staging path'
    if output.exists():
        # Gradle precreates declared output directories. Only its still-empty directory may be retired.
        assert output.is_dir() and not output.is_symlink() and output.stat().st_uid == os.getuid()
        output.rmdir()  # Fails on any prior artifact/evidence; never recursive.

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.macos-tcp-', dir=output.parent))
    os.chmod(stage, 0o700)
    # Retain failed staging directories for diagnosis, never overwrite a previous producer.
    native = root / 'library/p2p-transport-lan/src/nativeInterop/macosJvm'
    clang = run(['/usr/bin/xcrun', '--find', 'clang'])
    library = stage / 'libp2pkit_lan_socket.dylib'
    command = [clang, '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wpedantic', '-O2', '-fvisibility=hidden',
               '-arch', 'arm64', '-dynamiclib', '-pthread', '-Wl,-install_name,@rpath/libp2pkit_lan_socket.dylib',
               '-I' + str(args.jdk / 'include'), '-I' + str(args.jdk / 'include/darwin'),
               '-DP2P_LAN_BUILD_SOURCE="' + source + '"', '-DP2P_LAN_BUILD_TREE="' + tree + '"',
               str(native / 'p2pkit_lan_socket.c'), str(native / 'p2pkit_lan_jni.c'),
               str(native / 'p2pkit_bonjour.c'), str(native / 'p2pkit_bonjour_jni.c'), '-o', str(library)]
    subprocess.run(command, check=True)
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', str(library)], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(library)], check=True)
    dependencies = run(['/usr/bin/otool', '-L', str(library)])
    deps = [line.strip().split(' (')[0] for line in dependencies.splitlines()[1:]]
    assert deps == ['@rpath/libp2pkit_lan_socket.dylib', '/usr/lib/libSystem.B.dylib'], deps
    values = dict(abi='1', platform='macos', arch='arm64', source=source, tree=tree, file=library.name,
                  bytes=str(library.stat().st_size), sha256=hashlib.sha256(library.read_bytes()).hexdigest())
    manifest = ''.join(f'{key}={value}\n' for key, value in values.items()).encode('ascii')
    (stage / 'macos-tcp.properties').write_bytes(manifest)
    with zipfile.ZipFile(stage / 'p2pkit-macos-tcp-manifest.jar', 'x', compression=zipfile.ZIP_STORED) as jar:
        info = zipfile.ZipInfo('META-INF/p2pkit/macos-tcp.properties', (1980, 1, 1, 0, 0, 0))
        jar.writestr(info, manifest)
    (stage / 'producer.json').write_text(json.dumps(dict(source=source, tree=tree, command=command,
        dependencies=deps, compiler=run([clang, '--version']), sdk=run(['/usr/bin/xcrun', '--show-sdk-version']),
        signing='local-ad-hoc-not-distribution-notarization', manifest=values), indent=2)+'\n')
    assert run(['git', 'rev-parse', 'HEAD'], root) == source
    assert not run(['git', 'status', '--porcelain', '--untracked-files=all'], root)
    for file in stage.iterdir():
        os.chmod(file, 0o500 if file == library else 0o400)
    os.rename(stage, output)
    print(json.dumps(dict(source=source, tree=tree, output=str(output), sha256=values['sha256'])))


if __name__ == '__main__':
    main()
