@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.transport.lan.interop.p2pkit_nw_required_lan_interface_index
import platform.Foundation.NSLock
import platform.Network.nw_parameters_create
import platform.darwin.dispatch_queue_create
import platform.darwin.kDNSServiceFlagsIncludeP2P
import platform.darwin.kDNSServiceFlagsLongLivedQuery
import platform.darwin.kDNSServiceInterfaceIndexAny
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Inert query/ownership controls: no DNS query, advertisement, listener or route is executed. */
class IosLanTxtQueryScopeTest {
    @Test
    fun ordinaryScopePreservesPeerToPeerAndAnyInterface() {
        val scope = IosLanTxtQueryScope.ordinary
        assertEquals(kDNSServiceInterfaceIndexAny.toUInt(), scope.interfaceIndex)
        assertEquals(kDNSServiceFlagsIncludeP2P or kDNSServiceFlagsLongLivedQuery, scope.flags)
        assertTrue(scope.isCurrent())
    }

    @Test
    fun organizationScopePinsOriginalVerifiedIndexWithoutPeerToPeer() {
        var verified = 7u
        val scope = IosLanTxtQueryScope.organization { verified }
        assertEquals(7u, scope.interfaceIndex)
        assertEquals(kDNSServiceFlagsLongLivedQuery, scope.flags)
        assertEquals(0u, scope.flags and kDNSServiceFlagsIncludeP2P)
        assertTrue(scope.isCurrent())
        verified = 8u
        assertFalse(scope.isCurrent(), "replacement index is not authority to retarget a live query")
        verified = 0u
        assertFalse(scope.isCurrent(), "unavailable index never becomes InterfaceIndexAny")
    }

    @Test
    fun organizationRefusesMissingReservedAndExceptionalInterfaceObservations() {
        for (index in listOf(0u, UInt.MAX_VALUE, UInt.MAX_VALUE - 1u, UInt.MAX_VALUE - 2u, UInt.MAX_VALUE - 3u)) {
            assertFailsWith<IllegalStateException> { IosLanTxtQueryScope.organization { index } }
        }
        var failed = false
        val scope = IosLanTxtQueryScope.organization { if (failed) error("readback unavailable") else 7u }
        failed = true
        assertFalse(scope.isCurrent())
    }

    @Test
    fun originalNativeParametersMustActuallyRequireAnAdmittedInterface() {
        assertEquals(0u, p2pkit_nw_required_lan_interface_index(null, "en0", "10.1.2.3"))
        val bare = assertNotNull(nw_parameters_create())
        assertEquals(0u, p2pkit_nw_required_lan_interface_index(bare, "en0", "10.1.2.3"))
        assertEquals(0u, p2pkit_nw_required_lan_interface_index(bare, null, "10.1.2.3"))
    }

    @Test
    fun lostScopeRefusesPlatformQueryBeforeAnyNativeReferenceOrCallback() {
        var index = 7u
        val scope = IosLanTxtQueryScope.organization { index }
        index = 0u
        val dns = PlatformIosLanTxtDns(dispatch_queue_create("p2pkit.txt.scope.refusal", null))
        var callbacks = 0
        val result = dns.start("remote._p2pkit2._tcp.local.", scope) { _, _ -> callbacks++ }
        assertTrue(result.error != 0)
        assertEquals(null, result.reference)
        assertEquals(0, callbacks)
    }

    @Test
    fun queuedStartCannotRetargetAfterOriginalInterfaceChanges() {
        var index = 7u
        val dns = FakeIosLanTxtDns().also { it.holdQueue = true }
        val monitor = monitor(dns)
        monitor.add(service(IosLanTxtQueryScope.organization { index }))
        index = 8u
        dns.drain()
        assertEquals(0, dns.references.size)
        assertEquals(0, monitor.queryCountForTest)
        assertEquals(0, monitor.reservedQueryCountForTest)
    }

    @Test
    fun scopeLostDuringQueryCreationRetiresReturnedReferenceWithoutScheduling() {
        var index = 7u
        val dns = FakeIosLanTxtDns().also { it.afterStart = { index = 8u } }
        val monitor = monitor(dns)
        monitor.add(service(IosLanTxtQueryScope.organization { index }))
        assertEquals(listOf("deallocate", "dispose"), dns.references.single().operations)
        assertEquals(0, monitor.queryCountForTest)
        assertEquals(0, monitor.reservedQueryCountForTest)
    }

