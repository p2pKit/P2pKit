plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(libs.kotlinx.serialization.json)
    testImplementation(kotlin("test"))
}

tasks.register<JavaExec>("generateDiagnosticEvidenceSamples") {
    description = "Generate synthetic pass/fail evidence packages for every sample platform."
    group = "verification"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("dev.p2pkit.sample.diagnostics.SampleEvidenceGeneratorKt")
    args(layout.buildDirectory.dir("sample-evidence").get().asFile.absolutePath)
}
