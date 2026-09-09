package dev.p2pkit.core.testfixtures

import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** A failed safe cast is read-only-interface evidence, on JVM as well as Native. */
internal fun <E> assertCannotAdd(list: List<E>, value: E) {
    val retained = list.toList()
    val mutable = list as? MutableList<E>
    if (mutable != null) assertFailsWith<UnsupportedOperationException> { mutable.add(value) }
    assertEquals(retained, list)
}

internal fun <E> assertCannotAdd(set: Set<E>, value: E) {
    val retained = set.toSet()
    val mutable = set as? MutableSet<E>
    if (mutable != null) assertFailsWith<UnsupportedOperationException> { mutable.add(value) }
    assertEquals(retained, set)
}

internal fun <E> assertCannotClear(list: List<E>) {
    val retained = list.toList()
    val mutable = list as? MutableList<E>
    if (mutable != null) assertFailsWith<UnsupportedOperationException> { mutable.clear() }
    assertEquals(retained, list)
}

internal fun <K, V> assertCannotClear(map: Map<K, V>) {
    val retained = map.toMap()
    val mutable = map as? MutableMap<K, V>
    if (mutable != null) assertFailsWith<UnsupportedOperationException> { mutable.clear() }
    assertEquals(retained, map)
}

internal fun <K, V> assertCannotPut(map: Map<K, V>, key: K, value: V) {
    val retained = map.toMap()
    val mutable = map as? MutableMap<K, V>
    if (mutable != null) assertFailsWith<UnsupportedOperationException> { mutable[key] = value }
    assertEquals(retained, map)
}
