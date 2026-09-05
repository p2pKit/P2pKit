package dev.p2pkit.sample.diagnostics

/**
 * SDK-owner-aware access to a sample's observable offer/row list. Confine calls
 * to the UI thread, just like the backing list. In particular, take consent
 * entries before launching a suspending action so repeated clicks do nothing.
 */
public class SessionTransferList<T>(
    private val entries: MutableList<T>,
    private val keyOf: (T) -> SessionTransferKey
) {
    public operator fun get(key: SessionTransferKey): T? = entries.firstOrNull { keyOf(it) == key }

    public fun take(key: SessionTransferKey): T? {
        val index = entries.indexOfFirst { keyOf(it) == key }
        return if (index < 0) null else entries.removeAt(index)
    }

    public fun update(key: SessionTransferKey, transform: (T) -> T) {
        val index = entries.indexOfFirst { keyOf(it) == key }
        if (index >= 0) entries[index] = transform(entries[index])
    }

    /** Removes only this collector's entries, never another session's same IDs. */
    public fun remove(sessionId: String, transferIds: Set<String>) {
        entries.removeAll { keyOf(it).let { key -> key.sessionId == sessionId && key.transferId in transferIds } }
    }
}
