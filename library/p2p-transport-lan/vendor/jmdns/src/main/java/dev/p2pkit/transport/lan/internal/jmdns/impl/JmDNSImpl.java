/*
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/*
 * P2pKit modification: privately relocated from javax.jmdns to
 * dev.p2pkit.transport.lan.internal.jmdns. See the accompanying
 * PROVENANCE.json and MODIFICATIONS.txt for origin and change details.
 */
package dev.p2pkit.transport.lan.internal.jmdns.impl;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.MulticastSocket;
import java.net.SocketAddress;
import java.net.SocketException;
import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.IdentityHashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Random;
import java.util.Set;
import java.util.Timer;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import dev.p2pkit.transport.lan.internal.jmdns.JmDNS;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo.Fields;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceListener;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceTypeListener;
import dev.p2pkit.transport.lan.internal.jmdns.impl.ListenerStatus.ServiceListenerStatus;
import dev.p2pkit.transport.lan.internal.jmdns.impl.ListenerStatus.ServiceTypeListenerStatus;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSState;
import dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask;
import dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.RecordReaper;
import dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask;
import dev.p2pkit.transport.lan.internal.jmdns.impl.util.NamedThreadFactory;

// REMIND: multiple IP addresses

/**
 * mDNS implementation in Java.
 *
 * @author Arthur van Hoff, Rick Blair, Jeff Sonstein, Werner Randelshofer, Pierre Frisch, Scott Lewis, Kai Kreuzer, Victor Toni
 */
public class JmDNSImpl extends JmDNS implements DNSStatefulObject, DNSTaskStarter {

    private static final boolean IS_WINDOWS;

    private final Logger logger = LoggerFactory.getLogger(JmDNSImpl.class);

    public enum Operation {
        Remove, Update, Add, RegisterServiceType, Noop
    }

    /**
     * This is the multicast group, we are listening to for multicast DNS messages.
     */
    private volatile InetAddress     _group;
    /**
     * This is our multicast socket.
     */
    private volatile MulticastSocket _socket;

    /**
     * Holds instances of JmDNS.DNSListener. Must be a synchronized collection, because it is updated from concurrent threads.
     */
    private final List<DNSListener> _listeners;

    /**
     * Holds instances of ServiceListener's. Keys are Strings holding a fully qualified service type. Values are LinkedList's of ServiceListener's.
     */
    /* default */ final ConcurrentMap<String, List<ServiceListenerStatus>> _serviceListeners;

    /**
     * Holds instances of ServiceTypeListener's.
     */
    private final Set<ServiceTypeListenerStatus> _typeListeners;

    /**
     * Cache for DNSEntry's.
     */
    private final DNSCache _cache;

    /**
     * This hashtable holds the services that have been registered. Keys are instances of String which hold an all lower-case version of the fully qualified service name. Values are instances of ServiceInfo.
     */
    private final ConcurrentMap<String, ServiceInfo> _services;

    /**
     * This hashtable holds the service types that have been registered or that have been received in an incoming datagram.<br/>
     * Keys are instances of String which hold an all lower-case version of the fully qualified service type.<br/>
     * Values hold the fully qualified service type.
     */
    private final ConcurrentMap<String, ServiceTypeEntry> _serviceTypes;

    private volatile Delegate _delegate;

    protected final long _threadSleepDurationMs;

    /**
     * This is used to store type entries. The type is stored as a call variable and the map support the subtypes.
     * <p>
     * The key is the lowercase version as the value is the case preserved version.
     * </p>
     */
    public static class ServiceTypeEntry extends AbstractMap<String, String>implements Cloneable {

        private final Set<Map.Entry<String, String>> _entrySet;

        private final String _type;

        private static class SubTypeEntry implements Entry<String, String>, java.io.Serializable, Cloneable {

            private static final long serialVersionUID = 9188503522395855322L;

            private final String _key;
            private final String _value;

