#!/usr/bin/env python3
"""Small, independently runnable CI components. No bootstrap or publication.

Hosted callers wrap this driver with ci_evidence.py. Commands retain ordinary
exit status; stdout/stderr are private evidence, not public Actions diagnostics.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = {
    'source': ('ubuntu-24.04', 30),
    'dependencies': ('ubuntu-24.04', 45),
    'jvm-linux': ('ubuntu-24.04', 60),
    'jvm-windows': ('windows-2025', 60),
    'android': ('ubuntu-24.04', 75),
    'apple-arm64': ('macos-26', 150),
    'apple-x64': ('macos-15-intel', 120),
    'desktop-linux': ('ubuntu-24.04', 75),
    'desktop-windows': ('windows-2025', 75),
    'desktop-macos': ('macos-26', 75),
    'security': ('ubuntu-24.04', 30),
    'compatibility': ('macos-26', 180),
}
FLAGS = ['--no-daemon', '--no-build-cache', '--no-configuration-cache',
         '--dependency-verification', 'strict', '--max-workers=2', '--no-parallel', '--console=plain']
MODULES = ['p2p-core', 'p2p-transport-lan', 'p2p-network-provisioning-android',
           'p2p-network-provisioning-desktop']


# Genuine small native-process cases on each additional host; no old audit
# executor/custody campaign or product/RPC-provider qualification is implied.
SUPERVISOR_TESTS = (
    'EvidenceTests.test_real_success_captures_both_private_streams_and_known_close',
    'EvidenceTests.test_real_nonzero_is_preserved_and_not_relabelled_pass',
    'EvidenceTests.test_real_timeout_retires_original_child',
    'EvidenceTests.test_real_leader_exit_does_not_leave_child_writing',
    'EvidenceTests.test_real_output_limit_is_enforced_during_capture',
    'EvidenceTests.test_actual_scope_failed_postspawn_still_closes_original_pipes',
    'EvidenceTests.test_real_cancellation_is_not_pass',
)


def matrix(selected):
    names = list(COMPONENTS) if selected == 'all' else selected.split(',')
    if not names or len(names) != len(set(names)) or any(x not in COMPONENTS for x in names):
        raise ValueError('Unknown or duplicate component')
    return {'include': [{'component': x, 'os': COMPONENTS[x][0], 'minutes': COMPONENTS[x][1], 'job_minutes': COMPONENTS[x][1] + 10} for x in names]}


def commands(component):
    py = [sys.executable, '-B']
    bash = ['bash']
    gradle = [str(ROOT / 'gradlew.bat') if os.name == 'nt' else './gradlew', *FLAGS]
    tests = lambda *paths: [(p, py + ['scripts/tests/' + p, '-v']) for p in paths]
    supervisor = ('supervisor-controls', py + ['scripts/tests/ci-evidence-test.py', '-v', *SUPERVISOR_TESTS])
    if component == 'source':
        return [
            ('wrapper', bash + ['scripts/check-gradle-wrapper.sh']),
            ('layout', bash + ['scripts/tests/check-repository-layout.sh']),
            ('links', bash + ['scripts/tests/check-markdown-links.sh']),
            ('release-metadata', bash + ['scripts/check-release-metadata.sh']),
            *[(name, bash + ['scripts/tests/' + script + '-test.sh']) for name, script in (
                ('release-tag-controls', 'check-release-tag'),
                ('release-identity-controls', 'check-release-identity'),
                ('maven-environment-controls', 'check-maven-release-environment'),
                ('maven-namespace-controls', 'check-maven-namespace-access'),
                ('maven-coordinate-controls', 'check-maven-central-version'),
                ('maven-upload-controls', 'publish-central-portal-bundle'))],
            ('workflow-contract', ['ruby', 'scripts/check-modular-ci-policy.rb']),
            ('workflow-syntax', ['actionlint', '-shellcheck=', '-pyflakes=',
                *[str(p.relative_to(ROOT)) for p in sorted((ROOT / '.github/workflows').glob('*.yml'))
                  if not p.name.startswith('audit-')]]),
            ('workflow-controls', ['ruby', 'scripts/tests/check-modular-ci-policy-test.rb']),
            ('platform-contract', ['ruby', 'scripts/tests/check-platform-test-policy-test.rb']),
            ('version-encoding', bash + ['scripts/tests/check-application-release-version.sh']),
            *tests('ci-component-test.py', 'ci-evidence-test.py', 'ci-qualification-test.py',
                   'dependency-update-test.py', 'embedded-jmdns-aar-test.py',
                   'application-release-version-test.py', 'sample-artifact-identity-test.py',
                   'package-sample-apps-test.py', 'publish-sample-release-test.py',
                   'release-application-set-test.py', 'run-platform-tests-test.py'),
        ]
    if component == 'dependencies':
        return [('integrity-policy', bash + ['scripts/check-dependency-verification.sh']),
                ('lock-coverage', bash + ['scripts/tests/check-osv-lockfile-coverage.sh']),
                ('lock-writer-policy', bash + ['scripts/tests/check-lock-write-policy-test.sh']),
                *tests('check-freemarker-floor-test.py', 'check-jackson-floor-test.py'),
                ('build-plugin-floors', gradle + [':verifyBuildPluginSecurityFloors', ':checkPublicConstantAbiPolicy'])]
    if component.startswith('jvm-'):
        tasks = [':p2p-core:jvmTest', ':p2p-transport-lan:jvmTest', ':p2p-network-provisioning-desktop:test']
        if (ROOT / 'library/p2p-rpc').is_dir():
            tasks.append(':p2p-rpc:jvmTest')
        if (ROOT / 'samples/p2p-sample-rpc').is_dir():
            tasks.append(':p2p-sample-rpc:jvmTest')
        return ([supervisor] if component == 'jvm-windows' else []) + [('jvm-tests', gradle + tasks)]
    if component == 'android':
        tasks = [':p2p-core:testAndroidHostTest', ':p2p-transport-lan:testAndroidHostTest',
                 ':p2p-network-provisioning-android:testAndroidHostTest', ':p2p-sample-android:testDebugUnitTest',
                 ':p2p-sample-android:assembleDebug']
        if (ROOT / 'library/p2p-rpc').is_dir():
            tasks += [':p2p-rpc:testAndroidHostTest']
        if (ROOT / 'samples/p2p-sample-rpc').is_dir():
            tasks.append(':p2p-sample-rpc:testAndroidHostTest')
        return [('android-tests-and-apk', gradle + tasks)]
    if component.startswith('desktop-'):
        packaging = {'desktop-linux': 'packageDeb', 'desktop-windows': 'packageMsi',
                     'desktop-macos': 'packageDmg'}[component]
        # Stage the existing experimental JDK21 adapter in the normal MSI.
        # This build option does not enable the deliberately disabled provider.
        options = ['-Pp2pkit.rpc.windows.previewAdapter=true'] if component == 'desktop-windows' and \
            (ROOT / 'samples/p2p-sample-rpc').is_dir() else []
        return ([supervisor] if component == 'desktop-macos' else []) + [('desktop-tests-and-installer', gradle + options + [
            ':p2p-sample-desktop:check', ':p2p-sample-desktop:installDist', ':p2p-sample-desktop-ui:test',
            ':p2p-sample-desktop-ui:checkRuntime', ':p2p-sample-desktop-ui:hotRunArgfile',
            ':p2p-sample-desktop-ui:createDistributable', ':p2p-sample-desktop-ui:' + packaging])]
    if component.startswith('apple-'):
        return [('native-platform-tests', py + ['scripts/run-platform-tests.py',
                 'full' if component == 'apple-arm64' else 'ios-x64'])]
    if component == 'compatibility':
        modules = MODULES + (['p2p-rpc'] if (ROOT / 'library/p2p-rpc').is_dir() else [])
        abi = [':' + m + ':checkKotlinAbi' for m in modules]
        abi += [':' + m + ':checkAndroidAbi' for m in modules if m != 'p2p-network-provisioning-desktop']
        return [('abi-graph', bash + ['scripts/check-android-abi-guard.sh']),
                ('api-abi', gradle + abi),
                ('documentation', gradle + [':' + m + ':dokkaGeneratePublicationHtml' for m in modules]),
                ('sbom', bash + ['scripts/check-sbom.sh']),
                ('publication-shape', bash + ['scripts/check-publish-artifacts.sh']),
                ('signed-bundle-test', bash + ['scripts/tests/build-central-portal-bundle-test.sh']),
                ('isolated-consumers', bash + ['scripts/check-published-consumers.sh']),
                ('xcframework', gradle + [':p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance']),
                ('minimum-apple-os', bash + ['scripts/check-xcframework-minimum-os.sh']),
                ('swift-ui', bash + ['scripts/run-ios-ui-tests.sh'])]
    if component == 'security':
        # The existing pinned scanner wrapper preserves findings, errors and SARIF.
        return [('osv-lock-coverage', bash + ['scripts/tests/check-osv-lockfile-coverage.sh']),
                ('osv-scan', py + ['scripts/run-osv-scan.py', os.environ.get('CI_OSV_BINARY', ''),
                                 str(ROOT / 'build/reports/osv')])]
    raise ValueError('Unknown component')


def record_tools(component):
    """Read actual tool versions; only parsed public versions/hashes leave logs."""
    target = os.environ.get('CI_EVIDENCE_TOOLS_FILE')
    if not target:
        return
    result = {}
    probes = [('java', shutil.which('java'), ['-version'], r'version "([^"\n]+)"'),
              ('gpg', shutil.which('gpg'), ['--version'], r'gpg \(GnuPG\) ([0-9.]+)')]
    if component not in ('source', 'security'):
        probes.append(('gradle', str(ROOT / ('gradlew.bat' if os.name == 'nt' else 'gradlew')),
                       [*FLAGS, '--version'], r'(?m)^Gradle ([0-9A-Za-z.+-]+)$'))
    if component in ('apple-arm64', 'apple-x64', 'desktop-macos', 'compatibility'):
        probes.append(('xcode', shutil.which('xcodebuild'), ['-version'], r'(?m)^Xcode ([0-9.]+)$'))
    for name, executable, args, pattern in probes:
        if executable is None:
            raise RuntimeError('Required tool unavailable: ' + name)
        tool = Path(executable).resolve(strict=True)
        completed = subprocess.run([str(tool), *args], cwd=ROOT, check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        # Native Windows tools emit CRLF; normalize line endings only, retaining
        # the same exact version grammar and required-tool identity checks.
        version_output = completed.stdout.decode('utf-8', errors='replace').replace('\r\n', '\n')
        match = re.search(pattern, version_output)
        if match is None or not re.fullmatch(r'[A-Za-z0-9 ._+()/-]{1,120}', match[1]):
            raise RuntimeError('Cannot identify required tool: ' + name)
        with tool.open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
            sha256 = digest.hexdigest()
        result[name] = {'version': match[1], 'executableSha256': sha256}
    Path(target).write_text(json.dumps(result) + '\n')


def execute(component):
    if component not in COMPONENTS:
        raise ValueError('Unknown component')
    output = ROOT / 'build/reports/ci-component'
    output.mkdir(parents=True, exist_ok=True)
    tasks = []
    is_gradle = component not in ('source', 'security')
    package = component == 'android' or component.startswith('desktop-')
    kind = 'android' if component == 'android' else 'desktop'
    code = 0

    def run_task(name, argv, timeout=None):
        nonlocal code
        try:
            completed = subprocess.run(argv, cwd=ROOT, check=False, timeout=timeout)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
        except (OSError, ValueError):
            exit_code = 125
        tasks.append({'task': name, 'exitCode': exit_code})
        if exit_code and code == 0:
            code = exit_code
        return exit_code

    try:
        record_tools(component)
        destination = str(Path(os.environ['RUNNER_TEMP']) / 'p2pkit-sample-apps') if package else None
        if package:
            run_task('prepare-' + kind, [sys.executable, '-B', 'scripts/package-sample-apps.py', 'prepare',
                                        '--kind', kind, '--output', destination])
        for name, argv in commands(component):
            if code:
                break
            run_task(name, argv)
        if is_gradle:
            run_task('gradle-stop', [str(ROOT / 'gradlew.bat') if os.name == 'nt' else './gradlew', '--stop'], 90)
        if code == 0 and package:
            run_task('inspect-' + kind, [sys.executable, '-B', 'scripts/package-sample-apps.py', 'package',
                                        '--kind', kind, '--output', destination])
    except Exception:
        # Raw exception goes to the private outer capture, never an Actions annotation.
        if code == 0:
            code = 125
        tasks.append({'task': 'component-setup', 'exitCode': code})
        raise
    finally:
        # Cleanup is attempted even when a setup/launch failed. Preserve the
        # original task failure; uncertain retirement is never converted to PASS.
        if is_gradle and not any(t['task'] == 'gradle-stop' for t in tasks):
            run_task('gradle-stop', [str(ROOT / 'gradlew.bat') if os.name == 'nt' else './gradlew', '--stop'], 90)
        (output / (component + '.json')).write_text(json.dumps({'component': component, 'tasks': tasks,
                                                               'exitCode': code}, indent=2) + '\n')
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', nargs='?', choices=list(COMPONENTS))
    parser.add_argument('--matrix')
    parser.add_argument('--list-commands', action='store_true')
    args = parser.parse_args()
    if args.matrix:
        print(json.dumps(matrix(args.matrix), separators=(',', ':')))
        return 0
    if args.list_commands:
        print(json.dumps(commands(args.component), indent=2))
        return 0
    return execute(args.component)


if __name__ == '__main__':
    sys.exit(main())
