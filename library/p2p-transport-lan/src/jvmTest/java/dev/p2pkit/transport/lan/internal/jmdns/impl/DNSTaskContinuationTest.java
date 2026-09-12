package dev.p2pkit.transport.lan.internal.jmdns.impl;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;
import dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask;
import org.junit.Test;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Timer;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertSame;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

public class DNSTaskContinuationTest {
    private static final int FLAGS = DNSConstants.FLAGS_QR_RESPONSE | DNSConstants.FLAGS_AA;
    private static final int ID = 0x4a39;
    private static final int CAPACITY = 512;
    private static final String TYPE = "_p2pkit._tcp.local.";

    @Test
    public void supportedResponseRetainsRequesterAndRecordsAcrossRepeatedOverflow() throws IOException {
        List<DNSRecord> records = serviceRecords(250);
        // Two ordinary services, with individually valid TXT records, require repeated continuation.
        records.addAll(serviceRecords(250, "22222222-2222-4222-8222-222222222222"));
        assertResponse(records, requester(49152), false, true);
    }

    @Test
    public void smallResponseDoesNotSplitOrChangeItsContext() throws IOException {
        assertResponse(serviceRecords(12), requester(49152), false, false);
    }

    @Test
    public void multicastContinuationPreservesDefaultOrExplicitDestinationAndZeroWireId() throws IOException {
        assertResponse(serviceRecords(250), null, true, true);
        assertResponse(serviceRecords(250), requester(DNSConstants.MDNS_PORT), true, true);
    }

    @Test
    public void everyRecordSectionAndQuestionUsesTheSameContinuationContext() throws IOException {
        for (int section = 0; section < 4; section++) {
            CapturingTask task = new CapturingTask();
            DNSOutgoing out = outgoing(requester(49152), false, 128);
            List<Object> expected = new ArrayList<>();
            for (int i = 0; i < 16; i++) {
                String name = "peer-" + i + "." + TYPE;
                if (section == 0) {
                    DNSQuestion question = DNSQuestion.newQuestion(
                        name, DNSRecordType.TYPE_PTR, DNSRecordClass.CLASS_IN, false);
                    expected.add(question);
                    out = task.addQuestion(out, question);
                } else {
                    DNSRecord record = new DNSRecord.Pointer(TYPE, DNSRecordClass.CLASS_IN, false, 120, name);
                    expected.add(record);
                    if (section == 1) {
                        out = task.addAnswer(out, record, 0);
                    } else if (section == 2) {
                        out = task.addAuthoritativeAnswer(out, record);
                    } else {
                        out = task.addAdditionalAnswer(out, null, record);
                    }
                }
            }
            task.send(out);
            assertTrue("Repeated overflow must be exercised", task.packets.size() >= 3);
            List<Object> actual = new ArrayList<>();
            for (Packet packet : task.packets) {
                DNSIncoming incoming = packet.parse();
                switch (section) {
                    case 0: actual.addAll(incoming.getQuestions()); break;
                    case 1: actual.addAll(incoming.getAnswers()); break;
                    case 2: actual.addAll(incoming.getAuthorities()); break;
                    default: actual.addAll(incoming.getAdditionals()); break;
                }
            }
            assertEquals("Section records must not be lost, duplicated or reordered", expected, actual);
            assertContexts(task.packets, requester(49152), false, 128);
        }
    }

    @Test
    public void sendFailureAndIndividuallyOversizedRecordStillFailWithoutSilentLoss() throws IOException {
        CapturingTask task = new CapturingTask();
        DNSOutgoing out = outgoing(requester(49152), false, 128);
        DNSRecord prefix = new DNSRecord.Pointer(TYPE, DNSRecordClass.CLASS_IN, false, 120, "peer." + TYPE);
        out.addAnswer(prefix, 0);
        DNSRecord tooLarge = new DNSRecord.Text("peer." + TYPE, DNSRecordClass.CLASS_IN, false, 120,
            new byte[CAPACITY]);
        IOException failure = new IOException("sentinel send failure");
        task.failure = failure;
        assertSame(failure, assertThrows(IOException.class, () -> task.addAnswer(out, tooLarge, 0)));
        assertEquals(1, task.sendAttempts);
        assertTrue(task.packets.isEmpty());

        task.failure = null;
        DNSOutgoing fresh = outgoing(requester(49152), false, 128);
        fresh.addAnswer(prefix, 0);
        assertThrows(IOException.class, () -> task.addAnswer(fresh, tooLarge, 0));
        assertEquals("Flush the prefix once, not an empty continuation", 2, task.sendAttempts);
        assertEquals(1, task.packets.size());
        assertEquals(Arrays.asList(prefix), new ArrayList<>(task.packets.get(0).parse().getAnswers()));
        assertEquals(FLAGS | DNSConstants.FLAGS_TC, task.packets.get(0).parse().getFlags());
    }

