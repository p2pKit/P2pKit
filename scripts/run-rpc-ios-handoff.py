#!/usr/bin/env python3
"""Fresh native-ARM phone controls and unsigned test-app handoff, never a release.

The unchanged native executor must admit/finalize every command. This independent
app-hosted simulator scope does not replace the full Apple matrix, ARM adapter
cleanup, Bonjour, physical signing, interoperability or mobile-capacity gates.
"""
from __future__ import annotations

import argparse
import contextlib
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
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_capacity_evidence as evidence
import rpc_phone_diagnostics as phone_diagnostics

REF = 'refs/heads/work/rpc-lan-20260927-054728-8b1b11da'
MARKER = '[rpc-ios-handoff]'
SCOPE = 'UNSIGNED_PHONE_APP_NATIVE_ARM_SIMULATOR_NOT_APPLE_MATRIX_PHYSICAL_CAPACITY_OR_RELEASE'
DEVELOPER = '/Applications/Xcode_26.5.app/Contents/Developer'
PURPOSES = ('native-controls', 'jdk17', 'jdk21', 'macos-version', 'xcode-version', 'xcode-first-launch',
            'rosetta-admission', 'android-compile-platforms', 'pinned-xcodegen', 'phone-runtimes', 'phone-controls')
BOUNDS = dict(zip(PURPOSES, (1800, 45, 45, 45, 45, 120, 45, 900, 900, 120, 18000)))
PACKAGES = ('platforms;android-36', 'platforms;android-37.0', 'platform-tools')
ARCHIVE = 'p2pkit-rpc-iphone-unsigned.app.zip'
MAX_APP = 1024 ** 3
MAX_ARCHIVE = 512 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def admit(env):
    need(platform.system() == 'Darwin' and platform.machine() == 'arm64' and os.getuid() == os.geteuid() != 0,
         'Native unprivileged Apple ARM execution required')
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and re.fullmatch('[a-f0-9]{40}', env.get('GITHUB_SHA', '')) and
         env.get('DEVELOPER_DIR') == DEVELOPER and Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT,
         'Exact supported host and feature source request required')


def runtime_selection(value):
    need(type(value) is dict and type(value.get('runtimes')) is list and len(value['runtimes']) <= 64,
         'Bounded actual simulator inventory required')
    choices = [r for r in value['runtimes'] if type(r) is dict and r.get('isAvailable') is True and
               re.fullmatch(r'com\.apple\.CoreSimulator\.SimRuntime\.iOS-[0-9-]{1,16}', r.get('identifier', ''))]
    need(choices and all(type(r.get('version')) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}', r['version'])
                        for r in choices), 'An installed iOS runtime is required')
    need(len({r['identifier'] for r in choices}) == len(choices), 'Ambiguous runtime inventory')
    selected = max(choices, key=lambda r: tuple(map(int, r['version'].split('.'))))
    need(type(selected.get('supportedArchitectures')) is list and 'arm64' in selected['supportedArchitectures'] and
         all(type(a) is str and a in ('arm64', 'x86_64') for a in selected['supportedArchitectures']) and
         len(set(selected['supportedArchitectures'])) == len(selected['supportedArchitectures']),
         'Selected runtime must support native ARM, never an x86 substitute')
    return selected['identifier']


