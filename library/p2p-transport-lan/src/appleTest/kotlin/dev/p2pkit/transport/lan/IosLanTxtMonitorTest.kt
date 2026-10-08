@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import platform.Network.nw_endpoint_create_bonjour_service
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real discovery ownership/admission with controllable native calls, not multicast evidence. */
class IosLanTxtMonitorTest {
    @Test
    fun sameGenerationReplacementRejectsOldRecordsAndOldRemoval() = withRig {
        val old = owner()
        val oldRef = dns.references.last()
        oldRef.answer(bytes())
        val first = assertNotNull(registry.lease(REMOTE))
        val fresh = owner(previous = old)
        val freshRef = dns.references.last()
        assertNotSame(old, fresh)
        freshRef.answer(bytes(name = "Fresh"))
        val current = assertNotNull(registry.lease(REMOTE))
        assertNotSame(first, current)
        val before = events.toList()
        oldRef.answer(bytes(name = "Stale"))
        oldRef.error()
        discovery.removeTxtServiceForTest(old)
        assertSame(current, registry.lease(REMOTE))
        assertEquals("Fresh", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
        assertEquals(before, events)
        assertTrue(oldRef.deallocated && oldRef.disposed)
    }

    @Test
    fun callbackReenteredDuringCopyCannotCommitOrWithdrawReplacement() = withRig {
        val old = owner()
        val oldRef = dns.references.last()
        oldRef.answer(bytes())
        var fresh: IosLanTxtMonitor.Owner? = null
        oldRef.answer(bytes(name = "Stale"), read = { count ->
            fresh = owner(previous = old)
            assertNotSame(old, fresh)
            bytes(name = "Stale").copyOf(count)
        })
        assertNotNull(fresh)
        assertNull(registry.lease(REMOTE), "returned old bytes must not commit after replacement")
        dns.references.last().answer(bytes(name = "Fresh"))
        assertNotNull(registry.lease(REMOTE))
        assertEquals("Fresh", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
        assertFalse(events.filterIsInstance<PeerEvent.Found>().any { it.peer.publicPeer.name == "Stale" })
    }

    @Test
    fun callbackReenteredDuringCopyCannotOverwriteANewerRecordRevision() = withRig {
        owner()
        val ref = dns.references.last()
        val old = bytes()
        ref.answer(old)
        val newer = bytes(name = "Newer")
        ref.answer(bytes(name = "Stale"), read = { count ->
            dns.onQueue {
                ref.answer(old, added = false, moreComing = true)
                ref.answer(newer)
            }
            bytes(name = "Stale").copyOf(count)
        })
        assertEquals("Newer", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
        assertEquals(1, assertNotNull(discovery.txtSnapshotForTest(REMOTE.value)).records.size)
        assertFalse(events.any { it is PeerEvent.Lost })
    }

    @Test
    fun concordantScopesAndUnknownKeysDoNotInventInterfaceEquality() = withRig {
        owner()
        val ref = dns.references.last()
        val original = bytes()
        val reordered = LanTxtRecordFixtures.encode(
            properties().toList().reversed() + ("unknown" to byteArrayOf(0xff.toByte()))
        )
        dns.onQueue {
            ref.answer(original, scope = 0xffffffffu, moreComing = true)
            ref.answer(reordered, scope = 7u)
        }
        assertNotNull(registry.lease(REMOTE))
        assertEquals(2, assertNotNull(discovery.txtSnapshotForTest(REMOTE.value)).records.size)
        ref.answer(original, scope = 0xffffffffu)
        assertEquals(2, assertNotNull(discovery.txtSnapshotForTest(REMOTE.value)).records.size)
        ref.answer(original, scope = 0xffffffffu, added = false)
        assertNotNull(registry.lease(REMOTE), "the other actual RR owner is still current")
        ref.answer(original, scope = 0xffffffffu, added = false)
        assertNotNull(registry.lease(REMOTE), "duplicate removal cannot remove another scope")
        ref.answer(reordered, scope = 7u, added = false)
        assertNull(registry.lease(REMOTE))
        assertEquals(1, events.count { it is PeerEvent.Lost })
        ref.answer(original, scope = 0xffffffffu)
        assertNotNull(registry.lease(REMOTE))
    }

    @Test
    fun conflictingAndInvalidCurrentRecordsWithdrawUntilActuallyRemoved() = withRig {
        owner()
        val ref = dns.references.last()
        val valid = bytes()
        val contradictory = bytes(name = "Other")
        ref.answer(valid, scope = 1u)
        ref.answer(contradictory, scope = 2u)
        assertNull(registry.lease(REMOTE))
        ref.answer(valid, scope = 1u)
        assertNull(registry.lease(REMOTE), "a duplicate valid Add cannot hide the conflicting owner")
        ref.answer(contradictory, scope = 2u, added = false)
        assertNotNull(registry.lease(REMOTE))
        val invalid = bytes(properties() + ("app" to "foreign".encodeToByteArray()))
        ref.answer(invalid, scope = 3u)
        assertNull(registry.lease(REMOTE))
        ref.answer(invalid, scope = 3u, added = false)
        assertNotNull(registry.lease(REMOTE))
        assertFalse(ref.deallocated, "semantic invalidity is not native query termination")
    }

    @Test
    fun completeBatchesKeepUpdatesAtomicAndIncompleteBatchesWithdraw() = withRig {
        val firstOwner = owner()
        val ref = dns.references.last()
        val initial = bytes()
        val updated = bytes(name = "Updated")
        ref.answer(initial)
        dns.onQueue {
            ref.answer(initial, added = false, moreComing = true)
            ref.answer(updated)
        }
        assertEquals("Updated", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
        assertEquals(0, events.count { it is PeerEvent.Lost }, "complete update must not invent loss")
        ref.answer(updated, moreComing = true)
        assertNull(registry.lease(REMOTE), "one quiet incomplete batch cannot keep last-good admission")
        assertTrue(assertNotNull(discovery.txtSnapshotForTest(REMOTE.value)).pending)
        assertFalse(ref.deallocated)
        ref.answer(updated)
        assertNotNull(registry.lease(REMOTE))
        assertEquals(1, events.count { it is PeerEvent.Lost })
        dns.onQueue {
            repeat(20) {
                ref.answer(updated, moreComing = true)
                ref.answer(updated)
            }
            assertEquals(1, dns.pendingBlocks, "completed batches must coalesce one outstanding guard")
            val fresh = owner(previous = firstOwner)
            assertNotSame(firstOwner, fresh)
        }
        dns.references.last().answer(bytes(name = "Replacement"))
        assertEquals("Replacement", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
    }

    @Test
    fun endlessBatchAndRecordOverflowRetireInsteadOfKeepingPartialState() = withRig {
        owner()
        val ref = dns.references.last()
        val valid = bytes()
        ref.answer(valid)
        dns.onQueue { repeat(65) { ref.answer(valid, moreComing = true) } }
        assertNull(registry.lease(REMOTE))
        assertTrue(ref.deallocated && ref.disposed)
        discovery.refresh()
        owner()
        val capped = dns.references.last()
        repeat(8) { capped.answer(valid, scope = it.toUInt()) }
        assertNotNull(registry.lease(REMOTE))
        capped.answer(valid, scope = 8u)
        assertNull(registry.lease(REMOTE))
        assertTrue(capped.deallocated && capped.disposed)
        assertEquals(0, discovery.txtQueryCountForTest)
    }

    @Test
    fun globalRawBudgetWithdrawsTheAffectedQueryWithoutEvictingOtherPeers() = withRig {
        val refs = (0 until 17).map { index ->
            val pid = "large-$index"
            owner(pid)
            dns.references.last()
        }
        val records = (0 until 17).map { paddedRecord(bytes(pid = "large-$it")) }
        // 128 * 65,535 = 8MiB - 128; every individual owner is below the eight-RR cap.
        repeat(7) { scope -> refs.forEachIndexed { index, ref -> ref.answer(records[index], scope.toUInt()) } }
        repeat(9) { index -> refs[index].answer(records[index], 7u) }
        assertEquals(17, registry.sizeForTest())
        val retained = assertNotNull(registry.lease(PeerId("large-0")))
        refs[9].answer(records[9], 7u)
        assertNull(registry.lease(PeerId("large-9")))
        assertSame(retained, registry.lease(PeerId("large-0")))
        assertEquals(16, registry.sizeForTest())
        assertTrue(refs[9].deallocated && refs[9].disposed)
    }

    @Test
    fun invalidTxtFreesOnlyAdmissionUntilActualNativeRemovalFreesQueryCapacity() = withRig {
        val owners = (0 until MAX_TRACKED_LAN_PEERS).map { index ->
            owner("peer-$index").also { dns.references.last().answer(bytes(pid = "peer-$index")) }
        }
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, registry.sizeForTest())
        val firstRef = dns.references.first()
        val firstRaw = bytes(pid = "peer-0")
        firstRef.answer(firstRaw, added = false)
        assertEquals(MAX_TRACKED_LAN_PEERS - 1, registry.sizeForTest())
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
        assertNull(tryOwner("overflow"))
        assertEquals(MAX_TRACKED_LAN_PEERS, dns.references.size)
        firstRef.answer(firstRaw)
        assertNotNull(registry.lease(PeerId("peer-0")), "the still-live invalid query must recover")
        discovery.removeTxtServiceForTest(owners.first())
        assertTrue(firstRef.deallocated && firstRef.disposed)
        assertEquals(MAX_TRACKED_LAN_PEERS - 1, discovery.txtQueryCountForTest)
        owner("overflow")
        dns.references.last().answer(bytes(pid = "overflow"))
        assertNotNull(registry.lease(PeerId("overflow")))
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
    }

    @Test
    fun fullCapacityReplacementTransfersOnlyAfterTheOldNativeContextRetires() = withRig {
        val owners = (0 until MAX_TRACKED_LAN_PEERS).map { index ->
            owner("peer-$index").also { dns.references.last().answer(bytes(pid = "peer-$index")) }
        }
        val old = owners.first()
        val ref = dns.references.first()
        val unrelated = assertNotNull(registry.lease(PeerId("peer-1")))
        dns.holdQueue = true
        val fresh = owner("peer-0", previous = old)
        assertNotSame(old, fresh)
        assertNull(registry.lease(PeerId("peer-0")))
        assertSame(unrelated, registry.lease(PeerId("peer-1")))
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtReservedQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, dns.references.size)
        val reads = ref.fieldsRead
        ref.answer(bytes(pid = "peer-0", name = "Stale"))
        assertEquals(reads, ref.fieldsRead)
        discovery.removeTxtServiceForTest(old)
        assertNull(registry.lease(PeerId("peer-0")))
        dns.drainOne()
        assertTrue(ref.deallocated)
        assertFalse(ref.disposed)
        assertEquals(MAX_TRACKED_LAN_PEERS - 1, discovery.txtQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtReservedQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, dns.references.size)
        dns.drainOne()
        assertTrue(ref.disposed)
        assertEquals(MAX_TRACKED_LAN_PEERS, dns.references.size, "disposal is not successor allocation")
        var turns = 0
        while (dns.pendingBlocks > 0) {
            check(turns++ < 16) { "one replacement cannot enqueue unbounded native work" }
            dns.drainOne()
            assertTrue(discovery.txtReservedQueryCountForTest <= MAX_TRACKED_LAN_PEERS)
            assertTrue(discovery.txtQueryCountForTest <= MAX_TRACKED_LAN_PEERS)
        }
        assertEquals(MAX_TRACKED_LAN_PEERS + 1, dns.references.size)
        assertSame(fresh, assertNotNull(discovery.txtSnapshotForTest("peer-0")).owner)
        dns.references.last().answer(bytes(pid = "peer-0", name = "Fresh"))
        assertEquals("Fresh", discovery.announceEntryForTest("peer-0")?.peer?.publicPeer?.name)
        assertSame(unrelated, registry.lease(PeerId("peer-1")))
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
        // Replacing a queued successor must retain ONE reservation owned by the old live ref.
        val secondRef = dns.references.last()
        val pending = owner("peer-0", previous = fresh)
        val newest = owner("peer-0", previous = pending)
        discovery.removeTxtServiceForTest(pending)
        val referenceCount = dns.references.size
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtReservedQueryCountForTest)
        turns = 0
        while (dns.pendingBlocks > 0) {
            check(turns++ < 16)
            dns.drainOne()
            assertTrue(discovery.txtReservedQueryCountForTest <= MAX_TRACKED_LAN_PEERS)
            assertTrue(discovery.txtQueryCountForTest <= MAX_TRACKED_LAN_PEERS)
            if (dns.references.size > referenceCount) assertTrue(secondRef.deallocated && secondRef.disposed)
        }
        assertEquals(referenceCount + 1, dns.references.size, "superseded pending owner must never start")
        assertSame(newest, assertNotNull(discovery.txtSnapshotForTest("peer-0")).owner)
        dns.references.last().answer(bytes(pid = "peer-0", name = "Newest"))
        assertEquals("Newest", discovery.announceEntryForTest("peer-0")?.peer?.publicPeer?.name)
        // Cancelling the current pending successor must not release its predecessor's still-live slot.
        val finalRef = dns.references.last()
        val cancelled = owner("peer-0", previous = newest)
        discovery.removeTxtServiceForTest(cancelled)
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtReservedQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
        assertFalse(finalRef.deallocated)
        val beforeCancelDrain = dns.references.size
        dns.holdQueue = false
        dns.drain()
        assertEquals(beforeCancelDrain, dns.references.size, "cancelled pending owner must never start")
        assertTrue(finalRef.deallocated && finalRef.disposed)
        assertEquals(MAX_TRACKED_LAN_PEERS - 1, discovery.txtReservedQueryCountForTest)
        assertEquals(MAX_TRACKED_LAN_PEERS - 1, discovery.txtQueryCountForTest)
        owner("after-cancel")
        dns.references.last().answer(bytes(pid = "after-cancel"))
        assertNotNull(registry.lease(PeerId("after-cancel")))
        assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtReservedQueryCountForTest)
        assertSame(unrelated, registry.lease(PeerId("peer-1")))
    }

    @Test
    fun conflictingOwnerAtCapacityCannotHideBehindAllocationRejection() = withRig {
        repeat(MAX_TRACKED_LAN_PEERS) { index ->
            owner("peer-$index")
            dns.references.last().answer(bytes(pid = "peer-$index"))
        }
        val other = assertNotNull(registry.lease(PeerId("peer-1")))
        assertNull(tryOwner("peer-0", domain = "other.local."))
        assertEquals(MAX_TRACKED_LAN_PEERS, dns.references.size)
        assertNull(registry.lease(PeerId("peer-0")))
        assertSame(other, registry.lease(PeerId("peer-1")))
        assertNull(tryOwner("peer-0"), "untracked conflicting owner cannot be cleared by guessing")
        assertEquals(MAX_TRACKED_LAN_PEERS - 1, registry.sizeForTest())
    }

    @Test
    fun nativeStartScheduleAndAsyncErrorsOwnTheirExactCleanupPhases() = withRig {
        dns.startError = -1
        owner("start-failure")
        assertEquals(0, discovery.txtQueryCountForTest)
        assertEquals(1, dns.failedStartContextsDisposed)
        assertTrue(dns.references.isEmpty())
        dns.startError = 0
        dns.successWithoutReference = true
        owner("null-reference")
        assertEquals(0, discovery.txtQueryCountForTest)
        dns.successWithoutReference = false
        dns.scheduleError = -2
        owner("schedule-failure")
        val failed = dns.references.last()
        assertEquals(listOf("schedule", "deallocate", "dispose"), failed.operations)
        dns.scheduleError = 0
        owner("async-failure")
        val async = dns.references.last()
        async.error()
        assertEquals(0, async.fieldsRead, "all error payload fields are undefined")
        assertEquals(listOf("schedule", "deallocate", "dispose"), async.operations)
        async.error()
        assertEquals(1, async.operations.count { it == "deallocate" })
        assertEquals(1, async.operations.count { it == "dispose" })
        assertEquals(0, discovery.txtQueryCountForTest)
        dns.holdQueue = true
        val neverStarted = owner("cancel-before-start")
        val count = dns.references.size
        assertEquals(1, discovery.txtReservedQueryCountForTest)
        discovery.removeTxtServiceForTest(neverStarted)
        dns.holdQueue = false
        dns.drain()
        assertEquals(count, dns.references.size, "cancelled queued creation must not allocate a native reference")
        assertEquals(0, discovery.txtReservedQueryCountForTest)
        dns.afterStart = {
            val created = assertNotNull(discovery.txtSnapshotForTest("cancel-before-attach")).owner
            discovery.removeTxtServiceForTest(created)
        }
        owner("cancel-before-attach")
        dns.afterStart = null
        assertEquals(listOf("deallocate", "dispose"), dns.references.last().operations)
        assertEquals(0, discovery.txtQueryCountForTest)
        assertEquals(0, discovery.txtReservedQueryCountForTest)
    }

    @Test
    fun callbackIdentityAndLengthFailuresNeverConsumeUnownedStorage() = withRig {
        data class Invalid(val name: String? = null, val type: UShort = 16u, val klass: UShort = 1u)
        for ((index, invalid) in listOf(Invalid("foreign.local."), Invalid(type = 12u), Invalid(klass = 3u))
            .withIndex()
        ) {
            owner("invalid-$index")
            val ref = dns.references.last()
            ref.answer(bytes(pid = "invalid-$index"), fullName = invalid.name ?: ref.fullName,
                rrType = invalid.type, rrClass = invalid.klass)
            assertEquals(0, ref.byteReads)
            assertTrue(ref.deallocated && ref.disposed)
        }
        owner("null-name")
        val nullName = dns.references.last()
        nullName.answer(bytes(pid = "null-name"), fullName = null)
        assertEquals(0, nullName.byteReads)
        assertTrue(nullName.deallocated && nullName.disposed)
        owner("oversized")
        val oversized = dns.references.last()
        oversized.answer(null, length = 65_536UL, read = { error("oversized input must not be read") })
        assertEquals(0, oversized.byteReads)
        assertTrue(oversized.deallocated && oversized.disposed)
        owner("empty")
        val empty = dns.references.last()
        empty.answer(null, length = 0UL, read = { error("empty input must not be dereferenced") })
        assertEquals(0, empty.byteReads)
        assertNull(registry.lease(PeerId("empty")))
        assertFalse(empty.deallocated, "empty semantic TXT remains eligible for later live recovery")
        owner("missing")
        val missing = dns.references.last()
        missing.answer(null, length = 1UL)
        assertEquals(1, missing.byteReads)
        assertTrue(missing.deallocated && missing.disposed)
        for ((index, copied) in listOf(ByteArray(1), ByteArray(3)).withIndex()) {
            owner("wrong-copy-$index")
            val wrongCopy = dns.references.last()
            wrongCopy.answer(copied, length = 2UL)
            assertEquals(1, wrongCopy.byteReads)
            assertTrue(wrongCopy.deallocated && wrongCopy.disposed)
            assertNull(registry.lease(PeerId("wrong-copy-$index")))
        }
    }

    @Test
    fun retirementRetainsContextUntilTheFinalQueueTurnAndStopsLatePayloadReads() = withRig {
        val current = owner()
        val ref = dns.references.last()
        ref.answer(bytes())
        dns.holdQueue = true
        discovery.removeTxtServiceForTest(current)
        assertNull(registry.lease(REMOTE), "logical ownership must be revoked before native release")
        assertFalse(ref.deallocated)
        dns.drainOne()
        assertTrue(ref.deallocated)
        assertFalse(ref.disposed, "context survives deallocate until a later queue turn")
        val reads = ref.fieldsRead
        ref.answer(bytes(name = "Late"))
        assertEquals(reads, ref.fieldsRead)
        assertNull(registry.lease(REMOTE))
        dns.drainOne()
        assertTrue(ref.disposed)
        discovery.removeTxtServiceForTest(current)
        dns.holdQueue = false
        dns.drain()
        assertEquals(listOf("schedule", "deallocate", "dispose"), ref.operations)
    }

    private class Rig(profile: TransportSecurityProfile) {
        val context = TransportContext(
            appId = AppId("lan-txt-test"), localPeerId = PeerId("local"), deviceName = "Observer",
            platform = Platform.IOS, securityProfile = profile
        )
        val dns = FakeIosLanTxtDns()
        val registry = IosEndpointRegistry()
        val data = IosLanDataTransport(context, registry)
        val discovery = IosLanDiscoveryTransport(context, registry, data, dns)
        val events = mutableListOf<PeerEvent>()

        fun properties(): Map<String, ByteArray?> = LanTxtRecordFixtures.properties(context.securityProfile)
        fun bytes(properties: Map<String, ByteArray?>): ByteArray = LanTxtRecordFixtures.encode(properties.toList())
        fun bytes(pid: String = REMOTE.value, name: String = "Remote"): ByteArray = bytes(
            properties() + ("pid" to pid.encodeToByteArray()) + ("name" to name.encodeToByteArray())
        )

        fun tryOwner(
            pid: String = REMOTE.value,
            previous: IosLanTxtMonitor.Owner? = null,
            domain: String = "local."
        ): IosLanTxtMonitor.Owner? {
            val endpoint = assertNotNull(nw_endpoint_create_bonjour_service(pid, context.lanServiceTypeBonjour, domain))
            return discovery.txtServiceForTest(endpoint, discovery.browserGenerationForTest, previous)
        }

        fun owner(
            pid: String = REMOTE.value,
            previous: IosLanTxtMonitor.Owner? = null
        ): IosLanTxtMonitor.Owner = assertNotNull(tryOwner(pid, previous))
    }

    private fun withRig(block: suspend Rig.() -> Unit) = runBlocking<Unit> {
        for (profile in TransportSecurityProfile.entries) {
            val rig = Rig(profile)
            val collector = launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
                rig.discovery.events.collect { rig.events += it }
            }
            try {
                withTimeout(5_000) {
                    rig.discovery.startDiscovery()
                    rig.block()
                }
            } finally {
                withContext(NonCancellable) {
                    rig.dns.holdQueue = false
                    rig.dns.drain()
                    try {
                        rig.discovery.stopDiscovery()
                    } finally {
                        try { collector.cancelAndJoin() } finally { rig.data.close() }
                    }
                    assertEquals(0, rig.discovery.txtQueryCountForTest)
                    assertEquals(0, rig.discovery.txtReservedQueryCountForTest)
                    assertEquals(0, rig.discovery.txtRetainedBytesForTest)
                    rig.dns.references.forEach { ref ->
                        assertEquals(1, ref.operations.count { it == "deallocate" })
                        assertEquals(1, ref.operations.count { it == "dispose" })
                    }
                }
            }
        }
    }

