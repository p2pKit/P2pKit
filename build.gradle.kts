import dev.p2pkit.build.VerifyPublicConstantAbiTask
import org.gradle.api.publish.PublishingExtension
import org.gradle.api.publish.maven.MavenPublication
import org.gradle.api.publish.maven.tasks.AbstractPublishToMaven
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.jvm.tasks.Jar
import org.gradle.plugins.signing.Sign
import org.gradle.plugins.signing.SigningExtension
import org.gradle.api.services.BuildService
import org.gradle.api.services.BuildServiceParameters
import org.cyclonedx.gradle.CyclonedxDirectTask
import org.cyclonedx.gradle.utils.CyclonedxUtils
import org.cyclonedx.model.Ancestors
import org.cyclonedx.model.Component
import org.cyclonedx.model.Dependency
import org.cyclonedx.model.Diff
import org.cyclonedx.model.ExternalReference
import org.cyclonedx.model.Hash
import org.cyclonedx.model.Patch
import org.cyclonedx.model.Pedigree
import org.cyclonedx.model.Property as CyclonedxProperty
import org.cyclonedx.parsers.BomParserFactory
import org.jetbrains.kotlin.gradle.tasks.KotlinCompilationTask
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile
import com.android.build.gradle.tasks.BundleAar
import com.fasterxml.jackson.annotation.JsonInclude
import com.fasterxml.jackson.core.JsonParser
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import kotlinx.validation.KotlinApiBuildTask
import kotlinx.validation.KotlinApiCompareTask
import java.util.Base64
import java.util.HexFormat
import java.nio.file.Files
import java.security.MessageDigest

// Plugin DSL dependencies resolve before the allprojects rules below exist.
// Apply the same advisory floors to the root build classpath so build tools
// cannot execute an older vulnerable transitive dependency in trusted CI.
buildscript {
    configurations.configureEach {
        resolutionStrategy.activateDependencyLocking()
        resolutionStrategy.eachDependency {
            val requestedGroup = requested.group ?: return@eachDependency
            val requestedModule = "$requestedGroup:${requested.name}"
            val minimumVersion = when (requestedGroup) {
                "org.bouncycastle" -> "1.85"
                else -> mapOf(
                    "com.fasterxml.jackson.core:jackson-core" to "2.21.5",
                    "com.fasterxml.jackson.core:jackson-databind" to "2.21.5",
                    "org.bitbucket.b_c:jose4j" to "0.9.6",
                    "org.jdom:jdom2" to "2.0.6.1",
                    "org.jsoup:jsoup" to "1.23.1",
                )[requestedModule]
            }
            if (minimumVersion != null) {
                val numericComponent = Regex("\\d+")
                val requestedParts = numericComponent.findAll(requested.version.orEmpty())
                    .mapNotNull { it.value.toIntOrNull() }
                    .toList()
                val minimumParts = numericComponent.findAll(minimumVersion)
                    .mapNotNull { it.value.toIntOrNull() }
                    .toList()
                val requestedIsBelow = requestedParts.isEmpty() ||
                    (0 until maxOf(requestedParts.size, minimumParts.size)).firstNotNullOfOrNull { index ->
                        val requestedPart = requestedParts.getOrElse(index) { 0 }
                        val minimumPart = minimumParts.getOrElse(index) { 0 }
                        when {
                            requestedPart < minimumPart -> true
                            requestedPart > minimumPart -> false
                            else -> null
                        }
                    } == true
                if (requestedIsBelow) {
                    useVersion(minimumVersion)
                    because("ENV-06 root build-plugin advisory minimum")
                }
            }
        }
    }
}

plugins {
    alias(libs.plugins.kotlin.multiplatform) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.kmp.library) apply false
    alias(libs.plugins.jetbrains.compose) apply false
    alias(libs.plugins.dokka) apply false
    alias(libs.plugins.cyclonedx)
    alias(libs.plugins.binary.compatibility.validator) apply false
}

// A lock refresh must configure the complete project model. Configuration on
// demand can leave subproject check and Dokka tasks unregistered, producing a
// successful but partial lock rewrite before the graph policy can detect the
// omission. Reject that mode independently of how the refresh task is named.
check(!gradle.startParameter.isWriteDependencyLocks || !gradle.startParameter.isConfigureOnDemand) {
    "--write-locks requires --no-configure-on-demand"
}

abstract class NetworkIntegrationTestService : BuildService<BuildServiceParameters.None>

