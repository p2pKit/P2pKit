#!/usr/bin/env python3
"""Offline live-helper and maintained modular RPC routing controls.

No Java/network/Gradle or installed-Windows qualification. The removed inline
Desktop full/build-only experiment is not a contract for its modular replacement.
"""

import copy
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rpc_hosted", ROOT / "scripts/run-rpc-hosted-validation.py")
hosted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosted)




def check_release_rpc_controls(source):
    """Tripwire for the known straight-line preflight block, not a general shell parser."""
    lines = source.splitlines()
    start, end = 'cd "$ROOT"', "python3 scripts/run-platform-tests.py full"
    required = "python3 -I -B -S scripts/tests/check-rpc-hosted-validation-test.py"
    if lines.count(start) != 1 or lines.count(end) != 1 or lines.index(start) >= lines.index(end):
        raise ValueError("Missing or ambiguous release preflight boundaries")
    block = lines[lines.index(start) + 1:lines.index(end)]
    script = r"scripts/[A-Za-z0-9_./-]+"
    # Extend only reviewed non-evaluating command forms. Trailing -v -f is unittest's
    # verbose/fail-fast pair; it does not make the required RPC invocation optional.
    simple = re.compile(rf"(?:python3(?: -[IBS])* {script}(?: -v -f)?|(?:(?:ruby|node|bash) )?{script})")
    for line in block:
        if line.strip() and not line.lstrip().startswith("#") and not simple.fullmatch(line):
            raise ValueError("Release preflight is not the reviewed straight-line check block")
    if block.count(required) != 1:
        raise ValueError("RPC offline controls must execute exactly once in release preflight")




def check_windows_policy_units(source):
    """Fixed-source recipe tripwire; actual process/parser controls live in the companion PowerShell test."""
    expected = ["policy", "stage", "lock", "delete", "child", "role", "candidate", "rename", "sync",
                "replace", "write", "record_delete", "namespace", "publication_probe", "creation_result", "token_sid"]
    selections = re.findall(r"\$tests = @\((.*?)\)\n", source, re.DOTALL)
    if len(selections) != 1 or re.findall(r"'([^']+)'", selections[0]) != expected:
        raise ValueError("Exactly the 16 reviewed memory-only native test files must be selected")
    for forbidden in ("profile_win32.c", "profile_jni.c", "profile_win32_smoke_test", "LoadLibrary",
                      "Start-Process", ".ReadToEnd", "/DNDEBUG", "Get-ChildItem", "$env:ComSpec"):
        if forbidden in source:
            raise ValueError("Unexpected native source/launcher/output substitution: " + forbidden)
    for required in ("WINDOWS_NATIVE_POLICY_UNIT_NOT_STORAGE_OR_RELEASE", "/std:c11 /W4 /WX", "/UNDEBUG",
                     '"$native\\profile_policy.c" "$testSource"', '"tests/profile_$($_)_test.c"', "/MACHINE:X64",
                     "profileNativeExecution = 'NOT_PERFORMED'", "nativeStorageExecution = 'NOT_PERFORMED'",
                     "smokeSupervisorQualification = 'NOT_PERFORMED'", "sourceBlobIds = $blobs", "sourceEol = @(",
                     "$row.outputExceeded = $true", "$counts[$index] -gt 65536", "[byte[]]::new(4096)",
                     "$clock.ElapsedMilliseconds -ge $Milliseconds", "$row.elapsedMs -lt $Milliseconds",
                     "$process.Kill($true)", "$process.WaitForExit(5000)", "$process.Dispose()",
                     "[IO.FileMode]::CreateNew", "$row.passed -and $finalized -and $row.processExitObserved",
                     "$entry.executable.sha256", "$receipt.tests.Count -ne 16",
                     "$receipt.sourceUnchanged = $true", "$receipt.result = 'PASS'",
                     "if ($LASTEXITCODE -ne 0 -or ($ExpectedLines -ge 0", "-ExpectedLines 19",
                     "Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0",
                     "Join-Path ([Environment]::SystemDirectory) 'cmd.exe'", "'compile' 60000", "'test' 10000"):
        if required not in source:
            raise ValueError("Missing strict Windows policy-unit control: " + required)
    for variable in ("CL", "_CL_", "LINK", "_LINK_", "ERRORLEVEL", "INCLUDE", "LIB", "LIBPATH"):
        if f'set "{variable}="' not in source:
            raise ValueError("Ambient native build override was not cleared: " + variable)


def check_windows_static_msi(source):
    """Source tripwire for a reviewed, ordinary builder-only extraction command, not a sandbox."""
    for value in ("$env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012'",
                  "$env:GITHUB_JOB -cne 'rpc-windows'", "$env:RUNNER_ARCH -cne 'X64'",
                  "$imageRecord.tree -cne $tree[0]", "$payload.tree -cne $tree[0]",
                  "$imageRecord.source -cne $env:GITHUB_SHA", "$payload.source -cne $env:GITHUB_SHA",
                  "'WINDOWS_APP_IMAGE_BYTES_NOT_INSTALLED_OR_RUNTIME_QUALIFIED'",
                  "'MSI_STATIC_COMPONENT_EQUALITY_NOT_INSTALLED_RUNTIME'",
                  "$msis[0].Length -ne $imageRecord.msi.bytes", "$imageRecord.msi.sha256",
                  "'p2pkit-windows-msi-static-extraction'", "'Static extraction output must be fresh'",
                  "$previousTemporary = $env:WIX_TEMP", "$env:WIX_TEMP = $temporary",
                  "finally {\n    $env:WIX_TEMP = $previousTemporary", "'dark' 60000\n",
                  "if (-not $unchangedTool)", "if (-not $result.passed)",
                  "./scripts/verify-rpc-windows-msi-payload.py", "$payload.comparedFiles.Count -ne $aliases.Count",
                  "'msi-loader-adapter.jar.bytes'",
                  "[IO.File]::Copy($original, $copy, $false)", "$member.sha256",
                  "if ($LASTEXITCODE -ne 0 -or $afterStatus.Count)"):
        if value not in source:
            raise ValueError("Missing static MSI boundary: " + value)
    for value in ("msiexec", "Start-Process", "System.load", "LoadLibrary", "package-rpc-preview",
                  "Invoke-WebRequest", "Set-Acl", "ReadToEnd"):
        if value in source:
            raise ValueError("Unexpected static MSI action: " + value)


