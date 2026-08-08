package dev.p2pkit.core.internal

/**
 * One-copy, read-only collection snapshots used at public ownership boundaries.
 *
 * Kotlin's standard `List`, `Set`, and `Map` types are read-only interfaces,
 * but `toList()`/`toSet()`/`toMap()` may still return a mutable implementation.
 * These wrappers never expose their private backing storage. Kotlin mutable
 * casts therefore fail where the runtime can distinguish them, and Java
 * mutation methods fail with [UnsupportedOperationException].
 */
internal fun <E> immutableListSnapshot(source: Iterable<E>): List<E> =
    ImmutableSnapshotList(source.toList())

internal fun <E> immutableSetSnapshot(source: Iterable<E>): Set<E> =
    ImmutableSnapshotSet(source.toList().distinct())

internal fun <K, V> immutableMapSnapshot(source: Map<K, V>): Map<K, V> =
    ImmutableSnapshotMap(source.entries.map { ImmutableSnapshotEntry(it.key, it.value) })

private class ImmutableSnapshotList<E>(
    private val elements: List<E>
) : AbstractList<E>() {
    override val size: Int get() = elements.size
    override fun get(index: Int): E = elements[index]
}

private class ImmutableSnapshotSet<E>(
    private val elements: List<E>
) : AbstractSet<E>() {
    override val size: Int get() = elements.size
    override fun contains(element: E): Boolean = elements.contains(element)
    override fun iterator(): Iterator<E> = SnapshotIterator(elements)
}

private class ImmutableSnapshotMap<K, V>(
    entries: List<Map.Entry<K, V>>
) : AbstractMap<K, V>() {
    override val entries: Set<Map.Entry<K, V>> = ImmutableSnapshotSet(entries)
}

private class ImmutableSnapshotEntry<K, V>(
    override val key: K,
    override val value: V
) : Map.Entry<K, V> {
    override fun equals(other: Any?): Boolean =
        other is Map.Entry<*, *> && key == other.key && value == other.value

    override fun hashCode(): Int = (key?.hashCode() ?: 0) xor (value?.hashCode() ?: 0)

    override fun toString(): String = "$key=$value"
}

private class SnapshotIterator<E>(
    private val elements: List<E>
) : Iterator<E> {
    private var index: Int = 0

    override fun hasNext(): Boolean = index < elements.size

    override fun next(): E {
        if (!hasNext()) throw NoSuchElementException()
        return elements[index++]
    }
}