val networkIntegrationTestService = gradle.sharedServices.registerIfAbsent(
    "networkIntegrationTests",
    NetworkIntegrationTestService::class,
) {
    // Kotlin/Native test binaries share one simulator host and process-global
    // Apple services. Real JVM LAN suites also share one host interface,
    // multicast group, and JmDNS lifecycle. Cross-task overlap caused raw-
    // channel churn and multicast/TCP timeouts even though every complete
    // suite passed alone. Serialize only those integration-test tasks while
    // leaving compilation and deterministic non-network tests parallel.
    maxParallelUsages.set(1)
}

val serializedJvmNetworkTestTasks = mapOf(
    ":p2p-transport-lan" to setOf("jvmTest"),
    ":sample-kmp-shared" to setOf("jvmTest"),
    ":p2p-network-provisioning-desktop" to setOf("test"),
)

// ENV-06: build, documentation, and test plugins bring their own dependency
// graphs, which are not part of the published SDK SBOM but still execute in
// trusted CI. Keep security floors centralized so a plugin cannot silently
// reintroduce a version with a current OSV advisory. These overrides remain
// scoped to dependencies already requested by a configuration; they do not
// add any library to a published runtime graph.
val advisoryMinimumVersions = mapOf(
    "com.fasterxml.jackson.core:jackson-core" to "2.21.5",
    "com.fasterxml.jackson.core:jackson-databind" to "2.21.5",
    "io.opentelemetry:opentelemetry-api" to "1.62.0",
    "io.opentelemetry:opentelemetry-context" to "1.62.0",
    "org.apache.commons:commons-lang3" to "3.18.0",
    "org.apache.httpcomponents:httpclient" to "4.5.13",
    "org.bitbucket.b_c:jose4j" to "0.9.6",
    "org.jdom:jdom2" to "2.0.6.1",
    "org.jsoup:jsoup" to "1.23.1",
)

fun isVersionBelow(requestedVersion: String?, minimumVersion: String): Boolean {
    if (requestedVersion == null) return true
    val numericComponent = Regex("\\d+")
    val requested = numericComponent.findAll(requestedVersion).mapNotNull { it.value.toIntOrNull() }.toList()
    val minimum = numericComponent.findAll(minimumVersion).mapNotNull { it.value.toIntOrNull() }.toList()
    if (requested.isEmpty()) return true
    for (index in 0 until maxOf(requested.size, minimum.size)) {
        val requestedPart = requested.getOrElse(index) { 0 }
        val minimumPart = minimum.getOrElse(index) { 0 }
        if (requestedPart != minimumPart) return requestedPart < minimumPart
    }
    return false
}

// Establish Maven coordinates for every module from the single source of truth
// in gradle.properties (GROUP / VERSION_NAME), producing artifacts at
// io.github.apdelrahman1911:<module>:<version>.
// AUDIT-2026-06: `maven-publish` now ships on all four library modules
// (:p2p-core, :p2p-transport-lan, :p2p-network-provisioning-android,
// :p2p-network-provisioning-desktop). Module names/descriptions live beside
// each publication; shared repository, license, developer, and SCM metadata
// comes from buildSrc's P2pPomMetadata helper. Signing is wired centrally below.
allprojects {
    group = (findProperty("GROUP") as String?) ?: "io.github.apdelrahman1911"
    version = (findProperty("VERSION_NAME") as String?) ?: "0.0.0-SNAPSHOT"

    // REL-SUPPLY-01 (BUILD-06): every resolvable project configuration uses
    // committed lock state. The maintenance task below refreshes all locks in
    // one explicit --write-locks operation; ordinary builds never rewrite it.
    dependencyLocking {
        lockAllConfigurations()
        if (project.path == ":p2p-sample-desktop-ui") {
            // Compose Desktop and Skiko use OS/architecture-specific module
            // names. The direct Compose coordinate and common Skiko modules
            // pin their versions, while strict verification authenticates the
            // platform bytes. Ignore only those classifier module families so
            // one common lock remains valid on every supported Desktop host.
            ignoredDependencies.add("org.jetbrains.compose.desktop:desktop-jvm-*")
            ignoredDependencies.add("org.jetbrains.skiko:skiko-awt-runtime-*")
        }
    }

    configurations.configureEach {
        resolutionStrategy.eachDependency {
            val requestedGroup = requested.group ?: return@eachDependency
            val requestedModule = "$requestedGroup:${requested.name}"
            val minimumVersion = when (requestedGroup) {
                "io.netty" -> "4.1.137.Final"
                "org.bouncycastle" -> "1.85"
                else -> advisoryMinimumVersions[requestedModule]
            }
            if (minimumVersion != null && isVersionBelow(requested.version, minimumVersion)) {
                useVersion(minimumVersion)
                because("ENV-06 current advisory minimum")
            }
        }
    }

    // The aggregate release SBOM describes the four published libraries, not
    // sample applications, compiler toolchains, test engines, or build-system
    // internals. Narrow inputs to one runtime graph per published module and
    // disable the direct BOM task everywhere else.
    tasks.withType(CyclonedxDirectTask::class.java).configureEach {
        val releaseConfigurations = when (project.path) {
            ":p2p-core", ":p2p-transport-lan" -> listOf(
                "jvmRuntimeClasspath",
                "iosArm64CompileKlibraries",
                "iosSimulatorArm64CompileKlibraries",
                "iosX64CompileKlibraries",
            )
            ":p2p-network-provisioning-android" -> listOf("androidRuntimeClasspath")
            ":p2p-network-provisioning-desktop" -> listOf("runtimeClasspath")
            else -> null
        }
        if (releaseConfigurations == null) {
            enabled = false
        } else {
            includeConfigs.set(releaseConfigurations)
            includeMetadataResolution.set(false)
            includeBuildEnvironment.set(false)
        }
    }
}

