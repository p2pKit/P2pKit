package dev.p2pkit.sample.rpc.profile

/** Sample-owned filesystem boundary. No provider may silently substitute weaker persistence. */
internal interface ProtectedProfileSession : AutoCloseable {
    val root: ProtectedProfileDirectory
}

internal interface ProtectedProfileLease : AutoCloseable

/** Every operation is relative to an admitted directory; no caller-provided native handles or absolute children. */
internal interface ProtectedProfileDirectory {
    val mutexIdentity: Any
    fun verifyIdentity(): Any
    fun fileIdentity(name: String): Any
    fun exists(name: String): Boolean
    fun names(): Set<String>
    fun child(name: String, create: Boolean = false): ProtectedProfileDirectory
    fun read(name: String, maximum: Int = 262_144): ByteArray
    fun write(name: String, bytes: ByteArray, replace: Boolean = false)
    fun lock(name: String, nonBlocking: Boolean = false): ProtectedProfileLease
    /** Supplied custody must reach the provider's deletion boundary, not be replaced by a newer observation. */
    fun delete(name: String, expectedIdentity: Any? = null): Boolean
    fun sync()
    fun deleteIfEmpty()
}

internal fun profileComponent(name: String): String {
    require(name.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,95}"))) { "Invalid profile component" }
    require(!name.endsWith('.') && name.substringBefore('.').uppercase() !in setOf(
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    )) { "Reserved profile component" }
    return name
}