def workflow(source):
    # Use the same safe YAML parser as the repository's maintained Ruby policies;
    # no extra Python package or general shell evaluator is introduced.
    result = subprocess.run(['ruby', '-ryaml', '-rjson', '-e',
        'puts JSON.generate(YAML.safe_load(STDIN.read, aliases: false))'],
        input=source, text=True, capture_output=True, timeout=5)
    if result.returncode:
        raise ValueError('Invalid workflow YAML')
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError('Workflow must be a mapping')
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_main_rpc_change_coverage(source):
    document = workflow(source)
    triggers = document.get('on', document.get('true', {}))
    require('pull_request' in triggers and triggers['pull_request'] in (None, {}),
            'Main RPC coverage must not filter pull-request paths')
    require(triggers.get('push', {}).get('branches') == ['main'], 'Main push coverage missing')
    require(document['jobs']['component']['uses'] == './.github/workflows/ci-component.yml',
            'Main must retain the same-source component worker')


def check_desktop_dispatch(source):
    document = workflow(source)
    triggers = document.get('on', document.get('true', {}))
    require(set(triggers) == {'workflow_dispatch'}, 'Desktop wrapper must remain explicit dispatch')
    inputs = triggers['workflow_dispatch']['inputs']
    require(inputs == {'component': {'type': 'choice', 'default': 'all',
            'options': ['all', 'desktop-linux', 'desktop-windows', 'desktop-macos']}},
            'Desktop selector must retain all three maintained components')
    require(document['permissions'] == {'contents': 'read', 'actions': 'read'},
            'Desktop dispatch cannot acquire write credentials')
    jobs = document['jobs']
    require(set(jobs) == {'plan', 'component'}, 'Desktop dispatch cannot add a qualification or inline native job')
    plan = jobs['plan']
    require('if' not in plan and not plan.get('continue-on-error'), 'Desktop planning cannot be suppressed')
    checkout, select = plan['steps']
    require(re.fullmatch(r'actions/checkout@[0-9a-f]{40}', checkout['uses']) and
            checkout['with'] == {'persist-credentials': False}, 'Same-event checkout cannot persist credentials or substitute refs')
    expected = ('if [[ "$COMPONENT" == all ]]; then COMPONENT=desktop-linux,desktop-windows,desktop-macos; fi\n'
                'echo "matrix=$(python3 -B scripts/ci_component.py --matrix "$COMPONENT")" >> "$GITHUB_OUTPUT"\n')
    require(select == {'id': 'components', 'env': {'COMPONENT': '${{ inputs.component }}'}, 'run': expected},
            'Desktop selection must execute the maintained component matrix')
    require(jobs['component'] == {
        'name': '${{ matrix.component }}', 'needs': 'plan',
        'strategy': {'fail-fast': False, 'matrix': '${{ fromJSON(needs.plan.outputs.matrix) }}'},
        'uses': './.github/workflows/ci-component.yml',
        'with': {'component': '${{ matrix.component }}', 'runner': '${{ matrix.os }}',
                 'minutes': '${{ matrix.minutes }}', 'job_minutes': '${{ matrix.job_minutes }}'},
    }, 'Desktop must run the same-source worker without skipped peers or ignored failures')


def component_commands():
    spec = importlib.util.spec_from_file_location('rpc_modular_component', ROOT / 'scripts/ci_component.py')
    component = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(component)
    return {name: component.commands(name) for name in ('jvm-windows', 'desktop-windows')}


def check_windows_modular_commands(commands):
    # Actual command arrays, not echoed YAML task names. The admin development
    # fixture and built MSI are not standard-user/installed provider acceptance.
    wrapper = str(ROOT / 'gradlew.bat') if os.name == 'nt' else './gradlew'
    flags = ['--no-daemon', '--no-build-cache', '--no-configuration-cache',
             '--dependency-verification', 'strict', '--max-workers=2', '--no-parallel', '--console=plain']
    jvm = [argv for task, argv in commands['jvm-windows'] if task == 'jvm-tests']
    require(jvm == [[wrapper, *flags, '-Pp2pkit.rpc.windows.protectedDevelopmentFixture=true',
        ':p2p-core:jvmTest', ':p2p-transport-lan:jvmTest', ':p2p-network-provisioning-desktop:test',
        ':p2p-rpc:jvmTest', ':p2p-sample-rpc:jvmTest']], 'Windows JVM suite must remain complete, strict and unfiltered')
    require(commands['desktop-windows'] == [
        ('desktop-tests-and-installer', [wrapper, *flags, '-Pp2pkit.rpc.windows.previewAdapter=true',
            ':p2p-sample-desktop:check', ':p2p-sample-desktop:installDist', ':p2p-sample-desktop-ui:test',
            ':p2p-sample-desktop-ui:checkRuntime', ':p2p-sample-desktop-ui:hotRunArgfile',
            ':p2p-sample-desktop-ui:createDistributable', ':p2p-sample-desktop-ui:packageMsi']),
        ('rpc-windows-package-inspection', [sys.executable, '-B', 'scripts/inspect-rpc-windows-package.py']),
        ('rpc-windows-runtime-readback', [sys.executable, '-B', 'scripts/check-rpc-windows-image-runtime.py']),
    ], 'Windows must build the normal MSI, then inspect its image/payload and runtime without ignored failures')