// Kotlin's built-in ABI validation deliberately excludes Android-only
// publications. Protect the Kotlin-visible Android bytecode explicitly with
// the same metadata-aware dumper used by JetBrains' compatibility validator;
// raw javap output would incorrectly freeze Kotlin-internal declarations.
val androidAbiProjects = setOf(
    ":p2p-core",
    ":p2p-transport-lan",
    ":p2p-network-provisioning-android",
)

subprojects {
    if (path !in androidAbiProjects) return@subprojects

    val androidAbiRuntime = configurations.register("androidAbiRuntime") {
        isCanBeConsumed = false
        isCanBeResolved = true
        description = "Runtime used to extract Kotlin-aware Android ABI signatures."
    }
    dependencies {
        add(androidAbiRuntime.name, "org.ow2.asm:asm:9.9.1")
        add(androidAbiRuntime.name, "org.ow2.asm:asm-tree:9.9.1")
        add(androidAbiRuntime.name, "org.jetbrains.kotlin:kotlin-metadata-jvm:2.3.21")
    }

    val buildAndroidAbi = tasks.register<KotlinApiBuildTask>("buildAndroidAbi") {
        group = "verification"
        description = "Extracts the Kotlin-visible ABI from the Android main bytecode."
        outputApiFile.set(
            layout.buildDirectory.file("kotlin/androidAbi/${project.name}.api"),
        )
        runtimeClasspath.from(androidAbiRuntime)
    }

    val checkAndroidAbi = tasks.register<KotlinApiCompareTask>("checkAndroidAbi") {
        group = "verification"
        description = "Checks Android-only public API against the committed ABI baseline."
        projectApiFile.set(layout.projectDirectory.file("api/android/${project.name}.api"))
        generatedApiFile.set(buildAndroidAbi.flatMap { it.outputApiFile })
    }

    val checkAndroidPublicConstants = tasks.register<VerifyPublicConstantAbiTask>("checkAndroidPublicConstants") {
        group = "verification"
        description = "Rejects unrecorded public constants on Kotlin-visible Android API owners."
        apiBaseline.set(layout.projectDirectory.file("api/android/${project.name}.api"))
        inputClassesDirs.from(buildAndroidAbi.map { it.inputClassesDirs })
    }
    checkAndroidAbi.configure { dependsOn(checkAndroidPublicConstants) }

    tasks.register<Copy>("updateAndroidAbi") {
        group = "other"
        description = "Updates the committed Android-only ABI baseline after review."
        dependsOn(buildAndroidAbi)
        from(buildAndroidAbi.flatMap { it.outputApiFile })
        into(layout.projectDirectory.dir("api/android"))
    }

    tasks.matching { it.name == "check" }.configureEach {
        dependsOn(checkAndroidAbi)
    }
}

