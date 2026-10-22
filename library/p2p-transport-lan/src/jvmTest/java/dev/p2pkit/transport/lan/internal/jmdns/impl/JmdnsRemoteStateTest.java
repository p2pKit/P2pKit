package dev.p2pkit.transport.lan.internal.jmdns.impl;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceTypeListener;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;
import org.junit.Test;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.InetAddress;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertSame;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

/** Real parser/record/cache executions. Socket-free; not native networking or soak qualification. */
public class JmdnsRemoteStateTest {
    private static final String META = "_services._dns-sd._udp.local.";
    private static final String TYPE = "_p2pkit2._tcp.local.";
    private static final int FLAGS = DNSConstants.FLAGS_QR_RESPONSE | DNSConstants.FLAGS_AA;

    @Test
    public void unsolicitedMetaResponsesAreBoundedBeforeAnyPeerListenerExists() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(16))) {
            for (int i = 0; i < DNSCache.MAX_RECORDS + 64; i++) {
                dns.handleResponse(packet(pointer(META, "_remote" + i + "._tcp.local.", 86400)));
                assertBounds(dns.getCache(), DNSCache.MAX_RECORDS, DNSCache.MAX_RETAINED_BYTES);
            }
            assertEquals(DNSCache.MAX_RECORDS, dns.getCache().recordCount());
            assertEquals("All meta aliases share one owner name, not one record budget slot", 1, dns.getCache().size());
            assertEquals(DNSCache.MAX_RECORDS, dns.getServiceTypes().size());
            assertFalse(dns.getServiceTypes().containsKey("_remote0._tcp.local."));
            assertTrue(dns.getServiceTypes().containsKey("_remote4159._tcp.local."));
            dns.getCache().clear();
            assertTrue("Remote aliases must not survive in the local registration map", dns.getServiceTypes().isEmpty());
        }
    }

    @Test
    public void sharedPtrAliasesAndSubtypesCannotBypassTheRecordBudget() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 65536))) {
            for (int i = 0; i < 40; i++) {
                // DNSEntry.equals omits subtype: same alias but distinct subtype must still be charged.
                dns.handleResponse(packet(pointer("_s" + i + "._sub." + TYPE, "peer." + TYPE, 120)));
                assertBounds(dns.getCache(), 8, 65536);
            }
            assertEquals(8, dns.getCache().recordCount());
            assertEquals(1, dns.getCache().size());
            JmDNSImpl.ServiceTypeEntry type = dns.getServiceTypes().get(TYPE);
            assertEquals(8, type.size());
            assertFalse(type.contains("s0"));
            assertTrue(type.contains("s39"));
        }
    }

    @Test
    public void ordinaryDistinctNamesAreByteBoundedAndNewestUsableRecordsRemain() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 100, 5000))) {
            for (int i = 0; i < 32; i++) {
                dns.handleResponse(packet(text("peer" + i + "." + TYPE, 120, 800)));
                assertBounds(dns.getCache(), 100, 5000);
            }
            assertTrue("Byte budget, not record count, must be reached", dns.getCache().recordCount() < 4);
            assertNull(dns.getCache().getDNSEntry("peer0." + TYPE, DNSRecordType.TYPE_TXT, DNSRecordClass.CLASS_IN));
            assertNotNull(dns.getCache().getDNSEntry("peer31." + TYPE, DNSRecordType.TYPE_TXT, DNSRecordClass.CLASS_IN));
        }
    }

    @Test
    public void oversizedUpdateCannotFlushOrReplaceAnExistingUsableRecord() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 2048))) {
            DNSRecord old = at(text("peer." + TYPE, 120, 12), 10000);
            dns.handleRecord(old, 10000);
            DNSRecord incoming = packet(text("peer." + TYPE, 120, 2048)).getAllAnswers().get(0);
            at(incoming, 12000);
            dns.handleRecord(incoming, 12000);
            assertSame(old, dns.getCache().getDNSEntry(incoming));
            assertEquals("Rejected cache-flush update must leave the original TTL intact", 120, old.getTTL());
            assertFalse(old.isExpired(13001));
            assertEquals(1, dns.getCache().recordCount());
        }
    }

    @Test
    public void ttlRefreshReusesOneRecordAndRemoteTypeExpiresWithIt() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 4, 65536))) {
            DNSRecord old = at(pointer(META, TYPE, 2), 10000);
            dns.handleRecord(old, 10000);
            DNSRecord refresh = at(pointer(META, TYPE, 60), 11000);
            dns.handleRecord(refresh, 11000);
            assertSame(old, dns.getCache().getDNSEntry(refresh));
            assertEquals(1, dns.getCache().recordCount());
            assertTrue(dns.getServiceTypes(70999).containsKey(TYPE));
            dns.cleanCache(71000);
            assertTrue(dns.getServiceTypes(71000).isEmpty());
            assertBounds(dns.getCache(), 0, 0);
        }
    }

    @Test
    public void unknownGoodbyesNeverRegisterTypesAndKnownGoodbyesHaveOneSecondGrace() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 4, 65536))) {
            dns.handleRecord(at(pointer(META, TYPE, 0), 10000), 10000);
            assertTrue(dns.getServiceTypes(10000).isEmpty());
            assertEquals(0, dns.getCache().recordCount());
            dns.handleRecord(at(pointer(META, TYPE, 120), 10000), 10000);
            dns.handleRecord(at(pointer(META, TYPE, 0), 11000), 11000);
            assertTrue(dns.getServiceTypes(11999).containsKey(TYPE));
            dns.cleanCache(12000);
            assertTrue(dns.getServiceTypes(12000).isEmpty());
            assertBounds(dns.getCache(), 0, 0);
        }
    }

    @Test
    public void oneSharedOwnerExpiringDoesNotEraseAnotherOwnerOrLocalSubtype() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 65536))) {
            dns.registerServiceType("_local._sub." + TYPE);
            dns.handleRecord(at(pointer("_remote._sub." + TYPE, "first." + TYPE, 1), 10000), 10000);
            dns.handleRecord(at(pointer(TYPE, "second." + TYPE, 60), 10000), 10000);
            assertTrue(dns.getServiceTypes(10000).get(TYPE).contains("remote"));
            assertTrue(dns.getServiceTypes(10000).get(TYPE).contains("local"));
            // Mutating a returned snapshot cannot pin an untrusted remote subtype locally.
            dns.getServiceTypes(10000).get(TYPE).add("snapshot-only");
            assertFalse(dns.getServiceTypes(10000).get(TYPE).contains("snapshot-only"));
            dns.cleanCache(11000);
            assertFalse(dns.getServiceTypes(11000).get(TYPE).contains("remote"));
            assertTrue(dns.getServiceTypes(11000).get(TYPE).contains("local"));
            assertEquals(1, dns.getCache().recordCount());
            dns.cleanCache(70000);
            assertEquals(0, dns.getCache().recordCount());
            assertEquals(1, dns.getServiceTypes(70000).size());
            assertTrue(dns.getServiceTypes(70000).get(TYPE).contains("local"));
        }
    }

    @Test
    public void sharedRemoteTypeSurvivesUntilItsLastPtrExpires() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 65536))) {
            dns.handleRecord(at(pointer(TYPE, "first." + TYPE, 1), 10000), 10000);
            dns.handleRecord(at(pointer(TYPE, "second." + TYPE, 60), 10000), 10000);
            dns.cleanCache(11000);
            assertTrue(dns.getServiceTypes(11000).containsKey(TYPE));
            dns.cleanCache(70000);
            assertTrue(dns.getServiceTypes(70000).isEmpty());
        }
    }

    @Test
    public void expiredRecordsArePreferredToLiveRecordsAtCapacity() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 2, 65536))) {
            DNSRecord live = at(pointer(META, "_live._tcp.local.", 120), 10000);
            DNSRecord expired = at(pointer(META, "_expired._tcp.local.", 1), 10000);
            dns.handleRecord(live, 10000);
            dns.handleRecord(expired, 10000);
            dns.handleRecord(at(pointer(META, "_new._tcp.local.", 120), 12000), 12000);
            assertSame(live, dns.getCache().getDNSEntry(live));
            assertNull(dns.getCache().getDNSEntry(expired));
            assertEquals(2, dns.getCache().recordCount());
        }
    }

    @Test
    public void cacheFlushPreservesRecentSharedAddressesThenReapsOnlyOldAddress() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 65536))) {
            DNSRecord old = at(address("peer.local.", 1), 10000);
            DNSRecord fresh = at(address("peer.local.", 2), 12000);
            DNSRecord recent = at(address("peer.local.", 3), 12500);
            dns.handleRecord(old, 10000);
            dns.handleRecord(fresh, 12000);
            dns.handleRecord(recent, 12500);
            assertEquals(1, old.getTTL());
            assertEquals(120, fresh.getTTL());
            assertEquals(120, recent.getTTL());
            assertEquals(3, dns.getCache().recordCount());
            dns.cleanCache(13000);
            assertEquals(2, dns.getCache().recordCount());
            assertEquals(Arrays.asList(fresh, recent), new ArrayList<>(dns.getCache().allValues()));
        }
    }

    @Test
    public void refreshOfSecondSharedAddressUpdatesThatExactValueWithoutDuplication() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 65536))) {
            DNSRecord first = at(address("peer.local.", 1), 10000);
            DNSRecord second = at(address("peer.local.", 2), 10000);
            dns.handleRecord(first, 10000);
            dns.handleRecord(second, 10000);
            DNSRecord refresh = at(address("peer.local.", 2), 11000);
            dns.handleRecord(refresh, 11000);
            assertEquals(2, dns.getCache().recordCount());
            assertSame(second, dns.getCache().getDNSEntry(refresh));
            assertEquals(11000, second.getCreated());
            assertEquals(10000, first.getCreated());
        }
    }

    @Test
    public void capacityDiagnosticIsOneBoundedNoticeForTheWholeCacheLifetime() {
        DNSCache cache = new DNSCache(1, 1, 65536);
        assertFalse(cache.takePressureNotice());
        cache.addDNSEntry(pointer(META, "_one._tcp.local.", 120));
        cache.addDNSEntry(pointer(META, "_two._tcp.local.", 120));
        assertTrue(cache.takePressureNotice());
        assertFalse(cache.takePressureNotice());
        cache.clear();
        for (int i = 0; i < 32; i++) {
            cache.addDNSEntry(pointer(META, "_again" + i + "._tcp.local.", 120));
        }
        assertFalse("Flushes cannot rearm a warning flood", cache.takePressureNotice());
    }

    @Test
    public void normalParsedServiceLookupAndPortUpdateStillWorkAfterUnrelatedChurn() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 8, 65536))) {
            for (int i = 0; i < 20; i++) {
                dns.handleResponse(packet(pointer(META, "_other" + i + "._tcp.local.", 120)));
            }
            String name = "normal." + TYPE;
            dns.handleResponse(packet(pointer(TYPE, name, 120),
                    new DNSRecord.Service(name, DNSRecordClass.CLASS_IN, true, 120, 0, 0, 12345, "peer.local."),
                    new DNSRecord.Text(name, DNSRecordClass.CLASS_IN, true, 120, new byte[] {4, 'i', 'd', '=', 'x'}),
                    address("peer.local.", 7)));
            ServiceInfo info = dns.getServiceInfo(TYPE, "normal", false, 0);
            assertNotNull(info);
            assertEquals(12345, info.getPort());
            assertEquals("x", info.getPropertyString("id"));
            assertEquals("10.0.0.7", info.getInet4Addresses()[0].getHostAddress());
            dns.handleResponse(packet(new DNSRecord.Service(name, DNSRecordClass.CLASS_IN,
                    true, 120, 0, 0, 23456, "peer.local.")));
            assertEquals(23456, dns.getServiceInfo(TYPE, "normal", false, 0).getPort());
            assertBounds(dns.getCache(), 8, 65536);
        }
    }

    @Test
    public void evictionNotifiesExistingDnsListenersWithAnExpiredRemovedRecord() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 2, 65536))) {
            List<DNSEntry> removals = new ArrayList<>();
            dns.addListener((cache, now, entry) -> {
                if (entry.isExpired(now)) {
                    removals.add(entry);
                }
            }, null);
            DNSRecord first = text("first." + TYPE, 120, 12);
            dns.handleResponse(packet(first));
            dns.handleResponse(packet(text("second." + TYPE, 120, 12)));
            dns.handleResponse(packet(text("third." + TYPE, 120, 12)));
            assertEquals(1, removals.size());
            assertEquals(first.getKey(), removals.get(0).getKey());
            assertEquals(2, dns.getCache().recordCount());
        }
    }

    @Test
    public void concurrentRecordIngressCannotOvershootEitherBudget() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 32, 65536))) {
            ExecutorService workers = Executors.newFixedThreadPool(4);
            CountDownLatch start = new CountDownLatch(1);
            List<Future<?>> futures = new ArrayList<>();
            try {
                for (int worker = 0; worker < 4; worker++) {
                    final int id = worker;
                    futures.add(workers.submit(() -> {
                        start.await();
                        for (int n = 0; n < 256; n++) {
                            DNSRecord record = text("peer" + id + "-" + n + "." + TYPE, 120, 64);
                            dns.handleRecord(record, record.getCreated());
                            assertBounds(dns.getCache(), 32, 65536);
                        }
                        return null;
                    }));
                }
                start.countDown();
                for (Future<?> future : futures) {
                    future.get(10, TimeUnit.SECONDS);
                }
            } finally {
                workers.shutdownNow();
                assertTrue(workers.awaitTermination(10, TimeUnit.SECONDS));
            }
            assertEquals(32, dns.getCache().recordCount());
            assertBounds(dns.getCache(), 32, 65536);
        }
    }

    @Test
    public void cacheAccountingCannotBeBypassedThroughMapViewsOrReplacement() {
        DNSCache cache = new DNSCache(1, 2, 65536);
        DNSRecord first = pointer(TYPE, "one." + TYPE, 120);
        DNSRecord second = pointer(TYPE, "two." + TYPE, 120);
        assertTrue(cache.addDNSEntry(first));
        assertFalse(cache.addDNSEntry(pointer(TYPE, "one." + TYPE, 120)));
        assertThrows(UnsupportedOperationException.class, () -> cache.put(TYPE, Collections.singletonList(second)));
        assertThrows(UnsupportedOperationException.class, () -> cache.get(TYPE).add(second));
        assertThrows(UnsupportedOperationException.class, () -> cache.entrySet().iterator().next().getValue().clear());
        assertTrue(cache.replaceDNSEntry(second, first));
        assertNull(cache.getDNSEntry(first));
        assertSame(second, cache.getDNSEntry(second));
        DNSCache copy = new DNSCache(cache);
        copy.clear();
        assertBounds(copy, 0, 0);
        assertEquals(1, cache.recordCount());
        assertTrue(cache.removeDNSEntry(second));
        assertBounds(cache, 0, 0);
    }

    @Test
    public void typeListenerHistoryIsBoundedInsteadOfRetainingEveryExpiredType() throws Exception {
        try (MemoryDns dns = new MemoryDns(new DNSCache(1))) {
            AtomicInteger callbacks = new AtomicInteger();
            ServiceTypeListener listener = new ServiceTypeListener() {
                @Override public void serviceTypeAdded(ServiceEvent event) { callbacks.incrementAndGet(); }
                @Override public void subTypeForServiceTypeAdded(ServiceEvent event) { callbacks.incrementAndGet(); }
            };
            ListenerStatus.ServiceTypeListenerStatus status =
                    new ListenerStatus.ServiceTypeListenerStatus(listener, ListenerStatus.SYNCHRONOUS);
            int limit = 2 * DNSCache.MAX_RECORDS;
            for (int n = 0; n < limit + 1; n++) {
                status.serviceTypeAdded(new ServiceEventImpl(dns, "_t" + n + "._tcp.local.", "", null));
            }
            assertEquals(limit, status.retainedTypeCount());
            assertTrue(status.retainedTypeBytes() <= DNSCache.MAX_RETAINED_BYTES);
            int before = callbacks.get();
            status.serviceTypeAdded(new ServiceEventImpl(dns, "_t" + limit + "._tcp.local.", "", null));
            assertEquals("Retained duplicates still collapse", before, callbacks.get());
            status.serviceTypeAdded(new ServiceEventImpl(dns, "_t0._tcp.local.", "", null));
            assertEquals("Forgotten types can legitimately be reannounced", before + 1, callbacks.get());
        }
    }

    @Test
    public void parsedRemoteTypeCallbacksPreserveSubtypeAndDuplicateSemantics() throws Exception {
        AtomicInteger types = new AtomicInteger();
        AtomicInteger subtypes = new AtomicInteger();
        try (MemoryDns dns = new MemoryDns(new DNSCache(1, 2, 65536))) {
            dns.addServiceTypeListener(new ServiceTypeListener() {
                @Override public void serviceTypeAdded(ServiceEvent event) { types.incrementAndGet(); }
                @Override public void subTypeForServiceTypeAdded(ServiceEvent event) { subtypes.incrementAndGet(); }
            });
            dns.handleResponse(packet(pointer(META, TYPE, 0)));
            dns.handleResponse(packet(pointer(META, TYPE, 120)));
            dns.handleResponse(packet(pointer(META, TYPE, 120)));
            dns.handleResponse(packet(pointer("_blue._sub." + TYPE, "peer." + TYPE, 120)));
            dns.handleResponse(packet(pointer(META, "_other._tcp.local.", 120)));
        } // The real owned callback executor is drained by close, not a sleep.
        assertEquals(2, types.get());
        assertEquals(1, subtypes.get());
    }

    @Test
    public void localRegistrationSurvivesPressureButCloseReleasesBothKindsOfState() throws Exception {
        MemoryDns dns = new MemoryDns(new DNSCache(1, 2, 65536));
        try {
            ServiceInfo local = ServiceInfo.create(TYPE, "local", 12345, "id=local");
            dns.registerService(local);
            for (int n = 0; n < 6; n++) {
                dns.handleResponse(packet(pointer(META, "_remote" + n + "._tcp.local.", 120)));
            }
            assertEquals(1, dns.getServices().size());
            assertTrue(dns.getServiceTypes().containsKey(TYPE));
            assertEquals(3, dns.getServiceTypes().size());
        } finally {
            dns.close();
        }
        assertBounds(dns.getCache(), 0, 0);
        assertTrue(dns.getServiceTypes().isEmpty());
        assertTrue(dns.getServices().isEmpty());
        dns.handleResponse(packet(pointer(META, TYPE, 120)));
        assertFalse(dns.registerServiceType(TYPE));
        assertTrue(dns.getServiceTypes().isEmpty());
        assertBounds(dns.getCache(), 0, 0);
        try (MemoryDns fresh = new MemoryDns(new DNSCache(1, 2, 65536))) {
            fresh.handleResponse(packet(pointer(META, TYPE, 120)));
            assertTrue(fresh.getServiceTypes().containsKey(TYPE));
            assertEquals(1, fresh.getCache().recordCount());
        }
    }

    private static void assertBounds(DNSCache cache, int records, long bytes) {
        synchronized (cache) {
            assertTrue(cache.recordCount() <= records);
            assertTrue(cache.retainedBytes() <= bytes);
            assertTrue(cache.retainedBytes() >= 0);
            Collection<DNSEntry> all = cache.allValues();
            assertEquals(all.size(), cache.recordCount());
            long calculated = 0;
            for (DNSEntry entry : all) {
                calculated += DNSCache.retainedSize(entry);
            }
            assertEquals(calculated, cache.retainedBytes());
        }
    }

    private static DNSRecord.Pointer pointer(String name, String alias, int ttl) {
        return new DNSRecord.Pointer(name, DNSRecordClass.CLASS_IN, false, ttl, alias);
    }

    private static DNSRecord.Text text(String name, int ttl, int bytes) {
        return new DNSRecord.Text(name, DNSRecordClass.CLASS_IN, true, ttl, new byte[bytes]);
    }

    private static DNSRecord address(String name, int suffix) {
        return new DNSRecord.IPv4Address(name, DNSRecordClass.CLASS_IN, true, 120,
                new byte[] {10, 0, 0, (byte) suffix});
    }

    private static DNSRecord at(DNSRecord record, long created) {
        int ttl = record.getTTL();
        record.setWillExpireSoon(created);
        record.setTTL(ttl);
        return record;
    }

    private static DNSIncoming packet(DNSRecord... records) throws IOException {
        DNSOutgoing outgoing = new DNSOutgoing(FLAGS, true, 4096);
        for (DNSRecord record : records) {
            outgoing.addAnswer(record, 0);
        }
        byte[] bytes = outgoing.data();
        assertTrue(bytes.length <= 4096);
        return new DNSIncoming(new DatagramPacket(bytes, bytes.length,
                InetAddress.getByAddress(new byte[] {10, 0, 0, 1}), DNSConstants.MDNS_PORT));
    }

    private static final class MemoryDns extends JmDNSImpl {
        MemoryDns(DNSCache cache) throws IOException {
            // Named literal prevents reverse DNS; no multicast socket/timer is allocated.
            super(InetAddress.getByAddress("fixture", new byte[] {127, 0, 0, 1}), "cache-fixture", cache);
        }

        @Override public void startProber() { }
        @Override public void startTypeResolver() { }
        @Override public void startServiceResolver(String type) { }
        @Override public void startServiceInfoResolver(ServiceInfoImpl info) {
            // Exercise the real listener/cache replay used by ServiceInfoResolver
            // initialization, omitting only timer scheduling and network queries.
            info.setDns(this);
            addListener(info, DNSQuestion.newQuestion(info.getQualifiedName(),
                    DNSRecordType.TYPE_ANY, DNSRecordClass.CLASS_IN, false));
        }
    }
}
