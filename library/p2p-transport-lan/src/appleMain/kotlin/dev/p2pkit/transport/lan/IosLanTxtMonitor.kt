@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import kotlinx.cinterop.ByteVar
import kotlinx.cinterop.COpaquePointer
import kotlinx.cinterop.CPointer
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.StableRef
import kotlinx.cinterop.alloc
import kotlinx.cinterop.allocArray
import kotlinx.cinterop.asStableRef
import kotlinx.cinterop.get
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.readBytes
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.staticCFunction
import kotlinx.cinterop.value
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import platform.Foundation.NSLock
import platform.Network.nw_endpoint_t
import platform.darwin.DNSServiceConstructFullName
import platform.darwin.DNSServiceQueryRecord
import platform.darwin.DNSServiceRef
import platform.darwin.DNSServiceRefDeallocate
import platform.darwin.DNSServiceRefVar
import platform.darwin.DNSServiceSetDispatchQueue
import platform.darwin.dispatch_async
import platform.darwin.dispatch_queue_t
import platform.darwin.kDNSServiceClass_IN
import platform.darwin.kDNSServiceFlagsAdd
import platform.darwin.kDNSServiceFlagsIncludeP2P
import platform.darwin.kDNSServiceFlagsLongLivedQuery
import platform.darwin.kDNSServiceFlagsMoreComing
import platform.darwin.kDNSServiceInterfaceIndexAny
import platform.darwin.kDNSServiceType_TXT

/** Borrowed fields are accessed synchronously, and never at all after a nonzero error. */
internal data class IosLanTxtAnswer(
    val fullName: String?,
    val interfaceIndex: UInt,
    val rrType: UShort,
    val rrClass: UShort,
    val added: Boolean,
    val moreComing: Boolean,
    val length: ULong,
    val readBytes: (Int) -> ByteArray?
)

/** The small native-call seam retains the real query/queue/context ownership phases. */
internal interface IosLanTxtDns {
    interface Reference {
        fun schedule(): Int
        fun deallocate()
        fun disposeContext()
    }

    data class Start(val error: Int, val reference: Reference?)

    fun constructFullName(name: String, type: String, domain: String): String?
    fun start(fullName: String, callback: (Int, () -> IosLanTxtAnswer) -> Unit): Start
    fun enqueue(block: () -> Unit)
}

/** An opaque eligible NW endpoint remains the only route; DNS supplies an untrusted TXT claim. */
internal data class IosLanTxtService(
    val name: String,
    val type: String,
    val domain: String,
    val endpoint: nw_endpoint_t,
    val generation: Int
) {
    internal val key: List<String> get() = listOf(name, type, domain)
}

/**
 * One bounded live RRset per current NW incarnation. All mutable state uses the discovery
 * transaction lock. Native calls and decoding are outside it; publication rechecks the exact
 * owner/revision under that same lock. No DNS result constructs or selects a network route.
 */