// Kotlin's JVM dumper omits some ConstantValue fields even on supported public
// owners (private companions and internal members in public file facades).
// Inspect compiled fields rather than guessing visibility from Kotlin source.
val jvmAbiProjects = setOf(":p2p-core", ":p2p-transport-lan", ":p2p-network-provisioning-desktop")
subprojects {
    if (path !in jvmAbiProjects) return@subprojects
    val desktop = path == ":p2p-network-provisioning-desktop"
    val checkJvmPublicConstants = tasks.register<VerifyPublicConstantAbiTask>("checkJvmPublicConstants") {
        group = "verification"
        description = "Rejects unrecorded public constants on Kotlin-visible JVM API owners."
        apiBaseline.set(layout.projectDirectory.file("api/${if (desktop) "" else "jvm/"}${project.name}.api"))
        // Include both main producers, never dependencies or test outputs. Configure
        // these providers here rather than mutating this task during Java task realization.
        inputClassesDirs.from(
            tasks.named<KotlinCompile>(if (desktop) "compileKotlin" else "compileKotlinJvm")
                .flatMap { it.destinationDirectory },
            tasks.named<JavaCompile>(if (desktop) "compileJava" else "compileJvmMainJava")
                .flatMap { it.destinationDirectory },
        )
        // These two already-published fields are absent only from the Kotlin JVM
        // dumps. Never turn this into a wildcard or a list of newly leaked fields.
        retainedConstants.set(
            when (project.path) {
                ":p2p-core" -> listOf(
                    "dev/p2pkit/core/provisioning/UnsupportedNetworkProvisioningManager#NOT_IN_V01 Ljava/lang/String;",
                )
                ":p2p-network-provisioning-desktop" -> listOf(
                    "dev/p2pkit/provisioning/desktop/JvmNetworkProvisioningManager#DEFAULT_POLL_INTERVAL_MS J",
                )
                else -> emptyList()
            },
        )
    }
    tasks.matching { it.name == "checkKotlinAbi" || it.name == "check" }.configureEach {
        dependsOn(checkJvmPublicConstants)
    }
}

val checkPublicConstantAbiPolicy = tasks.register<Exec>("checkPublicConstantAbiPolicy") {
    group = "verification"
    description = "Exercises the constant ABI guard against real compiled positive and negative fixtures."
    commandLine("bash", layout.projectDirectory.file("scripts/tests/check-public-constant-abi.sh").asFile)
}

val verifyBuildPluginSecurityFloors = tasks.register("verifyBuildPluginSecurityFloors") {
    group = "verification"
    description = "Fails when the root build classpath drifts from its lock or resolves below an advisory floor."
    doLast {
        val classpath = buildscript.configurations.getByName("classpath")
        val required = setOf(
            "com.fasterxml.jackson.core:jackson-core",
            "com.fasterxml.jackson.core:jackson-databind",
            "org.bitbucket.b_c:jose4j",
            "org.bouncycastle:bcpkix-jdk18on",
            "org.bouncycastle:bcprov-jdk18on",
            "org.jdom:jdom2",
        )
        val resolvedComponents = classpath.incoming.resolutionResult.allComponents
            .mapNotNull { it.id as? org.gradle.api.artifacts.component.ModuleComponentIdentifier }
            .map { "${it.group}:${it.module}:${it.version}" }
            .toSet()
        val buildscriptLock = layout.projectDirectory.file("buildscript-gradle.lockfile").asFile
        check(buildscriptLock.isFile) {
            "Root build-plugin classpath has no committed buildscript-gradle.lockfile"
        }
        val lockedComponents = buildscriptLock.readLines()
            .asSequence()
            .filterNot { it.isBlank() || it.startsWith("#") || it.startsWith("empty=") }
            .filter { line -> line.substringAfter('=', "").split(',').contains("classpath") }
            .map { it.substringBefore('=') }
            .toSet()
        check(lockedComponents.isNotEmpty()) {
            "Root build-plugin lock contains no classpath components"
        }
        check(resolvedComponents == lockedComponents) {
            val missing = (resolvedComponents - lockedComponents).sorted()
            val stale = (lockedComponents - resolvedComponents).sorted()
            "Root build-plugin lock does not match the resolved classpath; " +
                "missing=$missing, stale=$stale"
        }

        val checked = mutableSetOf<String>()
        val violations = mutableListOf<String>()
        resolvedComponents.forEach { component ->
            val module = component.substringBeforeLast(':')
            val version = component.substringAfterLast(':')
            val minimum = when (module.substringBefore(':')) {
                "org.bouncycastle" -> "1.85"
                else -> advisoryMinimumVersions[module]
            }
            if (minimum != null) {
                checked += module
                if (isVersionBelow(version, minimum)) {
                    violations += "$module:$version < $minimum"
                }
            }
        }
        check(checked.containsAll(required)) {
            "Root build-plugin security verification did not resolve: ${(required - checked).sorted()}"
        }
        check(violations.isEmpty()) {
            "Root build-plugin advisory floors failed: ${violations.sorted()}"
        }
        logger.lifecycle(
            "Root build-plugin lock verified for ${resolvedComponents.size} components; " +
                "advisory floors verified for ${checked.size} modules"
        )
    }
}

