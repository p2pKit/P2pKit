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

import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * A table of DNS entries. This is a map table which can handle multiple entries with the same name.
 * <p>
 * Storing multiple entries with the same name is implemented using a linked list. This is hidden from the user and can change in later implementation.
 * </p>
 * <p>
 * Here's how to iterate over all entries:
 *
 * <pre>
 *       for (Iterator i=dnscache.allValues().iterator(); i.hasNext(); ) {
 *             DNSEntry entry = i.next();
 *             ...do something with entry...
 *       }
 * </pre>
 * <p>
 * And here's how to iterate over all entries having a given name:
 *
 * <pre>
 *       for (Iterator i=dnscache.getDNSEntryList(name).iterator(); i.hasNext(); ) {
 *             DNSEntry entry = i.next();
 *           ...do something with entry...
 *       }
 * </pre>
 *
 * @author Arthur van Hoff, Werner Randelshofer, Rick Blair, Pierre Frisch
 */
public class DNSCache extends AbstractMap<String, List<DNSEntry>> {

    // Per handle, before any service/peer callback. Allows several records for
    // each of the SDK's 256 peers without granting arbitrary remote cardinality.
    static final int MAX_RECORDS = 4096;
    static final long MAX_RETAINED_BYTES = 8L * 1024L * 1024L;

    private final Logger        logger              = LoggerFactory.getLogger(DNSCache.class);

    private final Map<String, List<DNSEntry>> entries;
    // DNSEntry.equals does not include the subtype. Account by identity so
    // distinct subtype PTRs for the same service cannot alias one budget slot.
    private final Map<DNSEntry, Long> costs = new IdentityHashMap<>();
    private final List<DNSEntry> insertionOrder = new ArrayList<>();
    private final int maxRecords;
    private final long maxBytes;
    private long retainedBytes;
    private boolean pressureReported;
    private boolean pressurePending;

    /**
     *
     */
    public DNSCache() {
        this(1024);
    }

    /**
     * @param map
     */
    public DNSCache(DNSCache map) {
        this(map != null ? map.size() : 1024,
                map != null ? map.maxRecords : MAX_RECORDS,
                map != null ? map.maxBytes : MAX_RETAINED_BYTES);
        if (map != null) {
            for (DNSEntry entry : map.allValues()) {
                addDNSEntry(entry);
            }
        }
    }

    /**
     * Create a table with a given initial size.
     *
     * @param initialCapacity
     */
    public DNSCache(int initialCapacity) {
        this(initialCapacity, MAX_RECORDS, MAX_RETAINED_BYTES);
    }

    DNSCache(int initialCapacity, int maxRecords, long maxBytes) {
        if (maxRecords <= 0 || maxBytes <= 0) {
            throw new IllegalArgumentException("DNS cache budgets must be positive");
        }
        this.entries = new LinkedHashMap<>(Math.min(initialCapacity, maxRecords));
        this.maxRecords = maxRecords;
        this.maxBytes = maxBytes;
    }

    // ====================================================================
    // Map

    /**
     * {@inheritDoc}
     */
    @Override
    protected Object clone() throws CloneNotSupportedException {
        return new DNSCache(this);
    }

    // ====================================================================

    /**
     * Returns all entries in the cache
     *
     * @return all entries in the cache
     */
    public synchronized Collection<DNSEntry> allValues() {
        return new ArrayList<>(insertionOrder);
    }

    // Never expose mutable lists or inherited map writes that bypass accounting.
    @Override
    public synchronized Set<Entry<String, List<DNSEntry>>> entrySet() {
        Set<Entry<String, List<DNSEntry>>> result = new LinkedHashSet<>();
        for (Entry<String, List<DNSEntry>> entry : entries.entrySet()) {
            result.add(new SimpleImmutableEntry<>(entry.getKey(),
                    Collections.unmodifiableList(new ArrayList<>(entry.getValue()))));
        }
        return Collections.unmodifiableSet(result);
    }

    @Override
    public synchronized List<DNSEntry> get(Object key) {
        List<DNSEntry> result = entries.get(key);
        return result == null ? null : Collections.unmodifiableList(new ArrayList<>(result));
    }

    @Override
    public synchronized int size() {
        return entries.size();
    }

    @Override
    public synchronized void clear() {
        entries.clear();
        costs.clear();
        insertionOrder.clear();
        retainedBytes = 0;
    }

    synchronized int recordCount() {
        return costs.size();
    }

    synchronized long retainedBytes() {
        return retainedBytes;
    }

    synchronized boolean containsRecord(DNSEntry entry) {
        return costs.containsKey(entry);
    }

