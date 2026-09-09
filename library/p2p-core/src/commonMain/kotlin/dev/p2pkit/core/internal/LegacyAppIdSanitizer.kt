package dev.p2pkit.core.internal

/**
 * Frozen compatibility mapping for deprecated plaintext UUID PeerId storage.
 * JVM/Android use it to locate legacy migration inputs; iOS also uses it for
 * its current NSUserDefaults bucket and lock names. Hashed writable entries
 * distinguish AppIds even when these legacy segments intentionally collide.
 *
 * Iterate UTF-16 Chars, retaining Unicode letters/digits and `[._-]`, replace
 * other chars with `_`, replace non-overlapping `..` with `._`, trim leading
 * dots, fall back to `_`, then take 64 chars. Do not normalize Unicode, change
 * the order, or "fix" collisions without a migration for historical paths/keys.
 * This is not the authenticated-v2 identity namespace or fingerprint mapping.
 */
internal fun sanitizeAppIdLegacySegment(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