// `./gradlew check` is the repository's standard gate. Give the root project a
// check task so plugin-classpath verification runs alongside every subproject.
tasks.register("check") {
    group = "verification"
    description = "Runs root build-tool security and ABI-policy verification."
    dependsOn(verifyBuildPluginSecurityFloors)
    dependsOn(checkPublicConstantAbiPolicy)
}

val resolveAndLockAll = tasks.register("resolveAndLockAll") {
    group = "build setup"
    description = "Resolves every subproject check, library Dokka task, and the aggregate SBOM."
    doFirst {
        check(gradle.startParameter.isWriteDependencyLocks) {
            "resolveAndLockAll must be invoked with --write-locks"
        }
    }
    dependsOn(
        "cyclonedxBom",
    )
}

// Authorize lock writes from the resolved graph, not the spelling used on the
// command line. This covers abbreviated, qualified, indirect, and Tooling API
// task selection, and rejects partial lock rewrites through ordinary tasks.
gradle.taskGraph.whenReady {
    val lockRefreshInGraph = hasTask(resolveAndLockAll.get())
    check(lockRefreshInGraph == gradle.startParameter.isWriteDependencyLocks) {
        if (lockRefreshInGraph) {
            "resolveAndLockAll must be invoked with --write-locks"
        } else {
            "--write-locks may only be used with resolveAndLockAll"
        }
    }
}

// Keep coverage in sync with the actual project task model. Resolve the task
// set only after every project has registered its plugins and verification
// tasks. Projects without either task (currently the native Swift launcher
// project) are excluded naturally rather than by name.
gradle.projectsEvaluated {
    val dependencyConsumerTasks = subprojects.flatMap { subproject ->
        listOfNotNull(
            subproject.tasks.findByName("check"),
            subproject.tasks.findByName("dokkaGeneratePublicationHtml"),
        )
    }
    resolveAndLockAll.configure {
        dependsOn(dependencyConsumerTasks)
    }
}