    synchronized boolean canRetain(DNSEntry entry) {
        if (retainedSize(entry) > maxBytes) {
            reportPressure();
            return false;
        }
        return true;
    }

    /**
     * Iterate only over items with matching name. Returns a list of DNSEntry or null. To retrieve all entries, one must iterate over this linked list.
     *
     * @param name
     * @return list of DNSEntries
     */
    public synchronized Collection<? extends DNSEntry> getDNSEntryList(String name) {
        if (name == null)
            return Collections.emptyList();
        return new ArrayList<>(getEntryListOrEmpty(name.toLowerCase(Locale.ROOT)));
    }

    /**
     * Get a matching DNS entry from the table (using isSameEntry). Returns the entry that was found.
     *
     * @param dnsEntry
     * @return DNSEntry
     */
    public synchronized DNSEntry getDNSEntry(DNSEntry dnsEntry) {
        if (dnsEntry == null)
            return  null;
        String key = dnsEntry.getKey();
        DNSEntry match = null;
        for (DNSEntry testDNSEntry : getEntryListOrEmpty(key)) {
            if (testDNSEntry.isSameEntry(dnsEntry)) {
                // Prefer the exact value in a multivalued RRset so refreshing
                // its second address does not append a duplicate or miss its TTL.
                if (testDNSEntry.equals(dnsEntry))
                    return testDNSEntry;
                if (match == null)
                    match = testDNSEntry;
            }
        }
        return match;
    }

    /**
     * Get a matching DNS entry from the table.
     *
     * @param name
     * @param type
     * @param recordClass
     * @return DNSEntry
     */
    public synchronized DNSEntry getDNSEntry(String name, DNSRecordType type, DNSRecordClass recordClass) {
        if (name == null)
            return null;

        String key = name.toLowerCase(Locale.ROOT);
        for (DNSEntry testDNSEntry : getEntryListOrEmpty(key)) {
            if (testDNSEntry.matchRecordType(type) && testDNSEntry.matchRecordClass(recordClass))
                return testDNSEntry;
        }
        return null;
    }

    /**
     * Get all matching DNS entries from the table.
     *
     * @param name
     * @param type
     * @param recordClass
     * @return list of entries
     */
    public synchronized Collection<? extends DNSEntry> getDNSEntryList(String name, DNSRecordType type, DNSRecordClass recordClass) {
        if (name == null)
            return Collections.emptyList();

        String key = name.toLowerCase(Locale.ROOT);
        ArrayList<DNSEntry> result = new ArrayList<>(getEntryListOrEmpty(key));
        // remove records that do not match
        result.removeIf(testDNSEntry -> !testDNSEntry.matchRecordType(type) || (!testDNSEntry.matchRecordClass(recordClass)));
        return result;
    }

    /**
     * Adds an entry to the table.
     *
     * @param dnsEntry
     * @return true if the entry was added
     */
    public boolean addDNSEntry(DNSEntry dnsEntry) {
        return addDNSEntry(dnsEntry, System.currentTimeMillis(), new ArrayList<DNSEntry>());
    }

    synchronized boolean addDNSEntry(DNSEntry dnsEntry, long now, List<DNSEntry> evicted) {
        if (dnsEntry == null || costs.containsKey(dnsEntry))
            return false;
        for (DNSEntry entry : getEntryListOrEmpty(dnsEntry.getKey())) {
            if (entry.isSameEntry(dnsEntry) && entry.equals(dnsEntry)) {
                return false;
            }
        }
        long cost = retainedSize(dnsEntry);
        if (cost > maxBytes) {
            reportPressure();
            return false;
        }
        if (costs.size() >= maxRecords || retainedBytes + cost > maxBytes) {
            // Prefer expired records, then oldest retained insertion. Updates do
            // not acquire an immortal slot by extending an advertised TTL.
            for (DNSEntry entry : new ArrayList<>(insertionOrder)) {
                if (entry.isExpired(now)) {
                    removeDNSEntry(entry);
                    evicted.add(entry);
                }
            }
            while (costs.size() >= maxRecords || retainedBytes + cost > maxBytes) {
                DNSEntry oldest = insertionOrder.get(0);
                removeDNSEntry(oldest);
                evicted.add(oldest);
                reportPressure();
            }
        }
        String key = dnsEntry.getKey();
        List<DNSEntry> entryList = entries.get(key);
        if (entryList == null) {
            entryList = new ArrayList<>(3);
            entries.put(key, entryList);
        }
        entryList.add(dnsEntry);
        costs.put(dnsEntry, cost);
        insertionOrder.add(dnsEntry);
        retainedBytes += cost;
        return true;
    }

