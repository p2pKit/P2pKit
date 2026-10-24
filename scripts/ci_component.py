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
    # Explicit supported CLI candidate; hosted tests must qualify this context.
    'consumers': ('macos-15-intel', 120),
    'macos-shared': ('macos-15-intel', 120),
}
# Explicit focused diagnostics are not release components or aggregate inputs.
# Workflow-call Apple/Android issue diagnostics are intentionally absent here:
# ci.yml dispatches them separately, never through this component executor.
DIAGNOSTICS = {'bundle-diagnostic': ('macos-26', 60), 'jmdns-diagnostic': ('macos-15-intel', 30),
               'published-consumers-diagnostic': ('macos-15-intel', 120),
               'consumers-pom-diagnostic': ('macos-15-intel', 60),
               'apple-keyboard-diagnostic': ('macos-26', 60)}

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
    routes = {**COMPONENTS, **DIAGNOSTICS}
    if not names or len(names) != len(set(names)) or any(x not in routes for x in names) or \
            (any(x in DIAGNOSTICS for x in names) and len(names) != 1):
        raise ValueError('Unknown or duplicate component')
    return {'include': [{'component': x, 'os': routes[x][0], 'minutes': routes[x][1], 'job_minutes': routes[x][1] + 10} for x in names]}


def commands(component):
    py = [sys.executable, '-B']
    bash = ['bash']
    gradle = [str(ROOT / 'gradlew.bat') if os.name == 'nt' else './gradlew', *FLAGS]
    # Retain actual daemon/compiler selection in the existing encrypted command
    # logs. A missing deprecation warning alone does not prove the intended JDK ran.
    if component in ('jvm-windows', 'desktop-windows'):
        gradle.append('--info')
    tests = lambda *paths: [(p, py + ['scripts/tests/' + p, '-v']) for p in paths]
    supervisor = ('supervisor-controls', py + ['scripts/tests/ci-evidence-test.py', '-v', *SUPERVISOR_TESTS])
    if component == 'source':
        return [
            ('wrapper', bash + ['scripts/check-gradle-wrapper.sh']),
            ('layout', bash + ['scripts/tests/check-repository-layout.sh']),
            ('links', bash + ['scripts/tests/check-markdown-links.sh']),
            ('release-metadata', bash + ['scripts/check-release-metadata.sh']),
            ('ios-launcher-controls', bash + ['scripts/tests/run-ios-app-test.sh']),
            *[(name, bash + ['scripts/tests/' + script + '-test.sh']) for name, script in (
                ('release-tag-controls', 'check-release-tag'),
                ('release-identity-controls', 'check-release-identity'),
                ('maven-environment-controls', 'check-maven-release-environment'),
                ('maven-namespace-controls', 'check-maven-namespace-access'),
                ('maven-coordinate-controls', 'check-maven-central-version'),
                ('maven-upload-controls', 'publish-central-portal-bundle'))],
            ('embedded-jmdns-archive-controls', bash + ['scripts/tests/check-embedded-jmdns-aar.sh']),
            ('central-gpg-lifecycle-controls', bash + ['scripts/tests/central-gpg-lifecycle-test.sh']),
            ('workflow-contract', ['ruby', 'scripts/check-modular-ci-policy.rb']),
            ('workflow-syntax', ['actionlint', '-shellcheck=', '-pyflakes=',
                *[str(p.relative_to(ROOT)) for p in sorted((ROOT / '.github/workflows').glob('*.yml'))
                  if not p.name.startswith('audit-')]]),
            ('workflow-controls', ['ruby', 'scripts/tests/check-modular-ci-policy-test.rb']),
            ('kotlin-toolchain-controls', bash + ['scripts/tests/check-kotlin-toolchain-policy-test.sh']),
            ('published-consumer-controls', py + ['scripts/tests/audit-consumer-test.py', '-v',
                                                '-k', 'latest_published', '-k', 'pipeline']),
            ('platform-contract', ['ruby', 'scripts/tests/check-platform-test-policy-test.rb']),
            ('version-encoding', bash + ['scripts/tests/check-application-release-version.sh']),
            *tests('check-rpc-hosted-validation-test.py', 'central-http-test.py', 'ci-component-test.py', 'ci-evidence-test.py', 'ci-qualification-test.py',
                   'apple-issue-validation-test.py', 'run-android-ui-validation-test.py', 'android-legacy-task-preview-test.py',
                   'tcp-nodelay-latency-test.py', 'protocol-ping-latency-test.py', 'run-rpc-qualification-test.py',
                   'run-jmdns-interpreter-diagnostic-test.py', 'run-android-permission-validation-test.py',
                   'swift-jvm-transfer-test.py', 'run-android-art-smoke-test.py',
                   'dependency-update-test.py', 'embedded-jmdns-aar-test.py', 'intel-bonjour-environment-test.py',
                   'central-bundle-evidence-test.py', 'maven-recovery-test.py',
                   'rpc-apple-bonjour-environment-test.py', 'intel-bonjour-advertising-test.py',
                   'application-release-version-test.py', 'sample-artifact-identity-test.py',
                   'package-sample-apps-test.py', 'publish-sample-release-test.py',
                   'release-application-set-test.py', 'run-platform-tests-test.py', 'audit-process-drain-deadline-test.py',
                   'verify-rpc-windows-jdk21-test.py', 'check-rpc-windows-packaging-test.py',
                   'verify-rpc-windows-app-image-test.py', 'verify-rpc-windows-msi-payload-test.py',
                   'inspect-rpc-windows-package-test.py', 'check-rpc-windows-image-runtime-test.py'),
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
        # Explicit stock-administrator development fixture, never standard-user/installed qualification.
        # Existing job supervision/budgets remain; a requested fixture refusal fails rather than skips.
        options = ['-Pp2pkit.rpc.windows.protectedDevelopmentFixture=true'] if component == 'jvm-windows' and \
            (ROOT / 'samples/p2p-sample-rpc').is_dir() else []
        return ([supervisor] if component == 'jvm-windows' else []) + [('jvm-tests', gradle + options + tasks)]
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
        # This packaging option is not installed-provider/lifecycle qualification.
        options = ['-Pp2pkit.rpc.windows.previewAdapter=true'] if component == 'desktop-windows' and \
            (ROOT / 'samples/p2p-sample-rpc').is_dir() else []
        # The shared inbox reconciler has filesystem-specific link semantics.
        # Its process/ownership tests must run on Windows, not merely compile
        # as a dependency of the Desktop application.
        diagnostics = [':p2p-sample-diagnostics:test'] if component == 'desktop-windows' else []
        return ([supervisor] if component == 'desktop-macos' else []) + [('desktop-tests-and-installer', gradle + options + diagnostics + [
            ':p2p-sample-desktop:check', ':p2p-sample-desktop:installDist', ':p2p-sample-desktop-ui:test',
            ':p2p-sample-desktop-ui:checkRuntime', ':p2p-sample-desktop-ui:hotRunArgfile',
            ':p2p-sample-desktop-ui:createDistributable', ':p2p-sample-desktop-ui:' + packaging])] + (
                [('rpc-windows-package-inspection', py + ['scripts/inspect-rpc-windows-package.py']),
                 ('rpc-windows-runtime-readback', py + ['scripts/check-rpc-windows-image-runtime.py'])]
                if options else [])
    if component in ('apple-arm64', 'apple-x64'):
        return [('native-platform-tests', py + ['scripts/run-platform-tests.py',
                 'ios-arm64' if component == 'apple-arm64' else 'ios-x64'])]
    if component == 'macos-shared':
        return [('shared-platform-tests', py + ['scripts/run-platform-tests.py', 'macos-shared'])]
    if component == 'jmdns-diagnostic':
        return [('jmdns-interpreter-diagnostic', py + ['scripts/run-jmdns-interpreter-diagnostic.py']),
                ('jmdns-close-tests', gradle + [':p2p-transport-lan:jvmTest', '--tests',
                 'dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest'])]
    if component == 'bundle-diagnostic':
        return [('signed-bundle-test', bash + ['scripts/tests/build-central-portal-bundle-test.sh'])]
    if component == 'published-consumers-diagnostic':
        return [('published-consumers-diagnostic', ['env',
                 'P2PKIT_CONSUMER_REPOSITORY_URL=https://repo.maven.apache.org/maven2',
                 *bash, 'scripts/check-published-consumers.sh', '--latest-published'])]
    if component == 'consumers-pom-diagnostic':
        return [('published-pom-diagnostic', bash + ['scripts/check-published-consumers.sh', '--pom-diagnostic'])]
    if component == 'apple-keyboard-diagnostic':
        return [('keyboard-readiness-diagnostic', ['env', 'SIM_RUNTIME=com.apple.CoreSimulator.SimRuntime.iOS-26-5',
                 *bash, 'scripts/run-ios-ui-tests.sh', 'run-keyboard-readiness'])]
    if component == 'consumers':
        return [('isolated-consumers', bash + ['scripts/check-published-consumers.sh'])]
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
                ('xcframework', gradle + [':p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance']),
                ('minimum-apple-os', bash + ['scripts/check-xcframework-minimum-os.sh']),
                ('swift-ui', ['env', 'SIM_RUNTIME=com.apple.CoreSimulator.SimRuntime.iOS-26-5',
                              *bash, 'scripts/run-ios-ui-tests.sh'])]
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
    if component in ('apple-arm64', 'apple-x64', 'desktop-macos', 'compatibility', 'consumers', 'macos-shared', *DIAGNOSTICS):
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
        if component in ('consumers', 'published-consumers-diagnostic', 'consumers-pom-diagnostic', 'jmdns-diagnostic', 'macos-shared') and \
                name == 'xcode' and match[1] != '26.3':
            raise RuntimeError('Consumer baseline requires Xcode 26.3')
        with tool.open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
            sha256 = digest.hexdigest()
        result[name] = {'version': match[1], 'executableSha256': sha256}
    Path(target).write_text(json.dumps(result) + '\n')


