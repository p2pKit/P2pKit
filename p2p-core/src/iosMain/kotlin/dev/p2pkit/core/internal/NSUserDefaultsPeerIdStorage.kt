package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
import platform.Foundation.NSUserDefaults

/**
 * iOS [PeerIdStorage] backed by `NSUserDefaults.standardUserDefaults`.
 *
 * NSUserDefaults persists across app launches, survives iOS upgrades, and is
 * cleared on app uninstall — matching the on-uninstall semantics of the
 * Android `filesDir`-based storage. Unlike Android, iOS apps always have
 * writable app-scoped storage, so there is no init-context dance and no
 * in-memory fallback.
 *
 * The key is namespaced by [AppId] so multiple P2pKit-consuming apps in the
 * same bundle (rare) would not collide.
 *
 * Internal — apps don't construct this directly; [defaultPeerIdStorage]
 * routes here on iOS.
 */
internal class NSUserDefaultsPeerIdStorage(
    appId: AppId,
    private val logger: P2pLogger,
    private val defaults: NSUserDefaults = NSUserDefaults.standardUserDefaults
) : PeerIdStorage {

    private val key: String = "dev.p2pkit.peerId.${sanitizeAppIdForKey(appId.value)}"

    override fun loadOrGenerate(): PeerId {
        val existing = readExistingOrNull()
        if (existing != null) return existing
        return generateAndPersist()
    }

    private fun readExistingOrNull(): PeerId? {
        val raw = defaults.stringForKey(key) ?: return null
        val trimmed = raw.trim()
        return if (trimmed.isEmpty()) null else PeerId(trimmed)
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun generateAndPersist(): PeerId {
        val fresh = PeerId(Uuid.random().toString())
        try {
            defaults.setObject(fresh.value, key)
        } catch (e: Throwable) {
            logger.warn(
                "Failed to persist PeerId to NSUserDefaults under key $key; " +
                    "PeerId will not survive restart",
                e
            )
        }
        return fresh
    }
}

/**
 * Reduce a raw appId to a safe `NSUserDefaults` key suffix.
 *
 * Keeps `[A-Za-z0-9._-]`, replaces anything else with `_`, collapses any
 * `..` to `._` (parallels [sanitizeAppIdForFilesystem] on JVM/Android), and
 * caps the result at 64 characters.
 */
internal fun sanitizeAppIdForKey(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
