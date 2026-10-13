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


def preview_staging_contract(build):
    """Source-level tripwire only; actual Gradle/Windows image tests remain mandatory."""
    resources = build[build.index('val rpcWindowsApplicationResources ='):build.index(
        'compose.desktop.application.nativeDistributions', build.index('val rpcWindowsApplicationResources ='))]
    if 'adapterJar' in resources or 'rpcWindowsLoaderJdk21Jar' in resources:
        raise AssertionError("Preview JAR must stay outside jpackage's recursively scanned resources")
    start = build.index('if (packageTask in imageTasks) {')
    end = build.index('                    } else {\n                        val imageTask', start)
    image = build[start:end]
    for required in (
        'dependsOn(":p2p-sample-rpc:rpcWindowsLoaderJdk21Jar")',
        'inputs.file(adapterJar).withPropertyName("rpcWindowsPreviewAdapterJar")',
        'doLast {', 'targetFormat == TargetFormat.AppImage',
        'val image = destinationDir.get().dir(packageName.get()).asFile.toPath()',
        'val resources = app.resolve("resources")',
        'Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS)',
        'it.readNBytes(16 * 1024 * 1024 + 1)', 'after.fileKey() == before.fileKey()',
        'after.lastModifiedTime() == before.lastModifiedTime()',
        'it.readNBytes(65537)', '!cfgBytes.toString(Charsets.UTF_8).contains(source.fileName.toString())',
        'val adapterDirectory = resources.resolve("rpc-loader-jdk21")',
        'Files.createDirectory(adapterDirectory)',
        'Files.write(target, bytes, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)',
        'Files.mismatch(source, target) == -1L',
    ):
        if required not in image:
            raise AssertionError("Missing completed-image staging invariant: " + required)
    if image.index('inputs.file(adapterJar)') > image.index('doLast {') or 'doFirst {' in image:
        raise AssertionError("Declare adapter input before image completion; never stage before jpackage")
    if 'Files.write(cfg' in image or 'REPLACE_EXISTING' in image:
        raise AssertionError("Staging must not rewrite configuration or replace an existing adapter")
    installer = build[end:build.index('                doFirst {\n                    check(appResourcesDir', end)]
    for required in (
        'packageTask.startsWith("packageRelease")', '"createReleaseDistributable"', '"createDistributable"',
        'val maintainedImage = tasks.named<AbstractJPackageTask>(imageTask)', 'dependsOn(maintainedImage)',
        'val completedImage = maintainedImage.flatMap { image ->',
        'image.destinationDir.map { it.dir(image.packageName.get()) }',
        'if (!appImage.isPresent) appImage.set(completedImage)',
        'inputs.dir(completedImage)',
        'check(appImage.get().asFile == completedImage.get().asFile)',
    ):
        if required not in installer:
            raise AssertionError("Missing maintained installer/image binding: " + required)
    if installer.count('appImage.set(') != 1:
        raise AssertionError("Only the absent Windows installer image binding may be supplied")


