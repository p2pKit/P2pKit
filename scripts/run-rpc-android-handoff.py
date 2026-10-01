#!/usr/bin/env python3
"""Source-bound debug APK handoff after the existing supplemental API24 controls.

This is NOT the maintained API37/24/25 ART gate, physical-device or capacity
qualification. No KVM policy change, production signing, publication, restored
outputs, raw evidence export or process-ownership exception is allowed.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_capacity_evidence as evidence
import rpc_product_diagnostics as diagnostics

REF = 'refs/heads/work/rpc-lan-20260927-054728-8b1b11da'
MARKER = '[rpc-android-handoff]'
SCOPE = 'DEBUG_APK_SUPPLEMENTAL_API24_NOT_MAINTAINED_ART_PHYSICAL_CAPACITY_OR_RELEASE'
PURPOSES = ('native-controls', 'jdk17', 'jdk21', 'android-sdk', 'android-apk-producer', 'supplemental-api24')
TASKS = (':p2p-sample-android:assembleDebug', ':p2p-sample-android:assembleDebugAndroidTest')
PACKAGES = ('platforms;android-36', 'platforms;android-37.0', 'platform-tools', 'emulator',
            'system-images;android-24;default;x86_64')
APKS = {
    'p2pkit-rpc-android-debug.apk': 'samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk',
    'p2pkit-rpc-android-debug-androidTest.apk':
        'samples/p2p-sample-android/build/outputs/apk/androidTest/debug/p2p-sample-android-debug-androidTest.apk',
}
BOUNDS = dict(zip(PURPOSES, (1800, 45, 45, 900, 7200, 1800)))


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
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64' and os.getuid() == os.geteuid() != 0,
         'Actual nonroot Linux host required')
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and env.get('RPC_ANDROID_HANDOFF_REQUESTED') == 'true' and
         re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')) and
         Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT, 'Explicit source-bound feature request required')


def receipt(runner, checker, state, context, purpose, argv, code):
    need(purpose in PURPOSES and type(code) is int, 'Unknown native invocation')
    need(argv == commands(state)[purpose], 'Only the exact APK preparation commands are admitted')
    alias = state / 'private' / (purpose + '.json')
    value = runner.read_json(alias)
    checker.validate(value, code, purpose, ROOT, ROOT / 'gradlew', argv)
    need(value['jobId'] == context['id'] and value['sourceBefore'] == value['sourceAfter'] == context['source'] and
         value['kind'] == ('gradle' if purpose == 'android-apk-producer' else 'command') and
         value['host'] == 'linux-x64' and value['gradleHome'] == context['gradleHome'] and
         value['ancestorInvocationIds'] == [] and not value['errors'] and not value['ownedSurvivors'] and
         not value['ownership']['discoveryErrors'] and value['stopExitCode'] == 0 and
         value == runner.read_json(state / 'evidence' / value['id'] / 'receipt.json'), 'Native finalization unproven')
    return value


def commands(state):
    sdk = state / 'work/sdk'
    result = {
        'native-controls': [sys.executable, 'scripts/tests/run-audit-command-test.py', '--expected-host', 'linux-x64',
                            '--evidence-dir', str(state / 'evidence/native-controls')],
        'android-sdk': [str(sdk / 'cmdline-tools/latest/bin/sdkmanager'), '--sdk_root=' + str(sdk), *PACKAGES],
        'android-apk-producer': [*TASKS, '--console=plain', '--warning-mode=fail', '--stacktrace'],
        'supplemental-api24': [sys.executable, str(ROOT / 'scripts/run-rpc-android-controls.py'),
            '--owner-authorized-software-emulator', '--root', str(ROOT), '--sdk', str(sdk),
            '--producer-receipt', str(state / 'private/android-apk-producer.json'),
            '--directory', str(state / 'work/api24-controls')],
    }
    for major, key in (('17', 'JAVA_HOME'), ('21', 'P2PKIT_AUDIT_JDK21')):
        result['jdk' + major] = [str(Path(os.environ[key]).resolve(strict=True) / 'bin/java'),
                                '-XshowSettings:properties', '-version']
    return result


def package_revision(text):
    need(type(text) is str and len(text) <= 65536, 'Bounded SDK metadata required')
    revisions = re.findall(r'(?m)^Pkg\.Revision[^\S\n]*=[^\S\n]*(.*)$', text)
    need(len(revisions) == 1 and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}', revisions[0].strip()),
         'Exact SDK package revision missing')
    return revisions[0].strip()


def assess_controls(value, context, producer_digest, app_digest, test_digest, phone):
    need(type(value) is dict and value['source'] == context['source'] and value['status'] == 'PASS' and
         value['scope'] == phone.SCOPE and value['producerReceiptSha256'] == producer_digest and
         value['scriptSha256'] == evidence.file_hash(ROOT / 'scripts/run-rpc-android-controls.py') and
         value['appSha256'] == app_digest and value['testApkSha256'] == test_digest and
         value['booted'] is True and value['controlsPassed'] is True and value['naturalCleanup'] is True and
         value['errors'] == [] and value['capacityQualified'] is False and value['acceleration'] == 'off' and
         type(value['api']) is int and value['api'] == 24 and type(value['cores']) is int and value['cores'] == 1 and
         type(value['bootSeconds']) in (int, float) and math.isfinite(value['bootSeconds']) and 0 < value['bootSeconds'] < 600,
         'Actual source-bound API24 execution and cleanup required')
    fields = value['instrumentation']
    need(type(fields) is dict and len(fields) == 16 and all(type(k) is str and type(v) is str and
         len(k) <= 64 and len(v) <= 256 and '\n' not in v and '\r' not in v for k, v in fields.items()),
         'Exact bounded instrumentation fields required')
    token = fields.get('rpcToken')
    need(type(token) is str and re.fullmatch('[a-f0-9]{32}', token), 'Actual instrumentation token required')
    # Reuse the existing exact eight-control parser, not a new permissive count.
    raw = ''.join('INSTRUMENTATION_RESULT: ' + k + '=' + v + '\n' for k, v in fields.items())
    phone.assess_instrumentation(raw + 'INSTRUMENTATION_CODE: -1\n', token)
    return dict(api=24, abi='x86_64', vm='Dalvik', acceleration='off', booted=True,
        bootSeconds=value['bootSeconds'], controlsPassed=len(phone.CONTROL_NAMES), naturalCleanup=True,
        imageRevision=package_revision(value['imageProperties']),
        emulatorRevision=package_revision(value['emulatorProperties']))


def validate_public(value, source, required_controls):
    """One closed public shape; neither private values nor partial passes escape."""
    need(type(required_controls) is int and required_controls > 0, 'Actual native inventory required')
    need(type(value) is dict and set(value) == {'schema', 'scope', 'source', 'result', 'sourceUnchanged',
         'foundationStatus', 'physicalQualification', 'mobileCapacityQualification', 'maintainedArtQualification',
         'nativeControlTests', 'commands', 'controls', 'artifacts', 'productDiagnostics'} and
         type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and
         value['source'] == source and type(source) is dict and set(source) == {'commit', 'tree'} and
         all(type(v) is str and re.fullmatch('[a-f0-9]{40}', v) for v in source.values()) and
         value['result'] in ('PASS', 'FAIL') and type(value['sourceUnchanged']) is bool and
         value['foundationStatus'] == 'NOT_READY' and value['physicalQualification'] is False and
         value['mobileCapacityQualification'] is False and value['maintainedArtQualification'] is False and
         type(value['nativeControlTests']) is int and value['nativeControlTests'] in (0, required_controls),
         'Closed non-release source-bound manifest required')
    rows = value['commands']
    need(type(rows) is list and len(rows) <= len(PURPOSES), 'Bounded command inventory required')
    for index, row in enumerate(rows):
        need(type(row) is dict and set(row) == {'purpose', 'exitCode', 'finalizationVerified'} and
             row['purpose'] == PURPOSES[index] and type(row['finalizationVerified']) is bool and
             (row['exitCode'] is None or type(row['exitCode']) is int and -255 <= row['exitCode'] <= 255) and
             (not row['finalizationVerified'] or row['exitCode'] is not None and row['exitCode'] != 125),
             'Unrecognized, private or inconsistent command result')
    diagnostics.validate(value['productDiagnostics'], ROOT, PURPOSES)
    if value['result'] == 'PASS':
        need(value['sourceUnchanged'] and value['nativeControlTests'] == required_controls and
             len(rows) == len(PURPOSES) and all(r['exitCode'] == 0 and r['finalizationVerified'] for r in rows),
             'Incomplete native execution cannot produce APKs')
        controls = value['controls']
        need(type(controls) is dict and set(controls) == {'api', 'abi', 'vm', 'acceleration', 'booted',
             'bootSeconds', 'controlsPassed', 'naturalCleanup', 'imageRevision', 'emulatorRevision'} and
             type(controls['api']) is int and controls['api'] == 24 and controls['abi'] == 'x86_64' and
             controls['vm'] == 'Dalvik' and controls['acceleration'] == 'off' and controls['booted'] is True and
             controls['naturalCleanup'] is True and type(controls['controlsPassed']) is int and
             controls['controlsPassed'] == 8 and type(controls['bootSeconds']) in (int, float) and
             math.isfinite(controls['bootSeconds']) and 0 < controls['bootSeconds'] < 600 and
             all(type(controls[k]) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}', controls[k])
                 for k in ('imageRevision', 'emulatorRevision')), 'Actual supplemental controls required')
        need(type(value['artifacts']) is dict and set(value['artifacts']) == set(APKS), 'Both exact APKs required')
        for row in value['artifacts'].values():
            need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and
                 0 < row['bytes'] <= 128 * 1024 * 1024 and type(row['sha256']) is str and
                 re.fullmatch('[a-f0-9]{64}', row['sha256']), 'Bounded content-bound APK metadata required')
    else:
        need(value['artifacts'] == {} and value['controls'] is None, 'Failed run cannot export a partial APK pass')
    return value


def apk_metadata(path, runner):
    runner.reject_symlinks(path)
    def identity(value):
        return value.st_dev, value.st_ino, value.st_uid, value.st_mode, value.st_size, value.st_mtime_ns, value.st_nlink
    # APKs have an explicit 128-MiB bound; the JSON/report reader deliberately
    # retains its independent 8-MiB limit. Stream the already-open owned inode
    # instead of both rejecting normal APKs and allocating their full contents.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
             0 < before.st_size <= 128 * 1024 * 1024 and stat.S_IMODE(before.st_mode) & 0o022 == 0,
             'Owned bounded regular APK required')
        digest, total = hashlib.sha256(), 0
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            while chunk := stream.read(65536):
                total += len(chunk)
                need(total <= before.st_size, 'Growing APK refused')
                digest.update(chunk)
        after = os.fstat(descriptor)
        need(total == before.st_size and identity(before) == identity(after) == identity(path.lstat()),
             'APK changed while hashing')
    finally:
        os.close(descriptor)
    return dict(bytes=after.st_size, sha256=digest.hexdigest())


def export_apk(source, target, expected, runner):
    """Stage privately; a failed hash/copy is never placed on an upload path."""
    runner.reject_symlinks(source)
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as src, target.open('xb') as dst:
        before = os.fstat(src.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
             before.st_size == expected['bytes'] <= 128 * 1024 * 1024, 'Only the tested APK may be exported')
        digest, total = hashlib.sha256(), 0
        while chunk := src.read(65536):
            total += len(chunk)
            need(total <= expected['bytes'], 'Growing APK refused')
            digest.update(chunk)
            dst.write(chunk)
        after = os.fstat(src.fileno())
        need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and
             total == expected['bytes'] and digest.hexdigest() == expected['sha256'], 'APK export changed identity/content')
    need(apk_metadata(target, runner) == expected, 'Export does not match tested APK')


class Job:
    def __init__(self):
        admit(os.environ)
        self.runner = module('android_handoff_executor', 'run-audit-command.py')
        self.checker = module('android_handoff_checker', 'check-audit-receipt.py')
        self.q = module('android_handoff_control_inventory', 'run-rpc-qualification.py')
        self.phone = module('android_handoff_controls', 'run-rpc-android-controls.py')
        self.parent = self.runner.absolute_path(os.environ['RPC_ANDROID_HANDOFF_PARENT'])
        module('android_handoff_private_policy', 'run-rpc-capacity-lab.py').private_directory(self.parent)
        need(self.parent.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve(strict=True)), 'Fresh private parent required')
        need(self.runner.git(ROOT, 'rev-parse', '--is-shallow-repository').strip() == b'false' and
             not self.runner.git(ROOT, 'for-each-ref', '--format=%(refname)', 'refs/tags').strip() and
             MARKER in self.runner.git(ROOT, 'show', '-s', '--format=%B', 'HEAD').decode(), 'Full untagged marked source required')
        self.state = self.parent / 'state'
        with (self.parent / 'initialize.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            self.runner.initialize(argparse.Namespace(root=str(ROOT), state=str(self.state),
                expected_commit=os.environ['GITHUB_SHA'], host='linux-x64'))
        self.state, self.context = self.runner.context_at(str(self.state))
        need(self.context['source']['status'] == '' and not self.context['preexistingOutputPaths'],
             'Dirty source or restored/preexisting products refused')
        for name in ('private', 'work', 'tmp', 'konan', 'android-user'):
            (self.state / name).mkdir(mode=0o700)
        self.private = self.state / 'private'
        os.environ.update(P2PKIT_AUDIT_STATE_DIR=str(self.state), GRADLE_USER_HOME=self.context['gradleHome'],
            KONAN_DATA_DIR=str(self.state / 'konan'), ANDROID_USER_HOME=str(self.state / 'android-user'),
            TMPDIR=str(self.state / 'tmp'), P2PKIT_GRADLE_EXECUTOR=str(ROOT / 'scripts/run-audit-command.py'))
        for key in list(os.environ):
            if key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN') or key.upper().startswith(
                    ('SIGNING_', 'ORG_GRADLE_PROJECT_SIGNING', 'MAVEN_CENTRAL_', 'SONATYPE_')):
                os.environ.pop(key)
        self.result = dict(schema=1, scope=SCOPE, source=self.context['source'], result='FAIL', commands=[],
            nativeControlTests=0, sourceUnchanged=False, controls=None, artifacts={}, productDiagnostics={})
        self.unsafe = False

    def output(self, proof, stream='stdout'):
        return evidence.bounded(self.state / 'evidence' / proof['id'] / ('product.' + stream + '.log'), 64 * 1024 * 1024)

    def invoke(self, purpose, argv, timeout, kind='command'):
        need(not self.unsafe and purpose in PURPOSES and purpose not in [r['purpose'] for r in self.result['commands']],
             'Repeated or unowned product work refused')
        need(argv == commands(self.state)[purpose] and timeout == BOUNDS[purpose] and
             kind == ('gradle' if purpose == 'android-apk-producer' else 'command'), 'Exact bounded command required')
        row = dict(purpose=purpose, argv=argv, exitCode=None, verified=False)
        self.result['commands'].append(row)
        print('START ' + purpose, flush=True)
        alias = self.private / (purpose + '.json')
        with (self.private / (purpose + '.driver.log')).open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = self.runner.main(['--cwd', str(ROOT), '--wrapper', str(ROOT / 'gradlew'), '--kind', kind,
                '--purpose', purpose, '--timeout', str(timeout), '--receipt', str(alias), '--', *argv])
        row['exitCode'] = code
        try:
            proof = receipt(self.runner, self.checker, self.state, self.context, purpose, argv, code)
            row.update(verified=True, receiptSha256=self.runner.file_digest(alias))
        except BaseException:
            self.unsafe = True
            raise
        if purpose == 'android-apk-producer':
            self.result['productDiagnostics'] = diagnostics.validate({'build': {purpose: {
                stream: diagnostics.build_observation(ROOT, self.output(proof, stream)) for stream in ('stdout', 'stderr')}}},
                ROOT, PURPOSES)
        print('END ' + purpose + ' exit=' + str(code), flush=True)
        need(code == 0, 'Product command failed')
        return proof

    def run(self):
        try:
            proof = self.invoke('native-controls', [sys.executable, 'scripts/tests/run-audit-command-test.py',
                '--expected-host', 'linux-x64', '--evidence-dir', str(self.state / 'evidence/native-controls')], 1800)
            count = self.q.unittest_count(self.output(proof, 'stderr').decode())
            need(count == self.q.control_inventory('linux-x64'), 'Complete actual native inventory required')
            self.result['nativeControlTests'] = count
            for major, key in (('17', 'JAVA_HOME'), ('21', 'P2PKIT_AUDIT_JDK21')):
                proof = self.invoke('jdk' + major, [str(Path(os.environ[key]).resolve(strict=True) / 'bin/java'),
                    '-XshowSettings:properties', '-version'], 45)
                raw = self.output(proof, 'stderr').decode()
                need(re.search(r'(?m)^\s*java\.specification\.version = ' + major + r'\s*$', raw) and
                     re.search(r'(?m)^\s*os\.arch = amd64\s*$', raw), 'Actual selected native JDK required')
            base = Path(os.environ['ANDROID_HOME']).resolve(strict=True)
            sdk = self.state / 'work/sdk'
            sdk.mkdir()
            for name in ('cmdline-tools/latest', 'licenses'):
                need((base / name).is_dir(), 'Installed public SDK tooling/licenses required')
                shutil.copytree(base / name, sdk / name)
            os.environ.pop('ANDROID_SDK_ROOT', None)
            os.environ['ANDROID_HOME'] = str(sdk)
            self.invoke('android-sdk', [str(sdk / 'cmdline-tools/latest/bin/sdkmanager'), '--sdk_root=' + str(sdk), *PACKAGES], 900)
            self.invoke('android-apk-producer', [*TASKS, '--console=plain', '--warning-mode=fail', '--stacktrace'], 7200, 'gradle')
            self.invoke('supplemental-api24', [sys.executable, str(ROOT / 'scripts/run-rpc-android-controls.py'),
                '--owner-authorized-software-emulator', '--root', str(ROOT), '--sdk', str(sdk),
                '--producer-receipt', str(self.private / 'android-apk-producer.json'),
                '--directory', str(self.state / 'work/api24-controls')], 1800)
            self.result['artifacts'] = {name: apk_metadata(ROOT / relative, self.runner) for name, relative in APKS.items()}
            values = list(self.result['artifacts'].values())
            self.result['controls'] = assess_controls(self.runner.read_json(self.state / 'work/api24-controls/result.json'),
                self.context, self.runner.file_digest(self.private / 'android-apk-producer.json'),
                values[0]['sha256'], values[1]['sha256'], self.phone)
            self.result['result'] = 'PASS'
        except Exception as error:
            # Never publish arbitrary exception text or raw build/device logs.
            self.result['failureType'] = type(error).__name__
        finally:
            self.result['sourceUnchanged'] = self.runner.source_snapshot(ROOT) == self.context['source']
            if self.unsafe or not self.result['sourceUnchanged']:
                self.result['result'] = 'FAIL'
            self.runner.write_new_json(self.private / 'result.json', self.result)
        return 0 if self.result['result'] == 'PASS' else 1


def collect():
    admit(os.environ)
    runner = module('android_handoff_collector', 'run-audit-command.py')
    checker = module('android_handoff_collect_checker', 'check-audit-receipt.py')
    q = module('android_handoff_collect_inventory', 'run-rpc-qualification.py')
    phone = module('android_handoff_collect_controls', 'run-rpc-android-controls.py')
    parent = runner.absolute_path(os.environ['RPC_ANDROID_HANDOFF_PARENT'])
    module('android_handoff_collect_private', 'run-rpc-capacity-lab.py').private_directory(parent)
    temporary = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    need(parent != temporary and parent.is_relative_to(temporary), 'Owned collection parent required')
    state, context = runner.context_at(str(parent / 'state'))
    original = runner.read_json(state / 'private/result.json')
    inventory = q.control_inventory('linux-x64')
    need(original['source'] == context['source'] and original['scope'] == SCOPE and
         type(original['schema']) is int and original['schema'] == 1 and original['result'] in ('PASS', 'FAIL') and
         type(original['sourceUnchanged']) is bool and type(original['nativeControlTests']) is int and
         original['nativeControlTests'] in (0, inventory) and type(original['commands']) is list and
         len(original['commands']) <= len(PURPOSES), 'Source/result mismatch')
    public = dict(schema=1, scope=SCOPE, source={k: context['source'][k] for k in ('commit', 'tree')},
        result='FAIL', sourceUnchanged=runner.source_snapshot(ROOT) == context['source'],
        foundationStatus='NOT_READY', physicalQualification=False, mobileCapacityQualification=False,
        maintainedArtQualification=False, nativeControlTests=0, commands=[], controls=None, artifacts={},
        productDiagnostics=diagnostics.validate(original['productDiagnostics'], ROOT, PURPOSES))
    for index, row in enumerate(original['commands']):
        need(type(row) is dict and row['purpose'] == PURPOSES[index] and type(row['verified']) is bool and
             (row['exitCode'] is None or type(row['exitCode']) is int and -255 <= row['exitCode'] <= 255),
             'Unknown/repeated/private command result')
        verified = False
        try:
            proof = receipt(runner, checker, state, context, row['purpose'], row['argv'], row['exitCode'])
            verified = row['verified'] is True and row['receiptSha256'] == runner.file_digest(state / 'private' / (row['purpose'] + '.json'))
            if row['purpose'] == 'native-controls' and verified and row['exitCode'] == 0:
                raw = evidence.bounded(state / 'evidence' / proof['id'] / 'product.stderr.log')
                need(q.unittest_count(raw.decode()) == original['nativeControlTests'] == inventory,
                     'Native inventory changed')
                public['nativeControlTests'] = inventory
        except Exception:
            verified = False
        public['commands'].append(dict(purpose=row['purpose'], exitCode=row['exitCode'], finalizationVerified=verified))
    ready = (original['result'] == 'PASS' and original['sourceUnchanged'] is True and public['sourceUnchanged'] and
             public['nativeControlTests'] == inventory and
             tuple(r['purpose'] for r in public['commands']) == PURPOSES and
             all(r['exitCode'] == 0 and r['finalizationVerified'] for r in public['commands']))
    # Atomically expose only complete, rechecked exports. No partial binary can
    # be uploaded even if the collector fails after copying its first file.
    validate_public(public, public['source'], inventory)
    directory = parent / 'export-staging'
    directory.mkdir(mode=0o700)
    if ready:
        files = {name: apk_metadata(ROOT / relative, runner) for name, relative in APKS.items()}
        need(files == original['artifacts'], 'Produced/tested APKs changed before export')
        values = list(files.values())
        controls = assess_controls(runner.read_json(state / 'work/api24-controls/result.json'), context,
            runner.file_digest(state / 'private/android-apk-producer.json'), values[0]['sha256'], values[1]['sha256'], phone)
        need(controls == original['controls'], 'Actual control result changed')
        for name, relative in APKS.items():
            export_apk(ROOT / relative, directory / name, files[name], runner)
        need(runner.source_snapshot(ROOT) == context['source'], 'Source changed during APK staging')
        public.update(result='PASS', artifacts=files, controls=controls)
    runner.write_new_json(directory / 'manifest.json', validate_public(public, public['source'], inventory))
    need(not (parent / 'public').exists(), 'Cannot replace an earlier handoff export')
    directory.rename(parent / 'public')
    print('ANDROID HANDOFF ' + public['result'] + '; supplemental API24 only', flush=True)
    return 0 if public['result'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run', 'collect'))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        return Job().run() if args.operation == 'run' else collect()
    except Exception:
        print('ANDROID HANDOFF failed closed; inspect private source-bound evidence', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