val aggregateSbomGroup = group.toString()
val embeddedJmdnsVendorRelative = "library/p2p-transport-lan/vendor/jmdns"
val embeddedJmdnsVendor = layout.projectDirectory.dir(embeddedJmdnsVendorRelative)
// Resolve the actual producer output only for the selected aggregate task.
// An unconditional projectsEvaluated lookup would break unrelated CoD builds.
val embeddedJmdnsArchive = providers.provider {
    project(":p2p-transport-lan").tasks.named<Jar>("embeddedJmdnsJar").get().archiveFile.get()
}
tasks.cyclonedxBom {
    dependsOn(":p2p-transport-lan:embeddedJmdnsJar")
    projectType.set(org.cyclonedx.model.Component.Type.LIBRARY)
    componentGroup = project.group.toString()
    componentName = rootProject.name
    componentVersion = project.version.toString()
    includeBomSerialNumber = false
    includeBuildSystem = false
    includeLicenseText = false
    jsonOutput.set(layout.buildDirectory.file("reports/cyclonedx/bom.json"))
    xmlOutput.set(layout.buildDirectory.file("reports/cyclonedx/bom.xml"))
    inputs.file(embeddedJmdnsArchive).withPropertyName("embeddedJmdnsProducer")
    inputs.files(fileTree(embeddedJmdnsVendor) {
        include("PROVENANCE.json", "src/main/**", "patches/**", "LICENSE", "NOTICE.txt", "MODIFICATIONS.txt")
    }).withPropertyName("embeddedJmdnsSources").withPathSensitivity(PathSensitivity.RELATIVE)

    // The plugin merges resolved Maven graphs, not privately embedded file-JAR
    // contents. Preserve that graph, join the four-module root, and explicitly
    // describe the owned modified producer rather than impersonating upstream.
    doLast {
        // Diff otherwise emits absent text as null, which is not a valid
        // CycloneDX attachment. Keep this URL-only representation schema-valid.
        @JsonInclude(JsonInclude.Include.NON_NULL)
        class ReferencedPatchDiff : Diff()

        fun boundedBytes(file: java.io.File): ByteArray {
            val limit = 16 * 1024 * 1024
            val bytes = file.inputStream().use { it.readNBytes(limit + 1) }
            check(bytes.isNotEmpty() && bytes.size <= limit) { "Invalid embedded JmDNS input: $file" }
            return bytes
        }
        fun sha256(bytes: ByteArray) = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes))
        fun requiredText(node: JsonNode, name: String): String {
            val value = node.path(name)
            check(value.isTextual && value.textValue().isNotBlank()) { "Invalid JmDNS provenance field: $name" }
            return value.textValue()
        }
        val vendorRoot = embeddedJmdnsVendor.asFile.toPath()
        fun vendorFile(relative: String): java.io.File {
            val path = java.nio.file.Path.of(relative)
            check(
                !path.isAbsolute && !relative.contains('\\') && relative.matches(Regex("[A-Za-z0-9_./-]+")) &&
                    path.normalize().toString().replace(java.io.File.separatorChar, '/') == relative &&
                    path.none { it.toString() == ".." }
            ) { "Unsafe embedded JmDNS provenance path" }
            var current = vendorRoot
            for (part in path) {
                current = current.resolve(part)
                check(!Files.isSymbolicLink(current)) { "Symlinked embedded JmDNS input" }
            }
            check(Files.isRegularFile(current)) { "Missing embedded JmDNS input: $relative" }
            return current.toFile()
        }
        val manifestBytes = boundedBytes(vendorFile("PROVENANCE.json"))
        val manifest = ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readTree(manifestBytes)
        check(manifest.path("schema").isIntegralNumber && manifest.path("schema").intValue() == 2) {
            "Unsupported embedded JmDNS provenance schema"
        }
        check(manifest.path("sources").isArray && manifest.path("resources").isArray) {
            "Missing embedded JmDNS source/resource roster"
        }
        val patchRecord = manifest.path("lifecyclePatch")
        check(requiredText(patchRecord, "path") == "patches/410-lifecycle.patch") {
            "Unexpected embedded JmDNS lifecycle patch"
        }
        val followupPatchArray = manifest.path("followupPatches")
        check(followupPatchArray.isArray) { "Missing embedded JmDNS followup patch roster" }
        val followupPatchRecords = followupPatchArray.toList()
        check(
            followupPatchRecords.map { requiredText(it, "path") } == listOf(
                "patches/415-opt-rcode.patch",
                "patches/416-reverse-domain.patch",
            )
        ) {
            "Unexpected embedded JmDNS followup patch order or membership"
        }
        val patchRecords = listOf(patchRecord) + followupPatchRecords
        val records = manifest.path("sources").toList() + manifest.path("resources").toList() + patchRecords
        for (record in records) {
            val expected = requiredText(record, "sha256")
            check(expected.matches(Regex("[0-9a-f]{64}"))) { "Invalid embedded JmDNS source digest" }
            check(sha256(boundedBytes(vendorFile(requiredText(record, "path")))) == expected) {
                "Embedded JmDNS source/resource/patch bytes differ from provenance"
            }
        }
        val identity = manifest.path("component")
        val upstream = manifest.path("upstream")
        val upstreamRef = requiredText(upstream, "purl")
        check(upstreamRef == "pkg:maven/org.jmdns/jmdns@3.6.3") { "Unexpected embedded JmDNS ancestor" }
        val upstreamCommit = requiredText(upstream, "commit")
        val sourceUrl = requiredText(upstream, "sourceUrl")
        val sourceSha256 = requiredText(upstream, "sourceSha256")
        val ancestor = Component().apply {
            type = Component.Type.LIBRARY
            bomRef = upstreamRef
            group = "org.jmdns"
            name = "jmdns"
            version = "3.6.3"
            purl = upstreamRef
            hashes = listOf(Hash(Hash.Algorithm.SHA_256, requiredText(upstream, "binarySha256")))
            externalReferences = listOf(
                ExternalReference().apply {
                    type = ExternalReference.Type.SOURCE_DISTRIBUTION
                    url = sourceUrl
                    hashes = listOf(Hash(Hash.Algorithm.SHA_256, sourceSha256))
                },
                ExternalReference().apply {
                    type = ExternalReference.Type.VCS
                    url = "https://github.com/jmdns/jmdns/tree/$upstreamCommit"
                },
            )
        }
        val embeddedRef = requiredText(identity, "bomRef")
        val provenanceProperties = sortedMapOf(
            "hash-scope" to "private-producer-jar",
            "namespace" to requiredText(manifest.path("relocation"), "to"),
            "provenance-path" to "$embeddedJmdnsVendorRelative/PROVENANCE.json",
            "source-manifest-sha256" to sha256(manifestBytes),
            "upstream-source-sha256" to sourceSha256,
            "lifecycle-patch-sha256" to requiredText(patchRecord, "sha256"),
            "upstream-commit" to upstreamCommit,
            "upstream-tree" to requiredText(upstream, "tree"),
        )
        for (patch in followupPatchRecords) {
            val path = requiredText(patch, "path")
            provenanceProperties["followup-patch-sha256:$path"] = requiredText(patch, "sha256")
        }
        val embedded = Component().apply {
            type = Component.Type.LIBRARY
            bomRef = embeddedRef
            group = requiredText(identity, "group")
            name = requiredText(identity, "name")
            version = requiredText(identity, "version")
            purl = requiredText(identity, "purl")
            // This is the owned producer JAR, not the upstream JAR or outer publication.
            hashes = listOf(Hash(Hash.Algorithm.SHA_256, sha256(boundedBytes(embeddedJmdnsArchive.get().asFile))))
            modified = true
            pedigree = Pedigree().apply {
                ancestors = Ancestors().apply { components = listOf(ancestor) }
                patches = patchRecords.map { patch ->
                    val path = requiredText(patch, "path")
                    Patch().apply {
                        type = Patch.Type.UNOFFICIAL
                        diff = ReferencedPatchDiff().apply { url = "$embeddedJmdnsVendorRelative/$path" }
                    }
                }
            }
            properties = provenanceProperties.map { (key, value) ->
                CyclonedxProperty("p2pkit:embedded-jmdns:$key", value)
            }
        }
        val jsonFile = jsonOutput.get().asFile
        val xmlFile = xmlOutput.get().asFile
        val bom = BomParserFactory.createParser(jsonFile).parse(jsonFile)
        check(bom.components.orEmpty().none {
            it.name == "jmdns" || it.bomRef == embeddedRef || it.group == "unspecified"
        }) { "Unexpected upstream JmDNS or private file dependency in aggregate runtime graph" }
        val logging = bom.components.orEmpty().filter { it.group == "org.slf4j" && it.name == "slf4j-api" }
        check(logging.size == 1 && logging.single().version == "2.0.7") {
            "Expected the resolved LAN SLF4J API 2.0.7 dependency"
        }
        val loggingRef = requireNotNull(logging.single().bomRef) { "SLF4J component has no bom-ref" }
        bom.components = bom.components.orEmpty().plus(embedded).sortedBy { it.bomRef }
        val rootRef = requireNotNull(bom.metadata?.component?.bomRef) {
            "Aggregate SBOM root component has no bom-ref"
        }
        val publishedModules = setOf(
            "p2p-core",
            "p2p-transport-lan",
            "p2p-network-provisioning-android",
            "p2p-network-provisioning-desktop",
        )
        val moduleRefs = publishedModules.associateWith { moduleName ->
            val matches = bom.components.orEmpty().filter { component ->
                component.group == aggregateSbomGroup && component.name == moduleName
            }
            check(matches.size == 1) {
                "Aggregate SBOM expected one $moduleName component, found ${matches.size}"
            }
            requireNotNull(matches.single().bomRef) {
                "Aggregate SBOM component $moduleName has no bom-ref"
            }
        }

        val rootDependency = Dependency(rootRef).apply {
            dependencies = moduleRefs.values.sorted().map(::Dependency)
        }
        val lanRef = moduleRefs.getValue("p2p-transport-lan")
        val originalLan = bom.dependencies.orEmpty().filter { it.ref == lanRef }
        check(originalLan.size <= 1) { "Duplicate LAN dependency entry" }
        val lanTargets = originalLan.singleOrNull()?.dependencies.orEmpty().map { it.ref } + embeddedRef
        val lanDependency = Dependency(lanRef).apply {
            dependencies = lanTargets.distinct().sorted().map(::Dependency)
        }
        val embeddedDependency = Dependency(embeddedRef).apply {
            dependencies = listOf(Dependency(loggingRef))
        }
        bom.dependencies = bom.dependencies.orEmpty()
            .filterNot { it.ref == rootRef || it.ref == lanRef }
            .plus(listOf(rootDependency, lanDependency, embeddedDependency))
            .sortedBy { it.ref }
        CyclonedxUtils.writeJsonBom(schemaVersion.get(), bom, jsonFile)
        CyclonedxUtils.writeXmlBom(schemaVersion.get(), bom, xmlFile)
    }
}