internal class IosLanTxtMonitor(
    private val stateLock: NSLock,
    private val dns: IosLanTxtDns,
    private val isCurrentGenerationLocked: (Int) -> Boolean,
    private val onSnapshot: (Snapshot) -> Unit,
    private val onWithdrawLocked: (Owner) -> Unit
) {
    internal class Reservation {
        internal var current: Owner? = null
        internal var replacement: Owner? = null
    }

    internal class Owner internal constructor(
        val service: IosLanTxtService,
        internal val reservation: Reservation
    ) {
        var fullName: String = ""
            internal set
        internal var active = true
        internal var ambiguous = false
        internal var revision = 0L
        internal var pending = false
        internal var batchCallbacks = 0
        internal var guardQueued = false
        internal var closeQueued = false
        internal var released = false
        internal var reference: IosLanTxtDns.Reference? = null
        internal val records = mutableListOf<Record>()
    }

    internal data class Snapshot(
        val owner: Owner,
        val revision: Long,
        val pending: Boolean,
        val records: List<IosBonjour.DecodedRecord>
    )

    internal data class Record(
        val scope: UInt,
        val raw: ByteArray,
        val decoded: IosBonjour.DecodedRecord
    )

    private val owners = mutableMapOf<List<String>, Owner>()
    private var reservedQueries = 0
    private var allocatedReferences = 0
    private var retainedBytes = 0

    private inline fun <T> locked(block: () -> T): T {
        stateLock.lock()
        return try { block() } finally { stateLock.unlock() }
    }

    /** Capture at NW callback entry, before decoding, query creation or an asynchronous hop. */
    fun capture(service: IosLanTxtService): Owner? = locked {
        owners[service.key]?.takeIf { it.service.generation == service.generation }
    }

    /** A fresh Add is not authority to overwrite an already represented native owner. */
    fun add(service: IosLanTxtService): Owner? = transition(null, service)

    /** A recognized old->new transition/removal can act only on its captured immutable token. */
    fun replace(expected: Owner, service: IosLanTxtService?): Owner? = transition(expected, service)

    private fun transition(expected: Owner?, service: IosLanTxtService?): Owner? {
        val closing = mutableListOf<Owner>()
        var startNow = false
        val created = locked {
            val generation = service?.generation ?: expected?.service?.generation ?: return@locked null
            if (!isCurrentGenerationLocked(generation)) return@locked null
            val handoff = expected?.reservation?.takeIf {
                it.current != null && (it.current === expected || it.replacement === expected)
            }
            if (expected != null) {
                if (owners[expected.service.key] !== expected || expected.ambiguous) return@locked null
                owners.remove(expected.service.key)
                invalidateLocked(expected, withdraw = true)
                closing += expected
            }
            if (service == null) return@locked null
            // Check contradictions BEFORE a capacity rejection. An unretained extra owner must
            // not disappear behind the cap while the conflicting admitted peer stays dialable.
            val conflicts = owners.values.filter { it.service.name == service.name }
            if (conflicts.isNotEmpty()) {
                conflicts.forEach {
                    it.ambiguous = true
                    invalidateLocked(it, withdraw = true)
                    closing += it
                }
                return@locked null
            }
            if (owners.size >= MAX_TRACKED_LAN_PEERS ||
                (handoff == null && reservedQueries >= MAX_TRACKED_LAN_PEERS)
            ) {
                return@locked null
            }
            val reservation = handoff ?: Reservation().also { reservedQueries++ }
            Owner(service, reservation).also {
                owners[service.key] = it
                if (handoff == null) {
                    reservation.current = it
                    startNow = true
                } else {
                    // One captured transition owns this slot. Superseding a pending replacement
                    // changes only its successor, never releases the still-live native owner.
                    reservation.replacement = it
                }
            }
        }
        closing.forEach(::closeLater)
        created?.takeIf { startNow }?.let { owner ->
            try {
                dns.enqueue { startOnQueue(owner) }
            } catch (_: Throwable) {
                fail(owner)
            }
        }
        return created
    }

    /** Caller holds the discovery transaction lock; no native calls or suspension here. */
    fun isCurrentLocked(owner: Owner, revision: Long? = null): Boolean =
        owner.active && !owner.ambiguous && owners[owner.service.key] === owner &&
            isCurrentGenerationLocked(owner.service.generation) &&
            (revision == null || revision == owner.revision)

    /** Preserve the existing generation-grace cache policy; its endpoint is cleared by discovery. */
    fun invalidateAllLocked(): List<Owner> {
        val previous = owners.values.toList()
        owners.clear()
        previous.forEach { invalidateLocked(it, withdraw = false) }
        return previous
    }

    fun retire(owners: List<Owner>) = owners.forEach(::closeLater)

    /** Off-queue lifecycle callers await native deallocation AND the later context-disposal turn. */
    suspend fun drain() = withContext(NonCancellable) {
        val done = CompletableDeferred<Unit>()
        dns.enqueue { dns.enqueue { done.complete(Unit) } }
        done.await()
    }

    fun withdraw(snapshot: Snapshot) = locked {
        if (isCurrentLocked(snapshot.owner, snapshot.revision)) onWithdrawLocked(snapshot.owner)
    }

    fun snapshotForTest(pid: String): Snapshot? = locked {
        owners.values.singleOrNull { it.service.name == pid }?.let(::snapshotLocked)
    }

    val queryCountForTest: Int get() = locked { allocatedReferences }
    val reservedQueryCountForTest: Int get() = locked { reservedQueries }
    val retainedBytesForTest: Int get() = locked { retainedBytes }

    private fun snapshotLocked(owner: Owner) = Snapshot(
        owner, owner.revision, owner.pending, owner.records.map { it.decoded }
    )

    private fun startOnQueue(owner: Owner) {
        if (!locked { isCurrentLocked(owner) }) return
        try {
            val fullName = dns.constructFullName(owner.service.name, owner.service.type, owner.service.domain)
            if (fullName.isNullOrEmpty() || fullName.encodeToByteArray().size > 1008) {
                fail(owner)
                return
            }
            val mayStart = locked {
                owner.fullName = fullName
                isCurrentLocked(owner)
            }
            if (!mayStart) return
            val start = dns.start(fullName) { error, fields -> receive(owner, error, fields) }
            if (start.error != 0 || start.reference == null) {
                // An error has no valid output reference. Real adapter disposes only its context.
                fail(owner)
                return
            }
            val reference = start.reference
            val stillCurrent = locked {
                owner.reference = reference
                allocatedReferences++
                isCurrentLocked(owner)
            }
            if (!stillCurrent || reference.schedule() != 0) fail(owner)
        } catch (_: Throwable) {
            fail(owner)
        }
    }

    private fun receive(owner: Owner, error: Int, fields: () -> IosLanTxtAnswer) {
        // In a DNS-SD error callback every field other than error/context is undefined.
        if (error != 0) {
            fail(owner)
            return
        }
        val atEntry = locked { owner.revision.takeIf { isCurrentLocked(owner) } } ?: return
        try {
            val answer = fields()
            if (answer.fullName != owner.fullName || answer.rrType != 16.toUShort() ||
                answer.rrClass != 1.toUShort()
            ) {
                fail(owner)
                return
            }
            var raw: ByteArray? = if (answer.length == 0UL) ByteArray(0) else null
            val properties = decodeLanTxtRecord(answer.length) { count ->
                answer.readBytes(count)?.copyOf()?.also { raw = it }
            }
            val bytes = raw
            if (bytes == null || bytes.size.toULong() != answer.length) {
                fail(owner)
                return
            }
            val decoded = IosBonjour.DecodedRecord(properties.orEmpty(), malformed = properties == null)
            var queueGuard = false
            var overflow = false
            val snapshot = locked {
                if (!isCurrentLocked(owner, atEntry)) return@locked null
                owner.batchCallbacks++
                val previous = owner.records.indexOfFirst {
                    it.scope == answer.interfaceIndex && it.raw.contentEquals(bytes)
                }
                if (owner.batchCallbacks > 64 || (answer.added && previous < 0 &&
                    (owner.records.size >= 8 || retainedBytes + bytes.size > 8 * 1024 * 1024))
                ) {
                    // Never keep an old accepted/truncated set after dropping a contradictory RR.
                    invalidateLocked(owner, withdraw = true)
                    overflow = true
                    return@locked null
                }
                if (answer.added && previous < 0) {
                    owner.records += Record(answer.interfaceIndex, bytes, decoded)
                    retainedBytes += bytes.size
                } else if (!answer.added && previous >= 0) {
                    retainedBytes -= owner.records.removeAt(previous).raw.size
                }
                owner.revision++
                owner.pending = answer.moreComing
                if (owner.pending) {
                    if (!owner.guardQueued) {
                        owner.guardQueued = true
                        queueGuard = true
                    }
                    null
                } else {
                    owner.batchCallbacks = 0
                    snapshotLocked(owner)
                }
            }
            if (overflow) closeLater(owner)
            if (queueGuard) dns.enqueue { guardPendingBatch(owner) }
            if (snapshot != null) onSnapshot(snapshot)
        } catch (_: Throwable) {
            fail(owner)
        }
    }

    /** At most one queued guard per lease, reused for the current pending batch, not an old revision. */
    private fun guardPendingBatch(owner: Owner) = locked {
        owner.guardQueued = false
        if (isCurrentLocked(owner) && owner.pending) onWithdrawLocked(owner)
    }

    private fun invalidateLocked(owner: Owner, withdraw: Boolean) {
        owner.active = false
        owner.revision++
        owner.pending = false
        owner.batchCallbacks = 0
        retainedBytes -= owner.records.sumOf { it.raw.size }
        owner.records.clear()
        if (withdraw) onWithdrawLocked(owner)
    }

    private fun fail(owner: Owner) {
        locked {
            if (owners[owner.service.key] === owner) invalidateLocked(owner, withdraw = true)
        }
        closeLater(owner)
    }

    private fun closeLater(owner: Owner) {
        val enqueue = locked {
            if (owner.closeQueued || owner.released) false else {
                owner.closeQueued = true
                true
            }
        }
        if (enqueue) dns.enqueue { closeOnQueue(owner) }
    }

    private fun closeOnQueue(owner: Owner) {
        val reference = locked { owner.reference.also { owner.reference = null } }
        if (reference == null) {
            releaseReservation(owner)
            return
        }
        try {
            reference.deallocate()
        } catch (_: Throwable) {
            // Do not report retirement or hand this slot to a successor after a failed release.
            locked { owner.reference = reference }
            return
        }
        locked { allocatedReferences-- }
        // Not in the callback stack, and after the queued DNS source has been deallocated.
        dns.enqueue {
            try { reference.disposeContext() } catch (_: Throwable) { return@enqueue }
            releaseReservation(owner)
        }
    }

    private fun releaseReservation(owner: Owner) {
        val successor = locked {
            if (owner.released) return@locked null
            owner.released = true
            val reservation = owner.reservation
            if (reservation.current !== owner) {
                if (reservation.replacement === owner) reservation.replacement = null
                return@locked null
            }
            val next = reservation.replacement?.takeIf {
                !it.released && !it.closeQueued && isCurrentLocked(it)
            }
            reservation.current = next
            reservation.replacement = null
            if (next == null) reservedQueries--
            next
        }
        // This is the original recognized transition, not a retry or a new name-based lookup.
        successor?.let { dns.enqueue { startOnQueue(it) } }
    }
}