    private companion object {
        val REMOTE = PeerId("remote")

        fun paddedRecord(prefix: ByteArray): ByteArray {
            val output = ByteArray(65_535)
            prefix.copyInto(output)
            var offset = prefix.size
            while (offset < output.size) {
                val count = minOf(255, output.size - offset - 1)
                output[offset++] = count.toByte()
                if (count > 0) output[offset] = 'x'.code.toByte()
                offset += count
            }
            return output
        }
    }
}

/** Synthetic native calls; queue turns and borrowed-field reads are observable, never DNS answers. */
internal class FakeIosLanTxtDns : IosLanTxtDns {
    val references = mutableListOf<Reference>()
    var startError = 0
    var scheduleError = 0
    var successWithoutReference = false
    var afterStart: (() -> Unit)? = null
    var failedStartContextsDisposed = 0
    var holdQueue = false
    private val blocks = ArrayDeque<() -> Unit>()
    private var queueDepth = 0
    val pendingBlocks: Int get() = blocks.size

    override fun constructFullName(name: String, type: String, domain: String): String =
        "$name.${type.trimEnd('.')}.${domain.trimEnd('.')}."

    override fun start(fullName: String, callback: (Int, () -> IosLanTxtAnswer) -> Unit): IosLanTxtDns.Start {
        check(queueDepth > 0) { "query must start on its native queue" }
        if (startError != 0) {
            failedStartContextsDisposed++
            return IosLanTxtDns.Start(startError, null)
        }
        if (successWithoutReference) return IosLanTxtDns.Start(0, null)
        val ref = Reference(fullName, callback, scheduleError)
        references += ref
        afterStart?.invoke()
        return IosLanTxtDns.Start(0, ref)
    }