// AUDIT-2026-06 / RC-readiness: wire artifact signing + a robust publish→sign
// task dependency for every module that publishes (those applying
// `maven-publish`). Centralized here so the four library modules stay identical
// and only their POM differs.
//
// Signing is required when an in-memory PGP key is supplied, or when
// releasePublication=true (which also requires a non-empty key password).
// Configure signingInMemoryKey or signingInMemoryKeyBase64, never both;
// corresponding ORG_GRADLE_PROJECT_* environment variables are accepted.
// Ordinary keyless dev/CI builds skip Sign tasks. See
// docs/releasing/maven-central.md for the signing variables and local bundle
// recipe, and docs/releasing/checklist.md for the complete release gates.
subprojects {
    val sub = this

    // Embed the canonical license in Jar outputs (main, native metadata, sources and Dokka)
    // and Android AARs. Kotlin/Native KLIBs are not Jar tasks and are not
    // rewritten here; their license metadata is in the sibling POM. See
    // docs/releasing/checklist.md#archive-license-policy for scope and checks.
    tasks.withType(Jar::class.java).configureEach {
        from(rootProject.layout.projectDirectory.file("LICENSE")) {
            into("META-INF")
            rename { "LICENSE" }
        }
    }
    tasks.withType(BundleAar::class.java).configureEach {
        from(rootProject.layout.projectDirectory.file("LICENSE")) {
            into("META-INF")
            rename { "LICENSE" }
        }
    }

    tasks.matching {
        it.name in setOf("iosSimulatorArm64Test", "iosX64Test") ||
            it.name in serializedJvmNetworkTestTasks[sub.path].orEmpty()
    }.configureEach {
        usesService(networkIntegrationTestService)
    }

    // REL-GATE-01 (BUILD-14): warnings are regressions, not informational
    // output. Apply this to every Kotlin target (including common tests and
    // native compilations) and to Java sources such as Android/buildSrc-facing
    // helpers. Gradle's own deprecation warnings are promoted separately in
    // gradle.properties.
    tasks.withType(KotlinCompilationTask::class.java).configureEach {
        compilerOptions.allWarningsAsErrors.set(true)
    }
    tasks.withType(JavaCompile::class.java).configureEach {
        options.compilerArgs.add("-Werror")
    }

    plugins.withId("maven-publish") {
        sub.apply(plugin = "signing")
        val publishing = sub.extensions.getByType(PublishingExtension::class.java)
        sub.extensions.configure(SigningExtension::class.java) {
            val signingKey = (sub.findProperty("signingInMemoryKey") as String?)
                ?.takeUnless(String::isBlank)
            val signingKeyBase64 = (sub.findProperty("signingInMemoryKeyBase64") as String?)
                ?.takeUnless(String::isBlank)
            val signingPassword = (sub.findProperty("signingInMemoryKeyPassword") as String?)
                ?.takeUnless(String::isBlank)
            val releasePublication = sub.findProperty("releasePublication")
                ?.toString()
                ?.toBooleanStrictOrNull()
                ?: false
            check(signingKey == null || signingKeyBase64 == null) {
                "Configure only one of signingInMemoryKey or signingInMemoryKeyBase64"
            }
            val decodedSigningKey = signingKey ?: signingKeyBase64?.let { encoded ->
                try {
                    String(Base64.getDecoder().decode(encoded.trim()), Charsets.UTF_8)
                } catch (error: IllegalArgumentException) {
                    throw GradleException("signingInMemoryKeyBase64 is not valid base64", error)
                }
            }
            if (releasePublication) {
                check(!decodedSigningKey.isNullOrBlank()) {
                    "Release publication requires an in-memory PGP signing key"
                }
                check(!signingPassword.isNullOrBlank()) {
                    "Release publication requires a non-empty signing key password"
                }
            }
            isRequired = releasePublication || decodedSigningKey != null
            if (decodedSigningKey != null) {
                useInMemoryPgpKeys(decodedSigningKey, signingPassword)
            }
            // Live collection — also covers KMP's per-target publications,
            // which the multiplatform plugin creates lazily in afterEvaluate.
            sign(publishing.publications)
        }
        // Gradle flags sign→publish ordering unless declared. Make every publish
        // task depend on all Sign tasks so `publish` works without the "uses
        // output of task … without declaring dependency" execution error.
        sub.tasks.withType(AbstractPublishToMaven::class.java).configureEach {
            dependsOn(sub.tasks.withType(Sign::class.java))
        }

        // REL-SUPPLY-01 (BUILD-13): every published variant gets real Dokka
        // Javadoc rather than a formally present but empty archive. One Jar
        // per publication keeps signing outputs disjoint even though all jars
        // consume the same module-level Dokka output.
        plugins.withId("org.jetbrains.dokka") {
            publishing.publications.withType(MavenPublication::class.java).configureEach {
                val publicationName = name
                val javadocJar = sub.tasks.register(
                    "${publicationName}DokkaJavadocJar",
                    Jar::class.java,
                ) {
                    dependsOn("dokkaGeneratePublicationHtml")
                    from(sub.layout.buildDirectory.dir("dokka/html"))
                    archiveClassifier.set("javadoc")
                    archiveAppendix.set(publicationName.lowercase())
                }
                artifact(javadocJar)
            }
        }
    }
}