def commands(state, q, runtime=None):
    sdk, xcodegen = state / 'work/sdk', state / 'tools/xcodegen/bin/xcodegen'
    result = {
        'native-controls': [sys.executable, 'scripts/tests/run-audit-command-test.py', '--expected-host', 'macos-arm64',
                            '--evidence-dir', str(state / 'evidence/native-controls')],
        'macos-version': ['/usr/bin/sw_vers', '-productVersion'],
        'xcode-version': ['/usr/bin/xcodebuild', '-version'],
        'xcode-first-launch': ['/usr/bin/xcodebuild', '-checkFirstLaunchStatus'],
        'rosetta-admission': [sys.executable, '-c', q.NATIVE_ROLE_PROBE],
        'android-compile-platforms': [str(sdk / 'cmdline-tools/latest/bin/sdkmanager'), '--sdk_root=' + str(sdk), *PACKAGES],
        'pinned-xcodegen': ['/bin/bash', 'scripts/install-xcodegen.sh', str(state / 'tools/xcodegen')],
        'phone-runtimes': ['/usr/bin/xcrun', 'simctl', 'list', 'runtimes', '--json'],
    }
    for major, key in (('17', 'JAVA_HOME'), ('21', 'P2PKIT_AUDIT_JDK21')):
        result['jdk' + major] = [str(Path(os.environ[key]).resolve(strict=True) / 'bin/java'),
                                '-XshowSettings:properties', '-version']
    if runtime is not None:
        need(re.fullmatch(r'com\.apple\.CoreSimulator\.SimRuntime\.iOS-[0-9-]{1,16}', runtime), 'Invalid runtime')
        result['phone-controls'] = [sys.executable, str(ROOT / 'scripts/run-rpc-phone-ios-controls.py'),
            '--owner-authorized-phone-controls', '--root', str(ROOT), '--directory', str(state / 'work/phone-controls'),
            '--xcodegen', str(xcodegen), '--runtime', runtime]
    return result


def receipt(runner, checker, state, context, purpose, argv, code):
    need(purpose in PURPOSES and type(code) is int, 'Exact native purpose/result required')
    value = runner.read_json(state / 'private' / (purpose + '.json'))
    checker.validate(value, code, purpose, ROOT, ROOT / 'gradlew', argv)
    need(value['jobId'] == context['id'] and value['host'] == 'macos-arm64' and value['kind'] == 'command' and
         value['sourceBefore'] == value['sourceAfter'] == context['source'] and
         value['gradleHome'] == context['gradleHome'] and value['ancestorInvocationIds'] == [] and
         not value['errors'] and not value['ownedSurvivors'] and not value['ownership']['discoveryErrors'] and
         value['stopExitCode'] == 0 and value == runner.read_json(state / 'evidence' / value['id'] / 'receipt.json'),
         'Original exact native ownership/finalization required')
    return value


def command_output(state, proof, stream='stdout'):
    return evidence.bounded(state / 'evidence' / proof['id'] / ('product.' + stream + '.log'), 64 * 1024 * 1024)


def verify_toolchain(state, proofs, q):
    for major in ('17', '21'):
        raw = command_output(state, proofs['jdk' + major], 'stderr').decode()
        need(re.search(r'(?m)^\s*java\.specification\.version = ' + major + r'\s*$', raw) and
             re.search(r'(?m)^\s*os\.arch = aarch64\s*$', raw), 'Actual native JDK required')
    need(command_output(state, proofs['macos-version']).decode().strip().split('.')[0] == '26' and
         command_output(state, proofs['xcode-version']).decode().splitlines()[0] == 'Xcode 26.5',
         'Required actual macOS 26 / Xcode 26.5 host')
    q.admit_native_apple_role('apple-arm64', command_output(state, proofs['rosetta-admission']))


