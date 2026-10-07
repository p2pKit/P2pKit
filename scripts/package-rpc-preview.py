#!/usr/bin/env python3
"""Package exact-source RPC app images, not release signing or network qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import zipfile


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def run(argv, cwd=None):
    return subprocess.check_output([str(x) for x in argv], cwd=cwd, text=True).strip()


def checked_entries(directory, source):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['sourceSha'] != source or not 1 <= len(manifest['entries']) <= 128:
        raise ValueError('Wrong source or unbounded classpath')
    names = set()
    for row in manifest['entries']:
        name = row['name']
        if name in names or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.jar', name):
            raise ValueError('Unsafe/duplicate classpath entry')
        names.add(name)
        file = directory / name
        if file.is_symlink() or not file.is_file() or digest(file) != row['sha256']:
            raise ValueError('Classpath integrity mismatch')
    return sorted(names)


def manifest_bytes(names):
    # JAR manifest physical lines must not exceed 72 bytes, including CRLF.
    lines = ['Manifest-Version: 1.0', 'Main-Class: dev.p2pkit.sample.rpc.desktop.RpcDesktopMainKt']
    value = ('Class-Path: ' + ' '.join(names)).encode('ascii')
    chunks = []
    while value:
        size = 70 if not chunks else 69
        chunks.append((b'' if not chunks else b' ') + value[:size])
        value = value[size:]
    return b'\r\n'.join([x.encode('ascii') for x in lines] + chunks) + b'\r\n\r\n'


def package(root, jdk):
    source = run(['git', 'rev-parse', 'HEAD'], root)
    tree = run(['git', 'rev-parse', 'HEAD^{tree}'], root)
    if run(['git', 'status', '--porcelain'], root):
        raise ValueError('Clean source required')
    system = platform.system()
    if system not in ('Darwin', 'Windows', 'Linux'):
        raise ValueError('Unsupported packaging OS')
    label = {'Darwin': 'macos-arm64', 'Windows': 'windows-x64-ui-preview', 'Linux': 'linux-x64'}[system]
    if system == 'Darwin' and platform.machine() != 'arm64':
        raise ValueError('The native macOS provider is ARM64 only')
    if system != 'Darwin' and platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('Unexpected runner architecture')
    out = root / 'build/rpc-app-delivery'
    out.mkdir(parents=True, exist_ok=True)
    work = root / 'build/rpc-app-packaging' / source / label
    work.mkdir(parents=True, exist_ok=False)
    inputs = work / 'input'
    inputs.mkdir()
    jars = root / 'samples/p2p-sample-rpc/build/capacity-lab'
    names = checked_entries(jars, source)
    for name in names:
        shutil.copy2(jars / name, inputs / name)
    options = []
    if system == 'Darwin':
        native = root / 'library/p2p-transport-lan/build/macos-tcp' / source
        receipt = json.loads((native / 'producer.json').read_text())
        values = receipt['manifest']
        if receipt['source'] != source or receipt['tree'] != tree or values['arch'] != 'arm64':
            raise ValueError('Wrong native provider provenance')
        library = native / 'libp2pkit_lan_socket.dylib'
        if digest(library) != values['sha256']:
            raise ValueError('Native provider changed')
        run(['/usr/bin/codesign', '--verify', '--strict', library])
        (inputs / 'native').mkdir()
        for name in ('libp2pkit_lan_socket.dylib', 'p2pkit-macos-tcp-manifest.jar'):
            shutil.copy2(native / name, inputs / 'native' / name)
        expected = ''.join(f'{key}={value}\n' for key, value in values.items()).encode('ascii')
        with zipfile.ZipFile(inputs / 'native/p2pkit-macos-tcp-manifest.jar') as metadata:
            if metadata.namelist() != ['META-INF/p2pkit/macos-tcp.properties'] or metadata.read(
                    'META-INF/p2pkit/macos-tcp.properties') != expected:
                raise ValueError('Native manifest differs from verified producer')
        names.append('native/p2pkit-macos-tcp-manifest.jar')
        options = ['--java-options', '-Ddev.p2pkit.lan.macos.nativeDir=$APPDIR/native']
    with zipfile.ZipFile(inputs / 'rpc-launcher.jar', 'x') as jar:
        jar.writestr('META-INF/MANIFEST.MF', manifest_bytes(names))
    tool = jdk / 'bin' / ('jpackage.exe' if system == 'Windows' else 'jpackage')
    argv = [tool, '--type', 'app-image', '--name', 'P2pKit-RPC', '--app-version', '1.0.0',
            '--input', inputs, '--main-jar', 'rpc-launcher.jar', '--dest', work / 'image',
            '--vendor', 'P2pKit', '--description', 'Local RPC developer preview',
            '--add-modules', 'java.se,jdk.crypto.ec,jdk.unsupported,jdk.charsets,jdk.crypto.cryptoki', *options]
    subprocess.run([str(x) for x in argv], check=True)
    app = work / 'image' / ('P2pKit-RPC.app' if system == 'Darwin' else 'P2pKit-RPC')
    launcher = app / {'Darwin': 'Contents/MacOS/P2pKit-RPC', 'Windows': 'P2pKit-RPC.exe',
                      'Linux': 'bin/P2pKit-RPC'}[system]
    if not launcher.is_file():
        raise ValueError('Missing native launcher')
    if system == 'Darwin':
        # jpackage may rewrite the signature blob of input Mach-O files. The loader pins the whole
        # native file, not just its CodeDirectory. Restore the verified producer bytes, then seal
        # only our newly generated ad-hoc outer bundle; never re-sign vendor runtime components.
        metadata = subprocess.check_output(['/usr/bin/codesign', '-d', '--verbose=4', str(app)],
                                           stderr=subprocess.STDOUT, text=True)
        flags = re.search(r'flags=0x([0-9a-fA-F]+)', metadata)
        if not flags or not int(flags.group(1), 16) & 2:
            raise ValueError('Refusing to replace a non-ad-hoc bundle signature')
        shutil.copy2(library, app / 'Contents/app/native' / library.name)
        if digest(app / 'Contents/app/native' / library.name) != values['sha256']:
            raise ValueError('Packaged native bytes differ from verified producer')
        run(['/usr/bin/codesign', '--verify', '--strict', app / 'Contents/app/native' / library.name])
        run(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', app])
        run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app])
    app_inputs = app / ('Contents/app' if system == 'Darwin' else 'app' if system == 'Windows' else 'lib/app')
    for name in names + ['rpc-launcher.jar']:
        if digest(inputs / name) != digest(app_inputs / name):
            raise ValueError('Packaged classpath differs from verified inputs')

    limitations = ['Developer preview, not release signed/notarized or device qualified.',
                   'Requires a permitted private IPv4 LAN; transport checks remain strict.',
                   'Use a separate application profile passphrase, not your OS login password.']
    if system == 'Windows':
        limitations.append('WINDOWS UI ONLY: POSIX protected profile storage is unavailable; Host/Client disabled.')
    (work / 'image' / 'README.txt').write_text('\n'.join(limitations) + '\n')
    extension = 'tar.gz' if system == 'Linux' else 'zip'
    filename = f'p2pkit-rpc-{label}-{source[:12]}.{extension}'
    archive = out / filename
    if archive.exists():
        raise ValueError('Refusing to replace an existing artifact')
    if system == 'Darwin':
        # ditto preserves the app's executable modes and symlinks in the runtime image.
        run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', app, archive])
    elif system == 'Linux':
        with tarfile.open(archive, 'x:gz') as content:
            content.add(app, arcname=app.name)
        with tarfile.open(archive, 'r:gz') as content:
            member = content.getmember('P2pKit-RPC/bin/P2pKit-RPC')
            if not member.isfile() or not member.mode & 0o111:
                raise ValueError('Packaged Linux launcher is not executable')
    else:
        shutil.make_archive(str(archive.with_suffix('')), 'zip', work / 'image')
    if system != 'Linux':
        with zipfile.ZipFile(archive) as content:
            if content.testzip() is not None:
                raise ValueError('Archive CRC failed')
    receipt = dict(schema=1, sourceCommit=source, tree=tree, platform=label,
                   scope='DEVELOPER_PREVIEW_NOT_RELEASE_OR_NETWORK_QUALIFICATION',
                   file=filename, bytes=archive.stat().st_size, sha256=digest(archive),
                   java=run([jdk / 'bin' / ('java.exe' if system == 'Windows' else 'java'), '--version']),
                   limitations=limitations, packagingVersion='1.0.0',
                   signing='ad-hoc outer and native verified; not notarized' if system == 'Darwin' else 'unsigned',
                   workflowRun=os.environ.get('GITHUB_RUN_ID'), attempt=os.environ.get('GITHUB_RUN_ATTEMPT'))
    (out / (label + '.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    (out / (label + '-README.txt')).write_text('\n'.join(limitations) + '\n')
    if run(['git', 'rev-parse', 'HEAD'], root) != source or run(['git', 'status', '--porcelain'], root):
        raise ValueError('Source changed during packaging')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jdk', type=Path, required=True)
    args = parser.parse_args()
    package(Path(__file__).resolve().parent.parent, args.jdk.resolve(strict=True))
