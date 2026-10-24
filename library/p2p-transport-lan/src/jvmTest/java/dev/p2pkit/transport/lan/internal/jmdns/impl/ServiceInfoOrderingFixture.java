package dev.p2pkit.transport.lan.internal.jmdns.impl;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceListener;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;

import java.io.IOException;
import java.lang.reflect.Field;
import java.net.DatagramPacket;
import java.net.InetAddress;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Real cache replay, record parsing, ServiceInfo cloning and listener dispatch.
 * Only the scheduling pause and socket-free handle are test seams.
 * No fabricated resolved event, retry, timer or multicast socket supplies success.
 */
public final class ServiceInfoOrderingFixture implements AutoCloseable {
    private static final String SERVER = "ordered-source.local.";
    private static final ServiceListener NOOP = new ServiceListener() {
        @Override public void serviceAdded(ServiceEvent event) { }
        @Override public void serviceRemoved(ServiceEvent event) { }
        @Override public void serviceResolved(ServiceEvent event) { }
    };

    private final String type;
    private final String name;
    private final byte[] completeTxt;
    private final MemoryDns dns;
    private final ExecutorService originalExecutor;
    private final AtomicReference<Throwable> workerFailure = new AtomicReference<>();
    private Thread older;
    private Thread newer;
    private Thread independent;

    public ServiceInfoOrderingFixture(String type, String name, byte[] completeTxt) throws Exception {
        this(type, name, completeTxt, false);
    }

    public ServiceInfoOrderingFixture(String type, String name, byte[] completeTxt, boolean includePtr) throws Exception {
        this.type = type;
        this.name = name;
        this.completeTxt = completeTxt.clone();
        dns = new MemoryDns();
        Field field = JmDNSImpl.class.getDeclaredField("_executor");
        field.setAccessible(true);
        originalExecutor = (ExecutorService) field.get(dns);
        // Keep the ordinary collector installed before the cache contains SRV/A.
        dns.addServiceListener(type, NOOP);
        dns.removeServiceListener(type, NOOP);
        dns.handleResponse(packet(
                new DNSRecord.Service(name + "." + type, DNSRecordClass.CLASS_IN,
                        true, 120, 0, 0, 45001, SERVER),
                new DNSRecord.IPv4Address(SERVER, DNSRecordClass.CLASS_IN,
                        true, 120, new byte[] {127, 0, 0, 1})));
        if (includePtr) {
            // Exercise the ordinary collector/getServiceInfoFromCache path as
            // well as a late listener observing a still-PTR-less SRV response.
            dns.handleResponse(packet(new DNSRecord.Pointer(type, DNSRecordClass.CLASS_IN,
                    false, 120, name + "." + type)));
            drainCallbacks();
        }
    }

    /**
     * Pause the cache-replay thread at its first resolved clone, or at replay
     * completion when no clone was emitted. Then deliver the incoming TXT on
     * another thread. A premature pre-TXT clone can overtake that resolution;
     * the fixed source must not manufacture a resolved clone before TXT.
     */
    public void replayAgainstIncomingTxt(ServiceListener application) throws Exception {
        replayAgainstIncomingTxt(application, false);
    }

    /** Also exercise a second live resolver for the same service, not just one info monitor. */
    public void replayAgainstIncomingTxt(ServiceListener application, boolean secondResolver) throws Exception {
        if (older != null) throw new IllegalStateException("Fixture is one-shot");
        ServiceListener requestingListener = new ServiceListener() {
            @Override public void serviceAdded(ServiceEvent event) {
                application.serviceAdded(event);
                // Same production request used by JvmLanDiscoveryTransport.
                dns.requestServiceInfo(event.getType(), event.getName(), true);
            }

            @Override public void serviceRemoved(ServiceEvent event) {
                application.serviceRemoved(event);
            }

            @Override public void serviceResolved(ServiceEvent event) {
                application.serviceResolved(event);
            }
        };
        older = worker("ordered-cache-replay", () -> dns.addServiceListener(type, requestingListener));
        dns.olderThread = older;
        older.start();
        try {
            await(dns.olderBoundary, "Original cache replay did not reach its scheduling boundary");
            checkIndependentServiceProgress();
            if (secondResolver) {
                ServiceInfoImpl other = dns.resolveServiceInfo(type, name, "", true);
                if (other == dns.originalInfo) throw new AssertionError("Expected a distinct original resolver info");
            }
            newer = worker("ordered-incoming-txt", () -> {
                dns.handleResponse(packet(new DNSRecord.Text(name + "." + type,
                        DNSRecordClass.CLASS_IN, true, 120, completeTxt)));
            });
            newer.start();
            join(newer);
            rethrowWorkerFailure();
            drainCallbacks();
        } finally {
            dns.releaseOlder.countDown();
            join(older);
            join(newer);
        }
        rethrowWorkerFailure();
        drainCallbacks();
        if (dns.getCache().getDNSEntry(name + "." + type,
                DNSRecordType.TYPE_TXT, DNSRecordClass.CLASS_IN) == null) {
            throw new AssertionError("Incoming TXT was not retained in the real cache");
        }
    }

    public void requestUnchangedResolution() throws Exception {
        dns.requestServiceInfo(type, name, true);
        drainCallbacks();
    }

    public void receiveTxt(byte[] txt) throws Exception {
        dns.handleResponse(packet(new DNSRecord.Text(name + "." + type,
                DNSRecordClass.CLASS_IN, true, 120, txt)));
        drainCallbacks();
    }

