#!/usr/bin/env python3
"""Create only owned synthetic signed-file controls; never launch an app, load JNI, install, or contact a peer."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import zipfile

SOURCE = '1' * 40
TREE = '2' * 40


def command(arguments):
    result = subprocess.run(arguments, check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=60,
                            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError('Synthetic fixture command failed: ' + repr(arguments) + '\n' + result.stdout)
    return result.stdout


def write_jar(path, entries):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as jar:
        for name, content in entries.items():
            jar.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('Mac ARM64 required; no platform skip')
    root = args.output.absolute()
    if root.exists() or root != root.resolve(strict=False) or not root.parent.is_dir():
        raise RuntimeError('New canonical output directory required')
    root.mkdir(mode=0o700)
    helper_path = Path(__file__).resolve().parents[1] / 'stage-rpc-macos-app.py'
    spec = importlib.util.spec_from_file_location('stage_rpc_app', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    (root / 'fixture.c').write_text('int fixture(void) { return 42; }\nint main(void) { return 0; }\n')
    clang = command(['/usr/bin/xcrun', '--sdk', 'macosx', '--find', 'clang']).strip()
    sdk = command(['/usr/bin/xcrun', '--sdk', 'macosx', '--show-sdk-path']).strip()
    stage = root / 'stage'
    stage.mkdir(mode=0o700)
    library = stage / helper.LIBRARY
    command([clang, '-isysroot', sdk, '-Wall', '-Wextra', '-Werror', '-arch', 'arm64', '-dynamiclib',
             '-Wl,-install_name,@rpath/' + helper.LIBRARY, str(root / 'fixture.c'), '-o', str(library)])
    command(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', str(library)])
    command(['/usr/bin/codesign', '--verify', '--strict', str(library)])
    values = dict(abi='1', platform='macos', arch='arm64', source=SOURCE, tree=TREE, file=helper.LIBRARY,
                  bytes=str(library.stat().st_size), sha256=hashlib.sha256(library.read_bytes()).hexdigest())
    raw = ''.join(f'{key}={value}\n' for key, value in values.items()).encode('ascii')
    (stage / 'macos-tcp.properties').write_bytes(raw)
    write_jar(stage / 'p2pkit-macos-tcp-manifest.jar', {helper.RESOURCE: raw})
    (root / 'trusted.properties').write_bytes(raw)
    original = root / 'input' / 'P2pKit Native Fixture.app'
    (original / 'Contents/MacOS').mkdir(parents=True)
    (original / 'Contents/app').mkdir()
    launcher = original / 'Contents/MacOS/P2pKitNativeFixture'
    command([clang, '-isysroot', sdk, '-Wall', '-Wextra', '-Werror', '-arch', 'arm64',
             str(root / 'fixture.c'), '-o', str(launcher)])
    command(['/usr/bin/codesign', '--remove-signature', str(launcher)])
    (original / 'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleExecutable': launcher.name, 'CFBundleIdentifier': 'dev.p2pkit.test.installed-native-fixture',
        'CFBundleName': 'P2pKit Native Fixture', 'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '0.0.0', 'CFBundleVersion': '1',
    }))
    write_jar(original / 'Contents/app/transport-fixture.jar', {
        'dev/p2pkit/transport/lan/MacLanNativeLoader.class': b'synthetic test marker, not executable bytecode',
    })
    shutil.copyfile(stage / 'p2pkit-macos-tcp-manifest.jar', original / 'Contents/app/p2pkit-macos-tcp-manifest.jar')
    (original / 'Contents/app/P2pKitNativeFixture.cfg').write_text(
        '[Application]\napp.classpath=$APPDIR/transport-fixture.jar:$APPDIR/p2pkit-macos-tcp-manifest.jar\n'
        '[JavaOptions]\njava-options=-D' + helper.PROPERTY + '=' + helper.POLICY + '\n')
    (root / 'good').mkdir(mode=0o700)
    good = root / 'good' / original.name
    receipt = helper.finalize(original, good, stage, SOURCE, TREE)
    (root / 'finalizer-receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    cases = ['changed-native', 'changed-manifest', 'changed-resource', 'unsigned', 'symlink', 'hardlink',
             'writable-file', 'writable-directory', 'allow-acl']
    for case in cases:
        app = root / case / original.name
        shutil.copytree(good, app)
        native = app / helper.NATIVE
        file = native / helper.LIBRARY
        if case == 'changed-native':
            with file.open('r+b') as output:
                output.seek(512)
                byte = output.read(1)
                output.seek(512)
                output.write(bytes([byte[0] ^ 1]))
        elif case == 'changed-manifest':
            with (native / 'macos-tcp.properties').open('ab') as output:
                output.write(b'extra=1\n')
        elif case == 'changed-resource':
            with (app / 'Contents/app/transport-fixture.jar').open('ab') as output:
                output.write(b'changed-resource\n')
        elif case == 'unsigned':
            command(['/usr/bin/codesign', '--remove-signature', str(app)])
        elif case == 'symlink':
            file.unlink()
            file.symlink_to(good / helper.NATIVE / helper.LIBRARY)
        elif case == 'hardlink':
            os.link(file, native / 'extra-hardlink')
        elif case == 'writable-file':
            os.chmod(file, 0o664)
        elif case == 'writable-directory':
            os.chmod(native, 0o775)
        elif case == 'allow-acl':
            command(['/bin/chmod', '+a', 'everyone allow read', str(file)])
    # Explicit helper rejection controls; every output is new and all prior artifacts remain untouched.
    controls = {}
    tests = {
        'reject-overwrite': (original, good, stage, SOURCE, TREE),
        'reject-invalid-existing-signature': (root / 'changed-resource' / original.name,
                                              root / 'reject-invalid' / original.name, stage, SOURCE, TREE),
        'reject-wrong-source': (original, root / 'reject-source' / original.name, stage, '3' * 40, TREE),
        'reject-replacement-native-stage': (good, root / 'reject-replacement' / original.name, stage, SOURCE, TREE),
    }
    for name, arguments in tests.items():
        arguments[1].parent.mkdir(mode=0o700, exist_ok=True)
        try:
            helper.finalize(*arguments)
        except ValueError:
            controls[name] = 'PASS'
        else:
            raise RuntimeError('Expected finalizer rejection: ' + name)
    result = {'scope': 'SYNTHETIC_SIGNED_FILE_PREFLIGHT_NOT_NATIVE_OR_APPLICATION_QUALIFICATION',
              'source': SOURCE, 'tree': TREE, 'nativeLoaded': False, 'applicationLaunched': False,
              'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'finalizerSha256': hashlib.sha256(helper_path.read_bytes()).hexdigest(),
              'compiler': command([clang, '--version']), 'sdk': sdk, 'fixtureCases': ['good'] + cases,
              'finalizerControls': controls, 'fixtures': helper.inventory(root)}
    (root / 'fixture-receipt.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'fixtures'}, sort_keys=True))


if __name__ == '__main__':
    main()