    private static void assertResponse(
        List<DNSRecord> records, InetSocketAddress destination, boolean multicast, boolean overflow
    ) throws IOException {
        CapturingTask task = new CapturingTask();
        DNSOutgoing out = outgoing(destination, multicast, CAPACITY);
        DNSQuestion question = DNSQuestion.newQuestion(TYPE, DNSRecordType.TYPE_PTR, DNSRecordClass.CLASS_IN, true);
        out = task.addQuestion(out, question);
        for (DNSRecord record : records) {
            // Prove overflow is not an individually oversized record disguised as a valid response.
            DNSOutgoing single = outgoing(destination, multicast, CAPACITY);
            single.addAnswer(record, 0);
            assertTrue(single.data().length <= CAPACITY);
            out = task.addAnswer(out, (DNSIncoming) null, record);
        }
        task.send(out);
        assertEquals("The supported response must exercise the intended branch", overflow, task.packets.size() > 1);
        if (records.size() > 4) {
            assertTrue("Repeated continuation must be exercised", task.packets.size() >= 3);
        }
        List<DNSQuestion> questions = new ArrayList<>();
        List<DNSRecord> answers = new ArrayList<>();
        for (Packet packet : task.packets) {
            DNSIncoming incoming = packet.parse();
            questions.addAll(incoming.getQuestions());
            answers.addAll(incoming.getAnswers());
            assertTrue(incoming.getAuthorities().isEmpty());
            assertTrue(incoming.getAdditionals().isEmpty());
        }
        assertEquals(Arrays.asList(question), questions);
        // DNSRecord equality includes record content, but not the serialization-time remaining TTL.
        assertEquals("All records must survive exactly once, in assembly order", records, answers);
        assertContexts(task.packets, destination, multicast, CAPACITY);
    }

    private static void assertContexts(
        List<Packet> packets, InetSocketAddress destination, boolean multicast, int capacity
    ) {
        for (int i = 0; i < packets.size(); i++) {
            Packet packet = packets.get(i);
            int flags = FLAGS | (i + 1 < packets.size() ? DNSConstants.FLAGS_TC : 0);
            assertEquals("Destination, wire ID, format, capacity and flags for packet " + i,
                Arrays.asList(destination, multicast ? 0 : ID, multicast, capacity, flags),
                Arrays.asList(packet.destination, unsignedShort(packet.bytes, 0), packet.multicast,
                    packet.capacity, unsignedShort(packet.bytes, 2)));
            assertTrue("Every serialized packet fits its payload budget", packet.bytes.length <= capacity);
        }
    }

    private static int unsignedShort(byte[] bytes, int offset) {
        return ((bytes[offset] & 0xff) << 8) | (bytes[offset + 1] & 0xff);
    }

    private static DNSOutgoing outgoing(InetSocketAddress destination, boolean multicast, int capacity) {
        DNSOutgoing out = new DNSOutgoing(FLAGS, multicast, capacity);
        out.setDestination(destination);
        out.setId(ID);
        return out;
    }

    private static InetSocketAddress requester(int port) throws IOException {
        // Documentation-only address: construction and parsing never create a socket or resolve a name.
        return new InetSocketAddress(InetAddress.getByAddress(new byte[] {(byte) 192, 0, 2, 1}), port);
    }

    private static List<DNSRecord> serviceRecords(int nameLength) throws IOException {
        return serviceRecords(nameLength, "11111111-1111-4111-8111-111111111111");
    }

    private static List<DNSRecord> serviceRecords(int nameLength, String peerId) throws IOException {
        Map<String, String> txt = new LinkedHashMap<>();
        txt.put("pid", peerId);
        txt.put("app", "a".repeat(64));
        txt.put("name", "n".repeat(nameLength));
        txt.put("plat", "JVM_DESKTOP");
        txt.put("caps", "LAN");
        txt.put("pv", "1");
        ServiceInfo info = ServiceInfo.create(TYPE, peerId, 45001, 0, 0, txt);
        if (nameLength == 250) {
            assertEquals("Supported plaintext-v1 TXT witness", 397, info.getTextBytes().length);
        }
        return new ArrayList<>(Arrays.asList(
            new DNSRecord.Pointer(TYPE, DNSRecordClass.CLASS_IN, false, 120, info.getQualifiedName()),
            new DNSRecord.Service(info.getQualifiedName(), DNSRecordClass.CLASS_IN, true, 120, 0, 0, 45001,
                "host.local."),
            new DNSRecord.Text(info.getQualifiedName(), DNSRecordClass.CLASS_IN, true, 120, info.getTextBytes()),
            new DNSRecord.IPv4Address("host.local.", DNSRecordClass.CLASS_IN, true, 120,
                new byte[] {(byte) 192, 0, 2, 2})
        ));
    }

    private static final class Packet {
        final InetSocketAddress destination;
        final boolean multicast;
        final int capacity;
        final byte[] bytes;

        Packet(DNSOutgoing out) {
            destination = out.getDestination();
            multicast = out.isMulticast();
            capacity = out.getMaxUDPPayload();
            bytes = out.data();
        }

        DNSIncoming parse() throws IOException {
            InetSocketAddress source = requester(multicast ? DNSConstants.MDNS_PORT : 49152);
            return new DNSIncoming(new DatagramPacket(bytes, bytes.length, source));
        }
    }

    private static final class CapturingTask extends DNSTask {
        final List<Packet> packets = new ArrayList<>();
        IOException failure;
        int sendAttempts;

        CapturingTask() {
            // Only direct record assembly is exercised, never JmDNS startup/timer scheduling.
            super(null);
        }

        @Override
        protected void send(DNSOutgoing out) throws IOException {
            sendAttempts++;
            if (failure != null) {
                throw failure;
            }
            packets.add(new Packet(out));
        }

        @Override
        public void start(Timer timer) {
            throw new AssertionError("Record-assembly test must not schedule a task");
        }

        @Override
        protected void runTask() {
            throw new AssertionError("Record-assembly test must not execute a scheduled task");
        }

        @Override
        public String getName() {
            return "capturing record assembly";
        }
    }
}