class WindowsPackagingWiringTest(unittest.TestCase):
    def test_windows_tasks_are_inside_actual_host_guard(self):
        start = BUILD.index('if (detectedDesktopLockTarget == "windows-x64") {')
        end = BUILD.index('\ncompose.desktop {', start)
        block = BUILD[start:end]
        self.assertIn('tasks.register<BuildWindowsProfileTask>("buildRpcWindowsProfileNative")', block)
        self.assertIn('tasks.register<JavaExec>("stageRpcWindowsProfileNative")', block)
        self.assertIn('tasks.named<AbstractJPackageTask>(packageTask) {', block)
        self.assertIn('dependsOn(stageRpcWindowsProfileNative)', block)
        self.assertIn('appResourcesDir.set(layout.dir(rpcWindowsApplicationResources.map { it.destinationDir }))', block)
        self.assertNotIn('package-rpc-preview', block)

    def test_internal_package_resource_property_has_explicit_dependency_and_input(self):
        start = BUILD.index('if (detectedDesktopLockTarget == "windows-x64") {')
        end = BUILD.index('\ncompose.desktop {', start)
        block = BUILD[start:end]
        self.assertNotIn('tasks.withType<AbstractJPackageTask>().configureEach', block)
        self.assertIn('tasks.named<AbstractJPackageTask>(packageTask)', block)
        for task in ('createDistributable', 'packageMsi', 'packageExe',
                     'createReleaseDistributable', 'packageReleaseMsi', 'packageReleaseExe'):
            self.assertIn('"' + task + '"', block)
        self.assertIn('dependsOn(rpcWindowsApplicationResources)', block)
        self.assertIn('inputs.dir(rpcWindowsApplicationResources.map { it.destinationDir })', block)
        self.assertIn('check(appResourcesDir.get().asFile == rpcWindowsApplicationResources.get().destinationDir)', block)

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
        self.assertIn('tasks.named<AbstractJPackageTask>(packageTask)', block)
        self.assertNotIn('appResourcesRootDir.set', block)
        self.assertIn('from(tasks.named<Sync>("prepareAppResources").map { it.destinationDir })', block)

    def test_existing_application_identity_and_formats_remain(self):
        self.assertIn('mainClass = "dev.p2pkit.sample.desktop.ui.MainKt"', BUILD)
        self.assertIn('targetFormats(TargetFormat.Exe, TargetFormat.Msi, TargetFormat.Dmg, TargetFormat.Deb)', BUILD)
        self.assertIn('packageName = "P2pKit Sample"', BUILD)

    def test_preview_investigation_is_opt_in_and_named_not_a_classpath_dependency(self):
        self.assertIn('providers.gradleProperty("p2pkit.rpc.windows.previewAdapter")', BUILD)
        self.assertIn('it.toBooleanStrict()', BUILD)
        self.assertIn('}.getOrElse(false)', BUILD)
        self.assertNotIn('from(adapterJar)', BUILD)
        self.assertIn('inputs.file(adapterJar)', BUILD)
        self.assertNotIn('classpath(adapterJar)', BUILD)
        self.assertNotIn('files.from(adapterJar)', BUILD)
        self.assertIn('"--enable-preview"', BUILD)
        self.assertIn('"--add-modules=dev.p2pkit.rpc.windows.loader"', BUILD)
        self.assertIn('"--enable-native-access=dev.p2pkit.rpc.windows.loader"', BUILD)
        self.assertNotIn('ALL-UNNAMED', BUILD)

    def test_adapter_stages_only_after_the_existing_image_action_with_declared_inputs(self):
        preview_staging_contract(BUILD)
        self.assertIn('val imageTasks = setOf("createDistributable", "createReleaseDistributable")', BUILD)
        self.assertNotIn('finalizedBy(', BUILD)
        self.assertNotIn('stageRpcWindowsPreviewImage', BUILD)

    def test_source_controls_reject_staging_into_jpackage_input_again(self):
        needle = 'from(appResources.map { it.dir("windows") })'
        changed = BUILD.replace(needle, needle + '\n        from(adapterJar) { into("rpc-loader-jdk21") }')
        with self.assertRaisesRegex(AssertionError, "recursively scanned"):
            preview_staging_contract(changed)

    def test_source_controls_reject_missing_input_dependency_or_wrong_completion_order(self):
        for original, replacement in (
            ('dependsOn(":p2p-sample-rpc:rpcWindowsLoaderJdk21Jar")', ''),
            ('inputs.file(adapterJar).withPropertyName("rpcWindowsPreviewAdapterJar")', ''),
            ('                        doLast {', '                        doFirst {'),
        ):
            with self.subTest(original=original), self.assertRaises(AssertionError):
                preview_staging_contract(BUILD.replace(original, replacement))

    def test_source_controls_reject_overwrite_unbounded_copy_and_classpath_rewrite(self):
        for original, replacement in (
            ('it.readNBytes(16 * 1024 * 1024 + 1)', 'it.readAllBytes()'),
            ('StandardOpenOption.CREATE_NEW', 'StandardOpenOption.CREATE'),
            ('Files.mismatch(source, target) == -1L', 'true'),
            ('!cfgBytes.toString(Charsets.UTF_8).contains(source.fileName.toString())', 'true'),
            ('Files.write(target, bytes,', 'Files.write(cfg, bytes,'),
        ):
            with self.subTest(original=original), self.assertRaises(AssertionError):
                preview_staging_contract(BUILD.replace(original, replacement))

    def test_source_controls_reject_installer_bypassing_completed_image(self):
        for original, replacement in (
            ('dependsOn(maintainedImage)', ''),
            ('inputs.dir(completedImage)', ''),
            ('check(appImage.get().asFile == completedImage.get().asFile)', 'check(true)'),
            ('val maintainedImage = tasks.named<AbstractJPackageTask>(imageTask)',
             'val maintainedImage = tasks.named<AbstractJPackageTask>("otherImage")'),
        ):
            with self.subTest(original=original), self.assertRaises(AssertionError):
                preview_staging_contract(BUILD.replace(original, replacement))

    def test_windows_installer_supplies_absent_image_binding_to_exact_named_output(self):
        preview_staging_contract(BUILD)
        start = BUILD.index('val maintainedImage = tasks.named<AbstractJPackageTask>(imageTask)')
        end = BUILD.index('                doFirst {\n                    check(appResourcesDir', start)
        installer = BUILD[start:end]
        self.assertLess(installer.index('if (!appImage.isPresent) appImage.set(completedImage)'),
                        installer.index('doFirst {'))
        for original, replacement in (
            ('if (!appImage.isPresent) appImage.set(completedImage)', ''),
            ('if (!appImage.isPresent) appImage.set(completedImage)', 'appImage.set(completedImage)'),
            ('image.destinationDir.map { it.dir(image.packageName.get()) }', 'image.destinationDir'),
            ('image.destinationDir.map { it.dir(image.packageName.get()) }',
             'image.destinationDir.map { it.dir("other-app") }'),
        ):
            with self.subTest(original=original, replacement=replacement), self.assertRaises(AssertionError):
                preview_staging_contract(BUILD.replace(original, replacement))

    def test_preview_runtime_family_applies_to_linker_not_just_installer(self):
        self.assertIn('tasks.withType<AbstractJLinkTask>().configureEach', BUILD)
        self.assertIn('tasks.withType<AbstractCheckNativeDistributionRuntime>().configureEach', BUILD)
        self.assertIn('jdkHome.set(previewRuntime.map', BUILD)
        self.assertIn('javaHome.set(previewRuntime.map', BUILD)
        self.assertIn('jvmToolchain(17)', BUILD)

    def test_java21_preview_is_confined_to_unpublished_adapter_compilation(self):
        sample = (ROOT / "samples/p2p-sample-rpc/build.gradle.kts").read_text()
        self.assertIn('jvmToolchain(17)', sample)
        self.assertEqual(sample.count('"--enable-preview"'), 1)
        self.assertIn('tasks.register<JavaCompile>("compileRpcWindowsLoaderJdk21")', sample)
        self.assertIn('source(layout.projectDirectory.dir("native/windows-loader-jdk21/src/main/java"))', sample)
        self.assertIn('options.release.set(21)', sample)
        self.assertIn('classpath = files()', sample)
        self.assertIn('from(compileRpcWindowsLoaderJdk21.flatMap { it.destinationDirectory })', sample)
        self.assertNotIn('implementation(windowsLoaderJdk21)', sample)

    def test_stage_has_no_execution_or_availability_promotion(self):
        for forbidden in ('System.load(', 'System.loadLibrary(', 'IMPLEMENTED = true', 'QUALIFIED = true'):
            self.assertNotIn(forbidden, STAGER)
        self.assertIn('WindowsProfileByteManifest.produce', STAGER)
        self.assertIn('WindowsProfileByteManifest.authorize', STAGER)
        self.assertIn('readBounded(path, bytes.size, bytes.size).contentEquals(bytes)', STAGER)


if __name__ == "__main__":
    unittest.main()