/** Copy a bounded DNS C string; no unbounded toKString access to native result fields. */
internal fun copyLanDnsString(bytes: CPointer<ByteVar>?, bound: Int = 1009): String? {
    if (bytes == null) return null
    var size = 0
    while (size < bound && bytes[size] != 0.toByte()) size++
    if (size == bound) return null
    return try { bytes.readBytes(size).decodeToString(throwOnInvalidSequence = true) } catch (_: Throwable) { null }
}

private class IosLanTxtCallbackContext(val callback: (Int, () -> IosLanTxtAnswer) -> Unit)

internal class PlatformIosLanTxtDns(private val queue: dispatch_queue_t) : IosLanTxtDns {

    override fun enqueue(block: () -> Unit) = dispatch_async(queue, block)

    override fun constructFullName(name: String, type: String, domain: String): String? = memScoped {
        val result = allocArray<ByteVar>(1009)
        if (DNSServiceConstructFullName(result, name, type, domain) != 0) null else copyLanDnsString(result)
    }

    override fun start(fullName: String, callback: (Int, () -> IosLanTxtAnswer) -> Unit): IosLanTxtDns.Start {
        val context = StableRef.create(IosLanTxtCallbackContext(callback))
        var transferred = false
        var untransferredRef: DNSServiceRef? = null
        try {
            return memScoped {
                val output = alloc<DNSServiceRefVar>()
                output.value = null
                val error = DNSServiceQueryRecord(
                    output.ptr,
                    kDNSServiceFlagsIncludeP2P or kDNSServiceFlagsLongLivedQuery,
                    kDNSServiceInterfaceIndexAny.toUInt(),
                    fullName,
                    kDNSServiceType_TXT.toUShort(),
                    kDNSServiceClass_IN.toUShort(),
                    staticCFunction(::iosLanTxtReply),
                    context.asCPointer()
                )
                // Do not inspect undefined output on synchronous error.
                if (error != 0) return@memScoped IosLanTxtDns.Start(error, null)
                val ref = output.value ?: return@memScoped IosLanTxtDns.Start(-1, null)
                untransferredRef = ref
                val reference = object : IosLanTxtDns.Reference {
                    private var deallocated = false
                    private var disposed = false

                    override fun schedule(): Int = DNSServiceSetDispatchQueue(ref, queue)

                    override fun deallocate() {
                        if (!deallocated) {
                            deallocated = true
                            DNSServiceRefDeallocate(ref)
                        }
                    }

                    override fun disposeContext() {
                        if (!disposed) {
                            disposed = true
                            context.dispose()
                        }
                    }
                }
                transferred = true
                IosLanTxtDns.Start(0, reference)
            }
        } finally {
            if (!transferred) {
                untransferredRef?.let { DNSServiceRefDeallocate(it) }
                context.dispose()
            }
        }
    }
}