    /**
     * Removes a specific entry from the table. Returns true if the entry was found.
     *
     * @param dnsEntry
     * @return true if the entry was removed
     */
    public synchronized boolean removeDNSEntry(DNSEntry dnsEntry) {
        if (dnsEntry == null)
            return false;
        String key = dnsEntry.getKey();
        List<DNSEntry> entryList = entries.get(key);
        if (entryList == null)
            return false;
        DNSEntry removed = null;
        for (int i = 0; i < entryList.size(); i++) {
            DNSEntry candidate = entryList.get(i);
            if (candidate == dnsEntry || (candidate.isSameEntry(dnsEntry) && candidate.equals(dnsEntry))) {
                removed = entryList.remove(i);
                break;
            }
        }
        if (removed == null)
            return false;
        retainedBytes -= costs.remove(removed);
        for (int i = 0; i < insertionOrder.size(); i++) {
            if (insertionOrder.get(i) == removed) {
                insertionOrder.remove(i);
                break;
            }
        }
        if (entryList.isEmpty()) {
            entries.remove(key);
        }
        return true;
    }

    /**
     * Replace an existing entry by a new one.<br/>
     * <b>Note:</b> the 2 entries must have the same key.
     *
     * @param newDNSEntry
     * @param existingDNSEntry
     * @return <code>true</code> if the entry has been replaced, <code>false</code> otherwise.
     */
    public boolean replaceDNSEntry(DNSEntry newDNSEntry, DNSEntry existingDNSEntry) {
        return replaceDNSEntry(newDNSEntry, existingDNSEntry,
                System.currentTimeMillis(), new ArrayList<DNSEntry>());
    }

    synchronized boolean replaceDNSEntry(DNSEntry newDNSEntry, DNSEntry existingDNSEntry,
            long now, List<DNSEntry> evicted) {
        if (newDNSEntry == null || existingDNSEntry == null || !newDNSEntry.getKey().equals(existingDNSEntry.getKey()))
            return false;
        if (retainedSize(newDNSEntry) > maxBytes) {
            reportPressure();
            return false; // Preserve the old usable value on an oversized replacement.
        }
        removeDNSEntry(existingDNSEntry);
        return addDNSEntry(newDNSEntry, now, evicted);
    }

    private List<DNSEntry> getEntryListOrEmpty(String key) {
        List<DNSEntry> entryList = entries.get(key);
        if (entryList == null)
            return Collections.emptyList();
        return entryList;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public synchronized String toString() {
        StringBuilder sb = new StringBuilder(2000);
        sb.append("\n\t---- cache ----");
        for (Map.Entry<String, List<DNSEntry>> entry : entries.entrySet()) {
            sb.append("\n\n\t\tname '").append(entry.getKey()).append('\'');
            List<DNSEntry> entryList = entry.getValue();
            if (entryList == null)
                continue;
            for (DNSEntry dnsEntry : entryList) {
                sb.append("\n\t\t\t").append(dnsEntry.toString());
            }
        }
        return sb.toString();
    }

    /**
     * Deterministic retained-byte charge, not a VM heap-size measurement. Count
     * every variable-length field (including derived names), plus a fixed
     * allowance for record/map/list/address objects. No serialization allocation.
     */
    static long retainedSize(DNSEntry entry) {
        long size = 1024L + stringSize(entry.getName()) + stringSize(entry.getKey()) + stringSize(entry.getType());
        for (String part : entry.getQualifiedNameMap().values()) {
            size += stringSize(part);
        }
        if (entry instanceof DNSRecord.Text) {
            size += ((DNSRecord.Text) entry).getText().length;
        } else if (entry instanceof DNSRecord.Pointer) {
            size += stringSize(((DNSRecord.Pointer) entry).getAlias());
        } else if (entry instanceof DNSRecord.Service) {
            size += stringSize(((DNSRecord.Service) entry).getServer());
        } else if (entry instanceof DNSRecord.HostInformation) {
            DNSRecord.HostInformation info = (DNSRecord.HostInformation) entry;
            size += stringSize(info._cpu) + stringSize(info._os);
        }
        return size;
    }

    private static long stringSize(String value) {
        return value == null ? 0L : 2L * value.length();
    }

    private void reportPressure() {
        if (!pressureReported) {
            pressureReported = true;
            pressurePending = true;
        }
    }

    synchronized boolean takePressureNotice() {
        boolean pending = pressurePending;
        pressurePending = false;
        return pending;
    }

    /**
     * Prints the content of the cache to the {@link #logger}.
     */
    public void logCachedContent() {
        if (!logger.isTraceEnabled()) {
            return;
        }

        logger.trace("Cached DNSEntries: {}", this);
    }

}
