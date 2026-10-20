#!/usr/bin/env python3
"""Focused native #327/#409 commands, not the retired host-qualification suite.

Run outside ci_evidence: the unchanged Swift/JVM controller requires the existing
leaf executor's real context. Afterwards `retain` joins actual terminal receipts
and private artifacts under ci_evidence; that manifest describes validation, not
an invented native invocation. Neither operation grants physical-device credit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / 'scripts/run-audit-command.py'
HOSTED_EXECUTOR = ROOT / 'scripts/run-apple-issue-command.py'
HOSTED_BOUNDARY = 'GITHUB_HOSTED_DARWIN_MARKER_DOMAIN_V1'
SELF = ROOT / 'scripts/run-apple-issue-validation.py'
RELEASE = ROOT / 'library/p2p-transport-lan/build/XCFrameworks/release'
SIDECARS = ('BUILD_COMMIT.txt', 'BUILD_SOURCE_STATE.txt', 'BUILD_INPUTS_SHA256.txt', 'BUILD_ARTIFACTS_SHA256.txt')
CASE = 'p2pkit-sample-jvm-transfer-tests/SwiftJvmTransferUITests/testBidirectionalSecure204800ByteTransferWithJvmPeer()'
OPERATIONS = ('iphoneos-product', 'swift-jvm-transfer', 'both')
REPORT = ROOT / 'build/apple-issue-validation'


class UnsafeRun(RuntimeError):
    """Missing finalization blocks every later productive command."""


def require(value, message):
    if not value:
        raise ValueError(message)


def native_host(operation):
    require(operation in OPERATIONS, 'Unknown native operation')
    # Native2 exhausted the unchanged absolute360 cap during Intel XCTest/UI
    # startup. Select the maintained ARM image for only the remaining #409 case;
    # no prewarming, acceptance-clock changes or application changes are made.
    arm = operation == 'swift-jvm-transfer'
    require(platform.system() == 'Darwin' and platform.machine() == ('arm64' if arm else 'x86_64'),
            'Selected operation requires its native macOS architecture')
    require(os.environ.get('RUNNER_OS') == 'macOS' and os.environ.get('RUNNER_ARCH') == ('ARM64' if arm else 'X64'),
            'Hosted runner architecture differs from the selected native operation')
    require(platform.mac_ver()[0].split('.')[0] == ('26' if arm else '15'),
            'Selected operation requires its maintained macOS image')
    return 'macos-arm64' if arm else 'macos-x64'


def read(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024, 'Invalid JSON file')
    return json.loads(path.read_text())


def write(path, value):
    with path.open('x') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def digest(path):
    with path.open('rb') as stream:
        checksum = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
        return checksum.hexdigest()


def audit_module():
    sys.path.insert(0, str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('apple_issue_executor', EXECUTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def terminal_module():
    spec = importlib.util.spec_from_file_location('apple_terminal_receipts', ROOT / 'scripts/run-ci-terminal-component.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def terminal_directory(parent):
    terminal = terminal_module()
    terminal.apple_parent({'APPLE_ISSUE_PARENT': str(parent), 'RUNNER_TEMP': os.environ['RUNNER_TEMP']})
    reference = terminal.private.read_json(parent / 'terminal-context.json')
    require(set(reference) == {'schema', 'component', 'source', 'directory'} and
            type(reference['schema']) is int and reference['schema'] == 1 and
            reference['component'] == terminal.APPLE_COMPONENT, 'Invalid Apple Terminal reference')
    directory = Path(reference['directory'])
    terminal.private.private_parent(directory, os.getuid())
    require(parent.parent == directory.parent == Path(os.environ['RUNNER_TEMP']).resolve(strict=True) and
            directory.name.startswith('ci-terminal-'), 'Terminal evidence outside the original runner state')
    return directory, reference


def terminal_ok(parent, source):
    terminal = terminal_module()
    directory, reference = terminal_directory(parent)
    identity = {key: source[key] for key in ('commit', 'tree')}
    require(reference['source'] == identity, 'Terminal source differs from the native source')
    wrapper = terminal.private.read_json(directory / 'wrapper-result.json')
    require(type(wrapper.get('schema')) is int and type(wrapper.get('finalExitCode')) is int and
            wrapper.get('finalized') is True and wrapper.get('commandRemoved') is True and
            wrapper == {
        'schema': 1, 'component': terminal.APPLE_COMPONENT, 'source': identity,
        'finalExitCode': 0, 'finalized': True, 'commandRemoved': True}, 'Terminal wrapper did not finalize successfully')
    compile_result = terminal.private.read_json(directory / 'compile-result.json')
    require(compile_result.get('code') == 'PASS' and compile_result.get('cleanupKnown') is True and
            compile_result.get('capturesClosed') is True, 'Terminal helper compile did not finalize successfully')
    require(terminal.private.read_private(directory / 'shell-result.txt', os.getuid()) == b'0\n',
            'Terminal shell did not return the original successful child status')
    terminal.validate_result(terminal.private.read_json(directory / 'application-result.json'),
        terminal.private.read_json(directory / 'child-admission.json'),
        terminal.private.read_json(directory / 'child-result.json'), identity, 0, terminal.APPLE_COMPONENT)


def iphoneos_command(derived):
    require(derived.is_absolute() and not derived.exists(), 'DerivedData must be fresh and absolute')
    return ['xcodebuild', '-jobs', '2', '-project', str(ROOT / 'samples/iosApp/p2pkit-sample.xcodeproj'),
            '-scheme', 'p2pkit-sample-ui', '-configuration', 'Debug', '-sdk', 'iphoneos',
            '-destination', 'generic/platform=iOS', '-derivedDataPath', str(derived),
            'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'build']


def inspect_iphoneos(derived, output):
    """Inspect the exact recipe product, never substitute a simulator product."""
    app = derived / 'Build/Products/Debug-iphoneos/p2pkit-sample.app'
    require(app.is_dir(), 'Recipe product missing')
    with (app / 'Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    require(info.get('CFBundleSupportedPlatforms') == ['iPhoneOS'] and info.get('DTPlatformName') == 'iphoneos',
            'Not an iphoneos application')
    executable = info.get('CFBundleExecutable')
    require(isinstance(executable, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', executable), 'Invalid app executable')
    binaries = {'app': app / executable, 'embeddedFramework': app / 'Frameworks/P2pKitShared.framework/P2pKitShared'}
    debug = app / (executable + '.debug.dylib')
    if debug.exists():
        binaries['appDebugDylib'] = debug
    result = {'schema': 1, 'result': 'PASS', 'product': str(app), 'derivedData': str(derived),
              'signed': False, 'deviceInstalled': False, 'binaries': {}}
    for name, binary in binaries.items():
        require(binary.is_file() and binary.stat().st_size > 0, 'Missing built binary')
        architectures = subprocess.check_output(['xcrun', 'lipo', '-archs', str(binary)], timeout=30).decode().split()
        load = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], timeout=30).decode()
        require(architectures == ['arm64'] and re.findall(r'^\s*platform\s+(\S+)', load, re.M) == ['IOS'],
                'Built product is not an arm64 iOS device binary')
        result['binaries'][name] = {'sha256': digest(binary), 'bytes': binary.stat().st_size,
                                     'architectures': architectures, 'buildCommands': load}
    links = subprocess.check_output(['xcrun', 'otool', '-L', str(binaries['app'])], timeout=30).decode()
    result['linkedLibraries'] = {'app': links}
    if debug.exists():
        require('@rpath/' + debug.name in links, 'App does not link its actual Debug dylib')
        links = subprocess.check_output(['xcrun', 'otool', '-L', str(debug)], timeout=30).decode()
        result['linkedLibraries']['appDebugDylib'] = links
    require('@rpath/P2pKitShared.framework/P2pKitShared' in links, 'App does not link the embedded framework')
    write(output, result)


def receipt_ok(value, source):
    require(value.get('finalExitCode') == 0 and value.get('productExitCode') == 0 and
            value.get('stopExitCode') == 0 and value.get('sourceUnchanged') is True and
            value.get('sourceBefore') == value.get('sourceAfter') == source and
            value.get('errors') == [] and value.get('ownedSurvivors') == [] and
            value.get('ownership', {}).get('ownershipBoundary') == HOSTED_BOUNDARY,
            'Native command/cleanup/boundary did not pass')


def transfer_ok(value, source, bundles):
    require(len(bundles) == 1 and value.get('schema') == 1 and value.get('result') == 'PASS' and
            value.get('source') == source and value.get('case') == CASE and
            value.get('nativeCase') == {'identifier': CASE, 'status': 'Success'} and
            value.get('resultBundle') == 'Logs/Test/' + bundles[0].name, 'Exact original native case missing')
    rows = value.get('transfers', [])
    require(len(rows) == 2 and {row.get('direction') for row in rows} == {'swift-to-jvm', 'jvm-to-swift'} and
            len({row.get('transferId') for row in rows}) == 2 and all(row.get('bytes') == 204800 and
            re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')) and row.get('sender', {}).get('events') and
            row.get('receiver', {}).get('events') for row in rows) and value.get('cleanupErrors') == [] and
            value.get('unresolvedChildren') == [], 'Transfer/integrity/natural cleanup incomplete')
    ready = value.get('readiness', {})
    activity, offer = ready.get('activity', {}), ready.get('firstOfferAccepted', {})
    require(ready.get('finalUniqueActivityVerified') is True and
            activity.get('producerRawNanoseconds', -1) <= offer.get('hostRawNanoseconds', -2) <
            activity.get('producerRawNanoseconds', -1) + 120_000_000_000 and
            offer.get('monotonicSeconds', float('inf')) < ready.get('absoluteDeadlineMonotonicSeconds', -1),
            'Producer-clock readiness/first-offer evidence missing')
    require(value.get('cliQuitWriteUtc') and value.get('cliQuitFlushedUtc') and
            not value.get('cliQuitTimeoutUtc'), 'Natural CLI quit evidence missing')


def select_simulator(devices):
    # Same maintained newest-available-runtime policy, but reject duplicate
    # devices within that runtime instead of silently selecting one by UUID.
    choices = []
    for runtime, rows in devices.items():
        match = re.search(r'\.SimRuntime\.iOS-([0-9-]+)$', runtime)
        if match:
            for device in rows:
                if device.get('name') == 'iPhone 17' and device.get('isAvailable') is True and device.get('state') == 'Shutdown':
                    choices.append((tuple(map(int, match[1].split('-'))), device['udid']))
    require(choices, 'No available shutdown iPhone 17 simulator')
    newest = max(version for version, _ in choices)
    selected = [udid for version, udid in choices if version == newest]
    require(len(selected) == 1 and re.fullmatch(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}', selected[0]),
            'Ambiguous or malformed simulator in newest available runtime')
    return selected[0]


class Run:
    def __init__(self, state, operation):
        self.state, self.operation = state, operation
        self.safe = True
        self.audit = audit_module()
        self.context = read(state / 'context.json')
        self.environment = dict(os.environ, P2PKIT_AUDIT_STATE_DIR=str(state),
                                GRADLE_USER_HOME=str(state / 'gradle-home'),
                                P2PKIT_GRADLE_EXECUTOR=str(HOSTED_EXECUTOR), P2PKIT_XCODE_JOBS='2')
        self.result = {'schema': 1, 'source': self.context['source'], 'operation': operation,
                       'result': 'FAIL', 'issues': {}, 'commands': [],
                       'limits': 'Unsigned device build and same-codebase host/simulator integration only; no physical, AWDL, backup or independent-peer credit.'}

    def invoke(self, label, command, kind='command', timeout=3600, extra=None):
        receipt = self.state / ('host-' + label + '.json')
        argv = [sys.executable, str(HOSTED_EXECUTOR), '--cwd', str(ROOT), '--wrapper', str(ROOT / 'gradlew'),
                '--purpose', label, '--kind', kind, '--receipt', str(receipt), '--timeout', str(timeout), '--', *command]
        require(self.safe, 'Previous command finalization unknown')
        self.safe = False
        code = subprocess.call(argv, cwd=ROOT, env={**self.environment, **(extra or {})})
        self.result['commands'].append({'label': label, 'exitCode': code, 'receipt': receipt.name})
        try:
            record = read(receipt)
            require(record.get('errors') == [] and record.get('ownedSurvivors') == [] and
                    record.get('stopExitCode') == 0 and record.get('sourceUnchanged') is True and
                    record.get('ownership', {}).get('ownershipBoundary') == HOSTED_BOUNDARY and
                    record.get('sourceBefore') == record.get('sourceAfter') == self.context['source'],
                    'Command finalization/source unknown')
            self.safe = True
        except Exception as error:
            raise UnsafeRun(label + ' finalization unknown') from error
        require(code == 0, label + ' failed')
        receipt_ok(record, self.context['source'])

    def execute(self):
        work = self.state / 'work'
        work.mkdir(mode=0o700)
        tools = {}
        for name, command in (('macos', ['sw_vers']), ('xcode', ['xcodebuild', '-version']),
                              ('iphoneosSdk', ['xcrun', '--sdk', 'iphoneos', '--show-sdk-version']),
                              ('java', [str(Path(os.environ['JAVA_HOME']) / 'bin/java'), '-version']),
                              ('xcodegen', ['xcodegen', '--version'])):
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=30)
            require(len(output) <= 65536, 'Tool identity output too large')
            tools[name] = {'command': command, 'output': output.decode('utf-8')}
        write(self.state / 'tools.json', tools)
        expected_xcode = 'Xcode 26.5' if self.operation == 'swift-jvm-transfer' else 'Xcode 26.3'
        require(tools['xcode']['output'].splitlines()[0] == expected_xcode, 'Selected maintained Xcode version required')
        require(not RELEASE.exists(), 'Canonical XCFramework output must not preexist this run')
        self.invoke('xcframework-build', [':p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance'], 'gradle', 7200)
        rows = []
        for name in SIDECARS:
            path = RELEASE / name
            require(path.is_file() and not path.is_symlink(), 'Canonical producer sidecar missing')
            shutil.copyfile(path, self.state / 'evidence' / name)
            rows.append({'path': name, 'sha256': digest(path), 'result': 'RETAINED'})
        write(self.state / 'evidence/xcframework-sidecars.json',
              {'sourceInvocationId': read(self.state / 'host-xcframework-build.json')['id'], 'files': rows})
        # Existing executor reuses only this finalized producer + all four original
        # sidecars for Xcode's mandatory verification; no stale output exemption.
        self.audit.xcframework_reuse_binding(self.state, self.context, ROOT, ROOT / 'gradlew')
        self.invoke('xcframework-inspect', ['bash', 'scripts/check-xcframework-minimum-os.sh'])
        if self.operation in ('iphoneos-product', 'both'):
            try:
                self.invoke('xcode-project', ['xcodegen', 'generate', '--spec', 'samples/iosApp/project.yml'])
                derived = work / 'iphoneos/DerivedData'
                derived.parent.mkdir(mode=0o700)
                self.invoke('iphoneos-build', iphoneos_command(derived), timeout=3600)
                self.invoke('iphoneos-inspect', [sys.executable, str(SELF), 'inspect-iphoneos',
                    '--derived-data', str(derived), '--output', str(self.state / 'iphoneos-product.json')], timeout=120)
                self.result['issues']['327'] = 'PASS'
            except Exception as error:
                self.result['issues']['327'] = 'FAIL'
                self.result.setdefault('errors', []).append(str(error))
                if not self.safe:
                    raise
        if self.operation in ('swift-jvm-transfer', 'both'):
            try:
                self.invoke('swift-jvm-cli-prepare', [':p2p-sample-desktop:installDist'], 'gradle', 3600)
                inventory = subprocess.check_output(['xcrun', 'simctl', 'list', '--json', 'devices', 'available'], timeout=30)
                devices = json.loads(inventory)['devices']
                udid = select_simulator(devices)
                write(self.state / 'simulator-inventory.json', json.loads(inventory))
                extra = {'IOS_RUN_DIR': str(work / 'swift-ui'), 'KEEP_IOS_RUN_ARTIFACTS': '1', 'SIM_UDID': udid}
                try:
                    self.invoke('swift-jvm-ui-prepare', ['bash', 'scripts/run-ios-ui-tests.sh', 'prepare-jvm-transfer'], extra=extra)
                    self.invoke('swift-jvm-transfer', ['bash', 'scripts/run-ios-ui-tests.sh', 'run-jvm-transfer'], timeout=900, extra=extra)
                    bundles = list((work / 'swift-ui/DerivedData/Logs/Test').glob('swift-jvm-transfer-*.xcresult'))
                    transfer_ok(read(work / 'swift-ui/jvm-transfer/result.json'), self.context['source'], bundles)
                finally:
                    # Retire this exact simulator only; never erase or change privacy.
                    if self.safe:
                        self.invoke('simulator-shutdown', ['xcrun', 'simctl', 'shutdown', udid], timeout=120)
                self.result['issues']['409'] = 'PASS'
            except Exception as error:
                self.result['issues']['409'] = 'FAIL'
                self.result.setdefault('errors', []).append(str(error))
        require(self.result['issues'] and all(value == 'PASS' for value in self.result['issues'].values()), 'Selected acceptance incomplete')
        self.result['result'] = 'PASS'


def run(state, operation):
    host = native_host(operation)
    require(os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'Use a disposable hosted runner')
    require(not any(os.environ.get(key) for key in ('P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN',
            'P2PKIT_AUDIT_OWNERSHIP_DOMAINS', 'P2PKIT_AUDIT_STATE_DIR')), 'Run directly, not inside another ownership context')
    code = subprocess.call([sys.executable, str(EXECUTOR), 'init', '--root', str(ROOT), '--state', str(state),
                           '--expected-commit', os.environ['GITHUB_SHA'], '--host', host], cwd=ROOT)
    require(code == 0, 'Native context initialization failed')
    runner = Run(state, operation)
    try:
        runner.execute()
    except Exception as error:
        runner.result.setdefault('errors', []).append(str(error))
    finally:
        write(state / 'result.json', runner.result)
    return 0 if runner.result['result'] == 'PASS' else 1


def retain(state, bootstrap_log):
    """Retain original failures too. ci_evidence encrypts this private report tree."""
    require(not REPORT.exists(), 'Report directory must be fresh')
    REPORT.mkdir(parents=True, mode=0o700)
    selected = [bootstrap_log, *state.glob('*.json'), *state.glob('evidence/**/*'),
                *state.glob('work/swift-ui/jvm-transfer/*.json'), *state.glob('work/swift-ui/jvm-transfer/*.jsonl'),
                *state.glob('work/swift-ui/jvm-transfer/*.log'),
                *state.glob('work/swift-ui/DerivedData/Logs/Test/swift-jvm-transfer-*.xcresult/**/*')]
    terminal = None
    reference = state.parent / 'terminal-context.json'
    if reference.exists():
        terminal, _ = terminal_directory(state.parent)
        # Retain original private receipts/logs even on failure, never the helper
        # binary or executable .command. A missing final result remains failure.
        selected += [reference, *terminal.glob('*.json'), *terminal.glob('*.log'),
                     *terminal.glob('shell-result.txt'),
                     *terminal.glob('compile/**/*.json'), *terminal.glob('compile/**/*.log')]
    count = total = 0
    for path in sorted(set(selected)):
        if path.is_dir() and not path.is_symlink():
            continue
        require(path.is_file() and not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), 'Invalid retained evidence')
        if path == bootstrap_log:
            relative = Path('driver.log')
        elif path == reference:
            relative = Path('terminal-context.json')
        elif terminal is not None and path.is_relative_to(terminal):
            relative = Path('terminal') / path.relative_to(terminal)
        else:
            relative = path.relative_to(state)
        require(not any(parent.is_symlink() for parent in path.parents), 'Symlinked evidence path')
        total += path.stat().st_size
        count += 1
        require(total <= 480 * 1024 * 1024 and count <= 9500, 'Evidence exceeds existing archive bounds')
        target = REPORT / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(path, target)
        os.chmod(target, 0o600)
        require(digest(path) == digest(target), 'Evidence changed during retention')
    result, context = read(state / 'result.json'), read(state / 'context.json')
    require(audit_module().source_snapshot(ROOT) == context['source'] == result['source'], 'Source changed')
    expected = {'327', '409'} if result['operation'] == 'both' else (
        {'327'} if result['operation'] == 'iphoneos-product' else {'409'})
    require(set(result['issues']) == expected, 'Requested acceptance not completely accounted for')
    for row in result['commands']:
        if row['exitCode'] == 0:
            receipt_ok(read(state / row['receipt']), context['source'])
    require(result['result'] == 'PASS' and result['issues'] and
            all(value == 'PASS' for value in result['issues'].values()), 'Native results failed; original evidence retained')
    if '327' in expected:
        require(read(state / 'iphoneos-product.json').get('result') == 'PASS', 'Product inspection missing')
    if '409' in expected:
        if result['operation'] == 'swift-jvm-transfer':
            terminal_ok(state.parent, context['source'])
        bundles = list((state / 'work/swift-ui/DerivedData/Logs/Test').glob('swift-jvm-transfer-*.xcresult'))
        transfer_ok(read(state / 'work/swift-ui/jvm-transfer/result.json'), context['source'], bundles)
    print('APPLE_ISSUE_VALIDATION PASS ' + ','.join(sorted(result['issues'])))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    native = sub.add_parser('run')
    native.add_argument('--state', type=Path, required=True)
    native.add_argument('--operation', choices=OPERATIONS, required=True)
    product = sub.add_parser('inspect-iphoneos')
    product.add_argument('--derived-data', type=Path, required=True)
    product.add_argument('--output', type=Path, required=True)
    reports = sub.add_parser('retain')
    reports.add_argument('--state', type=Path, required=True)
    reports.add_argument('--bootstrap-log', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'run':
        return run(args.state, args.operation)
    if args.command == 'retain':
        return retain(args.state, args.bootstrap_log)
    inspect_iphoneos(args.derived_data, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