def phone_observations(state, context, outer, runtime, runner, q):
    """Project only this finalized invocation's failed/successful tool observations."""
    work = state / 'work/phone-controls'
    path = work / 'result.json'
    private = runner.read_json(path) if path.exists() else None
    if private is not None:
        phone = module('ios_handoff_observed_phone', 'run-rpc-phone-ios-controls.py')
        need(type(private.get('schema')) is int and private['schema'] == 1 and private['scope'] == phone.SCOPE and
             private['source'] == context['source'] and private['architecture'] == 'arm64' and
             private['runtime'] == runtime and private['scriptSha256'] ==
             runner.file_digest(ROOT / 'scripts/run-rpc-phone-ios-controls.py'), 'Diagnostic source/owner differs')
    # Validate labels before using one to select an owned log. No recorded argv
    # or exception message is a file-selection capability.
    first = phone_diagnostics.observe(private, {}, ROOT)
    logs = {'phone-controls': {stream: command_output(state, outer, stream) for stream in ('stdout', 'stderr')}}
    for row in first['commands']:
        files = {stream: work / (row['label'] + '.' + stream) for stream in ('stdout', 'stderr')}
        if all(path.exists() for path in files.values()):
            logs[row['label']] = {stream: evidence.bounded(path, 256 * 1024 * 1024) for stream, path in files.items()}
    producer = None
    path = work / 'framework-producer.json'
    if path.exists():
        proof = runner.read_json(path)
        need(type(proof.get('id')) is str and re.fullmatch('[a-f0-9]{32}', proof['id']) and
             proof['jobId'] == context['id'] and proof['host'] == 'macos-arm64' and proof['kind'] == 'gradle' and
             proof['purpose'] == 'rpc-phone-framework-producer' and proof['sourceBefore'] == context['source'] and
             proof['gradleHome'] == context['gradleHome'] and proof['ancestorInvocationIds'] == [outer['id']] and
             proof['requestedArgv'] == [module('ios_handoff_observed_producer', 'run-rpc-phone-ios-controls.py').FRAMEWORK_TASK,
                                        '--console=plain'] and
             proof == runner.read_json(state / 'evidence' / proof['id'] / 'receipt.json'), 'Foreign producer diagnostic refused')
        stop = ''
        for stream in ('stdout', 'stderr'):
            path = state / 'evidence' / proof['id'] / ('stop.' + stream + '.log')
            if path.exists():
                stop += evidence.bounded(path, 256 * 1024 * 1024).decode(errors='replace')
        producer = q.receipt_diagnostic(proof, stop)
    return phone_diagnostics.observe(private, logs, ROOT), producer


def app_manifest(path, runner):
    runner.reject_symlinks(path)
    need(path.is_dir() and path.name == 'p2pkit-rpc-phone.app', 'Exact produced application required')
    files = runner.regular_report_files(path, [0])
    need(0 < len(files) <= 4096 and sum(p.stat().st_size for p in files) <= MAX_APP, 'Bounded complete application required')
    result = {}
    for file in files:
        relative = file.relative_to(path).as_posix()
        need(all(part not in ('', '.', '..', '_CodeSignature') for part in Path(relative).parts) and
             'embedded.mobileprovision' not in Path(relative).parts, 'Unsigned artifact cannot export provisioning/signing material')
        before = file.stat()
        need(before.st_uid == os.getuid() and stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             stat.S_IMODE(before.st_mode) & 0o022 == 0, 'Owned regular non-writable application input required')
        result[relative] = runner.file_digest(file)
        after = file.stat()
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode, before.st_uid) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode, after.st_uid), 'Application changed while hashing')
    info = plistlib.loads(evidence.bounded(path / 'Info.plist', 1024 * 1024))
    need(info.get('CFBundleIdentifier') == 'dev.p2pkit.rpc.phonelab' and info.get('CFBundleExecutable') == 'p2pkit-rpc-phone' and
         info.get('MinimumOSVersion') in ('15.0', '15.0.0') and 'p2pkit-rpc-phone' in result,
         'Actual device app identity/minimum OS differs')
    return result


def verify_device_target(raw):
    need(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024, 'Bounded actual Mach-O build commands required')
    text = raw.decode('utf-8')
    need(re.findall(r'(?m)^\s*platform\s+(\w+)\s*$', text) == ['IOS'] and
         re.findall(r'(?m)^\s*minos\s+([0-9.]+)\s*$', text) in (['15.0'], ['15.0.0']),
         'The actual arm64 device binary must target iOS 15, not the simulator or only a plist declaration')


