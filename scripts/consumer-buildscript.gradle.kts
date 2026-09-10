// Copied before the generated consumer's plugins block. This constrains only
// build tools, never the published library dependencies under test. The data
// file is the reviewed root lock, not a Gradle lock for this smaller graph:
// constraints do not introduce unrelated root plugins into the consumer.
buildscript {
    val lock = file("consumer-plugin-versions.lock")
    check(lock.isFile) { "Missing reviewed consumer plugin versions" }
    val lockBytes = lock.inputStream().use { it.readNBytes(1024 * 1024 + 1) }
    check(lockBytes.size <= 1024 * 1024) { "Oversized reviewed consumer plugin versions" }
    val reviewed = linkedMapOf<String, String>()
    val entry = Regex("([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)=classpath")
    lockBytes.toString(Charsets.UTF_8).lineSequence().forEach { line ->
        if (line.isBlank() || line.startsWith("#") || line == "empty=") return@forEach
        val match = checkNotNull(entry.matchEntire(line)) {
            "Malformed reviewed consumer plugin version: $line"
        }
        val (group, name, version) = match.destructured
        check(!version.startsWith("latest.")) { "Non-exact reviewed consumer plugin version: $line" }
        check(reviewed.put("$group:$name", version) == null) {
            "Duplicate reviewed consumer plugin module: $group:$name"
        }
    }
    check(reviewed.isNotEmpty()) { "No reviewed consumer plugin versions" }
    dependencies {
        constraints {
            reviewed.forEach { (module, expected) ->
                add("classpath", "$module:$expected") {
                    version { strictly(expected) }
                    because("Consumer build tools must use the reviewed root plugin graph")
                }
            }
        }
    }
    val classpath = configurations.getByName("classpath")
    classpath.resolutionStrategy.eachDependency {
        val module = "${requested.group}:${requested.name}"
        check(module in reviewed) { "Unreviewed consumer plugin dependency: $module" }
    }
    // Check the selected graph during resolution, before plugin application,
    // not in a task that would run only after unreviewed code had executed.
    classpath.incoming.afterResolve {
        val graph = classpath.incoming.resolutionResult
        val rootId = graph.rootComponent.get().id
        var count = 0
        graph.allComponents.forEach { component ->
            val id = component.id
            if (id != rootId) {
                check(id is org.gradle.api.artifacts.component.ModuleComponentIdentifier) {
                    "Non-module consumer plugin dependency: $id"
                }
                check(reviewed["${id.group}:${id.module}"] == id.version) {
                    "Consumer plugin selection differs from reviewed root lock: $id"
                }
                count += 1
            }
        }
        check(count > 0) { "Empty consumer plugin classpath" }
        logger.lifecycle(
            "Consumer plugin classpath: $count exact components from ${reviewed.size} reviewed root entries"
        )
    }
}