class HostedValidationTest(unittest.TestCase):
    def test_maintained_main_covers_rpc_changes_without_desktop_path_filters(self):
        check_main_rpc_change_coverage((ROOT / '.github/workflows/ci.yml').read_text())

    def test_main_rpc_coverage_rejects_missing_or_filtered_pull_request_trigger(self):
        source = (ROOT / '.github/workflows/ci.yml').read_text()
        for replacement in ('', '  pull_request:\n    paths: [docs/**]\n',
                            '  pull_request:\n    paths-ignore: [library/p2p-rpc/**]\n'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                check_main_rpc_change_coverage(source.replace('  pull_request:\n', replacement, 1))
        with self.assertRaises(ValueError):
            check_main_rpc_change_coverage(source.replace('branches: [main]', 'branches: [other]', 1))

    def test_manual_desktop_dispatch_uses_all_three_same_source_components(self):
        check_desktop_dispatch((ROOT / '.github/workflows/desktop-cross-host.yml').read_text())

    def test_desktop_dispatch_rejects_omissions_ref_substitution_credentials_and_false_qualification(self):
        source = (ROOT / '.github/workflows/desktop-cross-host.yml').read_text()
        mutations = (
            ('default: all', 'default: desktop-windows'),
            ('options: [all, desktop-linux, desktop-windows, desktop-macos]', 'options: [desktop-windows]'),
            ('contents: read', 'contents: write'),
            ('persist-credentials: false', 'persist-credentials: true'),
            ('persist-credentials: false', 'persist-credentials: false\n          ref: another'),
            ('fail-fast: false', 'fail-fast: true'),
            ('    needs: plan', '    needs: plan\n    continue-on-error: true'),
            ('    name: ${{ matrix.component }}', '    name: ${{ matrix.component }}\n    if: false'),
            ('uses: ./.github/workflows/ci-component.yml', 'uses: other/repo/.github/workflows/ci-component.yml@main'),
            ('COMPONENT=desktop-linux,desktop-windows,desktop-macos', 'COMPONENT=desktop-windows'),
        )
        for before, after in mutations:
            self.assertIn(before, source)
            with self.subTest(mutation=before), self.assertRaises(ValueError):
                check_desktop_dispatch(source.replace(before, after, 1))
        with self.assertRaises(ValueError):
            check_desktop_dispatch(source + '\n  qualify:\n    runs-on: ubuntu-latest\n    steps: []\n')

    def test_windows_modular_jvm_msi_image_and_runtime_commands_remain_complete(self):
        check_windows_modular_commands(component_commands())

    def test_windows_modular_jvm_controls_reject_selectors_exclusions_and_bypasses(self):
        original = component_commands()
        for suffix in (['--tests', 'OneTest'], ['-x', ':p2p-sample-rpc:jvmTest'],
                       ['--exclude-task', ':p2p-rpc:jvmTest'], ['--init-script', 'narrow.gradle'],
                       ['--dry-run'], ['||', 'true']):
            commands = copy.deepcopy(original)
            next(argv for task, argv in commands['jvm-windows'] if task == 'jvm-tests').extend(suffix)
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                check_windows_modular_commands(commands)
        for task in (':p2p-rpc:jvmTest', ':p2p-sample-rpc:jvmTest'):
            commands = copy.deepcopy(original)
            next(argv for label, argv in commands['jvm-windows'] if label == 'jvm-tests').remove(task)
            with self.assertRaises(ValueError):
                check_windows_modular_commands(commands)

    def test_windows_modular_packaging_cannot_skip_inspection_reorder_or_use_alternate_producer(self):
        original = component_commands()
        for index in range(3):
            commands = copy.deepcopy(original)
            del commands['desktop-windows'][index]
            with self.subTest(index=index), self.assertRaises(ValueError):
                check_windows_modular_commands(commands)
        commands = copy.deepcopy(original)
        commands['desktop-windows'].reverse()
        with self.assertRaises(ValueError):
            check_windows_modular_commands(commands)
        for before, after in ((':p2p-sample-desktop-ui:packageMsi', ':p2p-sample-rpc:packageMsi'),
                              ('strict', 'off'), (':p2p-sample-desktop-ui:test', '--dry-run')):
            commands = copy.deepcopy(original)
            argv = commands['desktop-windows'][0][1]
            argv[argv.index(before)] = after
            with self.subTest(mutation=before), self.assertRaises(ValueError):
                check_windows_modular_commands(commands)


    def test_static_msi_wrapper_stays_source_bound_and_nonexecuting(self):
        path = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-msi-payload.ps1"
        check_windows_static_msi(path.read_text())

    def test_static_msi_wrapper_rejects_binding_tool_and_copy_weakening(self):
        path = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-msi-payload.ps1"
        source = path.read_text()
        for before, after in (("$payload.tree -cne $tree[0]", "$false"),
                              ("$imageRecord.source -cne $env:GITHUB_SHA", "$false"),
                              ("'dark' 60000", "'dark' 600000"),
                              ("if (-not $unchangedTool)", "if ($false)"),
                              ("$payload.comparedFiles.Count -ne $aliases.Count", "$false"),
                              ("'msi-loader-adapter.jar.bytes'", "'missing.jar.bytes'"),
                              ("[IO.File]::Copy($original, $copy, $false)",
                               "[IO.File]::Copy($original, $copy, $true)")):
            with self.subTest(mutation=before), self.assertRaises(ValueError):
                self.assertIn(before, source)
                check_windows_static_msi(source.replace(before, after))




    def test_windows_policy_units_are_fixed_memory_only_asserting_and_bounded(self):
        path = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-policy-tests.ps1"
        check_windows_policy_units(path.read_text())

    def test_windows_policy_units_reject_missing_tests_storage_source_and_weakened_execution(self):
        path = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-policy-tests.ps1"
        source = path.read_text()
        mutations = (("'token_sid'", "'policy'"), ("/UNDEBUG", "/DNDEBUG"), ("/W4 /WX", "/W4"),
                     ('"$native\\profile_policy.c" "$testSource"', '"$native\\profile_win32.c" "$testSource"'),
                     ('set "_CL_="', ""), ('set "ERRORLEVEL="', ""),
                     ("$counts[$index] -gt 65536", "$false"), ("$row.elapsedMs -lt $Milliseconds", "$true"),
                     ("$process.WaitForExit(5000)", "$process.WaitForExit()"),
                     ("$receipt.tests.Count -ne 16", "$receipt.tests.Count -ne 1"),
                     ("nativeStorageExecution = 'NOT_PERFORMED'", "nativeStorageExecution = 'PASS'"),
                     ("if ($LASTEXITCODE -ne 0 -or ($ExpectedLines -ge 0", "if (($ExpectedLines -ge 0"))
        for before, after in mutations:
            with self.subTest(mutation=before), self.assertRaises(ValueError):
                self.assertIn(before, source)
                check_windows_policy_units(source.replace(before, after))






    def test_complete_release_gate_runs_rpc_offline_controls(self):
        check_release_rpc_controls((ROOT / "scripts/run-release-gate.sh").read_text())

    def test_release_gate_rpc_registration_rejects_bypass_shapes(self):
        command = "python3 -I -B -S scripts/tests/check-rpc-hosted-validation-test.py"
        source = 'cd "$ROOT"\n' + command + '\npython3 scripts/run-platform-tests.py full\n'
        check_release_rpc_controls(source)
        replacements = ("", "# " + command, command.replace(" -I", ""), command + " || true",
                        command + "\n" + command, "if false; then\n" + command + "\nfi")
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    check_release_rpc_controls(source.replace(command, replacement, 1))

    def test_release_preflight_accepts_reviewed_foundation_command_forms(self):
        # Forms observed at Foundation 67baa27e; not a copy of its release pipeline.
        lines = (
            "ruby scripts/tests/check-heavy-job-queue-policy-test.rb",
            "python3 -I -B -S scripts/tests/hosted-dependency-update-test.py -v -f",
            "python3 -I -B -S scripts/tests/hosted-dependency-update-context-test.py -v -f",
            "python3 -I -B -S scripts/tests/hosted-dependency-update-context-startup-observation-test.py -v -f",
            "node scripts/tests/hosted-ordinary-cache-provider-action-test.cjs",
            "python3 -I -B scripts/tests/application-release-version-test.py",
            "bash scripts/tests/check-application-release-version.sh",
        )
        command = "python3 -I -B -S scripts/tests/check-rpc-hosted-validation-test.py"
        source = 'cd "$ROOT"\n' + "\n".join((*lines, command)) + '\npython3 scripts/run-platform-tests.py full\n'
        check_release_rpc_controls(source)

    def test_release_preflight_rejects_unreviewed_interpreters_arguments_and_shell_operators(self):
        command = "python3 -I -B -S scripts/tests/check-rpc-hosted-validation-test.py"
        prefix = 'cd "$ROOT"\n' + command + "\n"
        suffix = "\npython3 scripts/run-platform-tests.py full\n"
        rejected = (
            "python3 -O scripts/tests/example.py",
            "python3 -c scripts/tests/example.py",
            "python3 scripts/tests/example.py --unknown",
            "python3 scripts/tests/example.py -v -f || true",
            "python3 scripts/tests/example.py -v -f; true",
            "python3 scripts/tests/example.py -v -f &",
            "bash -c scripts/tests/example.sh",
            "bash scripts/tests/example.sh ignored-argument",
            "node --eval scripts/tests/example.cjs",
            "node scripts/tests/example.cjs > ignored-output",
            "sh scripts/tests/example.sh",
            "env python3 scripts/tests/example.py",
            "$(python3 scripts/tests/example.py)",
        )
        for line in rejected:
            with self.subTest(line=line), self.assertRaises(ValueError):
                check_release_rpc_controls(prefix + line + suffix)

    def test_foundation_command_forms_cannot_replace_the_required_rpc_command(self):
        command = "python3 -I -B -S scripts/tests/check-rpc-hosted-validation-test.py"
        for replacement in ("", "# " + command,
                            command + " -v -f", command.replace("python3", "bash", 1)):
            source = ('cd "$ROOT"\nnode scripts/tests/foundation.cjs\n'
                      'bash scripts/tests/foundation.sh\npython3 -I -B -S scripts/tests/foundation.py -v -f\n'
                      + replacement + '\npython3 scripts/run-platform-tests.py full\n')
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                check_release_rpc_controls(source)




    def test_complete_writer_is_not_replaced_by_a_partial_graph(self):
        commands = hosted.generator_commands()
        self.assertEqual([row[0] for row in commands], ["apple-abi", "complete-lock-writer"])
        self.assertEqual(commands[1][1], ["resolveAndLockAll", "--write-locks",
                                        "--write-verification-metadata", "sha256"])
        self.assertIn("--no-configure-on-demand", hosted.FLAGS)
        self.assertIn("--rerun-tasks", hosted.FLAGS)
        self.assertEqual(hosted.FLAGS[hosted.FLAGS.index("--dependency-verification") + 1], "strict")
        self.assertNotIn("-x", hosted.FLAGS)
        self.assertTrue(all("publish" not in str(row).lower() for row in commands))

    def test_generated_allowlist_excludes_keys_source_and_binaries(self):
        for path in ("keys.json", "gradle.properties", "library/p2p-rpc/src/Test.kt",
                     "library/p2p-rpc/build/rpc.jar", "AGENTS.md", "CLAUDE.md", "RPC_MODULE_PLAN.md"):
            self.assertNotIn(path, hosted.GENERATED)
        self.assertIn("library/p2p-rpc/gradle.lockfile", hosted.GENERATED)
        self.assertIn("samples/p2p-sample-rpc/gradle.lockfile", hosted.GENERATED)
        self.assertEqual(len(hosted.LOCKS), 14)

    def test_lock_inventory_matches_every_tracked_lock_including_both_rpc_modules(self):
        # Count alone would accept a stale Foundation set padded with duplicate/untracked entries.
        tracked = subprocess.check_output(
            ["git", "--no-optional-locks", "ls-files", "-z", "*gradle.lockfile"], cwd=ROOT
        ).decode("utf-8").rstrip("\0").split("\0")
        self.assertEqual(len(hosted.LOCKS), len(set(hosted.LOCKS)))
        self.assertEqual(sorted(hosted.LOCKS), sorted(tracked))
        self.assertIn("library/p2p-rpc/gradle.lockfile", tracked)
        self.assertIn("samples/p2p-sample-rpc/gradle.lockfile", tracked)
        self.assertIn("samples/p2p-sample-desktop-ui/gradle.lockfile", tracked)
        for path in tracked:
            self.assertIn(path, hosted.GENERATED)
            self.assertTrue((ROOT / path).is_file())
            self.assertFalse((ROOT / path).is_symlink())

    def test_no_offline_execution_can_be_mistaken_for_hosted_authorization(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(hosted.HostedValidationError, "authorized disposable"):
                hosted.paths()

    def test_unrelated_ref_is_rejected_before_any_build(self):
        with patch.object(hosted.platform, "system", return_value="Darwin"), patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_REF": "refs/heads/main",
        }):
            with self.assertRaisesRegex(hosted.HostedValidationError, "feature ref"):
                hosted.paths()

    def test_diagnostics_exclude_fixture_payloads_and_assertion_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.log"
            path.write_text("e: file:///public/Example.kt:12:7 Unresolved reference 'example'.\n"
                            "> Task :p2p-rpc:compileKotlinIosArm64 FAILED\n"
                            "> Could not resolve org.example:public-library:1.0.\n"
                            "invitation=synthetic-private-value\n"
                            "Expected payload <synthetic-private-value>\n"
                            "> Could not resolve secret: synthetic-private-value\n"
                            "BUILD FAILED in 4s\n")
            output = hosted.safe_diagnostics(path)
            self.assertEqual(len(output), 4)
            self.assertNotIn("synthetic-private-value", "\n".join(output))

    def test_overlong_line_is_not_admitted_by_a_matching_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.log"
            path.write_text("x" * 8193 + "e: file:///public/Example.kt:12 synthetic-private-value\n"
                            "BUILD FAILED in 4s\n")
            self.assertEqual(hosted.safe_diagnostics(path), ["BUILD FAILED in 4s"])

    def test_test_report_redacts_output_messages_and_stacktraces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "library/example/build/test-results/iosTest/TEST-example.xml"
            path.parent.mkdir(parents=True)
            path.write_text('<testsuite tests="2" failures="1" errors="0" skipped="0">'
                            '<testcase classname="example.Test" name="failure">'
                            '<failure message="secret">private trace</failure>'
                            '<system-out>private payload</system-out></testcase>'
                            '<testcase name="pass"/><system-err>private stderr</system-err></testsuite>')
            result = hosted.test_summary(root)
            self.assertEqual(result[0]["tests"], 2)
            self.assertEqual(result[0]["failedCases"], [{"classname": "example.Test", "name": "failure",
                                                       "type": "OTHER", "locations": []}])
            self.assertNotIn("private", json.dumps(result))
            self.assertNotIn("secret", json.dumps(result))

    def test_failure_details_allow_only_known_types_and_public_in_range_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "library/example/src/commonTest/kotlin/PublicTest.kt"
            source.parent.mkdir(parents=True)
            source.write_text("package example\nclass PublicTest\n// fixture\n")
            failure = hosted.ET.fromstring(
                '<failure type="java.lang.AssertionError" message="synthetic-secret">'
                'private-path/synthetic-secret/PublicTest.kt:2:4\n'
                'private-path/SecretFile.kt:1\nPublicTest.kt:9999999\n'
                'PublicTest.kt:0\nPublicTest.kt:4\nprivate message</failure>')
            details = hosted.failure_details(failure, hosted.source_locations(root))
            self.assertEqual(details, {"type": "java.lang.AssertionError", "locations": [
                {"source": source.relative_to(root).as_posix(), "line": 2}]})
            failure.attrib["type"] = "synthetic.secret.Exception"
            self.assertEqual(hosted.failure_details(failure, {})["type"], "OTHER")
            self.assertNotIn("secret", json.dumps(details))
            self.assertNotIn("private", json.dumps(details))

    def test_fixture_markers_reject_addresses_paths_dynamic_errors_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "library/p2p-transport-lan/build/reports/jmdns-close/run-fixture/control-123.log"
            path.parent.mkdir(parents=True)
            accepted = ["FAIL mode=control", "phase=fixture_rescue_begin mode=control",
                        "startup firstSendFailureClass=java.net.NoRouteToHostException "
                        "firstSendDestinationIpv4Mdns=true",
                        "startup routeFlag=BLACKHOLE present=false",
                        "startup interfaceSnapshot=BEFORE_WAIT selectedKnown=true hostKnown=true socketKnown=true "
                        "selectedHostMatch=true selectedSocketMatch=true hostSocketMatch=true"]
            secret = "synthetic-private-value"
            rejected = ["FAIL mode=" + secret, "phase=" + secret + " mode=control",
                        "startup firstSendFailureClass=" + secret + " firstSendDestinationIpv4Mdns=true",
                        "startup frameRole=send_failure frame=" + secret,
                        "startup routeFlag=" + secret + " present=false", "path=/private/" + secret,
                        "startup address=192.168.1.1", "startup selectedInterface=en0",
                        "Exception in thread \"main\" java.lang.AssertionError: " + secret]
            path.write_text("\n".join([*accepted, *(line + " " + secret for line in accepted), *rejected,
                                       'Exception in thread "main" java.lang.AssertionError: host_not_announced']))
            summary = hosted.fixture_summary(root)
            self.assertEqual(summary, [{"mode": "control", "markers": [*accepted,
                                                                         "assertionCode=host_not_announced"]}])
            for excluded in (secret, "192.168.1.1", "en0", "/private/"):
                self.assertNotIn(excluded, json.dumps(summary))

    def test_diagnostic_mode_never_substitutes_for_full_writer(self):
        commands = hosted.diagnostic_commands()
        self.assertEqual([command[0] for command in commands], ["diagnostic-jmdns", "diagnostic-ios-lan"])
        self.assertEqual(commands[0][1], [":p2p-transport-lan:jvmTest", "--tests",
                                         "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest"])
        self.assertEqual(commands[1][1], [":p2p-transport-lan:iosSimulatorArm64Test"])
        self.assertNotIn("--write-locks", str(commands))
        self.assertNotIn("resolveAndLockAll", str(commands))
        self.assertNotIn("publish", str(commands).lower())

    def test_native_correction_does_not_retry_unchanged_jmdns_or_write_inputs(self):
        commands = hosted.diagnostic_commands("diagnose-native")
        self.assertEqual(commands, [hosted.diagnostic_commands()[1]])
        self.assertNotIn("jvmTest", str(commands))
        self.assertNotIn("--write-", str(commands))
        with self.assertRaises(hosted.HostedValidationError):
            hosted.diagnostic_commands("unknown")

    def test_workflow_allocates_only_explicit_feature_work_without_shared_secrets(self):
        source = (ROOT / ".github/workflows/rpc-feature-validation.yml").read_text()
        for required in (hosted.REF, "github.event_name == 'workflow_dispatch'", "[rpc-native]",
                         "[rpc-diagnose]", "[rpc-generate]", "cancel-in-progress: false",
                         "persist-credentials: false", "contents: read", "fetch-depth: 1",
                         "git fetch --no-tags --unshallow origin"):
            self.assertIn(required, source)
        for forbidden in ("pull_request_target:", "secrets.", "environment:", "continue-on-error:",
                          "cancel-in-progress: true", "secrets: inherit", "fetch-depth: 0",
                          "+refs/tags/*:refs/tags/*"):
            self.assertNotIn(forbidden, source)

    def test_compiler_checks_are_strict_separate_from_tests_locks_and_publication(self):
        commands = hosted.compilation_commands()
        self.assertEqual(commands[0][1], [f":{name}:dokkaGeneratePublicationHtml" for name in hosted.LIBRARIES])
        self.assertEqual(commands[1][1], [":p2p-sample-rpc:linkDebugFrameworkIosSimulatorArm64",
                                         ":p2p-sample-rpc:linkDebugFrameworkIosArm64",
                                         ":p2p-sample-rpc:linkDebugFrameworkIosX64"])
        for forbidden in ("jvmTest", "iosSimulatorArm64Test", "resolveAndLockAll", "--write-", "publish"):
            self.assertNotIn(forbidden, str(commands))
        with tempfile.TemporaryDirectory() as directory:
            for target, (sdk, triple) in hosted.APPLE_TARGETS.items():
                with patch.object(hosted.subprocess, "check_output", return_value=directory):
                    command = hosted.swift_command(Path(directory), target)
                    self.assertIn("-typecheck", command)
                    self.assertIn("-warnings-as-errors", command)
                    self.assertEqual(command[command.index("-target") + 1], triple)
                    self.assertIn("ios14.0", triple)
                    self.assertEqual(command[2], sdk)

    def test_compilation_requires_nonempty_genuine_outputs_and_preserves_ios_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in hosted.LIBRARIES:
                path = root / f"library/{name}/build/dokka/html/index.html"
                path.parent.mkdir(parents=True)
                path.write_text("<html>synthetic control</html>")
            self.assertEqual(len(hosted.compilation_receipt(root, "strict-dokka")["htmlIndexes"]), 3)
            for target in hosted.APPLE_TARGETS:
                path = hosted.framework_path(root, target)
                for name in ("P2pKitRpcExample", "Headers/P2pKitRpcExample.h", "Modules/module.modulemap"):
                    output = path / name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"synthetic offline control, not a framework")
                (path / "Info.plist").write_bytes(hosted.plistlib.dumps({"MinimumOSVersion": "14.0"}))
            result = hosted.compilation_receipt(root, "rpc-frameworks")
            self.assertEqual(len(result["frameworks"]), 3)
            (path / "Info.plist").write_bytes(hosted.plistlib.dumps({"MinimumOSVersion": "15.0"}))
            with self.assertRaisesRegex(hosted.HostedValidationError, "minimum iOS"):
                hosted.compilation_receipt(root, "rpc-frameworks")
            (path / "Info.plist").write_bytes(hosted.plistlib.dumps({"MinimumOSVersion": "14.0"}))
            (path / "P2pKitRpcExample").write_bytes(b"")
            with self.assertRaisesRegex(hosted.HostedValidationError, "compiler output"):
                hosted.compilation_receipt(root, "rpc-frameworks")

    def diagnostic_fixture(self, root, label):
        helper = hosted.platform_runner()
        policy = helper.read_json(ROOT / "gradle/platform-test-policy.json")
        task = hosted.diagnostic_commands()[0 if label == "diagnostic-jmdns" else 1][1][0]
        report = {"schema": 1, "token": "fixture", "dryRun": False, "buildFailed": False,
                  "host": {"os": "Mac OS X", "arch": "aarch64"}, "model": policy["model"], "tests": {}}
        for entry in policy["model"].values():
            for name in entry["tests"]:
                report["tests"][name] = {"outcome": "NOT_REQUESTED", "enabled": True, "inGraph": False,
                                         "passed": 0, "failed": 0, "skipped": 0}
        count = 2 if label == "diagnostic-jmdns" else 1
        report["tests"][task].update(outcome="EXECUTED", inGraph=True, passed=count)
        path = root / ("library/p2p-transport-lan/build/test-results/" + task.rsplit(":", 1)[1]
                       + "/TEST-dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.xml")
        path.parent.mkdir(parents=True)
        methods = ["realResourceCloseRegressionsExitNaturally"]
        if label == "diagnostic-jmdns":
            methods.append("failedSendsCannotMultiplyTheSdkCleanupBudget")
        path.write_text(f'<testsuite tests="{count}" failures="0" errors="0" skipped="0">' + ''.join(
            '<testcase classname="dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest" '
            f'name="{method}"/>' for method in methods) + '</testsuite>')
        for mode in hosted.FIXTURE_MODES:
            log = root / f"library/p2p-transport-lan/build/reports/jmdns-close/run-fixture/{mode}-123.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("PASS mode=" + mode + "\n")
        return report, path, task

    def test_diagnostics_require_fresh_matching_task_counts_and_xml(self):
        for label in ("diagnostic-jmdns", "diagnostic-ios-lan"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report, path, task = self.diagnostic_fixture(root, label)
                self.assertEqual(hosted.assess_diagnostic(root, label, report, "fixture")["passed"],
                                 2 if label == "diagnostic-jmdns" else 1)
                for key, value in (("token", "stale"), ("dryRun", True), ("buildFailed", True)):
                    with patch.dict(report, {key: value}), self.assertRaises((hosted.HostedValidationError, ValueError)):
                        hosted.assess_diagnostic(root, label, report, "fixture")
                for key, value in (("outcome", "UP-TO-DATE"), ("passed", 0), ("failed", 1), ("enabled", False)):
                    with patch.dict(report["tests"][task], {key: value}):
                        with self.assertRaises((hosted.HostedValidationError, ValueError)):
                            hosted.assess_diagnostic(root, label, report, "fixture")
                path.unlink()
                with self.assertRaisesRegex(hosted.HostedValidationError, "XML is missing"):
                    hosted.assess_diagnostic(root, label, report, "fixture")

    def test_zero_gradle_exit_cannot_hide_deferred_native_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, path, task = self.diagnostic_fixture(root, "diagnostic-ios-lan")
            for xml in ('<testsuite tests="1" failures="1"><testcase><failure/></testcase></testsuite>',
                        '<testsuite tests="1" failures="0"><testcase><failure/></testcase></testsuite>',
                        '<testsuite tests="1" failures="0"/>'):
                path.write_text(xml)
                with self.assertRaises(hosted.HostedValidationError):
                    hosted.assess_diagnostic(root, "diagnostic-ios-lan", report, "fixture")

    def test_jmdns_pass_marker_cannot_hide_failed_or_missing_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, path, task = self.diagnostic_fixture(root, "diagnostic-jmdns")
            log = root / "library/p2p-transport-lan/build/reports/jmdns-close/run-fixture/control-123.log"
            log.write_text("PASS mode=control\nphase=fixture_rescue_begin mode=control\n")
            with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
            log.unlink()
            with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")

    def test_jmdns_requires_both_new_budget_children_across_invocation_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, _, task = self.diagnostic_fixture(root, "diagnostic-jmdns")
            parent = root / "library/p2p-transport-lan/build/reports/jmdns-close"
            budget = parent / "run-budget-fixture"
            budget.mkdir()
            for mode in ("stop_during_recovery", "failed_goodbyes"):
                (parent / "run-fixture" / (mode + "-123.log")).rename(budget / (mode + "-123.log"))
            self.assertEqual(hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")["passed"], 2)
            with patch.dict(report["tests"][task], passed=1):
                with self.assertRaisesRegex(hosted.HostedValidationError, "fresh JmDNS fixture"):
                    hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
            for mode in ("stop_during_recovery", "failed_goodbyes"):
                path = budget / (mode + "-123.log")
                raw = path.read_text()
                path.write_text(raw + "phase=fixture_rescue_begin mode=" + mode + "\n")
                with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                    hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
                path.unlink()
                with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                    hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
                path.write_text(raw)

    def test_invalid_counts_and_xml_entities_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "samples/example/build/test-results/test/TEST-example.xml"
            path.parent.mkdir(parents=True)
            for xml in ('<testsuite tests="-1"/>', '<!DOCTYPE x><testsuite tests="1"/>'):
                path.write_text(xml)
                with self.assertRaises(hosted.HostedValidationError):
                    hosted.test_summary(root)

    def test_bounded_reader_rejects_oversized_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"12345")
            self.assertEqual(hosted.read_bounded(path, 5), b"12345")
            with self.assertRaises(hosted.HostedValidationError):
                hosted.read_bounded(path, 4)
            link = path.with_name("link")
            link.symlink_to(path)
            with self.assertRaises(hosted.HostedValidationError):
                hosted.read_bounded(link)

    def test_unexpected_source_changes_block_candidate_export(self):
        with patch.object(hosted, "git", return_value=b"library/p2p-rpc/src/Unexpected.kt\n"):
            with self.assertRaisesRegex(hosted.HostedValidationError, "Unexpected source"):
                hosted.collect_candidates(ROOT, False)

    def test_failed_writer_never_exports_acceptable_locks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(hosted, "git", return_value=b""):
            root = Path(directory)
            for name in (*hosted.LOCKS, *(f"library/{n}/api/{n}.klib.api" for n in hosted.LIBRARIES)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture\n")
            self.assertEqual(hosted.collect_candidates(root, False)[0]["status"], "INCOMPLETE_DO_NOT_IMPORT")
            self.assertEqual(hosted.collect_candidates(root, True)[0]["status"], "REVIEW_REQUIRED")
            (root / "library/p2p-rpc/gradle.lockfile").unlink()
            self.assertEqual(hosted.collect_candidates(root, True)[0]["status"], "INCOMPLETE_DO_NOT_IMPORT")

    def terminal_fixture(self, observed, *, returncode=0, size=0, drained=True, running=False,
                         stat_error=None):
        # All process, clock, log and cleanup objects are fake. No child, signal,
        # socket or filesystem operation is performed by this source regression.
        state, log = MagicMock(), MagicMock()
        state.__truediv__.return_value = log
        log.stat.return_value = SimpleNamespace(st_size=size)
        if stat_error is not None:
            log.stat.side_effect = stat_error
        process = Mock(returncode=returncode)
        process.poll.return_value = None if running else returncode
        child = SimpleNamespace(Popen=Mock(return_value=process), STDOUT=hosted.subprocess.STDOUT)
        clock = SimpleNamespace(monotonic=Mock(side_effect=[0.0, observed, observed + 0.001]),
                                sleep=Mock(side_effect=AssertionError("Unexpected fake polling retry")))
        helper = SimpleNamespace(ProcessOwner=Mock(return_value=process), terminate_process=Mock(return_value=drained))
        def execute():
            with patch.object(hosted, "platform_runner", return_value=helper), \
                    patch.object(hosted, "subprocess", child), patch.object(hosted, "time", clock):
                return hosted.execute(state, "terminal-fixture", ["not-executed"], 5)
        return execute, child, helper, process, log, clock

    def assert_terminal_cleanup(self, child, helper, process, log, clock):
        child.Popen.assert_not_called()
        helper.ProcessOwner.assert_called_once_with()
        process.start.assert_called_once_with(["not-executed"], cwd=hosted.ROOT,
                                              stdout=log.open.return_value.__enter__.return_value,
                                              stderr=hosted.subprocess.STDOUT)
        log.open.assert_called_once_with("xb")
        log.open.return_value.__exit__.assert_called_once()
        helper.terminate_process.assert_called_once_with(process)
        clock.sleep.assert_not_called()

    def test_terminal_observation_within_original_bounds_preserves_success_and_failure(self):
        for returncode, size in ((0, 0), (7, 0), (0, hosted.MAX_LOG)):
            with self.subTest(returncode=returncode, size=size):
                execute, *fakes = self.terminal_fixture(4.999, returncode=returncode, size=size)
                row = execute()
                self.assertEqual(row["exitCode"], returncode)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_success_at_or_after_original_deadline_is_rejected(self):
        for observed in (5.0, 5.001, 25.0):
            with self.subTest(observed=observed):
                execute, *fakes = self.terminal_fixture(observed)
                row = execute()
                self.assertEqual(row["exitCode"], 124)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_exit_cannot_hide_an_overlong_final_log(self):
        for returncode in (0, 7):
            with self.subTest(returncode=returncode):
                execute, *fakes = self.terminal_fixture(1.0, returncode=returncode, size=hosted.MAX_LOG + 1)
                row = execute()
                self.assertEqual(row["exitCode"], 124)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_cleanup_uncertainty_cannot_be_reported_as_success(self):
        for observed, size in ((1.0, 0), (5.0, 0), (1.0, hosted.MAX_LOG + 1)):
            with self.subTest(observed=observed, size=size):
                execute, *fakes = self.terminal_fixture(observed, size=size, drained=False)
                row = execute()
                self.assertEqual(row["exitCode"], 125)
                self.assertFalse(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_original_running_deadline_and_log_guards_still_drain_the_same_process(self):
        for observed, size in ((5.001, 0), (1.0, hosted.MAX_LOG + 1)):
            with self.subTest(observed=observed, size=size):
                execute, *fakes = self.terminal_fixture(observed, size=size, running=True)
                row = execute()
                self.assertEqual(row["exitCode"], 124)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_log_observation_error_still_drains_the_owned_process(self):
        execute, *fakes = self.terminal_fixture(1.0, stat_error=OSError("synthetic stat failure"))
        with self.assertRaisesRegex(OSError, "synthetic stat failure"):
            execute()
        self.assert_terminal_cleanup(*fakes)

    def test_partial_launch_still_retires_the_original_owner_without_hiding_failure(self):
        for drained in (True, False):
            execute, child, helper, process, log, clock = self.terminal_fixture(1.0, drained=drained)
            failure = OSError("synthetic partial native launch")
            process.start.side_effect = failure
            with self.subTest(drained=drained), self.assertRaises(OSError) as caught:
                execute()
            self.assertIs(caught.exception, failure)
            process.poll.assert_not_called()
            self.assert_terminal_cleanup(child, helper, process, log, clock)

    def test_python_fixture_exit_and_deadline_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            failed = hosted.execute(state, "failure", [sys.executable, "-c", "raise SystemExit(7)"], 5)
            self.assertEqual(failed["exitCode"], 7)
            self.assertTrue(failed["processGroupDrained"])
            timed = hosted.execute(state, "deadline", [sys.executable, "-c", "import time; time.sleep(10)"], 0.1)
            self.assertEqual(timed["exitCode"], 124)
            self.assertTrue(timed["processGroupDrained"])


if __name__ == "__main__":
    unittest.main()