def assess_phone(state, context, outer, runtime, runner, checker, phone):
    work = state / 'work/phone-controls'
    value = runner.read_json(work / 'result.json')
    need(value['schema'] == 1 and type(value['schema']) is int and value['scope'] == phone.SCOPE and
         value['status'] == 'PASS_REQUIRES_OUTER_FINALIZATION' and value['source'] == context['source'] and
         value['scriptSha256'] == runner.file_digest(ROOT / 'scripts/run-rpc-phone-ios-controls.py') and
         value['architecture'] == 'arm64' and value['runtime'] == runtime and not value['errors'] and
         value['simulatorTestsPassed'] is True and value['simulatorShutdown'] is True and
         value['simulatorDeleted'] is True and value['unsignedDeviceAppBuilt'] is True and
         value['physicalInstallable'] is False and value['capacityQualified'] is False,
         'Actual complete phone execution/retirement required')
    need(type(value['runtimeVersion']) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}', value['runtimeVersion']) and
         value['xcodegenSha256'] == runner.file_digest(state / 'tools/xcodegen/bin/xcodegen'), 'Phone tool/runtime changed')
    expected = phone.inventory(ROOT)
    paths = sorted(work.glob('xcresult-tests-*.stdout'))
    need(0 < len(paths) <= 8 and all(p.name == f'xcresult-tests-{i}.stdout' for i, p in enumerate(paths)),
         'Exact actual xcresult summary inventory required')
    actual = phone.assess_xctest([evidence.read(p, 16 * 1024 * 1024) for p in paths], expected)
    need(actual == value['methods'] and b'** TEST SUCCEEDED **' in evidence.bounded(work / 'phone-unit-ui.stdout', phone.LIMIT),
         'Actual tests and retained record differ')
    for name, purpose, count, argv in (
        ('nestedFrameworkProducer', 'rpc-phone-framework-producer', 1, [phone.FRAMEWORK_TASK, '--console=plain']),
        ('nestedProvenance', 'rpc-phone-xcode-provenance', 2, [phone.FRAMEWORK_TASK, '-q', '--console=plain']),
    ):
        rows = value[name]
        need(type(rows) is list and len(rows) == count and len({r['id'] for r in rows}) == count,
             'Missing/repeated nested current-source producer/verifier')
        for row in rows:
            need(set(row) == {'id', 'sha256'} and re.fullmatch('[a-f0-9]{32}', row['id']), 'Invalid nested proof')
            path = state / 'evidence' / row['id'] / 'receipt.json'
            p = runner.read_json(path)
            checker.validate(p, 0, purpose, ROOT, ROOT / 'gradlew', argv)
            need(runner.file_digest(path) == row['sha256'] and p['host'] == 'macos-arm64' and p['kind'] == 'gradle' and
                 p['jobId'] == context['id'] and p['ancestorInvocationIds'] == [outer['id']] and
                 p['gradleHome'] == context['gradleHome'] and
                 p['sourceBefore'] == p['sourceAfter'] == context['source'] and p['stopExitCode'] == 0 and
                 not p['errors'] and not p['ownedSurvivors'] and not p['ownership']['discoveryErrors'],
                 'Nested source/ownership/finalization differs')
    need(value['nestedFrameworkProducer'][0]['sha256'] == value['frameworkProducerReceiptSha256'], 'Producer proof differs')
    app = work / 'device-derived/Build/Products/Debug-iphoneos/p2pkit-rpc-phone.app'
    need(value['unsignedDeviceApp'] == str(app) and evidence.bounded(work / 'device-architectures.stdout').strip() == b'arm64',
         'Actual arm64 device artifact required')
    verify_device_target(evidence.bounded(work / 'device-minimum-os.stdout', 1024 * 1024))
    manifest = app_manifest(app, runner)
    need(manifest == runner.read_json(work / 'unsigned-device-app-manifest.json'), 'Device application changed')
    return dict(simulatorArchitecture='arm64', runtimeVersion=value['runtimeVersion'], unitMethods=len(actual['p2pkit-rpc-phone-tests']),
                uiMethods=len(actual['p2pkit-rpc-phone-uitests']), simulatorShutdown=True, simulatorDeleted=True,
                nestedFrameworkProducers=1, nestedProvenanceChecks=2, deviceArchitecture='arm64', deviceMinimumOs='15.0'), app, manifest


