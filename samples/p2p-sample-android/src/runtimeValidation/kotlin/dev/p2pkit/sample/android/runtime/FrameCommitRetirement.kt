package dev.p2pkit.sample.android.runtime

/** False means still owned: Android may have captured the callback but not executed it yet. */
internal fun frameCommitRetired(
    registered: Boolean,
    committed: () -> Boolean,
    unregister: () -> Boolean
): Boolean {
    if (!registered || committed()) return true
    return unregister() || committed()
}