    override fun enqueue(block: () -> Unit) {
        blocks.addLast(block)
        if (queueDepth == 0 && !holdQueue) drain()
    }

    fun onQueue(block: () -> Unit) {
        queueDepth++
        try { block() } finally {
            queueDepth--
            if (queueDepth == 0 && !holdQueue) drain()
        }
    }

    fun drainOne() {
        if (blocks.isEmpty()) return
        queueDepth++
        try { blocks.removeFirst().invoke() } finally { queueDepth-- }
    }

    fun drain() {
        var count = 0
        while (blocks.isNotEmpty()) {
            check(count++ < 10_000) { "unexpected unbounded native queue work" }
            drainOne()
        }
    }

    inner class Reference(
        val fullName: String,
        private val callback: (Int, () -> IosLanTxtAnswer) -> Unit,
        private val schedulingError: Int
    ) : IosLanTxtDns.Reference {
        val operations = mutableListOf<String>()
        var fieldsRead = 0
        var byteReads = 0
        var deallocated = false
        var disposed = false

        override fun schedule(): Int {
            check(queueDepth > 0)
            check(!deallocated && !disposed)
            operations += "schedule"
            return schedulingError
        }

        override fun deallocate() {
            check(queueDepth > 0)
            check(!deallocated && !disposed)
            operations += "deallocate"
            deallocated = true
        }

        override fun disposeContext() {
            check(queueDepth > 0)
            check(deallocated && !disposed)
            operations += "dispose"
            disposed = true
        }

        fun error(code: Int = -1) = onQueue {
            callback(code) {
                fieldsRead++
                kotlin.error("error callback fields are undefined")
            }
        }

        fun answer(
            bytes: ByteArray?,
            scope: UInt = 1u,
            added: Boolean = true,
            moreComing: Boolean = false,
            fullName: String? = this.fullName,
            rrType: UShort = 16u,
            rrClass: UShort = 1u,
            length: ULong = bytes?.size?.toULong() ?: 0UL,
            read: ((Int) -> ByteArray?)? = null
        ) = onQueue {
            callback(0) {
                fieldsRead++
                IosLanTxtAnswer(fullName, scope, rrType, rrClass, added, moreComing, length) { count ->
                    byteReads++
                    if (read != null) read(count) else bytes?.copyOf()
                }
            }
        }
    }
}