def export_app(app, target, manifest, runner):
    need(not target.exists() and not target.is_symlink() and app_manifest(app, runner) == manifest, 'Fresh unchanged app export required')
    with target.open('xb') as stream:
        os.chmod(target, 0o600)
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in sorted(manifest):
                archive.write(app / name, app.name + '/' + name)
    need(app_manifest(app, runner) == manifest and 0 < target.stat().st_size <= MAX_ARCHIVE, 'Archive input drift/size limit')
    with zipfile.ZipFile(target) as archive:
        need(archive.namelist() == [app.name + '/' + n for n in sorted(manifest)], 'Unexpected archive entry')
        for name, digest in manifest.items():
            need(hashlib.sha256(archive.read(app.name + '/' + name)).hexdigest() == digest, 'Archived bytes changed')
    return dict(bytes=target.stat().st_size, sha256=runner.file_digest(target), files=len(manifest))


def validate_public(value, source, inventory):
    need(type(inventory) is int and inventory > 0, 'Complete actual native control inventory required')
    need(type(value) is dict and set(value) == {'schema', 'scope', 'source', 'result', 'sourceUnchanged', 'nativeControlTests',
         'commands', 'controls', 'artifacts', 'foundationStatus', 'physicalInstallable', 'physicalQualification',
         'mobileCapacityQualification', 'appleMatrixQualification', 'phoneDiagnostics', 'producerDiagnostic'} and
         type(value['schema']) is int and value['schema'] == 2 and
         value['scope'] == SCOPE and value['source'] == source and type(source) is dict and set(source) == {'commit', 'tree'} and
         all(type(v) is str and re.fullmatch('[a-f0-9]{40}', v) for v in source.values()) and
         value['result'] in ('PASS', 'FAIL') and type(value['sourceUnchanged']) is bool and value['foundationStatus'] == 'NOT_READY' and
         all(value[k] is False for k in ('physicalInstallable', 'physicalQualification', 'mobileCapacityQualification', 'appleMatrixQualification')) and
         type(value['nativeControlTests']) is int and value['nativeControlTests'] in (0, inventory), 'Closed unsigned source-bound manifest required')
    rows = value['commands']
    need(type(rows) is list and len(rows) <= len(PURPOSES), 'Bounded exact command inventory required')
    for i, row in enumerate(rows):
        need(type(row) is dict and set(row) == {'purpose', 'exitCode', 'finalizationVerified'} and row['purpose'] == PURPOSES[i] and
             type(row['finalizationVerified']) is bool and (row['exitCode'] is None or type(row['exitCode']) is int and -255 <= row['exitCode'] <= 255) and
             (not row['finalizationVerified'] or row['exitCode'] is not None and row['exitCode'] != 125), 'Invalid native command result')
    if value['phoneDiagnostics'] is not None:
        need(any(r['purpose'] == 'phone-controls' and r['finalizationVerified'] for r in rows), 'Unowned phone observations refused')
        phone_diagnostics.validate(value['phoneDiagnostics'], ROOT)
        if 'bootProcesses' in value['phoneDiagnostics']:
            need(value['phoneDiagnostics']['bootProcesses']['nativeRole'] == 'macos-arm64',
                 'Phone observations must match the independently admitted native ARM role')
    if value['producerDiagnostic'] is not None:
        need(value['phoneDiagnostics'] is not None, 'Producer observation requires its owned phone controller')
        module('ios_handoff_diagnostic_policy', 'run-rpc-qualification.py').validate_diagnostic(value['producerDiagnostic'])
    if value['result'] == 'PASS':
        need(value['sourceUnchanged'] and value['nativeControlTests'] == inventory and len(rows) == len(PURPOSES) and
             all(r['exitCode'] == 0 and r['finalizationVerified'] for r in rows), 'Partial execution cannot produce a handoff')
        controls = value['controls']
        need(type(controls) is dict and set(controls) == {'simulatorArchitecture', 'runtimeVersion', 'unitMethods', 'uiMethods',
             'simulatorShutdown', 'simulatorDeleted', 'nestedFrameworkProducers', 'nestedProvenanceChecks', 'deviceArchitecture', 'deviceMinimumOs'} and
             controls['simulatorArchitecture'] == controls['deviceArchitecture'] == 'arm64' and controls['deviceMinimumOs'] == '15.0' and
             controls['simulatorShutdown'] is True and controls['simulatorDeleted'] is True and
             type(controls['runtimeVersion']) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}', controls['runtimeVersion']) and
             all(type(controls[k]) is int and controls[k] == n for k, n in
                 (('unitMethods', 10), ('uiMethods', 2), ('nestedFrameworkProducers', 1), ('nestedProvenanceChecks', 2))), 'Incomplete phone controls')
        need(type(value['artifacts']) is dict and set(value['artifacts']) == {ARCHIVE}, 'Exact unsigned app archive required')
        row = value['artifacts'][ARCHIVE]
        need(type(row) is dict and set(row) == {'bytes', 'sha256', 'files'} and type(row['bytes']) is int and 0 < row['bytes'] <= MAX_ARCHIVE and
             type(row['files']) is int and 0 < row['files'] <= 4096 and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}', row['sha256']),
             'Bounded content-bound unsigned app required')
    else:
        need(value['artifacts'] == {} and value['controls'] is None, 'Failed app preparation cannot export a partial pass')
    return value


