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
import org.cyclonedx.model.Dependency
import org.cyclonedx.parsers.BomParserFactory
import org.jetbrains.kotlin.gradle.tasks.KotlinCompilationTask
import com.android.build.gradle.tasks.BundleAar
import kotlinx.validation.KotlinApiBuildTask
import kotlinx.validation.KotlinApiCompareTask
import java.util.Base64

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
    description = "Runs root build-tool security verification."
    dependsOn(verifyBuildPluginSecurityFloors)
}

val resolveAndLockRequested = gradle.startParameter.taskNames.any {
    it == "resolveAndLockAll" || it.endsWith(":resolveAndLockAll")
}
if (resolveAndLockRequested && !gradle.startParameter.isWriteDependencyLocks) {
    error("resolveAndLockAll must be invoked with --write-locks")
}

tasks.register("resolveAndLockAll") {
    group = "build setup"
    description = "Runs every dependency-consuming gate; invoke only with --write-locks."
    doFirst {
        check(gradle.startParameter.isWriteDependencyLocks) {
            "resolveAndLockAll must be invoked with --write-locks"
        }
    }
    dependsOn(
        verifyBuildPluginSecurityFloors,
        "cyclonedxBom",
        ":p2p-core:check",
        ":p2p-transport-lan:check",
        ":p2p-network-provisioning-android:check",
        ":p2p-network-provisioning-desktop:check",
        ":p2p-sample-diagnostics:check",
        ":p2p-sample-android:check",
        ":p2p-sample-desktop:check",
        ":p2p-sample-desktop-ui:check",
        ":sample-kmp-shared:check",
        ":p2p-core:dokkaGeneratePublicationHtml",
        ":p2p-transport-lan:dokkaGeneratePublicationHtml",
        ":p2p-network-provisioning-android:dokkaGeneratePublicationHtml",
        ":p2p-network-provisioning-desktop:dokkaGeneratePublicationHtml",
    )
}

val aggregateSbomGroup = group.toString()
tasks.cyclonedxBom {
    projectType.set(org.cyclonedx.model.Component.Type.LIBRARY)
    componentGroup = project.group.toString()
    componentName = rootProject.name
    componentVersion = project.version.toString()
    includeBomSerialNumber = false
    includeBuildSystem = false
    includeLicenseText = false
    jsonOutput.set(layout.buildDirectory.file("reports/cyclonedx/bom.json"))
    xmlOutput.set(layout.buildDirectory.file("reports/cyclonedx/bom.xml"))

    // CycloneDX's aggregate task merges each subproject graph but does not
    // connect its synthetic root component to those subprojects. Add the four
    // published modules as the exact top-level dependency set so consumers can
    // traverse the aggregate SBOM instead of receiving a disconnected graph.
    doLast {
        val jsonFile = jsonOutput.get().asFile
        val xmlFile = xmlOutput.get().asFile
        val bom = BomParserFactory.createParser(jsonFile).parse(jsonFile)
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
        }.values.sorted()

        val rootDependency = Dependency(rootRef).apply {
            dependencies = moduleRefs.map(::Dependency)
        }
        bom.dependencies = bom.dependencies.orEmpty()
            .filterNot { it.ref == rootRef }
            .plus(rootDependency)
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
// Signing is REQUIRED only when a PGP key is supplied via Gradle properties or
// env vars (`ORG_GRADLE_PROJECT_signingInMemoryKey[+Password]` → the
// `signingInMemoryKey[+Password]` project properties). So `publishToMavenLocal`
// and ordinary dev/CI builds need no keys and are unaffected (Sign tasks are
// skipped); a Maven Central release just sets those two properties. See
// docs/STABILIZATION_AND_RELEASE.md for the release recipe.
subprojects {
    val sub = this

    // Every distributable archive carries the exact repository license. This
    // covers JVM/KMP metadata jars and Android KMP AARs without copying or
    // maintaining per-module legal text.
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
        it.name == "iosSimulatorArm64Test" ||
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