@Suppress("UNUSED_PARAMETER")
private fun iosLanTxtReply(
    ref: DNSServiceRef?,
    flags: UInt,
    interfaceIndex: UInt,
    error: Int,
    fullName: CPointer<ByteVar>?,
    rrType: UShort,
    rrClass: UShort,
    length: UShort,
    data: COpaquePointer?,
    ttl: UInt,
    context: COpaquePointer?
) {
    var target: IosLanTxtCallbackContext? = null
    try {
        val current = context?.asStableRef<IosLanTxtCallbackContext>()?.get() ?: return
        target = current
        if (error != 0) {
            current.callback(error) { kotlin.error("Undefined DNS-SD error fields") }
        } else {
            current.callback(0) {
                IosLanTxtAnswer(
                    copyLanDnsString(fullName), interfaceIndex, rrType, rrClass,
                    (flags and kDNSServiceFlagsAdd) != 0u,
                    (flags and kDNSServiceFlagsMoreComing) != 0u,
                    length.toULong(),
                    { count -> data?.reinterpret<ByteVar>()?.readBytes(count) }
                )
            }
        }
    } catch (_: Throwable) {
        // Never cross the C ABI. Only the captured context identifies the unavailable lease.
        try { target?.callback(-1) { kotlin.error("Unavailable DNS-SD callback") } } catch (_: Throwable) { }
    }
}