def execute(component):
    if component not in COMPONENTS and component not in DIAGNOSTICS:
        raise ValueError('Unknown component')
    output = ROOT / 'build/reports/ci-component'
    output.mkdir(parents=True, exist_ok=True)
    tasks = []
    is_gradle = component not in ('source', 'security')
    package = component == 'android' or component.startswith('desktop-')
    kind = 'android' if component == 'android' else 'desktop'
    code = 0
    intel_preparation_started = False
    intel_adapter = [sys.executable, '-I', '-S', '-B', 'scripts/with-intel-bonjour-advertising.py']

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
        # The immutable remote consumer requires a new/empty borrowed work
        # directory. gradlew --version populates its future GRADLE_USER_HOME,
        # so record the same real tool identities after that consumer has run.
        deferred_tools = component == 'published-consumers-diagnostic'
        if not deferred_tools:
            record_tools(component)
        destination = str(Path(os.environ['RUNNER_TEMP']) / 'p2pkit-sample-apps') if package else None
        if package:
            run_task('prepare-' + kind, [sys.executable, '-B', 'scripts/package-sample-apps.py', 'prepare',
                                        '--kind', kind, '--output', destination])
        if component == 'apple-x64':
            intel_preparation_started = True
            run_task('intel-advertising-prepare', intel_adapter + ['prepare'], 150)
        for name, argv in commands(component):
            if code:
                break
            run_task(name, argv)
        if deferred_tools:
            record_tools(component)
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
        try:
            if is_gradle and not any(t['task'] == 'gradle-stop' for t in tasks):
                run_task('gradle-stop', [str(ROOT / 'gradlew.bat') if os.name == 'nt' else './gradlew', '--stop'], 90)
        finally:
            try:
                if intel_preparation_started:
                    # Restore after product AND Gradle stop, including preparation
                    # failure. The adapter refuses incomplete privileged commands;
                    # neither missing state nor a failed restore becomes PASS.
                    run_task('intel-advertising-restore', intel_adapter + ['restore'], 150)
            finally:
                (output / (component + '.json')).write_text(json.dumps({'component': component, 'tasks': tasks,
                                                                       'exitCode': code}, indent=2) + '\n')
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', nargs='?', choices=[*COMPONENTS, *DIAGNOSTICS])
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