            public SubTypeEntry(String subtype) {
                super();
                _value = (subtype != null ? subtype : "");
                _key = _value.toLowerCase();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public String getKey() {
                return _key;
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public String getValue() {
                return _value;
            }

            /**
             * Replaces the value corresponding to this entry with the specified value (optional operation). This implementation simply throws <tt>UnsupportedOperationException</tt>, as this class implements an <i>immutable</i> map entry.
             *
             * @param value
             *            new value to be stored in this entry
             * @return (Does not return)
             * @exception UnsupportedOperationException
             *                always
             */
            @Override
            public String setValue(String value) {
                throw new UnsupportedOperationException();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public boolean equals(Object entry) {
                if (!(entry instanceof Map.Entry)) {
                    return false;
                }
                return this.getKey().equals(((Map.Entry<?, ?>) entry).getKey()) && this.getValue().equals(((Map.Entry<?, ?>) entry).getValue());
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public int hashCode() {
                return (_key == null ? 0 : _key.hashCode()) ^ (_value == null ? 0 : _value.hashCode());
            }

            /*
             * (non-Javadoc)
             * @see java.lang.Object#clone()
             */
            @Override
            public SubTypeEntry clone() {
                // Immutable object
                return this;
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public String toString() {
                return _key + "=" + _value;
            }

        }

        public ServiceTypeEntry(String type) {
            super();
            this._type = type;
            this._entrySet = new HashSet<>();
        }

        /**
         * The type associated with this entry.
         *
         * @return the type
         */
        public String getType() {
            return _type;
        }

        /*
         * (non-Javadoc)
         * @see java.util.AbstractMap#entrySet()
         */
        @Override
        public Set<Map.Entry<String, String>> entrySet() {
            return _entrySet;
        }

        /**
         * Returns <code>true</code> if this set contains the specified element. More formally, returns <code>true</code> if and only if this set contains an element <code>e</code> such that
         * <code>(o==null&nbsp;?&nbsp;e==null&nbsp;:&nbsp;o.equals(e))</code>.
         *
         * @param subtype
         *            element whose presence in this set is to be tested
         * @return <code>true</code> if this set contains the specified element
         */
        public boolean contains(String subtype) {
            return subtype != null && this.containsKey(subtype.toLowerCase());
        }

        /**
         * Adds the specified element to this set if it is not already present. More formally, adds the specified element <code>e</code> to this set if this set contains no element <code>e2</code> such that
         * <code>(e==null&nbsp;?&nbsp;e2==null&nbsp;:&nbsp;e.equals(e2))</code>. If this set already contains the element, the call leaves the set unchanged and returns <code>false</code>.
         *
         * @param subtype
         *            element to be added to this set
         * @return <code>true</code> if this set did not already contain the specified element
         */
        public boolean add(String subtype) {
            if (subtype == null || this.contains(subtype)) {
                return false;
            }
            _entrySet.add(new SubTypeEntry(subtype));
            return true;
        }

        /**
         * Returns an iterator over the elements in this set. The elements are returned in no particular order (unless this set is an instance of some class that provides a guarantee).
         *
         * @return an iterator over the elements in this set
         */
        public Iterator<String> iterator() {
            return this.keySet().iterator();
        }

        /*
         * (non-Javadoc)
         * @see java.util.AbstractMap#clone()
         */
        @Override
        public ServiceTypeEntry clone() {
            ServiceTypeEntry entry = new ServiceTypeEntry(this.getType());
            for (Map.Entry<String, String> subTypeEntry : this.entrySet()) {
                entry.add(subTypeEntry.getValue());
            }
            return entry;
        }

        /*
         * (non-Javadoc)
         * @see java.util.AbstractMap#toString()
         */
        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder(200);
            if (this.isEmpty()) {
                sb.append("empty");
            } else {
                for (String value : this.values()) {
                    sb.append(value);
                    sb.append(", ");
                }
                sb.setLength(sb.length() - 2);
            }
            return sb.toString();
        }

    }

    /**
     * This is the shutdown hook, we registered with the java runtime.
     */
    protected Thread _shutdown;

    /**
     * Handle on the local host
     */
    private HostInfo _localHost;

    private Thread _incomingListener;

    /**
     * Throttle count. This is used to count the overall number of probes sent by JmDNS. When the last throttle increment happened .
     */
    private int _throttle;

    /**
     * Last throttle increment.
     */
    private long _lastThrottleIncrement;

    // Initialized before any constructor dispatch; protocol state is not ownership.
    private final JmDNSLifecycle _lifecycle = new JmDNSLifecycle();
    private final ExecutorService _executor;
    private volatile DNSTaskStarter _taskStarter;

    /**
     * The source for random values. This is used to introduce random delays in responses. This reduces the potential for collisions on the network.
     */
    private final static Random _random = new Random();

    /**
     * This lock is used to coordinate processing of incoming and outgoing messages. This is needed, because the Rendezvous Conformance Test does not forgive race conditions.
     */
    private final ReentrantLock _ioLock = new ReentrantLock();

    /**
     * If an incoming package which needs an answer is truncated, we store it here. We add more incoming DNSRecords to it, until the JmDNS.Responder timer picks it up.<br/>
     * FIXME [PJYF June 8 2010]: This does not work well with multiple planned answers for packages that came in from different clients.
     */
    private DNSIncoming _plannedAnswer;

    // State machine

    /**
     * This hashtable is used to maintain a list of service types being collected by this JmDNS instance. The key of the hashtable is a service type name, the value is an instance of JmDNS.ServiceCollector.
     *
     * @see #list
     */
    private final ConcurrentMap<String, ServiceCollector> _serviceCollectors;

    private final String _name;

    static {
        final String osName = System.getProperty("os.name");
        if (osName == null) {
            IS_WINDOWS = false;
        } else {
            IS_WINDOWS = osName.startsWith("Windows");
        }
    }

    /**
     * Main method to display API information if run from java -jar
     *
     * @param argv
     *            the command line arguments
     */
    public static void main(String[] argv) {
        String version;
        try {
            final Properties pomProperties = new Properties();
            pomProperties.load(JmDNSImpl.class.getResourceAsStream(
                    "/dev/p2pkit/transport/lan/internal/jmdns/version.properties"));
            version = pomProperties.getProperty("jmdns.version");
        } catch (Exception e) {
            version = "RUNNING.IN.IDE.FULL";
        }
        System.out.println("JmDNS version \"" + version + "\"");
        System.out.println(" ");

        System.out.println("Running on java version \"" + System.getProperty("java.version") + "\"" + " (build " + System.getProperty("java.runtime.version") + ")" + " from " + System.getProperty("java.vendor"));

        System.out.println("Operating environment \"" + System.getProperty("os.name") + "\"" + " version " + System.getProperty("os.version") + " on " + System.getProperty("os.arch"));

        System.out.println("For more information on JmDNS please visit https://jmdns.org");
    }

    /**
     * Create an instance of JmDNS and bind it to a specific network interface given its IP-address.
     *
     * @param address
     *            IP address to bind to.
     * @param name
     *            name of the newly created JmDNS
     * @exception IOException
     */
    public JmDNSImpl(InetAddress address, String name) throws IOException {
        this(address, name, 0L);
    }
    /**
     * Create an instance of JmDNS and bind it to a specific network interface given its IP-address.
     *
     * @param address
     *            IP address to bind to.
     * @param name
     *            name of the newly created JmDNS
     * @param threadSleepDurationMs
     *            time in milliseconds that the JmDNS listener thread should sleep between multicast receives
     * @exception IOException
     */
    public JmDNSImpl(InetAddress address, String name, long threadSleepDurationMs) throws IOException {
        super();
        logger.debug("JmDNS instance created");

        _cache = new DNSCache(100);

        _listeners = Collections.synchronizedList(new ArrayList<>());
        _serviceListeners = new ConcurrentHashMap<>();
        _typeListeners = Collections.synchronizedSet(Collections.newSetFromMap(
                new IdentityHashMap<ServiceTypeListenerStatus, Boolean>()));
        _serviceCollectors = new ConcurrentHashMap<>();

        _services = new ConcurrentHashMap<>(20);
        _serviceTypes = new ConcurrentHashMap<>(20);

        _localHost = HostInfo.newHostInfo(address, this, name);
        _name = (name != null ? name : _localHost.getName());
        _threadSleepDurationMs = threadSleepDurationMs;
        _executor = Executors.newSingleThreadExecutor(new NamedThreadFactory("JmDNS"));

        // _cancelerTimer = new Timer("JmDNS.cancelerTimer");

        // (ldeck 2.1.1) preventing shutdown blocking thread
        // -------------------------------------------------
        // _shutdown = new Thread(new Shutdown(), "JmDNS.Shutdown");
        // Runtime.getRuntime().addShutdownHook(_shutdown);

        // -------------------------------------------------

        synchronized (_lifecycle) {
            _lifecycle.startupInProgress = true;
            _lifecycle.startupOwner = Thread.currentThread();
        }
        try {
            // Allocate once, before any task or listener can run. Never look it up
            // through the allocating factory again, including after failed close.
            DNSTaskStarter starter = DNSTaskStarter.Factory.getInstance().getStarter(this);
            synchronized (_lifecycle) {
                _taskStarter = starter;
            }
            if (!this.openMulticastSocket(this.getLocalHost(), null)) {
                throw new IOException("JmDNS was closed during construction");
            }
            this.start(this.getServices().values());
            this.startReaper();
        } catch (IOException | RuntimeException | Error failure) {
            finishStartupOwnership();
            abortConstruction(failure);
            throw failure;
        } finally {
            finishStartupOwnership();
        }
    }

    private void finishStartupOwnership() {
        synchronized (_lifecycle) {
            _lifecycle.startupInProgress = false;
            _lifecycle.startupOwner = null;
            _lifecycle.notifyAll();
        }
    }

    private void start(Collection<? extends ServiceInfo> serviceInfos) {
        startSocketListener();
        this.startProber();
        for (ServiceInfo info : serviceInfos) {
            try {
                this.registerService(new ServiceInfoImpl(info));
            } catch (final Exception exception) {
                logger.warn("start() Registration exception ", exception);
            }
        }
    }

    private void startSocketListener() {
        MulticastSocket socket = _socket;
        if (socket == null || isTerminalRequested()) {
            return;
        }
        // Construction may call public getName(); keep it outside the slice.
        SocketListener listener = new SocketListener(this, socket);
        if (!_lifecycle.beginMutation(false)) {
            return;
        }
        JmDNSLifecycle.OwnedThread owned = new JmDNSLifecycle.OwnedThread();
        owned.thread = listener;
        try {
            synchronized (_lifecycle) {
                if (_incomingListener != null || _socket != socket) {
                    return;
                }
                _incomingListener = listener;
                _lifecycle.listeners.add(owned);
            }
            try {
                listener.start();
                synchronized (_lifecycle) {
                    owned.started = true;
                }
            } finally {
                synchronized (_lifecycle) {
                    owned.launchResolved = true;
                    _lifecycle.notifyAll();
                }
            }
        } finally {
            _lifecycle.endMutation();
        }
    }

    private InetSocketAddress getMulticastBindAddress(HostInfo hostInfo) {
        if (IS_WINDOWS) {
            return new InetSocketAddress(hostInfo.getInetAddress(), DNSConstants.MDNS_PORT);
        } else {
            return new InetSocketAddress(DNSConstants.MDNS_PORT);
        }
    }

    private boolean openMulticastSocket(HostInfo hostInfo, JmDNSLifecycle.Recovery recovery) throws IOException {
        if (_group == null) {
            _group = InetAddress.getByName(hostInfo.getInetAddress() instanceof Inet6Address
                    ? DNSConstants.MDNS_GROUP_IPV6 : DNSConstants.MDNS_GROUP);
        }
        if (isTerminalRequested()) {
            return false;
        }
        // A candidate is private until every operation which can fail has run.
        MulticastSocket candidate = new MulticastSocket(getMulticastBindAddress(hostInfo));
        synchronized (_lifecycle) {
            _lifecycle.sockets.add(candidate);
        }
        boolean published = false;
        Throwable preparationFailure = null;
        try {
            if (hostInfo.getInterface() != null) {
                SocketAddress multicastAddr = new InetSocketAddress(_group, DNSConstants.MDNS_PORT);
                candidate.setNetworkInterface(hostInfo.getInterface());
                candidate.joinGroup(multicastAddr, hostInfo.getInterface());
            } else {
                candidate.joinGroup(_group);
            }
            candidate.setTimeToLive(255);
            if (recovery != null) {
                beforeRecoverySocketPublication(candidate);
            }
            synchronized (_lifecycle) {
                if (!_lifecycle.terminalRequested && (recovery == null
                        || (_lifecycle.recovery == recovery && recovery.mutating))) {
                    _socket = candidate;
                    _lifecycle.socketPublications++;
                    published = true;
                }
            }
            return published;
        } catch (IOException | RuntimeException | Error failure) {
            preparationFailure = failure;
            throw failure;
        } finally {
            if (!published) {
                List<Throwable> failures = new ArrayList<>();
                disposeSocket(candidate, failures);
                for (Throwable failure : failures) {
                    if (preparationFailure != null) {
                        preparationFailure.addSuppressed(failure);
                    } else {
                        logger.warn("Could not dispose unpublished multicast socket", failure);
                    }
                }
            }
        }
    }

    private void disposeSocket(MulticastSocket socket, List<Throwable> failures) {
        if (!socket.isClosed()) {
            try {
                socket.leaveGroup(_group);
            } catch (Throwable failure) {
                failures.add(failure);
            }
            // A leaveGroup failure must never skip the independent close.
            try {
                socket.close();
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        if (socket.isClosed()) {
            synchronized (_lifecycle) {
                _lifecycle.sockets.remove(socket);
                if (_socket == socket) {
                    _socket = null;
                }
            }
        } else {
            failures.add(new JmDNSLifecycle.CloseIncompleteException("Multicast socket remains open"));
        }
    }

    private void disposeSockets(List<Throwable> failures) {
        List<MulticastSocket> sockets;
        synchronized (_lifecycle) {
            sockets = new ArrayList<>(_lifecycle.sockets);
        }
        for (MulticastSocket socket : sockets) {
            disposeSocket(socket, failures);
        }
    }

    private void awaitOwnedThread(JmDNSLifecycle.OwnedThread owned, JmDNSLifecycle.WaitBudget budget,
            String obligation) throws InterruptedException {
        synchronized (_lifecycle) {
            while (!owned.launchResolved) {
                budget.await(_lifecycle, obligation + " launch");
            }
        }
        if (owned.started) {
            budget.join(owned.thread, obligation);
        }
    }

    private void drainSocketListeners(JmDNSLifecycle.WaitBudget budget) throws InterruptedException {
        List<JmDNSLifecycle.OwnedThread> listeners;
        synchronized (_lifecycle) {
            listeners = new ArrayList<>(_lifecycle.listeners);
        }
        for (JmDNSLifecycle.OwnedThread listener : listeners) {
            awaitOwnedThread(listener, budget, "socket listener");
            synchronized (_lifecycle) {
                _lifecycle.listeners.remove(listener);
                if (_incomingListener == listener.thread) {
                    _incomingListener = null;
                }
            }
        }
    }

    private void abortConstruction(Throwable original) {
        try {
            // The same arbiter owns constructor unwind, including tasks/recovery
            // already launched by constructor dispatch. Never a second disposer.
            closeOwnedLifetime();
        } catch (Throwable disposalFailure) {
            original.addSuppressed(disposalFailure);
        }
    }

    public final boolean isTerminalRequested() {
        synchronized (_lifecycle) {
            return _lifecycle.terminalRequested;
        }
    }

    public final boolean enterTaskExecution(boolean cancellationTask) {
        return _lifecycle.enterTask(cancellationTask);
    }

    public final void exitTaskExecution() {
        _lifecycle.exitTask();
    }

    public final boolean beginProducerMutation() {
        return _lifecycle.beginMutation(false);
    }

    public final void endProducerMutation() {
        _lifecycle.endMutation();
    }

    private boolean beginOwnedTaskMutation(boolean cancellation) {
        synchronized (_lifecycle) {
            if (cancellation && _lifecycle.terminalRequested) {
                Thread caller = Thread.currentThread();
                boolean closeOwner = _lifecycle.attempt != null && _lifecycle.attempt.owner == caller
                        && _lifecycle.attempt.outcome == null;
                boolean recoveryOwner = _lifecycle.recovery != null && _lifecycle.recovery.thread == caller
                        && _lifecycle.recovery.mutating;
                if (!closeOwner && !recoveryOwner) {
                    return false;
                }
            }
            return _lifecycle.beginMutation(cancellation);
        }
    }

    boolean beginTaskStart(boolean cancellation) {
        if (!beginOwnedTaskMutation(cancellation)) {
            return false;
        }
        if (!cancellation) {
            synchronized (_lifecycle) {
                _lifecycle.normalTaskStarts++;
            }
        }
        return true;
    }

    /** Called only inside the same admitted slice as actual Timer insertion. */
    private void associateTaskForLifetime(DNSTask task, DNSState state) {
        synchronized (this) {
            _localHost.associateWithTask(task, state);
        }
        for (ServiceInfo info : _services.values()) {
            ((ServiceInfoImpl) info).associateWithTaskForLifetime(task, state);
        }
    }

    /** Actual Timer insertion is fenced after all start calculations/overrides. */
    public final void scheduleTask(DNSTask task, Timer timer, long delay, long period, boolean cancellation) {
        if (!beginOwnedTaskMutation(cancellation)) {
            return;
        }
        try {
            associateScheduledTask(task);
            timer.schedule(task, delay, period);
        } finally {
            _lifecycle.endMutation();
        }
    }

    public final void scheduleTask(DNSTask task, Timer timer, long delay, boolean cancellation) {
        if (!beginOwnedTaskMutation(cancellation)) {
            return;
        }
        try {
            associateScheduledTask(task);
            timer.schedule(task, delay);
        } finally {
            _lifecycle.endMutation();
        }
    }

    private void associateScheduledTask(DNSTask task) {
        if (task instanceof DNSStateTask) {
            associateTaskForLifetime(task, ((DNSStateTask) task).getInitialAssociationState());
        }
    }

    void enterListenerExecution() {
        _lifecycle.enterDependent();
    }

    void exitListenerExecution() {
        _lifecycle.exitDependent();
        synchronized (_lifecycle) {
            _lifecycle.notifyAll();
        }
    }

    private void dispatchCallback(Runnable callback) {
        if (!_lifecycle.reserveCallback(false)) {
            return;
        }
        _lifecycle.enterDependent();
        try {
            callback.run();
        } finally {
            _lifecycle.exitDependent();
            _lifecycle.endCallback();
        }
    }

    private void submitCallback(final Runnable callback) {
        if (!_lifecycle.reserveCallback(true)) {
            return;
        }
        boolean accepted = false;
        try {
            _executor.submit(new Runnable() {
                @Override
                public void run() {
                    _lifecycle.enterDependent();
                    try {
                        callback.run();
                    } finally {
                        _lifecycle.exitDependent();
                        _lifecycle.endCallback();
                    }
                }
            });
            accepted = true;
        } finally {
            if (!accepted) {
                _lifecycle.endCallback();
            }
            _lifecycle.endSubmission();
        }
    }

    // State machine
    /**
     * {@inheritDoc}
     */
    @Override
    public boolean advanceState(DNSTask task) {
        return this._localHost.advanceState(task);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean revertState() {
        if (!beginProducerMutation()) {
            return false;
        }
        try {
            return this._localHost.revertState();
        } finally {
            endProducerMutation();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean cancelState() {
        return this._localHost.cancelState();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean closeState() {
        return this._localHost.closeState();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean recoverState() {
        if (!beginProducerMutation()) {
            return false;
        }
        try {
            return this._localHost.recoverState();
        } finally {
            endProducerMutation();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public JmDNSImpl getDns() {
        return this;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void associateWithTask(DNSTask task, DNSState state) {
        this._localHost.associateWithTask(task, state);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void removeAssociationWithTask(DNSTask task) {
        this._localHost.removeAssociationWithTask(task);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isAssociatedWithTask(DNSTask task, DNSState state) {
        return this._localHost.isAssociatedWithTask(task, state);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isProbing() {
        return this._localHost.isProbing();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isAnnouncing() {
        return this._localHost.isAnnouncing();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isAnnounced() {
        return this._localHost.isAnnounced();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isCanceling() {
        return this._localHost.isCanceling();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isCanceled() {
        return this._localHost.isCanceled();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isClosing() {
        return this._localHost.isClosing();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isClosed() {
        return this._localHost.isClosed();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean waitForAnnounced(long timeout) {
        return this._localHost.waitForAnnounced(timeout);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean waitForCanceled(long timeout) {
        return this._localHost.waitForCanceled(timeout);
    }

    /**
     * Return the DNSCache associated with the cache variable
     *
     * @return DNS cache
     */
    public DNSCache getCache() {
        return _cache;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String getName() {
        return _name;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String getHostName() {
        return _localHost.getName();
    }

    /**
     * Returns the local host info
     *
     * @return local host info
     */
    public HostInfo getLocalHost() {
        return _localHost;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public InetAddress getInetAddress() throws IOException {
        return _localHost.getInetAddress();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    @Deprecated
    public InetAddress getInterface() throws IOException {
        return _socket.getInterface();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ServiceInfo getServiceInfo(String type, String name) {
        return this.getServiceInfo(type, name, false, DNSConstants.SERVICE_INFO_TIMEOUT);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ServiceInfo getServiceInfo(String type, String name, long timeout) {
        return this.getServiceInfo(type, name, false, timeout);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ServiceInfo getServiceInfo(String type, String name, boolean persistent) {
        return this.getServiceInfo(type, name, persistent, DNSConstants.SERVICE_INFO_TIMEOUT);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ServiceInfo getServiceInfo(String type, String name, boolean persistent, long timeout) {
        final ServiceInfoImpl info = this.resolveServiceInfo(type, name, "", persistent);
        this.waitForInfoData(info, timeout);
        return (info.hasData() ? info : null);
    }

    ServiceInfoImpl resolveServiceInfo(String type, String name, String subtype, boolean persistent) {
        if (!isTerminalRequested()) {
            this.cleanCache();
            this.registerServiceType(type);
            ensureServiceCollector(type);
        }
        final ServiceInfoImpl info = this.getServiceInfoFromCache(type, name, subtype, persistent);
        this.startServiceInfoResolver(info);
        return info;
    }

    private ServiceCollector ensureServiceCollector(String type) {
        String loType = type.toLowerCase();
        ServiceCollector collector;
        boolean created = false;
        if (!beginProducerMutation()) {
            return null;
        }
        try {
            collector = _serviceCollectors.get(loType);
            if (collector == null) {
                ServiceCollector candidate = new ServiceCollector(type);
                ServiceCollector existing = _serviceCollectors.putIfAbsent(loType, candidate);
                collector = existing == null ? candidate : existing;
                created = existing == null;
            }
        } finally {
            endProducerMutation();
        }
        if (created) {
            this.addServiceListener(loType, collector, ListenerStatus.SYNCHRONOUS, true);
        }
        return collector;
    }

    ServiceInfoImpl getServiceInfoFromCache(String type, String name, String subtype, boolean persistent) {
        // Check if the answer is in the cache.
        ServiceInfoImpl info = new ServiceInfoImpl(type, name, subtype, 0, 0, 0, persistent, (byte[]) null);
        DNSEntry pointerEntry = this.getCache().getDNSEntry(new DNSRecord.Pointer(type, DNSRecordClass.CLASS_ANY, false, 0, info.getQualifiedName()));
        if (pointerEntry instanceof DNSRecord) {
            ServiceInfoImpl cachedInfo = (ServiceInfoImpl) ((DNSRecord) pointerEntry).getServiceInfo(persistent);
            if (cachedInfo != null) {
                // To get a complete info record we need to retrieve the service, address and the text bytes.

                Map<Fields, String> map = cachedInfo.getQualifiedNameMap();
                byte[] srvBytes = null;
                String server = "";
                DNSEntry serviceEntry = this.getCache().getDNSEntry(info.getQualifiedName(), DNSRecordType.TYPE_SRV, DNSRecordClass.CLASS_ANY);
                if (serviceEntry instanceof DNSRecord) {
                    ServiceInfo cachedServiceEntryInfo = ((DNSRecord) serviceEntry).getServiceInfo(persistent);
                    if (cachedServiceEntryInfo != null) {
                        cachedInfo = new ServiceInfoImpl(map, cachedServiceEntryInfo.getPort(), cachedServiceEntryInfo.getWeight(), cachedServiceEntryInfo.getPriority(), persistent, (byte[]) null);
                        srvBytes = cachedServiceEntryInfo.getTextBytes();
                        server = cachedServiceEntryInfo.getServer();
                    }
                }
                for (DNSEntry addressEntry : this.getCache().getDNSEntryList(server, DNSRecordType.TYPE_A, DNSRecordClass.CLASS_ANY)) {
                    if (addressEntry instanceof DNSRecord) {
                        ServiceInfo cachedAddressInfo = ((DNSRecord) addressEntry).getServiceInfo(persistent);
                        if (cachedAddressInfo != null) {
                            for (Inet4Address address : cachedAddressInfo.getInet4Addresses()) {
                                cachedInfo.addAddress(address);
                            }
                            cachedInfo._setText(cachedAddressInfo.getTextBytes());
                        }
                    }
                }
                for (DNSEntry addressEntry : this.getCache().getDNSEntryList(server, DNSRecordType.TYPE_AAAA, DNSRecordClass.CLASS_ANY)) {
                    if (addressEntry instanceof DNSRecord) {
                        ServiceInfo cachedAddressInfo = ((DNSRecord) addressEntry).getServiceInfo(persistent);
                        if (cachedAddressInfo != null) {
                            for (Inet6Address address : cachedAddressInfo.getInet6Addresses()) {
                                cachedInfo.addAddress(address);
                            }
                            cachedInfo._setText(cachedAddressInfo.getTextBytes());
                        }
                    }
                }
                DNSEntry textEntry = this.getCache().getDNSEntry(cachedInfo.getQualifiedName(), DNSRecordType.TYPE_TXT, DNSRecordClass.CLASS_ANY);
                if (textEntry instanceof DNSRecord) {
                    ServiceInfo cachedTextInfo = ((DNSRecord) textEntry).getServiceInfo(persistent);
                    if (cachedTextInfo != null) {
                        cachedInfo._setText(cachedTextInfo.getTextBytes());
                    }
                }
                if (cachedInfo.getTextBytes().length == 0) {
                    cachedInfo._setText(srvBytes);
                }
                if (cachedInfo.hasData()) {
                    info = cachedInfo;
                }
            }
        }
        return info;
    }

    private void waitForInfoData(ServiceInfo info, long timeout) {
        synchronized (info) {
            long loops = (timeout / 200L);
            if (loops < 1) {
                loops = 1;
            }
            for (int i = 0; i < loops; i++) {
                if (info.hasData() || isTerminalRequested()) {
                    break;
                }
                try {
                    info.wait(200);
                } catch (final InterruptedException e) {
                    /* Stub */
                }
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void requestServiceInfo(String type, String name) {
        this.requestServiceInfo(type, name, false, DNSConstants.SERVICE_INFO_TIMEOUT);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void requestServiceInfo(String type, String name, boolean persistent) {
        this.requestServiceInfo(type, name, persistent, DNSConstants.SERVICE_INFO_TIMEOUT);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void requestServiceInfo(String type, String name, long timeout) {
        this.requestServiceInfo(type, name, false, timeout);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void requestServiceInfo(String type, String name, boolean persistent, long timeout) {
        final ServiceInfoImpl info = this.resolveServiceInfo(type, name, "", persistent);
        this.waitForInfoData(info, timeout);
    }

    void handleServiceResolved(ServiceEvent event) {
        List<ServiceListenerStatus> list = _serviceListeners.get(event.getType().toLowerCase());
        final List<ServiceListenerStatus> listCopy;
        if ((list != null) && (!list.isEmpty())) {
            if ((event.getInfo() != null) && event.getInfo().hasData()) {
                final ServiceEvent localEvent = event;
                synchronized (list) {
                    listCopy = new ArrayList<>(list);
                }
                try {
                    for (final ServiceListenerStatus listener : listCopy) {
                        submitCallback(new Runnable() {
                            /**
                             * {@inheritDoc}
                             */
                            @Override
                            public void run() {
                                listener.serviceResolved(localEvent);
                            }
                        });
                    }
                } catch (RejectedExecutionException exc) {
                    logger.warn("Failed to submit runnable for serviceEvent in handleServiceResolved", exc);
                }
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void addServiceTypeListener(ServiceTypeListener listener) {
        final ServiceTypeListenerStatus status = new ServiceTypeListenerStatus(listener, ListenerStatus.ASYNCHRONOUS);
        if (!addTypeListenerStatus(status)) {
            return;
        }
        for (final String type : _serviceTypes.keySet()) {
            dispatchCallback(new Runnable() {
                @Override
                public void run() {
                    status.serviceTypeAdded(new ServiceEventImpl(JmDNSImpl.this, type, "", null));
                }
            });
        }
        this.startTypeResolver();
    }

    private boolean addTypeListenerStatus(ServiceTypeListenerStatus status) {
        for (;;) {
            ServiceTypeListenerStatus[] snapshot = _typeListeners.toArray(new ServiceTypeListenerStatus[0]);
            boolean duplicate = false;
            for (ServiceTypeListenerStatus old : snapshot) {
                // Listener equals/hashCode may be application code. Do not own
                // a producer slice across it; validate the identity snapshot later.
                if (status.equals(old)) {
                    duplicate = true;
                    break;
                }
            }
            if (!beginProducerMutation()) {
                return false;
            }
            try {
                synchronized (_typeListeners) {
                    boolean unchanged = _typeListeners.size() == snapshot.length;
                    for (ServiceTypeListenerStatus old : snapshot) {
                        unchanged &= _typeListeners.contains(old); // identity-backed set
                    }
                    if (!unchanged) {
                        continue;
                    }
                    if (!duplicate) {
                        _typeListeners.add(status);
                    }
                    return true;
                }
            } finally {
                endProducerMutation();
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void removeServiceTypeListener(ServiceTypeListener listener) {
        ServiceTypeListenerStatus status = new ServiceTypeListenerStatus(listener, ListenerStatus.ASYNCHRONOUS);
        for (ServiceTypeListenerStatus old : _typeListeners.toArray(new ServiceTypeListenerStatus[0])) {
            if (status.equals(old)) {
                _typeListeners.remove(old); // identity-backed, no user code under lock
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void addServiceListener(String type, ServiceListener listener) {
        this.addServiceListener(type, listener, ListenerStatus.ASYNCHRONOUS, true);
    }

    private void addServiceListener(String type, ServiceListener listener, boolean synch, boolean shouldStartServiceResolver) {
        final ServiceListenerStatus status = new ServiceListenerStatus(listener, synch);
        final String loType = type.toLowerCase();
        List<ServiceListenerStatus> list = _serviceListeners.get(loType);
        ServiceCollector newCollector = null;
        if (list == null) {
            if (!beginProducerMutation()) {
                return;
            }
            try {
                if (_serviceListeners.putIfAbsent(loType, new LinkedList<ServiceListenerStatus>()) == null) {
                    ServiceCollector candidate = new ServiceCollector(type);
                    if (_serviceCollectors.putIfAbsent(loType, candidate) == null) {
                        newCollector = candidate;
                    }
                }
                list = _serviceListeners.get(loType);
            } finally {
                endProducerMutation();
            }
        }
        if (newCollector != null) {
            // Collector recursion and its cached replay are outside the slice.
            this.addServiceListener(loType, newCollector, ListenerStatus.SYNCHRONOUS, false);
        }
        if (list == null || !addServiceListenerStatus(list, status)) {
            return;
        }
        final List<ServiceEvent> serviceEvents = new ArrayList<>();
        for (DNSEntry entry : this.getCache().allValues()) {
            final DNSRecord record = (DNSRecord) entry;
            if (record.getRecordType() == DNSRecordType.TYPE_SRV && record.getKey().endsWith(loType)) {
                serviceEvents.add(new ServiceEventImpl(this, record.getType(),
                        toUnqualifiedName(record.getType(), record.getName()), record.getServiceInfo()));
            }
        }
        for (final ServiceEvent serviceEvent : serviceEvents) {
            dispatchCallback(new Runnable() {
                @Override
                public void run() {
                    status.serviceAdded(serviceEvent);
                }
            });
        }
        if (shouldStartServiceResolver) {
            this.startServiceResolver(type);
        }
    }

    private boolean addServiceListenerStatus(List<ServiceListenerStatus> list, ServiceListenerStatus status) {
        for (;;) {
            List<ServiceListenerStatus> snapshot;
            synchronized (list) {
                snapshot = new ArrayList<>(list);
            }
            boolean duplicate = snapshot.contains(status); // may invoke application equals
            if (!beginProducerMutation()) {
                return false;
            }
            try {
                synchronized (list) {
                    boolean unchanged = list.size() == snapshot.size();
                    for (int index = 0; unchanged && index < snapshot.size(); index++) {
                        unchanged = list.get(index) == snapshot.get(index);
                    }
                    if (!unchanged) {
                        continue;
                    }
                    if (!duplicate) {
                        list.add(status);
                    }
                    return true;
                }
            } finally {
                endProducerMutation();
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void removeServiceListener(String type, ServiceListener listener) {
        String loType = type.toLowerCase();
        List<ServiceListenerStatus> list = _serviceListeners.get(loType);
        if (list == null) {
            return;
        }
        List<ServiceListenerStatus> snapshot;
        synchronized (list) {
            snapshot = new ArrayList<>(list);
        }
        ServiceListenerStatus requested = new ServiceListenerStatus(listener, ListenerStatus.ASYNCHRONOUS);
        for (ServiceListenerStatus status : snapshot) {
            if (requested.equals(status)) {
                synchronized (list) {
                    for (int index = 0; index < list.size(); index++) {
                        if (list.get(index) == status) {
                            list.remove(index);
                            break;
                        }
                    }
                    if (list.isEmpty()) {
                        _serviceListeners.remove(loType, list);
                    }
                }
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void registerService(ServiceInfo infoAbstract) throws IOException {
        if (isTerminalRequested() || this.isClosing() || this.isClosed()) {
            throw new IllegalStateException("This DNS is closed.");
        }
        final ServiceInfoImpl info = (ServiceInfoImpl) infoAbstract;
        if (info.getDns() != null) {
            if (info.getDns() != this) {
                throw new IllegalStateException("A service information can only be registered with a single instance of JmDNS.");
            } else if (_services.get(info.getKey()) != null) {
                throw new IllegalStateException("A service information can only be registered once.");
            }
        }
        info.setDns(this);
        this.registerServiceType(info.getTypeWithSubtype());
        info.recoverState();
        info.setServer(_localHost.getName());
        info.addAddress(_localHost.getInet4Address());
        info.addAddress(_localHost.getInet6Address());
        for (;;) {
            // Includes the replaceable NameRegister: never keep admission across it.
            this.makeServiceNameUnique(info);
            String key = info.getKey();
            if (!beginProducerMutation()) {
                throw new IllegalStateException("This DNS is closing.");
            }
            try {
                if (_services.putIfAbsent(key, info) == null) {
                    break;
                }
            } finally {
                endProducerMutation();
            }
        }
        this.startProber();
        logger.debug("registerService() JmDNS registered service as {}", info);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void unregisterService(ServiceInfo infoAbstract) {
        final ServiceInfoImpl info = (ServiceInfoImpl) _services.get(infoAbstract.getKey());

        if (info != null) {
            info.cancelState();
            this.startCanceler();
            info.waitForCanceled(DNSConstants.CLOSE_TIMEOUT);

            _services.remove(info.getKey(), info);
            logger.debug("unregisterService() JmDNS {} unregistered service as {}", this.getName(), info);
        } else {
            logger.warn("{} removing unregistered service info: {}", this.getName(), infoAbstract.getKey());
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void unregisterAllServices() {
        logger.debug("unregisterAllServices()");

        for (final ServiceInfo info : _services.values()) {
            if (info != null) {
                final ServiceInfoImpl infoImpl = (ServiceInfoImpl) info;
                logger.debug("Cancelling service info: {}", info);
                infoImpl.cancelState();
            }
        }
        this.startCanceler();

        for (final Map.Entry<String, ServiceInfo> entry : _services.entrySet()) {
            final ServiceInfo info = entry.getValue();
            if (info != null) {
                final ServiceInfoImpl infoImpl = (ServiceInfoImpl) info;
                final String name = entry.getKey();

                logger.debug("Wait for service info cancel: {}", info);
                infoImpl.waitForCanceled(DNSConstants.CLOSE_TIMEOUT);
                _services.remove(name, info);
            }
        }

    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean registerServiceType(String type) {
        Map<Fields, String> map = ServiceTypeDecoder.decodeQualifiedNameMapForType(type);
        String domain = map.get(Fields.Domain);
        String protocol = map.get(Fields.Protocol);
        String application = map.get(Fields.Application);
        final String subtype = map.get(Fields.Subtype);
        final String name = (!application.isEmpty() ? "_" + application + "." : "")
                + (!protocol.isEmpty() ? "_" + protocol + "." : "") + domain + ".";
        String loname = name.toLowerCase();
        boolean typeAdded = false;
        boolean subtypeAdded = false;
        if (!beginProducerMutation()) {
            return false;
        }
        try {
            if (!application.equalsIgnoreCase("dns-sd") && !domain.toLowerCase().endsWith("in-addr.arpa")
                    && !domain.toLowerCase().endsWith("ip6.arpa")) {
                typeAdded = _serviceTypes.putIfAbsent(loname, new ServiceTypeEntry(name)) == null;
            }
            if (!subtype.isEmpty()) {
                ServiceTypeEntry subtypes = _serviceTypes.get(loname);
                if (subtypes != null) {
                    synchronized (subtypes) {
                        subtypeAdded = subtypes.add(subtype);
                    }
                }
            }
        } finally {
            endProducerMutation();
        }
        if (typeAdded) {
            final ServiceEvent event = new ServiceEventImpl(this, name, "", null);
            for (final ServiceTypeListenerStatus status : _typeListeners.toArray(new ServiceTypeListenerStatus[0])) {
                try {
                    submitCallback(new Runnable() {
                        @Override
                        public void run() {
                            status.serviceTypeAdded(event);
                        }
                    });
                } catch (RejectedExecutionException failure) {
                    logger.warn("Failed to submit service type callback", failure);
                }
            }
        }
        if (subtypeAdded) {
            final ServiceEvent event = new ServiceEventImpl(this, "_" + subtype + "._sub." + name, "", null);
            for (final ServiceTypeListenerStatus status : _typeListeners.toArray(new ServiceTypeListenerStatus[0])) {
                try {
                    submitCallback(new Runnable() {
                        @Override
                        public void run() {
                            status.subTypeForServiceTypeAdded(event);
                        }
                    });
                } catch (RejectedExecutionException failure) {
                    logger.warn("Failed to submit service subtype callback", failure);
                }
            }
        }
        return typeAdded || subtypeAdded;
    }

    /**
     * Generate a possibly unique name for a service using the information we have in the cache.
     *
     * @return returns true, if the name of the service info had to be changed.
     */
    private boolean makeServiceNameUnique(ServiceInfoImpl info) {
        final String originalQualifiedName = info.getKey();
        final long now = System.currentTimeMillis();

        boolean collision;
        do {
            collision = false;

            // Check for collision in cache
            for (DNSEntry dnsEntry : this.getCache().getDNSEntryList(info.getKey())) {
                if (DNSRecordType.TYPE_SRV.equals(dnsEntry.getRecordType()) && !dnsEntry.isExpired(now)) {
                    final DNSRecord.Service s = (DNSRecord.Service) dnsEntry;
                    if (s.getPort() != info.getPort() || !s.getServer().equals(_localHost.getName())) {
                        logger.debug("makeServiceNameUnique() JmDNS.makeServiceNameUnique srv collision:{} s.server={} {} equals:{}",
                                dnsEntry,
                                s.getServer(),
                                _localHost.getName(),
                                s.getServer().equals(_localHost.getName())
                        );
                        info.setName(NameRegister.Factory.getRegistry().incrementName(_localHost.getInetAddress(), info.getName(), NameRegister.NameType.SERVICE));
                        collision = true;
                        break;
                    }
                }
            }

            // Check for collision with other service infos published by JmDNS
            final ServiceInfo selfService = _services.get(info.getKey());
            if (selfService != null && selfService != info) {
                info.setName(NameRegister.Factory.getRegistry().incrementName(_localHost.getInetAddress(), info.getName(), NameRegister.NameType.SERVICE));
                collision = true;
            }
        }
        while (collision);

        return !(originalQualifiedName.equals(info.getKey()));
    }

    /**
     * Add a listener for a question. The listener will receive updates of answers to the question as they arrive, or from the cache if they are already available.
     *
     * @param listener
     *            DSN listener
     * @param question
     *            DNS query
     */
    public void addListener(final DNSListener listener, DNSQuestion question) {
        final long now = System.currentTimeMillis();
        if (!beginProducerMutation()) {
            return;
        }
        try {
            _listeners.add(listener);
        } finally {
            endProducerMutation();
        }
        if (question != null) {
            for (final DNSEntry dnsEntry : this.getCache().getDNSEntryList(question.getName().toLowerCase())) {
                if (question.answeredBy(dnsEntry) && !dnsEntry.isExpired(now)) {
                    dispatchCallback(new Runnable() {
                        @Override
                        public void run() {
                            listener.updateRecord(_cache, now, dnsEntry);
                        }
                    });
                }
            }
        }
    }

    /**
     * Remove a listener from all outstanding questions. The listener will no longer receive any updates.
     *
     * @param listener
     *            DSN listener
     */
    public void removeListener(DNSListener listener) {
        List<DNSListener> snapshot;
        synchronized (_listeners) {
            snapshot = new ArrayList<>(_listeners);
        }
        for (DNSListener old : snapshot) {
            if (listener == old || (listener != null && listener.equals(old))) {
                synchronized (_listeners) {
                    for (int index = 0; index < _listeners.size(); index++) {
                        if (_listeners.get(index) == old) {
                            _listeners.remove(index);
                            return;
                        }
                    }
                }
            }
        }
    }

    /**
     * Renew a service when the record become stale. If there is no service collector for the type this method does nothing.
     *
     * @param type
     *            Service Type
     */
    public void renewServiceCollector(String type) {
        if (_serviceCollectors.containsKey(type.toLowerCase())) {
            // Create/start ServiceResolver
            this.startServiceResolver(type);
        }
    }

    final boolean renameHostAfterConflict() {
        String oldName = _localHost.getName();
        // The replaceable registry is outside both admission and the host monitor.
        String replacement = NameRegister.Factory.getRegistry().incrementName(
                _localHost.getInetAddress(), oldName, NameRegister.NameType.HOST);
        if (!beginProducerMutation()) {
            return false;
        }
        try {
            if (!_localHost.renameForLifetime(oldName, replacement)) {
                return false;
            }
            _cache.clear();
            for (ServiceInfo service : _services.values()) {
                ((ServiceInfoImpl) service).revertStateForLifetime();
            }
            return true;
        } finally {
            endProducerMutation();
        }
    }

    final boolean publishServiceRename(ServiceInfoImpl info, String oldKey, String replacement, String newKey) {
        if (!beginProducerMutation()) {
            return false;
        }
        try {
            if (_services.get(oldKey) != info) {
                return false;
            }
            info.renameForLifetime(replacement);
            _services.remove(oldKey, info);
            _services.put(newKey, info);
            return true;
        } finally {
            endProducerMutation();
        }
    }

    final void revertServiceAfterConflict(ServiceInfoImpl info) {
        if (!beginProducerMutation()) {
            return;
        }
        try {
            info.revertStateForLifetime();
        } finally {
            endProducerMutation();
        }
    }

    // Remind: Method updateRecord should receive a better name.
    /**
     * Notify all listeners that a record was updated.
     *
     * @param now
     *            update date
     * @param rec
     *            DNS record
     * @param operation
     *            DNS cache operation
     */
    public void updateRecord(long now, DNSRecord rec, Operation operation) {
        ServiceEvent event = rec.getServiceEvent(this);
        if (operation == Operation.Remove && DNSRecordType.TYPE_SRV.equals(rec.getRecordType())) {
            removeObsoleteDnsListener(event);
        }

        // We do not want to block the entire DNS while we are updating the record for each listener (service info)
        {
            List<DNSListener> listenerList;
            synchronized (_listeners) {
                listenerList = new ArrayList<>(_listeners);
            }
            for (final DNSListener listener : listenerList) {
                final long callbackTime = now;
                final DNSRecord callbackRecord = rec;
                dispatchCallback(new Runnable() {
                    @Override
                    public void run() {
                        listener.updateRecord(_cache, callbackTime, callbackRecord);
                    }
                });
            }
        }

        if (
                DNSRecordType.TYPE_PTR.equals(rec.getRecordType())
                || ( DNSRecordType.TYPE_SRV.equals(rec.getRecordType()) && Operation.Remove.equals(operation))
        )
        {
            if ((event.getInfo() == null) || !event.getInfo().hasData()) {
                // We do not care about the subtype because the info is only used if complete and the subtype will then be included.
                ServiceInfo info = this.getServiceInfoFromCache(event.getType(), event.getName(), "", false);
                if (info.hasData()) {
                    event = new ServiceEventImpl(this, event.getType(), event.getName(), info);
                }
            }

            List<ServiceListenerStatus> list = _serviceListeners.get(event.getType().toLowerCase());
            final List<ServiceListenerStatus> serviceListenerList;
            if (list != null) {
                synchronized (list) {
                    serviceListenerList = new ArrayList<ServiceListenerStatus>(list);
                }
            } else {
                serviceListenerList = Collections.emptyList();
            }
            logger.trace("{}.updating record for event: {} list {} operation: {}",
                this.getName(),
                event,
                serviceListenerList,
                operation
            );
            if (!serviceListenerList.isEmpty()) {
                final ServiceEvent localEvent = event;

                switch (operation) {
                    case Add:
                        for (final ServiceListenerStatus listener : serviceListenerList) {
                            if (listener.isSynchronous()) {
                                dispatchCallback(new Runnable() {
                                    @Override
                                    public void run() {
                                        listener.serviceAdded(localEvent);
                                    }
                                });
                            } else {
                                try {
                                    submitCallback(new Runnable() {
                                        /**
                                         * {@inheritDoc}
                                         */
                                        @Override
                                        public void run() {
                                            listener.serviceAdded(localEvent);
                                        }
                                    });
                                } catch (RejectedExecutionException exc) {
                                    logger.warn("Failed to submit runnable for serviceEvent in updateRecord (Add)", exc);
                                }
                            }
                        }
                        break;
                    case Remove:
                        for (final ServiceListenerStatus listener : serviceListenerList) {
                            if (listener.isSynchronous()) {
                                dispatchCallback(new Runnable() {
                                    @Override
                                    public void run() {
                                        listener.serviceRemoved(localEvent);
                                    }
                                });
                            } else {
                                try {
                                    submitCallback(new Runnable() {
                                        /**
                                         * {@inheritDoc}
                                         */
                                        @Override
                                        public void run() {
                                            listener.serviceRemoved(localEvent);
                                        }
                                    });
                                } catch (RejectedExecutionException exc) {
                                    logger.warn("Failed to submit runnable for serviceEvent in updateRecord (Remove)", exc);
                                }
                            }
                        }
                        break;
                    default:
                        break;
                }
            }
        }
    }

    private void removeObsoleteDnsListener(ServiceEvent event) {
        ServiceInfo serviceInfo = event.getInfo();
        if (!(serviceInfo instanceof DNSListener)) {
            return;
        }
        DNSListener listener = (DNSListener) serviceInfo;

        removeListener(listener);
    }

    void handleRecord(DNSRecord record, long now) {
        DNSRecord newRecord = record;

        Operation cacheOperation = Operation.Noop;
        final boolean expired = newRecord.isExpired(now);
        logger.debug("{} handle response: {}", this.getName(), newRecord);

        if (!beginProducerMutation()) {
            return;
        }
        try {
            // update the cache
            if (!newRecord.isServicesDiscoveryMetaQuery() && !newRecord.isDomainDiscoveryQuery()) {
                final boolean unique = newRecord.isUnique();
                final DNSRecord cachedRecord = (DNSRecord) _cache.getDNSEntry(newRecord);
                // RFC 6762, section 10.2 Announcements to Flush Outdated Cache Entries
                // https://tools.ietf.org/html/rfc6762#section-10.2
                // if (cache-flush a.k.a unique), remove all existing records matching these criterias :--
                //     1. same name
                //     2. same record type
                //     3. same record class
                //     4. record is older than 1 second.
                if (unique) {
                    for (DNSEntry entry : _cache.getDNSEntryList(newRecord.getKey())) {
                        if (    newRecord.getRecordType().equals(entry.getRecordType()) &&
                                newRecord.getRecordClass().equals(entry.getRecordClass()) &&
                                isOlderThanOneSecond( (DNSRecord)entry, now )
                        ) {
                            // this set ttl to 1 second,
                            ((DNSRecord) entry).setWillExpireSoon(now);
                        }
                    }
                }
                if (cachedRecord != null) {
                    if (expired) {
                        // if the record has a 0 ttl that means we have a cancel record we need to delay the removal by 1s
                        if (newRecord.getTTL() == 0) {
                            cacheOperation = Operation.Noop;
                            cachedRecord.setWillExpireSoon(now);
                            // the actual record will be disposed of by the record reaper.
                        } else {
                            cacheOperation = Operation.Remove;
                            _cache.removeDNSEntry(cachedRecord);
                        }
                    } else {
                        // If the record content has changed we need to inform our listeners.
                        if (    !newRecord.sameValue(cachedRecord) ||
                                (
                                        !newRecord.sameSubtype(cachedRecord) &&
                                        (!newRecord.getSubtype().isEmpty())
                                )
                        ) {
                            if (newRecord.isSingleValued()) {
                                cacheOperation = Operation.Update;
                                _cache.replaceDNSEntry(newRecord, cachedRecord);
                            } else {
                                // Address record can have more than one value on multi-homed machines
                                cacheOperation = Operation.Add;
                                _cache.addDNSEntry(newRecord);
                            }
                        } else {
                            cachedRecord.resetTTL(newRecord);
                            newRecord = cachedRecord;
                        }
                    }
                } else {
                    if (!expired) {
                        cacheOperation = Operation.Add;
                        _cache.addDNSEntry(newRecord);
                    }
                }
            }
        } finally {
            endProducerMutation();
        }

        logger.trace("{} cache operation {} for record {}", _name, cacheOperation, newRecord);

        // Register new service types
        if (newRecord.getRecordType() == DNSRecordType.TYPE_PTR) {
            // handle DNSConstants.DNS_META_QUERY records
            boolean typeAdded = false;
            if (newRecord.isServicesDiscoveryMetaQuery()) {
                // The service names are in the alias.
                if (!expired) {
                    typeAdded = this.registerServiceType(((DNSRecord.Pointer) newRecord).getAlias());
                }
                return;
            }
            typeAdded |= this.registerServiceType(newRecord.getName());
            if (typeAdded && (cacheOperation == Operation.Noop)) {
                cacheOperation = Operation.RegisterServiceType;
            }
        }

        // notify the listeners
        if (cacheOperation != Operation.Noop) {
            this.updateRecord(now, newRecord, cacheOperation);
        }

    }

    /**
     *
     * @param dnsRecord
     * @param timeToCompare a given times for comparison
     * @return true if dnsRecord create time is older than 1 second, relative to the given time; false otherwise
     */
    private boolean isOlderThanOneSecond(DNSRecord dnsRecord, long timeToCompare) {
        return (dnsRecord.getCreated() < (timeToCompare - DNSConstants.FLUSH_RECORD_OLDER_THAN_1_SECOND*1000));
    }

    /**
     * Handle an incoming response. Cache answers, and pass them on to the appropriate questions.
     *
     * @exception IOException
     */
    void handleResponse(DNSIncoming msg) throws IOException {
        final long now = System.currentTimeMillis();

        boolean hostConflictDetected = false;
        boolean serviceConflictDetected = false;

        List<DNSRecord> allAnswers = msg.getAllAnswers();
        allAnswers = aRecordsLast(allAnswers);
        for (DNSRecord newRecord : allAnswers) {
            this.handleRecord(newRecord, now);

            if (DNSRecordType.TYPE_A.equals(newRecord.getRecordType()) || DNSRecordType.TYPE_AAAA.equals(newRecord.getRecordType())) {
                hostConflictDetected |= newRecord.handleResponse(this);
            } else {
                serviceConflictDetected |= newRecord.handleResponse(this);
            }

        }

        if (hostConflictDetected || serviceConflictDetected) {
            this.startProber();
        }
    }

    /**
     * In case the a record is received before the srv record the ip address would not be set.
     * <p>
     * Wireshark record: see also file a_record_before_srv.pcapng and {@link ServiceInfoImplTest#test_ip_address_is_set()}
     * <p>
     * Multicast Domain Name System (response)
     * Transaction ID: 0x0000
     * Flags: 0x8400 Standard query response, No error
     * Questions: 0
     * Answer RRs: 2
     * Authority RRs: 0
     * Additional RRs: 8
     * Answers
     * _ibisip_http._tcp.local: type PTR, class IN, DeviceManagementService._ibisip_http._tcp.local
     * _ibisip_http._tcp.local: type PTR, class IN, PassengerCountingService._ibisip_http._tcp.local
     * Additional records
     * DeviceManagementService._ibisip_http._tcp.local: type TXT, class IN, cache flush
     * PassengerCountingService._ibisip_http._tcp.local: type TXT, class IN, cache flush
     * DIST500_7-F07_OC030_05_03941.local: type A, class IN, cache flush, addr 192.168.88.236
     * DeviceManagementService._ibisip_http._tcp.local: type SRV, class IN, cache flush, priority 0, weight 0, port 5000, target DIST500_7-F07_OC030_05_03941.local
     * PassengerCountingService._ibisip_http._tcp.local: type SRV, class IN, cache flush, priority 0, weight 0, port 5001, target DIST500_7-F07_OC030_05_03941.local
     * DeviceManagementService._ibisip_http._tcp.local: type NSEC, class IN, cache flush, next domain name DeviceManagementService._ibisip_http._tcp.local
     * PassengerCountingService._ibisip_http._tcp.local: type NSEC, class IN, cache flush, next domain name PassengerCountingService._ibisip_http._tcp.local
     * DIST500_7-F07_OC030_05_03941.local: type NSEC, class IN, cache flush, next domain name DIST500_7-F07_OC030_05_03941.local
     */
    private List<DNSRecord> aRecordsLast(List<DNSRecord> allAnswers) {
        ArrayList<DNSRecord> ret = new ArrayList<>(allAnswers.size());
        ArrayList<DNSRecord> arecords = new ArrayList<>();
        // filter all a records and move them to the end of the list
        // we do not change der order of the order records
        for (DNSRecord answer : allAnswers) {
            if (answer.getRecordType().equals(DNSRecordType.TYPE_A) || answer.getRecordType().equals(DNSRecordType.TYPE_AAAA)) {
                arecords.add(answer);
            } else {
                ret.add(answer);
            }
        }
        ret.addAll(arecords);
        return ret;
    }


    /**
     * Handle an incoming query. See if we can answer any part of it given our service infos.
     *
     * @param in
     * @param addr
     * @param port
     * @exception IOException
     */
    void handleQuery(DNSIncoming in, InetAddress addr, int port) throws IOException {
        logger.debug("{} handle query: {}", this.getName(), in);
        // Track known answers
        boolean conflictDetected = false;
        final long expirationTime = System.currentTimeMillis() + DNSConstants.KNOWN_ANSWER_TTL;
        for (DNSRecord answer : in.getAllAnswers()) {
            conflictDetected |= answer.handleQuery(this, expirationTime);
        }

        this.ioLock();
        try {

            DNSIncoming response = null;
            if (!beginProducerMutation()) {
                return;
            }
            try {
                if (_plannedAnswer != null) {
                    _plannedAnswer.append(in);
                } else {
                    response = in.clone();
                    if (in.isTruncated()) {
                        _plannedAnswer = response;
                    }
                }
            } finally {
                endProducerMutation();
            }
            if (response != null) {
                this.startResponder(response, addr, port);
            }

        } finally {
            this.ioUnlock();
        }

        final long now = System.currentTimeMillis();
        for (DNSRecord answer : in.getAnswers()) {
            this.handleRecord(answer, now);
        }

        if (conflictDetected) {
            this.startProber();
        }
    }

    public void respondToQuery(DNSIncoming in) {
        this.ioLock();
        try {
            if (_plannedAnswer == in) {
                _plannedAnswer = null;
            }
        } finally {
            this.ioUnlock();
        }
    }

    /**
     * Add an answer to a question. Deal with the case when the outgoing packet overflows
     *
     * @param in
     * @param addr
     * @param port
     * @param out
     * @param rec
     * @return outgoing answer
     * @exception IOException
     */
    public DNSOutgoing addAnswer(DNSIncoming in, InetAddress addr, int port, DNSOutgoing out, DNSRecord rec) throws IOException {
        DNSOutgoing newOut = out;
        if (newOut == null) {
            newOut = new DNSOutgoing(DNSConstants.FLAGS_QR_RESPONSE | DNSConstants.FLAGS_AA, false, in.getSenderUDPPayload());
        }
        try {
            newOut.addAnswer(in, rec);
        } catch (final IOException e) {
            newOut.setFlags(newOut.getFlags() | DNSConstants.FLAGS_TC);
            newOut.setId(in.getId());
            send(newOut);

            newOut = new DNSOutgoing(DNSConstants.FLAGS_QR_RESPONSE | DNSConstants.FLAGS_AA, false, in.getSenderUDPPayload());
            newOut.addAnswer(in, rec);
        }
        return newOut;
    }

    /**
     * Send an outgoing multicast DNS message.
     *
     * @param out
     * @exception IOException
     */
    public void send(DNSOutgoing out) throws IOException {
        if (!out.isEmpty()) {
            final InetAddress addr;
            final int port;

            if (out.getDestination() != null) {
                addr = out.getDestination().getAddress();
                port = out.getDestination().getPort();
            } else {
                addr = _group;
                port = DNSConstants.MDNS_PORT;
            }

            byte[] message = out.data();
            final DatagramPacket packet = new DatagramPacket(message, message.length, addr, port);

            if (logger.isTraceEnabled()) {
                try {
                    final DNSIncoming msg = new DNSIncoming(packet);
//                    if (logger.isTraceEnabled()) {
                        logger.trace("send({}) JmDNS out:{}", this.getName(), msg.print(true));
//                    }
                } catch (final IOException e) {
                    logger.debug("{}.send({}) - JmDNS can not parse what it sends!!!", getClass(), this.getName(), e);
                }
            }
            final MulticastSocket ms = _socket;
            if (ms != null && !ms.isClosed()) {
                ms.send(packet);
            }
        }
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#purgeTimer()
     */
    @Override
    public void purgeTimer() {
        _taskStarter.purgeTimer();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#purgeStateTimer()
     */
    @Override
    public void purgeStateTimer() {
        _taskStarter.purgeStateTimer();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#cancelTimer()
     */
    @Override
    public void cancelTimer() {
        if (_taskStarter != null) {
            _taskStarter.cancelTimer();
        }
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#cancelStateTimer()
     */
    @Override
    public void cancelStateTimer() {
        if (_taskStarter != null) {
            _taskStarter.cancelStateTimer();
        }
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startProber()
     */
    @Override
    public void startProber() {
        _taskStarter.startProber();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startAnnouncer()
     */
    @Override
    public void startAnnouncer() {
        _taskStarter.startAnnouncer();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startRenewer()
     */
    @Override
    public void startRenewer() {
        _taskStarter.startRenewer();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startCanceler()
     */
    @Override
    public void startCanceler() {
        if (_taskStarter != null) {
            _taskStarter.startCanceler();
        }
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startReaper()
     */
    @Override
    public void startReaper() {
        _taskStarter.startReaper();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startServiceInfoResolver(dev.p2pkit.transport.lan.internal.jmdns.impl.ServiceInfoImpl)
     */
    @Override
    public void startServiceInfoResolver(ServiceInfoImpl info) {
        _taskStarter.startServiceInfoResolver(info);
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startTypeResolver()
     */
    @Override
    public void startTypeResolver() {
        _taskStarter.startTypeResolver();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startServiceResolver(java.lang.String)
     */
    @Override
    public void startServiceResolver(String type) {
        _taskStarter.startServiceResolver(type);
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.DNSTaskStarter#startResponder(dev.p2pkit.transport.lan.internal.jmdns.impl.DNSIncoming, int)
     */
    @Override
    public void startResponder(DNSIncoming in, InetAddress addr, int port) {
        _taskStarter.startResponder(in, addr, port);
    }

    /** Recover in one tracked mutation phase, then invoke any delegate outside it. */
    public void recover() {
        if (this.isClosing() || this.isClosed() || this.isCanceling() || this.isCanceled()) {
            return;
        }
        final JmDNSLifecycle.Recovery recovery = new JmDNSLifecycle.Recovery();
        Thread worker = new Thread(new Runnable() {
            @Override
            public void run() {
                _lifecycle.enterDependent();
                try {
                    __recover(recovery);
                } finally {
                    synchronized (_lifecycle) {
                        recovery.mutating = false;
                        if (_lifecycle.recovery == recovery) {
                            _lifecycle.recovery = null;
                        }
                        _lifecycle.notifyAll();
                    }
                    _lifecycle.exitDependent();
                }
            }
        }, _name + ".recover()");
        recovery.thread = worker;
        synchronized (_lifecycle) {
            if (_lifecycle.terminalRequested || _lifecycle.recovery != null) {
                return;
            }
            // Retire prior worker identities only after actual termination was
            // observed; do not grow a history of dead threads across recoveries.
            Iterator<JmDNSLifecycle.Recovery> previous = _lifecycle.recoveries.iterator();
            while (previous.hasNext()) {
                JmDNSLifecycle.Recovery old = previous.next();
                if (old.launchResolved && (!old.started || !old.thread.isAlive())) {
                    previous.remove();
                }
            }
            _lifecycle.recovery = recovery;
            _lifecycle.recoveries.add(recovery);
        }
        boolean started = false;
        _lifecycle.enterDependent();
        try {
            // False and exceptional cancellation must also resolve admission.
            if (this.cancelState()) {
                worker.start();
                started = true;
            }
        } catch (Throwable failure) {
            logger.warn("Could not launch JmDNS recovery", failure);
        } finally {
            synchronized (_lifecycle) {
                recovery.started = started;
                recovery.launchResolved = true;
                if (!started) {
                    recovery.mutating = false;
                    if (_lifecycle.recovery == recovery) {
                        _lifecycle.recovery = null;
                    }
                }
                _lifecycle.notifyAll();
            }
            _lifecycle.exitDependent();
        }
    }

    private void __recover(JmDNSLifecycle.Recovery recovery) {
        final Collection<ServiceInfo> oldServiceInfos = new ArrayList<>(getServices().values());
        boolean notifyFailure = false;
        try {
            logger.warn("RECOVERING");
            this.purgeTimer();
            this.unregisterAllServices();
            this.disposeServiceCollectors();
            _localHost.waitForCanceledInterruptibly(DNSConstants.CLOSE_TIMEOUT);
            this.purgeStateTimer();

            List<Throwable> failures = new ArrayList<>();
            disposeSockets(failures);
            drainSocketListeners(new JmDNSLifecycle.WaitBudget());
            for (Throwable failure : failures) {
                logger.warn("Recovery socket disposal failed", failure);
            }
            this.getCache().clear();
            if (this.isCanceled()) {
                // Every restart producer re-admits; this token alone does not
                // authorize publishing a socket or scheduling work after close.
                for (ServiceInfo info : oldServiceInfos) {
                    if (isTerminalRequested()) {
                        break;
                    }
                    ((ServiceInfoImpl) info).recoverState();
                }
                this.recoverState();
                if (this.openMulticastSocket(this.getLocalHost(), recovery)) {
                    this.start(oldServiceInfos);
                }
            } else {
                notifyFailure = true;
                logger.warn("{}.recover() Could not recover we are Down!", this.getName());
            }
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            logger.warn("Recovery interrupted", failure);
            notifyFailure = true;
        } catch (Throwable failure) {
            logger.warn("Recovery failed", failure);
            notifyFailure = true;
        } finally {
            Delegate delegate = _delegate;
            boolean callbackReserved = false;
            synchronized (_lifecycle) {
                if (notifyFailure && delegate != null && !_lifecycle.terminalRequested) {
                    _lifecycle.callbacks++;
                    callbackReserved = true;
                }
                // The worker/callback remains owned until actual Thread exit.
                recovery.mutating = false;
                _lifecycle.notifyAll();
            }
            if (callbackReserved) {
                try {
                    delegate.cannotRecoverFromIOError(this, oldServiceInfos);
                } finally {
                    _lifecycle.endCallback();
                }
            }
        }
    }

    /**
     * Checks the cache of expired records and removes them.
     * If any records are about to expire it tries to get them refreshed.
     *
     * <p>
     * Implementation note:<br />
     * This method is called by the {@link RecordReaper} every {@link DNSConstants#RECORD_REAPER_INTERVAL} milliseconds.
     * </p>
     * @see DNSRecord
     * @see RecordReaper
     */
    public void cleanCache() {
        this.getCache().logCachedContent();

        final long now = System.currentTimeMillis();
        final Set<String> staleServiceTypesForRefresh = new HashSet<>();
        for (final DNSEntry entry : this.getCache().allValues()) {
            try {
                final DNSRecord record = (DNSRecord) entry;
                if (record.isExpired(now)) {
                    this.updateRecord(now, record, Operation.Remove);
                    logger.trace("Removing DNSEntry from cache: {}", entry);
                    if (beginProducerMutation()) {
                        try {
                            _cache.removeDNSEntry(record);
                        } finally {
                            endProducerMutation();
                        }
                    }
                } else if (record.isStaleAndShouldBeRefreshed(now)) {
                    if (!beginProducerMutation()) {
                        return;
                    }
                    try {
                        record.incrementRefreshPercentage();
                    } finally {
                        endProducerMutation();
                    }
                    String type = record.getServiceInfo().getType().toLowerCase();
                    // only query every service type once per refresh
                    if (staleServiceTypesForRefresh.add(type)) {
                        // we should query for the record we care about i.e. those in the service collectors
                        this.renewServiceCollector(type);
                    }
                }
            } catch (Exception exception) {
                logger.warn("{}.Error while reaping records: {}", this.getName(), entry, exception);
                logger.warn(this.toString());
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void close() {
        closeOwnedLifetime();
    }

    private void closeOwnedLifetime() {
        // A successful return means disposal, never merely a request. Native
        // callbacks/tasks cannot synchronously wait for the work they themselves own.
        if (_lifecycle.isDependent() || _ioLock.isHeldByCurrentThread()) {
            throw new IllegalStateException("Blocking close is not supported from JmDNS-managed work");
        }
        JmDNSLifecycle.WaitBudget budget = new JmDNSLifecycle.WaitBudget();
        for (;;) {
            JmDNSLifecycle.Attempt attempt;
            boolean owner = false;
            boolean retryBarrier = false;
            synchronized (_lifecycle) {
                attempt = _lifecycle.attempt;
                if (_lifecycle.startupInProgress && _lifecycle.startupOwner == Thread.currentThread()) {
                    throw new IllegalStateException("Blocking close cannot reenter JmDNS construction");
                }
                if (attempt != null && attempt.owner == Thread.currentThread() && attempt.outcome == null) {
                    throw new IllegalStateException("Blocking close cannot reenter its cleanup owner");
                }
                if (attempt == null) {
                    _lifecycle.terminalRequested = true;
                    attempt = new JmDNSLifecycle.Attempt(++_lifecycle.nextAttempt,
                            Thread.currentThread(), false, budget);
                    _lifecycle.attempt = attempt;
                    owner = true;
                } else if (attempt.outcome != null && attempt.outcome.failure != null) {
                    retryBarrier = true;
                } else {
                    attempt.joinedCallers++;
                }
            }
            if (retryBarrier) {
                // No retry may overtake a native owner's post-outcome thread tail.
                awaitPreviousHelper(attempt, budget);
                synchronized (_lifecycle) {
                    if (_lifecycle.attempt != attempt) {
                        continue;
                    }
                    attempt = new JmDNSLifecycle.Attempt(++_lifecycle.nextAttempt,
                            Thread.currentThread(), false, budget);
                    _lifecycle.attempt = attempt;
                    owner = true;
                }
            }
            if (owner) {
                List<Throwable> initialFailures = new ArrayList<>();
                try {
                    afterCloseAttemptAdmission(attempt.id, true);
                } catch (Throwable failure) {
                    initialFailures.add(failure);
                }
                finishClose(attempt, initialFailures);
                attempt.outcome.report();
                return;
            }
            try {
                afterCloseAttemptAdmission(attempt.id, false);
                JmDNSLifecycle.Outcome outcome;
                if (Thread.interrupted()) {
                    throw new InterruptedException("Interrupted joining close");
                }
                synchronized (_lifecycle) {
                    while (attempt.outcome == null) {
                        budget.await(_lifecycle, "close attempt " + attempt.id);
                    }
                    outcome = attempt.outcome;
                }
                if (attempt.helper != null) {
                    awaitOwnedThread(attempt.helper, budget, "native close helper");
                }
                beforeCloseOutcomeConsumption(attempt.id);
                outcome.report();
                return;
            } catch (InterruptedException failure) {
                Thread.currentThread().interrupt();
                throw new JmDNSLifecycle.CloseIncompleteException("Interrupted waiting for JmDNS close", failure);
            } finally {
                synchronized (_lifecycle) {
                    attempt.joinedCallers--;
                    _lifecycle.notifyAll();
                }
            }
        }
    }

    private void awaitPreviousHelper(JmDNSLifecycle.Attempt attempt, JmDNSLifecycle.WaitBudget budget) {
        try {
            if (Thread.interrupted()) {
                throw new InterruptedException("Interrupted before close retry");
            }
            if (attempt.helper != null) {
                awaitOwnedThread(attempt.helper, budget, "previous native close helper");
            }
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new JmDNSLifecycle.CloseIncompleteException("Interrupted before JmDNS close retry", failure);
        }
    }

    /** The sole nonwaiting native entrypoint: Responder's exceptional timer path. */
    void requestCloseFromResponder() {
        final JmDNSLifecycle.Attempt attempt;
        synchronized (_lifecycle) {
            if (_lifecycle.terminalRequested || _lifecycle.attempt != null) {
                return; // Coalesce, including failure: native requests never retry.
            }
            _lifecycle.terminalRequested = true;
            attempt = new JmDNSLifecycle.Attempt(++_lifecycle.nextAttempt, null, true,
                    new JmDNSLifecycle.WaitBudget());
            _lifecycle.attempt = attempt;
        }
        try {
            Thread helper = new Thread(new Runnable() {
                @Override
                public void run() {
                    _lifecycle.enterDependent();
                    try {
                        finishClose(attempt, new ArrayList<Throwable>());
                    } finally {
                        _lifecycle.exitDependent();
                    }
                }
            }, _name + ".terminal-close");
            helper.setDaemon(false);
            synchronized (_lifecycle) {
                attempt.owner = helper;
                attempt.helper.thread = helper;
            }
            afterCloseAttemptAdmission(attempt.id, true);
            helper.start();
            synchronized (_lifecycle) {
                attempt.helper.started = true;
                attempt.helper.launchResolved = true;
                _lifecycle.notifyAll();
            }
        } catch (Throwable failure) {
            synchronized (_lifecycle) {
                attempt.helper.launchResolved = true;
                if (attempt.outcome == null) {
                    attempt.outcome = new JmDNSLifecycle.Outcome(attempt.id,
                            Collections.singletonList(failure));
                }
                _lifecycle.notifyAll();
            }
            logger.warn("Could not launch native terminal close helper", failure);
        }
    }

    private void finishClose(JmDNSLifecycle.Attempt attempt, List<Throwable> failures) {
        boolean interrupted = Thread.currentThread().isInterrupted();
        if (interrupted) {
            failures.add(new InterruptedException("Close owner was interrupted"));
        }
        try {
            disposeOwnedResources(attempt.budget, failures, interrupted);
        } catch (Throwable failure) {
            // All individual operations below are isolated; keep a final outcome
            // even if an unexpected bookkeeping failure escapes them.
            failures.add(failure);
        } finally {
            interrupted |= Thread.currentThread().isInterrupted();
            synchronized (_lifecycle) {
                attempt.outcome = new JmDNSLifecycle.Outcome(attempt.id, failures);
                _lifecycle.notifyAll();
            }
            if (interrupted) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private void disposeOwnedResources(JmDNSLifecycle.WaitBudget budget, List<Throwable> failures,
            boolean interrupted) {
        boolean handoffAcquired;
        synchronized (_lifecycle) {
            handoffAcquired = !_lifecycle.startupInProgress && _lifecycle.mutations == 0
                    && (_lifecycle.recovery == null || !_lifecycle.recovery.mutating);
        }
        if (!handoffAcquired && !interrupted) {
            try {
                synchronized (_lifecycle) {
                    while (_lifecycle.startupInProgress || _lifecycle.mutations != 0
                            || (_lifecycle.recovery != null && _lifecycle.recovery.mutating)) {
                        budget.await(_lifecycle, "producer/recovery mutation handoff");
                    }
                    handoffAcquired = true;
                }
            } catch (InterruptedException failure) {
                interrupted = true;
                failures.add(failure);
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        if (!handoffAcquired) {
            failures.add(new JmDNSLifecycle.CloseIncompleteException("Mutation ownership was not handed off"));
            // Timers and the executor are original, stable identities. Socket,
            // service and collector ownership still belongs to the live mutation
            // phase: never traverse/dispose/detach those as if handoff succeeded.
            initiateShutdownWithoutHandoff(failures);
            if (interrupted) {
                Thread.currentThread().interrupt();
            }
            return;
        }

        if (!_lifecycle.generalTimerDisposed) {
            try {
                this.cancelTimer();
                synchronized (_lifecycle) {
                    _lifecycle.generalTimerDisposed = true;
                }
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }

        if (_taskStarter != null && !_lifecycle.dispatchSealed) {
            // Resource-only retries must not wait for impossible protocol progress
            // once the original timer dispatch phase has irreversibly ended.
            // Real cancellation is attempted even when cancelState() returns false.
            // Keep the original socket and state timer usable for actual TTL=0 sends.
            Collection<ServiceInfo> services = new ArrayList<>(_services.values());
            try {
                this.cancelState();
            } catch (Throwable failure) {
                failures.add(failure);
            }
            for (ServiceInfo service : services) {
                try {
                    ((ServiceInfoImpl) service).cancelState();
                } catch (Throwable failure) {
                    failures.add(failure);
                }
            }
            if (_socket != null && !_socket.isClosed()) {
                try {
                    this.startCanceler();
                } catch (Throwable failure) {
                    failures.add(failure);
                }
                if (!interrupted) {
                    for (ServiceInfo service : services) {
                        try {
                            budget.pauseForGoodbyeWait();
                            ((ServiceInfoImpl) service).waitForCanceledInterruptibly(DNSConstants.CLOSE_TIMEOUT);
                        } catch (InterruptedException failure) {
                            interrupted = true;
                            failures.add(failure);
                            break;
                        } catch (Throwable failure) {
                            // Protocol best effort is distinct from resource disposal.
                            logger.warn("Service goodbye wait failed", failure);
                        } finally {
                            budget.resumeAfterGoodbyeWait();
                        }
                    }
                }
                if (!interrupted) {
                    try {
                        budget.pauseForGoodbyeWait();
                        _localHost.waitForCanceledInterruptibly(DNSConstants.CLOSE_TIMEOUT);
                    } catch (InterruptedException failure) {
                        interrupted = true;
                        failures.add(failure);
                    } catch (Throwable failure) {
                        logger.warn("Host goodbye wait failed", failure);
                    } finally {
                        budget.resumeAfterGoodbyeWait();
                    }
                }
            }

        }

        synchronized (_lifecycle) {
            // Even a task dequeued by Timer before cancel must pass this seal.
            _lifecycle.dispatchSealed = true;
        }
        if (!_lifecycle.stateTimerDisposed) {
            try {
                this.cancelStateTimer();
                synchronized (_lifecycle) {
                    _lifecycle.stateTimerDisposed = true;
                }
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        disposeSockets(failures);
        try {
            _executor.shutdown();
        } catch (Throwable failure) {
            failures.add(failure);
        }
        try {
            this.disposeServiceCollectors();
        } catch (Throwable failure) {
            failures.add(failure);
        }
        if (_shutdown != null) {
            try {
                Runtime.getRuntime().removeShutdownHook(_shutdown);
                _shutdown = null;
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        if (_lifecycle.generalTimerDisposed && _lifecycle.stateTimerDisposed && !_lifecycle.starterDetached) {
            try {
                if (_taskStarter != null) {
                    DNSTaskStarter.Factory.getInstance().disposeStarter(this, _taskStarter);
                }
                synchronized (_lifecycle) {
                    _lifecycle.starterDetached = true;
                }
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }

        // All unblock/shutdown actions precede every dependent-work drain.
        if (!interrupted) {
            try {
                synchronized (_lifecycle) {
                    while (_lifecycle.mutations != 0 || _lifecycle.submissions != 0
                            || _lifecycle.tasks != 0 || _lifecycle.callbacks != 0) {
                        budget.await(_lifecycle, "admitted tasks, callbacks and submissions");
                    }
                }
            } catch (InterruptedException failure) {
                interrupted = true;
                failures.add(failure);
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        if (!interrupted) {
            try {
                drainSocketListeners(budget);
            } catch (InterruptedException failure) {
                interrupted = true;
                failures.add(failure);
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        if (!interrupted) {
            try {
                drainRecoveries(budget);
            } catch (InterruptedException failure) {
                interrupted = true;
                failures.add(failure);
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        if (!interrupted) {
            try {
                awaitExecutor(budget);
            } catch (InterruptedException failure) {
                interrupted = true;
                failures.add(failure);
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        synchronized (_lifecycle) {
            if (!_lifecycle.generalTimerDisposed || !_lifecycle.stateTimerDisposed
                    || !_lifecycle.starterDetached || !_lifecycle.sockets.isEmpty()
                    || !_lifecycle.listeners.isEmpty() || !_lifecycle.recoveries.isEmpty()
                    || _lifecycle.startupInProgress || _lifecycle.mutations != 0 || _lifecycle.tasks != 0
                    || _lifecycle.callbacks != 0 || _lifecycle.submissions != 0
                    || !_executor.isTerminated() || _shutdown != null) {
                failures.add(new JmDNSLifecycle.CloseIncompleteException("JmDNS retains incomplete disposal obligations"));
            }
        }
        if (failures.isEmpty()) {
            _services.clear();
            _serviceCollectors.clear();
            _serviceListeners.clear();
            _typeListeners.clear();
            _listeners.clear();
            // Bookkeeping follows proof, never substitutes for it.
            _localHost.closeState();
            _localHost.advanceState(null);
        }
        if (interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    private void initiateShutdownWithoutHandoff(List<Throwable> failures) {
        if (_taskStarter != null && !_lifecycle.generalTimerDisposed) {
            try {
                this.cancelTimer();
                synchronized (_lifecycle) {
                    _lifecycle.generalTimerDisposed = true;
                }
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        synchronized (_lifecycle) {
            _lifecycle.dispatchSealed = true;
        }
        if (_taskStarter != null && !_lifecycle.stateTimerDisposed) {
            try {
                this.cancelStateTimer();
                synchronized (_lifecycle) {
                    _lifecycle.stateTimerDisposed = true;
                }
            } catch (Throwable failure) {
                failures.add(failure);
            }
        }
        try {
            _executor.shutdown();
        } catch (Throwable failure) {
            failures.add(failure);
        }
    }

    private void awaitExecutor(JmDNSLifecycle.WaitBudget budget) throws InterruptedException {
        if (!_executor.isTerminated()) {
            long remaining = budget.remainingNanos();
            if (remaining == 0L || !_executor.awaitTermination(remaining, TimeUnit.NANOSECONDS)) {
                throw new JmDNSLifecycle.CloseIncompleteException("Timed out waiting for callback executor termination");
            }
        }
    }

    private void drainRecoveries(JmDNSLifecycle.WaitBudget budget) throws InterruptedException {
        List<JmDNSLifecycle.Recovery> recoveries;
        synchronized (_lifecycle) {
            recoveries = new ArrayList<>(_lifecycle.recoveries);
        }
        for (JmDNSLifecycle.Recovery recovery : recoveries) {
            awaitOwnedThread(recovery, budget, "recovery worker");
            synchronized (_lifecycle) {
                _lifecycle.recoveries.remove(recovery);
                if (_lifecycle.recovery == recovery) {
                    _lifecycle.recovery = null;
                }
            }
        }
    }

    JmDNSLifecycle.Snapshot lifecycleSnapshot() {
        int listenerCount = _listeners.size();
        synchronized (_lifecycle) {
            return new JmDNSLifecycle.Snapshot(_lifecycle, _taskStarter, _executor, listenerCount);
        }
    }

    void beforeRecoverySocketPublication(MulticastSocket candidate) {
        // Package-private, outside-gate observation seam for the real-resource fixture.
    }

    void afterCloseAttemptAdmission(long attemptId, boolean owner) {
        // Package-private, outside-gate observation seam; no lifecycle authority.
    }

    void beforeCloseOutcomeConsumption(long attemptId) {
        // Joined callers retain their immutable attempt across this observation seam.
    }

    /**
     * {@inheritDoc}
     */
    @Override
    @Deprecated
    public void printServices() {
        System.err.println(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String toString() {
        final StringBuilder sb = new StringBuilder(2048);
        sb.append("\n");
        sb.append("\t---- Local Host -----");
        sb.append("\n\t");
        sb.append(_localHost);
        sb.append("\n\t---- Services -----");
        for (final Map.Entry<String, ServiceInfo> entry : _services.entrySet()) {
            sb.append("\n\t\tService: ");
            sb.append(entry.getKey());
            sb.append(": ");
            sb.append(entry.getValue());
        }
        sb.append("\n");
        sb.append("\t---- Types ----");
        for (final ServiceTypeEntry subtypes : _serviceTypes.values()) {
            sb.append("\n\t\tType: ");
            sb.append(subtypes.getType());
            sb.append(": ");
            sb.append(subtypes.isEmpty() ? "no subtypes" : subtypes);
        }
        sb.append("\n");
        sb.append(_cache.toString());
        sb.append("\n");
        sb.append("\t---- Service Collectors ----");
        for (final Map.Entry<String, ServiceCollector> entry : _serviceCollectors.entrySet()) {
            sb.append("\n\t\tService Collector: ");
            sb.append(entry.getKey());
            sb.append(": ");
            sb.append(entry.getValue());
        }
        sb.append("\n");
        sb.append("\t---- Service Listeners ----");
        for (final Map.Entry<String, List<ListenerStatus.ServiceListenerStatus>> entry : _serviceListeners.entrySet()) {
            sb.append("\n\t\tService Listener: ");
            sb.append(entry.getKey());
            sb.append(": ");
            sb.append(entry.getValue());
        }
        return sb.toString();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ServiceInfo[] list(String type) {
        return this.list(type, DNSConstants.SERVICE_INFO_TIMEOUT);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ServiceInfo[] list(String type, long timeout) {
        if (isTerminalRequested() || this.isCanceling() || this.isCanceled()) {
            return new ServiceInfo[0];
        }
        this.cleanCache();
        ServiceCollector collector = ensureServiceCollector(type);
        return collector != null ? collector.list(timeout) : new ServiceInfo[0];
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Map<String, ServiceInfo[]> listBySubtype(String type) {
        return this.listBySubtype(type, DNSConstants.SERVICE_INFO_TIMEOUT);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Map<String, ServiceInfo[]> listBySubtype(String type, long timeout) {
        Map<String, List<ServiceInfo>> map = new HashMap<>(5);
        for (ServiceInfo info : this.list(type, timeout)) {
            String subtype = info.getSubtype().toLowerCase();
            if (!map.containsKey(subtype)) {
                map.put(subtype, new ArrayList<>(10));
            }
            map.get(subtype).add(info);
        }

        Map<String, ServiceInfo[]> result = new HashMap<>(map.size());
        for (final Map.Entry<String, List<ServiceInfo>> entry : map.entrySet()) {
            final String subtype = entry.getKey();
            final List<ServiceInfo> infoForSubType = entry.getValue();
            result.put(subtype, infoForSubType.toArray(new ServiceInfo[0]));
        }

        return result;
    }

    /**
     * This method disposes all ServiceCollector instances which have been created by calls to method <code>list(type)</code>.
     *
     * @see #list
     */
    private void disposeServiceCollectors() {
        for (final Map.Entry<String, ServiceCollector> entry : _serviceCollectors.entrySet()) {
            ServiceCollector collector = entry.getValue();
            List<ServiceListenerStatus> listeners = _serviceListeners.get(entry.getKey());
            if (listeners != null) {
                synchronized (listeners) {
                    Iterator<ServiceListenerStatus> iterator = listeners.iterator();
                    while (iterator.hasNext()) {
                        if (iterator.next().getListener() == collector) {
                            iterator.remove();
                        }
                    }
                    if (listeners.isEmpty()) {
                        _serviceListeners.remove(entry.getKey(), listeners);
                    }
                }
            }
            _serviceCollectors.remove(entry.getKey(), collector);
        }
    }

    /**
     * Instances of ServiceCollector are used internally to speed up the performance of method <code>list(type)</code>.
     *
     * @see #list
     */
    private static class ServiceCollector implements ServiceListener {

        /**
         * A set of collected service instance names.
         */
        private final ConcurrentMap<String, ServiceInfo> _infos;

        /**
         * A set of collected service event waiting to be resolved.
         */
        private final ConcurrentMap<String, ServiceEvent> _events;

        /**
         * This is the type we are listening for (only used for debugging).
         */
        private final String _type;

        /**
         * This is used to force a wait on the first invocation of list.
         */
        private volatile boolean _needToWaitForInfos;

        public ServiceCollector(String type) {
            super();
            _infos = new ConcurrentHashMap<>();
            _events = new ConcurrentHashMap<>();
            _type = type;
            _needToWaitForInfos = true;
        }

        /**
         * A service has been added.
         *
         * @param event
         *            service event
         */
        @Override
        public void serviceAdded(ServiceEvent event) {
            synchronized (this) {
                ServiceInfo info = event.getInfo();
                if ((info != null) && (info.hasData())) {
                    _infos.put(event.getName(), info);
                } else {
                    String subtype = (info != null ? info.getSubtype() : "");
                    info = ((JmDNSImpl) event.getDNS()).resolveServiceInfo(event.getType(), event.getName(), subtype, true);
                    if (info != null) {
                        _infos.put(event.getName(), info);
                    } else {
                        _events.put(event.getName(), event);
                    }
                }
            }
        }

        /**
         * A service has been removed.
         *
         * @param event
         *            service event
         */
        @Override
        public void serviceRemoved(ServiceEvent event) {
            synchronized (this) {
                _infos.remove(event.getName());
                _events.remove(event.getName());
            }
        }

        /**
         * A service has been resolved. Its details are now available in the ServiceInfo record.
         *
         * @param event
         *            service event
         */
        @Override
        public void serviceResolved(ServiceEvent event) {
            synchronized (this) {
                _infos.put(event.getName(), event.getInfo());
                _events.remove(event.getName());
            }
        }

        /**
         * Returns an array of all service infos which have been collected by this ServiceCollector.
         *
         * @param timeout
         *            timeout if the info list is empty.
         * @return Service Info array
         */
        public ServiceInfo[] list(long timeout) {
            if (_infos.isEmpty() || !_events.isEmpty() || _needToWaitForInfos) {
                long loops = (timeout / 200L);
                if (loops < 1) {
                    loops = 1;
                }
                for (int i = 0; i < loops; i++) {
                    try {
                        Thread.sleep(200);
                    } catch (final InterruptedException e) {
                        /* Stub */
                    }
                    if (_events.isEmpty() && !_infos.isEmpty() && !_needToWaitForInfos) {
                        break;
                    }
                }
            }
            _needToWaitForInfos = false;
            return _infos.values().toArray(new ServiceInfo[0]);
        }

        /**
         * {@inheritDoc}
         */
        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder();
            sb.append("\n\tType: ");
            sb.append(_type);
            if (_infos.isEmpty()) {
                sb.append("\n\tNo services collected.");
            } else {
                sb.append("\n\tServices");
                for (final Map.Entry<String, ServiceInfo> entry : _infos.entrySet()) {
                    sb.append("\n\t\tService: ");
                    sb.append(entry.getKey());
                    sb.append(": ");
                    sb.append(entry.getValue());
                }
            }
            if (_events.isEmpty()) {
                sb.append("\n\tNo event queued.");
            } else {
                sb.append("\n\tEvents");
                for (final Map.Entry<String, ServiceEvent> entry : _events.entrySet()) {
                    sb.append("\n\t\tEvent: ");
                    sb.append(entry.getKey());
                    sb.append(": ");
                    sb.append(entry.getValue());
                }
            }
            return sb.toString();
        }

    }

    static String toUnqualifiedName(String type, String qualifiedName) {
        String loType = type.toLowerCase();
        String loQualifiedName = qualifiedName.toLowerCase();
        if (loQualifiedName.endsWith(loType) && !(loQualifiedName.equals(loType))) {
            return qualifiedName.substring(0, qualifiedName.length() - type.length() - 1);
        }
        return qualifiedName;
    }

    public Map<String, ServiceInfo> getServices() {
        return _services;
    }

    public void setLastThrottleIncrement(long lastThrottleIncrement) {
        if (!beginProducerMutation()) {
            return;
        }
        try {
            this._lastThrottleIncrement = lastThrottleIncrement;
        } finally {
            endProducerMutation();
        }
    }

    public long getLastThrottleIncrement() {
        return _lastThrottleIncrement;
    }

    public void setThrottle(int throttle) {
        if (!beginProducerMutation()) {
            return;
        }
        try {
            this._throttle = throttle;
        } finally {
            endProducerMutation();
        }
    }

    public int getThrottle() {
        return _throttle;
    }

    public static Random getRandom() {
        return _random;
    }

    public void ioLock() {
        _ioLock.lock();
    }

    public void ioUnlock() {
        _ioLock.unlock();
    }

    public void setPlannedAnswer(DNSIncoming plannedAnswer) {
        if (!beginProducerMutation()) {
            return;
        }
        try {
            this._plannedAnswer = plannedAnswer;
        } finally {
            endProducerMutation();
        }
    }

    public DNSIncoming getPlannedAnswer() {
        return _plannedAnswer;
    }

    void setLocalHost(HostInfo localHost) {
        this._localHost = localHost;
    }

    public Map<String, ServiceTypeEntry> getServiceTypes() {
        return _serviceTypes;
    }

    public MulticastSocket getSocket() {
        return _socket;
    }

    public InetAddress getGroup() {
        return _group;
    }

    @Override
    public Delegate getDelegate() {
        return this._delegate;
    }

    @Override
    public Delegate setDelegate(Delegate delegate) {
        Delegate previous = this._delegate;
        this._delegate = delegate;
        return previous;
    }

}
