package dev.p2pkit.core.testfixtures

import kotlin.concurrent.atomics.AtomicReference
import kotlin.concurrent.atomics.ExperimentalAtomicApi

/**
 * Minimal thread-safe, append-only list for fixture bookkeeping (fixture
 * change F8 / TST-7): fixtures are mutated from the kit's multi-threaded
 * dispatchers while tests read the recorded state from the test thread, so
 * recorded state needs atomic publication. Copy-on-write keeps every read a
 * consistent snapshot without locking.
 */
@OptIn(ExperimentalAtomicApi::class)
internal class SnapshotList<T> {
    private val ref = AtomicReference<List<T>>(emptyList())

    fun add(element: T) {
        while (true) {
            val current = ref.load()
            if (ref.compareAndSet(current, current + element)) return
        }
    }

    fun snapshot(): List<T> = ref.load()
}
