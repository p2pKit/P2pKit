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

import java.util.ArrayList;
import java.util.EventListener;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import dev.p2pkit.transport.lan.internal.jmdns.JmDNS;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceListener;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceTypeListener;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * This class track the status of listener.<br/>
 * The main purpose of this class is to collapse consecutive events so that we can guarantee the correct call back sequence.
 *
 * @param <T>
 *            listener type
 *
 */
public class ListenerStatus<T extends EventListener> {

    public static class ServiceListenerStatus extends ListenerStatus<ServiceListener> {
        private final Logger logger = LoggerFactory.getLogger(ServiceListenerStatus.class);

        private final ConcurrentMap<String, ServiceInfo> _addedServices;

        /**
         * @param listener
         *            listener being tracked.
         * @param synch
         *            true if that listener can be called asynchronously
         */
        public ServiceListenerStatus(ServiceListener listener, boolean synch) {
            super(listener, synch);
            _addedServices = new ConcurrentHashMap<>(32);
        }

        /**
         * A service has been added.<br/>
         * <b>Note:</b>This event is only the service added event. The service info associated with this event does not include resolution information.<br/>
         * To get the full resolved information you need to listen to {@link #serviceResolved(ServiceEvent)} or call {@link JmDNS#getServiceInfo(String, String, long)}
         *
         * <pre>
         *  ServiceInfo info = event.getDNS().getServiceInfo(event.getType(), event.getName())
         * </pre>
         * <p>
         * Please note that service resolution may take a few second to resolve.
         * </p>
         *
         * @param event
         *            The ServiceEvent providing the name and fully qualified type of the service.
         */
        void serviceAdded(ServiceEvent event) {
            String qualifiedName = event.getName() + "." + event.getType();
            if (null == _addedServices.putIfAbsent(qualifiedName, event.getInfo().clone())) {
                this.getListener().serviceAdded(event);
                ServiceInfo info = event.getInfo();
                if ((info != null) && (info.hasData())) {
                    this.getListener().serviceResolved(event);
                }
            } else {
                logger.debug("Service Added called for a service already added: {}", event);
            }
        }

        /**
         * A service has been removed.
         *
         * @param event
         *            The ServiceEvent providing the name and fully qualified type of the service.
         */
        void serviceRemoved(ServiceEvent event) {
            String qualifiedName = event.getName() + "." + event.getType();
            if (_addedServices.remove(qualifiedName, _addedServices.get(qualifiedName))) {
                this.getListener().serviceRemoved(event);
            } else {
                logger.debug("Service Removed called for a service already removed: {}", event);
            }
        }

        /**
         * A service has been resolved. Its details are now available in the ServiceInfo record.<br/>
         * <b>Note:</b>This call back will never be called if the service does not resolve.<br/>
         *
         * @param event
         *            The ServiceEvent providing the name, the fully qualified type of the service, and the service info record.
         */
        synchronized void serviceResolved(ServiceEvent event) {
            ServiceInfo info = event.getInfo();
            if ((info != null) && (info.hasData())) {
                String qualifiedName = event.getName() + "." + event.getType();
                ServiceInfo previousServiceInfo = _addedServices.get(qualifiedName);
                if (!_sameInfo(info, previousServiceInfo)) {
                    if (null == previousServiceInfo) {
                        if (null == _addedServices.putIfAbsent(qualifiedName, info.clone())) {
                            this.getListener().serviceResolved(event);
                        }
                    } else {
                        if (_addedServices.replace(qualifiedName, previousServiceInfo, info.clone())) {
                            this.getListener().serviceResolved(event);
                        }
                    }
                } else {
                    logger.debug("Service Resolved called for a service already resolved: {}", event);
                }
            } else {
                logger.warn("Service Resolved called for an unresolved event: {}", event);

            }
        }

        private static boolean _sameInfo(ServiceInfo info, ServiceInfo lastInfo) {
            if (info == null) return false;
            if (lastInfo == null) return false;
            if (!info.equals(lastInfo)) return false;
            if (info.getPort() != lastInfo.getPort()) return false;
            byte[] text = info.getTextBytes();
            byte[] lastText = lastInfo.getTextBytes();
            if (text.length != lastText.length) return false;
            for (int i = 0; i < text.length; i++) {
                if (text[i] != lastText[i]) return false;
            }

            return info.hasSameAddresses(lastInfo);
        }

