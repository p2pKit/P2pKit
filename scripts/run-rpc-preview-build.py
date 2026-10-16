#!/usr/bin/env python3
"""Explicit disposable GitHub runner preview builds; no signing secrets or device execution."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
TARGET = os.environ.get('RPC_PREVIEW_TARGET')


def run(args, **kwargs):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True, **kwargs)


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('Disposable GitHub-hosted runner only')
    if TARGET not in ('android', 'linux', 'windows-ui-preview', 'macos-arm64'):
        raise ValueError('Unknown target')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if source != os.environ['GITHUB_SHA']:
        raise ValueError('Source mismatch')
    sdk = Path(os.environ['ANDROID_HOME'])
    if sys.argv[1:] == ['configure']:
        home = Path(os.environ.get('GRADLE_USER_HOME', Path.home() / '.gradle'))
        home.mkdir(parents=True, exist_ok=True)
        settings = home / 'gradle.properties'
        original = settings.read_text() if settings.exists() else ''
        settings.write_text(original + '\norg.gradle.java.installations.auto-download=false\n' +
                            'org.gradle.java.installations.paths=' +
                            ','.join(Path(os.environ[k]).as_posix() for k in ('JAVA_HOME', 'RPC_PREVIEW_JDK21')) + '\n')
        manager = sdk / 'cmdline-tools/latest/bin' / ('sdkmanager.bat' if os.name == 'nt' else 'sdkmanager')
        run([manager, '--sdk_root=' + str(sdk), 'platforms;android-36', 'platforms;android-37.0',
             'build-tools;36.1.0'], input='y\n' * 100, text=True)
        return
    if sys.argv[1:] != ['build']:
        raise ValueError('Expected configure or build')
    flags = ['--no-daemon', '--no-build-cache', '--no-configuration-cache', '--no-parallel',
             '--max-workers=2', '--dependency-verification', 'strict', '--warning-mode=fail',
             '-Pkotlin.compiler.execution.strategy=in-process', '--console=plain']
    tasks = ([':p2p-sample-android:testDebugUnitTest', '--tests', 'dev.p2pkit.sample.android.rpclab.*',
              ':p2p-sample-android:assembleDebug'] if TARGET == 'android' else
             [':p2p-sample-rpc:prepareRpcCapacityLab'])
    # Desktop protected-profile tests are POSIX-only, not silently counted as Windows passes.
    if TARGET in ('linux', 'macos-arm64'):
        tasks += [':p2p-sample-rpc:jvmTest', '--tests', 'dev.p2pkit.sample.rpc.desktop.*']
    if TARGET == 'macos-arm64':
        tasks += [':p2p-transport-lan:stageMacTcp']
    start = time.monotonic()
    wrapper = [str(ROOT / 'gradlew.bat')] if os.name == 'nt' else ['/bin/sh', str(ROOT / 'gradlew')]
    command = wrapper + tasks + flags
    (ROOT / 'build').mkdir(exist_ok=True)
    code = 1
    try:
        run(command)
        if TARGET != 'android':
            run([sys.executable, '-I', '-B', ROOT / 'scripts/package-rpc-preview.py', '--jdk', os.environ['JAVA_HOME']])
        else:
            out = ROOT / 'build/rpc-app-delivery'
            out.mkdir(parents=True, exist_ok=False)
            apk = ROOT / 'samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk'
            signer = sdk / 'build-tools/36.1.0/apksigner'
            checked = subprocess.check_output([str(signer), 'verify', '--verbose', '--print-certs', str(apk)], text=True)
            destination = out / ('p2pkit-rpc-android-' + source[:12] + '.apk')
            shutil.copy2(apk, destination)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            (out / 'manifest.json').write_text(json.dumps(dict(sourceCommit=source,
                tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
                file=destination.name, sha256=digest, bytes=destination.stat().st_size,
                signing='CI debug key; not the existing device/store key', signatureVerification=checked,
                scope='DEBUG_PREVIEW_NOT_DEVICE_OR_RELEASE_QUALIFICATION'), indent=2) + '\n')
            (out / 'README.txt').write_text('Debug-only RPC launcher: P2pKit RPC. No device/ART pass claimed.\n'
                'CI debug signing may differ from an installed local APK. Do not uninstall/reset trust to hide a mismatch.\n'
                'No signing credential is included in this artifact.\n')
        code = 0
    finally:
        (ROOT / 'build/rpc-preview-build.json').write_text(json.dumps(dict(sourceCommit=source,
            target=TARGET, command=command, exitCode=code, elapsedSeconds=time.monotonic() - start,
            scope='PREVIEW_BUILD_NOT_INTEROPERABILITY_OR_RELEASE_QUALIFICATION'), indent=2) + '\n')


if __name__ == '__main__':
    main()