    @Test
    fun scopeLostDuringQueueAttachmentRetiresOriginalReferenceWithoutPublishing() {
        var index = 7u
        val dns = FakeIosLanTxtDns().also { it.afterSchedule = { index = 0u } }
        var snapshots = 0
        val monitor = monitor(dns) { snapshots++ }
        monitor.add(service(IosLanTxtQueryScope.organization { index }))
        val reference = dns.references.single()
        reference.answer(byteArrayOf())
        assertEquals(listOf("schedule", "deallocate", "dispose"), reference.operations)
        assertEquals(0, reference.fieldsRead)
        assertEquals(0, snapshots)
        assertEquals(0, monitor.queryCountForTest)
        assertEquals(0, monitor.reservedQueryCountForTest)
    }

    @Test
    fun scopeLossAtCallbackEntryRefusesBorrowedFieldsAndRetiresOriginalReference() {
        var index = 7u
        val dns = FakeIosLanTxtDns()
        var snapshots = 0
        val monitor = monitor(dns) { snapshots++ }
        monitor.add(service(IosLanTxtQueryScope.organization { index }))
        val reference = dns.references.single()
        index = 0u
        reference.answer(byteArrayOf())
        assertEquals(0, reference.fieldsRead)
        assertEquals(0, reference.byteReads)
        assertEquals(0, snapshots)
        assertEquals(listOf("schedule", "deallocate", "dispose"), reference.operations)
        assertEquals(0, monitor.queryCountForTest)
        assertEquals(0, monitor.reservedQueryCountForTest)
    }

    @Test
    fun scopeLossDuringCopyCannotPublishAndKeepsRetirementOrder() {
        var index = 7u
        val dns = FakeIosLanTxtDns()
        var snapshots = 0
        val monitor = monitor(dns) { snapshots++ }
        monitor.add(service(IosLanTxtQueryScope.organization { index }))
        val reference = dns.references.single()
        val raw = LanTxtRecordFixtures.encode(
            LanTxtRecordFixtures.properties(TransportSecurityProfile.AuthenticatedV2).toList()
        )
        reference.answer(raw, read = { count -> index = 8u; raw.copyOf(count) })
        assertEquals(1, reference.fieldsRead)
        assertEquals(1, reference.byteReads)
        assertEquals(0, snapshots)
        assertEquals(listOf("schedule", "deallocate", "dispose"), reference.operations)
        assertEquals(0, monitor.retainedBytesForTest)
    }

    @Test
    fun successfulQueryReceivesOriginalScopeAndDoesNotTreatCacheLabelAsRouteAuthority() {
        val scope = IosLanTxtQueryScope.organization { 7u }
        val dns = FakeIosLanTxtDns()
        var snapshots = 0
        val monitor = monitor(dns) { snapshots++ }
        val owner = assertNotNull(monitor.add(service(scope)))
        val reference = dns.references.single()
        assertSame(scope, reference.scope)
        assertEquals(7u, reference.scope.interfaceIndex)
        assertEquals(kDNSServiceFlagsLongLivedQuery, reference.scope.flags)
        val raw = LanTxtRecordFixtures.encode(
            LanTxtRecordFixtures.properties(TransportSecurityProfile.AuthenticatedV2).toList()
        )
        reference.answer(raw, scope = UInt.MAX_VALUE)
        assertEquals(1, snapshots, "daemon cache scope is not a new query/route selection")
        monitor.replace(owner, null)
        assertEquals(listOf("schedule", "deallocate", "dispose"), reference.operations)
    }

    private fun monitor(dns: FakeIosLanTxtDns, onSnapshot: (IosLanTxtMonitor.Snapshot) -> Unit = {}) = IosLanTxtMonitor(
        NSLock(), dns, { it == 1 }, onSnapshot, {}
    )

    private fun service(scope: IosLanTxtQueryScope) =
        IosLanTxtService("remote", "_p2pkit2._tcp", "local.", null, 1, scope)
}
