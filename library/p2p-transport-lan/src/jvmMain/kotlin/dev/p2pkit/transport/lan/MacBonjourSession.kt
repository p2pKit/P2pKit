package dev.p2pkit.transport.lan

import java.io.Closeable
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** At most one registration worker and two browsers during add-first refresh. No native callback enters Java. */
internal class MacBonjourWorker(
    private val initial: MacBonjourRef,
    private val work: (MacBonjourRef, () -> Boolean, () -> Unit) -> Unit,
    private val failed: (Throwable) -> Unit,
) : Closeable {
    @Volatile private var stopping = false
    @Volatile private var failure: Throwable? = null
    private val ready = CountDownLatch(1)
    private var thread: Thread? = null

    @Synchronized fun start(open: () -> Unit) {
        check(thread == null && !stopping)
        open()
        thread = Thread({
            try { work(initial, { !stopping }, { ready.countDown() }) }
            catch (error: Throwable) {
                failure = error
                ready.countDown()
                if (!stopping) failed(error)
            } finally {
                try { initial.close() } catch (error: Throwable) {
                    failure = error
                    if (!stopping) failed(error)
                }
                ready.countDown()
            }
        }, "p2pkit-scoped-bonjour").also { it.isDaemon = true; it.start() }
    }

    fun awaitRegistration() {
        if (!ready.await(5, TimeUnit.SECONDS)) throw IOException("Scoped Bonjour registration deadline exceeded")
        failure?.let { throw IOException("Scoped Bonjour registration rejected", it) }
        check(!stopping)
    }

    override fun close() {
        val worker = synchronized(this) { stopping = true; thread }
        if (worker === Thread.currentThread()) throw IOException("Bonjour worker cannot join itself")
        worker?.join(2_000)
        if (worker?.isAlive == true) throw IOException("Scoped Bonjour worker cleanup deadline exceeded")
        // Includes open failure, thread-start failure and repeated close after a prior native close failure.
        initial.close()
    }
}

/** Continuous browse lifetime with bounded/fair numeric-TXT re-resolution. Never performs host-name DNS. */
internal class MacBonjourBrowser(
    private val registration: LanServiceRegistration,
    private val policy: OrganizationLan,
    private val index: Int,
    private val api: MacBonjourCalls,
    private val publish: (String, MacBonjourEvent?) -> Unit,
    private val clock: () -> Long = System::nanoTime,
) {
    private class Entry(var attempted: Long = Long.MIN_VALUE) {
        var validated: Long? = null
        var query: MacBonjourRef? = null
    }
    private val entries = linkedMapOf<String, Entry>()

    fun run(browser: MacBonjourRef, running: () -> Boolean, ready: () -> Unit) {
        ready()
        try {
            while (running()) {
                repeat(16) {
                    browser.poll()?.let { event ->
                        check(event.kind == 1 || event.kind == 2)
                        if (event.name != registration.localPeerId.value) acceptBrowse(event)
                    }
                }
                val now = clock()
                // Timeout/invalid TXT explicitly withdraws previous admission; no stale dial endpoint is retained.
                entries.forEach { (name, entry) ->
                    val query = entry.query
                    if (query != null) {
                        val event = query.poll()
                        if (event != null || now - entry.attempted >= RESOLVE_NANOS) {
                            query.close()
                            entry.query = null
                            val valid = event?.takeIf { validateMacBonjourRecord(it, registration, policy) != null }
                            entry.validated = if (valid != null) now else null
                            publish(name, valid)
                        }
                    }
                    if (entry.validated?.let { now - it >= STALE_NANOS } == true) {
                        entry.validated = null
                        publish(name, null)
                    }
                }
                val available = MAX_RESOLVES - entries.values.count { it.query != null }
                entries.entries.asSequence().filter { (_, entry) ->
                    entry.query == null && (entry.attempted == Long.MIN_VALUE || now - entry.attempted >= REFRESH_NANOS)
                }.sortedBy { it.value.attempted }.take(available).forEach { (name, entry) ->
                    entry.attempted = now
                    val query = MacBonjourRef(api, index)
                    entry.query = query // Ownership before allocation or exception.
                    query.open(3, registration.protocolVersion, name)
                }
                Thread.sleep(25)
            }
        } finally {
            val failures = entries.values.mapNotNull { runCatching { it.query?.close() }.exceptionOrNull() }
            // Do not discard ownership on a close failure. The session retains this browser until verified retirement.
            if (failures.isNotEmpty()) throw IOException("Scoped Bonjour resolver cleanup failed", failures.first())
            entries.keys.forEach { publish(it, null) }
            entries.clear()
        }
    }

    fun verifyClosed() {
        entries.values.forEach { it.query?.close() }
        entries.clear()
    }

    private fun acceptBrowse(event: MacBonjourEvent) {
        when (event.kind) {
            1 -> if (event.name !in entries) {
                if (entries.size >= MAX_TRACKED_LAN_PEERS) throw IOException("Scoped Bonjour peer capacity exceeded")
                entries[event.name] = Entry()
            }
            2 -> {
                entries[event.name]?.query?.close()
                entries.remove(event.name)
                publish(event.name, null)
            }
        }
    }

    private companion object {
        const val MAX_RESOLVES = 8
        const val RESOLVE_NANOS = 2_000_000_000L
        const val REFRESH_NANOS = 3_000_000_000L
        const val STALE_NANOS = 10_000_000_000L
    }
}

internal fun validateMacBonjourRecord(
    event: MacBonjourEvent, registration: LanServiceRegistration, policy: OrganizationLan,
): ValidatedLanDiscoveryRecord? {
    if (event.kind != 3) return null
    val properties = decodeLanTxtRecord(event.txt) ?: return null
    val record = validateLanDiscoveryRecord(properties, registration.appId, registration.localPeerId,
        registration.securityProfile) ?: return null
    val endpoint = record.numericEndpoint ?: return null
    if (event.name != record.peerId.value || event.port != endpoint.port || !policy.allows(endpoint.host)) return null
    return record
}