    private void checkIndependentServiceProgress() throws Exception {
        CountDownLatch resolved = new CountDownLatch(1);
        independent = worker("ordered-independent-service", () -> {
            String otherType = "_independent._tcp.local.";
            String otherName = "independent";
            String otherServer = "independent.local.";
            dns.addServiceListener(otherType, NOOP);
            dns.removeServiceListener(otherType, NOOP);
            dns.handleResponse(packet(
                    new DNSRecord.Service(otherName + "." + otherType, DNSRecordClass.CLASS_IN,
                            true, 120, 0, 0, 45002, otherServer),
                    new DNSRecord.IPv4Address(otherServer, DNSRecordClass.CLASS_IN,
                            true, 120, new byte[] {127, 0, 0, 1}),
                    new DNSRecord.Text(otherName + "." + otherType,
                            DNSRecordClass.CLASS_IN, true, 120, completeTxt)));
            dns.addServiceListener(otherType, new ServiceListener() {
                @Override public void serviceAdded(ServiceEvent event) {
                    dns.requestServiceInfo(event.getType(), event.getName(), true);
                }
                @Override public void serviceRemoved(ServiceEvent event) { }
                @Override public void serviceResolved(ServiceEvent event) {
                    if (java.util.Arrays.equals(completeTxt, event.getInfo().getTextBytes())) resolved.countDown();
                }
            });
        });
        independent.start();
        join(independent);
        rethrowWorkerFailure();
        await(resolved, "An independent service on the same handle could not resolve during the pause");
    }

    private Thread worker(String label, CheckedRunnable body) {
        return new Thread(() -> {
            try {
                body.run();
            } catch (Throwable failure) {
                workerFailure.compareAndSet(null, failure);
            }
        }, label);
    }

    private void rethrowWorkerFailure() {
        if (workerFailure.get() != null) throw new AssertionError("Controlled worker failed", workerFailure.get());
    }

    private void drainCallbacks() throws Exception {
        originalExecutor.submit(() -> { }).get(5, TimeUnit.SECONDS);
        originalExecutor.submit(() -> { }).get(5, TimeUnit.SECONDS);
    }

    private static void await(CountDownLatch latch, String message) {
        try {
            if (!latch.await(5, TimeUnit.SECONDS)) throw new AssertionError(message);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new AssertionError(message, error);
        }
    }

    private static void join(Thread thread) throws InterruptedException {
        if (thread == null) return;
        thread.join(5000);
        if (thread.isAlive()) throw new AssertionError("Controlled worker did not retire");
    }

    private static DNSIncoming packet(DNSRecord... records) throws IOException {
        DNSOutgoing outgoing = new DNSOutgoing(DNSConstants.FLAGS_QR_RESPONSE | DNSConstants.FLAGS_AA,
                true, 4096);
        for (DNSRecord record : records) outgoing.addAnswer(record, 0);
        byte[] bytes = outgoing.data();
        return new DNSIncoming(new DatagramPacket(bytes, bytes.length,
                InetAddress.getByAddress(new byte[] {127, 0, 0, 1}), DNSConstants.MDNS_PORT));
    }

    @Override public void close() throws Exception {
        dns.releaseOlder.countDown();
        try {
            join(older);
            join(newer);
            join(independent);
        } finally {
            dns.close();
        }
        if (dns.getSocket() != null || !originalExecutor.isShutdown()
                || !originalExecutor.awaitTermination(5, TimeUnit.SECONDS)) {
            throw new AssertionError("Original socket-free handle/executor was not disposed");
        }
    }

    private interface CheckedRunnable {
        void run() throws Exception;
    }

    private static final class MemoryDns extends JmDNSImpl {
        private final CountDownLatch olderBoundary = new CountDownLatch(1);
        private final CountDownLatch releaseOlder = new CountDownLatch(1);
        private volatile ServiceInfoImpl originalInfo;
        private volatile Thread olderThread;

        private MemoryDns() throws IOException {
            super(InetAddress.getByAddress("fixture", new byte[] {127, 0, 0, 1}),
                    "ordered-fixture", new DNSCache(16));
        }

        @Override public void startProber() { }
        @Override public void startTypeResolver() { }
        @Override public void startServiceResolver(String type) { }

        @Override public void startServiceInfoResolver(ServiceInfoImpl info) {
            if (Thread.currentThread() == olderThread) originalInfo = info;
            info.setDns(this);
            addListener(info, DNSQuestion.newQuestion(info.getQualifiedName(),
                    DNSRecordType.TYPE_ANY, DNSRecordClass.CLASS_IN, false));
            pauseOriginalReplay();
        }

        @Override void handleServiceResolved(ServiceEvent event) {
            if (Thread.currentThread() == olderThread && olderBoundary.getCount() != 0L) {
                if (!event.getInfo().hasData() || event.getInfo().getPropertyNames().hasMoreElements()) {
                    throw new AssertionError("Expected original complete-address, pre-TXT clone");
                }
                pauseOriginalReplay();
            }
            super.handleServiceResolved(event);
        }

        private void pauseOriginalReplay() {
            if (Thread.currentThread() == olderThread && olderBoundary.getCount() != 0L) {
                olderBoundary.countDown();
                await(releaseOlder, "Original cache replay was not released");
            }
        }
    }
}
