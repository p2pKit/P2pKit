package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.InboundConnectionAdmission
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Non-suspending, multiplatform admission counter used directly in native
 * socket callbacks and blocking JVM/Android accept loops.
 *
 * Entries exist only while at least one lease is held. [maxTrackedSources]
 * also bounds the map independently of caller queue behavior, so a stream of
 * attacker-controlled addresses cannot grow retained state without limit.
 */
internal class PerSourceAdmissionLimiter(
    private val maxPerSource: Int = MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE,
    private val maxTrackedSources: Int = MAX_TRACKED_PRE_HANDSHAKE_SOURCES
) {
    private val counts = MutableStateFlow<Map<String, Int>>(emptyMap())

    init {
        require(maxPerSource > 0) { "maxPerSource must be > 0" }
        require(maxTrackedSources > 0) { "maxTrackedSources must be > 0" }
    }

    fun tryAcquire(source: String): SourceAdmissionLease? {
        while (true) {
            val current = counts.value
            val held = current[source] ?: 0
            if (held >= maxPerSource) return null
            if (held == 0 && current.size >= maxTrackedSources) return null
            val updated = current + (source to held + 1)
            if (counts.compareAndSet(current, updated)) {
                return SourceAdmissionLease(source) { release(source) }
            }
        }
    }

    private fun release(source: String) {
        while (true) {
            val current = counts.value
            val held = current[source] ?: return
            val updated = if (held == 1) current - source else current + (source to held - 1)
            if (counts.compareAndSet(current, updated)) return
        }
    }

    internal fun heldForTest(source: String): Int = counts.value[source] ?: 0
    internal fun trackedSourcesForTest(): Int = counts.value.size
}

/** Exactly-once lease transferred with one accepted connection. */
internal class SourceAdmissionLease(
    val source: String,
    private val releaseAction: () -> Unit
) {
    private val held = MutableStateFlow(true)

    fun release() {
        if (held.compareAndSet(expect = true, update = false)) releaseAction()
    }
}

/** Core-visible wrapper for JVM/Android inbound connections. */
internal class AdmissionControlledRawConnection(
    private val delegate: RawConnection,
    private val lease: SourceAdmissionLease
) : RawConnection, InboundConnectionAdmission {
    override val admissionSource: String = lease.source
    override val state: StateFlow<dev.p2pkit.core.ConnectionState> = delegate.state

    override suspend fun write(bytes: ByteArray) = delegate.write(bytes)
    override fun read(): Flow<ByteArray> = delegate.read()

    override suspend fun close() {
        try {
            delegate.close()
        } finally {
            lease.release()
        }
    }

    override fun releasePreHandshakeAdmission() = lease.release()
}

/** One host may occupy only a small fraction of the core's global budget. */
internal const val MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE: Int = 2

/** Hard ceiling for attacker-selected keys retained by one transport instance. */
internal const val MAX_TRACKED_PRE_HANDSHAKE_SOURCES: Int = 96
