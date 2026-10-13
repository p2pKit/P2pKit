#!/usr/bin/env python3
"""Source guard for the existing Desktop packaging wiring, not Windows installer/runtime qualification."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILD = (ROOT / "samples/p2p-sample-desktop-ui/build.gradle.kts").read_text()
COMPILER = (ROOT / "buildSrc/src/main/java/dev/p2pkit/build/BuildWindowsProfileTask.java").read_text()
SOURCE_CHECK = (ROOT / "buildSrc/src/main/java/dev/p2pkit/build/WindowsProfilePackagingSource.java").read_text()
STAGER = (ROOT / "samples/p2p-sample-rpc/src/jvmMain/kotlin/dev/p2pkit/sample/rpc/profile/"
          "WindowsProfilePackageStage.kt").read_text()


class WindowsPackagingWiringTest(unittest.TestCase):
    def test_windows_tasks_are_inside_actual_host_guard(self):
        start = BUILD.index('if (detectedDesktopLockTarget == "windows-x64") {')
        end = BUILD.index('\ncompose.desktop {', start)
        block = BUILD[start:end]
        self.assertIn('tasks.register<BuildWindowsProfileTask>("buildRpcWindowsProfileNative")', block)
        self.assertIn('tasks.register<JavaExec>("stageRpcWindowsProfileNative")', block)
        self.assertIn('tasks.withType<AbstractJPackageTask>().configureEach {', block)
        self.assertIn('dependsOn(stageRpcWindowsProfileNative)', block)
        self.assertIn('appResourcesDir.set(layout.dir(rpcWindowsApplicationResources.map { it.destinationDir }))', block)
        self.assertNotIn('package-rpc-preview', block)

    def test_native_task_retains_clean_source_requirement_and_normal_tool_setup(self):
        for value in ('WindowsProfilePackagingSource.inspect(getRootDirectory().get().getAsFile(), source)', 'VsDevCmd.bat', '-arch=x64 -host_arch=x64', 'getJavaHome()', 'assertNormalExitValue()',
                      'build-windows.cmd', 'COMPILER_BYTES_ONLY'):
            self.assertIn(value, COMPILER)
        self.assertEqual(COMPILER.count('WindowsProfilePackagingSource.inspect(getRootDirectory().get().getAsFile(), source)'), 2)
        for forbidden in ('System.load(', 'System.loadLibrary(', 'AdjustTokenPrivileges', 'download('):
            self.assertNotIn(forbidden, COMPILER)

    def test_clean_source_check_is_an_always_run_prerequisite(self):
        guard = (ROOT / "buildSrc/src/main/java/dev/p2pkit/build/VerifyWindowsProfileSourceTask.java").read_text()
        self.assertIn('tasks.register<VerifyWindowsProfileSourceTask>', BUILD)
        self.assertIn('dependsOn(verifyRpcWindowsPackagingSource)', BUILD)
        self.assertIn('WindowsProfilePackagingSource.inspect', guard)
        self.assertIn('Native packaging requires an exact clean committed source', SOURCE_CHECK)
        self.assertNotIn('@Output', guard)
        self.assertIn('doNotTrackState', guard)

    def test_final_pin_module_is_in_packaged_runtime_without_global_module_expansion(self):
        self.assertIn('modules("jdk.unsupported")', BUILD)
        self.assertNotIn('includeAllModules = true', BUILD)

    def test_stage_depends_on_production_code_not_tests_or_lab(self):
        start = BUILD.index('val stageRpcWindowsProfileNative =')
        end = BUILD.index('val rpcWindowsParentPinJar', start)
        block = BUILD[start:end]
        self.assertIn('classpath(configurations.runtimeClasspath)', block)
        self.assertIn('dependsOn(buildRpcWindowsProfileNative)', block)
        self.assertNotIn('jvmTest', block)
        self.assertNotIn('labCompilation', block)

    def test_component_pins_are_packaged_in_parent_jar_separately(self):
        self.assertIn('tasks.register<Jar>("rpcWindowsParentPinJar") {\n'
                      '        dependsOn(stageRpcWindowsProfileNative)\n        from(parentPinResources)', BUILD)
        self.assertIn('files.from(rpcWindowsParentPinJar.flatMap { it.archiveFile })', BUILD)
        self.assertNotIn('tasks.named<ProcessResources>', BUILD)
        self.assertIn('include("META-INF/p2pkit/windows-profile-parent.properties")', BUILD)
        self.assertIn('META-INF/p2pkit/windows-profile-parent.properties', STAGER)
        self.assertIn('PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY', STAGER)
        self.assertIn('manifestSha256=${staged.manifestSha256}', STAGER)
        self.assertIn('dllSha256=${staged.dllSha256}', STAGER)

    def test_ordinary_development_does_not_depend_on_windows_compiler(self):
        start = BUILD.index('if (detectedDesktopLockTarget == "windows-x64") {')
        end = BUILD.index('\ncompose.desktop {', start)
        block = BUILD[start:end]
        for forbidden in ('tasks.withType<Test>', 'tasks.named<Test>', 'tasks.withType<ProcessResources>',
                          'tasks.named<ProcessResources>', 'sourceSets', 'tasks.named("run")'):
            self.assertNotIn(forbidden, block)
        self.assertIn('tasks.withType<AbstractJPackageTask>().configureEach', block)
        self.assertNotIn('appResourcesRootDir.set', block)
        self.assertIn('from(tasks.named<Sync>("prepareAppResources").map { it.destinationDir })', block)

    def test_existing_application_identity_and_formats_remain(self):
        self.assertIn('mainClass = "dev.p2pkit.sample.desktop.ui.MainKt"', BUILD)
        self.assertIn('targetFormats(TargetFormat.Exe, TargetFormat.Msi, TargetFormat.Dmg, TargetFormat.Deb)', BUILD)
        self.assertIn('packageName = "P2pKit Sample"', BUILD)

    def test_stage_has_no_execution_or_availability_promotion(self):
        for forbidden in ('System.load(', 'System.loadLibrary(', 'IMPLEMENTED = true', 'QUALIFIED = true'):
            self.assertNotIn(forbidden, STAGER)
        self.assertIn('WindowsProfileByteManifest.produce', STAGER)
        self.assertIn('WindowsProfileByteManifest.authorize', STAGER)
        self.assertIn('readBounded(path, bytes.size, bytes.size).contentEquals(bytes)', STAGER)


if __name__ == "__main__":
    unittest.main()