class Job:
    def __init__(self):
        admit(os.environ)
        self.runner = module('ios_handoff_owner', 'run-audit-command.py')
        self.checker = module('ios_handoff_checker', 'check-audit-receipt.py')
        self.q = module('ios_handoff_native_policy', 'run-rpc-qualification.py')
        self.parent = self.runner.absolute_path(os.environ['RPC_QUALIFICATION_PARENT'])
        module('ios_handoff_private', 'run-rpc-capacity-lab.py').private_directory(self.parent)
        need(self.parent != Path(os.environ['RUNNER_TEMP']).resolve(strict=True) and
             self.parent.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve(strict=True)), 'Fresh task-private parent required')
        need(MARKER in self.runner.git(ROOT, 'show', '-s', '--format=%B', 'HEAD').decode() and
             self.runner.git(ROOT, 'rev-parse', '--is-shallow-repository').strip() == b'false' and
             not self.runner.git(ROOT, 'for-each-ref', '--format=%(refname)', 'refs/tags').strip(), 'Explicit full-history no-tags feature source required')
        self.state = self.parent / 'state'
        with (self.parent / 'initialize.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            self.runner.initialize(argparse.Namespace(root=str(ROOT), state=str(self.state), expected_commit=os.environ['GITHUB_SHA'], host='macos-arm64'))
        self.state, self.context = self.runner.context_at(str(self.state))
        need(not self.context['preexistingOutputPaths'], 'No restored product outputs admitted')
        for name in ('private', 'work', 'tools', 'tmp', 'konan', 'android-user'):
            (self.state / name).mkdir(mode=0o700)
        self.private = self.state / 'private'
        os.environ.update(P2PKIT_AUDIT_STATE_DIR=str(self.state), GRADLE_USER_HOME=self.context['gradleHome'],
            KONAN_DATA_DIR=str(self.state / 'konan'), ANDROID_USER_HOME=str(self.state / 'android-user'),
            TMPDIR=str(self.state / 'tmp'), P2PKIT_GRADLE_EXECUTOR=str(ROOT / 'scripts/run-audit-command.py'),
            PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
        for key in list(os.environ):
            if key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN') or key.upper().startswith(
                    ('SIGNING_', 'ORG_GRADLE_PROJECT_SIGNING', 'MAVEN_CENTRAL_', 'SONATYPE_')):
                os.environ.pop(key)
        self.result = dict(schema=1, scope=SCOPE, source=self.context['source'], result='FAIL', commands=[], nativeControlTests=0,
                           runtime=None, sourceUnchanged=False)
        self.unsafe = False
        self.proofs = {}

    def invoke(self, purpose):
        need(not self.unsafe and purpose == PURPOSES[len(self.result['commands'])], 'Exact one-shot ordered native commands required')
        argv = commands(self.state, self.q, self.result['runtime'])[purpose]
        row = dict(purpose=purpose, argv=argv, exitCode=None, verified=False)
        self.result['commands'].append(row)
        print('START ' + purpose, flush=True)
        with (self.private / (purpose + '.driver.log')).open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = self.runner.main(['--cwd', str(ROOT), '--wrapper', str(ROOT / 'gradlew'), '--kind', 'command',
                '--purpose', purpose, '--timeout', str(BOUNDS[purpose]), '--receipt', str(self.private / (purpose + '.json')), '--', *argv])
        row['exitCode'] = code
        try:
            proof = receipt(self.runner, self.checker, self.state, self.context, purpose, argv, code)
            row.update(verified=True, receiptSha256=self.runner.file_digest(self.private / (purpose + '.json')))
        except BaseException:
            self.unsafe = True
            raise
        self.proofs[purpose] = proof
        print('END ' + purpose + ' exit=' + str(code), flush=True)
        need(code == 0, 'Required product failed')
        return proof

    def run(self):
        try:
            proof = self.invoke('native-controls')
            count = self.q.unittest_count(command_output(self.state, proof, 'stderr').decode())
            need(count == self.q.control_inventory('macos-arm64'), 'Complete fresh native controls required')
            self.result['nativeControlTests'] = count
            for purpose in PURPOSES[1:7]:
                self.invoke(purpose)
            verify_toolchain(self.state, self.proofs, self.q)
            base, sdk = Path(os.environ['ANDROID_HOME']).resolve(strict=True), self.state / 'work/sdk'
            sdk.mkdir()
            for name in ('cmdline-tools/latest', 'licenses'):
                need((base / name).is_dir(), 'Installed public SDK tooling/licenses required')
                shutil.copytree(base / name, sdk / name)
            os.environ.pop('ANDROID_SDK_ROOT', None)
            os.environ['ANDROID_HOME'] = str(sdk)
            self.invoke('android-compile-platforms')
            self.invoke('pinned-xcodegen')
            os.environ['PATH'] = str(self.state / 'tools/xcodegen/bin') + os.pathsep + os.environ['PATH']
            r = self.invoke('phone-runtimes')
            self.result['runtime'] = runtime_selection(json.loads(command_output(self.state, r), object_pairs_hook=evidence.unique))
            self.invoke('phone-controls')
            assess_phone(self.state, self.context, self.proofs['phone-controls'], self.result['runtime'], self.runner, self.checker,
                         module('ios_handoff_actual_controls', 'run-rpc-phone-ios-controls.py'))
            self.result['result'] = 'PASS'
        except Exception as error:
            self.result['failureType'] = type(error).__name__
        finally:
            self.result['sourceUnchanged'] = self.runner.source_snapshot(ROOT) == self.context['source']
            if self.unsafe or not self.result['sourceUnchanged']:
                self.result['result'] = 'FAIL'
            self.runner.write_new_json(self.private / 'result.json', self.result)
        return 0 if self.result['result'] == 'PASS' else 1


def collect():
    admit(os.environ)
    runner = module('ios_handoff_collect_owner', 'run-audit-command.py')
    checker = module('ios_handoff_collect_checker', 'check-audit-receipt.py')
    q = module('ios_handoff_collect_policy', 'run-rpc-qualification.py')
    parent = runner.absolute_path(os.environ['RPC_QUALIFICATION_PARENT'])
    module('ios_handoff_collect_private', 'run-rpc-capacity-lab.py').private_directory(parent)
    temporary = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    need(parent != temporary and parent.is_relative_to(temporary), 'Owned collection parent required')
    state, context = runner.context_at(str(parent / 'state'))
    original = runner.read_json(state / 'private/result.json')
    inventory = q.control_inventory('macos-arm64')
    need(original['source'] == context['source'] and context['source']['commit'] == os.environ['GITHUB_SHA'] and
         original['scope'] == SCOPE and original['result'] in ('PASS', 'FAIL') and type(original['commands']) is list and
         len(original['commands']) <= len(PURPOSES), 'Exact original source/result required')
    public = dict(schema=2, scope=SCOPE, source={k: context['source'][k] for k in ('commit', 'tree')}, result='FAIL',
        sourceUnchanged=runner.source_snapshot(ROOT) == context['source'], nativeControlTests=0, commands=[], controls=None,
        artifacts={}, foundationStatus='NOT_READY', physicalInstallable=False, physicalQualification=False,
        mobileCapacityQualification=False, appleMatrixQualification=False, phoneDiagnostics=None, producerDiagnostic=None)
    proofs = {}
    for i, row in enumerate(original['commands']):
        need(type(row) is dict and row['purpose'] == PURPOSES[i] and row['argv'] == commands(state, q, original['runtime'])[row['purpose']],
             'Original exact ordered commands required')
        verified = False
        try:
            proof = receipt(runner, checker, state, context, row['purpose'], row['argv'], row['exitCode'])
            verified = row['verified'] is True and row['receiptSha256'] == runner.file_digest(state / 'private' / (row['purpose'] + '.json'))
            if verified:
                proofs[row['purpose']] = proof
                if row['purpose'] == 'native-controls' and row['exitCode'] == 0:
                    need(q.unittest_count(command_output(state, proof, 'stderr').decode()) == original['nativeControlTests'] == inventory,
                         'Native control count differs')
                    public['nativeControlTests'] = inventory
        except Exception:
            verified = False
        public['commands'].append(dict(purpose=row['purpose'], exitCode=row['exitCode'], finalizationVerified=verified))
    if 'phone-controls' in proofs:
        public['phoneDiagnostics'], public['producerDiagnostic'] = phone_observations(
            state, context, proofs['phone-controls'], original['runtime'], runner, q)
    ready = (original['result'] == 'PASS' and original['sourceUnchanged'] is True and public['sourceUnchanged'] and
             public['nativeControlTests'] == inventory and len(public['commands']) == len(PURPOSES) and
             all(r['exitCode'] == 0 and r['finalizationVerified'] for r in public['commands']))
    validate_public(public, public['source'], inventory)
    staging = parent / 'export-staging'
    staging.mkdir(mode=0o700)
    if ready:
        verify_toolchain(state, proofs, q)
        runtime = runtime_selection(json.loads(command_output(state, proofs['phone-runtimes']), object_pairs_hook=evidence.unique))
        need(runtime == original['runtime'], 'Selected actual runtime differs')
        controls, app, manifest = assess_phone(state, context, proofs['phone-controls'], runtime, runner, checker,
                                             module('ios_handoff_collect_phone', 'run-rpc-phone-ios-controls.py'))
        archive = export_app(app, staging / ARCHIVE, manifest, runner)
        need(runner.source_snapshot(ROOT) == context['source'], 'Source drift during app staging')
        public.update(result='PASS', controls=controls, artifacts={ARCHIVE: archive})
    runner.write_new_json(staging / 'manifest.json', validate_public(public, public['source'], inventory))
    need(not (parent / 'public').exists(), 'Cannot replace an earlier handoff export')
    staging.rename(parent / 'public')
    print('IPHONE HANDOFF ' + public['result'] + '; unsigned, simulator only', flush=True)
    return 0 if public['result'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'collect'))
    parser.add_argument('--owner-authorized-phone-handoff', action='store_true', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    return Job().run() if args.operation == 'run' else collect()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('IPHONE_HANDOFF_ABORTED: ' + type(error).__name__ + '; no qualified package', file=sys.stderr)
        raise SystemExit(1)