        /*
         * (non-Javadoc)
         * @see java.lang.Object#toString()
         */
        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder(2048);
            sb.append("[Status for ");
            sb.append(this.getListener().toString());
            if (_addedServices.isEmpty()) {
                sb.append(" no type event ");
            } else {
                sb.append(" (");
                for (final String service : _addedServices.keySet()) {
                    sb.append(service).append(", ");
                }
                sb.append(") ");
            }
            sb.append("]");
            return sb.toString();
        }

    }

    public static class ServiceTypeListenerStatus extends ListenerStatus<ServiceTypeListener> {
        private final Logger                       logger = LoggerFactory.getLogger(ServiceTypeListenerStatus.class);

        // Deduplication must not recreate the old immortal remote-type map as
        // types expire/are evicted. A forgotten type may be announced again.
        private final LinkedHashMap<String, Long> _addedTypes;
        private long _typeBytes;

        /**
         * @param listener
         *            listener being tracked.
         * @param synch
         *            true if that listener can be called asynchronously
         */
        public ServiceTypeListenerStatus(ServiceTypeListener listener, boolean synch) {
            super(listener, synch);
            _addedTypes = new LinkedHashMap<>(32);
        }

        /**
         * A new service type was discovered.
         *
         * @param event
         *            The service event providing the fully qualified type of the service.
         */
        void serviceTypeAdded(ServiceEvent event) {
            if (rememberType(event.getType())) {
                this.getListener().serviceTypeAdded(event);
            } else {
                logger.trace("Service Type Added called for a service type already added: {}", event);
            }
        }

        /**
         * A new subtype for the service type was discovered.
         *
         * <pre>
         * &lt;sub&gt;._sub.&lt;app&gt;.&lt;protocol&gt;.&lt;servicedomain&gt;.&lt;parentdomain&gt;.
         * </pre>
         *
         * @param event
         *            The service event providing the fully qualified type of the service with subtype.
         */
        void subTypeForServiceTypeAdded(ServiceEvent event) {
            if (rememberType(event.getType())) {
                this.getListener().subTypeForServiceTypeAdded(event);
            } else {
                logger.trace("Service Sub Type Added called for a service sub type already added: {}", event);
            }
        }

        private synchronized boolean rememberType(String type) {
            String key = type.toLowerCase(Locale.ROOT);
            if (_addedTypes.containsKey(key)) {
                return false;
            }
            long bytes = 128L + 2L * key.length();
            if (bytes > DNSCache.MAX_RETAINED_BYTES) {
                return true; // A local caller's oversized type is not retained.
            }
            Iterator<Map.Entry<String, Long>> iterator = _addedTypes.entrySet().iterator();
            while (_addedTypes.size() >= 2 * DNSCache.MAX_RECORDS
                    || _typeBytes + bytes > DNSCache.MAX_RETAINED_BYTES) {
                _typeBytes -= iterator.next().getValue();
                iterator.remove();
            }
            _addedTypes.put(key, bytes);
            _typeBytes += bytes;
            return true;
        }

        synchronized int retainedTypeCount() {
            return _addedTypes.size();
        }

        synchronized long retainedTypeBytes() {
            return _typeBytes;
        }

        private synchronized List<String> rememberedTypes() {
            return new ArrayList<>(_addedTypes.keySet());
        }

        /*
         * (non-Javadoc)
         * @see java.lang.Object#toString()
         */
        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder(2048);
            sb.append("[Status for ");
            sb.append(this.getListener().toString());
            List<String> types = rememberedTypes();
            if (types.isEmpty()) {
                sb.append(" no type event ");
            } else {
                sb.append(" (");
                for (final String type : types) {
                    sb.append(type).append(", ");
                }
                sb.append(") ");
            }
            sb.append("]");
            return sb.toString();
        }

    }

    public final static boolean SYNCHRONOUS  = true;
    public final static boolean ASYNCHRONOUS = false;

    private final T             _listener;

    private final boolean       _synch;

    /**
     * @param listener
     *            listener being tracked.
     * @param synch
     *            true if that listener can be called asynchronously
     */
    public ListenerStatus(T listener, boolean synch) {
        super();
        _listener = listener;
        _synch = synch;
    }

    /**
     * @return the listener
     */
    public T getListener() {
        return _listener;
    }

    /**
     * Return <code>true</code> if the listener must be called synchronously.
     *
     * @return the synch
     */
    public boolean isSynchronous() {
        return _synch;
    }

    /*
     * (non-Javadoc)
     * @see java.lang.Object#hashCode()
     */
    @Override
    public int hashCode() {
        return this.getListener().hashCode();
    }

    /*
     * (non-Javadoc)
     * @see java.lang.Object#equals(java.lang.Object)
     */
    @Override
    public boolean equals(Object obj) {
        return (obj instanceof ListenerStatus) && this.getListener().equals(((ListenerStatus<?>) obj).getListener());
    }

    /*
     * (non-Javadoc)
     * @see java.lang.Object#toString()
     */
    @Override
    public String toString() {
        return "[Status for " + this.getListener().toString() + "]";
    }
}
