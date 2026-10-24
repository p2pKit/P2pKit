package dev.p2pkit.transport.lan.internal.jmdns.impl;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceListener;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;
import dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.resolver.ServiceInfoResolver;
import org.junit.Test;

import java.io.IOException;
import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/** Socket-free source interleaving, not a multicast/native-platform qualification. */
public class ServiceInfoOrderingTest {
    @Test
    public void cachedPreTxtCloneCannotOvertakeTheIncomingCompleteResolution() throws Exception {
        assertOrderedResolution(false, false);
    }

    @Test
    public void distinctResolversCannotReintroducePreTxtClonesAndUnchangedInfoStaysDeduplicated() throws Exception {
        assertOrderedResolution(true, false);
    }

    @Test
    public void ordinaryPtrCollectorAndCacheLookupCannotInventTxtDuringReplay() throws Exception {
        assertOrderedResolution(true, true);
    }

    @Test
    public void missingTxtIsNotResolutionButReceivedEmptyTxtRemainsValid() throws Exception {
        assertTxtReadiness(InetAddress.getByAddress(new byte[] {127, 0, 0, 1}));
        byte[] ipv6 = new byte[16];
        ipv6[15] = 1;
        assertTxtReadiness(InetAddress.getByAddress(ipv6));
    }

    @Test
    public void explicitlyProvidedEmptyTxtAndTextReplacementRemainCompatible() throws Exception {
        ServiceInfoImpl map = new ServiceInfoImpl("_p2pkit2._tcp.local.", "remote", "", 45001,
                0, 0, true, Collections.emptyMap());
        ServiceInfoImpl bytes = new ServiceInfoImpl("_p2pkit2._tcp.local.", "remote", "", 45001,
                0, 0, true, new byte[0]);
        for (ServiceInfoImpl info : List.of(map, bytes)) {
            info.setServer("remote.local.");
            info.addAddress((Inet4Address) InetAddress.getByAddress(new byte[] {127, 0, 0, 1}));
            assertTrue("Provided empty TXT must remain distinct from absent TXT", info.hasData());
            assertArrayEquals(new byte[] {0}, info.getTextBytes());
            info.setText(Collections.singletonMap("app", "scope"));
            assertTrue(info.hasData());
            assertEquals("scope", info.getPropertyString("app"));
            info.setText(new byte[0]);
            assertTrue(info.hasData());
            assertFalse(info.getPropertyNames().hasMoreElements());
        }
    }

    @Test
    public void resolverContinuesAskingForTxtUntilTheRecordArrives() throws Exception {
        ServiceInfoImpl info = new ServiceInfoImpl("_p2pkit2._tcp.local.", "remote", "", 45001,
                0, 0, true, (byte[]) null);
        info.setServer("remote.local.");
        info.addAddress((Inet4Address) InetAddress.getByAddress(new byte[] {127, 0, 0, 1}));
        QueryResolver resolver = new QueryResolver(info);
        List<DNSQuestion> questions = new ArrayList<>(resolver.questions().getQuestions());
        assertEquals(4, questions.size());
        assertEquals(DNSRecordType.TYPE_TXT, questions.get(1).getRecordType());
        assertEquals(info.getQualifiedName(), questions.get(1).getName());
        DNSRecord.Text empty = new DNSRecord.Text(info.getQualifiedName(), DNSRecordClass.CLASS_IN,
                true, 120, new byte[] {0});
        info.updateRecord(new DNSCache(1), empty.getCreated(), empty);
        assertTrue("Actual empty TXT completes resolution and stops the queries", resolver.questions().isEmpty());
    }

    private static void assertOrderedResolution(boolean secondResolver, boolean includePtr) throws Exception {
        List<Boolean> callbacks = new CopyOnWriteArrayList<>();
        AtomicInteger added = new AtomicInteger();
        AtomicInteger removed = new AtomicInteger();
        byte[] txt = new byte[] {9, 'a', 'p', 'p', '=', 's', 'c', 'o', 'p', 'e'};
        try (ServiceInfoOrderingFixture fixture = new ServiceInfoOrderingFixture(
                "_p2pkit2._tcp.local.", "remote", txt, includePtr)) {
            fixture.replayAgainstIncomingTxt(new ServiceListener() {
                @Override public void serviceAdded(ServiceEvent event) { added.incrementAndGet(); }
                @Override public void serviceRemoved(ServiceEvent event) { removed.incrementAndGet(); }
                @Override public void serviceResolved(ServiceEvent event) {
                    callbacks.add("scope".equals(event.getInfo().getPropertyString("app")));
                }
            }, secondResolver);
            assertEquals("No pre-TXT resolved callback may erase the complete TXT callback", List.of(true), callbacks);
            fixture.requestUnchangedResolution();
            assertEquals("A new resolver must not replay invalid partial data or disable deduplication",
                    List.of(true), callbacks);
            assertEquals(1, added.get());
            assertEquals(0, removed.get());
        }
    }

    private static void assertTxtReadiness(InetAddress address) {
        ServiceInfoImpl info = new ServiceInfoImpl("_p2pkit2._tcp.local.", "remote", "", 45001,
                0, 0, true, (byte[]) null);
        info.setServer("remote.local.");
        if (address instanceof Inet4Address) info.addAddress((Inet4Address) address);
        else info.addAddress((Inet6Address) address);
        assertArrayEquals("The wire-format getter remains compatible", new byte[] {0}, info.getTextBytes());
        assertFalse(info.getPropertyNames().hasMoreElements());
        assertFalse("SRV and an address are insufficient before TXT", info.hasData());
        assertFalse("Cloning or reading properties must not invent TXT evidence", info.clone().hasData());

        DNSRecord.Text empty = new DNSRecord.Text(info.getQualifiedName(), DNSRecordClass.CLASS_IN,
                true, 120, new byte[] {0});
        info.updateRecord(new DNSCache(1), empty.getCreated(), empty);
        assertTrue("An actual empty TXT record resolves a DNS-SD service", info.hasData());
        assertTrue(info.clone().hasData());
        assertArrayEquals(new byte[] {0}, info.getTextBytes());
        assertFalse(info.getPropertyNames().hasMoreElements());
    }

    private static final class QueryResolver extends ServiceInfoResolver {
        private QueryResolver(ServiceInfoImpl info) {
            super(null, info);
        }

        private DNSOutgoing questions() throws IOException {
            return addQuestions(new DNSOutgoing(DNSConstants.FLAGS_QR_QUERY));
        }

        @Override protected void send(DNSOutgoing outgoing) {
            throw new AssertionError("Unscheduled query construction must not need a native sender");
        }
    }
}
